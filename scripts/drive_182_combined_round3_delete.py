#!/usr/bin/env python3
"""Combined round 3: drive the saved-report DELETE path until it breaks.

B8-275 changed a destructive path. `_saved_delete_refusal` used to count the
window's own `_all_report_files` snapshot and now counts the FOLDER it is about
to write in. This drives that change in a real window, on a copy of a real
project, and after every press it LISTS THE FOLDER ON DISK rather than asking
the window what it thinks happened.

Seven presses, in the order a person could make them:

  A  the last saved report of a dated verification         -> must refuse
  B  one of several saved reports of one date              -> must delete the
     one the confirmation names, and then refuse the last
  C  the chosen report's file removed under the app         -> ?
  D  the folder made read-only between the confirmation
     and the press                                          -> ?
  E  two dates, one of them holding no report at all        -> ?
  F  a delete straight after a Generate, no re-pick         -> ?
  G  a `report_*.json` the window CANNOT READ beside the
     only one it can                                        -> ?

Nothing is blanket-approved: `_confirm` is recorded and answered per press, so
what the confirmation PROMISED can be compared with what the folder holds
afterwards.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

SOURCE = Path.home() / "ChromIQ" / "Demo-Switching"
DATE = "2026-06-24_164000"
VERIF_TI3 = "Demo-Switching-verify.ti3"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def on_disk(folder: Path) -> list:
    """What `report_*.json` files the folder really holds, and which of them
    the window could read. Never asked of the window."""
    out = []
    try:
        for p in sorted(folder.glob("report_*.json")):
            try:
                json.loads(p.read_text(encoding="utf-8"))
                out.append(p.name)
            except Exception:                       # noqa: BLE001
                out.append(p.name + "  [UNREADABLE]")
    except OSError as exc:
        return [f"<{exc}>"]
    return out


def row(d) -> dict:
    return {
        "saved_combo": [d._saved_combo.itemText(i)
                        for i in range(d._saved_combo.count())],
        "index": d._saved_combo.currentIndex(),
        "delete_enabled": d._delete_report_btn.isEnabled(),
        "note": d._saved_note_full,
        "history": len(d._history),
    }


def pick(d, name: str) -> bool:
    for i in range(d._saved_combo.count()):
        data = d._saved_combo.itemData(i)
        if data and data[1] == name:
            d._saved_combo.setCurrentIndex(i)
            d._on_saved_chosen(i)
            return True
    return False


def main() -> int:                                   # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
    assert not os.environ.get("QT_QPA_PLATFORM"), "ON SCREEN IS THE DEFAULT"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    R: dict = {}
    crashes: list = []
    prev = sys.excepthook
    sys.excepthook = lambda t, e, tb: (
        crashes.append("".join(traceback.format_exception(t, e, tb))),
        prev(t, e, tb))

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r3d-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("restore_last_session", False)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    R["work"] = str(work)
    R["locked_at_start"] = session_is_locked()
    print(f"    screen locked at start: {R['locked_at_start']}", flush=True)

    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")

    # The confirmation is RECORDED and answered per press.
    said: list = []
    answer = {"say": True, "before": None}
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    def _confirm(self, t, b):
        said.append({"title": t, "body": b})
        if answer["before"] is not None:
            answer["before"]()
        return answer["say"]

    MeasurementReportDialog._confirm = _confirm           # type: ignore
    warned: list = []
    from ui import warning_sign
    warning_sign.warn = lambda *a, **k: warned.append(a[1:])   # type: ignore
    import ui.dialogs.measurement_report_dialog as MRD
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    assert MRD is not None

    def fresh(tag: str) -> Path:
        p = work / f"Demo-Switching-{tag}"
        shutil.copytree(SOURCE, p, symlinks=True)
        return p

    def verif(proj: Path, date: str = DATE) -> Path:
        return proj / "runs" / "run2" / "verifications" / date

    def open_on(ti3: Path):
        d = MeasurementReportDialog(settings, None, initial_ti3=ti3)
        d.resize(1500, 1050)
        d.show()
        pump(app, 3000)
        return d

    shots = []

    def shoot(d, name):
        ok, why = capture_window(d, out / name)
        shots.append({"file": name, "ok": ok, "why": why})
        print(f"    capture {name}: {ok} {why}", flush=True)

    # ---------------------------------------------------------------- A
    print("\n=== A  the last saved report of a dated verification", flush=True)
    pA = fresh("A")
    vA = verif(pA)
    rA = vA / "reports"
    dA = open_on(vA / VERIF_TI3)
    only = on_disk(rA)[0]
    picked = pick(dA, only)
    pump(app, 1200)
    R["A"] = {"folder_before": on_disk(rA), "picked": picked, "row": row(dA)}
    shoot(dA, "A-the-last-report-of-a-dated-verification.png")
    n_said = len(said)
    dA._on_delete_report()                       # the press, refused or not
    pump(app, 1500)
    R["A"]["confirmation_asked"] = len(said) > n_said
    R["A"]["folder_after"] = on_disk(rA)
    R["A"]["row_after"] = row(dA)
    shoot(dA, "A-after-the-refused-press.png")
    print(f"    {R['A']['folder_before']} -> {R['A']['folder_after']}", flush=True)
    print(f"    delete enabled={R['A']['row']['delete_enabled']} "
          f"note={R['A']['row']['note']!r}", flush=True)
    dA.close(); pump(app, 500)

    # ---------------------------------------------------------------- B
    print("\n=== B  one of several saved reports of one date", flush=True)
    pB = fresh("B")
    vB = verif(pB)
    rB = vB / "reports"
    src = sorted(rB.glob("report_*.json"))[0]
    spare = rB / (src.stem + "_2.json")
    shutil.copy2(src, spare)
    assert spare.is_file()
    dB = open_on(vB / VERIF_TI3)
    R["B"] = {"folder_before": on_disk(rB), "combo": row(dB)}
    pick(dB, spare.name)
    pump(app, 1200)
    R["B"]["on_the_spare"] = row(dB)
    shoot(dB, "B-two-reports-on-one-date.png")
    n_said = len(said)
    dB._on_delete_report()
    pump(app, 2000)
    R["B"]["confirmation"] = said[-1] if len(said) > n_said else None
    R["B"]["folder_after_first_delete"] = on_disk(rB)
    R["B"]["row_after_first_delete"] = row(dB)
    shoot(dB, "B-after-the-spare-went.png")
    # …and now the last one must be refused.
    left = on_disk(rB)
    if left:
        pick(dB, left[0])
        pump(app, 1200)
        R["B"]["on_the_last_one"] = row(dB)
        n_said = len(said)
        dB._on_delete_report()
        pump(app, 1500)
        R["B"]["second_press_asked"] = len(said) > n_said
        R["B"]["folder_after_second_press"] = on_disk(rB)
        shoot(dB, "B-after-the-refused-second-press.png")
    print(f"    {R['B']['folder_before']} -> {R['B']['folder_after_first_delete']}"
          f" -> {R['B'].get('folder_after_second_press')}", flush=True)
    dB.close(); pump(app, 500)

    # ---------------------------------------------------------------- C
    print("\n=== C  the chosen report's file removed under the app", flush=True)
    pC = fresh("C")
    vC = verif(pC)
    rC = vC / "reports"
    src = sorted(rC.glob("report_*.json"))[0]
    spare = rC / (src.stem + "_2.json")
    shutil.copy2(src, spare)
    dC = open_on(vC / VERIF_TI3)
    pick(dC, spare.name)
    pump(app, 1200)
    R["C"] = {"folder_before": on_disk(rC), "row": row(dC)}
    spare.unlink()                      # removed UNDER the app, window open
    R["C"]["folder_after_external_removal"] = on_disk(rC)
    n_said, n_warn = len(said), len(warned)
    dC._on_delete_report()
    pump(app, 2000)
    R["C"]["confirmation"] = said[-1] if len(said) > n_said else None
    R["C"]["warned"] = warned[n_warn:]
    R["C"]["folder_after_press"] = on_disk(rC)
    R["C"]["row_after"] = row(dC)
    shoot(dC, "C-after-a-press-on-a-file-that-is-gone.png")
    print(f"    confirmation: {R['C']['confirmation']}", flush=True)
    print(f"    warned: {R['C']['warned']}", flush=True)
    print(f"    folder: {R['C']['folder_after_press']}", flush=True)
    dC.close(); pump(app, 500)

    # ---------------------------------------------------------------- D
    print("\n=== D  the folder made read-only between confirm and press",
          flush=True)
    pD = fresh("D")
    vD = verif(pD)
    rD = vD / "reports"
    src = sorted(rD.glob("report_*.json"))[0]
    spare = rD / (src.stem + "_2.json")
    shutil.copy2(src, spare)
    dD = open_on(vD / VERIF_TI3)
    pick(dD, spare.name)
    pump(app, 1200)
    R["D"] = {"folder_before": on_disk(rD), "row": row(dD)}
    answer["before"] = lambda: os.chmod(rD, stat.S_IRUSR | stat.S_IXUSR)
    n_said, n_warn = len(said), len(warned)
    dD._on_delete_report()
    pump(app, 2000)
    answer["before"] = None
    R["D"]["confirmation"] = said[-1] if len(said) > n_said else None
    R["D"]["warned"] = warned[n_warn:]
    os.chmod(rD, 0o755)
    R["D"]["folder_after"] = on_disk(rD)
    R["D"]["row_after"] = row(dD)
    shoot(dD, "D-after-a-press-into-a-read-only-folder.png")
    print(f"    warned: {R['D']['warned']}", flush=True)
    print(f"    folder: {R['D']['folder_after']}", flush=True)
    dD.close(); pump(app, 500)

    # ---------------------------------------------------------------- E
    print("\n=== E  two dates, one holding no report at all", flush=True)
    pE = fresh("E")
    other = sorted(p for p in (pE / "runs" / "run2" / "verifications").iterdir()
                   if p.is_dir() and p.name not in ("old", "cache", "exports",
                                                    "reports"))
    R["E"] = {"dates": [p.name for p in other]}
    empty = [p for p in other if p.name != DATE][0]
    for p in (empty / "reports").glob("report_*.json"):
        p.unlink()
    R["E"]["emptied"] = empty.name
    R["E"]["emptied_folder"] = on_disk(empty / "reports")
    vE = verif(pE)
    dE = open_on(vE / VERIF_TI3)
    R["E"]["folder_before"] = on_disk(vE / "reports")
    only = on_disk(vE / "reports")[0]
    pick(dE, only)
    pump(app, 1200)
    R["E"]["row"] = row(dE)
    n_said = len(said)
    dE._on_delete_report()
    pump(app, 1500)
    R["E"]["confirmation_asked"] = len(said) > n_said
    R["E"]["folder_after"] = on_disk(vE / "reports")
    shoot(dE, "E-two-dates-one-of-them-empty.png")
    print(f"    delete enabled={R['E']['row']['delete_enabled']} "
          f"note={R['E']['row']['note']!r}", flush=True)
    print(f"    {R['E']['folder_before']} -> {R['E']['folder_after']}", flush=True)
    dE.close(); pump(app, 500)

    # ---------------------------------------------------------------- F
    print("\n=== F  a delete straight after a Generate, with no re-pick",
          flush=True)
    pF = fresh("F")
    vF = verif(pF)
    rF = vF / "reports"
    dF = open_on(vF / VERIF_TI3)
    R["F"] = {"folder_before": on_disk(rF), "row_before": row(dF)}
    dF._on_generate_report()
    pump(app, 3000)
    R["F"]["folder_after_generate"] = on_disk(rF)
    R["F"]["row_after_generate"] = row(dF)
    shoot(dF, "F-straight-after-a-generate.png")
    n_said = len(said)
    dF._on_delete_report()
    pump(app, 2000)
    R["F"]["confirmation"] = said[-1] if len(said) > n_said else None
    R["F"]["folder_after_delete"] = on_disk(rF)
    R["F"]["row_after_delete"] = row(dF)
    shoot(dF, "F-after-the-delete.png")
    print(f"    {R['F']['folder_before']} -> {R['F']['folder_after_generate']}"
          f" -> {R['F']['folder_after_delete']}", flush=True)
    print(f"    confirmation: {R['F']['confirmation']}", flush=True)
    dF.close(); pump(app, 500)

    # ---------------------------------------------------------------- G
    print("\n=== G  a report_*.json the window cannot read, beside the only "
          "one it can", flush=True)
    pG = fresh("G")
    vG = verif(pG)
    rG = vG / "reports"
    good = sorted(rG.glob("report_*.json"))[0]
    broken = rG / (good.stem + "_2.json")
    broken.write_text(good.read_text(encoding="utf-8")[:120], encoding="utf-8")
    R["G"] = {"folder_before": on_disk(rG)}
    dG = open_on(vG / VERIF_TI3)
    pick(dG, good.name)
    pump(app, 1200)
    R["G"]["row"] = row(dG)
    shoot(dG, "G-one-readable-report-and-one-truncated-file.png")
    n_said = len(said)
    dG._on_delete_report()
    pump(app, 2000)
    R["G"]["confirmation"] = said[-1] if len(said) > n_said else None
    R["G"]["folder_after"] = on_disk(rG)
    R["G"]["row_after"] = row(dG)
    shoot(dG, "G-after-the-press.png")
    print(f"    delete enabled={R['G']['row']['delete_enabled']} "
          f"note={R['G']['row']['note']!r}", flush=True)
    print(f"    {R['G']['folder_before']} -> {R['G']['folder_after']}", flush=True)
    print(f"    confirmation: {R['G']['confirmation']}", flush=True)
    dG.close(); pump(app, 500)

    R["captures"] = shots
    R["crashes"] = crashes
    R["confirmations_seen"] = said
    (out / "delete-round3.json").write_text(
        json.dumps(R, indent=2, default=str), encoding="utf-8")
    print(f"\n    crashes: {len(crashes)}", flush=True)
    print(f"    written: {out / 'delete-round3.json'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
