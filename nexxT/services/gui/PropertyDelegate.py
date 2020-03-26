# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides a delegate for use in the Configuration GUI service to edit properties.
"""

from PySide2.QtCore import Qt
from PySide2.QtWidgets import QStyledItemDelegate, QLineEdit, QSpinBox

class PropertyDelegate(QStyledItemDelegate):
    """
    This class provides a delegate for providing editor widgets for the nexxT gui service Configuration.
    """
    def __init__(self, model, role, PropertyContent, parent):
        """
        Constructor.
        :param model: An instance of the nexxT gui service implementation of QAbstractItemModle
        :param role: the role which can be used to query the property items
        :param PropertyContent: the class of the property items queried with model->data(..., self.role)
        :param parent: the parent QObject
        """
        super().__init__(parent)
        self.model = model
        self.role = role
        # in fact this is a type name and not a variable
        self.PropertyContent = PropertyContent # pylint: disable=invalid-name

    def createEditor(self, parent, option, index):
        """
        Create an editor for the given index (if this is not a PropertyContent, the default implementation is used)
        :param parent: the parent of the editor
        :param option: unused
        :param index: the model index
        :return: an editor widget
        """
        d = self.model.data(index, self.role)
        if isinstance(d, self.PropertyContent):
            p = d.property.getPropertyDetails(d.name)
            res = None
            if isinstance(p.defaultVal, str):
                res = QLineEdit(parent)
                res.setFrame(False)
                res.setValidator(p.validator)
            elif isinstance(p.defaultVal, int):
                res = QSpinBox(parent)
                res.setFrame(False)
                res.setMinimum(p.validator.bottom())
                res.setMaximum(p.validator.top())
            elif isinstance(p.defaultVal, float):
                res = QLineEdit(parent)
                res.setFrame(False)
                res.setValidator(p.validator)
            if res is not None:
                return res
        return super().createEditor(parent, option, index)

    def setEditorData(self, editor, index):
        """
        Populate the editor with the data from the model
        :param editor: the editor as created by createEditor
        :param index: the index into the model
        :return:
        """
        d = self.model.data(index, self.role)
        if isinstance(d, self.PropertyContent):
            p = d.property.getPropertyDetails(d.name)
            if isinstance(p.defaultVal, str):
                # editor is line edit
                editor.setText(p.converter(d.property.getProperty(d.name)))
                return None
            if isinstance(p.defaultVal, int):
                # editor is spin box
                editor.setValue(p.converter(d.property.getProperty(d.name)))
                return None
            if isinstance(p.defaultVal, float):
                # editor is line edit
                editor.setText(str(p.converter(d.property.getProperty(d.name))))
                return None
        return super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        """
        Commit the data from the editor into the model
        :param editor: the editor as returned by createEditor
        :param model: the model
        :param index: an index to the model
        :return:
        """
        assert model is self.model
        d = self.model.data(index, self.role)
        if isinstance(d, self.PropertyContent):
            p = d.property.getPropertyDetails(d.name)
            value = None
            if isinstance(p.defaultVal, str):
                # editor is line edit
                value = editor.text()
            elif isinstance(p.defaultVal, int):
                # editor is spin box
                value = editor.value()
            elif isinstance(p.defaultVal, float):
                # editor is line edit
                value = p.converter(editor.text())
            if value is not None:
                model.setData(index, value, Qt.EditRole)
        return super().setModelData(editor, model, index)
