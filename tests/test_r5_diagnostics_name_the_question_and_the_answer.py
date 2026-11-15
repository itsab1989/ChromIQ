"""R5 (4.3.39): the ruler diagnostics file names WHICH question a strip got
and WHAT the person answered.

jctay's file (forum 150236): strip 9 was asked about seven times, but the
file only said ``other_question: true`` (ChromIQ's own question won over the
ruler's), never which question, and no answer was recorded, so how strip 9
ended right could only be guessed. Now each accepted strip's entry carries
``questions_asked`` (``ruler_not_covered``, ``ruler_direction``,
``engine_slip``, ``slip``, ``back_to_front``, ``read_twice``) and an
``answers`` list ``[{"question", "answer"}]`` in the order they were given;
the ruler question's old ``answer`` key stays as it was.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

REPO = Path(__file__).resolve().parents[1]


def _diag(tmp_path):
    from workflow.ruler_diagnostics import Diagnostics
    d = Diagnostics(tmp_path / "d.json", instrument="i1pro3", firmware=1)
    d.add_strip({}, strip="9", figures={}, verdict="accepted",
                extra={"questions_asked": ["back_to_front"]})
    return d


def test_answers_are_kept_in_order(tmp_path):
    d = _diag(tmp_path)
    d.note_question_answer("9", "back_to_front", "remeasure")
    d.note_question_answer("9", "back_to_front", "turn")
    doc = json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))
    e = doc["strips"][-1]
    assert e["questions_asked"] == ["back_to_front"]
    assert e["answers"] == [
        {"question": "back_to_front", "answer": "remeasure"},
        {"question": "back_to_front", "answer": "turn"}]


def test_the_ruler_answer_keeps_its_old_key_and_is_listed(tmp_path):
    from workflow.ruler_session import RulerSession
    rs = RulerSession(ti1_path=None)
    rs.diag = _diag(tmp_path)
    rs.note_answer("9", "continue")
    e = json.loads((tmp_path / "d.json").read_text(encoding="utf-8"))["strips"][-1]
    assert e["answer"] == "continue"
    assert e["answers"] == [{"question": "ruler", "answer": "continue"}]


def test_the_manager_names_the_question_and_passes_answers(qapp, tmp_path):
    from workflow.measure_manager import MeasureManager
    from test_knut_5956210745_next_strip_after_a_read import _Runner
    m = MeasureManager(_Runner())
    got = []

    class _RS:
        def note_question_answer(self, strip, q, a):
            got.append((strip, q, a))
    m._ruler = _RS()
    m.note_question_answer("9", "slip", None)
    assert got == [("9", "slip", "closed")]
    m._read_twice_pending = [("D", "C")]
    m.answer_read_twice("keep")
    assert got[-1] == ("D", "read_twice", "keep")


def test_the_strip_entry_lists_chromiqs_own_question():
    src = (REPO / "workflow/measure_manager.py").read_text(encoding="utf-8")
    i = src.index("_others = []")
    blk = src[i:i + 900]
    for name in ("engine_slip", "back_to_front", "slip", "read_twice"):
        assert f'"{name}"' in blk
    assert "other_questions=_others" in blk
    rs = (REPO / "workflow/ruler_session.py").read_text(encoding="utf-8")
    assert '"questions_asked": asked' in rs
    assert 'asked.append("ruler_not_covered")' in rs
    assert 'asked.append("ruler_direction")' in rs


def test_the_window_answer_reaches_the_file():
    src = (REPO / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    i = src.index("def _on_strip_partly_misaligned")
    blk = src[i:src.index("def _misaligned_strip_buttons", i)]
    assert 'note(strip, "back_to_front" if f.get("reversed") else "slip",' in blk
    assert blk.index("note(strip") < blk.index("_after_misaligned_strip_choice")
