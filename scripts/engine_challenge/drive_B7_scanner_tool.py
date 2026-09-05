"""B7 — Tools → "Build profile with scanner or camera", printer mode, with
the engine + Maximum accuracy on (A-Q3).

The whole ~/ChromIQ/Knut-Scanner project is COPIED into the sandbox first.
The tool is opened through the same call the Tools menu makes
(`open_tool_dialog("scanner_profile", …)`, a modal `exec()`), driven from
the journey: "A chart I made in ChromIQ", tick "Profile my printer from this
scan", chart = the copied run's Knut-Scanner.ti2 (`_set_chart`, ASSISTED —
the picker is a native file dialog), scanner profile = the copied
Knut-Scanner-scanner.icc (ASSISTED, same reason). Then the command preview
is read and photographed. The build itself is started through the tool's
own `_build_printer_profile(pbase, base)` on the copied, already
accumulated Knut-Scanner-printer.ti3 (ASSISTED: the three page scans are
not re-read through scanin; everything from the colprof step on is the
tool's real code path). Then the same measurement in Build Profile → Manual
→ accurate, and both A2B1 tables compared through xicclu on 20 device
values.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.engine_challenge.harness import Harness            # noqa: E402
from scripts.engine_challenge.drive_B_common import (            # noqa: E402
    WORK_B, active_modal, build_and_answer, button_named, buttons_of, click,
    grab, modal_title, run_journey, sandbox, say)

OUT = WORK_B / "B7"
OUT.mkdir(parents=True, exist_ok=True)
SEEN: list[tuple[str, str]] = []
SRC = Path.home() / "ChromIQ" / "Knut-Scanner"
XICCLU = "/Applications/Argyll/bin/xicclu"
DEV = [(r / 100, g / 100, b / 100) for r, g, b in
       [(0, 0, 0), (100, 100, 100), (50, 50, 50), (25, 25, 25), (75, 75, 75),
        (100, 0, 0), (0, 100, 0), (0, 0, 100), (100, 100, 0), (0, 100, 100),
        (100, 0, 100), (80, 20, 20), (20, 80, 20), (20, 20, 80), (60, 40, 20),
        (40, 60, 80), (90, 90, 60), (10, 30, 50), (70, 10, 40), (35, 65, 45)]]


def a2b1(icc: Path) -> list[list[float]]:
    inp = "\n".join(f"{r:.4f} {g:.4f} {b:.4f}" for r, g, b in DEV) + "\n"
    r = subprocess.run([XICCLU, "-ff", "-ir", "-pl", "-s100", str(icc)], input=inp,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    out = []
    for ln in r.stdout.splitlines():
        if "->" in ln:
            rhs = ln.split("->")[1].split("[")[0].split()
            out.append([float(x) for x in rhs[:3]])
    return out


def de76(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


ENGINE_ONLY = "--engine-only" in sys.argv


def journey(h, run_dir: Path):
    win = h.win
    base = run_dir / "Knut-Scanner"
    pbase = run_dir / "Knut-Scanner-printer"
    ti3 = run_dir / "Knut-Scanner-printer.ti3"
    tool_icc = run_dir / "Knut-Scanner-printer.icc"
    say(f"engine settings: beta={h.settings.get('profile_engine_beta')} mode={h.settings.get('gammap_mode')}")
    if ENGINE_ONLY:
        yield from engine_half(h, tool_icc)
        return

    say("open the tool the way the Tools menu does (modal exec)")
    from PyQt6.QtCore import QTimer
    from ui.dialogs.tools_dialogs import open_tool_dialog
    QTimer.singleShot(0, lambda: open_tool_dialog("scanner_profile", win._runner, h.settings, win))
    for _ in range(60):
        yield 100
        if active_modal(h) is not None:
            break
    dlg = active_modal(h)
    say(f"  modal: {dlg.__class__.__name__} title={dlg.windowTitle()!r} size={dlg.width()}x{dlg.height()}")
    yield 500
    click(dlg._mode_chromiq); yield 300
    click(dlg._printer_cb); yield 400
    say(f"  chromiq mode={dlg._mode_chromiq.isChecked()} printer mode={dlg._printer_mode()} run button={dlg._run_btn.text()!r}")
    dlg._set_chart(base.with_suffix(".ti2")); yield 500
    say(f"  chart field={dlg._ti3_field.text()!r}")
    dlg._printer_scan_profile = run_dir / "Knut-Scanner-scanner.icc"
    dlg._printer_prof_field.setText(str(dlg._printer_scan_profile))
    dlg._refresh(); dlg._update_command_preview(); yield 400
    say(f"  profile name field={dlg._prof_name.text()!r}")
    say(f"  COMMAND PREVIEW: {dlg._cmd_preview.text()!r}")
    say(f"  run button enabled={dlg._run_btn.isEnabled()} text={dlg._run_btn.text()!r}")
    from PyQt6.QtWidgets import QAbstractButton, QComboBox, QCheckBox
    eng = [w for w in dlg.findChildren(QAbstractButton) + dlg.findChildren(QComboBox)
           if any(k in (getattr(w, "text", lambda: "")() + " ".join(w.itemText(i) for i in range(w.count())) if isinstance(w, QComboBox) else w.text()).lower()
                  for k in ("spectral", "noise", "bijective", "icc profile version", "engine", "accura"))]
    say(f"  engine-ish controls in the tool window: {[(w.__class__.__name__, (w.text() if not isinstance(w, QComboBox) else w.currentText())) for w in eng]}")
    grab(dlg, OUT / "01-tool-printer-mode.png")
    # Advanced section open → what options does the tool offer?
    for w in dlg.findChildren(QAbstractButton):
        if w.text().strip().lower().startswith("advanced"):
            click(w); yield 500
            break
    grab(dlg, OUT / "02-tool-advanced-open.png")
    say(f"  COMMAND PREVIEW (advanced open): {dlg._cmd_preview.text()!r}")

    say("start the tool's own printer-profile build from the accumulated .ti3 (skips scanin)")
    if tool_icc.exists():
        tool_icc.rename(run_dir / "Knut-Scanner-printer.ORIGINAL.icc")
    t0 = time.monotonic()
    QTimer.singleShot(0, lambda: dlg._build_printer_profile(pbase, base))
    for _ in range(600):
        yield 200
        m = active_modal(h)
        if m is not None and m is not dlg:
            yield 300
            say(f"  tool modal {m.windowTitle()!r} buttons={[b.text() for b in buttons_of(m)]}")
            grab(m, OUT / "03-tool-modal.png")
            b = buttons_of(m)[-1] if buttons_of(m) else None
            SEEN.append((m.windowTitle(), b.text() if b else "?"))
            if b is not None:
                click(b)
            continue
        if not win._runner.is_running and time.monotonic() - t0 > 3 and dlg._run_btn.isEnabled():
            break
    say(f"  tool build finished in {time.monotonic()-t0:.0f}s; runner running={win._runner.is_running}; icc={tool_icc.exists()} size={tool_icc.stat().st_size if tool_icc.exists() else 0}")
    log = dlg._log.toPlainText()
    (OUT / "tool-log.txt").write_text(log, encoding="utf-8")
    say("  tool log (last 12 lines):")
    for ln in log.splitlines()[-12:]:
        say(f"    {ln}")
    grab(dlg, OUT / "04-tool-after-build.png")
    if tool_icc.exists():
        shutil.copyfile(tool_icc, OUT / "tool-colprof.icc")
    # close the tool
    for b in buttons_of(dlg):
        if b.text().strip().lower() in ("close", "done"):
            SEEN.append((dlg.windowTitle(), b.text()))
            click(b)
            break
    else:
        dlg.reject()
    yield 500
    say(f"  modal after closing tool: {modal_title(h)}")

    yield from engine_half(h, tool_icc)


def engine_half(h, tool_icc: Path):
    say("same measurement in Build Profile → Manual → accurate (project Knut-Engine, its run1 measurement IS Knut-Scanner-printer.ti3)")
    h.open_project("Knut-Engine")
    yield 400
    prof = h.go_profile_tab("manual")
    eng_ti3 = h.work / "Knut-Engine/runs/run1/Knut-Engine.ti3"
    if Path(prof._file_lbl.text()) != eng_ti3:
        say(f"  the tab still showed {prof._file_lbl.text()!r}; loading the run's own measurement (harness: set_ti3_path)")
        h.load_measurement(eng_ti3)
    yield 300
    say(f"  ti3={prof._file_lbl.text()!r} rows visible={prof._m_engine_rows_widget.isVisible()} first log={prof._log.toPlainText().splitlines()[:2]}")
    el, title = yield from build_and_answer(h, OUT, "engine", SEEN, shots=(10,), answer=("Done", "Build anyway", "Close", "OK"))
    say(f"  engine build ended with modal {title!r} after {el:.0f}s")
    eng_icc = h.work / "Knut-Engine/runs/run1/Knut-Engine.icc"
    say(f"  engine icc={eng_icc.exists()} size={eng_icc.stat().st_size if eng_icc.exists() else 0}")
    if eng_icc.exists():
        shutil.copyfile(eng_icc, OUT / "engine-accurate.icc")
    if tool_icc.exists() and eng_icc.exists():
        a, b = a2b1(tool_icc), a2b1(eng_icc)
        rows = [(DEV[i], a[i], b[i], round(de76(a[i], b[i]), 2)) for i in range(min(len(a), len(b)))]
        (OUT / "a2b1-compare.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        des = sorted(r[3] for r in rows)
        say(f"  A2B1 tool(colprof) vs engine(accurate) on {len(rows)} device values: ΔE76 median={des[len(des)//2]} max={des[-1]}")
        for r in rows:
            say(f"    dev={tuple(round(x,2) for x in r[0])} colprof={[round(x,2) for x in r[1]]} engine={[round(x,2) for x in r[2]]} ΔE={r[3]}")


def main() -> int:
    h = Harness(sandbox("B7"))
    dst = h.work / "Knut-Scanner"
    if not dst.exists():
        shutil.copytree(SRC, dst)
    run_dir = dst / "runs/run1"
    h.boot()
    # the engine-side project: the SAME accumulated scanner measurement as its run1 measurement
    h.make_project("Knut-Engine", run_dir / "Knut-Scanner-printer.ti3")
    h.enable_engine("accurate")
    h.open_project("Knut-Scanner")
    run_journey(h, journey(h, run_dir), timeout=1500)
    say(f"dialogs I clicked: {SEEN}; watchdog: {h.modals_answered}")
    say(f"sandbox: {h.sandbox}  out: {OUT}")
    h.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
