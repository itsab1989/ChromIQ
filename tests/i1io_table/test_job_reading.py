"""Build step 7: READING in the table job, against the table simulator and a simulated helper
process behind the app's own ``reader.SpotReader`` (no hardware).

| what (the brief of step 7)                                    | here                          |
|---------------------------------------------------------------|-------------------------------|
| the reader consent before the first reader, once              | test_the_consent_*            |
| exactly one i1Pro 2, the helper's own model report            | test_the_instrument_check_*,  |
|                                                               | test_a_reader_that_*          |
| clean named failures (helper missing, busy, wrong, dies...)   | test_a_reader_that_*          |
| calibration: the place, own tile and table tile, validity    | test_calibration_*            |
| the instrument's own prompts                                  | test_*_asks_for_a_calibration |
| spot rows: every failure kind at every patch of a small page  | test_every_failure_kind_*     |
| a failed patch read again once; a second failure fails the row| test_a_patch_that_fails_*     |
| a failed row: again / skip / stop; two rows again PER PAGE    | test_a_page_reads_at_most_*   |
| both modes: one question per ROW in the asking mode           | test_one_report_per_row_*     |
| report_problem / stop / cancel inside a row                   | test_*_inside_a_row_*         |
| a lost link and a problem report at every line of reading     | test_*_at_every_line_*        |
| the Measure tab's options                                     | test_options_*                |
"""
from __future__ import annotations

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_safety import moves, shaped_sheet
from workflow.i1io.table import job as J
from workflow.i1io.table import session_table as tbl
from workflow.i1io.table import spot as sp
from workflow.i1io.table import usb_system as us

SMALL = [4, 4]                              # a small page: two rows of four patches


def small_sheet(rows=None, pages=1):
    return shaped_sheet(list(rows or SMALL), pages=pages, w=210.0, h=297.0)


def job_for(tmp_path, script=None, sheet=None, asking=False, **kw):
    sheet = sheet or small_sheet()
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                aims=H.demo_aims(sheet),
                                                ask_after_each_step=asking, **kw)
    return job, sim, helper, run, H.Person(job, sim, script)


def ready_to_read(job, p, steps=("open", "calibrate", "align")):
    for s in steps:
        r = p.drive(getattr(job, s)())
        assert r.ok, (s, r.reason, r.detail)
    return r


def read_page(job, p):
    out = []
    while job.rows_left():
        r = p.drive(job.read_row())
        out.append(r)
        if not r.ok:
            break
    return out


# ---- the reader consent ----------------------------------------------------------------------

def test_the_consent_comes_before_the_first_reader_and_only_once(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    asked = [(c, d, n) for _s, c, d, n, _m in p.asked]
    consent = [a for a in asked if a[0] == J.Confirm.READER_CONSENT]
    assert len(consent) == 1
    assert "on_a_mac_it_closes_xrites_i1prodeviceservice_if_the_instrument_is_in_use_for_up_to_"\
           "two_seconds" in consent[0][1]["facts"]
    read_page(job, p)
    assert [c for _s, c, *_r in p.asked].count(J.Confirm.READER_CONSENT) == 1
    assert job.readers_started == 1 + 2


def test_the_consent_is_asked_before_any_reader_starts(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    p.drive(job.open())
    r = job.calibrate()
    assert r.confirm == J.Confirm.READER_CONSENT and helper.started == []


def test_a_no_to_the_consent_starts_no_reader_and_the_sitting_goes_on(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.READER_CONSENT: "no"})
    p.drive(job.open())
    n = len(sim.received)
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "reader_not_started")
    assert helper.started == [] and len(sim.received) == n + 1          # the rest reading only
    assert moves(sim.received[n:]) == [] and job.calibration is None
    assert job.state().sending_closed is False                          # the sitting goes on
    p.script[J.Confirm.READER_CONSENT] = "yes"
    assert p.drive(job.calibrate()).ok


# ---- the instrument and the reader: clean, named failures ------------------------------------

@pytest.mark.parametrize("state", ["no_instrument", "several_instruments", "other_instrument",
                                   "cannot_tell"])
def test_the_instrument_check_starts_no_reader_unless_exactly_one_i1pro2(tmp_path, state):
    job, sim, helper, run, p = job_for(tmp_path, instrument=lambda: us.Check(state, {}))
    p.drive(job.open())
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, f"instrument_{state}")
    assert helper.started == [] and not any(c == J.Confirm.READER_CONSENT
                                            for _s, c, *_r in p.asked)


@pytest.mark.parametrize("why", ["helper_missing", "helper_not_runnable"])
def test_a_missing_helper_starts_nothing(tmp_path, why):
    job, sim, helper, run, p = job_for(tmp_path, helper_check=lambda: why)
    p.drive(job.open())
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, why) and helper.started == []


def test_the_default_helper_check_names_a_missing_helper(monkeypatch, tmp_path):
    from workflow.i1io.table import reader as rd
    monkeypatch.setattr(rd, "helper_path", lambda pkg=None: tmp_path / "not-there")
    assert J._default_helper_check() == "helper_missing"
    f = tmp_path / "chromiq-chartread"
    f.write_text("", encoding="utf-8")
    monkeypatch.setattr(rd, "helper_path", lambda pkg=None: f)
    assert J._default_helper_check() == "helper_not_runnable"


OPEN_FAULTS = {"no_instrument": "instrument_not_found", "busy": "instrument_busy",
               "wrong_model": "wrong_instrument", "no_model": "instrument_not_reported",
               "dies": "reader_died", "silent": "reader_did_not_get_ready",
               "cal_fails": "calibration_failed", "cal_other_cond": "calibration_kind_unknown"}


@pytest.mark.parametrize("fault", sorted(OPEN_FAULTS))
def test_a_reader_that_cannot_open_fails_cleanly_with_its_name(tmp_path, fault):
    job, sim, helper, run, p = job_for(tmp_path, faults={"open": fault})
    p.drive(job.open())
    n = len(sim.received)
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, OPEN_FAULTS[fault])
    assert job.calibration is None and job._open_readers == []
    assert all(not pr.alive() for pr in helper.procs)                # the reader was ended
    assert moves(sim.received[n:]) == [] and r.state.at_rest
    assert r.way_back == J.WayBack.NONE and not r.state.sending_closed


@pytest.mark.parametrize("fault", ["no_instrument", "busy", "wrong_model", "dies", "silent"])
def test_a_reader_that_cannot_open_for_a_row_leaves_the_arm_held_and_unmoved(tmp_path, fault):
    job, sim, helper, run, p = job_for(tmp_path, faults={"open": fault, "open_at": 2})
    ready_to_read(job, p)
    n_moves = len(moves(sim.received))
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.REFUSED and r.reason == OPEN_FAULTS[fault]
    assert len(moves(sim.received)) == n_moves                      # no move of the row
    assert p.drive(job.home()).ok and sim.violations == []


# ---- calibration --------------------------------------------------------------------------------

def test_calibration_on_the_table_tile_moves_nothing_and_reads_the_arm_before_and_after(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    p.drive(job.open())
    n = len(sim.received)
    r = p.drive(job.calibrate())
    assert r.ok and r.detail["place"] == "table tile"
    assert sim.received[n:] == [";p025", ";p025"]
    assert moves(sim.received[n:]) == [] and helper.calibrations == 1
    assert job.calibration["place"] == "table tile"
    place = [d for _s, c, d, *_r in p.asked if c == J.Confirm.CAL_PLACE][0]
    assert place == {"recommended": "table tile", "measured": J.CAL_PLACE_MEASURED,
                     "decision_open": "D-4b"}


def test_calibration_on_the_own_tile_asks_out_then_seated_and_the_white_counts_only_then(
        tmp_path):
    order = []

    def on_ask(person, res):
        order.append((res.confirm, helper.calibrations))
        return None
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.CAL_PLACE: "own tile"})
    p.drive(job.open())
    p.on_ask = on_ask
    assert p.drive(job.calibrate()).ok
    kinds = [k for k, _n in order]
    assert kinds == [J.Confirm.READER_CONSENT, J.Confirm.CAL_PLACE, J.Confirm.CAL_OWN_TILE,
                     J.Confirm.CAL_RESEAT]
    # the instrument's calibration ran after "ready" and before "seated"
    assert dict(order)[J.Confirm.CAL_OWN_TILE] == 0 and dict(order)[J.Confirm.CAL_RESEAT] == 1
    # a second white: the place is not asked again; out and seated are
    order.clear()
    assert p.drive(job.calibrate()).ok
    assert [k for k, _n in order] == [J.Confirm.CAL_OWN_TILE, J.Confirm.CAL_RESEAT]


def test_calibration_not_seated_again_reads_no_row(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.CAL_PLACE: "own tile",
                                                  J.Confirm.CAL_RESEAT: "stop"})
    p.drive(job.open())
    r = p.drive(job.calibrate())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "instrument_not_seated_again")
    assert job.calibration is None and job.instrument_out
    assert job.align().reason == "instrument_not_in_the_arm"
    assert job.read_row().reason == "instrument_not_in_the_arm"


def test_calibration_only_at_rest(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)                    # the arm free on the sheet after the aims
    n = len(sim.received)
    assert job.calibrate().reason == "arm_not_at_rest" and len(sim.received) == n


def test_calibration_validity_a_new_white_is_due_between_rows_never_inside_one(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    # nearly an hour later: the next row would end after the white's hour (plus the margin)
    sim.clock = job.calibration["t"] + sp.CAL_VALID_S - sp.CAL_MARGIN_S - 5
    n = len(sim.received)
    r = job.read_row()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "calibration_due") and len(sim.received) == n
    # the way on: home (the arm parked), a new white at rest, aim the sheet again, read on
    for s in ("home", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    assert p.drive(job.read_row()).ok and job.rows_left() == []


def test_a_row_says_when_the_next_one_needs_a_new_white(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    # just enough left for this row (4 patches: 16 s + 10 s + the 2 minutes), not the next
    sim.clock = job.calibration["t"] + sp.CAL_VALID_S - sp.CAL_MARGIN_S - sp.row_seconds(4) - 4
    r = p.drive(job.read_row())
    assert r.ok and r.detail.get("calibration_due_before_next_row") is True


def test_the_instrument_that_asks_for_a_calibration_at_a_row_reads_nothing_there(tmp_path):
    """-N (a white made earlier) and the instrument wants a new one: the row ends before its
    first move (the arm stands over the sheet: never a calibration there)."""
    job, sim, helper, run, p = job_for(tmp_path)
    assert job.set_options(["-p", "-N"]).ok
    for s in ("open", "align"):
        assert p.drive(getattr(job, s)()).ok
    n_moves = len(moves(sim.received))
    r = p.drive(job.read_row())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "instrument_asks_for_calibration")
    assert len(moves(sim.received)) == n_moves and job.calibration_due
    assert job.read_row().reason == "calibration_due"


def test_a_calibration_request_during_a_reading_fails_the_row_and_makes_a_white_due(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED: "skip"},
                                       faults={"read": {2: "cal_required"}})
    ready_to_read(job, p)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "skipped"
    fail = [d for _s, c, d, *_r in p.asked if c == J.Confirm.ROW_FAILED][0]
    assert fail["why"] == "instrument_asks_for_calibration" and fail["again_allowed"] is False
    assert job.read_row().reason == "calibration_due"


# ---- spot rows: every failure kind at every patch of a small page ----------------------------

RETRY = ("error", "coms", "implausible", "no_values")
ROW_ENDS = ("other_loc", "dies", "slow")
N_SMALL = sum(SMALL)


def _clean(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    read_page(job, p)
    return sim


@pytest.mark.parametrize("kind", RETRY + ROW_ENDS)
@pytest.mark.parametrize("at", range(1, N_SMALL + 1))
def test_every_failure_kind_at_every_patch_of_a_small_page(tmp_path, kind, at):
    base = len(_clean(tmp_path / "clean").received)
    job, sim, helper, run, p = job_for(tmp_path / "f", faults={"read": {at + 0: kind}})
    ready_to_read(job, p)
    # the calibration's reader reads nothing, so reading n of the sitting is patch n of the page
    results = read_page(job, p)
    assert all(r.ok for r in results), [(r.reason, r.detail) for r in results]
    assert sim.violations == [] and job.rows_left() == []
    fails = [d for _s, c, d, *_r in p.asked if c == J.Confirm.ROW_FAILED]
    if kind in RETRY:
        # read again once from a fresh position reading: exactly ONE more line (p0), no move
        assert fails == []
        assert len(sim.received) == base + 1
        extra = [x for x in sim.received if x.startswith(";p0")]
        assert len(extra) == len([x for x in _clean(tmp_path / "c2").received
                                  if x.startswith(";p0")]) + 1
    else:
        assert len(fails) == 1 and fails[0]["again_allowed"] is True
        assert fails[0]["why"] == {"other_loc": "reading_of_another_patch",
                                   "dies": "reader_died", "slow": "reading_timed_out"}[kind]
        assert job.rows_again[0] == 1
    m = job.measurement()
    assert m.ok and m.detail["measurement"]["state"] == "complete", m.detail
    assert m.detail["measurement"]["read"] == N_SMALL


def test_a_patch_that_fails_twice_fails_the_row_and_its_values_never_reach_the_file(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED: "skip"},
                                       faults={"read_loc": {"0-2": "implausible"}})
    ready_to_read(job, p)
    results = read_page(job, p)
    assert [r.detail["status"] for r in results] == ["skipped", "read"]
    fail = [d for _s, c, d, *_r in p.asked if c == J.Confirm.ROW_FAILED]
    assert len(fail) == 1 and fail[0]["loc"] == "0-2" and fail[0]["why"] == "reading_implausible"
    m = job.measurement().detail["measurement"]
    assert m["state"] == "partial"
    # the row runs from column 0 (the end of marks 1 and 2, here 0-3: S-8); 0-3 was read
    # before the failure and is kept; 0-2 and the rest of the row not
    assert set(m["unread"]) == {"0-0", "0-1", "0-2"}
    text = run.i1io_table_measurement(RS.STAMP).read_text(encoding="utf-8")
    assert '"0-2"' not in text and " 0.010000 " not in text


# ---- a failed row: again / skip / stop; at most two rows read again PER PAGE ------------------

def test_a_failed_row_offers_again_skip_stop_and_stop_holds_the_arm(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED: "stop"},
                                       faults={"read": {2: "dies"}})
    ready_to_read(job, p)
    r = p.drive(job.read_row())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "stopped_after_a_failed_row")
    assert r.detail["by_person"] and not r.state.movement_may_be_unfinished
    assert r.state.position_now is not None and r.way_back == J.WayBack.HOME_OFFERED
    ask = [x for x in p.asked if x[1] == J.Confirm.ROW_FAILED][0]
    assert J.CHOICES[J.Confirm.ROW_FAILED] == ("again", "skip", "stop")
    assert not ask[4]                                         # never asked while the arm moves
    assert p.drive(job.home()).ok


def test_a_page_reads_at_most_two_rows_again(tmp_path):
    """NEXT_STEPS 4d: read a page, ask for the same row a third time: refused with that reason,
    nothing sent; on the next page the count starts again."""
    sheet = small_sheet(pages=2)
    job, sim, helper, run, p = job_for(tmp_path, sheet=sheet)
    ready_to_read(job, p)
    read_page(job, p)
    assert p.drive(job.read_row(1)).ok
    assert p.drive(job.read_row(1)).ok
    n = len(sim.received)
    r = job.read_row(1)
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "rows_read_again_limit")
    assert len(sim.received) == n and job._gen is None
    assert job.read_row(2).reason == "rows_read_again_limit"        # any row of the page
    # the next page: its own count
    assert p.drive(job.home()).ok and job.next_page().ok
    assert p.drive(job.align()).ok
    read_page(job, p)
    assert p.drive(job.read_row(1)).ok and p.drive(job.read_row(2)).ok
    assert job.read_row(1).reason == "rows_read_again_limit"
    assert job.rows_again == {0: 2, 1: 2}


def test_again_after_a_failed_row_counts_and_a_third_again_is_refused_with_nothing_sent(
        tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, faults={"read_loc": {"0-1": "dies"}})
    ready_to_read(job, p)
    lines_at_refusal = []

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED and job.rows_again.get(0, 0) >= 2:
            lines_at_refusal.append(len(sim.received))
        return None
    p.on_ask = on_ask
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "skipped" and r.detail["attempts"] == 3
    assert job.rows_again[0] == 2 and p.refused_again == 1
    assert len(sim.received) == lines_at_refusal[0]               # the refused again sent nothing
    assert job.read_row(1).reason == "rows_read_again_limit"


def test_a_skipped_row_leaves_a_partial_measurement(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.ROW_FAILED: "skip"},
                                       faults={"read": {6: "dies"}})
    ready_to_read(job, p)
    res = read_page(job, p)
    assert [r.detail["status"] for r in res] == ["read", "skipped"]
    m = job.measurement().detail["measurement"]
    # the reader died at the row's second patch: its first reading was never saved by the
    # helper (chartread saves on "done"), so it is not in the measurement either, and says so
    assert m["state"] == "partial" and m["read"] == 4 and len(m["unread"]) == 4
    assert m["rejected"] == [["1-3", "reader_saved_nothing"]]


# ---- both modes: a step is a ROW ----------------------------------------------------------------

@pytest.mark.parametrize("asking", [True, False])
def test_one_report_per_row_in_the_asking_mode_none_in_the_quiet_one(tmp_path, asking):
    job, sim, helper, run, p = job_for(tmp_path, asking=asking)
    ready_to_read(job, p)
    before = len(p.reports)
    read_page(job, p)
    rows = len(p.reports) - before
    assert rows == (len(SMALL) if asking else 0)
    assert all(step == "read_row" for step, _a in p.reports[before:])
    # GO: once before the first move after the aims, not per row (the alignment's move is
    # confirmed by the sheet-laid answer, final fix round M-1; "As described" is the hands-off
    # confirmation between rows in the asking mode)
    assert [c for _s, c, *_r in p.asked].count(J.Confirm.GO) == 1


def test_asking_mode_a_wrong_report_after_a_row_leaves_only_the_homing(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, asking=True)
    ready_to_read(job, p)
    p.script["report"] = "something wrong"
    p.drive(job.read_row())
    assert job.only_home and job.read_row().reason == "only_the_homing_now"
    assert p.drive(job.home()).ok


# ---- report_problem, stop and cancel inside a row ----------------------------------------------

def _row_with(tmp_path, at, action):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    lines_at = {}

    def hook(n):
        if n == at:
            lines_at["n"] = len(sim.received)
            action(job)
    helper.on_read = hook
    r = p.drive(job.read_row())
    return job, sim, helper, p, r, lines_at.get("n")


def test_a_stop_during_the_rows_last_patch_ends_with_the_row_and_reaches_no_other(tmp_path):
    job, sim, helper, p, r, n = _row_with(tmp_path, 4, lambda j: j.stop_at_next_pause())
    assert r.ok and r.detail["stop_asked_during_the_last_patch"] is True
    assert len(sim.received) == n and not job._pause_stop
    assert p.drive(job.read_row()).ok                       # the next row is not stopped by it


@pytest.mark.parametrize("at", [1, 2, 3])
def test_stop_at_next_pause_inside_a_row_stops_after_the_current_patch(tmp_path, at):
    job, sim, helper, p, r, n = _row_with(tmp_path, at, lambda j: j.stop_at_next_pause())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "stopped_between_patches")
    assert len(sim.received) == n and helper.reads == at          # nothing after the reading
    plan = sp.plan_row(job.sheet, 0, 0, job.alignment, None)
    assert J._near(r.state.position_now, plan.patches[at - 1].target)     # truthful: held there
    assert r.way_back == J.WayBack.HOME_OFFERED and p.drive(job.home()).ok
    assert job.measurement().detail["measurement"]["read"] == at


@pytest.mark.parametrize("at", [1, 3])
def test_something_wrong_inside_a_row_is_honoured_before_the_next_move(tmp_path, at):
    job, sim, helper, p, r, n = _row_with(
        tmp_path, at, lambda j: j.report_problem(J.PROBLEM_SOMETHING_WRONG, "a noise"))
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "problem_reported")
    assert moves(sim.received[n:]) == []
    assert job.only_home and job.read_row().reason == "only_the_homing_now"
    assert p.drive(job.home()).ok and job.problems[0][1] == "read_row"


@pytest.mark.parametrize("action", ["stop now", "cancel"])
def test_stop_now_or_cancel_inside_a_row_sends_nothing_more(tmp_path, action):
    act = (lambda j: j.report_problem(J.PROBLEM_STOP_NOW)) if action == "stop now" else \
        (lambda j: j.cancel())
    job, sim, helper, p, r, n = _row_with(tmp_path, 2, act)
    assert r.kind == J.Kind.STOPPED and len(sim.received) == n
    assert r.state.sending_closed and job.home().reason in ("stopped_by_person", "sending_closed")
    assert job._open_readers == [] and all(not pr.alive() for pr in helper.procs)
    # the patches read before the stop are kept as readings
    assert job.measurement().detail["measurement"]["read"] == 2


# ---- a lost link and a problem report at every line of a reading sitting ---------------------

STEPS7 = ["open", "calibrate", "align", "read_row", "read_row", "home"]


def _base_len(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    for s in STEPS7:
        p.drive(getattr(job, s)())
    return len(sim.received)


def test_a_lost_link_at_every_line_of_reading_ends_truthfully(tmp_path):
    n = _base_len(tmp_path / "base")
    for i in range(n):
        sim = csim.CSimTable(part_c=True, aims=H.demo_aims(small_sheet()))
        sim.inject_at(i, "unplug", 1.0)
        job, sim, helper, run, p = job_for(tmp_path / f"l{i}", sim=sim)
        last = None
        for s in STEPS7:
            last = p.drive(getattr(job, s)())
            if last.kind == J.Kind.STOPPED:
                break
        assert last.kind == J.Kind.STOPPED and last.reason == "link_lost", (i, last.reason)
        assert last.state.link_lost and last.state.sending_closed
        assert len(sim.received) == i + 1, i                          # nothing after it
        assert last.way_back in (J.WayBack.LINK_LOST_REPLUG,
                                 J.WayBack.LINK_LOST_SWITCH_OFF_FIRST), (i, last.way_back)
        if last.state.movement_may_be_unfinished:
            assert last.way_back == J.WayBack.LINK_LOST_SWITCH_OFF_FIRST, i
        assert job._open_readers == [], i
        assert sim.violations == [], i


@pytest.mark.parametrize("kind", [J.PROBLEM_STOP_NOW, J.PROBLEM_SOMETHING_WRONG])
def test_a_problem_at_every_line_of_reading_is_taken(tmp_path, kind):
    n = _base_len(tmp_path / "base")
    wire = {v.decode().rstrip("\r") for v in tbl.WIRE.values()}
    for i in range(n):
        sim = csim.CSimTable(part_c=True, aims=H.demo_aims(small_sheet()))
        holder = {}
        sim.on_command = (lambda k, i=i: holder["job"].report_problem(kind) if k == i else None)
        job, sim, helper, run, p = job_for(tmp_path / f"p{i}", sim=sim)
        holder["job"] = job
        for s in STEPS7:
            p.drive(getattr(job, s)())
        assert job.problems and job.problems[0][0] == kind, i
        if kind == J.PROBLEM_STOP_NOW:
            assert len(sim.received) == i + 1, i                    # the line on its way only
        else:
            later = moves(sim.received[i + 1:])
            assert job.only_home or job.stopped_by_person, i
            # at most the recorded step on its way (b_align: 3 movements), never a computed
            # move after the report: the row stops before its next move
            assert len([x for x in later if x != ";i12b"]) <= 3, (i, later)
            assert all(x in wire for x in later), (i, later)
        assert sim.violations == [], i


# ---- the Measure tab's options -----------------------------------------------------------------

def test_options_from_the_measure_tab_are_honoured_or_refused_with_a_reason():
    rep = sp.options_from_chartread_args(["-v", "-c", "2", "-S", "-N", "-p", "-H", "-r", "-T",
                                          "0.7", "-A", "A", "-L", "/runs/run1/Chart"])
    assert rep.ok and rep.options == sp.ReadOptions(suppress_warnings=True, high_res=True,
                                                    xrga="A", save_lab_and_xyz=True,
                                                    skip_initial_calibration=True, resume=True)
    assert rep.no_meaning == {"-v": "the_reader_always_reports_the_instrument",
                              "-c": "the_table_check_picks_its_own_i1pro2",
                              "-T": "the_table_knows_where_each_patch_is"}
    assert rep.options.reader_args() == ("-S", "-H", "-A", "A", "-L")
    bad = sp.options_from_chartread_args(["-v", "-c", "1", "-p", "-F", "n", "-xx", "-Q",
                                          "-B", "Chart"])
    assert not bad.ok and bad.refused == {"-F": "i1pro2_refuses_every_filter",
                                          "-xx": "external_values_not_with_the_table",
                                          "-Q": "option_unknown_to_the_table_job"}
    assert bad.no_meaning["-B"] == "no_meaning_for_spot_readings"
    # round B: without -p the rows are read as strips (a first try), said as an option used
    strip = sp.options_from_chartread_args(["-v", "-c", "1", "Chart"])
    assert strip.options.strip and "strip" in strip.used and "strip" not in strip.no_meaning
    assert set(sp.SETTINGS) >= {"aiming_help", "i1pro2_ruler_check", "i1pro2_lights",
                                "button_gestures", "i1pro3_conditions", "averaging_pass"}


def test_options_the_reader_gets_them_and_a_refused_one_reads_nothing(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    assert job.set_options(["-p", "-S", "-H", "-A", "X", "-n"]).ok
    ready_to_read(job, p)
    assert p.drive(job.read_row()).ok
    assert helper.started[-1][1:] == ["--json", "-S", "-H", "-A", "X", "-n", "-v", "-c", "1",
                                      "-N", "-p", "p1_row1"]
    text = run.i1io_table_session_dir(RS.STAMP)
    m = job.measurement().detail["measurement"]
    assert m["state"] == "partial"
    assert "SPEC_" not in run.i1io_table_measurement(RS.STAMP).read_text(encoding="utf-8")
    assert text.is_dir()
    job2, sim2, helper2, run2, p2 = job_for(tmp_path / "two")
    r = job2.set_options(["-p", "-F", "n"])
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "option_refused")
    # review 9, NOTE: the opening itself is refused while an option is refused (options cannot
    # change after it), so nothing is asked and nothing is sent
    assert p2.drive(job2.open()).reason == "option_refused" and sim2.received == []
    assert job2.calibrate().reason == "table_not_open" and sim2.received == []


def test_a_spot_session_reads_a_strip_only_when_asked(tmp_path):
    """Round B: strip rows exist now; a session with -p (patch by patch) reads patch by patch
    unless a strip is asked for by name (read_row(kind="strip"), never by the window)."""
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    assert job.row_kind == "spot"
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "spot"
    assert not any(ln.startswith(";m2") for ln in sim.received)


# ---- more of the new code, each with its own test (planted faults of step 7) ----------------

def test_every_patch_of_a_row_may_fail_once_and_the_row_still_fits_its_step(tmp_path):
    """A row's own cap (3 n + 4 lines) holds one fresh position reading for EVERY patch."""
    job, sim, helper, run, p = job_for(tmp_path, faults={"read_once": {
        f"0-{i}": "error" for i in range(4)}})
    ready_to_read(job, p)
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read", (r.reason, r.detail)
    assert len(sim.received) - n == 2 + 2 * 4 + 4          # where, still, 4 x (m0 p0), 4 fresh p0


def test_a_reading_not_taken_where_the_arm_was_read_is_a_clean_failure_read_again(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    real = job._patch
    seen = []

    def shifted(reader, pt, rec, readings):
        if not seen:
            seen.append(pt.loc)
            lines, at = job._arrival
            job._arrival = (lines, (at[0] + 50, at[1]))      # the arrival does not match
        return real(reader, pt, rec, readings)
    job._patch = shifted
    n = len(sim.received)
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read"
    rec = next(run.i1io_table_session_dir(RS.STAMP).glob("row-*/p1_row1.row.json"))
    import json
    data = json.loads(rec.read_text(encoding="utf-8"))
    assert [f["why"] for f in data["failed"]] == ["reading_off_target"]
    assert len(sim.received) - n == 2 + 2 * 4 + 1           # one fresh position reading


def test_the_arm_is_never_driven_faster_than_recorded_between_patches(tmp_path, monkeypatch):
    from workflow.i1io.table import reader as rd

    class SimTime:
        def monotonic(self):
            return sim.clock

        def sleep(self, s):
            sim.clock += s
    job, sim, helper, run, p = job_for(tmp_path, faults={"read_s": 0.1})
    monkeypatch.setattr(rd, "time", SimTime())
    ready_to_read(job, p)
    times = []
    sim.on_command = lambda k: times.append((k, sim.clock))
    read_end = []
    helper.on_read = lambda n: read_end.append(sim.clock)
    n0 = len(sim.received)
    assert p.drive(job.read_row()).ok
    m0 = [t for k, t in times if sim.received[k].startswith(";m0")]
    assert len(m0) == 4
    # from the start of each reading (0.1 s long here) to the next move: at least the floor
    for start, nxt in zip(read_end, m0[1:]):
        assert nxt - start >= sp.PACE_FLOOR_S - 1e-6, (start, nxt)
    assert n0 < len(sim.received)


def test_a_row_into_a_part_no_recording_reached_asks_first_and_no_moves_nothing(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.FIRST_VISIT: "no"})
    ready_to_read(job, p)
    n_moves = len(moves(sim.received))
    r = p.drive(job.read_row())
    asked = [d for _s, c, d, *_r in p.asked if c == J.Confirm.FIRST_VISIT]
    assert asked and asked[-1]["what"] == "row 1"
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "first_visit_declined")
    assert len(moves(sim.received)) == n_moves and helper.reads == 0


def test_a_free_arm_left_outside_the_area_starts_no_row(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    sim.hand_to(-1480, 2340)                                # beside the area's corner
    n_moves = len(moves(sim.received))
    r = p.drive(job.read_row())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "free_arm_outside_area")
    assert len(moves(sim.received)) == n_moves and helper.reads == 0


def test_a_failed_calibration_on_the_own_tile_leaves_no_white_until_seated_again(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.CAL_PLACE: "own tile"},
                                       faults={"open": "cal_fails", "open_at": 3})
    # (open_at 3: the second calibration's reader; the first calibration's second reader is
    # the table tile's reading that checks its white, final fix round S-1)
    p.drive(job.open())
    assert p.drive(job.calibrate()).ok and job.calibration is not None
    r = p.drive(job.calibrate())                            # the instrument out again; fails
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "calibration_failed")
    assert job.calibration is None                          # it is not in the arm
    assert job.align().reason == "instrument_not_in_the_arm"
    assert job.read_row().reason == "instrument_not_in_the_arm"
    assert p.drive(job.calibrate()).ok                      # the third: seated again
    assert p.drive(job.align()).ok and p.drive(job.read_row()).ok


def test_while_the_instrument_is_out_of_the_arm_nothing_moves(tmp_path):
    """Own tile: from "ready" (lifted out) until "seated", its cable hangs free: no moving step
    and no reading runs; only a calibration (which asks for "seated" again) does."""
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.CAL_PLACE: "own tile",
                                                  J.Confirm.CAL_RESEAT: "stop"})
    p.drive(job.open())
    assert p.drive(job.calibrate()).reason == "instrument_not_seated_again"
    assert job.instrument_out
    n = len(sim.received)
    for step in ("park", "align", "home", "read_tile", "read_row"):
        assert getattr(job, step)().reason == "instrument_not_in_the_arm", step
    assert len(sim.received) == n
    p.script[J.Confirm.CAL_RESEAT] = "seated"
    assert p.drive(job.calibrate()).ok and not job.instrument_out
    assert p.drive(job.align()).ok


def test_a_calibration_that_fails_with_the_instrument_out_keeps_it_out(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path, {J.Confirm.CAL_PLACE: "own tile"},
                                       faults={"open": "cal_fails"})
    p.drive(job.open())
    assert p.drive(job.calibrate()).reason == "calibration_failed"
    assert job.instrument_out and job.align().reason == "instrument_not_in_the_arm"


def test_the_reading_constants_are_pinned():
    """Part C's plausibility and pace, ArgyllCMS's hour, the helper's 2-minute rule as the
    margin, the reader's own waits, the i1Pro 2's name as ArgyllCMS gives it."""
    assert sp.PLAUSIBLE_Y == (0.2, 130.0) and sp.PACE_FLOOR_S == 1.0
    # S-9: i1Profiler's dual patch 2.0 s; ChromIQ's own single reading with its pace 2.5 s
    assert (sp.CAL_VALID_S, sp.CAL_MARGIN_S, sp.PATCH_S_ESTIMATE) == (3600.0, 120.0, 2.5)
    assert sp.I1PROFILER_DUAL_PATCH_S == 2.0 and sp.SPOT_ROWS_SERPENTINE is False
    assert (sp.OPEN_TIMEOUT_S, sp.READ_TIMEOUT_S) == (45.0, 15.0)
    assert sp.I1PRO2_MODEL == "X-Rite i1 Pro 2" and J.ROWS_READ_AGAIN_PER_PAGE == 2
    assert J.CAL_PLACE_RECOMMENDED == "table tile"


def test_a_row_needs_its_time_and_the_margin_left_on_the_white(tmp_path):
    job, sim, helper, run, p = job_for(tmp_path)
    ready_to_read(job, p)
    # the row's own time is left, but not the two minutes on top
    sim.clock = job.calibration["t"] + sp.CAL_VALID_S - sp.row_seconds(4) - sp.CAL_MARGIN_S / 2
    assert job.read_row().reason == "calibration_due"
