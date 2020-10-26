# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from PySide2.QtCore import QCoreApplication
from nexxT.interface import Services
from nexxT.core.Graph import FilterGraph
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
import os

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

def test_smoke():
    class DummySubConfig(object):
        def __init__(self):
            self.pc = PropertyCollectionImpl("root", None)

        def getPropertyCollection(self):
            return self.pc

    Services.addService("Profiling", None)
    fg = FilterGraph(DummySubConfig())
    n1 = fg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter")
    n2 = fg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleDynamicFilter.py", "SimpleDynInFilter")
    n3 = fg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleDynamicFilter.py", "SimpleDynOutFilter")
    n3_2 = fg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleDynamicFilter.py", "SimpleDynOutFilter")
    assert n3_2 == "SimpleDynOutFilter2"
    n3_3 = fg.addNode("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleDynamicFilter.py", "SimpleDynOutFilter")
    assert n3_3 == "SimpleDynOutFilter3"
    fg.deleteNode(n3_2)
    fg.deleteNode(n3_3)

    fg.addDynamicInputPort(n2, "inPort")
    fg.addDynamicInputPort(n2, "din1")
    fg.addDynamicInputPort(n2, "din2")
    fg.deleteDynamicInputPort(n2, "din2")
    fg.addDynamicInputPort(n2, "din2")

    fg.addDynamicOutputPort(n3, "dout1")
    fg.addDynamicOutputPort(n3, "dout2")
    fg.deleteDynamicOutputPort(n3, "dout2")
    fg.addDynamicOutputPort(n3, "dout2")

    app.processEvents()

    fg.addConnection(n1, "outPort", n2, "inPort")
    fg.addConnection(n3, "outPort", n2, "din1")
    fg.addConnection(n3, "dout1", n2, "din2")
    fg.addConnection(n3, "dout2", n1, "inPort")
    fg.addConnection(n2, "outPort", n3, "inPort")

    fg.renameDynamicInputPort(n2, "din2", "din3")
    fg.renameDynamicInputPort(n2, "din3", "din2")

    expect_exception(fg.renameDynamicInputPort, n2, "din2", "din1")

    fg.renameDynamicOutputPort(n3, "dout2", "dout3")
    fg.renameDynamicOutputPort(n3, "dout3", "dout2")

    fg.renameNode(n1, "static")
    fg.renameNode(n2, "dynin")
    fg.renameNode(n3, "dynout")

    assert set(fg._nodes.keys()) == set(["static", "dynin", "dynout"])
    assert fg._nodes["static"]["inports"] == ["inPort"] and fg._nodes["static"]["outports"] == ["outPort"]
    assert fg._nodes["dynin"]["inports"] == ["inPort", "din1", "din2"] and fg._nodes["dynin"]["outports"] == ["outPort"]
    assert fg._nodes["dynout"]["inports"] == ["inPort"] and fg._nodes["dynout"]["outports"] == ["outPort", "dout1", "dout2"]

    assert ("static", "outPort", "dynin" , "inPort") in fg._connections
    assert ("dynout", "outPort", "dynin" , "din1") in fg._connections
    assert ("dynout", "dout1"  , "dynin" , "din2") in fg._connections
    assert ("dynout", "dout2"  , "static", "inPort") in fg._connections
    assert ("dynin" , "outPort", "dynout", "inPort") in fg._connections


if __name__ == "__main__":
    test_smoke()