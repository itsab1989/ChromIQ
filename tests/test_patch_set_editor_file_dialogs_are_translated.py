"""The patch set editor's file dialogs speak the user's language.

Its "Load chart" dialog (and the colour, image, profile and export dialogs
beside it) handed ``open_file_dialog`` / ``save_file_dialog`` a bare English
title and file-type filter, so a German user read "Load chart" and
"All files (*)" in an otherwise German window. The general sweep in
``scripts/i18n_extract.py`` looks at ``QFileDialog`` calls only, and the
editor goes through the ``ui.widgets`` helpers, so nothing caught it.
"""
from __future__ import annotations

import ast
from pathlib import Path

EDITOR = (Path(__file__).resolve().parent.parent
          / "ui" / "dialogs" / "ti2_relayout_dialog.py")
HELPERS = {"open_file_dialog": ("title", "name_filter"),
           "save_file_dialog": ("title", "name_filter"),
           "open_dir_dialog": ("title",)}


def _is_tr(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "tr")


def _calls():
    tree = ast.parse(EDITOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in HELPERS):
            yield node


def test_the_editor_has_file_dialogs_to_check():
    assert sum(1 for _ in _calls()) >= 7


def test_every_file_dialog_title_and_filter_goes_through_tr():
    bad = []
    for call in _calls():
        names = HELPERS[call.func.id]
        given = dict(zip(names, call.args[1:]))
        given.update({k.arg: k.value for k in call.keywords if k.arg in names})
        for name, value in given.items():
            if isinstance(value, ast.Constant) and value.value == "":
                continue
            if not _is_tr(value):
                bad.append((call.lineno, call.func.id, name))
    assert not bad, f"untranslated file dialog text in the editor: {bad}"
