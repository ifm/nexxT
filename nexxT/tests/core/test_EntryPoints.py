# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import pkg_resources
import pytest
from nexxT.core.FilterEnvironment import FilterEnvironment
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
from nexxT.core.PluginManager import PluginManager
import nexxT

cfilters = set(["examples.videoplayback.AviReader",
                "examples.framework.CameraGrabber",
                "tests.nexxT.CSimpleSource",
                "tests.nexxT.CTestExceptionFilter"])

@pytest.mark.parametrize("ep",
                         [pytest.param(e.name, marks=pytest.mark.skipif(not nexxT.useCImpl and e.name in cfilters,
                                                                        reason="testing a pure python variant"))
                            for e in pkg_resources.iter_entry_points("nexxT.filters")])
def test_EntryPoint(ep):
    env = FilterEnvironment("entry_point://" + ep, "entry_point", PropertyCollectionImpl('propColl', None))
    PluginManager.singleton().unloadAll()

if __name__ == "__main__":
    test_EntryPoint('examples.videoplayback.AviReader')
    test_EntryPoint('tests.nexxT.PySimpleSource')
