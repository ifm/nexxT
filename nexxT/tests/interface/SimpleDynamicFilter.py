# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import logging
import time
from nexxT.interface import Filter, InputPort, OutputPort, DataSample

class SimpleDynInFilter(Filter):

    def __init__(self, environment):
        super().__init__(True, False, environment)
        self.outPort = OutputPort(False, "outPort", environment)
        self.addStaticPort(self.outPort)
        self.dynInPorts = None
        pc = self.propertyCollection()
        self.sleep_time = pc.defineProperty("sleep_time", 0.0,
                                            "sleep time to simulate computational load [s]")
        pc.defineProperty("ignore_ports", "",
                          "comma-seperated list of input port names which should not be copied to output.")
        pc.defineProperty("prefix", "", "prefix for log messages")

    def onInit(self):
        self.dynInPorts = self.getDynamicInputPorts()
        assert len(self.getDynamicOutputPorts()) == 0

    def onPortDataChanged(self, inputPort):
        dataSample = inputPort.getData()
        self.afterReceive(dataSample)
        pc = self.propertyCollection()
        if dataSample.getDatatype() == "text/utf8":
            logging.getLogger(__name__).info("%sreceived: %s on port %s",
                                             pc.getProperty("prefix"),
                                             dataSample.getContent().data().decode("utf8"),
                                             inputPort.name())
        ignore_ports = [pname for pname in self.propertyCollection().getProperty("ignore_ports").split(",") if pname != ""]
        if inputPort.name() not in ignore_ports:
            newSample = DataSample.copy(dataSample)
            time.sleep(self.sleep_time)
            self.beforeTransmit(dataSample)
            self.outPort.transmit(dataSample)
            self.afterTransmit()

    def onDeinit(self):
        self.dynInPorts = None

    # used by tests
    def afterReceive(self, dataSample):
        pass

    def beforeTransmit(self, dataSample):
        pass

    def afterTransmit(self):
        pass


class SimpleDynOutFilter(Filter):

    def __init__(self, environment):
        super().__init__(False, True, environment)
        self.inPort = InputPort(False, "inPort", environment)
        self.addStaticPort(self.inPort)
        self.outPort = OutputPort(False, "outPort", environment)
        self.addStaticPort(self.outPort)
        self.dynOutPorts = None

    def onInit(self):
        self.dynOutPorts = self.getDynamicInputPorts()
        assert len(self.getDynamicInputPorts()) == 0

    def onPortDataChanged(self, inputPort):
        dataSample = inputPort.getData()
        newSample = DataSample.copy(dataSample)
        for p in self.dynOutPorts + [self.outPort]:
            p.transmit(dataSample)

