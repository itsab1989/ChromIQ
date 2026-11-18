"""4.3.46, fix round 2: the table drive's readers end the REAL helper the helper's own way.

The review of the first real-table run (REVIEW.md of 18 Nov 2026) compared the app's readers
with ``native/chartread_helper`` and found that they spoke to the helper as if it always sat at
its patch menu. Outside that menu (``chromiq_chartread.c``'s spot loop, ``chromiq_cal.c``) the
helper waits for ONE key, where Esc ends it and any other key carries on:

* ``SpotReader.close`` at a patch sent one Esc; the helper stops the reading
  ("strip_interrupted"), asks once more, and was killed 5.0 s later with the i1Pro 2 open
  (the calibration reader, every unfinished row; the volunteer's log shows the same);
* ``SpotReader.finish`` sent "done" at a calibration the instrument asked for in the middle
  of a row: there "done" is "any other key", so the i1Pro 2 CALIBRATED on the patch under it,
  then the reader waited 20 s and killed it (25 s);
* after a failed reading the helper waits at "Hit Esc or 'q' to give up, any other key to
  retry" and drops a goto: the job's second try of a patch ended "did not go to patch" every
  time on the real helper (the simulator kept the helper at the patch);
* ``ScanReader.close`` sent "tscan_quit" while the helper waited inside its calibration (a
  request not answered, a failed strip white): tscan_* lines go to the table-scan queue, which
  it reads only after the calibration; 5 s, then the kill.

The spot tests run the app's ``SpotReader`` on the committed helper with its replay instrument
(same arguments and chart file as the job). The table-scan mode opens no replay instrument, so
``ScanReader`` runs against a model of the helper's two input channels, pinned to the C source.
"""
from __future__ import annotations

import queue
import re
import time
from pathlib import Path

import pytest

from tests.i1io_table.test_4346_the_reader_hears_the_real_helper import (
    HELPER_SRC, ROOT, _real_reader)
from workflow.i1io.table import reader as rd

pytestmark = pytest.mark.timeout(120)

#: a clean ending of the replay helper takes a few hundredths of a second (measured 0.02 to
#: 0.06 s); the kill this replaces came at 5.0 s
QUICK_S = 3.0


def _timed(fn):
    t0 = time.monotonic()
    out = fn()
    return out, time.monotonic() - t0


def _ended_by_itself(r) -> None:
    assert not r.proc.alive()
    # the process's own exit, not the reader's kill (-9)
    assert r.proc.p.returncode == 0, r.proc.p.returncode


def _names(r) -> "list[str]":
    return [e.get("event") for e in r.proc.events]


# ---- close() -------------------------------------------------------------------------------

def test_the_calibration_reader_at_its_first_patch_ends_by_itself(tmp_path, monkeypatch):
    """The job's calibration step: the white is made, the reader sits at its first patch and
    is closed (job._calibrate). 4.3.45: 5.0 s, then killed."""
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=True, needcal=True, patches=1)
    r.open(lambda ev: True, timeout=20)
    assert r.calibrated is True
    _none, took = _timed(r.close)
    _ended_by_itself(r)
    assert took < QUICK_S, took
    assert _names(r)[-1] == "strip_interrupted"        # the helper's own second question


def test_a_row_reader_closed_after_a_reading_ends_by_itself_and_keeps_it(tmp_path, monkeypatch):
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=False, needcal=False, patches=3)
    r.open(lambda ev: True, timeout=20)
    r.read("A1", timeout=10)
    _none, took = _timed(r.close)
    _ended_by_itself(r)
    assert took < QUICK_S, took
    # what it saved after the reading is its .ti3 (it saves after every reading)
    _wl, data = rd.read_ti3_spectra(r.base.with_suffix(".ti3"))
    assert sorted(data) == ["A1"]


def test_an_unanswered_calibration_request_still_ends_at_once(tmp_path, monkeypatch):
    """The place refused (the reader raised before answering): one Esc ends it, as before."""
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=True, needcal=True, patches=1)
    with pytest.raises(rd.ReaderFailed):
        r.open(lambda ev: False, timeout=20)
    _none, took = _timed(r.close)
    _ended_by_itself(r)
    assert took < QUICK_S, took
    assert "cal_done" not in _names(r)                  # nothing was calibrated


# ---- finish() at the helper's own prompts ----------------------------------------------------

def _row_with_a_fault_at_a2(tmp_path, monkeypatch, fault, needcal=False):
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=False, needcal=needcal, patches=3)
    r.open(lambda ev: True, timeout=20)
    a1 = r.read("A1", timeout=10)
    r.proc.send({"cmd": "swipe", "fault": fault})      # the replay instrument's next answer
    with pytest.raises(rd.ReaderFailed):
        r.read("A2", timeout=10)
    return r, a1


def test_a_calibration_asked_for_in_a_row_is_never_made_on_the_patch(tmp_path, monkeypatch):
    """A -N reader whose instrument asks for a white in the middle of a row (the stored white
    expired, say): the row ends (job: instrument_asks_for_calibration) and the reader is
    finished. 4.3.45 sent "done" there, which the helper took as "the instrument is placed":
    cal_done, i.e. a white measured on the patch under the arm, then 25 s and a kill."""
    r, _a1 = _row_with_a_fault_at_a2(tmp_path, monkeypatch, "needs_cal", needcal=True)
    assert _names(r)[-1] == "cal_required"
    ti3, took = _timed(r.finish)
    names = _names(r)
    assert "cal_done" not in names[names.index("cal_required"):], names
    assert {"cmd": "done"} not in _sent(r)
    _ended_by_itself(r)
    assert took < QUICK_S, took
    # the reading made before it is kept, with its spectrum, in the reader's own .ti3
    assert ti3 is not None and r.readings["A1"].spectrum is not None
    assert sorted(rd.read_ti3_spectra(ti3)[1]) == ["A1"]


@pytest.mark.parametrize("fault", ["misread", "coms"])
def test_a_reader_finished_after_a_failed_reading_ends_by_itself(tmp_path, monkeypatch, fault):
    """4.3.45: "done" at "Hit Esc or 'q' to give up, any other key to retry" was a retry; the
    reader then waited 20 s for a save that never came and killed the helper."""
    r, _a1 = _row_with_a_fault_at_a2(tmp_path, monkeypatch, fault)
    ti3, took = _timed(r.finish)
    _ended_by_itself(r)
    assert took < QUICK_S, took
    assert ti3 is not None and sorted(rd.read_ti3_spectra(ti3)[1]) == ["A1"]


def test_a_finished_row_still_ends_with_the_helpers_own_save(tmp_path, monkeypatch):
    """At the patch menu nothing changes: "done" (and "yes" for unread patches), the helper's
    final save, its "done", and the process ends."""
    r, _log = _real_reader(tmp_path, monkeypatch, calibrate=False, needcal=False, patches=3)
    r.open(lambda ev: True, timeout=20)
    r.read("A1", timeout=10)
    ti3, took = _timed(r.finish)
    _ended_by_itself(r)
    assert took < QUICK_S
    assert _sent(r)[-2:] == [{"cmd": "done"}, {"cmd": "yes"}]
    assert _names(r)[-1] == "done"
    assert sorted(rd.read_ti3_spectra(ti3)[1]) == ["A1"]


def test_the_row_file_is_the_same_whichever_way_the_reader_ends(tmp_path, monkeypatch):
    """The quit chain keeps exactly what "done" would have saved: the helper's .ti3 after
    every reading is the same file (save_ti3 with the same data) as its final save."""
    files = []
    for how in ("finish", "close"):
        (tmp_path / how).mkdir()
        r, _log = _real_reader(tmp_path / how, monkeypatch, calibrate=False, needcal=False,
                               patches=3)
        r.open(lambda ev: True, timeout=20)
        r.read("A1", timeout=10)
        r.read("A2", timeout=10)
        getattr(r, how)()
        _ended_by_itself(r)
        text = r.base.with_suffix(".ti3").read_text(encoding="utf-8")
        files.append([ln for ln in text.splitlines() if not ln.startswith("CREATED")])
    assert files[0] == files[1]


# ---- the second try of a patch after a failed reading -----------------------------------------

@pytest.mark.parametrize("fault", ["misread", "coms"])
def test_a_patch_is_read_again_after_a_failed_reading(tmp_path, monkeypatch, fault):
    """job._patch's second try (ready_loc dropped, the reader sent to the patch again). On the
    real helper a goto at the failed reading's prompt is dropped: 4.3.45 waited 5 s and the row
    failed "reader_did_not_go_to_patch". The helper's own "retry" offers the patch again."""
    r, _a1 = _row_with_a_fault_at_a2(tmp_path, monkeypatch, fault)
    try:
        r.ready_loc = None                     # as job._patch does before a second try
        again = r.read("A2", timeout=10)
        assert again.loc == "A2" and len(again.xyz) == 3
        assert {"cmd": "retry"} in _sent(r)
        ti3 = r.finish(timeout=10)
        assert sorted(rd.read_ti3_spectra(ti3)[1]) == ["A1", "A2"]
    finally:
        r.close()


def test_retry_is_never_sent_at_a_calibration_request(tmp_path, monkeypatch):
    """Any key at a calibration request starts the calibration: the second try's "retry" is
    only for a failed READING. A reader asked for a patch there refuses instead."""
    r, _a1 = _row_with_a_fault_at_a2(tmp_path, monkeypatch, "needs_cal", needcal=True)
    try:
        r.ready_loc = None
        with pytest.raises(rd.ReaderFailed):
            r.read("A2", timeout=5)
        assert {"cmd": "retry"} not in _sent(r)
        assert "cal_done" not in _names(r)
    finally:
        r.close()
    _ended_by_itself(r)


def _sent(r) -> "list[dict]":
    """The commands the reader sent (its log lines "cmd {...}")."""
    import json
    return [json.loads(m[4:]) for _k, m in r._log_lines if m.startswith("cmd ")]


@pytest.fixture(autouse=True)
def _keep_the_log(monkeypatch):
    """Every reader built here keeps its log lines on itself (r._log_lines)."""
    real = rd.SpotReader.__init__

    def init(self, helper, workdir, name, patches, log, calibrate, extra_args=()):
        self._log_lines = []

        def both(k, m):
            self._log_lines.append((k, m))
            log(k, m)
        real(self, helper, workdir, name, patches, both, calibrate, extra_args)
    monkeypatch.setattr(rd.SpotReader, "__init__", init)


# ---- the table-scan reader -------------------------------------------------------------------

class _TableScanHelper:
    """The helper in --i1io-table-scan, as far as its INPUT goes (pinned to the C source by
    the tests below): "tscan_*" lines go to the table-scan queue, which the main loop reads
    only between commands (chromiq_json.c cq_handle_line, chromiq_tablescan.c); "ok" / "quit"
    go to the single key slot, which the calibration reads while it waits (chromiq_cal.c
    cq_wait_char: Esc = give up, any other key = go on). ``killed``: the reader's stop had to
    kill it (the real _Proc.stop: 5 s, then SIGKILL)."""

    fail_white = False

    def __init__(self, argv, log, cwd):
        self.q: "queue.Queue[dict]" = queue.Queue()
        self.events: "list[dict]" = []
        self.sent: "list[dict]" = []
        self.tsq: "list[str]" = []
        self.key = None
        self.state = "idle"
        self.exited = self.killed = False
        self._emit({"event": "tscan_start"})
        self._emit({"event": "tscan_instrument", "model": "X-Rite i1 Pro 2"})

    def _emit(self, ev):
        self.events.append(ev)
        self.q.put(ev)

    def send(self, obj):
        if self.exited:
            raise rd.ReaderFailed("the reader stopped listening (BrokenPipeError)")
        self.sent.append(dict(obj))
        cmd = obj.get("cmd", "")
        if cmd.startswith("tscan_"):
            self.tsq.append(cmd)
        else:
            self.key = {"quit": "esc", "ok": "ret"}.get(cmd, cmd)
        self._run()

    def _run(self):
        while not self.exited:
            if self.state == "cal_wait":
                if self.key is None:
                    return
                k, self.key = self.key, None
                if k == "esc":
                    self._emit({"event": "tscan_calibrated", "ok": False, "detail": "x"})
                    self.state = "idle"
                elif self.fail_white:
                    self._emit({"event": "error", "kind": "cal_failed", "detail": "x"})
                else:
                    self._emit({"event": "cal_done"})
                    self._emit({"event": "tscan_calibrated", "ok": True, "detail": ""})
                    self.state = "idle"
                continue
            if not self.tsq:
                return
            c = self.tsq.pop(0)
            if c == "tscan_calibrate":
                self._emit({"event": "cal_required", "cond": "man_ref_white", "id": "",
                            "optional": False})
                self.state = "cal_wait"
            elif c == "tscan_quit":
                self._emit({"event": "tscan_end"})
                self.exited = True
                self.q.put({"event": "helper_gone"})

    def alive(self):
        return not self.exited

    def wait(self, names, timeout):
        while True:
            try:
                ev = self.q.get_nowait()
            except queue.Empty:
                return None
            if ev.get("event") in names or ev.get("event") in ("helper_gone", "error"):
                return ev

    def poll(self, name):
        return None

    def stop(self, quit_cmd):
        if not self.exited:
            try:
                self.send(quit_cmd)
            except rd.ReaderFailed:
                pass
        if not self.exited:
            self.killed = self.exited = True


def _scan(monkeypatch, tmp_path, fail_white=False):
    proc = type("P", (_TableScanHelper,), {"fail_white": fail_white})
    monkeypatch.setattr(rd, "_Proc", proc)
    s = rd.ScanReader(Path("chromiq-chartread"), tmp_path / "strip", lambda *a: None)
    s.opened(timeout=1)
    return s


def test_a_failed_strip_white_ends_the_table_scan_helper_by_itself(tmp_path, monkeypatch):
    s = _scan(monkeypatch, tmp_path, fail_white=True)
    with pytest.raises(rd.ReaderFailed):
        s.calibrate(lambda ev: True, timeout=1)
    s.close()
    assert not s.proc.killed                       # 4.3.45: killed after 5 s
    assert s.proc.sent[-2:] == [{"cmd": "quit"}, {"cmd": "tscan_quit"}]
    assert [e["event"] for e in s.proc.events][-2:] == ["tscan_calibrated", "tscan_end"]


def test_a_refused_strip_white_place_ends_the_helper_by_itself(tmp_path, monkeypatch):
    s = _scan(monkeypatch, tmp_path)
    with pytest.raises(rd.ReaderFailed, match="not done"):
        s.calibrate(lambda ev: False, timeout=1)
    s.close()
    assert not s.proc.killed
    assert "cal_done" not in [e["event"] for e in s.proc.events]


def test_a_strip_reader_after_its_white_is_closed_exactly_as_before(tmp_path, monkeypatch):
    """Outside the calibration nothing more is sent: tscan_quit alone, as in 4.3.45."""
    s = _scan(monkeypatch, tmp_path)
    s.calibrate(lambda ev: True, timeout=1)
    s.close()
    assert not s.proc.killed
    assert s.proc.sent == [{"cmd": "tscan_calibrate"}, {"cmd": "ok"}, {"cmd": "tscan_quit"}]


def _src(name: str) -> str:
    return (HELPER_SRC / name).read_text(encoding="utf-8", errors="replace")


def test_the_table_scan_model_is_the_helpers_own_routing():
    js = _src("chromiq_json.c")
    # tscan_* lines go to the table-scan hook BEFORE any key is decoded
    a = js.index("static void cq_handle_line(")
    body = js[a:js.index("\n}\n", a)]
    assert body.index('strncmp(cmd, "tscan_", 6) == 0') < body.index('strcmp(cmd, "quit") == 0')
    assert re.search(r'strcmp\(cmd, "quit"\) == 0\)\s*\n\s*key = 0x1b;', body)
    assert re.search(r'strcmp\(cmd, "accept"\) == 0 \|\| strcmp\(cmd, "ok"\) == 0\)\s*\n\s*key '
                     r'= 0x0d;', body)
    ts = _src("chromiq_tablescan.c")
    assert "cq_tscan_line_hook = cq_ts_push;" in ts
    # the dual scan on the table (2026-11-19): a dual session first forgets its kept dual tile
    # (a new white needs a new one); nothing else may come before the calibration itself
    assert re.search(re.escape('strstr(line, "\\"tscan_calibrate\\"") != NULL) {')
                     + r"\s*(?:if \(cq_tscan_dual\) \{[^{}]*\}\s*)?"
                     + r"rv = cq_handle_calibrate", ts)
    cal = _src("chromiq_cal.c")
    # after cal_failed and at a placement request: ONE key; Esc gives up
    i = cal.index('cq_emit_error("cal_failed"')
    assert "ch = cq_wait_char();" in cal[i:i + 400]
    assert "if (ch == 0x1b" in cal[i:i + 500]


def test_the_spot_prompts_are_the_helpers_own():
    """KEY_PROMPTS and the chain are what the spot loop does: Esc at a patch gives
    strip_interrupted and one more key; "retry" is the misread prompt's "any other key"."""
    src = _src("chromiq_chartread.c")
    a = src.index("Spot read stopped at user request")
    a = src.index('cq_emit_simple("strip_interrupted");', a)
    assert "cq_prompt_char()) == 0x1b" in src[a:a + 200]
    js = _src("chromiq_json.c")
    assert re.search(r'strcmp\(cmd, "retry"\) == 0\)\s*\n\s*key = \'r\';', js)
    # a goto at a key prompt is dropped (cq_wait_char takes it and waits on)
    w = js[js.index("int cq_wait_char(void)"):]
    assert "k != CQ_KEY_GOTO" in w[:400]
    # the helper saves after every spot reading, before it offers the next patch
    i = src.index("/* We've read the spot sample */")
    seg = src[i:i + 1200]
    assert seg.index("cq_emit_patch_read(") < seg.index("cq_write_ti3_atomic();")


# ---- the white made by one helper process is found by the next (review items 1 and 4) --------

def test_the_apps_environment_never_moves_where_the_i1pro2_keeps_its_whites(monkeypatch):
    """ArgyllCMS's i1Pro driver keeps every mode's white in ONE file per instrument,
    $XDG_CACHE_HOME (else $HOME/Library/Caches)/ArgyllCMS/.i1p_<serial>.cal (i1pro_imp.c:
    i1pro_save_calibration at the end of every calibration, i1pro_restore_calibration when the
    instrument opens). Only HOME and XDG_CACHE_HOME decide the place, never the working folder;
    every reader process gets the app's own environment for both."""
    monkeypatch.setenv("HOME", "/Users/someone")
    monkeypatch.setenv("XDG_CACHE_HOME", "/Users/someone/cache")
    env = rd.helper_env()
    assert env["HOME"] == "/Users/someone" and env["XDG_CACHE_HOME"] == "/Users/someone/cache"
    monkeypatch.delenv("XDG_CACHE_HOME")
    assert "XDG_CACHE_HOME" not in rd.helper_env()
    # every reader starts through _Proc, which passes helper_env() and only changes the cwd
    src = (ROOT / "workflow/i1io/table/reader.py").read_text(encoding="utf-8")
    assert src.count("env=helper_env()") == 1 and src.count("subprocess.Popen(") == 1


def test_the_driver_saves_the_white_before_the_helper_says_it_is_done():
    """The white is on disk when "cal_done" / "tscan_calibrated" arrive, so a reader that is
    then ended (or killed) cannot lose it; the file is keyed by the serial number only."""
    imp = (ROOT / "native/instlib/i1pro_imp.c").read_text(encoding="utf-8", errors="replace")
    a = imp.index("i1pro_code i1pro_imp_calibrate(")
    body = imp[a:imp.index("\ni1pro_code ", a + 10)]
    assert "#define ENABLE_NONVCAL" in imp
    assert "i1pro_save_calibration(p);" in body
    assert 'sprintf(cal_name, "ArgyllCMS/.i1p_%d.cal", m->serno);' in imp
    assert "i1pro_restore_calibration(p);" in imp
    cal = _src("chromiq_cal.c")
    # cal_done is emitted after p->calibrate returned inst_ok (the save is inside it)
    assert cal.index("ev = p->calibrate(") < cal.index('cq_emit_simple("cal_done")')
    binary = (ROOT / "native/chromiq-chartread").read_bytes()
    assert b"ArgyllCMS/.i1p_%d.cal" in binary and b"XDG_CACHE_HOME" in binary


# ---- the same in the job, with the simulated helper (which now keeps the helper's prompts) ----

def _job(tmp_path, faults):
    from tests.i1io_table.test_job_reading import job_for, read_page, ready_to_read
    from workflow.i1io.table import job as J
    job, sim, helper, _run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED: "skip"}, faults=faults)
    ready_to_read(job, p)
    return job, sim, helper, read_page(job, p)


def test_a_row_whose_instrument_asks_for_a_white_ends_without_one_and_unkilled(tmp_path):
    """The 6th reading of the sitting (row 2's second patch) asks for a calibration: the row
    fails, a new white is due, no white is made where the arm stands, no reader is killed."""
    job, sim, helper, res = _job(tmp_path, {"read": {6: "cal_required"}})
    assert [r.detail["status"] for r in res] == ["read", "skipped"]
    assert job.calibration_due
    assert not [v for v in sim.violations if "calibration started" in v], sim.violations
    assert helper.killed == []
    # the row's first reading, saved by the helper before the request, is kept
    assert job.measurement().detail["measurement"]["read"] == 5


def test_a_row_with_a_failed_reading_is_read_again_and_no_reader_is_killed(tmp_path):
    job, sim, helper, res = _job(tmp_path, {"read_once": {"1-2": "error"}})
    assert [r.detail["status"] for r in res] == ["read", "read"]
    assert helper.killed == [] and sim.violations == []
    assert job.measurement().detail["measurement"]["state"] == "complete"
