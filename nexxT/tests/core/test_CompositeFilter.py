# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import os
import time
from PySide2.QtCore import QCoreApplication, QTimer
from nexxT.interface import FilterState
from nexxT.core.CompositeFilter import CompositeFilter
from nexxT.core.Application import Application
from nexxT.core.ActiveApplication import ActiveApplication
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.Exceptions import CompositeRecursion
from nexxT.core.Configuration import Configuration

def setup():
    global app
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication()

def expect_exception(excClass, f, *args, **kw):
    ok = False
    try:
        f(*args, **kw)
    except excClass:
        ok = True
    assert ok

def simple_setup(sourceFreq, activeTime_s):
    t = QTimer()
    t.setSingleShot(True)
    # timeout if test case hangs
    t2 = QTimer()
    t2.start((activeTime_s + 3)*1000)
    try:
        config = Configuration()
        cf_inner = CompositeFilter("cf_inner", config)
        cg_inner = cf_inner.getGraph()
        f1 = cg_inner.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")
        cg_inner.addDynamicOutputPort("CompositeInput", "compositeIn")
        cg_inner.addDynamicInputPort("CompositeOutput", "compositeOut")
        app.processEvents()
        cg_inner.addConnection("CompositeInput", "compositeIn", f1, "inPort")
        cg_inner.addConnection(f1, "outPort", "CompositeOutput", "compositeOut")

        cf = CompositeFilter("cf", config)
        cg = cf.getGraph()
        f1 = cg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")
        f2 = cg.addNode(cf_inner, "compositeNode")
        app.processEvents()

        cg.addDynamicOutputPort("CompositeInput", "compositeIn")
        cg.addDynamicInputPort("CompositeOutput", "compositeOut")
        app.processEvents()

        cg.addConnection("CompositeInput", "compositeIn", f1, "inPort")
        cg.addConnection(f1, "outPort", f2, "compositeIn")
        cg.addConnection(f2, "compositeOut", "CompositeOutput", "compositeOut")

        expect_exception(CompositeRecursion, cg.addNode, cf, "compositeNode")
        expect_exception(CompositeRecursion, cg_inner.addNode, cf, "compositeNode")

        a = Application("app", config)
        ag = a.getGraph()
        cn = ag.addNode(cf, "compositeNode")

        app.processEvents()
        app.processEvents()

        cn_ip = [p.name() for p in ag.getMockup(cn).getAllInputPorts()]
        cn_op = [p.name() for p in ag.getMockup(cn).getAllOutputPorts()]
        assert cn_ip == ["compositeIn"]
        assert cn_op == ["compositeOut"]

        sn = ag.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleSource")
        p = ag.getMockup(sn).propertyCollection()
        p.setProperty("frequency", sourceFreq)
        ag.addConnection(sn, "outPort", cn, "compositeIn")
        fn = ag.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")
        ag.addConnection(cn, "compositeOut", fn, "inPort")

        cg.renameDynamicInputPort("CompositeOutput", "compositeOut", "renamedOut")
        app.processEvents()
        cg.renameDynamicOutputPort("CompositeInput", "compositeIn", "renamedIn")
        app.processEvents()

        aa = ActiveApplication(ag)
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
                app.exit(1)
        t2.timeout.connect(timeout2)
        t.timeout.connect(timeout)

        events = []
        def logger(object, function, datasample):
            nonlocal events
            events.append(dict(object=object, function=function, datasample=datasample, time=time.time()))

        def state_changed(state):
            if state == FilterState.ACTIVE:
                t.setSingleShot(True)
                t.start(activeTime_s*1000)
            elif not init and state == FilterState.CONSTRUCTED:
                t.start(1000)
        aa.stateChanged.connect(state_changed)

        t1 = aa._filters2threads["/SimpleSource"]
        f1 = aa._threads[t1]._filters["/SimpleSource"].getPlugin()
        f1.beforeTransmit = lambda ds: logger(object="SimpleSource", function="beforeTransmit", datasample=ds)
        f1.afterTransmit = lambda: logger(object="SimpleSource", function="afterTransmit", datasample=None)

        t2 = aa._filters2threads["/SimpleStaticFilter"]
        f2 = aa._threads[t2]._filters["/SimpleStaticFilter"].getPlugin()
        f2.afterReceive = lambda ds: logger(object="SimpleStaticFilter", function="afterReceive", datasample=ds)
        f2.beforeTransmit = lambda ds: logger(object="SimpleStaticFilter", function="beforeTransmit", datasample=ds)
        f2.afterTransmit = lambda: logger(object="SimpleStaticFilter", function="afterTransmit", datasample=None)

        aa.init()
        aa.open()
        aa.start()

        app.exec_()

        return events
    finally:
        del t
        del t2

def printEvents(events):
    t0 = None
    dst0 = None
    for e in events:
        if t0 is None:
            t0 = e["time"]
        if dst0 is None and e["datasample"] is not None:
            dst0 = e["datasample"].getTimestamp()
        print("%10.6f: %20s.%15s ds.t=%s" % (e["time"] - t0, e["object"], e["function"], e["datasample"].getTimestamp() - dst0 if e["datasample"] is not None else ""))

def test_smoke():
    events = simple_setup(sourceFreq=2.0, activeTime_s=2)
    t_transmit_source = [e["time"] for e in events if
                         e["object"] == "SimpleSource" and e["function"] == "afterTransmit"]
    t_receive_sink = [e["time"] for e in events if
                      e["object"] == "SimpleStaticFilter" and e["function"] == "afterReceive"]
    try:
        # because the receiver is in same thread than transmitter, we effectively have a framerate of 2 Hz
        assert all([t_transmit_source[i] - t_transmit_source[i - 1] > 0.4 and t_transmit_source[i] - t_transmit_source[
            i - 1] < 0.6 for i in range(1, len(t_transmit_source))])
        assert len(t_transmit_source) >= 4-1
        assert len(t_receive_sink) == len(t_transmit_source)
        assert all(
            [t_receive_sink[i] - t_receive_sink[i - 1] > 0.4 and t_receive_sink[i] - t_receive_sink[i - 1] < 0.6 for i
             in range(1, len(t_receive_sink))])
    except:
        printEvents(events)
        raise

def test_recursion():
    config = Configuration()
    cf_inner = CompositeFilter("cf_inner", config)
    cg_inner = cf_inner.getGraph()
    f1 = cg_inner.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")

    cf = CompositeFilter("cf", config)
    cg = cf.getGraph()
    f1 = cg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")
    f2 = cg.addNode(cf_inner, "compositeNode")

    # add composite node to itself
    cg_oldNodes = set(cg.allNodes())
    cg_inner_oldNodes = set(cg_inner.allNodes())
    expect_exception(CompositeRecursion, cg.addNode, cf, "compositeNode")
    assert cg_oldNodes == set(cg.allNodes())

    # add composite node to an inner node
    expect_exception(CompositeRecursion, cg_inner.addNode, cf, "compositeNode")
    assert cg_inner_oldNodes == set(cg_inner.allNodes())

    # double dependency
    cf1 = CompositeFilter("cf1", config)
    cf2 = CompositeFilter("cf2", config)
    cf1.getGraph().addNode(cf2, "compositeNode")
    expect_exception(CompositeRecursion, cf2.getGraph().addNode, cf1, "compositeNode")

def test_doubleNames():
    activeTime_s = 2
    sourceFreq = 2
    t = QTimer()
    t.setSingleShot(True)
    # timeout if test case hangs
    t2 = QTimer()
    t2.start((activeTime_s + 3)*1000)
    try:
        config = Configuration()
        cf_inner = CompositeFilter("cf_inner", config)
        cg_inner = cf_inner.getGraph()
        f1 = cg_inner.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")
        cg_inner.addDynamicOutputPort("CompositeInput", "compositeIn")
        cg_inner.addDynamicInputPort("CompositeOutput", "compositeOut")
        app.processEvents()
        cg_inner.addConnection("CompositeInput", "compositeIn", f1, "inPort")
        cg_inner.addConnection(f1, "outPort", "CompositeOutput", "compositeOut")

        a = Application("app", config)
        ag = a.getGraph()
        cn = ag.addNode(cf_inner, "compositeNode")
        #f2 = ag.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")

        app.processEvents()
        app.processEvents()

        cn_ip = [p.name() for p in ag.getMockup(cn).getAllInputPorts()]
        cn_op = [p.name() for p in ag.getMockup(cn).getAllOutputPorts()]
        assert cn_ip == ["compositeIn"]
        assert cn_op == ["compositeOut"]

        sn = ag.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleSource")
        p = ag.getMockup(sn).propertyCollection()
        p.setProperty("frequency", sourceFreq)
        ag.addConnection(sn, "outPort", cn, "compositeIn")
        fn = ag.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")
        ag.addConnection(cn, "compositeOut", fn, "inPort")

        cg_inner.renameDynamicInputPort("CompositeOutput", "compositeOut", "renamedOut")
        app.processEvents()
        cg_inner.renameDynamicOutputPort("CompositeInput", "compositeIn", "renamedIn")
        app.processEvents()

        aa = ActiveApplication(ag)
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
                app.exit(1)
        t2.timeout.connect(timeout2)
        t.timeout.connect(timeout)

        events = []
        def logger(object, function, datasample):
            nonlocal events
            events.append(dict(object=object, function=function, datasample=datasample, time=time.time()))

        def state_changed(state):
            if state == FilterState.ACTIVE:
                t.setSingleShot(True)
                t.start(activeTime_s*1000)
            elif not init and state == FilterState.CONSTRUCTED:
                t.start(1000)
        aa.stateChanged.connect(state_changed)

        t1 = aa._filters2threads["/SimpleSource"]
        f1 = aa._threads[t1]._filters["/SimpleSource"].getPlugin()
        f1.beforeTransmit = lambda ds: logger(object="SimpleSource", function="beforeTransmit", datasample=ds)
        f1.afterTransmit = lambda: logger(object="SimpleSource", function="afterTransmit", datasample=None)

        t2 = aa._filters2threads["/SimpleStaticFilter"]
        f2 = aa._threads[t2]._filters["/SimpleStaticFilter"].getPlugin()
        f2.afterReceive = lambda ds: logger(object="SimpleStaticFilter", function="afterReceive", datasample=ds)
        f2.beforeTransmit = lambda ds: logger(object="SimpleStaticFilter", function="beforeTransmit", datasample=ds)
        f2.afterTransmit = lambda: logger(object="SimpleStaticFilter", function="afterTransmit", datasample=None)

        aa.init()
        aa.open()
        aa.start()

        app.exec_()

        return events
    finally:
        del t
        del t2


if __name__ == "__main__":
    test_recursion()
    test_smoke()
    test_doubleNames()
