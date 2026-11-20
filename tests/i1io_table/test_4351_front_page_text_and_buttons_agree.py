"""4.3.51 (review of 4.3.50): the page before the arm goes forward explained "Go forward carefully,
my hands are away" first but showed that button second. The window shows a page's answers with
the one that moves (or goes on) LAST, as everywhere in the app (the ready question: Stop, The arm
is out, Start; the homing of the ending: Not now, Bring the arm home; a page done: End
measurement, Go on), so the text now lists the answers in that order."""
from __future__ import annotations

from core.i18n import tr
from ui import i1io_table_window as W
from workflow import measurement_messages as M
from workflow.i1io.table import job as J


def test_the_text_lists_the_answers_in_the_order_of_the_buttons():
    body = M.M_I1IO_DRIVE_FRONT.body
    labels = [W.choice_label(J.Confirm.FRONT_CHOICE, v) for v in J.CHOICES[J.Confirm.FRONT_CHOICE]]
    assert labels == [tr("I will move the sheet"), tr("Go forward carefully, my hands are away")]
    first = body.index("•  I will move the sheet")
    second = body.index("•  Go forward carefully, my hands are away")
    assert first < second


def test_the_moving_answer_is_last_on_the_page():
    assert J.CHOICES[J.Confirm.FRONT_CHOICE][-1] == "go on"
    assert (J.Confirm.FRONT_CHOICE, "go on") in J.HANDS_OFF_ANSWERS
