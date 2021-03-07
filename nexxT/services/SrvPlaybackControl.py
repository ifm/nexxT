# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the playback control console service for the nexxT framework.
"""

import pathlib
import logging
from PySide2.QtCore import QObject, Signal, Slot, Qt, QDir, QMutex, QMutexLocker
from nexxT.interface import FilterState
from nexxT.core.Exceptions import NexTRuntimeError
from nexxT.core.Application import Application
from nexxT.core.Utils import assertMainThread, MethodInvoker, handleException, mainThread

logger = logging.getLogger(__name__)

class PlaybackDeviceProxy(QObject):
    """
    This class acts as a proxy and is connected to exactly one playback device over QT signals slots for providing
    thread safety.
    """
    def __init__(self, playbackControl, playbackDevice, nameFilters):
        super().__init__()
        # private variables
        self._playbackControl = playbackControl
        self._nameFilters = nameFilters
        self._controlsFile = False # is set to True when setSequence is called with a matching file name
        self._featureSet = {}
        # this instance is called in the playbackDevice's thread, move it to the playbackControl thread (= main thread)
        self.moveToThread(playbackControl.thread())
        # setup mandatory connections from control to playback
        if not self._startPlayback.connect(playbackDevice.startPlayback):
            raise NexTRuntimeError("cannot connect to slot startPlayback()")
        if not self._pausePlayback.connect(playbackDevice.pausePlayback):
            raise NexTRuntimeError("cannot connect to slot pausePlayback()")
        # setup optional connections from control to playback
        self._featureSet = set(["startPlayback", "pausePlayback"])
        for feature in ["stepForward", "stepBackward", "seekTime", "seekBeginning", "seekEnd",
                        "setTimeFactor", "setSequence"]:
            signal = getattr(self, "_" + feature)
            slot = getattr(playbackDevice, feature, None)
            if slot is not None and signal.connect(slot):
                self._featureSet.add(feature)
        # setup optional connections from playback to control
        for feature in ["sequenceOpened", "currentTimestampChanged", "playbackStarted", "playbackPaused",
                        "timeRatioChanged"]:
            slot = getattr(self, "_" + feature)
            signal = getattr(playbackDevice, feature, None)
            if signal is not None and signal.connect(slot):
                self._featureSet.add(feature)

    def startPlayback(self):
        """
        Proxy function, checks whether this proxy has control and emits the signal if necessary
        """
        if self._controlsFile:
            self._startPlayback.emit()

    def pausePlayback(self):
        """
        Proxy function, checks whether this proxy has control and emits the signal if necessary
       """
        if self._controlsFile:
            self._pausePlayback.emit()

    def stepForward(self, stream):
        """
        Proxy function, checks whether this proxy has control and emits the signal if necessary
        """
        if self._controlsFile:
            self._stepForward.emit(stream)

    def stepBackward(self, stream):
        """
        Proxy function, checks whether this proxy has control and emits the signal if necessary
        """
        if self._controlsFile:
            self._stepBackward.emit(stream)

    def seekBeginning(self):
        """
        Proxy function, checks whether this proxy has control and emits the signal if necessary
        """
        if self._controlsFile:
            self._seekBeginning.emit()

    def seekEnd(self):
        """
        Proxy function, checks whether this proxy has control and emits the signal if necessary
        """
        if self._controlsFile:
            self._seekEnd.emit()

    def seekTime(self, timestamp_ns):
        """
        Proxy function, checks whether this proxy has control and emits the signal if necessary

        :param timestamp_ns: the timestamp in nanoseconds
        """
        if self._controlsFile:
            self._seekTime.emit(timestamp_ns)

    def setSequence(self, filename):
        """
        Proxy function, checks whether filename matches the filter's name filter list and takes control if necessary.

        :param filename: a string instance or None
        """
        if filename is not None and not QDir.match(self._nameFilters, pathlib.Path(filename).name):
            filename = None
        self._controlsFile = filename is not None
        self._setSequence.emit(filename)

    def setTimeFactor(self, factor):
        """
        Proxy function, checks whether this proxy has control and emits the signal if necessary

        :param factor: time factor as a float
        """
        if self._controlsFile:
            self._setTimeFactor.emit(factor)

    def hasControl(self):
        """
        Returns whether this proxy object has control over the player

        :return: true if this proxy object has control
        """
        return self._controlsFile

    def featureSet(self):
        """
        Returns the player device's feature set

        :return: a set of strings
        """
        return self._featureSet

    _startPlayback = Signal()
    _pausePlayback = Signal()
    _stepForward = Signal(str)
    _stepBackward = Signal(str)
    _seekBeginning = Signal()
    _seekEnd = Signal()
    _seekTime = Signal('qint64')
    _setSequence = Signal(object)
    _setTimeFactor = Signal(float)
    sequenceOpened = Signal(str, 'qint64', 'qint64', object)
    currentTimestampChanged = Signal('qint64')
    playbackStarted = Signal()
    playbackPaused = Signal()
    timeRatioChanged = Signal(float)

    def _sequenceOpened(self, filename, begin, end, streams):
        if self._controlsFile:
            self.sequenceOpened.emit(filename, begin, end, streams)

    def _currentTimestampChanged(self, currentTime):
        if self._controlsFile:
            self.currentTimestampChanged.emit(currentTime)

    def _playbackStarted(self):
        if self._controlsFile:
            self.playbackStarted.emit()

    def _playbackPaused(self):
        if self._controlsFile:
            self.playbackPaused.emit()

    def _timeRatioChanged(self, newRatio):
        if self._controlsFile:
            self.timeRatioChanged.emit(newRatio)


class MVCPlaybackControlBase(QObject):
    """
    Base class for interacting with playback controller, usually this is connected to a harddisk player. This class
    provides the functions setupConnections and removeConnections which can be called by filters to register and
    deregister themselfs as a playback device.
    """
    _startPlayback = Signal()
    _pausePlayback = Signal()
    _stepForward = Signal(str)
    _stepBackward = Signal(str)
    _seekBeginning = Signal()
    _seekEnd = Signal()
    _seekTime = Signal('qint64')
    _setSequence = Signal(object)
    _setTimeFactor = Signal(float)

    def __init__(self):
        super().__init__()
        self._deviceId = 0
        self._registeredDevices = {}
        self._mutex = QMutex()
        self._setSequence.connect(self._stopSetSequenceStart)

    @Slot(QObject, "QStringList")
    def setupConnections(self, playbackDevice, nameFilters):
        """
        Sets up signal/slot connections between this view/controller instance and the given playbackDevice. This
        function is thread safe and shall be called by a direct QT connection.
        It is intended, that this function is called in the onOpen(...) method of a filter. It expects playbackDevice
        to provide the following slots:

        - startPlayback() (starts generating DataSamples)
        - pausePlayback() (pause mode, stop generating DataSamples)
        - stepForward(QString stream) (optional; in case given, a single step operation shall be performed.
            if stream is not None, the playback shall stop when receiving the next data sample
            of stream; otherwise the playback shall proceed to the next data sample of any stream)
        - stepBackward(QString stream) (optional; see stepForward)
        - seekBeginning(QString stream) (optional; goes to the beginning of the sequence)
        - seekEnd() (optional; goes to the end of the stream)
        - seekTime(qint64) (optional; goes to the specified time stamp)
        - setSequence(QString) (optional; opens the given sequence)
        - setTimeFactor(float) (optional; sets the playback time factor, factor > 0)

        It expects playbackDevice to provide the following signals (all signals are optional):

        - sequenceOpened(QString filename, qint64 begin, qint64 end, QStringList streams)
        - currentTimestampChanged(qint64 currentTime)
        - playbackStarted()
        - playbackPaused()
        - timeRatioChanged(float)

        :param playbackDevice: a QObject providing the aforementioned signals and slots
        :param nameFilters: a QStringList providing information about suported fileextensions (e.g. ["*.avi", "*.mp4"])
        :return:
        """
        with QMutexLocker(self._mutex):
            for devid in self._registeredDevices:
                if self._registeredDevices[devid]["object"] is playbackDevice:
                    raise NexTRuntimeError("Trying to register a playbackDevice object twice.")

            proxy = PlaybackDeviceProxy(self, playbackDevice, nameFilters)
            featureset = proxy.featureSet()

            for feature in ["stepForward", "stepBackward", "seekTime", "seekBeginning", "seekEnd",
                            "setTimeFactor", "startPlayback", "pausePlayback"]:
                signal = getattr(self, "_" + feature)
                slot = getattr(proxy, feature, None)
                if slot is not None:
                    signal.connect(slot)

            for feature in ["sequenceOpened", "currentTimestampChanged", "playbackStarted", "playbackPaused",
                            "timeRatioChanged"]:
                slot = getattr(self, "_" + feature)
                signal = getattr(proxy, feature, None)
                if signal is not None:
                    signal.connect(slot, Qt.UniqueConnection)

            self._registeredDevices[self._deviceId] = dict(object=playbackDevice,
                                                           featureset=featureset,
                                                           nameFilters=nameFilters,
                                                           proxy=proxy)
            self._deviceId += 1
            MethodInvoker(dict(object=self, method="_updateFeatureSet", thread=mainThread()), Qt.QueuedConnection)

    @Slot(QObject)
    def removeConnections(self, playbackDevice):
        """
        unregisters the given playbackDevice and disconnects all. It is intended that this function is called in the
        onClose(...) method of a filter.

        :param playbackDevice: the playback device to be unregistered.
        :return: None
        """
        with QMutexLocker(self._mutex):
            found = []
            for devid in self._registeredDevices:
                if self._registeredDevices[devid]["object"] is playbackDevice:
                    found.append(devid)
            if len(found) > 0:
                for devid in found:
                    del self._registeredDevices[devid]
                logger.debug("disconnected connections of playback device. number of devices left: %d",
                             len(self._registeredDevices))
                MethodInvoker(dict(object=self, method="_updateFeatureSet", thread=mainThread()), Qt.QueuedConnection)

    @handleException
    def _stopSetSequenceStart(self, filename):
        assertMainThread()
        if Application.activeApplication is None:
            logger.warning("playbackControl.setSequence is called without an active application.")
            return
        state = Application.activeApplication.getState()
        if state not in [FilterState.ACTIVE, FilterState.OPENED]:
            logger.warning("playbackControl.setSequence is called with unexpected application state %s",
                           FilterState.state2str(state))
            return
        if state == FilterState.ACTIVE:
            Application.activeApplication.stop()
        assert Application.activeApplication.getState() == FilterState.OPENED
        for _, spec in self._registeredDevices.items():
            spec["proxy"].setSequence(filename)
            # only one filter will get the playback control
            if spec["proxy"].hasControl():
                filename = None
                logger.debug("found playback device with explicit control")
        if filename is not None:
            logger.warning("did not find a playback device taking control")
        Application.activeApplication.start()
        assert Application.activeApplication.getState() == FilterState.ACTIVE

    def _updateFeatureSet(self):
        assertMainThread()
        featureset = set()
        nameFilters = set()
        for devid in self._registeredDevices:
            featureset = featureset.union(self._registeredDevices[devid]["featureset"])
            nameFilters = nameFilters.union(self._registeredDevices[devid]["nameFilters"])
        self._supportedFeaturesChanged(featureset, nameFilters)

    def _supportedFeaturesChanged(self, featureset, nameFilters):
        """
        Can be overriden to get the supported features of the connected playbackDevice(s). This function is called
        from multiple threads, but not at the same time.

        :param featureset set of supported features
        :param nameFilters set of supported nameFilters
        :return:
        """

    def _sequenceOpened(self, filename, begin, end, streams):
        """
        Notifies about an opened sequence.

        :param filename: the filename which has been opened
        :param begin: timestamp of sequence's first sample
        :param end: timestamp of sequence's last sample
        :param streams: list of streams in the sequence
        :return: None
        """

    def _currentTimestampChanged(self, currentTime):
        """
        Notifies about a changed timestamp

        :param currentTime: the new current timestamp
        :return: None
        """

    def _playbackStarted(self):
        """
        Notifies about starting playback

        :return: None
        """

    def _playbackPaused(self):
        """
        Notifies about pause playback

        :return: None
        """

    def _timeRatioChanged(self, newRatio):
        """
        Notifies about a changed playback time ratio,

        :param newRatio the new playback ratio as a float
        :return: None
        """

class PlaybackControlConsole(MVCPlaybackControlBase):
    """
    Console service for playback control. Basically inverts the signals and slots and provides an API for scripting.
    The GUI service inherits from this class, so that the GUI can also be scripted in the same way.
    """
    supportedFeaturesChanged = Signal(object, object)
    sequenceOpened = Signal(str, 'qint64', 'qint64', object)
    currentTimestampChanged = Signal('qint64')
    playbackStarted = Signal()
    playbackPaused = Signal()
    timeRatioChanged = Signal(float)

    def __init__(self, config): # pylint: disable=unused-argument
        super().__init__()
        self._playing = False
        self._appConn = None

    def startPlayback(self):
        """
        Start playback

        :return:
        """
        self._startPlayback.emit()

    def pausePlayback(self):
        """
        Pause playback

        :return:
        """
        self._pausePlayback.emit()

    def stepForward(self, stream):
        """
        Step one frame forward in the given stream (might be None).

        :param stream: a string containing the selected stream.
        :return:
        """
        self._stepForward.emit(stream)

    def stepBackward(self, stream):
        """
        Step one frame backward in the given stream (might be None)

        :param stream: a string containing the selected stream.
        :return:
        """
        self._stepBackward.emit(stream)

    def seekBeginning(self):
        """
        Seek to the beginning of the file.

        :return:
        """
        self._seekBeginning.emit()

    def seekEnd(self):
        """
        Seek to the end of the file.

        :return:
        """
        self._seekEnd.emit()

    def seekTime(self, timestamp_ns):
        """
        Seek to the specified time

        :param timestamp_ns: the timestamp in nanoseconds
        :return:
        """
        self._seekTime.emit(timestamp_ns)

    def setSequence(self, file):
        """
        Set the sequence to be played.

        :param file: a string containing a filename
        :return:
        """
        self._setSequence.emit(file)

    def setTimeFactor(self, factor):
        """
        Set the time factor to be used.

        :param factor: a float containing the factor.
        :return:
        """
        self._setTimeFactor.emit(factor)

    def _supportedFeaturesChanged(self, featureset, nameFilters):
        """
        Can be overriden to get the supported features of the connected playbackDevice(s). This function is called
        from multiple threads, but not at the same time.

        :param featureset set of supported features
        :param nameFilters set of supported nameFilters
        :return:
        """
        self.supportedFeaturesChanged.emit(featureset, nameFilters)

    def _sequenceOpened(self, filename, begin, end, streams):
        """
        Notifies about an opened sequence.

        :param filename: the filename which has been opened
        :param begin: timestamp of sequence's first sample
        :param end: timestamp of sequence's last sample
        :param streams: list of streams in the sequence
        :return: None
        """
        self.sequenceOpened.emit(filename, begin, end, streams)

    def _currentTimestampChanged(self, currentTime):
        """
        Notifies about a changed timestamp

        :param currentTime: the new current timestamp
        :return: None
        """
        self.currentTimestampChanged.emit(currentTime)

    def _playbackStarted(self):
        """
        Notifies about starting playback

        :return: None
        """
        self._playing = True
        self.playbackStarted.emit()

    def _playbackPaused(self):
        """
        Notifies about pause playback

        :return: None
        """
        self._playing = False
        self.playbackPaused.emit()

    def _timeRatioChanged(self, newRatio):
        """
        Notifies about a changed playback time ratio,

        :param newRatio the new playback ratio as a float
        :return: None
        """
        self.timeRatioChanged.emit(newRatio)
