# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import sysconfig

Import("env")

env = env.Clone()
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

installed = env.Install(srcDir.Dir("..").Dir("binary").Dir(env.subst("$deploy_platform")).Dir(env.subst("$variant")).abspath, plugin)
env.RegisterTargets(installed)
