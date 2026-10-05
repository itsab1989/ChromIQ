"""The ONE way ChromIQ opens a font for Pillow: always with the BASIC layout.

Pillow lays text out with one of two engines, and which one it picks by default
depends on the MACHINE, not on ChromIQ. Its wheels carry libraqm but load
FriBiDi at run time, so:

* where a FriBiDi library can be found (Basti's Mac has Homebrew's
  ``/opt/homebrew/lib/libfribidi.dylib``), Pillow uses **RAQM**, with
  fractional advances;
* everywhere else (most users' Macs, Windows, the CI runners) it uses
  **BASIC**, with whole-pixel advances.

The layout engine measures row labels, strip indicators and sheet text with
Pillow, so the same preset built on two Macs came out a fraction of a
millimetre different (hexagon patch 8.09 against 8.1 mm, a row-label band
9.128 against 9.2312 mm; RB-6 of the beta-11 CI round). Basti decided
2026-10-05: *"ok pin basic for beta 11"*. Every chart is now laid out as most
machines already laid it out, and is byte-identical whether or not FriBiDi is
installed.

Product code never calls ``ImageFont.truetype`` itself; it calls
:func:`load_font`, so a new call cannot forget the pin.
``tests/test_pillow_text_layout_is_pinned_to_basic.py`` keeps it that way.
(``ImageFont.load_default()`` is already BASIC inside Pillow, and
``FreeTypeFont.font_variant`` keeps the engine of the font it copies.)
"""
from __future__ import annotations

from PIL import ImageFont

#: The engine every ChromIQ font is opened with.
LAYOUT_ENGINE = ImageFont.Layout.BASIC


def load_font(font, size: float = 10, index: int = 0,
              encoding: str = "") -> ImageFont.FreeTypeFont:
    """``ImageFont.truetype`` with the layout engine pinned to BASIC.

    Raises what ``ImageFont.truetype`` raises (``OSError`` for a font it
    cannot find or read), so callers keep their own fallbacks.
    """
    return ImageFont.truetype(font, size, index, encoding,
                              layout_engine=LAYOUT_ENGINE)
