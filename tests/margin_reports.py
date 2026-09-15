"""A "Measured from Preview" report for a recipe, for the notice tests.

Knut's ruling of 2026-09-15 (#182, comment 5679470670) makes every
patch-area notice on the "Measured from Preview" frame a measurement of the
sheet in the preview rather than a prediction from the boxes:

    "the calculations should use the Measured from Preview numbers in the
     calculations if text fit ... they are only usable after the Measured from
     Preview margin values have been completed (after a Generate Chart has been
     performed)."

So `TabChart._engine_text_notes` takes a :class:`~workflow.margin_inspector.
MarginReport` and says nothing about the four sides without one. The tests that
drive it with a stand-in tab used to pass none, because the arithmetic was
predicted from the recipe; they now have to say what the sheet measures.

:func:`report_for` is the honest default for a rectangular chart on a full
page, where the patch area really does land on the margins the geometry
resolved, and every edge can be overridden when a test is about a sheet where
it does not. **THE BOTTOM IS THE ONE THAT NEEDS OVERRIDING MOST OFTEN**, and
that is the whole of Knut's case: `raster._furniture_reserves_mm` holds the
sheet-text band back BELOW the bottom margin, and a flat-top honeycomb's last
row hangs below the grid box on top of that, so on his own chart the patches
stop at 15.82 mm against a 13.0 mm box.
"""
from __future__ import annotations

from workflow.margin_inspector import MarginReport


def report_for(r, *, left_mm=None, right_mm=None, top_mm=None,
               bottom_mm=None, dpi=None) -> MarginReport:
    """The report the frame would show for a full-page sheet laid out from *r*.

    The four edges default to the margins `instruments.geom_from_build_kwargs`
    resolves, which is where the patch area lands on a rectangular chart that
    fills its page. Pass any of them to describe a sheet where it does not.
    """
    from workflow.layout_engine import instruments, papers
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    w, h = papers.dimensions_mm(str(r.paper))
    left = float(g.margin_l if left_mm is None else left_mm)
    right = float(g.margin_r if right_mm is None else right_mm)
    top = float(g.margin_t if top_mm is None else top_mm)
    bottom = float(g.margin_b if bottom_mm is None else bottom_mm)
    return MarginReport(
        left_mm=left, right_mm=right, top_mm=top, bottom_mm=bottom,
        strip_width_mm=None, page_w_mm=float(w), page_h_mm=float(h),
        strip_length_mm=float(h) - top - bottom,
        dpi=float(dpi) if dpi is not None else float(getattr(r, "dpi", 300)
                                                     or 300),
    )
