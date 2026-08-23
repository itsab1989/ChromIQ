"""A disabled text box must LOOK disabled — in both themes (#164).

Knut, 2026-08-23, on the clip-border content: *"When I change to Notes box …
the text field is ignored (whatever is in it), thus the text input field should
rather be disabled when in this Content option."*

It already was disabled. Two screenshots of the same box — Custom text (live)
and Notes box (dead) — came out pixel for pixel identical, because
``QPlainTextEdit`` was missing from both themes' disabled-input rule while
``QWidget { color: … }`` painted its text at full brightness. A style sheet beats
the palette, so the palette's Disabled/Text entry never got a look in. It is the
same trap the radio buttons hit, written up at ui/styles.py.

The fix is two CSS selectors and one greyed label, and nothing guarded it — this
file does. It measures ink, not stylesheets: a rule can be present and still not
reach the widget.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _mean_text_ink(widget) -> float:
    """How dark the widget's own text is against its background, 0-255.

    Measured off the real grab, so a rule that exists but does not apply fails
    here exactly as it would on screen.
    """
    import numpy as np
    img = widget.grab().toImage()
    w, h = img.width(), img.height()
    buf = img.constBits()
    buf.setsize(img.sizeInBytes())
    arr = np.array(np.frombuffer(buf, np.uint8).reshape(
        h, img.bytesPerLine() // 4, 4)[:, :w, :3], dtype=int)
    grey = arr.mean(axis=2)
    return float(grey.max() - grey.min())      # contrast between text and field


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_a_disabled_text_box_is_visibly_dimmer(qapp, theme):
    from PyQt6.QtWidgets import QPlainTextEdit, QWidget

    if theme == "dark":
        from ui.styles import APP_STYLESHEET as sheet
    else:
        from ui.light_styles import LIGHT_STYLESHEET as sheet
    host = QWidget()
    host.setStyleSheet(sheet)
    box = QPlainTextEdit(host)
    box.setPlainText("Knut Larsson\nEpson P900")
    box.resize(320, 90)
    box.show()

    box.setEnabled(True)
    live = _mean_text_ink(box)
    box.setEnabled(False)
    dead = _mean_text_ink(box)
    assert dead < live * 0.75, (
        f"[{theme}] a disabled text box looks the same as a live one "
        f"(contrast {live:.0f} → {dead:.0f})")


def test_the_notes_mode_greys_the_field_and_its_label(qapp):
    """The label has to go with the field: a live-looking "Text:" over a dead
    box is half the same confusion."""
    from PyQt6.QtWidgets import QLabel

    from ui.dialogs.layout_options_panel import LayoutOptionsPanel

    p = LayoutOptionsPanel(with_selectors=True)
    p._expert_frame.set_collapsed(False)
    p.instr.setCurrentIndex(p.instr.findData("i1"))
    p.mode.setCurrentIndex(p.mode.findData("clip"))

    labels = [w for w in (p._clip_text_row or []) if isinstance(w, QLabel)]
    assert labels, "the Text row has no label to grey"

    p.clip_content_mode.setCurrentIndex(p.clip_content_mode.findData("notes"))
    assert not p.clip_text.isEnabled()
    assert all(not lb.isEnabled() for lb in labels), (
        "the Text label stayed live over a dead box")
    assert all(lb.objectName() == "param_label" for lb in labels), (
        "the label has no object name the themes style for :disabled")

    p.clip_content_mode.setCurrentIndex(p.clip_content_mode.findData("text"))
    assert p.clip_text.isEnabled()
    assert all(lb.isEnabled() for lb in labels)

    # …and in branding mode the field is LIVE, which is the other half of what
    # confused him: he could not tell that his lines were being used.
    p.clip_content_mode.setCurrentIndex(p.clip_content_mode.findData("branding"))
    assert p.clip_text.isEnabled()
    assert all(lb.isEnabled() for lb in labels)


@pytest.mark.parametrize("sheet_name", ["styles", "light_styles"])
def test_both_themes_carry_the_rule(sheet_name):
    """Cheap belt-and-braces: the selector must exist in both sheets, so a
    theme added later cannot quietly drop it."""
    import importlib

    mod = importlib.import_module(f"ui.{sheet_name}")
    sheet = getattr(mod, "APP_STYLESHEET", None) or mod.LIGHT_STYLESHEET
    assert "QPlainTextEdit:disabled" in sheet
    assert "QTextEdit:disabled" in sheet
