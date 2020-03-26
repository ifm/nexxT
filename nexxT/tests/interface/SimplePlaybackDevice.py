# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import logging
import time
from PySide2.QtCore import Signal, Slot, QTimer, QThread
from nexxT.interface import Filter, OutputPort, DataSample, Services

import sys, os
sys.path.append(os.path.abspath(__file__ + "/.."))
import test_dataSample
import PySide2.Qt3DRender

logger = logging.getLogger(__name__)

class MinimalPlaybackDevice(Filter):
    playbackStarted = Signal()
    playbackPaused = Signal()

    def __init__(self, environment):
        super().__init__(False, False, environment)
        self.outPort = OutputPort(False, "outPort", environment)
        self.addStaticPort(self.outPort)
        self.timeout_ms = int(
            1000 / self.propertyCollection().defineProperty("frequency", 1.0, "frequency of data generation [Hz]"))
        self.timer = QTimer()
        self.timer.timeout.connect(self.newDataEvent)
        self.thread = QThread.currentThread()

    def onStart(self):
        assert QThread.currentThread() is self.thread
        ctrlSrv = Services.getService("PlaybackControl")
        ctrlSrv.setupConnections(self, [])
        self.playbackPaused.emit()

    def onStop(self):
        assert QThread.currentThread() is self.thread
        ctrlSrv = Services.getService("PlaybackControl")
        ctrlSrv.removeConnections(self)

    @Slot()
    def startPlayback(self):
        assert QThread.currentThread() is self.thread
        # prevent different behaviour between linux and windows (the timer will fire 10 times as fast as needed
        # and the events are filtered in newDataEvent)
        self.timer.start(self.timeout_ms/10)
        self.counter = 0
        self.lastSendTime = None
        self.playbackStarted.emit()

    @Slot()
    def pausePlayback(self):
        assert QThread.currentThread() is self.thread
        self.timer.stop()
        self.playbackPaused.emit()

    def newDataEvent(self):
        assert QThread.currentThread() is self.thread
        t = time.monotonic()
        if self.lastSendTime is not None:
            if t - self.lastSendTime < self.timeout_ms*1e-3:
                # we are still earlier than the requested framerate
                return
        self.lastSendTime = t
        self.counter += 1
        c = "Sample %d" % self.counter
        s = DataSample(c.encode("utf8"), "text/utf8", int(time.time()/DataSample.TIMESTAMP_RES))
        logging.getLogger(__name__).info("transmit: %s", c)
        self.beforeTransmit(s)
        self.outPort.transmit(s)
        self.afterTransmit()

    # overwritten by tests
    def beforeTransmit(self, dataSample):
        pass

    def afterTransmit(self):
        pass

