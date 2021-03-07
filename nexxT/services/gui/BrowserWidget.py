# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides a widget for browsing the filesystem.
"""
import logging
from pathlib import Path
import os
import platform
import string
from PySide2.QtCore import (QAbstractTableModel, Qt, Signal, QModelIndex, QDateTime, QFileInfo, QDir, QEvent)
from PySide2.QtGui import QKeyEvent
from PySide2.QtWidgets import (QWidget, QVBoxLayout, QTreeView, QFileIconProvider, QCompleter, QLineEdit, QHeaderView)

logger = logging.getLogger(__name__)

class FolderListModel(QAbstractTableModel):
    """
    This class provides a model for browsing a folder.
    """
    folderChanged = Signal(str) # emitted when the folder changes

    def __init__(self, parent):
        super().__init__(parent=parent)
        self._folder = None
        self._filter = "*"
        self._children = []
        self._iconProvider = QFileIconProvider()
        self._reset(self._folder, self._filter)

    def setFolder(self, folder):
        """
        set the folder of this browser

        :param folder: a Path or string instance
        :return:
        """
        if Path(folder) != self._folder:
            self._reset(folder, self._filter)

    def setFilter(self, flt):
        """
        Set the filter of this browser

        :param flt: string or a list of strings containing glob-style patterns
        :return:
        """
        if isinstance(flt, str):
            flt = [flt]
        self._reset(self._folder, flt)

    def fileToIndex(self, filename):
        """
        return the given file name to a model index.

        :param filename: a string or Path instance
        :return: a QModelIndex instance
        """
        filename = Path(filename)
        try:
            idx = self._children.index(filename)
            return self.createIndex(idx, 0)
        except ValueError:
            return QModelIndex()

    def _match(self, path):
        if path.is_dir():
            return True
        res = QDir.match(self._filter, path.name)
        return res

    def _reset(self, folder, flt):
        self.beginRemoveRows(QModelIndex(), 0, self.rowCount()-1)
        self._folder = None
        self.endRemoveRows()
        if folder is not None:
            listDrives = False
            f = Path(folder).resolve()
            if platform.system() == "Windows":
                folder = Path(folder)
                if folder.name == ".." and folder.parent == Path(folder.drive + "/"):
                    listDrives = True
                    f = Path("<Drives>")
            self._folder = f
            self._filter = flt
            if platform.system() == "Windows":
                if listDrives:
                    self._children = [Path("%s:/" % dl) for dl in string.ascii_uppercase if Path("%s:/" % dl).exists()]
                else:
                    self._children = [f / ".."]
            else:
                self._children = ([] if f.root == f else [f / ".."])
            if not listDrives:
                self._children += [x for x in f.glob("*") if self._match(x)]
                self._children.sort(key=lambda c: (c.is_file(), c.drive, int(c.name != ".."), c.name))
            self.beginInsertRows(QModelIndex(), 0, len(self._children)-1)
            self.endInsertRows()
            if listDrives:
                self.folderChanged.emit("<Drives>")
            else:
                self.folderChanged.emit(str(self._folder) + (os.path.sep if self._folder.is_dir() else ""))

    def folder(self):
        """
        Return the current folder.

        :return: a Path instance
        """
        return self._folder

    def filter(self):
        """
        Return the current filter

        :return: a list of strings
        """
        return self._filter

    def columnCount(self, index=QModelIndex()): # pylint: disable=unused-argument
        """
        overwritten from base class

        :param index:
        :return:
        """
        return 4

    def rowCount(self, index=QModelIndex()): # pylint: disable=unused-argument
        """
        overwritten from base class

        :param index:
        :return:
        """
        return len(self._children)

    def data(self, index, role):
        """
        overwritten from base class

        :param index:
        :param role:
        :return:
        """
        c = self._children[index.row()]
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return c.name if c.name != "" else str(c)
            if index.column() == 1:
                if c.is_dir():
                    return ""
                try:
                    s = c.stat().st_size
                except Exception: # pylint: disable=broad-except
                    return ""
                if s >= 1024*1024*1024:
                    return "%.0f GB" % (s / (1024*1024*1024))
                if s >= 1024*1024:
                    return "%.0f MB" % (s / (1024*1024))
                if s >= 1024:
                    return "%.0f kB" % (s / 1024)
                return s
            if index.column() == 2:
                try:
                    return QDateTime.fromMSecsSinceEpoch(c.stat().st_mtime*1000)
                except Exception: # pylint: disable=broad-except
                    return ""
        if role == Qt.DecorationRole:
            if index.column() == 0:
                if c.is_dir():
                    return self._iconProvider.icon(QFileIconProvider.Drive)
                return self._iconProvider.icon(QFileInfo(str(c.absolute())))
        if role == Qt.UserRole:
            if index.column() == 0:
                return c
        if role in [Qt.DisplayRole, Qt.EditRole]:
            if index.column() == 3:
                if index.row() > 0:
                    return str(c) + (os.path.sep if c.is_dir() else "")
                return str(c.parent) + os.path.sep
        return None

    def headerData(self, section, orientation, role):
        """
        overwritten from base class

        :param section:
        :param orientation:
        :param role:
        :return:
        """
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return ["Name", "Size", "Time", ""][section]
        return super().headerData(section, orientation, role)

class TabCompletionLineEdit(QLineEdit):
    """
    This class provides a line edit which changes the tab-key semantics to interact with a completer.
    """
    def __init__(self, completer, parent=None):
        super().__init__(parent)
        self._compl = completer
        self.setCompleter(self._compl)

    def nextCompletion(self, direction):
        """
        interacts with the completer, selects next / previous item

        :param direction: the direction, either -1 or +1
        :return:
        """
        index = self._compl.currentIndex()
        self._compl.popup().setCurrentIndex(index)
        start = index.row()
        if not self._compl.setCurrentRow(start + direction):
            if direction == 1:
                self._compl.setCurrentRow(0)
            else:
                self._compl.setCurrentRow(self._compl.completionModel().rowCount()-1)
        index = self._compl.currentIndex()
        self._compl.popup().setCurrentIndex(index)

    def event(self, event):
        """
        overwritten from base class

        :param event:
        :return:
        """
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Tab:
                if not self._compl.popup().isVisible():
                    self._compl.complete()
                self.nextCompletion(+1)
                return True
            if event.key() == Qt.Key_Backtab:
                if not self._compl.popup().isVisible():
                    self._compl.complete()
                self.nextCompletion(-1)
                return True
            if event.key() in [Qt.Key_Slash, Qt.Key_Backslash]:
                event = QKeyEvent(event.type(), event.key(), event.modifiers(), event.text())
        return super().event(event)

class BrowserWidget(QWidget):
    """
    This class puts together a TabCompletionLineEdit and a list view of teh FolderListModel in one single widget.
    """

    activated = Signal(str) # emitted when the user selects a file

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recursiveActivated = False
        self._model = FolderListModel(self)
        self._completer = QCompleter(self._model, self)
        self._completer.setCompletionColumn(3)
        self._lineedit = TabCompletionLineEdit(self._completer, self)
        self._view = QTreeView(self)
        self._view.setModel(self._model)
        self._model.folderChanged.connect(self._lineedit.setText)
        self._model.setFolder(".")
        self._view.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self._view.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._view.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._view.header().resizeSection(0, 500)
        self._view.header().setSectionHidden(3, True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._lineedit)
        layout.addWidget(self._view)
        self.setLayout(layout)
        self._view.activated.connect(self._activated)
        self.activated.connect(self._lineedit.setText)
        self._lineedit.returnPressed.connect(self._leActivated, Qt.QueuedConnection)
        self._lineedit.textEdited.connect(self._leTextEdited)

    def setActive(self, activeFile):
        """
        set the activated file

        :param activeFile: a string or Path instance
        :return:
        """
        activeFile = Path(activeFile)
        assert activeFile.is_file()
        self._model.setFolder(activeFile.parent)
        idx = self._model.fileToIndex(activeFile)
        self._view.setCurrentIndex(idx)
        self._view.scrollTo(idx)
        self.activated.emit(str(activeFile))

    def active(self):
        """
        The currently activated file

        :return: a string instance
        """
        cidx = self._view.currentIndex()
        c = self._model.data(cidx, Qt.UserRole)
        return str(c) if c is not None else None

    def current(self):
        """
        A synonym for active()

        :return: a string instance
        """
        return self.active()

    def setFilter(self, flt):
        """
        Set the name filter of the file browser

        :param flt: a string instance or a list of strings
        :return:
        """
        self._model.setFilter(flt)

    def scrollTo(self, item):
        """
        Scrolls to the given item.

        :param item: a string instance
        :return:
        """
        cidx = self._model.fileToIndex(item)
        self._view.scrollTo(cidx)

    def folder(self):
        """
        Returns the current folder

        :return: a Path instance
        """
        return self._model.folder()

    def setFolder(self, folder):
        """
        Sets the current folder

        :param folder: a string or a Path instance
        :return:
        """
        self._model.setFolder(folder)

    def _leActivated(self):
        idx = self._model.fileToIndex(self._lineedit.text())
        self._activated(idx)

    def _leTextEdited(self, text):
        p = Path(text)
        if p.is_dir() and len(text) > 0 and text[-1] in ["/", "\\"]:
            self.setFolder(p)

    def _activated(self, idx):
        c = self._model.data(idx, Qt.UserRole)
        if c is None:
            return
        logger.debug("activate %s", c)
        if c.is_file():
            self.activated.emit(str(c))
        else:
            self._model.setFolder(c)

if __name__ == "__main__": # pragma: no-cover
    def main():
        """
        Test function

        :return:
        """
        # pylint: disable-import-outside-toplevel
        # this is just the test function part
        from PySide2.QtWidgets import QApplication

        app = QApplication()
        bw = BrowserWidget()
        bw.activated.connect(print)
        bw.setActive("/home/wiedeman/.bashrc")
        bw.show()
        app.exec_()
    main()
