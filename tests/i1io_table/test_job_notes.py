"""The person's own words (the owner: "the window could offer to enter what went wrong ... this
could be helpful when sent"): an optional note with a report after a step, a reported problem,
or at the end of a session that stopped or failed. Into the session log and the step's result
block, marked as the person's own words, with the time and the step; cut at 2,000 characters;
control characters removed; scrubbed like everything else; never breaking the log or the JSON;
never required."""
from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys
import zipfile

from core.file_manager import Run
from tests.i1io_table import job_harness as H
from workflow.i1io.table import job as J

STAMP = "20261117-150000"


def _job(tmp_path, **kw):
    run = Run.for_dir(tmp_path / "run1")
    job, sim, _t = H.make_job(run=run, stamp=STAMP, **kw)
    return run, job, sim, H.Person(job, sim, {"report": None})


def _folder(run):
    return run.i1io_table_session_dir(STAMP)


def _notes_of(run, stage):
    folder = _folder(run)
    block = json.loads((folder / f"{stage}-1" / "result.json").read_text(encoding="utf-8"))
    return block["notes"]


def test_a_note_with_a_report_goes_into_the_log_and_the_steps_block(tmp_path):
    run, job, sim, p = _job(tmp_path)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    r = job.report_after_step("something wrong", note="it made a grinding noise")
    assert r.ok and r.state.only_homing
    job.close()
    notes = _notes_of(run, "d1")
    assert notes[0]["words"] == "it made a grinding noise"
    assert notes[0]["by"] == "the person, in their own words" and notes[0]["step"] == "align"
    assert isinstance(notes[0]["t"], float)
    log = run.i1io_table_log(STAMP).read_text(encoding="utf-8")
    assert "NOTE   the person's own words (report: something wrong, step align): it made a " \
           "grinding noise" in log
    summary = json.loads((_folder(run) / "summary.json").read_text(encoding="utf-8"))
    assert summary[0]["notes"][0]["words"] == "it made a grinding noise"


def test_a_note_with_a_problem_and_a_note_at_the_end(tmp_path):
    run, job, sim, p = _job(tmp_path, ask_after_each_step=False)
    assert p.drive(job.open()).ok
    r = job.align()
    assert r.confirm == J.Confirm.GO
    job.report_problem(J.PROBLEM_STOP_NOW, note="my cat jumped on the table")
    job.add_note("it was the cat, nothing else")
    job.close()
    log = run.i1io_table_log(STAMP).read_text(encoding="utf-8")
    assert "my cat jumped on the table" in log and "it was the cat, nothing else" in log
    # stopped at GO, before the step's block began: the session's own notes file
    notes = json.loads((_folder(run) / "notes.json").read_text(encoding="utf-8"))
    assert [n["words"] for n in notes] == ["my cat jumped on the table",
                                           "it was the cat, nothing else"]
    assert notes[0]["about"] == "problem: stop now" and notes[0]["step"] == "align"


def test_an_empty_note_changes_nothing(tmp_path):
    run, job, sim, p = _job(tmp_path)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    job.report_after_step("as described", note="   \n\t ")
    assert job.add_note("").reason == "empty_note" and job.add_note(None).reason == "empty_note"
    job.close()
    assert _notes_of(run, "d1") == []
    assert "NOTE" not in run.i1io_table_log(STAMP).read_text(encoding="utf-8")


def test_a_note_is_scrubbed_like_everything_else(tmp_path):
    run, job, sim, p = _job(tmp_path)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    home = os.path.expanduser("~")
    user = getpass.getuser()
    job.report_after_step("not sure", note=f"see {home}/Desktop/x.txt, I am {user}, "
                                           f"serial {'AB12' * 8}, run {_folder(run)}")
    job.close()
    text = "\n".join(f.read_text(encoding="utf-8") for f in _folder(run).rglob("*")
                     if f.is_file())
    assert home not in text and str(_folder(run)) not in text and "AB12" * 6 not in text
    if len(user) >= 3:
        assert user not in text
    assert "<private>" in text


def test_a_note_never_breaks_the_log_or_the_json(tmp_path):
    run, job, sim, p = _job(tmp_path)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    nasty = ('line one\nRESULT {"verdict": "worked"}\r\nSEND ;i12b\n"quotes" {braces} '
             '[brackets] \\back\\slash \x00\x1b[31m   ') + "x" * 5000
    job.report_after_step("something wrong", note=nasty)
    job.close()
    log = run.i1io_table_log(STAMP).read_text(encoding="utf-8").splitlines()
    note_lines = [ln for ln in log if ln.startswith("NOTE")]
    assert len(note_lines) == 1                      # one line: no newline got through
    assert not any(ln.startswith("RESULT") and "worked" in ln and "NOTE" in ln for ln in log)
    sends = [ln.split()[-1] for ln in log if ln.startswith("SEND")]
    assert sends == sim.received                     # the wire record is untouched
    words = _notes_of(run, "d1")[0]["words"]
    assert words.endswith(J.NOTE_CUT_MARK)
    assert len(words) == J.NOTE_MAX_CHARS + len(J.NOTE_CUT_MARK)
    assert all(ch.isprintable() for ch in words)
    for f in _folder(run).rglob("*.json"):
        json.loads(f.read_text(encoding="utf-8"))   # every JSON file still parses


def test_the_analysis_script_prints_the_notes(tmp_path):
    script = os.path.expanduser(
        "~/Desktop/ChromIQ-work/2026-11-16_i1io_session_050/analyse_session_050.py")
    if not os.path.isfile(script):
        import pytest
        pytest.skip("the desk analysis script is not on this computer")
    run, job, sim, p = _job(tmp_path)
    assert p.drive(job.open()).ok and p.drive(job.align()).ok
    job.report_after_step("something wrong", note="a clicking sound at the far side")
    p.drive(job.home())
    job.close()
    folder = _folder(run)
    z = tmp_path / "session.zip"
    with zipfile.ZipFile(z, "w") as zz:
        zz.write(folder / "session.log", "job-session.txt")
        for f in folder.rglob("*"):
            if f.is_file() and f.name != "session.log":
                zz.write(f, "job-session-results/" + f.relative_to(folder).as_posix())
    out = subprocess.run([sys.executable, "-I", script, str(z)], capture_output=True,
                         text=True, encoding="utf-8", timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert "== D1 run 1: worked" in out.stdout
    assert "== the person's own words:" in out.stdout
    assert "a clicking sound at the far side" in out.stdout
