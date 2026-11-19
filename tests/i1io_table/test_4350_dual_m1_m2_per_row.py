"""4.3.50: M1 and M2 of the X-Rite i1Pro 2 dual scan ON THE i1iO TABLE are kept PER ROW, by the
same rules as by hand (Basti, 19 Nov 2026; by hand since 4.3.49).

Until 4.3.49 the table filed M1 / M2 only when every patch had them, else none at all
(job.py ``_dual_measurement``: "Refused ... when any patch lacks them"), and a row whose UV pass
failed lost its M0 too. Now:

* a dual row whose second pass (UV) failed or was refused after a complete lamp pass keeps its
  lamp pass as M0 only; every other row keeps its M1 / M2;
* the measurement's pair is then the hand path's PARTIAL pair (``<hash>-M1.partial.ti3`` /
  ``-M2.partial.ti3``: only the patches with all three, the main file's order), which Build
  Profile never offers (it starts at M0 and says why), and the pass record names the row "lamp
  only, second pass due";
* reading the row again in the same sitting, or Continue Measurement later (which, with the dual
  scan on, also reads the M0-only rows again), completes it: the complete pair, Build Profile at
  the condition chosen;
* every patch's M1 / M2 come from the SAME reading as its M0 (never another attempt's).

The same files and the same Build Profile behaviour as by hand: no second mechanism. Nothing new
is sent to the table or the instrument (the rows' lines are the released ones).
"""
from __future__ import annotations

from pathlib import Path

from tests.i1io_table import job_harness as H
from tests.i1io_table import reader_sim as RS
from tests.i1io_table.test_dual_table import STRIP, SPOT, _ready, dual_setup, long_sheet
from tests.i1io_table.test_window import settings  # noqa: F401 (fixture)
from workflow import i1pro3_conditions as ic
from workflow.dual_scan import storage as S
from workflow.i1io.table import job as J
from workflow.i1io.table import lines as cl
from workflow.i1io.table import measurement as ms

LATER = "20261119-150000"


def _job(tmp_path, args=STRIP, faults=None, script=None, stamp=None, chosen="M2"):
    sheet = long_sheet()
    kw = {"stamp": stamp} if stamp else {}
    job, sim, helper, run = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                                ask_after_each_step=False, faults=faults, **kw)
    job.dual = dual_setup(chosen)
    rep = job.set_options(args)
    assert rep.ok, (rep.reason, rep.detail)
    return job, sim, helper, run, H.Person(job, sim, script), rep


def _row_locs(job, row):
    return [q["loc"] for q in job.sheet["pages"][0]["strips"][row - 1]["patches"]]


def _read_all(job, p):
    out = []
    while job.rows_left():
        r = p.drive(job.read_row())
        out.append(r)
        if not r.ok:
            break
    return out


#: the first row's dual reader is scan reader 2 (the strip calibration is 1)
UV_FAILS_ON_ROW_1 = {"scan": {"uv_not_ready": True}, "scan_at": 2}


def _row1_m0_only(tmp_path, **kw):
    job, sim, helper, run, p, _rep = _job(
        tmp_path, faults=UV_FAILS_ON_ROW_1,
        script={J.Confirm.ROW_FAILED_STRIP: "skip"}, **kw)
    _ready(job, p)
    rows = _read_all(job, p)
    assert all(r.ok for r in rows), [(r.reason, r.detail) for r in rows]
    return job, sim, helper, run, p


def test_a_row_whose_uv_pass_failed_keeps_m0_and_the_others_keep_m1_m2(tmp_path):
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    # the question said that the row keeps M0 (its own page), and was answered "skip"
    asked = [d for _s, c, d, _n, _m in p.asked if c == J.Confirm.ROW_FAILED_STRIP]
    assert len(asked) == 1 and asked[0]["m0_kept"] and asked[0]["why"] == "uv_pass_failed_clean"
    m = job.measurement()
    assert m.ok and m.detail["measurement"]["state"] == "complete", m.detail
    dual = m.detail["dual"]
    assert dual["pair"] == "partial" and sorted(dual["m0_only"]) == sorted(_row_locs(job, 1))
    s = job.save()
    assert s.ok, (s.reason, s.detail)
    main = Path(run.measurement_ti3)
    # M0: every patch of both rows
    assert sorted(ic._locs_of(main)) == sorted(_row_locs(job, 1) + _row_locs(job, 2))
    # the hand path's own reading of it: row 1 is M0 only, nothing else
    assert sorted(ic.m0_only_locs(main)) == sorted(_row_locs(job, 1))
    assert not ic.no_pair_kept(main)
    for cond in ("M1", "M2"):
        # no complete pair: Build Profile does not offer M1 / M2
        assert ic.condition_file(main, cond) is None
        part = ic.partial_sibling_path(main, cond)
        assert part.is_file() and ic.sibling_in_step(main, part)
        assert ic._locs_of(part) == [loc for loc in ic._locs_of(main)
                                     if loc in _row_locs(job, 2)]       # the main file's order
    choices = {c.cond: c for c in ic.choices_for(main)}
    assert choices["M0"].usable and not choices["M1"].usable and not choices["M2"].usable
    assert "strip" in choices["M1"].reason.lower() or "M0" in choices["M1"].reason
    assert S.build_from_preset(main)[0] == "M0"
    rec = S.pass_record_of(main)
    assert rec is not None and not rec.complete()
    assert ("p1_row1", "uv") in rec.missing() and ("p1_row2", "uv") not in rec.missing()
    # nothing outside the released allow-list was sent
    for ln in sim.received:
        try:
            cl.classify((ln + "\r").encode())
        except Exception:      # noqa: BLE001 - the dual rows' own lines, in their pass
            assert ln.startswith((";m2", ";d1")), ln
    assert sim.violations == []


def test_m1_m2_come_from_the_same_reading_as_m0(tmp_path):
    """Row 1 read twice: the first attempt's lamp pass only (UV failed), the second with both.
    The file takes M0 AND M1 / M2 from the second attempt; a row whose LATEST reading is M0 only
    has no M1 / M2, even when an earlier attempt had them."""
    job, sim, helper, run, p, _rep = _job(tmp_path, faults=UV_FAILS_ON_ROW_1,
                                          script={J.Confirm.ROW_FAILED_STRIP: "again"})
    _ready(job, p)
    rows = _read_all(job, p)
    assert all(r.ok for r in rows)
    m = job.measurement()
    assert m.detail["dual"]["pair"] == "complete" and m.detail["dual"]["m0_only"] == []
    assert job.save().ok
    main = Path(run.measurement_ti3)
    assert ic.m0_only_locs(main) == []
    for cond in ("M1", "M2"):
        assert ic.condition_file(main, cond) is not None
    assert S.build_from_preset(main) == ("M2", "")
    # the sources: every patch of row 1 from the second attempt's record
    src = ms.m0_sources(job._session_dirs(), None)
    assert {src[loc][2]["attempt"] for loc in _row_locs(job, 1)} == {2}


def test_continue_measurement_reads_the_m0_only_row_again_and_completes_the_pair(tmp_path):
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    assert job.save().ok
    main = Path(run.measurement_ti3)
    assert ic.m0_only_locs(main)
    # a later sitting: Continue Measurement (-r) with the dual scan on
    job2, sim2, helper2, run2, p2, rep = _job(tmp_path, args=STRIP + ["-r"], stamp=LATER)
    assert rep.detail.get("fill_m0_only") == len(_row_locs(job, 1)), rep.detail
    assert set(job2.only_locs) == set(_row_locs(job, 1))
    _ready(job2, p2)
    rows = _read_all(job2, p2)
    assert [r.detail.get("row") for r in rows if r.detail.get("status") == "read"] == [1]
    s = job2.save()
    assert s.ok, (s.reason, s.detail)
    assert s.detail["dual"]["conditions"], s.detail["dual"]
    assert ic.m0_only_locs(main) == []
    for cond in ("M1", "M2"):
        f = ic.condition_file(main, cond)
        assert f is not None and sorted(ic._locs_of(f)) == sorted(ic._locs_of(main))
    assert S.build_from_preset(main) == ("M2", "")
    assert S.pass_record_of(main).complete()


def test_without_the_dual_scan_continue_never_reads_m0_only_rows(tmp_path):
    job, sim, helper, run, p = _row1_m0_only(tmp_path)
    assert job.save().ok
    sheet = long_sheet()
    job2, *_ = RS.make_reading_job(tmp_path, sheet=sheet, aims=H.demo_aims(sheet),
                                   ask_after_each_step=False, stamp=LATER)
    assert job2._m0_only_to_fill(Path(run.measurement_ti3)) == set()


def test_a_patch_by_patch_row_without_m1_m2_keeps_m0_only(tmp_path):
    """Patch by patch: the reader of row 1 wrote its row file but no M1 / M2 (its conditions
    ended): the row keeps its M0 readings (its own page says so), row 2 keeps M1 / M2."""
    job, sim, helper, run, p, _rep = _job(
        tmp_path, args=SPOT, faults={"no_conditions_at": (2,)},
        script={J.Confirm.ROW_FAILED: "skip"})
    _ready(job, p)
    rows = _read_all(job, p)
    assert all(r.ok for r in rows), [(r.reason, r.detail) for r in rows]
    asked = [d for _s, c, d, _n, _m in p.asked if c == J.Confirm.ROW_FAILED]
    assert len(asked) == 1 and asked[0]["m0_kept"] and asked[0]["why"] == "dual_conditions_missing"
    assert job.save().ok
    main = Path(run.measurement_ti3)
    assert sorted(ic.m0_only_locs(main)) == sorted(_row_locs(job, 1))
    assert ic.condition_file(main, "M1") is None
    assert ic.sibling_in_step(main, ic.partial_sibling_path(main, "M1"))


def test_no_row_with_m1_m2_leaves_no_pair_and_every_row_m0_only(tmp_path):
    """Both rows' UV passes fail and are skipped: no pair at all (as a hand dual scan whose M1 /
    M2 never started), every read patch M0 only, and Continue reads them all again."""
    job, sim, helper, run, p, _rep = _job(
        tmp_path, faults={"scan": {"uv_not_ready": True}},
        script={J.Confirm.ROW_FAILED_STRIP: "skip"})
    _ready(job, p)
    rows = _read_all(job, p)
    assert all(r.ok for r in rows)
    assert job.save().ok
    main = Path(run.measurement_ti3)
    assert not list(Path(run.condition_dir).glob("*-M1*.ti3")) if Path(
        run.condition_dir).is_dir() else True
    assert sorted(ic.m0_only_locs(main)) == sorted(ic._locs_of(main))
    assert ic.no_pair_kept(main)
    assert S.build_from_preset(main)[0] == "M0"


def test_the_m0_only_page_says_what_is_kept_and_what_skip_means():
    from workflow import measurement_messages as M
    _t, body = M.M_I1IO_DRIVE_ROW_M0_ONLY_STRIP.render(row=3, page=1, why="it did not match")
    assert "was read and is kept" in body and "no M1 and M2 yet" in body
    assert "every other row keeps its own" in body
    assert "Skip this row: it keeps M0 only" in body and "Continue Measurement" in body
    assert "uses none of this row's values" not in body
    _t, body = M.M_I1IO_DRIVE_ROW_M0_ONLY.render(row=3, page=1)
    assert "its M0 values are kept" in body and "counts as missing" not in body
    for msg in (M.M_I1IO_DRIVE_ROW_M0_ONLY_STRIP, M.M_I1IO_DRIVE_ROW_M0_ONLY):
        assert "—" not in msg.title + msg.body


def test_in_the_window_the_row_keeps_m0_and_the_save_files_the_partial_pair(
        qtbot, monkeypatch, tmp_path, settings):  # noqa: F811
    from core.i18n import tr
    from tests.i1io_table.test_window import open_window
    from tests.i1io_table.window_sim import WindowSim
    from ui import i1io_table_window as W
    from workflow import measurement_messages as M
    orig = W.TableMeasureWindow.__init__

    def init(self, *a, **k):
        k.setdefault("dual", dual_setup("M1"))
        orig(self, *a, **k)
    monkeypatch.setattr(W.TableMeasureWindow, "__init__", init)
    sim = WindowSim(faults=UV_FAILS_ON_ROW_1)
    win, sim, run, p, saved, finished = open_window(
        qtbot, monkeypatch, tmp_path, settings, asking=False, sheet=long_sheet(),
        args=["-v", "-c", "1", "-S", "chart"], sim=sim)
    assert p.drive_until("row_failed_strip") == "row_failed_strip"
    want = M.M_I1IO_DRIVE_ROW_M0_ONLY_STRIP.render(row=1, page=1, why="x")[0]
    assert win._title.text() == want
    assert tr("was read and is kept") in win._text.text() or "M0" in win._text.text()
    p.press(W.choice_label("row_failed_strip", "skip"))
    assert p.drive_until("end_of_session") == "end_of_session"
    p.press("Save and stop")
    main = Path(run.measurement_ti3)
    assert saved and Path(saved[0][0]) == main
    assert ic.m0_only_locs(main) and ic.condition_file(main, "M1") is None
    assert ic.sibling_in_step(main, ic.partial_sibling_path(main, "M1"))
    assert S.build_from_preset(main)[0] == "M0"


def test_a_refined_row_whose_uv_pass_fails_never_keeps_the_old_m1_m2(tmp_path):
    """A complete dual measurement; a later refinement reads row 1 again and its UV pass fails:
    row 1's new M0 (the lamp pass) replaces the old one, and its OLD M1 / M2 go with the old
    reading (never left beside a new M0); row 2 keeps its M1 / M2."""
    job, sim, helper, run, p, _rep = _job(tmp_path)
    _ready(job, p)
    assert all(r.ok for r in _read_all(job, p))
    assert job.save().ok
    main = Path(run.measurement_ti3)
    assert ic.condition_file(main, "M1") is not None
    sheet = long_sheet()
    job2, sim2, helper2, run2 = RS.make_reading_job(
        tmp_path, sheet=sheet, aims=H.demo_aims(sheet), ask_after_each_step=False,
        faults=UV_FAILS_ON_ROW_1, stamp=LATER)
    job2.dual = dual_setup("M2")
    rep = job2.set_options(STRIP + ["-r"], only_locs=set(_row_locs(job, 1)))
    assert rep.ok and rep.detail.get("refine") == len(_row_locs(job, 1)), rep.detail
    p2 = H.Person(job2, sim2, {J.Confirm.ROW_FAILED_STRIP: "skip"})
    _ready(job2, p2)
    assert all(r.ok for r in _read_all(job2, p2))
    assert job2.save().ok
    assert sorted(ic.m0_only_locs(main)) == sorted(_row_locs(job, 1))
    part = ic.partial_sibling_path(main, "M1")
    assert ic.sibling_in_step(main, part)
    assert sorted(ic._locs_of(part)) == sorted(_row_locs(job, 2))
