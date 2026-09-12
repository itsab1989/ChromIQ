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
                             QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from core.i18n import tr
from core.logger import get_logger
from ui.fade_scroll import attach_edge_fades
from ui.styles import ACCENT_WARN, SPEC_GREEN
from ui.tab_header import dialog_masthead
from ui.theme import resolve_mode
from ui.widgets import NoScrollDoubleSpinBox, WorkAreaClamped
from workflow.compliance_sets import (GROUP_LABELS, GROUP_ORDER, ROWS, SET_BY_ID,
                                      SETS, Limit, effective_limits,
                                      factory_limits, limit_text, rows_in_group,
                                      selectable_set_ids)

log = get_logger(__name__)

#: the "This run" pseudo column id
RUN_COLUMN = "__run__"

#: Gap between the items of the "Show:" row. Named, because the number is the
#: whole of the fix: the row holds up to eight ticks with long names, and the
#: style's own spacing left none between one name and the next tick.
SHOW_ROW_SPACING_PX = 24


def _stored_column(run) -> "dict | None":
    """Everything about the run that a Report limits window can write, straight
    off its `meta.json`, so that another window's write can be seen.

    BOTH KEYS, BECAUSE THE UNDO PUTS BOTH BACK. This watched
    `compliance_thresholds` alone while `_undo_the_edit` restores
    `compliance_columns` as well, so another window's choice of which columns
    the report shows was reverted with no collision reported and nothing said.

    None only when the run itself is missing. `Run.load_meta` answers a
    truncated or absent file with a fresh `RunMeta` rather than raising, on
    purpose (Knut's D2), so a corrupt meta reads here as an unbound run and
    this function cannot tell them apart. Saying so rather than implying a
    distinction the code does not make.
    """
    if run is None:
        return None
    m = run.load_meta()
    return {"thresholds": dict(m.compliance_thresholds or {}),
            "columns": list(getattr(m, "compliance_columns", []) or [])}

#: the fixed width of an editable cell; eight columns fit a 1728 px work area
#: with it, and do not with the spin box's natural 140 px (AR-CODE-MAP §4.2)
CELL_W = 104
#: the gap between two columns. It is NOT the grid's own horizontal spacing:
#: both grids run at spacing 0 and carry the gap inside each column's pinned
#: width, because Qt charges spacing to a column that holds a widget spanning
#: it (the group titles) and not to one that is merely hidden. With the
#: spacing left on, a hidden column cost the body 14 px that the head did not
#: pay, and every heading after it sat 14 px off its column, measured on
#: screen 2026-09-10.
COLUMN_GAP = 14


class _ScrolledBody(QWidget):
    """The scrolled half of the table.

    It exists only to say when its width changed, so the frozen head can be
    given the same width and lay its columns out over the same span. A bound
    method on a plain widget, not a lambda on a scroll bar's signal, which is
    the shape that segfaulted the app (CLAUDE.md).
    """

    def __init__(self, owner: "ThresholdsDialog") -> None:
        super().__init__()
        self._owner = owner

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._owner._match_head_to_body()


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
        #: WHAT THE WINDOW OPENED WITH, so that typing a number and typing it
        #: straight back is not an edit. `_run_dirty` was set on every
        #: `valueChanged`, so a net-zero visit wrote the column, asked the
        #: report window to recalculate a whole history, and on an unbound run
        #: bound it permanently, from an act that changed nothing. Filled in by
        #: `_fill_run_column`, which is where the opening values are known.
        self._run_limits_at_open: "dict | None" = None
        #: True after close when the run's copy was changed (the report window
        #: recalculates the run's dated reports then, once; CH-29)
        self.run_limits_changed = False
        #: THE RUN'S OWN COLUMN AS IT SAT ON DISK WHEN THIS WINDOW OPENED, and
        #: the only way this window can tell that somebody else moved it.
        #: NOT `_run_limits_at_open`, which is derived: on an unbound run it is
        #: the live default set's numbers, and this window edits the overrides
        #: those are derived from, so it moves for reasons that are this
        #: window's own doing.
        self._run_stored_at_open: "dict | None" = None
        #: True after close when the run's stored column had been changed by
        #: SOMEBODY ELSE while this window was open. The report window's
        #: "the binding has not moved" test cannot see that: it compares
        #: `compliance_bound_at`, which only `bind_run` stamps, and the other
        #: writer here is `set_run_limits`, which is this same `done()` in
        #: another window. A challenge round drove it: a second Report limits
        #: window on the same run had its number erased with no message at all,
        #: indistinguishable from the case where nobody else wrote.
        self.run_limits_collided = False
        #: THE SAME QUESTION FOR THE TWO APP-WIDE STORES this window writes:
        #: the default set and the overrides. A challenge round found that the
        #: report window puts BOTH back to its own snapshot when the user
        #: refuses, unconditionally, so another writer's change to the default
        #: set was destroyed with nothing said. That store is what every
        #: UNBOUND run is judged by, so it is not a small one.
        #: ONE BASELINE PER STORE, because a refresh is only ever earned by
        #: one of them. Held as a single tuple, this window's click on the
        #: "Default for new runs" radio swallowed another writer's change to
        #: the overrides, and the other way round: the watch never fired and
        #: the change was destroyed in silence. A challenge round drove both.
        self._default_set_last_seen: "str | None" = None
        self._overrides_last_seen: "str | None" = None
        #: True after close when those stores were changed by somebody else
        #: while this window was open.
        self.prefs_collided = False
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
            from workflow.compliance_sets import limits_to_json as _l2j
            self._run_limits_at_open = _l2j(self._run_limits)
            self._run_stored_at_open = _stored_column(run)
            self._run_label = rl.set_label

        self._default_set_last_seen, self._overrides_last_seen = self._prefs_now()

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
            # …AND IT NO LONGER SAYS THE CUSTOM SETS ARE EMPTY, because as of
            # 2026-09-12 they are not. Knut asked for a value on every metric
            # ChromIQ can measure, `_CUSTOM_PLACEHOLDER` supplies eleven, and
            # both Custom sets became selectable the same day. This sentence's
            # own guard is "neither ISO set is selectable", so it was shown
            # ONLY in the state where its second clause had become false, with
            # the two enabled radio buttons three rows above it.
            sub_text += " " + tr(
                "The ISO value sets are not yet available in this version: "
                "whether a standard's numbers may ship inside ChromIQ is still "
                "being decided. A cell reading ? is a limit the standard "
                "defines and ChromIQ does not show yet; you may type your own "
                "number into a Custom column from your own copy of the "
                "standard.")
        sub = QLabel(sub_text, self)
        sub.setWordWrap(True)
        inner.addWidget(sub)

        # -- the user's OWN limits file, when it could not be understood (F7)
        trouble = self._iso_file_trouble()
        if trouble:
            warn = QLabel(trouble, self)
            warn.setWordWrap(True)
            warn.setTextFormat(Qt.TextFormat.PlainText)
            # THE PANEL FOLLOWS THE THEME, and it did not: #3a2a00 is a
            # dark-mode ground, and on the light window this whole dialog is,
            # it painted a dark brown box in the middle of a pale page.
            # Photographed on screen. The same three-way the report window's
            # own strip uses, and for the same reason: every other colour here
            # is chosen per appearance, so one that is not stands out as a
            # mistake rather than as a warning.
            _mode = resolve_mode(self._settings.get("appearance", "auto"))
            if _mode == "dark":
                _skin = ("border: 1px solid #b08040; color: #f0b35a;"
                         " background: rgba(240,180,80,0.14);")
            elif _mode == "neutral":
                from ui import neutral_styles
                _skin = (f"border: 1px solid {neutral_styles.NM_BORDER_HI};"
                         f" color: {neutral_styles.NM_TEXT_MAIN};"
                         f" background: {neutral_styles.NM_BG_SURFACE};")
            else:
                _skin = ("border: 1px solid #c8922a; color: #8a5a00;"
                         " background: rgba(240,180,80,0.12);")
            warn.setObjectName("isoFileTrouble")
            warn.setStyleSheet(
                "QLabel#isoFileTrouble { border-radius: 4px;"
                " padding: 6px 10px; " + _skin + " }")
            inner.addWidget(warn)

        # -- which columns are shown (D29, K-b)
        #
        # THE LABELS NEED AIR BETWEEN THEM. Seven column names sit in this one
        # row, and with the layout's own spacing each name ended one pixel
        # before the next box began: "ChromIQ default (recommended)" ran
        # straight into the tick for "ChromIQ tight", so the row read as one
        # long sentence with squares in it. Reported twice (round 2 N5, round 3
        # N7). A checkbox's text has no right-hand padding of its own, so the
        # gap has to be the layout's, and it has to be set rather than
        # inherited: the style's default put 8 px between the "Show:" label and
        # the first box and nothing at all between the boxes.
        show_row = QHBoxLayout()
        show_row.setSpacing(SHOW_ROW_SPACING_PX)
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

        # -- the table: a head that stays put over a body that scrolls under
        # it (Knut, beta 3). Two grids, ONE column geometry (_sync_columns),
        # and the head is moved by the body's own horizontal scroll bar, so a
        # heading cannot come to sit over the wrong column.
        self._head_clip = QWidget(self)
        self._head_clip.setSizePolicy(QSizePolicy.Policy.Ignored,
                                      QSizePolicy.Policy.Fixed)
        self._head = QWidget(self._head_clip)
        self._head_grid = QGridLayout(self._head)
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        body = _ScrolledBody(self)
        self._grid = QGridLayout(body)
        for g in (self._head_grid, self._grid):
            g.setHorizontalSpacing(0)          # the gap lives in COLUMN_GAP
            g.setVerticalSpacing(3)
            g.setContentsMargins(0, 0, 0, 0)
        self._build_head()
        self._build_rows()
        # F7: with setWidgetResizable the body shrinks to the viewport and the
        # last column is clipped; pinning the body's minimum width to what it
        # paints brings the horizontal scroll bar back
        self._scroll.setWidget(body)
        self._scroll.horizontalScrollBar().valueChanged.connect(self._on_hscroll)
        self._sync_columns()
        self._fades = attach_edge_fades(self._scroll, surface="dialog")
        self._fades.set_appearance(resolve_mode(settings.get("appearance", "auto")))
        inner.addWidget(self._head_clip)
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
    def _iso_file_trouble(self) -> str:
        """What to tell a licence holder whose own limits file was not read.

        The route in `data/compliance_sets/README.md` ("point ChromIQ at your
        own file") had no way of failing out loud: `Limit.from_json` turns
        anything it cannot read into `?`, which is exactly what the empty
        bundled file produces, so a file in the wrong shape looked identical to
        no permission at all. Every sentence here is about the file the USER
        named; the bundled one says nothing, because being empty is what it is
        for.
        """
        from workflow.compliance_sets import (iso_data_path_text,
                                              iso_data_problems)
        problems = iso_data_problems()
        if not problems:
            return ""
        lines = [tr("ChromIQ could not use the limits file you pointed it at, "
                    "so the ISO limits still read ?.")]
        for kind, detail in problems:
            if kind == "unreadable":
                lines.append(tr("The file could not be read: {reason}")
                             .format(reason=detail))
            elif kind in ("not_an_object", "set_not_an_object"):
                lines.append(tr(
                    "The file must hold a JSON object with one key per limit "
                    "set, and each set holding that set's rows."))
            elif kind == "no_known_set":
                lines.append(tr(
                    "The file names no limit set ChromIQ knows. It needs a "
                    "top-level key {names}, holding that set's rows.")
                    .format(names=detail))
            elif kind == "unreadable_cells":
                lines.append(tr(
                    "These limits could not be read and still show ?: {rows}. "
                    "A limit is a plain number, or [number, \"should\"] for a "
                    "recommendation.").format(rows=detail))
            elif kind == "unknown_rows":
                lines.append(tr(
                    "These names are not rows ChromIQ has, and were ignored: "
                    "{rows}").format(rows=detail))
            else:
                lines.append(f"{kind}: {detail}")
        path = iso_data_path_text()
        if path:
            lines.append(tr("CHROMIQ_COMPLIANCE_ISO_FILE points at {path}")
                         .format(path=path))
        return "\n".join(lines)

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

    def _build_head(self) -> None:
        """The three rows that stay put: the column names, the Restore /
        read-only / locked line, and Default for new runs (Knut, beta 3)."""
        g = self._head_grid
        faint = "color: #8a8a8a; font-size: 10px;"
        cols = self._column_ids()
        g.addWidget(QLabel(tr("Row"), self), 0, 0)
        g.addWidget(QLabel(tr("Unit"), self), 0, 1)
        # The spare width goes to a trailing column, NOT to the row labels
        # (Knut, beta 3). With the stretch on column 0 every column a user
        # unticked was paid for in blank space in front of the Unit column,
        # and the columns still shown walked to the right edge.
        g.setColumnStretch(0, 0)
        g.setColumnStretch(2 + len(cols), 1)
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

    def _build_rows(self) -> None:
        """The scrolled half: the groups and their limit rows."""
        g = self._grid
        faint = "color: #8a8a8a; font-size: 10px;"
        cols = self._column_ids()
        g.setColumnStretch(0, 0)
        g.setColumnStretch(2 + len(cols), 1)
        r = 0
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
        # A WINDOW THAT WRITES NOTHING OFFERS NOTHING TO WRITE WITH.
        # The app-wide writes were guarded and the CONTROLS were left as they
        # were, so a "Show limits…" window still took a typed number into its
        # spin box and showed it for ever while the settings held something
        # else, and its "Restore this column" button wiped the column on screen
        # while the stored override went on governing every unbound run in
        # every project. A challenge round photographed both. Guarding a write
        # without guarding the control that invites it trades a window that
        # does the wrong thing for one that says the wrong thing.
        if self._read_only_here():
            return False
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
        # WHOSE NUMBERS THE TWO CUSTOM COLUMNS HOLD, said at the table where
        # they are read. They are named after a standard and start from
        # ChromIQ's own figures, so a reader who is not told will take them for
        # the standard's. Required by the owner's standing rule on #182: no
        # value from ISO 12647-7 or ISO 12647-8 is in ChromIQ, and a column
        # bearing those names must not be allowed to imply otherwise.
        custom = tr(
            "The two Custom columns start from ChromIQ's own numbers, chosen "
            "so that every row ChromIQ can measure has a limit to be judged "
            "against. They are not the published tolerances of ISO 12647-7 or "
            "ISO 12647-8, which ChromIQ does not hold. If you hold either "
            "standard, point ChromIQ at your own copy of its values and the "
            "Custom column starts from those instead. Every limit here is "
            "yours to change.")
        cannot = [tr(r.label) for r in ROWS if r.status == "unmeasurable"]
        title, body = M_THRESHOLDS_NOT_CERTIFICATION.render(rows=", ".join(cannot))
        return legend + "\n" + foot + "\n\n" + custom + "\n\n" + title + "\n" + body

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
        self._write_overrides()   # a no-op when this window is only showing

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
        # A LOCKED RUN IS NOT WRITTEN, AND THIS SLOT WAS THE ONE THAT DID.
        # `done()` checks `_run_editable` before it stores the numbers; this
        # writes `set_run_columns` the moment the box is clicked and checked
        # nothing, so a window opened as "Show limits…" on a locked run still
        # changed what that run stores. The column choice is per run and is
        # part of what the undo puts back, so it is not a view setting that can
        # be exempt.
        if self._run is not None and not self._run_editable:
            self._set_column_visible(col, bool(on))
            return
        self._set_column_visible(col, bool(on))
        shown = [sid for sid, c in self._column_checks.items() if c.isChecked()]
        import json
        if self._run is not None:
            from workflow.run_compliance import set_run_columns
            try:
                _wrote = shown if len(shown) < len(SET_BY_ID) else []
                set_run_columns(self._run, _wrote)
                # AND THIS WINDOW HAS NOW SEEN ITS OWN WRITE, THE COLUMNS
                # AND NOTHING ELSE. Without any refresh the collision check
                # reports this click as somebody else's work; with a refresh of
                # the WHOLE baseline it does the opposite, and swallows a
                # thresholds change another window made while this one sat
                # open. Two challenge rounds drove one each, and the second is
                # the quieter fault: it fails silent.
                #
                # A baseline is refreshed exactly as wide as the write that
                # earned it.
                if self._run_stored_at_open is not None:
                    # WHAT WE WROTE, NOT WHAT IS THERE NOW. Reading it back
                    # records whatever landed between this window's write and
                    # this line as seen, so another window's column choice was
                    # overwritten AND marked as ours. The right width and the
                    # wrong moment is still the wrong baseline.
                    self._run_stored_at_open["columns"] = list(_wrote)
            except OSError as exc:
                log.warning("could not store the column choice: %s", exc)
        elif self._buffer is not None:
            # F12: from Preferences the choice waits for Save like every other
            # setting on that tab
            self._buffer["columns"] = json.dumps(shown) if len(shown) < len(SET_BY_ID) else ""
        else:
            self._settings.set("compliance_columns_shown",
                               json.dumps(shown) if len(shown) < len(SET_BY_ID) else "")

    def _prefs_now(self) -> "tuple[str | None, str | None]":
        """The two app-wide stores this window can write, SEPARATELY.

        Read from the settings, not from `self._overrides`, which is this
        window's working copy and therefore always agrees with itself. From
        Preferences the edits go to a buffer and nothing app-wide is touched,
        so there is nothing to collide with and both are None.
        """
        if self._buffer is not None:
            return (None, None)
        from core.settings import compliance_overrides_of
        import json as _json
        try:
            return (str(self._settings.get("compliance_default_set", "") or ""),
                    _json.dumps(compliance_overrides_of(self._settings),
                                sort_keys=True))
        except Exception:              # noqa: BLE001
            return (None, None)

    def _read_only_here(self) -> bool:
        """Whether this window is showing a run rather than editing one.

        `run_editable` was read as "read-only for the RUN", and everything
        app-wide was left writable on the reasoning that a bound run's limits
        come from its own stored copy, so nothing app-wide can reach it. True
        of that run, and it does not reach the harm: a challenge round moved
        "Default for new runs" from a "Show limits…" window with no question
        and no undo, and a DIFFERENT project's next run was then bound to it
        and judged by 4.0 instead of 2.0. A window that says it is showing
        writes nothing.

        From Preferences there is no run, so this is False and that door is
        untouched.
        """
        return self._run is not None and not self._run_editable

    def _restore_default_radio(self) -> None:
        """Put the radio back on the set that is really the default.

        AND WHEN THERE IS NO SUCH RADIO, PUT THEM ALL BACK. The stored default
        can name a set this window does not offer: emptying a column's last
        limit-bearing row takes it out of `selectable_set_ids` (CH-11, an empty
        column is never a choice) while the stored id still names it. With no
        radio to restore, this returned and left the one the user had just
        clicked checked, in a window that writes nothing, so the click stuck
        and the window showed a default it had not set.
        """
        rb = self._default_radios.get(self._default_set)
        if rb is None:
            _was = self._syncing
            self._syncing = True
            try:
                for _r in self._default_radios.values():
                    _r.setAutoExclusive(False)
                    _r.setChecked(False)
                    _r.setAutoExclusive(True)
            finally:
                self._syncing = _was
            return
        _was = self._syncing
        self._syncing = True
        try:
            rb.setChecked(True)
        finally:
            self._syncing = _was

    def _on_default_toggled(self, on: bool) -> None:
        if not on:
            return
        rb = self.sender()
        col = rb.property("set_id") if rb is not None else None
        if not col:
            return
        if self._read_only_here():
            self._restore_default_radio()
            return
        self._default_set = col
        if self._buffer is not None:
            self._buffer["default_set"] = col
        else:
            self._settings.set("compliance_default_set", col)
            self._default_set_last_seen = self._prefs_now()[0]

    # --------------------------------------------------------------- helpers
    def _write_overrides(self) -> None:
        if self._read_only_here():
            # SHOWING, NOT EDITING. The same rule as the run's own numbers and
            # its columns, and for the same reason: nothing in a window that
            # says "Show limits…" may write, app-wide or not.
            return
        if self._buffer is not None:
            self._buffer["overrides"] = {k: dict(v) for k, v in self._overrides.items()}
        else:
            from core.settings import store_compliance_overrides
            store_compliance_overrides(self._settings, self._overrides)
            self._overrides_last_seen = self._prefs_now()[1]
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

    @staticmethod
    def _natural_column_widths(g: QGridLayout) -> "list[int]":
        """What one grid would give each column on its own, laid out at its
        own size hint. Read off the layout, never guessed from a style sheet:
        a wrapped heading's ``sizeHint`` is a heuristic and QSS padding lands
        only at polish, so both would lie about a column's real width.
        """
        holder = g.parentWidget()
        hint = g.sizeHint()
        if holder is not None:
            holder.resize(max(hint.width(), 1), max(hint.height(), 1))
        g.invalidate()
        g.activate()
        return [max(0, g.cellRect(0, ci).width()) for ci in range(g.columnCount())]

    def _sync_columns(self) -> None:
        """ONE column geometry for the head and the body, and the width the
        two of them ask for.

        The head and the rows are different layouts now, so nothing makes
        their columns agree by itself: left alone, a "Restore this column"
        button wider than a cell (F6: German is longer) would push its heading
        off the column it names, and every heading after it with it. Each
        column is therefore given the SAME explicit minimum width in both
        grids, the wider of what the two would take on their own.

        A hidden column is pinned to 0, because a minimum width is charged
        whether or not anything is painted in the column, and pinning it to
        its natural width would undo the hidden-column fix this window was
        opened for.
        """
        cols = self._column_ids()
        n = 2 + len(cols)
        # measure what each grid would take UNPINNED, or the gap folded in
        # below would be folded in again on every call
        for ci in range(n):
            self._head_grid.setColumnMinimumWidth(ci, 0)
            self._grid.setColumnMinimumWidth(ci, 0)
        head_w = self._natural_column_widths(self._head_grid)
        body_w = self._natural_column_widths(self._grid)
        for ci in range(n):
            if ci >= 2 and not self._column_shown(cols[ci - 2]):
                w = 0                       # a hidden column costs nothing
            else:
                w = max(head_w[ci] if ci < len(head_w) else 0,
                        body_w[ci] if ci < len(body_w) else 0)
                if ci:
                    w += COLUMN_GAP         # every column but the first
            self._head_grid.setColumnMinimumWidth(ci, w)
            self._grid.setColumnMinimumWidth(ci, w)
        self._pin_body_width()

    def _column_shown(self, col: str) -> bool:
        cb = self._column_checks.get(col)
        return True if cb is None else cb.isChecked()

    def _pin_body_width(self) -> None:
        """Pin the scrolled body, and the head with it, to the width the
        columns that are SHOWN need.

        F7 pinned it once, at build time, with every column visible. Hiding a
        column then left that width behind: the body stayed 1,405 px wide when
        its contents needed 909, and the horizontal scroll bar stayed with it,
        offering 496 px of nothing (measured on screen, 2026-09-10, Knut's
        beta-3 report). Re-pinned on every visibility change, the bar appears
        only when the columns really are wider than the window.

        BOTH halves, always. The head lives in its own widget with its own
        width, and a head left at the old width would lay its columns out over
        a longer span than the rows below it.
        """
        body = self._scroll.widget() if self._scroll is not None else None
        if body is None:
            return
        for g in (self._head_grid, self._grid):
            g.invalidate()
            g.activate()
        want = max(self._grid.sizeHint().width(), self._head_grid.sizeHint().width())
        body.setMinimumWidth(want)
        self._head.setMinimumWidth(want)
        self._match_head_to_body()
        # LEAVE THEM DIRTY. A grid laid out and marked clean at the width it
        # had a moment ago keeps that arithmetic when the widget is then given
        # its new width: ticking a hidden column back on left the row-label
        # column 138 px short of its own labels, head and body alike (measured
        # 2026-09-10). Invalidated last, the next real geometry pass rebuilds
        # at the width the widget actually gets.
        for g in (self._head_grid, self._grid):
            g.invalidate()

    def _match_head_to_body(self) -> None:
        """Give the head the body's width and the clip its height, then put it
        back under the body's current horizontal scroll."""
        body = self._scroll.widget() if self._scroll is not None else None
        if body is None or self._head is None:
            return
        h = max(self._head_grid.sizeHint().height(), 1)
        self._head.resize(max(body.width(), self._head.minimumWidth()), h)
        self._head_clip.setFixedHeight(h)
        self._on_hscroll(self._scroll.horizontalScrollBar().value())

    def _on_hscroll(self, value: int) -> None:
        """The head scrolls sideways with the body, and only sideways.

        A frozen head that did not follow would put every heading over the
        wrong column the moment the table is wider than the window, which is
        worse than the fault it was meant to fix.
        """
        if self._head is not None:
            self._head.move(-int(value), 0)

    def _set_column_visible(self, col: str, on: bool) -> None:
        for w in self._column_widgets.get(col, []):
            w.setVisible(on)
        self._sync_columns()

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

    def _run_column_really_moved(self) -> bool:
        """Whether the run's column ends this visit different from how it
        started. Compared through `limits_to_json`, the same shape that is
        written to disk, so two Limits that store the same thing compare equal.
        """
        from workflow.compliance_sets import limits_to_json
        if self._run_limits_at_open is None:
            return True                 # nothing to compare against; be safe
        try:
            return limits_to_json(self._run_limits) != self._run_limits_at_open
        except Exception:               # noqa: BLE001
            return True

    def done(self, result: int) -> None:  # noqa: D102
        # DID SOMEBODY ELSE MOVE THIS RUN WHILE THE WINDOW WAS OPEN?
        # Asked BEFORE the write below, because after it the answer is this
        # window's own. There is no other moment it can be asked from: the
        # report window sees only the state this `done()` leaves behind, and
        # both writers leave the same shape.
        if self._run is not None and self._run_stored_at_open is not None:
            _now = _stored_column(self._run)
            if _now is not None and _now != self._run_stored_at_open:
                self.run_limits_collided = True
                log.info("this run's limits were changed elsewhere while the "
                         "limits window was open: %s", self._run.dir)
        _dflt, _ovr = self._prefs_now()
        if ((self._default_set_last_seen is not None
             and _dflt != self._default_set_last_seen)
                or (self._overrides_last_seen is not None
                    and _ovr != self._overrides_last_seen)):
            self.prefs_collided = True
            log.info("the app-wide report limits were changed elsewhere while "
                     "the limits window was open")
        # DIRTY MEANS DIFFERENT, NOT TOUCHED.
        if (self._run is not None and self._run_dirty and self._run_editable
                and self._run_column_really_moved()):
            from workflow.run_compliance import set_run_limits
            try:
                set_run_limits(self._run, self._run_limits)
                self.run_limits_changed = True
            except OSError as exc:
                log.warning("could not store this run's limits: %s", exc)
        super().done(result)
