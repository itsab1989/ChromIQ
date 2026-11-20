"""4.3.52: the i1Pro 2 lights Beta's blue before the return pass of a dual scan,
and the quiet time before a reading as a setting of its own.

The owner, 2026-11-20: "yes build the blue light, are we too cautious with our
waiting time at the moment?" and "could we allow the user to set the timing
himself with recommendations of what was measured inside i1profiler and leave
more room than that to the bottom end?". The study (ChromIQ-work
2026-11-20_pulse452b/quiet_study.txt) keeps 2.1 s as the default.

Proved here on a FAKE USB layer through the REAL vendored driver
(native/chartread_helper/tests/i1pro2_dual_lights_test.c), and against ChromIQ
4.3.51's i1pro.c / i1pro_imp.c / i1pro_imp.h for every life that asks for
nothing new:

* the blue is the recorded 0xD6 + 702 bytes on 0x03, sent after the lamp pass
  and before the return pass's first trigger, and nothing else changes;
* it is refused (nothing on the wire) without the lights, without result
  signals, outside the return pass's wait, in a single scan, once the button
  was pressed, and a second time in one wait;
* the user's quiet time changes only how long the next trigger waits;
* everything else on the wire is 4.3.51's, byte for byte.

And the helper's and the app's side: the 550 ms, the skip, the flag, the
setting, Preferences, the log lines and the session header.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HELPER_SRC = ROOT / "native" / "chartread_helper"
INSTLIB = ROOT / "native" / "instlib"
BLUE_SHA256 = "f848b4e7f588225ab4af171034b582764da75d687527592a20a420e3acd6d202"


@pytest.fixture(scope="module")
def traces(tmp_path_factory) -> "dict[str, str]":
    if sys.platform == "win32":
        pytest.skip("the fake-USB driver tests are built on macOS and Linux only")
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not available: the helper is not built here")
    tmp = tmp_path_factory.mktemp("dualblue")
    old = tmp / "v4351"
    old.mkdir()
    for f in ("i1pro.c", "i1pro_imp.c", "i1pro_imp.h"):
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"v4.3.51:native/instlib/{f}"],
                           capture_output=True, timeout=60)
        if r.returncode != 0:
            pytest.skip("the v4.3.51 tag is not in this checkout")
        (old / f).write_bytes(r.stdout)
    build = tmp / "build"
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build),
                    "-DCMAKE_BUILD_TYPE=Release", f"-DCQ_V4351_I1PRO_DIR={old}"],
                   check=True, capture_output=True, timeout=600)
    jobs = str(max(2, (os.cpu_count() or 4) // 2))
    targets = ("i1pro2_dual_lights_test", "i1pro2_dual_lights_test_v4351")
    r = subprocess.run([cmake, "--build", str(build), "--target", *targets, "-j", jobs],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=1500)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    out = {}
    for t in targets:
        exe = next(p for p in build.rglob(t + "*")
                   if p.is_file() and os.access(p, os.X_OK) and p.name in (t, t + ".exe"))
        # budgeted for a loaded machine: about 15 s idle
        rr = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8",
                            timeout=600)
        assert rr.returncode == 0 and rr.stdout.rstrip().endswith("ALL DONE"), \
            t + " did not finish\n" + rr.stdout[-2000:] + rr.stderr[-2000:]
        out[t] = rr.stdout
    return out


def _lines(text: str, scn: str) -> "list[str]":
    return [ln.split(" ", 1)[1] for ln in text.splitlines() if ln.startswith(scn + " ")]


def _wire(text: str, scn: str) -> "list[str]":
    """The requests only (no timing, no notes)."""
    return [ln for ln in _lines(text, scn) if ln.split(" ", 1)[0] in ("CTL", "WR", "RD")]


def _blue_writes(wire: "list[str]") -> "list[int]":
    return [i for i, ln in enumerate(wire) if ln.startswith("WR 03 702 ")]


SAME = ("same_off_single", "same_off_dual", "same_lights_single", "same_lights_dual",
        "same_ready_dual")


@pytest.mark.parametrize("scn", SAME)
def test_every_life_that_asks_for_nothing_new_is_4_3_51s_wire(traces, scn):
    new = traces["i1pro2_dual_lights_test"]
    old = traces["i1pro2_dual_lights_test_v4351"]
    steps = [ln for ln in _lines(new, scn) if not ln.startswith("GAPMS")]
    assert steps == [ln for ln in _lines(old, scn) if not ln.startswith("GAPMS")]
    assert len(_wire(new, scn)) >= 2
    assert not _blue_writes(_wire(new, scn))


def test_the_blue_is_the_recorded_bytes_in_the_recorded_request(traces):
    wire = _wire(traces["i1pro2_dual_lights_test"], "blue_sent")
    (i,) = _blue_writes(wire)
    assert wire[i - 1] == "CTL d6 000002be"          # 0xD6 announcing 702 bytes, as recorded
    data = bytes.fromhex(wire[i].split()[3])
    assert len(data) == 702 and hashlib.sha256(data).hexdigest() == BLUE_SHA256


def test_the_blue_comes_after_the_lamp_pass_and_before_the_return_pass(traces):
    lines = _lines(traces["i1pro2_dual_lights_test"], "blue_sent")
    wire = [ln for ln in lines if ln.split(" ", 1)[0] in ("CTL", "WR", "RD", "STEP")]
    blue = next(k for k, ln in enumerate(wire) if ln.startswith("WR 03 702 "))
    lamp = max(k for k, ln in enumerate(wire[:blue]) if ln.startswith("CTL d4 ") and ln.endswith("0105"))
    after = [ln for ln in wire[blue + 1:] if ln.startswith("CTL d4 ")]
    # nothing but readings between the lamp pass and the blue; then the
    # return pass's dark trigger and its UV trigger "ruler end" (0x0209)
    between = [ln for ln in wire[lamp + 1:blue - 1] if not ln.startswith(("RD ", "STEP "))]
    assert between == []
    assert after[0].endswith("0000") and after[1].endswith("0209")
    assert wire.index("STEP return-wait") < blue < wire.index("STEP return-pass")


def test_nothing_else_on_the_wire_changes_with_the_blue(traces):
    t = traces["i1pro2_dual_lights_test"]
    wire = _wire(t, "blue_sent")
    (i,) = _blue_writes(wire)
    assert wire[:i - 1] + wire[i + 1:] == _wire(t, "same_lights_dual")


@pytest.mark.parametrize("scn,same", [
    ("blue_pressed_first", "same_lights_dual"),   # the button came first: skipped
    ("blue_no_signals", "same_ready_dual"),       # "ready light only": never
    ("blue_lights_off", "same_off_dual"),         # the lights Beta off: never
    ("blue_in_lamp_pass", "same_lights_dual"),    # in the lamp pass's wait: never
])
def test_where_the_blue_is_refused_nothing_is_sent(traces, scn, same):
    t = traces["i1pro2_dual_lights_test"]
    assert _wire(t, scn) == _wire(t, same)
    assert all(ln == "SECOND-PASS 0" for ln in _lines(t, scn) if ln.startswith("SECOND-PASS"))


def test_never_in_a_single_scan(traces):
    t = traces["i1pro2_dual_lights_test"]
    assert _wire(t, "blue_single_scan") == _wire(t, "same_lights_single")


def test_once_per_return_pass_and_never_after_its_wait(traces):
    t = traces["i1pro2_dual_lights_test"]
    assert [ln for ln in _lines(t, "blue_twice") if ln.startswith("SECOND-PASS")] == \
        ["SECOND-PASS 1", "SECOND-PASS 0"]
    assert len(_blue_writes(_wire(t, "blue_twice"))) == 1
    # blue_sent asks again in the next strip's lamp pass and after the wait
    assert [ln for ln in _lines(t, "blue_sent") if ln.startswith("SECOND-PASS")] == \
        ["SECOND-PASS 1", "SECOND-PASS 0", "SECOND-PASS 0"]


def _return_gap(t: str, scn: str) -> int:
    lines = _lines(t, scn)
    k = lines.index("STEP return-pass")
    return int(next(ln for ln in lines[k:] if ln.startswith("GAPMS")).split()[1])


def test_the_quiet_time_changes_the_wait_and_never_a_byte(traces):
    t = traces["i1pro2_dual_lights_test"]
    for scn in ("quiet_0", "quiet_400", "quiet_bad"):
        assert _wire(t, scn) == _wire(t, "blue_sent"), scn
    assert _return_gap(t, "quiet_0") < 150           # no wait at all
    assert 400 <= _return_gap(t, "quiet_400") < 1500
    assert _return_gap(t, "quiet_bad") >= 2100       # out of range: 4.3.37's 2100 ms


# ---------------------------------------------------------------------------
# The driver block (native/instlib/i1pro_imp.c, via scripts/vendor_instlib.py)
# ---------------------------------------------------------------------------
def _driver() -> str:
    return (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="surrogateescape")


def _body(text: str, head: str) -> str:
    b = text[text.index(head):]
    return b[:b.index("\n}\n")]


def test_the_default_quiet_time_is_still_2100_ms():
    t = _driver()
    assert "#define CQ_LIGHTS_QUIET_MS   2100" in t
    assert "int i1pro2_cq_lights_quiet_ms = -1;" in t
    q = _body(t, "static void cq_lights_quiet(i1proimp *m) {")
    assert ("(i1pro2_cq_lights_quiet_ms >= 0 && i1pro2_cq_lights_quiet_ms <= CQ_LIGHTS_QUIET_MAX_MS)"
            in q)
    assert "CQ_LIGHTS_QUIET_MS;" in q
    assert "#define CQ_LIGHTS_QUIET_MAX_MS 10000" in t


def test_the_blue_entry_checks_everything_before_it_sends():
    b = _body(_driver(), "int i1pro2_cq_lights_second_pass(void *pp) {")
    send = b.index("cq_lights_send(p, CQ_LIGHTS_BLUE")
    guard = b[:send]
    for need in ("cq_lights_m(p)", "!m->cq_lights_signals", "!m->cq_lights_reading",
                 "cq_lights_trigger_pending(m)", "cq_lights_pressed(m)",
                 "i1pro2_cq_dual_phase(pp) != CQ_DUAL_PHASE_UV",
                 "!i1pro2_cq_dual_uv_pass_ready(pp)",
                 "m->cq_lights_prog == CQ_LIGHTS_BLUE"):
        assert need in guard, need
    assert b.count("cq_lights_send(") == 1


def test_the_vendor_script_holds_the_same_block():
    script = (ROOT / "scripts" / "vendor_instlib.py").read_text(encoding="utf-8")
    for s in ("int i1pro2_cq_lights_second_pass(void *pp) {", "int i1pro2_cq_lights_quiet_ms = -1;",
              "#define CQ_LIGHTS_BLUE     7"):
        assert s in script and s in _driver()


# ---------------------------------------------------------------------------
# The helper (native/chartread_helper)
# ---------------------------------------------------------------------------
def _helper() -> str:
    return (HELPER_SRC / "chromiq_chartread.c").read_text(encoding="utf-8",
                                                          errors="surrogateescape")


def test_the_helper_sends_the_blue_550_ms_after_pass_1_from_the_armed_wait():
    h = _helper()
    assert "#define CQ_LIGHTS_BLUE_AFTER_MS 550" in h
    due = _body(h, "static void cq_lights_second_pass_due(void) {")
    assert "cq_lights_signals_on()" in due and "cq_lights_gen != 2" in due
    assert "i1pro2_cq_" not in due                  # only a time, nothing sent
    poll = _body(h, "static void cq_lights_second_pass_poll(void) {")
    assert "i1pro2_cq_lights_second_pass(cq_lights_it)" in poll
    assert poll.index("cq_lights_blue_due = 0;") < poll.index("i1pro2_cq_lights_second_pass(")
    over = _body(h, "static void cq_lights_second_pass_over(void) {")
    assert "i1pro2_cq_" not in over and '\\"why\\":\\"early\\"' in over
    # from the armed wait only, where no key is waiting
    k = h.index("cq_lights_second_pass_poll();\t/* 4.3.52")
    assert "if (purp == inst_armed && c == CQ_KEY_NONE)" in h[k - 80:k]


def test_the_dual_strip_sets_the_blue_due_only_where_pass_2_is_asked_for():
    d = (HELPER_SRC / "chromiq_dualdev.c").read_text(encoding="utf-8")
    body = d[d.index("static void cq_dd_strip("):]
    ready = body.index("if (!i1pro2_cq_dual_uv_pass_ready(it)) {")
    ask = body.index('"{\\"event\\":\\"dual_pass\\"')
    due = body.index("cq_lights_second_pass_due();")
    loop = body.index("rv2 = it->read_strip(it, \"STRIP\"")
    over = body.index("cq_lights_second_pass_over();")
    assert ready < ask < due < loop < over
    assert body.count("cq_lights_second_pass_due();") == 1


def test_the_quiet_flag_takes_only_a_whole_number_from_0_to_10000():
    h = _helper()
    k = h.index('strcmp(argv[ai], "--lights-quiet-ms") == 0')
    block = h[k:k + 900]
    assert "strtol(argv[ai + 1], &end, 10)" in block
    assert "*end == '\\0'" in block and "v >= 0 && v <= 10000" in block
    assert "eat = 2;" in block
    s = h.index("i1pro2_cq_lights_quiet_ms = cq_lights_quiet_ms;")
    assert s < h.index("if (!(cq_lights_gen == 3 ? i1pro3_cq_lights_begin(it)", s)


def test_the_helper_names_the_new_abilities_and_build():
    h = _helper()
    assert '\\"lights_quiet\\",\\"i1pro2_dual_blue\\"' in h
    ext = (HELPER_SRC / "chromiq_ext.h").read_text(encoding="utf-8")
    assert '"chromiq-chartread 2026-11-20a ' in ext
    assert "+conditions-kept+lights-quiet+i1pro2-dual-blue\"" in ext


def test_the_bundled_helper_is_this_build():
    exe = ROOT / "native" / "chromiq-chartread"
    if not exe.is_file():
        pytest.skip("no bundled helper in this checkout")
    data = exe.read_bytes()
    assert b"chromiq-chartread 2026-11-20a " in data
    assert b'"why\\":\\"early\\"' in data or b'"why":"early"' in data


# ---------------------------------------------------------------------------
# The app: the setting, the command line, the log
# ---------------------------------------------------------------------------
def test_the_setting_default_and_range():
    from core.settings import DEFAULTS
    from core import i1pro2_lights_quiet as lq
    assert DEFAULTS["i1pro2_lights_quiet_s"] == 2.1 == lq.DEFAULT_S
    assert (lq.MIN_S, lq.MAX_S, lq.DEFAULT_MS) == (0.0, 10.0, 2100)
    assert lq.to_ms(2.1) == 2100 and lq.to_ms(0) == 0 and lq.to_ms(0.4) == 400
    assert lq.to_ms(10) == 10000
    for bad in (-0.1, 10.1, "x", None, float("nan")):
        assert lq.to_ms(bad) == 2100, bad


def test_the_session_header_names_the_setting():
    from core.beta_registry import BETA_SUB_OPTIONS, LOGGED_KEYS
    assert "i1pro2_lights_quiet_s" in BETA_SUB_OPTIONS
    assert "i1pro2_lights_quiet_s" in LOGGED_KEYS


class _Runner:
    def __init__(self):
        self.calls = []
        self.is_running = False

    def run(self, tool, args, cwd, on_line=None, on_finish=None, use_pty=False):
        self.calls.append((str(tool), list(args)))

    def set_kill_courtesy(self, line):
        pass

    def write_stdin(self, text):
        pass


CAPS = {"i1pro2_lights", "lights_signals", "lights_during_reading", "lights_quiet"}


def _args(tmp_path, monkeypatch, *, lights=True, quiet=2.1, caps=CAPS):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps", lambda helper=None: frozenset(caps))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port", lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      engine_i1pro2_lights=lights, engine_lights_signals=True,
                      engine_lights_quiet_s=quiet)
    m.start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1], m


def test_the_default_keeps_the_command_line(qapp, tmp_path, monkeypatch):
    args, _m = _args(tmp_path, monkeypatch, quiet=2.1)
    assert "--i1pro2-lights" in args and "--lights-quiet-ms" not in args
    off, _m = _args(tmp_path, monkeypatch, lights=False, quiet=0.0)
    assert "--lights-quiet-ms" not in off and "--i1pro2-lights" not in off


@pytest.mark.parametrize("quiet,ms", [(0.0, "0"), (0.4, "400"), (10.0, "10000")])
def test_another_value_is_passed_in_ms(qapp, tmp_path, monkeypatch, quiet, ms):
    base, _m = _args(tmp_path, monkeypatch, quiet=2.1)
    args, m = _args(tmp_path, monkeypatch, quiet=quiet)
    k = args.index("--lights-quiet-ms")
    assert args[k + 1] == ms
    assert args[:k] + args[k + 2:] == base
    assert m._lights_quiet_ms == int(ms)


def test_a_helper_without_the_flag_is_not_given_it(qapp, tmp_path, monkeypatch):
    args, m = _args(tmp_path, monkeypatch, quiet=0.4, caps=CAPS - {"lights_quiet"})
    assert "--lights-quiet-ms" not in args and m._lights_quiet_ms == 2100


def test_the_start_line_names_the_quiet_time():
    src = (ROOT / "workflow" / "measure_log.py").read_text(encoding="utf-8")
    assert "lights_quiet_s=lights_quiet_s," in src
    mm = (ROOT / "workflow" / "measure_manager.py").read_text(encoding="utf-8")
    assert "lights_quiet_s=(getattr(self, \"_lights_quiet_ms\"" in mm


def test_the_start_line_is_written_with_it(caplog, tmp_path):
    from types import SimpleNamespace
    from workflow.measure_log import log_start
    p = SimpleNamespace(ti1_path=tmp_path / "c.ti1", patch_by_patch=False, extra_args=[],
                        instrument=1, high_res=False, resume=False)
    with caplog.at_level("INFO"):
        log_start(p, reader="engine", lights=True, lights_quiet_s=0.4)
    assert any("measure start:" in r.getMessage() and "lights_quiet_s=0.4" in r.getMessage()
               for r in caplog.records)


def _events(qapp, evs, quiet_ms=2100):
    from workflow.measure_manager import MeasureManager
    m = MeasureManager(_Runner())
    m._lights_quiet_ms = quiet_ms
    m._lights_held_said = False
    m._lights_option = True
    out = []
    for ev in evs:
        m._on_lights_event(ev, out.append)
    return out


def test_the_blue_is_said_in_the_measure_log_and_the_app_log(qapp, caplog):
    with caplog.at_level("INFO"):
        out = _events(qapp, [{"event": "lights", "sent": "blue"}])
    assert out == ["[Engine] Instrument lights (beta): blue. The second pass of this strip is due."]
    assert any("lights: sent=blue" in r.getMessage() and "second_pass_due" in r.getMessage()
               for r in caplog.records)


def test_a_skipped_blue_goes_to_the_app_log_only(qapp, caplog):
    with caplog.at_level("INFO"):
        out = _events(qapp, [{"event": "lights", "second_pass": "skipped", "why": "early"}])
    assert out == []
    assert any("second_pass=skipped" in r.getMessage() and "why=early" in r.getMessage()
               for r in caplog.records)


def test_the_wait_is_said_with_the_users_value(qapp):
    out = _events(qapp, [{"event": "lights", "held_ms": 300}], quiet_ms=400)
    assert len(out) == 1 and "0.4 s" in out[0] and "Preferences > Beta" in out[0]
    default = _events(qapp, [{"event": "lights", "held_ms": 300}])
    assert "about two seconds" in default[0]


def test_the_session_line_says_the_quiet_time_in_use(qapp, caplog):
    with caplog.at_level("INFO"):
        _events(qapp, [{"event": "lights", "active": True, "instrument": "i1pro2",
                        "signals": True, "during_reading": "off", "firmware": 634,
                        "quiet_ms": 400}])
    assert any("lights: instrument=i1pro2 quiet_ms=400 quiet_default=off" in r.getMessage()
               for r in caplog.records)


@pytest.fixture
def dialog(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "p.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    yield dlg, s
    dlg.deleteLater()


def test_preferences_greys_the_wait_until_the_lights_are_on(dialog):
    dlg, _s = dialog
    assert dlg._lights_quiet_spin.isEnabled() is False
    assert dlg._lights_quiet_spin.value() == pytest.approx(2.1)
    assert (dlg._lights_quiet_spin.minimum(), dlg._lights_quiet_spin.maximum()) == (0.0, 10.0)
    dlg._i1pro2_lights_check.setChecked(True)
    assert dlg._lights_quiet_spin.isEnabled() is True
    assert dlg._lights_quiet_label.buddy() is dlg._lights_quiet_spin


def test_preferences_saves_the_wait(dialog):
    dlg, s = dialog
    dlg._i1pro2_lights_check.setChecked(True)
    dlg._lights_quiet_spin.setValue(0.4)
    dlg._save_and_close()
    assert s.get("i1pro2_lights_quiet_s") == pytest.approx(0.4)


def test_the_help_names_the_recorded_numbers_and_the_risk():
    from ui.dialogs.settings_dialog import (i1pro2_lights_help, i1pro2_lights_quiet_help,
                                            i1pro2_lights_quiet_note)
    note = i1pro2_lights_quiet_note()
    assert "2.1 s" in note and "0.37 s" in note and "0.46 s" in note and "app log" in note
    h = i1pro2_lights_quiet_help()
    for need in ("0.37", "0.46", "0.01", "lost communication", "M1 and M2", "0 to 10 s",
                 "app log"):
        assert need in h, need
    lights = i1pro2_lights_help()
    assert "second pass of this strip is due" in lights
    assert "changes how ChromIQ talks to the instrument" in lights
    assert "left light pulses blue" in lights and "either direction" in lights
