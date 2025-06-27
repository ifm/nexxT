# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
Real gui testing, a handy command for monitoring what's going on in the headless mode is:

> x11vnc -display :27 -localhost & (sleep 1; vncviewer :0) # 27 must match the display printed at the test start

You can also pass --no-xvfb to pytest and also --keep-open for inspecting the issue in head mode.
"""

import json
import os
import logging
from pathlib import Path
import re
import pytest
import nexxT.shiboken
from nexxT.Qt.QtCore import QItemSelection, Qt, QTimer, QSize, QPoint, QModelIndex
from nexxT.Qt.QtWidgets import QGraphicsSceneContextMenuEvent, QWidget, QApplication, QTreeView
from nexxT.core.AppConsole import startNexT
from nexxT.core import Compatibility
from nexxT.interface import Services
from nexxT.services.gui.GraphEditorView import GraphEditorView

logger = logging.getLogger(__name__)

@pytest.fixture
def keep_open(request):
    return request.config.getoption("--keep-open")

def setup():
    logging.getLogger().setLevel(logging.INFO)

# context menu actions
class ContextMenuEntry(str):
    pass
CM_ADD_APPLICATION = ContextMenuEntry("Add application")
CM_EDIT_GRAPH = ContextMenuEntry("Edit graph")
CM_REMOVE_APP = ContextMenuEntry("Remove app ...")
CM_REMOVE_COMPOSITE = ContextMenuEntry("Remove composite ...")
CM_INIT_APP = ContextMenuEntry("Init Application")
CM_INIT_APP_AND_OPEN =ContextMenuEntry("Init and load sequence")
CM_INIT_APP_AND_PLAY = ContextMenuEntry("Init, load and play")
CM_FILTER_LIBRARY = ContextMenuEntry("Filter Library")
CM_FILTER_FROM_PYMOD = ContextMenuEntry("Add filter from python module ...")
CM_FILTER_FROM_FILE = ContextMenuEntry("Add filter from file ...")
CM_FILTER_FROM_COMPOSITE = ContextMenuEntry("Add filter form composite definition ...")
CM_ADDCOMPOSITE = ContextMenuEntry("Add composite filter")
CM_AUTOLAYOUT = ContextMenuEntry("Auto layout")
CM_FILTER_LIBRARY_TESTS = ContextMenuEntry("tests")
CM_FILTER_LIBRARY_HARDDISK = ContextMenuEntry("harddisk")
CM_FILTER_LIBRARY_TESTS_NEXXT = ContextMenuEntry("nexxT")
CM_FILTER_LIBRARY_CSIMPLESOURCE = ContextMenuEntry("CSimpleSource")
CM_FILTER_LIBRARY_PYSIMPLESTATICFILTER = ContextMenuEntry("PySimpleStaticFilter")
CM_FILTER_LIBRARY_CPROPERTY_RECEIVER = ContextMenuEntry("CPropertyReceiver")
CM_FILTER_LIBRARY_PYSIMPLEVIEW = ContextMenuEntry("PySimpleView")
CM_FILTER_LIBRARY_HDF5WRITER = ContextMenuEntry("HDF5Writer")
CM_FILTER_LIBRARY_HDF5READER = ContextMenuEntry("HDF5Reader")
CM_RENAME_NODE = ContextMenuEntry("Rename node ...")
CM_REMOVE_NODE = ContextMenuEntry('Remove node ...')
CM_ADDDYNINPORT = ContextMenuEntry("Add dynamic input port ...")
CM_ADDDYNOUTPORT = ContextMenuEntry("Add dynamic output port ...")
CM_SUGGEST_DYNPORTS = ContextMenuEntry("Suggest dynamic ports ...")
CM_SETTHREAD = ContextMenuEntry("Set thread ...")
CM_RENAMEDYNPORT = ContextMenuEntry("Rename dynamic port ...")
CM_REMOVEDYNPORT = ContextMenuEntry("Remove dynamic port ...")
CM_ADDVARIABLE = ContextMenuEntry("Add variable ...")
CONFIG_MENU_DEINITIALIZE = ContextMenuEntry("Deinitialize")
CONFIG_MENU_INITIALIZE = ContextMenuEntry("Initialize")
LM_WARNING = ContextMenuEntry("Warning")

class GuiTestBase:
    def __init__(self, qtbot, xvfb, keep_open, delay, tmpdir):
        self.qtbot = qtbot
        self.delay = delay
        self.xvfb = xvfb
        self.keep_open = keep_open
        self.tmpdir = tmpdir
        if xvfb is not None:
            print("dims = ",xvfb.width, xvfb.height)
            print("DISPLAY=",xvfb.display)
        # make sure that we have a fresh environment
        os.environ["HOME"] = str(tmpdir)
        logger.info("TMPDIR=%s", tmpdir)

    """
    Class encapsulates useful method for gui testing the nexxT application.
    """
    def activateContextMenu(self, *menuItems, **kwargs):
        """
        In a given context menu navigate to the given index using key presses and activate it using return
        :param menuItems: Might be either integers referencing the position in the menu or (better) strings referencing
                          the menu text
        :return:
        """
        def activeMenuEntry():
            """
            return the text of the active menu item including submenus
            :return:
            """
            menu = QApplication.activePopupWidget()
            if menu is None:
                return None
            act = menu.activeAction()
            if act is None:
                return None

            while Compatibility.getMenuFromAction(act) is not None and Compatibility.getMenuFromAction(act).activeAction() is not None:
                act = Compatibility.getMenuFromAction(act).activeAction()
            return act.text()

        if kwargs.get("debug", False):
            logger_debug = logger.info
        else:
            logger_debug = logger.debug
        try:
            # navigate to the requested menu item
            for j in range(len(menuItems)):
                if isinstance(menuItems[j], int):
                    for i in range(menuItems[j]):
                        self.qtbot.keyClick(None, Qt.Key_Down, delay=self.delay)
                    logger_debug("(int) Current action: '%s'", activeMenuEntry())
                else:
                    nonNoneAction = None
                    while activeMenuEntry() is None or activeMenuEntry() != menuItems[j]:
                        logger_debug("(str) Current action: '%s' != '%s'", activeMenuEntry(), menuItems[j])
                        self.qtbot.keyClick(None, Qt.Key_Down, delay=self.delay)
                        if nonNoneAction is None:
                            nonNoneAction = activeMenuEntry()
                        else:
                            assert nonNoneAction != activeMenuEntry()
                    logger_debug("(str) Current action: '%s'", activeMenuEntry())
                if j < len(menuItems) - 1:
                    self.qtbot.keyClick(None, Qt.Key_Right, delay=self.delay)
            self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)
        except Exception:
            logger.exception("exception while activating context menu")
            raise

    @staticmethod
    def aw():
        """
        on xvfb, the main window sometimes looses focus leading to a crash of the qtbot's keyClick(s) function
        this function avoids this
        :return:
        """
        w = QApplication.activeWindow()
        if w is None:
            QApplication.setActiveWindow(Services.getService("MainWindow").data())
            w = QApplication.activeWindow()
        return w

    def enterText(self, text, w=None):
        """
        Enter the given text into the widget w (or the current widget, if w is None)
        :param text: the text to be entered
        :param w: the widget it should be entered to
        :return:
        """
        if isinstance(text, str):
            if text != "":
                self.qtbot.keyClicks(w, text)
        else:
            for k in text:
                self.qtbot.keyClick(w, k)
        self.qtbot.keyClick(w, Qt.Key_Return)

    def gsContextMenu(self, graphView, pos):
        """
        This function starts a context menu on a graphics view.
        :param graphView: the respective QGraphicsView
        :param pos: the position where the context menu shall be raised
        :return:
        """
        ev = QGraphicsSceneContextMenuEvent()
        ev.setScenePos(pos)
        ev.setPos(QPoint(0,0)) # item position
        ev.setScreenPos(graphView.viewport().mapToGlobal(graphView.mapFromScene(pos)))
        #print("scenePos=", ev.scenePos(), ", pos=", ev.pos(), ", screenPos=", ev.screenPos())
        self.qtbot.mouseMove(graphView.viewport(), graphView.mapFromScene(ev.scenePos()))
        graphView.scene().contextMenuEvent(ev)

    def cmContextMenu(self, conf, idx, *contextMenuIndices, **kwargs):
        """
        This function executes a context menu on the configuration tree view
        :param conf: The configuration gui service
        :param idx: A QModelIndex of the item where the context menu shall be raised
        :param contextMenuIndices: A list of ContextMenuEntry, int and str instances. ContextMenuEntry and int instances
                                   are used to navigate through the context menu, afterwards the str instances are
                                   entered as text (in dialogs resulting from the context menu).
        :return:
        """
        treeView = conf.treeView
        assert isinstance(treeView, QTreeView)
        treeView.scrollTo(idx)
        self.qtbot.wait(1000)
        pos = treeView.visualRegionForSelection(QItemSelection(idx, idx)).boundingRect().center()
        self.qtbot.mouseMove(treeView.viewport(), pos=pos, delay=self.delay)
        try:
            intIdx = max([i for i in range(-1, -len(contextMenuIndices)-1, -1)
                          if isinstance(contextMenuIndices[i], (int,ContextMenuEntry))])
            intIdx += len(contextMenuIndices)
        except ValueError:
            logger.exception("exception contextMenuIndices:%s empty?!?", contextMenuIndices)
            intIdx = -1
        cmIdx = contextMenuIndices[:intIdx+1]
        texts = contextMenuIndices[intIdx+1:]
        if kwargs.get("debug", False):
            logger.info("contextMenuIndices:%s cmIdx:%s texts:%s", contextMenuIndices, cmIdx, texts)
        QTimer.singleShot(self.delay, lambda: self.activateContextMenu(*cmIdx, **kwargs))
        for i, t in enumerate(texts):
            QTimer.singleShot(self.delay*(i+2), lambda text=t: self.enterText(text))
        conf._execTreeViewContextMenu(pos)

    def addNodeToGraphEditor(self, graphEditView, scenePos, *contextMenuItems):
        """
        Adds a node to the nexxT graph editor.
        :param graphEditView: the GraphEditorView instance
        :param scenePos: the position where the node shall be created
        :param contextMenuItems: the context menu items to be processed (see activateContextMenu(...))
        :return: the newly created node
        """
        oldNodes = set(graphEditView.scene().nodes.keys())
        try:
            intIdx = max([i for i in range(-1,-len(contextMenuItems)-1,-1)
                                if isinstance(contextMenuItems[i], (int, ContextMenuEntry))])
            intIdx += len(contextMenuItems)
        except ValueError:
            intIdx = -1
        cmIdx = contextMenuItems[:intIdx+1]
        texts = contextMenuItems[intIdx+1:]
        QTimer.singleShot(self.delay, lambda: self.activateContextMenu(*cmIdx))
        for i,t in enumerate(texts):
            QTimer.singleShot(self.delay*(i+2), lambda text=t: self.enterText(text))
        with self.qtbot.waitSignal(graphEditView.scene().changed):
            self.gsContextMenu(graphEditView, scenePos)
        res = None
        assert len(graphEditView.scene().nodes) == len(oldNodes) + 1
        for n in graphEditView.scene().nodes:
            if n not in oldNodes:
                assert res is None
                res = graphEditView.scene().nodes[n]
        assert res is not None
        # hover this item
        scenePos = res.nodeGrItem.sceneBoundingRect().center()
        self.qtbot.mouseMove(graphEditView.viewport(), QPoint(0,0), delay=self.delay)
        self.qtbot.mouseMove(graphEditView.viewport(), graphEditView.mapFromScene(scenePos), delay=self.delay)
        # set item selected and deselected again
        self.qtbot.mouseClick(graphEditView.viewport(), Qt.LeftButton, pos=graphEditView.mapFromScene(scenePos),
                              delay=self.delay)
        self.qtbot.mouseClick(graphEditView.viewport(), Qt.LeftButton, pos=graphEditView.mapFromScene(scenePos),
                              delay=self.delay)
        return res

    def removeNodeFromGraph(self, graphEditView, node):
        """
        Removes a node from the nexxT graph editor
        :param graphEditView: the GraphEditorView instance
        :param node: the node to be removed
        :return:
        """
        pos = node.nodeGrItem.sceneBoundingRect().center()
        QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_REMOVE_NODE))
        QTimer.singleShot(2*self.delay, lambda: self.enterText(""))
        self.gsContextMenu(graphEditView, pos)

    def setThreadOfNode(self, graphEditView, node, thread):
        pos = node.nodeGrItem.sceneBoundingRect().center()
        QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_SETTHREAD))
        QTimer.singleShot(2*self.delay, lambda: self.enterText(thread))
        self.gsContextMenu(graphEditView, pos)

    def addConnectionToGraphEditor(self, graphEditView, p1, p2):
        """
        Adds a connection in the nexxT graph editor
        :param graphEditView: the GraphEditorView instance
        :param p1: The port to start from
        :param p2: The port to end to
        :return:
        """
        pos1 = graphEditView.mapFromScene(p1.portGrItem.sceneBoundingRect().center())
        pos2 = graphEditView.mapFromScene(p2.portGrItem.sceneBoundingRect().center())
        self.qtbot.mouseMove(graphEditView.viewport(), pos1, delay=self.delay)
        self.qtbot.mousePress(graphEditView.viewport(), Qt.LeftButton, pos=pos1, delay=self.delay)
        # mouse move event will not be triggered (yet?), see https://bugreports.qt.io/browse/QTBUG-5232
        for i in range(30):
            w = i/29
            self.qtbot.mouseMove(graphEditView.viewport(), (pos1*(1-w)+pos2*w), delay=(self.delay+15)//30)
        self.qtbot.mouseMove(graphEditView.viewport(), pos2, delay=self.delay)
        self.qtbot.mouseRelease(graphEditView.viewport(), Qt.LeftButton, pos=pos2, delay=self.delay)

    def setFilterProperty(self, conf, subConfig, filterName, propName, propVal, expectedVal=None, indirect=False):
        """
        Sets a filter property in the configuration gui service.
        :param conf: the configuration gui service
        :param subConfig: the SubConfiguration instance
        :param filterName: the name of the filter
        :param propName: the name of the property
        :param propVal: the value of the property (which will be entered using enterText)
        :param expectedVal: if not None, the new expected value after editing, otherwise propVal will be used as the
                            expected value.
        :return:
        """
        idxapp = conf.model.indexOfSubConfig(subConfig)
        # search for filter
        idxFilter = None
        for r in range(conf.model.rowCount(idxapp)):
            idxFilter = conf.model.index(r, 0, idxapp)
            name = conf.model.data(idxFilter, Qt.DisplayRole)
            if name == filterName:
                break
            else:
                idxFilter = None
        assert idxFilter is not None
        # search for property
        idxProp = None
        row = None
        for r in range(conf.model.rowCount(idxFilter)):
            idxProp = conf.model.index(r, 0, idxFilter)
            name = conf.model.data(idxProp, Qt.DisplayRole)
            if name == propName:
                row = r
                break
            else:
                idxProp = None
        assert idxProp is not None
        assert row is not None
        # start the editor by pressing F2 on the property value
        idxPropVal = conf.model.index(row, 1, idxFilter)
        idxPropIndirect = conf.model.index(row, 2, idxFilter)
        cindirect = conf.model.data(idxPropIndirect, Qt.CheckStateRole) != Qt.Unchecked
        logger.info("cindirect=%s ==? indirect=%s", repr(cindirect), repr(indirect))
        if cindirect != indirect:
            conf.model.setData(idxPropIndirect, True, Qt.EditRole)
            self.qtbot.wait(self.delay)
            cindirect = conf.model.data(idxPropIndirect, Qt.CheckStateRole) != Qt.Unchecked
            assert cindirect == indirect
        conf.treeView.scrollTo(idxPropVal)
        region = conf.treeView.visualRegionForSelection(QItemSelection(idxPropVal, idxPropVal))
        self.qtbot.mouseMove(conf.treeView.viewport(), pos=region.boundingRect().center(), delay=self.delay)
        self.qtbot.mouseClick(conf.treeView.viewport(), Qt.LeftButton, pos=region.boundingRect().center(), delay=self.delay)
        self.qtbot.keyClick(conf.treeView.viewport(), Qt.Key_F2, delay=self.delay)
        self.aw()
        # there are some QT warnings when directly specifying the entertext widget manually, so we try to do without...
        self.qtbot.wait(self.delay*3)
        mw = Services.getService("MainWindow")
        #widgets = [w for w in mw.findChildren(QWidget, "PropertyDelegateEditor") if w.isVisible()]
        #assert len(widgets) == 1
        self.enterText(propVal) #, widgets[0])
        self.qtbot.wait(self.delay)
        if expectedVal is None:
            expectedVal = propVal
        assert conf.model.data(idxPropVal, Qt.DisplayRole) == expectedVal

    def getFilterProperty(self, conf, subConfig, filterName, propName):
        """
        Sets a filter property in the configuration gui service.
        :param conf: the configuration gui service
        :param subConfig: the SubConfiguration instance
        :param filterName: the name of the filter
        :param propName: the name of the property
        :return: the current property value
        """
        idxapp = conf.model.indexOfSubConfig(subConfig)
        # search for filter
        idxFilter = None
        for r in range(conf.model.rowCount(idxapp)):
            idxFilter = conf.model.index(r, 0, idxapp)
            name = conf.model.data(idxFilter, Qt.DisplayRole)
            if name == filterName:
                break
            else:
                idxFilter = None
        assert idxFilter is not None
        # search for property
        idxProp = None
        row = None
        for r in range(conf.model.rowCount(idxFilter)):
            idxProp = conf.model.index(r, 0, idxFilter)
            name = conf.model.data(idxProp, Qt.DisplayRole)
            if name == propName:
                row = r
                break
            else:
                idxProp = None
        assert idxProp is not None
        assert row is not None
        # start the editor by pressing F2 on the property value
        idxPropVal = conf.model.index(row, 1, idxFilter)
        return conf.model.data(idxPropVal, Qt.DisplayRole)


    def getLastLogFrameIdx(self, log):
        """
        Convert the last received log line to a frame index (assuming that the PySimpleStaticFilter has been used)
        :param log: the logging service
        :return: the frame index
        """
        self.qtbot.wait(1000) # log may be delayed
        lidx = log.logWidget.model().index(log.logWidget.model().rowCount(QModelIndex())-1, 2, QModelIndex())
        lastmsg = log.logWidget.model().data(lidx, Qt.DisplayRole)
        assert "received: Sample" in lastmsg
        return int(lastmsg.strip().split(" ")[-1])

    @staticmethod
    def getCurrentFrameIdx(log):
        """
        Same as getLastLogFrameIdx but searches upwards
        :param log: the logging service
        :return: the frame index
        """
        numRows = log.logWidget.model().rowCount(QModelIndex())
        for row in range(numRows-1,0,-1):
            lidx = log.logWidget.model().index(row, 2, QModelIndex())
            lastmsg = log.logWidget.model().data(lidx, Qt.DisplayRole)
            if "received: Sample" in lastmsg:
                return int(lastmsg.strip().split(" ")[-1])

    @staticmethod
    def assertLogItem(log, expectedLevel, expectedMsg):
        found = False
        model = log.logWidget.model()
        numRows = model.rowCount(QModelIndex())
        for row in range(numRows-1,0,-1):
            level = model.data(model.index(row, 1, QModelIndex()), Qt.DisplayRole)
            msg = model.data(model.index(row, 2, QModelIndex()), Qt.DisplayRole)
            if level == expectedLevel and msg in expectedMsg:
                found = True
        if not found:
            raise RuntimeError("expected message %s:%s not found in log", expectedLevel, expectedMsg)

    @staticmethod
    def clearLog(log):
        log.logWidget.clear()

    @staticmethod
    def noWarningsInLog(log, ignore=[]):
        """
        assert that there are no warnings logged
        :param log: the logging service
        :return:
        """
        model = log.logWidget.model()
        numRows = model.rowCount(QModelIndex())
        for row in range(numRows-1,0,-1):
            level = model.data(model.index(row, 1, QModelIndex()), Qt.DisplayRole)
            if level not in ["INFO", "DEBUG", "INTERNAL"]:
                msg = model.data(model.index(row, 2, QModelIndex()), Qt.DisplayRole)
                if not msg in ignore:
                    raise RuntimeError("Warnings or errors found in log: %s(%s)", level, msg)

    def clickDiscardChanges(self):
        """
        Discard the config changes if being asked to.
        :return:
        """
        self.qtbot.keyClick(None, Qt.Key_Tab, delay=self.delay)
        self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)

    def startGraphEditor(self, conf, mw, appName, isComposite=False):
        """
        Start the graph editor of the given application.
        :param conf: the configuration service
        :param mw: the main window
        :param appName: the name of the application to be edited
        :param isComposite: if true, the name is related to a composite filter
        :return: the graph editor view
        """
        oldChildren = mw.findChildren(GraphEditorView, None)
        if isComposite:
            app = conf.configuration().compositeFilterByName(appName)
        else:
            app = conf.configuration().applicationByName(appName)
        # start graph editor
        self.cmContextMenu(conf, conf.model.indexOfSubConfig(app), CM_EDIT_GRAPH)
        newChildren = mw.findChildren(GraphEditorView, None)
        gev = None
        for w in newChildren:
            if w not in oldChildren:
                gev = w
        gev.setMinimumSize(QSize(400, 350))
        return gev

    def select(self, graphEditView, nodes):
        """
        Select the given nodes in the graph editor
        :param graphEditView: The graph editor instances
        :param nodes: the nodes to be selected
        :return:
        """
        pos = nodes[0].nodeGrItem.sceneBoundingRect().center()
        self.qtbot.mouseClick(graphEditView.viewport(), Qt.LeftButton, pos=graphEditView.mapFromScene(pos),
                              delay=self.delay)
        for node in nodes[1:]:
            node.nodeGrItem.setSelected(True)

class BasicTest(GuiTestBase):
    """
    Concrete instance for the test_basic(...) test
    """
    def __init__(self, qtbot, xvfb, keep_open, delay, tmpdir):
        super().__init__(qtbot, xvfb, keep_open, delay, tmpdir)

    def _first(self):
        conf = None
        mw = None
        try:
            mw = Services.getService("MainWindow")
            mw.resize(1980,1080)
            conf = Services.getService("Configuration")
            rec = Services.getService("RecordingControl")
            playback = Services.getService("PlaybackControl")
            log = Services.getService("Logging")
            idxComposites = conf.model.index(0, 0)
            idxApplications = conf.model.index(1, 0)
            # add application
            conf.treeView.setMinimumSize(QSize(300,300))
            conf.treeView.scrollTo(idxApplications)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxApplications, idxApplications))
            self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
            # mouse click does not trigger context menu :(
            #qtbot.mouseClick(conf.treeView.viewport(), Qt.RightButton, pos=region.boundingRect().center())
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADD_APPLICATION))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            app = conf.configuration().applicationByName("application")
            # start graph editor
            gev = self.startGraphEditor(conf, mw, "application")
            self.qtbot.wait(self.delay)
            # create 3 nodes: CSimpleSource, PySimpleStaticFilter, HDF5Writer
            n1 = self.addNodeToGraphEditor(gev, QPoint(20,20),
                                           CM_FILTER_LIBRARY, CM_FILTER_LIBRARY_TESTS, CM_FILTER_LIBRARY_TESTS_NEXXT,
                                           CM_FILTER_LIBRARY_CSIMPLESOURCE)
            self.removeNodeFromGraph(gev, n1)
            n1 = self.addNodeToGraphEditor(gev, QPoint(20,20),
                                           CM_FILTER_LIBRARY, CM_FILTER_LIBRARY_TESTS, CM_FILTER_LIBRARY_TESTS_NEXXT,
                                           CM_FILTER_LIBRARY_CSIMPLESOURCE)
            n2 = self.addNodeToGraphEditor(gev, QPoint(20,80),
                                           CM_FILTER_LIBRARY, CM_FILTER_LIBRARY_TESTS, CM_FILTER_LIBRARY_TESTS_NEXXT,
                                           CM_FILTER_LIBRARY_PYSIMPLESTATICFILTER)
            n3 = self.addNodeToGraphEditor(gev, QPoint(20,140),
                                           CM_FILTER_LIBRARY, CM_FILTER_LIBRARY_HARDDISK, CM_FILTER_LIBRARY_HDF5WRITER)
            n4 = self.addNodeToGraphEditor(gev, QPoint(-120,-60), CM_FILTER_FROM_PYMOD,
                                           "nexxT.tests.interface.SimpleStaticFilter", "SimpleView")
            n5 = self.addNodeToGraphEditor(gev, QPoint(-120, 140), CM_FILTER_FROM_PYMOD,
                                           "nexxT.tests.interface.SimpleStaticFilter", "SimpleView")
            n6 = self.addNodeToGraphEditor(gev, QPoint(20, -60), CM_FILTER_FROM_PYMOD,
                                           "nexxT.tests.interface.SimpleStaticFilter", "SimpleView")
            # auto layout
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_AUTOLAYOUT))
            self.gsContextMenu(gev, QPoint(-120,40))
            self.qtbot.wait(self.delay)
            # rename n4
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_RENAME_NODE))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("view_source"))
            #print(n4, n4.nodeGrItem.sceneBoundingRect().center())
            self.gsContextMenu(gev, n4.nodeGrItem.sceneBoundingRect().center())
            # rename n5
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_RENAME_NODE))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("view_filter"))
            #print(n5, n5.nodeGrItem.sceneBoundingRect().center())
            self.gsContextMenu(gev, n5.nodeGrItem.sceneBoundingRect().center())
            # rename n6
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_RENAME_NODE))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("view_filter2"))
            #print(n6, n6.nodeGrItem.sceneBoundingRect().center())
            self.gsContextMenu(gev, n6.nodeGrItem.sceneBoundingRect().center())
            # setup dynamic input port of HDF5Writer
            n3p = n3.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNINPORT))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("CSimpleSource_out"))
            self.gsContextMenu(gev, n3p)
            # rename the dynamic port
            pp = n3.inPortItems[0].portGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_RENAMEDYNPORT))
            QTimer.singleShot(2*self.delay, lambda: self.enterText("xxx"))
            self.gsContextMenu(gev, pp)
            # remove the dynamic port
            pp = n3.inPortItems[0].portGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_REMOVEDYNPORT))
            QTimer.singleShot(2*self.delay, lambda: self.enterText(""))
            self.gsContextMenu(gev, pp)
            # setup dynamic input port of HDF5Writer
            n3p = n3.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNINPORT))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("CSimpleSource_out"))
            self.gsContextMenu(gev, n3p)
            # set thread of souurce
            n1p = n1.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_SETTHREAD))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("source_thread"))
            self.gsContextMenu(gev, n1p)
            # set thread of HDF5Writer
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_SETTHREAD))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("writer_thread"))
            self.gsContextMenu(gev, n3p)
            # connect the ports
            self.addConnectionToGraphEditor(gev, n1.outPortItems[0], n2.inPortItems[0])
            self.addConnectionToGraphEditor(gev, n3.inPortItems[0], n1.outPortItems[0])
            # set frequency to 10
            self.setFilterProperty(conf, app, "CSimpleSource", "frequency", "10.0")
            # copy a part of the app to a composite filter
            self.select(gev, [n1,n2])
            self.qtbot.keyClick(gev.viewport(), Qt.Key_X, Qt.ControlModifier, delay=self.delay)
            # add composite
            conf.treeView.scrollTo(idxComposites)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxComposites, idxComposites))
            self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDCOMPOSITE))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            self.qtbot.wait(self.delay)
            gevc = self.startGraphEditor(conf, mw, "composite", True)
            assert gevc != gev
            self.qtbot.wait(self.delay)
            self.qtbot.keyClick(gevc.viewport(), Qt.Key_V, Qt.ControlModifier, delay=self.delay)
            gevc_in = gevc.scene().nodes["CompositeInput"]
            gevc_out = gevc.scene().nodes["CompositeOutput"]
            n1 = gevc.scene().nodes["CSimpleSource"]
            n2 = gevc.scene().nodes["PySimpleStaticFilter"]
            # setup dynamic port of gevc_in
            gevc_inp = gevc_in.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNOUTPORT))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("comp_in"))
            self.gsContextMenu(gevc, gevc_inp)
            # setup dynamic ports of gevc_out
            gevc_outp = gevc_out.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNINPORT))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("source"))
            self.gsContextMenu(gevc, gevc_outp)
            gevc_outp = gevc_out.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNINPORT))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("filter"))
            self.gsContextMenu(gevc, gevc_outp)
            # setup connections
            self.addConnectionToGraphEditor(gevc, gevc_out.inPortItems[0], n1.outPortItems[0])
            self.addConnectionToGraphEditor(gevc, gevc_out.inPortItems[1], n2.outPortItems[0])
            # add composite filter to gev
            comp = self.addNodeToGraphEditor(gev, QPoint(20,20), CM_FILTER_FROM_COMPOSITE, "composite")
            nexxT.shiboken.delete(gevc.parent())
            self.qtbot.wait(self.delay)
            # auto layout
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_AUTOLAYOUT))
            self.gsContextMenu(gev, QPoint(-120,40))
            self.qtbot.wait(self.delay)
            self.addConnectionToGraphEditor(gev, comp.outPortItems[0], n3.inPortItems[0])
            # add visualization filters
            self.addConnectionToGraphEditor(gev, comp.outPortItems[0], n4.inPortItems[0])
            self.addConnectionToGraphEditor(gev, comp.outPortItems[1], n5.inPortItems[0])
            self.addConnectionToGraphEditor(gev, comp.outPortItems[1], n6.inPortItems[0])
            # set captions
            self.setFilterProperty(conf, app, "view_source", "caption", "view[0,0]")
            self.setFilterProperty(conf, app, "view_filter", "caption", "view[1,0]")
            self.setFilterProperty(conf, app, "view_filter2", "caption", "filter2")
            # activate and initialize the application
            with self.qtbot.waitSignal(conf.configuration().appActivated):
                conf.configuration().activate("application")
            self.aw()
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_INITIALIZE)
            rec.dockWidget.raise_()
            # application runs for 2 seconds
            self.qtbot.wait(2000)
            # set the folder for the recording service and start recording
            QTimer.singleShot(self.delay, lambda: self.enterText(str(self.tmpdir)))
            rec.actSetDir.trigger()
            recStartFrame = self.getCurrentFrameIdx(log)
            rec.actStart.trigger()
            # record for 2 seconds
            self.qtbot.wait(2000)
            # stop recording
            recStopFrame = self.getCurrentFrameIdx(log)
            rec.actStop.trigger()
            assert recStopFrame >= recStartFrame + 10
            self.qtbot.wait(2000)
            # de-initialize application
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
            # check that the last log message is from the SimpleStaticFilter and it should have received more than 60
            # samples
            assert self.getLastLogFrameIdx(log) >= 60
            # save the configuration file
            prjfile = self.tmpdir / "test_project.json"
            h5file = list(Path(self.tmpdir).glob("*.h5"))
            assert len(h5file) == 1
            h5file = h5file[0]
            QTimer.singleShot(self.delay, lambda: self.enterText(str(prjfile)))
            conf.actSave.trigger()
            gevc = self.startGraphEditor(conf, mw, "composite", True)
            self.removeNodeFromGraph(gevc, gevc.scene().nodes["PySimpleStaticFilter"])
            # load the confiugration file
            assert conf.configuration().dirty()
            QTimer.singleShot(self.delay, lambda: self.clickDiscardChanges())
            QTimer.singleShot(2*self.delay, lambda: self.enterText(str(prjfile)))
            conf.actLoad.trigger()

            # add another application for offline use
            conf.configuration().addNewApplication()
            # start and delete a graph editor for the old application
            gev = self.startGraphEditor(conf, mw, "application")
            self.qtbot.wait(self.delay)
            nexxT.shiboken.delete(gev.parent())
            self.qtbot.wait(self.delay)
            # start the editor for the new application
            gev = self.startGraphEditor(conf, mw, "application_2")
            # start graph editor
            self.qtbot.mouseMove(gev, pos=QPoint(20,20), delay=self.delay)
            # create 2 nodes: HDF5Reader and PySimpleStaticFilter
            n1 = self.addNodeToGraphEditor(gev, QPoint(20,80), CM_FILTER_LIBRARY, CM_FILTER_LIBRARY_HARDDISK,
                                           CM_FILTER_LIBRARY_HDF5READER)
            n2 = self.addNodeToGraphEditor(gev, QPoint(20,80), CM_FILTER_LIBRARY, CM_FILTER_LIBRARY_TESTS,
                                           CM_FILTER_LIBRARY_TESTS_NEXXT, CM_FILTER_LIBRARY_PYSIMPLESTATICFILTER)
            # auto layout
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_AUTOLAYOUT))
            self.gsContextMenu(gev, QPoint(1,1))
            # setup dynamic output port of HDF5Reader
            n1p = n1.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNOUTPORT))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("yyy"))
            self.gsContextMenu(gev, n1p)
            # rename the dynamic port
            pp = n1.outPortItems[0].portGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_RENAMEDYNPORT))
            QTimer.singleShot(2*self.delay, lambda: self.enterText("xxx"))
            self.gsContextMenu(gev, pp)
            self.qtbot.wait(self.delay)
            # remove the dynamic port
            pp = n1.outPortItems[0].portGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_REMOVEDYNPORT))
            QTimer.singleShot(2*self.delay, lambda: self.enterText(""))
            self.gsContextMenu(gev, pp)
            # setup dynamic ports of HDF5Reader using the suggest ports feature
            n1p = n1.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_SUGGEST_DYNPORTS))
            QTimer.singleShot(self.delay*2, lambda: self.enterText(str(h5file)))
            QTimer.singleShot(self.delay*4, lambda: self.enterText(""))
            self.gsContextMenu(gev, n1p)
            # set thread of HDF5Writer
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_SETTHREAD))
            QTimer.singleShot(self.delay*2, lambda: self.enterText("reader_thread"))
            self.gsContextMenu(gev, n1p)
            # connect the ports
            self.addConnectionToGraphEditor(gev, n1.outPortItems[0], n2.inPortItems[0])
            # activate and initialize the application
            with self.qtbot.waitSignal(conf.configuration().appActivated):
                conf.configuration().activate("application_2")
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_INITIALIZE)
            # turn off load monitoring
            self.qtbot.keyClick(self.aw(), Qt.Key_O, Qt.AltModifier, delay=self.delay)
            self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)
            self.qtbot.wait(self.delay)
            # turn on load monitoring
            self.qtbot.keyClick(self.aw(), Qt.Key_O, Qt.AltModifier, delay=self.delay)
            self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)
            self.qtbot.wait(self.delay)
            # turn on port profiling
            self.qtbot.keyClick(self.aw(), Qt.Key_O, Qt.AltModifier, delay=self.delay)
            self.qtbot.keyClick(None, Qt.Key_Down, delay=self.delay)
            self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)
            self.qtbot.wait(self.delay)
            # select file in browser
            playback.dockWidget.raise_()
            self.qtbot.keyClick(playback.browser._lineedit, Qt.Key_A, Qt.ControlModifier)
            self.qtbot.keyClicks(playback.browser._lineedit, str(h5file))
            self.qtbot.keyClick(playback.browser._lineedit, Qt.Key_Return)
            # wait until action start is enabled
            self.qtbot.waitUntil(playback.actStart.isEnabled)
            # play until finished
            playback.actStart.trigger()
            self.qtbot.waitUntil(lambda: not playback.actStart.isEnabled())
            self.qtbot.waitUntil(lambda: not playback.actPause.isEnabled(), timeout=10000)
            # check that the last log message is from the SimpleStaticFilter and it should be in the range of 40-50
            lastFrame = self.getLastLogFrameIdx(log)
            assert recStopFrame-10 <= lastFrame <= recStopFrame+10
            playback.actStepBwd.trigger()
            self.qtbot.wait(self.delay)
            currFrame = self.getLastLogFrameIdx(log)
            assert currFrame == lastFrame - 1
            playback.actStepFwd.trigger()
            self.qtbot.wait(self.delay)
            assert self.getLastLogFrameIdx(log) == lastFrame
            playback.actSeekBegin.trigger()
            firstFrame = self.getLastLogFrameIdx(log)
            assert recStartFrame-10 <= firstFrame <= recStartFrame+10
            playback.actSeekEnd.trigger()
            assert self.getLastLogFrameIdx(log) == lastFrame
            # de-initialize application
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
            conf.actSave.trigger()
            self.qtbot.wait(self.delay)
            # test removal of subconfigs which are still in use
            compidx = conf.model.indexOfSubConfig(conf.configuration().compositeFilterByName("composite"))
            QTimer.singleShot(self.delay, lambda: self.cmContextMenu(conf, compidx, CM_REMOVE_COMPOSITE, "", ""))
            self.qtbot.wait(self.delay * 5)
            assert conf.model.indexOfSubConfig(conf.configuration().compositeFilterByName("composite")) != QModelIndex()
            # test removal of applications
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            QTimer.singleShot(self.delay, lambda: self.cmContextMenu(conf, appidx, CM_REMOVE_APP, ""))
            self.qtbot.wait(self.delay * 4)
            try:
                conf.configuration().applicationByName("application")
                assert False
            except:
                pass
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application_2"))
            QTimer.singleShot(self.delay, lambda: self.cmContextMenu(conf, appidx, CM_REMOVE_APP, ""))
            self.qtbot.wait(self.delay * 4)
            try:
                conf.configuration().applicationByName("application_2")
                assert False
            except:
                pass
            compidx = conf.model.indexOfSubConfig(conf.configuration().compositeFilterByName("composite"))
            QTimer.singleShot(self.delay, lambda: self.cmContextMenu(conf, compidx, CM_REMOVE_COMPOSITE, ""))
            self.qtbot.wait(self.delay * 4)
            try:
                conf.configuration().compositeFilterByName("composite")
                assert False
            except:
                pass

            self.noWarningsInLog(log)
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _second(self):
        conf = None
        mw = None
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            playback = Services.getService("PlaybackControl")
            log = Services.getService("Logging")
            # load recent config
            self.qtbot.keyClick(self.aw(), Qt.Key_R, Qt.ControlModifier, delay=self.delay)
            # this is the offline config
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application_2"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(self.delay)
            assert not playback.actPause.isEnabled()
            self.cmContextMenu(conf, appidx, CM_INIT_APP_AND_OPEN, 0)
            self.qtbot.wait(self.delay)
            assert not playback.actPause.isEnabled()
            playback.actStepFwd.trigger()
            self.qtbot.wait(self.delay)
            firstFrame = self.getLastLogFrameIdx(log)
            self.cmContextMenu(conf, appidx, CM_INIT_APP_AND_PLAY, 0)
            self.qtbot.wait(self.delay)
            self.qtbot.waitUntil(playback.actStart.isEnabled, timeout=10000)
            lastFrame = self.getLastLogFrameIdx(log)
            assert lastFrame >= firstFrame + 10
            # this is the online config
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(2000)
            self.cmContextMenu(conf, appidx, CM_INIT_APP_AND_OPEN, 0)
            self.qtbot.wait(2000)
            self.cmContextMenu(conf, appidx, CM_INIT_APP_AND_PLAY, 0)
            self.qtbot.wait(2000)
            self.noWarningsInLog(log, ignore=[
                "did not find a playback device taking control",
                "The inter-thread connection is set to stopped mode; data sample discarded."])
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def test_first(self):
        """
        first start of nexxT in a clean environment, click through a pretty exhaustive scenario.
        :return:
        """
        QTimer.singleShot(self.delay, self._first)
        startNexT(None, None, [], [], True)

    def test_second(self):
        """
        second start of nexxT, make sure that the history is saved correctly
        :return:
        """
        QTimer.singleShot(self.delay, self._second)
        startNexT(None, None, [], [], True)

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_basic(qtbot, xvfb, keep_open, delay, tmpdir):
    test = BasicTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test_first()
    test.test_second()

class PropertyTest(GuiTestBase):
    """
    Concrete test class for the test_property test case
    """
    def __init__(self, qtbot, xvfb, keep_open, delay, tmpdir):
        super().__init__(qtbot, xvfb, keep_open, delay, tmpdir)

    def _properties(self):
        conf = None
        mw = None
        thefilter_py = (Path(self.tmpdir) / "thefilter.py")
        thefilter_py.write_text(
"""
from nexxT.interface import Filter

class TheFilter(Filter):
    def __init__(self, env):
        super().__init__(False, False, env)
        pc = self.propertyCollection()
        pc.defineProperty("bool_prop", False, "a boolean")
        pc.defineProperty("unbound_float", 7., "an unbound float")
        pc.defineProperty("low_bound_float", 7., "a low bound float", dict(min=-3))
        pc.defineProperty("high_bound_float", 7., "a high bound float", dict(max=123))
        pc.defineProperty("bound_float", 7., "a bound float", dict(min=6, max=1203))
        pc.defineProperty("unbound_int", 7, "an unbound integer")
        pc.defineProperty("low_bound_int", 7, "a low bound integer", dict(min=-3))
        pc.defineProperty("high_bound_int", 7, "a high bound integer", dict(max=123))
        pc.defineProperty("bound_int", 7, "a bound integer", dict(min=6, max=1203))
        pc.defineProperty("string", "str", "an arbitrary string")
        pc.defineProperty("enum", "v1", "an enum", dict(enum=["v1", "v2", "v3"]))
"""
        )
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            idxComposites = conf.model.index(0, 0)
            idxApplications = conf.model.index(1, 0)
            # add application
            conf.treeView.setMinimumSize(QSize(300,300))
            conf.treeView.scrollTo(idxApplications)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxApplications, idxApplications))
            self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
            # mouse click does not trigger context menu :(
            #qtbot.mouseClick(conf.treeView.viewport(), Qt.RightButton, pos=region.boundingRect().center())
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADD_APPLICATION))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            app = conf.configuration().applicationByName("application")
            # start graph editor
            gev = self.startGraphEditor(conf, mw, "application")
            self.qtbot.wait(self.delay)
            # create a node "TheFilter"
            the_filter = self.addNodeToGraphEditor(gev, QPoint(20,20),
                                                   CM_FILTER_FROM_FILE, str(thefilter_py), "TheFilter")
            self.qtbot.keyClick(self.aw(), Qt.Key_Return, delay=self.delay)
            self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)
            logger.info("Filter: %s", repr(the_filter))
            self.setFilterProperty(conf, app, "TheFilter", "bool_prop", [Qt.Key_Down, Qt.Key_Return], "True")
            self.setFilterProperty(conf, app, "TheFilter", "bool_prop", [Qt.Key_Down, Qt.Key_Return], "True")
            self.setFilterProperty(conf, app, "TheFilter", "bool_prop", [Qt.Key_Up, Qt.Key_Return], "False")
            self.setFilterProperty(conf, app, "TheFilter", "bool_prop", [Qt.Key_Up, Qt.Key_Return], "False")
            self.setFilterProperty(conf, app, "TheFilter", "unbound_float", "3.4028235e+38")
            self.setFilterProperty(conf, app, "TheFilter", "unbound_float", "-3.4028235e+38")
            self.setFilterProperty(conf, app, "TheFilter", "low_bound_float", "3.4028235e+38")
            self.setFilterProperty(conf, app, "TheFilter", "low_bound_float", "-3.4028235e+38", "-3.0")
            self.setFilterProperty(conf, app, "TheFilter", "low_bound_float", "-4", "-3.0")
            self.setFilterProperty(conf, app, "TheFilter", "low_bound_float", "-3", "-3.0")
            self.setFilterProperty(conf, app, "TheFilter", "high_bound_float", "-3.4028235e+38")
            self.setFilterProperty(conf, app, "TheFilter", "high_bound_float", "3.4028235e+38", "123.0")
            self.setFilterProperty(conf, app, "TheFilter", "high_bound_float", "124", "123.0")
            self.setFilterProperty(conf, app, "TheFilter", "high_bound_float", "123", "123.0")
            self.setFilterProperty(conf, app, "TheFilter", "bound_float", "-9", "6.0")
            self.setFilterProperty(conf, app, "TheFilter", "bound_float", "5", "6.0")
            self.setFilterProperty(conf, app, "TheFilter", "bound_float", "6.0")
            self.setFilterProperty(conf, app, "TheFilter", "bound_float", "1204", "1203.0")
            self.setFilterProperty(conf, app, "TheFilter", "bound_float", "1203", "1203.0")
            self.setFilterProperty(conf, app, "TheFilter", "unbound_int", "2147483647")
            self.setFilterProperty(conf, app, "TheFilter", "unbound_int", "-2147483648")
            self.setFilterProperty(conf, app, "TheFilter", "low_bound_int", "2147483647")
            self.setFilterProperty(conf, app, "TheFilter", "low_bound_int", "-2147483648", "-2")
            self.setFilterProperty(conf, app, "TheFilter", "low_bound_int", "-4", "-2")
            self.setFilterProperty(conf, app, "TheFilter", "low_bound_int", "-3")
            self.setFilterProperty(conf, app, "TheFilter", "high_bound_int", "-2147483648")
            self.setFilterProperty(conf, app, "TheFilter", "high_bound_int", "2147483647", "21")
            self.setFilterProperty(conf, app, "TheFilter", "high_bound_int", "124", "12")
            self.setFilterProperty(conf, app, "TheFilter", "high_bound_int", "123")
            self.setFilterProperty(conf, app, "TheFilter", "bound_int", "-9", "9")
            self.setFilterProperty(conf, app, "TheFilter", "bound_int", "5", "9")
            self.setFilterProperty(conf, app, "TheFilter", "bound_int", "6")
            self.setFilterProperty(conf, app, "TheFilter", "bound_int", "1204", "120")
            self.setFilterProperty(conf, app, "TheFilter", "bound_int", "1203")
            self.setFilterProperty(conf, app, "TheFilter", "string", "", "str")
            self.setFilterProperty(conf, app, "TheFilter", "string", [Qt.Key_Backspace], "")
            self.setFilterProperty(conf, app, "TheFilter", "string", "an arbitrary value")
            # the enum editor is a combo box, so the text editing does not work here.
            self.setFilterProperty(conf, app, "TheFilter", "enum", [Qt.Key_Down, Qt.Key_Return], "v2")
            self.setFilterProperty(conf, app, "TheFilter", "enum", [Qt.Key_Down, Qt.Key_Return], "v3")
            self.setFilterProperty(conf, app, "TheFilter", "enum", [Qt.Key_Down, Qt.Key_Return], "v3")
            self.setFilterProperty(conf, app, "TheFilter", "enum", [Qt.Key_Up, Qt.Key_Return], "v2")
            self.setFilterProperty(conf, app, "TheFilter", "enum", [Qt.Key_Up, Qt.Key_Return], "v1")
            self.setFilterProperty(conf, app, "TheFilter", "enum", [Qt.Key_Up, Qt.Key_Return], "v1")
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _dynamic_properties(self):
        conf = None
        mw = None
        thefilter_py = (Path(self.tmpdir) / "thedynfilter.py")
        thefilter_py.write_text(
"""
from nexxT.interface import Filter

class TheDynFilter(Filter):
    def __init__(self, env):
        super().__init__(True, True, env)
        
    def onInit(self):
        pc = self.propertyCollection()
        din = self.getDynamicInputPorts()
        dout = self.getDynamicOutputPorts()
        pc.defineProperty("enum_input_ports", "(none)", "help",
                          dict(enum=["(none)"] +[p.name() for p in din], ignoreInconsistentOptions=True))
        pc.defineProperty("enum_output_ports", "(none)", "help",
                          dict(enum=["(none)"] +[p.name() for p in dout], ignoreInconsistentOptions=True))
"""
        )
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            idxComposites = conf.model.index(0, 0)
            idxApplications = conf.model.index(1, 0)
            # add application
            conf.treeView.setMinimumSize(QSize(300, 300))
            conf.treeView.scrollTo(idxApplications)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxApplications, idxApplications))
            self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADD_APPLICATION))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            app = conf.configuration().applicationByName("application")
            # start graph editor
            gev = self.startGraphEditor(conf, mw, "application")
            self.qtbot.wait(self.delay)
            # create a node "TheFilter"
            the_filter = self.addNodeToGraphEditor(gev, QPoint(20, 20),
                                                   CM_FILTER_FROM_FILE, str(thefilter_py), "TheDynFilter")
            self.qtbot.keyClick(self.aw(), Qt.Key_Return, delay=self.delay)
            self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)

            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNINPORT))
            QTimer.singleShot(self.delay * 2, lambda: self.enterText("input_port_1"))
            self.gsContextMenu(gev, the_filter.nodeGrItem.sceneBoundingRect().center())

            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNINPORT))
            QTimer.singleShot(self.delay * 2, lambda: self.enterText("input_port_2"))
            self.gsContextMenu(gev, the_filter.nodeGrItem.sceneBoundingRect().center())

            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDDYNOUTPORT))
            QTimer.singleShot(self.delay * 2, lambda: self.enterText("output_port"))
            self.gsContextMenu(gev, the_filter.nodeGrItem.sceneBoundingRect().center())

            logger.info("Filter: %s", repr(the_filter))
            self.setFilterProperty(conf, app, "TheDynFilter", "enum_input_ports",
                                   [Qt.Key_Down, Qt.Key_Return], "input_port_1")
            self.setFilterProperty(conf, app, "TheDynFilter", "enum_input_ports",
                                   [Qt.Key_Down, Qt.Key_Return], "input_port_2")
            self.setFilterProperty(conf, app, "TheDynFilter", "enum_output_ports",
                                   [Qt.Key_Down, Qt.Key_Return], "output_port")

            cfgfile = str((Path(self.tmpdir) / "dynprops.json").absolute())
            QTimer.singleShot(self.delay, lambda: self.enterText(cfgfile))
            conf.actSave.trigger()

            logger.info("saved application")

            QTimer.singleShot(self.delay, lambda: self.enterText(cfgfile))
            conf.actLoad.trigger()

            logger.info("loaded application")
            app = conf.configuration().applicationByName("application")
            assert self.getFilterProperty(conf, app, "TheDynFilter", "enum_input_ports") == "input_port_2"
            assert self.getFilterProperty(conf, app, "TheDynFilter", "enum_output_ports") == "output_port"


        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _prop_changed(self, variant):
        conf = None
        mw = None
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            log = Services.getService("Logging")
            idxComposites = conf.model.index(0, 0)
            idxApplications = conf.model.index(1, 0)
            # add application
            conf.treeView.setMinimumSize(QSize(300, 300))
            conf.treeView.scrollTo(idxApplications)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxApplications, idxApplications))
            self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADD_APPLICATION))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            app = conf.configuration().applicationByName("application")
            # start graph editor
            gev = self.startGraphEditor(conf, mw, "application")
            self.qtbot.wait(self.delay)
            if variant == "c":
                # create a node "TheFilter"
                the_filter = self.addNodeToGraphEditor(gev, QPoint(20,20),
                                                       CM_FILTER_LIBRARY, CM_FILTER_LIBRARY_TESTS,
                                                       CM_FILTER_LIBRARY_TESTS_NEXXT,
                                                       CM_FILTER_LIBRARY_CPROPERTY_RECEIVER)
                self.setThreadOfNode(gev, the_filter, "non_main")
                self.qtbot.wait(self.delay)
                logger.info("Filter: %s", repr(the_filter))
            elif variant == "py":
                thefilter_py = (Path(self.tmpdir) / "thepropfilter.py")
                thefilter_py.write_text(
"""
from nexxT.interface import Filter
import logging

class CPropertyReceiver(Filter):
    def __init__(self, env):
        super().__init__(False, False, env)

    def onInit(self):
        pc = self.propertyCollection()
        pc.defineProperty("int", 1, "an integer property")
        pc.defineProperty("float", 10.0, "a float property")
        pc.defineProperty("str", "Hello World", "a string property")
        pc.defineProperty("bool", False, "a bool property")
        pc.defineProperty("enum", "v1", "an enum property", options=dict(enum=["v1", "v2", "v3"]))
        pc.propertyChanged.connect(self.propertyChanged)
    
    def onDeinit(self):
        pc = self.propertyCollection()
        pc.propertyChanged.disconnect(self.propertyChanged)
        
    def propertyChanged(self, pc, name):
        v = pc.getProperty(name)
        logging.getLogger(__name__).info("propertyChanged %s is %s", name, v)        
"""
                )
                # create a node "TheFilter"
                the_filter = self.addNodeToGraphEditor(gev, QPoint(20, 20),
                                                       CM_FILTER_FROM_FILE, str(thefilter_py), "CPropertyReceiver")
                self.qtbot.keyClick(self.aw(), Qt.Key_Return, delay=self.delay)
                self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)
            else:
                assert False
            # init application
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(1000)

            self.setFilterProperty(conf, app, "CPropertyReceiver", "int",
                                   ["7", Qt.Key_Return], "7")
            self.setFilterProperty(conf, app, "CPropertyReceiver", "float",
                                   "1.0", "1.0")
            self.setFilterProperty(conf, app, "CPropertyReceiver", "str",
                                   "changed", "changed")
            self.setFilterProperty(conf, app, "CPropertyReceiver", "bool",
                                   [Qt.Key_Down, Qt.Key_Return], "True")
            self.setFilterProperty(conf, app, "CPropertyReceiver", "enum",
                                   [Qt.Key_Down, Qt.Key_Return], "v2")

            expectedLogItems = [
                "propertyChanged int is 7",
                "propertyChanged float is 1" if variant == "c" else "propertyChanged float is 1.0",
                "propertyChanged str is changed",
                "propertyChanged bool is true" if variant == "c" else "propertyChanged bool is True",
                "propertyChanged enum is v2",
            ]

            self.qtbot.wait(1000)

            model = log.logWidget.model()
            numRows = model.rowCount(QModelIndex())
            for row in range(numRows):
                level = model.data(model.index(row, 1, QModelIndex()), Qt.DisplayRole)
                msg = model.data(model.index(row, 2, QModelIndex()), Qt.DisplayRole)
                if len(expectedLogItems) > 0 and level == "INFO" and msg in expectedLogItems[0]:
                    expectedLogItems = expectedLogItems[1:]
                assert level not in ["WARN", "WARNING", "ERROR"]
            assert len(expectedLogItems) == 0
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def test(self):
        """
        test property editing in config editor
        :return:
        """
        QTimer.singleShot(self.delay, self._properties)
        startNexT(None, None, [], [], True)

    def test_dyn(self):
        """
        test property editing in config editor
        :return:
        """
        QTimer.singleShot(self.delay, self._dynamic_properties)
        startNexT(None, None, [], [], True)

    def test_propChangedC(self):
        """
        test connections to propertyChanged signals
        """
        QTimer.singleShot(self.delay, lambda: self._prop_changed("c"))
        startNexT(None, None, [], [], True)

    def test_propChangedPy(self):
        """
        test connections to propertyChanged signals
        """
        QTimer.singleShot(self.delay, lambda: self._prop_changed("py"))
        startNexT(None, None, [], [], True)

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_properties(qtbot, xvfb, keep_open, delay, tmpdir):
    test = PropertyTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test()

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_dyn_properties(qtbot, xvfb, keep_open, delay, tmpdir):
    test = PropertyTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test_dyn()

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_prop_changed_c(qtbot, xvfb, keep_open, delay, tmpdir):
    test = PropertyTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test_propChangedC()

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_prop_changed_py(qtbot, xvfb, keep_open, delay, tmpdir):
    test = PropertyTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test_propChangedPy()

class GuiStateTest(GuiTestBase):
    """
    Concrete test class for the guistate test case
    """
    def __init__(self, qtbot, xvfb, keep_open, delay, tmpdir):
        super().__init__(qtbot, xvfb, keep_open, delay, tmpdir)
        self.prjfile = self.tmpdir / "test_guistate.json"
        self.guistatefile = self.tmpdir / "test_guistate.json.guistate"

    def getMdiWindow(self):
        mw = Services.getService("MainWindow")
        assert len(mw.managedSubplots) == 1
        title = list(mw.managedSubplots.keys())[0]
        return mw.managedSubplots[title]["mdiSubWindow"]

    def _stage0(self):
        conf = None
        mw = None
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            idxApplications = conf.model.index(1, 0)
            # add application
            conf.treeView.setMinimumSize(QSize(300,300))
            conf.treeView.scrollTo(idxApplications)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxApplications, idxApplications))
            self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
            # mouse click does not trigger context menu :(
            #qtbot.mouseClick(conf.treeView.viewport(), Qt.RightButton, pos=region.boundingRect().center())
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADD_APPLICATION))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            app = conf.configuration().applicationByName("application")
            # start graph editor
            gev = self.startGraphEditor(conf, mw, "application")
            self.qtbot.wait(self.delay)
            # create a visualization node
            pysimpleview = self.addNodeToGraphEditor(gev, QPoint(20,20),
                                                     CM_FILTER_LIBRARY, CM_FILTER_LIBRARY_TESTS,
                                                     CM_FILTER_LIBRARY_TESTS_NEXXT, CM_FILTER_LIBRARY_PYSIMPLEVIEW)
            self.qtbot.keyClick(self.aw(), Qt.Key_Return, delay=self.delay)
            self.qtbot.keyClick(self.aw(), Qt.Key_Return, delay=self.delay)
            # save the configuration file
            QTimer.singleShot(self.delay, lambda: self.enterText(str(self.prjfile)))
            conf.actSave.trigger()
            self.prjfile_contents = self.prjfile.read_text("utf-8")
            assert not self.guistatefile.exists()
            # initialize the application, window is shown the first time
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(1000)
            self.getMdiWindow().move(QPoint(37, 63))
            self.qtbot.wait(1000)
            self.mdigeom = self.getMdiWindow().geometry()
            # de-initialize application
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
            assert not self.guistatefile.exists()
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _stage1(self):
        conf = None
        mw = None
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            idxApplications = conf.model.index(1, 0)
            # load recent config
            self.qtbot.keyClick(self.aw(), Qt.Key_R, Qt.ControlModifier, delay=self.delay)
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(1000)
            assert self.mdigeom == self.getMdiWindow().geometry()
            # de-initialize application
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _stage2(self):
        conf = None
        mw = None
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            idxApplications = conf.model.index(1, 0)
            # load recent config
            self.qtbot.keyClick(self.aw(), Qt.Key_R, Qt.ControlModifier, delay=self.delay)
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(1000)
            # should be moved to default location
            assert self.mdigeom != self.getMdiWindow().geometry()
            self.getMdiWindow().move(QPoint(42, 51))
            self.qtbot.wait(1000)
            self.mdigeom = self.getMdiWindow().geometry()
            # because the gui state is not correctly saved when an application is active, the action is disabled in
            # active state
            assert not conf.actSaveWithGuiState.isEnabled()
            # de-initialize application
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
            self.qtbot.wait(self.delay)
            # action should be enabled in non-active state
            assert conf.actSaveWithGuiState.isEnabled()
            conf.actSaveWithGuiState.trigger()
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _stage3(self):
        conf = None
        mw = None
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            idxApplications = conf.model.index(1, 0)
            # load recent config
            self.qtbot.keyClick(self.aw(), Qt.Key_R, Qt.ControlModifier, delay=self.delay)
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(1000)
            # should be moved to default location
            self.getMdiWindow().move(QPoint(17, 22))
            self.qtbot.wait(1000)
            self.mdigeom = self.getMdiWindow().geometry()
            #self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            #self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
            # reload the config
            self.qtbot.keyClick(self.aw(), Qt.Key_R, Qt.ControlModifier, delay=self.delay)
            self.qtbot.wait(1000)
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(1000)
            # should be moved to last location
            assert self.mdigeom == self.getMdiWindow().geometry()
            # de-initialize application
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def test(self):
        """
        first start of nexxT in a clean environment
        :return:
        """
        # create application and move window to non-default location
        QTimer.singleShot(self.delay, self._stage0)
        startNexT(None, None, [], [], True)
        assert self.guistatefile.exists()
        self.guistate_contents = self.guistatefile.read_text("utf-8")
        logger.info("guistate_contents: %s", self.guistate_contents)

        # assert that the window is in the non-default location
        QTimer.singleShot(self.delay, self._stage1)
        startNexT(None, None, [], [], True)
        guistate_contents = self.guistatefile.read_text("utf-8")
        logger.info("guistate_contents: %s", guistate_contents)
        assert self.guistate_contents == guistate_contents

        # remove gui state -> the window should be placed in default location
        os.remove(str(self.guistatefile))
        # assert that window is in default location and save the gui state to the config file
        QTimer.singleShot(self.delay, self._stage2)
        startNexT(None, None, [], [], True)
        guistate_contents = self.guistatefile.read_text("utf-8")
        logger.info("guistate_contents: %s", guistate_contents)
        assert self.guistate_contents != guistate_contents
        self.guistate_contents = guistate_contents

        # assert that the window is in the non-default location
        QTimer.singleShot(self.delay, self._stage1)
        startNexT(None, None, [], [], True)
        guistate_contents = self.guistatefile.read_text("utf-8")
        logger.info("guistate_contents: %s", guistate_contents)
        assert self.guistate_contents == guistate_contents

        # remove gui state -> the window should still be placed in non-default location
        os.remove(str(self.guistatefile))
        QTimer.singleShot(self.delay, self._stage1)
        startNexT(None, None, [], [], True)
        guistate_contents = self.guistatefile.read_text("utf-8")
        logger.info("guistate_contents: %s", guistate_contents)
        assert self.guistate_contents == guistate_contents

        # check that re-opening the same config correctly restores the gui state
        QTimer.singleShot(self.delay, self._stage3)
        startNexT(None, None, [], [], True)

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_guistate(qtbot, xvfb, keep_open, delay, tmpdir):
    test = GuiStateTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test()

class DeadlockTestIssue25(GuiTestBase):
    """
    Concrete test class for the test_property test case
    """
    def __init__(self, qtbot, xvfb, keep_open, delay, tmpdir, change_conn):
        super().__init__(qtbot, xvfb, keep_open, delay, tmpdir)
        self.change_conn = change_conn
        self.tmpdir = tmpdir

    def _stage0(self):
        tmpdir = self.tmpdir
        conf = None
        mw = None
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            log = Services.getService("Logging")
            # load recent config
            if self.change_conn is None:
                fn = str((Path(__file__).parent.parent / "core" / "test_deadlock.json").absolute())
            else:
                cfg = json.load((Path(__file__).parent.parent / "core" / "test_deadlock.json").open("rb"))
                conns = cfg["applications"][0]["connections"]
                conns = conns[:self.change_conn] + conns[self.change_conn+1:]
                cfg["applications"][0]["connections"] = conns
                fn = Path(tmpdir) / "test_deadlock.json"
                with fn.open("w") as fp:
                    json.dump(cfg, fp)
                fn = str(fn.absolute())
            logger.info("laoding fn=%s", fn)
            QTimer.singleShot(self.delay, lambda: self.enterText(fn))
            conf.actLoad.trigger()
            self.qtbot.wait(self.delay*2)

            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("deadlock"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            if self.change_conn in [None, 0, 2]:
                self.qtbot.wait(1000)
                logMsg = "This graph is not deadlock-safe. A cycle has been found in the thread graph: main->compute->main"
                self.noWarningsInLog(log, ignore=[logMsg])
                self.assertLogItem(log, "ERROR", logMsg)
            else:
                self.qtbot.wait(10000)
                self.noWarningsInLog(log)

            # assert that the samples arrived in the correct order
            def assertSampleOrder():
                numRows = log.logWidget.model().rowCount(QModelIndex())
                filters = {}
                for row in range(numRows):
                    lidx = log.logWidget.model().index(row, 2, QModelIndex())
                    msg = log.logWidget.model().data(lidx, Qt.DisplayRole)
                    if "received: Sample" in msg:
                        flt = msg.split(":")[0]
                        idx = int(msg.strip().split(" ")[-1])
                        if not flt in filters:
                            assert idx == 1
                        else:
                            assert idx == filters[flt] + 1
                        filters[flt] = idx
            # at the moment we do not let the user start these configs, but the sample order is still ok with no samples
            # at all
            assertSampleOrder()
            logger.info("finishing")
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def test(self):
        QTimer.singleShot(self.delay, self._stage0)
        startNexT(None, None, [], [], True)
        self.qtbot.wait(1000)

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
@pytest.mark.timeout(60, method="thread")
@pytest.mark.parametrize("change_conn", [None, 0, 1, 2, 3])
def test_deadlock_issue25(qtbot, xvfb, keep_open, delay, tmpdir, change_conn):
    test = DeadlockTestIssue25(qtbot, xvfb, keep_open, delay, tmpdir, change_conn)
    test.test()

class ExecutionOrderTest(GuiTestBase):
    """
    Concrete test class for the test_property test case
    """
    def __init__(self, qtbot, xvfb, keep_open, delay, tmpdir):
        super().__init__(qtbot, xvfb, keep_open, delay, tmpdir)

    def _stage0(self):
        # binary tree execution order
        conf = None
        mw = None
        try:
            # execution order config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")

            # this is the offline config
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("binarytree"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(3000)
            log = Services.getService("Logging")

            model = log.logWidget.model()
            numRows = model.rowCount(QModelIndex())
            # depth first execution order
            expected = [(1,1), (2,1), (2,2), (1,2), (2,3), (2,4)]
            order = []
            for row in range(numRows):
                msg = model.data(model.index(row, 2, QModelIndex()), Qt.DisplayRole)
                M = re.match(r'^layer(\d)_f(\d)', msg)
                if M is not None:
                    item = (int(M.group(1)),int(M.group(2)))
                    order.append( item )
            for i, item in enumerate(order):
                assert item == expected[i % len(expected)]
            assert len(order) >= len(expected)
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _stage1(self):
        # recursion single thread execution order
        conf = None
        mw = None
        try:
            # execution order config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")

            # this is the offline config
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("recursion_single_thread"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(3000)
            log = Services.getService("Logging")

            model = log.logWidget.model()
            numRows = model.rowCount(QModelIndex())
            expected = [(1, "recursive", "in"), (1, "filter", None), (1, "recursive", "recursive")]
            order = []
            for row in range(numRows):
                msg = model.data(model.index(row, 2, QModelIndex()), Qt.DisplayRole)
                M = re.match(r'^([^:]+):received: Sample (\d+)(.*)', msg)
                if M is not None:
                    M2 = re.match(r" on port (.*)$", M.group(3))
                    item = (int(M.group(2)), M.group(1), M2.group(1) if M2 is not None else None)
                    order.append( item )
            k = 0
            for i, item in enumerate(order):
                if i % len(expected) == 0:
                    k += 1
                eitem = expected[i % len(expected)]
                eitem = (k,) + eitem[1:]
                assert item == eitem
            assert len(order) >= len(expected)
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _stage2(self):
        self._throughput("singlethread")

    def _stage3(self):
        self._throughput("multithread")

    def _throughput(self, threadmode):
        # throughput
        conf = None
        mw = None
        try:
            # execution order config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")

            app = conf.configuration().applicationByName("binarytree")
            # start graph editor
            self.setFilterProperty(conf, app, "layer1_f1", "log_throughput_at_end", [Qt.Key_Down, Qt.Key_Return], "True")
            self.setFilterProperty(conf, app, "source", "frequency", "10000.0")

            if threadmode == "multithread":
                graph = app.getGraph()
                for n in graph.allNodes():
                    mockup = graph.getMockup(n)
                    pc = mockup.getPropertyCollectionImpl()
                    pc.children()[0].setProperty("thread", "thread_"+n)

            self.qtbot.keyClick(self.aw(), Qt.Key_L, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(LM_WARNING)
            # this is the offline config
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("binarytree"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(3000)
            log = Services.getService("Logging")
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
            self.qtbot.wait(2*self.delay)

            model = log.logWidget.model()
            numRows = model.rowCount(QModelIndex())
            throughput = None
            for row in range(numRows):
                msg = model.data(model.index(row, 2, QModelIndex()), Qt.DisplayRole)
                logger.info(repr(msg))
                M = re.match(r'layer1_f1:throughput: (\d+.\d+) samples/second', msg)
                if M is not None:
                    throughput = float(M.group(1))
            if threadmode == "multithread":
                self.record_property("multithread_smp_per_sec", throughput)
                assert throughput >= 750
            else:
                self.record_property("throughput_smp_per_sec", throughput)
                assert throughput >= 4500
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def test(self, record_property):
        """
        test property editing in config editor
        :return:
        """
        self.record_property = record_property
        QTimer.singleShot(self.delay, self._stage0)
        startNexT(str(Path(__file__).parent.parent / "core" / "test_tree_order.json"), None, [], [], True)
        QTimer.singleShot(self.delay, self._stage1)
        startNexT(str(Path(__file__).parent.parent / "core" / "test_tree_order.json"), None, [], [], True)
        QTimer.singleShot(self.delay, self._stage2)
        startNexT(str(Path(__file__).parent.parent / "core" / "test_tree_order.json"), None, [], [], True)
        QTimer.singleShot(self.delay, self._stage3)
        startNexT(str(Path(__file__).parent.parent / "core" / "test_tree_order.json"), None, [], [], True)


@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_executionOrder(qtbot, xvfb, keep_open, delay, tmpdir, record_property):
    test = ExecutionOrderTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test(record_property)

class ReloadTest(GuiTestBase):
    """
    Concrete test class for the guistate test case
    """
    def __init__(self, qtbot, xvfb, keep_open, delay, tmpdir):
        super().__init__(qtbot, xvfb, keep_open, delay, tmpdir)
        self.prjfile = self.tmpdir / "test_reload.json"
        self.guistatefile = self.tmpdir / "test_reload.json.guistate"

    def generateFilter(self, messageAtOpen):
        myfilter = self.tmpdir / "myfilter.py"
        myfilter.write_text("""
import logging
from nexxT.Qt.QtWidgets import QLabel
from nexxT.interface import Filter, InputPort, Services

logger = logging.getLogger(__name__)

class MyFilter(Filter): # almost same as SimpleView
    def __init__(self, env):
        super().__init__(False, False, env)
        self.inputPort = InputPort(False, "in", env)
        self.addStaticPort(self.inputPort)
        self.propertyCollection().defineProperty("caption", "view", "Caption of view window.")
        self.label = None

    def onOpen(self):
        caption = self.propertyCollection().getProperty("caption")
        mw = Services.getService("MainWindow")
        self.label = QLabel()
        self.label.setMinimumSize(100, 20)
        mw.subplot(caption, self, self.label)
        logger.info("%s")

    def onPortDataChanged(self, inputPort):
        dataSample = inputPort.getData()
        if dataSample.getDatatype() == "text/utf8":
            self.label.setText(dataSample.getContent().data().decode("utf8"))

    def onClose(self):
        mw = Services.getService("MainWindow")
        mw.releaseSubplot(self.label)
        self.label = None     
""" % messageAtOpen, encoding="utf-8")
        return Path(myfilter)

    def getMdiWindow(self):
        mw = Services.getService("MainWindow")
        assert len(mw.managedSubplots) == 1
        title = list(mw.managedSubplots.keys())[0]
        return mw.managedSubplots[title]["mdiSubWindow"]

    def _stage0(self):
        conf = None
        mw = None
        try:
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            log = Services.getService("Logging")
            idxApplications = conf.model.index(1, 0)
            # add application
            conf.treeView.setMinimumSize(QSize(300,300))
            conf.treeView.scrollTo(idxApplications)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxApplications, idxApplications))
            self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
            # mouse click does not trigger context menu :(
            #qtbot.mouseClick(conf.treeView.viewport(), Qt.RightButton, pos=region.boundingRect().center())
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADD_APPLICATION))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            app = conf.configuration().applicationByName("application")
            # start graph editor
            gev = self.startGraphEditor(conf, mw, "application")
            self.qtbot.wait(self.delay)
            # create a visualization node
            pyfile = str(self.generateFilter("myfilter version 1").absolute())
            logger.info("pyfile=%s", pyfile)
            pysimpleview = self.addNodeToGraphEditor(gev, QPoint(20,20), CM_FILTER_FROM_FILE,
                                                     pyfile, "MyFilter")
            self.qtbot.keyClick(self.aw(), Qt.Key_Return, delay=self.delay)
            self.qtbot.keyClick(self.aw(), Qt.Key_Return, delay=self.delay)
            # init application
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(1000)
            # note: the following depends on --forked isolation which is broken with PySide6
            self.assertLogItem(log, "INFO", "myfilter version 1")
            # move the window to non-standard position
            self.getMdiWindow().move(QPoint(37, 63))
            self.qtbot.wait(1000)
            mdigeom = self.getMdiWindow().geometry()
            # generate new filter version
            self.generateFilter("myfilter version 2")
            # reload (without config being saved, no gui state)
            self.qtbot.keyClick(self.aw(), Qt.Key_P, Qt.ControlModifier, delay=self.delay)
            self.qtbot.wait(1000)
            assert mdigeom == self.getMdiWindow().geometry()
            self.assertLogItem(log, "INFO", "myfilter version 2")
            # save the configuration file
            QTimer.singleShot(self.delay, lambda: self.enterText(str(self.prjfile)))
            conf.actSave.trigger()
            self.prjfile_contents = self.prjfile.read_text("utf-8")
            assert not self.guistatefile.exists()
            # move window
            self.getMdiWindow().move(QPoint(31, 23))
            self.qtbot.wait(1000)
            mdigeom = self.getMdiWindow().geometry()
            # generate new filter version
            self.generateFilter("myfilter version 3")
            # reload (without config being saved, no gui state)
            self.qtbot.keyClick(self.aw(), Qt.Key_P, Qt.ControlModifier, delay=self.delay)
            self.qtbot.wait(1000)
            assert mdigeom == self.getMdiWindow().geometry()
            self.assertLogItem(log, "INFO", "myfilter version 3")
            # save again to create gui state
            # can't save again without setting config to dirty
            conf._dirtyChanged(True)
            assert conf.actSave.isEnabled()
            conf.actSave.trigger()
            assert self.guistatefile.exists()
            # move window
            self.getMdiWindow().move(QPoint(17, 11))
            self.qtbot.wait(1000)
            mdigeom = self.getMdiWindow().geometry()
            # generate new filter version
            self.generateFilter("myfilter version 4")
            # reload (without config being saved, no gui state)
            self.qtbot.keyClick(self.aw(), Qt.Key_P, Qt.ControlModifier, delay=self.delay)
            self.qtbot.wait(1000)
            assert mdigeom == self.getMdiWindow().geometry()
            self.assertLogItem(log, "INFO", "myfilter version 4")
            # de-initialize application
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
            self.generateFilter("myfilter version 5")
            # reload
            self.qtbot.keyClick(self.aw(), Qt.Key_P, Qt.ControlModifier, delay=self.delay)
            self.qtbot.wait(1000)
            appidx = conf.model.indexOfSubConfig(conf.configuration().applicationByName("application"))
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            self.qtbot.wait(1000)
            self.assertLogItem(log, "INFO", "myfilter version 5")
            self.qtbot.keyClick(self.aw(), Qt.Key_C, Qt.AltModifier, delay=self.delay)
            self.activateContextMenu(CONFIG_MENU_DEINITIALIZE)
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def test(self):
        """
        first start of nexxT in a clean environment
        :return:
        """
        # create application and move window to non-default location
        QTimer.singleShot(self.delay, self._stage0)
        startNexT(None, None, [], [], True)

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_reload(qtbot, xvfb, keep_open, delay, tmpdir):
    test = ReloadTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test()


class VariablesTest(GuiTestBase):
    """
    Concrete test class for the test_variables test case
    """

    def __init__(self, qtbot, xvfb, keep_open, delay, tmpdir):
        super().__init__(qtbot, xvfb, keep_open, delay, tmpdir)

    def _variables(self):
        conf = None
        mw = None
        thefilter_py = (Path(self.tmpdir) / "thefilter.py")
        thefilter_py.write_text("""\
import logging
from nexxT.interface import Filter

logger = logging.getLogger(__name__)

class TheFilter(Filter):
    def __init__(self, env):
        super().__init__(False, False, env)
        pc = self.propertyCollection()
        pc.defineProperty("bool_prop", False, "a boolean")
        pc.defineProperty("unbound_float", 7., "an unbound float")
        pc.defineProperty("low_bound_float", 7., "a low bound float", dict(min=-3))
        pc.defineProperty("high_bound_float", 7., "a high bound float", dict(max=123))
        pc.defineProperty("bound_float", 7., "a bound float", dict(min=6, max=1203))
        pc.defineProperty("unbound_int", 7, "an unbound integer")
        pc.defineProperty("low_bound_int", 7, "a low bound integer", dict(min=-3))
        pc.defineProperty("high_bound_int", 7, "a high bound integer", dict(max=123))
        pc.defineProperty("bound_int", 7, "a bound integer", dict(min=6, max=1203))
        pc.defineProperty("string", "str", "an arbitrary string")
        pc.defineProperty("enum", "v1", "an enum", dict(enum=["v1", "v2", "v3"]))
        
    def onOpen(self):
        pc = self.propertyCollection()
        for n in ["bool_prop", "unbound_float", "low_bound_float", "high_bound_float", "bound_float",
                  "unbound_int", "low_bound_int", "high_bound_int", "bound_int", "string", "enum"]:
            logger.info("getProperty(%s) = %s", n, repr(pc.getProperty(n)))
"""
        )
        try:
            # load last config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            log = Services.getService("Logging")
            idxComposites = conf.model.index(0, 0)
            idxApplications = conf.model.index(1, 0)
            idxVariables = conf.model.index(2, 0)
            # add application
            conf.treeView.setMinimumSize(QSize(300, 300))
            conf.treeView.scrollTo(idxApplications)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxApplications, idxApplications))
            self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
            # mouse click does not trigger context menu :(
            # qtbot.mouseClick(conf.treeView.viewport(), Qt.RightButton, pos=region.boundingRect().center())
            QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADD_APPLICATION))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            app = conf.configuration().applicationByName("application")
            appidx = conf.model.indexOfSubConfig(app)
            # start graph editor
            gev = self.startGraphEditor(conf, mw, "application")
            self.qtbot.wait(self.delay)
            # create a node "TheFilter"
            the_filter = self.addNodeToGraphEditor(gev, QPoint(20, 20),
                                                   CM_FILTER_FROM_FILE, str(thefilter_py), "TheFilter")
            self.qtbot.keyClick(self.aw(), Qt.Key_Return, delay=self.delay)
            self.qtbot.keyClick(None, Qt.Key_Return, delay=self.delay)
            logger.info("Filter: %s", repr(the_filter))
            # add variables
            self.aw()
            for name, value in [("BFALSE", "False"), ("BTRUE", "True"),
                                ("FHIGH", "3.4028235e+38"), ("FLOW", "-3.4028235e+38"),
                                ("IHIGH", "2147483647"), ("ILOW", "-2147483648"),
                                ("IM4", "-4"), ("I1", "1"),
                                ("EV1", "v1"), ("EV2", "v2"), ("EV3", "v3")]:
                conf.treeView.scrollTo(idxVariables)
                region = conf.treeView.visualRegionForSelection(QItemSelection(idxVariables, idxVariables))
                self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
                QTimer.singleShot(self.delay, lambda: self.activateContextMenu(CM_ADDVARIABLE))
                QTimer.singleShot(self.delay * 2, lambda: self.enterText(name))
                conf._execTreeViewContextMenu(region.boundingRect().center())
                def find_var_index(parentIndex, varname):
                    m = conf.model
                    for r in range(m.rowCount(parentIndex)):
                        idx = m.index(r, 0, parentIndex)
                        t = m.data(idx, Qt.DisplayRole)
                        if t == varname:
                            return m.index(r, 1, parentIndex)
                idx = find_var_index(idxVariables, name)
                assert idx is not None
                conf.treeView.scrollTo(idx)
                region = conf.treeView.visualRegionForSelection(QItemSelection(idx, idx))
                self.qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=self.delay)
                self.qtbot.mouseClick(conf.treeView.viewport(), Qt.LeftButton, pos=region.boundingRect().center(),
                                      delay=self.delay)
                self.qtbot.keyClick(conf.treeView.viewport(), Qt.Key_F2, delay=self.delay)
                self.aw()
                mw = Services.getService("MainWindow")
                QTimer.singleShot(self.delay*2, lambda: self.enterText(value))
                self.qtbot.wait(self.delay*3)
                assert conf.model.data(idx, Qt.DisplayRole) == value
                logger.info("Added variable %s=%s", name, value)
            tests = dict(
                bool_prop=[("$BFALSE", repr(False)), ("$BTRUE", repr(True)), ("$NONEXIST", repr(False))],
                unbound_float=[("$FHIGH", repr(3.4028235e+38)), ("$FLOW", repr(-3.4028235e+38)),
                               ("$NONEXIST", repr(0.0))],
                low_bound_float=[("$FHIGH", repr(3.4028235e+38)), ("$FLOW", repr(-3.0)), ("$IM4", repr(-3.0)),
                                 ("$I1", repr(1.0)), ("$NONEXIST", repr(0.0))],
                high_bound_float=[("$FHIGH", repr(123.0)), ("$FLOW", repr(-3.4028235e+38)), ("$IM4", repr(-4.0)),
                                  ("$I1", repr(1.0)), ("$NONEXIST", repr(0.0))],
                bound_float=[("$FHIGH", repr(1203.0)), ("$FLOW", repr(6.0)),
                             ("$NONEXIST", repr(6.0))],
                unbound_int=[("$IHIGH", repr(2147483647)), ("$ILOW", repr(-2147483648)), ("$IM4", repr(-4)),
                             ("$I1", repr(1)), ("$NONEXIST", repr(0))],
                low_bound_int=[("$IHIGH", repr(2147483647)), ("$ILOW", repr(-3)), ("$IM4", repr(-3)),
                               ("$I1", repr(1)), ("$NONEXIST", repr(0))],
                high_bound_int=[("$IHIGH", repr(123)), ("$ILOW", repr(-2147483648)), ("$IM4", repr(-4)),
                                ("$I1", repr(1)), ("$NONEXIST", repr(0))],
                bound_int=[("$IHIGH", repr(1203)), ("$ILOW", repr(6)), ("$IM4", repr(6)),
                           ("$I1", repr(6)), ("$NONEXIST", repr(6))],
                string=[("$IHIGH", repr("2147483647")), ("$FILTERNAME", repr("TheFilter")),
                        ("$FULLQUALIFIEDFILTERNAME", repr("/TheFilter")), ("$COMPOSITENAME", repr("<root>")),
                        ("$APPNAME", repr("application"))],
                enum=[("$EV1", repr("v1")), ("$EV2", repr("v2")), ("$EV3", repr("v3")), ("$NONEXIST", repr("v1"))]
            )
            for tidx in range(max(len(tests[k]) for k in tests)):
                expectedLogs = []
                logger.info("test_gui:variables:start test cycle")
                for k in tests:
                    if tidx < len(tests[k]):
                        t = tests[k][tidx]
                        logger.info("test_gui:variables:set property %s->%s", k, t[0])
                        self.setFilterProperty(conf, app, "TheFilter", k, t[0], t[0], indirect=True)
                        expectedLogs.append("getProperty(%s) = %s" % (k, t[1]))
                logger.info("test_gui:variables:Initializing app")
                self.cmContextMenu(conf, appidx, CM_INIT_APP)
                logger.info("test_gui:variables:wait")
                self.qtbot.wait(1000)
                for logMsg in expectedLogs:
                    logger.info("test_gui:variables:checklog")
                    self.assertLogItem(log, "INFO", logMsg)
                logger.info("test_gui:variables:clearlog")
                self.clearLog(log)
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    self.aw()
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def _composite(self):
        conf = None
        mw = None
        thefilter_py = (Path(self.tmpdir) / "thefilter.py")
        thefilter_py.write_text("""\
import logging
from nexxT.interface import Filter

logger = logging.getLogger(__name__)

class TheFilter(Filter):
    def __init__(self, env):
        super().__init__(False, False, env)
        pc = self.propertyCollection()
        pc.defineProperty("string", "str", "an arbitrary string")

    def onOpen(self):
        pc = self.propertyCollection()
        logger.info("getProperty(string) = %s", repr(pc.getProperty("string")))
""")
        config_file = Path(self.tmpdir) / "composite.json"
        config_file.write_text((Path(__file__).parent / "composite.json").read_text())
        try:
            # load config
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            log = Services.getService("Logging")

            conf.loadConfig(str(config_file))
            logger.info("test_gui:variables:Initializing app")
            app = conf.configuration().applicationByName("application")
            appidx = conf.model.indexOfSubConfig(app)
            self.cmContextMenu(conf, appidx, CM_INIT_APP)
            logger.info("test_gui:variables:wait")
            self.qtbot.wait(1000)
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/comp2/RootRef : root'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/comp2/Comp1Ref : b'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/comp2/Comp2Ref : c'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/comp2/Comp3Ref : $COMP3VAR'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/comp3/RootRef : root'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/comp3/Comp1Ref : b'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/comp3/Comp2Ref : $COMP2VAR'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/comp3/Comp3Ref : d'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/RootRef : root'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/Comp1Ref : b'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/Comp2Ref : $COMP2VAR'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_2/Comp3Ref : $COMP3VAR'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/comp2/RootRef : root'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/comp2/Comp1Ref : a'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/comp2/Comp2Ref : c'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/comp2/Comp3Ref : $COMP3VAR'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/comp3/RootRef : root'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/comp3/Comp1Ref : a'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/comp3/Comp2Ref : $COMP2VAR'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/comp3/Comp3Ref : d'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/RootRef : root'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/Comp1Ref : a'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/Comp2Ref : $COMP2VAR'")
            self.assertLogItem(log, "INFO", "getProperty(string) = '/comp1_1/Comp3Ref : $COMP3VAR'")
        finally:
            if not self.keep_open:
                if conf.configuration().dirty():
                    self.aw()
                    QTimer.singleShot(self.delay, self.clickDiscardChanges)
                mw.close()

    def test(self):
        """
        test property editing in config editor
        :return:
        """
        QTimer.singleShot(self.delay, self._variables)
        startNexT(None, None, [], [], True)


    def test_composite(self):
        """
        test property editing in config editor
        :return:
        """
        QTimer.singleShot(self.delay, self._composite)
        startNexT(None, None, [], [], True)


@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_variables(qtbot, xvfb, keep_open, delay, tmpdir):
    test = VariablesTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test()

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_variablesComposite(qtbot, xvfb, keep_open, delay, tmpdir):
    test = VariablesTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test_composite()

