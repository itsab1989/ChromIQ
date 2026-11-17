"""Build step 6: the job's session log and results, written through the Run's own members, with
the content the tester's results zip gave the analysis script, and nothing private in them: no
serial number, no person's or computer's name, no folder path."""
from __future__ import annotations

import getpass
import json
import os
import re

from core.file_manager import Run
from tests.i1io_table import job_harness as H
from tests.i1io_table import session_sim as ss
from workflow.i1io.table import diagnostics as dg
from workflow.i1io.table import job as J

STAMP = "20261117-120000"


def _sitting(tmp_path, steps=("open", "align", "creep", "check_move", "home")):
    run = Run.for_dir(tmp_path / "Basti's project" / "runs" / "run1")
    sheet, pts = H.recorded_sheet("S2 684.0", 18)
    res, job, sim, _p = H.run_steps(list(steps), script={J.Confirm.FRONT_CHOICE: "go on"},
                                    sheet=sheet, aims=pts, run=run, stamp=STAMP)
    return run, res, job, sim


def test_the_session_is_written_through_the_runs_members(tmp_path):
    run, res, job, sim = _sitting(tmp_path)
    folder = run.i1io_table_session_dir(STAMP)
    assert run.i1io_table_log(STAMP).is_file()
    assert run.i1io_table_sessions() == [folder]
    names = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    assert names == ["TABLE_IN_USE.acknowledged.json", "TABLE_IN_USE.json",   # fix round 10
                     "chart_identity.json",                                  # review 12
                     "d1-1/alignment.json", "d1-1/result.json", "d2-1/result.json",
                     "dz-1/result.json", "f-1/result.json", "session.log",
                     "session_summary.json", "summary.json"]   # step 8: the ending summary


def test_the_log_has_the_testers_content(tmp_path):
    run, res, job, sim = _sitting(tmp_path)
    log = run.i1io_table_log(STAMP).read_text(encoding="utf-8")
    kinds = {ln.split()[0] for ln in log.splitlines() if ln.strip()}
    assert {"INFO", "SEND", "RECV", "DATA", "STEP", "STAGE", "RESULT", "ANSWER", "STOP"} <= kinds
    sends = [ln.split(None, 2)[2] for ln in log.splitlines() if ln.startswith("SEND")]
    assert sends == sim.received                      # every line on the wire, in order
    # the analysis script's patterns (analyse_session_050.py): move times and positions
    assert re.search(r"^DATA\s+[\d.]+\s+(\w\w)(?: \((\w+)\))? took ([\d.]+) s", log, re.M)
    assert re.search(r"the arm reports \((-?\d+), (-?\d+)\)", log)
    blocks = [json.loads(ln.split(None, 1)[1]) for ln in log.splitlines()
              if ln.startswith("RESULT") and "{" in ln]
    assert [b["stage"] for b in blocks] == ["d1", "dz", "d2", "f"]
    keys = {"stage", "run", "verdict", "why", "folder", "lines_before", "lines_after",
            "moves_before", "moves_after", "position_before", "position_after", "t_start",
            "t_end", "answers", "data", "last_read", "arm_free", "mode_on",
            "movement_unconfirmed", "front_zone_reached_y"}
    assert all(keys <= set(b) for b in blocks)
    assert [b["verdict"] for b in blocks] == ["worked"] * 4
    summary = json.loads((run.i1io_table_session_dir(STAMP) / "summary.json").read_text(encoding="utf-8"))
    assert [b["stage"] for b in summary] == ["d1", "dz", "d2", "f"]
    al = json.loads((run.i1io_table_session_dir(STAMP) / "d1-1" / "alignment.json")
                    .read_text(encoding="utf-8"))
    assert set(al) == {"aims_mm", "readings", "M", "checks"}


def test_nothing_private_is_written(tmp_path, monkeypatch):
    run, res, job, sim = _sitting(tmp_path)
    folder = run.i1io_table_session_dir(STAMP)
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in folder.rglob("*") if p.is_file())
    forbidden = [str(tmp_path), str(folder), os.path.expanduser("~"), "/Users/", "C:\\",
                 "Basti's project", ss.FAKE_SERIAL, ss.FAKE_SERIAL.encode().hex().upper(),
                 ss._memory_a()[16:40], ss._memory_b()]
    user = getpass.getuser()
    if len(user) >= 3:
        forbidden.append(user)
    for word in forbidden:
        assert word not in text, word
    assert not re.search(r"[0-9A-Fa-f]{24,}", text)


def test_the_scrub_replaces_what_slips_in():
    home = os.path.expanduser("~")
    out = dg.scrub(f"a path {home}/x and {'AB' * 20}")
    assert home not in out and "AB" * 12 not in out
    assert out.startswith("a path <private>/x and"), out      # the whole home folder, at once
    assert dg.scrub("in /tmp/abc", extra=("/tmp/abc",)) == "in <private>"


def test_a_stopped_sitting_still_writes_its_block_and_summary(tmp_path):
    run = Run.for_dir(tmp_path / "run1")
    from tests.i1io_table import part_c_sim as csim
    sim = csim.CSimTable(part_c=True, aims=H.demo_aims())
    sim.inject_at(30, "unplug")
    res, job, sim, _p = H.run_steps(["open", "align", "check_move", "home"], sim=sim, run=run,
                                    stamp=STAMP)
    folder = run.i1io_table_session_dir(STAMP)
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary[-1]["verdict"] == "stopped" and summary[-1]["why"] == "link_lost"
    assert summary[-1]["way_back"] in (J.WayBack.LINK_LOST_REPLUG,
                                       J.WayBack.LINK_LOST_SWITCH_OFF_FIRST)
