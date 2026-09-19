#!/usr/bin/env python3
"""Adversary round 29, focused: the two Generate doors the round never opened.

Each runs on its OWN fresh copy and its OWN fresh window, and there is exactly
ONE popup handler alive at a time: it answers the three-button question with
the button named, then goes on watching and records whatever box comes next.

  A. **Update a report whose file has gone from disk under the window.**
  B. **Create New / Update with the reports folder read-only.**

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-r29/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-r29/presets
    python scripts/adv29_two_doors.py <project> <out>
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
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox            # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        if x.shape != y.shape:
            return False
        return bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                      # noqa: BLE001
        return False


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def capture_settled(app, win, first: Path, second: Path, tries: int = 3):
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 700)
        ok, why = capture_window(win, first)
        pump(app, 700)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return True, why, n, True
    return bool(ok and ok2), why, tries, False


#: every handler ever armed, so the one before can be KILLED before the next is
#: armed.  A handler left polling from the previous press wakes up during this
#: one, answers the box with its default and hands the window a "cancel" nobody
#: asked for -- which is exactly what happened on the first run of this probe
#: and made a working Update look like a dead button.
LIVE: "list[dict]" = []


def stop_handlers() -> None:
    for h in LIVE:
        h["done"] = True
    LIVE.clear()


def answer_boxes(app, out, tag, label, ticks=40):
    """ONE handler. Presses *label* in the first box, records every box after."""
    stop_handlers()
    seen = {"boxes": [], "pressed": None, "tries": 0}
    LIVE.append(seen)

    def _act():
        if seen.get("done"):
            return
        box = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, QMessageBox) and w.isVisible()), None)
        if box is None:
            seen["tries"] += 1
            if seen["tries"] > ticks:
                seen["done"] = True
                return
            QTimer.singleShot(250, _act)
            return
        rec = {"text": box.text(), "informative": box.informativeText(),
               "buttons": [b.text().replace("&", "") for b in box.buttons()]}
        if out is not None and not seen["boxes"]:
            ok, why, _t, same = capture_settled(
                app, box, out / f"{tag}-box-1.png", out / f"{tag}-box-2.png")
            rec["photo"] = {"taken": ok, "why": why, "identical": same}
        hit = next((b for b in box.buttons()
                    if b.text().replace("&", "") == label), None)
        if hit is not None and seen["pressed"] is None:
            rec["pressed"] = label
            seen["pressed"] = label
            seen["boxes"].append(rec)
            hit.click()
        else:
            rec["pressed"] = "(default)"
            seen["boxes"].append(rec)
            box.accept()
        seen["tries"] = 0
        QTimer.singleShot(250, _act)

    QTimer.singleShot(300, _act)
    return seen


def files(d: Path) -> list:
    return sorted(str(p.relative_to(d)) for p in d.rglob("report_*.json"))


def state(dlg) -> dict:
    try:
        upd = dlg._document_being_updated()
    except Exception as exc:                                # noqa: BLE001
        upd = f"RAISED {exc!r}"
    try:
        n = len(dlg._reports_to_generate())
    except Exception as exc:                                # noqa: BLE001
        n = f"RAISED {exc!r}"
    return {
        "entry": dlg._saved_combo.currentText(),
        "loaded_doc_id": str(dlg._loaded_doc_id),
        "red_line": dlg._stale_label.isVisible(),
        "settings_modified": dlg._settings_were_modified(),
        "document_being_updated": (None if upd is None
                                   else (upd if isinstance(upd, str)
                                         else upd.get("key"))),
        "reports_to_generate": n,
        "run_ctx": dlg._run_ctx is not None,
        "generate_enabled": dlg._generate_btn.isEnabled(),
    }


def setup(app, src, tag):
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix=f"chromiq-r29-{tag}-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "light")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    from core.file_manager import FileManager
    fm = FileManager(settings); del fm
    ti3 = sorted((dest / "runs" / "run1" / "verifications"
                  / "2026-11-16_100000").glob("*.ti3"))[0]
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1480, 1000)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 2500)
    return settings, dest, dlg


def main() -> int:                                          # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    res = {"locked_at_start": session_is_locked()}
    print(f"    screen locked at start: {res['locked_at_start']}", flush=True)

    # =================== A. the file is gone ============================
    _s, dest, dlg = setup(app, src, "gone")
    A = {"window_visible": dlg.isVisible(), "files_at_start": len(files(dest))}
    # make a real document first
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 900)
    h = answer_boxes(app, out, "A0", "Update")
    dlg._on_generate_report()
    pump(app, 3000)
    made = str(dlg._loaded_doc_id)
    A["made"] = {"doc": made, "boxes": h["boxes"], "files": len(files(dest))}
    print(f"  A0 made {made}  boxes={[b['buttons'] for b in h['boxes']]}",
          flush=True)
    # find its files and DELETE them
    gone = []
    for d in dlg._saved_documents(dlg._run_ctx.run):
        if d["key"] == made:
            for r, n in (d.get("members") or []):
                p = Path(str(r.get("_origin_dir"))) / "reports" / n
                if p.exists():
                    p.unlink()
                    gone.append(str(p.relative_to(dest)))
    A["deleted"] = gone
    A["files_after_delete"] = len(files(dest))
    A["state_after_delete"] = state(dlg)
    print(f"  A1 deleted {gone}", flush=True)
    print(f"     state {json.dumps(A['state_after_delete'])}", flush=True)
    dlg._all_runs_check.setChecked(not dlg._all_runs_check.isChecked())
    pump(app, 1200)
    A["state_after_moving_a_setting"] = state(dlg)
    print(f"  A2 after moving a setting "
          f"{json.dumps(A['state_after_moving_a_setting'])}", flush=True)
    h2 = answer_boxes(app, out, "A2", "Update")
    dlg._on_generate_report()
    pump(app, 3500)
    A["press"] = {"boxes": h2["boxes"], "pressed": h2["pressed"],
                  "files_after": len(files(dest)),
                  "file_list": files(dest),
                  "state": state(dlg)}
    print(f"  A3 pressed Generate: boxes={len(h2['boxes'])} "
          f"pressed={h2['pressed']} files {A['files_after_delete']} -> "
          f"{A['press']['files_after']}", flush=True)
    ok, why, _t, same = capture_settled(app, dlg, out / "A-after-1.png",
                                        out / "A-after-2.png")
    A["photo"] = {"taken": ok, "why": why, "identical": same}
    print(f"     photograph: {ok} {why}; identical {same}", flush=True)
    res["A_file_is_gone"] = A
    dlg.close(); pump(app, 600)

    # =================== B. the folder is read-only =====================
    _s2, dest2, dlg2 = setup(app, src, "ro")
    B = {"window_visible": dlg2.isVisible()}
    dlg2._detail_check.setChecked(not dlg2._detail_check.isChecked())
    pump(app, 900)
    B["state_before"] = state(dlg2)
    folders = sorted({p.parent for p in dest2.rglob("report_*.json")})
    modes = {}
    for f in folders:
        modes[str(f)] = f.stat().st_mode
        os.chmod(f, stat.S_IRUSR | stat.S_IXUSR)
    B["locked"] = sorted(modes)
    before = files(dest2)
    try:
        h3 = answer_boxes(app, out, "B", "Update")
        dlg2._on_generate_report()
        pump(app, 4000)
        B["press"] = {"boxes": h3["boxes"], "pressed": h3["pressed"],
                      "files_before": len(before),
                      "files_after": len(files(dest2)),
                      "state": state(dlg2)}
        print(f"  B  read-only Update: boxes="
              f"{[b.get('text','')[:60] for b in h3['boxes']]} "
              f"files {len(before)} -> {B['press']['files_after']}", flush=True)
        print(f"     state {json.dumps(B['press']['state'])}", flush=True)
        ok, why, _t, same = capture_settled(app, dlg2, out / "B-after-1.png",
                                            out / "B-after-2.png")
        B["photo"] = {"taken": ok, "why": why, "identical": same}
        print(f"     photograph: {ok} {why}; identical {same}", flush=True)
    finally:
        for f, m in modes.items():
            try:
                os.chmod(f, m)
            except OSError:
                pass
    res["B_read_only"] = B
    dlg2.close(); pump(app, 600)

    res["locked_at_end"] = session_is_locked()
    (out / "two-doors.json").write_text(json.dumps(res, indent=2, default=str),
                                        encoding="utf-8")
    print(f"    wrote {out / 'two-doors.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                      # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
