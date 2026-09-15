"""The only two sentences that name where a person's history went were erased
milliseconds after being written.

Found by the combined adversary round of 2026-09-16 (B8-219), enumerating the
"an ending that leaves state behind" shape on doors no combined round had
looked at.

"Build here anyway" on M-PROFILE-VERIFY runs `_archive_superseded_profile`,
which MOVES the run's built profile into ``runs/runN/old/<timestamp>/`` and
EVERY dated verification measurement into ``verifications/old/<timestamp>/``,
and writes the two lines that name those exact folders into the Build Profile
tab's log. `_on_build` then called ``self._log.clear()`` seven lines later.

WHAT A PERSON SAW, driven on screen in a real window on a real project holding a
real profile and two real dated verification measurements (combined round 7,
``E-result.json``, ``E1-the-question-that-archives-them.png``): after "Build
here anyway", ``old/2026-09-16_000225/Demo-Switching.icc`` and
``verifications/old/2026-09-16_000225/`` with both dated folders inside it, and
a log holding colprof's output and nothing else. The clear was watched at the
instant it fired and it held exactly those two lines.

GRADED HONESTLY: the window above already names ``old/`` and the ``old`` folder
inside ``verifications``, so nobody is stranded and nothing is lost. What is
lost is the TIMESTAMPED folder -- the one thing that says which archive is
theirs when a run has several.

`ui/tabs/tab_measure.py::_on_start` records the same fault and the same fix in
its own words, about the calibration messages: they were *"erased milliseconds
after being written… None of it had ever been seen by anybody."*
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


def _src():
    from ui.tabs.tab_profile import TabProfile
    return inspect.getsource(TabProfile._on_build)


def _code() -> str:
    """`_on_build`'s CODE, with its docstring and every `#` comment removed.

    The first version of these tests indexed the raw source and went red on a
    correct tree: the comment explaining this very fix names
    `_confirm_rebuild_over_verifications` in prose, above the clear, so
    `str.index` found the sentence instead of the call. A test about the order
    of two statements has to read statements.
    """
    src = _src()
    if '"""' in src:
        src = src.split('"""', 2)[-1]
    return "\n".join(line.split("#", 1)[0]
                      for line in src.splitlines()
                      if not line.lstrip().startswith("#"))


# ---------------------------------------------------------------------------
# the premise: those lines really are written into THIS log
# ---------------------------------------------------------------------------

def test_the_archive_really_names_its_folders_in_the_tabs_log():
    from ui.tabs.tab_profile import TabProfile
    src = inspect.getsource(TabProfile._archive_superseded_profile)
    assert "self._log.appendPlainText" in src
    assert "The previous profile was moved to" in src
    assert "The verification measurements made against it were moved to" in src


def test_the_archive_really_moves_the_profile_and_the_verifications():
    """A record is only worth keeping because something really moved."""
    from ui.tabs.tab_profile import TabProfile
    src = inspect.getsource(TabProfile._archive_superseded_profile)
    assert "archive_to_old" in src
    assert "run.verifications()" in src
    assert "verifications_old_dir" in src


def test_the_question_that_archives_is_asked_from_on_build():
    assert "_confirm_rebuild_over_verifications" in _code()


# ---------------------------------------------------------------------------
# …and the clear cannot be allowed to land on top of them
# ---------------------------------------------------------------------------

def test_the_log_is_cleared_before_the_question_that_archives():
    src = _code()
    assert "self._log.clear()" in src, (
        "a build still starts with a clean log; it is the ORDER that matters")
    assert src.index("self._log.clear()") < src.index(
        "_confirm_rebuild_over_verifications"), (
        "`_archive_superseded_profile` writes the only two lines that ever "
        "name the timestamped archive folders, and a clear below them erases "
        "both before anybody can read one")


def test_the_log_is_cleared_before_every_step_that_writes_into_it():
    """Not only that one question: every guard between the clear and the build
    reports into this log, and each of them is about THIS attempt."""
    src = _code()
    at_clear = src.index("self._log.clear()")
    for later in ("_validate_gamut_source",
                  "_confirm_building_outside_the_selected_run",
                  "_confirm_rebuild_over_verifications",
                  "_apply_preconditioning_merge"):
        assert at_clear < src.index(later), (
            f"{later} runs before the log is cleared, so anything it says is "
            f"erased")


def test_the_log_is_cleared_exactly_once_in_on_build():
    """Two clears would put the second one back on top of the first's output,
    which is the fault re-introduced by the most obvious way of 'keeping' it."""
    assert _code().count("self._log.clear()") == 1


def test_the_first_refusal_still_says_its_piece():
    """"No valid .ti3 file selected" is written BEFORE the clear and returns,
    so it survives - which is what made this ordering safe to change."""
    src = _code()
    assert src.index("No valid .ti3 file selected") < src.index(
        "self._log.clear()")
