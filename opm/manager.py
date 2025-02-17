import os
import venv

from qt_material_icons import MaterialIcon
from qt_parameters import CollapsibleBox
from qtpy import QtWidgets, QtCore, QtGui

from opm.widgets.browser import FilterBrowser
from opm.widgets.filter import FilterListWidget, FilterWidget


class ToolBar(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_ui()

    def _init_ui(self) -> None:
        self._layout = QtWidgets.QVBoxLayout()
        self.setLayout(self._layout)

    def add_button(
        self, text: str, icon: QtGui.QIcon | None = None
    ) -> QtWidgets.QToolButton:
        button = QtWidgets.QToolButton()
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setText(text)
        if icon:
            button.setIcon(icon)
            button.setIconSize(QtCore.QSize(24, 24))
        button.setCheckable(True)
        button.setAutoRaise(True)
        button.setSizePolicy(
            QtWidgets.QSizePolicy(
                QtWidgets.QSizePolicy.Policy.MinimumExpanding,
                QtWidgets.QSizePolicy.Policy.Minimum,
            )
        )
        self._layout.addWidget(button)
        return button

    def add_stretch(self) -> None:
        self._layout.addStretch()


class Manager(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle('Open Package Manager')
        self.resize(720, 480)

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        self.tool_bar = ToolBar()
        layout.addWidget(self.tool_bar)

        self.tool_bar.add_button(
            'Discover\nPackages', MaterialIcon('travel_explore', size=24)
        )
        self.tool_bar.add_button('Update\nPackages', MaterialIcon('sync', size=24))
        self.tool_bar.add_stretch()
        self.tool_bar.add_button('About', MaterialIcon('info', size=24))
        self.tool_bar.add_button('Settings', MaterialIcon('settings', size=24))

        filter_list_widget = FilterListWidget()
        filter_list_widget.add_filter_widget(0, FilterWidget('Type'))
        layout.addWidget(filter_list_widget)

        layout.addWidget(FilterBrowser())
        layout.setStretch(2, 1)
