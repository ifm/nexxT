# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This viewer is a showcase to see how to write a viewer for nexxT. Note that there are multiple possibilities
to view images, and this one might actually not be the best option. You can use python toolkits such as pyqtgraph,
matpllotlibs or others supporting a QT5 backend.
"""

import logging
import numpy as np
from PySide2.QtGui import QPainter, QImage
from PySide2.QtWidgets import QWidget
from nexxT.interface import Filter, Services
from nexxT.examples.framework.ImageData import byteArrayToNumpy

logger = logging.getLogger(__name__)

class ImageView(Filter):
    """
    This is the filter receiving the image data to be drawn. It has to be run in the GUI thread.
    """
    def __init__(self, env):
        super().__init__(False, False, env)
        # create an input port for receiving the image data
        self.inPort = self.addStaticInputPort("video_in", 1, -1)
        # note that the widget shall not be created directly but in the onOpen(...) function.
        # reason is that the constructor and onInit(...) functions are called quite often and so they should
        # not perform expensive operations.
        self._widget = None
        # define the properties of this filter
        pc = self.propertyCollection()
        pc.defineProperty("caption", "view",
                          "Caption for the MDI window. You can use 2D indices for aligning multiple views\n"
                          "in a grid layout.")
        pc.defineProperty("scale", 1.0, "Scale factor for display", options=dict(min=0.01, max=16.0))
        # we use the propertyChanged signal to synchronize the scale factor.
        pc.propertyChanged.connect(self.propChanged)

    def propChanged(self, propColl, name):
        """
        Slot called whenever a property of this filter has changed.

        :param pc: the PropertyCollection instance of this filter
        :param name: the name of the changed parameter
        :return:
        """
        if name == "scale" and self._widget is not None:
            self._widget.setScale(propColl.getProperty("scale"))

    def onOpen(self):
        """
        Now we can create the widget.

        :return:
        """
        pc = self.propertyCollection()
        # get the main window service, used for registering the "subplot" in a QMDISubWindow instance
        mw = Services.getService("MainWindow")
        # create the widget
        self._widget = DisplayWidget()
        # register the subplot in the main window
        mw.subplot(pc.getProperty("caption"), self, self._widget)
        # inform the display widget about the current scale
        self._widget.setScale(pc.getProperty("scale"))

    def onClose(self):
        """
        Inverse of onOpen

        :return:
        """
        mw = Services.getService("MainWindow")
        # de-register the subplot
        mw.releaseSubplot(self._widget)
        # delete the widget reference
        self._widget = None

    def onPortDataChanged(self, port):
        """
        Notification of new data.

        :param port: the port where the data arrived.
        :return:
        """
        if port.getData().getDatatype() == "example/image":
            # convert to numpy array
            npa = byteArrayToNumpy(port.getData().getContent())
            # send to the widget
            self._widget.setData(npa)

class DisplayWidget(QWidget):
    """
    The widget actually displaying the image. It has a scale parameter for setting the scale factor of the drawn
    image. The widget is created from the Filter instance. Both are QObjects and both have to run in the main (=GUI)
    thread of the QApplication.
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._img = QImage(16, 16, QImage.Format_RGB888)
        self._scale = 1.0
        self._mv = None

    def setScale(self, scale):
        """
        Set the scale factor

        :param scale: a floating point (<1: size reduction)
        :return:
        """
        self._scale = scale
        # check for size constraints
        self.checkSize()
        # update the displayed image
        self.update()

    def setData(self, data):
        """
        Called when new data arrives. This function converts the numpy array to a QImage which can then be drawn
        with a QT painter.

        :param data: the image as a numpy array
        :return:
        """
        img = None
        if data.dtype is np.dtype(np.uint8):
            # uint8 images can either be 2 dimensional (intensity) or 3 dimensional with 3 channels (rgb)
            assert len(data.shape) == 2 or (len(data.shape) == 3 and data.shape[-1] == 3)
            # conversion will be performed later in this case
        elif data.dtype is np.dtype(np.uint16) and len(data.shape) == 2:
            # an uint16 intensity image
            self._mv = memoryview(data)
            # conversion is done immediately
            img = QImage(self._mv, data.shape[1], data.shape[0], data.shape[1], QImage.Format_Grayscale16)
        else:
            # all other cases: convert the image to a uint8 array scaling between min and max
            mind = np.nanmin(data)
            maxd = np.nanmax(data)
            data = np.clip((data.astype(np.float64)-mind)/(maxd-mind)*256, 0, 255).astype(np.uint8)
        if img is None:
            # if not yet done, convert the (uint8) data to a qimage
            self._mv = memoryview(data)
            img = QImage(self._mv, data.shape[1], data.shape[0], np.prod(data.shape[1:]),
                         QImage.Format_RGB888 if len(data.shape) == 3 and data.shape[-1] == 3
                         else QImage.Format_Grayscale8)
        # save for later painting
        self._img = img
        # check for size constraints
        self.checkSize()
        # request QT for an update
        self.update()

    def checkSize(self):
        """
        make sure that the minimum size is consistent with the shown image.

        :return:
        """
        size = self._img.size() * self._scale
        if size != self.minimumSize():
            logger.info("Size changed: %s", size)
            self.setMinimumSize(size)
            self.parent().parent().adjustSize()

    def paintEvent(self, paintEvent): # pylint: disable=unused-argument
        """
        The paint event actually drawing the image

        :param paintEvent: a QPaintEvent instance
        :return:
        """
        p = QPainter(self)
        p.scale(self._scale, self._scale)
        p.drawImage(0, 0, self._img)
