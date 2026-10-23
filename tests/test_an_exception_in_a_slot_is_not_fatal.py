"""Agent 22, 2026-10-23: a Print button's slot raised TypeError in an
on-screen driver and PyQt6 aborted the process ("Python quit unexpectedly"
on Basti's Mac). With the default sys.excepthook PyQt6 calls qFatal() on an
exception in a slot. main.py installs a logging hook at import, which keeps
the shipped app alive; a driver's build_app must install one too."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PROBE = r"""
import sys
sys.path.insert(0, {root!r}); sys.path.insert(0, {scripts!r})
{setup}
from PyQt6.QtWidgets import QApplication, QPushButton
app = QApplication.instance() or QApplication([])
b = QPushButton("x")
def boom():
    raise TypeError("boom")
b.clicked.connect(boom)
b.click()
print("STILL ALIVE", flush=True)
"""


def _run(setup: str):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    code = _PROBE.format(root=str(ROOT), scripts=str(ROOT / "scripts"),
                         setup=setup)
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, encoding="utf-8", timeout=120, env=env, cwd=str(ROOT))


def test_the_drivers_hook_keeps_the_process_alive():
    r = _run("from capture_screens import install_logging_excepthook\n"
             "install_logging_excepthook()")
    assert r.returncode == 0 and "STILL ALIVE" in r.stdout, r.stderr[-800:]


def test_main_installs_a_hook_at_import():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "sys.excepthook = _log_excepthook" in src


def test_build_app_installs_it():
    src = (ROOT / "scripts" / "capture_screens.py").read_text(encoding="utf-8")
    body = src[src.index("def build_app"):]
    assert "install_logging_excepthook()" in body[:body.index("\ndef ", 10)]
