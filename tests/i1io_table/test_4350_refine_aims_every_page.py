"""4.3.50 (the owner's explicit requirement, owed since 4.3.49): in a REFINEMENT of a multipage
i1iO chart, every page that is read is aimed again with its own three points IN THAT SITTING; no
sheet position is reused from an earlier sitting or from another page.

How the job holds it: the sheet position is ``TableJob.alignment``, set only by ``_align`` from
this sitting's three p1 readings, cleared at ``next_page``, at every homing and at a failed
alignment; a row refuses ``needs_alignment`` without it; a job is built per START. These tests
fail if a page could be read without being aimed in the same sitting: by behaviour (a two-page
refinement, the sheet of page 2 laid elsewhere than page 1's), and by a census of the source (no
other code gives the job a sheet position).
"""
from __future__ import annotations

import ast
from pathlib import Path

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_job_reading import job_for, read_page, small_sheet
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J

ROOT = Path(__file__).resolve().parents[2]
LATER = "20261119-160000"


def _two_pages() -> dict:
    """Two pages whose patches have their own ids and names (small_sheet(pages=2) repeats
    page 1's, which a measurement file cannot hold)."""
    sheet = small_sheet(pages=2)
    n = sum(len(st["patches"]) for st in sheet["pages"][0]["strips"])
    for st in sheet["pages"][1]["strips"]:
        for q in st["patches"]:
            q["sample_id"] = str(int(q["sample_id"]) + n)
            q["loc"] = "2-" + q["loc"]
    return sheet


def _full_measurement(tmp_path, sheet):
    job, sim, helper, run, p = job_for(tmp_path, sheet=sheet)
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    assert all(r.ok for r in read_page(job, p))
    assert p.drive(job.home()).ok and job.next_page().ok
    assert p.drive(job.align()).ok
    assert all(r.ok for r in read_page(job, p))
    assert job.save().ok
    return job, run


def test_a_two_page_refinement_aims_each_page_again_in_its_own_sitting(tmp_path, monkeypatch):
    sheet = _two_pages()
    first, run = _full_measurement(tmp_path, sheet)
    earlier = first.alignment
    # the refinement: one row of each page (a quality check's list), a NEW sitting
    locs = {sheet["pages"][0]["strips"][1]["patches"][0]["loc"],
            sheet["pages"][1]["strips"][0]["patches"][0]["loc"]}
    job, sim, helper, run2, p = job_for(tmp_path, sheet=sheet, stamp=LATER)
    fits = []
    real = geo.fit_alignment

    def counted(aims_mm, readings):
        fits.append([tuple(r) for r in readings])
        return real(aims_mm, readings)
    monkeypatch.setattr(geo, "fit_alignment", counted)
    rep = job.set_options(["-p", "-r"], only_locs=locs)
    assert rep.ok and rep.detail.get("refine") == 2, rep.detail
    assert job.alignment is None                       # nothing of the earlier sitting
    for s in ("open", "calibrate"):
        assert p.drive(getattr(job, s)()).ok, s
    # a row before the aims: refused, nothing sent
    n = len(sim.received)
    r = job.read_row()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "needs_alignment") and len(sim.received) == n
    # page 1: its own three points
    assert p.drive(job.align()).ok
    page1 = job.alignment
    assert page1 is not earlier and len(fits) == 1
    assert [tuple(x) for x in page1.readings] == fits[0]
    assert all(r.ok for r in read_page(job, p))
    # page 2: the sheet is laid 3 mm further right and 2 mm further back than page 1 was
    assert p.drive(job.home()).ok
    assert job.next_page().ok and job.page == 1
    assert job.alignment is None
    n = len(sim.received)
    r = job.read_row()
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "needs_alignment") and len(sim.received) == n
    sim.aims = [(x + 30, y - 20) for x, y in sim.aims]
    assert p.drive(job.align()).ok
    page2 = job.alignment
    assert page2 is not page1 and len(fits) == 2
    assert [tuple(x) for x in page2.readings] == fits[1]
    for a, b in zip(page1.readings, page2.readings):
        assert abs((b[0] - a[0]) - 30) <= 6 and abs((b[1] - a[1]) + 20) <= 6, (a, b)
    assert all(r.ok for r in read_page(job, p))
    assert job.save().ok
    # the diagnostics name both pages' aims, both from this sitting
    assert [e["page"] for e in job.reach_diag["aims"]] == [1, 2]
    assert sim.violations == []


def test_a_homing_in_the_middle_of_a_page_means_aiming_again(tmp_path):
    sheet = small_sheet(pages=2)
    job, sim, helper, run, p = job_for(tmp_path, sheet=sheet)
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    assert p.drive(job.read_row()).ok
    assert p.drive(job.home()).ok
    assert job.alignment is None
    n = len(sim.received)
    assert job.read_row().reason == "needs_alignment" and len(sim.received) == n


def _assignments(tree):
    """(function name, owner, value source) of every assignment to ``<owner>.alignment``."""
    out = []

    class V(ast.NodeVisitor):
        stack: "list[str]" = []

        def visit_FunctionDef(self, node):
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Assign(self, node):
            for t in node.targets:
                for el in (t.elts if isinstance(t, ast.Tuple) else [t]):
                    if isinstance(el, ast.Attribute) and el.attr == "alignment":
                        out.append((self.stack[-1] if self.stack else "<module>",
                                    ast.unparse(el.value), ast.unparse(node.value)))
            self.generic_visit(node)
    V().visit(tree)
    return out


def test_only_the_aiming_gives_the_job_a_sheet_position():
    """The census: in the app's code, the job's ``alignment`` is set to anything but None
    only in ``_align`` (from this sitting's readings), and nothing outside the job sets it."""
    seen = {}
    for folder in ("workflow", "ui", "core", "scripts"):
        for f in (ROOT / folder).rglob("*.py"):
            text = f.read_text(encoding="utf-8", errors="replace")
            if ".alignment" not in text:
                continue
            got = [(fn, v) for fn, owner, v in _assignments(ast.parse(text))
                   if not owner.startswith(("cell", "ws.cell"))]   # openpyxl: a text style
            if got:
                seen[str(f.relative_to(ROOT))] = got
    job_py = "workflow/i1io/table/job.py"
    assert set(seen) == {job_py}, seen
    setters = [(fn, v) for fn, v in seen[job_py] if v != "None"]
    assert setters == [("_align", "al")], seen[job_py]
    # ...and is cleared at the next page and at every homing (two guards: the next page needs
    # the arm at rest, which a homing gives; each is pinned on its own)
    assert ("next_page", "None") in seen[job_py] and \
        ("_alignment_homed", "None") in seen[job_py], seen[job_py]
    # and _align fits only the readings it took itself (no stored or passed-in position)
    src = ast.get_source_segment((ROOT / job_py).read_text(encoding="utf-8"), next(
        n for n in ast.walk(ast.parse((ROOT / job_py).read_text(encoding="utf-8")))
        if isinstance(n, ast.FunctionDef) and n.name == "_align"))
    assert "geo.fit_alignment(aims_mm, readings)" in src
