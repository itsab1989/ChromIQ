"""#182 E2, beta 38: a page counts for evenness only when its patches cover at
least 60 % of it (Knut, 5789263863; built at 75 % as approved in 5789539407,
lowered to 60 % in 5792912682: *"lower the threshold to 60%. instrument's
minimum margins are general rules that not always works."*; B8-828).

    coverage = (paper width - left - right) x (paper height - top - bottom)
               / (paper width x paper height)

with left, right, top and bottom the distances from each paper edge to the
first patch: the four numbers Create Chart's "Measured from Preview" shows. A
page under the floor is left out as a page under 9 by 9 is; a chart whose
files do not say where its patches sit reads N-A with that reason. The report,
the presets window and the pre-flight all ask the same arithmetic.

Every test names the mutation it was run against.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_report as MR                  # noqa: E402
from workflow import page_coverage as PC                       # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402
from tests.test_evenness_across_the_sheet import (             # noqa: E402
    FROM_MEAN, PAIR, _even, _words, _write_chart, _write_sheet)

_TWO = (PAIR, FROM_MEAN)


@pytest.fixture(autouse=True)
def _fresh_caches():
    PE.clear_cache()
    PC.clear_cache()
    yield
    PE.clear_cache()
    PC.clear_cache()


def _ev(ti2, where, sigma=0.2):
    return MR.build_report(_write_sheet(ti2, where, _even(sigma)))["evenness"]


# ---------------------------------------------------------------------------
# the formula and the floor
# ---------------------------------------------------------------------------
def test_knuts_formula_on_the_margins():
    """An A4 page, margins 26 / 6 / 38 / 19 mm (the i1Pro 572-patch chart):
    (210-26-6) x (297-38-19) / (210 x 297) = 178 x 240 / 62370 = 68.5 %,
    over the 60 % floor. The same block moved right to leave 87 mm there
    (the 312-patch half page): 97 x 240 / 62370 = 37.3 %, under it.

    MUTATION: leave the right and bottom margins out of `coverage_of` and it
    reads 184 x 259 / 62370 = 76.4 %, and the half page 76.4 % too."""
    got = PC.coverage_of(210, 297, 26, 6, 38, 19)
    assert got == pytest.approx(178 * 240 / (210 * 297), abs=1e-9)
    assert got >= MR.EVENNESS_MIN_PAGE_COVERAGE
    half = PC.coverage_of(210, 297, 26, 87, 38, 19)
    assert half == pytest.approx(97 * 240 / (210 * 297), abs=1e-9)
    assert half < MR.EVENNESS_MIN_PAGE_COVERAGE
    assert PC.coverage_of(210, 297, 0, 0, 0, 0) == 1.0
    assert PC.coverage_of(210, 297, 200, 200, 0, 0) == 0.0


def test_the_floor_is_60_percent_and_inclusive(tmp_path):
    """Knut, 5792912682: 60 %. Exactly 60 %: counted. A hair under: left out,
    N-A with the reason. Through a real report, just over (60.3 %) is judged
    and just under (59.7 %) is refused.

    MUTATION: `>` for `>=` against `EVENNESS_MIN_PAGE_COVERAGE` in
    `evenness_from_residuals` and the page at exactly 60 % is refused; the
    constant left at 0.75 and the 60.3 % page is refused."""
    import numpy as np
    assert MR.EVENNESS_MIN_PAGE_COVERAGE == 0.60
    grid = MR.evenness_grid_from_layout([12], 12, 144, coverage=[0.60])
    ev = MR.evenness_from_residuals(grid, np.zeros((144, 3)), shuffles=20)
    assert ev["eligible"], ev
    grid = MR.evenness_grid_from_layout([12], 12, 144, coverage=[0.5999])
    ev = MR.evenness_from_residuals(grid, np.zeros((144, 3)), shuffles=20)
    assert ev["reason"] == MR.REASON_EVENNESS_PAGE_COVERAGE
    # …and through a real report, from the geometry beside the chart
    ti2, where = _write_chart(tmp_path / "a", coverage=0.603)
    ev = _ev(ti2, where)
    assert ev["eligible"], ev
    assert ev["coverage"][0] == pytest.approx(0.603, abs=2e-3)
    assert ev["coverage"][0] >= 0.60
    ti2, where = _write_chart(tmp_path / "b", coverage=0.597)
    ev = _ev(ti2, where)
    assert ev["coverage"][0] < 0.60
    assert not ev["eligible"]
    assert ev["reason"] == MR.REASON_EVENNESS_PAGE_COVERAGE
    assert ev["pages_uncovered"] == [1]


def test_the_floor_is_one_constant(tmp_path, monkeypatch):
    """Move the constant and a page between the two floors changes side, and
    every sentence quoting the floor says the new figure.

    MUTATION: write 0.60 into `evenness_from_residuals` or 60 into the note
    instead of reading `EVENNESS_MIN_PAGE_COVERAGE`; one half goes red."""
    from ui.dialogs.measurement_report_dialog import _evenness_coverage_sentence
    ti2, where = _write_chart(tmp_path / "a", coverage=0.55)
    rep = MR.build_report(_write_sheet(ti2, where, _even(0.2)))
    assert "at least 60 % is needed" in _evenness_coverage_sentence(rep)
    monkeypatch.setattr(MR, "EVENNESS_MIN_PAGE_COVERAGE", 0.5)
    ev = _ev(ti2, where)
    assert ev["eligible"], ev
    ti2, where = _write_chart(tmp_path / "b", coverage=0.45)
    rep = MR.build_report(_write_sheet(ti2, where, _even(0.2)))
    assert "at least 50 % is needed" in _evenness_coverage_sentence(rep)


def test_an_uncovered_page_is_left_out_and_the_others_judged(tmp_path):
    """Knut's E1 rule applied to the new floor: a page under it is left out,
    the rest of the chart is judged, and the note names the page and its
    figure.

    MUTATION: refuse the whole chart when any page is under the floor."""
    from ui.dialogs.measurement_report_dialog import _evenness_where_sentence
    ti2, where = _write_chart(tmp_path / "c", pages=(12, 12), rows=12,
                              coverage=[0.85, 0.5])
    rep = MR.build_report(_write_sheet(ti2, where, _even(0.2)))
    ev = rep["evenness"]
    assert ev["eligible"] and ev["pages_used"] == [1]
    assert ev["pages_uncovered"] == [2] and ev["pages_small"] == []
    assert ev["n_patches"] == 12 * 12
    s = _evenness_where_sentence(rep)
    assert "The patches on page 2 cover 50.0 % of the page, less than 60 %, " \
           "so it is not counted." in s, s


def test_the_grid_floor_is_asked_first(tmp_path):
    """A page under 9 by 9 that also covers too little is named for its
    grid, the reason it was already given before E2.

    MUTATION: ask the coverage before the grid and an 8-strip chart reads
    "cover 50 %" instead of "8 strips and 20 rows"."""
    k = MR.EVENNESS_MIN_GRID
    ti2, where = _write_chart(tmp_path / "a", pages=(k - 1,), rows=20,
                              coverage=0.5)
    ev = _ev(ti2, where)
    assert ev["reason"] == MR.REASON_EVENNESS_GRID_TOO_SMALL


def test_a_chart_with_no_page_geometry_is_na_and_stays_off_the_strip(tmp_path):
    """A laid-out `.ti2` with no engine geometry, no page image and no derived
    rectangles beside it: nobody can say how much of the page it covers.

    MUTATION: read an unknown coverage as 1.0 in `_page_coverages` and the
    chart is judged on a page nobody measured."""
    ti2, where = _write_chart(tmp_path / "a", coverage=None)
    ev = _ev(ti2, where)
    assert ev["reason"] == MR.REASON_EVENNESS_NO_PAGE_GEOMETRY
    assert ev["pages_unmeasured"] == [1]
    assert MR.REASON_EVENNESS_NO_PAGE_GEOMETRY in MR.EVENNESS_FILE_REASONS
    assert MR.REASON_EVENNESS_NO_PAGE_GEOMETRY in PE.OTHER_SHORTFALL_REASONS
    assert MR.REASON_EVENNESS_PAGE_COVERAGE in PE.LAYOUT_SHORTFALL_REASONS
    assert not PE.is_patch_shortfall(MR.REASON_EVENNESS_PAGE_COVERAGE)


# ---------------------------------------------------------------------------
# the note (K22: what the measured chart lacks)
# ---------------------------------------------------------------------------
def test_the_note_names_the_page_and_its_share_rounded_down():
    """Knut's K22 wording: "the patches on page N of the measured chart cover
    X % of the page; at least 60 % is needed". A page at 59.96 % must never
    read "60.0 %" beside a refusal, and the floor itself reads "60", not
    "60.0" or the float's "60.00000000000001".

    MUTATION: round the share instead of flooring it in `_coverage_pct`; or
    format the floor with `:.1f` in `_min_coverage_pct`."""
    from ui.dialogs.measurement_report_dialog import (
        _evenness_coverage_sentence, _min_coverage_pct)
    assert _min_coverage_pct() == "60"
    one = {"evenness": {"pages_uncovered": [1], "coverage": [0.59962]}}
    assert _evenness_coverage_sentence(one) == (
        "the patches on page 1 of the measured chart cover 59.9 % of the "
        "page; at least 60 % is needed")
    two = {"evenness": {"pages_uncovered": [1, 2], "coverage": [0.553, 0.58]}}
    assert _evenness_coverage_sentence(two) == (
        "the patches on pages 1, 2 of the measured chart cover at most 58.0 % "
        "of their page; at least 60 % is needed")


def test_the_report_window_shows_the_note_on_both_rows(qapp, tmp_path):
    """On screen the N-A cells carry the note, and the strip names the
    layout, not the grey ramp.

    MUTATION: drop the `evenness_page_coverage_too_small` entry from
    `_reason_sentence` and the note is empty."""
    from tests.test_beta37_round_fixes import _settings, _visible
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.compliance_sets import N_A
    ti2, where = _write_chart(tmp_path / "c", coverage=0.553)
    t3 = _write_sheet(ti2, where, _even(0.2))
    dlg = MeasurementReportDialog(_settings(tmp_path), None, initial_ti3=t3)
    try:
        rows, _rec = dlg._verdict_rows(dlg._report)
        ev = [x for x in rows if x.get("row_id") in _TWO]
        assert ev and all(x["word"] == N_A for x in ev)
        text = _visible(dlg)
        want = ("the patches on page 1 of the measured chart cover 55.3 % of "
                "the page; at least 60 % is needed")
        assert want in text, text[:2000]
        # the strip is about the chart, and a chart laid out to fill more of
        # the page answers this, so it names both rows with the same note
        strip = dlg._mismatch_text()
        assert strip.count(want) == 2, strip
    finally:
        dlg.deleteLater()


def test_the_layout_strip_names_the_coverage_too():
    """M-REPORT-CHART-MISMATCH-LAYOUT, under a list holding only the two
    evenness rows, says what they want of the layout: more strips and rows,
    and patches covering most of the page (revised for E2, still PROPOSED).

    MUTATION: put back the beta 37 body, which named strips and rows only."""
    from workflow.measurement_messages import M_REPORT_CHART_MISMATCH_LAYOUT
    title, body = M_REPORT_CHART_MISMATCH_LAYOUT.render(set="S", rows="• r")
    assert "cover most of the page" in body
    assert "more strips and more rows on a page" in body


# ---------------------------------------------------------------------------
# where the numbers come from: the panel's own two measurements
# ---------------------------------------------------------------------------
def _build(tmp_path, slug, with_channels=True):
    from dataclasses import asdict
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS
    from workflow.layout_engine.chart import build_from_recipe
    from workflow.layout_engine.presets import LayoutRecipe
    p = next(x for x in KNUT_PRESETS if x.slug == slug)
    chart = Path(resource_path(p.ti1_asset))
    rec = LayoutRecipe.from_dict(dict(p.layout_recipe))
    res, used = build_from_recipe(str(chart), str(tmp_path / "b"), rec)
    ti2 = Path(res.ti2_path)
    if with_channels:
        lay = json.loads(ti2.with_suffix(".strips.json").read_text("utf-8"))
        lay.update({"engine": "chromiq", "recipe": asdict(used)})
        ti2.with_suffix(".channels.json").write_text(
            json.dumps({"layout": lay}), encoding="utf-8")
    return p, chart, ti2


def test_a_built_chart_reads_what_measured_from_preview_shows(tmp_path):
    """Knut's 572-patch i1Pro A4 chart, built for real: its coverage is the
    one the panel's own `measure_from_engine` margins give, the page image
    agrees within a pixel row, and the presets window predicted it before
    the chart existed. 68.4 %: under the first 75 % floor (the i1Pro's 26 mm
    clip border and 38 mm top leave an A4 page no room for it) and over
    Knut's 60 %.

    MUTATION: have `predicted_page_coverage` read the grid box
    (`geometry.compute`) without `engine_ink_bounds_px`, or drop the right
    margin from `coverage_of`; one of the three figures moves apart."""
    from workflow.margin_inspector import measure_from_engine, measure_margins
    p, chart, ti2 = _build(tmp_path, "i1_w8_a4_572p_1page_portrait_w8_0mm")
    r, _ = measure_from_engine(ti2.with_suffix(".channels.json"), 0)
    panel = PC.coverage_of(r.page_w_mm, r.page_h_mm, r.left_mm, r.right_mm,
                           r.top_mm, r.bottom_mm)
    got = PC.chart_page_coverage(ti2, 1)
    assert got["source"] == PC.SOURCE_ENGINE
    assert got["pages"][0]["coverage"] == pytest.approx(panel, abs=1e-9)
    assert panel == pytest.approx(0.684, abs=0.002)
    assert panel >= MR.EVENNESS_MIN_PAGE_COVERAGE
    img = measure_margins(ti2.with_suffix(".tif"))
    assert PC.coverage_of(img.page_w_mm, img.page_h_mm, img.left_mm,
                          img.right_mm, img.top_mm, img.bottom_mm) \
        == pytest.approx(panel, abs=0.005)
    from workflow.layout_engine.presets import LayoutRecipe
    pred = PC.predicted_page_coverage(
        LayoutRecipe.from_dict(dict(p.layout_recipe)), PE.patch_count(chart))
    assert pred["pages"][0]["coverage"] == pytest.approx(panel, abs=0.002)


def test_without_engine_geometry_the_page_image_is_measured(tmp_path):
    """The panel's fallback, and a printtarg chart's only source: the page
    TIFF beside the `.ti2`.

    MUTATION: skip the TIFF in `_measure_pages` and the chart reads N-A for
    want of a geometry it has."""
    _p, _chart, ti2 = _build(tmp_path, "i1_w8_a4_572p_1page_portrait_w8_0mm",
                             with_channels=False)
    got = PC.chart_page_coverage(ti2, 1)
    assert got["source"] == PC.SOURCE_IMAGE
    assert got["pages"][0]["coverage"] == pytest.approx(0.684, abs=0.005)


def test_a_dated_snapshot_borrows_the_live_charts_pages_only_if_identical(
        tmp_path):
    """`verify_chart_snapshot` leaves the page images out of a dated
    verification's chart/ folder; the live chart two folders up still has
    them and is used while its `.ti2` is byte for byte the snapshot's.

    MUTATION: drop the byte comparison in `_live_chart_of_snapshot` and a
    snapshot of a DIFFERENT chart borrows the live chart's pages."""
    vdir = tmp_path / "verifications"
    live, where = _write_chart(vdir, stem="x-verify", coverage=0.8)
    snap = vdir / "2026-10-01_100000" / "chart"
    snap.mkdir(parents=True)
    shutil.copy2(live, snap / live.name)
    got = PC.chart_page_coverage(snap / live.name, 1)
    assert got["pages"][0]["coverage"] == pytest.approx(0.8, abs=2e-3)
    assert got["source"].endswith("+live")
    (snap / live.name).write_text(live.read_text("utf-8") + "\n",
                                  encoding="utf-8")
    PC.clear_cache()
    assert PC.chart_page_coverage(snap / live.name, 1)["pages"] == [None]


# ---------------------------------------------------------------------------
# the presets window and the pre-flight
# ---------------------------------------------------------------------------
def _assess_preset(slug):
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS
    p = next(x for x in KNUT_PRESETS if x.slug == slug)
    chart = Path(resource_path(p.ti1_asset))
    return dict(PE.assess(chart, MR.REPORT_TYPE_FULL, "chromiq_default",
                          recipe=dict(p.layout_recipe)).missing)


def test_the_presets_window_and_the_preflight_ask_the_same_floor():
    """Two engine presets that have not been built. The 312-patch i1Pro A4
    chart fills the left half of the page, 12 strips by 26 rows: the
    prediction says 37.3 %, so the presets window and the pre-flight
    (`assess_any`) both file the two rows under the coverage reason, with a
    line of their own that quotes 60 %, and the star is not touched (a layout
    shortfall). Knut's 572-patch chart, 68.4 %, now answers both rows.

    MUTATION: leave `coverage` out of `_predicted_grid`; the rows read "no
    page geometry" instead (and the 572 chart stops answering)."""
    from ui.dialogs.preset_verification_dialog import reason_line
    a = _assess_preset("i1_w8_a4_312p_1page_portrait_w8_0mm")
    assert a.get(PAIR) == MR.REASON_EVENNESS_PAGE_COVERAGE, a
    assert a.get(FROM_MEAN) == MR.REASON_EVENNESS_PAGE_COVERAGE, a
    b = _assess_preset("i1_w8_a4_572p_1page_portrait_w8_0mm")
    assert PAIR not in b and FROM_MEAN not in b, b
    for code in (MR.REASON_EVENNESS_PAGE_COVERAGE,
                 MR.REASON_EVENNESS_NO_PAGE_GEOMETRY):
        assert code in PE.classified_reasons()
        assert "cannot check this metric" not in reason_line(code), code
    line = reason_line(MR.REASON_EVENNESS_PAGE_COVERAGE)
    assert "cover at least 60 % of the page" in line, line
    assert "75" not in line, line


def test_the_built_in_engine_presets_against_the_60_percent_floor():
    """The count the register quotes (B8-828), over all 172 built-in engine
    presets: at 60 % four are refused by the coverage, all four the half-page
    i1Pro charts (312 and 324 patches, A4 and Letter, 34 to 37 %), and twelve
    by the 9 by 9 grid first. At 75 % it was 123 by the coverage.

    MUTATION: put `EVENNESS_MIN_PAGE_COVERAGE` back to 0.75 and 123 are
    refused by the coverage."""
    from core.resource_path import resource_path
    from ui.tabs.tab_chart import KNUT_PRESETS
    eng = [p for p in KNUT_PRESETS if getattr(p, "layout_recipe", None)]
    assert len(eng) == 172
    by_coverage, by_grid = [], []
    for p in eng:
        g = PE._evenness_grid_for(Path(resource_path(p.ti1_asset)),
                                  dict(p.layout_recipe))
        ev = MR.evenness_from_residuals(g, {})
        if ev.get("reason") == MR.REASON_EVENNESS_PAGE_COVERAGE:
            by_coverage.append(p.slug)
        elif ev.get("reason") == MR.REASON_EVENNESS_GRID_TOO_SMALL:
            by_grid.append(p.slug)
    assert sorted(by_coverage) == sorted([
        "i1_w8_a4_312p_1page_portrait_w8_0mm",
        "i1_w8_letter_312p_1page_portrait_w8_0mm",
        "i1_w75_a4_324p_1page_portrait_w7_5mm",
        "i1_w75_letter_324p_1page_portrait_w7_5mm"])
    assert len(by_grid) == 12


def test_a_laid_out_chart_in_the_preflight_reads_its_own_files(tmp_path):
    """The pre-flight's chart is laid out, so it reads the geometry beside
    it, like the report.

    MUTATION: have `chart_grid` skip `chart_page_coverage` and the laid-out
    chart reads "no page geometry"."""
    small, _ = _write_chart(tmp_path / "s", pages=(22,), rows=26,
                            coverage=0.55)
    big, _ = _write_chart(tmp_path / "l", pages=(22,), rows=26,
                          coverage=0.65)
    a = dict(PE.assess_any(small).missing)
    assert a.get(PAIR) == MR.REASON_EVENNESS_PAGE_COVERAGE, a
    b = PE.assess_any(big)
    assert PAIR in b.answered and FROM_MEAN in b.answered, b.missing


def test_the_help_text_quotes_the_floor():
    """The metric help icon says 60 %, and the constant must agree.

    MUTATION: change `EVENNESS_MIN_PAGE_COVERAGE` without the help text."""
    from workflow import compliance_sets as CS
    pct = f"{MR.EVENNESS_MIN_PAGE_COVERAGE * 100:g} %"
    assert f"cover at least {pct} of the page" in CS.ROW_BY_ID[PAIR].detect
    assert f"covering at least {pct} of the page" in CS.ROW_BY_ID[PAIR].remedy
