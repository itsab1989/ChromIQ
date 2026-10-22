"""Forum post 149786, Knut's second lead: is it the LABELS?

jctay's charts number their strips and letter their patches ("36A"). Knut
asked whether everything that maps readings to patches by label copes with
every strip/patch pattern the help offers, letters-then-numbers or the other
way round, padded or not, and with the paper squares that pad a last strip.

The engine's half is proved by `test_pattern_variants_read_by_both_readers`
(22 pairs, every reading lands on its own location) and, for jctay's own
chart, by `test_149786_part_of_a_strip_slipped`. This file holds the PYTHON
side to the same 22 pairs plus jctay's chart: the chart's labels place every
location exactly once; a perfect measurement pairs every expected colour with
its own measured colour in the Measurement Report (ΔE00 0 everywhere, so the
Worst patches table can only show the truth); and a slip injected into the
LAST strip, jctay's chain exactly (the first patch reads the paper, the next
seven each the patch before, then in step), is reported on that strip and
those patches, by the report and by the live check, whatever the pattern.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))

from test_pattern_variants_read_by_both_readers import (  # noqa: E402
    VARIANTS, _build, _ids)
from workflow.layout_engine.labels import labels_for_chart  # noqa: E402

#: jctay's own chart (his 4.3.8 log): numbered strips, lettered patches,
#: 4x6 in, 13 a strip, 9 strips a sheet; 576 colours, so the last strip ends
#: in 9 paper squares.
JCTAY = ("0-9,@-9,@-9;1-999", "A-Z, A-Z", 576, None, "jctay's chart, padded")
#: Knut's list (A1, A01, AA0, AA01, 1A, 01A, 0AA, 01AA): the 22 pairs hold
#: all but two of those shapes; these are the two, numbered strips with
#: two-letter patches, from 0 and zero-padded.
EXTRA = [
    ("0-9,@-9", "A-Z, A-Z", 400, None, "0AA: strips from 0, patches past Z"),
    ("0-9,0-9;01-99", "A-Z, A-Z", 400, None, "01AA: strips 01, patches past Z"),
]
ALL = VARIANTS + EXTRA + [JCTAY]


def _build_any(tmp: Path, variant) -> Path:
    strip, patch, n, max_strip, why = variant
    if variant is JCTAY:
        import random
        from workflow.i1profiler_import import RgbPatch, write_ti1
        from workflow.layout_engine.chart import build_chart
        rnd = random.Random(576)
        tmp.mkdir(parents=True, exist_ok=True)
        write_ti1([RgbPatch(rnd.uniform(0, 100), rnd.uniform(0, 100),
                            rnd.uniform(0, 100)) for _ in range(n)],
                  tmp / "p.ti1")
        build_chart(tmp / "p.ti1", tmp / "chart", instrument="i1",
                    paper="4x6", dpi=72, layout_mode="patch_first",
                    margins=(5.5, 4.0, 1.0, 5.0), clip_border_width=20.0,
                    patch_w=8.0, patch_h=8.2, strip_pattern=strip,
                    patch_pattern=patch, randomize=True, seed=149786)
        return tmp / "chart"
    return _build(tmp, strip, patch, n, max_strip)


def _table(path: Path):
    fmt: list = []
    rows: list = []
    st = 0
    lines = path.read_text(encoding="latin-1").splitlines()
    for ln in lines:
        s = ln.strip()
        if s == "BEGIN_DATA_FORMAT":
            st = 1
            continue
        if s == "END_DATA_FORMAT":
            st = 0
            continue
        if st == 1:
            fmt += s.split()
            continue
        if s == "BEGIN_DATA":
            st = 2
            continue
        if s == "END_DATA":
            break
        if st == 2 and s:
            rows.append(dict(zip(fmt, s.split())))
    return fmt, rows


def _write_ti3(ti2: Path, readings: "dict[str, tuple]") -> Path:
    """A measurement of the chart: SAMPLE_ID, SAMPLE_LOC, RGB and the given
    XYZ per location, as chartread writes one."""
    fmt, rows = _table(ti2)
    body = []
    for r in rows:
        loc = r["SAMPLE_LOC"].strip('"')
        x, y, z = readings[loc]
        body.append(f'{r["SAMPLE_ID"]} "{loc}" {r["RGB_R"]} {r["RGB_G"]} '
                    f'{r["RGB_B"]} {x:.5f} {y:.5f} {z:.5f}')
    ti3 = ti2.with_suffix(".ti3")
    ti3.write_text(
        'CTI3\n\nDESCRIPTOR "Argyll Calibration Target chart information 3"\n'
        'ORIGINATOR "test"\nDEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(body)}\nBEGIN_DATA\n"
        + "\n".join(body) + "\nEND_DATA\n", encoding="utf-8")
    return ti3


def _chart(tmp: Path, variant):
    base = _build_any(tmp, variant)
    ti2 = base.with_suffix(".ti2")
    _fmt, rows = _table(ti2)
    cl = labels_for_chart(ti2)
    expected = {r["SAMPLE_LOC"].strip('"'):
                (float(r["XYZ_X"]), float(r["XYZ_Y"]), float(r["XYZ_Z"]))
                for r in rows}
    grid: dict = {}
    for loc in expected:
        sp = cl.split(loc)
        assert sp is not None and cl.location(*sp) == loc, (variant, loc)
        assert sp not in grid, (variant, loc, grid.get(sp))
        grid[sp] = loc
    return ti2, cl, expected, grid


@pytest.mark.parametrize("variant", ALL, ids=_ids)
def test_a_perfect_measurement_pairs_every_patch_with_its_own_reading(
        variant, tmp_path):
    from workflow.measurement_report import build_report
    ti2, _cl, expected, _grid = _chart(tmp_path, variant)
    r = build_report(_write_ti3(ti2, expected))
    worst = r.get("worst_patches") or []
    assert worst, variant
    assert max(w["de"] for w in worst) < 0.01, (variant, worst[:3])
    assert all(w["expected_hex"] == w["measured_hex"] for w in worst)
    assert "shifted_strips" not in r, (variant, r.get("shifted_strips"))
    # the nine sheet areas place every patch by the same labels
    from workflow.measurement_report import chart_grid
    g = chart_grid(ti2)
    assert "slot" in g, (variant, g)
    assert len(g["slot"]) == len(expected), (variant, len(g["slot"]))


def _slipped_last_strip(expected, grid):
    """jctay's chain on the LAST strip: paper first, the next 7 one late,
    the 8th patch's own reading lost, then in step (on a strip of 9 or 10
    patches, two patches shorter, so the strip still ends in step)."""
    last = max(s for s, _p in grid)
    pats = sorted(p for s, p in grid if s == last)
    locs = [grid[(last, p)] for p in pats]
    paper = max(expected.values(), key=lambda v: v[1])
    read = dict(expected)
    true = [expected[l] for l in locs]
    k = min(8, len(locs) - 2)
    shifted = [paper] + true[:k - 1] + true[k:]
    for loc, xyz in zip(locs, shifted):
        read[loc] = xyz
    return last, locs, read, k


@pytest.mark.parametrize("variant", ALL, ids=_ids)
def test_jctays_chain_on_the_last_strip_is_named_whatever_the_pattern(
        variant, tmp_path):
    from workflow.measurement_report import build_report
    from workflow.slipped_strip import slipped_run_in_strip_read
    ti2, cl, expected, grid = _chart(tmp_path, variant)
    last, locs, read, k = _slipped_last_strip(expected, grid)
    r = build_report(_write_ti3(ti2, read))
    found = r.get("shifted_strips") or []
    assert [f["strip"] for f in found] == [cl.strip(last)], (variant, found)
    assert found[0]["offset"] == 1
    assert found[0]["first"] == locs[0]
    assert found[0]["last"] in (locs[k - 2], locs[k - 1]), (found[0], locs)
    # the Worst patches table is the slipped patches, each with its own name
    worst = {w["loc"] for w in r["worst_patches"] if w["de"] > 1.0}
    assert worst and worst <= set(locs[:k]), (variant, worst)
    # ...and the live check, on the engine's event for that strip
    ev = [{"loc": l, "xyz": list(read[l]), "exyz": list(expected[l])}
          for l in locs]
    run = slipped_run_in_strip_read(ev)
    assert run is not None and run.offset == 1 and run.first == 0, variant


@pytest.mark.parametrize("variant", ALL, ids=_ids)
def test_the_measure_tab_names_every_patchs_strip_by_the_chart(variant,
                                                               tmp_path):
    """The re-read and 'confirmed' bookkeeping group patches by strip with
    `TabMeasure._strip_of`, which asks the chart's labels: every location
    must land in the strip the labels give it, numbered strips included."""
    from ui.tabs.tab_measure import TabMeasure
    ti2, cl, _expected, grid = _chart(tmp_path, variant)

    class _Tab:
        _chart_labels = staticmethod(lambda: cl)
    for (s, _p), loc in grid.items():
        assert TabMeasure._strip_of(_Tab(), loc) == cl.strip(s), (variant, loc)


@pytest.mark.parametrize("variant", EXTRA, ids=_ids)
def test_the_engine_reads_the_two_extra_shapes_onto_the_right_patches(
        variant, tmp_path):
    """The engine's half for the two shapes the 22 pairs lack, by the same
    check those pairs go through."""
    import test_pattern_variants_read_by_both_readers as V
    if not V.HELPER.exists():
        pytest.skip("chromiq-chartread not built")
    V.test_chromiq_engine_reads_the_whole_chart_onto_the_right_patches(
        variant, tmp_path)
