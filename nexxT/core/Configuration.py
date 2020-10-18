# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the nexxT class Configuration
"""

import logging
from PySide2.QtCore import QObject, Slot, Signal
from nexxT.core.Application import Application
from nexxT.core.CompositeFilter import CompositeFilter
from nexxT.core.Exceptions import (NexTRuntimeError, CompositeRecursion, NodeNotFoundError, NexTInternalError,
                                   PropertyCollectionPropertyNotFound, PropertyCollectionChildNotFound)
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.PluginManager import PluginManager
from nexxT.core.ConfigFiles import ConfigFileLoader

logger = logging.getLogger(__name__)

class Configuration(QObject):
    """
    A configuration is a collection of subgraphs, i.e., applications and composite filters.
    """

    subConfigAdded = Signal(object)
    subConfigRemoved = Signal(str, int)
    configNameChanged = Signal(object)
    appActivated = Signal(str, object)
    configLoaded = Signal()
    configAboutToSave = Signal()
    dirtyChanged = Signal(bool)

    CONFIG_TYPE_COMPOSITE = 0
    CONFIG_TYPE_APPLICATION = 1

    @staticmethod
    def configType(subConfig):
        """
        return the config type (either CONFIG_TYPE_COMPOSITE or CONFIG_TYPE_APPLICATION) of a SubConfiguration
        instance
        :param subConfig: a SubConfiguration instance
        :return:
        """
        if isinstance(subConfig, Application):
            return Configuration.CONFIG_TYPE_APPLICATION
        if isinstance(subConfig, CompositeFilter):
            return Configuration.CONFIG_TYPE_COMPOSITE
        raise NexTRuntimeError("Unexpected instance type")

    def __init__(self):
        super().__init__()
        self._compositeFilters = []
        self._applications = []
        self._propertyCollection = PropertyCollectionImpl("root", None)
        self._guiState = PropertyCollectionImpl("_guiState", self._propertyCollection)
        self._dirty = False

    @Slot(bool)
    def setDirty(self, dirty=True):
        """
        Slot to actualize the dirty flag of the configuration file. Emits the dirtyChanged signal if necessary.
        :param dirty: new dirty state given as a boolean
        :return:
        """
        if dirty != self._dirty:
            self._dirty = dirty
            self.dirtyChanged.emit(self._dirty)

    def dirty(self):
        """
        Returns the current dirty state.
        :return: a boolean
        """
        return self._dirty

    @Slot()
    def close(self, avoidSave=False):
        """
        Closing the configuration instance and free allocated resources.
        :return:
        """
        logger.internal("entering Configuration.close")
        if not avoidSave:
            ConfigFileLoader.saveGuiState(self)
        Application.unactivate()
        for sc in self._compositeFilters + self._applications:
            sc.cleanup()
        for c in self._compositeFilters:
            self.subConfigRemoved.emit(c.getName(), self.CONFIG_TYPE_COMPOSITE)
        self._compositeFilters = []
        for a in self._applications:
            self.subConfigRemoved.emit(a.getName(), self.CONFIG_TYPE_APPLICATION)
        self._applications = []
        self._propertyCollection.deleteLater()
        self._propertyCollection = PropertyCollectionImpl("root", None)
        self.configNameChanged.emit(None)
        self.appActivated.emit("", None)
        PluginManager.singleton().unloadAll()
        logger.internal("leaving Configuration.close")

    @Slot(object)
    def load(self, cfg):
        """
        Load the configuration from a dictionary.
        :param cfg: dictionary loaded from a json file
        :return: None
        """
        self.close()
        try:
            self._propertyCollection.defineProperty("CFGFILE", cfg["CFGFILE"],
                                                    "The absolute path to the configuration file.",
                                                    options=dict(enum=[cfg["CFGFILE"]]))
            try:
                self._propertyCollection.deleteChild("_guiState")
            except PropertyCollectionChildNotFound:
                pass
            self._guiState = PropertyCollectionImpl("_guiState", self._propertyCollection, cfg["_guiState"])
            recursiveset = set()
            def compositeLookup(name):
                nonlocal recursiveset
                if name in recursiveset:
                    raise CompositeRecursion(name)
                try:
                    return self.compositeFilterByName(name)
                except NodeNotFoundError:
                    recursiveset.add(name)
                    try:
                        for cfg_cf in cfg["composite_filters"]:
                            if cfg_cf["name"] == name:
                                cf = CompositeFilter(name, self)
                                cf.load(cfg_cf, compositeLookup)
                                return cf
                        raise NodeNotFoundError("name")
                    finally:
                        recursiveset.remove(name)

            for cfg_cf in cfg["composite_filters"]:
                compositeLookup(cfg_cf["name"])
            for cfg_app in cfg["applications"]:
                app = Application(cfg_app["name"], self)
                app.load(cfg_app, compositeLookup)
            self.setDirty(False)
            self.configNameChanged.emit(cfg["CFGFILE"])
            self.configLoaded.emit()
        except RuntimeError as e:
            self.close(avoidSave=True)
            raise e

    def save(self, file=None):
        """
        return a dictionary suitable for saving to json (inverse of load)
        :return: dictionary
        """
        self.configAboutToSave.emit()
        cfg = {}
        if file is not None:
            # TODO: we assume here that this is a new config; a "save to file" feature is not yet implemented.
            self._propertyCollection.defineProperty("CFGFILE", str(file),
                                                    "The absolute path to the configuration file.",
                                                    options=dict(enum=[str(file)]))
        try:
            cfg["CFGFILE"] = self._propertyCollection.getProperty("CFGFILE")
        except PropertyCollectionPropertyNotFound:
            cfg["CFGFILE"] = None
        cfg["_guiState"] = self._guiState.saveDict()
        cfg["composite_filters"] = [cf.save() for cf in self._compositeFilters]
        cfg["applications"] = [app.save() for app in self._applications]
        self.configNameChanged.emit(cfg["CFGFILE"])
        self.setDirty(False)
        return cfg

    def filename(self):
        """
        Get the configuration file name or None if it is not set.
        :return:
        """
        try:
            return self._propertyCollection.getProperty("CFGFILE")
        except PropertyCollectionPropertyNotFound:
            return None


    def propertyCollection(self):
        """
        Get the (root) property collection.
        :return: PropertyCollectionImpl instance
        """
        return self._propertyCollection

    def guiState(self):
        """
        Return the per-config gui state.
        :return: a PropertyCollection instance
        """
        return self._guiState

    def compositeFilterByName(self, name):
        """
        Search for the composite filter with the given name
        :param name: a string
        :return: a CompositeFilter instance
        """
        match = [cf for cf in self._compositeFilters if cf.getName() == name]
        if len(match) == 1:
            return match[0]
        if len(match) == 0:
            raise NodeNotFoundError(name)
        raise NexTInternalError("non unique name %s" % name)

    def applicationByName(self, name):
        """
        Search for the application with the given name
        :param name: a string
        :return: an Application instance
        """
        match = [app for app in self._applications if app.getName() == name]
        if len(match) == 1:
            return match[0]
        if len(match) == 0:
            raise NodeNotFoundError(name)
        raise NexTInternalError("non unique name %s" % name)

    def subConfigByNameAndTye(self, name, typeid):
        """
        Return the subconfiguration with the given name and type
        :param name: a string
        :param typeid: either CONFIG_TYPE_APPLICATION or CONFIG_TYPE_COMPOSITE
        :return: a SubConfiguration instance
        """
        if typeid == self.CONFIG_TYPE_APPLICATION:
            return self.applicationByName(name)
        if typeid == self.CONFIG_TYPE_COMPOSITE:
            return self.compositeFilterByName(name)
        raise NexTInternalError("unknown typeid %s" % typeid)

    @Slot(str)
    def activate(self, appname):
        """
        Activate the application with the given name.
        :param appname: a string
        :return: None
        """
        for app in self._applications:
            if app.getName() == appname:
                app.activate()
                self.appActivated.emit(appname, Application.activeApplication)
                return
        raise NexTRuntimeError("Application '%s' not found." % appname)

    @Slot(str, str)
    def renameComposite(self, oldName, newName):
        """
        Rename a composite subgraph
        :param oldName: the old name
        :param newName: the new name
        :return:
        """
        if oldName != newName:
            self._checkUniqueName(self._compositeFilters, newName)
            self.compositeFilterByName(oldName).setName(newName)
            self.setDirty(True)

    @Slot(str, str)
    def renameApp(self, oldName, newName):
        """
        Rename an application subgraph
        :param oldName: the old name
        :param newName: the new name
        :return:
        """
        if oldName != newName:
            self._checkUniqueName(self._applications, newName)
            self.applicationByName(oldName).setName(newName)
            self.setDirty(True)

    def addComposite(self, compFilter):
        """
        Add a composite filter instance to this configuration.
        :param compFilter: a CompositeFilter instance
        :return: None
        """
        self._checkUniqueName(self._compositeFilters, compFilter.getName())
        self._compositeFilters.append(compFilter)
        self.subConfigAdded.emit(compFilter)
        self.setDirty(True)

    def addApplication(self, app):
        """
        Add an application instance to this configuration
        :param app: an Application instance
        :return: None
        """
        self._checkUniqueName(self._applications, app.getName())
        self._applications.append(app)
        self.subConfigAdded.emit(app)
        self.setDirty(True)

    def addNewApplication(self):
        """
        Add a new application to this configuration. The name will be chosen automatically to be unique.
        :return: the chosen name
        """
        name = "application"
        idx = 1
        existing = [a.getName() for a in self._applications]
        while name in existing:
            idx += 1
            name = "application_%d" % idx
        Application(name, self)
        return name

    def addNewCompositeFilter(self):
        """
        Add a new composite filter to this configuration. The name will be chosen automaitcally to be unique.
        :return: the chosen name
        """
        name = "composite"
        idx = 1
        while len([c for c in self._compositeFilters if c.getName() == name]) > 0:
            idx += 1
            name = "composite_%d" % idx
        CompositeFilter(name, self)
        return name

    def getApplicationNames(self):
        """
        Return list of application names
        :return: list of strings
        """
        return [app.getName() for app in self._applications]

    def getCompositeFilterNames(self):
        """
        Return list of composite filters
        :return: list of strings
        """
        return [cf.getName() for cf in self._compositeFilters]

    @staticmethod
    def _checkUniqueName(collection, name):
        for i in collection:
            if i.getName() == name:
                raise NexTRuntimeError("Name '%s' is not unique." % name)

    def checkRecursion(self):
        """
        Checks for recursions in the composite filters, raises a CompositeRecursion exception if necessary.
        :return: None
        """
        for cf in self._compositeFilters:
            self._checkRecursion(cf.getGraph(), set([cf.getName()]))

    @staticmethod
    def _checkRecursion(graph, activeNames):
        if activeNames is None:
            activeNames = set()
        nodes = graph.allNodes()
        allComposites = []
        for n in nodes:
            # check whether this node is itself a composite node
            mockup = graph.getMockup(n)
            if issubclass(mockup.getPluginClass(), CompositeFilter.CompositeNode):
                allComposites.append(mockup)
                cf = mockup.getLibrary()
                name = cf.getName()
                #print("active:", activeNames, "; curr:", name)
                if name in activeNames:
                    raise CompositeRecursion(name)
                activeNames.add(name)
                Configuration._checkRecursion(cf.getGraph(), activeNames)
                activeNames.remove(name)
