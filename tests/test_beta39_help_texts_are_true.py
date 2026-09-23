"""The help texts beta 39 made false are gone, and the new ones say what the
app does (B8-910).

The audit behind this file is
``~/Desktop/ChromIQ-beta39-proof/remaining-questions/HELP-GAPS.md``: 15 help
sentences that were false at d2a587bb (12 made false by beta 39 itself, 3
older ones found on the way), 17 beta 39 behaviours no help text described,
and five more false sentences from the text re-challenge of beta 39
(``rechallenge-R2-text/REPORT.md``, findings 3, 4, 5, 6 and 11).

Two halves, both read from the English source strings, which are what every
language is translated from:

* **GONE**: a distinctive phrase of each false sentence, which must not be in
  any user-facing string any more. A phrase is taken from the sentence that
  was false, never from a word it shares with a true one.
* **SAID**: a key phrase of each new sentence, read from the place a reader
  opens (the help constant, the Dictionary entry, the file guide row, the
  help-icon text), so that removing the new sentence fails here and not only
  on screen.

The German of every new key is in ``data/i18n/de.json``; ``test_i18n.py``
holds it complete.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def english_keys() -> "set[str]":
    from scripts.i18n_extract import extract_keys
    return set(extract_keys())


@pytest.fixture(scope="module")
def german() -> dict:
    return json.loads((ROOT / "data" / "i18n" / "de.json").read_text(
        encoding="utf-8"))


#: (where it was, a distinctive phrase of the false sentence)
GONE = [
    ("Dictionary, Report type: ISO types greyed for the values",
     "because the figures they would judge against are published"),
    ("verify card, How to read the result words: INFO",
     "INFO when the set puts no limit on that row"),
    ("Dictionary, verdict words: INFO",
     "INFO means the set puts no limit on that row"),
    ("_PAIRING_HELP: the mid-tone ramp shown for information",
     "so that one is shown for information"),
    ("Report shown help: this run only",
     "Every report this run has generated"),
    ("Report shown help: an update renames",
     "An update renames the report to match its settings"),
    ("Show detailed data help: the run's limit set",
     "verdict words against the run's limit set"),
    ("window guide, Colour accuracy: the run's limit set",
     "judged against the run's limit set"),
    ("file guide, project reports row: beside the project folders",
     "is kept in a reports folder beside those project folders"),
    ("Save measurement report help: always the run's folder",
     "in the run's “reports” folder: how close"),
    ("verify card: a Printing record for a verification",
     "check, or a Printing record, which sets down"),
    ("window guide: i1Profiler export and convert",
     "Just two steps:"),
    ("Dictionary, Grey ramp: needed for tone",
     "before it will judge grey balance or tone"),
    ("window guide: two ways", "Two ways to use it"),
    ("verify card: both titles", "You can set both titles"),
    ("Dictionary, Report scope: dates only",
     "how much of the history it covers"),
    ("Delete help: the reports were not said to follow",
     "files inside the remaining runs are not renamed.\n"),
    # rechallenge R2
    ("Report limits: the button is below", "Reference values…” below."),
    ("Report limits Custom paragraph: the button is below",
     "below to supply its figures"),
    ("file guide: a shipped set reads ?",
     "ships no value for reads “?”"),
    ("Report limits legend and masthead: may not show",
     "does not hold or may not show"),
    ("Report limits sub-line: still being decided",
     "is still being decided"),
    ("Dictionary, brackets: ? in a document ChromIQ does not hold",
     "the number lives in a document ChromIQ does not hold"),
]


@pytest.mark.parametrize("where,phrase", GONE, ids=[w for w, _ in GONE])
def test_the_false_sentence_is_gone(english_keys, where, phrase):
    hits = [k for k in english_keys if phrase in k]
    assert not hits, f"{where}: still says {phrase!r} in {hits[0][:120]!r}"


@pytest.mark.parametrize("where,phrase", GONE, ids=[w for w, _ in GONE])
def test_the_false_sentence_is_gone_in_german_too(german, where, phrase):
    """A stale German entry would keep the false sentence alive on a German
    machine; the key itself must not be in the catalogue."""
    hits = [k for k in german if phrase in k]
    assert not hits, f"{where}: de.json still keys {hits[0][:120]!r}"


def _glossary(title_start: str) -> str:
    from ui.dialogs.welcome_dialog import GLOSSARY
    hits = [body for title, body in GLOSSARY if title.startswith(title_start)]
    assert len(hits) == 1, title_start
    return hits[0]


def test_the_iso_report_types_are_greyed_for_the_documents():
    body = _glossary("Report type")
    assert "ship with ChromIQ as two read-only limit sets" in body
    assert "not built yet" in body


def test_info_is_the_word_of_an_ungraded_sheet_and_a_dash_row_leaves():
    body = _glossary("PASS, FAIL, COND, INFO, N-A")
    assert "is left out of the report altogether" in body
    assert "raw drift check" in body


def test_the_pairing_help_leaves_the_ramp_out_and_names_the_iso_sets():
    from ui.dialogs.measurement_report_dialog import _PAIRING_HELP
    assert "so that row is left out of the report" in _PAIRING_HELP
    assert "The read-only ISO 12647-8 set and both Custom ISO sets judge all three" in _PAIRING_HELP


def test_the_pairing_help_matches_the_shipped_ramp_limits():
    """What the sentence says of each set is measured, not asserted: the
    ramp row carries a number exactly where the help says it does."""
    from workflow.compliance_sets import effective_limits, shipped_iso_sets
    if set(shipped_iso_sets()) != {"iso_12647_7", "iso_12647_8"}:
        pytest.skip("the sentence describes the build that ships both sets")
    ramp = "ramps_30_70_dl_max"
    has = {sid: effective_limits(sid, {})[ramp].is_numeric
           for sid in ("chromiq_default", "chromiq_tight", "chromiq_quick",
                       "iso_12647_7", "iso_12647_8",
                       "custom_iso_12647_7", "custom_iso_12647_8")}
    assert has == {"chromiq_default": False, "chromiq_tight": False,
                   "chromiq_quick": False, "iso_12647_7": False,
                   "iso_12647_8": True, "custom_iso_12647_7": True,
                   "custom_iso_12647_8": True}


def test_the_chart_help_says_the_grey_steps_are_evenly_spaced():
    from ui.dialogs.measurement_report_dialog import _CHART_HELP
    assert "roughly evenly spaced grey steps" in _CHART_HELP
    assert "the two read-only ones and the two Custom ones" in _CHART_HELP
    body = _glossary("Grey ramp")
    assert "roughly evenly spaced" in body
    assert "The tone row needs less" in body


def test_the_report_scope_entry_names_every_tag():
    body = _glossary("Report scope")
    for tag in ("One date", "Multiple runs", "Cal ", "Multiple cals",
                "All cals", "an update that covers the same measurements"):
        assert tag in body, tag


def test_bound_and_report_limits_entries_say_what_a_report_across_places_does():
    assert "binds no run" in _glossary("Bound (a run's limits)")
    assert "its first column is “This report”" in _glossary(
        "Report limits (window)")


def test_a_rename_and_a_run_delete_say_the_reports_follow(english_keys):
    assert "Saved measurement reports that name the project follow the " \
           "new name" in _glossary("Printer profile project name")
    assert any("the saved measurement reports that name runs follow the new "
               "numbers" in k for k in english_keys)
    assert any("Saved measurement reports that name the profile follow the "
               "new name" in k for k in english_keys)


@pytest.mark.parametrize("phrase", [
    # the window guide
    "  • Calibration: with Run type Calibration, the window opens on",
    "is judged against its own set instead",
    "directly with “Add Profile's Measurements…”",
    # Report shown
    "Every report generated for the measurements in the list",
    "changes only when the update covers different measurements",
    "An update never leaves a measurement out behind your back",
    # Judged against
    "the choice here is the report's own",
    # Saving and finding the report
    "A calibration (Run type Calibration): the project's cal/reports folder",
    "otherwise the reports folder of your ChromIQ folder",
    # the list tooltip
    "and ticking it brings it straight back",
    # Show detailed data
    "a Printing record judges nothing, so its table has none",
    # the Measure tab
    "and the project's cal/reports with Run type Calibration",
    "With Run type Calibration it opens on the project's calibration",
    # the Calibrate card
    "“Multiple cals” or “All cals” when calibrations of several projects",
    # the verify card
    "is not offered for a verification",
    "the published values of ISO 12647-7 and ISO 12647-8 as two read-only sets",
    "across every measurement ticked in it",
    "those of the profiling and calibration reports",
    # Report limits
    "the first column is “This report”: the report's own limits",
    "“Reference values…” at the top of this window",
    "? means the set limits that row but no number has been supplied",
    # file guide
    "A CALIBRATION goes in cal/reports/",
    "or in your ChromIQ folder's when they are not side by side",
    "a row that standard puts no limit on reads “–”",
    # Preferences
    "and the project's cal/reports for a calibration",
    "(with verdict words wherever the report judges; a Printing record has none)",
])
def test_the_new_help_says_it(english_keys, german, phrase):
    hits = [k for k in english_keys if phrase in k]
    assert hits, f"no help text says {phrase!r}"
    for k in hits:
        assert german.get(k) and german[k] != k, f"untranslated: {k[:80]!r}"


def test_the_list_tooltip_carries_the_chromiq_folder_rule():
    """Knut named the list's own tooltip for this rule (B8-854)."""
    import inspect

    from ui.dialogs import measurement_report_dialog as mrd
    src = inspect.getsource(mrd.MeasurementReportDialog)
    at = src.index("self._list_tooltip = tr(")
    assert "_report_across_projects_help()" in src[at:at + 900]


def test_the_calibration_reports_old_folder_is_in_the_tree():
    from ui import file_guide
    import inspect
    src = inspect.getsource(file_guide)
    at = src.index("The measurement reports of this project's calibration, made")
    assert '(3, "old/"' in src[at:at + 400]
