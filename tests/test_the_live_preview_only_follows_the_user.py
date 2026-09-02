"""The live preview re-renders when the USER changes the layout — and at no
other time.

Basti, 2026-08-26:

    *"sometimes when generating a chart in guided and then switching to manual
    when the auto-update preview option is on the chart regenerates directly
    after the switch between the modules … when i went back to guided, generated
    again and then back to manual, the chart stayed unchanged until i really
    changed a setting there."*

His log has it exactly:

    13:28:13,886  chart build (Generate Chart)   <- him, in Guided
    13:28:45,405  the mode switch seeds Manual's widgets
    13:28:45,902  chart build (live preview)     <- nobody asked

497 ms apart: the 450 ms debounce timer, armed by the switch itself. Seeding a
widget is indistinguishable from a user turning a knob, so the preview believed
the layout had changed — and a live re-render REWRITES the chart in the run, so
the sheet he had just generated was silently replaced.

It looked like a once-per-session quirk because the second transfer writes
values that are already there: the fingerprint does not move, so nothing arms.

Three separate things have to hold, and they are tested separately because two
earlier attempts each fixed one and left another broken.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.file_manager import FileManager            # noqa: E402
from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("auto_update_preview", True)
    from ui.tabs.tab_chart import TabChart
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    ti1 = tmp_path / "chart.ti1"
    ti1.write_text("TI1\n", encoding="utf-8")
    t._current_ti1_path = ti1
    return t


def _renders(tab, monkeypatch) -> list:
    """Record every re-layout the preview asks for, and open every OTHER gate.

    `_auto_regenerate_preview` has several early returns after the fingerprint
    check — the mode, a build in flight, the .ti1, whether a project is named,
    and §4. If any of those is left shut, a test "proves" the fingerprint check
    works while the render was actually stopped by something else. The first
    version of this file did exactly that and would have passed with the bug in
    place.

    `_target_run` is stubbed to None deliberately. It is a MUTATING getter —
    with `_is_named` forced True it built a real project under the tester's own
    ~/ChromIQ the first time this ran. A unit test must not reach the home
    folder at all.
    """
    import ui.tabs.tab_chart as tc
    import workflow.chart_integrity as ci

    calls: list = []
    monkeypatch.setattr(type(tab), "_generate_from_ti1",
                        lambda self, ti1, ask=True, preview=False: calls.append(ti1))
    monkeypatch.setattr(type(tab), "_current_mode", lambda self: "manual")
    monkeypatch.setattr(type(tab), "_chart_build_in_flight", lambda self: False)
    monkeypatch.setattr(tc, "_is_named", lambda _fm: True)
    monkeypatch.setattr(type(tab), "_target_run", lambda self: None)
    monkeypatch.setattr(type(tab), "_is_verification_target", lambda self: False)
    monkeypatch.setattr(ci, "assess_profiling_chart",
                        lambda _run: type("A", (), {"warn": False})())
    return calls


# ---------------------------------------------------------------- fire time

def test_an_arming_that_has_since_been_baselined_is_dropped(tab, monkeypatch):
    """The timer is armed for a LAYOUT, not for a moment.

    Re-baselining `_last_auto_sig` used to stop nothing, because by then the
    timer is already running and this method checked the mode, the build guard,
    the .ti1 and §4 — everything except the question it was started to answer.
    """
    calls = _renders(tab, monkeypatch)
    tab._last_auto_sig = tab._layout_signature()
    tab._auto_regenerate_preview()
    assert calls == [], "a render went ahead for a layout already baselined"

    # PROOF THIS TEST CAN SEE ITS OWN FAILURE. Every other gate is open, so the
    # fingerprint is the only thing holding the render back: move it, and the
    # render must happen on the very next call.
    tab._last_auto_sig = "a layout that is not the one on screen"
    tab._auto_regenerate_preview()
    assert len(calls) == 1, (
        "with the fingerprint moved nothing rendered — some OTHER gate is shut, "
        "so the assertion above proves nothing about the fire-time check")


def test_a_real_change_still_renders(tab, monkeypatch):
    """The control for the test above. If the fingerprint really has moved, the
    render must happen — otherwise the fix is just a switched-off feature."""
    calls = _renders(tab, monkeypatch)
    tab._last_auto_sig = "a layout that is not the one on screen"
    tab._auto_regenerate_preview()
    assert len(calls) == 1, (
        "nothing re-rendered after a genuine layout change — the fire-time "
        "check has swallowed the feature instead of the bug")


# ------------------------------------------------------------- mode switch

def test_opening_manual_after_a_guided_build_arms_nothing(tab):
    """Half one of Basti's report. The #79 transfer reproduces the chart that
    was just built, so there is nothing for the preview to discover."""
    tab._switch_mode("guided")
    tab._guided_transfer_pending = True
    tab._last_auto_sig = None            # as if the Guided build had just landed
    tab._switch_mode("manual")
    assert not tab._auto_preview_timer.isActive(), (
        "changing module armed the live preview; the user touched nothing")
    assert tab._last_auto_sig == tab._layout_signature(), (
        "the fingerprint was left stale, so the next arming would fire")


def test_the_transfer_really_does_arm_the_timer(tab, monkeypatch):
    """The control for the test above.

    If seeding Manual's widgets did not arm the timer in the first place, the
    assertion that it is inactive afterwards would hold with or without the fix.
    Neutralise the two lines of the fix — the cancel, and a re-baseline that can
    ever match — and the timer must be running.
    """
    monkeypatch.setattr(type(tab), "_cancel_pending_auto_preview", lambda self: None)
    counter = iter(range(1_000_000))
    monkeypatch.setattr(type(tab), "_layout_signature",
                        lambda self: f"unique-{next(counter)}")
    tab._switch_mode("guided")
    tab._guided_transfer_pending = True
    tab._last_auto_sig = None
    tab._switch_mode("manual")
    assert tab._auto_preview_timer.isActive(), (
        "the mode switch armed nothing even with the fix neutralised — the "
        "test above is not measuring what it claims to")


def test_a_setting_the_user_changed_in_guided_is_not_swallowed(tab):
    """The opposite case, and the reason the re-baseline is NARROW.

    `_carry_shared_settings` carries what the user CHANGED — instrument and
    paper. A blanket re-baseline on every mode switch drops a paper the user
    picked by hand in Guided, which is a second bug with the same smell as the
    first.
    """
    tab._switch_mode("guided")
    tab._guided_transfer_pending = False      # no #79 transfer: a plain switch
    sentinel = "the baseline from before the switch"
    tab._last_auto_sig = sentinel
    tab._switch_mode("manual")
    assert tab._last_auto_sig == sentinel, (
        "a plain mode switch re-baselined the preview, which swallows a change "
        "the user made in the other module")


# -------------------------------------------------------------- run switch

def test_selecting_a_run_does_not_re_render_its_chart(tab, monkeypatch):
    """THIS IS N3 of `per_target_settings_test_plan.md` — the one the plan says
    nothing ships without. It lived on a stand-in class with no timer until
    2026-08-26 and was green while the real path was broken.

    ONE DEVIATION, DELIBERATE AND UNCONFIRMED: the plan words N3 as "assert the
    chart file's mtime is unchanged". THAT ASSERTION CANNOT FAIL HERE, measured
    2026-08-26:

    `_auto_regenerate_preview` ends in `_generate_from_ti1`, which reaches
    `ArgyllRunner.run` -> `QProcess.start` — asynchronous. Nothing on disk has
    moved when it returns; the .ti2 is written by printtarg, in another process.
    printtarg on a 210-patch A4 chart takes 0.263 s here, so the earliest the
    mtime can move after a run switch is 450 ms (the debounce) + spawn + 0.26 s
    ~= 0.75 s. A test that switches run and stats the file reads an UNCHANGED
    mtime WHILE THE BUG IS HAPPENING. It would only go red if it also waited out
    an Argyll subprocess against a real run — which this fixture deliberately
    does not build, because `_target_run` is a mutating getter that once created
    a project under the tester's own ~/ChromIQ. Granularity is not the obstacle:
    /private/tmp, $TMPDIR and $HOME all resolve to ~1.6 ms here.

    So this asserts the rebuild is never STARTED — the same rule of §7 B,
    observed earlier and without the race. Awaiting Basti's confirmation, and a
    matching edit to N3's wording in the test plan.

    `per_target_settings.md` §7 B, and N3 of its test plan: *"Loading
    settings must not trigger a rebuild … This is the one that would actually
    hurt, so it gets its own test."*

    Merely picking a different run in the bar re-laid out that run's chart and
    rewrote it to disk. The handler seeds the panel twice — through
    `load_target_settings` and again through `_display_run_chart` ->
    `_restore_chart_settings` — so declining while `_loading_target_settings`
    is up guards only the first and moves which line arms the timer. The
    episode, not the flag, is the unit.
    """
    def seeds_widgets_like_a_target_load(self):
        self._last_auto_sig = "whatever the load left behind"
        self._auto_preview_timer.start(450)

    # THE CONTROL FIRST: the seeding really does arm the timer. Without this the
    # assertion below would hold with or without the fix — which is exactly how
    # N3 stayed green for weeks while the real path was broken.
    seeds_widgets_like_a_target_load(tab)
    assert tab._auto_preview_timer.isActive(), (
        "the stand-in load armed nothing, so nothing below is being measured")

    monkeypatch.setattr(type(tab), "_load_target_and_show_its_chart",
                        seeds_widgets_like_a_target_load, raising=False)
    monkeypatch.setattr(type(tab), "_apply_ui_state",
                        lambda self, *a, **k: seeds_widgets_like_a_target_load(self),
                        raising=False)
    tab._on_target_changed()
    assert not tab._auto_preview_timer.isActive(), (
        "selecting a run armed the live preview — §7 B forbids exactly this")
    assert tab._last_auto_sig == tab._layout_signature()

    # AND THE EPISODE, NOT JUST THE TWO FLAGS. A future seeding path that armed
    # the timer *and* moved the fingerprint would satisfy both assertions above
    # on the way in, and still rewrite the chart when the timer fired. `_renders`
    # opens every other gate, so this measures the fire-time fingerprint check
    # and nothing else; its own control is
    # `test_an_arming_that_has_since_been_baselined_is_dropped`.
    calls = _renders(tab, monkeypatch)
    tab._auto_regenerate_preview()
    assert calls == [], (
        "the fire-time path re-laid out the run's chart after a plain run "
        "switch — the rewrite §7 B forbids, one timer tick later")


def test_the_run_switch_guard_survives_a_failure_half_way(tab, monkeypatch):
    """A target switch that raises must still leave the preview baselined —
    otherwise the timer it armed on the way in fires into a half-loaded tab."""
    def blows_up_after_seeding(self, *a, **k):
        self._auto_preview_timer.start(450)
        raise RuntimeError("target load failed")

    monkeypatch.setattr(type(tab), "_apply_ui_state", blows_up_after_seeding,
                        raising=False)
    monkeypatch.setattr(type(tab), "_target_ctl", None, raising=False)
    try:
        tab._on_target_changed()
    except RuntimeError:
        pass
    assert not tab._auto_preview_timer.isActive()


# ------------------------------------------------- the other seeding paths

def _arm(tab):
    """Put the tab in the state a seeder leaves behind: a queued render for a
    fingerprint that is no longer current."""
    tab._last_auto_sig = "whatever the seeding left behind"
    tab._auto_preview_timer.start(450)


def test_the_settle_helper_disarms_and_rebaselines(tab):
    """Both halves are needed. Cancelling alone leaves a stale fingerprint that
    arms on the next unrelated signal; re-baselining alone does not stop a timer
    that is already running."""
    _arm(tab)
    assert tab._auto_preview_timer.isActive()          # control: it IS armed
    tab._settle_live_preview()
    assert not tab._auto_preview_timer.isActive(), "the queued render survived"
    assert tab._last_auto_sig == tab._layout_signature(), "the fingerprint is stale"


def test_settling_never_raises_out_of_its_caller(tab, monkeypatch):
    """It runs in a `finally` on paths the user is mid-way through. A failure
    here must not take down a preset load or a target switch."""
    monkeypatch.setattr(type(tab), "_layout_signature",
                        lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
    tab._settle_live_preview()          # must not raise


def test_resetting_manual_to_its_preset_arms_nothing(tab, monkeypatch):
    """Manual's "Reset" writes the whole panel from the stored preset. That is
    the app filling the widgets, not the user."""
    monkeypatch.setattr(type(tab), "_current_layout_recipe",
                        lambda self: (_ for _ in ()).throw(RuntimeError("no store")))
    _arm(tab)
    tab._reset_manual_to_preset()       # bails early — must NOT settle
    assert tab._auto_preview_timer.isActive(), (
        "a reset that failed before touching anything still cancelled a render "
        "the user had legitimately queued")


def test_mirroring_a_loaded_chart_arms_nothing(tab, monkeypatch, tmp_path):
    """Open Chart File (.ti2) mirrors a chart this tab does not own. Looking at
    it must never re-lay it out — that would rewrite a file in someone else's
    folder."""
    ti2 = tmp_path / "elsewhere.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    # The one-time "loaded from elsewhere" note is a real modal; a test that
    # leaves one open hangs the suite (tests/conftest.py catches it). Suppress
    # it with the app's own switch rather than patching QMessageBox, which
    # leaks across tests.
    tab._settings.set("reflect_backfill_hide_warning", True)
    _arm(tab)
    try:
        tab.reflect_loaded_chart(ti2, [])
    except Exception:                   # noqa: BLE001 — the settle is in a finally
        pass
    assert not tab._auto_preview_timer.isActive(), (
        "mirroring a chart from elsewhere left a re-layout queued")
    assert tab._last_auto_sig == tab._layout_signature()


def test_loading_a_user_preset_arms_nothing(tab, monkeypatch, tmp_path):
    """The largest of the five settle sites, and the one with no test until now.

    `_on_preset_selected` writes the whole layout panel from the preset. It is
    wrapped in try/finally over ~230 lines with four mid-way returns, so the
    settle has to hold on every one of them — including the `auto_run` preset
    that leaves early when a process is already running.
    """
    combo = tab._preset_combo
    # NAME THE PROJECT FIRST. Since 2026-08-30 a preset no longer names the
    # project after itself, so an empty name box makes the build ask for one —
    # correct in front of a person, but in a headless run it leaves a modal
    # standing and the settle this test is about never happens.
    tab._manual_target_name_edit.setText("ZZ-preview-settle-probe")
    # Choosing a preset that does not exist exercises the ordinary path: the
    # handler runs, seeds nothing it can find, and must still settle.
    _arm(tab)
    tab._on_preset_selected(0)
    assert not tab._auto_preview_timer.isActive(), (
        "selecting in the preset dropdown left a re-layout queued")
    assert tab._last_auto_sig == tab._layout_signature()

    # And the early-return path: a divider row is not a choice at all.
    if combo.count() > 1:
        _arm(tab)
        tab._on_preset_selected(combo.count() - 1)
        assert not tab._auto_preview_timer.isActive()


def test_mirroring_a_loaded_chart_settles_on_the_HAPPY_path_too(tab, tmp_path):
    """`test_mirroring_a_loaded_chart_arms_nothing` swallows exceptions, so it
    proves the `finally` fires — not that the ordinary path does. This drives a
    .ti2 the loader can actually read."""
    ti2 = tmp_path / "real.ti2"
    ti2.write_text(
        "CTI2\n\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
        "1 100.0 100.0 100.0\nEND_DATA\n", encoding="utf-8")
    tab._settings.set("reflect_backfill_hide_warning", True)
    _arm(tab)
    try:
        tab.reflect_loaded_chart(ti2, [])
    except Exception:                      # noqa: BLE001
        pass
    assert not tab._auto_preview_timer.isActive()
    assert tab._last_auto_sig == tab._layout_signature()
