"""No button of a Measurement Report window answers Return (challenge C, C9).

A QPushButton in a QDialog is ``autoDefault`` unless told otherwise, and when
a dialog is shown with no default button Qt makes the first ``autoDefault``
button in the focus chain the default. In the Measurement Report window that
was "Add Profile's Measurements…": Return anywhere in the window (after typing
in a field, in the pulldowns, in the list) opened its file chooser, 10 times
out of 10 on screen. In the Report limits window it was "Reference values…",
and in that window a user types numbers and presses Return.

None of these windows has a button a user expects Return to press: Close is
one click away and every other button starts something (a chooser, a write, a
question). So none is a default, now or later: the call is repeated when the
window is shown, because rows of buttons are built after construction.
"""
from __future__ import annotations


def no_default_button(dialog) -> None:
    """Take ``autoDefault`` and ``default`` off every QPushButton of *dialog*."""
    from PyQt6.QtWidgets import QPushButton
    for b in dialog.findChildren(QPushButton):
        b.setAutoDefault(False)
        b.setDefault(False)
