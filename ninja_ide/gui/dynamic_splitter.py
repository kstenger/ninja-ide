# -*- coding: utf-8 -*-
#
# This file is part of NINJA-IDE (http://ninja-ide.org).
#
# NINJA-IDE is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# any later version.
#
# NINJA-IDE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with NINJA-IDE; If not, see <http://www.gnu.org/licenses/>.

from PyQt4.QtGui import QSplitter
from PyQt4.QtCore import Qt
from PyQt4.QtCore import SIGNAL


class DynamicSplitter(QSplitter):
    """
    SIGNALS:
    @currentComboSplitterChanged(PyQt_PyObject, PyQt_PyObject)
    """

    def __init__(self, orientation=Qt.Horizontal):
        super(DynamicSplitter, self).__init__(orientation)
        self._current_splitter = self
        self._current_combo_area = None

        self._add_mapper = {
            0: "_add_first_widget",
            1: "_add_second_widget",
            2: "_add_more_widgets",
        }
        self._orientation_mapper = {
            "row": Qt.Horizontal,
            "col": Qt.Vertical,
        }

    @property
    def current_combo_area(self):
        return self._current_combo_area

    def add_widget(self, widget, top=False, orientation="",
                   default=Qt.Horizontal):
        orientation = self._orientation_mapper.get(orientation, default)
        append_widget = getattr(self._current_splitter,
            self._add_mapper[self._current_splitter.count()])
        ignore = append_widget(widget, top, orientation)
        if not ignore:
            self.connect(widget, SIGNAL("focusGained(PyQt_PyObject)"),
                self._set_current_widget)
            self._set_current_widget(widget)

    def _add_first_widget(self, widget, top, orientation):
        self.addWidget(widget)

    def _add_second_widget(self, widget, top, orientation):
        self.setOrientation(orientation)
        if top:
            self.insertWidget(0, widget)
        else:
            self.addWidget(widget)

    def _add_more_widgets(self, widget, top, orientation):
        #current_index = self.count() - 1
        current_index = self.indexOf(self._current_combo_area)
        old_widget = self.widget(current_index)
        dynamic = DynamicSplitter(orientation)
        dynamic.addWidget(old_widget)
        if top:
            dynamic.insertWidget(0, widget)
        else:
            dynamic.addWidget(widget)
        self.insertWidget(current_index, dynamic)
        dynamic.setSizes([1, 1])
        self.disconnect(old_widget, SIGNAL("focusGained(PyQt_PyObject)"),
            self._set_current_widget)
        self.connect(old_widget, SIGNAL("focusGained(PyQt_PyObject)"),
                dynamic._set_current_widget)
        self.connect(widget, SIGNAL("focusGained(PyQt_PyObject)"),
                dynamic._set_current_widget)
        self.connect(dynamic,
            SIGNAL("currentComboSplitterChanged(PyQt_PyObject, PyQt_PyObject)"),
            self._set_current_widget)
        dynamic._set_current_widget(widget)
        return True

    def _set_current_widget(self, combo, splitter=None):
        if splitter is None:
            print 'splitter is none'
            splitter = self
        self._current_splitter = splitter
        self._current_combo_area = combo
        print 'emit'
        self.emit(
            SIGNAL("currentComboSplitterChanged(PyQt_PyObject, PyQt_PyObject)"),
            combo, self)