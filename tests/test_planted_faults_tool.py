"""`scripts/planted_faults.py` tests the tests, and never touches the tree it copies.

Measured on an INVENTED mini project in `tmp_path`, so the suite never copies the real tree:

* the unplanted copy runs first and must be green;
* a fault the tests notice is "caught", one they do not notice "SURVIVED", one whose text is
  not there "NOT PLANTED", and the exit code is 1 while anything survived;
* every copy goes into its own new folder under `--out`, and an existing `--out` is refused;
* the original files are byte for byte unchanged afterwards;
* `--example` prints valid JSON whose faults name real files of this repository.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import planted_faults as pf  # noqa: E402


def _mini(tmp_path: Path) -> Path:
    proj = tmp_path / "mini"
    (proj / "pkg").mkdir(parents=True)
    (proj / "tests").mkdir()
    (proj / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (proj / "pkg" / "calc.py").write_text(
        "LIMIT = 10  # the cap\n\n\ndef add(a, b):\n    return a + b\n", encoding="utf-8")
    (proj / "tests" / "test_calc.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))\n"
        "from pkg.calc import add\n\n\ndef test_add():\n    assert add(2, 2) == 4\n",
        encoding="utf-8")
    return proj


def _faults(tmp_path: Path) -> Path:
    spec = {"tests": ["tests/test_calc.py"], "pytest_args": ["-q"],
            "faults": [
                {"id": "F1", "why": "plus becomes minus", "file": "pkg/calc.py",
                 "old": "return a + b", "new": "return a - b"},
                {"id": "F2", "why": "the cap raised by one, and no test looks",
                 "file": "pkg/calc.py", "old": "LIMIT = 10", "new": "LIMIT = 11"},
                {"id": "F3", "why": "text that is not there", "file": "pkg/calc.py",
                 "old": "return a * b", "new": "return 0"}]}
    p = tmp_path / "faults.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    return p


def test_caught_survived_and_not_planted_are_told_apart(tmp_path):
    proj = _mini(tmp_path)
    before = {p: p.read_bytes() for p in proj.rglob("*.py")}
    out = tmp_path / "planted"
    rc = pf.main([str(_faults(tmp_path)), "--out", str(out), "--root", str(proj),
                  "--timeout", "300"])
    assert rc == 1                                   # F2 survived, F3 was not planted
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    results = {r["id"]: r["result"] for r in report["runs"]}
    assert results == {"baseline": "passed", "F1": "caught", "F2": "SURVIVED",
                       "F3": "NOT PLANTED"}
    assert report["tree_unchanged"] is True
    assert {p: p.read_bytes() for p in proj.rglob("*.py")} == before
    for fid in ("baseline", "F1", "F2", "F3"):
        assert (out / fid / "tree" / "pkg" / "calc.py").is_file()
    assert "return a - b" in (out / "F1" / "tree" / "pkg" / "calc.py").read_text()
    assert (out / "report.md").is_file()


def test_an_existing_out_folder_is_refused(tmp_path):
    proj = _mini(tmp_path)
    out = tmp_path / "already"
    out.mkdir()
    (out / "keep.txt").write_text("mine", encoding="utf-8")
    assert pf.main([str(_faults(tmp_path)), "--out", str(out), "--root", str(proj)]) == 2
    assert (out / "keep.txt").read_text() == "mine"
    assert sorted(p.name for p in out.iterdir()) == ["keep.txt"]


def test_a_red_baseline_runs_no_fault(tmp_path):
    proj = _mini(tmp_path)
    (proj / "tests" / "test_calc.py").write_text("def test_red():\n    assert False\n",
                                                  encoding="utf-8")
    out = tmp_path / "planted"
    assert pf.main([str(_faults(tmp_path)), "--out", str(out), "--root", str(proj)]) == 1
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in report["runs"]] == ["baseline"]


def test_the_example_names_real_files(capsys):
    assert pf.main(["--example"]) == 0
    spec = json.loads(capsys.readouterr().out)
    for f in spec["faults"]:
        text = (ROOT / f["file"]).read_text(encoding="utf-8")
        assert text.count(f["old"]) == 1, f["id"]
        for t in f["tests"]:
            assert (ROOT / t).is_file()


def test_the_tool_has_no_delete_call():
    """It may copy and write, never remove (scripts/README.md, "safe for a stranger")."""
    src = (ROOT / "scripts" / "planted_faults.py").read_text(encoding="utf-8")
    for word in ("rmtree", "unlink(", "os.remove", "rmdir("):
        assert word not in src, word
