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
    """The text lives in the reviewed catalogue now, so that is where it is
    checked; the window is checked for using it (test_message_catalogue.py)."""
    from workflow.measurement_messages import M_PROFILE_VERIFY
    body = M_PROFILE_VERIFY.body
    assert "What each button does" in body
    for button in ("Duplicate the run and build there", "Build here anyway",
                   "Cancel"):
        assert button in body


def test_the_message_carries_the_numbers():
    """§6c: "a few verification measurements" is not something a user can weigh."""
    from workflow.measurement_messages import M_PROFILE_VERIFY
    assert "{n} dated verification measurements" in M_PROFILE_VERIFY.body
    assert "back to {date}" in M_PROFILE_VERIFY.body


def test_no_message_uses_a_bracketed_plural():
    """The model's approved text is plural-only here — "1 dated verification
    measurements" is a wording point raised with Knut rather than fixed in the
    code, because the text is his to approve. What must never appear is the
    bracketed form."""
    from workflow.measurement_messages import M_PROFILE_VERIFY
    assert "(s)" not in M_PROFILE_VERIFY.body


def test_the_message_does_not_call_the_old_measurements_wrong():
    """Knut's correction: replacing the profile does not invalidate them; it
    removes the record of which profile they belong to."""
    from workflow.measurement_messages import M_PROFILE_VERIFY
    body = M_PROFILE_VERIFY.body
    assert "does not make those measurements wrong" in body
    assert "no longer say which profile they belong to" in body


def test_the_message_promises_nothing_is_deleted():
    from workflow.measurement_messages import M_PROFILE_VERIFY
    assert "Nothing is deleted" in M_PROFILE_VERIFY.body


def test_duplicate_is_not_offered_when_it_cannot_work():
    """§4a: never recommend a control the user would find greyed out.
    M-DUPLICATE-BLOCKED is appended to whichever message recommends it."""
    from workflow.measurement_messages import M_DUPLICATE_BLOCKED
    assert "Duplicating this run is not offered right now" in M_DUPLICATE_BLOCKED
    assert "{missing}" in M_DUPLICATE_BLOCKED, "and say which file is missing"

    src = inspect.getsource(TabProfile._confirm_rebuild_over_verifications)
    assert "if w.can_duplicate" in src
    assert "M_DUPLICATE_BLOCKED" in src


def test_the_silence_checkbox_is_scoped_and_says_so():
    from workflow.measurement_messages import (M_SILENCE_LABEL,
                                               M_SILENCE_TOOLTIP)
    assert M_SILENCE_LABEL == "Don't show this again for this run"
    assert "until you close ChromIQ" in M_SILENCE_TOOLTIP, \
        "the scope has to be visible"


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
