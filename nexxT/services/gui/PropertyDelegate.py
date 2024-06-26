# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2020 ifm electronic gmbh
#
# THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
#

"""
This module provides a delegate for use in the Configuration GUI service to edit properties.
"""

from nexxT.Qt.QtCore import Qt
from nexxT.Qt.QtWidgets import QStyledItemDelegate, QLineEdit

class PropertyDelegate(QStyledItemDelegate):
    """
    This class provides a delegate for providing editor widgets for the nexxT gui service Configuration.
    """
    def __init__(self, model, role, PropertyContent, parent): # pylint: disable=invalid-name
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
            if index.column() == 1:
                p = d.property.getPropertyDetails(d.name)
                if not p.useEnvironment:
                    res = p.handler.createEditor(parent)
                    if res is not None:
                        res.setObjectName("PropertyDelegateEditor")
                        return res
                else:
                    res = QLineEdit(parent)
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
            if index.column() == 1:
                if not p.useEnvironment:
                    v = d.property.getProperty(d.name)
                    p.handler.setEditorData(editor, v)
                else:
                    editor.setText(d.property.getProperty(d.name, subst=False))
                return None
        if isinstance(editor, QLineEdit):
            # this is happening for variables ...
            editor.setText(self.model.data(index, Qt.DisplayRole))
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
            if index.column() == 1:
                if not p.useEnvironment:
                    value = p.handler.getEditorData(editor)
                    if value is not None:
                        model.setData(index, value, Qt.EditRole)
                else:
                    value = editor.text()
                    model.setData(index, value, Qt.EditRole)
                return None
        return super().setModelData(editor, model, index)
