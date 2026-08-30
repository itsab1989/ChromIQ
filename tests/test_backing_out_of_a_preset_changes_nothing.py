"""#175 — backing out of a built-in preset must leave the tab exactly as it was.

Basti's ruling, 2026-08-27: *"when a person picks a built-in preset and then
backs out of the window that follows, everything the preset touched must go back
to how it was."* Before this, answering Cancel left the tab moved: Manual instead
of Guided, the whole parameter panel on the preset's values, and — the part
nobody had noticed — **settings changed for good**, outliving the app run.

The refusal is injected by making the build step decline, which is what every
real refusal ends in (the §S4.7 project window's Cancel and "Use a different
name", a missing patch set, a runner already busy).

WHAT THE `settings` FIXTURE MUST NOT DO: it must not point at the real
``~/ChromIQ``. Seeding a preset asks the FileManager where it is working, and
that invents a name and creates the folder — see the note in
``test_knut_spyderprint_presets.py``.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import (  # noqa: E402
    BUILTIN_PRESET_KEYS,
    KNUT_PRESETS,
    MUNKI_TARGEN,
    PREBUILT_PRESETS,
    TC918_PRESET_KEY,
    TabChart,
)

# DETERMINISTIC KEYS, NOT `list(FROZENSET)[0]`. `KNUT_PRESET_KEYS` is a
# frozenset, so indexing it picks a different preset in every process — two
# earlier reports drew conclusions from that idiom before it was spotted.
_ENGINE_KEY = sorted(p.key for p in KNUT_PRESETS
                     if p.layout_recipe is not None or p.engine)[0]
# THE OTHER LIVE FAMILY. All 121 Spyderprint presets are engine presets, so
# `_seed_knut_preset`'s printtarg half never runs for any of them — the panel
# rows a person can see moved come from the prebuilt family instead.
assert not [p for p in KNUT_PRESETS if p.layout_recipe is None and not p.engine], \
    "a printtarg-based Spyderprint preset is back — cover it here as well"
_PREBUILT_KEY = sorted(PREBUILT_PRESETS)[0]


def test_only_two_preset_families_can_be_reached_from_the_dropdown():
    """The undo above covers the two families a person can actually choose.

    Two of `_on_preset_selected`'s four dispatch branches are unreachable: no
    `MUNKI_TARGEN` key and not `TC918_PRESET_KEY` is in `BUILTIN_PRESET_KEYS`.
    That matters here because the ColorMunki branch builds through
    `_on_generate`, which has no way to say "the person said no" — so it can
    only ever answer True. If either family comes back, this fails, and #175's
    undo needs a real answer from it before it ships.
    """
    assert TC918_PRESET_KEY not in BUILTIN_PRESET_KEYS
    assert not (set(MUNKI_TARGEN) & BUILTIN_PRESET_KEYS)
    assert BUILTIN_PRESET_KEYS == set(PREBUILT_PRESETS) | {p.key for p in KNUT_PRESETS}

# The settings a preset writes that outlive the app run (Basti ruled they go
# back too, 2026-08-28). TAKEN FROM THE IMPLEMENTATION, not copied: a hand-kept
# copy had already drifted — it was missing `i1pro_chromiq_clip_style`, so that
# key was restored by code no test looked at.
_PERSISTED = TabChart._PRESET_PERSISTED_SETTINGS


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "chromiq_test.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


@pytest.fixture()
def tab(qapp, settings):
    t = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    t._switch_mode("guided")
    # NAME THE PROJECT FIRST. Since 2026-08-30 a preset no longer names the
    # project after itself, and the name is asked for BEFORE §S4.7 so the gate
    # sees the real answer. With an empty box these tests — whose subject is
    # what a REFUSED preset leaves behind — would sit on that dialog instead.
    t._manual_target_name_edit.setText("ZZ-backout-probe")
    t._target_name_edit.setText("ZZ-backout-probe")
    return t


def _refuse(tab, monkeypatch):
    """Make every build step decline, the way a real refusal does."""
    for name in ("_generate_from_ti1", "_create_prebuilt_target"):
        monkeypatch.setattr(tab, name, lambda *a, **k: False, raising=False)


def _pick(tab, key):
    """Choose *key* the way the dropdown does: the combo moves first, then the
    handler runs. Calling the handler alone leaves the combo behind and makes
    the dropdown assertions meaningless."""
    idx = tab._preset_combo.findData(key)
    assert idx > 0, f"{key} is not in the dropdown"
    tab._preset_combo.blockSignals(True)
    tab._preset_combo.setCurrentIndex(idx)
    tab._preset_combo.blockSignals(False)
    tab._on_preset_selected(idx)
    return idx


def _pick_from_the_star(tab, key):
    """Choose *key* the way the ★ overlay does — this is the route that switches
    the mode to Manual, so it is the only one that can prove the mode goes back."""
    tab._activate_builtin_preset(key)


def _snapshot_settings(tab):
    return {k: tab._settings.get(k) for k in _PERSISTED}


# ---------------------------------------------------------------------------
# T1 — the settings that outlive the app run
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [_ENGINE_KEY, _PREBUILT_KEY])
def test_a_refused_preset_leaves_no_setting_changed(tab, monkeypatch, key):
    before = _snapshot_settings(tab)
    _refuse(tab, monkeypatch)
    _pick(tab, key)
    after = _snapshot_settings(tab)
    changed = {k: (before[k], after[k]) for k in _PERSISTED if before[k] != after[k]}
    assert not changed, f"a cancelled preset changed stored settings: {changed}"


def test_the_same_preset_accepted_DOES_change_them(tab, monkeypatch):
    """Negative control — without it, T1 could pass because nothing happens at
    all. The preset must really be writing these settings on the way in."""
    before = _snapshot_settings(tab)
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda *a, **k: True,
                        raising=False)
    monkeypatch.setattr(tab, "_create_prebuilt_target", lambda *a, **k: True,
                        raising=False)
    _pick(tab, _ENGINE_KEY)
    engine_after = _snapshot_settings(tab)
    _pick(tab, _PREBUILT_KEY)
    prebuilt_after = _snapshot_settings(tab)
    assert before != engine_after or before != prebuilt_after, (
        "no preset writes any persisted setting any more — T1 has stopped "
        "proving anything")


# ---------------------------------------------------------------------------
# T2 — the mode
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [_ENGINE_KEY, _PREBUILT_KEY])
def test_a_refused_preset_puts_the_mode_back(tab, monkeypatch, key):
    assert tab._current_mode() == "guided"
    _refuse(tab, monkeypatch)
    _pick_from_the_star(tab, key)
    assert tab._current_mode() == "guided", \
        "Cancel left the user in Manual, which is not where they were"


def test_the_star_really_does_move_the_mode(tab, monkeypatch):
    """Negative control for the test above: if ★ stopped switching to Manual,
    that test would pass while proving nothing."""
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda *a, **k: True,
                        raising=False)
    _pick_from_the_star(tab, _ENGINE_KEY)
    assert tab._current_mode() == "manual"


# ---------------------------------------------------------------------------
# T3 — the parameter panel, including a value the user set deliberately
# ---------------------------------------------------------------------------

def test_a_refused_preset_keeps_a_deliberate_margin(tab, monkeypatch):
    tab._switch_mode("manual")
    # Start on the OTHER instrument, so putting `-i` back re-applies a margin
    # default and would wipe the typed 10 unless `-m` is restored after it.
    other = "CM" if tab._prebuilt_instrument(_PREBUILT_KEY) == "i1" else "i1"
    tab._set_manual_value("printtarg", "-i", other)
    tab._set_manual_value("printtarg", "-m", 10)
    assert tab._manual_get("printtarg", "-m", None) == 10
    _refuse(tab, monkeypatch)
    _pick(tab, _PREBUILT_KEY)
    assert tab._manual_get("printtarg", "-i", None) == other
    assert tab._manual_get("printtarg", "-m", None) == 10, (
        "the margin the user typed was rewritten by a preset they refused "
        "(restore order: -i must go back BEFORE -m, or the instrument default "
        "overwrites it)")


@pytest.mark.parametrize("key", [_ENGINE_KEY, _PREBUILT_KEY])
def test_a_refused_preset_restores_every_printtarg_row(tab, monkeypatch, key):
    tab._switch_mode("manual")
    before = tab._snapshot_printtarg_fields()
    _refuse(tab, monkeypatch)
    _pick(tab, key)
    after = tab._snapshot_printtarg_fields()
    diff = [(b, a) for b, a in zip(before, after) if b != a]
    assert not diff, f"rows left on the refused preset's values: {diff}"


# ---------------------------------------------------------------------------
# T6 — the dropdown, and the trap that comes with putting it back
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [_ENGINE_KEY, _PREBUILT_KEY])
def test_a_refused_preset_leaves_the_dropdown_where_it_was(tab, monkeypatch, key):
    start = tab._preset_combo.currentIndex()
    _refuse(tab, monkeypatch)
    _pick(tab, key)
    assert tab._preset_combo.currentIndex() == start
    assert tab._last_preset_index == start


def test_the_dropdown_is_wired_to_activated_not_to_a_change(tab):
    """The combo must be on `activated`, not `currentIndexChanged`.

    Putting the dropdown back on the previous preset is only safe if choosing
    that same entry again still does something. `currentIndexChanged` is silent
    when the index does not move, which is how the first attempt at the revert
    moved the trap from the new preset onto the previous one.

    Measured on the wiring itself rather than by patching the handler: PyQt
    binds the slot when `connect` runs, so replacing the method afterwards —
    on the instance or on the class — is invisible to the connection, and such
    a probe passes while proving nothing.
    """
    combo = tab._preset_combo
    assert combo.receivers(combo.activated) == 1, \
        "the presets dropdown is not connected to `activated`"
    assert combo.receivers(combo.currentIndexChanged) == 0, (
        "the presets dropdown is still connected to `currentIndexChanged` — "
        "either instead of `activated` (the previous preset then cannot be "
        "re-chosen) or as well as it (one click dispatches twice)")


def test_the_star_overlay_dispatches_an_already_shown_preset(tab, monkeypatch):
    """`activated` is not emitted by `setCurrentIndex`, so ★ must call the
    handler itself — in both directions, including when the entry it wants is
    already the one on show."""
    seen = []
    monkeypatch.setattr(TabChart, "_on_preset_selected",
                        lambda self, idx: seen.append(idx))
    idx = tab._preset_combo.findData(_ENGINE_KEY)
    tab._preset_combo.blockSignals(True)
    tab._preset_combo.setCurrentIndex(idx)
    tab._preset_combo.blockSignals(False)
    tab._activate_builtin_preset(_ENGINE_KEY)
    assert seen == [idx], ("★ did not dispatch a preset that was already "
                           "showing in the dropdown")


# ---------------------------------------------------------------------------
# T7 — the family flags
# ---------------------------------------------------------------------------

_FLAGS = ("_tc918_active", "_knut_active", "_knut_active_key",
          "_prebuilt_active", "_prebuilt_key", "_applied_active",
          "_reflected_active", "_preset_ti1_path", "_vendor_debranded",
          "_layout_owned_by_build")


@pytest.mark.parametrize("key", [_ENGINE_KEY, _PREBUILT_KEY])
def test_a_refused_preset_leaves_no_family_flag_set(tab, monkeypatch, key):
    before = {f: getattr(tab, f, None) for f in _FLAGS}
    _refuse(tab, monkeypatch)
    _pick(tab, key)
    after = {f: getattr(tab, f, None) for f in _FLAGS}
    changed = {f: (before[f], after[f]) for f in _FLAGS if before[f] != after[f]}
    assert not changed, f"a refused preset left state behind: {changed}"


# ---------------------------------------------------------------------------
# T4 / T5 — these pass today and must keep passing
# ---------------------------------------------------------------------------

def test_an_accepted_preset_still_applies_everything(tab, monkeypatch):
    calls = []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda *a, **k: (calls.append(a), True)[1], raising=False)
    idx = _pick(tab, _ENGINE_KEY)
    assert calls, "the accepted preset never reached the build step"
    assert tab._knut_active is True
    assert tab._knut_active_key == _ENGINE_KEY
    assert tab._preset_combo.currentIndex() == idx
    assert tab._last_preset_index == idx


def test_an_accepted_prebuilt_preset_still_seeds_its_layout(tab, monkeypatch):
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda *a, **k: True,
                        raising=False)
    monkeypatch.setattr(tab, "_create_prebuilt_target", lambda *a, **k: True,
                        raising=False)
    _pick(tab, _PREBUILT_KEY)
    assert tab._manual_get("printtarg", "-i", None) \
        == tab._prebuilt_instrument(_PREBUILT_KEY)
    assert tab._manual_get("printtarg", "-p", None) \
        == tab._prebuilt_paper_code(_PREBUILT_KEY)
    assert tab._prebuilt_active is True


# ---------------------------------------------------------------------------
# Found ON SCREEN, not by any of the above (#175, 2026-08-28)
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine_off_tab(qapp, tmp_path):
    """A tab whose layout panel has never been seeded — the state a person is in
    with the ChromIQ engine switched off. The default `tab` fixture inherits the
    app-wide default, which is engine ON, so the panel is already inited there."""
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "engine_off.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("use_chromiq_layout_engine", False)
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("guided")
    return t


def test_a_refused_preset_does_not_leave_its_layout_in_an_unseeded_panel(
        engine_off_tab, monkeypatch):
    tab = engine_off_tab
    """The layout panel exists before it is ever SEEDED, and that is the gap.

    With the ChromIQ engine off, `_manual_panel_inited` is False and the panel
    is not on screen — but the widget is built and holds a recipe. Snapshotting
    only when the panel was "inited" therefore took nothing, so a refused engine
    preset left its own layout sitting in it: driven on screen, an A3 ColorMunki
    preset backed out of left CM / 420x297 / 200 dpi and its four margins in
    place, invisible until the person next switched the engine on and inherited
    a chart layout they had refused.
    """
    panel = tab._manual_layout_panel
    assert not tab._manual_panel_inited, \
        "this test needs the pre-seeding state — the fixture no longer starts there"
    before = panel.get_recipe()
    _refuse(tab, monkeypatch)
    _pick(tab, _ENGINE_KEY)
    after = panel.get_recipe()
    assert (after.instrument, after.paper, after.dpi) \
        == (before.instrument, before.paper, before.dpi), (
            f"the refused preset's layout stayed in the panel: "
            f"{before.instrument}/{before.paper}/{before.dpi} became "
            f"{after.instrument}/{after.paper}/{after.dpi}")
    assert after == before, "the refused preset left part of its recipe behind"


# ---------------------------------------------------------------------------
# The tick boxes — the whole restore of these passed 19/19 without them
# ---------------------------------------------------------------------------

def test_a_refused_preset_puts_every_tick_box_back(tab, monkeypatch):
    """Deleting the ENTIRE tick-box restore used to pass every test in this
    file, and three real faults were living in that blind spot: the command
    stamp was silently unticked, Triple Density was switched off while `-i` was
    momentarily not a ColorMunki, and the three Auto neutrals were left ticked
    beside boxes that had been re-enabled.

    So this moves every box in `_PRESET_CHECKS` away from where a preset would
    put it, and asserts all of them come back.
    """
    tab._switch_mode("manual")
    tab._set_manual_value("printtarg", "-i", "CM")     # Triple density is CM-only
    wanted = {}
    for attr in TabChart._PRESET_CHECKS:
        w = getattr(tab, attr, None)
        if w is None or not w.isEnabled():
            continue
        w.setChecked(not w.isChecked())
        wanted[attr] = w.isChecked()
    assert len(wanted) >= 6, f"too few boxes exercised: {sorted(wanted)}"

    _refuse(tab, monkeypatch)
    _pick(tab, _ENGINE_KEY)

    wrong = {a: (want, getattr(tab, a).isChecked())
             for a, want in wanted.items() if getattr(tab, a).isChecked() != want}
    assert not wrong, f"tick boxes not put back: {wrong}"


def test_the_greying_that_belongs_to_a_tick_box_comes_back_with_it(tab, monkeypatch):
    """A tick box restored without its greying leaves the panel contradicting
    itself. Measured before the fix: "Auto white/black/grey" ticked while the
    -e / -B / -g boxes beside them were enabled and read 0 instead of "Auto"."""
    tab._switch_mode("manual")
    for which, (_pw_attr, chk_attr) in tab._AUTO_NEUTRAL_MAP.items():
        chk = getattr(tab, chk_attr, None)
        if chk is not None:
            chk.setChecked(True)
            tab._on_auto_neutral_toggled(which, True)
    before = {}
    for which, (pw_attr, _c) in tab._AUTO_NEUTRAL_MAP.items():
        pw = getattr(tab, pw_attr, None)
        assert pw is not None and pw._control is not None
        before[which] = (pw._control.isEnabled(), pw._control.specialValueText())
    assert all(t == "Auto" for _e, t in before.values()), before

    _refuse(tab, monkeypatch)
    _pick(tab, _ENGINE_KEY)

    after = {which: (getattr(tab, pw_attr)._control.isEnabled(),
                     getattr(tab, pw_attr)._control.specialValueText())
             for which, (pw_attr, _c) in tab._AUTO_NEUTRAL_MAP.items()}
    assert after == before, (
        f"the Auto rows disagree with their own tick boxes: {before} -> {after}")


# ---------------------------------------------------------------------------
# Re-picking the entry that is already showing (the cost of `activated`)
# ---------------------------------------------------------------------------

def test_re_picking_none_does_not_wipe_what_the_person_typed(tab):
    """`activated` fires when someone opens the list and clicks the entry that
    is ALREADY ticked — an easy accident. On "none" that used to re-run the
    Default branch and rewrite every row from the stored defaults: measured, a
    typed margin of 17 and a patch count of 999 went back to 6 and 0, with
    nothing said. Only the built-ins re-dispatch (Basti, 2026-08-28)."""
    tab._switch_mode("manual")
    assert tab._preset_combo.currentIndex() == 0
    tab._set_manual_value("printtarg", "-m", 17)
    tab._set_manual_value("targen", "-f", 999)
    tab._preset_combo.activated.emit(0)
    assert tab._manual_get("printtarg", "-m", None) == 17
    assert tab._manual_get("targen", "-f", None) == 999


def test_re_picking_a_BUILT_IN_that_is_already_showing_does_dispatch(tab, monkeypatch):
    """…and the other half, which is the whole reason the combo moved to
    `activated`: a built-in put back on the dropdown after a refusal has to be
    choosable again."""
    calls = []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda *a, **k: (calls.append(1), True)[1], raising=False)
    idx = _pick(tab, _ENGINE_KEY)
    assert len(calls) == 1
    tab._preset_combo.activated.emit(idx)      # the entry already showing
    assert len(calls) == 2, "the built-in showing in the dropdown became unpickable"


# ---------------------------------------------------------------------------
# Nothing here may take ChromIQ down, or half-undo
# ---------------------------------------------------------------------------

def test_a_snapshot_that_cannot_be_read_leaves_the_preset_applied(tab, monkeypatch):
    """`_on_preset_selected` is a Qt slot. An exception escaping it does not
    just abort the undo — PyQt hands it to `sys.excepthook`, which ends in
    `qFatal()`, and ChromIQ aborts. Measured as SIGABRT before this guard.

    With no snapshot there is no undo, so the preset stays applied, which is
    exactly what happened before the feature existed."""
    def boom(*_a, **_k):
        raise RuntimeError("the state could not be read")
    monkeypatch.setattr(tab, "_is_deletable_preset", boom, raising=False)
    assert tab._snapshot_preset_state() is None
    _refuse(tab, monkeypatch)
    _pick(tab, _ENGINE_KEY)        # must not raise


def test_one_failing_step_does_not_take_the_rest_of_the_undo_with_it(tab, monkeypatch):
    """A raise part-way through leaves the tab worse than no undo at all — the
    rows back, but the dropdown, the name field and the family flags still on
    the preset that was refused. Every step is independent now."""
    start_combo = tab._preset_combo.currentIndex()
    monkeypatch.setattr(tab, "_write_back_settings",
                        lambda *_a, **_k: (_ for _ in ()).throw(
                            RuntimeError("boom in the settings step")),
                        raising=False)
    _refuse(tab, monkeypatch)
    _pick(tab, _ENGINE_KEY)        # must not raise
    assert tab._preset_combo.currentIndex() == start_combo, \
        "the dropdown was left on a preset that was refused"
    assert tab._knut_active is False, \
        "the tab still says a Spyderprint chart is loaded"


# ---------------------------------------------------------------------------
# The two paths the `_refuse` stub structurally cannot reach
# ---------------------------------------------------------------------------

def test_a_failed_replace_does_not_leave_the_app_on_another_project(tab, monkeypatch,
                                                                    tmp_path):
    """`_create_prebuilt_target` applies the typed name before it carries out an
    agreed "Replace it". When that archive fails it says nothing has happened —
    and used to leave the FileManager on the new project anyway, dropping a
    nested project's location with it (`set_target_name` clears the root
    override). The branch two lines above it always restored the target; this
    one did not."""
    fm = tab._file_mgr
    fm.set_target_name("AlreadyOpen")
    before = fm.target_snapshot()
    tab._manual_target_name_edit.setText("SomethingElse")
    monkeypatch.setattr(tab, "_gate_route_and_replace",
                        lambda *a, **k: (True, True), raising=False)
    monkeypatch.setattr(tab, "_perform_pending_replace",
                        lambda *a, **k: False, raising=False)
    ok = tab._create_prebuilt_target(_PREBUILT_KEY, gate_already_asked=True,
                                     s4_already_answered=True)
    assert ok is False
    assert fm.target_snapshot() == before, (
        f"the app was left on another project: {before} -> {fm.target_snapshot()}")


def test_an_agreed_replace_does_not_survive_the_undo(tab, monkeypatch):
    """"Replace it" is destructive and was agreed to for a build that then did
    not happen. Every consumer re-asks first, so nothing acts on a leftover
    today — but four earlier leaks of exactly this kind are why one live-preview
    render once archived a whole project with no window on screen."""
    tab._pending_replace = ("/some/root", "TheProject")
    tab._adopted_via_gate = True
    tab._adopt_run_choice = "run1"
    _refuse(tab, monkeypatch)
    _pick(tab, _ENGINE_KEY)
    assert tab._pending_replace is None, "an agreed archive outlived its window"
    assert tab._adopted_via_gate is False
    assert not hasattr(tab, "_adopt_run_choice")


def test_a_refused_preset_does_not_pin_a_setting_that_was_never_stored(tab,
                                                                       monkeypatch):
    """A value alone cannot tell "never written" from "written to today's
    default": `AppSettings.get` answers with the default for both. So putting
    the value back pinned keys that had never been in the person's file — and a
    pinned key stops following a changed default, which this project requires a
    migration to do.
    """
    absent = [k for k in TabChart._PRESET_PERSISTED_SETTINGS
              if not tab._settings.is_stored(k)]
    assert absent, "the fixture starts with every key already written"
    _refuse(tab, monkeypatch)
    _pick(tab, _PREBUILT_KEY)
    pinned = [k for k in absent if tab._settings.is_stored(k)]
    assert not pinned, f"a refused preset wrote keys that were never there: {pinned}"


def test_the_same_preset_accepted_MAY_pin_them(tab, monkeypatch):
    """Negative control. Applying a preset really does write these keys, so the
    test above is about the undo and not about nothing happening at all."""
    absent = [k for k in TabChart._PRESET_PERSISTED_SETTINGS
              if not tab._settings.is_stored(k)]
    monkeypatch.setattr(tab, "_create_prebuilt_target", lambda *a, **k: True,
                        raising=False)
    _pick(tab, _PREBUILT_KEY)
    assert [k for k in absent if tab._settings.is_stored(k)], (
        "no preset writes any of these keys any more — the test above has "
        "stopped proving anything")


# ---------------------------------------------------------------------------
# Found ON SCREEN in round 9 — a forced tick box whose side effects nobody redid
# ---------------------------------------------------------------------------

def test_triple_density_still_works_after_a_refused_preset(tab, monkeypatch):
    """A tick box has to be forced back with its signals blocked — its handler
    is not idempotent, and re-running it would stash the TRIPLE-density values
    as the "before" ones (#89). But then nothing redoes what the handler did.

    Measured on screen: after backing out of a preset, Triple Density still read
    "on", "Double density" beside it was clickable again, and unticking Triple
    Density changed nothing at all — the chart stayed at the triple-density
    spacing with nothing saying so. The box was there; it had stopped meaning
    anything.
    """
    tab._switch_mode("manual")
    tab._set_manual_value("printtarg", "-i", "CM")     # Triple density is CM-only
    tab._manual_td_check.setChecked(True)
    assert tab._td_saved_layout, "the fixture did not reach the triple-density state"
    before_stash = dict(tab._td_saved_layout)
    assert tab._manual_dd_pw.isEnabled() is False, "Double density should be greyed"

    _refuse(tab, monkeypatch)
    _pick(tab, _ENGINE_KEY)

    assert tab._manual_td_check.isChecked() is True
    assert tab._manual_dd_pw.isEnabled() is False, \
        "Double density was left clickable beside a ticked Triple Density"
    assert tab._td_saved_layout == before_stash, \
        "the layout Triple Density is hiding was lost, so unticking it reverts nothing"

    # …and the box still does what it says: unticking it puts the layout back.
    tab._manual_td_check.setChecked(False)
    assert tab._manual_get("printtarg", "-a", None) == before_stash["-a"]
    assert tab._manual_get("printtarg", "-m", None) == before_stash["-m"]
    assert tab._manual_get("printtarg", "-P", None) == before_stash["-P"]


def test_a_failing_row_restore_does_not_abandon_the_rest_of_the_undo(tab,
                                                                    monkeypatch):
    """Step 6 used to sit outside every guard, so ONE raise there skipped every
    step after it — the dropdown, the family flags and the instrument were left
    on the preset that had just been refused, which is the exact state the undo
    exists to prevent.

    The realistic trigger is a `ParameterWidget` whose C++ object has been
    deleted: reading `pw.flag` then raises `RuntimeError`, and the snapshot side
    already guarded that access while the restore did not. This test makes the
    step fail directly rather than planting a dead widget, because a dead widget
    in `_manual_widgets` also breaks panel code that has nothing to do with the
    undo, and the point here is that the undo carries on.
    """
    class Unreadable(dict):
        def items(self):
            raise RuntimeError("wrapped C/C++ object of type ParameterWidget "
                               "has been deleted")

    start_combo = tab._preset_combo.currentIndex()
    _refuse(tab, monkeypatch)
    real = tab._restore_preset_state

    def with_unreadable_rows(snap):
        snap = dict(snap)
        snap["widgets"] = Unreadable()
        return real(snap)

    monkeypatch.setattr(tab, "_restore_preset_state", with_unreadable_rows,
                        raising=False)
    _pick(tab, _ENGINE_KEY)          # must not raise

    assert tab._preset_combo.currentIndex() == start_combo, \
        "the dropdown was abandoned on a preset that was refused"
    assert tab._last_preset_index == start_combo
    assert tab._knut_active is False, \
        "the tab still says a Spyderprint chart is loaded"
    assert tab._pending_replace is None


def test_a_refused_preset_leaves_the_sections_the_person_opened_open(tab,
                                                                     monkeypatch):
    """The "targen parameters" section is collapsed by default, so opening it is
    a deliberate click — and a preset shut it again for good.

    `_update_preset_locks` collapses that frame while a preset locks the patch
    recipe, but on the way back the same method does nothing, because it only
    touches the frame while a preset is active. So the section stayed shut with
    every targen row the person had in view gone, and nothing said why. Worst
    under Run type = Calibration, where ChromIQ opens that section on purpose so
    "Single Channel Steps" — the row that decides the calibration — is in view.
    """
    tab._switch_mode("manual")
    grp = tab._manual_targen_grp
    grp.set_collapsed(False)                       # the deliberate click
    assert grp.is_collapsed() is False

    _refuse(tab, monkeypatch)
    _pick(tab, _ENGINE_KEY)

    assert grp.is_collapsed() is False, (
        "the section the person opened was shut by a preset they refused")


def test_a_preset_that_IS_applied_still_collapses_it(tab, monkeypatch):
    """Negative control. A preset locks the patch recipe and collapses the
    section on purpose (Knut), so the test above is about the undo and not about
    the collapsing having stopped."""
    tab._switch_mode("manual")
    grp = tab._manual_targen_grp
    grp.set_collapsed(False)
    monkeypatch.setattr(tab, "_generate_from_ti1", lambda *a, **k: True,
                        raising=False)
    _pick(tab, _ENGINE_KEY)
    assert grp.is_collapsed() is True, \
        "an applied preset no longer collapses the recipe — the test above proves nothing"
