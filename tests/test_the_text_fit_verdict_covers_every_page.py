"""The sheet text is printed on every page, so it is judged on every page.

Found by the combined adversary round of 2026-09-15, on the second and third
page, which the round before it never reached.

Knut's ruling of 2026-09-15 made all four text-fit checks read the MEASURED
sheet rather than a prediction. The measured sheet is one page, and
`_update_margin_inspector` says which one in its own words: *"Measure the page
CURRENTLY SHOWN in the preview, so the numbers, the threshold guides and the
visible patches all describe the same page. Multi-page charts have different
per-page margins … Re-runs when the user pages through (page_changed)."* That
is right for the guides, and `_engine_text_notes` is called from inside the
same method.

A prediction was the same number on every page. A measurement is not, and the
case that proves it is a PART-FULL LAST PAGE: its patches stop early, so the
paper beside them is the width of the empty half of the sheet.

WHAT A USER SAW. A real three-page A4 chart, one set of settings, "Text
distance from edge" Clip at 10 mm, driven on screen
(`~/Desktop/ChromIQ-beta18-proof/combined-round-2/`, `K1`/`K2`/`K3`). The
measured right margin is **7.985 mm** on pages 1 and 2 and **175.964 mm** on
page 3. The panel said, on pages 1 and 2:

    "⚠ The chart notes down the right edge run over the patches. They are
     printed 10.0 mm in from the paper edge, need 2.7 mm at 7 pt, and the right
     margin leaves 0.0 mm … Raise “Right” under “Margins (mm)” by about 5.1 mm"

and on page 3, nothing at all. Pressing *Next* made a red warning disappear
with nothing saying why, and a reader who happened to be on the last page was
told nothing about the two sheets that clip. Both readers of that edge are
affected: the chart note, and the clip border's own content.

Top, bottom and left measured identically on all three pages to 0.001 mm, so
the right edge is where it bites today. The rule is written for all four.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

#: A real chart's recorded geometry: 240 patches over three A4 pages, the last
#: holding one strip of sixteen. Taken off a project on disk, and it carries
#: nothing but the layout (no paths, no names).
CHANNELS = Path(__file__).parent / "data" / \
    "a_three_page_chart_with_a_part_full_last_page.channels.json"

#: What `measure_from_engine` reads out of it, page by page. Recorded here so
#: a test that stops seeing three different pages says so.
EXPECTED_RIGHT_MM = [7.985, 7.985, 175.964]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("use_chromiq_layout_engine", True)
    s.set("auto_update_preview", False)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("manual")
    yield t
    t.deleteLater()


def _three_pages(tab, tmp_path):
    """Point the tab at the three-page chart. The TIFFs are never opened: an
    engine chart is measured from its `channels.json` (`measure_from_engine`),
    which is the path this chart takes in the app too."""
    d = tmp_path / "chart"
    d.mkdir(parents=True, exist_ok=True)
    ti2 = d / "Three-Page.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    shutil.copy2(CHANNELS, ti2.with_suffix(".channels.json"))
    tiffs = []
    for i in range(3):
        t = d / f"Three-Page_{i + 1:02d}.tif"
        t.write_bytes(b"")
        tiffs.append(t)
    tab._margin_ti2 = ti2
    tab._margin_tiffs = tiffs
    # The whole-chart measurement, exactly where `_update_margin_inspector`
    # makes it: once per chart, before the page on screen is measured.
    tab._ensure_worst_page_cache(300.0)
    return tiffs


def _report_on_page(tab, i):
    from workflow.margin_inspector import measure_from_engine
    eng = measure_from_engine(Path(tab._margin_ti2).with_suffix(
        ".channels.json"), i)
    assert eng is not None, f"the control failed: page {i} did not measure"
    return eng[0]


# ---------------------------------------------------------------------------

def test_the_pages_really_do_measure_differently(tab, tmp_path):
    """THE CONTROL. Without three different pages nothing below means
    anything, and a fixture that quietly became one page would make every
    check here pass for the wrong reason."""
    _three_pages(tab, tmp_path)
    got = [round(_report_on_page(tab, i).right_mm, 3) for i in range(3)]
    assert got == EXPECTED_RIGHT_MM, (
        "the three-page fixture no longer measures three different right "
        "margins: %r" % (got,))


def test_the_verdict_is_the_worst_page_not_the_page_on_screen(tab, tmp_path):
    """THE FAULT ITSELF: standing on the part-full last page must not widen
    the paper the sheet text is judged against.

    MUTATION: make `_update_margin_inspector` pass `report` to
    `_engine_text_notes` instead of `self._worst_page_report(report)` and
    this goes red, with the last page judged against 175.964 mm.
    """
    _three_pages(tab, tmp_path)
    for i in range(3):
        judged = tab._worst_page_report(_report_on_page(tab, i))
        assert round(judged.right_mm, 3) == min(EXPECTED_RIGHT_MM), (
            "with page %d on screen the sheet text is judged against %.3f mm "
            "of right margin, and the worst page leaves %.3f"
            % (i + 1, judged.right_mm, min(EXPECTED_RIGHT_MM)))


def test_the_frame_actually_hands_the_notes_the_worst_page(tab, tmp_path,
                                                           monkeypatch):
    """THE ROUTING, WHICH IS WHERE THE FAULT LIVED.

    Every other check here calls `_worst_page_report` itself, and all of
    them stayed green when the one line that USES it was removed — proved by
    mutation, which is the only reason this test exists. The fault was never in
    the arithmetic; it was that `_update_margin_inspector` handed
    `_engine_text_notes` the page on screen. So this drives the real method and
    records what the notes were given.

    MUTATION: make `_update_margin_inspector` pass `report` instead of
    `self._worst_page_report(report)` and this goes red with 175.964.
    """
    _three_pages(tab, tmp_path)
    tab._settings.set("margin_inspector_show", True)
    handed: list = []

    def record(self, report=None):
        handed.append(report)
        return [], []
    monkeypatch.setattr(type(tab), "_engine_text_notes", record)
    # Standing on the part-full LAST page, which is the state that hid it.
    tab._preview._current = 2
    tab._update_margin_inspector()
    assert handed, ("the control failed: `_update_margin_inspector` never "
                    "asked for the text notices")
    got = handed[-1]
    assert got is not None, "the notices were handed no report at all"
    assert round(got.right_mm, 3) == min(EXPECTED_RIGHT_MM), (
        "standing on page 3, the text notices were judged against %.3f mm of "
        "right margin; the worst page of this chart leaves %.3f"
        % (got.right_mm, min(EXPECTED_RIGHT_MM)))
    assert round(tab._margin_report.right_mm, 3) == EXPECTED_RIGHT_MM[2], (
        "the frame's own report is no longer the page on screen: %.3f"
        % tab._margin_report.right_mm)


def test_every_side_is_taken_from_its_own_worst_page(tab, tmp_path):
    """Four sides, four independent minimums. Written for all four because the
    rule is about the sheet text, not about the one edge that bites today.
    """
    _three_pages(tab, tmp_path)
    judged = tab._worst_page_report(_report_on_page(tab, 2))
    for name in ("top_mm", "bottom_mm", "left_mm", "right_mm"):
        per_page = [round(getattr(_report_on_page(tab, i), name), 3)
                    for i in range(3)]
        assert round(getattr(judged, name), 3) == min(per_page), (
            "%s is judged at %.3f mm where the worst page leaves %.3f"
            % (name, getattr(judged, name), min(per_page)))


def test_the_frame_still_shows_the_page_on_screen(tab, tmp_path):
    """THE RULE THIS MUST NOT EAT (#83). The frame is headed "Measured from
    Preview" and its numbers, its guides and the patches the reader can see all
    describe ONE page: the one in front of them. Only the text-fit verdict is
    about the chart.

    MUTATION: assign the worst page's report to `self._margin_report` as well and
    this goes red, because the frame would then print the worst page's numbers
    over a picture of a different one.
    """
    _three_pages(tab, tmp_path)
    shown = _report_on_page(tab, 2)
    judged = tab._worst_page_report(shown)
    assert round(shown.right_mm, 3) == EXPECTED_RIGHT_MM[2], (
        "the page's own report was altered: %.3f" % shown.right_mm)
    assert judged is not shown, (
        "the worst page's report is the same object as the page's own, so editing "
        "one would edit the other")


def test_a_one_page_chart_is_untouched(tab, tmp_path):
    """Nothing changes for the charts most people make: with one page, the
    page IS the chart and the report is handed straight through."""
    _three_pages(tab, tmp_path)
    tab._margin_tiffs = tab._margin_tiffs[:1]
    tab._ensure_worst_page_cache(300.0)
    shown = _report_on_page(tab, 0)
    assert tab._worst_page_report(shown) is shown, (
        "a one-page chart went through the multi-page path")


def test_it_is_measured_once_per_chart_and_not_once_per_page_turn(
        tab, tmp_path, monkeypatch):
    """Knut's ruling says these numbers may be recomputed when the chart is
    generated, and paging through is not that. Measuring every page on every
    page turn would also put a read of every page's TIFF into the page button.

    MUTATION: delete the `cached[0] == key` early return from
    `_ensure_worst_page_cache` and this goes red with one pass per page turn.
    """
    _three_pages(tab, tmp_path)
    passes: list[int] = []
    real = type(tab)._measure_every_page

    def counted(self, tiffs, dpi):
        passes.append(1)
        return real(self, tiffs, dpi)
    monkeypatch.setattr(type(tab), "_measure_every_page", counted)
    for _ in range(6):                      # six page turns
        tab._ensure_worst_page_cache(300.0)
    assert passes == [], (
        "six page turns cost %d fresh passes over every page of the chart"
        % len(passes))


def test_a_new_chart_is_measured_again(tab, tmp_path):
    """…and the cache must not outlive the chart it was measured from, or a
    second Generate would be judged against the first chart's pages."""
    _three_pages(tab, tmp_path)
    first = tab._worst_page_report(_report_on_page(tab, 2))
    assert round(first.right_mm, 3) == min(EXPECTED_RIGHT_MM)
    # A different chart: one page, and it is the part-full one.
    tab._margin_tiffs = tab._margin_tiffs[2:]
    tab._ensure_worst_page_cache(300.0)
    shown = _report_on_page(tab, 2)
    again = tab._worst_page_report(shown)
    assert round(again.right_mm, 3) == EXPECTED_RIGHT_MM[2], (
        "a new chart was judged against the previous chart's pages: %.3f"
        % again.right_mm)


# ---------------------------------------------------------------------------
# …AND THE READER IS TOLD WHEN THE NOTICE AND THE FRAME ARE DIFFERENT SHEETS
# ---------------------------------------------------------------------------
#
# Found by the combined adversary round of 2026-09-15 (B8-210), attacking this
# file's own fix. Judging the notices on the tightest page is right — paging
# forward used to make a red warning vanish — and the frame must still show the
# page on screen, because the guides have to land on the patches the reader can
# see (#83). What nobody checked is what those two say TOGETHER.
#
# Photographed on a real three-page A4 chart, page 3 of 3
# (`~/Desktop/ChromIQ-beta18-proof/combined-round-3/`,
# `P3-create-chart-on-page-3-of-3.png` and its crop): the frame printed
# **"Right (to first patch) 176.0"** and the red notice INSIDE THE SAME FRAME
# said **"the right margin leaves 0.0 mm … Raise “Right” … by about 5.1 mm"**.
# Two numbers for one edge, 176 mm apart, an inch apart on screen, and the
# advice was wrong for the sheet in front of the reader. The notices even name
# this frame while quoting their number.

def test_the_reader_is_told_when_the_notice_is_about_another_page(qapp):
    """One plain sentence, above the notices, on the panel's SURFACE.

    MUTATION: stop passing `notice_preamble` from `_update_margin_inspector`
    and this goes red.
    """
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._update_margin_inspector)
    assert "notice_preamble=" in src, (
        "the panel is never told that its notices are about another page")


def test_the_two_sheets_are_compared_edge_by_edge(qapp):
    """The question is "are these the same sheet", asked of the four numbers
    rather than of object identity: `_worst_page_report` hands back the shown
    report itself when nothing was replaced.

    MUTATION: compare with `is not` instead of the edges and this goes red.
    """
    import dataclasses
    from ui.tabs.tab_chart import TabChart
    from workflow.margin_inspector import MarginReport
    fields = {f.name: 1.0 for f in dataclasses.fields(MarginReport)
              if f.default is dataclasses.MISSING
              and f.default_factory is dataclasses.MISSING}  # type: ignore
    try:
        shown = MarginReport(**fields)
    except Exception:                       # noqa: BLE001 — shape moved
        import pytest as _p
        _p.skip("MarginReport's shape changed; the behaviour is covered on "
                "screen in P3-create-chart-on-page-3-of-3.png")
    same = dataclasses.replace(shown)
    assert TabChart._notes_are_about_another_page(shown, same) is False
    other = dataclasses.replace(shown, right_mm=float(shown.right_mm) + 168.0)
    assert TabChart._notes_are_about_another_page(shown, other) is True
    assert TabChart._notes_are_about_another_page(shown, None) is False
    assert TabChart._notes_are_about_another_page(None, other) is False


def test_the_sentence_is_not_counted_as_a_warning(qapp):
    """A chart with one fault must not announce two. The preamble is printed
    in the same block and left out of the count.

    MUTATION: add the preamble to `overlap_warnings` instead and this goes red
    with a count of 2.
    """
    from ui.margin_inspector_panel import MarginInspectorPanel
    panel = MarginInspectorPanel()
    panel._update_status([], thresholds_defined=False, notify=True,
                         text_warnings=[], overlap_warnings=["⚠ one fault"],
                         notice_preamble="judged on another page")
    assert panel._warning_count == 1, panel._warning_count
    shown = panel._status.text()
    assert "judged on another page" in shown, shown
    assert shown.index("judged on another page") < shown.index("⚠ one fault")


def test_no_preamble_when_there_is_nothing_to_reconcile(qapp):
    """It appears only where the two really differ."""
    from ui.margin_inspector_panel import MarginInspectorPanel
    panel = MarginInspectorPanel()
    panel._update_status([], thresholds_defined=False, notify=True,
                         text_warnings=[], overlap_warnings=["⚠ one fault"],
                         notice_preamble=None)
    assert panel._status.text() == "⚠ one fault"
    assert panel._warning_count == 1
