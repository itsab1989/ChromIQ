"""Driving the table job headless against the simulator (test support, not shipped).

The person's side is a SCRIPT: for every confirmation the job asks for, the answer is looked up
(per confirmation kind, optionally per mark); a missing answer fails the test (the job never
answers itself). At an aim the simulated hand puts the sight on the mark first, as the tester's
simulated run does.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from tests.i1io_table import part_c_sim as csim
from tests.i1io_table import session_sim as ss
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import reach as rc
from workflow.i1io.table import scan as sc
from workflow.i1io.table import usb_system as us

HERE = Path(__file__).resolve().parent
DEMO_SHEET = HERE / "data" / "demo-sheet.i1io.json"
DEMO_ORIGIN = (1650, 700)


def demo_sheet() -> dict:
    return json.loads(DEMO_SHEET.read_text(encoding="utf-8"))


def demo_aims(sheet=None, origin=DEMO_ORIGIN, page=0):
    sheet = sheet or demo_sheet()
    out = []
    for a in sc.aims_of(sheet, page):
        u = sc.sheet_table_mm(sheet, a["page_mm"])
        out.append((int(round(origin[0] - 10 * u[0])), int(round(origin[1] + 10 * u[1]))))
    return out


def recorded_sheet(name: str, rows: int, cols: int = 28) -> "tuple[dict, tuple]":
    """The tester's _recorded_sheet: a sheet whose three marks are the corner patches of a chart
    with the sizes of the recorded alignment *name* (its aims are the recorded p1 readings)."""
    pts = geo.RECORDED_ALIGNMENTS[name]
    W = math.dist(pts[1], pts[2]) / 10
    H = math.dist(pts[0], pts[1]) / 10
    h, x0, y0 = 297.0, 20.0, 20.0

    def page(tx, ty):
        return [round(ty, 3), round(h - tx, 3)]
    strips, sid = [], 1
    for r in range(rows + 1):
        ty = y0 + r * H / rows
        pats = []
        for c in range(cols):
            tx = x0 + c * W / (cols - 1)
            pats.append({"loc": f"R{r + 1}C{c + 1}", "sample_id": sid, "centre_mm": page(tx, ty)})
            sid += 1
        run = sorted((h - (x0 + W + 5), h - (x0 - 5)))
        strips.append({"x_mm": round(ty, 3), "run_mm": [round(v, 3) for v in run],
                       "patches": pats})
    aims = [{"number": 1, "corner_on_table": "top-left", "target": "patch", "patch": "R1C1",
             "page_mm": page(x0, y0)},
            {"number": 2, "corner_on_table": "bottom-left", "target": "patch",
             "patch": f"R{rows + 1}C1", "page_mm": page(x0, y0 + H)},
            {"number": 3, "corner_on_table": "bottom-right", "target": "patch",
             "patch": f"R{rows + 1}C{cols}", "page_mm": page(x0 + W, y0 + H)}]
    sheet = {"schema": 1, "paper_mm": [210.0, h], "patch_mm": [8.0, round(W / (cols - 1), 3)],
             "orientation": "as in your i1Profiler session", "table_model": "i1iO 2",
             "head_model": "i1Pro 2", "pages": [{"strips": strips, "aim_points": aims}]}
    return sheet, pts


class FixedReachStore(rc.ReachStore):
    """4.3.49: a store that gives every table the same reach (the one a test assumes) and keeps
    what the job stores in ``put_calls`` without changing what it gives."""

    def __init__(self, reach: dict):
        self.reach = dict(reach)
        self.put_calls: "list[dict]" = []
        super().__init__(lambda: "", lambda _t: None)

    def salt(self) -> str:
        return "0" * 32

    def get(self, key):
        return rc.Reach.from_dict(key, dict(self.reach))

    def put(self, reach) -> bool:
        self.put_calls.append(reach.as_dict())
        reach.dirty = False
        return True


#: 4.3.49: a table that has shown ChromIQ nothing yet (the model's defaults; no motor arrival
#: in the front zone remembered, so every sitting creeps as in 4.3.48). The tests written before
#: the remembered reach run on it; the reach's own tests pass their own store.
REACH_LIKE_4348: dict = {}


def store_like_4348() -> FixedReachStore:
    return FixedReachStore(REACH_LIKE_4348)


OK_PREFLIGHT = us.Preflight("macos", {"platform": "darwin"}, us.Check("ok", {"i1pro_devices": 1}),
                            us.Check("nobody_listed"), False)

#: the tester's AutoConsole: the first choice to every question, except where a script says
DEFAULT = {J.Confirm.START_UP: "yes", J.Confirm.GO: "yes", J.Confirm.SHEET_LAID: "yes",
           J.Confirm.ARM_FELT: "free", J.Confirm.AIMED: "aimed", J.Confirm.FRONT_CHOICE: "back",
           J.Confirm.FRONT_YES: "yes", J.Confirm.FIRST_VISIT: "yes",
           J.Confirm.MARKER: "switched off and on", J.Confirm.READY_TO_OPEN: "yes",
           #: the person's report after a step that moved (tester: "did it do what was
           #: described?"; its AutoConsole answered "yes")
           "report": "as described",
           # step 7 (the tester's AutoConsole: the first choice; CAL_WHERE's first was "arm",
           # the table's tile)
           J.Confirm.READER_CONSENT: "yes", J.Confirm.CAL_PLACE: "table tile",
           J.Confirm.CAL_OWN_TILE: "ready", J.Confirm.CAL_RESEAT: "seated",
           J.Confirm.ROW_FAILED: "again",
           # round B: a failed strip row (again as a strip / patch by patch / skip / stop)
           J.Confirm.ROW_FAILED_STRIP: "patch by patch",
           #: what the person answers when "again" is refused (two rows read again already)
           "after_again_refused": "skip"}


class Person:
    def __init__(self, job, sim, script=None, on_ask=None):
        self.job, self.sim = job, sim
        self.script = dict(DEFAULT)
        self.script.update(script or {})
        self.asked: "list[tuple]" = []
        self.reports: "list[tuple[str, str]]" = []
        self.on_ask = on_ask

    def drive(self, res):
        while res.kind == J.Kind.NEEDS:
            self.asked.append((res.step, res.confirm, dict(res.detail), len(self.sim.received),
                               self.sim.moving))
            if self.on_ask is not None:
                stop = self.on_ask(self, res)
                if stop is not None:
                    return stop
            key = (res.confirm, res.detail.get("mark"))
            ans = self.script.get(key, self.script.get(res.confirm))
            assert ans is not None, f"no scripted answer for {res.confirm}"
            if res.confirm == J.Confirm.AIMED and ans == "aimed":
                self.sim.aim(res.detail["mark"])
            asked = res.confirm
            res = self.job.answer(asked, ans)
            if (asked in (J.Confirm.ROW_FAILED, J.Confirm.ROW_FAILED_STRIP)
                    and res.kind == J.Kind.REFUSED
                    and res.reason == "rows_read_again_limit"):
                self.refused_again = getattr(self, "refused_again", 0) + 1
                res = self.job.answer(asked, self.script["after_again_refused"])
        if res.confirm == J.Confirm.REPORT_AFTER_STEP and self.script.get("report") is not None:
            self.reports.append((self.job.report_due, self.script["report"]))
            self.report_result = self.job.answer(J.Confirm.REPORT_AFTER_STEP,
                                                 self.script["report"])
        return res


def make_job(sim=None, sheet=None, aims=None, folder=None, preflight=None, run=None, stamp=None,
             other_program=None, ask_after_each_step=True, reach_store=None, **simkw):
    sheet = sheet or demo_sheet()
    if sim is None:
        sim = csim.CSimTable(part_c=True, aims=aims or demo_aims(sheet), **simkw)
    else:
        sim.part_c = True
        if not sim.aims:
            sim.aims = list(aims or demo_aims(sheet))
    transport = ss.SimTransport(sim)
    job = J.TableJob(sheet, folder=folder, run=run, stamp=stamp,
                     open_transport=lambda: transport,
                     preflight=lambda: preflight or OK_PREFLIGHT,
                     other_program=other_program or (lambda: False),
                     ask_after_each_step=ask_after_each_step,
                     reach_store=reach_store if reach_store is not None else store_like_4348())
    return job, sim, transport


def run_steps(steps, script=None, on_ask=None, **kw):
    """Run *steps* in order (each driven to its end), then close. Returns (results, job, sim,
    person). A stopped step ends the list (nothing more could be sent anyway)."""
    job, sim, _t = make_job(**kw)
    person = Person(job, sim, script, on_ask)
    results = []
    for s in steps:
        res = person.drive(getattr(job, s)())
        results.append(res)
        if res.kind == J.Kind.STOPPED:
            break
    results.append(job.close())
    return results, job, sim, person
