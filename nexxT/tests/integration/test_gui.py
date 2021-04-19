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

import os
import logging
from pathlib import Path
import pytest
import shiboken2
from PySide2.QtCore import QItemSelection, Qt, QTimer, QSize, QPoint, QModelIndex
from PySide2.QtWidgets import QGraphicsSceneContextMenuEvent, QWidget, QApplication, QTreeView
from nexxT.core.AppConsole import startNexT
from nexxT.interface import Services
from nexxT.services.gui.GraphEditorView import GraphEditorView

logger = logging.getLogger(__name__)

@pytest.fixture
def keep_open(request):
    return request.config.getoption("--keep-open")

# context menu actions
class ContextMenuEntry(str):
    pass
CM_ADD_APPLICATION = ContextMenuEntry("Add application")
CM_EDIT_GRAPH = ContextMenuEntry("Edit graph")
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
CONFIG_MENU_DEINITIALIZE = ContextMenuEntry("Deinitialize")
CONFIG_MENU_INITIALIZE = ContextMenuEntry("Initialize")

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
            while act.menu() is not None and act.menu().activeAction() is not None:
                act = act.menu().activeAction()
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

    def setFilterProperty(self, conf, subConfig, filterName, propName, propVal, expectedVal=None):
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
        conf.treeView.scrollTo(idxPropVal)
        region = conf.treeView.visualRegionForSelection(QItemSelection(idxPropVal, idxPropVal))
        self.qtbot.mouseMove(conf.treeView.viewport(), pos=region.boundingRect().center(), delay=self.delay)
        self.qtbot.mouseClick(conf.treeView.viewport(), Qt.LeftButton, pos=region.boundingRect().center(), delay=self.delay)
        self.qtbot.keyClick(conf.treeView.viewport(), Qt.Key_F2, delay=self.delay)
        self.aw()
        mw = Services.getService("MainWindow")
        self.enterText(propVal, mw.findChild(QWidget, "PropertyDelegateEditor"))
        self.qtbot.wait(self.delay)
        if expectedVal is None:
            expectedVal = propVal
        assert conf.model.data(idxPropVal, Qt.DisplayRole) == expectedVal

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
        self.cmContextMenu(conf, conf.model.indexOfSubConfig(app), 1)
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
            shiboken2.delete(gevc.parent())
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
            shiboken2.delete(gev.parent())
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
            self.qtbot.wait(1000)
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
            self.qtbot.wait(1000)
            assert not playback.actPause.isEnabled()
            self.cmContextMenu(conf, appidx, CM_INIT_APP_AND_OPEN, 0)
            self.qtbot.wait(1000)
            assert not playback.actPause.isEnabled()
            playback.actStepFwd.trigger()
            self.qtbot.wait(1000)
            firstFrame = self.getLastLogFrameIdx(log)
            self.cmContextMenu(conf, appidx, CM_INIT_APP_AND_PLAY, 0)
            self.qtbot.wait(1000)
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

    def test(self):
        """
        test property editing in config editor
        :return:
        """
        QTimer.singleShot(self.delay, self._properties)
        startNexT(None, None, [], [], True)

@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_properties(qtbot, xvfb, keep_open, delay, tmpdir):
    test = PropertyTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test()

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

    def test(self):
        """
        first start of nexxT in a clean environment, click through a pretty exhaustive scenario.
        :return:
        """
        # create application and move window to non-default location
        QTimer.singleShot(self.delay, self._stage0)
        startNexT(None, None, [], [], True)
        assert self.guistatefile.exists()
        self.guistate_contents = self.guistatefile.read_text("utf-8")
        logger.info("guistate_contents: %s", self.guistate_contents)

        QTimer.singleShot(self.delay, self._stage1)
        startNexT(None, None, [], [], True)
        guistate_contents = self.guistatefile.read_text("utf-8")
        logger.info("guistate_contents: %s", guistate_contents)
        assert self.guistate_contents == guistate_contents

        # remove gui state -> the window should be placed in default location
        os.remove(str(self.guistatefile))
        QTimer.singleShot(self.delay, self._stage2)
        startNexT(None, None, [], [], True)
        guistate_contents = self.guistatefile.read_text("utf-8")
        logger.info("guistate_contents: %s", guistate_contents)
        assert self.guistate_contents != guistate_contents
        self.guistate_contents = guistate_contents

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



@pytest.mark.gui
@pytest.mark.parametrize("delay", [300])
def test_guistate(qtbot, xvfb, keep_open, delay, tmpdir):
    test = GuiStateTest(qtbot, xvfb, keep_open, delay, tmpdir)
    test.test()
