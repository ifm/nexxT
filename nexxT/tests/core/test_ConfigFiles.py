# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import json
import logging
from pathlib import Path
import pytest
from PySide2.QtCore import QCoreApplication, QTimer
from nexxT.interface import FilterState, Services
from nexxT.core.ConfigFiles import ConfigFileLoader
from nexxT.core.Application import Application
from nexxT.core.Configuration import Configuration
import nexxT

def expect_exception(f, *args, **kw):
    ok = False
    try:
        f(*args, **kw)
    except:
        ok = True
    assert ok

def setup():
    global app
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication()

def simple_setup(activeTime_s):
    t = QTimer()
    t.setSingleShot(True)
    # timeout if test case hangs
    t2 = QTimer()
    t2.start((activeTime_s + 3)*1000)
    try:
        if nexxT.useCImpl:
            test_json = Path(__file__).parent / "test2.json"
        else:
            test_json = Path(__file__).parent / "test1.json"
        config = Configuration()
        ConfigFileLoader.load(config, test_json)
        # we don't have a save as feature yet, so this function is throwing an exception atm
        expect_exception(ConfigFileLoader.save, config, test_json.parent / "test1.saved.json")
        config.activate("testApp")
        app.processEvents()

        aa = Application.activeApplication

        init = True
        def timeout():
            nonlocal init
            if init:
                init = False
                aa.stop()
                aa.close()
                aa.deinit()
            else:
                app.exit(0)    #logging.INTERNAL = INTERNAL


        def timeout2():
            print("Application timeout hit!")
            nonlocal init
            if init:
                init = False
                aa.stop()
                aa.close()
                aa.deinit()
            else:
                app.exit(1)
        t2.timeout.connect(timeout2)
        t.timeout.connect(timeout)
        def state_changed(state):
            if state == FilterState.ACTIVE:
                t.setSingleShot(True)
                t.start(activeTime_s*1000)
            elif not init and state == FilterState.CONSTRUCTED:
                t.start(1000)
        aa.stateChanged.connect(state_changed)

        aa.init()
        aa.open()
        aa.start()

        app.exec_()
    finally:
        del t
        del t2

def test_smoke():
    simple_setup(2)
    simple_setup(4)

if __name__ == "__main__":
    test_smoke()
