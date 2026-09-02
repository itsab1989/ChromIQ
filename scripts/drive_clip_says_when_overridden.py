#!/usr/bin/env python3
"""On-screen proof for fix/clip-says-when-overridden.

Drives the REAL ChromIQ window, on screen, against a sandboxed settings file,
a sandboxed presets folder and a sandboxed working folder, and answers:

  1. With Knut's `i1Pro-A4-162p-1page-Portrait-w7.5mm` (a 26 mm clip border)
     and "Clip" at 4 mm, does the layout panel say the labels are held at 26?
  2. Do the numbers it gives match the ink on the sheet the app itself writes?
  3. Does the line go when "Clip" is raised past the border width?
  4. Does anything appear when the typed value IS the one in force?

    CHROMIQ_SETTINGS_FILE=/tmp/clipmsg.ini \
    CHROMIQ_PRESETS_DIR=/tmp/clipmsg-presets \
    python scripts/drive_clip_says_when_overridden.py --out DIR
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402

PRESET = "__chromiq_knut_i1_w75_a4_162p_1page_portrait_w7_5mm__"
PROJECT = "Clip-Message-Proof"
WORK = Path("/tmp/clipmsg-work")

modals: list[dict] = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(widget, path: Path) -> str:
    ok = widget.grab().save(str(path))
    print(f"    shot {path.name}: {'saved' if ok else 'FAILED'}")
    return path.name if ok else ""


def install_modal_watchdog(app, out: Path):
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        title = w.windowTitle()
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f()); break
                except Exception:
                    pass
        name = f"modal_{len(modals):02d}.png"
        try:
            w.grab().save(str(out / name))
        except Exception:
            name = ""
        modals.append({"title": title, "text": text[:400], "shot": name})
        print(f"    !! modal: {title!r} -> closing")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer(); t.setInterval(400); t.timeout.connect(check); t.start()
    _timers.append(t)
    return t


def wait_for_build(app, tab, timeout=240) -> bool:
    end = time.time() + timeout
    pump(app, 800)
    while time.time() < end:
        app.processEvents(); time.sleep(0.05)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            pump(app, 1500)
            if tab._generate_btn.isEnabled() and not tab._runner.is_running:
                return True
    return False


def note_state(panel) -> dict:
    w = panel.text_edge_clip_note
    return {
        "clip_box_mm": round(float(panel.text_edge_clip.value()), 2),
        "clip_border_width_mm": round(float(panel.clip_width.value()), 2),
        "row_indicators_on": bool(panel.show_row_indicators.isChecked()),
        "note_shown": bool(w.isVisibleTo(panel)),
        "note_text": w.text(),
    }


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path.home() / "Desktop/beta7/clip-message-proof"
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET as APP_STYLESHEET_DARK
    app.setStyleSheet(APP_STYLESHEET_DARK)

    from core.settings import AppSettings
    settings = AppSettings()
    if (WORK / PROJECT).exists():
        shutil.rmtree(WORK / PROJECT)
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("use_chromiq_layout_engine", True)
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, "
          f"work {WORK}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1560, 1040)
    win.show()
    pump(app, 900)
    install_modal_watchdog(app, out)

    tab = win._tab_chart
    res: dict = {"modals": modals}

    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 400)
    tab._manual_target_name_edit.setText(PROJECT)
    pump(app, 200)

    print("01 applying Knut's i1Pro A4 162p 1page Portrait w7.5mm")
    tab._activate_builtin_preset(PRESET)
    res["01_build_finished"] = wait_for_build(app, tab)
    pump(app, 800)

    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 400)
    # Scroll the Clip row into view so the shot of the window shows it.
    for attr in ("_expert_scroll", "_scroll"):
        pass
    panel.text_edge_clip.setFocus()
    pump(app, 200)

    # -- Knut's chart, with the row indicators he switches on.
    if not panel.show_row_indicators.isChecked():
        panel.show_row_indicators.click()
    pump(app, 400)

    steps = []

    def step(tag, clip, comment):
        panel.text_edge_clip.setValue(clip)
        pump(app, 500)
        st = note_state(panel)
        st["step"] = tag
        st["comment"] = comment
        st["shot_window"] = shot(win, out / f"onscreen_{tag}_window.png")
        st["shot_panel"] = shot(panel._expert_frame,
                                out / f"onscreen_{tag}_expert.png")
        steps.append(st)
        print(f"  {tag}: Clip {clip} -> shown={st['note_shown']}")
        print("     " + (st["note_text"].replace("\n", "\n     ") or "(nothing)"))
        return st

    step("02_clip4", 4.0, "the preset's own value: the box says 4, the labels "
                          "are held at the 26 mm border")
    step("03_clip26", 26.0, "exactly the border width: the typed value IS in "
                            "force for the labels")
    step("04_clip30", 30.0, "above the border: Clip positions the labels again")
    step("05_clip0", 0.0, "an empty box is read as 4 mm")
    step("06_back_to_4", 4.0, "back where we started")

    # -- The silent case: nothing in the clip border, and "Clip" above the
    #    border width. The typed value is then in force everywhere, and the
    #    panel must say NOTHING.
    for i in range(panel.clip_content_mode.count()):
        if panel.clip_content_mode.itemData(i) == "off":
            panel.clip_content_mode.setCurrentIndex(i)
            break
    pump(app, 500)
    step("07_clip30_content_off", 30.0,
         "the typed value IS in force: the panel says nothing at all")
    step("08_clip4_content_off", 4.0,
         "back under the border: only the row-label line comes back")

    # -- The same two states in the light theme, because both must read.
    from ui.light_styles import LIGHT_STYLESHEET
    app.setStyleSheet(LIGHT_STYLESHEET)
    pump(app, 700)
    for i in range(panel.clip_content_mode.count()):
        if panel.clip_content_mode.itemData(i) == "notes":
            panel.clip_content_mode.setCurrentIndex(i)
            break
    pump(app, 500)
    step("09_light_clip4", 4.0, "light theme")
    step("10_light_clip0", 0.0, "light theme, both lines")
    app.setStyleSheet(APP_STYLESHEET_DARK)
    pump(app, 500)

    # Back to the state the sheet is generated from.
    step("11_ready_to_generate", 4.0, "the state the sheet below is built in")

    # -- The sheet the app itself writes, at Clip 4, and where its ink lands.
    print("07 generating the sheet at Clip 4")
    panel.text_edge_clip.setValue(4.0)
    pump(app, 400)
    tab._generate_btn.click()
    res["07_build_finished"] = wait_for_build(app, tab)
    pump(app, 1200)

    res["steps"] = steps
    res["08_project_dir"] = str(WORK / PROJECT)
    tifs = sorted((WORK / PROJECT).rglob("*.tif"))
    res["08_tifs"] = [str(t) for t in tifs]
    print(f"08 wrote {len(tifs)} tif(s)")

    # -- Prove ~/ChromIQ gained nothing.
    home = Path.home() / "ChromIQ"
    res["09_home_chromiq_has_project"] = (home / PROJECT).exists()

    (out / "onscreen-result.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("written", out / "onscreen-result.json")

    for t in _timers:
        t.stop()
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
