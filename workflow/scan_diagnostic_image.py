"""Is this "scan" actually one of ArgyllCMS's own diagnostic images?

`scanin -dipon` writes a picture *of a read*: the whole scan converted to
greyscale, with the original colour painted back over the pixels it sampled and
the patch names and box outlines drawn on top. It is the picture ChromIQ shows
in the Check Alignment window, and it lands in ``cache/`` as a ``.tif`` beside
the scan — so it is an easy file to pick again by mistake. Knut did exactly that
in his beta.7 session (chromiq.log, 15:30): he offered
``diagnosticReadLSTarget01.tif`` as the scan and the app accepted it without a
word, then reported **a failure that was not true** — "sample boxes sit on patch
edges, worst 73.80 %" — about a read that had been fine. The grid cannot line up
on a diagnostic: two thirds of it is grey, and the colour that is left has
already been clipped to the sample boxes of the *previous* read.

So the picture has to be recognised, and recognised from the pixels rather than
from the file name: Knut's file was made by his own ``scanin`` command and is
called nothing ChromIQ would ever write.

**The two signatures, measured** (AGENT-I, 2026-09-03, full resolution, no
subsampling — 3 diagnostics against 20 real scans and photographs):

| picture | % of pixels with R == G == B | % at the annotation colour |
|---|---|---|
| ChromIQ's own ``-dipon`` diagnostic | 60.44 | 3.3770 |
| Knut's ``-dipn`` Wolf Faust diagnostic | 66.18 | 0.7366 |
| Knut's ``-dipn`` LaserSoft diagnostic | 60.21 | 1.3596 |
| 20 real scans/photos (best-exposed → worst) | 0.01 – 45.25 | **0.0000** |

The neutral fraction alone is NOT enough — a JPEG at quality 12 reached 45.25 %,
and a greyscale scan reaches 100 % — so both signatures must hold. The
annotation colour is `scanrd.c`'s ``col = 0x00a0ff`` (`show_sbox`, ArgyllCMS
3.5.0), which reaches the file as RGB ``(254, 159, 0)``; the tolerance below
covers the ±1 the diagnostic writer's gamma step introduces, and no real scan
in the set put a single pixel inside it.

Recognising this is a WARNING, not a refusal. The harm is a false verdict, not
a bad profile, and a detector with a small measured sample should not be able to
lock anybody out of their own scan. See `FINDINGS.md` for the evidence behind
that choice.
"""
from __future__ import annotations

from dataclasses import dataclass

#: At least this fraction of the picture must be exactly neutral (R == G == B).
NEUTRAL_MIN = 0.40
#: …and at least this fraction must be Argyll's annotation colour.
MARKER_MIN = 0.0001          # 0.01 %; the three measured diagnostics: 0.7–3.4 %
#: `scanrd.c` show_sbox: ``col = 0x00a0ff``, written out as R=254 G=159 B=0.
MARKER_RGB = (254, 159, 0)
#: ±: the diagnostic writer's gamma step moves the value by one.
MARKER_TOL = 4
#: Never look at more than this many pixels — whole rows are kept, because the
#: outlines and glyphs are one pixel wide and a subsample across x would lose
#: them.
MAX_PIXELS = 25_000_000


@dataclass(frozen=True)
class DiagnosticVerdict:
    """What the two measurements said, so a caller can log the evidence."""

    is_diagnostic: bool
    neutral_fraction: float
    marker_fraction: float


def looks_like_a_scanin_diagnostic(rgb) -> DiagnosticVerdict:
    """Judge an ``(h, w, 3)`` uint8 array. Never raises on a shape it cannot
    read — an unreadable picture is simply not a diagnostic."""
    import numpy as np

    a = np.asarray(rgb)
    if a.ndim != 3 or a.shape[2] < 3 or a.size == 0:
        return DiagnosticVerdict(False, 0.0, 0.0)
    step = 1
    while (a.shape[0] // step) * a.shape[1] > MAX_PIXELS:
        step += 1
    a = a[::step, :, :3].astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    neutral = float(np.mean((r == g) & (g == b)))
    mr, mg, mb = MARKER_RGB
    marker = float(np.mean((np.abs(r - mr) <= MARKER_TOL)
                           & (np.abs(g - mg) <= MARKER_TOL)
                           & (np.abs(b - mb) <= MARKER_TOL)))
    return DiagnosticVerdict(neutral >= NEUTRAL_MIN and marker >= MARKER_MIN,
                             neutral, marker)


def verdict_for_qimage(img) -> "DiagnosticVerdict | None":
    """The same judgement on the QImage the window already decoded for its
    preview, so nothing is read from disk twice. ``None`` when there is no
    usable image (a null QImage, or numpy/Qt not answering)."""
    try:
        import numpy as np
        from PyQt6.QtGui import QImage
    except Exception:                              # noqa: BLE001
        return None
    if img is None or img.isNull():
        return None
    try:
        conv = img.convertToFormat(QImage.Format.Format_RGB888)
        w, h, stride = conv.width(), conv.height(), conv.bytesPerLine()
        buf = conv.constBits()
        buf.setsize(stride * h)
        # bytesPerLine is padded to a 4-byte boundary; take the real width back
        # out of each row rather than reshaping across the padding.
        arr = np.frombuffer(memoryview(buf), dtype=np.uint8)
        arr = arr.reshape(h, stride)[:, : w * 3].reshape(h, w, 3)
    except Exception:                              # noqa: BLE001
        return None
    return looks_like_a_scanin_diagnostic(arr)
