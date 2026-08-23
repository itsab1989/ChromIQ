#!/usr/bin/env python3
"""Screenshots of everything #164 changed, taken from the REAL window.

Pairs with ``scripts/drive_k_feedback_repro.py``, which recorded the same places
before the fixes. Each shot is named for the claim it settles:

  1_markers_group          the new "Show markers for" row, with its ⓘ
  2_markers_group_off      …and the whole group greyed with the tick box
  3_clip_cm_<mode>         the clip Preview + "Clip area" on a ColorMunki
  4_clip_notes_disabled    the Text field now LOOKS disabled in Notes-box mode
  5_clip_branding_place    branding with the image's placement controls
  6_help_card_print        the Print… button on a Help card
  7_overlay_proposal       the preview overlay when it is not on the sheet yet

    python scripts/drive_164_after_shots.py [--out DIR]

Basti's preferences are copied into a throwaway .ini — nothing of his is
touched. Shots land in --out (default: ~/Desktop/chromiq-164-after).
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
TI1 = ROOT / "tests/fixtures/charts/cm_a4_480p_2pages.ti1"


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(widget, path: Path) -> None:
    if not widget.grab().save(str(path)):
        print(f"    (could not save {path.name})")
    else:
        print(f"    {path.name}")


def main() -> int:
    out = Path.home() / "Desktop" / "chromiq-164-after"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_164_"))
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    settings.set("custom_output_path", str(work))

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    # A sheet GENERATED with 3 markers per patch, so the overlay has something
    # real to disagree with.
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import default_recipe
    rec = default_recipe("CM", "A4", mode="freehand")
    rec.helper_markers = True
    rec.helper_marker_edge_mm = 2.0
    rec.helper_marker_len_mm = 4.0
    rec.helper_marker_per_patch = 3
    res = le_chart.build_chart(TI1, sandbox / "sheet", **rec.build_kwargs())
    ti2 = Path(res.ti2_path)
    ti2.with_suffix(".channels.json").write_text(json.dumps({
        "layout": {"engine": "chromiq", "seed": res.seed,
                   "recipe": rec.to_dict()}}), encoding="utf-8")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1700, 1050)
    win.show()
    pump(app, 2500)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 900)
    lp = tab._manual_layout_panel
    lp._expert_frame.set_collapsed(False)
    lp.instr.setCurrentIndex(lp.instr.findData("CM"))
    pump(app, 600)

    print("1/2 — the ruler-marker group")
    lp.helper_markers_cb.setChecked(True)
    lp.helper_marker_len.setValue(4.0)
    pump(app, 400)
    shot(lp._helper_markers_grp, out / "1_markers_group.png")
    lp.helper_markers_cb.setChecked(False)
    pump(app, 400)
    shot(lp._helper_markers_grp, out / "2_markers_group_off.png")
    lp.helper_markers_cb.setChecked(True)
    pump(app, 300)

    print("3 — the clip band on a ColorMunki")
    for key in ("text", "branding", "notes"):
        lp.clip_content_mode.setCurrentIndex(lp.clip_content_mode.findData(key))
        if key in ("text", "branding"):
            lp.clip_text.setPlainText("Knut Larsson\nEpson P900\nHahnemuehle")
        pump(app, 800)
        shot(lp._clip_content_grp, out / f"3_clip_cm_{key}.png")
        print(f"    Clip area: {lp.clip_dims_label.text()}")

    print("4 — the Notes-box Text field")
    lp.clip_content_mode.setCurrentIndex(lp.clip_content_mode.findData("notes"))
    pump(app, 700)
    shot(lp._clip_content_grp, out / "4_clip_notes_disabled.png")

    print("5 — branding, placed")
    lp.clip_content_mode.setCurrentIndex(lp.clip_content_mode.findData("branding"))
    lp.clip_text.setPlainText("Knut Larsson\nEpson P900")
    lp.clip_image_offy.setValue(25.0)
    lp.clip_image_scale.setValue(70.0)
    pump(app, 900)
    shot(lp._clip_content_grp, out / "5_clip_branding_place.png")

    print("7 — the overlay when it is only a proposal")
    tab._preview.set_notice(None)
    tab._preview.load_tiff([Path(res.tiff_paths[0])])
    tab._set_margin_chart([Path(res.tiff_paths[0])], ti2)
    lp.helper_marker_per_patch.setValue(3)
    pump(app, 900)
    shot(tab._preview, out / "7a_overlay_matches_the_sheet.png")
    lp.helper_marker_per_patch.setValue(6)
    pump(app, 900)
    shot(tab._preview, out / "7b_overlay_proposal.png")

    print("6 — the Help card's Print button")
    from ui.dialogs.welcome_dialog import WORKFLOWS, WelcomeDialog
    dlg = WelcomeDialog(settings, win)
    dlg.resize(900, 700)
    dlg.show()
    pump(app, 800)
    key = next(w["key"] for w in WORKFLOWS if w.get("kind") == "shortcuts")
    dlg._on_card_clicked(key)
    pump(app, 700)
    shot(dlg, out / "6_help_card_print.png")
    dlg.close()

    print(f"\nShots: {out}")
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
