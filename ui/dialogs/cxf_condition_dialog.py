"""The window that asks which measurement condition of an i1Profiler CxF
measurement to import (M-IMPORT-CXF-CONDITION, 4.3.23).

An i1Profiler ``.mxf`` / ``.cxf`` can hold every patch's spectrum under up to
three measurement conditions: M0 (the instrument's own lamp), M1 (D50 daylight
with ultraviolet) and M2 (ultraviolet cut). Until 4.3.23 the import took M2
without asking or saying so; jctay (printerknowledge, 2026-11-03) compared the
import with his M1 readings and found 4.4 dE76 between them on his brightened
paper. Basti, 2026-11-03: *"ChromIQ offers a choice of condition."*

ONE WINDOW FOR EVERY DOOR. :func:`choose_cxf_condition` is what the Measure
tab's IMPORT, Build Profile's import, Tools > Convert i1Profiler > TI3, the
calibration measurement, the Measurement Report and the scanner-target dialog
call before they convert a CxF file. A file with one condition is not asked
about: the condition is taken and the log says which.

NOTHING IS REMEMBERED. No other choice made while importing a file is kept
from one import to the next, and a remembered condition would be applied to
the next file in silence, which is exactly what this window exists to stop.
The preselection is the file's own (when it says so with certainty), else M1.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QButtonGroup, QDialog, QHBoxLayout, QLabel,
                             QPushButton, QRadioButton, QVBoxLayout, QWidget)

from core.i18n import tr
from workflow import measurement_messages as M

#: The accent the window's primary button takes when the caller names none.
_DEFAULT_ACCENT = "#5aa9e6"


class CxfConditionDialog(QDialog):
    """Asks for one of the conditions a CxF file holds; :meth:`condition`
    is the one picked (the preselection until the person picks another)."""

    def __init__(self, parent: "QWidget | None", name: str, conditions,
                 accent: str = _DEFAULT_ACCENT) -> None:
        super().__init__(parent)
        self.setObjectName("cxf_condition_dialog")
        self._conditions = conditions
        # Every word from workflow.measurement_messages
        # (M-IMPORT-CXF-CONDITION and its parts), none of the window's own.
        title, body = M.M_IMPORT_CXF_CONDITION.render(
            name=name,
            conditions=M.cxf_condition_list(conditions.available))
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(640)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        head = QLabel(title)
        head.setObjectName("cxf_condition_headline")
        f = head.font()
        f.setBold(True)
        f.setPointSizeF(f.pointSizeF() * 1.15)
        head.setFont(f)
        lay.addWidget(head)

        text = QLabel(body)
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.PlainText)
        lay.addWidget(text)

        self._group = QButtonGroup(self)
        self._radios: "dict[str, QRadioButton]" = {}
        pre = conditions.preselect
        # ABOVE THE CHOICES (4.3.24): the line says which condition "is
        # selected below" and why (the one chosen in i1Profiler, when the
        # file says so), so it stands before the choices it talks about.
        setting = QLabel(M.cxf_condition_setting_line(
            conditions.selected_raw, conditions.selected, pre))
        setting.setObjectName("cxf_condition_setting")
        setting.setWordWrap(True)
        setting.setTextFormat(Qt.TextFormat.PlainText)
        lay.addWidget(setting)
        for cond in conditions.available:
            if cond not in M.CXF_CONDITION_OPTIONS:
                continue
            rb = QRadioButton(M.cxf_condition_label(cond))
            rb.setObjectName(f"cxf_condition_{cond}")
            rf = rb.font()
            rf.setBold(True)
            rb.setFont(rf)
            rb.setChecked(cond == pre)
            self._group.addButton(rb)
            self._radios[cond] = rb
            lay.addWidget(rb)
            desc = QLabel(M.cxf_condition_text(cond))
            desc.setWordWrap(True)
            desc.setTextFormat(Qt.TextFormat.PlainText)
            desc.setContentsMargins(26, 0, 0, 4)
            desc.setBuddy(rb)
            lay.addWidget(desc)

        for note in (M.cxf_condition_fwa_note(), M.cxf_condition_kept_note()):
            lbl = QLabel(note)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.TextFormat.PlainText)
            lay.addWidget(lbl)

        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton(tr("Cancel"))
        cancel.setObjectName("cxf_condition_cancel")
        cancel.clicked.connect(self.reject)
        go = QPushButton(M.cxf_condition_import_button())
        go.setObjectName("primary")
        go.setDefault(True)
        go.clicked.connect(self.accept)
        self._go = go
        row.addWidget(cancel)
        row.addWidget(go)
        lay.addLayout(row)
        try:
            from ui.widgets import tint_dialog_primary
            tint_dialog_primary(self, accent)
        except Exception:       # noqa: BLE001 - a colour is never worth a crash
            pass

    def condition(self) -> str:
        for cond, rb in self._radios.items():
            if rb.isChecked():
                return cond
        return self._conditions.preselect

    def select(self, condition: str) -> None:
        """Pick *condition* (drivers and tests)."""
        rb = self._radios.get(condition)
        if rb is not None:
            rb.setChecked(True)


def _run(dlg: CxfConditionDialog) -> bool:
    """Shows the window and waits; True when Import was pressed. A seam for
    the tests, which must never sit in a modal ``exec()``."""
    return dlg.exec() == QDialog.DialogCode.Accepted


def choose_cxf_condition(parent: "QWidget | None", path: "str | Path",
                         *, log: "Callable[[str], None] | None" = None,
                         accent: str = _DEFAULT_ACCENT) -> "str | None":
    """The condition to import *path* under, asking when there is a choice.

    Returns the condition ("M0", "M1", "M2"); ``None`` when the person
    cancelled (nothing must be imported then); ``""`` when there is nothing
    to choose from: not a CxF file, a file that cannot be read, or one with
    no M0/M1/M2 readings, whose conversion then says what is wrong. *log*
    receives the line every door writes (M-IMPORT-CXF-CONDITION-PARTS)."""
    from workflow.reference_convert import (ReferenceConvertError,
                                            cxf_conditions, is_cxf)
    p = Path(path)
    if not is_cxf(p):
        return ""
    try:
        conds = cxf_conditions(p)
    except (ReferenceConvertError, OSError):
        return ""
    if not conds.available:
        return ""
    if not conds.needs_choice:
        chosen = conds.available[0]
    else:
        dlg = CxfConditionDialog(parent, p.name, conds, accent)
        try:
            accepted = _run(dlg)
            chosen = dlg.condition()
        finally:
            dlg.deleteLater()
        if not accepted:
            if log is not None:
                log(M.cxf_condition_cancelled_line())
            return None
    if log is not None:
        log(M.cxf_condition_log_line(chosen, conds.available))
    return chosen
