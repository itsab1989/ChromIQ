"""B8 — bad inputs as the user sees them (critic N13, N17).

Three projects in one sandbox: the 18-patch stuck-instrument CR30 chart, the
315-patch junk scanner chart, and a copy of the 924p chart with one XYZ row
turned into NaN. Each: Manual + accurate, Build, read the modal / the log /
the fit line, and whether a profile file was written.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    CHART_18, CHART_315, CHART_924, WORK_B, build_and_answer, grab,
    run_journey, sandbox, say)

OUT = WORK_B / "B8"
OUT.mkdir(parents=True, exist_ok=True)
SEEN: list[tuple[str, str]] = []


def make_nan_copy(src: Path, dst: Path, row: int = 100) -> None:
    lines = src.read_text(encoding="utf-8").splitlines(keepends=True)
    out, in_data, n = [], False, 0
    for ln in lines:
        if ln.startswith("BEGIN_DATA") and not ln.startswith("BEGIN_DATA_FORMAT"):
            in_data = True
            out.append(ln)
            continue
        if ln.startswith("END_DATA"):
            in_data = False
        if in_data:
            n += 1
            if n == row:
                parts = ln.split()
                # SAMPLE_ID SAMPLE_LOC R G B X Y Z SPEC…  → X Y Z := nan
                parts[5:8] = ["nan", "nan", "nan"]
                ln = " ".join(parts) + "\n"
        out.append(ln)
    dst.write_text("".join(out), encoding="utf-8")


def one(h, name: str):
    win, prof = h.win, h.win._tab_profile
    h.open_project(name)
    yield 500
    prof = h.go_profile_tab("manual")
    own = h.work / name / "runs/run1" / f"{name}.ti3"
    if Path(prof._file_lbl.text()) != own:
        say(f"    tab showed {prof._file_lbl.text()!r}; loading the run's own measurement (harness: set_ti3_path)")
        h.load_measurement(own)
    yield 300
    say(f"=== {name}: ti3={prof._file_lbl.text()!r} build enabled={prof._build_btn.isEnabled()} tip={prof._build_btn.toolTip()[:120]!r}")
    say(f"    first log lines: {prof._log.toPlainText().splitlines()[:3]}")
    grab(win, OUT / f"{name}-before.png")
    if not prof._build_btn.isEnabled():
        say("    Build disabled — stopping here for this chart")
        return
    el, title = yield from build_and_answer(h, OUT, name, SEEN, answer=("Done", "Close", "OK", "Build anyway", "Cancel"), shots=())
    log = prof._log.toPlainText()
    icc = h.work / name / "runs/run1" / f"{name}.icc"
    say(f"    modal={title!r} after {el:.0f}s; icc written={icc.exists()} size={icc.stat().st_size if icc.exists() else 0}")
    fit = [ln for ln in log.splitlines() if re.search(r"fit|ERROR|disagree|scatter|noise|patch", ln, re.I)]
    say("    fit/error lines:")
    for ln in fit:
        say(f"      {ln}")


def journey(h):
    for name in ("CR30-18p", "Scanner-315p", "NaN-924p"):
        yield from one(h, name)


def main() -> int:
    h = Harness(sandbox("B8"))
    h.boot()
    nan_src = WORK_B / "B8" / "real-rgb-924p-nan-row100.ti3"
    make_nan_copy(CHART_924, nan_src)
    h.make_project("CR30-18p", CHART_18)
    h.make_project("Scanner-315p", CHART_315)
    h.make_project("NaN-924p", nan_src)
    h.enable_engine("accurate")
    run_journey(h, journey(h), timeout=1500)
    say(f"dialogs I clicked: {SEEN}; watchdog: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}  out: {OUT}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
