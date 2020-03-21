# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from nexxT.core.BaseGraph import BaseGraph

def expect_exception(f, *args, **kw):
    ok = False
    try:
        f(*args, **kw)
    except:
        ok = True
    assert ok

def test_smoke():
    signals_received = []
    def trace_signal(args, signal):
        signals_received.append( (signal,) + args )

    g = BaseGraph()
    for s in [  "nodeAdded",
                "nodeRenamed",
                "nodeDeleted",
                "inPortAdded",
                "inPortRenamed",
                "inPortDeleted",
                "outPortAdded",
                "outPortRenamed",
                "outPortDeleted",
                "connectionAdded",
                "connectionDeleted"]:
        getattr(g, s).connect(lambda *args, signal=s: trace_signal(args, signal))

    g.addNode("n1")
    assert signals_received == [("nodeAdded", "n1")]
    signals_received.clear()

    g.addNode("n2")
    assert signals_received == [("nodeAdded", "n2")]
    signals_received.clear()

    expect_exception(g.addNode, "n1")

    g.renameNode("n1", "n3")
    assert signals_received == [("nodeRenamed", "n1", "n3")]
    signals_received.clear()

    g.renameNode("n3", "n1")
    assert signals_received == [("nodeRenamed", "n3", "n1")]
    signals_received.clear()

    expect_exception(g.renameNode, "n1", "n2")
    expect_exception(g.renameNode, "n2", "n1")
    expect_exception(g.renameNode, "non_existing", "nonono")

    g.addInputPort("n2", "i1")
    assert signals_received == [("inPortAdded", "n2", "i1")]
    signals_received.clear()

    expect_exception(g.addInputPort, "n3", "i1")
    expect_exception(g.addInputPort, "n2", "i1")

    g.addOutputPort("n1", "o1")
    assert signals_received == [("outPortAdded", "n1", "o1")]
    signals_received.clear()

    expect_exception(g.addOutputPort, "n3", "o1")
    expect_exception(g.addOutputPort, "n1", "o1")

    g.addConnection("n1", "o1", "n2", "i1")
    assert signals_received == [("connectionAdded", "n1", "o1", "n2", "i1")]
    signals_received.clear()

    expect_exception(g.addConnection, "n3", "o1", "n2", "i1")
    expect_exception(g.addConnection, "n1", "o2", "n2", "i1")
    expect_exception(g.addConnection, "n1", "o1", "n3", "i1")
    expect_exception(g.addConnection, "n1", "o1", "n2", "i2")

    g.renameNode("n1", "n3")
    assert signals_received == [("nodeRenamed", "n1", "n3")]
    assert g._connections == [("n3","o1","n2","i1")]
    signals_received.clear()

    g.renameNode("n3", "n1")
    assert signals_received == [("nodeRenamed", "n3", "n1")]
    assert g._connections == [("n1","o1","n2","i1")]
    signals_received.clear()

    g.renameNode("n2", "n3")
    assert signals_received == [("nodeRenamed", "n2", "n3")]
    assert g._connections == [("n1","o1","n3","i1")]
    signals_received.clear()

    g.renameNode("n3", "n2")
    assert signals_received == [("nodeRenamed", "n3", "n2")]
    assert g._connections == [("n1","o1","n2","i1")]
    signals_received.clear()

    g.renameInputPort("n2", "i1", "i2")
    assert signals_received == [("inPortRenamed", "n2", "i1", "i2")]
    assert g._connections == [("n1","o1","n2","i2")]
    signals_received.clear()

    g.renameInputPort("n2", "i2", "i1")
    assert signals_received == [("inPortRenamed", "n2", "i2", "i1")]
    assert g._connections == [("n1","o1","n2","i1")]
    signals_received.clear()

    g.renameOutputPort("n1", "o1", "o2")
    assert signals_received == [("outPortRenamed", "n1", "o1", "o2")]
    assert g._connections == [("n1","o2","n2","i1")]
    signals_received.clear()

    g.renameOutputPort("n1", "o2", "o1")
    assert signals_received == [("outPortRenamed", "n1", "o2", "o1")]
    assert g._connections == [("n1","o1","n2","i1")]
    signals_received.clear()

    expect_exception(g.deleteConnection, "n2","o1","n2","i1")
    expect_exception(g.deleteConnection, "n1","o2","n2","i1")
    expect_exception(g.deleteConnection, "n1","o1","n1","i1")
    expect_exception(g.deleteConnection, "n1","o1","n2","i2")

    g.deleteConnection("n1","o1","n2","i1")
    assert signals_received == [("connectionDeleted", "n1","o1","n2","i1")]
    signals_received.clear()

    g.addConnection("n1","o1","n2","i1")
    assert signals_received == [("connectionAdded", "n1", "o1", "n2", "i1")]
    signals_received.clear()

    expect_exception(g.deleteNode, "n3")

    g.deleteNode("n1")
    assert signals_received == [("connectionDeleted", "n1","o1","n2","i1"), ("outPortDeleted", "n1", "o1"), ("nodeDeleted", "n1")]
    signals_received.clear()

    g.addNode("n1")
    g.addOutputPort("n1", "o1")
    g.addConnection("n1","o1","n2","i1")
    signals_received.clear()
    g.deleteNode("n2")
    assert signals_received == [("connectionDeleted", "n1","o1","n2","i1"), ("inPortDeleted", "n2", "i1"), ("nodeDeleted", "n2")]
    signals_received.clear()

    expect_exception(g.deleteInputPort, "n1", "i1")
    expect_exception(g.deleteInputPort, "n3", "i1")

    expect_exception(g.deleteOutputPort, "n2", "o1")
    expect_exception(g.deleteOutputPort, "n3", "o1")

    assert signals_received ==[]

    g.addNode("n2")
    g.addInputPort("n2", "i1")
    g.addConnection("n1","o1","n2","i1")
    signals_received.clear()
    g.deleteInputPort("n2", "i1")
    assert signals_received == [("connectionDeleted", "n1", "o1", "n2", "i1"), ("inPortDeleted", "n2", "i1")]
    signals_received.clear()

    g.addInputPort("n2", "i1")
    g.addConnection("n1","o1","n2","i1")
    signals_received.clear()
    g.deleteOutputPort("n1", "o1")
    assert signals_received == [("connectionDeleted", "n1", "o1", "n2", "i1"), ("outPortDeleted", "n1", "o1")]
    signals_received.clear()

if __name__ == "__main__":
    test_smoke()