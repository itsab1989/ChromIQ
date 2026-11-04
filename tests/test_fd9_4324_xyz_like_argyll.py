"""4.3.24: an FD-9 measurement's XYZ is ArgyllCMS's, like an i1Profiler
import's (`workflow.argyll_colorimetry`).

4.3.22 and 4.3.23 summed the FD-9's 36 bands at 10 nm (about 0.05 dE76 mean,
0.35 max away from ArgyllCMS's ``spec2cie``). A new FD-9 measurement is now
worked out by ArgyllCMS's method and says so in ``CHROMIQ_XYZ_METHOD``. The
FD-9's own rules stay: reflectance as a fraction, never clipped (a brightened
paper reads above 1), D50 for M0, M1 and M2 alike (the sensor has already
produced the condition).

A measurement started before the update goes on, on Resume, with the method
its saved rows were made with, so one .ti3 never mixes the two and nobody
loses a half-measured chart. Every spectrum here is invented; the vendored
driver is not touched.
"""
from __future__ import annotations

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from tests.test_fd9_partial import setup  # noqa: F401
from tests.test_fd9_factory_workflow import action, native_settings
from workflow.fd9.measurement import (first_table, measure_chart,
                                      publish_measurement, resume_plan)
from workflow.fd9 import native_export as NE
from workflow.reference_convert import XYZ_METHOD_ARGYLL, XYZ_METHOD_KEYWORD

LAM = np.arange(380, 731, 10.0)


def _spec2cie():
    p = Path("/Applications/Argyll/bin/spec2cie")
    return str(p) if p.exists() else shutil.which("spec2cie")


def _spectra(n=30, seed=4):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        c, w, a = (rng.uniform(380, 720, 3), rng.uniform(15, 80, 3),
                   rng.uniform(0, 0.9, 3))
        out.append(0.02 + sum(a[k] * np.exp(-((LAM - c[k]) / w[k]) ** 2)
                              for k in range(3)))
    out = np.array(out)
    out[0] = 1.0                     # a perfect white
    out[1] = 0.88
    out[1, :6] = 1.3                 # a brightened paper, above 1, unclipped
    return out


def _rows(path):
    _, _, rows = first_table(path)
    spec = np.array([[float(r[f"SPEC_{int(w)}"]) for w in LAM] for r in rows])
    xyz = np.array([[float(r[k]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")]
                    for r in rows])
    return spec / 100.0, xyz


def _keywords(path):
    return dict(re.findall(r'^([A-Z0-9_]+) "([^"]*)"$',
                           Path(path).read_text(encoding="utf-8"), re.M))


def test_new_fd9_colour_is_argylls_and_the_old_sums_stay_available():
    from workflow.argyll_colorimetry import spectra_to_xyz_like_argyll
    for refl in _spectra(8):
        xyz, lab = NE.native_colour(refl)
        want = spectra_to_xyz_like_argyll(refl, LAM, illuminant="D50",
                                          observer="1931_2", percent=False,
                                          clamp=False)[0]
        assert np.allclose(xyz, want)
        assert len(lab) == 3
    old, _ = NE.native_colour(_spectra(3)[2], NE.XYZ_METHOD_SUMS)
    new, _ = NE.native_colour(_spectra(3)[2])
    assert not np.allclose(old, new, atol=1e-3)


def test_the_10nm_digest_is_exactly_the_one_4323_recorded():
    """So a session started before the update still resumes."""
    from workflow.profile_engine.spectral import illuminant_spd, observer_cmf
    lam = np.arange(380, 731, 10, dtype=float)
    record = {"wavelengths_nm": lam.tolist(),
              "D50": illuminant_spd("D50", lam).tolist(),
              "1931_2": observer_cmf("1931_2", lam).tolist(),
              "integration": "CIE15-discrete-Y100-v1"}
    old = hashlib.sha256(json.dumps(record, sort_keys=True,
                                    separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()
    assert NE.colour_data(NE.XYZ_METHOD_SUMS)[2] == old
    assert NE.colour_data()[2] != old


@pytest.mark.skipif(not _spec2cie(), reason="ArgyllCMS not installed")
def test_an_fd9_export_has_spec2cies_xyz(tmp_path):
    """The exported FD-9 .ti3, recomputed by spec2cie from its own SPEC_
    columns: within 0.001 dE76, brightened white included."""
    from workflow.profile_engine.ti3_data import xyz_to_lab
    spectra = _spectra()
    lines = ["CTI3", "", 'DESCRIPTOR "invented FD-9"', 'ORIGINATOR "test"',
             'DEVICE_CLASS "OUTPUT"', 'COLOR_REP "RGB_XYZ"',
             'SPECTRAL_BANDS "36"', 'SPECTRAL_START_NM "380.000000"',
             'SPECTRAL_END_NM "730.000000"', 'SPECTRAL_NORM "100"', "",
             f"NUMBER_OF_FIELDS {7 + 36}", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z "
             + " ".join(f"SPEC_{int(w)}" for w in LAM),
             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {len(spectra)}",
             "BEGIN_DATA"]
    mine = []
    for i, refl in enumerate(spectra, 1):
        xyz, _lab = NE.native_colour(refl)
        mine.append(xyz)
        lines.append(f"{i} 0 0 0 " + " ".join(f"{v:.10f}" for v in xyz) + " "
                     + " ".join(f"{100 * v:.10f}" for v in refl))
    lines += ["END_DATA", ""]
    src = tmp_path / "in.ti3"
    src.write_text("\n".join(lines), encoding="utf-8")
    try:
        r = subprocess.run([_spec2cie(), str(src), str(tmp_path / "out.ti3")],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        pytest.fail("spec2cie did not finish within 120 s")
    assert r.returncode == 0, r.stdout + r.stderr
    _spec, want = _rows(tmp_path / "out.ti3")
    d = np.linalg.norm(xyz_to_lab(np.asarray(mine)) - xyz_to_lab(want), axis=1)
    assert d.max() < 0.001, (d.mean(), d.max())


def test_a_new_measurement_records_its_method(setup):
    s = setup
    result = measure_chart(s.chart, native_settings(s), s.tmp / "new",
                           capture=action(s, 36, True))
    kw = _keywords(result["staged"])
    assert kw[XYZ_METHOD_KEYWORD] == XYZ_METHOD_ARGYLL
    assert kw["FD9_COLOUR_DATA_SHA256"] == NE.colour_data()[2]
    spec, xyz = _rows(result["staged"])
    for refl, got in zip(spec, xyz):
        assert np.allclose(got, NE.native_colour(refl)[0], atol=1e-6)


def _make_it_an_old_session(ti3: Path) -> None:
    """What 4.3.23 wrote: no CHROMIQ_XYZ_METHOD, the 10 nm digest, and XYZ
    and Lab from the 10 nm sums."""
    text = ti3.read_text(encoding="utf-8")
    text = re.sub(rf'^{XYZ_METHOD_KEYWORD} "[^"]*"\n', "", text, flags=re.M)
    text = re.sub(r'^FD9_COLOUR_DATA_SHA256 "[0-9a-f]+"',
                  f'FD9_COLOUR_DATA_SHA256 "{NE.colour_data(NE.XYZ_METHOD_SUMS)[2]}"',
                  text, flags=re.M)
    head, rest = text.split("BEGIN_DATA_FORMAT\n", 1)
    fields = rest.split("\n", 1)[0].split()
    body_start = text.index("BEGIN_DATA\n") + len("BEGIN_DATA\n")
    body_end = text.index("END_DATA\n", body_start)
    out = []
    for line in text[body_start:body_end].splitlines():
        vals = line.split()
        row = dict(zip(fields, vals))
        refl = [float(row[f"SPEC_{int(w)}"]) / 100 for w in LAM]
        xyz, lab = NE.native_colour(refl, NE.XYZ_METHOD_SUMS)
        for k, v in zip(("XYZ_X", "XYZ_Y", "XYZ_Z", "LAB_L", "LAB_A", "LAB_B"),
                        xyz + lab):
            vals[fields.index(k)] = f"{v:.10f}"
        out.append(" ".join(vals))
    text = text[:body_start] + "\n".join(out) + "\n" + text[body_end:]
    ti3.write_text(text, encoding="utf-8")


def test_a_session_from_before_the_update_resumes_with_its_own_method(setup):
    s = setup
    settings = native_settings(s)
    first = measure_chart(s.chart, settings, s.tmp / "first",
                          capture=action(s, 17))
    publish_measurement(first["staged"], first["destination"], s.chart,
                        allow_partial=True)
    base = Path(first["destination"])
    _make_it_an_old_session(base)
    old_rows = first_table(base)[2]
    resumed = replace(settings, resume=True)
    assert resume_plan(s.chart, resumed)[2] == [1, 2]
    last = measure_chart(s.chart, resumed, s.tmp / "last",
                         capture=action(s, 24, True))
    assert last["complete"]
    kw = _keywords(last["staged"])
    assert XYZ_METHOD_KEYWORD not in kw               # still the old method
    assert kw["FD9_COLOUR_DATA_SHA256"] == NE.colour_data(NE.XYZ_METHOD_SUMS)[2]
    assert first_table(last["staged"])[2][:12] == old_rows
    spec, xyz = _rows(last["staged"])
    for refl, got in zip(spec, xyz):               # every row, old and new
        assert np.allclose(got, NE.native_colour(refl, NE.XYZ_METHOD_SUMS)[0],
                           atol=1e-6)


def test_an_unknown_method_is_refused_with_the_resume_window(setup):
    s = setup
    settings = native_settings(s)
    first = measure_chart(s.chart, settings, s.tmp / "first",
                          capture=action(s, 17))
    publish_measurement(first["staged"], first["destination"], s.chart,
                        allow_partial=True)
    base = Path(first["destination"])
    base.write_text(base.read_text(encoding="utf-8").replace(
        XYZ_METHOD_ARGYLL, "something else"), encoding="utf-8")
    from ui.fd9_measurement import fd9_error_kind
    with pytest.raises(ValueError) as caught:
        resume_plan(s.chart, replace(settings, resume=True))
    assert fd9_error_kind(str(caught.value)) == "resume"


def test_the_vendored_driver_is_not_used_for_the_new_method():
    """The change is ChromIQ's own export; the vendored driver neither knows
    nor calls the new module."""
    src = (Path(__file__).resolve().parent.parent / "vendor" /
           "fd9-independent").rglob("*.py")
    assert not any("argyll_colorimetry" in p.read_text(encoding="utf-8")
                   for p in src)


def test_a_multi_page_resume_keeps_the_old_method_on_every_page(setup):
    """Page 1 measured before the update, page 2 after: page 2 is worked out
    the old way too, even though it starts fresh in this Start."""
    from tests.test_fd9_multipage import capture_pages, make_chart
    s = setup
    s.chart = make_chart(s.tmp).ti2_path
    settings = native_settings(s)
    capture, _ = capture_pages(s, stop_page=2)
    partial = measure_chart(s.chart, settings, s.tmp / "a", capture=capture)
    publish_measurement(partial["staged"], partial["destination"], s.chart,
                        allow_partial=True)
    _make_it_an_old_session(Path(partial["destination"]))
    capture, _ = capture_pages(s)
    final = measure_chart(s.chart, replace(settings, resume=True),
                          s.tmp / "b", capture=capture)
    assert final["complete"]
    assert XYZ_METHOD_KEYWORD not in _keywords(final["staged"])
    spec, xyz = _rows(final["staged"])
    for refl, got in zip(spec, xyz):
        assert np.allclose(got, NE.native_colour(refl, NE.XYZ_METHOD_SUMS)[0],
                           atol=1e-6)
