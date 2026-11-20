"""A10 completed (4.3.50): a table measurement carries CHROMIQ_VERSION and
CHROMIQ_HELPER_BUILD like a hand measurement.

The first attempt stamped the run's .ti3 AFTER filing it, which changed the
bytes the filing note's checksum named, so the next START read a saved sitting
as interrupted (five red tests, reverted in e4fbba3ee). The review found the
cause; the stamp now goes into the assembled file BEFORE the note is taken,
and the run's file is a copy of exactly those bytes. Nothing sent to the table
changes (the frozen wire tests stay as they are)."""
from __future__ import annotations

import inspect

import pytest

from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_ending import SECOND, _end, job_on, project
from tests.i1io_table.test_job_reading import read_page, ready_to_read
from tests.i1io_table.test_job_review8_fixes import (_a_complete_page, _power_cut_at,
                                                      _save_with_a_power_cut)
from workflow.i1io.table import job as J


def _header(path):
    return path.read_bytes().split(b"BEGIN_DATA_FORMAT")[0].decode("utf-8", "replace")


def test_a_saved_sitting_is_stamped_and_reads_as_saved(tmp_path):
    from workflow.i1io.table import session_end as se
    proj, run = project(tmp_path)
    job, sim, helper, p = job_on(run, tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    r, _st = _end(job, p, "save")
    assert r.ok
    job.close()
    head = _header(run.measurement_ti3)
    assert "CHROMIQ_VERSION" in head and "CHROMIQ_HELPER_BUILD" in head
    sdir = run.i1io_table_session_dir(RS.STAMP)
    assert se.session_state(sdir, run.measurement_ti3) == se.SAVED
    job2, *_ = job_on(run, tmp_path / "b", stamp=SECOND)
    found = {e["stamp"]: e for e in job2.earlier_sessions()}
    assert found[RS.STAMP]["state"] == se.SAVED


def test_a_crash_after_filing_still_reads_as_saved(tmp_path, monkeypatch):
    """The filing note names the stamped bytes: a power cut after the run's file changed
    (before session_result.json) is still recognised as saved at the next START."""
    from workflow.i1io.table import session_end as se
    run, job, sim, p = _a_complete_page(tmp_path)
    _power_cut_at(monkeypatch, job, "result")
    _save_with_a_power_cut(job)
    assert "CHROMIQ_VERSION" in _header(run.measurement_ti3)
    job2, *_ = job_on(run, tmp_path / "b", stamp=SECOND)
    found = {e["stamp"]: e for e in job2.earlier_sessions()}
    assert found[RS.STAMP]["state"] == se.SAVED


def test_an_interrupted_sitting_still_reads_as_interrupted(tmp_path, monkeypatch):
    from workflow.i1io.table import measurement as ms
    from workflow.i1io.table import session_end as se
    run, job, sim, p = _a_complete_page(tmp_path)
    _power_cut_at(monkeypatch, job, "filing")
    _save_with_a_power_cut(job)
    sdir = run.i1io_table_session_dir(RS.STAMP)
    assert (sdir / ms.FILING).is_file() and not run.measurement_ti3.exists()
    job2, *_ = job_on(run, tmp_path / "b", stamp=SECOND)
    found = {e["stamp"]: e for e in job2.earlier_sessions()}
    assert found[RS.STAMP]["state"] == se.INTERRUPTED


def test_the_stamp_precedes_the_filing_note_and_touches_only_files():
    src = inspect.getsource(J.TableJob.save)
    assert src.index("_stamp_provenance(self._assembly.path)") < src.index("se.filing_note(")
    helper = inspect.getsource(J._stamp_provenance)
    for word in ("send", "wire", "_link", "command", "transport"):
        assert word not in helper.replace("nothing is sent", ""), word
