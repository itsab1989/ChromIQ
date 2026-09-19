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


def test_the_window_offers_the_three_buttons(qapp_or_skip):
    """The door a person actually presses, not just the function behind it."""
    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    for name in ("_on_iso_template", "_on_iso_use", "_on_iso_forget",
                 "_sync_iso_buttons"):
        assert callable(getattr(ThresholdsDialog, name, None)), name


@pytest.fixture()
def qapp_or_skip():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_row_carries_an_info_icon_and_not_three_hover_tooltips(qapp_or_skip,
                                                                   tmp_path,
                                                                   monkeypatch):
    """Basti, 2026-09-20, asked two questions about the door I had just built:
    whether the file dialogs are ChromIQ's own with the useful shortcuts down
    the left, and whether there is *"a tooltip icon that opens a tooltip window
    - friendly extensive easy to understand and correct"*.

    The first was already true: `open_file_dialog` and `save_file_dialog` are
    the app's own unless the user has turned native dialogs on in Preferences,
    and they carry an OS-correct localized sidebar. The second was not. Three
    hover tooltips are three sentences nobody reads together, and every other
    control in this app explains itself through an ⓘ that opens a window.

    This pins the ⓘ and what it has to cover, because an info window that does
    not say why the numbers are missing, or that the values never leave the
    computer, is the half-answer that made the question necessary.
    """
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.tooltip_button import TooltipButton

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s)
    try:
        body = ""
        for b in dlg.findChildren(TooltipButton):
            t = (getattr(b, "_title", "") or "") + (getattr(b, "_body", "") or "")
            if "limit values" in t.lower() or "ISO 12647-7" in t:
                body = t
                break
        assert body, "the ISO row has no ⓘ of its own"
        for must in ("Save a file to fill in", "Use a file I filled in",
                     "Stop using it"):
            assert must in body, f"the ⓘ does not mention {must!r}"
        assert "paid standard" in body, "it does not say WHY the numbers are absent"
        assert "does not send them anywhere" in body, \
            "it does not say the values stay on this computer"
        assert "—" not in body, "em dash in user-facing text"
    finally:
        dlg.close()


def test_pressing_each_button_really_runs(qapp_or_skip, tmp_path, monkeypatch):
    """PRESS THE BUTTONS. The first version of this file read the slots'
    SOURCE with `inspect.getsource` and asserted the right names appeared in
    it, and it passed while all three buttons did nothing at all: `Path` was
    never imported into `thresholds_dialog`, every slot raised `NameError`, and
    Qt swallows an exception raised inside a slot. Basti found it in the
    shipped beta 26 within minutes: *"clicking save a file to fill in does
    nowthing"*.

    That is this project's oldest shape, a guard that tests the HELPER instead
    of the DOOR, and reading source text is the purest form of it. So this
    calls the slots, with the file dialogs and the info window replaced, and a
    NameError anywhere in any of them fails the test.
    """
    import ui.widgets as W
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    monkeypatch.setenv("CHROMIQ_PRESETS_DIR", str(tmp_path / "presets"))
    monkeypatch.delenv(cs.ISO_DATA_ENV, raising=False)
    cs.reset_iso_cache()

    template = tmp_path / "template.json"
    asked: dict = {}
    monkeypatch.setattr(W, "save_file_dialog",
                        lambda *a, **k: (asked.update(save=k), str(template))[1])
    monkeypatch.setattr(W, "open_file_dialog",
                        lambda *a, **k: (asked.update(open=k), str(template))[1])

    s_ = AppSettings()
    s_._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s_)
    said: list = []
    dlg._iso_say = said.append
    try:
        dlg._iso_template_btn.click()
        assert template.is_file(), "the first button wrote nothing"
        assert json.loads(template.read_text(encoding="utf-8"))["iso_12647_7"]

        # the dialogs are the app's own and offer the folder as a shortcut
        assert "extra_paths" in asked["save"], "no shortcut offered"

        dlg._iso_use_btn.click()
        assert cs.user_values_path().is_file(), "the second button installed nothing"
        assert dlg._iso_forget_btn.isEnabled()

        dlg._iso_forget_btn.click()
        assert not cs.user_values_path().is_file(), "the third button removed nothing"
        # saved, using-it, reopen-to-see, and back-to-ours: four sentences,
        # one per thing that happened, which is what a reader needs to follow.
        assert len(said) == 5, said
    finally:
        dlg.close()
        cs.reset_iso_cache()


def test_the_three_buttons_and_the_icon_match_the_window(qapp_or_skip, tmp_path):
    """Basti on beta 26: *"the three buttons should be reduced in heigth and
    the report limits window seemingly uses the green accent color so the new
    tooltip icon should as well"*. Both pinned, both measured off the widgets
    rather than off the stylesheet."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.styles import SPEC_GREEN
    from ui.tooltip_button import TooltipButton

    s_ = AppSettings()
    s_._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    dlg = ThresholdsDialog(s_)
    try:
        for b in (dlg._iso_template_btn, dlg._iso_use_btn, dlg._iso_forget_btn):
            assert b.height() <= 24, f"{b.text()!r} is {b.height()} px tall"
        icon = None
        for t in dlg.findChildren(TooltipButton):
            if "limit values" in (getattr(t, "_title", "") or "").lower():
                icon = t
                break
        assert icon is not None
        assert getattr(icon, "_color_override", None) == SPEC_GREEN, (
            "the info icon does not take this window's green accent")
    finally:
        dlg.close()


def test_the_file_dialogs_are_the_apps_own_with_its_sidebar():
    """Not the OS dialog, unless the user asked for it in Preferences.

    ChromIQ's own dialog is what carries the shortcuts down the left: Desktop,
    Pictures, Downloads, Documents, the app's working folder, and whatever the
    caller adds. These two calls add the folder the values file lives in, so a
    reader who saved a template yesterday can get back to it.
    """
    import inspect

    from ui.dialogs import thresholds_dialog as td

    for name in ("_on_iso_template", "_on_iso_use"):
        src = inspect.getsource(getattr(td.ThresholdsDialog, name))
        assert "_file_dialog(" in src, f"{name} does not use the app's dialog"
        assert "QFileDialog" not in src, f"{name} reaches past the app's own"
        assert "extra_paths" in src, f"{name} offers no shortcut to the folder"
        assert "DocumentsLocation" in src, f"{name} starts somewhere unhelpful"
