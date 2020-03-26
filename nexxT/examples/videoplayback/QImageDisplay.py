# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

import logging
import shiboken2
from PySide2.QtCore import QBuffer
from PySide2.QtGui import QImageReader, QPixmap
from PySide2.QtWidgets import QLabel, QWidget, QMdiSubWindow
from nexxT.interface import Filter, InputPort, Services

logger = logging.getLogger(__name__)

class QImageDisplay(Filter):

    def __init__(self, environment):
        Filter.__init__(self, False, False, environment)
        self.inPort = InputPort(False, "inPort", environment)
        self.addStaticPort(self.inPort)
        self.propertyCollection().defineProperty("SubplotID", "ImageDisplay", "The parent subplot.")
        self.lastSize = None

    def onOpen(self):
        srv = Services.getService("MainWindow")
        self.display = QLabel()
        self.subplotID = self.propertyCollection().getProperty("SubplotID")
        srv.subplot(self.subplotID, self, self.display)

    def onClose(self):
        srv = Services.getService("MainWindow")
        srv.releaseSubplot(self.subplotID)

    def onPortDataChanged(self, inputPort):
        dataSample = inputPort.getData()
        c = dataSample.getContent()
        b = QBuffer(c)
        r = QImageReader()
        r.setDevice(b)
        img = r.read()
        self.display.setPixmap(QPixmap.fromImage(img))
        logger.debug("got image, size %d %d", img.size().width(), img.size().height())
        if self.lastSize != img.size():
            self.lastSize = img.size()
            self.display.setMinimumSize(img.size())
            # propagate the size change to the parents
            w = self.display
            while w is not None:
                if isinstance(w, QWidget):
                    w.adjustSize()
                if isinstance(w, QMdiSubWindow):
                    break
                w = w.parent()