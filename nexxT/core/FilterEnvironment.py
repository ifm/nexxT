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
from PySide2.QtCore import QObject, Signal, QMutex, QMutexLocker, QThread
from nexxT.interface import FilterState, InputPortInterface, OutputPortInterface
from nexxT import useCImpl
from nexxT.core.PluginManager import PluginManager
from nexxT.core.Exceptions import (PortExistsError, PortNotFoundError, FilterStateMachineError, NexTRuntimeError,
                                   NexTInternalError, DynamicPortUnsupported, UnexpectedFilterState)

logger = logging.getLogger(__name__)

# TODO: make new file for BaseFilterEnvironment
if useCImpl:
    import cnexxT
    # this is not really a constant, but a class name
    BaseFilterEnvironment = cnexxT.nexxT.BaseFilterEnvironment # pylint: disable=invalid-name
else:
    class BaseFilterEnvironment(QObject):
        """
        This class is a base class for the FilterEnvironment class. It contains all methods
        necessary to port to C++.
        """
        def _assertMyThread(self):
            if QThread.currentThread() is not self._thread:
                raise NexTInternalError("Function is called from unexpected thread")

        def __init__(self, propertyCollection):
            super().__init__()
            self._plugin = None
            self._thread = QThread.currentThread()
            self._propertyCollection = propertyCollection
            self._dynamicInputPortsSupported = False
            self._dynamicOutputPortsSupported = False

        def setPlugin(self, plugin):
            """
            Sets the plugin managed by this BaseFilterEnvironment instance.
            :param plugin: a Filter instance
            :return: None
            """
            if self._plugin is not None:
                self._plugin.deleteLater() # pylint: disable=no-member
                self._plugin = None
            self._plugin = plugin

        def resetPlugin(self):
            """
            Resets the plugin managed by this BaseFilterEnvironment instance.
            :return: None
            """
            self.setPlugin(None)

        def getPlugin(self):
            """
            Get the corresponding Filter instance.
            :return: a Filter instance
            """
            return self._plugin

        def propertyCollection(self):
            """
            Get the property collection of this filter.
            :return: PropertyCollection instance
            """
            self._assertMyThread()
            return self._propertyCollection

        def guiState(self):
            """
            Return the gui state associated with this filter.
            :return: PropertyCollection instance
            """
            raise NotImplementedError()

        def setDynamicPortsSupported(self, dynInPortsSupported, dynOutPortsSupported):
            """
            Changes dynamic port supported settings for input and output ports. Will raise an exception if dynamic ports
            are not supported but dynamic ports are already existing.
            :param dynInPortsSupported: boolean whether dynamic input ports are supported
            :param dynOutPortsSupported: boolean whether dynamic output ports are supported
            :return: None
            """
            self._assertMyThread()
            self._dynamicInputPortsSupported = dynInPortsSupported
            self._dynamicOutputPortsSupported = dynOutPortsSupported
            if not dynInPortsSupported:
                p = self.getDynamicInputPorts()
                assert len(p) == 0 # TOOD: we would need to delete the existing dynamic ports
            if not dynOutPortsSupported:
                p = self.getDynamicOutputPorts()
                assert len(p) == 0

        def getDynamicPortsSupported(self):
            """
            Return the dynamic port supported flags.
            :return: 2-tuple of booleans
            """
            self._assertMyThread()
            return self._dynamicInputPortsSupported, self._dynamicOutputPortsSupported

        def portDataChanged(self, inputPort):
            """
            Calls the onPortDataChanged of the filter and catches exceptions as needed.
            :param inputPort: The InputPort instance where the data arrived.
            :return: None
            """
            self._assertMyThread()
            if self._state != FilterState.ACTIVE:
                if self._state != FilterState.INITIALIZED:
                    raise UnexpectedFilterState(self._state, "portDataChanged")
                logger.info("DataSample discarded because application has been stopped already.")
                return
            try:
                self._plugin.onPortDataChanged(inputPort)
            except Exception: # pylint: disable=broad-except
                # catching a general exception is exactly what is wanted here
                logger.exception("Uncaught exception")

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

    def close(self):
        """
        Deinitialize filter if necessary.
        :return: None
        """
        if not (self.getPlugin() is None or (useCImpl and self.getPlugin().data() is None)):
            if self._state == FilterState.ACTIVE:
                self.stop()
            if self._state == FilterState.INITIALIZED:
                self.deinit()
            if not self._state in [FilterState.CONSTRUCTED, FilterState.DESTRUCTING]:
                raise FilterStateMachineError(self._state, FilterState.DESTRUCTING)
            self._state = FilterState.DESTRUCTING
        self.resetPlugin()

    def __enter__(self):
        return self

    def __exit__(self, *args): #exctype, value, traceback
        self.close()

    def guiState(self):
        """
        Gets the gui state of this filter. Note that the gui state, in contrast to the properties, is dependent on the
        concrete instance of a filter.
        :return:
        """
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
            assert self.state() in [FilterState.CONSTRUCTING, FilterState.CONSTRUCTED]
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
        self._assertMyThread()
        if self.getPlugin() is None or (useCImpl and self.getPlugin().data() is None):
            raise NexTInternalError("Cannot perform state transitions on uninitialized plugin")
        operations = {
            FilterState.CONSTRUCTING: (None, FilterState.CONSTRUCTED, None),
            FilterState.INITIALIZING: (FilterState.CONSTRUCTED, FilterState.INITIALIZED, self.getPlugin().onInit),
            FilterState.STARTING: (FilterState.INITIALIZED, FilterState.ACTIVE, self.getPlugin().onStart),
            FilterState.STOPPING: (FilterState.ACTIVE, FilterState.INITIALIZED, self.getPlugin().onStop),
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
        self._assertMyThread()
        if self.getPlugin() is None or (useCImpl and self.getPlugin().data() is None):
            raise NexTInternalError("Cannot perform state transitions on uninitialized plugin")
        operations = {
            FilterState.CONSTRUCTING: (None, FilterState.CONSTRUCTED, None),
            FilterState.INITIALIZING: (FilterState.CONSTRUCTED, FilterState.INITIALIZED, self.getPlugin().onInit),
            FilterState.STARTING: (FilterState.INITIALIZED, FilterState.ACTIVE, self.getPlugin().onStart),
            FilterState.STOPPING: (FilterState.ACTIVE, FilterState.INITIALIZED, self.getPlugin().onStop),
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

    def start(self):
        """
        Perform filter start (state transition INITIALIZED -> STARTING -> ACTIVE)
        :return: None
        """
        self._assertMyThread()
        self._stateTransition(FilterState.STARTING)

    def stop(self):
        """
        Perform filter stop (state transition ACTIVE -> STOPPING -> INITIALIZED)
        :return: None
        """
        self._assertMyThread()
        self._stateTransition(FilterState.STOPPING)

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
