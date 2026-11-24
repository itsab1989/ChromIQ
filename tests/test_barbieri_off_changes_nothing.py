"""WITH "Barbieri Spectro 100xy" OFF, CHROMIQ IS WHAT IT WAS (the Barbieri
chart Beta, 2026-11-24).

The nets of `docs/adding_an_instrument_checklist.md` 1.9, for the Barbieri:

1. A child process builds the real main window and Preferences with the Beta
   off, from fresh settings and from settings a user leaves behind after
   turning it off: no Barbieri in any list, no Barbieri module loaded beyond
   the switch.
2. The Measure tab reads no chart for the Barbieri while off, refuses a
   Barbieri chart at Start with M-BARBIERI-SUPPORT-OFF (never the name
   "repair"), and the layout engine refuses the code as unknown; a recipe of
   any other instrument carries no Barbieri field, and an engine chart of
   another instrument gets no Barbieri side file.
3. The files outside the Barbieri's own modules that name it are pinned
   (`HOOKED_FILES`).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def barbieri_beta_off():
    from workflow.barbieri import support
    before = support._latched
    support.set_enabled_for_this_process(False)
    try:
        yield
    finally:
        support._latched = before


PROBE = r"""
import json, os, sys
sys.path.insert(0, os.environ["CHROMIQ_ROOT"])
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PyQt6.QtWidgets import QApplication, QComboBox
app = QApplication([])
from ui.styles import WinButtonLayoutStyle
app.setStyle(WinButtonLayoutStyle("Fusion"))
from core.numeric_locale import pin_c_numeric_locale
pin_c_numeric_locale()
from core.settings import AppSettings
s = AppSettings()
s.set("custom_output_path", os.environ["CHROMIQ_PROBE_OUT"])
s.set("restore_last_session", False)
s.set("session_project", "")
if os.environ.get("CHROMIQ_PROBE_STALE"):
    # What a user leaves behind who made a Barbieri chart with the Beta on
    # and then turned it off: Guided's and Manual's Save as Defaults.
    s.set("chart_instrument", "B100XY")
    s.set("chart_paper", "A4R")
    s.set("chart_barbieri_head", "transmission-0.5")
    s.set("manual_printtarg_-i_l", "B100XY")
from workflow.barbieri.support import latch_from
assert latch_from(s) is False
from ui.main_window import MainWindow
win = MainWindow(s)
guided = win._tab_chart._paper_combo
papers = [str(guided.itemData(i)) for i in range(guided.count())]
from ui.dialogs.settings_dialog import SettingsDialog
dlg = SettingsDialog(s, win)
entries = []
for top in (win, dlg):
    for combo in top.findChildren(QComboBox):
        for i in range(combo.count()):
            entries.append([combo.itemText(i), str(combo.itemData(i))])
loaded = sorted(m for m in sys.modules if m.startswith("workflow.barbieri")
                or m in ("ui.dialogs.barbieri_panel",
                         "ui.barbieri_numbers_panel"))
print("PROBE" + json.dumps({
    "entries": entries, "loaded": loaded, "papers": papers,
    "paper": str(guided.currentData()),
    "instrument": str(win._tab_chart._instr_combo.currentData()),
    "beta_box": dlg._barbieri_charts_check.isChecked(),
    "numbers": getattr(win._tab_chart, "_barbieri_numbers", None) is not None,
    "group": getattr(win._tab_chart._manual_layout_panel, "_barbieri_group",
                     None) is not None}))
dlg.deleteLater(); win.close()
os._exit(0)
"""


def _probe(tmp_path, stale=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop("CHROMIQ_PROBE_STALE", None)
    env.update(CHROMIQ_ROOT=str(ROOT), QT_QPA_PLATFORM="offscreen",
               CHROMIQ_SETTINGS_FILE=str(tmp_path / "settings.ini"),
               CHROMIQ_PROBE_OUT=str(tmp_path / "out"))
    if stale:
        env["CHROMIQ_PROBE_STALE"] = "1"
    try:
        r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           env=env, cwd=str(tmp_path), timeout=600)
    except subprocess.TimeoutExpired:
        pytest.fail("the probe did not finish building the window in 600 s "
                    "(a loaded machine, or a window waiting for an answer)")
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("PROBE")),
                None)
    assert line, f"probe failed (exit {r.returncode}):\n{r.stderr[-3000:]}"
    return json.loads(line[len("PROBE"):])


@pytest.mark.parametrize("stale", [False, True],
                         ids=["fresh settings", "stale Barbieri settings"])
def test_the_real_window_offers_no_barbieri_and_loads_none_of_its_code(
        tmp_path, stale):
    got = _probe(tmp_path / ("stale" if stale else "fresh"), stale)
    if stale:
        fresh = _probe(tmp_path / "fresh", False)
        assert got["papers"] == fresh["papers"]
        assert got["instrument"] == fresh["instrument"], (got, fresh)
    entries = [e for e in got["entries"]
               if e[1] == "B100XY" or "Barbieri" in e[0]]
    assert not entries, f"with the Beta off a list offers the Barbieri: {entries}"
    extra = sorted(set(got["loaded"]) - {"workflow.barbieri",
                                         "workflow.barbieri.support"})
    assert not extra, f"Barbieri modules loaded with the option off: {extra}"
    assert got["beta_box"] is False
    assert got["group"] is False
    assert got["numbers"] is False


def _barbieri_chart(tmp_path, name="Barbieri Spectro 100xy"):
    ti2 = tmp_path / "barbchart.ti2"
    ti2.write_text(
        "CTI2\n\n"
        'DESCRIPTOR "Argyll Calibration Target chart information 2"\n'
        f'TARGET_INSTRUMENT "{name}"\nCOLOR_REP "RGB"\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
        '1 "A1" 100 100 100 95 100 108\nEND_DATA\n', encoding="utf-8")
    ti2.with_suffix(".ti1").write_text(ti2.read_text(encoding="utf-8")
                                       .replace("CTI2", "CTI1", 1),
                                       encoding="utf-8")
    return ti2


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    t.close()
    t.deleteLater()


def test_a_barbieri_chart_is_refused_at_start_with_the_beta_named(
        tab, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(tab, "_barbieri_support_off_window",
                        lambda: shown.append("M-BARBIERI-SUPPORT-OFF"))
    monkeypatch.setattr(tab, "_barbieri_steps_window", lambda: pytest.fail(
        "the steps window belongs to the option ON"))
    monkeypatch.setattr(tab, "_repair_target_instrument", lambda *a: pytest.fail(
        "a Barbieri chart must not be offered a name 'correction'"))
    ti2 = _barbieri_chart(tmp_path)
    tab.set_ti1_path(ti2.with_suffix(".ti1"))
    assert tab._blocked_by_unusable_target_instrument() is True
    assert shown == ["M-BARBIERI-SUPPORT-OFF"]


def test_the_start_reads_no_chart_for_the_barbieri_while_off(tab, tmp_path,
                                                             monkeypatch):
    import workflow.barbieri.support as sup

    def asked(*_a, **_k):
        raise AssertionError("a chart was read for the Barbieri with the Beta off")

    monkeypatch.setattr(sup, "chart_names_barbieri", asked)
    tab.set_ti1_path(_barbieri_chart(tmp_path).with_suffix(".ti1"))
    assert tab._refused_as_a_barbieri_chart() is False


def test_the_layout_engine_knows_no_barbieri_while_off(monkeypatch):
    from workflow.layout_engine import instruments
    monkeypatch.setitem(sys.modules, "workflow.barbieri.chart", None)
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.build("B100XY")
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.geom_from_build_kwargs({"instrument": "B100XY",
                                            "paper": "A4"})


def test_the_default_recipe_and_other_instruments_are_untouched():
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    # off, the Barbieri's own defaults are not applied (the recipe is the
    # generic one, as for any instrument the app does not know)
    r = default_recipe("B100XY", "A4R")
    g = default_recipe("i1", "A4R")
    assert (r.patch_w_mm, r.margin_left, r.layout_mode) == (
        g.patch_w_mm, g.margin_left, g.layout_mode)
    for inst in ("i1", "p3", "CM", "SS", "CR30"):
        d = default_recipe(inst, "A4").to_dict()
        kw = default_recipe(inst, "A4").build_kwargs()
        assert not any(k.startswith("barbieri") for k in d), inst
        assert not any(k.startswith("barbieri") for k in kw), inst
    assert LayoutRecipe().barbieri_head == "reflection-3"


def test_an_ss_chart_gets_no_barbieri_side_file_and_keeps_its_top_band(
        tmp_path):
    """The SpectroScan entry keeps its hidden top band (Basti, 2026-11-24:
    "keep for now") and nothing of the Barbieri reaches it."""
    from tests._barbieri_fixture import write_ti1
    from workflow.layout_engine import presets
    from workflow.layout_engine.chart import build_chart
    ti1 = write_ti1(tmp_path / "s.ti1", 120)
    kw = presets.default_recipe("SS", "A4").build_kwargs()
    kw.update(margins=(1.0, 10.0, 10.0, 15.0), patch_w=7.0, patch_h=7.0,
              use_instrument_margins=False, layout_mode="patch_first",
              draw_indicators=False, row_indicators=False)
    build_chart(ti1, tmp_path / "s", **kw)
    assert not (tmp_path / "s.barbieri.json").exists()
    text = (tmp_path / "s.ti2").read_text()
    assert "CHROMIQ_BARBIERI" not in text
    strips = json.loads((tmp_path / "s.strips.json").read_text())
    top_px = min(p["y"] for p in strips["patches"])
    assert top_px * 25.4 / strips["dpi"] > 7.5      # the 6 + 2 mm band


#: Files outside the Barbieri's own modules that name it, each of which asks
#: the switch (`workflow.barbieri.support`) before acting. A new file here is
#: a new hook: make it ask the switch, then add it, in the same commit.
BARBIERI_OWN = ("workflow/barbieri/", "ui/dialogs/barbieri_panel.py",
                "ui/barbieri_numbers_panel.py")
HOOKED_FILES = {
    "core/beta_registry.py",         # the app log's header names the switch
    "core/session_header.py",        # ...and whether this session runs it
    "core/file_manager.py",          # .barbieri.json companion (a name only)
    "core/settings.py",              # the switch's default, threshold label
    "data/patch_db.py",              # the label; filtered by the switch
    "main.py",                       # latches the switch
    "ui/dialogs/settings_dialog.py",  # the Beta row, consent, limits list
    "ui/dialogs/layout_options_panel.py",  # Manual's panel (the mixin)
    "ui/tabs/tab_chart.py",          # Guided entry and opening, papers, numbers
    "ui/tabs/tab_measure.py",        # the two Start windows
    "ui/tabs/tab_print.py",          # the print note; switch-gated
    "workflow/chart_creator.py",     # engine-only; Guided kwargs; log lines
    "workflow/chart_import.py",      # .barbieri.json companion
    "workflow/measurement_messages.py",  # M-BARBIERI-* (texts only)
    "workflow/layout_engine/chart.py",
    "workflow/layout_engine/instruments.py",
    "workflow/layout_engine/presets.py",
}


def test_the_files_that_name_the_barbieri_are_the_known_ones():
    pat = re.compile(r"workflow\.barbieri|\"B100XY\"|\.barbieri\.json|"
                     r"barbieri_enabled|is_barbieri_|barbieri_chart_beta|"
                     r"_barbieri_|CHROMIQ_BARBIERI|barbieri_panel")
    found = set()
    for base in ("core", "ui", "workflow", "data"):
        for p in (ROOT / base).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith(BARBIERI_OWN):
                continue
            if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                found.add(rel)
    if pat.search((ROOT / "main.py").read_text(encoding="utf-8")):
        found.add("main.py")
    assert found == HOOKED_FILES, (
        f"new: {sorted(found - HOOKED_FILES)}; gone: "
        f"{sorted(HOOKED_FILES - found)}")
