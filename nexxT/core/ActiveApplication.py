# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module contains the class definition of ActiveApplication
"""

import logging
from PySide2.QtCore import QObject, Slot, Signal, Qt, QCoreApplication
from nexxT.interface import FilterState, OutputPortInterface, InputPortInterface
from nexxT.core.Exceptions import FilterStateMachineError, NexTInternalError
from nexxT.core.CompositeFilter import CompositeFilter
from nexxT.core.Utils import Barrier, assertMainThread
from nexxT.core.Thread import NexTThread

logger = logging.getLogger(__name__) # pylint: disable=invalid-name

class ActiveApplication(QObject):
    """
    Class for managing an active filter graph. This class lives in the main thread. It is assumed that the graph
    is fixed during the livetime of the active application.
    """

    performOperation = Signal(str, object) # Signal is connected to all the threads (operation, barrier)
    stateChanged = Signal(int)             # Signal is emitted after the state of the graph has been changed
    aboutToClose = Signal()                 # Signal is emitted before stop operation takes place

    def __init__(self, graph):
        super().__init__()
        assertMainThread()
        self._graph = graph
        self._threads = {}
        self._filters2threads = {}
        self._composite2graphs = {}
        self._traverseAndSetup(graph)
        # initialize private variables
        self._numThreadsSynced = 0
        self._state = FilterState.CONSTRUCTING
        self._graphConnected = False
        self._interThreadConns = []
        self._operationInProgress = False
        # connect signals and slots
        for tname in self._threads:
            t = self._threads[tname]
            t.operationFinished.connect(self._operationFinished)
            # we use a queued connection because we want to be able to connect signals
            # to and from this object after constructor has passed
            self.performOperation.connect(t.performOperation, type=Qt.QueuedConnection)
        # finally, create the filters
        self.create()

    def getApplication(self):
        """
        Return the corresponding application instance
        :return:
        """
        return self._graph.getSubConfig()

    def _traverseAndSetup(self, graph, namePrefix=""):
        """
        Recursively create threads and add the filter mockups to them
        """
        for basename in graph.allNodes():
            filtername = namePrefix + "/" + basename
            mockup = graph.getMockup(basename)
            if issubclass(mockup.getPluginClass(), CompositeFilter.CompositeNode):
                with mockup.createFilter() as cf:
                    self._composite2graphs[filtername] = cf.getPlugin().getGraph()
                    self._traverseAndSetup(cf.getPlugin().getGraph(), filtername)
            elif issubclass(mockup.getPluginClass(), CompositeFilter.CompositeInputNode):
                pass
            elif issubclass(mockup.getPluginClass(), CompositeFilter.CompositeOutputNode):
                pass
            else:
                props = mockup.getPropertyCollectionImpl()
                nexTprops = props.getChildCollection("_nexxT")
                threadName = nexTprops.getProperty("thread")
                if not threadName in self._threads:
                    # create threads as needed
                    self._threads[threadName] = NexTThread(threadName)
                self._threads[threadName].addMockup(filtername, mockup)
                self._filters2threads[filtername] = threadName

    def __del__(self):
        logger.debug("destructor of ActiveApplication")
        if self._state != FilterState.DESTRUCTING and self._state != FilterState.DESTRUCTED:
            logger.warning("ActiveApplication: shutdown in destructor")
            self.cleanup()
        logger.debug("destructor of ActiveApplication done")

    def cleanup(self):
        """
        Clean up all memory objects held. Afterwards the object shall not be used anymore.
        :return:
        """
        self.shutdown()
        self._graph = None
        self._threads = {}
        self._filters2threads = {}
        self._composite2graphs = {}
        # initialize private variables
        self._numThreadsSynced = 0
        self._interThreadConns = []

    def getState(self):
        """
        return current state
        :return: a FilterState integer
        """
        return self._state

    @Slot()
    def shutdown(self):
        """
        Transfer graph to DESTRUCTED state.
        :return: None
        """
        assertMainThread()
        if self._state == FilterState.ACTIVE:
            self.stop()
        # while this is similar to code in FilterEnvironment, the lines here refer to applications
        # and the lines in FilterEnvironment refer to filters.
        if self._state == FilterState.OPENED:
            self.close()
        if self._state == FilterState.INITIALIZED:
            self.deinit()
        if self._state == FilterState.CONSTRUCTED:
            self.destruct()
        if not self._state == FilterState.DESTRUCTED:
            raise NexTInternalError("Unexpected state '%s' after shutdown." % FilterState.state2str(self._state))

    def stopThreads(self):
        """
        stop all threads (except main)
        :return: None
        """
        logger.internal("stopping threads...")
        assertMainThread()
        for tname in self._threads:
            self._threads[tname].cleanup()
        self._threads.clear()

    @staticmethod
    def _compress(proxy):
        """
        compress transitive composite proxy dependencies (e.g. when a composite input is itself connected to a composite
        filter)
        """
        changed = True
        while changed:
            changed = False
            for compName, fromPort in proxy:
                for idx in range(len(proxy[compName, fromPort])):
                    if proxy[compName, fromPort][idx] is None:
                        continue
                    proxyNode, proxyPort = proxy[compName, fromPort][idx]
                    # if fromNode is itself a composite node, resolve it
                    if (proxyNode, proxyPort) in proxy:
                        changed = True
                        proxy[compName, fromPort][idx] = None
                        proxy[compName, fromPort].extend(proxy[proxyNode, proxyPort])
        # remove None's
        for compName, fromPort in proxy:
            toDel = set()
            for idx in range(len(proxy[compName, fromPort])):
                if proxy[compName, fromPort][idx] is None:
                    toDel.add(idx)
            for idx in sorted(toDel)[::-1]:
                assert proxy[compName, fromPort][idx] is None
                proxy[compName, fromPort] = proxy[compName, fromPort][:idx] + proxy[compName, fromPort][idx + 1:]
        return proxy

    def _calculateProxyPorts(self):
        """
        collect ports which are connected to the proxy nodes in composite graphs
        """
        proxyInputPorts = {}
        proxyOutputPorts = {}
        for compName in self._composite2graphs:
            subgraph = self._composite2graphs[compName]
            cin_node = "CompositeInput"
            for fromPort in subgraph.allOutputPorts(cin_node):
                proxyInputPorts[compName, fromPort] = []
                for _, _, toNode, toPort in subgraph.allConnectionsFromOutputPort(cin_node, fromPort):
                    proxyInputPorts[compName, fromPort].append((compName + "/" + toNode, toPort))
                proxyOutputPorts[compName + "/" + cin_node, fromPort] = []
            cout_node = "CompositeOutput"
            for toPort in subgraph.allInputPorts(cout_node):
                proxyOutputPorts[compName, toPort] = []
                for fromNode, fromPort, _, _ in subgraph.allConnectionsToInputPort(cout_node, toPort):
                    proxyOutputPorts[compName, toPort].append((compName + "/" + fromNode, fromPort))
                proxyInputPorts[compName + "/" + cout_node, toPort] = []

        return self._compress(proxyInputPorts), self._compress(proxyOutputPorts)


    def _allConnections(self):
        """
        return all connections of this application including the connections from and to composite nodes
        """
        proxyInputPorts, proxyOutputPorts = self._calculateProxyPorts()
        allGraphs = set([(n, self._composite2graphs[n]) for n in self._composite2graphs] + [("", self._graph)])
        res = []

        for namePrefix, graph in allGraphs:
            for fromNode, fromPort, toNode, toPort in graph.allConnections():
                fromName = namePrefix + "/" + fromNode
                toName = namePrefix + "/" + toNode

                if (fromName, fromPort) in proxyOutputPorts:
                    src = proxyOutputPorts[fromName, fromPort]
                else:
                    src = [(fromName, fromPort)]

                if (toName, toPort) in proxyInputPorts:
                    dest = proxyInputPorts[toName, toPort]
                else:
                    dest = [(toName, toPort)]

                for s in src:
                    for d in dest:
                        res.append(s + d)
        return res

    def _setupConnections(self):
        """
        Setup the connections for actual datasample transport. It is assumed that connections are fixed during the
        livetime of the active application
        :return: None
        """
        assertMainThread()
        if self._graphConnected:
            return
        for fromNode, fromPort, toNode, toPort in self._allConnections():
            fromThread = self._filters2threads[fromNode]
            toThread = self._filters2threads[toNode]
            p0 = self._threads[fromThread].getFilter(fromNode).getPort(fromPort, OutputPortInterface)
            p1 = self._threads[toThread].getFilter(toNode).getPort(toPort, InputPortInterface)
            if toThread == fromThread:
                OutputPortInterface.setupDirectConnection(p0, p1)
            else:
                itc = OutputPortInterface.setupInterThreadConnection(p0, p1, self._threads[fromThread].qthread())
                self._interThreadConns.append(itc)
        self._graphConnected = True

    @Slot()
    def _operationFinished(self):
        """
        slot called once from each thread which has been finished with an operation
        """
        logger.internal("operation finished callback")
        assertMainThread()
        self._numThreadsSynced += 1
        if self._numThreadsSynced == len(self._threads):
            # received the finished signal from all threads
            # perform state transition
            self._numThreadsSynced = 0
            if self._state == FilterState.CONSTRUCTING:
                self._state = FilterState.CONSTRUCTED
            elif self._state == FilterState.INITIALIZING:
                self._state = FilterState.INITIALIZED
            elif self._state == FilterState.OPENING:
                self._state = FilterState.OPENED
            elif self._state == FilterState.STARTING:
                self._state = FilterState.ACTIVE
            elif self._state == FilterState.STOPPING:
                self._state = FilterState.OPENED
            elif self._state == FilterState.CLOSING:
                self._state = FilterState.INITIALIZED
            elif self._state == FilterState.DEINITIALIZING:
                self._state = FilterState.CONSTRUCTED
            elif self._state == FilterState.DESTRUCTING:
                self._state = FilterState.DESTRUCTED
                self.stopThreads()
            self.stateChanged.emit(self._state)

    @Slot()
    def create(self):
        """
        Perform create operation
        :return:None
        """
        assertMainThread()
        while self._operationInProgress and self._state != FilterState.CONSTRUCTING:
            QCoreApplication.processEvents()
        if self._state != FilterState.CONSTRUCTING:
            raise FilterStateMachineError(self._state, FilterState.CONSTRUCTING)
        self._operationInProgress = True
        self.performOperation.emit("create", Barrier(len(self._threads)))
        while self._state == FilterState.CONSTRUCTING:
            QCoreApplication.processEvents()
        self._operationInProgress = False

    @Slot()
    def init(self):
        """
        Perform init operation
        :return:None
        """
        logger.internal("entering init operation, old state %s", FilterState.state2str(self._state))
        assertMainThread()
        while self._operationInProgress and self._state != FilterState.CONSTRUCTED:
            QCoreApplication.processEvents()
        if self._state != FilterState.CONSTRUCTED:
            raise FilterStateMachineError(self._state, FilterState.INITIALIZING)
        self._operationInProgress = True
        self._state = FilterState.INITIALIZING
        self.performOperation.emit("init", Barrier(len(self._threads)))
        while self._state == FilterState.INITIALIZING:
            QCoreApplication.processEvents()
        self._operationInProgress = False
        logger.internal("leaving operation done, new state %s", FilterState.state2str(self._state))

    @Slot()
    def open(self):
        """
        Perform open operation
        :return: None
        """
        logger.internal("entering setup operation, old state %s", FilterState.state2str(self._state))
        assertMainThread()
        while self._operationInProgress and self._state != FilterState.INITIALIZED:
            QCoreApplication.processEvents()
        if self._state != FilterState.INITIALIZED:
            raise FilterStateMachineError(self._state, FilterState.OPENING)
        self._operationInProgress = True
        self._state = FilterState.OPENING
        self.performOperation.emit("open", Barrier(len(self._threads)))
        while self._state == FilterState.OPENING:
            QCoreApplication.processEvents()
        self._operationInProgress = False
        logger.internal("leaving operation done, new state %s", FilterState.state2str(self._state))

    @Slot()
    def start(self):
        """
        Setup connections if necessary and perform start operation
        :return:None
        """
        logger.internal("entering start operation, old state %s", FilterState.state2str(self._state))
        assertMainThread()
        while self._operationInProgress and self._state != FilterState.OPENED:
            QCoreApplication.processEvents()
        if self._state != FilterState.OPENED:
            raise FilterStateMachineError(self._state, FilterState.STARTING)
        self._operationInProgress = True
        self._state = FilterState.STARTING
        self._setupConnections()
        for itc in self._interThreadConns:
            # set connections in active mode.
            itc.setStopped(False)
        self.performOperation.emit("start", Barrier(len(self._threads)))
        while self._state == FilterState.STARTING:
            QCoreApplication.processEvents()
        self._operationInProgress = False
        logger.internal("leaving start operation, new state %s", FilterState.state2str(self._state))

    @Slot()
    def stop(self):
        """
        Perform stop operation
        :return: None
        """
        logger.internal("entering stop operation, old state %s", FilterState.state2str(self._state))
        assertMainThread()
        while self._operationInProgress and self._state != FilterState.ACTIVE:
            QCoreApplication.processEvents()
        if self._state != FilterState.ACTIVE:
            logger.warning("Unexpected state %s", FilterState.state2str(self._state))
            raise FilterStateMachineError(self._state, FilterState.STOPPING)
        self._operationInProgress = True
        self._state = FilterState.STOPPING
        for itc in self._interThreadConns:
            # set connections in active mode.
            itc.setStopped(True)
        self.performOperation.emit("stop", Barrier(len(self._threads)))
        while self._state == FilterState.STOPPING:
            logger.internal("stopping ... %s", FilterState.state2str(self._state))
            QCoreApplication.processEvents()
        self._operationInProgress = False
        logger.internal("leaving stop operation, new state %s", FilterState.state2str(self._state))

    @Slot()
    def close(self):
        """
        Perform close operation
        :return: None
        """
        logger.internal("entering close operation, old state %s", FilterState.state2str(self._state))
        assertMainThread()
        self.aboutToClose.emit()
        while self._operationInProgress and self._state != FilterState.OPENED:
            QCoreApplication.processEvents()
        if self._state != FilterState.OPENED:
            raise FilterStateMachineError(self._state, FilterState.CLOSING)
        self._operationInProgress = True
        self._state = FilterState.CLOSING
        self.performOperation.emit("close", Barrier(len(self._threads)))
        while self._state == FilterState.CLOSING:
            QCoreApplication.processEvents()
        self._operationInProgress = False
        logger.internal("leaving operation done, new state %s", FilterState.state2str(self._state))

    @Slot()
    def deinit(self):
        """
        Perform deinit operation
        :return: None
        """
        logger.internal("entering deinit operation, old state %s", FilterState.state2str(self._state))
        assertMainThread()
        while self._operationInProgress and self._state != FilterState.INITIALIZED:
            QCoreApplication.processEvents()
        if self._state != FilterState.INITIALIZED:
            raise FilterStateMachineError(self._state, FilterState.DEINITIALIZING)
        self._operationInProgress = True
        self._state = FilterState.DEINITIALIZING
        self.performOperation.emit("deinit", Barrier(len(self._threads)))
        while self._state == FilterState.DEINITIALIZING:
            QCoreApplication.processEvents()
        self._operationInProgress = False
        logger.internal("leaving stop operation, new state %s", FilterState.state2str(self._state))

    @Slot()
    def destruct(self):
        """
        Perform destruct operation
        :return: None
        """
        logger.internal("entering destruct operation, old state %s", FilterState.state2str(self._state))
        assertMainThread()
        while self._operationInProgress and self._state != FilterState.CONSTRUCTED:
            QCoreApplication.processEvents()
        if self._state != FilterState.CONSTRUCTED:
            raise FilterStateMachineError(self._state, FilterState.DESTRUCTING)
        self._state = FilterState.DESTRUCTING
        self.performOperation.emit("destruct", Barrier(len(self._threads)))
        logger.internal("waiting...")
        while self._state == FilterState.DESTRUCTING:
            QCoreApplication.processEvents()
            logger.internal("waiting...")
        logger.internal("waiting done")
        logger.internal("leaving destruct operation, old state %s", FilterState.state2str(self._state))
