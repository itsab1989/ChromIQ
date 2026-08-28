"""The three left-hand masthead buttons move as one group (#164).

THE STORY, in one sentence: the two left buttons bring something IN, the third
lets the open one GO, and everything stops while ChromIQ is busy.

Two independent reasons a button can be unavailable — busy (a measurement or a
profile build) and nothing-to-close — and **busy wins when both apply**, because
"nothing to close" is only the more useful message if it is actionable, and the
fix for it (open a project) is greyed at the same moment.

Every test here drives a REAL transition. Asserting on source text has hidden
four separate bugs in this project, including a `NameError` in a guard written
to prevent a crash.
"""
import os
import pathlib
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


@pytest.fixture
def win(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.main_window import MainWindow

    settings = AppSettings()
    settings.set("custom_output_path", str(tmp_path / "out"))
    settings.set("session_project", "")
    w = MainWindow(settings)
    qapp.processEvents()
    yield w
    w.close()


def _state(win):
    m = win._masthead
    return {
        "open": m._load_project_btn.isEnabled(),
        "chart": m._load_ti2_btn.isEnabled(),
        "close": m._close_project_btn.isEnabled(),
        "tools": m._tools_btn.isEnabled(),
    }


def test_a_fresh_launch_has_nothing_to_close(win):
    """The button must not look available before there is a project."""
    assert _state(win)["close"] is False
    assert _state(win)["open"] is True, "Open Project should still be offered"


def test_opening_a_project_offers_the_close_button(win):
    win._file_mgr.set_target_name("Availability Test")
    win._refresh_masthead_availability()
    assert _state(win)["close"] is True


@pytest.mark.parametrize("start,stop,reason", [
    ("_on_measurement_active", "_on_measurement_active", "measuring"),
    ("_on_profile_active", "_on_profile_active", "building"),
])
def test_busy_greys_the_whole_group_and_releases_it(win, start, stop, reason):
    """A build must lock exactly as a measurement does (Basti, #164), and both
    must let go again — a lock that sticks leaves the user unable to open any
    project without restarting."""
    win._file_mgr.set_target_name("Availability Test")
    win._refresh_masthead_availability()
    assert all(_state(win).values()), "not all available before we start"

    getattr(win, start)(True)
    assert not any(_state(win).values()), f"{reason} did not grey the group"

    getattr(win, stop)(False)
    assert all(_state(win).values()), f"{reason} did not release the group"


def test_busy_wins_when_there_is_also_nothing_to_close(win):
    """Both reasons at once: the tooltip must give the busy one, so three
    adjacent grey buttons tell one story rather than two."""
    win._on_measurement_active(True)
    tip = win._masthead._close_project_btn.toolTip()
    assert "measurement" in tip.lower(), (
        f"the close button explains the wrong reason while busy: {tip[:80]!r}")
    win._on_measurement_active(False)


def test_each_greyed_state_says_which_reason_applies(win):
    """A greyed button with no explanation is a dead end."""
    m = win._masthead
    assert "nothing to close" in m._close_project_btn.toolTip().lower()

    win._file_mgr.set_target_name("Availability Test")
    win._refresh_masthead_availability()
    win._on_profile_active(True)
    assert "profile is being built" in m._close_project_btn.toolTip().lower()
    win._on_profile_active(False)


def test_the_shortcuts_obey_the_same_lock_as_their_buttons(win, monkeypatch):
    """A shortcut that bypasses its button's guard is worse than no guard —
    the greyed button says the app is protected. ⌘T did exactly that."""
    opened = []

    # Stub what the handlers ACTUALLY call. The previous version patched
    # `_open_project_dialog`, which exists nowhere in the codebase, with
    # `raising=False` hiding that — so the "open" half asserted nothing, and a
    # regression in the guard would have opened a real modal QFileDialog and
    # hung the whole gate rather than failing the test.
    monkeypatch.setattr(type(win._tab_chart), "_load_existing_profile",
                        lambda self: opened.append("open"))
    monkeypatch.setattr(type(win._tab_measure), "_on_load_ti2",
                        lambda self, *a, **k: opened.append("chart"),
                        raising=False)
    import ui.tools_popup as tools_popup
    monkeypatch.setattr(tools_popup.ToolsPopup, "show_under",
                        lambda self, b: opened.append("tools"))

    # Positive control FIRST: prove the stubs are reached when NOT locked, or
    # an empty `opened` below would prove nothing at all.
    win._on_masthead_load_project()
    assert opened == ["open"], (
        f"the stub was never reached, so this test cannot detect a bypass "
        f"({opened})")
    opened.clear()

    win._on_measurement_active(True)
    try:
        win._on_masthead_load_project()
        win._on_masthead_load_ti2()
        win._open_tools_menu()
        assert not opened, f"a shortcut worked while the group was greyed: {opened}"
    finally:
        win._on_measurement_active(False)


def test_the_button_wakes_up_when_a_project_appears(win):
    """Basti, #164: *"the close button remains greyed when i generate a chart
    or load a project"*.

    The refresh ran on measurement and build transitions, on delete and at
    startup — but nothing told it when a project came INTO existence, which is
    the one transition that turns this button on. Both routes are covered:
    a bar change (what Generate Chart causes) and the open-project handler.
    """
    assert win._masthead._close_project_btn.isEnabled() is False

    win._file_mgr.set_target_name("Appeared")
    win._target_ctl.changed.emit()
    assert win._masthead._close_project_btn.isEnabled() is True, (
        "the bar changed and the Close button did not notice")


def test_opening_a_project_lights_the_button_however_it_happened(win,
                                                                monkeypatch):
    """Driven replacement for two source-text tests.

    They asserted that `_on_masthead_load_project` mentions
    `_refresh_masthead_availability` and that `__init__` mentions a
    `changed.connect(...)` — both of which pass on a comment, and neither of
    which says the button actually lights. This runs the handler.
    """
    btn = win._masthead._close_project_btn
    assert btn.isEnabled() is False

    # The real handler, with only the file dialog it would open replaced by
    # the naming it would have produced.
    monkeypatch.setattr(
        type(win._tab_chart), "_load_existing_profile",
        lambda self: self._file_mgr.set_target_name("Opened From Disk"))
    win._on_masthead_load_project()

    assert win._file_mgr.is_named() is True
    assert btn.isEnabled() is True, (
        "a project was opened and the Close button stayed greyed")


def test_a_locked_tab_says_why_during_a_measurement(win):
    """#164 Q6(b): *"greyed with a note saying why"*. The Build Profile tab was
    already greyed for a measurement, but silently — a dead tab with no tooltip
    reads as a bug, not a lock."""
    idx = win._tabs.indexOf(win._tab_profile)
    win._on_measurement_active(True)
    try:
        assert win._tabs.isTabEnabled(idx) is False
        tip = win._tabs.tabToolTip(idx)
        assert "measurement" in tip.lower(), (
            f"the greyed Build Profile tab explains nothing (tooltip {tip!r})")
        assert "comes back" in tip.lower(), "it does not say when it returns"
    finally:
        win._on_measurement_active(False)
    assert win._tabs.isTabEnabled(idx) is True
    assert win._tabs.tabToolTip(idx) == "", "the lock's note outlived the lock"


def test_a_locked_tab_says_why_during_a_build(win):
    """#164 Q7: a build locks the same way, so it explains itself the same way."""
    idx = win._tabs.indexOf(win._tab_chart)
    win._on_profile_active(True)
    try:
        assert win._tabs.isTabEnabled(idx) is False
        tip = win._tabs.tabToolTip(idx)
        assert "built" in tip.lower() or "build" in tip.lower(), (
            f"the greyed Create Chart tab explains nothing (tooltip {tip!r})")
    finally:
        win._on_profile_active(False)
    assert win._tabs.isTabEnabled(idx) is True
    assert win._tabs.tabToolTip(idx) == ""


def test_a_measurement_does_not_eat_the_verification_explanation(win):
    """The gate's own tooltip on tab 4 must come back after a measurement — and
    the tab must stay locked, because a verification still never builds."""
    idx = win._tabs.indexOf(win._tab_profile)
    win._target_ctl.target.is_verification = lambda: True
    win._apply_profile_tab_gate()
    before = win._tabs.tabToolTip(idx)
    assert "verification" in before.lower()

    win._on_measurement_active(True)
    assert "measurement" in win._tabs.tabToolTip(idx).lower()
    win._on_measurement_active(False)

    assert win._tabs.tabToolTip(idx) == before, (
        "the verification explanation was replaced by the measurement lock's")
    assert win._tabs.isTabEnabled(idx) is False, (
        "tab 4 came back live on a verification run")


def test_locking_twice_does_not_lose_the_real_tooltips(win):
    """A second lock while already locked must not save the WHY text as if it
    were the tab's own tooltip — that would make the note permanent."""
    idx = win._tabs.indexOf(win._tab_chart)
    win._on_measurement_active(True)
    win._on_measurement_active(True)          # the double call
    win._on_measurement_active(False)
    assert win._tabs.tabToolTip(idx) == "", (
        "a repeated lock made its own note stick to the tab for good")


def test_two_locks_do_not_cancel_each_other(win):
    """Locks are COUNTED, not boolean.

    The ChromIQ profile engine builds in a QThread of its own, outside the
    single ArgyllRunner that serialises everything else, so a measurement and a
    build are not mutually exclusive by construction. With an on/off flag,
    whichever ENDED first unlocked everything — leaving every tab live during a
    still-running measurement, wearing a stale tooltip.
    """
    m_idx = win._tabs.indexOf(win._tab_measure)
    p_idx = win._tabs.indexOf(win._tab_profile)

    win._on_measurement_active(True)
    win._on_profile_active(True)
    # Both holders keep their own tab usable — Measure so Stop stays
    # reachable, Build Profile so its own progress is visible. Everything else
    # is locked.
    m_idx = win._tabs.indexOf(win._tab_measure)
    p_idx = win._tabs.indexOf(win._tab_profile)
    assert win._tabs.isTabEnabled(m_idx) is True
    assert win._tabs.isTabEnabled(p_idx) is True
    assert not any(win._tabs.isTabEnabled(i)
                   for i in range(win._tabs.count())
                   if i not in (m_idx, p_idx)), (
        "with two holders, no OTHER tab is safe to walk into")

    win._on_profile_active(False)          # build ends, measurement continues
    try:
        assert win._tabs.isTabEnabled(m_idx) is True, "the Measure tab should be live"
        assert win._tabs.isTabEnabled(p_idx) is False, (
            "the build ending unlocked the tabs while a measurement is running")
        assert "measurement" in win._tabs.tabToolTip(p_idx).lower(), (
            "the tab kept the build's note after the build ended")
    finally:
        win._on_measurement_active(False)

    assert all(win._tabs.isTabEnabled(i) for i in range(win._tabs.count()))
    assert all(win._tabs.tabToolTip(i) == "" for i in range(win._tabs.count())), (
        "a lock note outlived the last lock")


def test_the_reverse_order_is_symmetric(win):
    """Ending a measurement must not unlock the tabs during a build."""
    p_idx = win._tabs.indexOf(win._tab_profile)

    win._on_profile_active(True)
    win._on_measurement_active(True)
    win._on_measurement_active(False)      # measurement ends, build continues
    try:
        assert win._tabs.isTabEnabled(p_idx) is True, "Build Profile should be live"
        for i in range(win._tabs.count()):
            if i != p_idx:
                assert win._tabs.isTabEnabled(i) is False, (
                    f"tab {i} came back while a build is running")
    finally:
        win._on_profile_active(False)
    assert all(win._tabs.isTabEnabled(i) for i in range(win._tabs.count()))


def test_the_second_holder_does_not_capture_the_first_ones_note(win):
    """The saved tooltips must be taken before the FIRST holder overwrites
    them, or the note becomes permanent."""
    win._on_measurement_active(True)
    win._on_profile_active(True)
    win._on_profile_active(False)
    win._on_measurement_active(False)
    assert all(win._tabs.tabToolTip(i) == "" for i in range(win._tabs.count())), (
        "a lock note was saved as if it were a tab's own tooltip")


def test_the_masthead_follows_the_file_manager_not_the_bar(win):
    """#164: the Close button stayed greyed after Generate and after Open Chart
    File because the refresh hung off the Profile-run bar's `changed` signal —
    a signal about the BAR — while the state it reads (`is_named()`) lives on
    the FileManager. Every route that named a project without moving the bar
    went stale. Driven here with the bar deliberately untouched.
    """
    btn = win._masthead._close_project_btn
    assert btn.isEnabled() is False

    win._file_mgr.set_target_name("Named-Without-Touching-The-Bar")
    assert btn.isEnabled() is True, (
        "naming a project did not reach the masthead unless the bar moved")

    win._file_mgr.close_project()
    assert btn.isEnabled() is False, "closing did not reach the masthead"


def test_a_nested_project_also_reaches_the_masthead(win, tmp_path):
    """`open_project_at` is the nested-project route (#130) and bypasses
    `set_target_name`'s name path entirely."""
    btn = win._masthead._close_project_btn
    win._file_mgr.open_project_at(tmp_path / "customers" / "2026" / "Nested")
    assert btn.isEnabled() is True
    win._file_mgr.close_project()
    assert btn.isEnabled() is False


def test_re_applying_the_same_name_does_not_churn_the_listeners(win):
    """Only a real CHANGE notifies, and the churn this guards against is
    re-applying the SAME name: `set_target_name` runs on every keystroke path,
    every preset and every Generate, almost always with the name that is
    already set.

    THIS TEST USED TO SAY SWITCHING PROJECTS WAS CHURN TOO, and that was too
    narrow. It compared "is something open" before and after, so with project A
    open and a build adopting project B, nothing fired at all — and the Create
    Chart hint that says "you already have a project with this name" went on
    showing after ChromIQ had opened exactly that project. The comparison is now
    the FOLDER (`_project_identity`), so a swap is a change and re-applying a
    name is not (2026-08-27).
    """
    calls = []
    win._file_mgr.add_named_state_listener(lambda: calls.append(1))

    win._file_mgr.set_target_name("First")
    assert len(calls) == 1, "opening should notify once"
    win._file_mgr.set_target_name("First")
    win._file_mgr.set_target_name("First")
    assert len(calls) == 1, (
        f"re-applying the same name notified again ({len(calls)} times)")
    win._file_mgr.set_target_name("Second")
    assert len(calls) == 2, "swapping one project for another must notify"
    win._file_mgr.close_project()
    assert len(calls) == 3, "closing should notify"


def test_the_tab_you_are_standing_in_stays_usable_with_two_holders(win):
    """Stop lives on the Measure page (`ui/tabs/tab_measure.py`).

    With two lock holders the code disabled EVERY tab, including the one the
    user was standing in — so during a measurement the Stop button became
    unreachable while the tooltip said "wait for them to finish", which a
    measurement does not do on its own.
    """
    m_idx = win._tabs.indexOf(win._tab_measure)
    win._tabs.setCurrentIndex(m_idx)

    win._on_measurement_active(True)
    win._on_profile_active(True)
    try:
        assert win._tabs.isTabEnabled(m_idx) is True, (
            "the page holding Stop was disabled while a measurement ran")
        # The build's own tab stays live too — every holder keeps its page, so
        # the result no longer depends on which lock arrived first.
        p_idx = win._tabs.indexOf(win._tab_profile)
        assert win._tabs.isTabEnabled(p_idx) is True
        others = [i for i in range(win._tabs.count())
                  if i not in (m_idx, p_idx)]
        assert not any(win._tabs.isTabEnabled(i) for i in others), (
            "the other tabs should still be locked")
    finally:
        win._on_profile_active(False)
        win._on_measurement_active(False)


def test_an_unlock_with_no_lock_leaves_tooltips_alone(win):
    """A stray release wrote "" over every tab. Harmless today only because the
    verification gate re-applies its own note immediately afterwards — a trap
    for the next tooltip anyone adds."""
    win._tabs.setTabToolTip(0, "someone else's tooltip")
    win._on_profile_active(False)          # release with nothing held
    assert win._tabs.tabToolTip(0) == "someone else's tooltip", (
        "a stray unlock wiped a tooltip it never set")
