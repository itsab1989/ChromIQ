"""The reading sittings whose wire the job must send byte for byte as tester 0.6.0 (step 7).

Each case: the tester's stages (part C: C1, C2, D1, D2, D3, D4, F) and the job's steps for the
same situation, the same simulated helper (``reader_sim``) behind each one's own reader module,
and the same faults. ``job_run(case)`` runs the job on the app's simulator and returns what it
wrote to the table and how it started the reader. The tester's side is captured by the step 7
work folder's ``tools/wire_tester7.py`` into ``data/tester_060_reading_wire.json``.

C3 and C4 (the RECORDED i1Profiler row of 14 November, read at its recorded places) have no
situation in the app: the job reads the person's ChromIQ sheet only, so there is no job step to
compare them with."""
from __future__ import annotations

from tests.i1io_table import job_harness as H
from tests.i1io_table import must1_wire as M1
from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import reader_sim as RS
from workflow.i1io.table import job as J
from workflow.i1io.table import usb_system as us

OWN = {"tester_script": {"Where should the instrument be calibrated": "own"},
       "job_script": {J.Confirm.CAL_PLACE: "own tile"}}
D3 = (["c1", "d1", "d3", "f"], ["open", "calibrate", "align", "read_row", "home"])


def _case(tester, job, **kw):
    return dict(tester=tester, job=job, **kw)


#: the length of the D3 sitting's wire (tester 0.6.0 and job alike): every line gets a fault
BASE_LEN = 102


def cases(base_len: "int | None" = BASE_LEN):
    out = {
        "A C1 table tile": _case(["c1"], ["open", "calibrate"]),
        "B C1 own tile": _case(["c1"], ["open", "calibrate"], **OWN),
        "C C1 C2": _case(["c1", "c2"], ["open", "calibrate", "read_tile"]),
        "D C1 D1 D3 F": _case(*D3),
        "D own tile C1 D1 D3 F": _case(*D3, **OWN),
        "E C1 D1 D4 F": _case(["c1", "d1", "d4", "f"],
                              ["open", "calibrate", "align", "page", "home"]),
        "E C1 D1 D2 D3 F": _case(["c1", "d1", "d2", "d3", "f"],
                                 ["open", "calibrate", "align", "check_move", "read_row",
                                  "home"]),
        "E C1 D1 D3 D3 F": _case(["c1", "d1", "d3", "d3", "f"],
                                 ["open", "calibrate", "align", "read_row", ("read_row", 1),
                                  "home"]),
        # the tester's C1 checks twice (its strip reader, then its spot reader), the job's once
        "H D3 no instrument at its reader": _case(*D3, check_fail_at=2, tester_check_fail_at=3),
        "H D3 reader finds no instrument": _case(*D3, faults={"open": "no_instrument",
                                                              "open_at": 2}),
        "H D3 reader dies at its start": _case(*D3, faults={"open": "dies", "open_at": 2}),
    }
    for k in (1, 5, 23):
        out[f"I D3 stopped after reading {k}"] = _case(*D3, stop_after_reading=k)
    if base_len:
        for kind in ("unplug", "no_answer", "status", "late"):
            for i in range(base_len):
                out[f"F {kind} at {i}"] = _case(*D3, fault=(i, kind))
        for i in range(base_len):
            out[f"G cancel at {i}"] = _case(*D3, cancel_at=i)
    return out


def job_run(case: dict, tmp_path, ask_after_each_step: bool = True):
    """(lines sent, reader arguments without the program path, reader charts, results)."""
    sim = csim.CSimTable(part_c=True, aims=list(H.demo_aims()))
    if "fault" in case:
        i, kind = case["fault"]
        # 4.3.47 MUST-1: tester line i is the job's line job_index(i) (must1_wire)
        sim.inject_at(M1.job_index(i, M1.EXTRA_IN_READING_D3_SITTING), kind, 30.0 if kind == "late" else 1.0)
    holder = {}
    if "cancel_at" in case:
        sim.on_command = (lambda k, i=M1.job_index(case["cancel_at"], M1.EXTRA_IN_READING_D3_SITTING):
                          holder["job"].cancel()
                          if k == i else None)
    checks = [0]

    def instrument():
        checks[0] += 1
        if case.get("check_fail_at") == checks[0]:     # the job's own count of checks
            return us.Check("no_instrument", {"i1pro_devices": 0})
        return us.Check("ok", {"i1pro_devices": 1})
    job, sim, helper, _run = RS.make_reading_job(tmp_path, faults=case.get("faults"), sim=sim,
                                                 instrument=instrument,
                                                 ask_after_each_step=ask_after_each_step)
    holder["job"] = job
    sim.job = job          # 4.3.47 MUST-1: its own record of the extra readings
    if "stop_after_reading" in case:
        helper.on_read = (lambda n, k=case["stop_after_reading"]: job.stop_at_next_pause()
                          if n == k else None)
    person = H.Person(job, sim, case.get("job_script"))
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
    return sim.received, [a[1:] for a in helper.started], helper.charts, results, sim
