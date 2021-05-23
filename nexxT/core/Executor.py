# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the class Executor
"""

import logging
from PySide2.QtCore import QObject, Signal, QThread, Qt, QMutex, QTimer
import nexxT
from nexxT.core.Utils import handleException

logger = logging.getLogger(__name__)

if nexxT.useCImpl:

    import cnexxT

    def Executor(*args): # pylint: disable=invalid-name
        """
        This is a factory function for the C version of the Executor class
        """
        res = cnexxT.nexxT.Executor.make_shared(cnexxT.nexxT.Executor(*args))
        return res

else:

    class Executor(QObject):
        """
        Each nexxT thread has an executor for executing tasks (i.e. notifying filters about changes in the ports).
        """

        notify = Signal()
        MAX_LOOPS_FINALIZE = 5

        def __init__(self, qthread):
            """
            Construtor

            :param qthread: the QThread instance this object shall be moved to
            """
            super().__init__()
            self._pendingReceivesMutex = QMutex()
            self._pendingReceives = []
            self._blockedFilters = set()
            self._stopped = False
            self.moveToThread(qthread)
            self.notify.connect(self.notifyInThread, Qt.QueuedConnection)

        def registerPendingRcvSync(self, inputPort, dataSample):
            """
            Register a pending synchronous (i.e. originated from the same thread) receive event.

            :param inputPort: The InputPort instance which shall be notified
            :param dataSample: The DataSample instance to be delivered
            """
            self._registerPendingRcvSync(inputPort, dataSample)

        @handleException
        def _registerPendingRcvSync(self, inputPort, dataSample):
            if not self._stopped:
                self._pendingReceivesMutex.lock()
                self._pendingReceives.append((inputPort, dataSample, None))
                self._pendingReceivesMutex.unlock()
                QTimer.singleShot(0, self.step)

        def registerPendingRcvAsync(self, inputPort, dataSample, semaphore):
            """
            Register a pending asynchronous (i.e. originated from another thread through a PortToPortConnection
            instacne) receive event.

            :param inputPort: The InputPort instance which shall be notified
            :param dataSample: The DataSample instance to be delivered
            :param semaphore: The QSemaphore instance of the corresponding InterThreadConnection instance
            """
            self._registerPendingRcvAsync(inputPort, dataSample, semaphore)

        @handleException
        def _registerPendingRcvAsync(self, inputPort, dataSample, semaphore):
            assert inputPort.thread() == self.thread()
            if not self._stopped:
                self._pendingReceivesMutex.lock()
                self._pendingReceives.append((inputPort, dataSample, semaphore))
                self._pendingReceivesMutex.unlock()
                self.notify.emit()

        def notifyInThread(self):
            """
            Slot called during _registerPendingRcvAsync, starts a single shot timer for the step function.
            """
            self._notifyInThread()

        @handleException
        def _notifyInThread(self):
            QTimer.singleShot(0, self.step)

        def step(self, fromFilter=None):
            """
            This function process one of the pending events.

            :param fromFilter: An optional filter instance which will be blocked for further processing until the
                function returns
            :return: True if an event was processed, False otherwise.
            """
            return self._step(fromFilter)

        @handleException
        def _step(self, fromFilter):
            assert QThread.currentThread() == self.thread()
            res = False
            if fromFilter is not None:
                self._blockedFilters.add(fromFilter)
            try:
                if not self._stopped:
                    self._pendingReceivesMutex.lock()
                    for idx, (inputPort, dataSample, semaphore) in enumerate(self._pendingReceives):
                        if inputPort.environment().getPlugin() not in self._blockedFilters:
                            self._pendingReceives.pop(idx)
                            self._pendingReceivesMutex.unlock()
                            res = True
                            if semaphore is None:
                                inputPort.receiveSync(dataSample)
                            else:
                                inputPort.receiveAsync(dataSample, semaphore)
                            # only process one sample
                            break
            finally:
                if not res:
                    self._pendingReceivesMutex.unlock()
                if fromFilter is not None:
                    self._blockedFilters.remove(fromFilter)
            return res

        def finalize(self):
            """
            This function processes the queue before the thread is stopped. In case of infinite recursions, an early
            stop criterion is applied.
            """
            logger.internal("starting finalize (%s)", self.thread())
            numCalled = {}
            changed = True
            while changed:
                changed = False
                self._pendingReceivesMutex.lock()
                for idx, (inputPort, dataSample, semaphore) in enumerate(self._pendingReceives):
                    if (inputPort.environment().getPlugin() not in self._blockedFilters and
                            numCalled.get(inputPort, 0) < self.MAX_LOOPS_FINALIZE):
                        self._pendingReceives.pop(idx)
                        self._pendingReceivesMutex.unlock()
                        numCalled[inputPort] = numCalled.get(inputPort, 0) + 1
                        changed = True
                        if semaphore is None:
                            inputPort.receiveSync(dataSample)
                        else:
                            inputPort.receiveAsync(dataSample, semaphore)
                        self._pendingReceivesMutex.lock()
                        # only one sample, note that _pendingReceives is changed inside the loop!
                        break
                self._pendingReceivesMutex.unlock()

        def clear(self):
            """
            Called after processing is stopped.
            """
            self._stopped = True
            self._pendingReceives = []
            self._blockedFilters = []
