import logging
import sys
import os
from nexxT.interface import Filter, DataSample
from PySide2.QtGui import QIntValidator, QDoubleValidator
from PySide2.QtCore import QTimer

sys.path.append(os.path.split(__file__)[0])
from ImageData import Image_ui8

logger = logging.getLogger(__name__)

class VirtualLiveGrabber(Filter):
    def __init__(self, env):
        Filter.__init__(self, False, False, env)
        logger.debug("constructor: begin")
        self.port = self.addStaticOutputPort("image")
        pc = self.propertyCollection()
        pc.defineProperty("width", 640, "image width", validator=QIntValidator(bottom=8, top=5*1024))
        pc.defineProperty("height", 480, "image height", validator=QIntValidator(bottom=8, top=5*1024))
        pc.defineProperty("framerate", 10.0, "image frame rate", validator=QDoubleValidator(bottom=0.1, top=1000))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.newSample)
        logger.debug("constructor: end")

    def onOpen(self):
        # a real frame grabber would connect to the hardware in this function
        logger.debug("onOpen: begin")
        self.frame = 0
        pc = self.propertyCollection()
        width = pc.getProperty("width")
        height = pc.getProperty("height")
        img = Image_ui8()
        img.width = width
        img.height = height
        n = width*height
        img.data[:n] = [v % 255 for v in range(self.frame, self.frame + n)]
        self.img = img
        logger.debug("onOpen: end")
        
    def onStart(self):
        # actually start the grabbing
        logger.debug("onStart: begin")
        pc = self.propertyCollection()
        self.timer.start(int(1000 / pc.getProperty("framerate")))
        logger.debug("onStart: end")
        
    def newSample(self):
        # transmit a new sample over the port
        logger.debug("newSample: begin")
        v0 = self.img.data[0]
        n = self.img.width * self.img.height
        self.img.data[:n-1] = self.img.data[1:n]
        self.img.data[n-1] = v0
        self.port.transmit(DataSample(bytes(self.img), "nexxT/examples/img/ui8", DataSample.currentTime()))
        logger.debug("newSample: end")
        
    def onStop(self):
        # actually stop the grabbing
        logger.debug("onStop: begin")
        self.timer.stop()
        logger.debug("onStop: end")
        
    def onClose(self):
        # a real frame grabber would disconnect from the hardware in this function
        logger.debug("onClose: begin")
        del self.img
        logger.debug("onClose: end")
