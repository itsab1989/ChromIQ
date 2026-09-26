"""#182 K49 (Knut, 5841092535): his three answers to the K47 questions.

1. *"Should (b2) be built? Answer: Yes."* The paper row and the two solid
   rows compare a measurement with the profile's own description of the
   printing condition: the paper (the chart's patch printed with no ink)
   with the profile's media white on every verification that has a paper
   patch and a profile that can be read (the K37 lookup: the profile the
   print record names, else the run's own); the solids with the colours the
   profile predicts for them where they were printed raw (a FROM PROFILE
   GAMUT chart always, else a raw print). A sheet printed THROUGH the profile
   keeps the solid rows N-A, saying why; no profile, N-A, saying so. The
   cube-corner table keeps the ideal values.
2. *"Yes, it can have value for trending, but be a bit more informative than
   "No limit applies" as note."* (the graphs: tests/test_k47_* and
   tests/test_trend_graphs_for_judged_metrics.py).
3. *"OK."* (the Control strip's three lines, the caption outside §M).

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta44-proof/k49/mutations.txt).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from tests.test_k37_paper_white_from_the_profile import (      # noqa: E402,F401
    _PRINT_WHITE, _RUN_WHITE, _fpg_sheet, _icc, _project, fake_profile)
from workflow import measurement_report as MR                  # noqa: E402
from workflow.ti3_analysis import ciede2000                    # noqa: E402


def _record(ti3: Path) -> Path:
    return next(ti3.parent.glob("*.print.json"))


def _set_colour(ti3: Path, colour: str) -> None:
    rec = _record(ti3)
    d = json.loads(rec.read_text(encoding="utf-8"))
    d["colour"] = colour
    if colour == "raw":
        d["intent"] = ""
        d.pop("profile_path", None)
    rec.write_text(json.dumps(d), encoding="utf-8")


# --------------------------------------------------------------------------
# the paper
# --------------------------------------------------------------------------
def test_the_paper_of_an_ordinary_chart_is_compared_with_the_runs_profile(
        tmp_path):
    """An ordinary chart printed through the profile, with a paper patch,
    on a paper 3 b* yellower than the profile's: the row reads that
    difference, from the run's own profile, with the note saying which paper
    it was compared with. Before K49 it read N-A (needs_reference_file).

    MUTATION, proven red: compare the paper with the ideal white (100, 0, 0)
    in `condition_reference_block` (the row reads about 3.2)."""
    paper = (_RUN_WHITE[0], _RUN_WHITE[1], _RUN_WHITE[2] + 3.0)
    rep = MR.build_report(_project(tmp_path, with_paper=True, paper=paper))
    cond = rep["condition_reference"]["paper"]
    assert cond["from"] == MR.CONDITION_FROM_PROFILE, cond
    assert cond["source"] == MR.PAPER_REF_FROM_RUN and cond["profile"] == "P.icc"
    cell = MR.row_values(rep)["substrate_de00_max"]
    want = ciede2000(paper, _RUN_WHITE)
    assert cell["value"] == pytest.approx(want, abs=0.05), (cell, want)
    assert MR.NOTE_PAPER_AGAINST_PROFILE in cell["notes"]


def test_the_profile_the_sheet_was_printed_through_comes_first(tmp_path):
    """The K37 lookup: a print record naming a profile on disk outranks the
    run's own. The paper is the other profile's paper, so it reads ~0.

    MUTATION, proven red: ask `_run_profile_white` first in
    `profile_paper_white` (the row reads the 2.3 between the two whites)."""
    other = _icc(tmp_path / "Other.icc", _PRINT_WHITE)
    rep = MR.build_report(_project(tmp_path / "p", with_paper=True,
                                   print_profile=other, paper=_PRINT_WHITE))
    cond = rep["condition_reference"]["paper"]
    assert cond["source"] == MR.PAPER_REF_FROM_PRINT, cond
    assert cond["profile"] == "Other.icc"
    assert MR.row_values(rep)["substrate_de00_max"]["value"] < 0.1


def test_no_paper_patch_or_no_profile_is_a_named_n_a(tmp_path):
    """No patch printed with no ink: "paper_not_measured". A paper patch and
    no profile anywhere: "no_profile_to_compare". Never a guess.

    MUTATION, proven red: map CONDITION_NO_PAPER_PATCH to
    REASON_NO_PROFILE_TO_COMPARE in `row_values`."""
    no_patch = MR.build_report(_project(tmp_path / "a", with_paper=False))
    cell = MR.row_values(no_patch)["substrate_de00_max"]
    assert cell["value"] is None
    assert cell["reason"] == MR.REASON_NO_PAPER_PATCH
    no_icc = MR.build_report(_project(tmp_path / "b", with_paper=True,
                                      run_profile=False))
    cell = MR.row_values(no_icc)["substrate_de00_max"]
    assert cell["value"] is None
    assert cell["reason"] == MR.REASON_NO_PROFILE_TO_COMPARE


def test_the_paper_is_read_as_measured_not_media_relative(tmp_path):
    """A white-mapped sheet is judged media-relative on its paper patch, so
    the patch itself reads L* 100 in the cube-corner table; the paper row
    must take the patch AS MEASURED, or it could never read anything but the
    distance from L* 100.

    MUTATION, proven red: take the paper row's Lab from the W corner of
    ``report["corners"]`` on an ordinary chart (it reads ~4.5 on a sheet
    printed on the profile's own paper)."""
    rep = MR.build_report(_project(tmp_path, with_paper=True))
    assert rep["yardstick"] == "media-relative"
    assert MR.row_values(rep)["substrate_de00_max"]["value"] < 0.1


# --------------------------------------------------------------------------
# the solids
# --------------------------------------------------------------------------
def test_solids_printed_through_the_profile_stay_n_a_and_say_why(tmp_path):
    """Printed through the profile, the chart's "cyan" is the chart's cyan
    mapped into the gamut, not the printer's solid: N-A with the reason.

    MUTATION, proven red: return None for "through-profile" in
    `solids_printed_raw` (the rows ask for a prediction and read
    no_profile_to_compare)."""
    rep = MR.build_report(_project(tmp_path, with_paper=True))
    vals = MR.row_values(rep)
    for rid in MR.ROWS_ON_RAW_SOLIDS:
        assert vals[rid]["value"] is None
        assert vals[rid]["reason"] == MR.REASON_SOLIDS_THROUGH_PROFILE, rid


def test_solids_of_an_unrecorded_print_cannot_be_told(tmp_path):
    """No print record: nobody knows whether the solids went out raw.

    MUTATION, proven red: treat a missing record as raw in
    `solids_printed_raw`."""
    ti3 = _project(tmp_path, with_paper=True)
    _record(ti3).unlink()
    vals = MR.row_values(MR.build_report(ti3))
    for rid in MR.ROWS_ON_RAW_SOLIDS:
        assert vals[rid]["reason"] == MR.REASON_SOLIDS_PRINTING_UNRECORDED


def test_solids_of_a_raw_print_are_compared_with_the_prediction(
        tmp_path, monkeypatch):
    """A raw print of an ordinary chart: each solid corner patch against the
    run's profile's ABSOLUTE prediction for its own device value. The fake
    profile predicts the black 2 L* lighter than it reads.

    MUTATION, proven red: ask `forward_lab` with the relative intent (the
    fake refuses it); or compare with the chart's design aim."""
    asked = []

    def fake(rows, profile, bin_dir, *, intent="r", runner=None):
        asked.append((len(rows), Path(profile).name, intent))
        assert intent == "a"
        return [(20.0, 0.5, -0.5) for _ in rows]
    monkeypatch.setattr("workflow.xicclu_runner.forward_lab", fake)
    ti3 = _project(tmp_path, with_paper=True)
    _set_colour(ti3, "raw")
    rep = MR.build_report(ti3, argyll_bin="/fake/argyll")
    solids = rep["condition_reference"]["solids"]
    assert solids["from"] == MR.CONDITION_FROM_PROFILE, solids
    assert asked == [(1, "P.icc", "a")]           # the K corner, the run's
    k = next(c for c in rep["corners"] if c["name"] == "K")
    cell = MR.row_values(rep)["solids_de00_max"]
    assert cell["value"] == pytest.approx(
        ciede2000(tuple(k["lab"]), (20.0, 0.5, -0.5)), abs=0.02)
    assert MR.NOTE_SOLIDS_PREDICTED in cell["notes"]
    # this chart has no cyan, magenta or yellow corner
    assert MR.row_values(rep)["cmy_solids_dhab_max"]["reason"] \
        == MR.REASON_NO_CORNERS


def test_a_from_profile_gamut_chart_needs_its_prediction(
        tmp_path, fake_profile):
    """A FROM PROFILE GAMUT chart is always raw; with no profile to ask the
    solid rows read N-A "no profile", where K37 (i) kept the ideal values.
    With one, they read the shift the fake prediction makes.

    MUTATION, proven red: fall back to the ideal corners (``corners``'s own
    ΔE00) when `fpg_predictions` is None."""
    with_icc = MR.build_report(_fpg_sheet(tmp_path / "a"),
                               argyll_bin="/fake/argyll")
    assert MR.row_values(with_icc)["solids_de00_max"]["value"] > 0.5
    without = MR.build_report(_fpg_sheet(tmp_path / "b", run_profile=False),
                              argyll_bin="/fake/argyll")
    vals = MR.row_values(without)
    for rid in MR.ROWS_ON_RAW_SOLIDS:
        assert vals[rid]["value"] is None
        assert vals[rid]["reason"] == MR.REASON_NO_PROFILE_TO_COMPARE, rid


# --------------------------------------------------------------------------
# a saved report
# --------------------------------------------------------------------------
def test_a_report_saved_before_k49_keeps_its_old_rows(tmp_path):
    """§6: a report with no ``condition_reference`` was worked out against
    the chart's colorimetric reference alone, so read as saved its paper row
    on an ordinary chart is N-A as it was; the block is rebuilt when read
    (ALWAYS_BUILT_BLOCKS), is a rule block (never lent to a kept verdict),
    travels with a verdict of several dates, and a rebuild that judges
    against the profile says the report was worked out differently.

    MUTATION, proven red: leave "condition_reference" out of RULE_BLOCKS
    (the saved record borrows the rebuilt block and its paper row reads a
    number it never had)."""
    from ui.dialogs.measurement_report_dialog import (
        ALWAYS_BUILT_BLOCKS, RULE_BLOCKS, WORKED_OUT_EARLIER_KEY,
        _the_saved_record, _worked_out_differently)
    assert "condition_reference" in ALWAYS_BUILT_BLOCKS
    assert "condition_reference" in RULE_BLOCKS
    assert "condition_reference" in MR.JUDGED_EXPLANATION_KEYS
    rebuilt = MR.build_report(_project(tmp_path, with_paper=True))
    saved = dict(rebuilt)
    saved.pop("condition_reference")
    MR.stamp_verdict(saved, MR.limits_from_pair(2.0, 3.0))
    assert MR.row_values(saved)["substrate_de00_max"]["reason"] \
        == MR.REASON_NEEDS_REFERENCE_FILE
    assert _worked_out_differently(saved, rebuilt)
    rec = _the_saved_record(saved, rebuilt)
    assert "condition_reference" not in rec
    assert rec.get(WORKED_OUT_EARLIER_KEY) is True
    assert MR.row_values(rec)["substrate_de00_max"]["value"] is None


# --------------------------------------------------------------------------
# the words
# --------------------------------------------------------------------------
def test_every_new_reason_and_note_has_its_sentence_in_both_languages(qapp):
    """Four N-A reasons, each saying what the measured chart or its print
    lacks (K22), and the two §M notes, APPROVED by Knut in 5845588201 (K50).
    German by hand, and no "du" in report text.

    MUTATION, proven red: drop "solids_through_profile" from
    `_reason_sentence` (the N-A cell has no numbered note)."""
    import json as _json
    from core.resource_path import resource_path
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_messages as M
    dlg = MeasurementReportDialog(_settings())
    try:
        cat = _json.load(open(resource_path("data/i18n/de.json"),
                              encoding="utf-8"))
        for code in (MR.REASON_NO_PROFILE_TO_COMPARE, MR.REASON_NO_PAPER_PATCH,
                     MR.REASON_SOLIDS_THROUGH_PROFILE,
                     MR.REASON_SOLIDS_PRINTING_UNRECORDED):
            said = dlg._reason_sentence(code, {})
            assert said and "measured chart" in said, code
            de = cat[said]
            assert de != said and " du " not in f" {de.lower()} ", code
        assert dlg._note_sentence(MR.NOTE_SOLIDS_PREDICTED) \
            == M.M_REPORT_SOLIDS_PREDICTED.render()[1]
        assert dlg._note_sentence(MR.NOTE_PAPER_AGAINST_PROFILE) \
            == M.M_REPORT_PAPER_AGAINST_PROFILE.render()[1]
        for m in (M.M_REPORT_SOLIDS_PREDICTED,
                  M.M_REPORT_PAPER_AGAINST_PROFILE):
            assert m.approved
            assert m.id not in M.PROPOSED
    finally:
        dlg.deleteLater()


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------------------
# the presets window
# --------------------------------------------------------------------------
def test_the_presets_window_answers_the_paper_row_from_the_paper_patch(
        tmp_path):
    """Before printing: a chart with a patch printed with no ink answers the
    paper row (its run will have a profile); one without it does not, and
    says so; the two solid rows stay with the FROM PROFILE GAMUT remedy.

    MUTATION, proven red: model every chart's paper as answered in
    `_condition_it_would_get`."""
    from workflow import preset_eligibility as PE
    from tests.test_the_preset_window_says_what_a_chart_can_answer import \
        _write_ti1
    greys = [(v, v, v) for v in range(0, 101, 10)]
    with_paper = _write_ti1(tmp_path / "with.ti1", greys + [(50.0, 0.0, 0.0)])
    without = _write_ti1(tmp_path / "without.ti1",
                         [(v, v, v) for v in range(0, 91, 10)]
                         + [(50.0, 0.0, 0.0)])
    PE.clear_cache()
    a = PE.chart_row_values(with_paper)
    b = PE.chart_row_values(without)
    assert a["substrate_de00_max"]["value"] == 0.0
    assert b["substrate_de00_max"]["reason"] == MR.REASON_NO_PAPER_PATCH
    for rid in MR.ROWS_ON_RAW_SOLIDS:
        assert a[rid]["reason"] == MR.REASON_NEEDS_REFERENCE_FILE
    assert PE.gamut_only_rows() == MR.ROWS_ON_RAW_SOLIDS
    PE.clear_cache()


# --------------------------------------------------------------------------
# a graph with values and no limit (answer 2)
# --------------------------------------------------------------------------
def test_a_grey_and_tone_check_plots_no_colour_row_without_a_limit(
        qapp, monkeypatch):
    """A row with values and no limit is plotted for trending (K49, answer
    2), but only a row the document is ABOUT: a Grey and tone check is not
    about the solids, so it shows no Solid colours graph however many values
    they have; a Full colour check does. A judged row is never one of them.

    MUTATION, proven red: drop the report-type filter in
    `_unlimited_trend_rows`."""
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(_settings())
    try:
        dlg._trend_series = [{"rows": {"solids_de00_max": 1.0 + i,
                                       "ramps_30_70_dl_max": 0.5}}
                             for i in range(2)]
        monkeypatch.setattr(type(dlg), "_report_type_now",
                            lambda self: MR.REPORT_TYPE_GREY)
        assert dlg._unlimited_trend_rows({}) == {"ramps_30_70_dl_max"}
        monkeypatch.setattr(type(dlg), "_report_type_now",
                            lambda self: MR.REPORT_TYPE_FULL)
        assert dlg._unlimited_trend_rows({}) == {"ramps_30_70_dl_max",
                                                 "solids_de00_max"}
        assert dlg._unlimited_trend_rows({"solids_de00_max": 3.0}) == {
            "ramps_30_70_dl_max"}
    finally:
        dlg.deleteLater()
