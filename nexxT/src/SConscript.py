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

env.Append(CPPPATH=[".",
                    purelib.abspath + "/shiboken2_generator/include",
                    purelib.abspath + "/PySide2/include/QtCore",
                    purelib.abspath + "/PySide2/include",
                    include.abspath,
                    platinclude.abspath,
                    ],
           LIBPATH=[".",
                    sysconfig.get_paths()['stdlib'],
                    sysconfig.get_paths()['platstdlib'],
                    sysconfig.get_config_vars()['installed_platbase'] + "/libs",
                    sysconfig.get_paths()['purelib'] + "/shiboken2",
                    sysconfig.get_paths()['purelib'] + "/PySide2",
                    ]
           )

if "linux" in env["target_platform"]:
    env["SHIBOKEN_INCFLAGS"] = ":".join(env["CPPPATH"])
    env.Append( LINKFLAGS = Split('-z origin') )
    env.Append( RPATH = env.Literal('\\$$ORIGIN'))
else:
    env["SHIBOKEN_INCFLAGS"] = ";".join(env["CPPPATH"])

nexxT_headers = env.RegisterSources(
    [srcDir.File("NexxTLinkage.hpp"),
     srcDir.File("DataSamples.hpp"),
     srcDir.File("Filters.hpp"),
     ])
apilib = env.SharedLibrary("nexxT", env.RegisterSources(Split("""
    DataSamples.cpp 
    FilterEnvironment.cpp
    Filters.cpp
    Logger.cpp
    Ports.cpp
    Services.cpp
    PropertyCollection.cpp
    NexxTPlugins.cpp
""")), CPPDEFINES=["NEXXT_LIBRARY_COMPILATION"])
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
targets += [spath.Dir("cnexxT").File("qsharedpointer_datasample_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("qsharedpointer_filter_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("qsharedpointer_port_wrapper.cpp")]
targets += [spath.Dir("cnexxT").File("qsharedpointer_qobject_wrapper.cpp")]

env = env.Clone()
env.Append(LIBS=["nexxT"])
if "linux" in env["target_platform"]:
    # the : notation is for the linker and enables to use lib names which are not
    # ending with .so
    env.Append(LIBS=[":libpyside2.abi3.so.$QT5VERSION",":libshiboken2.abi3.so.$QT5VERSION"])
else:
    env.Append(LIBS=["shiboken2.abi3", "pyside2.abi3"])

if "manylinux" in env["target_platform"]:
    # we are on a manylinux* platform which doesn't have llvm in required versions
    dummy = []
    env.Append(CPPPATH=Dir("#/build/linux_x86_64_release/nexxT/src/cnexxT-shiboken/cnexxT"))
    for t in targets:
        source = Dir("#/build/linux_x86_64_release/nexxT/src/cnexxT-shiboken/cnexxT").File(os.path.basename(str(t)))
        dummy.extend(env.InstallAs(t, source))
else:
    dummy = env.Command(targets, env.RegisterSources(Split("cnexxT.h cnexxT.xml")),
                        [
                            Delete("$SPATH"),
                            sysconfig.get_paths()["scripts"] + "/shiboken2 --generator-set=shiboken --avoid-protected-hack --output-directory=${SPATH} "
                            "--language-level=c++14 --include-paths=$SHIBOKEN_INCFLAGS --enable-pyside-extensions "
                            "--typesystem-paths=%(purelib)s/PySide2/typesystems $SOURCES" % sysconfig.get_paths(),
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
    env.RegisterTargets(env.Install(srcDir.Dir("..").Dir("include").abspath, Glob(srcDir.abspath + "/*.hpp")))
    qrcsrc = srcDir.File('../../workspace/resources/nexxT.qrc')
    rccout = env.Qrc5('qrc_resources.py', qrcsrc.abspath, QT5_QRCFLAGS=Split("-g python"))
    iout = env.Install(srcDir.Dir("..").Dir("core").abspath, rccout)
    env.RegisterTargets(iout)
