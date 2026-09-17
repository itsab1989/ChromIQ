#!/usr/bin/env python3
"""Load and GENERATE every built-in preset, and write down what it says.

Asked for by the design authority, 2026-09-16: *"all Presets should be
individually regenerated, (except those saying 'by Pharmacist'), so that
changes made in features are incorporated. However, if any preset have
warnings, these must be listed in a bullet-list with their exact names, so that
I can report back what settings to modify to get rid of the warning messages in
the presets."*

And, in the same comment: *"I mentioned before that some presets when loaded
are missing the 'Margins: OK' message, and instead have no message at all. Why
is that ...?"* -- so this also records the margin panel's own STATUS LINE,
verbatim, which is the only way to tell the three outcomes apart:

  * the green "Margins: OK";
  * a red paragraph naming what is wrong;
  * **nothing at all**, which is the state he is asking about.

Each preset is put through the dropdown a person uses and then GENERATED, so
what is recorded is what the sheet really produced rather than what the recipe
predicts. A preset that cannot be generated is recorded as such, with the
reason, rather than skipped.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20p.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20p-presets \\
        python scripts/drive_182_survey_every_builtin_preset.py <out-dir> [N]

*N* limits the run to the first N presets, for a smoke test.

Never QT_QPA_PLATFORM=offscreen: it is a driver, not a test.
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
from onscreen_capture import session_is_locked                   # noqa: E402

#: Excluded by name, exactly as he wrote it.
SKIP_MARK = "Pharmacist"


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:                                      # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    argv = list(sys.argv[1:])
    # **THE STAMP IS AN APP SETTING, NOT A PRESET FIELD**, and it defaults ON.
    # `tab_chart` seeds the "Stamp settings down the right edge" box from
    # `settings.get("chart_stamp_commands", True)` whenever the run has no
    # stored value, so on a FRESH install every chart carries it -- and on
    # these sheets it warns, because the right margin is spent on the clip
    # band. Surveying only in that state would hand back a list of presets all
    # warning about one setting that belongs to none of them; surveying only
    # with it off would hide what a new user actually sees. So it is a flag and
    # the survey is run BOTH ways.
    stamp = True
    if "--no-stamp" in argv:
        argv.remove("--no-stamp")
        stamp = False
    out = Path(argv[0]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    limit = int(argv[1]) if len(argv) > 1 else 0
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20p-survey-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    settings.set("chart_stamp_commands", bool(stamp))
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

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
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    combo = tab._preset_combo
    todo = []
    for i in range(combo.count()):
        data = combo.itemData(i)
        text = combo.itemText(i)
        if not data or not str(data).startswith("__chromiq"):
            continue
        if SKIP_MARK in text:
            continue
        todo.append((str(data), text))
    if limit:
        todo = todo[:limit]
    print(f"    {len(todo)} preset(s) to survey "
          f"(every built-in except '{SKIP_MARK}'), "
          f"stamp={'ON (fresh-install default)' if stamp else 'OFF'}",
          flush=True)

    panel = tab._margin_panel
    rows = []
    for n, (key, label) in enumerate(todo, 1):
        row = {"key": key, "combo_label": label, "stamp_setting": bool(stamp)}
        try:
            if tab._manual_target_name_edit is not None:
                tab._manual_target_name_edit.setText("B20PSurvey")
            tab._margin_report = None
            tab._activate_builtin_preset(key)
            pump(app, 1500)
            row["target_name"] = (
                tab._manual_target_name_edit.text()
                if tab._manual_target_name_edit is not None else "")
            # GENERATE. Some presets generate on load, which is why the report
            # is cleared first and the button pressed regardless.
            tab._generate_btn.click()
            waited = 0.0
            while waited < 180.0:
                pump(app, 150)
                waited += 0.15
                if getattr(tab, "_margin_report", None) is not None:
                    break
            rep = getattr(tab, "_margin_report", None)
            row["generated"] = rep is not None
            row["seconds"] = round(waited, 1)
            if rep is not None:
                row["measured"] = {k: round(float(getattr(rep, k)), 2) for k in
                                   ("left_mm", "right_mm", "top_mm", "bottom_mm")}
            tab._update_margin_inspector()
            pump(app, 700)
            # THE PANEL'S OWN STATUS LINE, verbatim and with its visibility.
            # An empty string with the label hidden is the "no message at all"
            # state he is asking about, and it is NOT the same as "Margins: OK".
            row["status_text"] = panel._status.text()
            row["status_visible"] = bool(panel._status.isVisible())
            row["warning_count"] = int(getattr(panel, "_warning_count", 0) or 0)
            warns, over = TabChart._engine_text_notes(tab, rep)
            row["surface_warnings"] = list(over)
            row["tooltip_notes"] = [w for w in warns if w not in over]
        except Exception as exc:                       # noqa: BLE001
            row["error"] = repr(exc)
            row["generated"] = False
        rows.append(row)
        print(f"  [{n:3}/{len(todo)}] {label[:58]:58} "
              f"gen={'Y' if row.get('generated') else 'N'} "
              f"warn={len(row.get('surface_warnings') or [])} "
              f"status={row.get('status_text', '')[:28]!r}", flush=True)
        (out / ("survey.json" if stamp else "survey-no-stamp.json")).write_text(
            json.dumps({"rows": rows, "crashes": crashes}, indent=2,
                       ensure_ascii=False), encoding="utf-8")

    print(f"    crashes: {len(crashes)}", flush=True)
    for c in crashes:
        print(c[:2000], flush=True)
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    sys.exit(main())
