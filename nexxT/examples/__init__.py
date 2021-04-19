# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
define FilterSurrogates for binary filters.
"""

from pathlib import Path
import os
from nexxT.interface import FilterSurrogate
if os.environ.get("READTHEDOCS", None) is None:
    from PySide2 import QtMultimedia # needed to load corresponding DLL before loading the nexxT plugin

AviReader = FilterSurrogate(
    "binary://" + str((Path(__file__).parent.parent / "tests" /
                       "binary" / "${NEXXT_PLATFORM}" / "${NEXXT_VARIANT}" / "test_plugins").absolute()),
    "VideoPlaybackDevice"
)
"""
Filter surrogate for the VideoPlaybackDevice class which is defined in a packaged shared object "test_plugins".
"""

CameraGrabber = FilterSurrogate(
    "binary://" + str((Path(__file__).parent.parent / "tests" /
                       "binary" / "${NEXXT_PLATFORM}" / "${NEXXT_VARIANT}" / "test_plugins").absolute()),
    "CameraGrabber"
)
"""
Filter surrogate for the CameraGrabber class which is defined in a packaged shared object "test_plugins".
"""
