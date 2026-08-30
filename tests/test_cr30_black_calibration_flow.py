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

    def __init__(self, parent=None):
        self._buttons: dict = {}
        self._clicked = None

    def __getattr__(self, name):
        return lambda *a, **k: None

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
    its own button."""
    window.choose = None                      # the red traffic light / X / Esc
    tab = _Tab()
    assert tab._run_cr30_black_calibration() is False, (
        "closing the window let the measurement go ahead anyway")
    assert not tab.did_calibrate


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


def test_a_failed_black_calibration_does_not_stop_the_measurement_either():
    src = inspect.getsource(TabMeasure._do_black_calibration)
    i = src.index('"error" in result')
    assert "return True" in src[i:i + 2000]


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
    assert "not the same as verified" in shown, (
        "the healthy-looking case must say plainly what it is NOT — 'nothing "
        "wrong was seen' is not 'we checked it'")


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
