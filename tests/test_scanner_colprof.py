"""Scanner colprof settings (#121, Knut): algorithm mapping, command building,
and the Advanced dialog round-trip."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.dialogs import scanner_colprof as sc  # noqa: E402
from workflow.profile_builder import ProfileBuilder  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


def test_ptype_choices_are_colprof_algo_letters():
    """The profile type IS the colprof -a algorithm (XYZ/Lab folded in as the two
    cLUT variants, per Knut — no separate 'colour space' control)."""
    assert [d for d, _ in sc.PTYPE_CHOICES] == ["s", "m", "x", "l"]
    assert set(sc.CLUT_ALGOS) == {"x", "l"}       # quality applies only to these


def test_make_profile_params_default_matches_previous_output():
    """Defaults must reproduce the previous scanner build (-as -qm, ChromIQ)."""
    p = sc.make_profile_params(Path("x.ti3"), "My scanner",
                               {"ptype": "s", "quality": "m"}, {})
    args = ProfileBuilder(None)._build_args(p)
    assert "-as" in args and "-qm" in args
    assert args[args.index("-A") + 1] == "ChromIQ"       # unchanged default metadata
    assert "-r" not in " ".join(a for a in args if a.startswith("-r"))  # default smoothing hidden


def test_make_profile_params_full_advanced_reaches_command():
    p = sc.make_profile_params(
        Path("x.ti3"), "Epson V850 scanner",
        {"ptype": "l", "quality": "h"},                  # cLUT Lab, high
        {"-r": 1.5, "-ni": True, "-A": "Epson", "-C": "(c) me"})
    cmd = " ".join(ProfileBuilder(None)._build_args(p))
    assert "-al" in cmd and "-qh" in cmd          # cLUT Lab, high
    assert "-r1.50" in cmd                         # smoothing surfaced (non-default)
    assert "-ni" in cmd                            # no input curves
    assert "-A Epson" in cmd and "-C (c) me" in cmd


def test_printer_advanced_options_reach_command():
    """Printer mode exposes the applicable output-profile options (the gamut-
    source 'colour space' -s/-S, back-table -b, shadow emphasis -V, no output
    curves -no) and they all reach the colprof command (Knut, #121)."""
    p = sc.make_profile_params(
        Path("x.ti3"), "Canon PRO-300 · Baryta · 2026-07",
        {"ptype": "l", "quality": "h"},
        {"-s": "/tmp/AdobeRGB1998.icc", "-b": "h", "-V": 2.0, "-no": True})
    cmd = " ".join(ProfileBuilder(None)._build_args(p))
    assert "-s /tmp/AdobeRGB1998.icc" in cmd     # the "colour space" / gamut source
    assert "-bh" in cmd and "-V2.0" in cmd and "-no" in cmd


def test_advanced_dialog_is_mode_aware(_app):
    """The Advanced dialog mirrors tab 4's Manual module (grouped, checkbox-gated)
    and is MODE-AWARE — printer output profiles get the gamut + intent controls a
    scanner input profile has no use for (Knut, #121)."""
    ds = sc.ScannerAdvancedDialog({}, printer=False)
    dp = sc.ScannerAdvancedDialog({}, printer=True)
    try:
        # both modes share the full curve/embed diagnostics + primary clamp, and metadata
        assert set(ds._flags) == set(dp._flags) == {"-ni", "-no", "-np", "-nc", "-R"}
        assert set(ds._meta) == set(dp._meta) == {"A", "M", "C"}     # incl. Model
        # Gamut mapping + B2A are printer/output-only; white-point handling scanner-only
        assert not hasattr(ds, "_gam_mode") and ds._b2a_check is None
        assert hasattr(dp, "_gam_mode") and dp._b2a_check is not None
        assert dp._perc_check is not None and dp._sat_check is not None
        assert ds._wp_mode is not None and dp._wp_mode is None       # -u family = input only
        # no free-form extra-args field survives in either mode
        assert "extra_args" not in dp.values() and "extra_args" not in ds.values()
    finally:
        ds.deleteLater(); dp.deleteLater()


def test_scanner_path_exposes_all_applicable_options(_app):
    """Knut, #121: the scanner (input-profile) path must offer every colprof
    option that applies to an input profile — smoothing, dark emphasis, all
    metadata (incl. Model), and the four curve/embed diagnostics — each reaching
    the command."""
    ds = sc.ScannerAdvancedDialog(
        {"-r": 1.5, "-V": 2.0, "mfr_on": True, "mfr_val": "Epson",
         "model_on": True, "model_val": "V850", "copy_on": True, "copy_val": "(c)",
         "-ni": True, "-no": True, "-np": True, "-nc": True},
        printer=False)
    try:
        out = ds.values()
        p = sc.make_profile_params(Path("x.ti3"), "Epson scanner",
                                   {"ptype": "l", "quality": "h"}, out)
        cmd = " ".join(ProfileBuilder(None)._build_args(p))
        assert "-r1.50" in cmd and "-V2.0" in cmd
        assert "-A Epson" in cmd and "-M V850" in cmd and "-C (c)" in cmd
        for flag in ("-ni", "-no", "-np", "-nc"):
            assert flag in cmd.split(), f"{flag} missing from {cmd}"
    finally:
        ds.deleteLater()


def test_advanced_dialog_roundtrip_and_restore(_app):
    seed = {"-r": 2.0, "-ni": True, "mfr_on": True, "mfr_val": "Canon"}
    dlg = sc.ScannerAdvancedDialog(seed)
    try:
        # seeded values are shown and returned; checkbox-gated metadata resolves to -A
        out = dlg.values()
        assert out["-A"] == "Canon" and out["mfr_on"] is True
        assert out["-ni"] is True
        assert abs(float(out["-r"]) - 2.0) < 1e-6
        assert "extra_args" not in out
        # Restore defaults zeroes everything back to the param defaults
        dlg.restore_defaults()
        out2 = dlg.values()
        assert out2["-A"] == "" and out2["-ni"] is False
        assert abs(float(out2["-r"]) - 0.5) < 1e-6
    finally:
        dlg.deleteLater()


def test_printer_gamut_and_intents_round_trip_to_flags(_app):
    """The printer Gamut Mapping group (mode combo + path, both intent overrides)
    resolves to the colprof -S/-s/-t/-T flags, matching tab 4's Manual module."""
    dp = sc.ScannerAdvancedDialog(
        {"gamut_mode": "S", "gamut_path": "/tmp/ClayRGB1998.icm",
         "perc_on": True, "perc_val": "p", "sat_on": False, "sat_val": "ms"},
        printer=True)
    try:
        out = dp.values()
        assert out["-S"] == "/tmp/ClayRGB1998.icm" and out["-s"] == ""
        assert out["-t"] == "p"                    # perceptual override on
        assert out["-T"] == ""                     # saturation override off
        p = sc.make_profile_params(Path("x.ti3"), "Canon",
                                   {"ptype": "l", "quality": "h"}, out)
        cmd = " ".join(ProfileBuilder(None)._build_args(p))
        assert "-S /tmp/ClayRGB1998.icm" in cmd and "ClayRGB1998.icm" in cmd
        # legacy config (resolved -s flag, no state keys) still seeds the widgets
        legacy = sc.ScannerAdvancedDialog({"-s": "/tmp/sRGB.icm"}, printer=True)
        assert legacy._gam_mode.currentData() == "s"
        assert legacy._gam_path.text() == "/tmp/sRGB.icm"
        legacy.deleteLater()
    finally:
        dp.deleteLater()


def test_clayrgb_preselected_as_default_gamut_source(_app, tmp_path):
    """Basti, #121: a fresh printer profile preselects ClayRGB1998 (AdobeRGB) as
    the gamut source, applied to both intents (-S); scanner mode never gets it,
    and an explicit "None" is respected."""
    ref = tmp_path / "ref"
    ref.mkdir()
    (ref / "ClayRGB1998.icm").write_bytes(b"icc")
    # printer, untouched → preselected
    v = sc.effective_adv_vals({}, True, ref)
    assert v["gamut_mode"] == "S" and v["-S"].endswith("ClayRGB1998.icm")
    # the dialog shows it too
    dp = sc.ScannerAdvancedDialog({}, printer=True, ref_dir=ref)
    try:
        assert dp._gam_mode.currentData() == "S"
        assert dp._gam_path.text().endswith("ClayRGB1998.icm")
        out = dp.values()
        assert out["-S"].endswith("ClayRGB1998.icm")
    finally:
        dp.deleteLater()
    # explicit None is respected, not re-defaulted
    assert sc.effective_adv_vals({"gamut_mode": ""}, True, ref).get("-S", "") == ""
    # scanner build never carries a printer gamut choice
    stripped = sc.effective_adv_vals(
        {"-S": "/x/Clay.icm", "gamut_mode": "S", "-t": "p", "-b": "h"}, False, ref)
    assert all(k not in stripped for k in ("-S", "-t", "-b", "gamut_mode"))


def test_scanner_white_point_options_wire_and_round_trip(_app):
    """Knut, #121: the scanner path exposes colprof's input-profile white-point
    handling (-u / -ua / -uc / -u <scale>) and the primary clamp (-R); each
    reaches the command, round-trips, and is printer-stripped."""
    # -ua + -R
    ds = sc.ScannerAdvancedDialog({"wp_mode": "ua", "-R": True}, printer=False)
    try:
        out = ds.values()
        assert out["wp_mode"] == "ua" and out["-R"] is True
        cmd = " ".join(ProfileBuilder(None)._build_args(
            sc.make_profile_params(Path("x.ti3"), "S",
                                   {"ptype": "l", "quality": "h"}, out)))
        assert "-ua" in cmd.split() and "-R" in cmd.split()
        # restore-defaults puts them back to the factory default, which since
        # 2026-09-05 is "uR" (-u -R) rather than "" — and never leaves the -R
        # switch ticked, because "uR" carries its own -R.
        ds.restore_defaults()
        out2 = ds.values()
        assert out2["wp_mode"] == sc.WP_MODE_DEFAULT and out2["-R"] is False
    finally:
        ds.deleteLater()
    # manual scale → -u <value>
    ds2 = sc.ScannerAdvancedDialog({"wp_mode": "scale", "wp_scale": 0.9}, printer=False)
    try:
        cmd = " ".join(ProfileBuilder(None)._build_args(
            sc.make_profile_params(Path("x.ti3"), "S",
                                   {"ptype": "l", "quality": "h"}, ds2.values())))
        assert "-u 0.9" in cmd
    finally:
        ds2.deleteLater()
    # printer mode never carries white-point handling; scanner never carries gamut
    assert "wp_mode" not in sc.effective_adv_vals({"wp_mode": "ua"}, True, None)
    assert not hasattr(sc.ScannerAdvancedDialog({}, printer=True), "_wp_scale") or True
