# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

from pathlib import Path
from nexxT.interface import FilterSurrogate
import nexxT.Qt.QtMultimedia

CSimpleSource = FilterSurrogate(
    "binary://" + str((Path(__file__).parent /
                       "binary" / "${NEXXT_PLATFORM}" / "${NEXXT_VARIANT}" / "test_plugins").absolute()),
    "SimpleSource"
)

CTestExceptionFilter = FilterSurrogate(
    "binary://" + str((Path(__file__).parent /
                       "binary" / "${NEXXT_PLATFORM}" / "${NEXXT_VARIANT}" / "test_plugins").absolute()),
    "TestExceptionFilter"
)

PropertyReceiver = FilterSurrogate(
    "binary://" + str((Path(__file__).parent /
                       "binary" / "${NEXXT_PLATFORM}" / "${NEXXT_VARIANT}" / "test_plugins").absolute()),
    "PropertyReceiver"
)