# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from nexxT.interface import InputPortInterface, Services
from nexxT.core.FilterMockup import FilterMockup
from nexxT.core.PropertyCollectionImpl import PropertyCollectionImpl
import os

def test_smoke():
    # most of this is already tested in testGraph
    Services.addService("Profiling", None)
    mockup = FilterMockup("pyfile://" + os.path.dirname(__file__) + "/../interface/SimpleDynamicFilter.py",
                          "SimpleDynInFilter", PropertyCollectionImpl("mockup", None), None)
    mockup.createFilterAndUpdate()
    mockup.addDynamicPort("dynin", InputPortInterface)
    res = mockup.createFilter()


if __name__ == "__main__":
    test_smoke()