"""§T1.4 second half — the §6 warning is really in front of Build Profile.

``docs/design/unified_measurement_management.md`` §6. The decision is tested as
arithmetic in ``test_profile_rebuild_guard.py``; this checks the Build Profile
tab asks before it builds, that "Build here anyway" archives instead of
deleting, and that the message says everything §6c requires.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_profile import TabProfile      # noqa: E402


class _Silent:
    """Enough of the tab for the archiving to run: somewhere to log."""

    class _Log:
        def __init__(self): self.lines = []
        def appendPlainText(self, text): self.lines.append(text)

    def __init__(self):
        self._log = self._Log()


def test_the_question_comes_before_the_build():
    src = inspect.getsource(TabProfile._on_build)
    assert "_confirm_rebuild_over_verifications()" in src
    i = src.index("_confirm_rebuild_over_verifications()")
    for later in ("_runner.run", "start(", "colprof"):
        if later in src:
            assert i < src.index(later), f"the question must come before {later}"


def test_saying_no_stops_the_build():
    src = inspect.getsource(TabProfile._on_build)
    i = src.index("_confirm_rebuild_over_verifications()")
    assert "return" in src[i:i + 120]


def test_the_message_explains_every_button():
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "What each button does" in src
    for button in ("Duplicate the run and build there", "Build here anyway",
                   "Cancel"):
        assert button in src


def test_the_message_carries_the_numbers():
    """§6c: "a few verification measurements" is not something a user can weigh."""
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "{n} dated verification measurements" in src
    assert "back to {date}" in src


def test_one_measurement_reads_as_one_measurement():
    """House rule: real singular and plural, never "measurement(s)"."""
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "if n == 1:" in src
    assert "one dated verification measurement, made on" in src
    assert "(s)" not in src


def test_the_message_does_not_call_the_old_measurements_wrong():
    """Knut's correction: replacing the profile does not invalidate them; it
    removes the record of which profile they belong to."""
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "does not make those measurements" in src and "wrong" in src
    assert "no longer say which" in src and "profile they belong to" in src


def test_the_message_promises_nothing_is_deleted():
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert src.count("Nothing is deleted") >= 1


def test_duplicate_is_not_offered_when_it_cannot_work():
    """§4a: never recommend a control the user would find greyed out."""
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "if w.can_duplicate" in src
    assert "Why there is no Duplicate button here" in src
    assert "{missing}" in src, "and say which file is missing"
    assert "That leaves you two ways forward" in src, \
        "explaining an absence without a next step leaves the user stuck"


def test_the_silence_checkbox_is_scoped_and_says_so():
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "Don't show this again for this run" in src
    assert "until you close ChromIQ" in src, "the scope has to be visible"


def test_cancel_never_silences_the_question():
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "clicked in (dup, go)" in src


def test_build_here_anyway_archives_both_the_profile_and_its_verifications():
    src = inspect.getsource(TabProfile._archive_superseded_profile)
    assert "built_profile_icc()" in src
    assert "run.verifications()" in src and "v.exists()" in src
    assert "archive_to_old" in src


def test_the_archive_really_moves_the_files(tmp_path):
    """Not "it calls the right function" — the files are where the message
    said they would be, and still readable."""
    from core.file_manager import Run

    run_dir = tmp_path / "proj" / "runs" / "run1"
    (run_dir / "verifications").mkdir(parents=True)
    run = Run.for_dir(run_dir)
    run.built_profile_icc().write_bytes(b"icc")
    for vid in ("2026-01-01_100000", "2026-02-01_100000"):
        v = run.verification(vid)
        v.ensure_dir()
        v.measurement_ti3.write_text("BEGIN_DATA\nEND_DATA\n")

    TabProfile._archive_superseded_profile(
        _Silent(), run)

    assert not run.built_profile_icc().exists(), "moved, not copied"
    archived = list(run.old_dir.rglob("*.icc"))
    assert len(archived) == 1 and archived[0].read_bytes() == b"icc"

    moved = list(run.verifications_old_dir.rglob("*.ti3"))
    assert len(moved) == 2, "both dated measurements travelled with it"
    assert run.verifications() == [] or all(
        not v.exists() for v in run.verifications())


def test_the_verifications_do_not_land_in_the_runs_own_old_folder(tmp_path):
    """A verification's history stays inside verifications/ — the rule the rest
    of the app already follows."""
    from core.file_manager import Run

    run_dir = tmp_path / "proj" / "runs" / "run1"
    (run_dir / "verifications").mkdir(parents=True)
    run = Run.for_dir(run_dir)
    run.built_profile_icc().write_bytes(b"icc")
    v = run.verification("2026-01-01_100000")
    v.ensure_dir()
    v.measurement_ti3.write_text("BEGIN_DATA\nEND_DATA\n")

    TabProfile._archive_superseded_profile(_Silent(), run)

    strays = [p for p in run.old_dir.rglob("*.ti3")]
    assert strays == []


def test_nothing_is_archived_when_there_is_nothing_to_archive(tmp_path):
    from core.file_manager import Run

    run_dir = tmp_path / "proj" / "runs" / "run1"
    run_dir.mkdir(parents=True)
    run = Run.for_dir(run_dir)
    TabProfile._archive_superseded_profile(_Silent(), run)
    assert not run.old_dir.exists()


def test_archiving_never_stops_the_build():
    src = inspect.getsource(TabProfile._archive_superseded_profile)
    assert "except Exception" in src
    assert "WARNING" in src, "it is reported, not swallowed"


def test_a_loaded_file_is_not_treated_as_a_run():
    src = inspect.getsource(TabProfile._run_being_built_into)
    assert '"runs"' in src
    assert "return None" in src


def test_duplicate_reuses_the_one_implementation():
    """Two duplicate code paths would be two sets of guards to keep in step."""
    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "duplicate_run_requested.emit()" in src
    assert "proj.duplicate_run" not in src

    import ui.main_window as mw
    wired = inspect.getsource(mw.MainWindow.__init__)
    assert "duplicate_run_requested.connect" in wired
    assert "request_duplicate" in wired
