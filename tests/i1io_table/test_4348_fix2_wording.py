"""Safety review 448, NOTE (text): what the 4.3.48 texts say is what is true.

* The homing after a stop sends i1Profiler's end-of-job lines (plus one reading), but i1Profiler
  sent them mid-job with the hand-alignment mode on: not "exactly" the way it ends a job.
* No reading precedes either recorded start-up (i0), so the start-up is "never recorded with the
  arm out over the table", not "recorded only with the arm at its resting place".
* German: "hat ChromIQ den Arm ... gelesen" was literal; it says where the arm stands.
"""
from __future__ import annotations

import json
from pathlib import Path

from workflow import measurement_messages as M

ROOT = Path(__file__).resolve().parents[2]


def test_the_homing_after_a_stop_does_not_say_exactly():
    body = M.M_I1IO_DRIVE_HOME_AFTER_STOP.body
    # 4.3.52: short, and it promises nothing about recordings or places
    assert "exactly" not in body and "record" not in body and "i1Profiler" not in body
    assert "ChromIQ can bring it home: press Bring the arm home." in body


def test_the_start_up_sentence_says_never_recorded_with_the_arm_out():
    src = (ROOT / "ui/i1io_table_window.py").read_text(encoding="utf-8")
    assert "recorded only with the arm at its resting place" not in src
    assert "never been recorded with the arm out over the table" in src


def test_the_german_place_check_page_says_where_the_arm_stands():
    """4.3.52: the sentence before the page is gone (the page itself says it, shorter); the
    German page names the arm's place as the table reports it."""
    from workflow import measurement_messages as M
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    assert "Right before its usual homing" not in (ROOT / "ui/i1io_table_window.py").read_text(
        encoding="utf-8")
    assert de[M.M_I1IO_DRIVE_HOME_AFTER_STOP.body].startswith(
        "Der Arm steht nicht an seinem Ruheplatz. Der Tisch meldet ihn bei {where}.")


def test_the_no_offer_sentence_names_the_condition_of_must_1():
    """The page after a stop without the offer lists the conditions; after MUST-1 it must name
    the case MUST-1 is about (the arm found out right after a movement of the table), or a stop
    after ChromIQ's own homing would read as one of those. 4.3.52: no place in it any more."""
    src = (ROOT / "ui/i1io_table_window.py").read_text(encoding="utf-8")
    assert '"which the table answered every line as recorded, the "' in src
    assert '"motors hold the arm, and the arm was not found away from where a "' in src
    assert "a place where a recorded homing starts" not in src
