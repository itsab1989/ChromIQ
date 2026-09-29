"""B8-555: every release build installs PyInstaller at one pinned version.

PyInstaller 6.19.0 built a macOS app that does not start, and the workflows
installed whatever was newest ("pip install pyinstaller"). The versions that
built v4.3.0-beta.48 are pinned in requirements-build.txt; these tests keep
every build workflow installing from it, and nothing installing PyInstaller
around it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ("build-release.yml", "build-linux.yml", "build-windows.yml")
BUILD_REQS = ROOT / "requirements-build.txt"


def _pip_lines(text: str) -> "list[str]":
    return [ln.strip() for ln in text.splitlines()
            if re.search(r"\bpip3?\s+install\b", ln)]


def _pins() -> "dict[str, str]":
    pins = {}
    for ln in BUILD_REQS.read_text(encoding="utf-8").splitlines():
        ln = ln.split("#", 1)[0].split(";", 1)[0].strip()
        if not ln:
            continue
        m = re.fullmatch(r"([A-Za-z0-9_.\-]+)\s*==\s*([0-9][^\s]*)", ln)
        assert m, f"requirements-build.txt: {ln!r} is not an exact pin (==)"
        pins[m.group(1).lower()] = m.group(2)
    return pins


def test_the_build_requirements_pin_pyinstaller_and_qt_exactly():
    pins = _pins()
    for name in ("pyinstaller", "pyinstaller-hooks-contrib", "pyqt6",
                 "pyqt6-qt6", "pyqt6-webengine", "pyqt6-webengine-qt6"):
        assert name in pins, f"{name} is not pinned in requirements-build.txt"


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_the_workflow_installs_from_the_pinned_file(workflow):
    text = (ROOT / ".github" / "workflows" / workflow).read_text(
        encoding="utf-8")
    assert any("-r requirements-build.txt" in ln for ln in _pip_lines(text)), (
        f"{workflow} does not install requirements-build.txt, so its "
        "PyInstaller is whatever is newest")


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_no_workflow_installs_pyinstaller_around_the_pin(workflow):
    text = (ROOT / ".github" / "workflows" / workflow).read_text(
        encoding="utf-8")
    for ln in _pip_lines(text):
        for word in re.findall(r"(?<![-/\w])pyinstaller\S*", ln, re.I):
            assert "==" in word, (
                f"{workflow} installs {word!r} unpinned: {ln!r}")
