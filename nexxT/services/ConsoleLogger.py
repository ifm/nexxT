# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides a service which maps log messages coming from c++ and qt to python log messages.
It is automatically used by NEXT_LOG_*() macros in c++.
"""

import logging
import os.path
import sys
from PySide2.QtCore import QObject, Slot, qInstallMessageHandler, QtMsgType
from nexxT.core.Utils import excepthook

logger = logging.getLogger(__name__)

# see https://stackoverflow.com/questions/32443808/best-way-to-override-lineno-in-python-logger
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
def makeRecord(self, name, level, filename, lineno, msg, args, excInfo, func=None, extra=None, sinfo=None):
    """
    A factory method which can be overridden in subclasses to create
    specialized LogRecords.
    """
    if extra is not None:
        filename, lineno = extra
        name = "c++/%s" % (os.path.split(filename)[1])
    return logging.LogRecord(name, level, filename, lineno, msg, args, excInfo, func, sinfo)
# pylint: enable=too-many-arguments
# pylint: enable=unused-argument

logger.__class__ = type("CplusplusLogger", (logger.__class__,), dict(makeRecord=makeRecord))

class ConsoleLogger(QObject):
    """
    Logging service to console (using python logging module). This class is used to log messages in C++.
    """
    @Slot(int, str, str, int)
    def log(self, level, message, file, line): # pylint: disable=no-self-use
        """
        Called from c++ to log a message.

        :param level: logging compatible log level
        :param message: message as a string
        :param file: file which originated the log message
        :param line: line of log message statement
        :return:
        """
        logger.log(level, message, extra=(file, line))

    @staticmethod
    def qtMessageHandler(qtMsgType, qMessageLogContext, msg):
        """
        Qt message handler for handling qt messages in normal logging.

        :param qtMsgType: qt log level
        :param qMessageLogContext: qt log context
        :param msg: message as a string
        :return:
        """
        typeMap = {QtMsgType.QtDebugMsg : logging.DEBUG,
                   QtMsgType.QtInfoMsg : logging.INFO,
                   QtMsgType.QtWarningMsg : logging.WARNING,
                   QtMsgType.QtCriticalMsg : logging.CRITICAL,
                   QtMsgType.QtFatalMsg : logging.FATAL}
        logger.log(typeMap[qtMsgType], msg, extra=(qMessageLogContext.file if qMessageLogContext.file is not None
                                                   else "<qt>", qMessageLogContext.line))

qInstallMessageHandler(ConsoleLogger.qtMessageHandler)
sys.excepthook = excepthook
