# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the Configuration GUI service of the nexxT framework.
"""

import logging
from PySide2.QtCore import (QObject, Signal, Slot, Qt, QAbstractItemModel, QModelIndex, QSettings, QByteArray,
                            QDataStream, QIODevice, QMimeData)
from PySide2.QtGui import QFont, QPainter
from PySide2.QtWidgets import (QTreeView, QAction, QStyle, QApplication, QFileDialog, QAbstractItemView, QMessageBox,
                               QHeaderView, QMenu, QDockWidget, QGraphicsView)
from nexxT.interface import Services, FilterState
from nexxT.core.Exceptions import NexTRuntimeError
from nexxT.core.ConfigFiles import ConfigFileLoader
from nexxT.core.Configuration import Configuration
from nexxT.core.Application import Application
from nexxT.core.CompositeFilter import CompositeFilter
from nexxT.core.Utils import assertMainThread
from nexxT.services.gui.PropertyDelegate import PropertyDelegate
from nexxT.services.gui.GraphEditor import GraphScene

logger = logging.getLogger(__name__)

ITEM_ROLE = Qt.UserRole + 4223

class ConfigurationModel(QAbstractItemModel):
    """
    This class encapsulates a next Configuration item in a QAbstractItemModel ready for usage in a QTreeView.

    Internally, item-trees are constructed which duplicate the relevant information from the python classes.
    """

    # Helper classes

    class Item:
        """
        An item instance for creating the item tree. Items have children, a parent and arbitrary content.
        """
        def __init__(self, parent, content):
            if parent is not None:
                parent.children.append(self)
            self.children = []
            self.parent = parent
            self.content = content

        def row(self):
            """
            :return: the index of this item in the parent item.
            """
            return self.parent.children.index(self)

    class NodeContent:
        """
        A node in a subconfig, for usage within the model
        """
        def __init__(self, subConfig, name):
            self.subConfig = subConfig
            self.name = name

    class PropertyContent:
        """
        A property in a propertyCollection, for usage within the model.
        """
        def __init__(self, name, propertyCollection):
            self.name = name
            self.property = propertyCollection

    class SubConfigContent:
        """
        A subConfiguration, for usage within the model.
        """
        def __init__(self, subConfig):
            self.subConfig = subConfig

    # Model implementation

    def __init__(self, configuration, parent):
        super().__init__(parent)
        self.root = self.Item(None, configuration)
        self.Item(self.root, "composite")
        self.Item(self.root, "apps")
        self.activeApp = None
        configuration.subConfigAdded.connect(self.subConfigAdded)
        configuration.subConfigRemoved.connect(self.subConfigRemoved)
        configuration.appActivated.connect(self.appActivated)

    def isSubConfigParent(self, index):
        item = self.data(index, ITEM_ROLE)
        if index.isValid() and not index.parent().isValid():
            if item == "composite":
                return Configuration.CONFIG_TYPE_COMPOSITE
            if item == "apps":
                return Configuration.CONFIG_TYPE_APPLICATION
        return None

    @staticmethod
    def isApplication(index):
        """
        Returns true, if this index relates to an applications, false otherwise.
        :param index: a QModelIndex instance
        :return: bool
        """
        parent = index.parent()
        return parent.isValid() and not parent.parent().isValid() and parent.row() == 1

    def indexOfSubConfigParent(self, subConfig):
        """
        Returns the index of the given subConfig's parent
        :param subConfig: a SubConfiguration instance
        :return: a QModelIndex instance.
        """
        sctype = Configuration.configType(subConfig)
        if sctype is Configuration.CONFIG_TYPE_APPLICATION:
            parent = self.index(1, 0, QModelIndex())
        elif sctype is Configuration.CONFIG_TYPE_COMPOSITE:
            parent = self.index(0, 0, QModelIndex())
        else:
            raise NexTRuntimeError("Unexpected subconfig type")
        return parent

    def indexOfSubConfig(self, subConfig):
        """
        Returns the index of the given subConfig
        :param subConfig: a SubConfiguration instance
        :return: a QModelIndex instance.
        """
        parent = self.indexOfSubConfigParent(subConfig)
        parentItem = parent.internalPointer()
        if isinstance(subConfig, str):
            idx = [i for i in range(len(parentItem.children))
                   if parentItem.children[i].content.subConfig.getName() == subConfig]
        else:
            idx = [i for i in range(len(parentItem.children))
                   if parentItem.children[i].content.subConfig is subConfig]
        if len(idx) != 1:
            raise NexTRuntimeError("Unable to locate subconfig.")
        return self.index(idx[0], 0, parent)

    def indexOfNode(self, subConfig, node):
        """
        Returns the index of the given node inside a subconfig.
        :param subConfig: a SubConfiguration instance
        :param node: a node name
        :return: a QModelIndex instance
        """
        parent = self.indexOfSubConfig(subConfig)
        parentItem = parent.internalPointer()
        idx = [i for i in range(len(parentItem.children))
               if parentItem.children[i].content.name == node]
        if len(idx) != 1:
            raise NexTRuntimeError("Unable to locate node.")
        return self.index(idx[0], 0, parent)

    def subConfigByNameAndType(self, name, sctype):
        """
        Returns a SubConfiguration instance, given its name and type
        :param name: the name as a string
        :param sctype: either CONFIG_TYPE_APPLICATION or CONFIG_TYPE_COMPOSITE
        :return: a SubConfiguration instance
        """
        if sctype is Configuration.CONFIG_TYPE_APPLICATION:
            found = [c.content.subConfig
                     for c in self.root.children[1].children if c.content.subConfig.getName() == name]
        elif sctype is Configuration.CONFIG_TYPE_COMPOSITE:
            found = [c.content.subConfig
                     for c in self.root.children[0].children if c.content.subConfig.getName() == name]
        else:
            raise NexTRuntimeError("Unexpected subconfig type")
        if len(found) != 1:
            raise NexTRuntimeError("Unable to locate subConfig")
        return found[0]

    @Slot(object)
    def subConfigAdded(self, subConfig):
        """
        This slot is called when a subconfig is added to the configuration instance. It inserts a row as needed.
        :param subConfig: a SubConfiguration instance
        :return:
        """
        parent = self.indexOfSubConfigParent(subConfig)
        parentItem = parent.internalPointer()
        graph = subConfig.getGraph()
        subConfig.nameChanged.connect(self.subConfigRenamed)
        graph.nodeAdded.connect(lambda node: self.nodeAdded(subConfig, node))
        graph.nodeDeleted.connect(lambda node: self.nodeDeleted(subConfig, node))
        graph.nodeRenamed.connect(lambda oldName, newName: self.nodeRenamed(subConfig, oldName, newName))
        self.beginInsertRows(parent, len(parentItem.children), len(parentItem.children))
        self.Item(parentItem, self.SubConfigContent(subConfig))
        self.endInsertRows()

    @Slot(object)
    def subConfigRenamed(self, subConfig, oldName): # pylint: disable=unused-argument
        """
        This slot is called when a subconfig is renamed in the configuration instance.
        :param subConfig: a SubConfiguration instance
        :param oldName: the old name of this subConfig
        :return:
        """
        index = self.indexOfSubConfig(subConfig)
        if (self.activeApp is not None and
                subConfig is self.subConfigByNameAndType(self.activeApp, Configuration.CONFIG_TYPE_APPLICATION)):
            self.activeApp = subConfig.getName()
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])

    @Slot(str, int)
    def subConfigRemoved(self, name, sctype):
        """
        This slot is called when a subconfig is removed from the configuration
        :param name. the name of the removed subConfig
        :param sctype: the type ( either CONFIG_TYPE_APPLICATION or CONFIG_TYPE_COMPOSITE)
        :return:
        """
        logger.debug("sub config removed %s %d", name, sctype)
        subConfig = self.subConfigByNameAndType(name, sctype)
        parent = self.indexOfSubConfigParent(subConfig)
        parentItem = parent.internalPointer()
        index = self.indexOfSubConfig(subConfig)
        if sctype == Configuration.CONFIG_TYPE_APPLICATION and name == self.activeApp:
            self.appActivated("", None)
        idx = index.row()
        self.beginRemoveRows(parent, idx, idx)
        parentItem.children = parentItem.children[:idx] + parentItem.children[idx+1:]
        self.endRemoveRows()

    @Slot(str, object)
    def appActivated(self, name, app):
        """
        This slot is called when an application has been activated.
        :param name: the name of the application
        :param app: the Application instance
        :return:
        """
        if self.activeApp is not None:
            try:
                subConfig = self.subConfigByNameAndType(self.activeApp, Configuration.CONFIG_TYPE_APPLICATION)
                parent = self.indexOfSubConfig(subConfig)
                index = parent.row()
                self.dataChanged.emit(index, index, [Qt.FontRole])
                self.activeApp = None
            except NexTRuntimeError:
                logger.exception("error during resetting active app (ignored)")

        if name != "" and app is not None:
            subConfig = self.subConfigByNameAndType(name, Configuration.CONFIG_TYPE_APPLICATION)
            parent = self.indexOfSubConfig(subConfig)
            self.activeApp = name
            index = parent.row()
            self.dataChanged.emit(index, index, [Qt.FontRole])

    def nodeAdded(self, subConfig, node):
        """
        This slot is called when a node is added to a subConfig
        :param subConfig: a SubConfiguration instance
        :param node: the node name.
        :return:
        """
        parent = self.indexOfSubConfig(subConfig)
        parentItem = parent.internalPointer()
        self.beginInsertRows(parent, len(parentItem.children), len(parentItem.children))
        item = self.Item(parentItem, self.NodeContent(subConfig, node))
        self.endInsertRows()
        mockup = subConfig.getGraph().getMockup(node)
        propColl = mockup.getPropertyCollectionImpl()
        logger.debug("register propColl: %s", propColl)
        for pname in propColl.getAllPropertyNames():
            self.propertyAdded(item, propColl, pname)
        propColl.propertyAdded.connect(lambda pc, name: self.propertyAdded(item, pc, name))
        propColl.propertyRemoved.connect(lambda pc, name: self.propertyRemoved(item, pc, name))
        propColl.propertyChanged.connect(lambda pc, name: self.propertyChanged(item, pc, name))

    def nodeDeleted(self, subConfig, node):
        """
        This slot is called when a node is removed from a subConfig
        :param subConfig: a SubConfiguration instance
        :param node: the node name.
        :return:
        """
        index = self.indexOfNode(subConfig, node)
        parent = index.parent()
        parentItem = parent.internalPointer()
        idx = index.row()
        self.beginRemoveRows(parent, idx, idx)
        parentItem.children = parentItem.children[:idx] + parentItem.children[idx+1:]
        self.endRemoveRows()

    def nodeRenamed(self, subConfig, oldName, newName):
        """
        This slot is called when a node is renamed in a subConfig
        :param subConfig: a SubConfiguration instance
        :param oldName: the original name.
        :param newName: the new name
        :return:
        """
        if oldName != newName:
            index = self.indexOfNode(subConfig, oldName)
            item = index.internalPointer()
            item.content.name = newName
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])

    def propertyAdded(self, parentItem, propColl, name):
        """
        Slot called when a property was added.
        :param parentItem: a NodeItem instance
        :param propColl: the PropertyCollection instance
        :param name: the name of the new property.
        :return:
        """
        parent = self.indexOfNode(parentItem.content.subConfig, parentItem.content.name)
        self.beginInsertRows(parent, len(parentItem.children), len(parentItem.children))
        self.Item(parentItem, self.PropertyContent(name, propColl))
        self.endInsertRows()

    def indexOfProperty(self, nodeItem, propName):
        """
        Returns the model index of the specified property
        :param nodeItem: a NodeItem instance
        :param propName: a property name
        :return: a QModelIndex instance
        """
        idx = [idx for idx in range(len(nodeItem.children)) if nodeItem.children[idx].content.name == propName]
        if len(idx) != 1:
            raise NexTRuntimeError("Property item not found.")
        idx = idx[0]
        parent = self.indexOfNode(nodeItem.content.subConfig, nodeItem.content.name)
        return self.index(idx, 0, parent)

    def propertyRemoved(self, parentItem, propColl, name): # pylint: disable=unused-argument
        """
        Slot called when a property has been removed.
        :param parentItem: a NodeItem instance
        :param propColl: a PropertyCollection instance
        :param name: the name of the removed property
        :return:
        """
        index = self.indexOfProperty(parentItem, name)
        self.beginRemoveRows(index.parent(), index.row(), index.row())
        parentItem.children = parentItem.children[:index.row()] + parentItem.children[index.row()+1:]
        self.endRemoveRows()

    def propertyChanged(self, item, propColl, name):
        """
        Slot called when a property has been changed.
        :param item: a PropertyItem instance
        :param propColl: a PropertyCollection instance
        :param name: the name of the changed property
        :return:
        """
        index = self.indexOfProperty(item, name)
        self.setData(index, propColl.getProperty(name), Qt.DisplayRole)

    def index(self, row, column, parent=QModelIndex()):
        """
        Creates a model index according to QAbstractItemModel conventions.
        :param row: the row index
        :param column: the column index
        :param parent: the parent index
        :return:
        """
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        if not parent.isValid():
            parentItem = self.root
        else:
            parentItem = parent.internalPointer()
        try:
            child = parentItem.children[row]
        except IndexError:
            return QModelIndex()
        return self.createIndex(row, column, child)

    def parent(self, index):
        """
        Returns the indice's parent according to QAbstractItemModel convetions.
        :param index: a QModelIndex instance.
        :return:
        """
        if not index.isValid():
            return QModelIndex()

        child = index.internalPointer()
        parentItem = child.parent
        if parentItem is self.root:
            return QModelIndex()
        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        """
        Returns the number of children of the given model index
        :param parent: a QModelIndex instance
        :return:
        """
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            parentItem = self.root
        else:
            parentItem = parent.internalPointer()
        return len(parentItem.children)

    def columnCount(self, parent):
        """
        Returns the number of columns of the given model index
        :param parent: a QModelIndex instance
        :return:
        """
        if parent.isValid():
            parentItem = parent.internalPointer()
            if isinstance(parentItem.content, self.NodeContent):
                return 2 # nodes children have the editable properties
            return 1
        return 2

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ["Name", "Property"][section]
        return super().headerData(section, orientation, role)

    def data(self, index, role): # pylint: disable=too-many-return-statements,too-many-branches
        """
        Generic data query
        :param index: a QModelIndex instance
        :param role: the data role (see QAbstractItemModel)
        :return:
        """
        if not index.isValid():
            return None
        item = index.internalPointer().content
        if role == Qt.DisplayRole:
            if isinstance(item, str):
                return item if index.column() == 0 else None
            if isinstance(item, self.SubConfigContent):
                return item.subConfig.getName()  if index.column() == 0 else None
            if isinstance(item, self.NodeContent):
                return item.name  if index.column() == 0 else None
            if isinstance(item, self.PropertyContent):
                if index.column() == 0:
                    return item.name
                p = item.property.getPropertyDetails(item.name)
                return p.converter(item.property.getProperty(item.name))
            logger.warning("Unknown item %s", repr(item))
        if role == Qt.DecorationRole:
            if index.column() != 0:
                return None
            if isinstance(item, str):
                if not index.parent().isValid():
                    return QApplication.style().standardIcon(QStyle.SP_DriveHDIcon)
            if isinstance(item, self.SubConfigContent):
                if Configuration.configType(item.subConfig) == Configuration.CONFIG_TYPE_COMPOSITE:
                    return QApplication.style().standardIcon(QStyle.SP_DirLinkIcon)
                if Configuration.configType(item.subConfig) == Configuration.CONFIG_TYPE_APPLICATION:
                    return QApplication.style().standardIcon(QStyle.SP_DirIcon)
            if isinstance(item, self.NodeContent):
                return QApplication.style().standardIcon(QStyle.SP_FileIcon)
            if isinstance(item, self.PropertyContent):
                # TODO
                return None
            logger.warning("Unknown item %s", repr(item))
        if role == Qt.FontRole:
            if index.column() != 0:
                return None
            if isinstance(item, self.SubConfigContent):
                if index.parent().row() == 1:
                    font = QFont()
                    if item.subConfig.getName() == self.activeApp:
                        font.setBold(True)
                        return font
        if role == Qt.ToolTipRole:
            if isinstance(item, self.PropertyContent):
                p = item.property.getPropertyDetails(item.name)
                return p.helpstr
        if role == ITEM_ROLE:
            return item
        return None

    def flags(self, index): # pylint: disable=too-many-return-statements,too-many-branches
        """
        Returns teh item flags of the given index
        :param index: a QModelIndex instance
        :return:
        """
        if not index.isValid():
            return Qt.NoItemFlags
        item = index.internalPointer().content
        if isinstance(item, str):
            return Qt.ItemIsEnabled
        if isinstance(item, self.SubConfigContent):
            if isinstance(item.subConfig, CompositeFilter):
                return Qt.ItemIsEnabled | Qt.ItemIsEditable | Qt.ItemIsDragEnabled
            return Qt.ItemIsEnabled | Qt.ItemIsEditable
        if isinstance(item, self.NodeContent):
            return Qt.ItemIsEnabled | Qt.ItemIsEditable
        if isinstance(item, self.PropertyContent):
            if index.column() == 0:
                return Qt.ItemIsEnabled
            return Qt.ItemIsEnabled | Qt.ItemIsEditable
        return Qt.ItemIsEnabled

    def setData(self, index, value, role):# pylint: disable=too-many-return-statements,too-many-branches,unused-argument
        """
        Generic data modification (see QAbstractItemModel for details)
        :param index: a QModelIndex instance
        :param value: the new value
        :param role: the role to be changed
        :return:
        """
        if not index.isValid():
            return False
        item = index.internalPointer().content
        if isinstance(item, str):
            return False
        if isinstance(item, self.SubConfigContent):
            subConfig = item.subConfig
            if value == subConfig.getName():
                return False
            config = self.root.content
            if Configuration.configType(subConfig) == Configuration.CONFIG_TYPE_APPLICATION:
                try:
                    if subConfig.getName() == self.activeApp:
                        self.activeApp = value
                    config.renameApp(subConfig.getName(), value)
                except NexTRuntimeError:
                    return False
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
            if Configuration.configType(subConfig) == Configuration.CONFIG_TYPE_COMPOSITE:
                try:
                    config.renameComposite(subConfig.getName(), value)
                except NexTRuntimeError:
                    return False
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                return True
        if isinstance(item, self.NodeContent):
            if item.name == value:
                return False
            subConfig = index.parent().internalPointer().content.subConfig
            graph = subConfig.getGraph()
            try:
                graph.renameNode(item.name, value)
            except NexTRuntimeError:
                return False
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            return True
        if isinstance(item, self.PropertyContent):
            # TODO
            try:
                item.property.setProperty(item.name, value)
            except NexTRuntimeError:
                return False
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            return True
        return False

    def headerDate(self, section, orientation, role): # pylint: disable=no-self-use
        """
        Returns the header data of this model
        :param section: section number starting from 0
        :param orientation: orientation
        :param role: the role to be returned
        :return:
        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section == 0:
                return "Name"
            return "Value"
        return None

    def mimeTypes(self):
        logger.debug("mimeTypes")
        return ["application/x-nexxT-compositefilter"]

    def mimeData(self, indices):
        logger.debug("mimeData")
        if len(indices) == 1 and indices[0].isValid():
            index = indices[0]
            item = index.internalPointer().content
            if isinstance(item, self.SubConfigContent) and isinstance(item.subConfig, CompositeFilter):
                res = QMimeData()
                res.setData(self.mimeTypes()[0], item.subConfig.getName().encode("utf8"))
                return res
        return None

class MVCConfigurationGUI(QObject):
    """
    GUI implementation of MVCConfigurationBase
    """

    activeAppChanged = Signal(str)

    def __init__(self, configuration):
        super().__init__()
        assertMainThread()
        srv = Services.getService("MainWindow")
        confMenu = srv.menuBar().addMenu("&Configuration")
        toolBar = srv.getToolBar()
        self._configuration = configuration
        
        self.actLoad = QAction(QApplication.style().standardIcon(QStyle.SP_DialogOpenButton), "Open config", self)
        self.actLoad.triggered.connect(lambda *args: self._execLoad(configuration, *args))
        self.actSave = QAction(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton), "Save config", self)
        self.actSave.triggered.connect(lambda *args: self._execSave(configuration, *args))
        self.actNew = QAction(QApplication.style().standardIcon(QStyle.SP_FileIcon), "New config", self)
        self.actNew.triggered.connect(lambda *args: self._execNew(configuration, *args))

        self.cfgfile = None
        configuration.configNameChanged.connect(self._configNameChanged)

        self.actActivate = QAction(QApplication.style().standardIcon(QStyle.SP_ArrowUp), "Initialize", self)
        self.actActivate.triggered.connect(Application.initialize)
        self.actDeactivate = QAction(QApplication.style().standardIcon(QStyle.SP_ArrowDown), "Deinitialize", self)
        self.actDeactivate.triggered.connect(Application.deInitialize)

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
        self.model = ConfigurationModel(configuration, self.mainWidget)
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

        configuration.appActivated.connect(self.appActivated)
        self.activeAppChanged.connect(configuration.activate)
        self.restoreState()
        srv.aboutToClose.connect(self.saveState)

    def _execLoad(self, configuration):
        assertMainThread()
        fn, _ = QFileDialog.getOpenFileName(self.mainWidget, "Load configuration", self.cfgfile, filter="*.json")
        if fn is not None and fn != "":
            logger.debug("Loading config file %s", fn)
            try:
                ConfigFileLoader.load(configuration, fn)
            except Exception as e: # pylint: disable=broad-except
                logger.exception("Error while loading configuration %s: %s", fn, str(e))
                QMessageBox.warning(self.mainWidget, "Error while loading configuration", str(e))

    def _openRecent(self):
        """
        Called when the user clicks on a recent sequence.
        :return:
        """
        action = self.sender()
        fn = action.data()
        try:
            ConfigFileLoader.load(self._configuration, fn)
        except Exception as e:
            logger.exception("Error while loading configuration %s: %s", fn, str(e))
            QMessageBox.warning(self.mainWidget, "Error while loading configuration", str(e))

    @staticmethod
    def _execSave(configuration):
        assertMainThread()
        logger.debug("Saving config file")
        ConfigFileLoader.save(configuration)

    def _execNew(self, configuration):
        assertMainThread()
        fn, _ = QFileDialog.getSaveFileName(self.mainWidget, "Save configuration", filer="*.json")
        if fn is not None and fn != "":
            logger.debug("Creating config file %s", fn)
            configuration.close()
            ConfigFileLoader.save(configuration, fn)

    def _execTreeViewContextMenu(self, point):
        index = self.treeView.indexAt(point)
        item = self.model.data(index, ITEM_ROLE)
        if isinstance(item, ConfigurationModel.SubConfigContent):
            m = QMenu()
            a = QAction("Edit graph ...")
            m.addAction(a)
            a = m.exec_(self.treeView.mapToGlobal(point))
            if a is not None:
                srv = Services.getService("MainWindow")
                graphDw = srv.newDockWidget("Graph (%s)" % (item.subConfig.getName()), parent=None,
                                            defaultArea=Qt.RightDockWidgetArea,
                                            allowedArea=Qt.RightDockWidgetArea|Qt.BottomDockWidgetArea)
                graphDw.setAttribute(Qt.WA_DeleteOnClose, True)
                assert isinstance(graphDw, QDockWidget)
                graphView = QGraphicsView(graphDw)
                graphView.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
                graphView.setScene(GraphScene(item.subConfig.getGraph(), graphDw))
                graphDw.setWidget(graphView)
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
        assertMainThread()
        self.cfgfile = cfgfile
        srv = Services.getService("MainWindow")
        if cfgfile is None:
            srv.setWindowTitle("nexxT")
        else:
            srv.setWindowTitle("nexxT: " + cfgfile)
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

    def _onItemDoubleClicked(self, index):
        assertMainThread()
        if self.model.isApplication(index):
            app = self.model.data(index, Qt.DisplayRole)
            self.activeAppChanged.emit(app)

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
        logger.debug("saving config state ...")
        settings = QSettings()
        b = QByteArray()
        ds = QDataStream(b, QIODevice.WriteOnly)
        l = [rc.data() for rc in self.recentConfigs if rc.isVisible() and rc.data() is not None and rc.data() != ""]
        ds.writeQStringList(l)
        settings.setValue("ConfigurationRecentFiles", b)
        logger.debug("saving config state done (%s)", l)