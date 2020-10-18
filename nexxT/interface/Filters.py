# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the FilterState and Filter classes of the nexxT interface.
"""

from PySide2.QtCore import QObject
from nexxT.interface import OutputPort, InputPort

class FilterState:
    """
    This class defines an enum for the filter states.
    """
    CONSTRUCTING = 0
    CONSTRUCTED = 1
    INITIALIZING = 2
    INITIALIZED = 3
    OPENING = 4
    OPENED = 5
    STARTING = 6
    ACTIVE = 7
    STOPPING = 8
    CLOSING = 9
    DEINITIALIZING = 10
    DESTRUCTING = 11
    DESTRUCTED = 12

    @staticmethod
    def state2str(state):
        """
        converts a state integer to the corresponding string
        :param state: the state integer
        :return: string
        """
        for k in FilterState.__dict__:
            if k[0] != "_" and k.upper() == k and getattr(FilterState, k) == state:
                return k
        raise RuntimeError("Unknown state %s" % state)


class Filter(QObject):
    """
    This class is the base class for defining a nexxT filter. A minimal nexxT filter class looks like this:

    class SimpleStaticFilter(Filter):

        def __init__(self, environment):
            super().__init__(False, False, environment)
            pc = self.propertyCollection()
            self.sample_property = pc.getProperty("sample_property", 0.1, "a sample property for demonstration purpose")
            self.inPort = InputPort.Factory(False, "inPort", environment)
            self.addStaticPort(self.inPort)
            self.outPort = OutputPort.Factory(False, "outPort", environment)
            self.addStaticPort(self.outPort)

        def onPortDataChanged(self, inputPort):
            dataSample = inputPort.getData()
            newSample = DataSample.copy(dataSample)
            self.outPort.transmit(dataSample)

    The constructor has a single argument environment which is passed through to this base class. It configures
    dynamic port usage with the two boolean flags. In the constructor, the filter can define and query properties
    and create ports.

    The onPortDataChanged is called whenever new data arrives on an input port.
    """
    def __init__(self, dynInPortsSupported, dynOutPortsSupported, environment):
        super().__init__()
        environment.setDynamicPortsSupported(dynInPortsSupported, dynOutPortsSupported)
        self._environment = environment

    # protected methods (called by filter implementations)

    def propertyCollection(self):
        """
        Return the property collection associated with this filter.
        :return: PropertyCollection instance
        """
        return self._environment.propertyCollection()

    def guiState(self):
        """
        Return the gui state associated with this filter. Note: the gui state shall not be used for properties which
        are important for data transport, for these cases the propertyCollection() shall be used. Typical gui state
        variables are: the geometry of a user-managed window, the last directory path used in a file dialog, etc.
        The gui state might not be initialized during mockup-phase.
        :return: PropertyCollection instance
        """
        return self._environment.guiState()

    def addStaticPort(self, port):
        """
        Register a static port for this filter. Only possible in CONSTRUCTING state.
        :param port: InputPort or OutputPort instance
        :return: None
        """
        if port.dynamic():
            raise RuntimeError("The given port should be static but is dynamic.")
        self._environment.addPort(port)

    def addStaticOutputPort(self, name):
        """
        Shortcut for generating a static output port and adding it to the filter
        :param name: The name of the output port (see OutputPort)
        :return: the new port instance
        """
        port = OutputPort(False, name, self._environment)
        self.addStaticPort(port)
        return port

    def addStaticInputPort(self, name, queueSizeSamples=1, queueSizeSeconds=None):
        """
        Shortcut for generating a static input port and adding it to the filter
        :param name: The name of the input port (see InputPort)
        :return: the new port instance
        """
        port = InputPort(False, name, self._environment,
                         queueSizeSamples=queueSizeSamples, queueSizeSeconds=queueSizeSeconds)
        self.addStaticPort(port)
        return port

    def removeStaticPort(self, port):
        """
        Remove a static port of this filter. Only possible in CONSTRUCTING state.
        :param port: InputPort or OutputPort instance
        :return: None
        """
        if port.dynamic():
            raise RuntimeError("The given port should be static but is dynamic.")
        self._environment.removePort(port)

    def getDynamicInputPorts(self):
        """
        Get dynamic input ports of this filter. Only possible in and after INITIALIZING state.
        :return: list of dynamic input ports
        """
        return self._environment.getDynamicInputPorts()

    def getDynamicOutputPorts(self):
        """
        Get dynamic output ports of this filter. Only possible in and after INITIALIZING state.
        :return: list of dynamic output ports
        """
        return self._environment.getDynamicOutputPorts()

    # protected methods (overwritten by filter implementations)

    def onInit(self):
        """
        This function can be overwritten for performing initialization tasks related to dynamic ports.
        :return: None
        """

    def onOpen(self):
        """
        This function can be overwritten for general initialization tasks (e.g. acquire resources needed to
        run the filter, open files, connecting to services etc.).
        :return:
        """

    def onStart(self):
        """
        This function can be overwritten to reset internal filter state. It is called before loading a new sequence.
        :return: None
        """

    def onPortDataChanged(self, inputPort):
        """
        This function can be overwritten to be notified when new data samples arrive at input ports. For each
        data sample arrived this function will be called exactly once.
        :param inputPort: the port where the data arrived
        :return: None
        """

    def onStop(self):
        """
        Opposite of onStart.
        :return: None
        """

    def onClose(self):
        """
        This function can be overwritten for general de-initialization tasks (e.g. release resources needed to
        run the filter, close files, etc.). It is the opoosite to onOpen(...).
        :return: None
        """

    def onDeinit(self):
        """
        This function can be overwritten for performing de-initialization tasks related to dynamic ports. It is
        the opposite to onInit(...)
        :return: None
        """

    def environment(self):
        """
        Returns the environment associated with this filter.
        :return: a FilterEnvironment instance
        """
        return self._environment

    def onSuggestDynamicPorts(self): # pylint: disable=no-self-use
        """
        Shall return the suggested dynamic ports of this filter. Prominent example is to return the streams
        contained in a HDF5 file. Note that it is safe to assume that the instance lives in the GUI thread,
        when this function is called from the nexxT framework.
        :return: listOfInputPortNames, listOfOutputPortNames
        """
        return [], []

class FilterSurrogate:
    """
    This class acts as a surrogate to reference a filter from a DLL/shared object plugin from within python.
    Create an instance in one of your modules and preferrably create an entry point for it.
    """
    def __init__(self, dllUrls, name):
        """
        Create a CFilterSurrogate instance.
        :param dllUrls: might be (1) a dictionary mapping variant names to URLs, variant names are usually "nonopt" and
                        "release" or (2) a url string which will be mapped to the release variant
                        Note that URLs for binary libraries (DLL's or shared objects) are of the form
                        "binary://<absolute-path-to-dll>".'The absolute path might contain variables like
                        ${NEXXT_PLATFORM} or ${NEXXT_VARIANT}.
        :param name: the name of the filter class or factory function
        """
        if not isinstance(dllUrls, dict):
            dllUrls = {"release": dllUrls}
        self._dllUrls = dllUrls
        self._name = name

    def dllUrl(self, variant):
        """
        returns the absolute path of the optimzed dll/shared object
        """
        try:
            return self._dllUrls[variant]
        except KeyError:
            return self._dllUrls["release"]

    def name(self):
        """
        returns the name of the filter class
        """
        return self._name
