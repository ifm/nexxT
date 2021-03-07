# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides a generic reader which can be inherited to use new data formats inside nexxT.
"""

import time
import logging
import math
from PySide2.QtCore import Signal, QTimer
from PySide2.QtWidgets import QFileDialog
from nexxT.interface import Filter, Services, DataSample
from nexxT.core.Utils import handleException, isMainThread

logger = logging.getLogger(__name__)

class GenericReaderFile:
    """
    Interface for adaptations of new file formats.

    For supporting new file formats, inherit from this class and overwrite all of the methods listed here. The
    constructor of the inherited class usually takes a filename argument. Inherit also from GenericReader to provide
    a new Filter class and overwrite the methods getNameFilter and openFile, which returns an instance of the
    GenericReaderFile implementation.

    See :py:class:`nexxT.filters.hdf5.Hdf5File` and :py:class:`nexxT.filters.hdf5.Hdf5Reader` for an example.
    """

    # pylint: disable=no-self-use
    # this is an abstract class and the methods are provided for reference

    def close(self):
        """
        Closes the file.

        :return:
        """
        raise NotImplementedError()

    def getNumberOfSamples(self, stream):
        """
        Returns the number of samples in the given stream

        :param stream: the name of the stream as a string
        :return: the number of samples in the stream
        """
        raise NotImplementedError()

    def getTimestampResolution(self):
        """
        Returns the resolution of the timestamps in ticks per second.

        :return: ticks per second as an integer
        """
        raise NotImplementedError()

    def allStreams(self):
        """
        Returns the streams in this file.

        :return: a list of strings
        """
        raise NotImplementedError()

    def readSample(self, stream, streamIdx):
        """
        Returns the referenced sample as a tuple (content, dataType, dataTimestamp, rcvTimestamp).

        :param stream: the stream
        :param idx: the index of the sample in the stream
        :return: (content: QByteArray, dataType: str, dataTimestamp: int, receiveTimestamp: int)
        """
        raise NotImplementedError()

    def getRcvTimestamp(self, stream, streamIdx):
        """
        Returns the recevie timestamp of the given (stream, streamIdx) sample. The default implementation uses
        readSample(...). It may be replaced by a more efficient implementation.

        :param stream: the name of the stream as a string
        :param streamIdx: the stream index as an integer
        :return: the timestamp as an integer (see also getTimestampResolution)
        """
        return self.readSample(stream, streamIdx)[3]

class GenericReader(Filter):
    """
    Generic harddisk reader which can be used as base class for implementing readers for custom file formats. To create
    a new input file reader, inherit from this class and reimplement getNameFilter(...) and openFile(...). openFile(...)
    shall return an instance of an implementation of the interface GenericReaderFile.

    See :py:class:`nexxT.filters.hdf5.Hdf5Reader` for an example.
    """

    # signals for playback device
    playbackStarted = Signal()
    playbackPaused = Signal()
    sequenceOpened = Signal(str, 'qint64', 'qint64', list)
    currentTimestampChanged = Signal('qint64')
    timeRatioChanged = Signal(float)

    # methods to be overloaded

    def getNameFilter(self): # pylint: disable=no-self-use
        """
        Returns the name filter associated with the input files.

        :return: a list of strings, e.g. ["*.h5", "*.hdf5"]
        """
        raise NotImplementedError()

    def openFile(self, filename): # pylint: disable=no-self-use
        """
        Opens the given file and return an instance of GenericReaderFile.

        :return: an instance of GenericReaderFile
        """
        raise NotImplementedError()

    # slots for playback device

    def startPlayback(self):
        """
        slot called when the playback shall be started

        :return:
        """
        if not self._playing:
            self._playing = True
            self._timer.start(0)
            self._updateTimer.start()
            self.playbackStarted.emit()

    def pausePlayback(self):
        """
        slot called when the playback shall be paused

        :return:
        """
        if self._playing:
            self._playing = False
            self._untilStream = None
            self._dir = 1
            self._timer.stop()
            self._updateTimer.stop()
            self._updateCurrentTimestamp()
            self.playbackPaused.emit()

    def stepForward(self, stream):
        """
        slot called to step one frame in stream forward

        :param stream: a string instance or None (all streams are selected)
        :return:
        """
        self._untilStream = stream if stream is not None else ''
        self.startPlayback()

    def stepBackward(self, stream):
        """
        slot called to step one frame in stream backward

        :param stream: a string instance or None (all streams are selected)
        :return:
        """
        self._dir = -1
        self._untilStream = stream if stream is not None else ''
        self.startPlayback()

    def seekBeginning(self):
        """
        slot called to go to the beginning of the file

        :return:
        """
        self.pausePlayback()
        for p in self._portToIdx:
            self._portToIdx[p] = -1
        self._transmitNextSample()
        self._updateCurrentTimestamp()

    def seekEnd(self):
        """
        slot called to go to the end of the file

        :return:
        """
        self.pausePlayback()
        for p in self._portToIdx:
            self._portToIdx[p] = self._file.getNumberOfSamples(p)
        self._dir = -1
        self._transmitNextSample()
        self._dir = +1
        self._updateCurrentTimestamp()

    def seekTime(self, timestamp):
        """
        slot called to go to the specified time

        :param timestamp: a timestamp in nanosecond resolution
        :return:
        """
        t = timestamp // (1000000000//self._file.getTimestampResolution())
        nValid = 0
        for p in self._portToIdx:
            # binary search
            minIdx = -1
            num = self._file.getNumberOfSamples(p)
            maxIdx = num
            # binary search for timestamp
            while maxIdx - minIdx > 1:
                testIdx = max(0, min(num-1, (minIdx + maxIdx)//2))
                vTest = self._file.getRcvTimestamp(p, testIdx)
                if vTest <= t:
                    minIdx = testIdx
                else:
                    maxIdx = testIdx
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
        """
        slot called to set the sequence file name

        :param filename: a string instance
        :return:
        """
        logger.debug("Set sequence filename=%s", filename)
        self._name = filename

    def setTimeFactor(self, factor):
        """
        slot called to set the time factor

        :param factor: a float
        :return:
        """
        self._timeFactor = factor
        self.timeRatioChanged.emit(self._timeFactor)

    # overwrites from Filter

    def __init__(self, env):
        super().__init__(False, True, env)
        self._name = None
        self._file = None
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
        """
        overloaded from Filter

        :return:
        """
        srv = Services.getService("PlaybackControl")
        srv.setupConnections(self, self.getNameFilter())
        if isMainThread():
            logger.warning("This GenericReader seems to run in GUI thread. Consider to move it to a seperate thread.")

    def onStart(self):
        """
        overloaded from Filter

        :return:
        """
        if self._name is not None:
            self._file = self.openFile(self._name) # pylint: disable=assignment-from-no-return
            if not isinstance(self._file, GenericReaderFile):
                logger.error("Unexpected instance returned from openFile(...) method of instance %s", (repr(self)))
            # sanity checks for the timestamp resolutions
            # spit out some errors because when these checks fail, the timestamp logic doesn't work
            # note that nexxT tries to avoid applying floating point arithmetics to timestamps due to possible loss
            # of accuracy
            tsResolution = self._file.getTimestampResolution()
            f = DataSample.TIMESTAMP_RES*tsResolution
            if (f > 1 and f % 1.0 != 0.0) or (f < 1 and (1/f) % 1.0 != 0.0):
                logger.error("timestamp resolution of opened instance %s is no integer multiple of internal resolution",
                             repr(self._file))
            if (1000000000/tsResolution) % 1.0 != 0.0:
                logger.error("timestamp resolution of opened instance %s is no integer multiple of nanoseconds",
                             repr(self._file))
            self._portToIdx = {}
            self._ports = self.getDynamicOutputPorts()
            for s in self._file.allStreams():
                if s in [p.name() for p in self._ports]:
                    if self._file.getNumberOfSamples(s) > 0:
                        self._portToIdx[s] = -1
                    else:
                        logger.warning("Stream %s does not contain any samples.", s)
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
        """
        overloaded from Filter

        :return:
        """
        if self._file is not None:
            self._file.close()
            self._file = None
            self._portToIdx = None
            self._timer.stop()
            self._timer = None
            self._playing = None
            self._currentTimestamp = None

    def onClose(self):
        """
        overloaded from Filter

        :return:
        """
        srv = Services.getService("PlaybackControl")
        srv.removeConnections(self)

    def onSuggestDynamicPorts(self):
        """
        overloaded from Filter

        :return:
        """
        try:
            fn, ok = QFileDialog.getOpenFileName(caption="Choose template hdf5 file",
                                                 filter="Support files (%s)" % (" ".join(self.getNameFilter())))
            if ok:
                f = self.openFile(fn) # pylint: disable=assignment-from-no-return
                if not isinstance(f, GenericReaderFile):
                    logger.error("Unexpected instance returned from openFile(...) method of instance %s", (repr(self)))
                return [], list(f.allStreams())
        except Exception: # pylint: disable=broad-except
            logger.exception("Caught exception during onSuggestDynamicPorts")
        return [], []

    # private slots and methods

    def _timeSpan(self):
        tmin = math.inf
        tmax = -math.inf
        for p in self._portToIdx:
            t = self._file.getRcvTimestamp(p, 0)
            tmin = min(t, tmin)
            t = self._file.getRcvTimestamp(p, self._file.getNumberOfSamples(p)-1)
            tmax = max(t, tmax)
        return (tmin*(1000000000//self._file.getTimestampResolution()),
                tmax*(1000000000//self._file.getTimestampResolution()))

    def _getNextSample(self):
        # check which port has the next sample to deliver according to rcv timestamps
        nextPort = None
        for p in self._portToIdx:
            idx = self._portToIdx[p]
            idx = idx + self._dir
            if 0 <= idx < self._file.getNumberOfSamples(p):
                ts = self._file.getRcvTimestamp(p, idx)
                # pylint: disable=unsubscriptable-object
                # actually, nextPort can be either None or a 2-tuple
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
        factorTStoNS = 1e9/self._file.getTimestampResolution()
        while nextPort is not None:
            ts, pname = nextPort
            self._portToIdx[pname] += self._dir
            lastTransmit = self._transmit(pname)
            if not self._playing:
                return pname
            nextPort = self._getNextSample()
            if nextPort is not None:
                newTs, _ = nextPort
                nowTime = time.perf_counter_ns()
                deltaT_ns = max(0, (newTs - ts) * factorTStoNS / self._timeFactor - (nowTime - lastTransmit))
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
        content, dataType, dataTimestamp, rcvTimestamp = self._file.readSample(pname, idx)
        # create sample to transmit
        f = 1/(DataSample.TIMESTAMP_RES * self._file.getTimestampResolution())
        if f >= 1:
            f = round(f)
            tsData = dataTimestamp * f
        else:
            f = round(1/f)
            tsData = dataTimestamp // f
        sample = DataSample(content, dataType, tsData)
        res = time.perf_counter_ns()
        # transmit sample over corresponding port
        self._ports[[p.name() for p in self._ports].index(pname)].transmit(sample)
        self._currentTimestampChanged(rcvTimestamp*(1000000000//self._file.getTimestampResolution()))
        if self._untilStream is not None:
            if self._untilStream == pname or self._untilStream == '':
                self.pausePlayback()
        return res

    def _transmitCurrent(self):
        ports = list(self._portToIdx.keys())
        values = [self._file.getRcvTimestamp(p, self._portToIdx[p]) for p in ports]
        sortedIdx = sorted(range(len(values)), key=lambda x: values[x])
        # transmit most recent sample
        self._transmit(ports[sortedIdx[-1]])

    def _currentTimestampChanged(self, timestamp):
        self._currentTimestamp = timestamp

    def _updateCurrentTimestamp(self):
        if self._currentTimestamp is not None:
            self.currentTimestampChanged.emit(self._currentTimestamp)
