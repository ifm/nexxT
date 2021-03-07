# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the FilterMockup class
"""

import logging
from PySide2.QtCore import QMutexLocker, Qt
from nexxT.interface import InputPort, OutputPort, InputPortInterface, OutputPortInterface
from nexxT.core.FilterEnvironment import FilterEnvironment
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.Exceptions import PortNotFoundError, PortExistsError, PropertyCollectionChildExists
from nexxT.core.Utils import assertMainThread, MethodInvoker
import nexxT

logger = logging.getLogger(__name__)

class FilterMockup(FilterEnvironment):
    """
    The filter mockup class caches the port information of a filter without having the filter loaded and running
    all the time.
    """
    def __init__(self, library, factoryFunction, propertyCollection, graph):
        super().__init__(None, None, propertyCollection, self)
        assertMainThread()
        self._library = library
        self._graph = graph
        self._factoryFunction = factoryFunction
        self._propertyCollectionImpl = propertyCollection
        self._pluginClass = None
        self._createFilterAndUpdatePending = None
        try:
            # add also a child collection for the nexxT internals
            pc = PropertyCollectionImpl("_nexxT", propertyCollection)
        except PropertyCollectionChildExists:
            pc = propertyCollection.getChildCollection("_nexxT")
        pc.defineProperty("thread", "main", "The thread this filter belongs to.")

    def getGraph(self):
        """
        Returns the FilterGraph instance this mockup belongs to
        :return: FilterGraph instance
        """
        return self._graph

    def getLibrary(self):
        """
        Returns the library of this filter.
        :return: library as given to constructor
        """
        return self._library

    def getFactoryFunction(self):
        """
        Returns the factory function of this filter.
        :return: factory function as given to constructor
        """
        return self._factoryFunction

    def createFilterAndUpdate(self, immediate=True):
        """
        Creates the filter, performs init() operation and updates the port information.
        :return: None
        """
        if immediate:
            self._createFilterAndUpdate()
            self._createFilterAndUpdatePending = None
        elif self._createFilterAndUpdatePending is None:
            self._createFilterAndUpdatePending = MethodInvoker(dict(object=self, method="_createFilterAndUpdate"),
                                                               Qt.QueuedConnection)

    def _createFilterAndUpdate(self):
        self._createFilterAndUpdatePending = None
        assertMainThread()
        self._propertyCollectionImpl.markAllUnused()
        with FilterEnvironment(self._library, self._factoryFunction, self._propertyCollectionImpl, self) as tempEnv:
            for p in self._ports:
                if p.dynamic():
                    tempEnv.addPort(p.clone(tempEnv))
            tempEnv.init()
            self._propertyCollectionImpl.deleteUnused()
            self.updatePortInformation(tempEnv)
            self._pluginClass = tempEnv.getPlugin().__class__
            if nexxT.useCImpl:
                # pylint: disable=import-outside-toplevel
                # don't want to pollute global namespace with this; need to update the
                # the class if it is a wrapped shared pointer.
                import cnexxT
                if self._pluginClass is cnexxT.__dict__["QSharedPointer<nexxT::Filter >"]:
                    self._pluginClass = tempEnv.getPlugin().data().__class__

    def createFilter(self):
        """
        Creates the filter for real usage. State is CONSTRUCTED. This function is thread safe and can be called
        from multiple threads.
        :return: None
        """
        # called from threads
        res = FilterEnvironment(self._library, self._factoryFunction, self._propertyCollectionImpl)
        with QMutexLocker(self._portMutex):
            for p in self._ports:
                if p.dynamic():
                    res.addPort(p.clone(res))
            return res

    def addDynamicPort(self, portname, factory):
        """
        Add a dynamic port to the filter and re-acquire the port information.
        :param portname: name of the new port
        :param factory: either InputPort or OutputPort
        :return: None
        """
        assertMainThread()
        if factory is InputPortInterface:
            factory = InputPort
        if factory is OutputPortInterface:
            # if InputPort or OutputPort classes are given as argument, make sure to actually use the factories
            factory = OutputPort
        self.addPort(factory(True, portname, self))
        self.createFilterAndUpdate(False)

    def renameDynamicPort(self, oldPortName, newPortName, factory):
        """
        Rename a dynamic port of the filter.
        :param oldPortName: original name of the port
        :param newPortName: new name of the port
        :param factory: either InputPort or OutputPort
        :return: None
        """
        assertMainThread()
        found = False
        try:
            self.getPort(newPortName, factory)
            found = True
        except PortNotFoundError:
            pass
        if found:
            raise PortExistsError("<unknown>", newPortName)
        p = self.getPort(oldPortName, factory)
        p.setName(newPortName)
        self.createFilterAndUpdate(False)

    def deleteDynamicPort(self, portname, factory):
        """
        Remove a dynamic port of the filter.
        :param portname: name of the dynamic port
        :param factory: either InputPort or OutputPort
        :return:
        """
        assertMainThread()
        p = self.getPort(portname, factory)
        self.removePort(p)
        self.createFilterAndUpdate(False)

    def getPropertyCollectionImpl(self):
        """
        return the PropertyCollectionImpl instance associated with this filter
        :return: PropertyCollectionImpl instance
        """
        return self._propertyCollectionImpl

    def getPluginClass(self):
        """
        Returns the class of the plugin.
        :return: python class information for use with issubclass(...)
        """
        return self._pluginClass
