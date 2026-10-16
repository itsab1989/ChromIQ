"""#211: Check & Refine counts every reading, also when locations repeat.

The #211 user's Profile Quality window said "2 of 420 patches above your
tolerance (0.5%)" for a 1,680-reading measurement converted from i1Profiler,
whose four pages each name their patches A1 … T21 (420 distinct SAMPLE_LOC
values). profcheck checked 1,680 patches; the plan keyed them by location and
kept the last of each. Every line profcheck prints is now one patch, a
location shared by several patches never merges them, and a file with no
SAMPLE_LOC (profcheck then prints no " @ ") is counted too.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from workflow import refine_plan as rp
from workflow.profcheck_runner import (ProfcheckRunner, parse_refine_patches,
                                       strips_to_refine, write_refine_strips)

LETTERS = "ABCDEFGHIJKLMNOPQRST"          # 20 strips x 21 places = 420


def _line(i: int, loc: "str | None", de: float) -> str:
    at = f" @ {loc}" if loc else ""
    return (f"[{de:.6f}] {i}{at}: 0.50000000 0.50000000 0.50000000 -> "
            f"50.000000 {de:.6f} 0.000000 should be 50.000000 0.000000 "
            f"0.000000")


def _the_211_shape(with_locs: bool = True) -> "tuple[str, list]":
    """1,680 readings on four pages sharing A1 … T21; on page 3 patch C5 and
    on page 4 patch I7 are above 2.0, everything else at 0.5. Same location
    on another page (C5 of page 1) is fine, so a plan keyed by location sees
    whichever page came last."""
    lines, want = ["No of test patches = 1680"], []
    i = 0
    for page in range(4):
        for s in LETTERS:
            for n in range(1, 22):
                i += 1
                loc = f"{s}{n}"
                de = 0.5
                if (page, loc) in ((2, "C5"), (3, "I7")):
                    de = 3.0
                lines.append(_line(i, loc if with_locs else None, de))
                want.append((i, loc, de))
    lines.append("Profile check complete, errors(CIEDE2000): max. = 3.000000, "
                 "avg. = 0.503571, RMS = 0.5")
    return "\n".join(lines) + "\n", want


def _result(text: str):
    pr = ProfcheckRunner(SimpleNamespace())
    return pr.parse_results(text)


def test_profcheck_result_has_one_entry_per_reading():
    text, want = _the_211_shape()
    res = _result(text)
    assert len(res.patch_errors) == 1680
    assert len(res.patch_rows) == 1680
    assert res.patch_rows[0] == ("1", "A1", 0.5)
    assert len({sid for sid, _l, _d in res.patch_rows}) == 1680


def test_the_plan_counts_1680_patches_and_both_above_the_limit():
    text, _ = _the_211_shape()
    res = _result(text)
    patches = rp.parse_patches(res.raw_log, res.patch_errors)
    assert len(patches) == 1680
    plan = rp.build_plan(patches, 2.0, "ΔE00")
    assert plan.n_total == 1680            # was 420
    assert plan.n_over == 2                # C5 of page 3 and I7 of page 4
    assert plan.shared_locations == 420 and plan.no_location == 0
    assert sorted(a.strip for a in plan.offered) == ["C", "I"]
    # the window's line says it
    t = rp.plan_text(plan, res.avg_de, res.peak_de)
    assert "1680" in t.over and "420" not in t.over


def test_a_location_shared_by_four_patches_is_four_patches():
    """Distinct patches are never merged because they share a location:
    page 1's C5 at 0.5 does not hide page 3's C5 at 3.0, and the reverse
    order does not either."""
    text, _ = _the_211_shape()
    lines = text.splitlines()
    head, body, tail = lines[:1], lines[1:-1], lines[-1:]
    for order in (body, list(reversed(body))):
        patches = rp.parse_patches("\n".join(head + order + tail))
        c5 = [p for p in patches if p.loc == "C5"]
        assert len(c5) == 4
        assert sorted(p.de for p in c5) == [0.5, 0.5, 0.5, 3.0]
        assert len({p.sid for p in c5}) == 4


def test_no_blend_partner_is_taken_from_another_page():
    """The partly-read-as-its-neighbour test looks the neighbour up by
    location; a shared location names no one patch, so it is not used."""
    text, _ = _the_211_shape()
    plan = rp.build_plan(rp.parse_patches(text), 2.0)
    assert all(a.kind != rp.BLEND for a in plan.offered)


def test_a_file_without_locations_is_counted_and_offers_no_strip():
    text, _ = _the_211_shape(with_locs=False)
    res = _result(text)
    assert len(res.patch_rows) == 1680
    assert all(loc == "" for _s, loc, _d in res.patch_rows)
    patches = rp.parse_patches(res.raw_log, res.patch_errors)
    assert len(patches) == 1680 and all(p.loc == "" for p in patches)
    assert patches[0].meas is not None          # its colours were read
    plan = rp.build_plan(patches, 2.0)
    assert (plan.n_total, plan.n_over, plan.no_location) == (1680, 2, 1680)
    assert plan.offered == [] and plan.chosen_patches(False) == []
    # the legacy strip helper puts a reading named by its id in no strip
    assert strips_to_refine(res.patch_errors, 2.0) == []


def test_a_chart_chromiq_made_is_unchanged():
    """Unique locations: the plan is what it always was."""
    lines = [_line(i + 1, f"{s}{n}", 3.0 if (s, n) == ("B", 4) else 0.5)
             for i, (s, n) in enumerate((s, n) for s in "ABC"
                                         for n in range(1, 8))]
    plan = rp.build_plan(rp.parse_patches("\n".join(lines)), 2.0)
    assert (plan.n_total, plan.n_over) == (21, 1)
    assert plan.shared_locations == 0 and plan.no_location == 0
    assert plan.chosen(False) == [("B", 3.0)]


def test_the_refine_strips_file_visits_a_shared_location_once(tmp_path):
    text, _ = _the_211_shape()
    lines = text.splitlines()
    # page 1's C5 above the limit too: two patches filed under C5
    lines[1 + 2 * 21 + 4] = _line(47, "C5", 2.5)
    plan = rp.build_plan(rp.parse_patches("\n".join(lines)), 2.0)
    assert plan.n_over == 3
    pts = plan.chosen_patches(False)
    assert [loc for loc, _ in pts].count("C5") == 2      # both written
    f = write_refine_strips(tmp_path, "x", plan.chosen(False), patches=pts)
    assert parse_refine_patches(f) == ["C5", "I7"]      # one place to go to


def test_the_accuracy_view_matches_by_id_when_locations_repeat():
    from workflow.ti3_analysis import accuracy_from_profcheck
    text, want = _the_211_shape()
    res = _result(text)
    n = len(want)
    data = SimpleNamespace(
        xyz=np.full((n, 3), 20.0), rgb=np.tile([0.2, 0.5, 0.8], (n, 1)),
        has_device=True, sample_ids=[str(i) for i, _l, _d in want],
        sample_locs=[loc for _i, loc, _d in want])
    acc = accuracy_from_profcheck(data, res.patch_errors, res.patch_rows)
    assert acc.n == 1680
    assert abs(acc.mean_de - (1678 * 0.5 + 2 * 3.0) / 1680) < 1e-9
