"""Supplying a standard's own limit values must not need a terminal.

ChromIQ keeps the ISO 12647 tolerance values out of its own code and reads them
from a file the user supplies. Until 2026-09-20 the only way to name that file
was the environment variable `CHROMIQ_COMPLIANCE_ISO_FILE`, and the only way to
get a file of the right shape was `python scripts/iso_values_template.py`.

**Both are developer doors.** A shipped ChromIQ is a `.dmg`, a `.zip` or a
`.tar.gz` with no `scripts/` folder in it, and a variable exported in a shell
never reaches an app launched from Finder, the Dock, the Start menu or a
desktop file. So the feature existed and nobody outside this checkout could
use it. Basti, 2026-09-20: *"i just hope this is straightforward and does not
require any special knowledge"*, and *"whatever you do must work on win and
linux as well"*.

This file pins the door that answers both: a known location derived the same
way the presets folder is derived on each platform, and three buttons in the
Report limits window that write the template, install a filled-in file and
remove it again.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core import platform_paths as pp  # noqa: E402
from workflow import compliance_sets as cs  # noqa: E402


@pytest.fixture()
def own_folder(tmp_path, monkeypatch):
    """Point the whole per-platform chain at a temp folder."""
    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    monkeypatch.delenv(cs.ISO_DATA_ENV, raising=False)
    cs.reset_iso_cache()
    yield tmp_path
    cs.reset_iso_cache()


def test_the_folder_is_beside_the_presets_on_every_platform(monkeypatch):
    """Not a hard-coded macOS path: the same derivation the presets use.

    `presets_dir()` already answers %APPDATA%\\ChromIQ on Windows,
    ~/Library/Preferences/ChromIQ on macOS and $XDG_CONFIG_HOME/ChromIQ on
    Linux. Deriving from it is what makes this work on all three without this
    test having to know which one it is running on.
    """
    monkeypatch.delenv("CHROMIQ_PRESETS_DIR", raising=False)
    assert pp.compliance_dir().parent == pp.presets_dir().parent
    assert pp.compliance_dir().name == "compliance"

    for plat, marker in (("win32", "ChromIQ"), ("darwin", "ChromIQ"),
                         ("linux", "ChromIQ")):
        monkeypatch.setattr(pp.sys, "platform", plat)
        assert marker in str(pp.compliance_dir()), plat


def test_a_filled_in_file_is_used_and_then_forgotten(own_folder):
    """The three buttons' whole journey, without a shell or a variable."""
    assert cs.iso_data_path_text() == "", "a fresh install starts with none"
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"].kind == "unknown"

    # 1. the template, as the first button writes it
    filled = own_folder / "mine.json"
    doc = json.loads(cs.iso_values_template())
    doc["iso_12647_7"]["all_de00_avg"] = 1.9
    filled.write_text(json.dumps(doc), encoding="utf-8")

    # 2. the second button
    where = cs.install_user_values(filled)
    assert where == cs.user_values_path()
    assert where.is_file(), "the file was not copied into ChromIQ's own folder"
    assert cs.iso_data_path_text() == str(where)
    lim = cs.factory_limits("iso_12647_7")["all_de00_avg"]
    assert lim.kind == "value" and lim.number == pytest.approx(1.9)

    # it is COPIED, so tidying up the source does not take the values away
    filled.unlink()
    cs.reset_iso_cache()
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"].number == \
        pytest.approx(1.9)

    # 3. the third button
    assert cs.forget_user_values() is True
    assert cs.iso_data_path_text() == ""
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"].kind == "unknown"
    assert cs.forget_user_values() is False, "removing nothing is not an event"


def test_rubbish_is_refused_before_it_is_installed(own_folder):
    """A hand-edited file with a trailing comma must not become the live one."""
    bad = own_folder / "bad.json"
    bad.write_text('{"iso_12647_7": {"all_de00_avg": 1.9,}}', encoding="utf-8")
    with pytest.raises(ValueError):
        cs.install_user_values(bad)
    assert not cs.user_values_path().is_file()
    assert cs.iso_data_path_text() == ""


def test_the_environment_variable_still_wins(own_folder, monkeypatch):
    """The developer door stays open: the suite and this checkout use it."""
    doc = json.loads(cs.iso_values_template())
    doc["iso_12647_7"]["all_de00_avg"] = 1.1
    own = own_folder / "own.json"
    own.write_text(json.dumps(doc), encoding="utf-8")
    cs.install_user_values(own)

    doc["iso_12647_7"]["all_de00_avg"] = 2.2
    env = own_folder / "env.json"
    env.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(env))
    cs.reset_iso_cache()
    assert cs.factory_limits("iso_12647_7")["all_de00_avg"].number == \
        pytest.approx(2.2)
    cs.forget_user_values()


@pytest.fixture()
def qapp_or_skip():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_pressing_each_button_really_runs(qapp_or_skip, tmp_path, monkeypatch):
    """PRESS THE BUTTONS. The first version of this file read the slots'
    SOURCE with `inspect.getsource` and asserted the right names appeared in
    it, and it passed while all three buttons did nothing at all: `Path` was
    never imported, every slot raised `NameError`, and Qt swallows an exception
    raised inside a slot. Basti found it in the shipped beta 26 within minutes.

    That is this project's oldest shape, a guard that tests the HELPER instead
    of the DOOR, and reading source text is the purest form of it.

    The three buttons now live in `ReferenceValuesDialog`, one section per
    source, because Basti saw that one data source costing three buttons meant
    two would cost six. This presses them where they are.
    """
    import ui.widgets as W
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog

    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    monkeypatch.delenv(cs.ISO_DATA_ENV, raising=False)
    cs.reset_iso_cache()

    template = tmp_path / "template.json"
    asked: dict = {}
    monkeypatch.setattr(W, "save_file_dialog",
                        lambda *a, **k: (asked.update(save=k), str(template))[1])
    monkeypatch.setattr(W, "open_file_dialog",
                        lambda *a, **k: (asked.update(open=k), str(template))[1])

    dlg = ReferenceValuesDialog()
    said: list = []
    dlg._say = said.append
    try:
        src, state, forget = dlg._rows[0]
        assert not forget.isEnabled(), "nothing is supplied, so nothing to forget"
        assert "Nothing supplied" in state.text()

        dlg._template(src)
        assert template.is_file(), "the first button wrote nothing"
        assert json.loads(template.read_text(encoding="utf-8"))["iso_12647_7"]

        dlg._install(src)
        assert cs.user_values_path().is_file(), "the second button installed nothing"
        assert forget.isEnabled()
        assert "In use:" in state.text(), "the window does not say what is in use"

        dlg._forget(src)
        assert not cs.user_values_path().is_file(), "the third button removed nothing"
        assert not forget.isEnabled()
        assert len(said) == 3, said
    finally:
        dlg.close()
        cs.reset_iso_cache()


def test_the_report_limits_window_has_one_door_and_it_is_small(qapp_or_skip,
                                                               tmp_path):
    """Basti, twice on the shipped beta: *"the three buttons should be reduced
    in heigth"*, then *"the current ones are still big ... they could be
    smaller i think"*, and then the reason it matters: *"if you are putting in
    3 more buttons there will be quite a lot in the end"*.

    So the Report limits window carries ONE button, at 18 px, which is that
    window's own smallest interactive control, its check boxes. The three
    actions moved behind it. This guard fails the day a second one appears
    beside it, which is the failure he predicted.
    """
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QPushButton
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    s_ = AppSettings()
    s_._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s_)
    try:
        # 26, AND THE 18 THIS ONCE ASSERTED WAS NEVER ON SCREEN. The door was
        # built with `setFixedHeight(18)`, which this read back happily from a
        # dialog that was never shown -- while the app's own stylesheet
        # (`QPushButton { padding: 6px 18px; min-height: 28px; }`) made it
        # 42 px in the window, which is what Basti was looking at when he asked
        # a SECOND time for it to be smaller. Round 30 measured it and it is a
        # per-widget stylesheet now, the same one the window's own "Restore
        # this column" button has always used: 26 px, laid out, everywhere.
        # `tests/test_a_short_button_is_short_on_screen.py` is the guard that
        # can see this, because it shows the dialog first; this line only has
        # to stop being a lie.
        assert dlg._iso_values_btn.height() == 26, dlg._iso_values_btn.height()
        # and it is alone: no leftover sibling from the three-button version
        for name in ("_iso_template_btn", "_iso_use_btn", "_iso_forget_btn"):
            assert not hasattr(dlg, name), f"{name} is still in this window"
        # the grey line says which numbers are in force without a click
        assert dlg._iso_state_lbl.text(), "the window does not say what is in use"
    finally:
        dlg.close()


def test_a_second_source_costs_no_button_in_the_report_limits_window():
    """The whole point of the one door: Fogra's characterisation data joins
    `sources()` and the Report limits window does not change at all."""
    import inspect

    from ui.dialogs import reference_values_dialog as rv

    src = inspect.getsource(rv.sources)
    assert "iso_source()" in src
    # the window builds a section per source, so a second entry is a section
    assert "for src in sources():" in inspect.getsource(rv.ReferenceValuesDialog.__init__)


def test_the_window_behind_the_door_explains_itself(qapp_or_skip):
    """What the dropped icon guard was really protecting, kept.

    The three hover tooltips and the one ⓘ in the Report limits window are
    gone with the three buttons. The explanation moved into the window behind
    the door, and the two sentences that exist purely to reassure a reader must
    survive any future edit of it: WHY ChromIQ has no numbers of its own, and
    that what you supply never leaves the computer.
    """
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog, iso_source

    src = iso_source()
    assert "paid standard" in src.why, "it does not say WHY the numbers are absent"
    help_text = ReferenceValuesDialog._help(src)
    for must in ("Save a file to fill in", "Use a file I filled in",
                 "Stop using it"):
        assert must in help_text, f"the ⓘ does not mention {must!r}"
    assert "does not send them anywhere" in help_text, \
        "it does not say the values stay on this computer"
    assert "—" not in help_text and "—" not in src.why, "em dash"
