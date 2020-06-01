import logging
from PySide2.QtWidgets import QSpinBox, QLineEdit, QComboBox, QCheckBox
from PySide2.QtGui import QDoubleValidator
from nexxT.interface import PropertyHandler
from nexxT.core.Exceptions import PropertyParsingError, PropertyCollectionUnknownType

logger = logging.getLogger(__name__)

class IntHandler(PropertyHandler):

    def __init__(self, options):
        for k in options:
            if k in ["min", "max"]:
                if not isinstance(options[k], int):
                    raise PropertyParsingError("Unexpected type of option %s; expected int." % k)
            else:
                raise PropertyParsingError("Unexpected option %s; expected 'min' or 'max'." % k)
        self._options = options

    def options(self):
        return self._options

    def fromConfig(self, value):
        assert isinstance(value, int)
        return self.validate(value)

    def toConfig(self, value):
        assert isinstance(value, int)
        return value

    def toViewValue(self, value):
        assert isinstance(value, int)
        return str(value)

    def validate(self, value):
        if "min" in self._options:
            if value < self._options["min"]:
                logger.warning("Adapted option value %d to minimum value %d.", value, self._options["min"])
                return self._options["min"]
        if "max" in self._options:
            if value > self._options["max"]:
                logger.warning("Adapted option value %d to maximum value %d.", value, self._options["max"])
                return self._options["max"]
        return int(value)

    def createEditor(self, parent):
        res = QSpinBox(parent)
        res.setFrame(False)
        if "min" in self._options:
            res.setMinimum(self._options["min"])
        if "max" in self._options:
            res.setMaximum(self._options["max"])
        return res

    def setEditorData(self, editor, value):
        editor.setValue(value)

    def getEditorData(self, editor):
        return self.validate(editor.value())


class StringHandler(PropertyHandler):

    def __init__(self, options):
        for k in options:
            if k == "enum":
                if not isinstance(options[k], list):
                    raise PropertyParsingError("enum options must be defined as list of strings.")
                if len(options[k]) == 0:
                    raise PropertyParsingError("enum options must be defined as non-empty list.")
                for v in options[k]:
                    if not isinstance(v, str):
                        raise PropertyParsingError("enum options must be defined as list of strings.")
            else:
                raise PropertyParsingError("Unknown option %s for string properties" % k)
        self._options = options

    def options(self):
        return self._options

    def fromConfig(self, value):
        assert isinstance(value, str)
        return self.validate(value)

    def toConfig(self, value):
        assert isinstance(value, str)
        return value

    def toViewValue(self, value):
        assert isinstance(value, str)
        return value

    def validate(self, value):
        if "enum" in self._options:
            if not value in self._options["enum"]:
                logger.warning("Enum validation failed. Using first value in allowed list.")
                return self._options["enum"][0]
        return str(value)

    def createEditor(self, parent):
        if "enum" in self._options:
            res = QComboBox(parent)
            res.addItems(self._options["enum"])
        else:
            res = QLineEdit(parent)
        res.setFrame(False)
        return res

    def setEditorData(self, editor, value):
        if isinstance(editor, QComboBox):
            editor.setCurrentText(value)
        else:
            editor.setText(value)

    def getEditorData(self, editor):
        if isinstance(editor, QComboBox):
            return editor.currentText()
        return self.validate(editor.text())


class FloatHandler(PropertyHandler):

    def __init__(self, options):
        for k in options:
            if k in ["min", "max"]:
                if not isinstance(options[k], int) and not isinstance(options[k], float):
                    raise PropertyParsingError("Unexpected type of option %s; expected int." % k)
            else:
                raise PropertyParsingError("Unexpected option %s; expected 'min' or 'max'." % k)
        self._options = options

    def options(self):
        return self._options

    def fromConfig(self, value):
        assert isinstance(value, float) or isinstance(value, int)
        return float(self.validate(value))

    def toConfig(self, value):
        assert isinstance(value, float)
        return value

    def toViewValue(self, value):
        assert isinstance(value, float)
        return str(value)

    def validate(self, value):
        if "min" in self._options:
            if value < self._options["min"]:
                logger.warning("Adapted option value %f to minimum value %f.", value, self._options["min"])
                return float(self._options["min"])
        if "max" in self._options:
            if value > self._options["max"]:
                logger.warning("Adapted option value %f to maximum value %f.", value, self._options["max"])
                return float(self._options["max"])
        return float(value)

    def createEditor(self, parent):
        res = QLineEdit(parent)
        v = QDoubleValidator()
        if "min" in self._options:
            v.setBottom(self._options["min"])
        if "max" in self._options:
            res.setTop(self._options["max"])
        res.setValidator(v)
        res.setFrame(False)
        return res

    def setEditorData(self, editor, value):
        editor.setValue(str(value))

    def getEditorData(self, editor):
        return self.validate(editor.value())


class BoolHandler(PropertyHandler):

    def __init__(self, options):
        for k in options:
            raise PropertyParsingError("Unexpected option %s; expected 'min' or 'max'." % k)
        self._options = options

    def options(self):
        return self._options

    def fromConfig(self, value):
        assert isinstance(value, bool)
        return self.validate(value)

    def toConfig(self, value):
        assert isinstance(value, bool)
        return value

    def toViewValue(self, value):
        assert isinstance(value, bool)
        return str(value)

    def validate(self, value):
        return bool(value)

    def createEditor(self, parent):
        res = QCheckBox(parent)
        res.setFrame(False)
        return res

    def setEditorData(self, editor, value):
        editor.setChecked(value)

    def getEditorData(self, editor):
        return editor.isChecked()

def defaultHandler(propertyValue):
    if isinstance(propertyValue, int):
        return IntHandler
    if isinstance(propertyValue, str):
        return StringHandler
    if isinstance(propertyValue, float):
        return FloatHandler
    if isinstance(propertyValue, bool):
        return BoolHandler
    raise PropertyCollectionUnknownType("Cannot deduce default handler for property value %s" % repr(propertyValue))
