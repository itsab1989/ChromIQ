"""THE AIMS ARE GIVEN UP (safety review of the new i1iO chart layout, 25 Nov 2026, B1 and S1): after
the question whether the right sheet lies on the table, or after a row that was refused as read
beside its place, the sheet may be another one or lie elsewhere. No row is read on the aims from
before; the arm goes home and the three marks are aimed at again. And S2 and N7: blank paper is asked
about whatever its ranks say, and the judge never takes the place of the table's own error."""
from __future__ import annotations

import random

import pytest

from tests.i1io_table import bed_sim as B
from tests.i1io_table.test_pieces_in_the_window import _window, open_window, settings  # noqa: F401
from tests.i1io_table.test_pieces_measured import chart, four, _on_to  # noqa: F401
from tests.i1io_table.test_row_identity_job import _asked, _job, _records
from workflow.i1io.table import identity as idn
from workflow.i1io.table import job as J


def _moves(sim, n):
    return [ln for ln in sim.received[n:] if ln[:3] in (";m0", ";m2", ";m1", ";m4")]


def _kept(job, page: int = 1) -> dict:
    """What the records keep of a page (1-based): {location: XYZ}."""
    return {a["loc"]: a["xyz"] for r in _records(job) if r["page"] == page
            for a in r["accepted"]}


def _aimed(p):
    return len([a for a in p.asked if a[1] == J.Confirm.AIMED])


def _at_the_question(tmp_path, ch, kind, answer="stop"):
    """Piece 1 is read, piece 3 laid for piece 2: the question, answered with *answer*."""
    bed = B.Bed(ch.laid(0))
    job, sim, helper, p = _job(tmp_path, ch, bed, kind, script={J.Confirm.ROW_IDENTITY: answer})
    while job.rows_left():
        assert p.drive(job.read_row()).ok
    _on_to(job, p, bed, ch, 1, laid=ch.laid(2))
    res = p.drive(job.read_row())
    assert len(_asked(p)) == 1
    return job, sim, p, bed, res


def _keep_measuring(job):
    e = job.end()
    assert e.kind == J.Kind.NEEDS
    e = job.answer(J.Confirm.END, "keep measuring")
    assert e.ok and e.detail["ending"] == "keep_measuring"
    return [r["row"] for r in e.detail["missing_rows"] if r["page"] == 2]


# the reviewer's table: piece 2 laid by eye, this far (along, across) off the aims of piece 3
OFFS = ((0.0, 0.0), (1.5, 1.0), (2.5, 2.0), (3.5, 2.0), (0.0, 3.5), (5.0, 3.0))


@pytest.mark.parametrize("kind", ["strip", "spot"])
@pytest.mark.parametrize("off", OFFS)
def test_no_row_is_read_with_the_aims_of_the_piece_before(four, tmp_path, kind, off):
    job, sim, p, bed, res = _at_the_question(tmp_path, four, kind)
    assert res.kind == J.Kind.REFUSED
    left = _keep_measuring(job)
    assert 1 in left
    bed.laid, bed.shift_mm = four.laid(1), off
    n, aimed = len(sim.received), _aimed(p)
    res = p.drive(job.read_row(1))
    assert res.kind == J.Kind.REFUSED and res.reason == "needs_alignment"
    assert not _moves(sim, n) and job.needs_aims()
    # home first (an aiming straight from the held arm is refused), then three new aims
    assert p.drive(job.align()).kind == J.Kind.REFUSED
    assert p.drive(job.home()).ok
    sim.aims = bed.aims(four.sheet, 1)
    assert p.drive(job.align()).ok and not job.needs_aims()
    assert _aimed(p) - aimed == 3
    p.script[J.Confirm.ROW_IDENTITY] = "right"
    for row in left[:2]:
        assert p.drive(job.read_row(row)).detail["status"] == "read"
    got, want = _kept(job, 2), B.values_of(four, 1)
    rows = [q["loc"] for st in four.sheet["pages"][1]["strips"][:2] for q in st["patches"]]
    for loc in rows:
        assert got[loc] == pytest.approx(B.xyz_of(want[loc]), abs=2.0), loc
    assert len(_asked(p)) == 1
    job.close()


def test_the_homing_is_the_one_of_every_end_of_a_page(four, tmp_path):
    """The aims are given up, not forgotten: until the arm is home they still say how far the
    arm may be (the same lines are sent as without the question)."""
    job, sim, p, bed, res = _at_the_question(tmp_path, four, "strip")
    assert job.alignment is not None and job.aims_void
    _keep_measuring(job)
    n = len(sim.received)
    assert p.drive(job.home()).ok
    with_question = list(sim.received[n:])
    assert job.alignment is None and not job.aims_void
    job.close()
    job, sim, p, bed, res = _at_the_question(tmp_path / "2", four, "strip", answer="right")
    assert res.ok and not job.aims_void and not job.needs_aims()
    n = len(sim.received)
    assert p.drive(job.home()).ok
    assert [ln[:3] for ln in sim.received[n:]] == [ln[:3] for ln in with_question]


def test_the_answer_right_keeps_the_aims_and_the_text_asks_nobody_to_touch_the_sheet(
        four, tmp_path):
    """“It is the right piece” means right AND not moved: no text before it asks anybody to lay
    or move paper, and whoever did has End measurement."""
    from ui.i1io_table_window import row_identity_page
    for d, pieces in (({"page": 2, "pages": 4}, True), ({"page": 2, "pages": 2}, False),
                      ({"page": 1, "pages": 1}, False)):
        text = row_identity_page(d, pieces)[1]
        before, after = text.split("Otherwise press “End measurement” below")
        assert "without moving it" in before
        assert "was not moved or swapped, press “It is the right" in before
        assert "lay" not in before.replace("layout", "")
        assert "lay the right" in after and "aim at its marks again" in after
        assert "continue the measurement" not in text
    job, sim, p, bed, res = _at_the_question(tmp_path, four, "spot", answer="right")
    assert res.ok and not job.needs_aims() and 1 in job.identity_confirmed
    # the next movement still asks the hands away, and the veto is not switched off by it
    asked = len(p.asked)
    bed.laid, bed.shift_mm = four.laid(1), (11.0, 0.0)
    res = p.drive(job.read_row())
    assert [a[1] for a in p.asked[asked:]][0] == J.Confirm.GO
    assert res.detail["status"] == "skipped" and idn.REASON_SPOT in [
        r["why"] for r in _records(job)]


def test_a_new_laying_is_a_new_question(four, tmp_path):
    """S1: "right" is said about the sheet that lies there; what is laid after the arm was home
    is asked about again."""
    job, sim, p, bed, res = _at_the_question(tmp_path, four, "strip", answer="right")
    assert res.ok and 1 in job.identity_confirmed
    assert p.drive(job.home()).ok
    bed.laid = four.laid(3)
    assert p.drive(job.align()).ok and 1 not in job.identity_confirmed
    p.script[J.Confirm.ROW_IDENTITY] = "stop"
    assert p.drive(job.read_row()).kind == J.Kind.REFUSED
    assert len(_asked(p)) == 2


@pytest.mark.parametrize("kind", ["strip", "spot"])
def test_a_refused_row_and_end_this_step(tmp_path, kind):
    """S4: a row one patch beside its place; "End this step" gives the aims up, and the row
    itself is the next one after the new aims. "Skip" and "again" read on."""
    ch = B.build_chart(tmp_path, count=72)
    bed = B.Bed(ch.laid())
    what = J.Confirm.ROW_FAILED if kind == "spot" else J.Confirm.ROW_FAILED_STRIP
    job, sim, helper, p = _job(tmp_path, ch, bed, kind, script={what: "stop"})
    assert p.drive(job.read_row()).ok
    bed.shift_mm = (11.0, 0.0)
    res = p.drive(job.read_row())
    assert res.kind == J.Kind.REFUSED and res.reason == "stopped_after_a_failed_row"
    assert job.needs_aims() and job.rows_left()[0] == 2
    n = len(sim.received)
    assert p.drive(job.read_row()).reason == "needs_alignment" and not _moves(sim, n)
    assert p.drive(job.home()).ok
    sim.aims = bed.aims(ch.sheet)
    assert p.drive(job.align()).ok
    res = p.drive(job.read_row())
    assert res.detail["row"] == 2 and res.detail["status"] == "read"
    got, want = _kept(job), B.values_of(ch)
    for q in ch.sheet["pages"][0]["strips"][1]["patches"]:
        assert got[q["loc"]] == pytest.approx(B.xyz_of(want[q["loc"]]), abs=2.0)


@pytest.mark.parametrize("ans", ["skip", "stop"])
@pytest.mark.parametrize("why", ["another_reason", "beside"])
def test_only_a_row_beside_its_place_gives_the_aims_up(tmp_path, why, ans, monkeypatch):
    ch = B.build_chart(tmp_path, count=72)
    bed = B.Bed(ch.laid())
    job, sim, helper, p = _job(tmp_path, ch, bed, "strip",
                               script={J.Confirm.ROW_FAILED_STRIP: ans})
    assert p.drive(job.read_row()).ok
    if why == "beside":
        bed.shift_mm = (11.0, 0.0)
    else:
        from workflow.i1io.table import strip as stp
        real = stp.cut_row
        monkeypatch.setattr(stp, "cut_row", lambda *a, **k: stp.Cut(
            False, "strip_instrument_delivered_nothing"))
        assert real
    p.drive(job.read_row())
    assert job.needs_aims() is (why == "beside" and ans == "stop")
    assert job.row_status[0].get(1) == (None if job.needs_aims() else
                                        "skipped" if ans == "skip" else "failed")


# ---- in the panel -----------------------------------------------------------------------------

def test_end_and_keep_measuring_go_home_and_ask_for_the_sheet(qtbot, monkeypatch, tmp_path,
                                                              settings, four):  # noqa: F811
    bed = B.Bed(four.laid(0))
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, four, bed)
    while not any(r["status"] == "read" for r in (_records(win.job) if win.job else [])):
        p.answer_page()
    bed.laid = four.laid(2)                # piece 3 lies where piece 1 belongs
    assert p.drive_until("row_identity") == "row_identity"
    n = len(sim.sim.received)
    win._on_end_pressed()
    p.idle()
    for _ in range(3):
        if p.page() == "report_after_step":
            p.press("As described, my hands are away")
    assert p.page() == "end_of_session"
    from workflow import measurement_messages as M
    assert M.M_I1IO_DRIVE_END_CHOICES_AIM_AGAIN.render()[1] in win._text.text()
    assert M.I1IO_END_GOES_ON not in win._text.text() and "goes on here" not in win._text.text()
    bed.laid = four.laid(0)
    p.press("Keep measuring")
    assert p.drive_until(("sheet_laid", "aimed", "row_identity")) == "sheet_laid"
    assert not [ln for ln in sim.sim.received[n:] if ln[:3] == ";m2"]
    assert win.job.identity_confirmed == set()
    assert p.drive_until(("aimed", "row_identity")) == "aimed"


def test_the_refused_row_page_says_how_to_aim_again():
    from workflow import measurement_messages as M
    from ui import i1io_table_window as W
    for m, word in ((M.M_I1IO_DRIVE_ROW_AIM_AGAIN, "sheet"),
                    (M.M_I1IO_DRIVE_ROW_AIM_AGAIN_PIECE, "piece")):
        body = m.render()[1]
        assert "or if it is not the right one" in body and f"lay the right {word}" in body
        assert "“End this step” and then “Carry on”" in body and word in body
        assert "aim at its marks again" in body
    for pieces in (False, True):
        for why in (idn.REASON_STRIP, idn.REASON_SPOT):
            text = M.strip_fallback_text(why, 3, pieces)
            assert "without moving it" in text and "aim at its marks again" in text
            assert "then read the row again" not in text


# ---- S2: blank paper ---------------------------------------------------------------------------

def _row(n, seed, spread=60.0):
    r = random.Random(seed)
    return {f"A{k}": (20.0 + spread * r.random(), 80 * r.random() - 40, 80 * r.random() - 40)
            for k in range(1, n + 1)}


@pytest.mark.parametrize("n", [12, 16, 24])
def test_blank_paper_is_always_asked_about(n):
    """Noise on one lightness passed as the row itself in up to one row in twenty."""
    by_chance = 0
    for seed in range(300):
        exp = _row(n, seed)
        r = random.Random(1000 + seed)
        paper = {k: (95.0 + r.gauss(0, 0.1), r.gauss(0, 0.1), r.gauss(0, 0.1)) for k in exp}
        v = idn.judge(paper, list(exp), exp)
        if not v["judged"]:
            continue
        assert v["verdict"] == "ask" and "blank paper" in idn.summary(v)
        by_chance += (v["own"] or 0) >= idn.ASK_BELOW
    assert by_chance or n > 16                     # the fault is real without the rule


def test_a_printed_row_of_little_contrast_is_judged_as_before():
    exp = _row(20, 3)
    flat = {k: (60.0 + 0.2 * (L - 50.0), a * 0.3, b * 0.3) for k, (L, a, b) in exp.items()}
    v = idn.judge(flat, list(exp), exp)
    assert v["judged"] and v["verdict"] == "ok" and "blank" not in v
    nearly = {k: (60.0 + 0.05 * (L - 50.0), a * 0.05, b * 0.05) for k, (L, a, b) in exp.items()}
    assert idn.judge(nearly, list(exp), exp)["verdict"] == "ask"


# ---- N7, N1 -------------------------------------------------------------------------------------

def test_the_judge_never_raises(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from workflow.i1io.table import strip as stp
    ch = B.build_chart(tmp_path, count=48)
    job, sim, helper, p = _job(tmp_path, ch, B.Bed(ch.laid()))
    monkeypatch.setattr(stp, "lab_d50", lambda x: (_ for _ in ()).throw(ValueError("bad")))
    rec = {}
    assert job._judge_row(SimpleNamespace(page=0, index=0), rec,
                          [{"loc": "A1", "xyz": [1.0, 2.0, 3.0]}]) is None
    assert rec["identity"]["judged"] is False


@pytest.mark.parametrize("patch", [None, ["a", "b"], [8], [8, None], [8, float("nan")], [8, 0.0]])
def test_a_patch_length_that_cannot_be_read_is_never_read_faster(patch):
    from ui.i1io_table_window import row_speed_for
    assert row_speed_for({"patch_mm": patch}, 1.95) == (1.0, "")
    assert row_speed_for({"patch_mm": patch}, 0.6) == (0.6, "")


def test_an_ordinary_ending_says_nothing_of_it(qtbot, monkeypatch, tmp_path, settings,
                                               four):  # noqa: F811
    from workflow import measurement_messages as M
    bed = B.Bed(four.laid(0))
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, four, bed)
    p.drive_until("prepare")
    while not any(r["status"] == "read" for r in (_records(win.job) if win.job else [])):
        p.answer_page()
    win._on_end_pressed()
    p.idle()
    for _ in range(3):
        if p.page() == "report_after_step":
            p.press("As described, my hands are away")
    assert p.page() == "end_of_session"
    assert M.M_I1IO_DRIVE_END_CHOICES.render()[1] in win._text.text()
    assert M.I1IO_END_AIMS_AGAIN not in win._text.text()


def test_the_refused_row_page_begins_with_the_way_on(qtbot, monkeypatch, tmp_path, settings,
                                                     four):  # noqa: F811
    """…where it is seen without scrolling; another failed row says nothing of it."""
    from workflow import measurement_messages as M
    bed = B.Bed(four.laid(0))
    win, sim, run, p, saved, finished = _window(qtbot, monkeypatch, tmp_path, settings, four, bed)
    p.drive_until("aimed")
    bed.shift_mm = (11.0, 0.0)
    assert p.drive_until(("row_failed_strip", "row_failed")) == "row_failed_strip"
    assert win._text.text().startswith(M.M_I1IO_DRIVE_ROW_AIM_AGAIN_PIECE.render()[1])
    p.press("End this step")
    for _ in range(3):
        if p.page() == "report_after_step":
            p.press("As described, my hands are away")
    p.press("Carry on")
    assert p.drive_until(("sheet_laid", "aimed", "row_failed_strip")) == "sheet_laid"


# ---- R1 (safety review 2): every way a row is dropped ------------------------------------------

@pytest.mark.parametrize("off", [(2.0, 2.5), (0.0, 2.0)])
@pytest.mark.parametrize("how", ["a reading fails", "Stop"])
def test_a_wrong_sheet_noticed_by_an_early_end(tmp_path, off, how):
    """Patch by patch: 12 patches or more of a wrong sheet, then a reading fails ("End this step"
    and Carry on) or Stop is pressed: the right sheet, laid by eye, is aimed at again."""
    ch = B.build_chart(tmp_path, count=72)
    other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(72, seed=99), seed=9)
    bed = B.Bed(other.laid())
    job, sim, helper, p = _job(tmp_path, ch, bed, "spot", script={J.Confirm.ROW_FAILED: "stop"})
    count = [0]

    def seen(ev):
        if ev.get("event") == "patch_read":
            count[0] += 1
            if count[0] == 13 and how == "Stop":
                job.stop_at_next_pause()
            elif count[0] == 13:
                bed.read = lambda x, y: [float("nan")] * 36
    job.on_progress = seen
    res = p.drive(job.read_row())
    assert res.kind == J.Kind.REFUSED
    rec = _records(job)[-1]
    assert rec["why"] == idn.REASON_ENDED and rec["accepted"] == []
    if how != "Stop":
        asked = [a[2] for a in p.asked if a[1] == J.Confirm.ROW_FAILED]
        assert asked[-1]["aim_again"] is True and asked[-1]["why"] == idn.REASON_ENDED
        assert job.rows_left()[0] == 1
    job.on_progress = None
    bed.__dict__.pop("read", None)
    bed.laid, bed.shift_mm = ch.laid(), off
    sent = len(sim.received)
    assert p.drive(job.read_row(1)).reason == "needs_alignment" and not _moves(sim, sent)
    assert p.drive(job.home()).ok
    sim.aims = bed.aims(ch.sheet)
    assert p.drive(job.align()).ok
    assert p.drive(job.read_row(1)).detail["status"] == "read"
    got, want = _kept(job), B.values_of(ch)
    for q in ch.sheet["pages"][0]["strips"][0]["patches"]:
        assert got[q["loc"]] == pytest.approx(B.xyz_of(want[q["loc"]]), abs=2.0)


@pytest.mark.parametrize("kind", ["strip", "spot"])
@pytest.mark.parametrize("go,given_up", [("back", True), ("yes", False)])
def test_back_after_read_it_again_does_not_take_the_aims_back(tmp_path, kind, go, given_up):
    ch = B.build_chart(tmp_path, count=72)
    bed = B.Bed(ch.laid())
    what = J.Confirm.ROW_FAILED if kind == "spot" else J.Confirm.ROW_FAILED_STRIP
    job, sim, helper, p = _job(tmp_path, ch, bed, kind, script={what: "again"})
    assert p.drive(job.read_row()).ok
    bed.shift_mm = (11.0, 0.0)

    def on_ask(person, res):
        if res.confirm == what:
            bed.shift_mm = (0.0, 0.0)          # the row reads well the second time
            person.script[J.Confirm.GO] = go
    p.on_ask = on_ask
    res = p.drive(job.read_row())
    assert res.kind == (J.Kind.REFUSED if go == "back" else J.Kind.OK)
    assert job.needs_aims() is given_up


@pytest.mark.parametrize("ans", ["skip", "stop", "again"])
@pytest.mark.parametrize("kind", ["strip", "spot"])
def test_stop_pressed_at_the_page_of_a_row_beside_its_place(tmp_path, kind, ans):
    """Whoever presses Stop there may reach for the sheet: new aims, whatever is answered."""
    ch = B.build_chart(tmp_path, count=72)
    bed = B.Bed(ch.laid())
    what = J.Confirm.ROW_FAILED if kind == "spot" else J.Confirm.ROW_FAILED_STRIP
    job, sim, helper, p = _job(tmp_path, ch, bed, kind, script={what: ans})
    assert p.drive(job.read_row()).ok
    bed.shift_mm = (11.0, 0.0)

    def on_ask(person, res):
        if res.confirm == what:
            job.stop_at_next_pause()
    p.on_ask = on_ask
    assert p.drive(job.read_row()).kind == J.Kind.REFUSED
    n = len(sim.received)
    assert job.needs_aims()
    assert p.drive(job.read_row()).reason == "needs_alignment" and not _moves(sim, n)


def test_the_two_wordings_of_the_ending_never_stand_together():
    """Only the last button's part differs, and each page has one of the two."""
    from workflow import measurement_messages as M
    here, again = M.M_I1IO_DRIVE_END_CHOICES.body, M.M_I1IO_DRIVE_END_CHOICES_AIM_AGAIN.body
    assert here.endswith("Keep measuring: " + M.I1IO_END_GOES_ON)
    assert again == here.replace(M.I1IO_END_GOES_ON, M.I1IO_END_AIMS_AGAIN) != here
    assert M.I1IO_END_GOES_ON not in again and M.I1IO_END_AIMS_AGAIN not in here
    # nor does any other text of the ending's page say that it goes on here
    assert "goes on here" not in M.M_I1IO_DRIVE_END.body
