"""Reusable parameter row: label + typed control + tooltip button."""
from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox, NoScrollDoubleSpinBox, NoScrollSpinBox, make_browse_button, open_file_dialog

log = get_logger(__name__)


class ParameterWidget(QWidget):
    """One parameter row driven by a parameter definition dict from parameters.yaml."""

    value_changed = pyqtSignal()

    def __init__(
        self,
        param: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._param = param
        self._control: QWidget | None = None
        self._browse_btn: QPushButton | None = None
        self._enable_check: QCheckBox | None = None
        self._custom_combo: NoScrollComboBox | None = None
        self._custom_w_spin: NoScrollSpinBox | None = None
        self._custom_h_spin: NoScrollSpinBox | None = None
        self._custom_dim_row: QWidget | None = None
        self._build()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def flag(self) -> str:
        return self._param.get("flag", "")

    @property
    def affects_preview(self) -> bool:
        return bool(self._param.get("affects_preview", False))

    @property
    def no_space(self) -> bool:
        return bool(self._param.get("no_space", False))

    @property
    def expert_only(self) -> bool:
        return bool(self._param.get("expert_only", False))

    def get_value(self) -> str:
        """Return CLI-ready value string, or '' to skip this flag."""
        if self._control is None and self._enable_check is not None:
            return "__flag__" if self._enable_check.isChecked() else ""
        c = self._control
        if c is None:
            return ""
        t = self._param.get("type", "string")
        if t == "boolean":
            return "" if not c.isChecked() else "__flag__"
        if t == "choice":
            if self._custom_combo is not None:
                data = self._custom_combo.currentData()
                if data == "custom" and self._custom_w_spin is not None and self._custom_h_spin is not None:
                    return f"{self._custom_w_spin.value()}x{self._custom_h_spin.value()}"
                return data or ""
            return c.currentData() or ""
        if t == "int":
            return str(c.value()) if c.value() != self._param.get("default", 0) else str(c.value())
        if t == "float":
            return str(c.value())
        if t in ("string", "file_path"):
            return c.text().strip()
        return ""

    def get_raw_value(self) -> Any:
        """Return Python-native value (bool, int, float, str)."""
        if self._control is None and self._enable_check is not None:
            return self._enable_check.isChecked()
        c = self._control
        if c is None:
            return None
        t = self._param.get("type", "string")
        if t == "boolean":
            return c.isChecked()
        if t == "choice":
            if self._custom_combo is not None:
                data = self._custom_combo.currentData()
                if data == "custom" and self._custom_w_spin is not None and self._custom_h_spin is not None:
                    return f"{self._custom_w_spin.value()}x{self._custom_h_spin.value()}"
                return data
            return c.currentData()
        if t == "int":
            return c.value()
        if t == "float":
            return c.value()
        if t in ("string", "file_path"):
            return c.text().strip()
        return None

    def set_value(self, v: Any) -> None:
        if self._control is None and self._enable_check is not None:
            self._enable_check.setChecked(bool(v))
            return
        c = self._control
        if c is None:
            return
        t = self._param.get("type", "string")
        try:
            if t == "boolean":
                c.setChecked(bool(v))
            elif t == "choice":
                combo = self._custom_combo if self._custom_combo is not None else c
                idx = combo.findData(str(v))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                elif self._custom_combo is not None and "x" in str(v):
                    parts = str(v).split("x", 1)
                    if len(parts) == 2:
                        try:
                            w, h = int(parts[0]), int(parts[1])
                            ci = self._custom_combo.findData("custom")
                            if ci >= 0:
                                self._custom_combo.setCurrentIndex(ci)
                            if self._custom_w_spin:
                                self._custom_w_spin.setValue(w)
                            if self._custom_h_spin:
                                self._custom_h_spin.setValue(h)
                        except ValueError:
                            pass
            elif t == "int":
                c.setValue(int(v))
            elif t == "float":
                c.setValue(float(v))
            elif t in ("string", "file_path"):
                c.setText(str(v))
                if t == "file_path" and self._enable_check is not None and str(v).strip():
                    self._enable_check.setChecked(True)
        except Exception as exc:
            log.warning("set_value(%s, %r): %s", self.flag, v, exc)

    @property
    def is_enabled_by_user(self) -> bool:
        """False when this is an expert param whose enable-checkbox is unchecked."""
        if self._enable_check is not None:
            return self._enable_check.isChecked()
        return True

    def set_user_enabled(self, checked: bool) -> None:
        """Programmatically set the expert enable-checkbox state."""
        if self._enable_check is not None:
            self._enable_check.setChecked(checked)

    def build_args(self) -> list[str]:
        """Build the list of CLI tokens for this parameter."""
        if not self.is_enabled_by_user:
            return []
        val = self.get_value()
        if not val:
            return []
        flag = self.flag
        if val == "__flag__":
            return [flag]
        if self.no_space:
            return [flag + val]
        return [flag, val]

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        name = self._param.get("name", self.flag)
        t    = self._param.get("type", "string")

        # Expert boolean: single checkbox serves as both enable-flag and control
        if self.expert_only and t == "boolean":
            self._enable_check = QCheckBox(name, self)
            self._enable_check.setChecked(False)
            self._enable_check.setStyleSheet("color: #c8c8c8;")
            self._enable_check.toggled.connect(self.value_changed)
            layout.addWidget(self._enable_check)
            # No separate control widget; tooltip button only
            tt_title = self._param.get("tooltip_title", name)
            tt_body  = self._param.get("tooltip_body", "No description available.")
            layout.addStretch()
            layout.addWidget(TooltipButton(tt_title, tt_body, self))
            return  # early exit — no _control needed

        # Expert non-boolean: enable-checkbox replaces label
        if self.expert_only:
            self._enable_check = QCheckBox(name + ":", self)
            self._enable_check.setChecked(False)
            self._enable_check.setFixedWidth(230)
            self._enable_check.setStyleSheet("color: #c8c8c8;")
            layout.addWidget(self._enable_check)
        else:
            lbl = QLabel(name + ":", self)
            lbl.setFixedWidth(230)
            lbl.setWordWrap(False)
            lbl.setStyleSheet("color: #c8c8c8;")
            layout.addWidget(lbl)

        # Control
        self._control = self._make_control()
        layout.addWidget(self._control, stretch=1)

        # Browse button for file_path
        if self._param.get("type") == "file_path":
            self._browse_btn = make_browse_button(self, "Browse…")
            self._browse_btn.clicked.connect(self._browse)
            layout.addWidget(self._browse_btn)

        # Tooltip button
        tt_title = self._param.get("tooltip_title", name)
        tt_body  = self._param.get("tooltip_body", "No description available.")
        btn = TooltipButton(tt_title, tt_body, self)
        layout.addWidget(btn)

        # Wire enable-checkbox to control enabled state
        if self._enable_check is not None:
            self._control.setEnabled(False)
            if self._browse_btn:
                self._browse_btn.setEnabled(False)
            self._enable_check.toggled.connect(self._on_enable_toggled)

    def _on_enable_toggled(self, checked: bool) -> None:
        if self._control:
            self._control.setEnabled(checked)
        if self._browse_btn:
            self._browse_btn.setEnabled(checked)
        self.value_changed.emit()

    def _make_control(self) -> QWidget:
        t       = self._param.get("type", "string")
        default = self._param.get("default")

        if t == "boolean":
            cb = QCheckBox(self)
            cb.setChecked(bool(default))
            cb.toggled.connect(self.value_changed)
            return cb

        if t == "choice":
            if self._param.get("custom_dimensions"):
                return self._make_custom_dim_control()
            combo = NoScrollComboBox(self)
            choices = self._param.get("choices", [])
            labels  = self._param.get("labels", choices)
            for ch, lb in zip(choices, labels):
                combo.addItem(str(lb), str(ch))
            if default is not None:
                idx = combo.findData(str(default))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.currentIndexChanged.connect(self.value_changed)
            return combo

        if t == "int":
            sb = NoScrollSpinBox(self)
            sb.setRange(
                self._param.get("min", 0),
                self._param.get("max", 9999),
            )
            sb.setSingleStep(self._param.get("step", 1))
            if default is not None:
                sb.setValue(int(default))
            sb.valueChanged.connect(self.value_changed)
            return sb

        if t == "float":
            sb = NoScrollDoubleSpinBox(self)
            sb.setRange(
                self._param.get("min", 0.0),
                self._param.get("max", 999.9),
            )
            sb.setSingleStep(self._param.get("step", 0.1))
            sb.setDecimals(2)
            if default is not None:
                sb.setValue(float(default))
            sb.valueChanged.connect(self.value_changed)
            return sb

        # string / file_path
        le = QLineEdit(self)
        if default:
            le.setText(str(default))
        le.textChanged.connect(self.value_changed)
        return le

    def _browse(self) -> None:
        filt = self._param.get("filter", "")
        path = open_file_dialog(self, "Select file", filt)
        if path and isinstance(self._control, QLineEdit):
            self._control.setText(path)

    def _make_custom_dim_control(self) -> QWidget:
        container = QWidget(self)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        combo = NoScrollComboBox(container)
        choices = self._param.get("choices", [])
        labels  = self._param.get("labels", choices)
        for ch, lb in zip(choices, labels):
            combo.addItem(str(lb), str(ch))
        default = self._param.get("default")
        if default is not None:
            idx = combo.findData(str(default))
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self._custom_combo = combo
        combo.currentIndexChanged.connect(self.value_changed)
        combo.currentIndexChanged.connect(self._on_custom_dim_changed)
        vbox.addWidget(combo)

        dim_row = QWidget(container)
        hbox = QHBoxLayout(dim_row)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(6)

        lbl_w = QLabel("W (mm):", dim_row)
        lbl_w.setStyleSheet("color: #c8c8c8;")
        hbox.addWidget(lbl_w)

        w_spin = NoScrollSpinBox(dim_row)
        w_spin.setRange(10, 9999)
        w_spin.setValue(210)
        w_spin.valueChanged.connect(self.value_changed)
        self._custom_w_spin = w_spin
        hbox.addWidget(w_spin)

        lbl_h = QLabel("H (mm):", dim_row)
        lbl_h.setStyleSheet("color: #c8c8c8;")
        hbox.addWidget(lbl_h)

        h_spin = NoScrollSpinBox(dim_row)
        h_spin.setRange(10, 9999)
        h_spin.setValue(297)
        h_spin.valueChanged.connect(self.value_changed)
        self._custom_h_spin = h_spin
        hbox.addWidget(h_spin)
        hbox.addStretch()

        dim_row.hide()
        self._custom_dim_row = dim_row
        vbox.addWidget(dim_row)

        return container

    def _on_custom_dim_changed(self) -> None:
        if self._custom_dim_row is None or self._custom_combo is None:
            return
        self._custom_dim_row.setVisible(self._custom_combo.currentData() == "custom")
