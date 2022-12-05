# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import sysconfig
import platform
import os

Import("env")

env = env.Clone()

srcDir = Dir(".").srcnode()
purelib = Dir(sysconfig.get_paths()['purelib'])
include = Dir(sysconfig.get_paths()['include'])
platinclude = Dir(sysconfig.get_paths()['platinclude'])

if os.environ.get("PYSIDEVERSION", "6") in "52":
    ver=2
    standard="c++14"
elif os.environ.get("PYSIDEVERSION", "6") == "6":
    ver=6
    standard="c++17"
else:
    raise RuntimeError("invalid env variable PYSIDEVERSION=%s" % os.environ["PYSIDEVERSION"])

env.Append(CPPPATH=[".",
                    str(srcDir.Dir("..").Dir("include")),
                    purelib.abspath + "/shiboken%d_generator/include" % ver,
                    purelib.abspath + "/PySide%d/include/QtCore" % ver,
                    # TODO: the following 2 lines can be removed after this bug has been
                    #       fixed: https://bugreports.qt.io/browse/PYSIDE-1627
                    purelib.abspath + "/PySide%d/include/QtWidgets" % ver,
                    purelib.abspath + "/PySide%d/include/QtGui" % ver,
                    purelib.abspath + "/PySide%d/include" % ver,
                    include.abspath,
                    platinclude.abspath,
                    ],
           LIBPATH=[".",
                    sysconfig.get_paths()['stdlib'],
                    sysconfig.get_paths()['platstdlib'],
                    sysconfig.get_config_vars()['installed_platbase'] + "/libs",
                    sysconfig.get_paths()['purelib'] + "/shiboken%d" % ver,
                    sysconfig.get_paths()['purelib'] + "/PySide%d" % ver,
                    ]
           )

if "linux" in env["target_platform"]:
    env["SHIBOKEN_INCFLAGS"] = ":".join(env["CPPPATH"])
    env.Append( LINKFLAGS = Split('-z origin') )
    env.Append( RPATH = env.Literal('\\$$ORIGIN'))
else:
    env["SHIBOKEN_INCFLAGS"] = ";".join(env["CPPPATH"])

# we have to manually moc because of seperation of headers and sources
moced = [
    env.Moc6(os.path.basename(h) + ".cpp", srcDir.File(h))
        for h in Split("""
            ../include/nexxT/FilterEnvironment.hpp
            ../include/nexxT/Filters.hpp
            ../include/nexxT/InputPortInterface.hpp
            ../include/nexxT/OutputPortInterface.hpp
            ../include/nexxT/Ports.hpp
            ../include/nexxT/Ports.hpp
            ../include/nexxT/PropertyCollection.hpp
        """)
]

apilib = env.SharedLibrary("nexxT", env.RegisterSources(
    Split("""
        DataSamples.cpp 
        FilterEnvironment.cpp
        Filters.cpp
        Logger.cpp
        Ports.cpp
        InputPortInterface.cpp
        OutputPortInterface.cpp
        Services.cpp
        PropertyCollection.cpp
        NexxTPlugins.cpp
        Compatibility.cpp
    """)) + moced
    , CPPDEFINES=["NEXXT_LIBRARY_COMPILATION"])
env.RegisterTargets(apilib)

spath = Dir("./cnexxT-shiboken")
targets = []
targets += [spath.Dir("cnexxT").File("cnexxt_module_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_datasample_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_port_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_interthreadconnection_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_outputportinterface_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_inputportinterface_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_services_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_filterstate_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_filter_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_propertycollection_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_propertyhandler_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_basefilterenvironment_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_plugininterface_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_logging_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("nexxt_compatibility_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("qsharedpointer_datasample_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("qsharedpointer_filter_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("qsharedpointer_port_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("qsharedpointer_qobject_wrapper.cpp")]


env = env.Clone()
env.Append(LIBS=["nexxT"])
if os.environ.get("PYSIDEVERSION", "6") == "6":
    if "linux" in env["target_platform"]:
        # the : notation is for the linker and enables to use lib names which are not
        # ending with .so
        qt6vend = ".".join(env.subst("$QT6VERSION").split(".")[:2])

        env.Append(LIBS=[":libpyside6.abi3.so." + qt6vend,":libshiboken6.abi3.so." + qt6vend])
    else:
        env.Append(LIBS=["shiboken6.abi3", "pyside6.abi3"])
else:
    raise RuntimeError("invalid env variable PYSIDEVERSION=%s" % os.environ["PYSIDEVERSION"])

if "manylinux" in env["target_platform"]:
    # we are on a manylinux* platform which doesn't have llvm in required versions
    dummy = []
    env.Append(CPPPATH=Dir("#/build/linux_x86_64_release/nexxT/src/cnexxT-shiboken/cnexxT"))
    for t in targets:
        source = Dir("#/build/linux_x86_64_release/nexxT/src/cnexxT-shiboken/cnexxT").File(os.path.basename(str(t)))
        dummy.extend(env.InstallAs(t, source))
else:
    d = {"ver": ver, "standard": standard}
    d.update(sysconfig.get_paths())
    dummy = env.Command(targets, env.RegisterSources(Split("cnexxT.h cnexxT.xml")),
                        [
                            Delete("$SPATH"),
                            sysconfig.get_paths()["scripts"] + "/shiboken%(ver)d --generator-set=shiboken --avoid-protected-hack --output-directory=${SPATH} "
                            "--language-level=%(standard)s --include-paths=$SHIBOKEN_INCFLAGS --enable-pyside-extensions "
                            "--typesystem-paths=%(purelib)s/PySide%(ver)d/typesystems $SOURCES" % d,
                        ], SPATH=spath)

pyext = env.SharedLibrary("cnexxT", dummy,
                          SHLIBPREFIX=sysconfig.get_config_var("EXT_PREFIX"),
                          SHLIBSUFFIX=sysconfig.get_config_var("EXT_SUFFIX") if platform.system() == "Windows" else ".abi3.so",
                          no_import_lib=True)
env.RegisterTargets(pyext)
Depends(dummy, apilib)

# install python extension and library files into project directory
env.RegisterTargets(env.Install(srcDir.Dir("..").Dir("binary").Dir(env.subst("$deploy_platform")).Dir(env.subst("$variant")).abspath, pyext+apilib))
if env["variant"] == "release":
    qrcsrc = srcDir.File('../../workspace/resources/nexxT.qrc')
    if os.environ.get("PYSIDEVERSION", "6") in "52":
        rccout = env.Qrc5('qrc_resources.py', qrcsrc.abspath, QT5_QRCFLAGS=Split("-g python"))
    elif os.environ.get("PYSIDEVERSION", "6") == "6":
        rccout = env.Qrc6('qrc_resources.py', qrcsrc.abspath, QT6_QRCFLAGS=Split("-g python"))
    else:
        raise RuntimeError("invalid env variable PYSIDEVERSION=%s" % os.environ["PYSIDEVERSION"])
    iout = env.Install(srcDir.Dir("..").Dir("core").abspath, rccout)
    env.RegisterTargets(iout)
