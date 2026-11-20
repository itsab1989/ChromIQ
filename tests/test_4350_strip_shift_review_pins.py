"""4.3.50 integration: the re-review of the strip shift check (2026-11-20).

S3: two choices no test pinned (fault planting left them green):
* the finder is given the chart's DESIGN colours (``raw``), never the verification
  prediction the older rules judge with: its limits were measured on design colours;
* the other-row guard compares a reading with every other row BOTH ways round.
S1, S2 and the switch: the four questions give no opposite advice in one window, say only what
the score measured, and name the option that switches them off as Preferences shows it.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from workflow import measurement_messages as M

I18N = Path(__file__).resolve().parents[1] / "data" / "i18n"
SHIFT = (M.M_STRIP_ENDS_SHIFTED_LATE, M.M_STRIP_ENDS_SHIFTED_EARLY,
         M.M_STRIP_END_PAPER_LATE, M.M_STRIP_END_PAPER_EARLY)
OPTION = "Warn me if a strip looks misaligned"


def test_the_other_row_guard_compares_both_ways_round():
    from workflow.strip_shift import other_rows_best
    row = [[20.0, 10.0, 5.0], [60.0, 70.0, 30.0], [30.0, 20.0, 60.0], [80.0, 85.0, 90.0]]
    assert other_rows_best(row, [row]) == pytest.approx(0.0, abs=1e-6)
    # the reading is the other row read back to front: only the reversed half finds it
    assert other_rows_best(list(reversed(row)), [row]) == pytest.approx(0.0, abs=1e-6)


def test_the_finder_is_given_the_charts_design_colours_not_the_prediction(monkeypatch):
    import workflow.slipped_strip as SS
    from workflow.measure_manager import MeasureManager
    seen = {}
    monkeypatch.setattr(SS, "slipped_run_in_strip_read", lambda patches: None)

    def finder(patches, paper, others):
        seen["patches"] = patches
        return None

    monkeypatch.setattr(SS, "shift_in_strip_read", finder)
    raw = [{"loc": "A1", "exyz": [1.0, 2.0, 3.0]}, {"loc": "A2", "exyz": [4.0, 5.0, 6.0]}]
    predicted = [{"loc": "A1", "exyz": [9.0, 9.0, 9.0]}, {"loc": "A2", "exyz": [9.0, 9.0, 9.0]}]
    fake = SimpleNamespace(_safenet_on=True, _expected_for_slip_check=lambda p: predicted,
                           _design_xyz_rows={}, _design_paper_xyz=[95.0, 100.0, 108.0])
    assert MeasureManager._check_part_of_strip_slipped(fake, {"strip": "A"}, raw) is None
    assert seen["patches"] is raw


def test_the_numbers_sentence_says_only_when_it_is_true():
    assert "by only" in M.shift_numbers_line(30.0, 12.0)
    assert M.shift_numbers_line(12.0, 12.0) == ""
    assert M.shift_numbers_line(12.0, 14.5) == ""
    assert M.shift_numbers_line(None, 3.0) == ""


@pytest.mark.parametrize("msg", SHIFT, ids=lambda m: m.id)
def test_one_window_gives_one_piece_of_advice(msg):
    body = msg.body
    assert "should be read again" not in body and "(recommended)" not in body
    assert "choose {keep}" in body
    assert OPTION in body and "Preferences ▸ Measurement" in body
    assert "—" not in body


@pytest.mark.parametrize("msg", SHIFT[:2], ids=lambda m: m.id)
def test_the_two_or_three_readings_are_said_to_fit_together(msg):
    assert msg.body.startswith("As a group")
    assert "{numbers_line}" in msg.body and "by only {best}" not in msg.body


@pytest.mark.parametrize("code", sorted(p.stem for p in I18N.glob("*.json")))
def test_every_language_names_the_option_as_preferences_shows_it(code):
    cat = json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))
    name = cat[OPTION]
    for msg in SHIFT:
        assert name in cat[msg.body], (code, msg.id)
