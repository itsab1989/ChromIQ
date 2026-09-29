"""Knut's house style for help cards, kept measurable.

Knut, issue #182, 2026-09-20: *"all workflow steps described in most of the
help cards should be re-organised and re-written in similar style as for
'Profile my scanner or camera' and 'Profile my printer with a flatbed
scanner', so that main actions are first described as specific and
recognisable to-do steps, and then detailed descriptions are shown in
collapsable sections under each main steps, for those users that want more
detailed understanding. This principle should be used throughout the help
cards."*

The shape is already in the data model: a step is
``(tab, text[, optional[, notes]])`` and ``notes`` is a sequence of
``(heading, body)`` pairs, CLOSED on screen and OPEN on paper. What was
missing is anything that keeps the shape once it is there. This file adds
four things that were each a real fault or a real question in the batch that
introduced it:

1. **A malformed note tuple crashes the print path**, and nothing else catches
   it. One note written ``((h, b)))`` instead of ``((h, b),))`` is a 2-tuple
   of strings rather than a 1-tuple of pairs, and ``help_card_print`` raises
   ``ValueError: too many values to unpack`` the moment the card is printed
   or saved as a PDF. The card renders fine on screen up to that point.
2. **A step has a ceiling, and the ceiling is the model's own.** The longest
   step in the two cards Knut named is 423 characters. A step twice that is
   not a step, it is an essay with a number in front of it, which is the
   fault this rewrite removed.
3. **A card with steps and no notes has not been rewritten.** The register
   below is what says which cards were.
4. **A COLLAPSED SECTION MUST NOT SILENTLY OMIT CONTENT FROM PAPER.** That is
   the design question a disclosure raises in a PRINTED document, and the
   answer this project holds is: on paper there is nothing to click, so every
   note prints, indented and in smaller grey type under its step
   (``help_card_print._notes_html``). The last test below is that promise,
   measured against the real printed document rather than against the HTML.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


#: The two cards Knut named as the model. Everything else copies their shape.
MODEL_CARDS = ("scanner_profile", "printer_from_scan")

#: Measured 2026-09-21 over every card: the longest single step in the whole
#: help set is `printer_from_scan` step 6 at 423 characters, and it is one of
#: the two MODEL cards, so the ceiling is the model's own rather than a number
#: anybody chose. 460 leaves one sentence of slack.
#:
#: LOWER IT WHEN THE TEXT GETS TIGHTER; do not raise it. A step past this is
#: the "200-word step that sets three controls" the second register exists to
#: replace, and the fix is to move the explanation into a note.
LONGEST_STEP = 460

#: Cards whose steps carry no notes, and why each one is allowed to.
#: Every other card with steps must carry at least three.
NO_NOTES_ALLOWED: dict = {}


def _cards_with_steps():
    from ui.dialogs.welcome_dialog import WORKFLOWS
    return [w for w in WORKFLOWS if w.get("steps")]


def _notes_of(step):
    return tuple(step[3]) if len(step) > 3 else ()


# ---------------------------------------------------------------- the shape
def test_every_note_is_a_heading_and_a_body():
    """The malformed-tuple fault, which only the PRINT path ever reaches.

    ``((h, b)))`` is a pair of strings; ``((h, b),))`` is a sequence of one
    pair. Python accepts both and only one of them survives
    ``for heading, body in notes``.
    """
    faults = []
    for wf in _cards_with_steps():
        for i, step in enumerate(wf["steps"], start=1):
            notes = _notes_of(step)
            for n in notes:
                if not (isinstance(n, (tuple, list)) and len(n) == 2
                        and all(isinstance(x, str) and x.strip() for x in n)):
                    faults.append(
                        f"{wf['key']} step {i}: a note must be a "
                        f"(heading, body) pair of non-empty strings, got "
                        f"{type(n).__name__} {str(n)[:60]!r}")
    assert not faults, "\n".join(faults)


def test_a_malformed_note_really_breaks_the_printed_card():
    """THE CONTROL. Without it the test above could be guarding nothing.

    Build the exact mistake and show that the print path raises on it, so the
    shape check above is known to be protecting a real failure and not a
    stylistic preference.
    """
    from ui.help_card_print import card_html

    good = {"key": "x", "title": "T", "subtitle": "S",
            "steps": [(1, "Do the thing.", False, (("Why", "Because."),))]}
    assert "Because." in card_html(good)

    bad = dict(good)
    bad["steps"] = [(1, "Do the thing.", False, ("Why", "Because."))]
    with pytest.raises(ValueError):
        card_html(bad)


# ----------------------------------------------------------- steps are acts
def test_no_step_is_longer_than_the_cards_knut_named_as_the_model():
    over = []
    for wf in _cards_with_steps():
        for i, step in enumerate(wf["steps"], start=1):
            n = len(str(step[1]))
            if n > LONGEST_STEP:
                over.append(f"{wf['key']} step {i}: {n} characters "
                            f"(ceiling {LONGEST_STEP}) - move the explanation "
                            f"into a note")
    assert not over, "\n".join(over)


def test_the_ceiling_is_the_models_own_and_not_a_round_number():
    """Guard the number: it has to stay above what the model cards really do.

    A ceiling that drifted below the two cards Knut pointed at would fail them
    and be quietly raised; one far above them would stop meaning anything.
    """
    from ui.dialogs.welcome_dialog import WORKFLOWS

    longest = max(
        len(str(s[1]))
        for w in WORKFLOWS if w["key"] in MODEL_CARDS
        for s in w["steps"])
    assert longest <= LONGEST_STEP, (
        f"the model cards themselves now break the ceiling ({longest} > "
        f"{LONGEST_STEP}); they are the pattern, so re-derive it from them")
    assert LONGEST_STEP <= longest + 120, (
        f"the ceiling ({LONGEST_STEP}) has drifted far above what the model "
        f"cards do ({longest}) and no longer constrains anything")


# ------------------------------------------------- every card has a second
# ------------------------------------------------- register
def test_every_card_with_steps_carries_notes():
    """A card with steps and no collapsible detail has not been rewritten."""
    thin = []
    for wf in _cards_with_steps():
        if wf["key"] in NO_NOTES_ALLOWED:
            continue
        n = sum(len(_notes_of(s)) for s in wf["steps"])
        if n < 3:
            thin.append(f"{wf['key']}: {n} note(s) across "
                        f"{len(wf['steps'])} steps")
    assert not thin, (
        "these cards carry steps but almost no second register, so a reader "
        "who wants the reasoning has nowhere to open it:\n" + "\n".join(thin))


def test_the_model_cards_still_have_the_shape_everything_else_copied():
    from ui.dialogs.welcome_dialog import WORKFLOWS

    for key in MODEL_CARDS:
        wf = next(w for w in WORKFLOWS if w["key"] == key)
        n = sum(len(_notes_of(s)) for s in wf["steps"])
        assert n >= 5, (
            f"{key} is one of the two cards Knut named as the pattern and it "
            f"now carries only {n} notes; the pattern cannot be derived from "
            f"it any more")


# --------------------------------------------- a collapsed note still PRINTS
@pytest.mark.parametrize("page", ["A4", "Letter"])
def test_a_note_closed_on_screen_is_open_on_paper(qapp, tmp_path, page):
    """THE DESIGN ANSWER, measured on the real printed document.

    A disclosure is new structure in a document that gets PRINTED, and the
    question it raises is what a collapsed section does on paper. It must not
    omit anything: a note the reader cannot reach is a note that was deleted.

    Checked against the laid-out ``QTextDocument``'s plain text rather than
    against the HTML string, because the HTML is what we wrote and the
    document is what is painted.
    """
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QPageLayout, QPageSize, QPdfWriter

    from ui.help_card_print import (build_document, printable_size_mm,
                                    render_card)

    writer = QPdfWriter(str(tmp_path / f"{page}.pdf"))
    writer.setPageSize(QPageSize(getattr(QPageSize.PageSizeId, page)))
    writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
    w_mm, h_mm = printable_size_mm(writer)

    missing = []
    for wf in _cards_with_steps():
        text = " ".join(
            build_document(wf, width_mm=w_mm, height_mm=h_mm)
            .toPlainText().split())
        for i, step in enumerate(wf["steps"], start=1):
            for heading, body in _notes_of(step):
                # The heading gains a full stop on paper, so compare on the
                # stem; the body is compared whole.
                head = " ".join(str(heading).rstrip(".").split())
                if head not in text:
                    missing.append(f"{wf['key']}/{page} step {i}: the note "
                                   f"heading {head[:48]!r} is not on the sheet")
                if " ".join(str(body).split()) not in text:
                    missing.append(f"{wf['key']}/{page} step {i}: the note "
                                   f"body under {head[:36]!r} is not on the "
                                   f"sheet")
    assert not missing, (
        "a collapsed section must never take content off the printed page:\n"
        + "\n".join(missing[:20]))


def test_the_print_path_is_what_opens_them_and_not_the_card_data(qapp):
    """Guard the guard: the test above must fail if the notes stop printing.

    Neuter ``_notes_html`` and the promise has to break. Without this control,
    a renderer that silently dropped every note would still pass, because the
    step text alone would satisfy a looser check.
    """
    import ui.help_card_print as hcp

    wf = {"key": "x", "title": "T", "subtitle": "S",
          "steps": [(1, "Do the thing.", False,
                     (("Why it matters", "The reason is here."),))]}
    assert "The reason is here." in hcp.card_html(wf)

    original = hcp._notes_html
    try:
        hcp._notes_html = lambda notes: ""
        assert "The reason is here." not in hcp.card_html(wf), (
            "the note text reaches the sheet by some route other than "
            "_notes_html, so neutering it proves nothing")
    finally:
        hcp._notes_html = original
