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
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core import i18n                                       # noqa: E402
from workflow.profcheck_runner import ProfcheckResult       # noqa: E402


DATA = Path(__file__).parent / "data" / "check_refine"


def _knut(name: str, thr: float):
    """Knut's own check output, and the plan the window shows for it."""
    from workflow.profcheck_runner import _SUMMARY_RE
    from workflow.refine_plan import build_plan, de_name_for, parse_patches
    text = (DATA / name).read_text(encoding="utf-8")
    m = _SUMMARY_RE.search(text)
    res = ProfcheckResult(avg_de=float(m.group(2)), peak_de=float(m.group(1)),
                          raw_log=text)
    return res, build_plan(parse_patches(text), thr, frozenset(),
                           de_name_for(text, "-k"))


def _one_strip():
    from workflow.refine_plan import OVER, RefinePlan, StripAdvice
    res = ProfcheckResult(avg_de=1.09, peak_de=3.4, raw_log="")
    return res, RefinePlan(3.0, 648, 1, 9.0, False, "\u0394E00",
                           rest=[StripAdvice("H", OVER, "H9", 3.4, 1)])


CASES = {
    "run2-3.0": lambda: _knut("knut_run2_profcheck_qc6.txt", 3.0),
    "run2-0.5-start-over": lambda: _knut("knut_run2_profcheck_qc6.txt", 0.5),
    "run3-2.0": lambda: _knut("knut_run3_profcheck.txt", 2.0),
    "one-strip": _one_strip,
}


def _window(qapp, tmp_path, monkeypatch, case: str):
    from PyQt6.QtWidgets import QDialog
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_check_refine import TabCheckRefine
    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "work"))
    tab = TabCheckRefine(ArgyllRunner(s), s)
    tab._icc_path = tmp_path / "test.icc"          # the pre-conditioning text too
    tab._ti3_path = tmp_path / "test.ti3"
    res, plan = CASES[case]()
    seen = []

    def _exec(dlg):
        seen.append(dlg)
        return 0
    monkeypatch.setattr(QDialog, "exec", _exec)
    tab._show_result_dialog(res, plan, tmp_path / "Refine_Strips_1_test.txt")
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


@pytest.mark.parametrize("case", sorted(CASES))
def test_every_label_is_whole_at_default_and_minimum_size(
        qapp, tmp_path, monkeypatch, language, case):
    _tab, dlg = _window(qapp, tmp_path, monkeypatch, case)
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
    """The strips wrap into rows instead of widening the window."""
    _tab, dlg = _window(qapp, tmp_path, monkeypatch, "run2-0.5-start-over")
    try:
        dlg.show()
        assert dlg.minimumSizeHint().width() < 1000
    finally:
        dlg.close()
        dlg.deleteLater()


def test_the_lists_and_the_order_sentence_are_german(
        qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QLabel
    i18n.set_language("de")
    try:
        _tab, dlg = _window(qapp, tmp_path, monkeypatch, "run3-2.0")
        text = "\n".join(lbl.text() for lbl in dlg.findChildren(QLabel))
        dlg.deleteLater()
    finally:
        i18n.set_language("en")
    assert "Re-measure these strips first" not in text
    assert "stands out clearly" not in text
    assert "in chart order" not in text
    assert "\u0394E00" in text


def test_the_lists_are_never_rich_text_in_a_pre_again():
    import inspect
    from ui.tabs.tab_check_refine import TabCheckRefine
    src = inspect.getsource(TabCheckRefine._show_result_dialog)
    assert "<pre>" not in src
