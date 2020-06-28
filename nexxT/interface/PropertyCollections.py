# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the PropertyCollection interface class of the nexxT framework.
"""

from PySide2.QtCore import QObject, Signal, Slot

class PropertyHandler: # pragma: no cover
    """
    This class represents a property definition for a specific type. The type handles loading/saving from and to
    .json configs as well as providing editor widgets for modifying the property in a model/view framework.
    """

    def options(self):
        """
        Returns the options set for this handler as a QVariantMap
        :return: a QVariantMap instance
        """
        raise NotImplementedError()

    def fromConfig(self, value):
        """
        Converts the value read from the json file into the native python format
        :param value: a QVariant instance
        :return: the native value (also a QVariant)
        """
        raise NotImplementedError()

    def toConfig(self, value):
        """
        Converts the native python format into a value suitable for json files.
        :param value: a QVariant instance (the native value)
        :return: the json value (also a QVariant)
        """
        raise NotImplementedError()

    def toViewValue(self, value):
        """
        Converts the native python format into a value suitable for display in the
        Qt model/view framework.
        :param value: a QVariant instance (the native value)
        :return: a QVariant value (suitable value for display)
        """
        raise NotImplementedError()

    def validate(self, value):
        """
        Returns a validated version of value.
        :param value: the value to be set
        :return: a validated version of value
        """
        raise NotImplementedError()

    def createEditor(self, parent):
        """
        This is called in QStyledItemDelegate::createEditor; creates an editor widget instance.
        :param parent: a QWidget instance
        :return: a QWidget instance
        """
        raise NotImplementedError()

    def setEditorData(self, editor, value):
        """
        This is called in QStyledItemDelegate::setEditorData; populates the editor widget with
        the actual data.
        :param editor: the editor widget as rezurned by createEditor
        :param value: the current property value, given as native python value
        :return: None
        """
        raise NotImplementedError()

    def getEditorData(self, editor):
        """
        This is called in QStyledItemDelegate::setModelData; converts the value from the editor
        back to native python value.
        :param editor: the editor widget
        :return: a QVariant, the new native property value
        """
        raise NotImplementedError()

class PropertyCollection(QObject): # pragma: no cover
    """
    This class represents a collection of properties. These collections are organized in a tree, such that there
    are parent/child relations. This is a generic base class, which is implemented in the core package. Access to
    properties throug the methods below is thread safe.
    """

    propertyChanged = Signal(object, str)

    def defineProperty(self, name, defaultVal, helpstr, options=None, propertyHandler=None):
        """
        Return the value of the given property, creating a new property if it doesn't exist. If it does exist,
        the definition must be consistent, otherwise an error is raised.
        :param name: the name of the property
        :param defaultVal: the default value of the property. Note that this value will be used to determine the
                           property's type. Currently supported types are string, int and float
        :param helpstr: a help string for the user
        :param options: a dict mapping string to qvariant (common options: min, max, enum)
        :param propertyHandler: a PropertyHandler instance, or None for automatic choice according to defaultVal
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
