"""ChromIQ draws its own warning sign, and it is right in all three appearances.

Basti, 2026-09-03, on the two new windows in Tools ▸ Read single patches:
*"could you create one in our regular style for all colorschemes — light dark
neutral?"*

`QMessageBox.Icon.Warning` is the platform's sign: on macOS the system caution
triangle with the app badged into it, in a hue Neutral exists to remove. These
pin the replacement — that it is drawn at all, that Neutral gets no hue, and
that the mark is actually visible against the sign rather than merely specified.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox           # noqa: E402

from ui import neutral_styles                                   # noqa: E402
from ui.styles import ACCENT_WARN                               # noqa: E402
from ui.warning_sign import (set_warning_icon, warning_colours,  # noqa: E402
                             warning_pixmap)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_light_and_dark_wear_the_apps_own_amber():
    for mode in ("light", "dark"):
        fill, mark = warning_colours(mode)
        assert fill == ACCENT_WARN, mode
        assert QColor(mark).lightness() < 60, \
            f"{mode}: the mark must read against the amber it sits on"


def test_neutral_carries_no_hue_at_all(qapp):
    """Neutral says 'warning' with the shape and the words. Rule 1."""
    fill, mark = warning_colours("neutral")
    assert fill == neutral_styles.NM_ACTION
    assert mark == neutral_styles.NM_ON_ACTION
    assert QColor(fill).saturation() == 0 and QColor(mark).saturation() == 0
    assert fill != ACCENT_WARN


def test_the_sign_is_actually_drawn(qapp):
    """A pixmap that is merely transparent is a warning nobody sees."""
    for mode in ("light", "dark", "neutral"):
        img = warning_pixmap(48, mode, 1.0).toImage()
        assert img.width() == 48 and img.height() == 48, mode
        opaque = sum(1 for y in range(48) for x in range(48)
                     if img.pixelColor(x, y).alpha() > 200)
        assert opaque > 48 * 48 * 0.2, f"{mode}: almost nothing was painted"
        # the corners stay transparent: it is a triangle, not a square
        assert img.pixelColor(1, 1).alpha() < 40, mode


def test_both_the_sign_and_its_mark_reach_the_pixels(qapp):
    """The mark is a hole in the sign; specifying it is not drawing it."""
    for mode in ("light", "dark", "neutral"):
        fill, mark = warning_colours(mode)
        img = warning_pixmap(64, mode, 1.0).toImage()
        seen = {img.pixelColor(x, y).name()
                for y in range(64) for x in range(64)
                if img.pixelColor(x, y).alpha() > 240}
        assert QColor(fill).name() in seen, f"{mode}: the sign was not painted"
        assert QColor(mark).name() in seen, f"{mode}: the mark was not painted"


def test_it_is_drawn_for_the_screen_it_lands_on(qapp):
    px = warning_pixmap(48, "dark", 2.0)
    assert px.devicePixelRatio() == 2.0
    assert px.width() == 96, "a 2x sign scaled up from 1x looks like a mistake"


def test_the_message_box_gets_ours_and_not_the_platforms(qapp):
    box = QMessageBox()
    set_warning_icon(box, "light")
    assert box.icon() == QMessageBox.Icon.NoIcon, \
        "setIconPixmap must REPLACE the standard triangle, not sit beside it"
    assert not box.iconPixmap().isNull()


def test_an_unknown_appearance_lands_on_dark(qapp):
    """Pinned as it BEHAVES, not as it is described.

    `theme.by_mode`'s own docstring says "every caller fails loudly rather than
    silently inheriting somebody else's value" — and its last line is
    `.get(mode or active_mode(), dark)`, which does the opposite. That gap is
    older than this file and belongs to whoever owns `ui/theme.py`; recording
    it here means a future change to `by_mode` shows up as a failure with the
    reason attached, instead of silently changing what this sign draws.
    """
    assert warning_colours("sepia") == warning_colours("dark")


def test_the_two_new_windows_use_it():
    import inspect

    from ui.dialogs.spot_read_dialog import SpotReadDialog
    for method in (SpotReadDialog._confirm_clear, SpotReadDialog._may_close):
        src = inspect.getsource(method)
        assert "set_warning_icon(box)" in src, method.__name__
        assert "QMessageBox.Icon.Warning" not in src, method.__name__
