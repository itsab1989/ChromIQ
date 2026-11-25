"""MEASURING A CHART IN PIECES (the new i1iO chart layout, step 8), on the bed that reads what lies on
it: four pieces of one sheet, stopped and continued, one strip refined, and at each of the four
pieces another piece, another chart and the uncut sheet laid in its place."""
from __future__ import annotations


import pytest

from tests.i1io_table import bed_sim as B
from tests.i1io_table import job_harness as H
from tests.i1io_table.test_job_ending import SECOND, _end
from tests.i1io_table.test_job_reading import read_page, ready_to_read
from tests.i1io_table.test_row_identity_job import _asked, _job, _leaks, _records, _xyz_by_loc
from workflow.i1io import pieces as P
from workflow.i1io.table import job as J
from workflow.measurement_state import unread_locations

STRIP = ["-v", "-c", "1", "chart"]
#: A small sheet of four pieces, so that a whole chart is read in seconds.
FOUR = ("v1;sheet=250x340;piece=125x170;turn=0;at=0,170/0,0/125,170/125,0;cut_x=125;cut_y=170")


@pytest.fixture(scope="module")
def chart(tmp_path_factory):
    from workflow.i1io import support
    was = support.i1io_enabled()
    support.set_enabled_for_this_process(True)
    ch = B.build_chart(tmp_path_factory.mktemp("four"), paper="250x340", count=440,
                       i1io_pieces=FOUR, i1io_limits=2)
    from workflow.i1io import sheets
    ch.uncut = sheets.ensure(ch.run.chart_ti2)
    support.set_enabled_for_this_process(was)
    assert len(ch.sheet["pages"]) == 4 and len(ch.uncut) == 1
    return ch


@pytest.fixture
def four(chart, tmp_path):
    """The chart in a project of its own (a measurement is filed there)."""
    import shutil
    from core.file_manager import Project
    run = Project.create(tmp_path / "Bed-Target", "Bed-Target").current_run()
    run.ensure_dir()
    for f in chart.run.dir.iterdir():
        if f.is_file():
            shutil.copy(f, run.dir / f.name)
    return B.Chart(run, chart.sheet, [run.dir / t.name for t in chart.tiffs], chart.colours)


def _locs(ch, page):
    return [q["loc"] for st in ch.sheet["pages"][page]["strips"] for q in st["patches"]]


def _on_to(job, p, bed, ch, page, laid=None):
    """Page *page* laid (or *laid* in its place), the arm homed, aimed again."""
    if job.page != page:
        assert p.drive(job.home()).ok
        assert job.next_page().ok and job.page == page
        bed.laid = laid or ch.laid(page)
        assert p.drive(job.align()).ok


def test_the_sheet_is_four_pieces_for_the_table_too(four):
    plan = P.record_of(four.run.chart_ti2)
    assert plan.token == FOUR and plan.count == 4
    locs = [v for k in range(4) for v in _locs(four, k)]
    assert len(set(locs)) == len(locs) >= 440
    # every piece has its own patches and its own expected colours
    for k in range(4):
        values = B.values_of(four, k)
        assert len(values) == len(_locs(four, k))


def test_four_pieces_read_right_are_kept_and_nobody_is_asked(four, tmp_path):
    bed = B.Bed(four.laid(0))
    job, sim, helper, p = _job(tmp_path, four, bed)
    for k in range(4):
        _on_to(job, p, bed, four, k)
        rows = read_page(job, p)
        assert rows and all(r.ok and r.detail["status"] == "read" for r in rows), k
    assert _asked(p) == []
    end, st = _end(job, p, "save")
    assert end.ok and st["state"] == "complete"
    assert unread_locations(four.run.measurement_ti3, four.run.chart_ti2) in ([], (), set())


def test_stopped_in_piece_3_continued_and_one_strip_of_piece_2_refined(four, tmp_path):
    ch = four
    bed = B.Bed(ch.laid(0))
    job, sim, helper, p = _job(tmp_path, ch, bed)
    for k in range(2):
        _on_to(job, p, bed, ch, k)
        assert all(r.ok for r in read_page(job, p))
    _on_to(job, p, bed, ch, 2)
    assert p.drive(job.read_row()).ok
    end, st = _end(job, p, "save")
    assert end.ok and st["state"] == "partial"
    n = len(ch.sheet["pages"][2]["strips"][0]["patches"])
    assert st["read"] == len(_locs(ch, 0)) + len(_locs(ch, 1)) + n
    job.close()
    unread = set(unread_locations(ch.run.measurement_ti3, ch.run.chart_ti2))
    assert unread == (set(_locs(ch, 2)[n:]) | set(_locs(ch, 3)))

    # CONTINUE: the rest of piece 3, then piece 4
    bed2 = B.Bed(ch.laid(2))
    job2, sim2, helper2, _r = B.bed_job(tmp_path, ch, bed2, stamp=SECOND,
                                        ask_after_each_step=False,
                                        aims=B.Bed(ch.laid(0)).aims(ch.sheet))
    assert job2.set_options(STRIP[:-1] + ["-r"] + STRIP[-1:]).detail["resume_unread"] == \
        len(unread)
    job2.page = 2                        # (the window opens the first piece with unread patches)
    p2 = H.Person(job2, sim2, {J.Confirm.ROW_FAILED_STRIP: "skip"})
    ready_to_read(job2, p2)
    res = read_page(job2, p2)
    assert [x.detail["status"] for x in res][0] == "nothing_to_read"
    assert all(x.detail["status"] == "read" for x in res[1:]) and len(res) > 1
    _on_to(job2, p2, bed2, ch, 3)
    assert all(x.ok for x in read_page(job2, p2))
    assert _asked(p2) == []
    end, st = _end(job2, p2, "save")
    assert end.ok and st["state"] == "complete"
    job2.close()
    whole = _xyz_by_loc(ch.run.measurement_ti3)

    # REFINE: one strip of piece 2, and nothing else is read or changed
    strip = [q["loc"] for q in ch.sheet["pages"][1]["strips"][1]["patches"]]
    import random
    bed3 = B.Bed(ch.laid(1), rng=random.Random(77))        # (other noise than the first time)
    job3, sim3, helper3, _r = B.bed_job(tmp_path, ch, bed3, stamp="20261127-100000",
                                        ask_after_each_step=False,
                                        aims=B.Bed(ch.laid(0)).aims(ch.sheet))
    rep = job3.set_options(STRIP[:-1] + ["-r"] + STRIP[-1:], only_locs=set(strip))
    assert rep.ok and rep.detail.get("refine") == len(strip)
    job3.page = 1
    p3 = H.Person(job3, sim3, {J.Confirm.ROW_FAILED_STRIP: "skip"})
    ready_to_read(job3, p3)
    res = read_page(job3, p3)
    assert [x.detail["status"] for x in res].count("read") == 1
    end, st = _end(job3, p3, "save")
    assert end.ok and st["state"] == "complete"
    after = _xyz_by_loc(ch.run.measurement_ti3)
    changed = {k for k in whole if whole[k] != after[k]}
    assert set(whole) == set(after) and changed and changed <= set(strip)


@pytest.mark.parametrize("what", ["another piece", "another chart", "the uncut sheet"])
@pytest.mark.parametrize("piece", [0, 1, 2, 3])
def test_what_does_not_belong_there_is_asked_about_and_not_kept(four, chart, tmp_path, what,
                                                                piece):
    """The first row of each piece with something else on the bed: the question where the row can
    be judged; "End measurement" keeps nothing of it. (The uncut sheet lies with its first piece
    where a piece lies: for piece 1 that is the right paper, and its rows are right.)"""
    ch = four
    if what == "another piece":
        wrong = ch.laid((piece + 1) % 4)
    elif what == "another chart":
        other = B.build_chart(tmp_path, name="Other", colours=B.patch_set(440, seed=99), seed=9,
                              paper="250x340", i1io_pieces=FOUR, i1io_limits=2)
        wrong = other.laid(piece)
    else:
        wrong = B.Laid.from_tiff(chart.uncut[0], (250.0, 340.0))
    bed = B.Bed(ch.laid(0))
    job, sim, helper, p = _job(tmp_path, ch, bed,
                               script={J.Confirm.ROW_IDENTITY: "stop"})
    for k in range(piece):
        _on_to(job, p, bed, ch, k)
        assert p.drive(job.read_row()).ok                 # (one row of each piece before)
    kept = [x for _i, _v, vs in p.seen for x in vs]
    if piece:
        _on_to(job, p, bed, ch, piece, laid=wrong)
    else:
        bed.laid = wrong
    n = len(p.seen)
    r = p.drive(job.read_row())
    judged = p.seen[n]
    if what == "the uncut sheet" and piece == 0:
        assert r.ok and r.detail["status"] == "read" and _asked(p) == []
        return
    asked = _asked(p)
    assert len(asked) == 1, (r.reason, judged[1])
    assert asked[0]["page"] == piece + 1 and asked[0]["pages"] == 4
    if what == "another piece":
        assert asked[0]["other"] == f"page {(piece + 1) % 4 + 1}"
    assert r.reason == "ended_at_the_row_identity_question"
    rec = _records(job)[-1] if piece == 0 else [
        x for x in _records(job) if x["page"] == piece + 1 or x.get("page") == piece][-1]
    assert rec["accepted"] == [] and rec["refused_readings"] == len(judged[2])
    values = [v for v in judged[2] if v not in kept]
    if piece:
        end, st = _end(job, p, "save")
        assert end.ok and st["read"] == sum(
            len(ch.sheet["pages"][k]["strips"][0]["patches"]) for k in range(piece))
    job.close()
    assert _leaks(ch.run, values) == []


def test_the_right_answer_keeps_the_row_and_asks_no_more_of_this_piece(four, tmp_path):
    ch = four
    bed = B.Bed(ch.laid(0))
    job, sim, helper, p = _job(tmp_path, ch, bed)
    _on_to(job, p, bed, ch, 1, laid=ch.laid(2))           # piece 3 laid for piece 2
    rows = read_page(job, p)
    assert len(_asked(p)) == 1 and all(r.ok for r in rows[:2])
    bed.laid = ch.laid(3)
    _on_to(job, p, bed, ch, 2, laid=ch.laid(3))           # …and again: a question of its own
    assert p.drive(job.read_row()).ok
    assert len(_asked(p)) == 2


def test_averaging_two_reads_of_a_chart_in_pieces(four, tmp_path):
    """Piece = page: the average of two whole reads is made of all four."""
    import subprocess
    from workflow.ti3_merge import _resolve_average
    reads = []
    for stamp in (None, SECOND):
        bed = B.Bed(four.laid(0))
        kw = {"stamp": stamp} if stamp else {}
        job, sim, helper, p = _job(tmp_path, four, bed, **kw)
        for k in range(4):
            _on_to(job, p, bed, four, k)
            assert all(r.ok for r in read_page(job, p))
        end, st = _end(job, p, "save")
        assert end.ok and st["state"] == "complete"
        job.close()
        four.run.promote_measurement_to_read()
    reads = four.run.reads()
    assert len(reads) == 2
    out = tmp_path / "avg.ti3"
    try:
        rc = subprocess.run([str(_resolve_average(None)), *map(str, reads), str(out)],
                            capture_output=True, text=True, encoding="utf-8",
                            timeout=300).returncode
    except OSError:
        pytest.skip("ArgyllCMS's average is not installed")
    assert rc == 0
    n = len([v for k in range(4) for v in _locs(four, k)])
    import re
    assert int(re.search(r"NUMBER_OF_SETS (\d+)", out.read_text(encoding="utf-8")).group(1)) == n


