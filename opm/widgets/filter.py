from __future__ import annotations
import logging
import operator
from collections.abc import Container
from typing import Any, Sequence, Optional, Callable

from qtpy import QtCore, QtGui, QtWidgets
from qt_material_icons import MaterialIcon

from qt_parameters import CollapsibleBox
from qt_parameters.scrollarea import VerticalScrollArea

logger = logging.getLogger(__name__)


def is_in(a: Any, b: Container) -> bool:
    return a in b


def is_not_in(a: Any, b: Container) -> bool:
    return a not in b


class Filter:
    value: Any = None
    match: Optional[Callable] = operator.eq
    role: QtCore.Qt.ItemDataRole = QtCore.Qt.ItemDataRole.DisplayRole
    inverted: bool = False

    def __repr__(self) -> str:
        match = self.match.__name__ if self.match else None
        return (
            f'{self.__class__.__name__}'
            f'(value={self.value!r}, '
            f'match={match!r}, '
            f'role={self.role})'
        )

    def accepts(self, value: Any) -> bool:
        if self.match is None or value is None:
            return True

        # Note: Allow values like 0 but not other falsy values.
        if self.value == 0:
            pass
        elif not self.value:
            return True
        return self.match(value, self.value) != self.inverted


class FilterWidget(CollapsibleBox):
    filter_changed: QtCore.Signal = QtCore.Signal(Filter)

    def __init__(
        self, title: str = '', parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(title, parent)

        self._filter = Filter()
        self._default: Any = None
        self._values: tuple = ()

    def _init_ui(self) -> None:
        super()._init_ui()

        self.set_box_style(CollapsibleBox.Style.BUTTON)
        self.set_collapsible(True)
        self.set_collapsed(True)
        self.setLayout(QtWidgets.QVBoxLayout())

        header_layout = self.header.layout()
        header_layout.setSpacing(0)

        invert_icon = MaterialIcon('block')
        palette = QtWidgets.QApplication.palette()
        color = palette.color(
            QtGui.QPalette.ColorGroup.Normal, QtGui.QPalette.ColorRole.WindowText
        )
        invert_icon.set_color(color, QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.On)
        color = palette.color(
            QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText
        )
        invert_icon.set_color(color, QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)

        self.invert_button = QtWidgets.QToolButton()
        self.invert_button.setIcon(invert_icon)
        self.invert_button.setAutoRaise(True)
        self.invert_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.invert_button.setCheckable(True)
        self.invert_button.toggled.connect(self.set_inverted)
        header_layout.insertWidget(header_layout.count() - 1, self.invert_button)

        self.reset_button = QtWidgets.QToolButton()
        self.reset_button.setIcon(MaterialIcon('undo'))
        self.reset_button.setAutoRaise(True)
        self.reset_button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self.reset)
        header_layout.insertWidget(header_layout.count() - 1, self.reset_button)

    def filter(self) -> Filter:
        return self._filter

    def set_filter(self, value: Filter) -> None:
        self._filter = value
        self.filter_changed.emit(self._filter)

    def inverted(self) -> bool:
        return self._filter.inverted

    def set_inverted(self, inverted: bool) -> None:
        if self._filter.inverted != inverted:
            self._filter.inverted = inverted
            self.filter_changed.emit(self._filter)

    def value(self) -> Any:
        return self._filter.value

    def set_value(self, value: Any) -> None:
        if self._filter.value != value:
            self._filter.value = value
            self.filter_changed.emit(self._filter)
            self._refresh()

    def values(self) -> tuple:
        return self._values

    def set_values(self, values: Sequence) -> None:
        values = tuple(value for value in values if value is not None)
        self._values = values

    def reset(self) -> None:
        self.set_value(self._default)
        self.set_inverted(False)

    def _refresh(self) -> None:
        has_changes = self._filter.value != self._default
        if has_changes:
            weight = QtGui.QFont.Weight.Bold
        else:
            weight = QtGui.QFont.Weight.Normal
        font = self.title_label.font()
        font.setWeight(weight)
        self.title_label.setFont(font)

        self.reset_button.setEnabled(has_changes)


class MultiFilterWidget(FilterWidget):
    def __init__(
        self, title: str = '', parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(title, parent)

        self._filter.match = is_in
        self._default: tuple = ()
        self._checkboxes: tuple[QtWidgets.QCheckBox, ...] = ()

    def set_value(self, value: Sequence) -> None:
        super().set_value(value)

        for checkbox, v in zip(self._checkboxes, self._values):
            checkbox.blockSignals(False)
            checkbox.setChecked(v in value)
            checkbox.blockSignals(False)

    def set_values(self, values: Sequence) -> None:
        super().set_values(values)
        self._update_checkboxes()

    def _checkbox_toggled(self) -> None:
        values = []
        for checkbox, value in zip(self._checkboxes, self._values):
            if checkbox.isChecked():
                values.append(value)
        super().set_value(tuple(values))

    def _clear_layout(self) -> None:
        while item := self.layout().takeAt(0):
            if widget := item.widget():
                widget.deleteLater()

    def _update_checkboxes(self) -> None:
        self._clear_layout()
        checkboxes = []
        for value in self._values:
            checkbox = QtWidgets.QCheckBox()
            checkbox.setText(str(value))
            if self._filter.value:
                checkbox.setChecked(self._filter.accepts(value))
            checkbox.toggled.connect(self._checkbox_toggled)
            checkboxes.append(checkbox)
            self.layout().addWidget(checkbox)
        self._checkboxes = tuple(checkboxes)


class FilterListWidget(VerticalScrollArea):
    filter_changed: QtCore.Signal = QtCore.Signal(Filter)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._model: QtGui.QStandardItemModel | None = None
        self._widgets: dict[int, FilterWidget] = {}

        self._init_ui()

    def _init_ui(self) -> None:
        widget = QtWidgets.QWidget()
        self.setWidget(widget)

        self._layout = QtWidgets.QVBoxLayout()
        self._layout.addStretch()
        widget.setLayout(self._layout)

    def minimumSizeHint(self) -> QtCore.QSize:
        size_hint = super().minimumSizeHint()
        size_hint.setWidth(max(size_hint.width(), 256))
        return size_hint

    def add_filter_widget(self, column: int, widget: FilterWidget) -> None:
        index = self._layout.count() - 1
        self._layout.insertWidget(index, widget)
        widget.filter_changed.connect(self.filter_changed.emit)
        self._widgets[column] = widget
        self.refresh_column(column)

    def remove_filter_widget(
        self, column: int = -1, widget: FilterWidget | None = None
    ) -> None:
        if column < 0:
            for c, w in self._widgets.items():
                if w == widget:
                    column = c
                    break
        widget = self._widgets.get(column)
        if widget:
            self._layout.removeWidget(widget)
            widget.deleteLater()

    def filter_widgets(self) -> tuple[FilterWidget, ...]:
        return tuple(self._widgets.values())  # noqa

    def filters(self) -> dict[int, Filter]:
        return {column: widget.filter() for column, widget in self._widgets.items()}

    def model(self) -> QtGui.QStandardItemModel:
        return self._model

    def set_model(self, model: QtGui.QStandardItemModel) -> None:
        self._model = model
        self.refresh()

    def refresh(self) -> None:
        for column, widget in self._widgets.items():
            self.refresh_column(column)

    def refresh_column(self, column: int) -> None:
        widget = self._widgets.get(column)
        if not widget or not self._model:
            return

        enabled = column < self._model.columnCount()
        if enabled:
            filter_role = widget.filter().role
            values = self._get_column_values(column, filter_role)
            widget.set_values(tuple(values))

        widget.setEnabled(enabled)
        widget.setVisible(enabled)

    def _get_column_values(
        self,
        column: int,
        role: QtCore.Qt.ItemDataRole = QtCore.Qt.ItemDataRole.DisplayRole,
        parent: QtCore.QModelIndex | None = None,
    ) -> tuple:
        """Returns all values of a column for a given role recursively."""
        values = set()
        if parent is None:
            parent = QtCore.QModelIndex()

        for row in range(self._model.rowCount(parent)):
            index = self._model.index(row, column, parent)
            value = index.data(role)
            values.add(value)
            sibling_index = index.siblingAtColumn(0)
            values.update(self._get_column_values(column, role, sibling_index))
        return tuple(values)
