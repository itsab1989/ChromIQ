"""Shortcut text must name the key the user's own keyboard has.

Knut, 4.1.3-beta.15: *"Make sure tool tip text is specific to the platform used,
so that correct symbol or key is shown."* Most of ChromIQ already does this —
`keys_for()` renders through `QKeySequence.toString(NativeText)`, which gives
⌘⇧O on macOS and Ctrl+Shift+O elsewhere. What did not were the hand-written
rows, which had ⏎ and ⇧ baked into the source string, and the scan-alignment
hint, which showed everyone "⌘/Ctrl" — a key a Windows user does not have next
to one a Mac user does not need.
"""
from __future__ import annotations

import re

import pytest

from ui import keyboard_help


#: Glyphs that only exist on an Apple keyboard.
MAC_ONLY = "⌘⌥⇧⏎⌃"


def test_no_mac_glyph_is_baked_into_a_hand_written_row(monkeypatch):
    """On a non-Mac, nothing in the card may show a Mac-only symbol."""
    monkeypatch.setattr(keyboard_help, "_IS_MAC", False)
    rows = keyboard_help._measurement_keys()
    for keys, _what, _who in rows:
        assert not any(g in keys for g in MAC_ONLY), (
            f"{keys!r} shows a Mac-only symbol on a non-Mac platform")


def test_the_mac_still_gets_its_symbols(monkeypatch):
    """The control: this must not have flattened everyone to words."""
    monkeypatch.setattr(keyboard_help, "_IS_MAC", True)
    joined = " ".join(k for k, _w, _o in keyboard_help._measurement_keys())
    assert "⏎" in joined and "⇧" in joined, (
        "the Mac lost its native symbols — the fix went too far")


def test_shift_and_enter_differ_by_platform(monkeypatch):
    monkeypatch.setattr(keyboard_help, "_IS_MAC", True)
    mac = (keyboard_help._shift(), keyboard_help._enter())
    monkeypatch.setattr(keyboard_help, "_IS_MAC", False)
    other = (keyboard_help._shift(), keyboard_help._enter())
    assert mac == ("⇧", "⏎")
    assert other != mac and not any(g in "".join(other) for g in MAC_ONLY)


def test_the_shortcut_hint_is_not_appended_twice():
    """`attach_shortcut_hint` reads its own output back, so it must be idempotent.

    Without the check a second call — a re-styled tab, a rebuilt row — gives
    "Generate Chart (⌘↵) (⌘↵)".
    """
    class _W:
        def __init__(self) -> None:
            self._tip = ""
        def toolTip(self) -> str:
            return self._tip
        def setToolTip(self, t: str) -> None:
            self._tip = t
        def text(self) -> str:
            return "Generate Chart"

    action = next(a for a in keyboard_help.BINDINGS if keyboard_help.keys_for(a))
    w = _W()
    keyboard_help.attach_shortcut_hint(w, action)
    once = w.toolTip()
    keyboard_help.attach_shortcut_hint(w, action)
    assert w.toolTip() == once, f"the hint was appended twice: {w.toolTip()!r}"
    assert once.count(keyboard_help.keys_for(action)) == 1
