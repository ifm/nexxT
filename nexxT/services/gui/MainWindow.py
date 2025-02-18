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
import subprocess
import time
import sys
import nexxT.shiboken
from nexxT.Qt.QtWidgets import (QMainWindow, QMdiArea, QMdiSubWindow, QDockWidget, QWidget, QGridLayout,
                               QMenuBar, QMessageBox, QScrollArea, QLabel)
from nexxT.Qt.QtCore import (QObject, Signal, Slot, Qt, QByteArray, QDataStream, QIODevice, QRect, QPoint, QSettings,
                            QTimer, QUrl, QEvent)
from nexxT.Qt.QtGui import QDesktopServices, QAction, QActionGroup
import nexxT
from nexxT.interface import Filter
from nexxT.core.Application import Application
from nexxT.core.Utils import handleException, assertMainThread

logger = logging.getLogger(__name__)

class NexxTMdiSubWindow(QMdiSubWindow):
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
        stream.writeUInt32(int(bool(self.windowState() & Qt.WindowMaximized)))
        stream.writeUInt32(int(bool(self.windowState() & Qt.WindowFullScreen)))
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
        maximized = bool(stream.readUInt32())
        fullScreen = bool(stream.readUInt32())
        frameHeight = 0
        if (not restoredNormalGeometry.isValid()) and (restoredFrameGeometry.isValid()):
            # there seems to be an issue in PySide6 that the normalGeometry is always invalid (?)
            restoredNormalGeometry = restoredFrameGeometry
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

class NexxTDockWidget(QDockWidget):
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

class MainWindow(QMainWindow):
    """
    Main Window service for the nexxT frameworks. Other services usually create dock windows, filters use the
    subplot functionality to create grid-layouted views.
    """
    mdiSubWindowCreated = Signal(QMdiSubWindow) # TODO: deprecated, can be removed in later versions
    aboutToClose = Signal(object)
    userSelectionChanged = Signal(str, QPoint)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.config.appActivated.connect(self._appActivated)
        self.mdi = QMdiArea(self)
        self.mdi.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdi.viewport().installEventFilter(self)
        self.setCentralWidget(self.mdi)
        self.menu = self.menuBar().addMenu("&Windows")
        self.framerateMenu = self.menu.addMenu("Display Framerate")
        self.framerateActionGroup = QActionGroup(self)
        self.framerate = 25
        for framerate in [1, 2, 5, 10, 15, 20, 25, 40, 50, 100]:
            a = QAction(self)
            a.setData(framerate)
            a.setText(f"{framerate} Hz")
            a.setCheckable(True)
            if framerate == self.framerate:
                a.setChecked(True)
            a.toggled.connect(self._setFramerate)
            self.framerateActionGroup.addAction(a)
            self.framerateMenu.addAction(a)
        self.config.configLoaded.connect(self.restoreConfigSpecifics)
        self.config.configAboutToSave.connect(self.saveConfigSpecifics)
        closeAllPlotsAction = QAction("Close all plots", self)
        closeAllPlotsAction.triggered.connect(self._closeAllPlots)
        self.menu.addAction(closeAllPlotsAction)
        showAllPlotsAction = QAction("Show all plots", self)
        showAllPlotsAction.triggered.connect(self._showAllPlots)
        self.menu.addAction(showAllPlotsAction)
        cascadeAction = QAction("Cascade plots", self)
        cascadeAction.triggered.connect(self.mdi.cascadeSubWindows)
        self.menu.addAction(cascadeAction)
        tileAction = QAction("Tile plots", self)
        tileAction.triggered.connect(self.mdi.tileSubWindows)
        self.menu.addAction(tileAction)
        self.dockWindowsMenu = self.menu.addMenu("Dock Windows")
        self.menu.addSeparator()
        self.aboutMenu = QMenuBar(self.menuBar())
        self.menuBar().setCornerWidget(self.aboutMenu)
        m = self.aboutMenu.addMenu("&Help")
        self.helpNexxT = QAction("Help ...")
        self.aboutNexxT = QAction("About nexxT ...")
        self.aboutQt = QAction("About Qt ...")
        self.aboutPython = QAction("About Python ...")
        m.addActions([self.helpNexxT])
        m.addSeparator()
        m.addActions([self.aboutNexxT, self.aboutQt, self.aboutPython])
        self.helpNexxT.triggered.connect(lambda: QDesktopServices.openUrl(QUrl("https://nexxT.readthedocs.org")))
        self.aboutNexxT.triggered.connect(lambda: QMessageBox.about(self, "About nexxT", f"""\
This program uses <b>nexxT</b> {nexxT.__version__}, a generic hybrid python/c++ framework for developing computer vision 
algorithms.<br><br>

nexxT is available under the <a href='https://github.com/ifm/nexxT/blob/master/LICENSE'>Apache 2.0 License</a> together 
with the <a href='https://github.com/ifm/nexxT/blob/master/NOTICE'>notice</a>. 
"""))
        self.aboutQt.triggered.connect(lambda: QMessageBox.aboutQt(self))
        self.aboutPython.triggered.connect(self._aboutPython)
        self.toolbar = None
        self.managedMdiWindows = []
        self.managedSubplots = {}
        self.windows = {}
        self.activeApp = None
        self._ignoreCloseEvent = False
        self._deferredUpdateHistory = {}
        self._pendingUpdates = set()
        self._deferredUpdateTimer = QTimer()
        self._deferredUpdateTimer.setSingleShot(True)
        self._deferredUpdateTimer.timeout.connect(self._deferredUpdateTimeout)

    def eventFilter(self, obj, event):
        """
        Overwritten from QObject, for disabling mouse wheel scrolling on the main widget's viewport
        """
        if obj is self.mdi.viewport() and event.type() == QEvent.Wheel:
            # disable mouse wheel scrolling on the viewport widget it's pretty annoying...
            return True
        return False

    @Slot(QObject, str)
    def deferredUpdate(self, obj, slotName):
        """
        Call this method to defer a call to the sepcified slot (obj->slotName()) in accordance with the user-defined
        framerate set. The slot will be called via getattr(obj, slotName)()

        :param obj: A QObject instance
        :param slotName: The name of the slot.
        """
        self._deferredUpdate(obj, slotName)

    @handleException
    def _deferredUpdate(self, obj, slotName):
        assertMainThread()
        if (obj, slotName) in self._deferredUpdateHistory:
            lastUpdateTime = self._deferredUpdateHistory[obj, slotName]
            dt = 1e-9*(time.monotonic_ns() - lastUpdateTime)
            if dt < 1/self.framerate:
                if len(self._pendingUpdates) == 0:
                    self._deferredUpdateTimer.start(int((1/self.framerate - dt)*1000))
                self._pendingUpdates.add((obj, slotName))
                return
        self._deferredUpdateHistory[obj, slotName] = time.monotonic_ns()
        clb = getattr(obj, slotName)
        clb()

    def _deferredUpdateTimeout(self):
        t = time.monotonic_ns()
        for obj, slotName in self._pendingUpdates:
            clb = getattr(obj, slotName)
            self._deferredUpdateHistory[obj, slotName] = t
            clb()
        self._pendingUpdates.clear()

    def _setFramerate(self, checked):
        if checked:
            self.framerate = self.sender().data()

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
        logger.debug("restoring main window's state")
        settings = QSettings()
        v = settings.value("MainWindowState")
        if v is not None:
            super().restoreState(v)
        v = settings.value("MainWindowGeometry")
        if v is not None:
            self.restoreGeometry(v)
        if self.toolbar is not None:
            self.toolbar.show()

    def restoreConfigSpecifics(self):
        """
        restores the config-specific state of the main window.
        """
        propertyCollection = self.config.guiState()
        propertyCollection.defineProperty("MainWindow_framerate", 10, "Display framerate set by user.")
        framerate = propertyCollection.getProperty("MainWindow_framerate")
        logger.debug("Set framerate to %d", framerate)
        for a in self.framerateActionGroup.actions():
            if a.data() == framerate:
                a.setChecked(True)

    def saveState(self):
        """
        saves the state of the main window including the dock windows of Services

        :return:
        """
        logger.debug("saving main window's state")
        settings = QSettings()
        settings.setValue("MainWindowState", super().saveState())
        settings.setValue("MainWindowGeometry", self.saveGeometry())

    def saveConfigSpecifics(self):
        """
        saves the config-specific state of the main window.
        """
        propertyCollection = self.config.guiState()
        propertyCollection.defineProperty("MainWindow_framerate", 10, "Display framerate set by user.")
        propertyCollection.setProperty("MainWindow_framerate", self.framerate)
        logger.debug("Store framerate %d", self.framerate)

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
            visible = self.windows[nexxT.shiboken.getCppPointer(window)[0]].isChecked() # pylint: disable=no-member
            propColl.setProperty(prefix + "_geom", geom)
            logger.debug("%s is visible: %d", prefix, int(visible))
            propColl.setProperty(prefix + "_visible", int(visible))
        self.managedMdiWindows = []

    @Slot()
    def _closeAllPlots(self):
        """
        Slot to close all MDI windows
        """
        for i in self.managedMdiWindows:
            w = i["window"]
            w.hide()
            self.windows[nexxT.shiboken.getCppPointer(w)[0]].setChecked(False)

    @Slot()
    def _showAllPlots(self):
        """
        Slot to close all MDI windows
        """
        for i in self.managedMdiWindows:
            i["window"].show()

    def __del__(self):
        logging.getLogger(__name__).debug("deleting MainWindow")

    @Slot(str, QPoint)
    def updateSelection(self, group, point):
        """
        QT Meta-function which can be called to update the 2D selection.

        :param group: the group name given as str/QString
        :param point: the new selection point given as QPoint
        """
        self.userSelectionChanged.emit(group, point)

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

    @staticmethod
    def _substWindowTitle(title, theFilter):
        if title == "":
            title = "${FULLQUALIFIEDFILTERNAME}"
        if ("${COMPOSITENAME}" in title or
                "${FILTERNAME}" in title or
                "${FULLQUALIFIEDFILTERNAME}" in title):
            logger.warning("Deprecated: implicit variable substitution for window titles - "
                           "use explicit variable substitution instead.")
            if isinstance(theFilter, Filter):
                name = theFilter.environment().getFullQualifiedName()
                if "/" in name:
                    pos = name.rfind("/")
                    composite_name = name[:pos]
                    filter_name = name[pos+1:]
                else:
                    composite_name = "<root>"
                    filter_name = name
                title = (title.replace("${COMPOSITENAME}", composite_name).
                         replace("${FILTERNAME}", filter_name).
                         replace("${FULLQUALIFIEDFILTERNAME}", name))
            else:
                logger.warning("MainWindow.subplot(...,theFilter,...) expected a "
                               "nexxT::Filter instance, but got '%s'", theFilter)
        return title

    @Slot(str, QObject, QWidget)
    def subplot(self, windowId, theFilter, widget):
        """
        Adds widget to the GridLayout specified by windowId.

        :param windowId: a string with the format "<windowTitle>[<row>,<col>]" where <windowTitle> is the caption
                         of the MDI window (and it is used as identifier for saving/restoring window state) and
                         <row>, <col> are the coordinates of the addressed subplots (starting at 0)
        :param theFilter: a Filter instance which is requesting the subplot
        :param widget:   a QWidget which shall be placed into the grid layout. Note that this widget is reparented
                         as a result of this operation and the parents can be used to get access to the MDI sub window.
                         Use releaseSubplot to remove the window
        :return: None
        """
        logger.internal("subplot '%s'", windowId)
        title, row, col = self.parseWindowId(windowId)
        title = self._substWindowTitle(title, theFilter)
        if title in self.managedSubplots and (row, col) in self.managedSubplots[title]["plots"]:
            logger.warning("subplot %s[%d,%d] is already registered. Creating a new window for the plot.",
                           title, row, col)
            i = 2
            while f"{title}({i})" in self.managedSubplots:
                i += 1
            title = f"{title}({i})"
            row = 0
            col = 0
        if title not in self.managedSubplots:
            subWindow = self._newMdiSubWindow(theFilter, title)
            swwidget = QWidget()
            subWindow.setWidget(swwidget)
            layout = QGridLayout(swwidget)
            swwidget.setLayout(layout)
            self.managedSubplots[title] = dict(mdiSubWindow=subWindow, layout=layout, swwidget=swwidget, plots={})
        self.managedSubplots[title]["layout"].addWidget(widget, row, col)
        self.managedSubplots[title]["mdiSubWindow"].updateGeometry()
        widget.setParent(self.managedSubplots[title]["swwidget"])
        # note: there seems to be a race condition when decreasing the single shot timeout to 0
        #       sometimes the window size is then not correctly adjusted
        #       with the 100 ms timeout this couldn't be reproduced
        QTimer.singleShot(100, lambda: (
            self.managedSubplots[title]["mdiSubWindow"].adjustSize() if
            nexxT.shiboken.isValid(widget) and ( # pylint: disable=no-member
                widget.parent().size().height() < widget.minimumSizeHint().height() or
                widget.parent().size().height() < widget.minimumSize().height()) else None
        ))
        self.managedSubplots[title]["plots"][row, col] = widget

    @Slot(QWidget)
    @Slot(str)
    def releaseSubplot(self, arg):
        """
        This needs to be called to release the previously allocated subplot called windowId.
        The managed widget is deleted as a consequence of this function.

        :param arg: the widget as passed to subplot. Passing the windowId is also supported, but deprecated.
        :return:
        """
        if isinstance(arg, str):
            windowId = arg
            logger.warning("Using deprecated API to release a subplot. Please pass the widget instead of the windowId.")
            logger.internal("releaseSubplot '%s'", windowId)
            title, row, col = self.parseWindowId(windowId)
            if title not in self.managedSubplots or (row, col) not in self.managedSubplots[title]["plots"]:
                logger.warning("releasSubplot: cannot find %s", windowId)
                return
            widget = self.managedSubplots[title]["plots"][row, col]
        elif isinstance(arg, QWidget):
            widget = arg
            found = False
            for title, sp in self.managedSubplots.items():
                for row, col in sp["plots"]:
                    if sp["plots"][row, col] is widget:
                        found = True
                        break
                if found:
                    break
            if not found:
                raise RuntimeError("cannot find widget given for releaseSubplot.")
        else:
            raise RuntimeError("arg of releaseSubplot must be either a string or a QWidget instance.")
        self.managedSubplots[title]["layout"].removeWidget(widget)
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
        def ensureVisible():
            # see issue https://github.com/ifm/nexxT/issues/64
            if window.isFloating():
                window.setFloating(False)
            window.setVisible(True)
            act.setChecked(True)
            window.raise_()
            if isinstance(window, QMdiSubWindow):
                self.mdi.setActiveSubWindow(window)
                x = self.mdi.horizontalScrollBar().value()
                y = self.mdi.verticalScrollBar().value()
                w = self.mdi.viewport().width()
                h = self.mdi.viewport().height()
                r = QRect(x, y, w, h)
                g = window.geometry()
                logger.debug("r=%s w=%s", r, g)
                if not r.intersects(g):
                    self.mdi.horizontalScrollBar().setValue(g.x())
                    self.mdi.verticalScrollBar().setValue(g.y())
        act.setCheckable(True)
        act.triggered.connect(ensureVisible)
        window.visibleChanged.connect(act.setChecked)
        nameChangedSignal.connect(act.setText)
        self.windows[nexxT.shiboken.getCppPointer(window)[0]] = act # pylint: disable=no-member
        if not isinstance(window, QDockWidget):
            self.menu.addAction(act)
        else:
            self.dockWindowsMenu.addAction(act)
        logger.debug("Registering window %s, new len=%d",
                     nexxT.shiboken.getCppPointer(window), len(self.windows)) # pylint: disable=no-member
        window.destroyed.connect(self._windowDestroyed)

    def _windowDestroyed(self, obj):
        logger.internal("_windowDestroyed")
        ptr = nexxT.shiboken.getCppPointer(obj) # pylint: disable=no-member
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

    def _aboutPython(self):
        piplic = subprocess.check_output([sys.executable, "-m", "piplicenses", "--format=plain"],
                                         encoding="utf-8").replace("\n", "<br>").replace(" ", "&nbsp;")
        piplic = piplic.replace("<br>", "<br><br>", 1)
        msgBox = QMessageBox()
        msgBox.setText("This program uses <b>python</b> %(version)s. The used packages are listed below." %
                       dict(version=sys.version, table=piplic))
        view = QScrollArea(msgBox)
        label = QLabel("<pre>%(table)s</pre>" % dict(version=sys.version, table=piplic), msgBox)
        label.setTextInteractionFlags(Qt.TextSelectableByKeyboard|Qt.TextSelectableByMouse)
        view.setWidgetResizable(True)
        view.setWidget(label)
        msgBox.layout().addWidget(view, 3, 0, 1, msgBox.layout().columnCount())
        msgBox.exec_()
