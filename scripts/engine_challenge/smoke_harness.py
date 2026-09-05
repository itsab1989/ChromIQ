"""Smoke: boot the real app, build the real 924-patch chart in Maximum accuracy on screen."""
from __future__ import annotations
import sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from scripts.engine_challenge.harness import Harness, fresh_sandbox

CHART = Path.home() / "Desktop/ChromIQ-engine-challenge/charts/real-rgb-924p-spectral36.ti3"

def main() -> int:
    h = Harness(fresh_sandbox("smoke-"))
    h.boot()
    h.arm_modal_watchdog()
    h.make_project("Real-924", CHART)
    h.open_project("Real-924")
    h.enable_engine("accurate")
    prof = h.go_profile_tab("manual")
    print("engine rows hidden?", prof._m_engine_rows_widget.isHidden(),
          "visible?", prof._m_engine_rows_widget.isVisible(), flush=True)
    h.screenshot("manual-accurate-rows")
    h.load_measurement(h.work / "Real-924/runs/run1/Real-924.ti3")
    t0 = time.time()
    h.build()
    h.screenshot("building")
    ok = h.wait_build_done(900)
    print(f"build finished={ok} in {time.time()-t0:.0f}s", flush=True)
    h.screenshot("after-build")
    icc = h.work / "Real-924/runs/run1/Real-924.icc"
    print("icc exists:", icc.exists(), icc.stat().st_size if icc.exists() else 0)
    print("modals answered:", h.modals_answered)
    print("--- log tail ---")
    print("\n".join(h.build_log().splitlines()[-12:]))
    print("sandbox:", h.sandbox)
    h.close()
    return 0 if ok and icc.exists() else 1

if __name__ == "__main__":
    sys.exit(main())
