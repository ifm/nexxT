import os
from pathlib import Path
import pytest
import time
import pytestqt
import pytest_xvfb
from PySide2.QtCore import QItemSelection, Qt, QTimer, QSize, QPoint, QModelIndex
from PySide2.QtWidgets import QGraphicsSceneContextMenuEvent, QWidget, QApplication
from nexxT.core.AppConsole import startNexT
from nexxT.core.Application import Application
from nexxT.interface import Services
from nexxT.services.gui.Configuration import MVCConfigurationGUI
from nexxT.services.gui.RecordingControl import MVCRecordingControlGUI
from nexxT.services.gui.PlaybackControl import MVCPlaybackControlGUI
from nexxT.services.gui.GraphEditorView import GraphEditorView
from nexxT.services.gui.GuiLogger import GuiLogger

@pytest.fixture
def keep_open(request):
    return request.config.getoption("--keep-open")

@pytest.mark.gui
@pytest.mark.parametrize("delay", [500])
def test_basic(qtbot, xvfb, keep_open, delay, tmpdir):
    if xvfb is not None:
        os.environ["HOME"] = str(tmpdir)
        print("dims = ",xvfb.width, xvfb.height)
        print("DISPLAY=",xvfb.display)
    def do_test():

        def activateContextMenu(*idx):
            # activate context menu index idx
            delay = 2000
            for j in range(len(idx)):
                for i in range(idx[j]):
                    qtbot.keyClick(None, Qt.Key_Down, delay=delay)
                if j < len(idx) - 1:
                    qtbot.keyClick(None, Qt.Key_Right, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)

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
            qtbot.keyClicks(w, text)
            qtbot.keyClick(w, Qt.Key_Return)

        def addNodeToGraphEditor(graphEditView, scenePos, *contextMenuIndices):
            oldNodes = set(graphEditView.scene().nodes.keys())
            ev = QGraphicsSceneContextMenuEvent()
            p = scenePos
            ev.setScenePos(p)
            ev.setScreenPos(graphEditView.mapToGlobal(p))
            QTimer.singleShot(delay, lambda: activateContextMenu(*contextMenuIndices))
            scene.contextMenuEvent(ev)
            for n in graphEditView.scene().nodes:
                if n not in oldNodes:
                    return graphEditView.scene().nodes[n]
            raise RuntimeError("no node created.")

        def addConnectionToGraphEditor(graphEditView, p1, p2):
            pos1 = graphEditView.mapFromScene(p1.portGrItem.sceneBoundingRect().center())
            pos2 = graphEditView.mapFromScene(p2.portGrItem.sceneBoundingRect().center())
            qtbot.mouseMove(graphEditView.viewport(), pos1, delay=delay)
            qtbot.mousePress(graphEditView.viewport(), Qt.LeftButton, pos=pos1, delay=delay)
            qtbot.mouseMove(graphEditView.viewport(), pos2, delay=delay)
            qtbot.mouseRelease(graphEditView.viewport(), Qt.LeftButton, pos=pos2, delay=delay)

        def getLastLogFrameIdx(log):
            qtbot.wait(1000) # log may be delayed
            lidx = log.logWidget.model().index(log.logWidget.model().rowCount(QModelIndex())-1, 2, QModelIndex())
            lastmsg = log.logWidget.model().data(lidx, Qt.DisplayRole)
            assert "received: Sample" in lastmsg
            return int(lastmsg.strip().split(" ")[-1])

        try:
            mw = Services.getService("MainWindow")
            conf = Services.getService("Configuration")
            rec = Services.getService("RecordingControl")
            playback = Services.getService("PlaybackControl")
            log = Services.getService("Logging")
            if 0:
                assert isinstance(conf, MVCConfigurationGUI)
                assert isinstance(rec, MVCRecordingControlGUI)
                assert isinstance(playback, MVCPlaybackControlGUI)
                assert isinstance(log, GuiLogger)
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
            idxapp = conf.model.indexOfSubConfig(app)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxapp, idxapp))
            qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=delay)
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            gev = mw.findChild(GraphEditorView, None)
            assert gev is not None
            gev.setMinimumSize(QSize(400, gev.height()))
            scene = gev.scene()
            qtbot.mouseMove(gev, pos=QPoint(20,20), delay=delay)
            qtbot.mouseMove(gev, pos=QPoint(20,20), delay=delay)
            # create 3 nodes: CSimpleSource, PySimpleStaticFilter, HDF5Writer
            n1 = addNodeToGraphEditor(gev, QPoint(20,20), 3,2,0,0)
            n2 = addNodeToGraphEditor(gev, QPoint(20,80), 3,2,0,5)
            n3 = addNodeToGraphEditor(gev, QPoint(20,80), 3,1,1)
            # auto layout
            ev = QGraphicsSceneContextMenuEvent()
            ev.setScenePos(QPoint(1,1))
            ev.setScreenPos(gev.mapToGlobal(QPoint(1,1)))
            QTimer.singleShot(delay, lambda: activateContextMenu(4))
            scene.contextMenuEvent(ev)
            # setup dynamic input port of HDF5Writer
            n3p = n3.nodeGrItem.sceneBoundingRect().center()
            ev.setScenePos(n3p)
            ev.setScreenPos(gev.mapToGlobal(gev.mapFromScene(n3p)))
            QTimer.singleShot(delay, lambda: activateContextMenu(3))
            QTimer.singleShot(delay*2, lambda: enterText("CSimpleSource_out"))
            scene.contextMenuEvent(ev)
            # set thread of HDF5Writer
            QTimer.singleShot(delay, lambda: activateContextMenu(5))
            QTimer.singleShot(delay*2, lambda: enterText("writer_thread"))
            scene.contextMenuEvent(ev)
            # connect the ports
            addConnectionToGraphEditor(gev, n1.outPortItems[0], n2.inPortItems[0])
            addConnectionToGraphEditor(gev, n1.outPortItems[0], n3.inPortItems[0])
            # set frequency to 10
            idxapp = conf.model.indexOfSubConfig(app)
            idxsource = conf.model.index(0, 0, idxapp)
            assert conf.model.data(idxsource, Qt.DisplayRole) == "CSimpleSource"
            idxprop = conf.model.index(0, 0, idxsource)
            idxpropval = conf.model.index(0, 1, idxsource)
            assert conf.model.data(idxprop, Qt.DisplayRole) == "frequency"
            conf.treeView.expand(idxsource)
            conf.treeView.scrollTo(idxpropval)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxpropval, idxpropval))
            qtbot.mouseMove(conf.treeView.viewport(), pos=region.boundingRect().center(), delay=delay)
            qtbot.mouseClick(conf.treeView.viewport(), Qt.LeftButton, pos=region.boundingRect().center(), delay=delay)
            qtbot.keyClick(conf.treeView.viewport(), Qt.Key_F2, delay=delay)
            aw()
            enterText("10.0", mw.findChild(QWidget, "PropertyDelegateEditor"))
            qtbot.wait(delay)
            assert conf.model.data(idxpropval, Qt.DisplayRole) == "10.0"
            # activate and initialize the application
            with qtbot.waitSignal(conf.configuration().appActivated):
                conf.configuration().activate("application")
            aw()
            qtbot.keyClick(None, Qt.Key_C, Qt.AltModifier, delay=delay)
            for i in range(2):
                qtbot.keyClick(None, Qt.Key_Up, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
            rec.dockWidget.raise_()
            # application runs for 2 seconds
            qtbot.wait(2000)
            # set the folder for the recording service and start recording
            QTimer.singleShot(delay, lambda: enterText(str(tmpdir)))
            rec.actSetDir.trigger()
            rec.actStart.trigger()
            # record for 2 seconds
            qtbot.wait(2000)
            # stop recording
            rec.actStop.trigger()
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
            # load the confiugration file
            QTimer.singleShot(delay, lambda: enterText(str(prjfile)))
            conf.actLoad.trigger()
            # add another application for offline use
            conf.configuration().addNewApplication()
            app = conf.configuration().applicationByName("application_2")
            # start graph editor
            idxapp = conf.model.indexOfSubConfig(app)
            qtbot.wait(delay)
            region = conf.treeView.visualRegionForSelection(QItemSelection(idxapp, idxapp))
            qtbot.mouseMove(conf.treeView.viewport(), region.boundingRect().center(), delay=delay)
            QTimer.singleShot(delay, lambda: activateContextMenu(1))
            conf._execTreeViewContextMenu(region.boundingRect().center())
            gev = mw.findChild(GraphEditorView, None)
            assert gev is not None
            gev.setMinimumSize(QSize(400, gev.height()))
            scene = gev.scene()
            qtbot.mouseMove(gev, pos=QPoint(20,20), delay=delay)
            # create 3 nodes: CSimpleSource, PySimpleStaticFilter, HDF5Writer
            n1 = addNodeToGraphEditor(gev, QPoint(20,80), 3,1,0)
            n2 = addNodeToGraphEditor(gev, QPoint(20,80), 3,2,0,5)
            # auto layout
            ev = QGraphicsSceneContextMenuEvent()
            ev.setScenePos(QPoint(1,1))
            ev.setScreenPos(gev.mapToGlobal(QPoint(1,1)))
            QTimer.singleShot(delay, lambda: activateContextMenu(4))
            scene.contextMenuEvent(ev)
            # setup dynamic ports of HDF5Reader
            n1p = n1.nodeGrItem.sceneBoundingRect().center()
            ev.setScenePos(n1p)
            ev.setScreenPos(gev.mapToGlobal(gev.mapFromScene(n1p)))
            qtbot.wait(delay)
            QTimer.singleShot(delay, lambda: activateContextMenu(4))
            QTimer.singleShot(delay*2, lambda: enterText(str(h5file)))
            QTimer.singleShot(delay*3, lambda: enterText(""))
            scene.contextMenuEvent(ev)
            # set thread of HDF5Writer
            QTimer.singleShot(delay, lambda: activateContextMenu(5))
            QTimer.singleShot(delay*2, lambda: enterText("reader_thread"))
            scene.contextMenuEvent(ev)
            # connect the ports
            addConnectionToGraphEditor(gev, n1.outPortItems[0], n2.inPortItems[0])
            # activate and initialize the application
            with qtbot.waitSignal(conf.configuration().appActivated):
                conf.configuration().activate("application_2")
            qtbot.keyClick(aw(), Qt.Key_C, Qt.AltModifier, delay=delay)
            for i in range(2):
                qtbot.keyClick(None, Qt.Key_Up, delay=delay)
            qtbot.keyClick(None, Qt.Key_Return, delay=delay)
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
            assert 40 <= lastFrame <= 50
            playback.actStepBwd.trigger()
            qtbot.wait(delay)
            currFrame = getLastLogFrameIdx(log)
            assert currFrame == lastFrame - 1
            playback.actStepFwd.trigger()
            qtbot.wait(delay)
            assert getLastLogFrameIdx(log) == lastFrame
            playback.actSeekBegin.trigger()
            firstFrame = getLastLogFrameIdx(log)
            assert firstFrame < lastFrame - 10
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
                    def clickDiscardChanges():
                        qtbot.keyClick(None, Qt.Key_Tab, delay=delay)
                        qtbot.keyClick(None, Qt.Key_Return, delay=delay)
                    QTimer.singleShot(delay, clickDiscardChanges)
                mw.close()

    QTimer.singleShot(delay, do_test)
    startNexT(None, None, [], [], True)
