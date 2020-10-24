# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
Setup the logging here until we have a better place.
"""

def setup():
    try:
        from importlib import metadata
    except ImportError:
        # Running on pre-3.8 Python; use importlib-metadata package
        import importlib_metadata as metadata
    import logging
    from pathlib import Path
    import os
    import sys
    import platform

    logger = logging.getLogger()
    INTERNAL = 5 # setup log level for internal messages
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
    logger.info("configured logger")
    logger.setLevel(logging.INFO)

    global __version__
    __version__ = metadata.version("nexxT")

    global useCImpl
    useCImpl = not bool(int(os.environ.get("NEXXT_DISABLE_CIMPL", "0")))
    if useCImpl:
        # make sure to import PySide2 before loading the cnexxT extension module because
        # there is a link-time dependency which would be impossible to resolve otherwise
        import PySide2.QtCore
        p = os.environ.get("NEXXT_CEXT_PATH", None)
        if p is None:
            variant = os.environ.get("NEXXT_VARIANT", "release")
            cplatform = "linux_x86_64" if platform.system() == "Linux" else "msvc_x86_64"
            p = [p for p in [Path(__file__).parent / "binary" / cplatform / variant,
                             Path(__file__).parent / "binary" / cplatform / variant] if p.exists()]
            if len(p) > 0:
                p = p[0].absolute()
            else:
                p = None
        if p is not None:
            p = str(Path(p).absolute())
            logger.info("c extension module search path: %s", p)
            sys.path.append(p)
        import cnexxT as imp_cnexxT
        global cnexxT
        cnexxT = imp_cnexxT
        def setLevel(level):
            ret = setLevel.origFunc(level)
            cnexxT.nexxT.Logging.setLogLevel(logger.level)
            return ret
        setLevel.origFunc = logger.setLevel
        logger.setLevel = setLevel
        logger.setLevel(logging.INFO)

setup()