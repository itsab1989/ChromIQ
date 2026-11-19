"""4.3.49 acceptance: the owner's EXACT three aims of 19 Nov 2026 (session 124127, round 1, at the
crosses of ChromIQ's A4 chart) replayed through the job on the simulated table, and wider sheets
up to the largest the i1iO chart builder takes (230 x 320 mm, the table's reach), and the chart
kinds: with crosses and without (corner patches).

What these tests pin (the honest answers, see the report):

* his exact aims, sheet where he laid it: refused at the three points (mark 2 and 3 at Y 3253,
  the target area ends at Y 3109), with the advice "about 16 mm towards the back";
* the same aims with the sheet laid as the page says: the run goes on through the front-zone
  creep, the check move to mark 3, and reads the first row;
* the largest sheet: refused where his sheet lay, accepted and read when laid as advised;
* a chart without crosses: the pages name the corner PATCH and never a cross.
"""
from __future__ import annotations

import pytest

from core.i18n import tr
from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_job_safety import shaped_sheet
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import scan as sc

CROSSES_1 = [(1394, 1369), (1402, 3253), (-1362, 3253)]        # his round 1, exact
GO_ON = {J.Confirm.FRONT_CHOICE: "go on"}


def _shift(aims, dx, dy):
    return [(x + dx, y + dy) for x, y in aims]


def _through_first_row(tmp_path, sheet, aims):
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=aims,
                                                ask_after_each_step=False)
    p = H.Person(job, sim, GO_ON)
    out = []
    for step in ("open", "calibrate", "align"):
        r = p.drive(getattr(job, step)())
        out.append((step, r.kind, r.reason))
        if not r.ok:
            return out, job, sim
    if job.front_need:
        r = p.drive(job.creep())
        out.append(("creep", r.kind, r.reason))
        if not r.ok:
            return out, job, sim
    r = p.drive(job.check_move())
    out.append(("check_move", r.kind, r.reason))
    if r.ok:
        r = p.drive(job.read_row())
        out.append(("read_row", r.kind, r.reason))
    return out, job, sim


# ---- Q1: the exact same thing on the same sheet -------------------------------------------------

def test_q1_his_exact_aims_are_still_refused_at_the_three_points_with_the_way_on(tmp_path):
    out, job, sim = _through_first_row(tmp_path, H.demo_sheet(), CROSSES_1)
    assert out[-1] == ("align", J.Kind.REFUSED, "aims_outside_area"), out
    assert job.align_refusals_in_a_row == 1


def test_q1_laid_as_the_page_says_his_aims_go_on_to_the_first_row(tmp_path):
    out, job, sim = _through_first_row(tmp_path, H.demo_sheet(), _shift(CROSSES_1, 0, -160))
    assert [s for s, k, _r in out if k != J.Kind.OK] == [], out
    assert out[-1][0] == "read_row" and sim.violations == []


# ---- Q2: wider marks, up to the largest sheet --------------------------------------------------

def _largest_sheet():
    """230 x 320 mm (the table's reach, the largest sheet the chart builder lays across it),
    crosses 8 / 12 mm in, 28 strips of 30 patches."""
    return shaped_sheet([30] * 28)


def _aims(sheet, origin):
    return H.demo_aims(sheet, origin=origin)


def test_q2_the_largest_sheet_laid_where_his_lay_is_refused_with_how_far(tmp_path):
    sheet = _largest_sheet()
    aims = _aims(sheet, (1504, 1259))                 # his sheet's corner, as on 19 Nov
    res, job, sim, _p = H.run_steps(["open", "align"], sheet=sheet, aims=aims)
    r = res[1]
    assert r.reason == "aims_outside_area"
    mv = r.detail["sheet_move"]
    assert mv["back_mm"] > 0 and mv["left_mm"] > 0


def test_q2_the_largest_sheet_laid_as_advised_reads_its_first_row(tmp_path):
    sheet = _largest_sheet()
    first = H.run_steps(["open", "align"], sheet=sheet, aims=_aims(sheet, (1504, 1259)))[0][1]
    mv = first.detail["sheet_move"]
    origin = (1504 + 10 * mv["left_mm"], 1259 - 10 * mv["back_mm"])
    out, job, sim = _through_first_row(tmp_path, sheet, _aims(sheet, origin))
    assert [s for s, k, _r in out if k != J.Kind.OK] == [], out
    assert sim.violations == []


def test_q2_no_sheet_the_builder_makes_is_wider_than_the_target_area():
    """The reason a refused sheet can always be laid so that it fits: the largest sheet's
    crosses span less than the target area in both directions."""
    sheet = _largest_sheet()
    mm = [sc.sheet_table_mm(sheet, a["page_mm"]) for a in sc.aims_of(sheet, 0)]
    span_x = max(m[0] for m in mm) - min(m[0] for m in mm)
    span_y = max(m[1] for m in mm) - min(m[1] for m in mm)
    a = geo.CAP_AREA
    assert span_x * 10 < a.xmax - a.xmin and span_y * 10 < a.ymax - a.ymin


# ---- a chart without crosses: the corner patches, never a cross --------------------------------

def test_a_chart_without_crosses_never_names_a_cross(qtbot, monkeypatch, tmp_path, settings):
    sheet, pts = H.recorded_sheet("S2 684.0", 17)
    assert all(a["target"] == "patch" for a in sc.aims_of(sheet, 0))
    # corner patches aimed one patch off: refused for the length, in patch words
    bad = [pts[0], (pts[1][0], pts[1][1] - 90), pts[2]]
    sim = WindowSim(aims=bad)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    sheet=sheet, sim=sim)
    assert p.drive_until("aimed") == "aimed"
    text = win._text.text()
    assert "patch R1C1" in text and "printed cross" not in text
    assert "not on the coloured patch" not in text
    assert win._last.detail["target"] == "patch" and win._last.detail["patch"] == "R1C1"
    assert p.drive_until("refused") == "refused"
    text = win._text.text()
    assert "corner patch" in text, text
    for word in ("each cross", "printed cross", "the crosses"):
        assert word not in text, (word, text)
    assert "coloured corner patches beside the crosses" not in text


def test_the_crosses_hint_is_never_given_on_a_chart_without_crosses():
    sheet, pts = H.recorded_sheet("S2 684.0", 17)
    aims = sc.aims_of(sheet, 0)
    mm = [sc.sheet_table_mm(sheet, a["page_mm"]) for a in aims]
    d = J._aims_detail(sheet, 0, aims, mm, [pts[0], (pts[1][0], pts[1][1] - 90), pts[2]],
                       "marks 1 and 2 are 125.4 mm apart on the table but 134.4 mm on the sheet "
                       "(at most 2.5 mm difference")
    assert "aimed_at" not in d
