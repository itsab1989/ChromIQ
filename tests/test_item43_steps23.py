"""Item 43 steps 2-3: every reading of Read single patches keeps M0, M1 and M2
where the instrument gives them (Basti's decision 2: the list can be switched
between M0, M1 and M2 without measuring again), read by ChromIQ's own helper
(``--spot-session``):

* an i1Pro 3 with the Beta "X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2
  from every scan";
* an i1Pro 2 with the dual scan Beta, following the dual scan's own "always /
  only for M1 or M2" (decision 3);
* everything else, and both Betas off: stock spotread, the command line of
  4.3.63 exactly.

The helper's wire is ``tests/test_spot_session_wire.py``'s business; here:
the helper's events through its replay instrument, the manager, the window,
the files.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox          # noqa: E402

from workflow import spot_read_io as IO                          # noqa: E402
from workflow.helper_spot_manager import (HelperSpotManager,     # noqa: E402
                                          HelperSpotParams)
from workflow.spot_read_io import SpotReading                    # noqa: E402

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, helper_env                      # noqa: E402

needs_helper = pytest.mark.skipif(not HELPER.exists(),
                                  reason="chromiq-chartread helper not built")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ===================================================================== files

def _kept(name, m0, m1, m2, shown="M0"):
    lab = lambda y: (y, 0.0, 0.0)                    # noqa: E731
    conds = {"M0": (m0, lab(m0[1])), "M1": (m1, lab(m1[1])),
             "M2": (m2, lab(m2[1]))}
    r = SpotReading(name=name, xyz=conds["M0"][0], lab=conds["M0"][1],
                    condition="M0", conditions=conds)
    r.show(shown)
    return r


def test_a_reading_shows_any_condition_it_keeps():
    r = _kept("P1", (40.0, 42.0, 35.0), (41.0, 43.0, 37.0), (39.0, 41.0, 33.0))
    assert r.keeps_several and r.condition == "M0"
    assert r.show("M1") and r.condition == "M1" and r.xyz == (41.0, 43.0, 37.0)
    assert not r.show("M1")                          # already shown
    assert r.show("M2") and r.xyz == (39.0, 41.0, 33.0)
    plain = SpotReading("P2", (1.0, 2.0, 3.0), (4.0, 5.0, 6.0), condition="M1")
    assert not plain.show("M2") and plain.condition == "M1"


def test_averaging_keeps_every_shared_condition_each_within_itself():
    a = _kept("A", (40.0, 40.0, 40.0), (44.0, 44.0, 44.0), (38.0, 38.0, 38.0))
    b = _kept("B", (42.0, 42.0, 42.0), (46.0, 46.0, 46.0), (40.0, 40.0, 40.0))
    avg = IO.average_readings([a, b], "Average")
    assert avg.condition == "M0" and avg.xyz == (41.0, 41.0, 41.0)
    assert avg.conditions["M1"][0] == (45.0, 45.0, 45.0)
    assert avg.conditions["M2"][0] == (39.0, 39.0, 39.0)
    avg.show("M1")
    assert avg.xyz == (45.0, 45.0, 45.0)
    # shown in different conditions: refused, as in step 1
    b.show("M1")
    with pytest.raises(IO.MixedConditions):
        IO.average_readings([a, b], "Average")


def test_save_writes_one_file_per_condition_whatever_is_shown(tmp_path):
    rs = [_kept("A", (40.0, 40.0, 40.0), (44.0, 44.0, 44.0), (38.0, 38.0, 38.0)),
          _kept("B", (20.0, 21.0, 22.0), (23.0, 24.0, 25.0), (19.0, 20.0, 21.0),
                shown="M2")]
    groups = IO.ti3_groups(tmp_path / "spots", rs)
    assert [p.name for p, _g in groups] == ["spots-M0.ti3", "spots-M1.ti3", "spots-M2.ti3"]
    for (_p, g), c in zip(groups, ("M0", "M1", "M2")):
        assert [r.condition for r in g] == [c, c]
        assert [r.name for r in g] == ["A", "B"]
    assert groups[1][1][1].xyz == (23.0, 24.0, 25.0)
    # the list is unchanged by the save
    assert [r.condition for r in rs] == ["M0", "M2"]
    paths = IO.write_ti3_files(tmp_path / "spots", rs)
    for p, c in zip(paths, ("M0", "M1", "M2")):
        text = p.read_text(encoding="latin-1")
        assert f'MEASUREMENT_CONDITION "{c}"' in text
    head = IO.write_csv(tmp_path / "spots.csv", rs).read_text(
        encoding="utf-8").splitlines()
    assert head[0].endswith(",condition") and head[2].endswith(",M2")


def test_lists_without_kept_conditions_save_as_before(tmp_path):
    rs = [SpotReading("A", (1.0, 2.0, 3.0), (4.0, 5.0, 6.0)),
          SpotReading("B", (1.0, 2.0, 3.0), (4.0, 5.0, 6.0))]
    assert [p.name for p, _g in IO.ti3_groups(tmp_path / "x", rs)] == ["x.ti3"]
    assert not IO.csv_needs_condition(rs)


# =================================================================== manager

class _StubRunner:
    def __init__(self):
        self.writes: list = []
        self.runs: list = []
        self.aborted = 0

    def write_stdin(self, text):
        self.writes.append(json.loads(text) if text.strip().startswith("{") else text)

    def run(self, tool, args, cwd, **kw):
        self.runs.append((tool, list(args), kw))

    def abort(self):
        self.aborted += 1

    def forget_run_callbacks(self):
        pass

    @property
    def is_running(self):
        return False


def _mgr(monkeypatch, **params):
    monkeypatch.setattr("core.instrument_port.refused_port", lambda *a: None)
    r = _StubRunner()
    m = HelperSpotManager(r)
    m.start(HelperSpotParams(helper=Path("/x/chromiq-chartread"), **params),
            lambda _l: None)
    return m, r


def _spec(level):
    return {"short": 380.0, "long": 730.0, "norm": 100, "v": [level] * 36}


def _reading_ev(m0=(40.0, 42.0, 35.0), m1=(41.0, 43.0, 37.0), m2=(39.0, 41.0, 33.0),
                level=40.0):
    return {"event": "spot_reading", "n": 1, "main": "M0", "XYZ": list(m0),
            "Lab": [70.0, 1.0, 2.0], "spec": _spec(level), "dual": False,
            "conditions": {"M1": {"XYZ": list(m1), "Lab": [71.0, 1.0, 1.0]},
                           "M2": {"XYZ": list(m2), "Lab": [69.0, 1.0, 3.0]}}}


def test_the_helper_command_line(qapp, monkeypatch):
    m, r = _mgr(monkeypatch)
    assert r.runs[0][0] == "/x/chromiq-chartread"
    assert r.runs[0][1] == ["--json", "--spot-session", "--spot-conditions", "-c", "1"]
    assert r.runs[0][2]["use_pty"] is False
    m, r = _mgr(monkeypatch, disable_initial_cal=True)
    assert r.runs[0][1][-1] == "-N"
    dual = ["--dual-scale", "1.1560", "--dual-scale-source", "standard",
            "--dual-white", "instrument", "--dual-chosen", "M1"]
    m, r = _mgr(monkeypatch, disable_initial_cal=True, dual_args=dual, chosen="M1")
    assert r.runs[0][1] == ["--json", "--spot-session", "--spot-conditions"] + dual \
        + ["-c", "1"]                                 # never -N with the dual scan


def test_every_condition_reaches_the_window_before_the_reading(qapp, monkeypatch):
    m, _r = _mgr(monkeypatch)
    got = []
    m.reading_conditions.connect(lambda c: got.append(("conds", c)))
    m.reading_ready.connect(lambda x, l: got.append(("reading", x)))
    m.handle_event({"event": "filter", "filter": "none"})
    m.handle_event({"event": "conditions", "active": True, "main": "M0"})
    m.handle_event(_reading_ev())
    assert got[0][0] == "conds" and set(got[0][1]) == {"M0", "M1", "M2"}
    assert got[0][1]["M1"][0] == (41.0, 43.0, 37.0)
    assert got[1] == ("reading", (40.0, 42.0, 35.0))


def test_a_uv_cut_filter_records_no_condition(qapp, monkeypatch):
    m, _r = _mgr(monkeypatch)
    got = []
    m.reading_conditions.connect(got.append)
    m.handle_event({"event": "filter", "filter": "uvcut"})
    m.handle_event(_reading_ev())
    assert got == [{}]


def test_item_41_judges_the_m0_spectrum(qapp, monkeypatch):
    """M1 may glow above the limit with a fluorescent ink; the lamp's M0 is
    what tells a calibration that was too weak."""
    m, _r = _mgr(monkeypatch)
    v = []
    m.calibration_suspect.connect(v.append)
    m.handle_event(_reading_ev(level=60.0))           # M0 fine (M1 is not looked at)
    assert v == []
    m2, _r = _mgr(monkeypatch)
    m2.calibration_suspect.connect(v.append)
    m2.handle_event(_reading_ev(level=108.0))         # M0 lighter than a print can be
    assert len(v) == 1 and v[0].reason != "saturated"


def test_an_instrument_without_other_conditions_goes_to_spotread(qapp, monkeypatch):
    m, r = _mgr(monkeypatch)
    dropped, fb, ended = [], [], []
    m.condition_dropped.connect(dropped.append)
    m.fallback_requested.connect(lambda: fb.append(1))
    m.session_ended.connect(ended.append)
    m.handle_event({"event": "instrument", "model": "X-Rite ColorMunki"})
    m.handle_event({"event": "conditions", "active": False, "why": "instrument"})
    assert dropped == ["X-Rite ColorMunki"]
    assert r.writes[-1] == {"cmd": "quit"}
    prompts = []
    m.calibration_prompt.connect(lambda: prompts.append(1))
    m.handle_event({"event": "cal_required", "cond": "man_ref_white", "id": ""})
    m.handle_event({"event": "spot_ready", "n": 1})    # not offered to the window
    assert prompts == []          # its key would reach the spotread that follows
    m._on_finish(0)
    assert fb == [1] and ended == []


def test_m1_m2_ending_mid_session_is_said_and_m0_goes_on(qapp, monkeypatch):
    m, r = _mgr(monkeypatch)
    said, fb = [], []
    m.conditions_ended.connect(said.append)
    m.fallback_requested.connect(lambda: fb.append(1))
    m.handle_event({"event": "conditions", "active": True, "dual": True})
    m.handle_event(_reading_ev())
    m.handle_event({"event": "conditions", "active": False, "why": "dual_bad_values"})
    assert said and "not numbers" in said[0]
    assert {"cmd": "quit"} not in r.writes
    m._on_finish(0)
    assert fb == []


def test_a_refused_dual_spot_asks_for_a_calibration_and_holds_ready(qapp, monkeypatch):
    m, r = _mgr(monkeypatch, dual_args=["--dual-scale", "1.1560"])
    refused, ready, misread = [], [], []
    m.dual_spot_refused.connect(lambda w, c: refused.append((w, c)))
    m.ready_to_read.connect(lambda: ready.append(1))
    m.misread.connect(lambda: misread.append(1))
    m.handle_event({"event": "dual_pass_result", "what": "spot", "ok": False,
                    "why": "no_dual_calibration", "calibrate": True})
    m.handle_event({"event": "error", "kind": "spot_misread", "detail": "x"})
    m.handle_event({"event": "spot_ready", "n": 1})
    assert refused == [("no_dual_calibration", True)] and misread == [] and ready == []
    m.send_key("\r")                                   # the window leaves the misread
    assert ready == [1]
    m.request_calibration()
    assert r.writes[-1] == {"cmd": "calibrate"}


def test_the_windows_keys(qapp, monkeypatch):
    m, r = _mgr(monkeypatch)
    m.handle_event({"event": "cal_required", "cond": "man_ref_white", "id": ""})
    m.send_key("\r")
    assert r.writes[-1] == {"cmd": "ok"}
    m.take_reading()
    assert r.writes[-1] == {"cmd": "read"}
    m.handle_event({"event": "cal_required", "cond": "man_ref_white", "id": "",
                    "requested": True})
    m.send_key("\x1b")                                 # Cancel session in that window
    assert r.writes[-2:] == [{"cmd": "cal_cancel"}, {"cmd": "quit"}]


def test_a_cancelled_calibration_is_not_called_complete(qapp, monkeypatch):
    m, _r = _mgr(monkeypatch)
    done = []
    m.calibration_finished.connect(lambda: done.append(1))
    m.handle_event({"event": "cal_required", "cond": "man_ref_white", "id": "",
                    "requested": True})
    m.handle_event({"event": "cal_result", "result": "cancelled", "damaged": False})
    m.handle_event({"event": "spot_ready", "n": 1})
    assert done == []


# ============================================== the real helper, replayed

def _session(tmp_path, script: str, inst: str, *, flags=(), cmds=(), env=None,
             timeout=20.0):
    """The REAL helper's spot session through its replay instrument; *cmds*
    are (event to wait for, command) pairs. Returns every event."""
    rp = tmp_path / "replay.txt"
    rp.write_text(script, encoding="utf-8")
    e = helper_env()
    e["CHROMIQ_REPLAY_INSTRUMENT"] = inst
    e.update(env or {})
    p = subprocess.Popen([str(HELPER), "--json", "--spot-session", *flags,
                          "--replay", str(rp)], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         text=True, encoding="utf-8", cwd=tmp_path, env=e)
    import threading
    events: list = []

    def _read():
        for ln in p.stdout:
            if ln.strip().startswith("{"):
                events.append(json.loads(ln))
    t = threading.Thread(target=_read, daemon=True)
    t.start()
    seen = 0
    end = time.monotonic() + timeout
    for want, cmd in cmds:
        while want is not None:
            idx = next((i for i, ev in enumerate(events[seen:], seen)
                        if ev.get("event") == want), None)
            if idx is not None:
                seen = idx + 1
                break
            if time.monotonic() > end:
                p.kill()
                pytest.fail(f"no {want}: {events[-4:]}")
            time.sleep(0.02)
        p.stdin.write(json.dumps(cmd) + "\n")
        p.stdin.flush()
    p.wait(timeout=10)
    t.join(5)
    return events


I1PRO3_SCRIPT = """PATCHES 2
STRIP A
50 52 40
20 21 18
COND M1
51 53 42
21 22 19
COND M2
49 51 38
19 20 17
"""


@needs_helper
def test_an_i1pro3_press_keeps_all_three(tmp_path):
    ev = _session(tmp_path, I1PRO3_SCRIPT, "i1pro3", flags=["--spot-conditions"],
                  cmds=[("spot_ready", {"cmd": "read"}), ("spot_ready", {"cmd": "read"}),
                        ("spot_ready", {"cmd": "quit"})])
    cond = [e for e in ev if e["event"] == "conditions"]
    assert cond[0]["active"] is True and cond[0]["instrument"] == "i1pro3"
    rd = [e for e in ev if e["event"] == "spot_reading"]
    assert [r["XYZ"] for r in rd] == [[50.0, 52.0, 40.0], [20.0, 21.0, 18.0]]
    assert rd[0]["conditions"]["M1"]["XYZ"] == [51.0, 53.0, 42.0]
    assert rd[1]["conditions"]["M2"]["XYZ"] == [19.0, 20.0, 17.0]
    assert ev[-1] == {"event": "spot_session_end", "why": "stopped"}
    # nothing written: no chart, no file
    assert sorted(p.name for p in tmp_path.iterdir()) == ["replay.txt"]


@needs_helper
def test_without_spot_conditions_a_reading_has_m0_only(tmp_path):
    ev = _session(tmp_path, I1PRO3_SCRIPT, "i1pro3",
                  cmds=[("spot_ready", {"cmd": "read"}), ("spot_ready", {"cmd": "quit"})])
    assert [e for e in ev if e["event"] == "conditions"][0] == \
        {"event": "conditions", "active": False, "why": "off"}
    rd = [e for e in ev if e["event"] == "spot_reading"]
    assert rd[0]["conditions"] == {}


@needs_helper
def test_another_instrument_says_so_before_any_reading(tmp_path):
    ev = _session(tmp_path, I1PRO3_SCRIPT, "colormunki", flags=["--spot-conditions"],
                  cmds=[("spot_ready", {"cmd": "quit"})])
    c = [e for e in ev if e["event"] == "conditions"][0]
    assert c["active"] is False and c["why"] == "instrument"
    assert not [e for e in ev if e["event"] == "spot_reading"]


@needs_helper
def test_a_misread_is_read_again_and_a_calibration_can_be_asked_for(tmp_path):
    ev = _session(tmp_path, I1PRO3_SCRIPT, "i1pro3", flags=["--spot-conditions"],
                  env={"CHROMIQ_REPLAY_CAL": "setup_ok"},
                  cmds=[("spot_ready", {"cmd": "swipe", "fault": "misread"}),
                        (None, {"cmd": "read"}),
                        ("error", {"cmd": "calibrate"}),
                        ("cal_required", {"cmd": "ok"}),
                        ("cal_result", {"cmd": "read"}),
                        ("spot_reading", {"cmd": "quit"})])
    kinds = [e["event"] for e in ev]
    assert kinds.index("error") < kinds.index("cal_required") < kinds.index("spot_reading")
    assert [e for e in ev if e["event"] == "error"][0]["kind"] == "spot_misread"
    assert [e for e in ev if e["event"] == "cal_required"][0]["requested"] is True
    assert [e for e in ev if e["event"] == "cal_result"][0]["result"] == "done"
    rd = [e for e in ev if e["event"] == "spot_reading"]
    assert len(rd) == 1 and rd[0]["n"] == 1


@needs_helper
def test_the_end_of_stdin_ends_the_session(tmp_path):
    """The app gone (its end of the pipe closed): the session leaves the
    wait and closes the instrument itself."""
    rp = tmp_path / "r.txt"
    rp.write_text(I1PRO3_SCRIPT, encoding="utf-8")
    e = helper_env()
    e["CHROMIQ_REPLAY_INSTRUMENT"] = "i1pro3"
    t0 = time.monotonic()
    r = subprocess.run([str(HELPER), "--json", "--spot-session", "--spot-conditions",
                        "--replay", str(rp)], input="", capture_output=True, text=True, encoding="utf-8",
                       timeout=20, env=e, cwd=tmp_path)
    assert time.monotonic() - t0 < 10
    assert '"spot_reading"' not in r.stdout
    assert '{"event":"spot_session_end","why":"stdin"}' in r.stdout
    assert r.returncode == 0


@needs_helper
def test_an_i1pro2_dual_spot_gives_the_dual_scans_own_m1_and_m2(tmp_path):
    """The replay's LAMP / UV records through the helper's arithmetic: the
    Python module's numbers (the chart dual scan's own check, for one press)."""
    from tests.test_i1pro2_dual_scan_engine import _invented, _paper, _vec, S
    from workflow.dual_scan import model
    tab, cal = _invented()
    m2, g = _paper([40.0, 70.0], 7)
    L, U, M1 = model.forward(m2, g, cal, tab, S)
    lines = ["PATCHES 2", "DUALCAL", f"W {_vec(cal.white)}", f"T {_vec(cal.uv_tile)}",
             f"E {_vec(cal.emis)}", f"KA {_vec(tab.kA[:18])}", f"KD {_vec(tab.kD[:18])}",
             "CLOCKS 139 139", "STRIP A"]
    for i in range(2):
        lines += [f"LAMP {_vec(L[i])}", f"UV {_vec(U[i])}"]
    dual = ["--dual-scale", f"{S:.4f}", "--dual-scale-source", "standard",
            "--dual-white", "instrument", "--dual-chosen", "M2"]
    ev = _session(tmp_path, "\n".join(lines) + "\n", "i1pro2",
                  flags=["--spot-conditions", *dual],
                  cmds=[("spot_ready", {"cmd": "read"}), ("spot_ready", {"cmd": "read"}),
                        ("spot_ready", {"cmd": "quit"})])
    c = [e for e in ev if e["event"] == "conditions"][0]
    assert c["active"] and c["dual"] and c["chosen"] == "M2"
    rd = [e for e in ev if e["event"] == "spot_reading"]
    assert len(rd) == 2
    for i, r in enumerate(rd):
        np.testing.assert_allclose(np.array(r["spec"]["v"]) / 100.0, L[i], atol=1e-5)
        np.testing.assert_allclose(np.array(r["conditions"]["M2"]["spec"]["v"]) / 100.0,
                                   m2[i], atol=1e-5)
        np.testing.assert_allclose(np.array(r["conditions"]["M1"]["spec"]["v"]) / 100.0,
                                   M1[i], atol=1e-5)


# ==================================================================== window

def _dialog(monkeypatch, family, *, stored="M0", conditions_beta=False,
            dual_beta=False, dual_mode="m1_m2"):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.dialogs.spot_read_dialog import SpotReadDialog
    from workflow.dual_scan import instrument_model as IM

    class _D(SpotReadDialog):
        def _ask(self, box: QMessageBox):
            self.asked.append((box.text(), box.informativeText()))
            for b in box.buttons():
                if b.text().replace("&", "") in ("Carry on measuring", "Replace"):
                    return b
            return None

    monkeypatch.setattr(IM, "attached_family", lambda: family)
    monkeypatch.setattr("core.instrument_port.refused_port", lambda *a: None)
    import tempfile
    from PyQt6.QtCore import QSettings
    s = AppSettings()
    s._qs = QSettings(str(Path(tempfile.mkdtemp(prefix="chromiq-item43b-")) / "s.ini"),
                      QSettings.Format.IniFormat)
    s.set("spot_read_instrument", "argyll")
    s.set("spot_read_condition", stored)
    s.set("i1pro3_conditions_beta", bool(conditions_beta or dual_beta))
    s.set("i1pro2_dual_scan_beta", bool(dual_beta))
    s.set("i1pro2_dual_scan_mode", dual_mode)
    runner = ArgyllRunner(s)
    runs: list = []
    monkeypatch.setattr(runner, "run",
                        lambda tool, args, cwd, **k: runs.append(list(args)))
    sent: list = []
    monkeypatch.setattr(runner, "write_stdin", sent.append)
    d = _D(runner, s)
    d.asked = []
    d.runs = runs
    d.sent = sent
    return d


def _helper_events(d, model, readings=(), dual=False):
    h = d._helper_mgr
    h.handle_event({"event": "instrument", "model": model})
    h.handle_event({"event": "filter", "filter": "none"})
    h.handle_event({"event": "conditions", "active": True, "dual": dual,
                    "main": "M0", "extra": ["M1", "M2"]})
    h.handle_event({"event": "spot_ready", "n": 1})
    for r in readings:
        h.handle_event(r)
        h.handle_event({"event": "spot_ready", "n": 2})


def _sent(d):
    return [json.loads(x) for x in d.sent if x.strip().startswith("{")]


@needs_helper
def test_with_both_betas_off_an_i1pro3_starts_4363s_spotread(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3, stored="M1")
    d._on_start_stop()
    assert d.runs == [["-v", "-c", "1", "-F", "5", "-s"]]
    assert d._manager is d._spotread
    d.deleteLater()


@needs_helper
@pytest.mark.parametrize("dual_beta", [False, True])
def test_an_i1pro_family_without_the_dual_rule_starts_plain_spotread(
        qapp, monkeypatch, dual_beta):
    """Betas off: the row is hidden, today's command line. Dual scan on, but
    "only for M1 or M2" with M0 chosen: an ordinary spot reading, no -F
    (an i1Pro 2 refuses every -F)."""
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO, dual_beta=dual_beta)
    assert d._cond_row.isHidden() is (not dual_beta)
    d._on_start_stop()
    assert d.runs == [["-v", "-c", "1", "-s"]]
    d.deleteLater()


@needs_helper
def test_an_i1pro3_with_the_conditions_beta_keeps_all_three(qapp, monkeypatch, tmp_path):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3, stored="M1", conditions_beta=True)
    d._on_start_stop()
    assert d.runs == [["--json", "--spot-session", "--spot-conditions", "-c", "1"]]
    assert d._manager is d._helper_mgr
    _helper_events(d, "X-Rite i1 Pro 3", [_reading_ev()])
    r = d._readings[0]
    assert r.condition == "M1" and r.xyz == (41.0, 43.0, 37.0)   # shown as chosen
    assert set(r.conditions) == {"M0", "M1", "M2"}
    assert d._table.item(0, 8).text() == "M1"
    assert not d._view_row.isHidden()
    assert d._view.currentData() == "M1"
    assert d._condition.currentData() == "M1"                  # the choice stays
    # the whole list in M2, nothing measured
    n_runs, n_sent = len(d.runs), len(d.sent)
    d._view.setCurrentIndex(2)
    assert r.condition == "M2" and r.xyz == (39.0, 41.0, 33.0)
    assert d._table.item(0, 8).text() == "M2"
    assert d._table.item(0, 4).text().startswith("39")       # X of M2
    assert (len(d.runs), len(d.sent)) == (n_runs, n_sent)
    # Save: one .ti3 per condition, the CSV as shown
    monkeypatch.setattr("ui.widgets.save_file_dialog",
                        lambda *a, **k: str(tmp_path / "spots.csv"))
    monkeypatch.setattr("ui.dialogs.spot_read_dialog.inform", lambda *a, **k: None)
    assert d._on_save()
    assert sorted(p.name for p in tmp_path.iterdir()) == \
        ["spots-M0.ti3", "spots-M1.ti3", "spots-M2.ti3", "spots.csv"]
    assert (tmp_path / "spots.csv").read_text(encoding="utf-8").splitlines()[1] \
        .endswith(",M2")
    d.deleteLater()


@needs_helper
def test_the_session_note_says_every_reading_keeps_all_three(qapp, monkeypatch):
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3, conditions_beta=True)
    d._on_start_stop()
    _helper_events(d, "X-Rite i1 Pro 3")
    assert M.M_SPOT_ALL_CONDITIONS.render()[1] in d._status.text()
    d.deleteLater()


@needs_helper
@pytest.mark.parametrize("mode,chosen,dual", [("m1_m2", "M1", True), ("m1_m2", "M2", True),
                                               ("always", "M0", True)])
def test_an_i1pro2_with_the_dual_scan_reads_dual_spots(qapp, monkeypatch, mode,
                                                       chosen, dual):
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO, stored=chosen, dual_beta=True,
                dual_mode=mode)
    assert not d._cond_row.isHidden()
    d._skip_cal.setChecked(True)
    d._on_start_stop()
    args = d.runs[0]
    assert args[:3] == ["--json", "--spot-session", "--spot-conditions"]
    assert args[args.index("--dual-chosen") + 1] == chosen
    assert args[args.index("--dual-scale") + 1] == "1.1560"
    assert "-N" not in args and "-F" not in args
    _helper_events(d, "X-Rite i1 Pro 2", [_reading_ev()], dual=True)
    assert M.M_SPOT_DUAL_SKIP_CAL.render()[1] in d._status.text() or \
        M.M_SPOT_DUAL_SKIP_CAL.render()[1] in d._session_note
    assert d._readings[0].condition == chosen
    d.deleteLater()


@needs_helper
def test_the_dual_calibration_window_says_the_tile_is_read_with_uv(qapp, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QLabel
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO, stored="M1", dual_beta=True)
    d._on_start_stop()
    shown = []

    def _exec(dlg):
        shown.append(" ".join(l.text() for l in dlg.findChildren(QLabel)))
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, "exec", _exec)
    d._helper_mgr.handle_event({"event": "cal_required", "cond": "man_ref_white",
                                "id": ""})
    assert M.M_SPOT_DUAL_CAL_TILE.render()[1] in shown[0]
    assert _sent(d)[-1] == {"cmd": "ok"}
    d.deleteLater()


@needs_helper
def test_a_wrong_guess_starts_spotread_before_anything_is_read(qapp, monkeypatch):
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO, stored="M1", dual_beta=True)
    d._on_start_stop()
    h = d._helper_mgr
    h.handle_event({"event": "instrument", "model": "GretagMacbeth i1 Pro"})
    h.handle_event({"event": "conditions", "active": False,
                    "why": "dual_no_uv_tables"})
    assert _sent(d)[-1] == {"cmd": "quit"}
    h._on_finish(0)
    assert d.runs[-1] == ["-v", "-c", "1", "-s"]               # no -F to an i1Pro
    assert d._manager is d._spotread
    assert "GretagMacbeth i1 Pro" in d._status.text()
    assert M.M_SPOT_CONDITION_FALLBACK.render(model="GretagMacbeth i1 Pro")[1] \
        == d._condition_note
    d.deleteLater()


@needs_helper
def test_a_refused_dual_spot_asks_for_a_calibration_on_the_status_line(qapp, monkeypatch):
    from workflow import measurement_messages as M
    from workflow.dual_scan import instrument_model as IM
    from workflow.dual_scan.session import reason_sentence
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO, stored="M1", dual_beta=True)
    d._on_start_stop()
    _helper_events(d, "X-Rite i1 Pro 2", dual=True)
    h = d._helper_mgr
    h.handle_event({"event": "dual_pass_result", "what": "spot", "ok": False,
                    "why": "no_dual_calibration", "calibrate": True})
    h.handle_event({"event": "error", "kind": "misread", "detail": ""})
    h.handle_event({"event": "spot_ready", "n": 1})
    st = d._status.text()
    assert reason_sentence("no_dual_calibration") in st
    assert M.M_SPOT_DUAL_CALIBRATE.render()[1] in st
    assert d._read_btn.isEnabled()
    d._calibrate_again()
    assert _sent(d)[-1] == {"cmd": "calibrate"}
    assert not d._readings
    d.deleteLater()


@needs_helper
def test_m1_m2_ending_keeps_the_list_and_says_so(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO, stored="M1", dual_beta=True)
    d._on_start_stop()
    _helper_events(d, "X-Rite i1 Pro 2", [_reading_ev()], dual=True)
    h = d._helper_mgr
    h.handle_event({"event": "conditions", "active": False, "why": "dual_bad_values"})
    from workflow import measurement_messages as M
    from workflow.dual_scan.session import reason_sentence
    said = M.M_SPOT_CONDITIONS_ENDED.render(reason=reason_sentence("dual_bad_values"))[1]
    assert d._status.text() == said
    plain = dict(_reading_ev())
    plain["conditions"] = {}
    h.handle_event(plain)
    h.handle_event({"event": "spot_ready", "n": 3})
    assert said in d._status.text()                       # kept above Ready
    assert d._readings[0].keeps_several and d._readings[0].condition == "M1"
    assert d._readings[1].conditions is None and d._readings[1].condition == "M0"
    d.deleteLater()


@needs_helper
def test_average_of_kept_readings_can_be_shown_in_any_condition(qapp, monkeypatch):
    from workflow.dual_scan import instrument_model as IM
    d = _dialog(monkeypatch, IM.FAMILY_I1PRO3, conditions_beta=True)
    d._on_start_stop()
    _helper_events(d, "X-Rite i1 Pro 3", [_reading_ev(), _reading_ev(
        m0=(42.0, 44.0, 37.0), m1=(43.0, 45.0, 39.0), m2=(41.0, 43.0, 35.0))])
    d._table.selectAll()
    d._on_average_selected()
    avg = d._readings[-1]
    assert avg.condition == "M0" and avg.keeps_several
    d._view.setCurrentIndex(1)
    assert avg.xyz == (42.0, 44.0, 38.0)
    d.deleteLater()
