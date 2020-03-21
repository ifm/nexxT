# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import sysconfig

Import("env")

env = env.Clone()
env.EnableQt5Modules(['QtCore', "QtMultimedia", "QtGui"])

env.Append(CPPPATH=["../../src", "."],
           LIBPATH=["../../src"],
           LIBS=["nexxT"])

env['QT5_DEBUG'] = 1

plugin = env.RegisterTargets(env.SharedLibrary("test_plugins", env.RegisterSources(Split("""
    SimpleSource.cpp
    AviFilePlayback.cpp
    TestExceptionFilter.cpp
    Plugins.cpp
"""))))
