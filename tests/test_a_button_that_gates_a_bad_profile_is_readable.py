"""The buttons that let someone go ahead anyway must be readable.

Knut, #130 2026-07-28: *"The button Delete Run 4 Permanently has its text cut on
both sides. Again, all windows created must follow the universal rules created
to prevent this happening."* `ui.widgets.fit_message_box_buttons` IS that rule.
It was written then, and by beta 8 three of the windows that matter most were
not calling it.

Measured with the shipped stylesheet, whose `padding: 6px 18px` adds 36 px to
every button's width hint while QMessageBox sizes itself from its TEXT and then
squeezes whatever is left:

    "Build anyway"            wants 132 px, granted 126  ->  "uild anywa"
    "Install Profile Anyway"  wants 210 px, granted 126  ->  "nstall Profile A"

Those two are exactly the buttons a person presses to build or install a profile
ChromIQ has just warned them about. A warning whose "go ahead anyway" button is
unreadable is worse than no warning: it makes the app look broken at the moment
it is trying to be trusted.

This is a BEHAVIOURAL check on real widgets rather than a search for the call,
so a different way of solving it still passes — and a stylesheet change that
re-breaks it fails here rather than in somebody's screenshot.
"""
import pytest
from PyQt6.QtWidgets import QMessageBox

from ui.styles import APP_STYLESHEET
from ui.widgets import fit_message_box_buttons

#: Every label in the app long enough to be at risk, with the shortest one it is
#: shown beside — a short partner is the bad case, because the box takes its
#: width from the text and gives the row no reason to grow.
_PAIRS = [
    ("Build anyway", "Cancel"),
    ("Install Profile Anyway", "Stop"),
    ("Build profile anyway", "Stop"),
    ("Delete Run 4 Permanently", "Cancel"),   # Knut's original, #130
]


def _row(_qapp, long_label, short_label, fit):
    box = QMessageBox()
    # The stylesheet goes on the BOX, never on the application. CLAUDE.md:
    # "Never call qapp.setStyleSheet() in a test. It re-polishes every widget
    # the suite has alive — two tests that took 0.2 s alone cost 29 s inside a
    # full run." A box styled directly measures the same widths and leaves the
    # rest of the suite alone.
    box.setStyleSheet(APP_STYLESHEET)
    box.setText("A short message.")          # short on purpose: the bad case
    a = box.addButton(long_label, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(short_label, QMessageBox.ButtonRole.RejectRole)
    if fit:
        fit_message_box_buttons(box)
    box.show()
    _qapp.processEvents()
    got, want = a.width(), a.sizeHint().width()
    box.close()
    return got, want


@pytest.mark.parametrize("long_label,short_label", _PAIRS)
def test_the_rule_makes_a_long_label_fit(qapp, long_label, short_label):
    got, want = _row(qapp, long_label, short_label, fit=True)
    assert got >= want, (
        f"“{long_label}” is granted {got} px and needs {want} — it will be "
        f"painted with its ends cut off. Call "
        f"ui.widgets.fit_message_box_buttons(box) after the last addButton.")


def test_without_the_rule_the_label_really_is_cut(qapp):
    """The guard must be guarding something. If this ever stops failing, either
    the stylesheet's button padding changed or QMessageBox did — and this file's
    numbers need re-measuring rather than trusting."""
    got, want = _row(qapp, "Install Profile Anyway", "Stop", fit=False)
    assert got < want, (
        "a long label now fits without the rule being applied — re-measure the "
        "numbers in this file's docstring before deleting anything")


def test_every_window_that_offers_going_ahead_anyway_applies_it():
    """The three windows this was found missing from, pinned by name so a future
    edit that drops the call is caught here and not by a user."""
    import inspect
    from ui.dialogs import scanin_dialog
    from ui.tabs import tab_profile
    for mod in (scanin_dialog, tab_profile):
        src = inspect.getsource(mod)
        for i, chunk in enumerate(src.split('addButton(tr("Build anyway")')[1:]):
            head = chunk[:600]
            assert "fit_message_box_buttons(box)" in head, (
                f"{mod.__name__}: the “Build anyway” box at occurrence {i + 1} "
                f"does not fit its buttons before showing")
