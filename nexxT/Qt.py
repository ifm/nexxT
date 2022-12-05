"""
This module is never imported when executing nexxT. Instead, the Qt module is provided through the QtMetaPackage
which is preventing python from loading unnecessary extensions. However, it is very handy to have this module, so
pylint and the IDE auto-completers are happy to know the contents of this module
"""
import logging
from PySide6 import QtWidgets, QtCore, QtGui

logging.getLogger(__name__).warning("nexxT.Qt imported not via QtMetaPackage!")
