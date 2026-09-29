"""When the left pane of the scanner/camera window runs out of room, it stacks.

**A QVBoxLayout THAT RUNS OUT OF ROOM DOES NOT CLIP AND DOES NOT SCROLL — IT
LAYS ITS ROWS ON TOP OF ONE ANOTHER.** The left pane of
`Tools ▸ Build profile with scanner or camera` holds four things: the settings
scroll area, the spectrum busy bar, the four big buttons and the log. Three of
them cannot give — `fit_log_height` pins the log at min == max, the buttons are
two rows of real buttons, the bar is a fixed strip — and the fourth, the only
one that scrolls, held a hard `minimumHeight` of 120-136 px and refused.

Measured on the live window (agent BM, 2026-09-05, German, macOS, the window
forced under its own floor):

    pane 367 px (its own minimum is 447)   the spectrum bar painted 12 px into
                                           the settings area
    pane 287 px                            40 px
    pane 207 px                            the bar 46 px in, and the button
                                           grid a further 13 px on top of that

The pane is handed less than its minimum only when the WINDOW is — which is
finding C of the Windows verification, a floor of 675 logical pixels on a laptop
that has 672 — and it is what a new row in this column will do the moment
`MIN_LEFT_SCROLL_H` is already the binding constraint. Knut's proposed "Usage
Scenario:" selector (register item B8-71) is exactly such a row, and its own
entry names this as its layout prerequisite.

A scroll area that refuses to shrink is not protecting anything: it is choosing
to be painted over instead of scrolling. So it follows the room —
`ScannerProfileDialog._let_the_settings_pane_give`.

What is guarded here:

* no two rows of the left pane ever share pixels, at any height;
* the settings area keeps its comfortable height whenever the pane has room for
  it, so nothing moves in ordinary use — the window's floor is unchanged in all
  thirteen languages (1048-1178 x 640, measured before and after);
* the give is idempotent: a second pass moves nothing, because `event()` runs
  this on every LayoutRequest and the invalidation inside posts LayoutRequests.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                     # noqa: E402

from tests.scanner_floor_probe import FakeSettings           # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("scanner-left-pane")


def _make(app, out_dir):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    dlg = ScannerProfileDialog(object(), FakeSettings(out_dir))
    dlg.show()
    _settle(app, dlg, 8)
    return dlg


def _settle(app, dlg, n=6):
    for _ in range(n):
        app.processEvents()
    dlg.layout().activate()
    app.processEvents()


def _pane_rows(dlg):
    """The left pane's top-level rows, as (name, rect-in-the-pane)."""
    pane = dlg._left_pane_w
    lay = pane.layout()
    out = []
    for i in range(lay.count()):
        it = lay.itemAt(i)
        w = it.widget()
        if w is not None:
            if not w.isVisible():
                continue
            out.append((f"{i}:{type(w).__name__}", w.geometry()))
        else:
            r = it.geometry()
            if r.height() > 0:
                out.append((f"{i}:{'layout' if it.layout() else 'spacer'}", r))
    return out


def _stacked(dlg):
    """Rows of the left pane whose vertical extents share pixels.

    Two rows touching on one pixel is a rounding artefact of a layout, not a
    widget drawn over another; anything from two pixels up is paint the user
    sees.
    """
    rows = _pane_rows(dlg)
    bad = []
    for a in range(len(rows)):
        for b in range(a + 1, len(rows)):
            na, ra = rows[a]
            nb, rb = rows[b]
            lo, hi = max(ra.top(), rb.top()), min(ra.bottom(), rb.bottom())
            if hi - lo >= 2:
                bad.append(f"{na} [{ra.top()}..{ra.bottom()}] over "
                           f"{nb} [{rb.top()}..{rb.bottom()}] — {hi - lo + 1}px")
    return bad


#: Heights the window is pushed to, in logical pixels. 640 is the floor the
#: window reports in all thirteen languages; below it is where a window manager
#: on a screen too short for that floor leaves it, which is the state this file
#: exists for. 400 is well past any real screen and is here because a rule that
#: holds only just inside the measured range is a rule nobody can rely on.
_HEIGHTS = (900, 800, 700, 640, 560, 480, 400)


def test_the_left_panes_rows_never_sit_on_top_of_each_other(_app, _out_dir):
    dlg = _make(_app, _out_dir)
    try:
        assert not _stacked(dlg), (
            "the pane is already stacking at the size the window opens: "
            + "; ".join(_stacked(dlg)))
        for h in _HEIGHTS:
            # The minimum is dropped deliberately. The point of this file is
            # what happens when the window is SHORTER than its own floor, which
            # is not something the user can do with a drag and is exactly what a
            # screen too short for the floor does — the Windows VM's finding C.
            dlg.setMinimumHeight(0)
            dlg.resize(dlg.width(), h)
            _settle(_app, dlg, 6)
            bad = _stacked(dlg)
            assert not bad, (
                f"at {h}px the left pane lays its rows on top of each other "
                f"(pane {dlg._left_pane_w.height()}px, its layout asks for "
                f"{dlg._left_pane_w.layout().minimumSize().height()}px): "
                + "; ".join(bad[:4]))
    finally:
        dlg.deleteLater()


def test_the_settings_area_gives_only_what_the_pane_cannot_hold(_app, _out_dir):
    """It has to actually shrink, or the test above proves nothing.

    A pane that never runs short would pass the no-stacking rule for free. So:
    at a height the pane cannot hold, the settings area must be smaller than the
    comfortable height it is entitled to — and at a height it can, it must be
    exactly that height and not a pixel less.
    """
    dlg = _make(_app, _out_dir)
    try:
        _settle(_app, dlg)
        comfortable = dlg._settings_pane_floor
        assert comfortable > 0
        dlg.setMinimumHeight(0)
        dlg.resize(dlg.width(), 480)
        _settle(_app, dlg, 6)
        squeezed = dlg._scroll.minimumHeight()
        assert squeezed < comfortable, (
            f"the pane was 480px tall against a minimum of "
            f"{dlg._left_pane_w.layout().minimumSize().height()}px and the "
            f"settings area still held {squeezed}px — it did not give, so "
            f"something else in the pane did, and that is the stacking")
        dlg.resize(dlg.width(), 900)
        _settle(_app, dlg, 6)
        assert dlg._scroll.minimumHeight() == comfortable, (
            f"the room was handed back and the settings area stayed at "
            f"{dlg._scroll.minimumHeight()}px instead of {comfortable}px — "
            f"a squeeze that does not undo itself is a ratchet")
    finally:
        dlg.deleteLater()


def test_a_second_pass_moves_nothing(_app, _out_dir):
    """`event()` runs the fit on every LayoutRequest and the fit posts them."""
    dlg = _make(_app, _out_dir)
    try:
        dlg.setMinimumHeight(0)
        dlg.resize(dlg.width(), 560)
        _settle(_app, dlg, 6)
        first = dlg._scroll.minimumHeight()
        for _ in range(5):
            dlg._let_the_settings_pane_give()
        assert dlg._scroll.minimumHeight() == first, (
            f"one pass left the settings area at {first}px and five more moved "
            f"it to {dlg._scroll.minimumHeight()}px")
        assert dlg._let_the_settings_pane_give() is False, (
            "a pass that changes nothing still reports a change, so every "
            "layout event re-settles the splitter for no reason")
    finally:
        dlg.deleteLater()


def test_the_window_floor_is_unchanged_by_any_of_this(_app, _out_dir):
    """Nothing above may cost the ordinary window a pixel.

    The floor is `MAX_FLOOR_H` — 640 px of client height, which is what a
    1920x1080 laptop at 150 % scaling has left once the taskbar and the caption
    are taken off. Measured in all thirteen languages before and after this
    change: 1048-1178 px wide, 640 px tall, identical.
    """
    dlg = _make(_app, _out_dir)
    try:
        assert dlg.minimumHeight() <= dlg.MAX_FLOOR_H, (
            f"the window's floor is {dlg.minimumHeight()}px against the "
            f"{dlg.MAX_FLOOR_H}px a small laptop has")
        assert dlg._scroll.minimumHeight() == dlg._settings_pane_floor, (
            "the settings area is being squeezed at the size the window opens, "
            "which is not a state this fix is supposed to reach")
    finally:
        dlg.deleteLater()
