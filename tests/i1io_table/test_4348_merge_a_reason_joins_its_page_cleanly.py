"""4.3.48 merge: a reason sentence joins the page around it without a doubled full stop.

The final challenger pass of 4.3.48 found every translation of the dual scan's ``no_ruler``
sentence carrying a stray ". ." where its two parts meet (``"... patch by patch. " +
_BOTH_AGAIN`` in workflow/dual_scan/reasons.py). The English join is right, and the stray
stops were translation artefacts (removed by the challenger in every language): pinned here so
none comes back, for every sentence assembled from parts.

Looking at how the table's pages put a reason into a sentence found a real join fault next to
it: "Row {row} of page {page} could not be read (as a strip): {why}. ..." stripped only the
ASCII "." from *why*, so in Japanese and Chinese every such page read "。。".
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

import ui.i1io_table_window as W
from core import i18n
from workflow import measurement_messages as M
from workflow.dual_scan import reasons as R

ROOT = Path(__file__).resolve().parents[2]
LANGS = sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json"))
DOUBLE = re.compile(r"[.。．!?！？]\s*[.。．]")


def test_the_english_join_of_the_strip_sentences_is_one_stop_and_one_space():
    assert R.REASONS["no_ruler"].endswith(R._BOTH_AGAIN)
    assert "patch by patch. Read this strip once more" in R.REASONS["no_ruler"]
    for rid, text in R.REASONS.items():
        assert not DOUBLE.search(text), rid
        assert "  " not in text, rid


@pytest.mark.parametrize("code", LANGS)
def test_no_translated_reason_carries_a_stop_its_english_has_not(code):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text(encoding="utf-8"))
    bad = {}
    assert isinstance(cat.get(R.REASONS["no_ruler"]), str), code
    for rid, en in list(R.REASONS.items()) + list(R.NOTES.items()):
        tr_ = cat.get(en)
        if not isinstance(tr_, str):
            continue                  # not shown through tr() (scripts/i18n_extract.py's say)
        m = DOUBLE.search(tr_)
        if m and not DOUBLE.search(en):
            bad[rid] = tr_[max(0, m.start() - 30):m.end() + 10]
    assert not bad, (code, bad)


def _reason_ids():
    src = inspect.getsource(W.reason_text)
    return sorted(set(re.findall(r'^\s+"([a-z0-9_]+)": tr\(', src, re.M)) | set(R.REASONS))


@pytest.mark.parametrize("code", ["en"] + LANGS)
def test_a_row_page_never_doubles_the_stop_after_its_reason(code):
    i18n.set_language(code)
    try:
        bad = {}
        for rid in _reason_ids():
            why = W.as_clause(W.reason_text(rid))
            for msg in (M.M_I1IO_DRIVE_ROW_FAILED_STRIP, M.M_I1IO_DRIVE_ROW_FAILED,
                        M.M_I1IO_DRIVE_ROW_FAILED_STRIP_NOT_MOVED):
                body = msg.render(row=1, page=1, why=why)[1]
                m = DOUBLE.search(body)
                if m:
                    bad[(rid, msg.id)] = body[max(0, m.start() - 30):m.end() + 10]
        assert not bad, (code, list(bad.items())[:5], len(bad))
    finally:
        i18n.set_language("en")


def test_the_window_puts_every_row_reason_through_as_clause():
    src = inspect.getsource(W.TableMeasureWindow)
    assert 'reason_text(d.get("why", "")).rstrip(".")' not in src
    assert src.count('why=as_clause(self._reason(d.get("why", "")))') == 2
    assert W.as_clause("abc。") == "abc" and W.as_clause("abc.") == "abc"
    assert W.as_clause("abc． ") == "abc" and W.as_clause("abc?") == "abc?"
