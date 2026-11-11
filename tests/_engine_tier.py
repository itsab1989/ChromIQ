"""THE HEAVY ENGINE TIER: which tests only run with ``--runengine``.

Basti, 2026-11-11: *"the engine is beta and off by default so i dont want it
to put on 25minutes on each gate from now on"*. The research profile engine
brought about 800 tests, many of them real engine profile builds of a minute
or more each, and the release gate went from about 10 minutes to 27.

This module is the ONE place that says which of them are heavy. It is plain
data so it can be read in one sitting and audited:

* ``HEAVY_FILES``: whole test files, by name. Every test in them carries the
  ``engine_heavy`` marker.
* ``HEAVY_TESTS``: single tests (node ids, without a parametrize id: every
  parametrisation of the function goes) in files that also hold fast tests
  which must stay in the normal gate.

Both were chosen by MEASURED cost (``tests/data/gate_durations.json``, a
committed snapshot of a full gate run with ``--durations=0``), not by name.
``tests/test_the_normal_gate_cannot_silently_grow.py`` keeps the list honest:
no stale entry, and no test above the bound left in the normal gate unless it
is on ``ALLOWED_SLOW`` with a reason.

``scripts/gate_tier.py`` reads ``FULL_GATE_PATHS`` and these lists to say which
gate a change needs.
"""
from __future__ import annotations

#: Whole files in the heavy engine tier.
HEAVY_FILES: tuple[str, ...] = (
    "test_engine_v2_options.py",
    "test_engine_colorimetric_resolve_on_every_rgb_build_is_the_default.py",
    "test_engine_hue_kept_rendering_is_optional_and_rgb_only.py",
    "test_engine_pins_the_paper_white.py",
    "test_engine_second_batch_from_the_accuracy_challenge.py",
    "test_engine_v2_candidates.py",
    "test_research_a28_default_tokens_reach_every_consumer.py",
    "test_research_a33_integration4_defaults.py",
    "test_research_a29_blackhandover.py",
    "test_engine_a19_extrapolation_bounds.py",
    "test_research_a40_inklimit.py",
    "test_v4_twin_perceptual_reference_medium.py",
    "test_engine_parallel_profile_identity.py",
    "test_engine_black_ink_limit_and_2015_observers.py",
    "test_engine_profiles_match_macos_reference_nodes.py",
    "test_engine_accurate_black_ink_limit_keeps_the_black_deep.py",
    "test_f13_rgb_shadows_stay_monotone.py",
    "test_engine_accurate_mode_keeps_hue_black_and_honest_smoothing.py",
    "test_f00_default_token_state_passes_the_neutral_column_check.py",
    "test_engine_accurate_black_reaches_its_ink_limit_depth.py",
    "test_engine_accurate_neutral_highlight_and_black.py",
    "test_engine_names_patches_the_way_the_sheet_does.py",
    "test_f08_gammap_helper_survives_an_optimising_compiler.py",
)

#: Single tests in the heavy engine tier, as ``tests/<file>.py::<function>``
#: (a class method as ``tests/<file>.py::<Class>::<method>``).
HEAVY_TESTS: tuple[str, ...] = (
    "tests/test_engine_accurate_mode.py::test_accurate_rgb_build_end_to_end",
    "tests/test_engine_accurate_mode.py::test_accurate_build_emits_granular_progress",
    "tests/test_engine_accurate_mode.py::test_accurate_xyz_build_carries_shaped_tables",
    "tests/test_engine_accurate_mode.py::test_accurate_cmyk_build_and_separation_smoothness",
    "tests/test_engine_builder.py::test_thread_reference_is_held_until_the_thread_really_stops",
    "tests/test_engine_builder.py::test_engine_builder_builds_profile",
    "tests/test_engine_v2_harness.py::test_icc_profile_reader_matches_model",
    "tests/test_engine_v2_harness.py::test_build_reports_outlier_rows",
    "tests/test_engine_gp.py::test_gp_build_emits_confidence_map",
    "tests/test_engine_ucs.py::test_build_with_ucs_candidate",
    "tests/test_benchmarks_research_v31.py::test_ncq_runs_on_a_real_seven_ink_set_through_its_proxy",
    "tests/test_the_new_profile_engine_is_one_switch.py::test_a_real_build_without_colprof_stops_and_leaves_no_profile",
)

#: Tests that take longer than the bound in the snapshot and stay in the
#: normal gate anyway, each with the reason. Keyed like HEAVY_TESTS.
ALLOWED_SLOW: dict[str, str] = {
    "tests/test_beta12_b_review.py::test_the_shipped_certificates_are_what_this_chromiq_works_out":
        "the release check of data/preset_certificates.json (every built-in "
        "preset worked out again, no engine involved); the one test that "
        "catches a judging change after the version bump. 373 s alone, 670 s "
        "in a full gate: the floor of the normal gate, see CLAUDE.md Test",
    "tests/test_fd9_4325_presets.py::test_every_builtin_loaded_on_the_fd9_leaves_a_chart_the_fd9_can_read":
        "lays out every bundled patch set for the FD-9 (chart creation, no "
        "profile engine); already in the slow tier",
    "tests/test_reopening_the_open_project_keeps_the_runs_settings.py::test_a_change_after_the_reopen_is_the_only_thing_saved":
        "drives the real main window over a real demo project: the reopen "
        "bug of 4.3.23 that silently replaced a saved layout; colprof path",
    "tests/test_reopening_the_open_project_keeps_the_runs_settings.py::test_reopening_the_open_project_files_nothing_of_the_chart":
        "drives the real main window over a real demo project: the reopen "
        "bug of 4.3.23; colprof path",
    "tests/test_reopening_the_open_project_keeps_the_runs_settings.py::test_a_fresh_open_shows_the_chart_and_files_nothing_of_it":
        "drives the real main window over a real demo project: the reopen "
        "bug of 4.3.23; colprof path",
    "tests/test_k44_default_button_audit.py::test_every_audited_window_is_in_exactly_one_class":
        "its time is the module fixture that opens every audited window "
        "once; the other tests of the file share it",
    "tests/test_fd9_off_stale_project.py::test_an_fd9_project_opened_with_the_beta_off_is_left_as_it_was":
        "its time is the module fixture that generates the FD-9 project; "
        "protects every user who has the FD-9 beta off",
    "tests/test_the_demo_presets_pair_on_every_requirement.py::test_every_demo_preset_reaches_the_window":
        "its time is the module fixture that opens the presets window over "
        "every demo preset; the file's other tests share it",
}

#: Whole FILES whose normal-gate tests add up to more than FILE_BOUND_SECONDS
#: and stay anyway (under --dist loadfile a file is one worker's work).
ALLOWED_SLOW_FILES: dict[str, str] = {
    "tests/test_beta12_b_review.py":
        "holds the preset-certificate release check (see ALLOWED_SLOW)",
    "tests/test_reopening_the_open_project_keeps_the_runs_settings.py":
        "three real main-window drives over a demo project (see ALLOWED_SLOW)",
}

#: Anything a diff touches under these paths needs the FULL gate
#: (``--runslow --runengine``), because the heavy tier is where it is tested.
#: The heavy test files themselves are added by ``scripts/gate_tier.py``.
FULL_GATE_PATHS: tuple[str, ...] = (
    "workflow/profile_engine/",
    "workflow/engine_builder.py",
    "workflow/argyll_colorimetry.py",
    "native/gammap_helper/",
    "native/argyll/",
    "benchmarks/research/",
    "tests/_engine_tier.py",
)

#: The bound, in seconds of setup + call + teardown in the snapshot, above
#: which a test must be in the heavy tier or on ALLOWED_SLOW.
BOUND_SECONDS = 30.0

#: The same for a whole file's normal-gate tests added together.
FILE_BOUND_SECONDS = 240.0

SKIP_REASON = "heavy engine build tier - use --runengine"


def strip_param(nodeid: str) -> str:
    """``f.py::test_x[a-b]`` -> ``f.py::test_x``."""
    head, sep, _ = nodeid.partition("[")
    return head if sep else nodeid


def is_heavy(nodeid: str) -> bool:
    """True when this collected node id is in the heavy engine tier."""
    path = nodeid.split("::", 1)[0]
    if path.rsplit("/", 1)[-1] in HEAVY_FILES:
        return True
    return strip_param(nodeid) in HEAVY_TESTS
