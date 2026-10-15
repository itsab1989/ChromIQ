"""#211 (Basti, 2026-10-15): in PATCH-BY-PATCH mode "Guide me through
refinement" goes patch by patch, to the patches the quality check found above
the limit, in chart order, never strip by strip and never to every patch of
the listed strips (a CR30 has no strip mode at all). Strip mode is unchanged.

Found by the other builder: in patch-by-patch mode the guide did nothing; the
engine simply went on to the first unread patch.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).parent))
from test_knut_5956210745_next_strip_after_a_read import (  # noqa: E402
    _feed, _session)

from workflow import profcheck_runner as PR            # noqa: E402
from workflow.refine_plan import Patch, build_plan     # noqa: E402

TARGETS = ["A2", "B3", "D1"]


def _patch_gotos(runner):
    out = []
    for raw in runner.sent:
        try:
            cmd = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if cmd.get("cmd") == "goto" and cmd.get("patch"):
            out.append(cmd["patch"])
    return out


def _ready(loc, all_done=True):
    return {"event": "spot_ready", "id": "1", "loc": loc, "read": True,
            "all_done": all_done}


def _read(loc):
    return {"event": "patch_read", "id": "1", "loc": loc}


def _guided(targets=TARGETS):
    m, r = _session(complete=True)
    m._spot_mode = True
    m.set_guided_patches(targets)
    lines: list = []
    done: list = []
    m.all_stripes_done.connect(lambda: done.append(True))

    def feed(*evs):
        for ev in evs:
            m._handle_engine_line(json.dumps(ev), lines.append)
    return m, r, feed, lines, done


def test_the_guide_takes_the_reader_to_each_listed_patch_in_turn():
    m, r, feed, lines, done = _guided()
    feed(_ready("A1"))                 # the engine opens on the first patch
    assert _patch_gotos(r) == ["A2"]
    feed(_ready("A2"))
    assert m._guided_state == "waiting"
    feed(_read("A2"), _ready("A3"))    # read; the engine steps on by itself
    assert _patch_gotos(r) == ["A2", "B3"]
    feed(_ready("B3"), _read("B3"), _ready("B4"))
    assert _patch_gotos(r) == ["A2", "B3", "D1"]
    assert not done
    feed(_ready("D1"), _read("D1"))
    assert done == [True], "the completion window follows the list"
    assert m._guided_state == "idle_done"
    text = "\n".join(lines)
    assert "A2, B3, D1" in text and "(1 of 3)" in text and "(2 of 3)" in text


def test_a_patch_not_on_the_list_is_never_where_the_guide_waits():
    m, r, feed, lines, done = _guided()
    feed(_ready("A1"), _ready("A2"), _read("A2"), _ready("A3"))
    feed(_ready("C1"))                 # the reader ended up elsewhere
    assert _patch_gotos(r)[-1] == "B3"
    feed(_read("C1"))                  # reading it does not tick B3 off
    assert m._guided_idx == 1


def test_strip_mode_keeps_its_strip_guide():
    m, r = _session(complete=True)
    m.set_guided_strips(["B", "D"])
    assert not m.guided_by_patch
    _feed(m, {"event": "strip_ready", "strip": "A", "read": True,
              "all_done": True})
    sent = [json.loads(x) for x in r.sent if x.startswith("{")]
    assert {"cmd": "goto", "strip": "B"} in sent


def test_the_plan_lists_the_patches_above_the_limit_in_chart_order():
    patches = [Patch("A1", 1.0, "A", 1), Patch("A2", 6.0, "A", 2),
               Patch("A3", 9.0, "A", 3), Patch("B1", 2.0, "B", 1),
               Patch("C2", 7.5, "C", 2), Patch("C1", 5.5, "C", 1)]
    plan = build_plan(patches, 5.0)
    assert [p for p, _ in plan.chosen_patches(first_only=False)] == \
        ["A2", "A3", "C1", "C2"]


def test_the_refine_file_carries_them_and_older_readers_ignore_them(tmp_path):
    f = PR.write_refine_strips(tmp_path, "x", [("A", 9.0), ("C", 7.5)],
                               patches=[("A2", 6.0), ("A3", 9.0),
                                        ("C1", 5.5), ("C2", 7.5)])
    assert PR.parse_refine_strips(f) == ["A", "C"]
    assert PR.parse_refine_patches(f) == ["A2", "A3", "C1", "C2"]
    old = tmp_path / "old.txt"
    old.write_text("# CHROMIQ_REFINE_STRIPS_V1\n# Strip\tMaxDE\nA\t9.00\n",
                   encoding="utf-8")
    assert PR.parse_refine_patches(old) == []
