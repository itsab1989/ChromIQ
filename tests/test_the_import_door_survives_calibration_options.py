"""Switching on Preferences → Calibration options must not remove the IMPORT door.

Found by the combined adversary round of 2026-09-15, walking the run types on a
merged tree. It is a seam between two features that never met: #137's
calibration preference, and the measurement import door that #133 opened and
this week widened from verification runs to profiling ones.

WHAT THE PREFERENCE PROMISES, in its own Settings card
(`docs/design/calibration_run_type.md`): *"When active: the guided modes in all
tabs are hidden, 'Calibration' is added to the 'Run type' list …"*. What
`TabMeasure.set_calibration_mode` did was hide the whole **mode row**, and when
that line was written the row held two buttons, GUIDED and MANUAL, so the two
were the same thing. #133 then added a third button to the same row.

So from that day, a person with this preference on could not reach the import
module on ANY run type, and nothing on screen said why:

* `_import_available()` answered **True** on a profiling run;
* `_refresh_import_visibility()` duly called `_import_btn.setVisible(True)`;
* and the button's own parent was hidden underneath it, so
  `isVisible()` was **False** with `isVisibleTo(parent)` **True**.

Photographed on screen on a profiling run, the same project and the same run,
the preference the only difference (`~/Desktop/ChromIQ-beta18-proof/
combined-round-2/`, `H-measure-tab-calibration-mode-OFF.png` shows
`GUIDED | MANUAL | IMPORT`; `...-ON.png` shows no row at all).

Every test the import work shipped with asks `isVisibleTo(tab)` without ever
calling `set_calibration_mode`, which is why the whole set was green: the row
those tests measure through was never hidden in them.

THE FIX KEEPS THE PROMISE AND NOT THE IMPLEMENTATION. The GUIDED button is
hidden, which is the sentence; the row stays while it still offers a choice.
A calibration run still has no row, because there is nothing to choose there:
IMPORT is refused on a calibration for a data-safety reason (one `cal/`, no
`old/` archive), and MANUAL alone is the module already showing.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.measurement_target import (RUN_TYPE_CALIBRATION,  # noqa: E402
                                     RUN_TYPE_PROFILING,
                                     RUN_TYPE_VERIFICATION)


def _tab_on(tmp_path, qapp, run_type, *, calibration_options: bool):
    """A real Measure tab, with the preference set and the bar on *run_type*."""
    from tests.test_import_measurement_module import _env, _tab
    s, fm, ctl = _env(tmp_path)
    ctl.set_calibration_allowed(True)      # the bar coerces the value otherwise
    tab = _tab(s, fm, ctl)
    tab.set_calibration_mode(calibration_options)
    ctl.set_run_type(run_type)
    qapp.processEvents()
    assert str(ctl.target.run_type) == run_type, (
        "the control failed: the bar coerced the run type to %r"
        % ctl.target.run_type)
    return s, fm, ctl, tab


# ---------------------------------------------------------------------------

def test_the_import_button_is_reachable_with_calibration_options_on(
        tmp_path, qapp):
    """THE FAULT ITSELF, on a profiling run.

    `isVisibleTo(tab)` is False when ANY widget between the button and the tab
    is hidden, which is what the mode row was. Asked from the tab, not from the
    button's own parent, because a button nobody can press is not shown.

    MUTATION: put `set_calibration_mode` back to
    `self._mode_row_widget.setVisible(not enabled)` and this goes red.
    """
    _s, _fm, _ctl, tab = _tab_on(tmp_path, qapp, RUN_TYPE_PROFILING,
                                 calibration_options=True)
    assert tab._import_available(), (
        "the control failed: the import rule says no on a profiling run")
    assert tab._import_btn.isVisibleTo(tab), (
        "the IMPORT button cannot be reached with Preferences -> Calibration "
        "options on: the rule says %r, the button's own flag says %r, and the "
        "mode row it sits in says %r"
        % (tab._import_available(), tab._import_btn.isVisibleTo(
            tab._import_btn.parentWidget()),
           tab._mode_row_widget.isVisibleTo(tab)))


def test_pressing_it_reaches_the_import_module(tmp_path, qapp):
    """Reachable is not the same as working. The module behind the button has
    to come up, or the button is decoration.

    MUTATION: restore the old `set_calibration_mode` and this goes red, because
    `_switch_mode` is never asked.
    """
    _s, _fm, _ctl, tab = _tab_on(tmp_path, qapp, RUN_TYPE_PROFILING,
                                 calibration_options=True)
    tab._switch_mode("import")
    qapp.processEvents()
    assert tab._stack.currentIndex() == 2, (
        "pressing IMPORT left the tab on module %d" % tab._stack.currentIndex())


def test_the_guided_module_is_still_hidden(tmp_path, qapp):
    """THE PROMISE THIS MUST NOT BREAK: *"the guided modes in all tabs are
    hidden"*. The row came back; the GUIDED button did not.

    MUTATION: drop the `self._guided_btn.setVisible(not enabled)` line and this
    goes red.
    """
    _s, _fm, _ctl, tab = _tab_on(tmp_path, qapp, RUN_TYPE_PROFILING,
                                 calibration_options=True)
    assert not tab._guided_btn.isVisibleTo(tab), (
        "Preferences -> Calibration options is on and GUIDED is still offered")
    assert tab._stack.currentIndex() != 0, (
        "the tab is standing on the guided module while GUIDED is hidden")


def test_a_calibration_run_still_has_no_mode_row(tmp_path, qapp):
    """Nothing to choose there, so nothing is shown. A calibration cannot
    import (one `cal/`, no `old/` archive), and MANUAL alone is the module
    already on screen.

    MUTATION: make `_sync_mode_row_visibility` always show the row and this
    goes red.
    """
    _s, _fm, _ctl, tab = _tab_on(tmp_path, qapp, RUN_TYPE_CALIBRATION,
                                 calibration_options=True)
    assert not tab._import_available(), (
        "the control failed: a calibration run is offering the import door")
    assert not tab._mode_row_widget.isVisibleTo(tab), (
        "a calibration run is showing a mode row with nothing to choose in it")


def test_leaving_the_import_module_never_lands_on_the_hidden_guided_one(
        tmp_path, qapp):
    """The trap the fix would otherwise have introduced.

    `_refresh_import_visibility` leaves the import module by asking for
    "guided", which was safe while the module could not be entered at all with
    this preference on. Now that it can, that fallback would put a person on a
    module whose button is hidden, with no way back.

    MUTATION: delete the `if mode == "guided" and not self._guided_available()`
    clause from `_switch_mode` and this goes red on module 0.
    """
    _s, _fm, ctl, tab = _tab_on(tmp_path, qapp, RUN_TYPE_PROFILING,
                                calibration_options=True)
    tab._switch_mode("import")
    qapp.processEvents()
    assert tab._stack.currentIndex() == 2, "the control failed: not in IMPORT"
    ctl.set_run_type(RUN_TYPE_CALIBRATION)    # the one run type that refuses it
    qapp.processEvents()
    assert tab._stack.currentIndex() == 1, (
        "leaving the import module for a calibration left the tab on module "
        "%d, and GUIDED is hidden" % tab._stack.currentIndex())


def test_the_preference_off_is_exactly_as_it_was(tmp_path, qapp):
    """Nothing changes for the users who never switch it on: all three
    buttons, guided first."""
    for rt in (RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION):
        _s, _fm, _ctl, tab = _tab_on(tmp_path, qapp, rt,
                                     calibration_options=False)
        assert tab._mode_row_widget.isVisibleTo(tab)
        assert tab._guided_btn.isVisibleTo(tab)
        assert tab._import_btn.isVisibleTo(tab), (
            "%s: the IMPORT button is gone with the preference off" % rt)
