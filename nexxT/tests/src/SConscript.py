# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import os

Import("env")

env = env.Clone()
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
    Properties.cpp
""")))
env.RegisterTargets(plugin)

installed = env.Install(srcDir.Dir("..").Dir("binary").Dir(env.subst("$deploy_platform")).Dir(env.subst("$variant")).abspath, plugin)
env.RegisterTargets(installed)
