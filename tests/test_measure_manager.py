"""Parser tests for MeasureManager — confirms each chartread line pattern
produces the right signal with the right payload.

Fixture lines are copied verbatim from Argyll 3.5.0 chartread.c (the printf
format strings concretised with example values). See the plan file for the
exact source line references.
"""
from __future__ import annotations

import sys
from typing import Any, List, Tuple

import pytest

# pytest-qt isn't a dependency; we drive signals through a manual collector.
from PyQt6.QtCore import QCoreApplication

from workflow.measure_manager import MeasureManager, MeasureParams


# QApplication is required for QObject signals to work at all.
@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


class _StubRunner:
    """Minimal ArgyllRunner stand-in. Records every write_stdin call so we can
    verify the auto-answer behaviour for the Save-Partial state machine."""

    def __init__(self) -> None:
        self.writes: List[str] = []

    def write_stdin(self, text: str) -> None:
        self.writes.append(text)

    # Nothing else in MeasureManager._handle_line uses the runner.
    def run(self, *a, **k) -> None:
        pass

    def abort(self) -> None:
        pass


def _make_manager() -> Tuple[MeasureManager, _StubRunner, dict]:
    """Build a manager and attach a `signals` dict that collects every emit."""
    runner = _StubRunner()
    mgr = MeasureManager(runner)
    # Guided-strip navigation is normally configured by Tab Measure before
    # start(); for parser-only tests we disable it explicitly so seeing a
    # strip line doesn't make _guided_step index into an empty list.
    mgr._guided_state = "disabled"
    sigs: dict = {}

    def _collect(name: str):
        sigs.setdefault(name, [])
        return lambda *args: sigs[name].append(args)

    for name in (
        "stripe_changed", "all_stripes_done", "calibration_prompt",
        "calibration_done", "strip_error", "instrument_disconnected",
        "device_busy", "no_instrument", "wrong_strip", "unexpected_response",
        "sensor_wrong_position", "usb_claimed_by_vm",
        "strip_interrupted", "unread_confirm", "generic_instrument_error",
        "coms_init_failed", "inst_init_failed", "instrument_wrong_type",
        "ccmx_load_failed", "mode_set_failed",
        "info_message",
        "xy_place_sheet", "spot_ready", "abort_confirm",
    ):
        getattr(mgr, name).connect(_collect(name))
    return mgr, runner, sigs


def _feed(mgr: MeasureManager, line: str) -> None:
    """Push a line through the same path chartread output takes."""
    mgr._handle_line(line, lambda _l: None)


# ---------------------------------------------------------------------------
# Command construction — bidirectional flags
# ---------------------------------------------------------------------------

def _args(**kw) -> list[str]:
    from pathlib import Path
    mgr, _runner, _sigs = _make_manager()
    return mgr._build_args(MeasureParams(ti1_path=Path("/tmp/chart.ti1"), **kw))


def test_build_args_disable_bidir_emits_capital_B():
    assert "-B" in _args(disable_bidir=True)
    assert "-b" not in _args(disable_bidir=True)


def test_build_args_force_bidir_emits_lowercase_b():
    assert "-b" in _args(force_bidir=True)
    assert "-B" not in _args(force_bidir=True)


def test_build_args_bidir_flags_mutually_exclusive():
    # -B and -b can never both be passed; -B (disable) wins if both are set.
    args = _args(disable_bidir=True, force_bidir=True)
    assert "-B" in args and "-b" not in args


def test_build_args_no_bidir_flag_by_default():
    args = _args()
    assert "-B" not in args and "-b" not in args


# ---------------------------------------------------------------------------
# A. Mid-measurement recovery prompts
# ---------------------------------------------------------------------------

def test_strip_interrupted_fires_signal():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Strip read stopped at user request!")
    assert sigs.get("strip_interrupted") == [()]


def test_unread_confirm_fires_with_patch_info_when_state_idle():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Done ? - At least one unread patch (45, B12), Are you sure [y/n]: ")
    assert sigs.get("unread_confirm") == [("45, B12",)]


def test_unread_confirm_is_always_the_users_to_answer():
    """Save-Partial no longer drives chartread through the strip menu, so it
    never meets this prompt and never answers it automatically. The old chain
    did — and it is the chain that hung the session when it was started from a
    misread (Knut, #130 2026-07-30)."""
    mgr, runner, sigs = _make_manager()
    mgr._save_partial_state = "wait_give_up_prompt"
    _feed(mgr, "Done ? - At least one unread patch (45, B12), Are you sure [y/n]: ")
    assert sigs.get("unread_confirm") == [("45, B12",)]
    assert runner.writes == [], "nothing may be answered on the user's behalf"


def test_save_partial_sends_two_q_commands():
    """The protocol Knut established by hand: 'q' stops the armed strip, and the
    second 'q' at the give-up prompt is what makes chartread write the .ti3 and
    exit.

    ENGINE ONLY. Its helper calls cq_write_ti3_atomic() before giving up; stock
    chartread has no such call and 'q' there exits without writing anything
    (chartread.c:1654), which is what lost Knut a strip on 2026-08-01. The stock
    chain is covered in tests/test_knut_beta118_save_partial_stock.py.
    """
    mgr, runner, sigs = _make_manager()
    mgr._engine_active = True
    assert not mgr.save_partial_in_progress

    mgr.send_save_partial_and_quit()
    assert mgr.save_partial_in_progress          # first 'q' out, awaiting prompt
    assert runner.writes == ['{"cmd": "quit"}\n']

    _feed(mgr, "Strip read stopped at user request!")
    assert not mgr.save_partial_in_progress      # second 'q' sent, chain complete
    assert runner.writes == ['{"cmd": "quit"}\n', '{"cmd": "quit"}\n']


def test_the_strip_menu_no_longer_drives_save_partial():
    """A strip menu arriving mid-save must not send anything: that route is gone.
    """
    mgr, runner, sigs = _make_manager()
    mgr.send_save_partial_and_quit()
    runner.writes.clear()
    _feed(mgr, "Ready to read strip pass A")
    assert runner.writes == []


def test_generic_ierror_fires_with_friendly_and_technical():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Got 'Communication error' (USB read timeout) error.")
    assert sigs.get("generic_instrument_error") == [("Communication error", "USB read timeout")]


def test_strip_error_misread_carries_parenthesised_reason():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Strip read failed due to misread (Insufficient delta E)")
    assert sigs.get("strip_error") == [("Insufficient delta E",)]


def test_strip_error_communication_problem_fires_without_parens():
    # chartread.c L1671 prints no "(reason)" for a comms failure, so this used
    # to slip past _STRIP_ERROR_RE and no dialog appeared.
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Strip read failed due to communication problem.")
    assert sigs.get("strip_error") == [("communication problem",)]


# ---------------------------------------------------------------------------
# B. Startup / config failure messages
# ---------------------------------------------------------------------------

def test_coms_init_failed_fires():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Establishing communications with instrument failed with message 'COM port not found' (open failed)")
    assert sigs.get("coms_init_failed") == [("COM port not found",)]


def test_inst_init_failed_fires():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Initialising instrument failed with message 'No response from device' (timeout)")
    assert sigs.get("inst_init_failed") == [("No response from device",)]


@pytest.mark.parametrize("line,expected", [
    ("Need reflection spot, strip, xy or chart reading capability,", "reflection"),
    ("Need transmission reading capability,", "transmission"),
    ("Need emissive spot or strip reading capability", "emissive"),
    ("Need emissive reading capability", "emissive"),
])
def test_capability_mismatch_classified(line: str, expected: str):
    mgr, _, sigs = _make_manager()
    _feed(mgr, line)
    assert sigs.get("instrument_wrong_type") == [(expected,)]


@pytest.mark.parametrize("line", [
    "Setting Colorimeter Correction Matrix failed with error :'Bad data' (corrupt)",
    "Reading CCMX/CCSS File '/tmp/x.ccmx' failed with error 5:'no such file'",
    "Instrument doesn't have Colorimeter Correction Matrix capability",
    "Instrument doesn't have Colorimeter Calibration Spectral Sample capability",
])
def test_ccmx_failure_variants(line: str):
    mgr, _, sigs = _make_manager()
    _feed(mgr, line)
    assert "ccmx_load_failed" in sigs and len(sigs["ccmx_load_failed"]) == 1


def test_mode_set_failed_fires():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Setting instrument mode failed with error :'mode not supported' (refused)")
    assert sigs.get("mode_set_failed") == [("mode not supported",)]


# ---------------------------------------------------------------------------
# B-status. Informational messages
# ---------------------------------------------------------------------------

def test_info_battery_status_disabled():
    # Battery percentage flashes were felt to be noisy (fires on every i1Pro/
    # Spectro2 start-up). The pattern is intentionally inert; this test pins
    # that decision.
    mgr, _, sigs = _make_manager()
    _feed(mgr, "The battery charged level is 47.0%")
    assert not sigs.get("info_message")


def test_info_chart_instrument_mismatch():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Warning: chart is for i1pro2, using instrument i1pro3")
    assert sigs.get("info_message") == [
        ("chart_instrument_mismatch",
         "Note: chart was generated for i1pro2; reading with i1pro3 anyway."),
    ]


@pytest.mark.parametrize("line,category", [
    ("Warning: Instrument isn't capable of spectral measurement", "no_spectral"),
    ("high resolution ignored - instrument doesn't support high res. mode", "highres_ignored"),
    ("UV measurement mode requested, but instrument doesn't support this mode", "uv_ignored"),
    ("Modified patch consistency tolerance ignored - instrument doesn't support it", "scan_tol_ignored"),
])
def test_other_info_messages_categorised(line: str, category: str):
    mgr, _, sigs = _make_manager()
    _feed(mgr, line)
    assert sigs.get("info_message") is not None
    assert sigs["info_message"][0][0] == category


# ---------------------------------------------------------------------------
# D. Spot / XY mode defensive coverage
# ---------------------------------------------------------------------------

def test_xy_place_sheet_carries_sheet_numbers():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Please place sheet 2 of 5 on table, then")
    assert sigs.get("xy_place_sheet") == [(2, 5)]


def test_xy_sheet_ok_emits_info_message():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Sheet 2 of 5 read OK")
    assert sigs.get("info_message") == [("xy_sheet_ok", "Sheet 2 of 5 read successfully.")]


def test_spot_ready_carries_patch_id():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Ready to read patch 'A07'")
    assert sigs.get("spot_ready") == [("A07",)]


def test_abort_confirm_fires_signal():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Abort ? - Are you sure ? [y/n]:")
    assert sigs.get("abort_confirm") == [()]


def test_patch_not_found_emits_info_message():
    mgr, _, sigs = _make_manager()
    _feed(mgr, "Patch 'ZZ99' not found")
    assert sigs.get("info_message") == [("patch_not_found", "Patch 'ZZ99' not found.")]


# ---------------------------------------------------------------------------
# E. ALL ROWS READ — verify the existing detection survives the 3.5.0
# inline-suffix form on the "Ready to read strip pass" prompt.
# ---------------------------------------------------------------------------

def test_all_rows_read_inline_suffix_in_normal_mode():
    """In normal (non-resume) mode, the inline suffix should still fire
    all_stripes_done so the user can be offered the Build Profile dialog."""
    mgr, _, sigs = _make_manager()
    mgr._is_resume = False
    _feed(mgr, "Ready to read strip pass A (!! ALL ROWS READ !!)")
    assert sigs.get("stripe_changed") == [("A",)]
    assert sigs.get("all_stripes_done") == [()]


def test_all_rows_read_inline_suffix_suppressed_in_resume_mode():
    """In resume mode the same line just means we're revisiting a fully-read
    chart — must NOT prematurely show 'Build Profile'."""
    mgr, _, sigs = _make_manager()
    mgr._is_resume = True
    _feed(mgr, "Ready to read strip pass A (!! ALL ROWS READ !!)")
    assert sigs.get("stripe_changed") == [("A",)]
    assert not sigs.get("all_stripes_done")


def test_all_rows_read_standalone_line_still_fires_on_a_normal_run():
    """Older Argyll printed ALL ROWS READ on its own line. The detection must
    keep firing for that historical form too."""
    mgr, _, sigs = _make_manager()
    mgr._is_resume = False
    _feed(mgr, "    (!! ALL ROWS READ !!)")
    assert sigs.get("all_stripes_done") == [()]


def test_the_standalone_line_waits_for_a_real_read_on_a_resume():
    """Updated with Knut's report of 2026-07-27: the inline form was already
    suppressed during a resume, but the standalone form was not — and that is
    the one that put the completion window in front of him the instant he
    started a refine, before he had re-read anything."""
    mgr, _, sigs = _make_manager()
    mgr._is_resume = True

    _feed(mgr, "    (!! ALL ROWS READ !!)")
    assert not sigs.get("all_stripes_done")

    _feed(mgr, "Strip read OK")
    _feed(mgr, "    (!! ALL ROWS READ !!)")
    assert sigs.get("all_stripes_done") == [()]


# ---------------------------------------------------------------------------
# Guided refinement navigation — regression coverage to ensure the new
# message-coverage patterns don't disturb the auto-navigation state machine.
# ---------------------------------------------------------------------------

def _make_guided_manager():
    """Like _make_manager but leaves guided navigation enabled."""
    mgr, runner, sigs = _make_manager()
    mgr._guided_state = "idle"  # re-enable (default test helper disables it)
    return mgr, runner, sigs


def test_guided_single_target_navigates_and_finishes():
    mgr, runner, sigs = _make_guided_manager()
    mgr.set_guided_strips(["C"])  # target strip C
    _feed(mgr, "Ready to read strip pass A")   # idle -> navigating, press 'f'
    _feed(mgr, "Ready to read strip pass B")   # still navigating, press 'f'
    _feed(mgr, "Ready to read strip pass C")   # arrived -> waiting
    _feed(mgr, " Strip read OK")               # advance -> done
    assert runner.writes == ["f", "f"]
    assert mgr._guided_state == "idle_done"
    assert sigs.get("all_stripes_done") == [()]


def test_guided_multi_target_with_backward_move():
    mgr, runner, sigs = _make_guided_manager()
    mgr.set_guided_strips(["B", "D"])
    _feed(mgr, "Ready to read strip pass E")   # nav back to B -> 'b'
    _feed(mgr, "Ready to read strip pass B")   # arrived B -> waiting
    _feed(mgr, " Strip read OK")               # advance idx -> D
    _feed(mgr, "Ready to read strip pass B")   # nav to D -> 'f'
    _feed(mgr, "Ready to read strip pass C")   # nav -> 'f'
    _feed(mgr, "Ready to read strip pass D")   # arrived D -> waiting
    _feed(mgr, " Strip read OK")               # advance -> done
    assert runner.writes == ["b", "f", "f"]
    assert mgr._guided_state == "idle_done"
    assert sigs.get("all_stripes_done") == [()]


def test_guided_run_emits_no_spurious_dialog_signals():
    """A clean guided run must not trip any of the new error/recovery patterns."""
    mgr, runner, sigs = _make_guided_manager()
    mgr.set_guided_strips(["B"])
    for line in (
        "Ready to read strip pass A",
        "Ready to read strip pass B",
        " Strip read OK",
    ):
        _feed(mgr, line)
    for noisy in (
        "strip_interrupted", "unread_confirm", "generic_instrument_error",
        "coms_init_failed", "inst_init_failed", "instrument_wrong_type",
        "ccmx_load_failed", "mode_set_failed", "info_message",
        "xy_place_sheet", "spot_ready", "abort_confirm", "strip_error",
    ):
        assert not sigs.get(noisy), f"{noisy} fired during a clean guided run"


# ---------------------------------------------------------------------------
# Engine XY/chart mode events (#126 follow-up)
# ---------------------------------------------------------------------------

def _feed_engine(mgr, line: str) -> None:
    mgr._handle_engine_line(line, lambda _l: None)


def test_mode_fallback_event_sets_flag():
    mgr, _r, _s = _make_manager()
    _feed_engine(mgr, '{"event":"mode_fallback","mode":"xy"}')
    assert mgr._engine_mode_fallback is True


def test_chart_read_event_emits_chart_measured():
    mgr, _r, _s = _make_manager()
    got = []
    mgr.chart_measured.connect(lambda ev: got.append(ev))
    _feed_engine(mgr, '{"event":"chart_read","patches":[{"loc":"A1",'
                      '"xyz":[50,50,50],"exyz":[50,50,50],"de":0.0}]}')
    assert len(got) == 1 and len(got[0]["patches"]) == 1


def test_xy_place_sheet_event_emits_signal():
    mgr, _r, sigs = _make_manager()
    _feed_engine(mgr, '{"event":"xy_place_sheet","sheet":2,"total":3}')
    assert sigs["xy_place_sheet"] == [(2, 3)]
