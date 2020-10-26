# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.PropertyHandlers import defaultHandler
from nexxT.interface import PropertyHandler
from nexxT.core.Exceptions import *
from PySide2.QtCore import QRegExp, QCoreApplication

class MySimplePropertyHandler(PropertyHandler):
    def __init__(self, options):
        self.options = options

    def validate(self, value):
        return value

    def fromConfig(self, value):
        return value

    def toConfig(self, value):
        return value

def expect_exception(f, etype, *args, **kw):
    ok = False
    try:
        f(*args, **kw)
    except etype:
        ok = True
    assert ok

def setup():
    global app
    # we need a QCoreApplication for the child events
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication()

def test_smoke():
    signals_received = []

    def trace_signal(args, signal):
        signals_received.append((signal,) + args)

    def newPropColl(name, parent):
        res = PropertyCollectionImpl(name, parent)
        for s in ["propertyChanged",
                  "propertyAdded",
                  "propertyRemoved",
                  "childAdded",
                  "childRemoved",
                  "childRenamed"]:
            getattr(res, s).connect(lambda *args, signal=s: trace_signal(args, signal))
        return res

    p_root = newPropColl("root", None)
    assert len(signals_received) == 0
    p_child1 = newPropColl("child1", p_root)
    assert signals_received == [("childAdded", p_root, "child1")]
    signals_received.clear()
    p_child2 = newPropColl("child2", p_root)
    assert signals_received == [("childAdded", p_root, "child2")]
    signals_received.clear()
    p_child11 = newPropColl("child11", p_child1)
    assert signals_received == [("childAdded", p_child1, "child11")]
    signals_received.clear()
    p_child12 = newPropColl("child12", p_child1)
    assert signals_received == [("childAdded", p_child1, "child12")]
    signals_received.clear()

    expect_exception(newPropColl, PropertyCollectionChildExists, "child1", p_root)
    expect_exception(p_root.deleteChild, PropertyCollectionChildNotFound, "child5")

    assert p_root.getChildCollection("child2") is p_child2

    expect_exception(p_child1.setProperty, PropertyCollectionPropertyNotFound, "nonexisting", "no")

    assert p_child1.defineProperty("prop1", 1.0, "a sample float prop") == 1.0
    assert signals_received == [("propertyAdded", p_child1, "prop1")]
    signals_received.clear()
    p_child1.setProperty("prop1", 2.0)
    assert p_child1.defineProperty("prop1", 1.0, "a sample float prop") == 2.0
    assert signals_received == [("propertyChanged", p_child1, "prop1")]
    signals_received.clear()
    p_child1.setProperty("prop1", "3.0")
    assert p_child1.defineProperty("prop1", 1.0, "a sample float prop") == 3.0
    assert signals_received == [("propertyChanged", p_child1, "prop1")]
    signals_received.clear()

    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop1", 2.0, "a sample float prop")
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop1", 1.0, "aa sample float prop")
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop1", 1.0, "a sample float prop",
                     options=dict(min=0))
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop1", 1.0, "a sample float prop",
                     propertyHandler=MySimplePropertyHandler({}))
    expect_exception(p_child1.setProperty, PropertyParsingError, "prop1", "a")

    assert p_child1.defineProperty("prop2", 4, "a sample int prop") == 4
    assert signals_received == [("propertyAdded", p_child1, "prop2")]
    signals_received.clear()
    p_child1.setProperty("prop2", 3)
    assert p_child1.defineProperty("prop2", 4, "a sample int prop") == 3
    assert signals_received == [("propertyChanged", p_child1, "prop2")]
    signals_received.clear()
    p_child1.setProperty("prop2", "2")
    assert p_child1.defineProperty("prop2", 4, "a sample int prop") == 2
    assert signals_received == [("propertyChanged", p_child1, "prop2")]
    signals_received.clear()

    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop2", 5, "a sample int prop")
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop2", 4, "aa sample int prop")
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop2", 4, "a sample int prop",
                     options=dict(min=1))
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop2", 4, "a sample int prop",
                     propertyHandler=MySimplePropertyHandler({}))
    expect_exception(p_child1.setProperty, PropertyParsingError, "prop2", "a")

    assert p_child1.defineProperty("prop3", "a", "a sample str prop") == "a"
    assert signals_received == [("propertyAdded", p_child1, "prop3")]
    signals_received.clear()
    p_child1.setProperty("prop3", "b")
    assert p_child1.defineProperty("prop3", "a", "a sample str prop") == "b"
    assert signals_received == [("propertyChanged", p_child1, "prop3")]
    signals_received.clear()

    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop3", "b", "a sample str prop")
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop3", "a", "aa sample str prop")
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop3", "a", "a sample str prop",
                     options=dict(enum=["a"]))
    expect_exception(p_child1.defineProperty, PropertyInconsistentDefinition, "prop3", "a", "a sample str prop",
                     propertyHandler=MySimplePropertyHandler({}))

    expect_exception(p_child2.defineProperty, PropertyInconsistentDefinition, "nonsense2", 1.0, "",
                     propertyHandler=defaultHandler("")({}))

    expect_exception(p_child2.defineProperty, PropertyCollectionUnknownType, "nonsense3", [], "")
    expect_exception(p_child2.defineProperty, PropertyCollectionUnknownType, "nonsense3", [], "",
                     options=dict(min=1))

    p_child1.markAllUnused()
    assert p_child1.defineProperty("prop3", "a", "a sample str prop") == "b"
    p_child1.deleteUnused()
    assert set(signals_received) == set([("propertyRemoved", p_child1, "prop1"),
                                         ("propertyRemoved", p_child1, "prop2")])
    signals_received.clear()

    del p_child1
    del p_child11
    del p_child12
    p_root.deleteChild("child1")
    assert set([(s[0], s[2]) for s in signals_received]) == set([("childRemoved", "child11"),
                                                                 ("childRemoved", "child12"),
                                                                 ("childRemoved", "child1")])

if __name__ == "__main__":
    test_smoke()