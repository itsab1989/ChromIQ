"""The Check & Refine result window shows every line it holds (Basti, 2026-10-03).

On Knut's run2 at a ΔE 3.0 threshold the "Profile Quality Assessment" window
cut the strip and patch lists off after two lines (no scroll bar), ran the
row of 17 flagged strips off its right edge, and clipped the "Listed in
measurement order" sentence at the bottom. The same on 4.3.3-beta.5. The lists
were rich text in a ``<pre>`` inside word-wrapped labels; they are now plain
monospace labels and the flagged strips a grid that goes on row after row.

Proved here the way the screen shows it: every visible label in the window,
at its default size and at its minimum size, in English and German, is at
least as large as the label says it needs, and lies inside the window.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import i18n                                       # noqa: E402
from workflow.profcheck_runner import ProfcheckResult       # noqa: E402


def _result(n_strips: int = 24) -> ProfcheckResult:
    letters = [chr(ord("A") + i) for i in range(n_strips)]
    errs = []
    for k, s in enumerate(letters):
        for row in range(1, 28):
            errs.append((f"{s}{row}", 3.0 + 0.1 * (k % 9) if row == 5 else 0.9))
    return ProfcheckResult(avg_de=1.09, peak_de=5.32, patch_errors=errs,
                           raw_log="profcheck output")


def _window(qapp, tmp_path, monkeypatch, *, start_over: bool, n_flag: int):
    from PyQt6.QtWidgets import QDialog
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_check_refine import TabCheckRefine
    from workflow.profcheck_runner import group_by_strip, strips_to_refine
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "work"))
    tab = TabCheckRefine(ArgyllRunner(s), s)
    tab._icc_path = tmp_path / "test.icc"          # the pre-conditioning text too
    tab._threshold_spin.setValue(3.0)
    res = _result()
    refine = strips_to_refine(res.patch_errors, threshold=3.0)[:n_flag]
    seen = []

    def _exec(dlg):
        seen.append(dlg)
        return 0
    monkeypatch.setattr(QDialog, "exec", _exec)
    tab._show_result_dialog(res, group_by_strip(res.patch_errors), refine,
                            tmp_path / "Refine_Strips_1_test.txt", start_over,
                            len(refine), 24, len(refine), 648)
    return tab, seen[0]


def _clipped(dlg) -> list[str]:
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QApplication, QLabel
    for _ in range(3):
        QApplication.processEvents()
    inside = QRect(0, 0, dlg.width(), dlg.height())
    bad = []
    for lbl in dlg.findChildren(QLabel):
        if not lbl.isVisible() or not lbl.text().strip():
            continue
        if lbl.wordWrap():
            need_w = 0
            need_h = lbl.heightForWidth(lbl.width())
        else:
            need_w = lbl.sizeHint().width()
            need_h = lbl.sizeHint().height()
        top_left = lbl.mapTo(dlg, lbl.rect().topLeft())
        rect = QRect(top_left, lbl.size())
        if lbl.height() < need_h or lbl.width() < need_w \
                or not inside.contains(rect):
            bad.append(f"{lbl.text()[:60]!r}: {lbl.width()}x{lbl.height()} "
                       f"needs {need_w}x{need_h}, at {rect.getRect()} in "
                       f"{dlg.width()}x{dlg.height()}")
    # The buttons: each at least its own minimum, inside, and none over another
    # (German at the old 640 px floor drew them over each other).
    from PyQt6.QtWidgets import QPushButton
    rects = []
    for b in dlg.findChildren(QPushButton):
        if not b.isVisible():
            continue
        rect = QRect(b.mapTo(dlg, b.rect().topLeft()), b.size())
        if b.width() < b.minimumSizeHint().width() or not inside.contains(rect):
            bad.append(f"button {b.text()!r}: {b.width()} wide, needs "
                       f"{b.minimumSizeHint().width()}, at {rect.getRect()}")
        for other_text, other in rects:
            if rect.intersects(other):
                bad.append(f"button {b.text()!r} overlaps {other_text!r}")
        rects.append((b.text(), rect))
    return bad


@pytest.fixture(params=["en", "de"])
def language(request):
    i18n.set_language(request.param)
    try:
        yield request.param
    finally:
        i18n.set_language("en")


@pytest.mark.parametrize("start_over, n_flag", [
    (False, 17),    # Knut's run2 at 3.0: the refine list
    (False, 1),     # one flagged strip
    (True, 24),     # run2 at 2.0: start over
])
def test_every_label_is_whole_at_default_and_minimum_size(
        qapp, tmp_path, monkeypatch, language, start_over, n_flag):
    _tab, dlg = _window(qapp, tmp_path, monkeypatch,
                        start_over=start_over, n_flag=n_flag)
    try:
        dlg.show()
        assert _clipped(dlg) == [], "default size"
        dlg.resize(dlg.minimumSize())
        assert _clipped(dlg) == [], "minimum size"
    finally:
        dlg.close()
        dlg.deleteLater()


def test_the_window_is_not_stretched_by_one_long_line(qapp, tmp_path,
                                                      monkeypatch):
    """The flagged strips wrap into rows instead of widening the window."""
    _tab, dlg = _window(qapp, tmp_path, monkeypatch,
                        start_over=False, n_flag=17)
    try:
        dlg.show()
        assert dlg.minimumSizeHint().width() < 1000
    finally:
        dlg.close()
        dlg.deleteLater()


def test_the_refine_heading_and_order_sentence_are_german(
        qapp, tmp_path, monkeypatch):
    """The heading's key carries a narrow no-break space (U+202F) before the
    limit; a rewrite with a plain space left the heading English."""
    from PyQt6.QtWidgets import QLabel
    i18n.set_language("de")
    try:
        _tab, dlg = _window(qapp, tmp_path, monkeypatch,
                            start_over=False, n_flag=17)
        text = "\n".join(lbl.text() for lbl in dlg.findChildren(QLabel))
        dlg.deleteLater()
    finally:
        i18n.set_language("en")
    assert "17 Streifen haben mindestens ein Messfeld" in text
    assert "In Messreihenfolge aufgelistet: Die App" in text
    assert "strips have at least one patch" not in text


def test_the_lists_are_never_rich_text_in_a_pre_again():
    import inspect
    from ui.tabs.tab_check_refine import TabCheckRefine
    src = inspect.getsource(TabCheckRefine._show_result_dialog)
    assert "<pre>" not in src
