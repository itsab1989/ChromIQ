"""A7 + A8 (4.3.50): at a measurement's end the app log says where its files went
and, with the dual scan / M0-M1-M2 kept, how many strips have all three conditions
and which have M0 only. Driven through the REAL helper's dual scan (replay)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession  # noqa: E402

import test_conditions_kept_4349 as K  # noqa: E402

needs_helper = pytest.mark.skipif(not HELPER.exists(), reason="helper not built")


def _ev(caplog, tag):
    return [r.getMessage() for r in caplog.records if r.getMessage().startswith(tag + ":")]


@needs_helper
def test_a_dual_scan_end_counts_its_strips(tmp_path, monkeypatch, caplog):
    from workflow.measure_log import log_measurement_end
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    base, rp = K._dual_chart(tmp_path)
    cdir = tmp_path / "conditions"
    cdir.mkdir()
    with ReplaySession(base, rp, extra_args=K._dual_args(cdir)) as s:
        K._read(s)
        K._read(s, m0=True)
        K._read(s)
        K._done(s, unread=True)
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        log_measurement_end(base.with_suffix(".ti3"), code=0, conditions=True, dual=True,
                            in_thread=False)
    (end,) = _ev(caplog, "measure end")
    assert "exit=0" in end and "measurement=" in end
    (c,) = _ev(caplog, "conditions end")
    assert "strips=3" in c and "strips_all_three=1" in c and 'm0_only="B C"' in c, c
    assert "partial=M1,M2" in c and "dual_scan=on" in c
    w = _ev(caplog, "file written")
    assert any("what=measurement" in x for x in w)
    assert any('what="condition M1 (partial record)"' in x for x in w), w


def test_no_conditions_no_conditions_line(tmp_path, caplog):
    from workflow.measure_log import log_measurement_end
    ti3 = tmp_path / "T.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        log_measurement_end(ti3, code=1, conditions=False, dual=False, in_thread=False)
    assert len(_ev(caplog, "measure end")) == 1 and not _ev(caplog, "conditions end")
    with caplog.at_level(logging.INFO, logger="chromiq.events"):
        log_measurement_end(tmp_path / "missing.ti3", code=1, conditions=True, dual=False,
                            in_thread=False)   # never raises
