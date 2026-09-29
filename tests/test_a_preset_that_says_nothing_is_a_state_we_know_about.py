"""A loaded preset that shows neither a warning nor "Margins: OK".

**THIS FILE PINS A FAULT, NOT A DESIGN.** The design authority asked about it
on 2026-09-16: *"I mentioned before that some presets when loaded are missing
the 'Margins: OK' message, and instead have no message at all. Why is that, for
what kind of circumstances does this happen, and is that a bug? Can it be
fixed, so that all presets loaded end up showing the 'Margins: OK' message?"*

It was diagnosed rather than guessed at, by driving all 149 built-in presets
and reading the panel's own status line back (B8-284). What follows is what
was measured, and the tests below hold the MECHANISM still so that whoever
implements his ruling has to change them deliberately rather than by accident.
**A green run here does not mean the app is right; it means the app is still
doing the thing he was told about.**

THE MECHANISM, in one sentence: `MarginInspectorPanel.update_report` blanks and
HIDES its status label whenever `text_warnings` is non-empty, and
`text_warnings` is the list that goes to the panel's ⓘ and never appears on the
panel's surface at all.

So the three states a reader can be in are:

| what is live | what the surface shows |
|---|---|
| a margin violation or an overlap warning | a red paragraph naming it |
| only an ⓘ note | **nothing whatever** |
| neither | a green "Margins: OK" |

The middle row is the one he is asking about, and the thing being withheld is
worth more than the green line: on the fifteen presets that reach it, the ⓘ
note says the strip is longer than the instrument's ruler and may not fit the
user's jig.

WHY IT IS FIFTEEN, AND WHY THEY ARE ALL ONE FAMILY. `tab_chart` adds a text
note when `_ruler_over_mm` is set, which is the i1Pro 3 Plus's 220 mm ruler.
Measured: the A4 chart's strip is 236.98 mm and it goes silent; its Letter
sibling's is 219.20 mm, 0.8 mm under the limit, and it shows the green line.
Same author, same recipe shape, margins within a tenth of a millimetre.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from ui.margin_inspector_panel import MarginInspectorPanel  # noqa: E402
from workflow.margin_inspector import MarginReport          # noqa: E402


def _report():
    """A chart whose margins are fine by any threshold."""
    return MarginReport(left_mm=27.94, right_mm=10.03, top_mm=40.13,
                        bottom_mm=20.19, strip_width_mm=24.6,
                        page_w_mm=210.0, page_h_mm=297.0,
                        strip_length_mm=236.98, dpi=300.0)


@pytest.fixture
def panel(qapp):
    p = MarginInspectorPanel()
    yield p
    p.deleteLater()


def test_with_nothing_live_the_panel_says_margins_are_ok(panel):
    """The state 134 of the 149 built-in presets are in."""
    panel.update_report(_report(), [], thresholds_defined=True, notify=True,
                        thresholds={}, text_warnings=[], overlap_warnings=[])
    assert panel.status_message() == "Margins: OK"


def test_an_i_note_alone_blanks_the_verdict_and_shows_nothing(panel):
    """**THE FAULT, HELD STILL.** One ⓘ-only note and the surface goes silent.

    The margins have not changed and are still fine; the label is specifically
    about margins; and the note that caused the silence is not on the surface
    either. So the reader is given no verdict, no warning, and no cue that
    there is anything to hover.

    When this is ruled on, this test is the one to rewrite.
    """
    panel.update_report(
        _report(), [], thresholds_defined=True, notify=True, thresholds={},
        text_warnings=["⚠ Strip length 237 mm exceeds the 220 mm instrument "
                       "ruler, the strip may not fit your jig"],
        overlap_warnings=[])
    assert panel.status_message() == "", (
        "the panel now says something in the state B8-284 is about; if that "
        "is the ruling being implemented, rewrite this file rather than "
        "deleting it")
    # AND THE NOTE REALLY IS ONLY ON THE ⓘ, which is what makes the silence
    # total rather than merely terse.
    assert "220 mm instrument ruler" in panel.text_notes()


def test_an_overlap_warning_is_shown_and_explains_its_own_silence(panel):
    """The contrast that makes the middle row a fault rather than a style.

    An overlap warning suppresses the green line too, but it PRINTS itself in
    red where the green line would have been, so the reader can see why the
    verdict is gone. That is the behaviour the ⓘ-only case should have and
    does not.
    """
    panel.update_report(
        _report(), [], thresholds_defined=True, notify=True, thresholds={},
        text_warnings=[],
        overlap_warnings=["⚠ The settings stamp down the right edge runs over "
                          "the patches."])
    assert "stamp down the right edge" in panel.status_message()
    assert panel.status_message() != "Margins: OK"


def test_turning_the_margin_notice_off_is_a_SECOND_way_to_get_silence(panel):
    """And it is a deliberate one, recorded here so the two are not confused.

    Preferences carries "warn me about margin violations"; with it off,
    `_update_status` hides the label before it looks at anything else. That is
    the user asking for silence and getting it, which is not the fault above:
    there, the user asked for nothing and the panel went quiet on its own.

    This is also the trap that cost this file a first draft, which passed
    `notify=False` and then read the silence as the fault it was hunting.
    """
    panel.update_report(_report(), [], thresholds_defined=True, notify=False,
                        thresholds={}, text_warnings=[], overlap_warnings=[])
    assert panel.status_message() == ""


def test_the_rule_is_keyed_on_a_list_that_never_reaches_the_surface():
    """Read from the source, because this is the reasoning and not a value.

    The suppression's own comment justifies itself with *"a green headline over
    a red notice reads as approval of the thing the notice is about"*. That
    describes an OVERLAP warning, which is red and on the surface. It is keyed
    on `text_warnings`, which `_show_text_notes` hands to the ⓘ and which
    `set_live_note` puts only in a hover tooltip, leaving the icon unmarked.
    If either of those two facts stops being true, the fault described in
    B8-284 has changed shape and the entry needs re-reading.
    """
    import inspect
    from ui import tooltip_button
    from ui import margin_inspector_panel as mip
    src = inspect.getsource(mip)
    assert "if text_warnings:" in src, (
        "the suppression is no longer keyed on text_warnings")
    assert "self._status.setVisible(False)" in src
    # The ⓘ carries the note into a HOVER tooltip and nothing else: no badge,
    # no colour change, nothing a reader can see without hovering.
    note_src = inspect.getsource(tooltip_button.TooltipButton.set_live_note)
    assert "_refresh_hover_tip" in note_src
    assert "setIcon" not in note_src and "set_ink" not in note_src, (
        "the ⓘ now marks itself when it carries a note, which would give the "
        "reader the cue B8-284 says is missing")
