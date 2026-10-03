"""A start-up self-test the release build runs on the BUILT app.

``CHROMIQ_SELFTEST=1 ChromIQ.app/Contents/MacOS/ChromIQ`` loads what a normal
start loads first (numpy with its BLAS, Qt's widgets), does one small piece of
linear algebra, prints one line and exits, without opening a window or
touching any setting. The macOS build runs it under ``arch -x86_64`` so the
Intel half of the universal app is proved to start (review P_review2_beta1:
the Rosetta step imported numpy from the build machine's site-packages, not
from the app it ships). Unset, it does nothing.
"""
from __future__ import annotations

import os
import platform
import sys

ENV = "CHROMIQ_SELFTEST"


def run_if_asked() -> None:
    if os.environ.get(ENV, "").strip() != "1":
        return
    try:
        import numpy
        import numpy.linalg
        from PyQt6 import QtWidgets  # noqa: F401  (Qt's libraries load)
        inv = float(numpy.linalg.inv(numpy.eye(3) * 2.0)[0, 0])
        if abs(inv - 0.5) > 1e-12:
            raise RuntimeError(f"numpy.linalg.inv gave {inv}, not 0.5")
    except BaseException as exc:      # noqa: BLE001 — report, then fail
        print(f"chromiq-selftest FAILED on {platform.machine()}: {exc!r}",
              flush=True)
        sys.exit(1)
    print(f"chromiq-selftest ok machine={platform.machine()} "
          f"numpy={numpy.__version__}", flush=True)
    sys.exit(0)
