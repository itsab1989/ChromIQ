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

from ui.dialogs.update_dialog import UpdateAvailableDialog

#: Short, ordinary, and long enough to push the body onto another line. The
#: third is what a build-metadata version looks like, and it is the case that
#: reproduced the fault.
VERSIONS = [
    "v9.9.9",
    "v4.3.0-beta.32",
    "v4.3.0-beta.32-rc1+build.20260922.arm64",
]


@pytest.mark.parametrize("latest", VERSIONS)
def test_the_window_cannot_be_shorter_than_the_text_it_holds(qapp, latest):
    """MUTATION: delete the `setMinimumHeight(self.sizeHint().height())` line
    from `ui/dialogs/update_dialog.py` and the long-version case goes red at
    262 against 310, with the two shorter ones red at 262 against 294.
    """
    dlg = UpdateAvailableDialog(latest, None)
    try:
        dlg.show()
        qapp.processEvents()
        need = dlg.sizeHint().height()
        floor = dlg.minimumHeight()
        assert floor >= need, (
            f"the update window needs {need} px to show its text and can be "
            f"dragged down to {floor}, so the text is cut and the user has to "
            f"resize the window to read it"
        )
    finally:
        dlg.close()
        dlg.deleteLater()


def test_a_longer_version_string_raises_the_floor(qapp):
    """The floor must FOLLOW the content, not be one number for every case.

    A fixed floor that happened to be tall enough today would satisfy the test
    above and break again the moment a version string grew, which is the fault
    being fixed. So the long case must ask for more than the short one.
    """
    short = UpdateAvailableDialog(VERSIONS[0], None)
    long_ = UpdateAvailableDialog(VERSIONS[-1], None)
    try:
        for d in (short, long_):
            d.show()
        qapp.processEvents()
        assert long_.minimumHeight() > short.minimumHeight(), (
            f"the floor is {short.minimumHeight()} px for a short version and "
            f"{long_.minimumHeight()} for one that wraps onto another line; it "
            f"is not following the content"
        )
    finally:
        for d in (short, long_):
            d.close(); d.deleteLater()
