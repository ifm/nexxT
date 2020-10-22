# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the class FilterEnvironment.
"""

import copy
import logging
from PySide2.QtCore import Signal, QMutex, QMutexLocker
from nexxT.interface import FilterState, InputPortInterface, OutputPortInterface
from nexxT import useCImpl
from nexxT.core.BaseFilterEnvironment import BaseFilterEnvironment
from nexxT.core.PluginManager import PluginManager
from nexxT.core.Exceptions import (PortExistsError, PortNotFoundError, FilterStateMachineError, NexTRuntimeError,
                                   NexTInternalError, DynamicPortUnsupported)

logger = logging.getLogger(__name__)

class FilterEnvironment(BaseFilterEnvironment): # pylint: disable=too-many-public-methods
    """
    This class implements the environment of a filter. It implements the filter state machine, manages dynamic
    filter ports (these ports are defined by the user, not by the filter developer). Currently it also manages
    plugins, but this functionality will be moved to a seperate class in the future. It can serve as a context
    manager for automatic de-initializing of the embedded filter instance.
    """
    portInformationUpdated = Signal(object, object)

    def __init__(self, library, factoryFunction, propertyCollection, mockup=None):
        BaseFilterEnvironment.__init__(self, propertyCollection)
        # ports are accessed by multiple threads (from FilterMockup.createFilter)
        self._portMutex = QMutex(QMutex.Recursive)
        self._ports = []
        self._mockup = mockup
        self._state = FilterState.CONSTRUCTING
        if library is not None:
            plugin = PluginManager.singleton().create(library, factoryFunction, self)
            if plugin is not None:
                self.setPlugin(plugin)
                plugin.setObjectName(str(library) + "_" + str(factoryFunction))
            self._state = FilterState.CONSTRUCTED

    if useCImpl:
        def _assertMyThread(self):
            self.assertMyThread()

    def getMockup(self):
        """
        Returns the FilterMockup instance this environment belongs to.
        :return: FilterMockup instance (or None)
        """
        return self._mockup

    def destroy(self):
        """
        Deinitialize filter if necessary.
        :return: None
        """
        if not (self.getPlugin() is None or (useCImpl and self.getPlugin().data() is None)):
            if self._state == FilterState.ACTIVE:
                self.stop()
            if self._state == FilterState.OPENED:
                self.close()
            if self._state == FilterState.INITIALIZED:
                self.deinit()
            if not self._state in [FilterState.CONSTRUCTED, FilterState.DESTRUCTING]:
                raise FilterStateMachineError(self._state, FilterState.DESTRUCTING)
            self._state = FilterState.DESTRUCTING
        self.resetPlugin()

    def __enter__(self):
        return self

    def __exit__(self, *args): #exctype, value, traceback
        self.destroy()

    def guiState(self):
        """
        Gets the gui state of this filter. Note that the gui state, in contrast to the properties, is dependent on the
        concrete instance of a filter.
        :return:
        """
        # pylint: disable=import-outside-toplevel
        # to avoid recursive import
        from nexxT.core.Thread import NexTThread
        from nexxT.core.Application import Application
        if isinstance(self.parent(), NexTThread) and Application.activeApplication is not None:
            try:
                path = self.parent().getName(self)
                app = Application.activeApplication.getApplication()
                return app.guiState("filters/" + path)
            except NexTRuntimeError:
                logger.warning("Cannot find guiState.")
        return None

    def getFullQualifiedName(self):
        """
        Returns the fully qualified name of this filter.
        :return: a string instance.
        """
        # pylint: disable=import-outside-toplevel
        # to avoid recursive import
        from nexxT.core.Thread import NexTThread
        from nexxT.core.Application import Application
        if isinstance(self.parent(), NexTThread) and Application.activeApplication is not None:
            try:
                return self.parent().getName(self)
            except NexTRuntimeError:
                pass
        logger.warning("Cannot find name of environment.")
        return "?unknown?"

    def addPort(self, port):
        """
        Register a port of this filter.
        :param port: instance of InputPort ot OutputPort
        :return: None
        """
        if useCImpl:
            # make sure to make copies of the shared pointers
            port = copy.copy(port)
        with QMutexLocker(self._portMutex):
            assert self.state() in [FilterState.CONSTRUCTING, FilterState.CONSTRUCTED, FilterState.INITIALIZING]
            dynInSupported, dynOutSupported = self.getDynamicPortsSupported()
            if port.dynamic() and ((port.isInput() and not dynInSupported) or
                                   (port.isOutput() and not dynOutSupported)):
                raise DynamicPortUnsupported(port.name(), type(port))
            for p in self._ports:
                if p.isInput() and port.isInput() and p.name() == port.name():
                    raise PortExistsError("<unknown>", port.name(), InputPortInterface)
                if p.isOutput() and port.isOutput() and p.name() == port.name():
                    raise PortExistsError("<unknown>", port.name(), OutputPortInterface)
            self._ports.append(port)

    def removePort(self, port):
        """
        Unregister a port of this filter
        :param port: instacne of InputPort or OutputPort
        :return: None
        """
        with QMutexLocker(self._portMutex):
            logger.debug("remove port: %s", port)
            if useCImpl:
                for p in self._ports:
                    if p.data() == port.data():
                        port = p
            self._ports.remove(port)

    def _getInputPorts(self, dynamic):
        with QMutexLocker(self._portMutex):
            return [p for p in self._ports if p.isInput()
                    and (p.dynamic() == dynamic or dynamic is None)]

    def emitPortInformationUpdated(self, inPorts, outPorts):
        """
        Emits the signal portInformationUpdated (this is necessary due to some shiboken fails).
        :param inPorts: list of input ports
        :param outPorts: list of output ports
        :return: None
        """
        self.portInformationUpdated.emit(inPorts, outPorts)

    def getDynamicInputPorts(self):
        """
        Get dynamic input ports
        :return: list of InputPort instances
        """
        return self._getInputPorts(True)

    def getStaticInputPorts(self):
        """
        Get static input ports
        :return: list of InputPort instances
        """
        return self._getInputPorts(False)

    def getAllInputPorts(self):
        """
        Get all input ports
        :return: list of InputPort instances
        """
        return self._getInputPorts(None)

    def _getOutputPorts(self, dynamic):
        with QMutexLocker(self._portMutex):
            return [p for p in self._ports if p.isOutput()
                    and (p.dynamic() == dynamic or dynamic is None)]

    def getDynamicOutputPorts(self):
        """
        Get dynamic output ports
        :return: list of OutputPort instances
        """
        return self._getOutputPorts(True)

    def getStaticOutputPorts(self):
        """
        Get static output ports
        :return: list of OutputPort instances
        """
        return self._getOutputPorts(False)

    def getAllOutputPorts(self):
        """
        Get all output ports
        :return: list of OutputPort instances
        """
        return self._getOutputPorts(None)

    def getPort(self, portName, portType):
        """
        Get port by name
        :param portName: the name of the port
        :param portType: either InputPort or OutputPort
        :return: port instance
        """
        query = {InputPortInterface:"isInput", OutputPortInterface:"isOutput"}
        with QMutexLocker(self._portMutex):
            f = [p for p in self._ports if getattr(p, query[portType])() and p.name() == portName]
            if len(f) != 1:
                raise PortNotFoundError("<unknown>", portName, portType)
            return f[0]

    def getOutputPort(self, portName):
        """
        Get output port by name
        :param portName: the name of the port
        :return: port instance
        """
        return self.getPort(portName, OutputPortInterface)

    def getInputPort(self, portName):
        """
        Get input port by name
        :param portName: the name of the port
        :return: port instance
        """
        return self.getPort(portName, InputPortInterface)

    def updatePortInformation(self, otherInstance):
        """
        Copy port information from another FilterEnvironment instance to this.
        :param otherInstance: FilterEnvironment instance
        :return: None
        """
        with QMutexLocker(self._portMutex):
            oldIn = self.getAllInputPorts()
            oldOut = self.getAllOutputPorts()
            self._ports = [p.clone(self) for p in otherInstance.getAllInputPorts() + otherInstance.getAllOutputPorts()]
            self.setDynamicPortsSupported(*otherInstance.getDynamicPortsSupported())
            self.emitPortInformationUpdated(oldIn, oldOut)

    def preStateTransition(self, operation):
        """
        State transitions might be explicitely set all filters to the operation state before executing the
        operation on the filters. This method makes sure that the state transitions are sane.
        :param operation: The FilterState operation.
        :return: None
        """
        logger.internal("Performing pre-state transition: %s", FilterState.state2str(operation))
        self._assertMyThread()
        if self.getPlugin() is None or (useCImpl and self.getPlugin().data() is None):
            raise NexTInternalError("Cannot perform state transitions on uninitialized plugin")
        operations = {
            FilterState.CONSTRUCTING: (None, FilterState.CONSTRUCTED, None),
            FilterState.INITIALIZING: (FilterState.CONSTRUCTED, FilterState.INITIALIZED, self.getPlugin().onInit),
            FilterState.OPENING: (FilterState.INITIALIZED, FilterState.OPENED, self.getPlugin().onOpen),
            FilterState.STARTING: (FilterState.OPENED, FilterState.ACTIVE, self.getPlugin().onStart),
            FilterState.STOPPING: (FilterState.ACTIVE, FilterState.OPENED, self.getPlugin().onStop),
            FilterState.CLOSING: (FilterState.OPENED, FilterState.INITIALIZED, self.getPlugin().onClose),
            FilterState.DEINITIALIZING: (FilterState.INITIALIZED, FilterState.CONSTRUCTED, self.getPlugin().onDeinit),
            FilterState.DESTRUCTING: (FilterState.CONSTRUCTED, None, None),
        }
        fromState, toState, function = operations[operation]
        if self._state != fromState:
            raise FilterStateMachineError(self._state, operation)
        self._state = operation

    def _stateTransition(self, operation):
        """
        Perform state transition according to operation.
        :param operation: The FilterState operation.
        :return: None
        """
        logger.internal("Performing state transition: %s", FilterState.state2str(operation))
        self._assertMyThread()
        if self.getPlugin() is None or (useCImpl and self.getPlugin().data() is None):
            raise NexTInternalError("Cannot perform state transitions on uninitialized plugin")
        operations = {
            FilterState.CONSTRUCTING: (None, FilterState.CONSTRUCTED, None),
            FilterState.INITIALIZING: (FilterState.CONSTRUCTED, FilterState.INITIALIZED, self.getPlugin().onInit),
            FilterState.OPENING: (FilterState.INITIALIZED, FilterState.OPENED, self.getPlugin().onOpen),
            FilterState.STARTING: (FilterState.OPENED, FilterState.ACTIVE, self.getPlugin().onStart),
            FilterState.STOPPING: (FilterState.ACTIVE, FilterState.OPENED, self.getPlugin().onStop),
            FilterState.CLOSING: (FilterState.OPENED, FilterState.INITIALIZED, self.getPlugin().onClose),
            FilterState.DEINITIALIZING: (FilterState.INITIALIZED, FilterState.CONSTRUCTED, self.getPlugin().onDeinit),
            FilterState.DESTRUCTING: (FilterState.CONSTRUCTED, None, None),
        }
        fromState, toState, function = operations[operation]
        # filters must be either in fromState or already in operation state (if preStateTransition has been used)
        if self._state not in (fromState, operation):
            raise FilterStateMachineError(self._state, operation)
        self._state = operation
        try:
            function()
        except Exception as e: # pylint: disable=broad-except
            # What should be done on errors?
            #    1. inhibit state transition to higher state
            #         pro: prevent activation of not properly intialized filter
            #         con: some actions of onInit might already be executed, we really want to call onDeinit for cleanup
            #    2. ignore the exception and perform state transition anyways
            #         pro/con is inverse to 1
            #    3. introduce an error state
            #         pro: filters in error state are clearly identifyable and prevented from being used
            #         con: higher complexity, cleanup issues, ...
            #    --> for now we use 2.
            self._state = fromState
            logger.exception("Exception while executing operation %s of filter %s",
                             FilterState.state2str(operation),
                             self.propertyCollection().objectName())
        self._state = toState

    def init(self):
        """
        Perform filter initialization (state transition CONSTRUCTED -> INITIALIZING -> INITIALIZED)
        :return: None
        """
        self._assertMyThread()
        self._stateTransition(FilterState.INITIALIZING)

    def open(self):
        """
        Perform filter opening (state transition INITIALIZED -> OPENING -> OPENED
        :return:
        """
        self._assertMyThread()
        self._stateTransition(FilterState.OPENING)

    def start(self):
        """
        Perform filter start (state transition OPENED -> STARTING -> ACTIVE)
        :return: None
        """
        self._assertMyThread()
        self._stateTransition(FilterState.STARTING)

    def stop(self):
        """
        Perform filter stop (state transition ACTIVE -> STOPPING -> OPENED)
        :return: None
        """
        self._assertMyThread()
        self._stateTransition(FilterState.STOPPING)

    def close(self):
        """
        Perform filter stop (state transition OPENED -> CLOSING -> INITIALIZED)
        :return: None
        """
        self._assertMyThread()
        self._stateTransition(FilterState.CLOSING)

    def deinit(self):
        """
        Perform filter deinitialization (state transition INITIALIZED -> DEINITIALIZING -> CONSTRUCTED)
        :return: None
        """
        self._assertMyThread()
        self._stateTransition(FilterState.DEINITIALIZING)

    def state(self):
        """
        Return the filter state.
        :return: filter state integer
        """
        self._assertMyThread()
        return self._state
