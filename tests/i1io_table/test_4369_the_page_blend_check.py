"""4.3.69, item 76: THE PAGE BLEND CHECK ON THE TABLE (``workflow/i1io/table/page_blend.py``).

A sheet that lies a few millimetres ACROSS the rows from where its marks were aimed is read partly on
the neighbouring rows: at 3.5 mm a third of the 4.5 mm opening lies there, every row looks like
itself to the identity check, the placement check measures along the row, and the readings were
filed 15 to 24 dE76 off (median). The import's own neighbour-strip check (``measure_chart.
blend_share``, its limit 0.12) now runs on the table after every row over the rows of the page read
on the present aims. When it trips, that row and every other row of the page read on these aims are
dropped, and the person aims again (the row identity check's path, B1). Nothing new is sent.

Measured before it was built on the owner's real pages (kept privately, numbers only): right pages
never above 0.030 after any row; 3.5 mm across found after row 2 to 5, 3.0 mm after row 3 to 9."""
from __future__ import annotations

import json

import numpy as np
import pytest

from tests.i1io_table import bed_sim as B
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_dual_table import dual_setup
from tests.i1io_table.test_job_reading import read_page, ready_to_read
from workflow.i1io import measure_chart as mc
from workflow.i1io.table import identity as idn
from workflow.i1io.table import job as J
from workflow.i1io.table import page_blend as pb

STRIP = ["-v", "-c", "1", "chart"]
SPOT = ["-v", "-c", "1", "-p", "chart"]
COMPACT = {"patch_h": 8.0, "patch_w": 8.0, "spacer_width": 1.0, "i1io_limits": 2}


# ---- the check itself -----------------------------------------------------------------------------

def _grid(rows=6, cols=24, seed=3):
    rng = np.random.default_rng(seed)
    exp = rng.uniform([20, -60, -60], [95, 60, 60], (rows, cols, 3))
    locs = {r: [f"{chr(65 + r)}{c + 1}" for c in range(cols)] for r in range(rows)}
    expected = {locs[r][c]: tuple(exp[r, c]) for r in range(rows) for c in range(cols)}
    return locs, expected, exp


def _measured(locs, exp, share=0.0, side=1, noise=0.5, seed=5):
    rng = np.random.default_rng(seed)
    rows, cols = exp.shape[:2]
    out = {}
    for r in range(rows):
        nb = min(max(r + side, 0), rows - 1)
        for c in range(cols):
            v = (1 - share) * exp[r, c] + share * exp[nb, c] + rng.normal(0, noise, 3)
            out[locs[r][c]] = tuple(0.9 * v + 2.0)        # a printer's own (affine) response
    return out


def test_the_reason_is_the_identity_checks_family():
    assert pb.REASON == idn.REASON_PAGE == "page_not_where_aimed"
    assert idn.REASON_PAGE in idn.REASONS
    assert pb.limit() == mc.BLEND_LIMIT == 0.12


def test_a_right_page_is_judged_and_passes():
    locs, expected, exp = _grid()
    v = pb.judge(locs, _measured(locs, exp), expected)
    assert v["judged"] and not v["beside"] and v["share"] < 0.05


@pytest.mark.parametrize("side", [1, -1])
def test_a_page_read_a_third_on_its_neighbours_is_beside(side):
    locs, expected, exp = _grid()
    v = pb.judge(locs, _measured(locs, exp, share=0.36, side=side), expected)
    assert v["judged"] and v["beside"] and v["share"] > pb.limit(), v
    assert "THE ROWS HOLD THEIR NEIGHBOURS' COLOURS" in pb.summary(v)


def test_what_it_does_not_judge_is_said():
    locs, expected, exp = _grid()
    m = _measured(locs, exp, share=0.36)
    assert pb.judge(locs, m, {})["why"] == "the chart names no expected colours"
    one = {0: locs[0]}
    assert pb.judge(one, m, expected)["why"] == "fewer than two complete neighbouring rows"
    apart = {0: locs[0], 2: locs[2]}                 # not neighbours: no row lies beside another
    assert not pb.judge(apart, m, expected)["judged"]
    partial = {0: locs[0], 1: locs[1][:5]}
    assert not pb.judge(partial, m, expected)["judged"]


def test_the_switch_turns_it_off(monkeypatch):
    locs, expected, exp = _grid()
    monkeypatch.setattr(pb, "PAGE_BLEND_CHECK", False)
    v = pb.judge(locs, _measured(locs, exp, share=0.36), expected)
    assert not v["judged"] and not v["beside"] and v["why"] == "switched off"


def test_it_never_raises():
    v = pb.judge({0: ["A1"], 1: ["B1"]}, {"A1": ("x",), "B1": (1, 2)}, {"A1": (1, 2, 3),
                                                                     "B1": (1, 2, 3)})
    assert not v["judged"] and not v["beside"]


# ---- in the job, on the bed that reads what lies on it --------------------------------------------

def _job(tmp_path, layout, kind, shift, script=None, count=192):
    ch = B.build_chart(tmp_path, count=count, **(COMPACT if layout == "compact" else {}))
    bed = B.Bed(ch.laid(), shift_mm=shift)
    job, sim, helper, run = B.bed_job(tmp_path, ch, bed, ask_after_each_step=False,
                                      aims=B.Bed(ch.laid()).aims(ch.sheet))
    if kind == "dual":
        job.dual = dual_setup("M1")
    assert job.set_options(SPOT if kind == "spot" else STRIP).ok
    p = H.Person(job, sim, {J.Confirm.ROW_FAILED: "skip", J.Confirm.ROW_FAILED_STRIP: "skip",
                            J.Confirm.ROW_IDENTITY: "right", **(script or {})})
    p.events = []
    job.on_progress = p.events.append

    def on_ask(person, res):
        # safety review 81b: a row the page check refused offers End this step only
        if res.confirm in (J.Confirm.ROW_FAILED, J.Confirm.ROW_FAILED_STRIP):
            person.script[res.confirm] = ("stop" if res.detail.get("only_end")
                                          else (script or {}).get(res.confirm, "skip"))
    p.on_ask = on_ask
    ready_to_read(job, p)
    return job, sim, helper, p, ch, bed


def _records(job):
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(job.diag.folder.rglob("*.row.json"))]


def _asked(p, what):
    return [d for _s, c, d, _n, _m in p.asked if c == what]


@pytest.mark.parametrize("layout", ["standard", "compact"])
@pytest.mark.parametrize("kind", ["strip", "spot"])
def test_a_sheet_that_lies_where_it_was_aimed_is_read_as_ever(tmp_path, layout, kind):
    job, sim, helper, p, ch, bed = _job(tmp_path, layout, kind, (0.0, 0.0))
    rows = read_page(job, p)
    assert all(r.ok and r.detail["status"] == "read" for r in rows)
    recs = _records(job)
    assert all(r["page_blend"]["beside"] is False for r in recs)
    judged = [r["page_blend"]["share"] for r in recs if r["page_blend"]["judged"]]
    assert len(judged) == len(recs) - 1 and max(judged) < 0.05      # from the second row on
    assert not [e for e in p.events if e["event"] == "row_dropped"]
    log = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                    for f in job.diag.folder.rglob("*.log"))
    assert log.count("page blend check: share ") == len(recs) - 1
    assert "page blend check: not judged: fewer than two complete neighbouring rows" in log


@pytest.mark.parametrize("layout, kind", [("standard", "strip"), ("standard", "spot"),
                                          ("compact", "spot"), ("standard", "dual")])
@pytest.mark.parametrize("across", [3.5, -3.5])
def test_a_sheet_that_lies_across_from_its_aims_is_refused_and_nothing_of_the_page_kept(
        tmp_path, layout, kind, across):
    job, sim, helper, p, ch, bed = _job(tmp_path, layout, kind, (0.0, across),
                                        count=100 if kind == "dual" else 192)
    out = []
    while job.rows_left():
        r = p.drive(job.read_row())
        out.append(r)
        if _asked(p, J.Confirm.ROW_FAILED_STRIP) or _asked(p, J.Confirm.ROW_FAILED):
            break
    failed = _asked(p, J.Confirm.ROW_FAILED_STRIP) + _asked(p, J.Confirm.ROW_FAILED)
    assert failed, [r.detail for r in out]
    d = failed[0]
    assert d["why"] == idn.REASON_PAGE and d["aim_again"] is True
    assert 2 <= d["row"] <= 9
    # nothing of the page is kept: every row read on these aims is emptied and will be read again
    recs = _records(job)
    assert all(r["accepted"] == [] and not r.get("m0_only") for r in recs), \
        [(r["row"], len(r["accepted"])) for r in recs]
    assert sum(1 for r in recs if r.get("dropped_later") == idn.REASON_PAGE) == d["row"] - 1
    assert "read" not in set(job.row_status.get(0, {}).values())
    dropped = [e for e in p.events if e["event"] == "row_dropped"]
    assert {e["row"] for e in dropped} == set(range(1, d["row"] + 1))
    # 81b: End this step is the one answer; the aims are given up
    assert d["only_end"] is True and job.needs_aims() is True


def test_ending_the_step_aims_again_and_reads_the_page_again(tmp_path):
    """B1's way on: End this step, the arm home, the sheet laid as it now lies, three aims; then the
    rows of the page are read again, the dropped ones first."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 3.5),
                                        script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    while job.rows_left():
        r = p.drive(job.read_row())
        if not r.ok:
            break
    assert not r.ok and r.reason == "stopped_after_a_failed_row", (r.reason, r.detail)
    assert job.needs_aims()
    assert p.drive(job.home()).ok
    sim.aims = bed.aims(ch.sheet)                    # the person aims at the marks where they lie
    r = p.drive(job.align())
    assert r.ok, (r.reason, r.detail)
    rows = read_page(job, p)
    assert all(x.ok and x.detail["status"] == "read" for x in rows)
    assert sorted(job.row_status[0]) == list(range(len(ch.sheet["pages"][0]["strips"])))
    assert set(job.row_status[0].values()) == {"read"}
    recs = [r for r in _records(job) if r["accepted"]]
    assert len(recs) == len(rows) and all(not r["page_blend"]["beside"] for r in recs)


def test_wire_a_right_page_sends_what_it_sent_before(tmp_path, monkeypatch):
    """No line is sent for the check: the same page, checked and not, sends the same lines."""
    lines = {}
    for on in (True, False):
        monkeypatch.setattr(pb, "PAGE_BLEND_CHECK", on)
        job, sim, helper, p, ch, bed = _job(tmp_path / str(on), "standard", "strip", (0.0, 0.0))
        n = len(sim.received)
        assert all(r.ok for r in read_page(job, p))
        lines[on] = sim.received[n:]
    assert lines[True] == lines[False]


def test_the_failed_row_page_says_why_in_the_new_words():
    from ui import i1io_table_window as W
    from workflow import measurement_messages as M
    assert W.reason_text(idn.REASON_PAGE) == M.M_I1IO_DRIVE_PAGE_BESIDE.render()[1]
    assert "across the rows, from where you aimed at its marks" in W.reason_text(idn.REASON_PAGE)


def test_new_aims_start_the_page_check_afresh(tmp_path):
    """Rows read on earlier aims never count with rows read on new ones (another alignment of the
    same sheet may lie a millimetre elsewhere)."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 0.0))
    assert p.drive(job.read_row()).ok and p.drive(job.read_row()).ok
    assert len(job._aim_readings) == 2
    assert p.drive(job.home()).ok
    assert job._aim_readings == {}
    assert p.drive(job.align()).ok
    assert job._aim_readings == {}
    assert p.drive(job.read_row()).ok
    assert list(job._aim_readings) == [(0, 2)]


# ---- safety review 81 ---------------------------------------------------------------------------

def _read_whole_page(job, p):
    """Every row of the page, whatever the answers (the person's script), until none is left or
    the step ends."""
    out = []
    for _ in range(80):
        if not job.rows_left():
            break
        r = p.drive(job.read_row())
        out.append(r)
        if not r.ok:
            break
    return out


@pytest.mark.parametrize("layout, kind", [("standard", "strip"), ("compact", "spot"),
                                          ("standard", "spot"), ("standard", "dual")])
@pytest.mark.parametrize("answer", ["skip", "again", "patch by patch"])
def test_81b_after_a_trip_end_this_step_is_the_one_answer(tmp_path, layout, kind, answer):
    """S1 / 81b: Read it again, patch by patch and Skip it are refused (nothing sent); End this
    step ends it, the aims are given up. 0 patches kept on the page."""
    job, sim, helper, p, ch, bed = _job(tmp_path, layout, kind, (0.0, 3.5),
                                        count=100 if kind == "dual" else 192)
    tries = []

    def on_ask(person, res):
        if res.confirm in (J.Confirm.ROW_FAILED, J.Confirm.ROW_FAILED_STRIP) \
                and res.detail.get("only_end"):
            n = len(sim.received)
            r = job.answer(res.confirm, answer)
            tries.append((r.kind, r.reason, len(sim.received) - n))
            person.script[res.confirm] = "stop"
    p.on_ask = on_ask
    _read_whole_page(job, p)
    failed = _asked(p, J.Confirm.ROW_FAILED_STRIP) + _asked(p, J.Confirm.ROW_FAILED)
    assert failed and failed[0]["why"] == idn.REASON_PAGE and failed[0]["only_end"]
    assert tries == [(J.Kind.REFUSED, "not_one_of_the_choices", 0)]
    assert [a for r in _records(job) for a in r["accepted"]] == []
    assert job.needs_aims()


def test_81b_a_row_read_on_refused_aims_is_dropped_unjudged(tmp_path):
    """The flag: once the page check refused the aims, a row read on them is dropped without
    being judged (a row just under the limit, or one cut short, is never kept), until the
    homing."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 3.5))
    _read_whole_page(job, p)
    assert job._aims_refused == {0}
    # the person moves nothing; a row read on the same aims (as a later "again" would)
    bed.shift_mm = (0.0, 0.0)                         # (even a row that would pass on its own)
    job.aims_void = False
    r = p.drive(job.read_row())
    rec = _records(job)[-1]
    assert rec["accepted"] == [] and rec["page_blend"]["beside"] is True
    assert "refused these aims before" in rec["page_blend"]["why"]
    assert p.drive(job.home()).ok and job._aims_refused == set()


def test_81b_a_row_cut_short_on_refused_aims_keeps_nothing(tmp_path, monkeypatch):
    """A row read patch by patch that ends early on refused aims (here a reading that fails
    after three patches) keeps none of its patches."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "spot", (0.0, 3.5))
    _read_whole_page(job, p)
    assert job._aims_refused == {0}
    job.aims_void = False
    real = job._patch
    n = {"k": 0}

    def patch(*a, **k):
        n["k"] += 1
        if n["k"] > 3:
            raise J._RowFailed("strip_patch_implausible", "")
        return real(*a, **k)
    monkeypatch.setattr(job, "_patch", patch)
    p.drive(job.read_row())
    rec = _records(job)[-1]
    assert rec["accepted"] == [], len(rec["accepted"])


def test_81b_a_confirmed_page_is_judged_like_any_other(tmp_path):
    """Safety review 81b: the person's "right" at the identity question does not switch the page
    check off (the exemption 81's builder added is gone)."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 3.5))
    job.identity_confirmed.add(0)
    _read_whole_page(job, p)
    failed = _asked(p, J.Confirm.ROW_FAILED_STRIP)
    assert failed and failed[0]["why"] == idn.REASON_PAGE
    assert [a for r in _records(job) for a in r["accepted"]] == []


def test_s1_the_aims_change_only_at_the_homing(tmp_path):
    """The refused readings stay in the check until the aims are given up (the homing)."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 3.5))
    _read_whole_page(job, p)
    assert job._aim_readings
    assert p.drive(job.home()).ok and job._aim_readings == {}


def test_s2_the_spot_page_does_not_say_the_rows_before_are_kept():
    from ui import i1io_table_window as W
    from workflow import measurement_messages as M
    besides = M.M_I1IO_DRIVE_ROW_FAILED_BESIDE.render(row=3, page=1, why="x")[1]
    assert "the rows read before it are kept" not in besides
    assert "the rows read before it are kept" in M.M_I1IO_DRIVE_ROW_FAILED.render(
        row=3, page=1, why="x")[1]
    assert M.of_pieces(M.M_I1IO_DRIVE_ROW_FAILED_BESIDE, True).id.endswith("-PIECE")
    import inspect
    src = inspect.getsource(W)
    assert 'M.M_I1IO_DRIVE_ROW_FAILED_BESIDE if d.get("why") == "page_not_where_aimed"' in src
    assert "read it again" not in besides.lower() and "skip it" not in besides.lower()


def test_s2_the_window_shows_the_variant(qtbot, monkeypatch, tmp_path):
    """The real failed-row page of a row read patch by patch that the check refused."""
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from tests.i1io_table.test_window import open_window
    from ui import i1io_table_window as W
    from types import SimpleNamespace as NS
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "w.ini"), QSettings.Format.IniFormat)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, st)
    for confirm in ("row_failed", "row_failed_strip"):
        res = NS(kind="needs_confirmation", confirm=confirm, step="read_row", choices=(),
                 detail={"row": 3, "page": 1, "why": idn.REASON_PAGE, "aim_again": True,
                         "again_allowed": True, "only_end": True})
        win._ask(res)
        text = win._text.text()
        assert "across the rows, from where you aimed at its marks" in text
        # the page says how to aim again (M-I1IO-DRIVE-ROW-AIM-AGAIN), first
        from workflow import measurement_messages as M
        assert text.startswith(M.M_I1IO_DRIVE_ROW_AIM_AGAIN.render()[1])
        assert "the rows read before it are kept" not in text
        assert "as often as you like" not in text and "Read it patch by patch" not in text
        # 81b: End this step is the one answer offered
        assert [b.text() for b in win._buttons] == [W.tr("End this step")], confirm


def test_s3_the_reason_says_what_holds_after_every_answer():
    from workflow import measurement_messages as M
    body = M.M_I1IO_DRIVE_PAGE_BESIDE.body
    assert "no row is kept until you have aimed at the marks again" in body
    assert "read again once" not in body


def test_p2_a_measurement_put_together_before_the_trip_loses_the_dropped_rows(tmp_path):
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 3.5))
    _read_whole_page(job, p)
    out = job.run.i1io_table_measurement(job.stamp)
    if out.exists():
        text = out.read_text(encoding="utf-8", errors="replace")
        dropped = {e["row"] for e in p.events if e["event"] == "row_dropped"}
        locs = [q["loc"] for st in ch.sheet["pages"][0]["strips"][:max(dropped)]
                for q in st["patches"]]
        assert not any(f'"{q}"' in text or f" {q} " in text for q in locs)


def test_p2_the_measurement_file_is_removed_by_the_trip(tmp_path, monkeypatch):
    """The measurement of the sitting, written at a row end before the trip, is removed with the
    rows it held."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 3.5))
    out = job.run.i1io_table_measurement(job.stamp)
    real = job._drop_page_rows_on_these_aims

    def spy(plan, reason):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("written before the trip", encoding="utf-8")
        return real(plan, reason)
    monkeypatch.setattr(job, "_drop_page_rows_on_these_aims", spy)
    _read_whole_page(job, p)
    assert not out.exists()


def test_p10_a_check_that_fails_never_trips(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise ValueError("planted")
    monkeypatch.setattr(mc, "blend_share", boom)
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 3.5))
    rows = read_page(job, p)
    assert all(r.ok and r.detail["status"] == "read" for r in rows)
    recs = _records(job)
    assert all(r["page_blend"]["beside"] is False for r in recs)
    assert any("could not be judged" in (r["page_blend"]["why"] or "") for r in recs)


def test_p12_a_lamp_pass_kept_on_its_own_goes_when_its_page_trips(tmp_path):
    """Row 1's UV pass would not start: its lamp pass is kept as M0 (one row: the page check
    cannot judge yet). Row 2 trips the page: row 1's M0 goes with it."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "dual", (0.0, 3.5), count=100)
    helper.faults["scan"] = {"uv_not_ready": True}
    p.drive(job.read_row())
    rec1 = _records(job)[0]
    assert rec1["m0_only"] and rec1["accepted"]
    helper.faults.pop("scan")
    _read_whole_page(job, p)
    first = [r for r in _records(job) if r["row"] == 1]
    assert first and all(r["accepted"] == [] and not r.get("m0_only") for r in first)
    assert any(r.get("dropped_later") == idn.REASON_PAGE for r in first)


# ---- safety review 81c ----------------------------------------------------------------------------

def _turned(laid):
    """An unusual print: the same sheet with its colour channels turned (the identity check asks
    at the first row; the person says it is the right sheet)."""
    out = B.Laid(laid.pixels[..., [1, 2, 0]].copy(), laid.w, laid.h)
    return out


@pytest.mark.parametrize("layout, kind", [("standard", "strip"), ("standard", "spot"),
                                          ("compact", "spot")])
@pytest.mark.parametrize("across", [3.0, 3.5])
def test_81c_f1_a_row_confirmed_at_the_identity_question_goes_with_a_trip(tmp_path, layout,
                                                                           kind, across):
    ch = B.build_chart(tmp_path, count=192, **(COMPACT if layout == "compact" else {}))
    bed = B.Bed(_turned(ch.laid()), shift_mm=(0.0, across))
    job, sim, helper, run = B.bed_job(tmp_path, ch, bed, ask_after_each_step=False,
                                      aims=B.Bed(ch.laid()).aims(ch.sheet))
    assert job.set_options(SPOT if kind == "spot" else STRIP).ok
    p = H.Person(job, sim, {J.Confirm.ROW_FAILED: "stop", J.Confirm.ROW_FAILED_STRIP: "stop",
                            J.Confirm.ROW_IDENTITY: "right"})
    p.events = []
    job.on_progress = p.events.append
    ready_to_read(job, p)
    _read_whole_page(job, p)
    assert _asked(p, J.Confirm.ROW_IDENTITY), "the unusual print is asked about"
    assert [a for r in _records(job) for a in r["accepted"]] == []


def _fail_row(monkeypatch, at_row):
    """The row placement check refuses row *at_row* (1-based) of the page, as a real refusal."""
    from workflow.i1io.table import strip as stp
    real = stp.cut_row
    n = {"k": 0}

    def cut(*a, **k):
        n["k"] += 1
        if n["k"] == at_row:
            return stp.Cut(False, stp.PLACEMENT_REASON)
        return real(*a, **k)
    monkeypatch.setattr(stp, "cut_row", cut)


def test_81c_f2_end_after_a_failure_empties_the_rows_no_check_vouched_for(tmp_path, monkeypatch):
    """Row 1 read alone (too few rows for the check), row 2 refused by the placement check, End
    this step: row 1 goes too, and is read again after the new aims."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 0.0),
                                        script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    _fail_row(monkeypatch, 2)
    _read_whole_page(job, p)
    recs = _records(job)
    assert [a for r in recs for a in r["accepted"]] == []
    assert any(r.get("dropped_later") == J.UNVOUCHED for r in recs)
    assert 0 not in job.row_status.get(0, {})


def test_81c_f2_rows_a_passing_check_judged_stay(tmp_path, monkeypatch):
    """Rows 1 to 3 read and judged by the check (passing), row 4 refused by the placement check,
    End this step: rows 1 to 3 stay as read."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 0.0),
                                        script={J.Confirm.ROW_FAILED_STRIP: "stop"})
    _fail_row(monkeypatch, 4)
    _read_whole_page(job, p)
    kept = {r["row"] for r in _records(job) if r["accepted"]}
    assert kept == {1, 2, 3}
    assert {job.row_status[0][k] for k in (0, 1, 2)} == {"read"}


def test_81c_p12_a_lamp_pass_on_refused_aims_is_not_kept(tmp_path):
    """The keep-the-lamp-pass path honours the refused aims ("beside") as the row itself does."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "dual", (0.0, 0.0), count=100)
    assert p.drive(job.read_row()).ok
    job._aims_refused.add(0)                          # the check refused these aims
    helper.faults["scan"] = {"uv_not_ready": True}
    p.drive(job.read_row())
    rec = [r for r in _records(job) if r["row"] == 2][-1]
    assert rec["accepted"] == [] and not rec.get("m0_only")


def test_81c_p4b_new_aims_forget_the_old_readings_without_a_homing_in_between(tmp_path):
    """The aims' own reset (not only the homing's): readings, the refused flag and the vouched
    rows of earlier aims are gone the moment new aims are taken."""
    job, sim, helper, p, ch, bed = _job(tmp_path, "standard", "strip", (0.0, 0.0))
    assert p.drive(job.read_row()).ok and p.drive(job.read_row()).ok
    assert p.drive(job.home()).ok
    job._aim_readings[(0, 7)] = {"X1": (50.0, 0.0, 0.0)}
    job._aims_refused.add(0)
    job._aim_vouched.add((0, 7))
    assert p.drive(job.align()).ok
    assert job._aim_readings == {} and 0 not in job._aims_refused and job._aim_vouched == set()
