# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from nexxT.interface import Filter, InputPort

class TestExceptionFilter(Filter):
    def __init__(self, env):
        super().__init__(False, False, env)
        self.propertyCollection().defineProperty("whereToThrow", "nowhere",
                                                 "one of nowhere,constructor,init,open,start,port,stop,close,deinit")
        if self.propertyCollection().getProperty("whereToThrow") == "constructor":
            raise RuntimeError("exception in constructor")
        self.port = InputPort(False, "port", env)
        self.addStaticPort(self.port)

    def onInit(self):
        if self.propertyCollection().getProperty("whereToThrow") == "init":
            raise RuntimeError("exception in init")

    def onOpen(self):
        if self.propertyCollection().getProperty("whereToThrow") == "open":
            raise RuntimeError("exception in open")

    def onStart(self):
        if self.propertyCollection().getProperty("whereToThrow") == "start":
            raise RuntimeError("exception in start")

    def onStop(self):
        if self.propertyCollection().getProperty("whereToThrow") == "stop":
            raise RuntimeError("exception in stop")

    def onClose(self):
        if self.propertyCollection().getProperty("whereToThrow") == "close":
            raise RuntimeError("exception in close")

    def onDeinit(self):
        if self.propertyCollection().getProperty("whereToThrow") == "deinit":
            raise RuntimeError("exception in deinit")

    def onPortDataChanged(self, port):
        if self.propertyCollection().getProperty("whereToThrow") == "port":
            raise RuntimeError("exception in port")
