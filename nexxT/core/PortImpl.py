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
from nexxT.interface.Services import Services
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
        self._stopped = True

    def receiveSample(self, dataSample):
        """
        Receive a sample, called in the source's thread. Uses a semaphore to avoid buffering infinitely.
        :param dataSample: the sample to be received
        :return: None
        """
        self._receiveSample(dataSample)

    @handleException
    def _receiveSample(self, dataSample):
        assert QThread.currentThread() is self.thread()
        while True:
            if self._stopped:
                logger.info("The inter-thread connection is set to stopped mode; data sample discarded.")
                break
            if self.semaphore.tryAcquire(1, 500):
                self.transmitInterThread.emit(dataSample, self.semaphore)
                break

    def setStopped(self, stopped):
        """
        When the connection is stopped (the default), acquire will not deadlock and there is a warning when samples are
        transmitted, samples are not forwarded to the input port in this case. Note: This method is thread safe and
        may be called from any thread.
        :return:
        """
        self._stopped = stopped

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
        self._queueSizeSamples = queueSizeSamples
        self._queueSizeSeconds = queueSizeSeconds
        self.setQueueSize(queueSizeSamples, queueSizeSeconds)
        self._semaphoreN = {
        }
        self._interthreadDynamicQueue = False
        try:
            self.srvprof = Services.getService("Profiling")
        except KeyError:
            self.srvprof = None
        self.profname = None
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
        if self._queueSizeSamples is not None and self._queueSizeSamples > 0:
            if len(self.queue) > self._queueSizeSamples:
                self.queue = self.queue[:self._queueSizeSamples]
        if self._queueSizeSeconds is not None and self._queueSizeSeconds > 0.0:
            queueSizeTime = self._queueSizeSeconds / DataSample.TIMESTAMP_RES
            while len(self.queue) > 0 and self.queue[0].getTimestamp() - self.queue[-1].getTimestamp() > queueSizeTime:
                self.queue.pop()

    def _transmit(self):
        if self.srvprof is not None:
            if self.profname is None:
                self.profname = self.environment().getFullQualifiedName() + self.name()
            self.srvprof.beforePortDataChanged(self.profname)
        self.environment().portDataChanged(self)
        if self.srvprof is not None:
            self.srvprof.afterPortDataChanged(self.profname)

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
        self._addToQueue(dataSample)
        if not self._interthreadDynamicQueue:
            # usual behaviour
            semaphore.release(1)
            self._transmit()
        else:
            if semaphore not in self._semaphoreN:
                self._semaphoreN[semaphore] = 1
            delta = self._semaphoreN[semaphore] - len(self.queue)
            if delta <= 0:
                # the semaphore's N is too small
                semaphore.release(1-delta)
                self._semaphoreN[semaphore] += -delta
                logger.internal("delta = %d: semaphoreN = %d", delta, self._semaphoreN[semaphore])
                self._transmit()
            elif delta > 0:
                # first acquire is done by caller
                self._semaphoreN[semaphore] -= 1
                # the semaphore's N is too large, try acquires to reduce the size
                for i in range(1, delta):
                    if semaphore.tryAcquire(1):
                        self._semaphoreN[semaphore] -= 1
                    else:
                        break
                logger.internal("delta = %d: semaphoreN = %d", delta, self._semaphoreN[semaphore])
                self._transmit()

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
        self._transmit()

    def clone(self, newEnvironment):
        """
        Return a copy of this port attached to a new environment.
        :param newEnvironment: the new FilterEnvironment instance
        :return: a new Port instance
        """
        return InputPortImpl(self.dynamic(), self.name(), newEnvironment, self._queueSizeSamples,
                             self._queueSizeSeconds)

    def setQueueSize(self, queueSizeSamples, queueSizeSeconds):
        """
        Set the queue size of this port.
        :param queueSizeSamples: 0 related the most actual sample, numbers > 0 relates to historic samples (None can be
                                 given if delaySeconds is not None)
        :param queueSizeSeconds: if not None, a delay of 0.0 is related to the current sample, positive numbers are
                                 related to historic samples
        :return:
        """
        if (queueSizeSamples is None or queueSizeSamples <= 0) and (queueSizeSeconds is None or queueSizeSeconds <= 0):
            logger.warning("Warning: infinite buffering used for port '%s'. "
                           "Using a one sample sized queue instead.", self.name())
            queueSizeSamples = 1
        self._queueSizeSamples = queueSizeSamples
        self._queueSizeSeconds = queueSizeSeconds

    def queueSizeSamples(self):
        """
        return the current queueSize in samples
        :return: an integer
        """
        return self._queueSizeSamples

    def queueSizeSeconds(self):
        """
        return the current queueSize in seconds
        :return: an integer
        """
        return self._queueSizeSeconds

    def setInterthreadDynamicQueue(self, enabled):
        """
        If enabled is True, inter thread connections to this input port are dynamically queued for non-blocking
        behaviour. This setting does not affect connections from within the same thread. This method can be called
        only during constructor or the onInit() method of a filter.
        :param enabled: whether the dynamic queuing feature is enabled or not.
        :return:
        """
        if enabled != self._interthreadDynamicQueue:
            state = self.environment().state()
            # pylint: disable=import-outside-toplevel
            # needed to avoid recursive import
            from nexxT.interface.Filters import FilterState # avoid recursive import
            if state not in [FilterState.CONSTRUCTING, FilterState.CONSTRUCTED,
                             FilterState.INITIALIZING, FilterState.INITIALIZED]:
                logger.error("Cannot change the interthreadDynamicQueue setting in state %s.",
                             FilterState.state2str(state))
            else:
                self._interthreadDynamicQueue = enabled

    def interthreadDynamicQueue(self):
        """
        Return the interthread dynamic queue setting.
        :return: a boolean
        """
        return self._interthreadDynamicQueue
