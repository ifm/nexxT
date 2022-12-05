# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines exceptions used in the nexxT framework.
"""

def _factoryToString(factory):
    # pylint: disable=import-outside-toplevel
    # pylint: disable=cyclic-import
    # needed to avoid recursive import
    from nexxT.interface.Ports import InputPortInterface, OutputPortInterface
    if isinstance(factory, str):
        return factory
    return "Input" if factory is InputPortInterface else ("Output" if factory is OutputPortInterface else "")

class NexTRuntimeError(RuntimeError):
    """
    Generic runtime error of nexxT framework.
    """

class NexTInternalError(NexTRuntimeError):
    """
    Raised when we found a bug in nexxT.
    """

class NodeExistsError(NexTRuntimeError):
    """
    raised node is added or renamed which already exists
    """
    def __init__(self, nodeName):
        super().__init__(f"Node {nodeName} already exists.")

class NodeNotFoundError(NexTRuntimeError):
    """
    raised node is added or renamed which already exists
    """
    def __init__(self, nodeName):
        super().__init__(f"Node {nodeName} not found.")

class NodeProtectedError(NexTRuntimeError):
    """
    raised if protected node is to be deleted or renamed
    """
    def __init__(self, nodeName):
        super().__init__(f"Node {nodeName} is protected and cannot be deleted or renamed.")

class PortExistsError(NexTRuntimeError):
    """
    raised when a port is added or renamed which already exists
    """
    def __init__(self, nodeName, portName, factory=None):
        super().__init__(f"{_factoryToString(factory)}Port {nodeName}/{portName} already exists.")

class PortNotFoundError(NexTRuntimeError):
    """
    raised when a referenced port is not found.
    """
    def __init__(self, nodeName, portName, factory=None):
        super().__init__(f"{_factoryToString(factory)}Port {nodeName}/{portName} not found.")

class DynamicPortUnsupported(NexTRuntimeError):
    """
    raised for unsupported dynamic port operations
    """
    def __init__(self, portName, factory=None):
        super().__init__(f"No dynamic {_factoryToString(factory)}Port support; port name: {portName}")

class ConnectionExistsError(NexTRuntimeError):
    """
    raised when a connection is added twice
    """
    def __init__(self, nodeFrom, portFrom, nodeTo, portTo):
        super().__init__(f"Connection from {nodeFrom}/{portFrom} to {nodeTo}/{portTo} already exists.")

class ConnectionNotFound(NexTRuntimeError):
    """
    raised when a connection is added twice
    """
    def __init__(self, nodeFrom, portFrom, nodeTo, portTo):
        super().__init__(f"Connection from {nodeFrom}/{portFrom} to {nodeTo}/{portTo} not found.")

class UnknownPluginType(NexTRuntimeError):
    """
    raised when a plugin has unknown extension
    """

class PluginException(NexTRuntimeError):
    """
    raised when a plugin raises an unexpected unhandled exception
    """

class UnexpectedFilterState(NexTRuntimeError):
    """
    raised when operations are performed in unexpected filter states
    """
    def __init__(self, state, operation):
        # pylint: disable=import-outside-toplevel
        # pylint: disable=cyclic-import
        # needed to avoid recursive import
        from nexxT.interface.Filters import FilterState
        super().__init__(f"Operation '{operation}' cannot be performed in state {FilterState.state2str(state)}")

class FilterStateMachineError(UnexpectedFilterState):
    """
    raised when a state transition is invalid.
    """
    def __init__(self, oldState, newState):
        # pylint: disable=import-outside-toplevel
        # pylint: disable=cyclic-import
        # needed to avoid recursive import
        from nexxT.interface.Filters import FilterState
        super().__init__(oldState, "Transition to " + FilterState.state2str(newState))

class PropertyCollectionChildExists(NexTRuntimeError):
    """
    raised when trying to create an already existing property collection
    """
    def __init__(self, name):
        super().__init__(f"PropertyCollection already has a child named {name}")

class PropertyCollectionChildNotFound(NexTRuntimeError):
    """
    raised when trying to access a non-existing property collection
    """
    def __init__(self, name):
        super().__init__(f"PropertyCollection has no child named {name}")

class PropertyCollectionPropertyNotFound(NexTRuntimeError):
    """
    raised when trying to set the value of an unknown property
    """
    def __init__(self, name):
        super().__init__(f"PropertyCollection has no property named {name}")

class PropertyCollectionUnknownType(NexTRuntimeError):
    """
    raised when the type given to getProperty or setProperty is unknown to the property system
    """
    def __init__(self, value):
        super().__init__(f"PropertyCollection has been provided with an invalid typed value {repr(value)}")

class PropertyParsingError(NexTRuntimeError):
    """
    raised when a property cannot be parsed from a string
    """

class PropertyInconsistentDefinition(NexTRuntimeError):
    """
    raised when the same property is defined in different ways
    """
    def __init__(self, name):
        super().__init__(f"Inconsistent definitions for property named {name}")

class InvalidIdentifierException(NexTRuntimeError):
    """
    raised when a provided name doesn't confirm to identifier specification
    """
    def __init__(self, name):
        super().__init__(f"Invalid identifier '{name}'")

class CompositeRecursion(NexTRuntimeError):
    """
    raised when a composite filter is dependent on itself
    """
    def __init__(self, name):
        super().__init__(f"Composite filter '{name}' depends on itself.")

class PossibleDeadlock(NexTRuntimeError):
    """
    raised during application activation when a possible deadlock is detected (a cycle was found in the thread graph)
    """
    def __init__(self, cycle):
        super().__init__(f"This graph is not deadlock-safe. A cycle has been found in the thread graph: {cycle}")
