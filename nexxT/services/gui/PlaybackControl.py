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
from pathlib import Path
from PySide2.QtCore import Signal, Qt, QTimer, QDir
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import (QWidget, QGridLayout, QLabel, QBoxLayout, QSlider, QToolBar, QAction, QApplication,
                               QStyle, QActionGroup)
from nexxT.interface import Services
from nexxT.core.Exceptions import PropertyCollectionPropertyNotFound
from nexxT.core.Utils import assertMainThread
from nexxT.services.SrvPlaybackControl import PlaybackControlConsole
from nexxT.services.gui.BrowserWidget import BrowserWidget

logger = logging.getLogger(__name__)

class MVCPlaybackControlGUI(PlaybackControlConsole):
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

        style = QApplication.style()
        self.actStart = QAction(QIcon.fromTheme("media-playback-start", style.standardIcon(QStyle.SP_MediaPlay)),
                                "Start Playback", self)
        self.actPause = QAction(QIcon.fromTheme("media-playback-pause", style.standardIcon(QStyle.SP_MediaPause)),
                                "Pause Playback", self)
        self.actPause.setEnabled(False)
        self.actStepFwd = QAction(QIcon.fromTheme("media-seek-forward",
                                                  style.standardIcon(QStyle.SP_MediaSeekForward)),
                                  "Step Forward", self)
        self.actStepBwd = QAction(QIcon.fromTheme("media-seek-backward",
                                                  style.standardIcon(QStyle.SP_MediaSeekBackward)),
                                  "Step Backward", self)
        self.actSeekEnd = QAction(QIcon.fromTheme("media-skip-forward",
                                                  style.standardIcon(QStyle.SP_MediaSkipForward)),
                                  "Seek End", self)
        self.actSeekBegin = QAction(QIcon.fromTheme("media-skip-backward",
                                                    style.standardIcon(QStyle.SP_MediaSkipBackward)),
                                    "Seek Begin", self)
        self.actSetTimeFactor = {r : QAction("x 1/%d" % (1/r), self) if r < 1 else QAction("x %d" % r, self)
                                 for r in (1/8, 1/4, 1/2, 1, 2, 4, 8)}

        # pylint: disable=unnecessary-lambda
        # let's stay on the safe side and do not use emit as a slot...
        self.actStart.triggered.connect(self.startPlayback)
        self.actPause.triggered.connect(self.pausePlayback)
        self.actStepFwd.triggered.connect(lambda: self.stepForward(self.selectedStream()))
        self.actStepBwd.triggered.connect(lambda: self.stepBackward(self.selectedStream()))
        self.actSeekEnd.triggered.connect(self.seekEnd)
        self.actSeekBegin.triggered.connect(self.seekBeginning)
        # pylint: enable=unnecessary-lambda

        def setTimeFactor(newFactor):
            logger.debug("new time factor %f", newFactor)
            self.setTimeFactor(newFactor)

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
        self.positionSlider.setTracking(False)
        self.positionSlider.valueChanged.connect(self.onSliderValueChanged, Qt.DirectConnection)
        self.positionSlider.sliderMoved.connect(self.displayPosition)

        # file browser
        self.browser = BrowserWidget(self.dockWidget)
        self.nameFiltersChanged.connect(self._onNameFiltersChanged, Qt.QueuedConnection)
        contentsLayout.addWidget(self.browser, 3, 0, 1, 3)
        contentsLayout.setRowStretch(3, 100)
        self.browser.activated.connect(self.browserActivated)

        self.actShowAllFiles = QAction("Show all files")
        self.actShowAllFiles.setCheckable(True)
        self.actShowAllFiles.setChecked(False)
        self.actShowAllFiles.toggled.connect(self._onShowAllFiles)
        playbackMenu.addSeparator()
        playbackMenu.addAction(self.actShowAllFiles)

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
        logger.internal("deleting playback control")

    def _onNameFiltersChanged(self, nameFilt):
        self.browser.setFilter(nameFilt)
        if isinstance(nameFilt, str):
            nameFilt = [nameFilt]
        for a in self.recentSeqs:
            if a.isVisible():
                m = QDir.match(nameFilt, Path(a.data()).name)
                a.setEnabled(m)

    def _onShowAllFiles(self, enabled):
        self.fileSystemModel.setNameFilterDisables(enabled)

    def _supportedFeaturesChanged(self, featureset, nameFilters):
        """
        overwritten from MVCPlaybackControlBase. This function is called
        from multiple threads, but not at the same time.

        :param featureset: the current featureset
        :return:
        """
        assertMainThread()
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
        logger.debug("current feature set: %s", featureset)
        logger.debug("Setting name filters of browser: %s", list(nameFilters))
        self.nameFiltersChanged.emit(list(nameFilters))
        super()._supportedFeaturesChanged(featureset, nameFilters)

    def scrollToCurrent(self):
        """
        Scrolls to the current item in the browser

        :return:
        """
        assertMainThread()
        c = self.browser.current()
        if c is not None:
            self.browser.scrollTo(c)

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
        self.preventSeek = True
        self.positionSlider.setRange(0, (end - begin)//1000000)
        self.preventSeek = False
        self.beginLabel.setText(self._timeToString(0))
        self.endLabel.setText(self._timeToString((end - begin)//1000000))
        self._currentTimestampChanged(begin)
        try:
            self.browser.blockSignals(True)
            self.browser.setActive(filename)
            self.browser.scrollTo(filename)
        finally:
            self.browser.blockSignals(False)
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
        super()._sequenceOpened(filename, begin, end, streams)

    @staticmethod
    def _splitTime(milliseconds):
        hours = milliseconds // (60 * 60 * 1000)
        milliseconds -= hours * (60 * 60 * 1000)
        minutes = milliseconds // (60 * 1000)
        milliseconds -= minutes * (60 * 1000)
        seconds = milliseconds // 1000
        milliseconds -= seconds * 1000
        return hours, minutes, seconds, milliseconds

    @staticmethod
    def _timeToString(milliseconds):
        return "%02d:%02d:%02d.%03d" % (MVCPlaybackControlGUI._splitTime(milliseconds))

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
            sliderVal = (currentTime - self.beginTime) // 1000000 # nanoseconds to milliseconds
            self.preventSeek = True
            self.positionSlider.setValue(sliderVal)
            self.preventSeek = False
            self.positionSlider.blockSignals(False)
            self.currentLabel.setEnabled(True)
            self.currentLabel.setText(self._timeToString(sliderVal))
        super()._currentTimestampChanged(currentTime)

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
            ts = self.beginTime + value * 1000000
            self.seekTime(ts)
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
            ts = self.beginTime // 1000000 + value
            self.currentLabel.setEnabled(False)
            self.currentLabel.setText(self._timeToString(ts))

    def _playbackStarted(self):
        """
        Notifies about starting playback

        :return: None
        """
        assertMainThread()
        self.actStart.setEnabled(False)
        if "pausePlayback" in self.featureset:
            self.actPause.setEnabled(True)
        super()._playbackStarted()

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
        super()._playbackPaused()

    def openRecent(self):
        """
        Called when the user clicks on a recent sequence.

        :return:
        """
        assertMainThread()
        action = self.sender()
        self.browser.setActive(action.data())

    def browserActivated(self, filename):
        """
        Called when the user activated a file.

        :param filename: the new filename
        :return:
        """
        assertMainThread()
        if filename is not None and Path(filename).is_file():
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
            self.recentSeqs[0].setText(self.compressFileName(filename))
            self.recentSeqs[0].setData(filename)
            self.recentSeqs[0].setVisible(True)
            self.setSequence(filename)

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
        super()._timeRatioChanged(newRatio)

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

    def _defineProperties(self):
        propertyCollection = self.config.guiState()
        propertyCollection.defineProperty("PlaybackControl_showAllFiles", 0, "show all files setting")
        propertyCollection.defineProperty("PlaybackControl_folder", "", "current folder name")
        propertyCollection.defineProperty("PlaybackControl_recent", "", "recent opened sequences")

    def saveState(self):
        """
        Saves the state of the playback control

        :return:
        """
        assertMainThread()
        self._defineProperties()
        propertyCollection = self.config.guiState()
        showAllFiles = self.actShowAllFiles.isChecked()
        folder = self.browser.folder()
        logger.debug("Storing current folder: %s", folder)
        try:
            propertyCollection.setProperty("PlaybackControl_showAllFiles", int(showAllFiles))
            propertyCollection.setProperty("PlaybackControl_folder", folder)
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
        self._defineProperties()
        propertyCollection = self.config.guiState()
        showAllFiles = propertyCollection.getProperty("PlaybackControl_showAllFiles")
        self.actShowAllFiles.setChecked(bool(showAllFiles))
        folder = propertyCollection.getProperty("PlaybackControl_folder")
        if Path(folder).is_dir():
            logger.debug("Setting current file: %s", folder)
            self.browser.setFolder(folder)
        recentFiles = propertyCollection.getProperty("PlaybackControl_recent")
        idx = 0
        for f in recentFiles.split("|"):
            if f != "" and Path(f).is_file():
                self.recentSeqs[idx].setData(f)
                self.recentSeqs[idx].setText(self.compressFileName(f))
                self.recentSeqs[idx].setVisible(True)
                self.recentSeqs[idx].setEnabled(False)
                idx += 1
                if idx >= len(self.recentSeqs):
                    break
        for a in self.recentSeqs[idx:]:
            a.setData(None)
            a.setText("")
            a.setVisible(False)

    @staticmethod
    def compressFileName(filename):
        """
        Compresses long path names with an ellipsis (...)

        :param filename: the original path name as a Path or string instance
        :return: the compressed path name as a string instance
        """
        p = Path(filename)
        parts = tuple(p.parts)
        if len(parts) >= 6:
            p = Path(*parts[:2]) / "..." /  Path(*parts[-2:])
        return str(p)
