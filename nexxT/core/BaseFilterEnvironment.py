# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the class BaseFilterEnvironment.
"""

import logging
from PySide2.QtCore import QObject, QThread
from nexxT import useCImpl
from nexxT.interface import FilterState
from nexxT.core.Exceptions import NexTInternalError, UnexpectedFilterState

logger = logging.getLogger(__name__)

if useCImpl:
    import cnexxT
    # pylint: disable=invalid-name
    # this is not really a constant, but a class name
    BaseFilterEnvironment = cnexxT.nexxT.BaseFilterEnvironment
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
                if self._state != FilterState.OPENED:
                    raise UnexpectedFilterState(self._state, "portDataChanged")
                logger.info("DataSample discarded because application has been stopped already.")
                return
            try:
                self._plugin.onPortDataChanged(inputPort)
            except Exception: # pylint: disable=broad-except
                # catching a general exception is exactly what is wanted here
                logger.exception("Uncaught exception")

        def getFullQualifiedName(self):
            """
            Returns the fully qualified name of this filter.
            :return: string instance
            """
            raise NotImplementedError()
