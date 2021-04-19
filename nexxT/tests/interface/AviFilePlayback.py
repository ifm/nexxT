# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import logging
import time
from PySide2.QtCore import Signal, Slot, QTimer, QUrl
from PySide2.QtMultimedia import QMediaPlayer, QMediaPlaylist, QAbstractVideoSurface, QVideoFrame
from PySide2.QtMultimediaWidgets import QVideoWidget
from nexxT.interface import Filter, OutputPort, DataSample, Services

logger = logging.getLogger(__name__)

class DummyVideoSurface(QAbstractVideoSurface):
    def __init__(self, parent=None):
        super().__init__(parent)

    def supportedPixelFormats(self, handleType):
        return [QVideoFrame.Format_ARGB32, QVideoFrame.Format_ARGB32_Premultiplied,
                QVideoFrame.Format_RGB32, QVideoFrame.Format_RGB24, QVideoFrame.Format_RGB565,
                QVideoFrame.Format_RGB555, QVideoFrame.Format_ARGB8565_Premultiplied,
                QVideoFrame.Format_BGRA32, QVideoFrame.Format_BGRA32_Premultiplied, QVideoFrame.Format_BGR32,
                QVideoFrame.Format_BGR24, QVideoFrame.Format_BGR565, QVideoFrame.Format_BGR555,
                QVideoFrame.Format_BGRA5658_Premultiplied, QVideoFrame.Format_AYUV444,
                QVideoFrame.Format_AYUV444_Premultiplied, QVideoFrame.Format_YUV444,
                QVideoFrame.Format_YUV420P, QVideoFrame.Format_YV12, QVideoFrame.Format_UYVY,
                QVideoFrame.Format_YUYV, QVideoFrame.Format_NV12, QVideoFrame.Format_NV21,
                QVideoFrame.Format_IMC1, QVideoFrame.Format_IMC2, QVideoFrame.Format_IMC3,
                QVideoFrame.Format_IMC4, QVideoFrame.Format_Y8, QVideoFrame.Format_Y16,
                QVideoFrame.Format_Jpeg, QVideoFrame.Format_CameraRaw, QVideoFrame.Format_AdobeDng]

    def isFormatSupported(self, format):
        imageFormat = QVideoFrame.imageFormatFromPixelFormat(format.pixelFormat())
        size = format.frameSize()
        return True
        return imageFormat != QImage.Format_Invalid and not size.isEmpty() and \
               format.handleType() == QAbstractVideoBuffer.NoHandle

    def present(self, frame):
        logger.debug("video frame arrived")

    def start(self):
        logger.debug("start")
        super().start()

    def stop(self):
        logger.debug("stop")
        super().stop()


class VideoPlaybackDevice(Filter):
    playbackStarted = Signal()
    playbackPaused = Signal()
    sequenceOpened = Signal(str, qint64, qint64, list)
    currentTimestampChanged = Signal(qint64)

    def __init__(self, environment):
        super().__init__(False, False, environment)
        self.video_out = OutputPort(False, "video", environment)
        self.audio_out = OutputPort(False, "audio", environment)
        self.addStaticPort(self.video_out)
        self.addStaticPort(self.audio_out)
        self.filename = self.propertyCollection().defineProperty("filename", "", "avi file name")

    def newDuration(self, newDuration):
        logger.debug("newDuration %s", newDuration)
        self.sequenceOpened.emit(self.filename,
                                 0,
                                 newDuration * 1000000,
                                 ["video"])

    def currentMediaChanged(self, media):
        logger.debug("currentMediaChanged videoAv=%s audioAv=%s", self.player.isVideoAvailable(), self.player.isAudioAvailable())


    def _openVideo(self):
        logger.debug("entering _openVideo")
        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.videoOutput = DummyVideoSurface(self.player)
        #self.videoOutput = QVideoWidget()
        #self.videoOutput.show()
        self.player.setVideoOutput(self.videoOutput)
        #self.player.setMuted(True)
        self.player.durationChanged.connect(self.newDuration)
        self.player.currentMediaChanged.connect(self.currentMediaChanged)
        self.player.setMedia(QUrl.fromLocalFile(self.filename))
        logger.debug("leaving _openVideo; videoAv=%s audioAv=%s", self.player.isVideoAvailable(), self.player.isAudioAvailable())

    def _closeVideo(self):
        try:
            del self.player
            del self.playlist
        except:
            pass

    def onStart(self):
        ctrlSrv = Services.getService("PlaybackControl")
        ctrlSrv.setupConnections(self)
        self.playbackPaused.emit()
        if self.filename != "":
            self._openVideo()

    def onStop(self):
        ctrlSrv = Services.getService("PlaybackControl")
        ctrlSrv.removeConnections(self)
        self._closeVideo()

    @Slot()
    def startPlayback(self):
        self.player.play()
        self.playbackStarted.emit()
        logger.debug("leaving startPlayback; videoAv=%s audioAv=%s", self.player.isVideoAvailable(), self.player.isAudioAvailable())

    @Slot()
    def pausePlayback(self):
        self.player.pause()
        self.playbackPaused.emit()

    def newDataEvent(self):
        t = time.monotonic()
        if self.lastSendTime is not None:
            if t - self.lastSendTime < self.timeout_ms * 1e-3:
                # we are still earlier than the requested framerate
                return
        self.lastSendTime = t
        self.counter += 1
        c = "Sample %d" % self.counter
        s = DataSample(c.encode("utf8"), "text/utf8", int(time.time() / DataSample.TIMESTAMP_RES))
        logging.getLogger(__name__).info("transmit: %s", c)
        self.beforeTransmit(s)
        self.outPort.transmit(s)
        self.afterTransmit()

    def stepForward(self):
        pass

    def stepBackward(self):
        pass

    def seekBeginning(self):
        pass

    def seekEnd(self):
        pass

    def seekTime(self, timestamp):
        pass

    def setSequence(self, filename):
        self.filename

    def setTimeFactor(self, factor):
        pass
