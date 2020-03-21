# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This __init__.py generates shortcuts for exported classes
"""

import nexxT
if nexxT.useCImpl:
    import cnexxT
    # constants here are really classes
    # pylint: disable=invalid-name
    cnexxT = cnexxT.nexxT
    Filter = cnexxT.Filter
    FilterState = cnexxT.FilterState
    DataSample = lambda *args, **kw: cnexxT.DataSample.make_shared(cnexxT.DataSample(*args, **kw))
    DataSample.TIMESTAMP_RES = cnexxT.DataSample.TIMESTAMP_RES
    DataSample.copy = cnexxT.DataSample.copy
    cnexxT.DataSample.registerMetaType()
    cnexxT.DataSample.registerMetaType()
    Port = cnexxT.Port
    OutputPortInterface = cnexxT.OutputPortInterface
    InputPortInterface = cnexxT.InputPortInterface
    PropertyCollection = cnexxT.PropertyCollection
    Services = cnexxT.Services
    OutputPort = lambda *args, **kw: Port.make_shared(OutputPortInterface(*args, **kw))
    InputPort = (lambda dynamic, name, environment, queueSizeSamples=1, queueSizeSeconds=-1:
                 Port.make_shared(InputPortInterface(dynamic, name, environment, queueSizeSamples, queueSizeSeconds)))
else:
    # pylint: enable=invalid-name
    from nexxT.interface.Filters import Filter, FilterState
    from nexxT.interface.DataSamples import DataSample
    from nexxT.interface.Ports import Port
    from nexxT.interface.Ports import OutputPortInterface
    from nexxT.interface.Ports import InputPortInterface
    from nexxT.interface.PropertyCollections import PropertyCollection
    from nexxT.interface.Services import Services
    # make sure that PortImpl is actually imported to correctly set up the factory functions
    from nexxT.core import PortImpl
    OutputPort = PortImpl.OutputPortImpl
    InputPort = PortImpl.InputPortImpl
    OutputPortInterface.setupDirectConnection = OutputPort.setupDirectConnection
    OutputPortInterface.setupInterThreadConnection = OutputPort.setupInterThreadConnection
    del PortImpl
del nexxT
