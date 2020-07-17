# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides a MainWindow GUI service for the nexxT framework.
"""

import logging
import re
import shiboken2
from PySide2.QtWidgets import QMainWindow, QMdiArea, QMdiSubWindow, QDockWidget, QAction, QWidget, QGridLayout
from PySide2.QtCore import QObject, Signal, Slot, Qt, QByteArray, QDataStream, QIODevice, QRect, QPoint, QSettings
from nexxT.interface import Filter
from nexxT.core.Application import Application

logger = logging.getLogger(__name__)

class NexxTMdiSubWindow(QMdiSubWindow): # pragma: no cover
    """
    Need subclassing for getting close / show events and saving / restoring state.
    """
    visibleChanged = Signal(bool)

    def closeEvent(self, closeEvent):
        """
        override from QMdiSubWindow
        :param closeEvent: a QCloseEvent instance
        :return:
        """
        logger.internal("closeEvent widget=%s", self.widget())
        self.visibleChanged.emit(False)
        return super().closeEvent(closeEvent)

    def showEvent(self, showEvent):
        """
        override from QMdiSubWindow
        :param closeEvent: a QShowEvent instance
        :return:
        """
        logger.internal("showEvent widget=%s", self.widget())
        self.visibleChanged.emit(True)
        res = super().showEvent(showEvent)
        # no idea why this is necessary, but otherwise the child window is not shown
        if self.widget() is not None:
            self.widget().show()
        return res

    def saveGeometry(self):
        """
        Saves the geometry of this subwindow (see https://bugreports.qt.io/browse/QTBUG-18648)
        :return: a ByteArray instance
        """
        array = QByteArray()
        stream = QDataStream(array, QIODevice.WriteOnly)
        stream.writeUInt32(0x1D9D0CB)
        stream.writeUInt16(1)
        stream.writeUInt16(0)
        frameGeom = self.frameGeometry()
        stream.writeInt64(frameGeom.x())
        stream.writeInt64(frameGeom.y())
        stream.writeInt64(frameGeom.width())
        stream.writeInt64(frameGeom.height())
        normalGeom = self.normalGeometry()
        stream.writeInt64(normalGeom.x())
        stream.writeInt64(normalGeom.y())
        stream.writeInt64(normalGeom.width())
        stream.writeInt64(normalGeom.height())
        stream.writeUInt32(self.windowState() & Qt.WindowMaximized)
        stream.writeUInt32(self.windowState() & Qt.WindowFullScreen)
        return array

    def restoreGeometry(self, geometry):
        """
        Restores the geometry of this subwindow
        :param geometry: the saved state as a QByteArray instance
        :return:
        """
        if geometry.size() < 4:
            return False
        stream = QDataStream(geometry)
        if stream.readUInt32() != 0x1D9D0CB:
            return False
        if stream.readUInt16() != 1:
            return False
        stream.readUInt16() # minorVersion is ignored.
        x = stream.readInt64()
        y = stream.readInt64()
        width = stream.readInt64()
        height = stream.readInt64()
        restoredFrameGeometry = QRect(x, y, width, height)
        x = stream.readInt64()
        y = stream.readInt64()
        width = stream.readInt64()
        height = stream.readInt64()
        restoredNormalGeometry = QRect(x, y, width, height)
        maximized = stream.readUInt32()
        fullScreen = stream.readUInt32()
        frameHeight = 20
        if not restoredFrameGeometry.isValid():
            restoredFrameGeometry = QRect(QPoint(0, 0), self.sizeHint())
        if not restoredNormalGeometry.isValid():
            restoredNormalGeometry = QRect(QPoint(0, frameHeight), self.sizeHint())
        restoredFrameGeometry.moveTop(max(restoredFrameGeometry.top(), 0))
        restoredNormalGeometry.moveTop(max(restoredNormalGeometry.top(), 0 + frameHeight))
        if maximized or fullScreen:
            self.setGeometry(restoredNormalGeometry)
            ws = self.windowState()
            if maximized:
                ws |= Qt.WindowMaximized
            if fullScreen:
                ws |= Qt.WindowFullScreen
            self.setWindowState(ws)
        else:
            offset = QPoint()
            self.setWindowState(self.windowState() & ~(Qt.WindowMaximized|Qt.WindowFullScreen))
            self.move(restoredFrameGeometry.topLeft() + offset)
            self.resize(restoredNormalGeometry.size())
        return True

class NexxTDockWidget(QDockWidget): # pragma: no cover
    """
    Need subclassing for getting close / show events
    """
    visibleChanged = Signal(bool)

    def closeEvent(self, closeEvent):
        """
        override from QMdiSubWindow
        :param closeEvent: a QCloseEvent instance
        :return:
        """
        self.visibleChanged.emit(False)
        return super().closeEvent(closeEvent)

    def showEvent(self, showEvent):
        """
        override from QMdiSubWindow
        :param closeEvent: a QShowEvent instance
        :return:
        """
        self.visibleChanged.emit(True)
        return super().showEvent(showEvent)

class MainWindow(QMainWindow): # pragma: no cover
    """
    Main Window service for the nexxT frameworks. Other services usually create dock windows, filters use the
    subplot functionality to create grid-layouted views.
    """
    mdiSubWindowCreated = Signal(QMdiSubWindow) # TODO: remove, is not necessary anymore with subplot feature
    aboutToClose = Signal(object)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.config.appActivated.connect(self._appActivated)
        self.mdi = QMdiArea(self)
        self.mdi.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(self.mdi)
        self.menu = self.menuBar().addMenu("Windows")
        self.toolbar = None
        self.managedMdiWindows = []
        self.managedSubplots = {}
        self.windows = {}
        self.activeApp = None
        self._ignoreCloseEvent = False

    def closeEvent(self, closeEvent):
        """
        Override from QMainWindow, saves the state.
        :param closeEvent: a QCloseEvent instance
        :return:
        """
        self._ignoreCloseEvent = False
        self.aboutToClose.emit(self)
        if self._ignoreCloseEvent:
            logger.info("Ignoring event")
            closeEvent.ignore()
            return
        closeEvent.accept()
        self.saveState()
        self.saveMdiState()
        super().closeEvent(closeEvent)

    def ignoreCloseEvent(self):
        """
        Can be called in slots connected to aboutToClose for requesting to ignore the event.
        Use case is the "There are unsaved changes" dialog.
        :return:
        """
        self._ignoreCloseEvent = True

    def restoreState(self):
        """
        restores the state of the main window including the dock windows of Services
        :return:
        """
        logger.info("restoring main window's state")
        settings = QSettings()
        v = settings.value("MainWindowState")
        if v is not None:
            super().restoreState(v)
        v = settings.value("MainWindowGeometry")
        if v is not None:
            self.restoreGeometry(v)
        if self.toolbar is not None:
            # TODO: add toolbar to windows menu, so we don't need this
            self.toolbar.show()

    def saveState(self):
        """
        saves the state of the main window including the dock windows of Services
        :return:
        """
        logger.info("saving main window's state")
        settings = QSettings()
        settings.setValue("MainWindowState", super().saveState())
        settings.setValue("MainWindowGeometry", self.saveGeometry())

    def saveMdiState(self):
        """
        saves the state of the individual MDI windows
        :return:
        """
        for i in self.managedMdiWindows:
            window = i["window"]
            propColl = i["propColl"]
            prefix = i["prefix"]
            logger.debug("save window geometry %s: %s", prefix, window.geometry())
            geom = str(window.saveGeometry().toBase64(), "ascii")
            visible = self.windows[shiboken2.getCppPointer(window)[0]].isChecked() # pylint: disable=no-member
            propColl.setProperty(prefix + "_geom", geom)
            logger.debug("%s is visible: %d", prefix, int(visible))
            propColl.setProperty(prefix + "_visible", int(visible))
        self.managedMdiWindows = []

    def __del__(self):
        logging.getLogger(__name__).debug("deleting MainWindow")

    @Slot()
    def getToolBar(self):
        """
        Get the main toolbar (adds seperators as appropriate).
        :return:
        """
        if self.toolbar is None:
            self.toolbar = self.addToolBar("NexxT")
            self.toolbar.setObjectName("NexxT_main_toolbar")
        else:
            self.toolbar.addSeparator()
        return self.toolbar

    @Slot(str, QObject, int, int)
    def newDockWidget(self, name, parent, defaultArea, allowedArea=Qt.LeftDockWidgetArea|Qt.BottomDockWidgetArea,
                      defaultLoc=None):
        """
        This function is supposed to be called by services
        :param name: the name of the dock window
        :param parent: the parent (usually None)
        :param defaultArea: the default dock area
        :param allowedArea: the allowed dock areas
        :return: a new QDockWindow instance
        """
        res = NexxTDockWidget(name, parent if parent is not None else self)
        res.setAllowedAreas(allowedArea)
        res.setAttribute(Qt.WA_DeleteOnClose, False)
        self.addDockWidget(defaultArea, res)
        self._registerWindow(res, res.objectNameChanged)
        res.setObjectName(name)
        if defaultLoc is not None:
            dl = self.findChild(QDockWidget, defaultLoc)
            if dl is not None:
                self.tabifyDockWidget(dl, res)
        return res

    @staticmethod
    def parseWindowId(windowId):
        """
        convers a subplot window id into windowTitle, row and column
        :param windowId: the window id
        :return: title, row, column
        """
        regexp = re.compile(r"([^\[]+)\[(\d+),\s*(\d+)\]")
        match = regexp.match(windowId)
        if not match is None:
            return match.group(1), int(match.group(2)), int(match.group(3))
        return windowId, 0, 0

    @Slot(str, QObject, QWidget)
    def subplot(self, windowId, theFilter, widget):
        """
        Adds widget to the GridLayout specified by windowId.
        :param windowId: a string with the format "<windowTitle>[<row>,<col>]" where <windowTitle> is the caption
                         of the MDI window (and it is used as identifier for saving/restoring window state) and
                         <row>, <col> are the coordinates of the addressed subplots (starting at 0)
        :param theFilter:a Filter instance which is requesting the subplot
        :param widget:   a QWidget which shall be placed into the grid layout. Note that this widget is reparented
                         as a result of this operation and the parents can be used to get access to the MDI sub window.
                         Use releaseSubplot to remove the window
        :return: None
        """
        logger.internal("subplot '%s'", windowId)
        title, row, col = self.parseWindowId(windowId)
        if not title in self.managedSubplots:
            subWindow = self._newMdiSubWindow(theFilter, title)
            swwidget = QWidget()
            subWindow.setWidget(swwidget)
            layout = QGridLayout(swwidget)
            self.managedSubplots[title] = dict(mdiSubWindow=subWindow, layout=layout, swwidget=swwidget, plots={})
        self.managedSubplots[title]["layout"].addWidget(widget, row, col)
        widget.setParent(self.managedSubplots[title]["swwidget"])
        self.managedSubplots[title]["plots"][row, col] = widget

    @Slot(str)
    def releaseSubplot(self, windowId):
        """
        This needs to be called to release the previously allocated subplot called windowId.
        The managed widget is deleted as a consequence of this function.

        :param windowId: see subplot(...) for details.
        :return:
        """
        logger.internal("releaseSubplot '%s'", windowId)
        title, row, col = self.parseWindowId(windowId)
        if title not in self.managedSubplots or (row, col) not in self.managedSubplots[title]["plots"]:
            logger.warning("releasSubplot: cannot find %s", windowId)
            return
        self.managedSubplots[title]["layout"].removeWidget(self.managedSubplots[title]["plots"][row, col])
        self.managedSubplots[title]["plots"][row, col].deleteLater()
        del self.managedSubplots[title]["plots"][row, col]
        if len(self.managedSubplots[title]["plots"]) == 0:
            self.managedSubplots[title]["layout"].deleteLater()
            self.managedSubplots[title]["swwidget"].deleteLater()
            self.managedSubplots[title]["mdiSubWindow"].deleteLater()
            del self.managedSubplots[title]

    @Slot(QObject)
    @Slot(QObject, str)
    def newMdiSubWindow(self, filterOrService, windowTitle=None):
        """
        Deprectated (use subplot(...) instead): This function is supposed to be called by filters.
        :param filterOrService: a Filter instance
        :param windowTitle: the title of the window (might be None)
        :return: a new QMdiSubWindow instance
        """
        logger.warning("This function is deprecated. Use subplot function instead.")
        return self._newMdiSubWindow(filterOrService, windowTitle)

    def _newMdiSubWindow(self, filterOrService, windowTitle):
        res = NexxTMdiSubWindow(None)
        res.setAttribute(Qt.WA_DeleteOnClose, False)
        self.mdi.addSubWindow(res)
        self._registerWindow(res, res.windowTitleChanged)
        if isinstance(filterOrService, Filter):
            propColl = filterOrService.guiState()
            res.setWindowTitle(propColl.objectName() if windowTitle is None else windowTitle)
        else:
            app = Application.activeApplication.getApplication()
            propColl = app.guiState("services/MainWindow")
            res.setWindowTitle("<unnamed>" if windowTitle is None else windowTitle)
        prefix = re.sub(r'[^A-Za-z_0-9]', '_', "MainWindow_MDI_" + res.windowTitle())
        i = dict(window=res, propColl=propColl, prefix=prefix)
        self.managedMdiWindows.append(i)
        window = i["window"]
        propColl = i["propColl"]
        prefix = i["prefix"]
        propColl.defineProperty(prefix + "_geom", "", "Geometry of MDI window")
        b = QByteArray.fromBase64(bytes(propColl.getProperty(prefix + "_geom"), "ascii"))
        window.restoreGeometry(b)
        logger.debug("restored geometry %s:%s (%s)", prefix, window.geometry(), b)
        propColl.defineProperty(prefix + "_visible", 1, "Visibility of MDI window")
        if propColl.getProperty(prefix + "_visible"):
            window.show()
        else:
            window.hide()
        self.mdiSubWindowCreated.emit(res)
        return res

    def _registerWindow(self, window, nameChangedSignal):
        act = QAction("<unnamed>", self)
        act.setCheckable(True)
        act.toggled.connect(window.setVisible)
        window.visibleChanged.connect(act.setChecked)
        nameChangedSignal.connect(act.setText)
        self.windows[shiboken2.getCppPointer(window)[0]] = act # pylint: disable=no-member
        self.menu.addAction(act)
        logger.debug("Registering window %s, new len=%d",
                     shiboken2.getCppPointer(window), len(self.windows)) # pylint: disable=no-member
        window.destroyed.connect(self._windowDestroyed)

    def _windowDestroyed(self, obj):
        logger.internal("_windowDestroyed")
        ptr = shiboken2.getCppPointer(obj) # pylint: disable=no-member
        try:
            ptr = ptr[0]
        except TypeError:
            pass
        logger.debug("Deregistering window %s, old len=%d", ptr, len(self.windows))
        self.windows[ptr].deleteLater()
        del self.windows[ptr]
        logger.debug("Deregistering window %s done", ptr)

    def _appActivated(self, name, app):
        if app is not None:
            self.activeApp = name
            app.aboutToClose.connect(self.saveMdiState, Qt.UniqueConnection)
        else:
            self.activeApp = None
