"""Text measurements the tests freeze, and where they hold (CI round 2).

The layout engine draws every chart's text with Pillow
(`workflow/layout_engine/raster.py`). Pillow's wheels carry libraqm but load
FriBiDi at run time, so Pillow's DEFAULT engine depends on the machine: RAQM
where a FriBiDi library can be found (Basti's Mac has Homebrew's), BASIC
everywhere else. CI round 2 therefore carried a BASIC value beside every
frozen RAQM one and picked by the engine found.

Since beta 11 the app never uses that default: `core.pil_font.load_font` pins
BASIC (RB-6, Basti 2026-10-05, "ok pin basic for beta 11"), so a chart is
byte-identical with or without FriBiDi and every frozen text measurement has
ONE expected value, the BASIC one, on every machine. The RAQM/BASIC switch
that lived here is gone with it.

What remains is the macOS CoreText marker below: Qt's text (PDF reports,
help cards) is a different text stack, untouched by the pin.
"""
from __future__ import annotations


def _measured_with_coretext():
    import sys

    import pytest
    return pytest.mark.skipif(sys.platform != "darwin", reason=(
        "a page count or a fixture sized to spill by one line, measured with "
        "macOS CoreText text metrics; FreeType (Linux, and Windows offscreen) "
        "sets the same text in other widths, so the pinned number is a "
        "different number there rather than a fault. The general rules "
        "(no colophon-only sheet, no table straddling) still run everywhere"))


#: Marks a test whose expected number IS a macOS measurement (CI round 2).
MEASURED_WITH_CORETEXT = _measured_with_coretext()
