"""Map device values to a displayable sRGB-ish triple for the TIFF raster.

ChromIQ profiles **RGB** printers, so RGB / CMY (stored as RGB) render exactly.
Gray and CMYK are converted for a faithful *visual* chart; their measured
device values in the ``.ti2`` are always exact regardless of this preview.
Extra inks beyond CMY(K) (O/R/G/B/V, light inks…) are composited on top of
the CMY(K) base in linear light using the per-ink absorption model below —
without this an orange-only patch has C=M=Y=K=0 and would render paper white
(#124 reports 4/5).
"""
from __future__ import annotations

# ink code → (R_absorption, G_absorption, B_absorption) per unit ink value
# (0–1). Values calibrated against the US Web Coated SWOP v2 ICC profile's
# full-ink response. The canonical table — ui.tiff_preview composites its
# separated-view previews from this same data.
#
# Provenance note: these are a handful of full-ink sRGB triples read off that
# profile, kept because they are what the numbers below were fitted to. The
# profile itself is no longer bundled (see THIRD-PARTY-NOTICES.md); ChromIQ
# ships ArgyllCMS's public-domain ref/cmyk.icm instead.
_INK_ABSORPTION: dict[str, tuple[float, float, float]] = {
    # CMYK primaries (calibrated from SWOP full-ink response on white paper)
    "c":   (1.00, 0.32, 0.06),   # Cyan:    R=0, G=174, B=239 at full ink on white
    "m":   (0.08, 1.00, 0.45),   # Magenta: R=236, G=0, B=140
    "y":   (0.00, 0.05, 1.00),   # Yellow:  R=255, G=242, B=0
    "k":   (0.86, 0.88, 0.87),   # Black:   R=35, G=31, B=32
    # Light inks ≈ parent at ~50% (extrapolated from SWOP midtone data)
    "lc":  (0.57, 0.18, 0.04),
    "lm":  (0.04, 0.57, 0.25),
    "ly":  (0.00, 0.03, 0.55),
    "lk":  (0.42, 0.42, 0.42),
    "llk": (0.22, 0.22, 0.22),
    # Medium inks ≈ parent at ~75%
    "mc":  (0.80, 0.25, 0.05),
    "mm":  (0.06, 0.80, 0.35),
    "my":  (0.00, 0.04, 0.78),
    "mk":  (0.65, 0.65, 0.65),
    # Spot / extended-gamut inks
    "o":   (0.02, 0.40, 0.95),   # Orange:      absorbs blue + some green
    "r":   (0.05, 0.90, 0.80),   # Red:         absorbs green + blue
    "g":   (0.90, 0.05, 0.80),   # Green:       absorbs red + blue
    "b":   (0.82, 0.68, 0.05),   # Blue/Violet: absorbs red + most green
    "v":   (0.76, 0.62, 0.04),   # Violet
    "w":   (0.00, 0.00, 0.00),   # White
}

# COLOR_REP letter token → ChromIQ ink code — the inverse of
# ``workflow.ti2_relayout._INK_REP_LETTER`` (Argyll's inkmask notation:
# lowercase = light ink, "2c" = medium cyan, "1k" = light-light black).
_REP_TOKEN_CODE: dict[str, str] = {
    "C": "c", "M": "m", "Y": "y", "K": "k", "O": "o", "R": "r", "G": "g",
    "B": "b", "V": "v", "W": "w",
    "c": "lc", "m": "lm", "y": "ly", "k": "lk",
    "2c": "mc", "2m": "mm", "2y": "my", "2k": "mk", "1k": "llk",
}


def rep_ink_codes(color_rep: str) -> list[str] | None:
    """``COLOR_REP`` string → per-channel ChromIQ ink codes, or None if any
    token is unknown (case-sensitive: ``"CMYKcm"`` → light cyan/magenta)."""
    s = color_rep.strip()
    if s.startswith("i"):        # display-space marker (iRGB etc.)
        s = s[1:]
    out: list[str] = []
    i = 0
    while i < len(s):
        tok = s[i]
        if tok.isdigit():
            if i + 1 >= len(s):
                return None
            tok += s[i + 1]
            i += 1
        i += 1
        code = _REP_TOKEN_CODE.get(tok)
        if code is None:
            return None
        out.append(code)
    return out


def _srgb1_to_linear(v: float) -> float:
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _linear1_to_srgb(v: float) -> float:
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def _lab_to_linear_srgb(L: float, a: float, b: float) -> tuple[float, float, float]:
    """CIELab (D50) → linear sRGB (D50-adapted matrix), clipped to 0..1."""
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t: float) -> float:
        return t ** 3 if t > 6.0 / 29.0 else 3 * (6.0 / 29.0) ** 2 * (t - 4.0 / 29.0)

    x, y, z = finv(fx) * 0.9642, finv(fy) * 1.0, finv(fz) * 0.8249
    # Inverse of the Bradford-adapted sRGB→XYZ(D50) matrix.
    m = ((3.1338561, -1.6168667, -0.4906146),
         (-0.9787684, 1.9161415, 0.0334540),
         (0.0719453, -0.2289914, 1.4052427))
    return tuple(min(1.0, max(0.0, r[0] * x + r[1] * y + r[2] * z))
                 for r in m)  # type: ignore[return-value]


_ABS_LIN_CACHE: dict[str, tuple[float, float, float]] = {}


def ink_absorption_linear(code: str) -> tuple[float, float, float]:
    """Per-channel LINEAR-light absorption for one ink code.

    Preferred source: the ink's real Lab anchor from the i1Profiler export
    reference data (EXTRA_INK; placeholders excluded) — Lab → linear sRGB of
    the full ink on paper, absorption = 1 − transmittance. Fallback: the
    hand-calibrated gamma-space table, linearised (its values are full-ink
    sRGB responses, so decoding the implied colour is exact). Cached per code.
    """
    cached = _ABS_LIN_CACHE.get(code)
    if cached is not None:
        return cached
    rgb_lin = None
    try:
        from workflow.i1profiler_export import EXTRA_INK, _PLACEHOLDER_LAB
        key = {"o": "O", "g": "G", "v": "V", "b": "B"}.get(code)
        if key and key in EXTRA_INK and key not in _PLACEHOLDER_LAB:
            L, a_, b_ = (float(v) for v in EXTRA_INK[key][1].split("|"))
            rgb_lin = _lab_to_linear_srgb(L, a_, b_)
    except Exception:  # noqa: BLE001 — reference data is best-effort here
        rgb_lin = None
    if rgb_lin is None:
        ar, ag, ab = _INK_ABSORPTION.get(code, (0.87, 0.87, 0.87))
        rgb_lin = (_srgb1_to_linear(1 - ar), _srgb1_to_linear(1 - ag),
                   _srgb1_to_linear(1 - ab))
    out = tuple(min(1.0, max(0.0, 1.0 - t)) for t in rgb_lin)
    _ABS_LIN_CACHE[code] = out  # type: ignore[assignment]
    return out  # type: ignore[return-value]


def _composite_extra_inks(base_rgb: tuple[float, float, float],
                          device: tuple[float, ...], color_rep: str,
                          base_n: int) -> tuple[int, int, int] | None:
    """Multiply the extra channels' reflectance onto a CMY(K) base colour.

    Physical light mixes linearly, so the sRGB-ish base is decoded, each extra
    ink multiplies the reflectance by ``1 − ink · absorption``, and the result
    is re-encoded — the same model the separated-TIFF preview uses. Returns
    None when the rep can't be parsed (caller keeps the base colour).
    """
    codes = rep_ink_codes(color_rep)
    if codes is None or len(codes) != len(device):
        return None
    ref = [_srgb1_to_linear(min(255.0, max(0.0, v)) / 255.0) for v in base_rgb]
    for val, code in zip(device[base_n:], codes[base_n:]):
        t = min(1.0, max(0.0, val / 100.0))
        absorb = ink_absorption_linear(code)
        ref = [rr * (1.0 - t * aa) for rr, aa in zip(ref, absorb)]
    return tuple(max(0, min(255, round(_linear1_to_srgb(min(1.0, max(0.0, rr)))
                                       * 255.0))) for rr in ref)  # type: ignore[return-value]


def to_display_rgb(device: tuple[float, ...], color_rep: str) -> tuple[int, int, int]:
    """Device values (0–100) → 8-bit (R, G, B) for rendering."""
    rep = color_rep.upper()

    def clamp(v: float) -> int:
        return max(0, min(255, round(v)))

    if rep in ("RGB", "IRGB") and len(device) == 3:
        # Stored RGB is the printable RGB (CMY targets are stored as RGB too).
        return tuple(clamp(c / 100.0 * 255.0) for c in device)  # type: ignore[return-value]

    if rep == "W" and len(device) == 1:
        v = clamp(device[0] / 100.0 * 255.0)
        return (v, v, v)

    if rep.startswith("CMYK") and len(device) >= 4:
        c, m, y, k = (d / 100.0 for d in device[:4])
        r = 255.0 * (1.0 - c) * (1.0 - k)
        g = 255.0 * (1.0 - m) * (1.0 - k)
        b = 255.0 * (1.0 - y) * (1.0 - k)
        if len(device) > 4:
            extra = _composite_extra_inks((r, g, b), device, color_rep, 4)
            if extra is not None:
                return extra
        return (clamp(r), clamp(g), clamp(b))

    if rep.startswith("CMY") and len(device) >= 3:
        c, m, y = (d / 100.0 for d in device[:3])
        r = 255.0 * (1.0 - c)
        g = 255.0 * (1.0 - m)
        b = 255.0 * (1.0 - y)
        if len(device) > 3:
            extra = _composite_extra_inks((r, g, b), device, color_rep, 3)
            if extra is not None:
                return extra
        return (clamp(r), clamp(g), clamp(b))

    # Fallback: first channel as grey.
    v = clamp((device[0] if device else 0.0) / 100.0 * 255.0)
    return (v, v, v)


def luminance(rgb: tuple[int, int, int]) -> float:
    """Rec.709 relative luminance (0–255)."""
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def to_device_approx(rgb: tuple[int, int, int],
                     device_fields: list[str]) -> tuple[float, ...]:
    """Approximate device ink values (0–100) for a *display* colour.

    Used for **unmeasured** furniture whose colour carries meaning — chiefly the
    contrast spacers, so a red/yellow separator prints red/yellow on a CMYK+N
    device instead of collapsing to grey (matching printtarg's coloured spacers).
    Achromatic colours route to the single black ink (clean, low ink); chromatic
    colours invert into C/M/Y. Extra inks (O/G/V/light) stay 0 — approximate by
    design, never applied to a patch that gets measured.
    """
    r, g, b = (v / 255.0 for v in rgb)
    suf = [f.split("_")[-1].upper() for f in device_fields]
    out = [0.0] * len(suf)
    mx, mn = max(r, g, b), min(r, g, b)
    if (mx - mn) < 0.06 and "K" in suf:          # near-neutral → black ink only
        out[suf.index("K")] = 100.0 * (1.0 - mx)
        return tuple(out)
    for i, s in enumerate(suf):                  # chromatic → naive CMY inversion
        if s == "C":
            out[i] = 100.0 * (1.0 - r)
        elif s == "M":
            out[i] = 100.0 * (1.0 - g)
        elif s == "Y":
            out[i] = 100.0 * (1.0 - b)
    return tuple(out)


def to_device_approx_array(rgb, device_fields: list[str]):
    """Vectorised :func:`to_device_approx` over an ``(H, W, 3)`` uint8 image →
    ``(H, W, n)`` float device values (0–100).

    Used to carry a *rendered* colour region — chiefly the notes/clip strip —
    into the device raster so its artwork prints in colour (a CMY(K)
    approximation; extra inks stay 0) instead of flat black. Near-neutral pixels
    route to the black ink; black text therefore stays crisp K.
    """
    import numpy as np

    r = rgb[..., 0].astype(np.float32) / 255.0
    g = rgb[..., 1].astype(np.float32) / 255.0
    b = rgb[..., 2].astype(np.float32) / 255.0
    suf = [f.split("_")[-1].upper() for f in device_fields]
    n = len(suf)
    out = np.zeros(r.shape + (n,), dtype=np.float32)
    for i, s in enumerate(suf):                  # chromatic → CMY inversion
        if s == "C":
            out[..., i] = 100.0 * (1.0 - r)
        elif s == "M":
            out[..., i] = 100.0 * (1.0 - g)
        elif s == "Y":
            out[..., i] = 100.0 * (1.0 - b)
    if "K" in suf:                               # near-neutral → single K ink
        mx = np.maximum(np.maximum(r, g), b)
        mn = np.minimum(np.minimum(r, g), b)
        ach = (mx - mn) < 0.06
        out[ach] = 0.0
        ki = suf.index("K")
        out[..., ki] = np.where(ach, 100.0 * (1.0 - mx), out[..., ki])
    return out
