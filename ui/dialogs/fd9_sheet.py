"""Feed-oriented sheet and patch controls for the independent FD-9 workflow."""

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QDialogButtonBox,
)
from core.i18n import tr
from ui.widgets import NoScrollDoubleSpinBox
from workflow.fd9.chart import (
    dimensions,
    capacity,
    MIN_WIDTH,
    MAX_WIDTH,
    MIN_HEIGHT,
    MAX_HEIGHT,
)


class FD9PatchControls(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.patch_width = NoScrollDoubleSpinBox(self)
        self.patch_height = NoScrollDoubleSpinBox(self)
        self.gap = NoScrollDoubleSpinBox(self)
        for spin, label, low, high, value in (
            (self.patch_width, tr("Patch width:"), 6, 30, 8),
            (self.patch_height, tr("Patch height:"), 6, 30, 8),
            (self.gap, tr("Gap between patches:"), 0, 5, 1),
        ):
            spin.setRange(low, high)
            spin.setDecimals(1)
            spin.setSingleStep(0.5)
            spin.setSuffix(" mm")
            spin.setValue(value)
            spin.valueChanged.connect(self._changed)
            form.addRow(label, spin)

    def _changed(self, *_):
        self.changed.emit()

    def values(self):
        return self.patch_width.value(), self.patch_height.value(), self.gap.value()

    def set_values(self, width, height=None, gap=1):
        with QSignalBlocker(self.patch_width), QSignalBlocker(
            self.patch_height
        ), QSignalBlocker(self.gap):
            self.patch_width.setValue(width)
            self.patch_height.setValue(width if height is None else height)
            self.gap.setValue(gap)


class FD9SheetDialog(QDialog):
    def __init__(
        self,
        paper,
        parent=None,
        *,
        patch_mm=8.0,
        patch_height_mm=None,
        gap_mm=1.0,
        dpi=300,
        edit_sheet=True,
    ):
        super().__init__(parent)
        self.dpi = dpi
        self.setWindowTitle(
            tr("FD-9 sheet size") if edit_sheet else tr("FD-9 patch layout")
        )
        outer = QVBoxLayout(self)
        note = QLabel(
            tr(
                "FD-9: 6-30 mm patch width and height; gaps may be zero. Feed arrow first, printed face up."
            )
        )
        note.setWordWrap(True)
        outer.addWidget(note)
        try:
            w, h = dimensions(paper)
        except (ValueError, TypeError, AttributeError):
            w, h = 137, 300
        sheet = QWidget(self)
        form = QFormLayout(sheet)
        self.width = NoScrollDoubleSpinBox(sheet)
        self.height = NoScrollDoubleSpinBox(sheet)
        for spin, label, low, high, value in (
            (self.width, tr("Width across feed:"), MIN_WIDTH, MAX_WIDTH, w),
            (self.height, tr("Length along feed:"), MIN_HEIGHT, MAX_HEIGHT, h),
        ):
            spin.setRange(low, high)
            spin.setDecimals(1)
            spin.setSuffix(" mm")
            spin.setValue(value)
            spin.valueChanged.connect(self._update_capacity)
            form.addRow(label, spin)
        sheet.setVisible(edit_sheet)
        outer.addWidget(sheet)
        self.patch_controls = FD9PatchControls(self)
        self.patch_controls.set_values(patch_mm, patch_height_mm, gap_mm)
        self.patch_controls.changed.connect(self._update_capacity)
        self.patch = self.patch_controls.patch_width  # legacy square-size API
        self.patch_height = self.patch_controls.patch_height
        self.gap = self.patch_controls.gap
        outer.addWidget(self.patch_controls)
        self.summary = QLabel()
        outer.addWidget(self.summary)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self._update_capacity()

    def paper(self):
        return f"{self.width.value():g}x{self.height.value():g}"

    def _update_capacity(self):
        if hasattr(self, "summary"):
            self.summary.setText(
                tr("Capacity: {n} patches on one sheet.").format(
                    n=capacity(
                        self.paper(), *self.patch_controls.values(), dpi=self.dpi
                    )
                )
            )
