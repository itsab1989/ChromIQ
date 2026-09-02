"""The scanner/camera window is two panels, and it fits the screens it must.

The window used to be one tall column: German needed 1869 px of width, and
twelve wheel notches of scrolling to reach the bottom. It is now two panes —
the settings and the log on the left, the preview and everything that acts on
it on the right — with the long rows on two lines and the Advanced editor
folded in as a section instead of a modal.

What these guard:

* the two panes exist, and the right things are in each of them;
* NOTHING chooses the layout at run time — there is no environment switch and
  no second code path, so what ships is what was measured;
* every one of the twelve languages fits a 1280-px screen with room to spare,
  with Advanced closed AND open, in every source mode, with nothing clipped;
* the eight drag handles of the preview can all be reached, which is the whole
  job that panel exists for;
* Advanced is a live section: moving a control reaches the command, "Restore
  defaults" works, and each kind of profile shows and keeps its own options;
* the two trims that bought the width back are still in place.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect, QSize  # noqa: E402
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QComboBox,  # noqa: E402
                             QGroupBox, QLabel, QLineEdit, QSpinBox, QWidget)

from core.settings import DEFAULTS  # noqa: E402

# Every catalogue the Settings combobox offers, plus the English source.
LANGUAGES = ["en", "de", "fr", "es", "it", "nl", "no", "pl", "pt", "ru", "sv",
             "ja", "zh_CN"]
# The narrowest screen the window has to fit, and the room we insist on having
# left over. The measured worst is Spanish at 1186 — 94 px to spare.
SMALLEST_SCREEN = 1280
HEADROOM = 60


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    """A settings double built from DEFAULTS, with its own output root.

    `custom_output_path` defaults to "", and "" means `~/ChromIQ` — the real
    projects folder. This dialog provisions standard scanner targets under the
    output root when it opens, so the root is pinned per instance.
    """

    def __init__(self, out_dir, **overrides):
        self._store = {**DEFAULTS, **overrides}
        self._store["custom_output_path"] = str(out_dir)

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("scanner-two-panel")


def _make(_app, out_dir, show=True):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    dlg = ScannerProfileDialog(object(), _FakeSettings(out_dir))
    if show:
        dlg.show()
        _settle(_app, dlg)
    return dlg


def _settle(app, dlg, n=6):
    for _ in range(n):
        app.processEvents()
    dlg.layout().activate()
    app.processEvents()


def _clipped(dlg):
    """Every leaf control whose right edge falls outside its scroll viewport.

    A floor the window can be dragged to but at which a control is cut in half
    is not a floor: both panes pin their horizontal scrollbar off, so there is
    nothing to scroll the missing part back into view.
    """
    bad = []
    for scroll, side in ((dlg._scroll, "left"), (dlg._scroll_right, "right")):
        vp = scroll.viewport()
        for w in scroll.widget().findChildren(QWidget):
            if not w.isVisible() or w.findChildren(QWidget):
                continue
            if not isinstance(w, (QAbstractButton, QLabel, QLineEdit,
                                  QComboBox, QSpinBox)):
                continue
            left = w.mapTo(vp, w.rect().topLeft()).x()
            if left + w.width() > vp.width() + 1:
                bad.append(f"{side}: {type(w).__name__} "
                           f"+{left + w.width() - vp.width()}px")
    return bad


def _states(dlg, app):
    """Every state that changes how wide the window has to be: the three source
    modes, each with the Advanced section closed and open."""
    def chart():
        dlg._mode_chromiq.setChecked(True)
        dlg._printer_cb.setChecked(False)

    def standard():
        dlg._printer_cb.setChecked(False)
        dlg._mode_standard.setChecked(True)

    def printer():
        dlg._mode_chromiq.setChecked(True)
        dlg._printer_cb.setChecked(True)

    for name, setup in (("a ChromIQ chart", chart),
                        ("a standard target", standard),
                        ("printer from a scan", printer)):
        for advanced in (False, True):
            setup()
            _settle(app, dlg)
            dlg._adv_inline_head.setChecked(advanced)
            _settle(app, dlg)
            yield (f"{name}, Advanced "
                   + ("open" if advanced else "closed")), dlg.minimumWidth()
    dlg._adv_inline_head.setChecked(False)
    _settle(app, dlg)


def _floor_check(app, out_dir, lang):
    """The window's floor in *lang*, and whether it clips when sat on it."""
    from core.i18n import set_language
    set_language(lang)
    try:
        dlg = _make(app, out_dir)
        try:
            worst = ("", 0)
            for state, floor in _states(dlg, app):
                if floor > worst[1]:
                    worst = (state, floor)
            # …and now sit the window on that floor and look for damage.
            for state, floor in _states(dlg, app):
                dlg.resize(floor, 900)
                _settle(app, dlg, 8)
                bad = _clipped(dlg)
                assert not bad, f"{lang}, {state}, at {floor}px: {bad}"
            return worst
        finally:
            dlg.deleteLater()
    finally:
        set_language("en")


# --------------------------------------------------------------- the panes
def test_the_window_is_two_panes(_app, _out_dir):
    """The settings on the left, the preview and its controls on the right —
    and the log, the buttons and the spectrum bar under the LEFT pane only,
    which is what stops the window being as wide as its widest button row."""
    dlg = _make(_app, _out_dir)
    try:
        left, right = dlg._scroll.widget(), dlg._scroll_right.widget()
        assert dlg._marquee in right.findChildren(type(dlg._marquee))
        assert dlg._use_fiducials_cb in right.findChildren(
            type(dlg._use_fiducials_cb))
        # the profile settings stayed on the left
        assert dlg._ptype in left.findChildren(type(dlg._ptype))
        assert dlg._adv_inline in left.findChildren(type(dlg._adv_inline))
        # the log and the four big buttons are inside the left pane's column,
        # not across the whole window
        assert dlg._log.parentWidget() is not None
        assert dlg._left_pane_w.isAncestorOf(dlg._log)
        for b in (dlg._run_btn, dlg._close_btn, dlg._save_defaults_btn,
                  dlg._restore_defaults_btn):
            assert dlg._left_pane_w.isAncestorOf(b), b.text()
        assert not dlg._button_box.isVisible()
    finally:
        dlg.deleteLater()


def test_nothing_chooses_the_layout_at_run_time():
    """No environment switch, and no second code path behind one.

    While this was a proposal the two-panel window lived behind
    CHROMIQ_SCANIN_TWO_PANEL and five `if` branches that could still build the
    old single column. A feature reachable only through a hidden variable is
    not shipped, and a second layout nobody looks at is a second layout nobody
    maintains — so both are gone, and this fails if either comes back.
    """
    from ui.dialogs import scanin_dialog
    src = inspect.getsource(scanin_dialog)
    for smell in ("CHROMIQ_SCANIN", "_reflow_two_panel",
                  "_reflow_full_proposal", "_TWO_PANEL_CUTS", "self._wrap"):
        assert smell not in src, f"{smell} is still in the scanner window"


def test_the_pane_cut_is_recorded_not_counted(_app, _out_dir):
    """Which rows go right is recorded as they are BUILT, not written down as
    a pair of indices — so inserting a row above the preview cannot silently
    move the cut and send half the settings into the wrong pane."""
    dlg = _make(_app, _out_dir, show=False)
    try:
        assert dlg._right_first < dlg._right_last
    finally:
        dlg.deleteLater()


# --------------------------------------------------------------- the width
@pytest.mark.parametrize("lang", ["en", "es", "ru"])
def test_the_worst_languages_fit_a_1280_screen(_app, _out_dir, lang):
    """Spanish is the widest of the twelve and Russian the widest with the
    Advanced section open; English is the floor of the whole set."""
    state, floor = _floor_check(_app, _out_dir, lang)
    assert floor <= SMALLEST_SCREEN - HEADROOM, \
        f"{lang} needs {floor}px ({state}) — under {HEADROOM}px of headroom"


@pytest.mark.slow
@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_language_fits_a_1280_screen(_app, _out_dir, lang):
    """All twelve, in every source mode, with Advanced closed and open, with
    nothing clipped when the window is sat on the floor it reports."""
    state, floor = _floor_check(_app, _out_dir, lang)
    assert floor <= SMALLEST_SCREEN - HEADROOM, \
        f"{lang} needs {floor}px ({state}) — under {HEADROOM}px of headroom"


def test_the_floor_is_the_layouts_own_not_the_opening_width(_app, _out_dir):
    """MIN_WIDTH is the width the window OPENS at. If it were also the floor,
    a 1280-px screen would never see the window with room to spare."""
    dlg = _make(_app, _out_dir)
    try:
        assert dlg.minimumWidth() < dlg.MIN_WIDTH
        assert dlg.minimumWidth() == dlg.layout().minimumSize().width()
    finally:
        dlg.deleteLater()


# ------------------------------------------------------------- the handles
def _handles(dlg):
    """Each of the eight drag handles, and how much of its grab area is inside
    the preview pane's viewport and clear of that pane's scrollbar."""
    from PyQt6.QtWidgets import QScrollArea
    import ui.scan_grid_marquee as sgm
    corner, side = int(sgm._HANDLE_R * 2.4), int(sgm._SIDE_R * 2.8)
    mq = dlg._marquee
    host = mq
    while host is not None and not isinstance(host, QScrollArea):
        host = host.parentWidget()
    vp = host.viewport()
    vp_rect = QRect(vp.mapTo(dlg, QPoint(0, 0)), vp.size())
    vbar = host.verticalScrollBar()
    bar = (QRect(vbar.mapTo(dlg, QPoint(0, 0)), vbar.size())
           if vbar.isVisible() else QRect())

    names = ["top-left", "top-right", "bottom-right", "bottom-left",
             "top", "right", "bottom", "left"]
    out = {}
    for i, name in enumerate(names):
        p = mq._handle_pos(i) if i < 4 else mq._side_handle_pos(i - 4)
        r = corner if i < 4 else side
        box = QRect(mq.mapTo(dlg, QPoint(int(p.x()) - r, int(p.y()) - r)),
                    QSize(r * 2, r * 2))
        area = box.width() * box.height()
        seen = vp_rect.intersected(box)
        hidden = bar.intersected(box)
        out[name] = ((seen.width() * seen.height())
                     - (hidden.width() * hidden.height())) / area
    return out


def test_the_preview_drag_handles_are_all_reachable(_app, _out_dir):
    """All eight, at the size the window opens AND at its floor.

    Placing the four corners on the patch block is the entire task this panel
    exists for. The handles are drawn OUTSIDE the grid, so without room
    reserved for them the ones on the preview's own edge fall past the widget
    and cannot be grabbed with a mouse at all — 8 of 8 unreachable at the size
    the single-column window used to open at, and 3 of 8 here without it.
    """
    dlg = _make(_app, _out_dir)
    try:
        dlg._mode_standard.setChecked(True)
        dlg._refresh()
        dlg._reveal_target_files()
        _settle(_app, dlg, 8)
        opened = (dlg.width(), dlg.height())
        for tag, size in (("as it opens", opened),
                          ("at its floor",
                           (dlg.minimumWidth(), dlg.minimumHeight()))):
            dlg.resize(*size)
            _settle(_app, dlg, 4)
            dlg._marquee._recompute_fit()
            _settle(_app, dlg, 4)
            for name, reach in _handles(dlg).items():
                assert reach > 0.6, (
                    f"{name} handle is {reach:.0%} reachable {tag} "
                    f"({size[0]}x{size[1]})")
    finally:
        dlg.deleteLater()


# -------------------------------------------------------------- Advanced
def _adv_groups(dlg):
    return sorted(g.title() for g in dlg._adv_inline_body.findChildren(QGroupBox))


def test_advanced_is_a_live_section_of_this_window(_app, _out_dir):
    """It is not a picture of the old modal: moving a control reaches the
    command that will be run, and "Restore defaults" puts it back.

    While this was a proposal the section's controls were re-parented in and
    then never read again — every switch in it was inert, and the Restore
    defaults button was connected to nothing at all.
    """
    dlg = _make(_app, _out_dir)
    try:
        assert "-ni" not in dlg._cmd_preview.text()
        dlg._adv_editor._flags["-ni"].setChecked(True)
        _settle(_app, dlg)
        assert "-ni" in dlg._cmd_preview.text()
        assert dlg._adv_vals.get("-ni") is True
        dlg._restore_defaults_btn.click()
        _settle(_app, dlg)
        assert "-ni" not in dlg._cmd_preview.text()
    finally:
        dlg.deleteLater()


def test_advanced_shows_the_options_of_the_profile_being_built(_app, _out_dir):
    """A printer profile and a scanner profile expose different colprof
    options (#121), and each remembers its own. The section is rebuilt when the
    kind changes, exactly as the modal was rebuilt every time it was opened."""
    dlg = _make(_app, _out_dir)
    try:
        scanner = _adv_groups(dlg)
        assert any("White" in t for t in scanner)
        assert not any("Gamut" in t for t in scanner)
        dlg._adv_editor._flags["-ni"].setChecked(True)
        _settle(_app, dlg)

        dlg._printer_cb.setChecked(True)
        _settle(_app, dlg, 8)
        printer = _adv_groups(dlg)
        assert any("Gamut" in t for t in printer)
        assert not any("White" in t for t in printer)
        # a printer profile keeps its own settings, so it did not inherit -ni
        assert not dlg._adv_vals.get("-ni")

        dlg._printer_cb.setChecked(False)
        _settle(_app, dlg, 8)
        assert _adv_groups(dlg) == scanner
        assert dlg._adv_vals.get("-ni") is True     # …and the scanner kept its
        assert "-ni" in dlg._cmd_preview.text()
    finally:
        dlg.deleteLater()


# ----------------------------------------------------------------- the trim
def test_the_advanced_switches_are_one_column(_app, _out_dir):
    """Two across, this row was the widest thing in the whole Advanced panel in
    all twelve languages — 689 px in Russian against 321 for the widest
    measurement row — and the panel sits in the fixed-width left pane, so that
    one row set how far the pane had to grow when Advanced was opened."""
    from ui.dialogs.scanner_colprof import ScannerAdvancedDialog
    dlg = ScannerAdvancedDialog({}, None, printer=False)
    try:
        grp = [g for g in dlg.findChildren(QGroupBox)
               if g.layout().__class__.__name__ == "QGridLayout"][0]
        lay = grp.layout()
        rows = {lay.getItemPosition(i)[0] for i in range(lay.count())}
        checks = [w for w in grp.findChildren(QWidget)
                  if w.__class__.__name__ == "QCheckBox"]
        assert len(rows) == len(checks), \
            "the Advanced switches are back on more than one per row"
        widest = max(c.sizeHint().width() for c in checks)
        assert grp.minimumSizeHint().width() < widest * 2
    finally:
        dlg.deleteLater()


def test_the_option_combos_do_not_ask_for_their_longest_entry(_app, _out_dir):
    """These combos take the stretch slot in their row, so capping the width
    they ASK for changes nothing at any real window width and the drop-down
    still shows every name in full — but it is worth 145 px of window floor in
    Spanish, and the difference between fitting a 1280 screen and not."""
    from ui.dialogs.scanner_colprof import ScannerAdvancedDialog
    for printer in (False, True):
        dlg = ScannerAdvancedDialog({}, None, printer=printer)
        try:
            combos = [dlg._gam_mode, dlg._perc_combo, dlg._sat_combo,
                      dlg._b2a_combo] if printer else [dlg._wp_mode]
            for c in combos:
                assert c.sizeAdjustPolicy() == \
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                # The proof, not the setting: give it an absurdly long entry
                # and see whether the width it asks for follows.
                before = c.sizeHint().width()
                c.addItem("x" * 200, "__probe__")
                assert c.sizeHint().width() == before, \
                    f"{c.itemText(0)!r} still asks for its longest entry"
                c.removeItem(c.count() - 1)
        finally:
            dlg.deleteLater()
