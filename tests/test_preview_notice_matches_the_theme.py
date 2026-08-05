"""#130 — the "No chart for this profile run yet" notice follows the theme.

Basti, beta.143: *"the 'no chart for this profile run yet' info box under the
tiff preview has a dark grey background. in darkmode it is a little brighter
than its surrounding and in lightmode it's… well… also grey instead of
matching."*

It was styled as a **badge** — ``rgba(30, 30, 30, 185)`` with ``#f4f2ef`` text —
which is right for something floating OVER the image, and wrong for this, which
sits below the preview in the panel. A fixed slab cannot match two themes.
"""
from __future__ import annotations

import re

import pytest


def _notice_style() -> str:
    import inspect

    from ui.tiff_preview import TiffPreview

    src = inspect.getsource(TiffPreview)
    i = src.index("_notice_lbl.setStyleSheet")
    return src[i:i + 400]


def test_the_notice_sets_no_colour_of_its_own():
    """No background and no text colour: the palette decides, so it matches
    whichever theme is on — and keeps matching when the theme is switched."""
    style = _notice_style()
    assert "background: transparent" in style
    assert "color:" not in style, (
        "the notice pins a text colour; it must take the theme's"
    )
    assert not re.search(r"rgba?\(", style), (
        "the notice pins a background colour; it must take the theme's"
    )


def test_the_floating_badge_keeps_its_own_colours():
    """…and the badge that really does float over the image keeps its slab.

    Its contrast cannot come from the palette, because what is behind it is the
    user's chart — any colour at all. This is the boundary between the two, and
    the reason only one of them changed.
    """
    import inspect

    from ui.tiff_preview import TiffPreview

    src = inspect.getsource(TiffPreview)
    i = src.index("_badge_lbl = QLabel(self)")
    assert "rgba(30, 30, 30" in src[i:i + 400], (
        "the floating badge lost its own background; over an arbitrary chart "
        "image the palette's colours guarantee nothing"
    )


# A third test tried to prove the colour CHANGES with the theme. Two ways were
# tried and both were wrong for the same reason — they asked Qt a question it
# does not answer:
#
#   * applying an appearance to the application sets the app-wide stylesheet,
#     which re-polishes every widget the suite has alive. CLAUDE.md forbids it
#     in tests, and it segfaulted a gate worker at 97%.
#   * setting a palette on the parent does not show up in the child's resolved
#     palette, so the assertion compared a colour with itself.
#
# The mechanism is entirely "the stylesheet names no colour", which
# test_the_notice_sets_no_colour_of_its_own asserts and which fails when the
# fixed slab is put back. The appearance itself was checked by rendering the
# widget in both themes and looking at it — the only way that question is
# honestly answered.
