# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
Real gui testing, a handy command for monitoring what's going on in the headless mode is:

> x11vnc -display :27 -localhost & (sleep 1; vncviewer :0) # 27 must match the display printed at the test start

You can also pass --no-xvfb to pytest and also --keep-open for inspecting the issue in head mode.
"""

import os
import logging
from pathlib import Path
import pytest
import time
import pytestqt
import pytest_xvfb
import shiboken2
from PySide2.QtCore import QItemSelection, Qt, QTimer, QSize, QPoint, QModelIndex, QEvent
from PySide2.QtGui import QKeyEvent
from PySide2.QtWidgets import QGraphicsSceneContextMenuEvent, QWidget, QApplication
from nexxT.core.AppConsole import startNexT
from nexxT.interface import Services
from nexxT.services.gui.Configuration import MVCConfigurationGUI
from nexxT.services.gui.RecordingControl import MVCRecordingControlGUI
from nexxT.services.gui.PlaybackControl import MVCPlaybackControlGUI
from nexxT.services.gui.GraphEditorView import GraphEditorView
from nexxT.services.gui.GuiLogger import GuiLogger

logger = logging.getLogger(__name__)

@pytest.fixture
def keep_open(request):
    return request.config.getoption("--keep-open")

@pytest.mark.gui
@pytest.mark.parametrize("delay", [600])
def test_basic(qtbot, xvfb, keep_open, delay, tmpdir):
    if xvfb is not None:
        os.environ["HOME"] = str(tmpdir)
        print("dims = ",xvfb.width, xvfb.height)
        print("DISPLAY=",xvfb.display)
    def do_test():

        def activateContextMenu(*idx):
            try:
                # activate context menu index idx
                for j in range(len(idx)):
                    for i in range(idx[j]):
                        qtbot.keyClick(None, Qt.Key_Down, delay=delay)
                    if j < len(idx) - 1:
                        qtbot.keyClick(None, Qt.Key_Right, delay=delay)
                qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            except Exception:
                logger.exception("exception while activating context menu")

        def aw(w=None):
            # on xvfb, the main window sometimes looses focus leading to a crash of the qtbot's keyClick(s) function
            # this function avoids this
            if w is None:
                w = QApplication.activeWindow()
                if w is None:
                    QApplication.setActiveWindow(mw.data())
                    w = QApplication.activeWindow()
            return w

        def enterText(text, w=None):
            if text != "":
                qtbot.keyClicks(w, text)
            qtbot.keyClick(w, Qt.Key_Return)

        def gsContextMenu(graphView, pos):
            ev = QGraphicsSceneContextMenuEvent()
            ev.setScenePos(pos)
            ev.setPos(QPoint(0,0)) # item position
            ev.setScreenPos(graphView.viewport().mapToGlobal(graphView.mapFromScene(pos)))
            #print("scenePos=", ev.scenePos(), ", pos=", ev.pos(), ", screenPos=", ev.screenPos())
            qtbot.mouseMove(graphView.viewport(), graphView.mapFromScene(ev.scenePos()))
            graphView.scene().contextMenuEvent(ev)

        def addNodeToGraphEditor(graphEditView, scenePos, *contextMenuIndices):
            oldNodes = set(graphEditView.scene().nodes.keys())
            try:
                intIdx = max([i for i in range(-1,-len(contextMenuIndices)-1,-1) if isinstance(contextMenuIndices[i], int)])
                intIdx += len(contextMenuIndices)
            except ValueError:
                intIdx = -1
            cmIdx = contextMenuIndices[:intIdx+1]
            texts = contextMenuIndices[intIdx+1:]
            QTimer.singleShot(delay, lambda: activateContextMenu(*cmIdx))
            for i,t in enumerate(texts):
                print(i, t)
                QTimer.singleShot(delay*(i+2), lambda text=t: enterText(text))
            with qtbot.waitSignal(graphEditView.scene().changed):
                gsContextMenu(graphEditView, scenePos)
            res = None
            assert len(graphEditView.scene().nodes) == len(oldNodes) + 1
            for n in graphEditView.scene().nodes:
                if n not in oldNodes:
                    assert res is None
                    res = graphEditView.scene().nodes[n]
            assert res is not None
            # hover this item
            scenePos = res.nodeGrItem.sceneBoundingRect().center()
            qtbot.mouseMove(graphEditView.viewport(), QPoint(0,0), delay=delay)
            qtbot.mouseMove(graphEditView.viewport(), graphEditView.mapFromScene(scenePos), delay=delay)
            # set item selected and deselected again
            qtbot.mouseClick(graphEditView.viewport(), Qt.LeftButton, pos=graphEditView.mapFromScene(scenePos), delay=delay)
            qtbot.mouseClick(graphEditView.viewport(), Qt.LeftButton, pos=graphEditView.mapFromScene(scenePos), delay=delay)
            return res

        def removeNodeFromGraph(graphEditView, node):
            pos = node.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(2))
            QTimer.singleShot(2*delay, lambda: enterText(""))
            gsContextMenu(graphEditView, pos)

        def addConnectionToGraphEditor(graphEditView, p1, p2):
            pos1 = graphEditView.mapFromScene(p1.portGrItem.sceneBoundingRect().center())
            pos2 = graphEditView.mapFromScene(p2.portGrItem.sceneBoundingRect().center())
            qtbot.mouseMove(graphEditView.viewport(), pos1, delay=delay)
            qtbot.mousePress(graphEditView.viewport(), Qt.LeftButton, pos=pos1, delay=delay)
            # mouse move event will not be triggered (yet?), see https://bugreports.qt.io/browse/QTBUG-5232
            for i in range(30):
                w = i/29
                qtbot.mouseMove(graphEditView.viewport(), (pos1*(1-w)+pos2*w), delay=(delay+15)//30)
            qtbot.mouseMove(graphEditView.viewport(), pos2, delay=delay)
            qtbot.mouseRelease(graphEditView.viewport(), Qt.LeftButton, pos=pos2, delay=delay)

        def setFilterProperty(conf, subConfig, filterName, propName, propVal):
            idxapp = conf.model.indexOfSubConfig(subConfig)
            for r in range(conf.model.rowCount(idxapp)):
                idxFilter = conf.model.index(r, 0, idxapp)
                name = conf.model.data(idxFilter, Qt.DisplayRole)
                if name == filterName:
                    break
                else:
                    idxFilter = None
            assert idxFilter is not None
            for r in range(conf.model.rowCount(idxFilter)):
                idxProp = conf.model.index(r, 0, idxFilter)
                name = conf.model.data(idxProp, Qt.DisplayRole)
                print(name)
                if name == propName:
                    break
                else:
                    idxProp = None
            assert idxProp is not None
            idxPropVal = conf.model.index(r, 1, idxFilter)
            conf.treeView.scrollTo(idxPropVal)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxPropVal, idxPropVal))
            qtbot.mouseMove(conf.treeView.viewport(), pos=region.boundingRect().center(), delay=delay)
            qtbot.mouseClick(conf.treeView.viewport(), Qt.LeftButton, pos=region.boundingRect().center(), delay=delay)
            qtbot.keyClick(conf.treeView.viewport(), Qt.Key_F2, delay=delay)
            aw()
            enterText(propVal, mw.findChild(QWidget, "PropertyDelegateEditor"))
            qtbot.wait(delay)
            assert conf.model.data(idxPropVal, Qt.DisplayRole) == propVal

        def getLastLogFrameIdx(log):
            qtbot.wait(1000) # log may be delayed
            lidx = log.logWidget.model().index(log.logWidget.model().rowCount(QModelIndex())-1, 2, QModelIndex())
            lastmsg = log.logWidget.model().data(lidx, Qt.DisplayRole)
            assert "received: Sample" in lastmsg
            return int(lastmsg.strip().split(" ")[-1])

        def getCurrentFrameIdx(log):
            numRows = log.logWidget.model().rowCount(QModelIndex())
            for row in range(numRows-1,0,-1):
                lidx = log.logWidget.model().index(row, 2, QModelIndex())
                lastmsg = log.logWidget.model().data(lidx, Qt.DisplayRole)
                if "received: Sample" in lastmsg:
                    return int(lastmsg.strip().split(" ")[-1])

        def clickDiscardChanges():
            qtbot.keyClick(None, Qt.Key_Tab, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)

        def startGraphEditor(conf, mw, appName, isComposite=False):
            oldChildren = mw.findChildren(GraphEditorView, None)
            if isComposite:
                app = conf.configuration().compositeFilterByName(appName)
            else:
                app = conf.configuration().applicationByName(appName)
            # start graph editor
            idxapp = conf.model.indexOfSubConfig(app)
            conf.treeView.scrollTo(idxapp)
            qtbot.wait(delay)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxapp, idxapp))
            qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=delay)
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            newChildren = mw.findChildren(GraphEditorView, None)
            gev = None
            for w in newChildren:
                if w not in oldChildren:
                    gev = w
            gev.setMinimumSize(QSize(400, 400))
            return gev

        def select(graphEditView, nodes):
            pos = nodes[0].nodeGrItem.sceneBoundingRect().center()
            qtbot.mouseClick(graphEditView.viewport(), Qt.LeftButton, pos=graphEditView.mapFromScene(pos),
                             delay=delay)
            for node in nodes[1:]:
                node.nodeGrItem.setSelected(True)

        try:
            mw = Services.getService("MainWindow")
            mw.resize(1980,1080)
            conf = Services.getService("Configuration")
            rec = Services.getService("RecordingControl")
            playback = Services.getService("PlaybackControl")
            log = Services.getService("Logging")
            if 0:
                assert isinstance(conf, MVCConfigurationGUI)
                assert isinstance(rec, MVCRecordingControlGUI)
                assert isinstance(playback, MVCPlaybackControlGUI)
                assert isinstance(log, GuiLogger)
            idxComposites = conf.model.index(0, 0)
            idxApplications = conf.model.index(1, 0)
            # add application
            conf.treeView.setMinimumSize(QSize(300,300))
            conf.treeView.scrollTo(idxApplications)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxApplications, idxApplications))
            qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=delay)
            # mouse click does not trigger context menu :(
            #qtbot.mouseClick(conf.treeView.viewport(), Qt.RightButton, pos=region.boundingRect().center())
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            app = conf.configuration().applicationByName("application")
            # start graph editor
            gev = startGraphEditor(conf, mw, "application")
            scene = gev.scene()
            qtbot.wait(delay)
            # create 3 nodes: CSimpleSource, PySimpleStaticFilter, HDF5Writer
            n1 = addNodeToGraphEditor(gev, QPoint(20,20), 3,2,0,0)
            removeNodeFromGraph(gev, n1)
            n1 = addNodeToGraphEditor(gev, QPoint(20,20), 3,2,0,0)
            n2 = addNodeToGraphEditor(gev, QPoint(20,80), 3,2,0,5)
            n3 = addNodeToGraphEditor(gev, QPoint(20,140), 3,1,1)
            n4 = addNodeToGraphEditor(gev, QPoint(-120,-60), 2, "nexxT.tests.interface.SimpleStaticFilter", "SimpleView")
            n5 = addNodeToGraphEditor(gev, QPoint(-120, 140), 2, "nexxT.tests.interface.SimpleStaticFilter", "SimpleView")
            n6 = addNodeToGraphEditor(gev, QPoint(20, -60), 2, "nexxT.tests.interface.SimpleStaticFilter", "SimpleView")
            # auto layout
            QTimer.singleShot(delay, lambda: activateContextMenu(4))
            gsContextMenu(gev, QPoint(-120,40))
            qtbot.wait(delay)
            # rename n4
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            QTimer.singleShot(delay*2, lambda: enterText("view_source"))
            print(n4, n4.nodeGrItem.sceneBoundingRect().center())
            gsContextMenu(gev, n4.nodeGrItem.sceneBoundingRect().center())
            # rename n5
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            QTimer.singleShot(delay*2, lambda: enterText("view_filter"))
            print(n5, n5.nodeGrItem.sceneBoundingRect().center())
            gsContextMenu(gev, n5.nodeGrItem.sceneBoundingRect().center())
            # rename n6
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            QTimer.singleShot(delay*2, lambda: enterText("view_filter2"))
            print(n6, n6.nodeGrItem.sceneBoundingRect().center())
            gsContextMenu(gev, n6.nodeGrItem.sceneBoundingRect().center())
            # setup dynamic input port of HDF5Writer
            n3p = n3.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(3))
            QTimer.singleShot(delay*2, lambda: enterText("CSimpleSource_out"))
            gsContextMenu(gev, n3p)
            # rename the dynamic port
            pp = n3.inPortItems[0].portGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            QTimer.singleShot(2*delay, lambda: enterText("xxx"))
            gsContextMenu(gev, pp)
            # remove the dynamic port
            pp = n3.inPortItems[0].portGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(2))
            QTimer.singleShot(2*delay, lambda: enterText(""))
            gsContextMenu(gev, pp)
            # setup dynamic input port of HDF5Writer
            n3p = n3.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(3))
            QTimer.singleShot(delay*2, lambda: enterText("CSimpleSource_out"))
            gsContextMenu(gev, n3p)
            # set thread of souurce
            n1p = n1.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(3))
            QTimer.singleShot(delay*2, lambda: enterText("source_thread"))
            gsContextMenu(gev, n1p)
            # set thread of HDF5Writer
            QTimer.singleShot(delay, lambda: activateContextMenu(5))
            QTimer.singleShot(delay*2, lambda: enterText("writer_thread"))
            gsContextMenu(gev, n3p)
            # connect the ports
            addConnectionToGraphEditor(gev, n1.outPortItems[0], n2.inPortItems[0])
            addConnectionToGraphEditor(gev, n3.inPortItems[0], n1.outPortItems[0])
            # set frequency to 10
            setFilterProperty(conf, app, "CSimpleSource", "frequency", "10.0")
            # copy a part of the app to a composite filter
            select(gev, [n1,n2])
            qtbot.keyClick(gev.viewport(), Qt.Key_X, Qt.ControlModifier, delay=delay)
            # add composite
            conf.treeView.scrollTo(idxComposites)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxComposites, idxComposites))
            qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=delay)
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            composite = conf.configuration().compositeFilterByName("composite")
            qtbot.wait(delay)
            gevc = startGraphEditor(conf, mw, "composite", True)
            assert gevc != gev
            qtbot.wait(delay)
            qtbot.keyClick(gevc.viewport(), Qt.Key_V, Qt.ControlModifier, delay=delay)
            gevc_in = gevc.scene().nodes["CompositeInput"]
            gevc_out = gevc.scene().nodes["CompositeOutput"]
            n1 = gevc.scene().nodes["CSimpleSource"]
            n2 = gevc.scene().nodes["PySimpleStaticFilter"]
            # setup dynamic port of gevc_in
            gevc_inp = gevc_in.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(3))
            QTimer.singleShot(delay*2, lambda: enterText("comp_in"))
            gsContextMenu(gevc, gevc_inp)
            # setup dynamic ports of gevc_out
            gevc_outp = gevc_out.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(3))
            QTimer.singleShot(delay*2, lambda: enterText("source"))
            gsContextMenu(gevc, gevc_outp)
            gevc_outp = gevc_out.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(3))
            QTimer.singleShot(delay*2, lambda: enterText("filter"))
            gsContextMenu(gevc, gevc_outp)
            # setup connections
            addConnectionToGraphEditor(gevc, gevc_out.inPortItems[0], n1.outPortItems[0])
            addConnectionToGraphEditor(gevc, gevc_out.inPortItems[1], n2.outPortItems[0])
            # add composite filter to gev
            comp = addNodeToGraphEditor(gev, QPoint(20,20), 3, "composite")
            shiboken2.delete(gevc.parent())
            gevc = None
            qtbot.wait(delay)
            # auto layout
            QTimer.singleShot(delay, lambda: activateContextMenu(5))
            gsContextMenu(gev, QPoint(-120,40))
            qtbot.wait(delay)
            addConnectionToGraphEditor(gev, comp.outPortItems[0], n3.inPortItems[0])
            # add visualization filters
            addConnectionToGraphEditor(gev, comp.outPortItems[0], n4.inPortItems[0])
            addConnectionToGraphEditor(gev, comp.outPortItems[1], n5.inPortItems[0])
            addConnectionToGraphEditor(gev, comp.outPortItems[1], n6.inPortItems[0])
            # set captions
            setFilterProperty(conf, app, "view_source", "caption", "view[0,0]")
            setFilterProperty(conf, app, "view_filter", "caption", "view[1,0]")
            setFilterProperty(conf, app, "view_filter2", "caption", "filter2")
            # activate and initialize the application
            with qtbot.waitSignal(conf.configuration().appActivated):
                conf.configuration().activate("application")
            aw()
            qtbot.keyClick(aw(), Qt.Key_C, Qt.AltModifier, delay=delay)
            for i in range(2):
                qtbot.keyClick(None, Qt.Key_Up, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            rec.dockWidget.raise_()
            # application runs for 2 seconds
            qtbot.wait(2000)
            # set the folder for the recording service and start recording
            QTimer.singleShot(delay, lambda: enterText(str(tmpdir)))
            rec.actSetDir.trigger()
            recStartFrame = getCurrentFrameIdx(log)
            rec.actStart.trigger()
            # record for 2 seconds
            qtbot.wait(2000)
            # stop recording
            recStopFrame = getCurrentFrameIdx(log)
            rec.actStop.trigger()
            assert recStopFrame >= recStartFrame + 10
            qtbot.wait(2000)
            # de-initialize application
            qtbot.keyClick(aw(), Qt.Key_C, Qt.AltModifier, delay=delay)
            for i in range(2):
                qtbot.keyClick(None, Qt.Key_Up, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            # check that the last log message is from the SimpleStaticFilter and it should have received more than 60
            # samples
            assert getLastLogFrameIdx(log) >= 60
            # save the configuration file
            prjfile = tmpdir / "test_project.json"
            h5file = list(Path(tmpdir).glob("*.h5"))
            assert len(h5file) == 1
            h5file = h5file[0]
            QTimer.singleShot(delay, lambda: enterText(str(prjfile)))
            conf.actSave.trigger()
            gevc = startGraphEditor(conf, mw, "composite", True)
            removeNodeFromGraph(gevc, gevc.scene().nodes["PySimpleStaticFilter"])
            # load the confiugration file
            assert conf.configuration().dirty()
            QTimer.singleShot(delay, lambda: clickDiscardChanges())
            QTimer.singleShot(2*delay, lambda: enterText(str(prjfile)))
            conf.actLoad.trigger()

            # add another application for offline use
            conf.configuration().addNewApplication()
            app = conf.configuration().applicationByName("application_2")
            # start and delete a graph editor for the old application
            gev = startGraphEditor(conf, mw, "application")
            qtbot.wait(delay)
            shiboken2.delete(gev.parent())
            qtbot.wait(delay)
            # start the editor for the new application
            gev = startGraphEditor(conf, mw, "application_2")
            # start graph editor
            scene = gev.scene()
            qtbot.mouseMove(gev, pos=QPoint(20,20), delay=delay)
            # create 3 nodes: CSimpleSource, PySimpleStaticFilter, HDF5Writer
            n1 = addNodeToGraphEditor(gev, QPoint(20,80), 4,1,0)
            n2 = addNodeToGraphEditor(gev, QPoint(20,80), 4,2,0,5)
            # auto layout
            QTimer.singleShot(delay, lambda: activateContextMenu(5))
            gsContextMenu(gev, QPoint(1,1))
            # setup dynamic output port of HDF5Reader
            n1p = n1.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(3))
            QTimer.singleShot(delay*2, lambda: enterText("yyy"))
            gsContextMenu(gev, n1p)
            # rename the dynamic port
            pp = n1.outPortItems[0].portGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            QTimer.singleShot(2*delay, lambda: enterText("xxx"))
            gsContextMenu(gev, pp)
            qtbot.wait(delay)
            # remove the dynamic port
            pp = n1.outPortItems[0].portGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(2))
            QTimer.singleShot(2*delay, lambda: enterText(""))
            gsContextMenu(gev, pp)
            # setup dynamic ports of HDF5Reader
            n1p = n1.nodeGrItem.sceneBoundingRect().center()
            QTimer.singleShot(delay, lambda: activateContextMenu(4))
            QTimer.singleShot(delay*2, lambda: enterText(str(h5file)))
            QTimer.singleShot(delay*3, lambda: enterText(""))
            gsContextMenu(gev, n1p)
            # set thread of HDF5Writer
            QTimer.singleShot(delay, lambda: activateContextMenu(5))
            QTimer.singleShot(delay*2, lambda: enterText("reader_thread"))
            gsContextMenu(gev, n1p)
            # connect the ports
            addConnectionToGraphEditor(gev, n1.outPortItems[0], n2.inPortItems[0])
            # activate and initialize the application
            with qtbot.waitSignal(conf.configuration().appActivated):
                conf.configuration().activate("application_2")
            qtbot.keyClick(aw(), Qt.Key_C, Qt.AltModifier, delay=delay)
            for i in range(2):
                qtbot.keyClick(None, Qt.Key_Up, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            # turn off load monitoring
            qtbot.keyClick(aw(), Qt.Key_O, Qt.AltModifier, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            qtbot.wait(delay)
            # turn on load monitoring
            qtbot.keyClick(aw(), Qt.Key_O, Qt.AltModifier, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            qtbot.wait(delay)
            # turn on port profiling
            qtbot.keyClick(aw(), Qt.Key_O, Qt.AltModifier, delay=delay)
            qtbot.keyClick(None, Qt.Key_Down, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            qtbot.wait(delay)
            # select file in browser
            playback.dockWidget.raise_()
            qtbot.keyClick(playback.browser._lineedit, Qt.Key_A, Qt.ControlModifier)
            qtbot.keyClicks(playback.browser._lineedit, str(h5file))
            qtbot.keyClick(playback.browser._lineedit, Qt.Key_Return)
            # wait until action start is enabled
            qtbot.waitUntil(playback.actStart.isEnabled)
            # play until finished
            playback.actStart.trigger()
            qtbot.waitUntil(lambda: not playback.actStart.isEnabled())
            qtbot.waitUntil(lambda: not playback.actPause.isEnabled(), timeout=10000)
            # check that the last log message is from the SimpleStaticFilter and it should be in the range of 40-50
            lastFrame = getLastLogFrameIdx(log)
            assert recStopFrame-10 <= lastFrame <= recStopFrame+10
            playback.actStepBwd.trigger()
            qtbot.wait(delay)
            currFrame = getLastLogFrameIdx(log)
            assert currFrame == lastFrame - 1
            playback.actStepFwd.trigger()
            qtbot.wait(delay)
            assert getLastLogFrameIdx(log) == lastFrame
            playback.actSeekBegin.trigger()
            firstFrame = getLastLogFrameIdx(log)
            assert recStartFrame-10 <= firstFrame <= recStartFrame+10
            playback.actSeekEnd.trigger()
            assert getLastLogFrameIdx(log) == lastFrame
            # de-initialize application
            qtbot.keyClick(aw(), Qt.Key_C, Qt.AltModifier, delay=delay)
            for i in range(2):
                qtbot.keyClick(None, Qt.Key_Up, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            qtbot.wait(1000)
        finally:
            if not keep_open:
                if conf.configuration().dirty():
                    QTimer.singleShot(delay, clickDiscardChanges)
                mw.close()

    QTimer.singleShot(delay, do_test)
    startNexT(None, None, [], [], True)
