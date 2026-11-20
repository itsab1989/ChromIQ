"""4.3.51 (review of 4.3.50): the page before the arm goes forward explained "Go forward carefully,
my hands are away" first but, in the panel, showed that button second. The app shows a page's
confirming answer FIRST: its dialogs use the Windows button order on every platform (main.py's
WinButtonLayoutStyle), and the table's own pop-ups place the confirming answer by its role, first.
So the panel now shows this page's answers in the order its text explains them; the words and the
pop-up are unchanged."""
from __future__ import annotations

from core.i18n import tr
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from ui import i1io_table_window as W
from workflow import measurement_messages as M
from workflow.i1io.table import job as J


def test_the_panel_shows_the_answers_in_the_order_the_text_explains_them():
    body = M.M_I1IO_DRIVE_FRONT.body
    shown = W.SHOWN_CHOICES.get(J.Confirm.FRONT_CHOICE, J.CHOICES[J.Confirm.FRONT_CHOICE])
    labels = [W.choice_label(J.Confirm.FRONT_CHOICE, v) for v in shown]
    assert labels == [tr("Go forward carefully, my hands are away"), tr("I will move the sheet")]
    assert body.index("\u2022  Go forward carefully") < body.index("\u2022  I will move the sheet")
    assert set(shown) == set(J.CHOICES[J.Confirm.FRONT_CHOICE])


def test_the_panel_shows_them_in_that_order(qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True)
    # The shared helper waits 15 s per step, which a full gate (every core busy) can exceed
    # (seen once). Only in this test: wait up to 60 s and say what was being waited for.
    wait_s = 60

    def wait_loaded(cond):
        try:
            qtbot.waitUntil(cond, timeout=wait_s * 1000)
        except Exception as exc:  # pytestqt raises TimeoutError
            raise AssertionError(
                f"the table window did not finish its opening step within {wait_s} s") from exc

    p.wait = wait_loaded
    assert p.drive_until("ready_to_open") == "ready_to_open"
    assert not win._popups
    res = J.StepResult("align", J.Kind.NEEDS, confirm=J.Confirm.FRONT_CHOICE,
                       choices=J.CHOICES[J.Confirm.FRONT_CHOICE], detail={"back_mm": 12})
    win._ask(res)
    assert p.labels()[:2] == ["Go forward carefully, my hands are away", "I will move the sheet"]
