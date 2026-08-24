"""The Profile-run bar's labels sit on the masthead's version rail (#164).

THE RAIL PAINTS ITSELF; A WIDGET SITTING ON IT DOES NOT. The bar's labels are
ordinary `QLabel`s with no background of their own, so they were drawn in the
application palette's near-black on a #070707 rail — measured **1.11:1** for
"Profile run:" and "Run type:", and **1.55:1** for the first-run hint, which is
the one sentence telling a brand-new user what to do. All three were invisible.

Two traps this file exists to hold shut:

* `QLabel.grab()` paints the label's OWN background, so a grabbed label looks
  perfectly legible in isolation while being invisible in the window. The bug
  is only visible in the composited window.
* `set_appearance` returns early when the mode has not changed, so colouring
  the labels only from there leaves the first widget ever hosted uncoloured.
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from ui.masthead_header import _PALETTE_DARK, _PALETTE_LIGHT  # noqa: E402

#: WCAG 2.1 AA, normal-size text.
AA = 4.5


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("name,pal", [("dark", _PALETTE_DARK),
                                      ("light", _PALETTE_LIGHT)])
def test_the_first_run_sentence_is_readable(name, pal):
    """It is instruction, not decoration — it has to reach AA."""
    r = contrast(pal["rail_hint_fg"], pal["ver_bg"])
    assert r >= AA, (
        f"{name}: the first-run hint is {r:.2f}:1 against the rail, "
        f"below WCAG AA's {AA}:1")


@pytest.mark.parametrize("name,pal", [("dark", _PALETTE_DARK),
                                      ("light", _PALETTE_LIGHT)])
def test_the_bar_labels_are_not_invisible(name, pal):
    """"Profile run:" / "Run type:" follow the rail's own version text, which
    is 3.7–3.8:1 — short labels, and the masthead's established typography.
    The bar is what must not go back to 1.11:1."""
    r = contrast(pal["ver_fg"], pal["ver_bg"])
    assert r >= 3.0, (
        f"{name}: the bar's labels are {r:.2f}:1 against the rail")


def test_the_labels_are_coloured_for_the_rail_not_the_app_palette(qapp):
    """Both object names must be given a colour, and it must happen when the
    widget is hosted — not only when the theme later changes."""
    import inspect

    from ui import masthead_header

    src = inspect.getsource(masthead_header.MastheadHeader)
    for name in ("target_bar_label", "target_bar_hint"):
        assert name in src, f"{name} is never given a colour for the rail"
    hosted = inspect.getsource(masthead_header.MastheadHeader.set_center_widget)
    assert "_paint_center_widget_text" in hosted, (
        "the first widget hosted on the rail keeps the application palette")
