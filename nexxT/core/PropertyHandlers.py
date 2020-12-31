# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module contains the specific nexxT property handlers for the supported types.
"""

import logging
from PySide2.QtWidgets import QSpinBox, QLineEdit, QComboBox
from PySide2.QtGui import QDoubleValidator
from nexxT.interface import PropertyHandler
from nexxT.core.Exceptions import PropertyParsingError, PropertyCollectionUnknownType

logger = logging.getLogger(__name__)

class IntHandler(PropertyHandler):
    """
    The property handler for integer properties; Supported options: min and max.
    """

    def __init__(self, options):
        """
        Constructor

        :param options: the options given to the defineProperty(...) function.
        """
        for k in options:
            if k in ["min", "max"]:
                if not isinstance(options[k], int):
                    raise PropertyParsingError("Unexpected type of option %s; expected int." % k)
            else:
                raise PropertyParsingError("Unexpected option %s; expected 'min' or 'max'." % k)
        self._options = options

    def options(self):
        """
        return this handler's options

        :return: a python dict with the actual options.
        """
        return self._options

    def fromConfig(self, value):
        """
        import value from config file and return the adapted version.

        :param value: an integer is expected
        :return: the validated integer
        """
        assert isinstance(value, (float, int, bool))
        return self.validate(value)

    def toConfig(self, value):
        """
        export value to config file and return the adapted version

        :param value: an integer is expected
        :return: the exported value
        """
        assert isinstance(value, int)
        return value

    def toViewValue(self, value):
        """
        create a view of this option value.

        :param value: the current option value
        :return: a string
        """
        assert isinstance(value, int)
        return str(value)

    def validate(self, value):
        """
        Validate an option value and return an adapted, valid value

        :param value: the value to be tested (an integer)
        :return: the adapted, valid value
        """
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
        """
        Creates a QSpinBox instance for GUI editing of integer values

        :param parent: the parent of the widget
        :return: a QSpinBox instance
        """
        res = QSpinBox(parent)
        res.setFrame(False)
        if "min" in self._options:
            res.setMinimum(self._options["min"])
        else:
            res.setMinimum(-2147483648)
        if "max" in self._options:
            res.setMaximum(self._options["max"])
        else:
            res.setMaximum(2147483647)
        return res

    def setEditorData(self, editor, value):
        """
        set the value of the QSpinBox

        :param editor: the instance returned by createEditor
        :param value: the option value (an integer)
        :return: None
        """
        editor.setValue(value)

    def getEditorData(self, editor):
        """
        return the currently edited value

        :param editor: the instance returned by createEditor
        :return: the integer value
        """
        return self.validate(editor.value())


class StringHandler(PropertyHandler):
    """
    The property handler for string properties; Supported options: enum
    """

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
        """
        return this handler's options
        :return: a python dict with the actual options.
        """
        return self._options

    def fromConfig(self, value):
        """
        import value from config file and return the adapted version.
        :param value: a string is expected
        :return: the validated string
        """
        assert isinstance(value, str)
        return self.validate(value)

    def toConfig(self, value):
        """
        export value to config file and return the adapted version
        :param value: an string is expected
        :return: the exported value
        """
        assert isinstance(value, str)
        return value

    def toViewValue(self, value):
        """
        create a view of this option value.
        :param value: the current option value
        :return: a string
        """
        assert isinstance(value, str)
        return value

    def validate(self, value):
        """
        Validate an option value and return an adapted, valid value
        :param value: the value to be tested (a string)
        :return: the adapted, valid value
        """
        if "enum" in self._options:
            if not value in self._options["enum"]:
                logger.warning("Enum validation failed. Using first value in allowed list.")
                return self._options["enum"][0]
        return str(value)

    def createEditor(self, parent):
        """
        Creates a QLineEdit or QComboBox instance for GUI editing of integer values
        :param parent: the parent of the widget
        :return: the editor instance
        """
        if "enum" in self._options:
            res = QComboBox(parent)
            res.addItems(self._options["enum"])
        else:
            res = QLineEdit(parent)
        res.setFrame(False)
        return res

    def setEditorData(self, editor, value):
        """
        set the value of the QLineEdit/QComboBox
        :param editor: the instance returned by createEditor
        :param value: the option value (a string)
        :return: None
        """
        if isinstance(editor, QComboBox):
            editor.setCurrentText(value)
        else:
            editor.setText(value)

    def getEditorData(self, editor):
        """
        return the currently edited value
        :param editor: the instance returned by createEditor
        :return: the string value
        """
        if isinstance(editor, QComboBox):
            return editor.currentText()
        return self.validate(editor.text())


class FloatHandler(PropertyHandler):
    """
    The property handler for float properties; Supported options: min and max.
    """

    def __init__(self, options):
        for k in options:
            if k in ["min", "max"]:
                if not isinstance(options[k], int) and not isinstance(options[k], float):
                    raise PropertyParsingError("Unexpected type of option %s; expected int." % k)
            else:
                raise PropertyParsingError("Unexpected option %s; expected 'min' or 'max'." % k)
        self._options = options

    def options(self):
        """
        return this handler's options
        :return: a python dict with the actual options.
        """
        return self._options

    def fromConfig(self, value):
        """
        import value from config file and return the adapted version.
        :param value: a float is expected
        :return: the validated float
        """
        assert isinstance(value, (float, int, bool))
        return float(self.validate(value))

    def toConfig(self, value):
        """
        export value to config file and return the adapted version
        :param value: an float is expected
        :return: the exported value
        """
        assert isinstance(value, float)
        return value

    def toViewValue(self, value):
        """
        create a view of this option value.
        :param value: the current option value
        :return: a string
        """
        assert isinstance(value, float)
        return str(value)

    def validate(self, value):
        """
        Validate an option value and return an adapted, valid value
        :param value: the value to be tested (a float)
        :return: the adapted, valid value
        """
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
        """
        Creates a QLineEdit instance for GUI editing of integer values
        :param parent: the parent of the widget
        :return: a QLineEdit instance
        """
        res = QLineEdit(parent)
        v = QDoubleValidator()
        # QDoubleValidator seems to have a very strange behaviour when bottom and/or top values are set.
        # Therefore, we don't use this feature and rely on our own implementation.
        res.setValidator(v)
        res.setFrame(False)
        return res

    def setEditorData(self, editor, value):
        """
        set the value of the QLineEdit
        :param editor: the instance returned by createEditor
        :param value: the option value (a float)
        :return: None
        """
        editor.setText(self.toViewValue(value))

    def getEditorData(self, editor):
        """
        return the currently edited value
        :param editor: the instance returned by createEditor
        :return: the float value
        """
        res = self.validate(float(editor.text()))
        return res


class BoolHandler(PropertyHandler):
    """
    The property handler for boo. properties; Supported options: none
    """

    def __init__(self, options):
        for k in options:
            raise PropertyParsingError("Unexpected option %s; expected 'min' or 'max'." % k)
        self._options = options

    def options(self):
        """
        return this handler's options
        :return: a python dict with the actual options.
        """
        return self._options

    def fromConfig(self, value):
        """
        import value from config file and return the adapted version.
        :param value: a bool is expected
        :return: the bool
        """
        assert isinstance(value, (float, int, bool))
        return self.validate(value)

    def toConfig(self, value):
        """
        export value to config file and return the adapted version
        :param value: an bool is expected
        :return: the exported value
        """
        assert isinstance(value, bool)
        return value

    def toViewValue(self, value):
        """
        create a view of this option value.
        :param value: the current option value
        :return: a string
        """
        assert isinstance(value, bool)
        return str(value)

    def validate(self, value):
        """
        Validate an option value and return an adapted, valid value
        :param value: the value to be tested (a bool)
        :return: the adapted, valid value
        """
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)

    def createEditor(self, parent):
        """
        Creates a QCheckBox instance for GUI editing of integer values
        :param parent: the parent of the widget
        :return: a QCheckBox instance
        """
        res = QComboBox(parent)
        res.addItems([self.toViewValue(x) for x in [False, True]])
        res.setFrame(False)
        return res

    def setEditorData(self, editor, value):
        """
        set the value of the QCheckBox
        :param editor: the instance returned by createEditor
        :param value: the option value (a bool)
        :return: None
        """
        editor.setCurrentText(self.toViewValue(value))

    def getEditorData(self, editor):
        """
        return the currently edited value
        :param editor: the instance returned by createEditor
        :return: the bool value
        """
        res = editor.currentText() == self.toViewValue(True)
        return res

def defaultHandler(propertyValue):
    """
    Return a suitable property handler given the value.
    :param propertyValue: the property value
    :return: a PropertyHandler instance
    """
    if isinstance(propertyValue, bool):
        return BoolHandler
    if isinstance(propertyValue, int):
        return IntHandler
    if isinstance(propertyValue, str):
        return StringHandler
    if isinstance(propertyValue, float):
        return FloatHandler
    raise PropertyCollectionUnknownType("Cannot deduce default handler for property value %s" % repr(propertyValue))
