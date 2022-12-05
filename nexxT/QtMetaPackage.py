"""
This module provides a QT meta package such that we are able to write "from nexxT.Qt.QtWidgets import QWidget" and
nexxT.Qt will serve as an alias for PySide6

It is loosly based on this tutorial:
https://dev.to/dangerontheranger/dependency-injection-with-import-hooks-in-python-3-5hap
"""
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import types

class QtFinder(importlib.abc.MetaPathFinder):
    """
    The meta path finder which will be added to sys.meta_path
    """
    def __init__(self, loader):
        self._loader = loader

    def find_spec(self, fullname, path, target=None):
        """
        Attempt to locate the requested module

        :param fullname: the fully-qualified name of the module,
        :param path: set to __path__ for sub-modules/packages, or None otherwise.
        :param target: can be a module object, but is unused here.
        """
        if self._loader.provides(fullname):
            return importlib.machinery.ModuleSpec(fullname, self._loader)

class QtLoader(importlib.abc.Loader):
    """
    The actual loader which maps PySide modules to nexxT.Qt. The approach is similar to executing a
    ``from PySide6 import *`` statement in a real Qt.py module, but it is dynamically and prevents from loading unused
    QT modules, like QtMultimedia, etc.
    """

    def __init__(self, prefix, qtlib):
        """
        Constructor.

        :param prefix: the prefix for the proxied library (e.g. nexxT.Qt)
        :param qtlib: the PySide library to be used, must be PySide6
        """
        self._prefix = prefix
        self._qtlib = qtlib

    def provides(self, fullname):
        """
        Checks whether the queried module can be provided by this laoder or not.

        :param fullname: full-qualified module name.
        """
        return fullname == self._prefix or fullname.startswith(self._prefix + ".")

    def create_module(self, spec):
        """
        Creates a new module according to spec. It will be empty initially and populated during exec_module(...).

        :param spec: A ModuleSpec instance.
        """
        res = types.ModuleType(spec.name)
        return res

    def exec_module(self, module):
        """
        This function is called after create_module and it populates the module's namespace with the corresponding
        instances from PySideX.
        """
        proxyname = self._qtlib + module.__name__[len(self._prefix):]
        proxymod = importlib.import_module(proxyname)
        def _copy_attrs(src, dst):
            """
            pyqtgraph approach for creating mirrors of the Qt modules
            """
            for o in dir(src):
                if isinstance(getattr(src,o), types.ModuleType):
                    continue
                if o == "__path__":
                    setattr(dst, o, [])
                    continue
                if o.startswith("__") and o != "__version__" and o != "__version_info__":
                    continue
                if not hasattr(dst, o):
                    setattr(dst, o, getattr(src, o))
        _copy_attrs(proxymod, module)
        if proxyname == "PySide6":
            module.call_exec = lambda instance, *args, **kw: instance.exec(*args, **kw)

    def _truncate_name(self, fullname):
        """Strip off _COMMON_PREFIX from the given module name
        Convenience method when checking if a service is provided.
        """
        return fullname[len(self._prefix):]

def setup():
    libs = []
    try:
        import PySide6
        libs.append(("PySide6", "shiboken6"))
    except ImportError:
        pass
    if len(libs) != 1:
        raise RuntimeError("nexxT needs PySide6 installed (available: %s).", libs)
    libs = libs[0]
    sys.meta_path = ([QtFinder(QtLoader("nexxT.Qt", libs[0])), QtFinder(QtLoader("nexxT.shiboken", libs[1]))] +
                     sys.meta_path)

setup()
