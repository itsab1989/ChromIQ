"""A simulated person in front of the Measure tab's table window (test and driver support, not
shipped): presses the window's own buttons, by their labels, and puts the simulated sight on a
mark before pressing Aimed (the hand on the arm)."""
from __future__ import annotations

from core.i18n import tr

#: the answer a person gives on each page when a test does not say otherwise
DEFAULT = {
    "consent": "I understand, drive my table",
    "prepare": "Start",
    "ready_to_open": "Start",
    "pending_marker": "I switched it off and on",
    "start_up": "Start the table, my hands are away",
    "go": "Go",
    "sheet_laid": "The page is laid, and my hands are away from the table",
    "arm_felt": "It moves freely",
    "aimed": "Aimed",
    "reader_consent": "Open the instrument",
    "calibration_place": "Table's tile",
    "cal_choice": "Table's tile",
    "calibration_own_tile": "Ready",
    "calibration_reseated": "Seated",
    "report_after_step": "As described, my hands are away",
    "front_choice": "I will move the sheet",
    "first_visit": "Make this move, my hands are away",
    "row_failed": "Read it again",
    "next_page": "Go on",
    "home_offered": "Bring the arm home",
    # 4.3.50: the homing that is part of the ending (its hands-off GO)
    "home_at_end": "Bring the arm home, my hands are away",
    # 4.3.50 fix round: the homing's question, still open after "Not now"
    "home_not_now": "Bring the arm home, my hands are away",
    "done": "Close",
}
#: pages whose ticks must all be ticked first
TICKED = ("consent", "ready_to_open")


class WindowPerson:
    def __init__(self, win, sim, wait, script=None):
        """*wait(cond)* waits for a condition while Qt runs (qtbot.waitUntil or a driver's
        pump)."""
        self.win, self.sim, self.wait = win, sim, wait
        self.script = dict(DEFAULT)
        self.script.update(script or {})
        self.seen: "list[str]" = []

    def idle(self) -> None:
        self.wait(lambda: not self.win._busy)

    def labels(self) -> "list[str]":
        return [b.text() for b in self.win._buttons]

    def press(self, english: str) -> None:
        self.idle()
        want = tr(english)
        found = [b for b in self.win._buttons if b.text() == want and b.isEnabled()]
        assert found, (english, self.labels(), self.win.pages_shown[-1:])
        found[0].click()
        self.idle()

    def leave_it_there(self) -> None:
        """The answer that leaves the arm out: "Leave it there" where a page still offers it (the
        homing offered after a stop); at the homing of the ending (4.3.50 fix round, MUST-1)
        "Not now" and then Close, which answers the homing's open question "back" and ends the
        connection to the table."""
        if self.page() == "home_at_end":
            self.press("Not now")
            assert self.page() == "home_not_now", self.win.pages_shown[-3:]
            self.press("Close")
            return
        self.press("Leave it there")

    def page(self) -> str:
        self.idle()
        return self.win.pages_shown[-1] if self.win.pages_shown else ""

    def answer_page(self, page: "str | None" = None) -> str:
        page = page or self.page()
        self.seen.append(page)
        ans = self.script.get(page)
        assert ans is not None, f"no answer scripted for the page {page!r}"
        if page in TICKED:
            for cb in self.win._tick_widgets:
                cb.setChecked(True)
        if page == "home_at_end" and ans == "Leave it there":
            # (an older script's word for leaving the arm out: Not now, then Close)
            self.leave_it_there()
            return page
        if page == "aimed" and self.sim.sim is not None:
            self.sim.aim(self.win._last.detail["mark"])
        self.press(ans)
        return page

    def at_the_rows(self, page: "str | None" = None) -> bool:
        """4.3.50: the hands-off GO before the first move of a row (since the check move to mark 3
        is gone, the page right after the aims, or after the careful steps): "rows" in
        :meth:`drive_until` stops there, unanswered (press "Go" to start reading)."""
        page = page or self.page()
        last = getattr(self.win, "_last", None)
        return (page == "go" and last is not None
                and (getattr(last, "detail", None) or {}).get("step") == "read_row")

    def drive_until(self, stop_at, limit: int = 400) -> str:
        """Answer every page until one in *stop_at* is shown (returned)."""
        stop_at = (stop_at,) if isinstance(stop_at, str) else tuple(stop_at)
        for _ in range(limit):
            p = self.page()
            if p in stop_at:
                return p
            if "rows" in stop_at and self.at_the_rows(p):
                return "rows"
            self.answer_page(p)
        raise AssertionError(f"never reached {stop_at}; seen {self.seen[-12:]}")
