"""THE i1iO'S LETTERS AND NUMBERS ARE HELD AS ON EVERY CHART, AND WHAT IS
RISKY IS SAID (review 3, items 2 and 5).

The owner, 2026-11-13: risky is allowed, silent is not. Before:

* "Label offset" Y -15 printed the strip letters on row 1's patches with
  no word; X 10: the panel said the letters were held at 8.7 mm while the
  build used 10, so the last letter landed on cross 2's digit or off the
  paper; Y +30 dropped them off the sheet silently;
* a chart offset Y of 20 dropped the letters off the sheet and put the
  patch numbers on cross 1's digit, with no word.

Now "Label offset" X is held inside the side text distance of both paper
edges, as on every chart (`raster.strip_label_x_plan`), by ONE function the
build and the panel share (`workflow.i1io.chart.held_letters`); letters or
their underline on a patch, on a cross or partly off the sheet, and numbers
on a cross or partly off the sheet, are warned in the build's log and in
"Measured from Preview" alike; letters or numbers wholly off the sheet are
refused, as other off-sheet content is.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_chart import _ti1  # noqa: E402

DPI = 100


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _build(folder, n=528, **kw):
    from workflow.layout_engine import chart
    folder.mkdir(parents=True, exist_ok=True)
    ti1 = _ti1(folder / "c.ti1", n)
    return chart.build_chart(ti1, folder / "c", instrument="IO2",
                             paper="A4", dpi=DPI, seed=11, project="P",
                             chart_date="2026-11-13", **kw)


def _preview(**kw):
    from workflow.i1io import chart as C
    return C.preview_checks({"instrument": "IO2", "paper": "A4", "dpi": DPI,
                             "area_target_count": 528, **kw})


PATCH = "would print on the patches"
CROSS_L = "strip letters would touch an aiming cross"
EDGE_L = "strip letters would reach past the edge"
CROSS_N = "patch number would touch an aiming cross"


@pytest.mark.parametrize("kw,want", [
    ({}, []),
    ({"strip_label_offset_mm": -15.0}, [PATCH]),
    ({"strip_label_offset_mm": 8.0}, [EDGE_L]),
    ({"strip_label_offset_x_mm": 10.0}, [CROSS_L]),
    ({"offset_y": 8.0}, [EDGE_L, CROSS_N]),
])
def test_what_is_risky_is_said_in_the_log_and_the_panel(tmp_path, kw, want):
    result = _build(tmp_path, **kw)
    got = [w for w in result.warnings
           if any(k in w for k in (PATCH, CROSS_L, EDGE_L, CROSS_N))]
    for key in want:
        assert any(key in w for w in got), (key, got)
    assert len(got) == len(want), got
    # the panel says the same words as the log, all of them
    _shift, notes = _preview(**kw)
    assert sorted(notes) == sorted(result.warnings)


@pytest.mark.parametrize("kw", [{"strip_label_offset_mm": 30.0},
                                {"offset_y": 20.0}])
def test_letters_wholly_off_the_sheet_are_refused(tmp_path, kw):
    from workflow.i1io.chart import I1ioSheetRefused
    with pytest.raises(I1ioSheetRefused, match="off the sheet"):
        _build(tmp_path, **kw)


def test_x_is_held_where_the_panel_says(tmp_path):
    """Asked 40 mm: the letters stop inside the side text distance, and the
    panel's notice names the X the build uses."""
    import numpy as np
    from PIL import Image
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments
    shift, _notes = _preview(strip_label_offset_x_mm=40.0)
    assert shift is not None and shift.held
    assert shift.used_mm < 40.0
    result = _build(tmp_path, strip_label_offset_x_mm=40.0)
    geom = instruments.geom_from_build_kwargs(
        {"instrument": "IO2", "paper": "A4", "dpi": DPI})
    side = tef.geom_side_text_edge_mm(geom)
    im = np.asarray(Image.open(result.tiff_paths[0]).convert("L"))
    h, w = im.shape
    s = DPI / 25.4
    # the letters' band below the strips, clear of the bottom crosses' rows
    sidef = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    run_end = max(st["run_mm"][1] for st in sidef["pages"][0]["strips"])
    band = im[int((run_end + 1.0) * s):, :]
    cols = np.where((band < 128).any(axis=0))[0]
    # the crosses' outlines sit at the paper's right too: only what lies
    # between them counts, and nothing may cross the side text distance
    # except a cross (mark centre 11 mm in from the edge)
    letters = [c for c in cols if c / s < 210.0 - 15.0]
    assert max(letters) / s <= 210.0 - side + 0.5


def test_held_letters_is_the_one_answer():
    import inspect
    from workflow.layout_engine import chart
    from ui.tabs import tab_chart
    assert "held_letters(" in inspect.getsource(chart.build_chart)
    src = inspect.getsource(tab_chart.TabChart._engine_text_notes)
    assert "preview_checks(" in src
