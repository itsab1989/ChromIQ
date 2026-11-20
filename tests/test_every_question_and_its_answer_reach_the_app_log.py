"""A4 (4.3.50): every question a window asks reaches the app log with its
catalogue id, the answer given (in English) and how long it was open, from ONE
central place: the application's dialog filter."""
from __future__ import annotations

import logging

import pytest
from PyQt6.QtWidgets import QDialog, QMessageBox, QPushButton, QVBoxLayout, QLabel


@pytest.fixture
def app_filter(qapp):
    from ui.widgets import CompositeAppFilter
    f = CompositeAppFilter()
    qapp.installEventFilter(f)
    yield f
    qapp.removeEventFilter(f)


def _questions(caplog):
    return [r.getMessage() for r in caplog.records
            if r.getMessage().startswith("question")]


def test_a_message_box_with_a_catalogue_message(qapp, app_filter, caplog):
    from workflow import measurement_messages as M
    title, body = M.M_STRIP_PART_SLIPPED_LATE.render(
        strip="C", first="C3", last="C9", lead_line="", base="3.1", best="0.4",
        numbers_line="", twice="?", shift_line="", middle_line="",
        remeasure="Re-measure this strip", keep="Keep it", turn="Turn", stop="Stop")
    box = QMessageBox()
    box.setWindowTitle("Strip may be misaligned")
    box.setText(body)
    keep = box.addButton("Keep it", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Stop", QMessageBox.ButtonRole.RejectRole)
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        box.show()
        qapp.processEvents()
        keep.click()
        qapp.processEvents()
        box.hide()
        qapp.processEvents()
    (q,) = _questions(caplog)
    assert q.startswith("question: id=M-STRIP-PART-SLIPPED-LATE window=QMessageBox")
    assert 'answer="Keep it"' in q and "open_s=" in q


def test_a_custom_dialog_names_its_button(qapp, app_filter, caplog):
    dlg = QDialog()
    dlg.setObjectName("strip_read_twice_window")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel("Did you read strip C twice?"))
    b = QPushButton("I read strip B", dlg)
    b.setObjectName("read_b")
    b.clicked.connect(dlg.accept)
    lay.addWidget(b)
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        dlg.show()
        qapp.processEvents()
        b.click()
        qapp.processEvents()
    (q,) = _questions(caplog)
    assert "id=strip_read_twice_window" in q and 'answer="I read strip B"' in q
    assert "button=read_b" in q and "result=accepted" in q


def test_a_window_closed_without_an_answer(qapp, app_filter, caplog):
    dlg = QDialog()
    dlg.setWindowTitle("Some window")
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        dlg.show()
        qapp.processEvents()
        dlg.reject()
        qapp.processEvents()
    (q,) = _questions(caplog)
    assert "answer=closed" in q and "result=rejected" in q


def test_a_translated_answer_is_logged_in_english(monkeypatch):
    from core import i18n
    from core import question_log as ql
    monkeypatch.setattr(i18n, "_catalog", {"Keep it": "Behalten", "Stop": "Anhalten"})
    ql._REVERSE = None
    assert ql.english("Behalten") == "Keep it"
    assert ql.english("&Anhalten") == "Stop"
    assert ql.english("unknown") == "unknown"
    ql._REVERSE = None


def test_the_misaligned_strip_answer_is_logged_by_name():
    import inspect
    from ui.tabs import tab_measure
    src = inspect.getsource(tab_measure)
    assert "_answered(message.id, choice[0], strip=strip" in src


def test_auto_answered_says_so(caplog):
    from core.question_log import auto_answered
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        auto_answered("M-I1IO-DRIVE-AFTER-STEP", "carry_on", page="after_step")
    (q,) = _questions(caplog)
    assert q == ("question answer: id=M-I1IO-DRIVE-AFTER-STEP answer=carry_on "
                 "by=automatic page=after_step")
