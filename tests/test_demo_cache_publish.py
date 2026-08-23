"""The demo-project cache must survive a marker-less tree on its key path.

Both things proved here were found by a Windows release gate that took 22
minutes and wedged at 99 %, twice. Neither is about the app: they are about the
suite's own plumbing, and both are invisible on macOS.

* ``os.replace`` cannot replace an existing directory on Windows. The cache
  publish read that failure as "another worker got there first", threw away its
  own good build, and left the unusable tree in place — so every later run
  rebuilt the demo projects from scratch, on two xdist workers at once. That
  build is the single most expensive thing in the suite.

* ``subprocess.run(capture_output=True, timeout=…)`` does not time out on
  Windows when a grandchild inherits the pipe: the post-kill ``communicate()``
  joins a reader thread that never ends. ``scripts/make_demo_projects.py`` shells
  out to Argyll three times and every one of them was written that way.
"""
from __future__ import annotations

import os
from pathlib import Path

from tests.conftest import _publish_demo_cache

MARKER = ".complete"


def _tree(root: Path, *, marker: bool) -> Path:
    """A stand-in for a built demo tree, with or without its completion marker."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "Demo-Full-RGB").mkdir(exist_ok=True)
    (root / "Demo-Full-RGB" / "project.json").write_text("{}")
    if marker:
        (root / MARKER).write_text("key")
    return root


def test_publishes_onto_a_free_key_path(tmp_path):
    staging = _tree(tmp_path / "staging", marker=True)
    cached = tmp_path / "key"

    assert _publish_demo_cache(staging, cached, cached / MARKER) is True

    assert (cached / MARKER).is_file()
    assert (cached / "Demo-Full-RGB" / "project.json").is_file()
    assert not staging.exists()


def test_a_complete_tree_already_there_wins(tmp_path):
    """Two workers finish at once: the published one stands, ours is dropped."""
    staging = _tree(tmp_path / "staging", marker=True)
    cached = _tree(tmp_path / "key", marker=True)
    (cached / "theirs.txt").write_text("built by the other worker")

    assert _publish_demo_cache(staging, cached, cached / MARKER) is True

    assert (cached / "theirs.txt").is_file(), "the winner's tree was clobbered"
    assert not staging.exists(), "our redundant build was left behind"


def test_a_marker_less_tree_does_not_poison_the_cache_for_ever(tmp_path):
    """THE REGRESSION. A tree with no marker used to be immortal on Windows.

    It is never read (the fixture requires the marker), and it could never be
    replaced (Windows), so it sat on the key path defeating the cache on every
    future run.
    """
    staging = _tree(tmp_path / "staging", marker=True)
    cached = _tree(tmp_path / "key", marker=False)
    (cached / "stale.txt").write_text("left by an interrupted run")

    assert _publish_demo_cache(staging, cached, cached / MARKER) is True

    assert (cached / MARKER).is_file(), "the cache is still unusable"
    assert not (cached / "stale.txt").exists(), "the stale tree was not cleared"
    assert (cached / "Demo-Full-RGB" / "project.json").is_file()


def test_the_healed_cache_is_then_a_hit(tmp_path):
    """After healing, a second publish takes the cheap path and keeps the tree."""
    cached = _tree(tmp_path / "key", marker=False)
    _publish_demo_cache(_tree(tmp_path / "s1", marker=True), cached, cached / MARKER)
    (cached / "ours.txt").write_text("the healed tree")

    assert _publish_demo_cache(
        _tree(tmp_path / "s2", marker=True), cached, cached / MARKER) is True
    assert (cached / "ours.txt").is_file(), "a cache hit rebuilt over itself"


def test_no_stale_aside_directories_are_left_behind(tmp_path):
    """Healing renames the dead tree aside — it must not survive the run."""
    cached = _tree(tmp_path / "key", marker=False)
    _publish_demo_cache(_tree(tmp_path / "staging", marker=True), cached, cached / MARKER)

    leftovers = [p.name for p in tmp_path.iterdir() if ".stale-" in p.name]
    assert leftovers == [], f"aside copies left in the cache home: {leftovers}"


def test_the_generator_never_captures_argyll_output_through_a_pipe():
    """``capture_output=True`` there is an unbounded wait on Windows.

    Guards the second half of the fix: the timeout on these calls is only real
    while the output goes to a file. Reintroducing ``capture_output`` — or a
    bare ``stdout=PIPE`` — brings the 99 % gate hang straight back.
    """
    src = Path(__file__).resolve().parents[1] / "scripts" / "make_demo_projects.py"
    lines = src.read_text(encoding="utf-8").splitlines()
    offenders = [
        f"{src.name}:{n}"
        for n, line in enumerate(lines, 1)
        if ("capture_output" in line or "subprocess.PIPE" in line)
        and not line.lstrip().startswith(("#", "*", '"', "'"))
        and "``" not in line
    ]
    assert offenders == [], f"piped Argyll output is a Windows deadlock: {offenders}"


def test_every_argyll_call_in_the_generator_is_bounded():
    """Each tool call must carry a timeout — a wedged targen once cost 2.5 h."""
    import ast

    src = Path(__file__).resolve().parents[1] / "scripts" / "make_demo_projects.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    unbounded = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name in ("run", "_run_tool") and "timeout" not in {k.arg for k in node.keywords}:
            unbounded.append(f"line {node.lineno}")
    assert unbounded == [], f"Argyll calls with no timeout: {unbounded}"
