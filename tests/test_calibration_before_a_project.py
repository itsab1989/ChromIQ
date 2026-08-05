"""#130 — Calibration can be chosen before any project exists.

Knut, 2026-08-05, ruling on the three options put to him: **"Go with option 2."**

The bar used to grey BOTH dropdowns whenever no profile project was loaded —
State B, Hole 7 — and the hint gave the reason: *"…then you may choose a
profile run."* That reason is about the **Profile run** box. #137 then made
Calibration the one run type that does not use that box at all (there is
exactly one calibration per project, so it is fixed and disabled). So the
single case the greying could not justify was the one step that comes FIRST in
the work: you calibrate the printer, then you profile it, then you verify it.

Reaching it used to require generating a profiling chart nobody wanted.
"""
from __future__ import annotations

import pytest

from core.measurement_target import (RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING,
                                     RUN_TYPE_VERIFICATION)


@pytest.fixture
def empty_bar(qapp, tmp_path, monkeypatch):
    """A bar with NO project open — the state this is all about."""
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)

    st = AppSettings()
    monkeypatch.setattr(st, "get",
                        lambda k, d=None, _o=st.get: str(tmp_path)
                        if k == "custom_output_path" else _o(k, d))
    ctl = MeasurementTargetController(FileManager(st))
    assert ctl.project_or_none() is None, "this fixture is about having none"
    return MeasurementTargetBar(ctl), ctl


def test_run_type_is_usable_with_no_project_when_calibration_is_on(empty_bar):
    bar, ctl = empty_bar
    bar.set_calibration_allowed(True)
    assert bar._type_combo.isEnabled(), (
        "Calibration is the first step of the work and needs no run — it must "
        "be reachable from a clean app"
    )


def test_the_profile_run_box_stays_greyed_with_no_project(empty_bar):
    """Option 2 changed one box, not two. There is still no run to pick."""
    bar, ctl = empty_bar
    bar.set_calibration_allowed(True)
    assert not bar._run_combo.isEnabled()
    assert not bar._verify_combo.isEnabled()


def test_calibration_can_actually_be_selected_with_no_project(empty_bar):
    bar, ctl = empty_bar
    bar.set_calibration_allowed(True)
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    assert ctl.target.run_type == RUN_TYPE_CALIBRATION


def test_nothing_changes_with_the_preference_off(empty_bar):
    """T8 — with calibration switched off, the app behaves exactly as before:
    no project, no Run type."""
    bar, ctl = empty_bar
    bar.set_calibration_allowed(False)
    assert not bar._type_combo.isEnabled()
    assert not bar._run_combo.isEnabled()


def test_the_hint_says_calibration_is_available_when_it_is(empty_bar):
    """A sentence telling you to go and make a chart first, beside a dropdown
    you can use right now, is worse than no sentence at all."""
    bar, ctl = empty_bar
    bar.set_calibration_allowed(True)
    assert "Calibration needs no run" in bar._hint.text()
    assert bar._hint.isVisibleTo(bar), "the hint is still shown; only its words change"


def test_the_hint_is_not_cut_off_by_the_row_pin(empty_bar, qapp):
    """The row is pinned to what it needs — INCLUDING the hint.

    Basti hit both sides of this in one afternoon. Pinning the row to its
    controls cut the sentence off (*"the text in the bar is now clipping"*);
    letting the hint's own sizeHint decide put the controls back in the middle
    of empty space (*"too much space over and below the bar's elements"*). The
    sentence's sizeHint claims three lines at a width it is not given, while
    the text needs one — so neither number is the row's height on its own.

    Asserted as the property, not the mechanism: whatever the row is pinned to,
    the sentence must fit in it.
    """
    bar, ctl = empty_bar
    bar.set_calibration_allowed(True)
    bar.resize(1400, 40)
    bar.show()
    qapp.processEvents()
    hint = bar._hint
    assert hint.isVisible() and hint.width() > 0
    needs = hint.heightForWidth(hint.width())
    assert hint.height() >= needs, (
        f"the sentence needs {needs} px at {hint.width()} px wide and has "
        f"{hint.height()} — it is being cut off"
    )
    bar.hide()


def test_the_row_is_no_taller_than_what_is_in_it(empty_bar, qapp):
    """…and the other side: no slack for the controls to float in."""
    bar, ctl = empty_bar
    bar.set_calibration_allowed(True)
    bar.resize(1400, 40)
    bar.show()
    qapp.processEvents()
    controls = max(bar._run_combo.height(), bar._delete_btn.height())
    needs = bar._hint.heightForWidth(bar._hint.width())
    assert bar.maximumHeight() <= max(controls, needs) + 1, (
        f"the row is capped at {bar.maximumHeight()} px when the tallest "
        f"thing in it is {max(controls, needs)} — the controls will sit in "
        f"the middle of the slack"
    )
    bar.hide()


def test_the_bar_does_not_resize_a_beat_after_it_is_shown(empty_bar, qapp):
    """The pin must act on the refresh that changed things, not the next one.

    Basti, beta.142: *"when loading the app now something in the bar changes
    its size. first it seems to look good and then it gets bigger and there is
    more space under the bars elements again."*

    `_update_location()` — which pins — runs at the TOP of the refresh, and
    `_hint_wanted` is worked out 46 lines further down, so the pin could only
    ever act on the PREVIOUS refresh's answer and every change of state took
    two refreshes to settle.
    """
    bar, ctl = empty_bar
    bar.set_calibration_allowed(True)
    bar.resize(1400, 40)
    bar.show()
    qapp.processEvents()
    assert bar._hint.isVisible(), "no project yet, so the hint is on screen"

    # The transition: a project appears, the hint goes. The row's ceiling must
    # follow on THIS refresh, not the one after it.
    ctl._fm.set_target_name("Settle-Test")
    ctl._fm.project()
    bar.refresh()
    qapp.processEvents()
    settled = bar.maximumHeight()

    bar.refresh()               # nothing has changed; nothing may move
    qapp.processEvents()
    assert bar.maximumHeight() == settled, (
        f"the ceiling went {settled} -> {bar.maximumHeight()} on a refresh "
        f"that changed nothing — the pin is a beat behind the state it follows"
    )
    bar.hide()


def test_the_hint_is_no_longer_than_the_one_that_never_clipped(empty_bar):
    """A length limit, because the mechanism has no other guard.

    The hint wraps against the version text in a row whose width it does not
    control, and the wrap is computed at a width the label is not always
    painted at. The sentence without calibration has lived there without
    trouble; the calibration one is held to the same length rather than
    trusting the layout to cope.
    """
    bar, ctl = empty_bar
    bar.set_calibration_allowed(False)
    plain = len(bar._hint.text())
    bar.set_calibration_allowed(True)
    withcal = len(bar._hint.text())
    assert withcal <= plain + 2, (
        f"the calibration hint is {withcal} chars against {plain} for the "
        f"plain one — it will wrap where the other does not"
    )


def test_the_hint_is_unchanged_with_the_preference_off(empty_bar):
    bar, ctl = empty_bar
    bar.set_calibration_allowed(False)
    text = bar._hint.text()
    assert "then you may choose a profile run." in text
    assert "Calibration" not in text


def test_generating_creates_the_project_from_the_name_field():
    """The other half of option 2, and the half that could have been missed.

    Selecting Calibration with no project is only useful if Generate then makes
    the project. It does, and by the same line that makes a first PROFILING
    chart make one — so the two paths cannot drift apart.
    """
    import inspect

    from ui.tabs.tab_chart import TabChart

    src = inspect.getsource(TabChart._on_generate)
    i = src.index("set_target_name")
    before = src[:i]
    # The name is applied BEFORE anything branches on the run type, so the
    # project exists whichever type is selected.
    assert "cal_target_active" not in before, (
        "the project is being created after the calibration branch; a "
        "calibration started with no project would have nowhere to go"
    )



def test_the_bar_knows_the_calibration_preference_before_it_is_told(qapp, tmp_path):
    """The widths must be right the first time they are painted.

    MainWindow fans the preference out on a ``singleShot(0)`` — the first pass
    of the event loop, which is after the first paint. The Profile run box is
    measured against "Project calibration" when calibration is on, so learning
    it late made that box grow from 147 to 176 px ON SCREEN, shoving the six
    controls to its right 29 px sideways (Basti, beta.142: *"directly after
    loading it seems that the run type combobox is adjusting its width a bit.
    looks like a jump"* — it was its neighbour pushing it).

    So the bar reads the preference itself at construction. The fan-out still
    happens and still works; it just no longer has anything left to change.
    """
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)

    class _Settings(AppSettings):
        def get(self, key, default=None):
            if key == "calibration_mode":
                return True
            if key == "custom_output_path":
                return str(tmp_path)
            return super().get(key, default)

    ctl = MeasurementTargetController(FileManager(_Settings()))
    bar = MeasurementTargetBar(ctl)
    assert ctl.calibration_allowed, (
        "the bar was built without knowing the preference; its widths will be "
        "wrong until MainWindow tells it, which is a paint too late"
    )
    assert bar._type_combo.count() == 3


def test_the_widths_do_not_change_when_the_fan_out_confirms_them(qapp, tmp_path):
    """…and the fan-out that follows must be a no-op, not a second layout."""
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import (MeasurementTargetBar,
                                           MeasurementTargetController)

    class _Settings(AppSettings):
        def get(self, key, default=None):
            if key == "calibration_mode":
                return True
            if key == "custom_output_path":
                return str(tmp_path)
            return super().get(key, default)

    bar = MeasurementTargetBar(
        MeasurementTargetController(FileManager(_Settings())))
    bar.resize(1400, 40)
    bar.show()
    qapp.processEvents()
    before = (bar._run_combo.width(), bar._type_combo.width())
    bar.set_calibration_allowed(True)         # what MainWindow does, a beat later
    qapp.processEvents()
    assert (bar._run_combo.width(), bar._type_combo.width()) == before, (
        "the boxes resized when the preference was confirmed — that is the "
        "jump, arriving after the first paint"
    )
    bar.hide()
