# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from nexxT.core.FilterEnvironment import FilterEnvironment
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.interface import Port, InputPort, OutputPort, FilterState, DataSample
from nexxT import useCImpl
import os

def expect_exception(f, *args, **kw):
    ok = False
    try:
        f(*args, **kw)
    except:
        ok = True
    assert ok

def test_static_filter():
    function_calls = []
    with FilterEnvironment("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter",
                           PropertyCollectionImpl("root", None) ) as staticPyFilter:
        f = staticPyFilter.getPlugin()
        
        # call the methods to check everything is sane
        assert f.environment() is staticPyFilter
        assert len(f.onSuggestDynamicPorts()[0]) == 0
        assert len(f.onSuggestDynamicPorts()[1]) == 0

        origCallbacks = dict(onInit=f.onInit, onOpen=f.onOpen, onStart=f.onStart, onStop=f.onStop, onClose=f.onClose,
                             onDeinit=f.onDeinit, onPortDataChanged=f.onPortDataChanged)
        for callback in origCallbacks:
            setattr(f, callback,
                    lambda *args, callback=callback: function_calls.append((callback, origCallbacks[callback](*args))))

        def exceptionCallback(*args):
            raise RuntimeError()

        assert staticPyFilter.getDynamicInputPorts() == []
        assert staticPyFilter.getDynamicOutputPorts() == []
        sip = staticPyFilter.getStaticInputPorts()
        assert len(sip) == 1
        assert sip[0].name() == "inPort"
        assert sip[0] is staticPyFilter.getInputPort("inPort")
        sop = staticPyFilter.getStaticOutputPorts()
        assert len(sop) == 1
        assert sop[0].name() == "outPort"
        assert sop[0] is staticPyFilter.getOutputPort("outPort")
        expect_exception(staticPyFilter.addPort, InputPort(True, "dynOutPort", staticPyFilter))
        expect_exception(staticPyFilter.addPort, OutputPort(True, "dynOutPort", staticPyFilter))
        assert staticPyFilter.state() == FilterState.CONSTRUCTED

        assert len(function_calls) == 0
        expect_exception(staticPyFilter.start)
        expect_exception(staticPyFilter.open)
        expect_exception(staticPyFilter.stop)
        expect_exception(staticPyFilter.close)
        expect_exception(staticPyFilter.deinit)
        staticPyFilter.init()
        assert function_calls == [("onInit", None)]
        assert staticPyFilter.state() == FilterState.INITIALIZED
        function_calls.clear()

        expect_exception(staticPyFilter.init)
        expect_exception(staticPyFilter.stop)
        expect_exception(staticPyFilter.start)
        expect_exception(staticPyFilter.close)
        staticPyFilter.open()
        assert function_calls == [("onOpen", None)]
        assert staticPyFilter.state() == FilterState.OPENED
        function_calls.clear()

        expect_exception(staticPyFilter.init)
        expect_exception(staticPyFilter.open)
        expect_exception(staticPyFilter.stop)
        expect_exception(staticPyFilter.deinit)
        staticPyFilter.start()
        assert function_calls == [("onStart", None)]
        assert staticPyFilter.state() == FilterState.ACTIVE
        function_calls.clear()

        assert len(function_calls) == 0
        expect_exception(staticPyFilter.init)
        expect_exception(staticPyFilter.open)
        expect_exception(staticPyFilter.start)
        expect_exception(staticPyFilter.close)
        expect_exception(staticPyFilter.deinit)
        staticPyFilter.stop()
        assert function_calls == [("onStop", None)]
        assert staticPyFilter.state() == FilterState.OPENED
        function_calls.clear()

        assert len(function_calls) == 0
        expect_exception(staticPyFilter.init)
        expect_exception(staticPyFilter.open)
        expect_exception(staticPyFilter.stop)
        expect_exception(staticPyFilter.deinit)
        staticPyFilter.close()
        assert function_calls == [("onClose", None)]
        assert staticPyFilter.state() == FilterState.INITIALIZED
        function_calls.clear()

        assert len(function_calls) == 0
        staticPyFilter.deinit()
        assert function_calls == [("onDeinit", None)]
        assert staticPyFilter.state() == FilterState.CONSTRUCTED
        function_calls.clear()

        # check exception call backs
        f.onInit = exceptionCallback
        staticPyFilter.init()
        assert staticPyFilter.state() == FilterState.INITIALIZED
        staticPyFilter.deinit()
        function_calls.clear()

    # check auto cleanup functionality
    with FilterEnvironment("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter",
                           PropertyCollectionImpl("root", None) ) as staticPyFilter:
        f = staticPyFilter.getPlugin()
        origCallbacks = dict(onInit=f.onInit, onOpen=f.onOpen, onStart=f.onStart, onStop=f.onStop, onClose=f.onClose,
                             onDeinit=f.onDeinit, onPortDataChanged=f.onPortDataChanged)
        for callback in origCallbacks:
            setattr(f, callback,
                    lambda *args, callback=callback: function_calls.append((callback, origCallbacks[callback](*args))))

    assert len(function_calls) == 0

    with FilterEnvironment("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter",
                           PropertyCollectionImpl("root", None) ) as staticPyFilter:
        f = staticPyFilter.getPlugin()
        origCallbacks = dict(onInit=f.onInit, onOpen=f.onOpen, onStart=f.onStart, onStop=f.onStop, onClose=f.onClose,
                             onDeinit=f.onDeinit, onPortDataChanged=f.onPortDataChanged)
        for callback in origCallbacks:
            setattr(f, callback,
                    lambda *args, callback=callback: function_calls.append((callback, origCallbacks[callback](*args))))
        staticPyFilter.init()

    assert function_calls == [("onInit", None), ("onDeinit", None)]
    function_calls.clear()

    with FilterEnvironment("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleStaticFilter.py", "SimpleStaticFilter",
                           PropertyCollectionImpl("root", None) ) as staticPyFilter:
        f = staticPyFilter.getPlugin()
        origCallbacks = dict(onInit=f.onInit, onStart=f.onStart, onOpen=f.onOpen, onStop=f.onStop, onClose=f.onClose,
                             onDeinit=f.onDeinit, onPortDataChanged=f.onPortDataChanged)
        for callback in origCallbacks:
            setattr(f, callback,
                    lambda *args, callback=callback: function_calls.append((callback, origCallbacks[callback](*args))))
        staticPyFilter.init()
        staticPyFilter.open()
        staticPyFilter.start()

    assert function_calls == [("onInit", None), ("onOpen", None), ("onStart", None),
                              ("onStop", None), ("onClose", None), ("onDeinit", None)]
    function_calls.clear()

    expect_exception(FilterEnvironment, "weird.plugin.extension", "factory", PropertyCollectionImpl("root", None) )

def test_dynamic_in_filter():
    with FilterEnvironment("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleDynamicFilter.py", "SimpleDynInFilter",
                           PropertyCollectionImpl("root", None) ) as dynInPyFilter:
        f = dynInPyFilter.getPlugin()

        dip = InputPort(True, "dynInPort", dynInPyFilter)
        dynInPyFilter.addPort(dip)
        expect_exception(dynInPyFilter.addPort, dip)
        dop = OutputPort(True, "dynOutPort", dynInPyFilter)
        expect_exception(dynInPyFilter.addPort, dop)

        if useCImpl:
            assert [p.data() for p in dynInPyFilter.getDynamicInputPorts()] == [dip.data()]
        else:
            assert dynInPyFilter.getDynamicInputPorts() == [dip]
        assert dynInPyFilter.getDynamicOutputPorts() == []
        sip = dynInPyFilter.getStaticInputPorts()
        assert len(sip) == 0
        sop = dynInPyFilter.getStaticOutputPorts()
        assert len(sop) == 1
        assert sop[0].name() == "outPort"
        assert sop[0] is dynInPyFilter.getOutputPort("outPort")
        assert dynInPyFilter.state() == FilterState.CONSTRUCTED

        dynInPyFilter.init()
        dip2 = InputPort(True, "dynInPort2", dynInPyFilter)
        expect_exception(dynInPyFilter.addPort, dip2)

        dynInPyFilter.open()
        expect_exception(dynInPyFilter.addPort, dip2)

def test_dynamic_out_filter():
    with FilterEnvironment("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleDynamicFilter.py", "SimpleDynOutFilter",
                           PropertyCollectionImpl("root", None) ) as dynOutPyFilter:
        f = dynOutPyFilter.getPlugin()

        dip = InputPort(True, "dynInPort", dynOutPyFilter)
        expect_exception(dynOutPyFilter.addPort, dip)
        dop = OutputPort(True, "dynOutPort", dynOutPyFilter)
        dynOutPyFilter.addPort(dop)
        expect_exception(dynOutPyFilter.addPort, dop)

        assert dynOutPyFilter.getDynamicInputPorts() == []
        if useCImpl:
            assert [p.data() for p in dynOutPyFilter.getDynamicOutputPorts()] == [dop.data()]
        else:
            assert dynOutPyFilter.getDynamicOutputPorts() == [dop]
        sip = dynOutPyFilter.getStaticInputPorts()
        assert len(sip) == 1
        assert sip[0].name() == "inPort"
        assert sip[0] is dynOutPyFilter.getInputPort("inPort")
        sop = dynOutPyFilter.getStaticOutputPorts()
        assert len(sop) == 1
        assert sop[0].name() == "outPort"
        assert sop[0] is dynOutPyFilter.getOutputPort("outPort")
        assert dynOutPyFilter.state() == FilterState.CONSTRUCTED

        dynOutPyFilter.init()
        dop2 = OutputPort(True, "dynOutPort2", dynOutPyFilter)
        expect_exception(dynOutPyFilter.addPort, dop2)

        dynOutPyFilter.open()
        expect_exception(dynOutPyFilter.addPort, dop2)

if __name__ == "__main__":
    test_static_filter()
    #test_dynamic_in_filter()
    #test_dynamic_out_filter()
