"""Saving a help card as a PDF: the crash Knut hit, and the silence behind it.

Two independent faults met in one button (Help ▸ SAVE AS PDF…, 2026-08-27):

1. `ui/widgets.py::save_file_dialog` overwrote its own `parent` argument with a
   `Path`, so the call raised `TypeError` before a file could be chosen. That is
   covered in `tests/test_native_file_dialogs.py`; here we only need the dialog
   to work at all, so it is stubbed.

2. Behind it, `save_card_pdf` returned a path it had never checked. `QPdfWriter`
   does not raise when it cannot open its file: the `QPainter` simply never
   begins, every paint call is a no-op warning nobody sees, and the render still
   reports a page count. So a save into an unwritable folder returned a Path for
   a file that does not exist, and the caller logged "help card saved as …".

These prove both directions — a real PDF where one can be written, and a raised
error where one cannot — because the failure mode here is a SUCCESS that never
happened, and only the negative case can catch it.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _a_card():
    from ui.dialogs.welcome_dialog import WORKFLOWS
    return next(w for w in WORKFLOWS if w["key"] == "first_profile")


def _save_to(monkeypatch, target):
    """Run the real save_card_pdf with the file dialog answering *target*."""
    import ui.widgets as widgets
    from ui import help_card_print

    monkeypatch.setattr(widgets, "save_file_dialog",
                        lambda *a, **k: str(target))
    return help_card_print.save_card_pdf(_a_card(), None, lang="en")


def test_a_writable_path_really_produces_a_pdf(qapp, monkeypatch, tmp_path):
    """The positive control: without it, a function that always raised would
    look like it was catching the fault."""
    out = tmp_path / "card.pdf"
    got = _save_to(monkeypatch, out)
    assert got == out
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_bytes()[:5] == b"%PDF-"


def test_a_path_that_cannot_be_written_raises_instead_of_reporting_success(
        qapp, monkeypatch, tmp_path):
    """The fault itself: no file, no exception, and a success message."""
    missing = tmp_path / "no-such-folder" / "card.pdf"
    with pytest.raises(OSError):
        _save_to(monkeypatch, missing)
    assert not missing.exists()


def test_a_cancelled_dialog_is_not_a_failure(qapp, monkeypatch):
    """Cancel still returns None and must never raise — the caller treats a
    raise as "something went wrong" and shows a window for it."""
    import ui.widgets as widgets
    from ui import help_card_print

    monkeypatch.setattr(widgets, "save_file_dialog", lambda *a, **k: "")
    assert help_card_print.save_card_pdf(_a_card(), None, lang="en") is None


def test_a_typed_name_without_an_extension_still_lands_as_pdf(
        qapp, monkeypatch, tmp_path):
    out = tmp_path / "My card v1.2"
    got = _save_to(monkeypatch, out)
    assert got == tmp_path / "My card v1.2.pdf"
    assert got.exists() and got.read_bytes()[:5] == b"%PDF-"
