"""Generate PostScript Level 2/3 from TIFF profiling targets.

Uses device-dependent colour spaces (DeviceGray, DeviceRGB, DeviceCMYK,
DeviceN) to bypass all CUPS and macOS colour management.  Supports 8-bit
and 16-bit TIFFs for any channel count produced by printtarg.
"""
from __future__ import annotations

import base64
import zlib
from pathlib import Path

import numpy as np
import tifffile

from core.logger import get_logger

log = get_logger(__name__)

_PT_PER_INCH = 72.0

# ChromIQ ink codes → PostScript colorant names for DeviceN
_INK_CODE_TO_PS_NAME: dict[str, str] = {
    "k":   "Black",
    "c":   "Cyan",
    "m":   "Magenta",
    "y":   "Yellow",
    "r":   "Red",
    "g":   "Green",
    "b":   "Blue",
    "o":   "Orange",
    "v":   "Violet",
    "w":   "White",
    "lc":  "LightCyan",
    "lm":  "LightMagenta",
    "lk":  "LightBlack",
    "ly":  "LightYellow",
    "llk": "LightLightBlack",
    "mc":  "LightCyan2",
    "mm":  "LightMagenta2",
}

# Approximate CMYK contribution per ink for the DeviceN fallback tint transform.
# Accuracy is not critical — this path is only used by PS interpreters that do
# not support DeviceN natively.
_INK_TO_CMYK: dict[str, tuple[float, float, float, float]] = {
    "c":   (1.0, 0.0, 0.0, 0.0),
    "m":   (0.0, 1.0, 0.0, 0.0),
    "y":   (0.0, 0.0, 1.0, 0.0),
    "k":   (0.0, 0.0, 0.0, 1.0),
    "r":   (0.0, 0.5, 0.5, 0.0),
    "g":   (0.5, 0.0, 0.5, 0.0),
    "b":   (0.5, 0.5, 0.0, 0.0),
    "o":   (0.0, 0.4, 0.7, 0.0),
    "v":   (0.6, 0.5, 0.0, 0.0),
    "w":   (0.0, 0.0, 0.0, 0.0),
    "lc":  (0.5, 0.0, 0.0, 0.0),
    "lm":  (0.0, 0.5, 0.0, 0.0),
    "ly":  (0.0, 0.0, 0.5, 0.0),
    "lk":  (0.0, 0.0, 0.0, 0.5),
    "llk": (0.0, 0.0, 0.0, 0.3),
    "mc":  (0.3, 0.0, 0.0, 0.0),
    "mm":  (0.0, 0.3, 0.0, 0.0),
}


class PostScriptGenerator:
    """Convert a TIFF profiling target to a PostScript Level 2/3 document."""

    def generate(
        self,
        tiff_path: Path,
        dpi: int = 300,
        ink_channels: list[str] | None = None,
        page_size_pt: tuple[float, float] | None = None,
    ) -> str:
        """Return a complete PS document for *tiff_path*.

        DPI is read from the TIFF's XResolution tag; *dpi* is used as fallback.
        ink_channels: ordered ink codes matching the TIFF channels (e.g.
        ['c','m','y','k','lc','lm']) — required only for N > 4 channel DeviceN
        naming.  A sidecar .channels.json file is the usual source for this.
        page_size_pt: physical media size (w_pt, h_pt). When set, drives the
        PostScript setpagedevice PageSize so the PS document and any
        `lp -o PageSize=...` agree. Defaults to the TIFF's own dimensions.
        """
        arr, actual_dpi = self._read_tiff(tiff_path, fallback_dpi=dpi)
        # Downcast 16-bit TIFFs (printtarg -T) to 8-bit before encoding.
        # Older PostScript interpreters (e.g. HP CLJ 5550, firmware ~2005)
        # silently drop jobs whose `colorimage` uses BitsPerComponent=16, even
        # though the L3 spec supports it. Profile patches are flat fills, so
        # dropping the low byte is lossless for downstream colprof — the .ti3
        # measurement file is what determines profile accuracy, not the inline
        # image data sent to the printer. (Issue #15 second failure mode.)
        if arr.dtype == np.uint16:
            arr = (arr >> 8).astype(np.uint8)
            log.debug("PS: downcast 16-bit TIFF to 8-bit for colorimage compatibility")
        h, w, n_ch = arr.shape
        bits = 8

        tiff_w_pt = w * _PT_PER_INCH / actual_dpi
        tiff_h_pt = h * _PT_PER_INCH / actual_dpi
        if page_size_pt is None:
            page_w, page_h = tiff_w_pt, tiff_h_pt
            page_rotated = False
        else:
            page_w, page_h = page_size_pt
            # If the declared page orientation contradicts the TIFF's, swap
            # so setpagedevice agrees with the image we draw. Otherwise the
            # image overhangs the page bounds and pstops double-rotates.
            page_rotated = (page_w > page_h) != (tiff_w_pt > tiff_h_pt)
            if page_rotated:
                page_w, page_h = page_h, page_w

        cs_block = self._colorspace_block(n_ch, ink_channels)
        encoded, raw_len, encoded_len = self._encode_flate_a85(arr, bits)

        log.debug(
            "PS: %s  %dx%d px  TIFF %.1f×%.1f pt  Page %.1f×%.1f pt%s  "
            "%d dpi  %d-bit  %d-ch  raw %d → encoded %d (%.1f%%)",
            tiff_path.name, w, h, tiff_w_pt, tiff_h_pt, page_w, page_h,
            " (rotated to match TIFF aspect)" if page_rotated else "",
            actual_dpi, bits, n_ch, raw_len, encoded_len,
            100.0 * encoded_len / max(raw_len, 1),
        )

        return self._build_ps(
            w, h, tiff_w_pt, tiff_h_pt, page_w, page_h,
            bits, n_ch, cs_block, encoded,
        )

    # ------------------------------------------------------------------
    # TIFF reading
    # ------------------------------------------------------------------

    @staticmethod
    def _read_tiff(path: Path, fallback_dpi: int = 300) -> tuple[np.ndarray, float]:
        """Return (H, W, C) array and DPI extracted from the TIFF."""
        with tifffile.TiffFile(str(path)) as tif:
            page = tif.pages[0]
            dpi = PostScriptGenerator._read_dpi(page, fallback_dpi)
            arr = page.asarray()

        # Grayscale (H, W) → (H, W, 1)
        if arr.ndim == 2:
            arr = arr[:, :, np.newaxis]

        return np.ascontiguousarray(arr), dpi

    @staticmethod
    def _read_dpi(page: tifffile.TiffPage, fallback: int) -> float:
        """Pixels-per-inch from a TIFF page, honouring ResolutionUnit.

        ArgyllCMS `printtarg` writes the resolution in pixels-per-centimetre
        (ResolutionUnit = 3); the raw value (~118 for a 300-dpi chart) must be
        scaled by 2.54 or every derived dimension comes out 2.54× too large.
        """
        tag = page.tags.get("XResolution")
        if tag is None:
            return float(fallback)
        v = tag.value
        if isinstance(v, tuple) and len(v) == 2 and v[1]:
            res = float(v[0]) / float(v[1])
        else:
            try:
                res = float(v)
            except (TypeError, ValueError):
                return float(fallback)
        if res <= 0:
            return float(fallback)

        unit_tag = page.tags.get("ResolutionUnit")
        try:
            unit = int(getattr(unit_tag, "value", 2))
        except (TypeError, ValueError):
            unit = 2
        if unit == 1:          # no absolute unit
            return float(fallback)
        if unit == 3:          # pixels per centimetre → pixels per inch
            res *= 2.54
        return res

    # ------------------------------------------------------------------
    # Hex encoding
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_flate_a85(arr: np.ndarray, bits: int) -> tuple[str, int, int]:
        """Return (ascii85 stream, raw_len, encoded_len).

        Pixel bytes are deflate-compressed (zlib) and then ASCII85-encoded.
        The PS interpreter chains /ASCII85Decode → /FlateDecode → raw bytes,
        so what `colorimage` receives is bit-exact identical to the
        previous ASCII-hex-only path. Profile charts compress ~99% because
        the patches are large uniform areas — a 90 MB ASCII-hex stream
        becomes ~0.3 MB with this filter chain, which prevents PS interpreter
        OOM on consumer printers (the failure reported in issue #15).
        """
        raw = arr.astype(">u2").tobytes() if bits == 16 else arr.tobytes()
        compressed = zlib.compress(raw, 6)
        a85 = base64.a85encode(compressed, wrapcol=72).decode("ascii")
        return a85 + "~>", len(raw), len(a85) + 2

    # ------------------------------------------------------------------
    # Colour space blocks
    # ------------------------------------------------------------------

    def _colorspace_block(self, n_ch: int, ink_channels: list[str] | None) -> str:
        if n_ch == 1:
            return "/DeviceGray setcolorspace"
        if n_ch == 3:
            return "/DeviceRGB setcolorspace"
        if n_ch == 4:
            return "/DeviceCMYK setcolorspace"
        return self._devicen_block(n_ch, ink_channels)

    def _devicen_block(self, n_ch: int, ink_channels: list[str] | None) -> str:
        if ink_channels and len(ink_channels) >= n_ch:
            channels = list(ink_channels[:n_ch])
        else:
            channels = [f"ink{i + 1}" for i in range(n_ch)]

        ps_names = " ".join(
            f"/{_INK_CODE_TO_PS_NAME.get(c, c.capitalize())}"
            for c in channels
        )
        tint = self._devicen_tint(channels)
        return (
            f"[/DeviceN [{ps_names}]\n"
            f"/DeviceCMYK\n"
            f"{{\n{tint}\n}}\n"
            f"] setcolorspace"
        )

    def _devicen_tint(self, channels: list[str]) -> str:
        """PS procedure body: N ink values → 4 CMYK values (fallback only)."""
        n = len(channels)
        # Build unique PS variable names
        seen: dict[str, int] = {}
        varnames: list[str] = []
        for code in channels:
            safe = code.replace("-", "_")
            cnt = seen.get(safe, 0)
            seen[safe] = cnt + 1
            varnames.append(safe if cnt == 0 else f"{safe}_{cnt}")

        lines = [f"  {n} dict begin"]
        # Stack order: first channel deepest, last on top → pop in reverse order
        for vname in reversed(varnames):
            lines.append(f"  /{vname} exch def")

        for ci, comp in enumerate(("C", "M", "Y", "K")):
            terms: list[str] = []
            for i, code in enumerate(channels):
                w = _INK_TO_CMYK.get(code, (0.0, 0.0, 0.0, 0.0))[ci]
                if w > 0.0:
                    terms.append(
                        varnames[i] if w == 1.0
                        else f"{varnames[i]} {w:.3f} mul"
                    )
            if not terms:
                lines.append(f"  0.0  % {comp}")
            else:
                expr = terms[0]
                for t in terms[1:]:
                    expr += f" {t} add"
                lines.append(f"  {expr} 1.0 min  % {comp}")

        lines.append("  end")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # PS document assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ps(
        w_px: int, h_px: int,
        tiff_w_pt: float, tiff_h_pt: float,
        page_w_pt: float, page_h_pt: float,
        bits: int, n_ch: int,
        cs_block: str,
        encoded_data: str,
    ) -> str:
        # PostScript Level 3 is required for /FlateDecode (added in PS L3,
        # universal on every printer ChromIQ supports — HP CLJ ≥ 5550,
        # Epson/Canon photo printers from ~2005 onward). For the rare
        # L2-only target, CupsRawPrinter retries with the TIFF raster path.
        x_off = (page_w_pt - tiff_w_pt) / 2.0
        y_off = (page_h_pt - tiff_h_pt) / 2.0
        # /Duplex false /Tumble false are baked into setpagedevice rather than
        # relying on `lp -o Duplex=None`, because some older interpreters (HP
        # CLJ 5550, firmware ~2005) honour the panel/PPD default and ignore
        # the CUPS option — pulling each profiling sheet back through for a
        # blank second side, or pairing two charts onto one sheet for "Print
        # All Pages". setpagedevice is part of PS L3 and overrides the device
        # default, so the interpreter itself disables duplex. (Issue #15
        # third failure mode, reported after 3.5.2 fixed the colorimage bits.)
        return (
            f"%!PS-Adobe-3.0\n"
            f"%%LanguageLevel: 3\n"
            f"%cupsJobTicket: cups-disable-cmm\n"
            f"%%EndComments\n"
            f"\n"
            f"<< /PageSize [{page_w_pt:.2f} {page_h_pt:.2f}] /ImagingBBox null "
            f"/Duplex false /Tumble false >> setpagedevice\n"
            f"\n"
            f"{cs_block}\n"
            f"\n"
            f"{x_off:.2f} {y_off:.2f} translate\n"
            f"{tiff_w_pt:.2f} {tiff_h_pt:.2f} scale\n"
            f"{w_px} {h_px} {bits}\n"
            f"[{w_px} 0 0 -{h_px} 0 {h_px}]\n"
            f"currentfile /ASCII85Decode filter /FlateDecode filter\n"
            f"false {n_ch}\n"
            f"colorimage\n"
            f"{encoded_data}\n"
            f"\n"
            f"showpage\n"
            f"%%EOF\n"
        )


class PdfGenerator:
    """Convert a TIFF profiling target to a minimal PDF (bypass colour management)."""

    def generate(
        self,
        tiff_path: Path,
        dpi: int = 300,
        ink_channels: list[str] | None = None,
        page_size_pt: tuple[float, float] | None = None,
        icc_profile: bytes | None = None,
    ) -> bytes:
        """Return a complete PDF as bytes for *tiff_path*.

        icc_profile: an RGB chart is tagged ICCBased with these profile bytes
        instead of DeviceRGB.  Used to tag a chart with the very profile its job
        selects, so macOS's rasteriser has an identity conversion to make.

        page_size_pt: physical media size (w_pt, h_pt). When set, drives the
        page MediaBox so the PDF and any `lp -o PageSize=...` agree; the image
        is centred on it at its exact natural size — overhang is clipped at
        the printer's hardware margins, never scaled. (Apple's cgimagetopdf
        scales raw TIFFs down to fit the imageable area, which is exactly what
        this path exists to avoid.) Defaults to the TIFF's own dimensions.
        """
        arr, actual_dpi = PostScriptGenerator._read_tiff(tiff_path, fallback_dpi=dpi)
        h, w, n_ch = arr.shape
        bits = 16 if arr.dtype == np.uint16 else 8
        pts_w = w * _PT_PER_INCH / actual_dpi
        pts_h = h * _PT_PER_INCH / actual_dpi

        turned = False
        if page_size_pt is None:
            page_w, page_h = pts_w, pts_h
        else:
            page_w, page_h = page_size_pt
            # Beta 16 final: the MediaBox keeps the PAPER's orientation and a
            # chart of the other orientation is turned onto it, 90 degrees
            # counter-clockwise (CUPS' "landscape"). The page used to be swapped
            # to the chart's orientation, as the PostScript does; but macOS's
            # PDF rasteriser never turns a landscape page onto portrait paper:
            # measured on PRO-300, ET-8550, Gutenprint HP and HP DeskJet capture
            # queues, a landscape A4 chart on "A4" came out unturned, its
            # middle on the sheet and the rest cut off. (The TIFF route turns
            # it, through orientation-requested.)
            turned = (page_w > page_h) != (pts_w > pts_h) and abs(page_w - page_h) > 0.5
        draw_w, draw_h = (pts_h, pts_w) if turned else (pts_w, pts_h)
        x_off = (page_w - draw_w) / 2.0
        y_off = (page_h - draw_h) / 2.0

        log.debug(
            "PDF: %s  %dx%d px  %.1f×%.1f pt on %.1f×%.1f pt page  %d dpi  %d-bit  %d-ch",
            tiff_path.name, w, h, pts_w, pts_h, page_w, page_h, actual_dpi, bits, n_ch,
        )

        raw = arr.astype(">u2").tobytes() if bits == 16 else arr.tobytes()
        img_data = zlib.compress(raw, 6)
        cs_str = self._pdf_colorspace(n_ch, ink_channels)
        if turned:
            # the image's unit square: its width runs up the page, its height
            # to the left (a 90 degree counter-clockwise turn)
            content = (
                f"q\n0 {pts_w:.4f} {-pts_h:.4f} 0 {x_off + pts_h:.4f} {y_off:.4f} cm\n"
                f"/Im Do\nQ"
            ).encode("ascii")
        else:
            content = (
                f"q\n{pts_w:.4f} 0 0 {pts_h:.4f} {x_off:.4f} {y_off:.4f} cm\n/Im Do\nQ"
            ).encode("ascii")

        has_tint_fn = n_ch > 4
        tagged = icc_profile is not None and n_ch == 3
        if tagged:
            cs_str = "[/ICCBased 6 0 R]"
        n_objs = 6 if (has_tint_fn or tagged) else 5
        obj_bodies: list[bytes] = [b""] * (n_objs + 1)

        obj_bodies[1] = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        obj_bodies[2] = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        obj_bodies[3] = (
            f"3 0 obj\n"
            f"<< /Type /Page\n"
            f"   /MediaBox [0 0 {page_w:.4f} {page_h:.4f}]\n"
            f"   /Parent 2 0 R\n"
            f"   /Resources << /XObject << /Im 5 0 R >> >>\n"
            f"   /Contents 4 0 R >>\n"
            f"endobj\n"
        ).encode("ascii")
        obj_bodies[4] = (
            f"4 0 obj\n<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content + b"\nendstream\nendobj\n"
        )
        obj_bodies[5] = (
            f"5 0 obj\n"
            f"<< /Type /XObject /Subtype /Image\n"
            f"   /Width {w} /Height {h}\n"
            f"   /BitsPerComponent {bits}\n"
            f"   /ColorSpace {cs_str}\n"
            f"   /Filter /FlateDecode\n"
            f"   /Length {len(img_data)} >>\n"
            f"stream\n"
        ).encode("ascii") + img_data + b"\nendstream\nendobj\n"

        if tagged:
            icc_data = zlib.compress(icc_profile, 6)
            obj_bodies[6] = (
                f"6 0 obj\n"
                f"<< /N 3 /Alternate /DeviceRGB /Filter /FlateDecode\n"
                f"   /Length {len(icc_data)} >>\n"
                f"stream\n"
            ).encode("ascii") + icc_data + b"\nendstream\nendobj\n"
        if has_tint_fn:
            tint_body = self._pdf_tint_fn_body(n_ch, ink_channels).encode("ascii")
            domain = " ".join(["0 1"] * n_ch)
            obj_bodies[6] = (
                f"6 0 obj\n"
                f"<< /FunctionType 4\n"
                f"   /Domain [{domain}]\n"
                f"   /Range [0 1 0 1 0 1 0 1]\n"
                f"   /Length {len(tint_body)} >>\n"
                f"stream\n"
            ).encode("ascii") + tint_body + b"\nendstream\nendobj\n"

        return self._assemble_pdf(obj_bodies, n_objs)

    def _pdf_colorspace(self, n_ch: int, ink_channels: list[str] | None) -> str:
        if n_ch == 1:
            return "/DeviceGray"
        if n_ch == 3:
            return "/DeviceRGB"
        if n_ch == 4:
            return "/DeviceCMYK"
        channels = (
            list(ink_channels[:n_ch]) if ink_channels and len(ink_channels) >= n_ch
            else [f"ink{i + 1}" for i in range(n_ch)]
        )
        names = " ".join(
            f"/{_INK_CODE_TO_PS_NAME.get(c, c.capitalize())}" for c in channels
        )
        return f"[/DeviceN [{names}] /DeviceCMYK 6 0 R]"

    @staticmethod
    def _pdf_tint_fn_body(n_ch: int, ink_channels: list[str] | None = None) -> str:
        """PDF Type-4 tint function: N ink values → CMYK, each output the weighted
        sum of the inks' CMYK contributions (clamped) so a viewer previews the
        real colours. CMYK inks pass through 1:1; extra inks map to their nearest
        CMYK via _INK_TO_CMYK. (An earlier version averaged every ink into one
        channel, which previewed a CMYK+N chart as all-magenta.)

        PDF Type 4 restricts operators to arithmetic/boolean/stack — no def/begin/end.
        """
        channels = (list(ink_channels[:n_ch]) if ink_channels and len(ink_channels) >= n_ch
                    else [f"ink{i + 1}" for i in range(n_ch)])
        w = [_INK_TO_CMYK.get(c, (0.0, 0.0, 0.0, 0.0)) for c in channels]
        ops: list[str] = []
        for j in range(4):                       # C, M, Y, K outputs
            terms = [(i, w[i][j]) for i in range(n_ch) if w[i][j]]
            if not terms:
                ops.append("0")
            else:
                for k, (i, weight) in enumerate(terms):
                    ops.append(f"{j + k + (n_ch - 1 - i)} index {weight:.4f} mul")
                ops.extend(["add"] * (len(terms) - 1))
            ops.append("dup 0 lt {pop 0} if dup 1 gt {pop 1} if")   # clamp 0..1
        ops.append(f"{n_ch + 4} 4 roll")         # drop the N inputs under the CMYK
        ops.extend(["pop"] * n_ch)
        return "{ " + " ".join(ops) + " }"

    @staticmethod
    def _assemble_pdf(obj_bodies: list[bytes], n_objs: int) -> bytes:
        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        parts: list[bytes] = [header]
        offsets: list[int] = [0] * (n_objs + 1)
        pos = len(header)
        for i in range(1, n_objs + 1):
            offsets[i] = pos
            parts.append(obj_bodies[i])
            pos += len(obj_bodies[i])

        xref_pos = pos
        xref_lines: list[bytes] = [
            b"xref\n",
            f"0 {n_objs + 1}\n".encode("ascii"),
            b"0000000000 65535 f\r\n",
        ]
        for i in range(1, n_objs + 1):
            xref_lines.append(f"{offsets[i]:010d} 00000 n\r\n".encode("ascii"))
        parts.extend(xref_lines)

        trailer = (
            f"trailer\n<< /Size {n_objs + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
        parts.append(trailer)
        return b"".join(parts)
