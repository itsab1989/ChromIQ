"""Second batch of engine fixes from the Maximum-accuracy challenge (A-08,
A-12, A-15, A-16, A-17, A-18 in reports/agent-A/01-findings.md, 2026-09-05).

* ``-s`` builds the perceptual table only and the saturation table aliases
  it (colprof.html); the engine mapped both and, with ``-nP -nS``, made the
  saturation table a copy of the perceptual one.
* The gamut tag leaked the inversion's residual (0.3–0.9 ΔE) onto two thirds
  of the printable interior; ICC.1 §9.2.29 says in-gamut = 0.
* On a chart measured at 3× a healthy instrument's noise the "please
  remeasure" line named 61 patches, one of them a misread.
* A stuck-instrument chart (every patch the same colour) built a profile in
  1.4 s that mapped every colour to paper white; a junk chart with a 5 ΔE fit
  installed like any other; a stamped 400 % ink limit on a chart printed at
  280 % sent the inversion to 349 %.
* Repeated patches are averaged before the fit (accurate mode) — measured
  better on every battery metric than fitting through the repeats.
* ``-no`` now reaches every B2A table; a v4 profile computed under D65 gets
  ``chad`` and a D50-adapted white point (ICC.1 §8.2, §9.2.36).
"""
from __future__ import annotations

import struct
from datetime import datetime, timezone

import numpy as np
import pytest

from benchmarks.iccread import IccProfile
from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from tests.test_profile_engine import synth_xyz, write_synth_ti3
from workflow.profile_engine import BuildSettings, EngineError, build_profile
from workflow.profile_engine.ti3_data import read_ti3

_TS = datetime(2026, 9, 5, tzinfo=timezone.utc)
_RGB = ["RGB_R", "RGB_G", "RGB_B"]
_CLAY = "/Applications/Argyll/ref/ClayRGB1998.icm"


def _tags(path) -> dict[bytes, tuple[int, int]]:
    d = path.read_bytes()
    n = struct.unpack(">I", d[128:132])[0]
    out = {}
    for i in range(n):
        sig, off, ln = struct.unpack(">4sII", d[132 + 12 * i:144 + 12 * i])
        out[sig] = (off, ln)
    return out


def _rgb_ti3(tmp_path, name="s.ti3"):
    return write_synth_ti3(tmp_path / name, "iRGB", _RGB, True, n_per_axis=6)


@pytest.mark.skipif(not __import__("pathlib").Path(_CLAY).exists(),
                    reason="Argyll ref profiles not installed")
def test_lowercase_s_aliases_the_saturation_table_to_perceptual(tmp_path):
    ti3 = _rgb_ti3(tmp_path)
    # Distinct names — APFS folds case, so "s.icc" and "S.icc" are ONE file.
    only = tmp_path / "perceptual-only.icc"
    both = tmp_path / "perceptual-and-saturation.icc"
    build_profile(ti3, only, BuildSettings(quality="l", timestamp=_TS,
                                           source_gamut=_CLAY,
                                           sat_gamut=False))
    build_profile(ti3, both, BuildSettings(quality="l", timestamp=_TS,
                                           source_gamut=_CLAY,
                                           sat_gamut=True))
    t = _tags(only)
    assert t[b"B2A2"] == t[b"B2A0"] and t[b"B2A0"] != t[b"B2A1"]
    t2 = _tags(both)
    assert t2[b"B2A2"] != t2[b"B2A0"]
    # -nP -nS with -S: two tables, both still distinct from the colorimetric.
    nps = tmp_path / "nPnS.icc"
    build_profile(ti3, nps, BuildSettings(quality="l", timestamp=_TS,
                                          source_gamut=_CLAY, sat_gamut=True,
                                          perc_src_colorimetric=True,
                                          sat_src_colorimetric=True))
    t3 = _tags(nps)
    assert t3[b"B2A2"] != t3[b"B2A0"]


def test_gamut_tag_is_zero_for_printable_colours(tmp_path):
    out = tmp_path / "g.icc"
    build_profile(_rgb_ti3(tmp_path), out, BuildSettings(quality="m",
                                                         timestamp=_TS))
    icc = IccProfile(out)
    rng = np.random.default_rng(2)
    dev = rng.uniform(0.05, 0.95, (2000, 3))
    lab = icc.a2b_lab(dev, "A2B1")
    g = icc.gamut_distance(lab)
    # The tag interpolates across cells, so a hard 100 % is out of reach for
    # any grid (colprof's own figure is 72 %); before the fix 32 % read 0.
    assert (g == 0).mean() >= 0.80, (g == 0).mean()
    assert (g < 1.0).mean() >= 0.99, (g < 1.0).mean()
    assert np.median(g) == 0.0
    # Reviewer R10: no band inside the surface either — colours on the
    # printer's own faces pulled 5 ΔE inward read under 1 ΔE.
    faces = rng.uniform(0.0, 1.0, (1500, 3))
    faces[np.arange(1500), rng.integers(0, 3, 1500)] = rng.integers(0, 2, 1500)
    lab_f = icc.a2b_lab(faces, "A2B1")
    chroma = np.hypot(lab_f[:, 1], lab_f[:, 2])
    keep = chroma > 15.0
    f = (chroma[keep] - 5.0) / chroma[keep]
    inside = np.stack([lab_f[keep, 0], lab_f[keep, 1] * f, lab_f[keep, 2] * f], 1)
    gi = icc.gamut_distance(inside)
    assert (gi < 1.0).mean() >= 0.95, (gi < 1.0).mean()
    far = np.array([[50.0, 120.0, 0.0], [50.0, 0.0, -120.0], [5.0, -80, 60]])
    assert (icc.gamut_distance(far) > 0).all()


def test_outlier_report_does_not_flood_on_a_noisy_chart(tmp_path):
    p = PRINTERS["S4"]                        # CMYK at 3× instrument noise
    chart = make_chart(p, 900)
    xyz, refl, misread = measure(p, chart, seed=23)
    ti3 = write_ti3(tmp_path / "s4.ti3", p, chart, xyz, refl)
    lines: list[str] = []
    res = build_profile(ti3, tmp_path / "s4.icc",
                        BuildSettings(quality="l", gammap_mode="accurate",
                                      timestamp=_TS, progress=lines.append))
    flagged = set(res.outlier_rows)
    # 61 of 900 before (A-15); a chart at 3× the healthy noise still has a
    # genuine tail, so the bar is "not a flood": under 3 % of the patches.
    assert len(flagged) <= 27, sorted(flagged)


def test_flat_measurement_is_refused(tmp_path):
    dev = np.random.default_rng(1).uniform(0, 1, (40, 3))
    dev[0] = 1.0
    xyz = np.tile([[48.4, 37.4, 5.8]], (40, 1))          # a stuck instrument
    lines = ["CTI3", "", 'COLOR_REP "RGB_XYZ"', 'DEVICE_CLASS "OUTPUT"',
             "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i, (d, x) in enumerate(zip(dev, xyz)):
        lines.append(f"{i + 1} " + " ".join(f"{v * 100:.3f}" for v in d)
                     + " " + " ".join(f"{v:.3f}" for v in x))
    lines.append("END_DATA")
    ti3 = tmp_path / "flat.ti3"
    ti3.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(EngineError, match="cannot describe a printer"):
        build_profile(ti3, tmp_path / "flat.icc",
                      BuildSettings(quality="l", gammap_mode="accurate"))
    assert not (tmp_path / "flat.icc").exists()


def test_poor_fit_gets_a_warning_line(tmp_path):
    rng = np.random.default_rng(4)
    dev = rng.uniform(0, 1, (300, 3))
    dev[0] = 1.0
    dev[1] = 0.0
    xyz = synth_xyz(dev, additive=True)
    xyz = xyz * rng.uniform(0.6, 1.4, xyz.shape)          # a wrecked read
    lines_t = ["CTI3", "", 'COLOR_REP "RGB_XYZ"', 'DEVICE_CLASS "OUTPUT"',
               "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
               "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
               "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i, (d, x) in enumerate(zip(dev, xyz)):
        lines_t.append(f"{i + 1} " + " ".join(f"{v * 100:.3f}" for v in d)
                       + " " + " ".join(f"{v:.3f}" for v in x))
    lines_t.append("END_DATA")
    ti3 = tmp_path / "junk.ti3"
    ti3.write_text("\n".join(lines_t), encoding="utf-8")
    log: list[str] = []
    build_profile(ti3, tmp_path / "junk.icc",
                  BuildSettings(quality="l", timestamp=_TS, progress=log.append))
    assert any("WARNING: the model fits this measurement poorly" in ln
               for ln in log), log[-5:]


def test_ink_limit_above_the_chart_is_capped_with_a_line(tmp_path):
    fields = [f"CMYK_{c}" for c in "CMYK"]
    ti3 = write_synth_ti3(tmp_path / "c.ti3", "CMYK", fields, False,
                          n_per_axis=6, ink_limit=400.0)
    printed = read_ti3(ti3).device.sum(1).max() * 100.0
    log: list[str] = []
    build_profile(ti3, tmp_path / "c.icc",
                  BuildSettings(quality="l", timestamp=_TS, progress=log.append))
    said = [ln for ln in log if "Total ink limit 400%" in ln]
    assert said and f"using {printed:.0f}%" in said[0], log[:6]
    # A limit the USER typed is kept with a warning, as colprof does.
    log2: list[str] = []
    build_profile(ti3, tmp_path / "c2.icc",
                  BuildSettings(quality="l", timestamp=_TS, ink_limit=390.0,
                                progress=log2.append))
    said2 = [ln for ln in log2 if "your total ink limit 390%" in ln]
    assert said2 and "Kept as you asked" in said2[0], log2[:6]
    assert not any("using" in ln and "actually measured" in ln for ln in log2)


def test_repeated_patches_can_be_averaged_in_accurate_mode(tmp_path):
    """Opt-in (BuildSettings.average_duplicates): the battery, whose charts
    repeat only white and black, measured a net loss with it on by default."""
    rng = np.random.default_rng(9)
    base = rng.uniform(0, 1, (200, 3))
    base[0] = 1.0
    base[1] = 0.0
    dev = np.vstack([base, base[:40], base[:40]])          # 40 patches ×3
    xyz = synth_xyz(dev, additive=True) + rng.normal(0, 0.3, (len(dev), 3))
    lines_t = ["CTI3", "", 'COLOR_REP "RGB_XYZ"', 'DEVICE_CLASS "OUTPUT"',
               "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
               "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
               "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i, (d, x) in enumerate(zip(dev, xyz)):
        lines_t.append(f"{i + 1} " + " ".join(f"{v * 100:.4f}" for v in d)
                       + " " + " ".join(f"{v:.4f}" for v in x))
    lines_t.append("END_DATA")
    ti3 = tmp_path / "rep.ti3"
    ti3.write_text("\n".join(lines_t), encoding="utf-8")
    m = read_ti3(ti3)
    groups, removed = m.collapse_duplicates()
    assert groups == 40 and removed == 80 and len(m.device) == 200
    log: list[str] = []
    res = build_profile(ti3, tmp_path / "rep.icc",
                        BuildSettings(quality="l", gammap_mode="accurate",
                                      timestamp=_TS, progress=log.append,
                                      average_duplicates=True))
    assert any("Averaged 40 repeated patch(es) (80 extra readings)" in ln
               for ln in log), log[:8]
    # Fitting THROUGH the repeats reads their scatter as misreads.
    stacked = build_profile(ti3, tmp_path / "stacked.icc",
                            BuildSettings(quality="l", gammap_mode="accurate",
                                          timestamp=_TS,
                                          average_duplicates=False))
    assert len(res.outlier_rows) <= len(stacked.outlier_rows), (
        res.outlier_rows, stacked.outlier_rows)
    assert len(res.outlier_rows) <= 6, res.outlier_rows
    # The noise model weighs each reading itself: no averaging there.
    log2: list[str] = []
    build_profile(ti3, tmp_path / "rep2.icc",
                  BuildSettings(quality="l", gammap_mode="accurate",
                                noise_model=True, timestamp=_TS,
                                progress=log2.append))
    assert not any("Averaged" in ln for ln in log2)


@pytest.mark.skipif(not __import__("pathlib").Path(_CLAY).exists(),
                    reason="Argyll ref profiles not installed")
def test_no_output_shaper_reaches_the_mapped_tables(tmp_path):
    out = tmp_path / "no.icc"
    build_profile(_rgb_ti3(tmp_path), out,
                  BuildSettings(quality="l", timestamp=_TS, source_gamut=_CLAY,
                                no_output_shaper=True))
    icc = IccProfile(out)
    for tag in ("B2A0", "B2A1", "B2A2"):
        lut = icc.lut(tag)
        ident = np.linspace(0.0, 1.0, lut.out_tables.shape[1])
        assert np.abs(np.asarray(lut.out_tables) - ident[None, :]).max() < 1e-3, tag


def test_v4_under_d65_carries_chad_and_a_d50_white(tmp_path):
    rng = np.random.default_rng(3)
    dev = rng.uniform(0.0, 1.0, (150, 3))
    dev[0] = 1.0
    dev[1] = 0.0
    lam = np.arange(380.0, 731.0, 10.0)
    peaks = np.array([450.0, 540.0, 610.0])
    absorb = np.exp(-((lam[None, :] - peaks[:, None]) / 40.0) ** 2)
    refl = 0.9 * np.prod(1.0 - 0.85 * (1.0 - dev)[:, :, None] * absorb[None],
                         axis=1)
    from workflow.profile_engine.spectral import spectra_to_xyz
    xyz = spectra_to_xyz(refl, lam)
    lines_t = ["CTI3", "", 'COLOR_REP "RGB_XYZ"', 'DEVICE_CLASS "OUTPUT"',
               'SPECTRAL_BANDS "36"', 'SPECTRAL_START_NM "380.0"',
               'SPECTRAL_END_NM "730.0"', f"NUMBER_OF_FIELDS {7 + 36}",
               "BEGIN_DATA_FORMAT",
               "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z "
               + " ".join(f"SPEC_{int(w)}" for w in lam),
               "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(dev)}", "BEGIN_DATA"]
    for i, (d, x, r) in enumerate(zip(dev, xyz, refl)):
        lines_t.append(f"{i + 1} " + " ".join(f"{v * 100:.4f}" for v in d)
                       + " " + " ".join(f"{v:.4f}" for v in x)
                       + " " + " ".join(f"{v:.5f}" for v in r))
    lines_t.append("END_DATA")
    ti3 = tmp_path / "spec.ti3"
    ti3.write_text("\n".join(lines_t), encoding="utf-8")
    v2 = tmp_path / "d65.icc"
    build_profile(ti3, v2, BuildSettings(quality="l", timestamp=_TS,
                                         illuminant="D65", icc_version="both"))
    v4 = tmp_path / "d65-v4.icc"
    assert v4.exists()
    t2, t4 = _tags(v2), _tags(v4)
    assert b"chad" not in t2 and b"chad" in t4       # v2 = colprof parity
    d = v4.read_bytes()
    off, _ = t4[b"wtpt"]
    w4 = np.array(struct.unpack(">iii", d[off + 8:off + 20])) / 65536.0
    off2, _ = t2[b"wtpt"]
    w2 = np.array(struct.unpack(">iii", v2.read_bytes()[off2 + 8:off2 + 20])) / 65536.0
    # The raw D65-relative white is bluish (Z high); adapted it sits at D50.
    assert w2[2] / w2[1] > 1.0 and abs(w4[2] / w4[1] - 0.8249) < 0.03, (w2, w4)
    assert abs(w4[0] / w4[1] - 0.9642) < 0.03
