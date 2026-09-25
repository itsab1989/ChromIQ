"""The gear window says what the paper filter does, and has help for it
(#182 K42-3, Knut 5832746557 and 5833232475; register B8-1144, B8-1145).

Knut, 5833232475: *"This feature only apply build-in presets, and the settings
window should say so. There should be a help icon for the feature inside the
built-in presets window, explaining the details of how this feature works.
There should also be a help icon for the "Filter preset-dropdown list
according to selected paper size" checkbox (on its right side as usual)"*, and
the window's own list *"is not affected by the checkbox"*.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

OWN = ("Your own presets are not affected: neither the ticks nor the paper "
       "filter below changes them, and they always stay at the top. OK keeps "
       "your choice; Close leaves the lists as they were.")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _dialog(paper_filter=True):
    from ui.dialogs.builtin_presets_shown_dialog import \
        BuiltinPresetsShownDialog
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS
    groups = [(h, [(k, "", k) for (_c, _o, k) in e])
              for h, e in BUILTIN_PRESET_GROUPS]
    return BuiltinPresetsShownDialog(groups, set(),
                                     paper_filter=paper_filter), groups


def test_the_window_says_own_presets_are_unaffected_by_ticks_and_filter(qapp):
    dlg, _g = _dialog()
    try:
        assert OWN in dlg._intro.text()
    finally:
        dlg.deleteLater()


def test_a_help_icon_for_the_window_and_one_right_of_the_box(qapp):
    """MUTATION: drop either icon (red); put the box's icon on its left
    (red)."""
    from ui.tooltip_button import TooltipButton
    dlg, _g = _dialog()
    try:
        dlg.show()
        qapp.processEvents()
        win = dlg._help
        box = dlg._paper_filter_help
        assert isinstance(win, TooltipButton) and win.isVisible()
        assert isinstance(box, TooltipButton) and box.isVisible()
        body = win.dialog_body()
        for words in ("▸ N more presets", "OK keeps", "Export list",
                      "Import list", "Paper filter", "Your own presets"):
            assert words in body, words
        b = box.dialog_body()
        for words in ("built-in presets only", "Your own presets are never "
                      "filtered", "“Select preset” and the Built-in presets "
                      "list", "Guided", "Manual", "Scanner", "Custom",
                      "orientation counts", "“▸ N more presets”",
                      "this window's list"):
            assert words in b, words
        cb = dlg._paper_filter
        assert box.geometry().left() >= cb.geometry().right()
        assert abs(box.geometry().center().y()
                   - cb.geometry().center().y()) <= 4
    finally:
        dlg.close()
        dlg.deleteLater()


@pytest.mark.parametrize("on", [True, False])
def test_the_box_does_not_change_the_windows_own_list(qapp, on):
    """Knut, 5833232475: the window *"always show the prests existing, and
    those selected to show directly"*. Every built-in, whatever the box, and
    ticking the box on screen hides nothing in the window."""
    dlg, groups = _dialog(paper_filter=on)
    try:
        dlg.show()
        qapp.processEvents()

        def listed():
            out = []
            for i in range(dlg._tree.topLevelItemCount()):
                g = dlg._tree.topLevelItem(i)
                for j in range(g.childCount()):
                    c = g.child(j)
                    if not c.isHidden():
                        out.append(c.text(0))
            return out
        every = [k for _h, e in groups for (k, _t, _k) in e]
        assert listed() == every
        dlg._paper_filter.setChecked(not on)
        qapp.processEvents()
        assert listed() == every
    finally:
        dlg.close()
        dlg.deleteLater()


def test_the_german_is_translated_by_hand_in_du_form():
    root = Path(__file__).resolve().parent.parent / "data" / "i18n"
    de = json.loads((root / "de.json").read_text(encoding="utf-8"))
    t = de[OWN]
    assert t.startswith("Deine eigenen Presets sind nicht betroffen")
    assert "Papierfilter" in t
    keys = [k for k in de if k.startswith(("This window chooses which "
                                           "built-in presets",
                                           "While this box is ticked"))]
    assert len(keys) == 2
    for k in keys + [OWN, "How the built-in preset lists work",
                     "The paper filter"]:
        v = de[k]
        assert v != k, k[:40]
        assert " Sie " not in v and "Ihre " not in v, k[:40]
        assert "—" not in v and "—" not in k, k[:40]
