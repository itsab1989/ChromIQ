"""The strip-row sittings whose wire the job must send byte for byte as tester 0.6.0 (round B).

Each case: the tester's stages (part C: C1, D1, D2, E2 or E3, F) and the job's steps for the same
situation ("Patch-by-patch mode (-p)" off: strip rows), the same simulated table, the same
simulated table-scan reader (part C's FakeScanReader, the strip scan at the recorded pace), the
same faults. ``job_run(case)`` runs the job and returns what it wrote to the table. The tester's
side is captured by round B's ``tools/wire_tester_b.py`` into ``data/tester_060_strip_wire.json``.
E1 (the RECORDED i1Profiler row of 14 November) has no situation in the app."""
from __future__ import annotations

from tests.i1io_table import job_harness as H
from tests.i1io_table import must1_wire as M1
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import reader_sim as RS
from workflow.i1io.table import job as J
from workflow.i1io.table import usb_system as us

STRIP_ARGS = ["-v", "-c", "1", "chart"]          # no -p: strip rows
E2 = (["c1", "d1", "d2", "e2", "f"],
      ["open", "calibrate", "align", "check_move", ("read_row", 1), "home"])
E3 = (["c1", "d1", "d2", "e3", "f"], ["open", "calibrate", "align", "check_move", "page",
                                      "home"])
#: the job's answer to a failed strip row where the tester's stage simply failed: stop
STOP_ROW = {J.Confirm.ROW_FAILED_STRIP: "stop"}


def _case(tester, job, **kw):
    return dict(tester=tester, job=job, **kw)


#: the length of the E2 sitting's wire (tester 0.6.0 and job alike): every line gets a fault
BASE_LEN = 66


def cases(base_len: "int | None" = BASE_LEN):
    out = {
        "S C1 D1 D2 E2 F": _case(*E2),
        "S C1 D1 D2 E3 F": _case(*E3),
        "S own tile C1 D1 D2 E2 F": _case(*E2, tester_script={
            "Where should the instrument be calibrated": "own"},
            job_script={J.Confirm.CAL_PLACE: "own tile"}),
    }
    for fault in ("no_lamp", "not_ready", "lights_err", "fire_unsent", "dies_at_fire",
                  "dark_fail"):
        out[f"T E2 scan {fault}"] = _case(*E2, scan_faults={fault: True}, job_script=STOP_ROW)
    if base_len:
        for kind in ("unplug", "no_answer", "status", "late"):
            for i in range(base_len):
                out[f"U {kind} at {i}"] = _case(*E2, fault=(i, kind), job_script=STOP_ROW)
        for i in range(base_len):
            out[f"V cancel at {i}"] = _case(*E2, cancel_at=i, job_script=STOP_ROW)
    return out


def job_run(case: dict, tmp_path, ask_after_each_step: bool = True):
    """(lines sent, results, sim, helper)."""
    sim = csim.CSimTable(part_c=True, aims=list(H.demo_aims()))
    if "fault" in case:
        i, kind = case["fault"]
        # 4.3.47 MUST-1: tester line i is the job's line job_index(i) (must1_wire)
        sim.inject_at(M1.job_index(i, M1.EXTRA_IN_STRIP_E2_SITTING), kind, 30.0 if kind == "late" else 1.0)
    holder = {}
    if "cancel_at" in case:
        sim.on_command = (lambda k, i=M1.job_index(case["cancel_at"], M1.EXTRA_IN_STRIP_E2_SITTING):
                          holder["job"].cancel()
                          if k == i else None)
    faults = {"scan": dict(case["scan_faults"]), "scan_at": 2} if case.get("scan_faults") \
        else None
    job, sim, helper, _run = RS.make_reading_job(
        tmp_path, faults=faults, sim=sim,
        instrument=lambda: us.Check("ok", {"i1pro_devices": 1}),
        ask_after_each_step=ask_after_each_step)
    holder["job"] = job
    sim.job = job          # 4.3.47 MUST-1: its own record of the extra readings
    assert job.set_options(STRIP_ARGS).ok
    script = dict(case.get("job_script") or {})
    person = H.Person(job, sim, script)
    results = []
    for s in case["job"]:
        if s == "page":
            while job.rows_left():
                res = person.drive(job.read_row())
                results.append(res)
                if not res.ok:
                    break
            if results and results[-1].kind == J.Kind.STOPPED:
                break
            continue
        if isinstance(s, tuple):
            res = person.drive(getattr(job, s[0])(*s[1:]))
        else:
            res = person.drive(getattr(job, s)())
        results.append(res)
        if res.kind == J.Kind.STOPPED:
            break
    results.append(job.close())
    return sim.received, results, sim, helper
