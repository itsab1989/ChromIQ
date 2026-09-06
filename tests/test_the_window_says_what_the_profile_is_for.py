"""Knut's beta 10 batch for "Build profile with scanner or camera", all five.

*"I think we could make the 'Profile my printer from this scan' option a part
of several user cases, maybe called 'Usage Scenario:' as a heading"* — plus
three factual errors in the printer-mode help, an invisible `-R`, a white-point
default that is wrong for two of the four profile types, and a request that the
profile type, quality and white point be chosen from the patch count.

**All five set the same three controls, so there is one mechanism, not three.**
`scanner_colprof.SETUP_SMALL` / `SETUP_LARGE` is the whole rule; the usage
scenario's everyday case IS that rule; and the two "(recommended for …)"
markers on the white-point dropdown are DERIVED from it. Nothing here can
disagree with anything else here, and the first three tests are what says so.

**And the hard rule, which is why B8-71 was deferred in the first place:** an
existing target must not have settings applied to it on first open, or its next
profile silently changes and the user is never told. One predicate,
`_may_auto_setup`, enforces it, and it is asked by every automatic path.
`_ctx_stored` is computed ONCE, at construction, from the settings store — not
from `_ctx_cfg`, which gains an entry for every bucket the window merely
visits.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                       # noqa: E402

from core.settings import DEFAULTS                             # noqa: E402
from ui.dialogs import scanner_colprof as sc                   # noqa: E402
from workflow.profile_builder import ProfileBuilder            # noqa: E402


class _FakeSettings:
    """DEFAULTS with a hermetic output root, and a real dict behind get/set.

    `custom_output_path` must never be left at its "" default here: the window
    resolves projects through it, and "" reaches the user's own ~/ChromIQ.
    """

    def __init__(self, **overrides):
        self._store = {**DEFAULTS, **overrides}
        if not self._store.get("custom_output_path"):
            self._store["custom_output_path"] = tempfile.mkdtemp(
                prefix="chromiq-cj-")

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def _dialog(settings=None):
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    return ScannerProfileDialog(object(), settings or _FakeSettings())


def _three(dlg):
    """What the window is set to right now, in the rule's own vocabulary."""
    return {"ptype": dlg._ptype.currentData(),
            "quality": dlg._pq.currentData(),
            "wp_mode": str(dlg._adv_vals.get("wp_mode",
                                             sc.WP_MODE_DEFAULT))}


def _load_chart(dlg, n_patches: int):
    """Give the window a chart of a known size, the way picking one does.

    `_known_patch_count` reads `self._layout`, and `_refresh` is where every
    chart-picking path ends. This is the same two lines `_chart_geometry_ready`
    runs, without needing a real file on disk for a question that is only about
    how many patches there are.
    """
    dlg._layout = {"patches": [{"page": 0, "x": 1, "y": 1, "w": 1, "h": 1,
                                "id": f"A{i}"} for i in range(n_patches)]}
    dlg._chart_measured = True
    dlg._refresh()


# ==========================================================================
# 1. ONE RULE. The three mechanisms are the same table, so they cannot fight
# ==========================================================================
def test_the_patch_count_rule_is_knuts_rule():
    """*"below 100 patches, Shaper + Matrix with quality Medium and Map chart
    white to white. At 100 or above, cLUT XYZ table with quality High and Scan
    white to a perfect white surface."*"""
    assert sc.SETUP_CROSSOVER == 100
    assert sc.setup_for_patch_count(24) == {"ptype": "s", "quality": "m",
                                            "wp_mode": ""}
    assert sc.setup_for_patch_count(99) == sc.setup_for_patch_count(24)
    assert sc.setup_for_patch_count(100) == {"ptype": "x", "quality": "h",
                                             "wp_mode": "uR"}
    assert sc.setup_for_patch_count(288) == sc.setup_for_patch_count(100)
    # …and it says nothing at all about a size nobody has supplied.
    assert sc.setup_for_patch_count(None) is None
    assert sc.setup_for_patch_count(0) is None


def test_the_everyday_scenario_is_that_same_rule_and_not_a_second_answer():
    """If scenario 1 had its own three fixed values it would contradict the
    patch-count rule the moment a chart was loaded. It has none: it IS the
    rule."""
    for n in (None, 0, 24, 49, 99, 100, 288, 864):
        assert sc.scenario_setup(sc.SCENARIO_EVERYDAY, n) == \
            sc.setup_for_patch_count(n)


def test_the_white_point_markers_are_derived_from_the_same_table():
    """Knut's item 4 and item 5 are the same fact said twice, so they are
    written once. A change to the setup table moves the dropdown labels with
    it, and this test is what makes that literally true."""
    assert set(sc.WP_MODE_RECOMMENDED) == {sc.SETUP_LARGE["wp_mode"],
                                           sc.SETUP_SMALL["wp_mode"]}
    assert sc.WP_MODE_RECOMMENDED[sc.SETUP_LARGE["wp_mode"]] == "clut"
    assert sc.WP_MODE_RECOMMENDED[sc.SETUP_SMALL["wp_mode"]] == "matrix"
    # …and the two halves of the claim are true of the table itself: the large
    # row really is a cLUT and the small row really is a matrix.
    assert sc.SETUP_LARGE["ptype"] in sc.CLUT_ALGOS
    assert sc.SETUP_SMALL["ptype"] in sc.MATRIX_ALGOS


def test_the_two_matrix_types_and_the_two_clut_types_are_all_four():
    """A profile type in neither tuple would be a type the advice is silent
    about, and the silence would be invisible."""
    assert set(sc.CLUT_ALGOS) | set(sc.MATRIX_ALGOS) == \
        {d for d, _ in sc.PTYPE_CHOICES}
    assert not set(sc.CLUT_ALGOS) & set(sc.MATRIX_ALGOS)


# ==========================================================================
# 2. The scenarios themselves
# ==========================================================================
def test_the_measuring_scenario_sets_the_three_measured_settings():
    """cLUT XYZ, Quality High, -ua. Every one of the three is a held-out
    measurement (B8-69), not colour-management lore."""
    for n in (None, 24, 288, 864):
        assert sc.scenario_setup(sc.SCENARIO_INSTRUMENT, n) == {
            "ptype": "x", "quality": "h", "wp_mode": "ua"}


def test_the_measuring_scenario_does_not_set_restrict_white_black_primaries():
    """Measured beside `-ua` on a cLUT it is a complete no-op, and on a cLUT it
    cannot restrict primaries at all (`profin.c:1070` sets ICX_CLIP_WB only).
    Setting it would be cargo cult, and the design says so by name."""
    assert "-R" not in sc.SETUP_INSTRUMENT


def test_the_printer_scenario_changes_no_colprof_setting():
    """It is today's printer tick. The printer bucket already defaults to a Lab
    cLUT and white-point handling is stripped from an output build."""
    for n in (None, 24, 288):
        assert sc.scenario_setup(sc.SCENARIO_PRINTER, n) is None


def test_the_three_are_listed_in_the_order_you_would_do_them(_app):
    """The correction that makes the control work. As three flat alternatives a
    user who wants a printer profile picks the third, has no measuring profile,
    and is stuck: today's dead end with a nicer label."""
    dlg = _dialog()
    try:
        order = [b.text() for b in dlg._scenario_group.buttons()]
        keys = list(dlg._scenario_radios)
        assert keys == [sc.SCENARIO_EVERYDAY, sc.SCENARIO_INSTRUMENT,
                        sc.SCENARIO_PRINTER], keys
        assert "everyday scanning" in order[0]
        assert "measuring instrument" in order[1]
        assert "my printer" in order[2]
    finally:
        dlg.deleteLater()


def test_the_second_and_third_say_they_are_two_steps_of_one_job(_app):
    """Without these two clauses the list is three alternatives again."""
    dlg = _dialog()
    try:
        glosses = [w.text() for w in dlg.findChildren(type(dlg._mode_note))]
        joined = "\n".join(glosses)
        assert "the printer scenario below uses it" in joined
        assert "the scenario above" in joined
    finally:
        dlg.deleteLater()


# ==========================================================================
# 3. Pre-select, never lock
# ==========================================================================
def test_choosing_a_scenario_sets_the_three_controls(_app):
    dlg = _dialog()
    try:
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        assert _three(dlg) == {"ptype": "x", "quality": "h", "wp_mode": "ua"}
    finally:
        dlg.deleteLater()


def test_a_scenario_locks_nothing(_app):
    """Knut said "pre-selects". Every control it touched stays the user's."""
    dlg = _dialog()
    try:
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        assert dlg._ptype.isEnabled() and dlg._pq.isEnabled()
        assert dlg._adv_editor._wp_mode.isEnabled()
        dlg._ptype.setCurrentIndex(dlg._ptype.findData("s"))
        assert dlg._ptype.currentData() == "s"
    finally:
        dlg.deleteLater()


def test_the_window_names_the_divergence_when_the_user_overrides(_app):
    """*"…and name the divergence when the user overrides."* It names the
    SETTING and both values, because "your settings do not match" is not
    something anybody can act on."""
    dlg = _dialog()
    try:
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        assert not dlg._scenario_note.isVisibleTo(dlg)
        dlg._ptype.setCurrentIndex(dlg._ptype.findData("s"))
        said = dlg._scenario_note.text()
        assert dlg._scenario_note.isVisibleTo(dlg), "the override is not named"
        assert "Profile type" in said
        assert "Shaper + matrix" in said and "XYZ table" in said
        # …and nothing was put back.
        assert dlg._ptype.currentData() == "s"
    finally:
        dlg.deleteLater()


def test_a_setting_the_user_changed_is_never_chosen_for_them_again(_app):
    """Rule 2 of the design, with the one amendment this work needed: the
    everyday scenario DOES re-apply when the patch count changes, because a
    rule keyed on the patch count cannot do anything else. It stops for good
    the moment the user touches one of the three."""
    dlg = _dialog()
    try:
        _load_chart(dlg, 288)
        assert _three(dlg)["ptype"] == "x"
        dlg._ptype.setCurrentIndex(dlg._ptype.findData("m"))   # a hand edit
        _load_chart(dlg, 24)                                   # a small chart
        assert _three(dlg)["ptype"] == "m", \
            "a choice the user made was overwritten by the patch-count rule"
    finally:
        dlg.deleteLater()


def test_the_custom_state_is_a_state_and_not_a_fourth_option(_app):
    dlg = _dialog()
    try:
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        dlg._scenario_ctx[dlg._active_ctx] = None
        dlg._sync_scenario_ui()
        assert not any(rb.isChecked() for rb in dlg._scenario_radios.values())
        assert dlg._scenario_note.isVisibleTo(dlg)
        assert "no scenario is selected" in dlg._scenario_note.text()
    finally:
        dlg.deleteLater()


# ==========================================================================
# 4. THE HARD RULE: a target with stored settings is left alone
# ==========================================================================
def _saved(ctx="chart", scenario=None, **main):
    """A settings store carrying a bucket somebody actually saved.

    *scenario* None is a configuration written BEFORE this feature: no scenario
    key at all, which is the whole of the migration. Pass one to get a bucket
    saved by this version.
    """
    cfg = {"main": {"ptype": "s", "quality": "m", "description": "",
                    **main},
           "adv": {"wp_mode": "ua", sc.ADV_SCHEMA_KEY: sc.ADV_SCHEMA_VERSION}}
    if scenario is not None:
        cfg["scenario"] = scenario
    return _FakeSettings(scanner_colprof_configs={ctx: cfg})


def test_a_bucket_with_stored_settings_is_never_set_up_on_first_open(_app):
    """Somebody profiled a scanner last month and reopens the window. They get
    what they had, whatever size the target is.

    TWO buckets, and the second is the one that needs `_ctx_stored` at all.
    A configuration written before this feature has no scenario, so the
    scenario check in `_maybe_auto_setup` already refuses it and the stored-set
    gate never gets a word in. The case that rests on the gate alone is a
    bucket saved BY this version, on the everyday scenario, whose owner then
    changed a setting and saved it: the scenario says "yes, choose for me" and
    only `_ctx_stored` says no. A mutation run found this hole, which is why
    both halves are here.
    """
    for scenario in (None, sc.SCENARIO_EVERYDAY):
        dlg = _dialog(_saved(scenario=scenario))
        try:
            assert dlg._active_ctx == "chart"
            assert "chart" in dlg._ctx_stored
            before = _three(dlg)
            assert before == {"ptype": "s", "quality": "m", "wp_mode": "ua"}
            _load_chart(dlg, 864)          # far over the crossover
            assert _three(dlg) == before, (
                f"a stored bucket (scenario={scenario!r}) had its settings "
                f"changed by the patch-count rule")
        finally:
            dlg.deleteLater()


def test_a_stored_bucket_from_before_this_feature_shows_no_scenario(_app):
    """Its settings match no scenario and were never labelled with one, so the
    honest answer is the Custom state. Anything else would claim the user had
    chosen something they had never seen."""
    dlg = _dialog(_saved())
    try:
        assert dlg._scenario_for("chart") is None
        assert not any(rb.isChecked() for rb in dlg._scenario_radios.values())
    finally:
        dlg.deleteLater()


def test_the_stored_set_is_read_from_the_store_and_not_from_the_visits(_app):
    """The trap this rule dies in: `_ctx_cfg` gains an entry for every bucket
    the window merely VISITS (`_snapshot_context`), so a user who ticked and
    unticked the printer box would look like a user who had saved settings.
    `_ctx_stored` is taken once, from the store."""
    dlg = _dialog()
    try:
        assert dlg._ctx_stored == set()
        dlg._printer_cb.setChecked(True)
        dlg._printer_cb.setChecked(False)
        dlg._mode_standard.setChecked(True)
        dlg._mode_chromiq.setChecked(True)
        assert set(dlg._ctx_cfg) >= {"chart", "printer"}    # visited
        assert dlg._ctx_stored == set(), \
            "merely visiting a bucket made it look saved"
    finally:
        dlg.deleteLater()


def test_a_bucket_nobody_ever_saved_is_set_up_from_the_patch_count(_app):
    """The other half: the rule has to actually fire, or item 5 is not built."""
    dlg = _dialog()
    try:
        _load_chart(dlg, 49)
        assert _three(dlg) == {"ptype": "s", "quality": "m", "wp_mode": ""}
    finally:
        dlg.deleteLater()
    dlg = _dialog()
    try:
        _load_chart(dlg, 288)
        assert _three(dlg) == {"ptype": "x", "quality": "h", "wp_mode": "uR"}
    finally:
        dlg.deleteLater()


def test_the_patch_count_rule_is_off_in_printer_mode(_app):
    """*"…but only when 'Profile my printer from this scan' is OFF."* A printer
    profile is an output profile: the type default is Argyll's Lab cLUT and
    white-point handling does not apply to it at all."""
    dlg = _dialog()
    try:
        dlg._printer_cb.setChecked(True)
        assert dlg._active_ctx == "printer"
        _load_chart(dlg, 864)
        assert dlg._ptype.currentData() == "l", \
            "the scanner rule reached into a printer build"
        assert dlg._pq.currentData() == "m"
    finally:
        dlg.deleteLater()


def test_the_printer_guard_holds_in_the_window_where_it_is_reachable(_app):
    """The `_printer_mode()` half of that guard is not decoration.

    `_on_printer_toggled` re-picks the chart (#105, so a sidecar-less chart is
    re-evaluated when the tick goes on) BEFORE it calls
    `_sync_colprof_context`. Inside that window the tick is already on and
    `_active_ctx` is still the SCANNER bucket, and `_set_chart` ends in
    `_refresh`, which is where the patch-count rule runs. Without the
    `_printer_mode()` test, ticking the printer box would write scanner
    settings into the scanner bucket on the way past. This reproduces that
    window directly, because arranging the real interleaving needs a chart file
    on disk and the state it proves is one line wide.

    A mutation run is what found this: removing the guard left every black-box
    assertion green, because `_scenario_for("printer")` had already refused.
    """
    dlg = _dialog()
    try:
        _load_chart(dlg, 24)                       # chart bucket: s / m / ""
        before = _three(dlg)
        assert before["ptype"] == "s"
        dlg._printer_cb.blockSignals(True)
        dlg._printer_cb.setChecked(True)           # the tick is on…
        dlg._printer_cb.blockSignals(False)
        assert dlg._active_ctx == "chart"          # …and the bucket has not moved
        dlg._layout = {"patches": [{"page": 0, "x": 1, "y": 1, "w": 1, "h": 1,
                                    "id": f"A{i}"} for i in range(864)]}
        dlg._maybe_auto_setup()
        assert _three(dlg) == before, (
            "ticking the printer box let the scanner rule write into the "
            "scanner bucket on its way past")
    finally:
        dlg.deleteLater()


def test_it_applies_to_a_bought_target_as_well_as_a_chart(_app):
    """*"Applies to both 'A chart I made in ChromIQ' and 'A standard target I
    own'."* The standard combo already knows its target's size."""
    dlg = _dialog()
    try:
        dlg._mode_standard.setChecked(True)
        assert dlg._active_ctx == "standard"
        n = dlg._known_patch_count()
        assert n and n >= sc.SETUP_CROSSOVER, n
        assert _three(dlg) == {"ptype": "x", "quality": "h", "wp_mode": "uR"}
    finally:
        dlg.deleteLater()


def test_the_scenario_is_stored_with_the_bucket(_app):
    """So reopening SHOWS it without RE-APPLYING it."""
    settings = _FakeSettings()
    dlg = _dialog(settings)
    try:
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        dlg._save_defaults_clicked()
    finally:
        dlg.deleteLater()
    stored = settings.get("scanner_colprof_configs", {})
    assert stored["chart"]["scenario"] == sc.SCENARIO_INSTRUMENT
    dlg = _dialog(settings)
    try:
        assert dlg._scenario_for("chart") == sc.SCENARIO_INSTRUMENT
        assert dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].isChecked()
        # …and it did NOT re-apply: a stored bucket is off limits, so a big
        # chart does not move a thing.
        before = _three(dlg)
        _load_chart(dlg, 24)
        assert _three(dlg) == before
    finally:
        dlg.deleteLater()


# ==========================================================================
# 5. "Restrict white, black & primaries" is visible when it is in force
# ==========================================================================
def test_the_R_switch_is_shown_ticked_and_locked_when_the_white_point_carries_it(_app):
    """Knut: *"the -R checkbox is invisible."* It is on the command line, so
    an unticked box is false."""
    dlg = sc.ScannerAdvancedDialog({}, None, printer=False)
    try:
        cb = dlg._flags["-R"]
        assert dlg._wp_mode.currentData() == sc.WP_MODE_DEFAULT
        assert cb.isChecked() and not cb.isEnabled()
        assert dlg._r_note.isVisibleTo(dlg)
        assert "White point handling" in dlg._r_note.text()
    finally:
        dlg.deleteLater()


def test_the_locked_tick_changes_no_command_line(_app):
    """The requirement Knut attached to it: whatever is shown, the command must
    not change. It does not, because `values()` writes the user's own answer
    and `-R` was already being emitted by the white-point entry."""
    dlg = sc.ScannerAdvancedDialog({}, None, printer=False)
    try:
        vals = dlg.values()
        assert vals["-R"] is False, "the display state was stored as a choice"
    finally:
        dlg.deleteLater()

    def args(adv):
        p = sc.make_profile_params(Path("x.ti3"), "S",
                                   {"ptype": "s", "quality": "m"}, adv)
        return ProfileBuilder(None)._build_args(p)

    shown = args({**vals})
    # what the window ran before any of this existed: wp_mode uR, -R unticked
    was = args({"wp_mode": sc.WP_MODE_DEFAULT, "-R": False})
    assert shown == was, (shown, was)
    assert shown.count("-R") == 1 and "-u" in shown


def test_the_R_switch_comes_back_with_whatever_the_user_had(_app):
    """Locked is not "taken away". Leave the entry that carries it and the
    switch is the user's again, holding their own answer."""
    dlg = sc.ScannerAdvancedDialog({"wp_mode": "ua", "-R": True}, None,
                                   printer=False)
    try:
        cb = dlg._flags["-R"]
        assert cb.isEnabled() and cb.isChecked()
        dlg.set_wp_mode(sc.WP_MODE_DEFAULT)
        assert cb.isChecked() and not cb.isEnabled()
        assert dlg.values()["-R"] is True, "the user's own -R was thrown away"
        dlg.set_wp_mode("ua")
        assert cb.isEnabled() and cb.isChecked()
        assert dlg.values()["-R"] is True
    finally:
        dlg.deleteLater()


def test_saving_defaults_on_that_entry_never_stores_an_R_nobody_chose(_app):
    """The trap in ticking a box for somebody: it gets SAVED, and then a later
    switch to "Map chart white to white" carries a clamp they never asked
    for."""
    dlg = sc.ScannerAdvancedDialog({}, None, printer=False)
    try:
        stored = dlg.values()
    finally:
        dlg.deleteLater()
    assert stored["-R"] is False
    reopened = sc.ScannerAdvancedDialog(stored, None, printer=False)
    try:
        reopened.set_wp_mode("")           # Map chart white to white
        assert reopened.values()["-R"] is False
        assert reopened._flags["-R"].isEnabled()
    finally:
        reopened.deleteLater()


def test_a_printer_build_has_no_such_switch_to_lock(_app):
    """White-point handling is an input-profile setting; the printer side of
    this dialog has no white-point row at all, so nothing may lock anything."""
    dlg = sc.ScannerAdvancedDialog({"-R": True}, None, printer=True)
    try:
        assert dlg._wp_mode is None and dlg._r_note is None
        assert dlg._flags["-R"].isEnabled()
        assert dlg.values()["-R"] is True
    finally:
        dlg.deleteLater()


# ==========================================================================
# 6. The three factual errors in the printer-mode help (Knut, beta 10)
# ==========================================================================
def _printer_help(dlg) -> str:
    from ui.tooltip_button import TooltipButton
    for b in dlg.findChildren(TooltipButton):
        if b._title == "Printer profile from a scan":
            return b._body
    raise AssertionError("the printer-mode help has gone")


def test_the_help_no_longer_says_the_profile_must_come_from_a_bought_target(_app):
    """*"Not true. It can also be built from 'A chart I made in ChromIQ', if
    the user has such a target, made earlier or made by someone else with a
    proper spectrophotometer."*"""
    dlg = _dialog()
    try:
        body = _printer_help(dlg)
        assert "from a bought target (an IT8 or LaserSoft sheet), and set" \
            not in body
        assert "A chart you made in ChromIQ does" in body
        assert "spectrophotometer" in body
        assert "somebody who has the instrument" in body
    finally:
        dlg.deleteLater()


def test_the_help_says_outright_that_the_xyz_table_does_not_set_ua(_app):
    """*"It does not. He says the text is unclear and is being
    misunderstood."* So the text says the opposite in as many words, and then
    says what WAS true: it is scanin's own absolute read, not the profile
    type, that makes the flag look small inside ChromIQ."""
    dlg = _dialog()
    try:
        body = _printer_help(dlg)
        assert "does not set it: the profile type and " in body
        assert "asks the scanner profile for absolute colour itself" in body
    finally:
        dlg.deleteLater()


def test_the_help_does_not_end_by_pointing_at_the_lab_table(_app):
    """*"…reads as advice to choose 'cLUT Lab table', which an earlier
    paragraph recommends against, and 'Set it' has no clear referent."*"""
    dlg = _dialog()
    try:
        body = _printer_help(dlg)
        assert "It costs nothing. Set it." not in body
        assert "the right answer there is to take the XYZ table in the first " \
            "place" in body
        # the instruction now names what to set
        assert 'set White Point Handling to “Force Absolute Colorimetric ' \
            '(-ua)”' in body
    finally:
        dlg.deleteLater()


def test_the_help_points_at_the_scenario_that_sets_all_three(_app):
    """B8-69 made the requirement visible; B8-71 makes it unnecessary to
    remember. The help has to say the second one exists."""
    dlg = _dialog()
    try:
        body = _printer_help(dlg)
        assert "stand in for a measuring instrument" in body
    finally:
        dlg.deleteLater()


# ==========================================================================
# 7. The gate under the printer scenario (B8-70, absorbed)
# ==========================================================================
def test_the_printer_scenario_is_greyed_for_a_bought_target_with_its_reason(_app):
    """*"B8-70's gate becomes a greyed option with its reason beside it rather
    than a control that vanishes."* The gate itself is unchanged."""
    dlg = _dialog()
    try:
        assert dlg._scenario_radios[sc.SCENARIO_PRINTER].isEnabled()
        dlg._mode_standard.setChecked(True)
        assert not dlg._scenario_radios[sc.SCENARIO_PRINTER].isEnabled()
        assert dlg._mode_note.isVisibleTo(dlg)
        assert dlg._printer_mode() is False
        dlg._mode_chromiq.setChecked(True)
        assert dlg._scenario_radios[sc.SCENARIO_PRINTER].isEnabled()
        assert not dlg._mode_note.isVisibleTo(dlg)
    finally:
        dlg.deleteLater()


def test_the_printer_scenario_and_the_tick_are_one_control(_app):
    """Two controls that mean the same thing must never disagree."""
    dlg = _dialog()
    try:
        dlg._scenario_radios[sc.SCENARIO_PRINTER].setChecked(True)
        assert dlg._printer_cb.isChecked() and dlg._printer_mode()
        dlg._printer_cb.setChecked(False)
        assert not dlg._scenario_radios[sc.SCENARIO_PRINTER].isChecked()
        dlg._printer_cb.setChecked(True)
        assert dlg._scenario_radios[sc.SCENARIO_PRINTER].isChecked()
    finally:
        dlg.deleteLater()


# ==========================================================================
# 8. It is announced. A setting that changes the next profile is never silent
# ==========================================================================
def test_the_window_says_what_it_set_up_and_why(_app):
    dlg = _dialog()
    try:
        dlg._log.clear()
        _load_chart(dlg, 288)
        said = dlg._log.toPlainText()
        assert "288 patches" in said
        assert "XYZ table" in said and "High" in said
        assert "perfect white surface" in said
        assert "leave all three alone" in said
    finally:
        dlg.deleteLater()


def test_it_says_nothing_when_it_changed_nothing(_app):
    """A bucket it may not touch produces no line at all."""
    dlg = _dialog(_saved())
    try:
        dlg._log.clear()
        _load_chart(dlg, 288)
        assert "patches, so ChromIQ has set" not in dlg._log.toPlainText()
    finally:
        dlg.deleteLater()


# ==========================================================================
# 9. Two faults the on-screen adversarial pass found, 2026-09-06
# ==========================================================================
def test_switching_source_never_writes_the_new_modes_count_into_the_old_bucket(
        _app):
    """FOUND ON SCREEN. `_on_mode_changed` calls `_on_target_changed` (which
    ends in `_refresh`, which is where the patch-count rule runs) BEFORE it
    calls `_sync_colprof_context`. For that one call the source radio already
    says "a standard target" while `_active_ctx` is still the chart bucket, so
    the bought target's 288 patches landed in the CHART bucket.

    The symptom the driver printed: a chart bucket left on the XYZ table at
    High with "Force Absolute Colorimetric" came back, after one round trip
    through the standard-target side, holding "Scale white to a perfect white
    surface" instead. Nobody chose that.
    """
    dlg = _dialog()
    try:
        # The chart bucket, on the everyday scenario, with no chart loaded: the
        # window has no patch count of its own, so nothing here may be set from
        # the bought target's.
        # Away and back: everyday is already lit on a fresh window, so
        # setChecked on it emits nothing and applies nothing. Without the
        # detour this test asserted the FACTORY settings and passed only
        # because they happened to equal the everyday answer (CL-2 separated
        # the two).
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        dlg._scenario_radios[sc.SCENARIO_EVERYDAY].setChecked(True)
        chart_had = _three(dlg)
        assert chart_had == sc.SETUP_EVERYDAY_UNKNOWN
        dlg._mode_standard.setChecked(True)         # a 288-patch bought target
        assert dlg._known_patch_count() >= sc.SETUP_CROSSOVER
        assert _three(dlg) == sc.SETUP_LARGE        # …which the STANDARD bucket takes
        dlg._mode_chromiq.setChecked(True)
        assert _three(dlg) == chart_had, (
            "the bought target's patch count was written into the chart bucket")
    finally:
        dlg.deleteLater()


def test_choosing_everyday_with_nothing_loaded_still_means_everyday(_app):
    """FOUND ON SCREEN. Choose the measuring scenario, then choose everyday
    again with no chart loaded: the patch-count rule has nothing to say, so
    without a fallback the settings simply stayed on `-ua` and the XYZ table
    at High while the radio said "everyday scanning".

    The divergence line cannot catch this one: with no patch count there is no
    recipe to compare against, so it correctly says nothing. The window has to
    not get into the state in the first place.
    """
    dlg = _dialog()
    try:
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        assert _three(dlg)["wp_mode"] == "ua"
        dlg._scenario_radios[sc.SCENARIO_EVERYDAY].setChecked(True)
        assert _three(dlg) == sc.SETUP_EVERYDAY_UNKNOWN, (
            "the everyday radio is lit over another scenario's settings")
        # …and it is still only a starting point: a chart refines all three.
        _load_chart(dlg, 288)
        assert _three(dlg) == sc.SETUP_LARGE
    finally:
        dlg.deleteLater()


def test_the_unknown_count_fallback_is_only_for_the_explicit_click(_app):
    """The automatic path must never set anything from a number nobody
    supplied, which is what `setup_for_patch_count(None) is None` says."""
    assert sc.setup_for_patch_count(None) is None
    assert sc.scenario_setup(sc.SCENARIO_EVERYDAY, None) is None
    dlg = _dialog()
    try:
        before = _three(dlg)
        dlg._maybe_auto_setup()                 # no chart, no click
        assert _three(dlg) == before
    finally:
        dlg.deleteLater()


# ==========================================================================
# 10. The gap a hidden hint left behind it (found on screen, 2026-09-06)
# ==========================================================================
def test_a_hint_that_is_hidden_claims_no_height(_app):
    """`_WrapHint` reclaims its height in `resizeEvent`, and a hint created
    HIDDEN gets one resize to Qt's default 100 px before anything lays it out.
    `heightForWidth(100)` for a paragraph is several hundred pixels, and that
    was latched; layouts skip a hidden widget, so nothing corrected it, and the
    moment the hint was shown it claimed about 700 px with its text floating in
    the middle.

    Seen in a photograph of the real left column: two gaps of roughly 300 px,
    above and below the standard-target explanation, pushing everything after
    it off the visible pane. Geometry alone did not show it, because by the
    time a probe asked, some runs had settled and some had not.
    """
    from ui.dialogs.scanin_dialog import _WrapHint
    lbl = _WrapHint("A paragraph long enough to need several lines when it is "
                    "wrapped into the width of this window's left column, "
                    "which is where every one of these hints lives.", None)
    lbl.setWordWrap(True)
    try:
        lbl.resize(100, 30)                     # the default nobody laid out
        assert lbl.minimumHeight() == 0, (
            "a hidden hint latched a height from a width nobody laid out")
    finally:
        lbl.deleteLater()


def test_the_standard_target_explanation_sits_against_the_rows_around_it(_app):
    """The consequence, measured on the real column: no gap between the greyed
    printer scenario and its reason, and none between that reason and the
    question below it."""
    dlg = _dialog()
    try:
        dlg.show()
        dlg._mode_standard.setChecked(True)
        for _ in range(12):
            _app.processEvents()
        dlg.layout().activate()
        for _ in range(12):
            _app.processEvents()
        note = dlg._mode_note
        assert note.isVisibleTo(dlg)
        want = note.heightForWidth(note.width())
        assert 0 < note.height() <= want + 8, (
            f"the explanation is {note.height()} px tall where its own text "
            f"needs {want}; the space above and below it is the gap")
    finally:
        dlg.close()
        dlg.deleteLater()


# ==========================================================================
# 11. The review's findings (AGENT CL, 2026-09-06)
# ==========================================================================
def test_saving_settings_means_the_same_thing_before_and_after_a_restart(_app):
    """CL-1, the root of it. `_ctx_stored` is read once, at construction, from
    the settings store, which is right for the question it answers and wrong
    the moment the store changes underneath it. "Save as Defaults" wrote to the
    store and left the set alone, so the patch-count rule went on managing the
    bucket until the window was closed and reopened, and then stopped for ever.
    """
    settings = _FakeSettings()
    dlg = _dialog(settings)
    try:
        _load_chart(dlg, 288)
        assert _three(dlg) == sc.SETUP_LARGE
        assert "chart" not in dlg._ctx_stored
        dlg._save_defaults_clicked()
        assert "chart" in dlg._ctx_stored, (
            "saving meant nothing until the window was reopened")
        _load_chart(dlg, 24)
        assert _three(dlg) == sc.SETUP_LARGE, (
            "the rule went on managing a bucket the user had just saved")
    finally:
        dlg.deleteLater()
    # …and the next session agrees, which it always did.
    dlg = _dialog(settings)
    try:
        assert "chart" in dlg._ctx_stored
    finally:
        dlg.deleteLater()


def test_a_saved_bucket_is_never_told_its_settings_are_a_divergence(_app):
    """CL-1, the part a user reads. Save what ChromIQ itself chose from a
    288-patch target, then open a 24-patch one: the settings now differ from
    the rule's answer, but the user made none of those choices, and the lit
    radio's own gloss promises ChromIQ sets those three from the target size.
    Blaming them for ChromIQ's own choice is the fault. The window says what is
    true instead, and names what the rule would have done."""
    dlg = _dialog()
    try:
        _load_chart(dlg, 288)
        dlg._save_defaults_clicked()
        _load_chart(dlg, 24)
        said = dlg._scenario_note.text()
        assert dlg._scenario_note.isVisibleTo(dlg)
        assert "no longer match" not in said, said
        assert "You saved settings" in said
        assert "24 patches" in said
        # …and it names the answer the user can act on
        assert "Shaper + matrix" in said and "Medium" in said
        assert "Map chart white to white" in said
    finally:
        dlg.deleteLater()


def test_a_saved_bucket_with_no_chart_yet_still_says_why_nothing_happens(_app):
    dlg = _dialog(_saved(scenario=sc.SCENARIO_EVERYDAY))
    try:
        said = dlg._scenario_note.text()
        assert "You saved settings" in said
        assert "patches" not in said, "it named a count nobody supplied"
    finally:
        dlg.deleteLater()


def test_a_hand_edit_is_still_named_as_a_divergence(_app):
    """The other half, and it must NOT be swallowed by the fix above: a user
    who changed one of the three deliberately is told which one."""
    dlg = _dialog()
    try:
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        dlg._ptype.setCurrentIndex(dlg._ptype.findData("s"))
        said = dlg._scenario_note.text()
        assert "no longer match" in said
        assert "Profile type" in said
    finally:
        dlg.deleteLater()


def test_the_divergence_line_carries_a_warning_mark(_app):
    """CL-4. It is the one line in this group whose whole job is to be
    noticed, and without a mark it read as a fourth gloss of the scenario
    above it. The mark is added outside the translated string, so no catalogue
    can lose it, and the informational lines do NOT carry one."""
    dlg = _dialog()
    try:
        dlg._scenario_radios[sc.SCENARIO_INSTRUMENT].setChecked(True)
        dlg._ptype.setCurrentIndex(dlg._ptype.findData("s"))
        assert dlg._scenario_note.text().startswith("⚠ ")
        assert dlg._scenario_note.contentsMargins().top() > 0, (
            "the warning is hard against the gloss above it")
        # the saved-bucket line is information, not a warning
        dlg2 = _dialog()
        try:
            _load_chart(dlg2, 288)
            dlg2._save_defaults_clicked()
            _load_chart(dlg2, 24)
            assert not dlg2._scenario_note.text().startswith("⚠")
        finally:
            dlg2.deleteLater()
    finally:
        dlg.deleteLater()


def test_the_unknown_count_answer_is_the_rules_own_small_row(_app):
    """CL-2. The first version paired a MATRIX profile type with the white
    point this module labels "(best for cLUT profiles)", and gave the same
    scenario two answers at the same profile type: the rule says shaper+matrix
    wants "Map chart white to white" and this said it wants "Scale white to a
    perfect white surface". One scenario cannot mean two things."""
    assert sc.SETUP_EVERYDAY_UNKNOWN == sc.SETUP_SMALL
    assert sc.SETUP_EVERYDAY_UNKNOWN["ptype"] in sc.MATRIX_ALGOS
    assert sc.WP_MODE_RECOMMENDED[sc.SETUP_EVERYDAY_UNKNOWN["wp_mode"]] == \
        "matrix"


def test_the_shipped_default_white_point_did_not_move_with_it(_app):
    """…and the thing CL-2 deliberately does NOT touch. A window nobody has
    configured still opens where B8-75 put it; that pairing is Basti's ruling
    and a separate question."""
    assert sc.WP_MODE_DEFAULT == "uR"
    dlg = _dialog()
    try:
        assert _three(dlg)["wp_mode"] == sc.WP_MODE_DEFAULT
    finally:
        dlg.deleteLater()


def test_the_lab_note_does_not_contradict_the_profile_type_help(_app):
    """CL-6, and it is pre-existing. This note still described the world
    before B8-75 moved the white-point default: it told a user whose window is
    on "Scale white to a perfect white surface" that their bright paper is
    being flattened, and sent them to "Auto-scale to avoid clipping" to lift a
    ceiling the profile-type help says is ALREADY at about 114 % reflectance,
    above anything that can physically be put on the glass. One ⓘ, two
    answers."""
    note = sc.ptype_advice(False, "l", 288)
    assert note
    assert "lifts the ceiling" not in note
    assert "Auto-scale to avoid clipping" not in note
    assert "114 %" in note and "94 %" in note
    _, help_body = sc.ptype_help(False)
    for claim in ("114 %", "94 %"):
        assert claim in help_body, "the ⓘ and its live note disagree again"
