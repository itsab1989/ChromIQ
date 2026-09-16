"""A Size box that is inert must not show a number, and no preset may set one.

A tester, beta 18: *"under the Clip-border content frame with selected Notes box
has the Size input box locked with 12 pt inside the input box. Is it locked
because it has its own shrinking feature? If so, should it not show auto? if
this comes from the json files of the presets and this is wrong, then correct
this on all the preset files, if they have anything else than size=auto while
also having content = Notes box."*

It is locked for exactly that reason: the notes box lays itself out and
`layout_options_panel._sync_clip_content_enabled` disables the Size box for
every content mode but free text. The 12 pt came from the preset data: `_P3_BASE`
carried `clip_text_size_mm: 4.23`, which is 12.0 pt, on all 24 charts of that
family, and two more preset bases carried 3.53 mm beside "Notes box".

A greyed number is a promise the sheet does not keep. Both halves are fixed:
the data says auto, and the box shows auto whenever its content sizes itself.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

_SRC = Path(__file__).resolve().parents[1] / "ui" / "tabs" / "tab_chart.py"


def test_no_preset_pairs_a_notes_box_with_a_typed_size():
    """Every recipe literal in the tab, read as text so a new family cannot
    slip past by not being imported here.

    MUTATION: put `4.23` back on `_P3_BASE` and this goes red.
    """
    src = _SRC.read_text(encoding="utf-8")
    bad = []
    for m in re.finditer(r'["\']clip_content_mode["\']\s*:\s*["\'](\w+)["\']',
                         src):
        if m.group(1) != "notes":
            continue
        line = src[:m.start()].count("\n") + 1
        tail = src[m.end():m.end() + 1200]
        size = re.search(r'["\']clip_text_size_mm["\']\s*:\s*([0-9.]+)', tail)
        if size and float(size.group(1)) > 0:
            bad.append(f"line {line}: notes box with "
                       f"clip_text_size_mm {size.group(1)}")
    assert not bad, (
        "a built-in preset pairs the Notes box with a typed Size, which the "
        "panel then shows greyed out and the sheet never uses:\n  "
        + "\n  ".join(bad))


def test_the_shipped_i1pro3_family_really_carries_auto():
    """The family a tester named, asked of the data rather than of the text."""
    from ui.tabs.tab_chart import _P3_BASE
    assert _P3_BASE["clip_content_mode"] == "notes"
    assert _P3_BASE["clip_text_size_mm"] == 0.0, (
        f"the 24 i1Pro 3 charts still carry "
        f"{_P3_BASE['clip_text_size_mm']} mm of clip text size")


def test_the_size_box_reads_auto_whenever_its_content_sizes_itself(qtbot=None):
    """The widget, driven: pick "Notes box" and the box must read its special
    "auto" value, and picking free text again must give the typed size back.

    MUTATION: delete the stash/restore block and the second half goes red.
    """
    from PyQt6.QtWidgets import QApplication
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    _app = QApplication.instance() or QApplication([])
    p = LayoutOptionsPanel()
    p.clip_content_mode.setCurrentIndex(
        p.clip_content_mode.findData("text"))
    p.clip_text_size.setValue(12.0)
    p._sync_clip_content_enabled()
    assert p.clip_text_size.isEnabled()
    p.clip_content_mode.setCurrentIndex(
        p.clip_content_mode.findData("notes"))
    p._sync_clip_content_enabled()
    assert not p.clip_text_size.isEnabled()
    assert p.clip_text_size.value() == 0.0, (
        f"the inert Size box still shows {p.clip_text_size.value()} pt")
    assert p.clip_text_size.specialValueText(), (
        "the box has no special value text, so 0 would read as '0 pt'")
    p.clip_content_mode.setCurrentIndex(
        p.clip_content_mode.findData("text"))
    p._sync_clip_content_enabled()
    assert p.clip_text_size.value() == 12.0, (
        "the typed size was lost when the content mode came back")
