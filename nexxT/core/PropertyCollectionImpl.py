# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the PropertyCollection interface class of the nexxT framework.
"""

from collections import OrderedDict
from pathlib import Path
import logging
import platform
import string
import os
import shiboken2
from PySide2.QtGui import QValidator, QRegExpValidator, QIntValidator, QDoubleValidator
from PySide2.QtCore import QRegExp, QLocale, Signal, Slot, QObject, QMutex, QMutexLocker
from nexxT.core.Exceptions import (PropertyCollectionChildNotFound, PropertyCollectionChildExists,
                                   PropertyCollectionUnknownType, PropertyParsingError, NexTInternalError,
                                   PropertyInconsistentDefinition, PropertyCollectionPropertyNotFound)
from nexxT.core.Utils import assertMainThread, checkIdentifier
from nexxT.interface import PropertyCollection

logger = logging.getLogger(__name__)

class Property:
    """
    This class represents a specific property.
    """
    def __init__(self, defaultVal, helpstr, converter, validator):
        self.defaultVal = defaultVal
        self.value = defaultVal
        self.helpstr = helpstr
        self.converter = converter
        self.validator = validator
        self.used = True

class ReadonlyValidator(QValidator):
    """
    A validator implementing readonly values.
    """
    def __init__(self, value):
        super().__init__()
        self._value = value

    def fixup(self, inputstr): # pylint: disable=unused-argument
        """
        override from QValidator
        :param inputstr: string
        :return: fixed string
        """
        return str(self._value)

    def validate(self, inputstr, pos):
        """
        override from QValidator
        :param inputstr: string
        :param pos: int
        :return: state, newpos
        """
        state = QValidator.Acceptable if inputstr == str(self._value) else QValidator.Invalid
        return state, inputstr, pos

class PropertyCollectionImpl(PropertyCollection):
    """
    This class represents a collection of properties. These collections are organized in a tree, such that there
    are parent/child relations.
    """
    propertyChanged = Signal(object, str)
    propertyAdded = Signal(object, str)
    propertyRemoved = Signal(object, str)
    childAdded = Signal(object, str)
    childRemoved = Signal(object, str)
    childRenamed = Signal(object, str, str)

    def __init__(self, name, parentPropColl, loadedFromConfig=None):
        PropertyCollection.__init__(self)
        assertMainThread()
        self._properties = {}
        self._accessed = False # if no access to properties has been made, we stick with configs from config file.
        self._loadedFromConfig = loadedFromConfig if loadedFromConfig is not None else {}
        self._propertyMutex = QMutex(QMutex.Recursive)
        if parentPropColl is not None:
            if not isinstance(parentPropColl, PropertyCollectionImpl):
                raise NexTInternalError("parentPropColl should always be a property collection instance but it isn't")
            parentPropColl.addChild(name, self)

    def applyLoadedConfig(self, loadedFromConfig):
        """
        applies the loaded configuration after the instance has been already created. This is used for guiState items.
        :param loadedFromConfig: dictionary loaded from json file
        :return: None
        """
        if len(self._loadedFromConfig) > 0:
            raise NexTInternalError("Expected that no loaded config is present.")
        self._accessed = False
        self._loadedFromConfig = loadedFromConfig

    def childEvent(self, event):
        assertMainThread()
        if event.added():
            self.childAdded.emit(self, event.child().objectName())
        elif event.removed():
            self.childRemoved.emit(self, event.child().objectName())

    def getChildCollection(self, name):
        """
        Return child property collection with given name
        :param name: the name of the child
        :return: PropertyCollection instance
        """
        assertMainThread()
        # note findChild seems to be recursive, that's really a boomer; the option Qt::FindDirectChildrenOnly
        # doesn't seem to be there on the python side. So we do this by hand
        #res = self.findChild(QObject, name)
        res = [c for c in self.children() if c.objectName() == name]
        if len(res) == 0:
            raise PropertyCollectionChildNotFound(name)
        return res[0]

    @staticmethod
    def _defaultIntConverter(theObject):
        if isinstance(theObject, str):
            c = QLocale(QLocale.C)
            ret, ok = c.toInt(theObject)
            if not ok:
                raise PropertyParsingError("Cannot convert '%s' to int." % theObject)
            return ret
        c = QLocale(QLocale.C)
        return c.toString(theObject)

    @staticmethod
    def _defaultFloatConverter(theObject):
        if isinstance(theObject, str):
            c = QLocale(QLocale.C)
            ret, ok = c.toDouble(theObject)
            if not ok:
                raise PropertyParsingError("Cannot convert '%s' to double." % theObject)
            return ret
        c = QLocale(QLocale.C)
        return c.toString(theObject)

    @staticmethod
    def _defaultValidator(defaultVal):
        if isinstance(defaultVal, str):
            validator = QRegExpValidator(QRegExp(".*"))
        elif isinstance(defaultVal, int):
            validator = QIntValidator()
        elif isinstance(defaultVal, float):
            validator = QDoubleValidator()
        else:
            raise PropertyCollectionUnknownType(defaultVal)
        return validator

    @staticmethod
    def _defaultStringConverter(defaultVal):
        if isinstance(defaultVal, str):
            stringConverter = str
        elif isinstance(defaultVal, int):
            stringConverter = PropertyCollectionImpl._defaultIntConverter
        elif isinstance(defaultVal, float):
            stringConverter = PropertyCollectionImpl._defaultFloatConverter
        else:
            raise PropertyCollectionUnknownType(defaultVal)
        return stringConverter

    def defineProperty(self, name, defaultVal, helpstr, stringConverter=None, validator=None):
        """
        Return the value of the given property, creating a new property if it doesn't exist.
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
        self._accessed = True
        checkIdentifier(name)
        with QMutexLocker(self._propertyMutex):
            if not name in self._properties:
                if validator is None:
                    validator = self._defaultValidator(defaultVal)
                if stringConverter is None:
                    stringConverter = self._defaultStringConverter(defaultVal)
                self._properties[name] = Property(defaultVal, helpstr, stringConverter, validator)
                p = self._properties[name]
                if name in self._loadedFromConfig:
                    l = self._loadedFromConfig[name]
                    if type(l) is type(defaultVal):
                        p.value = l
                    else:
                        try:
                            p.value = stringConverter(str(l))
                        except PropertyParsingError:
                            logger.warning("Property %s: can't convert value '%s'.", name, str(l))
                self.propertyAdded.emit(self, name)
            else:
                # the arguments to getProperty shall be consistent among calls
                p = self._properties[name]
                if p.defaultVal != defaultVal or p.helpstr != helpstr:
                    raise PropertyInconsistentDefinition(name)
                if stringConverter is not None and p.converter is not stringConverter:
                    raise PropertyInconsistentDefinition(name)
                if validator is not None and p.validator is not validator:
                    raise PropertyInconsistentDefinition(name)

            p.used = True
            return p.value

    @Slot(str)
    def getProperty(self, name):
        self._accessed = True
        with QMutexLocker(self._propertyMutex):
            if name not in self._properties:
                raise PropertyCollectionPropertyNotFound(name)
            p = self._properties[name]
            p.used = True
            return p.value

    def getPropertyDetails(self, name):
        """
        returns the property details of the property identified by name.
        :param name: the property name
        :return: a Property instance
        """
        with QMutexLocker(self._propertyMutex):
            if name not in self._properties:
                raise PropertyCollectionPropertyNotFound(name)
            p = self._properties[name]
            return p

    def getAllPropertyNames(self):
        """
        Query all property names handled in this collection
        :return: list of strings
        """
        return list(self._properties.keys())

    @Slot(str, str)
    def setProperty(self, name, value):
        """
        Set the value of a named property.
        :param name: property name
        :param value: the value to be set
        :return: None
        """
        self._accessed = True
        with QMutexLocker(self._propertyMutex):
            if name not in self._properties:
                raise PropertyCollectionPropertyNotFound(name)
            p = self._properties[name]
            if isinstance(value, str):
                state, newValue, newCursorPos = p.validator.validate(value, len(value))
                if state != QValidator.Acceptable:
                    raise PropertyParsingError("Property %s: '%s' is not compatible to given validator."
                                               % (name, value))
                value = p.converter(newValue)
            if value != p.value:
                p.value = value
                self.propertyChanged.emit(self, name)

    def markAllUnused(self):
        """
        Mark all properties of the collection as unused (TODO: do we need recursion?)
        :return: None
        """
        with QMutexLocker(self._propertyMutex):
            for n in self._properties:
                self._properties[n].used = False

    def deleteUnused(self):
        """
        Delete properties marked as unused (TODO: do we need recursion?)
        :return: None
        """
        if not self._accessed:
            # this function is only meaningful if something in the store has been used.
            return
        with QMutexLocker(self._propertyMutex):
            toDel = []
            for n in self._properties:
                if not self._properties[n].used:
                    toDel.append(n)
            for n in toDel:
                del self._properties[n]
                self.propertyRemoved.emit(self, n)
            self._loadedFromConfig.clear()

    def saveDict(self):
        """
        Save properties into a dictionary suited for json output.
        :return: dictionary with key/value pairs
        """
        if self._accessed:
            res = OrderedDict()
            with QMutexLocker(self._propertyMutex):
                for n in sorted(self._properties):
                    res[n] = self._properties[n].value
            return res
        return self._loadedFromConfig

    def addChild(self, name, propColl):
        """
        register child
        :param name: name of the child
        :param propColl: the child, an instance of PropertyCollectionImpl
        :return: None
        """
        assertMainThread()
        try:
            self.getChildCollection(name)
            raise PropertyCollectionChildExists(name)
        except PropertyCollectionChildNotFound:
            pass
        propColl.setObjectName(name)
        propColl.setParent(self)
        logger.internal("Propcoll %s: add child %s", self.objectName(), name)

    def renameChild(self, oldName, newName):
        """
        Rename a child collection.
        :param oldName: original name of collection
        :param newName: new name of collection
        :return: None
        """
        assertMainThread()
        c = self.getChildCollection(oldName)
        try:
            self.getChildCollection(newName)
            raise PropertyCollectionChildExists(newName)
        except PropertyCollectionChildNotFound:
            pass
        c.setObjectName(newName)
        self.childRenamed.emit(self, oldName, newName)

    def deleteChild(self, name):
        """
        Remove a child collection.
        :param name: the name of the collection.
        :return: None
        """
        assertMainThread()
        cc = self.getChildCollection(name)
        for c in cc.children():
            if isinstance(c, PropertyCollectionImpl):
                cc.deleteChild(c.objectName())
        if shiboken2.isValid(cc): # pylint: disable=no-member
            shiboken2.delete(cc) # pylint: disable=no-member

    def evalpath(self, path):
        """
        Evaluates the string path. If it is an absolute path it is unchanged, otherwise it is converted
        to an absolute path relative to the config file path.
        :param path: a string
        :return: absolute path as string
        """
        if Path(path).is_absolute():
            return path
        root_prop = self
        while root_prop.parent() is not None:
            root_prop = root_prop.parent()
        # substitute ${VAR} with environment variables
        default_environ = dict(
            NEXXT_VARIANT="release"
        )
        if platform.system() == "Windows":
            default_environ["NEXXT_PLATFORM"] = "msvc_x86%s" % ("_64" if platform.architecture()[0] == "64bit" else "")
        else:
            default_environ["NEXXT_PLATFORM"] = "linux_x86%s" % ("_64" if platform.architecture()[0] == "64bit" else "")
        origpath = path
        path = string.Template(path).safe_substitute({**default_environ, **os.environ})
        logger.debug("interpolated path %s -> %s", origpath, path)
        if Path(path).is_absolute():
            return path
        try:
            return str((Path(root_prop.getProperty("CFGFILE")).parent / path).absolute())
        except PropertyCollectionPropertyNotFound:
            return path
