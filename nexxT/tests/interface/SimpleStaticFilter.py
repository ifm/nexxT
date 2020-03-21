# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import logging
import time
from nexxT.interface import Filter, InputPort, InputPortInterface, OutputPort, DataSample
from PySide2.QtCore import QTimer, Slot

class SimpleStaticFilter(Filter):

    def __init__(self, environment):
        Filter.__init__(self, False, False, environment)
        self.inPort = InputPort(False, "inPort", environment)
        self.addStaticPort(self.inPort)
        self.outPort = OutputPort(False, "outPort", environment)
        self.addStaticPort(self.outPort)
        self.sleep_time = self.propertyCollection().defineProperty("sleep_time", 0.0,
                                                                "sleep time to simulate computational load [s]")

    def onPortDataChanged(self, inputPort):
        dataSample = inputPort.getData()
        self.afterReceive(dataSample)
        if dataSample.getDatatype() == "text/utf8":
            logging.getLogger(__name__).info("received: %s", dataSample.getContent().data().decode("utf8"))
        newSample = DataSample.copy(dataSample)
        time.sleep(self.sleep_time)
        self.beforeTransmit(dataSample)
        self.outPort.transmit(dataSample)
        self.afterTransmit()

    # used by tests
    def afterReceive(self, dataSample):
        pass

    def beforeTransmit(self, dataSample):
        pass

    def afterTransmit(self):
        pass

class SimpleSource(Filter):
    def __init__(self, environment):
        Filter.__init__(self, False, False, environment)
        self.outPort = OutputPort(False, "outPort", environment)
        self.addStaticPort(self.outPort)
        self.timeout_ms = int(1000 / self.propertyCollection().defineProperty("frequency", 1.0, "frequency of data generation [Hz]"))

    def onStart(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.newDataEvent)
        # prevent different behaviour between linux and windows (the timer will fire 10 times as fast as needed
        # and the events are filtered in newDataEvent)
        self.timer.start(self.timeout_ms/10)
        self.counter = 0
        self.lastSendTime = None

    def newDataEvent(self):
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

    def onStop(self):
        self.timer.stop()
        del self.timer

    def onPortDataChanged(self, inputPort):
        dataSample = inputPort.getData()
        newSample = DataSample.copy(dataSample)
        self.outPort.transmit(dataSample)

    # overwritten by tests
    def beforeTransmit(self, dataSample):
        pass

    def afterTransmit(self):
        pass


def test_create():
    class EnvironmentMockup(object):
        def addStaticPort(self, port):
            pass
    env = EnvironmentMockup()
    filter = SimpleStaticFilter(env)
    inData = DataSample(b'Hello', "bytes", 1)
    filter.onPortDataChanged(filter.inPort)

if __name__ == "__main__":
    test_create()