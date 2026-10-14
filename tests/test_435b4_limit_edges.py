"""Every misread limit, exactly at its edge, on every chart type (#182, Knut
6154440320, 4.3.5 beta 4).

    *"make sure that the patch error check and neighbour check are using the
    correct limits according to its run type and chart (calibration chart,
    profiling chart with or without pre-conditioning profile, and
    verification chart), and verify by test that each chart type is
    triggering on the correct limit by setting all limits to unique levels
    and making demo project data with proper measurement data that is
    designed to trigger exactly on each one of the limits for each chart type
    and for each test method."*

``scripts/make_limit_edge_demo.py`` builds the charts and the readings, every
limit of Preferences ▸ Measurement set to its own unique value, with patches
planted 0.01 under, exactly on and 0.01 over each limit, the strip test's
fence, the same-reading tolerance, and the readings that give every kind of
card. ``scripts/drive_b4_limit_edges.py``'s protocol drives the Measure tab
with them through the reading engine's signals and compares the outline and
the card's sentences with the demo's own figures. The same protocol runs on
screen, with a photograph of every card (beta 4 report, M1).
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from scripts.make_limit_edge_demo import KINDS, build  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    return build(tmp_path_factory.mktemp("edges"))


class _Settings:
    def __init__(self):
        self._d = {"chartread_engine": "chromiq"}

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


@pytest.mark.parametrize("kind", KINDS)
def test_every_limit_at_its_edge(qapp, demo, kind):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from core.argyll_runner import ArgyllRunner
    from scripts.drive_b4_limit_edges import Protocol, Rig
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    tab = TabMeasure(ArgyllRunner(s), s)
    try:
        p = Protocol(Rig(qapp, tab, demo))
        rows = p.run(kind)
    finally:
        tab.deleteLater()
    bad = [f"{r['case']} {r['loc']}: expected {r['expected']}; seen "
           f"{r['seen']}" for r in rows if not r["pass"]]
    assert not bad, "\n".join(bad)
    assert len(rows) >= 20
