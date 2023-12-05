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
import nexxT.shiboken
from nexxT.Qt.QtCore import Signal, Slot, QRecursiveMutex, QMutexLocker
from nexxT.core.Exceptions import (PropertyCollectionChildNotFound, PropertyCollectionChildExists,
                                   PropertyParsingError, NexTInternalError,
                                   PropertyInconsistentDefinition, PropertyCollectionPropertyNotFound)
from nexxT.core.Utils import assertMainThread, checkIdentifier
from nexxT.core.PropertyHandlers import defaultHandler
from nexxT.core.Variables import Variables
from nexxT.interface import PropertyCollection, PropertyHandler

logger = logging.getLogger(__name__)

class Property:
    """
    This class represents a specific property.
    """
    def __init__(self, defaultVal, helpstr, handler):
        self.defaultVal = defaultVal
        self.value = defaultVal
        self.helpstr = helpstr
        self.handler = handler
        self.useEnvironment = False
        self.used = True

class PropertyCollectionImpl(PropertyCollection):
    """
    This class represents a collection of properties. These collections are organized in a tree, such that there
    are parent/child relations.
    """
    propertyAdded = Signal(object, str)
    propertyRemoved = Signal(object, str)
    childAdded = Signal(object, str)
    childRemoved = Signal(object, str)
    childRenamed = Signal(object, str, str)

    def __init__(self, name, parentPropColl, loadedFromConfig=None, variables=None):
        PropertyCollection.__init__(self)
        assertMainThread()
        self._properties = {}
        if variables is None:
            self._vars = Variables(parent=parentPropColl._vars if parentPropColl is not None else None)
            self._vars.setObjectName("propcoll:" + name)
        else:
            self._vars = variables
            assert parentPropColl is None # this should be the root property
        self._accessed = False # if no access to properties has been made, we stick with configs from config file.
        self._loadedFromConfig = loadedFromConfig if loadedFromConfig is not None else {}
        self._propertyMutex = QRecursiveMutex()
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
        """
        Overwritten from QObject

        :param event: a QChildEvent instance.
        """
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

    def getVariables(self):
        """
        Return the associated variables instance.
        """
        return self._vars

    def defineProperty(self, name, defaultVal, helpstr, options=None, propertyHandler=None, variables=None):
        """
        Return the value of the given property, creating a new property if it doesn't exist.
        :param name: the name of the property
        :param defaultVal: the default value of the property. Note that this value will be used to determine the
                           property's type. Currently supported types are string, int and float
        :param helpstr: a help string for the user
        :param options: a dict mapping string to qvariant (common options: min, max, enum)
        :param propertyHandler: a PropertyHandler instance, or None for automatic choice according to defaultVal
        :return: the current value of this property
        """
        self._accessed = True
        checkIdentifier(name)
        if options is not None and propertyHandler is None and isinstance(options, PropertyHandler):
            propertyHandler = options
            options = None
        with QMutexLocker(self._propertyMutex):
            if options is not None and propertyHandler is not None:
                raise PropertyInconsistentDefinition(
                    "Pass either options or propertyHandler to defineProperty but not both.")
            if options is None:
                options = {}
            ignoreInconsistentOptions = False
            if "ignoreInconsistentOptions" in options:
                ignoreInconsistentOptions = options["ignoreInconsistentOptions"]
                del options["ignoreInconsistentOptions"]
            if propertyHandler is None:
                propertyHandler = defaultHandler(defaultVal)(options)
            assert isinstance(propertyHandler, PropertyHandler)
            assert isinstance(options, dict)
            if propertyHandler.validate(defaultVal) != defaultVal:
                # pylint: disable=consider-using-f-string
                raise PropertyInconsistentDefinition(
                    "The validation of the default value must be the identity (%s != %s)!" %
                    (repr(propertyHandler.validate(defaultVal)), repr(defaultVal)))
            if not name in self._properties:
                self._properties[name] = Property(defaultVal, helpstr, propertyHandler)
                p = self._properties[name]
                if name in self._loadedFromConfig:
                    l = self._loadedFromConfig[name]
                    if isinstance(l, dict) and "subst" in l and "value" in l:
                        p.useEnvironment = l["subst"]
                        p.value = l["value"]
                    else:
                        p.useEnvironment = False
                        p.value = l
                try:
                    if not p.useEnvironment:
                        p.value = p.handler.validate(p.handler.fromConfig(p.value))
                    else:
                        if variables is None:
                            variables = self._vars
                        p.handler.validate(variables.subst(p.value))
                except Exception as e:
                    raise PropertyParsingError(
                        f"Error parsing property {name} from {repr(l)} (original exception: {str(e)})") from e
                self.propertyAdded.emit(self, name)
            else:
                # the arguments to getProperty shall be consistent among calls
                p = self._properties[name]
                if p.defaultVal != defaultVal or p.helpstr != helpstr:
                    raise PropertyInconsistentDefinition(name)
                if not isinstance(p.handler, type(propertyHandler)) or options != p.handler.options():
                    if ignoreInconsistentOptions:
                        p.handler = propertyHandler
                        logger.debug("option %s has inconsistent options but ignoring as requested.", name)
                    else:
                        raise PropertyInconsistentDefinition(name)

            p.used = True
            return p.value

    @Slot(str)
    def getProperty(self, name, subst=True, variables=None):
        self._accessed = True
        with QMutexLocker(self._propertyMutex):
            if name not in self._properties:
                raise PropertyCollectionPropertyNotFound(name)
            p = self._properties[name]
            p.used = True
            if p.useEnvironment and subst:
                if variables is None:
                    variables = self._vars
                return p.handler.validate(variables.subst(p.value))
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
            try:
                value = p.handler.validate(value)
            except Exception as e:
                raise PropertyParsingError(
                    f"Error parsing property {name} from {repr(value)} (original exception: {str(e)})") from e
            if value != p.value or p.useEnvironment:
                p.value = value
                p.useEnvironment = False
                self.propertyChanged.emit(self, name)

    @Slot(str, str)
    def setVarProperty(self, name, value):
        """
        Set the value of a named property using an variable substitution.

        :param name: property name
        :param value: the value to be set
        :return: None
        """
        self._accessed = True
        with QMutexLocker(self._propertyMutex):
            if name not in self._properties:
                raise PropertyCollectionPropertyNotFound(name)
            p = self._properties[name]
            if value != p.value or not p.useEnvironment:
                p.value = value
                p.useEnvironment = True
                self.propertyChanged.emit(self, name)

    def markAllUnused(self):
        """
        Mark all properties of the collection as unused (TODO: do we need recursion?)
        :return: None
        """
        with QMutexLocker(self._propertyMutex):
            for _, p in self._properties.items():
                p.used = False

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
            for n, p in self._properties.items():
                if not p.used:
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
                    p = self._properties[n]
                    if p.useEnvironment:
                        res[n] = {"subst": True, "value": p.value}
                    else:
                        res[n] = {"subst": False, "value": p.handler.toConfig(p.value)}
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
        propColl.getVariables().setParent(self.getVariables())
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
        if nexxT.shiboken.isValid(cc): # pylint: disable=no-member
            nexxT.shiboken.delete(cc) # pylint: disable=no-member

    def evalpath(self, path, variables=None):
        """
        Evaluates the string path. If it is an absolute path it is unchanged, otherwise it is converted
        to an absolute path relative to the config file path.
        :param path: a string
        :return: absolute path as string
        """
        if variables is None:
            variables = self._vars
        spath = variables.subst(path)
        if spath != path or not Path(spath).is_absolute():
            logger.warning("Deprecated: Implicit substitution or relative paths to the config file. Consider to use "
                           "explicit variable substitution with ${CFG_DIR} to reference the directory of the config "
                           "file instead. Found while evaluating %s.", path)
        if not Path(spath).is_absolute():
            spath = str((Path(variables.subst("$CFG_DIR")) / spath).absolute())
        return spath

class PropertyCollectionProxy(PropertyCollection):
    """
    This class proxies to a PropertyCollection object but uses a different instance of variables
    """

    def __init__(self, proxiedPropColl, variables):
        PropertyCollection.__init__(self)
        self._proxiedPropColl = proxiedPropColl
        self._vars = variables
        assertMainThread()
        self._propertyMutex = QRecursiveMutex()
        proxiedPropColl.propertyChanged.connect(self._propertyChanged)
        self.setObjectName(self._proxiedPropColl.objectName())

    def _propertyChanged(self, _, name):
        self.propertyChanged.emit(self, name)

    def getChildCollection(self, name):
        """
        Return child property collection with given name
        :param name: the name of the child
        :return: PropertyCollection instance
        """
        return self._proxiedPropColl.getChildCollection(name)

    def getVariables(self):
        """
        Return the associated variables instance.
        """
        return self._vars

    def defineProperty(self, name, defaultVal, helpstr, options=None, propertyHandler=None):
        """
        Return the value of the given property, creating a new property if it doesn't exist.
        :param name: the name of the property
        :param defaultVal: the default value of the property. Note that this value will be used to determine the
                           property's type. Currently supported types are string, int and float
        :param helpstr: a help string for the user
        :param options: a dict mapping string to qvariant (common options: min, max, enum)
        :param propertyHandler: a PropertyHandler instance, or None for automatic choice according to defaultVal
        :return: the current value of this property
        """
        return self._proxiedPropColl.defineProperty(name, defaultVal, helpstr, options, propertyHandler,
                                                    variables=self._vars)

    @Slot(str)
    def getProperty(self, name, subst=True):
        """
        See PropertyCollectionImpl.getProperty for details
        """
        return self._proxiedPropColl.getProperty(name, subst, variables=self._vars)

    def getPropertyDetails(self, name):
        """
        returns the property details of the property identified by name.
        :param name: the property name
        :return: a Property instance
        """
        return self._proxiedPropColl.getPropertyDetails(self, name)

    def getAllPropertyNames(self):
        """
        Query all property names handled in this collection
        :return: list of strings
        """
        return self._proxiedPropColl.getAllPropertyNames()

    @Slot(str, str)
    def setProperty(self, name, value):
        """
        Set the value of a named property.

        :param name: property name
        :param value: the value to be set
        :return: None
        """
        self._proxiedPropColl.setProperty(name, value)

    @Slot(str, str)
    def setVarProperty(self, name, value):
        """
        Set the value of a named property using an variable substitution.

        :param name: property name
        :param value: the value to be set
        :return: None
        """
        self._proxiedPropColl.setVarProperty(name, value)

    def evalpath(self, path):
        """
        Evaluates the string path. If it is an absolute path it is unchanged, otherwise it is converted
        to an absolute path relative to the config file path.
        :param path: a string
        :return: absolute path as string
        """
        return self._proxiedPropColl.evalpath(path, variables=self._vars)
