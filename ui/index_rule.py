"""The Index rule — the five-cell step rule that carries tab identity in Neutral.

**One component, two problems.** The approved handoff (design draft 1, "Index")
answers two questions with the same part:

* *How does a colourless theme say which tab you are in?* Not with a shade —
  five greys that read side by side stop reading when you see one at a time,
  which is the normal case. With a **five-cell rule filled up to the current
  step**.
* *What replaces the spectrum bar?* The same rule. The bar was five hues in a
  row; this is five cells in a row, and it says something the bar never did.

From the handoff, verbatim:

    One accent value, ``ACTION #101010``, used for every accent surface. Tab
    identity is carried by a five-cell rule filled up to the current step
    rather than by a shade. Rule geometry: 5 cells, 3px tall, 2–3px gaps,
    spanning whatever width the site needs. Cells ``1..n`` filled in ACTION;
    cells ``n+1..5`` in BORDER_HI at 28% opacity. Reads as progress through the
    run as well as identity. **This same part replaces the spectrum bar** — one
    component, two problems.

So the geometry below is not a choice made here, and neither are the two
colours. What *is* decided here is how a site with more height than 3 px places
the rule (centred in its band) and what a site with no step means by "step"
(:data:`ALL` — every cell filled, the mark rather than a readout: the splash and
a dialog with no workflow position).

WHERE IT IS USED. Every screen site the spectrum bar occupied:

* ``ui/masthead_header.py`` — the 6 px masthead stripe
* ``ui/spectrum_tab_bar.py`` — the active tab's top rule (and the pink tint goes)
* ``ui/tab_header.py`` — :class:`~ui.tab_header.SpectrumStripe`, the dialog
  masthead rule, and the 22×2 accent stroke beside a step eyebrow
* ``ui/spectrum_progress.py`` — the Build Profile ramp, which was already five
  segments and is now five cells
* ``ui/splash.py`` — the splash bar

**Three spectrum sites are NOT here and must stay coloured**: ``ui/pdf_layout.py``,
``workflow/tiff_metadata.py`` and ``workflow/layout_engine/raster.py``. Those are
ink on paper and in generated documents, which the screen theme has no
jurisdiction over.

ONLY NEUTRAL. :func:`use_index_rule` is the single question a paint site asks;
in Light and Dark it answers ``False`` and every site paints exactly what it
always painted. That is what keeps the two shipped appearances byte-identical.
"""
from __future__ import annotations

from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ui import neutral_styles

#: Cells in the rule. Five, because there are five tabs and five steps in the
#: run — the rule counts the workflow, not the pixels available.
CELLS = 5
#: Cell height, px. The handoff's "3px tall".
CELL_H = 3
#: Gap between cells, px. The handoff allows 2–3; 3 is taken so the gap is
#: never thinner than the cell is tall and the rule cannot read as a solid bar
#: at a small width.
GAP = 3
#: Opacity of an unreached cell, as the handoff states it.
EMPTY_ALPHA = 0.28

#: "No step here" — every cell filled. A splash and a dialog masthead have no
#: position in the run; they wear the mark, not a readout.
ALL = CELLS


def use_index_rule(mode: "str | None" = None) -> bool:
    """Does *mode* paint the Index rule instead of the spectrum bar?

    THE ONE QUESTION EVERY PAINT SITE ASKS, and it is asked by name rather than
    by measuring a background: at L* 90 the Neutral masthead is "light" to every
    lightness threshold the app ever used. ``mode`` may be omitted, in which
    case the live application appearance is used — that is what a widget that
    was never told its appearance has to fall back on.
    """
    from ui.theme import APPEARANCE_NEUTRAL, accept_mode, active_mode
    if mode is None:
        return active_mode() == APPEARANCE_NEUTRAL
    return accept_mode(mode, default=active_mode()) == APPEARANCE_NEUTRAL


def rule_colours() -> "tuple[QColor, QColor]":
    """``(filled, empty)`` — ACTION, and BORDER_HI at 28 %.

    Both are darker than every ground in the theme, which is the handoff's
    rule 1: nothing is ever lighter than what it sits on.
    """
    filled = QColor(neutral_styles.NM_ACTION)
    empty = QColor(neutral_styles.NM_BORDER_HI)
    empty.setAlpha(round(EMPTY_ALPHA * 255))
    return filled, empty


def paint_index_rule(p: QPainter, x: int, y: int, w: int, h: int,
                     step: int = ALL, *, cells: int = CELLS) -> None:
    """Paint the rule into the band ``(x, y, w, h)``.

    The band may be taller than :data:`CELL_H` — the masthead's stripe is 6 px
    and the splash's is 9 — in which case the 3 px rule is centred in it. It is
    never stretched: the rule has one thickness everywhere in the app, so the
    masthead and the tab bar show the same part and not two sizes of it.

    ``step`` is how many cells are filled, 0..``cells``. Anything outside that
    is clamped rather than raising: this runs inside ``paintEvent``, where an
    exception is a repaint loop.
    """
    if w <= 0 or h <= 0 or cells <= 0:
        return
    step = max(0, min(cells, int(step)))
    filled, empty = rule_colours()
    ch = min(CELL_H, h)
    cy = y + (h - ch) // 2
    span = w - GAP * (cells - 1)
    if span < cells:                      # too narrow to show gaps: one solid rule
        p.fillRect(x, cy, w, ch, filled if step >= cells else empty)
        return
    prev_end = 0
    for i in range(cells):
        # Positions are derived from the full width so the last cell ends
        # exactly on the right edge — rounding each cell to the same integer
        # width leaves a ragged tail on most window widths.
        end = round(span * (i + 1) / cells)
        cx = x + prev_end + i * GAP
        cw = end - prev_end
        prev_end = end
        p.fillRect(cx, cy, cw, ch, filled if i < step else empty)


class IndexRule(QWidget):
    """The rule as a widget, for the sites that had a widget before.

    :class:`ui.tab_header.SpectrumStripe` is one; anything that wants a rule in
    a layout is another. Sites that already own a ``paintEvent`` call
    :func:`paint_index_rule` directly instead of nesting a widget in it.
    """

    def __init__(self, parent: "QWidget | None" = None, *,
                 step: int = ALL, height: int = CELL_H) -> None:
        super().__init__(parent)
        self._step = step
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_step(self, step: int) -> None:
        if step != self._step:
            self._step = step
            self.update()

    def step(self) -> int:
        return self._step

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        paint_index_rule(p, 0, 0, self.width(), self.height(), self._step)
        p.end()
