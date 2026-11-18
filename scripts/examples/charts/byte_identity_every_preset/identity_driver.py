#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXAMPLE (kept as a pattern; may need adapting): generate EVERY built-in preset in the real
app, on screen, and record a SHA-256 of every file each build writes.

From the byte-identity loop of the page-output Beta (4.3.43) and its units round (4.3.44):
docs/adding_an_instrument.md, section 9b. Run it once in each of two trees (the previous
release in its own `git worktree`, and your branch), then compare the two JSON files with
compare_identity.py beside it. Everything that differs between runs for no reason is pinned,
the same way in both trees, so it cannot hide a real difference:

* the seed a randomised preset draws (`permutation.pick_seed`): a constant per preset;
* the CGATS CREATED stamp and the long English date of the i1Profiler exports: constants;
* the date a sheet prints: 2026-11-16; and the version number the files carry (--pin-version).

ArgyllCMS's own printtarg writes its own CREATED line, which no pin reaches; the masked hash
(clock instants replaced) covers it, and compare_identity.py reports such files separately.

NOTE: this driver answers every message box itself (QDialog.exec / QMessageBox patched), which
is right for a build loop and wrong for proving a window: use scripts/userdrive.py for that.

    export CHROMIQ_SETTINGS_FILE=/new/folder/settings.ini
    export CHROMIQ_PRESETS_DIR=/new/folder/presets CHROMIQ_LOG_DIR=/new/folder/logs
    python identity_driver.py /path/to/tree /new/folder/tree-a.json --mode off
    (again in the other tree), then: python compare_identity.py tree-a.json tree-b.json

Environment knobs: PB_ONLY (a text the preset label must contain), PB_PICK (1-based numbers,
comma separated), PB_ENGINE (1/0, the layout engine), PB_STAMP (1: the settings stamp on),
PB_UNITS (the Units choice), PB_NOTES (chart notes text), PB_KEEP (a NEW folder to copy the
built files into), PB_FULLSNAP (1: keep each preset's whole snapshot).
Needs: a display, ArgyllCMS, the tree's .venv. Every preset takes a few seconds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

_ap = argparse.ArgumentParser(description=__doc__,
                              formatter_class=argparse.RawDescriptionHelpFormatter)
_ap.add_argument("repo", help="the tree to build in (its own checkout)")
_ap.add_argument("out", help="a NEW .json file for the hashes")
_ap.add_argument("--mode", choices=("plain", "off", "on"), default="plain",
                 help="the option under test (see THE OPTION UNDER TEST in the code)")
_ap.add_argument("--limit", type=int, default=0, help="only the first N presets")
_ap.add_argument("--pin-version", default="0.0.0",
                 help="the version number written into files, the same in both trees")
_A = _ap.parse_args()
REPO = Path(_A.repo).resolve()
OUT = Path(_A.out).resolve()
MODE = _A.mode
LIMIT = _A.limit
for _var in ("CHROMIQ_SETTINGS_FILE", "CHROMIQ_PRESETS_DIR", "CHROMIQ_LOG_DIR"):
    if not os.environ.get(_var):
        sys.exit(f"set {_var} to a scratch location first (scripts/README.md)")
if OUT.exists():
    sys.exit(f"{OUT} exists already: give a new file")
if os.environ.get("PB_KEEP") and Path(os.environ["PB_KEEP"]).exists():
    sys.exit("PB_KEEP must name a NEW folder")
if "QT_QPA_PLATFORM" in os.environ:
    sys.exit("a driver runs on screen: unset QT_QPA_PLATFORM")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
import core.version as _pin_version                       # noqa: E402
_pin_version.APP_VERSION = _A.pin_version
os.chdir(REPO)

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

# ---- pins ----------------------------------------------------------------
_SEED = [12345]
import workflow.layout_engine.permutation as _perm          # noqa: E402
_perm.pick_seed = lambda rng=None: _SEED[0]
import core.cgats_date as _cd                               # noqa: E402
_cd.created_stamp = lambda when=None: "Mon Nov 16 12:00:00 2026"
_cd.long_english_date = lambda when=None: "November 16, 2026"
import time as _time                                        # noqa: E402
_real_strftime = _time.strftime


def _strftime(fmt, t=None):
    if fmt == "%Y-%m-%d":
        return "2026-11-16"
    return _real_strftime(fmt) if t is None else _real_strftime(fmt, t)


_time.strftime = _strftime

from capture_screens import build_app                       # noqa: E402
from PyQt6.QtWidgets import QDialog, QMessageBox             # noqa: E402

app = build_app()


def pump(ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


import re as _re
#: Wall-clock instants the pins do not reach: ISO date-times (project.json and
#: meta.json "created_at", the .pxf CreationDate) and asctime CREATED lines
#: (ArgyllCMS's own printtarg). Masked ONLY for the second hash; the first is
#: the raw bytes, and compare_identity.py reports both.
_CLOCK = _re.compile(rb"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:[+-]\d\d:\d\d|Z)?"
                     rb"|CREATED \"[^\"]*\"")
_TEXT = {".json", ".pxf", ".txt", ".ti1", ".ti2", ".ti3", ".xml", ".txf", ".cht", ".ps"}


def masked_sha(p: Path) -> "str | None":
    if p.suffix.lower() not in _TEXT:
        return None
    return hashlib.sha256(_CLOCK.sub(b"<CLOCK>", p.read_bytes())).hexdigest()


def main() -> int:                                          # noqa: C901
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-pb-identity-",
                                 dir=os.environ["CHROMIQ_LOG_DIR"]))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", os.environ.get("PB_ENGINE", "1") == "1")
    settings.set("restore_last_session", False)
    settings.set("chart_stamp_commands", os.environ.get("PB_STAMP") == "1")
    settings.set("auto_update_preview", False)
    units = os.environ.get("PB_UNITS")
    if units:
        # the Units choice (branch only; master has no such key and ignores it)
        settings.set("page_output_units", units)
    # THE OPTION UNDER TEST (adapt): here the page-output Beta of 4.3.43, as the example ran.
    # "plain" sets nothing; "off" asserts it is off; "on" switches it on and uses nothing new.
    if MODE == "on":
        settings.set("page_output_beta", True)
        from workflow.page_output.support import latch_from
        assert latch_from(settings) is True
    elif MODE == "off":
        try:
            from workflow.page_output.support import latch_from
            assert latch_from(settings) is False
        except ImportError:
            pass                                       # an older tree: no such switch
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from workflow.chart_creator import ChartCreator
    done = {"n": 0}
    _orig_finish = ChartCreator._finish

    def _finish(self, tiffs):
        try:
            return _orig_finish(self, tiffs)
        finally:
            done["n"] += 1
    ChartCreator._finish = _finish

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    win = MainWindow(settings)
    win.resize(1500, 980)
    win.show()
    focus = getattr(app, "_chromiq_focus_give_back", None)
    pump(2500)
    if focus is not None:
        focus.give_back()
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(800)
    tab._user_switch_mode("manual")
    pump(1500)
    on_screen = bool(win.isVisible())
    print(f"    window on screen: {on_screen} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    combo = tab._preset_combo
    todo = []
    for i in range(combo.count()):
        data = combo.itemData(i)
        if data and str(data).startswith("__chromiq"):
            todo.append((str(data), combo.itemText(i)))
    if os.environ.get("PB_ONLY"):
        todo = [t for t in todo if os.environ["PB_ONLY"] in t[1]]
    if LIMIT:
        todo = todo[:LIMIT]
    if os.environ.get("PB_PICK"):
        _pick = [int(x) for x in os.environ["PB_PICK"].split(",")]
        todo = [todo[i - 1] for i in _pick]
    print(f"    {len(todo)} built-in preset(s), mode {MODE}", flush=True)

    rows = []
    seen: dict = {}
    for n, (key, label) in enumerate(todo, 1):
        row = {"key": key, "label": label}
        _SEED[0] = 1000 + n
        t0 = time.monotonic()
        try:
            if tab._manual_target_name_edit is not None:
                # a new target per preset, named BEFORE the preset is applied
                # (naming afterwards switches target and loads its defaults)
                tab._manual_target_name_edit.setText(f"PB{n:03d}")
                pump(300)
            tab._activate_builtin_preset(key)
            pump(1200)
            if os.environ.get("PB_NOTES") and tab._manual_chart_notes_edit is not None:
                tab._manual_chart_notes_edit.setText(os.environ["PB_NOTES"])
                tab._manual_chart_notes_edit.editingFinished.emit()
                pump(300)
            row["target_name"] = (tab._manual_target_name_edit.text()
                                  if tab._manual_target_name_edit is not None
                                  else "")
            panel = getattr(tab, "_manual_layout_panel", None)
            if panel is not None:
                row["panel"] = {"dpi": panel.dpi.value(),
                                "dpi_range": [panel.dpi.minimum(),
                                              panel.dpi.maximum()],
                                "custom_decimals": panel.custom_w.decimals(),
                                "custom_range": [panel.custom_w.minimum(),
                                                 panel.custom_w.maximum()],
                                "paper": panel.paper.currentData()}
            if panel is not None:
                # B: every length field as the person sees it (value is mm);
                # D: what a preset saved now would hold
                from PyQt6.QtWidgets import QDoubleSpinBox
                fields = {}
                for name, box in vars(panel).items():
                    boxes = box.items() if isinstance(box, dict) else [("", box)]
                    for k, b in boxes:
                        if isinstance(b, QDoubleSpinBox):
                            fields[f"{name}{k}"] = [b.minimum(), b.maximum(),
                                                    b.singleStep(), b.decimals(),
                                                    b.value()]
                row["fields"] = fields
                try:
                    snap = tab._snapshot_preset_state()
                    row["preset_snapshot"] = hashlib.sha256(json.dumps(
                        snap, sort_keys=True, default=str).encode()).hexdigest()
                    row["preset_recipe"] = (snap or {}).get("layout_recipe")
                    if os.environ.get("PB_FULLSNAP"):
                        row["preset_full"] = json.loads(json.dumps(
                            snap, sort_keys=True, default=str))
                except Exception as exc:              # noqa: BLE001
                    row["preset_snapshot"] = repr(exc)
            before = done["n"]
            tab._generate_btn.click()
            waited = 0.0
            while waited < 300.0:
                pump(150)
                waited += 0.15
                if done["n"] > before:
                    break
            pump(1500)
            row["finished"] = done["n"] > before
        except Exception as exc:                          # noqa: BLE001
            row["error"] = repr(exc)
            row["traceback"] = traceback.format_exc()[-2000:]
        files = {}
        for p in sorted(work.rglob("*")):
            if p.is_file():
                rel = str(p.relative_to(work))
                st = p.stat()
                stamp = (st.st_mtime_ns, st.st_size)
                if seen.get(rel) == stamp:
                    continue              # written by an earlier preset
                seen[rel] = stamp
                files[rel] = {"sha": sha(p), "size": st.st_size,
                              "masked": masked_sha(p)}
        row["files"] = files
        row["seconds"] = round(time.monotonic() - t0, 1)
        rows.append(row)
        tifs = [f for f in files if f.endswith(".tif")]
        print(f"  [{n:3}/{len(todo)}] {label[:60]:60} files={len(files):3} "
              f"tif={len(tifs):2} fin={row.get('finished')} "
              f"{'ERR ' + row['error'][:60] if 'error' in row else ''}",
              flush=True)
        OUT.write_text(json.dumps({"mode": MODE, "repo": str(REPO),
                                   "on_screen": on_screen, "rows": rows},
                                  indent=1), encoding="utf-8")
    win.close()
    pump(500)
    keep = os.environ.get("PB_KEEP")
    if keep:
        shutil.copytree(work, Path(keep), dirs_exist_ok=True)
    # nothing is deleted: the built files stay in CHROMIQ_LOG_DIR/chromiq-pb-identity-*
    print("    done", flush=True)
    return 0


if __name__ == "__main__":
    rc = main()
    os._exit(rc)
