"""Two is "both", never "All 2" (4.3.11, Basti; CLAUDE.md's count rule).

The re-read window said "All 2 chart strips have been re-measured
successfully." Every counted "all {n}" text that can meet n = 2 now has an
explicit "both" sentence, in English and in all 13 catalogues; one and many
are unchanged.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

BOTH_KEYS = [
    "<b>Both chart strips have been re-measured successfully.</b>",
    "<b>Both patches have been re-measured successfully.</b>",
    "Delete both verifications",
    "Delete this run's whole verification folder: the verification chart and both results",
    "•  both verification results:",
    "Re-measure both strips above your limit",
    "[Guided Refinement] Both patches above the limit have been read again.",
    "[OK] This measurement carries no device values, so ChromIQ paired it "
    "with {chart} by patch name and took the device values of both patches "
    "from the chart.",
]
LANGS = sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json"))


def test_the_opening_line_counts_one_two_and_many():
    from ui.tabs.tab_measure import remeasured_opening as o
    assert o(1) == "<b>The chart strip has been re-measured successfully.</b>"
    assert o(2) == "<b>Both chart strips have been re-measured successfully.</b>"
    assert o(3) == "<b>All 3 chart strips have been re-measured successfully.</b>"
    assert o(5, 1) == "<b>The patch has been re-measured successfully.</b>"
    assert o(5, 2) == "<b>Both patches have been re-measured successfully.</b>"
    assert o(1, 7) == "<b>All 7 patches have been re-measured successfully.</b>"


def test_both_windows_take_the_line_from_the_one_helper():
    src = (ROOT / "ui" / "tabs" / "tab_measure.py").read_text(encoding="utf-8")
    assert src.count("remeasured_opening(len(self._strip_list)") == 2
    # the old inline form, which had only one and many, is gone
    assert src.count('tr("<b>All {n} chart strips have been re-measured') == 1


def test_the_delete_texts_say_both_for_two(tmp_path):
    from core import run_delete as rd
    plan = rd.DeletePlan.__new__(rd.DeletePlan)
    plan.kind = rd.KIND_VERIFY_ALL
    plan.run_id = "run1"
    plan.verification_ids = ["2026-07-14_090211", "2026-07-21_114035"]
    assert rd.tooltip_for(plan).endswith("the verification chart and both results")
    plan.verification_ids.append("2026-07-28_101010")
    assert "all 3 results" in rd.tooltip_for(plan)


def test_the_choice_of_two_strips_says_both():
    from workflow import measurement_messages as mm
    assert mm._CR_CHOICE_BOTH in mm.M_CR_STRIPS.body
    src = (ROOT / "workflow" / "refine_plan.py").read_text(encoding="utf-8")
    assert "_CR_CHOICE_BOTH" in src


def test_the_preset_noise_text_says_both_pages():
    from ui.dialogs.preset_verification_dialog import _noise_count_body as b
    two = b(have=40, need=60, pages=2, low=40, high=40, total=2)
    assert "both pages" in two and "all 2" not in two
    assert "all 3 pages" in b(have=40, need=60, pages=3, low=40, high=40,
                              total=3)
    spread = b(have=40, need=60, pages=2, low=30, high=50, total=2)
    assert "both pages" in spread and "all 2" not in spread


@pytest.mark.parametrize("lang", LANGS)
def test_every_catalogue_has_the_both_sentences(lang):
    cat = json.loads((ROOT / "data" / "i18n" / f"{lang}.json")
                     .read_text(encoding="utf-8"))
    for k in BOTH_KEYS:
        assert cat.get(k), f"{lang}: no translation of {k!r}"
        assert "{n}" not in cat[k] and "{c}" not in cat[k], (lang, k)
        assert "—" not in cat[k], (lang, k)


@pytest.mark.parametrize("lang", ["ru", "uk"])
def test_three_or_four_strips_read_right_in_russian_and_ukrainian(lang):
    """"Все 3 полос" / "Усі 3 смуг" is the genitive plural that only fits 5
    and more; the count now sits in brackets, as the patch line already did."""
    cat = json.loads((ROOT / "data" / "i18n" / f"{lang}.json")
                     .read_text(encoding="utf-8"))
    t = cat["<b>All {n} chart strips have been re-measured successfully.</b>"]
    assert "({n})" in t
    assert not re.search(r"\{n\} (полос|смуг)", t)
