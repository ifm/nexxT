# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This __init__.py handles c++ parts of the core (if enabled)
"""

import nexxT
# constants here are really classes
# pylint: disable=invalid-name
if nexxT.useCImpl:
    import cnexxT
    PluginInterface = cnexxT.nexxT.PluginInterface
else:
    PluginInterface = None
    