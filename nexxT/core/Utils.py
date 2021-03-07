# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module contains various small utility classes.
"""

import io
import re
import sys
import logging
import datetime
import os.path
import sqlite3
import time
from PySide2.QtCore import (QObject, Signal, Slot, QMutex, QWaitCondition, QCoreApplication, QThread,
                            QMutexLocker, QRecursiveMutex, QTimer, Qt, QPoint)
from PySide2.QtGui import QColor, QPainter, QTextLayout, QTextOption
from PySide2.QtWidgets import QFrame, QSizePolicy
from nexxT.core.Exceptions import NexTInternalError, InvalidIdentifierException

logger = logging.getLogger(__name__)

class MethodInvoker(QObject):
    """
    a workaround for broken QMetaObject.invokeMethod wrapper. See also
    https://stackoverflow.com/questions/53296261/usage-of-qgenericargument-q-arg-when-using-invokemethod-in-pyside2
    """

    signal = Signal() # 10 arguments

    methodscalled = set()

    IDLE_TASK = "IDLE_TASK"

    def __init__(self, callback, connectiontype, *args):
        super().__init__()
        self.args = args
        if isinstance(callback, dict):
            obj = callback["object"]
            method = callback["method"]
            self.callback = getattr(obj, method)
            thread = callback["thread"] if "thread" in callback else obj.thread()
        elif hasattr(callback, "__self__") and isinstance(callback.__self__, QObject):
            self.callback = callback
            thread = callback.__self__.thread()
        else:
            thread = None
            self.callback = callback
            if connectiontype != Qt.DirectConnection:
                logger.warning("Using old style API, wrong thread might be used!")
        if not thread is None:
            self.moveToThread(thread)
        self.methodscalled.add(self)
        if connectiontype is self.IDLE_TASK:
            QTimer.singleShot(0, self.callbackWrapper)
        else:
            self.signal.connect(self.callbackWrapper, connectiontype)
            self.signal.emit()

    @Slot(object)
    def callbackWrapper(self):
        """
        Slot which actuall performs the method call.
        :return: None
        """
        self.callback(*self.args)
        self.methodscalled.remove(self)

class ThreadToColor:
    """
    This class maps threads to colors. It is ment to be used with a singleton.
    """
    singleton = None

    def _newColor(self):
        n = len(self._threadColors)
        # [0] -> default ~ 120
        if n < 6:
            return QColor.fromHsv((120 + n*60) % 360, 200, 255)
        if n < 12:
            return QColor.fromHsv((30 + (n-6)*60) % 360, 200, 255)
        if n < 18:
            return QColor.fromHsv((30 + (n-6)*60) % 360, 100, 255)
        if n < 24:
            return QColor.fromHsv((30 + (n-6)*60) % 360, 100, 255)
        return QColor.fromHsv(0, 0, 200)

    def __init__(self):
        self._threadColors = {}
        self.get("main")

    def get(self, thread):
        """
        Return the color associated with the given thread.
        :param thread: the name of the thread given as a string instance
        :return: a QColor instance
        """
        if not thread in self._threadColors:
            self._threadColors[thread] = self._newColor()
        return self._threadColors[thread]

ThreadToColor.singleton = ThreadToColor()

def waitForSignal(signal, callback=None, timeout=None):
    """
    Waits for the given signal. If a callback is given, it will be called with the signal's arguments until the
    return value of the callback evaluates to true. If a timeout is given (in seconds), a TimeoutError will be
    thrown after the time has elapsed.
    :param signal: a Qt signal to be waited for, suitable for slot connections.
    :param callback: a callable called
    :param timeout: an optional timeout in seconds.
    :return: None
    """
    _received = False
    _sigArgs = None
    def _slot(*args, **kw):
        nonlocal _received, _sigArgs
        _sigArgs = args
        if callback is None:
            _received = True
        else:
            if callback(*args, **kw):
                _received = True
    if not signal.connect(_slot, Qt.QueuedConnection):
        raise NexTInternalError("cannot connect the signal.")
    t0 = time.perf_counter()
    while not _received:
        QCoreApplication.processEvents()
        if timeout is not None and time.perf_counter() - t0 > timeout:
            signal.disconnect(_slot)
            raise TimeoutError()
    signal.disconnect(_slot)
    return _sigArgs

class Barrier:
    """
    Implement a barrier, such that threads block until other monitored threads reach a specific location.
    The barrier can be used multiple times (it is reinitialized after the threads passed).

    See https://stackoverflow.com/questions/9637374/qt-synchronization-barrier/9639624#9639624
    """
    def __init__(self, count):
        self.count = count
        self.origCount = count
        self.mutex = QMutex()
        self.condition = QWaitCondition()

    def wait(self):
        """
        Wait until all monitored threads called wait.
        :return: None
        """
        self.mutex.lock()
        self.count -= 1
        if self.count > 0:
            self.condition.wait(self.mutex)
        else:
            self.count = self.origCount
            self.condition.wakeAll()
        self.mutex.unlock()

def mainThread():
    """
    return the applications main thread
    :return:
    """
    return QCoreApplication.instance().thread()

def isMainThread():
    """
    check whether current thread is main thread or not
    :return: boolean
    """
    return not QCoreApplication.instance() or QThread.currentThread() == mainThread()

def assertMainThread():
    """
    assert that function is called in main thread, otherwise, a NexTInternalError is raised
    :return: None
    """
    if not isMainThread():
        raise NexTInternalError("Non thread-safe function is called in unexpected thread.")


def checkIdentifier(name):
    """
    Check that name is a valid nexxT name (c identifier including minus signs). Raises InvalidIdentifierException.
    :param name: string
    :return: None
    """
    if re.match(r'^[A-Za-z_][A-Za-z0-9_-]*$', name) is None:
        raise InvalidIdentifierException(name)

# https://github.com/ar4s/python-sqlite-logging/blob/master/sqlite_handler.py
class SQLiteHandler(logging.Handler):
    """
    Logging handler that write logs to SQLite DB
    """
    ONE_CONNECTION_PER_THREAD = 0
    SINGLE_CONNECTION = 1

    def __init__(self, filename, threadSafety=ONE_CONNECTION_PER_THREAD):
        """
        Construct sqlite handler appending to filename
        :param filename:
        """
        logging.Handler.__init__(self)
        self.filename = filename
        self.threadSafety = threadSafety
        if self.threadSafety == self.SINGLE_CONNECTION:
            self.dbConn = sqlite3.connect(self.filename, check_same_thread=False)
            self.dbConn.execute(
                "CREATE TABLE IF NOT EXISTS "
                "debug(date datetime, loggername text, filename, srclineno integer, func text, level text, msg text)")
            self.dbConn.commit()
        elif self.threadSafety == self.ONE_CONNECTION_PER_THREAD:
            self.mutex = QRecursiveMutex()
            self.dbs = {}
        else:
            raise RuntimeError("Unknown threadSafety option %s" % repr(self.threadSafety))

    def _getDB(self):
        if self.threadSafety == self.SINGLE_CONNECTION:
            return self.dbConn
        # create a new connection for each thread
        with QMutexLocker(self.mutex):
            tid = QThread.currentThread()
            if not tid in self.dbs:
                # Our custom argument
                db = sqlite3.connect(self.filename)  # might need to use self.filename
                if len(self.dbs) == 0:
                    db.execute(
                        "CREATE TABLE IF NOT EXISTS "
                        "debug(date datetime, loggername text, filename, srclineno integer, "
                        "func text, level text, msg text)")
                    db.commit()
                self.dbs[tid] = db
            return self.dbs[tid]

    def emit(self, record):
        """
        save record to sqlite db
        :param record a logging record
        :return:None
        """
        db = self._getDB()
        thisdate = datetime.datetime.now()
        db.execute(
            'INSERT INTO debug(date, loggername, filename, srclineno, func, level, msg) VALUES(?,?,?,?,?,?,?)',
            (
                thisdate,
                record.name,
                os.path.abspath(record.filename),
                record.lineno,
                record.funcName,
                record.levelname,
                record.msg % record.args,
            )
        )
        if self.threadSafety == self.SINGLE_CONNECTION:
            pass
        else:
            db.commit()

class QByteArrayBuffer(io.IOBase):
    """
    Efficient IOBase wrapper around QByteArray for pythonic access, for memoryview doesn't seem
    supported; note this seems to have changed in PySide2 5.14.2.
    """
    def __init__(self, qByteArray):
        super().__init__()
        logger.warning("Using deprecated class QByteArrayBuffer. Since PySide2 5.14.2 you can cast QByteArrays directly"
                       "to memoryview and this class is not needed anymore.")
        self._ba = qByteArray
        self._ptr = 0

    def readable(self):
        """
        overwritten from base class, always true
        :return:
        """
        return True

    def seekable(self):
        """
        overwritten from base class, always true
        :return:
        """
        return True

    def read(self, size=-1):
        """
        Read from the given bytes from the byte array (if size is negative,
        the whole buffer will be read).
        :param size: the number of bytes to be read.
        :return:
        """
        if size < 0:
            size = self._ba.size() - self._ptr
        oldP = self._ptr
        self._ptr += size
        if self._ptr > self._ba.size():
            self._ptr = self._ba.size()
        return self._ba[oldP:self._ptr].data()

    def seek(self, offset, whence):
        """
        Implementation of IOBase's seek method.
        :param offset: the offset in bytes (see whence for the explanation)
        :param whence: one of io.SEEK_SET, io.SEEK_CUR, io.SEEK_END
        :return:
        """
        if whence == io.SEEK_SET:
            self._ptr = offset
        elif whence == io.SEEK_CUR:
            self._ptr += offset
        elif whence == io.SEEK_END:
            self._ptr = self._ba.size()
        if self._ptr < 0:
            self._ptr = 0
        elif self._ptr > self._ba.size():
            self._ptr = self._ba.size()

# https://stackoverflow.com/questions/6234405/logging-uncaught-exceptions-in-python
def excepthook(*args):
    """
    Generic exception handler for logging uncaught exceptions in plugin code.
    :param args:
    :return:
    """
    exc_type = args[0]
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(*args)
        return
    logger.error("Uncaught exception", exc_info=args)

def handleException(func):
    """
    Can be used as decorator to enable generic exception catching. Important: Do not use
    this for PySide2 slots because it confuses the PySide2 slot/thread detection logic.
    Instead, make a non-slot method with exception handling and call that method from
    the slot.
    :param func: The function to be wrapped
    :return: the wrapped function
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception: # pylint: disable=broad-except
            # catching a general exception is exactly wanted here
            excepthook(*sys.exc_info())
    return wrapper

class ElidedLabel(QFrame):
    """
    Loosly based on this https://doc.qt.io/qt-5/qtwidgets-widgets-elidedlabel-example.html
    """
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._content = None
        self._textOption = QTextOption()
        self._elideMode = Qt.ElideRight
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(self.fontMetrics().lineSpacing() + 5)
        self.setText(text)

    def setText(self, newText):
        """
        Sets the displayed text.
        :param newText: str
        :return:
        """
        self._content = newText
        self.update()

    def text(self):
        """
        Returns the current text
        :return:
        """
        return self._content

    def setTextOption(self, textOption):
        """
        Sets the text option
        :param textOption: A QTextOption instance
        :return:
        """
        self._textOption = textOption

    def textOption(self):
        """
        Returns the text option
        :return: a QTextOption instance
        """
        return self._textOption

    def setElideMode(self, elideMode):
        """
        Sets the elide mode of the label.
        :param elideMode: see Qt.ElideMode
        :return:
        """
        self._elideMode = elideMode

    def elideMode(self):
        """
        Returns the elide mode of the label
        :return: see Qt.ElideMode
        """
        return self._elideMode

    def paintEvent(self, event):
        """
        standard qt paint event
        :param event: a QPaintEvent instance
        :return:
        """
        self._paintEvent(event)

    @handleException
    def _paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        fontMetrics = painter.fontMetrics()
        lineSpacing = self.fontMetrics().lineSpacing()
        y = 0
        textLayout = QTextLayout(self._content, painter.font())
        textLayout.setTextOption(self._textOption)
        textLayout.beginLayout()
        while True:
            line = textLayout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(self.width())
            nextLineY = y + lineSpacing
            if self.height() >= nextLineY + lineSpacing:
                # not the last line
                elidedLine = self._content[line.textStart():line.textStart() + line.textLength()]
                elidedLine = fontMetrics.elidedText(elidedLine, self._elideMode, self.width())
                painter.drawText(QPoint(0, y + fontMetrics.ascent()), elidedLine)
                y = nextLineY
            else:
                # last line, check if we are to elide here to the end
                lastLine = self._content[line.textStart():]
                elidedLastLine = fontMetrics.elidedText(lastLine, self._elideMode, self.width())
                painter.drawText(QPoint(0, y + fontMetrics.ascent()), elidedLastLine)
                break
        textLayout.endLayout()

if __name__ == "__main__": # pragma: no cover
    def _smokeTestBarrier():
        # pylint: disable=import-outside-toplevel
        # pylint: disable=missing-class-docstring
        import random

        n = 10

        barrier = Barrier(n)

        def threadWork():
            st = random.randint(0, 5000)/1000.
            time.sleep(st)
            barrier.wait()

        class MyThread(QThread):
            def run(self):
                threadWork()

        threads = []
        for _ in range(n):
            t = MyThread()
            t.start()
            threads.append(t)

        for t in threads:
            t.wait()

    _smokeTestBarrier()
