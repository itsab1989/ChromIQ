"""K51: Knut's rulings on the five K50 analyses (#182 5846167083 and
5846297769), B8-1330 to B8-1340.

A. (B8-1330, B8-1331) K50-1 option (2), "yes for both": on a raw print the
   paper row and the two solid rows are judged, their reference being the
   profile; the other rows stay INFO (the drift check); the drift sentence
   names the judged rows; the Overall word follows.
B. (B8-1332 to B8-1334) K50-2 option (A), "Yes": a "–" metric is not in the
   report, graphs included; the three graphs of the sheet itself carry their
   own sentence (Paper white's approved verbatim); and Knut's modification:
   where the report judges nothing, the limit lines ARE drawn, shown for
   information, with a note saying so.
C. (B8-1340) K50-3, the star, rule (4) "with modifications": under 900
   patches, a paper patch, every metric the patches decide, the evenness rows
   included from the laid-out preset; two pages (the data: no one-page i1Pro 3
   Plus preset on A4 or Letter answers evenness).
D. (B8-1335) K50-4 option (A), "yes": a FROM PROFILE GAMUT chart built with
   the media-relative intent is judged media-relative, the approved line.
E. (B8-1336) K50-5: the i1Pro group enabled with the engine on, the approved
   title and help.

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta44-proof/k51/mutations.txt).
"""
from __future__ import annotations

import os
import re
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402

from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _de_cat() -> dict:
    import json
    return json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# A. a raw print judges its paper and solid rows
# --------------------------------------------------------------------------
def _raw_sheet(k_solid: float = 5.4, paper: float = 0.4) -> dict:
    """A raw drift check (verification, design reference, printed raw)
    whose paper and solids were compared with the profile ((b2))."""
    return {
        "is_verification": True, "sheet_kind": "verification",
        "reference_source": "design", "printing": {"colour": "raw"},
        "de00": MR._stats([12.0 + 0.1 * i for i in range(60)]),
        "condition_reference": {
            "paper": {"from": MR.CONDITION_FROM_PROFILE, "de": paper},
            "solids": {"from": MR.CONDITION_FROM_PROFILE,
                       "de": {"C": 0.3, "M": 0.2, "Y": 0.1, "K": k_solid},
                       "dhab": {"C": 0.1, "M": 0.2, "Y": 0.1}}},
    }


def test_a_raw_print_judges_its_paper_and_solid_rows_against_the_profile():
    """ISO 12647-7 limits the paper (3.0) and both solid rows (3.0, 2.5): on
    the raw sheet those three get words, the solid black at 5.4 FAILs, and
    every design-referenced row stays INFO. The Overall word follows the
    judged rows, and counts only them.

    MUTATION, proven red: drop ``elif cell.get("graded") is True`` in
    `judge` (every row INFO again), or count INFO rows in `set_summary`."""
    rep = _raw_sheet()
    assert MR.is_drift_check(rep) and not MR.is_graded_sheet(rep)
    lim = CS.effective_limits("iso_12647_7", {})
    rows = {r["row_id"]: r for r in MR.judge(rep, lim)}
    assert rows["substrate_de00_max"]["word"] == CS.PASS
    assert rows["solids_de00_max"]["word"] == CS.FAIL
    assert rows["cmy_solids_dhab_max"]["word"] == CS.PASS
    assert rows["all_de00_avg"]["word"] == CS.INFO
    MR.stamp_verdict(rep, lim, set_id="iso_12647_7", set_label="ISO")
    v = rep["verdict"]
    assert v["graded"] is True and v["overall"] == CS.FAIL, v
    assert v["summary"]["total"] == 3 and v["summary"]["checked"] == 3, v
    assert v["all_pass"] is False


def test_a_set_with_no_limit_on_those_rows_leaves_the_drift_check_unjudged():
    """ChromIQ default puts "–" on all three: the sheet stays a drift check
    with no verdict, as before K51.

    MUTATION, proven red: make `sheet_is_judged` answer True for every
    drift check."""
    rep = _raw_sheet()
    lim = CS.effective_limits("chromiq_default", {})
    rows = MR.judge(rep, lim)
    assert not MR.drift_check_judges(rows)
    MR.stamp_verdict(rep, lim, set_id="chromiq_default", set_label="d")
    assert rep["verdict"]["graded"] is False
    assert rep["verdict"]["overall"] == CS.INFO


def test_a_column_judging_nothing_keeps_its_info_rows_in_the_count():
    """The INFO rows leave the count only where something WAS judged, so
    "nothing was graded" still reads as before (CH-17's sentence).

    MUTATION, proven red: drop INFO rows from `set_summary` whenever the
    column is graded."""
    v = CS.Limit.value(1.5)
    s = CS.set_summary([(v, CS.INFO), (v, CS.INFO)], set_is_iso=False,
                       graded=True)
    assert s.reason == CS.SUMMARY_REASONS["nothing_graded"]
    s = CS.set_summary([(v, CS.PASS), (v, CS.INFO)], set_is_iso=False,
                       graded=True)
    assert s.word == CS.PASS and s.total == 1


APPROVED_DRIFT = ("the paper and the solid colours are judged against the "
                  "profile; the other colours are compared with the chart's "
                  "design colours for information")


def test_the_drift_sentence_names_the_judged_rows_in_knuts_words(qapp,
                                                                 monkeypatch):
    """The words Knut approved ("yes for both"), in the sentence under the
    results of a drift column that judges, and in German by hand.

    MUTATION, proven red: keep printing the old sentence for a judging
    drift column (the `if self._drift_judges(r)` branch removed)."""
    import ui.dialogs.measurement_report_dialog as mrd
    # rendered, as the results print it: the new sentence where the column
    # judges, the old one where it judges nothing
    dlg = _dialog(qapp)
    try:
        rep = _raw_sheet()
        for sid, new_there in (("iso_12647_7", True),
                               ("chromiq_default", False)):
            rows = MR.judge(rep, CS.effective_limits(sid, {}))
            monkeypatch.setattr(type(dlg), "_verdict_rows",
                                lambda self, r, rows=rows: (
                                    [dict(x) for x in rows], False))
            html = dlg._report_results_html(
                [rep], [x["row_id"] for x in rows])
            assert ("On them the paper and the solid colours are judged "
                    "against the profile" in html) is new_there, sid
            assert ("so PASS and FAIL would be unfair" in html) \
                is (not new_there), sid
    finally:
        dlg.deleteLater()
    src = Path(mrd.__file__).read_text(encoding="utf-8")
    flat = re.sub(r'"\s*\n\s*"', "", src)
    assert APPROVED_DRIFT in flat.replace("On them t", "t")
    key = next(k for k in _de_cat() if "On them the paper and the solid" in k)
    de = _de_cat()[key]
    assert "gegen das Profil beurteilt" in de and " du " not in f" {de} "
    assert "—" not in key and "—" not in de


def _dialog(qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(_settings())


def test_a_drift_column_shows_words_on_the_judged_rows_only(qapp,
                                                            monkeypatch):
    """The column of a judging drift check: its Overall word is the judged
    rows' word, "Judged against" names the set, the paper and solid rows
    carry their words and every other cell reads "drift".

    MUTATION, proven red: `_summary_cell` asks `_is_raw_drift` again (the
    Overall cell reads "drift")."""
    dlg = _dialog(qapp)
    try:
        rep = _raw_sheet()
        rows = MR.judge(rep, CS.effective_limits("iso_12647_7", {}))
        monkeypatch.setattr(type(dlg), "_verdict_rows",
                            lambda self, r: ([dict(x) for x in rows], False))
        monkeypatch.setattr(
            type(dlg), "_column_summary",
            lambda self, r: CS.Summary(CS.FAIL, 3, 3, 1, 0, 0,
                                       CS.SUMMARY_REASONS["fail"]))
        assert dlg._drift_judges(rep) and not dlg._drift_only(rep)
        assert {x["row_id"] for x in dlg._rows_with_words(rep)} == set(
            MR.ROWS_JUDGED_ON_A_RAW_PRINT)
        cell = dlg._summary_cell(rep)
        assert "FAIL" in cell and "drift" not in cell, cell
        monkeypatch.setattr(type(dlg), "_verdict_rows",
                            lambda self, r: ([dict(x) for x in MR.judge(
                                r, CS.effective_limits("chromiq_default",
                                                       {}))], False))
        assert dlg._drift_only(rep)
        assert "drift" in dlg._summary_cell(rep)
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# B. "–" is not in the report; lines for information
# --------------------------------------------------------------------------
PAPER_WHITE_APPROVED = (
    "This graph shows the lightness of the paper on each date, as measured. "
    "It is a measurement of the sheet, not a judged metric, so no limit line "
    "is drawn; the trend shows whether the paper changes between dates.")


def test_the_paper_white_sentence_is_knuts_approved_wording():
    """Knut: *"Approved."*, verbatim, whatever the report judges.

    MUTATION, proven red: change one word of `_SHEET_GRAPH_NOTES["white"]`."""
    import ui.dialogs.measurement_report_dialog as mrd
    for why in (mrd.NO_LIMIT_WHY_SET, mrd.NO_LIMIT_WHY_RECORD,
                mrd.NO_LIMIT_WHY_ACCURACY):
        assert mrd.no_limit_note("white", why) == PAPER_WHITE_APPROVED
    for key in ("black", "corners"):
        t = mrd.no_limit_note(key)
        assert "It is a measurement of the sheet, not a judged metric, so " \
               "no limit line is drawn; the trend shows whether" in t, key
        de = _de_cat()[t]
        assert de != t and "—" not in de and " du " not in f" {de} "


def test_the_information_note_has_both_forms_in_both_languages():
    """One line or several: "the limit line is" / "the limit lines are".

    MUTATION, proven red: return the plural form for one line."""
    import ui.dialogs.measurement_report_dialog as mrd
    one, two = mrd.info_limit_note(1), mrd.info_limit_note(2)
    assert "the limit line is shown for information only" in one
    assert "the limit lines are shown for information only" in two
    assert one.startswith("This report records these measurements without "
                          "judging them")
    for t in (one, two):
        assert _de_cat()[t] != t


def test_the_key_under_a_graph_says_the_lines_are_for_information(qapp):
    """After the line notes, in the window's key and the PDF alike.

    MUTATION, proven red: drop the ``elif self._info_note`` branch of
    `_TrendChart.descriptions`."""
    import ui.dialogs.measurement_report_dialog as mrd
    from PyQt6.QtGui import QColor
    ch = mrd._TrendChart()
    series = [{"created": f"2026-01-0{i}T10:00:00",
               "rows": {"grey_balance_neutral_ramp_avg": 1.0 + 0.1 * i}}
              for i in (1, 2, 3)]
    metrics = [("Grey", QColor("#56d6a5"),
                lambda pt: (pt.get("rows") or {}).get(
                    "grey_balance_neutral_ramp_avg"))]
    ch.set_data(series, metrics, limit_lines=[(1.5, "Avg", QColor("#56d6a5"))],
                line_notes=["Avg (1.5 ΔCh): the limit for x."],
                info_note=mrd.info_limit_note(1))
    d = ch.descriptions()
    assert [k for k, _c, _t in d] == ["line", "note"]
    assert d[-1][2] == mrd.info_limit_note(1)
    assert mrd.html.escape(mrd.info_limit_note(1)) in mrd._trend_key_html(d)
    ch.deleteLater()


def test_a_printing_record_plots_the_rows_its_set_limits_and_no_dash_row(
        qapp, tmp_path, monkeypatch):
    """A record under a set that limits the grey average and leaves the grey
    maximum at "–": the Grey balance graph plots the average, with its line
    for information, and not the maximum.

    MUTATION, proven red: plot every row with values in a tab that judges
    nothing (K49's `_unlimited_trend_rows` back)."""
    from tests.test_trend_graphs_for_judged_metrics import _group, _open
    lim = dict(CS.effective_limits("chromiq_default", {}))
    lim["grey_balance_neutral_ramp_max"] = CS.Limit.none()
    dlg = _open(tmp_path, qapp, lim)
    try:
        monkeypatch.setattr(type(dlg), "_ungraded_by_type", lambda self: True)
        dlg._refresh_trend()
        qapp.processEvents()
        g = _group(dlg, "grey")
        assert [m[0] for m in g._metrics] == [
            "Average ΔCh, grey balance of the grey ramp"]
        assert [v for v, _w, _c in g._limit_lines] == [1.5]
        assert any(k == "note" and "information only" in t
                   for k, _c, t in g.descriptions())
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# C. the star
# --------------------------------------------------------------------------
def _values(paper=True, evenness=(0.8, 0.5), short=False) -> dict:
    v = {r.id: {"value": 0.0, "reason": None} for r in CS.ROWS}
    if not paper:
        v["substrate_de00_max"] = {"value": None,
                                   "reason": MR.REASON_NO_PAPER_PATCH}
    for rid, val in zip(MR.EVENNESS_ROWS, evenness):
        v[rid] = {"value": val, "reason": None,
                  "noise_p95": 0.2 if val is not None else None}
        if val is None:
            v[rid]["reason"] = MR.REASON_EVENNESS_GRID_TOO_SMALL
    if short:
        v["grey_balance_neutral_ramp_avg"] = {"value": None,
                                              "reason": MR.REASON_NO_GREYS}
    return v


def test_the_star_follows_rule_4_with_knuts_modifications(tmp_path,
                                                          monkeypatch):
    """One or two pages, fewer than 900 patches, a paper patch, no patch
    shortfall and both evenness rows answered.

    MUTATION, proven red: drop the paper-patch check, or the
    `evenness_answered` call, or set ``VERIFICATION_MAX_PAGES = 1``."""
    chart = tmp_path / "c.ti1"
    chart.write_text("x", encoding="utf-8")
    state = {"v": _values()}
    monkeypatch.setattr(PE, "chart_row_values",
                        lambda c, recipe=None, **k: state["v"])
    assert PE.VERIFICATION_MAX_PAGES == 2
    assert PE.VERIFICATION_PATCHES_UNDER == 900
    ok = PE.made_for_verification
    assert ok(chart, 308, 2)
    assert ok(chart, 899, 1)
    assert not ok(chart, 900, 1)
    assert not ok(chart, 462, 3)
    assert not ok(chart, 308, 2, relayoutable=False)
    state["v"] = _values(paper=False)
    assert not ok(chart, 308, 2)
    state["v"] = _values(evenness=(None, None))
    assert not ok(chart, 308, 2)
    state["v"] = _values(short=True)
    assert not ok(chart, 308, 2)


def test_evenness_counts_under_the_loosest_limit_of_any_set():
    """The star is a property of the chart: the evenness rows are asked
    under the loosest limit any set puts on them (1.5 and 2.0), the
    pre-flight's set-independent question.

    MUTATION, proven red: use ChromIQ default's 1.0 on the from-the-mean
    row in `evenness_answered`."""
    v = _values(evenness=(1.2, 1.4))
    for rid in MR.EVENNESS_ROWS:
        v[rid]["noise_p95"] = 1.2
    assert PE.evenness_answered(v)
    assert not PE.evenness_answered(v, CS.effective_limits("chromiq_default",
                                                          {}))


def test_the_star_line_says_the_rule_and_the_constants_agree():
    """The ★ line under the pulldowns: "one or two printed pages" is written
    out, so it is held to the constant here; German by hand, Du-Form.

    MUTATION, proven red: set ``VERIFICATION_MAX_PAGES = 3``."""
    import ui.dialogs.preset_verification_dialog as pvd
    src = re.sub(r'"\s*\n\s*"', "",
                 Path(pvd.__file__).read_text(encoding="utf-8"))
    m = re.search(r'"(★ marks a chart made for verification: [^"]+)"', src)
    assert m, "the star line is gone"
    key = m.group(1)
    assert "one or two printed pages" in key and PE.VERIFICATION_MAX_PAGES == 2
    assert "fewer than {patches} patches" in key
    assert "evenness" in key and "paper" in key
    de = _de_cat()[key]
    assert "eine oder zwei gedruckte Seiten" in de and "{patches}" in de
    assert "—" not in key and "—" not in de


# --------------------------------------------------------------------------
# D. a media-relative FROM PROFILE GAMUT chart
# --------------------------------------------------------------------------
_PAPER = (93.0, 1.5, 3.5)


def _bradford_onto(xyz, paper_xyz):
    """A relative XYZ carried onto a paper whose white is *paper_xyz*, by the
    Bradford adaptation, written out here rather than borrowed from the code
    under test (Lam 1985's matrix; D50 the Lab white)."""
    b = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367],
                  [0.0389, -0.0685, 1.0296]])
    d50 = np.array([96.422, 100.0, 82.521])
    m = np.linalg.inv(b) @ np.diag((b @ np.asarray(paper_xyz)) / (b @ d50)) @ b
    return m @ np.asarray(xyz, dtype=float)


def _relative_chart(tmp_path, intent: str) -> Path:
    """A FROM PROFILE GAMUT verification built with *intent*, measured by a
    printer that prints exactly as profiled on a paper of `_PAPER`: each
    patch's relative aim carried onto the paper (the way ArgyllCMS relates
    the two colorimetries); the bare paper reads the paper itself."""
    from core.file_manager import Project
    from tests.test_k34_knuts_section_a import _selection, _sheet
    from workflow.gamut_target import (mark_chart_as_colorimetric,
                                       reference_rows,
                                       write_colorimetric_reference)
    from workflow.ti3_analysis import _lab_to_xyz_array
    proj = Project.create(tmp_path / "G", "G")
    run = proj.current_run()
    run.ensure_dir()
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    sel = replace(_selection(_PAPER), intent=intent)
    sel.targets = [(i, (float(rng.uniform(25, 90)), float(rng.uniform(-40, 40)),
                        float(rng.uniform(-40, 40))),
                    (float(rng.uniform(5, 95)), float(rng.uniform(5, 95)),
                     float(rng.uniform(5, 95)))) for i in range(40)]
    rows = reference_rows(sel)
    stem = f"{run.stem}-verify"
    ti2 = _sheet(vdir / f"{stem}.ti2",
                 [(dev, (10.0, 10.0, 10.0)) for _s, dev, _l in rows],
                 kind="CTI2")
    ref = write_colorimetric_reference(sel, vdir / f"{stem}-reference.ti3")
    mark_chart_as_colorimetric(ti2, ref)
    date = vdir / "2026-10-05_100000"
    date.mkdir()
    paper_xyz = _lab_to_xyz_array(np.array([_PAPER]))[0]
    measured = []
    for _sid, dev, lab in rows:
        if tuple(dev) == (100.0, 100.0, 100.0):
            xyz = paper_xyz
        else:
            xyz = _bradford_onto(_lab_to_xyz_array(np.array([lab]))[0],
                                 paper_xyz)
        measured.append((dev, tuple(float(v) for v in xyz)))
    return _sheet(date / f"{stem}.ti3", measured)


def test_a_media_relative_chart_is_judged_relative_to_its_paper(tmp_path):
    """The same perfect print, the chart built relative and absolute: the
    relative one reads ~0 against its aims (it read the paper's distance
    from L* 100 before), the paper row stays absolute (the paper against the
    profile's paper: 0), and the record says why.

    MUTATION, proven red: drop the K51-D block of `build_report` (the
    relative chart reads about 5), or scale by the plain XYZ ratio in
    `media_relative_xyz` (0.2 and more)."""
    rel = MR.build_report(_relative_chart(tmp_path / "r", "relative"))
    assert rel["yardstick"] == "media-relative"
    assert rel["paper_white_used"] == {
        "from": MR.PAPER_WHITE_FROM_SHEET,
        "why": MR.PAPER_WHITE_CHART_RELATIVE}
    v = MR.row_values(rel)
    assert v["all_de00_avg"]["value"] < 0.02, v["all_de00_avg"]
    assert v["all_de00_max"]["value"] < 0.05
    assert v["substrate_de00_max"]["value"] == pytest.approx(0.0, abs=0.02)
    assert rel["evenness"]["aims"] == "on_the_paper"
    w = next(c for c in rel["corners"] if c["name"] == "W")
    assert w["lab"][0] == pytest.approx(_PAPER[0], abs=0.05)   # as measured
    ab = MR.build_report(_relative_chart(tmp_path / "a", "absolute"))
    assert ab["yardstick"] == "absolute"
    assert MR.row_values(ab)["all_de00_avg"]["value"] > 2.0


def test_the_approved_line_says_how_the_colours_were_judged(qapp):
    """Knut: *"Approved."*, verbatim, in "How the colours were judged".

    MUTATION, proven red: let the K37 (e) or the pairing-3 line answer for
    such a sheet (the branch order in `_printing_block_html`)."""
    dlg = _dialog(qapp)
    try:
        r = {"is_verification": True, "reference_source": "colorimetric",
             "printing": {"colour": "raw"}, "yardstick": "media-relative",
             "paper_white_used": {"from": MR.PAPER_WHITE_FROM_SHEET,
                                  "why": MR.PAPER_WHITE_CHART_RELATIVE},
             "colorimetric": {"intent": "relative"}}
        html = dlg._printing_block_html(r)
        assert ("relative to the paper white of this sheet, because the chart "
                "was built with the media-relative intent") in html
        assert "the print mapped white to the paper" not in html
    finally:
        dlg.deleteLater()


def test_a_saved_relative_report_says_it_was_worked_out_earlier():
    """A report saved before K51-D judged such a sheet as measured; its
    verdict is kept and the page says this version works it out otherwise.

    MUTATION, proven red: drop the K51-D clause of `_worked_out_differently`."""
    import ui.dialogs.measurement_report_dialog as mrd
    saved = {"paper_white_used": {"from": MR.PAPER_WHITE_NOT_USED},
             "condition_reference": {}, "strip_corner_aims": {},
             "paper_patch": True}
    rebuilt = {"paper_white_used": {"from": MR.PAPER_WHITE_FROM_SHEET,
                                    "why": MR.PAPER_WHITE_CHART_RELATIVE}}
    assert mrd._worked_out_differently(saved, rebuilt)
    assert not mrd._worked_out_differently(rebuilt, rebuilt)


# --------------------------------------------------------------------------
# E. the i1Pro group in Preferences > Chart Layout
# --------------------------------------------------------------------------
TITLE = "i1Pro margin and patch scale (Guided, and Manual with printtarg)"
HELP = ("Used by Guided mode, and by Manual mode when the ChromIQ layout "
        "engine is off. With the layout engine on, Manual takes the margins "
        "from Instrument Limits and the patch scale from the Chart Layout "
        "presets above, which you can set for each paper.")


def test_the_i1pro_group_is_enabled_with_the_engine_on(qapp, tmp_path):
    """Knut: *"Yes"* (Guided uses it whatever the engine setting), with the
    approved title; the old "Changes apply to both" sentence is gone.

    MUTATION, proven red: ``setEnabled(not engine_on)`` back in
    `_build_chart_layout_tab`."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", True)
    dlg = SettingsDialog(s)
    try:
        grp = dlg._i1pro_grp
        assert grp.isEnabled() and dlg._i1pro_preset_combo.isEnabled()
        assert grp.title() == TITLE
    finally:
        dlg.deleteLater()
    import ui.dialogs.settings_dialog as sd
    src = re.sub(r'"\s*\n\s*"', "", Path(sd.__file__).read_text(
        encoding="utf-8"))
    src = re.sub(r'"\s*\n(\s*#[^\n]*\n)*\s*"', "", src)
    assert HELP in src
    assert "Changes apply to both Guided and Manual mode" not in src
    de = _de_cat()
    assert de[TITLE] != TITLE
    k = next(k for k in de if HELP in k)
    assert "Messgeräte-Grenzwerten" in de[k] and " du " in f" {de[k]} "
    assert "—" not in k and "—" not in de[k]
