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

    The badge became **per appearance** when Neutral arrived (a near-black slab
    is a dark-theme value, and Neutral's answer is an ``ACTION`` fill with
    ``ON_ACTION`` on it — the one sanctioned light-on-dark pairing). What is
    asserted is therefore the property, not one literal: the badge names a
    background of its own in *every* appearance, that background is opaque
    enough to stand on any chart, and its label reads on it. Light and Dark
    still name the exact slab they always did.
    """
    from ui.tiff_preview import (_PREVIEW_BY_MODE, _PREVIEW_DARK,
                                 _PREVIEW_LIGHT)

    slab = "rgba(30, 30, 30, 185)"
    assert _PREVIEW_LIGHT["badge_bg"] == slab
    assert _PREVIEW_LIGHT["badge_text"] == "#f4f2ef"
    assert _PREVIEW_DARK["badge_bg"] == slab
    assert _PREVIEW_DARK["badge_text"] == "#f4f2ef"

    for mode, pal in _PREVIEW_BY_MODE.items():
        bg = pal["badge_bg"]
        assert bg and bg != "transparent", (
            f"{mode}: the floating badge lost its own background; over an "
            "arbitrary chart image the palette's colours guarantee nothing"
        )
        if bg.startswith("rgba("):
            alpha = int(bg[bg.index("(") + 1:bg.index(")")].split(",")[3])
            assert alpha >= 150, f"{mode}: the badge slab is too transparent"
        assert _contrast(pal["badge_text"], _opaque(bg)) >= 7.0, (
            f"{mode}: the badge's own label does not read on its own slab"
        )


def _opaque(value: str) -> str:
    """A colour spec as its opaque hex — the slab's own colour, alpha aside."""
    if value.startswith("rgba(") or value.startswith("rgb("):
        r, g, b = (int(float(x)) for x in
                   value[value.index("(") + 1:value.index(")")].split(",")[:3])
        return f"#{r:02x}{g:02x}{b:02x}"
    return value


def _contrast(a: str, b: str) -> float:
    def lum(hexc: str) -> float:
        h = hexc.lstrip("#")
        parts = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
               for c in parts]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    la, lb = lum(a), lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


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
