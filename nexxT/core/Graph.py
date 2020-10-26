# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the class FilterGraph
"""

import logging
from PySide2.QtCore import Signal, Slot
from nexxT.interface import InputPortInterface, OutputPortInterface
from nexxT.core.FilterMockup import FilterMockup
from nexxT.core.BaseGraph import BaseGraph
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.Utils import assertMainThread, handleException
from nexxT.core.Exceptions import NexTRuntimeError, PropertyCollectionChildNotFound, CompositeRecursion

logger = logging.getLogger(__name__)

class FilterGraph(BaseGraph):
    """
    This class defines the filter graph. It adds dynamic (user-defined) ports top the BaseGraph class and connects
    the graph with FilterMockup instances. It additionally manages PropertyCollections of the related filters.
    """
    dynInputPortAdded = Signal(str, str)
    dynInputPortRenamed = Signal(str, str, str)
    dynInputPortDeleted = Signal(str, str)
    dynOutputPortAdded = Signal(str, str)
    dynOutputPortRenamed = Signal(str, str, str)
    dynOutputPortDeleted = Signal(str, str)

    def __init__(self, subConfig):
        super().__init__()
        assertMainThread()
        self._parent = subConfig
        self._filters = {}
        self._properties = subConfig.getPropertyCollection()
        self.nodeDeleted.connect(self.onNodeDeleted)
        self.nodeRenamed.connect(self.onNodeRename)

    #def dump(self):
    #    for name in self._filters:
    #        logger.internal("Dump %s:\n %s", name, shiboken2.dump(self._filters[name]))

    def getSubConfig(self):
        """
        returns this graph's parent.
        :return: a SubConfiguration instance
        """
        return self._parent

    def nodeName(self, filterEnv):
        """
        Given a FilterEnvironment instance, get the corresponding unique name.
        :param filterEnv: a FilterEnvironment instance
        :return: the name as string
        """
        names = [n for n in self._filters if self._filters[n] is filterEnv]
        if len(names) != 1:
            raise NexTRuntimeError("Lookup of filter failed; either non-unique or not in graph.")
        return names[0]

    def cleanup(self):
        """
        cleanup function
        :return:
        """
        self._filters.clear()
        self.dirtyChanged.emit()

    # pylint: disable=arguments-differ
    # different arguments to BaseGraph are wanted in this case
    # BaseGraph gets the node name, this method gets arguments
    # for constructing a filter
    @Slot(str, str, object)
    def addNode(self, library, factoryFunction, suggestedName=None):
        """
        Add a node to the graph, given a library and a factory function for instantiating the plugin.
        :param library: definition file of the plugin
        :param factoryFunction: function for instantiating the plugin
        :param suggestedName: name suggested by used (if None, factoryFunction is used)
        :return: the name of the created node
        """
        assertMainThread()
        if suggestedName is None:
            suggestedName = factoryFunction
        name = super().uniqueNodeName(suggestedName)
        try:
            propColl = self._properties.getChildCollection(name)
        except PropertyCollectionChildNotFound:
            propColl = PropertyCollectionImpl(name, self._properties)
        propColl.propertyChanged.connect(self.setDirty)
        filterMockup = FilterMockup(library, factoryFunction, propColl, self)
        filterMockup.createFilterAndUpdate()
        self._filters[name] = filterMockup
        assert super().addNode(name) == name
        if factoryFunction == "compositeNode" and hasattr(library, "checkRecursion"):
            try:
                library.checkRecursion()
            except CompositeRecursion as e:
                self.deleteNode(name)
                raise e
        for port in filterMockup.getStaticInputPorts():
            self.addInputPort(name, port.name())
        for port in filterMockup.getStaticOutputPorts():
            self.addOutputPort(name, port.name())
        filterMockup.portInformationUpdated.connect(self.portInformationUpdated)
        self.dirtyChanged.emit()
        return name
    # pylint: enable=arguments-differ

    @Slot()
    def setDirty(self):
        """
        Notification of dirty state (called from propertycollections.
        :return:
        """
        self.dirtyChanged.emit()

    def getMockup(self, name):
        """
        Get the mockup related to the given filter.
        :param name: the node name
        :return: FilterMockup instance
        """
        assertMainThread()
        return self._filters[name]

    @Slot(str)
    def onNodeDeleted(self, name):
        """
        Delete corresponding FilterMockup and PropertyCollection instances.
        :param name: the node name
        :return: None
        """
        assertMainThread()
        logger.debug("onNodeDeleted: Deleted filter %s", name)
        self._properties.deleteChild(name)
        del self._filters[name]

    @Slot(str, str)
    def onNodeRename(self, oldName, newName):
        """
        Renames the corresponding filter of the node.
        :param oldName: the old node name
        :param newName: the new node name
        :return: None
        """
        assertMainThread()
        f = self._filters[oldName]
        del self._filters[oldName]
        self._filters[newName] = f
        self._properties.renameChild(oldName, newName)

    @Slot(str, str)
    def addDynamicInputPort(self, node, port):
        """
        Add a dynamic input port to the referenced node.
        :param node: the affected node name
        :param port: the name of the new port
        :return: None
        """
        assertMainThread()
        self._filters[node].addDynamicPort(port, InputPortInterface)
        self.dynInputPortAdded.emit(node, port)
        self.dirtyChanged.emit()

    @Slot(str, str, str)
    def renameDynamicInputPort(self, node, oldPort, newPort):
        """
        Rename a dynamic input port of a node.
        :param node: the affected node name
        :param oldPort: the original name of the port
        :param newPort: the new name of the port
        :return: None
        """
        assertMainThread()
        self.renameInputPort(node, oldPort, newPort)
        self._filters[node].renameDynamicPort(oldPort, newPort, InputPortInterface)
        self.dynInputPortRenamed.emit(node, oldPort, newPort)
        self.dirtyChanged.emit()

    @Slot(str, str)
    def deleteDynamicInputPort(self, node, port):
        """
        Remove a dynamic input port of a node.
        :param node: the affected node name
        :param port: the name of the port to be deleted
        :return: None
        """
        assertMainThread()
        self._filters[node].deleteDynamicPort(port, InputPortInterface)
        self.dynInputPortDeleted.emit(node, port)
        self.dirtyChanged.emit()

    @Slot(str, str)
    def addDynamicOutputPort(self, node, port):
        """
        Add a dynamic output port to the referenced node.
        :param node: the name of the affected node
        :param port: the name of the new port
        :return: None
        """
        assertMainThread()
        self._filters[node].addDynamicPort(port, OutputPortInterface)
        self.dynOutputPortAdded.emit(node, port)
        self.dirtyChanged.emit()

    @Slot(str, str, str)
    def renameDynamicOutputPort(self, node, oldPort, newPort):
        """
        Rename a dynamic output port of a node.
        :param node: the affected node name
        :param oldPort: the original name of the port
        :param newPort: the new name of the port
        :return: None
        """
        assertMainThread()
        self.renameOutputPort(node, oldPort, newPort)
        self._filters[node].renameDynamicPort(oldPort, newPort, OutputPortInterface)
        self.dynOutputPortRenamed.emit(node, oldPort, newPort)
        self.dirtyChanged.emit()

    @Slot(str, str)
    def deleteDynamicOutputPort(self, node, port):
        """
        Remove a dynamic output port of a node.
        :param node: the affected node name
        :param port: the name of the port to be deleted
        :return: None
        """
        assertMainThread()
        self._filters[node].deleteDynamicPort(port, OutputPortInterface)
        self.dynOutputPortDeleted.emit(node, port)
        self.dirtyChanged.emit()

    @Slot(object, object)
    def portInformationUpdated(self, oldIn, oldOut):
        """
        Called after the port information of a filter has changed. Makes sure that ports are deleted and
        added in the graph as necessary.
        :param oldIn: InputPort instances with old input ports
        :param oldOut: OutputPort instances with old output ports
        :return:
        """
        self._portInformationUpdated(oldIn, oldOut)

    @handleException
    def _portInformationUpdated(self, oldIn, oldOut):
        # pylint: disable=too-many-locals
        # cleaning up seems not to be an easy option here
        assertMainThread()
        def _nodeName():
            fe = self.sender()
            name = [k for k in self._filters if self._filters[k] is fe]
            if len(name) != 1:
                raise RuntimeError("Unexpected list length of matched filters: %s" % (name))
            return name[0]

        name = _nodeName()

        for portskey, oldPorts, getPorts, deletePort, deleteDynPort, addPort in [
                ("inports", oldIn, self._filters[name].getAllInputPorts, self.deleteInputPort,
                 self.deleteDynamicInputPort, self.addInputPort),
                ("outports", oldOut, self._filters[name].getAllOutputPorts, self.deleteOutputPort,
                 self.deleteDynamicOutputPort, self.addOutputPort)]:

            stalePorts = set(self._nodes[name][portskey])
            allPorts = set(self._nodes[name][portskey])
            newInputPorts = []
            # iterate over new ports
            for np in getPorts():
                # check if port is already existing in configuration
                if np.name() in stalePorts:
                    stalePorts.remove(np.name())
                if not np.name() in allPorts:
                    newInputPorts.append(np)
            for p in stalePorts:
                if len([op for op in oldPorts if (op.name() == p and op.dynamic())]) > 0:
                    deleteDynPort(name, p)
                else:
                    deletePort(name, p)
            for np in newInputPorts:
                addPort(name, np.name())
