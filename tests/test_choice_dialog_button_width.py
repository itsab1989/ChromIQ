"""A choice dialog's buttons must fit, whatever the project is called.

Twice in two days the same window clipped its buttons. First because
`ButtonFontFilter` swaps them to Menlo/uppercase at polish, after their size
was decided — fixed with `fit_message_box_buttons`. Then because the fix made
the *window* grow to fit the buttons, and one button carries a project name:
measured offscreen, a 66-character project asked for a 633px button, which with
the other two overflowed the window and clipped every label again.

So the invariant is not "the fit helper is called" but "the buttons fit". These
tests assert on rendered geometry, and the long-name case fails if `_short_name`
is removed.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer                                # noqa: E402
from PyQt6.QtWidgets import QMessageBox                        # noqa: E402

import ui.ti2_loader as ti2_loader                             # noqa: E402
from ui.ti2_loader import _BUTTON_NAME_LIMIT, _short_name      # noqa: E402

_LONG = "Pro300_EpsonPremiumSemigloss_i1Studio_June2026_secondattempt_matte"


def _unleak_exec():
    """Undo a `QMessageBox.exec` patch some earlier test failed to restore.

    `exec` is INHERITED from QDialog, so the common idiom

        real = QMessageBox.exec; QMessageBox.exec = fake; ... ; QMessageBox.exec = real

    does not put things back — it installs a method object directly on
    QMessageBox that no longer binds. Every later `box.exec()` in that worker
    process is then called with no `self` and dies with "first argument of
    unbound method must have type 'QDialog'". Around 77 tests in this suite use
    that idiom, so which file inherits the damage depends purely on how xdist
    happens to schedule them: these tests passed alone, passed under `-n 4`
    alone, and failed twice in the full gate.

    Deleting the class attribute restores the inherited slot. A no-op when
    nothing leaked. Migrating those 77 sites to `monkeypatch.setattr` is the
    real cure and is worth doing as its own piece of work.
    """
    if "exec" in QMessageBox.__dict__:
        del QMessageBox.exec


def _measure(qapp, choices):
    """Open the real dialog, measure it, close it. Returns (window_w, buttons)."""
    _unleak_exec()
    result = {}

    def grab():
        for w in qapp.topLevelWidgets():
            if isinstance(w, QMessageBox) and w.isVisible():
                result["window"] = w.width()
                result["buttons"] = [(b.text(), b.width(), b.sizeHint().width())
                                     for b in w.buttons()]
                w.reject()

    QTimer.singleShot(0, grab)
    ti2_loader._choice_dialog(None, "Title", "", choices)
    assert result, "the dialog never appeared"
    return result["window"], result["buttons"]


def _choices(name):
    return [(f"Open {name}", f"Opens <b>{name}</b> and selects the run.", "open"),
            ("Use as base for a new profile", "Copies it into a new project.", "new")]


def test_no_button_is_narrower_than_its_text(qapp):
    """The original fault: a button laid out before the font swap is too small."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # width >= hint pivots on real text widths
    _, buttons = _measure(qapp, _choices("Knut-Scanner"))
    assert buttons, "no buttons on the dialog"
    for text, width, hint in buttons:
        assert width >= hint, (
            f"{text!r} is {width}px but needs {hint}px — its label is clipped"
        )


def test_a_very_long_project_name_still_fits(qapp):
    """The second fault. Remove `_short_name` and this fails.

    Not a check that the name was shortened — a check that the row of buttons
    fits inside the window it is drawn in, which is the thing the user sees.
    """
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # button/window fit pivots on real text widths
    window, buttons = _measure(qapp, _choices(_short_name(_LONG)))
    total = sum(hint for _t, _w, hint in buttons)
    assert total <= window, (
        f"the buttons need {total}px inside a {window}px window — with a "
        f"{len(_LONG)}-character project name the labels clip"
    )
    for text, width, hint in buttons:
        assert width >= hint, f"{text!r} is clipped ({width}px < {hint}px)"


@pytest.mark.parametrize("name", [
    "P",
    "Knut-Scanner",
    "A" * _BUTTON_NAME_LIMIT,
    "A" * (_BUTTON_NAME_LIMIT + 1),
    _LONG,
])
def test_short_name_never_exceeds_the_limit(name):
    out = _short_name(name)
    assert len(out) <= _BUTTON_NAME_LIMIT
    if len(name) <= _BUTTON_NAME_LIMIT:
        assert out == name, "a name that already fits must not be touched"
    else:
        assert out != name and "…" in out


def test_the_elision_keeps_both_ends():
    """Middle, not right — two projects differing only at the end must differ here.

    ``…_June2026_matte`` against ``…_June2026_gloss`` is the real case: a
    right-elide gives both the same button and the user cannot tell which
    project the dialog is offering to open.
    """
    a = _short_name("Canon-Pro300-EpsonPremiumSemigloss-June2026-matte")
    b = _short_name("Canon-Pro300-EpsonPremiumSemigloss-June2026-gloss")
    assert a != b, "the elision hides the part that distinguishes the projects"
    assert a.startswith("Canon-Pro300") and a.endswith("matte")


def test_both_open_buttons_are_elided():
    """Two call sites build an "Open {name}" button; both must shorten it.

    Structural: the behavioural route is a modal, and a call site that forgot
    the helper would look perfectly correct in isolation.
    """
    import inspect

    src = inspect.getsource(ti2_loader)
    opens = [ln for ln in src.splitlines() if 'tr("Open {name}").format' in ln]
    assert len(opens) >= 2, "the Open-button call sites have moved — update this test"
    for line in opens:
        assert "_short_name(" in line, (
            f"this button can carry an unbounded project name: {line.strip()}"
        )
