#!/usr/bin/env python3
"""The single on-screen runner for issue #130 (Knut agreed to the merge,
2026-07-26).

It drives the REAL ChromIQ app through **every** row of the #130 test plan in
one go and prints one table:

    load model      9 rows — loading profiles, charts and .ti2 files into new,
                             existing and external projects, with the pop-up
                             answered the way each row intends
                             (scripts/drive_130_test_plan.py)
    verification   14 rows — the dated verification folders, the chart snapshot
                             taken at measurement start, Restore Used Chart and
                             the archiving rules
                             (scripts/drive_130_verify_plan.py)

Run headless for a pass/fail table:
    QT_QPA_PLATFORM=offscreen python scripts/drive_130.py
Run on screen to watch it (slower, with pauses):
    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_130.py

Either section can still be run on its own — both scripts keep their own
``main()`` — but this is the one to run before cutting a beta.

**Order matters.** The load-model section builds a real MainWindow and must go
first: it imports QtWebEngine before any QApplication exists (issue #38), and
the verification section replaces the modal-dialog stubs with blanket ones that
would otherwise swallow the pop-up answers the load-model rows depend on.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Importing the load-model driver first sets QT_QPA_PLATFORM and pulls in
# QtWebEngine — both must happen before any QApplication is created.
import scripts.drive_130_test_plan as load_model      # noqa: E402
import scripts.drive_130_verify_plan as verification  # noqa: E402

SECTIONS = (
    ("load model", load_model, load_model.run_scenarios),
    ("verification", verification, verification.run_rows),
)


def main() -> int:
    failures: list[tuple[str, str, str]] = []
    total = passed = 0

    for title, module, run in SECTIONS:
        print(f"\n{'=' * 70}\n  #130 — {title}\n{'=' * 70}")
        try:
            run()
        except Exception as exc:      # noqa: BLE001 — one section must not
            # hide the other's result; record it and carry on.
            module.RESULTS.append((f"{title} section crashed", False,
                                   f"{type(exc).__name__}: {exc}"))
        rows = list(module.RESULTS)
        ok = sum(1 for _, good, _ in rows if good)
        total += len(rows)
        passed += ok
        failures += [(title, name, detail) for name, good, detail in rows
                     if not good]
        print(f"\n  {title}: {ok}/{len(rows)} passed")

    print(f"\n{'=' * 70}")
    print(f"==== #130 total: {passed}/{total} rows PASSED ====")
    if failures:
        print("\nFailures:")
        for title, name, detail in failures:
            print(f"  [{title}] {name} — {detail}")
    sys.stdout.flush()
    # Hard-exit past the WebEngine teardown, which segfaults offscreen (#38).
    os._exit(0 if passed == total else 1)


if __name__ == "__main__":
    raise SystemExit(main())
