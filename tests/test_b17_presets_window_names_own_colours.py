"""Beta 17: "Which presets can be used for verification?" names its counts
(#182, Knut 6078432080, 6082015002 and 6085694445).

* The footer: "Answering every metric asked, own colours: n" beside the From
  Profile Gamut one (6085694445: "The 'Answering every metric asked: 0' is
  still not showing 'Own colours' in the label").
* The headings' tooltip begins with what the columns count and explains both
  ways of filling a chart, short (the k56 mock-up, approved).
* The help icon beside the line over the list carries the long explanation
  (6082015002: "short in tool-tip and longer in help icon").
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ui.dialogs import preset_verification_dialog as pv

ROOT = Path(__file__).resolve().parent.parent


def test_the_tooltip_begins_with_what_the_columns_count():
    t = pv.TWO_COUNTS_NOTE
    assert t.startswith("Report metrics this chart can answer, counted for "
                        "the two ways a chart can be filled with colours.")
    assert ("Own colours: the preset's own patch colours. For a verification "
            "the chart is printed through the profile; for profiling it is "
            "printed raw.") in t
    assert ("From Profile Gamut: the preset's layout filled with colours your "
            "profile can print (Create Chart ▸ FROM PROFILE GAMUT). For "
            "verification only.") in t
    assert t.endswith("More under ⓘ.")


def test_the_help_explains_both_uses_of_own_colours():
    h = pv.OWN_COLOURS_HELP
    for part in ("**What the two columns count:**", "**Own colours:**",
                 "**From Profile Gamut:**", "**Why the two counts differ:**",
                 "**Which count applies:**",
                 "(Print Chart ▸ Colour: “Through the profile”)",
                 "(Print Chart ▸ Colour: “Raw — no profile”)",
                 "(“Raw — already converted”)",
                 "this is one of the Verification charts",
                 "these are the Profiling charts with estimated colours"):
        assert part in h, part


def test_the_window_shows_it(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    from ui.tooltip_button import TooltipButton
    rows = verification_preset_rows(AppSettings())
    dlg = pv.PresetVerificationDialog(rows, None, None, background=True)
    try:
        from core.i18n import tr
        assert dlg._tree.headerItem().toolTip(3) == tr(pv.TWO_COUNTS_NOTE)
        assert dlg._tree.headerItem().toolTip(4) == tr(pv.TWO_COUNTS_NOTE)
        assert dlg._two_counts.toolTip() == tr(pv.TWO_COUNTS_NOTE)
        assert isinstance(dlg._own_colours_help, TooltipButton)
        dlg._fill_figures()
        text = dlg._figures.text()
        assert "Answering every metric asked, own colours: " in text
        assert "Answering every metric asked, From Profile Gamut: " in text
        assert "Answering every metric asked: " not in text
    finally:
        dlg.close()


@pytest.mark.parametrize("code", ["de", "es", "fr", "it", "ja", "nl", "no",
                                  "pl", "pt", "ru", "sv", "uk", "zh_CN"])
def test_every_language_names_own_colours_in_the_footer(code):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text(
        encoding="utf-8"))
    key = ("Presets listed: {listed}     Made for verification: {starred}     "
           "Answering every metric asked, own colours: {complete}")
    own = cat["Own colours"].lower()
    assert own in cat[key].lower(), code
    assert cat[pv.TWO_COUNTS_NOTE] and cat[pv.OWN_COLOURS_HELP]
