# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the basic Configuration services of the nexxT framework.
"""

import logging
from PySide2.QtCore import (QObject, Slot, Qt, QAbstractItemModel, QModelIndex, QMimeData)
from PySide2.QtGui import QFont, QIcon
from PySide2.QtWidgets import QStyle, QApplication
from nexxT.core.Exceptions import NexTRuntimeError
from nexxT.core.ConfigFiles import ConfigFileLoader
from nexxT.core.Configuration import Configuration
from nexxT.core.Application import Application
from nexxT.core.CompositeFilter import CompositeFilter
from nexxT.core.Utils import assertMainThread, handleException

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
        """
        Returns CONFIG_TYPE_COMPOSITE if the index refers to the group
        composite, CONFIG_TYPE_APPLICATION if the index refers to the group
        applications, None otherwise.

        :param index: a QModelIndex instance
        :return:
        """
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
                return p.handler.toViewValue(item.property.getProperty(item.name))
            logger.warning("Unknown item %s", repr(item))
        if role == Qt.DecorationRole:
            if index.column() != 0:
                return None
            if isinstance(item, str):
                if not index.parent().isValid():
                    return QIcon.fromTheme("drive-harddisk", QApplication.style().standardIcon(QStyle.SP_DriveHDIcon))
            if isinstance(item, self.SubConfigContent):
                if Configuration.configType(item.subConfig) == Configuration.CONFIG_TYPE_COMPOSITE:
                    return QIcon.fromTheme("repository", QApplication.style().standardIcon(QStyle.SP_DirLinkIcon))
                if Configuration.configType(item.subConfig) == Configuration.CONFIG_TYPE_APPLICATION:
                    return QIcon.fromTheme("folder", QApplication.style().standardIcon(QStyle.SP_DirIcon))
            if isinstance(item, self.NodeContent):
                return QIcon.fromTheme("unknown", QApplication.style().standardIcon(QStyle.SP_FileIcon))
            if isinstance(item, self.PropertyContent):
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

class MVCConfigurationBase(QObject):
    """
    Base class for the configuration service. Might be used as a console service.
    The GUI service inherits from this class.
    """
    def __init__(self, configuration):
        super().__init__()
        assertMainThread()
        self._configuration = configuration

        self.cfgfile = None

        self.model = ConfigurationModel(configuration, self)
        configuration.appActivated.connect(self.appActivated)

    @Slot()
    def activate(self): # pylint: disable=no-self-use
        """
        Call this slot to activate the current application

        :return:
        """
        @handleException
        def execute():
            assertMainThread()
            Application.initialize()
        execute()

    @Slot()
    def deactivate(self): # pylint: disable=no-self-use
        """
        Call this slot to deactivate the current application

        :return:
        """
        @handleException
        def execute():
            assertMainThread()
            Application.deInitialize()
        execute()

    @Slot(str)
    def loadConfig(self, cfgFileName):
        """
        Call this slot to load a configuration

        :param cfgFileName: the filename of the configuration
        :return:
        """
        @handleException
        def execute():
            assertMainThread()
            ConfigFileLoader.load(self._configuration, cfgFileName)
        execute()

    @Slot()
    def saveConfig(self):
        """
        Call this slot to save the configuration (the gui state in the config will not be changed)

        :return:
        """
        @handleException
        def execute():
            assertMainThread()
            logger.debug("Saving config file")
            ConfigFileLoader.save(self._configuration)
        execute()

    @Slot()
    def saveConfigWithGuiState(self):
        """
        Call this slot to save the configuration and synchronize the gui state.

        :return:
        """
        @handleException
        def execute():
            assertMainThread()
            logger.debug("Saving config file")
            ConfigFileLoader.save(self._configuration, forceGuiState=True)
        execute()

    @Slot(str)
    def saveConfigAs(self, filename):
        """
        Call this slot to save the configuration

        :return:
        """
        @handleException
        def execute():
            assertMainThread()
            logger.debug("Saving config file")
            ConfigFileLoader.save(self._configuration, filename)
        execute()

    @Slot(str)
    def newConfig(self, cfgFileName):
        """
        Call this slot to create a new configuration

        :param cfgFileName: the filename of the configuration
        :return:
        """
        @handleException
        def execute():
            assertMainThread()
            self._configuration.close()
            logger.debug("Saving new config to %s", cfgFileName)
            ConfigFileLoader.save(self._configuration, cfgFileName)
        execute()

    @Slot(str)
    def changeActiveApp(self, app):
        """
        Call this slot to activate an application

        :param app: can be either an Application instance or the name of an application
        :return:
        """
        self._configuration.activate(app)

    def appActivated(self, name, app): # pylint: disable=unused-argument
        """
        Called when the application is activated. This is overwritten in the GUI class.

        :param name: the application name
        :param app: An ActiveApplication instance.
        :return:
        """

    def configuration(self):
        """
        Return this service's configuration object

        :return: a Configuration instance
        """
        return self._configuration
