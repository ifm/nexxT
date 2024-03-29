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
    import cnexxT # pylint: disable=import-error
    # constants here are really classes
    # pylint: disable=invalid-name
    cnexxT = cnexxT.nexxT
    Filter = cnexxT.Filter
    FilterState = cnexxT.FilterState

    def DataSample(*args, **kw):
        """
        DataSample factory function (create a shared pointer to a new DataSample instance)
        """
        return cnexxT.DataSample.make_shared(cnexxT.DataSample(*args, **kw))
    #DataSample = lambda *args, **kw: cnexxT.DataSample.make_shared(cnexxT.DataSample(*args, **kw))

    DataSample.TIMESTAMP_RES = cnexxT.DataSample.TIMESTAMP_RES
    DataSample.copy = cnexxT.DataSample.copy
    DataSample.currentTime = cnexxT.DataSample.currentTime
    cnexxT.DataSample.registerMetaType()
    cnexxT.DataSample.registerMetaType()
    Port = cnexxT.Port
    OutputPortInterface = cnexxT.OutputPortInterface
    InputPortInterface = cnexxT.InputPortInterface
    PropertyCollection = cnexxT.PropertyCollection
    PropertyHandler = cnexxT.PropertyHandler
    Services = cnexxT.Services

    def OutputPort(*args, **kw):
        """
        OutputPort factory function (create a shared pointer to a new OutputPortInterface instance)
        """
        return Port.make_shared(OutputPortInterface(*args, **kw))
    #OutputPort = lambda *args, **kw: Port.make_shared(OutputPortInterface(*args, **kw))

    def InputPort(dynamic, name, environment, queueSizeSamples=1, queueSizeSeconds=-1):
        """
        InputPort factory function (create a shared pointer to a new InputPortInterface instance)
        """
        return Port.make_shared(InputPortInterface(dynamic, name, environment, queueSizeSamples, queueSizeSeconds))
    #InputPort = (lambda dynamic, name, environment, queueSizeSamples=1, queueSizeSeconds=-1:
    #        Port.make_shared(InputPortInterface(dynamic, name, environment, queueSizeSamples, queueSizeSeconds)))

    from nexxT.interface.Filters import FilterSurrogate
else:
    # pylint: enable=invalid-name
    from nexxT.interface.Ports import Port
    from nexxT.interface.Ports import OutputPortInterface
    from nexxT.interface.Ports import InputPortInterface
    # make sure that PortImpl is actually imported to correctly set up the factory functions
    from nexxT.core import PortImpl
    OutputPort = PortImpl.OutputPortImpl
    InputPort = PortImpl.InputPortImpl
    OutputPortInterface.setupDirectConnection = OutputPort.setupDirectConnection
    OutputPortInterface.setupInterThreadConnection = OutputPort.setupInterThreadConnection
    del PortImpl
    from nexxT.interface.Filters import Filter, FilterState, FilterSurrogate
    from nexxT.interface.DataSamples import DataSample
    from nexxT.interface.PropertyCollections import PropertyCollection, PropertyHandler
    from nexxT.interface.Services import Services

__all__ = ["Services", "PropertyCollection", "PropertyHandler", "DataSample",
           "Filter", "FilterState", "FilterSurrogate",
           "Port", "InputPort", "OutputPort", "OutputPortInterface", "InputPortInterface"]

del nexxT
