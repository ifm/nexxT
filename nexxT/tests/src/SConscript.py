# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import os

Import("env")

env = env.Clone()
if os.environ.get("PYSIDEVERSION", "6") in "52":
    env.EnableQt5Modules(['QtCore', "QtMultimedia", "QtGui"])
    srcDir = Dir(".").srcnode()

    env.Append(CPPPATH=["../../src", "."],
               LIBPATH=["../../src"],
               LIBS=["nexxT"])

    plugin = env.SharedLibrary("test_plugins", env.RegisterSources(Split("""
        SimpleSource.cpp
        AviFilePlayback.cpp
        TestExceptionFilter.cpp
        Plugins.cpp
        CameraGrabber.cpp
        VideoGrabber.cpp
    """)))
    env.RegisterTargets(plugin)
elif os.environ.get("PYSIDEVERSION", "6") == "6":
    env.EnableQt6Modules(['QtCore', "QtGui", "QtMultimedia"])
    srcDir = Dir(".").srcnode()

    env.Append(CPPPATH=[srcDir.Dir("../../include"), "."],
               LIBPATH=["../../src"],
               LIBS=["nexxT"])

    plugin = env.SharedLibrary("test_plugins", env.RegisterSources(Split("""
        SimpleSource.cpp
        AviFilePlayback.cpp
        TestExceptionFilter.cpp
        Plugins.cpp
        VideoGrabber.cpp
        CameraGrabber.cpp
    """)))
    env.RegisterTargets(plugin)
else:
    raise RuntimeError("invalid env variable PYSIDEVERSION=%s" % os.environ["PYSIDEVERSION"])

installed = env.Install(srcDir.Dir("..").Dir("binary").Dir(env.subst("$deploy_platform")).Dir(env.subst("$variant")).abspath, plugin)
env.RegisterTargets(installed)
