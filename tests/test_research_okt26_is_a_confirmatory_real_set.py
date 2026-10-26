"""R-Pro300-Okt26 (Basti's own Canon PRO-300, 2026-10-09) is a battery real set (Agent 81, 2026-10-24).

It is representative: confirmatory by role_of (like R-ET8550), never robustness-only, and it is read
from the research workspace's read-only copy, never from ~/ChromIQ.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.research import datasets as dsm


def test_okt26_is_registered_and_confirmatory():
    assert "R-Pro300-Okt26" in dsm.REAL_SOURCES
    assert not dsm.is_robustness_only("R-Pro300-Okt26")
    assert dsm.role_of("R-Pro300-Okt26") == "confirmatory"
    assert "representative" in dsm.REAL_SOURCES["R-Pro300-Okt26"][3]


def test_okt26_is_read_from_the_research_copy_not_the_owner_folder():
    src, kind, _note = dsm.real_source("R-Pro300-Okt26")
    assert kind == "ti3"
    assert src.is_relative_to(dsm.RESEARCH_DATASETS)
    assert not src.is_relative_to(Path.home() / "ChromIQ")


def test_okt26_joins_every_real_battery_run():
    from benchmarks.research import run
    assert "R-Pro300-Okt26" in run.REAL_BASE


def test_okt26_held_out_split_is_leak_free(tmp_path):
    src, _k, _n = dsm.real_source("R-Pro300-Okt26")
    if not src.exists():
        pytest.skip("research dataset copy not on this machine")
    d = dsm.real("R-Pro300-Okt26", tmp_path)
    assert d.info["holdout_leak"] == 0
    assert d.info["held_out"] >= 20
