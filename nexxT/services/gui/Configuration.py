# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the Configuration GUI service of the nexxT framework.
"""

import logging
import shiboken2
from PySide2.QtCore import (Qt, QSettings, QByteArray, QDataStream, QIODevice)
from PySide2.QtGui import QPainter
from PySide2.QtWidgets import (QTreeView, QAction, QStyle, QApplication, QFileDialog, QAbstractItemView, QMessageBox,
                               QHeaderView, QMenu, QDockWidget, QGraphicsView)
from nexxT.interface import Services, FilterState
from nexxT.core.Configuration import Configuration
from nexxT.core.Utils import assertMainThread
from nexxT.services.SrvConfiguration import MVCConfigurationBase, ConfigurationModel, ITEM_ROLE
from nexxT.services.gui.PropertyDelegate import PropertyDelegate
from nexxT.services.gui.GraphEditor import GraphScene

logger = logging.getLogger(__name__)

class MVCConfigurationGUI(MVCConfigurationBase): # pragma: no cover
    """
    GUI implementation of MVCConfigurationBase
    """

    def __init__(self, configuration):
        super().__init__(configuration)
        assertMainThread()
        srv = Services.getService("MainWindow")
        srv.aboutToClose.connect(self._aboutToClose)
        confMenu = srv.menuBar().addMenu("&Configuration")
        toolBar = srv.getToolBar()

        configuration.configNameChanged.connect(self._configNameChanged)
        configuration.dirtyChanged.connect(self._dirtyChanged)

        self.actLoad = QAction(QApplication.style().standardIcon(QStyle.SP_DialogOpenButton), "Open config", self)
        self.actLoad.triggered.connect(self._execLoad)
        self.actSave = QAction(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton), "Save config", self)
        self.actSave.triggered.connect(self.saveConfig)
        self.actNew = QAction(QApplication.style().standardIcon(QStyle.SP_FileIcon), "New config", self)
        self.actNew.triggered.connect(self._execNew)

        self.actActivate = QAction(QApplication.style().standardIcon(QStyle.SP_ArrowUp), "Initialize", self)
        self.actActivate.triggered.connect(self.activate)
        self.actDeactivate = QAction(QApplication.style().standardIcon(QStyle.SP_ArrowDown), "Deinitialize", self)
        self.actDeactivate.triggered.connect(self.deactivate)

        confMenu.addAction(self.actLoad)
        confMenu.addAction(self.actSave)
        confMenu.addAction(self.actNew)
        confMenu.addAction(self.actActivate)
        confMenu.addAction(self.actDeactivate)
        toolBar.addAction(self.actLoad)
        toolBar.addAction(self.actSave)
        toolBar.addAction(self.actNew)
        toolBar.addAction(self.actActivate)
        toolBar.addAction(self.actDeactivate)

        self.recentConfigs = [QAction() for i in range(10)]
        confMenu.addSeparator()
        recentMenu = confMenu.addMenu("Recent")
        for a in self.recentConfigs:
            a.setVisible(False)
            a.triggered.connect(self._openRecent)
            recentMenu.addAction(a)

        self.mainWidget = srv.newDockWidget("Configuration", None, Qt.LeftDockWidgetArea)
        self.treeView = QTreeView(self.mainWidget)
        self.treeView.setHeaderHidden(False)
        self.treeView.setSelectionMode(QAbstractItemView.NoSelection)
        self.treeView.setEditTriggers(self.treeView.EditKeyPressed|self.treeView.AnyKeyPressed)
        self.treeView.setAllColumnsShowFocus(True)
        self.treeView.setExpandsOnDoubleClick(False)
        self.treeView.setDragEnabled(True)
        self.treeView.setDropIndicatorShown(True)
        self.treeView.setDragDropMode(QAbstractItemView.DragOnly)
        self.mainWidget.setWidget(self.treeView)
        self.treeView.setModel(self.model)
        self.treeView.header().setStretchLastSection(True)
        self.treeView.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.treeView.doubleClicked.connect(self._onItemDoubleClicked)
        self.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.treeView.customContextMenuRequested.connect(self._execTreeViewContextMenu)
        # expand applications by default
        self.treeView.setExpanded(self.model.index(1, 0), True)
        self.delegate = PropertyDelegate(self.model, ITEM_ROLE, ConfigurationModel.PropertyContent, self)
        self.treeView.setItemDelegate(self.delegate)

        self.restoreState()
        srv.aboutToClose.connect(self.saveState)
        # a list of dock widgets displaying subgraphs
        self._graphViews = []
        # make sure that the graph views are closed when the config is closed
        self._configuration.subConfigRemoved.connect(self._subConfigRemoved)

    def _execLoad(self):
        assertMainThread()
        if self._checkDirty():
            return
        fn, _ = QFileDialog.getOpenFileName(self.mainWidget, "Load configuration", self.cfgfile, filter="*.json")
        if fn is not None and fn != "":
            logger.debug("Loading config file %s", fn)
            try:
                self.loadConfig(fn)
            except Exception as e: # pylint: disable=broad-except
                logger.exception("Error while loading configuration %s: %s", fn, str(e))
                QMessageBox.warning(self.mainWidget, "Error while loading configuration", str(e))

    def _openRecent(self):
        """
        Called when the user clicks on a recent config.
        :return:
        """
        if self._checkDirty():
            return
        action = self.sender()
        fn = action.data()
        try:
            self.loadConfig(fn)
        except Exception as e: # pylint: disable=broad-except
            # catching general exception is wanted here.
            logger.exception("Error while loading configuration %s: %s", fn, str(e))
            QMessageBox.warning(self.mainWidget, "Error while loading configuration", str(e))

    def _checkDirty(self):
        if self._configuration.dirty():
            ans = QMessageBox.question(None, "Save changes?",
                                       "There are unsaved changes. Do you want to save them?",
                                       buttons=QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                       defaultButton=QMessageBox.Save)
            if ans == QMessageBox.Save:
                self.saveConfig()
                return False
            if ans == QMessageBox.Cancel:
                return True
        return False

    def _aboutToClose(self, mainWindow):
        if self._checkDirty():
            mainWindow.ignoreCloseEvent()

    def _execNew(self):
        assertMainThread()
        if self._checkDirty():
            return
        fn, _ = QFileDialog.getSaveFileName(self.mainWidget, "Save configuration", filer="*.json")
        if fn is not None and fn != "":
            logger.debug("Creating config file %s", fn)
            self.newConfig(fn)

    def _addGraphView(self, subConfig):
        g = subConfig.getGraph()
        # remove already deleted graph views from internal list
        valid_graphViews = []
        for gv in self._graphViews:
            if shiboken2.isValid(gv): # pylint: disable=no-member
                valid_graphViews.append(gv)
        self._graphViews = valid_graphViews
        # check if graph view is already there
        for gv in self._graphViews:
            if gv.widget().scene().graph == g:
                logger.info("Graph view already exists.")
                return
        # create new graph view
        srv = Services.getService("MainWindow")
        graphDw = srv.newDockWidget("Graph (%s)" % (subConfig.getName()), parent=None,
                                    defaultArea=Qt.RightDockWidgetArea,
                                    allowedArea=Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        graphDw.setAttribute(Qt.WA_DeleteOnClose, True)
        assert isinstance(graphDw, QDockWidget)
        graphView = QGraphicsView(graphDw)
        graphView.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        graphView.setScene(GraphScene(subConfig.getGraph(), graphDw))
        graphDw.setWidget(graphView)
        self._graphViews.append(graphDw)
        graphDw.visibleChanged.connect(self._removeGraphViewFromList)

    def _subConfigRemoved(self, subConfigName, configType):
        g = self._configuration.subConfigByNameAndTye(subConfigName, configType).getGraph()
        for gv in self._graphViews:
            if gv.widget().scene().graph == g:
                logger.debug("deleting graph view for subconfig %s", subConfigName)
                gv.deleteLater()

    def _removeGraphViewFromList(self, visible):
        if visible:
            return
        gv = self.sender()
        try:
            self._graphViews.remove(gv)
            logger.debug("removed graphview from list")
        except ValueError:
            logger.debug("graphview not in list, ignored")

    def _execTreeViewContextMenu(self, point):
        index = self.treeView.indexAt(point)
        item = self.model.data(index, ITEM_ROLE)
        if isinstance(item, ConfigurationModel.SubConfigContent):
            m = QMenu()
            a = QAction("Edit graph ...")
            m.addAction(a)
            a = m.exec_(self.treeView.mapToGlobal(point))
            if a is not None:
                self._addGraphView(item.subConfig)
            return
        if self.model.isSubConfigParent(index) == Configuration.CONFIG_TYPE_APPLICATION:
            m = QMenu()
            a = QAction("Add application ...")
            m.addAction(a)
            a = m.exec_(self.treeView.mapToGlobal(point))
            if a is not None:
                self._configuration.addNewApplication()
            return
        if self.model.isSubConfigParent(index) == Configuration.CONFIG_TYPE_COMPOSITE:
            m = QMenu()
            a = QAction("Add composite filter ...")
            m.addAction(a)
            a = m.exec_(self.treeView.mapToGlobal(point))
            if a is not None:
                self._configuration.addNewCompositeFilter()
            return

    def _configNameChanged(self, cfgfile):
        logger.debug("_configNameChanged: %s", cfgfile)
        assertMainThread()
        self.cfgfile = cfgfile
        self._dirtyChanged(self._configuration.dirty())
        foundIdx = None
        for i, a in enumerate(self.recentConfigs):
            if a.data() == cfgfile:
                foundIdx = i
        if foundIdx is None:
            foundIdx = len(self.recentConfigs)-1
        for i in range(foundIdx, 0, -1):
            self.recentConfigs[i].setText(self.recentConfigs[i-1].text())
            self.recentConfigs[i].setData(self.recentConfigs[i-1].data())
            self.recentConfigs[i].setVisible(self.recentConfigs[i-1].data() is not None)
        self.recentConfigs[0].setText(cfgfile)
        self.recentConfigs[0].setData(cfgfile)
        self.recentConfigs[0].setVisible(True)

    def _dirtyChanged(self, dirty):
        srv = Services.getService("MainWindow")
        if self.cfgfile is None:
            title = "nexxT: <unnamed>"
        else:
            title = "nexxT: " + self.cfgfile
        if dirty:
            title += " *"
        srv.setWindowTitle(title)

    def _onItemDoubleClicked(self, index):
        assertMainThread()
        if self.model.isApplication(index):
            app = self.model.data(index, Qt.DisplayRole)
            self.changeActiveApp(app)
        else:
            self.treeView.edit(index)

    def appActivated(self, name, app): # pylint: disable=unused-argument
        """
        Called when the application is activated.
        :param name: the application name
        :param app: An ActiveApplication instance.
        :return:
        """
        assertMainThread()
        if app is not None:
            self.activeAppStateChange(app.getState())
            app.stateChanged.connect(self.activeAppStateChange)
        else:
            self.actActivate.setEnabled(False)
            self.actDeactivate.setEnabled(False)

    def activeAppStateChange(self, newState):
        """
        Called when the active application changes its state.
        :param newState: the new application's state (see FilterState)
        :return:
        """
        assertMainThread()
        if newState == FilterState.CONSTRUCTED:
            self.actActivate.setEnabled(True)
        else:
            self.actActivate.setEnabled(False)
        if newState == FilterState.ACTIVE:
            self.actDeactivate.setEnabled(True)
        else:
            self.actDeactivate.setEnabled(False)

    def restoreState(self):
        """
        Restore the state of the configuration gui service (namely the recently
        open config files). This is saved in QSettings because it is used
        across config files.
        :return:
        """
        logger.debug("restoring config state ...")
        settings = QSettings()
        v = settings.value("ConfigurationRecentFiles")
        if v is not None and isinstance(v, QByteArray):
            ds = QDataStream(v)
            recentFiles = ds.readQStringList()
            idx = 0
            for f in recentFiles:
                if f != "" and f is not None:
                    self.recentConfigs[idx].setData(f)
                    self.recentConfigs[idx].setText(f)
                    self.recentConfigs[idx].setVisible(True)
                    idx += 1
                    if idx >= len(self.recentConfigs):
                        break
        logger.debug("restoring config state done")

    def saveState(self):
        """
        Save the state of the configuration gui service (namely the recently
        open config files). This is saved in QSettings because it is used
        across config files.
        :return:
        """
        logger.debug("saving config state ...")
        settings = QSettings()
        b = QByteArray()
        ds = QDataStream(b, QIODevice.WriteOnly)
        l = [rc.data() for rc in self.recentConfigs if rc.isVisible() and rc.data() is not None and rc.data() != ""]
        ds.writeQStringList(l)
        settings.setValue("ConfigurationRecentFiles", b)
        logger.debug("saving config state done (%s)", l)
