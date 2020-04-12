# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module contains implementations for abstract classes InputPort and OutputPort
"""

import logging
from PySide2.QtCore import QThread, QSemaphore, Signal, QObject, Qt
from nexxT.interface.Ports import InputPortInterface, OutputPortInterface
from nexxT.interface.DataSamples import DataSample
from nexxT.core.Utils import handleException
from nexxT.core.Exceptions import NexTRuntimeError, NexTInternalError

logger = logging.getLogger(__name__)

class InterThreadConnection(QObject):
    """
    Helper class for transmitting data samples between threads
    """
    transmitInterThread = Signal(object, QSemaphore)

    def __init__(self, qthread_from):
        super().__init__()
        self.moveToThread(qthread_from)
        self.semaphore = QSemaphore(1)

    def receiveSample(self, dataSample):
        """
        Receive a sample, called in the source's thread. Uses a semaphore to avoid buffering infinitely.
        :param dataSample: the sample to be received
        :return: None
        """
        assert QThread.currentThread() is self.thread()
        self.semaphore.acquire(1)
        self.transmitInterThread.emit(dataSample, self.semaphore)

class OutputPortImpl(OutputPortInterface):
    """
    This class defines an output port of a filter.
    """

    # pylint: disable=abstract-method
    # the Factory function is static and will be assigned later in this module

    # constructor inherited from OutputPort

    def transmit(self, dataSample):
        """
        transmit a data sample over this port
        :param dataSample: sample to transmit
        """
        if not QThread.currentThread() is self.thread():
            raise NexTRuntimeError("OutputPort.transmit has been called from an unexpected thread.")
        self.transmitSample.emit(dataSample)

    def clone(self, newEnvironment):
        """
        Return a copy of this port attached to a new environment.
        :param newEnvironment: the new FilterEnvironment instance
        :return: a new Port instance
        """
        return OutputPortImpl(self.dynamic(), self.name(), newEnvironment)

    @staticmethod
    def setupDirectConnection(outputPort, inputPort):
        """
        Setup a direct (intra-thread) connection between outputPort and inputPort
        Note: both instances must live in same thread!
        :param outputPort: the output port instance to be connected
        :param inputPort: the input port instance to be connected
        :return:None
        """
        logger.info("setup direct connection between %s -> %s", outputPort.name(), inputPort.name())
        outputPort.transmitSample.connect(inputPort.receiveSync, Qt.DirectConnection)

    @staticmethod
    def setupInterThreadConnection(outputPort, inputPort, outputPortThread):
        """
        Setup an inter thread connection between outputPort and inputPort
        :param outputPort: the output port instance to be connected
        :param inputPort: the input port instance to be connected
        :param outputPortThread: the QThread instance of the outputPort instance
        :return: an InterThreadConnection instance which manages the connection (has
                 to survive until connections is deleted)
        """
        logger.info("setup inter thread connection between %s -> %s", outputPort.name(), inputPort.name())
        itc = InterThreadConnection(outputPortThread)
        outputPort.transmitSample.connect(itc.receiveSample, Qt.DirectConnection)
        itc.transmitInterThread.connect(inputPort.receiveAsync, Qt.QueuedConnection)
        return itc

class InputPortImpl(InputPortInterface):
    """
    This class defines an input port of a filter. In addition to the normal port attributes, there are
    two new attributes related to automatic buffering of input data samples.
    queueSizeSamples sets the maximum number of samples buffered (it can be None, if queueSizeSeconds is not None)
    queueSizeSeconds sets the maximum time of samples buffered (it can be None, if queueSizeSamples is not None)
    If both attributes are set, they are and-combined.
    """

    # pylint: disable=abstract-method
    # the Factory function is static and will be assigned later in this module

    def __init__(self, dynamic, name, environment, queueSizeSamples=1, queueSizeSeconds=None):
        super().__init__(dynamic, name, environment)
        self.queueSizeSamples = queueSizeSamples
        self.queueSizeSeconds = queueSizeSeconds
        # the queue is implemented here as a python list, which is implemented as a c array
        # in cpython. Not the most performant choice, but it is usually not used because
        # this is just a reference implementation for the more performant C++ implementation
        # in cnexxT
        self.queue = []

    def getData(self, delaySamples=0, delaySeconds=None):
        """
        Return a data sample stored in the queue (called by the filter).
        :param delaySamples: 0 related the most actual sample, numbers > 0 relates to historic samples (None can be
                             given if delaySeconds is not None)
        :param delaySeconds: if not None, a delay of 0.0 is related to the current sample, positive numbers are related
                             to historic samples (TODO specify the exact semantics of delaySeconds)
        :return: DataSample instance
        """
        if not QThread.currentThread() is self.thread():
            raise NexTRuntimeError("InputPort.getData has been called from an unexpected thread.")
        if delaySamples is not None:
            assert delaySeconds is None
            return self.queue[delaySamples]
        if delaySeconds is not None:
            assert delaySamples is None
            delayTime = delaySeconds / DataSample.TIMESTAMP_RES
            i = 0
            while i < len(self.queue) and self.queue[0].getTimestamp() - self.queue[i].getTimestamp() < delayTime:
                i += 1
            return self.queue[i]
        raise RuntimeError("delaySamples and delaySeconds are both None.")

    def _addToQueue(self, dataSample):
        self.queue.insert(0, dataSample)
        if self.queueSizeSamples is not None and len(self.queue) > self.queueSizeSamples:
            self.queue = self.queue[:self.queueSizeSamples]
        if self.queueSizeSeconds is not None:
            queueSizeTime = self.queueSizeSeconds / DataSample.TIMESTAMP_RES
            while len(self.queue) > 0 and self.queue[0].getTimestamp() - self.queue[-1].getTimestamp() > queueSizeTime:
                self.queue.pop()
        self.environment().portDataChanged(self)

    def receiveAsync(self, dataSample, semaphore):
        return self._receiveAsync(dataSample, semaphore)

    @handleException
    def _receiveAsync(self, dataSample, semaphore):
        """
        Called from framework only and implements the asynchronous receive mechanism using a semaphore.
        :param dataSample: the transmitted DataSample instance
        :param semaphore: a QSemaphore instance
        :return: None
        """
        if not QThread.currentThread() is self.thread():
            raise NexTInternalError("InputPort.receiveAsync has been called from an unexpected thread.")
        semaphore.release(1)
        self._addToQueue(dataSample)

    def receiveSync(self, dataSample):
        return self._receiveSync(dataSample)

    @handleException
    def _receiveSync(self, dataSample):
        """
        Called from framework only and implements the synchronous receive mechanism.
        :param dataSample: the transmitted DataSample instance
        :return: None
        """
        if not QThread.currentThread() is self.thread():
            raise NexTInternalError("InputPort.receiveSync has been called from an unexpected thread.")
        self._addToQueue(dataSample)

    def clone(self, newEnvironment):
        """
        Return a copy of this port attached to a new environment.
        :param newEnvironment: the new FilterEnvironment instance
        :return: a new Port instance
        """
        return InputPortImpl(self.dynamic(), self.name(), newEnvironment, self.queueSizeSamples, self.queueSizeSeconds)
