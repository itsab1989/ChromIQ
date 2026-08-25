"""Every Welcome-window help card must actually draw an icon.

`WorkflowIcon.paintEvent` (`ui/dialogs/welcome_dialog.py:1486`) is one long
`if self._key == … elif …` chain with **no final else**. A card whose key has no
branch therefore paints nothing at all and ships as a blank 96x96 square — no
warning, no placeholder, nothing in the log. That is exactly what happened to
the three cards added in 4.1.3-beta.15: "Design a custom patch set for a chart",
"Spot-read the colour of a surface" and "Show or compare a chart's patch set in
3D" all rendered empty, and it reached a tester (Knut, beta.15), who read it as
"the icons do not match the style" rather than "there are no icons".

The test renders every card's icon for real and asserts that something was
painted, so the next card added cannot repeat it.
"""
from __future__ import annotations

import pytest
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication

from ui.dialogs.welcome_dialog import WORKFLOWS, WorkflowIcon


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _render(key: str, mode: str) -> QImage:
    icon = WorkflowIcon(key)
    icon.set_appearance(mode)
    img = QImage(WorkflowIcon.SIZE, WorkflowIcon.SIZE,
                 QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    icon.render(painter)
    painter.end()
    return img


#: A key that provably has no branch in the if/elif chain. Rendering it is what
#: "no icon" actually looks like — which is NOT an empty image: `render()` fills
#: the widget's background, so every pixel comes back opaque and counting
#: non-transparent pixels reports a full 96x96 canvas for a blank icon. The only
#: honest test is to compare against this baseline.
_NO_SUCH_KEY = "__no_branch_exists_for_this_key__"


def _differs_from_blank(key: str, mode: str) -> int:
    """How many pixels this icon has that an unmapped key does not."""
    drawn, blank = _render(key, mode), _render(_NO_SUCH_KEY, mode)
    return sum(1 for y in range(drawn.height()) for x in range(drawn.width())
               if drawn.pixelColor(x, y) != blank.pixelColor(x, y))


def test_the_blank_baseline_really_is_blank(app):
    """Positive control: prove the comparison can see a missing icon.

    Without this, the test below would pass for a card that draws nothing —
    which is how the first version of this file was green while three cards
    shipped as empty squares.
    """
    assert _differs_from_blank(_NO_SUCH_KEY, "dark") == 0
    assert _differs_from_blank("first_profile", "dark") > 200, (
        "a known-good icon is indistinguishable from a blank one — the "
        "comparison is broken, not the icon")


@pytest.mark.parametrize("card", WORKFLOWS, ids=lambda c: c["key"])
def test_the_card_draws_something(app, card):
    """A card with no icon branch paints an empty square — catch it here."""
    painted = _differs_from_blank(card["key"], "dark")
    assert painted > 200, (
        f"the {card['key']!r} help card drew {painted} pixels more than a key "
        f"with no icon at all — it has no branch in WorkflowIcon.paintEvent "
        f"and ships as a blank square")


def test_the_icon_follows_the_theme(app):
    """The icons are painted, not image files, so both themes must draw."""
    for card in WORKFLOWS:
        for mode in ("dark", "light"):
            assert _differs_from_blank(card["key"], mode) > 200, (
                f"{card['key']!r} draws nothing in {mode} mode")
