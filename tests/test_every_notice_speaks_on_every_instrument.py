"""Every text-overlap notice is decided by one law on every instrument.

Knut, #182, 2026-09-18, testing beta 21 with his own 648-patch CR30 honeycomb:

    "Using this chart, there is a warning message for overlapping strip labels
     for the CR30, but if you change instrument to SpectroScan, there is no
     warning. All the warnings for the label overlapping, row indicator
     overlapping, or clip-border text overlapping, or bottom text overlapping,
     they should all also happen for the SpectroScan instrument. Test for that
     to make sure it is implemented and verified."

**WHAT HIS CHART ACTUALLY MEASURES, DRIVEN ON SCREEN** (proof folder
`~/Desktop/ChromIQ-beta22-proof/knut-report-and-warnings/`): his recipe loaded
into the real Manual panel and read back field for field, his `test.ti1` armed
so Generate lays out his 648 patches, built once as CR30 and once as
SpectroScan. **Both warn**, and the only difference is the number in the
sentence: the CR30's letters reach 13.5 mm down the page and the SpectroScan's
reach 11.0, because the two instruments carry a different strip-label text
height (`Geom.txhisl`, 7.0 mm against 5.0). So at margins between those two
reaches the CR30 warns and the SpectroScan does not, which is his sentence
exactly -- and on the SpectroScan sheet there really is clear paper between the
letters and the first patch row, measured off the rendered TIFF at 200 dpi
(letters end 12.95 mm, patches begin 13.46 mm).

That is a difference in the SHEET, not in the law, and this file is what keeps
it that way. Two things are pinned:

1. **Structural.** Each of the four notices can be reached on the SpectroScan,
   with a recipe that differs from the one that reaches it on the CR30 only in
   the instrument. A notice that no state can reach on one instrument is the
   fault Knut is describing.
2. **Source.** Neither the notice block nor the law it calls may key on an
   instrument. Equality of behaviour today is not the same as a law that cannot
   grow a special case tomorrow, and this project has shipped "a guard on one
   door and not the identical door beside it" more than once.

**THE REPORT THESE TESTS ARE JUDGED AGAINST IS THE ENGINE'S OWN**, through
`margin_reports.engine_report_for`, and that is not a detail. The first version
of this sweep used `report_for`, which hands back the margins the geometry
resolved; on Knut's honeycomb it says the patch area starts at the 12.0 mm in
the box while the sheet measures **15.43**, and the sweep built on it reported
an instrument difference the app does not have. A fixture too tidy to contain
the fault agrees with the code.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication                       # noqa: E402

from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402

#: Every instrument the layout engine can build for.
INSTRUMENTS = ("i1", "p3", "CM", "41", "51", "SS", "CR30")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _base(key: str, hexa: bool = False) -> LayoutRecipe:
    """A roomy A4 chart on *key* with nothing colliding."""
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = key, "A4", "area_first"
    r.dpi = 200
    r.hflag = hexa
    r.clip_border = False
    r.clip_content_mode = "off"
    r.show_strip_indicators = True
    r.show_row_indicators = None
    r.margin_top = r.margin_right = r.margin_bottom = r.margin_left = 20.0
    r.text_edge_top_mm = r.text_edge_mm = r.text_edge_clip_mm = 4.0
    r.chart_text = ""
    r.stamp_command = False
    r.helper_markers = False
    return r


def _knuts_chart() -> LayoutRecipe:
    """His own 648-patch CR30 honeycomb, from the `meta.json` in the zip.

    Only the fields that decide where the patches land are carried here; the
    whole recipe is in the proof folder and was loaded into the real panel and
    read back field for field before anything in this file was written.
    """
    r = _base("CR30", hexa=True)
    r.dpi = 200
    r.pscale, r.sscale = 0.95, 0.6
    r.border = 10.0
    r.spacer_on, r.spacer_mode = True, "colored"
    r.patch_area_align = "center-left"
    r.area_method, r.area_cols, r.area_rows = "by_width", 15, 18
    r.area_min_patch_mm, r.layout_explicit = 13.5, True
    r.margin_top = r.margin_bottom = 5.0
    r.margin_left = r.margin_right = 7.0
    r.text_edge_top_mm = r.text_edge_mm = 4.0
    r.text_edge_clip_mm = 2.0
    r.helper_markers = True
    r.helper_marker_edge_mm = r.helper_marker_len_mm = 2.0
    r.helper_marker_per_patch = 5
    r.helper_markers_top_bottom, r.helper_markers_sides = True, False
    r.clip_border, r.clip_border_width_mm = True, 26.0
    r.clip_side, r.clip_content_mode = "left", "off"
    r.indicator_font = "JetBrains Mono"
    return r


def _notices(r, *, notes: str = "", stamp: bool = False, npat: int = 648):
    """The red notices this recipe earns, off the engine's own patch bounds."""
    from tests.margin_reports import engine_report_for
    from tests.test_text_is_never_dropped_on_any_side import _Tab
    from ui.tabs.tab_chart import TabChart
    rep = engine_report_for(r, npat)
    if rep is None:
        return None
    return TabChart._engine_text_notes(_Tab(r, notes, stamp), rep)[1]


def _kind(s: str) -> str:
    if "strip letters" in s:
        return "STRIP"
    if "row indicators" in s:
        return "ROW"
    if "sheet text along the bottom" in s:
        return "BOTTOM"
    if "chart notes" in s or "settings stamp" in s:
        return "NOTE"
    if "clip border content" in s:
        return "CLIP"
    if "clip border text is too long" in s:
        return "CLIPLEN"
    return "OTHER"


# --- the four provocations, one per notice Knut names ----------------------
#
# Each returns a recipe that puts that one piece of text on the patches. The
# instrument is the ONLY thing that varies between the runs of a provocation,
# which is what makes a silence attributable to the instrument.

def _provoke_strip(key: str) -> LayoutRecipe:
    r = _base(key)
    r.margin_top, r.text_edge_top_mm = 1.0, 2.0
    return r


def _provoke_row(key: str) -> LayoutRecipe:
    r = _base(key)
    r.show_row_indicators = True
    r.margin_left, r.text_edge_clip_mm = 1.0, 2.0
    return r


def _provoke_bottom(key: str) -> LayoutRecipe:
    r = _base(key)
    r.margin_bottom = 1.0
    r.chart_text = ("A long line of sheet text that has to go somewhere "
                    "on this page indeed")
    r.chart_text_size_mm = 10.0 * 25.4 / 72.0
    return r


def _provoke_note(key: str) -> LayoutRecipe:
    r = _base(key)
    r.margin_right = 1.0
    return r


PROVOCATIONS = {
    "STRIP": (_provoke_strip, {}),
    "ROW": (_provoke_row, {}),
    "BOTTOM": (_provoke_bottom, {}),
    "NOTE": (_provoke_note, {"notes": "Run 1 chart notes for this sheet"}),
}


@pytest.mark.parametrize("notice", sorted(PROVOCATIONS))
def test_the_spectroscan_earns_every_notice_the_cr30_earns(notice, qapp):
    """Knut's own sentence, as a predicate.

    The provocation is written once and run on both instruments, so the recipes
    differ in the instrument and in nothing else. A notice the CR30 earns and
    the SpectroScan cannot is the fault he reported.
    """
    make, kw = PROVOCATIONS[notice]
    seen = {}
    for key in ("CR30", "SS"):
        got = _notices(make(key), **kw)
        assert got is not None, f"{key}: the engine laid out no page to judge"
        seen[key] = {_kind(s) for s in got}
    assert notice in seen["CR30"], (
        f"the provocation for {notice} no longer reaches it on the CR30, so "
        f"this test proves nothing about the SpectroScan; it earned "
        f"{sorted(seen['CR30']) or ['nothing']}")
    assert notice in seen["SS"], (
        f"the CR30 earns {notice} on this sheet and the SpectroScan earns "
        f"{sorted(seen['SS']) or ['nothing']}. Knut, 2026-09-18: \"they should "
        f"all also happen for the SpectroScan instrument\"")


@pytest.mark.parametrize("notice", sorted(PROVOCATIONS))
def test_no_instrument_is_left_out_of_a_notice(notice, qapp):
    """…and the SpectroScan is not a special case of its own either.

    Knut names one instrument because that is the one he tested. The rule he is
    stating is that the notice belongs to the TEXT and the sheet, so it is
    asked of every instrument the engine builds for. An instrument whose sheet
    genuinely has room is allowed to be silent, so the provocation is checked
    for having reached the notice on that instrument's own geometry: the
    assertion is on instruments whose text really is over the patches.
    """
    make, kw = PROVOCATIONS[notice]
    from tests.margin_reports import engine_report_for
    silent = []
    for key in INSTRUMENTS:
        r = make(key)
        rep = engine_report_for(r, 648)
        if rep is None:
            continue
        # …only where the sheet really fills the page. A DTP51 A4 chart of this
        # many patches stops 84 mm above the bottom edge, so a bottom-text
        # notice there would be a warning about paper nobody is using.
        if notice == "BOTTOM" and rep.bottom_mm > 10.0:
            continue
        if notice == "NOTE" and rep.right_mm > 10.0:
            continue
        got = _notices(r, **kw)
        if got is not None and notice not in {_kind(s) for s in got}:
            silent.append((key, round(rep.top_mm, 2), round(rep.bottom_mm, 2),
                           round(rep.left_mm, 2), round(rep.right_mm, 2)))
    assert not silent, (
        f"{notice} is silent on {[s[0] for s in silent]} while the same sheet "
        f"earns it elsewhere: {silent}")


def test_the_notice_block_keys_on_no_instrument():
    """The law may not grow a special case for one device.

    Equality of behaviour today is not a law. `_engine_text_notes` asks the
    GEOMETRY for every number it uses, and the geometry is where an
    instrument's own dimensions belong; the moment the notice block or the fit
    law names a device key, the four notices stop being one law.
    """
    from ui.tabs import tab_chart
    from workflow import text_edge_fit

    keys = ('"i1"', "'i1'", '"p3"', "'p3'", '"CM"', "'CM'", '"SS"', "'SS'",
            '"CR30"', "'CR30'", '"41"', '"51"')
    src = inspect.getsource(tab_chart.TabChart._engine_text_notes)
    # the comments quote instruments by name constantly; only CODE counts.
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    for k in keys:
        assert k not in code, (
            f"`_engine_text_notes` compares against the instrument key {k}. "
            f"The four notices are one law for every instrument (Knut, "
            f"2026-09-18); an instrument's own dimensions belong in "
            f"`layout_engine/instruments.py`, which the notices read through "
            f"`Geom`")
    law = inspect.getsource(text_edge_fit)
    law_code = "\n".join(ln for ln in law.splitlines()
                         if not ln.lstrip().startswith("#")
                         and not ln.lstrip().startswith('"'))
    for k in keys:
        assert k not in law_code, (
            f"`workflow/text_edge_fit.py` names the instrument key {k}; the "
            f"fit law is instrument-agnostic by design")


def test_the_engine_report_is_not_the_margin_box(qapp):
    """The fixture that made the first sweep lie is pinned as wrong.

    On Knut's own honeycomb the top margin BOX reads 12.0 mm and the sheet
    measures 15.43. A sweep judged against the box found an instrument
    difference the app does not have, so this pins that the two really are
    different numbers and that `engine_report_for` returns the second one.
    """
    from tests.margin_reports import engine_report_for, report_for
    r = _knuts_chart()
    r.margin_top = 12.0
    boxed, measured = report_for(r), engine_report_for(r, 648)
    assert measured is not None
    assert measured.top_mm > boxed.top_mm + 1.0, (
        f"a turned honeycomb's first row starts below the top margin box; the "
        f"box says {boxed.top_mm:.2f} mm and the sheet {measured.top_mm:.2f}")
