"""Review 14 probes (the window, both presentations), copied from the reviewer's tree
(review14/tree/tests/i1io_table/test_review14_probes.py) as regression tests. The two probes that
documented findings (P-W1, P-W2: named ..._FINDING) are not copied: their fixed behaviour is
tested in test_last_review14_fixes.py (S-1 and M-1)."""
from __future__ import annotations

import pytest
from PyQt6.QtCore import QPoint, QRect

from core.i18n import tr
from tests.i1io_table.test_window import open_window, settings  # noqa: F401 (the fixture)
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W

MOVES = ("m0", "m1", "m2", "i1", "i0")
STRIP = ["-v", "-c", "1", "chart"]
BOTH = pytest.mark.parametrize("asking", [False, True], ids=["popups", "panel"])


def _moves(sim) -> int:
    return sum(1 for ln in sim.sim.received if ln[1:3] in MOVES)


def _btn(win, english):
    want = tr(english)
    found = [b for b in win._buttons if b.text() == want]
    assert found, (english, [b.text() for b in win._buttons], win.pages_shown[-1:])
    return found[0]


def _global_rect(b) -> QRect:
    tl = b.mapToGlobal(QPoint(0, 0))
    return QRect(tl, b.size())


# ---- P-W3: stale and doubled answers through the window -------------------------------------

@BOTH
def test_r14_w3_a_doubled_answer_call_never_moves_without_go(qtbot, monkeypatch, tmp_path,
                                                             settings, asking):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking)
    p.drive_until("arm_felt")
    n = _moves(sim)
    b = _btn(win, "It moves freely")
    b.click()
    b.click()          # the same (now hidden) button again: Qt still emits clicked
    p.idle()
    assert _moves(sim) == n
    # an answer arriving late (as from a stale pop-up) for the sheet question
    win._pending_kind = "sheet_laid"
    win.answer("yes")
    p.idle()
    assert _moves(sim) == n


# ---- P-W4: the button wait does not answer a non-aiming pop-up ------------------------------

def test_r14_w4_poll_button_outside_aiming_is_ignored(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sim=WindowSim(press=True))
    p.drive_until("go")
    win._aim_token = "forged"
    n = _moves(sim)
    win._poll_button()
    p.idle()
    assert win.pages_shown[-1] == "go" and _moves(sim) == n


# ---- P-W5: a second START while a session runs ----------------------------------------------

def test_r14_w5_start_twice_on_one_window(qtbot, monkeypatch, tmp_path, settings):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False)
    p.drive_until("go")
    n = _moves(sim)
    try:
        win.start()
    except Exception as exc:      # noqa: BLE001
        print("second start raised", exc)
    p.idle()
    print("pages", win.pages_shown[-4:], "jobs", len(sim.jobs))
    assert _moves(sim) == n


# ---- P-W6: a random window walker, both presentations, the wire checked (not the guard) -----

@pytest.mark.parametrize("seed", range(60))
def test_r14_w6_random_window_walk_never_moves_without_hands_off(qtbot, monkeypatch, tmp_path,
                                                                 settings, seed):
    import random
    from tests.i1io_table.test_review14_walker import Walk
    rnd = random.Random(seed)
    asking = bool(seed % 2)
    args = STRIP if seed % 3 == 0 else None
    sim = WindowSim(press=bool(seed % 4 == 1))
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=asking, sim=sim, args=args)
    p.idle()
    job = sim.jobs[0]
    walk = Walk(job, sim.sim, rnd)
    pages = []
    for _ in range(260):
        p.idle()
        if finished or win._finished:
            break
        page = win.pages_shown[-1] if win.pages_shown else ""
        pages.append(page)
        for cb in win._tick_widgets:
            if rnd.random() < 0.9:
                cb.setChecked(True)
        if page == "aimed" and rnd.random() < 0.9:
            sim.aim(win._last.detail["mark"])
        r = rnd.random()
        if r < 0.012:
            win._on_stop()
            continue
        if r < 0.02:
            win._on_problem()
            continue
        if r < 0.028 and win.popup() is not None:
            win.popup().reject()                     # Esc / close box
            continue
        cands = [b for b in win._buttons if b.isEnabled()]
        if win.popup() is not None:
            cands += [b for b in (win.popup().end_btn, win.popup().problem_btn)
                      if b.isVisibleTo(win.popup()) and b.isEnabled()]
        if not cands:
            win.reject()
            continue
        # mostly the forward answer the person script would give
        want = W.tr(p.script.get(page, "")) if page in p.script else None
        fw = [b for b in cands if want and b.text() == want]
        b = fw[0] if fw and rnd.random() < 0.94 else rnd.choice(cands)
        b.click()
    J_breaches = walk.breaches()
    moves = _moves(sim)
    print("seed", seed, "asking", asking, "moves", moves, "pages", len(pages),
          "last", pages[-3:])
    assert not J_breaches, (seed, J_breaches[:3], pages[-12:])
