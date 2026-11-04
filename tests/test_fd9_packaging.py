"""Bundled SDK-free dependency and platform packaging contract."""

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bundled_source_is_self_contained_and_licensed():
    package = ROOT / "vendor/fd9-independent"
    assert (package / "LICENSE").is_file() and (
        package / "docs/PROVENANCE.md"
    ).is_file()
    # Audit the entire distributable package, including test fixtures and docs.
    # Binary SDKs, captured graphics/data and fitted JSON/CSV profiles must not
    # become redistributable merely by moving outside src/.
    for path in package.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        assert path.name == "LICENSE" or path.suffix in {".py", ".md", ".toml"}, path
        assert b"\0" not in path.read_bytes(), path
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    code = "from workflow.fd9.independent import driver; from pathlib import Path; m=driver(None); print(Path(m.__file__).resolve())"
    output = subprocess.check_output(
        [sys.executable, "-S", "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert str(package / "src") in output


def test_all_platform_specs_include_the_driver_and_its_license():
    for name in ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec"):
        text = (ROOT / name).read_text(encoding="utf-8")
        ast.parse(text)
        for module in (
            "conversion_profile",
            "motion",
            "geometry",
            "operator_controls",
            "native",
            "native_motion",
            "instrument_model",
            "factory_motion",
            "factory",
            "sensor_data",
            "sensor_status",
        ):
            assert "fd9_independent." + module in text
        # ChromIQ's own FD-9 modules imported only inside functions
        # (4.3.25 review, L7).
        for module in ("pages", "sheet_check", "furniture"):
            assert f"'workflow.fd9.{module}'" in text, (name, module)
        assert "vendor/fd9-independent/LICENSE" in text
        assert "'fd9-independent', 'src'" in text


def test_vendored_library_suite_runs_without_private_research_tools():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "vendor/fd9-independent/src")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(ROOT / "vendor/fd9-independent/tests"),
        ],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    count = re.search(r"Ran (\d+) tests", result.stderr)
    assert count and int(count.group(1)) >= 64, result.stderr
