"""The profile engine pins the paper white to the PCS white — in every mode.

Found 2026-09-04 by the engine-accuracy challenge (critic M1/M2): the engine's
least-squares surface passed NEAR the white patches, not through them, so on a
real 924-patch chart A2B1(device white) read L* 99.76 (fast) / 99.94 (accurate)
and B2A1(L*=100) returned RGB ≈ 0.996 — ink in every paper-white area of a
print under relative AND perceptual rendering. colprof pins both to white
(``xfit.c`` "White point fine tune"): it looks the device white up through
the fitted model, re-adapts the whole grid so that lands on D50, and records
the FITTED white as ``wtpt``. The engine now does the same, and ``-u`` scales
that fitted white instead of one measured row (which its duplicate twins
out-voted — critic M6).

These checks read the WRITTEN bytes through the benchmark CMM replay, so a
model that is right in memory and wrong on disk cannot pass; where Argyll is
installed, ``xicclu`` referees the same numbers.
"""
from __future__ import annotations

import shutil
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from benchmarks.iccread import IccProfile
from tests.test_profile_engine import write_synth_ti3
from workflow.profile_engine import BuildSettings, build_profile

_TS = datetime(2026, 9, 4, tzinfo=timezone.utc)
_XICCLU = Path("/Applications/Argyll/bin/xicclu")

_CASES = [
    ("iRGB", ["RGB_R", "RGB_G", "RGB_B"], True),
    ("CMYK", [f"CMYK_{c}" for c in "CMYK"], False),
]


def _wtpt(path: Path) -> np.ndarray:
    data = path.read_bytes()
    n = struct.unpack(">I", data[128:132])[0]
    for i in range(n):
        sig, off, _ = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        if sig == b"wtpt":
            return np.array(struct.unpack(">iii", data[off + 8:off + 20]),
                            float) / 65536.0
    raise AssertionError("no wtpt tag")


def _build(tmp_path: Path, rep, fields, additive, mode, **kw) -> Path:
    ti3 = write_synth_ti3(tmp_path / f"{rep}-{mode}.ti3", rep, fields,
                          additive, n_per_axis=6)
    out = tmp_path / f"{rep}-{mode}.icc"
    build_profile(ti3, out, BuildSettings(quality="l", gammap_mode=mode,
                                          timestamp=_TS, **kw))
    return out


@pytest.mark.parametrize("rep,fields,additive", _CASES)
@pytest.mark.parametrize("mode", ["fast", "accurate"])
@pytest.mark.parametrize("algorithm,smoothing", [
    ("l", 0.5), ("x", 0.5), ("l", 12.0)])
def test_device_white_lands_exactly_on_the_pcs_white(tmp_path, rep, fields,
                                                     additive, mode, algorithm,
                                                     smoothing):
    """Lab and XYZ PCS (reviewer R1b: the XYZ grid had no node at D50, so an
    ``-a x`` profile printed 5 % CMY into paper white), and a heavily
    smoothed fit (reviewer R1: the local correction's weight was evaluated
    at the node's own L and fell short — 97.7 instead of 100 at -r 12)."""
    out = _build(tmp_path, rep, fields, additive, mode, algorithm=algorithm,
                 smoothing=smoothing)
    icc = IccProfile(out)
    n = len(fields)
    white = np.full((1, n), 1.0 if additive else 0.0)
    for tag in ("A2B0", "A2B1", "A2B2"):
        lab = icc.a2b_lab(white, tag)[0]
        # Lab16 quantisation is 100/65280 in L and 255/65280 in a/b.
        assert abs(lab[0] - 100.0) < 0.02, (tag, lab)
        assert abs(lab[1]) < 0.02 and abs(lab[2]) < 0.02, (tag, lab)
    # An XYZ-PCS profile's 512–2048-entry input table cannot place D50
    # exactly on the corner (the code for the white is not an entry), so
    # the interpolated white lands 0.3 % short — one 8-bit step, the same
    # size as littleCMS's own rounding — where it was 4–10 % ink before.
    tol = 2e-3                      # XYZ too: the grid top sits one table
    #                                 step under the white (codec_for)
    for tag in ("B2A0", "B2A1", "B2A2"):
        dev = icc.b2a_device(np.array([[100.0, 0.0, 0.0]]), tag)[0]
        assert np.allclose(dev, white[0], atol=tol), (tag, dev)


@pytest.mark.parametrize("mode", ["fast", "accurate"])
def test_white_point_tag_is_the_fitted_paper(tmp_path, mode):
    """``wtpt`` is the FITTED white (what colprof records), not the
    brightest duplicate row (fast, max-selection bias) nor the row mean
    (accurate) — three profiles of one paper used to carry three whites."""
    rep, fields, additive = _CASES[0]
    out = _build(tmp_path, rep, fields, additive, mode)
    w = _wtpt(out)
    # The synthetic paper is Y=1 exactly; the fitted white sits within the
    # fit's own tolerance of it.
    assert abs(w[1] - 1.0) < 0.02, w
    assert abs(w[0] - 0.9642) < 0.02 and abs(w[2] - 0.8249) < 0.02, w


def test_engine_wp_scale_scales_the_fitted_white_like_xfit(tmp_path):
    """``BuildSettings.wp_scale`` (xfit.c semantics: grid ×1/scale, white
    ×scale) — kept for an input-class future; the Build tab cannot reach
    it, see the next test."""
    rep, fields, additive = _CASES[0]
    plain = _build(tmp_path, rep, fields, additive, "fast")
    (tmp_path / "u").mkdir()
    scaled = _build(tmp_path / "u", rep, fields, additive, "fast",
                    wp_scale=0.9)
    w0, w1 = _wtpt(plain), _wtpt(scaled)
    assert np.allclose(w1 / w0, 0.9, atol=2e-3), (w0, w1)


def test_hand_typed_u_scale_is_refused_exactly_like_colprof():
    """colprof 3.5.0 on printer data: ``-u 1.1`` → "Input auto WP scale mode
    isn't applicable to an output device" (run 2026-09-04). The engine used
    to accept ``-u`` from Manual's extra options and scale ONE measured
    white row, which its duplicate twins then out-voted (fast: no effect;
    accurate: ×0.979 instead of ×0.9). Same answer as colprof now."""
    from workflow.engine_builder import BuildSettings as _BS  # noqa: F401
    from workflow.engine_builder import _apply_extra_args
    s = BuildSettings()
    with pytest.raises(ValueError, match="isn't applicable to an output"):
        _apply_extra_args("-u 0.9", s)
    with pytest.raises(ValueError, match="isn't applicable to an output"):
        _apply_extra_args("-u", s)
    assert s.wp_scale is None


@pytest.mark.skipif(not _XICCLU.exists(), reason="Argyll not installed")
@pytest.mark.parametrize("mode", ["fast", "accurate"])
def test_argyll_reads_the_same_white(tmp_path, mode):
    """The referee that found the bug reads the fixed bytes."""
    rep, fields, additive = _CASES[0]
    out = _build(tmp_path, rep, fields, additive, mode)

    def look(flags: list[str], text: str) -> np.ndarray:
        res = subprocess.run([str(_XICCLU), *flags, str(out)], input=text,
                             capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
        last = res.stdout.strip().splitlines()[-1]
        # "1.000000 1.000000 1.000000 [RGB] -> Lut -> 100.000 0.000 0.000 [Lab]"
        return np.array(last.split("->")[-1].split("[")[0].split(), float)

    lab = look(["-ff", "-ir", "-pl"], "1 1 1\n")
    assert abs(lab[0] - 100.0) < 0.02 and np.abs(lab[1:]).max() < 0.02, lab
    dev = look(["-fb", "-ir", "-pl"], "100 0 0\n")
    assert np.allclose(dev, 1.0, atol=2e-3), dev
