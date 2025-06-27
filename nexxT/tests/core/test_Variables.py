import math
from nexxT.Qt.QtCore import QCoreApplication
from nexxT.core.Variables import Variables

def setup():
    import nexxT
    from nexxT.services.ConsoleLogger import ConsoleLogger
    nexxT.changeLoggers()
    ConsoleLogger.installCrashHandlers(force=True)
    global app
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication()

def test_standardSubstitution():
    v = Variables()
    v["var1"] = "Hello World"
    v["var2"] = "$var1"
    v["var3"] = "$var3"
    v["var4"] = "${!importlib.import_module('math').exp(1)}"
    v["var5"] = "${!subst('$var1')}"
    v["var6"] = "${!xxx}"
    # unfortunately this is not directly possible due to the usage of string.Template.
    # you need a seperate variable defining only the python code, like var4
    v["var7"] = "exp(1) is ${!importlib.import_module('math').exp(1)}"

    assert v.subst("var1 is '$var1'") == "var1 is 'Hello World'"
    assert v.subst("var2 is '$var2'") == "var2 is 'Hello World'"
    try:
        v.subst("var3 is '$var3'")
        assert False
    except RecursionError:
        assert True
    assert v.subst("var4 is '$var4'") == f"var4 is '{math.exp(1)}'"
    assert v.subst("var5 is '$var5'") == f"var5 is 'Hello World'"
    assert v.subst("var1 is '${var1}'") == f"var1 is 'Hello World'"
    v.subst("var6 is '$var6'") == "var6 is '<NameError: name 'xxx' is not defined>'"
    assert v.subst("var7 is '$var7'") == "var7 is 'exp(1) is ${!importlib.import_module('math').exp(1)}'"

def test_treeStructure():
    root = Variables()
    child1 = Variables(root)
    child2 = Variables(root)
    grandchild = Variables(child1)
    
    root["id"] = "root"
    root["root"] = "$id"
    root["python"] = "${!subst('$id')}"
    root["python_nonexist"] = "${!subst('$child1')}"
    child1["id"] = "child1"
    child1["child1"] = "$id"
    child2["id"] = "child2"
    child2["child2"] = "$id"
    grandchild["id"] = "grandchild"
    grandchild["grandchild"] = "$id"
    
    assert root.subst("$id") == "root"
    assert child1.subst("$id") == "child1"
    assert child2.subst("$id") == "child2"
    assert grandchild.subst("$id") == "grandchild"

    assert root.subst("$python_nonexist") == "$child1"
    assert child1.subst("$python_nonexist") == "$child1"
    assert child2.subst("$python_nonexist") == "$child1"
    assert grandchild.subst("$python_nonexist") == "$child1"

    assert root.subst("$python") == "root"
    assert child1.subst("$python") == "root"
    assert child2.subst("$python") == "root"
    assert grandchild.subst("$python") == "root"

    assert child1.subst("$root") == "root"
    assert child1.subst("$child1") == "child1"
    assert child1.subst("$child2") == "$child2"
    assert child1.subst("$grandchild") == "$grandchild"

    assert child2.subst("$root") == "root"
    assert child2.subst("$child1") == "$child1"
    assert child2.subst("$child2") == "child2"
    assert child2.subst("$grandchild") == "$grandchild"

    assert grandchild.subst("$root") == "root"
    assert grandchild.subst("$child1") == "child1"
    assert grandchild.subst("$child2") == "$child2"
    assert grandchild.subst("$grandchild") == "grandchild"

