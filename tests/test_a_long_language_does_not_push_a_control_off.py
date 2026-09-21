"""A longer language may cost a line of text. It may not cost a CONTROL.

Two faults, both found by photographing the real app in Ukrainian on
2026-09-21 (issue #198, LackiUA's contributed catalogue), and both OURS rather
than the translation's — one of them visible in ENGLISH once it was looked for.

* **Three ⓘ help buttons cut in half on Create Chart ▸ Guided.** STILL OPEN,
  and said so here rather than left to be discovered. The rows themselves were
  half of it and are fixed below: a `QComboBox` makes its longest item the
  minimum width of its row, so the two Guided combos are `ElidingComboBox`
  now and the instrument row's minimum fell from 415 px to 227. That did NOT
  clear the overhang. Measured in a REAL window the same day: the panel is
  **565 px inside a 540 px viewport**, while its own `minimumSizeHint` is 260
  and its `sizeHint` 461 — so nothing in the panel asks for 565, the scroll
  area is simply handing it a width the viewport no longer has, and horizontal
  scrolling is off, so the last 25 px cannot be reached by any means. What
  lands there in English is empty space; in Ukrainian it is the ⓘ button on
  three rows. The row-minimum guard below holds the half that IS fixed.

* **Two buttons on every help card losing characters off both ends.** The
  footer split itself into three equal cells and four buttons do not fit a
  third, so a QHBoxLayout below the sum of its minimums let them clip. In
  ENGLISH at v4.3.0-beta.29 the button already painted `ave as PDF.` — no
  leading "S", no ellipsis — which is what settled that this was never a
  translation problem.

Both are asked here of real widgets in the language that exposed them, because
that is how they were found; a character count would have said nothing about
either.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QPushButton

from core import i18n
from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.settings import AppSettings
from ui.tabs.tab_chart import TabChart
from ui.widgets import ElidingComboBox

#: Ukrainian is the language that exposed both, and English is the control that
#: proves the fix is not language-specific.
LANGS = ("uk", "en")


@pytest.fixture(autouse=True)
def _reset_language(qapp):
    """English before AND after, and nothing of ours left alive in between.

    EVERY TEST HERE BUILDS A REAL TAB OR DIALOG IN A NON-ENGLISH LANGUAGE, and
    the first version of this file only put the language back. That was not
    enough: measured 2026-09-22, the everyday tier came out red in two runs of
    three with this file present and green twice in a row without it, in
    `MeasurementReportDialog` geometry tests that have nothing to do with
    Ukrainian -- a dialog 809 px tall against an 800 px offscreen screen. A
    widget that is merely hidden is still alive, still carries the metrics of
    the language it was built in, and `--dist loadfile` puts the next file on
    the same worker.

    So the language is reset on both sides and every top-level widget this
    file created is DESTROYED, not hidden, with the deferred deletes actually
    pumped before the next test starts.
    """
    from PyQt6.QtCore import QEvent
    i18n.set_language("en")
    before = {id(w) for w in QApplication.topLevelWidgets()}
    yield
    for w in QApplication.topLevelWidgets():
        if id(w) not in before:
            w.hide()
            w.setParent(None)
            w.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    i18n.set_language("en")


@pytest.fixture()
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return TabChart(ArgyllRunner(s), FileManager(s), s)


# ---------------------------------------------------------------------------
# Create Chart ▸ Guided: the ⓘ buttons stay inside the panel
# ---------------------------------------------------------------------------

def test_the_guided_combos_can_be_squeezed(tab):
    """The two combos that set this pane's width must elide, not push.

    NOT THE WHOLE FIX, and it is worth being plain about that: the ⓘ buttons
    are still 15 px past the viewport on screen for the separate reason in this
    file's docstring. What this holds is that the ROWS can compress, which they
    could not before — the instrument row's minimum fell from 415 px to 227
    (measured 2026-09-21, both languages) — so the panel is no longer wider
    than the pane because of its own content.

    MUTATION: change either back to `NoScrollComboBox` in `ui/tabs/tab_chart.py`
    and this goes red naming it.
    """
    for name, combo in (("instrument", tab._instr_combo),
                        ("paper size", tab._paper_combo)):
        assert isinstance(combo, ElidingComboBox), (
            f"the Guided {name} combo is a {type(combo).__name__}: its longest "
            "item becomes the minimum width of the 580 px pane, and the ⓘ "
            "button on its row is pushed off the right edge in any language "
            "whose label is longer than the English")


#: `left.setFixedWidth(580)` in every one of the four tabs, minus the scroll
#: area's own furniture. A row whose MINIMUM is wider than this cannot be shown
#: in full, and what disappears is the right-hand end of it.
_PANE_W = 580
_VIEWPORT_W = 540


@pytest.mark.parametrize("code", LANGS)
def test_no_guided_row_is_wider_than_the_pane_it_must_fit(tab, qapp, code):
    """The Guided rows must be able to COMPRESS into the 580 px pane.

    Asked of the row's minimum rather than of the painted geometry, and that
    was learned the hard way: the first version of this walked the ⓘ buttons
    and compared their right edge with their parent's width, and it passed
    happily with the fault put back — offscreen, the panel is simply given the
    room it asks for, so nothing is ever pushed anywhere. The minimum is the
    thing that decides, and it discriminates cleanly: measured 2026-09-21 with
    the eliding combo **227 px (en) / 232 px (uk)**, and with a plain
    `QComboBox` **415 px / 420 px** — which is what put the ⓘ off the edge on
    a real screen.

    MUTATION: change either Guided combo back to `NoScrollComboBox` and this
    goes red in both languages.
    """
    i18n.set_language(code)
    tab.resize(_PANE_W, 900)
    tab.show()
    qapp.processEvents()

    wide = []
    for name, combo in (("instrument", tab._instr_combo),
                        ("paper size", tab._paper_combo)):
        row = combo.parentWidget()
        if row is None:
            continue
        need = row.minimumSizeHint().width()
        if need > _VIEWPORT_W:
            wide.append(f"the {name} row cannot compress below {need} px, and "
                        f"the pane's viewport is {_VIEWPORT_W}: everything past "
                        f"that is off the edge, the ⓘ button included")
    tab.hide()
    assert not wide, f"[{code}] " + "\n  ".join(wide)


# ---------------------------------------------------------------------------
# The help card's footer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", LANGS)
def test_the_help_card_footer_gives_its_buttons_the_room_they_need(qapp, code,
                                                                   tmp_path):
    """No footer button is squeezed below the width its own label needs.

    `fit_button_width` has already worked out what each label costs and written
    it into the button's minimum. A layout that hands the cell less than the
    sum of those minimums does not shrink the buttons tidily, it lets them
    clip — which is why "Save as PDF…" painted as `ave as PDF.` in English.

    MUTATION: delete the `_balance_footer()` call in `ui/dialogs/
    welcome_dialog.py` and this goes red for both languages.
    """
    i18n.set_language(code)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.dialogs.welcome_dialog import WelcomeDialog
    dlg = WelcomeDialog(s, None, "light")
    dlg.resize(1180, 900)
    dlg.show()
    qapp.processEvents()
    dlg._on_card_clicked("first_profile")       # the page with all four buttons
    qapp.processEvents()

    # THE MECHANISM, NOT THE PAINTED WIDTH. Offscreen every widget is given
    # the room it asks for, so a guard that compared width with minimum passed
    # with the fault put back. What decides on a real screen is whether all
    # THREE footer cells carry a floor: the first fix set two of them and moved
    # the starvation onto the Ko-fi link in the middle, which then painted as
    # `дтримка Chr`.
    cells = {"left": dlg._footer_left, "mid": dlg._footer_mid,
             "right": dlg._footer_right}
    floorless = [name for name, c in cells.items()
                 if c.minimumWidth() < c.sizeHint().width()]
    sides = (dlg._footer_left.minimumWidth(), dlg._footer_right.minimumWidth())
    window_floor = dlg.minimumWidth()
    want = sum(c.minimumWidth() for c in cells.values())
    dlg.close()
    qapp.processEvents()
    assert not floorless, (
        f"[{code}] footer cell(s) {floorless} have no minimum of their own, so "
        "the layout may hand them less than their buttons need and the labels "
        "are cut at both ends")
    assert sides[0] == sides[1], (
        f"[{code}] the two side cells have different floors {sides}, so the "
        "Support link in the middle is no longer on the window's centre line")
    assert window_floor >= want, (
        f"[{code}] the window's own minimum is {window_floor} px and the three "
        f"footer cells need {want}: it can still be made too narrow to hold "
        "them, which is where the clipping came from")


def test_the_footer_keeps_its_centre_line(qapp, tmp_path):
    """The equal thirds were about the Support link sitting on the true centre,
    and the fix must not have bought the buttons' room by moving it."""
    i18n.set_language("uk")
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    from ui.dialogs.welcome_dialog import WelcomeDialog
    dlg = WelcomeDialog(s, None, "light")
    dlg.resize(1180, 900)
    dlg.show()
    qapp.processEvents()
    dlg._on_card_clicked("first_profile")
    qapp.processEvents()
    support = next(b for b in dlg.findChildren(QPushButton)
                   if "ChromIQ" in b.text() and b.isVisible()
                   and b is not dlg._close_btn)
    centre = support.mapTo(dlg, support.rect().center()).x()
    dlg.close()
    qapp.processEvents()
    assert abs(centre - dlg.width() // 2) <= 24, (
        f"the Support link sits at x={centre} in a {dlg.width()} px window; "
        "the footer's centre line has moved")


def test_an_eliding_widget_still_answers_with_the_whole_name(qapp):
    """Guard the guard for the parameter column: elision is only acceptable
    because nothing that READS the label sees the ellipsis."""
    from ui.widgets import ElidingCheckBox, ElidingLabel
    full = "Джерело відображення гами (відчуття + насиченість):"
    for cls in (ElidingLabel, ElidingCheckBox):
        w = cls(full)
        w.setFixedWidth(190)
        w.show()
        qapp.processEvents()
        painted = type(w).__mro__[1].text(w)
        assert w.text() == full, f"{cls.__name__}.text() lost the full name"
        assert painted != full, f"{cls.__name__} did not elide at 190 px"
        assert w.toolTip() == full, (
            f"{cls.__name__} elided without offering the full name on hover")
        w.hide()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Print Chart's four buttons
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ("uk", "en", "de"))
def test_the_print_chart_buttons_are_never_squeezed(qapp, code, tmp_path):
    """All four, in every language, at least as wide as they say they need.

    Sebastian photographed this row in Ukrainian and every one of the four was
    cut at BOTH ends. Measured in a real window the same day, this pane being
    locked to 580 px: in English each button's width is EXACTLY its own
    `minimumSizeHint` — the row fits with nothing to spare — and in Ukrainian
    all four were short, by 19, 19, 7 and 19 px. So the row was sized for
    English metrics and a language that needs more had nowhere to go.

    `minimumSizeHint` is the number that decides, not `minimumWidth`: the
    fitter's own floor was 110 px on all four and it is the STYLE's figure
    (154, 153, 117, 158 in Ukrainian) that says what the label needs. A sweep
    that asked about `minimumWidth` found nothing wrong with any of them.

    ASKED OF THE LAYOUT DECISION, NOT OF THE PAINTED WIDTHS, and that is not
    a detail. The first version of this compared each button's width with its
    `minimumSizeHint` and passed happily with the fault put back: offscreen,
    a widget is simply given the room it asks for, so nothing is ever squeezed
    and the guard could not see the thing it was written for. Which ROW each
    button is on is decided by font metrics, which are real offscreen.

    MUTATION: force the one-row branch in `ui/tabs/tab_print.py` (change the
    `need <= 580` test to `True`) and this goes red for uk and de.
    """
    i18n.set_language(code)
    from ui.tabs.tab_print import TabPrint
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabPrint(s)
    tab.resize(1360, 900)
    tab.show()
    qapp.processEvents()

    tops, hints = {}, {}
    for attr in ("_print_page_btn", "_print_all_btn",
                 "_clear_queue_btn", "_save_defaults_btn"):
        b = getattr(tab, attr, None)
        if b is None:
            continue
        tops[attr] = b.mapTo(tab, b.rect().topLeft()).y()
        hints[attr] = b.sizeHint().width()
    tab.hide()

    need = sum(hints.values())
    one_row = len(set(tops.values())) == 1
    if need + 24 <= 580:
        assert one_row, (
            f"[{code}] the four buttons need {need} px and fit the 580 px "
            "pane, but they have been split over two rows for nothing")
    else:
        assert not one_row, (
            f"[{code}] the four buttons want {need} px of a 580 px pane and "
            "are all on ONE row, so the layout is handing each of them less "
            "than it asked for and the labels are cut at both ends. "
            f"Widths asked for: {hints}")


def test_the_row_rule_itself_says_no_when_the_buttons_do_not_fit():
    """The rule, fed numbers, with no screen involved.

    The test above can only go red on a host whose fonts make the buttons too
    wide — under the offscreen plugin the four genuinely DO fit in every
    language, so a mutation that forces the one-row branch cannot be caught
    there. This one catches it anywhere: it is the same function the tab calls,
    given the widths measured on a real screen.

    MUTATION: make `buttons_fit_one_row` return True and this goes red.
    """
    from ui.tabs.tab_print import PANE_W, buttons_fit_one_row
    assert PANE_W == 580
    # English, measured on screen 2026-09-21: 122 + 110 + 111 + 110 = 453.
    assert buttons_fit_one_row([122, 110, 111, 110], 6) is True
    # Ukrainian the same day: 154 + 153 + 117 + 158 = 582, over the pane before
    # a single pixel of spacing. All four were cut at both ends.
    assert buttons_fit_one_row([154, 153, 117, 158], 6) is False
    # …and the boundary is the pane, not a number picked to suit the answer.
    assert buttons_fit_one_row([139, 139, 139, 139], 0) is True     # 580
    assert buttons_fit_one_row([139, 139, 139, 140], 0) is False    # 581


# ---------------------------------------------------------------------------
# A serif heading's last letter
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ("uk", "en", "de"))
def test_a_tab_heading_is_wide_enough_for_its_INK(qapp, code):
    """The ink box, not the advance box, is what has to fit.

    Sebastian reported this three times before it was believed: *"the last
    letter has a few px cut off"*. Measured on screen, the heading is Georgia
    at 30 px with `setLetterSpacing(85 %)`, and fourteen of fifteen headings
    across three languages were losing 1-2 px of their final glyph -- English
    and German included. `QLabel.sizeHint()` is built from `horizontalAdvance`,
    and a serif face's last glyph paints past the advance that reserves room
    for it, so the string "fits" by every width calculation and the ink does
    not.

    MUTATION: delete the `self._fit_title_ink()` call from `changeEvent` in
    `ui/tab_header.py` and this goes red in all three.
    """
    from PyQt6.QtGui import QFont, QFontMetrics
    from ui.tab_header import TabHeader
    i18n.set_language(code)
    h = TabHeader("STEP 02", i18n.tr("Print test chart"), "#ffb42d", None)
    # The font the STYLESHEET gives it, which is not the one it is built with.
    f = QFont("Georgia")
    f.setPixelSize(30)
    f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 85)
    h._title_lbl.setFont(f)
    h._fit_title_ink()
    h.show()
    qapp.processEvents()
    lbl = h._title_lbl
    fm = QFontMetrics(lbl.font())
    text = lbl.text()
    ink = max(fm.tightBoundingRect(text).right() + 1,
              fm.boundingRect(text).right() + 1)
    room = max(lbl.width(), lbl.minimumWidth())
    h.hide()
    qapp.processEvents()
    assert room >= ink, (
        f"[{code}] the heading {text!r} paints {ink} px of ink into {room} px: "
        f"{ink - room} px of its last letter is outside the label. Advance is "
        f"{fm.horizontalAdvance(text)}, which is why every width check says it "
        "fits")
