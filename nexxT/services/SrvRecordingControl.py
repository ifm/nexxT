# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the recording control console service for the nexxT framework.
"""

import logging
from PySide2.QtCore import QObject, Signal, Slot, Qt, QMutex, QMutexLocker
from nexxT.core.Application import Application
from nexxT.core.Exceptions import NexTRuntimeError
from nexxT.interface import FilterState

logger = logging.getLogger(__name__)

class MVCRecordingControlBase(QObject):
    """
    Base class for interacting with playback controller, usually this is connected to a
    harddisk player.
    """
    _startRecording = Signal(str)
    _stopRecording = Signal()
    statusUpdate = Signal(QObject, str, float, "qlonglong")
    notifyError = Signal(QObject, str)

    def __init__(self, config): # pylint: disable=unused-argument
        super().__init__()
        self._deviceId = 0
        self._registeredDevices = {}
        self._mutex = QMutex()
        self._recordingActive = False
        self._appConn = None

    @Slot(QObject)
    def setupConnections(self, recordingDevice):
        """
        Sets up signal/slot connections between this view/controller instance and the given playbackDevice. This
        function is thread safe and shall be called by a direct QT connection.
        It is intended, that this function is called in the onStart(...) method of a filter. It expects recordingDevice
        to provide the following slots:

        - startRecording(str directory) (starts recording DataSamples)
        - stopRecording() (stop the recording)

        It expects recordingDevice to provide the following signals (all signals are optional):

        - statusUpdate(str file, float lengthInSeconds, int bytesWritten)
        - notifyError(str errorDescription)

        :param recordingDevice: a QObject providing the aforementioned signals and slots
        :return:
        """
        with QMutexLocker(self._mutex):
            for devid in self._registeredDevices:
                if self._registeredDevices[devid]["object"] is recordingDevice:
                    raise NexTRuntimeError("Trying to register a playbackDevice object twice.")

            if not self._startRecording.connect(recordingDevice.startRecording):
                raise NexTRuntimeError("cannot connect to slot startPlayback()")
            if not self._stopRecording.connect(recordingDevice.stopRecording):
                raise NexTRuntimeError("cannot connect to slot pausePlayback()")

            connections = [(self._startRecording, recordingDevice.startRecording),
                           (self._stopRecording, recordingDevice.stopRecording)]

            featureset = set()

            for feature in ["statusUpdate", "notifyError"]:
                slot = getattr(self, "_" + feature)
                signal = getattr(recordingDevice, feature, None)
                if signal is not None and signal.connect(slot, Qt.UniqueConnection):
                    featureset.add(feature)
                    connections.append((signal, slot))

            self._registeredDevices[self._deviceId] = dict(object=recordingDevice,
                                                           featureset=featureset,
                                                           connections=connections)
            logger.debug("connected recording device. Current number of devices: %d",
                         len(self._registeredDevices))
            self._deviceId += 1
            self._updateFeatureSet()

    @Slot(QObject)
    def removeConnections(self, recordingDevice):
        """
        unregisters the given recordingDevice and disconnects all. It is intended that this function is called in the
        onStop(...) method of a filter.

        :param recordingDevice: the recording device to be unregistered.
        :return: None
        """
        with QMutexLocker(self._mutex):
            found = []
            for devid in self._registeredDevices:
                if self._registeredDevices[devid]["object"] is recordingDevice:
                    found.append(devid)
            if len(found) > 0:
                for devid in found:
                    for signal, slot in self._registeredDevices[devid]["connections"]:
                        signal.disconnect(slot)
                    del self._registeredDevices[devid]
                logger.debug("disconnected connections of recording device. number of devices left: %d",
                             len(self._registeredDevices))
                self._updateFeatureSet()

    def _updateFeatureSet(self):
        featureset = set()
        featureCount = {}
        for devid in self._registeredDevices:
            for f in self._registeredDevices[devid]["featureset"]:
                if not f in featureCount:
                    featureCount[f] = 0
                featureCount[f] += 1
            featureset = featureset.union(self._registeredDevices[devid]["featureset"])
        self._supportedFeaturesChanged(featureset)

    def _supportedFeaturesChanged(self, featureset):
        """
        Can be overriden to get the supported features of the connected playbackDevice(s). This function is called
        from multiple threads, but not at the same time.

        :param featureset set of supported features
        :param nameFilters set of supported nameFilters
        :return:
        """

    def _statusUpdate(self, file=None, lengthInSeconds=None, bytesWritten=None):
        """
        Emits the statusUpdate signal

        :param file: the currently active recording file
        :param lengthInSeconds: the length of this file in seconds
        :return:
        """
        self.statusUpdate.emit(self.sender(), file, lengthInSeconds, bytesWritten)

    def _notifyError(self, errorDescription):
        """
        Emits the notifyError signal and stops the recording

        :param errorDescription: a string with a description of the error
        :return:
        """
        self.stopRecording()
        self.notifyError.emit(self.sender(), errorDescription)

    def startRecording(self, directory):
        """
        Starts the recording in the given directory

        :param directory: The directory where to store the recordings
        :return:
        """
        self._recordingActive = True
        Application.activeApplication.stateChanged.connect(self.stateChanged)
        self._startRecording.emit(directory)

    def stateChanged(self, state):
        """
        Stops the recording when application is stopped.

        :param state: the new filter state
        :return:
        """
        if self._recordingActive and state == FilterState.OPENED:
            self.stopRecording()

    def stopRecording(self):
        """
        Stops the recording.

        :return:
        """
        self._recordingActive = False
        Application.activeApplication.stateChanged.disconnect(self.stateChanged)
        self._stopRecording.emit()
