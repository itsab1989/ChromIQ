"""The kept dual tile not taken up by a table row's reader: the reason in the logs, and the
words on the table window (2026-11-24, the table owner's dual tries of 23 Nov).

Every dual row of those tries was refused with dual_calibration_not_kept although the
calibration had been made and kept: the helper's restore check used a clock a fresh process
does not know yet (fixed in native/instlib/cq_i1pro2_dual.h, proved on the fake USB layer in
test_dual_helper_wire.py). Two things the logs and the window got wrong are fixed here:

* the helper said nothing about WHY ("why":"" in tdual_state). It now gives a "restore" word
  and its values in tdual_state and in the -N reader's dual_calibration event, and the table
  reader writes them as one line in the session log and one in the app log;
* the row's page called that case "The instrument's calibration is about to run out" (it was
  not) and told the person to calibrate again, which led into a loop that could not succeed.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


class _Log:
    def __init__(self):
        self.lines = []

    def __call__(self, kind, text):
        self.lines.append((kind, text))


@pytest.mark.parametrize("ev, words", [
    ({"event": "tdual_state", "t": 1014, "on": True, "tile": "none", "why": "",
      "restore": "other_integration", "restore_detail": "kept lamp 136 / uv 136 clocks, now 140"},
     "not taken up (other_integration), kept lamp 136 / uv 136 clocks, now 140"),
    ({"event": "dual_calibration", "ok": False, "why": "no_dual_calibration", "mode": "spot",
      "lamp_clocks": 0, "uv_clocks": 0, "volts": [-1, -1], "driver": 0,
      "restore": "no_file", "restore_detail": "no dual calibration was kept for this mode"},
     "not taken up (no_file), no dual calibration was kept for this mode"),
    ({"event": "tdual_state", "t": 1014, "on": True, "tile": "kept", "why": "",
      "restore": "kept", "restore_detail": "lamp 136 / uv 136 clocks"},
     "taken up, lamp 136 / uv 136 clocks"),
    # safety review 2026-11-24: the file matched, but the tile failed its own check afterwards
    ({"event": "tdual_state", "t": 1014, "on": True, "tile": "none", "why": "uv_tile_dark",
      "restore": "kept", "restore_detail": "lamp 136 / uv 136 clocks"},
     "found, but not usable: uv_tile_dark, lamp 136 / uv 136 clocks"),
    ({"event": "dual_calibration", "ok": False, "why": "bad_uv_tables", "mode": "spot",
      "lamp_clocks": 523, "uv_clocks": 523, "volts": [-1, -1], "driver": 0,
      "restore": "kept", "restore_detail": "lamp 523 / uv 523 clocks"},
     "found, but not usable: bad_uv_tables, lamp 523 / uv 523 clocks"),
])
def test_the_reason_is_one_line_in_the_session_log_and_the_app_log(caplog, ev, words):
    from workflow.i1io.table.reader import _Proc
    proc = object.__new__(_Proc)
    proc.log = _Log()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        proc._dual_restore(ev)
    (kind, text), = proc.log.lines
    assert kind == "DATA" and text == "dual calibration kept for this white: " + words
    app = [r.getMessage() for r in caplog.records
           if r.getMessage().startswith("i1pro2 dual tile:")]
    assert len(app) == 1 and "where=table" in app[0]
    usable = ev["ok"] if ev["event"] == "dual_calibration" else ev["tile"] == "kept"
    if ev["restore"] == "kept" and not usable:
        # never "taken up" when the tile could not be used
        assert "taken up" not in text and "restore=kept_not_usable" in app[0]
        assert ev["why"] in app[0]
    else:
        assert f"restore={ev['restore']}" in app[0]


def test_the_reader_logs_the_reason_for_both_events_and_only_when_the_helper_gives_one():
    src = (ROOT / "workflow" / "i1io" / "table" / "reader.py").read_text(encoding="utf-8")
    assert ('elif ev.get("event") in ("tdual_state", "dual_calibration") and ev.get("restore"):'
            in src)


def test_both_helper_events_carry_the_reason():
    for name, event in (("chromiq_tablescan.c", "tdual_state"),
                        ("chromiq_dualdev.c", "dual_calibration")):
        src = (ROOT / "native" / "chartread_helper" / name).read_text(encoding="utf-8")
        i = src.index("i1pro2_cq_dual_tile_restore_why(&rdet)")
        block = src[i:i + 900]
        assert f'\\"event\\":\\"{event}\\"' in block
        assert '\\"restore\\":\\"%s\\",\\"restore_detail\\":\\"%s\\"' in block
        assert "cq_json_escape(rdet_esc" in block


def test_the_row_page_no_longer_sends_the_person_round_in_a_loop(qapp):
    from ui.i1io_table_window import reason_text
    t = reason_text("dual_calibration_not_kept")
    assert "was made" in t and "could not find it again" in t
    assert "Please calibrate again" not in t
    assert "calibrating once more will not help" in t and "Preferences > Beta" in t
    assert "app log" in t
    again = reason_text("dual_calibration_not_found_again")
    assert "about to run out" not in again and "could not find the calibration" in again
    for s in (t, again):
        assert "—" not in s


def test_reading_again_not_possible_names_the_real_reason():
    """M-I1IO-DRIVE-ROW-NOT-AGAIN: for dual_calibration_not_kept its own sentence, not the
    calibration_due one, in both the strip and the patch-by-patch page"""
    src = (ROOT / "ui" / "i1io_table_window.py").read_text(encoding="utf-8")
    block = ('why = (reason_text("dual_calibration_not_found_again")\n'
             '                       if d.get("why") == "dual_calibration_not_kept"\n'
             '                       else reason_text("calibration_due") if d.get("calibration_due")')
    assert src.count(block) == 2
