"""The update popup may not open too short to read.

Knut, 2026-09-22, against a running build: *"Sometime the window opens too
short in height, making the text being cut, probably depending on the version
information written, but the user then must increase the height of the window
to show the content. The window should always show all text, and not keep the
window fixed and push the text into a frame that is partly not shown on
screen."*

**A WORD-WRAPPED `QLabel` DOES NOT REPORT THE HEIGHT IT NEEDS.** Its
`minimumSizeHint` comes from its own minimum content rather than from the
height the text occupies at the width the dialog gives it, so the dialog's
minimum stayed put while its `sizeHint` grew with the body. Measured on
screen, English, the only variable being the length of the version string:

    latest                                   sizeHint   minimumSizeHint
    v9.9.9                                     346x294       329x262
    v4.3.0-beta.32-rc1+build.20260922.arm64    346x310       329x262

With the long version the content needs 310 px and nothing stopped the window
being 262, which is Knut's report exactly.

The dialog's width is pinned at 540, so the body can never have to wrap into
more lines than it does at construction: the height asked for here is the
height it will need.
"""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication

from ui.dialogs.update_dialog import UpdateAvailableDialog


@pytest.fixture()
def dialog(qapp):
    """Build update dialogs and DESTROY them, not merely hide them.

    **`close()` AND `deleteLater()` ARE NOT ENOUGH ON THEIR OWN.** A deferred
    delete only happens when an event loop runs, so a dialog closed at the end
    of a test can still be a live top-level widget while the next test runs.
    `tests/conftest.py::_no_modal_may_hang_the_suite` sweeps every top-level
    widget on a timer and blames whichever test is running when it fires, so a
    survivor from here is reported against a stranger: the first gate run after
    this file was added failed in
    `test_update_check_survives_the_hourly_quota.py`, a file that opens no
    dialog at all, naming this dialog's title.

    Twelve gate runs before this file existed had none. That is not proof this
    file caused it, and it was not reproducible in isolation over five runs,
    but it is enough to make sure nothing built here can outlive the test that
    built it.
    """
    made: list = []

    def _make(latest: str) -> UpdateAvailableDialog:
        d = UpdateAvailableDialog(latest, None)
        made.append(d)
        return d

    yield _make

    for d in made:
        d.close()
        d.setParent(None)
        d.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    alive = [w for w in QApplication.topLevelWidgets()
             if isinstance(w, UpdateAvailableDialog)]
    assert not alive, (
        f"{len(alive)} update dialog(s) survived this test and would be swept "
        f"by the modal guard during somebody else's"
    )

#: Short, ordinary, and long enough to push the body onto another line. The
#: third is what a build-metadata version looks like, and it is the case that
#: reproduced the fault.
VERSIONS = [
    "v9.9.9",
    "v4.3.0-beta.32",
    "v4.3.0-beta.32-rc1+build.20260922.arm64",
]


@pytest.mark.parametrize("latest", VERSIONS)
def test_the_window_cannot_be_shorter_than_the_text_it_holds(qapp, dialog,
                                                           latest):
    """MUTATION: delete the `setMinimumHeight(self.sizeHint().height())` line
    from `ui/dialogs/update_dialog.py` and the long-version case goes red at
    262 against 310, with the two shorter ones red at 262 against 294.
    """
    dlg = dialog(latest)
    dlg.show()
    qapp.processEvents()
    need = dlg.sizeHint().height()
    floor = dlg.minimumHeight()
    assert floor >= need, (
        f"the update window needs {need} px to show its text and can be "
        f"dragged down to {floor}, so the text is cut and the user has to "
        f"resize the window to read it"
    )


def test_a_longer_version_string_raises_the_floor(qapp, dialog):
    """The floor must FOLLOW the content, not be one number for every case.

    A fixed floor that happened to be tall enough today would satisfy the test
    above and break again the moment a version string grew, which is the fault
    being fixed. So the long case must ask for more than the short one.
    """
    short = dialog(VERSIONS[0])
    long_ = dialog(VERSIONS[-1])
    for d in (short, long_):
        d.show()
    qapp.processEvents()
    assert long_.minimumHeight() > short.minimumHeight(), (
        f"the floor is {short.minimumHeight()} px for a short version and "
        f"{long_.minimumHeight()} for one that wraps onto another line; it "
        f"is not following the content"
    )


@pytest.mark.parametrize("code", ["en", "de", "uk", "ja"])
def test_the_window_cannot_be_dragged_narrower_than_it_was_measured(qapp, dialog,
                                                                    code):
    """A height measured at one width is only a floor AT that width.

    `setMinimumWidth(540)` is a MINIMUM and not a pin: the button row makes
    the window open wider than 540 in nine of the fourteen languages, and a
    user could still drag it back to 540. The body then wraps into more lines
    than the height was measured for, and Knut's fault returns.

    Measured by challenge round 38, dragging each window to the width it still
    allowed: German needs 80 px of body and has 64, so 16 px of text is cut,
    and the same in Norwegian, Ukrainian and Japanese.

    MUTATION: put back `setMinimumHeight(self.sizeHint().height())` on its own,
    without the width, and this goes red for every language that opens wider
    than 540.
    """
    from core import i18n
    i18n.set_language(code)
    try:
        dlg = dialog("v4.3.0-beta.32-rc1+build.20260922.arm64")
        dlg.show()
        qapp.processEvents()
        assert dlg.minimumWidth() >= dlg.sizeHint().width(), (
            f"[{code}] the window lays out at {dlg.sizeHint().width()} px wide "
            f"but can be dragged to {dlg.minimumWidth()}, where its text needs "
            f"more lines than the height it was given"
        )
    finally:
        i18n.set_language("en")
