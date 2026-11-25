"""The questions about a row of the i1iO table name their answers as the buttons read (item 58).

The texts spoke of "Skip this row" and "Read the rest patch by patch" while the buttons say "Skip it"
and "Rest patch by patch", and several translations had verb forms no button has. Every point of the
list is one button, in its order, in English and in the 13 languages, on a page and on a piece."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from ui import i1io_table_window as W
from workflow import measurement_messages as M

I18N = Path(__file__).resolve().parents[2] / "data" / "i18n"
LANGS = ["en", *sorted(p.stem for p in I18N.glob("*.json"))]

#: (message, the question, its answers in the order of the buttons)
QUESTIONS = [
    (M.M_I1IO_DRIVE_ROW_FAILED, "row_failed", ("again", "skip", "stop")),
    (M.M_I1IO_DRIVE_ROW_M0_ONLY, "row_failed", ("again", "skip", "stop")),
    (M.M_I1IO_DRIVE_ROW_FAILED_STRIP, "row_failed_strip",
     ("again", "patch by patch", "skip", "stop")),
    (M.M_I1IO_DRIVE_ROW_M0_ONLY_STRIP, "row_failed_strip",
     ("again", "patch by patch", "skip", "stop")),
    (M.M_I1IO_DRIVE_ROW_PLACEMENT_REST, "row_failed_strip",
     ("again", "rest patch by patch", "skip", "stop")),
]


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("pieces", (False, True), ids=("page", "piece"))
def test_every_point_is_a_button_by_its_own_words(lang, pieces):
    cat = {} if lang == "en" else json.loads(
        (I18N / f"{lang}.json").read_text(encoding="utf-8"))

    def tr(text):
        return text if lang == "en" else cat[text]
    for msg, kind, answers in QUESTIONS:
        msg = M.of_pieces(msg, pieces)
        points = re.findall(r"•\s+(.*)", tr(msg.body))
        assert len(points) == len(answers), msg.id
        for answer, point in zip(answers, points):
            label = tr(W.choice_label(kind, answer))
            assert re.match(rf"[«„“‘「]?{re.escape(label)}[»“”’」]?\s?[.:,。：，]", point), (
                msg.id, label, point)


def test_the_question_offers_these_answers_in_this_order():
    from workflow.i1io.table import job as J
    for _msg, kind, answers in QUESTIONS:
        offered = [a for a in J.CHOICES[kind] if a in answers]
        assert tuple(offered) == answers
