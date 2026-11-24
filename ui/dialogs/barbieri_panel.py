"""Manual's layout panel for the Barbieri Spectro 100xy (a Beta).

`ui.dialogs.layout_options_panel.LayoutOptionsPanel` calls these methods
through thin delegations (`_barbieri_call`), importing this module only while
the Beta "Barbieri Spectro 100xy" is on. Off, nothing here is imported, built
or called, so the panel is the one it was before, widget for widget
(`tests/test_barbieri_off_changes_nothing.py`).

On (and the Barbieri chosen):

* the group "Barbieri Spectro 100xy chart (Beta)" shows the chart's own
  options: the ready-made sizes, the measuring opening, the check patches and
  the corner marks;
* the controls that have no meaning for a chart read by coordinates are
  greyed, each tooltip starting with its own reason, and get their values
  back when another instrument is chosen (checklist 3.5): spacers and edge
  spacers, the patch scale, the layout mode (the chart is laid out patch
  size first, so Spectro32 gets one pitch in 0.1 mm steps), offset strips and
  hexagons, the strip-length switch and the ruler helper markers;
* the patch size boxes step in 0.1 mm, the table's own step;
* everything else stays open, as for the other instruments: the margins, the
  patch size, the gaps between patches and between columns, the labels, the
  alignment, the offsets, the clip border and the output.
"""
from __future__ import annotations

from core.i18n import tr


def barbieri_greyed_why() -> dict:
    """Why each greyed control is greyed for a Barbieri chart (by key)."""
    return {
        "spacers": tr("The Spectro 100xy moves its head to the centre of "
                      "every patch; it never looks for the edge between two "
                      "patches, so a Barbieri chart has no spacers. The gaps "
                      "between patches and between columns stay open."),
        "scale": tr("No base patch size to scale for this instrument: set the "
                    "patch size directly (it steps in 0.1 mm, the table's own "
                    "step)."),
        "mode": tr("A Barbieri chart is laid out patch size first, so "
                   "Spectro32 gets one pitch in whole 0.1 mm steps. The "
                   "ready-made sizes in the group “Barbieri Spectro 100xy "
                   "chart (Beta)” fill the common areas."),
        "shape": tr("Spectro32 and Gateway read a rectangular grid with one "
                    "pitch across and one down, so offset strips and "
                    "hexagons cannot be read."),
        "nolimit": tr("No ruler: the page and the margins decide the rows of "
                      "a Barbieri chart; use “Max strip length” to ask for "
                      "fewer rows."),
        "markers": tr("No ruler: the corner marks and the aim ticks are the "
                      "marks a Barbieri chart needs, and they are drawn by "
                      "themselves (group “Barbieri Spectro 100xy chart "
                      "(Beta)”)."),
    }


def barbieri_greyed_reason(why: str = "") -> str:
    own = barbieri_greyed_why().get(why, "")
    general = tr("The Barbieri Spectro 100xy chart (Beta) is a plain grid "
                 "read by coordinates; its own options are in the group "
                 "“Barbieri Spectro 100xy chart (Beta)”.")
    return (own + "\n\n" + general) if own else general


#: Each greyed control by attribute name, with its reason key.
BARBIERI_GREYED = {
    **dict.fromkeys(("spacer_mode", "spacer_width", "custom_spacer_cb",
                     "edge_spacers_cb"), "spacers"),
    **dict.fromkeys(("pscale", "sscale"), "scale"),
    "layout_mode": "mode",
    **dict.fromkeys(("cm_stagger_cb", "hex_flat_top_cb"), "shape"),
    "nolimit": "nolimit",
    **dict.fromkeys(("helper_markers_cb", "helper_marker_edge",
                     "helper_marker_len", "helper_marker_per_patch",
                     "helper_markers_top_bottom", "helper_markers_sides"),
                    "markers"),
}


def head_choice_label(key: str) -> str:
    from workflow.barbieri.chart import head_label
    from workflow.barbieri.chart_facts import HEADS
    return head_label(HEADS[key])


def fill_head_combo(combo) -> None:
    """The measuring openings, in the datasheets' order (Guided and Manual)."""
    from workflow.barbieri.chart_facts import HEAD_ORDER
    for key in HEAD_ORDER:
        combo.addItem(head_choice_label(key), key)


def size_label(key: str) -> str:
    """A ready-made size as the choice lists it (translated)."""
    return {
        "a4": tr("A4 landscape, one pass (3 mm, 6.5 mm patches)"),
        "letter": tr("Letter landscape, one pass (3 mm, 6.5 mm patches)"),
        "standard": tr("Barbieri standard area 225 x 180 mm (7.5 mm "
                       "patches)"),
        "full": tr("Full reading area 235 x 200 mm (6.5 mm patches)"),
        "film_large": tr("Film frame 9.25 x 7.75 in (3 mm transmission, "
                         "6.5 mm patches)"),
        "film_35": tr("35 mm film frame, 4096 x 2730 px at 2731 ppi "
                      "(0.5 mm, 1 mm patches)"),
    }.get(key, key)


def barbieri_option_help(which: str) -> str:
    """The (i) of each control in the Barbieri group (and Guided's opening)."""
    return {
        "head": tr(
            "The measuring opening you read with, and whether the chart is a "
            "sheet read by reflection or a film read by transmission. It "
            "gives the patch size a new chart starts with: 6.5 mm for the 3 mm "
            "opening (an owner read 896 such patches in one run), 1 mm for the "
            "0.5 mm opening (an owner's suggestion, not yet tried), 10 mm for "
            "the 6 mm opening of the second model (not yet tried). Spectro32 "
            "names the three it knows MR (3 mm reflection), MT (3 mm "
            "transmission) and M5 (0.5 mm transmission). Any patch size can "
            "be typed; one smaller than the opening with 0.25 mm of room on "
            "each side is warned about, never refused. **Default:** 3 mm, "
            "reflection."),
        "size": tr(
            "Ready-made sizes that suit this instrument. Picking one fills "
            "the paper, the margins, the patch size and the measuring opening "
            "(and for the film frames the page in inches or pixels and the "
            "resolution); every value stays yours to change, and it is saved "
            "like anything you type.\n"
            "  •  A4 and Letter, one pass: landscape sheets whose patch area "
            "fits the reading area of the datasheets, the 15 mm left border "
            "included.\n"
            "  •  Barbieri standard area: 225 x 180 mm, the patch area of most "
            "charts Barbieri's own Gateway ships with.\n"
            "  •  Full reading area: as much of the 235 x 200 mm the datasheets "
            "give as whole 6.5 mm patches fill.\n"
            "  •  The two film frames, for a film recorder: they need the Beta "
            "“Custom page size in inches or pixels, and high resolution” in "
            "Preferences > Beta.\n"
            "The 235 x 200 mm reading area comes from Barbieri's datasheets of "
            "2002 to 2004; ChromIQ does not limit a chart to it, as your table "
            "may read more. **Default:** none (your own size)."),
        "check": tr(
            "Moves a few of the chart's own patches to fixed places on every "
            "page: the darkest at A1, the most colourful at the upper-right "
            "patch (the one Spectro32 is aimed at), the lightest at the "
            "lower-left patch, and two clearly different colours right of and "
            "below A1. Only positions change: the patches and their number "
            "stay the same. When the measurement is brought back (a later "
            "version), these places show whether the sheet or film lay "
            "mirrored, upside down, turned or one patch off. Not on a "
            "calibration chart whose ramps each take a column: a ramp shows "
            "the way the sheet lay by itself. **Default:** on."),
        "marks": tr(
            "Marks in the margins, never on a patch: at the four outer "
            "corners of the patch grid on every page (Gateway is aimed at "
            "three of them), the upper-right one bold; two thin ticks that "
            "continue the first row and the last column so they cross at the "
            "centre of the upper-right patch, where Spectro32 is aimed; and a "
            "small square left of A1, the first patch read. A margin too "
            "narrow for a mark leaves that side's marks out, and the log says "
            "so. **Default:** on."),
        "left": tr(
            "A reflective sheet needs free paper on its left for the table. "
            "Barbieri's datasheets disagree on how much: 15 mm (the 2003 web "
            "page and the Italian and French sheets) or 35 mm (the English and "
            "German sheet of 2004). New charts start with 15 mm; make the left "
            "margin wider if your table needs it."),
    }.get(which, "")


class BarbieriPanelMixin:
    """The Barbieri parts of `LayoutOptionsPanel` (only while the Beta is on)."""

    # ---- the group ---------------------------------------------------------

    def _barbieri_build_group(self, parent_layout) -> None:
        """Build "Barbieri Spectro 100xy chart (Beta)" (hidden until the
        Barbieri is chosen)."""
        from PyQt6.QtGui import QStandardItemModel
        from PyQt6.QtWidgets import QCheckBox, QGridLayout, QGroupBox, QLabel
        from ui.tooltip_button import TooltipButton
        from ui.widgets import ElidingComboBox, FullTextComboBox
        g = QGroupBox(tr("Barbieri Spectro 100xy chart (Beta)"), self)
        grid = QGridLayout(g)
        grid.setColumnStretch(1, 1)
        row = 0

        def put(label, control, which, tip_title="", wide=False):
            nonlocal row
            if wide:
                # the name is long: label and help button on one line, the
                # box under them across the whole group (item 46)
                grid.addWidget(QLabel(label, g), row, 0, 1, 2)
                grid.addWidget(TooltipButton(
                    tip_title or label.rstrip(":"),
                    barbieri_option_help(which), g, min_width=560), row, 2)
                row += 1
                grid.addWidget(control, row, 0, 1, 3)
                row += 1
                return
            if label:
                grid.addWidget(QLabel(label, g), row, 0)
                grid.addWidget(control, row, 1)
            else:
                grid.addWidget(control, row, 0, 1, 2)
            grid.addWidget(TooltipButton(
                tip_title or (label.rstrip(":") if label else control.text()),
                barbieri_option_help(which), g, min_width=560), row, 2)
            row += 1

        from workflow.barbieri.chart import SIZE_PRESETS
        from workflow.page_output.support import page_output_enabled
        self.barbieri_size = FullTextComboBox(g)
        self.barbieri_size.addItem(tr("Your own size"), "")
        for p in SIZE_PRESETS:
            self.barbieri_size.addItem(size_label(p.key), p.key)
        model = self.barbieri_size.model()
        if isinstance(model, QStandardItemModel) and not page_output_enabled():
            for i in range(self.barbieri_size.count()):
                from workflow.barbieri.chart import size_preset
                p = size_preset(self.barbieri_size.itemData(i))
                if p is not None and p.needs_page_beta:
                    item = model.item(i)
                    item.setEnabled(False)
                    from workflow.barbieri.chart import \
                        film_needs_page_beta_reason
                    item.setToolTip(film_needs_page_beta_reason())
        put(tr("Ready-made size:"), self.barbieri_size, "size", wide=True)
        self.barbieri_head = ElidingComboBox(g)
        fill_head_combo(self.barbieri_head)
        put(tr("Measuring opening:"), self.barbieri_head, "head")
        self.barbieri_check = QCheckBox(tr("Check patches at the corners"), g)
        self.barbieri_check.setChecked(True)
        put("", self.barbieri_check, "check")
        self.barbieri_marks = QCheckBox(tr("Corner marks and aim ticks"), g)
        self.barbieri_marks.setChecked(True)
        put("", self.barbieri_marks, "marks")
        note = QLabel(tr("Left border for a reflective sheet: 15 mm or "
                         "more."), g)
        note.setWordWrap(True)
        put("", note, "left", tip_title=tr("Left border"))
        self.barbieri_size.activated.connect(self._barbieri_size_picked)
        for w, sig in ((self.barbieri_head, "currentIndexChanged"),
                       (self.barbieri_check, "toggled"),
                       (self.barbieri_marks, "toggled")):
            getattr(w, sig).connect(self._barbieri_option_changed)
        self.barbieri_head.currentIndexChanged.connect(
            self._barbieri_head_changed)
        # A READY-MADE SIZE IS A RECORD OF WHERE THE VALUES CAME FROM, so a
        # person's change to one of them makes the size their own again
        # (review N2): the choice shows "Your own size" and the side file
        # names no ready-made size
        edited = [(self.barbieri_head, "currentIndexChanged")]
        edited += [(b, "valueChanged") for b in (
            getattr(self, "patch_x", None), getattr(self, "patch_y", None),
            getattr(self, "dpi", None),
            getattr(self, "inter_patch", None),
            getattr(self, "strip_gap", None)) if b is not None]
        edited += [(b, "valueChanged")
                   for b in (getattr(self, "margins", None) or {}).values()]
        if getattr(self, "paper", None) is not None:
            edited.append((self.paper, "currentIndexChanged"))
        for w, sig in edited:
            getattr(w, sig).connect(self._barbieri_values_edited)
        self._barbieri_applying = False
        g.setVisible(False)
        self._barbieri_group = g
        self._barbieri_saved = None
        self._barbieri_head_was = self.barbieri_head.currentData()
        parent_layout.addWidget(g)

    def _barbieri_option_changed(self, *_a) -> None:
        if not getattr(self, "_loading", False):
            self._emit()

    def _barbieri_values_edited(self, *_a) -> None:
        """A value a ready-made size fills was changed by a person: the size
        is the person's own from now on."""
        if (getattr(self, "_loading", False)
                or getattr(self, "_barbieri_applying", False)
                or self._barbieri_saved is None):
            return
        box = getattr(self, "barbieri_size", None)
        if box is not None and box.currentIndex() != 0:
            box.blockSignals(True)
            box.setCurrentIndex(0)
            box.blockSignals(False)

    def _barbieri_head_changed(self, *_a) -> None:
        """A new opening: the patch size follows it while it is still the
        size the opening before started with (a size a person typed stays)."""
        from workflow.barbieri.chart import head_of
        new = self.barbieri_head.currentData()
        was = getattr(self, "_barbieri_head_was", None)
        self._barbieri_head_was = new
        if getattr(self, "_loading", False) or self._barbieri_saved is None:
            return
        old_default = head_of(was).default_patch_mm
        new_default = head_of(new).default_patch_mm
        for box in (self.patch_x, self.patch_y):
            if abs(float(box.value()) - old_default) < 1e-6:
                box.setValue(new_default)

    def _barbieri_size_picked(self, index: int) -> None:
        """A ready-made size was picked: fill the controls from it (every
        value stays editable, and is saved as typed)."""
        from dataclasses import replace
        from workflow.barbieri.chart import size_preset
        p = size_preset(self.barbieri_size.itemData(index))
        if p is None:
            return
        r = self.get_recipe()
        changes = dict(barbieri_size=p.key, barbieri_head=p.head,
                       patch_w_mm=p.patch_mm, patch_h_mm=p.patch_mm,
                       margin_top=p.margins[0], margin_right=p.margins[1],
                       margin_bottom=p.margins[2], margin_left=p.margins[3],
                       use_instrument_margins=False,
                       inter_patch_mm=0.0, strip_gap_mm=0.0)
        if p.page_size is not None:
            from workflow.page_output import support as po
            ps = po.clean_page_size(p.page_size)
            w, h = po.page_mm(ps, p.dpi or ps.get("ppi"))
            changes.update(paper=po.paper_code(w, h), page_size=ps,
                           tiff_res_unit="in")
        else:
            changes.update(paper=p.paper, page_size=None, tiff_res_unit="cm")
            # a paper size after a film frame: back from the film recorder's
            # resolution to the usual one, or an A4 page would be drawn at
            # 2731 ppi (400 megapixels); a person's own 600 dpi stays
            if int(getattr(r, "dpi", 300) or 300) > 1200:
                changes["dpi"] = 300
        if p.dpi:
            changes["dpi"] = int(p.dpi)
        r = replace(r, **changes)
        self._barbieri_applying = True
        try:
            self.set_recipe(r)
        finally:
            self._barbieri_applying = False
        self._margins_chosen = True
        self._emit()

    def _barbieri_controls(self) -> tuple:
        return (self.barbieri_size, self.barbieri_head, self.barbieri_check,
                self.barbieri_marks)

    def _barbieri_hold_greyed(self) -> None:
        """After an instrument change has run to its end: while the Barbieri
        is chosen, its greyed controls are greyed again with their reason."""
        if self._barbieri_saved is None:
            return
        for c, why in BarbieriPanelMixin._barbieri_greyed_controls(self):
            c.setEnabled(False)
            c.setToolTip(barbieri_greyed_reason(why))

    # ---- entering and leaving ------------------------------------------------

    def _barbieri_greyed_controls(self):
        for name, why in BARBIERI_GREYED.items():
            c = getattr(self, name, None)
            if c is not None:
                yield c, why
        for b in getattr(self, "_spacer_swatches", []) or []:
            yield b, "spacers"

    def _sync_barbieri_widgets(self, on: bool) -> None:
        """Enter or leave the Barbieri's layout, ONLY ON A CHANGE: entering
        greys what a Barbieri chart cannot use (each with its reason), shows
        the values that apply and lets the patch size step in 0.1 mm;
        leaving puts back exactly what was there."""
        grp = getattr(self, "_barbieri_group", None)
        if grp is None:
            return
        was = self._barbieri_saved
        grp.setVisible(bool(on))
        if on == (was is not None):
            return
        from workflow.barbieri.chart import head_of
        if on:
            saved = {"controls": [], "steps": [], "values": []}
            was_loading = getattr(self, "_loading", False)
            self._loading = True
            try:
                for c, why in BarbieriPanelMixin._barbieri_greyed_controls(
                        self):
                    saved["controls"].append((c, c.isEnabled(), c.toolTip()))
                    c.setEnabled(False)
                    c.setToolTip(barbieri_greyed_reason(why))
                sm = getattr(self, "spacer_mode", None)
                if sm is not None:
                    saved["spacer_mode"] = sm.currentIndex()
                    i = sm.findData("none")
                    if i >= 0:
                        sm.setCurrentIndex(i)
                lm = getattr(self, "layout_mode", None)
                if lm is not None:
                    saved["layout_mode"] = lm.currentIndex()
                    i = lm.findData("patch_first")
                    if i >= 0:
                        lm.setCurrentIndex(i)
                own = getattr(self, "_barbieri_own_patch", None)
                start = head_of(self.barbieri_head.currentData())
                for c, mine in zip((self.patch_x, self.patch_y),
                                   own or (None, None)):
                    saved["steps"].append((c, c.singleStep(), c.value(),
                                           c.specialValueText(),
                                           c.minimum()))
                    c.setSingleStep(0.1)
                    c.setSpecialValueText("")
                    c.setMinimum(max(0.1, c.minimum()))
                    c.setValue(mine if mine else start.default_patch_mm)
                si = getattr(self, "show_indicators", None)
                if si is not None:
                    saved["show_indicators"] = si.isChecked()
                    si.setChecked(bool(getattr(self, "_barbieri_own_letters",
                                               False)))
                pa = getattr(self, "patch_align", None)
                if pa is not None:
                    saved["align"] = pa.currentIndex()
                    # the Barbieri's own alignment when it is chosen again,
                    # else top-left unless a person picked one
                    own_align = getattr(self, "_barbieri_own_align", None)
                    i = pa.findData(own_align or "top-left")
                    if i >= 0 and (own_align or not getattr(
                            self, "_align_chosen", False)):
                        pa.setCurrentIndex(i)
                # THE MARGINS a new Barbieri chart starts with (15 mm left,
                # the patch area in the reading area), only where nobody set
                # them and nothing locks them
                locked = (hasattr(self, "use_instr_margins")
                          and self.use_instr_margins.isChecked())
                margins = getattr(self, "margins", None)
                at_default = getattr(self, "_margins_at_default", None)
                if (margins and not locked and callable(at_default)
                        and at_default()):
                    saved["margins"] = {k: b.value()
                                        for k, b in margins.items()}
                    from workflow.barbieri.chart import default_margins
                    from workflow.layout_engine import papers
                    try:
                        w, h = papers.dimensions_mm(
                            self.paper.currentData() if self.paper is not None
                            else "A4R")
                    except Exception:   # noqa: BLE001
                        w, h = 297.0, 210.0
                    for k, v in zip(("t", "r", "b", "l"),
                                    default_margins(w, h)):
                        margins[k].setValue(v)
            finally:
                self._loading = was_loading
            self._barbieri_saved = saved
            for name in ("_sync_layout_mode", "_sync_spacer_swatches",
                         "_sync_underline_enabled"):
                fn = getattr(self, name, None)
                if fn is not None:
                    fn()
            for c, why in BarbieriPanelMixin._barbieri_greyed_controls(self):
                c.setEnabled(False)
                c.setToolTip(barbieri_greyed_reason(why))
            return
        self._barbieri_saved = None
        self._barbieri_own_patch = (self.patch_x.value(), self.patch_y.value())
        pa = getattr(self, "patch_align", None)
        if pa is not None:
            self._barbieri_own_align = pa.currentData()
        si = getattr(self, "show_indicators", None)
        if si is not None:
            self._barbieri_own_letters = si.isChecked()
        was_loading = getattr(self, "_loading", False)
        self._loading = True
        try:
            for c, enabled, tip in was["controls"]:
                try:
                    c.setEnabled(enabled)
                    c.setToolTip(tip)
                except RuntimeError:
                    pass
            for c, step, value, special, minimum in was["steps"]:
                c.setMinimum(minimum)
                c.setSpecialValueText(special)
                c.setSingleStep(step)
                c.setValue(value)
            sm = getattr(self, "spacer_mode", None)
            if sm is not None and "spacer_mode" in was:
                sm.setCurrentIndex(was["spacer_mode"])
            lm = getattr(self, "layout_mode", None)
            if lm is not None and "layout_mode" in was:
                lm.setCurrentIndex(was["layout_mode"])
            pa = getattr(self, "patch_align", None)
            if pa is not None and "align" in was:
                pa.setCurrentIndex(was["align"])
            if si is not None and "show_indicators" in was:
                si.setChecked(was["show_indicators"])
            margins = getattr(self, "margins", None)
            if margins and "margins" in was:
                for k, v in was["margins"].items():
                    margins[k].setValue(v)
        finally:
            self._loading = was_loading
        for name in ("_sync_spacer_swatches", "_sync_underline_enabled",
                     "_sync_layout_mode"):
            fn = getattr(self, name, None)
            if fn is not None:
                fn()

    # ---- the recipe -----------------------------------------------------------

    def _barbieri_apply_to_recipe(self, r) -> None:
        """Write the group's values onto a "B100XY" recipe *r*."""
        if getattr(self, "_barbieri_group", None) is None \
                or r.instrument != "B100XY":
            return
        r.barbieri_head = self.barbieri_head.currentData() or "reflection-3"
        r.barbieri_check_patches = self.barbieri_check.isChecked()
        r.barbieri_marks = self.barbieri_marks.isChecked()
        r.barbieri_size = self.barbieri_size.currentData() or ""
        # what a Barbieri chart never has, stored as it is built
        r.spacer_mode, r.spacer_on = "none", False
        r.edge_spacers = False
        r.layout_mode = "patch_first"
        r.helper_markers = False

    def _barbieri_set_from_recipe(self, r) -> None:
        """Show a "B100XY" recipe's own options (any other: the defaults)."""
        if getattr(self, "_barbieri_group", None) is None:
            return
        from workflow.layout_engine.presets import BARBIERI_FIELD_DEFAULTS as D
        own = getattr(r, "instrument", "") == "B100XY"

        def val(name):
            return getattr(r, name, D[name]) if own else D[name]
        for w in BarbieriPanelMixin._barbieri_controls(self):
            w.blockSignals(True)
        try:
            i = self.barbieri_head.findData(val("barbieri_head"))
            self.barbieri_head.setCurrentIndex(max(0, i))
            self._barbieri_head_was = self.barbieri_head.currentData()
            i = self.barbieri_size.findData(val("barbieri_size") or "")
            self.barbieri_size.setCurrentIndex(max(0, i))
            self.barbieri_check.setChecked(bool(val("barbieri_check_patches")))
            self.barbieri_marks.setChecked(bool(val("barbieri_marks")))
            if own and self._barbieri_saved is not None:
                # a recipe's own patch size wins over the size the Barbieri
                # had when it was last chosen (`_sync_barbieri_widgets`)
                for box, v in ((self.patch_x, getattr(r, "patch_w_mm", 0)),
                               (self.patch_y, getattr(r, "patch_h_mm", 0))):
                    if v:
                        box.setValue(float(v))
        finally:
            for w in BarbieriPanelMixin._barbieri_controls(self):
                w.blockSignals(False)
