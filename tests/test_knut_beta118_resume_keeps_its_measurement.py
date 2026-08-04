"""#130 (Knut, 2026-08-01, testing beta.117): resuming destroyed the very
measurement it was resuming from.

He hit this five times in one session, on both reading engines::

    Error - Unable to read chart being resumed '…/run4/<name>.ti3'
          : Unable to open file '…' for reading

and each time the session died and the `.ti3` was gone from the run — recoverable
only because ``old/`` had it. His question was the right one: *"Many of these
errors above worked in earlier betas. What has happened?"*

**What happened.** Refine and resume hand the existing `.ti3` to chartread with
``-r``, so it is read, not replaced. Two decisions have to agree about that:
whether to warn that something is being replaced, and whether to move the file
into ``old/`` first. They were one decision — the archive happened inside the
question — and were deliberately separated in beta.113 so that a method called
``_confirm_…`` did not quietly move files. The archive lost the condition in the
move: the question still returned early for a resume, but the archive ran
regardless.

So ChromIQ moved the file away and then told chartread to resume from it.

Both now ask :meth:`TabMeasure._read_builds_on_existing`, and a test below
asserts they do — the two must never drift apart again, because when they do it
costs a measurement.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import QApplication             # noqa: E402

from core.argyll_runner import ArgyllRunner          # noqa: E402
from core.file_manager import Project                # noqa: E402
from core.settings import AppSettings                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab_and_ti3(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    proj = Project.create(tmp_path / "out" / "Demo", "Demo")
    run = proj.current_run()
    ti2 = run.dir / f"{run.stem}.ti2"
    ti2.write_text("CTI2\n\nNUMBER_OF_SETS 4\n")
    ti3 = run.dir / f"{run.stem}.ti3"
    ti3.write_text(
        "CTI3\n\nNUMBER_OF_SETS 1\n\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        "BEGIN_DATA\n1 100 100 100 95.0 100.0 108.9\nEND_DATA\n")

    from ui.tabs.tab_measure import TabMeasure
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._ti1_path = ti2
    return tab, ti3, run


def _set_refine(tab, on: bool):
    """Tick the refine box belonging to the mode that is on screen.

    The tab keeps a guided pair and a manual pair, and only the visible one
    counts — which is exactly why the check must be in one method rather than
    repeated at each call site.
    """
    guided = tab._current_mode() == "guided"
    cb = tab._refine_cb if guided else tab._m_refine_cb
    assert cb is not None
    cb.setVisible(True)
    cb.setEnabled(True)
    cb.setChecked(on)
    return cb


# ---- the fault itself ----------------------------------------------------
def test_resuming_keeps_the_measurement_it_resumes_from(tab_and_ti3):
    """THE regression test. Archiving here does not protect the file — it
    removes the one chartread is about to read."""
    tab, ti3, run = tab_and_ti3
    _set_refine(tab, True)
    tab._archive_measurement_before_replacing()
    assert ti3.is_file(), \
        "the measurement chartread is about to resume from was moved away"
    assert not list(run.dir.glob("old/**/*.ti3"))


def test_a_real_replacement_still_keeps_a_copy(tab_and_ti3):
    """The behaviour this archive exists for must survive the fix — Knut,
    2026-07-31: he agreed to REPLACE a measurement, not to have it destroyed."""
    tab, ti3, run = tab_and_ti3
    _set_refine(tab, False)
    tab._archive_measurement_before_replacing()
    assert not ti3.is_file()
    archived = list(run.dir.glob("old/**/*.ti3"))
    assert len(archived) == 1, archived


def test_the_decision_matches_the_checkbox(tab_and_ti3):
    tab, _ti3, _run = tab_and_ti3
    _set_refine(tab, True)
    assert tab._read_builds_on_existing() is True
    _set_refine(tab, False)
    assert tab._read_builds_on_existing() is False


def test_a_hidden_refine_box_does_not_count(tab_and_ti3):
    """A ticked box the user cannot see is not a choice they made — and a
    read that does not actually resume DOES replace, so the copy is wanted."""
    tab, ti3, _run = tab_and_ti3
    cb = _set_refine(tab, True)
    cb.setEnabled(False)
    assert tab._read_builds_on_existing() is False
    tab._archive_measurement_before_replacing()
    assert not ti3.is_file()


# ---- the two decisions must not drift apart again ------------------------
def test_the_question_and_the_archive_ask_the_same_thing():
    """They were one decision, were separated for good reasons, and the
    separation is what lost the condition. Neither may re-implement it."""
    from ui.tabs.tab_measure import TabMeasure
    confirm = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    archive = inspect.getsource(TabMeasure._archive_measurement_before_replacing)
    assert "_read_builds_on_existing" in confirm
    assert "_read_builds_on_existing" in archive
    # Neither may reach for the checkboxes itself. (The question does use
    # isChecked() — for its own "don't ask again" tick — so the check is for
    # the refine/resume widgets by name, not for the call.)
    for src, name in ((confirm, "the question"), (archive, "the archive")):
        for widget in ("_refine_cb", "_m_refine_cb", "_resume_cb", "_m_resume_cb"):
            assert widget not in src, (
                f"{name} re-implements the resume test via {widget} instead of "
                "asking for it; that is how the two came apart in the first place")


def test_the_start_path_archives_after_asking():
    """Order matters: asked first, then moved — and only when it is really a
    replacement."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    assert "_confirm_replacing_measurement" in src
    assert "_archive_measurement_before_replacing" in src
    assert (src.index("_confirm_replacing_measurement")
            < src.index("_archive_measurement_before_replacing"))


# ---- the refine-strips row is all-or-nothing -----------------------------
def test_the_refine_row_never_shows_an_empty_space(tab_and_ti3):
    """Knut, 2026-08-01: *"the 'Refine...' checkbox is an empty space, but its
    help icon is there and present."*

    The row and the checkbox inside it were decided in two different places —
    the row followed the resume tick, the checkbox followed whether a
    measurement exists. Ticking resume while the checkbox was hidden showed a
    row containing nothing but its ⓘ, which is added straight to the layout and
    so was never hidden with it.
    """
    from ui.tooltip_button import TooltipButton
    tab, _ti3, _run = tab_and_ti3
    guided = tab._current_mode() == "guided"
    resume = tab._resume_cb if guided else tab._m_resume_cb
    row = tab._refine_row if guided else tab._m_refine_row
    cb = tab._refine_cb if guided else tab._m_refine_cb

    resume.setChecked(True)
    tab._sync_refine_rows()
    if not row.isHidden():
        assert not cb.isHidden(), "a visible row must show its checkbox"
        for tip in row.findChildren(TooltipButton):
            assert not tip.isHidden()


def test_no_measurement_hides_the_whole_row(tab_and_ti3):
    """The other half of the same fault (#130, 2026-07-30): a lone sub-option
    offering to refine a measurement that does not exist."""
    tab, ti3, _run = tab_and_ti3
    guided = tab._current_mode() == "guided"
    resume = tab._resume_cb if guided else tab._m_resume_cb
    row = tab._refine_row if guided else tab._m_refine_row

    resume.setChecked(True)
    ti3.unlink()
    tab._sync_refine_rows()
    assert row.isHidden(), "no measurement → the whole row goes, ⓘ included"


def test_unticking_resume_takes_the_row_with_it(tab_and_ti3):
    tab, _ti3, _run = tab_and_ti3
    guided = tab._current_mode() == "guided"
    resume = tab._resume_cb if guided else tab._m_resume_cb
    row = tab._refine_row if guided else tab._m_refine_row

    resume.setChecked(True)
    tab._sync_refine_rows()
    resume.setChecked(False)
    tab._sync_refine_rows()
    assert row.isHidden()


# ---- the offer window and the options panel must agree -------------------
# Knut, beta.128, after copying a measurement back from old/ and re-entering
# the tab, with "This chart already has a measurement" answered:
#
#   resume OFF → *"the measure tab options area is missing the 'Refine / Resume
#   ...' checkbox, although the ti3 file is present."*
#   resume ON  → *"the measure tab options area is missing the 'Refine / Resume
#   ...' checkbox (but the 'Use refinement strips file for guided
#   re-measurement' is visible)."*
#
# The window applied the user's choice to controls whose visibility had last
# been decided when the chart was loaded — before the file came back. Ticking a
# hidden box then let the sub-option appear underneath nothing.
def _answer_offer(tab, monkeypatch, *, resume: bool, overlay: bool = False):
    """Drive the real window and press OK with those two boxes set."""
    from PyQt6.QtWidgets import QCheckBox, QDialog

    def _exec(self):
        boxes = self.findChildren(QCheckBox)
        # The window's own two: "show as overlay" and "refine / resume".
        for cb in boxes:
            text = cb.text().lower()
            if "overlay" in text:
                cb.setChecked(overlay)
            elif "refine" in text or "resume" in text:
                cb.setChecked(resume)
        return int(QDialog.DialogCode.Accepted)

    monkeypatch.setattr(QDialog, "exec", _exec)
    tab._maybe_offer_existing_overlay()


@pytest.mark.parametrize("resume", [True, False])
def test_the_offer_leaves_the_resume_box_on_screen(tab_and_ti3, monkeypatch,
                                                   resume):
    tab, _ti3, _run = tab_and_ti3
    guided = tab._current_mode() == "guided"
    box = tab._resume_cb if guided else tab._m_resume_cb
    # The state the bug needed: the file is there, the control is not, because
    # visibility was last decided while the measurement was elsewhere.
    box.setVisible(False)

    _answer_offer(tab, monkeypatch, resume=resume)

    assert not box.isHidden(), \
        "the measurement is on disk, so its option must be on screen"
    assert box.isChecked() is resume


def test_the_sub_option_never_outlives_its_parent(tab_and_ti3, monkeypatch):
    """His second case exactly: refine visible, resume not."""
    tab, _ti3, _run = tab_and_ti3
    guided = tab._current_mode() == "guided"
    box = tab._resume_cb if guided else tab._m_resume_cb
    row = tab._refine_row if guided else tab._m_refine_row
    box.setVisible(False)

    _answer_offer(tab, monkeypatch, resume=True)

    if not row.isHidden():
        assert not box.isHidden(), \
            "the refinement row is showing under a resume box that is not there"
