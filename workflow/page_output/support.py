"""THE ONE SWITCH FOR CUSTOM PAGE SIZES IN INCHES OR PIXELS, AND HIGH
RESOLUTION (Preferences > Beta).

Asked for in issue #215 by a person who images charts on FILM RECORDERS: a
recorder takes a frame of an exact pixel count at an exact resolution
(4096 x 2730 pixels at 2731 pixels per inch, 18796 x 15748 at 2032), reads the
resolution written in the file, and interpolates when it differs. ChromIQ
4.3.42 could not make such a file: the custom size is whole millimetres, the
resolution stops at 1200, and the file carries pixels per centimetre.

With this switch ON, and only then, Create Chart > Manual (and the re-layout
window, which uses the same panel) offers:

* the custom page size in millimetres (with fractions), in inches, or as an
  exact pixel count, in three rows of two-way fields;
* a resolution up to :data:`DPI_MAX_ON`, guarded by a memory budget
  (:func:`budget_problem`) instead of a ppi cap;
* the file's resolution written in pixels per inch, as an option.

**OFF is 4.3.42**, widget for widget and byte for byte
(``tests/test_page_output_off_changes_nothing.py``). Every hook in shared code
asks :func:`page_output_enabled` first, or acts only on a recipe value that
nothing but this Beta can write.

**Restart to apply**, like the other Betas: the value is read ONCE per process
(``main()`` latches it before the window is built), so a panel never changes
its ranges under the person's hands.

THE STORED FORM (one decision, so every reader agrees)
------------------------------------------------------

* ``LayoutRecipe.paper`` stays the ``"<W>x<H>"`` code in millimetres. A whole
  millimetre size is spelt exactly as before (``"210x297"``), so every chart,
  preset and project written before this Beta reads back unchanged; a fraction
  is spelt with at most four decimals (``"234.95x196.85"``). Every reader of the
  code already takes decimals (``papers.parse_custom``).
* ``LayoutRecipe.page_size`` (``None`` unless used) keeps what the person TYPED
  for each side, with its unit, and the resolution it was meant for::

      {"w": [4096, "px"], "h": [2730, "px"], "ppi": 2731}

  It is written only when a side was typed in inches or pixels; a size typed in
  millimetres needs nothing beyond the paper code. The typed value is the
  truth: converting for display never feeds back into it, so a size does not
  drift however often the other fields are refreshed.
* ``LayoutRecipe.tiff_res_unit`` is ``"cm"`` (the default, as printtarg writes)
  or ``"in"``; written only when ``"in"``.

THE PIXEL RULE
--------------

A side given in pixels comes out with exactly that many pixels: the renderer is
handed the count (:func:`page_pixels`). A side given in millimetres or inches
comes out with ``round(mm * ppi / 25.4)`` pixels, the renderer's own expression
(``raster.render_pages``), so the panel's count and the file agree. Inside the
page every edge is the renderer's ``round(mm * ppi / 25.4)`` of its position,
so patches land on whole pixels the same way at every resolution.
"""

from __future__ import annotations

import math
from typing import Any

#: The AppSettings key (``core.settings.DEFAULTS``: False).
SETTING = "page_output_beta"

#: Units a custom page side can be typed in.
UNIT_MM = "mm"
UNIT_IN = "in"
UNIT_PX = "px"
UNITS = (UNIT_MM, UNIT_IN, UNIT_PX)

MM_PER_INCH = 25.4

#: The resolution box, off (4.3.42's) and on.
DPI_MIN = 72
DPI_MAX_OFF = 1200
DPI_MAX_ON = 6000

#: The custom size range in millimetres (4.3.42's, unchanged by the Beta).
CUSTOM_MM_MIN = 20.0
CUSTOM_MM_MAX = 2000.0

#: How many decimals the paper code keeps for a fractional millimetre size.
#: 0.0001 mm is 0.024 pixel at 6000 ppi, so the code can never move a pixel.
PAPER_CODE_DECIMALS = 4

#: The file's resolution unit (``LayoutRecipe.tiff_res_unit``).
RES_UNIT_CM = "cm"
RES_UNIT_IN = "in"
RES_UNITS = (RES_UNIT_CM, RES_UNIT_IN)

_latched: "bool | None" = None


# ---- the switch --------------------------------------------------------------

def stored_value(settings: Any) -> bool:
    """What Preferences holds now (it may differ from the running value)."""
    try:
        return bool(settings.get(SETTING, False))
    except Exception:  # noqa: BLE001 - a broken store means "off"
        return False


def latch_from(settings: Any) -> bool:
    """Fix the running value from *settings*. Called once by ``main()``."""
    global _latched
    _latched = stored_value(settings)
    return _latched


def page_output_enabled() -> bool:
    """True when the Beta is on for THIS run of ChromIQ (read once)."""
    global _latched
    if _latched is None:
        try:
            from core.settings import AppSettings
            _latched = stored_value(AppSettings())
        except Exception:  # noqa: BLE001
            _latched = False
    return _latched


def set_enabled_for_this_process(value: "bool | None") -> None:
    """Tests and drivers only: set the running value (None = read again)."""
    global _latched
    _latched = None if value is None else bool(value)


# ---- units -------------------------------------------------------------------

def to_mm(value: float, unit: str, ppi: float) -> float:
    """One side in millimetres, unrounded."""
    v = float(value)
    if unit == UNIT_IN:
        return v * MM_PER_INCH
    if unit == UNIT_PX:
        return v * MM_PER_INCH / float(ppi)
    return v


def from_mm(mm: float, unit: str, ppi: float) -> float:
    """One side, given in millimetres, in *unit* (unrounded; pixels as a
    float: :func:`pixels_of` rounds them the renderer's way)."""
    if unit == UNIT_IN:
        return float(mm) / MM_PER_INCH
    if unit == UNIT_PX:
        return float(mm) * float(ppi) / MM_PER_INCH
    return float(mm)


def pixels_of(mm: float, ppi: float) -> int:
    """The renderer's own pixel count for *mm* at *ppi*
    (``raster.render_pages``: ``max(1, round(mm * (dpi / 25.4)))``)."""
    return max(1, round(float(mm) * (float(ppi) / MM_PER_INCH)))


def format_mm(mm: float) -> str:
    """A side for the paper code: a whole number as before, else at most
    :data:`PAPER_CODE_DECIMALS` decimals with no trailing zeros."""
    r = round(float(mm), PAPER_CODE_DECIMALS)
    if r == int(r):
        return str(int(r))
    return f"{r:.{PAPER_CODE_DECIMALS}f}".rstrip("0").rstrip(".")


def paper_code(w_mm: float, h_mm: float) -> str:
    """The ``"<W>x<H>"`` millimetre code for a custom page."""
    return f"{format_mm(w_mm)}x{format_mm(h_mm)}"


def is_whole_mm_code(code: str) -> bool:
    """True for a custom code both of whose sides are whole millimetres (the
    only custom codes 4.3.42 could write)."""
    from workflow.layout_engine.papers import parse_custom
    dims = parse_custom(str(code or ""))
    if dims is None:
        return True
    return all(float(v) == int(float(v)) for v in dims)


# ---- the stored page size ----------------------------------------------------

def clean_page_size(value: Any) -> "dict | None":
    """A stored ``page_size`` read safely, or None. Never raises."""
    if not isinstance(value, dict):
        return None
    out: dict = {}
    try:
        for side in ("w", "h"):
            pair = value.get(side)
            if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
                return None
            v, unit = float(pair[0]), str(pair[1])
            if unit not in UNITS or not math.isfinite(v) or v <= 0:
                return None
            if unit == UNIT_PX:
                v = int(round(v))
            out[side] = [v, unit]
        ppi = int(round(float(value.get("ppi"))))
        if ppi <= 0:
            return None
        out["ppi"] = ppi
    except (TypeError, ValueError):
        return None
    return out


def make_page_size(w: "tuple[float, str]", h: "tuple[float, str]",
                   ppi: int) -> "dict | None":
    """The stored form for two typed sides, or None when both are in
    millimetres (the paper code then says all of it)."""
    if w[1] == UNIT_MM and h[1] == UNIT_MM:
        return None
    return clean_page_size({"w": [w[0], w[1]], "h": [h[0], h[1]],
                            "ppi": int(ppi)})


def page_mm(page_size: dict, ppi: "float | None" = None
            ) -> "tuple[float, float]":
    """The page in millimetres, unrounded. A side in pixels is converted at
    *ppi* (the chart's resolution), else at the resolution it was meant for."""
    p = float(ppi if ppi else page_size["ppi"])
    return (to_mm(page_size["w"][0], page_size["w"][1], p),
            to_mm(page_size["h"][0], page_size["h"][1], p))


def page_pixels(page_size: dict, ppi: float) -> "tuple[int, int]":
    """The page in pixels at *ppi*: a side typed in pixels exactly as typed,
    any other side by the renderer's rule (:func:`pixels_of`)."""
    out = []
    for side in ("w", "h"):
        v, unit = page_size[side]
        out.append(int(v) if unit == UNIT_PX else pixels_of(to_mm(v, unit, ppi), ppi))
    return out[0], out[1]


def uses_beta_values(recipe: Any) -> bool:
    """True when *recipe* holds something only this Beta can write: a typed
    page size, a fractional custom size, a resolution above 1200 or the file
    resolution in pixels per inch."""
    try:
        if clean_page_size(getattr(recipe, "page_size", None)) is not None:
            return True
        if str(getattr(recipe, "tiff_res_unit", RES_UNIT_CM) or RES_UNIT_CM) \
                != RES_UNIT_CM:
            return True
        if int(getattr(recipe, "dpi", 300) or 300) > DPI_MAX_OFF:
            return True
        return not is_whole_mm_code(str(getattr(recipe, "paper", "") or ""))
    except Exception:  # noqa: BLE001
        return False


# ---- the memory budget -------------------------------------------------------
#
# MEASURED, NOT GUESSED (2026-11-16, `build_chart` in a fresh process each,
# peak RSS from `ru_maxrss` less the process before the build; the runs are in
# the issue-215 work folder, `budget/run1.jsonl`):
#
#   RGB 8 bit,  A4 at 1200 ppi (139 Mpx), 1 page ........  2,025 MB  14.5 B/px
#   RGB 8 bit,  9.25 x 7.75 in at 2032 (296 Mpx), 1 page   4,222 MB  14.3 B/px
#   RGB 8 bit,  A4 at 1200, 2 pages .....................  3,002 MB  +7.0 B/px
#   RGB 16 bit, 9.25 x 7.75 in at 2032 ..................  7,774 MB  26.3 B/px
#   CMYK 8 bit, A4 at 1200 ..............................  12,188 MB 87.6 B/px
#   CMYK 8 bit, 9.25 x 7.75 in at 2032 ..................  25,800 MB 87.2 B/px
#
# A page being drawn costs the most; every further page adds what is kept of
# it until the files are written. The constants below round each measurement
# UP. The budget is 8 GiB: about what the largest chart ChromIQ already offers
# on a standard paper costs (A2 at 1200 dpi, RGB, ~10 GB measured in
# `raster.render_pages`'s own note), and half of a 16 GB Mac, which leaves the
# rest of the app and the system room to run. Above it the build is refused
# BEFORE anything is drawn, with the page's pixel count and what to reduce.

#: The memory a build may take, in bytes.
MEMORY_BUDGET_BYTES = 8 * 1024 ** 3

#: Bytes per pixel of the page being drawn, and of each further page kept.
RGB8_FIRST_B_PER_PX = 15.0
RGB16_FIRST_B_PER_PX = 27.0
FURTHER_PAGE_B_PER_PX = 7.0
#: A device-ink chart (CMY, CMYK, more inks): 22 bytes per ink per pixel
#: (four inks: 88, measured 87.2 to 87.6), and each further page keeps its
#: inks as well as its preview.
DEVICE_B_PER_INK_PX = 22.0


def bytes_per_pixel(*, inks: int = 3, device: bool = False,
                    bit16: bool = False) -> "tuple[float, float]":
    """(first page, each further page) bytes per pixel."""
    if device:
        n = max(4, int(inks or 4))
        first = DEVICE_B_PER_INK_PX * n + (2.0 * n if bit16 else 0.0)
        more = FURTHER_PAGE_B_PER_PX + n * (2.0 if bit16 else 1.0)
        return first, more
    return (RGB16_FIRST_B_PER_PX if bit16 else RGB8_FIRST_B_PER_PX,
            FURTHER_PAGE_B_PER_PX)


def estimated_bytes(w_px: int, h_px: int, pages: int = 1, **kind) -> float:
    """What drawing *pages* pages of *w_px* x *h_px* is expected to need."""
    first, more = bytes_per_pixel(**kind)
    px = float(w_px) * float(h_px)
    return px * (first + more * max(0, int(pages) - 1))


def max_megapixels(pages: int = 1, **kind) -> float:
    """The largest page, in megapixels, the budget allows for *pages* pages."""
    first, more = bytes_per_pixel(**kind)
    return MEMORY_BUDGET_BYTES / (first + more * max(0, int(pages) - 1)) / 1e6


def budget_problem(w_px: int, h_px: int, pages: int = 1, **kind
                   ) -> "str | None":
    """The friendly refusal when the page is over the budget, else None."""
    if estimated_bytes(w_px, h_px, pages, **kind) <= MEMORY_BUDGET_BYTES:
        return None
    from core.i18n import tr
    from workflow import measurement_messages as _mm
    mpx = w_px * h_px / 1e6
    limit = max_megapixels(pages, **kind)
    gb = estimated_bytes(w_px, h_px, pages, **kind) / 1e9
    text = _mm._PAGE_OVER_BUDGET_ONE if int(pages) <= 1 \
        else _mm._PAGE_OVER_BUDGET_MANY
    return tr(text).format(w=f"{int(w_px):,}", h=f"{int(h_px):,}",
                           mpx=f"{mpx:,.0f}", gb=f"{gb:,.1f}",
                           limit=f"{limit:,.0f}", pages=int(pages))


class PageBudgetError(ValueError):
    """A page over the memory budget, refused before anything was drawn."""


class PageBetaOff(ValueError):
    """A chart that needs this Beta, drawn while it is off: refused, never
    drawn at another size or resolution."""


def resolution_tags(dpi: float, unit: str) -> "tuple[tuple[float, float], int]":
    """``(resolution, resolutionunit)`` for ``tifffile.imwrite``.

    ``"in"``: the resolution exactly as the whole number of pixels per inch
    (tifffile writes 2731 as the rational 2731/1, which reads back as exactly
    2731). Anything else: pixels per centimetre, exactly as 4.3.42 wrote it
    (``dpi / 2.54``, ResolutionUnit 3)."""
    if unit == RES_UNIT_IN:
        return (float(dpi), float(dpi)), 2
    res = dpi / 2.54
    return (res, res), 3
