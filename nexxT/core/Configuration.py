# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the nexxT class Configuration
"""

import logging
from nexxT.Qt.QtCore import QObject, Slot, Signal
from nexxT.core.Application import Application
from nexxT.core.CompositeFilter import CompositeFilter
from nexxT.core.Exceptions import (NexTRuntimeError, CompositeRecursion, NodeNotFoundError, NexTInternalError,
                                   PropertyCollectionChildNotFound)
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

    def _defaultRootPropColl(self):
        variables = None if not hasattr(self, "_propertyCollection") else self._propertyCollection.getVariables()
        res = PropertyCollectionImpl("root", None, variables=variables)
        theVars = res.getVariables()
        theVars.setReadonly({})
        for v in list(theVars.keys()):
            del theVars[v]
        # setup the default variables available on all platforms
        theVars["CFG_DIR"] = "${!str(importlib.import_module('pathlib').Path(subst('$CFGFILE')).parent.absolute())}"
        theVars["NEXXT_PLATFORM"] = "${!importlib.import_module('nexxT.core.Utils').nexxtPlatform()}"
        theVars["NEXXT_VARIANT"] = "${!importlib.import_module('os').environ.get('NEXXT_VARIANT', 'release')}"
        theVars.setReadonly({"CFG_DIR", "NEXXT_PLATFORM", "NEXXT_VARIANT", "CFGFILE"})
        theVars.variableAddedOrChanged.connect(lambda *args: self.setDirty())
        theVars.variableDeleted.connect(lambda *args: self.setDirty())
        return res

    def __init__(self):
        super().__init__()
        self._compositeFilters = []
        self._applications = []
        self._propertyCollection = self._defaultRootPropColl()
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
        self._propertyCollection = self._defaultRootPropColl()
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
            if cfg["CFGFILE"] is not None:
                # might happen during reload
                theVars = self._propertyCollection.getVariables()
                origReadonly = theVars.setReadonly([])
                theVars["CFGFILE"] = cfg["CFGFILE"]
                theVars.setReadonly(origReadonly)
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
                except NodeNotFoundError as exc:
                    recursiveset.add(name)
                    try:
                        for cfg_cf in cfg["composite_filters"]:
                            if cfg_cf["name"] == name:
                                cf = CompositeFilter(name, self)
                                cf.load(cfg_cf, compositeLookup)
                                return cf
                        raise NodeNotFoundError("name") from exc
                    finally:
                        recursiveset.remove(name)

            variables = self._propertyCollection.getVariables()
            for k in variables.keys():
                if not variables.isReadonly(k):
                    del variables[k]
            if "variables" in cfg:
                for k in cfg["variables"]:
                    variables[k] = cfg["variables"][k]
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
            theVars = self._propertyCollection.getVariables()
            origReadonly = theVars.setReadonly([])
            theVars["CFGFILE"] = file
            theVars.setReadonly(origReadonly)
        try:
            cfg["CFGFILE"] = self._propertyCollection.getVariables()["CFGFILE"]
        except KeyError:
            cfg["CFGFILE"] = None
        cfg["_guiState"] = self._guiState.saveDict()
        variables = self._propertyCollection.getVariables()
        if any(not variables.isReadonly(k) for k in variables.keys()):
            cfg["variables"] = {
                k: variables.getraw(k)
                for k in variables.keys() if not variables.isReadonly(k)
            }
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
            return self._propertyCollection.getVariables()["CFGFILE"]
        except KeyError:
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
        raise NexTInternalError(f"non unique name {name}")

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
        raise NexTInternalError(f"non unique name {name}")

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
        raise NexTInternalError(f"unknown typeid {typeid}")

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
        raise NexTRuntimeError(f"Application '{appname}' not found.")

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
            name = f"application_{idx}"
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
            name = f"composite_{idx}"
        CompositeFilter(name, self)
        return name

    def removeSubConfig(self, subConfig):
        """
        Remove the referenced sub configuration.

        :param subConfig: a SubConfiguration instance
        """
        if subConfig in self._compositeFilters:
            assert isinstance(subConfig, CompositeFilter)
            # check whether this composite filter is referenced by any other subconfig
            for sc in self._compositeFilters + self._applications:
                if sc is subConfig:
                    continue
                assert isinstance(sc, (Application, CompositeFilter))
                graph = sc.getGraph()
                for n in graph.allNodes():
                    mockup = graph.getMockup(n)
                    if issubclass(mockup.getPluginClass(), CompositeFilter.CompositeNode):
                        if mockup.getLibrary() is subConfig:
                            raise RuntimeError(f"Composite filter is still in use by {sc.getName()}.")
            self.setDirty()
            self.subConfigRemoved.emit(subConfig.getName(), self.CONFIG_TYPE_COMPOSITE)
            self._compositeFilters.remove(subConfig)
        elif subConfig in self._applications:
            self.setDirty()
            self.subConfigRemoved.emit(subConfig.getName(), self.CONFIG_TYPE_APPLICATION)
            self._applications.remove(subConfig)
        else:
            raise RuntimeError(f"Cannot find sub config {subConfig} to remove")

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
                raise NexTRuntimeError(f"Name '{name}' is not unique.")

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
