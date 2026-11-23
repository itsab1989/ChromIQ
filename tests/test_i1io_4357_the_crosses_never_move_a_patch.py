"""4.3.57 (items 29 and 30): the aiming crosses never move a patch, and a page keeps them where
its corner patches cannot be aligned on.

Item 29, from the table owner's 22 Nov evening test and Basti's own try: switching "Aiming
crosses" off moved patches three ways (the corner swap, 8 patches a page; on a narrow page the
freed 10 mm side band took a row; with an automatic count that made a new colour set). Now the
crosses change only what is aimed at: the same margins (unless a person lowers them by hand),
the same alignment, the seed's own patch order.

Item 30: a page whose aimed corner patches lie close together (a few rows, or short rows) keeps
its crosses: an ordinary aim error on a patch centre (``CORNER_AIM_ERROR_MM``) must pass the
alignment's own 1 degree check (kept: it is the only check that sees mark 3 one strip off), which
needs about 86 mm. That includes the latent fault of a page of TWO strips: its corner patches lie
8 mm apart, and the alignment refuses any two aims under 10 mm, so it could never be aligned.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from tests.test_i1io_aiming_crosses import _ti1, _ti2_rows


@pytest.fixture(autouse=True, scope="module")
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _no_pale(path: Path) -> Path:
    """The test set without its near-white patches (a pale corner keeps a page's crosses)."""
    text = path.read_text(encoding="utf-8")
    for v in range(94, 101):
        text = text.replace(f" {v}.0000", " 40.0000")
    path.write_text(text, encoding="utf-8")
    return path


def _build(folder: Path, n: int, paper="A4", pale=False, **kw):
    from workflow.layout_engine import chart
    folder.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(folder / "c.ti1", n)
    if not pale:
        _no_pale(ti1)
    res = chart.build_chart(ti1, folder / "c", instrument="IO2", paper=paper, dpi=100,
                            seed=1959595238, **kw)
    side = json.loads((folder / "c.i1io.json").read_text(encoding="utf-8"))
    return res, side


def _places(side) -> dict:
    """{patch location: (page, strip index, centre on the page)} from the side file."""
    out = {}
    for p in side["pages"]:
        for si, st in enumerate(p["strips"]):
            for q in st["patches"]:
                out[q["loc"]] = (p["page"], si, tuple(round(v, 3) for v in q["centre_mm"]))
    return out


@pytest.mark.parametrize("paper,n", [("A4", 528), ("60x297", 144), ("Letter", 300)])
def test_switching_the_crosses_off_moves_no_patch(tmp_path, paper, n):
    _r1, on = _build(tmp_path / "on", n, paper)
    _r2, off = _build(tmp_path / "off", n, paper, i1io_crosses=False)
    assert len(on["pages"]) == len(off["pages"])
    assert _places(on) == _places(off)
    # the same colour in every place (no corner swap)
    assert _ti2_rows(tmp_path / "on" / "c.ti2") == _ti2_rows(tmp_path / "off" / "c.ti2")


def test_the_narrow_page_of_the_owners_recipe_gets_no_extra_row(tmp_path):
    """The analysis's reproduction: 144 patches on 60 x 297 mm: 3 + 3 strips with the crosses,
    and (until 4.3.56) 4 + 2 without them."""
    _r, off = _build(tmp_path, 144, "60x297", i1io_crosses=False)
    assert [len(p["strips"]) for p in off["pages"]] == [3, 3]
    # and both pages keep their crosses: 3 strips are 16 mm across, far under 86 mm
    assert [p["aim"] for p in off["pages"]] == ["crosses", "crosses"]


def test_the_corner_side_needed_has_its_reason():
    from workflow.i1io import chart, table_facts as F
    from workflow.i1io.table import geometry as tgeo
    assert F.ALIGN_ANGLE_TOL_DEG.value == tgeo.ANGLE_TOL_DEG
    need = chart.corner_side_needed_mm()
    assert need == pytest.approx(1.5 / math.tan(math.radians(1.0)))
    assert 85 < need < 87
    # mark 3 one strip off on a full row stays visible to the angle check
    assert math.degrees(math.atan(8.0 / 275.0)) > tgeo.ANGLE_TOL_DEG


def test_a_full_a4_page_without_crosses_is_aimed_at_its_corner_patches(tmp_path):
    _r, off = _build(tmp_path, 528, "A4", i1io_crosses=False)
    page = off["pages"][0]
    assert page["aim"] == "corner patches" and len(page["aim_patches"]) == 3


def test_a_page_of_two_strips_keeps_its_crosses(tmp_path):
    """The latent fault: two strips 8 mm apart, under the alignment's 10 mm."""
    _r, off = _build(tmp_path, 528 + 48, "A4", i1io_crosses=False)
    assert [len(p["strips"]) for p in off["pages"]][1] == 2
    assert [p["aim"] for p in off["pages"]] == ["corner patches", "crosses"]


def test_a_pale_corner_keeps_the_crosses_and_moves_no_patch(tmp_path):
    _r1, on = _build(tmp_path / "on", 528, "A4", pale=True)
    _r2, off = _build(tmp_path / "off", 528, "A4", pale=True, i1io_crosses=False)
    assert _ti2_rows(tmp_path / "on" / "c.ti2") == _ti2_rows(tmp_path / "off" / "c.ti2")
    from workflow.i1io import chart
    rows = _ti2_rows(tmp_path / "off" / "c.ti2")
    for p in off["pages"]:
        if p["aim"] == "corner patches":
            for name in p["aim_patches"]:
                assert chart._lab_of_rgb(tuple(v * 2.55 for v in rows[name]))[0] < 85


def test_margins_lowered_by_hand_lay_the_page_out_again_and_say_what_is_close(tmp_path):
    """A person who lowers the margins by hand without the crosses gets more patches (the
    owner's wish of 13 Nov 2026, kept as an option); a page that then has no room for the
    crosses its close corners would need is built with a warning (the owner's narrow page)."""
    from workflow.i1io import chart
    kw = {"instrument": "IO2", "paper": "60x297", chart.CROSSES_KEY: False}
    res, side = _build(tmp_path, 144, "60x297", i1io_crosses=False,
                       margins=chart.least_margins_mm(kw))
    assert [len(p["strips"]) for p in side["pages"]] == [4, 2]
    assert [p["aim"] for p in side["pages"]] == ["corner patches", "crosses"]
    assert any("On page 1, the corner patches you aim at lie only 24 mm" in w
               for w in res.warnings)


def test_a_page_under_10_mm_without_room_for_crosses_is_refused():
    from workflow.i1io import chart
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm("A4")
    geom = instruments.geom_from_build_kwargs({"instrument": "IO2", "paper": "A4"})
    layout = geometry.compute(geom, w, h, 48)               # one page of two strips
    with pytest.raises(chart.I1ioSheetRefused, match="at least 10 mm apart"):
        chart.corner_warnings(geom, layout, w, h, [False])
    assert chart.corner_warnings(geom, layout, w, h, [True]) == []


def test_a_chart_made_before_measures_from_its_own_side_file(tmp_path, monkeypatch):
    """A chart laid out by 4.3.56 (the corner swap on every page) keeps its files; the table
    drive reads the side file only, so it is measured exactly as it was printed. Fix round
    (review N5): the side file is read the way START reads it, through ``drivable_sheet``, from
    a run folder (its ``table_place``)."""
    from workflow.i1io import chart
    from workflow.layout_engine import permutation, raster

    def old_slots(target, layout, geom, w, h, seed, randomize, crosses):
        slots = permutation.location_permutation(layout.total_patches, seed, randomize)
        media = target.media_patch()
        patches = list(target.patches) + [media] * layout.padding
        rgbs = [raster.to_display_rgb(dev, target.color_rep) for dev, _x in patches]
        return chart.corner_order(slots, rgbs, len(target.patches), geom, layout, w, h)
    monkeypatch.setattr(chart, "sheet_slots", old_slots)
    run_dir = tmp_path / "proj" / "runs" / "run1"
    _r, old = _build(run_dir, 528, "A4", pale=True, i1io_crosses=False)
    monkeypatch.undo()
    from ui.i1io_table_window import drivable_sheet
    from workflow.i1io.table import job as J
    sheet = drivable_sheet(run_dir / "c.ti2")
    assert sheet is not None, "START would not drive the chart made before"
    assert sheet == old
    job = J.TableJob(sheet, folder=tmp_path / "s", open_transport=lambda: None,
                     preflight=lambda: None, other_program=lambda: False)
    assert job.sheet["pages"][0]["aim_points"] == old["pages"][0]["aim_points"]
    assert _places(job.sheet) == _places(old)
    # and today's build of the same chart differs (it would not be the printed one)
    _r, new = _build(tmp_path / "new", 528, "A4", pale=True, i1io_crosses=False)
    assert _ti2_rows(run_dir / "c.ti2") != _ti2_rows(tmp_path / "new" / "c.ti2")
