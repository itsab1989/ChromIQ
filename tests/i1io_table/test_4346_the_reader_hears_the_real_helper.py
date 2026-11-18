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


#: the dual scan on the table (2026-11-19): part_c_sim's FakeScanReader stands in for the
#: READER object (rd.ScanReader), not for the helper, and returns what the reader itself
#: returns when nothing came: ``{"event": "timeout"}`` (reader.py's own fallback of
#: dual_state / arm / lights_off; never a helper event). Allowed for that file only, and only
#: while reader.py really makes it itself (pinned below).
READER_MADE = {"part_c_sim.py": {"timeout"}}


def test_the_reader_makes_its_own_timeout_event():
    src = (ROOT / "workflow/i1io/table/reader.py").read_text(encoding="utf-8")
    assert 'or {"event": "timeout"}' in src
    assert "timeout" not in _helper_events()


@pytest.mark.parametrize("name", ["reader_sim.py", "part_c_sim.py", "window_sim.py"])
def test_the_simulated_helpers_send_only_what_the_real_helper_sends(name):
    src = (Path(__file__).parent / name).read_text(encoding="utf-8")
    sent = set(re.findall(r'"event":\s*"([a-z_]+)"', src))
    unknown = sorted(sent - _helper_events() - OWN_EVENTS - READER_MADE.get(name, set()))
    assert unknown == [], f"{name} sends events the real helper never sends: {unknown}"


# ---- review of 4.3.46: the rest of the app's code that reads helper events, and their FIELDS --
#: every file of the table drive that reads the helper's events itself (not only reader.py)
EVENT_READERS = ("workflow/i1io/table/reader.py", "workflow/i1io/table/job.py",
                 "workflow/i1io/table/scan.py", "workflow/i1io/table/strip.py",
                 "workflow/i1io/table/spot.py", "ui/i1io_table_window.py",
                 # the dual scan on the table (2026-11-19)
                 "workflow/i1io/table/dual_rows.py")


#: where a bare ``k`` / ``kind`` holds an event's name (elsewhere it is a row's or a result's
#: kind): reader.py, and spot.failure_id
NAME_VARS = ("workflow/i1io/table/reader.py", "workflow/i1io/table/spot.py")


def _names_in(rel: str) -> "set[str]":
    src = (ROOT / rel).read_text(encoding="utf-8")
    names = _compared_names(src)
    if rel == "workflow/i1io/table/spot.py":
        a = src.index("def failure_id(")
        names |= _compared_names(src[a:src.index("\ndef ", a + 1)], True)
    elif rel in NAME_VARS:
        names |= _compared_names(src, True)
    return names


def _compared_names(src: str, name_vars: bool = False) -> "set[str]":
    """Event names the code waits for or compares an event's name with: ``wait((...))`` and
    ``poll("...")`` (with any spacing), and ``<x>.get("event")`` / ``<x>["event"]`` (and, with
    *name_vars*, ``k`` / ``kind``) compared by ==, != or in (...), and ``"..." in names``."""
    names = _waited_names(src) if name_vars else set()
    for tup in re.findall(r'\.wait\(\s*\(([^)]*)\)', src):
        names |= set(re.findall(r'"([a-z_]+)"', tup))
    names |= set(re.findall(r'\.poll\(\s*"([a-z_]+)"', src))
    lhs = (r'(?:\w+\.get\("event"\)|\w+\["event"\]|\bk|\bkind)' if name_vars
           else r'(?:\w+\.get\("event"\)|\w+\["event"\])')
    names |= set(re.findall(lhs + r'\s*[!=]=\s*"([a-z_]+)"', src))
    for tup in re.findall(lhs + r'\s+(?:not\s+)?in\s+\(([^)]*)\)', src):
        names |= set(re.findall(r'"([a-z_]+)"', tup))
    names |= set(re.findall(r'"([a-z_]+)"\s+in\s+names\b', src))
    return names


def test_every_event_the_table_drive_compares_is_one_the_helper_can_send():
    known = _helper_events() | OWN_EVENTS
    for rel in EVENT_READERS:
        unknown = sorted(_names_in(rel) - known)
        assert unknown == [], f"{rel} looks for events the helper never sends: {unknown}"


def test_the_wider_name_check_sees_the_events_outside_the_reader():
    seen = set()
    for rel in EVENT_READERS:
        seen |= _names_in(rel)
    # scan.py (armed/lights-off/fired), job.py and the window (press), spot.py (error)
    assert {"tscan_armed", "tscan_lights_off", "tscan_fired", "press", "press_wait_ready",
            "error", "cal_required", "spot_ready"} <= seen, sorted(seen)


#: (event, field): every field of a helper event the table drive's code reads
FIELDS_READ = [
    ("spot_ready", "loc"), ("patch_read", "loc"), ("patch_read", "xyz"),
    ("cal_required", "cond"), ("cal_result", "result"), ("instrument", "model"),
    ("error", "kind"), ("error", "detail"), ("unread_confirm", "loc"),
    ("tscan_instrument", "model"), ("tscan_calibrated", "ok"), ("tscan_armed", "ready"),
    ("tscan_lights_off", "err"), ("tscan_fired", "ok"), ("tscan_fired", "got"),
    ("tscan_fired", "lit_sent"), ("tscan_fired", "ms_lit_trig"), ("tscan_fired", "rec_ev"),
    ("tscan_fired", "patches"), ("press", "id"), ("press_armed", "id"),
    ("press_wait_ready", "model"),
    # the dual scan on the table (2026-11-19): every field job.py / scan.py read of the dual
    # events (job._dual_strip_attempt, _calibrate, _row_attempt, _read_patch)
    ("tdual_state", "on"), ("tdual_state", "tile"), ("tdual_state", "why"),
    ("tdual_calibration", "ok"), ("tdual_calibration", "why"),
    ("dual_calibration", "ok"), ("dual_calibration", "why"),
    ("dual_pass_result", "ok"), ("dual_pass_result", "why"),
    ("tscan_dual_computed", "ok"), ("tscan_dual_computed", "why"),
    ("tscan_dual_computed", "pairing"), ("tscan_dual_computed", "n"),
    ("tscan_dual_computed", "usable"),
    ("tscan_fired", "dark_sent"), ("tscan_fired", "pass"), ("tscan_fired", "volts"),
]


def _emit_fields(event: str) -> "set[str]":
    """The field names in every C statement that emits *event* (from its name to the end of
    the statement)."""
    out: "set[str]" = set()
    for p in sorted(HELPER_SRC.glob("*.c")):
        src = p.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r'\\"event\\":\\"' + re.escape(event) + r'\\"', src):
            end = src.find(");", m.end())
            out |= set(re.findall(r'\\"([a-z_]+)\\":', src[m.end():end]))
        if event == "error":
            out |= {"kind", "detail"}         # cq_emit_error's own format (chromiq_json.c)
        if event == "tscan_fired" and p.name == "chromiq_tablescan.c":
            # a dual pass's fire: ts_dual_fire appends "pass" and "volts" (its own snprintf
            # into `extra`, handed to ts_emit_fired's final %s)
            a = src.find("static int ts_dual_fire(")
            if a >= 0:
                body = src[a:src.index("\n}\n", a)]
                for m in re.finditer(r"snprintf\(extra,", body):
                    end = body.find(");", m.end())
                    out |= set(re.findall(r'\\"([a-z_]+)\\":', body[m.end():end]))
    return out


@pytest.mark.parametrize("event,field", FIELDS_READ)
def test_every_field_the_table_drive_reads_is_one_the_helper_sends(event, field):
    assert field in _emit_fields(event), (
        f"the table drive reads {event}.{field}, which the helper never sends "
        f"(it sends {sorted(_emit_fields(event))})")


def test_every_error_kind_the_table_drive_names_is_one_the_helper_sends():
    from workflow.i1io.table import spot as sp
    kinds: "set[str]" = set()
    for p in sorted(HELPER_SRC.glob("*.c")):
        src = p.read_text(encoding="utf-8", errors="replace")
        kinds |= set(re.findall(r'cq_emit_error\("([a-z_]+)"', src))
        kinds |= set(re.findall(r'\\"kind\\":\\"([a-z_]+)\\"', src))
    named = set(sp.ERROR_KIND_IDS) | {"cal_failed"}       # reader.SpotReader.open's own
    assert sorted(named - kinds) == []


# ---- the app's SpotReader against the REAL committed helper (its replay instrument) ---------
# The fault of 4.3.45 was in the conversation between the app's reader and the real helper,
# which no test held together: the helper's own tests saw "cal_done" (test_engine_spot.py), the
# app's tests saw a simulator. These start rd.SpotReader on native/chromiq-chartread exactly
# as the job does (same arguments, same chart file), with only the USB edge scripted.

def _real_helper():
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "tests" / "helpers"))
    from replay_tools import HELPER  # noqa: E402
    if not HELPER.exists():
        pytest.skip("chromiq-chartread not built")
    return HELPER


def _real_reader(tmp_path, monkeypatch, calibrate: bool, needcal: bool, patches=3):
    helper = _real_helper()
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    if needcal:
        monkeypatch.setenv("CHROMIQ_REPLAY_NEEDCAL", "1")
    else:
        monkeypatch.delenv("CHROMIQ_REPLAY_NEEDCAL", raising=False)
    replay = tmp_path / "replay.txt"
    replay.write_text(f"PATCHES {patches}\nSTRIP A\n" + "50 50 50\n" * patches,
                      encoding="utf-8")
    log: "list" = []
    r = rd.SpotReader(helper, tmp_path / "reader", "row", [(str(i + 1), f"A{i + 1}")
                                                          for i in range(patches)],
                      lambda k, m: log.append((k, m)), calibrate,
                      extra_args=("--replay", str(replay), "-S"))
    return r, log


def test_the_real_helpers_session_calibration_counts_as_a_white(tmp_path, monkeypatch):
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=True, needcal=True, patches=1)
    asked = []
    try:
        r.open(lambda ev: asked.append(ev.get("cond")) or True, timeout=20)
        assert asked == ["man_ref_white"]
        assert r.calibrated is True       # 4.3.45: False, "calibration not confirmed"
        assert r.ready_loc == "A1"
        names = [e.get("event") for e in r.proc.events]
        assert "cal_done" in names and "cal_result" not in names, names
    finally:
        r.close()
    assert not r.proc.alive()


def test_a_reader_without_a_calibration_has_no_white_on_the_real_helper(tmp_path, monkeypatch):
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=False, needcal=False, patches=1)
    try:
        r.open(lambda ev: True, timeout=20)
        assert r.calibrated is False
        assert r.ready_loc == "A1"
    finally:
        r.close()


def test_a_refused_calibration_ends_the_real_reader(tmp_path, monkeypatch):
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=True, needcal=True, patches=1)
    try:
        with pytest.raises(rd.ReaderFailed, match="calibration was not done"):
            r.open(lambda ev: False, timeout=20)
        assert r.calibrated is False
    finally:
        r.close()
    assert not r.proc.alive()


def test_a_row_read_patch_by_patch_on_the_real_helper(tmp_path, monkeypatch):
    """open, read every patch, finish: the real helper's events (scan_started, patch_read, the
    autosave's saved, spot_ready, and done at the end) take the reader through a whole row."""
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=False, needcal=False, patches=3)
    r.open(lambda ev: True, timeout=20)
    got = [r.read(loc, timeout=10).xyz for loc in ("A1", "A2", "A3")]
    assert all(len(x) == 3 for x in got)
    ti3 = r.finish(timeout=10)
    assert ti3 is not None and ti3.is_file()
    assert not r.proc.alive()
    assert "done" in [e.get("event") for e in r.proc.events]


def test_a_patch_read_again_after_a_goto_on_the_real_helper(tmp_path, monkeypatch):
    """The job's second try of a patch: the reader is sent to the patch again by goto."""
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=False, needcal=False, patches=3)
    try:
        r.open(lambda ev: True, timeout=20)
        r.read("A1", timeout=10)
        r.ready_loc = None                 # as job._patch does before a second try
        again = r.read("A1", timeout=10)
        assert again.loc == "A1" and len(again.xyz) == 3
    finally:
        r.close()


# ---- the strip reader (rd.ScanReader) on the real helper's event sequence --------------------
# No test drove rd.ScanReader's own wait loops: the job tests replace the whole class
# (part_c_sim.FakeScanReader). The sequences are those of the volunteer's tester sessions of
# 17 Nov 2026 on the real table (names and the fields the reader reads; times replaced).

REAL_STRIP_WHITE = [
    {"event": "tscan_start", "t": 0, "build": "chromiq-chartread"},
    {"event": "tscan_instrument", "t": 1, "model": "X-Rite i1 Pro 2"},
    # the reader sends {"cmd": "tscan_calibrate"}
    {"event": "cal_required", "cond": "man_ref_white", "id": "0", "optional": False},
    # the reader answers {"cmd": "ok"}
    {"event": "cal_done"},
    {"event": "tscan_calibrated", "t": 8, "ok": True, "detail": ""},
]


def _scan_reader(tmp_path, monkeypatch, script):
    proc = type("P", (_ScriptedProc,), {"script": list(script)})
    monkeypatch.setattr(rd, "_Proc", proc)
    return rd.ScanReader(Path("chromiq-chartread"), tmp_path / "strip", lambda *a: None)


def test_the_real_strip_white_sequence_calibrates(tmp_path, monkeypatch):
    s = _scan_reader(tmp_path, monkeypatch, REAL_STRIP_WHITE)
    assert s.opened(timeout=1)["model"] == "X-Rite i1 Pro 2"
    asked = []
    s.calibrate(lambda ev: asked.append(ev["cond"]) or True, timeout=1)
    assert asked == ["man_ref_white"]
    assert s.proc.sent == [{"cmd": "tscan_calibrate"}, {"cmd": "ok"}]


def test_a_failed_strip_white_is_a_failure_not_a_wait(tmp_path, monkeypatch):
    # chromiq_cal.c: a failed calibration is {"event":"error","kind":"cal_failed"}, and the
    # helper then waits for a retry; tscan_calibrated does not come
    script = REAL_STRIP_WHITE[:3] + [{"event": "error", "kind": "cal_failed", "detail": "x"}]
    s = _scan_reader(tmp_path, monkeypatch, script)
    s.opened(timeout=1)
    with pytest.raises(rd.ReaderFailed, match="did not finish"):
        s.calibrate(lambda ev: True, timeout=1)


def test_the_strip_readers_arm_and_lights_off_read_the_helpers_own_fields(tmp_path, monkeypatch):
    # chromiq_tablescan.c: tscan_lights_off {"err":0}, tscan_armed {"ready":true}
    script = [REAL_STRIP_WHITE[1],
              {"event": "tscan_lights_off", "t": 2, "err": 0},
              {"event": "tscan_armed", "t": 3, "n": 520, "ready": True, "waited_ms": 0,
               "still_ms": 0, "why": ""}]
    s = _scan_reader(tmp_path, monkeypatch, script)
    s.opened(timeout=1)
    assert s.lights_off()["err"] == 0
    assert s.arm(520, 3000)["ready"] is True
    assert s.proc.sent == [{"cmd": "tscan_lights_off"},
                           {"cmd": "tscan_arm", "n": 520, "wait_ms": 3000}]


# ---- the job's calibration step itself, with the job's own reader on the real helper ---------

def test_the_jobs_calibration_step_succeeds_on_the_real_helper(tmp_path, monkeypatch):
    """The volunteer's two refusals of 18 Nov 2026, as a test: the job's C1 (reader consent,
    the place, the instrument's own calibration) with job._default_reader's SpotReader on the
    committed helper. Only the table is simulated; on 4.3.45 this ends 'calibration not
    confirmed'."""
    from tests.i1io_table.test_job_reading import job_for
    from workflow.i1io.table import job as J
    helper = _real_helper()
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    monkeypatch.setenv("CHROMIQ_REPLAY_NEEDCAL", "1")
    replay = tmp_path / "replay.txt"
    replay.write_text("PATCHES 1\nSTRIP A\n50 50 50\n", encoding="utf-8")
    monkeypatch.setattr(rd, "helper_path", lambda pkg=None: helper)
    job, sim, _h, _run, p = job_for(tmp_path)
    started = []

    def real(folder, name, patches, calibrate, extra_args, log):
        r = J._default_reader(folder, name, patches, calibrate,
                              ("--replay", str(replay), *extra_args), log)
        started.append(r)
        return r
    job._reader_factory = real
    assert p.drive(job.open()).ok
    r = p.drive(job.calibrate())
    assert r.ok, (r.reason, r.detail)
    assert job.calibration is not None and job.calibration["kind"] == "spot"
    assert len(started) == 1 and started[0].calibrated is True
    assert not started[0].proc.alive()
