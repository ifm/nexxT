# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the Services class of the nexxT framework.
"""

class Services:
    """
    This class can be used to publish and query services. Services are QObjects with specific signal and slot
    interfaces you can connect to. Note that slots can be called directly via QMetaObject::invokeMethod
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
            raise RuntimeError("Service %s already exists" % name)
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
    def removeAll():
        """
        Remove all registered services
        :return: None
        """
        Services.services = {}
