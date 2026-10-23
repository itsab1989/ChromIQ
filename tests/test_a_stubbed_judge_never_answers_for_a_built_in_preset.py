"""A test that stubs how a chart is judged never leaves the stub's answer in
the presets' session cache (agent 23, 4.3.10 review).

Seen once, in agent 22's everyday run:
``KeyError: 'uniformity_de00_max_from_mean'`` in
`test_b8_1451_evenness_counts_are_true_and_consistent.py::
test_no_preset_is_withheld_for_the_estimated_noise_of_a_typical_print`.
The answer it read for a built-in preset held two rows, ``all_de00_avg`` and
``uniformity_sd``: exactly the stub `test_beta12_b_review.py` puts in place of
`measurement_report.row_values`. The presets' background thread
(`preset_layout`) outlives the test that queued it, so built-in presets queued
by an earlier window on the same worker were judged BY THE STUB and filed in
`preset_eligibility._CACHE` under their real keys.

The app never stubs its judge, so this is the suite's own hygiene: every test
that does asks for the `stubbed_judge` fixture (tests/conftest.py).
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication                       # noqa: E402

from workflow import measurement_report as MR                  # noqa: E402
from workflow import preset_eligibility as PE                  # noqa: E402
from workflow import preset_layout as PL                       # noqa: E402

TESTS = Path(__file__).parent

#: Patching one of these changes what `chart_row_values` files.
_JUDGE = re.compile(
    r"monkeypatch\.setattr\(\s*(MR|PE|measurement_report|preset_eligibility)"
    r"\s*,\s*[\"'](row_values|_perfect_print)[\"']")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _stub(_report):
    return {"all_de00_avg": {"value": 1.0, "reason": None},
            "uniformity_sd": {"value": None, "reason": "stub"}}


def test_the_background_thread_does_judge_with_a_stub(qapp, tmp_path,
                                                      stubbed_judge,
                                                      monkeypatch):
    """Why the fixture exists: work queued BEFORE the stub is judged by it.

    MUTATION, proven red: `_Compute.__call__` returning at once (then the
    cache stays clean and this guard of the guard fails)."""
    from workflow.i1profiler_import import RgbPatch, write_ti1
    charts = []
    for i in range(3):
        c = tmp_path / f"c{i}.ti1"
        write_ti1([RgbPatch(i, 0, 0), RgbPatch(100, 100, 100)], c)
        charts.append(c)
    PL._HOLD_UNTIL = 0.0
    monkeypatch.setattr(PE, "_perfect_print", lambda *a, **k: {})
    monkeypatch.setattr(MR, "row_values", _stub)
    for c in charts:
        PE.request_values(c, None)
    end = time.monotonic() + 30
    while PL.pending() and time.monotonic() < end:
        time.sleep(0.01)
    partial = [v for v in PE._CACHE.values()
               if "uniformity_de00_max_from_mean" not in v]
    assert partial, "the background thread did not judge with the stub"


def test_every_test_that_stubs_the_judge_asks_for_the_fixture():
    """MUTATION, proven red: drop ``stubbed_judge`` from either test in
    `test_beta12_b_review.py` that stubs `row_values`."""
    bad = []
    for path in sorted(TESTS.glob("test_*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if not _JUDGE.search(text):
            continue
        # each test function that stubs the judge must request the fixture
        for m in re.finditer(r"^def (test_\w+)\((.*?)\):\n(.*?)(?=^def |\Z)",
                             text, re.S | re.M):
            name, args, body = m.group(1), m.group(2), m.group(3)
            stubs = _JUDGE.search(body) or (
                "_no_judging(monkeypatch)" in body)
            if stubs and "stubbed_judge" not in args:
                bad.append(f"{path.name}::{name}")
    assert not bad, bad
