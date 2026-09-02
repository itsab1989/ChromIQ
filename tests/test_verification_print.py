"""The verification print conversion engine (#130 feature A, phase A1).

Covers §3.2 of docs/design/verification_printing_and_target.md: the cctiff
invocation carries the chosen intent (T3 at engine level), converted pages land
where they are pointed (T2's engine half), and the three failure rows A10–A12
raise the right §M message id and print nothing.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core.resource_path import argyll_binary
from workflow.verification_print import (
    COLOUR_RAW,
    COLOUR_THROUGH,
    ROUTE_CHROMIQ,
    ROUTE_EXTERNAL,
    STATE_CONVERTED,
    STATE_CONVERTED_REF_MISSING,
    STATE_REGULAR,
    VerificationPrintError,
    chart_conversion_state,
    colorimetric_reference_for,
    convert_pages_through_profile,
    intent_letter,
    print_record_path,
    read_print_record,
    write_print_record,
)


@pytest.fixture
def argyll_bin(tmp_path: Path) -> Path:
    """A bin dir holding a fake cctiff, so the tool-missing check passes."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / argyll_binary("cctiff")).write_text("#!/bin/sh\n", encoding="utf-8")
    return bin_dir


@pytest.fixture
def profile(tmp_path: Path) -> Path:
    p = tmp_path / "run.icc"
    p.write_bytes(b"icc")
    return p


@pytest.fixture
def srgb(tmp_path: Path) -> Path:
    p = tmp_path / "sRGB.icm"
    p.write_bytes(b"icc")
    return p


def _pages(tmp_path: Path, n: int = 2) -> "list[Path]":
    out = []
    for i in range(1, n + 1):
        p = tmp_path / f"chart_{i:02d}.tif"
        p.write_bytes(b"II*\x00")
        out.append(p)
    return out


def _ok_runner(calls: "list[list[str]]"):
    """A stub runner that records the command and writes the output file."""
    def run(cmd, **kw):
        calls.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"II*\x00converted")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    return run


# ---------------------------------------------------------------- the mapping
def test_intent_letters_match_cctiffs_own():
    assert intent_letter("relative") == "r"
    assert intent_letter("absolute") == "a"
    assert intent_letter("perceptual") == "p"
    assert intent_letter("saturation") == "s"
    # Already-a-letter and unknown both land somewhere safe.
    assert intent_letter("a") == "a"
    assert intent_letter("") == "r"
    assert intent_letter("nonsense") == "r"


# ------------------------------------------------------------- the conversion
def test_converted_pages_land_in_the_cache_dir(tmp_path, argyll_bin, profile, srgb):
    pages = _pages(tmp_path)
    out_dir = tmp_path / "cache"
    calls: list = []
    result = convert_pages_through_profile(
        pages, profile, "relative", out_dir,
        bin_dir=argyll_bin, source_profile=srgb, runner=_ok_runner(calls))
    assert set(result) == set(pages)
    for src, dst in result.items():
        assert dst.parent == out_dir
        assert dst.name == src.name
        assert dst.exists()
    assert len(calls) == 2


def test_the_arguments_carry_the_chosen_intent_not_hardcoded_r(
        tmp_path, argyll_bin, profile, srgb):
    """§9 T3 at the engine level: the -i letters follow the caller's choice."""
    pages = _pages(tmp_path, 1)
    for intent, letter in (("relative", "r"), ("absolute", "a"),
                           ("perceptual", "p"), ("saturation", "s")):
        calls: list = []
        convert_pages_through_profile(
            pages, profile, intent, tmp_path / "out",
            bin_dir=argyll_bin, source_profile=srgb, runner=_ok_runner(calls))
        cmd = calls[0]
        assert cmd.count("-i") == 2
        letters = [cmd[i + 1] for i, a in enumerate(cmd) if a == "-i"]
        assert letters == [letter, letter], intent
        # Source profile before the run profile, image before output — the
        # cctiff grammar the conversion depends on.
        assert cmd.index(str(srgb)) < cmd.index(str(profile))
        assert cmd.index(str(profile)) < cmd.index(str(pages[0]))


def test_missing_cctiff_raises_the_no_cctiff_message(tmp_path, profile, srgb):
    """§3.2 A10 — refuse and name M-CM-NO-CCTIFF; nothing is written."""
    with pytest.raises(VerificationPrintError) as exc:
        convert_pages_through_profile(
            _pages(tmp_path), profile, "relative", tmp_path / "out",
            bin_dir=tmp_path / "empty-bin", source_profile=srgb,
            runner=_ok_runner([]))
    assert exc.value.message_id == "M-CM-NO-CCTIFF"
    assert not (tmp_path / "out").exists()


def test_a_failed_page_stops_names_the_page_and_converts_no_more(
        tmp_path, argyll_bin, profile, srgb):
    """§3.2 A11 — stop, name the page, print nothing."""
    pages = _pages(tmp_path, 3)
    calls: list = []

    def run(cmd, **kw):
        calls.append(list(cmd))
        if len(calls) == 2:                      # page 2 fails
            return subprocess.CompletedProcess(cmd, 1, stdout="",
                                               stderr="cctiff: some failure")
        Path(cmd[-1]).write_bytes(b"II*\x00")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with pytest.raises(VerificationPrintError) as exc:
        convert_pages_through_profile(
            pages, profile, "relative", tmp_path / "out",
            bin_dir=argyll_bin, source_profile=srgb, runner=run)
    assert exc.value.message_id == "M-CM-CONVERT-FAILED"
    assert exc.value.page == 2 and exc.value.total == 3
    assert "some failure" in exc.value.reason
    assert len(calls) == 2                       # page 3 was never attempted


def test_an_unusable_profile_reports_cctiffs_parsed_error(
        tmp_path, argyll_bin, profile, srgb):
    """§3.2 A12 — cctiff's own error text becomes the reason."""
    def run(cmd, **kw):
        return subprocess.CompletedProcess(
            cmd, 1, stdout="", stderr="Error: ICC V4 not supported")

    with pytest.raises(VerificationPrintError) as exc:
        convert_pages_through_profile(
            _pages(tmp_path, 1), profile, "relative", tmp_path / "out",
            bin_dir=argyll_bin, source_profile=srgb, runner=run)
    assert exc.value.message_id == "M-CM-CONVERT-FAILED"
    assert "version-4" in exc.value.reason


def test_a_hung_cctiff_times_out_instead_of_waiting_forever(
        tmp_path, argyll_bin, profile, srgb):
    def run(cmd, **kw):
        assert kw.get("timeout"), "a subprocess without a timeout can hang the app"
        raise subprocess.TimeoutExpired(cmd, kw["timeout"])

    with pytest.raises(VerificationPrintError) as exc:
        convert_pages_through_profile(
            _pages(tmp_path, 1), profile, "relative", tmp_path / "out",
            bin_dir=argyll_bin, source_profile=srgb, runner=run)
    assert exc.value.message_id == "M-CM-CONVERT-FAILED"


def test_a_missing_profile_fails_before_any_process_runs(
        tmp_path, argyll_bin, srgb):
    def run(cmd, **kw):                          # pragma: no cover
        raise AssertionError("no process should run for a missing profile")

    with pytest.raises(VerificationPrintError) as exc:
        convert_pages_through_profile(
            _pages(tmp_path, 1), tmp_path / "gone.icc", "relative",
            tmp_path / "out", bin_dir=argyll_bin, source_profile=srgb,
            runner=run)
    assert exc.value.message_id == "M-CM-CONVERT-FAILED"


def test_no_pages_is_a_no_op(tmp_path, argyll_bin, profile, srgb):
    assert convert_pages_through_profile(
        [], profile, "relative", tmp_path / "out",
        bin_dir=argyll_bin, source_profile=srgb, runner=_ok_runner([])) == {}


# ------------------------------------------------- §3.1a chart-kind detection
def test_a_regular_chart_reads_as_regular(tmp_path):
    ti2 = tmp_path / "proj-verify.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    assert chart_conversion_state(ti2) == STATE_REGULAR
    assert chart_conversion_state(None) == STATE_REGULAR


def test_a_stored_colorimetric_reference_marks_the_chart_converted(tmp_path):
    ti2 = tmp_path / "proj-verify.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    colorimetric_reference_for(ti2).write_text("CTI3\n", encoding="utf-8")
    assert chart_conversion_state(ti2) == STATE_CONVERTED


def test_a_claimed_but_missing_reference_still_forces_raw(tmp_path):
    """§3.1a A3c — refusing to convert is always the safe direction."""
    ti2 = tmp_path / "proj-verify.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    (tmp_path / "proj-verify.channels.json").write_text(json.dumps(
        {"ink_channels": ["r", "g", "b"],
         "colorimetric_reference": "proj-verify-reference.ti3"}), encoding="utf-8")
    assert chart_conversion_state(ti2) == STATE_CONVERTED_REF_MISSING


def test_a_corrupt_sidecar_does_not_break_detection(tmp_path):
    ti2 = tmp_path / "proj-verify.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    (tmp_path / "proj-verify.channels.json").write_text("{not json", encoding="utf-8")
    assert chart_conversion_state(ti2) == STATE_REGULAR


# --------------------------------------------------- A15–A18 the print record
def test_the_print_record_sits_beside_the_chart(tmp_path):
    ti2 = tmp_path / "proj-verify.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    profile = tmp_path / "proj.icc"
    profile.write_bytes(b"icc")
    path = write_print_record(ti2, colour=COLOUR_THROUGH, intent="relative",
                              profile=profile, route=ROUTE_CHROMIQ,
                              source_profile="sRGB.icm")
    assert path == print_record_path(ti2)
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["colour"] == COLOUR_THROUGH
    assert rec["intent"] == "relative"
    assert rec["route"] == ROUTE_CHROMIQ
    assert rec["profile"] == "proj.icc"
    assert rec["profile_mtime"]                  # A17: rebuilt-later detection
    assert rec["printed_at"]


def test_a_raw_record_carries_no_intent_and_no_profile(tmp_path):
    ti2 = tmp_path / "proj-verify.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    path = write_print_record(ti2, colour=COLOUR_RAW, intent="relative",
                              profile=tmp_path / "proj.icc",
                              route=ROUTE_EXTERNAL)
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert rec["colour"] == COLOUR_RAW
    assert rec["intent"] == ""
    assert "profile" not in rec
    assert rec["route"] == ROUTE_EXTERNAL


def test_the_record_is_found_from_a_dated_verification_ti3(tmp_path):
    """The report reads a measurement in ``verifications/<date>/``; the record
    sits one level up beside the shared chart — the same walk the reference
    ``.ti2`` lookup makes."""
    vroot = tmp_path / "verifications"
    dated = vroot / "2026-08-09_120000"
    dated.mkdir(parents=True)
    ti2 = vroot / "proj-verify.ti2"
    ti2.write_text("CTI2\n", encoding="utf-8")
    write_print_record(ti2, colour=COLOUR_THROUGH, intent="absolute",
                       profile=None, route=ROUTE_CHROMIQ)
    ti3 = dated / "proj-verify.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    rec = read_print_record(ti3)
    assert rec is not None and rec["intent"] == "absolute"


def test_no_record_reads_as_none(tmp_path):
    ti3 = tmp_path / "proj-verify.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    assert read_print_record(ti3) is None


def test_the_dated_snapshot_record_outranks_the_shared_one(tmp_path):
    """A dated verification's chart/ snapshot keeps the record of ITS print;
    the shared record describes only the LAST print of the chart. Found on
    hardware (2026-08-10): after printing the second sheet through the
    profile, the first (raw) sheet's report claimed "through-profile"."""
    from workflow import verification_print as vp
    vdir = tmp_path / "verifications" / "2026-08-10_120247"
    (vdir / "chart").mkdir(parents=True)
    ti3 = vdir / "c-verify.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    shared = tmp_path / "verifications" / "c-verify.ti2"
    shared.write_text("CTI2\n", encoding="utf-8")
    # The chart was printed raw for THIS date…
    vp.write_print_record(vdir / "chart" / "c-verify.ti2", colour=vp.COLOUR_RAW,
                          intent="", profile=None, route=vp.ROUTE_CHROMIQ)
    # …and later through the profile (the live, shared record).
    vp.write_print_record(shared, colour=vp.COLOUR_THROUGH, intent="relative",
                          profile=None, route=vp.ROUTE_CHROMIQ)
    rec = vp.read_print_record(ti3)
    assert rec is not None and rec["colour"] == vp.COLOUR_RAW
    # A date with no snapshot still falls back to the shared record.
    (vdir / "chart" / "c-verify.print.json").unlink()
    rec = vp.read_print_record(ti3)
    assert rec is not None and rec["colour"] == vp.COLOUR_THROUGH


def test_dated_report_resolves_the_chart_from_its_own_snapshot(tmp_path):
    """The date's chart/ snapshot outranks the shared verify chart — the
    shared one changes with every regenerate/restore, and judging an old date
    against whatever is live gave ΔE ≈ 41 nonsense for a 2.8 measurement
    (Sebastian, 2026-08-10, the trend's first point)."""
    from workflow.measurement_report import _find_reference_ti2
    vdir = tmp_path / "verifications"
    dated = vdir / "2026-08-10_113503"
    (dated / "chart").mkdir(parents=True)
    ti3 = dated / "c-verify.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    snap = dated / "chart" / "c-verify.ti2"
    snap.write_text("CTI2 snapshot\n", encoding="utf-8")
    shared = vdir / "c-verify.ti2"
    shared.write_text("CTI2 live\n", encoding="utf-8")
    assert _find_reference_ti2(ti3) == snap
    # Without a snapshot the shared chart is still the fallback.
    snap.unlink()
    assert _find_reference_ti2(ti3) == shared


def test_a_rebuilt_report_is_dated_by_the_measurement_file(tmp_path):
    """created = the .ti3's own time, so a history rebuilt for the trend does
    not collapse onto the moment the window was opened."""
    import os
    from workflow.measurement_report import build_report
    ti3 = tmp_path / "m.ti3"
    ti3.write_text(
        "CTI3\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 2\nBEGIN_DATA\n"
        '1 "1" 0 0 0 5 3 2\n2 "2" 100 100 100 65 73 52\nEND_DATA\n', encoding="utf-8")
    t = 1750000000.0
    os.utime(ti3, (t, t))
    from datetime import datetime
    want = datetime.fromtimestamp(t).isoformat(timespec="seconds")
    assert build_report(ti3)["created"] == want
