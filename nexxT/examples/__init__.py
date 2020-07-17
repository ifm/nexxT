# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from pathlib import Path
from PySide2 import QtMultimedia # needed to load corresponding DLL before loading the nexxT plugin
from nexxT.interface import FilterSurrogate

AviReader = FilterSurrogate(
    "binary://" + str((Path(__file__).parent.parent / "tests" /
                       "binary" / "${NEXXT_PLATFORM}" / "${NEXXT_VARIANT}" / "test_plugins").absolute()),
    "VideoPlaybackDevice"
)
