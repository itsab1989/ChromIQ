"""4.3.46: the table's reader understands what the REAL helper says.

The first run of the in-app table drive on a real i1iO 2 with an i1Pro 2 (18 Nov 2026,
ChromIQ 4.3.45) ended twice at the calibration with the job's "calibration not confirmed"
refusal, although the instrument had calibrated: the helper ends the calibration a session
starts with by ``{"event":"cal_done"}`` (``native/chartread_helper/chromiq_cal.c``), and
``reader.SpotReader.open`` waited only for ``cal_result``, the event of a calibration the
person asks for. The simulated helper of the test suite sent ``cal_result`` too, so every
test passed.

These tests keep it that way round:

* the exact event sequence of that real session (event names and the fields the reader uses;
  nothing of the person or the instrument) opens a reader WITH a white;
* every event name the reader waits for is one the helper's C sources can emit;
* every event name the simulated helpers emit is one the helper's C sources can emit.
"""
from __future__ import annotations

import queue
import re
from pathlib import Path

import pytest

from workflow.i1io.table import reader as rd

ROOT = Path(__file__).resolve().parents[2]
HELPER_SRC = ROOT / "native" / "chartread_helper"

#: What the helper sent in the real session, in order, up to the first patch (the session log
#: of 18 Nov 2026: names and the fields the reader reads; ids and values replaced).
REAL_START = [
    {"event": "session_start", "chart": "c1_spot.ti2", "patches": 1},
    {"event": "instrument", "model": "X-Rite i1 Pro 2", "chart_model": "X-Rite i1 Pro 2"},
    {"event": "filter", "filter": "none"},
    {"event": "cal_required", "cond": "man_ref_white", "id": "0", "optional": False},
    # the reader answers {"cmd": "ok"} here
    {"event": "cal_done"},
    {"event": "spot_ready", "id": "1", "loc": "A1", "read": False, "all_done": False},
]


class _ScriptedProc:
    """Stands in for ``reader._Proc``: plays a list of events, records what is sent."""

    script: "list[dict]" = []

    def __init__(self, argv, log, cwd):
        self.argv = list(argv)
        self.sent: "list[dict]" = []
        self.q: "queue.Queue[dict]" = queue.Queue()
        self.events: "list[dict]" = []
        for ev in self.script:
            self.q.put(ev)

    def send(self, obj) -> None:
        self.sent.append(obj)

    def wait(self, names, timeout: float):
        while True:
            try:
                ev = self.q.get_nowait()
            except queue.Empty:
                return None
            self.events.append(ev)
            if ev.get("event") in names or ev.get("event") in ("helper_gone", "error"):
                return ev

    def poll(self, name):
        return None

    def close(self, *a, **k) -> None:
        pass


def _reader(tmp_path, monkeypatch, script):
    proc = type("P", (_ScriptedProc,), {"script": list(script)})
    monkeypatch.setattr(rd, "_Proc", proc)
    return rd.SpotReader(Path("chromiq-chartread"), tmp_path, "c1_spot", [("1", "A1")],
                         lambda *a: None, True)


def test_the_real_helpers_calibration_counts_as_a_white(tmp_path, monkeypatch):
    r = _reader(tmp_path, monkeypatch, REAL_START)
    asked = []
    r.open(lambda ev: asked.append(ev) or True)
    assert [e["cond"] for e in asked] == ["man_ref_white"]
    assert r.proc.sent == [{"cmd": "ok"}]
    assert r.calibrated is True          # on 4.3.45 this was False: "calibration not confirmed"
    assert r.ready_loc == "A1"


def test_a_calibration_the_person_asked_for_still_counts(tmp_path, monkeypatch):
    script = [REAL_START[1], REAL_START[3],
              {"event": "cal_result", "result": "done", "prompted": True}, REAL_START[5]]
    r = _reader(tmp_path, monkeypatch, script)
    r.open(lambda ev: True)
    assert r.calibrated is True


def test_a_reader_that_never_calibrated_has_no_white(tmp_path, monkeypatch):
    r = _reader(tmp_path, monkeypatch, [REAL_START[1], REAL_START[5]])
    r.open(lambda ev: True)
    assert r.calibrated is False


def test_the_helpers_failed_calibration_is_a_failed_calibration(tmp_path, monkeypatch):
    script = [REAL_START[1], REAL_START[3],
              {"event": "error", "kind": "cal_failed", "detail": "the white was not plausible"}]
    r = _reader(tmp_path, monkeypatch, script)
    with pytest.raises(rd.ReaderFailed) as exc:
        r.open(lambda ev: True)
    assert "calibration ended with" in str(exc.value)      # spot.py's "calibration_failed"


# ---- the names -----------------------------------------------------------------------------

def _helper_events() -> "set[str]":
    names: "set[str]" = set()
    for p in sorted(HELPER_SRC.glob("*.c")) + sorted(HELPER_SRC.glob("*.h")):
        src = p.read_text(encoding="utf-8", errors="replace")
        names |= set(re.findall(r'cq_emit_simple\("([a-z_]+)"\)', src))
        names |= set(re.findall(r'\\"event\\":\\"([a-z_]+)\\"', src))
    return names


#: not sent by the helper: made by the reader itself when the process ends
OWN_EVENTS = {"helper_gone"}


def test_the_helper_sources_are_read():
    ev = _helper_events()
    assert {"cal_done", "cal_required", "cal_result", "spot_ready", "patch_read",
            "tscan_calibrated", "press"} <= ev, sorted(ev)


def _waited_names(src: str) -> "set[str]":
    """The event names in the tuples handed to ``wait(...)`` / ``poll(...)`` and compared with
    ``ev.get("event")`` / ``ev["event"]`` / ``k`` in the reader."""
    names: "set[str]" = set()
    for tup in re.findall(r'\.wait\(\(([^)]*)\)', src):
        names |= set(re.findall(r'"([a-z_]+)"', tup))
    names |= set(re.findall(r'\.poll\("([a-z_]+)"\)', src))
    names |= set(re.findall(r'(?:ev\.get\("event"\)|ev\["event"\]|\bk)\s*==\s*"([a-z_]+)"', src))
    for tup in re.findall(r'(?:ev\.get\("event"\)|\bk)\s+in\s+\(([^)]*)\)', src):
        names |= set(re.findall(r'"([a-z_]+)"', tup))
    return names


def test_every_event_the_reader_waits_for_is_one_the_helper_can_send():
    src = (ROOT / "workflow/i1io/table/reader.py").read_text(encoding="utf-8")
    waited = _waited_names(src)
    assert {"cal_done", "spot_ready", "tscan_calibrated"} <= waited, sorted(waited)
    unknown = sorted(waited - _helper_events() - OWN_EVENTS)
    assert unknown == [], f"the reader waits for events the helper never sends: {unknown}"


@pytest.mark.parametrize("name", ["reader_sim.py", "part_c_sim.py", "window_sim.py"])
def test_the_simulated_helpers_send_only_what_the_real_helper_sends(name):
    src = (Path(__file__).parent / name).read_text(encoding="utf-8")
    sent = set(re.findall(r'"event":\s*"([a-z_]+)"', src))
    unknown = sorted(sent - _helper_events() - OWN_EVENTS)
    assert unknown == [], f"{name} sends events the real helper never sends: {unknown}"
