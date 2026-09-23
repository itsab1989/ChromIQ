"""Round B before beta 37: the report's TEXT, in English and German.

Each test names the finding it holds (challenge-B/REPORT.md) and the mutation
it was proved red against on 2026-09-23. Knut's rule K18 (#182 comment
5785414710): report text may be handed to a customer, so it never explains
ChromIQ, never speaks to the user, and says "the test chart used" and "the
printed test chart".
"""
from __future__ import annotations

import html as _html
import json
import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_beta37_round_fixes import (_settings,             # noqa: E402
                                           _stamped_profiling_run)

_DE = Path(__file__).resolve().parent.parent / "data" / "i18n" / "de.json"
_YOU = re.compile(r"\b(you|your|yours)\b", re.I)


def _text(dlg) -> str:
    body = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
    return " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", body)).split())


# ---------------------------------------------------------------------------
# H4: no "you", no ChromIQ explanation, no advice
# ---------------------------------------------------------------------------
def test_no_metric_blurb_speaks_to_the_reader():
    """The report guide prints each metric's own blurb: "How neutral your
    greys are", "where your chart asked", "the bare paper you printed on".

    MUTATION (proved red): put "How neutral your greys are on average" back
    in `compliance_sets`."""
    from workflow.compliance_sets import ROWS
    said = [r.id for r in ROWS if _YOU.search(r.blurb or "")]
    assert not said, f"metric blurbs that speak to the reader: {said}"


@pytest.mark.parametrize("which", ["full", "record"])
def test_the_report_neither_speaks_to_the_reader_nor_explains_chromiq(
        qapp, tmp_path, which):
    """The whole report body, detail on, of a graded Full colour check and of
    a Printing record.

    MUTATION (proved red): put "off — ChromIQ printed the sheet itself" back
    beside "Colour management at the printer", or "your instrument's own small
    uncertainty" back into the guide."""
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_report as mr
    from workflow import run_compliance as rc
    if which == "full":
        from tests.test_report_window_limit_controls import _verified_run
        proj, run, ti3s = _verified_run(tmp_path, dates=2)
        ti3 = ti3s[-1]
    else:
        run, ti3 = _stamped_profiling_run(tmp_path, "chromiq_default",
                                          "ChromIQ default (recommended)")
    dlg = MeasurementReportDialog(_settings(tmp_path), None, initial_ti3=ti3)
    try:
        if which == "full":
            rc.set_run_report_type(run, mr.REPORT_TYPE_FULL)
            dlg._forget_limits()
            dlg._sync_limit_controls()
        # the printing block names the route; put the one K18 is about on it
        for r in dlg._runs_for_report():
            r.setdefault("printing", {})["route"] = "chromiq"
        dlg._detail_check.setChecked(True)
        text = _text(dlg)
        assert "Colour management at the printer" in text
        assert "ChromIQ printed the sheet itself" not in text
        assert "re-profiling" not in text
        hits = sorted({m.group(0).lower() for m in _YOU.finditer(text)})
        where = [text[max(0, m.start() - 60):m.end() + 40]
                 for m in _YOU.finditer(text)][:3]
        assert not hits, f"the report speaks to its reader: {where}"
    finally:
        dlg.deleteLater()


def test_what_the_rising_numbers_mean_is_a_statement_not_advice():
    """"rising numbers over time show when it is worth re-profiling" becomes
    what the numbers mean. MUTATION: the old sentence back."""
    import inspect
    from ui.dialogs import measurement_report_dialog as d
    src = inspect.getsource(d)
    assert "worth re-profiling" not in src
    assert "profile describes the printer less well than it did" in src


# ---------------------------------------------------------------------------
# L5
# ---------------------------------------------------------------------------
def test_the_closing_sentence_says_why_and_not_what_a_row_needs():
    """MUTATION: the old "each note above names what that row needs"."""
    import inspect
    from ui.dialogs import measurement_report_dialog as d
    src = inspect.getsource(d)
    assert "each note above says why" in src
    assert "each note above names what that row needs" not in src


# ---------------------------------------------------------------------------
# M1: the one-page ISO summary names the unchecked values
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n,phrase", [
    (8, "the other 8 could not be worked out"),
    (1, "the one other value could not be worked out")])
def test_the_one_page_iso_summary_names_the_unchecked_values(n, phrase):
    """"12 of 20 values checked, all within this limit set's values." said
    nothing about the other 8.

    MUTATION (proved red): make `_one_page_summary` swap to
    `SUMMARY_REASONS["iso"]` again."""
    from workflow.compliance_sets import (PASS, SUMMARY_REASONS, Summary,
                                          summary_text)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    key = "iso_with_unchecked" if n > 1 else "iso_with_one_unchecked"
    sm = Summary(PASS, 20 - n, 20, 0, 0, n, SUMMARY_REASONS[key])
    out = summary_text(MeasurementReportDialog._one_page_summary(sm))
    assert phrase in out, out
    assert "listed below" not in out, "this page has no list to point at"
    assert "not a test against that standard" in out


# ---------------------------------------------------------------------------
# M5: the worst-5 % note names the in-gamut count that is short
# ---------------------------------------------------------------------------
def test_the_worst_five_note_says_what_is_short(monkeypatch):
    """"20 patches were measured ... at least 20 are needed" read as a
    condition met; 13 were inside the gamut.

    MUTATION (proved red): the old "at least 20 are needed to split off"."""
    import workflow.measurement_report as mr
    from ui.dialogs.measurement_report_dialog import _small_sample_sentence
    monkeypatch.setattr(mr, "graded_de00", lambda r: ({"n": 13}, "in_gamut"))
    s = _small_sample_sentence({"patches": 20})
    assert "13 of them fall inside the profile's gamut" in s
    assert "at least 20 inside it are needed" in s


# ---------------------------------------------------------------------------
# H5, M8, L3: German
# ---------------------------------------------------------------------------
def _de() -> dict:
    return json.loads(_DE.read_text(encoding="utf-8"))


def test_the_title_prefix_default_is_translated_and_a_custom_one_kept(
        tmp_path):
    """Every German PDF was headed "Measurement Report - Verification of
    Profile".

    MUTATION (proved red): make `report_title_prefix` return the stored
    string as it is."""
    import core.i18n as i18n
    from core.settings import report_title_prefix, report_title_to_store
    s = _settings(tmp_path)
    before = getattr(i18n, "current_language", lambda: "en")()
    try:
        i18n.set_language("de")
        assert report_title_prefix(s, "report_title_verification") == \
            "Messbericht - Verifizierung des Profils"
        assert report_title_prefix(s, "report_title_profiling") == \
            "Messbericht - Profilierung des Druckers"
        # a German user who never touched the box still has the default
        assert report_title_to_store(
            "report_title_verification",
            "Messbericht - Verifizierung des Profils") == \
            "Measurement Report - Verification of Profile"
        s.set("report_title_verification", "Prüfbericht Kunde A")
        assert report_title_prefix(s, "report_title_verification") == \
            "Prüfbericht Kunde A"
        assert report_title_to_store("report_title_verification",
                                     "Prüfbericht Kunde A") == \
            "Prüfbericht Kunde A"
    finally:
        i18n.set_language(before)


def test_the_report_prose_is_german_in_german():
    """"The ΔE figures measure a whole chain ..." and two provenance lines
    were English in de.json. MUTATION: set any of them back to its key."""
    d = _de()
    for k in d:
        if k.startswith(("The ΔE figures measure a whole chain",
                         "This date has no saved report of its own",
                         "This measurement is not in a project, so it has")):
            assert d[k] != k, f"still English in German: {k[:60]}"


def test_the_preflight_names_the_bars_own_german_labels():
    """B-M8: "sobald der Durchgangstyp „Prüfung“ ist" where the bar reads
    "Lauftyp: Verifizierung". MUTATION: the old wording back in de.json."""
    d = _de()
    assert not any("Durchgangstyp" in v for v in d.values())
    key = next(k for k in d if k.startswith(
        "Some of the metrics listed above can be met in only one way"))
    assert f"Lauftyp „{d['Verification']}“" in d[key]
    assert d["Run type:"].startswith("Lauftyp")


def test_the_worst_five_percent_is_plural_in_german():
    """B-L3: "das schlechteste 5 %"."""
    d = _de()
    assert not any("schlechteste 5" in v for v in d.values())
    assert sum("die schlechtesten 5 %" in v for v in d.values()) >= 2


def test_the_presets_column_heading_fits_in_german(qapp):
    """B-L3: "Beantwortete Metriken" was cut to "…Metriker" at 140 px.

    MUTATION (proved red): set the column width back to the fixed 140."""
    import core.i18n as i18n
    from ui.dialogs import preset_verification_dialog as PVD
    before = getattr(i18n, "current_language", lambda: "en")()
    try:
        i18n.set_language("de")
        dlg = PVD.PresetVerificationDialog([])
        try:
            head = dlg._tree.header()
            for c in (1, 2, 3):
                label = dlg._tree.headerItem().text(c)
                need = head.fontMetrics().horizontalAdvance(label)
                assert dlg._tree.columnWidth(c) > need + 12, (
                    c, label, dlg._tree.columnWidth(c), need)
        finally:
            dlg.close()
    finally:
        i18n.set_language(before)
