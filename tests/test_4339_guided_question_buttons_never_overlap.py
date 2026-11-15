"""Round-2 review of 4.3.39, MAJOR-1: the Guided question M-GUIDED-SET-PAGES,
with its three buttons, overlapped them (es, pt, nl at full width; 11 of 14
languages on a 1280 laptop). It now uses the shared row layout
(`ui.widgets.arrange_message_box_buttons`), as the loader's choice windows do.

For every language, on this screen and on simulated 1280 x 800 and 1366 x 768
laptops: no two buttons intersect, no label is wider than its button, the
window fits the work area and every button lies inside it; the text explains
the answers in the order the buttons read; Escape and Return are "Do not
generate".
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QRect, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton  # noqa: E402

LANGS = ["en", "de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru",
         "sv", "uk", "zh_CN"]
SCREENS = {"own": None,
           "1280x800": QRect(0, 25, 1280, 775),
           "1366x768": QRect(0, 0, 1366, 728)}
CAPTION = 28
FIXTURE = (Path(__file__).resolve().parent / "fixtures" / "charts"
           / "cm_a4_480p_2pages.ti1")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def tab(qapp, tmp_path_factory):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    tmp = tmp_path_factory.mktemp("guided_rows")
    s = AppSettings()
    s._qs = QSettings(str(tmp / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp / "out"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    t._switch_mode("guided")
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("CM"))
    t._paper_combo.setCurrentIndex(t._paper_combo.findData("A4"))
    t._pages_spin.setValue(6)
    ti1 = tmp / "mine.ti1"
    shutil.copy(FIXTURE, ti1)
    t._preset_ti1_path = ti1
    t._preset_ti1_targen_sig = t._targen_signature()
    t._update_patch_count()
    yield t
    t.deleteLater()


@pytest.fixture
def language():
    from core import i18n
    before = i18n.current_language()
    yield i18n.set_language
    i18n.set_language(before)


def _ask(qapp, tab, monkeypatch, screen, action):
    import ui.widgets as Wd
    if SCREENS[screen] is not None:
        monkeypatch.setattr(Wd, "long_buttons_work_area",
                            lambda box: SCREENS[screen])
    seen = {}

    def fake_exec(box):
        box.show()
        for _ in range(6):
            qapp.processEvents()
        btns = [b for b in box.findChildren(QPushButton) if b.isVisible()]
        seen["rects"] = [(b.text(), QRect(b.mapTo(box, b.rect().topLeft()),
                                          b.size())) for b in btns]
        seen["cut"] = [b.text() for b in btns
                       if b.width() < b.fontMetrics().horizontalAdvance(
                           b.text())]
        seen["size"] = (box.width(), box.height())
        seen["work"] = Wd.long_buttons_work_area(box)
        seen["body"] = box.informativeText()
        action(box)
        qapp.processEvents()
        box.hide()
        return 0
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    answer = tab._guided_bound_set_pages_answer()
    return answer, seen


def _escape(box):
    from PyQt6.QtTest import QTest
    QTest.keyClick(box.focusWidget() or box, Qt.Key.Key_Escape)


def _return(box):
    from PyQt6.QtTest import QTest
    QTest.keyClick(box.focusWidget() or box, Qt.Key.Key_Return)


@pytest.mark.parametrize("screen", sorted(SCREENS))
@pytest.mark.parametrize("code", LANGS)
def test_no_overlap_no_cut_and_inside_the_work_area(qapp, tab, language,
                                                    monkeypatch, code,
                                                    screen):
    language(code)
    answer, m = _ask(qapp, tab, monkeypatch, screen, _escape)
    assert answer == "cancel", (code, screen)
    rects = m["rects"]
    assert len(rects) == 3, (code, screen, [t for t, _r in rects])
    for i, (ta, ra) in enumerate(rects):
        for tb, rb in rects[i + 1:]:
            assert not ra.intersects(rb), (code, screen, ta, ra, tb, rb)
    assert not m["cut"], (code, screen, m["cut"])
    w, h = m["size"]
    work = m["work"]
    assert w <= work.width() and h + CAPTION <= work.height(), (
        code, screen, (w, h))
    at = QRect(work.x(), work.y() + CAPTION, w, h).topLeft()
    for t, r in rects:
        assert work.contains(r.translated(at)), (code, screen, t)


@pytest.mark.parametrize("screen", ["own", "1280x800"])
def test_return_is_do_not_generate(qapp, tab, language, monkeypatch, screen):
    language("de")
    answer, _m = _ask(qapp, tab, monkeypatch, screen, _return)
    assert answer == "cancel", screen


@pytest.mark.parametrize("code", ["en", "de", "es"])
def test_the_text_explains_the_answers_in_button_order(qapp, tab, language,
                                                       monkeypatch, code):
    """Text order = the order the buttons read (round-2 review, NIT)."""
    language(code)
    from core.i18n import count_phrase, tr
    _a, m = _ask(qapp, tab, monkeypatch, "1280x800", _escape)
    body = m["body"]
    labels = [count_phrase(1, tr("Make a new patch set for 1 page"),
                           tr("Make a new patch set for {n} pages")),
              tr("Keep my patches and lay them out again"),
              tr("Do not generate")]
    order = [t for t, _r in sorted(m["rects"],
                                   key=lambda tr_: (tr_[1].y(), tr_[1].x()))]
    assert order[1:] == labels[1:], order
    pos = [body.find(lbl + ":") for lbl in labels[1:]]
    assert -1 not in pos and pos == sorted(pos), (code, pos)
