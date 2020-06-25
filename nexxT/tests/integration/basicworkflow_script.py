import logging
from PySide2.QtCore import Qt, QCoreApplication, QTimer
from nexxT.interface import Services, FilterState
from nexxT.core.Utils import MethodInvoker, waitForSignal

logger = logging.getLogger(__name__)

def execute():
    cfg = Services.getService("Configuration")
    pbc = Services.getService("PlaybackControl")
    log = Services.getService("Logging")

    # create a new configuration with a composite graph and an application
    execute.i = MethodInvoker(cfg.newConfig, Qt.QueuedConnection, "basicworkflow.json")
    waitForSignal(cfg.configuration().configNameChanged)

    # create simple composite filter
    cfg.configuration().renameComposite(cfg.configuration().addNewCompositeFilter(), "composite")
    comp = cfg.configuration().compositeFilterByName("composite")
    node = comp.getGraph().addNode(library="pyfile://./SimpleStaticFilter.py",
                                   factoryFunction="SimpleStaticFilter")
    comp.getGraph().getMockup(node).propertyCollection().setProperty("sleep_time", 0.2)

    execute.i = MethodInvoker(comp.getGraph().addDynamicInputPort, Qt.QueuedConnection, "CompositeOutput", "out")
    waitForSignal(comp.getGraph().dynInputPortAdded)
    execute.i = MethodInvoker(comp.getGraph().addDynamicOutputPort, Qt.QueuedConnection, "CompositeInput", "in")
    waitForSignal(comp.getGraph().dynOutputPortAdded)
    comp.getGraph().addConnection("CompositeInput", "in", node, "inPort")
    comp.getGraph().addConnection(node, "outPort", "CompositeOutput", "out")

    # create simple application
    cfg.configuration().renameApp(cfg.configuration().addNewApplication(), "myApp")
    app = cfg.configuration().applicationByName("myApp")
    import nexxT
    if nexxT.useCImpl:
        src = app.getGraph().addNode(library="binary://./binary/${NEXXT_PLATFORM}/${NEXXT_VARIANT}/test_plugins",
                                      factoryFunction="SimpleSource")
    else:
        src = app.getGraph().addNode(library="pyfile://./SimpleStaticFilter.py",
                                      factoryFunction="SimpleSource")
    app.getGraph().getMockup(src).propertyCollection().getChildCollection("_nexxT").setProperty("thread", "source-thread")
    app.getGraph().getMockup(src).propertyCollection().setProperty("frequency", 10.0)

    flt = app.getGraph().addNode(library=comp,
                                 factoryFunction="compositeNode")
    app.getGraph().addConnection(src, "outPort", flt, "in")

    # save application
    execute.i = MethodInvoker(cfg.saveConfig, Qt.QueuedConnection)
    waitForSignal(cfg.configuration().configNameChanged)

    # activate
    execute.i = MethodInvoker(cfg.changeActiveApp, Qt.QueuedConnection, "myApp")
    waitForSignal(cfg.configuration().appActivated)
    execute.i = MethodInvoker(cfg.activate, Qt.QueuedConnection)
    waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.ACTIVE)
    logger.info("app activated")

    t = QTimer()
    t.setSingleShot(True)
    t.setInterval(3000)
    t.start()
    waitForSignal(t.timeout)

    execute.i = MethodInvoker(cfg.deactivate, Qt.QueuedConnection)
    waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.CONSTRUCTED)
    logger.info("app deactivated")

    execute.i = MethodInvoker(cfg.activate, Qt.QueuedConnection)
    waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.ACTIVE)
    logger.info("app activated")

    t = QTimer()
    t.setSingleShot(True)
    t.setInterval(3000)
    t.start()
    waitForSignal(t.timeout)

    execute.i = MethodInvoker(cfg.deactivate, Qt.QueuedConnection)
    waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.CONSTRUCTED)
    logger.info("app deactivated")

    # re-open this application
    execute.i = MethodInvoker(cfg.loadConfig, Qt.QueuedConnection, "basicworkflow.json")
    waitForSignal(cfg.configuration().configNameChanged)
    logger.info("config loaded")

    # activate
    execute.i = MethodInvoker(cfg.changeActiveApp, Qt.QueuedConnection, "myApp")
    waitForSignal(cfg.configuration().appActivated)
    execute.i = MethodInvoker(cfg.activate, Qt.QueuedConnection)
    waitForSignal(app.activeApplication.stateChanged, lambda s: s == FilterState.ACTIVE)
    logger.info("app activated")

    t = QTimer()
    t.setSingleShot(True)
    t.setInterval(3000)
    t.start()
    waitForSignal(t.timeout)

    if 0:
        import os,pprint, time
        pprint.pprint(os.environ)
        try:
            from pytest_cov.embed import cleanup
        except ImportError:
            pass
        else:
            print("Cleaning up")
            cleanup()

        #time.sleep(120)
    execute.i = MethodInvoker(QCoreApplication.quit, Qt.QueuedConnection)


execute()