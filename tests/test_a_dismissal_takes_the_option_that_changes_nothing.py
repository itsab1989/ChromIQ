"""R23-F4 (B8-389). Closing "Wrong Strip Read" must not FILE the bad reading.

`unified_measurement_management.md` already rules on what dismissing a window
means, in two places and on three windows:

    "Skipping a calibration step is a positive decision and keeps its own
     button. **Dismissing a window is a withdrawal**"

    "`clickedButton()` is None for the red traffic light, the Windows X and Esc
     alike, and **ending is the consequential act, so a dismissal takes the
     option that changes nothing**"

**Wrong Strip Read** and **Unexpected Colour Response** did the opposite. Both
build their window with a default `chosen`, and that value is read only when no
button was pressed -- the title-bar X, the red traffic light, Escape. It was
``"\\r"``, which at these prompts is **Use Anyway**. So the two windows whose
whole job is to say *this reading is probably wrong* filed the suspect reading
under the expected strip's name the moment the user closed them, with no
confirmation and nothing in the window warning anybody.

On these windows the consequential act is FILING the reading. Retry files
nothing and ends nothing -- Knut called Retry here *"the same thing as 'Keep
measuring'"* (`measurement_exit_strategy.md` note 1) -- so a dismissal is
Retry, ``" "``. `measurement_exit_strategy.md` note 8b.

**The control is in this file.** "Strip Read Interrupted" was already right at
``"\\r"`` (Resume, which files nothing) and is untouched, so a guard that
merely refused ``"\\r"`` everywhere would be wrong. It is asserted as ``b"\\r"``.

Measured where it matters: the byte at the far end of a real pty, written by
the real `ArgyllRunner` out of a session whose child process is really alive --
without which `_send_failure_choice` early-returns and nothing is sent at all.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from tests.helpers.live_reader import WindowDriver, measuring   # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


#: The title-bar X. `QDialog::closeEvent` answers it with `reject()`, which is
#: also what the red traffic light and Escape do -- one gesture, three routes.
def _the_title_bar_x(w):
    w.close()


def _dismiss(tab, reader, raise_the_window) -> tuple:
    """Raise one of the real windows, close it with the X, read the far end."""
    reader.forget()
    driver = WindowDriver(_the_title_bar_x).arm()
    raise_the_window()
    driver.disarm()
    return driver, reader.wait_for_a_byte()


# ---- the two windows that were wrong -------------------------------------
def test_dismissing_wrong_strip_read_retries_rather_than_filing_it(
        qapp, tmp_path):
    with measuring(tmp_path) as (tab, reader):
        driver, sent = _dismiss(
            tab, reader, lambda: tab._manager.wrong_strip.emit("C", "B"))

        assert driver.acted_on == "Wrong Strip Read", \
            f"the window that opened was {driver.acted_on!r}"
        assert driver.stuck is False, "the window did not answer its own X"
        assert sent == b" ", (
            "closing \"Wrong Strip Read\" sent Use Anyway, so the reading the "
            "window had just called suspect was filed under strip B -- with no "
            "confirmation and nothing in the window saying so. A dismissal "
            "takes the option that changes nothing, which here is Retry")


def test_dismissing_unexpected_colour_response_retries_too(qapp, tmp_path):
    with measuring(tmp_path) as (tab, reader):
        driver, sent = _dismiss(
            tab, reader, lambda: tab._manager.unexpected_response.emit("4.8"))

        assert driver.acted_on == "Unexpected Colour Response", \
            f"the window that opened was {driver.acted_on!r}"
        assert driver.stuck is False, "the window did not answer its own X"
        assert sent == b" ", (
            "closing \"Unexpected Colour Response\" accepted a reading it had "
            "just reported as ΔE 4.8 from what was expected")


# ---- the control, which was already right and must stay as it is ----------
def test_dismissing_strip_read_interrupted_still_resumes(qapp, tmp_path):
    """THE CONTROL. Resume files nothing and ends nothing, so it was already
    the option that changes nothing -- and it is still `\\r`.

    Without this, a guard demanding `b" "` from every window would "fix" a
    window that was never wrong, and would pass while doing it.
    """
    with measuring(tmp_path) as (tab, reader):
        driver, sent = _dismiss(
            tab, reader, lambda: tab._manager.strip_interrupted.emit())

        assert driver.acted_on == "Strip Read Interrupted", \
            f"the window that opened was {driver.acted_on!r}"
        assert sent == b"\r", (
            "the control window changed. Resume was already the harmless "
            "option here; only the two windows that FILED a reading were wrong")


# ---- and the reading really is refused, not merely re-keyed ---------------
def test_a_dismissal_never_ends_the_session(qapp, tmp_path):
    """Retry ends nothing. If a dismissal ever started ending the session, the
    window would have become a third exit -- which is what
    `measurement_exit_strategy.md` exists to catch."""
    with measuring(tmp_path) as (tab, reader):
        _driver, _sent = _dismiss(
            tab, reader, lambda: tab._manager.wrong_strip.emit("C", "B"))
        assert tab._runner.is_running is True
        assert tab._manager.ended_by_the_user is False, \
            "dismissing a misread window marked the session as ended"
