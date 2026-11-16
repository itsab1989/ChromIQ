"""Create Chart's layout panel, the page-output Beta's part (#215).

Only built while Preferences > Beta > "Custom page size in inches or pixels,
and high resolution" is on (`workflow.page_output.support`), and only in the
panels that choose a page (Create Chart > Manual; the patch set editor builds
the same panel hidden, and hands the chart's page back through it). With
the Beta off nothing here builds a widget; the one thing that still runs is
:func:`load_recipe`'s HOLD, for a chart made with the Beta and opened without
it (see below).

THE FIELDS. Three rows of two fields, millimetres, inches and pixels. Each
side keeps what the person last TYPED, in the unit it was typed in (the
"truth"); the other two rows show that value converted, and showing it never
writes back. So a side typed as 2730 pixels stays 2730 pixels however often
the millimetre row is redrawn, and a resolution changed afterwards keeps the
pixel count and moves the size (the frame is defined by its pixels). A side
typed in millimetres or inches keeps its size and its pixel count follows the
resolution.

The millimetre fields are the panel's own ``custom_w`` / ``custom_h``, which
other code also writes (the i1iO turns a custom size upright with its signals
blocked). A truth whose millimetres no longer match what those fields show was
overwritten behind this module's back, and the fields win
(:func:`_heal_truth`).

THE UNITS CHOICE (a panel built with ``units_choice=True``: Create Chart >
Manual). One "Units" combobox under Paper says what every length in the
panel is shown in: millimetres, inches, or (for the page size only) pixels.
The page size is then ONE pair of fields, the chosen unit's row; the other
two rows still exist, hidden, so everything above holds unchanged. The rules
of the choice (:func:`_page_switch`):

* the unit shown is the thing that is kept: with pixels shown a changed
  resolution keeps the pixel count, with mm or inches shown it keeps the size
  on paper (:func:`_keep_shown_unit` turns a side the other way round, at the
  resolution it was made for, before a new resolution is applied);
* switching between mm and inches never changes the page (the typed side is
  kept as typed, only shown converted); switching to pixels makes the page
  whole pixels, and switching back WITHOUT having typed anything (and at the
  same resolution) restores exactly what was there before: merely looking
  never changes a page;
* the stored form is 4.3.43's: the paper code, ``page_size`` with each side
  as it was typed, ``tiff_res_unit``.

Every other length box of the panel is a
:class:`ui.dialogs.length_units.LengthSpinBox`: its value is millimetres,
inches are a display only (pixels show millimetres there). The choice itself
is a personal preference (``page_output_units`` in AppSettings), never part of
a chart, a preset or a target. The patch set editor's hidden copy of the
panel has no choice and keeps the three rows.

THE HOLD (Beta off). A chart's recipe holding a value only the Beta writes
(:func:`workflow.page_output.support.uses_beta_values`) cannot be shown by the
4.3.42 fields: they are whole millimetres and stop at 1200 dpi. The panel then
shows the nearest values it can, says so in a note, and :func:`apply_to_recipe`
gives back the chart's OWN page values for as long as the person leaves the
paper, the size and the resolution as the load showed them. So saving the
target writes nothing new, and nothing is rounded silently; the engine refuses
to draw what needs the Beta (`PageBetaOff`). The first change the person makes
to any of the four is theirs, and the hold ends.
"""
from __future__ import annotations

from typing import Any

from core.i18n import tr
from workflow.page_output import support as po

_AXES = ("w", "h")


# ---- construction (Beta on) --------------------------------------------------

def build_custom_rows(panel: Any, grid: Any) -> None:
    """Lay the custom size out as three rows of two-way fields in *grid*
    (the custom-size widget's own layout)."""
    from PyQt6.QtWidgets import QLabel
    from ui.tooltip_button import TooltipButton
    from ui.widgets import NoScrollDoubleSpinBox, NoScrollSpinBox

    panel._custom_size_lbl.setText(tr("Custom size:"))
    panel._page_syncing = False
    panel._page_truth = {"w": (210.0, po.UNIT_MM), "h": (297.0, po.UNIT_MM)}
    panel._page_in = {}
    panel._page_px = {}
    for axis in _AXES:
        box = NoScrollDoubleSpinBox(panel)
        box.setDecimals(4)
        # the millimetre range in inches (review F5); the pixel range is
        # set by `_fit_ranges` (any count; whether it fits is said, R3-a)
        box.setRange(round(po.CUSTOM_MM_MIN_ON / po.MM_PER_INCH, 4),
                     round(po.CUSTOM_MM_MAX / po.MM_PER_INCH, 4))
        box.setMaximumWidth(96)
        panel._page_in[axis] = box
        pbox = NoScrollSpinBox(panel)
        pbox.setRange(1, 9_999_999)
        pbox.setMaximumWidth(96)
        panel._page_px[axis] = pbox
    grid.addWidget(panel._custom_size_lbl, 0, 0)
    rows = (
        (po.UNIT_MM, panel.custom_w, panel.custom_h, tr("mm")),
        (po.UNIT_IN, panel._page_in["w"], panel._page_in["h"], tr("in")),
        (po.UNIT_PX, panel._page_px["w"], panel._page_px["h"], tr("px")),
    )
    units = getattr(panel, "_units_choice", False)
    panel._page_rows = {}
    for row, (unit, wbox, hbox, word) in enumerate(rows):
        # with the Units choice the three rows share ONE grid row and only
        # the chosen unit's is shown (`_show_page_unit_rows`)
        at = 0 if units else row
        times, unit_lbl = QLabel("×", panel), QLabel(word, panel)
        grid.addWidget(wbox, at, 1)
        grid.addWidget(times, at, 2)
        grid.addWidget(hbox, at, 3)
        grid.addWidget(unit_lbl, at, 4)
        panel._page_rows[unit] = (wbox, times, hbox, unit_lbl)
    if units:
        panel._page_unit = po.UNIT_MM
        panel._page_look = None
    panel._page_size_tip = TooltipButton(
        tr("Custom size"),
        custom_size_help_units() if units else custom_size_help(), panel,
        min_width=620)
    grid.addWidget(panel._page_size_tip, 0, 5)
    grid.setColumnStretch(6, 1)
    # Bound methods on the panel's own class are not available for a module
    # function, so the slots are small QObject-free callables kept on the
    # panel; none captures a widget the panel does not own (CLAUDE.md: no
    # self-capturing lambda on a signal a child emits). `_Edited` holds the
    # panel weakly.
    for axis in _AXES:
        _connect(panel, panel.custom_w if axis == "w" else panel.custom_h,
                 axis, po.UNIT_MM)
        _connect(panel, panel._page_in[axis], axis, po.UNIT_IN)
        _connect(panel, panel._page_px[axis], axis, po.UNIT_PX)
        panel._page_in[axis].valueChanged.connect(panel._emit)
        panel._page_px[axis].valueChanged.connect(panel._emit)
    _show_truth(panel)


class _Edited:
    """The slot for one display field: what the person typed is the truth
    for that side, in that field's unit. Holds the panel weakly."""

    def __init__(self, panel: Any, axis: str, unit: str) -> None:
        import weakref
        self._panel = weakref.ref(panel)
        self.axis, self.unit = axis, unit

    def __call__(self, value: Any) -> None:
        panel = self._panel()
        if panel is None or getattr(panel, "_page_syncing", False):
            return
        try:
            last = getattr(panel, "_page_last_ppi", None)
            if last not in (None, _ppi(panel)):
                # the other side was made for the resolution shown before
                _keep_shown_unit(panel, last, skip=self.axis)
            panel._page_truth[self.axis] = (float(value), self.unit)
            _show_truth(panel, only=self.axis, skip_unit=self.unit)
        except RuntimeError:          # a widget deleted with the panel
            pass


def _connect(panel: Any, box: Any, axis: str, unit: str) -> None:
    slot = _Edited(panel, axis, unit)
    panel.__dict__.setdefault("_page_slots", []).append(slot)
    box.valueChanged.connect(slot)


def build_pixel_readout(panel: Any, grid: Any, row: int) -> None:
    """The line under the paper that says how many pixels the page will be."""
    from PyQt6.QtWidgets import QLabel
    lbl = QLabel("", panel)
    lbl.setWordWrap(True)
    panel._page_px_lbl = lbl
    grid.addWidget(lbl, row, 0, 1, 4)
    panel.changed.connect(_Refresh(panel))


class _Refresh:
    """Redraw the converted fields and the pixel line (panel held weakly)."""

    def __init__(self, panel: Any) -> None:
        import weakref
        self._panel = weakref.ref(panel)
        panel.__dict__.setdefault("_page_slots", []).append(self)

    def __call__(self, *_a) -> None:
        panel = self._panel()
        if panel is not None:
            try:
                refresh(panel)
            except RuntimeError:
                pass


def build_res_unit_row(panel: Any, grid: Any, row: int, add_row: Any) -> None:
    """Output > "Resolution unit:" (pixels per centimetre or per inch)."""
    from ui.tooltip_button import TooltipButton
    from ui.widgets import ElidingComboBox
    combo = ElidingComboBox(panel)
    combo.addItem(tr("Pixels per centimetre"), po.RES_UNIT_CM)
    combo.addItem(tr("Pixels per inch"), po.RES_UNIT_IN)
    combo.currentIndexChanged.connect(panel._emit)
    panel.tiff_res_unit = combo
    add_row(grid, row, tr("Resolution unit:"), combo,
            tip=TooltipButton(tr("Resolution unit"), res_unit_help(), panel,
                              min_width=620))


def sync_instrument(panel: Any, inst: str) -> None:
    """The Resolution unit row for the instrument chosen (review F3). The
    FD-9's contributed layout writes pixels per centimetre whatever the
    recipe asks, and its code is not changed by this Beta; so for the FD-9
    the row is greyed, shows what is written, and says why."""
    combo = getattr(panel, "tiff_res_unit", None)
    if combo is None:
        return
    fd9 = inst == "FD9"
    if fd9:
        if combo.isEnabled():
            panel._page_res_unit_kept = combo.currentData()
        b = combo.blockSignals(True)
        combo.setCurrentIndex(max(0, combo.findData(po.RES_UNIT_CM)))
        combo.blockSignals(b)
        combo.setEnabled(False)
        combo.setToolTip(tr(
            "Not available for the FD-9. An FD-9 chart is always written with "
            "its resolution in pixels per centimetre. The size of the page and "
            "its pixel count are as you set them."))
    elif not combo.isEnabled():
        combo.setEnabled(True)
        combo.setToolTip("")
        kept = panel.__dict__.pop("_page_res_unit_kept", None)
        if kept:
            b = combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(kept)))
            combo.blockSignals(b)


def turned_upright(panel: Any) -> None:
    """The i1iO turned the custom size upright in the millimetre fields (with
    their signals blocked): the typed sides turn with it, each in its own
    unit, so a page typed in pixels stays pixel-exact on the i1iO."""
    truth = getattr(panel, "_page_truth", None)
    if truth is None:
        return
    truth["w"], truth["h"] = truth["h"], truth["w"]
    _show_truth(panel)


# ---- the Units choice (a panel built with units_choice=True) -------------------

#: AppSettings key of the choice (``core.settings.DEFAULTS``: "mm").
UNITS_SETTING = "page_output_units"

def _length_labels() -> "list[tuple[str, str]]":
    """The labels that name millimetres today, and what they say in inches
    (both as shown, in the UI language)."""
    return [
        (tr("Margins (mm):"), tr("Margins (in):")),
        (tr("Patch size (mm):"), tr("Patch size (in):")),
        (tr("Chart offset (mm):"), tr("Chart offset (in):")),
        (tr("Minimum patch width (mm):"), tr("Minimum patch width (in):")),
        (tr("Distance from page edge (mm):"),
         tr("Distance from page edge (in):")),
        (tr("Marker length (mm):"), tr("Marker length (in):")),
        (tr("Text distance from edge (mm):"),
         tr("Text distance from edge (in):")),
    ]


def _stored_units() -> str:
    try:
        from core.settings import AppSettings
        unit = str(AppSettings().get(UNITS_SETTING, po.UNIT_MM) or po.UNIT_MM)
    except Exception:  # noqa: BLE001 - a broken store means millimetres
        unit = po.UNIT_MM
    return unit if unit in po.UNITS else po.UNIT_MM


def build_units_row(panel: Any, grid: Any, row: int) -> None:
    """"Units:" under Paper, in the Paper column, with its (i): the unit of
    every length in the panel (pixels: the page size only)."""
    from PyQt6.QtWidgets import QLabel
    from ui.tooltip_button import TooltipButton
    from ui.widgets import ElidingComboBox
    combo = ElidingComboBox(panel)
    combo.addItem(tr("Millimetres"), po.UNIT_MM)
    combo.addItem(tr("Inches"), po.UNIT_IN)
    combo.addItem(tr("Pixels (page size only)"), po.UNIT_PX)
    panel.units = combo
    panel._units_lbl = QLabel(tr("Units:"), panel)
    grid.addWidget(panel._units_lbl, row, 0)
    grid.addWidget(combo, row, 1)
    panel._units_tip = TooltipButton(tr("Units"), units_help(), panel,
                                     min_width=620)
    grid.addWidget(panel._units_tip, row, 4)


class _UnitsChosen:
    """The slot of the Units combobox (panel held weakly)."""

    def __init__(self, panel: Any) -> None:
        import weakref
        self._panel = weakref.ref(panel)
        panel.__dict__.setdefault("_page_slots", []).append(self)

    def __call__(self, *_a) -> None:
        panel = self._panel()
        if panel is None:
            return
        try:
            unit = panel.units.currentData() or po.UNIT_MM
            try:
                from core.settings import AppSettings
                AppSettings().set(UNITS_SETTING, unit)
            except Exception:  # noqa: BLE001 - shown even if not remembered
                pass
            apply_units(panel, unit)
            panel._emit()
        except RuntimeError:
            pass


def finish_units(panel: Any) -> None:
    """The end of the panel's construction: find the length labels, boxes
    and their (i), and show the unit the person chose last time."""
    from PyQt6.QtWidgets import QLabel
    from ui.dialogs.length_units import LengthSpinBox
    wanted = {a: (a, b) for a, b in _length_labels()}
    panel._unit_labels = [(lbl,) + wanted[lbl.text()]
                          for lbl in panel.findChildren(QLabel)
                          if lbl.text() in wanted]
    panel._length_boxes = list(panel.findChildren(LengthSpinBox))
    for lbl, _a, _b in panel._unit_labels:
        for w in _row_widgets(panel, lbl):
            for box in [w] + list(w.findChildren(LengthSpinBox)):
                if isinstance(box, LengthSpinBox):
                    box._unit_in_label = True
    tips = []
    for box in panel._length_boxes:
        tip = _row_tip(panel, box)
        if tip is not None and all(tip is not t for t in tips):
            tips.append(tip)
    panel._length_tips = tips
    unit = _stored_units()
    b = panel.units.blockSignals(True)
    panel.units.setCurrentIndex(max(0, panel.units.findData(unit)))
    panel.units.blockSignals(b)
    # the page is not converted at start: a recipe brings its own page, and
    # a page nobody typed is shown in the unit chosen
    panel._page_unit = unit
    _show_page_unit_rows(panel)
    _apply_length_unit(panel, unit)
    panel.units.currentIndexChanged.connect(_UnitsChosen(panel))
    _show_truth(panel)


def _row_widgets(panel: Any, widget: Any) -> list:
    """The widgets on the grid row of *widget* (a row label)."""
    from PyQt6.QtWidgets import QGridLayout
    for grid in panel.findChildren(QGridLayout):
        i = grid.indexOf(widget)
        if i < 0:
            continue
        row = grid.getItemPosition(i)[0]
        out = []
        for j in range(grid.count()):
            item = grid.itemAt(j)
            w = item.widget() if item is not None else None
            if w is not None and w is not widget and \
                    grid.getItemPosition(j)[0] == row:
                out.append(w)
        return out
    return []


def _row_tip(panel: Any, widget: Any) -> Any:
    """The (i) on the grid row that holds *widget* (or a box around it)."""
    from PyQt6.QtWidgets import QGridLayout
    from ui.tooltip_button import TooltipButton
    grids = panel.findChildren(QGridLayout)
    w = widget
    while w is not None and w is not panel:
        for grid in grids:
            i = grid.indexOf(w)
            if i < 0:
                continue
            row = grid.getItemPosition(i)[0]
            for j in range(grid.count()):
                item = grid.itemAt(j)
                tip = item.widget() if item is not None else None
                if isinstance(tip, TooltipButton) and \
                        grid.getItemPosition(j)[0] == row:
                    return tip
        w = w.parentWidget()
    return None


def apply_units(panel: Any, unit: str) -> None:
    """Show the panel in *unit*: the page size by the switch rule, every
    other length in mm or inches (pixels: millimetres)."""
    unit = unit if unit in po.UNITS else po.UNIT_MM
    _page_switch(panel, unit)
    _apply_length_unit(panel, unit)


def _apply_length_unit(panel: Any, unit: str) -> None:
    from ui.dialogs.length_units import LEN_IN, LEN_MM
    length = LEN_IN if unit == po.UNIT_IN else LEN_MM
    for box in getattr(panel, "_length_boxes", ()):
        try:
            box.set_length_unit(length)
            refresh_inch = getattr(box, "_refresh_inch", None)
            if callable(refresh_inch):
                refresh_inch()
        except RuntimeError:
            pass
    for lbl, mm_text, in_text in getattr(panel, "_unit_labels", ()):
        try:
            lbl.setText(in_text if length == LEN_IN else mm_text)
        except RuntimeError:
            pass
    note = _length_in_note()
    for tip in getattr(panel, "_length_tips", ()):
        try:
            base = tip.__dict__.setdefault("_units_base_body", tip._body)
            tip.set_content(tip._title, base + "\n\n" + note
                            if length == LEN_IN else base)
        except RuntimeError:
            pass
    if getattr(panel, "_spin_widths_fitted", False):
        try:
            panel._fit_spin_widths()
        except RuntimeError:
            pass


def _show_page_unit_rows(panel: Any) -> None:
    """Only the chosen unit's pair of page fields is shown."""
    rows = getattr(panel, "_page_rows", None)
    if not rows:
        return
    chosen = getattr(panel, "_page_unit", po.UNIT_MM)
    for unit, widgets in rows.items():
        for w in widgets:
            w.setVisible(unit == chosen)


def _side_in(side: "tuple[float, str]", unit: str,
             ppi: float) -> "tuple[float, str]":
    """One typed side as it is kept with *unit* shown: whole pixels for
    pixels; a side in pixels as its exact size for mm or inches; a side
    already in mm or inches as it was typed (the size on paper is kept)."""
    v, u = side
    if unit == po.UNIT_PX:
        if u == po.UNIT_PX:
            return (float(v), po.UNIT_PX)
        return (float(po.pixels_of(po.to_mm(v, u, ppi), ppi)), po.UNIT_PX)
    if u == po.UNIT_PX:
        return (po.from_mm(po.to_mm(v, u, ppi), unit, ppi), unit)
    return (float(v), u)


def _page_switch(panel: Any, new: str) -> None:
    """The page size's fields change to *new* (the rule in the module
    docstring). While the person is only LOOKING (nothing typed and the
    resolution unchanged since the last switch), every view is worked out
    from the page as it was before the first switch, and coming back to
    that unit gives it back exactly."""
    truth = getattr(panel, "_page_truth", None)
    old = getattr(panel, "_page_unit", po.UNIT_MM)
    if truth is None or new == old:
        panel._page_unit = new
        _show_page_unit_rows(panel)
        return
    _heal_truth(panel)
    ppi = _ppi(panel)
    now = {a: tuple(truth[a]) for a in _AXES}
    memo = getattr(panel, "_page_look", None)
    looking = (memo is not None and now == memo["after"]
               and ppi == memo["ppi"])
    if not looking:
        memo = {"origin": now, "unit": old, "ppi": ppi}
    if new == memo["unit"]:
        shown = dict(memo["origin"])
    else:
        shown = {a: _side_in(memo["origin"][a], new, ppi) for a in _AXES}
    panel._page_truth = shown
    memo["after"] = {a: tuple(shown[a]) for a in _AXES}
    panel._page_look = memo
    panel._page_unit = new
    panel._page_last_ppi = ppi
    _show_page_unit_rows(panel)
    _show_truth(panel)


def _keep_shown_unit(panel: Any, old_ppi: Any, skip: "str | None" = None
                     ) -> None:
    """The resolution moved from *old_ppi*: a side kept in the other kind
    of unit than the one shown (pixels against mm or inches) is first made
    the shown kind, at the resolution it was made for. So the unit on
    screen is what a new resolution keeps."""
    if not getattr(panel, "_units_choice", False) or not old_ppi:
        return
    truth = getattr(panel, "_page_truth", None)
    shown = getattr(panel, "_page_unit", po.UNIT_MM)
    if truth is None:
        return
    for a in _AXES:
        if a == skip:
            continue
        v, u = truth[a]
        if (u == po.UNIT_PX) != (shown == po.UNIT_PX):
            truth[a] = _side_in((v, u), shown, float(old_ppi))


def _other_units_text(panel: Any) -> str:
    """The page in the units its fields do not show, for the line under
    them: "1,4998 x 0,9996 in", "38,1 x 25,39 mm", or both for pixels
    (decimals in the UI language's own sign)."""
    if panel.paper is None:
        return ""
    code = panel.paper.currentData() or "A4"
    if code == "__custom__":
        w, h = custom_mm(panel)
    else:
        from workflow.layout_engine import papers
        try:
            w, h = papers.dimensions_mm(code)
        except ValueError:
            return ""
    mm_text = (f"{po.side_text(round(w, 2))} x {po.side_text(round(h, 2))} "
               f"{tr('mm')}")
    in_text = (f"{po.side_text(round(w / po.MM_PER_INCH, 4))} x "
               f"{po.side_text(round(h / po.MM_PER_INCH, 4))} {tr('in')}")
    unit = getattr(panel, "_page_unit", po.UNIT_MM)
    if unit == po.UNIT_MM:
        return in_text
    if unit == po.UNIT_IN:
        return mm_text
    return f"{mm_text} ({in_text})"


def fd9_entering(panel: Any) -> "dict | None":
    """The FD-9 is about to clamp the millimetre boxes to its own ranges:
    the typed sides, to give back when it is left (leftover a of 4.3.43)."""
    truth = getattr(panel, "_page_truth", None)
    if truth is None:
        return None
    return {"truth": {a: tuple(truth[a]) for a in _AXES},
            "unit": getattr(panel, "_page_unit", None)}


def fd9_left(panel: Any, saved: "dict | None") -> None:
    """The FD-9 was left and its ranges and boxes given back: the typed
    sides come back exactly as they were."""
    if not saved or getattr(panel, "_page_truth", None) is None:
        return
    panel._page_truth = dict(saved["truth"])
    panel._page_look = None
    panel._page_last_ppi = _ppi(panel)
    _show_truth(panel)


# ---- the truth and its displays ----------------------------------------------

def _ppi(panel: Any) -> int:
    try:
        return int(panel.dpi.value())
    except (AttributeError, RuntimeError):
        return 300


def _fit_ranges(panel: Any, ppi: int) -> None:
    """The pixel fields' range: from 1 pixel to the most a 2000 mm side can
    have at the highest resolution offered, WHATEVER the resolution on screen.

    NEVER WRITES THE TRUTH (re-review R3-a). The pixel fields used to stop
    where 2000 mm is at the resolution on screen, and a side typed in pixels
    beyond that after the resolution was lowered (or while a resolution was
    still being typed) became the top, for good: 18001 x 15001 pixels at
    72 ppi turned into 5669 x 5669 and stayed so when the resolution went
    back up; and at a low resolution a frame's pixels could not be typed at
    all, so the order of typing decided the result. Now any pixel count can
    be typed in any order and is kept exactly; whether it fits 1 to 2000 mm
    at the resolution set is said by the line under the fields and by
    Generate (:func:`size_problem`). The millimetre and inch fields still
    stop at 1 and 2000 mm (review F5)."""
    hi = int(po.CUSTOM_MM_MAX * float(po.DPI_MAX_ON) / po.MM_PER_INCH)
    for axis in _AXES:
        box = panel._page_px[axis]
        if (box.minimum(), box.maximum()) != (1, hi):
            blocked = box.blockSignals(True)
            box.setRange(1, hi)
            box.blockSignals(blocked)


def size_problem(panel: Any) -> "str | None":
    """The friendly words when the custom page, as typed, cannot be made at
    the resolution on screen (a side typed in pixels beyond 1 to 2000 mm),
    else None. The typed values are kept; this only says so (R3-a)."""
    if getattr(panel, "_page_truth", None) is None or panel.paper is None \
            or panel.paper.currentData() != "__custom__":
        return None
    t = panel._page_truth
    ps = po.make_page_size(t["w"], t["h"], _ppi(panel))
    return None if ps is None else po.size_problem(ps, _ppi(panel))


def _heal_truth(panel: Any) -> None:
    """A millimetre field written behind this module's back wins."""
    truth = getattr(panel, "_page_truth", None)
    if truth is None:
        return
    # compared at the resolution the fields were last DRAWN at: a resolution
    # changed since then has not reached them yet, and is not an overwrite
    ppi = getattr(panel, "_page_last_ppi", None) or _ppi(panel)
    for axis, box in (("w", panel.custom_w), ("h", panel.custom_h)):
        v, unit = truth[axis]
        # UNROUNDED, against half a step and a hair: Qt rounds a half up
        # (27.125 shows as 27.13) where Python's round() goes to even
        # (27.12), and comparing the two rounded values took a side typed as
        # 2170 pixels at 2032 ppi for an overwrite and turned it into
        # 27.13 mm, so a later resolution no longer kept its pixels (found
        # building the Units choice, 2026-11-17; 4.3.43 had it too)
        shown = po.to_mm(v, unit, ppi)
        if unit == po.UNIT_PX:
            # the mm field may be clamped to its range; the pixels are the
            # truth for as long as the field shows what they make
            shown = min(max(shown, box.minimum()), box.maximum())
        if abs(shown - box.value()) > 0.5 * 10 ** -box.decimals() + 1e-9:
            truth[axis] = (float(box.value()), po.UNIT_MM)


def _show_truth(panel: Any, only: "str | None" = None,
                skip_unit: "str | None" = None) -> None:
    """Show each side's truth in the two other units (never writes back)."""
    ppi = _ppi(panel)
    if only is None:
        _fit_ranges(panel, ppi)
        panel._page_last_ppi = ppi
    elif getattr(panel, "_page_last_ppi", None) not in (None, ppi):
        # one side typed while the other still shows an older resolution:
        # bring both up to date, the side typed is already the truth
        only = None
        _fit_ranges(panel, ppi)
        panel._page_last_ppi = ppi
    panel._page_syncing = True
    try:
        for axis in _AXES:
            if only is not None and axis != only:
                continue
            v, unit = panel._page_truth[axis]
            mm = po.to_mm(v, unit, ppi)
            boxes = {po.UNIT_MM: panel.custom_w if axis == "w" else panel.custom_h,
                     po.UNIT_IN: panel._page_in[axis],
                     po.UNIT_PX: panel._page_px[axis]}
            for u, box in boxes.items():
                if u == skip_unit:
                    continue
                if u == unit:
                    value = v
                elif u == po.UNIT_PX:
                    value = po.pixels_of(mm, ppi)
                else:
                    value = po.from_mm(mm, u, ppi)
                b = box.blockSignals(True)
                box.setValue(int(value) if u == po.UNIT_PX else value)
                box.blockSignals(b)
    finally:
        panel._page_syncing = False
    refresh_readout(panel)


def refresh(panel: Any) -> None:
    """After a change anywhere in the panel: the resolution may have moved,
    so the converted fields and the pixel line follow it."""
    if getattr(panel, "_page_truth", None) is None or \
            getattr(panel, "_page_syncing", False):
        return
    _heal_truth(panel)
    last = getattr(panel, "_page_last_ppi", None)
    if last != _ppi(panel):
        if last is not None:
            _keep_shown_unit(panel, last)
        _show_truth(panel)
        return
    refresh_readout(panel)


def custom_mm(panel: Any) -> "tuple[float, float]":
    """The custom page in millimetres, exact, from the typed sides."""
    _heal_truth(panel)
    ppi = _ppi(panel)
    t = panel._page_truth
    return (po.to_mm(t["w"][0], t["w"][1], ppi),
            po.to_mm(t["h"][0], t["h"][1], ppi))


def custom_paper_code(panel: Any) -> str:
    """The ``"<W>x<H>"`` code of the custom page (fractions kept), turned
    upright for the i1iO as `selection` does."""
    w, h = custom_mm(panel)
    if panel._i1io_chosen() and w > h:
        w, h = h, w
    return po.paper_code(w, h)


def page_size(panel: Any) -> "dict | None":
    """The stored form of the custom page (None when typed in mm only)."""
    _heal_truth(panel)
    t = panel._page_truth
    w, h = t["w"], t["h"]
    if panel._i1io_chosen() and custom_mm(panel)[0] > custom_mm(panel)[1]:
        w, h = h, w
    return po.make_page_size(w, h, _ppi(panel))


def page_pixels(panel: Any) -> "tuple[int, int] | None":
    """The page's pixel count at the resolution shown, or None."""
    if panel.paper is None:
        return None
    ppi = _ppi(panel)
    code = panel.paper.currentData() or "A4"
    if code == "__custom__":
        ps = page_size(panel)
        if ps is not None:
            return po.page_pixels(ps, ppi)
        w, h = custom_mm(panel)
    else:
        from workflow.layout_engine import papers
        try:
            w, h = papers.dimensions_mm(code)
        except ValueError:
            return None
    return po.pixels_of(w, ppi), po.pixels_of(h, ppi)


def needs_budget(panel: Any) -> bool:
    """True when the page on screen uses what only the Beta allows (a side
    typed in inches or pixels, a fraction of a millimetre, above 1200 dpi),
    so the memory budget applies (review F7, `po.needs_budget`)."""
    if panel.paper is None:
        return False
    code = panel.paper.currentData() or "A4"
    if code == "__custom__":
        return po.needs_budget(page_size=page_size(panel), dpi=_ppi(panel),
                               paper=custom_paper_code(panel))
    return po.needs_budget(dpi=_ppi(panel), paper=code)


def ink_kind(panel: Any) -> dict:
    """The chart's inks for the memory estimate (review F4): from the tab's
    Device Type when the panel has a source for it, else RGB."""
    source = getattr(panel, "page_ink_codes", None)
    try:
        codes = source() if callable(source) else None
    except Exception:      # noqa: BLE001 - an estimate never blocks
        codes = None
    return po.ink_kind(codes or ("r", "g", "b"))


def refresh_readout(panel: Any) -> None:
    """The pixel line: the count, and when it is over the budget (for a page
    only the Beta allows, with the chart's inks), why Generate will refuse
    it."""
    lbl = getattr(panel, "_page_px_lbl", None)
    if lbl is None:
        return
    from workflow import measurement_messages as mm
    px = page_pixels(panel)
    if px is None:
        lbl.setText("")
        return
    w, h = px
    pages = int(panel.pages.value()) if panel.pages is not None else 1
    bit16 = (panel.bit_depth.currentData() == 16
             if hasattr(panel, "bit_depth") else False)
    # no thousands separator in any language (review F8)
    if getattr(panel, "_units_choice", False):
        # the page in the units the fields do not show (the Units choice)
        text = tr(mm._PAGE_PIXELS_SIZE).format(
            w=po.number(w), h=po.number(h), mpx=po.decimal(w * h / 1e6),
            ppi=_ppi(panel), size=_other_units_text(panel))
    else:
        text = tr(mm._PAGE_PIXELS).format(
            w=po.number(w), h=po.number(h), mpx=po.decimal(w * h / 1e6),
            ppi=_ppi(panel))
    kind = dict(ink_kind(panel), bit16=bit16)
    over = needs_budget(panel) and \
        po.estimated_bytes(w, h, pages, **kind) > po.MEMORY_BUDGET_BYTES
    problem = size_problem(panel)
    if problem:
        # the typed size cannot be made at this resolution (R3-a): said,
        # never changed; the memory estimate of a page that will not be made
        # would only confuse
        text += " " + problem
        over = True
    elif over:
        text += " " + tr(mm._PAGE_PIXELS_OVER).format(
            limit=po.number(po.max_megapixels(pages, **kind)))
    from ui.widgets import set_ink
    set_ink(lbl, "#e05050" if over else "#909090", " font-size: 11px;",
            level="main" if over else "faint")
    lbl.setText(text)


# ---- recipes -------------------------------------------------------------------

def _shown_state(panel: Any) -> tuple:
    """What the four fields the hold watches show now."""
    return (panel.paper.currentData() if panel.paper is not None else None,
            float(panel.custom_w.value()), float(panel.custom_h.value()),
            int(panel.dpi.value()))


def load_recipe(panel: Any, r: Any) -> None:
    """A recipe was put into the panel (`_set_recipe_impl`, at its end)."""
    if getattr(panel, "_page_beta", False):
        if hasattr(panel, "tiff_res_unit"):
            i = panel.tiff_res_unit.findData(
                getattr(r, "tiff_res_unit", po.RES_UNIT_CM) or po.RES_UNIT_CM)
            panel.tiff_res_unit.setCurrentIndex(max(0, i))
        if panel.paper is not None and \
                panel.paper.currentData() == "__custom__":
            ps = po.clean_page_size(getattr(r, "page_size", None))
            if ps is not None:
                panel._page_truth = {a: (float(ps[a][0]), ps[a][1])
                                     for a in _AXES}
            else:
                from workflow.layout_engine import papers
                dims = papers.parse_custom(str(r.paper))
                if dims:
                    panel._page_truth = {"w": (float(dims[0]), po.UNIT_MM),
                                         "h": (float(dims[1]), po.UNIT_MM)}
            # the chart's own page, as stored, for the resolution it carries:
            # nothing typed yet, nothing to restore
            panel._page_last_ppi = _ppi(panel)
            panel._page_look = None
            _show_truth(panel)
        refresh_readout(panel)
        return
    # ---- Beta off: hold a chart's own page values ----------------------------
    _release(panel)
    if not po.uses_beta_values(r):
        return
    panel._page_hold = {
        "instrument": r.instrument, "paper": r.paper, "dpi": int(r.dpi),
        "page_size": po.clean_page_size(getattr(r, "page_size", None)),
        "tiff_res_unit": getattr(r, "tiff_res_unit", po.RES_UNIT_CM),
        "shown": _shown_state(panel)}
    _show_hold_note(panel, r)


def apply_to_recipe(panel: Any, r: Any) -> None:
    """`apply_to_recipe`'s last step for the page-output values."""
    if getattr(panel, "_page_beta", False):
        custom = (panel.paper is not None
                  and panel.paper.currentData() == "__custom__")
        r.page_size = page_size(panel) if custom else None
        r.tiff_res_unit = (panel.tiff_res_unit.currentData()
                           if hasattr(panel, "tiff_res_unit")
                           else po.RES_UNIT_CM) or po.RES_UNIT_CM
        if r.instrument == "FD9":
            # the FD-9's contributed layout writes pixels per centimetre
            # whatever is asked (review F3), so its recipe says so too
            r.tiff_res_unit = po.RES_UNIT_CM
        return
    hold = panel.__dict__.get("_page_hold")
    if not hold:
        return
    if _shown_state(panel) != hold["shown"]:
        # the person changed the paper, the size or the resolution: theirs
        _release(panel)
        return
    if r.instrument != hold["instrument"]:
        return
    r.paper = hold["paper"]
    r.dpi = hold["dpi"]
    r.page_size = hold["page_size"]
    r.tiff_res_unit = hold["tiff_res_unit"]


def hold_active(panel: Any) -> bool:
    """True while a Beta chart's own page values are held (Beta off)."""
    hold = panel.__dict__.get("_page_hold")
    return bool(hold) and _shown_state(panel) == hold["shown"]


def hold_refusal(panel: Any) -> "str | None":
    """The words that refuse Generate while a held chart needs the Beta
    (a size in inches or pixels, above 1200, or pixels per inch), else None.
    A chart held only for its fractions of a millimetre is not refused: the
    engine makes it at its own size, as it always could."""
    if not hold_active(panel):
        return None
    hold = panel.__dict__["_page_hold"]
    if hold["page_size"] is None and int(hold["dpi"]) <= po.DPI_MAX_OFF \
            and (hold["tiff_res_unit"] or po.RES_UNIT_CM) == po.RES_UNIT_CM:
        return None
    from workflow import measurement_messages as mm
    return tr(mm._PAGE_BETA_OFF_REDRAW)


def _release(panel: Any) -> None:
    panel.__dict__.pop("_page_hold", None)
    lbl = panel.__dict__.get("_page_hold_lbl")
    if lbl is not None:
        try:
            lbl.setVisible(False)
        except RuntimeError:
            pass


def describe_page(r: Any) -> str:
    """The page as it was typed, for the notes: "4096 x 2730 pixels",
    "9.25 x 7.75 inches", "234.95 x 196.85 mm" (with the decimal sign of the
    UI language)."""
    from workflow.layout_engine import papers
    ps = po.clean_page_size(getattr(r, "page_size", None))
    if ps is not None:
        return po.typed_text(ps)
    try:
        w, h = papers.dimensions_mm(str(r.paper))
        return f"{po.side_text(w)} x {po.side_text(h)} {tr('mm')}"
    except ValueError:
        return str(r.paper)


def describe_paper_for_readout(paper_flag: str, recipe: Any = None) -> str:
    """The page for the patch set editor's status line ("... laid out for
    the X on {paper}"): a page typed in inches or pixels as it was typed,
    with its resolution ("4096 x 2730 pixels at 2731 pixels per inch"); a
    custom size with fractions of a millimetre in millimetres with the UI
    language's decimal sign. Anything else (every chart 4.3.42 makes) is
    *paper_flag* exactly as before, and so is a recipe that is no longer
    the page the editor shows (its paper changed there since)."""
    try:
        from workflow.layout_engine import papers
        shown = papers.parse_custom(str(paper_flag or ""))
        mine = papers.parse_custom(str(getattr(recipe, "paper", "") or ""))
        if shown is None or mine is None or any(
                abs(float(a) - float(b)) > 0.051 for a, b in zip(shown, mine)):
            return paper_flag
        ps = po.clean_page_size(getattr(recipe, "page_size", None))
        if ps is not None:
            return tr("{size} at {ppi} pixels per inch").format(
                size=describe_page(recipe), ppi=int(getattr(recipe, "dpi", 0)
                                                    or ps["ppi"]))
        code = str(getattr(recipe, "paper", "") or "")
        if not po.is_whole_mm_code(code):
            return f"{po.side_text(mine[0])} x {po.side_text(mine[1])} {tr('mm')}"
    except Exception:  # noqa: BLE001 - a status line never breaks the editor
        pass
    return paper_flag


def _show_hold_note(panel: Any, r: Any) -> None:
    from PyQt6.QtWidgets import QLabel
    from workflow import measurement_messages as mm
    only_fraction = (po.clean_page_size(getattr(r, "page_size", None)) is None
                     and int(r.dpi) <= po.DPI_MAX_OFF
                     and (getattr(r, "tiff_res_unit", "cm") or "cm") == "cm")
    text = tr(mm._PAGE_BETA_OFF_NOTE_KEPT if only_fraction
              else mm._PAGE_BETA_OFF_NOTE_REFUSED).format(
        size=describe_page(r), ppi=int(r.dpi))
    lbl = panel.__dict__.get("_page_hold_lbl")
    if lbl is None:
        grid = getattr(panel, "_sel_grid", None)
        lbl = QLabel("", panel)
        lbl.setWordWrap(True)
        from ui.widgets import set_ink
        set_ink(lbl, "#e6a23c", " font-size: 11px;", level="main")
        if grid is not None:
            grid.addWidget(lbl, 4, 0, 1, 4)
        panel._page_hold_lbl = lbl
    lbl.setText(text)
    lbl.setVisible(True)
    try:
        panel.notice.emit(text)
    except (AttributeError, RuntimeError):
        pass


# ---- help ------------------------------------------------------------------------

def custom_size_help() -> str:
    """The (i) beside the custom size rows (Beta on)."""
    return "\n\n".join((
        tr("Type the size of your page in whichever unit you have it in: "
           "millimetres, inches, or an exact number of pixels. The other two "
           "rows show the same size converted, so you can check it."),
        tr("The fields you type in are the ones that count. If you type a "
           "width of 4096 pixels, the chart is exactly 4096 pixels wide, and "
           "the millimetres and inches beside it are only shown for "
           "information. You can mix units: a width in pixels and a height in "
           "inches is fine."),
        tr("Each side can be from 1 mm to 2000 mm, whichever unit you type "
           "it in, and the millimetre and inch fields go no further. The "
           "pixel fields take any count, whether you type it before or after "
           "the resolution, and keep it exactly as you typed it: if it would "
           "make a side longer "
           "than 2000 mm (or shorter than 1 mm) at the resolution you have "
           "set, the line under the paper size says so in red and names the "
           "resolutions that fit, and Generate makes no chart until the "
           "resolution or the size fits."),
        tr("The resolution is taken when you press Return or leave its box, "
           "not while you are still typing, so typing 2032 never passes "
           "through 203 on the way."),
        tr("Pixels and resolution belong together. A size typed in pixels "
           "keeps its pixels when you change the resolution, so the page "
           "becomes larger or smaller on paper. A size typed in millimetres "
           "or inches keeps its size on paper, and its pixel count follows "
           "the resolution. The line under the paper size always shows how "
           "many pixels the page will have."),
        tr("This is a beta option (Preferences, Beta tab).")))


def _length_in_note() -> str:
    """The note an (i) of a length field carries while inches are shown."""
    return tr("You have chosen inches under Units, at the top of this panel, "
              "so this field shows inches. ChromIQ still keeps the value in "
              "millimetres, exactly as before, so the millimetre figures in "
              "this help still apply (25.4 mm make one inch), and the grey "
              "figure beside the field, where there is one, shows the "
              "millimetres.")


def units_help() -> str:
    """The (i) of "Units:" (Beta on)."""
    return "\n\n".join((
        tr("Choose the unit you want to work in. It applies to every length "
           "in this panel: the custom page size, the margins, the patch size, "
           "the gaps and every other size below. ChromIQ remembers your "
           "choice for next time. It is your own preference: it is not saved "
           "with a chart, a preset or a profile project, so a chart is the "
           "same whichever unit you look at it in."),
        tr("Millimetres and inches only change what you see. ChromIQ keeps "
           "every length in millimetres, as it always has: if you type 0.25 "
           "inches it stores 6.35 mm and shows 0.25 again, and switching "
           "between the two never changes a value you have not typed."),
        tr("Pixels is for the custom page size only, for example the exact "
           "frame a film recorder takes. With pixels chosen, the page is the "
           "number of pixels you type, and all the other fields show "
           "millimetres."),
        tr("The unit you see is the one that is kept when you change the "
           "resolution. With pixels chosen, the pixel count stays and the "
           "page becomes larger or smaller on paper. With millimetres or "
           "inches chosen, the size on paper stays and the pixel count "
           "follows the resolution. Switching to pixels rounds the page to "
           "whole pixels. If you switch back without typing anything, you "
           "get exactly the size you had before, so just looking never "
           "changes your page."),
        tr("This is a beta option (Preferences, Beta tab).")))


def custom_size_help_units() -> str:
    """The (i) beside the custom size with the Units choice (Beta on)."""
    return "\n\n".join((
        tr("Type the width and height of your page in the unit chosen under "
           "Units, just above: millimetres, inches, or an exact number of "
           "pixels. The line under the fields shows the same page in the "
           "other units and how many pixels it will have, so you can check "
           "it."),
        tr("Each side can be from 1 mm to 2000 mm, whichever unit you type "
           "it in, and the millimetre and inch fields go no further. The "
           "pixel fields take any count, whether you type it before or after "
           "the resolution, and keep it exactly as you typed it: if it would "
           "make a side longer "
           "than 2000 mm (or shorter than 1 mm) at the resolution you have "
           "set, the line under the paper size says so in red and names the "
           "resolutions that fit, and Generate makes no chart until the "
           "resolution or the size fits."),
        tr("The resolution is taken when you press Return or leave its box, "
           "not while you are still typing, so typing 2032 never passes "
           "through 203 on the way."),
        tr("The unit you see is the one that is kept when you change the "
           "resolution. With pixels chosen, the pixel count stays and the "
           "page becomes larger or smaller on paper. With millimetres or "
           "inches chosen, the size on paper stays and the pixel count "
           "follows the resolution. Switching to pixels rounds the page to "
           "whole pixels. If you switch back without typing anything, you "
           "get exactly the size you had before, so just looking never "
           "changes your page."),
        tr("This is a beta option (Preferences, Beta tab).")))


def res_unit_help() -> str:
    """The (i) of Output > "Resolution unit:" (Beta on)."""
    return "\n\n".join((
        tr("Every chart image carries its resolution, so that a program "
           "opening it knows how large to print it. The size on paper is the "
           "same either way; only the unit written into the file differs."),
        tr("Pixels per centimetre (the default) is what ArgyllCMS writes, and "
           "what ChromIQ has always written."),
        tr("Pixels per inch writes the resolution exactly as you set it, as a "
           "whole number per inch: a chart made at 2731 dpi reads back as "
           "exactly 2731 pixels per inch. Choose it when the program or "
           "machine that takes the file reads the resolution from it and "
           "expects pixels per inch, for example a film recorder, which "
           "would otherwise scale the picture."),
        tr("This is a beta option (Preferences, Beta tab).")))
