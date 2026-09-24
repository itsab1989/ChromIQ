"""Beta 40 challenge B (texts, EN and DE): the fixes (B8-940 to B8-953).

Each behaviour test names the mutation it was proved red against
(`~/Desktop/ChromIQ-beta40-proof/challenge-B-fixes/mutations.txt`); the text
items are guarded by their old and new phrase, in English and in German.

Spec: `docs/design/measurement_report_limits.md` §25.3, §25.5, §26.1, §26.2,
§26.4, §26.5 and §19.1 (K18); §M-PROPOSED M-REPORT-CHART-MISMATCH-NO-GREY.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402
from PyQt6.QtWidgets import QApplication                       # noqa: E402

import ui.dialogs.measurement_report_dialog as mrd             # noqa: E402
from workflow.compliance_sets import ROW_BY_ID, effective_limits  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DE = json.loads((ROOT / "data" / "i18n" / "de.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _text(body_html: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", " ", body_html))


def _open(tmp_path, qapp):
    from tests.test_trend_graphs_for_judged_metrics import _open as o
    return o(tmp_path, qapp, effective_limits("chromiq_default", {}))


def _two_run_profiling_window(tmp_path, qapp):
    """A Profiling window on run 1 of a project whose two runs each hold a
    measured sheet: one source, both runs' sheets in its history."""
    from core.file_manager import Project
    from tests.test_calibration_reports import _settings
    from tests.test_import_measurement_module import _cgats, _PATCHES
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    proj = Project.create(tmp_path / "P", "P")
    run1 = proj.current_run()
    run1.ensure_dir()
    run2 = proj.new_run()
    run2.ensure_dir()
    from workflow.measurement_report import (REPORT_TYPE_RECORD, build_report,
                                             save_report, set_report_type)
    for r in (run1, run2):
        t = r.dir / "P.ti3"
        t.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
        rep = build_report(t)
        set_report_type(rep, REPORT_TYPE_RECORD)
        save_report(rep, r.dir)
    dlg = MeasurementReportDialog(_settings(), None,
                                  initial_ti3=run1.dir / "P.ti3")
    dlg.show()
    qapp.processEvents()
    return dlg, run1, run2


# ---------------------------------------------------------------------------
# 1. "Default for this run" only for a report of ONE profile run (B8-940)
# ---------------------------------------------------------------------------
def test_the_run_default_row_is_hidden_for_a_report_of_several_runs(
        tmp_path, qapp, monkeypatch):
    """§25.5: the row is shown when the window is opened from a report of
    one profile run. A Profiling window lists every run's sheet from ONE
    source, so the source count said "one run" for a report of two.

    MUTATION, proven red: delete the `_profile_runs_of_the_report` check in
    `_run_for_its_own_default` (the row is built, live, for two runs)."""
    import ui.dialogs.thresholds_dialog as td
    dlg, run1, run2 = _two_run_profiling_window(tmp_path, qapp)
    seen = {}

    def _exec(self):
        seen["rows"] = sorted(self._run_default_radios)
        self.done(0)
        return 0

    monkeypatch.setattr(td.ThresholdsDialog, "exec", _exec)
    try:
        assert len({str(r.get("_origin_dir")) for r in dlg._history}) == 2
        dlg._hidden_runs = set()
        assert len(dlg._profile_runs_of_the_report()) == 2
        assert dlg._run_for_its_own_default() is None
        dlg._on_open_limits()
        qapp.processEvents()
        assert seen["rows"] == [], "a live Default for this run row, two runs"
        # only run 1's sheet ticked: one profile run, the row is back
        dlg._hidden_runs = {dlg._run_key(r) for r in dlg._history
                            if str(r.get("_origin_dir")) == str(run2.dir)}
        assert dlg._run_for_its_own_default() is not None
        dlg._on_open_limits()
        qapp.processEvents()
        assert seen["rows"], "the row is gone for a report of one run"
    finally:
        dlg.close()


def test_the_judged_against_help_says_when_the_row_is_there():
    """The help sentence is true of the new rule, in English and German."""
    src = (ROOT / "ui" / "dialogs" / "measurement_report_dialog.py").read_text(
        encoding="utf-8")
    assert "With \"\n               \"one profile run loaded it also sets" not in src
    key = next(k for k in DE if k.startswith(
        "Every row of the results is compared with one limit set"))
    assert "When every measurement ticked is of one profile run, it also sets" in key
    assert "one profile run loaded" not in key
    assert "Sind alle angehakten Messungen aus einem einzigen Profillauf" in DE[key]


# ---------------------------------------------------------------------------
# 2. "How evenness was judged" only above a JUDGED evenness row (B8-941)
# ---------------------------------------------------------------------------
def _printing(dlg, monkeypatch, rows):
    monkeypatch.setattr(dlg, "_verdict_rows", lambda r: (rows, False))
    r = {"is_verification": True, "yardstick": "media-relative",
         "printing": {"colour": "through-profile", "intent": "relative"}}
    return _text(dlg._printing_block_html(r))


def test_the_evenness_line_is_not_printed_over_two_n_a_rows(
        tmp_path, qapp, monkeypatch):
    """MUTATION, proven red: drop `and x.get("word") != N_A and
    x.get("value") is not None` from `_evenness_row_is_in_report`."""
    dlg = _open(tmp_path, qapp)
    try:
        na = [{"row_id": "uniformity_sd", "word": "N-A", "value": None},
              {"row_id": "uniformity_de00_max_from_mean", "word": "N-A",
               "value": None},
              {"row_id": "all_de00_avg", "word": "PASS", "value": 0.8}]
        assert "How evenness was judged" not in _printing(dlg, monkeypatch, na)
        judged = [dict(na[0], word="PASS", value=0.4)] + na[1:]
        assert "How evenness was judged" in _printing(dlg, monkeypatch, judged)
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 3. the strip: the page's rows, the report's set, a lever for the chart
# ---------------------------------------------------------------------------
def _strip(dlg, monkeypatch, raw_rows, page_rows, sheet_extra=None):
    from workflow.run_compliance import RunLimits
    subject = dict(dlg._report or {}, **(sheet_extra or {}))
    page = dict(subject, _page_copy=True)
    monkeypatch.setattr(dlg, "_report", subject, raising=False)
    monkeypatch.setattr(dlg, "_runs_for_document", lambda: [page])
    monkeypatch.setattr(dlg, "_judged_by_the_document",
                        lambda rows: [page for _ in rows])
    monkeypatch.setattr(dlg, "_verdict_rows", lambda r: (
        (page_rows if r.get("_page_copy") else raw_rows), False))
    monkeypatch.setattr(dlg, "_ungraded_by_type", lambda: False)
    monkeypatch.setattr(dlg, "_report_limits", lambda: RunLimits(
        "chromiq_default", "THE REPORT'S SET", {}, label_en="x",
        bound=False))
    monkeypatch.setattr(dlg, "_window_limits", lambda: RunLimits(
        "chromiq_tight", "THE WINDOW'S SET", {}, label_en="y", bound=False))
    return dlg._mismatch_text()


def test_the_strip_names_only_the_rows_the_page_shows(
        tmp_path, qapp, monkeypatch):
    """The FPG case: the date's own saved report (its own set, its own
    edited numbers) read N-A on a row the report's set does not show.

    MUTATION, proven red: put back `if r not in _pages: _pages = [r] +
    _pages` (the raw subject's row is listed); or `lim =
    self._window_limits()` (the strip names the window's set)."""
    dlg = _open(tmp_path, qapp)
    try:
        strip_row = {"row_id": "control_strip_de00_p95", "word": "N-A",
                     "value": None, "reason": "no_control_strip"}
        grey_row = {"row_id": "grey_balance_neutral_ramp_avg", "word": "N-A",
                    "value": None, "reason": "too_few_levels"}
        assert _strip(dlg, monkeypatch, [strip_row], []) == ""
        txt = _strip(dlg, monkeypatch, [strip_row], [grey_row])
        assert "THE REPORT'S SET" in txt and "THE WINDOW'S SET" not in txt
        assert ROW_BY_ID["control_strip_de00_p95"].label not in txt
    finally:
        dlg.deleteLater()


def test_the_grey_lever_is_named_only_for_a_device_grey_row(
        tmp_path, qapp, monkeypatch):
    """§26.5: a FROM PROFILE GAMUT chart's grey steps are its neutral aims,
    and its lever is a larger chart, never grey steps; and a list with no
    grey row in it has no use for a grey lever.

    MUTATION, proven red: always choose M_REPORT_CHART_MISMATCH in
    `_mismatch_text` (the grey ramp is named under a strip-only list)."""
    dlg = _open(tmp_path, qapp)
    try:
        strip = {"row_id": "control_strip_de00_p95", "word": "N-A",
                 "value": None, "reason": "no_control_strip"}
        grey = {"row_id": "grey_balance_neutral_ramp_avg", "word": "N-A",
                "value": None, "reason": "too_few_levels"}
        lever = "Neutral grey ramp"
        assert lever not in _strip(dlg, monkeypatch, [], [strip])
        assert lever in _strip(dlg, monkeypatch, [], [strip, grey],
                               {"reference_source": "design"})
        assert lever not in _strip(dlg, monkeypatch, [], [strip, grey],
                                   {"reference_source": "colorimetric"})
    finally:
        dlg.deleteLater()


def test_the_no_grey_closing_is_catalogued_and_proposed():
    from workflow.measurement_messages import (CATALOGUE,
                                               M_REPORT_CHART_MISMATCH_NO_GREY)
    m = M_REPORT_CHART_MISMATCH_NO_GREY
    assert CATALOGUE[m.id] is m and not m.approved
    assert "grey" not in m.body.lower()
    doc = (ROOT / "docs" / "design" / "unified_measurement_management.md"
           ).read_text(encoding="utf-8")
    assert "### M-REPORT-CHART-MISMATCH-NO-GREY · PROPOSED" in doc


# ---------------------------------------------------------------------------
# 4. Edit limits: the tooltip says what the window writes (B8-943, §25.3)
# ---------------------------------------------------------------------------
def test_the_preferences_default_radio_writes_at_once_and_says_so(
        tmp_path, qapp):
    """The behaviour is kept (a click on "Default for new reports" stores
    Preferences at once, as the Preferences columns beside it always have),
    and the tooltips now say so; §25.3 records it.

    MUTATION, proven red: drop the `if self._buffer is None:` sentence from
    the radio's tooltip (the window says nothing about writing at once)."""
    from tests.test_calibration_reports import _settings
    from ui.dialogs.thresholds_dialog import ReportLimitsColumn, ThresholdsDialog
    from workflow.run_compliance import RunLimits
    s = _settings(compliance_default_set="chromiq_default")
    lim = RunLimits("chromiq_default", "ChromIQ default",
                    effective_limits("chromiq_default", {}), bound=False)
    dlg = ThresholdsDialog(s, None, run=ReportLimitsColumn(lim, columns=[]),
                           run_editable=True, report_column=True)
    try:
        rb = dlg._default_radios["chromiq_tight"]
        assert "stores it at once" in rb.toolTip()
        rb.click()
        qapp.processEvents()
        assert s.get("compliance_default_set") == "chromiq_tight"
    finally:
        dlg.deleteLater()
    src = (ROOT / "ui" / "dialogs" / "measurement_report_dialog.py").read_text(
        encoding="utf-8")
    assert "“This report”, beside every limit set. A change applies " not in src
    key = next(k for k in DE if k.startswith(
        "Opens the limits of the report shown"))
    assert "a change there is stored at once" in key
    assert "sofort gespeichert" in DE[key]
    spec = (ROOT / "docs" / "design" / "measurement_report_limits.md"
            ).read_text(encoding="utf-8")
    assert "B8-943" in spec


# ---------------------------------------------------------------------------
# 5, 7, 8. one name for one figure (B8-944)
# ---------------------------------------------------------------------------
def test_a_split_verification_names_its_limit_lines_within_gamut(
        tmp_path, qapp, monkeypatch):
    """The Colour accuracy legend said "…, within gamut" and the note of the
    line beside it did not.

    MUTATION, proven red: call `_limit_line_note` without the name in
    `_trend_extras` (the note prints the plain name)."""
    dlg = _open(tmp_path, qapp)
    try:
        split = [{"gamut_split": {"de00_in": {"avg_all": 1.0}},
                  "is_verification": True}]
        monkeypatch.setattr(dlg, "_document_runs_for_graphs", lambda: split)
        monkeypatch.setattr(dlg, "_ungraded_by_type", lambda: False)
        monkeypatch.setattr(dlg, "_accuracy_thresholds", lambda: (2.0, 3.0))
        notes = dlg._trend_extras(dlg._trend_de)["line_notes"]
        within = dlg._row_name("all_de00_avg", split)
        assert within.endswith("within gamut"), within
        assert any(within in n for n in notes), notes
        legend = [m[0] for m in dlg._trend_configs()[0][2]]
        assert any(within in x for x in legend), legend
        # and the evenness lines, whose rows are judged within gamut too
        monkeypatch.setattr(dlg, "_judged_trend_limits",
                            lambda: {"uniformity_sd": 1.5})
        even = dlg._trend_extras(dlg._trend_groups["evenness"])["line_notes"]
        name = dlg._row_name("uniformity_sd", split)
        assert name.endswith("within gamut") and any(name in n for n in even), even
    finally:
        dlg.deleteLater()


def test_a_profiling_sheet_or_a_printing_record_uses_the_plain_names(
        tmp_path, qapp, monkeypatch):
    """"…, within gamut" says the JUDGED figure is the within-gamut one. A
    profiling sheet is never graded, and a Printing record judges nothing.

    MUTATION, proven red: `_names_within_gamut` returning
    `_doc_is_split(runs)` (the profiling sheet's rows say within gamut)."""
    from workflow.measurement_report import REPORT_TYPE_FULL, REPORT_TYPE_RECORD
    dlg = _open(tmp_path, qapp)
    try:
        prof = [{"gamut_split": {"n_in": 3}, "is_verification": False}]
        ver = [{"gamut_split": {"n_in": 3}, "is_verification": True}]
        monkeypatch.setattr(dlg, "_report_type_now", lambda: REPORT_TYPE_FULL)
        assert not dlg._names_within_gamut(prof)
        assert dlg._names_within_gamut(ver)
        assert dlg._row_name("all_de00_avg", prof) == \
            ROW_BY_ID["all_de00_avg"].label
        monkeypatch.setattr(dlg, "_report_type_now",
                            lambda: REPORT_TYPE_RECORD)
        assert not dlg._names_within_gamut(ver)
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# 6. every limit line quotes its row's version 1 name (B8-945)
# ---------------------------------------------------------------------------
def test_every_limit_line_note_quotes_the_rows_name():
    for rid, note in mrd._LIMIT_NOTES.items():
        assert note() == f"the limit for “{ROW_BY_ID[rid].label}”.", rid
    assert mrd._LIMIT_NOTES["uniformity_sd"]("X, within gamut") == \
        "the limit for “X, within gamut”."
    assert not any(k.startswith("the limit for the colour cast of the worst")
                   for k in DE)


# ---------------------------------------------------------------------------
# 10, 11. no run in the report's own controls (B8-946, B8-947)
# ---------------------------------------------------------------------------
def test_the_type_and_set_labels_name_no_run():
    src = (ROOT / "ui" / "dialogs" / "measurement_report_dialog.py").read_text(
        encoding="utf-8")
    assert 'tr("Judged against ({run}):")' not in src
    assert 'tr("Report type ({run}):")' not in src
    assert "Judged against ({run}):" not in DE
    assert "Report type ({run}):" not in DE
    assert not any("No profile run's limits change" in k for k in DE)
    k = ("Judge this report against this set. The choice is this report's: "
         "it is applied when you press Generate report, and no saved report "
         "changes.")
    assert "Bericht erzeugen" in DE[k]


# ---------------------------------------------------------------------------
# 12. K18: statements about the report; "recorded" only of a saved one
# ---------------------------------------------------------------------------
def test_a_verdict_judged_just_now_is_not_called_recorded(tmp_path, qapp):
    """Under "New report…", before Generate, every column is a copy judged
    just now; it carries a verdict like a saved one.

    MUTATION, proven red: remove the `recorded and self._is_judged_now(r)`
    branch of `_verdict_provenance` ("recorded … when the report was made"
    under a report not yet made)."""
    dlg = _open(tmp_path, qapp)
    try:
        r = dlg._history[0]
        live = dlg._judged_live(r, dlg._report_limits())
        said = dlg._verdict_provenance(live, True)
        assert "recorded" not in said and "is judged against this report" in said
        assert "when the report was made" in dlg._verdict_provenance(
            dict(live), True)
    finally:
        dlg.deleteLater()


def test_no_report_text_explains_an_earlier_chromiq():
    for k in DE:
        assert "did not yet keep the verdict" not in k, k[:80]
        assert "Every report saved from now on" not in k, k[:80]
    assert not any("ChromIQ-Version gespeichert" in v for v in DE.values())


# ---------------------------------------------------------------------------
# 9, 14, 15, 16, 17, 23, 24, 28, 30, 32, 33: the words
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("old, new, de_old, de_new", [
    ("report has two or more runs", "report has two or more measurements",
     "zwei oder mehr Durchgänge", "zwei oder mehr Messungen"),
    ("need at least two runs; with a single run",
     "need at least two measurements; with a single measurement",
     "mindestens zwei Läufe", "mindestens zwei Messungen"),
    ("“Verification measurement” option on the Measure tab",
     "made with Run type Verification",
     "Option „Verification measurement“", "mit dem Lauftyp Verifizierung"),
    ("ChromIQ measures no tone value",
     "ChromIQ measures the lightness of tone steps, not the tone value",
     "ChromIQ misst keinen Tonwert", "nicht den Tonwert (die Flächendeckung)"),
    ("none lies within {tol} of the tone value",
     "none lies within {tol} percentage points of the tone value",
     "innerhalb von {tol} um den Tonwert",
     "innerhalb von {tol} Prozentpunkten um den Tonwert"),
    ("With a typical print that wants about 30",
     "On a typical print this takes about 30", None, None),
    ("Every number is a colour difference",
     "Most numbers are colour differences in ΔE00",
     "Jede Zahl ist ein Farbunterschied",
     "Die meisten Zahlen sind Farbunterschiede in ΔE00"),
    ("answered by measuring one verification chart",
     "answered by measuring the same chart more than once", None,
     "indem dasselbe Chart mehr als einmal gemessen wird"),
])
def test_the_old_words_are_gone_and_the_new_ones_are_there(old, new, de_old,
                                                         de_new):
    assert not any(old in k for k in DE), old
    keys = [k for k in DE if new in k]
    assert keys, new
    if de_old:
        assert not any(de_old in v for v in DE.values()), de_old
    if de_new:
        assert any(de_new in DE[k] for k in keys), de_new


def test_the_german_terms_are_the_reports_own():
    """23/24: "Grenzwertsatz" (never "Grenzwertset"), and the note the
    report prints is an "Anmerkung"."""
    assert not any("Grenzwertset" in v for v in DE.values())
    assert not any("die Notiz unter den Ergebnissen" in v for v in DE.values())
    assert any("die Anmerkung unter den Ergebnissen" in v for v in DE.values())


def test_a_level_carries_the_decimal_mark_of_its_language():
    """16. MUTATION, proven red: `_level_text` returning `f"{v:g}"`."""
    from core import i18n
    before = i18n.current_language()
    try:
        i18n.set_language("de")
        assert mrd._level_text(59.4) == "59,4" and mrd._level_text(50) == "50"
        i18n.set_language("en")
        assert mrd._level_text(59.4) == "59.4"
    finally:
        i18n.set_language(before)


def test_the_demo_descriptions_speak_of_the_reports_limits():
    """17: K31, limits are a report's; no run has edited limits."""
    src = (ROOT / "scripts" / "make_report_limit_demos.py").read_text(
        encoding="utf-8")
    assert "edited for this run" not in src
    assert re.search(r'edited for "\s*"this run', src) is None
    assert "limits edited for its reports" in src


def test_a_heading_over_one_entry_is_singular(tmp_path, qapp):
    """32. MUTATION, proven red: the old one-line plural `intro` in
    `_scope_html` (one date under "…verification runs are included")."""
    dlg = _open(tmp_path, qapp)
    try:
        runs = dlg._runs_for_report()[:1]
        txt = _text(dlg._scope_html(runs))
        assert "· 1 measurement" in txt
        assert "runs are included" not in txt, txt
        assert "run is included" in txt, txt
    finally:
        dlg.deleteLater()
    for k, g in (("The following profile verification run is included:",
                  "Der folgende Profil-Verifizierungslauf ist enthalten:"),
                 ("The following calibration measurement is included:",
                  "Die folgende Kalibrierungsmessung ist enthalten:")):
        assert DE[k] == g


def test_a_calibration_report_names_no_profile(tmp_path, qapp):
    """33. MUTATION, proven red: always print "Profile name: {name}" in
    `_detailed_section_html`."""
    from tests.test_calibration_reports import _project_with_cal, _settings, _window
    _p, ti3 = _project_with_cal(tmp_path, "P")
    dlg = _window(_settings(), ti3, qapp, "calibration")
    try:
        body = _text(dlg._detailed_section_html(dlg._runs_for_document()))
        assert "Calibration chart:" in body and "Profile name" not in body
    finally:
        dlg.close()
