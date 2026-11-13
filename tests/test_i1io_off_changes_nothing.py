"""WITH i1iO SUPPORT OFF, CHROMIQ IS 4.3.32 (the i1iO table Beta, 2026-11-13).

The X-Rite i1iO table is a Beta in Preferences > Beta, off by default. Off,
there may be no i1iO in any list, no i1iO chart code loaded, no chart file read
to find out whether it is an i1iO chart, and no new key in any target's
meta.json. The nets of `docs/adding_an_instrument.md` §4, for the i1iO (the
fourth, a real project made on and opened off, is
`tests/test_i1io_off_stale_project.py`):

1. A child process builds the real main window and Preferences with the option
   off, from fresh settings and from settings a user leaves behind after
   turning it off, and reports every combo entry and every module loaded.
2. In this process, the Measure tab: an i1iO chart is refused at Start with
   M-I1IO-SUPPORT-OFF (never offered the name "repair"), and nothing reads a
   chart for the i1iO before that point.
3. The files outside the i1iO's own modules that name it are pinned.

And the one deliberate difference from 4.3.32, recorded here so it stays one:
an i1iO chart opened with the option off is refused with a window that names
the option, where 4.3.32 would have offered to "correct" its instrument name.
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
def i1io_beta_off():
    from workflow.i1io import support
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
from PyQt6.QtWidgets import QApplication, QComboBox, QWidget
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
    # What a user leaves behind who made an i1iO chart with the Beta on and
    # then turned it off: Guided's Save as Defaults on the i1iO's sheet.
    s.set("chart_instrument", "IO2")
    s.set("chart_paper", "A4R")
from workflow.i1io.support import latch_from
assert latch_from(s) is False
from ui.main_window import MainWindow
win = MainWindow(s)
guided = win._tab_chart._paper_combo
papers = [str(guided.itemData(i)) for i in range(guided.count())]
paper = str(guided.currentData())
instrument = str(win._tab_chart._instr_combo.currentData())
from ui.dialogs.settings_dialog import SettingsDialog
dlg = SettingsDialog(s, win)
entries = []
for top in (win, dlg):
    for combo in top.findChildren(QComboBox):
        for i in range(combo.count()):
            entries.append([combo.itemText(i), str(combo.itemData(i))])
loaded = sorted(m for m in sys.modules if m.startswith("workflow.i1io"))
print("PROBE" + json.dumps({"entries": entries, "loaded": loaded,
                            "papers": papers, "paper": paper,
                            "instrument": instrument,
                            "beta_box": dlg._i1io_support_check.isChecked()}))
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
                         ids=["fresh settings", "stale i1iO settings"])
def test_the_real_window_offers_no_i1io_and_loads_none_of_its_code(
        tmp_path, stale):
    got = _probe(tmp_path / ("stale" if stale else "fresh"), stale)
    if stale:
        fresh = _probe(tmp_path / "fresh", False)
        assert got["papers"] == fresh["papers"]
        # The saved i1iO and its landscape sheet read as none.
        assert (got["instrument"], got["paper"]) == (
            fresh["instrument"], fresh["paper"]), (got, fresh)
    entries = [e for e in got["entries"]
               if e[1] == "IO2" or "i1iO" in e[0]]
    assert not entries, f"with i1iO support off a list offers it: {entries}"
    # Only the switch may be loaded (main() latches it; its package with it).
    extra = sorted(set(got["loaded"]) - {"workflow.i1io",
                                         "workflow.i1io.support"})
    assert not extra, f"i1iO modules loaded with the option off: {extra}"
    assert got["beta_box"] is False


def _i1io_chart(tmp_path, name="X-Rite i1iO"):
    ti2 = tmp_path / "iochart.ti2"
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


def test_an_i1io_chart_is_refused_at_start_with_the_beta_named(
        tab, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(tab, "_i1io_support_off_window",
                        lambda: shown.append("M-I1IO-SUPPORT-OFF"))
    monkeypatch.setattr(tab, "_i1io_not_yet_window", lambda: pytest.fail(
        "the 'not yet' window belongs to the option ON"))
    monkeypatch.setattr(tab, "_repair_target_instrument", lambda *a: pytest.fail(
        "an i1iO chart must not be offered a name 'correction'"))
    ti2 = _i1io_chart(tmp_path)
    tab.set_ti1_path(ti2.with_suffix(".ti1"))
    assert tab._blocked_by_unusable_target_instrument() is True
    assert shown == ["M-I1IO-SUPPORT-OFF"]


def test_the_start_reads_no_chart_for_the_i1io_while_off(tab, tmp_path,
                                                         monkeypatch):
    """The early i1iO check at the top of Start asks the switch first, and
    reads nothing while it is off."""
    import workflow.i1io.support as sup

    def asked(*_a, **_k):
        raise AssertionError("a chart was read for the i1iO with the Beta off")

    monkeypatch.setattr(sup, "chart_names_i1io", asked)
    tab.set_ti1_path(_i1io_chart(tmp_path).with_suffix(".ti1"))
    assert tab._refused_as_an_i1io_chart() is False


def test_the_layout_engine_knows_no_i1io_while_off(monkeypatch):
    from workflow.layout_engine import instruments
    monkeypatch.setitem(sys.modules, "workflow.i1io.chart", None)
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.build("IO2")
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.geom_from_build_kwargs({"instrument": "IO2",
                                            "paper": "A4R"})


def test_the_editor_flag_and_the_lists_are_4332s(qapp):
    """The shared label table names the i1iO (as it names the FD-9), and
    every list built from it leaves it out while the option is off: Guided,
    Manual's -i, the layout panel, the papers; the editor reads an i1iO
    chart's name as 4.3.32 did."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.papers import list_papers
    from workflow.ti2_relayout import instrument_to_flag
    import ui.tabs.tab_chart as tc
    assert "IO2" not in dict(LayoutOptionsPanel.instruments())
    assert instrument_to_flag("X-Rite i1iO") == "i1"
    assert [p[0] for p in list_papers("IO2", for_engine=True)] == \
        [p[0] for p in list_papers("i1iSis-unknown", for_engine=True)]
    params = tc._without_choice(
        {"printtarg": [{"flag": "-i", "choices": ["i1", "IO2"],
                        "labels": ["a", "b"]}]}, "IO2")
    assert params["printtarg"][0]["choices"] == ["i1"]


def test_manuals_instrument_list_is_4332s_while_off(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    try:
        params = tab._load_yaml_params()
        i = next(p for p in params["printtarg"] if p["flag"] == "-i")
        assert "IO2" not in i["choices"] and "i1iO" not in i["tooltip_body"]
        assert tab._instr_combo.findData("IO2") < 0
    finally:
        tab.deleteLater()


#: Files outside the i1iO's own modules that name it, each of which asks the
#: switch (`workflow.i1io.support`) before acting. A new file here is a new
#: hook: make it ask the switch, then add it, in the same commit.
I1IO_OWN = ("workflow/i1io/",)
HOOKED_FILES = {
    "core/file_manager.py",          # .i1io.json companion (no switch: a name)
    "core/settings.py",              # the switch's default
    "data/patch_db.py",              # the label; filtered by the switch
    "ui/tabs/tab_print.py",          # the load note; switch-gated
    "ui/tiff_preview.py",            # shown as on the table; 0 while off
    "ui/dialogs/ti2_relayout_dialog.py",  # the editor's page view: the
                                     # same turn; 0 while off
    "workflow/measurement_report.py",  # names the i1iO; switch-gated
    "workflow/printer_edges.py",     # the crosses' boxes from .i1io.json
                                     # (review r3 m3); nothing read while off
    "main.py",                       # latches the switch
    "ui/dialogs/settings_dialog.py",  # the Beta row and its consent window
    "ui/dialogs/layout_options_panel.py",  # Manual's panel: its greying
    "ui/tabs/tab_chart.py",          # Guided entry, papers, carry, transfer
    "ui/tabs/tab_measure.py",        # the two Start windows
    "workflow/chart_creator.py",     # engine-only; no stamp; its error words
    "workflow/chart_import.py",      # .i1io.json companion
    # the turned export (its own Beta) says why an i1iO chart has no
    # matching i1Profiler chart yet; reached only for an "IO2" recipe
    "workflow/i1profiler_turned.py",
    "workflow/layout_engine/chart.py",
    "workflow/layout_engine/instruments.py",
    "workflow/layout_engine/papers.py",
    "workflow/layout_engine/presets.py",
    "workflow/ti2_relayout.py",      # the editor's instrument (on only)
    # declares the i1iO's CHROMIQ_I1IO_* keywords (any CHROMIQ_ keyword);
    # every other chart's .ti2 is byte for byte as before
    "workflow/layout_engine/ti2_writer.py",
    # the i1iO's "what to aim at" paragraph (M-I1IO-AIM-*), rendered from
    # the chart's record; reached only from the i1iO's own Start notices
    "workflow/measurement_messages.py",
}


def test_the_files_that_name_the_i1io_are_the_known_ones():
    # The hook's own names, not the word: "i1iO" itself appears all over the
    # i1Profiler hand-off code (its device list), which is no hook.
    pat = re.compile(r"workflow\.i1io|\"IO2\"|\.i1io\.json|i1io_enabled|"
                     r"is_i1io_|i1io_support|_i1io_|CHROMIQ_I1IO")
    found = set()
    for base in ("core", "ui", "workflow", "data"):
        for p in (ROOT / base).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith(I1IO_OWN):
                continue
            if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                found.add(rel)
    if pat.search((ROOT / "main.py").read_text(encoding="utf-8")):
        found.add("main.py")
    assert found == HOOKED_FILES, (
        f"new: {sorted(found - HOOKED_FILES)}; gone: "
        f"{sorted(HOOKED_FILES - found)}")
