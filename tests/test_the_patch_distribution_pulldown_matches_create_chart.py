"""The "Compare with profile" pulldown of the Patch distribution window looks
and orders like the Create Chart Presets pulldown (Basti, beta 41).

Two faults, one screenshot (2026-09-24):

1. **Its field was beige in Light**, and so was Preferences > Reports >
   "Report type, default". Both are plain ``QComboBox``. All three app
   stylesheets wrote ``QComboBox:disabled::drop-down`` (and the same shape for
   the spin-box buttons); written that way Qt painted every ENABLED plain
   combo and spin box in the disabled colour. ``NoScrollComboBox`` escaped
   through its per-widget sheet. The fix is the selector
   (``QComboBox::drop-down:disabled``), once, in each sheet. Checked in every
   appearance, over every pulldown on show in the main window, Preferences,
   every Tools window and Patch distribution, against the Create Chart
   Presets pulldown, never against a fixed white.

2. **Its list kept its own order.** ``comparable_presets`` put the user's
   presets LAST under a "Custom presets" heading, so 26 CR30 presets sat under
   Red River Paper there and at the top in Create Chart. Both lists now come
   from ``preset_dropdown_groups``; the test reads the two real combos row by
   row, for a presets folder holding CR30, ColorMunki and i1Pro user presets,
   a genuinely custom one, and one saved without a patch set.

3. **The group order** (Basti, beta 41): every preset the user saved, for any
   instrument, at the very top of the whole list; the built-in CR30 group under
   its own headline directly before Scanner ("put them before scanner
   presets"), Red River Paper last.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# --------------------------------------------------------------------------
# 1. the field's colour, per appearance, against the other pulldowns
# --------------------------------------------------------------------------
#: Run in a child process: applying an appearance is an APP-WIDE stylesheet,
#: which re-polishes every widget alive in a worker (CLAUDE.md), and the fault
#: only shows under the app-wide sheet, so a widget-level one cannot stand in.
_PROBE = r"""
import collections, json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QTabWidget, QVBoxLayout
app = QApplication([]); app.setStyle("Fusion")
from core.settings import AppSettings
from core.argyll_runner import ArgyllRunner
from ui.theme import apply_appearance
from ui.main_window import MainWindow
from ui.dialogs.patch_cube_dialog import PatchCubeDialog
from ui.dialogs.settings_dialog import SettingsDialog
from ui.dialogs.tools_dialogs import TOOL_DIALOG_KEYS, build_tool_dialog
from ui.tabs.tab_chart import _CappedComboBox

settings = AppSettings()
settings.set("custom_output_path", sys.argv[2])      # never ~/ChromIQ


def field(c):
    # the commonest colour of a band through the closed box, left of the
    # drop-down button: the field, whatever its text
    img = c.grab().toImage()
    w, h = img.width(), img.height()
    if w < 60 or h < 12:
        return ""
    n = collections.Counter(img.pixelColor(x, y).name()
                            for x in range(4, w - 32, 2)
                            for y in range(h // 2 - 3, h // 2 + 4))
    return n.most_common(1)[0][0]


out = {}
for mode in ("light", "dark", "neutral"):
    apply_appearance(app, None, mode)
    ref_dlg = QDialog(); lay = QVBoxLayout(ref_dlg)
    ref = _CappedComboBox(ref_dlg); ref.addItem("none"); lay.addWidget(ref)
    ref_dlg.resize(400, 80); ref_dlg.show(); app.processEvents()
    rows = []

    def sweep(where, top):
        for c in top.findChildren(QComboBox):
            if c.isVisibleTo(top) and c.isEnabled():
                px = field(c)
                if px:
                    rows.append([where, type(c).__name__, c.currentText()[:40], px])

    win = MainWindow(settings); win.resize(1500, 1000); win.show()
    app.processEvents()
    for i in range(win._tabs.count()):
        win._tabs.setCurrentIndex(i); app.processEvents()
        sweep("main/" + win._tabs.tabText(i), win)
    sd = SettingsDialog(settings, win); sd.show(); app.processEvents()
    tabs = sd.findChild(QTabWidget)
    for i in range(tabs.count()):
        tabs.setCurrentIndex(i); app.processEvents()
        sweep("Preferences/" + tabs.tabText(i), sd)
    sd.close()
    runner = ArgyllRunner(settings)
    for key in TOOL_DIALOG_KEYS:
        dlg = build_tool_dialog(key, runner, settings, win)
        dlg.show(); app.processEvents()
        sweep("tool/" + key, dlg)
        dlg.close(); dlg.deleteLater()
    cube = PatchCubeDialog([(0, 0, 0)], mode=mode,
                           compare_presets=[("G", [("x", Path("/x.ti1"))])],
                           parent=win)
    cube.resize(900, 500); cube.show(); app.processEvents()
    sweep("Patch distribution", cube)
    out[mode] = {"reference": field(ref), "rows": rows,
                 "window": cube.palette().window().color().name()}
    cube.close(); win.close(); ref_dlg.close(); app.processEvents()
print("RESULT " + json.dumps(out))
"""


def test_every_pulldown_matches_create_chart_in_every_appearance(tmp_path):
    """Every enabled pulldown on show in the main window (each tab),
    Preferences (each tab), every Tools window and Patch distribution paints
    its field like the Create Chart Presets pulldown, in each appearance."""
    env = dict(os.environ)
    env.update(QT_QPA_PLATFORM="offscreen",
               CHROMIQ_SETTINGS_FILE=str(tmp_path / "s.ini"),
               CHROMIQ_PRESETS_DIR=str(tmp_path / "presets"))
    (tmp_path / "out").mkdir()
    try:
        r = subprocess.run([sys.executable, "-c", _PROBE, str(ROOT),
                            str(tmp_path / "out")],
                           capture_output=True, text=True, encoding="utf-8",
                           env=env,
                           timeout=280)       # budgeted for a loaded gate
    except subprocess.TimeoutExpired:
        pytest.fail("the appearance probe did not finish within 280 s")
    line = next((l for l in r.stdout.splitlines() if l.startswith("RESULT ")),
                None)
    assert line, f"probe printed no result:\n{r.stdout}\n{r.stderr[-3000:]}"
    got = json.loads(line[len("RESULT "):])
    assert set(got) == {"light", "dark", "neutral"}
    for mode, res in got.items():
        ref, rows = res["reference"], res["rows"]
        # Guard the guard: enough pulldowns were reached to mean something,
        # the two that were reported among them.
        where = {w for w, *_ in rows}
        assert len(rows) >= 40, (mode, len(rows))
        assert "Patch distribution" in where and "Preferences/Reports" in where
        bad = [f"{w} {cls} {txt!r}: {px}" for w, cls, txt, px in rows
               if px != ref]
        assert not bad, (f"{mode}: these pulldowns do not paint the Create "
                         f"Chart Presets field {ref}:\n" + "\n".join(bad))
    # In Light the field differs from the window, so a combo painting the
    # window's own colour cannot pass by coincidence.
    assert got["light"]["reference"] == "#ffffff"
    assert got["light"]["reference"] != got["light"]["window"]


# --------------------------------------------------------------------------
# 2. the grouping and order, read off both real combos
# --------------------------------------------------------------------------
_USER = {
    # name: saved with a patch set?
    "CR30-A4-77p-1page-Portrait-w24.0mm": True,
    "CR30-Letter-88p-1page-Portrait-w22.0mm": True,
    "ColorMunki-A4-300p-mine": True,
    "i1Pro-A3-900p-mine": True,
    "My glossy baryta": True,
    "Only settings, no patch set": False,
}


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    from core.settings import AppSettings
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    from core.preset_store import save_presets, sidecar_path
    src = sorted((ROOT / "assets/charts/knut/rgb/cr30").glob("*/chart.ti1"))[0]
    instr = {"CR30": "CR30", "ColorMunki": "CM"}
    save_presets("create_chart", {
        n: {"auto_run": False, "attached_ti1": t,
            "printtarg_-i": instr.get(n.split("-")[0], "i1")}
        for n, t in _USER.items()})
    for n, t in _USER.items():
        if t:
            sidecar_path("create_chart", n, ".ti1").write_bytes(src.read_bytes())
    return s


def _rows(combo, *, skip_first: bool) -> list[tuple[str, str]]:
    """``[(heading, row text)]`` as a person reads the open list: every
    selectable row with the bold heading above it ('' before any heading)."""
    out, heading = [], ""
    for i in range(1 if skip_first else 0, combo.count()):
        text = combo.itemText(i)
        if not text:                      # separator
            continue
        item = combo.model().item(i)
        if combo.itemData(i) is None:     # a heading row carries no data
            heading = text
            continue
        if item is not None and not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
            continue
        out.append((heading, text.strip()))
    return out


def test_the_list_is_create_charts_order_and_grouping(qapp, settings):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.preset_store import load_presets, sidecar_path
    from core.resource_path import resource_path
    from ui.dialogs.patch_cube_dialog import PatchCubeDialog
    from ui.tabs import tab_chart as TC

    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._populate_preset_combo(load_presets("create_chart", settings))
    cc = t._preset_combo

    # What Create Chart shows, reduced to the rows that have a patch set to
    # compare, each named as the compare list names it.
    overlay = {key: ov for _h, entries in TC.BUILTIN_PRESET_GROUPS
               for _c, ov, key in entries}
    want, heading = [], ""
    for i in range(1, cc.count()):
        text, key = cc.itemText(i), cc.itemData(i)
        if not text:
            continue
        if key is None:
            heading = text
            continue
        if key in overlay:
            asset = TC.TabChart._builtin_ti1_asset(key)
            if asset and resource_path(asset).is_file():
                want.append((heading, overlay[key]))
        elif sidecar_path("create_chart", key, ".ti1").is_file():
            want.append((heading, key))

    d = PatchCubeDialog([(0, 0, 0)],
                        compare_presets=TC.comparable_presets(settings))
    try:
        got = _rows(d._compare_combo, skip_first=True)
    finally:
        d.deleteLater()

    user_rows = [n for h, n in got if h == ""]
    assert user_rows == [n for n in load_presets("create_chart", settings)
                         if _USER[n]], (
        "EVERY user preset, the CR30 ones included, is at the very top of the "
        "whole list with no heading, exactly as Create Chart lists them")
    assert got[:len(user_rows)] == [("", n) for n in user_rows]
    assert not any(n.startswith("CR30-") for h, n in got if h)
    assert "Custom presets" not in {h for h, _n in got}
    assert got == want


def _headings(combo, first: int) -> list[str]:
    return [combo.itemText(i) for i in range(first, combo.count())
            if combo.itemText(i) and combo.itemData(i) is None]


def test_the_group_order_is_pinned_in_both_lists(qapp, settings):
    """Basti, beta 41: a CR30 headline like every other instrument, CR30
    directly before Scanner ("put them before scanner presets"), Red River
    Paper last, in Create Chart and in the compare list alike."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.preset_store import load_presets
    from ui.dialogs.patch_cube_dialog import PatchCubeDialog
    from ui.tabs import tab_chart as TC

    expected = [TC.INSTRUMENT_GROUP_LABELS["ColorMunki"],
                TC.INSTRUMENT_GROUP_LABELS["i1Pro"],
                TC.INSTRUMENT_GROUP_LABELS["i1Pro 3 Plus"],
                TC.INSTRUMENT_GROUP_LABELS["CR30"],
                "Scanner",
                "Red River Paper"]
    t = TC.TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._populate_preset_combo(load_presets("create_chart", settings))
    assert _headings(t._preset_combo, 1) == expected
    d = PatchCubeDialog([(0, 0, 0)],
                        compare_presets=TC.comparable_presets(settings))
    try:
        assert _headings(d._compare_combo, 1) == expected
    finally:
        d.deleteLater()
