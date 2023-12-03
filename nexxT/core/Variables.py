# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module implements a variable system for property substitution in nexxT
"""

import importlib
import logging
import string
from collections import UserDict
from nexxT.Qt.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class Variables(QObject):
    """
    This class represents a collection of variables suitable for substitution in properties of a filter.

    Substitution is performed according to the following rules:
    1. Variables are arranged in a tree structure. During substitution the tree is searched upwards until a variable is
    found.
    2. The syntax for substitution is basically the same as string.Template(value).safe_substitute.
    3. Variables are always converted to upper case strings before substituting (i.e. they are case insensitive).
    4. In case a variable is expanded to '${!python_code}', the python_code is evaluated using eval(...). The result is
    converted to a string, and the substitution proceeds (recursive substitution is possible). In case the python code
    raises an exception e, the substitution result is f'<{str(e)}' and a warning is logged. Substitution might use
    the importlib module to import modules and the special function subst(template) for substituting variables.
    """

    class VarDict(UserDict):
        """
        Internal helper class for implementing the variable substitution in nexxT.
        """

        def __init__(self, variables):
            self._variables = variables
            super().__init__()

        def __getitem__(self, key):
            key = key.upper()
            try:
                res = self.data[key]
                if res.startswith("${!") and res.endswith("}"):
                    try:
                        # pylint: disable=eval-used
                        # eval is insecure, but nexxT is not designed to be secure against malicious input (the whole
                        # plugin concept is insecure either)
                        res = str(eval(res[3:-1], {'importlib': importlib, 'subst': self._variables.subst}))
                    except Exception as e: # pylint: disable=broad-except
                        logger.warning("An error occurred while substituting '%s' evaluating to python code '%s': %s",
                                       key, res[3:-1], e)
                        res = f"<{str(e)}>"
                res = self._variables.subst(res)
                return res
            except KeyError as e:
                if self._variables._parent is not None:
                    return self._variables._parent[key]
                raise e

        def getraw(self, key):
            """
            get the raw, non substituted value corresponding to key

            :param key: the variable name
            """
            return self.data[key]

        def __setitem__(self, key, value):
            key = key.upper()
            if self._variables.isReadonly(key) and self.data[key] != value:
                raise RuntimeError(f"Trying to modify readonly variable {key}.")
            self.data[key] = value
            self._variables.variableAddedOrChanged.emit(key, value)

        def __delitem__(self, key):
            key = key.upper()
            super().__delitem__(key)
            self._variables.variableDeleted.emit(key)

    variableAddedOrChanged = Signal(str, str)
    variableDeleted = Signal(str)

    def __init__(self, parent = None):
        self._parent = None
        self.setParent(parent)
        self._readonly = set()
        self._vars = Variables.VarDict(self)
        super().__init__()

    def copyAndReparent(self, newParent):
        """
        Create a copy and reparent to the given parent.

        :param newParent: a Variables instance or None
        """
        res = Variables(newParent)
        for k in self.keys():
            res[k] = self.getraw(k)
        res.setReadonly(self._readonly)
        return res

    def setParent(self, parent):
        """
        reparent the variable class (for lookups of unknown variables)

        :param parent: the new parent
        """
        self._parent = parent

    def subst(self, content):
        """
        Recursively substitute the given content.

        :param content: the string to be substituted
        :return: the substituted string
        """
        return string.Template(content).safe_substitute(self)

    def setReadonly(self, readonlyvars):
        """
        Set the given variables as readonly and return the old set of readonly vars.

        :param readonlyvars: an iterable containing names of readonly variables
        :return: a set containing the readonly variables before the change
        """
        old = self._readonly
        self._readonly = set()
        for k in readonlyvars:
            self._readonly.add(k.upper())
        return old

    def isReadonly(self, key):
        """
        Return whether or not the given variable is readonly

        :param key: the variable name to be tested
        """
        return key.upper() in self._readonly

    def keys(self):
        """
        :return: the variables defined in this instance.
        """
        return self._vars.keys()

    def getraw(self, key):
        """
        Get the raw, non-substituted values of a variable.

        :return: a string instance
        """
        return self._vars.getraw(key)

    def __setitem__(self, key, value):
        self._vars[key] = value

    def __getitem__(self, key):
        return self._vars[key]

    def __delitem__(self, key):
        del self._vars[key]
