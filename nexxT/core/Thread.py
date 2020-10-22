# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the class NexTThread.
"""

import logging
import sys
import threading
from PySide2.QtCore import QObject, Signal, Slot, QCoreApplication, QThread
from nexxT.interface import FilterState, Services
from nexxT.core.Exceptions import NodeExistsError, NexTInternalError, NodeNotFoundError, NexTRuntimeError
from nexxT.core.Utils import handleException

logger = logging.getLogger(__name__)

class NexTThread(QObject):
    """
    A thread of the active application
    """

    class ThreadWithCoverage(QThread):
        """
        A thread with coverage enabled (if present)
        """

        @handleException
        def startupHook(self): # pylint: disable=no-self-use
            """
            see https://github.com/nedbat/coveragepy/issues/582
            and https://github.com/nedbat/coveragepy/issues/686
            :return:
            """
            th = threading._trace_hook # pylint: disable=protected-access
            if hasattr(sys, "settrace") and th is not None:
                logger.info("Registering startup hook for coverage")
                sys.settrace(th)
                logger.info("Startup hook registered")
            else:
                logger.debug("Skip startup hook registration (coverage not enabled).")

        def run(self):
            """
            Overwritten from QThread, registers the trace hook and proceeds with normal event-loop processing.
            :return:
            """
            self.startupHook()
            super().run()

    operationFinished = Signal() # used to synchronize threads from active application

    _operations = dict(
        init=FilterState.INITIALIZING,
        open=FilterState.OPENING,
        start=FilterState.STARTING,
        stop=FilterState.STOPPING,
        close=FilterState.CLOSING,
        deinit=FilterState.DEINITIALIZING,
    )

    def __init__(self, name):
        """
        Creates a NexTThread instance with a name. If this is not the main thread, create a corresponding
        QThread and start it (i.e., the event loop).
        :param name: name of the thread
        """
        super().__init__()
        self._filters = {}
        self._filter2name = {}
        self._mockups = {}
        self._name = name
        try:
            self._profsrv = Services.getService("Profiling")
            if hasattr(self._profsrv, "data") and self._profsrv.data() is None:
                self._profsrv = None
        except KeyError:
            self._profsrv = None
        if not self.thread() is QCoreApplication.instance().thread():
            raise NexTInternalError("unexpected thread")
        if name == "main":
            self._qthread = QCoreApplication.instance().thread()
            self._qthread.setObjectName(name)
        else:
            self._qthread = self.ThreadWithCoverage(parent=self)
            self._qthread.setObjectName(name)
            self._qthread.start()
        self.moveToThread(self._qthread)
        self.cleanUpCalled = False

    def __del__(self):
        logger.debug("destructor of Thread")
        if not self.cleanUpCalled:
            logger.warning("Thread:: calling cleanup in destructor.")
            self.cleanup()
        logger.debug("destructor of Thread done")

    def cleanup(self):
        """
        Stop threads and deallocate all resources.
        :return:
        """
        self.cleanUpCalled = True
        if self._name != "main" and self._qthread is not None:
            logger.internal("stopping thread %s", self._name)
            self._qthread.quit()
            self._qthread.wait()
            self._qthread = None
        logger.internal("cleanup filters")
        for name in self._filters:
            self._filters[name].destroy()
        self._filters.clear()
        self._filter2name.clear()
        logger.internal("cleanup mockups")
        # Note: the mockups are in ownership of the corresponding graph, we don't delete them
        self._mockups.clear()
        logger.internal("Thread cleanup done")

    def addMockup(self, name, mockup):
        """
        Add a FilterMockup instance by name.
        :param name: name of the filter
        :param mockup: the corresponding FilterMockup instance
        :return:
        """
        if name in self._mockups:
            raise NodeExistsError(name)
        self._mockups[name] = mockup

    def getFilter(self, name):
        """
        Return a filter by name.
        :param name: the filter name
        :return: A nexxT Filter instance
        """
        if not name in self._filters:
            raise NodeNotFoundError(name)
        return self._filters[name]

    def getName(self, filterEnvironment):
        """
        Return the path to the filter environment
        :param filterEnvironment: a FilterEnvironment instance
        :return: [Application instance] + [CompositeFilter instance]*
        """
        if not filterEnvironment in self._filter2name:
            raise NexTRuntimeError("Filterenvironment not found. Not active?")
        return self._filter2name[filterEnvironment]

    def qthread(self):
        """
        Return the corresponding qthread.
        :return: a QThread instance
        """
        return self._qthread

    @Slot(str, object)
    def performOperation(self, operation, barrier):
        """
        Perform the given operation on all filters.
        :param operation: one of "create", "destruct", "init", "open", "start", "stop", "close", "deinit"
        :param barrier: a barrier object to synchronize threads
        :return: None
        """
        # wait that all threads are in their event loop.
        barrier.wait()
        if operation in self._operations:
            # pre-adaptation of states (e.g. from CONSTRUCTED to INITIALIZING)
            # before one of the actual operations is called, all filters are in the adapted state
            for name in self._mockups:
                self._filters[name].preStateTransition(self._operations[operation])
            # wait for all threads
            barrier.wait()
        # perform operation for all filters
        for name in self._mockups:
            try:
                if operation == "create":
                    res = self._mockups[name].createFilter()
                    res.setParent(self)
                    self._filters[name] = res
                    self._filter2name[res] = name
                    logger.internal("Created filter %s in thread %s", name, self._name)
                elif operation == "destruct":
                    self._filters[name].destroy()
                    logging.getLogger(__name__).internal("deleting filter...")
                    del self._filters[name]
                    logging.getLogger(__name__).internal("filter deleted")
                else:
                    op = getattr(self._filters[name], operation)
                    op()
                if operation == "start":
                    if self._profsrv is not None:
                        self._profsrv.registerThread()
                elif operation == "stop":
                    if self._profsrv is not None:
                        self._profsrv.deregisterThread()
            except Exception: # pylint: disable=broad-except
                # catching a general exception is exactly what is wanted here
                logging.getLogger(__name__).exception("Exception while performing operation '%s' on %s",
                                                      operation, name)
        # notify ActiveApplication
        logging.getLogger(__name__).internal("emitting finished")
        self.operationFinished.emit()
        # and wait for all other threads to complete
        logging.getLogger(__name__).internal("waiting for barrier")
        barrier.wait()
        logging.getLogger(__name__).internal("performOperation done")
