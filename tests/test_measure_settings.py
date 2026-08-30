"""The Measure tab's per-target settings, and the guard that keeps them honest.

Knut put Measure in scope (#130: *"measure tab must be included"*) because two
of his own reports came from these controls — the ``-N`` that survived from an
earlier session and the resume tick that disagreed with itself.

`MEASURE_CONTROLS` is hand-written, which is the shape of mistake that has cost
this project several faults. The drift test below is therefore the important one
here: a `MeasureParams` field that nobody maps fails the suite instead of being
quietly absent from every target's stored settings.
"""
import dataclasses

import pytest

from workflow.measure_settings import (MEASURE_CONTROLS, NOT_A_SETTING, apply,
                                       snapshot)


class _Check:
    def __init__(self, on=False):
        self._on = on
        self._enabled = True
        self._tip = ""
    def isChecked(self):        return self._on
    def setChecked(self, v):    self._on = bool(v)
    # Enough of a widget to be greyed. The point of these tests is that a
    # DISABLED control keeps its value — so the fake has to be able to tell the
    # two apart, or it could not catch the bug it exists to catch.
    def setEnabled(self, v):    self._enabled = bool(v)
    def isEnabled(self):        return self._enabled
    def setToolTip(self, t):    self._tip = t
    def toolTip(self):          return self._tip


class _Combo:
    def __init__(self, data=("auto", "disable", "force"), current=0):
        self._data, self._i = list(data), current
    def currentData(self):      return self._data[self._i]
    def findData(self, v):      return self._data.index(v) if v in self._data else -1
    def setCurrentIndex(self, i): self._i = i
    def setEnabled(self, v):    self._enabled = bool(v)
    def isEnabled(self):        return getattr(self, "_enabled", True)


class _Opt:
    def __init__(self, key, on=False, widget=None):
        self.key, self.checkbox, self.widget = key, _Check(on), widget
        # The real option row carries these two as well: the frame the label
        # and value live in, and the flag that stops it emitting its argument
        # for an instrument that cannot honour it.
        self.row_widget = None
        self.suppressed = False


class _Tab:
    def __init__(self):
        self._m_suppress_cb = _Check(True)
        self._m_nocal_cb    = _Check(False)
        self._m_pbp_cb      = _Check(False)
        self._m_resume_cb   = _Check(False)
        self._m_bidir_combo = _Combo()
        self._chartread_opts = [_Opt("tolerance", widget=_Combo(("0.5", "0.7"))),
                                _Opt("highres")]


def test_the_drift_guard_every_setting_is_mapped_or_explained():
    """The one that matters: a new MeasureParams field cannot go unnoticed."""
    from workflow.measure_manager import MeasureParams

    fields = {f.name for f in dataclasses.fields(MeasureParams)}
    mapped = set(MEASURE_CONTROLS) | set(NOT_A_SETTING)
    forgotten = fields - mapped
    assert not forgotten, (
        f"{sorted(forgotten)} are MeasureParams fields that are neither stored "
        f"per target nor listed in NOT_A_SETTING with a reason — so they would "
        f"silently not follow the run"
    )


def test_nothing_is_excluded_that_does_not_exist():
    """A stale exclusion hides a real gap just as well as a missing one."""
    from workflow.measure_manager import MeasureParams

    fields = {f.name for f in dataclasses.fields(MeasureParams)}
    stale = set(NOT_A_SETTING) - fields
    assert not stale, f"NOT_A_SETTING lists fields that are gone: {sorted(stale)}"


def test_it_reads_the_controls():
    tab = _Tab()
    snap = snapshot(tab)
    assert snap["suppress_warnings"] == {"enabled": True, "value": True}
    assert snap["disable_initial_cal"] == {"enabled": True, "value": False}
    assert snap["bidirectional"]["value"] == "auto"


def test_it_reads_every_chartread_option():
    tab = _Tab()
    snap = snapshot(tab)
    assert "chartread.tolerance" in snap and "chartread.highres" in snap
    assert snap["chartread.tolerance"]["value"] == "0.5"


def test_a_round_trip_restores_both_halves():
    tab = _Tab()
    tab._m_nocal_cb.setChecked(True)
    tab._m_bidir_combo.setCurrentIndex(2)
    tab._chartread_opts[0].checkbox.setChecked(True)
    snap = snapshot(tab)

    other = _Tab()
    assert apply(other, snap) == []
    assert other._m_nocal_cb.isChecked() is True
    assert other._m_bidir_combo.currentData() == "force"
    assert other._chartread_opts[0].checkbox.isChecked() is True


def test_the_N_flag_does_not_leak_between_targets():
    """His beta.148 report, as a test: -N must not survive into another run."""
    a = _Tab(); a._m_nocal_cb.setChecked(True)
    b = _Tab()
    apply(b, snapshot(b))                      # b keeps its own, untouched
    assert b._m_nocal_cb.isChecked() is False, (
        "skip-initial-calibration leaked from one target to another"
    )


def test_an_unknown_key_is_reported_not_raised():
    tab = _Tab()
    assert apply(tab, {"gone": {"enabled": True, "value": 1}}) == ["gone"]
    assert apply(tab, {"suppress_warnings": "not a dict"}) == ["suppress_warnings"]


def test_a_missing_control_is_skipped_not_crashed():
    """A tab part-built (or a mode where a row is absent) must not raise."""
    class Bare:
        _chartread_opts = []
    assert snapshot(Bare()) == {}
    assert apply(Bare(), {"suppress_warnings": {"enabled": True, "value": True}}) == []


# ---------------------------------------------------------------------------
# The wiring on the real tab
# ---------------------------------------------------------------------------
class _Store:
    """A stand-in Run: the two methods the save/load pair actually uses."""

    def __init__(self, tmp_path):
        self.dir = tmp_path / "run1"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.id = "run1"
        from core.file_manager import RunMeta
        self._meta = RunMeta()

    def load_meta(self):        return self._meta
    def save_meta(self, m):     self._meta = m


class _WiredTab(_Tab):
    """The stand-in controls, plus the real save/load pair."""

    def __init__(self, store):
        super().__init__()
        self._store = store
        self._loading_measure_settings = False
        self._measure_written = {}
        self._target_ctl = None


@pytest.fixture
def wired(tmp_path, qapp):
    import ui.tabs.tab_measure as tm
    # `load_target_settings` re-asserts a guided refinement's ticks on both of
    # its exits, so the stub needs that method too — otherwise the real load
    # path cannot run here at all. Since #159 it re-asserts the CR30
    # patch-by-patch lock on both exits as well, for the same reason (a stored
    # `false` has just been written onto the screen), so that method and the
    # chart predicate it asks come along too. The stub has no `_ti1_path`, so
    # the lock answers "not a CR30" and does nothing here. The dead-option lock
    # rides along for the same reason — it is asserted from the same places and
    # asks the same predicate.
    for name in ("save_target_settings", "load_target_settings",
                 "_measure_written_cache", "_reassert_guided_refinement",
                 "_apply_cr30_pbp_lock", "_apply_cr30_dead_options",
                 # The dead-option lock also refreshes the panel's advice line,
                 # because that sentence is only true for a strip-reading
                 # instrument; it is a no-op when there is no such label.
                 "_refresh_calm_subtext",
                 "_chart_is_cr30", "_chart_file_for"):
        setattr(_WiredTab, name, getattr(tm.TabMeasure, name))
    # …and the class-level list the dead-option lock consults.
    _WiredTab.CR30_DEAD_OPTIONS = tm.TabMeasure.CR30_DEAD_OPTIONS
    store = _Store(tmp_path)
    return _WiredTab(store), store


def test_every_mapped_control_exists_on_the_real_tab(qapp):
    """A typo'd attribute name silently stores nothing — which is exactly how
    the port, the overlay toggle and the Live-preview controls followed the
    user from run to run until Knut's beta.3 test caught it. Ask the REAL
    tab: every key in MEASURE_CONTROLS must resolve to a live widget, and
    every one must appear in the snapshot."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import DEFAULTS
    from ui.tabs.tab_measure import TabMeasure

    class _S:
        def __init__(self):
            self._d = dict(DEFAULTS)

        def get(self, k, d=None):   return self._d.get(k, d)
        def set(self, k, v):        self._d[k] = v

    s = _S()
    tab = TabMeasure(ArgyllRunner(s), s)
    missing = [k for k, attr in MEASURE_CONTROLS.items()
               if getattr(tab, attr, None) is None]
    assert not missing, (
        f"MEASURE_CONTROLS names widgets the tab does not have: {missing}")
    snap = snapshot(tab)
    absent = [k for k in MEASURE_CONTROLS if k not in snap]
    assert not absent, f"mapped controls missing from the snapshot: {absent}"


def test_it_writes_the_settings_against_the_target(wired):
    tab, store = wired
    tab._m_nocal_cb.setChecked(True)
    assert tab.save_target_settings(store) is True
    assert store.load_meta().measure_settings["disable_initial_cal"]["value"] is True


def test_a_repeat_costs_nothing(wired):
    """§3a Q-4 — the same change-check the Create Chart tab has."""
    tab, store = wired
    assert tab.save_target_settings(store) is True
    for _ in range(4):
        assert tab.save_target_settings(store) is False


def test_a_real_change_still_lands_after_a_no_op(wired):
    tab, store = wired
    tab.save_target_settings(store)
    tab._m_resume_cb.setChecked(True)
    assert tab.save_target_settings(store) is True
    assert store.load_meta().measure_settings["resume"]["value"] is True


def test_a_write_never_resurrects_a_deleted_target(wired):
    """Knut's beta.102 rule, which has now caught this shape three times."""
    import shutil
    tab, store = wired
    tab.save_target_settings(store)
    shutil.rmtree(store.dir)
    assert tab.save_target_settings(store) is False
    assert not store.dir.exists(), "the write recreated a deleted run"


def test_loading_is_guarded_against_re_entry(wired):
    tab, store = wired
    tab._loading_measure_settings = True
    assert tab.save_target_settings(store) is False, (
        "a save ran while settings were being loaded"
    )


def test_the_written_cache_is_per_tab(tmp_path, qapp, wired):
    """A bare class attribute made two tabs share one — writes went missing."""
    tab_a, store = wired
    tab_a.save_target_settings(store)
    tab_b = _WiredTab(store)
    tab_b._m_pbp_cb.setChecked(True)
    assert tab_b.save_target_settings(store) is True, (
        "the second tab inherited the first's 'already written' marks"
    )


def test_the_two_tabs_use_one_store_resolver():
    """Two copies of this is how the three run types came to diverge."""
    import inspect

    import ui.tabs.tab_measure as tm
    src = inspect.getsource(tm.TabMeasure.save_target_settings)
    assert "store_for_target" in src


def test_a_target_with_nothing_stored_does_not_inherit_the_last_one(wired, monkeypatch):
    """The bug the on-screen drive found while all the tests above passed.

    Tick "skip initial calibration" on run 1, switch to run 2 — and it was
    still ticked, because loading returned early and left the previous
    target's values on screen. That is Knut's beta.148 `-N` leak, rebuilt by
    the very feature meant to prevent it.

    None of the tests above caught it: they all exercise a target that HAS
    settings. This one exercises the empty case, which is the common one.
    """
    tab, store = wired
    restored = []
    tab._restore_defaults = lambda: restored.append(True)
    tab._m_nocal_cb.setChecked(True)          # as if left over from run 1

    assert tab.load_target_settings.__name__ == "load_target_settings"
    # run2 has nothing stored…
    from workflow.per_target_settings import store_for_target  # noqa: F401
    monkeypatch.setattr("workflow.per_target_settings.store_for_target",
                        lambda _ctl: store)
    store.load_meta().measure_settings = {}
    assert tab.load_target_settings() is False
    assert restored, (
        "nothing put the tab back to its defaults, so the previous target's "
        "settings stayed on screen"
    )


# ---------------------------------------------------------------------------
# A target's record is the only thing that decides that target's settings
# ---------------------------------------------------------------------------
def _real_tab(qapp):
    from core.argyll_runner import ArgyllRunner
    from core.settings import DEFAULTS
    from ui.tabs.tab_measure import TabMeasure

    class _S:
        def __init__(self):
            self._d = dict(DEFAULTS)

        def get(self, k, d=None):   return self._d.get(k, d)
        def set(self, k, v):        self._d[k] = v

    return TabMeasure(ArgyllRunner(_S()), _S())


def test_a_stored_manual_value_is_not_overwritten_by_its_guided_twin(qapp):
    """The two modules mirror their shared controls, and `apply` restores the
    Manual key fifteen keys before its Guided twin — so the Guided write
    travelled back down the link and replaced the value that had just been
    restored from the file.

    Found switching between runs of a real project: the stored ``-p`` was not
    merely displayed wrong, the next save wrote the loss into meta.json. The
    binding rule is `docs/design/per_target_settings.md` — a target's settings
    come from that target's own record.

    This needs the REAL tab: the fault lives in the mirror, which the stand-in
    controls above do not have.
    """
    tab = _real_tab(qapp)
    stored = {
        "patch_by_patch":        {"enabled": True,  "value": True},
        "patch_by_patch_guided": {"enabled": False, "value": False},
    }
    assert list(MEASURE_CONTROLS).index("patch_by_patch") < \
        list(MEASURE_CONTROLS).index("patch_by_patch_guided"), (
        "the ordering this test is about has changed — re-read the test")

    assert apply(tab, stored) == []
    qapp.processEvents()
    assert tab._m_pbp_cb.isChecked() is True, (
        "Manual's stored True was overwritten by Guided's stored False")
    assert tab._pbp_cb.isChecked() is False, "Guided lost its own stored value"

    # …and the loss is not merely on screen: the next save files it.
    assert snapshot(tab)["patch_by_patch"]["value"] is True


def test_every_linked_pair_keeps_its_own_stored_value(qapp):
    """Not just patch-by-patch: the same shape applies to every control both
    modules store, so cross the whole set rather than the one that was
    reported."""
    tab = _real_tab(qapp)
    pairs = [("suppress_warnings", "suppress_warnings_guided",
              "_m_suppress_cb", "_suppress_cb"),
             ("patch_by_patch", "patch_by_patch_guided", "_m_pbp_cb", "_pbp_cb"),
             ("bidirectional_auto", "bidirectional_auto_guided",
              "_m_bidir_auto_cb", "_bidir_auto_cb")]
    for m_key, g_key, m_attr, g_attr in pairs:
        if g_key not in MEASURE_CONTROLS:
            continue
        for m_val in (True, False):
            stored = {m_key: {"enabled": m_val, "value": m_val},
                      g_key: {"enabled": not m_val, "value": not m_val}}
            apply(tab, stored)
            qapp.processEvents()
            assert getattr(tab, m_attr).isChecked() is m_val, (
                f"{m_key}: Manual's stored {m_val} did not survive")
            assert getattr(tab, g_attr).isChecked() is (not m_val), (
                f"{g_key}: Guided's stored {not m_val} did not survive")


def test_the_link_still_works_for_the_users_own_edits(qapp):
    """The counterweight. Suspending the mirror while a record is applied must
    not leave it suspended: a shared, visible control still has to follow
    between the modules when the USER changes it."""
    tab = _real_tab(qapp)
    apply(tab, {"patch_by_patch": {"enabled": False, "value": False},
                "patch_by_patch_guided": {"enabled": False, "value": False}})
    qapp.processEvents()
    tab._m_pbp_cb.setChecked(True)
    qapp.processEvents()
    assert tab._pbp_cb.isChecked() is True, "the link did not come back on"


def test_a_record_that_speaks_for_one_half_still_sets_both(qapp):
    """Suspending the mirror closed a data loss and opened a leak.

    `resume` has no Guided key at all — `MEASURE_CONTROLS` maps it to
    `_m_resume_cb` alone — so a record can only ever speak for the Manual half.
    The mirror used to carry it across; suspended, Guided's box kept the
    PREVIOUS target's tick, and the next save filed that as this target's own.
    That is the §4 leak the per-target store exists to prevent, and three places
    read the Guided box: the `-r` flag, the #134 overlay dialog, and the
    decision whether to archive the existing .ti3.
    """
    tab = _real_tab(qapp)
    tab._m_resume_cb.setChecked(True)              # the target we are leaving
    qapp.processEvents()
    assert tab._resume_cb.isChecked() is True      # linked, so both are on

    apply(tab, {"resume": {"enabled": False, "value": False}})
    qapp.processEvents()
    assert tab._m_resume_cb.isChecked() is False
    assert tab._resume_cb.isChecked() is False, (
        "Guided kept the previous target's resume tick")


def test_a_legacy_record_carries_the_tolerance_to_both_modules(qapp):
    """The one option both modules still own, and the one the legacy migration
    deliberately leaves alone because it belongs to both.

    A record written before the modules split carries only `chartread.tolerance`
    — a number that goes to the instrument. Without this, Manual keeps the
    previous target's scan tolerance.
    """
    tab = _real_tab(qapp)
    for o in tab._m_chartread_opts:
        if o.key == "tolerance":
            o.checkbox.setChecked(True)
            o.widget.setValue(2.5)
    qapp.processEvents()

    apply(tab, {"chartread.tolerance": {"enabled": True, "value": 0.4}})
    qapp.processEvents()
    manual = next(o for o in tab._m_chartread_opts if o.key == "tolerance")
    assert abs(manual.widget.value() - 0.4) < 1e-6, (
        f"Manual kept {manual.widget.value()}, the previous target's tolerance")


def test_both_halves_stored_still_beats_the_pair_sync(qapp):
    """The counterweight: filling in a half-covered pair must not undo the fix
    it was added to. When the record speaks for BOTH, each keeps its own."""
    tab = _real_tab(qapp)
    apply(tab, {"patch_by_patch":        {"enabled": True,  "value": True},
                "patch_by_patch_guided": {"enabled": False, "value": False}})
    qapp.processEvents()
    assert tab._m_pbp_cb.isChecked() is True
    assert tab._pbp_cb.isChecked() is False
