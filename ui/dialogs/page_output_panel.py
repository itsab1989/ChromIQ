"""Create Chart's layout panel, the page-output Beta's part (#215).

Only built while Preferences > Beta > "Custom page size in inches or pixels,
and high resolution" is on (`workflow.page_output.support`), and only in the
panels that choose a page (Create Chart > Manual, the re-layout window). With
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
        box.setRange(0.01, 99999.0)
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
    for row, (unit, wbox, hbox, word) in enumerate(rows):
        grid.addWidget(wbox, row, 1)
        grid.addWidget(QLabel("×", panel), row, 2)
        grid.addWidget(hbox, row, 3)
        grid.addWidget(QLabel(word, panel), row, 4)
    panel._page_size_tip = TooltipButton(
        tr("Custom size"), custom_size_help(), panel, min_width=620)
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


# ---- the truth and its displays ----------------------------------------------

def _ppi(panel: Any) -> int:
    try:
        return int(panel.dpi.value())
    except (AttributeError, RuntimeError):
        return 300


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
        shown = round(po.to_mm(v, unit, ppi), box.decimals())
        if unit == po.UNIT_PX:
            # the mm field may be clamped to its range; the pixels are the
            # truth for as long as the field shows what they make
            shown = min(max(shown, box.minimum()), box.maximum())
        if abs(shown - box.value()) > 0.5 * 10 ** -box.decimals():
            truth[axis] = (float(box.value()), po.UNIT_MM)


def _show_truth(panel: Any, only: "str | None" = None,
                skip_unit: "str | None" = None) -> None:
    """Show each side's truth in the two other units (never writes back)."""
    ppi = _ppi(panel)
    if only is None:
        panel._page_last_ppi = ppi
    elif getattr(panel, "_page_last_ppi", None) not in (None, ppi):
        # one side typed while the other still shows an older resolution:
        # bring both up to date, the side typed is already the truth
        only = None
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
    if getattr(panel, "_page_last_ppi", None) != _ppi(panel):
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


def refresh_readout(panel: Any) -> None:
    """The pixel line: the count, and when it is over the budget, why
    Generate will refuse it."""
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
    text = tr(mm._PAGE_PIXELS).format(
        w=f"{w:,}", h=f"{h:,}", mpx=f"{w * h / 1e6:,.1f}", ppi=_ppi(panel))
    over = po.estimated_bytes(w, h, pages, bit16=bit16) > \
        po.MEMORY_BUDGET_BYTES
    if over:
        text += " " + tr(mm._PAGE_PIXELS_OVER).format(
            limit=f"{po.max_megapixels(pages, bit16=bit16):,.0f}")
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


def _release(panel: Any) -> None:
    panel.__dict__.pop("_page_hold", None)
    lbl = panel.__dict__.get("_page_hold_lbl")
    if lbl is not None:
        try:
            lbl.setVisible(False)
        except RuntimeError:
            pass


def describe_page(r: Any) -> str:
    """The page as it was typed, for the notes: "4,096 x 2,730 pixels",
    "9.25 x 7.75 inches", "234.95 x 196.85 mm"."""
    from workflow.layout_engine import papers
    ps = po.clean_page_size(getattr(r, "page_size", None))

    def num(v: float) -> str:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    if ps is not None and ps["w"][1] == ps["h"][1]:
        unit = ps["w"][1]
        word = {po.UNIT_PX: tr("pixels"), po.UNIT_IN: tr("inches"),
                po.UNIT_MM: tr("mm")}[unit]
        return f"{num(ps['w'][0])} x {num(ps['h'][0])} {word}"
    if ps is not None:
        words = {po.UNIT_PX: tr("px"), po.UNIT_IN: tr("in"), po.UNIT_MM: tr("mm")}
        return (f"{num(ps['w'][0])} {words[ps['w'][1]]} x "
                f"{num(ps['h'][0])} {words[ps['h'][1]]}")
    try:
        w, h = papers.dimensions_mm(str(r.paper))
        return f"{num(w)} x {num(h)} {tr('mm')}"
    except ValueError:
        return str(r.paper)


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
        tr("Pixels and resolution belong together. A size typed in pixels "
           "keeps its pixels when you change the resolution, so the page "
           "becomes larger or smaller on paper. A size typed in millimetres "
           "or inches keeps its size on paper, and its pixel count follows "
           "the resolution. The line under the paper size always shows how "
           "many pixels the page will have."),
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
