# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the class SubConfiguration
"""

import logging
from collections import OrderedDict
from PySide2.QtCore import QObject, Signal
from nexxT.core.Graph import FilterGraph
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.Exceptions import NexTInternalError, PropertyCollectionPropertyNotFound, PropertyCollectionChildNotFound
from nexxT.core.Utils import checkIdentifier

logger = logging.getLogger(__name__)

class SubConfiguration(QObject):
    """
    This class handles a sub-configuration of a nexxT application. Sub configs are either applications or
    SubGraphs (which behave like a filter).
    """
    nameChanged = Signal(object, str)

    def __init__(self, name, configuration):
        super().__init__()
        checkIdentifier(name)
        self._propertyCollection = PropertyCollectionImpl(name, configuration.propertyCollection())
        self._graph = FilterGraph(self)
        self._graph.dirtyChanged.connect(configuration.setDirty)
        self._config = configuration
        self._name = name

    #def dump(self):
    #    self._graph.dump()

    def cleanup(self):
        """
        Cleanup function
        :return:
        """
        self._graph.cleanup()

    def getName(self):
        """
        Get the name of this subconfiguration
        :return: string
        """
        return self._name

    def setName(self, name):
        """
        Sets the name of this subconfiguration
        :param name: new name (string)
        :return: None
        """
        if name != self._name:
            oldName = self._name
            self._name = name
            self._propertyCollection.setObjectName(name)
            self.nameChanged.emit(self, oldName)
            self._config.setDirty()

    def getPropertyCollection(self):
        """
        Get the property collection of this sub configuration
        :return: a PropertyCollectionImpl instance
        """
        return self._propertyCollection

    def getGraph(self):
        """
        Get the filter graph of this sub config
        :return: a FilterGraph instance
        """
        return self._graph

    def getConfiguration(self):
        """
        Get the corresponding nexxT configuration
        :return: a Configuration instance
        """
        return self._config

    @staticmethod
    def connectionStringToTuple(con):
        """
        Converts a connection string to a 4 tuple.
        :param con: a string containing a connection "name1.port1 -> name2.port2"
        :return: a 4-tuple ("name1", "port1", "name2", "port2")
        """
        f, t = con.split("->")
        fromNode, fromPort = f.strip().split(".")
        toNode, toPort = t.strip().split(".")
        return fromNode.strip(), fromPort.strip(), toNode.strip(), toPort.strip()

    @staticmethod
    def tupleToConnectionString(connection):
        """
        Converts a 4-tuple connection to a string.
        :param connection: a 4-tuple ("name1", "port1", "name2", "port2")
        :return: a string "name1.port1 -> name2.port2"
        """
        return "%s.%s -> %s.%s" % connection

    def load(self, cfg, compositeLookup):
        """
        load graph from config dictionary (inverse operation of save(...))
        :param cfg: dictionary loaded from json file
        :return: None
        """
        # apply subconfig gui state
        if "_guiState" in cfg and len(cfg["_guiState"]) > 0:
            guistateCC = self._propertyCollection.getChildCollection("_guiState")
            for k in cfg["_guiState"]:
                PropertyCollectionImpl(k, guistateCC, cfg["_guiState"][k])
        for n in cfg["nodes"]:
            if not n["library"].startswith("composite://"):
                p = PropertyCollectionImpl(n["name"], self._propertyCollection, n["properties"])
                # apply node gui state
                nextP = PropertyCollectionImpl("_nexxT", p, {"thread": n["thread"]})
                logger.debug("loading: subconfig %s / node %s -> thread: %s", self._name, n["name"], n["thread"])
                tmp = self._graph.addNode(n["library"], n["factoryFunction"], suggestedName=n["name"])
                if tmp != n["name"]:
                    raise NexTInternalError("addNode(...) has set unexpected name for node.")
            else:
                # composite node handling
                if n["library"] == "composite://port":
                    # the special nodes are already there, nothing to do here
                    pass
                elif n["library"] == "composite://ref":
                    name = n["factoryFunction"]
                    cf = compositeLookup(name)
                    tmp = self._graph.addNode(cf, "compositeNode", suggestedName=n["name"])
                    if tmp != n["name"]:
                        raise NexTInternalError("addNode(...) has set unexpected name for node.")
            for dip in n["dynamicInputPorts"]:
                self._graph.addDynamicInputPort(n["name"], dip)
            for dop in n["dynamicOutputPorts"]:
                self._graph.addDynamicOutputPort(n["name"], dop)
            # make sure that the filter is instantiated and the port information is updated immediately
            self._graph.getMockup(n["name"]).createFilterAndUpdate()
        for c in cfg["connections"]:
            contuple = self.connectionStringToTuple(c)
            self._graph.addConnection(*contuple)

    def save(self):
        """
        save graph to config dictionary (inverse operation of load(...))
        :return: dictionary which can be saved as json file
        """
        def adaptLibAndFactory(lib, factory):
            if not isinstance(lib, str):
                if factory in ["CompositeInputNode", "CompositeOutputNode"]:
                    ncfg["library"] = "composite://port"
                    ncfg["factoryFunction"] = factory[:-len("Node")]
                elif factory in ["compositeNode"]:
                    ncfg["library"] = "composite://ref"
                    ncfg["factoryFunction"] = lib.getName()
                else:
                    raise NexTInternalError("Unexpected factory function '%s'" % factory)
            else:
                ncfg["library"] = lib
                ncfg["factoryFunction"] = factory
            return lib, factory
        #self.dump()
        cfg = dict(name=self.getName())
        try:
            gs = self._propertyCollection.getChildCollection("_guiState")
            cfg["_guiState"] = {}
            for obj in gs.children():
                if isinstance(obj, PropertyCollectionImpl):
                    cfg["_guiState"][obj.objectName()] = obj.saveDict()
        except PropertyCollectionChildNotFound:
            pass
        cfg["nodes"] = []
        for name in self._graph.allNodes():
            ncfg = OrderedDict(name=name)
            mockup = self._graph.getMockup(name)
            lib = mockup.getLibrary()
            factory = mockup.getFactoryFunction()
            lib, factory = adaptLibAndFactory(lib, factory)
            ncfg["dynamicInputPorts"] = []
            ncfg["staticInputPorts"] = []
            ncfg["dynamicOutputPorts"] = []
            ncfg["staticOutputPorts"] = []
            for ip in mockup.getDynamicInputPorts():
                ncfg["dynamicInputPorts"].append(ip.name())
            for ip in self._graph.allInputPorts(name):
                if not ip in ncfg["dynamicInputPorts"]:
                    ncfg["staticInputPorts"].append(ip)
            for op in mockup.getDynamicOutputPorts():
                ncfg["dynamicOutputPorts"].append(op.name())
            for op in self._graph.allOutputPorts(name):
                if not op in ncfg["dynamicOutputPorts"]:
                    ncfg["staticOutputPorts"].append(op)
            p = self._propertyCollection.getChildCollection(name)
            try:
                ncfg["thread"] = p.getChildCollection("_nexxT").getProperty("thread")
                logger.debug("saving: subconfig %s / node %s -> thread: %s", self._name, name, ncfg["thread"])
            except PropertyCollectionChildNotFound:
                pass
            except PropertyCollectionPropertyNotFound:
                pass
            ncfg["properties"] = p.saveDict()
            cfg["nodes"].append(ncfg)
        cfg["connections"] = [self.tupleToConnectionString(c) for c in self._graph.allConnections()]
        return cfg

    @staticmethod
    def getThreadSet(item):
        """
        Returns all threads (as strings) used by the given filter mockup. Usually this is only one, but
        for composite filters, this function performs a recursive lookup.
        :param mockup:
        :return: set of strings
        """
        # pylint: disable=import-outside-toplevel
        # needed to avoid recursive import
        from nexxT.core.CompositeFilter import CompositeFilter
        from nexxT.core.FilterMockup import FilterMockup
        if isinstance(item, FilterMockup):
            mockup = item
            if (issubclass(mockup.getPluginClass(), CompositeFilter.CompositeInputNode) or
                    issubclass(mockup.getPluginClass(), CompositeFilter.CompositeOutputNode)):
                return set()
            if not issubclass(mockup.getPluginClass(), CompositeFilter.CompositeNode):
                pc = mockup.propertyCollection().getChildCollection("_nexxT")
                thread = pc.getProperty("thread")
                return set([thread])
            g = mockup.getLibrary().getGraph()
            res = set()
            for n in g.allNodes():
                res = res.union(SubConfiguration.getThreadSet(g.getMockup(n)))
            return res
        if isinstance(item, SubConfiguration):
            g = item.getGraph()
            res = set()
            for n in g.allNodes():
                res = res.union(SubConfiguration.getThreadSet(g.getMockup(n)))
            return res
        raise RuntimeError("Don't know how to handle instances of this type.")
