"""No Create Chart section prints a paragraph at anybody any more.

Basti, 2026-09-04:

    "regarding the info text in create chart tab that is directly inside the
    sections (even that that you made collapsible) - i want that gone. You can
    fit it inside of a tooltip where it fits but not directly inside a section"

Four notices moved, and none of them was deleted:

===========================  ==========================================
was                          is now
===========================  ==========================================
``_label_style_note``        the ⓘ of every control in "Strip & row
                             labels" — it is true of all ten of them
``text_edge_clip_note``      the "Text distance from edge" ⓘ
``helper_markers_edge_       the "Show markers for" ⓘ
warning``
the collapsible "Text and    the "About the margin inspector" ⓘ
label notes" box             (`MarginInspectorPanel`)
===========================  ==========================================

The last of those is the one that needed permission rather than obedience.
``docs/design/row_label_geometry.md`` §R2 required the automatic left-margin
raise to be REPORTED, and §R5 correction 3 exists in that same document because
an earlier version of it *"claimed 'The panel says so' about the raised left
margin"* when no panel did. Removing the box without moving the specification
would have put the same false claim back into the same document about the same
feature, the second time. So it was put to Basti as a specification question,
with the cost stated — a notice under the preview is SEEN, a notice on an ⓘ is
only READ IF ASKED FOR — and he ruled *"a tooltip will be enough"*. §R6 records
that approval, and this file is what a future check can run against it.

WHAT IS DELIBERATELY LEFT ALONE. ``text_preview``, ``clip_dims_label``, the
margin table, the status verdict and the two placeholders are not info text:
every one of them is a value measured off the chart on screen. Basti did not
ask for those and they stay. :data:`LIVE_READOUTS` names them, so a future
change that quietly turns one of them into prose has to say so here first.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import (QApplication, QGroupBox, QLabel,   # noqa: E402
                             QWidget)

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "design" / "row_label_geometry.md"

#: A label inside a section may hold at most this many characters before it is
#: prose rather than a caption, a value or a verdict. The four that moved were
#: 78, 92, 112 and 395 characters; the longest thing left inside a section of
#: either panel is the margin table's "Patch width (in strip reading
#: direction)" at 40. Anything landing between those two numbers is a new
#: paragraph, which is the thing being kept out.
PROSE_CHARS = 60

#: Text inside a section that is NOT explanation — a measured value, a verdict,
#: or the empty state that stands in for one. Matched on the attribute name.
LIVE_READOUTS = ("text_preview", "clip_dims_label", "_status", "_placeholder",
                 "_strip_mm", "_strip_in", "_striplen_mm", "_striplen_in")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _pick(combo, want) -> bool:
    for i in range(combo.count()):
        if combo.itemData(i) == want:
            combo.setCurrentIndex(i)
            return True
    return False


def _knuts_panel(qapp):
    """The real panel in the state that fires every one of these notices.

    i1Pro, A4, a 26 mm clip border with a notes box on the left, row indicators
    on and "Clip" typed at 4 mm — Knut's own
    ``i1Pro-A4-162p-1page-Portrait-w7.5mm``, which is where all three of the
    layout panel's notices were reported and measured.
    """
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(None, with_selectors=True)
    _pick(p.instr, "i1")
    _pick(p.paper, "A4")
    _pick(p.mode, "clip")
    p.clip_width.setValue(26.0)
    _pick(p.clip_content_mode, "notes")
    _pick(p.clip_side, "left")
    # A CLICK, not setChecked: until a PERSON has touched the box the recipe
    # writes None ("follow the instrument's default", OFF for an i1Pro) and the
    # row-label band is never built at all.
    if not p.show_row_indicators.isChecked():
        p.show_row_indicators.click()
    p.text_edge_clip.setValue(4.0)
    p.helper_markers_cb.setChecked(True)
    p.helper_markers_top_bottom.setChecked(False)
    p.helper_markers_sides.setChecked(False)
    return p


def _inspector_with_notices(qapp):
    from ui.margin_inspector_panel import MarginInspectorPanel
    from workflow.margin_inspector import MarginReport
    panel = MarginInspectorPanel()
    report = MarginReport(left_mm=33.8, right_mm=8.2, top_mm=38.9, bottom_mm=26.0,
                          strip_width_mm=8.0, strip_length_mm=232.1,
                          page_w_mm=210.0, page_h_mm=297.0)
    panel.update_report(
        report, [], thresholds_defined=True, notify=True,
        text_warnings=[
            "⚠ The left margin was widened from 6.0 mm to 33.8 mm to fit the "
            "row indicators. The labels start 26.0 mm in from the page edge "
            "and their text needs 6.8 mm."])
    return panel


def _name_of(host, widget) -> str:
    for k, v in vars(host).items():
        if v is widget:
            return k
    return ""


def _prose_inside_a_section(host) -> "list[tuple[str, str]]":
    """(attribute name, text) for every long label sitting inside a group box."""
    found = []
    for lbl in host.findChildren(QLabel):
        txt = lbl.text()
        if len(txt) < PROSE_CHARS:
            continue
        p = lbl.parentWidget()
        inside = False
        while p is not None:
            if isinstance(p, QGroupBox):
                inside = True
                break
            p = p.parentWidget()
        if not inside:
            continue
        name = _name_of(host, lbl)
        if name in LIVE_READOUTS:
            continue
        found.append((name or "<anonymous>", txt))
    return found


# --------------------------------------------------- nothing prints prose ---
def test_no_section_of_the_layout_panel_prints_a_paragraph(qapp):
    """The panel driven into the state that fires all three of its notices."""
    p = _knuts_panel(qapp)
    try:
        # The premise: this state really does have things to say.
        assert p._text_edge_tip.live_note(), "the Clip note did not fire"
        assert p._hm_edges_tip.live_note(), "the marker notice did not fire"
        left = _prose_inside_a_section(p)
        assert not left, (
            "a Create Chart section is printing prose again:\n  " +
            "\n  ".join(f"{n}: {t[:90]!r}" for n, t in left))
    finally:
        p.deleteLater()


def test_no_section_of_the_margin_inspector_prints_a_paragraph(qapp):
    """…including the collapsible box, which is the one Basti named."""
    panel = _inspector_with_notices(qapp)
    try:
        assert panel.text_notes(), "the premise failed: no notice is live"
        left = _prose_inside_a_section(panel)
        assert not left, (
            "the margin inspector is printing prose again:\n  " +
            "\n  ".join(f"{n}: {t[:90]!r}" for n, t in left))
        assert not hasattr(panel, "_text_notes_box"), (
            "the collapsible box is back — Basti named it: *'even that that "
            "you made collapsible'*")
    finally:
        panel.deleteLater()


# ------------------------------------------------ each one reached its ⓘ ---
def test_where_a_label_style_setting_lives_is_on_every_icon_in_that_frame(qapp):
    """It is true of all ten label-style fields, so it goes on all of them.

    A frame-level ⓘ of its own would have cost width, and B8-48 measured this
    panel with NO width slack at all (Dutch sat exactly on its 514 px budget).
    """
    from ui.tooltip_button import TooltipButton
    p = _knuts_panel(qapp)
    try:
        tips = p._label_style_grp.findChildren(TooltipButton)
        assert len(tips) >= 6, f"only {len(tips)} ⓘ in the frame"
        for tip in tips:
            assert "Saved with this chart and its presets" in tip.dialog_body(), (
                f"the ⓘ {tip._title!r} does not say where the setting lives")
            assert "Preferences → Chart Layout" in tip.dialog_body()
    finally:
        p.deleteLater()


def test_the_clip_override_note_rides_on_the_row_it_is_about(qapp):
    p = _knuts_panel(qapp)
    try:
        note = p._text_edge_tip.live_note()
        assert "row indicator" in note, note
        assert "26.0 mm" in note and "4.0 mm" in note, note
        assert note in p._text_edge_tip.dialog_body()
        # …and the standing help is still under it.
        assert "minimum distance from the paper edge" in \
            p._text_edge_tip.dialog_body()
    finally:
        p.deleteLater()


def test_the_clip_note_comes_off_the_icon_when_the_typed_value_is_in_force(qapp):
    p = _knuts_panel(qapp)
    try:
        assert p._text_edge_tip.live_note()
        p.show_row_indicators.click()          # nothing left to overrule Clip
        p.clip_content_mode.setCurrentIndex(
            p.clip_content_mode.findData("off"))
        assert not p._text_edge_tip.live_note(), (
            "the ⓘ is still carrying a note about a chart that no longer has "
            "anything overruling “Clip”")
        assert "Click for details" in p._text_edge_tip.toolTip()
    finally:
        p.deleteLater()


def test_the_marker_notice_no_longer_points_above_itself(qapp):
    """"…tick at least one edge ABOVE" was true of a label under the two boxes
    and false of an ⓘ on the row above them. A notice that can move has to stop
    pointing with a finger."""
    p = _knuts_panel(qapp)
    try:
        note = p._hm_edges_tip.live_note()
        assert "No dashes will be printed" in note, note
        assert "above" not in note.lower(), note
        p.helper_markers_sides.setChecked(True)
        assert not p._hm_edges_tip.live_note()
    finally:
        p.deleteLater()


def test_the_marker_help_no_longer_sends_the_reader_under_the_boxes(qapp):
    """The standing help said *"ChromIQ says so under the boxes"*. Nothing is
    under the boxes now, and a help text that sends a reader to a line that is
    not there is worse than one that says nothing."""
    p = _knuts_panel(qapp)
    try:
        body = p._hm_edges_tip._body
        assert "under the boxes" not in body, body[-300:]
        assert "this ⓘ says so" in body, body[-300:]
    finally:
        p.deleteLater()


def test_the_text_distance_help_no_longer_promises_a_warning_is_shown(qapp):
    """The third sentence the move made false, and the quietest of them.

    This help ended *"the text overflows toward this line and a margin warning
    is shown"*. Nothing is SHOWN after the move — the warning is on the ⓘ
    beside the measured margins — and a help text that promises a line the
    reader will never find is the same fault as the other two, one degree
    softer. It now names the exact thing on screen instead.
    """
    p = _knuts_panel(qapp)
    try:
        body = p._text_edge_tip._body
        assert "a margin warning is shown" not in body, body[:400]
        assert "ⓘ beside the measured margins" in body, body[:400]
    finally:
        p.deleteLater()


# ------------------------------------------------- the mechanism behaves ---
def test_a_live_note_never_stacks_up_when_it_is_set_twice(qapp):
    """`_update_text_edge_clip_note` runs on every keystroke. A note appended
    to the stored body would grow without limit."""
    from ui.tooltip_button import TooltipButton
    b = TooltipButton("T", "the standing help")
    try:
        for _ in range(5):
            b.set_live_note("⚠ something happened")
        assert b.dialog_body().count("⚠ something happened") == 1
        assert b.dialog_body().endswith("the standing help")
    finally:
        b.deleteLater()


def test_the_standing_help_comes_back_when_the_note_goes(qapp):
    from ui.tooltip_button import TooltipButton
    b = TooltipButton("T", "the standing help")
    try:
        b.set_live_note("⚠ something happened")
        b.set_live_note("")
        assert b.dialog_body() == "the standing help"
        assert "something happened" not in b.toolTip()
    finally:
        b.deleteLater()


def test_the_hover_tooltip_says_there_is_something_to_read(qapp):
    """An ⓘ carrying a notice must say so BEFORE it is clicked — otherwise the
    disclosure depends on a click nobody has a reason to make (§R6.3)."""
    from ui.tooltip_button import TooltipButton
    b = TooltipButton("T", "the standing help")
    try:
        b.set_live_note("⚠ the left margin was widened\nand here is why")
        assert "⚠ the left margin was widened" in b.toolTip()
        # Only the FIRST line: a hover tooltip is a strip beside the pointer.
        assert "and here is why" not in b.toolTip()
        assert "Click for details" in b.toolTip()
    finally:
        b.deleteLater()


# ------------------------------------------------------ still readable -----
@pytest.mark.parametrize("mode", ["light", "dark", "neutral"])
def test_a_note_moved_into_a_tooltip_is_still_readable(qapp, mode):
    """A note that moved into a tooltip still has to be READ.

    ``tests/test_expert_notes_are_readable.py`` measured these off the panel's
    own pixels, at 4.5:1 (WCAG 2.1 AA). Two of the four it guarded now live in
    the ⓘ dialog, so the measurement moves with them — same method, same
    threshold, read off the dialog `TooltipButton` actually builds rather than
    off a colour constant.
    """
    from ui import theme
    from ui.tooltip_button import _InfoDialog
    import test_expert_notes_are_readable as ro       # the measurement kit

    sheet, make_palette = theme._APPEARANCE_STYLE[mode]
    pal = make_palette()
    # THE APPEARANCE HAS TO BE IN PLACE BEFORE THE DIALOG IS BUILT, WHICH IS
    # THE ORDER THE APP ITSELF USES. `_InfoDialog.__init__` reads
    # `self.palette().color(WindowText)` and writes that value into the body
    # label's stylesheet ONCE, at construction; painting a palette on
    # afterwards leaves black ink baked in — measured here, 1.18:1 on Dark's
    # #181818 — and a dialog is a WINDOW, so it does not take a parent's
    # palette either. `main.py:202` calls `apply_appearance(app, None, …)`
    # before it builds `MainWindow`, and two agents in a row have produced
    # false findings from a driver that did it the other way round (B8-45).
    # So the APPLICATION palette is set, and restored in the `finally` — the
    # same shape `apply_appearance` uses, and nothing this file leaves behind.
    # (This is `setPalette`, not `setStyleSheet`: CLAUDE.md forbids the latter
    # in a test because it re-polishes every widget the suite has alive.)
    before = qapp.palette()
    qapp.setPalette(pal)
    dlg = _InfoDialog(
        "Strip & row labels",
        "Saved with this chart and its presets. Preferences → Chart Layout "
        "only sets the starting values for a new chart.", None, 420)
    try:
        dlg.setPalette(pal)
        for child in dlg.findChildren(QWidget):
            child.setPalette(pal)
        dlg.setAutoFillBackground(True)
        dlg.setStyleSheet(sheet)
        body = [w for w in dlg.findChildren(QLabel)
                if "Saved with this chart" in w.text()]
        assert body, "the dialog did not build a body label"
        dlg.resize(560, 400)
        dlg.show()
        qapp.processEvents()
        ratio, ink, ground = ro._ink_on_ground(dlg, body[0])
        assert ratio >= ro.MIN_RATIO, (
            f"the note in the ⓘ dialog reads at {ratio:.2f}:1 in {mode} — "
            f"ink #{ink[0]:02x}{ink[1]:02x}{ink[2]:02x} on ground "
            f"#{ground[0]:02x}{ground[1]:02x}{ground[2]:02x}, under the "
            f"{ro.MIN_RATIO}:1 that body text needs")
    finally:
        dlg.close()
        dlg.deleteLater()
        qapp.setPalette(before)
        qapp.processEvents()


# ------------------------------------- the specification moved with it -----
def test_the_specification_names_the_home_the_code_actually_uses():
    """§R5 correction 3 exists because this document once claimed a disclosure
    that no code made. The way not to repeat that is to check it."""
    text = SPEC.read_text(encoding="utf-8")
    assert "§R6" in text, "the ruling is not recorded in the specification"
    assert "**Approved by:** Basti, 2026-09-04" in text, (
        "the ruling that moved the disclosure is not attributed — an approved "
        "change and a silent drift must stay tellable apart")
    assert "a tooltip will be enough" in text, "his words are not recorded"
    # It names a real symbol, not a remembered one.
    from ui.margin_inspector_panel import MarginInspectorPanel
    from ui.tooltip_button import TooltipButton
    for symbol in ("_show_text_notes", "set_live_note", "text_notes()"):
        assert symbol in text, f"§R6 does not name {symbol}"
    assert hasattr(MarginInspectorPanel, "_show_text_notes")
    assert hasattr(MarginInspectorPanel, "text_notes")
    assert hasattr(TooltipButton, "set_live_note")
    # …and it must not still promise the old home.
    assert not re.search(r"inspector under the preview says so", text), (
        "the document still promises the notice is printed under the preview")


def test_the_specification_still_requires_the_raise_to_be_disclosed():
    """Approval to MOVE a disclosure is not approval to drop it."""
    text = SPEC.read_text(encoding="utf-8")
    assert "must be disclosed" in text
    assert "R6.4" in text and "Nothing about the raise is printed inside a " \
        "Create Chart section" in text
