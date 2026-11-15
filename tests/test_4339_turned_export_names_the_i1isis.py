"""Combined review of 4.3.39, NIT: the turned i1Profiler export's reason for
an i1iSis chart said "laid out for the XRISIS", the internal code. It now
names the instrument as i1Profiler does: "i1iSis" or "i1iSis XL"."""
from __future__ import annotations

import json

import pytest


@pytest.mark.parametrize("model,name", [("", "i1iSis"), ("xl", "i1iSis XL")])
def test_the_reason_names_the_i1isis(tmp_path, model, name):
    from workflow.i1profiler_turned import plan_for
    ti2 = tmp_path / "c.ti2"
    ti2.write_text(
        "CTI2\n\nNUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 2\nBEGIN_DATA\n1 \"A1\" 0 0 0\n2 \"A2\" 100 100 100\n"
        "END_DATA\n", encoding="utf-8")
    (tmp_path / "c.channels.json").write_text(json.dumps({"layout": {
        "engine": "chromiq",
        "patches": [{"loc": "A1", "x": 0, "y": 0, "w": 10, "h": 10}],
        "strips": [{"x": 0, "y": 0, "w": 10, "h": 20}],
        "recipe": {"instrument": "XRISIS", "isis_model": model,
                   "spacer_on": False, "spacer_mode": "none"}}}),
        encoding="utf-8")
    reasons = " ".join(plan_for(ti2).reasons)
    assert "XRISIS" not in reasons
    assert f"laid out for the {name}, not for" in reasons
