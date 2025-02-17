from __future__ import annotations

import dataclasses
import enum
import logging
from collections.abc import Sequence
from functools import cache
from types import SimpleNamespace
from typing import Any

from qt_material_icons import MaterialIcon
from qtpy import QtWidgets, QtGui, QtCore

from opm import utils
from .filter import Filter

StateFlag = QtWidgets.QStyle.StateFlag
CheckState = QtCore.Qt.CheckState
ItemDataRole = QtCore.Qt.ItemDataRole
ItemFlag = QtCore.Qt.ItemFlag

logger = logging.getLogger(__name__)

ATTRIBUTE_SEPARATOR = '.'


def get_value(obj: Any, name: str) -> Any:
    """
    Return the value from an object's attribute. Attribute name can be separated by
    a dot.
    """
    attributes = name.split(ATTRIBUTE_SEPARATOR) if name else ()
    value = obj
    for attribute in attributes:
        value = getattr(value, attribute, None)
    return value


def set_value(obj: Any, name: str, value: Any) -> None:
    """
    Set the attribute on an object, creating an object structure if needed.
    """
    attributes = name.split(ATTRIBUTE_SEPARATOR)
    for attribute in attributes[:-1]:
        obj = getattr(obj, attribute, None)
        if obj is None:
            namespace = SimpleNamespace()
            setattr(obj, attribute, namespace)
            obj = namespace
    setattr(obj, attributes[-1], value)


@dataclasses.dataclass
class Field:
    name: str
    label: str = ''
    editable: bool = False
    checkable: bool = False

    def __post_init__(self) -> None:
        if not self.label:
            self.label = utils.title(self.name)

    def create_item(self, value: Any) -> QtGui.QStandardItem:
        item = QtGui.QStandardItem()
        flags = ItemFlag.ItemIsEnabled | ItemFlag.ItemIsSelectable
        if self.editable:
            flags |= ItemFlag.ItemIsEditable
        if self.checkable:
            flags |= ItemFlag.ItemIsUserCheckable
            item.setCheckState(CheckState.Unchecked)
        item.setFlags(flags)
        item.setData(value, ItemDataRole.DisplayRole)
        return item

    def refresh(self, value: Any, index: QtCore.QModelIndex) -> None:
        index.model().setData(index, value, ItemDataRole.DisplayRole)


class BoolField(Field):
    def create_item(self, value: bool) -> QtGui.QStandardItem:
        item = QtGui.QStandardItem()
        item.setFlags(ItemFlag.ItemIsEnabled | ItemFlag.ItemIsSelectable)
        if self.editable:
            item.setFlags(item.flags() or ItemFlag.ItemIsUserCheckable)
        item.setCheckState(CheckState.Checked if value else CheckState.Unchecked)
        item.setData(value, ItemDataRole.UserRole)
        return item

    def refresh(self, value: bool, index: QtCore.QModelIndex) -> None:
        model = index.model()
        if isinstance(model, QtGui.QStandardItemModel):
            item = model.itemFromIndex(index)
            item.setCheckState(CheckState.Checked if value else CheckState.Unchecked)
        index.model().setData(index, value, ItemDataRole.UserRole)


class EnumField(Field):
    def create_item(self, value: enum.Enum | None) -> QtGui.QStandardItem:
        item = QtGui.QStandardItem()
        item.setFlags(ItemFlag.ItemIsEnabled | ItemFlag.ItemIsSelectable)
        if isinstance(value, enum.Enum):
            item.setData(value.value, ItemDataRole.DisplayRole)
        return item

    def refresh(self, value: enum.Enum | None, index: QtCore.QModelIndex) -> None:
        value = value.value if isinstance(value, enum.Enum) else None
        index.model().setData(index, value.value, ItemDataRole.DisplayRole)


@dataclasses.dataclass
class ImageField(Field):
    def create_item(self, value: str) -> QtGui.QStandardItem:
        item = QtGui.QStandardItem()
        item.setFlags(ItemFlag.ItemIsEnabled | ItemFlag.ItemIsSelectable)
        if not value:
            value = get_default_thumbnail()
        item.setData(value, ItemDataRole.DecorationRole)
        return item

    def refresh(self, value: str, index: QtCore.QModelIndex) -> None:
        if not value:
            value = get_default_thumbnail()
        index.model().setData(index, value, ItemDataRole.DecorationRole)


@dataclasses.dataclass
class Group:
    name: str
    label: str = ''
    sort: str = ''
    order: QtCore.Qt.SortOrder = QtCore.Qt.SortOrder.DescendingOrder
    container: bool = True

    def __post_init__(self) -> None:
        if not self.label:
            self.label = utils.title(self.name)


class Container:
    def __init__(self, elements: Sequence, name: str) -> None:
        if elements:
            element = elements[0]
            value = get_value(element, name)
            set_value(self, name, value)


class ElementModel(QtGui.QStandardItemModel):
    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

        self._group = None
        self._fields: list[Field] = []

    def group(self) -> Group | None:
        return self._group

    def set_group(self, group: Group | None) -> None:
        """
        Sets the group for the model.

        This only allows setting one group, if nested groups are desired, create an
        interface that allows to set multiple groups in a row (hierarchy) where each row
        takes (name, sort, order, container). Then build a hierarchy for every group.
        """
        self._group = group

        elements = [e for e in self.elements() if not isinstance(e, Container)]

        self.clear()
        if group is None:
            for element in elements:
                self.append_element(element)
            return

        stacks = {}
        for element in elements:
            value = get_value(element, group.name)
            stack = stacks.get(value, [])
            stack.append(element)
            stacks[value] = stack

        for stack in stacks.values():
            if not stack:
                continue
            reverse = group.order == QtCore.Qt.SortOrder.AscendingOrder
            stack.sort(key=lambda obj: get_value(obj, group.sort), reverse=reverse)
            if group.container:
                container = Container(stack, group.name)
                parent_index = self.append_element(container)
                for element in stack:
                    self.append_element(element, parent_index)
            else:
                parent_index = self.append_element(stack[-1])
                for element in stack[:-1]:
                    self.append_element(element, parent_index)

    def clear(self) -> None:
        super().clear()
        # NOTE: Clearing the model also clears the headers.
        self.refresh_header()

    def fields(self) -> tuple[Field, ...]:
        return tuple(self._fields)

    def add_field(self, field: Field) -> None:
        self._fields.append(field)
        self.refresh_header()

    def remove_field(self, field: Field) -> None:
        if field in self._fields:
            column = self._fields.index(field)
            self.removeColumn(column)
            self._fields.remove(field)
            self.refresh_header()

    def element(self, index: QtCore.QModelIndex) -> Any:
        data = self.data(index.siblingAtColumn(0), ItemDataRole.UserRole)
        return data

    def elements(self, parent: QtCore.QModelIndex | None = None) -> list:
        if parent is None:
            parent = QtCore.QModelIndex()
        elements = []
        for row in range(self.rowCount(parent)):
            index = self.index(row, 0, parent)
            if not index.isValid():  # optimization
                continue
            data = index.data(ItemDataRole.UserRole)
            if data is not None:
                elements.append(data)
            elements.extend(self.elements(index))
        return elements

    def append_element(
        self,
        obj: Any,
        parent: QtCore.QModelIndex | None = None,
    ) -> QtCore.QModelIndex:

        parent_item = self.itemFromIndex(parent) if parent else None
        if parent_item is None:
            parent_item = self.invisibleRootItem()

        items = []
        for field in self._fields:
            value = get_value(obj, field.name)
            item = field.create_item(value)
            items.append(item)

        if not items:
            return QtCore.QModelIndex()

        item = items[0]
        item.setData(obj, ItemDataRole.UserRole)
        parent_item.appendRow(items)
        return item.index()

    def remove_element(self, element: Any) -> None:
        index = self.find_index(element)
        if not index:
            return

        # Re-parent child rows
        item = self.itemFromIndex(index)
        parent = item.parent()
        for row in range(item.rowCount()):
            items = [item.child(row, column) for column in range(item.columnCount())]
            parent.appendRow(items)

        self.removeRow(index.row())
        if self._group:
            self.set_group(self._group)

    def find_index(
        self,
        value: Any,
        role: ItemDataRole = ItemDataRole.UserRole,
        parent: QtCore.QModelIndex | None = None,
    ) -> QtCore.QModelIndex:
        if parent is None:
            parent = QtCore.QModelIndex()
        index = QtCore.QModelIndex()
        for row in range(self.rowCount(parent)):
            index = self.index(row, 0, parent)
            if not index.isValid():
                continue
            if value == self.data(index, role):
                break
            index = self.find_index(value, role, index)
            if index.isValid():
                break
        return index

    def refresh_index(self, index: QtCore.QModelIndex) -> None:
        """
        Refresh the DisplayRole of all items in the index's row.
        """
        element = self.element(index)
        for column, field in enumerate(self._fields):
            item_index = index.siblingAtColumn(column)
            value = get_value(element, field.name)
            field.refresh(value, item_index)

    def refresh_element(self, element: Any) -> None:
        """
        Refresh the DisplayRole of all items in the element's row.
        """
        index = self.find_index(element)
        if index.isValid():
            self.refresh_index(index)

    def refresh_header(self) -> None:
        labels = [field.label for field in self._fields]
        self.setHorizontalHeaderLabels(labels)

    def setData(
        self,
        index: QtCore.QModelIndex,
        value: Any,
        role: ItemDataRole = ItemDataRole.EditRole,
    ) -> bool:
        result = super().setData(index, value, role)

        # Update an element when a user changes the data in the delegate.
        if role == ItemDataRole.EditRole:
            if element := self.element(index):
                field = self._fields[index.column()]
                value = self.data(index, ItemDataRole.EditRole)
                set_value(element, field.name, value)
                self.refresh_index(index)

        return result


class ProxyModel(QtCore.QSortFilterProxyModel):
    """
    QSortFilterProxyModel with 'autoAcceptChildRows' that has been added in Qt6.
    """

    _autoAcceptChildRows = False

    def autoAcceptChildRows(self) -> bool:  # noqa
        return self._autoAcceptChildRows

    def setAutoAcceptChildRows(self, value: bool):  # noqa
        self._autoAcceptChildRows = value

    def filterAcceptsRow(
        self, source_row: int, source_parent: QtCore.QModelIndex
    ) -> bool:
        if super().filterAcceptsRow(source_row, source_parent):
            return True
        if self.autoAcceptChildRows() and source_parent.isValid():
            source_row = source_parent.row()
            source_parent = source_parent.parent()
            return self.filterAcceptsRow(source_row, source_parent)
        return False


class FilterProxyModel(ProxyModel):
    class AcceptRule(enum.Enum):
        DEFAULT = None
        ALLOW_ALL = enum.auto()
        ALLOW_NONE = enum.auto()

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

        self._filters: dict[int, Filter] = {}
        self._sort_roles: dict[int, ItemDataRole] = {}
        self._accept_rule = FilterProxyModel.AcceptRule.DEFAULT

    def filterAcceptsRow(
        self, source_row: int, source_parent: QtCore.QModelIndex
    ) -> bool:
        if self._accept_rule == FilterProxyModel.AcceptRule.DEFAULT:
            pass
        elif self._accept_rule == FilterProxyModel.AcceptRule.ALLOW_ALL:
            return True
        elif self._accept_rule == FilterProxyModel.AcceptRule.ALLOW_NONE:
            return False

        if not super().filterAcceptsRow(source_row, source_parent):
            return False

        for column, field_filter in self._filters.items():
            if field_filter.match:
                index = self.sourceModel().index(source_row, column, source_parent)
                value = index.data(field_filter.role)
                if not field_filter.accepts(value):
                    return False
        return True

    def lessThan(
        self, source_left: QtCore.QModelIndex, source_right: QtCore.QModelIndex
    ) -> bool:
        # NOTE: The default implementation only handles built-in types.
        value_left = source_left.data(self.sort_role(source_left.column()))
        value_right = source_right.data(self.sort_role(source_right.column()))
        try:
            return value_left < value_right
        except TypeError:
            return False

    def accept_rule(self) -> FilterProxyModel.AcceptRule:
        return self._accept_rule

    def set_accept_rule(self, accept_rule: FilterProxyModel.AcceptRule) -> None:
        if accept_rule != self._accept_rule:
            self._accept_rule = accept_rule
            self.invalidateFilter()

    def filter(self, column: int) -> Filter | None:
        return self._filters.get(column)

    def set_filter(self, column: int, filter_: Filter) -> None:
        self._filters[column] = filter_

    def set_filters(self, filters: dict) -> None:
        self._filters = filters

    def remove_filter(self, column: int) -> None:
        if column in self._filters:
            del self._filters[column]

    def sort_role(self, column: int) -> int:
        role = self._sort_roles.get(column, ItemDataRole.DisplayRole)
        return role

    def set_sort_role(self, column: int, role: ItemDataRole) -> None:
        self._sort_roles[column] = role


class StyledItemDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._padding = QtCore.QSize(0, 4)

    def sizeHint(
        self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex
    ) -> QtCore.QSize:
        size_hint = super().sizeHint(option, index)
        size_hint += self._padding
        return size_hint

    def padding(self) -> QtCore.QSize:
        return self._padding

    def set_padding(self, padding: QtCore.QSize) -> None:
        self._padding = padding


class ImageDelegate(StyledItemDelegate):
    """
    Delegate to display image thumbnails.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._aspect_ratio = 16 / 9
        self._max_width = 192
        self._width = 64
        self._size = self._get_size()
        self._style = self._get_style()

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: QtCore.QModelIndex,
    ) -> None:
        widget = self.parent()
        if not isinstance(widget, QtWidgets.QWidget):
            return

        self.initStyleOption(option, index)
        painter.save()
        painter.setClipRect(option.rect)

        # Panel
        self._style.drawPrimitive(
            QtWidgets.QStyle.PrimitiveElement.PE_PanelItemViewItem,
            option,
            painter,
            widget,
        )

        # Pixmap
        pixmap_rect = QtCore.QRect(option.rect)
        pixmap_rect.setSize(self._size)
        mode = QtGui.QIcon.Mode.Normal
        if not option.state & StateFlag.State_Enabled:
            mode = QtGui.QIcon.Mode.Disabled
        elif option.state & StateFlag.State_Selected:
            mode = QtGui.QIcon.Mode.Selected

        if option.state & StateFlag.State_Open == StateFlag.State_Open:
            state = QtGui.QIcon.State.On
        else:
            state = QtGui.QIcon.State.Off
        option.icon.paint(painter, pixmap_rect, option.decorationAlignment, mode, state)

        # Focus Rect
        if option.state & StateFlag.State_HasFocus:
            option_focus = QtWidgets.QStyleOptionFocusRect()
            option_focus.rect = option.rect
            option_focus.state = option.state
            option_focus.state |= StateFlag.State_KeyboardFocusChange
            option_focus.state |= StateFlag.State_Item

            if option.state & StateFlag.State_Enabled:
                color_group = QtGui.QPalette.ColorGroup.Normal
            else:
                color_group = QtGui.QPalette.ColorGroup.Disabled

            if option.state & StateFlag.State_Selected:
                role = QtGui.QPalette.ColorRole.Highlight
            else:
                role = QtGui.QPalette.ColorRole.Window
            option_focus.backgroundColor = option.palette.color(color_group, role)
            self._style.drawPrimitive(
                QtWidgets.QStyle.PrimitiveElement.PE_FrameFocusRect,
                option_focus,
                painter,
                widget,
            )

        painter.restore()

    def setParent(self, parent: QtWidgets.QWidget) -> None:
        super().setParent(parent)
        self._style = self._get_style()

    def sizeHint(
        self, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex
    ) -> QtCore.QSize:
        return self._size

    def aspect_ratio(self) -> float:
        return self._aspect_ratio

    def set_aspect_ratio(self, aspect_ratio: float) -> None:
        self._aspect_ratio = aspect_ratio
        self._size = self._get_size()

    def max_width(self) -> int:
        return self._max_width

    def set_max_width(self, max_width: int) -> None:
        self._max_width = max_width
        self._size = self._get_size()

    def width(self) -> int:
        return self._width

    def set_width(self, width: int) -> None:
        self._width = min(width, self._max_width)
        self._size = self._get_size()

    def _get_size(self) -> QtCore.QSize:
        return QtCore.QSize(self._width, int(self._width / self._aspect_ratio))

    def _get_style(self) -> QtWidgets.QStyle:
        if parent := self.parent():
            return parent.style()
        else:
            return QtWidgets.QApplication.style()


class MaterialStyle(QtWidgets.QProxyStyle):
    def drawControl(
        self,
        element: QtWidgets.QStyle.ControlElement,
        option: QtWidgets.QStyleOption,
        painter: QtGui.QPainter,
        widget: QtWidgets.QWidget | None = None,
    ) -> None:
        if element == QtWidgets.QStyle.ControlElement.CE_HeaderSection:
            frame_option = QtWidgets.QStyleOptionFrame()
            frame_option.rect = option.rect
            # frame_option.rect.adjust(0, -1, 0, 1)
            frame_option.frameShape = QtWidgets.QFrame.Shape.StyledPanel
            element = QtWidgets.QStyle.ControlElement.CE_ShapedFrame
            super().drawControl(element, frame_option, painter, widget)
            return
        elif element == QtWidgets.QStyle.ControlElement.CE_HeaderLabel:
            option.rect.adjust(8, 0, -8, 0)
        super().drawControl(element, option, painter, widget)


class ElementTree(QtWidgets.QTreeView):
    selection_changed: QtCore.Signal = QtCore.Signal()
    context_menu_requested: QtCore.Signal = QtCore.Signal(QtCore.QModelIndex)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.setSortingEnabled(True)
        self.setItemDelegate(StyledItemDelegate())
        self.header().setMinimumHeight(32)
        self.header().setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.header().setStretchLastSection(True)
        self.header().sectionResized.connect(self._header_resized)

        # self.proxy_style = MaterialStyle(self.header().style().objectName())
        # self.proxy_style.setParent(self.header())
        # self.header().setStyle(self.proxy_style)

    def selectionChanged(
        self, selected: QtCore.QItemSelection, deselected: QtCore.QItemSelection
    ) -> None:
        self.selection_changed.emit()
        super().selectionChanged(selected, deselected)

    def resize_columns(self, padding: int = 8) -> None:
        model = self.model()
        if model and model.rowCount():
            self.expandAll()
            for column in range(model.columnCount()):
                self.resizeColumnToContents(column)
                if padding:
                    width = self.columnWidth(column) + padding
                    self.setColumnWidth(column, width)
            self.collapseAll()

    def _header_resized(self, column: int, old: int, new: int) -> None:
        delegate = self.itemDelegateForColumn(column)
        if isinstance(delegate, ImageDelegate):
            delegate.set_width(new)
            if new < delegate.max_width():
                for row in range(self.model().rowCount()):
                    index = self.model().index(row, column)
                    delegate.sizeHintChanged.emit(index)


@cache
def get_default_thumbnail() -> QtGui.QPixmap:
    size = QtCore.QSize(192, 108)
    icon_size = QtCore.QSize(48, 48)

    pixmap = QtGui.QPixmap(size)
    palette = QtWidgets.QApplication.palette()
    color = palette.color(
        QtGui.QPalette.ColorGroup.Normal, QtGui.QPalette.ColorRole.Shadow
    )
    pixmap.fill(color)

    icon = MaterialIcon('image')
    icon_pixmap = icon.pixmap(size=icon_size, mode=QtGui.QIcon.Mode.Disabled)

    x = (size.width() - icon_size.width()) // 2
    y = (size.height() - icon_size.height()) // 2
    origin = QtCore.QPoint(x, y)

    painter = QtGui.QPainter(pixmap)
    painter.drawPixmap(origin, icon_pixmap)
    painter.end()
    return pixmap
