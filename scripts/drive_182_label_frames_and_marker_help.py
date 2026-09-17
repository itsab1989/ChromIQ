#!/usr/bin/env python3
"""The renamed label frames and the marker help, photographed in a real window.

Three things a tester can SEE, and none of them provable from a string
comparison:

1. the two frames in "Strip & row labels" now read "Strip and row indicators"
   and "Strip indicators only";
2. the ⓘ on "Print helper markers" opens and its text explains why a pair of
   edges greys out;
3. on an upright hexagonal CR30 preset the markers are OFF and the preview
   shows no dashes.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20p.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20p-presets \\
        python scripts/drive_182_label_frames_and_marker_help.py <out-dir>

Never QT_QPA_PLATFORM=offscreen: a tooltip is a POPUP, and a `widget.grab()`
render cannot show one at all.
"""
from __future__ import annotations

import json
import os
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

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def _scroll(panel, w) -> None:
    """Bring *w* into view, whichever ancestor owns the scroll area."""
    p = panel
    while p is not None:
        if hasattr(p, "ensureWidgetVisible"):
            try:
                p.ensureWidgetVisible(w, 60, 160)
                return
            except Exception:                       # noqa: BLE001
                pass
        p = p.parent()


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    crashes: list = []
    prev = sys.excepthook

    def hook(t, e, tb):
        crashes.append("".join(traceback.format_exception(t, e, tb)))
        prev(t, e, tb)
    sys.excepthook = hook

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20p-help-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    # **SHOWN, NOT EXEC'd.** The ⓘ opens a MODAL `_InfoDialog` with `exec()`,
    # so a driver that lets it run really blocks -- and a blocked driver on
    # this machine gets clicked by hand, after which every later reading is
    # somebody else's. Stubbing `exec` to return 1 (what the other drivers do)
    # is safe but never PAINTS the dialog, so the photograph came back with no
    # popup in it at all. `show()` gives a real, visible, non-blocking window.
    _shown: list = []

    def _show_instead_of_exec(self):
        self.setModal(False)
        self.show()
        self.raise_()
        _shown.append(self)
        return 1

    QDialog.exec = _show_instead_of_exec              # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show(); win.raise_(); win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    panel = tab._manual_layout_panel
    assert panel is not None
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    rows: dict = {}

    # --- 1. the two frame titles, read off the BUILT group boxes ------------
    rows["frame_titles"] = {
        "both": panel._label_sub_both.title(),
        "strip_only": panel._label_sub_strip_only.title(),
    }
    print(f"    titles: {rows['frame_titles']}", flush=True)

    # Load an upright hexagonal preset so the markers are in the reported state.
    from ui.tabs.tab_chart import KNUT_PRESETS
    hexp = next(p for p in KNUT_PRESETS
                if "cr30_a4_420p" in p.key and "hexagonal" in p.key)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("B20PHelp")
    tab._activate_builtin_preset(hexp.key)
    pump(app, 2000)
    rows["preset"] = hexp.name
    rows["markers"] = {
        "print_helper_markers_checked": bool(panel.helper_markers_cb.isChecked()),
        "top_bottom_checked": bool(panel.helper_markers_top_bottom.isChecked()),
        "top_bottom_enabled": bool(panel.helper_markers_top_bottom.isEnabled()),
        "sides_checked": bool(panel.helper_markers_sides.isChecked()),
        "sides_enabled": bool(panel.helper_markers_sides.isEnabled()),
        "top_bottom_tooltip": panel.helper_markers_top_bottom.toolTip(),
    }
    print(f"    markers: {json.dumps(rows['markers'], ensure_ascii=False)[:220]}",
          flush=True)

    # **THE LABEL FRAMES LIVE INSIDE "Expert Options", WHICH SHIPS COLLAPSED.**
    # Scrolling to a widget in a collapsed section scrolls to a zero-height
    # placeholder, which is what the first run of this photographed.
    exp = getattr(panel, "_expert_frame", None)
    if exp is not None and hasattr(exp, "set_collapsed"):
        exp.set_collapsed(False)
    elif exp is not None and hasattr(exp, "setChecked"):
        exp.setChecked(True)
    pump(app, 1200)
    rows["expert_expanded"] = bool(panel._label_sub_both.isVisible())
    print(f"    label frames visible: {rows['expert_expanded']}", flush=True)
    _scroll(panel, panel._label_sub_both)
    pump(app, 900)
    ok, why = capture_window(win, out / "frames-renamed.png")
    rows["photo_frames"] = str(out / "frames-renamed.png") if ok else None
    rows["photo_frames_refused"] = None if ok else why
    print(f"    photo frames: {'OK' if ok else why}", flush=True)

    # --- 2. the ⓘ on "Print helper markers", OPENED ------------------------
    from ui.tooltip_button import TooltipButton
    grp = panel.helper_markers_cb.parent()
    tip = next(w for w in grp.findChildren(TooltipButton)
               if "ruler helper marker" in (w._title or "").lower())
    _scroll(panel, tip)
    pump(app, 700)
    tip.click()
    pump(app, 1800)
    rows["help_dialog_visible"] = bool(_shown and _shown[-1].isVisible())
    print(f"    help dialog visible: {rows['help_dialog_visible']}", flush=True)
    # **PHOTOGRAPH THE DIALOG, NOT THE WINDOW BEHIND IT.** `_InfoDialog` is its
    # own TOP-LEVEL window, so `capture_window(win, ...)` takes the main
    # window's buffer and the help simply is not in the picture -- which is
    # what the first run of this produced, a photograph with no dialog in it
    # captioned as proof that the dialog opened.
    dlg = _shown[-1] if _shown else None
    if dlg is not None:
        dlg.raise_()
        pump(app, 600)
        ok, why = capture_window(dlg, out / "marker-help-dialog.png")
        rows["photo_help_dialog"] = (str(out / "marker-help-dialog.png")
                                     if ok else None)
        rows["photo_help_dialog_refused"] = None if ok else why
        print(f"    photo help DIALOG: {'OK' if ok else why}", flush=True)
    ok, why = capture_window(win, out / "marker-help-open.png")
    rows["photo_help"] = str(out / "marker-help-open.png") if ok else None
    rows["photo_help_refused"] = None if ok else why
    rows["help_body"] = tip._body
    print(f"    photo help: {'OK' if ok else why}", flush=True)

    for d in _shown:
        try:
            d.close()
        except Exception:                           # noqa: BLE001
            pass
    pump(app, 400)

    (out / "results.json").write_text(
        json.dumps({"rows": rows, "crashes": crashes}, indent=2,
                   ensure_ascii=False), encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    for c in crashes:
        print(c, flush=True)
    win.close(); pump(app, 500)
    return 0


if __name__ == "__main__":
    sys.exit(main())
