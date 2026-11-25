"""THE ROW IDENTITY CHECK IN THE JOB, on the bed that reads what lies on it (the new i1iO chart
layout, 25 Nov 2026), and THE FILES: a row the check dropped leaves nothing anybody can use (strips,
patch by patch, dual rows and a dual row's lamp pass; after a refusal and skip, after "patch by
patch", after End and Save, after Continue, after a killed app)."""
from __future__ import annotations

import json
import random

import pytest

from tests.i1io_table import bed_sim as B
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_dual_table import dual_setup
from tests.i1io_table.test_job_ending import SECOND, _end
from tests.i1io_table.test_job_reading import read_page, ready_to_read
from workflow.i1io.table import identity as idn
from workflow.i1io.table import job as J
from workflow.i1io.table import measurement as ms
from workflow.i1io.table import strip as stp
from workflow.measurement_state import unread_locations

STRIP = ["-v", "-c", "1", "chart"]
SPOT = ["-v", "-c", "1", "-p", "chart"]
KINDS = ("strip", "spot", "dual", "dual spot")
PITCH = 11.0


def _chart(tmp_path, count=72, **kw):
    return B.build_chart(tmp_path, count=count, **kw)


def _job(tmp_path, chart, bed, kind="strip", script=None, aims="nominal", **kw):
    """The job on *chart* with *bed*; the aims at the nominal places unless "bed"."""
    if aims == "nominal":
        kw["aims"] = B.Bed(chart.laid()).aims(chart.sheet)
    job, sim, helper, run = B.bed_job(tmp_path, chart, bed, ask_after_each_step=False, **kw)
    if kind.startswith("dual"):
        job.dual = dual_setup("M1")
    assert job.set_options(SPOT if "spot" in kind else STRIP).ok
    p = H.Person(job, sim, {J.Confirm.ROW_FAILED: "skip", J.Confirm.ROW_FAILED_STRIP: "skip",
                            J.Confirm.ROW_IDENTITY: "right", **(script or {})})
    p.seen = []
    p.events = []
    job.on_progress = p.events.append
    real = job._judge_row

    def spy(plan, rec, readings):
        v = real(plan, rec, readings)
        p.seen.append((plan.index, v, [tuple(r["xyz"]) for r in readings
                                       if r.get("xyz") is not None]))
        return v
    job._judge_row = spy
    ready_to_read(job, p)
    return job, sim, helper, p


def _records(job_or_run):
    folder = getattr(getattr(job_or_run, "diag", None), "folder", None)
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(
        folder.rglob("*" + ms.ROW_RECORD_SUFFIX))]


def _leaks(run, values) -> "list[str]":
    """Every file of the run that holds one of *values* (XYZ triples), except the raw
    diagnostics (.readings.csv, .spec.csv and the readers' raw files)."""
    needles = set()
    for xyz in values:
        x = float(xyz[0])
        needles |= {f"{x:.6f}", f"{x:.5f}", repr(round(x, 6)), repr(x), f"{x:.4f}"}
    needles = {n for n in needles if len(n.replace("0", "").replace(".", "")) >= 4}
    out = []
    for f in sorted(run.dir.rglob("*")):
        if not f.is_file() or f.name.endswith((".readings.csv", ".spec.csv", ".raw", ".rec.csv",
                                               ".tif", ".log", ".ti2", ".ti1")):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        hit = [n for n in needles if n in text]
        if hit:
            out.append(f"{f.relative_to(run.dir)}: {hit[:2]}")
    return out


def _asked(p, what=J.Confirm.ROW_IDENTITY):
    return [d for _s, c, d, _n, _m in p.asked if c == what]


# ---- a sheet that lies right ----------------------------------------------------------------------

@pytest.mark.parametrize("kind", KINDS)
def test_a_sheet_laid_right_is_kept_and_nobody_is_asked(tmp_path, kind):
    # (100 for the dual scan since item 70: with 60, one invented noisy reading of a dark first
    # patch stands in its window, and the placement check refuses the row)
    ch = _chart(tmp_path, count=100 if "dual" in kind else 72,
                patch_h=12.0 if "dual" in kind else None)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid()), kind)
    rows = read_page(job, p)
    assert all(r.ok and r.detail["status"] == "read" for r in rows)
    assert _asked(p) == [] and all(v is None for _k, v, _x in p.seen)
    recs = _records(job)
    assert all(r["identity"]["judged"] and r["identity"]["verdict"] == "ok" for r in recs)
    assert all(r["identity"]["own"] > 0.8 for r in recs)
    log = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                    for f in job.diag.folder.rglob("*.log"))
    assert log.count("row identity: the row looks like itself") == len(rows)
    ev = [e for e in p.events if e["event"] == "row_identity"]
    assert len(ev) == len(rows) and all(e["judged"] and e["page"] == 1 for e in ev)
    assert not [e for e in p.events if e["event"] == "row_dropped"]


def test_a_row_that_cannot_be_judged_is_said_not_silent(tmp_path):
    ch = _chart(tmp_path, count=48, colours=[(50.0 + 10 * (i % 2), 50.0, 50.0)
                                             for i in range(48)])
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid()))
    assert all(r.ok for r in read_page(job, p))
    for r in _records(job):
        assert not r["identity"]["judged"] and r["identity"]["why"]
    log = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                    for f in job.diag.folder.rglob("*.log"))
    assert log.count("row identity: not judged: ") == 2


# ---- the veto ---------------------------------------------------------------------------------

@pytest.mark.parametrize("kind,patches", [(k, d) for k in KINDS for d in (1, -1, 2)
                                          # (two patches off, the placement check sees the dual
                                          # row first: its border is wider)
                                          if not (k == "dual" and d == 2)])
def test_a_row_off_by_whole_patches_is_refused_and_leaves_nothing(tmp_path, kind, patches):
    ph = 12.0 if "dual" in kind else 10.0
    n = 20 if "dual" in kind else 24
    ch = _chart(tmp_path, count=3 * n, patch_h=ph)
    bed = B.Bed(ch.laid(), shift_mm=(patches * (ph + 1.0), 0.0))
    job, sim, helper, p = _job(tmp_path, ch, bed, kind)
    r = p.drive(job.read_row())
    reason = idn.REASON_SPOT if "spot" in kind else idn.REASON_STRIP
    failed = _asked(p, J.Confirm.ROW_FAILED if "spot" in kind else J.Confirm.ROW_FAILED_STRIP)
    assert [d["why"] for d in failed] == [reason], (r.reason, p.seen)
    assert _asked(p) == []                       # a veto row never asks
    rec = _records(job)[0]
    assert (rec["status"], rec["why"], rec["accepted"], rec["reader_ti3"]) == \
        ("failed", reason, [], None)
    assert rec["conditions"] is None
    assert rec["refused_readings"] == n and "m0_only" not in rec
    assert [e["why"] for e in p.events if e["event"] == "row_dropped"] == [reason]
    assert len([e for e in p.events if e["event"] == "row_dropped"][0]["locs"]) == n
    values = p.seen[0][2]
    assert len(values) == n and _leaks(ch.run, values) == []
    a = job.measurement()
    assert a.reason == "nothing_read"
    job.close()
    assert _leaks(ch.run, values) == []


def test_the_rest_is_never_offered_where_the_colours_refused_a_row(tmp_path, monkeypatch):
    """R3 (safety review 2, 25 Nov 2026): a sheet one patch off is one patch off patch by patch
    too, so "so this does not matter" would not be true. (Until then both reasons counted, and
    the test of that name fixed it.) After new aims the page counts afresh."""
    ch = _chart(tmp_path, count=144)
    bed = B.Bed(ch.laid(), shift_mm=(PITCH, 0.0))
    job, sim, helper, p = _job(tmp_path, ch, bed)
    helper.faults["scan"] = {"aperture_mm": 0.0}

    real = stp.cut_row

    def refused(mm):
        bed.shift_mm = (mm, 0.0)
        monkeypatch.setattr(stp, "cut_row", real if mm == PITCH else lambda *a, **k: stp.Cut(
            False, stp.PLACEMENT_REASON))
        assert p.drive(job.read_row()).detail["status"] == "skipped"
        return _asked(p, J.Confirm.ROW_FAILED_STRIP)[-1]
    assert refused(PITCH)["why"] == idn.REASON_STRIP
    last = [refused(6.5), refused(6.5)]
    assert [d["why"] for d in last] == [stp.PLACEMENT_REASON] * 2
    assert refused(PITCH)["why"] == idn.REASON_STRIP
    failed = _asked(p, J.Confirm.ROW_FAILED_STRIP)
    assert [d["offer_rest"] for d in failed] == [False] * 4
    assert [d["aim_again"] for d in failed] == [True, False, False, True]
    assert p.drive(job.home()).ok and p.drive(job.align()).ok
    assert refused(6.5)["offer_rest"] is True


def test_a_row_the_colours_refused_does_not_count_towards_the_rest(tmp_path, monkeypatch):
    ch = _chart(tmp_path, count=96)
    bed = B.Bed(ch.laid(), shift_mm=(PITCH, 0.0))
    job, sim, helper, p = _job(tmp_path, ch, bed)
    helper.faults["scan"] = {"aperture_mm": 0.0}
    p.drive(job.read_row())
    p.drive(job.read_row())
    assert p.drive(job.home()).ok and p.drive(job.align()).ok
    monkeypatch.setattr(stp, "cut_row", lambda *a, **k: stp.Cut(False, stp.PLACEMENT_REASON))
    p.drive(job.read_row())
    failed = _asked(p, J.Confirm.ROW_FAILED_STRIP)
    assert [d["why"] for d in failed] == [idn.REASON_STRIP] * 2 + [stp.PLACEMENT_REASON]
    assert [d["offer_rest"] for d in failed] == [False] * 3


def test_the_reason_stands_in_all_three_places_of_the_placement_reason():
    assert J.PLACE_REASONS == (stp.PLACEMENT_REASON, idn.REASON_STRIP)
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(J))
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "TableJob")
    uses = [x for x in ast.walk(cls) if isinstance(x, ast.Attribute)
            and x.attr == "PLACEMENT_REASON"]
    assert uses == []                                # every use is PLACE_REASONS
    assert sum(isinstance(x, ast.Name) and x.id == "PLACE_REASONS" for x in ast.walk(cls)) == 4


def test_a_row_read_at_another_speed_is_read_again_at_chromiqs_own(tmp_path):
    ch = _chart(tmp_path)
    bed = B.Bed(ch.laid(), shift_mm=(PITCH, 0.0))
    job, sim, helper, p = _job(tmp_path, ch, bed)
    job.row_speed_factor = 1.25
    job._table.row_speed_frame = True
    answers = iter(("again", "skip"))
    p.on_ask = lambda person, res: person.script.__setitem__(
        J.Confirm.ROW_FAILED_STRIP, next(answers)) if res.confirm == J.Confirm.ROW_FAILED_STRIP \
        else None
    p.drive(job.read_row())
    recs = _records(job)
    assert [r["why"] for r in recs] == [idn.REASON_STRIP] * 2
    assert recs[0]["row_speed"][0] == 1.25 and recs[1]["row_speed"][0] == 1.0


# ---- the question -----------------------------------------------------------------------------

def _other_chart(tmp_path):
    return B.build_chart(tmp_path, name="Other", colours=B.patch_set(72, seed=99), seed=9)


@pytest.mark.parametrize("kind", KINDS)
def test_another_sheet_is_asked_about_and_right_keeps_the_row_without_reading_again(tmp_path,
                                                                                  kind):
    ph = 12.0 if "dual" in kind else 10.0
    n = 20 if "dual" in kind else 24
    ch = _chart(tmp_path, count=3 * n, patch_h=ph)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(3 * n, seed=99), seed=9,
                          patch_h=ph)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(other.laid()), kind)
    at = {}

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_IDENTITY:
            at["records"] = len(list(job.diag.folder.rglob("*" + ms.ROW_RECORD_SUFFIX)))
            at["sent"] = len(sim.received)
            at["leaks"] = _leaks(ch.run, p.seen[-1][2])
            at["readers"] = len(job._open_readers)
    p.on_ask = on_ask
    reads0 = helper.reads
    r = p.drive(job.read_row())
    assert r.ok and r.detail["status"] == "read" and r.detail["attempts"] == 1
    asked = _asked(p)
    assert len(asked) == 1 and asked[0]["row"] == 1 and asked[0]["pages"] == 1
    # unwritten while the question was open, no reader waiting, nothing sent for it
    assert at["records"] == 0 and at["leaks"] == [] and at["readers"] == 0
    rec = _records(job)[0]
    assert rec["status"] == "read" and len(rec["accepted"]) == n and rec["reader_ti3"]
    assert rec["identity"]["confirmed_by_the_person"] is True
    if kind.startswith("dual"):
        assert set(rec["conditions"]) == {"M1", "M2"}
        for f in rec["conditions"].values():
            assert (job.diag.folder / "row-1" / f).is_file()
    if "spot" in kind:
        assert helper.reads - reads0 == n
    # the next rows are not asked about, the GO came before the next movement
    k = len(p.asked)
    r = p.drive(job.read_row())
    assert r.ok and [c for _s, c, _d, _n, _m in p.asked[k:]][:1] == [J.Confirm.GO]
    assert len(_asked(p)) == 1
    rec2 = _records(job)[1]
    assert rec2["status"] == "read" and rec2["identity"]["verdict"] == "ask"
    job.close()


def test_the_veto_still_works_after_the_right_piece(tmp_path):
    ch, other = _chart(tmp_path), _other_chart(tmp_path)
    bed = B.Bed(other.laid())
    job, sim, helper, p = _job(tmp_path, ch, bed)
    assert p.drive(job.read_row()).ok and len(_asked(p)) == 1
    bed.laid = ch.laid()
    bed.shift_mm = (PITCH, 0.0)
    p.drive(job.read_row())
    assert [d["why"] for d in _asked(p, J.Confirm.ROW_FAILED_STRIP)] == [idn.REASON_STRIP]
    assert len(_asked(p)) == 1


@pytest.mark.parametrize("kind", KINDS)
def test_end_drops_the_row_and_the_files_keep_nothing_of_it(tmp_path, kind):
    """Row 1 lies right and is kept; then the wrong sheet is laid; End, Save; Continue."""
    ph = 12.0 if "dual" in kind else 10.0
    n = 20 if "dual" in kind else 24
    ch = _chart(tmp_path, count=3 * n, patch_h=ph)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(3 * n, seed=99), seed=9,
                          patch_h=ph)
    bed = B.Bed(ch.laid())
    job, sim, helper, p = _job(tmp_path, ch, bed, kind, {J.Confirm.ROW_IDENTITY: "stop"})
    assert p.drive(job.read_row()).ok
    bed.laid = other.laid()
    sent = []
    p.on_ask = lambda person, res: sent.append(len(sim.received)) \
        if res.confirm == J.Confirm.ROW_IDENTITY else None
    r = p.drive(job.read_row())
    assert (r.kind, r.reason) == (J.Kind.REFUSED, "ended_at_the_row_identity_question")
    assert len(sim.received) == sent[0]          # nothing is sent for the question or its answer
    values = p.seen[-1][2]
    assert len(values) == n
    rec = _records(job)[1]
    assert (rec["status"], rec["why"], rec["accepted"], rec["reader_ti3"], rec["conditions"],
            rec["refused_readings"]) == ("failed", idn.REASON_ENDED, [], None, None, n)
    assert [e["why"] for e in p.events if e["event"] == "row_dropped"] == [idn.REASON_ENDED]
    end, st = _end(job, p, "save")
    assert end.ok and end.detail["measurement"]["state"] == "partial"
    assert st["read"] == n
    assert _leaks(ch.run, values) == []
    unread = unread_locations(ch.run.measurement_ti3, ch.run.chart_ti2)
    assert {q["loc"] for q in ch.sheet["pages"][0]["strips"][1]["patches"]} <= set(unread)
    job.close()
    # CONTINUE: the right sheet laid, only the rest is read, the dropped row with it
    bed2 = B.Bed(ch.laid(), rng=random.Random(77))     # other noise than the first sitting's
    job2, sim2, helper2, run2 = B.bed_job(tmp_path, ch, bed2, stamp=SECOND,
                                          ask_after_each_step=False)
    if kind.startswith("dual"):
        job2.dual = dual_setup("M1")
    opts = (SPOT if "spot" in kind else STRIP)
    assert job2.set_options(opts[:-1] + ["-r"] + opts[-1:]).detail["resume_unread"] == 2 * n
    p2 = H.Person(job2, sim2)
    ready_to_read(job2, p2)
    res = read_page(job2, p2)
    assert [x.detail["status"] for x in res] == ["nothing_to_read", "read", "read"]
    end, st = _end(job2, p2, "save")
    assert end.ok and st["state"] == "complete"
    assert _leaks(ch.run, values) == []
    job2.close()


@pytest.mark.parametrize("kind", ("strip", "spot", "dual"))
def test_a_killed_app_at_the_question_keeps_nothing_of_the_row(tmp_path, kind):
    ph = 12.0 if "dual" in kind else 10.0
    n = 20 if "dual" in kind else 24
    ch = _chart(tmp_path, count=3 * n, patch_h=ph)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(3 * n, seed=99), seed=9,
                          patch_h=ph)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(other.laid()), kind)

    class Killed(Exception):
        pass

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_IDENTITY:
            raise Killed
    p.on_ask = on_ask
    with pytest.raises(Killed):
        p.drive(job.read_row())
    values = p.seen[-1][2]
    assert values and _leaks(ch.run, values) == []
    # the app is gone here; the next START
    job2, sim2, helper2, _r = B.bed_job(tmp_path, ch, B.Bed(ch.laid()), stamp=SECOND,
                                        ask_after_each_step=False)
    found = job2.earlier_sessions()
    assert all(e["accepted"] == 0 for e in found)
    assert job2.measurement().reason in ("nothing_read", "no_run")


def test_the_window_closed_at_the_question_drops_the_row(tmp_path):
    ch, other = _chart(tmp_path), _other_chart(tmp_path)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(other.laid()), "spot")
    p.on_ask = lambda person, res: res if res.confirm == J.Confirm.ROW_IDENTITY else None
    r = p.drive(job.read_row())
    assert r.confirm == J.Confirm.ROW_IDENTITY
    r = job.cancel()
    assert r.kind == J.Kind.STOPPED
    rec = _records(job)[0]
    assert rec["status"] == "failed" and rec["accepted"] == [] and rec["refused_readings"] == 24
    assert _leaks(ch.run, p.seen[-1][2]) == []


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("answer", ("right", "stop"))
def test_a_stop_pressed_at_the_question_changes_nothing_about_its_answer(tmp_path, kind, answer):
    """(Until the review of step 3 a Stop threw "It is the right sheet" away; the old test of that
    name fixed it.) The row is kept or dropped as the person answers, and the stop is honoured
    after it, before anything moves."""
    ph = 12.0 if "dual" in kind else 10.0
    n = 20 if "dual" in kind else 24
    ch = _chart(tmp_path, count=3 * n, patch_h=ph)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(3 * n, seed=99), seed=9,
                          patch_h=ph)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(other.laid()), kind,
                               {J.Confirm.ROW_IDENTITY: answer})
    sent = []

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_IDENTITY:
            job.stop_at_next_pause()
            sent.append(len(sim.received))
    p.on_ask = on_ask
    r = p.drive(job.read_row())
    rec = _records(job)[0]
    assert sim.received[sent[0]:] == []
    if answer == "right":
        assert r.ok and r.detail["stop_asked_at_the_question"] is True
        assert rec["status"] == "read" and len(rec["accepted"]) == n and rec["reader_ti3"]
        assert job._pause_stop is False and job._go_page is None
        # the sheet is aimed at again (safety review B1: whoever stops to look may move it), and
        # whatever moves first asks the hands-off GO
        k = len(p.asked)
        p.on_ask = None
        assert p.drive(job.read_row()).reason == "needs_alignment"
        assert p.drive(job.home()).ok and p.asked[k][1] == J.Confirm.GO
        assert p.drive(job.align()).ok
        r = p.drive(job.read_row())
        assert r.ok and "stop_asked_at_the_question" not in r.detail
    else:
        assert r.kind == J.Kind.REFUSED
        assert rec["status"] == "failed" and rec["accepted"] == [] and rec["reader_ti3"] is None
        assert _leaks(ch.run, p.seen[-1][2]) == [] and _value_files_left(job, rec) == []
        assert job.needs_aims()
    job.close()


# ---- the earlier attempts of a dropped row ----------------------------------------------------

def _saved_locs(ch, job, p):
    """The locations the saved measurement holds (empty when nothing is saved)."""
    end, _st = _end(job, p, "save")
    if not ch.run.measurement_ti3.is_file():
        return set()
    every = {q["loc"] for pg in ch.sheet["pages"] for st in pg["strips"] for q in st["patches"]}
    return every - set(unread_locations(ch.run.measurement_ti3, ch.run.chart_ti2))


ROW_A = {f"A{k}" for k in range(1, 25)}


@pytest.mark.parametrize("failed_at", (6, 11))
@pytest.mark.parametrize("lies,then", (("another sheet", "end"), ("one patch off", "skip"),
                                       ("another sheet", "end after stop"),
                                       ("another sheet", "kill")))
def test_a_dropped_rows_earlier_attempts_go_with_it(tmp_path, failed_at, lies, then):
    """Patch by patch, the first attempt ends early with fewer than 12 patches (a patch fails
    twice, or Stop), which is too little to judge; the row is read again, judged wrong, dropped:
    nothing of the first attempt is saved either."""
    ch, other = _chart(tmp_path), _other_chart(tmp_path)
    bed = B.Bed((other if lies == "another sheet" else ch).laid(),
                shift_mm=(0.0, 0.0) if lies == "another sheet" else (PITCH, 0.0))
    job, sim, helper, p = _job(tmp_path, ch, bed, "spot", {J.Confirm.ROW_IDENTITY: "stop"})

    class Killed(Exception):
        pass
    again = iter(("again", "skip", "skip"))

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED:
            person.script[J.Confirm.ROW_FAILED] = next(again)
        if then == "kill" and res.confirm == J.Confirm.ROW_IDENTITY:
            raise Killed
    p.on_ask = on_ask
    if then == "end after stop":
        helper.on_read = lambda n: job.stop_at_next_pause() if n == failed_at - 1 else None
        assert p.drive(job.read_row()).kind == J.Kind.REFUSED
        helper.on_read = None
        assert len(_records(job)[0]["accepted"]) == failed_at - 1
        p.drive(job.read_row(row=1))
    else:
        helper.faults["read_twice"] = {f"A{failed_at}": "error"}
        if then == "kill":
            with pytest.raises(Killed):
                p.drive(job.read_row())
        else:
            p.drive(job.read_row())
    first = [r for r in _records(job) if r["attempt"] == 1 or then == "end after stop"][0]
    if then == "kill":
        # the app is gone while the question is open: the next START takes it as "no", for the
        # first attempt too
        job2, _s, _h, _r = B.bed_job(tmp_path, ch, B.Bed(ch.laid()), stamp=SECOND,
                                     ask_after_each_step=False)
        job2.set_options(SPOT)
        H.Person(job2, _s).drive(job2.open())
        assert all(e["accepted"] == 0 for e in job2.earlier_sessions())
        first = [r for r in _records(job) if r["attempt"] == 1][0]
        assert first["accepted"] == [] and first["dropped_later"] == idn.REASON_ENDED
        for x in p.seen:
            assert _leaks(ch.run, x[2]) == []
        return
    assert first["accepted"] == [] and first["reader_ti3"] is None and first["conditions"] is None
    assert first["refused_readings"] == failed_at - 1
    assert first["dropped_later"] in idn.REASONS
    assert all(_value_files_left(job, r) == [] for r in _records(job))
    for x in p.seen:
        assert _leaks(ch.run, x[2]) == []
    for f in job.diag.folder.rglob("*.readings.csv"):
        import csv
        rows = list(csv.DictReader(f.open(encoding="utf-8")))
        assert rows and all(q["plausible"] == "False" and q["why"] for q in rows), f.name
    ev = [e for e in p.events if e["event"] == "row_dropped"]
    assert ev and ev[0]["earlier"] == failed_at - 1
    assert _saved_locs(ch, job, p) & ROW_A == set()
    job.close()


@pytest.mark.parametrize("kind", KINDS)
def test_a_row_read_before_in_this_sitting_goes_with_the_dropped_one(tmp_path, kind):
    """Strips, dual and patch by patch: the row was read whole, the person reads it again and the
    wrong sheet lies there: End drops the row, every attempt of it; an earlier sitting's stays."""
    ph = 12.0 if "dual" in kind else 10.0
    n = 20 if "dual" in kind else 24
    # (5 rows since item 70, as above)
    ch = _chart(tmp_path, count=5 * n, patch_h=ph)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(5 * n, seed=99), seed=9,
                          patch_h=ph)
    bed = B.Bed(ch.laid())
    job, sim, helper, p = _job(tmp_path, ch, bed, kind, {J.Confirm.ROW_IDENTITY: "stop"})
    assert p.drive(job.read_row()).ok and p.drive(job.read_row()).ok
    assert job.measurement().ok                      # put together once, with row A in it
    bed.laid = other.laid()
    r = p.drive(job.read_row(row=1))
    assert r.reason == "ended_at_the_row_identity_question"
    recs = [r for r in _records(job) if r["row"] == 1]
    assert len(recs) == 2 and all(r["accepted"] == [] and r["reader_ti3"] is None
                                  and r["conditions"] is None for r in recs)
    assert recs[0]["dropped_later"] == idn.REASON_ENDED
    assert all(_value_files_left(job, r) == [] for r in recs)
    for k in (0, 2):                                 # (row 2's own files hold its own numbers)
        assert [x for x in _leaks(ch.run, p.seen[k][2]) if "/row-2/" not in x] == []
    locs = _saved_locs(ch, job, p)
    assert locs == {f"B{k}" for k in range(1, n + 1)}
    assert ch.run.measurement_ti3.is_file()
    job.close()


def test_a_dual_rows_lamp_pass_kept_before_goes_with_the_dropped_row(tmp_path):
    """The right sheet: the second pass fails, the lamp pass is kept as M0; read again on another
    sheet: dropped, the lamp pass too."""
    n = 20
    ch = _chart(tmp_path, count=3 * n, patch_h=12.0)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(3 * n, seed=99), seed=9,
                          patch_h=12.0)
    bed = B.Bed(ch.laid())
    job, sim, helper, p = _job(tmp_path, ch, bed, "dual", {J.Confirm.ROW_IDENTITY: "stop"})
    helper.faults["scan"] = {"uv_wrong_strip": True}
    p.drive(job.read_row())
    assert _records(job)[0]["m0_only"] and len(_records(job)[0]["accepted"]) == n
    helper.faults.pop("scan")
    bed.laid = other.laid()
    p.drive(job.read_row(row=1))
    recs = _records(job)
    assert len(recs) == 2 and all(r["accepted"] == [] and "m0_only" not in r for r in recs)
    assert all(_value_files_left(job, r) == [] for r in recs)
    assert _leaks(ch.run, p.seen[0][2]) == []
    assert _saved_locs(ch, job, p) == set()
    job.close()


def test_an_earlier_sittings_row_stays(tmp_path):
    """Sitting 1 was killed with row A read; sitting 2 completes it, reads row A again on another
    sheet, End: sitting 1's row A is what is saved."""
    ch, other = _chart(tmp_path), _other_chart(tmp_path)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid()), "strip")
    assert p.drive(job.read_row()).ok
    want = {tuple(a["xyz"]) for a in _records(job)[0]["accepted"]}
    bed = B.Bed(other.laid())
    job2, sim2, helper2, _r = B.bed_job(tmp_path, ch, bed, stamp=SECOND,
                                        ask_after_each_step=False,
                                        aims=B.Bed(ch.laid()).aims(ch.sheet))
    assert job2.set_options(STRIP).ok
    assert job2.adopt_earlier(job.stamp).ok
    p2 = H.Person(job2, sim2, {J.Confirm.ROW_IDENTITY: "stop"})
    ready_to_read(job2, p2)
    p2.drive(job2.read_row())
    assert [len(r["accepted"]) for r in _records(job)] == [24]
    assert {tuple(a["xyz"]) for a in _records(job)[0]["accepted"]} == want
    assert _saved_locs(ch, job2, p2) == ROW_A


# ---- the values on the disk while nobody has answered; a killed app -----------------------------

#: what may stay of a row nobody kept: the plan and the raw readings, named as refused
RAW = (".row.json", ".readings.csv", ".spec.csv", ".raw", ".ti2", ".plan_and_result.json",
       ".cut.json", ".strip_cut.json", ".dual_cut.json")


def _value_files_left(job, rec) -> "list[str]":
    """The files beside *rec*'s record that could hold its values (spectra too, which `_leaks`
    does not see): everything but the raw ones."""
    out = []
    for f in sorted(job.diag.folder.rglob(f"{rec['name']}*")):
        if f.is_file() and not f.name.endswith(RAW):
            out.append(f.name)
    for d in {f.parent for f in job.diag.folder.rglob(f"{rec['name']}{ms.ROW_RECORD_SUFFIX}")}:
        out += [f.name for f in sorted((d / "conditions").glob("*"))]
    return out


@pytest.mark.parametrize("kind", KINDS)
def test_while_the_question_is_open_no_file_of_values_stands_there(tmp_path, kind):
    ph = 12.0 if "dual" in kind else 10.0
    n = 20 if "dual" in kind else 24
    ch = _chart(tmp_path, count=3 * n, patch_h=ph)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(3 * n, seed=99), seed=9,
                          patch_h=ph)
    for answer in ("right", "stop"):
        (tmp_path / answer).mkdir()
        job, sim, helper, p = _job(tmp_path / answer, ch, B.Bed(other.laid()), kind,
                                   {J.Confirm.ROW_IDENTITY: answer},
                                   stamp="20261125-12000" + str(len(answer)))
        seen = {}

        def on_ask(person, res):
            if res.confirm == J.Confirm.ROW_IDENTITY:
                d = job.diag.folder / "row-1"
                seen["files"] = [f.name for f in d.rglob("*") if f.is_file()
                                 and not f.name.endswith(RAW + (J.JUDGING_SUFFIX,))]
                seen["marker"] = [f.name for f in d.glob("*" + J.JUDGING_SUFFIX)]
        p.on_ask = on_ask
        p.drive(job.read_row())
        assert seen["files"] == [] and len(seen["marker"]) == 1
        rec = _records(job)[0]
        assert not list(job.diag.folder.rglob("*" + J.JUDGING_SUFFIX))
        left = _value_files_left(job, rec)
        if answer == "stop":
            assert left == []
        else:
            # as an accepted row's, every file back
            want = {"strip": {"p1_row1.cut.ti3", "p1_row1.strip.ti3"},
                    "spot": {"p1_row1.ti3"},
                    "dual": {"p1_row1.cut.ti3", "p1_row1.dual_in.txt", "p1_row1.dual_out.txt",
                             "p1_row1.strip.ti3", "p1_row1.strip.M1.ti3", "p1_row1.strip.M2.ti3"},
                    "dual spot": {"p1_row1.ti3"}}[kind]
            assert want <= set(left), left
            if kind == "dual spot":
                assert len(left) > 2
        job.close()


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("where", ("question", "before the judgement", "after right"))
def test_a_killed_app_leaves_nothing_the_next_start_does_not_remove(tmp_path, monkeypatch, kind,
                                                                   where):
    """Killed while the question is open, between the values' files and the judgement, or after
    "right" before the row's record: the next START removes what stands there without a record;
    the raw readings stay, and other rows' files are not touched."""
    ph = 12.0 if "dual" in kind else 10.0
    n = 20 if "dual" in kind else 24
    ch = _chart(tmp_path, count=3 * n, patch_h=ph)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(3 * n, seed=99), seed=9,
                          patch_h=ph)
    bed = B.Bed(ch.laid())
    job, sim, helper, p = _job(tmp_path, ch, bed, kind)
    assert p.drive(job.read_row()).ok
    good = {f.relative_to(job.diag.folder): f.read_bytes()
            for f in (job.diag.folder / "row-1").rglob("*") if f.is_file()}
    bed.laid = other.laid()

    class Killed(BaseException):
        pass
    snapshot = tmp_path / "killed"

    def kill():
        # the disk as it is at this instant (the process's own clean-up never runs)
        import shutil
        shutil.copytree(job.diag.folder, snapshot)
        raise Killed
    if where == "before the judgement":
        monkeypatch.setattr(job, "_judge_row", lambda *a: kill())
    elif where == "after right":
        real = job.diag.write_json
        monkeypatch.setattr(job.diag, "write_json", lambda rel, data: kill()
                            if rel.endswith(ms.ROW_RECORD_SUFFIX) and not snapshot.exists()
                            else real(rel, data))
    else:
        p.on_ask = lambda person, res: kill() if res.confirm == J.Confirm.ROW_IDENTITY else None
    try:
        p.drive(job.read_row())
    except Killed:
        pass
    assert snapshot.is_dir()
    import shutil
    shutil.rmtree(job.diag.folder)
    shutil.copytree(snapshot, job.diag.folder)
    marker = list(job.diag.folder.rglob("*" + J.JUDGING_SUFFIX))
    assert len(marker) == 1
    job2, sim2, helper2, _r = B.bed_job(tmp_path, ch, B.Bed(ch.laid()), stamp=SECOND,
                                        ask_after_each_step=False)
    assert job2.set_options(SPOT if "spot" in kind else STRIP).ok
    p2 = H.Person(job2, sim2)
    p2.drive(job2.open())
    row2 = job.diag.folder / "row-2"
    assert [f.name for f in row2.rglob("*") if f.is_file() and not f.name.endswith(RAW)
            and f.name != "result.json"] == []
    assert list(row2.glob("*.spec.csv")) if "spot" not in kind else True
    assert {f.relative_to(job.diag.folder): f.read_bytes()
            for f in (job.diag.folder / "row-1").rglob("*") if f.is_file()} == good
    assert [e["accepted"] for e in job2.earlier_sessions()] == [n]
    log = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                    for f in job2.diag.folder.rglob("*.log"))
    assert "that was not settled when the app ended are removed" in log


def test_a_settled_rows_values_are_never_removed_by_the_next_start(tmp_path):
    """A marker that stayed beside a row WITH its record (killed between the two): the marker
    goes, the row stays."""
    ch = _chart(tmp_path)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid()), "strip")
    assert p.drive(job.read_row()).ok
    d = job.diag.folder / "row-1"
    (d / ("p1_row1" + J.JUDGING_SUFFIX)).write_text("{}", encoding="utf-8")
    before = sorted(f.name for f in d.iterdir())
    assert J.remove_unjudged_leftovers([job.diag.folder]) == []
    assert sorted(f.name for f in d.iterdir()) == [
        n for n in before if not n.endswith(J.JUDGING_SUFFIX)]


def test_a_file_that_cannot_be_taken_off_the_disk_is_emptied_and_said(tmp_path, monkeypatch):
    f = tmp_path / "a.cut.ti3"
    f.write_text("values", encoding="utf-8")
    said = []
    from pathlib import Path

    def no(self, *a, **k):
        raise PermissionError
    monkeypatch.setattr(Path, "unlink", no)
    aside = J._set_aside([f], (), lambda kind, text: said.append(text))
    assert f.read_text(encoding="utf-8") == "" and len(said) == 1 and "emptied" in said[0]
    monkeypatch.undo()
    J._bring_back(aside)
    assert f.read_text(encoding="utf-8") == "values"


# ---- what nobody could judge ------------------------------------------------------------------

def test_the_rows_read_before_the_question_that_nobody_judged(tmp_path):
    ch = _chart(tmp_path, count=72, randomize=False,
                colours=[(100.0, 100.0, 100.0)] * 24 + B.patch_set(48))
    bed = B.Bed(_other_chart(tmp_path).laid())
    job, sim, helper, p = _job(tmp_path, ch, bed, script={J.Confirm.ROW_IDENTITY: "stop"})
    assert p.drive(job.read_row()).ok
    assert job.rows_not_judged() == []               # nobody was asked yet
    assert p.drive(job.read_row()).kind == J.Kind.REFUSED
    rows = job.rows_not_judged()
    assert [(r["page"], r["row"], r["strip"], r["read"]) for r in rows] == [(1, 1, "A", 24)]
    assert rows[0]["why"] and len(_records(job)[0]["accepted"]) == 24     # nothing deleted
    # what is read after it (the right sheet laid) is not named
    bed.laid = ch.laid()
    n = len(rows)
    # (safety review B1, 25 Nov 2026: never on the aims from before the question)
    assert p.drive(job.read_row(row=2)).reason == "needs_alignment"
    assert p.drive(job.home()).ok and p.drive(job.align()).ok
    assert p.drive(job.read_row(row=2)).ok and len(job.rows_not_judged()) == n


def test_rows_that_were_judged_are_not_named(tmp_path):
    ch = _chart(tmp_path)
    bed = B.Bed(ch.laid())
    job, sim, helper, p = _job(tmp_path, ch, bed, script={J.Confirm.ROW_IDENTITY: "stop"})
    assert p.drive(job.read_row()).ok
    bed.laid = _other_chart(tmp_path).laid()
    assert p.drive(job.read_row()).kind == J.Kind.REFUSED
    assert len(_records(job)[0]["accepted"]) == 24 and job.identity_ended_at
    assert job.rows_not_judged() == []


def test_an_answered_question_names_nothing(tmp_path):
    ch = _chart(tmp_path, count=72, randomize=False,
                colours=[(100.0, 100.0, 100.0)] * 24 + B.patch_set(48))
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(_other_chart(tmp_path).laid()))
    assert p.drive(job.read_row()).ok and p.drive(job.read_row()).ok
    assert job.rows_not_judged() == []


def test_implausible_readings_are_not_judged(tmp_path):
    """Only what would be kept is judged: a reading named implausible says nothing."""
    ch = _chart(tmp_path, count=48)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid()))
    from types import SimpleNamespace
    plan = SimpleNamespace(page=0, index=0)
    truth = B.values_of(ch)
    read = [{"loc": f"A{k}", "xyz": truth[f"A{k}"] if len(truth[f"A{k}"]) == 3
             else B.xyz_of(truth[f"A{k}"])} for k in range(1, 25)]
    rec = {}
    assert job._judge_row(plan, rec, read) is None and rec["identity"]["patches"] == 24
    for r in read[8:]:
        r.update(plausible=False, xyz=[0.01, 0.01, 0.01])
    rec = {}
    assert job._judge_row(plan, rec, read) is None
    assert rec["identity"]["judged"] is False and "fewer than 12" in rec["identity"]["why"]


def test_the_same_row_of_another_page_is_named(tmp_path):
    ch = _chart(tmp_path, count=600)
    assert len(ch.sheet["pages"]) == 2
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid(1)))
    p.drive(job.read_row())
    asked = _asked(p)
    assert len(asked) == 1 and (asked[0]["page"], asked[0]["pages"], asked[0]["other"]) == \
        (1, 2, "page 2")


# ---- averaging: a dropped row of the second read -----------------------------------------------

def _xyz_by_loc(path):
    from workflow.measurement_pairing import _first_table
    fields, rows = _first_table(path.read_text(encoding="utf-8"))
    li, at = fields.index("SAMPLE_LOC"), [fields.index(f"XYZ_{c}") for c in "XYZ"]
    return {q[li].strip('"'): tuple(float(q[k]) for k in at)
            for q in (r.split() for r in rows) if len(q) >= len(fields)}


def test_an_average_takes_nothing_of_a_dropped_row(tmp_path):
    """The whole way: read 1 of a set, filed as the app files it (`promote_measurement_to_read`);
    read 2 loses row B to the question, is saved without it, and ArgyllCMS's average refuses the
    two as they are (72 patches against 24); read 2 completed by Continue and averaged: every
    value is the mean of read 1's and the right sheet's, row B too."""
    import subprocess

    from workflow.ti3_merge import _resolve_average
    ch, other = _chart(tmp_path), _other_chart(tmp_path)
    run = ch.run
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid()))
    read_page(job, p)
    end, st = _end(job, p, "save")
    assert end.ok and st["state"] == "complete"
    job.close()
    run.promote_measurement_to_read()
    assert not run.measurement_ti3.exists() and len(run.reads()) == 1

    def sitting(stamp, bed, script, opts, rng):
        j, s, _h, _r = B.bed_job(tmp_path, ch, bed, stamp=stamp, ask_after_each_step=False,
                                 aims=B.Bed(ch.laid()).aims(ch.sheet))
        assert j.set_options(opts).ok
        q = H.Person(j, s, script)
        ready_to_read(j, q)
        return j, q
    bed = B.Bed(ch.laid(), rng=random.Random(5))
    job2, p2 = sitting(SECOND, bed, {J.Confirm.ROW_IDENTITY: "stop"}, STRIP, 5)
    dropped = []
    real = job2._judge_row
    job2._judge_row = lambda plan, rec, r: (dropped.append([tuple(x["xyz"]) for x in r]),
                                            real(plan, rec, r))[1]
    assert p2.drive(job2.read_row()).ok
    bed.laid = other.laid()
    assert p2.drive(job2.read_row()).reason == "ended_at_the_row_identity_question"
    end, st = _end(job2, p2, "save")
    assert end.ok and st["state"] == "partial" and st["read"] == 24
    assert _leaks(run, dropped[1]) == []
    job2.close()
    tool = _resolve_average(None)
    out = tmp_path / "avg.ti3"

    def average(*reads):
        return subprocess.run([str(tool), *map(str, reads), str(out)], capture_output=True,
                              text=True, encoding="utf-8", timeout=300).returncode
    try:
        refused = average(run.reads()[0], run.measurement_ti3)
    except OSError:
        pytest.skip("ArgyllCMS's average is not installed")
    assert refused != 0 and not out.exists()
    job3, p3 = sitting("20261118-100000", B.Bed(ch.laid(), rng=random.Random(9)), {},
                       STRIP[:-1] + ["-r"] + STRIP[-1:], 9)
    read_page(job3, p3)
    end, st = _end(job3, p3, "save")
    assert end.ok and st["state"] == "complete"
    job3.close()
    assert _leaks(run, dropped[1]) == []
    assert average(run.reads()[0], run.measurement_ti3) == 0
    one, two, got = (_xyz_by_loc(f) for f in (run.reads()[0], run.measurement_ti3, out))
    assert len(got) == 72
    for loc, v in got.items():
        for a, b, c in zip(one[loc], two[loc], v):
            assert c == pytest.approx((a + b) / 2.0, abs=0.002), loc
    assert _leaks(run, dropped[1]) == []


# ---- refusal, then patch by patch; a row that ends early --------------------------------------

def test_after_a_refusal_patch_by_patch_reads_the_row_and_keeps_only_that(tmp_path):
    ch = _chart(tmp_path)
    bed = B.Bed(ch.laid(), shift_mm=(PITCH, 0.0))
    job, sim, helper, p = _job(tmp_path, ch, bed)

    def on_ask(person, res):
        if res.confirm == J.Confirm.ROW_FAILED_STRIP:
            person.script[res.confirm] = "patch by patch"
            bed.shift_mm = (0.0, 0.0)             # the person lays the sheet right
    p.on_ask = on_ask
    r = p.drive(job.read_row())
    assert r.ok and r.detail["row_kind"] == "spot" and r.detail["status"] == "read"
    values = p.seen[0][2]
    assert _leaks(ch.run, values) == []
    job.end()
    job.answer(J.Confirm.END, "save")
    assert _leaks(ch.run, values) == []
    job.close()


@pytest.mark.parametrize("stop_at,dropped", ((16, True), (8, False)))
def test_a_spot_row_stopped_on_the_wrong_sheet_is_dropped_when_it_can_be_judged(tmp_path, stop_at,
                                                                              dropped):
    """12 patches and more: judged, nobody is asked. Fewer: as it was (each patch was read at
    its own place), and said."""
    ch, other = _chart(tmp_path), _other_chart(tmp_path)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(other.laid()), "spot")
    helper.on_read = lambda n: job.stop_at_next_pause() if n == stop_at else None
    r = p.drive(job.read_row())
    assert r.kind == J.Kind.REFUSED and _asked(p) == []
    rec = _records(job)[0]
    values = p.seen[-1][2]
    assert len(values) == stop_at
    if dropped:
        assert rec["status"] == "failed" and rec["accepted"] == []
        assert rec["why"] == idn.REASON_ENDED and rec["refused_readings"] == stop_at
        assert _leaks(ch.run, values) == []
    else:
        assert len(rec["accepted"]) == stop_at
        assert rec["identity"]["judged"] is False and "fewer than 12" in rec["identity"]["why"]


def test_a_spot_row_stopped_on_the_right_sheet_keeps_what_was_read(tmp_path):
    ch = _chart(tmp_path)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid()), "spot")
    helper.on_read = lambda n: job.stop_at_next_pause() if n == 16 else None
    p.drive(job.read_row())
    rec = _records(job)[0]
    assert len(rec["accepted"]) == 16 and rec["identity"]["verdict"] == "ok"


@pytest.mark.parametrize("fault", ("uv_wrong_strip", "uv_not_ready"))
def test_a_dual_rows_lamp_pass_of_a_wrong_sheet_is_not_kept(tmp_path, fault):
    """The second pass fails (its values, or before it ran): the lamp pass would be kept as M0
    only, and is judged too."""
    for right in (True, False):
        d = tmp_path / str(right)
        n = 20
        ch = _chart(d, count=3 * n, patch_h=12.0)
        other = B.build_chart(d, name="Other", colours=B.patch_set(3 * n, seed=99), seed=9,
                              patch_h=12.0)
        bed = B.Bed((ch if right else other).laid())
        job, sim, helper, p = _job(d, ch, bed, "dual")
        helper.faults["scan"] = {fault: True}
        p.drive(job.read_row())
        rec = _records(job)[0]
        if right:
            assert rec["m0_only"] and len(rec["accepted"]) == n
        else:
            assert rec["accepted"] == [] and "m0_only" not in rec
            assert rec["reader_ti3"] is None and rec["refused_readings"] == n
            assert _leaks(ch.run, p.seen[-1][2]) == [] and _value_files_left(job, rec) == []
            # ...and the page says how to go on although its reason may be the second pass's
            failed = _asked(p, J.Confirm.ROW_FAILED_STRIP)
            assert failed[-1]["aim_again"] is True and job.needs_aims() is False   # (Skip)
            assert (failed[-1]["why"] in idn.REASONS) is (fault == "uv_wrong_strip")
        job.close()


# ---- the next strip, the calibration ------------------------------------------------------------

def test_the_neighbour_strip_is_asked_about_and_named(tmp_path):
    ch = _chart(tmp_path)
    # the sheet lies one strip (8 mm) further back: row 1 reads strip B
    bed = B.Bed(ch.laid(), shift_mm=(0.0, -8.0))
    job, sim, helper, p = _job(tmp_path, ch, bed)
    r = p.drive(job.read_row())
    asked = _asked(p)
    assert len(asked) == 1 and asked[0]["other"] == "row 2"
    assert r.ok


def test_every_confirmation_kind_has_one_fate():
    sets = (J.BY_SETTING.keys(), J.COUNTDOWN_INSTEAD, J.SKIPPED, J.ALWAYS_ASKED)
    assert sum(J.Confirm.ROW_IDENTITY in s for s in sets) == 1
    assert J.Confirm.ROW_IDENTITY in J.ALWAYS_ASKED
    assert (J.Confirm.ROW_IDENTITY, "right") not in J.HANDS_OFF_ANSWERS
    assert J.CHOICES[J.Confirm.ROW_IDENTITY] == ("right", "stop")


def test_a_calibration_chart_is_never_judged(tmp_path):
    from workflow.i1io.expected import expected_lab
    ch = _chart(tmp_path, count=48)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid(), shift_mm=(PITCH, 0.0)))
    job.expected_lab, job.expected_why = expected_lab(ch.run.chart_ti2, calibration=True)
    assert p.drive(job.read_row()).ok
    rec = _records(job)[0]
    assert rec["identity"] == {**rec["identity"], "judged": False, "why": "a calibration chart"}


def test_switched_off_it_judges_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(idn, "ROW_IDENTITY_CHECK", False)
    ch = _chart(tmp_path, count=48)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid(), shift_mm=(PITCH, 0.0)))
    assert p.drive(job.read_row()).ok
    assert _records(job)[0]["identity"]["why"] == "switched off"


def test_the_ship_switch_is_on():
    """It ships on only because a run on recorded rows of a real table (kept privately) repeated
    the design's result with this code: every right row kept (99), every row of a wrong sheet asked
    about (9), every row moved by one patch refused (198)."""
    assert idn.ROW_IDENTITY_CHECK is True
    assert (idn.ASK_BELOW, idn.VETO_SCORE, idn.VETO_MARGIN) == (0.5, 0.6, 0.25)
