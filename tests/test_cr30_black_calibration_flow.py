"""#159: the black calibration, and the rules it must not break.

Offered by an unticked checkbox inside the white-calibration window — per use,
deliberately not remembered. A remembered tick would turn "occasionally, on
purpose" into a second window and a device write on every Start of that target
for ever, which is exactly the two-pop-ups-every-time outcome the owner did not
want.

The step asks for the OPPOSITE of the one before it (cap off, pointing at
nothing), so both windows carry the same pair-of-steps picture with the current
step marked. And there is no black tile anywhere in it: this instrument has
none, its dark reference is open air, and the nearest dark thing to hand is the
cap's green face — the surface that silently ruined its white reference during
the research.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                    # noqa: E402

from PyQt6.QtWidgets import QApplication, QWidget                # noqa: E402

from ui.tabs.tab_measure import TabMeasure                       # noqa: E402
from workflow import measurement_messages as M                   # noqa: E402


@pytest.fixture(autouse=True)
def _app():
    QApplication.instance() or QApplication([])


def test_the_offer_is_per_use_and_never_remembered():
    src = inspect.getsource(TabMeasure._calibrate_and_confirm)
    assert "setCheckBox" in src, "the black step is not offered at all"
    assert "settings" not in src.split("setCheckBox")[1][:400].lower(), (
        "the checkbox state is being persisted — a remembered tick makes this "
        "a second window on every Start of the target, for ever")


# ---- the three ways out of the black-calibration window -----------------
#
# THIS USED TO BE A SOURCE SEARCH for the string "clickedButton() is not go",
# asserting a `return True` appeared near it. It passed for years and could not
# have caught what the owner found on 2026-08-30: that same condition was
# reached by CLOSING the window, so the red traffic light was read as "skip"
# and the measurement went ahead —
#
#   *"if i close them via the red traffic light button chromiq gives me the
#    next window anyway and allows me to go into the measurement"*
#
# A test that reads code cannot tell those two apart. These run the method.

class _Box:
    """Stands in for the window, and presses one of its own buttons.

    `choose = None` is the important case: it is what Qt reports for the red
    traffic light, the Windows X and Esc alike — measured, not assumed.
    """

    from PyQt6.QtWidgets import QMessageBox as _real
    Icon = _real.Icon
    ButtonRole = _real.ButtonRole
    choose: "str | None" = "Calibrate now"

    shown_texts: list = []

    def __init__(self, parent=None):
        self._buttons: dict = {}
        self._clicked = None

    def __getattr__(self, name):
        return lambda *a, **k: None

    def setText(self, t):
        type(self).shown_texts.append(t)

    def setInformativeText(self, t):
        type(self).shown_texts.append(t)

    def addButton(self, text, role):
        from PyQt6.QtWidgets import QPushButton
        b = QPushButton(text)
        self._buttons[text] = b
        return b

    def exec(self):
        want = type(self).choose
        self._clicked = self._buttons.get(want) if want else None
        if want is not None and self._clicked is None:
            raise AssertionError(
                f"no {want!r} button; the window offered "
                f"{sorted(self._buttons)}")

    def clickedButton(self):
        return self._clicked


class _Log:
    def __init__(self):
        self.lines: list[str] = []

    def appendPlainText(self, t):
        self.lines.append(t)

    def ensureCursorVisible(self):
        pass


class _Tab(QWidget):
    """A QWidget, because the window's pictogram is drawn in the tab's own
    palette and font — the picture is theme-aware by design."""

    _run_cr30_black_calibration = TabMeasure._run_cr30_black_calibration
    # The real one, so the message really does name the button the user can
    # see — "Continue Measurement" when the resume box is ticked.
    _start_button_name = TabMeasure._start_button_name
    _is_lost_link = TabMeasure._is_lost_link
    _LOST_LINK_SIGNS = TabMeasure._LOST_LINK_SIGNS

    def __init__(self):
        super().__init__()
        from PyQt6.QtWidgets import QPushButton
        self._log = _Log()
        self._start_btn = QPushButton("Start Measurement", self)
        self.did_calibrate = False

    def _do_black_calibration(self):
        self.did_calibrate = True
        return True


@pytest.fixture
def window(monkeypatch):
    import PyQt6.QtWidgets as W
    import ui.widgets as widgets
    monkeypatch.setattr(W, "QMessageBox", _Box)
    monkeypatch.setattr(widgets, "fit_message_box_buttons", lambda box: None)
    _Box.choose = "Calibrate now"
    _Box.shown_texts = []
    return _Box


def test_calibrate_now_takes_the_dark_reference(window):
    tab = _Tab()
    assert tab._run_cr30_black_calibration() is True
    assert tab.did_calibrate, "it never asked the instrument to calibrate"


def test_skipping_the_black_step_does_not_stop_the_measurement(window):
    """The white calibration has already happened; the session is usable."""
    window.choose = "Skip this step"
    tab = _Tab()
    assert tab._run_cr30_black_calibration() is True, (
        "declining the dark reference aborts the measurement")
    assert not tab.did_calibrate
    assert any("skipped" in l for l in tab._log.lines), (
        "the skip was silent, so nothing records which dark reference was used")


def test_closing_the_window_cancels_instead_of_skipping(window):
    """The owner's finding. Dismissing a window is a withdrawal, never a
    consent — and skipping a calibration step is a positive decision that has
    its own button.

    ⚠ THE STUB'S `None` IS NOT WHAT QT ACTUALLY DOES. It is kept because the
    branch must be right either way, but on a real window Qt clicks a BUTTON
    for Escape and the close box — see the test below, which is the one that
    would have caught the fault this file first claimed to fix.
    """
    window.choose = None                      # the red traffic light / X / Esc
    tab = _Tab()
    assert tab._run_cr30_black_calibration() is False, (
        "closing the window let the measurement go ahead anyway")
    assert not tab.did_calibrate


def test_escape_really_cancels_on_a_real_window(qapp_or_skip):
    """THE TEST THAT SHOULD HAVE EXISTED FIRST.

    QMessageBox does not report "no button" for Escape. With no escape button
    set it DETECTS one at exec() time and picks the RejectRole button — here
    "Skip this step". So the whole "a dismissal is a withdrawal" branch was
    unreachable, and closing the window skipped the dark reference and walked
    into the measurement: the owner's original report, still true after the fix
    meant to remove it.

    It was measured wrong twice before it was measured right:
      * `box.close()` on a box that was never shown returns None;
      * so does Escape on a box that was only `show()`n.
    Qt does not detect the escape button until `exec()`. Only an exec'd box
    with a real key event tells the truth, so this test uses one.
    """
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QMessageBox
    from ui.widgets import fit_message_box_buttons, order_message_box_buttons

    box = QMessageBox()
    go = box.addButton("Calibrate now", QMessageBox.ButtonRole.AcceptRole)
    skip = box.addButton("Skip this step", QMessageBox.ButtonRole.RejectRole)
    cancel = box.addButton("Cancel the measurement",
                           QMessageBox.ButtonRole.DestructiveRole)
    box.setEscapeButton(cancel)
    fit_message_box_buttons(box)
    order_message_box_buttons(box, [go, skip, cancel])

    QTimer.singleShot(20, lambda: (QTest.keyClick(box, Qt.Key.Key_Escape),
                                   QTimer.singleShot(300, box.reject)))
    box.exec()

    clicked = box.clickedButton()
    assert clicked is cancel, (
        "Escape did not cancel; it clicked "
        f"{clicked.text() if clicked else None!r} — with no escape button set "
        "Qt picks the RejectRole button, which is 'Skip this step'")


def test_the_window_the_app_builds_sets_its_escape_button():
    """And the real window must do it, not only this file's copy of it."""
    import inspect
    src = inspect.getsource(TabMeasure._run_cr30_black_calibration)
    assert "setEscapeButton(cancel)" in src, (
        "Escape falls back to Qt's own choice, which is 'Skip this step'")


def test_there_is_an_explicit_way_to_cancel(window):
    """*"none of the calibration pop ups allow to cancel"* — this one did not."""
    window.choose = "Cancel the measurement"
    tab = _Tab()
    assert tab._run_cr30_black_calibration() is False
    assert not tab.did_calibrate


def test_cancelling_says_so_and_reassures_and_says_what_to_do_next(window):
    """Cancelling before the helper starts costs nothing at all, and the user
    should be told that rather than left to wonder.

    The MEANING is asserted, not one phrasing — an earlier version of this
    pinned the exact sentence "Nothing has been changed" and broke the moment
    the wording was made friendlier, which teaches nobody anything.
    """
    window.choose = None
    tab = _Tab()
    tab._run_cr30_black_calibration()
    said = " ".join(tab._log.lines).lower()

    assert "cancel" in said, "the cancellation was silent"
    assert "nothing" in said and ("changed" in said or "measured" in said), (
        "it does not reassure the user that nothing was lost or altered")
    assert "start measurement" in said, (
        "it does not say how to begin again — a dead end is not friendly")


def test_it_names_the_button_the_user_can_actually_see(window):
    """The Start button reads "Continue Measurement" whenever the resume box is
    ticked, so a message hard-coding "Start Measurement" sends the user looking
    for a button that is not there. Found on screen during review."""
    window.choose = None
    tab = _Tab()
    tab._start_btn.setText("Continue Measurement")
    tab._run_cr30_black_calibration()
    said = " ".join(tab._log.lines)
    assert "Continue Measurement" in said, (
        "the message names a button the user cannot see")
    assert "Start Measurement" not in said


# ---- a refusal and a lost instrument are not the same failure -----------
#
# This was a source search for `return True` near `"error" in result`. It could
# not tell the two cases apart, and the difference matters more than the
# refusal does: on 2026-08-30 the owner's CR30 powered itself off, the
# Bluetooth link dropped between the white calibration and its read-back, and
# ChromIQ told him "the measurement can go ahead" over a dead link — then
# started a session and highlighted patch A3 for an instrument that was not
# there. It also showed him bleak's own sentence, "Service Discovery has not
# been performed yet", as the explanation.

def test_a_refused_black_calibration_does_not_stop_the_measurement():
    """The white calibration still stands and the chart can still be read."""
    tab = _Tab()
    assert tab._is_lost_link("the instrument refused the command") is False


@pytest.mark.parametrize("message", [
    "Service Discovery has not been performed yet",
    "BleakError: Not connected",
    "the peripheral disconnected",
    "No backend with an available connection",
])
def test_a_lost_link_is_recognised_as_one(message):
    assert _Tab()._is_lost_link(message) is True, (
        f"{message!r} was treated as a survivable refusal, so the user would "
        "be told the measurement can go ahead over a dead link")


def test_the_users_words_are_not_the_librarys_words():
    """"Service Discovery has not been performed yet" is bleak talking to
    itself. Shown in a window it explains nothing — and it was shown."""
    plain = TabMeasure._plain_instrument_error(
        "Service Discovery has not been performed yet")
    assert "Service Discovery" not in plain
    assert "connection" in plain.lower() and "lost" in plain.lower()


def test_an_instruments_own_words_are_kept():
    """Only the library's internals are translated. What the INSTRUMENT says
    is evidence, and a report is worth less without it."""
    real = "no usable reply among the only candidate in 200 bytes"
    assert TabMeasure._plain_instrument_error(real) == real


def test_the_zero_check_asks_the_instrument_rather_than_trusting_the_command():
    """The only honest verification either calibration has."""
    src = inspect.getsource(TabMeasure._do_black_calibration)
    assert "read_zero" in src


def _user_facing(method) -> str:
    """Only the strings this method puts ON SCREEN, from `tr(...)` calls.

    Two earlier versions of this got it wrong in the same way. Searching the
    whole source for words like "verified" matched the comments that DENY the
    claim, and the very sentence "that is not the same as verified" which is
    the honest disclaimer we want to REQUIRE. Stripping the docstring by text
    replacement then failed silently. A check that cannot tell an assertion
    from its refutation is not checking anything, so this parses the method and
    takes the literals actually handed to `tr`.
    """
    import ast
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "tr"):
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append(a.value)
                elif isinstance(a, ast.JoinedStr):
                    out.extend(v.value for v in a.values
                               if isinstance(v, ast.Constant))
    return "\n".join(out)


def test_nothing_claims_the_calibration_succeeded():
    """No success signal exists: the reply's bytes fit a result code and fit
    equally well the high byte of a clock that was never set."""
    shown = _user_facing(TabMeasure._do_black_calibration)
    body = M.M_CR30_CALIBRATE_BLACK.body.lower()
    for lie in ("calibration successful", "calibrated successfully",
                "succeeded", "confirmed"):
        assert lie not in shown.lower(), f"the code claims {lie!r}"
        assert lie not in body, f"the window claims {lie!r}"
    # THE MEANING, NOT ONE PHRASING. This pinned the exact words "not the same
    # as verified" and failed when the sentence was made STRONGER — the
    # healthy-case text now names what the check cannot see and why, which is
    # more than the phrase it replaced. Hardware settled that on 2026-08-30: a
    # dark reference taken against white paper read back 0.004 %R and passed,
    # because a dark calibration defines zero and whatever it saw becomes zero.
    low = shown.lower()
    assert "does not" in low or "not the same as verified" in low, (
        "the healthy-looking case must say plainly what it is NOT — 'nothing "
        "wrong was seen' is not 'we checked it'")
    assert "right thing" in low or "verified" in low, (
        "it does not say WHICH doubt remains, so the disclaimer is decoration")


def test_the_window_never_mentions_a_black_tile():
    """There is none. A user sent hunting for one reaches for the cap's green
    face, which is the accident this whole flow exists to prevent."""
    body = M.M_CR30_CALIBRATE_BLACK.body.lower()
    assert "no black tile" in body
    assert "empty air" in body or "pointing at nothing" in body
    assert "place it on" not in body.replace("nothing to place it on", "")


def test_both_windows_show_the_pair_with_the_current_step_marked():
    from ui.cr30_pictograms import BLACK_STEP, WHITE_STEP, steps_pair
    a, b = steps_pair(WHITE_STEP), steps_pair(BLACK_STEP)
    assert not a.isNull() and not b.isNull()
    assert a.toImage() != b.toImage(), (
        "both steps draw the same picture, so the window cannot show which "
        "one the user is on")


def test_the_drawing_follows_the_theme_rather_than_shipping_two_sets():
    """The owner's own point: a black swatch on a dark window is invisible, and
    the dark step is where being unmistakable matters most."""
    src = inspect.getsource(__import__("ui.cr30_pictograms",
                                       fromlist=["_ink"])._ink)
    assert "palette()" in src
    assert "QColor(0, 0, 0)" in src, "no fallback when there is no widget"


def test_it_is_still_awaiting_approval():
    assert M.M_CR30_CALIBRATE_BLACK.approved is False


# ---- a failure has to interrupt, because the log can be hidden ----------
#
# Basti, 2026-08-30, after running the black calibration deliberately wrong and
# finding the verdict nowhere: *"a failure message should be [a pop up] to warn
# the user and let him act accordingly because you can hide the log output as i
# do it and it is not that noticable there anyway"*. He does hide it.

class _WarnTab(QWidget):
    _warn_dark_reference_looks_wrong = (
        TabMeasure._warn_dark_reference_looks_wrong)

    def __init__(self):
        super().__init__()
        self._log = _Log()
        self.retook = 0

    def _do_black_calibration(self):
        self.retook += 1
        return True


def test_a_bad_dark_reference_opens_a_window(window):
    window.choose = "Carry on anyway"
    tab = _WarnTab()
    tab._warn_dark_reference_looks_wrong(2.317)
    assert window.shown_texts, (
        "the only honest check either calibration has reported a problem into "
        "a log panel the user hides")


def test_the_window_names_the_number_and_why_it_matters(window):
    window.choose = "Carry on anyway"
    tab = _WarnTab()
    tab._warn_dark_reference_looks_wrong(2.317)
    said = " ".join(window.shown_texts)
    assert "2.317" in said, "it does not say what was actually read"
    assert "every reading" in said or "shifts them all" in said, (
        "it does not say why a wrong dark reference matters")


def test_taking_it_again_really_recalibrates(window):
    window.choose = "Take it again"
    tab = _WarnTab()
    tab._warn_dark_reference_looks_wrong(2.317)
    assert tab.retook == 1, "the remedy was named but not offered"


def test_carrying_on_is_allowed_and_recorded(window):
    """It is the user's instrument and the user's chart. But the choice goes in
    the log, so a puzzling profile later has something to point at."""
    window.choose = "Carry on anyway"
    tab = _WarnTab()
    assert tab._warn_dark_reference_looks_wrong(2.317) is True
    assert tab.retook == 0
    assert any("at your choice" in l for l in tab._log.lines)


def test_a_healthy_reading_does_not_interrupt():
    """Only failures interrupt. A dark reference that reads as dark is not news
    worth a window."""
    src = inspect.getsource(TabMeasure._do_black_calibration)
    i = src.index("_CR30_ZERO_WARN")
    healthy = src[i:src.index("else:", i)]
    assert "_warn_dark_reference_looks_wrong" not in healthy



def test_the_healthy_note_names_the_circularity_hardware_proved():
    """The specific thing the check cannot see, in the text the user reads.

    Measured on the owner's CR30, 2026-08-30: black-calibrated against WHITE
    PAPER, the read-back came back at 0.00410 %R — inside the 0.05 threshold,
    reported as healthy. A dark calibration DEFINES zero, so whatever the
    instrument was looking at reads as nothing straight afterwards. The check
    is circular for the one mistake it appeared to guard.
    """
    shown = _user_facing(TabMeasure._do_black_calibration).lower()
    assert "defines" in shown or "becomes the new zero" in shown or \
           "reads as nothing" in shown, (
        "the healthy note does not explain WHY a good-looking reading proves "
        "nothing about what the instrument was pointed at")


def test_the_window_says_the_same_thing():
    """The window is where the user is standing when it matters — before the
    step, not after it."""
    body = M.M_CR30_CALIBRATE_BLACK.body.lower()
    assert "cannot check that you pointed it at the right thing" in body
    assert "0.004" in body, (
        "the window claims a limit without the measurement that established "
        "it; a number a user can check beats an assertion they cannot")



@pytest.fixture
def qapp_or_skip():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
