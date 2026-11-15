"""R6 (4.3.39): a chart whose patches are shorter along the strip than
ArgyllCMS's minimum for the instrument gets a note in Create Chart and one
line in the Measure log (M-CHART-PATCHES-SHORT, M-MEASURE-PATCHES-SHORT,
proposed). Nothing is refused or greyed.

The minimums are printtarg's own "Patch min length" (target/printtarg.c
3.5.0): i1Pro family 10 mm, i1Pro 3 Plus 20 mm, ColorMunki 14 mm, the same
numbers the layout engine starts from at patch scale 1.0 (pinned below, so the
two cannot drift apart). jctay's chart (forum 150236): 8.0 mm patches on an
i1Pro 3, below the 10 mm.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from workflow import patch_size_check as P
from workflow import measurement_messages as M

REPO = Path(__file__).resolve().parents[1]
ARGYLL_SRC = Path("/Users/Basti/Downloads/Argyll_V3.5.0_orig/target/printtarg.c")


def test_the_minimums_are_the_layout_engines_own_starting_lengths():
    from workflow.layout_engine import instruments
    for key, want in P.ARGYLL_MIN_PATCH_LENGTH_MM.items():
        g = instruments.build(key)
        if key == "p3":
            # printtarg lays the i1Pro 3 Plus out at 20 mm; 16 mm is its
            # absolute limit with the zebra ruler, the minimum judged here
            assert g.plen == pytest.approx(20.0) and want == 16.0
        else:
            assert g.plen == pytest.approx(want), key


@pytest.mark.skipif(not ARGYLL_SRC.exists(), reason="ArgyllCMS source not here")
def test_the_minimums_are_printtargs():
    src = ARGYLL_SRC.read_text(encoding="latin-1")
    assert "plen  = pscale * 10.00;\t/* Patch min length - total 10 mm (absolute limit is 10) */" in src
    assert "plen  = pscale * 20.00;\t/* Patch min length - total 20 mm" in src
    assert "plen  = pscale * 14.00;\t/* Patch min length - total 15 mm */" in src


@pytest.mark.parametrize("inst,lengths,warn", [
    ("i1", [8.0, 8.0], True),            # jctay's 8 mm on an i1Pro 3
    ("i1", [9.99], False),               # one pixel of rounding at 300 dpi
    ("i1", [10.0, 12.0], False),
    ("i1", [9.85], True),
    ("p3", [15.0], True),
    ("p3", [16.0], False),
    ("p3", [20.0], False),
    ("CM", [13.0], True),
    ("CM", [14.0], False),
    ("SS", [7.0], False),                 # tables are not judged
    ("IO2", [8.0], False),
    ("CR30", [5.0], False),
])
def test_judge(inst, lengths, warn):
    assert (P.judge(inst, lengths) is not None) is warn


def _channels(tmp_path, inst, h_px, dpi=300, engine="chromiq"):
    p = tmp_path / "c.channels.json"
    p.write_text(json.dumps({"layout": {
        "engine": engine, "dpi": dpi, "recipe": {"instrument": inst},
        "patches": [{"loc": "1A", "h": h_px}, {"loc": "1B", "h": h_px + 2}]}}),
        encoding="utf-8")
    return p


def test_from_the_charts_own_record(tmp_path):
    f = P.from_channels(_channels(tmp_path, "i1", 94))   # 7.96 mm
    assert f is not None and f.min_mm == 10.0 and f.patch_mm == 8.0
    assert P.from_channels(_channels(tmp_path, "i1", 118)) is None   # 9.99
    assert P.from_channels(_channels(tmp_path, "i1", 94, engine="printtarg")) is None
    assert P.from_channels(tmp_path / "missing.json") is None


def test_the_texts_name_the_minimum_and_what_can_happen(tmp_path):
    f = P.from_channels(_channels(tmp_path, "i1", 94))
    title, body = P.note_text(f)
    assert "8 mm" in body and "10 mm" in body and "i1Pro" in body
    assert "Reading is inconsistent" in body and "Too many patches" in body
    assert "—" not in body + title
    line = P.log_line(f)
    assert line.startswith("Note: the patches of this chart are 8 mm")
    assert "patch by patch" in line
    assert {M.M_CHART_PATCHES_SHORT.id, M.M_MEASURE_PATCHES_SHORT.id} <= set(M.PROPOSED)


def test_create_chart_and_measure_say_it_and_refuse_nothing():
    chart = (REPO / "ui/tabs/tab_chart.py").read_text(encoding="utf-8")
    i = chart.index("def _short_patch_note")
    blk = chart[i:chart.index("\n    @staticmethod", i)]
    assert "setEnabled" not in blk and "return False" not in blk
    assert "_short = self._short_patch_note()" in chart
    meas = (REPO / "ui/tabs/tab_measure.py").read_text(encoding="utf-8")
    start = meas.index("self._session_live = True\n")
    assert "self._say_short_patches()" in meas[start:start + 700]


def test_the_measure_log_says_it_once(qapp, tmp_path, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    tab = TabMeasure(ArgyllRunner(s), s)
    ti1 = tmp_path / "c.ti1"
    ti1.write_text("CTI1\n", encoding="utf-8")
    _channels(tmp_path, "i1", 94)
    tab._ti1_path = ti1
    tab._say_short_patches()
    assert tab._log.toPlainText().count("Note: the patches of this chart") == 1
    tab.deleteLater()


def test_extra_high_density_gets_its_own_words(tmp_path):
    p = tmp_path / "x.channels.json"
    p.write_text(json.dumps({"layout": {
        "engine": "chromiq", "dpi": 300,
        "recipe": {"instrument": "CM", "cm_density": 3},
        "patches": [{"loc": "A1", "h": 153}]}}), encoding="utf-8")   # 12.95 mm
    f = P.from_channels(p)
    assert f is not None and f.extra_high
    title, body = P.note_text(f)
    assert "Extra-high density" in body and "High density (rig)" in body
    assert "You can still" not in body                 # no blame
    assert "Extra-high density" in P.log_line(f)


def test_the_note_has_a_line_on_the_panels_surface(tmp_path):
    f = P.from_channels(_channels(tmp_path, "i1", 94))
    line = P.panel_line(f)
    assert line.startswith("Patches 8 mm long along the strip") and "10 mm" in line
    chart = (REPO / "ui/tabs/tab_chart.py").read_text(encoding="utf-8")
    assert "overlaps = list(overlaps or []) + [_line]" in chart
