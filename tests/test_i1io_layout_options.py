"""THE MANUAL LAYOUT OPTIONS AN i1iO CHART TAKES (the option audit, 2026-11-13).

The owner: "the i1io i think should be able to support most of the layout
engines options we have". Every control of Manual's layout panel was gone
through one by one (DESIGN_NOTE §22). A control is greyed for the i1iO only
where it would put ink where the aperture passes, leave the area the table
reaches or a printer prints, break the scan, or has no meaning on a table;
the audit un-greyed four:

* "Patch area alignment" (any of the nine places; nobody's pick = centred
  between the crosses, or at the patch numbers without them);
* "Spacer size" (1 mm up to a fifth of the patch length);
* "Custom spacer colours" and its swatches;
* the sheet text's "Insert" token menu.

For each, on a real i1iO chart: the side file and the ``.ti2`` agree patch
for patch, every run (the blank paper the arm runs in and out on) is paper
white over the strip's full width, and `check_sheet` passes (the build runs
it before writing anything, so a chart that is built has passed it). And the
panel: the control is live, the greyed ones carry their own reason.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_chart import _ti1  # noqa: E402

DPI = 100
S = DPI / 25.4


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _build(tmp_path, n=300, paper="A4", **kw):
    from workflow.layout_engine import chart
    ti1 = _ti1(tmp_path / "c.ti1", n)
    result = chart.build_chart(ti1, tmp_path / "c", instrument="IO2",
                               paper=paper, dpi=DPI, **kw)
    side = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    return result, side


def _ti2_ids(result) -> dict:
    ids = {}
    body = result.ti2_path.read_text(encoding="utf-8").split(
        "BEGIN_DATA\n", 1)[1]
    for line in body.splitlines():
        if line.startswith("END_DATA"):
            break
        tok = line.split()
        ids[tok[1].strip('"')] = int(tok[0])
    return ids


def _agree_and_blank(tmp_path, result, side):
    """The side file, the .ti2 and the .strips.json agree patch for patch,
    and every run is blank paper over the strip's full width."""
    from PIL import Image
    strips = json.loads((tmp_path / "c.strips.json").read_text(
        encoding="utf-8"))
    s = strips["dpi"] / 25.4
    rects = {(r["page"], r["loc"]): r for r in strips["patches"]}
    ids = _ti2_ids(result)
    seen = 0
    for page in side["pages"]:
        img = np.asarray(Image.open(
            result.tiff_paths[page["page"] - 1]).convert("L"))
        for strip in page["strips"]:
            ys = []
            for p in strip["patches"]:
                r = rects[(page["page"] - 1, p["loc"])]
                cx, cy = p["centre_mm"]
                assert abs((r["x"] + r["w"] / 2) / s - cx) < 0.5
                assert abs((r["y"] + r["h"] / 2) / s - cy) < 0.5
                assert ids[p["loc"]] == p["sample_id"]
                ys.append(cy)
                seen += 1
            half_w = side["patch_mm"][0] / 2 if "patch_mm" in side else 4.0
            half_h = (side["patch_mm"][1] / 2 if "patch_mm" in side
                      else 5.0)
            y0, y1 = strip["run_mm"]
            x = strip["x_mm"]
            first, last = min(ys) - half_h, max(ys) + half_h
            left = round((x - half_w) * S) + 1
            right = round((x + half_w) * S) - 1
            for a, b in ((y0, first), (last, y1)):
                band = img[round(a * S) + 1:round(b * S) - 1, left:right]
                assert band.size and band.min() >= 250, (page["page"], x, a, b)
    assert seen == result.layout.total_patches == len(ids)


def _block_box(side, page=0):
    xs, ys = [], []
    for strip in side["pages"][page]["strips"]:
        for p in strip["patches"]:
            xs.append(p["centre_mm"][0])
            ys.append(p["centre_mm"][1])
    return min(xs), min(ys), max(xs), max(ys)


ALIGNMENTS = ("top-left", "top-center", "top-right", "center-left", "center",
              "center-right", "bottom-left", "bottom-center", "bottom-right")


@pytest.mark.parametrize("crosses", [True, False])
@pytest.mark.parametrize("align", ALIGNMENTS)
def test_every_alignment_builds_a_sound_chart(tmp_path, align, crosses):
    """Any of the nine places, with and without the crosses, on a full
    page: the files agree, the runs are blank, `check_sheet` passed, and the
    block went where it was asked. The engine places the page's whole grid
    in what the margins leave, so the move is the leftover: up to one strip
    pitch across and one patch pitch along (A4: 3 mm and 1 mm with the
    crosses, 5 mm and 1 mm without)."""
    from workflow.i1io import chart as C
    from workflow.layout_engine import papers
    full = C.capacity({"paper": "A4"}, crosses)
    result, side = _build(tmp_path, full, i1io_align=align,
                          i1io_crosses=crosses)
    assert result.layout.pages == 1
    _agree_and_blank(tmp_path, result, side)
    t, r, b, lt = C.fixed_build_kwargs({"i1io_crosses": crosses})["margins"]
    w, h = papers.dimensions_mm("A4")
    pw, ph = side["patch_mm"]
    x0, y0, x1, y1 = _block_box(side)
    left, right = x0 - pw / 2 - lt, (w - r) - (x1 + pw / 2)
    top, bottom = y0 - ph / 2 - t, (h - b) - (y1 + ph / 2)
    assert min(left, right, top, bottom) >= -1e-6
    vert, horiz = ("center", "center") if align == "center" \
        else align.split("-")
    want_h = {"left": left, "right": right, "center": left - right}[horiz]
    want_v = {"top": top, "bottom": bottom, "center": top - bottom}[vert]
    assert abs(want_h) < 1e-6 and abs(want_v) < 1e-6, (left, right, top,
                                                       bottom)
    assert left + right > 0.5 and top + bottom > 0.5   # there was a leftover


def test_nobodys_alignment_is_the_i1ios_own(tmp_path):
    """Unchosen: centred with the crosses, at the patch numbers without
    them (what the i1iO did before the audit, byte for byte)."""
    from workflow.i1io import chart as C, table_facts as F
    assert C.align_of({}, True) == F.ALIGN_WITH_CROSSES.value == "center"
    assert C.align_of({}, False) == F.ALIGN_WITHOUT_CROSSES.value \
        == "center-left"
    assert C.align_of({"i1io_align": "nonsense"}, True) == "center"
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = _build(tmp_path / "a", 200, seed=7)[1]
    b = _build(tmp_path / "b", 200, seed=7, i1io_align="center")[1]
    assert a["pages"] == b["pages"]


@pytest.mark.parametrize("asked,length,got", [
    (None, 10.0, 1.0), (0.3, 10.0, 1.0), (1.5, 10.0, 1.5), (5.0, 10.0, 2.0),
    (3.5, 20.0, 3.5), (9.0, 20.0, 4.0)])
def test_the_spacer_size_is_held_inside_the_tables_limits(asked, length, got):
    from workflow.i1io import chart as C, table_facts as F
    assert F.spacer_width_mm(asked, length) == pytest.approx(got)
    kw = C.fixed_build_kwargs({"spacer_width": asked, "patch_h": length})
    assert kw["spacer_width"] == pytest.approx(got)
    assert C.fixed_build_kwargs({"spacer_width": 2.0,
                                 "spacer_mode": "none"})["spacer_width"] \
        is None


@pytest.mark.parametrize("width", [1.0, 2.0])
@pytest.mark.parametrize("mode", ["colored", "bw"])
def test_a_wider_spacer_builds_a_sound_chart(tmp_path, width, mode):
    """The spacer is printed between two patches of a strip, where the
    aperture passes anyway; wider spacers cost patches, never a run."""
    from workflow.layout_engine import geometry, instruments, papers
    result, side = _build(tmp_path, 400, spacer_width=width,
                          spacer_mode=mode)
    _agree_and_blank(tmp_path, result, side)
    g = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "spacer_width": width,
         "spacer_mode": mode})
    assert g.pspa == pytest.approx(width)
    assert result.layout.patches_per_page == geometry.patches_per_sheet(
        g, *papers.dimensions_mm("A4"))
    # the patch pitch along a strip is the patch plus the spacer
    ys = sorted(p["centre_mm"][1]
                for p in side["pages"][0]["strips"][0]["patches"])
    assert ys[1] - ys[0] == pytest.approx(10.0 + width, abs=0.05)


def test_own_spacer_colours_are_printed_between_the_patches(tmp_path):
    """Custom spacer colours (an engine feature the i1iO build always took;
    only the panel greyed it): every spacer is one of the chosen colours,
    and the runs stay blank."""
    from PIL import Image
    pal = ["#ff0000", "#0000ff"]
    result, side = _build(tmp_path, 300, spacer_palette=pal)
    _agree_and_blank(tmp_path, result, side)
    img = np.asarray(Image.open(result.tiff_paths[0]).convert("RGB"))
    strip = side["pages"][0]["strips"][0]
    ys = sorted(p["centre_mm"][1] for p in strip["patches"])
    x = strip["x_mm"]
    for a, b in zip(ys, ys[1:]):
        mid = (a + b) / 2                      # the middle of the spacer
        px = tuple(int(v) for v in img[round(mid * S), round(x * S)])
        assert px in ((255, 0, 0), (0, 0, 255)), (mid, px)


# ---- the panel ---------------------------------------------------------

@pytest.fixture
def panel(qapp, qtbot):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    qtbot.addWidget(p)
    return p


def _to(panel, code):
    panel.instr.setCurrentIndex(panel.instr.findData(code))


def test_the_unfreed_controls_are_live_and_the_rest_say_why(panel):
    from ui.dialogs.layout_options_panel import (i1io_greyed_reason,
                                                 i1io_greyed_why)
    _to(panel, "IO2")
    for c in (panel.patch_align, panel.spacer_width, panel.custom_spacer_cb,
              panel.insert_token_btn):
        assert c.isEnabled(), c
        assert c in panel._i1io_live_controls()
    greyed = list(panel._i1io_greyable_controls())
    why = i1io_greyed_why()
    # every greyed control has a reason of its own, and it is shown
    named = {id(getattr(panel, n)) for n in panel._I1IO_WHY
             if getattr(panel, n, None) is not None}
    for c in greyed:
        assert not c.isEnabled()
        assert c.toolTip() == panel._i1io_reason_for(c)
    for name, key in panel._I1IO_WHY.items():
        c = getattr(panel, name, None)
        if c is None or c not in greyed:
            continue
        assert c.toolTip() == i1io_greyed_reason(key)
        assert c.toolTip().startswith(why[key])
    # nothing greyed without its own reason
    unnamed = [c for c in greyed if id(c) not in named]
    assert not unnamed, [type(c).__name__ for c in unnamed]
    # every reason is free of em dashes
    assert not any("—" in t for t in why.values())


def test_the_greyed_boxes_show_what_an_i1io_chart_uses(panel):
    from workflow.i1io import table_facts as F
    _to(panel, "IO2")
    assert panel.indicator_rotation.currentData() == F.LABEL_TURN_DEG.value
    assert panel.row_indicator_rotation.currentData() == F.LABEL_TURN_DEG.value
    assert panel.text_edge_clip.value() == F.NUMBERS_EDGE_MM.value
    assert panel.nolimit.isChecked()
    assert panel.layout_mode.currentData() == "patch_first"
    assert panel.patch_align.currentData() == "center"
    assert panel.spacer_width.value() == F.SPACER_MM.value
    assert panel.spacer_width.maximum() == pytest.approx(2.0)
    panel.patch_y.setValue(15.0)
    assert panel.spacer_width.maximum() == pytest.approx(3.0)


def test_alignment_follows_the_crosses_until_a_person_picks(panel):
    _to(panel, "IO2")
    assert panel.patch_align.currentData() == "center"
    panel.i1io_crosses_cb.setChecked(False)
    assert panel.patch_align.currentData() == "center-left"
    assert panel.get_recipe().i1io_align == ""
    assert "i1io_align" not in panel.get_recipe().build_kwargs()
    panel.patch_align.setCurrentIndex(panel.patch_align.findData("bottom-right"))
    r = panel.get_recipe()
    assert r.i1io_align == "bottom-right"
    assert r.build_kwargs()["i1io_align"] == "bottom-right"
    panel.i1io_crosses_cb.setChecked(True)          # a pick stays a pick
    assert panel.patch_align.currentData() == "bottom-right"
    # a round trip keeps it, and a recipe for another instrument has none
    from workflow.layout_engine.presets import LayoutRecipe
    back = LayoutRecipe.from_dict(r.to_dict())
    assert back.i1io_align == "bottom-right"
    other = LayoutRecipe.from_dict({**r.to_dict(), "instrument": "i1"})
    assert "i1io_align" not in other.to_dict()
    assert "i1io_align" not in other.build_kwargs()


def test_leaving_the_i1io_gives_every_box_back(panel):
    _to(panel, "i1")
    panel.patch_align.setCurrentIndex(panel.patch_align.findData("top-right"))
    panel.spacer_width.setValue(0.0)
    panel.text_edge_clip.setValue(4.0)
    panel.nolimit.setChecked(False)
    rot = panel.indicator_rotation.currentData()
    before = (panel.patch_align.currentData(), panel.spacer_width.value(),
              panel.spacer_width.minimum(), panel.spacer_width.maximum(),
              panel.text_edge_clip.value(), panel.nolimit.isChecked(), rot)
    _to(panel, "IO2")
    panel.patch_align.setCurrentIndex(panel.patch_align.findData("bottom-left"))
    panel.spacer_width.setValue(1.5)
    _to(panel, "i1")
    after = (panel.patch_align.currentData(), panel.spacer_width.value(),
             panel.spacer_width.minimum(), panel.spacer_width.maximum(),
             panel.text_edge_clip.value(), panel.nolimit.isChecked(),
             panel.indicator_rotation.currentData())
    assert after == before
