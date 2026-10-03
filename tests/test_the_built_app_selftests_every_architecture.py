"""The release build starts the BUILT app's self-test on every architecture
it carries (review P_review2_beta1: the Rosetta step imported numpy from the
runner's own site-packages, so an Intel half that cannot load its numpy would
still have passed)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = (REPO / ".github" / "workflows" / "build-release.yml").read_text(encoding="utf-8")


def test_the_workflow_is_valid_yaml():
    yaml.safe_load(WORKFLOW)


def test_the_selftest_runs_on_the_built_app_after_pyinstaller():
    build = WORKFLOW.index("run: python3 -m PyInstaller ChromIQ.spec")
    step = WORKFLOW.index("Start the built app's self-test on every architecture")
    assert step > build
    body = WORKFLOW[step:step + 900]
    assert "CHROMIQ_SELFTEST=1 arch -\"$a\" \"$EXE\"" in body
    assert "lipo -archs \"$EXE\"" in body
    assert "machine=$a " in body


def test_rosetta_failing_to_install_fails_the_build():
    line = next(l for l in WORKFLOW.splitlines() if "--install-rosetta" in l)
    assert "|| true" not in line


def _main(env_value, log_dir):
    env = dict(os.environ)
    env.pop("CHROMIQ_SELFTEST", None)
    if env_value is not None:
        env["CHROMIQ_SELFTEST"] = env_value
    env["CHROMIQ_LOG_DIR"] = str(log_dir)
    return subprocess.run([sys.executable, "-c",
                           "import runpy; runpy.run_path('main.py', run_name='not_main')"],
                          cwd=REPO, env=env, capture_output=True, text=True,
                          encoding="utf-8", timeout=180)


def test_the_selftest_prints_one_line_and_exits_0(tmp_path):
    r = _main("1", tmp_path)
    assert r.returncode == 0, r.stderr[-2000:]
    import platform
    assert r.stdout.strip() == (
        f"chromiq-selftest ok machine={platform.machine()} "
        f"numpy={__import__('numpy').__version__}")


def test_unset_it_does_nothing(tmp_path):
    r = _main(None, tmp_path)      # imports main.py without running main()
    assert r.returncode == 0, r.stderr[-2000:]
    assert "chromiq-selftest" not in r.stdout
