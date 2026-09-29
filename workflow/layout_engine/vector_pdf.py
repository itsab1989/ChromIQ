"""Render a chart as a single multi-page **vector** PDF (#72).

Unlike :class:`workflow.postscript_generator.PdfGenerator` (which embeds the
rendered raster), this draws the chart as true vector: every patch and spacer is
a filled path in the chart's own device colour space (DeviceGray / RGB / CMYK /
DeviceN), the strip labels and sheet text are glyph outlines of the *exact* fonts
the engine chose, and the page is sized in real millimetres. The measurement grid
is therefore resolution-independent and byte-tiny, and — crucially — it is driven
by the **same** collected geometry as the TIFF (:func:`raster.render_pages` with
``collect_device_geom=True``), so the two outputs cannot diverge.

The notes/clip strip is embedded as a raster image (it can carry an imported
logo, which has no vector form); everything else is vector.
"""
from __future__ import annotations

import zlib
from pathlib import Path

from . import colorants
from . import vector_text

_PT_PER_MM = 72.0 / 25.4

# Device colorant char (device-field suffix) → PDF DeviceN colorant name.
_INK_PDF_NAME = {
    "C": "Cyan", "M": "Magenta", "Y": "Yellow", "K": "Black",
    "O": "Orange", "G": "Green", "R": "Red", "B": "Blue", "V": "Violet",
    "W": "White", "LC": "LightCyan", "LM": "LightMagenta", "LK": "LightBlack",
    "LY": "LightYellow", "LLK": "LightLightBlack", "MC": "LightCyan2",
    "MM": "LightMagenta2",
}


def _colorant_names(device_fields: list[str]) -> list[str]:
    return [_INK_PDF_NAME.get(f.split("_")[-1].upper(), f.split("_")[-1].capitalize())
            for f in device_fields]


# Approximate CMYK a colorant contributes, so the DeviceN tint transform previews
# real colours in a viewer (CMYK maps 1:1; extra inks map to their nearest CMYK).
_INK_CMYK = {
    "C": (1, 0, 0, 0), "M": (0, 1, 0, 0), "Y": (0, 0, 1, 0), "K": (0, 0, 0, 1),
    "O": (0, 0.35, 0.75, 0), "G": (0.65, 0, 0.70, 0), "V": (0.55, 0.65, 0, 0),
    "R": (0, 0.85, 0.85, 0), "B": (0.85, 0.60, 0, 0), "W": (0, 0, 0, 0),
    "LC": (0.4, 0, 0, 0), "LM": (0, 0.4, 0, 0), "LY": (0, 0, 0.4, 0),
    "LK": (0, 0, 0, 0.4), "LLK": (0, 0, 0, 0.2), "MC": (0.25, 0, 0, 0),
    "MM": (0, 0.25, 0, 0),
}


def _tint_fn_body(device_fields: list[str]) -> str:
    """PDF Type-4 tint transform: N ink values → CMYK, each output the weighted
    sum of the inks' CMYK contributions (clamped), so a viewer previews the real
    colours. CMYK inks pass through; extra inks map to their nearest CMYK."""
    codes = [f.split("_")[-1].upper() for f in device_fields]
    n = len(codes)
    w = [_INK_CMYK.get(c, (0, 0, 0, 0)) for c in codes]
    ops: list[str] = []
    for j in range(4):                       # C, M, Y, K outputs
        terms = [(i, w[i][j]) for i in range(n) if w[i][j]]
        if not terms:
            ops.append("0")
        else:
            for k, (i, weight) in enumerate(terms):     # in_i lies deeper as we push
                ops.append(f"{j + k + (n - 1 - i)} index {weight:.4f} mul")
            ops.extend(["add"] * (len(terms) - 1))
        ops.append("dup 0 lt {pop 0} if dup 1 gt {pop 1} if")   # clamp 0..1
    # stack now: in0..in_{n-1} C M Y K — roll the 4 outputs under and drop the inputs
    ops.append(f"{n + 4} 4 roll")
    ops.extend(["pop"] * n)
    return "{ " + " ".join(ops) + " }"


class _Obj:
    """A tiny indirect-object accumulator for hand-assembling the PDF."""

    def __init__(self) -> None:
        self.bodies: list[bytes] = [b""]        # 1-indexed; [0] unused

    def add(self, body: bytes) -> int:
        self.bodies.append(body)
        return len(self.bodies) - 1

    def reserve(self) -> int:
        self.bodies.append(b"")
        return len(self.bodies) - 1

    def set(self, num: int, body: bytes) -> None:
        self.bodies[num] = body

    def assemble(self, info_num: int | None = None) -> bytes:
        header = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"
        parts = [header]
        n = len(self.bodies) - 1
        offsets = [0] * (n + 1)
        pos = len(header)
        for i in range(1, n + 1):
            offsets[i] = pos
            parts.append(self.bodies[i])
            pos += len(self.bodies[i])
        xref_pos = pos
        xref = [b"xref\n", f"0 {n + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
        for i in range(1, n + 1):
            xref.append(f"{offsets[i]:010d} 00000 n \n".encode("ascii"))
        parts.extend(xref)
        info = f" /Info {info_num} 0 R" if info_num else ""
        parts.append((f"trailer\n<< /Size {n + 1} /Root 1 0 R{info} >>\n"
                      f"startxref\n{xref_pos}\n%%EOF\n").encode("ascii"))
        return b"".join(parts)


def _fill_color_op(dev01: tuple[float, ...], n: int) -> str:
    """Non-stroking colour operator for an n-channel device tuple in 0..1."""
    vals = " ".join(f"{v:.4f}" for v in dev01)
    if n == 1:
        return f"{vals} g"
    if n == 3:
        return f"{vals} rg"
    if n == 4:
        return f"{vals} k"
    return f"{vals} scn"          # DeviceN (colour space already selected)


def _page_content(page_elems: list[tuple], device_fields: list[str],
                  paper_w_mm: float, paper_h_mm: float, dpi: float,
                  cs_selected_name: str | None,
                  paper_dev01: tuple[float, ...]) -> tuple[bytes, list[dict]]:
    """Build one page's content stream from its collected display list.

    Returns ``(content_bytes, image_requests)`` — image_requests describes any
    clip-strip rasters the page needs so the caller can add XObjects.
    """
    n = len(device_fields)
    px2pt = 72.0 / dpi
    page_w_pt = paper_w_mm * _PT_PER_MM
    page_h_pt = paper_h_mm * _PT_PER_MM
    ops: list[str] = []
    images: list[dict] = []

    def y_pt(y_px: float) -> float:
        return page_h_pt - y_px * px2pt

    if cs_selected_name:                      # select DeviceN space for fills
        ops.append(f"/{cs_selected_name} cs")

    # Explicit paper background (the media patch's device value = white paper),
    # so undrawn areas print as paper and preview white in every viewer.
    ops.append(_fill_color_op(paper_dev01, n))
    ops.append(f"0 0 {page_w_pt:.3f} {page_h_pt:.3f} re f")

    def dev01_from_values(values, kind) -> tuple[float, ...]:
        if kind == "spacer":                  # spacer stored as display RGB (0..255)
            if n == 3:                         # RGB chart: display RGB *is* device
                return tuple(max(0.0, min(1.0, c / 255.0)) for c in values)
            if n == 1:                         # Gray: use luminance
                return (colorants.luminance(values) / 255.0,)
            # CMYK / DeviceN: approximate the display colour in ink
            return tuple(v / 100.0 for v in
                         colorants.to_device_approx(values, device_fields))
        return tuple(max(0.0, min(1.0, v / 100.0)) for v in values)

    for elem in page_elems:
        kind = elem[0]
        if kind == "clip":
            _, (ax, ay), arr = elem
            ih, iw = arr.shape[:2]
            x0 = ax * px2pt
            yb = y_pt(ay + ih)
            w = iw * px2pt
            h = ih * px2pt
            img_name = f"ClipIm{len(images)}"
            images.append({"name": img_name, "arr": arr})
            ops.append(f"q {w:.3f} 0 0 {h:.3f} {x0:.3f} {yb:.3f} cm /{img_name} Do Q")
            continue
        if kind in ("rect", "spacer"):
            _, (x0p, y0p, x1p, y1p), values = elem
            dev01 = dev01_from_values(values, kind)
            X = x0p * px2pt
            Yb = y_pt(y1p)
            W = (x1p - x0p) * px2pt
            H = (y1p - y0p) * px2pt
            ops.append(_fill_color_op(dev01, n))
            ops.append(f"{X:.3f} {Yb:.3f} {W:.3f} {H:.3f} re f")
        elif kind == "hex":
            _, pts, values = elem
            dev01 = dev01_from_values(values, kind)
            ops.append(_fill_color_op(dev01, n))
            p0 = pts[0]
            ops.append(f"{p0[0] * px2pt:.3f} {y_pt(p0[1]):.3f} m")
            for px_, py_ in pts[1:]:
                ops.append(f"{px_ * px2pt:.3f} {y_pt(py_):.3f} l")
            ops.append("h f")
        elif kind == "text":
            # ("text", left_x_px, baseline_y_px, str, font_path, size_px,
            #          spacing_px, rotation, rgb, variation)
            (_, lx, by, text, font_path, size_px, spc, rot, rgb, var) = elem
            ops.append(vector_text.run_ops(
                text, font_path, size_px, lx * px2pt, y_pt(by), px2pt,
                tuple(c / 255.0 for c in rgb), spacing_pt=spc * px2pt,
                rotation_deg=rot, variation=var))
        elif kind == "vrect":                 # furniture rule (underline etc.)
            # HALF-OPEN, like a Python slice: the box covers x0..x1-1 and
            # y0..y1-1, so its size is the plain difference. Pillow's own
            # `rectangle` is INCLUSIVE, so an emitter that hands its Pillow box
            # straight over loses a pixel in each dimension -- which is
            # invisible on a thick rule and total on a one-pixel one. See
            # `raster._ul_geom_rect`, which is the only converter.
            _, (x0p, y0p, x1p, y1p), rgb = elem
            r, g, b = (c / 255.0 for c in rgb)
            ops.append(f"{r:.4f} {g:.4f} {b:.4f} rg")
            ops.append(f"{x0p * px2pt:.3f} {y_pt(y1p):.3f} "
                       f"{(x1p - x0p) * px2pt:.3f} {(y1p - y0p) * px2pt:.3f} re f")

    return ("\n".join(ops) + "\n").encode("latin-1"), images


def save_vector_pdf(result, target, out_path: str | Path, *,
                    paper_w_mm: float, paper_h_mm: float, dpi: float) -> Path:
    """Write the collected render as one multi-page vector PDF at *out_path*.

    *result* is a :class:`raster.RenderResult` produced with
    ``collect_device_geom=True``; *target* supplies the device fields (colour
    space). Requires the display list — raises if geometry wasn't collected.
    """
    if result.patch_geom is None:
        raise ValueError("render lacked collect_device_geom=True; no vector geometry")
    device_fields = list(target.device_fields)
    n = len(device_fields)
    page_w_pt = paper_w_mm * _PT_PER_MM
    page_h_pt = paper_h_mm * _PT_PER_MM
    # White paper, matching the TIFF (which always renders on white): additive
    # spaces (RGB/Gray) → full 1.0; subtractive (CMYK/DeviceN) → 0 ink.
    paper_dev01 = (1.0,) * n if n in (1, 3) else (0.0,) * n

    objs = _Obj()
    catalog = objs.reserve()
    pages_obj = objs.reserve()

    # DeviceN colour space object (only for >4 inks), shared by every page.
    cs_selected = None
    devicen_obj = None
    if n > 4:
        tint = _tint_fn_body(device_fields).encode("ascii")
        domain = " ".join(["0 1"] * n)
        fn_obj = objs.add(
            (f"{{X}} 0 obj\n<< /FunctionType 4 /Domain [{domain}] "
             f"/Range [0 1 0 1 0 1 0 1] /Length {len(tint)} >>\nstream\n")
            .replace("{X}", str(len(objs.bodies))).encode("ascii")
            + tint + b"\nendstream\nendobj\n")
        names = " ".join(f"/{c}" for c in _colorant_names(device_fields))
        devicen_obj = objs.add(
            (f"{len(objs.bodies)} 0 obj\n[/DeviceN [{names}] /DeviceCMYK {fn_obj} 0 R]"
             f"\nendobj\n").encode("ascii"))
        cs_selected = "CSdev"

    page_obj_nums: list[int] = []
    for pi, page_elems in enumerate(result.patch_geom):
        content, image_reqs = _page_content(
            page_elems, device_fields, paper_w_mm, paper_h_mm, dpi, cs_selected,
            paper_dev01)
        content_z = zlib.compress(content, 6)
        content_obj = objs.add(
            (f"{len(objs.bodies)} 0 obj\n<< /Length {len(content_z)} "
             f"/Filter /FlateDecode >>\nstream\n").encode("ascii")
            + content_z + b"\nendstream\nendobj\n")

        # Clip-strip image XObjects (RGB raster).
        xobjects: list[tuple[str, int]] = []
        for req in image_reqs:
            arr = req["arr"]
            ih, iw = arr.shape[:2]
            raw = arr[:, :, :3].tobytes()
            zimg = zlib.compress(raw, 6)
            img_num = objs.add(
                (f"{len(objs.bodies)} 0 obj\n<< /Type /XObject /Subtype /Image "
                 f"/Width {iw} /Height {ih} /BitsPerComponent 8 "
                 f"/ColorSpace /DeviceRGB /Filter /FlateDecode "
                 f"/Length {len(zimg)} >>\nstream\n").encode("ascii")
                + zimg + b"\nendstream\nendobj\n")
            xobjects.append((req["name"], img_num))

        res_parts = ["/ProcSet [/PDF /ImageC]"]
        if cs_selected:
            res_parts.append(f"/ColorSpace << /{cs_selected} {devicen_obj} 0 R >>")
        if xobjects:
            xo = " ".join(f"/{nm} {num} 0 R" for nm, num in xobjects)
            res_parts.append(f"/XObject << {xo} >>")
        page_num = objs.add(
            (f"{len(objs.bodies)} 0 obj\n<< /Type /Page /Parent {pages_obj} 0 R "
             f"/MediaBox [0 0 {page_w_pt:.4f} {page_h_pt:.4f}] "
             f"/Resources << {' '.join(res_parts)} >> "
             f"/Contents {content_obj} 0 R >>\nendobj\n").encode("ascii"))
        page_obj_nums.append(page_num)

    kids = " ".join(f"{p} 0 R" for p in page_obj_nums)
    objs.set(pages_obj, (f"{pages_obj} 0 obj\n<< /Type /Pages /Kids [{kids}] "
                         f"/Count {len(page_obj_nums)} >>\nendobj\n").encode("ascii"))
    objs.set(catalog, (f"{catalog} 0 obj\n<< /Type /Catalog /Pages {pages_obj} 0 R >>"
                       f"\nendobj\n").encode("ascii"))

    # Document info: File → Properties plainly shows the colour space + inks, so
    # it's obvious a CMYK/N chart is device-native and not an RGB picture (#72).
    cs_name = ("RGB" if target.color_rep.upper() in ("RGB", "IRGB")
               else "Gray" if n == 1 else target.color_rep.upper())
    inks = ", ".join(_colorant_names(device_fields))

    def _pdfstr(s: str) -> str:
        return "(" + s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"

    info_num = objs.add(
        (f"{len(objs.bodies)} 0 obj\n"
         f"<< /Title {_pdfstr(f'ChromIQ chart - {cs_name} ({n}-channel)')}"
         f" /Subject {_pdfstr(f'Colorants: {inks}')}"
         f" /Creator (ChromIQ) /Producer (ChromIQ vector PDF export) >>\n"
         f"endobj\n").encode("latin-1"))

    out = Path(out_path)
    out.write_bytes(objs.assemble(info_num))
    return out
