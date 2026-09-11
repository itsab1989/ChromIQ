"""Knut's four rulings of 2026-09-11 on #182, each held to its own words.

He answered five questions about the scanner window and the margin panel; four
of them changed behaviour and are pinned here. The fifth ("why do some charts
give no green 'Margins: OK' at all?") is a question rather than a ruling and is
answered in the report and in `docs/design/row_label_geometry.md` §R7.

    R1  the honeycomb reading square gets a smaller maximum
        -> tests/test_hex_sample_clamp.py, which already owns that cap
    R2  Auto align places its best attempt instead of refusing      (here)
    R3  a two-sheet warning names the sheet and lists each one      (here)
    R4  the row-indicator margin raise is printed in red            (here)

Each test asserts both halves: that the new behaviour happens, AND that the
thing it replaced no longer does. A test that only checks the new half passes
against a build that does both, which is the shape of most of these faults.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M            # noqa: E402
from workflow.scan_placement import PlacementResult       # noqa: E402


# ====================================================================== R2 ===
#
# *"place its best attempt and tell user to check it."*

QUAD = [(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)]


def test_a_placement_the_checks_refused_is_still_handed_back():
    """The whole of R2, at the boundary that decides it: `corners` carries the
    best attempt and `trusted` carries the verdict, and they are two different
    questions. Before this, a refused candidate was discarded and the caller
    could not tell "nothing was found" from "something was found and I do not
    believe it"."""
    for ending in ("not-seated", "below-floor"):
        r = PlacementResult(corners=list(QUAD), ending=ending)
        assert r.ok, f"{ending}: the best attempt must reach the window"
        assert not r.trusted, f"{ending}: a refused check may never read as good"


def test_only_a_passed_check_is_trusted():
    """The other half. `trusted` is the single flag the app may read as "this
    grid is right", so nothing but the successful ending may set it."""
    assert PlacementResult(corners=list(QUAD), ending="placed").trusted
    for ending in ("not-seated", "below-floor", "no-better", "too-far",
                   "not-recognised", "no-usable-candidate",
                   "ambiguous-orientation", "no-chart-geometry", ""):
        assert not PlacementResult(corners=list(QUAD), ending=ending).trusted


def test_place_grid_sets_the_corners_before_it_checks_them():
    """Read at the source, because the ordering IS the fix: `res.corners` has
    to be assigned before the two checks, so that no early return can forget
    it. An assignment repeated inside each branch would pass a behaviour test
    and rot the first time a branch is added."""
    import inspect

    from workflow import scan_placement
    src = inspect.getsource(scan_placement.place_grid)
    body = src.split("# ---- 3.", 1)[1]
    before_seated = body.split("seated_verdict(", 1)[0]
    assert "res.corners = candidate" in before_seated, (
        "the best attempt must be recorded before the checks run, or a "
        "refusing branch loses it")
    assert body.count("res.corners = candidate") == 1, (
        "one assignment, or the branches will drift apart")


def _run_place_grid(monkeypatch, *, seated, rho, tmp_path):
    """`place_grid` end to end with its three helpers stubbed, so the LADDER is
    the thing under test and nothing shells out to scanin.

    Only the three leaf calls are replaced: the search, the refinement, and the
    two checks. Every branch, every assignment and every `ending` in between is
    the shipped code.
    """
    from types import SimpleNamespace

    from workflow import photo_fit, scan_auto_align, scan_placement

    found = SimpleNamespace(ok=True, corners=list(QUAD), reason="", rho=0.99,
                            rho_before=0.5, candidates=3, log_tail="",
                            rejected=[])
    monkeypatch.setattr(scan_auto_align, "auto_align",
                        lambda *a, **k: found)
    monkeypatch.setattr(photo_fit, "refine_corners",
                        lambda *a, **k: SimpleNamespace(
                            ok=True, corners=list(QUAD), reason="",
                            moved_pitch=0.1))
    monkeypatch.setattr(scan_placement, "seated_verdict",
                        lambda *a, **k: (seated, 0.01))
    monkeypatch.setattr(scan_auto_align, "reference_agreement_at",
                        lambda *a, **k: rho)
    scan = tmp_path / "scan.tif"
    scan.write_bytes(b"")
    return scan_placement.place_grid(
        "scanin", scan, tmp_path / "c.cht", tmp_path / "c.cie",
        boxes=[object()], expected_y={}, image_size=(100, 100),
        current_corners=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])


@pytest.mark.parametrize("seated,rho,ending", [
    (False, 0.99, "not-seated"),
    (True, 0.10, "below-floor"),
    (True, None, "below-floor"),
    (True, 0.99, "placed"),
])
def test_the_ladder_hands_back_its_candidate_whatever_the_checks_say(
        monkeypatch, tmp_path, seated, rho, ending):
    """Behaviour, not source. Each of the three refusals that HAS a candidate
    must return it; only the passing one may call itself trusted."""
    r = _run_place_grid(monkeypatch, seated=seated, rho=rho, tmp_path=tmp_path)
    assert r.ending == ending
    assert r.corners == QUAD, (
        f"{ending}: the best attempt was thrown away, so the user has nothing "
        "to look at and nothing to correct")
    assert r.trusted is (ending == "placed")


def test_the_two_placed_endings_have_words_of_their_own():
    """A placement that moved the grid may not be announced with the refusal
    headline, which opens "Auto align left your corners exactly where they
    are" — a sentence that would now be false on screen."""
    kept = M.M_SCAN_ALIGN_NO_MATCH.title
    for ending in ("not-seated", "below-floor"):
        msg = M.scan_align_unchecked(ending)
        assert msg.title != kept
        assert msg.title != M.M_SCAN_ALIGN_DONE.title, (
            "an unconfirmed placement must not read like a confirmed one")
        title, body = msg.render(ref_row="Measured chart (.ti3)")
        assert "{" not in title and "{" not in body, (title, body)
        # it says the grid MOVED, and it says to check it
        assert "placed" in title.lower()
        assert "check" in body.lower()
        assert "undo auto align" in body.lower(), (
            "the user must be told how to get their own corners back")


def test_the_refusals_that_have_nothing_to_place_are_untouched():
    """R2 is about the two endings that HAD an answer. The other seven still
    refuse, and still open with the headline that says nothing moved."""
    kept = M.M_SCAN_ALIGN_NO_MATCH.title
    for reason in ("not-recognised", "no-usable-candidate",
                   "ambiguous-orientation", "no-chart-geometry",
                   "no-better", "too-far"):
        assert M.scan_align_refusal(reason).title == kept, reason


def test_the_window_chooses_its_sentence_by_trusted_and_not_by_ok():
    """The wiring, read at the call site. `ok` now means "there is something to
    apply" and is True for both outcomes, so a window that still branched on it
    would announce every refused placement as a success."""
    import inspect

    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._auto_align_done)
    tail = src.split("corners = result.corners", 1)[1]
    assert "if _trusted:" in tail
    assert "M_SCAN_ALIGN_DONE" in tail and "scan_align_unchecked" in tail
    assert "if result.ok:" not in tail


# ====================================================================== R3 ===
#
# *"Yes, warning should name the sheet, and list each sheet separately."*

def test_two_sheets_with_the_same_finding_are_both_kept():
    """The mechanism, at the de-duplication key. Every sheet of a chart
    produces the SAME headline with a DIFFERENT number, and a title-only key
    threw the second sheet's number away — measured on a two-page chart, the
    gate said 25 % while page 2's own check said 1 %."""
    import inspect

    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._check_read_is_this_chart)
    assert "seen = {(pg, t) for pg, t, _b in self._read_findings}" in src, (
        "the de-duplication key must carry the sheet, or one sheet silences "
        "the next")
    assert "if t not in seen" not in src, (
        "a title-only test is still in there somewhere")
    assert src.count("self._read_findings.append((page, t, b))") == 5, (
        "every one of the five findings records its sheet")


def _clipped_read(path, share):
    """A scanner .ti3 with *share* of its patches pinned at the top of the
    scale, and the rest ranking perfectly against the reference.

    Not pinned to ONE flat value: a real clipped read still ranks almost
    perfectly against its reference (measured: +0.943 on a 39 %-clipped scan),
    and a fixture that clipped to a single number would be caught by the
    agreement check instead and prove nothing about the clipping check.
    """
    n = 100
    rows = [(f'"A{k}"', (99.6 + k * 0.001) if k > n * (1.0 - share)
             else float(k), float(k)) for k in range(1, n + 1)]
    body = "\n".join(
        f"{i} {name} {v:.4f} {v:.4f} {v:.4f} {y:.4f} {y:.4f} {y:.4f}"
        for i, (name, v, y) in enumerate(rows, 1))
    path.write_text(
        'CTI3\nKEYWORD "SAMPLE_LOC"\nDEVICE_CLASS "INPUT"\n'
        "NUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        f"END_DATA_FORMAT\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
        f"{body}\nEND_DATA\n", encoding="utf-8")
    return path


def test_the_second_sheets_own_number_survives_the_de_duplication(
        qapp_findings, tmp_path):
    """The fault Knut reported, reproduced and then fixed, at the method that
    collects the findings rather than at the window that shows them.

    Two sheets, both over the clipping cap, by different amounts. Under a
    title-only de-duplication key the second sheet was dropped as a repeat, so
    the gate quoted the FIRST sheet's percentage about a chart where page 2 was
    a different number. Measured on a two-page chart before this: the gate said
    25 % while page 2's own Check alignment said 1 %.
    """
    from types import SimpleNamespace
    dlg, _shown = qapp_findings
    dlg._read_findings = []
    for page, share in ((1, 0.40), (2, 0.80)):
        ti3 = _clipped_read(tmp_path / f"p{page}.ti3", share)
        dlg._check_read_is_this_chart({
            "page": page,
            "params": SimpleNamespace(out_ti3=ti3, is_printer=False,
                                      cht=tmp_path / "absent.cht",
                                      pbase=tmp_path / "b"),
        })
    clipped = [(pg, b) for pg, t, b in dlg._read_findings
               if "no colour left" in t]
    assert len(clipped) == 2, (
        f"one sheet silenced the other: {dlg._read_findings}")
    assert {pg for pg, _b in clipped} == {1, 2}
    assert clipped[0][1] != clipped[1][1], (
        "both sheets were kept but with the same body, so the number is not "
        "each sheet's own")


def test_the_gate_names_every_sheet_and_lists_them_separately(qapp_findings):
    """Driven through the real window: two sheets, the same finding, different
    numbers. Both must appear, and each must be named."""
    dlg, shown = qapp_findings
    dlg._pages = [0, 1]
    dlg._read_findings = [
        (1, "Part of this scan has no colour left in it", "25 % of it."),
        (2, "Part of this scan has no colour left in it", "1 % of it."),
    ]
    dlg._confirm_despite_read_findings()
    text = shown[-1]
    assert "25 % of it." in text and "1 % of it." in text, (
        "the second sheet's own number was dropped as a repeat")
    assert "Page 1" in text and "Page 2" in text, (
        "the warning must name the sheet each finding came from")


def test_a_single_sheet_chart_is_not_told_which_sheet_it_is(qapp_findings):
    """The other half, and the reason the label is conditional: on a one-sheet
    chart there is no other sheet to confuse it with, and "Target:" in front of
    every line is noise. `_page_label` already draws this line for the rest of
    the window."""
    dlg, shown = qapp_findings
    dlg._pages = [0]
    dlg._read_findings = [(1, "Part of this scan has no colour left in it",
                           "25 % of it.")]
    dlg._confirm_despite_read_findings()
    text = shown[-1]
    assert "25 % of it." in text
    assert "Page 1" not in text and "Target" not in text


def test_a_second_finding_carries_its_own_headline(qapp_findings):
    """Findings 2..n used to be stacked as bare paragraphs under the FIRST
    one's headline, so a sheet with a different problem was described by
    another sheet's title."""
    dlg, shown = qapp_findings
    dlg._pages = [0, 1]
    dlg._read_findings = [
        (1, "Part of this scan has no colour left in it", "25 % of it."),
        (2, "This scan never reached the top of the scale", "56 % of it."),
    ]
    dlg._confirm_despite_read_findings()
    text = shown[-1]
    assert "This scan never reached the top of the scale" in text


@pytest.fixture
def qapp_findings(tmp_path):
    """A real ScannerProfileDialog with its message box captured.

    The output root is PINNED: `custom_output_path` defaults to "" and "" is
    ~/ChromIQ, the owner's own projects folder, and this window provisions a
    folder as it opens.
    """
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    QApplication.instance() or QApplication([])
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "out"))
    dlg = ScannerProfileDialog(ArgyllRunner(s), s)
    shown: list[str] = []
    real = QMessageBox.exec

    def _capture(self):
        shown.append("\n".join([self.windowTitle(), self.text(),
                                self.informativeText()]))
        for b in self.buttons():
            if b.text() == "Stop":
                self.setClickedButton = None
        return QMessageBox.StandardButton.Ok

    QMessageBox.exec = _capture
    try:
        yield dlg, shown
    finally:
        QMessageBox.exec = real
        dlg.deleteLater()


# ====================================================================== R4 ===
#
# *"Yes, add also a warning in red text, telling if the left margin is below
# what is used when the row indicator is ON (with its font size), so that a
# user is made aware and may modify margins or font size, or 'Text distance
# from edge' Clip-parameter to get the right balance without showing
# warnings."*
#
# Driven against the REAL geometry and a REAL LayoutRecipe, the way
# `tests/test_the_raised_left_margin_is_reported.py` drives the same method: a
# stub stands in only for the three widgets it reads, never for the
# calculation. A fixture that supplied its own `margin_l` and `rlwi` would
# prove the sentence formats, not that it fires on a chart that has the fault.


class _Btn:
    def isChecked(self):
        return True


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


class _Tab:
    _manual_btn = _Btn()
    _manual_layout_panel = object()
    _settings = _Settings()
    _manual_chart_notes_edit = None
    _manual_stamp_cmd_check = None

    def __init__(self, recipe):
        self._recipe = recipe

    def _current_layout_recipe(self):
        return self._recipe


def _recipe(*, margin_l, rows=True, mode="area_first", instrument="CM"):
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = instrument, "A4", mode
    r.show_strip_indicators, r.show_row_indicators = True, rows
    r.clip_border = False
    r.margin_top = r.margin_right = r.margin_bottom = 10.0
    r.margin_left = margin_l
    return r


def _notes(r):
    """(everything the ⓘ gets, what the RED message field gets)."""
    from ui.tabs.tab_chart import TabChart
    return TabChart._engine_text_notes(_Tab(r), None)


def _resolved(r):
    from workflow.layout_engine import instruments
    return instruments.geom_from_build_kwargs(r.build_kwargs()).margin_l


def _anchor_is_clip(r):
    """Which of the two wordings this chart reaches, measured off its geometry.

    There are two, and the difference is not cosmetic: `floor` is the LARGER of
    Clip and the left furniture, so on a chart whose furniture is wider, Clip is
    not what is holding the labels out and offering it as a lever would be
    false (beta 8, B8-14). Both branches must be exercised, or a mutation that
    reverts one of them survives — which is exactly what happened the first
    time these tests were written.
    """
    from workflow.layout_engine import instruments
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    return g.text_edge_clip_mm >= g.row_label_floor - 0.05


# "i1" on this recipe leaves the floor at Clip (4.0), so Clip IS the anchor;
# "CM" reserves a 20 mm left furniture band and raises the floor to 26, so it
# is not. Measured, not assumed — `test_the_two_branches_are_both_reached`
# below fails if that ever stops being true.
@pytest.mark.parametrize("instrument", ["i1", "CM"])
def test_the_raise_is_printed_in_red_on_the_panel(instrument):
    """R4, and the premise is measured first. The notice used to reach `warns`
    alone, which `MarginInspectorPanel._update_status` parks on the ⓘ and never
    inks; Knut ruled it onto the surface, so it has to be in the OVERLAP list —
    that is the list `_update_margin_inspector` hands to the red message
    field."""
    r = _recipe(margin_l=4.0, instrument=instrument)
    got = _resolved(r)
    assert got > 4.05, ("the premise failed: this chart's left margin is not "
                        "raised, so there is nothing to report")
    warns, over = _notes(r)
    red = [w for w in over if "row indicators" in w]
    assert red, (f"the margin went from 4.0 to {got:.2f} mm and nothing "
                 f"reached the red message field: {over}")
    assert "4.0 mm" in red[0] and f"{got:.1f} mm" in red[0], (
        f"the red line does not carry both numbers: {red[0]}")
    assert any("row indicators" in w for w in warns), (
        "§R6.1's disclosure must survive: the ⓘ is handed `warns + over`, so "
        "the notice has to be in the first list the tab returns as well")


def test_the_two_branches_are_both_reached():
    """The fixtures above are only worth having while they really do land on
    different wordings."""
    assert _anchor_is_clip(_recipe(margin_l=4.0, instrument="i1"))
    assert not _anchor_is_clip(_recipe(margin_l=4.0, instrument="CM"))


def test_the_red_line_names_the_label_size_in_points():
    """*"(with its font size)"* is Knut's own parenthesis and it is load
    bearing: the band is as wide as the widest row number AT that size, so a
    message quoting the width without the size quotes half a fact."""
    from workflow.layout_engine import instruments
    from workflow.layout_engine.raster import (DEFAULT_INDICATOR_FONT,
                                               effective_row_label_size_mm)
    r = _recipe(margin_l=4.0, instrument="i1")
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    want = effective_row_label_size_mm(geom, int(r.dpi),
                                       DEFAULT_INDICATOR_FONT,
                                       float(r.indicator_size_mm or 0.0))
    want_pt = want * 72.0 / 25.4
    assert want_pt > 0, "the premise failed: no label size to quote"
    red = next(w for w in _notes(r)[1] if "row indicators" in w)
    assert f"{want_pt:.0f} pt" in red, (want_pt, red)


def test_the_red_line_names_all_three_levers():
    """*"…may modify margins or font size, or 'Text distance from edge'
    Clip-parameter to get the right balance"*. All three, named the way the
    controls are labelled on screen — Knut's other objection on this panel was
    that "Clip" alone "is not a clear reference for a user"."""
    r = _recipe(margin_l=4.0, instrument="i1")
    assert _anchor_is_clip(r), "the premise failed: Clip is not a lever here"
    red = next(w for w in _notes(r)[1] if "row indicators" in w)
    assert "Margins (mm)" in red
    assert "Size" in red
    assert "Text distance from edge" in red
    # …and on the OTHER branch all three are still named, because two of them
    # always work and Clip is named as the thing that does NOT.
    r2 = _recipe(margin_l=4.0, instrument="CM")
    assert not _anchor_is_clip(r2)
    red2 = next(w for w in _notes(r2)[1] if "row indicators" in w)
    assert "Margins (mm)" in red2
    assert "Size" in red2
    assert "Text distance from edge" in red2


def test_the_clip_lever_is_not_offered_when_it_cannot_move_anything():
    """B8-14's rule, kept. Clip is one of the three levers only while Clip is
    what is holding the labels out. On Knut's own 26 mm-border preset the floor
    is the border's width, lowering Clip moves nothing, and the sentence must
    not claim it does: a remedy the user can measure and find wrong is worse
    than no remedy at all."""
    from workflow.layout_engine import instruments
    r = _recipe(margin_l=6.0, instrument="i1")
    r.clip_border = True
    r.clip_border_width_mm = 26.0
    r.clip_side = "left"
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    assert g.row_label_floor >= 26.0 > g.text_edge_clip_mm, (
        "the premise failed: Clip IS the anchor on this chart")
    red = next(w for w in _notes(r)[1] if "row indicators" in w)
    assert "not what is holding them out there" in red
    assert "lower \u201cClip\u201d" not in red


def test_nothing_is_said_when_the_margin_was_not_raised():
    """The condition is Knut's: the left margin is BELOW what the indicators
    need. A chart that asked for enough gets nothing, in either list — a notice
    that fires while the user is looking at the thing working is how people
    learn to ignore notices."""
    r = _recipe(margin_l=40.0)
    assert abs(_resolved(r) - 40.0) < 0.05, "the premise failed"
    warns, over = _notes(r)
    assert not [w for w in over if "row indicators" in w]
    assert not [w for w in warns if "was widened" in w]


def test_nothing_is_said_when_there_are_no_row_indicators():
    r = _recipe(margin_l=4.0, rows=False)
    warns, over = _notes(r)
    assert not [w for w in over if "was widened" in w]
    assert not [w for w in warns if "was widened" in w]


def test_the_panel_can_no_longer_go_silent_on_a_raised_margin():
    """The reason this matters on screen, and the answer to Knut's fifth
    question for these charts. `MarginInspectorPanel` hides its message field
    entirely while a `text_warnings` notice is live, so a chart whose ONLY
    notice was the raise printed nothing at all: no green, no red, nothing.
    Measured over all 154 built-in presets on 2026-09-11, 8 of them did that.
    Moving the notice into the overlap list is what puts words back on the
    panel — asserted here at the panel, because that is where the silence
    was."""
    from PyQt6.QtWidgets import QApplication

    from ui.margin_inspector_panel import MarginInspectorPanel
    from workflow.margin_inspector import MarginReport
    QApplication.instance() or QApplication([])
    panel = MarginInspectorPanel()
    r = _recipe(margin_l=4.0, instrument="i1")
    warns, over = _notes(r)
    assert [w for w in over if "row indicators" in w], "the premise failed"
    report = MarginReport(left_mm=9.0, right_mm=9.0, top_mm=9.0, bottom_mm=9.0,
                          strip_width_mm=8.0, page_w_mm=210.0,
                          page_h_mm=297.0)
    panel.update_report(report, [], thresholds_defined=True, notify=True,
                        thresholds={"L": 6, "R": 6, "T": 6, "B": 6},
                        text_warnings=warns, overlap_warnings=over)
    assert "row indicators" in panel.status_message(), (
        "the panel is still silent on a chart whose left margin it moved")
    panel.deleteLater()
