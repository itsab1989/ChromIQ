"""§T2.6 and T2.7 of the Unified Measurement Management specification.

``docs/design/unified_measurement_management.md`` §2a and §3b: the measurement a
session starts from is copied aside before it runs, and put back when the
session ends badly.

Knut settled the policy (#130, 2026-08-03): *"archiving the ti3 at every session
start is the safest option, yes."* The reason it must be at the START is that
``chartread`` writes the file only on a clean exit and a resume overwrites the
file it resumed from — so by the time anything has gone wrong there is nothing
left to compare against and nothing to put back.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.measurement_session import MeasurementSession   # noqa: E402
from workflow.measurement_state import SessionVerdict          # noqa: E402

HEADER = "CTI3\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n" \
         "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n"


def _write(path, n, claimed=None):
    rows = "".join(f"{i} 10 10 10\n" for i in range(1, n + 1))
    path.write_text(f"{HEADER}\nNUMBER_OF_SETS {claimed if claimed is not None else n}\n"
                    f"BEGIN_DATA\n{rows}END_DATA\n")
    return path


@pytest.fixture
def run(tmp_path):
    d = tmp_path / "run1"
    d.mkdir()
    return d


# ---- T2.6 · the copy is taken, and nothing is lost -----------------------
def test_the_measurement_is_copied_before_a_session(run):
    ti3 = _write(run / "P.ti3", 12)
    s = MeasurementSession(ti3, old_dir=run / "old")
    archive = s.begin()
    assert archive is not None and archive.is_file()
    assert archive.read_text() == ti3.read_text(), "byte-identical copy"
    assert ti3.is_file(), "copied, not moved — a resume reads the live file"
    assert s.before == 12


def test_nothing_to_protect_is_not_an_error(run):
    s = MeasurementSession(run / "P.ti3", old_dir=run / "old")
    assert s.begin() is None
    assert s.before == 0


def test_the_copy_never_overwrites_an_earlier_one(run):
    ti3 = _write(run / "P.ti3", 5)
    from datetime import datetime
    when = datetime(2026, 8, 3, 12, 0, 0)
    a = MeasurementSession(ti3, old_dir=run / "old").begin(when)
    b = MeasurementSession(ti3, old_dir=run / "old").begin(when)
    assert a != b and a.is_file() and b.is_file()


# ---- T2.7 · the verdicts, end to end ------------------------------------
def test_a_normal_session_keeps_what_it_wrote(run):
    ti3 = _write(run / "P.ti3", 10)
    s = MeasurementSession(ti3, old_dir=run / "old")
    s.begin()
    _write(ti3, 40)
    out = s.finish(resumed=True)
    assert out.verdict is SessionVerdict.KEEP
    assert out.added == 30
    assert out.message_id is None, "nothing went wrong, so nothing to say"


def test_a_resume_that_lost_everything_is_put_back(run):
    """Knut's case: 10 patches before, an empty file after."""
    ti3 = _write(run / "P.ti3", 10)
    s = MeasurementSession(ti3, old_dir=run / "old")
    s.begin()
    _write(ti3, 0)
    out = s.finish(resumed=True)
    assert out.verdict is SessionVerdict.DELETE_AND_RESTORE
    assert out.restored and out.removed
    assert ti3.is_file()
    from workflow.measurement_state import classify
    assert classify(ti3).held == 10, "the earlier measurement is back"
    assert out.message_id == "M-TI3-EMPTY"


def test_a_resume_that_went_backwards_keeps_both(run):
    ti3 = _write(run / "P.ti3", 30)
    s = MeasurementSession(ti3, old_dir=run / "old")
    s.begin()
    _write(ti3, 8)
    out = s.finish(resumed=True)
    assert out.verdict is SessionVerdict.RESTORE_AND_KEEP_BOTH
    assert out.restored
    from workflow.measurement_state import classify
    assert classify(ti3).held == 30, "the longer measurement is what is live"
    assert out.kept_beside is not None and out.kept_beside.is_file(), \
        "and the shorter one is kept, because we do not know which is right"
    assert out.message_id == "M-TI3-SHRANK"


def test_the_empty_file_is_set_aside_not_deleted(run):
    """ChromIQ never deletes a file it did not create in the same breath — an
    empty measurement is still evidence of what happened."""
    ti3 = _write(run / "P.ti3", 4)
    s = MeasurementSession(ti3, old_dir=run / "old")
    s.begin()
    _write(ti3, 0)
    s.finish(resumed=True)
    aside = list((run / "old").rglob("empty-*.ti3"))
    assert aside, "the empty file is kept, under a name that says what it was"


def test_a_first_measurement_needs_no_rescue(run):
    ti3 = run / "P.ti3"
    s = MeasurementSession(ti3, old_dir=run / "old")
    s.begin()
    _write(ti3, 25)
    out = s.finish(resumed=False)
    assert out.verdict is SessionVerdict.KEEP
    assert out.added == 25


def test_a_session_that_read_nothing_at_all(run):
    ti3 = run / "P.ti3"
    s = MeasurementSession(ti3, old_dir=run / "old")
    s.begin()
    out = s.finish(resumed=False)
    assert out.verdict is SessionVerdict.NOTHING_TO_DO
    assert out.message_id is None


def test_replacing_with_fewer_readings_is_the_users_choice(run):
    """Not a resume, so this is a deliberate replace — the replace warning
    covers it, and this check must not second-guess it."""
    ti3 = _write(run / "P.ti3", 200)
    s = MeasurementSession(ti3, old_dir=run / "old")
    s.begin()
    _write(ti3, 9)
    out = s.finish(resumed=False)
    assert out.verdict is SessionVerdict.KEEP
    from workflow.measurement_state import classify
    assert classify(ti3).held == 9
    assert out.archive is not None and out.archive.is_file(), \
        "…and the 200-patch measurement is still in old/"


def test_a_failure_to_archive_does_not_block_measuring(run, monkeypatch):
    """The safety net failing must not stop the work it was protecting."""
    import shutil
    ti3 = _write(run / "P.ti3", 6)

    def boom(*_a, **_k):
        raise OSError("no room")

    monkeypatch.setattr(shutil, "copy2", boom)
    s = MeasurementSession(ti3, old_dir=run / "old")
    assert s.begin() is None
    assert s.before == 6, "the count is still taken, even when the copy fails"
