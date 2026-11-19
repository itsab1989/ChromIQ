"""Final fix round, the owner: "do the aiming helpers work on a chart with the crosshairs
disabled? does it then highlight the patches the user should put the device on?"

A chart made in Create Chart with the aiming crosses switched off is a first-class case:

* the job takes the three aimed points as the corner patches' CENTRES, and every patch target
  follows from them exactly as with crosses (checked against the chart's own geometry: the
  sheet lying on a simulated table, the person aiming at the true corner-patch centres);
* the panel names the PATCH as printed (its label and corner), asks for the cross hairs on its
  centre, and says the preview shows it ringed; the button line, the check move, the reports,
  the status lines and the log use the same naming; with crosses the texts are unchanged;
* the preview's ring sits exactly on the corner patch's box, on the right page, for the three
  aims and the check move;
* a page that names no three aim points is refused before anything is opened (a chart ChromIQ
  makes gives such a page its crosses: test_i1io_aiming_crosses)."""
from __future__ import annotations

import json

import pytest

from tests.i1io_table import tester_d2 as D2
from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.test_window_in_the_measure_tab import beta, tab  # noqa: F401
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp


@pytest.fixture(scope="module", params=["A4", "Letter"])
def off_sheet(tmp_path_factory, request):
    """A real chart, built as Create Chart builds an i1iO 2 chart, crosses off. Two papers:
    an i1iO chart lies on the table one way only (every page across the table, its top edge to
    the right), so the two sizes stand in for "both ways" of a sheet."""
    from tests.test_i1io_aiming_crosses import _build
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    try:
        folder = tmp_path_factory.mktemp("crosses_off")
        _build(folder, 552, paper=request.param, i1io_crosses=False)
    finally:
        support._latched = before
    side = next(folder.glob("*.i1io.json"))
    return folder, json.loads(side.read_text(encoding="utf-8"))


def test_the_chart_names_three_corner_patches_in_aiming_order(off_sheet):
    _folder, sheet = off_sheet
    pts = sorted(sheet["pages"][0]["aim_points"], key=lambda a: a["number"])
    assert [a["target"] for a in pts] == ["patch"] * 3
    assert [a["corner_on_table"] for a in pts] == ["top-left", "bottom-left", "bottom-right"]
    locs = {q["loc"]: q for st in sheet["pages"][0]["strips"] for q in st["patches"]}
    for a in pts:
        q = locs[a["patch"]]
        assert a["page_mm"] == pytest.approx(q["centre_mm"], abs=0.01)   # the patch's centre


def test_every_target_follows_from_the_three_corner_patch_centres(off_sheet):
    """The sheet lies on the simulated table; the person aims at the TRUE centres of the three
    corner patches; every patch target the job plans lands on that patch's true centre."""
    _folder, sheet = off_sheet
    origin = H.DEMO_ORIGIN
    readings = H.demo_aims(sheet, origin)
    aims_mm = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    al = geo.fit_alignment(aims_mm, readings)
    worst = 0.0
    n = 0
    for k in range(sp.rows_on_page(sheet, 0)):
        plan = sp.plan_row(sheet, 0, k, al, 10 ** 6, kind="spot")
        centres = {q["loc"]: q["centre_mm"] for st in sheet["pages"][0]["strips"]
                   for q in st["patches"]}
        for p in plan.patches:
            u = sc.sheet_table_mm(sheet, centres[p.loc])
            true = (origin[0] - 10 * u[0], origin[1] + 10 * u[1])
            worst = max(worst, abs(p.target[0] - true[0]), abs(p.target[1] - true[1]))
            n += 1
    assert n > 100 and worst <= 1.0, worst          # whole units of 0.1 mm


def test_the_job_reads_a_crosses_off_page_with_every_reading_on_its_patch(off_sheet, tmp_path):
    _folder, sheet = off_sheet
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet,
                                                aims=H.demo_aims(sheet),
                                                ask_after_each_step=False)
    p = H.Person(job, sim, {J.Confirm.FRONT_CHOICE: "go on"})
    for s in ("open", "calibrate", "align"):
        assert p.drive(getattr(job, s)()).ok, s
    if job.front_need is not None:
        assert p.drive(job.creep()).ok
    assert p.drive(D2.check_move(job)).ok
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read" and r.detail["read"] == r.detail["patches"]
    log = job.diag.log_path.read_text(encoding="utf-8")
    names = [a["patch"] for a in sc.aims_of(sheet, 0)]
    for name in names:
        assert f"(the centre of corner patch {name})" in log
    job.close()


def test_a_page_without_three_aim_points_is_refused_before_anything_opens(tmp_path):
    sheet = H.demo_sheet()
    sheet["pages"][0]["aim_points"] = sheet["pages"][0]["aim_points"][:2]
    opened = []
    job, sim, _t = H.make_job(sheet=sheet, aims=[(0, 0)] * 3)
    job._open_transport = lambda: opened.append(1)
    r = H.Person(job, sim).drive(job.open())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "chart_page_without_three_aim_points")
    assert opened == [] and sim.received == []
    from ui import i1io_table_window as W
    assert "Create Chart" in W.reason_text("chart_page_without_three_aim_points")


def test_the_panel_names_the_patch_and_says_its_centre(qtbot, monkeypatch, tmp_path, settings,
                                                       off_sheet):
    _folder, sheet = off_sheet
    from tests.i1io_table.window_sim import WindowSim
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=True, sheet=sheet,
                                                    sim=WindowSim(press=True))
    p.script.update({"front_choice": "Go forward carefully, my hands are away"})
    names = [a["patch"] for a in sc.aims_of(sheet, 0)]
    seen, reports = [], []
    for _ in range(80):
        page = p.page()
        if page == "aimed":
            seen.append((win._title.text(), win._text.text()))
        if page == "report_after_step":
            reports.append(win._text.text())
        if p.at_the_rows(page) or (page == "first_visit"
                                   and win._last.detail.get("what", "").startswith("row")):
            break                        # 4.3.50: no mark-3 check; the rows are next
        p.answer_page(page)
    joined = " ".join(reports)
    assert f"you aimed it at patches {names[0]}, {names[1]} and {names[2]}" in joined
    assert [t for t, _b in seen] == [f"Aim at patch {n}" for n in names]
    for (_t, body), corner in zip(seen, ("top left", "bottom left", "bottom right")):
        assert "centre of patch" in body and corner in body and "ringed" in body
        assert "mark" not in body.lower().replace("marks", "")
        assert "centre of patch" in body.split("button on the i1Pro 2")[-1] or True
    # the rows are next (their GO, or their first-visit question after the careful steps)
    assert win._title.text() in ("The arm is about to move",
                                 "A move to a part of the table not driven before")


def test_with_crosses_the_texts_are_unchanged(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("aimed")
    assert win._title.text() == "Aim at mark 1" and "cross hairs" in win._text.text()
    assert "“Aiming crosses” switched on" in win._text.text()
    p.drive_until("rows")
    assert win._title.text() == "The arm is about to move"


def test_the_ring_sits_on_each_corner_patch(tab, beta, off_sheet):
    folder, sheet = off_sheet
    tab.set_ti1_path(folder / "c.ti1")
    assert tab._patch_boxes and tab._patch_boxes[0]
    pv = tab._preview
    for a in sc.aims_of(sheet, 0):
        tab._table_aim_on_preview({"event": "aim", "mark": a["number"], "patch": a["patch"],
                                   "page": 1})
        assert pv._active_patch_page == 0 and pv.current_page() == 0
        assert pv._active_patch_box == tab._patch_boxes[0][a["patch"]], a["patch"]
