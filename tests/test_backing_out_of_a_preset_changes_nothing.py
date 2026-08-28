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
# back too, 2026-08-28).
_PERSISTED = (
    "use_chromiq_layout_engine",
    "helper_markers_show",
    "helper_marker_edge_mm",
    "helper_marker_len_mm",
    "helper_marker_per_patch",
    "helper_markers_top_bottom",
    "helper_markers_sides",
)


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
