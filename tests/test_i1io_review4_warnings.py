"""REVIEW 4: WHAT WAS STILL SILENT IS SAID (items 2 and 3), AND THE OPTIONS
OF A CHART FROM 4.3.33 TAKE EFFECT (finding 1, the owner's ruling).

* the strip letters or their underline on the blank paper a strip's run
  takes (run-in, run-out) are said: the table may take them for a patch;
* patch numbers asked for but left off for want of room beside the strips
  (a chart offset to the left) are said;
* a recipe read from a 4.3.33 project (no Job D fields) builds every option
  a person then sets: chart offset, Clip, label offset, helper markers.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_i1io_letters_and_numbers_are_held_or_said import (  # noqa
    _build, _preview, i1io_on)

RUN = "blank paper the arm starts or stops a strip on"
GONE = "do not fit beside the strips and are left off"


@pytest.mark.parametrize("kw", [
    {"strip_label_offset_mm": -6.0, "underline_mode": "black"},
    {"strip_label_offset_mm": -11.0}])
def test_letters_on_the_run_are_said(tmp_path, kw):
    result = _build(tmp_path, **kw)
    assert any(RUN in w for w in result.warnings), result.warnings
    _s, notes = _preview(**kw)
    assert any(RUN in w for w in notes)


@pytest.mark.parametrize("kw", [{"offset_x": -12.0},
                                {"offset_x": -7.0, "i1io_crosses": False}])
def test_numbers_left_off_are_said(tmp_path, kw):
    result = _build(tmp_path, **kw)
    assert any(GONE in w for w in result.warnings), result.warnings


def test_defaults_say_neither(tmp_path):
    result = _build(tmp_path)
    assert not any(RUN in w or GONE in w for w in result.warnings)


def test_a_4333_recipe_builds_the_options_set_on_it(tmp_path):
    """The reviewer's D1: a 4.3.33 i1iO recipe (none of the new fields),
    then chart offset X 8, Clip 3, label offset Y -15 and helper markers:
    every one reaches the chart's build kwargs, none is dropped."""
    from dataclasses import replace
    from workflow.i1io import chart as C
    from workflow.layout_engine.presets import LayoutRecipe
    import json
    from pathlib import Path
    d = json.loads((Path(__file__).parent / "data" / "i1io_4333_projects"
                    / "m-style" / "runs" / "run1" / "m-style.channels.json"
                    ).read_text(encoding="utf-8"))["layout"]["recipe"]
    assert "i1io_numbers_edge_mm" not in d          # written by 4.3.33
    r = replace(LayoutRecipe.from_dict(d), offset_x_mm=8.0,
                i1io_numbers_edge_mm=3.0, strip_label_offset_mm=-15.0,
                helper_markers=True)
    kw = r.build_kwargs()
    fixed = C.fixed_build_kwargs(kw)
    assert fixed["offset_x"] == 8.0
    assert fixed["helper_markers"] is True
    assert fixed["text_edge_clip"] == 3.0
    assert C.label_wishes(kw).off_y == -15.0
