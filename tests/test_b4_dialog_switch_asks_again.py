"""Knut, #182, 2026-10-13: when "Use default macOS printer dialog" is changed,
the project asks again how a PostScript printer gets the chart.

The setting is global (Preferences), so it counts its own switches
(``print_dialog_setting_changes``) and each project keeps the count it was
asked at beside its choice. A choice from an older count is not used: the
next print to a PostScript printer through the dialog asks again, and the
answer is kept with the new count. A run's own choice (the row) is kept.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                        # noqa: E402

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from workflow import ppd_color                            # noqa: E402

from tests.test_435b2_postscript_asked_after_the_dialog import (  # noqa: E402
    _answer, _env, _fake_print_frames, _tab, approved, mac, qapp)  # noqa: F401

DEVICE, MACOS = ppd_color.POSTSCRIPT_DEVICE_RGB, ppd_color.POSTSCRIPT_AS_MACOS


def _settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def test_only_a_real_switch_is_counted(tmp_path):
    """Preferences writes every key on OK, changed or not. MUTATION: count
    every write and an unrelated OK would re-ask every project."""
    s = _settings(tmp_path)
    s.set("use_native_print_dialog", True)
    base = s.get("print_dialog_setting_changes")
    s.set("use_native_print_dialog", True)
    assert s.get("print_dialog_setting_changes") == base
    s.set("use_native_print_dialog", False)
    assert s.get("print_dialog_setting_changes") == base + 1
    s.set("use_native_print_dialog", False)
    assert s.get("print_dialog_setting_changes") == base + 1
    s.set("use_native_print_dialog", True)
    assert s.get("print_dialog_setting_changes") == base + 2
    assert s.get("use_native_print_dialog") is True


def test_a_switch_asks_the_project_again(qapp, tmp_path, mac, approved, monkeypatch):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    # first print through the dialog: asked, the project keeps the answer
    seen = _answer(monkeypatch, mac, 1)
    sent = _fake_print_frames(monkeypatch, postscript=True)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [MACOS] and len(seen) == 1
    # the second print is not asked
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent == [MACOS, MACOS] and len(seen) == 1
    # off and on again in Preferences: two switches, the choice is stale
    s.set("use_native_print_dialog", False)
    s.set("use_native_print_dialog", True)
    assert tab._ps_form_stored() is None
    assert tab._ps_form_for_dialog() is None          # asked after the dialog
    # the stored choice itself is kept on disk until the new answer
    assert Project.load(tmp_path / "P").print_setting("postscript") == MACOS
    seen2 = _answer(monkeypatch, mac, 0)
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent[-1] == DEVICE and len(seen2) == 1
    proj = Project.load(tmp_path / "P")
    assert proj.print_setting("postscript") == DEVICE
    assert proj.print_setting("postscript_dialog_changes") == \
        s.get("print_dialog_setting_changes")
    # and then it is used without asking again
    tab._print_native([(tmp_path / "p.tif", 0)])
    assert sent[-1] == DEVICE and len(seen2) == 1


def test_the_same_answer_after_a_switch_is_kept_with_the_new_count(
        qapp, tmp_path, mac, approved, monkeypatch):
    """MUTATION: store the count only when the form changes and the same
    answer is asked again at every print."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab._store_ps_project_form(MACOS)
    s.set("use_native_print_dialog", False)
    s.set("use_native_print_dialog", True)
    assert tab._ps_form_stored() is None
    tab._store_ps_project_form(MACOS)
    assert tab._ps_form_stored() == MACOS


def test_a_project_from_before_the_rule_keeps_its_choice(qapp, tmp_path, mac, approved):
    """A choice stored by beta 2 or 3 has no count, and the setting was never
    switched since (count 0): it stays valid."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    s._qs.setValue("print_dialog_setting_changes", 0)
    tab._ps_project().set_print_setting("postscript", MACOS)
    assert tab._ps_form_stored() == MACOS


def test_a_runs_own_choice_is_kept(qapp, tmp_path, mac, approved):
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    tab._store_ps_project_form(MACOS)
    assert tab._store_ps_form(DEVICE)
    s.set("use_native_print_dialog", False)
    s.set("use_native_print_dialog", True)
    assert tab._ps_project_form() is None
    assert tab._ps_form_stored() == DEVICE


def test_switched_off_the_direct_route_still_sees_the_projects_choice(
        qapp, tmp_path, mac, approved):
    """Combined review of beta 4: switching the dialog OFF must not discard
    the project's choice on the direct route, where the question before
    printing a "let the printer adjust" project as unchanged colours
    (M-PRINT-DIRECT-LIKE-PREVIEW, P14) reads it. Switched on again, the
    project is asked again as Knut ruled. MUTATION: drop the route check in
    ``_ps_project_form`` and the first assertion goes red."""
    s, fm, ctl = _env(tmp_path)
    tab = _tab(s, ctl)
    s.set("use_native_print_dialog", True)
    tab._store_ps_project_form(MACOS)
    s.set("use_native_print_dialog", False)
    assert tab._ps_form_stored() == MACOS
    s.set("use_native_print_dialog", True)
    assert tab._ps_form_stored() is None
