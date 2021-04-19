# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import glob
import logging
from PySide2.QtCore import Qt, QCoreApplication, QTimer, QModelIndex
from nexxT.interface import Services, FilterState
from nexxT.core.Utils import MethodInvoker, waitForSignal
from nexxT.core.Application import Application

logger = logging.getLogger(__name__)

def _getIndex(model, names):
    """
    find the model index indicated by names (a list of strings)
    :param model: a QAbstractItemModel instance
    :param names: a list of strings
    :return: a QModelIndex instance
    """
    idx = QModelIndex()
    for i,n in enumerate(names):
        found = False
        for r in range(model.rowCount(idx)):
            ii = model.index(r,0,idx)
            if model.data(ii, Qt.DisplayRole) == n:
                idx = ii
                found = True
                break
        if not found:
            raise RuntimeError("not found: %d(%s) " % (i,n))
    return idx

def execute_0():
    """
    Creates a new application with an app and a composite filter and saves it to a file; finally activate the
    created app.
    :return:
    """
    logger.info("execute_0:begin")

    cfg = Services.getService("Configuration")

    # create a new configuration with a composite graph and an application
    execute_0.i = MethodInvoker(cfg.newConfig, Qt.QueuedConnection, "basicworkflow.json")
    waitForSignal(cfg.configuration().configNameChanged)

    # create simple composite filter
    cfg.configuration().renameComposite(cfg.configuration().addNewCompositeFilter(), "composite")
    comp = cfg.configuration().compositeFilterByName("composite")
    node = comp.getGraph().addNode(library="pyfile://./SimpleStaticFilter.py",
                                   factoryFunction="SimpleStaticFilter")
    idx = _getIndex(cfg.model, ["composite", "composite", node, "sleep_time"])
    cfg.model.setData(idx.siblingAtColumn(1), 0.01, Qt.EditRole)

    execute_0.i = MethodInvoker(comp.getGraph().addDynamicInputPort, Qt.QueuedConnection, "CompositeOutput", "out")
    waitForSignal(comp.getGraph().dynInputPortAdded)
    execute_0.i = MethodInvoker(comp.getGraph().addDynamicOutputPort, Qt.QueuedConnection, "CompositeInput", "in")
    waitForSignal(comp.getGraph().dynOutputPortAdded)
    comp.getGraph().addConnection("CompositeInput", "in", node, "inPort")
    comp.getGraph().addConnection(node, "outPort", "CompositeOutput", "out")

    # create simple application (live/recorder)
    cfg.configuration().renameApp(cfg.configuration().addNewApplication(), "myApp")
    app = cfg.configuration().applicationByName("myApp")
    import nexxT
    if nexxT.useCImpl:
        src = app.getGraph().addNode(library="entry_point://tests.nexxT.CSimpleSource",
                                      factoryFunction="entry_point")
    else:
        src = app.getGraph().addNode(library="pyfile://./SimpleStaticFilter.py",
                                      factoryFunction="SimpleSource")
    src2 = app.getGraph().addNode(library="pyfile://./SimpleStaticFilter.py",
                                  factoryFunction="SimpleSource")
    idx = _getIndex(cfg.model, ["apps", "myApp", src, "frequency"])
    cfg.model.setData(idx.siblingAtColumn(1), 10.0, Qt.EditRole)
    idx = _getIndex(cfg.model, ["apps", "myApp", src2, "frequency"])
    cfg.model.setData(idx.siblingAtColumn(1), 2.0, Qt.EditRole)
    idx = _getIndex(cfg.model, ["apps", "myApp", src2, "log_tr"])
    cfg.model.setData(idx.siblingAtColumn(1), False, Qt.EditRole)

    flt = app.getGraph().addNode(library=comp,
                                 factoryFunction="compositeNode")
    app.getGraph().addConnection(src, "outPort", flt, "in")

    # add a recorder
    rec = app.getGraph().addNode(library="pymod://nexxT.filters.hdf5", factoryFunction="Hdf5Writer")
    execute_0.i = MethodInvoker(app.getGraph().addDynamicInputPort, Qt.QueuedConnection, rec, "stream1")
    waitForSignal(app.getGraph().dynInputPortAdded)
    execute_0.i = MethodInvoker(app.getGraph().addDynamicInputPort, Qt.QueuedConnection, rec, "stream2")
    waitForSignal(app.getGraph().dynInputPortAdded)
    app.getGraph().addConnection(src, "outPort", rec, "stream1")
    app.getGraph().addConnection(src2, "outPort", rec, "stream2")

    # assign threads
    app.getGraph().getMockup(src).propertyCollection().getChildCollection("_nexxT").setProperty("thread", "source-thread")
    app.getGraph().getMockup(src2).propertyCollection().getChildCollection("_nexxT").setProperty("thread", "source2-thread")
    app.getGraph().getMockup(rec).propertyCollection().getChildCollection("_nexxT").setProperty("thread", "rec-thread")

    # create another application (playback)
    # hdf5 reader
    cfg.configuration().renameApp(cfg.configuration().addNewApplication(), "pbApp")
    app = cfg.configuration().applicationByName("pbApp")
    pb = app.getGraph().addNode(library="pymod://nexxT.filters.hdf5", factoryFunction="Hdf5Reader", suggestedName="player")
    assert pb == "player"
    execute_0.i = MethodInvoker(app.getGraph().addDynamicOutputPort, Qt.QueuedConnection, pb, "stream1")
    waitForSignal(app.getGraph().dynOutputPortAdded)
    execute_0.i = MethodInvoker(app.getGraph().addDynamicOutputPort, Qt.QueuedConnection, pb, "stream2")
    waitForSignal(app.getGraph().dynOutputPortAdded)
    # 2 filters
    flt1 = app.getGraph().addNode(library="pyfile://./SimpleStaticFilter.py",
                                  factoryFunction="SimpleStaticFilter", suggestedName="flt1")
    assert flt1 == "flt1"
    idx = _getIndex(cfg.model, ["apps", "pbApp", "flt1", "sleep_time"])
    cfg.model.setData(idx.siblingAtColumn(1), 0.01, Qt.EditRole)
    idx = _getIndex(cfg.model, ["apps", "pbApp", "flt1", "log_rcv"])
    cfg.model.setData(idx.siblingAtColumn(1), True, Qt.EditRole)
    idx = _getIndex(cfg.model, ["apps", "pbApp", "flt1", "log_prefix"])
    cfg.model.setData(idx.siblingAtColumn(1), "(flt1) ", Qt.EditRole)

    flt2 = app.getGraph().addNode(library="pyfile://./SimpleStaticFilter.py",
                                  factoryFunction="SimpleStaticFilter", suggestedName="flt2")
    assert flt2 == "flt2"
    idx = _getIndex(cfg.model, ["apps", "pbApp", "flt2", "sleep_time"])
    cfg.model.setData(idx.siblingAtColumn(1), 0.01, Qt.EditRole)
    idx = _getIndex(cfg.model, ["apps", "pbApp", "flt2", "log_rcv"])
    cfg.model.setData(idx.siblingAtColumn(1), True, Qt.EditRole)
    idx = _getIndex(cfg.model, ["apps", "pbApp", "flt2", "log_prefix"])
    cfg.model.setData(idx.siblingAtColumn(1), "(flt2) ", Qt.EditRole)

    app.getGraph().addConnection("player", "stream1", "flt1", "inPort")
    app.getGraph().addConnection("player", "stream2", "flt2", "inPort")

    # save application
    execute_0.i = MethodInvoker(cfg.saveConfig, Qt.QueuedConnection)
    waitForSignal(cfg.configuration().configNameChanged)

    # change active app
    execute_1.i = MethodInvoker(cfg.changeActiveApp, Qt.QueuedConnection, "myApp")
    waitForSignal(cfg.configuration().appActivated)

    # activate
    execute_1.i = MethodInvoker(cfg.activate, Qt.QueuedConnection)
    waitForSignal(cfg.configuration().appActivated)
    if app.activeApplication.getState() != FilterState.ACTIVE:
        waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.ACTIVE)
    logger.info("execute_0:end")

def execute_1():
    """
    after 3 seconds, deactivate and re-activate the app
    after 3 seconds, re-open and re-activate the app
    after 3 more seconds, quit
    :return:
    """
    logger.info("execute_1:begin")
    cfg = Services.getService("Configuration")
    rc = Services.getService("RecordingControl")

    logger.info("app activated")
    app = cfg.configuration().applicationByName("myApp")

    t = QTimer()
    t.setSingleShot(True)
    t.setInterval(3000)
    t.start()
    waitForSignal(t.timeout)

    execute_1.i = MethodInvoker(cfg.deactivate, Qt.QueuedConnection)
    waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.CONSTRUCTED)
    logger.info("app deactivated")

    execute_1.i = MethodInvoker(cfg.activate, Qt.QueuedConnection)
    waitForSignal(cfg.configuration().appActivated)
    if app.activeApplication.getState() != FilterState.ACTIVE:
        waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.ACTIVE)

    execute_1.i = MethodInvoker(rc.startRecording, Qt.QueuedConnection, ".")
    logger.info("app activated")

    t = QTimer()
    t.setSingleShot(True)
    t.setInterval(3000)
    t.start()
    waitForSignal(t.timeout)

    execute_1.i = MethodInvoker(cfg.deactivate, Qt.QueuedConnection)
    waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.CONSTRUCTED)
    logger.info("app deactivated")

    # re-open this application
    execute_1.i = MethodInvoker(cfg.loadConfig, Qt.QueuedConnection, "basicworkflow.json")
    waitForSignal(cfg.configuration().configNameChanged)
    logger.info("config loaded")

    # activate
    execute_1.i = MethodInvoker(cfg.changeActiveApp, Qt.QueuedConnection, "myApp")
    waitForSignal(cfg.configuration().appActivated)
    execute_1.i = MethodInvoker(cfg.activate, Qt.QueuedConnection)
    waitForSignal(cfg.configuration().appActivated)
    if app.activeApplication.getState() != FilterState.ACTIVE:
        waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.ACTIVE)
    logger.info("app activated")

    t = QTimer()
    t.setSingleShot(True)
    t.setInterval(3000)
    t.start()
    waitForSignal(t.timeout)

    execute_1.i = MethodInvoker(QCoreApplication.quit, Qt.QueuedConnection)
    logger.info("execute_1:end")

def execute_2():
    logger.info("execute_2:begin")
    cfg = Services.getService("Configuration")
    pbc = Services.getService("PlaybackControl")

    app = cfg.configuration().applicationByName("pbApp")

    logger.info("app activated")
    execute_2.i = MethodInvoker(pbc.setSequence, Qt.QueuedConnection, glob.glob("./*.h5")[0])
    _, tbegin, tend, _ = waitForSignal(pbc.sequenceOpened)

    execute_2.i = MethodInvoker(pbc.startPlayback, Qt.QueuedConnection)
    waitForSignal(pbc.playbackStarted)
    waitForSignal(pbc.playbackPaused)
    logger.info("played")

    execute_2.i = MethodInvoker(pbc.seekBeginning, Qt.QueuedConnection)
    waitForSignal(pbc.currentTimestampChanged)
    logger.info("seekBeginning")

    for i in range(10):
        execute_2.i = MethodInvoker(pbc.stepForward, Qt.QueuedConnection, None)
        waitForSignal(pbc.playbackPaused)
        logger.info("stepForward[None]")

    for i in range(10):
        execute_2.i = MethodInvoker(pbc.stepForward, Qt.QueuedConnection, "stream1")
        waitForSignal(pbc.playbackPaused)
        logger.info("stepForward[stream1]")

    for i in range(2):
        execute_2.i = MethodInvoker(pbc.stepForward, Qt.QueuedConnection, "stream2")
        waitForSignal(pbc.playbackPaused)
        logger.info("stepForward[stream2]")

    execute_2.i = MethodInvoker(pbc.seekTime, Qt.QueuedConnection, (tbegin + tend)//2)
    waitForSignal(pbc.currentTimestampChanged)
    logger.info("seekTime")

    execute_2.i = MethodInvoker(pbc.seekEnd, Qt.QueuedConnection)
    waitForSignal(pbc.currentTimestampChanged)
    logger.info("seekEnd")

    for i in range(10):
        execute_2.i = MethodInvoker(pbc.stepBackward, Qt.QueuedConnection, None)
        waitForSignal(pbc.playbackPaused)
        logger.info("stepBackward[None]")

    execute_2.i = MethodInvoker(pbc.seekTime, Qt.QueuedConnection, tbegin - 1000000000)
    waitForSignal(pbc.currentTimestampChanged)
    logger.info("seekTimeBegin")

    execute_2.i = MethodInvoker(pbc.seekTime, Qt.QueuedConnection, tend + 1000000000)
    waitForSignal(pbc.currentTimestampChanged)
    logger.info("seekTimeEnd")

    execute_2.i = MethodInvoker(QCoreApplication.quit, Qt.QueuedConnection)
    logger.info("execute_2:end")
    

if stage == 0:
    execute_0()
    execute_1()
elif stage == 1:
    execute_1()
elif stage == 2:
    execute_2()