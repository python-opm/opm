from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial

from qt_material_icons import MaterialIcon
from qtpy import QtCore, QtGui, QtWidgets

from .filter import FilterListWidget, FilterWidget
from .tree import (
    ElementTree,
    Field,
    ElementModel,
    FilterProxyModel,
    Group,
)

logger = logging.getLogger(__name__)


@dataclass
class Column:
    field: Field
    delegate: QtWidgets.QItemDelegate | None = None
    filter_widget: FilterWidget | None = None
    visible: bool = True
    enabled: bool = True


class SearchLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setPlaceholderText('Search ...')
        self.setClearButtonEnabled(True)
        clear_button = self.findChild(QtWidgets.QToolButton)
        if isinstance(clear_button, QtWidgets.QToolButton):
            icon = MaterialIcon('close')
            clear_button.setIcon(icon)


class Browser(QtWidgets.QWidget):
    selection_changed: QtCore.Signal = QtCore.Signal(object)
    context_menu_requested: QtCore.Signal = QtCore.Signal(QtGui.QContextMenuEvent)
    model_update_requested: QtCore.Signal = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._columns = []
        self._show_toolbar = True

        self._init_model()
        self._init_ui()

    def _init_model(self) -> None:
        self.model = ElementModel()
        # Force the disabled columns to be hidden
        self.model.columnsInserted.connect(self._refresh_columns)
        self.proxy = FilterProxyModel()
        self.proxy.setSourceModel(self.model)

    def _init_ui(self) -> None:
        self._layout = QtWidgets.QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(QtCore.QMargins())

        self.tree = ElementTree()
        self.tree.setModel(self.proxy)
        self.tree.selection_changed.connect(self._selection_changed)
        self._layout.addWidget(self.tree)

    def clear(self) -> None:
        self.blockSignals(True)
        self.model.clear()
        # NOTE: Clearing the model refreshes the headers, so refresh_columns.
        self.refresh()
        self.blockSignals(False)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        widget = self.childAt(event.pos())
        while widget:
            if widget == self.tree.viewport():
                self.context_menu_requested.emit(event)
                event.accept()
                return
            widget = widget.parentWidget()
        super().contextMenuEvent(event)

    def add_column(
        self,
        field: Field,
        delegate: QtWidgets.QStyledItemDelegate | None = None,
        filter_widget: FilterWidget | None = None,
        visible: bool = True,
        enabled: bool = True,
    ) -> None:
        column = len(self._columns)
        self._columns.append(Column(field, delegate, filter_widget, visible, enabled))
        self.model.add_field(field)

        if delegate:
            delegate.setParent(self.tree)
            self.tree.setItemDelegateForColumn(column, delegate)

        if filter_widget:
            self.proxy.set_filter(column, filter_widget.filter())

        self.tree.setColumnHidden(column, not visible or not enabled)

    def remove_column(self, column: int) -> None:
        self.proxy.remove_filter(column)
        if delegate := self.tree.itemDelegateForColumn(column):
            delegate.deleteLater()
        if column < len(self._columns):
            field = self._columns[column].field
            self.model.remove_field(field)
            self._columns.pop(column)

    def columns(self) -> tuple[Column, ...]:
        return tuple(self._columns)

    def selected_elements(self) -> tuple:
        elements = []
        indexes = self.tree.selectionModel().selectedRows()
        for index in indexes:
            model_index = self.proxy.mapToSource(index)
            elements.append(self.model.element(model_index))
        return tuple(elements)

    def set_selected_elements(self, elements: Sequence) -> None:
        selection_model = self.tree.selectionModel()
        selection_model.clearSelection()
        for element in elements:
            model_index = self.model.find_index(element)
            proxy_index = self.proxy.mapFromSource(model_index)
            command = (
                QtCore.QItemSelectionModel.SelectionFlag.Select
                | QtCore.QItemSelectionModel.SelectionFlag.Rows
            )
            selection_model.select(proxy_index, command)
            self.tree.expand(proxy_index)
            self.tree.scrollTo(proxy_index)

    def set_sort_order(self, order: QtCore.Qt.SortOrder) -> None:
        header = self.tree.header()
        column = header.sortIndicatorSection()
        self.tree.sortByColumn(column, order)

    def refresh(self) -> None:
        self._refresh_columns()
        self.tree.resize_columns()

    def _refresh_columns(self) -> None:
        for i, column in enumerate(self._columns):
            self.tree.setColumnHidden(i, not (column.enabled and column.visible))

    def _selection_changed(self) -> None:
        proxy_indexes = self.tree.selectionModel().selectedRows()
        indexes = tuple(self.proxy.mapToSource(index) for index in proxy_indexes)
        if indexes:
            element = self.model.element(indexes[0])
        else:
            element = None
        self.selection_changed.emit(element)


class FilterBrowser(Browser):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._groups = ()
        self._group = None

        self._init_toolbar()
        self._init_filters()

    def _init_ui(self) -> None:
        self._layout = QtWidgets.QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(QtCore.QMargins())

        self.toolbar_layout = QtWidgets.QHBoxLayout()
        self._layout.addLayout(self.toolbar_layout)

        self.splitter = QtWidgets.QSplitter()
        self._layout.addWidget(self.splitter)
        self._layout.setStretch(1, 1)

        self.tree = ElementTree()
        self.tree.setAlternatingRowColors(True)
        self.tree.setModel(self.proxy)
        self.splitter.addWidget(self.tree)

        self.filter_list = FilterListWidget()
        self.splitter.addWidget(self.filter_list)
        self.splitter.setStretchFactor(0, 1)

        self.splitter.setSizes((1, 0))

        self.splitter.splitterMoved.connect(self._splitter_moved)

    def _init_toolbar(self) -> None:
        # Sort
        sort_button = QtWidgets.QPushButton()
        sort_button.setAutoDefault(False)
        sort_button.setText('Sort')
        sort_button.setIcon(MaterialIcon('sort'))

        menu = QtWidgets.QMenu(parent=sort_button)
        sort_button.setMenu(menu)

        action = QtWidgets.QAction('Ascending', parent=sort_button)
        action.setIcon(MaterialIcon('keyboard_arrow_up'))
        func = partial(self.set_sort_order, QtCore.Qt.SortOrder.AscendingOrder)
        action.triggered.connect(func)
        menu.addAction(action)
        action = QtWidgets.QAction('Descending', parent=sort_button)
        action.setIcon(MaterialIcon('keyboard_arrow_down'))
        func = partial(self.set_sort_order, QtCore.Qt.SortOrder.DescendingOrder)
        action.triggered.connect(func)
        menu.addAction(action)

        self.toolbar_layout.addWidget(sort_button)

        # Group
        self.groups_button = QtWidgets.QPushButton()
        self.groups_button.setAutoDefault(False)
        self.groups_button.setText('Group')
        self.groups_button.setIcon(MaterialIcon('view_agenda'))
        self.groups_button.setVisible(False)
        self.toolbar_layout.addWidget(self.groups_button)

        # Columns
        self.fields_button = QtWidgets.QPushButton()
        self.fields_button.setAutoDefault(False)
        self.fields_button.setText('Columns')
        self.fields_button.setIcon(MaterialIcon('view_column'))
        self.fields_button.setVisible(False)
        self.toolbar_layout.addWidget(self.fields_button)

        # Stretch
        self.toolbar_layout.addStretch()

        # Search
        self.search_line = SearchLineEdit()
        self.search_line.setMaximumWidth(256)
        self.search_line.textChanged.connect(self._search_text_changed)
        self.toolbar_layout.addWidget(self.search_line)

        # Filters
        self.filter_button = QtWidgets.QToolButton()
        self.filter_button.setCheckable(True)
        self.filter_button.setText('Filters')
        self.filter_button.setIcon(MaterialIcon('filter_list'))
        self.filter_button.toggled.connect(self.toggle_filter_list)
        self.toolbar_layout.addWidget(self.filter_button)

    def _init_filters(self) -> None:
        self.filter_list.set_model(self.model)
        self.filter_list.filter_changed.connect(self.proxy.invalidateFilter)

    def add_column(
        self,
        field: Field,
        delegate: QtWidgets.QStyledItemDelegate | None = None,
        filter_widget: FilterWidget | None = None,
        visible: bool = True,
        enabled: bool = True,
    ) -> None:
        super().add_column(
            field=field,
            delegate=delegate,
            filter_widget=filter_widget,
            visible=visible,
            enabled=enabled,
        )

        if filter_widget:
            column = len(self._columns) - 1
            self.filter_list.add_filter_widget(column, filter_widget)

        self._refresh_fields_menu()

    def group(self) -> Group | None:
        return self._group

    def set_group(self, group: Group | None) -> None:
        if group == self._group:
            return
        self._group = group

        if group and group not in self._groups:
            self.set_groups((*self._groups, group))

        if menu := self.groups_button.menu():
            for action in menu.actions():
                if action.data() == group:
                    action.setChecked(True)
                    break

        self._update_group(group)

    def groups(self) -> tuple[Group, ...]:
        return self._groups

    def set_groups(self, groups: Sequence[Group]) -> None:
        if not isinstance(groups, tuple):
            groups = tuple(groups)
        self._groups = groups
        self._refresh_groups_menu()

    def set_column_visible(self, i: int, visible: bool = True) -> None:
        try:
            column = self._columns[i]
        except IndexError:
            return
        column.visible = visible
        self._refresh_fields_menu()

    def refresh(self) -> None:
        self.filter_list.refresh()
        if self._groups:
            self.model.set_group(self._group)
        super().refresh()

    def toggle_filter_list(self) -> None:
        try:
            collapsed = self.splitter.sizes()[1] == 0
        except IndexError:
            return
        if collapsed:
            size_hint = self.filter_list.minimumSizeHint()
            self.splitter.setSizes((1, size_hint.width()))
        else:
            self.splitter.setSizes((1, 0))

    def _refresh_fields_menu(self) -> None:
        self.fields_button.setVisible(bool(self._columns))
        if menu := self.fields_button.menu():
            for action in menu.actions():
                action.deleteLater()
        else:
            menu = QtWidgets.QMenu(parent=self.fields_button)
            self.fields_button.setMenu(menu)

        for i, column in enumerate(self._columns):
            if column.enabled:
                action = QtWidgets.QAction(column.field.label, parent=self)
                action.setCheckable(True)
                action.setChecked(column.visible)
                action.toggled.connect(partial(self._set_column_visible, i))
                menu.addAction(action)

        menu.addSeparator()
        action = QtWidgets.QAction('Show All', parent=self)
        action.triggered.connect(partial(self._set_all_columns_visible, True))
        menu.addAction(action)
        action = QtWidgets.QAction('Show None', parent=self)
        action.triggered.connect(partial(self._set_all_columns_visible, False))
        menu.addAction(action)

    def _refresh_groups_menu(self) -> None:
        self.groups_button.setVisible(bool(self._groups))
        if menu := self.groups_button.menu():
            for action in menu.actions():
                action.deleteLater()
        else:
            menu = QtWidgets.QMenu(parent=self.groups_button)
            self.groups_button.setMenu(menu)

        action_group = QtWidgets.QActionGroup(self)
        action = QtWidgets.QAction('None', parent=self)
        action.setCheckable(True)
        action_group.addAction(action)

        for group in self._groups:
            action = QtWidgets.QAction(group.label, parent=self)
            action.setCheckable(True)
            action.setData(group)
            action_group.addAction(action)

        for action in action_group.actions():
            group = action.data()
            action.setChecked(group == self._group)
            action.triggered.connect(partial(self._update_group, group))
            menu.addAction(action)

    def _set_column_visible(self, i: int, visible: bool = True) -> None:
        column = self._columns[i]
        column.visible = visible
        self.tree.setColumnHidden(i, not column.visible or not column.enabled)
        if column.visible and column.enabled:
            self.tree.resizeColumnToContents(i)

    def _set_all_columns_visible(self, visible: bool = True) -> None:
        for i, column in enumerate(self._columns):
            column.visible = visible
            self.tree.setColumnHidden(i, not column.visible or not column.enabled)
        self._refresh_fields_menu()

    def _update_group(self, group: Group | None) -> None:
        self._group = group
        self.model.set_group(group)
        # Updating model resets columns
        super().refresh()
        if group:
            for i, column in enumerate(self._columns):
                if column.field.name == group.sort:
                    self.proxy.sort(i, group.order)
                    break

    def _search_text_changed(self, text: str) -> None:
        self.proxy.setFilterWildcard(text)

    def _splitter_moved(self) -> None:
        try:
            collapsed = self.splitter.sizes()[1] == 0
        except IndexError:
            return
        if self.filter_button.isChecked() == collapsed:
            self.filter_button.blockSignals(True)
            self.filter_button.setChecked(not collapsed)
            self.filter_button.blockSignals(False)

    # def show_toolbar(self) -> bool:
    #     return self._show_toolbar
    #
    # def set_show_toolbar(self, show_toolbar: bool) -> None:
    #     self._show_toolbar = show_toolbar
    #     for i in range(self.toolbar_layout.count()):
    #         if item := self.toolbar_layout.itemAt(i):
    #             if widget := item.widget():
    #                 widget.setVisible(show_toolbar)
