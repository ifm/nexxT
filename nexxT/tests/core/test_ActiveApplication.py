# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from nexxT.core.ActiveApplication import ActiveApplication
from nexxT.core.Graph import FilterGraph
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.interface import FilterState
import os
import time
import pprint
from PySide2.QtCore import QCoreApplication, QTimer

def setup():
    global app
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication()

def simple_setup(multithread, sourceFreq, sinkTime, activeTime_s, dynamicFilter):
    t = QTimer()
    t.setSingleShot(True)
    # timeout if test case hangs
    t2 = QTimer()
    t2.start((activeTime_s + 3)*1000)

    try:
        class DummySubConfig(object):
            def __init__(self):
                self.pc = PropertyCollectionImpl("root", None)

            def getPropertyCollection(self):
                return self.pc

        fg = FilterGraph(DummySubConfig())
        n1 = fg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleSource")
        p = fg.getMockup(n1).getPropertyCollectionImpl()
        if multithread:
            p.getChildCollection("_nexxT").setProperty("thread", "thread-2")
        p.setProperty("frequency", sourceFreq)
        if not dynamicFilter:
            n2 = fg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")
        else:
            n2 = fg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleDynamicFilter.py", "SimpleDynInFilter")
            fg.renameNode(n2, "SimpleStaticFilter")
            n2 = "SimpleStaticFilter"
            fg.addDynamicInputPort(n2, "inPort")
            app.processEvents()
        p = fg.getMockup(n2).getPropertyCollectionImpl()
        p.setProperty("sleep_time", sinkTime)

        fg.addConnection(n1, "outPort", n2, "inPort")
        app.processEvents()

        if dynamicFilter:
            fg.renameDynamicInputPort(n2, "inPort", "renamedInPort")

        aa = ActiveApplication(fg)
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

def test_multiThreadSimple():
    events = simple_setup(multithread=True, sourceFreq=4.0, sinkTime=0.5, activeTime_s=2, dynamicFilter=False)
    t_transmit_source = [e["time"] for e in events if e["object"] == "SimpleSource" and e["function"] == "afterTransmit"]
    t_receive_sink = [e["time"] for e in events if e["object"] == "SimpleStaticFilter" and e["function"] == "afterReceive"]
    try:
        # t = 0.00: the sink takes the data and transmit returns instantly -> second transmit is with sourceFreq framerate
        # t = 0.25: the inter thread connection buffers the data (while the sink computes) and transmit returns instantly
        assert t_transmit_source[1] - t_transmit_source[0] < 0.3
        # t = 0.50: the sink computation is done, and the sink gets the second data while the semaphore is released
        # t = 0.50: the inter thread connection buffers the data (while the sink computes) and transmit returns instantly
        assert t_transmit_source[2] - t_transmit_source[1] < 0.3
        # t = 0.75: the source's transmit function blocks at the semaphore
        # t = 1.00: the sink computation of second data is done, and the sink gets the third data while the semaphore is released
        assert all([t_transmit_source[i] - t_transmit_source[i-1] > 0.4 and t_transmit_source[i] - t_transmit_source[i-1] < 0.6 for i in range(3, len(t_transmit_source))])
        # t = 1.00: the source's transmit function returns
        # t = 1.00: new data at source arrived already, the source's transmit function blocks at the semaphore
        # t = 1.50: the sink computation of third data is done, and the sink gets the fourth data while the semaphore is released
        # t = 1.50: the source's transmit function returns
        # t = 1.50: new data at source arrived already, the source's transmit function blocks.
        # ... and so on
        assert len(t_transmit_source) >= 3 + (2-0.5)/0.5 - 1
        assert len(t_receive_sink) in [len(t_transmit_source), len(t_transmit_source)-1]
        assert all([t_receive_sink[i] - t_receive_sink[i-1] > 0.4 and t_receive_sink[i] - t_receive_sink[i-1] < 0.6 for i in range(1, len(t_receive_sink))])
    except:
        printEvents(events)
        raise

def test_singleThreadSimple():
    events = simple_setup(multithread=False, sourceFreq=4.0, sinkTime=0.5, activeTime_s = 2, dynamicFilter=False)
    t_transmit_source = [e["time"] for e in events if e["object"] == "SimpleSource" and e["function"] == "afterTransmit"]
    t_receive_sink = [e["time"] for e in events if e["object"] == "SimpleStaticFilter" and e["function"] == "afterReceive"]
    try:
        # because the receiver is in same thread than transmitter, we effectively have a framerate of 2 Hz
        assert all([t_transmit_source[i] - t_transmit_source[i-1] > 0.4 and t_transmit_source[i] - t_transmit_source[i-1] < 0.6 for i in range(1, len(t_transmit_source))])
        assert len(t_transmit_source) >= 2/0.5 - 1
        assert len(t_receive_sink) == len(t_transmit_source)
        assert all([t_receive_sink[i] - t_receive_sink[i-1] > 0.4 and t_receive_sink[i] - t_receive_sink[i-1] < 0.6 for i in range(1, len(t_receive_sink))])
    except:
        printEvents(events)
        raise

def test_singleThreadDynamic():
    events = simple_setup(multithread=False, sourceFreq=4.0, sinkTime=0.5, activeTime_s = 2, dynamicFilter=True)
    t_transmit_source = [e["time"] for e in events if e["object"] == "SimpleSource" and e["function"] == "afterTransmit"]
    t_receive_sink = [e["time"] for e in events if e["object"] == "SimpleStaticFilter" and e["function"] == "afterReceive"]
    try:
        # because the receiver is in same thread than transmitter, we effectively have a framerate of 2 Hz
        assert all([t_transmit_source[i] - t_transmit_source[i-1] > 0.4 and t_transmit_source[i] - t_transmit_source[i-1] < 0.6 for i in range(1, len(t_transmit_source))])
        assert len(t_transmit_source) >= 2/0.5 - 1
        assert len(t_receive_sink) == len(t_transmit_source)
        assert all([t_receive_sink[i] - t_receive_sink[i-1] > 0.4 and t_receive_sink[i] - t_receive_sink[i-1] < 0.6 for i in range(1, len(t_receive_sink))])
    except:
        printEvents(events)
        raise

if __name__ == "__main__":
    test_singleThreadDynamic()
    test_singleThreadSimple()
    test_multiThreadSimple()
