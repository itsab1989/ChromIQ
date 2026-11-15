"""WITH "X-Rite i1iSis charts" OFF, CHROMIQ IS 4.3.37, WITH ONE STATED
EXCEPTION (the i1iSis chart Beta, 2026-11-14).

The exception is the owner's ruling of 2026-11-14: the printtarg entry
"i1iSis (via i1Profiler)" is gone for everybody, and a stale saved ``isis``
reads as no instrument (`tests/test_a_removed_instrument_reads_as_none.py`).

The nets of `docs/adding_an_instrument_checklist.md` 1.9, for the i1iSis (the
fourth, a real project made on and opened off, is
`tests/test_isis_off_stale_project.py`):

1. A child process builds the real main window and Preferences with the Beta
   off, from fresh settings and from settings a user leaves behind after
   turning it off: no i1iSis in any list, no i1iSis module loaded beyond the
   switch.
2. The Measure tab reads no chart for the i1iSis while off, refuses an
   i1iSis chart at Start with M-ISIS-SUPPORT-OFF (never the name "repair"),
   and the layout engine refuses the code as unknown.
3. The files outside the i1iSis's own modules that name it are pinned
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
def isis_beta_off():
    from workflow.isis import support
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
    # What a user leaves behind who made an i1iSis chart with the Beta on
    # and then turned it off: Guided's and Manual's Save as Defaults.
    s.set("chart_instrument", "XRISIS")
    s.set("chart_paper", "329x483")
    s.set("chart_isis_model", "xl")
    s.set("manual_printtarg_-i_l", "XRISIS")
from workflow.isis.support import latch_from
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
loaded = sorted(m for m in sys.modules if m.startswith("workflow.isis")
                or m == "ui.dialogs.isis_panel")
print("PROBE" + json.dumps({
    "entries": entries, "loaded": loaded, "papers": papers,
    "paper": str(guided.currentData()),
    "instrument": str(win._tab_chart._instr_combo.currentData()),
    "beta_box": dlg._isis_charts_check.isChecked(),
    "group": getattr(win._tab_chart._manual_layout_panel, "_isis_group",
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
                         ids=["fresh settings", "stale i1iSis settings"])
def test_the_real_window_offers_no_i1isis_and_loads_none_of_its_code(
        tmp_path, stale):
    got = _probe(tmp_path / ("stale" if stale else "fresh"), stale)
    if stale:
        fresh = _probe(tmp_path / "fresh", False)
        assert got["papers"] == fresh["papers"]
        # the saved i1iSis and its A3+ sheet read as none
        assert (got["instrument"], got["paper"]) == (
            fresh["instrument"], fresh["paper"]), (got, fresh)
    entries = [e for e in got["entries"]
               if e[1] in ("XRISIS", "isis") or "iSis" in e[0]]
    assert not entries, f"with the Beta off a list offers the i1iSis: {entries}"
    extra = sorted(set(got["loaded"]) - {"workflow.isis",
                                         "workflow.isis.support"})
    assert not extra, f"i1iSis modules loaded with the option off: {extra}"
    assert got["beta_box"] is False
    assert got["group"] is False


def _isis_chart(tmp_path, name="X-Rite i1iSis"):
    ti2 = tmp_path / "isischart.ti2"
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


def test_an_i1isis_chart_is_refused_at_start_with_the_beta_named(
        tab, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(tab, "_isis_support_off_window",
                        lambda: shown.append("M-ISIS-SUPPORT-OFF"))
    monkeypatch.setattr(tab, "_isis_not_yet_window", lambda: pytest.fail(
        "the 'not yet' window belongs to the option ON"))
    monkeypatch.setattr(tab, "_repair_target_instrument", lambda *a: pytest.fail(
        "an i1iSis chart must not be offered a name 'correction'"))
    ti2 = _isis_chart(tmp_path)
    tab.set_ti1_path(ti2.with_suffix(".ti1"))
    assert tab._blocked_by_unusable_target_instrument() is True
    assert shown == ["M-ISIS-SUPPORT-OFF"]


def test_the_start_reads_no_chart_for_the_i1isis_while_off(tab, tmp_path,
                                                           monkeypatch):
    import workflow.isis.support as sup

    def asked(*_a, **_k):
        raise AssertionError("a chart was read for the i1iSis with the Beta off")

    monkeypatch.setattr(sup, "chart_names_isis", asked)
    tab.set_ti1_path(_isis_chart(tmp_path).with_suffix(".ti1"))
    assert tab._refused_as_an_isis_chart() is False


def test_the_layout_engine_knows_no_i1isis_while_off(monkeypatch):
    from workflow.layout_engine import instruments
    monkeypatch.setitem(sys.modules, "workflow.isis.chart", None)
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.build("XRISIS")
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.geom_from_build_kwargs({"instrument": "XRISIS",
                                            "paper": "A4"})


def test_no_export_and_the_pxf_unchanged_while_off(tmp_path, monkeypatch):
    """write_sidecars reads nothing for the i1iSis and writes no .txf while
    off; the .pxf keeps its long-standing device name."""
    import workflow.isis.support as sup
    from workflow.chart_exports import i1profiler_device_for
    monkeypatch.setattr(sup, "chart_names_isis", lambda *_a: (_ for _ in ())
                        .throw(AssertionError("read while off")))
    ti2 = _isis_chart(tmp_path)
    from workflow.i1io import support as io
    before = io._latched
    io.set_enabled_for_this_process(False)
    try:
        assert i1profiler_device_for(ti2.with_suffix(".ti1")) is None
    finally:
        io._latched = before


#: Files outside the i1iSis's own modules that name it, each of which asks
#: the switch (`workflow.isis.support`) before acting. A new file here is a
#: new hook: make it ask the switch, then add it, in the same commit.
ISIS_OWN = ("workflow/isis/", "ui/dialogs/isis_panel.py")
HOOKED_FILES = {
    "core/file_manager.py",          # .isis.json companion (a name only)
    "core/settings.py",              # the switch's default, threshold label
    "data/patch_db.py",              # the label; filtered by the switch
    "main.py",                       # latches the switch
    "ui/dialogs/settings_dialog.py",  # the Beta row, consent, limits list
    "ui/dialogs/layout_options_panel.py",  # Manual's panel (isis_panel mixin)
    "ui/tabs/tab_chart.py",          # Guided entry and choices, papers, guard
    "ui/tabs/tab_measure.py",        # the two Start windows
    "ui/tabs/tab_print.py",          # the feed note; switch-gated
    "workflow/chart_creator.py",     # engine-only; no stamp; its words
    "workflow/chart_exports.py",     # the .txf and the .pxf's device name
    "workflow/chart_import.py",      # .isis.json companion
    # the order file pairs a measurement (measurement_import.py then says
    # "several pages" by the order's kind, read only from such an order)
    "workflow/i1profiler_turned.py",
    "workflow/measurement_messages.py",  # M-ISIS-* (texts only)
    "workflow/measurement_report.py",  # names the i1iSis; switch-gated
    "workflow/layout_engine/chart.py",
    "workflow/layout_engine/instruments.py",
    "workflow/layout_engine/presets.py",
}


def test_the_files_that_name_the_i1isis_are_the_known_ones():
    pat = re.compile(r"workflow\.isis|\"XRISIS\"|\.isis\.json|isis_enabled|"
                     r"is_isis_|isis_charts_beta|_isis_|CHROMIQ_ISIS|"
                     r"isis_panel")
    found = set()
    for base in ("core", "ui", "workflow", "data"):
        for p in (ROOT / base).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith(ISIS_OWN):
                continue
            if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                found.add(rel)
    if pat.search((ROOT / "main.py").read_text(encoding="utf-8")):
        found.add("main.py")
    assert found == HOOKED_FILES, (
        f"new: {sorted(found - HOOKED_FILES)}; gone: "
        f"{sorted(HOOKED_FILES - found)}")
