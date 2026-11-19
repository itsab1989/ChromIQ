"""4.3.49 acceptance: the owner's EXACT three aims of 19 Nov 2026 (session 124127, rounds 1 and 2,
at the crosses of ChromIQ's A4 chart) replayed through the job on the simulated table, and wider
sheets up to the largest the i1iO chart builder makes (230 x 320 mm), and the chart kinds.

Basti's ruling of 19 Nov 2026 (binding): the person who aims at a sheet's points knows that the
arm can reach them, so the targets are bounded by the AIMED area, no longer by the frontmost
recorded aim. Supported by the recordings: i1Profiler drives the opening to the very points the
person aimed the sight at (17 Nov 2026, three sessions, all three marks, within 1-5 units).

The simulated table behaves like his (only the parts the data shows; the rest is said):
* a right stop for the opening at X -1434 (two hand pushes stopped there), and the sight
  7.1 mm left of the opening there, so that his p1 at mark 3 (-1362) comes with the opening at
  that stop, as on 19 Nov;
* a physical FRONT END (FRONT_END_Y, INVENTED: no recording shows the real one); beyond it the
  simulated arm stalls, which is what the creep's arrival check then finds.

What these tests pin:
* Q1: his exact aims, sheet where he laid it: the run passes the three points, feels its way
  to the front (4.3.48's front-zone question and creep, the only questions), moves to mark 3 and
  reads the first row; nothing is refused and no sheet is moved;
* a second run on the same table does not ask the front-zone question again (the motors have
  been there); another table (other serial) does;
* Q2: the largest sheet laid as far forward as its crosses allow: read; laid where his lay, the
  right side refuses it with how far (the X side is kept: evidence of the right stop);
* a front end in front of the aimed area: the creep stops at the first step that does not
  arrive, cleanly, and the page says how far short the arm stopped.
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
from workflow.i1io.table import reach as rc
from workflow.i1io.table import scan as sc

CROSSES_1 = [(1394, 1369), (1402, 3253), (-1362, 3253)]        # his round 1, exact
CROSSES_2 = [(1394, 1379), (1399, 3240), (-1362, 3252)]        # his round 2, exact
GO_ON = {J.Confirm.FRONT_CHOICE: "go on"}
#: his table as far as the data shows it (see the module's docstring)
HIS_TABLE = {"right_end": -1434, "sight_offset": (-71, -318)}
#: the questions 4.3.48 already asked on such a run (no new step may appear among them)
KNOWN_QUESTIONS = {J.Confirm.READY_TO_OPEN, J.Confirm.READER_CONSENT, J.Confirm.CAL_PLACE,
                   J.Confirm.GO, J.Confirm.SHEET_LAID, J.Confirm.ARM_FELT, J.Confirm.AIMED,
                   J.Confirm.FRONT_CHOICE, J.Confirm.FIRST_VISIT}


def _shift(aims, dx, dy):
    return [(x + dx, y + dy) for x, y in aims]


def _through_first_row(tmp_path, sheet, aims, store=None, **simkw):
    kw = dict(HIS_TABLE)
    kw.update(simkw)
    job, sim, helper, run = RS.make_reading_job(
        tmp_path, sheet=sheet, aims=aims, ask_after_each_step=False,
        reach_store=store if store is not None else rc.MemoryReachStore(), **kw)
    p = H.Person(job, sim, GO_ON)
    out = []
    for step in ("open", "calibrate", "align"):
        r = p.drive(getattr(job, step)())
        out.append((step, r.kind, r.reason, r.detail))
        if not r.ok:
            return out, job, sim, p
    if job.front_need and job.front_reached() < job.front_need:
        r = p.drive(job.creep())
        out.append(("creep", r.kind, r.reason, r.detail))
        if not r.ok:
            return out, job, sim, p
    # 4.3.50: no check move to mark 3; the first row follows
    r = p.drive(job.read_row())
    out.append(("read_row", r.kind, r.reason, r.detail))
    return out, job, sim, p


def _steps(out):
    return [(s, k, r) for s, k, r, _d in out]


def _asked(p):
    return {c for _s, c, _d, _n, _m in p.asked}


# ---- Q1: the exact same thing on the same sheet -------------------------------------------------

@pytest.mark.parametrize("aims", [CROSSES_1, CROSSES_2], ids=["round 1", "round 2"])
def test_q1_his_exact_aims_go_on_to_the_first_row_with_no_extra_step(tmp_path, aims):
    out, job, sim, p = _through_first_row(tmp_path / "a", H.demo_sheet(), aims)
    assert [s for s, k, _r in _steps(out) if k != J.Kind.OK] == [], _steps(out)
    assert [s for s, _k, _r in _steps(out)] == ["open", "calibrate", "align", "creep",
                                               "read_row"]
    assert _asked(p) <= KNOWN_QUESTIONS, _asked(p) - KNOWN_QUESTIONS
    assert sim.violations == [] and sim.end_targets == []
    # after mark 3 the opening stood at the right stop (0.1 mm from it, as on 19 Nov) and the
    # first move started from there
    assert any(abs(x + 1433) <= 1 for x, _y in sim.hand_moves)
    front_mark = max(a[1] for a in aims)
    # 4.3.50: the front need is the plan's frontmost target, short of the marks
    assert job.alignment.aimed_front_y() >= front_mark > job.front_need > geo.FRONTMOST_AIM_Y


def test_a_second_run_on_the_same_table_does_not_feel_its_way_forward_again(tmp_path):
    store = rc.MemoryReachStore()
    out, job, sim, p = _through_first_row(tmp_path / "1", H.demo_sheet(), CROSSES_1, store)
    assert _steps(out)[-1][1] == J.Kind.OK
    assert J.Confirm.FRONT_CHOICE in _asked(p)
    been = job.reach.motor_front_y
    assert been is not None and been >= job.front_need
    job.close()
    out2, job2, sim2, p2 = _through_first_row(tmp_path / "2", H.demo_sheet(), CROSSES_1, store,
                                              motors_have_been_to=been)
    assert [s for s, _k, _r in _steps(out2)] == ["open", "calibrate", "align",
                                                "read_row"], _steps(out2)
    assert all(k == J.Kind.OK for _s, k, _r in _steps(out2))
    assert J.Confirm.FRONT_CHOICE not in _asked(p2)
    assert sim2.violations == []
    # another table (another serial) feels its way forward again
    out3, job3, sim3, p3 = _through_first_row(tmp_path / "3", H.demo_sheet(), CROSSES_1, store,
                                              serial="SIM0000OTHR")
    assert J.Confirm.FRONT_CHOICE in _asked(p3)
    assert job3.reach.key != job.reach.key
    assert _steps(out3)[-1][1] == J.Kind.OK


def test_the_remembered_reach_holds_no_serial_and_validates_what_it_loads():
    store = rc.MemoryReachStore()
    salt = store.salt()
    from tests.i1io_table import session_sim as ss
    ident = rc.ident_of_memory_block(ss._memory_a())
    key = rc.table_key(ident, salt)
    r = store.get(key)
    r.learn((-1400, 2900), "free")
    r.learn_motor_target((0, 3000))
    assert store.put(r)
    text = store.text
    assert ss.FAKE_SERIAL not in text and ss.FAKE_SERIAL.encode().hex() not in text.lower()
    assert ident not in text and salt in text and key in text
    back = store.get(key)
    assert (back.front_y, back.front_how, back.motor_front_y) == (2900, "free", 3000)
    # a stored value outside what is physically possible is ignored, never trusted
    bad = rc.Reach.from_dict(key, {"front_y": 9999, "front_how": "free", "motor_front_y": 99999,
                                   "right_end_x": -5000, "right_how": "free"})
    assert (bad.front_y, bad.motor_front_y, bad.right_end_x) == (rc.DEFAULT_FRONT_Y, None,
                                                                rc.DEFAULT_RIGHT_END_X)
    assert rc.Reach.from_dict(key, {"front_y": 3000, "front_how": "guessed"}).front_y == \
        rc.DEFAULT_FRONT_Y


# ---- Q2: wider marks, up to the largest sheet --------------------------------------------------

def _largest_sheet():
    """230 x 320 mm (the largest sheet the chart builder lays across the table), crosses 8 / 12
    mm in, 28 strips of 30 patches."""
    return shaped_sheet([30] * 28)


def _aims(sheet, origin):
    return H.demo_aims(sheet, origin=origin)


def test_q2_the_largest_sheet_laid_where_his_lay_is_refused_by_the_right_side_with_how_far(
        tmp_path):
    sheet = _largest_sheet()
    aims = _aims(sheet, (1504, 1259))                 # his sheet's corner, as on 19 Nov
    res, job, sim, _p = H.run_steps(["open", "align"], sheet=sheet, aims=aims,
                                    reach_store=rc.MemoryReachStore())
    r = res[1]
    assert r.reason == "aims_outside_area"
    mv = r.detail["sheet_move"]
    assert mv["left_mm"] > 0 and mv["back_mm"] == 0       # the front no longer refuses


@pytest.mark.parametrize("front", [3253, 3330], ids=["front marks where his lay",
                                                   "front marks 7.7 mm further"])
def test_q2_the_largest_sheet_as_far_forward_as_its_side_allows_reads_its_first_row(tmp_path,
                                                                                    front):
    """The largest sheet, moved across only as far as the right side asks, its front marks where
    his lay and further to the front (the simulated front end at Y 3400 is invented)."""
    sheet = _largest_sheet()
    first = H.run_steps(["open", "align"], sheet=sheet, aims=_aims(sheet, (1504, 1259)),
                        reach_store=rc.MemoryReachStore())[0][1]
    mv = first.detail["sheet_move"]
    span = max(a[1] for a in _aims(sheet, (0, 0)))
    origin = (1504 + 10 * mv["left_mm"], front - span)
    aims = _aims(sheet, origin)
    out, job, sim, p = _through_first_row(tmp_path, sheet, aims, right_end=None,
                                          sight_offset=(-106, -323))
    assert [s for s, k, _r in _steps(out) if k != J.Kind.OK] == [], _steps(out)
    assert max(a[1] for a in aims) > geo.FRONTMOST_AIM_Y      # beyond the old cap
    assert _asked(p) <= KNOWN_QUESTIONS and sim.violations == [] and sim.end_targets == []


def test_q2_a_sheet_aimed_beyond_where_the_arm_ends_stops_at_the_end_and_says_by_how_much(
        tmp_path):
    """The residual risk, on the simulated table: the sight can be aimed 31 mm further to the
    front than the opening can go. The creep (5 mm steps, each arrival checked) is the first
    motor visit there; its first step that does not arrive ends the measurement cleanly."""
    aims = _shift(CROSSES_1, 0, 0)
    # 4.3.50: the careful steps go to the frontmost patch row (3158), not to the marks (3253)
    out, job, sim, p = _through_first_row(tmp_path, H.demo_sheet(), aims, front_end=3140)
    step, kind, reason, detail = out[-1]
    assert (step, kind, reason) == ("creep", J.Kind.REFUSED, "creep_step_did_not_arrive"), out
    assert detail["short_mm"] >= (3158 - 3140) // 10
    assert job.only_home and sim.violations == []
    assert any("front end" in e[0] for e in sim.at_end_events)
    assert job.reach_diag["refusals"][-1]["kind"] == "creep_stopped"


def test_q2_no_sheet_the_builder_makes_is_wider_than_the_target_area():
    """The reason a refused sheet can always be laid so that it fits: the largest sheet's
    crosses span less than the target area across, and the front follows the aims."""
    sheet = _largest_sheet()
    mm = [sc.sheet_table_mm(sheet, a["page_mm"]) for a in sc.aims_of(sheet, 0)]
    span_x = max(m[0] for m in mm) - min(m[0] for m in mm)
    a = geo.CAP_AREA
    assert span_x * 10 < a.xmax - a.xmin


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


def test_the_page_after_a_creep_that_met_the_end_says_how_far_to_lay_the_sheet_back():
    from ui.i1io_table_window import reason_text
    text = reason_text("creep_step_did_not_arrive", {"short_mm": 8})
    assert "about 8 mm short" in text and "about 8 mm further towards the back" in text
    assert "—" not in text
    # without the amount (an older detail), the general sentence stays
    assert reason_text("creep_step_did_not_arrive", {}) == tr(
        "The slow steps towards the front stopped at a step that did not arrive exactly.")
