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


def _step5(text):
    return [ln for ln in text.split("\n") if ln.startswith("5.")][0]


def test_step_5_switches_the_table_on_before_i1profiler_in_english():
    s5 = _step5(M.M_I1IO_DRIVE_ARM_WAY_OUT.body)
    assert s5.index("switch the table on") < s5.index("open i1Profiler")


@pytest.mark.parametrize("code", LANGS)
def test_step_5_switches_the_table_on_before_i1profiler(code):
    d = json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))
    s5 = _step5(d[M.M_I1IO_DRIVE_ARM_WAY_OUT.body])
    assert SWITCH_ON[code] in s5, s5
    assert s5.index(SWITCH_ON[code]) < s5.rindex("i1Profiler 3.8.7"), s5
