# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the GraphEditorView class.
"""

import logging
import json
from PySide2.QtCore import QMimeData
from PySide2.QtGui import QPainter, QKeySequence, QGuiApplication
from PySide2.QtWidgets import QGraphicsView
from nexxT.core.SubConfiguration import SubConfiguration
from nexxT.services.gui.GraphEditor import BaseGraphScene, GraphScene

logger = logging.getLogger(__name__)

class GraphEditorView(QGraphicsView):
    """
    Subclass of QGraphicsView which handles copy&paste events
    """
    def __init__(self, parent):
        """
        Constructor

        :param parent: a QWidget instance
        """
        super().__init__(parent=parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)

    def keyPressEvent(self, event):
        """
        Overwritten from QGraphicsView for intercepting copy & paste events.

        :param event: a QKeyEvent instance
        :return:
        """
        if event.matches(QKeySequence.Copy):
            self._copy(cut=False)
            return True
        if event.matches(QKeySequence.Cut):
            self._copy(cut=True)
        if event.matches(QKeySequence.Paste):
            self._paste()
            return True
        return super().keyPressEvent(event)

    def _copy(self, cut):
        """
        Copys the selection to clipboard.

        :param cut: boolean whether the copy is actually a cut.
        :return:
        """
        logger.internal("Copying...")
        sc = self.scene()
        assert isinstance(sc, GraphScene)
        items = sc.selectedItems()
        nodes = set()
        for i in items:
            if isinstance(i, BaseGraphScene.NodeItem):
                nodes.add(i.name)
        saved = sc.graph.getSubConfig().save()
        if "_guiState" in saved:
            del saved["_guiState"]
        toDelIdx = []
        deletedNodes = set()
        for i, n in enumerate(saved["nodes"]):
            if not n["name"] in nodes:
                toDelIdx.append(i)
                deletedNodes.add(n["name"])
        for i in toDelIdx[::-1]:
            saved["nodes"] = saved["nodes"][:i] + saved["nodes"][i+1:]
        cToDel = set()
        for c in saved["connections"]:
            node1, _, node2, _ = SubConfiguration.connectionStringToTuple(c)
            if node1 in deletedNodes or node2 in deletedNodes:
                cToDel.add(c)
        for c in cToDel:
            saved["connections"].remove(c)
        md = QMimeData()
        md.setData("nexxT/json", json.dumps(saved, indent=2, ensure_ascii=False).encode())
        QGuiApplication.clipboard().setMimeData(md)
        if cut:
            for n in saved["nodes"]:
                sc.graph.deleteNode(n["name"])
        logger.info("Copyied %d nodes and %d connections", len(saved["nodes"]), len(saved["connections"]))

    def _paste(self):
        """
        Pastes the clipboard contents to the scene.

        :return:
        """
        md = QGuiApplication.clipboard().mimeData()
        ba = md.data("nexxT/json")
        if ba.count() > 0:
            logger.internal("Paste")
            cfg = json.loads(bytes(ba).decode())
            nameTransformations = {}
            for n in cfg["nodes"]:
                nameTransformations[n["name"]] = self.scene().graph.uniqueNodeName(n["name"])
                n["name"] = nameTransformations[n["name"]]
            newConn = []
            for c in cfg["connections"]:
                node1, port1, node2, port2 = SubConfiguration.connectionStringToTuple(c)
                node1 = nameTransformations[node1]
                node2 = nameTransformations[node2]
                newConn.append(SubConfiguration.tupleToConnectionString((node1, port1, node2, port2)))
            cfg["connections"] = newConn
            def compositeLookup(name):
                return self.scene().graph.getSubConfig().getConfiguration().compositeFilterByName(name)
            self.scene().graph.getSubConfig().load(cfg, compositeLookup)
            self.scene().autoLayout()
            logger.info("Pasted")
