"""scripts/check_bundle_load_paths.py finds a library a binary loads but the
app does not contain (review K_review_beta1, CI-1: numpy's Intel OpenBLAS loads
three Fortran runtimes from its own folder, and a merge that copies only files
with an arm64 twin would ship an Intel half that cannot import numpy, while
every "is it fat" check passes)."""
from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import check_bundle_load_paths as C  # noqa: E402

WORKFLOW = (REPO / ".github" / "workflows" / "build-release.yml").read_text(encoding="utf-8")

needs_clang = pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("clang"),
                                 reason="needs macOS and clang")


def _cc(args, cwd):
    subprocess.run(["clang", *args], cwd=cwd, check=True, capture_output=True, timeout=120)


def _app(tmp_path: Path, with_dep: bool) -> Path:
    app = tmp_path / "Tiny.app"
    lib_dir = app / "Contents" / "Frameworks" / "pkg" / ".dylibs"
    lib_dir.mkdir(parents=True)
    (app / "Contents" / "MacOS").mkdir(parents=True)
    with open(app / "Contents" / "Info.plist", "wb") as fh:
        plistlib.dump({"LSMinimumSystemVersion": "13.0"}, fh)
    (tmp_path / "dep.c").write_text("int dep(void){return 1;}\n", encoding="utf-8")
    (tmp_path / "user.c").write_text("int dep(void); int user(void){return dep();}\n",
                                     encoding="utf-8")
    _cc(["-dynamiclib", "-o", "libdep.dylib", "-install_name",
         "@loader_path/libdep.dylib", "dep.c"], tmp_path)
    _cc(["-dynamiclib", "-o", str(lib_dir / "libuser.dylib"), "user.c",
         "-L.", "-ldep"], tmp_path)
    if with_dep:
        shutil.copy(tmp_path / "libdep.dylib", lib_dir / "libdep.dylib")
    return app


@needs_clang
def test_a_missing_loader_path_library_is_found(tmp_path):
    app = _app(tmp_path, with_dep=False)
    bad = C.missing(app)
    assert [(Path(r).name, d) for r, _a, d in bad] == [("libuser.dylib", "@loader_path/libdep.dylib")]
    assert C.main(["x", str(app)]) == 1


@needs_clang
def test_a_complete_app_passes(tmp_path):
    app = _app(tmp_path, with_dep=True)
    assert C.missing(app) == []
    assert C.main(["x", str(app)]) == 0


def test_the_release_build_runs_it_on_the_built_app():
    build = WORKFLOW.index("run: python3 -m PyInstaller ChromIQ.spec")
    check = WORKFLOW.index("python3 scripts/check_bundle_load_paths.py dist/ChromIQ.app")
    assert check > build
