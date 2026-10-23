"""The rename window says "project" where it means the project (agent 23,
4.3.10 review; agent 22 left it open).

The window comes up when a project is given a new name in Create Chart. Its
title had already become "You have given this project a new name", but the
heading, the introduction and every choice under it still spoke of a
"profile": "You already created the profile ...", "Each profile is a separate
folder", "Rename the existing profile", "two separate profiles on disk". The
folder is a PROJECT (`core/file_manager.Project`), and the printer profile is
one of the files in it, which the Delete choice rightly calls "profiles".
"""
from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from ui.dialogs import target_change_dialog as TCD              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _dialog():
    return TCD.TargetChangeDialog("gen-a", "gen-b", Path("/u/gen-a"),
                                  Path("/u/gen-b"))


def test_nothing_in_the_window_calls_the_project_a_profile(qapp):
    """MUTATION, proven red: the heading back to "the profile"."""
    dlg = _dialog()
    try:
        texts = [w.text() for w in dlg.findChildren(QLabel)
                 + dlg.findChildren(QPushButton)]
        joined = "\n".join(texts)
        # the printer profiles in the folder are files, and are named so
        assert "(charts, measurements, profiles)" in joined
        rest = joined.replace("(charts, measurements, profiles)", "")
        assert "profile" not in rest.lower(), [
            t for t in texts if "profile" in t.lower()]
        assert 'You already created the project "gen-a"' in joined
        assert 'Rename the existing project to "gen-b"' in joined
        assert "—" not in joined
    finally:
        dlg.close()


@pytest.mark.parametrize("code", ["de", "es", "fr", "it", "ja", "nl", "no",
                                  "pl", "pt", "ru", "sv", "uk", "zh_CN"])
def test_every_language_has_the_new_words(code):
    """Each of the six texts is translated, with no em dash, and none of them
    is the old "profile" one."""
    data = json.loads((ROOT / "data" / "i18n" / f"{code}.json")
                      .read_text(encoding="utf-8"))
    src = inspect.getsource(TCD)
    keys = [k for k in data if k.startswith((
        'You already created the project "{old_name}"',
        "Each project is a separate folder on disk.",
        'Rename the existing project to "{new}"',
        "Recommended when you deliberately intended to change the project",
        "This is the safest choice: nothing is deleted. ChromIQ creates a "
        "brand-new project",
        'ChromIQ creates the new "{new}" project and moves'))]
    assert len(keys) == 6, keys
    for k in keys:
        assert data[k] and "—" not in data[k], (code, k)
    assert not [k for k in data if "the profile \"{old_name}\"" in k
                or k.startswith("Each profile is a separate folder")]
    assert "Each profile is a separate folder" not in src


def test_each_choice_answers_with_its_own_action(qapp):
    """The choices are wired by a bound method now, not a lambda capturing
    the window (CLAUDE.md, the fade_scroll crash class).

    MUTATION, proven red: `_on_option_clicked` choosing KEEP for every
    button."""
    want = {'Rename the existing project to "gen-b"': TCD.TargetChangeAction.RENAME,
            'Create "gen-b" and keep "gen-a"': TCD.TargetChangeAction.KEEP,
            'Create "gen-b" and delete "gen-a"': TCD.TargetChangeAction.DELETE}
    for text, action in want.items():
        dlg = _dialog()
        try:
            btn = next(b for b in dlg.findChildren(QPushButton)
                       if b.text() == text)
            btn.click()
            assert dlg.result_action() is action, text
        finally:
            dlg.close()
    assert "connect(lambda" not in inspect.getsource(TCD)
