# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the class BaseGraph
"""

from collections import OrderedDict
from PySide2.QtCore import QObject, Signal, Slot
from nexxT.core.Utils import assertMainThread
from nexxT.core.Exceptions import (NodeExistsError, NodeNotFoundError, PortExistsError, PortNotFoundError,
                                   ConnectionExistsError, ConnectionNotFound, NodeProtectedError)

class BaseGraph(QObject):
    """
    This class defines a graph where the nodes can have input and output ports and
    these ports can be connected together. All operations are performed with QT
    signals and slots.
    """
    nodeAdded = Signal(str)
    nodeRenamed = Signal(str, str)
    nodeDeleted = Signal(str)
    inPortAdded = Signal(str, str)
    inPortRenamed = Signal(str, str, str)
    inPortDeleted = Signal(str, str)
    outPortAdded = Signal(str, str)
    outPortRenamed = Signal(str, str, str)
    outPortDeleted = Signal(str, str)
    connectionAdded = Signal(str, str, str, str)
    connectionDeleted = Signal(str, str, str, str)
    dirtyChanged = Signal()

    def __init__(self):
        assertMainThread()
        super().__init__()
        self._protected = set()
        self._nodes = OrderedDict()
        self._connections = []

    def uniqueNodeName(self, nodeName):
        """
        Given a suggested node name, return a unique node name based on this name.
        :param nodeName: a node name string
        :return: a unique node name string
        """
        assertMainThread()
        if not nodeName in self._nodes:
            return nodeName
        t = 2
        while "%s%d" % (nodeName, t) in self._nodes:
            t += 1
        return "%s%d" % (nodeName, t)

    def protect(self, name):
        """
        Adds node <name> to protected set, which prevents renaming and deletion
        :param name:
        :return: None
        """
        if name not in self._nodes:
            raise NodeNotFoundError(name)
        self._protected.add(name)

    @Slot(str)
    def addNode(self, name):
        """
        Add a new node to the graph.
        :param name: the name of the new node
        :return: the name of the added node
        """
        assertMainThread()
        if name in self._nodes:
            raise NodeExistsError(name)
        self._nodes[name] = dict(inports=[], outports=[])
        self.nodeAdded.emit(name)
        self.dirtyChanged.emit()
        return name

    @Slot(str, str)
    def renameNode(self, oldName, newName):
        """
        Rename a node in the graph (connections will be adapted as well)
        :param oldName: the original name of the node
        :param newName: the new name of the node
        :return: None
        """
        assertMainThread()
        if not oldName in self._nodes:
            raise NodeNotFoundError(oldName)
        if newName in self._nodes:
            raise NodeExistsError(newName)
        if oldName in self._protected:
            raise NodeProtectedError(oldName)
        of = self._nodes[oldName]
        del self._nodes[oldName]
        self._nodes[newName] = of
        for i in range(len(self._connections)):
            c = self._connections[i]
            if c[0] == oldName:
                c = (newName, c[1], c[2], c[3])
            if c[2] == oldName:
                c = (c[0], c[1], newName, c[3])
            self._connections[i] = c
        self.nodeRenamed.emit(oldName, newName)
        self.dirtyChanged.emit()

    @Slot(str)
    def deleteNode(self, name):
        """
        Delete a node in the graph (connections are deleted as well)
        :param name: the name of the node to be deleted
        :return: None
        """
        assertMainThread()
        if not name in self._nodes:
            raise NodeNotFoundError(name)
        if name in self._protected:
            raise NodeProtectedError(name)
        for inport in self._nodes[name]["inports"][::-1]:
            self.deleteInputPort(name, inport)
        for outport in self._nodes[name]["outports"][::-1]:
            self.deleteOutputPort(name, outport)
        del self._nodes[name]
        self.nodeDeleted.emit(name)
        self.dirtyChanged.emit()

    @Slot(str, str, str, str)
    def addConnection(self, nodeNameFrom, portNameFrom, nodeNameTo, portNameTo):
        """
        Add a connection to the graph.
        :param nodeNameFrom: the source node
        :param portNameFrom: the source port
        :param nodeNameTo: the target node
        :param portNameTo: the target port
        :return: None
        """
        assertMainThread()
        if not nodeNameFrom in self._nodes:
            raise NodeNotFoundError(nodeNameFrom)
        if not nodeNameTo in self._nodes:
            raise NodeNotFoundError(nodeNameTo)
        if not portNameFrom in self._nodes[nodeNameFrom]["outports"]:
            raise PortNotFoundError(nodeNameFrom, portNameFrom, "Output")
        if not portNameTo in self._nodes[nodeNameTo]["inports"]:
            raise PortNotFoundError(nodeNameTo, portNameTo, "Input")
        if (nodeNameFrom, portNameFrom, nodeNameTo, portNameTo) in self._connections:
            raise ConnectionExistsError(nodeNameFrom, portNameFrom, nodeNameTo, portNameTo)
        self._connections.append((nodeNameFrom, portNameFrom, nodeNameTo, portNameTo))
        self.connectionAdded.emit(nodeNameFrom, portNameFrom, nodeNameTo, portNameTo)
        self.dirtyChanged.emit()

    @Slot(str, str, str, str)
    def deleteConnection(self, nodeNameFrom, portNameFrom, nodeNameTo, portNameTo):
        """
        Remove a connection from the graph
        :param nodeNameFrom: the source node
        :param portNameFrom: the source port
        :param nodeNameTo: the target node
        :param portNameTo: the target port
        :return: None
        """
        assertMainThread()
        if (nodeNameFrom, portNameFrom, nodeNameTo, portNameTo) not in self._connections:
            raise ConnectionNotFound(nodeNameFrom, portNameFrom, nodeNameTo, portNameTo)
        self._connections.remove((nodeNameFrom, portNameFrom, nodeNameTo, portNameTo))
        self.connectionDeleted.emit(nodeNameFrom, portNameFrom, nodeNameTo, portNameTo)
        self.dirtyChanged.emit()

    @Slot(str, str)
    def addInputPort(self, node, portName):
        """
        Add an input port to the node.
        :param node: the name of the node
        :param portName: the name of the new port
        :return: None
        """
        assertMainThread()
        if not node in self._nodes:
            raise NodeNotFoundError(node)
        if portName in self._nodes[node]["inports"]:
            raise PortExistsError(node, portName)
        self._nodes[node]["inports"].append(portName)
        self.inPortAdded.emit(node, portName)

    @Slot(str, str)
    def deleteInputPort(self, node, portName):
        """
        Remove an input port from a node (connections will be deleted as required)
        :param node: the node name
        :param portName: the port name to be deleted
        :return: None
        """
        assertMainThread()
        if not node in self._nodes:
            raise NodeNotFoundError(node)
        if not portName in self._nodes[node]["inports"]:
            raise PortNotFoundError(node, portName)
        toDel = []
        for i in range(len(self._connections)):
            fromNode, fromPort, toNode, toPort = self._connections[i]
            if (toNode == node and toPort == portName):
                toDel.append((fromNode, fromPort, toNode, toPort))
        for c in toDel:
            self.deleteConnection(*c)
        self._nodes[node]["inports"].remove(portName)
        self.inPortDeleted.emit(node, portName)

    @Slot(str, str, str)
    def renameInputPort(self, node, oldPortName, newPortName):
        """
        Rename an input port of a node (connections will be renamed as needed)
        :param node: the name of the node
        :param oldPortName: the original port name
        :param newPortName: the new port name
        :return: None
        """
        assertMainThread()
        if not node in self._nodes:
            raise NodeNotFoundError(node)
        if not oldPortName in self._nodes[node]["inports"]:
            if newPortName in self._nodes[node]["inports"]:
                # already renamed.
                return
            raise PortNotFoundError(node, oldPortName)
        if newPortName in self._nodes[node]["inports"]:
            raise PortExistsError(node, newPortName)
        idx = self._nodes[node]["inports"].index(oldPortName)
        self._nodes[node]["inports"][idx] = newPortName
        for i in range(len(self._connections)):
            fromNode, fromPort, toNode, toPort = self._connections[i]
            if (toNode == node and toPort == oldPortName):
                toPort = newPortName
            self._connections[i] = (fromNode, fromPort, toNode, toPort)
        self.inPortRenamed.emit(node, oldPortName, newPortName)

    @Slot(str, str)
    def addOutputPort(self, node, portName):
        """
        Add an output port to a node
        :param node: the node name
        :param portName: the name of the new port
        :return: None
        """
        assertMainThread()
        if not node in self._nodes:
            raise NodeNotFoundError(node)
        if portName in self._nodes[node]["outports"]:
            raise PortExistsError(node, portName)
        self._nodes[node]["outports"].append(portName)
        self.outPortAdded.emit(node, portName)

    @Slot(str, str)
    def deleteOutputPort(self, node, portName):
        """
        Remove an output port from a node (connections will be deleted as needed)
        :param node: the node name
        :param portName: the port name to be deleted
        :return: None
        """
        assertMainThread()
        if not node in self._nodes:
            raise NodeNotFoundError(node)
        if not portName in self._nodes[node]["outports"]:
            raise PortNotFoundError(node, portName)
        toDel = []
        for i in range(len(self._connections)):
            fromNode, fromPort, toNode, toPort = self._connections[i]
            if (fromNode == node and fromPort == portName):
                toDel.append((fromNode, fromPort, toNode, toPort))
        for c in toDel:
            self.deleteConnection(*c)
        self._nodes[node]["outports"].remove(portName)
        self.outPortDeleted.emit(node, portName)

    @Slot(str, str, str)
    def renameOutputPort(self, node, oldPortName, newPortName):
        """
        Rename an output port of a node (connections will be renamed as needed)
        :param node: the node name
        :param oldPortName: the original port name
        :param newPortName: the new port name
        :return: None
        """
        assertMainThread()
        if not node in self._nodes:
            raise NodeNotFoundError(node)
        if not oldPortName in self._nodes[node]["outports"]:
            if newPortName in self._nodes[node]["outports"]:
                # already renamed.
                return
            raise PortNotFoundError(node, oldPortName)
        if newPortName in self._nodes[node]["outports"]:
            raise PortExistsError(node, newPortName)
        idx = self._nodes[node]["outports"].index(oldPortName)
        self._nodes[node]["outports"][idx] = newPortName
        for i in range(len(self._connections)):
            fromNode, fromPort, toNode, toPort = self._connections[i]
            if (fromNode == node and fromPort == oldPortName):
                fromPort = newPortName
            self._connections[i] = (fromNode, fromPort, toNode, toPort)
        self.outPortRenamed.emit(node, oldPortName, newPortName)

    def allNodes(self):
        """
        Return all node names.
        :return: list of nodes
        """
        assertMainThread()
        return list(self._nodes.keys())

    def allConnections(self):
        """
        Return all connections
        :return: list of 4 tuples of strings (nodeFrom, portFrom, nodeTo, portTo)
        """
        assertMainThread()
        return self._connections

    def allConnectionsToInputPort(self, toNode, toPort):
        """
        Return all connections to the specified port.
        :param toNode: name of node
        :param toPort: name of port
        :return: a list of 4 tuples of strings (nodeFrom, portFrom, nodeTo, portTo)
        """
        return [(a, b, c, d) for a, b, c, d, in self._connections if (c == toNode and d == toPort)]

    def allConnectionsFromOutputPort(self, fromNode, fromPort):
        """
        Return all connections from the specified port.
        :param fromNode: name of node
        :param fromPort: name of port
        :return: a list of 4 tuples of strings (nodeFrom, portFrom, nodeTo, portTo)
        """
        return [(a, b, c, d) for a, b, c, d, in self._connections if (a == fromNode and b == fromPort)]

    def allInputPorts(self, node):
        """
        Return all input port names of the node.
        :param node: node name
        :return: list of port names
        """
        if not node in self._nodes:
            raise NodeNotFoundError(node)
        return self._nodes[node]["inports"]

    def allOutputPorts(self, node):
        """
        Return all output port names of the node.
        :param node: node name
        :return: list of port names
        """
        if not node in self._nodes:
            raise NodeNotFoundError(node)
        return self._nodes[node]["outports"]
