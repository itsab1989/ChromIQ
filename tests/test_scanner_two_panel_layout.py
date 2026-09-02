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
                                       LANGUAGES, SMALLEST_SCREEN,
                                       handle_reach)

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
    assert res["worst"] <= SMALLEST_SCREEN - HEADROOM, (
        f"{lang} needs {res['worst']}px ({res['worst_state']}) — under "
        f"{HEADROOM}px of headroom on a {SMALLEST_SCREEN}px screen")
    assert not res["handles_out_of_reach"], (
        f"{lang}: " + "; ".join(res["handles_out_of_reach"]))


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
