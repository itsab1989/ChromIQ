"""THE LIMITS OF AN i1iO CHART (the new chart layout, 25 November 2026).

Generate refuses, before anything is written, exactly what START would refuse
for a chart's shape: the chart side's maxima (`table_facts.layout_maxima`) and
the table package's own copy (`table.caps.LAYOUT_MAXIMA`) are the same numbers,
worked out again here from the layout engine. The reader's numbers that the
chart side keeps copies of are the reader's. A side file records numbers, no
sentence of where they come from, and nothing of the rule that was taken out
is left anywhere in the repository.
"""
from __future__ import annotations

import itertools
import json
import subprocess
from pathlib import Path

import pytest

from workflow.i1io import chart as C
from workflow.i1io import table_facts as F

ROOT = Path(__file__).resolve().parent.parent
PAPERS = ("A4", "Letter", "203x254", "148x210", "4x6", "215x297", "230x320",
          "216x310", "210x320")


@pytest.fixture(autouse=True)
def i1io_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        yield
    finally:
        support._latched = before


def _layout(kw, count=None):
    from workflow.layout_engine import geometry, instruments, papers
    w, h = papers.dimensions_mm(kw["paper"])
    g = instruments.geom_from_build_kwargs({"instrument": "IO2", **kw})
    n = count or geometry.patches_per_sheet(g, w, h)
    return g, geometry.compute(g, w, h, max(1, n)), w, h


def _kw(paper, along, across, mode, crosses, labels, spacer=0.5):
    return {"paper": paper, "patch_h": along, "patch_w": across,
            "spacer_mode": mode, "spacer_width": spacer, C.LIMITS_KEY: 2,
            C.CROSSES_KEY: crosses, "draw_indicators": labels,
            "row_indicators": labels, "margins": (0.1, 0.1, 0.1, 0.1)}


GRID = list(itertools.product(
    PAPERS, (5.5, 6.0, 7.0, 8.0, 10.0), (5.5, 7.0, 8.0),
    ("none", "colored"), (True, False), (True, False)))


def _start_takes(layout) -> "str | None":
    """What START's own check says about the shape (None: it takes it)."""
    from workflow.i1io.table import caps
    pages = []
    left = layout.total_patches
    while left > 0:
        n = min(left, layout.patches_per_page)
        rows, r = divmod(n, layout.steps_in_pass)
        pages.append(tuple([layout.steps_in_pass] * rows + ([r] if r else [])))
        left -= n
    try:
        caps.caps_for_sheet({"pages": [
            {"strips": [{"patches": [None] * k} for k in p]} for p in pages]})
    except caps.CapsRefused as exc:
        return exc.detail["what"]
    return None


def test_generate_refuses_exactly_what_start_would_refuse():
    refused = accepted = 0
    for paper, along, across, mode, crosses, labels in GRID:
        g, lay, w, h = _layout(_kw(paper, along, across, mode, crosses, labels))
        try:
            C.check_maxima(lay)
            mine = True
        except C.I1ioSheetRefused:
            mine = False
        assert mine == (_start_takes(lay) is None), (
            paper, along, across, mode, crosses, labels)
        refused += not mine
        accepted += mine
    # the grid holds both: 5.5 mm patches on the largest custom sheets
    assert refused and accepted


def test_a_sheet_of_7_mm_patches_and_more_is_never_refused_for_its_shape():
    for paper, along, across, mode, crosses, labels in GRID:
        if along < 7 or across < 7:
            continue
        C.check_maxima(_layout(_kw(paper, along, across, mode, crosses,
                                   labels))[1])


def test_the_refusal_comes_before_anything_is_written(tmp_path):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    kw = _kw("230x320", 5.5, 5.5, "none", False, False)
    _g, lay, _w, _h = _layout(kw)
    assert lay.patches_per_page > F.layout_maxima()["per_page"]
    with pytest.raises(C.I1ioSheetRefused,
                       match="strips on one sheet.*wider across"):
        chart.build_chart(_ti1(tmp_path / "c.ti1", lay.patches_per_page),
                          tmp_path / "c", instrument="IO2", dpi=100, seed=1,
                          chart_date="x", **kw)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.ti1"]
    # …and the panel says it before Generate is pressed
    _s, notes = C.preview_checks({"instrument": "IO2", "dpi": 100,
                                  "area_target_count": 2000, **kw})
    assert any("at most" in n for n in notes)


class _Layout:
    def __init__(self, steps, per_page, total):
        self.steps_in_pass, self.patches_per_page = steps, per_page
        self.total_patches = total
        self.pages = -(-total // per_page)


@pytest.mark.parametrize("layout,words", [
    (_Layout(50, 50, 50), ("50 patches in one strip", "at most 49", "longer")),
    (_Layout(1, 38, 38), ("38 strips on one sheet", "at most 37", "wider")),
    (_Layout(10, 10, 6680), ("needs 668 sheets", "at most 667", "fewer"))])
def test_each_refusal_names_its_own_number(layout, words):
    with pytest.raises(C.I1ioSheetRefused) as e:
        C.check_maxima(layout)
    assert all(w in str(e.value) for w in words), str(e.value)
    assert _start_takes(layout) is not None
    # one less is taken by both
    smaller = {50: _Layout(49, 49, 49), 38: _Layout(1, 37, 37),
               6680: _Layout(10, 10, 6670)}[layout.total_patches]
    C.check_maxima(smaller)
    assert _start_takes(smaller) is None


def test_a_part_strip_is_a_strip():
    """24 patches a strip: 25 patches are two strips, on the last page too."""
    lay = _Layout(24, 528, 553)
    assert C.page_shapes(lay) == [(24, 22, 528), (24, 2, 25)]
    assert C.page_shapes(_Layout(24, 528, 5)) == [(5, 1, 5)]
    # a page of 37 whole strips and a part of one more is refused
    with pytest.raises(C.I1ioSheetRefused, match="38 strips"):
        C.check_maxima(_Layout(2, 80, 75))
    assert _start_takes(_Layout(2, 80, 75)) == "rows"


def _maxima(sheets, spacer=0.5):
    """The most any layout of *sheets* holds: the smallest patches, with and
    without spacers, crosses and labels, the run held inside the reach."""
    most = {"per_row": 0, "rows": 0, "per_page": 0}
    for (w, h), mode, crosses, labels in itertools.product(
            sheets, ("none", "colored"), (True, False), (True, False)):
        g, lay, _w, _h = _layout(_kw(f"{w:g}x{h:g}", 5.5, 5.5, mode, crosses,
                                     labels, spacer))
        sp = 0.0 if mode == "none" else spacer
        block = F.REACH_MM.value[0] - 2 * F.RUN_MM.value
        n = min(lay.steps_in_pass, int((block + sp) // (5.5 + sp) + 1e-9))
        rows = lay.patches_per_page // lay.steps_in_pass
        for k, v in (("per_row", n), ("rows", rows), ("per_page", n * rows)):
            most[k] = max(most[k], v)
    return most


def test_the_maxima_are_the_layouts_own():
    w, h = F.PIECE_MAX_MM.value
    assert _maxima(((w, h), (210.0, 297.0), (215.9, 279.4))) == \
        F.LAYOUT_MAXIMA_SMALL
    lw, lh = F.PIECE_MAX_LARGE_MM.value
    assert _maxima(((w, h), (lw, lh), (241.5, 329.0))) == F.LAYOUT_MAXIMA_LARGE


def test_the_chart_side_and_the_table_package_hold_the_same_maxima():
    from workflow.i1io.table import caps
    assert caps.LAYOUT_MAXIMA == F.layout_maxima()
    assert caps.LARGE_PIECES == F.LARGE_PIECES is False
    assert caps._MAXIMA_SMALL == {**F.LAYOUT_MAXIMA_SMALL, "pages": F.MAX_PAGES}
    assert caps._MAXIMA_LARGE == {**F.LAYOUT_MAXIMA_LARGE, "pages": F.MAX_PAGES}


def test_the_readers_numbers_are_the_readers():
    from workflow.i1io.table import geometry, scan, spot
    assert F.SCAN_READING_INTERVAL_S.value == scan.READING_S
    assert F.READER_EDGE_MM.value == scan.STRIP_EDGE_MIN_MM
    assert F.READER_START_SPREAD_S.value == scan.MOTION_START_SPREAD_S
    assert F.READER_MIN_READINGS.value == spot.STRIP_MIN_READINGS
    assert F.LANDING_MM.value == scan.ARRIVAL_UNITS * F.TABLE_UNIT_MM.value
    assert F.ALIGN_ANGLE_TOL_DEG.value == geometry.ANGLE_TOL_DEG
    assert set(F.SCAN_SPEEDS_MM_S.value) <= set(geometry.RECORDED_M2_SPEEDS)
    for v in (54, 61, 88, 138):
        assert F.row_edge_mm(v) == scan.strip_edge_mm(v)


@pytest.mark.parametrize("size,share", [(5.5, 9.9), (6.0, 5.2), (7.0, 0.0)])
def test_the_neighbours_share_of_what_the_instrument_sees(size, share):
    assert 100 * F.neighbour_share(size) == pytest.approx(share, abs=0.06)


def test_a_side_file_records_numbers_not_sentences(tmp_path):
    from tests.test_i1io_chart import _ti1
    from workflow.layout_engine import chart
    chart.build_chart(_ti1(tmp_path / "c.ti1", 60), tmp_path / "c",
                      instrument="IO2", paper="A4", dpi=100, seed=1,
                      chart_date="x")
    doc = json.loads((tmp_path / "c.i1io.json").read_text(encoding="utf-8"))
    facts = doc["table_facts"]
    assert facts == json.loads(json.dumps(F.as_record()))
    text = json.dumps(facts)
    assert "source" not in text and "confidence" not in text
    assert "Profiler" not in text


def test_nothing_is_left_of_the_rule_that_was_taken_out():
    """Built from parts, so this file does not find itself. Every tracked
    text file, the catalogues too."""
    phrases = (" ".join(("gaps", "size", "too", "large")),
               "_".join(("GAP", "MAX", "FRACTION")),
               " ".join(("as", "i1Profiler", "allows")))
    files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=120).stdout.split("\0")
    found = []
    for name in files:
        p = ROOT / name
        if not name or not p.is_file() or p.suffix.lower() in (
                ".png", ".jpg", ".tif", ".icc", ".icm", ".pdf", ".gz", ".zip"):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found += [(name, ph) for ph in phrases if ph in text]
    assert not found, found
