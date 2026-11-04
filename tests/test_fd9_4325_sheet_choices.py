"""4.3.25, F7: the FD-9's sheet check offers choices instead of an OK.

Following the strip check (M-STRIP-READ-TWICE): when a sheet's readings fit
the page turned round, or another page, the worker pauses and asks; the
person can measure the page again (the safe answer, and what closing the
window does), file the readings where they belong (a complete sheet only),
or keep them as read. Every page's outcome is recorded in the .ti3.
Synthetic captures only; no device command is added.
"""
from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401

from dataclasses import replace

import pytest

import workflow.fd9.page_check as pc
from tests.test_fd9_chart_creation import ti1
from tests.test_fd9_factory_workflow import native_settings
from tests.test_fd9_multipage import capture_pages
from tests.test_fd9_partial import setup  # noqa: F401
from tests.test_fd9_normal_measurement import tab  # noqa: F401
from workflow.fd9.chart import build_chart, chart_pages
from workflow.fd9.measurement import (_keywords, checked_chart, first_table,
                                      measure_chart, resume_plan)


def _chart(s, pages=2):
    """Pages of 3 x 3 patches (30 mm on 137 x 170), the same shape each."""
    source, _ = ti1(s.tmp, rep="RGB", tokens=("R", "G", "B"), count=9 * pages)
    s.chart = build_chart(source, s.tmp / "multi", paper="137x170", dpi=72,
                          patch_mm=30, patch_height_mm=30,
                          randomize=False).ti2_path
    _, doc, locations = checked_chart(s.chart)
    return chart_pages(doc), locations


def _judge(monkeypatch, verdicts):
    """check_sheet answers from *verdicts*: {(page_index, attempt): (kind,
    found, turned)}; every other call is a normal fit."""
    seen = {}
    calls = []

    def judged(pages, page_index, design, measured):
        n = seen.get(page_index, 0)
        seen[page_index] = n + 1
        calls.append(page_index)
        v = verdicts.get((page_index, n))
        if v:
            kind, found, turned = v
            raise pc.SheetMismatch(kind, page_index + 1, found, len(pages),
                                   0.1, 0.95, turned=turned)
        return None
    monkeypatch.setattr(pc, "check_sheet", judged)
    return calls


def _run(s, answers, session="m", **kw):
    asked = []

    def on_mismatch(question):
        asked.append(question)
        return answers.pop(0)
    capture, calls = capture_pages(s, **kw)
    result = measure_chart(s.chart, native_settings(s), s.tmp / session,
                           capture=capture, on_mismatch=on_mismatch)
    return result, asked, calls


def _rows(result):
    return first_table(result["staged"])[2]


def test_measure_again_asks_for_the_same_page_and_files_nothing_of_it(
        setup, monkeypatch):
    s = setup
    pages, _ = _chart(s)
    _judge(monkeypatch, {(1, 0): ("turned", 2, True)})
    result, asked, calls = _run(s, ["again"])
    assert [q["kind"] for q in asked] == ["turned"]
    assert asked[0]["complete"] is True and asked[0]["page"] == 2
    assert [c[0] for c in calls] == [1, 2, 2]       # page 2 read twice
    assert result["complete"] and len(_rows(result)) == 18
    kw = _keywords(open(result["staged"], encoding="utf-8").read())
    assert kw["FD9_SHEET_CHECK_PAGE_1"] == pc.MATCHED
    assert kw["FD9_SHEET_CHECK_PAGE_2"] == pc.MATCHED


def test_save_it_turned_round_refiles_every_reading(setup, monkeypatch):
    s = setup
    pages, locations = _chart(s)
    _judge(monkeypatch, {(1, 0): ("turned", 2, True)})
    result, asked, calls = _run(s, ["refile"])
    assert [c[0] for c in calls] == [1, 2]
    rows = _rows(result)
    assert result["complete"] and len(rows) == 18
    design = {int(r["SAMPLE_ID"]): r for r in first_table(s.chart)[2]}
    for r in rows:                      # consistent with the chart again
        d = design[int(r["SAMPLE_ID"])]
        assert r["SAMPLE_LOC"] == locations[int(r["SAMPLE_ID"])]
        assert all(abs(float(r[f]) - float(d[f])) < 1e-6
                   for f in ("RGB_R", "RGB_G", "RGB_B"))
    kw = _keywords(open(result["staged"], encoding="utf-8").read())
    assert kw["FD9_SHEET_CHECK_PAGE_2"] == pc.TURNED_SAVED_TURNED


def test_keep_it_as_read_files_it_and_says_so(setup, monkeypatch):
    s = setup
    _chart(s)
    _judge(monkeypatch, {(1, 0): ("turned", 2, True)})
    result, _asked, calls = _run(s, ["keep"])
    assert result["complete"] and [c[0] for c in calls] == [1, 2]
    kw = _keywords(open(result["staged"], encoding="utf-8").read())
    assert kw["FD9_SHEET_CHECK_PAGE_2"] == pc.TURNED_KEPT


def test_it_was_page_two_saves_it_there_and_asks_for_page_one_again(
        setup, monkeypatch):
    s = setup
    pages, _ = _chart(s)
    _judge(monkeypatch, {(0, 0): ("wrong_sheet", 2, False)})
    result, asked, calls = _run(s, ["refile"])
    assert asked[0]["found"] == 2 and asked[0]["complete"]
    # Page 1's sheet went in as page 2; page 1 was asked for again, and
    # page 2, already filed, was not asked for at all.
    assert [c[0] for c in calls] == [1, 1]
    rows = _rows(result)
    assert result["complete"] and len(rows) == 18
    order = [p["id"] for page in pages for row in page["rows"] for p in row]
    assert [int(r["SAMPLE_ID"]) for r in rows] == order   # the chart's order
    kw = _keywords(open(result["staged"], encoding="utf-8").read())
    assert kw["FD9_SHEET_CHECK_PAGE_2"] == pc.FROM_SHEET_ASKED_AS.format(page=1)
    assert kw["FD9_SHEET_CHECK_PAGE_1"] == pc.MATCHED


def test_a_later_page_filed_first_can_be_resumed(setup, monkeypatch):
    """Stopped after a sheet was saved as page 2 and before page 1 was
    measured: the measurement holds page 2 only, and Resume takes it."""
    s = setup
    pages, _ = _chart(s)
    _judge(monkeypatch, {(0, 0): ("wrong_sheet", 2, False)})
    stop = {"n": 0}
    capture, calls = capture_pages(s)

    def stopping_capture(*a, **k):
        stop["n"] += 1
        if stop["n"] == 2:
            raise InterruptedError("Operator stopped between FD-9 pages")
        return capture(*a, **k)
    result = measure_chart(s.chart, native_settings(s), s.tmp / "m",
                           capture=stopping_capture,
                           on_mismatch=lambda q: "refile")
    rows = _rows(result)
    page2 = {p["id"] for row in pages[1]["rows"] for p in row}
    assert {int(r["SAMPLE_ID"]) for r in rows} == page2
    from workflow.fd9.measurement import publish_measurement
    publish_measurement(result["staged"], result["destination"], s.chart,
                        allow_partial=True)
    base, prior, remaining = resume_plan(
        s.chart, replace(native_settings(s), resume=True))
    assert {int(r["SAMPLE_ID"]) for r in prior} == page2
    assert remaining == [0, 1, 2]
    capture2, calls2 = capture_pages(s)
    final = measure_chart(s.chart, replace(native_settings(s), resume=True),
                          s.tmp / "m2", capture=capture2,
                          on_mismatch=lambda q: "again")
    assert final["complete"] and [c[0] for c in calls2] == [1]
    kw = _keywords(open(final["staged"], encoding="utf-8").read())
    assert kw["FD9_SHEET_CHECK_PAGE_2"] == pc.FROM_SHEET_ASKED_AS.format(page=1)


def test_a_sheet_not_measured_completely_is_never_refiled(setup,
                                                          monkeypatch):
    s = setup
    _chart(s)
    _judge(monkeypatch, {(1, 0): ("turned", 2, True)})
    result, asked, calls = _run(s, ["refile", "keep"], stop_page=2)
    assert asked[0]["complete"] is False
    assert asked[0]["measured"] < asked[0]["total"]
    # "refile" is not offered for it: taken as "again", page 2 read again.
    assert [c[0] for c in calls][:3] == [1, 2, 2]


def test_without_a_question_a_mismatch_ends_as_in_4324(setup, monkeypatch):
    s = setup
    _chart(s)
    _judge(monkeypatch, {(1, 0): ("turned", 2, True)})
    capture, _ = capture_pages(s)
    result = measure_chart(s.chart, native_settings(s), s.tmp / "m",
                           capture=capture)
    assert isinstance(result["acquisition_exception"], pc.SheetMismatch)
    assert len(_rows(result)) == 9


def test_one_sheet_again_and_turned_round(setup, monkeypatch):
    s = setup
    pages, locations = _chart(s, pages=1)
    # The fake capture reads the page from its folder's parent.
    _judge(monkeypatch, {(0, 0): ("turned", 1, True)})
    result, asked, calls = _run(s, ["again"], session="page-001/a")
    assert asked[0]["pages"] == 1 and len(calls) == 2
    assert result["complete"]
    _judge(monkeypatch, {(0, 0): ("turned", 1, True)})
    result, asked, calls = _run(s, ["refile"], session="page-001/b")
    assert len(calls) == 1 and result["complete"]
    kw = _keywords(open(result["staged"], encoding="utf-8").read())
    assert kw["FD9_SHEET_CHECK_PAGE_1"] == pc.TURNED_SAVED_TURNED


def test_refile_turns_the_grid_round_and_takes_the_charts_values():
    pages = [{"rows": [[{"id": 1}, {"id": 2}], [{"id": 3}, {"id": 4}]]},
             {"rows": [[{"id": 5}, {"id": 6}], [{"id": 7}, {"id": 8}]]}]
    design = {i: {"SAMPLE_ID": str(i), "RGB_R": f"{i * 10}"} for i in range(1, 9)}
    locations = {i: f"L{i}" for i in range(1, 9)}
    measured = [{"SAMPLE_ID": str(i), "SAMPLE_LOC": f"L{i}", "RGB_R": "x",
                 "XYZ_Y": f"{i}.5"} for i in (1, 2, 3, 4)]
    turned = pc.refile(measured, pages, 0, 0, True, design, locations)
    assert [(r["SAMPLE_ID"], r["XYZ_Y"], r["RGB_R"]) for r in turned] == [
        ("4", "1.5", "40"), ("3", "2.5", "30"), ("2", "3.5", "20"),
        ("1", "4.5", "10")]
    other = pc.refile(measured, pages, 0, 1, False, design, locations)
    assert [r["SAMPLE_ID"] for r in other] == ["5", "6", "7", "8"]
    assert other[0]["SAMPLE_LOC"] == "L5" and other[0]["XYZ_Y"] == "1.5"


# ---- the window -------------------------------------------------------------
def _window(tab, monkeypatch, question, click):
    seen = {}

    def run(dlg):
        from PyQt6.QtWidgets import QPushButton
        buttons = [b for b in dlg.findChildren(QPushButton)]
        seen["buttons"] = [b.text() for b in buttons]
        seen["default"] = [b.text() for b in buttons if b.isDefault()]
        if click is not None:
            buttons[click].click()
        return 0
    monkeypatch.setattr(tab, "_exec_measurement_window", run, raising=False)
    seen["answer"] = tab._fd9_ask_sheet(question)
    return seen


@pytest.mark.parametrize("click,answer", [(0, "again"), (1, "refile"),
                                          (2, "keep"), (None, None)])
def test_the_turned_window_offers_three_choices(tab, monkeypatch, click,
                                                answer):
    q = dict(kind="turned", page=2, found=2, pages=3, turned=True,
             complete=True, measured=40, total=40, reason="r")
    seen = _window(tab, monkeypatch, q, click)
    assert seen["buttons"] == ["Measure page 2 again", "Save it turned round",
                               "Keep it as read"]
    assert seen["default"] == ["Measure page 2 again"]
    assert seen["answer"] == answer


def test_the_wrong_page_window_names_both_pages(tab, monkeypatch):
    q = dict(kind="wrong_sheet", page=2, found=3, pages=3, turned=False,
             complete=True, measured=40, total=40, reason="r")
    seen = _window(tab, monkeypatch, q, 1)
    assert seen["buttons"] == ["Measure page 2 again",
                               "It was page 3: save it as page 3",
                               "Keep it as page 2"]
    assert seen["answer"] == "refile"


def test_a_partial_sheet_window_has_no_refile_button(tab, monkeypatch):
    q = dict(kind="wrong_sheet", page=2, found=3, pages=3, turned=False,
             complete=False, measured=12, total=40, reason="r")
    seen = _window(tab, monkeypatch, q, None)
    assert seen["buttons"] == ["Measure page 2 again", "Keep it as page 2"]
    one = dict(kind="turned", page=1, found=1, pages=1, turned=True,
               complete=True, measured=9, total=9, reason="r")
    assert _window(tab, monkeypatch, one, None)["buttons"][0] == \
        "Measure the sheet again"


def test_the_worker_waits_for_the_answer_and_stop_means_again(qapp):
    import threading
    from ui.fd9_measurement import FD9Job
    job = FD9Job("c", None, "s")
    got = []
    job.sheet_question.connect(lambda q: None)
    t = threading.Thread(target=lambda: got.append(job.ask_sheet({"k": 1})))
    t.start()
    job.answer_sheet("keep")
    t.join(5)
    assert got == ["keep"]
    t = threading.Thread(target=lambda: got.append(job.ask_sheet({"k": 1})))
    t.start()
    job.request_stop()
    t.join(5)
    assert got[-1] == "again"


def test_stop_while_the_question_is_open_ends_a_one_sheet_read(setup,
                                                               monkeypatch):
    """Review L4: Stop pressed while the question is open answers "again",
    and that must end the measurement rather than ask for the sheet again."""
    s = setup
    _chart(s, pages=1)
    _judge(monkeypatch, {(0, 0): ("turned", 1, True)})
    stopped = {"now": False}

    def on_mismatch(question):
        stopped["now"] = True             # Stop, while the window is open
        return "again"
    capture, calls = capture_pages(s)
    with pytest.raises(InterruptedError):
        measure_chart(s.chart, native_settings(s), s.tmp / "page-001" / "x",
                      capture=capture, on_mismatch=on_mismatch,
                      cancelled=lambda: stopped["now"])
    assert len(calls) == 1


def test_the_question_window_uses_a_bound_slot():
    """Review L5: the buttons connect to a method of a QDialog subclass,
    never to a closure capturing the window."""
    import inspect
    from ui import fd9_measurement as F
    src = inspect.getsource(F.FD9MeasureMixin._fd9_ask_sheet)
    assert "lambda" not in src and "def pick" not in src
    assert "FD9SheetQuestion" in src
    assert "btn.clicked.connect(self._answered)" in inspect.getsource(
        F.FD9SheetQuestion)


def test_the_live_preview_follows_the_answer(tab):
    """Review L6: "again" drops the set-aside sheet's colours, "save it
    turned round" turns them round, "save it as page M" moves them there."""
    shown = []
    tab._on_chart_measured = lambda ev, live=True: shown.append(
        sorted(p["loc"] for p in ev["patches"]))
    tab._fd9_restore_scan_colours = lambda chart: None
    tab._chart_file_for = lambda p: p
    tab._ti1_path = "x"
    asked, found = ["A1", "B1", "A2", "B2"], ["C1", "D1", "C2", "D2"]
    def colours():
        return {loc: {"loc": loc, "v": i} for i, loc in enumerate(asked)}
    tab._fd9_live_colours = colours()
    tab._fd9_follow_sheet_answer(dict(kind="turned", turned=True,
                                      locations=asked), "again")
    assert tab._fd9_live_colours == {}
    tab._fd9_live_colours = colours()
    tab._fd9_follow_sheet_answer(dict(kind="turned", turned=True,
                                      locations=asked), "refile")
    assert tab._fd9_live_colours["B2"]["v"] == 0      # (0,0) -> (R-1, C-1)
    assert tab._fd9_live_colours["A1"]["v"] == 3
    tab._fd9_live_colours = colours()
    tab._fd9_follow_sheet_answer(dict(kind="wrong_sheet", turned=False,
                                      locations=asked,
                                      found_locations=found), "refile")
    assert sorted(tab._fd9_live_colours) == sorted(found)
    assert tab._fd9_live_colours["C1"]["v"] == 0
    assert set(found) <= tab._progress_file_locs
    keep = colours()
    tab._fd9_live_colours = dict(keep)
    tab._fd9_follow_sheet_answer(dict(kind="turned", locations=asked), "keep")
    assert tab._fd9_live_colours == keep
