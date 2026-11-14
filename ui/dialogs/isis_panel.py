"""Manual's layout panel for the X-Rite i1iSis family (a Beta).

`ui.dialogs.layout_options_panel.LayoutOptionsPanel` calls these methods
through thin delegations (`_isis_call`), importing this module only while
the Beta "X-Rite i1iSis charts" is on. Off, nothing here is imported, built
or called, so the panel is 4.3.37's widget for widget
(`tests/test_isis_off_changes_nothing.py`).

On (and the i1iSis chosen):

* the group "i1iSis chart (Beta)" shows the chart's own options: the model
  width, the header length, tight margins, the barcode, the trailer, the
  feed arrows, the dashed outline, the corner labels, the strip letters, the
  row numbers and the notes band (PROPOSAL v2 §4);
* the controls that have no meaning for an i1iSis chart or would make it
  unreadable are greyed, each tooltip starting with its own reason, and get
  their values back when another instrument is chosen (checklist 3.5);
* the patch size boxes take X-Rite's 6 to 20 mm, and the patch area
  alignment is the chart's own (top-left unless a person chooses another).

Everything else stays open, as for the other instruments.
"""
from __future__ import annotations

from core.i18n import tr


def isis_greyed_why() -> dict:
    """Why each greyed control is greyed for an i1iSis chart (by key)."""
    gaps = tr("The i1iSis reads patches side by side without gaps (X-Rite's "
              "chart rules), so an i1iSis chart has no spacers and no gaps.")
    return {
        "gaps": gaps,
        "scale": tr("No base patch size to scale for this instrument: set the "
                    "patch size directly (6 to 20 mm)."),
        "mode": tr("An i1iSis chart has one layout; its own options are in "
                   "the group “i1iSis chart (Beta)”."),
        "shape": tr("The i1iSis needs straight rows with a marker at each "
                    "end, so offset strips and hexagons cannot be read."),
        "nolimit": tr("The page height decides the rows of an i1iSis chart; "
                      "use “Max strip length” to ask for fewer rows."),
        "clip": tr("An i1iSis chart has no side clip band; its notes band is "
                   "in the header or the trailer (group “i1iSis chart "
                   "(Beta)”), and the content options here fill it."),
        "markers": tr("No ruler: the black bar and the diamonds take the "
                      "ruler helper markers' place on an i1iSis chart."),
        "letter_gap": tr("The strip letters of an i1iSis chart sit in their "
                         "own place, the text band or the trailer, away from "
                         "the patches, so there is no gap to the strips to "
                         "set; “Label offset” moves them inside that place."),
    }


def isis_greyed_reason(why: str = "") -> str:
    own = isis_greyed_why().get(why, "")
    general = tr("The i1iSis chart (Beta) follows X-Rite's chart rules and "
                 "i1Profiler's own layout; its own options are in the group "
                 "“i1iSis chart (Beta)”.")
    return (own + "\n\n" + general) if own else general


#: Each greyed control by attribute name, with its reason key.
ISIS_GREYED = {
    **dict.fromkeys(("spacer_mode", "spacer_width", "custom_spacer_cb",
                     "inter_patch", "strip_gap", "edge_spacers_cb"),
                    "gaps"),
    "sig": "letter_gap",
    **dict.fromkeys(("pscale", "sscale"), "scale"),
    "mode": "mode",
    **dict.fromkeys(("cm_stagger_cb", "hex_flat_top_cb"), "shape"),
    "nolimit": "nolimit",
    **dict.fromkeys(("clip_enable", "clip_width", "clip_side",
                     "text_edge_clip"), "clip"),
    **dict.fromkeys(("helper_markers_cb", "helper_marker_edge",
                     "helper_marker_len", "helper_marker_per_patch",
                     "helper_markers_top_bottom", "helper_markers_sides"),
                    "markers"),
}


def isis_option_help(which: str) -> str:
    """The (i) of each control in the i1iSis group."""
    return {
        "model": tr(
            "“i1iSis / i1iSis 2” takes sheets up to 230 mm wide and reads the "
            "right markers up to 218 mm from the sheet's left edge; “XL "
            "models” (i1iSis XL, i1iSis 2 XL) take sheets up to 330 mm wide "
            "and read up to 318 mm. i1Profiler draws the same chart for both "
            "generations. **Default:** i1iSis / i1iSis 2."),
        "header": tr(
            "The distance from the chart's top edge to the black bar, 32 to "
            "80 mm (X-Rite's range; i1Profiler's own default is 32 mm). A "
            "longer header gives room for notes; the 20 mm right above the "
            "bar always stay blank. If the bar ends up more than 80 mm below "
            "the paper's top edge, the sheet must be cut along the dashed "
            "outline before it is fed. **Default:** 32 mm."),
        "tight": tr(
            "Moves the diamonds closer to the chart edge and the patches "
            "(4 mm and 3 mm instead of 5 mm and 5 mm), as i1Profiler's "
            "“tight margins”. On A4 one more column fits. **Default:** off."),
        "barcode": tr(
            "Prints X-Rite's Code 39 barcode under the bar: it names the "
            "rows, columns, patch size, page and the chart's name, so "
            "i1Profiler can recognise the sheet. The patch size must then be "
            "a multiple of 0.25 mm. This has not yet been read by a real "
            "i1iSis. **Default:** off."),
        "trailer": tr(
            "The blank paper after the last row, at least 25.5 mm (X-Rite "
            "asks for 25). The chart is never shorter than 171 mm, so a "
            "short chart gets a longer trailer by itself. **Default:** "
            "25.5 mm."),
        "arrows": tr(
            "Two arrows at the top that show which edge goes into the "
            "instrument first. i1Profiler always prints them; they are for "
            "you, the instrument does not need them. **Default:** on."),
        "outline": tr(
            "The dashed line around the chart. Cut along it when ChromIQ says "
            "the sheet must be cut. **Default:** on."),
        "corners": tr(
            "The names of the first and last patch in each corner, as "
            "i1Profiler prints them, in the text band at the top and the "
            "last 3.5 mm at the bottom. **Default:** on."),
        "letters": tr(
            "Where the strip letters go when “Show strip indicators” is "
            "ticked: the text band at the top of the chart, or the trailer "
            "(which grows to hold them). Only these two places, because the "
            "i1iSis looks everywhere else. The letters take the label style "
            "under “Labels” (typeface, size, bold, italic, rotation, "
            "alignment, underline and offsets), held inside their place; a "
            "label that would be smaller than 1.5 mm there is left off, and "
            "the log says so. “Show row indicators” prints the row numbers "
            "to the right of the right diamonds, with 3 mm of blank paper "
            "between, inside the chart's outline (the chart grows wider to "
            "hold them when the paper allows). Neither has been read by a "
            "real i1iSis yet. **Default:** top text band; both off."),
        "band": tr(
            "A band for notes in the header (the header grows by the band's "
            "height, up to 80 mm) or in the trailer (the trailer grows). It "
            "is filled with the content chosen under “Clip border content”: "
            "the Notes box by default, your text, the ChromIQ branding or an "
            "image. Nothing is ever printed in the 20 mm above the bar or "
            "in the first 22 mm after the last row. **Default:** off."),
    }.get(which, "")


class IsisPanelMixin:
    """The i1iSis parts of `LayoutOptionsPanel` (only while the Beta is on)."""

    # ---- the group ---------------------------------------------------------

    def _isis_build_group(self, parent_layout) -> None:
        """Build "i1iSis chart (Beta)" (hidden until the i1iSis is chosen)."""
        from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                                     QGridLayout, QGroupBox, QLabel)
        from ui.tooltip_button import TooltipButton
        g = QGroupBox(tr("i1iSis chart (Beta)"), self)
        grid = QGridLayout(g)
        row = 0

        def put(label, control, which):
            nonlocal row
            if label:
                grid.addWidget(QLabel(label, g), row, 0)
                grid.addWidget(control, row, 1)
            else:
                grid.addWidget(control, row, 0, 1, 2)
            grid.addWidget(TooltipButton(label.rstrip(":") if label
                                         else control.text(),
                                         isis_option_help(which), g,
                                         min_width=560), row, 2)
            row += 1

        self.isis_model = QComboBox(g)
        self.isis_model.addItem(tr("i1iSis / i1iSis 2"), "standard")
        self.isis_model.addItem(tr("XL models"), "xl")
        put(tr("Model:"), self.isis_model, "model")

        def spin(lo, hi, value, step=0.5):
            box = QDoubleSpinBox(g)
            box.setRange(lo, hi)
            box.setDecimals(1)
            box.setSingleStep(step)
            box.setSuffix(" mm")
            box.setValue(value)
            return box
        self.isis_header = spin(32.0, 80.0, 32.0)
        put(tr("Header length:"), self.isis_header, "header")
        self.isis_trailer = spin(25.5, 300.0, 25.5)
        put(tr("Trailer length:"), self.isis_trailer, "trailer")
        self.isis_tight = QCheckBox(tr("Tight margins"), g)
        put("", self.isis_tight, "tight")
        self.isis_barcode = QCheckBox(tr("Barcode"), g)
        put("", self.isis_barcode, "barcode")
        self.isis_arrows = QCheckBox(tr("Feed arrows"), g)
        self.isis_arrows.setChecked(True)
        put("", self.isis_arrows, "arrows")
        self.isis_outline = QCheckBox(tr("Dashed outline"), g)
        self.isis_outline.setChecked(True)
        put("", self.isis_outline, "outline")
        self.isis_corners = QCheckBox(tr("Corner labels"), g)
        self.isis_corners.setChecked(True)
        put("", self.isis_corners, "corners")
        # WHERE the strip letters go: the i1iSis's own (only where the
        # instrument does not look). Whether they and the row numbers are
        # printed, and in which style, is the engine's own label controls.
        self.isis_letters = QComboBox(g)
        self.isis_letters.addItem(tr("Top text band"), "top")
        self.isis_letters.addItem(tr("Trailer"), "bottom")
        put(tr("Strip letters place:"), self.isis_letters, "letters")
        self.isis_band = QCheckBox(tr("Notes band"), g)
        put("", self.isis_band, "band")
        self.isis_band_place = QComboBox(g)
        self.isis_band_place.addItem(tr("Header"), "header")
        self.isis_band_place.addItem(tr("Trailer"), "trailer")
        put(tr("Notes band place:"), self.isis_band_place, "band")
        self.isis_band_height = spin(4.0, 48.0, 24.0, 1.0)
        put(tr("Notes band height:"), self.isis_band_height, "band")
        for w, sig in ((self.isis_model, "currentIndexChanged"),
                       (self.isis_header, "valueChanged"),
                       (self.isis_trailer, "valueChanged"),
                       (self.isis_tight, "toggled"),
                       (self.isis_barcode, "toggled"),
                       (self.isis_arrows, "toggled"),
                       (self.isis_outline, "toggled"),
                       (self.isis_corners, "toggled"),
                       (self.isis_letters, "currentIndexChanged"),
                       (self.isis_band, "toggled"),
                       (self.isis_band_place, "currentIndexChanged"),
                       (self.isis_band_height, "valueChanged")):
            getattr(w, sig).connect(self._isis_option_changed)
        g.setVisible(False)
        self._isis_group = g
        # the person's own "Show strip indicators" for the i1iSis, kept for
        # when it is chosen again (i1iSis -> another -> i1iSis)
        si = getattr(self, "show_indicators", None)
        if si is not None:
            si.toggled.connect(self._isis_letters_toggled)
        self._isis_align = ""
        self._isis_saved = None
        parent_layout.addWidget(g)

    def _isis_option_changed(self, *_a) -> None:
        IsisPanelMixin._isis_option_changed_body(self)

    def _isis_option_changed_body(self, *_a) -> None:
        self.isis_band_place.setEnabled(self.isis_band.isChecked())
        self.isis_band_height.setEnabled(self.isis_band.isChecked())
        # the content group shows while the band is on
        self._update_clip_visibility()
        if not getattr(self, "_loading", False):
            self._emit()

    def _isis_letters_toggled(self, on: bool) -> None:
        # a tick while the i1iSis is chosen is its own, whether the person
        # set it or a preset or saved default did; entering and leaving set
        # the box while _isis_saved is None, so they never count
        if self._isis_saved is not None:
            self._isis_own_letters = bool(on)

    def _isis_controls(self) -> tuple:
        return (self.isis_model, self.isis_header, self.isis_trailer,
                self.isis_tight, self.isis_barcode, self.isis_arrows,
                self.isis_outline, self.isis_corners, self.isis_letters,
                self.isis_band, self.isis_band_place,
                self.isis_band_height)

    # ---- entering and leaving ------------------------------------------------

    def _isis_greyed_controls(self):
        for name, why in ISIS_GREYED.items():
            c = getattr(self, name, None)
            if c is not None:
                yield c, why
        for b in getattr(self, "_spacer_swatches", []) or []:
            yield b, "gaps"

    def _sync_isis_widgets(self, on: bool) -> None:
        """Enter or leave the i1iSis's layout, ONLY ON A CHANGE: entering
        greys what an i1iSis chart cannot use (each with its reason), shows
        the values that apply and holds the patch size inside 6 to 20 mm;
        leaving puts back exactly what was there."""
        grp = getattr(self, "_isis_group", None)
        if grp is None:
            return
        was = self._isis_saved
        grp.setVisible(bool(on))
        if on == (was is not None):
            return
        from workflow.isis import chart_facts as F
        if on:
            saved = {"controls": [], "ranges": [], "values": []}
            was_loading = getattr(self, "_loading", False)
            self._loading = True
            try:
                for c, why in IsisPanelMixin._isis_greyed_controls(self):
                    saved["controls"].append((c, c.isEnabled(), c.toolTip()))
                    c.setEnabled(False)
                    c.setToolTip(isis_greyed_reason(why))
                # what the greyed controls show: no spacers, no gaps
                for name, value in (("inter_patch", 0.0), ("strip_gap", 0.0)):
                    box = getattr(self, name, None)
                    if box is not None:
                        saved["values"].append((box, box.value()))
                        box.setValue(value)
                sm = getattr(self, "spacer_mode", None)
                if sm is not None:
                    saved["spacer_mode"] = sm.currentIndex()
                    i = sm.findData("none")
                    if i >= 0:
                        sm.setCurrentIndex(i)
                lo, hi = F.PATCH_MIN_MM.value, F.PATCH_MAX_MM.value
                own = getattr(self, "_isis_own_patch", None) or (None, None)
                for c, mine in zip((self.patch_x, self.patch_y), own):
                    saved["ranges"].append((c, c.minimum(), c.maximum(),
                                            c.value(), c.specialValueText()))
                    v = c.value()
                    c.setSpecialValueText("")
                    c.setRange(lo, hi)
                    # the i1iSis's own size comes back when it is chosen
                    # again (i1iSis -> another -> i1iSis)
                    if mine:
                        c.setValue(mine)
                    elif not v:
                        c.setValue(F.PATCH_DEFAULT_MM.value)
                # no strip letters by default, as i1Profiler prints none;
                # the person's own tick for the i1iSis comes back with it
                si = getattr(self, "show_indicators", None)
                if si is not None:
                    saved["show_indicators"] = si.isChecked()
                    # also inside a load: a recipe being loaded sets the
                    # instrument BEFORE this box (`_set_recipe_impl`), so
                    # its own value still wins and is recorded as the
                    # i1iSis's own (`_isis_letters_toggled`)
                    si.setChecked(bool(getattr(self, "_isis_own_letters",
                                               False)))
                pa = getattr(self, "patch_align", None)
                if pa is not None:
                    saved["align"] = pa.currentIndex()
                    i = pa.findData(self._isis_align or "top-left")
                    if i >= 0:
                        pa.setCurrentIndex(i)
            finally:
                self._loading = was_loading
            self._isis_saved = saved
            return
        self._isis_saved = None
        self._isis_own_patch = (self.patch_x.value(), self.patch_y.value())
        was_loading = getattr(self, "_loading", False)
        self._loading = True
        try:
            for c, enabled, tip in was["controls"]:
                try:
                    c.setEnabled(enabled)
                    c.setToolTip(tip)
                except RuntimeError:
                    pass
            for c, lo, hi, value, special in was["ranges"]:
                c.setSpecialValueText(special)
                c.setRange(lo, hi)
                c.setValue(value)
            for box, value in was["values"]:
                box.setValue(value)
            sm = getattr(self, "spacer_mode", None)
            if sm is not None and "spacer_mode" in was:
                sm.setCurrentIndex(was["spacer_mode"])
            pa = getattr(self, "patch_align", None)
            if pa is not None and "align" in was:
                pa.setCurrentIndex(was["align"])
            si = getattr(self, "show_indicators", None)
            if si is not None and "show_indicators" in was:
                si.setChecked(was["show_indicators"])
        finally:
            self._loading = was_loading

    def _isis_align_picked(self, *_a) -> None:
        """A PERSON picked "Patch area alignment" while the i1iSis is chosen:
        it places the chart from now on (`LayoutRecipe.isis_align`)."""
        if self._isis_saved is not None and not getattr(self, "_loading",
                                                        False):
            v = self.patch_align.currentData() or ""
            self._isis_align = "" if v == "top-left" else v

    # ---- the recipe -----------------------------------------------------------

    def _isis_apply_to_recipe(self, r) -> None:
        """Write the group's values onto an "XRISIS" recipe *r*."""
        if getattr(self, "_isis_group", None) is None \
                or r.instrument != "XRISIS":
            return
        r.isis_model = (self.isis_model.currentData() or "standard")
        if r.isis_model == "standard":
            r.isis_model = ""
        r.isis_header_mm = float(self.isis_header.value())
        r.isis_trailer_mm = float(self.isis_trailer.value())
        r.isis_tight = self.isis_tight.isChecked()
        r.isis_barcode = self.isis_barcode.isChecked()
        r.isis_arrows = self.isis_arrows.isChecked()
        r.isis_outline = self.isis_outline.isChecked()
        r.isis_corner_labels = self.isis_corners.isChecked()
        r.isis_strip_letters = self.isis_letters.currentData() or "top"
        r.isis_notes_band = self.isis_band.isChecked()
        r.isis_notes_place = self.isis_band_place.currentData() or "header"
        r.isis_notes_height_mm = float(self.isis_band_height.value())
        r.isis_align = self._isis_align
        # what an i1iSis chart never has, stored as it is built
        r.spacer_mode, r.spacer_on = "none", False
        r.inter_patch_mm = r.strip_gap_mm = 0.0
        r.edge_spacers = False

    def _isis_set_from_recipe(self, r) -> None:
        """Show an "XRISIS" recipe's own options (any other: the defaults)."""
        if getattr(self, "_isis_group", None) is None:
            return
        from workflow.layout_engine.presets import ISIS_FIELD_DEFAULTS as D
        own = getattr(r, "instrument", "") == "XRISIS"

        def val(name):
            return getattr(r, name, D[name]) if own else D[name]
        for w in IsisPanelMixin._isis_controls(self):
            w.blockSignals(True)
        try:
            i = self.isis_model.findData(val("isis_model") or "standard")
            self.isis_model.setCurrentIndex(max(0, i))
            self.isis_header.setValue(float(val("isis_header_mm")))
            self.isis_trailer.setValue(float(val("isis_trailer_mm")))
            self.isis_tight.setChecked(bool(val("isis_tight")))
            self.isis_barcode.setChecked(bool(val("isis_barcode")))
            self.isis_arrows.setChecked(bool(val("isis_arrows")))
            self.isis_outline.setChecked(bool(val("isis_outline")))
            self.isis_corners.setChecked(bool(val("isis_corner_labels")))
            i = self.isis_letters.findData(val("isis_strip_letters") or "top")
            self.isis_letters.setCurrentIndex(max(0, i))
            self.isis_band.setChecked(bool(val("isis_notes_band")))
            i = self.isis_band_place.findData(val("isis_notes_place")
                                              or "header")
            self.isis_band_place.setCurrentIndex(max(0, i))
            self.isis_band_height.setValue(float(val("isis_notes_height_mm")))
            self._isis_align = str(val("isis_align") or "")
            if own and self._isis_saved is not None:
                # a recipe's own patch size wins over the size the i1iSis
                # had when it was last chosen (`_sync_isis_widgets`)
                for box, v in ((self.patch_x, getattr(r, "patch_w_mm", 0)),
                               (self.patch_y, getattr(r, "patch_h_mm", 0))):
                    if v:
                        box.setValue(float(v))
        finally:
            for w in IsisPanelMixin._isis_controls(self):
                w.blockSignals(False)
        self.isis_band_place.setEnabled(self.isis_band.isChecked())
        self.isis_band_height.setEnabled(self.isis_band.isChecked())
        if self._isis_saved is not None:
            pa = getattr(self, "patch_align", None)
            if pa is not None:
                was = getattr(self, "_loading", False)
                self._loading = True
                try:
                    i = pa.findData(self._isis_align or "top-left")
                    if i >= 0:
                        pa.setCurrentIndex(i)
                finally:
                    self._loading = was
