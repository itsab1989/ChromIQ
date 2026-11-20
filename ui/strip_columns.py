"""Strip columns of a chart that stand apart on the page (4.3.52).

jctay, thread 17845 post 150417 (ChromIQ 4.3.49, i1Pro 3): "the progress arrow
moves very slowly behind the active strip". Measured 2026-11-20 on his sheet
(the patch-length test sheet 2, a `.ti2` and TIFF made outside ChromIQ, with
"START" and a scale bar in the top left margin and the strip letters at the
BOTTOM): the label-band detector in `tab_measure._detect_uniform_stripe_rects`
took "START" for the strip labels and the scale bar under it for the patch
block, and split that 95 px wide column into nine. Every strip's marker landed
inside strip A, about 10 px further right per strip.

This module finds the strips from the page itself when they stand apart: the
columns of ink separated by white, the ``n`` widest of them, of about one
width and one pitch. It returns nothing when the page does not show exactly
that, and the caller keeps what it had. It reads only the TIFF; the `.ti2`
gives ``n``.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QRect

log = logging.getLogger(__name__)

WHITE = 240          # an 8-bit grey below this is ink (as the uniform detector)
ANALYSIS_W = 1000    # analysed at this width at most (as the uniform detector)


def separated_strip_rects(tiff_path: Path, n_strips: int) -> "list[QRect]":
    """One rect per strip, in image pixels, left to right, top of each rect =
    the top of that strip's ink; or [] when the page does not show exactly
    ``n_strips`` separate columns of similar width at an even pitch."""
    if n_strips < 2:
        return []
    try:
        from PIL import Image
        try:
            img = Image.open(tiff_path).convert("L")
        except Exception:      # noqa: BLE001 - a multi-channel TIFF
            from ui.tiff_preview import load_tiff_as_rgb, _find_sidecar_channels
            img = load_tiff_as_rgb(
                tiff_path, ink_channels=_find_sidecar_channels(tiff_path)).convert("L")
        ow, oh = img.size
        scale = ANALYSIS_W / ow if ow > ANALYSIS_W else 1.0
        aw, ah = max(1, int(ow * scale)), max(1, int(oh * scale))
        import numpy as np
        ink = np.asarray(img.resize((aw, ah), Image.BOX), dtype=np.uint8) < WHITE
        col = ink.sum(axis=0)
        peak = int(col.max()) if col.size else 0
        if peak <= 0:
            return []
        thr = peak * 0.20
        runs: "list[list[int]]" = []
        for x in np.flatnonzero(col > thr).tolist():
            if runs and x - runs[-1][1] <= 2:   # anti-alias dropouts
                runs[-1][1] = x
            else:
                runs.append([x, x])
        if len(runs) < n_strips:
            return []
        widths = [r[1] - r[0] + 1 for r in runs]
        widest = max(widths)
        cands = [r for r, w in zip(runs, widths) if w >= 0.6 * widest]
        if len(cands) != n_strips:
            return []
        centres = [(r[0] + r[1]) / 2 for r in cands]
        pitches = [b - a for a, b in zip(centres, centres[1:])]
        if min(pitches) <= 0 or max(pitches) > 1.3 * min(pitches):
            return []
        if any((r[1] - r[0] + 1) >= min(pitches) for r in cands):
            return []      # the columns touch: not separated strips
        inv = 1.0 / scale
        rects: "list[QRect]" = []
        for x0, x1 in cands:
            need = max(1, int((x1 - x0 + 1) * 0.3))
            rows = np.flatnonzero(ink[:, x0:x1 + 1].sum(axis=1) >= need).tolist()
            if not rows:
                return []
            # the strip is the longest run of ink down the column, white gaps
            # of a few percent of the page bridged (white spacers); letters
            # or notes above or below it, past a larger gap, are not the strip
            gap_max = max(4, ah * 3 // 100)
            segs = [[rows[0], rows[0]]]
            for y in rows[1:]:
                if y - segs[-1][1] > gap_max:
                    segs.append([y, y])
                else:
                    segs[-1][1] = y
            top, bot = max(segs, key=lambda sg: sg[1] - sg[0])
            X0, X1 = int(x0 * inv), int((x1 + 1) * inv)
            Y0, Y1 = int(top * inv), min(oh, int((bot + 1) * inv))
            rects.append(QRect(X0, Y0, max(1, X1 - X0), max(1, Y1 - Y0)))
        # one top for all: strips start together on a sheet, and a strip
        # whose first patches are near white must not have its marker
        # hung halfway down (Quarter.ti2 in the sweep of 2026-11-20)
        top_all = min(r.y() for r in rects)
        rects = [QRect(r.x(), top_all, r.width(), r.bottom() + 1 - top_all)
                 for r in rects]
        log.info("Separated strip columns: %d strips, x=%d-%d (image px)",
                 n_strips, rects[0].x(), rects[-1].right())
        return rects
    except Exception as exc:   # noqa: BLE001 - the caller keeps what it had
        log.warning("Separated strip detection failed: %s", exc)
        return []


def uniform_agrees(uniform: "list[QRect]", separated: "list[QRect]") -> bool:
    """True when every uniform strip's centre lies inside the same strip's
    separated column: the two agree, and the uniform result is kept as it
    always was."""
    if len(uniform) != len(separated):
        return False
    for u, s in zip(uniform, separated):
        cx = u.x() + u.width() / 2
        if not (s.x() <= cx <= s.x() + s.width()):
            return False
    return True
