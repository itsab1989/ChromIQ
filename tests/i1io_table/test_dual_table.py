"""The i1Pro 2 dual scan ON THE i1iO 2 TABLE (2026-11-18, a first try): the table side.

The owner's ruling (18 Nov 2026): "you have the commands so you will do patch by patch and strip
mode so it can be tried. as long as there is no chance for physical harm of the table this is ok
so we can collect data". What i1Profiler 3.8.6 sent on the volunteer's table for a dual row
(private analysis of 18 Nov 2026, section 2; recording B, all five accepted rows alike):

    lamp   p0, (lights off), c4, p0, m0 to the row start @300, d1 016d, p0, m2 @132, a3, c3, lamp
    UV     p0, m0 ZERO-LENGTH to the position just read, c4, d1 00d2, p0, m2 back @132, a3, c3, UV

Only two lines are new against the released allow-list, d1 00d2 and m2 at 132, and each is
allowed only while the job's dual row reads the pass it belongs to. With the dual scan off the
table job is the released one (every released test in this folder stays as it was).
"""
from __future__ import annotations

import json

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import read_page, small_sheet
from tests.i1io_table.test_job_safety import shaped_sheet
from workflow.dual_scan import storage as S
from workflow.dual_scan.scale import ScaleChoice
from workflow.i1io.table import caps as cp
from workflow.i1io.table import dual_rows as dl
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import lines as cl
from workflow.i1io.table import scan as sc
from workflow.i1io.table import session_table as tbl
from workflow.i1io.table import spot as sp

STRIP = ["-v", "-c", "1", "chart"]
SPOT = ["-v", "-c", "1", "-p", "chart"]

#: recorded byte for byte (B 44.669, 49.904, 50.112, 50.144: the first accepted dual row)
REC_LAMP_M2 = b";m204f306a0008466\r"
REC_ZERO_M0 = b";m004f306a0012c3e\r"
REC_D1_UV = b";d100d23a\r"
REC_UV_M2 = b";m2fa6706ad0084fb\r"


def dual_setup(chosen="M2"):
    ch = ScaleChoice.standard()
    return dl.DualSetup(tuple(S.helper_args(ch, "table", chosen)), ch.value, ch.source, chosen,
                        "table")


def long_sheet():
    """Patches long enough for a dual row at 132 (10.6 mm, the recorded chart's pitch)."""
    return shaped_sheet([6, 6], along=10.6, across=10.0, w=210.0, h=297.0)


def _job(tmp_path, args=STRIP, sheet=None, faults=None, dual=True, chosen="M2", **kw):
    sheet = sheet or long_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False, faults=faults, **kw)
    if dual:
        job.dual = dual_setup(chosen)
    rep = job.set_options(args)
    assert rep.ok, (rep.reason, rep.detail)
    return job, sim, helper, run, H.Person(job, sim, None)


def _ready(job, p, steps=("open", "calibrate", "align")):
    for s in steps:
        r = p.drive(getattr(job, s)())
        assert r.ok, (s, r.reason, r.detail)


# ---- the allow-list: each new line only in its recorded place -------------------------------

def test_the_new_lines_are_the_recorded_bytes():
    # the form, byte for byte. 4.3.53: the recorded row reached X -1433, beyond the old fixed
    # right edge (-1384) that kept ChromIQ's own rows off it; that edge is gone, so ChromIQ's
    # builder now makes i1Profiler's own line, byte for byte
    assert geo._line("m2", 1267, 1696, 132) == REC_LAMP_M2
    assert geo._line("m2", -1433, 1709, 132) == REC_UV_M2
    assert geo.m2_line(1267, 1696, 132, dual=True) == REC_LAMP_M2
    assert geo.m2_line(-1433, 1709, 132, dual=True) == REC_UV_M2
    with pytest.raises(geo.AreaRefused):
        geo.m2_line(geo.CAP_AREA.xmin - 1, 1709, 132, dual=True)
    assert geo.m0_line(1267, 1696) == REC_ZERO_M0
    assert cl.C_DUAL_FIXED["scan_d1_uv"] == REC_D1_UV
    assert geo.DUAL_M2_SPEEDS == (132,)


INSIDE_UV_M2 = geo._line("m2", -1300, 1709, 132)


def test_without_a_dual_phase_the_allow_list_is_the_released_one():
    for line in (REC_D1_UV, REC_LAMP_M2, INSIDE_UV_M2):
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(line)
        with pytest.raises(tbl.ForbiddenLine):
            cl.wire_gate(line)
    with pytest.raises(geo.AreaRefused):
        geo.m2_line(1267, 1696, 132)
    assert cl.classify(cl.C_FIXED["scan_d1"]) == ("d1", False, "scan_d1")


def test_each_new_line_only_in_its_pass():
    # m2 at 132: in either pass of a dual row; d1 210 only in the UV pass, d1 365 never there
    assert cl.classify(REC_LAMP_M2, "lamp")[2] == "scan move"
    assert cl.classify(INSIDE_UV_M2, "uv")[2] == "scan move"
    assert cl.classify(REC_D1_UV, "uv") == ("d1", False, "scan_d1_uv")
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(REC_D1_UV, "lamp")
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(cl.C_FIXED["scan_d1"], "uv")
    assert cl.classify(cl.C_FIXED["scan_d1"], "lamp")[2] == "scan_d1"


def test_a_dual_row_never_combines_132_with_another_speed():
    for v in geo.RECORDED_M2_SPEEDS:
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(geo.m2_line(1267, 1696, v), "lamp")
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(REC_LAMP_M2, "neither")


def test_a_dual_plan_is_refused_at_any_other_speed_or_longer_than_the_longest_uv_pass():
    pts = [sc.Patch(str(k), f"A{k}", (-1250 + 100 * k, 1700), half_mm=5.3) for k in range(20)]
    p = sc.plan_row("r", (-1350, 1700), (900, 1700), 168, pts, dual=True)
    with pytest.raises(sc.PlanRefused):
        sc.check_plan(p)
    p = sc.plan_row("r", (-1350, 1700), (900, 1700), 132, pts, dual=True)
    sc.check_plan(p)
    p.N = sc.DUAL_N_MAX + 10
    with pytest.raises(sc.PlanRefused):
        sc.check_plan(p)


# ---- with the dual scan off nothing changes --------------------------------------------------

def test_dual_off_sends_no_dual_line_and_keeps_the_released_wire_gate(tmp_path, monkeypatch):
    from tests.i1io_table import session_sim as ss
    monkeypatch.setattr(ss.SimTransport, "gate", None, raising=False)
    job, sim, helper, run, p = _job(tmp_path, dual=False)
    _ready(job, p)
    read_page(job, p)
    # 2026-11-21 fix round (review m-5): every session's wire gate holds the table (a detour
    # move only while the way home is sent); with no dual phase it lets through what the released
    # wire_gate lets through, and refuses a dual line
    gate = job.transport.gate
    for raw in (b";d100d23a\r",):
        with pytest.raises(tbl.ForbiddenLine):
            gate(raw)
    assert gate(b";s022\r") == cl.wire_gate(b";s022\r")
    sent = [ln.encode() + b"\r" if not ln.endswith("\r") else ln.encode() for ln in sim.received]
    assert not any(ln.startswith(b";d100d2") for ln in sent)
    assert not any(ln.startswith(b";m2") and geo.decode_xyv(ln)[3] == 132 for ln in sent)
    assert all("--dual" not in " ".join(a) and "--i1io-table-dual" not in a
               for a in helper.started)
    assert all(getattr(r, "extra_args", ()) == () for r in helper.scan_readers)
    assert not sim.dual


def test_the_dual_caps_are_the_released_caps_plus_the_uv_passes():
    sheet = long_sheet()
    a, b = cp.caps_for_sheet(sheet), cp.caps_for_sheet(sheet, dual=True)
    assert b.lines > a.lines and b.moves >= a.moves
    assert cp.caps_for_sheet(sheet, dual=False) == a
    # 8 recorded lines of the UV pass, +1: the read-again after a question (4.3.47 MUST-1) OR
    # the UV pass's own reading when none is kept, never both (4.3.48 re-review NOTE-A;
    # test_dual_uv_pass_caps_are_tight.py); 2 movements (the zero m0, the scan move)
    assert cp.DUAL_UV_PASS == (8 + 1, 2)
    assert cp.DUAL_ROW == (cp.STRIP_ROW[0] + 9, cp.STRIP_ROW[1] + 2)


# ---- rows: the recorded dual row on the simulated table -------------------------------------

def _until(job, res, confirm):
    """Answer every question but *confirm* with yes (GO, first visit, the consent)."""
    while res.kind == J.Kind.NEEDS and res.confirm != confirm:
        res = job.answer(res.confirm, "yes")
    return res


def _row_lines(sim, n0):
    return [ln for ln in sim.received[n0:]]


def test_a_dual_row_is_the_recorded_sequence(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    n0 = len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "strip", (r.reason, r.detail)
    got = [ln[:3] for ln in _row_lines(sim, n0)]
    # 4.3.50: the first row starts from the FREE arm after the aims (no check move to mark 3
    # before it): two more readings of where the hand left it (the stillness pair), nothing else
    assert got == [";p0", ";p0", ";p0", ";c4", ";p0", ";m0", ";d1", ";p0", ";m2", ";a3", ";c3",
                   ";p0", ";m0", ";c4", ";d1", ";p0", ";m2", ";a3", ";c3", ";p0"]
    lines = _row_lines(sim, n0)
    assert lines[6] == ";d1016d35" and lines[14] == ";d100d23a"
    m2 = [geo.decode_xyv((ln + "\r").encode()) for ln in lines if ln.startswith(";m2")]
    assert [v for *_x, v in m2] == [132, 132]
    # the UV pass goes straight back over the same row, from where the lamp pass ended
    assert (m2[1][1], m2[1][2]) == geo.decode_xyv((lines[5] + "\r").encode())[1:3]
    # the recorded zero-length m0 goes to the position the p0 after the lamp pass reported
    # (4.3.47's less ideal simulated table: within a unit or two of the lamp pass's target)
    zero = geo.decode_xyv((lines[12] + "\r").encode())
    rec = _row_record(job)
    assert (zero[1], zero[2]) == tuple(rec["scan"]["lamp"]["end_xy"])
    assert abs(zero[1] - m2[0][1]) <= sc.ARRIVAL_UNITS and abs(zero[2] - m2[0][2]) <= \
        sc.ARRIVAL_UNITS
    assert sim.violations == []


def _row_record(job, name="p1_row1"):
    folder = next(iter(job.diag.folder.glob("row-*")))
    return json.loads((folder / f"{name}.row.json").read_text(encoding="utf-8"))


def test_every_dual_row_starts_at_the_same_end_as_recorded(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    read_page(job, p)
    starts = [geo.decode_xyv((ln + "\r").encode()) for ln in sim.received
              if ln.startswith(";m2")]
    lamp = starts[0::2]
    assert len(lamp) == 2 and all(a[1] > 0 or a[1] > starts[1][1] for a in lamp)
    assert lamp[0][1] == lamp[1][1] or abs(lamp[0][1] - lamp[1][1]) < 30


def test_a_dual_page_is_filed_with_m1_m2_and_build_profile_starts_at_the_choice(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, chosen="M2")
    _ready(job, p)
    rows = read_page(job, p)
    assert all(r.ok for r in rows)
    m = job.measurement()
    assert m.ok and m.detail["dual"]["conditions"], m.detail
    s = job.save()
    assert s.ok, (s.reason, s.detail)
    main = run.measurement_ti3
    import workflow.i1pro3_conditions as ic
    for cond in ("M1", "M2"):
        f = ic.condition_file(main, cond)
        assert f is not None and f.is_file() and f != main
    rec = S.read_dual_record(main)
    assert rec.dual and rec.white == "table" and rec.chosen == "M2"
    assert S.build_from_preset(main) == ("M2", "")
    assert S.pass_record_of(main).complete()


def test_every_reading_of_both_passes_is_kept_for_a_new_cut(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    p.drive(job.read_row())
    folder = next(iter(job.diag.folder.glob("row-*")))
    names = {f.name for f in folder.iterdir()}
    assert {"p1_row1.spec.csv", "p1_row1_uv.spec.csv", "p1_row1.dual_in.txt",
            "p1_row1.dual_out.txt", "p1_row1.dual_cut.json"} <= names
    rec = json.loads((folder / "p1_row1.row.json").read_text(encoding="utf-8"))
    assert rec["dual"] and rec["scan"]["lamp"]["kind"] == "done"
    assert rec["scan"]["uv"]["kind"] == "done" and rec["dual_compute"]["pairing"] == "checked"
    assert rec["not_tried_on_a_real_table"] is True


def test_a_uv_pass_over_the_wrong_row_fails_the_row_and_offers_it_again(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {"uv_wrong_strip": True}})
    _ready(job, p)
    res = _until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    assert res.kind == J.Kind.NEEDS and res.confirm == J.Confirm.ROW_FAILED_STRIP
    assert res.detail["why"] == "uv_pass_wrong_strip"
    # read it again patch by patch: the dual scan, patch by patch (no new table line)
    n0 = len(sim.received)
    res = job.answer(J.Confirm.ROW_FAILED_STRIP, "patch by patch")
    res = p.drive(res)
    assert res.ok and res.detail["row_kind"] == "spot", (res.reason, res.detail)
    assert not any(ln.startswith(";m2") or ln.startswith(";d1") for ln in sim.received[n0:])


def test_a_uv_pass_the_instrument_will_not_fire_at_once_is_never_sent(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {"uv_not_ready": True}})
    _ready(job, p)
    res = _until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    assert res.detail["why"] == "uv_pass_failed_clean"
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == 1   # only the lamp pass
    assert not sim.m2_pending


def test_an_instrument_without_the_uv_led_moves_nothing(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {"no_uv_led": True}})
    _ready(job, p)
    n0 = len(sim.received)
    res = _until(job, job.read_row(), J.Confirm.ROW_FAILED_STRIP)
    assert res.detail["why"] == "dual_no_uv_tables"
    assert not any(ln.startswith((";m0", ";m2")) for ln in sim.received[n0:])


def test_a_dual_calibration_that_fails_gives_no_white(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {"dual_cal_fails": True}})
    for s in ("open",):
        assert p.drive(getattr(job, s)()).ok
    r = p.drive(job.calibrate())
    assert not r.ok and r.reason == "dual_calibration_failed"
    assert job.strip_calibration is None


def test_a_stop_during_the_lamp_pass_is_honoured_before_the_uv_pass(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    real = sc.run_row

    def stop_after_lamp(*a, **k):
        res = real(*a, **k)
        if not k.get("uv_pass"):
            job.stop_at_next_pause()
        return res
    import workflow.i1io.table.scan as scm
    scm.run_row = stop_after_lamp
    try:
        r = p.drive(job.read_row())
    finally:
        scm.run_row = real
    assert r.kind == J.Kind.REFUSED and r.reason == "stopped_before_the_uv_pass"
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == 1
    assert ";d100d23a" not in sim.received


def test_short_patches_are_read_patch_by_patch_with_the_dual_scan(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, sheet=shaped_sheet([4, 4], along=7.0, w=210.0,
                                                                h=297.0))
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["read_patch_by_patch_because"] == "dual_row_patches_too_short"
    assert not any(ln.startswith(";m2") for ln in sim.received)


# ---- patch by patch: no new table line at all ----------------------------------------------

def test_patch_by_patch_sends_no_new_table_line_and_files_m1_m2(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, args=SPOT)
    _ready(job, p)
    rows = read_page(job, p)
    assert all(r.ok and r.detail["row_kind"] == "spot" for r in rows)
    for ln in sim.received:
        cl.classify((ln + "\r").encode())          # every line: the released allow-list
    starts = [a for a in helper.started if "-p" in a and "-N" in a]
    assert starts and all("--dual-table" in a and "--condition-dir" in a for a in starts)
    assert job.save().ok
    import workflow.i1pro3_conditions as ic
    assert ic.condition_file(run.measurement_ti3, "M1") is not None
    assert S.build_from_preset(run.measurement_ti3) == ("M2", "")


def test_a_row_reader_without_the_kept_dual_tile_moves_nothing(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, args=SPOT, faults={"dual_not_kept": True})
    _ready(job, p)
    n0 = len(sim.received)
    res = _until(job, job.read_row(), J.Confirm.ROW_FAILED)
    assert res.detail["why"] == "dual_calibration_not_kept"
    assert not any(ln.startswith(";m0") for ln in sim.received[n0:])
    assert job.calibration_due


def test_a_failed_uv_half_reads_the_patch_again_as_one_unit(tmp_path):
    sheet = long_sheet()
    loc = sheet["pages"][0]["strips"][0]["patches"][2]["loc"]
    job, sim, helper, run, p = _job(tmp_path, args=SPOT, faults={"uv_spot_once": (loc,)})
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok, (r.reason, r.detail)
    folder = next(iter(job.diag.folder.glob("row-*")))
    rec = json.loads((folder / "p1_row1.row.json").read_text(encoding="utf-8"))
    assert [f["why"] for f in rec["failed"]] == ["uv_spot_failed"]
    assert rec["conditions"] and [d["ok"] for d in rec["dual_spot_results"]].count(False) == 1


# ---- never mixed, never without a calibration ------------------------------------------------

def test_the_options_the_dual_scan_cannot_measure_with_are_refused(tmp_path):
    sheet = long_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False)
    job.dual = dual_setup()
    assert job.set_options(STRIP + ["-N"]).reason == "dual_needs_a_calibration"
    assert job.set_options(["-H"] + SPOT).reason == "dual_high_resolution"


def test_a_single_scan_measurement_is_never_continued_as_a_dual_one(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, dual=False)
    _ready(job, p)
    p.drive(job.read_row())
    assert job.save().ok
    job2, sim2, helper2, run2 = RS.make_reading_job(tmp_path, sheet=long_sheet(),
                                                    aims=H.demo_aims(long_sheet()),
                                                    ask_after_each_step=False, stamp="20261117-150000")
    job2.dual = dual_setup()
    r = job2.set_options(STRIP + ["-r"])
    assert r.reason == "mixed_scan_kind"


def test_a_dual_measurement_is_never_continued_as_a_single_scan(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    p.drive(job.read_row())
    assert job.save().ok
    job2, sim2, helper2, run2 = RS.make_reading_job(tmp_path, sheet=long_sheet(),
                                                    aims=H.demo_aims(long_sheet()),
                                                    ask_after_each_step=False, stamp="20261117-150000")
    assert job2.set_options(STRIP + ["-r"]).reason == "mixed_scan_kind"


# ---- the cut ---------------------------------------------------------------------------------

def test_the_cut_finds_the_patches_of_both_passes_by_position():
    pts = [sc.Patch(str(k), f"A{k}", (-1200 + 106 * k, 1700), half_mm=5.3) for k in range(20)]
    lamp = sc.plan_row("r", (-1306, 1700), (920, 1700), 132, pts, dual=True)
    for q in lamp.patches:
        q.along_mm = (q.xy[0] - lamp.start[0]) / 10.0
    uv = sp.uv_pass_of(lamp)

    def stream(plan, first, start, k):
        rows = []
        for i in range(plan.N):
            t = first + (i + 0.5) * sc.READING_S - start
            s = 0.0
            # where the sensor is at t: the move's own profile inverted numerically
            lo, hi = 0.0, plan.dist / 10.0
            for _ in range(40):
                mid = (lo + hi) / 2
                if sc.time_at(plan, mid) < t:
                    lo = mid
                else:
                    hi = mid
            s = lo
            idx = min(range(len(plan.patches)), key=lambda j: abs(plan.patches[j].along_mm - s))
            val = 0.05 + 0.04 * int(plan.patches[idx].sample_id)
            rows.append([val * k] * 36)
        return rows
    L = stream(lamp, 0.370, sc.DUAL_LAMP_MOTION_START_S, 1.0)
    U = stream(uv, sc.UV_FIRST_READING_AFTER_TRIGGER_S, sc.UV_MOTION_START_AFTER_TRIGGER_S, 0.2)
    cut = dl.cut_dual(lamp, uv, L, U)
    assert cut.ok, (cut.reason, cut.info)
    for q, l, u in zip(lamp.patches, cut.lamp, cut.uv):
        want = 0.05 + 0.04 * int(q.sample_id)
        assert abs(l[0] - want) < 1e-9 and abs(u[0] - 0.2 * want) < 1e-9
    assert min(cut.info["lamp_readings_per_patch"] + cut.info["uv_readings_per_patch"]) >= 3


def test_the_dual_phase_is_on_only_while_its_pass_runs(tmp_path):
    """d1 210 and m2 at 132 are reachable only while the dual row's pass runs: before and
    after every row (also a failed one) the table has no dual phase, and its gate refuses
    both."""
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    seen = []
    real = sc.run_row

    def watch(table, *a, **k):
        seen.append(table.dual_phase)
        return real(table, *a, **k)
    import workflow.i1io.table.scan as scm
    scm.run_row = watch
    try:
        assert p.drive(job.read_row()).ok
    finally:
        scm.run_row = real
    assert seen == ["lamp", "uv"]
    d = job._table
    assert d.dual_phase is None
    gate = cl.make_gate(d)
    for line in (REC_D1_UV, REC_LAMP_M2):
        with pytest.raises(tbl.ForbiddenLine):
            gate(line)


def test_chromiqs_own_10_mm_patches_are_read_as_dual_rows(tmp_path):
    sheet = shaped_sheet([6, 6], along=10.0, across=10.0, w=210.0, h=297.0)
    job, sim, helper, run, p = _job(tmp_path, sheet=sheet)
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "strip", (r.reason, r.detail)
    folder = next(iter(job.diag.folder.glob("row-*")))
    cut = json.loads((folder / "p1_row1.dual_cut.json").read_text(encoding="utf-8"))
    assert cut["ok"] and cut["info"]["edge_mm"] in sc.DUAL_EDGES_MM
    assert min(cut["info"]["lamp_readings_per_patch"]) >= sc.DUAL_MIN_READINGS


def test_the_cut_takes_the_narrower_edge_only_when_the_wider_leaves_too_few():
    pts = [sc.Patch(str(k), f"A{k}", (-1200 + 100 * k, 1700), half_mm=5.0) for k in range(20)]
    lamp = sc.plan_row("r", (-1300, 1700), (800, 1700), 132, pts, dual=True)
    uv = sp.uv_pass_of(lamp)
    rows = [[0.5] * 36 for _ in range(lamp.N)]
    wide = dl.cut_dual(lamp, uv, rows, rows, edges=(1.5,))
    # 4.3.54: a flat stream has no patch edges; the row placement check uses it only as a row of
    # identical patches (uniform_row), which this flat row is
    auto = dl.cut_dual(lamp, uv, rows, rows, uniform_row=True)
    assert not wide.ok and wide.reason == "strip_patch_too_few_readings"
    assert auto.ok and auto.info["edge_mm"] == 1.0
