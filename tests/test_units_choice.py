"""THE PAGE-OUTPUT BETA'S "UNITS" CHOICE (after 4.3.43, agreed with the owner).

Create Chart > Manual, with the Beta "Custom page size in inches or pixels,
and high resolution" on, has ONE "Units" combobox under Paper: millimetres,
inches, or pixels (the page size only). What is pinned here:

1. with millimetres chosen, nothing new used, every length field is 4.3.43's
   (range, step, decimals, value, suffix) and the recipe is the plain
   panel's, bit for bit;
2. the page size is one pair of fields in the chosen unit, and the unit shown
   is what a new resolution keeps; switching mm <-> in never changes the
   page, switching to pixels makes it whole pixels, and switching back
   without typing restores exactly what was there;
3. his three film frames, in every order of choosing the unit, typing the
   size and typing the resolution, are pixel-exact; 400 random pixel pages;
4. every other length is shown in inches as a DISPLAY: typing 0.25 in
   stores 6.35 mm and shows 0.25 again (1000 random values); a stored value
   looked at in inches is never moved; a recipe read with inches chosen is
   the recipe read with millimetres chosen (what a preset saves);
5. charts made by 4.3.43 (pixels, inches, fractional millimetres) open and
   give back their recipe unchanged, whatever unit is chosen;
6. the choice is a personal preference in AppSettings, never in a recipe;
7. the FD-9 there and back keeps a page typed in pixels (leftover a);
8. the printer edge note skips a page too large for Pillow with words
   (leftover c). Leftover b is in `test_page_output_beta_editor.py`.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.page_output import support as po          # noqa: E402

FRAMES = [((4096, 2730), 2731), ((8192, 5460), 5461), ((18796, 15748), 2032)]


@pytest.fixture
def beta_on():
    before = po._latched
    po.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        po._latched = before


def _panel(units_choice=True, unit=None):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    if unit is not None:
        from core.settings import AppSettings
        AppSettings().set("page_output_units", unit)
    return LayoutOptionsPanel(None, with_selectors=True, with_calibration=True,
                              units_choice=units_choice)


@pytest.fixture
def units_store():
    """The stored choice put back after the test (the suite's settings are
    a per-process sandbox, but other tests in the worker read it too)."""
    from core.settings import AppSettings
    s = AppSettings()
    before = s.get("page_output_units", "mm")
    try:
        yield s
    finally:
        s.set("page_output_units", before)


@pytest.fixture
def panel(qapp, beta_on, units_store):
    p = _panel(unit="mm")
    p.paper.setCurrentIndex(p.paper.findData("__custom__"))
    yield p
    p.deleteLater()


def _choose(p, unit):
    p.units.setCurrentIndex(p.units.findData(unit))


def _type(box, text):
    """Type *text* over the box's number (no focus taken) and take it."""
    box.lineEdit().setText(text)
    box.interpretText()


def _type_dpi(p, qapp, text):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    seen = []
    p.dpi.valueChanged.connect(seen.append)
    p.dpi.lineEdit().selectAll()
    for ch in text:
        QTest.keyClick(p.dpi, ch)
        qapp.processEvents()
    QTest.keyClick(p.dpi, Qt.Key.Key_Return)
    qapp.processEvents()
    p.dpi.valueChanged.disconnect(seen.append)
    return seen


def _set_px(p, w, h):
    # set twice, so the value differs from what the box showed: typed
    p._page_px["w"].setValue(w + 1)
    p._page_px["w"].setValue(w)
    p._page_px["h"].setValue(h + 1)
    p._page_px["h"].setValue(h)


def _page(p):
    """What the recipe stores for the custom page (paper code, page_size,
    resolution): `apply_to_recipe`'s own functions, without the whole
    recipe (a thousand of those take minutes)."""
    from ui.dialogs import page_output_panel as pop
    return (pop.custom_paper_code(p), pop.page_size(p), int(p.dpi.value()))


def _length_fields(p):
    """name -> the plain QDoubleSpinBox state of every length field."""
    from PyQt6.QtWidgets import QDoubleSpinBox
    out = {}
    for name, box in vars(p).items():
        boxes = box.items() if isinstance(box, dict) else [("", box)]
        for k, b in boxes:
            if isinstance(b, QDoubleSpinBox):
                out[f"{name}{k}"] = (b.minimum(), b.maximum(), b.singleStep(),
                                     b.decimals(), b.value(), b.suffix(),
                                     b.specialValueText(), b.text())
    return out


# ---- 1. millimetres chosen, nothing new used: 4.3.43 ---------------------------

def test_millimetres_chosen_every_field_is_the_plain_panels(qapp, beta_on,
                                                            units_store):
    plain = _panel(units_choice=False)
    mine = _panel(unit="mm")
    try:
        a, b = _length_fields(plain), _length_fields(mine)
        assert set(a) == set(b) and len(a) > 25
        for k in a:
            assert a[k] == b[k], k
        assert plain.get_recipe().to_dict() == mine.get_recipe().to_dict()
        # the boxes the choice reaches are its own kind; the plain panel's not
        from ui.dialogs.length_units import LengthSpinBox
        assert not plain.findChildren(LengthSpinBox)
        assert len(mine._length_boxes) >= 25
    finally:
        plain.deleteLater()
        mine.deleteLater()


def test_the_choice_sits_under_paper_and_only_where_it_is_asked(qapp,
                                                               beta_on):
    p = _panel()
    q = _panel(units_choice=False)
    try:
        grid = p._sel_grid
        assert grid.getItemPosition(grid.indexOf(p.units))[:2] == (2, 1)
        assert grid.getItemPosition(grid.indexOf(p.paper))[:2] == (1, 1)
        assert [p.units.itemData(i) for i in range(p.units.count())] == [
            "mm", "in", "px"]
        assert not hasattr(q, "units")
        # the tab asks for it; the patch set editor's hidden copy does not
        import inspect
        from ui.dialogs import ti2_relayout_dialog
        from ui.tabs import tab_chart
        assert "units_choice=True" in inspect.getsource(tab_chart)
        assert "units_choice" not in inspect.getsource(ti2_relayout_dialog)
    finally:
        p.deleteLater()
        q.deleteLater()


def test_with_the_beta_off_there_is_no_choice(qapp, units_store):
    before = po._latched
    po.set_enabled_for_this_process(False)
    try:
        p = _panel()
        assert not hasattr(p, "units") and p._units_choice is False
        from ui.dialogs.length_units import LengthSpinBox
        assert not p.findChildren(LengthSpinBox)
        p.deleteLater()
    finally:
        po._latched = before


# ---- 2. the page size ------------------------------------------------------------

def test_one_pair_of_fields_in_the_unit_chosen(panel):
    p = panel
    for unit in ("mm", "in", "px", "mm"):
        _choose(p, unit)
        for u, widgets in p._page_rows.items():
            assert all(w.isHidden() != (u == unit) for w in widgets), (unit, u)


@pytest.mark.parametrize("n", [
    100, pytest.param(1000, marks=pytest.mark.slow)])
def test_mm_in_mm_and_in_mm_in_never_change_the_page(panel, n):
    """1000 random sizes in the slow tier (about six minutes on one worker:
    every switch redraws the whole panel), 100 in the everyday tier."""
    p = panel
    rnd = random.Random(215)
    for _ in range(n):
        dpi = rnd.choice((72, 300, 1200, 2032, 2731, 5461, 6000))
        p.dpi.setValue(dpi)
        start = rnd.choice(("mm", "in"))
        _choose(p, start)
        if start == "mm":
            p.custom_w.setValue(round(rnd.uniform(1, 2000), 2))
            p.custom_h.setValue(round(rnd.uniform(1, 2000), 2))
        else:
            p._page_in["w"].setValue(round(rnd.uniform(0.04, 78.7), 4))
            p._page_in["h"].setValue(round(rnd.uniform(0.04, 78.7), 4))
        truth = dict(p._page_truth)
        page = _page(p)
        other = "in" if start == "mm" else "mm"
        _choose(p, other)
        assert p._page_truth == truth
        assert _page(p) == page
        _choose(p, start)
        assert p._page_truth == truth
        assert _page(p) == page


def test_mm_px_mm_without_typing_restores_exactly(panel):
    p = panel
    rnd = random.Random(43)
    for _ in range(200):
        _choose(p, "mm")
        p.dpi.setValue(rnd.choice((300, 2032, 2731)))
        p.custom_w.setValue(round(rnd.uniform(10, 300), 2))
        p.custom_h.setValue(round(rnd.uniform(10, 300), 2))
        page = _page(p)
        truth = dict(p._page_truth)
        _choose(p, "px")
        # the page IS whole pixels now, the renderer's count of the size
        ps = _page(p)[1]
        w, h = (po.pixels_of(v, p.dpi.value()) for v, _ in truth.values())
        assert ps["w"] == [w, "px"] and ps["h"] == [h, "px"]
        # through inches too: still only looking
        _choose(p, "in")
        _choose(p, "mm")
        assert p._page_truth == truth
        assert _page(p) == page
    # and the whole recipe, once
    recipe = p.get_recipe().to_dict()
    _choose(p, "px")
    _choose(p, "mm")
    assert p.get_recipe().to_dict() == recipe


def test_mm_px_type_mm_gives_the_pixel_pages_size(panel):
    p = panel
    p.dpi.setValue(2731)
    p.custom_w.setValue(40)
    _choose(p, "px")
    _set_px(p, 4096, 2730)
    _choose(p, "mm")
    r = p.get_recipe()
    assert r.page_size is None
    assert r.paper == "38.0953x25.3907"
    assert po.pixels_of(38.0953, 2731) == 4096
    assert p.custom_w.value() == pytest.approx(38.10)
    # and a resolution changed now keeps the size on paper (mm shown)
    p.dpi.setValue(5461)
    p._emit()
    assert p.get_recipe().paper == "38.0953x25.3907"


def test_the_unit_shown_is_what_a_new_resolution_keeps(panel, qapp):
    p = panel
    p.dpi.setValue(2731)
    _choose(p, "px")
    _set_px(p, 4096, 2730)
    for d in (72, 6000, 1200):
        p.dpi.setValue(d)
        p._emit()
        assert (p._page_px["w"].value(), p._page_px["h"].value()) == (4096, 2730)
    p.dpi.setValue(2731)
    p._emit()
    _choose(p, "in")
    paper = p.get_recipe().paper
    p.dpi.setValue(300)
    p._emit()
    assert p.get_recipe().paper == paper            # the size on paper stays
    assert p._page_px["w"].value() == po.pixels_of(38.0953, 300)


def test_a_loaded_pixel_page_shown_in_mm_keeps_the_size_on_a_new_resolution(
        panel):
    """A pixel page the person chooses to look at in millimetres keeps its
    size on paper on a new resolution (the unit shown is kept). The chart
    opens showing pixels (review P1-7), so this takes the choice of mm."""
    from workflow.layout_engine.presets import default_recipe
    p = panel
    frame = {"w": [4096, "px"], "h": [2730, "px"], "ppi": 2731}
    p.set_recipe(replace(default_recipe("SS", "38.0953x25.3907"), dpi=2731,
                         page_size=frame))
    assert p.get_recipe().page_size == frame        # as stored, untouched
    _choose(p, "mm")
    p.dpi.setValue(1200)
    p._emit()
    r = p.get_recipe()
    assert r.page_size is None and r.paper == "38.0953x25.3907"


# ---- 3. his three frames, every order ------------------------------------------

@pytest.mark.parametrize("order", [
    "unit_size_res", "unit_res_size", "res_unit_size", "size_mm_then_unit",
    "unit_size_res_typed", "res_down_up", "look_around"])
@pytest.mark.parametrize("frame", FRAMES)
def test_his_three_frames_in_every_order(qapp, beta_on, units_store, frame,
                                         order):
    (w, h), ppi = frame
    p = _panel(unit="mm")
    try:
        p.paper.setCurrentIndex(p.paper.findData("__custom__"))
        if order == "unit_size_res":
            p.dpi.setValue(300)
            _choose(p, "px")
            _set_px(p, w, h)
            p.dpi.setValue(ppi)
        elif order == "unit_res_size":
            _choose(p, "px")
            p.dpi.setValue(ppi)
            _set_px(p, w, h)
        elif order == "res_unit_size":
            p.dpi.setValue(ppi)
            _choose(p, "px")
            _set_px(p, w, h)
        elif order == "size_mm_then_unit":
            # typed as millimetres first, then the pixels: the pixels count
            p.dpi.setValue(ppi)
            p.custom_w.setValue(50)
            _choose(p, "px")
            _set_px(p, w, h)
        elif order == "unit_size_res_typed":
            p.dpi.setValue(300)
            _choose(p, "px")
            _set_px(p, w, h)
            assert _type_dpi(p, qapp, str(ppi)) == [ppi]
        elif order == "res_down_up":
            _choose(p, "px")
            p.dpi.setValue(ppi)
            _set_px(p, w, h)
            for d in (72, 150, 6000, 72):
                p.dpi.setValue(d)
                p._emit()
            assert _type_dpi(p, qapp, str(ppi)) == [ppi]
        else:   # looking at the other units changes nothing
            _choose(p, "px")
            p.dpi.setValue(ppi)
            _set_px(p, w, h)
            for u in ("mm", "in", "px", "in", "mm", "px"):
                _choose(p, u)
        p._emit()
        r = p.get_recipe()
        assert r.dpi == ppi
        assert r.page_size == {"w": [w, "px"], "h": [h, "px"], "ppi": ppi}
        assert po.page_pixels(r.page_size, r.dpi) == (w, h)
        assert (p._page_px["w"].value(), p._page_px["h"].value()) == (w, h)
        assert f"{w} x {h} pixels" in p._page_px_lbl.text()
    finally:
        p.deleteLater()


@pytest.mark.parametrize("n", [
    60, pytest.param(400, marks=pytest.mark.slow)])
def test_400_random_pixel_pages(panel, n):
    """400 in the slow tier (about four and a half minutes), 60 everyday."""
    p = panel
    _choose(p, "px")
    rnd = random.Random(400)
    for _ in range(n):
        ppi = rnd.randint(72, 6000)
        w = rnd.randint(max(1, int(ppi / 25.4) + 1), int(2000 * ppi / 25.4))
        h = rnd.randint(max(1, int(ppi / 25.4) + 1), int(2000 * ppi / 25.4))
        p.dpi.setValue(ppi)
        _set_px(p, w, h)
        r = p.get_recipe()
        assert r.page_size == {"w": [w, "px"], "h": [h, "px"], "ppi": ppi}
        assert po.page_pixels(r.page_size, ppi) == (w, h)
        # its paper code makes the same pixels at the same resolution
        from workflow.layout_engine import papers
        wm, hm = papers.parse_custom(r.paper)
        assert (po.pixels_of(wm, ppi), po.pixels_of(hm, ppi)) == (w, h)


@pytest.mark.parametrize("units_choice", [True, False])
def test_a_pixel_side_on_a_half_hundredth_stays_pixels(qapp, beta_on,
                                                     units_store,
                                                     units_choice):
    """2170 px at 2032 ppi is 27.125 mm: Qt shows 27.13, Python rounds to
    27.12, and comparing the two took the pixels for an overwrite (found
    while building this; 4.3.43 had it): the next resolution then kept
    millimetres instead of the pixels typed."""
    p = _panel(units_choice=units_choice, unit="px")
    try:
        p.paper.setCurrentIndex(p.paper.findData("__custom__"))
        p.dpi.setValue(2032)
        _set_px(p, 2170, 2170)
        p._emit()
        assert p._page_truth == {"w": (2170.0, "px"), "h": (2170.0, "px")}
        p.dpi.setValue(300)
        p._emit()
        assert p._page_truth == {"w": (2170.0, "px"), "h": (2170.0, "px")}
        assert p.get_recipe().page_size["w"] == [2170, "px"]
    finally:
        p.deleteLater()


def test_out_of_range_pixels_are_kept_and_refused_with_words(panel):
    from ui.dialogs import page_output_panel as pop
    p = panel
    _choose(p, "px")
    p.dpi.setValue(2032)
    _set_px(p, 18001, 15001)
    p.dpi.setValue(72)
    p._emit()
    assert p._page_truth == {"w": (18001.0, "px"), "h": (15001.0, "px")}
    assert "between 229 and 6000 pixels per inch" in p._page_px_lbl.text()
    assert pop.size_problem(p)
    p.dpi.setValue(2032)
    p._emit()
    assert pop.size_problem(p) is None
    assert p.get_recipe().page_size["w"] == [18001, "px"]


def test_the_line_says_the_page_in_the_other_units(panel):
    p = panel
    p.dpi.setValue(2731)
    _choose(p, "px")
    _set_px(p, 4096, 2730)
    assert ("4096 x 2730 pixels (11.2 megapixels) at 2731 pixels per inch, "
            "which is 38.1 x 25.39 mm (1.4998 x 0.9996 in)."
            in p._page_px_lbl.text())
    _choose(p, "in")
    assert "which is 38.1 x 25.39 mm." in p._page_px_lbl.text()
    _choose(p, "mm")
    assert "which is 1.4998 x 0.9996 in." in p._page_px_lbl.text()
    p.paper.setCurrentIndex(p.paper.findData("A4"))
    p.dpi.setValue(300)
    p._emit()
    assert "2480 x 3508 pixels" in p._page_px_lbl.text()
    assert "8.2677 x 11.6929 in" in p._page_px_lbl.text()


def test_the_line_follows_the_language(panel, monkeypatch):
    import core.i18n as i18n
    monkeypatch.setattr(i18n, "decimal_text",
                        lambda v, places=None: (
                            f"{v:.{places}f}" if places is not None
                            else str(v)).replace(".", ","))
    p = panel
    p.dpi.setValue(2731)
    _choose(p, "px")
    _set_px(p, 4096, 2730)
    text = p._page_px_lbl.text()
    assert "38,1 x 25,39 mm (1,4998 x 0,9996" in text
    assert "4096 x 2730" in text


# ---- 4. the other lengths: inches as a display ------------------------------------

def test_typing_inches_stores_exact_millimetres_1000_values(panel):
    p = panel
    _choose(p, "in")
    rnd = random.Random(254)
    boxes = [p.margins["t"], p.margins["l"], p.inter_patch, p.strip_gap,
             p.offx, p.text_edge, p.clip_width, p.strip_label_offset]
    for _ in range(1000):
        box = rnd.choice(boxes)
        lo = max(box.minimum(), 0.0) / 25.4
        hi = box.maximum() / 25.4
        x = round(rnd.uniform(lo, hi - 0.001), 3)
        if x * 25.4 <= box.minimum() and box.specialValueText():
            continue
        _type(box, f"{x:.3f}".replace(".", rnd.choice((".", ","))) + box.suffix())
        assert box.value() == pytest.approx(round(x * 25.4, 4), abs=1e-9)
        assert box.value() == float(f"{x * 25.4:.4f}")
        assert box.textFromValue(box.value()) .replace(",", ".") == f"{x:.3f}"
        # Return again with nothing typed: the value does not move
        before = box.value()
        box.interpretText()
        assert box.value() == before


def test_quarter_inch_is_6_35_mm_in_the_recipe(panel):
    p = panel
    _choose(p, "in")
    _type(p.margins["t"], "0.25")
    assert p.margins["t"].value() == 6.35
    assert p.margins["t"].text().replace(",", ".") == "0.250"
    assert p.get_recipe().margin_top == 6.35
    _choose(p, "mm")            # kept, shown with the decimals it needs
    assert p.margins["t"].value() == 6.35
    assert p.margins["t"].text().replace(",", ".") == "6.35"
    _choose(p, "in")
    assert p.margins["t"].text().replace(",", ".") == "0.250"
    assert p.get_recipe().margin_top == 6.35


def test_a_stored_value_looked_at_in_inches_never_moves(panel):
    p = panel
    from PyQt6.QtWidgets import QDoubleSpinBox
    rnd = random.Random(7)
    for _ in range(1000):
        box = rnd.choice(p._length_boxes)
        _choose(p, "mm")
        if not box.isEnabled():
            continue
        v = round(rnd.uniform(box.minimum(), box.maximum()), box.decimals())
        box.setValue(v)
        stored = box.value()
        _choose(p, "in")
        box.interpretText()             # Return / leaving with nothing typed
        assert box.value() == stored
        _choose(p, "mm")
        assert box.value() == stored
        assert isinstance(box, QDoubleSpinBox)


def test_arrows_step_a_hundredth_of_an_inch(panel):
    p = panel
    _choose(p, "in")
    box = p.margins["t"]
    _type(box, "0.25")
    box.stepBy(1)
    assert box.value() == float(f"{0.26 * 25.4:.4f}")
    box.stepBy(-3)
    assert box.value() == float(f"{0.23 * 25.4:.4f}")


def test_a_recipe_read_in_inches_is_the_recipe_read_in_mm(qapp, beta_on,
                                                          units_store):
    """What a preset saves is the panel's recipe: loading any recipe with
    inches chosen gives back exactly what millimetres give back, values
    the boxes round included."""
    from workflow.layout_engine.presets import default_recipe
    mm_p = _panel(unit="mm")
    in_p = _panel(unit="in")
    try:
        assert in_p.margins["t"].length_unit() == "in"
        rnd = random.Random(3)
        insts = [mm_p.instr.itemData(i) for i in range(mm_p.instr.count())]
        for inst in insts:
            for paper in ("A4", "Letter", "A3", "150x200"):
                r = default_recipe(inst, paper)
                odd = replace(r, margin_top=round(rnd.uniform(0, 40), 3),
                              margin_left=round(rnd.uniform(0, 40), 3),
                              strip_gap_mm=round(rnd.uniform(0, 5), 3),
                              offset_x_mm=round(rnd.uniform(0, 20), 3))
                for rec in (r, odd):
                    mm_p.set_recipe(rec)
                    in_p.set_recipe(rec)
                    a = json.dumps(mm_p.get_recipe().to_dict(), sort_keys=True)
                    b = json.dumps(in_p.get_recipe().to_dict(), sort_keys=True)
                    assert a == b, (inst, paper)
    finally:
        mm_p.deleteLater()
        in_p.deleteLater()


def test_labels_and_help_follow_the_unit(panel):
    from core.i18n import tr
    p = panel
    texts = lambda: {lbl.text() for lbl, _a, _b in p._unit_labels}  # noqa: E731
    assert tr("Margins (mm):") in texts()
    _choose(p, "in")
    assert tr("Margins (in):") in texts() and tr("Margins (mm):") not in texts()
    tip = next(t for t in p._length_tips if t._title == tr("Margins"))
    assert "chosen inches under Units" in tip.dialog_body()
    # a row whose label says the unit keeps its box bare; any other says in
    assert p.margins["t"].suffix() == ""
    assert p.inter_patch.suffix() == " " + tr("in")
    assert p.underline_gap.suffix() == " " + tr("in")
    _choose(p, "px")                     # pixels: the lengths are mm
    assert tr("Margins (mm):") in texts()
    assert "chosen inches" not in tip.dialog_body()
    assert p.inter_patch.suffix() == " mm"


# ---- 5. charts made by 4.3.43 ---------------------------------------------------

@pytest.mark.parametrize("unit", ["mm", "in", "px"])
@pytest.mark.parametrize("stored", [
    ("38.0953x25.3907", {"w": [4096, "px"], "h": [2730, "px"], "ppi": 2731},
     2731),
    ("234.95x196.85", {"w": [9.25, "in"], "h": [7.75, "in"], "ppi": 2032}, 2032),
    ("234.95x196.85", None, 1200),
])
def test_a_4_3_43_chart_opens_and_comes_back_unchanged(qapp, beta_on,
                                                       units_store, unit,
                                                       stored):
    from workflow.layout_engine.presets import default_recipe
    paper, ps, dpi = stored
    r = replace(default_recipe("SS", paper), dpi=dpi, page_size=ps,
                tiff_res_unit="in" if ps else "cm")
    p = _panel(unit=unit)
    try:
        # what the plain panel (no Units choice, 4.3.43's) gives back
        plain = _panel(units_choice=False)
        plain.set_recipe(r)
        want = plain.get_recipe().to_dict()
        plain.deleteLater()
        page = lambda d: (d["paper"], d["dpi"], d.get("page_size"),  # noqa
                          d.get("tiff_res_unit", "cm"))
        assert page(want) == page(r.to_dict())
        p.set_recipe(r)
        assert p.get_recipe().to_dict() == want
        # looking at it in every unit and back changes nothing
        start = p.units.currentData()
        for u in ("mm", "in", "px", start):
            _choose(p, u)
        assert p.get_recipe().to_dict() == want
    finally:
        p.deleteLater()


# ---- 6. a personal preference -----------------------------------------------------

def test_the_choice_is_remembered_and_never_in_a_recipe(qapp, beta_on,
                                                        units_store):
    p = _panel(unit="mm")
    try:
        before = p.get_recipe().to_dict()
        _choose(p, "in")
        assert units_store.get("page_output_units") == "in"
        assert p.get_recipe().to_dict() == before
        assert "units" not in json.dumps(before)
        q = _panel()
        assert q.units.currentData() == "in"
        assert q.margins["t"].length_unit() == "in"
        q.deleteLater()
    finally:
        p.deleteLater()


# ---- 7. leftover a: the FD-9 there and back ---------------------------------------

@pytest.mark.parametrize("units_choice", [True, False])
def test_the_fd9_there_and_back_keeps_a_pixel_page(qapp, beta_on, units_store,
                                                   units_choice):
    from workflow.fd9 import support as fd9
    before = fd9._latched
    fd9.set_enabled_for_this_process(True)
    p = _panel(units_choice=units_choice, unit="px")
    try:
        p.instr.setCurrentIndex(p.instr.findData("SS"))
        p.paper.setCurrentIndex(p.paper.findData("__custom__"))
        p.dpi.setValue(2731)
        _set_px(p, 4093, 2731)
        want = p.get_recipe().page_size
        assert want == {"w": [4093, "px"], "h": [2731, "px"], "ppi": 2731}
        p.instr.setCurrentIndex(p.instr.findData("FD9"))
        qapp.processEvents()
        p.instr.setCurrentIndex(p.instr.findData("SS"))
        qapp.processEvents()
        if p.paper.currentData() != "__custom__":
            p.paper.setCurrentIndex(p.paper.findData("__custom__"))
        p.dpi.setValue(2731)
        assert p.get_recipe().page_size == want
        assert p._page_truth == {"w": (4093.0, "px"), "h": (2731.0, "px")}
    finally:
        p.deleteLater()
        fd9._latched = before


# ---- 8. leftover c: the printer edge note on a page too large for Pillow --------

def test_the_edge_note_skips_a_page_too_large_with_words(qapp, monkeypatch,
                                                         caplog, tmp_path):
    import logging
    from PIL import Image
    from ui.tabs.tab_chart import TabChart
    from workflow import printer_edges as PE
    import workflow.page_geometry as pg

    class _Fake:
        _margin_tiffs = [str(tmp_path / "x.tif")]
        _settings = {}

        def window(self):
            return None

    monkeypatch.setattr(PE, "note_printer", lambda s, p: "Some Printer")
    monkeypatch.setattr(pg, "read_tiff_dimensions_points",
                        lambda p: (1000.0, 1000.0))

    class _E:
        def any(self):
            return True

        def as_dict(self):
            return {}
    monkeypatch.setattr(PE, "edges_for", lambda *a: (_E(), (1000.0, 1000.0)))

    def boom(*a, **k):
        raise Image.DecompressionBombError(
            "Image size (296000000 pixels) exceeds limit of 178956970 pixels")
    monkeypatch.setattr(PE, "losses_for_chart", boom)
    fake = _Fake()
    fake._settings = type("S", (), {"get": lambda self, k, d=None: d})()
    with caplog.at_level(logging.INFO, logger="ui.tabs.tab_chart"):
        assert TabChart._printer_edge_notice(fake) is None
    lines = [r for r in caplog.records if "edge note skipped" in r.getMessage()]
    assert lines and lines[0].levelno == logging.INFO
    assert "296000000 pixels" in lines[0].getMessage()


# ---- the fix round after the independent review (2026-11-17) ---------------------

@pytest.mark.parametrize("frame", [(18796, 15748), (18001, 15001)])
@pytest.mark.parametrize("route", [("mm", "px"), ("in", "px"),
                                   ("mm", "in", "px"), ("in", "mm", "px")])
def test_a_pixel_page_too_large_survives_every_unit(panel, frame, route):
    """Review P1-5 (the R3-a guarantee): a pixel page that is no size the mm
    and inch fields can hold at the resolution set stays its pixels when the
    Units go to mm or inches and back; the red line says why all along."""
    from ui.dialogs import page_output_panel as pop
    p = panel
    w, h = frame
    p.dpi.setValue(72)
    _choose(p, "px")
    _set_px(p, w, h)
    p._emit()
    assert pop.size_problem(p)
    for u in route:
        _choose(p, u)
        assert pop.size_problem(p), u           # the red line stays
        assert p._page_truth == {"w": (float(w), "px"), "h": (float(h), "px")}
    assert (p._page_px["w"].value(), p._page_px["h"].value()) == (w, h)
    p.dpi.setValue(2032)
    p._emit()
    assert pop.size_problem(p) is None
    assert p.get_recipe().page_size == {"w": [w, "px"], "h": [h, "px"],
                                        "ppi": 2032}


def test_a_pixel_page_too_large_looked_at_in_mm_keeps_its_pixels_on_a_new_resolution(
        panel):
    """...and a resolution changed while mm is shown keeps the pixels typed
    until the page fits (review S8d: it used to become 2000 x 2000 mm)."""
    p = panel
    p.dpi.setValue(72)
    _choose(p, "px")
    _set_px(p, 18796, 15748)
    _choose(p, "mm")
    p.dpi.setValue(2032)
    p._emit()
    assert po.page_pixels(p.get_recipe().page_size, 2032) == (18796, 15748)


def test_a_length_typed_in_inches_survives_reload_and_preset(qapp, beta_on,
                                                            units_store):
    """Review P1-1: typed 0.25 in (6.35 mm) for a margin, the strip gap and
    a chart offset; the recipe read back into the panel (project reopened),
    through a preset's JSON, and with either unit shown keeps 6.35."""
    from workflow.layout_engine.presets import LayoutRecipe
    p = _panel(unit="in")
    try:
        p.use_instr_margins.setChecked(False)
        for box in (p.margins["t"], p.strip_gap, p.offx):
            _type(box, "0.25")
            assert box.value() == 6.35
        r = p.get_recipe()
        assert (r.margin_top, r.strip_gap_mm, r.offset_x_mm) == (6.35,) * 3
        p.set_recipe(r)                                  # reopened
        assert p.get_recipe().to_dict() == r.to_dict()
        assert p.margins["t"].text().replace(",", ".") == "0.250"
        stored = LayoutRecipe.from_dict(json.loads(json.dumps(r.to_dict())))
        for unit in ("mm", "in"):
            q = _panel(unit=unit)
            try:
                q.set_recipe(stored)                    # a preset loaded
                got = q.get_recipe()
                assert (got.margin_top, got.strip_gap_mm,
                        got.offset_x_mm) == (6.35,) * 3, unit
                assert got.to_dict() == r.to_dict(), unit
                if unit == "mm":
                    assert q.strip_gap.text().replace(",", ".") == "6.35 mm"
            finally:
                q.deleteLater()
        _choose(p, "mm")
        p.set_recipe(p.get_recipe())
        assert p.get_recipe().strip_gap_mm == 6.35
    finally:
        p.deleteLater()


def test_old_one_decimal_values_load_exactly_as_the_plain_box(qapp, beta_on,
                                                             units_store):
    """A 4.3.43 recipe holds one-decimal millimetres: they load exactly as
    the plain box loads them, whatever unit is shown; and values finer than
    the box that are no inch value (2.25, 12.25, -299.25: review P1-2) are
    rounded as Qt rounds them (half away from zero) in both units."""
    from ui.dialogs.length_units import LengthSpinBox
    from ui.widgets import NoScrollDoubleSpinBox

    def mk(cls):
        b = cls()
        b.setRange(-300, 300)
        b.setDecimals(1)
        b.setSingleStep(0.5)
        b.setSuffix(" mm")
        return b
    inch, mm, plain = mk(LengthSpinBox), mk(LengthSpinBox), mk(NoScrollDoubleSpinBox)
    inch.set_length_unit("in")
    vals = [i / 100 for i in range(-30000, 30001)] + \
        [i / 1000 for i in range(0, 20001)]
    unit_diff, plain_diff = [], []
    for v in vals:
        inch.setValue(v)
        mm.setValue(v)
        plain.setValue(v)
        if inch.value() != mm.value():
            unit_diff.append(v)
        if mm.value() != plain.value():
            inches = v / 25.4
            on_grid = abs(round(inches, 3) - inches) < 1e-9
            if not on_grid or round(v, 1) == v:
                plain_diff.append(v)
    assert unit_diff == []          # 80,002 values, the reviewer's probe
    assert plain_diff == []
    for v, want in ((2.25, 2.3), (12.25, 12.3), (-299.25, -299.3), (6.3, 6.3)):
        inch.setValue(v)
        mm.setValue(v)
        assert inch.value() == mm.value() == want


def test_arrows_up_and_down_in_inches_come_back_exactly(panel):
    """Review P1-3."""
    p = panel
    box = p.inter_patch
    box.setValue(10.0)
    _choose(p, "in")
    box.stepBy(1)
    box.stepBy(-1)
    assert box.value() == 10.0
    box.stepBy(1)
    box.stepBy(1)
    box.stepBy(-2)
    assert box.value() == 10.0
    box.stepBy(1)
    assert box.value() == float(f"{0.404 * 25.4:.4f}")


def test_the_largest_value_shown_in_inches_types_back_to_the_maximum(panel):
    """Review P1-4: 300 mm shows as 11.811 in; typed back it is 300."""
    p = panel
    box = p.inter_patch
    _choose(p, "in")
    top = box.textFromValue(box.maximum())
    _type(box, top)
    assert box.value() == box.maximum()
    _type(box, box.textFromValue(box.minimum()))
    assert box.value() == box.minimum()


def test_switching_back_restores_each_side_on_its_own(panel):
    """Review P1-6: 100 x 50 mm, pixels, the width typed, back to mm: the
    untouched height is exactly 50 mm again."""
    p = panel
    p.dpi.setValue(300)
    _type(p.custom_w, "100")
    _type(p.custom_h, "50")
    _choose(p, "px")
    _type(p._page_px["w"], "2000")
    _choose(p, "mm")
    assert p._page_truth["h"] == (50.0, "mm")
    assert p.custom_h.value() == 50.0
    assert p._page_truth["w"][1] == "mm"
    assert po.pixels_of(p._page_truth["w"][0], 300) == 2000


@pytest.mark.parametrize("pref", ["mm", "in", "px"])
def test_a_chart_opens_showing_the_unit_its_page_is_stored_in(qapp, beta_on,
                                                             units_store, pref):
    """Coordinator's ruling after review P1-7: a page STORED in pixels opens
    with Pixels shown (one in inches with Inches), for that chart only: the
    remembered choice is not rewritten and the next chart follows it."""
    from workflow.layout_engine.presets import default_recipe
    p = _panel(unit=pref)
    try:
        px_frame = {"w": [4096, "px"], "h": [2730, "px"], "ppi": 2731}
        p.set_recipe(replace(default_recipe("SS", "38.0953x25.3907"), dpi=2731,
                             page_size=px_frame, tiff_res_unit="in"))
        assert p.units.currentData() == "px" and p._page_unit == "px"
        assert units_store.get("page_output_units") == pref
        p.dpi.setValue(1200)                 # a film chart keeps its pixels
        p._emit()
        assert p.get_recipe().page_size == {"w": [4096, "px"],
                                            "h": [2730, "px"], "ppi": 1200}
        in_page = {"w": [9.25, "in"], "h": [7.75, "in"], "ppi": 2032}
        p.set_recipe(replace(default_recipe("SS", "234.95x196.85"), dpi=2032,
                             page_size=in_page, tiff_res_unit="in"))
        assert p.units.currentData() == "in"
        assert p.margins["t"].length_unit() == "in"
        assert units_store.get("page_output_units") == pref
        p.set_recipe(default_recipe("SS", "A4"))  # the next chart
        assert p.units.currentData() == pref and p._page_unit == pref
        p.set_recipe(default_recipe("SS", "150x200"))
        assert p.units.currentData() == pref
    finally:
        p.deleteLater()


def test_the_fd9_there_and_back_with_mm_shown_keeps_the_pixel_count(
        qapp, beta_on, units_store):
    """Review P1-8: the sides and the resolution they were made for are
    taken before the FD-9 clamps anything."""
    from workflow.fd9 import support as fd9
    before = fd9._latched
    fd9.set_enabled_for_this_process(True)
    p = _panel(unit="px")
    try:
        p.instr.setCurrentIndex(p.instr.findData("SS"))
        p.paper.setCurrentIndex(p.paper.findData("__custom__"))
        p.dpi.setValue(2731)
        _set_px(p, 4093, 2731)
        _choose(p, "mm")
        p.instr.setCurrentIndex(p.instr.findData("FD9"))
        qapp.processEvents()
        p.instr.setCurrentIndex(p.instr.findData("SS"))
        qapp.processEvents()
        if p.paper.currentData() != "__custom__":
            p.paper.setCurrentIndex(p.paper.findData("__custom__"))
        p.dpi.setValue(2731)
        p._emit()
        assert po.page_pixels(p.get_recipe().page_size
                              or {"w": [p.custom_w.value(), "mm"],
                                  "h": [p.custom_h.value(), "mm"], "ppi": 2731},
                              2731) == (4093, 2731)
    finally:
        p.deleteLater()
        fd9._latched = before
