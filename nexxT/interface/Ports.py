# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the Port, InputPort and OutputPort interface classes of the nexxT framework.
"""

from PySide2.QtCore import QObject, Signal

class Port(QObject):
    """
    This class is the base class for ports. It is used mainly as structure, containing the 3 properties
    dynamic (boolean), name (str) and environment (a FilterEnvironment instance).

    ..note::
        Usually nexxT is using a wrapped C++ class instead of this pure python version. In python there are no
        differences between the wrapped C++ class and this python class. The C++ interface is defined in
        :cpp:class:`nexxT::Port`
    """
    INPUT_PORT = 0
    OUTPUT_PORT = 1

    def __init__(self, dynamic, name, environment):
        """
        Constructor.

        :param dynamic: boolean whether this is a dynamic port or not
        :param name: the port name, given as a string
        :param environment: the corresponding FilterEnvironment instance
        """
        super().__init__()
        self._dynamic = dynamic
        self._name = name
        self._environment = environment
        if not isinstance(self, OutputPortInterface) and not isinstance(self, InputPortInterface):
            raise RuntimeError("Ports must be either InputPorts or OutputPorts")
        self._type = self.OUTPUT_PORT if isinstance(self, OutputPortInterface) else self.INPUT_PORT

    def dynamic(self):
        """
        Returns whether this is a dynamic port

        :return: a boolean
        """
        return self._dynamic

    def name(self):
        """
        Returns the port name

        :return: a string
        """
        return self._name

    def setName(self, name):
        """
        Sets the port name

        :param name: the port name given as a string
        :return: None
        """
        self._name = name

    def environment(self):
        """
        Returns the environment instance managing this port

        :return: FilterEnvironment instance
        """
        return self._environment

    def isInput(self):
        """
        Returns true if this is an input port

        :return: bool
        """
        return self._type == self.INPUT_PORT

    def isOutput(self):
        """
        Returns true if this is an output port

        :return: bool
        """
        return self._type == self.OUTPUT_PORT

    def clone(self, newEnvironment):
        """
        This function must be overwritten in inherited classes to create a clone of this port attached to a
        different environment.

        :param newEnvironment: the new FilterEnvironment instance
        :return: a new Port instance
        """
        raise NotImplementedError()

def OutputPort(dynamic, name, environment): # pylint: disable=invalid-name
    # camel case is used because this is a factory function for class OutputPortInterface
    """
    .. note::
        Import this function with :code:`from nexxT.interface import OutputPort`.

    Factory function to create an OutputPort instance with an actual implementation attached. Will be dynamically
    implemented by the nexxT framework. This is done to prevent having implementation details in the class

    :param dynamic: boolean whether this is a dynamic input port
    :param name: the name of the port
    :param environment: the FilterEnvironment instance
    :return: an OutputPortInterface instance (actually an OutputPortImpl instance)
    """
    raise NotImplementedError()

class OutputPortInterface(Port):
    """
    This abstract base class defines the interface of an output port of a filter.

    ..note::
        Usually nexxT is using a wrapped C++ class instead of this pure python version. In python there are no
        differences between the wrapped C++ class and this python class. The C++ interface is defined in
        :cpp:class:`nexxT::OutputPortInterface`
    """

    # constructor inherited from Port
    transmitSample = Signal(object)

    def transmit(self, dataSample):
        """
        transmit a data sample over this port

        :param dataSample: sample to transmit
        """
        raise NotImplementedError()

    def clone(self, newEnvironment):
        """
        Return a copy of this port attached to a new environment.

        :param newEnvironment: the new FilterEnvironment instance
        :return: a new Port instance
        """
        raise NotImplementedError()

def InputPort(dynamic, name, environment, queueSizeSamples=1, queueSizeSeconds=None): # pylint: disable=invalid-name
    # camel case is used because this is a factory function for class OutputPortInterface
    """
    Factory function to creates an InputPortInterface instance with an actual implementation attached. Will be
    dynamically implemented by the nexxT framework. This is done to prevent having implementation details in the class.

    .. note::
        Import this function with :code:`from nexxT.interface import InputPort`.

    :param dynamic: boolean whether this is a dynamic input port
    :param name: the name of the port
    :param environment: the FilterEnvironment instance
    :param queueSizeSamples: the size of the queue in samples
    :param queueSizeSeconds: the size of the queue in seconds
    :return: an InputPortInterface instance (actually an InputPortImpl instance)
    """
    raise NotImplementedError()

class InputPortInterface(Port):
    """
    This abstract class defines the interface of an input port of a filter. In addition to the normal port attributes,
    there are two new attributes related to automatic buffering of input data samples.
    queueSizeSamples sets the maximum number of samples buffered (it can be None, if queueSizeSeconds is not None)
    queueSizeSeconds sets the maximum time of samples buffered (it can be None, if queueSizeSamples is not None)
    If both attributes are set, they are and-combined.

    ..note::
        Usually nexxT is using a wrapped C++ class instead of this pure python version. In python there are no
        differences between the wrapped C++ class and this python class. The C++ interface is defined in
        :cpp:class:`nexxT::InputPortInterface`
    """

    def getData(self, delaySamples=0, delaySeconds=None):
        """
        Return a data sample stored in the queue (called by the filter).

        :param delaySamples: 0 related the most actual sample, numbers > 0 relates to historic samples (None can be
                             given if delaySeconds is not None)
        :param delaySeconds: if not None, a delay of 0.0 is related to the current sample, positive numbers are related
                             to historic samples (TODO specify the exact semantics of delaySeconds)
        :return: DataSample instance
        """
        raise NotImplementedError()

    def receiveAsync(self, dataSample, semaphore):
        """
        Called from framework only and implements the asynchronous receive mechanism using a semaphore.

        :param dataSample: the transmitted DataSample instance
        :param semaphore: a QSemaphore instance
        :return: None
        """
        raise NotImplementedError()

    def receiveSync(self, dataSample):
        """
        Called from framework only and implements the synchronous receive mechanism. TODO implement

        :param dataSample: the transmitted DataSample instance
        :return: None
        """
        raise NotImplementedError()

    def clone(self, newEnvironment):
        """
        Return a copy of this port attached to a new environment.

        :param newEnvironment: the new FilterEnvironment instance
        :return: a new Port instance
        """
        raise NotImplementedError()

    def setQueueSize(self, queueSizeSamples, queueSizeSeconds):
        """
        Set the queue size of this port.

        :param queueSizeSamples: 0 related the most actual sample, numbers > 0 relates to historic samples (None can be
                                 given if delaySeconds is not None)
        :param queueSizeSeconds: if not None, a delay of 0.0 is related to the current sample, positive numbers are
                                 related to historic samples
        :return:
        """
        raise NotImplementedError()

    def queueSizeSamples(self):
        """
        return the current queueSize in samples

        :return: an integer
        """
        raise NotImplementedError

    def queueSizeSeconds(self):
        """
        return the current queueSize in seconds

        :return: an integer
        """
        raise NotImplementedError

    def setInterthreadDynamicQueue(self, enabled):
        """
        If enabled is True, inter thread connections to this input port are dynamically queued for non-blocking
        behaviour.

        This setting does not affect connections from within the same thread. This method can be called
        only during constructor or the onInit() method of a filter. The main use case is a recording filter where the
        QT signal/slot is allowed to buffer as many samples as allowed in the input port's queue to prevent unwanted
        blocking behaviour.

        Enabling this might cause a larger delay and might also consume a lot of memory.

        :param enabled: whether the dynamic queuing feature is enabled or not.
        :return:
        """
        raise NotImplementedError

    def interthreadDynamicQueue(self):
        """
        Return the interthread dynamic queue setting.

        :return: a boolean
        """
        raise NotImplementedError
