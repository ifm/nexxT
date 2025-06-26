# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
Setup the logging here until we have a better place.
"""

cnexxT = None # pylint: disable=invalid-name
useCImpl = True # pylint: disable=invalid-name
__version__ = None # pylint: disable=invalid-name

def setup():
    """
    Sets up the nexxT environment. In particular, provides the cnexxT and the Qt packages under the nexxT nameespace.
    """
    # create an alias nexxT.Qt for PySide[26]
    # pylint: disable=import-outside-toplevel
    import nexxT.QtMetaPackage

    try:
        from importlib import metadata
    except ImportError:
        # Running on pre-3.8 Python; use importlib-metadata package
        import importlib_metadata as metadata
    from pathlib import Path
    import os
    import sys
    import platform

    global __version__  # pylint: disable=invalid-name
    __version__ = metadata.version("nexxT")

    global useCImpl # pylint: disable=invalid-name
    useCImpl = not bool(int(os.environ.get("NEXXT_DISABLE_CIMPL", "0")))
    if useCImpl:
        # make sure to import nexxT.Qt before loading the cnexxT extension module because
        # there is a link-time dependency which would be impossible to resolve otherwise
        import nexxT.Qt.QtCore
        p = os.environ.get("NEXXT_CEXT_PATH", None)
        if p is None:
            variant = os.environ.get("NEXXT_VARIANT", "release")
            if platform.system() == "Linux":
                cplatform = "linux_" + platform.machine()
            else:
                cplatform = "msvc_x86_64"
            p = [p for p in [Path(__file__).parent / "binary" / cplatform / variant,
                             Path(__file__).parent / "binary" / cplatform / variant] if p.exists()]
            if len(p) > 0:
                p = p[0].absolute()
            else:
                p = None
        if p is not None:
            p = str(Path(p).absolute())
            sys.path.append(p)
        # TODO: following two lines can be removed after this bug has been
        #       fixed: https://bugreports.qt.io/browse/PYSIDE-1627
        import nexxT.Qt.QtWidgets
        import nexxT.Qt.QtGui
        import cnexxT as imp_cnexxT
        global cnexxT # pylint: disable=invalid-name
        cnexxT = imp_cnexxT

def changeLoggers():
    """
    Before starting nexxT, the logging system needs to be initialized:
    - add an internal logger method in addition to debug, info, warning, error
    - set default log level to INFO
    - monkey-patch root logger's setLevel() for notifying the c implementation about changes
    """
    if not getattr(changeLoggers, "executed", False):
        changeLoggers.executed = True
        # pylint: disable=import-outside-toplevel
        import logging

        logger = logging.getLogger()
        # setup log level for internal messages
        INTERNAL = 5 # pylint: disable=invalid-name
        logging.addLevelName(INTERNAL, "INTERNAL")
        logging.INTERNAL = INTERNAL
        def internal(self, message, *args, **kws):
            if self.isEnabledFor(INTERNAL):
                # Yes, logger takes its '*args' as 'args'.
                self._log(INTERNAL, message, args, **kws)
        logging.Logger.internal = internal

        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(console)
        if cnexxT is not None:
            def setLevel(level):
                ret = setLevel.origFunc(level)
                cnexxT.nexxT.Logging.setLogLevel(logger.level)
                return ret
            setLevel.origFunc = logger.setLevel
            logger.setLevel = setLevel
            logger.setLevel(logger.getEffectiveLevel())

setup()
