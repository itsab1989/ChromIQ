"""The sittings whose wire the job must send byte for byte as tester 0.6.0 (test support).

Each case: the tester's stages (as its capture tool chose them) and the job's steps for the same
situation; ``job_lines(case)`` runs the job on the simulator and returns what it wrote."""
from __future__ import annotations

from tests.i1io_table import job_harness as H
from tests.i1io_table import must1_wire as M1
from tests.i1io_table import part_c_sim as csim
from workflow.i1io.table import job as J

ALIGN = ["open", "align", "check_move", "home"]


def _wrong():
    good = H.demo_aims()

    def rot(points, deg):
        import math
        cx = sum(p[0] for p in points) / 3
        cy = sum(p[1] for p in points) / 3
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        return [(round(cx + c * (x - cx) - s * (y - cy)), round(cy + s * (x - cx) + c * (y - cy)))
                for x, y in points]
    return {"swapped corners": [good[1], good[0], good[2]],
            "swapped 2 and 3": [good[0], good[2], good[1]],
            "mirrored": [(2 * 150 - x, y) for x, y in good],
            "a corner one patch off": [good[0], good[1], (good[2][0] + 100, good[2][1])],
            "mark 2 one patch off": [good[0], (good[1][0], good[1][1] - 90), good[2]],
            "turned 180": rot(good, 180), "turned 90": rot(good, 90),
            "turned 5 degrees": rot(good, 5), "all on one spot": [good[0], good[0], good[0]]}


def cases(base_len: int = 54):
    out = {"A warm d1 d2 f": dict(steps=ALIGN),
           "B cold d1 d2 f": dict(steps=["open", "start_up", "align", "check_move", "home"],
                                  simkw=dict(cold=True))}
    for name, rows in (("S2 684.0", 18), ("R1 401.6", 17)):
        out[f"C {name} d1 dz d2 f"] = dict(steps=["open", "align", "creep", "check_move", "home"],
                                           recorded=(name, rows),
                                           script={J.Confirm.FRONT_CHOICE: "go on"},
                                           must1=M1.EXTRA_IN_CREEP_SITTINGS[name])
        out[f"D {name} d1 back f"] = dict(steps=["open", "align", "home"], recorded=(name, rows))
    for wname, aims in _wrong().items():
        out[f"E wrong {wname} d1 f"] = dict(steps=["open", "align", "home"], aims=aims)
    for kind in ("unplug", "no_answer", "status", "late"):
        for i in range(base_len):
            out[f"F {kind} at {i}"] = dict(steps=ALIGN, fault=(i, kind))
    for i in range(base_len):
        out[f"G cancel at {i}"] = dict(steps=ALIGN, cancel_at=i)
    return out


def job_lines(case: dict, ask_after_each_step: bool = True):
    kw = {}
    sheet = aims = None
    if "recorded" in case:
        sheet, aims = H.recorded_sheet(*case["recorded"])
    if "aims" in case:
        aims = case["aims"]
    sim = csim.CSimTable(part_c=True, aims=list(aims or H.demo_aims()),
                         **case.get("simkw", {}))
    if "must1" in case:
        M1.rng_neutral_at(sim, case["must1"])
    if "fault" in case:
        i, kind = case["fault"]
        # 4.3.47 MUST-1: tester line i is the job's line job_index(i) (must1_wire)
        sim.inject_at(M1.job_index(i, M1.EXTRA_IN_ALIGN_SITTING), kind, 30.0 if kind == "late" else 1.0)
    holder = {}
    if "cancel_at" in case:
        sim.on_command = (lambda k, i=M1.job_index(case["cancel_at"], M1.EXTRA_IN_ALIGN_SITTING):
                          holder["job"].cancel()
                          if k == i else None)
    job, sim, _t = H.make_job(sim=sim, sheet=sheet, aims=aims,
                              ask_after_each_step=ask_after_each_step)
    holder["job"] = job
    sim.job = job          # 4.3.47 MUST-1: its own record of the extra readings
    person = H.Person(job, sim, case.get("script"))
    results = []
    for s in case["steps"]:
        res = person.drive(getattr(job, s)())
        results.append(res)
        if res.kind == J.Kind.STOPPED:
            break
    results.append(job.close())
    return sim.received, results, sim
