"""Which engine Pillow lays text out with in THIS process (CI round 2).

The layout engine draws every chart's text (`workflow/layout_engine/raster.py`
measures labels with `ImageFont`). Pillow's wheels carry libraqm but load
FriBiDi at run time, so the engine depends on the MACHINE:

* RAQM where a FriBiDi library can be found. Basti's Mac has Homebrew's
  ``/opt/homebrew/lib/libfribidi.dylib``, so every number frozen on it was
  measured with RAQM (fractional advances).
* BASIC (whole-pixel advances) everywhere else: the GitHub runners (macOS,
  Windows), and a Mac without Homebrew's fribidi.

Measured 2026-10-04 by forcing BASIC on that Mac: exactly the values the macOS
runner reported (hexagon 8.09 against 8.1 mm, the auto bottom line 23.029
against 22.479 mm, an Instrument Serif italic row label equal to the regular
one at 34 px). Tests that freeze a text measurement carry the BASIC value
beside the RAQM one and pick by `pillow_lays_out_with_raqm()`; neither is
loosened.
"""
from __future__ import annotations

import functools
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@functools.lru_cache(maxsize=1)
def pillow_lays_out_with_raqm() -> bool:
    """True when `ImageFont.truetype` defaults to the RAQM engine here."""
    from PIL import ImageFont
    f = ImageFont.truetype(
        str(ROOT / "assets" / "fonts" / "Inter-VariableFont_opsz,wght.ttf"), 12)
    return f.layout_engine == ImageFont.Layout.RAQM


#: The reason a test gives when it keeps a second, BASIC-layout expectation.
BASIC_LAYOUT_REASON = (
    "Pillow lays text out with its BASIC engine here (no FriBiDi, so no "
    "libraqm): whole-pixel advances, as on the CI runners and on a Mac "
    "without Homebrew's fribidi")
