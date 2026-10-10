"""A verification whose profile was made after the sheet was printed: its
hover card says so (beta 11).

Such a sheet is compared with the chart's own estimate, not the profile's
prediction (``verify_expected``: the profile changed since printing), and its
card used the profiling wording, which ends "keep it for the profile". Knut
approved the red card's sentence in #182 5983480953 (lines 42 to 47 of
M-PATCH-COLOUR-RANGE); the "same value" and yellow lines are ours (48 to 51).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as mm             # noqa: E402
from workflow import verify_expected as ve                  # noqa: E402

PROFILING = ("this printer and paper cannot reach.",
             "A real difference this printer and",
             "paper cannot reach, not a misread.",
             "Keep it for the profile.",
             "it is real, keep it for the profile.")

LATER = [getattr(mm, n) for n in sorted(dir(mm))
         if n.startswith("_CARD_LATER_PROFILE_")]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _rows(info, source="estimate_profile_newer"):
    from ui.tiff_preview import _PatchInfoTile
    tile = _PatchInfoTile(None)
    base = {"loc": "D12", "exp_rgb": (90, 30, 200), "meas_rgb": (90, 80, 120),
            "exp_lab": (35, 60, -80), "meas_lab": (40, 20, -25), "de": 97.2,
            "warn": True, "warn_de": 95.0, "accurate": False}
    if source:
        base["expected_source"] = source
    base.update(info)
    tile.set_content(base, "both")
    return [t for _sw, t in tile._rows]


CASES = {
    "red": {"flag": ""},
    "re-read": {"flag": "confirmed", "prev_de": 97.0},
    "similar": {"flag": "confirmed", "peer_locs": ["E5", "F6"]},
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_the_card_never_says_the_profiling_phrases(qapp, case):
    rows = _rows(CASES[case])
    for phrase in PROFILING:
        assert phrase not in rows, (case, phrase)


def test_the_red_card_says_knuts_sentence(qapp):
    text = "\n".join(_rows(CASES["red"]))
    assert ("Far from the chart's estimate.\n"
            "The profile was made after this\n"
            "sheet was printed, so its\n"
            "prediction is not used.\n"
            "Either a misread, or a real difference:\n"
            "read it again to find out.\n\n"
            "Same value after a re-read:\n"
            "it is real: the print differs from\n"
            "the chart's estimate here.") in text
    # The approved sentence ends with its own "read it again".
    assert mm._CARD_RED_READ_AGAIN not in text.split("\n")
    # Judged at the limit for estimated colours, and named so (beta 17: the
    # patch error limit with its chart type).
    assert "(95.0, profiling charts with estimated\ncolours)." in text


@pytest.mark.parametrize("case", ["re-read", "similar"])
def test_the_yellow_card_says_a_real_difference_from_the_estimate(qapp, case):
    text = "\n".join(_rows(CASES[case]))
    assert ("A real difference from the chart's\n"
            "estimate, not a misread.\n\n"
            "No need to read it again.") in text


@pytest.mark.parametrize("case", sorted(CASES))
def test_every_other_card_is_unchanged(qapp, case):
    for source in (None, "prediction"):
        rows = _rows(CASES[case], source)
        assert not set(LATER) & set(rows), (case, source)


def test_the_two_profile_changed_fallbacks_mark_profile_newer(tmp_path):
    import test_k182_verify_expected_prediction as t
    then = (datetime.now() - timedelta(days=2)).isoformat(timespec="seconds")
    run, ti2, ti3, bin_dir = t._project(tmp_path / "raw", colour="raw",
                                        printed_at=then)
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=t._Tools(),
                          use_cache=False)
    assert not le.is_prediction and le.profile_newer
    run, ti2, ti3, bin_dir = t._project(tmp_path / "thr",
                                        colour="through-profile")
    os.utime(run.built_profile_icc(), None)
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir,
                          runner=t._Tools(sent=[(1, 1, 1)] * 8),
                          use_cache=False)
    assert not le.is_prediction and le.profile_newer
    # Any other fallback is not "made after the print".
    run, ti2, ti3, bin_dir = t._project(tmp_path / "none", record=False)
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=t._Tools(),
                          use_cache=False)
    assert not le.profile_newer


def test_the_tab_marks_the_card(qapp, tmp_path):
    import test_k182_verify_expected_prediction as t
    tab = t._tab(tmp_path)
    tab._live_expected = ve.estimate("x", profile_newer=True)
    tab._on_strip_measured(t._shifted_strip("A"))
    assert t._info(tab, "A2")["expected_source"] == "estimate_profile_newer"
    tab._live_expected = ve.estimate("x")
    tab._on_strip_measured(t._shifted_strip("A"))
    assert "expected_source" not in t._info(tab, "A2")


def test_the_lines_are_in_the_catalogue_short_and_translated():
    import json
    from pathlib import Path
    msg = mm.CATALOGUE["M-PATCH-COLOUR-RANGE"]
    assert len(LATER) == 10
    root = Path(__file__).resolve().parents[1] / "data" / "i18n"
    cats = [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(root.glob("*.json"))]
    assert len(cats) == 13
    for line in LATER:
        assert line in msg.body.split("\n")
        assert len(line) <= 44 and "—" not in line
        for cat in cats:
            assert line in cat


def test_an_unreadable_print_date_is_not_called_a_later_profile(tmp_path):
    """Review of beta 11: a raw print whose date cannot be read falls back to
    the estimate, but nothing shows the profile was made after it, so the
    card must not say so."""
    import test_k182_verify_expected_prediction as t
    run, ti2, ti3, bin_dir = t._project(tmp_path / "raw", colour="raw",
                                        printed_at="not a date")
    le = ve.live_expected(ti2, ti3, run, bin_dir=bin_dir, runner=t._Tools(),
                          use_cache=False)
    assert not le.is_prediction and not le.profile_newer
