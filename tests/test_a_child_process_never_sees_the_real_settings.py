"""A child process a test starts never opens the real preferences
(2026-10-25). The suite's settings sandbox is a name swapped inside the test
process; a fresh interpreter started with `sys.executable` has no conftest,
so it reaches the real store unless CHROMIQ_SETTINGS_FILE is in the
environment it inherits. `tests/conftest.py::pytest_configure` puts it there."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

PROBE = ("import sys; sys.path.insert(0, %r); "
         "from core.settings import AppSettings; "
         "print(AppSettings()._qs.fileName())") % str(REPO)


def test_the_variable_is_in_the_environment_children_inherit():
    v = os.environ.get("CHROMIQ_SETTINGS_FILE", "")
    assert v, "a child process would open the real preferences"
    assert "Library/Preferences" not in v


def test_a_child_appsettings_opens_the_sandbox_not_the_real_store():
    out = subprocess.run([sys.executable, "-c", PROBE], capture_output=True,
                         text=True, encoding="utf-8", timeout=120,
                         env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    path = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    assert path, out.stderr[-2000:]
    assert path == os.environ["CHROMIQ_SETTINGS_FILE"], path
    assert not path.endswith("com.chromiq.ChromIQ.plist")
