"""4.3.24, review of #214 (M4): a wrong sheet or a sheet turned round is not
filed. Synthetic readings only; no device, no new command, nothing printed.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import random

import pytest

from workflow.fd9 import page_check as pc
from workflow.fd9.page_check import SheetMismatch, check_sheet, spearman


def _chart(rows=6, cols=8, pages=2, seed=1, lo=2.0, hi=90.0):
    """Pages of patches with an invented aim Y each, and the design table."""
    rnd = random.Random(seed)
    layout, design, pid = [], {}, 1
    for _ in range(pages):
        grid = []
        for _r in range(rows):
            row = []
            for _c in range(cols):
                design[pid] = {"SAMPLE_ID": str(pid),
                               "XYZ_Y": f"{rnd.uniform(lo, hi):.4f}"}
                row.append({"id": pid})
                pid += 1
            grid.append(row)
        layout.append({"rows": grid})
    return layout, design


def _read(layout, design, page, *, as_page=None, turned=False, noise=1.5,
          seed=7, gain=0.9, rows=None):
    """Readings of the sheet that really went in (*as_page*, maybe turned),
    filed under the ids of *page* (what the FD-9 thinks it measured)."""
    rnd = random.Random(seed)
    src = layout[page if as_page is None else as_page]["rows"]
    out = []
    grid = layout[page]["rows"]
    R, C = len(grid), len(grid[0])
    for r, row in enumerate(grid[:rows] if rows else grid):
        for c, p in enumerate(row):
            q = src[R - 1 - r][C - 1 - c] if turned else src[r][c]
            y = float(design[q["id"]]["XYZ_Y"]) * gain + rnd.gauss(0, noise)
            out.append({"SAMPLE_ID": str(p["id"]), "XYZ_Y": f"{max(y, 0):.4f}"})
    return out


def test_a_normal_read_never_trips_it():
    for seed in range(40):
        layout, design = _chart(seed=seed, pages=3)
        for page in range(3):
            assert check_sheet(layout, page, design,
                               _read(layout, design, page, seed=seed,
                                     noise=4.0, gain=0.7)) is None


def test_a_sheet_turned_round_is_named():
    layout, design = _chart()
    with pytest.raises(SheetMismatch) as caught:
        check_sheet(layout, 1, design, _read(layout, design, 1, turned=True))
    e = caught.value
    assert (e.kind, e.page, e.found, e.pages) == ("turned", 2, 2, 2)
    assert e.window_kind() == "turned:2:2:2"


def test_another_page_is_named_either_way_round():
    layout, design = _chart(pages=3)
    for turned in (False, True):
        with pytest.raises(SheetMismatch) as caught:
            check_sheet(layout, 1, design,
                        _read(layout, design, 1, as_page=2, turned=turned))
        assert caught.value.kind == "wrong_sheet"
        assert (caught.value.page, caught.value.found) == (2, 3)


def test_a_single_page_chart_turned_round_is_named():
    layout, design = _chart(pages=1)
    with pytest.raises(SheetMismatch):
        check_sheet(layout, 0, design, _read(layout, design, 0, turned=True))


@pytest.mark.parametrize("lo,hi", [(1.0, 3.0), (85.0, 92.0)])
def test_a_dark_only_or_light_only_chart_stays_quiet(lo, hi):
    """Too little contrast to decide: say nothing, whatever went in."""
    layout, design = _chart(lo=lo, hi=hi)
    for turned in (False, True):
        assert check_sheet(layout, 1, design,
                           _read(layout, design, 1, turned=turned,
                                 noise=0.2)) == pc.SKIP_FLAT_READINGS


def test_too_few_patches_stays_quiet():
    layout, design = _chart(rows=2, cols=8)            # 16 patches
    assert check_sheet(layout, 0, design,
                       _read(layout, design, 0, turned=True)) == pc.SKIP_FEW


def test_a_chart_that_looks_the_same_turned_round_stays_quiet():
    """Point symmetric aims: turned round predicts the same pattern, so the
    two cannot be told apart and nothing is said."""
    layout, design = _chart(pages=1)
    grid = layout[0]["rows"]
    R, C = len(grid), len(grid[0])
    for r in range(R):
        for c in range(C):
            a, b = grid[r][c]["id"], grid[R - 1 - r][C - 1 - c]["id"]
            design[b]["XYZ_Y"] = design[a]["XYZ_Y"]
    assert check_sheet(layout, 0, design,
                       _read(layout, design, 0, turned=True)) == pc.SKIP_LOOKS_ALIKE


def test_two_identical_pages_stay_quiet():
    layout, design = _chart(pages=2)
    for a, b in zip(*(sum(([p["id"] for p in row] for row in pg["rows"]), [])
                      for pg in layout)):
        design[b]["XYZ_Y"] = design[a]["XYZ_Y"]
    assert check_sheet(layout, 1, design,
                       _read(layout, design, 1, as_page=0)) is None


def test_a_partly_read_sheet_is_judged_on_what_it_has():
    layout, design = _chart(rows=8, cols=8)
    with pytest.raises(SheetMismatch):
        check_sheet(layout, 0, design,
                    _read(layout, design, 0, turned=True, rows=4))
    assert check_sheet(layout, 0, design,
                       _read(layout, design, 0, rows=4)) is None


def test_spearman_handles_ties_and_constants():
    assert spearman([1, 2, 3], [1, 2, 3]) == pytest.approx(1)
    assert spearman([1, 1, 1], [1, 2, 3]) == 0.0
    assert spearman([1, 2, 2, 3], [3, 2, 2, 1]) == pytest.approx(-1)


def test_the_check_runs_before_a_page_is_filed(setup):
    """End to end on the multi-page path: page 2 read turned round is not
    merged; page 1 stays, and the exception names the window."""
    import json
    from types import SimpleNamespace
    from tests.test_fd9_multipage import capture_pages
    from tests.test_fd9_factory_workflow import native_settings
    from tests.test_fd9_chart_creation import ti1
    from workflow.fd9.chart import build_chart
    from workflow.fd9.measurement import first_table, measure_chart
    import workflow.fd9.page_check as pc
    s = setup
    source, _ = ti1(s.tmp, rep="RGB", tokens=("R", "G", "B"), count=12)
    s.chart = build_chart(source, s.tmp / 'multi', paper='137x170', dpi=72,
                          patch_mm=30, patch_height_mm=30,
                          randomize=False).ti2_path
    calls = []
    real = pc.check_sheet

    def judged(pages, page_index, design, measured):
        calls.append(page_index)
        if page_index == 1:
            raise SheetMismatch("turned", 2, 2, 2, 0.1, 0.95)
        return real(pages, page_index, design, measured)
    pc.check_sheet = judged
    try:
        capture, _ = capture_pages(s)
        result = measure_chart(s.chart, native_settings(s), s.tmp / 'm',
                               capture=capture)
    finally:
        pc.check_sheet = real
    assert calls == [0, 1]
    assert not result['complete'] and result['patches'] == 9
    assert len(first_table(result['staged'])[2]) == 9      # page 2 not filed
    assert isinstance(result['acquisition_exception'], SheetMismatch)
    from ui.fd9_measurement import fd9_exception_kind
    assert fd9_exception_kind(result['acquisition_exception']) == "turned:2:2:2"


def test_the_window_for_each_kind(tab, fd9_windows):
    tab._fd9_explain_error("Sheet check: ...", False, "turned:2:2:3")
    tab._fd9_explain_error("Sheet check: ...", False, "wrong_sheet:2:1:3")
    assert [w[0] for w in fd9_windows] == ["M-FD9-SHEET-TURNED",
                                           "M-FD9-WRONG-SHEET"]
    assert fd9_windows[1][1]["found"] == 1


from tests.test_fd9_partial import setup  # noqa: E402,F401
from tests.test_fd9_normal_measurement import tab  # noqa: E402,F401


def test_r1_l3_the_exact_reverse_is_named_turned_and_normal_ramps_pass():
    """A ramp chart (a calibration chart, not randomised) turned round gives
    the expected pattern reversed: the easiest turn to recognise."""
    layout, design = _chart(pages=1)
    ids = [p["id"] for row in layout[0]["rows"] for p in row]
    for i, pid in enumerate(ids):                       # a lightness ramp
        design[pid]["XYZ_Y"] = f"{2 + 88 * i / (len(ids) - 1):.4f}"
    with pytest.raises(SheetMismatch) as caught:
        check_sheet(layout, 0, design,
                    _read(layout, design, 0, turned=True, noise=0.5))
    assert caught.value.kind == "turned"
    for seed in range(40):
        assert check_sheet(layout, 0, design,
                           _read(layout, design, 0, seed=seed, noise=4.0,
                                 gain=0.7)) is None


def test_r1_l2_a_chart_without_usable_aims_says_the_check_was_skipped():
    layout, design = _chart()
    printed = _read(layout, design, 0)                 # a real, varied sheet
    for row in design.values():
        row["XYZ_Y"] = "50.0"                           # no usable aims
    assert check_sheet(layout, 0, design, printed) == pc.SKIP_NO_AIMS
    from ui.fd9_measurement import _progress_line
    for code in (pc.SKIP_FEW, pc.SKIP_FLAT_READINGS, pc.SKIP_NO_AIMS,
                 pc.SKIP_LOOKS_ALIKE):
        _stage, line = _progress_line(pc.SKIPPED_LINE + code)
        assert line.startswith("ChromIQ") and "right sheet" in line


def test_r1_l2_the_worker_logs_the_skip_once_per_sheet(setup):
    from tests.test_fd9_multipage import capture_pages, make_chart
    from tests.test_fd9_factory_workflow import native_settings
    from workflow.fd9.measurement import measure_chart
    s = setup
    s.chart = make_chart(s.tmp).ti2_path         # two pages, few patches
    capture, _ = capture_pages(s)
    lines = []
    measure_chart(s.chart, native_settings(s), s.tmp / "m", capture=capture,
                  progress=lines.append)
    skipped = [ln for ln in lines if ln.startswith(pc.SKIPPED_LINE)]
    assert len(skipped) == 2


def test_r1_l8_a_refused_sheet_on_a_later_page_resume_offers_nothing_to_save(
        setup):
    """Resume at page 2, page 2 refused: nothing new was measured, so the run
    ends as a failure (no ending question to file the unchanged .ti3)."""
    from dataclasses import replace
    from tests.test_fd9_multipage import capture_pages, make_chart
    from tests.test_fd9_factory_workflow import native_settings
    from workflow.fd9.measurement import measure_chart, publish_measurement
    s = setup
    s.chart = make_chart(s.tmp).ti2_path
    settings = native_settings(s)
    capture, _ = capture_pages(s, stop_page=2)
    partial = measure_chart(s.chart, settings, s.tmp / "a", capture=capture)
    publish_measurement(partial["staged"], partial["destination"], s.chart,
                        allow_partial=True)
    real = pc.check_sheet

    def refuse(pages, page_index, design, measured):
        raise SheetMismatch("turned", page_index + 1, page_index + 1,
                            len(pages), 0.1, 0.95)
    pc.check_sheet = refuse
    try:
        capture, _ = capture_pages(s)
        with pytest.raises(SheetMismatch):
            measure_chart(s.chart, replace(settings, resume=True),
                          s.tmp / "b", capture=capture)
    finally:
        pc.check_sheet = real
