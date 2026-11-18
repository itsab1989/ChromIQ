"""The worked examples under scripts/examples/ and the small helpers published with them are
safe for a stranger (scripts/README.md, "Safe to run for a stranger").

* every example script answers `--help` without writing a file, with no settings sandbox set;
* an example that builds the app refuses to start without `CHROMIQ_SETTINGS_FILE`;
* no example deletes anything;
* every example folder has a README that says it is an example;
* `scripts/examples/charts/byte_identity_every_preset/compare_identity.py` tells identical,
  clock-only and real differences apart, on invented hashes;
* `scripts/ptyrun.py` types each answer only after its question, in a real pseudo-terminal;
* `scripts/run_release_gates.sh` is valid shell, answers --help, and reads pytest's own exit
  code (it never pipes pytest).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "scripts" / "examples"
sys.path.insert(0, str(ROOT / "scripts"))


def _example_scripts():
    return sorted(p for p in EXAMPLES.rglob("*.py") if "__pycache__" not in p.parts)


def _clean_env():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CHROMIQ_SETTINGS_FILE", "CHROMIQ_PRESETS_DIR",
                                "CHROMIQ_LOG_DIR", "PYTEST_"))}
    return env


def test_there_are_examples():
    assert _example_scripts()


@pytest.mark.parametrize("script", _example_scripts(), ids=lambda p: p.name)
def test_help_writes_nothing(tmp_path, script):
    proc = subprocess.run([sys.executable, str(script), "--help"], cwd=tmp_path,
                          env=_clean_env(), capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert "EXAMPLE" in proc.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("script", _example_scripts(), ids=lambda p: p.name)
def test_no_example_deletes(script):
    src = script.read_text(encoding="utf-8")
    for word in ("rmtree", ".unlink(", "os.remove(", "rmdir(", "rm -"):
        assert word not in src, f"{script.name}: {word}"


@pytest.mark.parametrize("script", _example_scripts(), ids=lambda p: p.name)
def test_an_example_that_builds_the_app_needs_the_sandbox(tmp_path, script):
    src = script.read_text(encoding="utf-8")
    if not any(w in src for w in ("build_app", "AppSettings", "MainWindow", "userdrive")):
        pytest.skip("does not start the app")
    proc = subprocess.run([sys.executable, str(script), str(tmp_path), str(tmp_path / "o.json")],
                          cwd=tmp_path, env=_clean_env(), capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode != 0
    assert "CHROMIQ_SETTINGS_FILE" in proc.stderr + proc.stdout
    assert not (tmp_path / "o.json").exists()


def test_every_example_folder_has_a_readme():
    for folder in {p.parent for p in _example_scripts()}:
        readme = folder / "README.md"
        assert readme.is_file(), folder
        assert "pattern" in readme.read_text(encoding="utf-8")


def test_compare_identity_tells_the_three_cases_apart(tmp_path):
    sys.path.insert(0, str(EXAMPLES / "charts" / "byte_identity_every_preset"))
    import compare_identity as ci

    def run(files):
        return {"mode": "off", "repo": "tree", "on_screen": True,
                "rows": [{"key": "p1", "label": "Preset 1", "finished": True,
                          "target_name": "PB001", "files": files}]}
    a = run({"x.tif": {"sha": "1", "masked": None}, "x.ti2": {"sha": "2", "masked": "m"},
             "y.ti1": {"sha": "3", "masked": "n"}})
    b = run({"x.tif": {"sha": "1", "masked": None}, "x.ti2": {"sha": "9", "masked": "m"},
             "y.ti1": {"sha": "4", "masked": "o"}})
    lines, diffs = ci.compare(a, b)
    assert [d[1] for d in diffs] == ["y.ti1"]
    text = "\n".join(lines)
    assert "byte-identical: 1" in text and "identical except a wall-clock time stamp: 1" in text
    (tmp_path / "a.json").write_text(json.dumps(a))
    (tmp_path / "b.json").write_text(json.dumps(b))
    assert ci.main([str(tmp_path / "a.json"), str(tmp_path / "b.json")]) == 1
    assert ci.main([str(tmp_path / "a.json"), str(tmp_path / "a.json")]) == 0


@pytest.mark.skipif(sys.platform == "win32", reason="pty is POSIX only")
def test_ptyrun_answers_each_question_after_it_appears(tmp_path):
    import ptyrun
    text, code, left = ptyrun.run(
        [sys.executable, "-c", ptyrun.DEMO],
        [("Type yes to run it", "yes\n"), ("Did it do what was described?", "not sure\n")],
        timeout=60, transcript=str(tmp_path / "t.txt"))
    assert code == 0 and left == []
    assert "you typed yes" in text and "answer: not sure" in text
    assert (tmp_path / "t.txt").read_text(encoding="utf-8") == text


@pytest.mark.skipif(sys.platform == "win32", reason="pty is POSIX only")
def test_ptyrun_reports_a_question_that_never_came():
    import ptyrun
    _text, code, left = ptyrun.run([sys.executable, "-c", "print('hello')"],
                                   [("Type yes", "yes\n")], timeout=30)
    assert code == 0 and left == ["Type yes"]


@pytest.mark.skipif(sys.platform == "win32", reason="a bash script")
def test_the_gate_runner_is_valid_and_reads_pytests_own_exit_code(tmp_path):
    script = ROOT / "scripts" / "run_release_gates.sh"
    assert subprocess.run(["bash", "-n", str(script)], timeout=60).returncode == 0
    proc = subprocess.run(["bash", str(script), "--help"], cwd=tmp_path, capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0 and "THREE CONSECUTIVE" in proc.stdout
    assert list(tmp_path.iterdir()) == []
    src = script.read_text(encoding="utf-8")
    assert "pytest" in src and "| tail" not in src and 'wait "$P"; PRC=$?' in src
