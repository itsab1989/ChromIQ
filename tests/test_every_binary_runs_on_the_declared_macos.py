"""Every binary in ChromIQ.app runs on the macOS the app declares (13.0).

v4.3.2 shipped 17 binary slices that needed macOS 14 in an app that says
13.0 (scripts/check_bundle_min_macos.py on the released universal DMG,
2026-10-02): the two native helpers, built on the macos-14 runner with no
deployment target, and numpy's arm64 half, from the macosx_14_0 wheel pip
picks on that runner. macOS refuses to launch an executable built for a newer
system, so on Ventura the chart-reading engine could not run.
"""
from __future__ import annotations

import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_bundle_min_macos as C  # noqa: E402

WORKFLOW = (REPO / ".github" / "workflows" / "build-release.yml").read_text(encoding="utf-8")


def test_both_native_helpers_are_built_for_the_declared_macos():
    for helper in ("gammap", "chartread"):
        block = re.search(rf"cmake -S native/{helper}_helper -B build/{helper}(.*?)\n\s*cmake --build",
                          WORKFLOW, re.S)
        assert block, helper
        assert "-DCMAKE_OSX_DEPLOYMENT_TARGET=13.0" in block.group(1), helper


def test_the_spec_and_the_workflow_agree_on_13():
    spec = (REPO / "ChromIQ.spec").read_text(encoding="utf-8")
    assert "'LSMinimumSystemVersion':    '13.0'" in spec


def test_the_build_checks_every_binary_after_pyinstaller():
    build = WORKFLOW.index("run: python3 -m PyInstaller ChromIQ.spec")
    check = WORKFLOW.index("python3 scripts/check_bundle_min_macos.py dist/ChromIQ.app")
    assert check > build


def test_numpy_arm64_comes_from_its_macos_11_wheel_before_the_build():
    step = WORKFLOW.index("Use numpy's macOS 11 arm64 wheel")
    assert step < WORKFLOW.index("run: python3 -m PyInstaller ChromIQ.spec")
    assert "--platform macosx_13_0_arm64" in WORKFLOW[step:step + 1500]
    # and after the universal2 job's numpy<2.4 pin, so it reinstalls THAT version
    assert step > WORKFLOW.index("Pin numpy below 2.4 for old Intel Macs")


def test_the_lipo_step_takes_the_lowest_macos_x86_wheel():
    assert "w.sort(key=key); print(w[0]['url']" in WORKFLOW


# ---- the checker itself, on a real (tiny) app --------------------------------

def _app(tmp_path: Path, declared: str, binaries: dict[str, str]) -> Path:
    app = tmp_path / "Tiny.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    with open(app / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump({"LSMinimumSystemVersion": declared}, fh)
    src = tmp_path / "main.c"
    src.write_text("int main(void){return 0;}\n", encoding="utf-8")
    for name, minos in binaries.items():
        subprocess.run(["clang", f"-mmacosx-version-min={minos}", "-o",
                        str(app / "Contents" / "MacOS" / name), str(src)], check=True,
                       capture_output=True, timeout=120)
    (app / "Contents" / "MacOS" / "notes.txt").write_text("not a binary", encoding="utf-8")
    return app


needs_clang = pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("clang"),
                                 reason="needs macOS and clang")


@needs_clang
def test_a_binary_for_a_newer_macos_fails_the_check(tmp_path, capsys):
    app = _app(tmp_path, "13.0", {"old": "12.0", "new": "14.0"})
    declared, bad = C.too_new(app)
    assert declared == "13.0"
    assert [(Path(r).name, m) for r, _a, m in bad] == [("new", "14.0")]
    assert C.main(["x", str(app)]) == 1
    assert "Contents/MacOS/new" in capsys.readouterr().out


@needs_clang
def test_binaries_at_or_below_the_declared_macos_pass(tmp_path):
    app = _app(tmp_path, "13.0", {"a": "13.0", "b": "11.0"})
    assert C.too_new(app)[1] == []
    assert C.main(["x", str(app)]) == 0


def test_versions_compare_as_numbers_not_text():
    assert C._version("13.10") > C._version("13.9")
