#!/usr/bin/env python3
"""Adversary round 30, job 2: what does ChromIQ DO when a slot raises?

Beta 26 shipped three buttons that raised `NameError` on every press and looked
merely inert.  The commit message says "Qt swallows an exception raised inside a
slot".  Eight comments in this tree say the OPPOSITE -- that PyQt hands it to
`sys.excepthook` and calls `qFatal()`, so ChromIQ ABORTS.  Both cannot be true,
and which one it is decides whether an excepthook is worth building.

So measure it, in a real window, on the real app's `main.py` hook:

  A. a raising slot on `clicked`                    (the shipped shape)
  B. a raising slot on a queued/`singleShot` timer
  C. a raising `paintEvent`
  D. whether `main._log_excepthook` ever ran, and whether chromiq.log shows it

Nothing about this needs a photograph: the finding is a process exit code and a
log line.  Run it as a SUBPROCESS per case so an abort is observable.

    python scripts/adv30_what_happens_when_a_slot_raises.py            # parent
    python scripts/adv30_what_happens_when_a_slot_raises.py <case>     # child
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CASES = ("clicked", "singleshot", "paint")


def child(case: str) -> None:
    import main as chromiq_main          # installs sys.excepthook + faulthandler
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

    ran: list[str] = []
    prev = sys.excepthook

    def hook(t, e, tb):
        ran.append(f"{t.__name__}: {e}")
        print("EXCEPTHOOK-RAN " + json.dumps(ran[-1]), flush=True)
        prev(t, e, tb)

    sys.excepthook = hook

    app = QApplication.instance() or QApplication(sys.argv)

    class Painter(QWidget):
        def paintEvent(self, ev):                          # noqa: N802
            if case == "paint":
                raise RuntimeError("adv30 paintEvent")

    w = Painter()
    w.resize(320, 140)
    btn = QPushButton("press", w)
    btn.move(20, 40)

    def boom() -> None:
        print("SLOT-ENTERED", flush=True)
        raise RuntimeError("adv30 slot")

    btn.clicked.connect(boom)
    w.show()
    app.processEvents()

    print("ALIVE-BEFORE", flush=True)
    if case == "clicked":
        btn.click()
    elif case == "singleshot":
        QTimer.singleShot(0, boom)
        app.processEvents()
    app.processEvents()
    print("ALIVE-AFTER", flush=True)
    print("EXCEPTHOOK-COUNT " + str(len(ran)), flush=True)
    app.quit()
    sys.exit(0)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in CASES:
        child(sys.argv[1])
        return 0

    out = ROOT.parent  # unused
    env = dict(os.environ)
    env["CHROMIQ_SETTINGS_FILE"] = "/tmp/chromiq-r30/settings.ini"
    env["CHROMIQ_PRESETS_DIR"] = "/tmp/chromiq-r30/presets"
    env.pop("QT_QPA_PLATFORM", None)          # ON SCREEN. A real window.

    rows = []
    for case in CASES:
        p = subprocess.run([sys.executable, str(Path(__file__)), case],
                           capture_output=True, text=True, encoding='utf-8', timeout=180, env=env)
        o = p.stdout
        rows.append({
            "case": case,
            "exit": p.returncode,
            "slot_entered": "SLOT-ENTERED" in o,
            "reached_after": "ALIVE-AFTER" in o,
            "excepthook_ran": "EXCEPTHOOK-RAN" in o,
            "traceback_on_stderr": "Traceback (most recent call last)" in p.stderr,
            "qfatal_or_abort": p.returncode < 0 or "Fatal" in p.stderr
                               or "abort" in p.stderr.lower(),
            "stderr_tail": p.stderr.strip().splitlines()[-4:],
        })
        print(json.dumps(rows[-1], indent=2), flush=True)

    dest = Path.home() / "Desktop/ChromIQ-beta27-proof/round-30"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "excepthook-probe.json").write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print("\nwrote " + str(dest / "excepthook-probe.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
