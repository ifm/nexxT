# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the profiling service for nexxT, responsible for generating profiling measurements.
"""

import logging
import time
from threading import Lock
import numpy as np
from PySide2.QtCore import QObject, Signal, Slot, QThread, QTimer, Qt, QByteArray, QCoreApplication
from nexxT.core.Utils import MethodInvoker

logger = logging.getLogger(__name__)

TIMER = time.perf_counter_ns

class PortProfiling:
    """
    Simple helper class for storing profiling time points of a single port.
    """
    def __init__(self):
        self.spans = []
        self.currentItem = None

    def start(self, timeNs):
        """
        Called when the corresponding item is started.

        :param timeNs: the time point, given in nanoseconds.
        :return:
        """
        self.currentItem = [timeNs]

    def pause(self, timeNs):
        """
        Called when the corresponding item is paused (another item may be started).

        :param timeNs: the time point, given in nanoseconds.
        :return:
        """
        self.currentItem.append(timeNs)

    def unpause(self, timeNs):
        """
        Called when the corresponding item is unpaused.

        :param timeNs: the time point, given in nanoseconds.
        :return:
        """
        self.currentItem.append(timeNs)

    def stop(self, timeNs):
        """
        Called when the corresponding item is finished. The profiling information will be added to the history.

        :param timeNs: the time point, given in nanoseconds.
        :return:
        """
        self.currentItem.append(timeNs)
        ci = self.currentItem
        self.spans.append((ci[0], ci[-1]))
        for i in range(0, len(ci), 2):
            self.spans.append((ci[i], ci[i+1]))
        self.currentItem = None

    def getSpans(self):
        """
        Returns the profiling time points in a list.

        :return: list of tuples containing nanosecond time points.
        """
        res = self.spans
        self.spans = []
        return res

class ThreadSpecificProfItem:
    """
    This class contains all profiling items of a specific thread.
    """
    THREAD_PROFILING_PERIOD_SEC = 0.3
    THREAD_PROFILING_TOTAL_TIME = 60

    def __init__(self):
        self._lastThreadTime = time.thread_time_ns()
        self._lastMonotonicTime = TIMER()
        self._portProfiling = {}
        self._portStack = []
        self._measurements = []

    def update(self):
        """
        Updates the load profiling.

        :return:
        """
        thread_time = time.thread_time_ns()
        monotonic_time = TIMER()
        if monotonic_time == self._lastMonotonicTime:
            return
        load = (thread_time - self._lastThreadTime) / (monotonic_time - self._lastMonotonicTime)
        self._lastThreadTime = thread_time
        self._lastMonotonicTime = monotonic_time
        self._measurements.append((monotonic_time, load))

    def getLoad(self):
        """
        Returns the load measurements.

        :return: list of 2-tuples (time_nano_seconds, load_ratio)
        """
        res = self._measurements
        self._measurements = []
        return res

    def getSpans(self):
        """
        Get the current port profiling data.

        :return: dict mapping thread names to lists of tuples with nano-second time points.
        """
        res = {}
        for p, pp in self._portProfiling.items():
            res[p] = pp.getSpans()
        return res

    def registerPortChangeStarted(self, portname, timeNs):
        """
        Called when starting the onPortDataChanged function.

        :param portname: the full-qualified port name
        :param timeNs: the time in nano-seconds
        :return:
        """
        if len(self._portStack) > 0:
            self._portProfiling[self._portStack[-1]].pause(timeNs)
        self._portStack.append(portname)
        if not portname in self._portProfiling:
            self._portProfiling[portname] = PortProfiling()
        self._portProfiling[portname].start(timeNs)

    def registerPortChangeFinished(self, portname, timeNs):
        """
        Called when the onPortDataChanged function has finished.

        :param portname: the full-qualified port name
        :param timeNs: the time in nano-seconds
        :return:
        """
        if len(self._portStack) == 0 or self._portStack[-1] != portname:
            return # canceled during profiling
        self._portStack = self._portStack[:-1]
        self._portProfiling[portname].stop(timeNs)
        if len(self._portStack) > 0:
            self._portProfiling[self._portStack[-1]].unpause(timeNs)

    def cancel(self):
        """
        Cancel profiling on user-request and reset the corresponding data.

        :return:
        """
        self._portProfiling = {}
        self._portStack = []

class ProfilingService(QObject):
    """
    This class provides a profiling service for the nexxT framework.
    """

    # this signal is emitted when there is new load data for a thread.
    loadDataUpdated = Signal(str, QByteArray, QByteArray)
    spanDataUpdated = Signal(str, str, QByteArray)
    threadDeregistered = Signal(str)
    stopTimers = Signal()
    startTimers = Signal()

    def __init__(self):
        super().__init__()
        self._threadSpecificProfiling = {}
        self._lockThreadSpecific = Lock()
        self._lastEmitTime = TIMER()
        self._loadMonitoringEnabled = True
        self._portProfilingEnabled = False
        self._mi = None

    @Slot()
    def registerThread(self):
        """
        This slot shall be called from each activated nexxT thread with a direct connection.

        :return:
        """
        t = QThread.currentThread()
        logger.internal("registering thread %s", t.objectName())
        with self._lockThreadSpecific:
            if not t in self._threadSpecificProfiling:
                self._threadSpecificProfiling[t] = ThreadSpecificProfItem()
                self._threadSpecificProfiling[t].timer = QTimer(parent=self.sender())
                self._threadSpecificProfiling[t].timer.timeout.connect(self._generateRecord, Qt.DirectConnection)
                self._threadSpecificProfiling[t].timer.setInterval(
                    int(ThreadSpecificProfItem.THREAD_PROFILING_PERIOD_SEC*1e3))
                self.stopTimers.connect(self._threadSpecificProfiling[t].timer.stop)
                self.startTimers.connect(self._threadSpecificProfiling[t].timer.start)
                if self._loadMonitoringEnabled:
                    self._threadSpecificProfiling[t].timer.start()

            tmain = QCoreApplication.instance().thread()
            if self._mi is None and not tmain in self._threadSpecificProfiling:
                self._mi = MethodInvoker(dict(object=self, method="registerThread", thread=tmain),
                                         Qt.QueuedConnection)

    def setLoadMonitorEnabled(self, enabled):
        """
        Enables / disables load monitoring

        :param enabled: boolean
        :return:
        """
        if enabled != self._loadMonitoringEnabled:
            self._loadMonitoringEnabled = enabled
            if enabled:
                self.startTimers.emit()
            else:
                self.stopTimers.emit()
        if self._portProfilingEnabled and not self._loadMonitoringEnabled:
            logger.warning("Port profiling works only if load monitoring is enabled.")

    def setPortProfilingEnabled(self, enabled):
        """
        Enables / disables port profiling

        :param enabled: boolean
        :return:
        """
        if enabled != self._portProfilingEnabled:
            self._portProfilingEnabled = enabled
        if self._portProfilingEnabled and not self._loadMonitoringEnabled:
            logger.warning("Port profiling works only if load monitoring is enabled.")

    @Slot()
    def deregisterThread(self):
        """
        This slot shall be called from each deactivated nexxT thread with a direct connection

        :return:
        """
        self._mi = None
        t = QThread.currentThread()
        logger.debug("deregistering thread %s", t.objectName())
        with self._lockThreadSpecific:
            if t in self._threadSpecificProfiling:
                self._threadSpecificProfiling[t].timer.stop()
                del self._threadSpecificProfiling[t]
        self.threadDeregistered.emit(t.objectName())

    @Slot()
    def _generateRecord(self):
        """
        This slot is automaticall called periodically

        :return:
        """
        t = QThread.currentThread()
        with self._lockThreadSpecific:
            self._threadSpecificProfiling[t].update()
            self._emitData()

    @Slot(str)
    def beforePortDataChanged(self, portname):
        """
        This slot is called before calling onPortDataChanged.

        :param portname: the fully qualified name of the port
        :param timeNs: the timestamp
        :return:
        """
        if not self._portProfilingEnabled:
            return
        t = QThread.currentThread()
        timeNs = time.perf_counter_ns()
        with self._lockThreadSpecific:
            if t in self._threadSpecificProfiling:
                self._threadSpecificProfiling[t].registerPortChangeStarted(portname, timeNs)

    @Slot(str)
    def afterPortDataChanged(self, portname):
        """
        This slot is called after calling onPortDataChanged.

        :param portname: the fully qualified name of the port
        :param timeNs: the timestamp
        :return:
        """
        if not self._portProfilingEnabled:
            return
        t = QThread.currentThread()
        timeNs = time.perf_counter_ns()
        with self._lockThreadSpecific:
            if t in self._threadSpecificProfiling:
                self._threadSpecificProfiling[t].registerPortChangeFinished(portname, timeNs)

    def _emitData(self):
        t = TIMER()
        if t - self._lastEmitTime > 1e8:
            # emit each 100 ms
            self._lastEmitTime = t
            for t in self._threadSpecificProfiling:
                load = self._threadSpecificProfiling[t].getLoad()
                atimstamps = np.array([l[0] for l in load], dtype=np.int64)
                aload = np.array([l[1] for l in load], dtype=np.float32)
                if aload.size > 0:
                    self.loadDataUpdated.emit(t.objectName(), QByteArray(atimstamps.tobytes()),
                                              QByteArray(aload.tobytes()))
                port_spans = self._threadSpecificProfiling[t].getSpans()
                for port, spans in port_spans.items():
                    spans = np.array(spans, dtype=np.int64)
                    if spans.size > 0:
                        self.spanDataUpdated.emit(t.objectName(), port, QByteArray(spans.tobytes()))
