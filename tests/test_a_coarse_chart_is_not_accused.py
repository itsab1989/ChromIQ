"""A chart drawn at a coarse resolution must not be accused of a margin fault
that is smaller than one of its own pixels.

The margin check allows a shortfall of up to one device pixel, because a chart
is drawn on a raster and every edge of it rounds to a whole pixel — no margin
can be *realised*, or read back, more finely than 25.4/dpi mm (#167).

That allowance was capped once, at one pixel of 200 dpi (0.127 mm), to stop a
stray "Resolution: 72 dpi" in Create Chart Manual's saved defaults from widening
a safety check. The cap made a correct chart accuse itself: with nothing changed
but Resolution 200 -> 180, the factory preset
"A3Plus-616p-1page-Landscape-w10.0mm" reported "Top margin 33.9 mm is below the
34 mm minimum set for this chart" on a layout that lands exactly on its box.
Measured over the 119 built-ins with the cap in place: 2 false alarms at 180 dpi,
5 of 9 sampled at 120, 5 of 9 at 72; zero at any dpi without it.

The Resolution spin box offers 72-1200, so none of this is hard to reach.
"""
import pytest

from workflow.margin_inspector import MarginReport, check_violations

_MM_PER_INCH = 25.4

# Every dpi the false alarms were measured at, plus the two the built-ins use.
COARSE_DPI = [300.0, 200.0, 180.0, 150.0, 120.0, 100.0, 72.0]


def _report(top_mm: float, dpi: float) -> MarginReport:
    return MarginReport(
        left_mm=20.0, right_mm=20.0, top_mm=top_mm, bottom_mm=20.0,
        strip_width_mm=10.0, page_w_mm=329.0, page_h_mm=483.0,
        strip_length_mm=200.0, dpi=dpi,
    )


@pytest.mark.parametrize("dpi", COARSE_DPI)
def test_a_margin_short_by_less_than_one_of_its_own_pixels_is_not_a_fault(dpi):
    """The exact shape of the on-screen false alarm: a chart whose block edge
    rounded to the next pixel, judged against the margin it declares."""
    px_mm = _MM_PER_INCH / dpi
    # Just inside one pixel — the whole of the quantisation, minus a hair.
    report = _report(34.0 - px_mm * 0.99, dpi)
    assert check_violations(report, {"T": 34.0}) == [], (
        f"a {dpi:g} dpi chart was accused over "
        f"{px_mm * 0.99:.4f} mm, which is less than its own pixel ({px_mm:.4f} mm)"
    )


@pytest.mark.parametrize("dpi", COARSE_DPI)
def test_a_real_shortfall_is_still_reported_at_every_resolution(dpi):
    """The control. Loosening the allowance must not blind the check: a margin
    short by well over one pixel is still a fault at every resolution."""
    px_mm = _MM_PER_INCH / dpi
    report = _report(34.0 - px_mm * 3.0, dpi)
    found = check_violations(report, {"T": 34.0})
    assert [v.edge for v in found] == ["Top"], (
        f"a {dpi:g} dpi chart {px_mm * 3.0:.4f} mm short was not reported"
    )


def test_the_200_dpi_cap_is_what_this_guards_against():
    """Proof this file can see the failure it exists for.

    Re-impose the reverted cap and the 180 dpi case must break — otherwise the
    two tests above would pass just as happily with the bug back in place.
    """
    from workflow import margin_inspector as mi

    def capped(report):
        tol = 0.05
        dpi = float(getattr(report, "dpi", 0.0) or 0.0)
        if dpi > 0:
            tol = max(tol, min(_MM_PER_INCH / dpi, _MM_PER_INCH / 200.0))
        return tol

    original = mi._tolerance_mm
    mi._tolerance_mm = capped
    try:
        px_mm = _MM_PER_INCH / 180.0
        report = _report(34.0 - px_mm * 0.99, 180.0)
        assert check_violations(report, {"T": 34.0}), (
            "the mutation did not land — with the 200 dpi cap restored a "
            "180 dpi chart MUST be falsely accused, and this file would not "
            "have noticed the bug"
        )
    finally:
        mi._tolerance_mm = original

    # ...and with the real rule back, the same sheet is clean again.
    px_mm = _MM_PER_INCH / 180.0
    assert check_violations(_report(34.0 - px_mm * 0.99, 180.0), {"T": 34.0}) == []
