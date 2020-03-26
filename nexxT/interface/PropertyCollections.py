# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the PropertyCollection interface class of the nexxT framework.
"""

from PySide2.QtCore import QObject, Signal, Slot

class PropertyCollection(QObject):
    """
    This class represents a collection of properties. These collections are organized in a tree, such that there
    are parent/child relations. This is a generic base class, which is implemented in the core package. Access to
    properties throug the methods below is thread safe.
    """

    propertyChanged = Signal(object, str)

    def defineProperty(self, name, defaultVal, helpstr, stringConverter=None, validator=None):
        """
        Return the value of the given property, creating a new property if it doesn't exist. If it does exist,
        the definition must be consistent, otherwise an error is raised.
        :param name: the name of the property
        :param defaultVal: the default value of the property. Note that this value will be used to determine the
                           property's type. Currently supported types are string, int and float
        :param helpstr: a help string for the user
        :param stringConverter: a conversion function which converts a string to the property type. If not given,
                                a default conversion based on QLocale::C will be used.
        :param validator: an optional QValidator instance. If not given, the validator will be chosen according to the
                          defaultVal type.
        :return: the current value of this property
        """
        raise NotImplementedError()

    def getProperty(self, name):
        """
        return the property identified by name
        :param name: a string
        :return: the current property value
        """
        raise NotImplementedError()

    @Slot(str, object)
    def setProperty(self, name, value):
        """
        Set the value of a named property.
        :param name: property name
        :param value: the value to be set
        :return: None
        """
        raise NotImplementedError()

    def evalpath(self, path):
        """
        Evaluates the string path. If it is an absolute path it is unchanged, otherwise it is converted
        to an absolute path relative to the config file path.
        :param path: a string
        :return: absolute path as string
        """
        raise NotImplementedError()
