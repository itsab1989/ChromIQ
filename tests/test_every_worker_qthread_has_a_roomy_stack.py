"""Every worker QThread gets a stack big enough for numpy's OpenBLAS.

Knut, #182 5956290893 / 5956458028 (4.3.3-beta.3, Apple Silicon): Build Profile
with Engine v2 crashed every time, "Fatal Python error: Bus error" in
numpy.linalg.solve on `_EngineThread`: OpenBLAS's dgetrf_parallel ran off a
QThread's 512 KiB default stack. Reproduced 2026-10-02 with his own run1
measurement and the numpy the release ships (2.4.4 macosx_11_0_arm64,
scipy-openblas 0.3.31): exit 138 (SIGBUS) on the default stack, a finished
profile with core.thread_stack.roomy. This repository's own test numpy may use
Apple's Accelerate, which does not need the stack, so the crash itself cannot
be reproduced here; what is pinned is that no QThread is started without it.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
APP = [p for d in ("core", "ui", "workflow") for p in (REPO / d).rglob("*.py")]


def test_the_stack_is_large():
    from core.thread_stack import WORKER_STACK_BYTES
    assert WORKER_STACK_BYTES >= 16 * 1024 * 1024


def test_every_qthread_subclass_asks_for_room():
    missing = []
    for p in APP:
        src = p.read_text(encoding="utf-8")
        for m in re.finditer(r"^class (\w+)\(QThread\):", src, re.M):
            body = src[m.end():m.end() + 1500]
            if "roomy(self)" not in body:
                missing.append(f"{p.relative_to(REPO)}:{m.group(1)}")
    assert not missing, missing


def test_every_plain_qthread_is_made_roomy():
    bare = []
    for p in APP:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bQThread\(\)", line) and "roomy(QThread())" not in line:
                bare.append(f"{p.relative_to(REPO)}:{i}")
    assert not bare, bare


def test_roomy_sets_the_size():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtCore import QCoreApplication, QThread
    QCoreApplication.instance() or QCoreApplication([])
    from core.thread_stack import WORKER_STACK_BYTES, roomy
    t = roomy(QThread())
    assert t.stackSize() == WORKER_STACK_BYTES
