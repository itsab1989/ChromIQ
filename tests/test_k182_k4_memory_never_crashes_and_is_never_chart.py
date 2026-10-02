"""#182 K4, review AN: the yellow memory (`<stem>.confirmed.json`) is data on
disk, so it must never crash what reads it, and it is never part of a chart.

1. A memory whose hash matches its `.ti3` but whose CONTENTS are damaged (a
   hand edit, a `.ti3` and its memory edited together) made
   `confirmed_patches.load`, `confirmed_locations` and `carry` raise. `carry`
   runs inside the verification filing (`mark_verification_ti3`,
   `TabMeasure._finalize_verification`, which catches only OSError), so a
   damaged memory could break filing a measurement. Bad entries are skipped.

2. While a verification is read, the memory is written beside its working
   file at the root of `verifications/`. A session ended with "Discard and
   stop" (or a crash) leaves it there, and the verification slot counts EVERY
   file at that root as chart: the memory was then snapshotted into the next
   date's `chart/`, and Restore Used Chart stashed and archived it. It is
   excluded exactly as the working `.ti3` already is.
"""
from __future__ import annotations

import json

import pytest

from workflow import confirmed_patches as cp

_GOOD = {"kind": "confirmed", "de": 105.0, "prev_de": 104.0,
         "exp_lab": [1, 2, 3], "meas_lab": [4, 5, 6], "shift": [3, 3, 3],
         "standout": None}


def _ti3(folder, stem="chart"):
    p = folder / f"{stem}.ti3"
    p.write_text("CTI3\nBEGIN_DATA_FORMAT\nSAMPLE_ID\nEND_DATA_FORMAT\n"
                 "BEGIN_DATA\n1\nEND_DATA\n", encoding="utf-8")
    return p


@pytest.mark.parametrize("patches", [
    {"A1": dict(_GOOD, de="abc")},
    {"A1": dict(_GOOD, exp_lab=None)},
    {"A1": dict(_GOOD, meas_lab=["a", "b", "c"])},
    {"A1": dict(_GOOD, standout={})},
    ["A1"],
], ids=["de_text", "lab_null", "lab_text", "standout_dict", "patches_list"])
def test_a_damaged_memory_with_a_matching_hash_never_raises(tmp_path, patches):
    ti3 = _ti3(tmp_path)
    cp.confirmed_path(ti3).write_text(json.dumps(
        {"schema": 1, "ti3_sha256": cp.ti3_sha256(ti3), "mode": "strip",
         "patches": {"B2": _GOOD, **patches} if isinstance(patches, dict)
         else patches}), encoding="utf-8")
    data = cp.load(ti3)
    assert data is not None
    want = {"B2"} if isinstance(patches, dict) else set()
    assert cp.confirmed_locations(ti3) == want      # the good entry survives
    from workflow.ti3_analysis import mark_verification_ti3
    marked = mark_verification_ti3(ti3)             # carry() inside
    assert cp.confirmed_locations(marked) == want


def test_a_stale_verification_memory_is_not_chart(tmp_path):
    from core.file_manager import Project
    from workflow import chart_slot, verify_chart_snapshot as vcs
    proj = Project.create(tmp_path / "Demo", "Demo")
    run = proj.current_run()
    vdir = run.verifications_dir
    vdir.mkdir(parents=True, exist_ok=True)
    stem = run.verify_stem
    for ext in (".ti1", ".ti2"):
        (vdir / f"{stem}{ext}").write_text("chart", encoding="utf-8")
    # what a discarded verification session leaves at the root
    work = _ti3(vdir, stem)
    cp.write(work, {"A1": _GOOD}, "strip")
    mem = cp.confirmed_path(work)
    assert mem.parent == vdir and mem.is_file()
    names = {p.name for p in vcs.live_chart_files(run)}
    assert names == {f"{stem}.ti1", f"{stem}.ti2"}
    assert mem.name not in {p.name for p in vcs.files_to_snapshot(run)}
    v = run.new_verification()
    slot = chart_slot.slot_for_verification(v)
    assert mem.name not in {p.name for p in slot.live_files()}
