# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the CompositeFilter class
"""

import logging
from nexxT.interface import Filter, OutputPort, InputPort
from nexxT.core.SubConfiguration import SubConfiguration
from nexxT.core.Exceptions import NexTRuntimeError, NexTInternalError

logger = logging.getLogger(__name__)

class CompositeFilter(SubConfiguration):
    """
    This class handles a sub-configuration of a nexxT application. Sub configs are either applications or
    SubGraphs (which behave like a filter).
    """

    class CompositeInputNode(Filter):
        """
        This filter acts as a dummy filter inside the composite subgraph; because it represents
        the input to the subgraph, it uses dynamic output ports
        """
        def __init__(self, env):
            Filter.__init__(self, False, True, env)

    class CompositeOutputNode(Filter):
        """
        This filter acts as a dummy filter inside the composite subgraph; because it represents
        the output of the subgraph, it uses dynamic input ports
        """
        def __init__(self, env):
            Filter.__init__(self, True, False, env)

    class CompositeNode(Filter):
        """
        This class is used to represent a composite subgraph in a filter graph.
        """
        def __init__(self, env, envCInput, envCOutput, parent):
            Filter.__init__(self, False, False, env)
            self._parent = parent
            for src in envCInput.getDynamicOutputPorts():
                dest = InputPort(False, src.name(), env)
                self.addStaticPort(dest)
            for src in envCOutput.getDynamicInputPorts():
                dest = OutputPort(False, src.name(), env)
                self.addStaticPort(dest)

        def getGraph(self):
            """
            Returns the filter graph implementing this composite node (child filter graph)
            :return: a FilterGraph instance
            """
            return self._parent.getGraph()

        def getCompositeName(self):
            """
            Returns the type name of this composite filter (this is the same for all instances of a composite filter)
            :return: a string
            """
            return self._parent.getName()

    def __init__(self, name, configuration):
        super().__init__(name, configuration)
        self._configuration = configuration
        _compositeInputNode = self._graph.addNode(CompositeFilter, "CompositeInputNode", "CompositeInput")
        _compositeOutputNode = self._graph.addNode(CompositeFilter, "CompositeOutputNode", "CompositeOutput")
        if _compositeInputNode != "CompositeInput" or _compositeOutputNode != "CompositeOutput":
            raise NexTInternalError("unexpected node names.")
        # prevent renaming and deletion of these special nodes
        self._graph.protect("CompositeInput")
        self._graph.protect("CompositeOutput")
        configuration.addComposite(self)

    def compositeNode(self, env):
        """
        Factory function for creating a dummy filter instance (this one will never get active).
        :param env: the FilterEnvironment instance
        :return: a Filter instance
        """
        mockup = env.getMockup()
        compIn = self._graph.getMockup("CompositeInput")
        compOut = self._graph.getMockup("CompositeOutput")
        res = CompositeFilter.CompositeNode(env, compIn, compOut, self)

        def renameCompositeInputPort(node, oldPortName, newPortName):
            graph = mockup.getGraph()
            try:
                node = graph.nodeName(mockup)
            except NexTRuntimeError:
                # node has been already removed from graph
                logger.internal("Node '%s' already has been removed.", node, exc_info=True)
                return
            graph.renameInputPort(node, oldPortName, newPortName)

        def renameCompositeOutputPort(node, oldPortName, newPortName):
            graph = mockup.getGraph()
            try:
                node = graph.nodeName(mockup)
            except NexTRuntimeError:
                # node has been already removed from graph
                logger.internal("Node '%s' already has been removed.", node, exc_info=True)
                return
            graph.renameOutputPort(node, oldPortName, newPortName)

        self._graph.dynOutputPortRenamed.connect(renameCompositeInputPort)
        self._graph.dynInputPortRenamed.connect(renameCompositeOutputPort)
        if mockup is not None:
            self._graph.dynOutputPortAdded.connect(mockup.createFilterAndUpdate)
            self._graph.dynInputPortAdded.connect(mockup.createFilterAndUpdate)
            self._graph.dynOutputPortDeleted.connect(mockup.createFilterAndUpdate)
            self._graph.dynInputPortDeleted.connect(mockup.createFilterAndUpdate)

        return res

    def checkRecursion(self):
        """
        Check for composite recursions and raise a CompositeRecursion exception if necessary. Called from FilterGraph
        after adding a composite filter.
        :return:
        """
        self._configuration.checkRecursion()
