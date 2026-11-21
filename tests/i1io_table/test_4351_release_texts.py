"""4.3.51 release (the re-review's S3 and S4): two table texts that must be possible to follow
and true.

S3: the way out (M-I1IO-DRIVE-ARM-WAY-OUT) switches the table off in step 2; its step 5 sends
the person to i1Profiler, which can only find a table that is switched on, so step 5 says to
switch it on first, in every language.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import measurement_messages as M

I18N = Path(__file__).resolve().parents[2] / "data" / "i18n"
LANGS = sorted(p.stem for p in I18N.glob("*.json"))
#: "switch the table on" in each language, as step 4 of the same page says it
SWITCH_ON = {"de": "Schalte den Tisch ein", "es": "enciende la mesa", "fr": "allume la table",
             "it": "accendi il tavolo", "ja": "テーブルの電源を入れて", "nl": "zet de tafel aan",
             "no": "slå på bordet", "pl": "włącz stół", "pt": "ligue a mesa",
             "ru": "включите стол", "sv": "slå på bordet", "uk": "увімкніть стіл",
             "zh_CN": "先打开扫描台"}


def test_step_5_switches_the_table_on_before_i1profiler_in_english():
    """2026-11-21 (the owner: "driving the table should work without involving i1profiler"):
    the way out has no i1Profiler step any more; START MEASUREMENT brings the arm home and the
    power switch with the table's start-up is the step after it."""
    body = M.M_I1IO_DRIVE_ARM_WAY_OUT.body
    assert "i1Profiler" not in body
    assert body.index("START MEASUREMENT") < body.index("power switch")


@pytest.mark.parametrize("code", LANGS)
def test_step_5_switches_the_table_on_before_i1profiler(code):
    d = json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))
    body = d[M.M_I1IO_DRIVE_ARM_WAY_OUT.body]
    assert "i1Profiler" not in body, code
    if code == "de":
        assert "MESSUNG STARTEN" in body and "Netzschalter" in body


# S4 (the START page inside 4.3.48's envelope said only what the recordings from there show) is
# moot since 4.3.52: the START pages that talked about recordings are withdrawn; the one START
# page (M-I1IO-DRIVE-HOME-AT-START) names no recording, no place and no distance
# (test_4352_start_rule_by_state.test_the_window_shows_one_short_page_and_goes_on).
