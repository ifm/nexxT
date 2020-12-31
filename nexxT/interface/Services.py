# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the Services class of the nexxT framework.
"""
import logging

logger = logging.getLogger(__name__)

class Services:
    """
    .. note::
        Import this class with :code:`from nexxT.interface import Services`.

    This class can be used to publish and query services.

    The idea behind services is to provide a generic component interface, which is used to provide core functionalities,
    such that it is easily possiblet to change most aspects of nexxT without getting too deep into the core design.
    Typical services are the MainWindow service providing the core UI, the PlaybackControl providing the control for
    playback filters both in GUI and headless mode, the Configuration service providing interfaces for manipulating the
    configuration and the Logging service.

    In contrast to filters, services are not tied to the configuration's lifecycle management. Instead, services are
    loaded at nexxT startup and they are usually available until the process is finished.

    Services are QObjects with specific signal and slot interfaces you can connect to. Note that slots can be called
    directly via QMetaObject::invokeMethod in C++. In python this is normally not needed because a wrapped QObject will
    offer to call slots directly via python calls.

    .. note::
        Usually, nexxT is using the wrapped C++ class instead of the python version. In python there are no
        differences between the wrapped C++ class and this python class. The C++ interface is defined in
        :cpp:class:`nexxT::Services`
    """
    services = {}

    @staticmethod
    def addService(name, service):
        """
        Publish a named service.

        :param name: the name of the service
        :param service: a QObject instance
        :return: None
        """
        if name in Services.services:
            logger.warning("Service %s already existing, automatically replacing it with the new variant.")
        Services.services[name] = service

    @staticmethod
    def getService(name):
        """
        Query a named service

        :param name: the name of the service
        :return: the related QObject instance
        """
        return Services.services[name]

    @staticmethod
    def removeService(name):
        """
        Remove the given named service

        :param name: the name of the service
        :return: the related QObject instance
        """
        del Services.services[name]

    @staticmethod
    def removeAll():
        """
        Remove all registered services

        :return: None
        """
        Services.services = {}
