"""F-08: the gamut-mapping helper must survive a current optimising compiler.

Argyll 3.5.0's gamut.c read a single-triangle BSP leaf through
``(gtri **)&np``. That breaks C's strict-aliasing rule, and clang 20 and newer
(pointer TBAA on by default) delete the store of ``np`` at -O2/-O3: the helper
then reads uninitialised stack and segfaults in ``vector_isect_rec``. Measured
2026-10-05 with Apple clang 21 and clang 20.1.4 (the llvm-mingw that builds the
Windows ARM64 helper); gcc 13 and 16 were not affected.

Two guards, both kept: the vendored source copies the pointer into a real
``gtri *`` and the helper is compiled with ``-fno-strict-aliasing``. The fast
tests pin both; the slow one builds the helper the way the release workflows
do (Release, with clang when the machine has it) and runs Argyll's real mapper,
so a newer compiler on a CI image cannot bring the crash back unnoticed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tests.argyll_env import argyll_tool
from workflow.profile_engine import gammap_helper as gh

ROOT = Path(__file__).resolve().parent.parent
GAMUT_C = ROOT / "native/argyll/gamut/gamut.c"
HELPER_DIR = ROOT / "native/gammap_helper"


def test_vendored_gamut_c_never_reads_a_node_through_a_cast_of_its_address():
    src = GAMUT_C.read_text(encoding="latin-1")
    assert "(gtri **)&np" not in src, (
        "gamut.c reads a BSP node through (gtri **)&np again: clang >= 20 "
        "miscompiles that at -O2 and the helper segfaults (F-08)")
    # both single-triangle sites go through a real gtri * variable
    assert len(re.findall(r"t1 = \(gtri \*\)np;\s*tpp = &t1;", src)) == 2


def test_helper_build_turns_strict_aliasing_off():
    cm = HELPER_DIR.joinpath("CMakeLists.txt").read_text(encoding="utf-8")
    relax = re.search(r"set\(RELAX_FLAGS -w[^)]*\)", cm)
    assert relax and "-fno-strict-aliasing" in relax.group(0), (
        "the gcc/clang RELAX_FLAGS lost -fno-strict-aliasing (F-08)")
    # RELAX_FLAGS must reach the Argyll library, where gamut.c is compiled
    assert "target_compile_options(argyllgm PRIVATE ${RELAX_FLAGS})" in cm


def _compiler() -> str | None:
    for cc in ("clang", "cc", "gcc"):
        if shutil.which(cc):
            return cc
    return None


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("cmake") is None or _compiler() is None
                    or argyll_tool("iccgamut") is None,
                    reason="needs cmake, a C compiler and iccgamut")
@pytest.mark.parametrize("opt", ["-O2", "-O3"])
def test_helper_built_optimised_by_this_machines_compiler_maps(opt, tmp_path,
                                                               monkeypatch):
    cc = _compiler()
    build = tmp_path / "build"
    cfg = subprocess.run(
        ["cmake", "-S", str(HELPER_DIR), "-B", str(build),
         "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_C_FLAGS_RELEASE={opt} -DNDEBUG",
         f"-DCMAKE_C_COMPILER={cc}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300)
    assert cfg.returncode == 0, cfg.stderr[-800:]
    b = subprocess.run(["cmake", "--build", str(build), "-j4"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=1200)
    assert b.returncode == 0, b.stderr[-800:]
    exe = next(p for p in (build / "chromiq-gammap",
                           build / "chromiq-gammap.exe") if p.exists())
    version = subprocess.run([cc, "--version"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=60).stdout.splitlines()[0]
    monkeypatch.setenv("CHROMIQ_GAMMAP", str(exe))

    profiles = ROOT / "assets/profiles"

    def _gam(name: str, stem: str) -> Path:
        work = tmp_path / (stem + Path(name).suffix)
        shutil.copy(profiles / name, work)
        subprocess.run([argyll_tool("iccgamut"), "-ff", "-ir", "-pj", "-d10",
                        work.name], cwd=tmp_path, check=True,
                       capture_output=True, timeout=300)
        return work.with_suffix(".gam")

    # The exact call that segfaulted (exit -11) on clang 20/21 builds.
    query = np.array([[50.0, 0.0, 0.0], [70.0, 0.0, 0.0]])
    try:
        out = gh.run_gammap(query, src_gam=_gam("ClayRGB1998.icm", "src"),
                            intent="p", mapres=29,
                            dst_gam=_gam("sRGB.icm", "dst"))
    except gh.HelperUnavailable as exc:
        pytest.fail(f"helper built {opt} by {version} failed: {exc} (F-08)")
    assert out.shape == query.shape
    assert np.all(np.abs(out[:, 1:]) < 5.0)
