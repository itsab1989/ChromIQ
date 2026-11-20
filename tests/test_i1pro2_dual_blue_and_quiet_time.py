"""4.3.52: the i1Pro 2 lights Beta's blue before the return pass of a dual scan,
and the quiet time before a reading as a setting of its own.

(This first commit: the setting on the app side; the driver, the helper
and the blue follow in the next.)

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

