"""The ArgyllCMS command boxes (a dpreview request, 2026-11-02).

ThrillaMozilla asked for "a record of the commands sent to Argyll"; Basti asked
for a box on every Build Profile module, in the tab's cyan, and one switch in
Preferences → General that hides these boxes and the Create Chart ones.

The rule these tests hold: **the box shows the command the button runs.** Each
check below reads the box, then presses the module's own button with
``ArgyllRunner.run`` caught, and compares the two argument lists. A box built
by a second, drifting reimplementation would pass a test that only reads the
box; it cannot pass these.
"""
from __future__ import annotations

import inspect
import shlex
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.widgets import ARGYLL_COMMANDS_PROPERTY  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path, **prefs) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    for k, v in prefs.items():
        s.set(k, v)
    return s


def _tab(tmp_path, monkeypatch, **prefs):
    from ui.tabs.tab_profile import TabProfile
    s = _settings(tmp_path, **prefs)
    runner = ArgyllRunner(s)
    calls: list = []
    monkeypatch.setattr(runner, "run",
                        lambda tool, args, cwd, **k: calls.append(
                            (tool, list(args), Path(cwd))))
    tab = TabProfile(runner, s)
    return tab, calls


def _measurement(tmp_path, name="My Printer.ti3", rep="RGB_LAB") -> Path:
    folder = tmp_path / "a folder with spaces"
    folder.mkdir(exist_ok=True)
    ti3 = folder / name
    ti3.write_text(f'CTI3\nCOLOR_REP "{rep}"\n', encoding="utf-8")
    return ti3


def _press_build(tab, monkeypatch):
    """Build Profile's own button, with every question answered "go on"."""
    for name in ("_confirm_build_from_incomplete",
                 "_confirm_building_outside_the_selected_run",
                 "_confirm_rebuild_over_verifications",
                 "_validate_gamut_source"):
        monkeypatch.setattr(tab, name, lambda *a, **k: True)
    monkeypatch.setattr(tab, "_refuse_when_the_profiler_is_not_installed",
                        lambda *a, **k: False)
    monkeypatch.setattr(tab, "_archive_the_profile_being_replaced",
                        lambda *a, **k: None)
    tab._on_build()


def _command_lines(box_text: str, tool: str) -> "list[list[str]]":
    return [shlex.split(line) for line in box_text.splitlines()
            if line.startswith(tool + " ")]


# ---------------------------------------------------------------------------
# Build Profile (colprof)
# ---------------------------------------------------------------------------

def _set_manual(tab, *, quality=None, algorithm=None, description=None,
                k_rule=None, illuminant=None):
    if quality:
        tab._m_qual_combo.setCurrentIndex(tab._m_qual_combo.findData(quality))
    if algorithm:
        tab._m_algo_combo.setCurrentIndex(tab._m_algo_combo.findData(algorithm))
    if description is not None:
        tab._m_desc_edit.setText(description)
    if k_rule:
        tab._m_kgen_combo.setCurrentIndex(tab._m_kgen_combo.findData(k_rule))
    if illuminant:
        tab._m_illum_combo.setCurrentIndex(
            tab._m_illum_combo.findData(illuminant))


@pytest.mark.parametrize("mode,changes", [
    ("guided", {}),
    ("manual", {}),
    ("manual", {"quality": "h", "description": "Epson P900 – Hahnemühle's"}),
    ("manual", {"algorithm": "x", "k_rule": "p", "quality": "l"}),
    ("manual", {"illuminant": "D65", "description": "two  spaces"}),
])
def test_the_colprof_box_shows_the_command_the_build_runs(
        qapp, tmp_path, monkeypatch, mode, changes):
    tab, calls = _tab(tmp_path, monkeypatch)
    tab._switch_mode(mode)
    tab.set_ti3_path(_measurement(tmp_path))
    if mode == "manual":
        _set_manual(tab, **{k: v for k, v in changes.items()
                            if v is not None})
    tab.refresh_argyll_commands(every=True)
    box = tab._guided_cmd_box if mode == "guided" else tab._manual_cmd_box
    shown = _command_lines(box.text(), "colprof")
    assert len(shown) == 1, box.text()

    _press_build(tab, monkeypatch)
    assert [c[0] for c in calls] == ["colprof"]
    assert shown[0] == ["colprof"] + calls[0][1], (
        "the box shows a colprof command the build does not run")
    tab.deleteLater()


def test_the_box_follows_a_change_without_being_asked(qapp, tmp_path,
                                                       monkeypatch):
    """Live: a changed control rewrites the box on its own (debounced)."""
    tab, _calls = _tab(tmp_path, monkeypatch)
    tab._switch_mode("manual")
    tab.set_ti3_path(_measurement(tmp_path))
    tab.refresh_argyll_commands(every=True)
    before = tab._manual_cmd_box.text()
    tab._m_qual_combo.setCurrentIndex(tab._m_qual_combo.findData("u"))
    tab._argyll_cmd_timer.timeout.emit()      # the debounce, without waiting
    after = tab._manual_cmd_box.text()
    assert before != after and "-qu" in after
    tab.deleteLater()


def test_no_measurement_yet_shows_a_placeholder_and_says_so(qapp, tmp_path,
                                                            monkeypatch):
    from core.i18n import tr
    tab, _calls = _tab(tmp_path, monkeypatch)
    tab.refresh_argyll_commands(every=True)
    text = tab._guided_cmd_box.text()
    assert tr("<measurement>") in text
    assert tr("Names in angle brackets stand for files you have not chosen "
              "yet.") in text
    tab.deleteLater()


def test_the_engine_build_shows_no_colprof_command(qapp, tmp_path,
                                                   monkeypatch):
    """The ChromIQ engine builds the profile itself; a colprof line would be
    a record of a command nobody ran."""
    import ui.tabs.tab_profile as tp
    monkeypatch.setattr(tp, "engine_support", lambda _p: (True, ""))
    tab, _calls = _tab(tmp_path, monkeypatch, profile_engine_beta=True,
                       gammap_mode="fast")
    tab.set_ti3_path(_measurement(tmp_path))
    tab.refresh_argyll_commands(every=True)
    text = tab._guided_cmd_box.text()
    assert not _command_lines(text, "colprof")
    assert "ChromIQ profile engine" in text
    tab.deleteLater()


def test_bit_exact_still_shows_colprof(qapp, tmp_path, monkeypatch):
    tab, calls = _tab(tmp_path, monkeypatch, profile_engine_beta=True,
                      gammap_mode="argyll")
    tab.set_ti3_path(_measurement(tmp_path))
    tab.refresh_argyll_commands(every=True)
    shown = _command_lines(tab._guided_cmd_box.text(), "colprof")
    _press_build(tab, monkeypatch)
    assert shown == [["colprof"] + calls[0][1]]
    tab.deleteLater()


def test_a_multi_ink_measurement_without_the_engine_says_why(
        qapp, tmp_path, monkeypatch):
    tab, _calls = _tab(tmp_path, monkeypatch, profile_engine_beta=False)
    tab.set_ti3_path(_measurement(tmp_path, rep="CMYKOG_LAB"))
    tab.refresh_argyll_commands(every=True)
    text = tab._guided_cmd_box.text()
    assert not _command_lines(text, "colprof")
    assert "Preferences → Beta" in text
    tab.deleteLater()


def test_refinement_shows_the_average_merge_then_colprof_on_merged(
        qapp, tmp_path, monkeypatch):
    from core.file_manager import Run
    from workflow.ti3_merge import average_merge_args
    tab, _calls = _tab(tmp_path, monkeypatch, chromiq_refinement=True)
    folder = tmp_path / "a folder with spaces"
    folder.mkdir()
    ti3 = _ti3(folder / "My Printer.ti3")     # two files the merge accepts
    tab.set_ti3_path(ti3)
    pre = _ti3(folder / "preconditioning.ti3")
    tab.set_preconditioning_source(pre)
    tab.refresh_argyll_commands(every=True)
    text = tab._guided_cmd_box.text()
    merged = Run.for_dir(ti3.parent).merged_ti3
    assert _command_lines(text, "average") == [
        ["average"] + average_merge_args(ti3, pre, merged)]
    colprof = _command_lines(text, "colprof")
    assert colprof and colprof[0][-1] == str(merged.with_suffix(""))
    # …in that order, as the build runs them.
    assert text.index("\naverage ") < text.index("\ncolprof ")
    tab.deleteLater()


def test_the_merge_runs_the_arguments_the_box_shows():
    """`merge_preconditioning` takes its argument list from the same function
    the box uses."""
    import workflow.ti3_merge as tm
    src = inspect.getsource(tm.merge_preconditioning)
    assert "average_merge_args(fresh_ti3, pre_data, out_ti3)" in src


# ---------------------------------------------------------------------------
# Create Calibration File (printcal) and Apply Calibration (applycal)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode,dry,desc", [
    ("initial", False, ""),
    ("recalibrate", True, "Epson P900 cal"),
    ("imitation", False, "Café"),
])
def test_the_printcal_box_shows_the_command_create_calibration_runs(
        qapp, tmp_path, monkeypatch, mode, dry, desc):
    tab, calls = _tab(tmp_path, monkeypatch)
    ti3 = _measurement(tmp_path, name="My Cal.ti3")
    tab._cal_ti3_path = ti3
    tab._pc_mode_combo.setCurrentIndex(tab._pc_mode_combo.findData(mode))
    tab._pc_dry_run_cb.setChecked(dry)
    tab._pc_prev_edit.setText(str(tmp_path / "old one.cal"))
    tab._pc_desc_edit.setText(desc)
    tab.refresh_argyll_commands(every=True)
    lines = tab._pc_cmd_box.text().splitlines()
    cd = next(line for line in lines if line.startswith("cd "))
    shown = _command_lines(tab._pc_cmd_box.text(), "printcal")

    monkeypatch.setattr(tab, "_confirm_build_from_incomplete",
                        lambda *a, **k: True)
    tab._on_printcal_run()
    tool, args, cwd = calls[0]
    assert tool == "printcal"
    assert shown == [["printcal"] + args]
    assert shlex.split(cd) == ["cd", str(cwd)]
    tab.deleteLater()


@pytest.mark.parametrize("mode,verbose,out", [
    ("apply", False, ""),
    ("remove", True, "custom out.icc"),
    ("check", False, ""),
])
def test_the_applycal_box_shows_the_command_apply_calibration_runs(
        qapp, tmp_path, monkeypatch, mode, verbose, out):
    tab, calls = _tab(tmp_path, monkeypatch)
    icc = tmp_path / "a folder" / "My Profile.icc"
    icc.parent.mkdir()
    icc.write_bytes(b"icc")
    tab._ac_cal_edit.setText(str(tmp_path / "my cal.cal"))
    tab._ac_in_edit.setText(str(icc))
    tab._ac_out_edit.setText(str(tmp_path / out) if out else "")
    tab._ac_mode_combo.setCurrentIndex(tab._ac_mode_combo.findData(mode))
    tab._ac_verbose_cb.setChecked(verbose)
    tab.refresh_argyll_commands(every=True)
    shown = _command_lines(tab._ac_cmd_box.text(), "applycal")

    monkeypatch.setattr(tab, "_confirm_not_calibrated_twice",
                        lambda *a, **k: True)
    tab._on_applycal_run()
    assert calls and calls[0][0] == "applycal"
    assert shown == [["applycal"] + calls[0][1]]
    tab.deleteLater()


# ---------------------------------------------------------------------------
# The Preferences switch
# ---------------------------------------------------------------------------

def test_the_switch_exists_and_is_on_by_default():
    """Everything as it was plus the new boxes, until Basti turns it off."""
    from core.settings import DEFAULTS
    assert DEFAULTS["show_argyll_commands"] is True


def test_every_box_of_the_profile_tab_carries_the_mark_and_the_cyan_shape(
        qapp, tmp_path, monkeypatch):
    tab, _calls = _tab(tmp_path, monkeypatch)
    for attr in ("_guided_cmd_box", "_manual_cmd_box", "_pc_cmd_box",
                 "_ac_cmd_box"):
        box = getattr(tab, attr)
        assert box.property(ARGYLL_COMMANDS_PROPERTY) is True, attr
        # Cyan ink, border AND ground, in every theme's sheet.
        assert box.objectName() == "info_profile", attr
        assert not box.isHidden(), attr
        from PyQt6.QtCore import Qt
        assert box.textInteractionFlags() & \
            Qt.TextInteractionFlag.TextSelectableByMouse, attr
    tab.deleteLater()


def test_every_theme_styles_the_cyan_box():
    import ui.light_styles as ls
    import ui.neutral_styles as ns
    import ui.styles as st
    for mod in (st, ls, ns):
        assert "QLabel#info_profile" in inspect.getsource(mod), mod.__name__


def test_with_the_switch_off_the_boxes_start_hidden(qapp, tmp_path,
                                                    monkeypatch):
    tab, _calls = _tab(tmp_path, monkeypatch, show_argyll_commands=False)
    for attr in ("_guided_cmd_box", "_manual_cmd_box", "_pc_cmd_box",
                 "_ac_cmd_box"):
        assert getattr(tab, attr).isHidden(), attr
    tab.deleteLater()


def test_the_create_chart_boxes_carry_the_mark_and_the_measure_box_does_not():
    import ui.tabs.tab_chart as tc
    import ui.tabs.tab_measure as tm
    src = inspect.getsource(tc.TabChart)
    for name in ("_guided_info_lbl", "_manual_info_lbl"):
        assert (f"self.{name}.setProperty(ARGYLL_COMMANDS_PROPERTY, True)"
                in src), name
    # The Measure tab's box lists what Guided leaves at its standard settings:
    # guidance, not a command, so the switch leaves it alone.
    assert "ARGYLL_COMMANDS_PROPERTY" not in inspect.getsource(tm)


def test_main_window_finds_the_boxes_by_their_mark_at_startup_and_after_ok():
    import ui.main_window as mw
    body = inspect.getsource(mw.MainWindow._apply_argyll_command_visibility)
    assert "ARGYLL_COMMANDS_PROPERTY" in body
    assert "findChildren(QWidget)" in body
    for tab in ("_tab_chart", "_tab_measure"):
        assert tab not in body, f"{tab} is named; the mark is the list"
    src = inspect.getsource(mw.MainWindow)
    assert src.count("self._apply_argyll_command_visibility()") >= 2


def test_preferences_offers_it_with_a_tooltip_and_saves_it():
    import ui.dialogs.settings_dialog as sd
    src = inspect.getsource(sd)
    assert 'tr("Show the ArgyllCMS commands ChromIQ runs")' in src
    assert 'tr("Show the ArgyllCMS Commands ChromIQ Runs")' in src
    assert 's.set("show_argyll_commands"' in src
    assert 's.get("show_argyll_commands"' in src
    assert "_bh_cell(self._show_argyll_cmds_check, show_argyll_cmds_tip)" in src


# ---------------------------------------------------------------------------
# Review round 1
# ---------------------------------------------------------------------------

def _ti3(path: Path, rep="RGB_LAB", fields="SAMPLE_ID RGB_R RGB_G RGB_B "
         "LAB_L LAB_A LAB_B", ink=None) -> Path:
    head = f'CTI3\nCOLOR_REP "{rep}"\n'
    if ink is not None:
        head += f'TOTAL_INK_LIMIT "{ink}"\n'
    path.write_text(head + "BEGIN_DATA_FORMAT\n" + fields + "\nEND_DATA_FORMAT\n"
                    "BEGIN_DATA\n1 0 0 0 50 0 0\nEND_DATA\n", encoding="utf-8")
    return path


def test_a_merge_the_build_would_refuse_is_not_shown(qapp, tmp_path,
                                                      monkeypatch):
    """Finding 3: a different COLOR_REP makes the merge refuse and the build
    use the new measurement alone; the box says so and shows no average."""
    tab, _calls = _tab(tmp_path, monkeypatch, chromiq_refinement=True)
    folder = tmp_path / "run"
    folder.mkdir()
    ti3 = _ti3(folder / "Fresh.ti3")
    pre = _ti3(folder / "preconditioning.ti3", rep="CMYK_LAB")
    tab.set_ti3_path(ti3)
    tab.set_preconditioning_source(pre)
    tab.refresh_argyll_commands(every=True)
    text = tab._guided_cmd_box.text()
    assert not _command_lines(text, "average")
    colprof = _command_lines(text, "colprof")
    assert colprof and colprof[0][-1] == str(ti3.with_suffix(""))
    assert "built from the new measurement only" in text
    tab.deleteLater()


def test_the_ink_limit_comes_from_the_fresh_measurement_not_a_stale_merge(
        qapp, tmp_path, monkeypatch):
    """Finding 2: `average -m` keeps the first (fresh) file's
    TOTAL_INK_LIMIT; a stale merged.ti3 must not decide the box's -l."""
    from core.file_manager import Run
    tab, _calls = _tab(tmp_path, monkeypatch, chromiq_refinement=True)
    folder = tmp_path / "run"
    folder.mkdir()
    ti3 = _ti3(folder / "Fresh.ti3", ink=250)
    pre = _ti3(folder / "preconditioning.ti3")
    _ti3(Run.for_dir(folder).merged_ti3, ink=300)      # left from before
    tab.set_ti3_path(ti3)
    tab.set_preconditioning_source(pre)
    tab.refresh_argyll_commands(every=True)
    colprof = _command_lines(tab._guided_cmd_box.text(), "colprof")[0]
    assert "-l250" in colprof and "-l300" not in colprof
    tab.deleteLater()


def test_only_the_module_on_screen_is_refreshed(qapp, tmp_path, monkeypatch):
    """Finding 5: one box per refresh, not every module's."""
    tab, _calls = _tab(tmp_path, monkeypatch)
    tab.set_ti3_path(_measurement(tmp_path))
    tab._switch_mode("guided")
    tab._manual_cmd_box.setText("stale")
    tab.refresh_argyll_commands()
    assert tab._manual_cmd_box.text() == "stale"
    tab._switch_mode("manual")
    tab._argyll_cmd_timer.timeout.emit()
    assert "colprof " in tab._manual_cmd_box.text()
    tab.deleteLater()


def test_a_long_unbroken_token_wraps_instead_of_widening_the_box(qapp):
    """Finding 6: the box breaks a token with no space or sign in it, and
    what it hands to a copy is the text itself, with nothing inserted."""
    from ui.argyll_command_box import ArgyllCommandBox
    box = ArgyllCommandBox()
    word = "x" * 400
    box.setText("colprof -D " + word)
    assert box.minimumSizeHint().width() <= 60
    box.resize(300, 40)
    box.show()
    qapp.processEvents()
    lines = box.document().firstBlock().layout().lineCount()
    assert lines > 3, "the 400-character token was not broken"
    assert box.document().size().width() <= box.viewport().width() + 1
    assert box.height() > 40, "the box did not grow to its wrapped text"
    assert box.toPlainText() == "colprof -D " + word
    box.hide()
    box.deleteLater()


def test_windows_commands_are_written_for_powershell(monkeypatch):
    """Finding 1: single quotes, literal in PowerShell; `cd` without cmd's
    /d; a quoted program path behind PowerShell's call operator."""
    import workflow.argyll_command_text as act
    monkeypatch.setattr(act, "_windows", lambda: True)
    assert act.command_line("colprof", ["-D", "Tom & Jerry's 50%", "-al"]) \
        == "colprof -D 'Tom & Jerry''s 50%' -al"
    assert act.change_folder_line(r"C:\My Prints\run1") \
        == r"cd 'C:\My Prints\run1'"
    assert act.program_example(r"C:\Program Files\ArgyllCMS\bin\colprof.exe") \
        == r"& 'C:\Program Files\ArgyllCMS\bin\colprof.exe'"
    assert act.quote_arg("a,b") == "'a,b'"            # a comma is an array


def test_posix_commands_are_written_for_the_shell(monkeypatch):
    import workflow.argyll_command_text as act
    monkeypatch.setattr(act, "_windows", lambda: False)
    assert shlex.split(act.command_line("colprof", ["-D", "Tom & Jerry's"])) \
        == ["colprof", "-D", "Tom & Jerry's"]
    assert act.change_folder_line("/a b/c") == "cd '/a b/c'"
    assert act.program_example("/Applications/Argyll/bin/colprof") \
        == "/Applications/Argyll/bin/colprof"


def test_the_tooltip_names_the_shells_and_quotes_its_example():
    import ui.dialogs.settings_dialog as sd
    src = inspect.getsource(sd)
    assert "PowerShell on Windows" in src
    assert "_program_example(" in src
    assert "hides the boxes, and the Create Chart note" in src
