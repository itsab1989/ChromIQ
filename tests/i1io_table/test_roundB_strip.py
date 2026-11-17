"""Round B, part 2 (build step 10): reading rows as STRIPS, a first try (the job, the simulated
table and tester 0.6.0's simulated table-scan reader at the recorded pace; no hardware).

| the brief                                                          | here                     |
|--------------------------------------------------------------------|--------------------------|
| off by default: "-p" (ticked for a table chart) = patch by patch    | test_patch_by_patch_*    |
| a strip page is read, filed complete, values as the spot readings    | test_a_strip_page_*      |
| the strip white is made with the spot white (tester C1)              | test_calibration_*       |
| a row that cannot be cut FAILS truthfully, nothing guessed            | test_a_row_that_cannot_* |
| again / patch by patch / skip / stop; GO before any move; two again  | test_a_failed_strip_*    |
| too long, or only part of a row wanted: patch by patch, said         | test_*_patch_by_patch_*  |
| a scan move that may wait: switch off first, nothing more is sent     | test_a_scan_move_*       |
| Stop: honoured before the strip, or after the move has ended          | test_stop_*              |
| options honoured or refused for strip rows                            | test_options_*           |
| App Nap: the latency guard is held around every strip move            | test_the_latency_guard_* |
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_reading import read_page, small_sheet
from workflow.i1io.table import job as J
from workflow.i1io.table import spot as sp
from workflow.i1io.table import strip as stp

STRIP = ["-v", "-c", "1", "chart"]
SPOT = ["-v", "-c", "1", "-p", "chart"]


def _job(tmp_path, args=STRIP, sheet=None, faults=None, script=None, **kw):
    sheet = sheet or H.demo_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False, faults=faults, **kw)
    rep = job.set_options(args)
    assert rep.ok, rep.detail
    return job, sim, helper, run, H.Person(job, sim, script)


def _ready(job, p, steps=("open", "calibrate", "align", "check_move")):
    for s in steps:
        r = p.drive(getattr(job, s)())
        assert r.ok, (s, r.reason, r.detail)


def _moves(sim):
    from tests.i1io_table.test_job_safety import moves
    return moves(sim.received)


def test_patch_by_patch_is_what_the_p_option_says(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, args=SPOT)
    assert job.row_kind == "spot"
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "spot"
    assert helper.scans == []                      # no table-scan reader at all
    assert not any(b";m2" in ln.encode() for ln in sim.received)


def test_a_strip_page_is_read_and_filed_complete_with_the_spot_readings_values(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, sheet=small_sheet())
    assert job.row_kind == "strip"
    _ready(job, p)
    rows = read_page(job, p)
    assert len(rows) == 2 and all(r.ok and r.detail["row_kind"] == "strip" for r in rows)
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == 2
    m = job.measurement()
    assert m.ok and m.detail["measurement"]["state"] == "complete"
    # the same sheet read patch by patch gives the same spectra (the simulated print is one
    # colour per patch; the simulated spot reader's XYZ is not colorimetric, its spectrum is):
    # the cut by position found the patches
    job2, sim2, helper2, run2, p2 = _job(tmp_path / "spot", args=SPOT, sheet=small_sheet())
    _ready(job2, p2)
    read_page(job2, p2)
    m2 = job2.measurement()
    from workflow.measurement_pairing import _first_table
    def xyz(path):
        f, rows = _first_table(path.read_text(encoding="utf-8"))
        li, xi = f.index("SAMPLE_LOC"), f.index("SPEC_550")
        return {r.split()[li].strip('"'): float(r.split()[xi]) for r in rows}
    a = xyz(run.i1io_table_measurement(RS.STAMP))
    b = xyz(run2.i1io_table_measurement(RS.STAMP))
    assert a.keys() == b.keys()
    assert max(abs(a[k] - b[k]) for k in a) < 1.0
    job.close()
    job2.close()


def test_calibration_makes_the_strip_white_with_the_spot_white(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p, ("open", "calibrate"))
    assert job.strip_calibration is not None and job.calibration is not None
    assert len(helper.scans) == 1 and helper.strip_calibrated
    job2, sim2, helper2, run2, p2 = _job(tmp_path / "spot", args=SPOT)
    _ready(job2, p2, ("open", "calibrate"))
    assert job2.strip_calibration is None and helper2.scans == []
    # the table hears the same either way (two position readings at rest)
    assert sim.received == sim2.received


def test_calibration_on_the_own_tile_keeps_the_instrument_out_for_both_whites(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, script={J.Confirm.CAL_PLACE: "own tile"})
    _ready(job, p, ("open", "calibrate"))
    asked = [a[1] for a in p.asked]
    assert asked.count(J.Confirm.CAL_OWN_TILE) == 1 and asked.count(J.Confirm.CAL_RESEAT) == 1
    assert not job.instrument_out and job.strip_calibration["place"] == "own tile"


def test_a_failing_strip_white_fails_the_calibration_truthfully(tmp_path):
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {"cal_fails": True}})
    p.drive(job.open())
    r = p.drive(job.calibrate())
    assert r.kind == J.Kind.REFUSED and r.reason == "strip_calibration_failed"
    assert job.calibration is None and job.strip_calibration is None


def _broken_stream(monkeypatch, reason="strip_patch_not_on_one_colour"):
    real = stp.cut_row

    def cut(plan, outdir, fired):
        c = real(plan, outdir, fired)
        return stp.Cut(False, reason, info=c.info)
    monkeypatch.setattr(stp, "cut_row", cut)


def test_a_row_that_cannot_be_cut_fails_and_keeps_nothing(tmp_path, monkeypatch):
    _broken_stream(monkeypatch)
    job, sim, helper, run, p = _job(tmp_path, script={J.Confirm.ROW_FAILED_STRIP: "skip"})
    _ready(job, p)
    r = p.drive(job.read_row())
    failed = [a for a in p.asked if a[1] == J.Confirm.ROW_FAILED_STRIP]
    assert failed and failed[0][2]["why"] == "strip_patch_not_on_one_colour"
    assert failed[0][2]["read"] == 0
    assert r.ok and r.detail["status"] == "skipped"
    assert job.measurement().reason == "nothing_read"


@pytest.mark.parametrize("why", ["strip_patch_too_few_readings", "strip_fewer_readings_than_planned",
                                 "strip_patches_outside_the_readings",
                                 "strip_instrument_delivered_nothing", "strip_patch_implausible"])
def test_every_cut_failure_is_named(tmp_path, monkeypatch, why):
    _broken_stream(monkeypatch, why)
    job, sim, helper, run, p = _job(tmp_path, script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.REFUSED and r.reason == "stopped_after_a_failed_row"
    assert [a[2]["why"] for a in p.asked if a[1] == J.Confirm.ROW_FAILED_STRIP] == [why]


def test_the_real_cut_refuses_a_stream_that_is_not_one_colour_per_patch(tmp_path):
    """The cut itself, on a stream where every reading differs: refused, never averaged."""
    import random
    from workflow.i1io.table import scan as sc
    plan = sc.plan_row("r", (0, 1000), (2000, 1000), 54,
                       [sc.Patch(str(k + 1), f"A{k + 1}", (200 + 160 * k, 1000), half_mm=4.0)
                        for k in range(10)])
    rnd = random.Random(1)
    with open(tmp_path / "r.spec.csv", "w", encoding="utf-8") as fh:
        fh.write("reading," + ",".join(str(380 + 10 * w) for w in range(36)) + "\n")
        for i in range(plan.N):
            fh.write(f"{i}," + ",".join(f"{rnd.random():.4f}" for _ in range(36)) + "\n")
    c = stp.cut_row(plan, str(tmp_path), {"ok": True, "got": plan.N})
    assert not c.ok and c.reason == "strip_patch_not_on_one_colour" and not c.patches
    c2 = stp.cut_row(plan, str(tmp_path), {"ok": True, "got": plan.N - 50})
    assert not c2.ok and c2.reason == "strip_fewer_readings_than_planned"
    assert stp.cut_row(plan, str(tmp_path), {"ok": False}).reason == \
        "strip_instrument_delivered_nothing"


def test_a_failed_strip_read_patch_by_patch_asks_go_first_and_counts_as_again(tmp_path,
                                                                              monkeypatch):
    _broken_stream(monkeypatch)
    job, sim, helper, run, p = _job(tmp_path,
                                    script={J.Confirm.ROW_FAILED_STRIP: "patch by patch"})
    _ready(job, p)
    seen = {}

    def on_ask(person, res):
        if res.confirm == J.Confirm.GO and res.detail.get("again"):
            seen["moves_at_go"] = len(_moves(sim))
            seen["moving"] = sim.moving
    p.on_ask = on_ask
    before = len(_moves(sim))
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "spot" and r.detail["status"] == "read"
    assert r.detail["read_patch_by_patch_because"] == "chosen_by_you"
    assert job.rows_again[0] == 1
    # GO was asked after the strip ended and before the arm moved to a patch
    assert seen["moves_at_go"] == before + 2 and not seen["moving"]


def test_a_failed_strip_again_twice_then_the_third_is_refused(tmp_path, monkeypatch):
    _broken_stream(monkeypatch)
    job, sim, helper, run, p = _job(tmp_path, script={J.Confirm.ROW_FAILED_STRIP: "again"})
    _ready(job, p)
    r = p.drive(job.read_row())
    assert getattr(p, "refused_again", 0) == 1      # the third "again" was refused
    assert job.rows_again[0] == 2
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == 3


def test_a_row_too_long_for_one_strip_is_read_patch_by_patch_and_said(tmp_path, monkeypatch):
    monkeypatch.setattr(sp, "STRIP_N_MAX", 20)
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "spot"
    assert r.detail["read_patch_by_patch_because"] == "strip_row_too_long"
    assert not any(ln.startswith(";m2") for ln in sim.received)
    assert job.rows_again.get(0, 0) == 0           # not a row read again


def test_the_speed_goes_up_before_a_row_is_given_up(tmp_path):
    sheet = H.demo_sheet()
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    plan = sp.plan_strip_row(sheet, 0, 0, job.alignment, job._table.front_y)
    assert plan.scan.speed == 54 and plan.scan.N <= sp.STRIP_N_MAX
    import workflow.i1io.table.spot as spm
    old = spm.STRIP_N_MAX
    try:
        spm.STRIP_N_MAX = plan.scan.N - 10
        faster = sp.plan_strip_row(sheet, 0, 0, job.alignment, job._table.front_y)
        assert faster.scan.speed > 54 and faster.scan.N <= spm.STRIP_N_MAX
    finally:
        spm.STRIP_N_MAX = old


def test_only_some_patches_of_a_row_are_read_patch_by_patch(tmp_path):
    sheet = small_sheet()
    job, sim, helper, run, p = _job(tmp_path, sheet=sheet)
    locs = {q["loc"] for q in sheet["pages"][0]["strips"][0]["patches"]}
    job.only_locs = set(list(sorted(locs))[:2])
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["read_patch_by_patch_because"] == "strip_only_some_patches"


@pytest.mark.parametrize("fault", ["no_lamp", "fire_unsent", "dies_at_fire"])
def test_a_scan_move_that_may_wait_says_switch_off_first_and_sends_nothing_more(tmp_path,
                                                                               fault):
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {fault: True}, "scan_at": 2})
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.STOPPED and r.reason == "strip_move_may_be_pending"
    assert r.way_back == J.WayBack.SWITCH_OFF_PENDING and r.state.strip_move_may_be_pending
    n = len(sim.received)
    for step in ("read_row", "home", "check_move"):
        assert not getattr(job, step)().ok
    assert len(sim.received) == n
    job.close()
    assert run.i1io_table_pending_marker(RS.STAMP).is_file()


@pytest.mark.parametrize("fault", ["not_ready", "lights_err", "dark_fail"])
def test_a_clean_strip_failure_leaves_the_arm_held_and_offers_the_choices(tmp_path, fault):
    job, sim, helper, run, p = _job(tmp_path, faults={"scan": {fault: True}, "scan_at": 2},
                                    script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    _ready(job, p)
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.REFUSED and r.reason == "stopped_after_a_failed_row"
    asked = [a for a in p.asked if a[1] == J.Confirm.ROW_FAILED_STRIP]
    assert len(asked) == 1 and asked[0][2]["why"].startswith("strip_")
    assert not r.state.strip_move_may_be_pending and not r.state.movement_may_be_unfinished
    h = p.drive(job.home())
    assert h.ok


def test_stop_before_the_strip_is_honoured_before_any_move(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    job.stop_at_next_pause()
    n = len(_moves(sim))
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.REFUSED and r.reason == J.STOPPED_BEFORE_THE_NEXT_MOVE
    assert len(_moves(sim)) == n


def test_stop_during_the_strip_move_is_honoured_after_the_move(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    k0 = len(sim.received)

    def on_command(i):
        if i >= k0 and sim.received and sim.received[-1].startswith(";m2"):
            job.stop_at_next_pause()
    sim.on_command = on_command
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read"
    assert r.detail.get("stop_asked_during_the_last_patch") is True
    assert sum(1 for ln in sim.received if ln.startswith(";m2")) == 1
    r2 = job.read_row()
    assert r2.kind == J.Kind.NEEDS and r2.confirm == J.Confirm.GO


def test_the_latency_guard_is_held_around_every_strip_move(tmp_path):
    held = []

    class Guard:
        def __enter__(self):
            held.append("in")

        def __exit__(self, *a):
            held.append("out")
    job, sim, helper, run, p = _job(tmp_path, sheet=small_sheet(), latency_guard=Guard)
    _ready(job, p)
    read_page(job, p)
    assert held == ["in", "out", "in", "out"]


def test_options_for_strip_rows(tmp_path):
    rep = sp.options_from_chartread_args(["-H", "-S", "chart"])
    assert rep.options.strip and not rep.options.high_res and rep.options.suppress_warnings
    assert rep.no_meaning["-H"] == "the_strip_reading_has_no_high_resolution"
    rep = sp.options_from_chartread_args(["-A", "X", "chart"])
    assert not rep.ok and rep.refused["-A"] == "xrga_not_with_strip_rows"
    rep = sp.options_from_chartread_args(["-p", "-A", "X", "-H", "chart"])
    assert rep.ok and rep.options.xrga == "X" and rep.options.high_res and not rep.options.strip


@pytest.mark.parametrize("flags,fields", [
    ([], {"XYZ_X", "SPEC_380"}), (["-l"], {"LAB_L", "SPEC_380"}),
    (["-L"], {"XYZ_X", "LAB_L", "SPEC_380"}), (["-n"], {"XYZ_X"})])
def test_options_l_L_n_shape_the_strip_rows_file_as_a_spot_rows(tmp_path, flags, fields):
    job, sim, helper, run, p = _job(tmp_path, args=["-v"] + flags + ["chart"],
                                    sheet=small_sheet())
    _ready(job, p)
    read_page(job, p)
    m = job.measurement()
    assert m.ok, m.reason
    from workflow.measurement_pairing import _first_table
    f, _rows = _first_table(run.i1io_table_measurement(RS.STAMP).read_text(encoding="utf-8"))
    for want in fields:
        assert want in f, (flags, f)
    for absent in ({"XYZ_X", "LAB_L", "SPEC_380"} - fields):
        assert absent not in f, (flags, f)


def test_strip_and_patch_by_patch_rows_mix_in_one_measurement(tmp_path, monkeypatch):
    sheet = small_sheet()
    job, sim, helper, run, p = _job(tmp_path, sheet=sheet)
    _ready(job, p)
    assert p.drive(job.read_row(1)).ok                     # a strip
    assert p.drive(job.read_row(2, kind="spot")).ok        # patch by patch
    m = job.measurement()
    assert m.ok and m.detail["measurement"]["state"] == "complete", m.detail


def test_the_session_caps_hold_strip_rows_of_the_largest_chart():
    from workflow.i1io.table import caps as cp
    # a strip row costs the tester's E2 row step plus its front-row ends (unchanged)
    assert cp.STRIP_ROW == (19, 4)
    assert cp.row_cost(1) == (19, 4) and cp.row_cost(33) == (70, 33)


def test_the_strip_constants_are_pinned():
    assert sp.STRIP_N_MAX == 1190
    assert sp.STRIP_SPEEDS == (54, 61, 87, 88, 110, 118, 137, 138)
    from workflow.i1io.table import geometry as geo
    assert set(sp.STRIP_SPEEDS) <= set(geo.RECORDED_M2_SPEEDS)
    assert sp.STRIP_MIN_READINGS == 5 and sp.STRIP_UNIFORMITY_MAX == 0.10


# ---- the panel ---------------------------------------------------------------------------------

from tests.i1io_table.test_window import open_window, settings  # noqa: E402,F401
from ui import i1io_table_window as W  # noqa: E402


def test_every_strip_id_has_its_sentence():
    import re
    from pathlib import Path
    root = Path(J.__file__).parent
    ids = set(re.findall(r'"(strip_[a-z_]+)"', (root / "strip.py").read_text(encoding="utf-8")))
    ids |= {rid for _p, rid in J._STRIP_CLEAN_IDS}
    ids |= {"needs_strip_calibration", "strip_calibration_failed", "strip_reading_not_available",
            "strip_reader_did_not_open", "strip_row_too_long", "strip_only_some_patches"}
    fallback = W.reason_text("a_brand_new_id_nobody_wrote_a_sentence_for")
    plain = sorted(i for i in ids if W.reason_text(i) == fallback and i != "first_visit_declined"
                   and i != "free_arm_moved_between_two_readings"
                   and i != "movement_late_but_arrived")
    assert plain == [], plain
    for i in ids:
        assert i not in W.reason_text(i)


def test_the_panel_reads_strip_rows_and_says_it_is_a_first_try(qtbot, monkeypatch, tmp_path,
                                                                settings):  # noqa: F811
    win, sim, run, person, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, args=STRIP)
    assert person.page() == "prepare"
    assert "first try" in win._text.text() and "as a strip" in win._text.text()
    person.drive_until("end_of_session")
    assert sum(1 for ln in sim.sim.received if ln.startswith(";m2")) == 2


def test_the_panel_offers_four_ways_after_a_failed_strip(qtbot, monkeypatch, tmp_path, settings,  # noqa: F811
                                                        ):
    from workflow.i1io.table import strip as stp2
    real = stp2.cut_row
    monkeypatch.setattr(stp2, "cut_row", lambda plan, outdir, fired: stp2.Cut(
        False, "strip_patch_not_on_one_colour", info=real(plan, outdir, fired).info))
    win, sim, run, person, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, args=STRIP)
    person.drive_until("row_failed_strip")
    labels = person.labels()
    for want in ("Read it again as a strip", "Read it patch by patch", "Skip it",
                 "End this step"):
        assert want in labels, labels
    assert "could not be sure where that patch is" in win._text.text()
    assert not any(b.isDefault() or b.autoDefault() for b in win._buttons)
    person.press("Read it patch by patch")
    assert person.page() == "go"                     # hands off first, nothing moved


def test_app_nap_guard_is_what_the_real_job_holds(monkeypatch):
    import inspect
    from core.app_nap import latency_critical
    src = inspect.getsource(W.default_job_factory)
    assert "latency_guard=latency_critical" in src
    with latency_critical() as g:
        import sys
        assert g.active is (sys.platform == "darwin")
    assert not g.active


def test_no_strip_row_without_the_strip_white(tmp_path):
    job, sim, helper, run, p = _job(tmp_path)
    _ready(job, p)
    job.strip_calibration = None                 # a white for spot rows only
    n = len(sim.received)
    r = job.read_row()
    assert r.kind == J.Kind.REFUSED and r.reason == "needs_strip_calibration"
    assert len(sim.received) == n
