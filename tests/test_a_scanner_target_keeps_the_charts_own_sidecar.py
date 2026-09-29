"""`<stem>.channels.json` is SHARED, so the scanner-target tool owns one key.

`build_scanin_target_from_render` wrote `{"layout": layout}` over the file.
`out_base` is `_chart_base(the measurement the user picked)`
(`ui/dialogs/scanin_target_dialog.py:520`) — that file's folder and stem and
nothing more — so choosing a ChromIQ run's own `.ti3` in the dialog's
i1Profiler mode aimed the write at that chart's own sidecar.

Measured on a sidecar holding what the shipped writers put there (challenge
round 36, 2026-09-22): SEVEN keys destroyed in one press, and the chart's own
`chromiq` layout, seed and recipe replaced by a render-derived block. The worst
of the seven is `colorimetric_reference`:
`workflow.verification_print.chart_conversion_state` reads it to REFUSE to
print a colorimetric chart through a profile, so losing it silently re-offers
the conversion that flag exists to forbid.

Every other writer of this file already read-modify-writes
(`chart_creator._embed_layout_geometry`, `_capture_printtarg_cht`,
`gamut_target.mark_chart_as_colorimetric`). This pins the last one.

THE SUBJECT IS THE WRITE, NOT THE GEOMETRY. `derive_grid_layout` needs a real
rendered chart, and the only ones committed are the i1Profiler probe TIFFs,
which are not on every machine — a test that skips there would have watched
this fault ship. So the geometry and the `.cht`/`.cie` build are stubbed and
every other line of the function is the shipped one. The end-to-end path stays
covered by `tests/test_grid_layout_from_render.py`.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

#: What the shipped writers leave in a ChromIQ chart's sidecar, and who reads
#: each one back. Every one of these was destroyed before the fix.
THE_CHARTS_OWN = {
    # ui/tiff_preview.py resolve_ink_channels
    "ink_channels": ["R", "G", "B"],
    # ui/tabs/tab_chart.py — restored into Create Chart when the chart loads
    "chart_notes": "Canon PRO-1000 / Moab Entrada 300",
    "run_description": "the run this chart belongs to",
    "stamp_commands": True,
    # Knut's K2 sidecar-precedence registry
    "create_chart_settings": {"targen": {"-f": 1200}},
    "printtarg_fields": {"-ii1": True},
    # workflow/verification_print.py chart_conversion_state
    "colorimetric_reference": "Moab-reference.ti3",
}

DERIVED = {"engine": "derived", "dpi": 600, "paper_mm": [210, 297],
           "patches": []}


@pytest.fixture
def run_the_tool(tmp_path, monkeypatch):
    """Call the shipped `build_scanin_target_from_render` with the two things
    it does not own stubbed out."""
    import workflow.grid_layout_from_render as grid
    import workflow.scanin_target as st

    monkeypatch.setattr(st, "_ordered_rgb100",
                        lambda p: [(0, 0, 0), (100, 100, 100)])
    monkeypatch.setattr(grid, "derive_grid_layout",
                        lambda tiffs, rgb100, locs=None: dict(DERIVED))
    monkeypatch.setattr(st, "build_scanin_target_from_paths",
                        lambda *a, **k: "built")

    def _call(stem: str = "chart"):
        pset = tmp_path / "patches.ti1"
        pset.write_text("TI1\n", encoding="utf-8")
        page = tmp_path / f"{stem}_01.tif"
        page.write_bytes(b"II*\x00")
        ti3 = tmp_path / f"{stem}.ti3"
        ti3.write_text("TI3\n", encoding="utf-8")
        # `_chart_base(the measurement the user picked)` — folder and stem.
        return st.build_scanin_target_from_render(
            pset, [page], ti3, ti3.with_name(ti3.stem))

    return _call


def test_the_charts_own_keys_all_survive(tmp_path, run_the_tool):
    sidecar = tmp_path / "chart.channels.json"
    sidecar.write_text(json.dumps(
        dict(THE_CHARTS_OWN,
             layout={"engine": "chromiq", "seed": 4711,
                     "recipe": {"patch_mm": 8.0}})), encoding="utf-8")

    run_the_tool()

    after = json.loads(sidecar.read_text(encoding="utf-8"))
    destroyed = sorted(k for k in THE_CHARTS_OWN if k not in after)
    assert destroyed == [], f"the scanner-target tool destroyed {destroyed}"
    for key, value in THE_CHARTS_OWN.items():
        assert after[key] == value, key
    # …and the one key it DOES own is the one it wrote.
    assert after["layout"]["engine"] == "derived"
    assert "seed" not in after["layout"]


def test_a_chart_with_no_sidecar_still_gets_one(tmp_path, run_the_tool):
    """The other half: nothing to merge means nothing changes about the tool."""
    run_the_tool()
    doc = json.loads((tmp_path / "chart.channels.json").read_text(encoding="utf-8"))
    assert list(doc) == ["layout"]
    assert doc["layout"]["engine"] == "derived"


@pytest.mark.parametrize("rubbish", ["{not json", "[]", '"a string"', "5"])
def test_a_sidecar_that_cannot_be_merged_is_replaced_not_fatal(
        tmp_path, run_the_tool, rubbish):
    """`json.loads` is happy with `[]`, `"x"` and `5`. None of them can be
    merged into, so the tool writes its own block rather than raising — an
    unreadable byte must not stop a scanner target being built."""
    sidecar = tmp_path / "chart.channels.json"
    sidecar.write_text(rubbish, encoding="utf-8")
    run_the_tool()
    doc = json.loads(sidecar.read_text(encoding="utf-8"))
    assert doc["layout"]["engine"] == "derived"


def test_the_write_is_a_read_modify_write():
    """The shape, not just the outcome: a later edit that rebuilds the dict
    from scratch passes the cases above only until somebody adds a key."""
    from workflow import scanin_target

    src = inspect.getsource(scanin_target.build_scanin_target_from_render)
    assert 'json.dumps({"layout": layout}' not in src, (
        "build_scanin_target_from_render is writing a FRESH dict over a sidecar "
        "six other keys live in — read it, set layout, write it back")
    assert "channels.is_file()" in src and 'doc["layout"] = layout' in src


def test_the_two_workflow_writers_of_this_sidecar_stay_read_modify_writers():
    """`workflow/scanin_target.py` and `workflow/gamut_target.py` each add ONE
    key to a sidecar six other keys live in, so each must read it first.

    `chart_creator._write_channel_sidecar` is deliberately NOT in this list: it
    runs at the head of a chart BUILD, where a fresh sheet legitimately replaces
    the old one's record, and the layout writers re-add their block straight
    afterwards.
    """
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for rel in ("workflow/scanin_target.py", "workflow/gamut_target.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert ".channels.json" in src, f"{rel} no longer writes the sidecar"
        if 'json.dumps({"layout"' in src or 'json.dumps({"colorimetric' in src:
            offenders.append(rel)
    assert offenders == [], f"{offenders} write the shared sidecar from scratch"
