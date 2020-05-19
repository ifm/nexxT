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
from nexxT.core.Utils import assertMainThread, handleException

logger = logging.getLogger(__name__)

class LogHandler(logging.Handler):
    def __init__(self, logView):
        super().__init__()
        self.logView = logView

    def emit(self, record):
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

class LogView(QTableView):

    class LogModel(QAbstractItemModel):
        def __init__(self):
            super().__init__()
            self.entries = []

        def rowCount(self, parent):
            if not parent.isValid():
                return len(self.entries)
            return 0

        def columnCount(self, parent):
            return 6

        def update(self, queue):
            toInsert = []
            while not queue.empty():
                items = queue.get()
                toInsert.append(items)
            if len(toInsert) > 0:
                self.beginInsertRows(QModelIndex(), len(self.entries), len(self.entries) + len(toInsert) - 1)
                self.entries.extend(toInsert)
                self.endInsertRows()

        def clear(self):
            if len(self.entries) > 0:
                self.beginRemoveRows(QModelIndex(), 0, len(self.entries)-1)
                self.entries = []
                self.endRemoveRows()

        def index(self, row, column, parent):
            if not self.hasIndex(row, column, parent):
                #print("index invalid", row, column, parent.isValid())
                return QModelIndex()
            if not parent.isValid():
                #print("index valid", row, column, parent.isValid())
                return self.createIndex(row, column)
            #print("index invalid", row, column, parent.isValid())
            return QModelIndex()

        def parent(self, index):
            return QModelIndex()

        def headerData(self, section, orientation, role):
            if role in [Qt.DisplayRole, Qt.EditRole] and orientation == Qt.Horizontal:
                return ["Time", "Level", "Message", "Module", "Filename", "Line"][section]
            return super().headerData(section, orientation, role)

        def data(self, modelIndex, role):
            if not modelIndex.isValid():
                return None
            e = self.entries[modelIndex.row()]
            if role in [Qt.DisplayRole, Qt.EditRole]:
                #print("data", modelIndex.row(), modelIndex.column(), role)
                if modelIndex.column() == 1:
                    levelno = e[1]
                    if levelno <= logging.INTERNAL:
                        return "INTERNAL"
                    elif logging.INTERNAL < levelno <= logging.DEBUG:
                        return "DEBUG"
                    elif logging.DEBUG < levelno <= logging.INFO:
                        return "INFO"
                    elif logging.INFO < levelno <= logging.WARNING:
                        return "WARNING"
                    elif logging.WARNING < levelno <= logging.ERROR:
                        return "ERROR"
                    return "CRITICAL"
                return e[modelIndex.column()]
            if role == Qt.BackgroundColorRole:
                levelno = e[1]
                if levelno <= logging.INTERNAL:
                    return QColor(255, 255, 255)  # white
                elif logging.INTERNAL < levelno <= logging.DEBUG:
                    return QColor(155, 155, 255)  # blue
                elif logging.DEBUG < levelno <= logging.INFO:
                    return QColor(155, 255, 155)  # green
                elif logging.INFO < levelno <= logging.WARNING:
                    return QColor(255, 255, 155)  # yellow
                elif logging.WARNING < levelno <= logging.ERROR:
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
        self.queue.put( items )

    def update(self):
        assertMainThread()
        if not self.queue.empty():
            self.model.update(self.queue)
            if self.follow:
                self.scrollToBottom()

    def setFollow(self, follow):
        self.follow = follow

    def clear(self):
        self.model.clear()

class GuiLogger(ConsoleLogger):

    def __init__(self):
        super().__init__()
        srv = Services.getService("MainWindow")
        self.dockWidget = srv.newDockWidget("Log", parent=None,
                                            defaultArea=Qt.BottomDockWidgetArea,
                                            allowedArea=Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self.logWidget = LogView()
        self.dockWidget.setWidget(self.logWidget)
        logMenu = srv.menuBar().addMenu("&Log")
        logger = logging.getLogger()
        self.handler = LogHandler(self.logWidget)
        logger.addHandler(self.handler)
        self.logWidget.destroyed.connect(lambda: logger.removeHandler(self.handler))

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

        self.actInternal = QAction("Internal")
        self.actDebug = QAction("Debug")
        self.actInfo = QAction("Info")
        self.actWarning = QAction("Warning")
        self.actError = QAction("Error")

        self.actInternal.triggered.connect(lambda: logger.setLevel(logging.INTERNAL))
        self.actDebug.triggered.connect(lambda: logger.setLevel(logging.DEBUG))
        self.actInfo.triggered.connect(lambda: logger.setLevel(logging.INFO))
        self.actWarning.triggered.connect(lambda: logger.setLevel(logging.WARNING))
        self.actError.triggered.connect(lambda: logger.setLevel(logging.ERROR))
        self.actGroup = QActionGroup(self)
        self.actGroup.setExclusive(True)
        levelno = logging.getLogger().level

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
        logMenu.addSeparator()
        logMenu.addAction(self.actClear)
        logMenu.addAction(self.actFollow)
        logMenu.addAction(self.actSingleLine)

    def setLogLevel(self):
        lv = self.loglevelMap[self.sender()]
        logging.getLogger().setLevel(lv)