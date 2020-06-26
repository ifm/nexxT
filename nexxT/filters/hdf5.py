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
import numpy as np
import h5py
from PySide2.QtCore import Signal
from nexxT.interface import Filter, Services
from nexxT.core.Utils import handleException

class Hdf5Writer(Filter):
    """
    Generic nexxT filter for writing HDF5 files.
    """
    statusUpdate = Signal(str, float, int)

    def __init__(self, env):
        super().__init__(True, False, env)
        self._currentFile = None
        self.propertyCollection().defineProperty(
            "filename",
            "${DATE}_${TIME}_${FILTER_NAME}.h5",
            "Template for generated files. The following variables can be used: ${DATE}, ${TIME}, ${FILTER_NAME}")
        self.propertyCollection().defineProperty(
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
        # create a numpy-style dtype for the contents of a datasample
        type_content = h5py.vlen_dtype(np.dtype(np.uint8))
        type_timestamp = np.int64
        type_dataType = h5py.string_dtype()
        self.dtype = [('content', type_content),
                      ('dataType', type_dataType),
                      ('dataTimestamp', type_timestamp),
                      ('rcvTimestamp', type_timestamp),
                      ]


    def onStart(self):
        """
        Registers itself to the recording control service
        :return:
        """
        srv = Services.getService("RecordingControl")
        srv.setupConnections(self)

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
        self._use_rcv_timestamps = self.propertyCollection().getProperty("use_receive_timestamps")
        # interpolate the name with optionally given variables
        dt = datetime.datetime.now()
        vars = dict(DATE=dt.date().strftime('%Y-%m-%d'),
                    TIME=dt.time().strftime('%H-%M-%S'),
                    FILTER_NAME=self.propertyCollection().objectName())
        self._name = string.Template(self._name).safe_substitute(vars)
        mode = "w" if self.propertyCollection().getProperty("silent_overwrite") else "x"
        # create a new HDF5 file / truncate an existing file containing a stream for all existing input ports
        self._currentFile = h5py.File(Path(directory) / self._name, mode)
        streams = self._currentFile.create_group("streams")
        for port in self.getDynamicInputPorts():
            streams.create_dataset(port.name(), (0,), chunks=(1,), maxshape=(None,), dtype=self.dtype)
        # setup variables needed during processing
        self._basetime = time.perf_counter_ns()
        self._bytesWritten = 0
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
            lastDataTimestamp = s[-1,"dataTimestamp"]
            lastRcvTimestamp = s[-1,"rcvTimestamp"]
        else:
            lastDataTimestamp = sample.getTimestamp()
            lastRcvTimestamp = 0
        if self._use_rcv_timestamps:
            rcvTimestamp = np.int64(time.perf_counter_ns() - self._basetime)/1000
        else:
            rcvTimestamp = max(1, np.int64(sample.getTimestamp()) - lastDataTimestamp)

        # append the new data to the existing HDF5 dataset
        s.resize((s.shape[0]+1,))
        s[-1:] = (np.frombuffer(sample.getContent(), dtype=np.uint8),
                  sample.getDatatype(),
                  np.int64(sample.getTimestamp()),
                  rcvTimestamp)
        self._currentFile.flush()
        # remember the number of bytes written
        self._bytesWritten += sample.getContent().size() + len(sample.getDatatype()) + 2*8

        # status update once each second
        if (rcvTimestamp // 1000000) != (lastRcvTimestamp // 1000000):
            self.statusUpdate.emit(self._name, rcvTimestamp*1e-6, self._bytesWritten)
