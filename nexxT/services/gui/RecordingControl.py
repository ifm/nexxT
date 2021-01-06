# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the recording control GUI service for the nexxT framework.
"""

import logging
from pathlib import Path
from PySide2.QtCore import Qt, QStorageInfo
from PySide2.QtGui import QIcon, QTextOption
from PySide2.QtWidgets import QAction, QApplication, QStyle, QWidget, QBoxLayout, QToolBar, QFileDialog
from nexxT.core.Utils import assertMainThread, ElidedLabel
from nexxT.core.Exceptions import PropertyCollectionPropertyNotFound
from nexxT.interface import Services
from nexxT.services.SrvRecordingControl import MVCRecordingControlBase

logger = logging.getLogger(__name__)

class MVCRecordingControlGUI(MVCRecordingControlBase):
    """
    This service implements a GUI frontend for the recording service
    """

    def __init__(self, config):
        assertMainThread()
        super().__init__(config)

        # state
        self._directory = str(Path('.').absolute())

        # gui
        srv = Services.getService("MainWindow")
        config.configLoaded.connect(self._restoreState)
        config.configAboutToSave.connect(self._saveState)
        self._config = config
        recMenu = srv.menuBar().addMenu("&Recording")
        style = QApplication.style()
        self.actStart = QAction(QIcon.fromTheme("media-record", QIcon(":icons/media-record.svg")),
                                "Start Recording", self)
        self.actStop = QAction(QIcon.fromTheme("media-playback-stop", style.standardIcon(QStyle.SP_MediaStop)),
                               "Stop Recording", self)
        self.actSetDir = QAction(QIcon.fromTheme("document-open-folder", style.standardIcon(QStyle.SP_DirIcon)),
                                 "Choose directory ...", self)
        self.actStart.setEnabled(False)
        self.actStop.setEnabled(False)
        self.actSetDir.setEnabled(False)

        self.actStart.triggered.connect(self._startTriggered)
        self.actStop.triggered.connect(self._stopTriggered)
        self.actSetDir.triggered.connect(self._setDir)

        recMenu.addAction(self.actStart)
        recMenu.addAction(self.actStop)
        recMenu.addAction(self.actSetDir)

        self.dockWidget = srv.newDockWidget("RecordingControl", None, Qt.LeftDockWidgetArea,
                                            defaultLoc="PlaybackControl")
        self.dockWidgetContents = QWidget(self.dockWidget)
        self.dockWidget.setWidget(self.dockWidgetContents)
        toolLayout = QBoxLayout(QBoxLayout.TopToBottom, self.dockWidgetContents)
        toolLayout.setContentsMargins(0, 0, 0, 0)
        toolBar = QToolBar()
        toolLayout.addWidget(toolBar)
        toolBar.addAction(self.actStart)
        toolBar.addAction(self.actStop)
        toolBar.addAction(self.actSetDir)

        self._directoryLabel = ElidedLabel(self._directory, parent=self.dockWidgetContents)
        to = self._directoryLabel.textOption()
        to.setWrapMode(QTextOption.NoWrap)
        self._directoryLabel.setTextOption(to)
        self._directoryLabel.setElideMode(Qt.ElideMiddle)

        self._statusLabel = ElidedLabel("(disabled)", parent=self.dockWidgetContents)
        to = self._statusLabel.textOption()
        to.setWrapMode(QTextOption.NoWrap)
        self._statusLabel.setTextOption(to)
        self._statusLabel.setElideMode(Qt.ElideMiddle)

        toolLayout.addWidget(self._directoryLabel)
        toolLayout.addWidget(self._statusLabel, stretch=100)
        #toolLayout.addStretch(100)

        self.statusUpdate.connect(self._onUpdateStatus)
        self.notifyError.connect(self._onNotifyError)

    def _startTriggered(self):
        self.startRecording(self._directory)
        self.actStart.setEnabled(False)
        self.actStop.setEnabled(True)

    def _stopTriggered(self):
        self.stopRecording()
        self.actStart.setEnabled(True)
        self.actStop.setEnabled(False)

    def _setDir(self):
        tdir = QFileDialog.getExistingDirectory(parent=self.dockWidget,
                                                caption="Select recording target directory",
                                                dir=self._directory)
        if tdir != "" and tdir is not None:
            self._directory = str(Path(tdir).absolute())
            self._directoryLabel.setText(self._directory)

    def _supportedFeaturesChanged(self, featureset):
        if len(featureset) > 0 and not self.actSetDir.isEnabled():
            self.actStart.setEnabled(True)
            self.actStop.setEnabled(False)
            self.actSetDir.setEnabled(True)
            self._statusLabel.setText("inactive")
        elif len(featureset) == 0 and self.actSetDir.isEnabled():
            self.actStart.setEnabled(False)
            self.actStop.setEnabled(False)
            self.actSetDir.setEnabled(False)
            self._statusLabel.setText("(disabled)")

    def _onUpdateStatus(self, _, file, length, bytesWritten):
        lines = self._statusLabel.text().split("\n")
        if length < 0:
            length = None
        if bytesWritten < 0:
            bytesWritten = None
        updated = False

        if bytesWritten is None:
            bw = "??"
        elif bytesWritten < 1024:
            bw = "%3d bytes" % bytesWritten
        elif bytesWritten < 1024*1024:
            bw = "%.1f kb" % (bytesWritten/1024)
        elif bytesWritten < 1024*1024*1024:
            bw = "%.1f Mb" % (bytesWritten/1024/1024)
        else:
            bw = "%.1f Gb" % (bytesWritten/1024/1024/1024)

        if length is None:
            sl = "?? s"
        elif length < 60:
            sl = "%.1f sec" % length
        else:
            sl = "%.1f min" % (length//60)

        bytesAv = QStorageInfo(file).bytesAvailable()
        if length is not None and bytesWritten is not None and bytesAv >= 0 and bytesWritten > 0:
            timeAv = length*bytesAv/bytesWritten - length
            if timeAv < 60:
                av = "%.1f sec" % timeAv
            elif timeAv < 3600:
                av = "%.1f min" % (timeAv // 60)
            else:
                av = "> 1 hour"
        else:
            av = "?? s"

        if length is not None or bytesWritten is not None:
            newl = Path(file).name + ": " + sl + " | " + bw + " R: " + av
        else:
            newl = None

        if newl is not None:
            for i, l in enumerate(lines):
                if l.startswith(Path(file).name + ":"):
                    updated = True
                    lines[i] = newl
                    break
            if not updated:
                lines.append(newl)
            if lines[0] == "inactive":
                lines = lines[1:]
        else:
            toDel = None
            for i, l in enumerate(lines):
                if l.startswith(Path(file).name + ":"):
                    toDel = i
                    break
            if toDel is not None:
                lines = lines[:toDel] + lines[toDel+1:]
        if len(lines) == 0:
            lines.append("inactive")

        self._statusLabel.setText("\n".join(lines))

    def _onNotifyError(self, originFilter, errorDesc):
        lines = self._statusLabel.text().split("\n")
        newl = originFilter.objectName() + ": " + "ERROR: " + errorDesc
        updated = False
        for i, l in enumerate(lines):
            if l.startswith(originFilter.objectName() + ":"):
                updated = True
                lines[i] = newl
                break
        if not updated:
            lines.append(newl)
        if lines[0] == "inactive":
            lines = lines[1:]
        self._statusLabel.setText("\n".join(lines))

    def _defineProperties(self):
        propertyCollection = self._config.guiState()
        propertyCollection.defineProperty("RecordingControl_directory",
                                          str(Path('.').absolute()),
                                          "Target directory for recordings")


    def _saveState(self):
        """
        Saves the state of the playback control

        :return:
        """
        assertMainThread()
        self._defineProperties()
        propertyCollection = self._config.guiState()
        try:
            propertyCollection.setProperty("RecordingControl_directory", self._directory)
        except PropertyCollectionPropertyNotFound:
            pass

    def _restoreState(self):
        """
        Restores the state of the playback control from the given property collection

        :return:
        """
        assertMainThread()
        self._defineProperties()
        propertyCollection = self._config.guiState()
        logger.debug("before restore dir=%s", self._directory)
        d = propertyCollection.getProperty("RecordingControl_directory")
        if Path(d).exists():
            self._directory = d
        self._directoryLabel.setText(self._directory)
        logger.debug("after restore dir=%s", self._directory)
