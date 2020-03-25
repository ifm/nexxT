# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
Console entry point script for starting nexxT from command line without GUI.
"""

from argparse import ArgumentParser
import logging
import sys
from PySide2.QtCore import QCoreApplication
from PySide2.QtWidgets import QApplication

from nexxT.core.Utils import SQLiteHandler, MethodInvoker
from nexxT.core.ConfigFiles import ConfigFileLoader
from nexxT.core.Configuration import Configuration
from nexxT.core.PluginManager import PluginManager
from nexxT.core.Application import Application
from nexxT.interface import Services

from nexxT.services.ConsoleLogger import ConsoleLogger
from nexxT.services.gui.MainWindow import MainWindow
from nexxT.services.gui.Configuration import MVCConfigurationGUI
from nexxT.services.gui.PlaybackControl import MVCPlaybackControlGUI

logger = logging.getLogger(__name__)

def setupConsoleServices(config): # pylint: disable=unused-argument
    """
    Adds services available in console mode.
    :param config: a nexxT.core.Configuration instance
    :return: None
    """
    Services.addService("Logging", ConsoleLogger())

def setupGuiServices(config):
    """
    Adds services available in console mode.
    :param config: a nexxT.core.Configuration instance
    :return: None
    """
    Services.addService("Logging", ConsoleLogger()) # TODO: provide gui logging service
    mainWindow = MainWindow(config)
    Services.addService("MainWindow", mainWindow)
    Services.addService("PlaybackControl", MVCPlaybackControlGUI(config))
    Services.addService("Configuration", MVCConfigurationGUI(config))

def startNexT(cfgfile, active, withGui):
    """
    Starts next with the given config file and activates the given application.
    :param cfgfile: path to config file
    :param active: active application (if None, the first application in the config will be used)
    :return: None
    """
    logger.debug("Starting nexxT...")
    config = Configuration()
    if withGui:
        app = QApplication()
        app.setOrganizationName("nexxT")
        app.setApplicationName("nexxT")
        setupGuiServices(config)
    else:
        app = QCoreApplication()
        app.setOrganizationName("nexxT")
        app.setApplicationName("nexxT")
        setupConsoleServices(config)

    if cfgfile is not None:
        ConfigFileLoader.load(config, cfgfile)
    if withGui:
        mainWindow = Services.getService("MainWindow")
        mainWindow.restoreState()
        mainWindow.show()
    if active is not None:
        config.activate(active)
        # need the reference of this
        i2 = MethodInvoker(dict(object=Application, method="initialize", thread=app.thread()),
                           MethodInvoker.IDLE_TASK) # pylint: disable=unused-variable

    def cleanup():
        logger.debug("cleaning up loaded services")
        Services.removeAll()
        logger.debug("cleaning up loaded plugins")
        for v in ("last_traceback", "last_type", "last_value"):
            if hasattr(sys, v):
                del sys.__dict__[v]
        #PluginManager.singleton().unloadAll()
        logger.debug("cleaning up complete")

    res = app.exec_()
    logger.debug("closing config")
    config.close()
    cleanup()

    logger.internal("app.exec_ returned")

    return res

def main(withGui):
    """
    main function used as entry point
    :return: None
    """
    parser = ArgumentParser(description="nexxT console application")
    parser.add_argument("cfg", nargs='?', help=".json configuration file of the project to be loaded.")
    parser.add_argument("-a", "--active", default=None, type=str,
                        help="active application; default: first application in config file")
    parser.add_argument("-l", "--logfile", default=None, type=str,
                        help="log file location (.db extension will use sqlite).")
    parser.add_argument("-v", "--verbosity", default="INFO",
                        choices=["INTERNAL", "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"],
                        help="sets the log verbosity")
    parser.add_argument("-q", "--quiet", action="store_true", default=False, help="disble logging to stderr")
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
    startNexT(args.cfg, args.active, withGui=withGui)

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
