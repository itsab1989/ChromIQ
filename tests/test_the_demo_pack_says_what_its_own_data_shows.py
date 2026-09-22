"""Round 3B (B8-807): the demo pack proved a paper-white FAIL on a yellow
patch, and its README contradicted itself.

Every test here holds the GENERATOR, `scripts/make_report_limit_demos.py`,
because the README and the pack are generated and a hand-edit of either is
lost at the next build. None of them runs ArgyllCMS.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "scripts" / "make_report_limit_demos.py"


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("_demo_gen_r3b", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_demo_gen_r3b"] = mod
    spec.loader.exec_module(mod)
    try:
        yield mod
    finally:
        sys.modules.pop("_demo_gen_r3b", None)


def _ti3(path: Path, rows) -> Path:
    head = ("CTI3\n\nDESCRIPTOR \"t\"\nCOLOR_REP \"iRGB_XYZ\"\n\n"
            "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
            f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n")
    body = "".join(" ".join(str(v) for v in r) + "\n" for r in rows)
    path.write_text(head + body + "END_DATA\n", encoding="utf-8")
    return path


def _fake_readme(gen, cov=None) -> str:
    base = {"with_value": [], "judged": [], "shipped_judged": [],
            "crossed": [], "uncrossed": []}
    base.update(cov or {})
    return gen.readme([], [], base, dest=None)


# ---------------------------------------------------------------------------
# F13: the paper white is the chart's paper, on every date
# ---------------------------------------------------------------------------
def test_a_paper_white_on_a_colour_patch_stops_the_build(gen, tmp_path):
    """Every-Limit-Set/run6 2028-05-12 recorded patch 208, a yellow, as paper
    white. The check the build now runs on every date must name that.

    MUTATION: make `_paper_white_fault` return "" unconditionally and this
    goes red."""
    ti3 = _ti3(tmp_path / "s.ti3", [
        (1, 100, 100, 100, 84.0, 87.0, 70.0),     # the paper
        (2, 100, 100, 0, 80.0, 92.0, 10.0),       # a yellow, lighter
        (3, 0, 0, 0, 1.0, 1.0, 1.0),
    ])
    assert gen._paper_white_fault(ti3, {"paper_white": {"loc": "2"}})
    assert gen._paper_white_fault(ti3, {"paper_white": {"loc": "1"}}) == ""


def test_a_chart_with_no_paper_patch_is_not_a_fault(gen, tmp_path):
    """Strip-And-Gamut/run4's mid-tone grid has no white: its "paper white"
    is the lightest patch, and the README says so rather than the build
    refusing a chart the app accepts."""
    ti3 = _ti3(tmp_path / "g.ti3", [
        (1, 60, 60, 60, 50.0, 52.0, 44.0),
        (2, 40, 40, 40, 30.0, 31.0, 26.0),
    ])
    assert gen.chart_white_locs(ti3, {}) == set()
    assert gen._paper_white_fault(ti3, {"paper_white": {"loc": "1"}}) == ""


def test_the_paper_moves_toward_yellow_and_keeps_its_lightness(gen):
    """The K15 direction lowered L* by 0.3 per unit of b*, which at 9.0 put
    the paper under a saturated yellow. MUTATION: put -0.3 back and this goes
    red."""
    assert gen._PAPER_DRIFT[0] == 0.0
    assert gen._PAPER_DRIFT[2] > 0.0
    src = inspect.getsource(gen.apply_design)
    assert "_PAPER_DRIFT" in src and "[-0.3, 0.1, 1.0]" not in src


def test_every_date_and_the_profiling_sheet_are_checked(gen):
    src = inspect.getsource(gen.build_run)
    assert src.count("_paper_white_fault(") >= 2


def test_the_readme_explains_every_paper_that_is_not_the_pack_s(gen):
    """The README used to state one paper for every ordinary sheet, while
    Border-Conditions/run2 and run3 and every From Profile Gamut chart record
    another, and Strip-And-Gamut/run4 records an L* 82 grey."""
    results = [
        {"project": "Report-Limits-Strip-And-Gamut", "run": "run4",
         "date": "2028-11-23_100000", "chart": "grid",
         "print": "through-profile", "has_paper_patch": False,
         "paper_white": {"loc": "125", "lab": [82.26, -0.05, 0.51]}},
        {"project": "Report-Limits-Border-Conditions", "run": "run3",
         "date": "2026-12-03_100000", "chart": "ordinary", "print": "raw",
         "has_paper_patch": True,
         "paper_white": {"loc": "1", "lab": [94.52, 0.22, 1.73]}},
    ]
    text = " ".join(gen.paper_white_lines(results))
    assert "has no paper patch" in text and "L* 82" in text
    assert "Border-Conditions/run3" in text and "raw" in text


# ---------------------------------------------------------------------------
# F1, F2, F24, F21, F26: the README's numbers and names
# ---------------------------------------------------------------------------
def test_the_judge_all_heading_is_computed(gen):
    from workflow.compliance_sets import effective_limits, limit_bearing
    n = len(limit_bearing(effective_limits("custom_iso_12647_7", {})))
    text = _fake_readme(gen)
    assert f"COME TO JUDGE ALL {n} ROWS" in text
    assert "SIXTEEN" not in text


def test_a_row_name_is_printed_whole(gen):
    long_row = "ramps_30_70_dl_max"
    title = gen.ROW_TITLES[long_row]
    cov = {"matrix_sets": ["chromiq_default"],
           "matrix_cells": [{"set": "chromiq_default", "row": long_row,
                             "complete": True, "over": "a", "inside": "b"}]}
    assert title in _fake_readme(gen, cov)


def test_the_clean_verdict_section_names_what_it_counts(gen):
    text = " ".join(_fake_readme(gen, {"shipped_judged": list("abcdefghi")})
                    .split())
    assert "Nine rows can be judged by" in text
    assert "repeatability rows" in text
    assert "counting the row an edited column adds" not in text


def test_a_type_held_on_disk_counts_as_produced(gen):
    src = inspect.getsource(gen.type_set_coverage)
    assert "seen_types.update(counts)" in src


def test_a_printing_record_is_not_credited_to_a_verification(gen):
    src = inspect.getsource(gen.message_coverage)
    assert "report_types_for_kind" in src
    assert "record_type" in gen.UNREACHABLE_BY_DATA


# ---------------------------------------------------------------------------
# F12: a pack chart opens on the settings it was made with
# ---------------------------------------------------------------------------
def test_a_pack_chart_records_the_settings_it_was_made_with(gen, tmp_path):
    """Opened with nothing stored, the verification chart showed an i1Pro and
    the engine's 22 mm clip band against a printtarg sheet, in red."""
    folder = tmp_path / "verifications"
    folder.mkdir()
    gen.record_chart_settings(folder, "A4", gen._targen_settings(gen.CHART_MEDIUM))
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    s, ui = meta["create_chart_settings"], meta["create_chart_ui"]
    assert s["printtarg-i"]["value"] == gen.PRINTTARG_INSTRUMENT
    assert s["printtarg-p"]["value"] == "A4"
    assert s["targen-f"]["value"] == gen.CHART_MEDIUM.patches
    assert ui["engine_on"] is False and ui["mode"] == "manual"
    assert ui["engine_recipe"]["clip_content_mode"] == "off"
    # an absent Guided row opened on the i1Pro and was mirrored into -i
    assert ui["guided"]["instrument"] == gen.PRINTTARG_INSTRUMENT
    assert f"-M{gen.PRINTTARG_MARGIN_MM}" in gen.printtarg_args("A4")


# ---------------------------------------------------------------------------
# F30: a run description is the story, not a frozen lock state
# ---------------------------------------------------------------------------
def test_a_run_description_carries_the_story_only(gen):
    src = inspect.getsource(gen.build_run)
    assert "meta.description = plan.description" in src
    assert "meta.description = plan.full_description" not in src
