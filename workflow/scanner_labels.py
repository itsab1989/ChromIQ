"""Patch-label generation, combination and normalisation for scanner/camera
targets — a faithful port of the label logic in Knut Georg Larsson's **rectarg**
(https://github.com/…/rectarg, GPLv3), the tool ChromIQ users generate their
targets with. Credited to Knut; reproduced so ChromIQ's bundled ``.cht`` files
name every patch exactly the way rectarg (and therefore the paired ``.cie``) does.

Three pieces:

* :func:`generate_labels` — expand an area-line range (``A``–``Z``, ``01``–``19``,
  ``2A``–``2D``, ``GS00``–``GS23``, Excel-style ``A``–``AX``) into its label list.
* :func:`make_patch_label` — combine a row + column label into a patch name, with
  the alphabetic part **always first** (``A1``, ``2A1``), matching rectarg.
* :func:`normalize_sid` — canonicalise a label so ``A1`` == ``A01`` == ``A001``,
  ``GS1`` == ``GS01``, ``2A1`` == ``2A01`` — how rectarg reconciles ``.cht`` and
  ``.cie`` naming regardless of zero-padding.
"""
from __future__ import annotations

import re

__all__ = [
    "generate_labels", "make_patch_label", "normalize_sid",
    "is_prefixed_alpha", "label_mode_for",
]


def _alpha_range(start: str, end: str) -> list[str]:
    """Excel-style alphabetic range: ``A``–``Z``, ``A``–``AA``, ``AA``–``AD`` …"""
    def alpha_to_num(a: str) -> int:
        n = 0
        for c in a:
            n = n * 26 + (ord(c) - 64)
        return n

    def num_to_alpha(n: int) -> str:
        s = ""
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    n1, n2 = alpha_to_num(start), alpha_to_num(end)
    if n2 < n1:
        n1, n2 = n2, n1
    return [num_to_alpha(i) for i in range(n1, n2 + 1)]


def generate_labels(start_tok: str, end_tok: str) -> list[str]:
    """Labels between *start_tok* and *end_tok* (inclusive). ``_`` → disabled
    axis → empty list. Handles GS grayscale, zero-padded numeric, numeric-prefixed
    alpha (``2A``–``2D``), and Excel-style multi-letter ranges."""
    if start_tok == "_" or end_tok == "_":
        return []
    s, e = start_tok.strip().upper(), end_tok.strip().upper()

    m1, m2 = re.match(r"^(GS)(\d+)$", s), re.match(r"^(GS)(\d+)$", e)
    if m1 and m2:                                    # GS grayscale strip
        a, b = int(m1.group(2)), int(m2.group(2))
        width = max(len(m1.group(2)), len(m2.group(2)))
        return [f"GS{idx:0{width}d}" for idx in range(a, b + 1)]

    if re.match(r"^\d+$", s) and re.match(r"^\d+$", e):   # pure numeric (padded)
        a, b = int(s), int(e)
        width = max(len(s), len(e))
        return [f"{idx:0{width}d}" for idx in range(a, b + 1)]

    m3, m4 = re.match(r"^(\d+)([A-Z]+)$", s), re.match(r"^(\d+)([A-Z]+)$", e)
    if m3 and m4 and m3.group(1) == m4.group(1):     # 2A..2D
        prefix = m3.group(1)
        return [f"{prefix}{x}" for x in _alpha_range(m3.group(2), m4.group(2))]

    if re.match(r"^[A-Z]+$", s) and re.match(r"^[A-Z]+$", e):   # A..Z / A..AX
        return _alpha_range(s, e)

    return [s] if s == e else [s, e]                 # single / fallback


def is_prefixed_alpha(label: str) -> bool:
    """True for a numeric-prefixed alpha label like ``2A`` (the CMP second area)."""
    return bool(re.match(r"^\d+[A-Z]$", label, re.I))


def label_mode_for(xstart: str, xend: str, ystart: str, yend: str) -> str | None:
    """The area's label mode: ``prefixed_x`` / ``prefixed_y`` when a ``2A``-style
    range is on that axis, else ``None`` (rectarg's ``label_mode``)."""
    if is_prefixed_alpha(xstart) or is_prefixed_alpha(xend):
        return "prefixed_x"
    if is_prefixed_alpha(ystart) or is_prefixed_alpha(yend):
        return "prefixed_y"
    return None


def normalize_sid(sid: str) -> str:
    """Canonical form for matching ``.cht`` box names to ``.cie`` names:
    upper-cased, leading zeros stripped from the trailing number. So ``A01`` →
    ``A1``, ``GS01`` → ``GS1``, ``2A01`` → ``2A1``, ``001`` → ``1``."""
    up = str(sid or "").strip().upper()
    m = re.match(r"^(GS)0*(\d+)$", up)
    if m:
        return f"{m.group(1)}{int(m.group(2))}"
    m = re.match(r"^(\d+)([A-Z]+)0*(\d+)$", up)      # 2A01
    if m:
        return f"{m.group(1)}{m.group(2)}{int(m.group(3))}"
    m = re.match(r"^([A-Z]+)0*(\d+)$", up)           # A01 / AA1 / AX02
    if m:
        return f"{m.group(1)}{int(m.group(2))}"
    if re.match(r"^\d+$", up):
        return str(int(up))
    return up                                        # pure alpha / other


def expand_rectarg_cht(text: str) -> str:
    """Expand a rectarg **area-format** ``.cht`` (``Y A Z 1 19 …`` lines) into a
    ChromIQ **per-patch** ``.cht`` scanin accepts: one explicit ``X`` box per patch
    named via :func:`make_patch_label` (so ``2A1``/``GS``/alpha-first all come out
    right and match the ``.cie``), the real ``F`` fiducial line kept verbatim, and
    an ``XLIST``/``YLIST`` built from the patch column/row boundaries.

    Bypasses scanin's own area-line naming (which mis-orders class-``Y`` letters and
    breaks CMP) by giving every box an explicit, pre-normalised name."""
    F: list[float] | None = None
    shrink = 12.0
    areas: list[dict] = []
    expected: set[str] | None = None
    lines = text.splitlines()
    for k, line in enumerate(lines):
        p = line.split()
        if p[:1] == ["F"] and len(p) >= 11:
            F = [float(x) for x in p[3:11]]
        elif p[:1] in (["X"], ["Y"]) and len(p) >= 11:
            try:
                tx, ty, prx, pry = (float(v) for v in p[5:9])
            except ValueError:
                continue
            areas.append(dict(xs=p[1], xe=p[2], ys=p[3], ye=p[4],
                              tx=tx, ty=ty, prx=prx, pry=pry))
        elif p[:1] == ["BOX_SHRINK"] and len(p) > 1:
            try:
                shrink = float(p[1])
            except ValueError:
                pass
        elif p[:1] == ["EXPECTED"]:
            # Some targets (e.g. Hutchcolor) define a full grid but only print a
            # subset of patches; the EXPECTED list names the real ones. Keep only
            # those so we don't emit phantom boxes over empty grid positions.
            expected = set()
            for l2 in lines[k + 1:]:
                q = l2.split()
                if not q or not q[0][:1].isalnum():
                    break
                expected.add(normalize_sid(q[0]))
    if F is None:
        raise ValueError("rectarg .cht has no F (fiducial) line")

    boxes: list[tuple[str, float, float, float, float]] = []
    for a in areas:
        cols = generate_labels(a["xs"], a["xe"]) or ["_"]
        rows = generate_labels(a["ys"], a["ye"]) or ["_"]
        mode = label_mode_for(a["xs"], a["xe"], a["ys"], a["ye"])
        for i, col in enumerate(cols):
            for j, row in enumerate(rows):
                name = make_patch_label(row, col, mode)
                if expected is not None and normalize_sid(name) not in expected:
                    continue                       # empty grid position — skip
                boxes.append((name, a["tx"], a["ty"],
                              a["prx"] + i * a["tx"], a["pry"] + j * a["ty"]))

    xset = sorted({round(x, 3) for _, w, h, x, y in boxes}
                  | {round(x + w, 3) for _, w, h, x, y in boxes})
    yset = sorted({round(y, 3) for _, w, h, x, y in boxes}
                  | {round(y + h, 3) for _, w, h, x, y in boxes})
    pw, ph = xset[-1] - xset[0], yset[-1] - yset[0]

    out = ["# ChromIQ scanner/camera target — real F-line fiducials + per-patch",
           "# boxes named exactly as rectarg (Knut Georg Larsson): alpha-first,",
           "# 2A1 / GS / Excel-alpha, normalised so scanin matches the .cie.",
           f"BOXES {len(boxes)}",
           "  F _ _ " + " ".join(f"{v:g}" for v in F)]
    out += [f"  X {n} {n} _ _ {w:g} {h:g} {x:g} {y:g} 0 0"
            for n, w, h, x, y in boxes]
    out.append(f"BOX_SHRINK {shrink:g}")
    # Column 2 is the tick's strength RELATIVE TO THE STRONGEST TICK, which
    # ArgyllCMS's `doc/cht_format.html` says "will have a value 1.0" — not the
    # length of the edge. Every tick here spans the same page dimension, so the
    # normalised value is 1.0 for all of them.
    #
    # This wrote `ph` and `pw` — the page height and width — which is the fault
    # B8-05 spent a release finding: with an absolute length in that column,
    # scanrd's match term `llf = 1 - |rlen - len|` comes out around -384 per
    # tick and the recogniser is actively poisoned. It was excused here because
    # nothing calls this generator yet. "No caller" is the wrong reason to
    # leave a generator writing a number a hundred times too large; the eight
    # bundled files had no caller for this column either, right up until Auto
    # align became one.
    out.append(f"XLIST {len(xset)}")
    out += [f"  {x:g} 1.0 1.0" for x in xset]
    out.append(f"YLIST {len(yset)}")
    out += [f"  {y:g} 1.0 1.0" for y in yset]
    out.append("")
    return "\n".join(out)


def make_patch_label(rlabel: str, clabel: str, mode: str | None = None) -> str:
    """Combine a row + column label into a normalised patch name. The alphabetic
    label comes first (``A1``); ``prefixed_x``/``prefixed_y`` keep the ``2A1``
    order. Matches rectarg's ``make_patch_label``."""
    if rlabel in ("_", None):
        return normalize_sid(clabel)
    if clabel in ("_", None):
        return normalize_sid(rlabel)
    if mode == "prefixed_y":
        return normalize_sid(f"{rlabel}{clabel}")
    if mode == "prefixed_x":
        return normalize_sid(f"{clabel}{rlabel}")
    if rlabel[0].isalpha() and clabel[0].isdigit():
        return normalize_sid(f"{rlabel}{clabel}")
    if rlabel[0].isdigit() and clabel[0].isalpha():
        return normalize_sid(f"{clabel}{rlabel}")
    return normalize_sid(f"{rlabel}{clabel}")
