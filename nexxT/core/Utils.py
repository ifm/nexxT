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
import platform
import os.path
import sqlite3
from PySide2.QtCore import (QObject, Signal, Slot, QMutex, QWaitCondition, QCoreApplication, QThread,
                            QMutexLocker, QRecursiveMutex, QTimer, QSortFilterProxyModel, Qt)
from nexxT.core.Exceptions import NexTInternalError, InvalidIdentifierException

logger = logging.getLogger(__name__)

class MethodInvoker(QObject):
    """
    a workaround for broken QMetaObject.invokeMethod wrapper. See also
    https://stackoverflow.com/questions/53296261/usage-of-qgenericargument-q-arg-when-using-invokemethod-in-pyside2
    """

    signal = Signal() # 10 arguments

    IDLE_TASK = "IDLE_TASK"

    def __init__(self, callback, connectiontype, *args):
        super().__init__()
        self.args = args
        if isinstance(callback, dict):
            obj = callback["object"]
            method = callback["method"]
            self.callback = getattr(obj, method)
            thread = callback["thread"] if "thread" in callback else obj.thread()
            self.moveToThread(thread)
        else:
            self.callback = callback
            if connectiontype != Qt.DirectConnection:
                logger.warning("Using old style API, wrong thread might be used!")
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

def assertMainThread():
    """
    assert that function is called in main thread, otherwise, a NexTInternalError is raised
    :return: None
    """
    if QCoreApplication.instance() and not QThread.currentThread() == QCoreApplication.instance().thread():
        raise NexTInternalError("Non thread-safe function is called in unexpected thread.")


def checkIdentifier(name):
    """
    Check that name is a valid nexxT name (c identifier including minus signs). Raises InvalidIdentifierException.
    :param name: string
    :return: None
    """
    if re.match(r'^[A-Za-z_][A-Za-z0-9_-]*$', name) is None:
        InvalidIdentifierException(name)

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

class FileSystemModelSortProxy(QSortFilterProxyModel):
    """
    Proxy model for sorting a file system models with "directories first" strategy.
    See also https://stackoverflow.com/questions/10789284/qfilesystemmodel-sorting-dirsfirst
    """
    def lessThan(self, left, right):
        if self.sortColumn() == 0:
            asc = self.sortOrder() == Qt.SortOrder.AscendingOrder
            left_fi = self.sourceModel().fileInfo(left)
            right_fi = self.sourceModel().fileInfo(right)
            if self.sourceModel().data(left) == "..":
                return asc
            if self.sourceModel().data(right) == "..":
                return not asc

            if not left_fi.isDir() and right_fi.isDir():
                return not asc
            if left_fi.isDir() and not right_fi.isDir():
                return asc
            left_fp = left_fi.filePath()
            right_fp = right_fi.filePath()
            if (platform.system() == "Windows" and
                    left_fi.isAbsolute() and len(left_fp) == 3 and left_fp[1:] == ":/" and
                    right_fi.isAbsolute() and len(right_fp) == 3 and right_fp[1:] == ":/"):
                res = (asc and left_fp < right_fp) or ((not asc) and right_fp < left_fp)
                return res
        return QSortFilterProxyModel.lessThan(self, left, right)

class QByteArrayBuffer(io.IOBase):
    """
    Efficient IOBase wrapper around QByteArray for pythonic access, for memoryview doesn't seem
    supported.
    """
    def __init__(self, qByteArray):
        super().__init__()
        self.ba = qByteArray
        self.p = 0
        
    def readable(self):
        return True
        
    def read(self, size=-1):
        if size < 0:
            size = self.ba.size() - self.p
        oldP = self.p
        self.p += size
        if self.p > self.ba.size():
            self.p = self.ba.size()
        return self.ba[oldP:self.p].data()
        
    def seekable(self):
        return True
        
    def seek(self, offset, whence):
        if whence == io.SEEK_SET:
            self.p = offset
        elif whence == io.SEEK_CUR:
            self.p += offset
        elif whence == io.SEEK_END:
            self.p = self.ba.size()
        if self.p < 0: 
            self.p = 0
        elif self.p > self.ba.size():
            self.p = self.ba.size()

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

def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            excepthook(*sys.exc_info())
    return wrapper

if __name__ == "__main__": # pragma: no cover
    def _smokeTestBarrier():
        # pylint: disable=import-outside-toplevel
        # pylint: disable=missing-class-docstring
        import time
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
