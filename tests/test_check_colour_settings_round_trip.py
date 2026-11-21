"""The check reproduces colprof's own fit (issue 217, review B1): REAL ArgyllCMS.

A profile is built by colprof with the arguments Build Profile passes
(`ProfileBuilder._build_args`), its build is recorded as the app records it
(`record_for_build` + `fingerprint`), and the check's arguments come from the
record exactly as "Use the profile's settings" makes them
(`built_colorimetry` -> `apply_to_check` -> `ProfcheckRunner._build_args`).
profcheck's average and largest ΔE76 must then equal colprof's own "Profile
check complete" figures: the same colours on both sides. Cases: the observer
(-o 2015_2), the illuminant (-i D65), and the illuminant with FWA "Same as
illuminant" (-i D65 -f), the case the first build got wrong (it checked with
-fD50). The defaults (1931 2°, D50, no FWA) are the contrast: they must NOT
match the non-default builds.

The measurement is the repo's spectral test file with its instrument line set
to an i1Pro 2, because the ColorMunki that read it has no FWA (UV) data and
colprof refuses -f for it. This tests what ArgyllCMS computes, not a real
reading. Every call has a timeout.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "tests/data/g_basti_et8550_run1_verify"
       / "ET8550_EpsPremSG_AdobeRGB_CM_Okt26-verify.ti3")
ARGYLL = Path("/Applications/Argyll/bin")


def _bin(tool: str) -> "str | None":
    p = ARGYLL / tool
    return str(p) if p.is_file() else shutil.which(tool)


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(_bin("colprof") is None or _bin("profcheck") is None,
                       reason="ArgyllCMS colprof / profcheck not installed"),
]

_FIT = re.compile(r"Profile check complete, peak err = ([\d.]+), "
                  r"avg err = ([\d.]+)")
_CHECK = re.compile(r"max\. = ([\d.]+), avg\. = ([\d.]+)")


def _run(tmp_path, name):
    from core.file_manager import Project
    proj = Project.create(tmp_path / name, name)
    run = proj.current_run()
    text = SRC.read_text(encoding="latin-1")
    text = re.sub(r'^KEYWORD "CHROMIQ_VERIFICATION"\n', "", text, flags=re.M)
    text = re.sub(r'^CHROMIQ_VERIFICATION "true"\n', "", text, flags=re.M)
    text = text.replace('TARGET_INSTRUMENT "X-Rite ColorMunki"',
                        'TARGET_INSTRUMENT "X-Rite i1 Pro 2"')
    ti3 = run.dir / f"{name}.ti3"
    ti3.write_text(text, encoding="latin-1")
    return run, ti3


def _build(run, ti3, **colour):
    """colprof with Build Profile's own arguments; the app's record."""
    from core.argyll_runner import ArgyllRunner  # noqa: F401 (import check)
    from workflow import check_colorimetry as cc
    from workflow.profile_builder import ProfileBuilder, ProfileParams
    params = ProfileParams(ti3_path=ti3, quality="l", verbose=True, **colour)
    args = ProfileBuilder(None)._build_args(params)
    out = subprocess.run([_bin("colprof"), *args], cwd=ti3.parent,
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stdout + out.stderr
    m = _FIT.search(out.stdout + out.stderr)
    assert m, out.stdout[-2000:]
    icc = ti3.with_suffix(".icc")
    info = {"builder": "colprof", "profile": icc.name}
    info.update(cc.record_for_build(params))
    info.update(cc.fingerprint(icc))
    run.record_profile_build(info)
    return icc, (float(m.group(2)), float(m.group(1))), args


def _check(ti3, icc, *, follow: bool):
    from workflow import check_colorimetry as cc
    from workflow.profcheck_runner import ProfcheckParams, ProfcheckRunner
    params = ProfcheckParams(ti3_path=ti3, icc_path=icc, de_formula="",
                             verbosity="1")      # the tab's defaults
    if follow:
        built = cc.built_colorimetry(icc)
        assert built.known, built.why
        params = cc.apply_to_check(params, built.colorimetry)
    args = ProfcheckRunner(None)._build_args(params)
    out = subprocess.run([_bin("profcheck"), *args], cwd=ti3.parent,
                         capture_output=True, text=True, timeout=120)
    m = _CHECK.search(out.stdout + out.stderr)
    assert m, out.stdout[-2000:] + out.stderr[-2000:]
    return (float(m.group(2)), float(m.group(1))), args


@pytest.mark.parametrize("name,colour,expect_args", [
    ("obs", {"observer": "2015_2"}, ["-o", "2015_2"]),
    ("ill", {"illuminant": "D65"}, ["-i", "D65"]),
    ("fwa", {"illuminant": "D65", "fwa_enabled": True, "fwa_illum": ""},
     ["-fD65", "-i", "D65"]),
])
def test_the_check_reproduces_colprofs_own_fit(tmp_path, name, colour,
                                               expect_args):
    run, ti3 = _run(tmp_path, f"RT-{name}")
    icc, fit, _bargs = _build(run, ti3, **colour)
    got, cargs = _check(ti3, icc, follow=True)
    for a in expect_args:
        assert a in cargs, cargs
    assert got[0] == pytest.approx(fit[0], abs=2e-3), (got, fit, cargs)
    assert got[1] == pytest.approx(fit[1], abs=2e-3), (got, fit, cargs)
    # the tab's defaults do not reproduce it: the comparison is real
    plain, _ = _check(ti3, icc, follow=False)
    assert abs(plain[0] - fit[0]) > 0.01, (plain, fit)
