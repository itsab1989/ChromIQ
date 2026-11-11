"""The normal gate cannot silently grow back to 27 minutes.

Basti, 2026-11-11: *"cut down the time for the gates. the engine is beta and
off by default so i dont want it to put on 25minutes on each gate from now
on"*. The heavy engine builds moved to their own tier (``--runengine``,
``tests/_engine_tier.py``). This file keeps that honest, cheaply and
deterministically: it reads the committed timing snapshot
``tests/data/gate_durations.json`` (a full gate run with every test's
setup + call + teardown) and the source tree, and never times anything live.

* every entry of the tier list and of the allow-list names a file and a test
  that still exist (a stale entry would make the list lie about what it moves);
* every test the snapshot measured above ``BOUND_SECONDS`` is in the heavy
  tier or on ``ALLOWED_SLOW`` with a reason;
* every FILE whose normal-gate tests add up to more than ``FILE_BOUND_SECONDS``
  is in the heavy tier or allow-listed, because ``--dist loadfile`` keeps a
  file on one worker and the gate cannot end before its slowest file does.

A new heavy test therefore turns this red the next time the snapshot is
re-made (``python scripts/gate_tier.py --snapshot <junit.xml>``), instead of
quietly adding minutes to every gate.
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from tests import _engine_tier as tier

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "tests" / "data" / "gate_durations.json"


@lru_cache(maxsize=None)
def _snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _functions(rel: str) -> frozenset[str]:
    """Every ``test_*`` function and ``Class::test_*`` method in a file."""
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(f"{node.name}::{sub.name}")
    return frozenset(names)


def _exists(nodeid: str) -> bool:
    rel, _, name = tier.strip_param(nodeid).partition("::")
    return (ROOT / rel).is_file() and name in _functions(rel)


def _covered(nodeid: str) -> bool:
    return tier.is_heavy(nodeid) or tier.strip_param(nodeid) in tier.ALLOWED_SLOW


# ---------------------------------------------------------------------------
# The lists name things that exist
# ---------------------------------------------------------------------------

def test_every_heavy_file_exists():
    missing = [f for f in tier.HEAVY_FILES
               if not (ROOT / "tests" / f).is_file()]
    assert not missing, f"stale HEAVY_FILES entries: {missing}"


def test_no_entry_is_listed_twice():
    assert len(set(tier.HEAVY_FILES)) == len(tier.HEAVY_FILES)
    assert len(set(tier.HEAVY_TESTS)) == len(tier.HEAVY_TESTS)
    in_heavy_file = [t for t in tier.HEAVY_TESTS if tier.is_heavy(t)
                     and t.split("::", 1)[0].rsplit("/", 1)[-1]
                     in tier.HEAVY_FILES]
    assert not in_heavy_file, (
        f"these tests are already moved with their whole file: {in_heavy_file}")


@pytest.mark.parametrize("nodeid", list(tier.HEAVY_TESTS)
                         + list(tier.ALLOWED_SLOW))
def test_every_listed_test_exists(nodeid):
    assert "[" not in nodeid, "list the function, not one parametrisation"
    assert _exists(nodeid), f"stale entry, no such test: {nodeid}"


def test_every_allowance_says_why():
    thin = [k for k, why in tier.ALLOWED_SLOW.items() if len(why.strip()) < 20]
    assert not thin, f"an ALLOWED_SLOW entry needs a real reason: {thin}"
    both = [k for k in tier.ALLOWED_SLOW if tier.is_heavy(k)]
    assert not both, f"in the heavy tier AND allow-listed: {both}"


# ---------------------------------------------------------------------------
# The normal gate stays fast
# ---------------------------------------------------------------------------

def test_the_snapshot_is_a_full_gate():
    snap = _snapshot()
    assert "--runengine" in snap["command"] and "--runslow" in snap["command"]
    assert snap["tests"], "the snapshot is empty"


def test_every_slow_test_is_in_the_heavy_tier_or_allowed():
    offenders = sorted(
        (secs, nodeid) for nodeid, secs in _snapshot()["tests"].items()
        if secs > tier.BOUND_SECONDS and _exists(nodeid)
        and not _covered(nodeid))
    assert not offenders, (
        f"{len(offenders)} test(s) took more than {tier.BOUND_SECONDS:.0f} s "
        "in the last measured full gate and would run in every NORMAL gate. "
        "Add each to tests/_engine_tier.py: HEAVY_FILES/HEAVY_TESTS if it is "
        "an engine build, else ALLOWED_SLOW with the reason it must stay:\n  "
        + "\n  ".join(f"{s:7.1f} s  {n}" for s, n in reversed(offenders)))


def test_no_file_holds_the_normal_gate_up():
    # A file's total over ALL its tests, less the slow ones that are moved
    # or allowed one by one (those are all in "tests", being >= its floor).
    per_file = {rel: secs for rel, secs in _snapshot()["files"].items()
                if (ROOT / rel).is_file()
                and not tier.is_heavy(f"{rel}::x")}
    for nodeid, secs in _snapshot()["tests"].items():
        rel = nodeid.split("::", 1)[0]
        if rel in per_file and _covered(nodeid):
            per_file[rel] -= secs
    big = sorted(((s, f) for f, s in per_file.items()
                  if s > tier.FILE_BOUND_SECONDS
                  and f not in tier.ALLOWED_SLOW_FILES), reverse=True)
    assert not big, (
        f"under --dist loadfile a file runs on ONE worker, so a file above "
        f"{tier.FILE_BOUND_SECONDS:.0f} s sets the floor of the whole normal "
        "gate. Move its heavy tests to tests/_engine_tier.py or allow the "
        "file in ALLOWED_SLOW_FILES with the reason:\n  "
        + "\n  ".join(f"{s:7.1f} s  {f}" for s, f in big))


@pytest.mark.parametrize("rel", sorted(set(tier.ALLOWED_SLOW_FILES)))
def test_every_allowed_file_exists_and_says_why(rel):
    assert (ROOT / rel).is_file(), f"stale ALLOWED_SLOW_FILES entry: {rel}"
    assert len(tier.ALLOWED_SLOW_FILES[rel].strip()) >= 20


# ---------------------------------------------------------------------------
# The guard script
# ---------------------------------------------------------------------------

def _gate_tier():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import gate_tier
    finally:
        sys.path.pop(0)
    return gate_tier


@pytest.mark.parametrize("path,full", [
    ("workflow/profile_engine/model.py", True),
    ("workflow/engine_builder.py", True),
    ("workflow/argyll_colorimetry.py", True),
    ("native/gammap_helper/main.c", True),
    ("native/argyll/xicc/xlut.c", True),
    ("benchmarks/research/run.py", True),
    ("tests/_engine_tier.py", True),
    ("ui/main_window.py", False),
    ("workflow/profile_builder.py", False),
    ("data/i18n/de.json", False),
    ("CLAUDE.md", False),
])
def test_the_script_names_the_full_gate_for_engine_paths(path, full):
    assert bool(_gate_tier().reasons_for_full([path])) is full


def test_a_heavy_test_file_change_needs_the_full_gate():
    gt = _gate_tier()
    for name in tier.HEAVY_FILES[:3]:
        assert gt.reasons_for_full([f"tests/{name}"])
    for nodeid in tier.HEAVY_TESTS[:3]:
        assert gt.reasons_for_full([nodeid.split("::", 1)[0]])


def test_the_script_runs_against_the_last_release_tag():
    try:
        tag = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
            timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("git is not here")
    if tag.returncode != 0:
        pytest.skip("no release tag in this checkout (a shallow CI clone)")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "gate_tier.py"),
                        "--quiet"], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr
    assert re.fullmatch(r"(FULL|NORMAL)\s*", r.stdout), r.stdout
