"""The ruler check's diagnostics file (workflow/ruler_diagnostics.py): where it
lives, what it holds, what it must never hold."""
import json
from pathlib import Path

from core.file_manager import Run
from workflow import ruler_diagnostics as rd

CHART = Path(__file__).parent / "data" / "b8_1570_beta44_chart" / "chart.channels.json"


def test_the_file_lives_in_the_runs_reports_folder(tmp_path):
    run = Run.for_dir(tmp_path / "runs" / "run1")
    p = run.ruler_diagnostics_path("20261114-053000")
    assert p.parent.name == "reports" and p.name == "ruler_diagnostics_20261114-053000.json"
    assert run.ruler_diagnostics_files() == []


def test_strip_geometry_from_an_engine_chart():
    g = rd.strip_geometry(CHART)
    assert "A" in g
    a = g["A"]
    assert a["patches"] > 1 and a["span_mm"] > a["pitch_mm"] > a["patch_length_mm"] > 0


def test_strip_geometry_of_no_chart_is_empty(tmp_path):
    assert rd.strip_geometry(None) == {}
    assert rd.strip_geometry(tmp_path / "missing.json") == {}


def test_written_after_every_strip_and_holds_nothing_private(tmp_path):
    p = tmp_path / "reports" / "ruler_diagnostics_x.json"
    d = rd.Diagnostics(p, instrument="i1pro2", firmware=634,
                       geometry=rd.strip_geometry(CHART))
    rec = {"instrument": "i1pro2", "ended": "short", "samples": 100,
           "changes": [1, 2], "serial": "SECRET", "path": "/Users/x"}
    d.add_strip(rec, strip="A", figures={"travel_steps": 1}, verdict="ok")
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["format"] == rd.FORMAT and doc["firmware"] == 634
    assert doc["thresholds"]["provisional"] is True
    assert doc["strips"][0]["record"]["changes"] == [1, 2]
    text = p.read_text(encoding="utf-8")
    assert "SECRET" not in text and "/Users/" not in text
    d.note_answer("A", "reread")
    assert json.loads(p.read_text(encoding="utf-8"))["strips"][0]["answer"] == "reread"
    assert not list(p.parent.glob("*.part"))


def test_a_folder_that_cannot_be_written_never_raises(tmp_path):
    blocker = tmp_path / "reports"
    blocker.write_text("a file where the folder should be", encoding="utf-8")
    d = rd.Diagnostics(blocker / "r.json", instrument="i1pro3", firmware=None)
    d.add_strip({}, strip="A", figures={}, verdict="ok")   # must not raise
