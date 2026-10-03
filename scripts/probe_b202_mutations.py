#!/usr/bin/env python3
"""Mutation probe for the #202 fix: put back each fault (or its most likely
wrong variant) one at a time, run the #202 tests, require RED, restore.

Edits files IN PLACE and restores them from a backup, so never run it while a
gate is running or another process works in the same tree."""
import os
import shutil
import subprocess
from pathlib import Path

R = Path(__file__).resolve().parent.parent
TEST = "tests/test_b202_the_i1pro_generation_is_read_right.py"
MUTS = [
    ("the old table: 'i1 pro2' never matches Argyll's 'i1 Pro 2'", "core/measure_pace.py",
     'm = _I1PRO_RE.search(low)', 'm = _I1PRO_RE.search(str(argyll_name).lower())'),
    ("a later report may downgrade a 3 Plus", "core/measure_pace.py",
     'return not (old_key == "i1pro3plus" and new_key == "i1pro3")', 'return True'),
    ("the engine ignores the verbose header", "workflow/measure_manager.py",
     '                m = _INST_TYPE_RE.search(line)\n                if m:\n                    self.instrument_detected.emit(m.group(1).strip())\n',
     ''),
    ("the pace reads only the chart-overwritable name", "ui/tabs/tab_measure.py",
     'key = (model_key(getattr(self, "_reported_instrument", None))\n               or model_key(getattr(self, "_detected_instrument", None)))',
     'key = model_key(getattr(self, "_detected_instrument", None))'),
    ("a new session keeps the last device", "ui/tabs/tab_measure.py",
     '        self._saw_instrument = False\n        self._reported_instrument = None\n',
     '        self._saw_instrument = False\n'),
    ("every report warns again", "ui/tabs/tab_measure.py",
     '        if repeat:\n            return\n', ''),
]

for name, f, a, b in MUTS:
    p = R / f
    orig = p.read_text(encoding="utf-8")
    assert orig.count(a) == 1, name
    shutil.copy(p, str(p) + ".bak")
    try:
        p.write_text(orig.replace(a, b), encoding="utf-8")
        r = subprocess.run([str(R / ".venv/bin/python"), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            "-o", "addopts=", TEST], cwd=R, capture_output=True, text=True,
                           encoding="utf-8", env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
        failed = [l.split("::")[-1] for l in r.stdout.splitlines() if l.startswith("FAILED")]
        print(("RED  " if r.returncode else "GREEN"), name, failed, flush=True)
    finally:
        shutil.move(str(p) + ".bak", p)
