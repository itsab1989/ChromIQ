#!/usr/bin/env python3
"""The Reference values window with Fogra in it, driven on screen.

Part A of the Fogra reference-set work: ChromIQ ships the current sets, and a
user may point it at a NEWER file, per set, without a new ChromIQ. Sebastian,
2026-09-20: *"we could ship the most recent version and allow for a way to use
newer values if they are released at some point in the future without relying
on an update to ChromIQ for it."*

**EVERY CONTROL IS PRESSED IN A REAL WINDOW.** CLAUDE.md's rule, and this
window's own history: beta 26 shipped three buttons that raised `NameError` on
every press and looked merely inert, past three green gates, because the guard
READ THEIR SOURCE. The detector that round lacked is here:

  **A RECORDING `sys.excepthook`.** PyQt6 6.11 does not call `qFatal()` for an
  exception raised in a slot; it calls `sys.excepthook` and the app carries on,
  so a press that raises leaves the window looking fine.

Scenes
  A  the door in Report limits: still ONE button, with two sources behind it
  B  the window: two sections, ISO's one line and Fogra's eleven
  C  a newer file for a set that SHIPS  (FOGRA51)
  D  a file for a set that ships NOWHERE (FOGRA61, still beta at Fogra)
  E  "Stop using it" on each of them, and what each goes back to
  F  rubbish, and the sentence the user gets
  G  the whole archive as a .zip, exactly as Fogra publishes it
  H  the ISO section still works, because that is what this change could break

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-fogra/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-fogra/presets
    python scripts/drive_fogra_reference_values_onscreen.py <out-dir> [en|de]
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtWidgets import (QApplication, QLabel,                # noqa: E402
                             QPushButton)
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

#: Fogra's own files, unpacked from the archive Fogra publishes. Used when they
#: are there and synthesised when they are not, so the driver runs anywhere.
FOGRA_DIR = Path("/Users/Basti/.claude/jobs/c4ec4e71/tmp/fogra/"
                 "Fogra Characterisation Data")

RAISED: list = []
BOXES: list = []
OUT = Path(".")
WANT_PHOTO: dict = {"tag": None}


def install_recorder() -> None:
    prev = sys.excepthook

    def hook(t, e, tb):
        RAISED.append({"type": t.__name__, "msg": str(e),
                       "tb": "".join(traceback.format_tb(tb))[-600:]})
        prev(t, e, tb)

    sys.excepthook = hook


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _same(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        return x.shape == y.shape and bool((np.abs(x - y).sum(2) > tol).sum() == 0)
    except Exception:                                       # noqa: BLE001
        return False


def photo(app, win, tag: str) -> dict:
    """TWO PIXEL-IDENTICAL FRAMES OR IT IS NOT A PHOTOGRAPH. A single frame can
    catch a window mid-relayout and prove the opposite of what it is filed as."""
    ok = ok2 = False
    why = ""
    for _ in range(3):
        pump(app, 650)
        ok, why = capture_window(win, OUT / f"{tag}-1.png")
        pump(app, 650)
        ok2, why2 = capture_window(win, OUT / f"{tag}-2.png")
        why = why or why2
        if ok and ok2 and _same(OUT / f"{tag}-1.png", OUT / f"{tag}-2.png"):
            return {"taken": True, "identical": True,
                    "file": f"{tag}-1.png"}
    return {"taken": bool(ok and ok2), "identical": False, "why": why}


class BoxWatcher:
    """Standing watcher: close every InfoDialog that appears and say what it
    said. A one-shot handler hung an earlier driver for nine minutes inside
    `QDialog::exec`; this cannot, and its log is the evidence for a scene that
    must raise NO box at all."""

    def __init__(self, app):
        self.app = app
        self.t = QTimer()
        self.t.setInterval(140)
        self.t.timeout.connect(self.tick)
        self.t.start()

    def tick(self) -> None:
        from ui.tooltip_button import InfoDialog
        box = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, InfoDialog) and w.isVisible()), None)
        if box is None:
            return
        texts = [(x.text() or "").strip() for x in box.findChildren(QLabel)]
        rec = {"title": box.windowTitle(),
               "texts": [t for t in texts if t][:6]}
        tag = WANT_PHOTO.get("tag")
        if tag:
            WANT_PHOTO["tag"] = None
            rec["photo"] = photo(self.app, box, tag)
        for b in box.findChildren(QPushButton):
            if b.isVisible():
                b.click()
                break
        else:
            box.accept()
        BOXES.append(rec)

    def stop(self) -> None:
        self.t.stop()
        self.t.timeout.disconnect()


def boxes_since(n: int) -> list:
    return BOXES[n:]


# ---------------------------------------------------------------------------
# Material: Fogra's own files where they exist, synthesised where they do not
# ---------------------------------------------------------------------------
def _cgats(descriptor: str, fields: str, rows: "list[str]") -> bytes:
    body = ["ISO28178", f'FILE_DESCRIPTOR\t"{descriptor}"',
            'ORIGINATOR\t"Fogra, www.fogra.org"', 'CREATED\t"May 2015"',
            f"NUMBER_OF_FIELDS\t{len(fields.split())}", "BEGIN_DATA_FORMAT",
            fields, "END_DATA_FORMAT", f"NUMBER_OF_SETS\t{len(rows)}",
            "BEGIN_DATA", *rows, "END_DATA", ""]
    return "\r\n".join(body).encode("utf-8")


def material(work: Path) -> dict:
    """Returns ``{name: path}`` and says which ones are Fogra's own bytes."""
    out: dict = {"real": []}
    pairs = [("fogra51", FOGRA_DIR / "subs" / "FOGRA51_MW3_Subset.txt"),
             ("fogra61", FOGRA_DIR / "FOGRA61_beta.txt"),
             ("zip", FOGRA_DIR / "MK3_Subsets_FOGRA39_until_FOGRA60.zip")]
    for key, src in pairs:
        if src.is_file():
            dst = work / src.name
            shutil.copyfile(src, dst)
            out[key] = dst
            out["real"].append(key)
    if "fogra51" not in out:
        p = work / "FOGRA51_MW3_Subset.txt"
        p.write_bytes(_cgats(
            "FOGRA51_MW3_Subset",
            "SAMPLE_ID\tCMYK_C\tCMYK_M\tCMYK_Y\tCMYK_K\tLAB_L\tLAB_A\tLAB_B",
            ["1\t0\t0\t0\t0\t95.10\t1.40\t-6.10",
             "2\t100\t0\t0\t0\t56.12\t-34.90\t-52.52"]))
        out["fogra51"] = p
    if "fogra61" not in out:
        p = work / "FOGRA61_beta.txt"
        p.write_bytes(_cgats(
            "3D-DesignRGB_FOGRA61(beta)",
            "SAMPLE_ID\tRGB_R\tRGB_G\tRGB_B\tLAB_L\tLAB_A\tLAB_B",
            ["1\t0.00\t0.00\t0.00\t11.000\t0.000\t0.000",
             "3\t255.00\t255.00\t255.00\t91.000\t-1.000\t4.000"]))
        out["fogra61"] = p
    if "zip" not in out:
        p = work / "MK3_Subsets.zip"
        with zipfile.ZipFile(p, "w") as z:
            for n in ("FOGRA47", "FOGRA52", "FOGRA57"):
                z.writestr(f"subs/{n}_MW3_Subset.txt", _cgats(
                    f"{n}_MW3_Subset",
                    "SAMPLE_ID\tCMYK_C\tCMYK_M\tCMYK_Y\tCMYK_K\t"
                    "LAB_L\tLAB_A\tLAB_B",
                    ["1\t0\t0\t0\t0\t94.0\t1.0\t-5.0"]))
        out["zip"] = p
    rubbish = work / "holiday-photo-notes.txt"
    rubbish.write_text("Dear Fogra,\r\nplease send the data.\r\n",
                       encoding="utf-8")
    out["rubbish"] = rubbish
    return out


# ---------------------------------------------------------------------------
def main() -> int:                                              # noqa: C901
    global OUT
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    OUT = Path(sys.argv[1]).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 780

    install_recorder()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("appearance", "light")
    settings.set("language", lang)
    from core import i18n
    i18n.set_language(lang)
    # THE APP'S OWN STYLESHEET, OR EVERY SIZE MEASURED HERE IS FICTION. A shown
    # widget whose driver never called this is the third of the four ways a
    # guard has lied on this project in three days.
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")

    from workflow import reference_sets as rs
    from workflow import compliance_sets as cs
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    import ui.widgets as W

    # a clean slate inside the sandbox, and PROOF it is inside it
    assert "/tmp/chromiq-fogra" in str(rs.user_dir()), rs.user_dir()
    shutil.rmtree(rs.user_dir(), ignore_errors=True)
    if cs.user_values_path().is_file():
        cs.user_values_path().unlink()
    rs.reset_cache()
    cs.reset_iso_cache()

    work = Path(tempfile.mkdtemp(prefix="chromiq-fogra-drive-"))
    mat = material(work)
    res: dict = {"lang": lang, "width": width,
                 "locked_at_start": session_is_locked(),
                 "user_dir": str(rs.user_dir()),
                 "fogra_files_are_fogras_own": mat["real"]}
    watcher = BoxWatcher(app)

    answer: dict = {"open": "", "save": "", "open_kw": {}, "save_kw": {}}
    W.save_file_dialog = lambda *a, **k: (answer.__setitem__("save_kw", k),
                                          answer["save"])[1]
    W.open_file_dialog = lambda *a, **k: (answer.__setitem__("open_kw", k),
                                          answer["open"])[1]

    def lines(dlg, key):
        return [lbl.text() for s, _k, lbl, _b in dlg._rows if s.key == key]

    def row(dlg, key, item):
        return next((r for r in dlg._rows
                     if r[0].key == key and r[1] == item), None)

    def press_install(dlg, src_key, path, tag=None):
        src = next(s for s in dlg._sources if s.key == src_key)
        n = len(BOXES)
        RAISED.clear()
        answer["open"] = str(path)
        if tag:
            WANT_PHOTO["tag"] = tag
        btn = next(b for b in dlg.findChildren(QPushButton)
                   if b.text() == src.install_label)
        btn.click()
        pump(app, 2600)
        return {"button": btn.text(), "raised": list(RAISED),
                "boxes": boxes_since(n),
                "dialog_kwargs": {k: str(v) for k, v in answer["open_kw"].items()}}

    def press_stop(dlg, src_key, item, tag=None):
        r = row(dlg, src_key, item)
        if r is None:
            return {"error": f"no row for {src_key}/{item}"}
        n = len(BOXES)
        RAISED.clear()
        if tag:
            WANT_PHOTO["tag"] = tag
        visible, enabled = r[3].isVisible(), r[3].isEnabled()
        r[3].click()
        pump(app, 2600)
        return {"was_visible": visible, "was_enabled": enabled,
                "raised": list(RAISED), "boxes": boxes_since(n)}

    # =====================================================================
    # A. THE DOOR: one button, two sources behind it
    # =====================================================================
    th = ThresholdsDialog(settings, None)
    th.resize(1240, 820)
    th.show(); th.raise_(); th.activateWindow()
    pump(app, 1800)
    doors = [b.text() for b in th.findChildren(QPushButton)
             if "reference" in (b.text() or "").lower()
             or "referenz" in (b.text() or "").lower()]
    res["A_door"] = {
        "window_visible": th.isVisible(),
        "doors": doors,
        "door_count": len(doors),
        "door_height": th._iso_values_btn.height(),
        "photo": photo(app, th, f"A-report-limits-{lang}"),
    }
    th.close()
    pump(app, 400)

    # =====================================================================
    # B. THE WINDOW, as a user first meets it
    # =====================================================================
    # NO RESIZE. The window is photographed at the size it opens at, because
    # that is the size a person meets; a driver that picks its own is
    # measuring a window nobody has. `width` is recorded, not applied.
    dlg = ReferenceValuesDialog(None)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 1500)
    res["B_first_open"] = {
        "visible": dlg.isVisible(),
        "title": dlg.windowTitle(),
        "sources": [s.key for s in dlg._sources],
        "iso_lines": lines(dlg, "iso12647"),
        "fogra_lines": lines(dlg, "fogra"),
        "fogra_row_count": len(lines(dlg, "fogra")),
        "buttons": [b.text() for b in dlg.findChildren(QPushButton)
                    if b.isVisible()],
        "iso_stop_visible": row(dlg, "iso12647", "iso12647")[3].isVisible(),
        "iso_stop_enabled": row(dlg, "iso12647", "iso12647")[3].isEnabled(),
        "fogra_stops_visible": [r[3].isVisible() for r in dlg._rows
                                if r[0].key == "fogra"],
        "size": [dlg.width(), dlg.height()],
        "raised": list(RAISED),
        "photo": photo(app, dlg, f"B-window-first-open-{lang}"),
    }

    # =====================================================================
    # C. A NEWER FILE FOR A SET THAT SHIPS
    # =====================================================================
    res["C_newer_fogra51"] = press_install(dlg, "fogra", mat["fogra51"],
                                           f"C-said-{lang}")
    pump(app, 900)
    res["C_newer_fogra51"].update({
        "line_now": [ln for ln in lines(dlg, "fogra") if "51" in ln],
        "stop_now_visible": row(dlg, "fogra", "FOGRA51")[3].isVisible(),
        "stop_now_enabled": row(dlg, "fogra", "FOGRA51")[3].isEnabled(),
        "other_sets_untouched": [ln for ln in lines(dlg, "fogra")
                                 if "52" in ln],
        "supplied_by_user": rs.by_id("FOGRA51").supplied_by_user,
        "still_coated": rs.by_id("FOGRA51").group,
        "photo": photo(app, dlg, f"C-fogra51-is-yours-{lang}"),
    })

    # =====================================================================
    # D. A SET CHROMIQ SHIPS NOTHING FOR
    # =====================================================================
    before = len(lines(dlg, "fogra"))
    res["D_fogra61"] = press_install(dlg, "fogra", mat["fogra61"])
    pump(app, 900)
    res["D_fogra61"].update({
        "rows_before": before,
        "rows_after": len(lines(dlg, "fogra")),
        "line": [ln for ln in lines(dlg, "fogra") if "61" in ln],
        "in_bundled_list": any(s.id == "FOGRA61" for s in rs.bundled()),
        "credit_line": (rs.by_id("FOGRA61").credit_line
                        if rs.by_id("FOGRA61") else ""),
        "photo": photo(app, dlg, f"D-fogra61-arrived-{lang}"),
    })

    # =====================================================================
    # E. STOP USING IT, both kinds
    # =====================================================================
    res["E_stop_fogra51"] = press_stop(dlg, "fogra", "FOGRA51",
                                       f"E-stop-said-{lang}")
    pump(app, 900)
    res["E_stop_fogra51"].update({
        "line_now": [ln for ln in lines(dlg, "fogra") if "51" in ln],
        "supplied_by_user": rs.by_id("FOGRA51").supplied_by_user,
    })
    res["E_stop_fogra61"] = press_stop(dlg, "fogra", "FOGRA61")
    pump(app, 900)
    res["E_stop_fogra61"].update({
        "row_gone": not [ln for ln in lines(dlg, "fogra") if "61" in ln],
        "rows_now": len(lines(dlg, "fogra")),
        "files_left": sorted(p.name for p in rs.user_dir().iterdir())
                      if rs.user_dir().is_dir() else [],
        "photo": photo(app, dlg, f"E-back-to-what-shipped-{lang}"),
    })

    # =====================================================================
    # F. RUBBISH, AND THE SENTENCE THE USER GETS
    # =====================================================================
    res["F_rubbish"] = press_install(dlg, "fogra", mat["rubbish"],
                                     f"F-refusal-{lang}")
    pump(app, 600)
    res["F_rubbish"].update({
        "nothing_installed": rs.user_record() == {},
        "rows_now": len(lines(dlg, "fogra")),
    })

    # =====================================================================
    # G. THE WHOLE ARCHIVE, AS FOGRA PUBLISHES IT
    # =====================================================================
    res["G_zip"] = press_install(dlg, "fogra", mat["zip"], f"G-zip-said-{lang}")
    pump(app, 1200)
    res["G_zip"].update({
        "rows_now": len(lines(dlg, "fogra")),
        "yours_now": sum(1 for r in dlg._rows
                         if r[0].key == "fogra" and r[3].isVisible()),
        "sets": sorted(rs.user_record()),
        "photo": photo(app, dlg, f"G-a-whole-archive-{lang}"),
    })

    # =====================================================================
    # H. THE ISO SECTION STILL WORKS
    # =====================================================================
    iso = next(s for s in dlg._sources if s.key == "iso12647")
    tmpl = work / "iso12647.json"
    answer["save"] = str(tmpl)
    n = len(BOXES); RAISED.clear()
    tbtn = next(b for b in dlg.findChildren(QPushButton)
                if b.text() == iso.template.label)
    tbtn.click(); pump(app, 2200)
    res["H_iso_template"] = {"raised": list(RAISED), "boxes": boxes_since(n),
                             "written": tmpl.is_file(),
                             "bytes": tmpl.stat().st_size if tmpl.is_file() else 0}
    if tmpl.is_file():
        doc = json.loads(tmpl.read_text(encoding="utf-8"))
        for sid, v in doc.items():
            if not sid.startswith("_") and isinstance(v, dict):
                for rid in v:
                    v[rid] = 2.5
        tmpl.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    res["H_iso_install"] = press_install(dlg, "iso12647", tmpl)
    pump(app, 900)
    res["H_iso_install"].update({
        "line_now": lines(dlg, "iso12647"),
        "stop_enabled": row(dlg, "iso12647", "iso12647")[3].isEnabled(),
        "file_in_place": cs.user_values_path().is_file(),
        "photo": photo(app, dlg, f"H-iso-still-works-{lang}"),
    })
    res["H_iso_stop"] = press_stop(dlg, "iso12647", "iso12647")
    pump(app, 900)
    res["H_iso_stop"].update({
        "line_now": lines(dlg, "iso12647"),
        "file_gone": not cs.user_values_path().is_file(),
    })

    # =====================================================================
    res["boxes_all"] = BOXES
    res["raised_anywhere"] = RAISED
    watcher.stop()
    dlg.close()
    pump(app, 400)
    (OUT / f"result-{lang}.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    photos = [v.get("photo") for v in res.values() if isinstance(v, dict)]
    good = [p for p in photos if isinstance(p, dict) and p.get("identical")]
    print(f"[{lang}] wrote result-{lang}.json  "
          f"photographs {len(good)}/{len([p for p in photos if p])} identical, "
          f"exceptions {len(RAISED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
