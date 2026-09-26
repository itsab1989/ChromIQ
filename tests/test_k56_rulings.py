"""K56: Knut's answers in #182 5848287278 (beta 44).

1. M-VERIFY-SOLIDS-REASON is approved ("Answer: Approved."). It left
   §M-PROPOSED; `tests/test_message_catalogue.py` holds the document and the
   code in step, and `test_c8_drift_checks_and_dash_rows.py` its words.
2. The FROM PROFILE GAMUT paragraph of M-VERIFY-PREFLIGHT, revised as he
   accepted it (B8-1374): the solid rows are no longer "judged against a
   colorimetric reference".
3. The opening of a verification report whose sheets were ALL printed raw
   (B8-1377), his accepted words. Its last clause, "the paper and the solid
   colours are judged against the profile", is true only where every column
   judged them; under ChromIQ's own sets (those rows "–") and where no profile
   could be read (N-A) nothing was judged, and the sentence stops before the
   clause (B8-1381, a question for him). A document with one sheet printed
   through the profile keeps the approved sentence (a mixed document has no
   approved text yet, B8-1380).

Every test names the mutation that turns it red; each was run red
(~/Desktop/ChromIQ-beta44-proof/k56/mutations.txt).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow import compliance_sets as CS                     # noqa: E402
from workflow import measurement_messages as M                 # noqa: E402
from workflow import measurement_report as MR                  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

#: Knut's accepted words, #182 5848287278, verbatim.
GAMUT_PARAGRAPH = (
    "Some of the metrics listed above can be answered by a verification in "
    "only one way: its solid patches must be printed as they are, and a chart "
    "printed through its profile converts them. A chart built with FROM "
    "PROFILE GAMUT in the Create Chart tab prints them as they are.")
RAW_OPENING = (
    "This report follows the printer behind the profile built in {where}. "
    "Its sheets were printed without the profile, measured, and compared with "
    "the chart's own aim values; the paper and the solid colours are judged "
    "against the profile.")
#: The same, stopped before the clause the limit set decides (B8-1381).
RAW_OPENING_UNJUDGED = RAW_OPENING.split(";")[0] + "."
THROUGH_OPENING = (
    "This report judges the profile built in {where}. It was verified by "
    "printing a chart through that profile, measuring it, and comparing the "
    "measurements with the chart's own aim values. The measurements it covers "
    "are listed under Report Scope.")


def _de() -> dict:
    return json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _dialog(qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    return MeasurementReportDialog(_settings())


def _sheet(colour: str, when: str) -> dict:
    """A verification sheet of Demo, run 3, printed *colour* ("raw" or
    "profile"), against the chart's design colours."""
    return {"is_verification": True, "sheet_kind": "verification",
            "reference_source": "design", "printing": {"colour": colour},
            "chart": "Demo-verify", "ti3": "Demo-verify.ti3",
            "_origin_dir": f"/nowhere/Demo/runs/run3/verifications/{when}",
            "created": "2026-11-16T10:00:00",
            "de00": MR._stats([3.0 + 0.1 * i for i in range(60)])}


def _rows(solid_word: str) -> "list[dict]":
    """The three rows a raw print judges against the profile, the solid row
    reading *solid_word*, the other two N-A; one design row INFO."""
    rows = [{"row_id": rid, "key": rid, "value": None, "threshold": 3.0,
             "word": CS.N_A, "reason": MR.REASON_NEEDS_REFERENCE_FILE}
            for rid in ("substrate_de00_max", "solids_de00_max",
                        "cmy_solids_dhab_max")]
    rows[1].update(word=solid_word, value=5.4)
    rows.append({"row_id": "all_de00_avg", "key": "all_de00_avg",
                 "value": 3.1, "threshold": 2.5, "word": CS.INFO})
    return rows


def _opening(dlg, monkeypatch, runs, words):
    """The report's opening sentence, *words* giving each run's solid row."""
    by_id = {id(r): w for r, w in zip(runs, words)}
    monkeypatch.setattr(type(dlg), "_verdict_rows",
                        lambda self, r: (_rows(by_id[id(r)]), False))
    monkeypatch.setattr(type(dlg), "_report_kind",
                        lambda self, runs: "verification")
    return dlg._what_this_report_judges(runs)


# --------------------------------------------------------------------------
# 2. The FROM PROFILE GAMUT paragraph (B8-1374)
# --------------------------------------------------------------------------
def test_the_gamut_paragraph_is_knuts_accepted_revision():
    """His words, then the approved second paragraph unchanged. German by
    hand, no em dash, no "colorimetric reference" left in either language.

    MUTATION, proven red: restore the old first paragraph ("can be met in only
    one way: they are judged against a colorimetric reference")."""
    first, second = M.M_VERIFY_PREFLIGHT_GAMUT.split("\n\n")
    assert first == GAMUT_PARAGRAPH
    assert second.startswith("That button sits beside GUIDED and MANUAL")
    assert "colorimetric reference" not in M.M_VERIFY_PREFLIGHT_GAMUT
    de = _de()
    t = de[M.M_VERIFY_PREFLIGHT_GAMUT]
    assert t != M.M_VERIFY_PREFLIGHT_GAMUT
    assert "farbmetrische Referenz" not in t
    assert "AUS DEM PROFIL-GAMUT" in t and "Volltonfelder" in t
    assert "—" not in t and "—" not in first
    assert not any(k.startswith("Some of the metrics listed above can be met")
                   for k in de), "the old key is still in the catalogue"


# --------------------------------------------------------------------------
# 3. The opening of a report of raw sheets (B8-1377, B8-1380, B8-1381)
# --------------------------------------------------------------------------
def test_a_report_of_raw_sheets_that_judged_opens_with_knuts_sentence(
        qapp, monkeypatch):
    """Every sheet raw, every column judging its solid row: his accepted
    sentence, verbatim.

    MUTATION, proven red: delete the raw branch of
    `_what_this_report_judges` (the approved "verified by printing a chart
    through that profile" comes back over sheets printed without it)."""
    dlg = _dialog(qapp)
    try:
        runs = [_sheet("raw", "2026-11-16_100000"),
                _sheet("raw", "2026-11-23_100000")]
        said = _opening(dlg, monkeypatch, runs, [CS.FAIL, CS.PASS])
        assert said == RAW_OPENING.format(where="Demo, run 3"), said
        assert "through that profile" not in said
    finally:
        dlg.deleteLater()


def test_a_report_of_raw_sheets_that_judged_nothing_makes_no_claim(
        qapp, monkeypatch):
    """ChromIQ's own sets put "–" on the paper and solid rows, and a sheet
    with no readable profile reads N-A on all three: nothing was judged, so
    "the paper and the solid colours are judged against the profile" would be
    false. The sentence stops before it. One column that judged nothing among
    columns that did is enough to stop it, because the clause speaks for the
    whole document.

    MUTATION, proven red: drop the `all(self._drift_judges(...))` test (the
    clause is printed over columns that read "drift" throughout); and, as a
    second mutation, make it `any` (the mixed document gets the clause)."""
    dlg = _dialog(qapp)
    try:
        runs = [_sheet("raw", "2026-11-16_100000")]
        said = _opening(dlg, monkeypatch, runs, [CS.N_A])
        assert said == RAW_OPENING_UNJUDGED.format(where="Demo, run 3"), said
        assert "judged against the profile" not in said
        runs = [_sheet("raw", "2026-11-16_100000"),
                _sheet("raw", "2026-11-23_100000")]
        said = _opening(dlg, monkeypatch, runs, [CS.FAIL, CS.N_A])
        assert said == RAW_OPENING_UNJUDGED.format(where="Demo, run 3"), said
    finally:
        dlg.deleteLater()


def test_a_sheet_printed_through_the_profile_keeps_the_approved_sentence(
        qapp, monkeypatch):
    """A document of through-profile sheets, and a MIXED one, keep Knut's
    approved sentence of 2026-09-20: it is true of every sheet printed through
    the profile, and the mixed case has no approved text yet (B8-1380).

    MUTATION, proven red: test `any(_is_raw_drift(...))` instead of `all`
    (the mixed document says its sheets were printed without the profile)."""
    dlg = _dialog(qapp)
    try:
        runs = [_sheet("profile", "2026-11-16_100000")]
        said = _opening(dlg, monkeypatch, runs, [CS.PASS])
        assert said == THROUGH_OPENING.format(where="Demo, run 3"), said
        runs = [_sheet("profile", "2026-11-16_100000"),
                _sheet("raw", "2026-11-23_100000")]
        said = _opening(dlg, monkeypatch, runs, [CS.PASS, CS.FAIL])
        assert said == THROUGH_OPENING.format(where="Demo, run 3"), said
    finally:
        dlg.deleteLater()


def test_the_raw_openings_are_german_in_german():
    """By hand, placeholders kept, no em dash and no "du" (report text).

    MUTATION, proven red: set either German value back to its English key."""
    de = _de()
    for en in (RAW_OPENING, RAW_OPENING_UNJUDGED):
        t = de[en]
        assert t != en and "{where}" in t
        assert t.startswith("Dieser Bericht verfolgt den Drucker")
        assert "—" not in t and "—" not in en
        assert " du " not in f" {t} " and " dein" not in t
    assert "gegen das Profil beurteilt" in de[RAW_OPENING]
    assert "gegen das Profil beurteilt" not in de[RAW_OPENING_UNJUDGED]
