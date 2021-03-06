# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides a generic disk reader and writer based on HDF5.
To use it, you have to enable the "HDF5" feature during installation, i.e. pip install nexxT[HDF5]
"""
import datetime
from pathlib import Path
import string
import time
import logging
import os
import numpy as np
import h5py
from PySide2.QtCore import Signal
from nexxT.interface import Filter, Services
from nexxT.core.Utils import handleException, isMainThread
from nexxT.filters.GenericReader import GenericReader, GenericReaderFile

logger = logging.getLogger(__name__)

class Hdf5Writer(Filter):
    """
    Generic nexxT filter for writing HDF5 files.
    """
    statusUpdate = Signal(str, float, "qlonglong")

    def __init__(self, env):
        super().__init__(True, False, env)
        self._currentFile = None
        self._lastDataTimestamp = None
        self._lastRcvTimestamp = None
        self._name = None
        self._basetime = None
        self.propertyCollection().defineProperty(
            "filename",
            "${DATE}_${TIME}_${FILTER_NAME}.h5",
            "Template for generated files. The following variables can be used: ${DATE}, ${TIME}, ${FILTER_NAME}")
        self._useRcvTimestamps = self.propertyCollection().defineProperty(
            "use_receive_timestamps",
            True,
            "Flag whether or not to use receive timestamps, so that the playback timing is approximately equal to the "
            "recording"
        )
        self.propertyCollection().defineProperty(
            "silent_overwrite",
            False,
            "Whether or not silently overwrite existing files"
        )
        self.propertyCollection().defineProperty(
            "buffer_period",
            1.0,
            "The minimum buffer period in seconds. Pass 0.0 to disable buffering based on time.\n"
            "Note that high numbers might require a lot of memory.",
            options=dict(min=0.0, max=3600.0)
        )
        self.propertyCollection().defineProperty(
            "buffer_samples",
            0,
            "The minimum number of samples to buffer. Pass 0 to disable buffering based on samples.\n"
            "Note that high numbers might require a lot of memory.",
            options=dict(min=0, max=1000000)
        )
        self.propertyCollection().defineProperty(
            "use_posix_fadvise_if_available",
            True,
            "If available, hint the kernel with posix_fadvise(..., POSIX_FADV_DONTNEED). Might give\n"
            "better write performance on linux systems, because there are no bursts of written data.\n"
            "Note: You can also try to use echo 0 > /proc/sys/vm/dirty_writeback_centisecs to disable\n"
            "write caching."
        )
        self.propertyCollection().propertyChanged.connect(self._propertyChanged)
        # create a numpy-style dtype for the contents of a datasample
        type_content = h5py.vlen_dtype(np.dtype(np.uint8))
        type_timestamp = np.int64
        type_dataType = h5py.string_dtype()
        self.dtype = [('content', type_content),
                      ('dataType', type_dataType),
                      ('dataTimestamp', type_timestamp),
                      ('rcvTimestamp', type_timestamp),
                      ]

    def onInit(self):
        for p in self.getDynamicInputPorts():
            p.setInterthreadDynamicQueue(True)

    def onStart(self):
        """
        Registers itself to the recording control service

        :return:
        """
        self._propertyChanged(self.propertyCollection(), "buffer_samples")
        srv = Services.getService("RecordingControl")
        srv.setupConnections(self)
        if isMainThread():
            logger.warning("Hdf5Writer seems to run in GUI thread. Consider to move it to a seperate thread.")

    def _propertyChanged(self, propColl, name):
        if name in ["buffer_samples", "buffer_period"]:
            qss = propColl.getProperty("buffer_samples")
            qsp = propColl.getProperty("buffer_period")
            for p in self.getDynamicInputPorts():
                p.setQueueSize(qss, qsp)

    def onStop(self):
        """
        De-registers itself from the recording control service

        :return:
        """
        srv = Services.getService("RecordingControl")
        srv.removeConnections(self)

    @handleException
    def _startRecording(self, directory):
        # reset the current file
        self._currentFile = None
        self._name = self.propertyCollection().getProperty("filename")
        self._useRcvTimestamps = self.propertyCollection().getProperty("use_receive_timestamps")
        # interpolate the name with optionally given variables
        dt = datetime.datetime.now()
        variables = dict(DATE=dt.date().strftime('%Y%m%d'),
                         TIME=dt.time().strftime('%H%M%S'),
                         FILTER_NAME=self.propertyCollection().objectName())
        self._name = string.Template(self._name).safe_substitute(variables)
        if not (self._name.endswith(".h5") or self._name.endswith(".hdf5") or self._name.endswith(".hdf")):
            self._name += ".h5"
        mode = "w" if self.propertyCollection().getProperty("silent_overwrite") else "x"
        # create a new HDF5 file / truncate an existing file containing a stream for all existing input ports
        self._currentFile = h5py.File(Path(directory) / self._name, mode=mode)
        streams = self._currentFile.create_group("streams")
        for port in self.getDynamicInputPorts():
            streams.create_dataset(port.name(), (0,), chunks=(1,), maxshape=(None,), dtype=self.dtype)
        # setup variables needed during processing
        self._basetime = time.perf_counter_ns()
        # initial status update
        self.statusUpdate.emit(self._name, 0.0, 0)

    def startRecording(self, directory):
        """
        Called on a recording start event.

        :param directory: the directory where the recording is expected to be created.
        :return:
        """
        self._startRecording(directory)

    @handleException
    def _stopRecording(self):
        if self._currentFile is not None:
            # final status update
            self.statusUpdate.emit(self._name, -1, -1)
            # close the file
            self._currentFile.close()
            self._currentFile = None

    def stopRecording(self):
        """
        Called on a recording stop event.

        :param directory: the directory where the recording is expected to be created.
        :return:
        """
        self._stopRecording()

    def onPortDataChanged(self, port):
        """
        Called when new data arrives at a port.

        :param port: the port where the new data is available.
        :return:
        """
        if self._currentFile is None:
            # recording not active -> do nothing
            return
        s = self._currentFile["streams"][port.name()]
        sample = port.getData()

        # perform timestamp calculations
        if s.shape[0] > 0:
            lastDataTimestamp = self._lastDataTimestamp
            lastRcvTimestamp = self._lastRcvTimestamp
        else:
            lastDataTimestamp = sample.getTimestamp()
            lastRcvTimestamp = 0
        if self._useRcvTimestamps:
            rcvTimestamp = np.int64(time.perf_counter_ns() - self._basetime)/1000
        else:
            rcvTimestamp = max(1, sample.getTimestamp() - lastDataTimestamp)

        self._lastDataTimestamp = np.int64(sample.getTimestamp())
        self._lastRcvTimestamp = rcvTimestamp
        # append the new data to the existing HDF5 dataset
        s.resize((s.shape[0]+1,))
        s[-1:] = (np.frombuffer(sample.getContent(), dtype=np.uint8),
                  sample.getDatatype(),
                  np.int64(sample.getTimestamp()),
                  rcvTimestamp)
        self._currentFile.flush()

        # status update once each second
        if (rcvTimestamp // 1000000) != (lastRcvTimestamp // 1000000):
            if hasattr(os, "posix_fadvise") and self.propertyCollection().getProperty("use_posix_fadvise_if_available"):
                os.posix_fadvise(self._currentFile.id.get_vfd_handle(), 0, self._currentFile.id.get_filesize(),
                                 os.POSIX_FADV_DONTNEED)
            self.statusUpdate.emit(self._name, rcvTimestamp*1e-6, self._currentFile.id.get_filesize())

class Hdf5File(GenericReaderFile):
    """
    Adaptation of hdf5 file format
    """
    def __init__(self, filename):
        self._file = h5py.File(filename, "r")

    def close(self):
        """
        Closes the file.

        :return:
        """
        self._file.close()

    def getNumberOfSamples(self, stream):
        """
        Returns the number of samples in the given stream

        :param stream: the name of the stream as a string
        :return: the number of samples in the stream
        """
        return len(self._file["streams"][stream])

    def getTimestampResolution(self):
        """
        Returns the resolution of the timestamps in ticks per second.

        :return: ticks per second as an integer
        """
        return 1000000

    def allStreams(self):
        """
        Returns the streams in this file.

        :return: a list of strings
        """
        return list(self._file["streams"].keys())

    def readSample(self, stream, streamIdx):
        """
        Returns the referenced sample as a tuple (content, dataType, dataTimestamp, rcvTimestamp).

        :param stream: the stream
        :param idx: the index of the sample in the stream
        :return: (content: QByteArray, dataType: str, dataTimestamp: int, receiveTimestamp: int)
        """
        content, dataType, dataTimestamp, receiveTimestamp = self._file["streams"][stream][streamIdx]
        if isinstance(dataType, bytes):
            # this is happening now with h5py >= 3.x
            dataType = dataType.decode()
        return content.tobytes(), dataType, dataTimestamp, receiveTimestamp

    def getRcvTimestamp(self, stream, streamIdx):
        """
        Returns the recevie timestamp of the given (stream, streamIdx) sample. The default implementation uses
        readSample(...). It may be replaced by a more efficient implementation.

        :param stream: the name of the stream as a string
        :param streamIdx: the stream index as an integer
        :return: the timestamp as an integer (see also getTimestampResolution)
        """
        return self._file["streams"][stream][streamIdx]["rcvTimestamp"]

class Hdf5Reader(GenericReader):
    """
    Reader for the nexxT default file format based on hdf5.
    """

    def getNameFilter(self):
        """
        Returns the name filter associated with the input files.

        :return: a list of strings, e.g. ["*.h5", "*.hdf5"]
        """
        return ["*.h5", "*.hdf5", "*.hdf"]

    def openFile(self, filename):
        """
        Opens the given file and return an instance of GenericReaderFile.

        :return: an instance of GenericReaderFile
        """
        return Hdf5File(filename)
