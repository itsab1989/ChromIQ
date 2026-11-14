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


# ---------------------------------------------------------------------------
# 4.3.37: strips grouped by the chart's own label scheme
# ---------------------------------------------------------------------------
def _engine_chart(tmp_path, strip_pat, patch_pat, locs_by_strip, name="c"):
    """A small engine chart: <name>.ti2 with its label patterns and
    SAMPLE_LOCs, and <name>.channels.json with one rectangle per patch
    (strips run down the page)."""
    locs, rects = [], []
    for s_i, (_strip, plocs) in enumerate(locs_by_strip):
        for p_i, loc in enumerate(plocs):
            locs.append(loc)
            rects.append({"loc": loc, "x": 100 * s_i, "y": 50 * p_i,
                          "w": 90, "h": 45})
    ti2 = tmp_path / f"{name}.ti2"
    ti2.write_text(
        "CTI2\n\n"
        f'STRIP_INDEX_PATTERN "{strip_pat}"\nPATCH_INDEX_PATTERN "{patch_pat}"\n'
        'INDEX_ORDER "STRIP_THEN_PATCH"\n'
        f'STEPS_IN_PASS "{len(locs_by_strip[0][1])}"\n'
        f'PASSES_IN_STRIPS2 "{len(locs_by_strip)}"\n\n'
        "NUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC\n"
        "END_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(locs)}\nBEGIN_DATA\n"
        + "".join(f'{i + 1} "{loc}"\n' for i, loc in enumerate(locs))
        + "END_DATA\n", encoding="latin-1")
    ch = tmp_path / f"{name}.channels.json"
    ch.write_text(json.dumps({"layout": {"engine": "chromiq", "dpi": 300,
                                         "patches": rects}}), encoding="utf-8")
    return ti2, ch


def test_number_strips_with_letter_patches_are_grouped_by_strip(tmp_path):
    """ChromIQ's engine chart of the tester's file: strips 1-16 printed as
    numbers, patches A-L as letters ("9I"). The old rule made every patch a
    strip of its own (192 one-patch strips, no geometry for any strip)."""
    strips = [(str(n), [f"{n}{c}" for c in "ABCDEFGHIJKL"])
              for n in range(1, 17)]
    ti2, ch = _engine_chart(tmp_path, "0-9@0-9", "A-Z", strips)
    g = rd.strip_geometry(ch, ti2)
    assert sorted(g, key=int) == [str(n) for n in range(1, 17)]
    assert all(v["patches"] == 12 for v in g.values())
    assert g["9"]["pitch_mm"] > 0 and g["9"]["span_mm"] > g["9"]["pitch_mm"]
    # without the chart's labels, the old rule (and its fault) stays
    assert len(rd.strip_geometry(ch)) == 192


def test_a_classic_chart_is_grouped_as_before(tmp_path):
    strips = [(s, [f"{s}{i}" for i in range(1, 11)]) for s in "ABC"]
    ti2, ch = _engine_chart(tmp_path, "A-Z", "0-9@0-9", strips)
    assert rd.strip_geometry(ch, ti2) == rd.strip_geometry(ch)
    assert sorted(rd.strip_geometry(ch, ti2)) == ["A", "B", "C"]


def test_the_session_passes_the_charts_labels_and_its_own_facts(tmp_path):
    from workflow.ruler_session import RulerSession
    run = tmp_path / "runs" / "run1"
    run.mkdir(parents=True)
    strips = [(str(n), [f"{n}{c}" for c in "ABCDEFGHIJKL"]) for n in (1, 2)]
    _engine_chart(run, "0-9@0-9", "A-Z", strips, name="chart")
    for gen in ("i1pro2", "i1pro3"):
        rs = RulerSession(ti1_path=run / "chart.ti1", helper_build="b-1",
                          condition="M1")
        rs.on_session({"event": "ruler", "active": True, "instrument": gen,
                       "firmware": 634})
        doc = json.loads(rs.diagnostics_path().read_text(encoding="utf-8"))
        assert sorted(doc["chart_geometry"]) == ["1", "2"]
        assert doc["engine_build"] == "b-1"
        assert doc["measurement_condition"] == "M1"


def test_the_manager_passes_the_build_and_the_condition():
    src = (Path(__file__).resolve().parent.parent / "workflow" /
           "measure_manager.py").read_text(encoding="utf-8")
    assert "helper_build=helper_build(params.engine_helper)" in src
    assert "condition=condition_for_filter(filter_code_from_args(" in src
