# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the gui logging service for nexxT.
"""
import datetime
from queue import Queue
import traceback
import logging
from PySide2.QtCore import Qt, QTimer, QAbstractItemModel, QModelIndex
from PySide2.QtWidgets import QTableView, QHeaderView, QAction, QActionGroup
from PySide2.QtGui import QColor
from nexxT.services.ConsoleLogger import ConsoleLogger
from nexxT.interface import Services
from nexxT.core.Utils import assertMainThread

class LogHandler(logging.Handler): # pragma: no cover
    """
    Python logging handler which passes python log records to the gui.
    """
    def __init__(self, logView):
        super().__init__()
        self.logView = logView

    def emit(self, record):
        """
        called when a new log record is created
        :param record: a log record instance (see python docs)
        :return:
        """
        msg = record.getMessage()
        if record.exc_info is not None:
            msg += "\n" + "".join(traceback.format_exception(*record.exc_info))
        if msg[-1] == "\n":
            msg = msg[:-1]
        items = (str(datetime.datetime.fromtimestamp(record.created)),
                 record.levelno,
                 msg,
                 record.name, record.filename, str(record.lineno))
        self.logView.addLogRecord(items)

class LogView(QTableView): # pragma: no cover
    """
    Class implementing the GUI log display.
    """

    class LogModel(QAbstractItemModel):
        """
        Model/view model for log entries. The entries are held in a python list.
        """
        def __init__(self):
            super().__init__()
            self.entries = []

        def rowCount(self, parent):
            """
            Overwritten from QAbstractItemModel
            :param parent: a QModelIndex instance
            :return: number of log entries
            """
            if not parent.isValid():
                return len(self.entries)
            return 0

        def columnCount(self, parent): # pylint: disable=unused-argument
            """
            Overwritten from QAbstractItemModel
            :param parent: a QModelIndex instance
            :return: the number of columns (constant)
            """
            return 6

        def update(self, queue):
            """
            add queued items to model
            :param queue: a python Queue instance
            :return: None
            """
            toInsert = []
            while not queue.empty():
                items = queue.get()
                toInsert.append(items)
            if len(toInsert) > 0:
                self.beginInsertRows(QModelIndex(), len(self.entries), len(self.entries) + len(toInsert) - 1)
                self.entries.extend(toInsert)
                self.endInsertRows()

        def clear(self):
            """
            removes all entries from the list
            :return: None
            """
            if len(self.entries) > 0:
                self.beginRemoveRows(QModelIndex(), 0, len(self.entries)-1)
                self.entries = []
                self.endRemoveRows()

        def index(self, row, column, parent):
            """
            Overwritten from QAbstractItemModel
            :param row: integer
            :param column: integer
            :param parent: a QModelIndex instance
            :return: a QModelIndex for the specified item
            """
            if not self.hasIndex(row, column, parent):
                #print("index invalid", row, column, parent.isValid())
                return QModelIndex()
            if not parent.isValid():
                #print("index valid", row, column, parent.isValid())
                return self.createIndex(row, column)
            #print("index invalid", row, column, parent.isValid())
            return QModelIndex()

        def parent(self, index): # pylint: disable=unused-argument
            """
            Overwritten from QAbstractItemModel
            :param index:
            :return: invalid model index (because we have a 2D table)
            """
            return QModelIndex()

        def headerData(self, section, orientation, role):
            """
            Overwritten from QAbstractItemModel
            :param section: the section index
            :param orientation: the orientation
            :param role: the item role
            :return: the section label
            """
            if role in [Qt.DisplayRole, Qt.EditRole] and orientation == Qt.Horizontal:
                return ["Time", "Level", "Message", "Module", "Filename", "Line"][section]
            return super().headerData(section, orientation, role)

        def data(self, modelIndex, role):
            """
            Overwritten from QAbstractItemModel
            :param modelIndex: a QModelIndex instance
            :param role: the role
            :return: the requested data
            """
            if not modelIndex.isValid():
                return None
            e = self.entries[modelIndex.row()]
            if role in [Qt.DisplayRole, Qt.EditRole]:
                #print("data", modelIndex.row(), modelIndex.column(), role)
                if modelIndex.column() == 1:
                    levelno = e[1]
                    if levelno <= logging.INTERNAL:
                        return "INTERNAL"
                    if logging.INTERNAL < levelno <= logging.DEBUG:
                        return "DEBUG"
                    if logging.DEBUG < levelno <= logging.INFO:
                        return "INFO"
                    if logging.INFO < levelno <= logging.WARNING:
                        return "WARNING"
                    if logging.WARNING < levelno <= logging.ERROR:
                        return "ERROR"
                    return "CRITICAL"
                return e[modelIndex.column()]
            if role == Qt.BackgroundColorRole:
                levelno = e[1]
                if levelno <= logging.INTERNAL:
                    return QColor(255, 255, 255)  # white
                if logging.INTERNAL < levelno <= logging.DEBUG:
                    return QColor(155, 155, 255)  # blue
                if logging.DEBUG < levelno <= logging.INFO:
                    return QColor(155, 255, 155)  # green
                if logging.INFO < levelno <= logging.WARNING:
                    return QColor(255, 255, 155)  # yellow
                if logging.WARNING < levelno <= logging.ERROR:
                    return QColor(255, 205, 155)  # orange
                return QColor(255, 155, 155)  # red
            return None

    def __init__(self):
        super().__init__()
        self.follow = True
        self.model = self.LogModel()
        #self.setUniformRowHeights(True)
        self.setShowGrid(False)
        self.queue = Queue()
        self.setModel(self.model)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(False)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.timer = QTimer()
        self.timer.setSingleShot(False)
        self.timer.start(100)
        self.timer.timeout.connect(self.update, Qt.QueuedConnection)

    def addLogRecord(self, items):
        """
        Add a log record to the synchronized queue
        :param items: a tuple of (timestamp[str], level[int], message[str], modulename[str], filename[str], lineno[int])
        :return:None
        """
        self.queue.put(items)

    def update(self):
        """
        Called periodically to synchronize model with added log records
        :return:None
        """
        assertMainThread()
        if not self.queue.empty():
            self.model.update(self.queue)
            if self.follow:
                self.scrollToBottom()

    def setFollow(self, follow):
        """
        set follow mode
        :param follow: a boolean
        :return: None
        """
        self.follow = follow

    def clear(self):
        """
        Clears the view
        :return: None
        """
        self.model.clear()

class GuiLogger(ConsoleLogger): # pragma: no cover
    """
    Logging service in GUI mode.
    """

    def __init__(self):
        super().__init__()
        srv = Services.getService("MainWindow")
        self.dockWidget = srv.newDockWidget("Log", parent=None,
                                            defaultArea=Qt.BottomDockWidgetArea,
                                            allowedArea=Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self.logWidget = LogView()
        self.dockWidget.setWidget(self.logWidget)
        logMenu = srv.menuBar().addMenu("&Log")
        mainLogger = logging.getLogger()
        self.handler = LogHandler(self.logWidget)
        mainLogger.addHandler(self.handler)
        self.logWidget.destroyed.connect(lambda: mainLogger.removeHandler(self.handler))

        self.actFollow = QAction("Follow")
        self.actFollow.setCheckable(True)
        self.actFollow.setChecked(True)
        self.actClear = QAction("Clear")
        self.actSingleLine = QAction("Single Line")
        self.actSingleLine.setCheckable(True)
        self.actSingleLine.setChecked(True)

        self.actFollow.toggled.connect(self.logWidget.setFollow)
        self.actClear.triggered.connect(self.logWidget.clear)
        #self.actSingleLine.toggled.connect(self.logWidget.setUniformRowHeights)

        self.actDisable = QAction("Disable")
        self.actDisable.triggered.connect(self.setLogLevel)

        self.actGroup = QActionGroup(self)
        self.actGroup.setExclusive(True)
        levelno = mainLogger.level

        self.loglevelMap = {}
        for lv in ["INTERNAL", "DEBUG", "INFO", "WARNING", "ERROR"]:
            a = QAction(lv[:1] + lv[1:].lower())
            a.setCheckable(True)
            loglevel = getattr(logging, lv)
            self.loglevelMap[a] = loglevel
            setattr(self, "setLogLevel_" + lv, self.setLogLevel)
            a.triggered.connect(getattr(self, "setLogLevel_" + lv))
            self.actGroup.addAction(a)
            if levelno == loglevel:
                a.setChecked(True)
            else:
                a.setChecked(False)
            logMenu.addAction(a)
        self.loglevelMap[self.actDisable] = 100
        logMenu.addAction(self.actDisable)
        
        logMenu.addSeparator()
        logMenu.addAction(self.actClear)
        logMenu.addAction(self.actFollow)
        logMenu.addAction(self.actSingleLine)

    def setLogLevel(self):
        """
        Sets the current log level from the calling action.
        :return: None
        """
        lv = self.loglevelMap[self.sender()]
        logging.getLogger().setLevel(lv)
