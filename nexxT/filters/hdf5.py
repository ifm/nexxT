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
import numpy as np
import h5py
from PySide2.QtCore import Signal, QDateTime, QTimer
from nexxT.interface import Filter, Services, DataSample
from nexxT.core.Utils import handleException, isMainThread

logger = logging.getLogger(__name__)

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
        if isMainThread():
            logger.warning("Hdf5Writer seems to run in GUI thread. Consider to move it to a seperate thread.")

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
        if not (self._name.endswith(".h5") or self._name.endswith(".hdf5") or self._name.endswith(".hdf")):
            self._name += ".h5"
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
            rcvTimestamp = max(1, sample.getTimestamp() - lastDataTimestamp)

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

class Hdf5Reader(Filter):
    """
    Generic nexxT filter for reading HDF5 files created by Hdf5Writer
    """

    # signals for playback device
    playbackStarted = Signal()
    playbackPaused = Signal()
    sequenceOpened = Signal(str, QDateTime, QDateTime, list)
    currentTimestampChanged = Signal(QDateTime)
    timeRatioChanged = Signal(float)

    # slots for playback device

    def startPlayback(self):
        if not self._playing:
            self._playing = True
            self._timer.start(0)
            self._updateTimer.start()
            self.playbackStarted.emit()

    def pausePlayback(self):
        if self._playing:
            self._playing = False
            self._untilStream = None
            self._dir = 1
            self._timer.stop()
            self._updateTimer.stop()
            self._updateCurrentTimestamp()
            self.playbackPaused.emit()

    def stepForward(self, stream):
        self._untilStream = stream if stream is not None else ''
        self.startPlayback()

    def stepBackward(self, stream):
        self._dir = -1
        self._untilStream = stream if stream is not None else ''
        self.startPlayback()

    def seekBeginning(self):
        self.pausePlayback()
        for p in self._portToIdx:
            self._portToIdx[p] = -1
        self._transmitNextSample()
        self._updateCurrentTimestamp()

    def seekEnd(self):
        self.pausePlayback()
        for p in self._portToIdx:
            self._portToIdx[p] = len(self._currentFile["streams"][p])
        self._dir = -1
        self._transmitNextSample()
        self._dir = +1
        self._updateCurrentTimestamp()

    def seekTime(self, dt):
        t = dt.toMSecsSinceEpoch()*1000
        nValid = 0
        for p in self._portToIdx:
            s = self._currentFile["streams"][p]
            # binary search
            minIdx = -1
            vMin = -np.inf
            num = len(self._currentFile["streams"][p])
            maxIdx = num
            vMax = np.inf
            while maxIdx - minIdx > 1:
                testIdx = max(0, min(num-1, (minIdx + maxIdx)//2))
                vTest = s[testIdx,"rcvTimestamp"]
                if vTest <= t:
                    minIdx = testIdx
                    vMin = vTest
                else:
                    maxIdx = testIdx
                    vMax = vTest
            self._portToIdx[p] = minIdx
            if minIdx >= 0:
                # note: minIdx is always below num
                nValid += 1
        if nValid > 0:
            self._transmitCurrent()
        else:
            self._transmitNextSample()
        self._updateCurrentTimestamp()

    def setSequence(self, filename):
        self._name = filename

    def setTimeFactor(self, factor):
        self._timeFactor = factor
        self.timeRatioChanged.emit(self._timeFactor)

    # overwrites from Filter

    def __init__(self, env):
        super().__init__(False, True, env)
        self._name = None
        self._currentFile = None
        self._portToIdx = None
        self._timer = None
        self._updateTimer = QTimer(self)
        self._updateTimer.setInterval(1000) # update new position each second
        self._updateTimer.timeout.connect(self._updateCurrentTimestamp)
        self._currentTimestamp = None
        self._playing = None
        self._untilStream = None
        self._dir = 1
        self._ports = None
        self._timeFactor = 1

    def onOpen(self):
        srv = Services.getService("PlaybackControl")
        srv.setupConnections(self, ["*.h5", "*.hdf5", "*.hdf"])
        if isMainThread():
            logger.warning("Hdf5Reader seems to run in GUI thread. Consider to move it to a seperate thread.")

    def onStart(self):
        if self._name is not None:
            self._currentFile = h5py.File(self._name, "r")
            self._portToIdx = {}
            self._ports = self.getDynamicOutputPorts()
            for s in self._currentFile["streams"]:
                if s in [p.name() for p in self._ports]:
                    self._portToIdx[s] = -1
                else:
                    logger.warning("No matching output port for stream %s. Consider to create a port for it.", s)
            for p in self._ports:
                if not p.name() in self._portToIdx:
                    logger.warning("No matching stream for output port %s. HDF5 file not matching the configuration?",
                                   p.name())
            self._timer = QTimer(parent=self)
            self._timer.timeout.connect(self._transmitNextSample)
            self._playing = False
            self._currentTimestamp = None
            span = self._timeSpan()
            self.sequenceOpened.emit(self._name, span[0], span[1], sorted(self._portToIdx.keys()))
            self.timeRatioChanged.emit(self._timeFactor)
            self.playbackPaused.emit()

    def onStop(self):
        if self._currentFile is not None:
            self._currentFile.close()
            self._currentFile = None
            self._portToIdx = None
            self._timer.stop()
            self._timer = None
            self._playing = None
            self._currentTimestamp = None

    def onClose(self):
        srv = Services.getService("PlaybackControl")
        srv.removeConnections(self)

    # private slots and methods

    def _timeSpan(self):
        tmin = np.inf
        tmax = -np.inf
        for p in self._portToIdx:
            t = self._currentFile["streams"][p][0, "rcvTimestamp"]
            tmin = min(t, tmin)
            t = self._currentFile["streams"][p][-1, "rcvTimestamp"]
            tmax = max(t, tmax)
        return QDateTime.fromMSecsSinceEpoch(tmin//1000), QDateTime.fromMSecsSinceEpoch(tmax//1000)

    def _getNextSample(self):
        # check which port has the next sample to deliver according to rcv timestamps
        nextPort = None
        for p in self._portToIdx:
            idx = self._portToIdx[p]
            idx = idx + self._dir
            if idx >= 0 and idx < len(self._currentFile["streams"][p]):
                ts = self._currentFile["streams"][p][idx,"rcvTimestamp"]
                if nextPort is None or (ts < nextPort[0] and self._dir > 0) or (ts > nextPort[0] and self._dir < 0):
                    nextPort = (ts, p)
        return nextPort

    @handleException
    def _transmitNextSample(self):
        startTime = time.perf_counter_ns()
        nextPort = self._getNextSample()
        # when next data sample arrives sooner than this threshold, do not use the QTimer but perform busy waiting
        noSleepThreshold_ns = 0.005*1e9 # 5 ms
        # maximum time in busy-wait strategy (measured from the beginning of the function)
        maxTimeInMethod = 0.05*1e9 # yield all 50 ms
        while nextPort is not None:
            ts,pname = nextPort
            self._portToIdx[pname] += self._dir
            lastTransmit = self._transmit(pname)
            if not self._playing:
                return pname
            nextPort = self._getNextSample()
            if nextPort is not None:
                newTs,p = nextPort
                nowTime = time.perf_counter_ns()
                deltaT_ns = max(0, (newTs - ts) * 1000 / self._timeFactor - (nowTime - lastTransmit))
                if deltaT_ns < noSleepThreshold_ns and nowTime - startTime + deltaT_ns < maxTimeInMethod:
                    while time.perf_counter_ns() - nowTime < deltaT_ns:
                        pass
                else:
                    self._timer.start(deltaT_ns//1000000)
                    break
            else:
                self.pausePlayback()

    def _transmit(self, pname):
        idx = self._portToIdx[pname]
        # read data sample from HDF5 file
        content, dataType, dataTimestamp, rcvTimestamp = self._currentFile["streams"][pname][idx]
        # create sample to transmit
        sample = DataSample(content.tobytes(), dataType, dataTimestamp)
        res = time.perf_counter_ns()
        # transmit sample over corresponding port
        self._ports[[p.name() for p in self._ports].index(pname)].transmit(sample)
        self._currentTimestampChanged(QDateTime.fromMSecsSinceEpoch(rcvTimestamp//1000))
        if self._untilStream is not None:
            if self._untilStream == pname or self._untilStream == '':
                self.pausePlayback()
        return res

    def _transmitCurrent(self):
        ports = list(self._portToIdx.keys())
        values = [self._currentFile["streams"][p][self._portToIdx[p],"rcvTimestamp"] for p in ports]
        sortedIdx = sorted(range(len(values)), key=lambda x: values[x])
        # transmit most recent sample
        self._transmit(ports[sortedIdx[-1]])

    def _currentTimestampChanged(self, t):
        self._currentTimestamp = t

    def _updateCurrentTimestamp(self):
        if self._currentTimestamp is not None:
            self.currentTimestampChanged.emit(self._currentTimestamp)