"""The lamp wait per instrument model (after 4.3.54, the owner's decision of 2026-11-21, "option A").

Two fields: "i1Pro lamp wait" (the original i1Pro rev A to D and rebadged ones), default 1.5 s,
ArgyllCMS's value as before; "i1Pro 2 lamp wait" (the i1Pro 2, ES-2000, i1Basic Pro 2), default
1.10 s, i1Profiler's recorded 1.059 s rounded up. The helper gets both (--lamp-off-ms,
--lamp-off-ms-i1pro2, caps "lamp_off_i1pro2") and the driver picks by model when the wait applies.
Pinned here: the driver's own macro text compiled and run per model and per argument; the default
per model in the app; the migration (stored 1.5, stored another value, nothing stored, already
stored); a typed value wins; old helper + new app and new helper + old app; the app log. Nothing
changes for an i1Pro 3 or any other instrument (they never read this wait).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from core import instrument_waits as iw

ROOT = Path(__file__).resolve().parent.parent
INSTLIB = ROOT / "native" / "instlib"


# ---------------------------------------------------------------- the driver, compiled

_HARNESS = r"""
#include <stdio.h>
typedef enum { instI1Pro = 1, instI1Pro2 = 2, instI1Pro3 = 3 } instType;
typedef struct { instType dtype; } i1pro;
@@DEFINES@@
static unsigned int wait_of(instType t) { i1pro q, *p = &q; q.dtype = t; return CQ_LAMP_OFF_TIME; }
int main(void) {
	int a[] = { -1, 1060, 1300 }, b[] = { -1, 900, 2000 }, i, j;
	for (i = 0; i < 3; i++)
		for (j = 0; j < 3; j++) {
			i1pro_cq_lamp_off_ms = a[i];
			i1pro2_cq_lamp_off_ms = b[j];
			printf("%d %d %u %u\n", a[i], b[j], wait_of(instI1Pro), wait_of(instI1Pro2));
		}
	return 0;
}
"""


def test_the_driver_picks_the_wait_by_model(tmp_path):
    """The macro text of native/instlib/i1pro_imp.c itself, compiled: an original i1Pro waits
    --lamp-off-ms or ArgyllCMS's 1500; an i1Pro 2 waits --lamp-off-ms-i1pro2, else
    --lamp-off-ms (an app of 4.3.53 / 4.3.54 passes one value for both), else 1100."""
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        pytest.skip("no C compiler")
    c = (INSTLIB / "i1pro_imp.c").read_text(encoding="utf-8", errors="surrogateescape")
    a = c.index("#define LAMP_OFF_TIME 1500")
    b = c.index("#define PATCH_CONS_THR", a)
    src = tmp_path / "h.c"
    src.write_text(_HARNESS.replace("@@DEFINES@@", c[a:b]), encoding="utf-8")
    exe = tmp_path / "h"
    subprocess.run([cc, "-o", str(exe), str(src)], check=True, capture_output=True, timeout=120)
    got = {}
    for ln in subprocess.run([str(exe)], check=True, capture_output=True, text=True,
                             timeout=60).stdout.splitlines():
        x, y, w1, w2 = (int(v) for v in ln.split())
        got[(x, y)] = (w1, w2)
    assert got[(-1, -1)] == (1500, 1100)          # neither given: ArgyllCMS's / the i1Pro 2's own
    assert got[(1060, -1)] == (1060, 1060)        # an older app: one value for both, as before
    assert got[(-1, 900)] == (1500, 900)          # the new app: each its own
    assert got[(1300, 2000)] == (1300, 2000)
    assert int(re.search(r"^#define CQ_LAMP_OFF_TIME_I1PRO2 (\d+)", c, re.M).group(1)) == \
        int(round(iw.I1PRO2_LAMP_OFF.default_s * 1000))      # compiled fallback in step


def test_the_i1pro3_and_other_instruments_never_read_this_wait():
    """The wait lives in the i1Pro / i1Pro 2 driver only (i1pro_imp.c); the i1Pro 3 (its own
    i1pro3_imp.c) and the others have no such code."""
    for f in INSTLIB.glob("*.c"):
        if f.name == "i1pro_imp.c":
            continue
        t = f.read_text(encoding="utf-8", errors="surrogateescape")
        assert "i1pro2_cq_lamp_off_ms" not in t and "CQ_LAMP_OFF_TIME" not in t, f.name


# ---------------------------------------------------------------- the app

def test_the_defaults_per_model():
    assert iw.LAMP_OFF.default_s == 1.5 and iw.I1PRO2_LAMP_OFF.default_s == 1.10
    ms = iw.from_settings(lambda _k, d: d)
    assert iw.lamp_wait_for("i1Pro2", ms, i1pro2_taken=True) == ("i1pro2", 1100)
    assert iw.lamp_wait_for("i1Pro", ms, i1pro2_taken=True) == ("i1pro", 1500)
    # a helper without the i1Pro 2's argument: it waits the i1Pro value, as up to 4.3.54
    assert iw.lamp_wait_for("i1Pro2", ms, i1pro2_taken=False) == ("i1pro2(i1pro_value)", 1500)
    for other in ("i1Pro3", "i1Pro3 Plus", "ColorMunki", "Spyder", ""):
        assert iw.lamp_wait_for(other, ms, i1pro2_taken=True) is None, other


def _store(tmp_path, values: dict, schema: int = 35):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    path = str(tmp_path / "s.ini")

    def AS():
        s = AppSettings()
        s._qs = QSettings(path, QSettings.Format.IniFormat)
        return s
    s = AS()
    s._qs.setValue("settings_schema", schema)
    for k, v in values.items():
        s._qs.setValue(k, v)
    s._qs.sync()
    return AS


@pytest.mark.parametrize("values,want_i1pro,want_i1pro2,stored2", [
    ({}, 1.5, 1.10, False),                                         # nothing stored
    ({"i1pro_lamp_off_s": 1.5}, 1.5, 1.10, False),                  # the old default
    ({"i1pro_lamp_off_s": "1.5"}, 1.5, 1.10, False),                # as an ini string
    ({"i1pro_lamp_off_s": 1.2}, 1.2, 1.2, True),                    # somebody's choice: kept
    ({"i1pro_lamp_off_s": 1.2, "i1pro2_lamp_off_s": 0.95}, 1.2, 0.95, True),   # already there
])
def test_the_migration(qapp, tmp_path, values, want_i1pro, want_i1pro2, stored2):
    AS = _store(tmp_path, values)
    s = AS()
    s.migrate()
    s2 = AS()
    assert iw.seconds(iw.LAMP_OFF, s2.get(iw.LAMP_OFF.key)) == want_i1pro
    assert iw.seconds(iw.I1PRO2_LAMP_OFF, s2.get(iw.I1PRO2_LAMP_OFF.key)) == want_i1pro2
    assert s2.is_stored(iw.I1PRO2_LAMP_OFF.key) is stored2


def test_the_migration_runs_once(qapp, tmp_path):
    """A value typed into the i1Pro field after the first start of the new version never
    moves the i1Pro 2's (only the schema step copies)."""
    AS = _store(tmp_path, {})
    AS().migrate()
    s = AS()
    s.set(iw.LAMP_OFF.key, 1.3)
    AS().migrate()
    assert iw.seconds(iw.I1PRO2_LAMP_OFF, AS().get(iw.I1PRO2_LAMP_OFF.key)) == 1.10


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


def _args(tmp_path, monkeypatch, caps, waits=None):
    from workflow import chartread_engine
    from workflow.measure_manager import MeasureManager, MeasureParams
    monkeypatch.setattr(chartread_engine, "helper_caps", lambda helper=None: frozenset(caps))
    monkeypatch.setattr(MeasureManager, "_refuse_system_port", lambda self, *a, **k: False)
    runner = _Runner()
    m = MeasureManager(runner)
    p = MeasureParams(ti1_path=tmp_path / "chart.ti1", engine_helper=tmp_path / "chromiq-chartread",
                      engine_waits_ms=waits)
    m.start(p, lambda _l: None, lambda _c: None)
    return runner.calls[-1][1], m


def _flag(args, flag):
    return args[args.index(flag) + 1] if flag in args else None


def test_the_new_helper_gets_both_values(qapp, tmp_path, monkeypatch):
    args, m = _args(tmp_path, monkeypatch, {"instrument_waits", iw.CAP_I1PRO2})
    assert (_flag(args, "--lamp-off-ms"), _flag(args, "--lamp-off-ms-i1pro2")) == ("1500", "1100")
    assert m._waits_ms == {"lamp_off": 1500, "lamp_off_i1pro2": 1100}


def test_a_typed_value_wins(qapp, tmp_path, monkeypatch):
    args, m = _args(tmp_path, monkeypatch, {"instrument_waits", iw.CAP_I1PRO2},
                    waits={"lamp_off_i1pro2": 1500, "lamp_off": 1200})
    assert (_flag(args, "--lamp-off-ms"), _flag(args, "--lamp-off-ms-i1pro2")) == ("1200", "1500")


def test_an_older_helper_gets_one_value_as_before(qapp, tmp_path, monkeypatch):
    """A helper of 4.3.53 / 4.3.54 (no caps word): only --lamp-off-ms, which it applies to the
    i1Pro 2 too (it does not know the other argument, which would stop it)."""
    args, m = _args(tmp_path, monkeypatch, {"instrument_waits"})
    assert _flag(args, "--lamp-off-ms") == "1500" and "--lamp-off-ms-i1pro2" not in args
    assert m._waits_ms == {"lamp_off": 1500}


def test_the_new_helper_with_an_older_app():
    """An app of 4.3.53 / 4.3.54 passes --lamp-off-ms only: the helper's driver then gives that
    value to the i1Pro 2 too (test_the_driver_picks_the_wait_by_model, (1060, -1))."""
    h = (ROOT / "native" / "chartread_helper" / "chromiq_chartread.c").read_text(
        encoding="utf-8", errors="surrogateescape")
    assert '"--lamp-off-ms-i1pro2"' in h and "i1pro2_cq_lamp_off_ms = cq_lamp_off_i1pro2_set_ms;" in h
    assert '\\"lamp_off_i1pro2\\"' in h                     # the caps word
    assert '\\"lamp_off_i1pro2_ms\\":%d' in h               # said in the waits event


def test_the_app_log_says_both_and_which_applied(qapp, tmp_path, monkeypatch, caplog):
    args, m = _args(tmp_path, monkeypatch, {"instrument_waits", iw.CAP_I1PRO2})
    with caplog.at_level("INFO"):
        m._handle_engine_line(json.dumps({"event": "waits", "lamp_off_ms": 1500,
                                          "lamp_off_i1pro2_ms": 1100, "blue_quiet_ms": -1,
                                          "blue_after_ms": 550, "ignored": ""}), lambda _l: None)
        m._handle_engine_line(json.dumps({"event": "instrument", "model": "i1Pro2"}),
                              lambda _l: None)
    msgs = [r.getMessage() for r in caplog.records]
    assert any("helper waits" in s and "lamp_off_ms=1500" in s and "lamp_off_i1pro2_ms=1100" in s
               for s in msgs), msgs
    assert any(s.startswith("lamp wait: ") and "applied=i1pro2" in s and "lamp_off_s=1.1" in s
               for s in msgs), msgs
    from workflow.measure_log import _waits_fields
    f = _waits_fields(m._waits_ms)
    assert f == {"lamp_off_s": "1.5", "lamp_off_i1pro2_s": "1.1"}


def test_the_bundled_helper_takes_the_i1pro2_wait():
    data = (ROOT / "native" / "chromiq-chartread").read_bytes()
    assert b"--lamp-off-ms-i1pro2" in data and b"lamp_off_i1pro2" in data


def test_the_preferences_rows_sit_together_and_take_the_table():
    src = (ROOT / "ui" / "dialogs" / "settings_dialog.py").read_text(encoding="utf-8")
    a = src.index("self._add_wait_row(_beta, _iw.LAMP_OFF, 0,")
    b = src.index("self._add_wait_row(_beta, _iw.I1PRO2_LAMP_OFF, 0,")
    assert 0 < b - a < 600
    assert src.count("for _w in (_iw.BLUE_QUIET, _iw.BLUE_AFTER, _iw.LAMP_OFF, _iw.I1PRO2_LAMP_OFF):") == 2
