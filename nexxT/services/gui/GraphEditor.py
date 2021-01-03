# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the graph editor GUI service of the nexxT service.
"""

import logging
import platform
import os.path
import pkg_resources
from PySide2.QtWidgets import (QGraphicsScene, QGraphicsItemGroup, QGraphicsSimpleTextItem,
                               QGraphicsPathItem, QGraphicsItem, QMenu, QAction, QInputDialog, QMessageBox,
                               QGraphicsLineItem, QFileDialog, QDialog, QGridLayout, QCheckBox, QVBoxLayout, QGroupBox,
                               QDialogButtonBox, QGraphicsView, QStyle, QStyleOptionGraphicsItem)
from PySide2.QtGui import QBrush, QPen, QColor, QPainterPath, QImage
from PySide2.QtCore import QPointF, Signal, QObject, QRectF, QSizeF, Qt
from nexxT.core.BaseGraph import BaseGraph
from nexxT.core.Graph import FilterGraph
from nexxT.core.SubConfiguration import SubConfiguration
from nexxT.core.CompositeFilter import CompositeFilter
from nexxT.core.PluginManager import PluginManager
from nexxT.core.Utils import checkIdentifier, handleException, ThreadToColor, assertMainThread
from nexxT.core.Exceptions import InvalidIdentifierException
from nexxT.interface import InputPortInterface, OutputPortInterface
from nexxT.services.gui import GraphLayering

logger = logging.getLogger(__name__)

class MyGraphicsPathItem(QGraphicsPathItem, QObject):
    """
    Little subclass for receiving hover events and scene position changes outside the items
    """
    hoverEnter = Signal()
    hoverLeave = Signal()
    scenePosChanged = Signal(QPointF)

    def __init__(self, *args, **kw):
        QGraphicsPathItem.__init__(self, *args, **kw)
        QObject.__init__(self)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event):
        """
        emit corresponding singal

        :param event: the qt event
        :return:
        """
        self.hoverEnter.emit()
        return super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """
        emit corresponding signal

        :param event: the qt event
        :return:
        """
        self.hoverLeave.emit()
        return super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """
        in case of scene position changes, emit the corresponding signal

        :param change: what has changed
        :param value: the new value
        :return:
        """
        if change == QGraphicsItem.ItemScenePositionHasChanged:
            self.scenePosChanged.emit(value)
        return super().itemChange(change, value)

class MySimpleTextItem(QGraphicsSimpleTextItem):
    """
    QGraphicsSimpleTextItem with a background brush
    """
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.brush = QBrush()

    def setBackgroundBrush(self, brush):
        """
        set the background brush

        :param brush: a QBrush instance
        :return:
        """
        self.brush = brush

    def paint(self, painter, option, widget):
        """
        first paint the background and afterwards use standard paint method

        :param painter: a QPainter instance
        :param option: unused
        :param widget: unused
        :return:
        """
        b = painter.brush()
        p = painter.pen()
        painter.setBrush(self.brush)
        painter.setPen(QPen(QColor(0, 0, 0, 0)))
        painter.drawRect(self.boundingRect())
        painter.setBrush(b)
        painter.setPen(p)
        super().paint(painter, option, widget)

class BaseGraphScene(QGraphicsScene):
    """
    Basic graph display and manipulation scene. Generic base class intended to be overwritten.
    """

    connectionAddRequest = Signal(str, str, str, str)

    STYLE_ROLE_SIZE = 0     # expects a QSizeF instance
    STYLE_ROLE_PEN = 1      # expects a Pen instance
    STYLE_ROLE_BRUSH = 2    # expects a Brush instance
    STYLE_ROLE_RRRADIUS = 3 # expects a float, the radius of rounded rectangles
    STYLE_ROLE_VSPACING = 4 # expects a float
    STYLE_ROLE_HSPACING = 5 # expects a float
    STYLE_ROLE_TEXT_BRUSH = 6 # expects a brush, will be used as background of fonts

    KEY_ITEM = 0

    class NodeItem(QGraphicsItemGroup):
        """
        An item which represents a node in the graph. The item group is also used for grouping the port items.
        """
        @staticmethod
        def itemTypeName():
            """
            return a class identification name.

            :return:
            """
            return "node"

        def __init__(self, name):
            super().__init__(None)
            self.name = name
            self.inPortItems = []
            self.outPortItems = []
            self.setHandlesChildEvents(False)
            self.setFlag(QGraphicsItem.ItemClipsToShape, True)
            self.setFlag(QGraphicsItem.ItemClipsChildrenToShape, True)
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.hovered = False
            self.sync()

        def getInPortItem(self, name):
            """
            Searches for the input port named by name

            :param name: a string instance
            :return: a PortItem instance
            """
            found = [i for i in self.inPortItems if i.name == name]
            if len(found) == 1:
                return found[0]
            return None

        def getOutPortItem(self, name):
            """
            Searches for the output port named by name

            :param name: a string instance
            :return: a PortItem instance
            """
            found = [i for i in self.outPortItems if i.name == name]
            if len(found) == 1:
                return found[0]
            return None

        def addInPortItem(self, name):
            """
            Adds a new input port to the node

            :param name: the port name
            :return:
            """
            assert self.getInPortItem(name) is None
            portItem = BaseGraphScene.PortItem(name, self)
            self.inPortItems.append(portItem)
            self.sync()

        def addOutPortItem(self, name):
            """
            Adds a new output port to the node

            :param name: the port name
            :return:
            """
            assert self.getOutPortItem(name) is None
            portItem = BaseGraphScene.PortItem(name, self)
            self.outPortItems.append(portItem)
            self.sync()

        def nodeHeight(self):
            """
            :return: the node height in pixels including spacing.
            """
            style = BaseGraphScene.getData if self.scene() is None else self.scene().getData
            size = style(self, BaseGraphScene.STYLE_ROLE_SIZE)
            vspacing = style(self, BaseGraphScene.STYLE_ROLE_VSPACING)
            inPortHeight = sum([style(ip, BaseGraphScene.STYLE_ROLE_VSPACING) for ip in self.inPortItems])
            outPortHeight = sum([style(op, BaseGraphScene.STYLE_ROLE_VSPACING) for op in self.outPortItems])
            nodeHeight = size.height() + max(inPortHeight, outPortHeight)
            return nodeHeight+2*vspacing

        def nodeWidth(self):
            """
            :return: the node width in pixels including spacing.
            """
            style = BaseGraphScene.getData if self.scene() is None else self.scene().getData
            size = style(self, BaseGraphScene.STYLE_ROLE_SIZE)
            hspacing = style(self, BaseGraphScene.STYLE_ROLE_HSPACING)
            return size.width() + 2*hspacing

        def sync(self):
            """
            synchronize the item with the model (also the ports)

            :return:
            """
            self.prepareGeometryChange()
            nodePP = QPainterPath()
            style = BaseGraphScene.getData if self.scene() is None else self.scene().getData

            size = style(self, BaseGraphScene.STYLE_ROLE_SIZE)
            vspacing = style(self, BaseGraphScene.STYLE_ROLE_VSPACING)
            hspacing = style(self, BaseGraphScene.STYLE_ROLE_HSPACING)
            radius = style(self, BaseGraphScene.STYLE_ROLE_RRRADIUS)

            inPortHeight = sum([style(ip, BaseGraphScene.STYLE_ROLE_VSPACING) for ip in self.inPortItems])
            outPortHeight = sum([style(op, BaseGraphScene.STYLE_ROLE_VSPACING) for op in self.outPortItems])
            nodeHeight = size.height() + max(inPortHeight, outPortHeight)
            nodePP.addRoundedRect(hspacing, vspacing, size.width(), nodeHeight, radius, radius)
            if not hasattr(self, "nodeGrItem"):
                self.nodeGrItem = MyGraphicsPathItem(nodePP, None)
                self.nodeTextItem = MySimpleTextItem()
                self.nodeGrItem.hoverEnter.connect(self.hoverEnter)
                self.nodeGrItem.hoverLeave.connect(self.hoverLeave)
                self.nodeGrItem.setData(BaseGraphScene.KEY_ITEM, self)
            else:
                self.nodeGrItem.prepareGeometryChange()
                self.nodeTextItem.prepareGeometryChange()
                self.removeFromGroup(self.nodeGrItem)
                self.removeFromGroup(self.nodeTextItem)
            self.nodeGrItem.setPath(nodePP)
            self.nodeGrItem.setPen(style(self, BaseGraphScene.STYLE_ROLE_PEN))
            self.nodeGrItem.setBrush(style(self, BaseGraphScene.STYLE_ROLE_BRUSH))
            self.nodeTextItem.setText(self.name)
            self.nodeTextItem.setBackgroundBrush(style(self, BaseGraphScene.STYLE_ROLE_TEXT_BRUSH))
            self.addToGroup(self.nodeGrItem)
            self.addToGroup(self.nodeTextItem)
            br = self.nodeTextItem.boundingRect()
            self.nodeTextItem.setPos(hspacing + size.width()/2 - br.width()/2,
                                     vspacing + nodeHeight/2 - br.height()/2)

            y = vspacing + size.height()/2
            for p in self.inPortItems:
                y += style(p, BaseGraphScene.STYLE_ROLE_VSPACING)/2
                p.setPos(hspacing, y, False)
                y += style(p, BaseGraphScene.STYLE_ROLE_VSPACING)/2
                p.sync()

            y = vspacing + size.height()/2
            for p in self.outPortItems:
                y += style(p, BaseGraphScene.STYLE_ROLE_VSPACING)/2
                p.setPos(hspacing + size.width(), y, True)
                y += style(p, BaseGraphScene.STYLE_ROLE_VSPACING)/2
                p.sync()

        def hoverEnter(self):
            """
            Slot called on hover enter

            :return:
            """
            self.hovered = True
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
            self.sync()

        def hoverLeave(self):
            """
            Slot called on hover leave.

            :return:
            """
            self.hovered = False
            self.setFlag(QGraphicsItem.ItemIsMovable, False)
            self.sync()

        def itemChange(self, change, value):
            """
            overwritten from QGraphicsItem

            :param change: the thing that has changed
            :param value: the new value
            :return:
            """
            if change in [QGraphicsItem.ItemSelectedHasChanged]:
                self.sync()
            return super().itemChange(change, value)

        def paint(self, painter, option, widget):
            """
            Overwritten from base class to prevent drawing the selection rectangle

            :param painter: a QPainter instance
            :param option: a QStyleOptionGraphicsItem instance
            :param widget: a QWidget instance or None
            :return:
            """
            no = QStyleOptionGraphicsItem(option)
            no.state = no.state & ~QStyle.State_Selected
            super().paint(painter, no, widget)

    class PortItem:
        """
        This class represents a port in a node.
        """
        @staticmethod
        def itemTypeName():
            """
            Returns a class identification string.

            :return:
            """
            return "port"

        def __init__(self, name, nodeItem):
            self.name = name
            self.nodeItem = nodeItem
            self.connections = []
            self.hovered = False
            self.isOutput = False
            self.sync()

        def setPos(self, x, y, isOutput): # pylint: disable=invalid-name
            """
            Sets the position of this item to the given coordinates, assigns output / input property.

            :param x: the x coordinate
            :param y: the y coordinate
            :param isOutput: a boolean
            :return:
            """
            self.sync()
            self.isOutput = isOutput
            self.portGrItem.setPos(x, y)
            br = self.portTextItem.boundingRect()
            if isOutput:
                self.portTextItem.setPos(x+3, y - br.height())
            else:
                self.portTextItem.setPos(x-3-br.width(), y - br.height())

        def sync(self):
            """
            Synchronizes the item to the model.

            :return:
            """
            portPP = QPainterPath()
            style = BaseGraphScene.getData if self.nodeItem.scene() is None else self.nodeItem.scene().getData
            size = style(self, BaseGraphScene.STYLE_ROLE_SIZE)
            if self.isOutput:
                x = size.width()/2
            else:
                x = -size.width()/2
            portPP.addEllipse(QPointF(x, 0), size.width()/2, size.height()/2)
            if not hasattr(self, "portGrItem"):
                self.portGrItem = MyGraphicsPathItem(None)
                self.portTextItem = MySimpleTextItem(self.name, None)
                self.portGrItem.hoverEnter.connect(self.hoverEnter)
                self.portGrItem.hoverLeave.connect(self.hoverLeave)
                self.portGrItem.setData(BaseGraphScene.KEY_ITEM, self)
            else:
                self.portGrItem.prepareGeometryChange()
                self.portTextItem.prepareGeometryChange()
                self.nodeItem.removeFromGroup(self.portGrItem)
                self.nodeItem.removeFromGroup(self.portTextItem)
            self.portGrItem.setPath(portPP)
            self.portGrItem.setPen(style(self, BaseGraphScene.STYLE_ROLE_PEN))
            self.portGrItem.setBrush(style(self, BaseGraphScene.STYLE_ROLE_BRUSH))
            self.portGrItem.setFlag(QGraphicsItem.ItemSendsScenePositionChanges, True)
            self.portGrItem.scenePosChanged.connect(self.scenePosChanged)
            self.portGrItem.setZValue(1)
            self.nodeItem.addToGroup(self.portGrItem)
            self.nodeItem.addToGroup(self.portTextItem)
            self.portTextItem.setZValue(1)
            self.portTextItem.setBackgroundBrush(style(self, BaseGraphScene.STYLE_ROLE_TEXT_BRUSH))
            self.portTextItem.setText(self.name)
            for c in self.connections:
                c.sync()

        def hoverEnter(self):
            """
            Slot called on hover enter

            :return:
            """
            self.hovered = True
            self.sync()

        def hoverLeave(self):
            """
            Slot called on hover leave.

            :return:
            """
            self.hovered = False
            self.sync()

        def scenePosChanged(self, value): # pylint: disable=unused-argument
            """
            Slot called on scene position changes, need to synchronize connections.

            :param value:
            :return:
            """
            for c in self.connections:
                c.sync()

        def remove(self):
            """
            Removes this port from its item group.

            :return:
            """
            if hasattr(self, "portGrItem"):
                self.nodeItem.removeFromGroup(self.portGrItem)
                self.nodeItem.removeFromGroup(self.portTextItem)
                self.portGrItem.scene().removeItem(self.portGrItem)
                self.portTextItem.scene().removeItem(self.portTextItem)
            if self in self.nodeItem.outPortItems:
                self.nodeItem.outPortItems.remove(self)
            if self in self.nodeItem.inPortItems:
                self.nodeItem.inPortItems.remove(self)

    class ConnectionItem(QGraphicsPathItem):
        """
        This item corresponds with a connection between an output and an input port.
        """
        @staticmethod
        def itemTypeName():
            """
            Returns an identificytion string.

            :return:
            """
            return "connection"

        def __init__(self, portFrom, portTo):
            super().__init__()
            self.portFrom = portFrom
            self.portTo = portTo
            self.hovered = False
            self.setAcceptHoverEvents(True)
            self.setData(BaseGraphScene.KEY_ITEM, self)
            self.setZValue(-1)
            self.sync()

        def sync(self):
            """
            Synchronizes the view with the model.

            :return:
            """
            pp = QPainterPath()
            pFrom = self.mapFromScene(self.portFrom.nodeItem.mapToScene(self.portFrom.portGrItem.pos()))
            pTo = self.mapFromScene(self.portTo.nodeItem.mapToScene(self.portTo.portGrItem.pos()))
            style = BaseGraphScene.getData if self.scene() is None else self.scene().getData
            if pTo.x() > pFrom.x():
                # forward connection
                pp.moveTo(pFrom)
                pp.lineTo(pFrom + QPointF(style(self.portFrom, BaseGraphScene.STYLE_ROLE_HSPACING), 0))
                pp.lineTo(pTo - QPointF(style(self.portTo, BaseGraphScene.STYLE_ROLE_HSPACING), 0))
                pp.lineTo(pTo)
            else:
                # backward connection
                if self.portFrom.nodeItem is self.portTo.nodeItem:
                    upper = self.portTo.nodeItem.mapToScene(QPointF(0, 0))
                    upper -= QPointF(0, style(self.portTo.nodeItem, BaseGraphScene.STYLE_ROLE_VSPACING)/2)
                    upper = self.mapFromScene(upper)
                    y = upper.y()
                else:
                    y = pFrom.y()*0.5 + pTo.y()*0.5
                p = pFrom
                pp.moveTo(p)
                p += QPointF(style(self.portFrom, BaseGraphScene.STYLE_ROLE_HSPACING), 0)
                pp.lineTo(p)
                p.setY(y)
                pp.lineTo(p)
                p.setX(pTo.x() - style(self.portTo, BaseGraphScene.STYLE_ROLE_HSPACING))
                pp.lineTo(p)
                p.setY(pTo.y())
                pp.lineTo(p)
                pp.lineTo(pTo)
            self.prepareGeometryChange()
            self.setPen(style(self, BaseGraphScene.STYLE_ROLE_PEN))
            self.setPath(pp)

        def hoverEnterEvent(self, event):
            """
            override for hover enter events

            :param event: the QT event
            :return:
            """
            self.hovered = True
            self.sync()
            return super().hoverEnterEvent(event)

        def hoverLeaveEvent(self, event):
            """
            override for hover leave events

            :param event: the QT event
            :return:
            """
            self.hovered = False
            self.sync()
            return super().hoverLeaveEvent(event)

        def shape(self):
            """
            Unsure if this is needed, but it may give better hover positions

            :return:
            """
            return self.path()


    def __init__(self, parent):
        super().__init__(parent)
        self.nodes = {}
        self.connections = []
        self.itemOfContextMenu = None
        self.addingConnection = None
        self._lastEndPortHovered = None

    def addNode(self, name):
        """
        Add a named node to the graph

        :param name: a string instance
        :return:
        """
        assert not name in self.nodes
        self.nodes[name] = self.NodeItem(name)
        self.addItem(self.nodes[name])

    def renameNode(self, oldName, newName):
        """
        Rename a node in the graph

        :param oldName: the old name
        :param newName: the new name
        :return:
        """
        ni = self.nodes[oldName]
        ni.name = newName
        del self.nodes[oldName]
        self.nodes[newName] = ni
        ni.sync()

    def removeNode(self, name):
        """
        Remove a node from the graph

        :param name: the node name
        :return:
        """
        ni = self.nodes[name]
        toDel = []
        for c in self.connections:
            if c.portFrom.nodeItem is ni or c.portTo.nodeItem is ni:
                toDel.append(c)
        for c in toDel:
            self.removeConnection(c.portFrom.nodeItem.name, c.portFrom.name,
                                  c.portTo.nodeItem.name, c.portTo.name)
        del self.nodes[name]
        self.removeItem(ni)

    def addInPort(self, node, name):
        """
        add an input port to a node

        :param node: the node name
        :param name: the port name
        :return:
        """
        nodeItem = self.nodes[node]
        nodeItem.addInPortItem(name)

    def renameInPort(self, node, oldName, newName):
        """
        Rename an input port from a node

        :param node: the node name
        :param oldName: the old port name
        :param newName: the new port name
        :return:
        """
        ni = self.nodes[node]
        pi = ni.getInPortItem(oldName)
        pi.name = newName
        ni.sync()

    def renameOutPort(self, node, oldName, newName):
        """
        Rename an output port from a node

        :param node: the node name
        :param oldName: the old port name
        :param newName: the new port name
        :return:
        """
        ni = self.nodes[node]
        pi = ni.getOutPortItem(oldName)
        pi.name = newName
        ni.sync()

    def removeInPort(self, node, name):
        """
        Remove an input port from a node

        :param node: the node name
        :param name: the port name
        :return:
        """
        ni = self.nodes[node]
        pi = ni.getInPortItem(name)
        for c in pi.connections:
            if c.portTo is pi:
                self.removeConnection(c.portFrom.nodeItem.name, c.portFrom.name,
                                      c.portTo.nodeItem.name, c.portTo.name)
        pi.remove()
        ni.sync()

    def removeOutPort(self, node, name):
        """
        Remove an output port from a node

        :param node: the node name
        :param name: the port name
        :return:
        """
        ni = self.nodes[node]
        pi = ni.getOutPortItem(name)
        for c in pi.connections:
            if c.portFrom is pi:
                self.removeConnection(c.portFrom.nodeItem.name, c.portFrom.name,
                                      c.portTo.nodeItem.name, c.portTo.name)
        pi.remove()
        ni.sync()

    def addOutPort(self, node, name):
        """
        Adds an output port to a node

        :param node: the node name
        :param name: the port name
        :return:
        """
        nodeItem = self.nodes[node]
        nodeItem.addOutPortItem(name)

    def addConnection(self, nodeFrom, portFrom, nodeTo, portTo):
        """
        Add a connection to the graph

        :param nodeFrom: the start node's name
        :param portFrom: the start node's port
        :param nodeTo: the end node's name
        :param portTo: the end node's port
        :return:
        """
        nodeFromItem = self.nodes[nodeFrom]
        portFromItem = nodeFromItem.getOutPortItem(portFrom)
        nodeToItem = self.nodes[nodeTo]
        portToItem = nodeToItem.getInPortItem(portTo)
        self.connections.append(self.ConnectionItem(portFromItem, portToItem))
        portFromItem.connections.append(self.connections[-1])
        portToItem.connections.append(self.connections[-1])
        self.addItem(self.connections[-1])

    def removeConnection(self, nodeFrom, portFrom, nodeTo, portTo):
        """
        Removes a connection from the graph

        :param nodeFrom: the start node's name
        :param portFrom: the start node's port
        :param nodeTo: the end node's name
        :param portTo: the end node's port
        :return:
        """
        ni1 = self.nodes[nodeFrom]
        pi1 = ni1.getOutPortItem(portFrom)
        ni2 = self.nodes[nodeTo]
        pi2 = ni2.getInPortItem(portTo)
        for ci in [c for c in self.connections if c.portFrom is pi1 and c.portTo is pi2]:
            pi1.connections.remove(ci)
            pi2.connections.remove(ci)
            self.connections.remove(ci)
            self.removeItem(ci)
        ni1.sync()
        ni2.sync()

    @staticmethod
    def getData(item, role):
        """
        returns render-relevant information about the specified item
        can be overriden in concrete editor instances

        :param item: an instance of BaseGraphScene.NodeItem, BaseGraphScene.PortItem or BaseGraphScene.ConnectionItem
        :param role: one of STYLE_ROLE_SIZE, STYLE_ROLE_PEN, STYLE_ROLE_BRUSH, STYLE_ROLE_RRRADIUS, STYLE_ROLE_VSPACING,
                     STYLE_ROLE_HSPACING
        :return: the expected item related to the role
        """
        # pylint: disable=invalid-name
        DEFAULTS = {
            BaseGraphScene.STYLE_ROLE_HSPACING : 0,
            BaseGraphScene.STYLE_ROLE_VSPACING : 0,
            BaseGraphScene.STYLE_ROLE_SIZE : QSizeF(),
            BaseGraphScene.STYLE_ROLE_RRRADIUS : 0,
            BaseGraphScene.STYLE_ROLE_PEN : QPen(),
            BaseGraphScene.STYLE_ROLE_BRUSH : QBrush(),
            BaseGraphScene.STYLE_ROLE_TEXT_BRUSH : QBrush(),
        }

        if isinstance(item, BaseGraphScene.NodeItem):
            NODE_STYLE = {
                BaseGraphScene.STYLE_ROLE_HSPACING : 50,
                BaseGraphScene.STYLE_ROLE_VSPACING : 10,
                BaseGraphScene.STYLE_ROLE_SIZE : QSizeF(115, 30),
                BaseGraphScene.STYLE_ROLE_RRRADIUS : 4,
                BaseGraphScene.STYLE_ROLE_PEN : QPen(QColor(10, 10, 10)),
                BaseGraphScene.STYLE_ROLE_BRUSH : QBrush(QColor(10, 200, 10, 180)),
            }
            res = NODE_STYLE.get(role, DEFAULTS.get(role))
            if item.hovered and role == BaseGraphScene.STYLE_ROLE_PEN:
                res.setWidthF(3)
            if item.isSelected() and role == BaseGraphScene.STYLE_ROLE_PEN:
                res.setWidthF(max(2, res.widthF()))
                res.setStyle(Qt.DashLine)
            return res
        if isinstance(item, BaseGraphScene.PortItem):
            def portIdx(portItem):
                nodeItem = portItem.nodeItem
                if portItem in nodeItem.inPortItems:
                    return nodeItem.inPortItems.index(portItem)
                if portItem in nodeItem.outPortItems:
                    return len(nodeItem.outPortItems) - 1 - nodeItem.outPortItems.index(portItem)
                return 0

            PORT_STYLE = {
                BaseGraphScene.STYLE_ROLE_SIZE : QSizeF(5, 5),
                BaseGraphScene.STYLE_ROLE_VSPACING : 20,
                BaseGraphScene.STYLE_ROLE_HSPACING : (BaseGraphScene.getData(item.nodeItem,
                                                                             BaseGraphScene.STYLE_ROLE_HSPACING) +
                                                      portIdx(item) * 5),
                BaseGraphScene.STYLE_ROLE_PEN : QPen(QColor(10, 10, 10)),
                BaseGraphScene.STYLE_ROLE_BRUSH : QBrush(QColor(50, 50, 50, 180)),
            }
            PORT_STYLE_HOVERED = {
                BaseGraphScene.STYLE_ROLE_SIZE : QSizeF(8, 8),
            }
            if item.hovered:
                return PORT_STYLE_HOVERED.get(role, PORT_STYLE.get(role, DEFAULTS.get(role)))
            return PORT_STYLE.get(role, DEFAULTS.get(role))
        if isinstance(item, BaseGraphScene.ConnectionItem):
            CONN_STYLE = {
                BaseGraphScene.STYLE_ROLE_PEN : QPen(QColor(10, 10, 10), 1.5),
            }
            CONN_STYLE_HOVERED = {
                BaseGraphScene.STYLE_ROLE_PEN : QPen(QColor(10, 10, 10), 3),
            }
            if item.hovered:
                return CONN_STYLE_HOVERED.get(role, CONN_STYLE.get(role, DEFAULTS.get(role)))
            return CONN_STYLE.get(role, DEFAULTS.get(role))
        # pylint: enable=invalid-name
        raise TypeError("Unexpected item.")

    def graphItemAt(self, scenePos):
        """
        Returns the graph item at the specified scene position

        :param scenePos: a QPoint instance
        :return: a NodeItem, PortItem or ConnectionItem instance
        """
        gitems = self.items(scenePos)
        gitems_relaxed = self.items(QRectF(scenePos - QPointF(2, 2), QSizeF(4, 4)))
        for gi in gitems + gitems_relaxed:
            item = gi.data(BaseGraphScene.KEY_ITEM)
            self.itemOfContextMenu = item
            if isinstance(item, (BaseGraphScene.NodeItem, BaseGraphScene.PortItem, BaseGraphScene.ConnectionItem)):
                return item
        return None

    def mousePressEvent(self, event):
        """
        Override from QGraphicsScene (used for dragging connections)

        :param event: the QT event
        :return:
        """
        if event.button() == Qt.LeftButton:
            item = self.graphItemAt(event.scenePos())
            if isinstance(item, BaseGraphScene.PortItem):
                fromPos = item.portGrItem.scenePos()
                lineItem = QGraphicsLineItem(None)
                fromPos = lineItem.mapFromScene(fromPos)
                lineItem.setLine(fromPos.x(), fromPos.y(), fromPos.x(), fromPos.y())
                lineItem.setPen(QPen(Qt.DotLine))
                self.addItem(lineItem)
                self.addingConnection = dict(port=item, lineItem=lineItem)
                self.update()
                for v in self.views():
                    v.setDragMode(QGraphicsView.NoDrag)
                return True
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        Override from QGraphicsScene (used for dragging connections)

        :param event: the QT event
        :return:
        """
        if event.buttons() & Qt.LeftButton == Qt.LeftButton and self.addingConnection is not None:
            lineItem = self.addingConnection["lineItem"]
            toPos = lineItem.mapFromScene(event.scenePos())
            lineItem.prepareGeometryChange()
            lineItem.setLine(lineItem.line().x1(), lineItem.line().y1(), toPos.x(), toPos.y())
            item = self.graphItemAt(event.scenePos())
            if not isinstance(item, BaseGraphScene.PortItem):
                item = None
            if isinstance(item, BaseGraphScene.PortItem) and item != self._lastEndPortHovered:
                self._lastEndPortHovered = item
                item.hoverEnter()
            elif item != self._lastEndPortHovered and self._lastEndPortHovered is not None:
                self._lastEndPortHovered.hoverLeave()
                self._lastEndPortHovered = None
            self.update()
            return True
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Override from QGraphicsScene (used for dragging connections)

        :param event: the QT event
        :return:
        """
        if event.button() == Qt.LeftButton and self.addingConnection is not None:
            for v in self.views():
                v.setDragMode(QGraphicsView.RubberBandDrag)
            portOther = self.addingConnection["port"]
            self.removeItem(self.addingConnection["lineItem"])
            self.addingConnection = None
            portHere = self.graphItemAt(event.scenePos())
            if portOther.isOutput != portHere.isOutput:
                if portOther.isOutput:
                    portFrom = portOther
                    portTo = portHere
                else:
                    portFrom = portHere
                    portTo = portOther
                self.connectionAddRequest.emit(portFrom.nodeItem.name, portFrom.name, portTo.nodeItem.name, portTo.name)
            if self._lastEndPortHovered is not None:
                self._lastEndPortHovered.hoverLeave()
                self._lastEndPortHovered = None
            return True
        return super().mouseReleaseEvent(event)

    def autoLayout(self):
        """
        Automatic layout of nodes using a heuristic layering algorithm.

        :return:
        """
        gl = GraphLayering.GraphRep(self)
        layers, _ = gl.sortLayers()
        layeredNodes = gl.layersToNodeNames(layers)
        x = 0
        for _, l in enumerate(layeredNodes):
            y = 0
            maxdx = 0
            for _, n in enumerate(l):
                self.nodes[n].setPos(x, y)
                y += self.nodes[n].nodeHeight()
                maxdx = max(maxdx, self.nodes[n].nodeWidth())
            x += maxdx + self.STYLE_ROLE_HSPACING

class PortSelectorDialog(QDialog):
    """
    Dialog for selecting the ports which shall be created.
    """
    def __init__(self, parent, inputPorts, outputPorts, graph, nodeName):
        """
        Constructor

        :param parent: this dialog's parent widget
        :param inputPorts: the list of input port names
        :param outputPorts: the list of output port names
        :param graph: the corresponding BaseGraph instance
        :param nodeName: the name of the corresponding node
        """
        super().__init__(parent)
        layout = QGridLayout()
        gbi = QGroupBox("Input Ports", self)
        gbo = QGroupBox("Output Ports", self)
        vbi = QVBoxLayout()
        vbo = QVBoxLayout()
        self.inputCheckBoxes = []
        self.outputCheckBoxes = []
        self.selectedInputPorts = []
        self.selectedOutputPorts = []
        for ip in inputPorts:
            cb = QCheckBox(ip)
            cb.setText(ip)
            cb.setChecked(True)
            if ip in graph.allInputPorts(nodeName):
                cb.setEnabled(False)
            else:
                cb.setEnabled(True)
            vbi.addWidget(cb)
            self.inputCheckBoxes.append(cb)
        gbi.setLayout(vbi)
        for op in outputPorts:
            cb = QCheckBox(op)
            cb.setText(op)
            cb.setChecked(True)
            if op in graph.allOutputPorts(nodeName):
                cb.setEnabled(False)
            else:
                cb.setEnabled(True)
            vbo.addWidget(cb)
            self.outputCheckBoxes.append(cb)
        gbo.setLayout(vbo)
        layout = QGridLayout(self)
        layout.addWidget(gbi, 0, 0)
        layout.addWidget(gbo, 0, 1)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox, 1, 0, 1, 2)
        self.setLayout(layout)
        self.setWindowTitle("Select Ports to be created")

    def accept(self):
        """
        Accepts user selection.
        """
        self.selectedInputPorts = [cb.text() for cb in self.inputCheckBoxes if cb.isChecked() and cb.isEnabled()]
        self.selectedOutputPorts = [cb.text() for cb in self.outputCheckBoxes if cb.isChecked() and cb.isEnabled()]
        return super().accept()

    def reject(self):
        """
        Rejects user selection.
        """
        self.selectedInputPorts = []
        self.selectedOutputPorts = []
        return super().reject()

    @staticmethod
    def getSelectedPorts(parent, inputPorts, outputPorts, graph, nodeName):
        """
        Convenience function for executing the dialog.

        :param parent: this dialog's parent widget
        :param inputPorts: the list of input port names
        :param outputPorts: the list of output port names
        :param graph: the corresponding BaseGraph instance
        :param nodeName: the name of the corresponding node
        """
        d = PortSelectorDialog(parent, inputPorts, outputPorts, graph, nodeName)
        if d.exec() == QDialog.Accepted:
            return d.selectedInputPorts, d.selectedOutputPorts
        return [], []

class GraphScene(BaseGraphScene):
    """
    Concrete class interacting with a BaseGraph or FilterGraph instance
    """
    def __init__(self, graph, parent):
        super().__init__(parent)
        self.graph = graph
        self._threadBrushes = {
            "main" : BaseGraphScene.getData(BaseGraphScene.NodeItem("<temp>"), BaseGraphScene.STYLE_ROLE_BRUSH),
        }
        for n in self.graph.allNodes():
            self.addNode(n)
            for p in self.graph.allInputPorts(n):
                self.addInPort(n, p)
            for p in self.graph.allOutputPorts(n):
                self.addOutPort(n, p)
            # make sure that the added nodes are painted in correct styling
            self.nodes[n].sync()
        for c in self.graph.allConnections():
            self.addConnection(*c)
        self.graph.nodeAdded.connect(self.addNode)
        self.graph.nodeRenamed.connect(self.renameNode)
        self.graph.nodeDeleted.connect(self.removeNode)
        self.graph.inPortAdded.connect(self.addInPort)
        self.graph.inPortRenamed.connect(self.renameInPort)
        self.graph.inPortDeleted.connect(self.removeInPort)
        self.graph.outPortAdded.connect(self.addOutPort)
        self.graph.outPortRenamed.connect(self.renameOutPort)
        self.graph.outPortDeleted.connect(self.removeOutPort)
        self.graph.connectionAdded.connect(self.addConnection)
        self.graph.connectionDeleted.connect(self.removeConnection)
        self.connectionAddRequest.connect(self.graph.addConnection)

        self.itemOfContextMenu = None

        self.actRenameNode = QAction("Rename node ...", self)
        self.actRemoveNode = QAction("Remove node ...", self)
        self.actAddNode = QAction("Add filter from file ...", self)
        self.actAutoLayout = QAction("Auto layout", self)
        self.actRemoveConnection = QAction("Remove connection ...", self)
        self.actRenameNode.triggered.connect(self.renameDialog)
        self.actRemoveNode.triggered.connect(self.removeDialog)
        self.actRemoveConnection.triggered.connect(self.onConnectionRemove)
        self.actAutoLayout.triggered.connect(self.autoLayout)
        if isinstance(self.graph, FilterGraph):
            self.actRenamePort = QAction("Rename dynamic port ...", self)
            self.actRemovePort = QAction("Remove dynamic port ...", self)
            self.actAddInputPort = QAction("Add dynamic input port ...", self)
            self.actAddOutputPort = QAction("Add dynamic output port ...", self)
            self.actSuggestDynamicPorts = QAction("Suggest dynamic ports ...", self)
            self.entryPointActions = dict()
            for ep in pkg_resources.iter_entry_points("nexxT.filters"):
                d = self.entryPointActions
                groups = ep.name.split(".")
                name = groups[-1]
                try:
                    checkIdentifier(name)
                except InvalidIdentifierException:
                    logger.warning("Entry point '%s' is no valid identifier. Ignoring.", ep.name)
                    continue
                groups = groups[:-1]
                for g in groups:
                    if not g in d:
                        d[g] = dict()
                    d = d[g]
                if name in d:
                    logger.warning("Entry point '%s' registered twice, ignoring duplicates", ep.name)
                else:
                    d[name] = QAction(name)
                    d[name].setData(ep.name)
                    d[name].triggered.connect(self.addFilterFromEntryPoint)
            self.actAddNodeFromMod = QAction("Add filter from python module ...", self)
            self.actAddComposite = QAction("Add filter form composite definition ...", self)
            self.actSetThread = QAction("Set thread ...", self)
            self.actSuggestDynamicPorts.triggered.connect(self.onSuggestDynamicPorts)
            self.actAddNode.triggered.connect(self.onAddFilterFromFile)
            self.actAddNodeFromMod.triggered.connect(self.onAddFilterFromMod)
            self.actAddComposite.triggered.connect(self.onAddComposite)
            self.actSetThread.triggered.connect(self.setThread)
        elif isinstance(self.graph, BaseGraph):
            self.actRenamePort = QAction("Rename port ...", self)
            self.actRemovePort = QAction("Remove port ...", self)
            self.actAddInputPort = QAction("Add input port ...", self)
            self.actAddOutputPort = QAction("Add output port ...", self)
            self.actAddNode.triggered.connect(self.onAddNode)
        self.actRenamePort.triggered.connect(self.renameDialog)
        self.actRemovePort.triggered.connect(self.removeDialog)
        self.actAddInputPort.triggered.connect(self.addInputPort)
        self.actAddOutputPort.triggered.connect(self.addOutputPort)
        self.autoLayout()

    def getData(self, item, role):
        if isinstance(item, BaseGraphScene.NodeItem) and isinstance(self.graph, FilterGraph):
            if role == BaseGraphScene.STYLE_ROLE_BRUSH:
                mockup = self.graph.getMockup(item.name)
                threads = tuple(sorted(SubConfiguration.getThreadSet(mockup)))
                for t in threads:
                    if not t in self._threadBrushes:
                        self._threadBrushes[t] = QBrush(ThreadToColor.singleton.get(t))
                if len(threads) == 1:
                    return self._threadBrushes[threads[0]]
                if threads not in self._threadBrushes:
                    img = QImage(len(threads)*3, len(threads)*3, QImage.Format_BGR888)
                    for x in range(img.width()):
                        for y in range(img.height()):
                            tidx = ((x + y)//3) % len(threads)
                            c = self._threadBrushes[threads[tidx]].color()
                            img.setPixelColor(x, y, c)
                    self._threadBrushes[threads] = QBrush(img)
                return self._threadBrushes[threads]
            if role == BaseGraphScene.STYLE_ROLE_TEXT_BRUSH:
                mockup = self.graph.getMockup(item.name)
                threads = tuple(sorted(SubConfiguration.getThreadSet(mockup)))
                if len(threads) > 1:
                    return QBrush(QColor(255, 255, 255, 200))
                return QBrush(QColor(255, 255, 255, 100))
        return BaseGraphScene.getData(item, role)


    def contextMenuEvent(self, event):
        item = self.graphItemAt(event.scenePos())
        self.itemOfContextMenu = item
        if isinstance(item, BaseGraphScene.NodeItem):
            m = QMenu(self.views()[0])
            m.addActions([self.actRenameNode, self.actRemoveNode, self.actAddInputPort, self.actAddOutputPort,
                          self.actSuggestDynamicPorts])
            if isinstance(self.graph, FilterGraph):
                m.addAction(self.actSetThread)
                mockup = self.graph.getMockup(item.name)
                din, dout = mockup.getDynamicPortsSupported()
                self.actAddInputPort.setEnabled(din)
                self.actAddOutputPort.setEnabled(dout)
                self.actSuggestDynamicPorts.setEnabled(din or dout)
                if (issubclass(mockup.getPluginClass(), CompositeFilter) or
                        issubclass(mockup.getPluginClass(), CompositeFilter.CompositeNode) or
                        issubclass(mockup.getPluginClass(), CompositeFilter.CompositeOutputNode) or
                        issubclass(mockup.getPluginClass(), CompositeFilter.CompositeInputNode)):
                    self.actSetThread.setEnabled(False)
                else:
                    self.actSetThread.setEnabled(True)
            m.exec_(event.screenPos())
        elif isinstance(item, BaseGraphScene.PortItem):
            m = QMenu(self.views()[0])
            if isinstance(self.graph, FilterGraph):
                mockup = self.graph.getMockup(item.nodeItem.name)
                port = mockup.getPort(item.name, OutputPortInterface if item.isOutput else InputPortInterface)
                self.actRenamePort.setEnabled(port.dynamic())
                self.actRemovePort.setEnabled(port.dynamic())
            m.addActions([self.actRenamePort, self.actRemovePort])
            m.exec_(event.screenPos())
        elif isinstance(item, BaseGraphScene.ConnectionItem):
            m = QMenu(self.views()[0])
            m.addActions([self.actRemoveConnection])
            m.exec_(event.screenPos())
        else:
            self.itemOfContextMenu = event.scenePos()
            m = QMenu(self.views()[0])
            cfs = self.compositeFilters()
            self.actAddComposite.setEnabled(len(cfs) > 0)
            m.addActions([self.actAddNode, self.actAddNodeFromMod, self.actAddComposite])
            flm = m.addMenu("Filter Library")
            def populate(menu, src):
                for k in sorted(src):
                    if isinstance(src[k], dict):
                        populate(menu.addMenu(k), src[k])
                    else:
                        menu.addAction(src[k])
            populate(flm, self.entryPointActions)
            m.addAction(self.actAutoLayout)
            m.exec_(event.screenPos())
        self.itemOfContextMenu = None

    def compositeFilters(self):
        """
        Get a list of names of composite filters.

        :return: a list of strings
        """
        sc = self.graph.getSubConfig()
        conf = sc.getConfiguration()
        return conf.getCompositeFilterNames()

    def renameDialog(self):
        """
        Opens a dialog for renamign an item (node or port)

        :return:
        """
        item = self.itemOfContextMenu
        newName, ok = QInputDialog.getText(self.views()[0], self.sender().text(),
                                           "Enter new name of " + item.itemTypeName(),
                                           text=self.itemOfContextMenu.name)
        if ok and newName != "" and newName is not None:
            if isinstance(item, BaseGraphScene.NodeItem):
                self.graph.renameNode(item.name, newName)
            elif isinstance(item, BaseGraphScene.PortItem):
                if item.isOutput:
                    if isinstance(self.graph, FilterGraph):
                        self.graph.renameDynamicOutputPort(item.nodeItem.name, item.name, newName)
                    else:
                        self.graph.renameOutputPort(item.nodeItem.name, item.name, newName)
                else:
                    if isinstance(self.graph, FilterGraph):
                        self.graph.renameDynamicInputPort(item.nodeItem.name, item.name, newName)
                    else:
                        self.graph.renameInputPort(item.nodeItem.name, item.name, newName)

    def removeDialog(self):
        """
        Opens a dialog for removing an item (Node or Port)

        :return:
        """
        item = self.itemOfContextMenu
        btn = QMessageBox.question(self.views()[0], self.sender().text(),
                                   "Do you really want to remove the " + item.itemTypeName() + "?")
        if btn == QMessageBox.Yes:
            if isinstance(item, BaseGraphScene.NodeItem):
                self.graph.deleteNode(item.name)
            elif isinstance(item, BaseGraphScene.PortItem):
                if item.isOutput:
                    if isinstance(self.graph, FilterGraph):
                        self.graph.deleteDynamicOutputPort(item.nodeItem.name, item.name)
                    else:
                        self.graph.deleteOutputPort(item.nodeItem.name, item.name)
                else:
                    if isinstance(self.graph, FilterGraph):
                        self.graph.deleteDynamicInputPort(item.nodeItem.name, item.name)
                    else:
                        self.graph.deleteInputPort(item.nodeItem.name, item.name)

    def onConnectionRemove(self):
        """
        Removes a connection

        :return:
        """
        item = self.itemOfContextMenu
        self.graph.deleteConnection(item.portFrom.nodeItem.name, item.portFrom.name,
                                    item.portTo.nodeItem.name, item.portTo.name)

    def addInputPort(self):
        """
        Adds an input port to a node

        :return:
        """
        item = self.itemOfContextMenu
        if isinstance(item, BaseGraphScene.NodeItem):
            newName, ok = QInputDialog.getText(self.views()[0], self.sender().text(),
                                               "Enter name of input port of " + item.itemTypeName())
            if not ok:
                return
            if isinstance(self.graph, FilterGraph):
                self.graph.addDynamicInputPort(item.name, newName)
            else:
                self.graph.addInputPort(item.name, newName)

    def addOutputPort(self):
        """
        Adds an output port to a node

        :return:
        """
        item = self.itemOfContextMenu
        if isinstance(item, BaseGraphScene.NodeItem):
            newName, ok = QInputDialog.getText(self.views()[0], self.sender().text(),
                                               "Enter name of output port of " + item.itemTypeName())
            if not ok:
                return
            if isinstance(self.graph, FilterGraph):
                self.graph.addDynamicOutputPort(item.name, newName)
            else:
                self.graph.addOutputPort(item.name, newName)

    def setThread(self):
        """
        Opens a dialog to enter the new thread of the node.

        :return:
        """
        item = self.itemOfContextMenu
        threads = SubConfiguration.getThreadSet(self.graph.getSubConfig())
        newThread, ok = QInputDialog.getItem(self.views()[0], self.sender().text(),
                                             "Enter name of new thread of " + item.name,
                                             list(sorted(threads)), editable=True)
        if not ok or newThread is None or newThread == "":
            return
        mockup = self.graph.getMockup(item.name)
        pc = mockup.propertyCollection().getChildCollection("_nexxT")
        pc.setProperty("thread", newThread)
        item.sync()

    def onAddNode(self):
        """
        Called when the user wants to add a new node. (Generic variant)

        :return:
        """
        newName, ok = QInputDialog.getText(self.views()[0], self.sender().text(),
                                           "Enter name of new node")
        if ok:
            self.graph.addNode(newName)
            self.nodes[newName].setPos(self.itemOfContextMenu)

    def onSuggestDynamicPorts(self):
        """
        Called when the user wants to add dynamic ports based on the filter's suggestions.

        :return:
        """
        assertMainThread()
        item = self.itemOfContextMenu
        if isinstance(item, BaseGraphScene.NodeItem) and isinstance(self.graph, FilterGraph):
            mockup = self.graph.getMockup(item.name)
            with mockup.createFilter() as env:
                inputPorts, outputPorts = env.getPlugin().onSuggestDynamicPorts()
            if len(inputPorts) > 0 or len(outputPorts) > 0:
                inputPorts, outputPorts = PortSelectorDialog.getSelectedPorts(self.views()[0], inputPorts, outputPorts,
                                                                              self.graph, item.name)
                for ip in inputPorts:
                    self.graph.addDynamicInputPort(item.name, ip)
                for op in outputPorts:
                    self.graph.addDynamicOutputPort(item.name, op)
            else:
                QMessageBox.information(self.views()[0], "nexxT: information", "The filter does not suggest any ports.")

    def onAddFilterFromFile(self):
        """
        Called when the user wants to add a new filter from a file (FilterGraph variant).
        Opens a dialog to select the file.

        :return:
        """
        if platform.system().lower() == "linux":
            suff = "*.so"
        else:
            suff = "*.dll"
        library, ok = QFileDialog.getOpenFileName(self.views()[0], "Choose Library",
                                                  filter="Filters (*.py %s)" % suff)
        if not (ok and library is not None and os.path.exists(library)):
            return
        if library.endswith(".py"):
            library = "pyfile://" + library
        else:
            library = "binary://" + library
        self._genericAdd(library)

    def onAddFilterFromMod(self):
        """
        Called when the user wants to add a new filter from a python module.

        :return:
        """
        library, ok = QInputDialog.getText(self.views()[0], "Choose python module", "Choose python module")
        if ok:
            if not library.startswith("pymod://"):
                library = "pymod://" + library
            self._genericAdd(library)

    @handleException
    def _addFilterFromEntryPoint(self):
        ep_name = self.sender().data()
        library = "entry_point://" + ep_name
        name = self.graph.addNode(library, ep_name.split(".")[-1])
        self.nodes[name].setPos(self.itemOfContextMenu)

    def addFilterFromEntryPoint(self):
        """
        Add a filter from its corresponding entry point (the entry point is deduced from the sender action's data()).

        :return:
        """
        self._addFilterFromEntryPoint()

    def onAddComposite(self):
        """
        Called when the user wants to add a new composite filter to this graph.

        :return:
        """
        cfs = self.compositeFilters()
        compName, ok = QInputDialog.getItem(self.views()[0], "Choose composite filter", "Choose composite filter", cfs)
        if ok:
            sc = self.graph.getSubConfig()
            conf = sc.getConfiguration()
            comp = conf.compositeFilterByName(compName)
            name = self.graph.addNode(comp, "compositeNode", suggestedName=compName)
            self.nodes[name].setPos(self.itemOfContextMenu)

    def _genericAdd(self, library):
        pm = PluginManager.singleton()
        filters = pm.getFactoryFunctions(library)
        if len(filters) > 0:
            factory, ok = QInputDialog.getItem(self.views()[0], "Choose filter", "Choose filter", filters)
            if not ok or not factory in filters:
                return
        else:
            factory = filters[0]
        name = self.graph.addNode(library, factory)
        self.nodes[name].setPos(self.itemOfContextMenu)
