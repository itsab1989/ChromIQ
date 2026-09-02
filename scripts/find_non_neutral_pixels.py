"""Find every pixel in the Neutral appearance that is not a grey, and name the
widget that painted it.

A neutral colour has R = G = B. Anything else is a hue that survived the theme,
and in a theme whose whole point is "no colour anywhere in the interface" each
one is a bug with an address. Run it against a live window and it walks the
widget tree, grabs each widget on its own, and reports the offenders bottom-up
so the innermost widget that actually painted a pixel is the one named — not the
panel it happens to sit in.

    from scripts.find_non_neutral_pixels import scan_widget
    for hit in scan_widget(win):
        print(hit)

`tolerance` is the largest channel spread still called grey. Anti-aliased text
and rounded corners blend two greys and can land a point or two apart, so 0 is
too strict for a real window; 6 is measured to keep sub-pixel artefacts out
while still catching a desaturated tint.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Hit:
    widget: str                 # class name
    object_name: str            # objectName(), when it has one
    path: str                   # ancestry, outermost first
    colours: list = field(default_factory=list)   # (hex, count), worst first
    pixels: int = 0             # how many non-grey pixels in this widget alone
    area: int = 0               # its own area, so a share can be judged

    @property
    def share(self) -> float:
        return (self.pixels / self.area * 100.0) if self.area else 0.0

    def __str__(self) -> str:
        top = ", ".join(f"{c} ×{n}" for c, n in self.colours[:4])
        name = f"#{self.object_name}" if self.object_name else ""
        return (f"{self.widget}{name}: {self.pixels} px ({self.share:.1f}% of it) "
                f"-- {top}\n    in {self.path}")


def _worst(img, tolerance: int) -> tuple:
    """Non-grey pixel count and the commonest offending colours in one image."""
    from collections import Counter
    counts: Counter = Counter()
    w, h = img.width(), img.height()
    if w <= 0 or h <= 0:
        return 0, []
    for y in range(h):
        for x in range(w):
            c = img.pixelColor(x, y)
            if c.alpha() < 8:
                continue
            r, g, b = c.red(), c.green(), c.blue()
            if max(r, g, b) - min(r, g, b) > tolerance:
                counts[c.name()] += 1
    return sum(counts.values()), counts.most_common(8)


def scan_widget(root, tolerance: int = 6, min_pixels: int = 12,
                skip: tuple = ()) -> list:
    """Every visible descendant of *root* that paints a non-grey pixel.

    `skip` names widget CLASSES that are allowed their colour — the TIFF
    preview, the 3D gamut viewer and the measured-versus-expected overlay show
    the user's own colours and are excluded by the design, not by oversight.
    Pass them by class name so the exclusion is visible in the call rather than
    hidden in here.

    **THE SKIP LIST USED TO DO NOTHING, and it took a loaded chart to notice.**
    The exclusion was applied inside the loop below — but the loop runs
    INNERMOST FIRST, and a `TiffPreview` paints its chart into a plain `QLabel`
    child. That label was reached, measured and reported several iterations
    before its skipped parent's turn came round to claim it. Every sweep that
    passed `skip=("TiffPreview", …)` against an app with no project open saw
    nothing, because the preview was empty; open a chart and the census reports
    the user's own patches as a theme defect. The exclusion is resolved by
    ANCESTRY, and up front, so a skipped widget's children are out of the sample
    before the first measurement is taken.

    **AND OUT OF THEIR ANCESTORS' GRABS TOO.** Skipping the preview does not
    help if the window that CONTAINS it is grabbed whole a moment later — the
    same patches come back attributed to `MainWindow`. So a skipped widget's
    rectangle is painted out of every ancestor's grab before it is counted. The
    exclusion is then worth something with a project open, which is the only
    configuration where it matters; with an empty app the two behave alike, and
    an empty app is what every sweep so far measured.
    """
    from PyQt6.QtCore import QPoint
    from PyQt6.QtGui import QColor, QPainter
    from PyQt6.QtWidgets import QWidget

    hits: list = []
    widgets = [w for w in root.findChildren(QWidget)
               if w.isVisible() and w.width() > 0 and w.height() > 0]
    widgets.append(root)

    claimed: set = set()
    skipped: list = []
    if skip:
        for w in widgets:
            if type(w).__name__ in skip:
                claimed.add(id(w))
                claimed.update(id(c) for c in w.findChildren(QWidget))
                skipped.append(w)

    def _grab(w):
        """*w*'s pixels, with any skipped subtree inside it painted out."""
        pm = w.grab()
        blanks = [s for s in skipped if s is not w and _is_inside(s, w)]
        if blanks:
            p = QPainter(pm)
            for s in blanks:
                tl = w.mapFromGlobal(s.mapToGlobal(QPoint(0, 0)))
                p.fillRect(tl.x(), tl.y(), s.width(), s.height(),
                           QColor(128, 128, 128))
            p.end()
        return pm.toImage()

    def _is_inside(child, ancestor) -> bool:
        node = child.parentWidget()
        while node is not None:
            if node is ancestor:
                return True
            node = node.parentWidget()
        return False

    # Innermost first, so the widget that actually painted a pixel is named
    # before the panel it sits inside.
    widgets.sort(key=lambda w: w.width() * w.height())

    for w in widgets:
        if id(w) in claimed:
            continue
        img = _grab(w)
        n, colours = _worst(img, tolerance)
        if n < min_pixels:
            continue
        chain, node = [], w
        while node is not None:
            nm = type(node).__name__
            if node.objectName():
                nm += f"#{node.objectName()}"
            chain.append(nm)
            node = node.parentWidget()
        hits.append(Hit(widget=type(w).__name__, object_name=w.objectName(),
                        path=" < ".join(chain), colours=colours,
                        pixels=n, area=w.width() * w.height()))
        claimed.update(id(c) for c in w.findChildren(QWidget))
        claimed.add(id(w))
    hits.sort(key=lambda h: h.pixels, reverse=True)
    return hits
