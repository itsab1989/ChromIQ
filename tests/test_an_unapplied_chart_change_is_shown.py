"""`docs/design/per_target_settings.md` §2.2, confirmed by Knut Larsson and
Sebastian on 2026-09-10.

Selecting a run paints that run's chart over the Create Chart panel, so a
setting the user changes and does not build survives only until they leave the
run. Knut asked for *"a red warning text to notify user to click Generate Chart
to apply the change, and changes not applied will be lost when closing project
or changing between runs"*.

The hard part is WHEN it appears. Seeding a widget is not an edit: loading a
preset, opening a `.ti2`, selecting another run or restoring a chart all fill
the panel programmatically and every field fires `changed`. `_settle_live_
preview` exists in this file because the live preview could not tell a seeder
from a user and rewrote a sheet that had just been generated. So the notice is a
COMPARISON against a baseline taken at the END of each episode that makes the
panel describe the target's own chart, not a flag anybody sets.
"""
from __future__ import annotations

import pytest

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.settings import AppSettings
from ui.tabs.tab_chart import TabChart


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path))
    s.set("use_chromiq_layout_engine", True)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._refresh_manual_command_preview()      # build the engine panel
    if getattr(t, "_manual_layout_panel", None) is None:
        pytest.skip("the engine layout panel is not available in this build")
    return t


def _give_it_a_chart(t, tmp_path):
    """Put a chart on screen, the way a run selection does."""
    ti2 = tmp_path / "some-project.ti2"
    ti2.write_text("NUMBER_OF_SETS 600\n", encoding="utf-8")
    t._shown_chart_ti2 = ti2
    return ti2


def _move_a_targen_row(t, value):
    t._set_manual_value("targen", "-f", value)
    t._refresh_manual_command_preview()


def _showing(t) -> bool:
    # NOT `isVisible()`. The tab is never shown in this harness, and Qt reports
    # every widget under an unshown window as invisible however it was set — so
    # `isVisible()` here reads "the window is closed", not "the notice is up",
    # and every one of these tests passed for the wrong reason.
    return not t._unapplied_lbl.isHidden()


# --------------------------------------------------------------------------
# What it says, and when
# --------------------------------------------------------------------------

def test_a_tab_that_has_established_nothing_says_nothing(tab):
    """`_applied_sig` is None until an episode establishes it, and until then
    there is no honest comparison to make."""
    assert tab._applied_sig is None
    tab._refresh_unapplied_warning()
    assert not _showing(tab)


def test_a_change_the_user_makes_raises_it(tab, tmp_path):
    _give_it_a_chart(tab, tmp_path)
    tab._mark_settings_applied()
    assert not _showing(tab), "the panel and the chart agree, so nothing pends"

    _move_a_targen_row(tab, 1234)
    assert _showing(tab)
    said = tab._unapplied_lbl.text()
    assert "Generate Chart" in said, said
    assert "lost" in said, said


def test_moving_it_back_takes_it_away_again(tab, tmp_path):
    """It COMPARES. A flag set by a `changed` signal could not do this, and a
    notice that cannot go away is the one everybody learns to ignore."""
    _give_it_a_chart(tab, tmp_path)
    before = tab._manual_get("targen", "-f", 0)
    tab._mark_settings_applied()

    _move_a_targen_row(tab, 1234)
    assert _showing(tab)
    _move_a_targen_row(tab, before)
    assert not _showing(tab)


def test_seeding_the_panel_is_not_an_edit(tab, tmp_path):
    """The episode is the unit. An operation that fills the panel on the user's
    behalf ends by marking, and however many fields it moved on the way the
    notice is silent afterwards."""
    _give_it_a_chart(tab, tmp_path)
    tab._mark_settings_applied()

    # …what a seeder does: several fields, none of them the user's hand.
    tab._set_manual_value("targen", "-f", 999)
    tab._set_manual_value("targen", "-B", 7)
    tab._refresh_manual_command_preview()
    assert _showing(tab), "mid-episode the comparison is honestly out of step"

    tab._mark_settings_applied()             # the episode ENDS here
    assert not _showing(tab)


def test_a_run_with_nothing_built_is_not_a_pending_change(tab, tmp_path):
    """A chart that has never been generated has nothing to overwrite the
    panel: the run's own `meta.json` holds these settings and hands them
    straight back. So there is nothing to lose and nothing to say."""
    tab._shown_chart_ti2 = None
    tab._mark_settings_applied()
    _move_a_targen_row(tab, 4321)
    assert not _showing(tab)

    # …and the moment a chart exists, the same change is worth saying.
    _give_it_a_chart(tab, tmp_path)
    tab._refresh_unapplied_warning()
    assert _showing(tab)


def test_a_vanished_chart_file_is_not_a_pending_change(tab, tmp_path):
    ti2 = _give_it_a_chart(tab, tmp_path)
    tab._mark_settings_applied()
    _move_a_targen_row(tab, 4321)
    assert _showing(tab)

    ti2.unlink()
    tab._refresh_unapplied_warning()
    assert not _showing(tab)


def test_the_notes_and_the_stamp_raise_it_too(tab, tmp_path):
    """Both travel in the chart's sidecar and are restored over these controls
    on a run change, so both can be typed and lost. Neither routes through the
    command preview, which is why each has a slot of its own."""
    _give_it_a_chart(tab, tmp_path)

    tab._mark_settings_applied()
    tab._manual_chart_notes_edit.setText("Hahnemuehle Photo Rag, 2026-09-10")
    assert _showing(tab), "the chart notes"

    tab._manual_chart_notes_edit.setText("")
    tab._mark_settings_applied()
    was = tab._manual_stamp_cmd_check.isChecked()
    tab._manual_stamp_cmd_check.setChecked(not was)
    assert _showing(tab), "the stamp tick"


def test_it_never_blocks_the_button_it_names(tab, tmp_path):
    _give_it_a_chart(tab, tmp_path)
    tab._mark_settings_applied()
    _move_a_targen_row(tab, 1234)
    assert _showing(tab)
    assert tab._generate_btn.isEnabled(), (
        "§2.2: the warning describes what the app does and must never gate a "
        "build, a run change or a close")


# --------------------------------------------------------------------------
# Why the existing notion of "the layout differs" could not answer this
# --------------------------------------------------------------------------

def test_the_layout_signature_answers_a_different_question(tab, tmp_path):
    """`_layout_signature()` is the obvious-looking candidate and is wrong.

    It is printtarg's rows plus the bit depth plus the engine recipe, so it
    describes how the sheet is LAID OUT. Doubling the patch count changes the
    chart completely and moves it not one character, which is exactly the
    change a user makes and loses.
    """
    _give_it_a_chart(tab, tmp_path)
    layout_before = tab._layout_signature()
    settings_before = tab._chart_settings_fingerprint()

    _move_a_targen_row(tab, 1234)

    assert tab._layout_signature() == layout_before, (
        "if this ever starts moving, re-derive the choice rather than "
        "assuming the layout signature now answers §2.2")
    assert tab._chart_settings_fingerprint() != settings_before


def test_the_fingerprint_leaves_out_what_no_chart_overwrites(tab, tmp_path):
    """The module, the Guided row, the engine-calibration block and the gamut
    options live in the target's `create_chart_ui` and no chart writes over
    them, so they are not at risk. Warning about them would be false."""
    _give_it_a_chart(tab, tmp_path)
    tab._mark_settings_applied()
    tab._gamut_count_spin.setValue(tab._gamut_count_spin.value() + 5)
    tab._refresh_unapplied_warning()
    assert not _showing(tab)


def test_the_slots_are_bound_methods_and_not_closures():
    """CLAUDE.md, and `test_a_scrollbar_signal_never_takes_a_lambda`: a
    self-capturing lambda parked on a signal a child widget emits is how this
    app came to segfault under PyQt6 6.11.

    Read with `ast`, not by scanning lines: a lambda written on the line AFTER
    its `.connect(` is invisible to a line scan, and the first version of this
    check let exactly that mutation through.
    """
    import ast
    import inspect

    src = inspect.getsource(inspect.getmodule(TabChart))
    offenders = []
    for node in ast.walk(ast.parse(src)):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "connect"):
            continue
        for arg in node.args:
            if not isinstance(arg, ast.Lambda):
                continue
            names = {n.attr for n in ast.walk(arg)
                     if isinstance(n, ast.Attribute)}
            if names & {"_refresh_unapplied_warning",
                        "_mark_settings_applied",
                        "_chart_settings_fingerprint"}:
                offenders.append(node.lineno)
    assert not offenders, (
        f"§2.2's slots are connected as lambdas at line(s) {offenders}; "
        "PyQt6 6.11 segfaults on a self-capturing closure parked on a signal "
        "a child widget emits. Use a bound method.")
    assert "self._on_chart_settings_touched)" in src
