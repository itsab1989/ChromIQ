"""The Measurement Report's evenness check on an X-Rite i1iO chart (Beta).

An i1iO chart is a portrait sheet whose strips run down the page with patch 1
at the strip's BOTTOM (`Geom.reverse_steps`), so that laid on the table a
quarter turn clockwise every strip reads from the left. The evenness check
(#182, Knut 2026-09-22) cuts every page into three by three areas of whole
strips and whole rows, BY THE CHART'S OWN LABELS, and names an area by the
labels printed on the sheet, never "top left".

Checked here on a real i1iO chart: each of the nine areas is one physical
ninth of the page (the reversed numbering mirrors which band is called
first, and the two evenness numbers do not depend on that order), the page
passes the 9-by-9 and spread floors, and a ninth of the sheet printed
differently is found, with the strips and rows printed on it. So the check
applies to an i1iO chart unchanged; nothing in it assumed the usual
geometry.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _ti1(path: Path, n: int) -> Path:
    rows = [f"{i + 1} {(i * 7) % 101:.4f} {(i * 11) % 101:.4f} "
            f"{(i * 13) % 101:.4f} 50.0 50.0 50.0" for i in range(n)]
    path.write_text(
        "CTI1\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        'COLOR_REP "RGB"\n\n'
        "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


@pytest.fixture
def chart(tmp_path):
    from workflow.layout_engine import chart as engine
    ti1 = _ti1(tmp_path / "e.ti1", 504)
    engine.build_chart(ti1, tmp_path / "e", instrument="IO2", paper="A4",
                       dpi=100)
    return tmp_path / "e.ti2"


def _physical(ti2: Path) -> "dict[str, tuple[float, float]]":
    """Each sample id's patch centre on the page, in pixels, from the
    strip map the engine wrote (`<stem>.strips.json`, by location)."""
    from workflow.ti3_analysis import parse_ti3
    sm = json.loads(ti2.with_suffix(".strips.json").read_text("utf-8"))
    at = {p["loc"]: (p["x"] + p["w"] / 2.0, p["y"] + p["h"] / 2.0)
          for p in sm["patches"]}
    d = parse_ti3(ti2)
    return {sid: at[str(loc).strip('"')]
            for sid, loc in zip(d.sample_ids, d.sample_locs)}


def _thirds(values) -> "dict[float, int]":
    """Which third of the distinct *values* (sorted) each one falls in, with
    the evenness check's own band rule (remainder to the middle)."""
    from workflow.measurement_report import _bands_of
    distinct = sorted(set(round(v, 3) for v in values))
    bands = _bands_of(np.arange(len(distinct)),
                      np.full(len(distinct), len(distinct)))
    return dict(zip(distinct, (int(b) for b in bands)))


def test_the_chart_is_an_i1io_chart_with_patch_one_at_the_bottom(chart):
    pos = _physical(chart)
    from workflow.ti3_analysis import parse_ti3
    d = parse_ti3(chart)
    loc = dict(zip(d.sample_ids, (str(x).strip('"') for x in d.sample_locs)))
    by_loc = {loc[s]: p for s, p in pos.items()}
    # A1 below A2 on the page (larger y is lower)
    assert by_loc["A1"][1] > by_loc["A2"][1]


def test_every_area_is_one_physical_ninth_of_the_page(chart):
    from workflow.measurement_report import _bands_of, chart_grid
    grid = chart_grid(chart)
    assert "reason" not in grid, grid
    pos = _physical(chart)
    xs, ys = _thirds(p[0] for p in pos.values()), \
        _thirds(p[1] for p in pos.values())
    seen: "dict[int, set]" = {}
    for sid, (page, strip, row) in grid["slot"].items():
        a = (int(_bands_of(np.array([strip]),
                           np.array([grid["pages"][page]]))[0]) * 3
             + int(_bands_of(np.array([row]), np.array([grid["rows"]]))[0]))
        x, y = pos[sid]
        seen.setdefault(a, set()).add((xs[round(x, 3)], ys[round(y, 3)]))
    assert sorted(seen) == list(range(9))
    for a, cells in seen.items():
        assert len(cells) == 1, f"area {a} spans {cells}"
    assert len({next(iter(c)) for c in seen.values()}) == 9


def test_the_page_is_judged_and_a_different_ninth_is_found(chart):
    """A sheet whose physical top-left ninth printed 3 L* lighter: the check
    is eligible, finds it, and names it by the strips and rows printed in
    that ninth."""
    from workflow.measurement_report import chart_grid, evenness_from_residuals
    grid = chart_grid(chart)
    pos = _physical(chart)
    xs, ys = _thirds(p[0] for p in pos.values()), \
        _thirds(p[1] for p in pos.values())
    rng = np.random.default_rng(7)
    resid, hit = {}, set()
    for sid, (x, y) in pos.items():
        r = rng.normal(0.0, 0.3, 3)
        if xs[round(x, 3)] == 0 and ys[round(y, 3)] == 0:
            r[0] += 3.0
            hit.add(sid)
        resid[sid] = tuple(float(v) for v in r)
    block = evenness_from_residuals(grid, resid)
    assert block["eligible"], block.get("reason")
    assert block["pairwise"] > 2.0
    worst = block["areas"][block["worst_area"]]
    # the strips and rows the report names are the ones printed in that ninth
    from workflow.ti3_analysis import parse_ti3
    d = parse_ti3(chart)
    loc = dict(zip(d.sample_ids, (str(x).strip('"') for x in d.sample_locs)))
    strips = sorted({loc[s].rstrip("0123456789") for s in hit})
    rows = sorted({int(loc[s][len(loc[s].rstrip("0123456789")):])
                   for s in hit})
    assert [list(p) for p in worst["strips"]] == [[strips[0], strips[-1]]]
    assert sorted(int(v) for v in worst["rows"]) == [rows[0], rows[-1]]
