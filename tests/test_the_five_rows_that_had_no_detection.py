"""B8-397: the five limit rows that had no detection method, and now have one.

Knut, 2026-09-18, approving the three proposals of S2w
(`docs/design/issue_182_answers.md`) after they had waited since 14 September:

    Implement the proposals. I have already proposed to change the heading from
    'Selected patches of the standard's chart' to 'Selected patches of the
    chart'. The help text can explain, as for all the other metrics, what the
    detection method is and how it is used, and if there are any requirements
    to the charts etc.

Three rules, five rows:

1. **The control strip is DECLARED BY THE CHART.** A sidecar
   ``<chart stem>.control-strip.json`` holding a name and the sample ids, or a
   CGATS ``CONTROL_STRIP_IDS`` keyword on the ``.ti1`` / ``.ti2`` naming the
   same. Computable at k ≥ 8, and the 95th-percentile row at k ≥ 20.
2. **The two gamut populations are ChromIQ's own.** Surface: a patch touching
   the device cube's surface, ``min(v, 100 - v) ≤ 2.0`` on one of R, G, B, ten
   of them. Outer: the top quarter by the reference's chroma, twenty of them.
3. **The heading changes with them**, which is what keeps 2 from being a third
   instance of attributing ChromIQ's own coverage to a standard.

**THE CHARTS HERE ARE REAL, in the layout the app writes**: a ``.ti2`` design
chart at the run root, a measured ``-verify.ti3`` in
``runs/run1/verifications/<date>/``, and where the case calls for one a real
declaration beside the chart. `build_report` is run exactly as the app runs
it, so the reference resolution, the yardstick and the sidecar lookup are all
the product's own and not a fixture's idea of them.

Two of the cases were written to fail and did: the first attempt put the
``.ti3`` at the run root, where `_find_reference_ti2` cannot pair it, and every
declaration went unread. A fixture that cannot reach the chart agrees with a
code that cannot either.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                              # noqa: E402
import pytest                                                   # noqa: E402

import workflow.measurement_report as mr                        # noqa: E402
from workflow import compliance_sets as cs                      # noqa: E402
from workflow.compliance_sets import N_A, factory_limits        # noqa: E402
from workflow.ti3_analysis import mark_verification_ti3         # noqa: E402

CONTROL_ROWS = ("control_strip_de00_avg", "control_strip_de00_max",
                "control_strip_de00_p95")


# --------------------------------------------------------------- the charts
def _xyz_d50(r, g, b):
    from workflow.i1profiler_import import _patch_xyz
    return mr._bradford_d65_to_d50(*_patch_xyz(float(r), float(g), float(b)))


def _lab_to_xyz(lab):
    L, a, b = lab
    fy = (L + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def f(t):
        return t ** 3 if t ** 3 > 0.008856 else (t - 16 / 116) / 7.787
    return f(fx) * 0.9642, f(fy) * 1.0, f(fz) * 0.8249


def _cgats(path: Path, patches, header=(), tag="CTI2", err=0.0):
    from workflow.icc_info import xyz_to_lab
    lines = [tag, "", 'DESCRIPTOR "b397"', *header, "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {len(patches)}", "BEGIN_DATA"]
    for sid, (r, g, b) in patches:
        x, y, z = _xyz_d50(r, g, b)
        if err:
            L, a, bb = xyz_to_lab((x / 100, y / 100, z / 100))
            x, y, z = (v * 100 for v in _lab_to_xyz((L, a, bb + err)))
        lines.append(f"{sid} {r:.2f} {g:.2f} {b:.2f} {x:.4f} {y:.4f} {z:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _interior(n):
    """*n* patches that touch no face of the device cube (every channel 10..90)."""
    out = []
    for j in range(n):
        t = j / max(1, n - 1)
        vals = [10 + 80 * (0.5 + 0.5 * math.sin(6.3 * t + k))
                for k in (0.0, 2.1, 4.2)]
        out.append((f"I{j + 1}", tuple(round(min(90.0, max(10.0, v)), 2)
                                       for v in vals)))
    return out


def _surface(n):
    """*n* patches that really touch a face: one channel pinned at 0 or 100."""
    out = []
    for j in range(n):
        v = 5 + (90 * j / max(1, n - 1))
        vals = [v, 100 - v, 50.0]
        vals[j % 3] = 100.0 if j % 2 else 0.0
        out.append((f"S{j + 1}", tuple(round(x, 2) for x in vals)))
    return out


def _strip(n, prefix="A"):
    return [(f"{prefix}{j + 1}",
             (float((5 + 4 * j) % 100), 50.0, float((60 - j) % 100)))
            for j in range(n)]


def build_chart(root: Path, *, interior=60, surface=0, strip=0,
                declare="sidecar", strip_on_chart=True, err=1.2,
                strip_name="Test strip") -> Path:
    """A real run folder; returns the measured ``.ti3``.

    *declare* is "sidecar", "keyword" or None. *strip_on_chart* False writes a
    declaration naming ids the chart does not contain, which is the case a
    fixture that only ever declares what it prints can never reach.
    """
    run = root / "runs" / "run1"
    ver = run / "verifications" / "2026-09-18"
    ver.mkdir(parents=True, exist_ok=True)
    patches = _interior(interior) + _surface(surface)
    ids = [sid for sid, _ in _strip(strip)]
    if strip and strip_on_chart:
        patches = patches + _strip(strip)
    header = []
    if strip and declare == "keyword":
        header = [f'CONTROL_STRIP_NAME "{strip_name}"',
                  f'CONTROL_STRIP_IDS "{" ".join(ids)}"']
    _cgats(run / "chart.ti2", patches, header=header)
    if strip and declare == "sidecar":
        (run / "chart.control-strip.json").write_text(
            json.dumps({"name": strip_name, "sample_ids": ids}),
            encoding="utf-8")
    _cgats(ver / "chart.ti3", patches, tag="CTI3", err=err)
    return mark_verification_ti3(ver / "chart.ti3")


def report_of(ti3: Path) -> dict:
    return mr.build_report(ti3)


def rows_of(report: dict, set_id="custom_iso_12647_7") -> dict:
    """What the app's own sequence answers: build, judge, key by row.

    THE APP'S SEQUENCE, not two functions called by hand. `judge` asks
    `row_values`, `is_graded_sheet` and `row_verdict` in the order the report
    window does, against a real limit set, so a row that is computed and then
    dropped by the verdict rule cannot look computed here.
    """
    return {r["row_id"]: r for r in mr.judge(report, factory_limits(set_id))}


# ------------------------------------------------- 1. the control strip
def test_a_chart_that_declares_nothing_has_no_control_strip(tmp_path):
    rep = report_of(build_chart(tmp_path, interior=90, surface=20))
    block = rep["control_strip"]
    assert block["declared"] is False
    assert block["reason"] == mr.REASON_NO_CONTROL_STRIP
    rows = rows_of(rep)
    for rid in CONTROL_ROWS:
        assert rows[rid]["word"] == N_A, rid
        assert rows[rid]["reason"] == mr.REASON_NO_CONTROL_STRIP, rid


@pytest.mark.parametrize("declare", ["sidecar", "keyword"])
def test_both_declarations_are_read_and_both_name_the_strip(tmp_path, declare):
    """The sidecar and the CGATS keyword are the two S2w allows, and a chart
    may carry either. The NAME comes back either way, because a report that
    says "the strip is too short" is more use when it can say which strip."""
    rep = report_of(build_chart(tmp_path, interior=90, surface=20, strip=20,
                                declare=declare, strip_name="Wedge 2026"))
    block = rep["control_strip"]
    assert block["declared"] is True
    assert block["source"] == declare
    assert block["name"] == "Wedge 2026"
    assert block["declared_ids"] == 20 and block["n"] == 20
    rows = rows_of(rep)
    for rid in CONTROL_ROWS:
        assert rows[rid]["value"] is not None, rid
        assert rows[rid]["word"] != N_A, rid


def test_seven_is_too_few_and_eight_is_enough(tmp_path):
    """The threshold S2w names, driven from both sides.

    MUTATION: raise `CONTROL_STRIP_MIN` to 9 and the eight-patch half goes red;
    lower it to 7 and the seven-patch half does.
    """
    assert mr.CONTROL_STRIP_MIN == 8
    seven = rows_of(report_of(build_chart(tmp_path / "seven", interior=90,
                                          surface=20, strip=7)))
    for rid in CONTROL_ROWS:
        assert seven[rid]["word"] == N_A, rid
        assert seven[rid]["reason"] == mr.REASON_CONTROL_STRIP_TOO_SMALL, rid
    eight = rows_of(report_of(build_chart(tmp_path / "eight", interior=90,
                                          surface=20, strip=8)))
    assert eight["control_strip_de00_avg"]["value"] is not None
    assert eight["control_strip_de00_max"]["value"] is not None


def test_nineteen_cannot_carry_a_95th_percentile_and_twenty_can(tmp_path):
    """*"because its nearest rank ceil(0.95 k) equals k for every k below 20
    and it would simply repeat the largest"*.

    So the row is WITHHELD below twenty rather than published as a copy of the
    row above it, and the two rows above it are judged at the same time.

    MUTATION: drop the `p95_eligible` guard in `control_strip_block` and the
    nineteen half goes red on the reason AND on the value being the largest.
    """
    assert mr.CONTROL_STRIP_P95_MIN == 20
    r19 = report_of(build_chart(tmp_path / "n19", interior=90, surface=20,
                                strip=19))
    b19 = r19["control_strip"]
    assert b19["eligible"] is True and b19["p95_eligible"] is False
    assert b19["p95"] is None
    rows19 = rows_of(r19)
    assert rows19["control_strip_de00_avg"]["value"] is not None
    assert rows19["control_strip_de00_max"]["value"] is not None
    assert rows19["control_strip_de00_p95"]["word"] == N_A
    assert rows19["control_strip_de00_p95"]["reason"] == \
        mr.REASON_CONTROL_STRIP_TOO_SMALL
    # …and the reason it is withheld: at nineteen it would BE the largest.
    assert math.ceil(19 * 0.95) == 19

    r20 = report_of(build_chart(tmp_path / "n20", interior=90, surface=20,
                                strip=20))
    b20 = r20["control_strip"]
    assert b20["p95_eligible"] is True and b20["p95"] is not None
    assert rows_of(r20)["control_strip_de00_p95"]["value"] == b20["p95"]
    assert math.ceil(20 * 0.95) == 19


def test_a_declaration_naming_patches_the_chart_does_not_have(tmp_path):
    """A sidecar can name anything; the chart is what decides.

    The strip is declared with twelve ids and the chart carries none of them,
    so `n` is zero and the row says so with the count in it. Nothing raises,
    and nothing is invented.
    """
    rep = report_of(build_chart(tmp_path, interior=90, surface=20, strip=12,
                                strip_on_chart=False))
    block = rep["control_strip"]
    assert block["declared"] is True and block["declared_ids"] == 12
    assert block["n_present"] == 0 and block["n"] == 0
    assert block["reason"] == mr.REASON_CONTROL_STRIP_TOO_SMALL
    for rid in CONTROL_ROWS:
        assert rows_of(rep)[rid]["word"] == N_A, rid


def test_an_unreadable_sidecar_leaves_the_chart_where_it_was(tmp_path):
    """Half a JSON file is not a control strip, and it is not a crash either.

    The chart goes back to being one that declares nothing, which is the state
    every chart on every user's disk is in today.
    """
    ti3 = build_chart(tmp_path, interior=90, surface=20, strip=20)
    side = tmp_path / "runs" / "run1" / "chart.control-strip.json"
    assert side.is_file()
    side.write_text('{"name": "broken", "sample_ids": [', encoding="utf-8")
    rep = report_of(ti3)
    assert rep["control_strip"]["declared"] is False
    assert rep["control_strip"]["reason"] == mr.REASON_NO_CONTROL_STRIP


def test_a_sidecar_beside_the_run_chart_reaches_a_dated_verification(tmp_path):
    """**FOUND ON SCREEN, on the demo pack.** A dated verification is paired
    with the SNAPSHOT of the chart in its own ``chart/`` folder, so a sidecar
    written beside the run's chart, which is the file a user opens and names,
    was never looked at: the window said "this chart declares no control
    strip" about a chart that declared one.

    The declaration is now looked for beside every chart the report would pair
    the measurement with, in the report's own pairing order.

    MUTATION: search only beside the winning chart and this goes red.
    """
    ti3 = build_chart(tmp_path, interior=90, surface=20, strip=20)
    run = tmp_path / "runs" / "run1"
    side = run / "chart.control-strip.json"
    ids = json.loads(side.read_text(encoding="utf-8"))["sample_ids"]
    # move the measurement into a dated verification with its own snapshot,
    # which is the layout the app writes
    dated = run / "verifications" / "2026-09-19"
    (dated / "chart").mkdir(parents=True)
    moved = dated / ti3.name
    ti3.replace(moved)
    (run / "chart.ti2").replace(dated / "chart" / f"{moved.stem}.ti2")
    from workflow.measurement_report import _find_reference_ti2
    assert _find_reference_ti2(moved).parent.name == "chart", \
        "the fixture does not reproduce the pairing this is about"
    assert side.is_file() and not (dated / "chart" /
                                   f"{moved.stem}.control-strip.json").is_file()
    block = report_of(moved)["control_strip"]
    assert block["declared"] is True and block["declared_ids"] == len(ids)
    assert block["n"] == len(ids)


def test_the_sidecar_outranks_the_keyword(tmp_path):
    """Both present: the sidecar wins, because it is the one a user can edit
    without rewriting a chart file."""
    ti3 = build_chart(tmp_path, interior=90, surface=20, strip=20,
                      declare="keyword", strip_name="From the keyword")
    (tmp_path / "runs" / "run1" / "chart.control-strip.json").write_text(
        json.dumps({"name": "From the sidecar",
                    "sample_ids": [sid for sid, _ in _strip(20)]}),
        encoding="utf-8")
    block = report_of(ti3)["control_strip"]
    assert block["source"] == "sidecar" and block["name"] == "From the sidecar"


def test_a_ti1_that_carries_no_colour_column_can_still_declare_a_strip(tmp_path):
    """`parse_ti3` refuses a file with no measurement table, and a ``.ti1``
    need not have one. The keyword is read from the header instead.

    MUTATION: route `_cgats_keyword` through `parse_ti3` and this goes red.
    """
    ti3 = build_chart(tmp_path, interior=90, surface=20)
    run = tmp_path / "runs" / "run1"
    ids = " ".join(sid for sid, _ in _interior(90)[:20])
    (run / "chart.ti1").write_text(
        "CTI1\n\nDESCRIPTOR \"no colour columns\"\n"
        f'CONTROL_STRIP_IDS "{ids}"\n', encoding="utf-8")
    with pytest.raises(Exception):
        from workflow.ti3_analysis import parse_ti3
        parse_ti3(run / "chart.ti1")
    # the .ti2 is what `_find_reference_ti2` hands over; the .ti1 beside it is
    # the other file S2w names, and it is read too.
    decl = mr.control_strip_declaration(ti3, run / "chart.ti2")
    assert decl is not None and decl["source"] == "keyword"
    assert decl["file"] == "chart.ti1" and len(decl["ids"]) == 20


# ------------------------------------------- 2. the two gamut populations
def test_the_surface_population_is_the_patches_on_the_cube(tmp_path):
    """Nine is too few and ten is enough, on charts whose other patches touch
    no face at all.

    MUTATION: change `SURFACE_GAMUT_MIN` and one half or the other goes red;
    change `SURFACE_GAMUT_TOL` to 0.0 and both do, because the pinned channels
    are exactly 0 and 100 and nothing else comes within 2.
    """
    assert mr.SURFACE_GAMUT_MIN == 10 and mr.SURFACE_GAMUT_TOL == 2.0
    nine = report_of(build_chart(tmp_path / "nine", interior=60, surface=9))
    assert nine["gamut_populations"]["surface"]["n"] == 9
    assert nine["gamut_populations"]["surface"]["eligible"] is False
    rows = rows_of(nine)
    assert rows["surface_gamut_de00_avg"]["word"] == N_A
    assert rows["surface_gamut_de00_avg"]["reason"] == \
        mr.REASON_TOO_FEW_SURFACE_PATCHES

    ten = report_of(build_chart(tmp_path / "ten", interior=60, surface=10))
    assert ten["gamut_populations"]["surface"]["n"] == 10
    assert rows_of(ten)["surface_gamut_de00_avg"]["value"] is not None


def test_the_surface_rule_is_the_one_s2w_states(tmp_path):
    """``min(v, 100 - v) <= 2.0`` on at least ONE channel, not on all three.

    Driven on the block directly, because the arithmetic is what S2w fixes and
    the rest of this file drives it through the app.
    """
    ids = ["P1", "P2", "P3", "P4"]
    rgb = np.array([[50.0, 50.0, 50.0],      # interior
                    [1.5, 50.0, 50.0],       # one channel within 2.0 of 0
                    [50.0, 98.5, 50.0],      # one channel within 2.0 of 100
                    [50.0, 50.0, 97.0]])     # 3.0 off the face: not on it
    lab = [(50.0, 0.0, 0.0)] * 4
    ref = {sid: (50.0, 0.0, 0.0) for sid in ids}
    block = mr.gamut_populations_block(rgb, lab, ref, ids)["surface"]
    assert block["n_surface"] == 2


def test_the_outer_population_is_the_top_quarter_by_chroma(tmp_path):
    """Nineteen in the quarter is too few and twenty is enough.

    76 referenced patches give ceil(76/4) = 19, and 80 give 20, so the two
    charts differ by four patches and by the whole verdict.

    MUTATION: change `OUTER_GAMUT_MIN` or `OUTER_GAMUT_FRACTION` and one half
    goes red.
    """
    assert mr.OUTER_GAMUT_MIN == 20 and mr.OUTER_GAMUT_FRACTION == 0.25
    r76 = report_of(build_chart(tmp_path / "n76", interior=76))
    assert r76["gamut_populations"]["outer"]["n_referenced"] == 76
    assert r76["gamut_populations"]["outer"]["n"] == 19
    rows = rows_of(r76)
    assert rows["outer_gamut_226_de00_avg"]["word"] == N_A
    assert rows["outer_gamut_226_de00_avg"]["reason"] == \
        mr.REASON_TOO_FEW_OUTER_PATCHES

    r80 = report_of(build_chart(tmp_path / "n80", interior=80))
    assert r80["gamut_populations"]["outer"]["n"] == 20
    assert rows_of(r80)["outer_gamut_226_de00_avg"]["value"] is not None


def test_the_outer_quarter_is_ranked_by_the_AIM_and_not_by_the_PRINT():
    """The population is a property of the CHART, so the same chart picks the
    same patches however badly it printed. Ranking by the measured colour would
    let a bad print change which patches the row is about, which is a row that
    cannot be compared with itself over time.

    MUTATION: rank by `lab` instead of by `ref` and this goes red: the measured
    values here are deliberately in the opposite order.
    """
    ids = [f"P{i}" for i in range(80)]
    ref = {sid: (50.0, float(i), 0.0) for i, sid in enumerate(ids)}
    lab = [(50.0, float(79 - i), 0.0) for i in range(80)]
    rgb = np.full((80, 3), 50.0)
    block = mr.gamut_populations_block(rgb, lab, ref, ids)["outer"]
    assert block["n"] == 20
    # the aim's top quarter is a* 60..79, whose chroma floor is 60
    assert block["chroma_floor"] == 60.0


def test_a_chart_with_no_reference_at_all_says_so_rather_than_too_few():
    """"No aim values" and "too few patches" send a reader to different places,
    so they are different reasons.

    MUTATION: fold the two together and this goes red.
    """
    ids = [f"P{i}" for i in range(40)]
    rgb = np.array([[0.0, 50.0, 50.0]] * 40)
    lab = [(50.0, 0.0, 0.0)] * 40
    blocks = mr.gamut_populations_block(rgb, lab, {}, ids)
    assert blocks["surface"]["n_surface"] == 40 and blocks["surface"]["n"] == 0
    assert blocks["surface"]["reason"] == mr.REASON_NO_REFERENCE
    assert blocks["outer"]["reason"] == mr.REASON_NO_REFERENCE


def test_a_declared_strip_with_no_reference_says_no_reference():
    ids = [f"A{i}" for i in range(12)]
    lab = [(50.0, 0.0, 0.0)] * 12
    block = mr.control_strip_block(lab, {}, ids,
                                   {"name": "s", "ids": ids, "source": "sidecar"})
    assert block["n_present"] == 12 and block["n"] == 0
    assert block["reason"] == mr.REASON_NO_REFERENCE


# ------------------------------------------- 3. nothing on a disk changes
def test_a_report_saved_before_this_release_says_not_computed(tmp_path):
    """Rule 1 of this change: a report on a user's disk must still open and
    still say what it said. A report written before the two blocks existed
    carries neither, which is NOT "this chart declares no strip": it says
    nothing at all, and the sentence for `not_computed` says exactly that.

    MUTATION: default the missing blocks to `no_control_strip` and this goes
    red, because the window would tell a reader to add a declaration to a chart
    it never looked at.
    """
    rep = report_of(build_chart(tmp_path, interior=90, surface=20, strip=20))
    rep.pop("control_strip")
    rep.pop("gamut_populations")
    vals = mr.row_values(rep)
    for rid in CONTROL_ROWS + ("surface_gamut_de00_avg",
                               "outer_gamut_226_de00_avg"):
        assert vals[rid]["value"] is None, rid
        assert vals[rid]["reason"] == mr.REASON_NOT_COMPUTED, rid


def test_a_run_bound_before_this_release_is_not_reported_as_edited():
    """**MEASURED, and it was a real regression.** The five rows arrive in the
    two Custom columns with a limit on them, so a run bound to one of those
    columns before this release holds a ``?`` where the set now holds 2.0.
    `is_edited` compared the two and answered True: a run whose limits nobody
    had touched was labelled edited.

    Nothing a user can do produces a ``?``, so a stored one is never an edit.

    MUTATION: drop the `b.kind == "unknown"` clause in `is_edited` and this
    goes red.
    """
    from workflow.compliance_sets import (effective_limits, is_edited,
                                          limits_from_json, limits_to_json)
    for sid in ("custom_iso_12647_7", "custom_iso_12647_8"):
        stored = limits_to_json(effective_limits(sid, None))
        for rid in CONTROL_ROWS + ("surface_gamut_de00_avg",
                                   "outer_gamut_226_de00_avg"):
            assert stored[rid] is not None, rid   # the set really limits it now
            stored[rid] = "?"                     # what the old build wrote
        assert not is_edited(limits_from_json(stored), sid, None), sid
    # …and a real edit is still an edit.
    sid = "custom_iso_12647_7"
    real = limits_to_json(effective_limits(sid, None))
    real["all_de00_avg"] = 2.7
    assert is_edited(limits_from_json(real), sid, None)


def test_a_row_the_older_build_never_had_is_not_an_edit_either():
    """**THE SAME FAULT, THROUGH THE OTHER DOOR, AND IT SHIPPED ONCE.**

    The test above carved out a stored ``?``. A row that is simply ABSENT from
    the stored copy was not carved out, and adding a row re-opens the hole: the
    two repeatability rows landed on 2026-09-21, so every run bound by any
    earlier ChromIQ held a 30-row copy against a 32-row set, `is_edited` read
    each missing row as a limit the user had removed, and the run read
    "(edited)" on screen, in the PDF, and in every report the build saved.

    A row the user really did remove is NOT absent: `limits_to_json` writes
    every row of the column, and a removed limit goes to disk as ``null``. So
    absence and removal are distinguishable, and only removal is an edit.

    MUTATION: drop the ``if rid not in ref or rid not in values: continue``
    clause in `compliance_sets.is_edited` and this goes red on all five
    editable sets.
    """
    from workflow.compliance_sets import (SETS, effective_limits, is_edited,
                                          limits_from_json, limits_to_json)
    new_rows = ("repeat_patches_de00_max", "repeat_measurement_de00_max")
    editable = [s.id for s in SETS if s.editable]
    assert editable, "no editable set to measure"
    for sid in editable:
        full = limits_to_json(effective_limits(sid, None))
        older = {r: v for r, v in full.items() if r not in new_rows}
        assert len(older) == len(full) - len(new_rows), sid
        assert not is_edited(limits_from_json(older), sid, None), sid

    # A REMOVED LIMIT IS STILL AN EDIT, which is what keeps this honest: the
    # same row, present and null, must read the opposite way.
    sid = "chromiq_default"
    removed = limits_to_json(effective_limits(sid, None))
    assert removed["repeat_patches_de00_max"] is not None
    removed["repeat_patches_de00_max"] = None
    assert is_edited(limits_from_json(removed), sid, None)

    # …and a row a LATER ChromIQ wrote, which CH-20 keeps, is not an edit of a
    # set that does not define it.
    later = limits_to_json(effective_limits(sid, None))
    later["a_row_a_later_chromiq_added"] = 2.5
    assert not is_edited(limits_from_json(later), sid, None)


def test_a_chart_with_no_declaration_behaves_exactly_as_it_did(tmp_path):
    """The other half of rule 1: a chart without a control strip must behave as
    it does today. Its three control-strip rows read N-A, as they did when the
    rows had no detection at all, and every other row is untouched."""
    rep = report_of(build_chart(tmp_path, interior=90, surface=20))
    rows = rows_of(rep, "chromiq_default")
    # On ChromIQ default the three control-strip rows carry no limit, so they
    # produce no verdict cell at all, exactly as before.
    assert all(rid not in rows for rid in CONTROL_ROWS)
    assert rows["all_de00_avg"]["value"] is not None


# --------------------------------------- the reasons reach the window
@pytest.mark.parametrize("code", ["no_control_strip", "control_strip_too_small",
                                  "too_few_surface_patches",
                                  "too_few_outer_patches"])
def test_every_new_reason_becomes_a_sentence_that_says_what_to_do(qapp, code,
                                                                  tmp_path):
    """These go through the same `_reason_sentence` path as the other ten.

    K22 (Knut, 2026-09-23) replaced "each names the thing to change" with
    *"each names the thing missing in the measured chart"*: a report may reach
    a customer, so it states what is missing and never what to add or where.

    MUTATION: remove any one of the four keys from `_reason_sentence` and this
    goes red with an empty sentence.
    """
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    rep = report_of(build_chart(tmp_path, interior=60, surface=9, strip=7))
    text = MeasurementReportDialog._reason_sentence(None, code, rep)
    assert text, code
    assert "the measured chart" in text, text
    for instruction in ("declare a", "add ", "use a ", "create chart",
                        "control-strip.json"):
        assert instruction not in text.lower(), (instruction, text)


def test_the_strip_sentence_names_the_count_and_both_thresholds(tmp_path):
    """The shape `_small_sample_sentence` was rewritten into after a round
    measured it saying *"the chart has 20 patches; at least 20 are needed"*:
    the count the chart supplied, and the count that is wanted.

    A strip of nineteen judges two rows and not the third, so the sentence
    beside that third row has to name both numbers.
    """
    from ui.dialogs.measurement_report_dialog import _control_strip_sentence
    rep = report_of(build_chart(tmp_path, interior=90, surface=20, strip=19))
    text = _control_strip_sentence(rep)
    assert "19 patches" in text
    assert f"least {mr.CONTROL_STRIP_MIN} are needed" in text
    assert f"least {mr.CONTROL_STRIP_P95_MIN} for the 95th" in text


def test_the_count_bearing_sentences_have_a_singular_form(tmp_path):
    """CLAUDE.md: count-bearing messages get explicit singular and plural
    variants, never "(s)". Each of these three can reach one.

    MUTATION: drop any singular branch and this goes red.
    """
    from ui.dialogs.measurement_report_dialog import (_control_strip_sentence,
                                                      _outer_gamut_sentence,
                                                      _surface_gamut_sentence)
    one_strip = _control_strip_sentence({"control_strip": {"n": 1}})
    assert "has one patch" in one_strip and " 1 patches" not in one_strip
    one_surf = _surface_gamut_sentence(
        {"gamut_populations": {"surface": {"n": 1}}})
    assert "one patch of the measured chart sits" in one_surf
    assert " 1 patches" not in one_surf
    one_outer = _outer_gamut_sentence({"gamut_populations": {"outer": {"n": 1}}})
    assert "is one patch" in one_outer and " 1 patches" not in one_outer


def test_the_closing_note_does_not_name_one_remedy_for_every_reason():
    """**PHOTOGRAPHED ON SCREEN, 2026-09-18.** The note under the results
    table listed *"Control-strip patches, average (… Declare a longer strip, or
    add its patches to the chart)"* and then closed with *"add the missing
    patches to the chart in Create Chart to have it checked"*, one line below.
    A reader is told two different things about the same row, and the second
    one is wrong: a control strip is missing a DECLARATION, not patches.

    True of every reason while every reason meant "the chart is short of
    patches", and false the moment three of them stopped meaning that.

    MUTATION: put either old sentence back and this goes red.
    """
    import inspect

    from ui.dialogs import measurement_report_dialog as d
    from workflow.measurement_messages import M_REPORT_CHART_MISMATCH
    dead = "add the missing patches to the chart in Create Chart to have it"
    src = inspect.getsource(d)
    assert dead not in src, (
        "the closing note still names one remedy for every reason")
    assert dead not in M_REPORT_CHART_MISMATCH.body
    # …and it points at the reasons, which each carry their own lever. The
    # word was "reason" until 2026-09-21, when Knut's ruling turned each of
    # those reasons into a numbered NOTE beside the cell it explains; the
    # closing sentence moved under that list and says "note" for the thing
    # the reader is now looking at. What it must not do, and the whole point
    # of this test, is name one remedy for all of them.
    # beta 37, round B L5: the notes are causes, so the sentence says why
    assert "each note above says why" in src.lower()
    assert "names what that row needs" in M_REPORT_CHART_MISMATCH.body.lower()
