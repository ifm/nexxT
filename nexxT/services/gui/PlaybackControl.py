# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the nexxT GUI service PlaybackControl
"""
import functools
import logging
import os
from PySide2.QtCore import Signal, QDateTime, Qt, QTimer
from PySide2.QtWidgets import (QWidget, QGridLayout, QLabel, QBoxLayout, QSlider, QToolBar, QAction, QApplication,
                               QStyle, QLineEdit, QFileSystemModel, QTreeView, QHeaderView, QActionGroup)
from nexxT.interface import Services
from nexxT.core.Exceptions import PropertyCollectionPropertyNotFound
from nexxT.core.Utils import FileSystemModelSortProxy, assertMainThread
from nexxT.services.SrvPlaybackControl import PlaybackControlConsole

logger = logging.getLogger(__name__)

class MVCPlaybackControlGUI(PlaybackControlConsole): # pragma: no cover
    """
    GUI implementation of MVCPlaybackControlBase
    """
    nameFiltersChanged = Signal("QStringList")

    def __init__(self, config):
        assertMainThread()
        super().__init__(config)

        # state
        self.preventSeek = False
        self.beginTime = None
        self.timeRatio = 1.0

        # gui
        srv = Services.getService("MainWindow")
        config.configLoaded.connect(self.restoreState)
        config.configAboutToSave.connect(self.saveState)
        self.config = config
        playbackMenu = srv.menuBar().addMenu("&Playback")

        self.actStart = QAction(QApplication.style().standardIcon(QStyle.SP_MediaPlay), "Start Playback", self)
        self.actPause = QAction(QApplication.style().standardIcon(QStyle.SP_MediaPause), "Pause Playback", self)
        self.actPause.setEnabled(False)
        self.actStepFwd = QAction(QApplication.style().standardIcon(QStyle.SP_MediaSeekForward), "Step Forward", self)
        self.actStepBwd = QAction(QApplication.style().standardIcon(QStyle.SP_MediaSeekBackward), "Step Backward", self)
        self.actSeekEnd = QAction(QApplication.style().standardIcon(QStyle.SP_MediaSkipForward), "Seek End", self)
        self.actSeekBegin = QAction(QApplication.style().standardIcon(QStyle.SP_MediaSkipBackward), "Seek Begin", self)
        self.actSetTimeFactor = {r : QAction("x 1/%d" % (1/r), self) if r < 1 else QAction("x %d" % r, self)
                                 for r in (1/8, 1/4, 1/2, 1, 2, 4, 8)}

        # pylint: disable=unnecessary-lambda
        # let's stay on the safe side and do not use emit as a slot...
        self.actStart.triggered.connect(lambda: self._startPlayback.emit())
        self.actPause.triggered.connect(lambda: self._pausePlayback.emit())
        self.actStepFwd.triggered.connect(lambda: self._stepForward.emit(self.selectedStream()))
        self.actStepBwd.triggered.connect(lambda: self._stepBackward.emit(self.selectedStream()))
        self.actSeekEnd.triggered.connect(lambda: self._seekEnd.emit())
        self.actSeekBegin.triggered.connect(lambda: self._seekBeginning.emit())
        # pylint: enable=unnecessary-lambda

        def setTimeFactor(newFactor):
            logger.debug("new time factor %f", newFactor)
            self._setTimeFactor.emit(newFactor)

        for r in self.actSetTimeFactor:
            logger.debug("adding action for time factor %f", r)
            self.actSetTimeFactor[r].triggered.connect(functools.partial(setTimeFactor, r))

        self.dockWidget = srv.newDockWidget("PlaybackControl", None, Qt.LeftDockWidgetArea)
        self.dockWidgetContents = QWidget(self.dockWidget)
        self.dockWidget.setWidget(self.dockWidgetContents)
        toolLayout = QBoxLayout(QBoxLayout.TopToBottom, self.dockWidgetContents)
        toolLayout.setContentsMargins(0, 0, 0, 0)
        toolBar = QToolBar()
        toolLayout.addWidget(toolBar)
        toolBar.addAction(self.actSeekBegin)
        toolBar.addAction(self.actStepBwd)
        toolBar.addAction(self.actStart)
        toolBar.addAction(self.actPause)
        toolBar.addAction(self.actStepFwd)
        toolBar.addAction(self.actSeekEnd)
        playbackMenu.addAction(self.actSeekBegin)
        playbackMenu.addAction(self.actStepBwd)
        playbackMenu.addAction(self.actStart)
        playbackMenu.addAction(self.actPause)
        playbackMenu.addAction(self.actStepFwd)
        playbackMenu.addAction(self.actSeekEnd)
        playbackMenu.addSeparator()
        for r in self.actSetTimeFactor:
            playbackMenu.addAction(self.actSetTimeFactor[r])
        self.timeRatioLabel = QLabel("x 1")
        self.timeRatioLabel.addActions(list(self.actSetTimeFactor.values()))
        self.timeRatioLabel.setContextMenuPolicy(Qt.ActionsContextMenu)
        toolBar.addSeparator()
        toolBar.addWidget(self.timeRatioLabel)
        contentsLayout = QGridLayout()
        toolLayout.addLayout(contentsLayout, 10)
        # now we add a position view
        self.positionSlider = QSlider(Qt.Horizontal, self.dockWidgetContents)
        self.beginLabel = QLabel(parent=self.dockWidgetContents)
        self.beginLabel.setAlignment(Qt.AlignLeft|Qt.AlignCenter)
        self.currentLabel = QLabel(parent=self.dockWidgetContents)
        self.currentLabel.setAlignment(Qt.AlignHCenter|Qt.AlignCenter)
        self.endLabel = QLabel(parent=self.dockWidgetContents)
        self.endLabel.setAlignment(Qt.AlignRight|Qt.AlignCenter)
        contentsLayout.addWidget(self.beginLabel, 0, 0, alignment=Qt.AlignLeft)
        contentsLayout.addWidget(self.currentLabel, 0, 1, alignment=Qt.AlignHCenter)
        contentsLayout.addWidget(self.endLabel, 0, 2, alignment=Qt.AlignRight)
        contentsLayout.addWidget(self.positionSlider, 1, 0, 1, 3)
        self.filenameLabel = QLineEdit(parent=self.dockWidgetContents)
        self.filenameLabel.setReadOnly(True)
        self.filenameLabel.setFrame(False)
        self.filenameLabel.setStyleSheet("* { background-color: rgba(0, 0, 0, 0); }")
        contentsLayout.addWidget(self.filenameLabel, 2, 0, 1, 3)
        self.positionSlider.setTracking(False)
        self.positionSlider.valueChanged.connect(self.onSliderValueChanged, Qt.DirectConnection)
        self.positionSlider.sliderMoved.connect(self.displayPosition)

        # file browser
        self.fileSystemModel = QFileSystemModel()
        self.fileSystemModel.setNameFilterDisables(False)
        self.fileSystemModel.setRootPath("/")
        self.nameFiltersChanged.connect(lambda nameFilt: (getattr(self, "fileSystemModel").setNameFilters(nameFilt),
                                                          self.refreshBrowser()
                                                          ), Qt.QueuedConnection)

        self.browser = QTreeView(parent=self.dockWidgetContents)
        self.useProxy = True
        if self.useProxy:
            self.proxyFileSystemModel = FileSystemModelSortProxy(self)
            self.proxyFileSystemModel.setSourceModel(self.fileSystemModel)
            self.browser.setModel(self.proxyFileSystemModel)
        else:
            self.browser.setModel(self.fileSystemModel)
        self.browser.setSortingEnabled(True)
        self.browser.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.browser.setUniformRowHeights(True)
        self.browser.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.browser.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.browser.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.browser.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.browser.header().resizeSection(0, 500)
        contentsLayout.addWidget(self.browser, 3, 0, 1, 3)
        contentsLayout.setRowStretch(3, 100)
        self.browser.doubleClicked.connect(self.browserCurrentChanged)
        self.browser.selectionModel().currentChanged.connect(self.browserCurrentChanged)

        self.actShowAllFiles = QAction("Show all files")
        self.actShowAllFiles.setCheckable(True)
        self.actShowAllFiles.setChecked(False)
        self.actShowAllFiles.toggled.connect(lambda on: (getattr(self, "fileSystemModel").setNameFilterDisables(on),
                                                         self.refreshBrowser()))
        self.actRefreshBrowser = QAction("Refresh browser")
        self.actRefreshBrowser.triggered.connect(self.refreshBrowser)
        playbackMenu.addSeparator()
        playbackMenu.addAction(self.actShowAllFiles)
        playbackMenu.addAction(self.actRefreshBrowser)

        self.actGroupStream = QActionGroup(self)
        self.actGroupStream.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        playbackMenu.addSeparator()
        self.actGroupStreamMenu = playbackMenu.addMenu("Step Stream")
        self._selectedStream = None

        self.recentSeqs = [QAction() for i in range(10)]
        playbackMenu.addSeparator()
        recentMenu = playbackMenu.addMenu("Recent")
        for a in self.recentSeqs:
            a.setVisible(False)
            a.triggered.connect(self.openRecent)
            recentMenu.addAction(a)

        self._supportedFeaturesChanged(set(), set())

    def __del__(self):
        logger.debug("deleting playback control")

    def _supportedFeaturesChanged(self, featureset, nameFilters):
        """
        overwritten from MVCPlaybackControlBase. This function is called
        from multiple threads, but not at the same time.
        :param featureset: the current featureset
        :return:
        """
        self.featureset = featureset
        self.actStepFwd.setEnabled("stepForward" in featureset)
        self.actStepBwd.setEnabled("stepBackward" in featureset)
        self.actSeekBegin.setEnabled("seekBeginning" in featureset)
        self.actSeekEnd.setEnabled("seekEnd" in featureset)
        self.positionSlider.setEnabled("seekTime" in featureset)
        self.browser.setEnabled("setSequence" in featureset)
        self.timeRatioLabel.setEnabled("setTimeFactor" in featureset)
        for f in self.actSetTimeFactor:
            self.actSetTimeFactor[f].setEnabled("setTimeFactor" in featureset)
        self.timeRatioLabel.setEnabled("setTimeFactor" in featureset)
        self.timeRatioLabel.setEnabled("setTimeFactor" in featureset)
        self.timeRatioLabel.setEnabled("setTimeFactor" in featureset)
        self.timeRatioLabel.setEnabled("setTimeFactor" in featureset)
        if "startPlayback" not in featureset:
            self.actStart.setEnabled(False)
        if "pausePlayback" not in featureset:
            self.actPause.setEnabled(False)
        logger.info("current feature set: %s", featureset)
        logger.debug("Setting name filters of browser: %s", list(nameFilters))
        self.nameFiltersChanged.emit(list(nameFilters))

    def refreshBrowser(self):
        """
        It looks like QFileSystemModel is rather broken when it comes to automatically refresh
        This is a workaround...
        :return:
        """
        assertMainThread()
        newModel = QFileSystemModel()
        newModel.setRootPath("/")
        logger.debug("setNameFilterDisables %d", self.fileSystemModel.nameFilterDisables())
        newModel.setNameFilterDisables(self.fileSystemModel.nameFilterDisables())
        logger.debug("setNameFilters %s", self.fileSystemModel.nameFilters())
        newModel.setNameFilters(self.fileSystemModel.nameFilters())
        currentIdx = self.browser.currentIndex()
        if self.useProxy:
            currentIdx = self.proxyFileSystemModel.mapToSource(currentIdx)
        currentFile = self.fileSystemModel.filePath(currentIdx)
        logger.debug("got current file: %s", currentFile)
        if self.useProxy:
            self.proxyFileSystemModel.setSourceModel(newModel)
        oldModel = self.fileSystemModel
        self.fileSystemModel = newModel
        oldModel.deleteLater()
        idx = self.fileSystemModel.index(currentFile)
        if self.useProxy:
            idx = self.proxyFileSystemModel.mapFromSource(idx)
        self.browser.setCurrentIndex(idx)
        self.browser.scrollTo(idx)
        QTimer.singleShot(250, self.scrollToCurrent)

    def scrollToCurrent(self):
        """
        Scrolls to the current item in the browser
        :return:
        """
        assertMainThread()
        idx = self.browser.currentIndex()
        if idx.isValid():
            self.browser.scrollTo(idx)

    def _sequenceOpened(self, filename, begin, end, streams):
        """
        Notifies about an opened sequence.
        :param filename: the filename which has been opened
        :param begin: timestamp of sequence's first sample
        :param end: timestamp of sequence's last sample
        :param streams: list of streams in the sequence
        :return: None
        """
        assertMainThread()
        self.beginTime = begin
        self.positionSlider.setRange(0, end.toMSecsSinceEpoch() - begin.toMSecsSinceEpoch())
        self.beginLabel.setText(begin.toString("hh:mm:ss.zzz"))
        self.endLabel.setText(end.toString("hh:mm:ss.zzz"))
        self._currentTimestampChanged(begin)
        self.filenameLabel.setText(filename)
        idx = self.fileSystemModel.index(filename)
        if self.useProxy:
            idx = self.proxyFileSystemModel.mapFromSource(idx)
        self.browser.setCurrentIndex(idx)
        self.browser.scrollTo(idx)
        self._selectedStream = None
        for a in self.actGroupStream.actions():
            logger.debug("Remove stream group action: %s", a.data())
            self.actGroupStream.removeAction(a)
        for stream in streams:
            act = QAction(stream, self.actGroupStream)
            act.triggered.connect(lambda cstream=stream: self.setSelectedStream(cstream))
            act.setCheckable(True)
            act.setChecked(False)
            logger.debug("Add stream group action: %s", act.data())
            self.actGroupStreamMenu.addAction(act)
        QTimer.singleShot(250, self.scrollToCurrent)

    def _currentTimestampChanged(self, currentTime):
        """
        Notifies about a changed timestamp
        :param currentTime: the new current timestamp
        :return: None
        """
        assertMainThread()
        if self.beginTime is None:
            self.currentLabel.setText("")
        else:
            sliderVal = currentTime.toMSecsSinceEpoch() - self.beginTime.toMSecsSinceEpoch()
            self.preventSeek = True
            self.positionSlider.setValue(sliderVal)
            self.preventSeek = False
            self.positionSlider.blockSignals(False)
            self.currentLabel.setEnabled(True)
            self.currentLabel.setText(currentTime.toString("hh:mm:ss.zzz"))

    def onSliderValueChanged(self, value):
        """
        Slot called whenever the slider value is changed.
        :param value: the new slider value
        :return:
        """
        assertMainThread()
        if self.beginTime is None or self.preventSeek:
            return
        if self.actStart.isEnabled():
            ts = QDateTime.fromMSecsSinceEpoch(self.beginTime.toMSecsSinceEpoch() + value, self.beginTime.timeSpec())
            self._seekTime.emit(ts)
        else:
            logger.warning("Can't seek while playing.")

    def displayPosition(self, value):
        """
        Slot called when the slider is moved. Displays the position without actually seeking to it.
        :param value: the new slider value.
        :return:
        """
        assertMainThread()
        if self.beginTime is None:
            return
        if self.positionSlider.isSliderDown():
            ts = QDateTime.fromMSecsSinceEpoch(self.beginTime.toMSecsSinceEpoch() + value, self.beginTime.timeSpec())
            self.currentLabel.setEnabled(False)
            self.currentLabel.setText(ts.toString("hh:mm:ss.zzz"))

    def _playbackStarted(self):
        """
        Notifies about starting playback
        :return: None
        """
        assertMainThread()
        self.actStart.setEnabled(False)
        if "pausePlayback" in self.featureset:
            self.actPause.setEnabled(True)

    def _playbackPaused(self):
        """
        Notifies about pause playback
        :return: None
        """
        assertMainThread()
        logger.debug("playbackPaused received")
        if "startPlayback" in self.featureset:
            self.actStart.setEnabled(True)
        self.actPause.setEnabled(False)

    def openRecent(self):
        """
        Called when the user clicks on a recent sequence.
        :return:
        """
        action = self.sender()
        index = self.fileSystemModel.index(action.data(), 0)
        if self.useProxy:
            index = self.proxyFileSystemModel.mapFromSource(index)
            self.browser.setCurrentIndex(index)

    def browserCurrentChanged(self, current):
        """
        Called when the current item of the file browser changed.
        :param current: the proxyFileSystemModel model index
        :return:
        """
        assertMainThread()
        if self.useProxy:
            current = self.proxyFileSystemModel.mapToSource(current)
        if self.fileSystemModel.flags(current) & Qt.ItemIsEnabled and self.fileSystemModel.fileInfo(current).isFile():
            filename = self.fileSystemModel.filePath(current)
            foundIdx = None
            for i, a in enumerate(self.recentSeqs):
                if a.data() == filename:
                    foundIdx = i
            if foundIdx is None:
                foundIdx = len(self.recentSeqs)-1
            for i in range(foundIdx, 0, -1):
                self.recentSeqs[i].setText(self.recentSeqs[i-1].text())
                self.recentSeqs[i].setData(self.recentSeqs[i-1].data())
                logger.debug("%d data: %s", i, self.recentSeqs[i-1].data())
                self.recentSeqs[i].setVisible(self.recentSeqs[i-1].data() is not None)
            self.recentSeqs[0].setText(filename)
            self.recentSeqs[0].setData(filename)
            self.recentSeqs[0].setVisible(True)
            self._setSequence.emit(filename)

    def _timeRatioChanged(self, newRatio):
        """
        Notifies about a changed playback time ratio,
        :param newRatio the new playback ratio as a float
        :return: None
        """
        assertMainThread()
        self.timeRatio = newRatio
        logger.debug("new timeRatio: %f", newRatio)
        for r in [1/8, 1/4, 1/2, 1, 2, 4, 8]:
            if abs(newRatio / r - 1) < 0.01:
                self.timeRatioLabel.setText(("x 1/%d"%(1/r)) if r < 1 else ("x %d"%r))
                return
        self.timeRatioLabel.setText("%.2f" % newRatio)

    def selectedStream(self):
        """
        Returns the user-selected stream (for forward/backward stepping)
        :return:
        """
        return self._selectedStream

    def setSelectedStream(self, stream):
        """
        Sets the user-selected stream (for forward/backward stepping)
        :param stream the stream name.
        :return:
        """
        self._selectedStream = stream

    def saveState(self):
        """
        Saves the state of the playback control
        :return:
        """
        assertMainThread()
        propertyCollection = self.config.guiState()
        showAllFiles = self.actShowAllFiles.isChecked()
        current = self.browser.currentIndex()
        if self.useProxy:
            current = self.proxyFileSystemModel.mapToSource(current)
        if self.fileSystemModel.flags(current) & Qt.ItemIsEnabled and self.fileSystemModel.fileInfo(current).isFile():
            filename = self.fileSystemModel.filePath(current)
        else:
            filename = ""
        try:
            propertyCollection.setProperty("PlaybackControl_showAllFiles", int(showAllFiles))
            propertyCollection.setProperty("PlaybackControl_filename", filename)
            recentFiles = [a.data() for a in self.recentSeqs if a.data() is not None]
            propertyCollection.setProperty("PlaybackControl_recent", "|".join(recentFiles))
        except PropertyCollectionPropertyNotFound:
            pass

    def restoreState(self):
        """
        Restores the state of the playback control from the given property collection
        :param propertyCollection: a PropertyCollection instance
        :return:
        """
        assertMainThread()
        propertyCollection = self.config.guiState()
        propertyCollection.defineProperty("PlaybackControl_showAllFiles", 0, "show all files setting")
        showAllFiles = propertyCollection.getProperty("PlaybackControl_showAllFiles")
        self.actShowAllFiles.setChecked(bool(showAllFiles))
        propertyCollection.defineProperty("PlaybackControl_filename", "", "current file name")
        filename = propertyCollection.getProperty("PlaybackControl_filename")
        index = self.fileSystemModel.index(os.path.split(filename)[0])
        if self.useProxy:
            index = self.proxyFileSystemModel.mapFromSource(index)
        self.browser.setExpanded(index, True)
        self.browser.scrollTo(index)
        propertyCollection.defineProperty("PlaybackControl_recent", "", "recent opened sequences")
        recentFiles = propertyCollection.getProperty("PlaybackControl_recent")
        idx = 0
        for f in recentFiles.split("|"):
            if f != "":
                self.recentSeqs[idx].setData(f)
                self.recentSeqs[idx].setText(f)
                self.recentSeqs[idx].setVisible(True)
                idx += 1
                if idx >= len(self.recentSeqs):
                    break
        for a in self.recentSeqs[idx:]:
            a.setData(None)
            a.setText("")
            a.setVisible(False)
