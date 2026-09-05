"""Light inks are diluted primaries, not spot colours (A-20, agent E).

A CMYKcm printer's ``c`` is cyan dye at a lower density, bought for smooth
highlights and neutrals. What is landed here is the ground the fix stands
on — the separation itself (``reports/agent-E/light-ink-policy.patch``)
lost the battery gate because the forward model is 5–8 ΔE00 off wherever
the light inks print (see ``docs/dev_profile_engine_accuracy_challenge.md``):

* ``ti3_data.light_ink_parents`` maps every light letter Argyll's COLOR_REP
  can carry to the ink it dilutes (the policy's input);
* the battery's S7 printer is a genuine diluted primary, and its two
  referees — the dedicated highlight sample and the light-first metric —
  mean what the README says they mean;
* devices without light inks build byte-identical profiles: the Fast-mode
  bytes of the battery's S3 (CMYK) and S5 (CMYKOG) at a fixed timestamp
  are pinned by sha256, so the light-ink code path stays inert for them.

Each test was proven able to fail: the mapping with the lowercase branch
removed, the metric with the light-first predicate inverted, the hash by
renaming the output file (the stem is embedded in the bytes).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import numpy as np
import pytest

from benchmarks.battery import (HIGHLIGHT_L, RAMP_L, highlight_points,
                                light_ink_usage)
from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from workflow.profile_engine.ti3_data import (light_ink_parents, read_ti3,
                                              split_rep_letters)

_TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rep, want", [
    ("RGB", {}),
    ("CMYK", {}),
    ("CMYKOG", {}),
    ("CMYKV", {}),
    ("CMYKcm", {4: 0, 5: 1}),
    ("CMYKcmk", {4: 0, 5: 1, 6: 3}),
    ("CMYKcmk1k", {4: 0, 5: 1, 6: 3, 7: 6}),      # 1k dilutes k, k dilutes K
    ("CMYKk1k", {4: 3, 5: 4}),
    ("CMYK2c2mcm", {4: 0, 5: 1, 6: 4, 7: 5}),     # c dilutes 2c, 2c dilutes C
    ("CMYKOGcm", {6: 0, 7: 1}),                   # spot inks stay spot inks
])
def test_light_channels_map_to_the_ink_they_dilute(rep, want):
    assert light_ink_parents(split_rep_letters(rep)) == want


def test_a_read_chart_knows_its_light_pairs(tmp_path):
    printer = PRINTERS["S7"]
    chart = make_chart(printer, 300)
    xyz, refl, _ = measure(printer, chart)
    meas = read_ti3(write_ti3(tmp_path / "s7.ti3", printer, chart, xyz, refl))
    assert meas.device_rep == "CMYKcm"
    assert meas.light_ink_parents == {4: 0, 5: 1}
    assert printer.light_ink_pairs == [(4, 0), (5, 1)]


# ---------------------------------------------------------------------------
# The battery printer and its referees
# ---------------------------------------------------------------------------

def test_s7_light_inks_are_diluted_primaries():
    """Light cyan's solid is the colour of ~40 % dark cyan — same hue,
    less density — and S1–S6 have no light inks."""
    p = PRINTERS["S7"]
    solid_c = np.zeros((1, 6)); solid_c[0, 4] = 1.0
    ramp = np.zeros((101, 6)); ramp[:, 0] = np.linspace(0.0, 1.0, 101)
    lab_c = p.lab_relative_true(solid_c)[0]
    lab_ramp = p.lab_relative_true(ramp)
    nearest = int(np.argmin(np.linalg.norm(lab_ramp - lab_c, axis=1)))
    assert 30 <= nearest <= 50                    # ≈ 40 % of the dark ink
    hue_c = np.degrees(np.arctan2(lab_c[2], lab_c[1]))
    solid_dark = np.zeros((1, 6)); solid_dark[0, 0] = 1.0
    lab_d = p.lab_relative_true(solid_dark)[0]
    hue_d = np.degrees(np.arctan2(lab_d[2], lab_d[1]))
    assert abs(hue_c - hue_d) < 15.0 and lab_c[0] > lab_d[0] + 10.0
    for pid in ("S1", "S2", "S3", "S4", "S5", "S6"):
        assert PRINTERS[pid].light_inks == () \
            and PRINTERS[pid].light_ink_pairs == []


def test_highlight_sample_is_light_and_not_empty():
    """The main grid holds 3 of 6,000 points above L* 70 on six inks; the
    highlight referee draws its own."""
    for pid in ("S1", "S3", "S5", "S7"):
        p = PRINTERS[pid]
        pts = highlight_points(p, 4000)
        assert len(pts) >= 150, pid
        lab = p.lab_relative_true(pts)
        assert (lab[:, 0] > HIGHLIGHT_L).all()
        cov = 1.0 - pts if p.is_additive else pts
        assert cov.max() <= 0.40 + 1e-12


class _FakeProfile:
    """A B2A that answers with a chosen device value per target."""

    def __init__(self, device):
        self._device = device

    def b2a_device(self, lab):
        assert len(lab) == len(self._device)
        return self._device


def test_light_first_metric_means_what_the_readme_says():
    p = PRINTERS["S7"]
    # Light-first highlight recipes (each pair's larger share on the light
    # ink) whose printed colours ARE the highlight targets, so they print
    # exactly; the ramp gets a light-first neutral recipe that need not.
    high = highlight_points(p, 2000)
    for light, parent in p.light_ink_pairs:
        lo, hi = np.minimum(high[:, light], high[:, parent]), \
            np.maximum(high[:, light], high[:, parent])
        high[:, light], high[:, parent] = hi, lo
    lab_high = p.lab_relative_true(high)
    n_ramp, n_high = len(RAMP_L), len(lab_high)
    targets = np.vstack([np.stack([RAMP_L, 0 * RAMP_L, 0 * RAMP_L], 1),
                         lab_high])
    dev = np.zeros((len(targets), 6))
    dev[n_ramp:] = high
    dev[:n_ramp, 4] = 0.30                        # light cyan leads…
    dev[:n_ramp, 0] = 0.10                        # …over 10 % dark cyan
    out = light_ink_usage(p, _FakeProfile(dev), lab_high)
    assert out["n_targets"] == n_ramp + n_high
    assert out["light_first"] == pytest.approx(1.0)      # every row passes
    assert out["colour_ok"] >= n_high / (n_ramp + n_high) - 1e-9
    assert out["fraction"] <= out["colour_ok"]
    assert out["ramp_max_step"] == pytest.approx(0.0)    # a flat recipe
    # The hue gate's signature: the dark ink carries a neutral alone.
    dev2 = dev.copy(); dev2[:n_ramp, 4] = 0.0; dev2[:n_ramp, 0] = 0.20
    out2 = light_ink_usage(p, _FakeProfile(dev2), lab_high)
    assert out2["light_first"] == pytest.approx(n_high / (n_ramp + n_high))
    # Dark ink at or above 40 % is allowed to lead (the handover happened).
    dev3 = dev.copy(); dev3[:n_ramp, 4] = 0.05; dev3[:n_ramp, 0] = 0.45
    assert light_ink_usage(p, _FakeProfile(dev3), lab_high)["light_first"] \
        == pytest.approx(1.0)
    # A jump along the ramp is the ramp step.
    dev4 = dev.copy(); dev4[10, 5] = 0.175
    assert light_ink_usage(p, _FakeProfile(dev4), lab_high)["ramp_max_step"] \
        == pytest.approx(0.175)


# ---------------------------------------------------------------------------
# Inert for every device without light inks
# ---------------------------------------------------------------------------

# Fast mode, quality l, 900-patch battery charts, timestamp 2026-01-01 —
# the bytes the engine at 4d1b714a wrote, measured from a `git archive
# HEAD` tree and the working tree alike (reports/agent-E). If a DELIBERATE
# engine change moves them, re-pin with:
#   .venv/bin/python -c "import tests.test_engine_light_inks_are_diluted_primaries as t; t.print_hashes()"
_FAST_QL_SHA256 = {
    "S3": "44a051ab5757b25b2adbad85e7bc05394f97ff5f292da8d49c50f59bcb4cb692",
    "S5": "8fa70ddf680987ff3e553834cd78ff87cf74b319981c9a3adbf7e40bf6e36346",
}


def _build_fast_ql(pid, out_dir):
    from workflow.profile_engine.builder import BuildSettings, build_profile
    printer = PRINTERS[pid]
    chart = make_chart(printer, 900)
    xyz, refl, _ = measure(printer, chart)
    ti3 = write_ti3(out_dir / f"{pid}.ti3", printer, chart, xyz, refl)
    icc = out_dir / f"{pid}-fast-l.icc"       # the stem is embedded in the bytes
    settings = BuildSettings(quality="l", gammap_mode="fast",
                             ink_limit=printer.tac, timestamp=_TS,
                             progress=lambda m: None)
    build_profile(ti3, icc, settings)
    return hashlib.sha256(icc.read_bytes()).hexdigest()


def print_hashes(out_dir=None):          # re-pin helper, see above
    import tempfile
    from pathlib import Path
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix="chromiq-lightink-"))
    for pid in _FAST_QL_SHA256:
        print(pid, _build_fast_ql(pid, out_dir))


@pytest.mark.parametrize("pid", sorted(_FAST_QL_SHA256))
def test_cmyk_and_spot_ink_profiles_are_byte_identical(pid, tmp_path):
    got = _build_fast_ql(pid, tmp_path)
    assert got == _FAST_QL_SHA256[pid], (
        f"{pid} ({PRINTERS[pid].device_rep}) Fast -ql bytes changed: the "
        f"light-ink code must stay inert for a device without light inks. "
        f"If this is a deliberate engine change, re-pin (see the comment "
        f"above _FAST_QL_SHA256).")
