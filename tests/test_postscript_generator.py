"""Regression tests for PostScript page-size handling.

Issues #14 (landscape chart prints as portrait, columns cut off) and #15
(landscape chart silently disappears from the queue) both came from
PostScriptGenerator emitting a portrait `setpagedevice` PageSize while
drawing a landscape image on top — the image overhung the page and pstops
either clipped it or rejected it.

Pin the aspect-aware swap so we don't regress.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
import tifffile

from workflow.postscript_generator import PdfGenerator, PostScriptGenerator


def test_pdf_devicen_tint_maps_each_ink_not_all_magenta():
    """The DeviceN→CMYK tint transform must map each ink to its own CMYK
    contribution (so a viewer previews real colours), not collapse everything
    into one channel (the old average-into-magenta bug). #72"""
    body = PdfGenerator._pdf_tint_fn_body(6, ["c", "m", "y", "k", "o", "g"])
    # orange contributes magenta(0.4)+yellow(0.7); green contributes cyan+yellow(0.5)
    assert "0.7000 mul" in body and "0.4000 mul" in body and "0.5000 mul" in body
    # the buggy form averaged all inks (`6 div … 4 1 roll`); make sure it's gone
    assert "6 div" not in body
    assert body.count("index") >= 4          # weighted sums via stack copies


def _write_tiff(path: Path, w_px: int, h_px: int, dpi: int = 200) -> None:
    """Write a synthetic RGB TIFF with INCH resolution units."""
    arr = np.zeros((h_px, w_px, 3), dtype=np.uint8)
    tifffile.imwrite(str(path), arr, resolution=(dpi, dpi), resolutionunit="INCH")


def _page_size(ps_text: str) -> tuple[float, float]:
    m = re.search(r"/PageSize \[(\S+) (\S+)\]", ps_text)
    assert m, "no setpagedevice PageSize emitted"
    return float(m.group(1)), float(m.group(2))


def _translate(ps_text: str) -> tuple[float, float]:
    m = re.search(r"^(\S+) (\S+) translate$", ps_text, re.MULTILINE)
    assert m, "no translate emitted"
    return float(m.group(1)), float(m.group(2))


# Sub-pixel tolerance for tifffile's rational-encoded XResolution: writing
# resolution=200 round-trips back at ~199.91 dpi, so derived points drift by
# ≲0.5 pt. The bug we're testing for was a ~350 pt overhang.
_PT_SLOP = 1.0


# Issue #15 in miniature: A3 landscape TIFF + A3 portrait page_size_pt.
def test_landscape_tiff_on_portrait_page_swaps(tmp_path: Path) -> None:
    tiff = tmp_path / "landscape.tif"
    _write_tiff(tiff, w_px=3307, h_px=2339, dpi=200)  # ~1190 × 842 pt landscape
    ps = PostScriptGenerator().generate(tiff, page_size_pt=(842, 1191))
    pw, ph = _page_size(ps)
    assert pw > ph, f"expected landscape PageSize, got {pw}×{ph}"
    x_off, y_off = _translate(ps)
    assert x_off >= -_PT_SLOP and y_off >= -_PT_SLOP, (
        f"translate offsets {x_off}, {y_off} should be ~non-negative — "
        "image must fit inside the page"
    )


def test_portrait_tiff_on_landscape_page_swaps(tmp_path: Path) -> None:
    tiff = tmp_path / "portrait.tif"
    _write_tiff(tiff, w_px=2339, h_px=3307, dpi=200)  # ~842 × 1190 pt portrait
    ps = PostScriptGenerator().generate(tiff, page_size_pt=(1191, 842))
    pw, ph = _page_size(ps)
    assert ph > pw, f"expected portrait PageSize, got {pw}×{ph}"
    x_off, y_off = _translate(ps)
    assert x_off >= -_PT_SLOP and y_off >= -_PT_SLOP


def test_matching_aspect_does_not_swap(tmp_path: Path) -> None:
    tiff = tmp_path / "landscape.tif"
    _write_tiff(tiff, w_px=3307, h_px=2339, dpi=200)
    ps = PostScriptGenerator().generate(tiff, page_size_pt=(1191, 842))
    assert _page_size(ps) == (1191.0, 842.0)


def test_no_page_size_falls_back_to_tiff_dims(tmp_path: Path) -> None:
    tiff = tmp_path / "landscape.tif"
    _write_tiff(tiff, w_px=3307, h_px=2339, dpi=200)
    ps = PostScriptGenerator().generate(tiff)
    pw, ph = _page_size(ps)
    # 3307 px / 200 dpi * 72 pt/in = 1190.52; 2339 / 200 * 72 = 841.68
    assert pw == pytest.approx(1190.52, abs=_PT_SLOP)
    assert ph == pytest.approx(841.68, abs=_PT_SLOP)


def test_square_tiff_keeps_portrait_page(tmp_path: Path) -> None:
    # Strict `>` semantics: a perfectly square TIFF is neither landscape nor
    # portrait, so it must not trigger a swap when the page is portrait.
    tiff = tmp_path / "square.tif"
    _write_tiff(tiff, w_px=1000, h_px=1000, dpi=200)
    ps = PostScriptGenerator().generate(tiff, page_size_pt=(842, 1191))
    assert _page_size(ps) == (842.0, 1191.0)


# Issue #15 second failure mode: 16-bit TIFFs from `printtarg -T` produced PS
# with `colorimage … 16 …`, which older HP PostScript interpreters silently
# drop. The generator must downcast to 8-bit so the inline image is the
# universally-accepted format.
def test_16bit_tiff_emits_8bit_colorimage(tmp_path: Path) -> None:
    tiff = tmp_path / "chart16.tif"
    arr = np.full((100, 100, 3), 0x8080, dtype=np.uint16)
    tifffile.imwrite(str(tiff), arr, resolution=(200, 200), resolutionunit="INCH")

    ps = PostScriptGenerator().generate(tiff)
    m = re.search(r"^(\d+) (\d+) (\d+)\n\[", ps, re.MULTILINE)
    assert m, "no `W H BPC` line preceding the transform matrix"
    bits = int(m.group(3))
    assert bits == 8, f"expected 8-bit colorimage, got {bits}-bit"


# Issue #15 third failure mode: HP CLJ 5550 honoured its printer-panel duplex
# default and ignored `lp -o Duplex=None`, so single-page chart jobs got
# pulled back through the duplexer and "Print All Pages" paired two charts
# onto one sheet. The PS-level setpagedevice directive overrides the device
# default — pin it here so a future refactor can't strip it.
def test_setpagedevice_disables_duplex(tmp_path: Path) -> None:
    tiff = tmp_path / "chart.tif"
    _write_tiff(tiff, w_px=1000, h_px=1000, dpi=200)
    ps = PostScriptGenerator().generate(tiff)
    m = re.search(r"<<[^>]*?>>\s*setpagedevice", ps)
    assert m, "no setpagedevice block emitted"
    block = m.group(0)
    assert "/Duplex false" in block, (
        f"setpagedevice must force /Duplex false to override device defaults — "
        f"got: {block!r}"
    )
    assert "/Tumble false" in block, (
        f"setpagedevice should include /Tumble false for spec correctness — "
        f"got: {block!r}"
    )


def test_16bit_downcast_preserves_high_byte(tmp_path: Path) -> None:
    # The downcast right-shifts by 8, so 0xABCD becomes 0xAB. Confirms we're
    # taking the MSB (the colorimetrically meaningful half) and not just
    # truncating to the LSB by casting.
    tiff = tmp_path / "msb.tif"
    arr = np.full((50, 50, 3), 0xABCD, dtype=np.uint16)
    tifffile.imwrite(str(tiff), arr, resolution=(200, 200), resolutionunit="INCH")

    ps = PostScriptGenerator().generate(tiff)
    # Round-trip the encoded payload back to bytes and check the high byte.
    import base64
    import zlib

    m = re.search(r"colorimage\n(.+?)~>", ps, re.DOTALL)
    assert m, "no colorimage payload found"
    a85 = m.group(1).replace("\n", "") + "~>"
    decoded = zlib.decompress(base64.a85decode(a85, adobe=True))
    assert decoded[:6] == b"\xab" * 6, (
        f"expected high-byte 0xAB after downcast, got {decoded[:6].hex()}"
    )


# ---------------------------------------------------------------------------
# PdfGenerator page-size handling — the exact-size PDF fallback.
#
# Raw-TIFF lp submission lets Apple's cgimagetopdf place the image, which
# shrinks a full-page chart ~3% to fit the imageable area (and ignores every
# ppi/scaling option). The PDF fallback exists to keep the chart at 100%:
# MediaBox matches the requested page, the image is drawn 1:1 and centred.
# Pin that geometry.
# ---------------------------------------------------------------------------

from workflow.postscript_generator import PdfGenerator


def _pdf_media_box(pdf: bytes) -> tuple[float, float]:
    m = re.search(rb"/MediaBox \[0 0 (\S+) (\S+)\]", pdf)
    assert m, "no MediaBox emitted"
    return float(m.group(1)), float(m.group(2))


def _pdf_image_ctm(pdf: bytes) -> tuple[float, float, float, float]:
    """Return (scale_x, scale_y, offset_x, offset_y) of the image placement."""
    m = re.search(rb"q\n(\S+) 0 0 (\S+) (\S+) (\S+) cm\n/Im Do", pdf)
    assert m, "no image placement CTM emitted"
    return tuple(float(m.group(i)) for i in (1, 2, 3, 4))  # type: ignore[return-value]


def test_pdf_full_page_chart_drawn_1to1_never_shrunk(tmp_path: Path) -> None:
    # The core regression: an A4-sized chart on an A4 page must be drawn at
    # its full natural size — not fitted into the printer's imageable area.
    tiff = tmp_path / "a4.tif"
    _write_tiff(tiff, w_px=1654, h_px=2339, dpi=200)  # ~595 × 842 pt portrait
    pdf = PdfGenerator().generate(tiff, page_size_pt=(595.28, 841.89))
    pw, ph = _pdf_media_box(pdf)
    sx, sy, ox, oy = _pdf_image_ctm(pdf)
    assert abs(pw - 595.28) < 0.01 and abs(ph - 841.89) < 0.01
    assert abs(sx - 595.44) < _PT_SLOP and abs(sy - 842.04) < _PT_SLOP, (
        f"image must keep its natural size, got {sx}×{sy}"
    )
    assert abs(ox) < _PT_SLOP and abs(oy) < _PT_SLOP


def test_pdf_smaller_chart_centred_on_page(tmp_path: Path) -> None:
    tiff = tmp_path / "small.tif"
    _write_tiff(tiff, w_px=1000, h_px=1500, dpi=200)  # 360 × 540 pt portrait
    pdf = PdfGenerator().generate(tiff, page_size_pt=(595.28, 841.89))
    sx, sy, ox, oy = _pdf_image_ctm(pdf)
    assert abs(sx - 360.0) < _PT_SLOP and abs(sy - 540.0) < _PT_SLOP
    assert abs(ox - (595.28 - sx) / 2) < 0.01
    assert abs(oy - (841.89 - sy) / 2) < 0.01


def test_pdf_landscape_tiff_on_portrait_page_is_turned(tmp_path: Path) -> None:
    # Beta 16 final: the MediaBox keeps the PAPER's orientation and the image
    # is turned onto it. A swapped (landscape) MediaBox on portrait paper was
    # printed unturned and cut off by macOS's PDF rasteriser (measured on
    # four capture queues).
    tiff = tmp_path / "landscape.tif"
    _write_tiff(tiff, w_px=3307, h_px=2339, dpi=200)  # ~1190 × 842 pt landscape
    pdf = PdfGenerator().generate(tiff, page_size_pt=(842, 1191))
    pw, ph = _pdf_media_box(pdf)
    assert (pw, ph) == (842, 1191), f"expected the portrait paper, got {pw}×{ph}"
    m = re.search(rb"q\n0 (\S+) (\S+) 0 (\S+) (\S+) cm\n/Im Do", pdf)
    assert m, "the landscape image must be drawn turned"
    b, c, e, f = (float(m.group(i)) for i in range(1, 5))
    assert abs(b - 1190.5) < 1 and abs(-c - 842.0) < 1     # 1:1, never scaled
    assert e + c >= -_PT_SLOP and f >= -_PT_SLOP, "the turned image must fit the page"


def test_pdf_no_page_size_defaults_to_tiff_dims(tmp_path: Path) -> None:
    tiff = tmp_path / "plain.tif"
    _write_tiff(tiff, w_px=1000, h_px=1500, dpi=200)
    pdf = PdfGenerator().generate(tiff)
    pw, ph = _pdf_media_box(pdf)
    sx, sy, ox, oy = _pdf_image_ctm(pdf)
    assert abs(pw - sx) < 0.01 and abs(ph - sy) < 0.01
    assert ox == 0.0 and oy == 0.0
