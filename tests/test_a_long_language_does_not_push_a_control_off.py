"""A longer language may cost a line of text. It may not cost a CONTROL.

Two faults, both found by photographing the real app in Ukrainian on
2026-09-21 (issue #198, LackiUA's contributed catalogue), and both OURS rather
than the translation's — one of them visible in ENGLISH once it was looked for.

* **Five of the six ⓘ help buttons cut in half on Create Chart ▸ Guided.**
  FIXED 2026-09-22, and the sentence that used to stand here was wrong about
  why. It said *"nothing in the panel asks for 565, the scroll area is simply
  handing it a width the viewport no longer has"*, and that reading came from
  measuring the wrong object: `minimumSizeHint` was taken from the COMBO'S
  PARENT (260 px) rather than from the widget the scroll area actually holds.
  Asked of `sa.widget()`, that panel's minimum is **569 px against a 540 px
  viewport** — so something in the panel did ask for it, and the fault was
  ours to fix rather than the scroll area's to be blamed for.

  What asked: the "Chart Size" group put `-L`, its ⓘ, a stretch, `-P` and its
  ⓘ on ONE `QHBoxLayout`, and a box layout's minimum is the SUM of its items,
  527 px here however narrow the pane gets. `ui/option_pair_row.py` replaces
  that row with one that lays the same line out identically while it fits and
  drops `-P` to its own line when it cannot, so the row's minimum is now the
  WIDER OF THE TWO options rather than their sum, and the panel's fell from
  569 to 301.

  Measured on the downloaded v4.3.0-beta.30 arm64 dmg, driven on screen: the
  scroll area's `horizontalScrollBar().maximum()` was 29 with the bar
  `AlwaysOff`, so those 29 px could not be reached by any means a user has.
  Thirteen languages fitted and Ukrainian did not, but this was never a
  Ukrainian fault: Swedish stood **2 px** from the same cliff (538 against
  540). After the fix every shipped language has at least 230 px of headroom,
  and the geometry of all thirteen that already fitted is unchanged to the
  pixel, verified against HEAD in a worktree.

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
def make_tab(qapp, tmp_path):
    """Build the tab IN a language, because switching afterwards does nothing.

    **THIS FIXTURE REPLACED ONE THAT MADE EVERY LANGUAGE MEASURE ENGLISH.** The
    old `tab` fixture built the widget first and each test then called
    `i18n.set_language(code)`, but ChromIQ's catalogue is read when a string is
    constructed and the app applies a language change by restarting: a tab
    built in English keeps its English labels for ever. Measured 2026-09-22 at
    HEAD a083c6d6, the same group in the same process: built in English and
    then switched to Ukrainian it reports **495 px and its title is still
    "Chart Size"**; built in Ukrainian it reports **563 px** and is titled
    "Розмір діаграми". The first number is the one the parametrised guards in
    this file were comparing against the pane, fourteen times, in English.

    So the language goes in BEFORE the constructor, which is also the order the
    app itself uses.
    """
    made = []

    def _make(code: str):
        i18n.set_language(code)
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / f"s-{code}.ini"),
                          QSettings.Format.IniFormat)
        s.set("custom_output_path", str(tmp_path / "out"))
        t = TabChart(ArgyllRunner(s), FileManager(s), s)
        made.append(t)
        return t

    yield _make
    for t in made:
        t.hide()
        t.setParent(None)
        t.deleteLater()


# ---------------------------------------------------------------------------
# Create Chart ▸ Guided: the ⓘ buttons stay inside the panel
# ---------------------------------------------------------------------------

def test_the_guided_combos_can_be_squeezed(make_tab):
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
    tab = make_tab("en")
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
def test_no_guided_row_is_wider_than_the_pane_it_must_fit(make_tab, qapp,
                                                          code):
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
    tab = make_tab(code)
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


#: EVERY language ChromIQ ships, not the two that found the fault. Ukrainian
#: was 29 px over and Swedish 2 px under, so a guard that only asked the
#: language which happened to break would have called Swedish safe.
def _all_shipped_languages() -> list:
    return [code for code, _name in i18n.available_languages()]


def _panel_behind(widget):
    """The scrolling panel `widget` lives in, reached by walking UP.

    Not by searching for "the scroll area with the most help buttons in it":
    the first version of this did search, and offscreen it found a container
    holding 122 of them with an 82 px viewport, compared that against 540 and
    PASSED WITH THE FAULT PRESENT. A spin box the panel owns is an anchor a
    rename cannot quietly redirect.
    """
    from PyQt6.QtWidgets import QScrollArea
    w = widget
    while w is not None and not isinstance(w, QScrollArea):
        w = w.parentWidget()
    return None if w is None else w.widget()


#: The two panes of Create Chart, by an anchor widget each pane owns.
_PANES = (("Guided", "_pages_spin"), ("Manual", "_manual_pages_spin"))


@pytest.mark.parametrize("code", _all_shipped_languages())
@pytest.mark.parametrize("pane,anchor", _PANES, ids=[p for p, _ in _PANES])
def test_a_create_chart_pane_fits_its_viewport_in_every_language(
        make_tab, qapp, code, pane, anchor):
    """Neither Create Chart pane may demand more width than its viewport.

    THE WHOLE PANEL, NOT ONE GROUP, and that distinction is the finding of an
    adversary round rather than a refinement. The first version of this guard
    measured only the "Chart Size" group, and the panel holds five groups: a
    long translated string in any of the other four reproduced the exact fault
    this was written for while the guard stayed green. Measured by that round
    with a lengthened string in the Refinement group: panel 706 px against a
    540 px viewport, five of six help buttons clipped, guard 28/28 green.

    Measuring the group also left slack, because the group is narrower than the
    panel. On screen, panel minimum minus group minimum ran sv +4, fr +5,
    uk +6, pl +8, ja +24, so Swedish's real threshold was 544 rather than 540
    and a 3 px longer Swedish string would have clipped with this green.

    AND MANUAL IS COVERED NOW, because it is where the next one will happen.
    The fix that prompted this guard touched Guided only, and Manual sits in
    the same 540 px `ScrollBarAlwaysOff` viewport with, measured on screen,
    **18 px of room in Portuguese and 19 in French**.

    Asked of `minimumSizeHint` rather than painted geometry: offscreen a panel
    is handed whatever width it asks for, so nothing is ever pushed anywhere
    and a geometry check passes with the fault put back. The offscreen minimum
    also runs a little UNDER the on-screen one (fr Manual 503 here against 521
    on screen), so treat a small margin here as smaller still in a real window,
    and measure the real one with
    `scripts/drive_panel_overflow_per_language.py`.

    MUTATION, measured against HEAD a083c6d6 in a worktree: put the two Chart
    Size options back on one `QHBoxLayout` and the Guided case goes RED for
    `uk` at 563 against 540, green for the other thirteen.
    """
    tab = make_tab(code)
    tab.resize(_PANE_W, 900)
    tab.show()
    qapp.processEvents()

    anchor_widget = getattr(tab, anchor, None)
    panel = None if anchor_widget is None else _panel_behind(anchor_widget)
    need = None if panel is None else panel.minimumSizeHint().width()
    tab.hide()

    assert anchor_widget is not None, (
        f"TabChart has no {anchor!r} any more, so the {pane} pane was never "
        f"measured. Fix the anchor, do not delete the test."
    )
    assert panel is not None, (
        f"{anchor!r} is not inside a QScrollArea any more, so this measured "
        f"nothing."
    )
    assert need <= _VIEWPORT_W, (
        f"[{code}] the Create Chart {pane} pane cannot compress below {need} "
        f"px and its viewport is {_VIEWPORT_W}. The {need - _VIEWPORT_W} px "
        f"past the edge cannot be scrolled to, because that scroll area's "
        f"horizontal bar is off, and what sits at that edge is the column of "
        f"help buttons."
    )


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
