"""The Report limits window (#182): every limit set side by side, editable
where Knut ruled it editable, read-only where a standard defines the numbers.

Knut's rulings this window is built from (issue #182, 2026-09-05 to 07):

* **K1 / D15** the big table leaves the Preferences tab and becomes its own
  window, opened from the Reports frame; every limit written out in full,
  ChromIQ's own rows included.
* **D29** the window EDITS: input boxes for ChromIQ's three sets and the two
  Custom sets; the ISO columns are read-only; per-set checkboxes choose which
  columns are shown.
* **K-a** shape A: rows are grouped by the patches a limit is written over; a
  statistic ChromIQ computes and a standard also limits is one row.
* **K-b** all columns on by default; the choice is remembered per profile run
  when the window is opened from the report window.
* **D16** three cell states beyond a number: ``–`` the set defines no limit,
  ``✕`` ChromIQ cannot measure it (the row stays in the table so the user sees
  what a standard asks), ``?`` the number is in a clause ChromIQ does not hold
  or may not show.
* **D21** "Restore this column" per editable column, kept apart from the
  Preferences window's global Restore Factory Defaults.
* **D11 / D24** the note at the foot: what ChromIQ cannot evaluate, and that
  it does not certify anything.

Two doors, two behaviours (CH-19). From **Preferences** the window edits a
buffer the Preferences dialog owns; the blob is written on Preferences Save
and dropped on Cancel, like every other control on that tab. From the
**Measurement Report window** there is no Save around it, so edits are written
as they are made, and a first column "This run" holds the run's own copy of
its limits, editable only while the run is unlocked.

Every signal is connected to a bound method that reads ``self.sender()``. A
lambda or a ``functools.partial`` capturing ``self`` on a child widget's
signal is the shape that segfaulted the app (CLAUDE.md), and this window
holds up to two hundred spin boxes.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QDialog, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QPushButton, QRadioButton,
                             QScrollArea, QVBoxLayout, QWidget)

from core.i18n import tr
from core.logger import get_logger
from ui.fade_scroll import attach_edge_fades
from ui.styles import SPEC_GREEN
from ui.tab_header import dialog_masthead
from ui.theme import resolve_mode
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollDoubleSpinBox, WorkAreaClamped
from workflow.compliance_sets import (GROUP_LABELS, GROUP_ORDER, ROWS, SET_BY_ID,
                                      SETS, Limit, effective_limits,
                                      factory_limits, limit_text, rows_in_group,
                                      selectable_set_ids)

log = get_logger(__name__)

#: the "This run" pseudo column id
RUN_COLUMN = "__run__"
#: the fixed width of an editable cell; eight columns fit a 1728 px work area
#: with it, and do not with the spin box's natural 140 px (AR-CODE-MAP §4.2)
CELL_W = 104


class ThresholdsDialog(WorkAreaClamped, QDialog):
    def __init__(self, settings, parent: "QWidget | None" = None, *,
                 run=None, run_editable: bool = False,
                 buffer: "dict | None" = None) -> None:
        super().__init__(parent)
        self._settings = settings
        self._run = run
        self._run_editable = bool(run_editable and run is not None)
        #: {"overrides": {...}, "default_set": str} owned by Preferences, or
        #: None when edits go straight to the settings (report-window door)
        self._buffer = buffer
        from core.settings import compliance_overrides_of
        self._overrides = (dict(buffer.get("overrides") or {}) if buffer is not None
                           else compliance_overrides_of(settings))
        self._default_set = str((buffer or {}).get("default_set")
                                or settings.get("compliance_default_set",
                                                "chromiq_default"))
        #: the run's editable copy, edited in memory and written once on close
        self._run_limits: "dict[str, Limit]" = {}
        self._run_set_id = ""
        self._run_dirty = False
        #: True after close when the run's copy was changed (the report window
        #: recalculates the run's dated reports then, once; CH-29)
        self.run_limits_changed = False
        self._sized_once = False
        self._cells: "dict[tuple[str, str], QWidget]" = {}
        self._column_widgets: "dict[str, list[QWidget]]" = {}
        self._column_checks: "dict[str, QCheckBox]" = {}
        self._default_radios: "dict[str, QRadioButton]" = {}
        self._syncing = False

        if run is not None:
            from workflow.run_compliance import run_limits
            rl = run_limits(run, self._overrides, self._default_set)
            self._run_limits = dict(rl.limits)
            self._run_set_id = rl.set_id
            self._run_label = rl.set_label

        self.setWindowTitle(tr("Report limits"))
        self.setMinimumWidth(720)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        head, self._header, stripe = dialog_masthead(
            self, tr("MEASUREMENT REPORT"), tr("Report limits"),
            tooltip_title=tr("Report limits"),
            tooltip_body=tr(
                "A limit set is one column of this table: the numbers a "
                "Measurement Report is judged against, one per row. Rows are "
                "grouped by the patches a limit is written over; where a "
                "statistic ChromIQ computes is also limited by a standard, it "
                "is one row, so the sets can be read side by side.\n\n"
                "ChromIQ default, ChromIQ tight and Quick check are ChromIQ's "
                "own sets and can be edited here. The two ISO columns hold a "
                "standard's published values and are read-only; the two "
                "Custom columns start from them and are yours to change.\n\n"
                "A number in brackets is a recommendation, not a requirement: "
                "a value over it reads COND, never FAIL. “–” means the set puts "
                "no limit on that row. ✕ means ChromIQ cannot measure it at "
                "all; the row stays so you can see what the standard asks. "
                "? means the number is in a part of the standard ChromIQ does "
                "not hold or may not show.\n\n"
                "Turn a spin box down to 0 to remove a limit (it shows “–”). "
                "Restore this column puts a column back to its factory "
                "values. Default for new runs marks the set a new profile run "
                "is bound to at its first verification measurement."),
            accent=SPEC_GREEN)
        outer.addLayout(head)
        outer.addWidget(stripe)
        inner = QVBoxLayout()
        inner.setContentsMargins(22, 12, 22, 14)
        inner.setSpacing(10)
        outer.addLayout(inner)

        sub_text = tr(
            "Rows are grouped by the patches a limit is written over. A "
            "statistic ChromIQ computes and a standard also limits is one row.")
        if not any(sid in set(selectable_set_ids(self._overrides))
                   for sid in ("iso_12647_7", "iso_12647_8")):
            sub_text += " " + tr(
                "The ISO value sets are not yet available in this version, and "
                "the two Custom sets that start from them are empty: whether a "
                "standard's numbers may ship inside ChromIQ is still being "
                "decided. A cell reading ? is a limit the standard defines and "
                "ChromIQ does not show yet; you may type your own number into a "
                "Custom column from your own copy of the standard.")
        sub = QLabel(sub_text, self)
        sub.setWordWrap(True)
        inner.addWidget(sub)

        # -- which columns are shown (D29, K-b)
        show_row = QHBoxLayout()
        show_row.addWidget(QLabel(tr("Show:"), self))
        visible = self._visible_columns()
        if run is not None:
            cb = QCheckBox(tr("This run"), self)
            cb.setChecked(True)
            cb.setEnabled(False)
            show_row.addWidget(cb)
        for s in SETS:
            cb = QCheckBox(tr(s.label), self)
            cb.setProperty("set_id", s.id)
            cb.setChecked(s.id in visible)
            cb.toggled.connect(self._on_column_toggled)
            self._column_checks[s.id] = cb
            show_row.addWidget(cb)
        show_row.addStretch(1)
        inner.addLayout(show_row)

        # -- the table
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        body = QWidget()
        self._grid = QGridLayout(body)
        self._grid.setHorizontalSpacing(14)
        self._grid.setVerticalSpacing(3)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._build_grid()
        # F7: with setWidgetResizable the body shrinks to the viewport and the
        # last column is clipped; pinning the body's minimum width to what it
        # paints brings the horizontal scroll bar back
        body.setMinimumWidth(body.sizeHint().width())
        self._scroll.setWidget(body)
        self._fades = attach_edge_fades(self._scroll, surface="dialog")
        self._fades.set_appearance(resolve_mode(settings.get("appearance", "auto")))
        inner.addWidget(self._scroll, 1)

        # -- legend, footnotes, notes (D11, D24)
        notes = QLabel(self._notes_text(), self)
        notes.setWordWrap(True)
        notes.setTextFormat(Qt.TextFormat.PlainText)
        notes.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        inner.addWidget(notes)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_btn = QPushButton(tr("Close"), self)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        inner.addLayout(close_row)

        from ui.dialogs.tools_dialogs import neutral_controls_qss
        self.setStyleSheet(neutral_controls_qss(SPEC_GREEN, popup=SPEC_GREEN))
        for sid in SET_BY_ID:
            if sid not in visible:
                self._set_column_visible(sid, False)

    # ------------------------------------------------------------------ build
    def _column_ids(self) -> "list[str]":
        cols = [RUN_COLUMN] if self._run is not None else []
        return cols + [s.id for s in SETS]

    def _visible_columns(self) -> "set[str]":
        """K-b: per run from the report window, from Preferences otherwise."""
        import json
        ids = None
        if self._run is not None:
            try:
                ids = list(self._run.load_meta().compliance_columns or [])
            except Exception:  # noqa: BLE001
                ids = None
        else:
            raw = str(self._settings.get("compliance_columns_shown", "") or "")
            if self._buffer is not None and "columns" in self._buffer:
                raw = str(self._buffer.get("columns") or "")
            if raw:
                try:
                    ids = json.loads(raw)
                except ValueError:
                    ids = None
        if not ids:
            return set(SET_BY_ID)
        return {i for i in ids if i in SET_BY_ID} or set(SET_BY_ID)

    def _limits_of(self, col: str) -> "dict[str, Limit]":
        if col == RUN_COLUMN:
            return self._run_limits
        return effective_limits(col, self._overrides)

    def _header_text(self, col: str) -> str:
        if col == RUN_COLUMN:
            return tr("This run")
        return tr(SET_BY_ID[col].label)

    def _build_grid(self) -> None:
        g = self._grid
        faint = "color: #8a8a8a; font-size: 10px;"
        cols = self._column_ids()
        g.addWidget(QLabel(tr("Row"), self), 0, 0)
        g.addWidget(QLabel(tr("Unit"), self), 0, 1)
        g.setColumnStretch(0, 1)
        for ci, col in enumerate(cols, start=2):
            hdr = QLabel(self._header_text(col), self)
            hdr.setStyleSheet("font-weight: bold;")
            hdr.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
            hdr.setWordWrap(True)
            hdr.setMinimumWidth(CELL_W + 20)
            g.addWidget(hdr, 0, ci)
            self._column_widgets.setdefault(col, []).append(hdr)
            # row 1: the read-only mark / Restore this column / locked note
            editable = self._column_editable(col)
            if col == RUN_COLUMN and not self._run_editable:
                note = QLabel(tr("locked: tick “Unlock this run's limits” in "
                                 "the report window to change these"), self)
                note.setStyleSheet(faint)
                note.setWordWrap(True)
                note.setMinimumWidth(CELL_W + 20)
                note.setMaximumWidth(CELL_W + 80)
                g.addWidget(note, 1, ci)
                self._column_widgets[col].append(note)
            elif editable:
                btn = QPushButton(tr("Restore this column"), self)
                btn.setProperty("set_id", col)
                btn.setStyleSheet("QPushButton { padding: 1px 6px; font-size: 10px;"
                                  " min-height: 22px; max-height: 22px; }")
                btn.setMinimumWidth(btn.sizeHint().width())      # F6: German is longer
                btn.clicked.connect(self._on_restore_column)
                g.addWidget(btn, 1, ci)
                self._column_widgets[col].append(btn)
            else:
                ro = QLabel(tr("read-only"), self)
                ro.setStyleSheet(faint)
                ro.setAlignment(Qt.AlignmentFlag.AlignRight)
                g.addWidget(ro, 1, ci)
                self._column_widgets[col].append(ro)
        # row 2: default for new runs (CH-1 / S-13)
        g.addWidget(QLabel(tr("Default for new runs"), self), 2, 0)
        selectable = set(selectable_set_ids(self._overrides))
        for ci, col in enumerate(cols, start=2):
            if col == RUN_COLUMN or col not in selectable:
                continue
            rb = QRadioButton(self)
            rb.setProperty("set_id", col)
            rb.setChecked(col == self._default_set)
            rb.toggled.connect(self._on_default_toggled)
            rb.setToolTip(tr("A new profile run is bound to this set at its "
                             "first verification measurement."))
            self._default_radios[col] = rb
            g.addWidget(rb, 2, ci, Qt.AlignmentFlag.AlignRight)
            self._column_widgets[col].append(rb)
        r = 3
        for group in GROUP_ORDER:
            title = QLabel(tr(GROUP_LABELS[group]), self)
            title.setStyleSheet("font-weight: bold; margin-top: 8px; "
                                "text-transform: uppercase; font-size: 10px;"
                                " letter-spacing: 1px;")
            g.addWidget(title, r, 0, 1, 2 + len(cols))
            r += 1
            for row in rows_in_group(group):
                lab = QLabel(tr(row.label), self)
                lab.setStyleSheet("padding-left: 12px;")
                if row.status == "unmeasurable" and row.note:
                    lab.setToolTip(tr(row.note))
                g.addWidget(lab, r, 0)
                unit = QLabel(row.unit, self)
                unit.setStyleSheet(faint)
                g.addWidget(unit, r, 1)
                for ci, col in enumerate(cols, start=2):
                    w = self._make_cell(col, row.id)
                    g.addWidget(w, r, ci, Qt.AlignmentFlag.AlignRight)
                    self._cells[(col, row.id)] = w
                    self._column_widgets[col].append(w)
                r += 1

    def _column_editable(self, col: str) -> bool:
        if col == RUN_COLUMN:
            return self._run_editable
        return SET_BY_ID[col].editable

    @staticmethod
    def _cell_text(lim: Limit) -> str:
        """A read-only cell in the SAME number format as the spin boxes beside
        it: the spin boxes follow the system locale (a German machine shows
        2,00), so a plain "2.0" next to them read as a different number. Seen on
        screen, 2026-09-08."""
        if lim.is_numeric:
            from PyQt6.QtCore import QLocale
            txt = QLocale.system().toString(float(lim.number), "f", 2)
            return f"({txt})" if lim.is_should else txt
        return limit_text(lim)

    def _make_cell(self, col: str, row_id: str) -> QWidget:
        from workflow.compliance_sets import ROW_BY_ID
        row = ROW_BY_ID[row_id]
        lim = self._limits_of(col).get(row_id, Limit.none())
        # A Custom column inherits its ISO parent's cells; while S-2 is open
        # those read ? and the user may still type their own number (the
        # fallback the licensing question was asked with). So an editable
        # column's cell is a spin box unless the ROW is out of ChromIQ's reach.
        editable = (self._column_editable(col)
                    and row.status in ("now", "build", "ref")
                    and lim.kind in ("value", "should", "none", "unknown"))
        if not editable:
            lab = QLabel(self._cell_text(lim), self)
            lab.setAlignment(Qt.AlignmentFlag.AlignRight)
            lab.setFixedWidth(CELL_W)
            if lim.kind == "unmeasurable" and row.note:
                lab.setToolTip(tr(row.note))
            elif lim.kind == "unknown":
                lab.setToolTip(tr("The number is in a part of the standard "
                                  "ChromIQ does not hold or may not show yet."))
            return lab
        sb = NoScrollDoubleSpinBox(self)
        sb.setDecimals(2)
        sb.setRange(0.0, 100.0)
        sb.setSingleStep(0.1)
        sb.setFixedWidth(CELL_W)
        sb.setSpecialValueText("–")            # 0 = no limit (CH-21)
        if lim.is_should:
            sb.setPrefix("(")
            sb.setSuffix(")")
        sb.setValue(float(lim.number) if lim.is_numeric else 0.0)
        sb.setProperty("set_id", col)
        sb.setProperty("row_id", row_id)
        sb.valueChanged.connect(self._on_cell_changed)
        return sb

    def _notes_text(self) -> str:
        from workflow.measurement_messages import M_THRESHOLDS_NOT_CERTIFICATION
        legend = tr("Legend: a number is a required limit; (a number) a "
                    "recommendation, over it reads COND; “–” the set puts no limit "
                    "on the row; ✕ ChromIQ cannot measure it; ? the number is in "
                    "a part of the standard ChromIQ does not hold or may not show.")
        foot = tr("¹ The standards write these limits over their own chart and "
                  "control strip; ChromIQ applies them to the patches of the "
                  "chart that was measured, and the report says so. ² The "
                  "standards' aim is characterization data of a printing "
                  "condition; without a reference file the aim is the chart's "
                  "own design. ³ The standards set a maximum only over their "
                  "control strip, not over all patches.")
        cannot = [tr(r.label) for r in ROWS if r.status == "unmeasurable"]
        title, body = M_THRESHOLDS_NOT_CERTIFICATION.render(rows=", ".join(cannot))
        return legend + "\n" + foot + "\n\n" + title + "\n" + body

    # ------------------------------------------------------------------ slots
    def _on_cell_changed(self, value: float) -> None:
        if self._syncing:
            return
        sb = self.sender()
        if sb is None:
            return
        col = sb.property("set_id")
        row_id = sb.property("row_id")
        if not col or not row_id:
            return
        if col == RUN_COLUMN:
            # F4: a recommendation stays a recommendation when a cell passes
            # through 0. The kind comes from the run's SET (as effective_limits
            # decides it), not from the cell's last state; a historical set
            # falls back to the cell.
            if self._run_set_id in SET_BY_ID:
                base = effective_limits(self._run_set_id, self._overrides).get(row_id, Limit.none())
            else:
                base = self._run_limits.get(row_id, Limit.none())
            if value <= 0.0:
                new = Limit.none()
            else:
                new = Limit.should(value) if base.is_should else Limit.value(value)
            self._run_limits[row_id] = new
            self._run_dirty = True
            return
        mine = self._overrides.setdefault(col, {})
        fac = factory_limits(col).get(row_id, Limit.none())
        if value <= 0.0:
            if fac.kind == "none":
                mine.pop(row_id, None)          # back to the factory "–"
            else:
                mine[row_id] = None
        elif fac.is_numeric and abs(float(fac.number) - value) < 1e-9:
            mine.pop(row_id, None)              # back to the factory number
        else:
            mine[row_id] = float(value)
        if not mine:
            self._overrides.pop(col, None)
        self._write_overrides()

    def _on_restore_column(self) -> None:
        btn = self.sender()
        col = btn.property("set_id") if btn is not None else None
        if not col:
            return
        if col == RUN_COLUMN:
            if self._run_set_id in SET_BY_ID:
                self._run_limits = dict(effective_limits(self._run_set_id,
                                                         self._overrides))
                self._run_dirty = True
        else:
            self._overrides.pop(col, None)
            self._write_overrides()
        self._refill_column(col)

    def _on_column_toggled(self, on: bool) -> None:
        cb = self.sender()
        col = cb.property("set_id") if cb is not None else None
        if not col:
            return
        self._set_column_visible(col, bool(on))
        shown = [sid for sid, c in self._column_checks.items() if c.isChecked()]
        import json
        if self._run is not None:
            from workflow.run_compliance import set_run_columns
            try:
                set_run_columns(self._run, shown if len(shown) < len(SET_BY_ID) else [])
            except OSError as exc:
                log.warning("could not store the column choice: %s", exc)
        elif self._buffer is not None:
            # F12: from Preferences the choice waits for Save like every other
            # setting on that tab
            self._buffer["columns"] = json.dumps(shown) if len(shown) < len(SET_BY_ID) else ""
        else:
            self._settings.set("compliance_columns_shown",
                               json.dumps(shown) if len(shown) < len(SET_BY_ID) else "")

    def _on_default_toggled(self, on: bool) -> None:
        if not on:
            return
        rb = self.sender()
        col = rb.property("set_id") if rb is not None else None
        if not col:
            return
        self._default_set = col
        if self._buffer is not None:
            self._buffer["default_set"] = col
        else:
            self._settings.set("compliance_default_set", col)

    # --------------------------------------------------------------- helpers
    def _write_overrides(self) -> None:
        if self._buffer is not None:
            self._buffer["overrides"] = {k: dict(v) for k, v in self._overrides.items()}
        else:
            from core.settings import store_compliance_overrides
            store_compliance_overrides(self._settings, self._overrides)
        # a Custom column inherits nothing from its parent's overrides, but the
        # selectable set of columns can change when a column is emptied
        for col, rb in self._default_radios.items():
            rb.setEnabled(col in set(selectable_set_ids(self._overrides)))

    def _refill_column(self, col: str) -> None:
        self._syncing = True
        try:
            limits = self._limits_of(col)
            for (c, rid), w in self._cells.items():
                if c != col:
                    continue
                lim = limits.get(rid, Limit.none())
                if isinstance(w, NoScrollDoubleSpinBox):
                    w.setValue(float(lim.number) if lim.is_numeric else 0.0)
                elif isinstance(w, QLabel):
                    w.setText(self._cell_text(lim))
        finally:
            self._syncing = False

    def _set_column_visible(self, col: str, on: bool) -> None:
        for w in self._column_widgets.get(col, []):
            w.setVisible(on)

    def value_of(self, col: str, row_id: str) -> "Limit":
        """What the window currently shows for one cell (for tests/drivers)."""
        return self._limits_of(col).get(row_id, Limit.none())

    # ------------------------------------------------------------ lifecycle
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._sized_once:
            return
        self._sized_once = True
        from PyQt6.QtGui import QGuiApplication
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        body = self._scroll.widget()
        # body + the dialog's side insets + the vertical scroll bar + a margin
        natural_w = (body.sizeHint().width() + 44 + 16 + 24) if body else 1200
        w = max(self.minimumWidth(), min(natural_w, area.width() - 40))
        h = min(self.sizeHint().height() + 400, self._work_area_cap(area.height() - 40))
        self.resize(w, h)
        self._keep_inside_the_work_area()

    def done(self, result: int) -> None:  # noqa: D102
        if self._run is not None and self._run_dirty and self._run_editable:
            from workflow.run_compliance import set_run_limits
            try:
                set_run_limits(self._run, self._run_limits)
                self.run_limits_changed = True
            except OSError as exc:
                log.warning("could not store this run's limits: %s", exc)
        super().done(result)
