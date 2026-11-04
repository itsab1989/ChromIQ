"""Can the FD-9 find this sheet? Checked at Generate, for every page (4.3.25).

The FD-9 finds a sheet by a pre-scan: the vendored driver's `find_marks`
looks for EXACTLY FOUR isolated small dark squares, and `grid_rows` binds the
chart's patch grid to them. Anything else printed on the sheet (the page
label, the FD-9 clip border, a very dark patch) that the detector takes for a
fifth mark, or that joins a mark, makes the FD-9 refuse the sheet at the
device, after it has been printed.

So every page is put through the same two functions before anything is
written, on a synthetic pre-scan: the page as printed, in grey, scaled to two
scan resolutions (about 300 and 276 dpi, the range measured on 2026-11-04 in
the FD-9's 3638-pixel-wide scan), mirrored as the FD-9 sees it. The check
passes when exactly four marks are found and every patch centre the grid
gives lands within 1 mm of the patch it should. It does not replace a test on
the device; it catches what can be caught before printing.

WHAT IS REFUSED IS WHAT CHROMIQ ADDED. A page that fails is checked again
without the label and the clip border: when it then passes, they are the
cause and Generate refuses the chart (`SheetNotDetectable`); when it fails
without them too, the cause is the chart itself (very dark 6 mm patches can
look like marks at the smaller scan scale, report point 8.5), which is a
question for a test on the device and not something ChromIQ added, so the
chart is made as in 4.3.24 and a warning goes to the log.

The grey is an estimate from the device values (the scanner is not
modelled): for RGB the luminance, for separated inks a product of each ink's
estimated darkness, with black the darkest.
"""
from __future__ import annotations

#: The two scan scales, as dpi.
SCAN_DPI = (300.0, 276.0)
#: The FD-9's pre-scan width in pixels, and the paper border around the sheet.
SCAN_WIDTH_PX = 3638
SCAN_MARGIN_PX = 490
#: How far a grid point may land from its patch centre.
TOLERANCE_MM = 1.0
#: Estimated darkness of a full ink, by Argyll channel token.
_INK_DARKNESS = {"K": 0.95, "C": 0.6, "M": 0.65, "Y": 0.12, "LC": 0.3,
                 "LM": 0.3, "LK": 0.55, "LLK": 0.35}


class SheetNotDetectable(ValueError):
    """A generated FD-9 page the FD-9's detector would not find. *page* and
    *pages* number from 1; *dpi* is the scan resolution it failed at."""

    def __init__(self, page, pages, dpi, why):
        self.fd9_page, self.fd9_pages, self.dpi, self.why = page, pages, dpi, why
        super().__init__(
            f"FD-9 sheet check at Generate: page {page} of {pages}, simulated "
            f"pre-scan at {dpi:.0f} dpi: {why}")


def gray_from_array(arr, *, additive, gray_ink, tokens, maxval):
    """An 8-bit grey (0 black .. 255 white) of the rendered page array."""
    import numpy as np
    a = arr.astype(np.float32) / float(maxval)
    if additive:
        if a.shape[2] >= 3:
            g = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
        else:
            g = a[..., 0]
    else:
        g = np.ones(a.shape[:2], dtype=np.float32)
        for i, t in enumerate(tokens):
            g *= 1.0 - _INK_DARKNESS.get(t, 0.5) * a[..., i]
    return np.clip(g * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _scan(gray, render_dpi, scan_dpi):
    """The page as the FD-9's pre-scan would see it: scaled, on a white
    border, mirrored. Returns (image, left, top, px per mm)."""
    from PIL import Image
    im = Image.fromarray(gray, mode="L")
    f = scan_dpi / float(render_dpi)
    if abs(f - 1.0) > 1e-6:
        im = im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))),
                       Image.BILINEAR)
    # A wide sheet does not fit 3638 px at 300 dpi; the canvas grows rather
    # than cut its marks off (whether the FD-9 scans that wide is a device
    # question, not this check's).
    width = max(SCAN_WIDTH_PX, im.width + 2 * 20)
    canvas = Image.new("L", (width, im.height + 2 * SCAN_MARGIN_PX), 255)
    left = (width - im.width) // 2
    canvas.paste(im, (left, SCAN_MARGIN_PX))
    return (canvas.transpose(Image.Transpose.FLIP_LEFT_RIGHT), left,
            SCAN_MARGIN_PX, im.width / (gray.shape[1] * 25.4 / render_dpi))


def check_page(gray, render_dpi, page_doc, page=1, pages=1):
    """Raise :class:`SheetNotDetectable` when the FD-9's own detector, run on
    a synthetic pre-scan of *gray* at either scan scale, does not find this
    page's four marks and its grid where they are."""
    from .independent import chart_grid, driver
    driver(None)
    from fd9_independent.geometry import find_marks, grid_rows
    for dpi in SCAN_DPI:
        scan, left, top, ppmm = _scan(gray, render_dpi, dpi)
        try:
            marks = find_marks(scan.tobytes(), scan.width, scan.height)
            grid = dict(chart_grid(page_doc), image_width_px=scan.width)
            rows = grid_rows(marks, **grid)
        except ValueError as error:
            raise SheetNotDetectable(page, pages, dpi, str(error)) from None
        tol = TOLERANCE_MM * ppmm
        for row, cells in zip(rows, page_doc["rows"]):
            for (gx, gy), cell in zip(row, cells):
                x, y = cell["centre_mm"]
                ex, ey = left + x * ppmm, top + y * ppmm
                if abs(gx - ex) > tol or abs(gy - ey) > tol:
                    raise SheetNotDetectable(
                        page, pages, dpi,
                        "the marks found do not put the patch grid where it "
                        f"is printed (patch {cell['id']} off by "
                        f"{max(abs(gx - ex), abs(gy - ey)) / ppmm:.1f} mm)")


def check_page_furniture(gray, furniture, render_dpi, page_doc, page=1,
                         pages=1):
    """`check_page`, refusing only what the label and the clip border
    (*furniture*, a boolean array of their ink, or None) cause."""
    import logging
    try:
        check_page(gray, render_dpi, page_doc, page, pages)
        return
    except SheetNotDetectable as error:
        failure = error
    if furniture is not None and furniture.any():
        plain = gray.copy()
        plain[furniture] = 255
        try:
            check_page(plain, render_dpi, page_doc, page, pages)
        except SheetNotDetectable:
            pass
        else:
            raise failure
    logging.getLogger(__name__).warning(
        "%s. Not caused by anything ChromIQ added to the sheet, so the chart "
        "is made as before; whether the FD-9 finds it is for a test on the "
        "device.", failure)
