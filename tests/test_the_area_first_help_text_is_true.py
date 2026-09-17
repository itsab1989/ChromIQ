"""The area-first help text is a promise, so it is measured against a sheet.

Knut asked for the two layout methods to be explained properly, and the text
written for him said of "Prioritise chart area": *"Here your margins are the
law. The patch area lands exactly where you defined it."* An adversary round
drove the real Create Chart window and found that false: asking for 5 mm all
round on an i1Pro 3+ sheet gives a LEFT margin of 36.15 mm, because a whole
number of patches does not fill the width and the leftover is pushed to the
non-clip side so the patches butt against the clip strip. Down the page the
leftover is shared evenly instead, which is the constant ~1 mm on top and
bottom.

This file pins the two together: the sentence and the sheet have to agree.
"""
from __future__ import annotations

import json
import re

import pytest


def _sheet_margins(tmp_path, instrument: str, margin_mm: float) -> dict:
    """Build a real area-first sheet and measure its patch area, in mm."""
    from workflow.layout_engine import chart as le, papers
    from workflow.layout_engine.presets import LayoutRecipe
    rec = LayoutRecipe(
        instrument=instrument, paper="A4", layout_mode="area_first",
        area_min_patch_mm=8.0, use_instrument_margins=False,
        margin_left=margin_mm, margin_right=margin_mm,
        margin_top=margin_mm, margin_bottom=margin_mm, dpi=300,
    )
    d = tmp_path / f"{instrument}-{margin_mm}"
    d.mkdir(parents=True, exist_ok=True)
    src = d / "s.ti1"
    rows = ["CTI1", "", 'DESCRIPTOR "help"', 'ORIGINATOR "ChromIQ"',
            'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
            "END_DATA_FORMAT", "NUMBER_OF_SETS 120", "BEGIN_DATA"]
    rows += [f"{i + 1} {(i * 7) % 101} {(i * 11) % 101} {(i * 29) % 101} 40 45 50"
             for i in range(120)]
    rows += ["END_DATA", ""]
    src.write_text("\n".join(rows), encoding="utf-8")
    kw = dict(rec.build_kwargs())
    kw.pop("instrument", None)
    kw.pop("paper", None)
    kw["randomize"] = False
    kw["seed"] = 1
    le.build_chart(src, d / "s", instrument=rec.instrument, paper=rec.paper, **kw)
    st = json.loads((d / "s.strips.json").read_text())
    pats = [p for p in st["patches"] if int(p["page"]) == 0]
    assert pats
    k = 25.4 / 300.0
    pw, ph = papers.dimensions_mm("A4")
    return {
        "left": min(p["x"] for p in pats) * k,
        "right": pw - max(p["x"] + p["w"] for p in pats) * k,
        "top": min(p["y"] for p in pats) * k,
        "bottom": ph - max(p["y"] + p["h"] for p in pats) * k,
    }


def _area_first_paragraph() -> str:
    """The part of the Create-layout tooltip that describes area-first."""
    import inspect
    from ui.dialogs import layout_options_panel as lop
    src = inspect.getsource(lop)
    i = src.index("Prioritise chart area, then fit patches to it")
    j = src.index("PATCH-FIRST FIELDS", i)
    return src[i:j]


def test_the_text_does_not_promise_an_exact_margin():
    para = _area_first_paragraph()
    for promise in ("margins are the law", "lands exactly where you defined"):
        assert promise not in para, (
            f"the area-first help still promises {promise!r}, which a sheet "
            f"does not deliver")
    for needed in ("left over", "shared", "goes to the LEFT"):
        assert needed in para, (
            f"the area-first help does not explain {needed!r}, so a user "
            f"reading a 36 mm margin off a 5 mm request has nothing to go on")


@pytest.mark.slow
def test_the_sheet_behaves_the_way_the_text_now_says(tmp_path):
    """Measured, not asserted from the code: the vertical leftover is shared
    and the horizontal leftover is not."""
    tight = _sheet_margins(tmp_path, "p3", 5.0)
    wide = _sheet_margins(tmp_path, "p3", 40.0)
    # Down the page: a little more than asked, both ends ALIKE, because the
    # leftover height is shared. How much "a little" is depends on the chart
    # (round 9 measured 1.01 mm on a 300-patch sheet, this one gives 2.03), so
    # the test pins the sharing rather than the number.
    assert 5.0 < tight["top"] < 9.0 and 5.0 < tight["bottom"] < 9.0
    assert abs(tight["top"] - tight["bottom"]) < 0.2
    # Across it: the far side takes the whole leftover...
    assert tight["left"] > tight["right"] + 15.0
    assert abs(tight["right"] - 5.0) < 0.5
    # ...and it shrinks back to what was asked as the others widen.
    assert abs(wide["left"] - 40.0) < 1.0
