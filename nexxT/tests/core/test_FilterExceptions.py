# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import json
import logging
from pathlib import Path
import pytest
import pytestqt
from PySide2.QtCore import QCoreApplication, QTimer
from nexxT.interface import FilterState, Services
from nexxT.core.ConfigFiles import ConfigFileLoader
from nexxT.core.Application import Application
from nexxT.core.Configuration import Configuration
import nexxT

def setup():
    global app
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication()

def exception_setup(python, thread, where, activeTime_s):
    logging.getLogger(__name__).info("------------------------------------------------------")
    logging.getLogger(__name__).info("Starting exception_setup %d %s %s %f", python, thread, where, activeTime_s)
    from nexxT.services.ConsoleLogger import ConsoleLogger
    logger = ConsoleLogger()
    Services.addService("Logging", logger)
    class LogCollector(logging.StreamHandler):
        def __init__(self):
            super().__init__()
            self.logs = []
        def emit(self, record):
            self.logs.append(record)
    # avoid warning flood about service profiling not found
    Services.addService("Profiling", None)
    collector = LogCollector()
    logging.getLogger().addHandler(collector)
    try:
        t = QTimer()
        t.setSingleShot(True)
        # timeout if test case hangs
        t2 = QTimer()
        t2.start((activeTime_s + 3)*1000)
        try:
            test_json = Path(__file__).parent / "test_except_constr.json"
            with test_json.open("r", encoding='utf-8') as fp:
                cfg = json.load(fp)
            if nexxT.useCImpl and not python:
                cfg["composite_filters"][0]["nodes"][2]["library"] = "binary://../binary/${NEXXT_PLATFORM}/${NEXXT_VARIANT}/test_plugins"
            cfg["composite_filters"][0]["nodes"][2]["thread"] = thread
            cfg["composite_filters"][0]["nodes"][2]["properties"]["whereToThrow"] = where
            mod_json = Path(__file__).parent / "test_except_constr_tmp.json"
            with mod_json.open("w", encoding="utf-8") as fp:
                json.dump(cfg, fp)

            config = Configuration()
            ConfigFileLoader.load(config, mod_json)
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
                    app.exit(0)

            def timeout2():
                print("Application timeout hit!")
                nonlocal init
                if init:
                    init = False
                    aa.stop()
                    aa.close()
                    aa.deinit()
                else:
                    print("application exit!")
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
    finally:
        logging.getLogger().removeHandler(collector)
        Services.removeAll()
    return collector.logs

@pytest.mark.qt_no_exception_capture
def test_exception_python_main_none():
    logs = exception_setup(True, "main", "nowhere", 2)

# ---------------
# port exceptions
# ---------------

@pytest.mark.qt_no_exception_capture
def test_exception_python_main_port():
    logs = exception_setup(True, "main", "port", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) > 0
    assert all(e == "Uncaught exception" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_source_port():
    logs = exception_setup(True, "thread-source", "port", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) > 0
    assert all(e == "Uncaught exception" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_compute_port():
    logs = exception_setup(True, "compute", "port", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) > 0
    assert all(e == "Uncaught exception" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_main_port():
    logs = exception_setup(False, "main", "port", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) > 0
    assert all(e == "Unexpected exception during onPortDataChanged from filter filter: exception in port" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_source_port():
    logs = exception_setup(False, "thread-source", "port", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) > 0
    assert all(e == "Unexpected exception during onPortDataChanged from filter filter: exception in port" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_compute_port():
    logs = exception_setup(False, "compute", "port", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) > 0
    assert all(e == "Unexpected exception during onPortDataChanged from filter filter: exception in port" for e in errors)

# ---------------
# init exceptions
# ---------------

@pytest.mark.qt_no_exception_capture
def test_exception_python_main_init():
    logs = exception_setup(True, "main", "init", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation INITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_source_init():
    logs = exception_setup(True, "thread-source", "init", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation INITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_compute_init():
    logs = exception_setup(True, "compute", "init", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation INITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_main_init():
    logs = exception_setup(False, "main", "init", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation INITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_source_init():
    logs = exception_setup(False, "thread-source", "init", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation INITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_compute_init():
    logs = exception_setup(False, "compute", "init", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation INITIALIZING of filter filter" for e in errors)

# ---------------
# start exceptions
# ---------------

@pytest.mark.qt_no_exception_capture
def test_exception_python_main_start():
    logs = exception_setup(True, "main", "start", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STARTING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_source_start():
    logs = exception_setup(True, "thread-source", "start", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STARTING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_compute_start():
    logs = exception_setup(True, "compute", "start", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STARTING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_main_start():
    logs = exception_setup(False, "main", "start", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STARTING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_source_start():
    logs = exception_setup(False, "thread-source", "start", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STARTING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_compute_start():
    logs = exception_setup(False, "compute", "start", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STARTING of filter filter" for e in errors)

# ---------------
# stop exceptions
# ---------------

@pytest.mark.qt_no_exception_capture
def test_exception_python_main_stop():
    logs = exception_setup(True, "main", "stop", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STOPPING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_source_stop():
    logs = exception_setup(True, "thread-source", "stop", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STOPPING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_compute_stop():
    logs = exception_setup(True, "compute", "stop", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STOPPING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_main_stop():
    logs = exception_setup(False, "main", "stop", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STOPPING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_source_stop():
    logs = exception_setup(False, "thread-source", "stop", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STOPPING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_compute_stop():
    logs = exception_setup(False, "compute", "stop", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert all(e == "Exception while executing operation STOPPING of filter filter" for e in errors)

# ---------------
# deinit exceptions
# ---------------

@pytest.mark.qt_no_exception_capture
def test_exception_python_main_deinit():
    logs = exception_setup(True, "main", "deinit", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation DEINITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_source_deinit():
    logs = exception_setup(True, "thread-source", "deinit", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation DEINITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
def test_exception_python_compute_deinit():
    logs = exception_setup(True, "compute", "deinit", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation DEINITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_main_deinit():
    logs = exception_setup(False, "main", "deinit", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation DEINITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_source_deinit():
    logs = exception_setup(False, "thread-source", "deinit", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation DEINITIALIZING of filter filter" for e in errors)

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_compute_deinit():
    logs = exception_setup(False, "compute", "deinit", 2)
    errors = [r.message for r in logs if r.levelno >= logging.ERROR]
    assert 1 <= len(errors) <= 3
    assert all(e == "Exception while executing operation DEINITIALIZING of filter filter" for e in errors)

# ---------------
# constructor exceptions
# ---------------

@pytest.mark.qt_no_exception_capture
def test_exception_python_main_constr():
    try:
        logs = exception_setup(True, "main", "constructor", 2)
        exception = False
    except Exception as e:
        exception = True
    assert exception

@pytest.mark.qt_no_exception_capture
def test_exception_python_source_constr():
    try:
        logs = exception_setup(True, "thread-source", "constructor", 2)
        exception = False
    except Exception as e:
        exception = True
    assert exception

@pytest.mark.qt_no_exception_capture
def test_exception_python_compute_constr():
    try:
        logs = exception_setup(True, "compute", "constructor", 2)
        exception = False
    except Exception as e:
        exception = True
    assert exception

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_main_constr():
    try:
        logs = exception_setup(False, "main", "constructor", 2)
        exception = False
    except Exception as e:
        exception = True
    assert exception

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_source_constr():
    try:
        logs = exception_setup(False, "thread-source", "constructor", 2)
        exception = False
    except Exception as e:
        exception = True
    assert exception

@pytest.mark.qt_no_exception_capture
@pytest.mark.skipif(not nexxT.useCImpl, reason="python only test")
def test_exception_c_compute_constr():
    try:
        logs = exception_setup(False, "compute", "constructor", 2)
        exception = False
    except Exception as e:
        exception = True
    assert exception

if __name__ == "__main__":
    test_exception_python_compute_constr()