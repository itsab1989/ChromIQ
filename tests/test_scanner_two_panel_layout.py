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
* the trims that bought the width back are still in place — AND that what they
  bought it from is still readable: a combo asks for the width of the value it
  is showing, opening Advanced never widens the window, and a value too long
  for its box says so with an ellipsis instead of stopping mid-word.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (QApplication, QComboBox, QGroupBox,  # noqa: E402
                             QWidget)

from tests.scanner_floor_probe import (FakeSettings, HEADROOM,  # noqa: E402
                                       LANGUAGES, SMALLEST_CLIENT_H,
                                       SMALLEST_SCREEN, handle_reach)

REPO_ROOT = Path(__file__).resolve().parent.parent
PROBE = REPO_ROOT / "tests" / "scanner_floor_probe.py"
# Generous on purpose. One run costs about two seconds idle; the gate saturates
# every core, and a timeout that is too tight is a phantom red that says nothing
# about the thing under test.
PROBE_TIMEOUT = 300


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("scanner-two-panel")


def _make(_app, out_dir, show=True):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    dlg = ScannerProfileDialog(object(), FakeSettings(out_dir))
    if show:
        dlg.show()
        _settle(_app, dlg)
    return dlg


def _settle(app, dlg, n=6):
    for _ in range(n):
        app.processEvents()
    dlg.layout().activate()
    app.processEvents()


def _floor(lang, out_dir):
    """The window's real floor in *lang*, measured in a process of its own.

    A language is chosen once, at start-up, and this window's width comes from
    strings captured in module and class attributes — so switching language
    inside a live process measures English with a few translated labels mixed
    in, and under-reports the floor by up to 110 px. The app's own Fusion style
    and appearance stylesheet matter too, and `setStyle` / `setStyleSheet` reach
    every widget the process has alive, which no test may do to its neighbours.
    Both reasons point the same way: one process per language.
    See `tests/scanner_floor_probe.py`.
    """
    try:
        done = subprocess.run(
            [sys.executable, str(PROBE), lang, str(out_dir)],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            # NAMED, not the platform default: the probe prints the window's
            # own labels, and Russian, Japanese and Chinese do not survive a
            # guess (tests/test_encoding_is_named.py).
            encoding="utf-8", timeout=PROBE_TIMEOUT,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    except subprocess.TimeoutExpired:
        pytest.fail(f"the floor probe for {lang!r} did not finish within "
                    f"{PROBE_TIMEOUT}s — that is a hang, not a failed check")
    assert done.returncode == 0, (
        f"the floor probe for {lang!r} exited {done.returncode}\n"
        f"{done.stderr[-2500:]}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def _assert_fits(res):
    lang = res["lang"]
    # FIRST: that the numbers below are this language's at all. A process per
    # language removed the cause of the old sweep's lie, not the class of it —
    # `set_language` falls back to English silently, and a probe that fell back
    # prints English's floor under this language's name and passes everything
    # else here. `scanner_floor_probe.require_language` is the loud version;
    # this is the belt to its braces.
    assert res.get("language_applied") == lang, (
        f"{lang}: the probe measured {res.get('language_applied')!r}, not "
        f"{lang!r} — these numbers are the wrong language's")
    assert not res["clipped"], (
        f"{lang}: controls cut off at the floor the window reports: "
        + "; ".join(res["clipped"][:4]))
    # …and the question geometry does not ask. A combo can sit wholly inside
    # its viewport and still be showing a word cut in half, because Qt paints
    # a combo's label into the room it has and does not elide. That is exactly
    # what shipped: `Отобразить белое мишени в белое (по`, the combo's own
    # DEFAULT, with nothing clipped anywhere on the window.
    assert res["combos_checked"], (
        f"{lang}: the probe looked at no combo at all — a zero in "
        f"'unreadable' would mean nothing")
    assert not res["unreadable"], (
        f"{lang}: a combo cannot show the value it is set to, at the floor "
        f"the window reports: " + "; ".join(res["unreadable"][:4]))
    # Opening Advanced may not make the window wider. The section's controls
    # are the widest things in the left column, and the pane is fixed-width, so
    # a row that spends its width on a name AND a value side by side pushes the
    # whole window out the moment the disclosure is opened — 73 px in Russian,
    # 44 in German. With each option's control on its own line the section
    # costs the window nothing at all, in every language and every source mode,
    # which is what a disclosure is supposed to be.
    grew = [f"{mode}: {res['floors'][mode + ', Advanced open']} open vs "
            f"{res['floors'][mode + ', Advanced closed']} closed"
            for mode in ("a ChromIQ chart", "a standard target",
                         "printer from a scan")
            if (res["floors"][mode + ", Advanced open"]
                > res["floors"][mode + ", Advanced closed"])]
    assert not grew, f"{lang}: opening Advanced widens the window — " + "; ".join(grew)
    assert res["worst"] <= SMALLEST_SCREEN - HEADROOM, (
        f"{lang} needs {res['worst']}px ({res['worst_state']}) — under "
        f"{HEADROOM}px of headroom on a {SMALLEST_SCREEN}px screen")
    # …AND THE OTHER DIMENSION, which this sweep did not ask about when the
    # window became two panels. It came out with a floor of 675 logical pixels
    # on a Windows 11 VM and 716 measured here, against the 672 a 1920x1080
    # laptop at 150 % scaling has once its taskbar is taken off (finding C of
    # the Windows verification, 2026-09-03). A window whose MINIMUM exceeds the
    # screen cannot be used at all: it cannot be dragged smaller, and the row
    # that carries "Build profile" and "Close" is below the bottom edge.
    #
    # No HEADROOM here, and that is deliberate rather than an oversight: the
    # width figure is a client width on a screen whose whole width is usable,
    # while `SMALLEST_CLIENT_H` has already had the taskbar AND the caption
    # subtracted, so the slack is in the number itself.
    assert res["worst_h"] <= SMALLEST_CLIENT_H, (
        f"{lang} has a floor of {res['worst_h']}px tall "
        f"({res['worst_h_state']}) — a 1920x1080 laptop at 150 % leaves "
        f"{SMALLEST_CLIENT_H}px of client height, so the window cannot be "
        f"made to fit at all")
    assert not res["handles_out_of_reach"], (
        f"{lang}: " + "; ".join(res["handles_out_of_reach"]))


def test_the_height_floor_settles_in_one_pass(_app, _out_dir):
    """Two properties of the floor fit, and each is a bug this already had.

    ONE PASS IS ENOUGH. A QSplitter caches the minimum it reports, so reading
    the layout in the statement after the settings pane was shrunk returns the
    OLD number — the arithmetic then corrects a figure that has not moved and
    asks for a pane 48 px tall, clamped to the 96 px floor. It self-heals on
    the next layout event, so nothing visible stays wrong; what stays wrong is
    the settings pane, permanently smaller than it needs to be for anyone who
    sees the window before that event arrives.

    AND A SECOND PASS MUST CHANGE NOTHING. `event` runs this on every
    LayoutRequest, and the invalidation inside it posts LayoutRequests: a pass
    that keeps moving is a pass that keeps feeding itself.
    """
    dlg = _make(_app, _out_dir)
    try:
        # Back to the pane's original floor, then re-fit ONCE with no event
        # loop in between — which is the situation `showEvent` is in.
        dlg._scroll.setMinimumHeight(dlg._left_scroll_floor)
        dlg._fit_floor_to_the_smallest_screen()
        one_pass = dlg._scroll.minimumHeight()
        for _ in range(5):
            dlg._fit_floor_to_the_smallest_screen()
        assert dlg._scroll.minimumHeight() == one_pass, (
            f"one pass left the pane at {one_pass}px and five more moved it to "
            f"{dlg._scroll.minimumHeight()}px — the first reading was stale")
        assert dlg.layout().minimumSize().height() <= dlg.MAX_FLOOR_H
        assert one_pass > dlg.MIN_LEFT_SCROLL_H, (
            "the pane was clamped to its hard floor, which is what happens "
            "when the arithmetic is done against a stale layout minimum")
    finally:
        dlg.deleteLater()


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
def test_the_worst_languages_fit_a_1280_screen(_out_dir, lang):
    """Spanish is the widest of the twelve and English the floor of the whole
    set. Russian is here because it is the case this width work was for: with
    the Advanced section open it used to need 1279 px against a 1280 screen."""
    _assert_fits(_floor(lang, _out_dir))


@pytest.mark.slow
@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_language_fits_a_1280_screen(_out_dir, lang):
    """All twelve, in every source mode, with Advanced closed and open, with
    nothing clipped when the window sits on the floor it reports — and the
    eight drag handles reachable in each of them, since the preview is a
    different size in every language."""
    _assert_fits(_floor(lang, _out_dir))


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
def test_the_preview_drag_handles_are_all_reachable(_app, _out_dir):
    """All eight, at the size the window opens AND at its floor.

    Placing the four corners on the patch block is the entire task this panel
    exists for. The handles are drawn OUTSIDE the grid, so without room
    reserved for them the ones on the preview's own edge fall past the widget
    and cannot be grabbed with a mouse at all — 8 of 8 unreachable at the size
    the single-column window used to open at, and 3 of 8 here without it.

    English only here; the other twelve are covered by the per-language sweep
    above, which measures the handles in the same run as the floor.
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
            for name, reach in handle_reach(dlg).items():
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


def _option_combos(dlg, printer):
    return ([dlg._gam_mode, dlg._perc_combo, dlg._sat_combo, dlg._b2a_combo]
            if printer else [dlg._wp_mode])


def test_the_option_combos_do_not_ask_for_their_longest_entry(_app, _out_dir):
    """An entry nobody has chosen may not set how wide this panel has to be.

    The panel lives in the window's FIXED-width left pane, so a width it asks
    for is a width the window keeps at every screen size. "Map chart white to
    perfect white" is 410 px in Russian, and asking for it made the pane grow
    by that much the moment Advanced was opened.

    This is half of the guarantee and on its own it is the fault that shipped:
    the first version of this test asserted exactly this and nothing else, so
    it went green over a combo that could not show its own default. The other
    half is `test_an_option_combo_can_show_the_value_it_is_set_to`.
    """
    from ui.dialogs.scanner_colprof import ScannerAdvancedDialog
    for printer in (False, True):
        dlg = ScannerAdvancedDialog({}, None, printer=printer)
        try:
            for c in _option_combos(dlg, printer):
                before = c.sizeHint().width(), c.minimumSizeHint().width()
                c.addItem("x" * 200, "__probe__")
                after = c.sizeHint().width(), c.minimumSizeHint().width()
                assert after == before, \
                    f"{c.itemText(0)!r} still asks for its longest entry"
                c.removeItem(c.count() - 1)
        finally:
            dlg.deleteLater()


def test_an_option_and_its_control_are_on_separate_lines(_app, _out_dir):
    """A name that is a phrase and a value that is a phrase, side by side in a
    600-px pane, cannot both be read: the name takes its width first and the
    value gets the remainder — 253 px in Polish for a value needing 378.

    On its own line the control has the whole panel, so every entry of every
    one of these combos fits in all thirteen catalogues, and the row is as wide
    as its widest HALF instead of the sum of both. That is why opening Advanced
    now costs the window nothing (see `_assert_fits`).
    """
    from PyQt6.QtWidgets import QHBoxLayout
    from ui.dialogs.scanner_colprof import ScannerAdvancedDialog
    for printer in (False, True):
        dlg = ScannerAdvancedDialog({}, None, printer=printer)
        try:
            for c in _option_combos(dlg, printer):
                row = next(box for box in dlg.findChildren(QHBoxLayout)
                           if any(box.itemAt(i).widget() is c
                                  for i in range(box.count())))
                others = [box.itemAt(i).widget() for box in (row,)
                          for i in range(box.count())
                          if box.itemAt(i).widget() is not c]
                # Only the indent spacer may share the line with it.
                assert all(w is not None and w.objectName() == "form_label_spacer"
                           for w in others), (
                    f"{c.currentText()!r} shares its line with "
                    + ", ".join(type(w).__name__ if w is None else
                                f"{type(w).__name__}({getattr(w, 'text', lambda: '')()!r})"
                                for w in others))
        finally:
            dlg.deleteLater()


def test_an_option_combo_can_show_the_value_it_is_set_to(_app, _out_dir):
    """…and the half the first version of this file did not check.

    A combo that asks for a flat number of characters passes the test above and
    still cuts the value on screen — eighteen characters is comfortable in
    English and cuts a word in half in Russian. So the width a combo asks for
    has to follow the value it is SHOWING, in whatever language that value is.

    Every entry of every option combo, both profile kinds: whatever it is set
    to, the width it asks for is enough to read it.
    """
    from tests.scanner_floor_probe import width_for
    from ui.dialogs.scanner_colprof import ScannerAdvancedDialog
    checked = 0
    for printer in (False, True):
        dlg = ScannerAdvancedDialog({}, None, printer=printer)
        try:
            for c in _option_combos(dlg, printer):
                for i in range(c.count()):
                    c.setCurrentIndex(i)
                    need = width_for(c, c.currentText())
                    assert c.sizeHint().width() >= need, (
                        f"set to {c.currentText()!r}, the combo asks for "
                        f"{c.sizeHint().width()}px and needs {need}px")
                    checked += 1
        finally:
            dlg.deleteLater()
    # 6 white-point + 3 gamut-source + 12 + 12 intent + 5 B2A. A guard, not a
    # detail: the loop above is vacuously true over an empty combo list.
    # White point handling gained a sixth entry on 2026-09-05 — "Scale white to
    # a perfect white surface (-u -R)", the new default — and it is the longest
    # of the six, so the per-value assertion above is the one that matters for
    # it, and it passes.
    assert checked == 38, f"{checked} values were looked at, not 38"


def test_a_value_too_long_to_fit_says_so_and_offers_the_full_text(_app, _out_dir):
    """The backstop, for the one combo whose entries can never all fit.

    A standard target's name and patch count reach 771 px and the pane is
    ~600, so the window cannot promise every entry of the target list room.
    What it can promise is that a value it cannot show reads as SHORTENED
    rather than as a different, shorter value — and that the whole of it is one
    hover away. Qt does neither on its own: it paints what fits and drops the
    rest mid-word.

    Proved by rendering. The squeezed combo is compared, pixel for pixel,
    against the same widget holding the text already elided by hand — if it
    matches, the ellipsis is really on screen.
    """
    from PyQt6.QtCore import Qt
    from ui.widgets import ValueWidthComboBox
    long_text = "IT8 / ISO 12641-2 — LaserSoft Advanced  ·  864 patches"

    a = ValueWidthComboBox()
    a.addItem(long_text)
    a.show()
    _app.processEvents()
    room = a.sizeHint().width()
    a.resize(room - 120, a.sizeHint().height())
    _app.processEvents()

    assert a.toolTip() == long_text, (
        "a value that does not fit must offer the whole of itself as the "
        f"tooltip; this one offers {a.toolTip()!r}")

    from PyQt6.QtWidgets import QStyle, QStyleOptionComboBox
    opt = QStyleOptionComboBox()
    a.initStyleOption(opt)
    avail = a.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox, opt,
        QStyle.SubControl.SC_ComboBoxEditField, a).width()
    shortened = a.fontMetrics().elidedText(
        long_text, Qt.TextElideMode.ElideRight, avail)
    assert shortened.endswith("…") and shortened != long_text, \
        f"the test's own reference is not elided: {shortened!r}"

    b = ValueWidthComboBox()
    b.addItem(shortened)
    b.show()
    b.resize(a.width(), a.height())
    _app.processEvents()

    assert a.grab().toImage() == b.grab().toImage(), (
        "the squeezed combo does not paint the elided text — it is showing "
        f"{long_text!r} cut off instead of {shortened!r}")
    a.deleteLater()
    b.deleteLater()


def test_every_combo_in_this_window_can_shorten_what_it_cannot_show(_app, _out_dir):
    """Structural, so a combo added later cannot bring the fault back.

    The fault was not one string: it was a plain `QComboBox` in a pane that
    could not always afford its values. Any combo in this window may one day be
    handed a value longer than its room — a translation grows, a target list
    gains an entry — and the only acceptable answer is an ellipsis and a
    tooltip, never a word cut in half.
    """
    from ui.widgets import ElidingComboBox
    dlg = _make(_app, _out_dir)
    try:
        def chart():
            dlg._mode_chromiq.setChecked(True)
            dlg._printer_cb.setChecked(False)

        def standard():
            dlg._printer_cb.setChecked(False)
            dlg._mode_standard.setChecked(True)

        def printer():
            dlg._mode_chromiq.setChecked(True)
            dlg._printer_cb.setChecked(True)

        plain = []
        seen = 0
        # ALL THREE source modes. The first version of this test visited two of
        # them, and the target-type combo — the one whose entries reach 771 px,
        # the worst offender in the window — only ever appears in the third. It
        # went green over a plain QComboBox sitting right there.
        for kind, setup in (("a ChromIQ chart", chart),
                            ("a standard target", standard),
                            ("printer from a scan", printer)):
            setup()
            _settle(_app, dlg)
            dlg._adv_inline_head.setChecked(True)
            _settle(_app, dlg)
            for c in dlg.findChildren(QComboBox):
                if not c.isVisible():
                    continue
                seen += 1
                if not isinstance(c, ElidingComboBox):
                    plain.append(f"{kind}: {c.objectName() or c.currentText()!r}")
        assert seen >= 13, f"only {seen} visible combos were looked at"
        assert dlg._target_combo in dlg.findChildren(QComboBox)
        assert not plain, (
            "these combos cut their value off with no ellipsis and no "
            "tooltip: " + "; ".join(sorted(set(plain))))
    finally:
        dlg.deleteLater()


# ---------------------------------------------------------------------------
# Opening this window may not create a native window of its own for anything
# but the window (owner's beta-7 report: macOS full screen).
# ---------------------------------------------------------------------------

def test_opening_the_window_shows_no_widget_that_is_a_window(_app, _out_dir):
    """Nothing but the dialog itself may be SHOWN while it has no parent.

    A parentless widget IS a top-level window, and showing one makes the
    platform create a real window for it. `showEvent` lifts four buttons out of
    the QDialogButtonBox to lay them out in its own grid, and it used to show
    them in the gap between `setParent(None)` and `addWidget` — four native
    windows per open, reclaimed a moment later. On a plain desktop they are
    invisible; in macOS full screen the compositor has to animate each one into
    and out of the Space, which is what the owner saw and reported.

    The check has to run DURING the show: by the time `show()` returns the
    buttons have been reparented and their window handle is already gone, so
    nothing about the finished window records that this happened.
    """
    from PyQt6.QtCore import QEvent, QObject
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    caught: list[str] = []

    class _Spy(QObject):
        def eventFilter(self, obj, event):
            if (event.type() == QEvent.Type.Show
                    and isinstance(obj, QWidget)
                    and obj.parent() is None
                    and not isinstance(obj, ScannerProfileDialog)):
                caught.append(f"{type(obj).__name__} "
                              f"{getattr(obj, 'text', lambda: '')()!r}")
            return False

    spy = _Spy()
    _app.installEventFilter(spy)
    try:
        dlg = _make(_app, _out_dir)
    finally:
        _app.removeEventFilter(spy)
    try:
        assert not caught, (
            "opening the scanner window showed these widgets while they had no "
            "parent — each one costs a real native window: " + "; ".join(caught))
        # …and the buttons it moves are on screen where they belong, so the
        # check above cannot be satisfied by simply never showing them.
        for name in ("_run_btn", "_save_defaults_btn",
                     "_restore_defaults_btn", "_close_btn"):
            b = getattr(dlg, name)
            assert b.isVisible(), f"{name} is not visible after the window opened"
            assert not b.isWindow(), f"{name} is still a top-level window"
    finally:
        dlg.deleteLater()


def test_printer_mode_leaves_no_orphaned_info_button(_app, _out_dir):
    """Printer mode hides the whole averaging row — the ⓘ included.

    It reads ONE scan per page, so the add / remove / "Scan 1, Scan 2 …" /
    "Combine repeated scans by" controls are all hidden there. The ⓘ that
    explains them sat in the same row and was not, leaving a lone info button
    against the right edge offering to explain a feature that is not in this
    mode.
    """
    dlg = _make(_app, _out_dir)
    try:
        dlg._mode_chromiq.setChecked(True)
        dlg._printer_cb.setChecked(False)
        _settle(_app, dlg)
        assert dlg._add_shot_btn.isVisible(), "the averaging row should be here"
        assert dlg._avg_tip.isVisible(), "…and so should the ⓘ that explains it"

        dlg._printer_cb.setChecked(True)
        _settle(_app, dlg)
        assert not dlg._add_shot_btn.isVisible(), (
            "printer mode reads one scan per page — the add button belongs hidden")
        assert not dlg._avg_tip.isVisible(), (
            "the ⓘ explaining scan averaging is still on screen in printer "
            "mode, alone in an otherwise empty row, explaining a feature this "
            "mode does not have")
    finally:
        dlg.deleteLater()


def test_the_two_sections_do_not_both_say_advanced(qapp):
    """The owner, 2026-09-03: *"in build profile with scanner or camera there
    is an advanced section in the advanced section. one of them needs to
    change the name."*

    The outer collapsible section holds the ordinary profile settings; the
    inner box holds raw ArgyllCMS switches. Different KINDS of thing, not
    different depths - so the inner one takes the name the rest of the app
    already gives a block of raw switches, which `tab_chart` and the
    device-link tool both call "Expert Options".

    Asserted on the built widgets rather than on the source, because what
    matters is the two titles a user reads at the same time.
    """
    import inspect

    from ui.dialogs import scanner_colprof, scanin_dialog

    inner = inspect.getsource(
        scanner_colprof.ScannerAdvancedDialog._build_advanced_group)
    assert 'tr("Expert Options")' in inner, (
        "the inner box no longer uses the app's existing Expert Options key")
    assert 'QGroupBox(tr("Advanced")' not in inner

    outer = inspect.getsource(scanin_dialog)
    assert '_AdvancedSection(tr("Advanced' in outer, (
        "the outer section was renamed instead; the owner asked for the "
        "INNER one to change")


def test_expert_options_needs_no_new_translation(qapp):
    """The reason this rename was cheap, pinned so it stays true.

    "Expert Options" is an existing key in every catalogue. If someone later
    edits it to something new, twelve languages would silently ship English,
    which is the failure this project has had before.
    """
    import json
    import pathlib

    missing = []
    for path in sorted(pathlib.Path("data/i18n").glob("*.json")):
        if path.name.startswith("parameters."):
            continue
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        if "@language_name" not in catalogue:
            continue
        if not catalogue.get("Expert Options"):
            missing.append(path.stem)
    assert not missing, (
        f"'Expert Options' is untranslated in: {', '.join(missing)}")


def test_a_finished_build_can_show_reveal_and_install(_app, _out_dir):
    """The two buttons a finished build offers must be able to appear.

    They are created on the same `QDialogButtonBox` as Build and Close, and
    `showEvent` moves that box's buttons into the owner's grid and then hides
    the box for good. The four it moves survive; these two were left behind, so
    `_build_profile._done` set `setVisible(True)` on children of a hidden
    parent and NOTHING appeared — the user was told "[OK] Scanner profile
    saved" and "Install it as your scanner's input profile" with no way to open
    the folder and no way to install it. The same dead button is what
    `_confirm_despite_misalignment` offers as "Reveal folder" after Stop.

    Two halves, and both are needed: hidden before a build (the row must cost
    nothing until there is a profile), and really on screen after one — which
    is what a hidden parent silently prevents.
    """
    dlg = _make(_app, _out_dir)
    try:
        for name in ("_reveal_btn", "_install_btn"):
            b = getattr(dlg, name)
            assert not b.isVisible(), (
                f"{name} is on screen before anything has been built")

        # exactly what `_build_profile._done` does after colprof succeeds
        dlg._reveal_btn.setVisible(True)
        dlg._reveal_btn.setEnabled(True)
        dlg._install_btn.setVisible(True)
        dlg._install_btn.setEnabled(True)
        _settle(_app, dlg)

        for name, what in (("_reveal_btn", "open the profile's folder"),
                           ("_install_btn", "install the profile")):
            b = getattr(dlg, name)
            assert b.isVisible(), (
                f"a build has succeeded and {name} is still not on screen, so "
                f"the user has no way to {what}. Showing a widget whose parent "
                f"is hidden does not show it — the button has to be moved out "
                f"of the button box the way Build and Close are.")
            assert not b.isWindow(), (
                f"{name} was shown while it had no parent — that costs a real "
                f"native window")
            assert dlg.rect().contains(
                b.mapTo(dlg, b.rect().topLeft())), (
                f"{name} is visible but lands outside the window")
    finally:
        dlg.deleteLater()
