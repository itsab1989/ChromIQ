#!/usr/bin/env python3
"""Knut, #182 5872273862: after saving a preset under a new name, "New Patch
Set…" in the patch set editor shows a previously used setup, not the preset's.

Drives the REAL window through his sequence and reads, at every step, three
things side by side:

  * the design the SELECTED preset carries (its recipe),
  * the design the run on disk carries (meta.json ``editor_recipe``),
  * the design "New Patch Set…" actually opens with,

and photographs the New Patch Set window each time. The cube size (``cube_n``)
and the "fill to" count tell the designs apart at a glance.

    .venv/bin/python scripts/drive_preset_save_new_patch_set.py [before|after]

Everything is sandboxed: settings, presets, logs and the projects folder live
in a throwaway folder. No modal loop is entered: every exec() is answered by
the driver, and anything else that pops up is logged and closed.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.chdir(ROOT)

LABEL = sys.argv[1] if len(sys.argv) > 1 else "before"
OUT = Path.home() / "Desktop/ChromIQ-430-stable-prep/preset-save-bug" / LABEL
OUT.mkdir(parents=True, exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix="chromiq-preset-save-bug-"))
os.environ["CHROMIQ_SETTINGS_FILE"] = str(WORK / "drive.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(WORK / "presets")
os.environ["CHROMIQ_LOG_DIR"] = str(WORK / "logs")
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    ROOT / "data/compliance_sets/iso12647.json")
os.environ.pop("QT_QPA_PLATFORM", None)          # a REAL window

threading.Timer(900, lambda: os._exit(3)).start()   # hard stop

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtGui import QFontDatabase                                # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialog,       # noqa: E402
                             QMessageBox)

app = QApplication(sys.argv[:1])
app.setApplicationName("ChromIQ")
app.setOrganizationName("ChromIQ")
from core.resource_path import resource_path                         # noqa: E402
from ui.styles import WinButtonLayoutStyle                           # noqa: E402
from ui.theme import apply_appearance                                # noqa: E402
from ui.widgets import (ButtonFontFilter, DialogFocusFilter,         # noqa: E402
                        GroupBoxSurfaceFilter, TooltipWrapFilter)
for fp in resource_path("assets/fonts").glob("*.ttf"):
    QFontDatabase.addApplicationFont(str(fp))
app.setStyle(WinButtonLayoutStyle("Fusion"))
for F in (ButtonFontFilter, GroupBoxSurfaceFilter, TooltipWrapFilter,
          DialogFocusFilter):
    app.installEventFilter(F(app))
from core import gc_guard                                            # noqa: E402
gc_guard.install_gui_thread_collector(app)

from core.settings import AppSettings                                # noqa: E402
s = AppSettings()
s.set("custom_output_path", str(WORK / "projects"))
s.set("use_chromiq_layout_engine", False)
apply_appearance(app, None, "light")

from onscreen_capture import capture_window                          # noqa: E402
from ui.dialogs import ti2_relayout_dialog as RD                     # noqa: E402
from ui.dialogs.tools_dialogs import build_tool_dialog               # noqa: E402
from ui.widgets import PrefixLockedLineEdit                          # noqa: E402

LOG: list[str] = []


def say(msg: str) -> None:
    print(msg, flush=True)
    LOG.append(msg)


def pump(sec: float = 0.8) -> None:
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        watchdog()
        time.sleep(0.02)


def watchdog() -> None:
    for w in app.topLevelWidgets():
        if isinstance(w, QMessageBox) and w.isVisible():
            say(f"    popup (closed): {w.text()[:140]!r}")
            w.reject()


def design(rec) -> str:
    if not isinstance(rec, dict) or not rec:
        return "no design"
    sp = rec.get("sp") or {}
    cb = rec.get("cb") or {}
    return (f"cube_n={sp.get('cube_n')} neutral_n={sp.get('neutral_n')} "
            f"fill={'on' if cb.get('fill') else 'off'}->{sp.get('fill_to')} "
            f"instr={rec.get('instr')} paper={rec.get('paper')}")


# ---- every modal loop is answered here, never entered ---------------------
ANSWER: dict = {}
_orig_msg_exec = QMessageBox.exec


def _answer_dialog(self) -> int:
    title = self.windowTitle()
    if isinstance(self, QMessageBox):
        say(f"    question {title!r}: {self.text()[:160]!r}")
        want = ANSWER.get("message", "accept")
        for b in self.buttons():
            role = self.buttonRole(b)
            if want == "accept" and role in (
                    QMessageBox.ButtonRole.AcceptRole,
                    QMessageBox.ButtonRole.YesRole):
                self.show(); pump(0.3)
                capture_window(self, OUT / f"q-{len(LOG):03d}.png")
                b.click()
                self._clicked_by_driver = b
                return 0
        return int(QDialog.DialogCode.Rejected)
    if title == "Save Preset":
        name, attach = ANSWER["save"]
        edit = self.findChild(PrefixLockedLineEdit)
        for cb in self.findChildren(QCheckBox):
            if cb.text().startswith("Add a descriptive prefix"):
                cb.setChecked(False)
            if cb.text().startswith("Build from the currently loaded"):
                if attach and not cb.isEnabled():
                    say("    attach box is DISABLED (no .ti1 loaded)")
                cb.setChecked(bool(attach and cb.isEnabled()))
            if cb.text().startswith("Generate the chart immediately"):
                cb.setChecked(False)
        edit.setText(name)
        self.show(); pump(0.6)
        capture_window(self, OUT / f"{ANSWER['shot']}-save-dialog.png")
        self.hide()
        return int(QDialog.DialogCode.Accepted)
    say(f"    dialog {title!r} (rejected by the driver)")
    return int(QDialog.DialogCode.Rejected)


QDialog.exec = _answer_dialog                         # type: ignore[assignment]
QMessageBox.exec = _answer_dialog                     # type: ignore[assignment]

SEEN: dict = {}


def _new_chart_exec(self) -> int:
    self.resize(1360, 900)
    self.show()
    pump(2.0)
    st = self._collect_gen_state()
    SEEN["recipe"] = st
    SEEN["banner"] = [lbl.text() for lbl in self.findChildren(
        RD.QLabel) if lbl.objectName() == "recipeSource" and lbl.isVisible()]
    capture_window(self, OUT / f"{ANSWER['shot']}-new-patch-set.png")
    edit = ANSWER.get("edit_cube")
    if edit is not None:
        self._gen_cube_n.setValue(edit)
        pump(0.5)
        self._on_ok() if hasattr(self, "_on_ok") else self.accept()
        pump(1.0)
        self.hide()
        return int(self.result())
    self.hide()
    return int(QDialog.DialogCode.Rejected)


RD._NewChartDialog.exec = _new_chart_exec             # type: ignore[assignment]

from ui.main_window import MainWindow                                # noqa: E402


def new_window():
    w = MainWindow(s)
    w.resize(1600, 1000)
    w.show()
    pump(3.0)
    w._tabs.setCurrentWidget(w._tab_chart)
    pump(1.0)
    w._tab_chart._switch_mode("manual")
    pump(1.0)
    return w


def select(win, key) -> None:
    tab = win._tab_chart
    ix = tab._preset_combo.findData(key)
    assert ix >= 0, f"preset {key!r} not in the dropdown"
    tab._preset_combo.setCurrentIndex(ix)
    # A click in the list emits `activated`, which is what the tab listens to.
    tab._preset_combo.activated.emit(ix)
    for _ in range(200):          # a built-in builds as it is chosen
        pump(0.5)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            break
    pump(1.5)


def generate(win) -> None:
    tab = win._tab_chart
    tab._on_generate()
    for _ in range(400):
        pump(0.5)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            break
    pump(1.5)


def run_recipe(win):
    try:
        return win._file_mgr.project().current_run().load_meta().editor_recipe
    except Exception:  # noqa: BLE001
        return None


def open_new_patch_set(win, shot: str, edit_cube=None):
    ANSWER["shot"] = shot
    ANSWER["edit_cube"] = edit_cube
    SEEN.clear()
    ed = build_tool_dialog("ti2_relayout", win._runner, s, win,
                           on_apply=win._apply_editor_chart,
                           initial_chart=win._current_chart_ti2(),
                           **({"preset_recipe": win._tab_chart
                               .recipe_for_new_patch_set()}
                              if hasattr(win._tab_chart,
                                         "recipe_for_new_patch_set") else {}))
    ed.resize(1400, 900)
    ed.show()
    pump(3.0)
    ed._new_chart()
    pump(1.0)
    shown = SEEN.get("recipe")
    return ed, shown


def close_editor(ed) -> None:
    ed.hide()
    ed.reject()
    pump(0.3)
    if hasattr(ed, "dispose"):
        ed.dispose()
    pump(0.3)


def preset_file(name):
    d = WORK / "presets" / "Create Chart"
    return sorted(p.name for p in d.glob("*")) if d.is_dir() else []


def step(win, title, shot, expect):
    tab = win._tab_chart
    sel = tab._preset_combo.currentText()
    ed, shown = open_new_patch_set(win, shot)
    close_editor(ed)
    verdict = "PASS" if design(shown) == design(expect) else "FAIL"
    say(f"\n## {title}")
    say(f"  preset selected     : {sel}")
    say(f"  its design          : {design(expect)}")
    say(f"  the run's meta.json : {design(run_recipe(win))}")
    say(f"  New Patch Set shows : {design(shown)}")
    if SEEN.get("banner"):
        say(f"  New Patch Set says  : {SEEN['banner']}")
    say(f"  => {verdict}")
    return verdict


def main() -> int:
    from ui.tabs.tab_chart import builtin_preset_recipe
    from ui.tabs import tab_chart as T
    k1 = next(k for k in T.KNUT_PRESETS_BY_KEY if "fls_i1pro_a4_484p" in
              T.KNUT_PRESETS_BY_KEY[k].ti1_asset)
    k2 = next(k for k in T.KNUT_PRESETS_BY_KEY if "fls_i1pro_a4_1200p" in
              T.KNUT_PRESETS_BY_KEY[k].ti1_asset)
    r1, r2 = builtin_preset_recipe(k1), builtin_preset_recipe(k2)
    say(f"# New Patch Set after Save Preset ({LABEL}), real window")
    say(f"sandbox: {WORK}")
    say(f"built-in A: {T.KNUT_PRESETS_BY_KEY[k1].name}  -> {design(r1)}")
    say(f"built-in B: {T.KNUT_PRESETS_BY_KEY[k2].name}  -> {design(r2)}")
    verdicts = []

    win = new_window()
    tab = win._tab_chart
    tab._manual_target_name_edit.setText("PresetBug")
    pump(0.5)
    select(win, k1)
    generate(win)
    say(f"\ngenerated A: run design = {design(run_recipe(win))}")
    verdicts.append(step(win, "1. built-in A selected and built", "01-builtin-A-built", r1))

    select(win, k2)
    verdicts.append(step(win, "2. built-in B chosen (a built-in builds as it is chosen)", "02-builtin-B-chosen", r2))

    ANSWER["save"] = ("Mine B plain", False); ANSWER["shot"] = "03"
    tab._on_preset_save(); pump(1.5)
    saved = json.loads((WORK / "presets/Create Chart/Mine B plain.json").read_text(encoding="utf-8"))
    say(f"\nsaved 'Mine B plain': json name={saved['name']!r}, "
        f"design={design(saved['data'].get('editor_recipe'))}, files={preset_file('')}")
    verdicts.append(step(win, "3. saved as a NEW name, no .ti1", "03-saved-new-name-plain", r2))

    ANSWER["save"] = ("Mine B attached", True); ANSWER["shot"] = "04"
    tab._on_preset_save(); pump(1.5)
    saved = json.loads((WORK / "presets/Create Chart/Mine B attached.json").read_text(encoding="utf-8"))
    side = WORK / "presets/Create Chart/Mine B attached.ti1"
    from workflow.ti2_relayout import load_rgb_program
    n = len(load_rgb_program(side)) if side.is_file() else None
    say(f"\nsaved 'Mine B attached': attached_ti1={saved['data'].get('attached_ti1')}, "
        f".ti1 patches={n}, design={design(saved['data'].get('editor_recipe'))}")
    verdicts.append(step(win, "4. saved as a NEW name, .ti1 attached", "04-saved-new-name-attached", r2))

    select(win, "Mine B plain")
    verdicts.append(step(win, "5. user preset selected (not built)", "05-user-preset-selected", r2))
    generate(win)
    verdicts.append(step(win, "6. user preset built", "06-user-preset-built", r2))

    # Change the recipe inside the editor and apply it; then save under a new name.
    ed, _shown = open_new_patch_set(win, "07-change-recipe", edit_cube=11)
    pump(2.0)
    ed._prompt_apply_action = lambda: "overwrite"
    ed._save_and_apply()
    for _ in range(200):
        pump(0.5)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            break
    pump(1.5)
    close_editor(ed)
    changed = run_recipe(win)
    say(f"\napplied an edited design: run design = {design(changed)}")
    ANSWER["save"] = ("Mine cube 11", True); ANSWER["shot"] = "08"
    tab._on_preset_save(); pump(1.5)
    saved = json.loads((WORK / "presets/Create Chart/Mine cube 11.json").read_text(encoding="utf-8"))
    say(f"saved 'Mine cube 11': design={design(saved['data'].get('editor_recipe'))}")
    verdicts.append(step(win, "8. edited design saved under a new name", "08-edited-saved", changed))

    select(win, "Mine B attached")
    verdicts.append(step(win, "9. switch back to an older user preset", "09-back-to-older-user-preset", r2))

    # Reopen the app on the same sandbox.
    win.close(); pump(1.0)
    win = new_window(); tab = win._tab_chart
    select(win, "Mine cube 11")
    verdicts.append(step(win, "10. app reopened, 'Mine cube 11' selected", "10-reopened", changed))

    # Overwrite, with a case variant of the name.
    select(win, k1)
    ANSWER["save"] = ("mine cube 11", True); ANSWER["shot"] = "11"
    ANSWER["message"] = "accept"
    tab._on_preset_save(); pump(1.5)
    say(f"\noverwrite via 'mine cube 11': files={preset_file('')}")
    doc = json.loads((WORK / "presets/Create Chart/Mine cube 11.json").read_text(encoding="utf-8"))
    say(f"  json name={doc['name']!r}, design={design(doc['data'].get('editor_recipe'))}")
    verdicts.append(step(win, "11. overwritten with built-in A's design", "11-overwritten", r1))

    # Renamed by hand in Finder (json + ti1), then reopened.
    d = WORK / "presets/Create Chart"
    (d / "Mine B attached.json").rename(d / "Renamed in Finder.json")
    (d / "Mine B attached.ti1").rename(d / "Renamed in Finder.ti1")
    win.close(); pump(1.0)
    win = new_window(); tab = win._tab_chart
    names = [tab._preset_combo.itemData(i) for i in range(tab._preset_combo.count())]
    user = [n for n in names if isinstance(n, str) and not n.startswith("__")]
    say(f"\nafter a Finder rename, the dropdown's own presets: {user}")
    pick = "Renamed in Finder" if "Renamed in Finder" in user else "Mine B attached"
    select(win, pick)
    say(f"  selected {pick!r}: builds from sidecar = {tab._preset_ti1_path}")
    verdicts.append(step(win, "12. renamed in Finder, reopened", "12-renamed-in-finder", r2))

    win.close(); pump(0.5)
    say(f"\nSUMMARY: {verdicts.count('PASS')} PASS, {verdicts.count('FAIL')} FAIL")
    (OUT / "report.md").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    rc = main()
    os._exit(rc)
