"""A2 + A3 (4.3.50): one app-log line at each measurement start with what is in
effect, and one line per strip as it is decided (hand strip and dual scan),
fed through the manager's own event handler."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from workflow.measure_manager import MeasureManager, MeasureParams


class _Runner:
    is_running = True

    def __init__(self):
        self.sent = []
        self.ran = []

    def write_stdin(self, text):
        self.sent.append(text)

    def run(self, *a, **kw):
        self.ran.append(a)


def _manager():
    m = MeasureManager(_Runner())
    m._engine_active = True
    m._spot_mode = False
    m._is_resume = False
    m._guided_state = "disabled"
    m._safenet_on = True
    from workflow.measure_log import StripLog
    m._strip_log = StripLog()
    return m


def _feed(m, ev):
    m._handle_engine_line(json.dumps(ev), lambda _l: None)


def _patches(strip, n=6):
    k = ord(strip[0]) - 64
    return [{"loc": f"{strip}{i}", "xyz": [10.0 + 9 * ((i * k) % 7), 11.0 + 6 * ((i + k) % 5),
                                            12.0 + 4 * ((i * 3 + k) % 6)]}
            for i in range(1, n + 1)]


def _events(caplog, tag):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith(tag + ":")]


def test_each_strip_gets_one_line_with_its_checks(caplog):
    m = _manager()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        _feed(m, {"event": "strip_ready", "strip": "A"})
        _feed(m, {"event": "strip_read", "strip": "A", "worst_de": 1.25,
                  "patches": _patches("A")})
        _feed(m, {"event": "strip_ready", "strip": "B"})
        _feed(m, {"event": "error", "kind": "misread", "detail": "too few patches"})
        _feed(m, {"event": "strip_ready", "strip": "B"})
        _feed(m, {"event": "strip_read", "strip": "B", "worst_de": 0.5,
                  "patches": _patches("B")})
    lines = _events(caplog, "strip")
    assert len(lines) == 3, lines
    a, b1, b2 = lines
    assert a.startswith("strip: id=A attempt=1 result=kept mode=strip worst_de=1.25 patches=6")
    for word in ("engine_net=ok", "slip=ok", "read_twice=ok", "took_s="):
        assert word in a, a
    assert b1.startswith("strip: id=B attempt=1 result=refused reason=misread")
    assert 'detail="too few patches"' in b1
    assert b2.startswith("strip: id=B attempt=2 result=kept")


def test_a_strip_the_engine_net_flags_is_asked(caplog):
    m = _manager()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        _feed(m, {"event": "strip_ready", "strip": "C"})
        _feed(m, {"event": "strip_read", "strip": "C", "worst_de": 9.0, "misaligned": 1,
                  "patches": _patches("C")})
    (c,) = _events(caplog, "strip")
    assert "result=asked" in c and "engine_net=misaligned engine_net_offset=1" in c


def test_a_dual_scan_strip_carries_its_pass_pairing(caplog):
    m = _manager()
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        _feed(m, {"event": "strip_ready", "strip": "D"})
        _feed(m, {"event": "dual_pass_result", "what": "uv", "strip": "D", "ok": True,
                  "why": "", "uv_readings": 40, "fewest_per_patch": 5, "uv_triggers": 1,
                  "volts": [5000, 4990], "pairing": "by_time", "calibrate": False})
        _feed(m, {"event": "strip_read", "strip": "D", "worst_de": 1.0,
                  "patches": _patches("D")})
    (d,) = _events(caplog, "strip")
    assert "dual_pass.ok=on" in d and "dual_pass.pairing=by_time" in d
    assert "dual_pass.uv_readings=40" in d


def test_a_skip_is_a_line(caplog):
    m = _manager()
    m._dual_strip_now = "E"
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        m.skip_current_strip()
    (e,) = _events(caplog, "strip")
    assert e.startswith("strip: id=E attempt=1 result=skipped by=person")


def test_the_measurement_start_line_says_what_is_in_effect(caplog, tmp_path):
    from workflow.measure_log import log_start
    ti2 = tmp_path / "T.ti2"
    ti2.write_text('CTI2\nTARGET_INSTRUMENT "X-Rite i1Pro 2"\nSTEPS_IN_PASS "18"\n'
                   'PASSES_IN_STRIPS2 "18,18,3"\nNUMBER_OF_SETS 702\nBEGIN_DATA\n',
                   encoding="utf-8")
    p = MeasureParams(ti1_path=tmp_path / "T.ti1", high_res=True, extra_args="-F M1",
                      engine_safenet=True)
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        log_start(p, reader="engine", helper_build="b1", ruler=True, dual="on",
                  conditions="on")
    (s,) = _events(caplog, "measure start")
    for word in ("reader=engine", "helper_build=b1", "chart=T.ti2", "patches=702",
                 "pages=3", "strips=39", "patches_per_strip=18", "mode=strips",
                 "filter=M1", "dual_scan=on", "conditions=on", "ruler=on",
                 "misaligned_check=on", "high_res=on", "resume=off", "run_kind=profile",
                 "run_dir="):
        assert word in s, (word, s)


def test_the_manager_writes_the_start_line_without_starting_the_helper(caplog, tmp_path,
                                                                      monkeypatch):
    import workflow.chartread_engine as ce
    called = []
    monkeypatch.setattr(ce, "helper_caps", lambda *a, **k: called.append(a) or frozenset())
    m = MeasureManager(_Runner())
    m._log_measure_start  # exists
    m._dual_requested = False
    m._lights_option = False
    m._ruler = None
    p = MeasureParams(ti1_path=tmp_path / "T.ti1", engine_helper=tmp_path / "h")
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        m._log_measure_start(p, ["--json", "-v"])
    assert not called
    (s,) = _events(caplog, "measure start")
    assert "reader=engine" in s and "conditions=off" in s
