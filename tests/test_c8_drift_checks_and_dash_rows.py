"""Challenge 8 of beta 44: the report findings C2, C3, C5 and C6
(B8-1370 to B8-1376; spec §45.2, §45.3, §6).

C2 (B8-1370). A raw drift check saved by beta 43 under ISO 12647-7 kept its
paper and solid rows as N-A ("needs a reference for the printing condition")
and every other row INFO, with ``graded: False``. Beta 44 counted N-A as a
verdict in `drift_check_judges`, so the saved column stopped being drift-only:
N-A in three cells, INFO as its Overall word, the sentence "On them the paper
and the solid colours are judged against the profile" under a column that
judged nothing, and the profiling sheet's footnote ("It was measured to build
a profile rather than to check one") on a verification. A column judges only
when a row really got PASS or FAIL.

C3 (B8-1371). `_dash_row_ids` skipped raw drift columns, so a report of drift
checks dropped no "–" row: the Overview listed three rows ISO 12647-7 leaves
at "–" and the Colour accuracy graph plotted them, with a "Max 3.0" line that
was `legacy_pair`'s fallback, described as the limit of a row the set does
not limit.

C5 (B8-1373). The presets window and the Measure pre-flight gave the two
solid rows the reason "This chart carries no colorimetric reference.", which
K49/K51 made untrue. The reason is now §M-PROPOSED M-VERIFY-SOLIDS-REASON.

C6 (B8-1375, B8-1376). A Printing record's guide said "every value in it reads
INFO" above N-A rows; a sheet printed through its profile with the absolute
intent was told "a raw print has no intent at all".

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta44-proof/fixes-8-report/mutations.txt).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _dialog(qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(_settings())


def _raw_sheet() -> dict:
    """A raw drift check: verification, design reference, printed raw."""
    return {"is_verification": True, "sheet_kind": "verification",
            "reference_source": "design", "printing": {"colour": "raw"},
            "de00": MR._stats([3.0 + 0.1 * i for i in range(60)])}


#: The verdict rows a beta 43 drift check saved under ISO 12647-7, as read
#: from the challenge's own saved report (Report-Limits-Border-Conditions,
#: run3, report_2026-09-26_16-39-58.json): the three rows whose reference is
#: the profile read N-A, needs_reference_file; the others INFO.
def _saved_b43_rows() -> "list[dict]":
    rows = [{"row_id": rid, "key": rid, "value": None, "threshold": thr,
             "should": False, "pass": None, "word": CS.N_A,
             "reason": MR.REASON_NEEDS_REFERENCE_FILE}
            for rid, thr in (("substrate_de00_max", 3.0),
                             ("solids_de00_max", 3.0),
                             ("cmy_solids_dhab_max", 2.5))]
    rows += [{"row_id": rid, "key": rid, "value": v, "threshold": thr,
              "should": False, "pass": None, "word": CS.INFO, "reason": None}
             for rid, v, thr in (("control_strip_de00_avg", 2.967, 2.5),
                                 ("control_strip_de00_max", 3.25, 5.0),
                                 ("all_de00_avg", 3.195, 2.5),
                                 ("all_de00_p95", 5.0, 5.0))]
    return rows


# --------------------------------------------------------------------------
# C2: N-A is not a verdict
# --------------------------------------------------------------------------
def test_n_a_on_the_three_rows_does_not_make_a_drift_check_judge():
    """Three N-A rows judge nothing; one PASS or FAIL does.

    MUTATION, proven red: put ``N_A`` back into the words
    `drift_check_judges` accepts."""
    rows = _saved_b43_rows()
    assert not MR.drift_check_judges(rows)
    rep = _raw_sheet()
    assert not MR.sheet_is_judged(rep, rows)
    assert MR.counted_rows(rep, rows) == rows
    judged = [dict(r) for r in rows]
    judged[1].update(word=CS.FAIL, value=5.4)
    assert MR.drift_check_judges(judged)
    judged[1]["word"] = CS.PASS
    assert MR.drift_check_judges(judged)


def test_a_saved_beta_43_drift_check_reads_drift_throughout(qapp, monkeypatch):
    """The saved column, shown by beta 44: "drift" in every cell and in
    Overall, "—" as what it was judged against, the old drift sentence, no
    claim that the paper and solids were judged, and no profiling footnote.

    MUTATION, proven red: put ``N_A`` back into `drift_check_judges` (the
    three cells read N-A, Overall INFO, the new sentence and the profiling
    footnote are printed)."""
    dlg = _dialog(qapp)
    try:
        rep = _raw_sheet()
        rows = _saved_b43_rows()
        monkeypatch.setattr(type(dlg), "_verdict_rows",
                            lambda self, r: ([dict(x) for x in rows], True))
        prof = ("This sheet is not graded, so its numbers are shown for "
                "information only. It was measured to build a profile rather "
                "than to check one, and a profiling measurement is expected "
                "to fall outside the accuracy limits. That is normal here, "
                "and it is not a fault.")
        monkeypatch.setattr(
            type(dlg), "_column_summary",
            lambda self, r: CS.Summary(CS.INFO, 0, 7, 0, 0, 3, prof))
        assert dlg._drift_only(rep) and not dlg._drift_judges(rep)
        assert "drift" in dlg._summary_cell(rep)
        assert "—" in dlg._thresholds_cell(rep)
        html = dlg._report_results_html([rep], [x["row_id"] for x in rows])
        assert "N-A" not in html.split("Overall")[0], "a cell reads N-A"
        assert "judged against the profile" not in html
        assert "so PASS and FAIL would be unfair" in html
        assert "measured to build a profile" not in html
        assert ">INFO<" not in html
    finally:
        dlg.deleteLater()


def test_the_guide_claims_no_judging_where_no_drift_column_judged(qapp):
    """"How to read this report" says the paper and solid rows are judged
    against the profile only where a drift column judged them; a document
    whose drift columns judge nothing keeps the sentence it had before K51.

    MUTATION, proven red: pass ``drift_judged=True`` always from `_render`
    (or ignore the keyword in `_how_to_read_html`)."""
    import html as _html
    import inspect
    import re
    import ui.dialogs.measurement_report_dialog as mrd
    dlg = _dialog(qapp)
    try:
        claim = "Its paper and solid colour rows are judged against the profile"
        said = _html.unescape(dlg._how_to_read_html([], drift_judged=False))
        assert claim not in said
        assert "in every cell instead" in said
        said = _html.unescape(dlg._how_to_read_html([], drift_judged=True))
        assert claim in said
    finally:
        dlg.deleteLater()
    src = re.sub(r"\s+", " ", inspect.getsource(mrd.MeasurementReportDialog))
    assert ("drift_judged=not any(_is_raw_drift(r) for r in runs) or "
            "any(self._drift_judges(r) for r in runs)") in src
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    key = next(k for k in de if k.startswith(
        "A column read as a drift check shows the word “drift” in every cell "
        "instead"))
    assert de[key] != key


# --------------------------------------------------------------------------
# C3: "–" rows, drift checks included
# --------------------------------------------------------------------------
def test_a_drift_column_takes_its_dash_rows_out_too(qapp, monkeypatch):
    """A document of raw drift checks under ISO 12647-7 drops the rows the
    set leaves at "–" from the Overview and the graphs, as every other
    report does (K51, B8-1332).

    MUTATION, proven red: skip `_is_raw_drift` columns in `_dash_row_ids`
    again."""
    dlg = _dialog(qapp)
    try:
        iso = dict(CS.effective_limits("iso_12647_7", {}))
        monkeypatch.setattr(type(dlg), "_row_limits_of",
                            lambda self, r: dict(iso))
        dash = dlg._dash_row_ids([_raw_sheet(), _raw_sheet()])
        for rid in ("all_de00_max", "best95_de00_avg", "worst5_de00_avg"):
            assert iso[rid].kind == "none", rid
            assert rid in dash, rid
        assert "all_de00_avg" not in dash
    finally:
        dlg.deleteLater()


def test_no_accuracy_line_comes_from_the_fallback_pair(qapp, monkeypatch):
    """Whatever the "–" filter catches, the Colour accuracy graph's Avg and
    Max lines stand only for numbers the set holds: under ISO 12647-7, which
    puts no number on "Maximum ΔE00, all patches", there is no Max line and
    no caption for one, even with nothing dropped as "–".

    MUTATION, proven red: drop the ``_numeric`` guard in
    `_accuracy_thresholds` (legacy_pair's 3.0 comes back as the Max line)."""
    dlg = _dialog(qapp)
    try:
        iso = dict(CS.effective_limits("iso_12647_7", {}))

        class _L:
            limits = iso
        monkeypatch.setattr(type(dlg), "_document_limits", lambda self: _L())
        monkeypatch.setattr(type(dlg), "_dash_row_ids",
                            lambda self, runs: set())
        monkeypatch.setattr(type(dlg), "_report_type_now",
                            lambda self: "t2_full_colour_check")
        avg, mx = dlg._accuracy_thresholds()
        assert avg == pytest.approx(float(iso["all_de00_avg"].number))
        assert mx is None
        notes, _extra = dlg._accuracy_line_plan()
        assert notes[1] == ""
        assert not any("Maximum ΔE00, all patches" in n for n in notes)
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------------------
# C5: the pre-flight's reason for the solid rows
# --------------------------------------------------------------------------
def test_the_solid_rows_reason_is_true_both_ways():
    """The presets window's and the pre-flight's reason for the two solid
    rows is M-VERIFY-SOLIDS-REASON, proposed in §M: it says why (printed
    through the profile) and what a raw print gets; it no longer blames a
    missing colorimetric reference. German by hand, no em dash, no "du".

    MUTATION, proven red: give REASON_NEEDS_REFERENCE_FILE its old line
    "This chart carries no colorimetric reference." in `reason_line`."""
    from ui.dialogs.preset_verification_dialog import reason_line
    from workflow import measurement_messages as M
    line = reason_line(MR.REASON_NEEDS_REFERENCE_FILE)
    assert line == M.M_VERIFY_SOLIDS_REASON.body
    assert "colorimetric reference" not in line
    assert "through its profile" in line and "without a profile" in line
    assert not M.M_VERIFY_SOLIDS_REASON.approved
    assert "M-VERIFY-SOLIDS-REASON" in M.PROPOSED
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    t = de[M.M_VERIFY_SOLIDS_REASON.body]
    assert t and t != line and "—" not in t and "—" not in line
    assert " du " not in f" {t} " and " dein" not in t


# --------------------------------------------------------------------------
# C6: two sentences that were false where they were printed
# --------------------------------------------------------------------------
def test_a_sheet_printed_through_the_profile_is_not_told_about_raw_prints(
        qapp):
    """"How the colours were judged" on a through-profile sheet judged as
    measured drops the clause about a raw print; a raw sheet keeps it.

    MUTATION, proven red: accept any recorded colour in the raw branch of
    `_printing_block_html` again."""
    dlg = _dialog(qapp)
    try:
        base = {"is_verification": True, "yardstick": "absolute",
                "reference_source": "design"}
        through = dlg._printing_block_html(
            dict(base, printing={"colour": "through-profile",
                                 "intent": "a"}))
        raw = dlg._printing_block_html(dict(base, printing={"colour": "raw"}))
        assert "a raw print has no" not in through
        assert "as measured, with no white adjustment" in through
        assert "a raw print has no" in raw
    finally:
        dlg.deleteLater()


def test_a_printing_records_guide_does_not_say_every_value_reads_info():
    """The INFO bullet of a report type that judges nothing says what is
    true beside an N-A row: every value it can work out reads INFO.

    MUTATION, proven red: restore "so every value in it reads INFO"."""
    import re
    import ui.dialogs.measurement_report_dialog as mrd
    src = Path(mrd.__file__).read_text(encoding="utf-8")
    flat = re.sub(r'"\s*\n\s*"', "", src)
    assert "so every value it can work out reads INFO." in flat
    assert "so every value in it reads INFO." not in flat
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    key = ("INFO: the number is shown for information only. This kind of "
           "report judges nothing, so every value it can work out reads "
           "INFO.")
    assert de.get(key) and de[key] != key
