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
import nexxT

logger = logging.getLogger(__name__)

if False and nexxT.useCImpl:
    class ProfilingService(nexxT.cnexxT.nexxT.SrvProfiling):
        """
        For the c++ service, we only need to overwrite the thread_time in python.
        """
        def thread_time(self):
            """
            Returns the thread specific time as int64
            :return:
            """
            return time.thread_time()

else:

    class PortProfiling:
        def __init__(self):
            self.spans = []
            self.currentItem = None

        def start(self, time_ns):
            self.currentItem = [time_ns]

        def pause(self, time_ns):
            self.currentItem.append(time_ns)

        def unpause(self, time_ns):
            self.currentItem.append(time_ns)

        def stop(self, time_ns):
            self.currentItem.append(time_ns)
            ci = self.currentItem
            self.spans.append( (ci[0], ci[-1]) )
            for i in range(0, len(ci), 2):
                self.spans.append( (ci[i], ci[i+1]) )
            self.currentItem = None

        def get_spans(self):
            res = self.spans
            self.spans = []
            return res

    class ThreadSpecificProfItem:
        """
        This class contains all profiling items of a specific thread.
        """
        THREAD_PROFILING_PERIOD_SEC = 0.2
        THREAD_PROFILING_TOTAL_TIME = 60

        def __init__(self):
            self._last_thread_time = time.thread_time_ns()
            self._last_monotonic_time = time.monotonic_ns()
            self._first_monotonic_time = time.monotonic_ns()
            self._portProfiling = {}
            self._portStack = []
            self._measurements = []

        def update(self):
            thread_time = time.thread_time_ns()
            monotonic_time = time.monotonic_ns()
            load = (thread_time - self._last_thread_time) / (monotonic_time - self._last_monotonic_time)
            self._last_thread_time = thread_time
            self._last_monotonic_time = monotonic_time
            self._measurements.append( (1e-9*(monotonic_time - self._first_monotonic_time), load) )

        def get_load(self):
            res = self._measurements
            self._measurements = []
            return res

        def get_spans(self):
            res = {}
            for p,pp in self._portProfiling.items():
                res[p] = pp.get_spans()
            return res

        def registerPortChangeStarted(self, portname, time_ns):
            if len(self._portStack) > 0:
                self._portProfiling[self._portStack[-1]].pause(time_ns)
            self._portStack.append(portname)
            if not portname in self._portProfiling:
                self._portProfiling[portname] = PortProfiling()
            self._portProfiling[portname].start(time_ns)

        def registerPortChangeFinished(self, portname, time_ns):
            if self._portStack[-1] != portname:
                return # canceled during profiling
            self._portStack = self._portStack[:-1]
            self._portProfiling[portname].stop(time_ns)
            if len(self._portStack) > 0:
                self._portProfiling[self._portStack[-1]].unpause(time_ns)

        def cancel(self):
            self._portProfiling = {}
            self._portStack = []

    class ProfilingService(QObject):
        """
        This class provides a profiling service for the nexxT framework.
        """

        # this signal is emitted when there is new load data for a thread.
        loadDataUpdated = Signal(str, QByteArray)
        spanDataUpdated = Signal(str, str, QByteArray)
        threadDeregistered = Signal(str)
        stopTimers = Signal()
        startTimers = Signal()

        def __init__(self):
            super().__init__()
            self._thread_specific_profiling = {}
            self._lock_thread_specific = Lock()
            self._last_emit_time = time.monotonic_ns()
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
            with self._lock_thread_specific:
                if not t in self._thread_specific_profiling:
                    self._thread_specific_profiling[t] = ThreadSpecificProfItem()
                    self._thread_specific_profiling[t].timer = QTimer(parent=self.sender())
                    self._thread_specific_profiling[t].timer.timeout.connect(self._generateRecord, Qt.DirectConnection)
                    self._thread_specific_profiling[t].timer.setInterval(ThreadSpecificProfItem.THREAD_PROFILING_PERIOD_SEC*1e3)
                    self.stopTimers.connect(self._thread_specific_profiling[t].timer.stop)
                    self.startTimers.connect(self._thread_specific_profiling[t].timer.start)
                    if self._loadMonitoringEnabled:
                        self._thread_specific_profiling[t].timer.start()

                tmain = QCoreApplication.instance().thread()
                if self._mi is None and not tmain in self._thread_specific_profiling:
                    self._mi = MethodInvoker(dict(object=self, method="registerThread", thread=tmain), Qt.QueuedConnection)

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
            logger.info("deregistering thread %s", t.objectName())
            with self._lock_thread_specific:
                if t in self._thread_specific_profiling:
                    self._thread_specific_profiling[t].timer.stop()
                    del self._thread_specific_profiling[t]
            self.threadDeregistered.emit(t.objectName())

        @Slot()
        def _generateRecord(self):
            """
            This slot is automaticall called periodically
            :return:
            """
            t = QThread.currentThread()
            with self._lock_thread_specific:
                self._thread_specific_profiling[t].update()
                self._emit_data()

        @Slot(str)
        def beforePortDataChanged(self, portname):
            """
            This slot is called before calling onPortDataChanged.
            :param portname: the fully qualified name of the port
            :param time_ns: the timestamp
            :return:
            """
            if not self._portProfilingEnabled:
                return
            t = QThread.currentThread()
            time_ns = time.perf_counter_ns()
            with self._lock_thread_specific:
                self._thread_specific_profiling[t].registerPortChangeStarted(portname, time_ns)

        @Slot(str)
        def afterPortDataChanged(self, portname):
            """
            This slot is called after calling onPortDataChanged.
            :param portname: the fully qualified name of the port
            :param time_ns: the timestamp
            :return:
            """
            if not self._portProfilingEnabled:
                return
            t = QThread.currentThread()
            time_ns = time.perf_counter_ns()
            with self._lock_thread_specific:
                self._thread_specific_profiling[t].registerPortChangeFinished(portname, time_ns)

        def _emit_data(self):
            t = time.monotonic_ns()
            if t - self._last_emit_time > 1e8:
                # emit each 100 ms
                self._last_emit_time = t
                for t in self._thread_specific_profiling:
                    load = np.array(self._thread_specific_profiling[t].get_load(), dtype=np.float32)
                    if load.size > 0:
                        self.loadDataUpdated.emit(t.objectName(), QByteArray(load.tobytes()))
                    port_spans = self._thread_specific_profiling[t].get_spans()
                    for port,spans in port_spans.items():
                        spans = np.array(spans, dtype=np.int64)
                        if spans.size > 0:
                            self.spanDataUpdated.emit(t.objectName(), port, QByteArray(spans.tobytes()))
