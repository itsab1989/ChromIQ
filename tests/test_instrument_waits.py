"""4.3.53: the waits around an i1Pro / i1Pro 2 reading are values the app passes.

The owner, 2026-11-20: "for the waiting times just make it so it does not take a
day to change them again if the times then are too short", then: "repurpose the
one waiting time option to all of the waiting times ... so they can be changed by
the users directly".

The driver side (each argument changes only its wait, no byte; absent = 4.3.52,
also its timing) is proved on the fake USB layer in
tests/test_i1pro2_dual_blue_and_quiet_time.py (the "4352" / "4353" tests). Here:
the one table, the helper's parsing, the command line, the settings keys, the
Preferences fields, the log lines, and that no number has a second copy.
"""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HELPER_SRC = ROOT / "native" / "chartread_helper"
INSTLIB = ROOT / "native" / "instlib"


def _iw():
    from core import instrument_waits
    return instrument_waits


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------
def test_the_defaults_are_4_3_52s_values_and_the_helpers_fallbacks():
    """No behaviour change in 4.3.53: each default equals the compiled value
    the helper keeps when it is not given the argument."""
    iw = _iw()
    c = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="surrogateescape")
    h = (HELPER_SRC / "chromiq_chartread.c").read_text(encoding="utf-8", errors="surrogateescape")
    compiled = {
        "lights_quiet": int(re.search(r"^#define CQ_LIGHTS_QUIET_MS\s+(\d+)", c, re.M).group(1)),
        "blue_quiet": int(re.search(r"^#define CQ_LIGHTS_BLUE_QUIET_MS (\d+)", c, re.M).group(1)),
        "lamp_off": int(re.search(r"^#define LAMP_OFF_TIME (\d+)", c, re.M).group(1)),
        "blue_after": int(re.search(r"^#define CQ_LIGHTS_BLUE_AFTER_MS (\d+)", h, re.M).group(1)),
        # after 4.3.54 (the owner's decision of 2026-11-21): the i1Pro 2's own, a NEW value
        # (i1Profiler's 1.059 s rounded up), in step with its Python default
        "lamp_off_i1pro2": int(re.search(r"^#define CQ_LAMP_OFF_TIME_I1PRO2 (\d+)", c, re.M).group(1)),
    }
    assert compiled == {"lights_quiet": 2100, "blue_quiet": 370, "lamp_off": 1500,
                        "blue_after": 550, "lamp_off_i1pro2": 1100}   # 4.3.52's + the i1Pro 2's
    for w in iw.WAITS:
        assert int(round(w.default_s * 1000)) == compiled[w.name], w.name


def test_every_wait_has_a_key_a_flag_and_a_range():
    iw = _iw()
    assert [w.name for w in iw.WAITS] == ["lights_quiet", "blue_quiet", "blue_after", "lamp_off",
                                          "lamp_off_i1pro2"]
    assert len({w.key for w in iw.WAITS}) == 5 and len({w.flag for w in iw.WAITS}) == 5
    for w in iw.WAITS:
        assert 0 < w.default_s <= w.max_s
    assert (iw.LIGHTS_QUIET.max_s, iw.BLUE_QUIET.max_s, iw.BLUE_AFTER.max_s,
            iw.LAMP_OFF.max_s, iw.I1PRO2_LAMP_OFF.max_s) == (10.0, 10.0, 5.0, 5.0, 5.0)


@pytest.mark.parametrize("value,ms", [(0, 0), (0.37, 370), ("1.06", 1060), (5, 5000)])
def test_a_usable_value_becomes_milliseconds(value, ms):
    iw = _iw()
    assert iw.to_ms(iw.LAMP_OFF, value) == ms


@pytest.mark.parametrize("bad", [-0.01, 5.01, "x", None, float("nan"), ""])
def test_an_unusable_value_gives_the_default(bad):
    iw = _iw()
    assert iw.to_ms(iw.LAMP_OFF, bad) == 1500 and not iw.is_usable(iw.LAMP_OFF, bad)
    assert iw.seconds(iw.BLUE_AFTER, bad) == iw.BLUE_AFTER.default_s


def test_the_helper_arguments_are_every_wait_that_applies_also_at_the_default():
    iw = _iw()
    ms = iw.from_settings(lambda _k, d: d)
    assert ms == {"lights_quiet": 2100, "blue_quiet": 370, "blue_after": 550, "lamp_off": 1500,
                  "lamp_off_i1pro2": 1100}
    assert iw.helper_args(ms, lights=False) == ["--lamp-off-ms", "1500"]
    # after 4.3.54: the i1Pro 2's own, only to a helper that takes it
    assert iw.helper_args(ms, lights=False, i1pro2=True) == [
        "--lamp-off-ms", "1500", "--lamp-off-ms-i1pro2", "1100"]
    assert iw.helper_args(ms, lights=True) == [
        "--lamp-off-ms", "1500", "--lights-quiet-ms", "2100",
        "--lights-blue-quiet-ms", "370", "--lights-blue-after-ms", "550"]


def test_the_settings_keys_are_the_storage(qapp):
    """A tester's one line in the settings file is read; the field and the
    key are the same value."""
    from core.settings import DEFAULTS, AppSettings
    iw = _iw()
    for w in iw.WAITS:
        assert DEFAULTS[w.key] == w.default_s
    s = AppSettings()
    s.set("i1pro_lamp_off_s", "1.06")                 # as a settings file holds it
    s.set("i1pro2_blue_after_s", 9.0)                 # out of range
    try:
        ms = iw.from_settings(s.get)
        assert ms["lamp_off"] == 1060 and ms["blue_after"] == 550
    finally:
        s.set("i1pro_lamp_off_s", iw.LAMP_OFF.default_s)
        s.set("i1pro2_blue_after_s", iw.BLUE_AFTER.default_s)


def test_the_session_header_lists_every_wait():
    from core.beta_registry import BETA_SUB_OPTIONS, LOGGED_KEYS
    for w in _iw().WAITS:
        assert w.key in BETA_SUB_OPTIONS and w.key in LOGGED_KEYS


def test_the_header_line_carries_the_values(qapp):
    from core.session_header import header_lines
    iw = _iw()
    vals = {w.key: w.default_s for w in iw.WAITS}
    vals["i1pro_lamp_off_s"] = 1.06

    class S:
        def get(self, k, d=None):
            return vals.get(k, d)
    line = next(ln for ln in header_lines(S()) if ln.startswith("session: beta_options "))
    assert "i1pro_lamp_off_s=1.06" in line and "i1pro2_blue_quiet_s=0.37" in line
    assert "i1pro2_blue_after_s=0.55" in line and "i1pro2_lights_quiet_s=2.1" in line


# ---------------------------------------------------------------------------
# No second copy of a number
# ---------------------------------------------------------------------------
_PY_SITES = ["core/settings.py", "workflow/measure_manager.py",
             "workflow/measure_log.py", "ui/tabs/tab_measure.py", "core/beta_registry.py",
             "core/session_header.py"]


def _numbers(path: Path, wanted) -> "list[tuple[int, str]]":
    src = path.read_text(encoding="utf-8")
    return [(t.start[0], t.string) for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type == tokenize.NUMBER and t.string in wanted]


def test_no_python_site_holds_a_second_copy_of_a_default():
    wanted = ("2.1", "2100", "0.37", "370", "0.55", "550", "1.5", "1500")
    for rel in _PY_SITES:
        found = _numbers(ROOT / rel, wanted)
        if rel in ("workflow/measure_manager.py", "ui/tabs/tab_measure.py"):
            # two big files with unrelated 1.5 s timers: there, every line that
            # holds the lamp's number must not be about the waits
            src = (ROOT / rel).read_text(encoding="utf-8").splitlines()
            found = [(ln, n) for ln, n in found
                     if n not in ("1.5", "1500") or "wait" in src[ln - 1].lower()
                     or "lamp" in src[ln - 1].lower()]
        assert found == [], rel
    own = [n for _l, n in _numbers(ROOT / "core" / "instrument_waits.py", wanted)]
    # the four defaults, then i1Profiler's recorded 0.37 s (RECORDED_BLUE_QUIET_LOW_S);
    # the i1Pro 2's lamp wait (1.10) is not one of the numbers looked for
    assert own == ["2.1", "0.37", "0.55", "1.5", "0.37"], own
    # 4.3.52's module keeps only i1Profiler's recorded 0.37 s (a measurement, not a default)
    lq = (ROOT / "core" / "i1pro2_lights_quiet.py").read_text(encoding="utf-8")
    assert [n for _l, n in _numbers(ROOT / "core" / "i1pro2_lights_quiet.py", wanted)] == ["0.37"]
    assert "\nRECORDED_HAND_MIN_S = 0.37\n" in lq


def test_the_settings_dialog_takes_every_default_and_range_from_the_table():
    src = (ROOT / "ui" / "dialogs" / "settings_dialog.py").read_text(encoding="utf-8")
    body = src[src.index("    def _add_wait_row("):]
    body = body[:body.index("\n    def ", 10)]
    assert "spin.setRange(_iw.MIN_S, wait.max_s)" in body
    assert "spin.setValue(wait.default_s)" in body
    assert _numbers_in_text(body, ("0.37", "0.55", "1.5", "370", "550", "1500")) == []


def _numbers_in_text(src: str, wanted):
    return [t.string for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type == tokenize.NUMBER and t.string in wanted]


def test_the_native_sources_hold_each_compiled_value_once():
    c = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="surrogateescape")
    h = (HELPER_SRC / "chromiq_chartread.c").read_text(encoding="utf-8", errors="surrogateescape")
    assert len(re.findall(r"^#define CQ_LIGHTS_BLUE_QUIET_MS ", c, re.M)) == 1
    assert len(re.findall(r"^#define LAMP_OFF_TIME ", c, re.M)) == 1
    assert len(re.findall(r"^#define CQ_LIGHTS_BLUE_AFTER_MS ", h, re.M)) == 1
    # the lamp wait is read only through CQ_LAMP_OFF_TIME (no bare use left)
    ccode = re.sub(r"/\*.*?\*/", "", c, flags=re.S)
    assert len(re.findall(r"\bLAMP_OFF_TIME\b", ccode)) == 2     # the define + the fallback
    assert len(re.findall(r"\bCQ_LAMP_OFF_TIME\b", ccode)) == 4  # its define + the three uses
    lights = c[c.index("#define CQ_LIGHTS_UNUSED"):c.index("CHROMIQ PATCH: the ruler check (Preferences")]
    code = re.sub(r"/\*.*?\*/", "", lights, flags=re.S)
    assert re.findall(r"\b370\b", code) == ["370"]       # only the define
    hcode = re.sub(r"/\*.*?\*/", "", h, flags=re.S)
    assert re.findall(r"\b550\b", hcode) == ["550"]


def test_the_vendor_script_holds_the_same_changes():
    script = (ROOT / "scripts" / "vendor_instlib.py").read_text(encoding="utf-8")
    assert "I1PRO_IMP_C_WAITS_453" in script and "I1PRO_IMP_H_WAITS_453" in script
    c = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="surrogateescape")
    for s in ("int i1pro_cq_lamp_off_ms = -1;", "int i1pro2_cq_lights_blue_quiet_set_ms = -1;",
              "#define CQ_LAMP_OFF_I1PRO ((i1pro_cq_lamp_off_ms >= 0 && i1pro_cq_lamp_off_ms <= 5000)",
              "int i1pro2_cq_lamp_off_ms = -1;", "#define CQ_LAMP_OFF_TIME_I1PRO2 1100",
              "#define CQ_LAMP_OFF_TIME ((p)->dtype != instI1Pro2 ? CQ_LAMP_OFF_I1PRO"):
        assert s in c and s.replace('"', '\\"') in script


# ---------------------------------------------------------------------------
# The helper's parsing (compiled from the shipped text) and its build
# ---------------------------------------------------------------------------
_PARSE_HARNESS = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
static unsigned int now_ms = 1000;
static unsigned int msec_time(void) { return now_ms; }
static int cq_lights_gen = 2;
static int cq_lights_signals_on(void) { return 1; }
static int i1pro2_cq_lights_second_pass(void *pp) { (void)pp; printf("SEND %u\n", now_ms); return 1; }
static void *cq_lights_it = (void *)1;
static void cq_emit_raw(const char *fmt, ...) {
	va_list a; va_start(a, fmt); vprintf(fmt, a); va_end(a); printf("\n");
}
@@SOURCE@@
static void due_at(void) {
	now_ms = 1000; cq_lights_second_pass_due(1);
	for (now_ms = 1000; now_ms <= 7000; now_ms += 10) cq_lights_second_pass_poll();
	cq_lights_second_pass_over();
}
int main(void) {
	printf("default %d\n", cq_lights_blue_after_now()); due_at();
	cq_lights_blue_after_ms = cq_wait_arg("--lights-blue-after-ms", "200", 5000);
	printf("200 %d\n", cq_lights_blue_after_now()); due_at();
	cq_lights_blue_after_ms = cq_wait_arg("--lights-blue-after-ms", "abc", 5000);
	printf("abc %d\n", cq_lights_blue_after_now());
	cq_lights_blue_after_ms = cq_wait_arg("--lights-blue-after-ms", "5001", 5000);
	printf("5001 %d\n", cq_lights_blue_after_now());
	printf("q %d %d %d\n", cq_wait_arg("--lights-blue-quiet-ms", "0", 10000),
	       cq_wait_arg("--lights-blue-quiet-ms", "-1", 10000),
	       cq_wait_arg("--lamp-off-ms", "1060", 5000));
	printf("ignored [%s]\n", cq_waits_ignored);
	return 0;
}
"""


def test_the_helper_takes_a_whole_number_in_range_and_names_what_it_did_not(tmp_path):
    cc = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if cc is None or sys.platform == "win32":
        pytest.skip("no C compiler here")
    h = (HELPER_SRC / "chromiq_chartread.c").read_text(encoding="utf-8", errors="surrogateescape")
    a = h.index("#define CQ_LIGHTS_BLUE_AFTER_MS 550")
    k = h.index("static void cq_lights_second_pass_over(void) {")
    src = h[a:h.index("\n}\n", k) + 3]
    c = tmp_path / "waits_harness.c"
    c.write_text(_PARSE_HARNESS.replace("@@SOURCE@@", src), encoding="utf-8")
    exe = tmp_path / "waits_harness"
    r = subprocess.run([cc, "-std=c99", "-Wall", "-Werror", "-Wno-unused-function", "-Wno-unused-variable",
                        "-o", str(exe), str(c)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=120)
    assert r.returncode == 0, r.stderr
    out = subprocess.run([str(exe)], capture_output=True, text=True, encoding="utf-8",
                         timeout=60).stdout.splitlines()
    assert out == [
        "default 550", "SEND 1550",           # absent: 4.3.52's 550 ms
        "200 200", "SEND 1200",               # passed: only that wait changes
        "abc 550", "5001 550",                # not taken: the compiled value
        "q 0 -1 1060",
        "ignored [--lights-blue-after-ms --lights-blue-after-ms --lights-blue-quiet-ms]",
    ], out


def test_the_helper_says_the_waits_only_when_it_was_given_any():
    h = (HELPER_SRC / "chromiq_chartread.c").read_text(encoding="utf-8", errors="surrogateescape")
    k = h.index('cq_emit_raw("{\\"event\\":\\"waits\\"')
    assert "if (cq_json && cq_waits_given)" in h[k - 200:k]
    assert h.count('"--lamp-off-ms"') == 1 and "i1pro_cq_lamp_off_ms = cq_lamp_off_set_ms;" in h
    s = h.index("i1pro2_cq_lights_blue_quiet_set_ms = cq_lights_blue_quiet_set_ms;")
    assert s < h.index("if (!(cq_lights_gen == 3 ? i1pro3_cq_lights_begin(it)", s)
    assert '\\"instrument_waits\\"' in h      # 4.3.54: i1pro2_dual_fresh_start follows it


def test_the_bundled_helper_takes_the_waits():
    exe = ROOT / "native" / "chromiq-chartread"
    if not exe.is_file():
        pytest.skip("no bundled helper in this checkout")
    data = exe.read_bytes()
    assert b"chromiq-chartread 2026-11-24b " in data and b"+instrument-waits" in data
    for s in (b"--lamp-off-ms", b"--lights-blue-quiet-ms", b"--lights-blue-after-ms",
              b"instrument_waits"):
        assert s in data, s


# ---------------------------------------------------------------------------
# The command line and the log
# ---------------------------------------------------------------------------
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


CAPS = {"i1pro2_lights", "lights_signals", "lights_during_reading", "lights_quiet",
        "instrument_waits"}


def _args(tmp_path, monkeypatch, *, lights=True, caps=CAPS, waits=None, quiet=None):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps", lambda helper=None: frozenset(caps))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port", lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    kw = {}
    if quiet is not None:
        kw["engine_lights_quiet_s"] = quiet
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1",
                      engine_helper=tmp_path / "chromiq-chartread",
                      engine_i1pro2_lights=lights, engine_lights_signals=True,
                      engine_waits_ms=waits, **kw)
    m.start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1], m


def _flag(args, flag):
    return args[args.index(flag) + 1] if flag in args else None


def test_every_wait_reaches_the_helper_at_its_default(qapp, tmp_path, monkeypatch):
    args, m = _args(tmp_path, monkeypatch)
    assert (_flag(args, "--lamp-off-ms"), _flag(args, "--lights-quiet-ms"),
            _flag(args, "--lights-blue-quiet-ms"), _flag(args, "--lights-blue-after-ms")) == \
        ("1500", "2100", "370", "550")
    assert m._waits_ms == {"lights_quiet": 2100, "blue_quiet": 370, "blue_after": 550,
                           "lamp_off": 1500}


def test_a_changed_wait_changes_only_its_own_argument(qapp, tmp_path, monkeypatch):
    base, _m = _args(tmp_path, monkeypatch)
    args, _m = _args(tmp_path, monkeypatch, waits={"lamp_off": 1060})
    k = base.index("--lamp-off-ms")
    assert args[:k + 1] + args[k + 2:] == base[:k + 1] + base[k + 2:] and args[k + 1] == "1060"
    args, _m = _args(tmp_path, monkeypatch, quiet=0.4)
    assert _flag(args, "--lights-quiet-ms") == "400" and args.count("--lights-quiet-ms") == 1


def test_without_the_lights_only_argylls_lamp_wait_is_passed(qapp, tmp_path, monkeypatch):
    args, m = _args(tmp_path, monkeypatch, lights=False)
    assert _flag(args, "--lamp-off-ms") == "1500"
    for f in ("--lights-quiet-ms", "--lights-blue-quiet-ms", "--lights-blue-after-ms"):
        assert f not in args
    assert m._waits_ms == {"lamp_off": 1500}


def test_an_older_helper_gets_4_3_52s_command_line(qapp, tmp_path, monkeypatch):
    args, m = _args(tmp_path, monkeypatch, caps=CAPS - {"instrument_waits"})
    for f in ("--lamp-off-ms", "--lights-quiet-ms", "--lights-blue-quiet-ms",
              "--lights-blue-after-ms"):
        assert f not in args
    assert m._waits_ms is None


def test_the_start_line_names_every_wait(caplog, tmp_path):
    from types import SimpleNamespace
    from workflow.measure_log import log_start
    p = SimpleNamespace(ti1_path=tmp_path / "c.ti1", patch_by_patch=False, extra_args=[],
                        instrument=1, high_res=False, resume=False)
    with caplog.at_level("INFO"):
        log_start(p, reader="engine", lights=True, lights_quiet_s=2.1,
                  waits_ms={"lights_quiet": 2100, "blue_quiet": 370, "blue_after": 550,
                            "lamp_off": 1060})
        log_start(p, reader="engine", waits_ms=None)
    msgs = [r.getMessage() for r in caplog.records if "measure start:" in r.getMessage()]
    assert ("lights_quiet_s=2.1 blue_quiet_s=0.37 blue_after_s=0.55 "
            "lamp_off_s=1.06(changed)") in msgs[0]
    assert "waits=helper_default" in msgs[1]


def test_the_helpers_waits_event_goes_to_the_app_log(qapp, caplog):
    import json
    from workflow.measure_manager import MeasureManager
    m = MeasureManager(_Runner())
    out = []
    ev = {"event": "waits", "lamp_off_ms": 1060, "blue_quiet_ms": -1, "blue_after_ms": 550,
          "ignored": "--lights-blue-quiet-ms"}
    with caplog.at_level("INFO"):
        m._handle_engine_line(json.dumps(ev), out.append)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("helper waits" in s and "lamp_off_ms=1060" in s and "blue_after_ms=550" in s
               and "--lights-blue-quiet-ms" in s for s in msgs), msgs
    assert any("did not take --lights-blue-quiet-ms" in s for s in msgs)
    assert out == []                                  # the Measure log says nothing


def test_the_measure_tab_reads_the_settings_for_every_wait():
    src = (ROOT / "ui" / "tabs" / "tab_measure.py").read_text(encoding="utf-8")
    assert "p.engine_waits_ms = _iw.from_settings(self._settings.get)" in src


# ---------------------------------------------------------------------------
# Preferences > Beta
# ---------------------------------------------------------------------------
@pytest.fixture
def dialog(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    d = SettingsDialog(s)
    yield d, s
    d.deleteLater()


def test_each_field_is_preset_to_its_default(dialog):
    d, _s = dialog
    iw = _iw()
    for w in iw.WAITS:
        spin = d._wait_fields[w.key][1]
        assert spin.value() == pytest.approx(w.default_s)
        assert spin.minimum() == 0.0 and spin.maximum() == w.max_s
        assert spin.decimals() == 2 and spin.singleStep() == pytest.approx(0.05)


def _set_state(d, *, lights, signals, cond, dual):
    d._i1pro2_lights_check.setChecked(lights)
    d._lights_signals_combo.setCurrentIndex(1 if signals else 0)
    d._i1pro3_conditions_check.setChecked(cond)
    d._dual_follows()
    d._i1pro2_dual_check.setChecked(dual)
    d._lights_choices_follow()


@pytest.mark.parametrize("lights,signals,cond,dual,quiet,blue", [
    (False, True, True, True, False, False),
    (True, False, True, True, True, False),     # ready light only: no blue light is sent
    (True, True, True, False, True, False),     # no dual scan
    (True, True, False, True, True, False),     # the dual scan's own switch is off
    (True, True, True, True, True, True),
])
def test_greying_follows_meaning_only(dialog, lights, signals, cond, dual, quiet, blue):
    d, _s = dialog
    iw = _iw()
    _set_state(d, lights=lights, signals=signals, cond=cond, dual=dual)
    assert d._wait_fields[iw.LIGHTS_QUIET.key][1].isEnabled() is quiet
    assert d._wait_fields[iw.BLUE_QUIET.key][1].isEnabled() is blue
    assert d._wait_fields[iw.BLUE_AFTER.key][1].isEnabled() is blue
    assert d._wait_fields[iw.LAMP_OFF.key][1].isEnabled()      # every i1Pro 2 reading


def test_a_field_saves_into_its_settings_key(dialog):
    d, s = dialog
    iw = _iw()
    d._wait_fields[iw.LAMP_OFF.key][1].setValue(1.06)
    d._wait_fields[iw.BLUE_AFTER.key][1].setValue(0.6)
    try:
        d._save_and_close()
        assert s.get(iw.LAMP_OFF.key) == pytest.approx(1.06)
        assert s.get(iw.BLUE_AFTER.key) == pytest.approx(0.6)
    finally:
        for w in iw.WAITS:
            s.set(w.key, w.default_s)


def test_text_that_cannot_be_taken_is_said_under_the_field(dialog):
    d, _s = dialog
    iw = _iw()
    _label, spin, _tip, back = d._wait_fields[iw.LAMP_OFF.key]
    d.show()
    spin.lineEdit().setFocus()
    spin.lineEdit().clear()
    spin.lineEdit().textEdited.emit("")
    spin.editingFinished.emit()
    assert not back.isHidden() and "0 to 5 s" in back.text(), back.text()
    d.hide()


def test_the_help_says_purpose_vendor_before_and_risk():
    from ui.dialogs import settings_dialog as sd
    b = sd.i1pro2_blue_quiet_help()
    for need in ("0.37 to 1.39 s", "0.31 s", "4.3.52 waited 0.37 s", "M1 and M2 end",
                 "M0 goes on", "**Default:** 0.37 s", "0 to 10 s"):
        assert need in b, need
    a = sd.i1pro2_blue_after_help()
    for need in ("0.53 to 0.68 s", "after 0.55 s", "no reading is lost", "**Default:** 0.55 s",
                 "0 to 5 s"):
        assert need in a, need
    # after 4.3.54 (the owner's decision of 2026-11-21): two fields. The i1Pro's: ArgyllCMS's
    # value, no vendor recording evaluated; the i1Pro 2's: i1Profiler's 1.06 s, 4.3.54's 1.5 s,
    # the tester's gaps from 1.03 s, the dual scan's second pass
    lamp = sd.i1pro_lamp_off_help()
    for need in ("to make sure the lamp is dark for the dark measurement",
                 "1.5 s, ArgyllCMS's own value", "No recording of X-Rite's software",
                 "original i1Pro", "EFI ES-1000", "The i1Pro 2 has its own field below",
                 "readings may be slightly wrong", "you cannot see it", "without a warning",
                 "**Default:** 1.5 s",
                 "i1iO table when an original i1Pro sits in its arm"):
        assert need in lamp, need
    lamp2 = sd.i1pro2_lamp_off_help()
    for need in ("i1Pro 2", "EFI ES-2000", "i1Basic Pro 2", "about 1.06 s",
                 "0.11 to 0.18 s", "up to ChromIQ 4.3.54 the i1Pro 2 waited 1.5 s",
                 "The default is now 1.1 s", "1.03 s to 2.24 s", "showed no effect",
                 "never started sooner than about 1 s after the lamp went off",
                 "a wait below about 1 s does not make a dual scan faster",
                 "whether or not any Beta option is on",
                 "It does not reach the table's rows", "1.07 s", "0.17 s",
                 "readings may be slightly wrong", "**Default:** 1.1 s", "0 to 5 s"):
        assert need in lamp2, need
    assert "can be slightly wrong" not in lamp2
    assert "can be slightly wrong" not in lamp and "in every version" not in lamp
    assert "ArgyllCMS's lamp wait below holds it" in b       # S3, in the blue's own help
    q = sd.i1pro2_lights_quiet_help()
    assert "“Dual scan, wait after the blue light”" in q and "always waits" not in q


def test_the_lamp_field_is_its_own_line_not_under_the_lights():
    src = (ROOT / "ui" / "dialogs" / "settings_dialog.py").read_text(encoding="utf-8")
    k = src.index("self._add_wait_row(_beta, _iw.LAMP_OFF, 0,")
    assert "self._add_wait_row(_beta, _iw.BLUE_QUIET, 28," in src[:k]
    assert "self._add_wait_row(_beta, _iw.BLUE_AFTER, 28," in src[:k]
