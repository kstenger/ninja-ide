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

from __future__ import absolute_import
from __future__ import unicode_literals

import re

from PyQt4.QtGui import QDialog
from PyQt4.QtGui import QVBoxLayout
from PyQt4.QtCore import Qt
from PyQt4.QtCore import SIGNAL
from PyQt4.QtDeclarative import QDeclarativeView

from ninja_ide.core import settings
from ninja_ide.core.file_handling import file_manager
from ninja_ide.tools import ui_tools
from ninja_ide.gui.ide import IDE
from ninja_ide.tools.locator import locator


class LocatorWidget(QDialog):
    """LocatorWidget class with the Logic for the QML UI"""

    def __init__(self, parent=None):
        super(LocatorWidget, self).__init__(
            parent, Qt.Dialog | Qt.FramelessWindowHint)
        self._parent = parent
        self.setModal(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        self.setFixedHeight(400)
        self.setFixedWidth(500)
        # Create the QML user interface.
        view = QDeclarativeView()
        view.setResizeMode(QDeclarativeView.SizeRootObjectToView)
        view.setSource(ui_tools.get_qml_resource("Locator.qml"))
        self._root = view.rootObject()
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(view)

        self.locate_symbols = locator.LocateSymbolsThread()
        self.connect(self.locate_symbols, SIGNAL("finished()"), self._cleanup)
        self.connect(self.locate_symbols, SIGNAL("terminated()"),
                     self._cleanup)

        # Locator things
        self.filterPrefix = re.compile(r'(@|<|>|-|!|\.|/|:)')
        self.page_items_step = 10
        self._colors = {
            "@": "white",
            "<": "#18ff6a",
            ">": "red",
            "-": "#18e1ff",
            ".": "#f118ff",
            "/": "#fff118",
            ":": "#18ffd6",
            "!": "#ffa018"}
        self._replace_symbol_type = {"<": "&lt;", ">": "&gt;"}
        self.reset_values()

        self._filter_actions = {
            '.': self._filter_this_file,
            '/': self._filter_tabs,
            ':': self._filter_lines
        }

        self.connect(self._root, SIGNAL("textChanged(QString)"),
                     self.set_prefix)

    def reset_values(self):
        self._avoid_refresh = False
        self.__prefix = ''
        self.__pre_filters = []
        self.__pre_results = []
        self.tempLocations = []
        self.items_in_page = 0
        self._line_jump = -1

    def showEvent(self, event):
        """Method takes an event to show the Notification"""
        # Load POPUP
        #TODO
        super(LocatorWidget, self).showEvent(event)
        #width, pgeo = self._parent.width() / 2, self._parent.geometry()
        #x = pgeo.left() if conditional_horizont else pgeo.right()
        #y = pgeo.bottom() if conditional_vertical else pgeo.top() - self._height
        #self.setFixedWidth(width)
        x = (self._parent.width() / 2) - (self.width() / 2)
        y = 0
        #y = self._parent.y() + self._main_container.combo_header_size
        self.setGeometry(x, y, self.width(), self.height())
        self._root.activateInput()
        self._refresh_filter()

    def _cleanup(self):
        self.locate_symbols.wait()

    def explore_code(self):
        self.locate_symbols.find_code_location()

    def explore_file_code(self, path):
        self.locate_symbols.find_file_code_location(path)

    def set_prefix(self, prefix):
        """Set the prefix for the completer."""
        self.__prefix = prefix.lower()
        if not self._avoid_refresh:
            self._refresh_filter()

    def _refresh_filter(self):
        items = self.filter()
        self._root.clear()
        for item in items:
            if item.type in ("<", ">"):
                typeIcon = self._replace_symbol_type[item.type]
            else:
                typeIcon = item.type
            self._root.loadItem(typeIcon, item.name, item.lineno,
                                item.path, self._colors[item.type])

    def _create_list_items(self, locations):
        """Create a list of items (using pages for results to speed up)."""
        #The list is regenerated when the locate metadata is updated
        #for example: open project, etc.
        #Create the list items
        begin = self.items_in_page
        self.items_in_page += self.page_items_step
        locations_view = [x for x in locations[begin:self.items_in_page]]
        return locations_view

    def filter(self):
        self._line_jump = -1
        self.items_in_page = 0

        filterOptions = self.filterPrefix.split(self.__prefix.lstrip())
        if filterOptions[0] == '':
            del filterOptions[0]

        if len(filterOptions) == 0:
            self.tempLocations = self.locate_symbols.get_locations()
        elif len(filterOptions) == 1:
            self.tempLocations = [
                x for x in self.locate_symbols.get_locations()
                if x.comparison.lower().find(filterOptions[0].lower()) > -1]
        else:
            index = 0
            if not self.tempLocations and (self.__pre_filters == filterOptions):
                self.tempLocations = self.__pre_results
                return self._create_list_items(self.tempLocations)
            while index < len(filterOptions):
                filter_action = self._filter_actions.get(
                    filterOptions[index], self._filter_generic)
                if filter_action is None:
                    break
                index = filter_action(filterOptions, index)
            if self.tempLocations:
                self.__pre_filters = filterOptions
                self.__pre_results = self.tempLocations
        return self._create_list_items(self.tempLocations)

    def _filter_generic(self, filterOptions, index):
        at_start = (index == 0)
        if at_start:
            self.tempLocations = [
                x for x in self.locate_symbols.get_locations()
                if x.type == filterOptions[0] and
                x.comparison.lower().find(filterOptions[1].lower()) > -1]
        else:
            currentItem = self._root.currentItem()
            if (filterOptions[index - 2] == locator.FILTERS['classes'] and
                    currentItem):
                symbols = self.locate_symbols.get_symbols_for_class(
                    currentItem[2], currentItem[1])
                self.tempLocations = symbols
            elif currentItem:
                global mapping_symbols
                self.tempLocations = locator.mapping_symbols.get(
                    currentItem[2], [])
            self.tempLocations = [x for x in self.tempLocations
                                  if x.type == filterOptions[index] and
                                  x.comparison.lower().find(
                                      filterOptions[index + 1].lower()) > -1]
        return index + 2

    def _filter_this_file(self, filterOptions, index):
        at_start = (index == 0)
        if at_start:
            main_container = IDE.get_service('main_container')
            editorWidget = None
            if main_container:
                editorWidget = main_container.get_current_editor()
            index += 2
            if editorWidget:
                exts = settings.SYNTAX.get('python')['extension']
                file_ext = file_manager.get_file_extension(
                    editorWidget.file_path)
                if file_ext in exts:
                    filterOptions.insert(0, locator.FILTERS['files'])
                else:
                    filterOptions.insert(0, locator.FILTERS['non-python'])
                filterOptions.insert(1, editorWidget.file_path)
                self.tempLocations = \
                    self.locate_symbols.get_this_file_symbols(
                        editorWidget.file_path)
                search = filterOptions[index + 1].lstrip().lower()
                self.tempLocations = [x for x in self.tempLocations
                                      if x.comparison.lower().find(search) > -1]
        else:
            del filterOptions[index + 1]
            del filterOptions[index]
        return index

    def _filter_tabs(self, filterOptions, index):
        at_start = (index == 0)
        if at_start:
            ninjaide = IDE.get_service('ide')
            opened = ninjaide.filesystem.get_files()
            self.tempLocations = [
                locator.ResultItem(
                    locator.FILTERS['files'],
                    opened[f].file_name, opened[f].file_path) for f in opened]
            search = filterOptions[index + 1].lstrip().lower()
            self.tempLocations = [
                x for x in self.tempLocations
                if x.comparison.lower().find(search) > -1]
            index += 2
        else:
            del filterOptions[index + 1]
            del filterOptions[index]
        return index

    def _filter_lines(self, filterOptions, index):
        at_start = (index == 0)
        if at_start:
            main_container = IDE.get_service('main_container')
            editorWidget = None
            if main_container:
                editorWidget = main_container.get_current_editor()
            index = 2
            if editorWidget:
                exts = settings.SYNTAX.get('python')['extension']
                file_ext = file_manager.get_file_extension(
                    editorWidget.file_path)
                if file_ext in exts:
                    filterOptions.insert(0, locator.FILTERS['files'])
                else:
                    filterOptions.insert(0, locator.FILTERS['non-python'])
                filterOptions.insert(1, editorWidget.file_path)
            self.tempLocations = [
                x for x in self.locate_symbols.get_locations()
                if x.type == filterOptions[0] and
                x.path == filterOptions[1]]
        if filterOptions[index + 1].isdigit():
            self._line_jump = int(filterOptions[index + 1]) - 1
        return index + 2

    #def keyPressEvent(self, event):
        #if event.key() == Qt.Key_Space:
            #item = self.popup.listWidget.currentItem()
            #self.setText(item.data.comparison)
            #return

        #super(LocatorCompleter, self).keyPressEvent(event)
        #currentRow = self.popup.listWidget.currentRow()
        #if event.key() == Qt.Key_Down:
            #count = self.popup.listWidget.count()
            ##If the current position is greater than the amount of items in
            ##the list - 6, then try to fetch more items in the list.
            #if currentRow >= (count - 6):
                #locations = self._create_list_widget_items(self.tempLocations)
                #self.popup.fetch_more(locations)
            ##While the current position is lower that the list size go to next
            #if currentRow != count - 1:
                #self.popup.listWidget.setCurrentRow(
                    #self.popup.listWidget.currentRow() + 1)
        #elif event.key() == Qt.Key_Up:
            ##while the current position is greater than 0, go to previous
            #if currentRow > 0:
                #self.popup.listWidget.setCurrentRow(
                    #self.popup.listWidget.currentRow() - 1)
        #elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            ##If the user press enter, go to the item selected
            #item = self.popup.listWidget.currentItem()
            #self._go_to_location(item)

    #def _go_to_location(self, item):
        #if type(item) is LocateItem:
            #self._open_item(item.data)
        #self.emit(SIGNAL("hidden()"))

    def _open_item(self, data):
        """Open the item received."""
        main_container = IDE.get_service('main_container')
        if not main_container:
            return
        jump = data.lineno if self._line_jump == -1 else self._line_jump
        main_container.open_file(data.path, jump, None, True)

    def hideEvent(self, event):
        super(LocatorWidget, self).hideEvent(event)
        # clean
        self._avoid_refresh = True
        self._root.cleanText()
        self._root.clear()
        self.reset_values()