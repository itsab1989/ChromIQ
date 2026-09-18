"""“Which presets can be verified” — the window under the Create Chart presets
dropdown (#182, Knut, beta 22).

Knut asked for *"a window listing all the presets that fulfil the requirements
for verification on a specified report type and judge against selection"*, with
*"those charts suitable for verification"* highlighted, and for a preset that
does not qualify to say what it is missing.

**IT MARKS, IT DOES NOT FILTER, and that decision was measured rather than
guessed.** On the 177 built-in presets ChromIQ ships (2026-09-19):

=========================================  ==========  =========================
report type / limit set                    rows asked  answering every row
=========================================  ==========  =========================
any / ChromIQ default, tight, quick                 7  **177 of 177**
Grey and tone check / Custom ISO                    3  **177 of 177**
Colour summary or Full check / Custom ISO          16  **0 of 177** (13 each)
Printing record (not graded) / any                  0  every one, nothing judged
=========================================  ==========  =========================

A filter is therefore either a no-op or an empty window; it is never the thing
that helps. The list always holds every preset and marks each one, and a single
opt-in tick box narrows 177 rows to the 49 the star is on.

The zero is not a bug in the presets. Both Custom ISO columns put a limit on
the three reference rows, and **no preset chart can supply them**: a
colorimetric reference is written only beside a chart built FROM PROFILE GAMUT.
Every one of the other thirteen rows IS answered, the three control-strip rows
included, because `workflow.control_strip` builds a declaration out of a
chart's own patches when the chart is filed and all 177 fill the ladder past
its twenty-rung mark. The detail pane says which three are out of reach, in the
metric help icons' own words, which is why this window teaches instead of only
filtering.

Every judgement in here comes from :mod:`workflow.preset_eligibility`, which in
turn is :mod:`workflow.measurement_report`'s own eligibility code over a chart
that has not been printed yet. No sentence about what a chart can answer is
written twice.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.i18n import count_phrase, tr
from ui.fade_scroll import FadeScrollArea
from ui.theme import active_mode
from ui.widgets import NoScrollComboBox, WorkAreaClamped
from workflow import compliance_sets as CS
from workflow import measurement_report as MR
from workflow import preset_eligibility as PE

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# One row of the list
# ---------------------------------------------------------------------------
@dataclass
class PresetRow:
    """A preset as this window sees it: a name, a chart, and what it can do."""
    group: str
    label: str
    chart: "Path | None"
    patches: int
    pages: int
    builtin: bool
    starred: bool = False
    assessment: PE.Assessment = PE.UNCHECKED


# ---------------------------------------------------------------------------
# What is missing, in one line, before the metric's own remedy
# ---------------------------------------------------------------------------
#: One short sentence per reason code, saying WHAT is short. The lever that
#: follows it is the metric help icon's own `remedy` text, reused verbatim so
#: the two windows cannot drift: see `preset_eligibility.row_remedy`.
#:
#: Every code `workflow.preset_eligibility.classified_reasons` knows has an
#: entry, and `tests/test_the_preset_window_says_what_is_missing.py` fails when
#: one does not, because a row that says only "✕" teaches nobody anything.
def reason_line(code: str) -> str:
    """What this chart is short of, in one sentence."""
    return {
        MR.REASON_NEEDS_REFERENCE_FILE:
            tr("This chart carries no colorimetric reference."),
        MR.REASON_NO_REFERENCE:
            tr("This chart carries no aim values for its patches."),
        MR.REASON_NO_CONTROL_STRIP:
            tr("This chart declares no control strip."),
        MR.REASON_CONTROL_STRIP_TOO_SMALL:
            tr("The control strip this chart declares is too short."),
        MR.REASON_NO_GREYS:
            tr("This chart has no grey patches."),
        MR.REASON_TOO_FEW_STEPS:
            tr("The grey ramp on this chart has too few steps."),
        MR.REASON_NO_WHITE:
            tr("The grey ramp on this chart does not reach white."),
        MR.REASON_NO_BLACK:
            tr("The grey ramp on this chart does not reach black."),
        MR.REASON_NO_RAMP:
            tr("This chart has no tone ramp through the mid-tones."),
        MR.REASON_SMALL_SAMPLE:
            tr("This chart has too few patches for a worst twentieth of them "
               "to exist."),
        MR.REASON_TOO_FEW_SURFACE_PATCHES:
            tr("Too few of this chart's patches sit on the surface of the "
               "device cube."),
        MR.REASON_TOO_FEW_OUTER_PATCHES:
            tr("The most saturated quarter of this chart holds too few "
               "patches."),
        MR.REASON_NO_CORNERS:
            tr("This chart has no patch at any of the solid ink corners."),
        MR.REASON_NOT_COMPUTED:
            tr("ChromIQ cannot check this row on this chart."),
    }.get(code, tr("ChromIQ cannot check this row on this chart."))


#: Why a preset cannot be checked at all. Knut's window must say something
#: about every preset on the list, and "nothing" is not an option: a user
#: preset saved without its patch set is the one real case, and the sentence
#: names the tick box that fixes it.
def _unreadable_line(row: PresetRow) -> str:
    if row.chart is None:
        return tr(
            "This preset stores settings only, so ChromIQ has no patch set to "
            "check. Load or generate its chart, then save the preset again "
            "with \"Build from the currently loaded patch set (attach its "
            ".ti1)\" ticked, and it will be checked like the rest.")
    return tr(
        "ChromIQ could not read this preset's patch set, so it cannot say "
        "what the chart can answer.")


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------
class PresetVerificationDialog(WorkAreaClamped, QDialog):
    """The list of presets, marked against one report type and one limit set."""

    def __init__(self, rows: "list[PresetRow]",
                 overrides: "dict | None" = None,
                 parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Which presets can be verified"))
        self._rows = list(rows)
        self._overrides = overrides
        self._build()
        self.resize(1040, min(700, self._work_area_cap(700)))
        self._keep_inside_the_work_area()
        self.refresh()

    # -- construction ----------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        intro = QLabel(tr(
            "Every preset ChromIQ ships, and your own, against the rows a "
            "report of this type judged against this limit set asks of a "
            "chart. Nothing is hidden: pick a preset to see what it can "
            "answer and what it cannot."), self)
        intro.setWordWrap(True)
        intro.setObjectName("info")
        outer.addWidget(intro)

        # -- the two pulldowns
        picks = QHBoxLayout()
        picks.setSpacing(8)
        picks.addWidget(QLabel(tr("Report type:"), self))
        self._type_combo = NoScrollComboBox(self)
        for tid, name, blurb, built in MR.REPORT_TYPE_MENU:
            if not built:
                continue
            self._type_combo.addItem(tr(name), userData=tid)
            self._type_combo.setItemData(
                self._type_combo.count() - 1, tr(blurb),
                Qt.ItemDataRole.ToolTipRole)
        picks.addWidget(self._type_combo, stretch=1)
        picks.addSpacing(12)
        picks.addWidget(QLabel(tr("Judged against:"), self))
        self._set_combo = NoScrollComboBox(self)
        for sid in CS.selectable_set_ids(self._overrides):
            self._set_combo.addItem(CS.set_label(sid), userData=sid)
            self._set_combo.setItemData(
                self._set_combo.count() - 1, tr(CS.SET_BY_ID[sid].blurb),
                Qt.ItemDataRole.ToolTipRole)
        picks.addWidget(self._set_combo, stretch=1)
        outer.addLayout(picks)

        self._asked_label = QLabel("", self)
        self._asked_label.setWordWrap(True)
        outer.addWidget(self._asked_label)

        self._only_star = QCheckBox(
            tr("Show only the presets made for verification"), self)
        outer.addWidget(self._only_star)

        star_note = QLabel(tr(
            "★ marks a chart made for verification: one printed page, "
            "{max_patches} patches or fewer, and nothing withheld that a "
            "different patch set would supply. The mark describes the chart, "
            "so it does not change with the two pulldowns above.").format(
                max_patches=PE.VERIFICATION_MAX_PATCHES), self)
        star_note.setWordWrap(True)
        star_note.setObjectName("info")
        outer.addWidget(star_note)

        # -- the list and the detail
        split = QSplitter(Qt.Orientation.Horizontal, self)
        self._tree = QTreeWidget(split)
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels([tr("Preset"), tr("Patches"), tr("Pages"),
                                    tr("Rows answered")])
        self._tree.setRootIsDecorated(True)
        self._tree.setUniformRowHeights(True)
        self._tree.setAlternatingRowColors(True)
        # The NAME takes the leftover width and the three figures keep a
        # fixed one. With the last section stretching instead, 240 px of empty
        # column sat to the right of "Rows answered" while every preset name
        # was elided; photographed before this line.
        from PyQt6.QtWidgets import QHeaderView
        head = self._tree.header()
        head.setStretchLastSection(False)
        head.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c, wdt in ((1, 80), (2, 70), (3, 140)):
            head.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self._tree.setColumnWidth(c, wdt)
        # A BOUND METHOD, never a self-capturing lambda on a signal a widget's
        # own child emits: CLAUDE.md, the fade-scroll SIGSEGV.
        self._tree.currentItemChanged.connect(self._on_selected)
        split.addWidget(self._tree)

        detail_host = QWidget(split)
        dh = QVBoxLayout(detail_host)
        dh.setContentsMargins(0, 0, 0, 0)
        self._detail_scroll = FadeScrollArea(detail_host)
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setFrameShape(FadeScrollArea.Shape.NoFrame)
        self._detail_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # A DIALOG NEVER RECEIVES `MainWindow.apply_theme`'s BROADCAST, and
        # `FadeScrollArea` starts in dark. Photographed on the light theme
        # before this line: the bottom fade painted a black band with white
        # text over the detail pane's last paragraph. `_ToolDialogBase` does
        # the same thing for the same reason.
        self._detail_scroll.set_appearance(active_mode())
        self._detail = QWidget()
        self._detail_layout = QVBoxLayout(self._detail)
        self._detail_layout.setContentsMargins(10, 4, 10, 10)
        self._detail_layout.setSpacing(6)
        self._detail_scroll.setWidget(self._detail)
        dh.addWidget(self._detail_scroll)
        split.addWidget(detail_host)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        outer.addWidget(split, stretch=1)

        self._figures = QLabel("", self)
        self._figures.setWordWrap(True)
        outer.addWidget(self._figures)

        bb = QDialogButtonBox(self)
        close = bb.addButton(tr("Close"), QDialogButtonBox.ButtonRole.RejectRole)
        close.setDefault(True)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        self._type_combo.currentIndexChanged.connect(self._on_choice_changed)
        self._set_combo.currentIndexChanged.connect(self._on_choice_changed)
        self._only_star.toggled.connect(self._on_choice_changed)

    # -- the current choice ----------------------------------------------
    def current_type(self) -> str:
        return str(self._type_combo.currentData() or "")

    def current_set(self) -> str:
        return str(self._set_combo.currentData() or "")

    # -- slots (bound methods, never lambdas) ----------------------------
    def _on_choice_changed(self, *_a) -> None:
        self.refresh()

    def _on_selected(self, current, _previous=None) -> None:
        self._show_detail(current.data(0, Qt.ItemDataRole.UserRole)
                          if current is not None else None)

    # -- the work --------------------------------------------------------
    def refresh(self) -> None:
        """Re-assess every preset against the current choice and redraw."""
        type_id, set_id = self.current_type(), self.current_set()
        for row in self._rows:
            row.assessment = PE.assess(row.chart, type_id, set_id,
                                       self._overrides)
            row.starred = PE.made_for_verification(row.chart, row.patches,
                                                   row.pages)
        asked = PE.rows_asked(type_id, set_id, self._overrides)
        if not asked:
            self._asked_label.setText(tr(
                "This report type judges nothing, so no chart can fall short "
                "of it."))
        else:
            self._asked_label.setText(count_phrase(
                len(asked),
                tr("This report type and limit set ask 1 row of a chart."),
                tr("This report type and limit set ask {n} rows of a "
                   "chart.")))
        self._fill_tree()
        self._fill_figures()

    def _fill_tree(self) -> None:
        only = self._only_star.isChecked()
        keep_label = None
        cur = self._tree.currentItem()
        if cur is not None:
            row = cur.data(0, Qt.ItemDataRole.UserRole)
            keep_label = row.label if isinstance(row, PresetRow) else None
        self._tree.clear()
        bold = self._tree.font()
        bold.setBold(True)
        select_me = None
        for group in dict.fromkeys(r.group for r in self._rows):
            members = [r for r in self._rows
                       if r.group == group and (r.starred or not only)]
            if not members:
                continue
            head = QTreeWidgetItem(self._tree, [group, "", "", ""])
            head.setFirstColumnSpanned(True)
            head.setFont(0, bold)
            head.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for r in members:
                item = QTreeWidgetItem(head, self._columns(r))
                item.setData(0, Qt.ItemDataRole.UserRole, r)
                if r.starred:
                    item.setFont(0, bold)
                if r.label == keep_label:
                    select_me = item
            head.setExpanded(True)
        if select_me is not None:
            self._tree.setCurrentItem(select_me)
        else:
            self._show_detail(None)

    def _columns(self, row: PresetRow) -> "list[str]":
        name = ("★  " + row.label) if row.starred else row.label
        a = row.assessment
        if not a.checked:
            verdict = tr("Cannot be checked")
        elif not a.asked:
            verdict = tr("Nothing is judged")
        else:
            verdict = tr("{n} of {total} rows").format(
                n=len(a.answered), total=len(a.asked))
        return [name,
                str(row.patches) if row.patches else "",
                str(row.pages) if row.pages else "",
                verdict]

    def _fill_figures(self) -> None:
        shown = [r for r in self._rows
                 if r.starred or not self._only_star.isChecked()]
        s = PE.summarise(shown)
        self._figures.setText(
            tr("Presets listed: {listed}     Made for verification: "
               "{starred}     Answering every row asked: {complete}").format(
                   listed=s["listed"], starred=s["starred"],
                   complete=s["complete"]))

    # -- the detail pane -------------------------------------------------
    def _clear_detail(self) -> None:
        while self._detail_layout.count():
            it = self._detail_layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

    def _add(self, text: str, *, bold: bool = False, info: bool = False,
             indent: int = 0) -> QLabel:
        lab = QLabel(text, self._detail)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        if bold:
            f = lab.font()
            f.setBold(True)
            lab.setFont(f)
        if info:
            lab.setObjectName("info")
        if indent:
            lab.setContentsMargins(indent, 0, 0, 0)
        self._detail_layout.addWidget(lab)
        return lab

    def _show_detail(self, row: "PresetRow | None") -> None:
        self._clear_detail()
        if row is None:
            self._add(tr("Select a preset on the left to see what it can "
                         "answer."), info=True)
            self._detail_layout.addStretch()
            return
        self._add(row.label, bold=True)
        # NEVER "0 patches · 0 pages". A zero here means ChromIQ does not
        # know, and printing it as a number is a false statement about the
        # preset: measured on a user preset saved without its patch set, the
        # pane said "0 patches · 0 pages" about a preset whose chart it had
        # simply never seen.
        facts = []
        if row.patches:
            facts.append(count_phrase(row.patches, tr("1 patch"),
                                      tr("{n} patches")))
        if row.pages:
            facts.append(count_phrase(row.pages, tr("1 page"), tr("{n} pages")))
        if facts:
            self._add("   ·   ".join(facts), info=True)
        if row.starred:
            self._add(tr("★  Made for verification."))
        elif row.chart is not None and not row.pages:
            # A USER PRESET'S PAGE COUNT IS NOT KNOWABLE FROM ITS PATCH SET.
            # How many sheets a set lays out depends on the instrument, the
            # paper and the patch width, so the star is withheld and this says
            # why rather than leaving a reader to wonder.
            self._add(tr(
                "ChromIQ cannot tell how many pages this preset lays out "
                "until its chart is generated, so it is not marked as made "
                "for verification."), info=True)

        a = row.assessment
        if not a.checked:
            self._add(tr("Cannot be checked"), bold=True)
            self._add(_unreadable_line(row))
            self._detail_layout.addStretch()
            return
        if not a.asked:
            self._add(tr("This report type judges nothing, so this preset "
                         "cannot fall short of it."))
            self._detail_layout.addStretch()
            return

        if a.answered:
            self._add(tr("This chart can answer"), bold=True)
            for rid in a.answered:
                self._add("✓  " + tr(PE.row_label(rid)), indent=6)
        if a.missing:
            self._add(tr("This chart cannot answer"), bold=True)
            for rid, why in a.missing:
                self._add("✕  " + tr(PE.row_label(rid)), indent=6)
                self._add(reason_line(why), info=True, indent=22)
                remedy = PE.row_remedy(rid)
                if remedy:
                    self._add(tr(remedy), info=True, indent=22)
        else:
            self._add(tr("This chart answers every row this report type and "
                         "limit set ask of it."))
        self._detail_layout.addStretch()
