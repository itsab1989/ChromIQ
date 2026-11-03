"""WITH FD-9 SUPPORT OFF, CHROMIQ IS 4.3.21 (Basti's requirement 2, PR #213).

The Konica Minolta FD-9 (written and contributed by lessbones) is a Beta in
Preferences > Beta, off by default. Off, there may be no FD-9 in any list, no
FD-9 panel or hook on the Measure tab, no chart file read to find out whether
it is an FD-9 chart, no new key in any target's meta.json, and nothing else
that behaves differently. Three nets, because each catches what the others
cannot:

1. A child process builds the real main window and Preferences with the
   option off and reports every combo box entry, every widget name and every
   module it loaded. An "FD-9" anywhere, or the FD-9 measurement code or the
   vendored driver being loaded at all, fails. A new ungated hook that touches
   the FD-9 code shows up here even if nobody thought to test it.
2. In this process, the Measure tab with the option off: an FD-9 chart and an
   ordinary chart are loaded and started, and `is_fd9_chart` must never be
   asked; the stored settings carry no FD-9 key.
3. The files outside the FD-9's own modules that mention the FD-9 are pinned,
   so a new one is a deliberate act that shows in the diff.
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
def fd9_beta_off():
    from workflow.fd9 import support
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
    # What a user leaves behind who made an FD-9 chart with the Beta on and
    # then turned it off (review r1 F3): the Guided instrument and sheet, and
    # an FD-9 recipe as Manual's "Save as Defaults".
    s.set("chart_instrument", "FD9")
    s.set("chart_paper", "137x300")
    from workflow.layout_engine.presets import LayoutRecipe
    s.set("manual_engine_recipe", LayoutRecipe(
        instrument="FD9", paper="137x300", patch_w_mm=10.0, patch_h_mm=12.0,
        fd9_gap_mm=2.0, layout_mode="patch_first").to_dict())
from workflow.fd9.support import latch_from
assert latch_from(s) is False
from ui.main_window import MainWindow
win = MainWindow(s)
guided = win._tab_chart._paper_combo
papers = [str(guided.itemData(i)) for i in range(guided.count())]
instrument = str(win._tab_chart._instr_combo.currentData())
from ui.dialogs.settings_dialog import SettingsDialog
dlg = SettingsDialog(s, win)
entries, names = [], []
for top in (win, dlg):
    for combo in top.findChildren(QComboBox):
        for i in range(combo.count()):
            entries.append([combo.itemText(i), str(combo.itemData(i))])
    for w in top.findChildren(QWidget):
        if w.objectName():
            names.append(w.objectName())
loaded = sorted(m for m in sys.modules
                if m.startswith(("workflow.fd9", "fd9_independent",
                                 "ui.fd9_measurement", "ui.dialogs.fd9_sheet")))
print("PROBE" + json.dumps({"entries": entries, "names": names,
                            "loaded": loaded, "papers": papers,
                            "instrument": instrument}))
dlg.deleteLater(); win.close()
os._exit(0)
"""


def _probe(tmp_path, stale=False):
    """Build the real window in a child process; its report as a dict."""
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
                           text=True, encoding="utf-8", errors="replace", env=env, cwd=str(tmp_path), timeout=600)
    except subprocess.TimeoutExpired:
        pytest.fail("the probe did not finish building the window in 600 s "
                    "(a loaded machine, or a window waiting for an answer)")
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith("PROBE")),
                None)
    assert line, f"probe failed (exit {r.returncode}):\n{r.stderr[-3000:]}"
    return json.loads(line[len("PROBE"):])


@pytest.mark.parametrize("stale", [False, True],
                         ids=["fresh settings", "stale FD-9 settings"])
def test_the_real_window_offers_no_fd9_and_loads_none_of_its_code(
        tmp_path, stale):
    """Also from the settings a user leaves behind after turning the Beta
    off again (review r1 F3): the FD-9 chosen in Guided on the FD-9's own
    137 x 300 mm sheet, and an FD-9 recipe stored for Manual. The window then
    opens as if the FD-9 had never been there: no FD-9 sheet in the i1Pro's
    paper list, and no FD-9 code loaded to find that out."""
    got = _probe(tmp_path / ("stale" if stale else "fresh"), stale)
    if stale:
        fresh = _probe(tmp_path / "fresh", False)
        assert got["papers"] == fresh["papers"], (
            "stale FD-9 settings changed Guided's paper list: "
            f"{sorted(set(got['papers']) ^ set(fresh['papers']))}")
        assert got["instrument"] != "FD9"
    fd9_entries = [e for e in got["entries"]
                   if e[1] == "FD9" or "FD-9" in e[0] or "FD9" in e[0]]
    assert not fd9_entries, (
        f"with FD-9 support off a list still offers the FD-9: {fd9_entries}")
    fd9_names = [n for n in got["names"] if n.lower().startswith("fd9")]
    assert not fd9_names, f"FD-9 widgets built with the option off: {fd9_names}"
    # The only FD-9 module the app may load with the option off is the switch
    # itself (workflow.fd9 is its package). The mixin's module is imported by
    # the Measure tab for the class, and holds no FD-9 import at module level.
    allowed = {"workflow.fd9", "workflow.fd9.support", "ui.fd9_measurement"}
    extra = sorted(set(got["loaded"]) - allowed)
    assert not extra, (
        "with FD-9 support off these FD-9 modules were loaded, so some code "
        f"path reached the FD-9 without asking the switch: {extra}")


def _fd9_chart(tmp_path, name="FD-9"):
    ti2 = tmp_path / "fd9chart.ti2"
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


def test_the_measure_tab_never_asks_whether_a_chart_is_the_fd9s(
        tab, tmp_path, monkeypatch):
    import workflow.fd9.measurement as fm

    def asked(*_a, **_k):
        raise AssertionError("is_fd9_chart was asked with FD-9 support off")

    monkeypatch.setattr(fm, "is_fd9_chart", asked)
    assert not tab._fd9_on()
    assert not hasattr(tab, "_fd9_condition")
    for name in ("FD-9", "Konica Minolta FD-9"):
        ti2 = _fd9_chart(tmp_path, name)
        tab.set_ti1_path(ti2.with_suffix(".ti1"))
        assert tab._is_fd9_target() is False
        tab._refresh_start_button_label()
        assert not tab._read_builds_on_existing()


def test_the_stored_target_settings_carry_no_fd9_key(tab, tmp_path):
    from workflow.measure_settings import FD9_CONTROLS, snapshot
    tab.set_ti1_path(_fd9_chart(tmp_path).with_suffix(".ti1"))
    assert not set(FD9_CONTROLS) & set(snapshot(tab))


def test_an_fd9_chart_is_refused_at_start_with_the_beta_named(
        tab, tmp_path, monkeypatch):
    """Requirement 3: an FD-9 chart with the option off is refused at Start
    with M-FD9-SUPPORT-OFF, and nothing is started."""
    shown = []
    monkeypatch.setattr(tab, "_fd9_support_off_window",
                        lambda: shown.append("M-FD9-SUPPORT-OFF"))
    monkeypatch.setattr(tab, "_repair_target_instrument", lambda *a: pytest.fail(
        "an FD-9 chart must not be offered a name 'correction'"))
    for name in ("FD-9", "Konica Minolta FD-9"):
        ti2 = _fd9_chart(tmp_path, name)
        tab.set_ti1_path(ti2.with_suffix(".ti1"))
        assert tab._blocked_by_unusable_target_instrument() is True
    assert shown == ["M-FD9-SUPPORT-OFF"] * 2


def test_the_chartread_option_lock_is_4321s(tab):
    """The FD-9's option lock is a second lock; off, it never engages."""
    tab._set_settings_enabled(False)
    assert not tab._g_options.isEnabled()
    tab._set_settings_enabled(True)
    assert tab._g_options.isEnabled() and tab._save_defaults_btn.isEnabled()


def test_the_lists_and_the_instrument_flag_are_4321s():
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.ti2_relayout import instrument_to_flag
    import ui.tabs.tab_chart  # noqa: F401  (imports cleanly with the option off)
    assert "FD9" not in dict(LayoutOptionsPanel.instruments())
    assert instrument_to_flag("Konica Minolta FD-9") == "i1"
    assert instrument_to_flag("FD-9") == "i1"


#: Files outside the FD-9's own modules that name the FD-9, each of which
#: asks the switch (`workflow.fd9.support`) before acting. A new file here is
#: a new hook: make it ask the switch, then add it, in the same commit.
FD9_OWN = ("workflow/fd9/", "ui/fd9_measurement.py", "ui/dialogs/fd9_sheet.py",
           "vendor/")
HOOKED_FILES = {
    "core/file_manager.py",          # .fd9.json companion; Run.fd9_sessions_dir
    "core/settings.py",              # the switch and the FD-9 keys' defaults
    "data/patch_db.py",              # the label; filtered by the switch
    "main.py",                       # latches the switch
    "ui/dialogs/layout_options_panel.py",
    "ui/dialogs/settings_dialog.py",  # the Beta row
    "ui/main_window.py",             # the patch set editor refusal
    "ui/tabs/tab_chart.py",
    "ui/tabs/tab_measure.py",
    "ui/licences.py",                # the licence notice section
    "workflow/chart_creator.py",     # instrument "FD9" only
    "workflow/chart_import.py",      # .fd9.json companion
    # NOT switched, on purpose: ArgyllCMS refuses -f on an FD-9 measurement
    # with the Beta on or off (THE FWA GATE; tests/test_fd9_fwa_gate.py).
    "workflow/fwa_gate.py",
    "workflow/layout_engine/chart.py",
    "workflow/layout_engine/geometry.py",
    "workflow/layout_engine/instruments.py",
    "workflow/layout_engine/papers.py",
    "workflow/layout_engine/presets.py",
    "workflow/measure_settings.py",
    "workflow/measurement_messages.py",
    "workflow/ti2_relayout.py",
}


def test_the_files_that_name_the_fd9_are_the_known_ones():
    pat = re.compile(r"fd9|fd-9", re.I)
    found = set()
    for base in ("core", "ui", "workflow", "data"):
        for p in (ROOT / base).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith(FD9_OWN):
                continue
            if pat.search(p.read_text(encoding="utf-8", errors="ignore")):
                found.add(rel)
    if pat.search((ROOT / "main.py").read_text(encoding="utf-8")):
        found.add("main.py")
    assert found == HOOKED_FILES, (
        f"new: {sorted(found - HOOKED_FILES)}; gone: "
        f"{sorted(HOOKED_FILES - found)}")


def test_the_layout_engine_knows_no_fd9_while_off(monkeypatch):
    """Review r2 S2: off, an FD-9 chart or recipe is one for an instrument the
    layout engine does not know, as in 4.3.21, and no FD-9 layout code runs.
    `workflow.fd9.chart` is made unimportable, so reaching for it fails here
    instead of quietly laying the chart out the FD-9's way."""
    import sys
    from workflow.layout_engine import geometry, instruments, papers
    from workflow.layout_engine.presets import LayoutRecipe, edge_spacers_effect
    monkeypatch.setitem(sys.modules, "workflow.fd9.chart", None)
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.build("FD9")
    recipe = LayoutRecipe(instrument="FD9", paper="A4", patch_w_mm=8.0,
                          patch_h_mm=8.0, fd9_gap_mm=1.0,
                          layout_mode="patch_first")
    with pytest.raises(ValueError, match="unknown instrument"):
        instruments.geom_from_build_kwargs(recipe.build_kwargs())
    with pytest.raises(ValueError, match="unknown instrument"):
        edge_spacers_effect(recipe)
    assert papers.list_papers("FD9") == papers.list_papers("no-such-device")
    # A geometry carrying the FD-9's key (none can be built while off) is
    # never sent down the FD-9's own packing either.
    from dataclasses import replace
    fake = replace(instruments.build("SS"), key="FD9")
    assert geometry._is_fd9(fake) is False
    geometry.compute(fake, 210.0, 297.0, 20)


def test_create_chart_settings_of_an_fd9_target_are_carried_while_off():
    """Review r2 S1, the rule itself: the stored FD-9 instrument, sheet,
    pages, margins and gap go back over the i1Pro the off tab falls back to,
    in the stored order, and nothing else of the user's is touched."""
    from workflow.fd9.support import carry_fd9_chart_keys
    stored_params = {"printtarg-i": {"enabled": True, "value": "FD9"},
                     "printtarg-p": {"enabled": True, "value": "137x300"},
                     "targen-f": {"enabled": True, "value": 300}}
    stored_ui = {"mode": "guided",
                 "guided": {"instrument": "FD9", "paper": "137x300",
                            "pages": 1, "precond": ""},
                 "engine_recipe": {"instrument": "FD9", "paper": "137x300",
                                   "margin_top": 6.0, "patch_w_mm": 8.0,
                                   "fd9_gap_mm": 1.0, "dpi": 300}}
    wanted = {"printtarg-i": {"enabled": True, "value": "i1"},
              "printtarg-p": {"enabled": True, "value": "A4"},
              "targen-f": {"enabled": True, "value": 400}}
    ui = {"mode": "manual",
          "guided": {"instrument": "i1", "paper": "A4", "pages": 3,
                     "precond": ""},
          "engine_recipe": {"instrument": "i1", "paper": "A4",
                            "margin_top": 38.0, "patch_w_mm": 8.0,
                            "dpi": 600}}
    import copy
    at_load = (copy.deepcopy(wanted), copy.deepcopy(ui))
    carry_fd9_chart_keys(wanted, ui, stored_params, stored_ui, at_load)
    assert wanted == {**stored_params, "targen-f": {"enabled": True,
                                                    "value": 400}}
    assert ui["mode"] == "manual"
    assert ui["guided"] == stored_ui["guided"]
    assert ui["engine_recipe"] == {**stored_ui["engine_recipe"], "dpi": 600}
    assert list(ui["engine_recipe"]) == list(stored_ui["engine_recipe"])
    # An i1Pro target stored with the Beta off is left alone.
    plain = {"guided": {"instrument": "i1", "paper": "A4", "pages": 2}}
    ui2 = {"guided": {"instrument": "i1", "paper": "A3", "pages": 1}}
    carry_fd9_chart_keys({}, ui2, {}, plain, ({}, copy.deepcopy(ui2)))
    assert ui2 == {"guided": {"instrument": "i1", "paper": "A3", "pages": 1}}


def _fd9_stored():
    params = {"printtarg-i": {"enabled": True, "value": "FD9"},
              "printtarg-p": {"enabled": True, "value": "A4"}}
    ui = {"guided": {"instrument": "FD9", "paper": "A4", "pages": 1},
          "engine_recipe": {"instrument": "FD9", "paper": "A4",
                            "margin_top": 6.0, "fd9_gap_mm": 1.0}}
    return params, ui


def test_a_value_the_user_changed_with_the_beta_off_is_the_users():
    """Review r3 R3-1: only a value still as the off load left it is carried.
    A paper and page count the user picked are written as picked."""
    import copy
    from workflow.fd9.support import carry_fd9_chart_keys
    stored_params, stored_ui = _fd9_stored()
    at_load = ({"printtarg-i": {"enabled": True, "value": "i1"},
                "printtarg-p": {"enabled": True, "value": "A4"}},
               {"guided": {"instrument": "i1", "paper": "A4", "pages": 1},
                "engine_recipe": {"instrument": "i1", "paper": "A4",
                                  "margin_top": 38.0}})
    wanted = {"printtarg-i": {"enabled": True, "value": "i1"},
              "printtarg-p": {"enabled": True, "value": "Letter"}}
    ui = {"guided": {"instrument": "i1", "paper": "Letter", "pages": 2},
          "engine_recipe": {"instrument": "i1", "paper": "Letter",
                            "margin_top": 38.0}}
    carry_fd9_chart_keys(wanted, ui, stored_params, stored_ui,
                         copy.deepcopy(at_load))
    assert wanted["printtarg-p"]["value"] == "Letter"
    assert wanted["printtarg-i"]["value"] == "FD9"       # untouched: carried
    assert ui["guided"] == {"instrument": "FD9", "paper": "Letter",
                            "pages": 2}
    assert ui["engine_recipe"]["paper"] == "Letter"
    assert ui["engine_recipe"]["margin_top"] == 6.0      # untouched: carried


def test_without_a_snapshot_nothing_is_carried():
    """No snapshot = the user generated into the target, or its chart is not
    an FD-9 chart any more: the screen is written as it is."""
    from workflow.fd9.support import carry_fd9_chart_keys
    stored_params, stored_ui = _fd9_stored()
    wanted = {"printtarg-i": {"enabled": True, "value": "i1"}}
    ui = {"guided": {"instrument": "i1", "paper": "A4", "pages": 1}}
    carry_fd9_chart_keys(wanted, ui, stored_params, stored_ui, None)
    assert wanted == {"printtarg-i": {"enabled": True, "value": "i1"}}
    assert ui == {"guided": {"instrument": "i1", "paper": "A4", "pages": 1}}


@pytest.mark.parametrize("line, answer", [
    ('TARGET_INSTRUMENT "Konica Minolta FD-9"', True),
    ('TARGET_INSTRUMENT "FD-9"', True),
    ("TARGET_INSTRUMENT 'fd-9'", True),
    ('TARGET_INSTRUMENT "GretagMacbeth i1 Pro"', False),
    ('DESCRIPTOR "made for the FD-9"', False),
])
def test_the_chart_is_asked_by_its_target_instrument(tmp_path, line, answer):
    from workflow.fd9.support import chart_names_fd9
    ti2 = tmp_path / "x.ti2"
    ti2.write_bytes(("CTI2\n\n" + line + "\nBEGIN_DATA_FORMAT\n"
                     'TARGET_INSTRUMENT "FD-9"\n').encode("cp1252"))
    assert chart_names_fd9(ti2) is answer
    assert chart_names_fd9(tmp_path / "missing.ti2") is None
