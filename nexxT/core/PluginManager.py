# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module defines the class PluginManager
"""

import sys
import inspect
import os.path
import logging
import gc
from collections import OrderedDict
import importlib.util
from importlib.machinery import ExtensionFileLoader, EXTENSION_SUFFIXES
from PySide2.QtCore import QObject
from nexxT.core.Exceptions import UnknownPluginType, NexTRuntimeError, PluginException
from nexxT.interface import Filter
from nexxT.core import PluginInterface
import nexxT

logger = logging.getLogger(__name__)

class BinaryLibrary:
    """
    This class holds a reference to a QLibrary instance. Attributes can be used to access filter creation factories.
    """
    def __init__(self, library):
        self._library = library
        self._availableFilterTypes = PluginInterface.singleton().availableFilters(library)

    def __getattr__(self, attr):
        if attr in self._availableFilterTypes:
            return lambda env, library=self._library: PluginInterface.singleton().create(library, attr, env)
        raise NexTRuntimeError("requested creation func '%s' not found in %s" % (attr, self._library))

    def __getitem__(self, idx):
        return self._availableFilterTypes[idx]

    def __len__(self):
        return len(self._availableFilterTypes)

    def unload(self):
        """
        Should unload the shared object / DLL. ATM, this can only be achieved via unloadAll, so this method is empty.
        :return:
        """
        # TODO: currently we only have unlaodAll()

class PythonLibrary:
    """
    This class holds a reference to an imported python plugin. Attributes can be used to access filter creation
    factories.
    """
    _pyLoadCnt = 0

    def __init__(self, library):
        PythonLibrary._pyLoadCnt += 1
        self._library = library
        modulesBefore = set(sys.modules.keys())
        logging.getLogger(__name__).debug("importing python module from file '%s'", library)
        # https://stackoverflow.com/questions/67631/how-to-import-a-module-given-the-full-path
        spec = importlib.util.spec_from_file_location("nexxT.plugins.plugin%d" % PythonLibrary._pyLoadCnt, library)
        self._mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self._mod)
        modulesAfter = set(sys.modules.keys())
        self._loadedModules = modulesAfter.difference(modulesBefore)
        self._availableFilters = None

    def __getattr__(self, attr):
        res = getattr(self._mod, attr, None)
        if res is not None:
            return res
        raise NexTRuntimeError("requested creation func '%s' not found in %s" % (attr, self._library))

    def _checkAvailableFilters(self):
        self._availableFilters = []
        for attr in sorted(dir(self._mod)):
            if isinstance(attr, str) and attr[0] != "_":
                f = getattr(self._mod, attr)
                try:
                    if issubclass(f, Filter) and not f is Filter:
                        self._availableFilters.append(attr)
                except TypeError:
                    pass

    def __getitem__(self, idx):
        if self._availableFilters is None:
            self._checkAvailableFilters()
        return self._availableFilters[idx]

    def __len__(self):
        if self._availableFilters is None:
            self._checkAvailableFilters()
        return len(self._availableFilters)

    def unload(self):
        """
        Unloads this python module. During loading, transitive dependent modules are detected and they are unloaded
        as well.
        :return:
        """

        for m in self._loadedModules:
            if m in sys.modules:
                mod = sys.modules[m]
                try:
                    fn = inspect.getfile(mod)
                except Exception: # pylint: disable=broad-except
                    # whatever goes wrong in the above call, we don't want to unload this module...
                    fn = None
                loader = getattr(mod, '__loader__', None)
                if not (fn is None or isinstance(loader, ExtensionFileLoader) or
                        os.path.splitext(fn)[1] in EXTENSION_SUFFIXES):
                    logger.internal("Unloading pure python module '%s' (%s)", m, fn)
                    del sys.modules[m]

class PluginManager(QObject):
    """
    This class handles the loading of plugins. It should be accessed by the singleton() static method.
    """

    _singleton = None

    @staticmethod
    def singleton():
        """
        Returns the singleton instance
        :return: PluginManager instance
        """
        if PluginManager._singleton is None:
            PluginManager._singleton = PluginManager()
        return PluginManager._singleton

    def __init__(self):
        super().__init__()
        # loaded libraries
        self._libraries = OrderedDict()

    def create(self, library, factoryFunction, filterEnvironment):
        """
        Creates a filter from library by calling factoryFunction.
        :param library: file name string (currently supported: .py ending); alternatively, it might be a python object,
                        in which case the loading will be omitted
        :param factoryFunction: function name to construct the filter
        :param filterEnvironment: the calling environment
        :return: a nexxT Filter instance
        """
        if isinstance(library, str):
            prop = filterEnvironment.propertyCollection()
            if library not in self._libraries:
                try:
                    self._libraries[library] = self._load(library, prop)
                except UnknownPluginType:
                    # pass exception from loader through
                    raise
                except Exception as e: # pylint: disable=broad-except
                    # catching a general exception is exactly what is wanted here
                    logging.getLogger(__name__).exception("Exception while creating %s from library '%s'",
                                                          factoryFunction, library)
                    raise PluginException("Unexpected exception while loading the plugin %s:%s (%s)" %
                                          (library, factoryFunction, e))
            res = getattr(self._libraries[library], factoryFunction)(filterEnvironment)
        else:
            res = getattr(library, factoryFunction)(filterEnvironment)
        if nexxT.useCImpl and isinstance(res, Filter):
            res = Filter.make_shared(res)
        return res

    def getFactoryFunctions(self, library):
        """
        returns all factory functions in the given library
        :param library: library as string instance
        :return: list of strings
        """
        if library not in self._libraries:
            try:
                self._libraries[library] = self._load(library)
            except UnknownPluginType:
                # pass exception from loader through
                raise
            except Exception as e: # pylint: disable=broad-except
                # catching a general exception is exactly what is wanted here
                logging.getLogger(__name__).exception("Exception while loading library '%s'",
                                                      library)
                raise PluginException("Unexpected exception while loading the library %s (%s)" %
                                      (library, e))
        lib = self._libraries[library]
        return [lib[i] for i in range(len(lib))]

    def unloadAll(self):
        """
        unloads all loaded libraries (python and c++).
        :return:
        """
        for library in list(self._libraries.keys())[::-1]:
            self._unload(library)
        if PluginInterface is not None:
            gc.collect()
            # TODO: decide what to do about unloading dll's
            #       unloading the .dll's / shared objects might be causing a hard to debug seg-fault, if there are still
            #       objects left in the python world which are deallocated later. Calling the destructor will then
            #       result in a segmentation fault. So the safe option here would be not to unload any .dll's.
            #PluginInterface.singleton().unloadAll()
        self._libraries.clear()

    def _unload(self, library):
        self._libraries[library].unload()

    def _load(self, library, prop=None):
        if library.startswith("pyfile://"):
            return self._loadPyfile(library[len("pyfile://"):], prop)
        if library.startswith("binary://"):
            return self._loadBinary(library[len("binary://"):], prop)
        raise UnknownPluginType("don't know how to load library '%s'" % library)

    @staticmethod
    def _loadPyfile(library, prop=None):
        if prop is not None:
            library = prop.evalpath(library)
        return PythonLibrary(library)

    @staticmethod
    def _loadBinary(library, prop=None):
        if PluginInterface is None:
            raise UnknownPluginType("binary plugins can only be loaded with c extension enabled.")
        if prop is not None:
            library = prop.evalpath(library)
        else:
            logger.warning("no property collection instance, string interpolation skipped.")
        logger.debug("loading binary plugin from file '%s'", library)
        return BinaryLibrary(library)
