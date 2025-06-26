# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import pkg_resources
import pytest
from nexxT.Qt.QtCore import QCoreApplication
from nexxT.core.FilterEnvironment import FilterEnvironment
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.Configuration import Configuration
from nexxT.core.PluginManager import PluginManager
import nexxT

cfilters = set(["examples.videoplayback.AviReader",
                "examples.framework.CameraGrabber",
                "tests.nexxT.CSimpleSource",
                "tests.nexxT.CTestExceptionFilter",
                "tests.nexxT.CPropertyReceiver"])

blacklist = set([])

def setup():
    import nexxT
    from nexxT.services.ConsoleLogger import ConsoleLogger
    nexxT.changeLoggers()
    ConsoleLogger.installCrashHandlers(force=True)
    global app
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication()

@pytest.mark.parametrize("ep",
    [pytest.param(e.name,
     marks=[pytest.mark.skipif(not nexxT.useCImpl and e.name in cfilters, reason="testing a pure python variant"),
            pytest.mark.skipif(e.name in blacklist, reason="testing blacklisted filter")
           ]
    ) for e in pkg_resources.iter_entry_points("nexxT.filters")])
def test_EntryPoint(ep):
    cfg = Configuration()
    env = FilterEnvironment("entry_point://" + ep, "entry_point", cfg._defaultRootPropColl())
    PluginManager.singleton().unloadAll()

if __name__ == "__main__":
    test_EntryPoint('examples.videoplayback.AviReader')
    test_EntryPoint('tests.nexxT.PySimpleSource')
