"""#182 K37 (Knut, 5822758830, answer 1): *"Recommendation: (e), with a
numbered note on the sheet, and (b) only when no profile can be read."*

A sheet printed through its profile with an intent that maps white to the
paper, judged against the chart's design or device reference, whose chart has
NO patch printed with no ink (B8-1014 judged it in absolute Lab):

* (e) the paper white is the profile's media white (the profile the print
      record names, else the run's own built profile: the same reader A11
      uses), the sheet is judged media-relative with it, and its "Paper
      white" line (still N-A) carries M-REPORT-PAPER-WHITE-FROM-PROFILE in
      place of M-REPORT-NO-PAPER-PATCH, whose words would be false there;
* (b) no profile can be read: absolute Lab as before, M-REPORT-NO-PAPER-PATCH
      on the line, and M-REPORT-JUDGED-ABSOLUTE-NO-PAPER-WHITE on every row
      the paper white moves.

Every test names the mutation that turns it red; each was run red.
"""
from __future__ import annotations

import os
import struct
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

from tests.test_k34_knuts_section_a import _dispose, _sheet    # noqa: E402

#: The paper the run's profile was made for.
_RUN_WHITE = (95.5, 0.2, 1.4)
#: Another profile's paper, named by a print record.
_PRINT_WHITE = (94.0, 0.5, 3.0)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _icc(path: Path, lab) -> Path:
    """A minimal profile whose media white (``wtpt``) is *lab*."""
    from workflow.ti3_analysis import _lab_to_xyz_array
    x, y, z = (float(v) / 100.0 for v in _lab_to_xyz_array(np.array([lab]))[0])
    tag = b"XYZ " + b"\0" * 4 + struct.pack(
        ">3i", *(round(v * 65536) for v in (x, y, z)))
    header = bytearray(128)
    header[36:40] = b"acsp"
    table = struct.pack(">I", 1) + b"wtpt" + struct.pack(">II", 144, len(tag))
    data = bytes(header) + table + tag
    path.write_bytes(struct.pack(">I", len(data)) + data[4:])
    return path


def _xyz(lab):
    from workflow.ti3_analysis import _lab_to_xyz_array
    return tuple(float(v) for v in _lab_to_xyz_array(np.array([lab]))[0])


#: A small chart: its colours as MEDIA-RELATIVE Lab (what the print was asked
#: for, on an ideal white paper), each printed on the paper `_RUN_WHITE`.
_DESIGN = [
    ((0.0, 0.0, 0.0), (18.0, 0.5, -0.5)),
    ((100.0, 0.0, 0.0), (54.0, 76.0, 60.0)),
    ((0.0, 100.0, 0.0), (86.0, -80.0, 78.0)),
    ((0.0, 0.0, 100.0), (32.0, 72.0, -104.0)),
    ((50.0, 50.0, 50.0), (53.0, 0.0, 0.0)),
    ((25.0, 25.0, 25.0), (30.0, 0.0, 0.0)),
    ((75.0, 75.0, 75.0), (77.0, 0.0, 0.0)),
    ((100.0, 100.0, 60.0), (97.0, -8.0, 40.0)),
    ((80.0, 20.0, 60.0), (48.0, 55.0, -5.0)),
    ((20.0, 80.0, 60.0), (70.0, -50.0, 5.0)),
]
_PAPER_DEV = (100.0, 100.0, 100.0)


def _rows(with_paper: bool, paper=_RUN_WHITE):
    """``[(device, XYZ)]``: the design read media-relative, then printed on
    *paper* (X = X_rel * paper / D50), the paper patch first when asked."""
    d50 = np.array(_xyz((100.0, 0.0, 0.0)))
    scale = np.array(_xyz(paper)) / d50
    rows = []
    if with_paper:
        rows.append((_PAPER_DEV, tuple(np.array(_xyz(paper)))))
    for dev, lab in _DESIGN:
        # a small print error, so the statistics are not all zero
        err = (0.8, 0.4, -0.3)
        rel = np.array(_xyz(tuple(a + b for a, b in zip(lab, err))))
        rows.append((dev, tuple(rel * scale)))
    return rows


def _chart_rows():
    """The .ti2: every patch's DESIGN, the paper patch at the ideal white."""
    return [(_PAPER_DEV, _xyz((100.0, 0.0, 0.0)))] + [
        (dev, _xyz(lab)) for dev, lab in _DESIGN]


def _project(tmp_path, *, with_paper: bool, run_profile: bool = True,
             print_profile: "Path | None" = None, paper=_RUN_WHITE):
    """A project whose run1 holds one verification date printed through the
    profile, relative colorimetric. Returns the date's .ti3."""
    from core.file_manager import Project
    from workflow.verification_print import write_print_record
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    if run_profile:
        _icc(run.profile_icc, _RUN_WHITE)
    date = run.verifications_dir / "2026-09-25_100000"
    date.mkdir(parents=True)
    stem = f"{run.stem}-verify"
    chart = _chart_rows()
    if not with_paper:
        chart = chart[1:]
    ti2 = _sheet(date / f"{stem}.ti2", chart, kind="CTI2")
    ti3 = _sheet(date / f"{stem}.ti3", _rows(with_paper, paper))
    write_print_record(ti2, colour="through-profile", intent="relative",
                       profile=print_profile, route="chromiq")
    return ti3


# --------------------------------------------------------------------------
# (e): the profile's paper white
# --------------------------------------------------------------------------
def test_e_judges_a_sheet_with_no_paper_patch_against_the_runs_profile(
        tmp_path):
    """The sheet printed on the paper its profile was made for reads the
    same with its paper patch (media-relative on the sheet) and without it
    (media-relative on the profile's white), where beta 42 read it in
    absolute Lab.

    MUTATION, proven red: make `profile_paper_white` return None (the sheet
    reads absolute, avg_all about 3 ΔE00 higher)."""
    from workflow.measurement_report import build_report
    with_p = build_report(_project(tmp_path / "a", with_paper=True))
    without = build_report(_project(tmp_path / "b", with_paper=False))
    assert with_p["yardstick"] == "media-relative"
    assert with_p["paper_white_used"] == {"from": "sheet"}
    assert without["yardstick"] == "media-relative", without["yardstick"]
    used = without["paper_white_used"]
    assert used["from"] == "profile" and used["source"] == "run_profile", used
    assert used["profile"] == "P.icc"
    assert all(abs(a - b) < 0.05 for a, b in zip(used["lab"], _RUN_WHITE))
    # the same colours read the same: the largest difference is one of them,
    # and the sum over them is the same (the sheet WITH its paper patch also
    # counts that patch, at ~0, among its 11)
    a, b = with_p["de00"], without["de00"]
    assert abs(a["max_all"] - b["max_all"]) < 0.05, (a, b)
    assert abs(a["avg_all"] * 11 - b["avg_all"] * 10) < 0.1, (a, b)
    # the sheet's own paper is still not measured: no paper white recorded
    assert without["paper_patch"] is False and "paper_white" not in without
    assert without.get("yardstick_no_paper") is True


def test_e_prefers_the_profile_the_print_record_names(tmp_path):
    """A print record that names a profile still on disk is asked first:
    that is the profile the sheet went through.

    MUTATION, proven red: skip the print record in `profile_paper_white`
    (the run's profile, L* 95.5, is used instead of L* 94)."""
    from workflow.measurement_report import build_report
    other = _icc(tmp_path / "Other.icc", _PRINT_WHITE)
    rep = build_report(_project(tmp_path / "p", with_paper=False,
                                print_profile=other, paper=_PRINT_WHITE))
    used = rep["paper_white_used"]
    assert used["source"] == "printed_through", used
    assert used["profile"] == "Other.icc"
    assert abs(used["lab"][0] - _PRINT_WHITE[0]) < 0.05, used


def test_a_sheet_printed_absolute_is_never_given_a_profile_white(tmp_path):
    """The rule reaches only a sheet whose intent maps white to the paper;
    an absolute print is judged as measured, as before.

    MUTATION, proven red: ask `profile_paper_white` before testing
    `white_mapping`."""
    import json
    from workflow.measurement_report import build_report
    ti3 = _project(tmp_path, with_paper=False)
    rec = next(ti3.parent.glob("*.print.json"))
    d = json.loads(rec.read_text(encoding="utf-8"))
    d["intent"] = "absolute"
    rec.write_text(json.dumps(d), encoding="utf-8")
    rep = build_report(ti3)
    assert rep["yardstick"] == "absolute"
    assert rep["paper_white_used"] == {"from": "not_used"}


# --------------------------------------------------------------------------
# (b): no profile can be read
# --------------------------------------------------------------------------
def test_b_stays_absolute_and_notes_every_row_the_paper_white_moves(tmp_path):
    """No profile in the run and none in the print record: absolute Lab, and
    the rows it moves carry the (b) note; a repeatability row does not.

    MUTATION, proven red: drop the note loop at the end of `row_values`."""
    from workflow.measurement_report import (
        NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE, ROWS_MOVED_BY_THE_PAPER_WHITE,
        build_report, row_values)
    rep = build_report(_project(tmp_path, with_paper=False,
                                run_profile=False))
    assert rep["yardstick"] == "absolute"
    assert rep["paper_white_used"] == {"from": "unavailable"}
    vals = row_values(rep)
    noted = [rid for rid, c in vals.items()
             if NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE in c["notes"]]
    assert "all_de00_avg" in noted and "all_de00_max" in noted, noted
    assert set(noted) <= set(ROWS_MOVED_BY_THE_PAPER_WHITE), noted
    for rid in ("repeat_patches_de00_max", "repeat_measurement_de00_max"):
        assert NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE not in vals[rid]["notes"]


def test_the_b_note_is_not_on_an_e_sheet_or_a_sheet_with_its_paper(tmp_path):
    """The control: with a profile, or with a paper patch, no row carries it.

    MUTATION, proven red: attach the note whenever `yardstick_no_paper`."""
    from workflow.measurement_report import (
        NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE, build_report, row_values)
    for name, kw in (("e", {"with_paper": False}),
                     ("paper", {"with_paper": True, "run_profile": False})):
        rep = build_report(_project(tmp_path / name, **kw))
        assert not any(NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE in c["notes"]
                       for c in row_values(rep).values()), name


# --------------------------------------------------------------------------
# The window: which note the "Paper white" line carries
# --------------------------------------------------------------------------
def _window(ti3, qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow.measurement_report import build_report
    dlg = MeasurementReportDialog(_settings(), None, initial_ti3=ti3)
    return dlg, build_report(ti3)


def test_an_e_sheet_carries_the_profile_note_not_the_absolute_one(
        tmp_path, qapp):
    """M-REPORT-NO-PAPER-PATCH says "judged as measured, in absolute Lab",
    which is false of an (e) sheet: its "Paper white" line (still N-A)
    carries M-REPORT-PAPER-WHITE-FROM-PROFILE, filled in with the profile and
    its white, and the approved note is not on the page.

    MUTATION, proven red: return NOTE_NO_PAPER_PATCH from
    `_paper_white_note_code` for every sheet with no paper patch."""
    import html as _html
    import re
    from workflow import measurement_messages as M
    dlg, rep = _window(_project(tmp_path, with_paper=False), qapp)
    try:
        detail = _html.unescape(dlg._run_detail_html(rep))
        assert re.search(r"White - N-A<sup>&nbsp;\d\)</sup>", detail.replace(
            "\xa0", "&nbsp;")), detail[:2000]
        said = M.M_REPORT_PAPER_WHITE_FROM_PROFILE.render(
            profile="P.icc", L="95.5", a="0.2", b="1.4")[1]
        assert said in detail
        assert M.M_REPORT_NO_PAPER_PATCH.render()[1] not in detail
        nums = dlg._numbered_notes([rep])
        assert any(w == "Paper white" and s == said for _n, w, s in nums), nums
        printing = _html.unescape(dlg._printing_block_html(rep))
        assert "relative to the paper white recorded in the profile P.icc" \
            in printing, printing[:1500]
    finally:
        _dispose(dlg)


def test_a_b_sheet_keeps_the_approved_note_and_adds_the_b_note(
        tmp_path, qapp):
    """(b): M-REPORT-NO-PAPER-PATCH is true there and stays on the line; the
    (b) note is listed once, naming the rows it comments.

    MUTATION, proven red: give NOTE_JUDGED_ABSOLUTE_NO_PAPER_WHITE no
    sentence in `_note_sentence` (the list drops it)."""
    from workflow import measurement_messages as M
    dlg, rep = _window(_project(tmp_path, with_paper=False,
                                run_profile=False), qapp)
    try:
        nums = dlg._numbered_notes([rep])
        said = {s: w for _n, w, s in nums}
        assert said.get(M.M_REPORT_NO_PAPER_PATCH.render()[1]) == \
            "Paper white", nums
        b = M.M_REPORT_JUDGED_ABSOLUTE_NO_PAPER_WHITE.render()[1]
        assert b in said, nums
        assert "Average ΔE00, all patches" in said[b], said[b]
    finally:
        _dispose(dlg)


def test_the_paper_white_graph_draws_no_point_for_an_e_sheet(tmp_path):
    """The paper was not measured: no paper white is recorded, so the Paper
    white (L*) trend has no point for the sheet, as for every sheet with no
    paper patch.

    MUTATION, proven red: record the profile's white as `paper_white`."""
    from workflow.measurement_report import build_report, report_trend
    rep = build_report(_project(tmp_path, with_paper=False))
    pts = report_trend([rep])
    assert pts and "white_L" not in pts[0], pts


def test_a_report_saved_before_k37_is_worked_out_again():
    """A saved report without `paper_white_used` judged such a sheet in
    absolute Lab; it is rebuilt from its measurement when the window reads it.

    MUTATION, proven red: take "paper_white_used" out of
    ALWAYS_BUILT_BLOCKS."""
    from ui.dialogs.measurement_report_dialog import (
        ALWAYS_BUILT_BLOCKS, _report_needs_rebuilding)
    from workflow.measurement_report import REPORT_SCHEMA
    rep = {"schema": REPORT_SCHEMA, "de00": {"avg_all": 1.0}}
    for k in ALWAYS_BUILT_BLOCKS:
        rep[k] = {}
    assert not _report_needs_rebuilding(rep)
    del rep["paper_white_used"]
    assert _report_needs_rebuilding(rep)


# ==========================================================================
# K37 (i) (Knut, 5823088098 "Yes do so", on our 5823015844): on a FROM
# PROFILE GAMUT chart the control strip's seven ink and black corner rungs
# are compared with the profile's PREDICTION; the cube-corner table keeps
# the ideal values.
# ==========================================================================
_SHIFT = (-3.0, 0.0, 0.0)      # the fake profile predicts every corner 3 L* darker


def _fpg_sheet(tmp_path, *, run_profile=True):
    """A FROM PROFILE GAMUT verification whose every patch reads exactly its
    reference aim (the corners on their ideal values), with a control strip
    declared over all nine patches."""
    import json
    from tests.test_k34_knuts_section_a import (_PROFILE_WHITE,
                                                _gamut_verification)
    from workflow.ti3_analysis import parse_ti3
    ti3 = _gamut_verification(
        tmp_path, profile_white=_PROFILE_WHITE,
        run_icc_white=_PROFILE_WHITE if run_profile else None)
    vdir = ti3.parent.parent
    ti2 = next(vdir.glob("*-verify.ti2"))
    ids = list(parse_ti3(ti2).sample_ids)
    (vdir / (ti2.stem + ".control-strip.json")).write_text(json.dumps(
        {"name": "test strip", "sample_ids": ids}), encoding="utf-8")
    return ti3


@pytest.fixture
def fake_profile(monkeypatch):
    """xicclu's forward lookup, faked: each device corner's IDEAL value moved
    by `_SHIFT`, so the prediction is a known distance from the ideal."""
    from workflow.gamut_target import CORNER_DEVICES, _corner_ideal_labs
    ideal = dict(zip(CORNER_DEVICES, _corner_ideal_labs()))
    asked = []

    def fake(rows, profile, bin_dir, *, intent="r", runner=None):
        asked.append((len(rows), str(profile), intent))
        return [tuple(v + s for v, s in zip(
            ideal[tuple(float(x) for x in r)], _SHIFT)) for r in rows]
    monkeypatch.setattr("workflow.xicclu_runner.forward_lab", fake)
    return asked


def test_i_the_strip_compares_the_corners_with_the_profiles_prediction(
        tmp_path, fake_profile):
    """The corners read their ideal values exactly, so against the ideal the
    strip reads 0; against the prediction each of the seven reads the shift.
    The run's own profile is asked, with the chart's intent.

    MUTATION, proven red: hand `control_strip_block` `ref` instead of
    `strip_ref` (the strip reads 0.00)."""
    from workflow.measurement_report import build_report
    rep = build_report(_fpg_sheet(tmp_path), argyll_bin="/fake/argyll")
    aims = rep["strip_corner_aims"]
    assert aims["from"] == "profile" and aims["profile"] == "G.icc", aims
    assert len(aims["in_strip"]) == 7
    assert fake_profile and fake_profile[0][0] == 7
    assert fake_profile[0][2] == "a"               # the chart's intent
    cs = rep["control_strip"]
    assert cs["eligible"] and cs["max"] > 1.0, cs


def test_i_the_corner_table_keeps_the_ideal_values(tmp_path, fake_profile):
    """Knut's earlier "no" (§32.5): the corner rows and table are unchanged.

    MUTATION, proven red: put the predictions into `ref` itself (the corner
    table and "Solid colours, largest" read the shift)."""
    from workflow.measurement_report import build_report, row_values
    rep = build_report(_fpg_sheet(tmp_path), argyll_bin="/fake/argyll")
    v = row_values(rep)["solids_de00_max"]["value"]
    assert v is not None and v < 0.05, v
    for c in rep["corners"]:
        if c.get("name") != "W" and c.get("de") is not None:
            assert c["de"] < 0.05, c


def test_i_without_a_profile_the_strip_keeps_the_ideal_and_says_so(
        tmp_path, fake_profile):
    """No built profile in the run: today's comparison, and the strip rows
    carry M-REPORT-STRIP-CORNERS-IDEAL.

    MUTATION, proven red: map CORNER_AIMS_IDEAL to no note in `row_values`."""
    from workflow.measurement_report import (NOTE_STRIP_CORNERS_IDEAL,
                                             build_report, row_values)
    rep = build_report(_fpg_sheet(tmp_path, run_profile=False),
                       argyll_bin="/fake/argyll")
    assert rep["strip_corner_aims"]["from"] == "ideal"
    assert rep["control_strip"]["max"] < 0.05
    assert NOTE_STRIP_CORNERS_IDEAL in \
        row_values(rep)["control_strip_de00_avg"]["notes"]


def test_i_the_strip_rows_carry_the_two_comparisons_note(
        tmp_path, qapp, fake_profile):
    """The note on the strip rows, listed once, with its §M words.

    MUTATION, proven red: map CORNER_AIMS_FROM_PROFILE to no note in
    `row_values`."""
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_messages as M
    from workflow.measurement_report import (NOTE_STRIP_CORNERS_PREDICTED,
                                             build_report, row_values)
    ti3 = _fpg_sheet(tmp_path)
    rep = build_report(ti3, argyll_bin="/fake/argyll")
    vals = row_values(rep)
    for rid in ("control_strip_de00_avg", "control_strip_de00_max"):
        assert NOTE_STRIP_CORNERS_PREDICTED in vals[rid]["notes"], rid
    # a set that puts a number on the strip rows, so they carry a verdict;
    # the worker's sandboxed settings are put back afterwards
    s = _settings()
    before = s.get("compliance_default_set", "")
    s.set("compliance_default_set", "custom_iso_12647_7")
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    try:
        said = {t: w for _n, w, t in dlg._numbered_notes([rep])}
        assert M.M_REPORT_STRIP_CORNERS_PREDICTED.render()[1] in said, said
    finally:
        _dispose(dlg)
        s.set("compliance_default_set", before)


def test_i_an_ordinary_chart_is_unchanged(tmp_path, fake_profile):
    """Every other chart kind: no prediction asked, no note.

    MUTATION, proven red: drop the `ref_source == "colorimetric"` test before
    asking for predictions (and record them for any chart)."""
    from workflow.measurement_report import build_report, row_values
    rep = build_report(_project(tmp_path, with_paper=True),
                       argyll_bin="/fake/argyll")
    assert rep["strip_corner_aims"] == {"from": "not_applicable"}
    assert not fake_profile
    assert not any(n.startswith("strip_corners")
                   for c in row_values(rep).values() for n in c["notes"])


def test_i_a_report_saved_before_it_is_worked_out_again():
    """MUTATION, proven red: take "strip_corner_aims" out of
    ALWAYS_BUILT_BLOCKS."""
    from ui.dialogs.measurement_report_dialog import (
        ALWAYS_BUILT_BLOCKS, _report_needs_rebuilding)
    from workflow.measurement_report import REPORT_SCHEMA
    rep = {"schema": REPORT_SCHEMA, "de00": {"avg_all": 1.0}}
    for k in ALWAYS_BUILT_BLOCKS:
        rep[k] = {}
    del rep["strip_corner_aims"]
    assert _report_needs_rebuilding(rep)


def test_i_the_demo_generator_places_a_solid_between_its_two_aims():
    """The demo pack's FROM PROFILE GAMUT solids: the designed hue difference
    from the ideal is kept exactly, the solid row's budget is kept, and the
    ideal is left alone when it already fits the strip.

    MUTATION, proven red: return the ideal from `_between_two_aims` always
    (the strip difference stays the whole gap)."""
    import importlib
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                            / "scripts"))
    gen = importlib.import_module("make_report_limit_demos")
    from workflow.measurement_report import _hue_difference_ab
    from workflow.ti3_analysis import ciede2000
    ideal, pred = (97.1, -21.6, 94.5), (93.2, -14.9, 90.9)   # 3.8 apart
    got = gen._between_two_aims(ideal, pred, 0.4, (2.0, 3.0))
    assert abs(_hue_difference_ab(got, ideal) - 0.4) < 0.02, got
    assert ciede2000(got, ideal) <= 0.85 * 2.0 + 1e-6
    assert ciede2000(got, pred) < ciede2000(ideal, pred) - 1.0
    near = (96.9, -21.4, 94.3)
    assert gen._between_two_aims(ideal, near, None, (2.0, 3.0)) == ideal
