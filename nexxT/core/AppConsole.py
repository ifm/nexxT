# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
Console entry point script for starting nexxT from command line without GUI.
"""

from argparse import ArgumentParser, ArgumentTypeError, RawDescriptionHelpFormatter
import logging
import signal
import sys
import nexxT
import nexxT.Qt
from nexxT.Qt.QtCore import QCoreApplication, QLocale, Qt
from nexxT.Qt.QtGui import QIcon
from nexxT.Qt.QtWidgets import QApplication, QStyleFactory

from nexxT.core.Utils import SQLiteHandler, MethodInvoker, waitForSignal
from nexxT.core.ConfigFiles import ConfigFileLoader
from nexxT.core.Configuration import Configuration
from nexxT.core.Application import Application
from nexxT.core.ActiveApplication import ActiveApplication
from nexxT.core.PluginManager import PythonLibrary
# this import is needed for initializing the nexxT qt resources
import nexxT.core.qrc_resources # pylint: disable=unused-import
from nexxT.interface import Services, FilterState

from nexxT.services.ConsoleLogger import ConsoleLogger
from nexxT.services.SrvConfiguration import MVCConfigurationBase
from nexxT.services.SrvPlaybackControl import PlaybackControlConsole
from nexxT.services.SrvRecordingControl import MVCRecordingControlBase
from nexxT.services.SrvProfiling import ProfilingServiceDummy
from nexxT.services.gui.GuiLogger import GuiLogger
from nexxT.services.gui.MainWindow import MainWindow
from nexxT.services.gui.Configuration import MVCConfigurationGUI
from nexxT.services.gui.PlaybackControl import MVCPlaybackControlGUI
from nexxT.services.gui.RecordingControl import MVCRecordingControlGUI
from nexxT.services.gui.Profiling import Profiling

logger = logging.getLogger(__name__)

def setupConsoleServices(config):
    """
    Adds services available in console mode.
    :param config: a nexxT.core.Configuration instance
    :return: None
    """
    Services.addService("Logging", ConsoleLogger())
    Services.addService("PlaybackControl", PlaybackControlConsole(config))
    Services.addService("RecordingControl", MVCRecordingControlBase(config))
    Services.addService("Configuration", MVCConfigurationBase(config))
    Services.addService("Profiling", ProfilingServiceDummy())

def setupGuiServices(config, disableProfiling=False):
    """
    Adds services available in console mode.
    :param config: a nexxT.core.Configuration instance
    :return: None
    """
    mainWindow = MainWindow(config)
    Services.addService("MainWindow", mainWindow)
    Services.addService("Logging", GuiLogger())
    Services.addService("PlaybackControl", MVCPlaybackControlGUI(config))
    Services.addService("RecordingControl", MVCRecordingControlGUI(config))
    Services.addService("Configuration", MVCConfigurationGUI(config))
    if not disableProfiling:
        Services.addService("Profiling", Profiling())
    else:
        Services.addService("Profiling", ProfilingServiceDummy())

def startNexT(cfgfile, active, execScripts, execCode, withGui, singleThreaded=False, disableUnloadHeuristic=False,
              disableProfiling=False, saveMemory=False, cmdLineArgs=[]):
    """
    Starts next with the given config file and activates the given application.
    :param cfgfile: path to config file
    :param active: active application (if None, the first application in the config will be used)
    :return: None
    """
    nexxT.changeLoggers()
    ConsoleLogger.installCrashHandlers()

    logger.debug("Starting nexxT...")
    config = Configuration()
    QLocale.setDefault(QLocale.c())
    qtargs = sys.argv[:1] + cmdLineArgs
    if withGui:
        app = QApplication(qtargs) if QApplication.instance() is None else QApplication.instance()
        QApplication.setStyle(QStyleFactory.create("Fusion"))
        app.setWindowIcon(QIcon(":icons/nexxT.svg"))
        app.setOrganizationName("nexxT")
        app.setApplicationName("nexxT")
        setupGuiServices(config, disableProfiling=disableProfiling)
        if any("vnc" in arg for arg in cmdLineArgs):
            # for the vnc server, we want the window to occupy the whole vnc size
            Services.getService("MainWindow").setWindowState(Qt.WindowMaximized)
    else:
        app = QCoreApplication(qtargs) if QCoreApplication.instance() is None else QCoreApplication.instance()
        app.setOrganizationName("nexxT")
        app.setApplicationName("nexxT")
        setupConsoleServices(config)

    ActiveApplication.singleThreaded = singleThreaded
    PythonLibrary.disableUnloadHeuristic = disableUnloadHeuristic

    if cfgfile is not None:
        if saveMemory:
            ConfigFileLoader.load(config, cfgfile, focusOnApplication=active)
        else:
            ConfigFileLoader.load(config, cfgfile)
    if withGui:
        mainWindow = Services.getService("MainWindow")
        mainWindow.restoreState()
        mainWindow.show()
        # the reference will still be held by the service, but here we don't need it anymore
        del mainWindow
    if active is not None:
        config.activate(active)
        # pylint: disable=unused-variable
        # need to hold the reference of this until the method is called
        i2 = MethodInvoker(dict(object=Application, method="initialize", thread=app.thread()),
                           MethodInvoker.IDLE_TASK) # pylint: disable=unused-variable
        waitForSignal(config.appActivated)
        if Application.activeApplication.getState() != FilterState.ACTIVE:
            waitForSignal(Application.activeApplication.stateChanged, lambda s: s == FilterState.ACTIVE)
        logger.info("done")

    def cleanup():
        logger.debug("cleaning up loaded services")
        Services.removeAll()
        logger.debug("cleaning up loaded plugins")
        for v in ("last_traceback", "last_type", "last_value"):
            if hasattr(sys, v):
                del sys.__dict__[v]
        #PluginManager.singleton().unloadAll()
        logger.debug("cleaning up complete")

    code_globals = {}
    for c in execCode:
        logger.info("Executing code '%s'", c)
        # note that exec is used intentionally here to provide the user with scripting posibilities
        exec(compile(c, "<string>", 'exec'), code_globals) # pylint: disable=exec-used
        logger.debug("Executing code done")

    for s in execScripts:
        logger.info("Executing script '%s'", s)
        with open(s, encoding="utf-8") as fscript:
            # note that exec is used intentionally here to provide the user with scripting possibilities
            exec(compile(fscript.read(), s, 'exec'), code_globals)  # pylint: disable=exec-used
        logger.debug("Executing script done")

    res = nexxT.Qt.call_exec(app)
    logger.debug("closing config")
    config.close()
    cleanup()

    logger.internal("app.exec returned")

    return res

def main(withGui):
    """
    main function used as entry point
    :return: None
    """
    parser = ArgumentParser(description="nexxT console application",
                            formatter_class=RawDescriptionHelpFormatter,
                            epilog="""\
The following environment variables have effect on nexxT's behaviour:

NEXXT_VARIANT: 
    might be set to 'nonopt' to use the non-optimized variant

NEXXT_DISABLE_CIMPL: 
    If set to '1', the nexxT C extensions are replaced by native python modules.

NEXXT_CEXT_PATH:
    Can be set to override the default search path for the nexxT C extension.
    
NEXXT_BLACKLISTED_PACKAGES:
    List of additional python packages (seperated by a ';') which are not unloaded by nexxT when configuration files
    are switched. Use "*" or "__all__" to blacklist all modules.
""")
    parser.add_argument("cfg", nargs='?', help=".json configuration file of the project to be loaded.")
    parser.add_argument("-a", "--active", default=None, type=str,
                        help="active application; default: first application in config file.")
    parser.add_argument("-l", "--logfile", default=None, type=str,
                        help="log file location (.db extension will use sqlite).")
    parser.add_argument("-v", "--verbosity", default="INFO",
                        choices=["INTERNAL", "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"],
                        help="sets the log verbosity")
    parser.add_argument("-q", "--quiet", action="store_true", default=False, help="disble logging to stderr.")
    parser.add_argument("-e", "--execpython", action="append", default=[],
                        help="execute arbitrary python code given in a string before actually starting the "
                             "application.")
    parser.add_argument("-s", "--execscript", action="append", default=[],
                        help="execute arbitrary python code given in a file before actually starting the application.")
    parser.add_argument("-t", "--single-threaded", action="store_true", default=False,
                        help="force using only the main thread")
    parser.add_argument("-u", "--disable-unload-heuristic", action="store_true", default=False,
                        help="disable unload heuristic for python modules.")
    parser.add_argument("-np", "--no-profiling", action="store_true",
                        help="disable profiling support (only relevant for GUI).")
    parser.add_argument("-sm", "--save-memory", action="store_true",
                        help="only meaningful with a given .json configuration and an selected application (--active): "
                             "discard all other applications from the configuration and load only the given one.")
    parser.add_argument("--qt", action="append", default=[], 
                        help="Arguments passed to qt. Can be given multiple times. For example, using the built-in vnc "
                             "capability of qt can be achieved by passing `--qt=-platform --qt=vnc:5900:size=1024x768`")
    parser.add_argument("-oi", "--original-keyboard-interrupt-behaviour", action="store_true",
                        help="Use this flag to restore the original keyboard interrupt behaviour. By default, nexxT "
                             "overrides a signal handler instead using the KeybaordInterrupt exception from python.")

    def str2bool(value):
        if isinstance(value, bool):
            return value
        if value.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        if value.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        raise ArgumentTypeError('Boolean value expected.')
    parser.add_argument("-g", "--gui", type=str2bool, default=withGui, const=True, nargs='?',
                        help="If true, start nexxT with GUI otherwise use console mode.")
    args = parser.parse_args()
    if args.cfg is None and  args.active is not None:
        parser.error("Active application set, but no config given.")

    nexT_logger = logging.getLogger()
    nexT_logger.setLevel(args.verbosity)
    nexT_logger.debug("Setting verbosity: %s", args.verbosity)
    if args.quiet:
        for h in nexT_logger.handlers:
            nexT_logger.removeHandler(h)
    if args.logfile is not None:
        if args.logfile.endswith(".db"):
            handler = SQLiteHandler(args.logfile)
            nexT_logger.addHandler(handler)
        else:
            handler = logging.FileHandler(args.logfile)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            nexT_logger.addHandler(handler)
    if not args.original_keyboard_interrupt_behaviour:
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    if args.save_memory and (args.cfg is None or args.active is None):
        raise RuntimeError("saveMemory needs a configuration file and an active application given on command line.")

    startNexT(args.cfg, args.active, args.execscript, args.execpython, withGui=args.gui,
              singleThreaded=args.single_threaded, disableUnloadHeuristic=args.disable_unload_heuristic,
              disableProfiling=args.no_profiling, saveMemory=args.save_memory, cmdLineArgs=args.qt)

def mainConsole():
    """
    entry point for console application
    :return:
    """
    main(withGui=False)

def mainGui():
    """
    entry point for gui application
    :return:
    """
    main(withGui=True)

if __name__ == "__main__":
    mainGui()
    logger.internal("python script end")
