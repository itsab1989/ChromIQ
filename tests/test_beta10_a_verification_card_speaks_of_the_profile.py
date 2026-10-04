"""A verification judged against the profile's prediction: its hover card
speaks of the profile, never of what the printer cannot reach (beta 10).

Knut, #203 5982702169: on such a verification every colour is inside the
profile's gamut, so a large difference is a check of the profile's accuracy,
"not a highlighting of patches that the printer cannot reach". Proposed
wording in 5982715730, approved by Knut in 5982788316 (lines 32 to 41 of
M-PATCH-COLOUR-RANGE, whose other lines stay proposed). The profiling cards
are unchanged.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as mm             # noqa: E402

#: Every profiling phrase a verification card must not carry.
PROFILING = ("this printer and paper cannot reach.",
             "A real difference this printer and",
             "paper cannot reach, not a misread.",
             "Keep it for the profile.",
             "it is real, keep it for the profile.",
             "This one is off in the same way,")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _rows(info, verify):
    from ui.tiff_preview import _PatchInfoTile
    tile = _PatchInfoTile(None)
    base = {"loc": "D12", "exp_rgb": (90, 30, 200), "meas_rgb": (90, 80, 120),
            "exp_lab": (35, 60, -80), "meas_lab": (40, 20, -25), "de": 17.2,
            "warn": True, "warn_de": 15.0, "colour_range": "blue",
            "range_k": 3, "range_locs": ["A1", "B2", "C3"], "accurate": True}
    if verify:
        base["expected_source"] = "prediction"
    base.update(info)
    tile.set_content(base, "both")
    return [t for _sw, t in tile._rows]


CASES = {
    "red": {"flag": ""},
    "re-read": {"flag": "confirmed", "prev_de": 17.0},
    "similar": {"flag": "confirmed", "peer_locs": ["E5", "F6"]},
    "learned": {"flag": "learned", "like_loc": "A1", "landed": True},
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_verification_card_never_says_the_profiling_phrases(qapp, case):
    rows = _rows(CASES[case], verify=True)
    for phrase in PROFILING:
        assert phrase not in rows, (case, phrase)


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_profiling_card_is_unchanged(qapp, case):
    rows = _rows(CASES[case], verify=False)
    assert not any(r.startswith(("Far from what the profile",
                                 "A real difference, not a misread:",
                                 "The profile is off"))
                   for r in rows)


def test_the_red_verification_card_reads_as_proposed(qapp):
    text = "\n".join(_rows(CASES["red"], verify=True))
    assert ("Far from what the profile predicts.\n"
            "Either a misread, or a place where\n"
            "the profile is inaccurate.\n"
            "Read it again to find out.\n\n"
            "Same value after a re-read:\n"
            "it is real, and counts against\n"
            "the profile's accuracy.") in text


@pytest.mark.parametrize("case", ["re-read", "similar"])
def test_the_yellow_verification_card_reads_as_proposed(qapp, case):
    text = "\n".join(_rows(CASES[case], verify=True))
    assert ("A real difference, not a misread:\n"
            "the profile does not predict this\n"
            "colour well here (or the printer has\n"
            "changed since the profile was made).\n\n"
            "No need to read it again.") in text


def test_the_learned_verification_card_says_the_profile_is_off(qapp):
    rows = _rows(CASES["learned"], verify=True)
    assert mm._CARD_VERIFY_LEARNED in rows
    assert mm._CARD_RANGE_LANDED_1 in rows


def test_the_tab_marks_a_card_judged_against_the_prediction():
    """The card decides on ``expected_source == "prediction"``, which
    TabMeasure sets from _expected_is_predicted()."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert 'extra["expected_source"] = "prediction"' in src


def test_the_lines_are_proposed_short_and_in_every_catalogue():
    import json
    from pathlib import Path
    msg = mm.CATALOGUE["M-PATCH-COLOUR-RANGE"]
    assert not msg.approved
    names = [n for n in dir(mm) if n.startswith("_CARD_VERIFY_")]
    assert len(names) == 10
    root = Path(__file__).resolve().parents[1] / "data" / "i18n"
    for n in names:
        line = getattr(mm, n)
        assert line in msg.body.split("\n")
        assert len(line) <= 44 and "—" not in line
        for f in sorted(root.glob("*.json")):
            assert line in json.loads(f.read_text(encoding="utf-8")), (f.name, n)
