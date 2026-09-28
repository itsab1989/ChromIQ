"""B8-711 and B8-724: the one-page summary (T1) prints the column summary as
body text and has no row table and no note list under it, so no sentence on
it may point at either.

* B8-711: "the values not checked are listed below" (the ISO sentences).
  Knut ruled in K28 that the N-A reference numbers and their notes are what
  says what was left out, "This also applies to the one-page summary", so the
  page states the count without a list (`iso_partial_page`).
* B8-724: "The rows above say what is missing" (`nothing_checked`) and "The
  note below says why each was left ungraded" (`nothing_graded`). The page
  says the same without the pointer; the full report keeps it.

Every summary reason that reaches T1 is checked for a pointer, in English and
in every catalogue, so a new pointing sentence cannot slip onto the page.

MUTATION, proven red: take the two B8-724 entries out of the swap in
`MeasurementReportDialog._one_page_summary`.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow.compliance_sets import SUMMARY_REASONS, Summary, N_A, PASS

ROOT = Path(__file__).resolve().parent.parent
POINTERS = ("listed below", "rows above", "note below")


def _page(reason: str) -> str:
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    sm = Summary(N_A, 0, 9, 0, 0, 9, reason)
    return MeasurementReportDialog._one_page_summary(sm).reason


@pytest.mark.parametrize("key", ["nothing_checked", "nothing_graded",
                                 "iso_with_unchecked",
                                 "iso_with_one_unchecked"])
def test_no_sentence_on_the_page_points_at_a_part_it_lacks(key):
    said = _page(SUMMARY_REASONS[key])
    assert not any(p in said.lower() for p in POINTERS), (key, said)


@pytest.mark.parametrize("key", ["nothing_checked", "nothing_graded"])
def test_the_page_says_the_same_without_the_pointer(key):
    full = SUMMARY_REASONS[key]
    page = _page(full)
    assert page == SUMMARY_REASONS[key + "_page"]
    assert full.startswith(page), (
        "the page sentence must be the full one minus its pointer, not new "
        "wording")


def test_the_full_report_keeps_its_pointers():
    assert "rows above" in SUMMARY_REASONS["nothing_checked"]
    assert "note below" in SUMMARY_REASONS["nothing_graded"]


@pytest.mark.parametrize("path", sorted((ROOT / "data" / "i18n").glob("*.json")),
                         ids=lambda p: p.stem)
def test_every_language_has_the_page_sentences_as_its_own_first_sentence(path):
    cat = json.loads(path.read_text(encoding="utf-8"))
    if "@language_name" not in cat:
        pytest.skip("not a language catalogue")
    for key in ("nothing_checked", "nothing_graded"):
        full = cat.get(SUMMARY_REASONS[key])
        page = cat.get(SUMMARY_REASONS[key + "_page"])
        assert full and page, (path.stem, key)
        assert full.startswith(page), (path.stem, key, page)
        assert len(page) < len(full), (path.stem, key)
