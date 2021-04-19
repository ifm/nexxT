# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the PropertyCollection interface class of the nexxT framework.
"""

from PySide2.QtCore import QObject, Signal, Slot

class PropertyHandler:
    """
    .. note::
        Import this class with :code:`from nexxT.interface import PropertyHandler`.

    This class represents a property definition for a specific type. The type handles loading/saving from and to
    .json configs as well as providing editor widgets for modifying the property in a model/view framework.

    It is an abstrct base class.

    For illustration, the implementation of the IntHandler is given here as an example:

    .. literalinclude:: ../../../nexxT/core/PropertyHandlers.py
        :pyobject: IntHandler

    .. note::
        Usually, nexxT is using the wrapped C++ class instead of the python version. In python there are no
        differences between the wrapped C++ class and this python class. The C++ interface is defined in
        :cpp:class:`nexxT::PropertyHandler`
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

class PropertyCollection(QObject):
    """
    .. note::
        Import this class with :code:`from nexxT.interface import PropertyCollection`.

    This class represents a collection of properties. These collections are organized in a tree, such that there
    are parent/child relations. This is a generic base class, which is implemented in the core package. Access to
    properties throug the methods below is thread safe.

    Properties are usually used in subclasses of :py:class:`nexxT.interface.Filters.Filter`. They are presented in the
    GUI as editable entities and the settings are saved to the configuration file. They are defined during filter
    constructor and onInit(...), they can be used during the whole filter lifecycle. There is also the possibility
    to connect a callback function to the :py:attr:`propertyChanged` signal. Note that properties are
    automatically deleted from the config file if they disappear (e.g., due to code changes, changed dynamic ports,
    etc.).

    Example::

        class MyFilter(Filter):
            def __init__(self, env):
                super().__init__(False, False, env)
                pc = self.propertyCollection()
                pc.defineProperty("intProp", 1, "an unconstrained integer")
                pc.defineProperty("intPropMax", 1, "an max constrained integer", options=dict(max=10))
                pc.defineProperty("intPropBounded", 1, "a bounded integer", options=dict(min=-4, max=10))
                pc.defineProperty("floatProp", 1.0, "a floating point number", options=dict(min=-1e-4, max=10000))
                pc.defineProperty("boolProp", True, "a boolean")
                # it is also possible to connect a callback
                pc.propertyChanged.connect(self.onPropertyChanged)

            def onInit(self):
                pc = self.propertyCollection()
                pc.defineProperty("strProp", "Hello World", "a string")
                pc.defineProperty("enumProp", "Hello", "a string", options=dict(enum=["Hello", "World"]))

            def onStart(self):
                # queries the current value of the property
                pc = self.propertyCollection()
                intProp = pc.getProperty("intProp")
                # ...

            def onPropertyChanged(self, pc, name):
                logger.info("Property '%s' changed to %s", name, repr(pc.getProperty(name)))

    In the above example, different editors will be created apropriate to the chosen values. For example, the enum
    property can be edited using a combo box while integer properties are edited with spin boxes. It is also possible
    to adapt this behaviour by passing custom propertyHandlers.

    This class is an abstract base class.

    .. note::
        Usually, nexxT is using the wrapped C++ class instead of the python version. In python there are no
        differences between the wrapped C++ class and this python class. The C++ interface is defined in
        :cpp:class:`nexxT::PropertyCollection`
    """

    propertyChanged = Signal(object, str)
    """
    QT signal which is emitted after a property value of the collection has been changed by the user.

    :param pc: the PropertyCollection instance (i.e., the same as self.sender())
    :param propName: the name of the property which has been changed.
    """

    def defineProperty(self, name, defaultVal, helpstr, options=None, propertyHandler=None):
        """
        Return the value of the given property, creating a new property if it doesn't exist. If it does exist,
        the definition must be consistent, otherwise an error is raised.

        Note that the parameters options and propertyHandler must not be present at the same time. That is because the
        options are already passed to the constructor of the propertyHandler.

        :param name: the name of the property
        :param defaultVal: the default value of the property. Note that this value will be used to determine the
                           property's type. Currently supported types are string, int and float
        :param helpstr: a help string for the user (presented as a tool tip)
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
