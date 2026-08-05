"""#130 — archiving a measurement and then resuming it is a contradiction.

Knut, beta.144: *"Critical error: Not possible to do any measurement. After
Pressing Start Measurement only 'Steps in each...' and 'Passes in each...' is
shown in the log window. No sound, no initiation of instrument (it seems)."*

His log, the same five times over::

    archived Test-Profiling-P.ti3 (76 readings) to 2026-08-05_215226 before measuring
    chromiq-chartread --json --safenet -v -c 1 -p -r -T 0.7 …
    {"event":"session_start", …, "strips":[{"strip":"A", …,"read":true}, …]}
    ArgyllRunner: process killed

The archive **copies** rather than moves (``measurement_session.py``), so the
old readings are still there when the reader opens the chart; ``-r`` then
resumes against them, finds every strip accounted for, and the session is over
before the instrument is ever opened. That is why there was no sound and no
device initialisation — nothing got that far.

**The cause is two different tests for one question.** ``params.resume`` is
``resume_cb.isChecked()``, while the guard that decides whether to archive
also required ``resume_cb.isVisible()`` — and ``isVisible()`` is False whenever
any ancestor is hidden, which is a Qt trap this codebase has been caught by
before. Checked-but-not-visible therefore meant "resume" to the command line
and "replace" to the archive step, which is precisely the combination that
cannot work.

Not a beta.144 regression: nothing in the measurement path changed between
beta.143 and beta.144. It is older, and it needed this combination to surface.
"""
from __future__ import annotations

import inspect

import pytest


def test_the_two_sides_ask_the_same_question():
    """The guard and the command line must agree about what a resume is.

    Asserted on the source because the failure is a DISAGREEMENT between two
    places: a behavioural test can only ever exercise one of them at a time,
    and would pass while they still disagreed in the state Knut hit.
    """
    from ui.tabs.tab_measure import TabMeasure

    guard = inspect.getsource(TabMeasure._read_builds_on_existing)
    # Comments explain the trap and must be allowed to name it; only the CODE
    # is scanned, or the explanation would trip its own test.
    code = "\n".join(line.split("#", 1)[0] for line in guard.splitlines())
    code = code.split('"""')[-1]                 # drop the docstring too
    assert "isVisible()" not in code, (
        "the archive guard tests isVisible(), which is False whenever an "
        "ancestor is hidden — so a CHECKED resume box reads as 'not resuming' "
        "and the measurement is archived while -r is still passed. That is "
        "Knut's beta.144 session: archived, resumed, dead on arrival."
    )


def test_the_guard_still_recognises_a_ticked_resume(qapp):
    """…and it must still say yes when the box is ticked, whatever Qt thinks
    about the visibility of a tab that is not current."""
    from PyQt6.QtWidgets import QCheckBox, QWidget

    from ui.tabs.tab_measure import TabMeasure

    class _Stub:
        _current_mode = staticmethod(lambda: "manual")

    hidden_parent = QWidget()               # never shown: children are !isVisible
    stub = _Stub()
    stub._m_resume_cb = QCheckBox("resume", hidden_parent)
    stub._m_refine_cb = QCheckBox("refine", hidden_parent)
    stub._resume_cb = None
    stub._refine_cb = None
    stub._m_resume_cb.setChecked(True)

    assert not stub._m_resume_cb.isVisible(), "the premise: Qt calls it hidden"
    assert TabMeasure._read_builds_on_existing(stub) is True, (
        "a ticked resume box was read as 'not resuming' because its parent is "
        "not on screen — the measurement would be archived and then resumed"
    )


def test_a_resume_never_archives_the_file_it_resumes_from(qapp):
    """The rule in one line, since the two tests above are about how it is
    decided rather than what it means."""
    from ui.tabs.tab_measure import TabMeasure

    archive = inspect.getsource(TabMeasure._archive_measurement_before_replacing)
    assert "_read_builds_on_existing" in archive, (
        "the archive step no longer consults whether this read builds on the "
        "existing measurement; archiving the file a resume reads from kills "
        "the session"
    )
