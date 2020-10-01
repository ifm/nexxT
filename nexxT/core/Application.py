# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the nexxT framework class Application
"""

import logging
import re
from PySide2.QtCore import QCoreApplication, Qt
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.SubConfiguration import SubConfiguration
from nexxT.core.ActiveApplication import ActiveApplication
from nexxT.core.Exceptions import NexTRuntimeError, PropertyCollectionChildNotFound
from nexxT.core.Utils import MethodInvoker, assertMainThread, handleException

logger = logging.getLogger(__name__)

class Application(SubConfiguration):
    """
    This class is an application. In addition to subconfigurations, it also controls the active application.
    """

    activeApplication = None

    def __init__(self, name, configuration):
        super().__init__(name, configuration)
        configuration.addApplication(self)
        PropertyCollectionImpl("_guiState", self.getPropertyCollection())

    def guiState(self, name):
        """
        Return the gui state of the entity referenced by 'name' (eitehr a full qualified filter name or a service)
        :param name: a string
        :return: a PropertyCollectionImpl instance
        """
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        pc = self.getPropertyCollection()
        gs = pc.getChildCollection("_guiState")
        try:
            cc = gs.getChildCollection(name)
        except PropertyCollectionChildNotFound:
            cc = PropertyCollectionImpl(name, gs)
        return cc


    @staticmethod
    @handleException
    def unactivate():
        """
        if an active application exists, close it.
        :return:
        """
        logger.internal("entering unactivate")
        if Application.activeApplication is not None:
            logger.internal("need to stop existing application first")
            Application.activeApplication.cleanup()
            del Application.activeApplication
            Application.activeApplication = None
        logger.internal("leaving unactivate")

    @handleException
    def activate(self):
        """
        puts this application to active
        :return: None
        """
        logger.internal("entering activate")
        self.unactivate()
        Application.activeApplication = ActiveApplication(self._graph)
        QCoreApplication.instance().aboutToQuit.connect(Application.activeApplication.shutdown)
        logger.internal("leaving activate")

    @staticmethod
    @handleException
    def initialize():
        """
        Initialize the active application such that the filters are active.
        :return:
        """
        assertMainThread()
        if Application.activeApplication is None:
            raise NexTRuntimeError("No active application to initialize")
        # make sure that the application is re-created before initializing it
        # this is needed to synchronize the properties, etc.
        MethodInvoker(Application.activeApplication.getApplication().getConfiguration().activate,
                      Qt.DirectConnection, Application.activeApplication.getApplication().getName())
        MethodInvoker(Application.activeApplication.init, Qt.DirectConnection)
        MethodInvoker(Application.activeApplication.open, Qt.DirectConnection)
        MethodInvoker(Application.activeApplication.start, Qt.DirectConnection)

    @staticmethod
    @handleException
    def deInitialize():
        """
        Deinitialize the active application such that the filters are in CONSTRUCTED state
        :return:
        """
        assertMainThread()
        if Application.activeApplication is None:
            raise NexTRuntimeError("No active application to initialize")
        MethodInvoker(Application.activeApplication.stop, Qt.DirectConnection)
        MethodInvoker(Application.activeApplication.close, Qt.DirectConnection)
        MethodInvoker(Application.activeApplication.deinit, Qt.DirectConnection)
