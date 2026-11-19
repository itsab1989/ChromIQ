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
    assert "sends it home the way i1Profiler ends a job" in body
    assert "exactly" not in body


def test_the_start_up_sentence_says_never_recorded_with_the_arm_out():
    src = (ROOT / "ui/i1io_table_window.py").read_text(encoding="utf-8")
    assert "recorded only with the arm at its resting place" not in src
    assert "never been recorded with the arm out over the table" in src


def test_the_german_place_check_sentence_says_where_the_arm_stands():
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    key = ("Right before its usual homing, ChromIQ read the arm away from its resting place, out "
           "over the table, where it did not expect it.")
    assert de[key].startswith("Unmittelbar vor seiner üblichen Rückfahrt hat ChromIQ gelesen, "
                              "wo der Arm steht: nicht an seinem Ruheplatz, sondern draußen über "
                              "dem Tisch")


def test_the_no_offer_sentence_names_the_condition_of_must_1():
    """The page after a stop without the offer lists the conditions; after MUST-1 it must name
    'nothing had moved yet', or a stop after ChromIQ's own homing would read as one of those."""
    src = (ROOT / "ui/i1io_table_window.py").read_text(encoding="utf-8")
    assert '"which the table answered every line as recorded and "' in src
    assert '"nothing had moved yet in this measurement, and only from "' in src
