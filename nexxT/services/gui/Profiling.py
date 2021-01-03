# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides the gui part of the profiling service for nexxT.
"""

import logging
import numpy as np
from PySide2.QtCore import QByteArray, Slot, Qt, QPointF, QLineF, QRectF, QEvent
from PySide2.QtGui import QPainter, QPolygonF, QPen, QColor, QFontMetricsF, QPalette
from PySide2.QtWidgets import QWidget, QToolTip, QAction
from nexxT.core.Utils import ThreadToColor
from nexxT.interface import Services
from nexxT.services.SrvProfiling import ProfilingService

logger = logging.getLogger(__name__)

class LoadDisplayWidget(QWidget):
    """
    This widget displays the thread-specific load.
    """
    baseTimestamp = None

    def __init__(self, parent):
        super().__init__(parent=parent)
        self._loadData = {}
        self.setBackgroundRole(QPalette.Base)
        self.setAutoFillBackground(True)

    @Slot(str, QByteArray)
    def newLoadData(self, threadName, timestamps, load):
        """
        Slot called when new load data is available

        :param threadName: the name of the thread given as string
        :param loadData: the load data, given as the QByteArray of a n x 2 np.float32 array
        :return:
        """
        atimestamps = np.frombuffer(memoryview(timestamps), dtype=np.int64)
        aload = np.frombuffer(memoryview(load), dtype=np.float32)
        if LoadDisplayWidget.baseTimestamp is None:
            LoadDisplayWidget.baseTimestamp = np.min(atimestamps)
        if threadName not in self._loadData:
            self._loadData[threadName] = QPolygonF()
        p = self._loadData[threadName]
        for i in range(aload.shape[0]):
            x = 1e-9*(atimestamps[i] - self.baseTimestamp)
            if p.size() > 0 and p.at(p.count()-1).x() > x:
                # it seems that QT re-orders slots :( we have to maintain the order here
                idx = p.count()
                while idx > 0 and p.at(idx-1).x() > x:
                    idx -= 1
                p.insert(idx, QPointF(x, aload[i]))
            else:
                p.append(QPointF(x, aload[i]))
        if p[p.count()-1].x() - p[0].x() > 60:
            for i in range(p.count()):
                if p[p.count()-1].x() - p[i].x() <= 60:
                    p.remove(0, i)
                    break
        self.update()

    @Slot(str)
    def removeThread(self, thread):
        """
        Remove the thread from the stored load data.

        :param thread: the name of the thread to be removed.
        :return:
        """
        if thread in self._loadData:
            del self._loadData[thread]

    def paintEvent(self, ev):
        """
        Manually implemented paint event

        :param ev: the QT paint event
        :return:
        """
        h = self.height()
        w = self.width()
        p = QPainter(self)
        p.setClipRect(ev.region().boundingRect())
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(4)
        ls = QFontMetricsF(p.font()).lineSpacing()
        for idx, t in enumerate(sorted(list(self._loadData.keys()))):
            y = 10 + idx*ls
            pen.setColor(ThreadToColor.singleton.get(t))
            p.setPen(pen)
            p.drawLine(QLineF(15, y, 15 + 15, y))
            pen.setColor(QColor(0, 0, 0))
            p.setPen(pen)
            p.drawText(QPointF(35, y), t)

        if len(self._loadData) > 0:
            right = max([polygon[polygon.count()-1].x() for _, polygon in self._loadData.items()])
        else:
            right = 0.0
        p.translate(w-10-right*20, h-10)
        p.scale(20, -(h-20)) # x direction: 20 pixels per second, y direction: spread between 10 and h-10
        topleft = p.transform().inverted()[0].map(QPointF(10, 10))
        pen.setWidthF(0)
        pen.setCosmetic(True)
        left = topleft.x()
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(pen)
        p.drawLine(QLineF(left, 0, right, 0))
        p.drawLine(QLineF(left, 0, left, 1))
        idx = 0
        for t, polygon in self._loadData.items():
            pen.setColor(ThreadToColor.singleton.get(t))
            p.setPen(pen)
            p.drawPolyline(polygon)
        p.end()

class SpanDisplayWidget(QWidget):
    """
    This Widget displays the time/occupancy profiling overview based on the input ports events.
    """
    def __init__(self, parent):
        super().__init__(parent=parent)
        #self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)
        self._spanData = {}
        self._removedThreads = set()
        self.setBackgroundRole(QPalette.Base)
        self.setAutoFillBackground(True)
        self.portYCoords = []

    @Slot(str, str, QByteArray)
    def newSpanData(self, threadName, portName, spanData):
        """
        This slot is called when new profiling data is available.

        :param threadName: the name of the associated thread
        :param portName: the full-qualified name of the port
        :param spanData: the profiling data, given as the byte array representation of a n x 2 int64 array.
        :return:
        """
        if threadName in self._removedThreads:
            del self._spanData[threadName]
            self._removedThreads.remove(threadName)
        spanData = np.reshape(np.frombuffer(memoryview(spanData), dtype=np.int64), (-1, 2))
        if threadName not in self._spanData:
            self._spanData[threadName] = {}
        if portName not in self._spanData[threadName]:
            self._spanData[threadName][portName] = np.zeros((0, 2), np.int64)
        self._spanData[threadName][portName] = np.append(self._spanData[threadName][portName], spanData, axis=0)
        sd = self._spanData[threadName][portName]
        if (sd[-1, -1] - sd[0, 0])*1e-9 > 60:
            for i in range(sd.shape[0]):
                if (sd[-1, -1] - sd[i, 0])*1e-9 <= 60:
                    sd = sd[i:, :]
                    self._spanData[threadName][portName] = sd
                    break
        self.update()

    @Slot(str)
    def removeThread(self, thread):
        """
        Lazily removes the thread from the profiling data. To be able to inspect the data when the application is
        stopped, the data will actually be removed when new data of the thread is available.

        :param thread: the name of the thread to be removed.
        :return:
        """
        if thread in self._spanData:
            self._removedThreads.add(thread)

    def paintEvent(self, ev):
        """
        Manually implemented paint event of the time / occupancy diagram.

        :param ev: the qt paint event
        :return:
        """
        bgcolor = self.palette().color(self.backgroundRole())
        h = self.height()
        w = self.width()
        p = QPainter(self)
        p.setClipRect(ev.region().boundingRect())
        pen = QPen(QColor(0, 0, 0))
        pen.setWidth(0)
        pen.setCosmetic(True)
        ls = QFontMetricsF(p.font()).lineSpacing()
        maxx = 0
        minx = None
        for t in sorted(list(self._spanData.keys())):
            for port in sorted(list(self._spanData[t].keys())):
                sd = self._spanData[t][port]
                maxx = np.maximum(maxx, np.max(sd))
                minx = np.minimum(minx, np.min(sd)) if minx is not None else np.min(sd)
        scalex = 1e-9*200 # 200 pixels / second
        # (maxx-minx)*scalex + offx = w-10
        if minx is None:
            return
        offx = w-10-(maxx-minx)*scalex
        idx = 0
        self.portYCoords = []
        for t in sorted(list(self._spanData.keys())):
            for port in sorted(list(self._spanData[t].keys())):
                pen.setColor(QColor(0, 0, 0))
                p.setPen(pen)
                y = 10 + idx*ls
                self.portYCoords.append((t, port, y-ls/2, y))
                idx += 1
                sd = self._spanData[t][port]
                for i in range(sd.shape[0]):
                    x1, x2 = sd[i, :]
                    x1 = (x1-minx)*scalex + offx
                    x2 = (x2-minx)*scalex + offx
                    color = ThreadToColor.singleton.get(t)
                    color.setAlpha(125)
                    p.fillRect(QRectF(x1, y-ls/2, x2-x1, ls/2), color)
                    p.drawRect(QRectF(x1, y-ls/2, x2-x1, ls/2))
        pen = QPen(QColor(40, 40, 40))
        pen.setWidth(0)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        for x in range(w-10, -1, -20):
            p.drawLine(x, 10, x, h-10)
        idx = 0
        pen.setStyle(Qt.SolidLine)
        p.setPen(pen)
        for t in sorted(list(self._spanData.keys())):
            for port in sorted(list(self._spanData[t].keys())):
                y = 10 + idx*ls
                idx += 1
                br = QFontMetricsF(p.font()).boundingRect(port)
                br.translate(10, y)
                p.fillRect(br, bgcolor)
                p.drawText(10, y, port)
        p.end()

    def textDescription(self, thread, port):
        """
        Tooltip text generation.

        :param thread: the name of the corresponding thread
        :param port: the full-qualified port name.
        :return: a string instance containing the profiling info.
        """
        sd = self._spanData[thread][port]
        res = "Thread: %s, Port: %s\n" % (thread, port)
        groups = []
        activeGroup = dict()
        for i in range(sd.shape[0]):
            if len(activeGroup) > 0:
                if sd[i, 1] <= activeGroup["finish"]:
                    activeGroup["subcalls"].append(sd[i, :])
                    continue
                groups.append(activeGroup)
            activeGroup = dict(start=sd[i, 0], finish=sd[i, 1], subcalls=[])
        for i, g in enumerate(groups[::-1]):
            total = (g["finish"] - g["start"])*1e-6
            exclusive = sum([sc[1]-sc[0] for sc in g["subcalls"]])*1e-6
            subcalls = total - exclusive
            res += " event[%d] Total runtime: %.1f ms; Exclusive time: %.1f ms; Subcall time: %.1f ms\n" % (
                -i-1, total, exclusive, subcalls)
            if i >= 9: # show last 10 calls
                break
        return res

    def event(self, ev):
        """
        Event filter for generating tool tips.

        :param ev: a QEvent instance.
        :return:
        """
        if ev.type() == QEvent.ToolTip:
            for thread, port, y1, y2 in self.portYCoords:
                if ev.pos().y() >= y1 and ev.pos().y() <= y2:
                    QToolTip.showText(ev.globalPos(), self.textDescription(thread, port))
            return True
        return super().event(ev)

class Profiling(ProfilingService):
    """
    GUI part of the nexxT profiling service.
    """

    def __init__(self):
        super().__init__()
        srv = Services.getService("MainWindow")
        profMenu = srv.menuBar().addMenu("Pr&ofiling")

        self.loadDockWidget = srv.newDockWidget("Load", None, Qt.BottomDockWidgetArea)
        self.loadDisplay = LoadDisplayWidget(self.loadDockWidget)
        self.loadDockWidget.setWidget(self.loadDisplay)
        self.loadDataUpdated.connect(self.loadDisplay.newLoadData)
        self.threadDeregistered.connect(self.loadDisplay.removeThread)

        self.spanDockWidget = srv.newDockWidget("Profiling", None, Qt.BottomDockWidgetArea)
        self.spanDisplay = SpanDisplayWidget(self.spanDockWidget)
        self.spanDockWidget.setWidget(self.spanDisplay)
        self.spanDataUpdated.connect(self.spanDisplay.newSpanData)
        self.threadDeregistered.connect(self.spanDisplay.removeThread)

        self.actLoadEnabled = QAction("Enable Load Monitor")
        self.actLoadEnabled.setCheckable(True)
        self.actLoadEnabled.setChecked(True)
        self.actLoadEnabled.toggled.connect(self.setLoadMonitorEnabled)

        self.actProfEnabled = QAction("Enable Port Profiling")
        self.actProfEnabled.setCheckable(True)
        self.actProfEnabled.setChecked(False)
        self.actProfEnabled.toggled.connect(self.setPortProfilingEnabled)

        self.setLoadMonitorEnabled(True)
        self.setPortProfilingEnabled(False)

        profMenu.addAction(self.actLoadEnabled)
        profMenu.addAction(self.actProfEnabled)

    def setLoadMonitorEnabled(self, enabled):
        """
        called when the corresponding QAction is toggled

        :param enabled: boolean
        :return:
        """
        self.actProfEnabled.setEnabled(enabled)
        super().setLoadMonitorEnabled(enabled)

    def setPortProfilingEnabled(self, enabled):
        """
        called when the corresponding QAction is toggled

        :param enabled: boolean
        :return:
        """
        self.actLoadEnabled.setEnabled(not enabled)
        super().setPortProfilingEnabled(enabled)
