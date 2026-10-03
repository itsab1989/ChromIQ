"""A driver that ends with os._exit stops the processes it started.

Found 2026-10-03 (review of 6de015eb): eleven ``chromiq-chartread --replay``
helpers were still running from five on-screen driver runs, each waiting on
stdin for a swipe that would never come. The drivers end with ``os._exit``,
which skips every clean-up, so the helper the real MainWindow had started was
orphaned. ``capture_screens.build_app`` now installs
``onscreen_capture.stop_children_at_exit``.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform == "win32", reason="pkill: macOS and Linux")
def test_os_exit_stops_the_children(tmp_path):
    pidfile = tmp_path / "child.pid"
    code = (
        "import os, subprocess, sys\n"
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
        "import onscreen_capture as oc\n"
        "oc.stop_children_at_exit()\n"
        "oc.stop_children_at_exit()  # idempotent\n"
        "p = subprocess.Popen(['sleep', '120'])\n"
        f"open({str(pidfile)!r}, 'w').write(str(p.pid))\n"
        "os._exit(0)\n")
    subprocess.run([sys.executable, "-c", code], timeout=60, check=True)
    pid = int(pidfile.read_text(encoding="utf-8"))
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        # A zombie of an already-dead parent is reaped by init; ask ps.
        st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                            capture_output=True, text=True,
                            encoding="utf-8").stdout.strip()
        if not st or st.startswith("Z"):
            return
        time.sleep(0.2)
    os.kill(pid, 9)
    pytest.fail("the child outlived the driver's os._exit")


def test_build_app_installs_it():
    tree = ast.parse((ROOT / "scripts" / "capture_screens.py").read_text("utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "build_app")
    calls = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "stop_children_at_exit" in calls
