"""MUST-1 of the 4.3.48 re-review (also in the released 4.3.47): in a small main window (German,
900 x 930) the failed row's page showed its text, then empty space; the answers were in view only
at a middle scroll position, while the arm stood over the sheet waiting for them.

The rule now: EVERY page that waits for an answer shows at least one whole answer at scroll
position 0, in the Measure tab of a 900 x 930 main window and of the smallest one the main window
allows (900 x 650), in German (the longest texts of the shipped languages here) and in English.
Checked two ways:

* every page id the panel can show is pinned (a new page left out fails), and each of them,
  given the longest German text the table pages say and four long answers, shows one;
* a real session walked in the tab (a failed row, the problem page, a Stop, the ending and the
  way home), checking every page it shows.

The answers' box is also never cut above its first row at the scroll edge (``_cut_above``)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from core import i18n
from tests.i1io_table.test_window_in_the_measure_tab import beta, start, tab, table_run  # noqa: F401
from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_person import WindowPerson
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W

ROOT = Path(__file__).resolve().parents[2]
#: the main window's frame above the Measure tab's own area (the masthead, the run row, the tab
#: bar): "900 x 650 ... the Measure tab then has about 900 x 540" (test_quiet_part3)
ABOVE_THE_TAB = 110
SIZES = [(900, 930), (900, 650)]


@pytest.fixture(params=["de", "en"])
def language(request):
    before = i18n.current_language() if hasattr(i18n, "current_language") else "en"
    i18n.set_language(request.param)
    yield request.param
    i18n.set_language(before or "en")


@pytest.fixture
def host(tab):
    """The tab inside a window of the main window's size (the tab reads its window's height to
    decide what gives its room to the panel), styled as the app styles it (the widget under
    test, never the application: CLAUDE.md)."""
    from ui.theme import _APPEARANCE_STYLE
    h = QWidget()
    lay = QVBoxLayout(h)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    spacer = QWidget(h)
    spacer.setFixedHeight(ABOVE_THE_TAB)
    lay.addWidget(spacer)
    lay.addWidget(tab, 1)
    h.setStyleSheet(_APPEARANCE_STYLE["light"][0])
    yield h
    # the tab is the tab fixture's to close
    lay.removeWidget(tab)
    tab.setParent(None)
    h.close()
    h.deleteLater()


def _one_answer_in_view(win) -> "tuple[bool, str]":
    """At scroll position 0: one answer button whole inside the panel, not hidden by the
    scrolling area's edge, above the footer."""
    win._scroll.verticalScrollBar().setValue(0)
    from PyQt6.QtCore import QPoint
    seen = []
    for b in win._buttons:
        if not b.isVisible():
            seen.append((b.text(), "hidden"))
            continue
        r = b.visibleRegion().boundingRect()
        if r.isEmpty() or r.height() < b.height() or r.width() < b.width() - 1:
            seen.append((b.text(), "region", r.height(), b.height()))
            continue
        top = b.mapTo(win, QPoint(0, 0)).y()
        if top < 0 or top + b.height() > win.height():
            seen.append((b.text(), "outside", top))
            continue
        if win._page.indexOf(win._answers) >= 0:
            vp = win._scroll.viewport()
            y = b.mapTo(vp, QPoint(0, 0)).y()
            if y + b.height() > vp.height():
                seen.append((b.text(), "below the edge", y, vp.height()))
                continue
        return True, ""
    return False, repr(seen)


def _all_page_ids() -> "set[str]":
    """Every page the panel can show: its own ``_show("…")`` pages and the job's questions."""
    src = (ROOT / "ui" / "i1io_table_window.py").read_text(encoding="utf-8")
    own = set(re.findall(r'self\._show\(\s*"([a-z_]+)"', src))
    return own | set(W.JOB_QUESTION_PAGES)


def test_every_page_the_panel_can_show_is_pinned():
    ids = _all_page_ids()
    assert len(ids) > 30, ids
    assert ids <= set(W.TableMeasureWindow.PINNED_ANSWER_PAGES), sorted(ids - set(W.TableMeasureWindow.PINNED_ANSWER_PAGES))


def _longest_table_text() -> str:
    """The longest body any table page says, in the current language."""
    import collections
    from workflow import measurement_messages as M
    best = ""
    for name in dir(M):
        msg = getattr(M, name)
        if not name.startswith("M_I1IO_DRIVE") or not isinstance(msg, M.Message):
            continue
        body = i18n.tr(msg.body).format_map(collections.defaultdict(lambda: "1"))
        if len(body) > len(best):
            best = body
    assert len(best) > 400, best
    return best


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_every_waiting_page_shows_an_answer_at_scroll_zero(tab, beta, tmp_path, monkeypatch,
                                                           qtbot, language, size, host):
    tab._settings.set(W.ASK_KEY, True)                   # the panel
    host.resize(*size)
    host.show()
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch)
    win = tab._table_window
    assert win.presentation == W.PRESENTATION_PANEL
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    p.idle()
    text = _longest_table_text()
    labels = [i18n.tr("Read it again as a strip"), i18n.tr("Read it patch by patch"),
              i18n.tr("Skip it"), i18n.tr("End this step")]
    bad = {}
    for pid in sorted(_all_page_ids()):
        win._show(pid, i18n.tr("Row 1 could not be read as a strip"), text,
                  [(lab, lambda: None) for lab in labels])
        qtbot.wait(60)
        ok, why = _one_answer_in_view(win)
        if not ok:
            bad[pid] = why
    assert not bad, (size, language, win.size(), bad)


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_a_real_session_shows_an_answer_on_every_page(tab, beta, tmp_path, monkeypatch, qtbot,
                                                      language, size, host):
    tab._settings.set(W.ASK_KEY, True)
    host.resize(*size)
    host.show()
    run, sheet = table_run(tmp_path)
    sim = start(tab, run, monkeypatch,
                sim=WindowSim(faults={"read_loc": {"A2": "dies", "1-2": "dies"}, "scan": {"not_ready": True},
                                      "scan_at": 2}))
    monkeypatch.setattr(tab, "_show_all_stripes_done", lambda table=False: None)
    win = tab._table_window
    p = WindowPerson(win, sim, lambda c: qtbot.waitUntil(c, timeout=15000))
    p.script["row_failed_strip"] = "Read it patch by patch"
    seen, bad = [], {}

    def check(page):
        qtbot.wait(60)
        if win._buttons:
            ok, why = _one_answer_in_view(win)
            if not ok:
                bad[page] = why
        seen.append(page)

    for _ in range(300):
        page = p.page()
        check(page)
        if page in ("row_failed", "row_failed_strip") and "problem" not in seen:
            win._problem_btn.click()
            check(win.pages_shown[-1])
            p.press("Cancel")
            sim.helper.faults = {}
        if page == "end_of_session":
            break
        p.answer_page(page)
    p.press("Save and stop")
    p.drive_until("done")
    check(p.page())
    assert {"sheet_laid", "aimed", "check_mark", "problem", "end_of_session",
            "done"} <= set(seen), " ".join(seen)
    assert {"row_failed", "row_failed_strip"} & set(seen), seen
    assert not bad, (size, language, win.size(), bad)
    p.press("Close")
    qtbot.waitUntil(lambda: tab._table_window is None, timeout=5000)


def test_the_answers_box_is_never_cut_above_its_first_row(qtbot, monkeypatch, tmp_path,
                                                         settings):
    """``_cut_above`` with the answers' box across the edge: the edge stays under the last whole
    row of it, never above its first row."""
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    presentation=W.PRESENTATION_PANEL)
    p.idle()
    win._show("not_a_pinned_page", "Title", "Some text.",
              [("A", lambda: None), ("B", lambda: None), ("C", lambda: None)])
    win.resize(500, 700)
    qtbot.wait(100)
    monkeypatch.setattr(win, "_fit_room", lambda: None)
    monkeypatch.setattr(win, "_refit_room", lambda: None)
    win._place(win._answers, True, after=win._scroll)
    win._answers.adjustSize()
    win._page.activate()
    qtbot.wait(100)
    assert win._page.indexOf(win._answers) >= 0
    a = win._answers
    first = min(b.y() + b.height() for b in win._buttons)
    # the edge just under the first row: that row stays in view, 3 px kept free under it
    assert win._cut_above(a.y() + first + 3) == 3
    # the edge inside the first row: the box waits, whole, below the edge (as before)
    full = a.y() + first - 5
    assert win._cut_above(full) == full - a.y()
