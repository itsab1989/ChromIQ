"""Reusable ChromIQ layout-engine options panel (issue #93).

The same control set is shown in **Preferences → Chart Layout** (as the defaults
editor) and in the **Create Chart → Manual** module (as the per-chart mirror),
so the two can't drift.  The panel edits the layout-specific fields of a
:class:`~workflow.layout_engine.presets.LayoutRecipe`; the host supplies the
instrument / paper / mode (those live in the surrounding selectors).

It is Qt-only UI glue — no engine logic beyond reading/writing the recipe.
"""
from __future__ import annotations

from contextlib import contextmanager

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMenu,
    QToolButton, QVBoxLayout, QWidget,
)

from core.i18n import tr
from core.logger import get_logger
from ui.tooltip_button import TooltipButton
from ui.widgets import (
    CollapsibleGroupBox,
    ElidingComboBox,
    NoScrollDoubleSpinBox,
    NoScrollSpinBox,
    WrappingCheckBox,
)
from workflow.layout_engine.presets import LayoutRecipe

log = get_logger(__name__)

# Sheet-text placeholders, filled in at build time by chart.build_chart with
# human-readable values (e.g. {instrument} → "i1Pro3+", {paper} → "A4 landscape",
# {patchcount} → "576 patches", {seed} → "seed 1234", {dpi} → "300 dpi").
SHEET_TOKENS = (
    ("project", tr("Printer profile project name")),
    ("rundescription", tr("This run's description (or the calibration's)")),
    ("page", tr("This page, e.g. “page 1/3”")),
    ("date", tr("Build date")),
    ("paper", tr("Paper size & orientation")),
    ("instrument", tr("Instrument name")),
    ("patchcount", tr("Patch count (with “patches”)")),
    ("pages", tr("Total number of pages")),
    ("seed", tr("Seed (with “seed”)")),
    ("dpi", tr("Resolution (with “dpi”)")),
)


# Font sizes are shown to the user in points (Word/PowerPoint/PDF units) but
# stored and rendered by the engine in mm. A font drawn at S mm becomes
# S·dpi/25.4 px, i.e. a point size of S·72/25.4 — so pt = mm · 72/25.4 (Knut).
PT_PER_MM = 72.0 / 25.4          # ≈ 2.835
MM_PER_PT = 25.4 / 72.0          # ≈ 0.3528


def mm_to_pt(mm: float) -> float:
    """Round-trip-stable mm → points for the size spinboxes (0 stays 0=auto)."""
    return round(float(mm or 0.0) * PT_PER_MM)


def pt_to_mm(pt: float) -> float:
    """Points → mm for storing/rendering (0 stays 0=auto)."""
    return round(float(pt or 0.0) * MM_PER_PT, 2)


class LayoutOptionsPanel(QWidget):
    """All layout-engine controls except instrument/paper/mode."""

    changed = pyqtSignal()

    # Labels mirror the printtarg -i combobox (data/parameters.yaml) so the engine
    # and printtarg show the same instrument names (Knut). Codes stay i1/p3/CM/SS.
    INSTRUMENTS = [("i1", "i1Pro / i1Pro 2 / i1Pro 3"),
                   ("p3", "i1Pro 3 Plus"),
                   ("CM", "ColorMunki / i1Studio / ColorChecker Studio"),
                   ("SS", "SpectroScan (flatbed)"),
                   ("CR30", "CR30 (ChnSpec, patch by patch)")]

    @staticmethod
    def mode_label_for(inst: str) -> str:
        """The selector's label — it isn't really a generic "Mode" (#93, Knut):
        for i1/p3 it's the clip border, for CM the density, for SS the shape."""
        if inst in ("i1", "p3"):
            return tr("Clip border:")
        if inst == "CM":
            return tr("Density:")
        if inst == "SS":
            return tr("Patch shape:")
        if inst == "CR30":
            # The CR30 offers the SpectroScan's shape choice, so the control
            # says what it does (Basti, 2026-08-28).
            return tr("Patch shape:")
        return tr("Mode:")

    @staticmethod
    def mode_tooltip_for(inst: str) -> tuple[str, str]:
        """(title, body) for the Mode selector's ⓘ, describing only the option
        that actually applies to *inst* — not every instrument's (#93, Knut)."""
        if inst in ("i1", "p3"):
            return (tr("Clip border"),
                    tr("Whether a CLIP BORDER is printed — the white strip the "
                       "measuring rail grips so it can pull the chart through. "
                       "Turning it off frees that space for more patches; only do "
                       "so if your rig doesn't need it. Choose which edge it sits "
                       "on, and what it carries (a notes box, text or a logo), in "
                       "the Clip-border content section."))
        if inst == "CM":
            return (tr("Reading density"),
                    tr("How densely the ColorMunki reads. “Hand-held” still reads "
                       "whole strips — just a few large, widely-spaced patches — "
                       "with no accessory needed. “High density (rig)” needs the "
                       "measuring-rig accessory and packs far more patches per "
                       "sheet. “Extra-high density” packs even more (a ChromIQ "
                       "extension) — only use it if your patches stay large enough "
                       "to read reliably (watch the warning).\n\n"
                       "Density applies to both Create-layout choices. With "
                       "“Prioritise chart area” it sets the smallest patch the "
                       "layout may use, so it still decides how many patches "
                       "fit — unless you pin both columns and rows, which fixes "
                       "the grid outright."))
        if inst == "SS":
            return (tr("Patch shape"),
                    tr("Rectangular or hexagonal patches. Hexagons tessellate "
                       "tighter, fitting a few more patches per sheet; "
                       "rectangular is the safe default."))
        if inst == "CR30":
            return (tr("Patch shape"),
                    tr("Rectangular or hexagonal patches — and on a CR30, "
                       "hexagonal is worth a serious look.\n\n"
                       "The CR30 is a ROUND instrument: a 33 mm barrel reading "
                       "through a 4 mm circular window. A round window can "
                       "never use the corners of a square patch, so on a "
                       "square grid that paper is simply spent. Hexagons are "
                       "the tightest way to pack round openings into a sheet — "
                       "90.7 % of the area is within reach of a circle, "
                       "against 78.5 % for squares — so you keep exactly the "
                       "same room around the aperture while each patch uses "
                       "less paper. Measured on A4 at the standard size: 532 "
                       "patches rectangular, 576 hexagonal.\n\n"
                       "The honeycomb also helps you aim. Six sides funnel a "
                       "round barrel towards the middle of the cell in a way "
                       "four right angles do not, and the interlocking rows "
                       "make it harder to lose your place in a large grid.\n\n"
                       "The shape costs a CR30 nothing to read. It matters "
                       "only to an instrument that has to travel ALONG a row "
                       "of patches, and a CR30 never does — you lift it onto "
                       "one patch, press the button on the instrument, and "
                       "lift it onto the next.\n\n"
                       "One cost worth knowing about. The scanner and camera "
                       "tools turn a honeycomb chart away unless you switch "
                       "them on for it in Preferences → Beta. If you might "
                       "ever want to read this chart with a flatbed scanner "
                       "instead of the CR30, stay on Rectangular.\n\n"
                       "Either shape is a grid with row numbers down the left "
                       "and column letters along the top, so you can always "
                       "find the patch ChromIQ is asking for. Patch size is "
                       "PROVISIONAL — the 10 mm starting point is 2.5 times "
                       "the CR30's 4 mm aperture, the same ratio the i1Pro "
                       "uses — but nobody has yet measured how small a CR30 "
                       "patch can safely be. Make them bigger in Patch size "
                       "below if you find yourself missing patches."))
        return (tr("Layout mode"),
                tr("A per-instrument layout choice that keeps its own saved "
                   "preset."))

    @staticmethod
    def modes_for(inst: str) -> list[tuple[str, str]]:
        if inst in ("i1", "p3"):
            return [("clip", tr("On")),
                    ("noclip", tr("Off — more patches"))]
        if inst == "CM":
            return [("freehand", tr("Hand-held")), ("high", tr("High density (rig)")),
                    ("extrahigh", tr("Extra-high density"))]
        if inst == "SS":
            return [("flat", tr("Rectangular")), ("hex", tr("Hexagonal — denser"))]
        if inst == "CR30":
            return [("flat", tr("Rectangular")), ("hex", tr("Hexagonal — denser"))]
        return [("default", tr("Default"))]

    def __init__(self, parent: QWidget | None = None, *,
                 with_calibration: bool = False, with_selectors: bool = False,
                 defer_clip_preview: bool = False) -> None:
        super().__init__(parent)
        # Set BEFORE any widget exists: constructing the panel already renders
        # the clip preview a handful of times. A caller that is going to load a
        # recipe straight afterwards (Preferences -> Chart Layout) passes True
        # here and calls `resume_clip_preview()` when it has finished, so the
        # whole build costs one render instead of a dozen. See
        # `_refresh_clip_preview` for why that is safe.
        self._suspend_clip_preview = bool(defer_clip_preview)
        self._loading = False
        #: Millimetre spin boxes whose width is settled in `_fit_spin_widths()`
        #: once the style has been polished — see `small_mm`.
        self._fitted_spins: list = []
        self._spin_widths_fitted = False
        self._with_calibration = with_calibration
        self._with_selectors = with_selectors
        # Per-spacer manual colour overrides {str(flat_idx): "#hex"} — set by
        # clicking spacers in the editor preview; carried in the recipe (#93).
        self._spacer_overrides: dict = {}
        # Ruler helper markers (#152) — carried through the recipe, controlled
        # from the preview's "Measure from Preview" panel. See apply_to_recipe.

        self._border: float = 6.0      # base margin (-m); preserved, no control
        self._inst = "i1"           # last-known instrument / clip state, for
        self._clip = True           # clip-border-width row visibility
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        self.instr = self.paper = self.mode = self.pages = None
        if with_selectors:
            sel = QGridLayout()
            # Instrument and Mode each get a full-width row.
            self.instr = ElidingComboBox(self)
            for k, lbl in self.INSTRUMENTS:
                self.instr.addItem(lbl, k)
            sel.addWidget(QLabel(tr("Instrument:"), self), 0, 0)
            sel.addWidget(self.instr, 0, 1, 1, 3)
            sel.addWidget(TooltipButton(
                tr("Instrument"),
                tr("The measuring device you'll read the printed chart with. It "
                   "sets the patch size, strip length and overall layout the chart "
                   "is built for, so pick the one you actually own — a chart laid "
                   "out for one instrument may not read correctly on another."),
                self), 0, 4)
            # Mode (= ColorMunki density / i1 clip mode / SpectroScan shape) and
            # the CM/SS Clip-border toggle are created here but ADDED TO THE LAYOUT
            # FRAME (below), grouped with the other layout choices for better order
            # (Knut #93). Labels/tips stay referenced for the conditional enabling.
            self.mode = ElidingComboBox(self)
            self._mode_lbl = QLabel(tr("Mode:"), self)
            _mt, _mb = self.mode_tooltip_for("i1")
            self._mode_tip = TooltipButton(_mt, _mb, self)
            self._clip_enable_lbl = QLabel(tr("Clip border:"), self)
            self.clip_enable = ElidingComboBox(self)
            self.clip_enable.addItem(tr("Off — more patches"), "off")
            self.clip_enable.addItem(tr("On"), "on")
            self.clip_enable.currentIndexChanged.connect(self._on_clip_enable_changed)
            self._clip_enable_tip = TooltipButton(
                tr("Clip border"),
                tr("Reserve a clip-border strip on this chart (the same option the "
                   "i1Pro has). On reserves a band you can fill with a notes box, "
                   "text or a logo in the Clip-border content section below; Off "
                   "uses the whole page for patches. Choose which edge it sits on "
                   "in that section.\n\n"
                   "If you also print the ruler helper markers (the short dashes "
                   "along the page edges, switched on under the preview), a dash "
                   "can cross this band. That is allowed on purpose — the dashes "
                   "keep step with the patches wherever they fall. If one lands "
                   "awkwardly, move it with its own “Distance from page edge”, "
                   "or make it shorter."), self)
            # Paper + Pages share a row, directly under Instrument (Knut #93);
            # paper gets the stretch (wider).
            self.paper = ElidingComboBox(self)
            sel.addWidget(QLabel(tr("Paper:"), self), 1, 0)
            sel.addWidget(self.paper, 1, 1)
            self._pages_lbl = QLabel(tr("Pages:"), self)
            sel.addWidget(self._pages_lbl, 1, 2)
            self.pages = NoScrollSpinBox(self)
            self.pages.setRange(1, 20)
            self.pages.setValue(1)
            self.pages.setMaximumWidth(70)
            self.pages.valueChanged.connect(self._emit)
            sel.addWidget(self.pages, 1, 3)
            sel.addWidget(TooltipButton(
                tr("Paper and pages"),
                tr("Paper is the sheet size you'll print on — the profile is only "
                   "valid for the paper you actually use. Pages is how many sheets "
                   "to spread the patches across: more pages = more patches total "
                   "(and more ink and paper)."), self), 1, 4)
            # Custom paper W×H (shown only when Paper = "Custom…").
            self._custom_paper_w = QWidget(self)
            _cpl = QHBoxLayout(self._custom_paper_w)
            _cpl.setContentsMargins(0, 0, 0, 0); _cpl.setSpacing(6)
            _cpl.addWidget(QLabel(tr("Custom size (mm):"), self))
            self.custom_w = NoScrollDoubleSpinBox(self)
            self.custom_h = NoScrollDoubleSpinBox(self)
            for _cs in (self.custom_w, self.custom_h):
                _cs.setRange(20, 2000); _cs.setDecimals(0); _cs.setMaximumWidth(80)
                _cs.valueChanged.connect(self._emit)
            self.custom_w.setValue(210); self.custom_h.setValue(297)
            _cpl.addWidget(self.custom_w); _cpl.addWidget(QLabel("×", self))
            _cpl.addWidget(self.custom_h); _cpl.addStretch()
            sel.addWidget(self._custom_paper_w, 2, 0, 1, 4)   # directly below Paper
            self._custom_paper_w.setVisible(False)
            sel.setColumnStretch(1, 1)        # paper / instrument / mode expand
            v.addLayout(sel)
            # Long paper labels shouldn't force the panel wide; the paper combo
            # gets a roomier minimum (it shares its row only with Pages) while
            # instrument/mode stay capped. The dropdown always shows full text.
            from PyQt6.QtWidgets import QComboBox
            self.paper.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.paper.setMinimumContentsLength(11)   # elides long labels; full text in popup
            for _c in (self.instr, self.mode):
                _c.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                _c.setMinimumContentsLength(10)
            self.instr.currentIndexChanged.connect(self._on_instr_changed)
            self.paper.currentIndexChanged.connect(self._on_paper_changed)
            self.mode.currentIndexChanged.connect(self._apply_mode_defaults)
            self.mode.currentIndexChanged.connect(self._sync_clip_content_for_mode)
            self.mode.currentIndexChanged.connect(self._emit)
            self.mode.currentIndexChanged.connect(self._update_clip_visibility)
            self._on_instr_changed()

        def mm(special_auto: bool = False, top: float = 300.0) -> NoScrollDoubleSpinBox:
            sb = NoScrollDoubleSpinBox(self)
            sb.setRange(0, top)
            sb.setDecimals(1)
            sb.setSingleStep(0.5)
            sb.setSuffix(" mm")
            sb.setMinimumWidth(96)          # room for "300,0 mm" + buttons
            if special_auto:
                sb.setSpecialValueText(tr("auto"))
            sb.valueChanged.connect(self._emit)
            return sb

        def scale() -> NoScrollDoubleSpinBox:
            sb = NoScrollDoubleSpinBox(self)
            sb.setRange(0.5, 3.0)
            sb.setDecimals(3)
            sb.setSingleStep(0.05)
            sb.setMinimumWidth(96)
            sb.valueChanged.connect(self._emit)
            return sb

        from PyQt6.QtCore import Qt as _Qt

        def add_row(grid, r, label, control, tip=None, *,
                    align_left: bool = False):
            """label | control (control fills the column → no clipping).
            Returns the placed widgets so a whole row can be shown/hidden."""
            lbl = QLabel(label, self)
            # A LABEL THAT CAN WRAP CAN ALSO SHRINK.
            #
            # An unwrapped QLabel reports its whole text as a hard minimum, so
            # the label column could never be narrower than the longest label in
            # it — and this panel lives in a left pane locked at 580 px. In
            # German the labels are ~88 px wider than the English they were
            # sized against ("Layout erstellen:" 469 px against "Create
            # layout:" 381), which pushed the panel's minimum to 519 and put a
            # HORIZONTAL SCROLLBAR under the whole Expert section (Basti,
            # 2026-08-27, twice — the second time to say I had reported it and
            # not fixed it).
            #
            # Wrapping drops the panel's floor from 519 to 476 in German and
            # 431 to 389 in English. It costs nothing when there is room: a
            # label only takes a second line once it genuinely cannot fit, and
            # nothing is elided, so no word is ever lost — which matters more
            # here than tidiness, because these labels name the controls the
            # help text quotes.
            lbl.setWordWrap(True)
            # Labels are right-aligned against the control column everywhere
            # else. `align_left` puts them flush with the group's left edge
            # instead, so a group whose first line is a full-width checkbox
            # reads as one block (Basti, on screen) — the controls still share
            # column 1, so they keep starting at the same x.
            grid.addWidget(lbl, r, 0, _Qt.AlignmentFlag.AlignLeft if align_left
                           else _Qt.AlignmentFlag.AlignRight)
            grid.addWidget(control, r, 1)
            if tip is not None:
                grid.addWidget(tip, r, 2)
            grid.setColumnStretch(1, 1)
            return [w for w in (lbl, control, tip) if w is not None]

        def cell(*widgets):
            """A compact left-aligned row of small widgets in one grid cell."""
            box = QHBoxLayout(); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(6)
            for w in widgets:
                box.addWidget(w)
            box.addStretch()
            wrap = QWidget(self); wrap.setLayout(box)
            return wrap

        def cell_fill(grow, *fixed):
            """First widget fills the cell; trailing widgets keep their size."""
            box = QHBoxLayout(); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(6)
            box.addWidget(grow, 1)
            for w in fixed:
                box.addWidget(w)
            wrap = QWidget(self); wrap.setLayout(box)
            return wrap

        def mm_inch(spin):
            """A mm spinbox with a live, non-editable inch readout to its right —
            metric + imperial at a glance (#93, Knut). Sits in the control
            column's slack, so it doesn't widen the panel. Blank for a spinbox
            on its special ('auto'/'square') value."""
            inch = QLabel("", self)
            inch.setStyleSheet("color: #909090; font-size: 10px;")
            inch.setMinimumWidth(48)

            def _upd(*_a):
                v = spin.value()
                if spin.specialValueText() and v <= spin.minimum() + 1e-9:
                    inch.setText("")
                else:
                    # 3 decimals so a 0.1 mm change is visible in the inch readout
                    # (Knut beta.38).
                    inch.setText(f"{v / 25.4:.3f}″")
            spin.valueChanged.connect(_upd)
            _upd()
            # Expose the updater so callers that fill the value with signals
            # blocked (e.g. filling instrument margins) can refresh the inch
            # readout by hand — otherwise it would show the previous value
            # (Sebastian). Harmless no-op for spinboxes without an inch column.
            spin._refresh_inch = _upd
            box = QHBoxLayout(); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(6)
            box.addWidget(spin); box.addWidget(inch); box.addStretch()
            wrap = QWidget(self); wrap.setLayout(box)
            return wrap
        self._mm_inch = mm_inch

        # "Show strip indicators" (the per-chart on/off) lives in the Layout frame
        # right above Clip border (Knut #93); the indicator *styling* (font / size
        # / rotation / underline …) moved to Preferences → Chart Layout. Created
        # unconditionally so from_recipe/to_recipe work even without selectors.
        self.show_indicators = WrappingCheckBox(tr("Show strip indicators"), self)
        self.show_indicators.setChecked(True)
        self.show_indicators.toggled.connect(self._on_show_indicators)
        self.show_indicators.toggled.connect(self._emit)
        self._show_indicators_tip = TooltipButton(
            tr("Strip indicators"),
            tr("The small letter label printed above each strip (A, B, C…) so "
               "you always know which strip you're measuring and in what order. "
               "Turn off only if you have another way to keep the strips "
               "straight. Set the font, size and underline style in "
               "Preferences → Chart Layout."), self)

        from PyQt6.QtWidgets import QLineEdit, QPushButton

        def small_mm(top: float = 60.0, *,
                     special_auto: bool = False) -> NoScrollDoubleSpinBox:
            sb = NoScrollDoubleSpinBox(self)
            sb.setRange(0, top); sb.setDecimals(1); sb.setSingleStep(0.5)
            # WIDE ENOUGH FOR THE WORD THIS BOX ACTUALLY SHOWS — AND NO WIDER.
            #
            # These were 84/96 px, with a comment reading `room for "300,0" /
            # "auto" + buttons` — sized against the four-letter ENGLISH word.
            # German says "automatisch", which needs 72 px in a field that
            # offers exactly 72, so it fitted by nothing at all offscreen and
            # was clipped to "natisch" on a real display (Basti, 2026-08-27,
            # with a screenshot). Spanish and Portuguese sit 7 px behind it.
            #
            # A hard-coded width can only ever be right for the language it was
            # measured in. Ask the font instead, and leave a real margin.
            #
            # ONLY the two patch-size boxes ever set a special value text; the
            # other eleven callers show nothing but a number. Sizing all of them
            # for "automatisch" put 106 px into every one, and the three of them
            # sitting side by side in "Sheet text" then needed 404 px in Spanish
            # and 418 in Portuguese — which is what still pushed those two
            # languages into horizontal scrolling after the combo below was
            # fixed. Widen for the word only where the word can appear.
            _fm = sb.fontMetrics()
            _widest = _fm.horizontalAdvance(f"{top:.1f}".replace(".", ","))
            if special_auto:
                sb.setSpecialValueText(tr("auto"))
                _widest = max(_widest, _fm.horizontalAdvance(tr("auto")))
            #
            # The floors used to be `max(84, …)` / `max(96, …)`, which is the
            # ENGLISH width this helper was born with. 84 px happened to be
            # right, but only because the `_chrome` constant beside it was
            # wrong: the buttons, frame and text padding cost 55 px with this
            # stylesheet, not 34, so `_widest + 34` was 21 px short and the 84
            # was quietly covering for it. Neither number can be checked by
            # reading the code, and both are invalidated by any QSS change.
            #
            # So the width is settled once for real in `_fit_spin_widths()`,
            # which asks the STYLE what the chrome is — and can only do that
            # after the widget is polished, because before that the same query
            # answers 20 px. What is set here is a provisional value good
            # enough for the first layout pass.
            _chrome = 55
            sb.setMinimumWidth(_widest + _chrome)
            sb.setMaximumWidth(_widest + _chrome + 8)
            self._fitted_spins.append(sb)
            sb.valueChanged.connect(self._emit)
            return sb

        def small_pt(top_pt: float = 60.0) -> NoScrollDoubleSpinBox:
            """A font-size spinbox in **points** — the familiar unit from Word /
            PowerPoint / PDF (12 pt is body text, ~18–24 pt a heading). The
            engine stores and renders these sizes in mm, so the value is
            converted at the recipe boundary (see PT_PER_MM). 0 = "auto"."""
            sb = NoScrollDoubleSpinBox(self)
            sb.setRange(0, top_pt); sb.setDecimals(0); sb.setSingleStep(1)
            # Provisional only — settled in `_fit_spin_widths()` once the style
            # has been polished, for the same reason as `small_mm` above: 84/96
            # is the English width this was measured at, and these boxes carry
            # the translated "auto" as their special value.
            sb.setMinimumWidth(84)
            sb.setMaximumWidth(96)
            self._fitted_spins.append(sb)
            sb.valueChanged.connect(self._emit)
            return sb

        # The layout groups are split into two collapsible sections (Knut): Basic
        # (Layout, Page geometry, Randomisation) open by default, and Expert
        # Options (Patches & spacers, Output, Sheet text, Clip-border content,
        # Printer calibration) collapsed. Each group below is routed into one of
        # these instead of straight onto the panel.
        self._basic_frame = CollapsibleGroupBox(tr("Basic"), self)
        self._expert_frame = CollapsibleGroupBox(
            tr("Expert Options"), self, collapsed=True)
        _basic_v = QVBoxLayout(self._basic_frame.body)
        _basic_v.setContentsMargins(6, 6, 6, 6)
        _expert_v = QVBoxLayout(self._expert_frame.body)
        _expert_v.setContentsMargins(6, 6, 6, 6)
        v.addWidget(self._basic_frame)
        v.addWidget(self._expert_frame)

        # ---- Layout strategy (patch-first vs area-first, #93 / Knut) ----
        lg = QGroupBox(tr("Layout"), self)
        lgg = QGridLayout(lg)
        self.layout_mode = ElidingComboBox(self)
        self.layout_mode.addItem(
            tr("Prioritise chart area, then fit patches to it"), "area_first")
        self.layout_mode.addItem(
            tr("Prioritise patch size, then fit to page"), "patch_first")
        self.layout_mode.currentIndexChanged.connect(self._emit)
        self.layout_mode.currentIndexChanged.connect(self._sync_layout_mode)
        add_row(lgg, 0, tr("Create layout:"), self.layout_mode,
                tip=TooltipButton(
                    tr("Create layout"),
                    tr("Two ways to decide patch size vs. how many fit:\n\n"
                       "• Prioritise patch size — you set the patch size (or "
                       "scale) and ChromIQ fits as many patches as it can. Simple, "
                       "but the last strip may not reach the far margin.\n\n"
                       "• Prioritise chart area — you say how many strips "
                       "(columns) and/or patches per strip (rows) you want, and "
                       "ChromIQ SIZES the patches so the grid fills the usable area "
                       "(the space left inside your margins). The patch area always "
                       "lands exactly where you defined it; you trade patch size "
                       "for the grid you asked for. Watch that the patches don't "
                       "get too small for your instrument to read."), self))
        # Area-first fields (shown only in that mode).
        self._area_fields_w = QWidget(self)
        afg = QGridLayout(self._area_fields_w)
        afg.setContentsMargins(0, 0, 0, 0)
        self.area_cols = NoScrollSpinBox(self); self.area_cols.setRange(0, 200)
        self.area_cols.setSpecialValueText(tr("auto")); self.area_cols.setMaximumWidth(96)
        self.area_cols.valueChanged.connect(self._emit)
        self.area_cols.valueChanged.connect(self._sync_layout_mode)
        self.area_rows = NoScrollSpinBox(self); self.area_rows.setRange(0, 500)
        self.area_rows.setSpecialValueText(tr("auto")); self.area_rows.setMaximumWidth(96)
        self.area_rows.valueChanged.connect(self._emit)
        self.area_rows.valueChanged.connect(self._sync_layout_mode)
        # Patch shape as "minimum patch height, % of width" (Knut): 150 → height
        # 1.5× width. Stored in the recipe as a height:width fraction (value/100).
        # Default 100 % (square); no "square" special value — the arrows step it
        # up or down from 100 (Knut #93).
        self.area_ratio = NoScrollDoubleSpinBox(self)
        self.area_ratio.setRange(10.0, 1000.0); self.area_ratio.setDecimals(0)
        self.area_ratio.setSingleStep(10.0); self.area_ratio.setMaximumWidth(96)
        self.area_ratio.setSuffix(" %")
        self.area_ratio.setValue(100.0)
        self.area_ratio.valueChanged.connect(self._emit)
        self.area_min_patch = NoScrollDoubleSpinBox(self)
        self.area_min_patch.setRange(0.0, 100.0); self.area_min_patch.setDecimals(1)
        self.area_min_patch.setSingleStep(0.5); self.area_min_patch.setMaximumWidth(96)
        self.area_min_patch.setSpecialValueText(tr("auto"))
        self.area_min_patch.valueChanged.connect(self._emit)
        self.area_method = ElidingComboBox(self)
        self.area_method.addItem(tr("By patch width"), "by_width")
        self.area_method.addItem(tr("By columns / rows"), "by_grid")
        self.area_method.currentIndexChanged.connect(self._emit)
        self.area_method.currentIndexChanged.connect(self._sync_layout_mode)
        add_row(afg, 0, tr("Calculation method:"), self.area_method,
                tip=TooltipButton(
                    tr("Calculation method"),
                    tr("How to work out the patch grid inside the area:\n\n"
                       "• By patch width — you set the smallest patch width (and a "
                       "height %); ChromIQ fits as many as possible at that size "
                       "and grows them to fill the area. You know the strip width "
                       "you want, without juggling column counts.\n\n"
                       "• By columns / rows — you set exactly how many strips and "
                       "patches-per-strip; ChromIQ sizes the patches to fit. Full "
                       "control of the grid, but you tune the counts to land on a "
                       "patch size you like.\n\n"
                       "Both fill the same patch area defined by the margins."),
                    self))
        self._area_row_minpatch = add_row(afg, 1, tr("Minimum patch width (mm):"),
                mm_inch(self.area_min_patch),
                tip=TooltipButton(
                    tr("Minimum patch width"),
                    tr("The smallest strip (patch) width your instrument can read "
                       "reliably. ChromIQ fits as many strips as possible at this "
                       "width, then grows them slightly so the grid fills the area "
                       "exactly. The patch height follows the height % below."),
                    self))
        self._area_row_ratio = add_row(afg, 2,
                tr("Minimum patch height (% of width):"), self.area_ratio,
                tip=TooltipButton(
                    tr("Minimum patch height"),
                    tr("The patch height as a percentage of its width. 100% keeps "
                       "height = width (square); 150% makes each patch half again "
                       "as tall as it is wide; below 100% makes them wider than "
                       "tall. It's a minimum — the engine grows the patches from "
                       "here to fill the chart area."), self))
        self._area_row_cols = add_row(afg, 3, tr("Strips (columns):"), self.area_cols,
                tip=TooltipButton(
                    tr("Strips (columns)"),
                    tr("How many strips (columns of patches) to fit across the "
                       "page. ChromIQ makes the patches exactly wide enough that "
                       "this many strips span the usable width, so the block "
                       "reaches the margins evenly.\n\n"
                       "Leave it on “auto” and ChromIQ picks a count that gives a "
                       "patch close to your instrument's natural patch size — the "
                       "size it was designed to read — then fills the width to "
                       "that count."), self))
        self._area_row_rows = add_row(afg, 4, tr("Patches per strip (rows):"),
                self.area_rows,
                tip=TooltipButton(
                    tr("Patches per strip (rows)"),
                    tr("How many patches to stack down each strip. ChromIQ makes "
                       "the patches exactly tall enough that this many fit the "
                       "usable height.\n\n"
                       "Leave it on “auto” and ChromIQ picks a count that gives a "
                       "patch close to your instrument's natural patch size — the "
                       "size it was designed to read — then fills the height to "
                       "that count."), self))
        lgg.addWidget(self._area_fields_w, 1, 0, 1, 3)
        # "Show strip indicators" is a layout option (not a selector), so it is
        # ALWAYS placed here — otherwise, when the panel has no built-in selectors
        # (e.g. the Preferences → Chart Layout tab), the checkbox was created but
        # never added to a layout and floated at the panel's top-left, overlapping
        # the "Basic" frame header (Knut).
        lgg.addWidget(self.show_indicators, 2, 1)
        lgg.addWidget(self._show_indicators_tip, 2, 2)
        # Mode (density / clip mode / shape) and the CM/SS Clip-border toggle are
        # SELECTORS, so they only appear when the panel owns them (#93); in
        # Settings the same selectors are provided by the tab itself.
        if getattr(self, "mode", None) is not None:
            lgg.addWidget(self._mode_lbl, 3, 0)
            lgg.addWidget(self.mode, 3, 1)
            lgg.addWidget(self._mode_tip, 3, 2)
            lgg.addWidget(self._clip_enable_lbl, 4, 0)
            lgg.addWidget(self.clip_enable, 4, 1)
            lgg.addWidget(self._clip_enable_tip, 4, 2)
        # "Offset every second strip" is a ColorMunki layout option (printtarg's
        # rig stagger), so it belongs with the layout choices, not in Patches &
        # spacers (Knut). CM-only — visibility is set per-instrument. Always placed
        # (like Show strip indicators) so it shows in Preferences too.
        self.cm_stagger_cb = WrappingCheckBox(tr("Offset every second strip"), self)
        self.cm_stagger_cb.toggled.connect(self._emit)
        self._cm_stagger_tip = TooltipButton(
            tr("Offset every second strip"),
            tr("ColorMunki only: shifts every second strip down by half a patch so "
               "the columns interleave like a brick wall — matching ArgyllCMS "
               "printtarg's measuring-rig layout. Reserves a little space at the "
               "top and bottom for the offset, so the patch count drops slightly. "
               "Leave off for a plain aligned grid."), self)
        lgg.addWidget(self.cm_stagger_cb, 5, 1)
        lgg.addWidget(self._cm_stagger_tip, 5, 2)
        _basic_v.addWidget(lg)

        # ---- Patches & spacers (2-column: label | control) ----
        ps = QGroupBox(tr("Patches && spacers"), self)
        g = QGridLayout(ps)
        self.pscale = scale()
        self.sscale = scale()
        self.spacer_mode = ElidingComboBox(self)
        for k, lbl in (("colored", tr("Coloured")), ("bw", tr("Black & white")),
                       ("none", tr("None"))):
            self.spacer_mode.addItem(lbl, k)
        self.spacer_mode.currentIndexChanged.connect(self._emit)
        self.spacer_mode.currentIndexChanged.connect(self._sync_spacer_swatches)
        self.spacer_width = mm(special_auto=True)
        self.patch_x = small_mm(special_auto=True)
        self.patch_y = small_mm(special_auto=True)
        self.inter_patch = mm()
        self.strip_gap = mm()
        self.sig = mm()
        self._patch_size_row = add_row(g, 0, tr("Patch size (mm):"),
                cell(self.patch_x, QLabel("×", self), self.patch_y),
                tip=TooltipButton(
                    tr("Patch size"),
                    tr("Width × height of each patch in millimetres. Leave at "
                       "“auto” (0) to use the instrument's recommended size "
                       "(scaled by Patch scale). A value below ~6 mm can make the "
                       "chart hard to read."), self))
        self._patch_scale_row = add_row(g, 1, tr("Patch scale:"), self.pscale,
                tip=TooltipButton(
                    tr("Patch scale"),
                    tr("Grows or shrinks every patch (and its spacer) together. "
                       "1.0 is the instrument's standard size. Below 1.0 fits more "
                       "patches per sheet but each is harder for the instrument to "
                       "read reliably — watch the warning if patches get too "
                       "small."), self))
        add_row(g, 2, tr("Spacers:"), self.spacer_mode,
                tip=TooltipButton(
                    tr("Spacers"),
                    tr("The thin separator drawn between patches in a strip so the "
                       "instrument can tell where one patch ends and the next "
                       "begins. “Coloured” picks a high-contrast colour per gap "
                       "(default, most reliable); “Black & white” uses plain "
                       "black/white; “None” removes them — only if your instrument "
                       "doesn't need gaps."), self))
        add_row(g, 3, tr("Spacer size:"), mm_inch(self.spacer_width),
                tip=TooltipButton(
                    tr("Spacer size"),
                    tr("How thick the separator between patches is, in mm (it runs "
                       "along the strip, between consecutive patches). Leave at "
                       "“auto” (0) for the instrument default; increase it only if "
                       "your scanner has trouble finding the patch edges."),
                    self))
        add_row(g, 4, tr("Spacer scale:"), self.sscale,
                tip=TooltipButton(
                    tr("Spacer scale"),
                    tr("Scales only the spacer thickness, leaving patch size "
                       "alone. 1.0 is standard; raise it for fatter gaps without "
                       "making the patches bigger."), self))
        add_row(g, 5, tr("Inter-patch gap:"), mm_inch(self.inter_patch),
                tip=TooltipButton(
                    tr("Inter-patch gap"),
                    tr("Makes the spacer between patches thicker, in mm — extra "
                       "blank separation along the strip. Usually 0; raise it only "
                       "if patches bleed into each other on your printer/paper."),
                    self))
        add_row(g, 6, tr("Strip-indicator gap:"), mm_inch(self.sig),
                tip=TooltipButton(
                    tr("Strip-indicator gap"),
                    tr("How far the strip's letter label sits below the top edge of "
                       "the page, in mm. At 0 the labels hug the minimum text-edge "
                       "distance at the very top; raising it slides them down, "
                       "toward the patches, to fine-tune where the labels print."),
                    self))
        add_row(g, 7, tr("Strip gap (between strips):"), mm_inch(self.strip_gap),
                tip=TooltipButton(
                    tr("Strip gap"),
                    tr("Extra blank space added sideways between neighbouring "
                       "strips (columns of patches), in mm. Usually 0, which packs "
                       "the strips as tightly as the instrument allows to fit the "
                       "most patches per sheet. Raise it if your scanner needs a "
                       "wider gutter between strips, or to spread a sparse chart "
                       "out — each millimetre here means fewer strips fit, so the "
                       "patch count drops."), self))
        # Custom spacer palette (colored mode): the engine draws each gap's
        # spacer from this set instead of the built-in accents.
        self.custom_spacer_cb = WrappingCheckBox(tr("Custom spacer colours"), self)
        self.custom_spacer_cb.toggled.connect(self._on_custom_spacer_toggled)
        self._spacer_swatches = []
        _swrow = QHBoxLayout(); _swrow.setContentsMargins(0, 0, 0, 0); _swrow.setSpacing(4)
        # Five ChromIQ accents plus white + black, so the engine can pick a
        # high-contrast separator against very light or very dark patches too.
        for _hex in ("#ff4573", "#ffb42d", "#56d6a5", "#37bcd6", "#9f82ff",
                     "#ffffff", "#000000"):
            _b = QPushButton(self)
            # NOT objectName "compact_input": that QSS imposes an input min-width
            # which overrides setFixedSize, blowing the 5 swatches up to ~446px
            # and scrolling the panel (feedback_qt_button_sizing).
            _b.setFixedSize(26, 22)
            _b.setProperty("hexcol", _hex)
            self._style_swatch(_b)
            _b.clicked.connect(lambda _c=False, bb=_b: self._pick_spacer_colour(bb))
            self._spacer_swatches.append(_b)
            _swrow.addWidget(_b)
        _swrow.addStretch()
        _sww = QWidget(self); _sww.setLayout(_swrow)
        g.addWidget(self.custom_spacer_cb, 8, 1)
        g.addWidget(TooltipButton(
            tr("Custom spacer colours"),
            tr("By default the engine separates patches with spacers drawn from "
               "the five ChromIQ accent colours plus white and black, "
               "automatically picking the one with the most contrast at each gap "
               "so the instrument can always find the patch edges (white and "
               "black give it a strong choice against very dark or very light "
               "patches). Turn this on to choose your own set instead — click a "
               "swatch to change it. The engine still auto-picks the "
               "highest-contrast one from your set per gap, so keep them varied "
               "(and watch the low-contrast warning)."), self),
            8, 2)
        add_row(g, 9, tr("Spacer colours:"), _sww)
        self.edge_spacers_cb = WrappingCheckBox(tr("Edge spacers (bracket each strip)"), self)
        self.edge_spacers_cb.toggled.connect(self._emit)
        g.addWidget(self.edge_spacers_cb, 10, 1)
        g.addWidget(TooltipButton(
            tr("Edge spacers"),
            tr("Adds a spacer before the first patch and after the last patch of "
               "every strip — the way ArgyllCMS printtarg does. It's optional: "
               "the instrument finds each strip from the white border the layout "
               "already leaves at both ends, so this isn't needed for reliable "
               "reading. It fits in space the layout already reserves, so it "
               "doesn't reduce the patch count. Turn it on if you prefer the "
               "printtarg look or want an extra separator at the strip ends."),
            self), 10, 2)
        _expert_v.addWidget(ps)

        # ---- Randomisation ----
        rg = QGroupBox(tr("Randomisation"), self)
        rgg = QGridLayout(rg)
        self.randomize_cb = WrappingCheckBox(tr("Randomise patch order"), self)
        self.randomize_cb.setChecked(True)
        self.randomize_cb.toggled.connect(self._on_randomize_toggled)
        self.fixed_seed_cb = WrappingCheckBox(tr("Use a fixed seed (reproducible)"), self)
        self.fixed_seed_cb.toggled.connect(self._on_fixed_seed_toggled)
        self.seed_spin = NoScrollSpinBox(self)
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setMinimumWidth(70)        # don't force the row wide for 10 digits
        self.seed_spin.setMaximumWidth(150)
        self.seed_spin.setObjectName("compact_input")
        self.seed_spin.valueChanged.connect(self._emit)
        self.new_seed_btn = QPushButton(tr("New seed"), self)
        self.new_seed_btn.setObjectName("compact_input")
        # Height in the button's OWN stylesheet so the editor's controls QSS
        # (QPushButton { min-height: 26px }) can't inflate it; match the compact
        # browse buttons (#93).
        self.new_seed_btn.setStyleSheet(
            "QPushButton { min-height: 22px; max-height: 22px; "
            "padding-top: 0px; padding-bottom: 0px; }")
        self.new_seed_btn.clicked.connect(self._on_new_seed)
        rgg.addWidget(self.randomize_cb, 0, 1)
        rgg.addWidget(self.fixed_seed_cb, 1, 1)
        rgg.addWidget(QLabel(tr("Seed:"), self), 2, 0, _Qt.AlignmentFlag.AlignRight)
        rgg.addWidget(cell_fill(self.seed_spin, self.new_seed_btn), 2, 1)
        rgg.addWidget(TooltipButton(
            tr("Randomisation"),
            tr("Patches are shuffled across the sheet so a streak of similar "
               "colours can't bias a strip — leave this on. The seed is the "
               "number that drives the shuffle: with a fixed seed the exact same "
               "layout is reproduced every build (handy for re-printing an "
               "identical chart), otherwise a fresh seed is drawn each time. "
               "Press New seed to draw one now; it's saved with the chart so you "
               "can always recreate it."), self), 2, 2)
        _basic_v.addWidget(rg)
        self._on_randomize_toggled(True)

        # ---- Strip indicators (detail widgets) ----
        # The styling controls moved to Preferences → Chart Layout (Knut #93); only
        # the "Show strip indicators" checkbox stays in the panel (in the Layout
        # frame, above Clip border). These widgets are still built so a loaded
        # preset's styling round-trips through from_recipe / to_recipe, but the
        # group is never shown — it's a hidden carrier (see si.setVisible(False)).
        si = QGroupBox(tr("Strip indicators"), self)
        sig2 = QGridLayout(si)
        self.indicator_font = ElidingComboBox(self)
        self._populate_font_combo(self.indicator_font)
        self.indicator_font.currentIndexChanged.connect(self._emit)
        self.indicator_size = small_pt(top_pt=72.0)
        self.indicator_size.setSpecialValueText(tr("auto"))
        self.ind_bold = WrappingCheckBox(tr("Bold"), self)
        self.ind_bold.toggled.connect(self._emit)
        self.ind_italic = WrappingCheckBox(tr("Italic"), self)
        self.ind_italic.toggled.connect(self._emit)
        self._add_font_rows(sig2, 1, tr("Font:"), self.indicator_font,
                            self.indicator_size, self.ind_bold, self.ind_italic,
                            tip=TooltipButton(
                                tr("Indicator font"),
                                tr("Typeface, size and style of the strip letter "
                                   "labels. Bundled fonts are listed first, then "
                                   "every font installed on your system. Size "
                                   "“auto” fits the label to the strip width; Bold "
                                   "/ Italic grey out for fonts that don't offer "
                                   "them."), self))
        self.underline_mode = ElidingComboBox(self)
        for k, lbl in (("off", tr("Off")),
                       ("segments", tr("Coloured (5 segments)")),
                       ("cycle", tr("Coloured (per strip)")),
                       ("black", tr("Black"))):
            self.underline_mode.addItem(lbl, k)
        self.underline_mode.currentIndexChanged.connect(self._on_underline_changed)
        self.underline_thickness = small_mm(top=5.0)
        self.underline_gap = small_mm(top=20.0)
        add_row(sig2, 3, tr("Underline:"), self.underline_mode,
                tip=TooltipButton(
                    tr("Underline"),
                    tr("Draws a thin rule under each strip's letter label. "
                       "Coloured (5 segments) splits the rule into the five "
                       "ChromIQ accent colours side by side under every strip; "
                       "Coloured (per strip) instead cycles one accent colour "
                       "per strip so neighbours read apart; Black is a plain "
                       "rule. Use the thickness and distance to taste."),
                    self))
        add_row(sig2, 4, tr("Line thickness:"), self.underline_thickness,
                tip=TooltipButton(
                    tr("Underline thickness"),
                    tr("How thick the rule under the strip labels is drawn, in "
                       "millimetres. A thicker line is easier to spot at a glance; "
                       "a thinner one is more subtle. Only matters when the "
                       "Underline above is set to something other than Off."),
                    self))
        add_row(sig2, 5, tr("Line distance:"), self.underline_gap,
                tip=TooltipButton(
                    tr("Underline distance"),
                    tr("How far below the strip label the rule sits, in "
                       "millimetres. Increase it to give the label a little "
                       "breathing room above the line."), self))
        self.indicator_rotation = ElidingComboBox(self)
        for _deg in (0, 90, 180, 270):
            self.indicator_rotation.addItem(f"{_deg}°", _deg)
        # Compact, but wide enough for "270°" + the dropdown arrow; the freed
        # space goes to the alignment checkboxes alongside it.
        self.indicator_rotation.setMinimumContentsLength(3)
        self.indicator_rotation.setMaximumWidth(88)
        self.indicator_rotation.currentIndexChanged.connect(self._on_rotation_changed)
        # Reading-axis alignment for side-rotated (90°/270°) multi-letter labels.
        # A mutually-exclusive checkbox set (Left / Centered / Right); only active
        # when the rotation lays the label on its side, greyed out otherwise.
        self.ind_align_left = WrappingCheckBox(tr("Left"), self)
        self.ind_align_center = WrappingCheckBox(tr("Centered"), self)
        self.ind_align_right = WrappingCheckBox(tr("Right"), self)
        self._align_group = QButtonGroup(self)
        self._align_group.setExclusive(True)
        for _cb in (self.ind_align_left, self.ind_align_center, self.ind_align_right):
            self._align_group.addButton(_cb)
            _cb.toggled.connect(self._emit)
        self.ind_align_left.setChecked(True)
        add_row(sig2, 6, tr("Rotation:"),
                cell(self.indicator_rotation, self.ind_align_left,
                     self.ind_align_center, self.ind_align_right),
                tip=TooltipButton(
                    tr("Indicator rotation"),
                    tr("Turns the little letter printed above each strip so it "
                       "reads in the direction you want. 0° is normal, upright "
                       "text. 90° and 270° lay it on its side — useful when the "
                       "strips are very narrow (an upright letter would be wider "
                       "than the strip) or so the labels face you the way you "
                       "actually hold the sheet while measuring. 180° prints it "
                       "upside-down, for when you feed the page in from the other "
                       "end. If you're not sure, leave it at 0°.\n\n"
                       "Left / Centered / Right (only available at 90° / 270°) "
                       "set how a two-letter label lines up: Left keeps the first "
                       "letter on a fixed line nearest the patches so the label "
                       "grows away from them, Right anchors the last letter, and "
                       "Centered splits the difference."), self))
        self.strip_label_offset = NoScrollDoubleSpinBox(self)
        self.strip_label_offset.setRange(-50.0, 50.0)
        self.strip_label_offset.setDecimals(1)
        self.strip_label_offset.setSingleStep(0.5)
        self.strip_label_offset.setSuffix(" mm")
        self.strip_label_offset.setMinimumWidth(96)
        self.strip_label_offset.valueChanged.connect(self._emit)
        add_row(sig2, 7, tr("Label offset:"), self.strip_label_offset,
                tip=TooltipButton(
                    tr("Label offset"),
                    tr("Moves the strip letters up or down without moving the "
                       "patches. By default the labels sit flush just under the "
                       "top margin; a positive value lowers them toward the "
                       "patches, a negative value raises them into the margin. The "
                       "patch area doesn't change, so this doesn't affect how many "
                       "patches fit."), self))
        # Hidden carrier: the styling now lives in Preferences → Chart Layout, but
        # these widgets still back from_recipe / to_recipe so presets round-trip.
        si.setVisible(False)
        self._on_rotation_changed()

        # ---- Page geometry ----
        pg = QGroupBox(tr("Page geometry"), self)
        gg = QGridLayout(pg)
        self.margins = {k: small_mm(top=60.0) for k in ("t", "r", "b", "l")}
        # One row per edge (Top/Right/Bottom/Left), each with a live inch readout
        # — Knut's "list all 4 margins, mm and inch" (#93).
        _mlabels = {"t": tr("Top"), "r": tr("Right"), "b": tr("Bottom"),
                    "l": tr("Left")}
        _mgrid = QGridLayout()
        _mgrid.setContentsMargins(0, 0, 0, 0)
        _mgrid.setVerticalSpacing(4); _mgrid.setHorizontalSpacing(6)
        # "Use instrument margins" — when ticked, the four margins come from
        # Preferences → Instrument Limits for this combo (read-only) (#93, Knut).
        # Shown only when a threshold lookup is wired (set_threshold_lookup).
        self.use_instr_margins = WrappingCheckBox(tr("Use instrument margins"), self)
        self.use_instr_margins.setVisible(False)
        self.use_instr_margins.toggled.connect(self._sync_instr_margins)
        self.use_instr_margins.toggled.connect(self._emit)
        # Its own Page-geometry row so the ⓘ aligns with the panel's tooltip
        # column (gg col 2), not buried inside the margins sub-grid (Knut).
        self._use_instr_tip = TooltipButton(
            tr("Use instrument margins"),
            tr("Fill the four page margins from the per-instrument minimums set "
               "in Preferences → Instrument Limits for this instrument and "
               "paper, and lock them so the patch area always clears your "
               "reading jig. They refill automatically when you change "
               "instrument or paper. Untick to type your own margins."), self)
        self._use_instr_tip.setVisible(False)
        gg.addWidget(self.use_instr_margins, 0, 1)
        gg.addWidget(self._use_instr_tip, 0, 2)
        for _i, _k in enumerate(("t", "r", "b", "l")):
            _dl = QLabel(_mlabels[_k], self); _dl.setMinimumWidth(46)
            _mgrid.addWidget(_dl, _i, 0)
            _mgrid.addWidget(mm_inch(self.margins[_k]), _i, 1)
        _margins_w = QWidget(self); _margins_w.setLayout(_mgrid)
        self.dpi = NoScrollSpinBox(self); self.dpi.setRange(72, 1200)
        self.dpi.setSuffix(" dpi"); self.dpi.valueChanged.connect(self._emit)
        self.nolimit = WrappingCheckBox(tr("Don't cap strip length"), self)
        self.nolimit.toggled.connect(self._emit)
        self.max_strip = mm(special_auto=True, top=2000.0)  # large paper / roll media
        self.offx = small_mm(top=300.0)
        self.offy = small_mm(top=300.0)
        self.strip_pat = QLineEdit(self); self.strip_pat.textChanged.connect(self._emit)
        self.patch_pat = QLineEdit(self); self.patch_pat.textChanged.connect(self._emit)
        # Patch-area alignment — where the block sits within the usable area.
        self.patch_align = ElidingComboBox(self)
        for _key, _lbl in (
            ("top-left", tr("Top-left")), ("top-center", tr("Top-centre")),
            ("top-right", tr("Top-right")),
            ("center-left", tr("Centre-left")), ("center", tr("Centre")),
            ("center-right", tr("Centre-right")),
            ("bottom-left", tr("Bottom-left")), ("bottom-center", tr("Bottom-centre")),
            ("bottom-right", tr("Bottom-right")),
        ):
            self.patch_align.addItem(_lbl, _key)
        self.patch_align.currentIndexChanged.connect(self._emit)
        # Clip-border width (i1/p3, clip mode only) — reserved left zone for the
        # scanner's paper clip; printtarg hard-codes 26 mm, we make it adjustable.
        self.clip_width = small_mm(top=100.0)
        self.clip_width.setMinimum(10.0)
        self.clip_width.valueChanged.connect(self._update_clip_margin_conflict)
        # The left/right margins feed the same clip-side priority check.
        self.margins["l"].valueChanged.connect(self._update_clip_margin_conflict)
        self.margins["r"].valueChanged.connect(self._update_clip_margin_conflict)
        self.clip_width_label = QLabel(tr("Clip border width:"), self)
        self.clip_width_tip = TooltipButton(
            tr("Clip border width"),
            tr("Width of the clip border — the blank band reserved down one edge "
               "of the page for the "
               "clip that holds the sheet against the scanner bed. Make it wider "
               "if your clip covers more of the page; the patches start just "
               "past it. Only applies to the i1Pro / i1Pro 3 in clip-border "
               "mode (printtarg fixes this at 26 mm).\n\n"
               "Works together with the page margin on the same edge (Left or "
               "Right, set by “Side” under Clip-border content): the reserved "
               "clip zone is whichever of the two is larger. If that margin is "
               "wider than this width, the margin wins and this value is "
               "ignored — the box is outlined in red to show it. Raise this "
               "above the margin to make the clip zone wider than the margin."),
            self)
        add_row(gg, 1, tr("Margins (mm):"), _margins_w,
                tip=TooltipButton(
                    tr("Margins"),
                    tr("Blank borders kept clear of patches on each edge — Top, "
                       "Right, Bottom, Left, in mm. Most printers can't print to "
                       "the very edge, so keep a few mm here; the smallest of the "
                       "four also sets the instrument's leader/clip base.\n\n"
                       "When the clip border is on, the margin on the "
                       "clip edge (Left or Right, set by “Side” under Clip-border "
                       "content) shares that edge with the clip-border width: the "
                       "larger of the two is what's reserved. If the clip-border "
                       "width is wider than this margin, it wins and the margin "
                       "box is outlined in red to show it's being overridden."),
                    self))
        gg.addWidget(self.clip_width_label, 2, 0, _Qt.AlignmentFlag.AlignRight)
        self._clip_width_row = mm_inch(self.clip_width)   # spin + inch readout
        gg.addWidget(self._clip_width_row, 2, 1)
        gg.addWidget(self.clip_width_tip, 2, 2)
        add_row(gg, 3, tr("Resolution:"), self.dpi,
                tip=TooltipButton(
                    tr("Resolution"),
                    tr("Pixel density of the printed chart TIFF, in dots per inch. "
                       "300 dpi is a good default; higher makes a larger file with "
                       "no real benefit for solid colour patches."), self))
        self._max_strip_row = add_row(gg, 4, tr("Max strip length:"),
                mm_inch(self.max_strip),
                tip=TooltipButton(
                    tr("Max strip length"),
                    tr("Caps how long a single strip (column of patches) may get, "
                       "in mm. Leave at “auto” to use the instrument's limit (set "
                       "per instrument/paper in Preferences → Instrument Limits). Some "
                       "scanners can't read a strip past a certain length; lower "
                       "this if long strips misread. Only used in “Prioritise patch "
                       "size” — area-first fills the page and warns if a strip is "
                       "longer than the instrument's ruler instead."), self))
        self._offset_row = add_row(gg, 5, tr("Chart offset (mm):"),
                cell(self.offx, QLabel("×", self), self.offy),
                tip=TooltipButton(
                    tr("Chart offset"),
                    tr("Shifts the whole patch block right (X) and down (Y) on the "
                       "sheet, in mm. Usually 0 — use it to nudge the layout away "
                       "from a printer's unprintable area or to line up with a "
                       "pre-printed sheet. Only used in “Prioritise patch size”; "
                       "area-first places the block by the margins."), self))
        add_row(gg, 6, tr("Strip pattern:"), self.strip_pat,
                tip=TooltipButton(
                    tr("Strip pattern"),
                    tr("How each strip (column of patches) is labelled — the first "
                       "part of a patch's location, e.g. the “A” in A12. ChromIQ "
                       "reads this the way ArgyllCMS's printtarg does; in practice "
                       "it decides whether strips are labelled with LETTERS or "
                       "NUMBERS.\n\n"
                       "Valid examples:\n"
                       "• A-Z, A-Z — the default: letters A, B, C … Z, then AA, "
                       "AB, AC … once past 26 strips (like spreadsheet columns).\n"
                       "• A-Z — plain letters A, B, C … (same result while a chart "
                       "has 26 strips or fewer).\n"
                       "• 1-999 — numbers 1, 2, 3 …\n"
                       "• 0-9 — also numbers 1, 2, 3 …\n\n"
                       "Rule: any pattern that contains “A-Z” labels with letters; "
                       "anything else counts in plain numbers (no zero-padding). "
                       "This works together with the Patch pattern below — the two "
                       "combine into each location label, strip then patch (e.g. "
                       "strip “A” + patch “12” = A12). Leave the default unless "
                       "you're matching a specific reading-sheet scheme."), self))
        add_row(gg, 7, tr("Patch pattern:"), self.patch_pat,
                tip=TooltipButton(
                    tr("Patch pattern"),
                    tr("How patches within a strip are labelled — the second part "
                       "of a location, e.g. the “12” in A12. The patch label is "
                       "joined to the strip label to form each patch's full "
                       "location (strip then patch, e.g. A12).\n\n"
                       "The one rule that always applies: if the pattern contains "
                       "“A-Z” you get LETTERS, otherwise you get NUMBERS.\n\n"
                       "Common patterns:\n"
                       "• 0-9,@-9,@-9;1-999 — the default: numbers 1, 2, 3 …\n"
                       "• 1-999 — numbers 1, 2, 3 … (simpler, same result).\n"
                       "• A-Z, A-Z — letters A, B, C … Z, AA, AB ….\n"
                       "• A-Z — plain letters A, B, C ….\n\n"
                       "About the “@” and zeros (ArgyllCMS notation, used by the "
                       "classic printtarg engine):\n"
                       "• “@” means “this digit may be left blank”. It is what "
                       "stops the default from writing leading zeros — you get "
                       "1, 2, … 9, 10 rather than 001, 002 …\n"
                       "• To start counting at 0 instead of 1, include 0 in the "
                       "range, e.g. 0-999 → 0, 1, 2 ….\n"
                       "• To keep every number the same width WITH leading zeros "
                       "(01, 02, … 09, 10), use a fixed-width digit range such as "
                       "00-99 (two digits) or 000-999 (three).\n\n"
                       "Note: ChromIQ's own layout engine keeps patch numbers "
                       "simple (1, 2, 3 …) whatever the digit details; the “@” "
                       "and leading-zero options above take effect when a chart "
                       "is built with the classic printtarg engine. Leave the "
                       "default unless you're matching a specific scheme."),
                    self))
        self._patch_align_row = add_row(gg, 8, tr("Patch area alignment:"),
                self.patch_align,
                tip=TooltipButton(
                    tr("Patch area alignment"),
                    tr("Where the whole patch block sits within the page once the "
                       "margins are kept clear. The patches rarely fill the usable "
                       "area exactly, so this decides where the leftover white "
                       "space goes.\n\n"
                       "“Top-left” pins the block to the top-left corner (the "
                       "leftover sits at the right and bottom); “Centre” puts the "
                       "spare space evenly around it; “Bottom-right” pins it to the "
                       "opposite corner, and so on. It only moves the block — the "
                       "patch count and size don't change. Margins / thresholds "
                       "are still respected."), self))
        gg.addWidget(self.nolimit, 9, 1)
        self._nolimit_tip = TooltipButton(
            tr("Don't cap strip length"),
            tr("Removes the strip-length limit entirely (printtarg -P), letting a "
               "strip run the full usable height. Only enable if your instrument "
               "can read an unlimited-length strip; otherwise leave it off. Only "
               "used in “Prioritise patch size” — area-first already fills the "
               "page, so it's hidden there."),
            self)
        gg.addWidget(self._nolimit_tip, 9, 2)
        # Page geometry sits directly UNDER the Layout frame (Knut): the two are
        # the core layout block, so they read together, with patches/spacers and
        # the rest below. pg is built after several other groups, so insert it just
        # after Layout rather than appending at the end.
        _lg_idx = _basic_v.indexOf(lg)
        if _lg_idx >= 0:
            _basic_v.insertWidget(_lg_idx + 1, pg)
        else:
            _basic_v.addWidget(pg)
        self._update_clip_visibility()

        # ---- Output ----
        og = QGroupBox(tr("Output"), self)
        ogg = QGridLayout(og)
        self.bit_depth = ElidingComboBox(self)
        self.bit_depth.addItem(tr("8-bit"), 8)
        self.bit_depth.addItem(tr("16-bit"), 16)
        self.bit_depth.currentIndexChanged.connect(self._emit)
        self.compression = ElidingComboBox(self)
        for k, lbl in (("lzw", "LZW"), ("zlib", "Zlib"), ("none", tr("None"))):
            self.compression.addItem(lbl, k)
        self.compression.currentIndexChanged.connect(self._emit)
        add_row(ogg, 0, tr("Bit depth:"), self.bit_depth,
                tip=TooltipButton(
                    tr("Bit depth"),
                    tr("Colour precision of the chart TIFF. 8-bit is standard and "
                       "right for almost everyone. 16-bit doubles the file size "
                       "and only helps if your whole print path is genuinely "
                       "16-bit — otherwise it makes no visible difference."),
                    self))
        add_row(ogg, 1, tr("Compression:"), self.compression,
                tip=TooltipButton(
                    tr("Compression"),
                    tr("How the chart TIFF is compressed. LZW (default) and Zlib "
                       "are lossless and shrink the file; “None” writes it "
                       "uncompressed (largest, most compatible). All keep the "
                       "exact colours."), self))
        self.export_pdf = WrappingCheckBox(tr("Also export a PDF"), self)
        self.export_pdf.toggled.connect(self._emit)
        add_row(ogg, 2, "", self.export_pdf,
                tip=TooltipButton(
                    tr("Also export a PDF"),
                    tr("Saves a press-ready PDF of the chart next to the usual "
                       "TIFF — the TIFF is still made, this just adds a PDF copy.\n\n"
                       "When it helps:\n"
                       "• Your print shop or RIP prefers PDF, or asks for one.\n"
                       "• You want a file that prints at the exact paper size, with "
                       "no print dialog quietly scaling it down.\n"
                       "• Multi-ink charts (CMYK and CMYK + extra inks): the PDF "
                       "carries each ink as its own named channel, so a RIP knows "
                       "exactly which ink is which.\n\n"
                       "The PDF is drawn as true vector — the patches are exact "
                       "device colours and the labels stay crisp at any zoom — and "
                       "it uses the same fonts as the chart. All pages are in one "
                       "file.\n\n"
                       "One rule matters more than the rest: nothing between "
                       "this file and the paper may convert the colours. That is "
                       "not the same advice as for the TIFF, and the reason is in "
                       "the PDF format rather than in any one system. Both files "
                       "hold raw device values with no colour profile attached, "
                       "which is what a chart needs — but where a TIFF is a "
                       "picture whose numbers get passed along, a PDF lets "
                       "whatever opens it decide that those numbers meant some "
                       "particular colour space, and convert them. Measured on "
                       "macOS, a pure red patch of 255,0,0 came back as "
                       "234,51,35. On Linux, the PDF interpreter behind most "
                       "print queues assigns a default colour profile unless it "
                       "is told not to. On Windows it depends entirely on the "
                       "application you print from. How far the colours move "
                       "depends on the machine and the program, so the same file "
                       "can look fine on one and be badly wrong on another.\n\n"
                       "None of which means a chart PDF cannot be printed "
                       "properly — it can, and there are three ways to be sure "
                       "of it:\n"
                       "• Send it straight to the print queue, which is what "
                       "ChromIQ does with its own charts.\n"
                       "• Give it to a RIP with colour management switched off — "
                       "what this export is really for.\n"
                       "• Print from an application with an explicit setting for "
                       "it, such as “Same as source (no colour management)”.\n\n"
                       "What you cannot do is assume it. The case that goes wrong "
                       "is an ordinary viewer that simply draws the page and "
                       "offers no such setting, which is also the most common way "
                       "people open a PDF.\n\n"
                       "So: if you have a RIP, a print queue or an application "
                       "with that setting, the PDF is fine. If you are not "
                       "certain, print the TIFF sheets instead — they behave the "
                       "same way everywhere. A chart printed through a colour "
                       "conversion measures the conversion rather than your "
                       "printer, and nothing afterwards can tell that it "
                       "happened.\n\n"
                       "How to use it: tick this, build the chart as usual, and "
                       "you'll find a .pdf beside the .tif in the chart folder.\n\n"
                       "Leave it off if you only print through ChromIQ or just need "
                       "the TIFF.\n\n"
                       "Default: off."), self))
        _expert_v.addWidget(og)

        # ---- Ruler helper markers (#152, moved here by #158) ----
        # These dashes are PRINTED on the sheet, and Generate Chart is what puts
        # them there — so they belong beside the rest of the layout, not under
        # the preview where they used to live. Knut, #158: *"this checkmark and
        # the spin boxes would actually naturally fit as part of the Create
        # Chart parameters in the left panel, because one has to click the
        # Generate Chart button for markers to become visible on the tif files
        # for print."* The live preview still draws them as they are nudged, so
        # nothing is lost by the move.
        hm = self._helper_markers_grp = QGroupBox(
            tr("Ruler helper markers"), self)
        hmg = QGridLayout(hm)
        # Short label, spanning both columns: the long version sat alone in the
        # control column and made this the widest group in Expert Options
        # (535 px against 472 for the next one), which pushed the whole right
        # side into horizontal scrolling (Basti, on screen). The group title
        # already says these are ruler helper markers.
        self.helper_markers_cb = WrappingCheckBox(tr("Print helper markers"), self)
        self.helper_markers_cb.toggled.connect(self._emit)
        self.helper_marker_edge = small_mm(top=60.0)
        self.helper_marker_len = small_mm(top=60.0)
        self.helper_marker_per_patch = NoScrollSpinBox(self)
        self.helper_marker_per_patch.setRange(2, 12)
        # A two-digit count, so it takes the narrow width the panel's other
        # whole-number boxes use rather than the wider millimetre ones.
        self.helper_marker_per_patch.setMinimumWidth(64)
        self.helper_marker_per_patch.setMaximumWidth(70)
        self.helper_marker_per_patch.valueChanged.connect(self._emit)
        from PyQt6.QtCore import Qt as _QtAlign
        # Column 0 only, NOT spanning: a widget spanning 0-1 makes Qt charge its
        # whole width to the spanned columns, which inflated column 0 and pushed
        # the three spin boxes far to the right of their labels (x=371 against
        # x=189 in "Patches & spacers"). In one column it lines up with the
        # labels and the boxes sit where they do in every other group.
        hmg.addWidget(self.helper_markers_cb, 0, 0,
                      _QtAlign.AlignmentFlag.AlignLeft)
        hmg.addWidget(TooltipButton(
            tr("Ruler helper markers"),
            tr("Prints short dashes along all four edges of the sheet, so you "
               "can lay a ruler against the paper and line your instrument up "
               "with a row of patches.\n\n"
               "What you get: a dash at the centre of every patch and one "
               "between each pair, evenly spaced the whole way along. They "
               "follow your patch spacing automatically, so they stay correct "
               "whatever else you change.\n\n"
               "You need this if you read a chart with a hand-held instrument "
               "along a ruler. Leave it off for a chart you read without one — "
               "the dashes cost nothing but ink, and some people prefer a clean "
               "sheet.\n\n"
               "Press Generate Chart after changing this: the dashes are "
               "printed onto the sheet, and the preview only shows you where "
               "they will land. If \u201cAuto-update preview when a layout setting "
               "changes\u201d is ticked, the sheet is rebuilt for you and there is "
               "nothing more to do.\n\n"
               "Default: off."), self), 0, 2)
        self._hm_rows = []
        self._hm_rows.append(add_row(hmg, 1, tr("Distance from page edge (mm):"),
                cell(self.helper_marker_edge), align_left=True,
                tip=TooltipButton(
                    tr("Distance from page edge"),
                    tr("How far in from the edge of the paper each dash starts, "
                       "in millimetres.\n\n"
                       "Small values (1–2 mm) keep the dashes out of the way of "
                       "everything else on the sheet. Larger values move them "
                       "inward, which helps if your printer cannot print close "
                       "to the paper edge — many printers leave a few "
                       "millimetres unprinted.\n\n"
                       "If a dash would land where the strip labels or the "
                       "clip-border text sit, they may overlap: move whichever "
                       "one is in the way.\n\n"
                       "Default: 2.0 mm."), self)))
        self._hm_rows.append(add_row(hmg, 2, tr("Marker length (mm):"), cell(self.helper_marker_len),
                align_left=True, tip=TooltipButton(
                    tr("Marker length"),
                    tr("How long each dash is, measured inward from where it "
                       "starts.\n\n"
                       "Longer dashes are easier to see and to line a ruler "
                       "against; shorter ones stay further from the patches. "
                       "2–4 mm suits most charts.\n\n"
                       "The four sets of dashes never cross in the corners — a "
                       "dash is left out where it would run into the dashes "
                       "coming from the edge next to it.\n\n"
                       "Default: 2.0 mm."), self)))
        self._hm_rows.append(add_row(hmg, 3, tr("Markers per patch:"),
                cell(self.helper_marker_per_patch),
                align_left=True, tip=TooltipButton(
                    tr("Markers per patch"),
                    tr("How many dashes fall along a single patch, counting the "
                       "one at each end.\n\n"
                       "3 gives you a dash where two patches meet, one in the "
                       "middle of the patch, and one where the next patch "
                       "begins — the usual choice. Raise it if you want finer "
                       "steps to line your ruler up against: 5 puts three "
                       "dashes inside each patch instead of one. Lower it to 2 "
                       "for a single dash where patches meet and nothing in "
                       "between.\n\n"
                       "Every gap stays exactly the same size whichever number "
                       "you pick. With an even number there is no dash at the "
                       "centre of the patch — the middle one is replaced by two "
                       "sitting either side of it.\n\n"
                       "Default: 3."), self)))
        # WHICH EDGES CARRY THE DASHES (#164, Knut): *"for some layouts, it
        # might be an idea to have checkbox choice … Then a user can choose to
        # turn off the ones not needed, especially as the strip markers are the
        # most useful for measuring."* Named after the EDGE the dashes sit on,
        # with his own axis wording in brackets, because the top/bottom dashes
        # are drawn as vertical strokes and the side ones as horizontal — the
        # opposite of what the axis word suggests.
        # STACKED, NOT SIDE BY SIDE. Two checkboxes on one line made this the
        # widest group in Expert Options — 547 px against 472 for the next one —
        # and that pushes the whole right-hand column into horizontal scrolling
        # and clips the second label to "Sides (vertica". The panel has been
        # here before: the marker tick box's own label was shortened for exactly
        # this reason. One under the other costs a line and keeps Knut's wording.
        # ONE GRID ROW EACH, not a nested layout.
        #
        # Two tick boxes side by side in the control column made this group
        # 537 px wide — the widest in Expert Options, which pushes the whole
        # right-hand column into horizontal scrolling and clips the second
        # label. Stacking them in a nested QVBoxLayout fixed the width and
        # broke the look instead: inside the real window that layout came out
        # 43 px tall for two 22 px boxes, so the second overlapped the first and
        # the two tick indicators merged into one tall block. The grid this
        # group already uses spaces its own rows correctly, so the boxes go
        # straight into it — a row each, indented under their label.
        self.helper_markers_top_bottom = WrappingCheckBox(
            tr("Top/bottom (horizontal)"), self)
        self.helper_markers_sides = WrappingCheckBox(tr("Sides (vertical)"), self)
        for _cb in (self.helper_markers_top_bottom, self.helper_markers_sides):
            _cb.setChecked(True)
            # A QSS-sized tick indicator (16 px) is not in a QCheckBox's own
            # sizeHint, so the layout budgeted 14 px for a box that draws 18 and
            # the second one overlapped the first by a pixel — two indicators
            # merged into one tall block on screen. Ask for the height the box
            # actually needs. (Same class of trap as the padding note in
            # ui/styles.py: QSS geometry lands after the hint is taken.)
            _cb.setObjectName("param_label")
            _cb.setStyleSheet("margin-left: 16px;")
            _cb.toggled.connect(self._emit)
            _cb.toggled.connect(self._update_helper_marker_edge_warning)
        # UNDER THE LABEL, NOT BESIDE IT: a grid shares its column widths across
        # every row, so a tick box in the CONTROL column widens that column for
        # the three spin-box rows above as well. Spanning both columns on lines
        # of their own, the boxes use width the label column already has.
        self._hm_rows.append(add_row(hmg, 4, tr("Show markers for:"), QWidget(self),
                align_left=True, tip=TooltipButton(
                    tr("Show markers for"),
                    tr("Which edges of the sheet get the dashes.\n\n"
                       "Tick “Sides” for the dashes down the left and right "
                       "edges — these are the ones that line up with the rows "
                       "of patches, so they are what you want when you read a "
                       "strip with a hand-held instrument. Tick “Top/bottom” "
                       "for the dashes along the top and bottom edges, which "
                       "line up with the strips across the page.\n\n"
                       "Untick the set you don't need and it simply isn't "
                       "printed — less ink on the sheet, and nothing in the way "
                       "of your margins or the clip-border text. The set you "
                       "keep then reaches into the corners as well, because "
                       "there is no longer another set there to bump into.\n\n"
                       "With both unticked no dashes are printed at all — the "
                       "same as turning the markers off. ChromIQ says so under "
                       "the boxes if you leave it that way.\n\n"
                       "Default: both ticked."), self)))
        hmg.addWidget(self.helper_markers_top_bottom, 5, 0, 1, 2)
        hmg.addWidget(self.helper_markers_sides, 6, 0, 1, 2)
        self._hm_rows[-1] = tuple(self._hm_rows[-1]) + (
            self.helper_markers_top_bottom, self.helper_markers_sides)
        # The three distances only mean something once the markers are on, so
        # they grey with the tick box (Basti). The labels take the app's
        # dimmed-caption object name: this theme's Disabled palette paints a
        # plain QLabel in exactly the same colour as a live one, so without it
        # they would be disabled without LOOKING disabled — the same trap the
        # controls hit in their old home, and both themes already style
        # #param_label:disabled (ui/styles.py, ui/light_styles.py).
        for _row in self._hm_rows:
            for _w in _row:
                if isinstance(_w, QLabel):
                    _w.setObjectName("param_label")
        # Says so on the panel when the two tick boxes cancel the markers out.
        self.helper_markers_edge_warning = QLabel("", self)
        self.helper_markers_edge_warning.setWordWrap(True)
        self.helper_markers_edge_warning.setObjectName("param_label")
        self.helper_markers_edge_warning.setVisible(False)
        hmg.addWidget(self.helper_markers_edge_warning, 7, 0, 1, 2)
        self.helper_markers_cb.toggled.connect(self._update_helper_marker_rows)
        self.helper_markers_cb.toggled.connect(
            self._update_helper_marker_edge_warning)
        self._update_helper_marker_rows()
        self._update_helper_marker_edge_warning()
        _expert_v.addWidget(hm)

        # ---- Sheet text ----
        st = QGroupBox(tr("Sheet text"), self)
        stg = QGridLayout(st)
        self.chart_text = QLineEdit(self)
        self.chart_text.setPlaceholderText(tr("e.g. {project} — {date}"))
        self.chart_text.textChanged.connect(self._emit)
        self.insert_token_btn = self._make_insert_button(self.chart_text)
        self.text_preview = QLabel(self)
        self.text_preview.setWordWrap(True)
        self.text_preview.setStyleSheet("color: palette(mid);")
        self.chart_text_font = ElidingComboBox(self)
        self._populate_font_combo(self.chart_text_font)
        self.chart_text_font.currentIndexChanged.connect(self._emit)
        self.chart_text_size = small_pt(top_pt=72.0)
        self.chart_text_size.setSpecialValueText(tr("auto"))
        self.ct_bold = WrappingCheckBox(tr("Bold"), self)
        self.ct_bold.toggled.connect(self._emit)
        self.ct_italic = WrappingCheckBox(tr("Italic"), self)
        self.ct_italic.toggled.connect(self._emit)
        self.stamp_command = WrappingCheckBox(tr("Stamp layout summary on the sheet"), self)
        self.stamp_command.toggled.connect(self._emit)
        add_row(stg, 0, tr("Custom text:"),
                cell_fill(self.chart_text, self.insert_token_btn),
                tip=TooltipButton(
                    tr("Sheet text"),
                    tr("Optional text printed in the bottom margin of every sheet. "
                       "Use Insert ▾ to drop in a placeholder — it's replaced with "
                       "a human-readable value when the chart is built: {project} "
                       "(profile name), {page} (“page 1/3”), {date}, {paper} (e.g. "
                       "“A4 landscape”), {instrument} (e.g. “i1Pro3+”), "
                       "{patchcount}, {pages}, {seed}, {dpi}. The Preview line "
                       "shows how it will read."), self))
        add_row(stg, 1, tr("Preview:"), self.text_preview)
        self._add_font_rows(stg, 2, tr("Font:"), self.chart_text_font,
                            self.chart_text_size, self.ct_bold, self.ct_italic,
                            tip=TooltipButton(
                                tr("Sheet-text font"),
                                tr("Typeface, size and style of the custom sheet "
                                   "text in the bottom margin. Size “auto” uses a "
                                   "sensible default; Bold / Italic grey out for "
                                   "fonts that don't offer them."), self))
        stg.addWidget(self.stamp_command, 4, 1)
        stg.addWidget(TooltipButton(
            tr("Stamp layout summary"),
            tr("Prints a one-line summary of how the chart was made (engine, "
               "instrument, paper, dpi, patch count, seed) in the bottom margin. "
               "Handy for re-creating an identical chart later from the printed "
               "sheet alone."), self), 4, 2)
        # Min distance from the paper edge to text, one per text-bearing side
        # (Knut #93): top = strip labels, bottom = sheet text, clip = notes/clip
        # band. Independent of the margins; text overflows toward this line (and a
        # violation is flagged) if its margin is too small.
        self.text_edge_top = small_mm(top=30.0); self.text_edge_top.setValue(4.0)
        self.text_edge = small_mm(top=30.0); self.text_edge.setValue(4.0)
        self.text_edge_clip = small_mm(top=30.0); self.text_edge_clip.setValue(4.0)
        _te = QHBoxLayout(); _te.setContentsMargins(0, 0, 0, 0); _te.setSpacing(4)
        for _lbl, _sp in ((tr("T"), self.text_edge_top), (tr("B"), self.text_edge),
                          (tr("Clip"), self.text_edge_clip)):
            _sp.setMaximumWidth(50)
            _te.addWidget(QLabel(_lbl, self)); _te.addWidget(_sp)
        _te.addStretch()
        _te_w = QWidget(self); _te_w.setLayout(_te)
        # Label on its own row, the three compact spins below it, so the wide
        # spin row doesn't force the whole panel wider. The spin row is indented to
        # the field column (1) so it lines up with the boxes above it (Knut #93).
        #
        # SPANNING ALL THREE COLUMNS, WITH THE INDENT DRAWN INSIDE IT. Placed in
        # columns 1-2 the row's whole width was charged to those two columns, on
        # top of whatever column 0 needed — 361 px plus a 105 px label column
        # made "Sheet text" the widest group in the panel in Norwegian, Swedish,
        # Italian and Portuguese, and the thing still pushing them sideways once
        # the combos and the spin widths were fixed. Spanning 0-2 lets Qt charge
        # it to the whole grid instead, and the left margin below keeps Knut's
        # indent on screen.
        stg.addWidget(QLabel(tr("Text distance from edge (mm):"), self), 5, 0, 1, 2)
        _te.setContentsMargins(16, 0, 0, 0)
        stg.addWidget(_te_w, 6, 0, 1, 3)
        stg.addWidget(TooltipButton(
            tr("Text distance from edge"),
            tr("The minimum distance from the paper edge to the text on each side "
               "that can carry text: Top = strip labels, Bottom = sheet text, "
               "Clip = the clip-border / notes band. Increase a value if your "
               "printer clips text near that edge. These are independent of the "
               "page margins; if a margin is too small for its text, the text "
               "overflows toward this line and a margin warning is shown.\n\n"
               "If you also print the ruler helper markers (the short dashes "
               "along the page edges, switched on under the preview), a dash "
               "can land on top of this text. Nothing is hidden or moved "
               "automatically, because the dashes have to keep step with the "
               "patches to be useful. Move whichever one is in the way: give "
               "the text more room here, or shift the dashes with their own "
               "“Distance from page edge”."), self),
            5, 2)
        _expert_v.addWidget(st)
        self._update_text_preview()

        # ---- Clip-border content (i1/p3 clip mode) ----
        self._clip_content_grp = QGroupBox(tr("Clip-border content"), self)
        ccg = QGridLayout(self._clip_content_grp)
        self.clip_content_mode = ElidingComboBox(self)
        for k, lbl in (("off", tr("Off")), ("text", tr("Custom text")),
                       ("example", tr("Custom text example")),
                       ("branding", tr("ChromIQ branding")),
                       ("notes", tr("Notes box")), ("image", tr("Imported image"))):
            self.clip_content_mode.addItem(lbl, k)
        self.clip_content_mode.currentIndexChanged.connect(self._on_clip_content_changed)
        self.clip_side = ElidingComboBox(self)
        self.clip_side.addItem(tr("Left"), "left")
        self.clip_side.addItem(tr("Right"), "right")
        self.clip_side.currentIndexChanged.connect(self._update_clip_margin_conflict)
        self.clip_side.currentIndexChanged.connect(self._emit)
        # Flip the clip content 180° from its per-side default reading direction
        # (a right-side clip is auto-turned upside-down to read from the far side
        # of the sheet; this lets the user turn any clip the other way). (Knut)
        self.clip_flip_180 = WrappingCheckBox(tr("Flip 180°"), self)
        self.clip_flip_180.toggled.connect(self._emit)
        from PyQt6.QtWidgets import QPlainTextEdit
        # Multi-line so a record like the "Example custom table" template (many
        # lines) is comfortable to view and edit; ~4 lines tall with a scrollbar
        # to reach the rest (Knut).
        self.clip_text = QPlainTextEdit(self)
        self.clip_text.setPlaceholderText(tr("e.g. {project} — {date}"))
        _clip_fm = self.clip_text.fontMetrics()
        self.clip_text.setFixedHeight(int(_clip_fm.lineSpacing() * 4 + 12))
        self.clip_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.clip_text.setVerticalScrollBarPolicy(
            _Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.clip_text.textChanged.connect(self._emit)
        self.clip_insert_btn = self._make_insert_button(self.clip_text,
                                                        multiline=True)
        self.clip_text_font = ElidingComboBox(self)
        self._populate_font_combo(self.clip_text_font)
        self.clip_text_font.currentIndexChanged.connect(self._emit)
        # Manual text size for the clip strip (auto = fit to the strip width);
        # so the record text doesn't dominate the sheet (#125, Knut).
        self.clip_text_size = small_pt(top_pt=72.0)
        self.clip_text_size.setSpecialValueText(tr("auto"))
        self.clip_text_size.valueChanged.connect(self._emit)
        self.clip_image_path = QLineEdit(self)
        self.clip_image_path.setPlaceholderText(tr("no image selected"))
        self.clip_image_path.textChanged.connect(self._emit)
        self.clip_image_browse = self._compact_browse(tr("Browse for an image"))
        self.clip_image_browse.clicked.connect(self._browse_clip_image)
        from PyQt6.QtWidgets import QSizePolicy
        self.clip_dims_label = QLabel("", self)
        self.clip_dims_label.setStyleSheet("color: palette(mid);")
        self.clip_dims_label.setWordWrap(True)
        self.clip_preview = QLabel(self)
        # Tall enough to show a multi-line record at a glance (Knut).
        self.clip_preview.setMinimumHeight(90)
        self.clip_preview.setAlignment(_Qt.AlignmentFlag.AlignCenter)
        self.clip_preview.setStyleSheet("border: 1px solid palette(mid);")
        # Don't let the preview pixmap or dims text dictate the panel's min width
        # (it lives in a horizontal-scroll-free column).
        self.clip_preview.setSizePolicy(QSizePolicy.Policy.Ignored,
                                        QSizePolicy.Policy.Fixed)
        self.clip_dims_label.setSizePolicy(QSizePolicy.Policy.Ignored,
                                           QSizePolicy.Policy.Preferred)
        self.clip_export_btn = QPushButton(tr("Export template (PNG + PDF)…"), self)
        self.clip_export_btn.setObjectName("compact_input")
        self.clip_export_btn.clicked.connect(self._export_clip_template)
        add_row(ccg, 0, tr("Content:"), self.clip_content_mode,
                tip=TooltipButton(
                    tr("Clip-border content"),
                    tr("Available only when Clip border is turned On (in the "
                       "Layout section above) — with it Off there is no clip "
                       "border to fill, so these options do nothing.\n\n"
                       "Fills the blank band down the clip edge of the page that "
                       "the scanner clip reserves. Custom text accepts the same "
                       "{project}/{date}/… tokens as the sheet text; Notes box "
                       "prints a ready-made record — chart facts filled in "
                       "automatically (patches, instrument, paper, page, profile "
                       "name, date) plus labelled lines to hand-write the "
                       "printer, ink set, paper and media settings; ChromIQ "
                       "branding stamps the wordmark; Imported image places a "
                       "logo. Export template gives you an exact-size PNG and PDF "
                       "to design a graphic in another tool."), self))
        _clip_side_w = QWidget(self)
        _cs = QHBoxLayout(_clip_side_w)
        _cs.setContentsMargins(0, 0, 0, 0); _cs.setSpacing(8)
        _cs.addWidget(self.clip_side, 1)
        _cs.addWidget(self.clip_flip_180)
        _cs.addWidget(TooltipButton(
            tr("Flip writing direction"),
            tr("Turns the clip-border content 180° from the way it normally "
               "reads. A clip border on the Right side is printed upside-down by "
               "default, so it reads the right way up when you look at the sheet "
               "from that side. If you'd rather it read the same direction as the "
               "info line stamped along the bottom of the sheet, tick this. It "
               "works on either side, so you can also flip a Left-side clip."),
            self))
        add_row(ccg, 1, tr("Side:"), _clip_side_w,
                tip=TooltipButton(
                    tr("Clip border side"),
                    tr("Which edge of the page the clip border sits "
                       "on — Left or Right. Choose whichever matches how you feed "
                       "the chart into your instrument's ruler. The patches fill "
                       "the rest of the page; the patch count is the same either "
                       "way.\n\n"
                       "This also decides which page margin the clip-border width "
                       "shares an edge with: Left → the Left margin, Right → the "
                       "Right margin. On that edge the wider of the two (margin "
                       "or clip-border width) is what gets reserved; the smaller "
                       "one is outlined in red to show it's overridden."), self))
        self._clip_text_row = add_row(
                ccg, 2, tr("Text:"), cell_fill(self.clip_text, self.clip_insert_btn),
                tip=TooltipButton(
                    tr("Clip-border text"),
                    tr("The text printed up the clip-border strip (the tall band "
                       "along one edge that holds the instrument's calibration "
                       "area). Type freely, and use Insert ▾ to drop in either a "
                       "placeholder or a blank line to write on:\n\n"
                       "Placeholders are replaced with real values when the chart "
                       "is built:\n"
                       "  • {project} — your printer-profile name\n"
                       "  • {page} — this page, e.g. “page 1/3”\n"
                       "  • {date} — the build date\n"
                       "  • {paper} — paper size and orientation\n"
                       "  • {instrument} — the instrument name\n"
                       "  • {patchcount} — the number of patches (with the word "
                       "“patches”)\n"
                       "  • {pages} — the total number of pages\n"
                       "  • {seed} — the shuffle seed (shown as “seed 1234”), which "
                       "lets you reproduce the exact patch order later\n"
                       "  • {dpi} — the resolution (with “dpi”)\n\n"
                       "Blank lines to write on — “Underline — long/short” inserts "
                       "a run of underscores (10 or 5). Put several in a row for a "
                       "longer line; they join with no gap unless you type a space "
                       "between them. Handy for a hand-written date or paper name.\n\n"
                       "The font and size below apply to this text."),
                    self))
        _clip_font_w = QWidget(self)
        _cf = QHBoxLayout(_clip_font_w)
        _cf.setContentsMargins(0, 0, 0, 0); _cf.setSpacing(8)
        _cf.addWidget(self.clip_text_font, 1)
        # A LABEL THAT CAN WRAP CAN ALSO SHRINK — same reason as `add_row`.
        # Unwrapped, "Tamanho (pt):" is a 90 px floor in the middle of the
        # widest row of the widest group in Portuguese. It only ever takes a
        # second line if the row is genuinely too narrow for one.
        _cf_size_lbl = QLabel(tr("Size (pt):"), self)
        _cf_size_lbl.setWordWrap(True)
        _cf.addWidget(_cf_size_lbl)
        _cf.addWidget(self.clip_text_size)
        add_row(ccg, 3, tr("Font:"), _clip_font_w,
                tip=TooltipButton(
                    tr("Clip text font & size"),
                    tr("Typeface and size for the clip-strip text. Size is in mm; "
                       "leave it at “auto” to let ChromIQ fit the text to the "
                       "strip width. Set a smaller size when the auto text looks "
                       "too large and you want to keep the strip narrow / maximise "
                       "patch space. Applies to the custom-text clip content; the "
                       "Notes-box record has its own auto layout."), self))
        self._clip_image_row = add_row(
            ccg, 4, tr("Image:"),
            cell_fill(self.clip_image_path, self.clip_image_browse))
        # Image transform (rotate / scale / move) — applies to the imported image.
        self.clip_image_rotation = NoScrollSpinBox(self)
        self.clip_image_rotation.setRange(0, 359); self.clip_image_rotation.setSuffix("°")
        self.clip_image_scale = NoScrollDoubleSpinBox(self)
        # Very generous max (up to 50000%) so a small logo can be blown right up;
        # typing a value above the max would otherwise snap back (Knut). Step 10.
        self.clip_image_scale.setRange(1.0, 50000.0); self.clip_image_scale.setDecimals(0)
        self.clip_image_scale.setSingleStep(10.0)
        self.clip_image_scale.setSuffix(" %"); self.clip_image_scale.setValue(100.0)
        self.clip_image_offx = NoScrollDoubleSpinBox(self)
        self.clip_image_offy = NoScrollDoubleSpinBox(self)
        for _o in (self.clip_image_offx, self.clip_image_offy):
            _o.setRange(-300.0, 300.0); _o.setDecimals(1); _o.setSingleStep(0.5)
            # The unit lives on the field, so the row label can stay short: this
            # group sets the width of the whole Expert Options column, and
            # "Content move (mm):" is 11 px wider than the "Image move (mm):" it
            # replaced (#164).
            _o.setSuffix(" mm")
        def _xform_row(*pairs):
            row = QHBoxLayout(); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(6)
            for _l, _w in pairs:
                _w.setMinimumWidth(88); _w.valueChanged.connect(self._emit)
                row.addWidget(QLabel(_l, self)); row.addWidget(_w)
            row.addStretch()
            wrap = QWidget(self); wrap.setLayout(row)
            return wrap
        # Two rows so each spin is wide enough for its content (rotate/scale on
        # one, move X/Y on the next).
        self._clip_image_xform_w = _xform_row((tr("Rotate"), self.clip_image_rotation),
                                              (tr("Scale"), self.clip_image_scale))
        self._clip_image_move_w = _xform_row((tr("X"), self.clip_image_offx),
                                             (tr("Y"), self.clip_image_offy))
        self._clip_image_fit_row = add_row(
                ccg, 5, tr("Content fit:"), self._clip_image_xform_w,
                tip=TooltipButton(
                    tr("Content fit"),
                    tr("Places whatever the clip border is carrying — an imported "
                       "image, or the ChromIQ branding with your own lines under "
                       "it.\n\n"
                       "  • Rotate turns an imported image by whole degrees. The "
                       "branding always reads up the strip, so rotation does not "
                       "apply to it — use “Flip 180°” above to turn it the other "
                       "way round.\n"
                       "  • Scale is a percentage of the size that fits the band: "
                       "100 % is the automatic fit, less makes it smaller, more "
                       "makes it bigger.\n\n"
                       "Anything you push past the edge of the band is cut off, "
                       "and the Preview below shows that before it reaches "
                       "paper.\n\n"
                       "Default: 0°, 100 %."), self))
        self._clip_image_move_row = add_row(
                ccg, 6, tr("Content move:"), self._clip_image_move_w,
                tip=TooltipButton(
                    tr("Content move"),
                    tr("Shifts the image or the branding inside the clip border, "
                       "in millimetres.\n\n"
                       "  • X moves it ACROSS the clip border — towards the paper "
                       "edge, or towards the patches.\n"
                       "  • Y moves it ALONG the clip border — up or down the "
                       "sheet.\n\n"
                       "Both start at 0, which centres the content in the clip "
                       "border. Watch the Preview: what leaves the clip border is "
                       "not printed."),
                    self))
        add_row(ccg, 7, tr("Clip area:"), self.clip_dims_label,
                tip=TooltipButton(
                    tr("Clip area measurements"),
                    tr("The size of the printable clip-border strip — width × "
                       "height in millimetres — where your text or branding is "
                       "placed.\n\n"
                       "Where the numbers come from:\n"
                       "  • Width is the “Clip border width” you set above (or the "
                       "clip-side page margin, whichever is larger — the engine "
                       "reserves the bigger of the two on that edge).\n"
                       "  • Height is the paper height minus the top and bottom "
                       "text distances (so the strip clears the very edges), for "
                       "the current paper and orientation.\n\n"
                       "It updates live as you change the clip-border width, the "
                       "margins, the paper or the orientation, so you can see how "
                       "much room your text has before you print."),
                    self))
        add_row(ccg, 8, tr("Preview:"), self.clip_preview)
        ccg.addWidget(self.clip_export_btn, 9, 1)
        _expert_v.addWidget(self._clip_content_grp)

        # ---- Calibration (per-chart; engine -K/-I) ----
        self.cal_mode = self.cal_path_edit = None
        if with_calibration:
            from PyQt6.QtWidgets import QLineEdit, QPushButton
            cg = QGroupBox(tr("Printer calibration"), self)
            cgg = QGridLayout(cg)
            cgg.addWidget(QLabel(tr("Mode:"), self), 0, 0)
            self.cal_mode = ElidingComboBox(self)
            for k, lbl in (("off", tr("None")),
                           ("apply", tr("Apply & embed (-K)")),
                           ("embed", tr("Embed only (-I)"))):
                self.cal_mode.addItem(lbl, k)
            self.cal_mode.currentIndexChanged.connect(self._emit)
            cgg.addWidget(self.cal_mode, 0, 1)
            self.cal_path_edit = QLineEdit(self)
            self.cal_path_edit.setPlaceholderText(tr("no .cal file selected"))
            self.cal_path_edit.textChanged.connect(self._emit)
            cgg.addWidget(self.cal_path_edit, 1, 0, 1, 3)
            browse = self._compact_browse(tr("Browse for a .cal file"))
            browse.clicked.connect(self._browse_cal)
            cgg.addWidget(browse, 1, 3)
            cgg.addWidget(TooltipButton(
                tr("Printer calibration"),
                tr("Attach an ArgyllCMS calibration (.cal) that linearises your "
                   "printer so the chart's tones come out evenly spaced. "
                   "“Apply & embed (-K)” bakes the calibration into the printed "
                   "patch values and also records it in the chart file — pick this "
                   "if you have a .cal and want it used. “Embed only (-I)” just "
                   "records it without changing the patches; use this when your "
                   "printer or RIP already linearises on its own. Leave it on "
                   "“None” if you don't use a calibration."), self), 0, 2)
            _expert_v.addWidget(cg)

        # Match the compact input styling used throughout the Manual module
        # (app QSS targets #compact_input for the slim look + white bg).
        from PyQt6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit
        for w in self.findChildren((QAbstractSpinBox, QComboBox, QLineEdit)):
            w.setObjectName("compact_input")

        self._sync_clip_content_enabled()
        self._sync_spacer_swatches()
        self._update_clip_visibility()
        self._sync_layout_mode()
        # Re-run the instrument-specific visibility now that every widget exists
        # (the selectors-block init sync ran before cm_stagger_cb / clip_enable
        # were built, so they were left visible for non-ColorMunki instruments).
        # Works for BOTH configs: with selectors the instrument comes from the
        # combo; without them (the embedded Preferences → Chart Layout panel,
        # driven by set_recipe) it comes from the last-known _inst.
        self._sync_instrument_widgets(
            (self.instr.currentData() if self.instr is not None else self._inst)
            or "i1")

    def _browse_cal(self) -> None:
        from pathlib import Path
        from ui.widgets import open_file_dialog
        cur = self.cal_path_edit.text().strip() if self.cal_path_edit else ""
        start = str(Path(cur).parent) if cur else ""
        path = open_file_dialog(
            self, tr("Select printer calibration"),
            name_filter=tr("ArgyllCMS calibration (*.cal)"),
            start_dir=start, extra_path=start)
        if path and self.cal_path_edit is not None:
            self.cal_path_edit.setText(path)

    def cal_settings(self) -> tuple[str | None, bool]:
        """Return ``(cal_path_or_None, apply_cal)`` for the engine."""
        if self.cal_mode is None:
            return None, False
        mode = self.cal_mode.currentData()
        path = (self.cal_path_edit.text().strip() or None) if self.cal_path_edit else None
        if mode == "off" or not path:
            return None, False
        return path, (mode == "apply")

    def set_cal(self, path: str, mode: str) -> None:
        if self.cal_mode is None:
            return
        i = self.cal_mode.findData(mode)
        self.cal_mode.setCurrentIndex(i if i >= 0 else 0)
        if self.cal_path_edit is not None:
            self.cal_path_edit.setText(path or "")

    # ------------------------------------------------------------------
    def _apply_mode_defaults(self, *_a) -> None:
        """Seed the Guided-matching defaults when the user picks a mode that has
        its own preset. ColorMunki Extra-high density mirrors Guided's triple
        density exactly: 5 mm margins on every side (clip already defaults off for
        CM). Skipped during load so a loaded recipe's own margins win (#93,
        Sebastian)."""
        if self._loading or self.mode is None or self.instr is None:
            return
        if (self.instr.currentData() == "CM"
                and self.mode.currentData() == "extrahigh"):
            self._loading = True
            for k in ("t", "r", "b", "l"):
                self.margins[k].setValue(5.0)
            self._border = 5.0                       # base margin, = Guided
            # Guided centres the patch block (the small extra gap below the strip
            # labels Sebastian liked); match it here.
            if hasattr(self, "patch_align"):
                j = self.patch_align.findData("center-left")
                if j >= 0:
                    self.patch_align.setCurrentIndex(j)
            self._loading = False
            self._emit()

    def _sync_instrument_widgets(self, inst: str) -> None:
        """Show/hide the instrument-specific layout controls for *inst*.

        Called from :meth:`_on_instr_changed` and at the end of ``__init__``.
        The init sync fired from the selectors block runs *before* these widgets
        are constructed, so without the end-of-init call they were born visible
        for every instrument — e.g. "Offset every second strip" (a ColorMunki-
        only option) showed for SpectroScan / i1Pro / DTP41 / DTP51 until the
        user manually changed the instrument (Knut)."""
        # The extra clip-border On/Off selector — and its tooltip — are for CM/SS
        # only (i1/p3 use their Mode selector for the clip border).
        if hasattr(self, "clip_enable"):
            is_band = inst in ("CM", "SS", "CR30")
            self.clip_enable.setVisible(is_band)
            self._clip_enable_lbl.setVisible(is_band)
            self._clip_enable_tip.setVisible(is_band)
            self._sync_clip_enable_display()
        # "Offset every second strip" is a ColorMunki-only option.
        if hasattr(self, "cm_stagger_cb"):
            self.cm_stagger_cb.setVisible(inst == "CM")
            self._cm_stagger_tip.setVisible(inst == "CM")

    def _on_instr_changed(self, *_a) -> None:
        from workflow.layout_engine import papers
        if self.instr is None:
            return
        # True when set_recipe() is driving this change (it sets _loading before
        # touching the instrument combo): then the recipe supplies the layout
        # mode, so the SpectroScan default below must NOT override it.
        was_loading = self._loading
        self._loading = True
        inst = self.instr.currentData() or "i1"
        prev_paper = self.paper.currentData()
        self.paper.clear()
        for code, label, _dims in papers.list_papers(inst, for_engine=True):
            self.paper.addItem(label, code)
        self.paper.addItem(tr("Custom…"), "__custom__")
        i = self.paper.findData(prev_paper)
        if i < 0:
            # The engine paper list is ordered largest-first (A2 is index 0), which
            # is a surprising default — fall back to A4 when the previous paper
            # isn't available for the new instrument, not whatever sits at 0 (the
            # "keeps jumping back to A2" report, Sebastian).
            i = self.paper.findData("A4")
        self.paper.setCurrentIndex(i if i >= 0 else 0)
        prev_mode = self.mode.currentData()
        self.mode.clear()
        for k, lbl in self.modes_for(inst):
            self.mode.addItem(lbl, k)
        j = self.mode.findData(prev_mode)
        self.mode.setCurrentIndex(j if j >= 0 else 0)
        if getattr(self, "_mode_lbl", None) is not None:
            self._mode_lbl.setText(self.mode_label_for(inst))
        # Mode tooltip describes only the option this instrument actually has.
        if getattr(self, "_mode_tip", None) is not None:
            self._mode_tip.set_content(*self.mode_tooltip_for(inst))
        self._sync_instrument_widgets(inst)
        # Picking the SpectroScan defaults the layout to patch-first (a flatbed
        # reads a fixed grid; area-first + By-minimum-width collapses it to
        # useless full-width bands). Its area method also defaults to
        # By-columns/rows, so even if the user later switches to area-first they
        # get a proper grid, never bands (By-minimum-width is meaningless for a
        # flatbed). Only on a genuine USER switch — a preset load carries its own
        # values. Both selectors stay fully changeable afterwards.
        if hasattr(self, "layout_mode"):
            # The CR30 defaults to patch-first for a different reason (#159):
            # its patch size is what a hand aims at through a 4 mm aperture, so
            # it must not float with the paper. Its area METHOD is deliberately
            # left alone — "By minimum width" is meaningless for a flatbed but
            # perfectly meaningful for a hand-placed device, which really does
            # have a smallest patch a person can hit.
            if not was_loading and inst == "CR30":
                _pf = self.layout_mode.findData("patch_first")
                if _pf >= 0:
                    self.layout_mode.setCurrentIndex(_pf)
            if not was_loading and inst == "SS":
                _pf = self.layout_mode.findData("patch_first")
                if _pf >= 0:
                    self.layout_mode.setCurrentIndex(_pf)
                if hasattr(self, "area_method"):
                    _bg = self.area_method.findData("by_grid")
                    if _bg >= 0:
                        self.area_method.setCurrentIndex(_bg)
            self._sync_layout_mode()
        # Switching to an instrument with a real clip border (i1/p3): if the clip
        # content is still "off" — e.g. carried over from ColorMunki, which has no
        # clip band — default it to the notes record so the clip border isn't
        # blank. Only on a genuine USER switch; a preset/recipe load (was_loading)
        # carries its own clip-content value and must not be overridden.
        if (not was_loading and inst in ("i1", "p3")
                and hasattr(self, "clip_content_mode")
                and self.clip_content_mode.currentData() == "off"):
            _notes = self.clip_content_mode.findData("notes")
            if _notes >= 0:
                self.clip_content_mode.setCurrentIndex(_notes)
        self._loading = False
        self._on_paper_changed()

    def _update_clip_visibility(self, *_a) -> None:
        """Show the clip-content group when a clip / notes band is available: for
        i1/p3 in clip-border mode, and for CM/SS (which can carry an optional
        notes band, #93). The clip-width row shows whenever that band exists
        (i1/p3 clip mode, or CM/SS once notes content is turned on)."""
        if not hasattr(self, "clip_width"):
            return
        if self.instr is not None:
            inst = self.instr.currentData() or "i1"
            clip_mode = inst in ("i1", "p3") and (self.mode.currentData() == "clip")
        else:
            inst = self._inst
            clip_mode = self._clip and inst in ("i1", "p3")
        is_band_inst = inst in ("CM", "SS", "CR30")
        content_on = (hasattr(self, "clip_content_mode")
                      and self.clip_content_mode.currentData() != "off")
        # For CM/SS the band (and its content group) appears only when the clip
        # border is turned on — i.e. content is set to something — matching the
        # i1Pro, whose group hides when its clip is off (#93).
        show_group = clip_mode or (is_band_inst and content_on)
        show_width = clip_mode or (is_band_inst and content_on)
        for w in (self.clip_width_label,
                  getattr(self, "_clip_width_row", self.clip_width),
                  self.clip_width_tip):
            w.setVisible(show_width)
        if hasattr(self, "_clip_content_grp"):
            self._clip_content_grp.setVisible(show_group)
            if show_group:
                self._refresh_clip_preview()
        # Floor the clip-side margin at the clip width whenever a band is active.
        self._update_clip_margin_conflict()

    # ---- Clip-border content -------------------------------------------
    def _sync_clip_content_enabled(self) -> None:
        mode = self.clip_content_mode.currentData()
        # The "notes" design is fixed (auto-filled from the chart) so it ignores
        # the free Text field, but still honours the Font choice for its body.
        # Every mode that can carry words has the Text field live. Only the
        # Notes box fills itself in, so only the Notes box switches it off
        # (#164, Knut: *"Only Notes box shall have the text field disabled"*).
        custom_text = mode in ("text", "branding", "image")
        font_modes = mode in ("text", "branding", "notes", "image")
        self.clip_text.setEnabled(custom_text)
        self.clip_insert_btn.setEnabled(custom_text)
        # …and grey its LABEL with it. A live-looking "Text:" over a dead box is
        # the other half of what made Knut read the Notes-box field as editable
        # (#164); the app's dimmed-caption object name is what this theme styles
        # for disabled, exactly as the ruler-marker rows do.
        for _w in getattr(self, "_clip_text_row", []) or []:
            if isinstance(_w, QLabel):
                _w.setObjectName("param_label")
                _w.setEnabled(custom_text)
        self.clip_text_font.setEnabled(font_modes)
        # Manual size applies to the free-text clip content; the notes design
        # lays itself out, so the size box is inert there (#125).
        if hasattr(self, "clip_text_size"):
            self.clip_text_size.setEnabled(custom_text)
        # The image PATH row only makes sense for an imported image, so it is
        # hidden entirely unless "Imported image" is the content type (Knut),
        # rather than just greyed out.
        show_image = (mode == "image")
        for w in (getattr(self, "_clip_image_row", None) or []):
            w.setVisible(show_image)
        # The fit / move rows serve the BRANDING too (#164, Knut: *"For Imported
        # image option, then there are fields to position the image. Why are
        # those options not available for ChromIQ branding? Currently the image
        # is always centred on page vertically and text on next line."*). They
        # are the same recipe fields either way, so a preset carries the
        # placement whichever content it uses.
        show_place = mode in ("image", "branding")
        for row in (getattr(self, "_clip_image_fit_row", None),
                    getattr(self, "_clip_image_move_row", None)):
            for w in (row or []):
                w.setVisible(show_place)
        # Rotation is an image-only transform: the branding is composed to read
        # up the strip, and "Flip 180°" is how it is turned the other way.
        if hasattr(self, "clip_image_rotation"):
            self.clip_image_rotation.setEnabled(mode == "image")

    def _on_clip_content_changed(self, *_a) -> None:
        # "Example custom table" isn't a persistent mode — it loads a ready-made
        # record into the editable Text box and switches to Custom text (Knut).
        if self.clip_content_mode.currentData() == "example":
            self._load_example_clip_table()
            return
        self._sync_clip_content_enabled()
        # On CM/SS the clip-width row appears only once notes content is on, so
        # re-evaluate visibility when the content mode changes (#93).
        self._sync_clip_enable_display()
        self._update_clip_visibility()
        self._emit()

    @staticmethod
    def _example_clip_table_text() -> str:
        """A ready-made record for the clip strip (Knut's approved layout): a
        header line with the chart summary + print reminder, then two rows of
        fill-in fields with a BLANK line between each for hand-writing. The
        {patchcount}/{paper} tokens fill in when the chart is built; the underline
        runs are lengths Knut tuned to sit nicely at ~10–12 pt. Kept in sync with
        workflow/chart_creator.py's legacy left-clip record."""
        def field(label_key: str, n: int) -> str:
            return f"{tr(label_key)}: {'_' * n}"
        header = (tr("ChromIQ Chart {patchcount} RGB target on {paper}") + " - "
                  + tr("PRINT: borderless, 100% size (no scaling), color management OFF"))
        row1 = f"{field('date', 24)} {field('printer', 53)} {field('ink set', 53)}"
        row2 = (f"{field('profile name', 43)} {field('paper type', 36)} "
                f"{field('driver/resolution', 29)}")
        return "\n".join([header, " ", row1, " ", row2])

    def _load_example_clip_table(self) -> None:
        """Fill the clip Text box with the example record and switch to Custom
        text so it can be edited. Confirms first if the box already has text, so a
        stray selection can't wipe the user's own record."""
        existing = self.clip_text.toPlainText().strip()
        if existing:
            from PyQt6.QtWidgets import QMessageBox
            if QMessageBox.question(
                    self, tr("Load example table?"),
                    tr("Replace the current clip-border text with the example "
                       "table?")) != QMessageBox.StandardButton.Yes:
                # Revert the combo to Custom text without touching the text.
                self._select_clip_content("text")
                return
        self.clip_text.setPlainText(self._example_clip_table_text())
        self._select_clip_content("text")

    def _select_clip_content(self, key: str) -> None:
        """Set the Content combo to *key* and run the normal post-change sync,
        without recursing through the "example" one-shot branch."""
        i = self.clip_content_mode.findData(key)
        self.clip_content_mode.blockSignals(True)
        if i >= 0:
            self.clip_content_mode.setCurrentIndex(i)
        self.clip_content_mode.blockSignals(False)
        self._sync_clip_content_enabled()
        self._sync_clip_enable_display()
        self._update_clip_visibility()
        self._emit()

    def _sync_clip_enable_display(self) -> None:
        """Keep the CM/SS clip-border On/Off selector in step with the content
        mode (On ⇔ content set, Off ⇔ content off), without re-triggering its
        own handler (#93)."""
        if not hasattr(self, "clip_enable"):
            return
        on = (hasattr(self, "clip_content_mode")
              and self.clip_content_mode.currentData() not in (None, "off"))
        i = self.clip_enable.findData("on" if on else "off")
        self.clip_enable.blockSignals(True)
        self.clip_enable.setCurrentIndex(i if i >= 0 else 0)
        self.clip_enable.blockSignals(False)

    def _on_clip_enable_changed(self, *_a) -> None:
        """The CM/SS clip-border On/Off selector drives the content on/off."""
        self.set_clip_enabled(self.clip_enable.currentData() == "on")

    def _sync_clip_content_for_mode(self, *_a) -> None:
        """i1 / i1Pro 3+ use the Mode combo as the clip-border On/Off switch.
        Turning the clip border ON should default its content to the notes box
        (not “none”), and clear it when OFF — mirroring the CM/SS clip-enable
        behaviour (Knut). Skipped during load so a recipe that deliberately had
        the clip border on with no content keeps it."""
        if self._loading or self.instr is None or self.mode is None:
            return
        if self.instr.currentData() in ("i1", "p3"):
            self.set_clip_enabled(self.mode.currentData() == "clip")

    def clip_enabled(self) -> bool:
        """Whether a clip / notes band is currently turned on (content set)."""
        return (hasattr(self, "clip_content_mode")
                and self.clip_content_mode.currentData() not in (None, "off"))

    def set_clip_enabled(self, on: bool) -> None:
        """Turn the clip / notes band on or off by driving the content mode: On
        seeds a notes band (if none yet), Off clears it (#93). Lets a host (the
        Settings window) expose the CM/SS clip toggle without its own selector."""
        cur = self.clip_content_mode.currentData()
        if on and cur in (None, "off"):
            j = self.clip_content_mode.findData("notes")
            if j >= 0:
                self.clip_content_mode.setCurrentIndex(j)   # fires content-changed
        elif not on and cur not in (None, "off"):
            j = self.clip_content_mode.findData("off")
            if j >= 0:
                self.clip_content_mode.setCurrentIndex(j)   # fires content-changed
        else:
            self._update_clip_visibility()
            self._emit()

    # ------------------------------------------------------------------
    # Spin-box widths
    # ------------------------------------------------------------------
    def showEvent(self, event) -> None:      # noqa: N802 (Qt override)
        super().showEvent(event)
        if not self._spin_widths_fitted:
            self._spin_widths_fitted = True
            self._fit_spin_widths()

    def _fit_spin_widths(self) -> None:
        """Size each millimetre box to the widest string IT can actually show.

        The chrome — up/down buttons, frame, text padding — is ASKED OF THE
        STYLE rather than guessed, and it can only be asked once the widget has
        been polished: before that the per-widget stylesheet has not been
        applied and the same query answers 20 px instead of 55. (Same trap as
        the QSS-padding note in `ui/styles.py`: QSS geometry lands after the
        hint is taken.) A hard-coded 34 shipped in its place, 21 px short, and
        an 84 px floor beside it hid the error — until that floor became the
        thing that made three boxes in a row 367 px wide in Norwegian and
        pushed the panel into horizontal scrolling.
        """
        from PyQt6.QtWidgets import (QAbstractSpinBox, QStyle,
                                     QStyleOptionSpinBox)

        def _need(sb):
            """Width the box must have to show its longest string, or None."""
            fm = sb.fontMetrics()
            longest = sb.prefix() + sb.textFromValue(sb.maximum()) + sb.suffix()
            widest = max(fm.horizontalAdvance(longest),
                         fm.horizontalAdvance(sb.specialValueText() or ""))
            opt = QStyleOptionSpinBox()
            sb.initStyleOption(opt)
            field = sb.style().subControlRect(
                QStyle.ComplexControl.CC_SpinBox, opt,
                QStyle.SubControl.SC_SpinBoxEditField, sb).width()
            chrome = max(0, sb.width() - field)
            if chrome <= 0:
                return None
            return widest + chrome + 4   # 4 px so the caret is not on the frame

        for sb in self._fitted_spins:
            need = _need(sb)
            if need is None:
                continue
            sb.setMinimumWidth(need)
            sb.setMaximumWidth(need + 8)

        # AND EVERY OTHER BOX THAT WOULD CLIP ITS OWN SPECIAL VALUE. The two
        # helpers above are not the only places a spin box is built here, and
        # the others carry hard 84/96 px widths measured against the English
        # word "auto" — Portuguese writes "automático" and the panel showed
        # "mático" in "Largura mínima da amostra" (on screen, 2026-08-27). This
        # pass only ever WIDENS: a box that already fits, or that was
        # deliberately made wide (the dpi and seed boxes), is left alone.
        for sb in self.findChildren(QAbstractSpinBox):
            if sb in self._fitted_spins:
                continue
            need = _need(sb)
            if need is None or sb.maximumWidth() >= need:
                continue
            sb.setMaximumWidth(need)
            if sb.minimumWidth() < need:
                sb.setMinimumWidth(need)

    def set_threshold_lookup(self, fn) -> None:
        """Wire a callable ``fn(instrument, paper_code) -> {L,R,T,B}|None`` that
        returns the user's Instrument-Margins thresholds, enabling the "Use
        instrument margins" checkbox (#93). Without it the checkbox stays hidden."""
        self._threshold_lookup = fn
        if hasattr(self, "use_instr_margins"):
            self.use_instr_margins.setVisible(fn is not None)
            if hasattr(self, "_use_instr_tip"):
                self._use_instr_tip.setVisible(fn is not None)
            self._sync_instr_margins()

    def _current_instrument_paper(self) -> tuple[str, str]:
        if self.instr is not None and self.paper is not None:
            return (self.instr.currentData() or "i1",
                    self.paper.currentData() or "A4")
        return (self._inst, "A4")

    def _sync_instr_margins(self, *_a) -> None:
        """When "Use instrument margins" is on, fill the four margins from the
        threshold lookup for the current combo and lock them read-only; ticking it
        remembers the user's own margins and unticking restores them (#93, Knut)."""
        fn = getattr(self, "_threshold_lookup", None)
        on = (fn is not None and hasattr(self, "use_instr_margins")
              and self.use_instr_margins.isChecked())
        loading = getattr(self, "_loading", False)
        if loading:                      # a fresh recipe → no restore baseline
            self._saved_margins = None

        def _set(k, v):
            self.margins[k].blockSignals(True)
            self.margins[k].setValue(float(v))
            self.margins[k].blockSignals(False)
            # Signals were blocked (so we don't fire _emit for every edge), so
            # the inch readout wouldn't refresh on its own — do it by hand, or
            # it would keep showing the previous value (Sebastian).
            refresh = getattr(self.margins[k], "_refresh_inch", None)
            if refresh is not None:
                refresh()

        if on:
            # Remember the user's typed margins the first time it's ticked, so
            # unticking can put them back.
            if not loading and getattr(self, "_saved_margins", None) is None:
                self._saved_margins = {k: self.margins[k].value()
                                       for k in ("t", "r", "b", "l")}
            inst, paper = self._current_instrument_paper()
            try:
                thr = fn(inst, paper)
            except Exception:
                thr = None
            if thr:
                for k, key in {"t": "T", "r": "R", "b": "B", "l": "L"}.items():
                    v = thr.get(key)
                    if v not in (None, ""):
                        _set(k, v)
            else:
                # No user-defined Instrument-Limits entry for this instrument
                # (e.g. SpectroScan): don't leave the PREVIOUS instrument's
                # margins showing (Knut). Fall back to this instrument's own
                # default margins from the engine geometry, so the four boxes
                # always update the moment you pick a different instrument.
                fb = {"t": 6.0, "r": 6.0, "b": 6.0, "l": 6.0}
                try:
                    from workflow.layout_engine import instruments as _ins
                    g = _ins.geom_from_build_kwargs(
                        {"instrument": inst, "paper": paper,
                         "layout_mode": "patch_first"})
                    fb = {"t": g.margin_t, "r": g.margin_r,
                          "b": g.margin_b, "l": g.margin_l}
                except Exception:
                    pass
                for k, v in fb.items():
                    _set(k, v)
        else:
            saved = getattr(self, "_saved_margins", None)
            if saved is not None:        # restore what was there before ticking
                for k in ("t", "r", "b", "l"):
                    _set(k, saved[k])
                self._saved_margins = None
        for k in ("t", "r", "b", "l"):
            self.margins[k].setEnabled(not on)
            self.margins[k].setToolTip(tr(
                "Locked to your instrument's minimum margins because "
                "“Use instrument margins” is ticked. Untick it to type your "
                "own margins.") if on else "")
        # The clip-border width is NOT one of the four page margins, so
        # "Use instrument margins" must never lock it — you can always change
        # the clip-border width (Knut).
        if hasattr(self, "clip_width"):
            self.clip_width.setEnabled(True)
        # Re-evaluate the clip-width vs clip-side-margin highlight, which stays
        # active while margins are locked.
        self._update_clip_margin_conflict()

    def _clip_band_active(self) -> bool:
        """Whether a clip / notes band is currently on for the selected
        instrument (i1/p3 clip mode, or CM/SS with notes content)."""
        inst = (self.instr.currentData() if self.instr is not None
                else self._inst) or "i1"
        if inst in ("i1", "p3"):
            return (self.mode.currentData() == "clip") if self.mode is not None \
                else bool(self._clip)
        if inst in ("CM", "SS", "CR30"):
            return (hasattr(self, "clip_content_mode")
                    and self.clip_content_mode.currentData() not in (None, "off"))
        return False

    # Scoped to the spinbox classes so the red outline MERGES with the
    # widget's own per-widget stylesheet instead of replacing it. The margin /
    # clip-width boxes carry the load-bearing _input_bg_qss() rule (their
    # white-in-light field background — app-wide QSS is ignored for compound
    # widgets); the old un-scoped "border: …" sheet wiped that rule, leaving
    # every box that ever touched conflict handling looking permanently
    # greyed-out even though it stayed enabled (Knut, beta.5).
    _CONFLICT_QSS = (" QSpinBox, QDoubleSpinBox {"
                     " border: 1px solid #d9534f; border-radius: 3px; }")

    def _set_field_conflict(self, widget, message: "str | None") -> None:
        """Flag ``widget`` with a red outline + ``message`` tooltip, or clear the
        flag when ``message`` is None — restoring the widget's original tooltip
        AND its original stylesheet. Clearing a never-flagged widget is a no-op
        (it must not touch the widget's own stylesheet). Used for the
        clip-width ↔ clip-side-margin priority conflict (#125, Knut)."""
        if not hasattr(self, "_field_conflict_orig"):
            self._field_conflict_orig: dict[int, tuple[str, str]] = {}
        wid = id(widget)
        if message:
            if wid not in self._field_conflict_orig:
                self._field_conflict_orig[wid] = (widget.toolTip(),
                                                  widget.styleSheet())
            _tip, orig_qss = self._field_conflict_orig[wid]
            widget.setStyleSheet(orig_qss + self._CONFLICT_QSS)
            widget.setToolTip(message)
        elif wid in self._field_conflict_orig:
            tip, orig_qss = self._field_conflict_orig.pop(wid)
            widget.setToolTip(tip)
            widget.setStyleSheet(orig_qss)

    def _set_field_hint(self, widget, message: "str | None") -> None:
        """Set an explanatory tooltip on a field **without** a red outline (and
        restore the original when ``message`` is None). Used to explain a
        clip↔margin conflict on the always-editable clip-width box while the red
        outline itself sits on the locked (disabled) margin box, which can't pop
        a tooltip of its own (Sebastian)."""
        if not hasattr(self, "_field_hint_orig"):
            self._field_hint_orig: dict[int, str] = {}
        wid = id(widget)
        if message:
            self._field_hint_orig.setdefault(wid, widget.toolTip())
            widget.setToolTip(message)
        elif wid in self._field_hint_orig:
            widget.setToolTip(self._field_hint_orig.pop(wid))

    def _update_clip_margin_conflict(self, *_a) -> None:
        """Clip-border width and the clip-side page margin are **independent**
        inputs; the LARGER of the two is what the engine reserves on that edge
        (``instruments.build`` takes the max). The old code silently copied the
        clip width into the margin box, which confused users (Knut #125) — now
        the field being overridden is flagged with a red outline + a tooltip
        that explains which value wins:

          • band ON, clip width > clip-side margin → clip width wins; the margin
            box is flagged (too small to matter).
          • band ON, clip width < clip-side margin → the margin wins; the clip
            width box is flagged (smaller than the margin, so ignored).
          • equal, band OFF, or margins locked by "Use instrument margins" → no
            conflict; both fields shown normally.
        """
        if not (hasattr(self, "clip_width") and hasattr(self, "clip_side")):
            return
        m_l, m_r = self.margins.get("l"), self.margins.get("r")
        if m_l is None or m_r is None:
            return
        # Always start from a clean slate (both the red-outline flags and any
        # tooltip-only hint we parked on the clip-width box) — even while
        # values are being loaded. Skipping the clean-up during loading left a
        # stale red outline behind in the Preferences panel: a flag set
        # mid-load survived because the clip band ended up OFF and nothing
        # re-evaluated afterwards (Knut, beta.5).
        for w in (m_l, m_r, self.clip_width):
            self._set_field_conflict(w, None)
        self._set_field_hint(self.clip_width, None)
        # The conflict highlight stays active even when "Use instrument
        # margins" locks the page margins (Knut): the clip-border width is
        # still yours to change, so knowing which value wins matters. Only the
        # clip band being off makes it moot.
        if self._loading or not self._clip_band_active():
            return
        locked = (hasattr(self, "use_instr_margins")
                  and self.use_instr_margins.isChecked())
        side = (self.clip_side.currentData() or "left")
        side_margin = m_r if side == "right" else m_l
        side_name = tr("right") if side == "right" else tr("left")
        cw = self.clip_width.value()
        mv = side_margin.value()
        if abs(cw - mv) <= 1e-9:
            return                         # equal → nothing to flag
        clip_wins = cw > mv
        if locked:
            # Margins come from the instrument and are LOCKED (disabled). Never put
            # the red outline on that greyed box — on a disabled field it reads as a
            # stray, stuck focus ring rather than a warning (Sebastian). The
            # explanation rides on the always-editable clip-width box instead: a
            # hover hint when the clip legitimately wins, a red outline only when
            # the clip is too narrow (the field the user would raise).
            if clip_wins:
                self._set_field_hint(self.clip_width, tr(
                    "The clip-border width ({cw:.1f} mm) is wider than your "
                    "instrument's {side} margin ({mv:.1f} mm). On the {side} edge "
                    "the wider of the two is what gets reserved, so here the "
                    "clip-border width wins and this margin is effectively "
                    "overridden. That's fine — the clip border simply sets the "
                    "spacing on this edge. Lower the clip-border width below "
                    "{mv:.1f} mm if you want the instrument margin to take over."
                ).format(cw=cw, mv=mv, side=side_name))
            else:
                self._set_field_conflict(self.clip_width, tr(
                    "The clip-border width ({cw:.1f} mm) is narrower than your "
                    "instrument's {side} margin ({mv:.1f} mm). On the {side} edge "
                    "the wider of the two is what gets reserved, so here the "
                    "instrument margin wins and the clip border sits inside it. "
                    "Raise the clip-border width above {mv:.1f} mm if you want the "
                    "clip zone to reach past the margin."
                ).format(cw=cw, mv=mv, side=side_name))
        elif clip_wins:
            # Editable margins (#125): flag the (too-small) margin box you can raise
            # so it's clear the clip-border width is what gets reserved here.
            self._set_field_conflict(side_margin, tr(
                "The clip-border width ({cw:.1f} mm) is wider than this {side} "
                "margin, so the clip-border width is what gets reserved on the "
                "{side} edge. Raise this margin above the clip-border width if "
                "you want to push the patches further in.").format(
                    cw=cw, side=side_name))
        else:
            self._set_field_conflict(self.clip_width, tr(
                "The {side} margin ({mv:.1f} mm) is wider than the clip-border "
                "width, so the {side} margin is what gets reserved and this "
                "clip-border width is ignored. Raise it above the {side} margin "
                "to widen the reserved clip zone.").format(
                    mv=mv, side=side_name))

    def _sync_layout_mode(self, *_a) -> None:
        """Show only the fields each layout choice needs (#93 / Knut). Area-first
        derives the patch size, so HIDE the patch size/scale rows and the patch-
        area-alignment row (alignment is moot when the patches fill the area) —
        symmetric with hiding the area fields in patch-first. Margins and clip-
        border width stay (they define the area)."""
        if not hasattr(self, "layout_mode"):
            return
        area = (self.layout_mode.currentData() == "area_first")
        self._area_fields_w.setVisible(area)
        # Patch size/scale/alignment, the strip-length cap and the chart offset are
        # all "Prioritise patch size" concerns — area-first sizes patches to fill
        # the margin box, so hide them there (Knut #93).
        _patch_first_rows = [getattr(self, "_patch_size_row", []),
                             getattr(self, "_patch_scale_row", []),
                             getattr(self, "_patch_align_row", []),
                             getattr(self, "_max_strip_row", []),
                             getattr(self, "_offset_row", [])]
        for row in _patch_first_rows:
            for w in row:
                w.setVisible(not area)
        for w in (getattr(self, "nolimit", None), getattr(self, "_nolimit_tip", None)):
            if w is not None:
                w.setVisible(not area)
        # Within area-first, show only the rows the chosen Calculation method
        # needs: "by patch width" → min width + height%; "by columns/rows" →
        # strips + rows (Knut's two methods).
        by_width = (self.area_method.currentData() == "by_width")
        for w in self._area_row_minpatch + self._area_row_ratio:
            w.setVisible(area and by_width)
        for w in self._area_row_cols + self._area_row_rows:
            w.setVisible(area and not by_width)
        # THE COLORMUNKI DENSITY ROW USED TO BE HIDDEN IN AREA-FIRST. IT MUST NOT
        # BE. The belief was that in area-first "the patch size comes from the
        # columns/rows you set", so Density does nothing — true only when the
        # grid is FULLY pinned. With columns and rows on auto, which is what a
        # new preset has (area_cols = area_rows = 0), Density is the entire
        # input that decides the layout. Measured on A3, patches per sheet,
        # only cm_density varied (hand-held / rig / extra-high):
        #     area_first, by_width, min width auto : 130 /  520 / 918
        #     area_first, by_grid,  cols/rows auto : 270 /  540 / 756
        #     area_first, by_grid,  pinned 20x30   : 600 /  600 / 600
        # A 7x spread is not "moot". Density also states which ColorMunki
        # accessory the sheet is for (hand-held vs the measuring rig), so hiding
        # it stranded the user with whatever was last set and no way to see it.
        # The row stays for every layout mode, in every host of this panel.
        if self.mode is not None:
            for w in (self.mode, getattr(self, "_mode_lbl", None),
                      getattr(self, "_mode_tip", None)):
                if w is not None:
                    w.setVisible(True)

    def _browse_clip_image(self) -> None:
        from pathlib import Path
        from ui.widgets import open_file_dialog
        cur = self.clip_image_path.text().strip()
        start = str(Path(cur).parent) if cur else ""
        path = open_file_dialog(
            self, tr("Select clip-strip image"),
            name_filter=tr("Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp)"),
            start_dir=start, extra_path=start, preview=True)
        if path:
            self.clip_image_path.setText(path)

    def _clip_geom_and_height(self):
        """The Geom + paper size behind the clip preview, for ANY instrument
        whose band is on — or None when there is no band to show.

        Returns ``(geom, paper_h_mm, paper_w_mm)``.

        **The ColorMunki and the SpectroScan have a band too.** They have no
        native clip border, but they carry an optional notes band the moment
        clip content is switched on — the renderer reserves it in
        ``instruments.geom_from_build_kwargs`` (#93). This method used to answer
        None for anything that was not an i1/p3, so on one of Knut's ColorMunki
        presets the panel printed the band onto the sheet while showing
        *"Clip area: —"* and an empty Preview box, in every content mode
        (#164, 2026-08-23: *"the Preview does not know anything … the 'Clip
        area' shows only '-' … Choose any of my presets for colormunki to
        see."*). :meth:`_clip_band_active` already encodes exactly which
        selections have a band, so ask it rather than hard-coding two
        instruments here.

        **The band width comes from the recipe's own border, not from the
        margins.** ``border=min(margins)`` was this method's invention, and it
        collapses ``lbord`` to zero — i.e. "no clip area" — whenever the margins
        reach the clip width, on an i1 as readily as anywhere else. The engine
        builds the geometry from the recipe; so does this now, through the same
        call the renderer makes, which also means the CM/SS band width is
        derived in one place instead of two.
        """
        from workflow.layout_engine import instruments, papers
        if not self._clip_band_active():
            return None
        if self.instr is not None:
            inst, paper, _mode = self.selection()
        else:
            inst, paper = self._inst, self._preview_paper()
        try:
            r = self.apply_to_recipe(LayoutRecipe(instrument=inst, paper=paper))
            geom = instruments.geom_from_build_kwargs(r.build_kwargs())
            w_mm, h_mm = papers.dimensions_mm(paper)
        except Exception:      # noqa: BLE001 — a preview is never fatal
            return None
        if w_mm <= 0 or h_mm <= 0:
            return None
        return geom, h_mm, w_mm

    def _preview_paper(self) -> str:
        """The paper the clip preview measures against when this panel has no
        paper selector of its own (the Preferences copy, and the relayout
        dialog's).

        Those panels have no paper row, so the size comes from the last recipe
        loaded into them — which is the paper that recipe was written for. A4
        only when no recipe has ever been loaded. It used to be A4 always, so
        Preferences reported an A4 clip band to somebody working on A3.
        """
        return getattr(self, "_paper_hint", None) or "A4"

    @staticmethod
    def _pil_to_pixmap(img):
        from PyQt6.QtGui import QImage, QPixmap
        rgb = img.convert("RGB")
        data = rgb.tobytes("raw", "RGB")
        qimg = QImage(data, rgb.width, rgb.height, rgb.width * 3,
                      QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())

    def _preview_clip_image(self, max_px: int):
        """A downscaled copy of the clip image for the live preview, cached by
        (path, mtime, size) so dragging the rotate/scale/move spins stays smooth
        on a big file — generation still uses the full-resolution original (#93)."""
        path = self.clip_image_path.text().strip()
        if not path:
            return None
        try:
            from pathlib import Path as _P
            mtime = _P(path).stat().st_mtime
        except OSError:
            return None
        key = (path, mtime, int(max_px))
        if getattr(self, "_clip_img_cache_key", None) == key:
            return self._clip_img_cache
        try:
            from PIL import Image as _Img
            im = _Img.open(path).convert("RGBA")
            if max(im.width, im.height) > max_px:        # shrink for the preview
                sc = max_px / max(im.width, im.height)
                im = im.resize((max(1, int(im.width * sc)),
                                max(1, int(im.height * sc))))
            self._clip_img_cache_key, self._clip_img_cache = key, im
            return im
        except Exception:  # noqa: BLE001 — bad/missing image → blank preview
            self._clip_img_cache_key, self._clip_img_cache = key, None
            return None

    # Undoing setFixedHeight() needs the real ceiling back, not a guess.
    _PREVIEW_MAX_H = 16777215        # Qt's QWIDGETSIZE_MAX

    def _clear_clip_preview(self) -> None:
        """Empty the preview AND give it back its designed empty height.

        `setFixedHeight` (in `_refresh_clip_preview`) pins minimum == maximum
        for good, and `clear()` only drops the pixmap — so an emptied preview
        kept the height of whichever band was last drawn in it. The box was
        therefore 25 px after one recipe and 18 px after another, with nothing
        in it either time: its size was a record of what you had looked at
        before rather than of what it is showing. Restore the 90 px minimum the
        box is built with (line ~1456) so the empty state is always the same.
        """
        self.clip_preview.clear()
        self.clip_preview.setMinimumHeight(90)
        self.clip_preview.setMaximumHeight(self._PREVIEW_MAX_H)

    def resume_clip_preview(self) -> None:
        """End a `defer_clip_preview` window and draw the preview exactly once.

        Always call this from a `finally:` — a panel left suspended would show a
        stale preview for the rest of its life, which is a far worse bug than
        the slow build this exists to avoid.
        """
        if getattr(self, "_clip_batch_depth", 0) > 0:
            # Inside a batching window the redraw belongs to that window's exit,
            # which restores the flag this would clobber. Nothing does this
            # today; the guard is here so that adding a caller cannot quietly
            # break the one-redraw-per-load contract.
            return
        self._suspend_clip_preview = False
        self._refresh_clip_preview()

    def _refresh_clip_preview(self) -> None:
        if not hasattr(self, "clip_preview"):
            return
        # ONE RENDER PER LOAD, NOT THIRTY. Rebuilding this preview runs the
        # layout-engine geometry solver and a full raster of the strip — ~65 ms
        # a call. Loading a recipe sets every field in turn, and each one used to
        # re-render: `set_recipe()` alone cost 1.9 s and threw 29 of its 30
        # renders away. That is what made opening Preferences (which loads a
        # recipe into its Chart Layout panel) take ~1.9 s, and it cost the same
        # again on every preset load in Create Chart Manual and in the layout
        # editor, which share this panel.
        #
        # Skipping while `_loading` is safe because EVERY loading window is
        # closed by an unguarded `_emit()` with `_loading` back to False — the
        # consolidated refresh the tail of `set_recipe` already documents:
        #   * `_sync_extrahigh_defaults` : `_loading = False` then `_emit()`
        #   * `_on_instr_changed`        : `_loading = False` then
        #                                  `_on_paper_changed()` -> `_emit()`
        #   * `set_recipe`               : `_loading = False` then `_emit()`
        #     (no early return and no raise between, checked)
        # so the preview always ends up showing the recipe that was just loaded.
        # If you add a fourth window, it MUST end the same way.
        if getattr(self, "_loading", False):
            return
        # Explicit, caller-scoped suspension for a build that is about to load a
        # recipe anyway (see `resume_clip_preview`, which always ends the window
        # with exactly one render).
        if getattr(self, "_suspend_clip_preview", False):
            return
        from PyQt6.QtCore import Qt
        from workflow.layout_engine import geometry, raster
        gh = self._clip_geom_and_height()
        # The paper WIDTH matters: a right-side band is mirrored to the far edge
        # and `clip_area_mm` cannot place it without knowing how wide the sheet
        # is — and the ColorMunki family's own default puts the clip on the right.
        area = geometry.clip_area_mm(gh[0], gh[1], gh[2]) if gh else None
        if area is None:
            self.clip_dims_label.setText(tr("—"))
            self._clear_clip_preview()
            return
        _x, _y, w_mm, h_mm = area
        dpi = int(self.dpi.value())
        wp, hp = round(w_mm * dpi / 25.4), round(h_mm * dpi / 25.4)
        self.clip_dims_label.setText(
            tr("{w:.0f} × {h:.0f} mm  ({wp} × {hp} px @ {dpi} dpi)").format(
                w=w_mm, h=h_mm, wp=wp, hp=hp, dpi=dpi))
        mode = self.clip_content_mode.currentData()
        if mode == "off":
            self._clear_clip_preview()
            return
        pdpi = 220                  # render crisp, then scale down for display
        pw = max(1, round(w_mm * pdpi / 25.4))
        ph = max(1, round(h_mm * pdpi / 25.4))
        img = raster.render_clip_strip(
            mode, width_px=pw, height_px=ph, dpi=pdpi,
            text=self._resolve_sample(self.clip_text.toPlainText()),
            font_family=self.clip_text_font.currentData() or "Inter",
            image_path=self.clip_image_path.text().strip(),
            image_obj=self._preview_clip_image(max(pw, ph)) if mode == "image" else None,
            image_rotation=self.clip_image_rotation.value(),
            image_scale=self.clip_image_scale.value(),
            image_offset_x_mm=self.clip_image_offx.value(),
            image_offset_y_mm=self.clip_image_offy.value(),
            # The preview has to size the text exactly as the sheet will, or the
            # Size box appears to do nothing here and only shows its effect on
            # paper — which is how #163's shrunken branding went unnoticed.
            text_size_mm=pt_to_mm(self.clip_text_size.value()))
        # Show it lying down (rotated 90°) so the long strip uses the panel's
        # horizontal space instead of a thin vertical ribbon.
        img = img.rotate(-90, expand=True)
        pix = self._pil_to_pixmap(img)
        # Render at the screen's device-pixel ratio so it stays crisp on Retina
        # (a logical-size pixmap would be upscaled ×2 and look blurry).
        dpr = self.clip_preview.devicePixelRatioF() or 1.0
        avail = self.clip_preview.width()
        avail = min(max(avail if avail > 60 else 300, 120), 360)
        scaled = pix.scaledToWidth(round(avail * dpr),
                                   Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(dpr)
        self.clip_preview.setPixmap(scaled)
        self.clip_preview.setFixedHeight(round(scaled.height() / dpr) + 2)

    def _export_clip_template(self) -> None:
        from PyQt6.QtWidgets import QMessageBox
        from workflow.layout_engine import geometry, raster
        gh = self._clip_geom_and_height()
        area = geometry.clip_area_mm(gh[0], gh[1], gh[2]) if gh else None
        if area is None:
            return
        _x, _y, w_mm, h_mm = area
        dpi = int(self.dpi.value())
        from pathlib import Path as _P
        from ui.widgets import save_file_dialog
        # THE THIRD ARGUMENT IS QT'S FILE FILTER, NOT A LABEL. "Template base
        # name" was sitting in it, so the dialog filtered on the globs
        # "Template", "base" and "name" and listed nothing at all — the same
        # fault `ui/help_card_print.py` documents as fixed for the help card,
        # still live here. There IS no useful filter: what the user types is a
        # base name and `export_clip_template` writes both a .png and a .pdf
        # from it. So: no filter, and the label goes where the user reads it.
        base = save_file_dialog(
            self, tr("Export clip template"), "",
            start_path=str(_P.home() / "clip-template"))
        if not base:
            return
        w_px, h_px = round(w_mm * dpi / 25.4), round(h_mm * dpi / 25.4)
        # EXPORT WHAT THE PREVIEW SHOWS. The export used to write a blank design
        # canvas whatever the content was, so Knut's branding-plus-text came out
        # as a bare strip carrying only its own measurements (#164). Rendered
        # here through the same call the preview uses, at the real print size —
        # with the band switched off it still writes the blank canvas, which is
        # the case that canvas was made for.
        content = None
        if self.clip_content_mode.currentData() != "off":
            content = raster.render_clip_strip(
                self.clip_content_mode.currentData(),
                width_px=w_px, height_px=h_px, dpi=dpi,
                text=self._resolve_sample(self.clip_text.toPlainText()),
                font_family=self.clip_text_font.currentData() or "Inter",
                image_path=self.clip_image_path.text().strip(),
                image_rotation=self.clip_image_rotation.value(),
                image_scale=self.clip_image_scale.value(),
                image_offset_x_mm=self.clip_image_offx.value(),
                image_offset_y_mm=self.clip_image_offy.value(),
                text_size_mm=pt_to_mm(self.clip_text_size.value()))
        paths = raster.export_clip_template(
            base, width_px=w_px, height_px=h_px,
            width_mm=w_mm, height_mm=h_mm, dpi=dpi, content=content)
        QMessageBox.information(
            self, tr("Clip template exported"),
            tr("Wrote:\n{files}").format(files="\n".join(str(p) for p in paths)))

    def _sync_seed_enabled(self) -> None:
        on = self.randomize_cb.isChecked()
        self.fixed_seed_cb.setEnabled(on)
        self.new_seed_btn.setEnabled(on)
        self.seed_spin.setEnabled(on and self.fixed_seed_cb.isChecked())

    def _on_randomize_toggled(self, *_a) -> None:
        self._sync_seed_enabled()
        self._emit()

    def _on_fixed_seed_toggled(self, *_a) -> None:
        self._sync_seed_enabled()
        self._emit()

    def _on_new_seed(self) -> None:
        from workflow.layout_engine.permutation import pick_seed
        self.fixed_seed_cb.setChecked(True)   # a drawn seed is a reproducible one
        self.seed_spin.setValue(pick_seed())

    def _make_insert_button(self, target, *, multiline: bool = False):
        """A compact "Insert ▾" token menu that inserts into *target* (a QLineEdit
        or, when *multiline*, a QPlainTextEdit).

        Qt's own menu-indicator arrow is hidden so the single "▾" in the label
        is the only arrow (and stays aligned with the text).
        """
        btn = QToolButton(self)
        btn.setText(tr("Insert ▾"))
        btn.setObjectName("compact_input")
        btn.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0; }")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(btn)
        for tok, desc in SHEET_TOKENS:
            act = menu.addAction(f"{{{tok}}} — {desc}")
            act.triggered.connect(
                lambda _c=False, t=tok, tgt=target: self._insert_token_into(tgt, t))
        # Underline runs — a blank line to hand-write on (Knut). Insert several
        # in a row for a longer line; they join with no gap unless you type a
        # space between them.
        menu.addSeparator()
        for label, run in ((tr("Underline — long (10 “_”)"), "_" * 10),
                           (tr("Underline — short (5 “_”)"), "_" * 5)):
            act = menu.addAction(label)
            act.triggered.connect(
                lambda _c=False, r=run, tgt=target: self._insert_literal_into(tgt, r))
        # A newline — only for a multi-line target (the clip text), so a record
        # can be built line by line from the menu (Knut).
        if multiline:
            menu.addSeparator()
            act = menu.addAction(tr("New line"))
            act.triggered.connect(
                lambda _c=False, tgt=target: self._insert_literal_into(tgt, "\n"))
        btn.setMenu(menu)
        return btn

    @staticmethod
    def _style_swatch(btn) -> None:
        # min/max-width in the button's OWN stylesheet — the app QSS min-width
        # (for QPushButton / #compact_input) otherwise overrides setFixedSize and
        # blows the swatch row wide (feedback_qt_button_sizing).
        hexc = btn.property("hexcol") or "#ffffff"
        btn.setStyleSheet(
            f"QPushButton {{ background: {hexc}; border: 1px solid #888; "
            "border-radius: 3px; min-width: 22px; max-width: 26px; "
            "min-height: 18px; max-height: 22px; padding: 0; margin: 0; }")

    def _pick_spacer_colour(self, btn) -> None:
        from PyQt6.QtGui import QColor
        from PyQt6.QtWidgets import QColorDialog
        cur = QColor(btn.property("hexcol") or "#ffffff")
        # Non-native picker (hex field + RGB/HSV spinners), matching the editor's
        # patch / single-colour pickers — not the OS colour panel.
        col = QColorDialog.getColor(
            cur, self, tr("Spacer colour"),
            QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if col.isValid():
            btn.setProperty("hexcol", col.name())
            self._style_swatch(btn)
            self._emit()

    def set_spacer_override(self, flat: int, hexcol: "str | None") -> None:
        """Set (or clear, if *hexcol* is None) one spacer's manual colour and
        emit changed — used by the editor's click-to-recolour (#93)."""
        key = str(int(flat))
        if hexcol is None:
            self._spacer_overrides.pop(key, None)
        else:
            self._spacer_overrides[key] = hexcol
        self._emit()

    def _on_custom_spacer_toggled(self, *_a) -> None:
        self._sync_spacer_swatches()
        self._emit()

    def _sync_spacer_swatches(self, *_a) -> None:
        if not hasattr(self, "custom_spacer_cb"):
            return
        on = (self.custom_spacer_cb.isChecked()
              and (self.spacer_mode.currentData() or "colored") == "colored")
        for b in self._spacer_swatches:
            b.setEnabled(on)

    def _compact_browse(self, tooltip: str):
        """A magenta folder browse button sized like the targen -c browse
        (objectName browse_compact, 14px icon, 22px tall)."""
        from PyQt6.QtCore import QSize
        from ui.widgets import load_magenta_folder_icon, make_browse_button
        b = make_browse_button(self, tooltip)
        b.setIcon(load_magenta_folder_icon())
        b.setObjectName("browse_compact")
        b.style().unpolish(b)
        b.style().polish(b)
        b.setIconSize(QSize(14, 14))
        b.setFixedHeight(22)
        # Enforce the height in the button's OWN stylesheet too — when this panel
        # is embedded in the editor, the editor's controls QSS
        # (QPushButton { min-height: 26px }) cascades in and overrides
        # setFixedHeight; a per-widget rule has higher precedence (#93).
        b.setStyleSheet("QPushButton { min-height: 22px; max-height: 22px; "
                        "padding: 0px; margin: 0px; }")
        return b

    @staticmethod
    def _insert_at_cursor(target, text: str) -> None:
        """Insert *text* at the cursor of a QLineEdit OR a QPlainTextEdit."""
        if hasattr(target, "insertPlainText"):      # QPlainTextEdit (multi-line)
            target.insertPlainText(text)
        else:                                       # QLineEdit (single line)
            target.insert(text)
        target.setFocus()

    def _insert_token_into(self, target, token: str) -> None:
        """Drop ``{token}`` into *target* at the cursor."""
        self._insert_at_cursor(target, "{%s}" % token)

    def _insert_literal_into(self, target, text: str) -> None:
        """Drop literal *text* (e.g. an underline run or a newline) at the cursor."""
        self._insert_at_cursor(target, text)

    def _resolve_sample(self, text: str) -> str:
        """Fill *text*'s placeholders with representative values for preview —
        mirroring the human-readable values chart.build_chart produces."""
        import time
        from data.patch_db import PAPER_LABELS
        inst, paper = "i1", "A4"
        if self.instr is not None:
            inst, paper, _ = self.selection()
        _instr_friendly = {"i1": "i1Pro", "p3": "i1Pro3+", "CM": "ColorMunki",
                           "SS": "SpectroScan", "41": "DTP41", "51": "DTP51",
                           "CR30": "CR30"}
        _plabel = PAPER_LABELS.get(paper, paper)
        _pname = _plabel.split(" (")[0]
        _porient = (" landscape" if "Landscape" in _plabel
                    else " portrait" if "Portrait" in _plabel else "")
        _pages = self.get_pages()
        ctx = {
            "project": "MyChart", "page": f"page 1/{_pages}",
            "date": time.strftime("%Y-%m-%d"),
            "paper": f"{_pname}{_porient}",
            "instrument": _instr_friendly.get(inst, inst),
            "patchcount": "600 patches",
            "pages": str(_pages), "seed": "seed 12345",
            "dpi": f"{int(self.dpi.value())} dpi",
        }
        try:
            return text.format(**ctx)
        except (KeyError, IndexError, ValueError):
            return text       # unknown token — leave literal, as the builder does

    def _update_text_preview(self) -> None:
        if not hasattr(self, "text_preview"):
            return
        text = self.chart_text.text()
        self.text_preview.setText(self._resolve_sample(text) if text
                                  else tr("(no sheet text)"))

    def _add_font_rows(self, grid, r, label, combo, size, bold, italic,
                       tip=None) -> None:
        """Font on row *r*; Size + Bold + Italic on row *r+1*."""
        from PyQt6.QtCore import Qt
        grid.addWidget(QLabel(label, self), r, 0, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(combo, r, 1)
        if tip is not None:
            grid.addWidget(tip, r, 2)
        grid.addWidget(QLabel(tr("Size (pt):"), self), r + 1, 0, Qt.AlignmentFlag.AlignRight)
        wrap = QWidget(self)
        box = QHBoxLayout(wrap); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(8)
        box.addWidget(size); box.addWidget(bold); box.addWidget(italic); box.addStretch()
        grid.addWidget(wrap, r + 1, 1)
        grid.setColumnStretch(1, 1)
        combo.currentIndexChanged.connect(
            lambda: self._update_style_enabled(combo, bold, italic))
        self._update_style_enabled(combo, bold, italic)

    def _update_style_enabled(self, combo, bold, italic) -> None:
        """Grey Bold/Italic (box + label) when the chosen font lacks the style.

        Uses the engine's own capability probe so the checkbox can't promise a
        style the renderer won't actually apply.
        """
        from workflow.layout_engine.raster import font_supports
        has_bold, has_italic = font_supports(combo.currentData() or "")
        bold.setEnabled(has_bold)
        italic.setEnabled(has_italic)
        if not has_bold:
            bold.setChecked(False)
        if not has_italic:
            italic.setChecked(False)

    @staticmethod
    def _populate_font_combo(combo) -> None:
        """Bundled fonts on top, then a separator, then all installed families."""
        for fam in ("JetBrains Mono", "Inter", "Instrument Serif"):
            combo.addItem(fam, fam)
        combo.insertSeparator(combo.count())
        try:
            from PyQt6.QtGui import QFontDatabase
            for fam in QFontDatabase.families():
                combo.addItem(fam, fam)
        except Exception:
            pass
        from PyQt6.QtWidgets import QComboBox
        combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(12)

    def _on_show_indicators(self, on: bool) -> None:
        self.indicator_font.setEnabled(on)
        self.indicator_size.setEnabled(on)
        if on:
            self._update_style_enabled(self.indicator_font,
                                       self.ind_bold, self.ind_italic)
        else:
            self.ind_bold.setEnabled(False)
            self.ind_italic.setEnabled(False)
        self._sync_underline_enabled()
        self._emit()

    def _sync_underline_enabled(self) -> None:
        on = self.show_indicators.isChecked()
        self.underline_mode.setEnabled(on)
        active = on and self.underline_mode.currentData() != "off"
        self.underline_thickness.setEnabled(active)
        self.underline_gap.setEnabled(active)

    def _on_underline_changed(self, *_a) -> None:
        self._sync_underline_enabled()
        self._emit()

    def _on_rotation_changed(self, *_a) -> None:
        """Reading-axis alignment only matters for the side rotations (90°/270°);
        grey out the Left/Centered/Right checkboxes (and their labels) otherwise."""
        rot = int(self.indicator_rotation.currentData() or 0)
        active = rot in (90, 270)
        for cb in (self.ind_align_left, self.ind_align_center, self.ind_align_right):
            cb.setEnabled(active)
        self._emit()

    def _on_paper_changed(self, *_a) -> None:
        if self.paper is not None:
            self._custom_paper_w.setVisible(self.paper.currentData() == "__custom__")
        # Re-pull instrument margins for the new instrument/paper combo (#93).
        if hasattr(self, "use_instr_margins") and self.use_instr_margins.isChecked():
            self._sync_instr_margins()
        self._emit()

    def selection(self) -> tuple[str, str, str]:
        """(instrument, paper, mode) from the selectors (when present)."""
        if self.instr is None:
            return "i1", "A4", "default"
        paper = self.paper.currentData() or "A4"
        if paper == "__custom__":
            paper = f"{int(self.custom_w.value())}x{int(self.custom_h.value())}"
        return (self.instr.currentData() or "i1", paper,
                self.mode.currentData() or "default")

    def get_pages(self) -> int:
        return int(self.pages.value()) if self.pages is not None else 1

    def set_pages(self, n: int) -> None:
        if self.pages is not None:
            self.pages.setValue(max(1, int(n)))

    def set_pages_enabled(self, enabled: bool) -> None:
        """Grey the Pages control (spin + label) — used when an exact patch count
        is set, so the page count is fixed (#93)."""
        if self.pages is not None:
            self.pages.setEnabled(enabled)
        if getattr(self, "_pages_lbl", None) is not None:
            self._pages_lbl.setEnabled(enabled)

    def get_recipe(self, base: LayoutRecipe | None = None) -> LayoutRecipe:
        """Build a complete recipe from the selectors (if any) + the controls."""
        from workflow.layout_engine.presets import default_recipe
        if self.instr is not None:
            inst, paper, mode = self.selection()
            r = default_recipe(inst, paper, mode=mode)
        else:
            r = base if base is not None else LayoutRecipe()
        return self.apply_to_recipe(r)

    def _emit(self, *_a) -> None:
        self._update_text_preview()
        self._refresh_clip_preview()
        if not self._loading:
            self.changed.emit()

    def _update_helper_marker_rows(self, *_a) -> None:
        """Grey the three distances while the markers are switched off.

        The ⓘ buttons stay live: a user looking at a greyed row is exactly the
        one who wants to read what it would do (Knut's rule for the hexagonal
        case — greyed, but never unexplained).
        """
        on = bool(self.helper_markers_cb.isChecked())
        for row in getattr(self, "_hm_rows", []):
            for w in row:
                if isinstance(w, TooltipButton):
                    continue
                w.setEnabled(on)

    def _update_helper_marker_edge_warning(self, *_a) -> None:
        """Say it on the panel when the markers are on but no edge is ticked.

        "Print helper markers" ticked with both edges unticked prints nothing,
        and every distance box stays live and looks armed — a contradiction the
        user can only resolve by reading a tooltip. The preview says it too
        (the overlay goes into its "no markers next time" state), but the
        contradiction is made HERE, so the answer belongs here.
        """
        w = getattr(self, "helper_markers_edge_warning", None)
        if w is None:
            return
        on = bool(self.helper_markers_cb.isChecked())
        none_ticked = not (self.helper_markers_top_bottom.isChecked()
                           or self.helper_markers_sides.isChecked())
        if on and none_ticked:
            w.setText(tr("No dashes will be printed — tick at least one edge "
                         "above, or turn the markers off."))
            w.setVisible(True)
        else:
            w.setText("")
            w.setVisible(False)

    def set_helper_markers_supported(self, supported: bool,
                                     reason: str = "") -> None:
        """Grey the ruler-marker controls out when the chart cannot carry them.

        A hexagonal SpectroScan chart is a honeycomb — it has no rows to lay a
        ruler against, so the dashes are meaningless there and the engine draws
        none. Knut asked (#152) for the reason to be readable rather than the
        box simply going dead, so it goes on the group and on every control
        inside it, which is what a hover reaches.
        """
        grp = getattr(self, "_helper_markers_grp", None)
        if grp is None:
            return
        grp.setEnabled(bool(supported))
        tip = "" if supported else (reason or tr(
            "This chart's patches are hexagons, which have no rows to lay a "
            "ruler against — so helper markers cannot be printed on it."))
        for w in (grp, self.helper_markers_cb, self.helper_marker_edge,
                  self.helper_marker_len, self.helper_marker_per_patch,
                  self.helper_markers_top_bottom, self.helper_markers_sides):
            w.setToolTip(tip)
        if supported:
            self._update_helper_marker_rows()

    @contextmanager
    def _clip_preview_batched(self):
        """Draw the clip preview at most ONCE for everything done inside.

        Nests safely: an inner window leaves the redraw to the outer one, and an
        outer window that is itself a caller's `defer_clip_preview` leaves it to
        `resume_clip_preview`. The redraw is in a `finally:` so an exception
        cannot strand the panel suspended.
        """
        prev = getattr(self, "_suspend_clip_preview", False)
        self._suspend_clip_preview = True
        self._clip_batch_depth = getattr(self, "_clip_batch_depth", 0) + 1
        try:
            yield
        finally:
            self._clip_batch_depth -= 1
            self._suspend_clip_preview = prev
            if not prev:
                self._refresh_clip_preview()

    def set_recipe(self, r: LayoutRecipe) -> None:
        """Load *r* into every control, redrawing the clip preview once.

        Loading touches ~60 controls, and each change used to redraw the strip —
        three surviving redraws even after the `_loading` guard, because
        `_on_instr_changed` closes its own loading window part way through. One
        batching window around the whole load makes it one.
        """
        with self._clip_preview_batched():
            try:
                self._set_recipe_impl(r)
            finally:
                # A HALF-DONE LOAD MUST NOT KILL THE PANEL. `_set_recipe_impl`
                # clears `_loading` on its last line only, so a raise part way
                # through left it True for ever — and both the clip preview and
                # the `changed` signal are gated on it, so the preview froze on
                # the PREVIOUS recipe and the panel went silent. A preset file
                # with a null `dpi` is enough (`QSpinBox.setValue(None)` raises
                # TypeError), and the layout editor catches that exception and
                # carries on (`ti2_relayout_dialog.py:5372`, `:5419`) — so the
                # user would be left designing against a picture of the chart
                # they had open before.
                self._loading = False

    def _set_recipe_impl(self, r: LayoutRecipe) -> None:
        # WHO OVERWROTE THE PANEL? Sebastian watched his spacer and gap
        # settings revert a second after Generate Chart (2026-08-13), and
        # neither a headless harness nor the app driven on screen reproduced
        # it — so the trigger lives in a real session's own state. This line
        # turns the next occurrence into evidence: every write to the panel is
        # logged with the values and the caller that made it, at DEBUG, where
        # the rest of the diagnosis already looks.
        try:
            import traceback
            # -5:-2, not -4:-1: `set_recipe` now wraps this method, so the
            # innermost frame is always `set_recipe` itself and would eat one of
            # the three caller slots this line exists to record.
            caller = "  ←  ".join(
                f"{f.name}:{f.lineno}" for f in traceback.extract_stack()[-5:-2])
            log.debug("layout panel set_recipe: spacer=%s/%s gaps=%s/%s  [%s]",
                      r.spacer_mode, r.spacer_on, r.inter_patch_mm,
                      r.strip_gap_mm, caller)
        except Exception:      # noqa: BLE001 — diagnostics never break the UI
            pass
        # The ruler helper markers are ordinary controls in this panel since
        # #158 — they used to be carried as plain state because their widgets
        # lived under the preview, and that split is exactly what let a loaded
        # preset show the wrong tick (Basti, 2026-08-16).
        self.helper_markers_cb.setChecked(bool(getattr(r, "helper_markers", False)))
        self.helper_marker_edge.setValue(
            float(getattr(r, "helper_marker_edge_mm", 2.0)))
        self.helper_marker_len.setValue(
            float(getattr(r, "helper_marker_len_mm", 2.0)))
        self.helper_marker_per_patch.setValue(
            int(getattr(r, "helper_marker_per_patch", 3) or 3))
        self.helper_markers_top_bottom.setChecked(
            bool(getattr(r, "helper_markers_top_bottom", True)))
        self.helper_markers_sides.setChecked(
            bool(getattr(r, "helper_markers_sides", True)))
        self._update_helper_marker_rows()
        self._loading = True
        if self.instr is not None:
            ii = self.instr.findData(r.instrument)
            self.instr.setCurrentIndex(ii if ii >= 0 else 0)
            self._on_instr_changed()
            self._loading = True
            pi = self.paper.findData(r.paper)
            if pi >= 0:
                self.paper.setCurrentIndex(pi)
            else:
                from workflow.layout_engine import papers
                dims = papers.parse_custom(r.paper)
                ci = self.paper.findData("__custom__")
                if dims and ci >= 0:
                    self.paper.setCurrentIndex(ci)
                    self.custom_w.setValue(dims[0])
                    self.custom_h.setValue(dims[1])
            self._custom_paper_w.setVisible(self.paper.currentData() == "__custom__")
            mi = self.mode.findData(r.mode())
            if mi >= 0:
                self.mode.setCurrentIndex(mi)
        self.pscale.setValue(r.pscale)
        self.sscale.setValue(r.sscale)
        i = self.spacer_mode.findData(r.spacer_mode)
        self.spacer_mode.setCurrentIndex(i if i >= 0 else 0)
        self.spacer_width.setValue(r.spacer_width_mm)
        self.edge_spacers_cb.setChecked(bool(r.edge_spacers))
        self.cm_stagger_cb.setChecked(bool(getattr(r, "cm_stagger", False)))
        self._spacer_overrides = {str(k): v for k, v in (r.spacer_overrides or {}).items()}
        _pal = list(r.spacer_palette or [])
        self.custom_spacer_cb.setChecked(bool(_pal))
        for _i, _b in enumerate(self._spacer_swatches):
            if _i < len(_pal):
                _b.setProperty("hexcol", _pal[_i])
                self._style_swatch(_b)
        self._sync_spacer_swatches()
        _lm = self.layout_mode.findData(r.layout_mode or "patch_first")
        self.layout_mode.setCurrentIndex(_lm if _lm >= 0 else 0)
        _am = self.area_method.findData(r.area_method or "by_width")
        self.area_method.setCurrentIndex(_am if _am >= 0 else 0)
        self.area_cols.setValue(int(r.area_cols or 0))
        self.area_rows.setValue(int(r.area_rows or 0))
        # frac → %; an old 0.0 ("square") maps to 100 % (same height = width).
        self.area_ratio.setValue((float(r.area_ratio) or 1.0) * 100.0)
        self.area_min_patch.setValue(float(r.area_min_patch_mm or 0.0))
        self._sync_layout_mode()
        self.patch_x.setValue(r.patch_w_mm)
        self.patch_y.setValue(r.patch_h_mm)
        self.inter_patch.setValue(r.inter_patch_mm)
        self.strip_gap.setValue(r.strip_gap_mm)
        self.sig.setValue(r.strip_indicator_gap_mm)
        self.margins["t"].setValue(r.margin_top)
        self.margins["r"].setValue(r.margin_right)
        self.margins["b"].setValue(r.margin_bottom)
        self.margins["l"].setValue(r.margin_left)
        if hasattr(self, "use_instr_margins"):
            self.use_instr_margins.blockSignals(True)
            self.use_instr_margins.setChecked(bool(getattr(
                r, "use_instrument_margins", False)))
            self.use_instr_margins.blockSignals(False)
            self._sync_instr_margins()     # fill from thresholds when ticked
        self._border = r.border        # preserve base margin across the round-trip
        self.dpi.setValue(r.dpi)
        self.nolimit.setChecked(r.nolimit)
        self.max_strip.setValue(r.max_strip_mm)
        self.offx.setValue(r.offset_x_mm)
        self.offy.setValue(r.offset_y_mm)
        self.strip_pat.setText(r.strip_pattern)
        self.patch_pat.setText(r.patch_pattern)
        _ai = self.patch_align.findData(r.patch_area_align or "center-left")
        self.patch_align.setCurrentIndex(_ai if _ai >= 0 else
                                         self.patch_align.findData("center-left"))
        self.bit_depth.setCurrentIndex(1 if r.bit16 else 0)
        self.export_pdf.setChecked(r.export_pdf)
        self.show_indicators.setChecked(r.show_strip_indicators)
        _fi = self.indicator_font.findData(r.indicator_font)
        self.indicator_font.setCurrentIndex(_fi if _fi >= 0 else 0)
        self.indicator_size.setValue(mm_to_pt(r.indicator_size_mm))
        self.ind_bold.setChecked(r.indicator_bold)
        self.ind_italic.setChecked(r.indicator_italic)
        _rot = self.indicator_rotation.findData(int(r.indicator_rotation))
        self.indicator_rotation.setCurrentIndex(_rot if _rot >= 0 else 0)
        _align = {"left": self.ind_align_left, "center": self.ind_align_center,
                  "right": self.ind_align_right}.get(r.indicator_align,
                                                     self.ind_align_left)
        _align.setChecked(True)
        self.strip_label_offset.setValue(r.strip_label_offset_mm)
        self._on_rotation_changed()      # grey out align unless 90°/270°
        _umkey = "segments" if r.underline_mode == "colored" else r.underline_mode
        _um = self.underline_mode.findData(_umkey)
        self.underline_mode.setCurrentIndex(_um if _um >= 0 else 0)
        self.underline_thickness.setValue(r.underline_thickness_mm)
        self.underline_gap.setValue(r.underline_gap_mm)
        self._sync_underline_enabled()
        self.chart_text.setText(r.chart_text)
        _ctf = self.chart_text_font.findData(r.chart_text_font)
        self.chart_text_font.setCurrentIndex(_ctf if _ctf >= 0 else 0)
        self.chart_text_size.setValue(mm_to_pt(r.chart_text_size_mm))
        self.text_edge.setValue(getattr(r, "text_edge_mm", 4.0) or 4.0)
        self.text_edge_top.setValue(getattr(r, "text_edge_top_mm", 4.0) or 4.0)
        self.text_edge_clip.setValue(getattr(r, "text_edge_clip_mm", 4.0) or 4.0)
        self.ct_bold.setChecked(r.chart_text_bold)
        self.ct_italic.setChecked(r.chart_text_italic)
        self.stamp_command.setChecked(r.stamp_command)
        ci = self.compression.findData(r.compression)
        self.compression.setCurrentIndex(ci if ci >= 0 else 0)
        self.clip_width.setValue(r.clip_border_width_mm or 26.0)
        _cc = self.clip_content_mode.findData(r.clip_content_mode)
        self.clip_content_mode.setCurrentIndex(_cc if _cc >= 0 else 0)
        _cs = self.clip_side.findData(getattr(r, "clip_side", "left") or "left")
        self.clip_side.setCurrentIndex(_cs if _cs >= 0 else 0)
        self.clip_flip_180.setChecked(bool(getattr(r, "clip_flip_180", False)))
        self.clip_text.setPlainText(r.clip_text)
        _cf = self.clip_text_font.findData(r.clip_text_font)
        self.clip_text_font.setCurrentIndex(_cf if _cf >= 0 else 0)
        self.clip_text_size.setValue(mm_to_pt(r.clip_text_size_mm))
        self.clip_image_path.setText(r.clip_image_path)
        self.clip_image_rotation.setValue(int(getattr(r, "clip_image_rotation", 0) or 0))
        self.clip_image_scale.setValue(float(getattr(r, "clip_image_scale", 100.0) or 100.0))
        self.clip_image_offx.setValue(float(getattr(r, "clip_image_offset_x_mm", 0.0) or 0.0))
        self.clip_image_offy.setValue(float(getattr(r, "clip_image_offset_y_mm", 0.0) or 0.0))
        self._sync_clip_content_enabled()
        self._sync_clip_enable_display()
        self.randomize_cb.setChecked(r.randomize)
        _fixed = r.seed is not None
        self.fixed_seed_cb.setChecked(_fixed)
        if _fixed:
            self.seed_spin.setValue(int(r.seed))
        self._sync_seed_enabled()
        self._inst, self._clip = r.instrument, r.clip_border
        # …and the paper it was written for, so a panel with no paper selector
        # measures its clip band against the right sheet (see _preview_paper).
        self._paper_hint = getattr(r, "paper", None) or None
        self._update_clip_visibility()
        # Gate the instrument-specific controls (cm_stagger / clip_enable) for the
        # loaded instrument. This is the ONLY place it happens for the embedded
        # Preferences → Chart Layout panel (no instr combo of its own, driven by
        # set_recipe) — without it "Offset every second strip" showed for every
        # instrument there, not just the ColorMunki (Knut).
        self._sync_instrument_widgets(r.instrument)
        self._loading = False
        # Final pass with loading off: computes the real conflict state for
        # the values just loaded (during loading only the clean-up runs).
        self._update_clip_margin_conflict()
        # One consolidated refresh now that loading is off: every field above was
        # set with change-signals suppressed, so without this the text/clip
        # previews and any listener (the layout editor's render preview) kept
        # showing the PREVIOUS recipe — a freshly loaded preset showed the old
        # clip content and strip/patch layout until a field was toggled by hand
        # (Knut #130 beta-2 test #1). _emit refreshes both previews and fires the
        # panel's `changed` signal exactly as an interactive edit would.
        self._emit()

    def apply_to_recipe(self, r: LayoutRecipe) -> LayoutRecipe:
        """Write the panel's values onto *r* (keeps r's instrument/paper/mode)."""
        # THE RULER MARKERS HAVE NO CONTROL HERE, AND STILL BELONG TO THE RECIPE.
        #
        # Their checkbox lives in the preview's "Measure from Preview" panel,
        # because that is where you look while judging where the dashes land —
        # but they are printed onto the sheet, so the layout recipe is what has
        # to carry them to the renderer. This panel rebuilds the recipe from
        # scratch on every `get_recipe()`, so anything it does not know about is
        # silently dropped on the way to Generate Chart: that is why ticking the
        # box produced no markers at all (Knut, beta.3 of 4.0.2, #152 — *"Enabling
        # 'Show helper markers…' checkbox does nothing"*). Holding the three
        # values as plain state, set by `set_recipe` and written back here, makes
        # the round-trip lossless without putting a duplicate control on screen.
        r.helper_markers = bool(self.helper_markers_cb.isChecked())
        r.helper_marker_edge_mm = float(self.helper_marker_edge.value())
        r.helper_marker_len_mm = float(self.helper_marker_len.value())
        r.helper_marker_per_patch = int(self.helper_marker_per_patch.value())
        r.helper_markers_top_bottom = bool(
            self.helper_markers_top_bottom.isChecked())
        r.helper_markers_sides = bool(self.helper_markers_sides.isChecked())
        r.pscale = self.pscale.value()
        r.sscale = self.sscale.value()
        r.spacer_mode = self.spacer_mode.currentData() or "colored"
        r.spacer_palette = ([b.property("hexcol") for b in self._spacer_swatches]
                            if self.custom_spacer_cb.isChecked() else [])
        r.spacer_overrides = dict(self._spacer_overrides)
        r.spacer_on = r.spacer_mode != "none"
        r.edge_spacers = self.edge_spacers_cb.isChecked()
        r.cm_stagger = self.cm_stagger_cb.isChecked()
        r.spacer_width_mm = self.spacer_width.value()
        r.layout_mode = self.layout_mode.currentData() or "patch_first"
        r.area_method = self.area_method.currentData() or "by_width"
        r.area_cols = int(self.area_cols.value())
        r.area_rows = int(self.area_rows.value())
        r.area_ratio = float(self.area_ratio.value()) / 100.0          # % → frac
        r.area_min_patch_mm = float(self.area_min_patch.value())
        r.patch_w_mm = self.patch_x.value()
        r.patch_h_mm = self.patch_y.value()
        r.inter_patch_mm = self.inter_patch.value()
        r.strip_gap_mm = self.strip_gap.value()
        r.strip_indicator_gap_mm = self.sig.value()
        r.margin_top = self.margins["t"].value()
        r.margin_right = self.margins["r"].value()
        r.margin_bottom = self.margins["b"].value()
        r.margin_left = self.margins["l"].value()
        if hasattr(self, "use_instr_margins"):
            r.use_instrument_margins = self.use_instr_margins.isChecked()
        # Preserve the chart's base margin (printtarg -m; drives the clip-holder
        # width lbord = clip_width − border). The panel has no separate control
        # for it, so re-deriving it from min(margins) silently changed it on a
        # round-trip (e.g. 10→6), shifting the layout right and dropping strips
        # in the editor. Keep the loaded value; new recipes default it to 6. (#93)
        r.border = self._border
        r.dpi = int(self.dpi.value())
        r.nolimit = self.nolimit.isChecked()
        r.max_strip_mm = self.max_strip.value()
        r.offset_x_mm = self.offx.value()
        r.offset_y_mm = self.offy.value()
        r.strip_pattern = self.strip_pat.text() or r.strip_pattern
        r.patch_pattern = self.patch_pat.text() or r.patch_pattern
        r.patch_area_align = self.patch_align.currentData() or "center-left"
        r.bit16 = (self.bit_depth.currentData() == 16)
        r.export_pdf = self.export_pdf.isChecked()
        r.show_strip_indicators = self.show_indicators.isChecked()
        r.indicator_font = self.indicator_font.currentData() or "JetBrains Mono"
        r.indicator_size_mm = pt_to_mm(self.indicator_size.value())
        r.indicator_bold = self.ind_bold.isChecked()
        r.indicator_italic = self.ind_italic.isChecked()
        r.indicator_rotation = int(self.indicator_rotation.currentData() or 0)
        r.indicator_align = ("center" if self.ind_align_center.isChecked()
                             else "right" if self.ind_align_right.isChecked()
                             else "left")
        r.strip_label_offset_mm = self.strip_label_offset.value()
        r.underline_mode = self.underline_mode.currentData() or "off"
        r.underline_thickness_mm = self.underline_thickness.value()
        r.underline_gap_mm = self.underline_gap.value()
        r.chart_text = self.chart_text.text()
        r.chart_text_font = self.chart_text_font.currentData() or "Inter"
        r.chart_text_size_mm = pt_to_mm(self.chart_text_size.value())
        r.text_edge_mm = self.text_edge.value()
        r.text_edge_top_mm = self.text_edge_top.value()
        r.text_edge_clip_mm = self.text_edge_clip.value()
        r.chart_text_bold = self.ct_bold.isChecked()
        r.chart_text_italic = self.ct_italic.isChecked()
        r.stamp_command = self.stamp_command.isChecked()
        r.compression = self.compression.currentData() or "lzw"
        r.clip_border_width_mm = self.clip_width.value()
        r.clip_content_mode = self.clip_content_mode.currentData() or "off"
        r.clip_side = self.clip_side.currentData() or "left"
        r.clip_flip_180 = self.clip_flip_180.isChecked()
        r.clip_text = self.clip_text.toPlainText()
        r.clip_text_font = self.clip_text_font.currentData() or "Inter"
        r.clip_text_size_mm = pt_to_mm(self.clip_text_size.value())
        r.clip_image_path = self.clip_image_path.text().strip()
        r.clip_image_rotation = self.clip_image_rotation.value()
        r.clip_image_scale = self.clip_image_scale.value()
        r.clip_image_offset_x_mm = self.clip_image_offx.value()
        r.clip_image_offset_y_mm = self.clip_image_offy.value()
        r.randomize = self.randomize_cb.isChecked()
        r.seed = (int(self.seed_spin.value())
                  if r.randomize and self.fixed_seed_cb.isChecked() else None)
        return r
