"""The chrome, in Neutral: the Index rule, and the sites the spectrum bar left.

The owner looked at the Neutral appearance the day it shipped and said *"there
is still very much color."* He was right, and this file is what stops it coming
back. It pins three things:

1. **The Index rule itself** — the geometry and the two colours the approved
   handoff specifies, at every step, and the fact that a rule is a *rule* and
   not a solid bar.
2. **Every screen site the spectrum bar occupied** now paints it, and paints
   not one hued pixel in Neutral: the masthead stripe, the tab bar (strips AND
   the active tab's tint), the dialog masthead rule, the Build Profile ramp,
   the splash.
3. **Light and Dark still paint all five hues at every one of them.** That is
   the guard: this whole change is allowed to move nothing outside Neutral, and
   a hue count is the cheapest way to catch it if it does.

THE APPEARANCE IS SET BY PALETTE ONLY, never by `apply_appearance`. An app-wide
`setStyleSheet` re-polishes every widget alive in the process and has already
crashed an xdist worker once when a theme suite shared one; `active_mode()`
identifies the appearance from the palette, which is all these need.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget

from ui import index_rule, neutral_styles
from ui.light_styles import make_light_palette
from ui.neutral_styles import make_neutral_palette
from ui.styles import TAB_COLORS, make_dark_palette

_PALETTES = {
    "light":   make_light_palette,
    "dark":    make_dark_palette,
    "neutral": make_neutral_palette,
}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def appearance(app):
    """Put the app into one appearance and put it back afterwards."""
    was = app.palette()

    def _set(mode: str):
        app.setPalette(_PALETTES[mode]())
        return mode

    yield _set
    app.setPalette(was)


def hues(image, tolerance: int = 6) -> int:
    """Non-grey pixels in an image — the instrument's own rule, inlined.

    `scripts/find_non_neutral_pixels` walks a live widget tree; here the
    question is about one painted surface, so only its definition of "grey" is
    borrowed: max(r,g,b) - min(r,g,b) <= tolerance.
    """
    n = 0
    for y in range(image.height()):
        for x in range(image.width()):
            c = image.pixelColor(x, y)
            if c.alpha() < 8:
                continue
            if max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue()) > tolerance:
                n += 1
    return n


def paint(w: int, h: int, fn) -> "QPixmap":
    pm = QPixmap(w, h)
    pm.fill(QColor(neutral_styles.NM_BG_WINDOW))
    p = QPainter(pm)
    fn(p)
    p.end()
    return pm


# ======================================================================
# 1. The component
# ======================================================================

def test_the_rule_is_five_cells_three_px_tall():
    """The handoff's geometry, verbatim: 5 cells, 3px tall, 2-3px gaps."""
    assert index_rule.CELLS == 5
    assert index_rule.CELL_H == 3
    assert 2 <= index_rule.GAP <= 3


def test_the_two_colours_are_action_and_border_hi_at_28_percent():
    filled, empty = index_rule.rule_colours()
    assert filled.name() == neutral_styles.NM_ACTION
    assert empty.name() == neutral_styles.NM_BORDER_HI
    assert empty.alpha() == round(0.28 * 255)


@pytest.mark.parametrize("step", [0, 1, 2, 3, 4, 5])
def test_exactly_step_cells_are_filled(step):
    """THE WHOLE POINT OF THE DRAFT. Identity is carried by how many cells are
    filled, so the count has to be exact at every step — including 0 and 5,
    the two a fence-post error hits first."""
    pm = paint(300, 3, lambda p: index_rule.paint_index_rule(p, 0, 0, 300, 3, step))
    img = pm.toImage()
    # Sample the middle of each cell rather than counting pixels: the cells are
    # the thing being asserted, and a gap is not a cell.
    span = 300 - index_rule.GAP * 4
    seen = []
    prev = 0
    for i in range(5):
        end = round(span * (i + 1) / 5)
        cx = prev + i * index_rule.GAP + (end - prev) // 2
        prev = end
        seen.append(img.pixelColor(cx, 1))
    filled = [c for c in seen if c.name() == neutral_styles.NM_ACTION]
    assert len(filled) == step
    assert seen[:step] == filled, "the filled cells must be the FIRST ones"


def test_the_rule_reaches_both_edges_and_is_not_a_solid_bar():
    pm = paint(300, 3, lambda p: index_rule.paint_index_rule(p, 0, 0, 300, 3, 5))
    img = pm.toImage()
    assert img.pixelColor(0, 1).name() == neutral_styles.NM_ACTION
    assert img.pixelColor(299, 1).name() == neutral_styles.NM_ACTION
    # Four gaps, each GAP wide, and none of them is ink.
    gaps = sum(1 for x in range(300)
               if img.pixelColor(x, 1).name() != neutral_styles.NM_ACTION)
    assert gaps == index_rule.GAP * 4, (
        "a rule with no gaps is a bar, and a bar says nothing about a step")


def test_the_rule_is_centred_in_a_taller_band_and_never_stretched():
    """The masthead's stripe is 6px and the splash's is 9. One thickness
    everywhere in the app, or the same part reads as two different parts."""
    pm = paint(300, 9, lambda p: index_rule.paint_index_rule(p, 0, 0, 300, 9, 5))
    img = pm.toImage()
    ink = [y for y in range(9)
           if img.pixelColor(5, y).name() == neutral_styles.NM_ACTION]
    assert ink == [3, 4, 5]


def test_only_neutral_uses_the_rule(appearance):
    for mode in ("light", "dark"):
        appearance(mode)
        assert not index_rule.use_index_rule()
        assert not index_rule.use_index_rule(mode)
    appearance("neutral")
    assert index_rule.use_index_rule()
    assert index_rule.use_index_rule("neutral")


# ======================================================================
# 2. Every site the spectrum bar occupied
# ======================================================================

def _spectrum_hues_in(image) -> set:
    names = {c.lower() for c in TAB_COLORS}
    found = set()
    for y in range(image.height()):
        for x in range(image.width()):
            n = image.pixelColor(x, y).name().lower()
            if n in names:
                found.add(n)
    return found


def test_the_masthead_wears_five_hues_and_neutral_wears_a_hairline(app, appearance):
    """THE INDEX RULE IS GONE FROM THE MASTHEAD, on the owner's instruction.

    2026-09-02: *"for neutral mode i want this indexing lines over every tab
    gone"*. The masthead stripe spans the whole window width, so it sat over
    all five tab columns and is the one he was pointing at.

    What is left is a 1px BORDER hairline across the very top. Not decoration:
    the masthead is BG_WINDOW and the system title bar above it is another
    light grey, so with the stripe gone the two met with no edge and the window
    had no top. Light and Dark keep all five spectrum hues, unchanged.
    """
    from ui.masthead_header import MastheadHeader
    head = MastheadHeader(version="9.9.9")
    head.resize(900, head.height())

    for mode in ("light", "dark"):
        appearance(mode)
        head.set_appearance(mode)
        img = head.grab().toImage()
        assert len(_spectrum_hues_in(img)) == 5, (
            f"{mode} must still wear all five spectrum hues")

    appearance("neutral")
    head.set_appearance("neutral")
    stripe_rows = []
    for step in (1, 3, 5):
        head.set_step(step)
        img = head.grab().toImage()
        stripe = img.copy(0, 0, head.width(), MastheadHeader.STRIPE_H)
        assert hues(stripe) == 0, "the masthead stripe still carries a hue"
        # NO CELLS. The rule painted ACTION cells; there must be none left, at
        # any step — the mid-band row is where they were.
        ink = sum(1 for x in range(head.width())
                  if stripe.pixelColor(x, MastheadHeader.STRIPE_H // 2).name()
                  == neutral_styles.NM_ACTION)
        assert ink == 0, (
            f"step {step}: {ink} px of the Index rule are still in the masthead")
        stripe_rows.append([stripe.pixelColor(x, 0).name()
                            for x in range(0, head.width(), 7)])
    # The hairline: row 0 is BORDER all the way across, and it does not move
    # with the step (it is an edge, not a readout).
    assert set(stripe_rows[0]) == {neutral_styles.NM_BORDER}, (
        "the masthead has no top edge in Neutral")
    assert stripe_rows[0] == stripe_rows[1] == stripe_rows[2], (
        "the top edge changes with the step — it is a rule again")
    # …and the band below it is the masthead ground, not a second line.
    img = head.grab().toImage()
    assert img.pixelColor(head.width() // 2, 3).name() == neutral_styles.NM_BG_WINDOW


def test_the_tab_bar_has_no_hue_no_rule_and_outlines_the_active_tab(app, appearance):
    from ui.spectrum_tab_bar import SpectrumTabBar
    tabs = QTabWidget()
    bar = SpectrumTabBar(tabs)
    tabs.setTabBar(bar)
    for name in ("1", "2", "3", "4", "5"):
        tabs.addTab(QWidget(), name)
    tabs.resize(1000, 200)
    tabs.show()
    app.processEvents()
    # The bar's own geometry, not the parent's: `tabRect` is in the bar's
    # coordinates and a grab is only as wide as the bar has actually been laid
    # out to be.
    app.processEvents()

    appearance("neutral")
    bar.set_appearance("neutral")
    tabs.setCurrentIndex(2)
    img = bar.grab().toImage()
    assert hues(img) == 0, (
        "the tab bar still carries a hue — the per-tab strips, or the active "
        "tab's tint, which measured 17.5% of this bar")

    # NO RULE ON ANY TAB. The five-cell strip is gone from the tab bar too —
    # the owner's 2026-09-02 instruction covers "every tab". The row it was
    # drawn on carries no ACTION anywhere along the bar.
    def rule_ink_on(i: int) -> int:
        r = bar.tabRect(i)
        hi = min(r.x() + r.width() - 2, img.width())
        return sum(1 for x in range(r.x() + 2, hi)
                   if img.pixelColor(x, r.y() + 1).name() == neutral_styles.NM_ACTION)

    for i in range(5):
        assert rule_ink_on(i) == 0, (
            f"tab {i} still carries the Index rule along its top edge")

    # …AND THE ACTIVE TAB IS STILL FINDABLE. It lost the rule and, with the
    # grounds collapsed onto one, its lighter fill as well, so it is marked by
    # an EDGE: BORDER_HI along the top and down both sides, open at the bottom
    # into the pane. Only the active tab has it.
    def outline_on(i: int) -> int:
        r = bar.tabRect(i)
        hi = min(r.x() + r.width() - 2, img.width())
        top = sum(1 for x in range(r.x() + 2, hi)
                  if img.pixelColor(x, r.y()).name() == neutral_styles.NM_BORDER_HI)
        return top

    assert outline_on(2) > 50, "the active tab has no mark at all"
    for i in (0, 1, 3, 4):
        assert outline_on(i) == 0, (
            f"tab {i} is not active and must carry no outline")
    # The sides, on the active tab only.
    r = bar.tabRect(2)
    y_mid = r.y() + r.height() // 2
    assert img.pixelColor(r.x(), y_mid).name() == neutral_styles.NM_BORDER_HI
    # The active tab's FILL is the trough's own value — the mark is the edge,
    # never a brighter ground (rule 1). Sampled beside the label, not through
    # it: the centre of a tab is where its text is.
    assert (img.pixelColor(r.x() + 5, y_mid).name()
            == neutral_styles.NM_BG_WINDOW)
    assert (img.pixelColor(bar.tabRect(0).x() + 5, y_mid).name()
            == neutral_styles.NM_BG_WINDOW), "an inactive tab moved"

    # Light and Dark keep the per-tab strips. The inactive hints are drawn at
    # alpha 60 over the trough, so only the active tab's 3px strip is the pure
    # hue — count hued pixels, and check the active strip is tab 3's own value.
    for mode in ("light", "dark"):
        appearance(mode)
        bar.set_appearance(mode)
        img2 = bar.grab().toImage()
        assert hues(img2) > 0, f"{mode} lost its per-tab strips"
        r = bar.tabRect(2)
        x = min(r.x() + r.width() // 2, img2.width() - 1)
        assert img2.pixelColor(x, r.y() + 1).name() == TAB_COLORS[2]


def test_the_splash_bar_is_the_rule_in_neutral(app):
    from ui.splash import make_splash_pixmap
    assert hues(make_splash_pixmap("neutral", "v9").toImage()) == 0
    for mode in ("light", "dark"):
        assert len(_spectrum_hues_in(make_splash_pixmap(mode, "v9").toImage())) == 5


def test_the_dialog_masthead_rule_takes_its_step_from_its_accent(app, appearance):
    from ui.styles import SPEC_GREEN
    from ui.tab_header import SpectrumStripe, dialog_masthead
    host = QWidget()
    _head, _hdr, stripe = dialog_masthead(host, "MEASURE", "Title",
                                          accent=SPEC_GREEN)
    assert stripe.step() == 3, "SPEC_GREEN is tab 3 — Measure"

    plain = SpectrumStripe()
    assert plain.step() == index_rule.ALL, (
        "a window with no place in the run wears the mark, not a readout")

    appearance("neutral")
    stripe.resize(400, SpectrumStripe.HEIGHT)
    assert hues(stripe.grab().toImage()) == 0
    appearance("light")
    assert len(_spectrum_hues_in(stripe.grab().toImage())) == 5


def test_the_build_profile_ramp_loses_its_hues(app, appearance):
    from ui.spectrum_progress import SpectrumSegmentsBar
    bar = SpectrumSegmentsBar()
    bar.resize(400, 46)
    for value in (None, 0.0, 0.42, 1.0):
        bar.set_value(value)
        appearance("neutral")
        assert hues(bar.grab().toImage()) == 0, (
            f"the ramp still carries a hue at value={value}")
        appearance("dark")
        assert hues(bar.grab().toImage()) > 0, (
            "dark must keep the five-colour ramp it always had")


def test_the_gradient_wash_is_action_in_neutral_only(app, appearance):
    from ui.gradient_overlay import GradientOverlay
    host = QWidget()
    host.resize(300, 200)
    appearance("light")
    ov = GradientOverlay(TAB_COLORS[0], parent=host)
    assert ov._color.name() == TAB_COLORS[0]
    appearance("neutral")
    ov.set_appearance("neutral")
    assert ov._color.name() == neutral_styles.NM_ACTION
    appearance("dark")
    ov.set_appearance("dark")
    assert ov._color.name() == TAB_COLORS[0], (
        "the wash must go back to the hue it was built with")


def test_the_tooltip_ring_is_one_value_in_neutral(app, appearance):
    """BOTH ways a colour reaches this button. The tab accent arrives through
    the class global; a tool dialog passes its own at construction and never
    goes past MainWindow at all."""
    from ui.tooltip_button import TooltipButton
    appearance("neutral")
    for btn in (TooltipButton("t", "b"),
                TooltipButton("t", "b", color=TAB_COLORS[2])):
        img = btn.icon().pixmap(18, 18).toImage()
        assert hues(img) == 0, "an ⓘ ring is still coloured in Neutral"
    appearance("light")
    coloured = TooltipButton("t", "b", color=TAB_COLORS[2])
    assert hues(coloured.icon().pixmap(18, 18).toImage()) > 0


# ======================================================================
# 3. The per-tab accent generator
# ======================================================================

def test_the_per_tab_sheet_carries_no_tab_hue_in_neutral(app, appearance):
    """26 of the 95 literal values lived in this one method."""
    from ui.main_window import MainWindow

    class _Stub:
        def __init__(self, mode):
            self._title_bar_mode = mode
            self._styled_tab_theme: dict[int, str] = {}
            self._tabs = QTabWidget()
            for _ in range(5):
                self._tabs.addTab(QWidget(), "t")

    appearance("neutral")
    for i in range(5):
        stub = _Stub("neutral")
        MainWindow._apply_tab_widget_styling(stub, i)
        qss = stub._tabs.widget(i).styleSheet()
        for hue in TAB_COLORS:
            assert hue not in qss, f"tab {i}'s sheet still carries {hue}"
        assert "#ffffff" not in qss, (
            "white on a light panel is 1.19:1 — the Calculated Patches number")
        assert neutral_styles.NM_ACTION in qss

    # …and the five sheets are IDENTICAL, which is the draft's stated trade.
    sheets = []
    for i in range(5):
        stub = _Stub("neutral")
        MainWindow._apply_tab_widget_styling(stub, i)
        sheets.append(stub._tabs.widget(i).styleSheet())
    assert len(set(sheets)) == 1

    # Light and Dark still get a per-tab hue, one per tab.
    for mode in ("light", "dark"):
        appearance(mode)
        seen = set()
        for i in range(5):
            stub = _Stub(mode)
            MainWindow._apply_tab_widget_styling(stub, i)
            qss = stub._tabs.widget(i).styleSheet()
            assert TAB_COLORS[i] in qss
            seen.add(qss)
        assert len(seen) == 5


def test_the_log_text_is_dark_ink_in_neutral(app, appearance):
    """The owner's ruling: log text is black or very dark grey. Before it, the
    per-tab accent was painted raw on the log and measured 1.63:1 in amber."""
    from ui.main_window import MainWindow, _darken_for_light_log

    class _Stub:
        def __init__(self, mode):
            self._title_bar_mode = mode
            self._styled_tab_theme: dict[int, str] = {}
            self._tabs = QTabWidget()
            for _ in range(5):
                self._tabs.addTab(QWidget(), "t")

    appearance("neutral")
    stub = _Stub("neutral")
    MainWindow._apply_tab_widget_styling(stub, 0)
    qss = stub._tabs.widget(0).styleSheet()
    # The per-tab sheet says nothing about the log at all: the theme's own
    # sheet already sets NM_LOG_TEXT, and one answer in one place is the point.
    assert "QPlainTextEdit#log" not in qss
    assert neutral_styles.NM_LOG_TEXT == neutral_styles.NM_TEXT_MAIN

    # Light is untouched — its log still gets the darkened tab accent.
    assert _darken_for_light_log(TAB_COLORS[1]) != TAB_COLORS[1]
    appearance("light")
    stub = _Stub("light")
    MainWindow._apply_tab_widget_styling(stub, 1)
    assert (_darken_for_light_log(TAB_COLORS[1])
            in stub._tabs.widget(1).styleSheet())


def test_the_tab_pane_is_the_panel_in_neutral(app, appearance):
    from ui.main_window import MainWindow

    class _Stub:
        pass

    for mode, expected in (("neutral", neutral_styles.NM_BG_PANEL),
                           ("light", "#ffffff"),
                           ("dark", "#181818")):
        stub = _Stub()
        stub._title_bar_mode = mode
        assert expected in MainWindow._compose_pane_qss(stub), (
            f"{mode}'s tab pane background is wrong — a dark pane behind a "
            f"light-grey window is a hole in the page")


def test_group_boxes_get_a_raised_surface_in_neutral(app, appearance):
    """Handoff: Stacked surface logic — panel L* 93, raised surface L* 97.

    Measured before this: Neutral's group boxes painted the LIGHT theme's cream
    `#f7f4ef`, 250,000 non-neutral pixels across the five tabs.
    """
    from PyQt6.QtGui import QPalette
    from PyQt6.QtWidgets import QGroupBox
    from ui.light_styles import LM_BG_SURFACE
    from ui.widgets import _apply_groupbox_surface

    def window_of(mode: str) -> str:
        appearance(mode)
        gb = QGroupBox("g")
        _apply_groupbox_surface(gb)
        return gb.palette().color(QPalette.ColorRole.Window).name()

    assert window_of("neutral") == neutral_styles.NM_BG_SURFACE
    assert window_of("light") == LM_BG_SURFACE
    # Dark has no raised surface and must not acquire one.
    appearance("dark")
    gb = QGroupBox("g")
    _apply_groupbox_surface(gb)
    assert gb.autoFillBackground() is False


def test_the_window_tells_the_masthead_which_step_it_is_on(app, appearance):
    """THE HOLE THE MUTATION FOUND. Every other check here proves the masthead
    PAINTS the step it is given; nothing proved anybody ever gives it one, and
    deleting the push left the whole suite green with a stripe frozen at step 1.

    The masthead has no idea which tab is current — it is a sibling of the tab
    widget, not its parent — so the window has to say, and it has to say it on
    every switch.
    """
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    win = MainWindow(AppSettings())
    try:
        for i in range(win._tabs.count()):
            win._tabs.setCurrentIndex(i)
            assert win._masthead._step == i + 1, (
                f"tab {i} is showing but the masthead's rule is at step "
                f"{win._masthead._step}")
    finally:
        win.close()
        win.deleteLater()
