"""Item 71: what START and the refused aims say (words only; nothing is accepted or moved by them)."""
from __future__ import annotations

import math

import pytest

from tests.i1io_table import job_harness as H
from tests.i1io_table.test_dual_table import dual_setup
from tests.i1io_table.test_job_reading import job_for, small_sheet
from tests.i1io_table.test_job_safety import shaped_sheet
from tests.i1io_table.test_window_in_the_measure_tab import (  # noqa: F401 (fixtures)
    beta, start, tab, table_run)
from workflow import measurement_messages as M
from workflow.i1io.table import geometry as geo
from workflow.i1io.table import job as J
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp

MARKS = ((10.0, 10.0), (10.0, 198.0), (285.0, 198.0))     # sides 188 and 275 mm


def _aims(r1=1.0, r2=1.0, turn=0.0, at=(1300, 1400)):
    """p1 readings of MARKS on a sheet printed at r1 x r2 (table X runs to the left)."""
    P1 = at
    P2 = (at[0], at[1] + 1880 * r1)
    a = math.radians(turn)
    P3 = (P2[0] - 2750 * r2 * math.cos(a), P2[1] - 2750 * r2 * math.sin(a))
    return tuple((int(round(x)), int(round(y))) for x, y in (P1, P2, P3))


# ---- the scaled print --------------------------------------------------------------------------

@pytest.mark.parametrize("r1,r2,percent", [
    (0.965, 0.973, 97), (0.967, 0.970, 97), (0.972, 0.968, 97), (0.95, 0.955, 95),
    (1.03, 1.031, 103), (0.93, 0.93, 93)])
def test_a_scaled_print_is_named_and_still_refused(r1, r2, percent):
    aims = _aims(r1, r2)
    assert geo.print_scale_hint(MARKS, aims) == percent
    with pytest.raises(geo.AlignmentRefused):
        geo.fit_model(MARKS, aims)


@pytest.mark.parametrize("r1,r2,turn,why", [
    (1.0, 1.0, 0.0, "printed right"), (0.99, 0.99, 0.0, "inside a hand aim"),
    (0.97, 1.03, 0.0, "opposite ways"), (0.97, 0.94, 0.0, "not the same"),
    (0.97, 0.97, 1.6, "the corner is off"), (0.90, 0.90, 0.0, "further than a print"),
    (0.97, 1.0, 0.0, "one side: a wrong cross"), (1.0, 0.95, 0.0, "one side")])
def test_anything_else_is_no_scaled_print(r1, r2, turn, why):
    assert geo.print_scale_hint(MARKS, _aims(r1, r2, turn)) is None, why


def test_no_scale_is_ever_accepted():
    """The refusal is the released one at every scale the hint can name."""
    for k in range(920, 1081):
        r = k / 1000.0
        if geo.print_scale_hint(MARKS, _aims(r, r)) is not None:
            with pytest.raises(geo.AlignmentRefused):
                geo.fit_model(MARKS, _aims(r, r))


def test_the_refused_page_says_the_percent_and_that_it_is_not_accepted(tmp_path):
    from ui.i1io_table_window import reason_text
    sheet = small_sheet()
    marks = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    good = H.demo_aims(sheet)
    P2 = good[1]
    scaled = [tuple(int(round(P2[i] + 0.97 * (p[i] - P2[i]))) for i in (0, 1)) for p in good]
    assert geo.print_scale_hint(marks, scaled) == 97
    job, sim, helper, run, p = job_for(tmp_path, sheet=sheet)
    sim.aims = list(scaled)
    for s in ("open", "calibrate"):
        assert p.drive(getattr(job, s)()).ok
    n = len(sim.received)
    r = p.drive(job.align())
    assert r.kind == J.Kind.REFUSED and r.reason.startswith("aims_distance"), (r.kind, r.reason)
    assert r.detail["scaled_percent"] == 97
    text = reason_text(r.reason, dict(r.detail))
    assert "97 %" in text and "not at 100 %" in text and "does not accept it" in text
    assert "“Next step”" in text and "you aimed at another point at least once." in text
    assert job.alignment is None
    assert not [ln for ln in sim.received[n:] if ln.startswith(";m2")]


# ---- the dual scan on a chart too short for it ---------------------------------------------------

@pytest.mark.parametrize("along", [7.0, 8.0, 8.9, 9.0, 9.5, 10.0, 10.6, 12.0])
def test_start_counts_the_rows_the_planner_refuses(along):
    sheet = shaped_sheet([20, 20], along=along, across=10.0, w=210.0, h=297.0)
    marks = [tuple(sc.sheet_table_mm(sheet, a["page_mm"])) for a in sc.aims_of(sheet, 0)]
    al = geo.fit_alignment(marks, H.demo_aims(sheet))
    refused = 0
    for k in range(2):
        try:
            sp.plan_dual_row(sheet, 0, k, al, 3000)
        except sp.RowRefused as exc:
            refused += 20 * (exc.reason == "dual_row_patches_too_short")
    assert sp.dual_rows_too_short(sheet) == refused
    locs = {q["loc"] for q in sheet["pages"][0]["strips"][0]["patches"][:5]}
    assert sp.dual_rows_too_short(sheet, locs) == (5 if refused else 0)


def test_the_minutes_come_from_the_measured_pace():
    from ui.i1io_table_window import dual_patch_by_patch_minutes as minutes
    assert sp.DUAL_SPOT_PATCH_S == (2.6, 3.1)
    full = shaped_sheet([22] * 29, along=8.0, across=7.0, w=210.0, h=297.0)
    assert minutes(full) == (638, 28, 33)
    assert minutes(shaped_sheet([22] * 3, along=8.0)) is None           # a few patches
    assert minutes(shaped_sheet([22] * 29, along=10.6)) is None         # read as strips
    assert minutes({"pages": None}) is None                             # never in the way


class _Box:
    """QMessageBox.exec answered: the button whose text is *answer*."""
    def __init__(self, monkeypatch, answer):
        from PyQt6.QtWidgets import QMessageBox
        self.seen, me = [], self

        def run(box):
            me.seen.append((box.text(), box.informativeText(), [b.text() for b in box.buttons()],
                            box.defaultButton().text()))
            box._answer = next(b for b in box.buttons() if b.text() == answer)
        monkeypatch.setattr(QMessageBox, "exec", run)
        monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: box._answer)


SHORT = shaped_sheet([22] * 29, along=8.0, across=7.0, w=210.0, h=297.0)


@pytest.mark.parametrize("answer,goes", [("Read it patch by patch", True), ("Not now", False)])
def test_the_question_at_start(tab, monkeypatch, answer, goes):  # noqa: F811
    box = _Box(monkeypatch, answer)
    assert tab._confirm_dual_patch_by_patch(SHORT, None, ["-v", "chart"]) is goes
    title, body, buttons, default = box.seen[0]
    assert (title, body) == M.M_I1IO_DRIVE_DUAL_SPOT_WHOLE.render(n=638, low=28, high=33)
    assert default == "Not now" and set(buttons) == {"Read it patch by patch", "Not now"}
    assert "28 to 33 minutes" in body


def test_it_is_not_asked_when_it_says_nothing_new(tab, monkeypatch):  # noqa: F811
    box = _Box(monkeypatch, "Not now")
    assert tab._confirm_dual_patch_by_patch(SHORT, None, ["-v", "-p", "chart"])
    assert tab._confirm_dual_patch_by_patch(
        shaped_sheet([22] * 29, along=10.6), None, ["-v", "chart"])
    assert box.seen == []


@pytest.mark.parametrize("dual", [True, False])
def test_not_now_opens_nothing_and_writes_nothing(tab, beta, tmp_path, monkeypatch,  # noqa: F811
                                                  qtbot, dual):
    run, sheet = table_run(tmp_path)
    monkeypatch.setattr(tab, "_table_dual_setup", lambda: dual_setup("M1") if dual else None)
    asked, saved = [], []
    monkeypatch.setattr(tab, "_confirm_dual_patch_by_patch",
                        lambda *a: asked.append(a) or False)
    monkeypatch.setattr(tab, "save_target_settings", lambda *a, **k: saved.append(1))
    sim = start(tab, run, monkeypatch)
    if dual:
        assert len(asked) == 1 and getattr(tab, "_table_window", None) is None and sim.jobs == [] and saved == []
    else:
        assert asked == [] and tab._table_window is not None      # no dual scan: never asked


# ---- what is said now ------------------------------------------------------------------------

def test_the_compact_text_is_true_and_modest():
    body = M.M_I1IO_COMPACT_INFO.body
    assert "simulated" not in body and "one real table" in body and "without the dual scan" in body
    assert "takes much longer" in body


def test_the_beta_help_says_what_was_read():
    from ui.dialogs.settings_dialog import i1io_support_help, i1io_table_pbp_help
    text = i1io_support_help()
    assert "has not yet run on a real table" not in text and "whole sheets" in text
    assert "sheets cut into pieces" in text and "Other tables have not been tried yet." in text
    assert "has not been tried on a real table yet" not in i1io_table_pbp_help()


def test_the_countdown_before_the_repair_says_what_was_found_and_what_moves():
    body = M.M_I1IO_DRIVE_REPAIR_COUNTDOWN.body
    assert body.startswith("ChromIQ found the table in its aiming mode")
    assert "moves the arm a little and back to its resting place" in body
    assert "earlier measurement" not in body


def test_the_countdown_page_says_what_was_found_and_what_moves(qtbot, monkeypatch,
                                                              tmp_path):  # noqa: F811
    """Safety review 2, S5 (T30): on the page itself, guidance off, the arm at its resting place."""
    from core.settings import AppSettings
    from PyQt6.QtCore import QSettings
    from tests.i1io_table.test_window import open_window
    from tests.i1io_table.window_sim import WindowSim
    from ui import i1io_table_window as W
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    sim = WindowSim()
    real = sim.factory

    def factory(*a, **k):
        job = real(*a, **k)
        sim.sim.mode, sim.sim.a0_aiming, sim.sim.pos = "01", "530000", [1102.0, 36.0]
        return job
    sim.factory = factory
    pages = []
    orig = W.TableMeasureWindow._show

    def show(self, page, title, body, *a, **k):
        pages.append((page, title, body))
        return orig(self, page, title, body, *a, **k)
    monkeypatch.setattr(W.TableMeasureWindow, "_show", show)
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, st,
                                                    guided=False, sim=sim)
    p.drive_until("aimed")
    shown = [(t, b) for page, t, b in pages if page == "countdown"]
    assert shown
    title, body = shown[0]
    assert title == M.M_I1IO_DRIVE_REPAIR_COUNTDOWN.title
    assert body.startswith(M.M_I1IO_DRIVE_REPAIR_COUNTDOWN.body)
    assert "Please keep your hands away" in body and "The arm moves in" in body


def test_no_text_says_untried_what_a_real_table_has_done():
    """Safety review 2, S3 / S4: what is proven, and no more; "not tried" stays where it is true."""
    from ui.dialogs.layout_options_panel import i1io_layout_help
    for m in (M.M_I1IO_DRIVE_AIM_BUTTON, M.M_I1IO_DRIVE_AIM_BUTTON_PATCH,
              M.M_I1IO_DRIVE_STRIP_OPTION, M.M_I1IO_DRIVE_STRIP_FIRST_TRY,
              M.M_I1IO_DRIVE_DUAL_ROWS):
        assert "not been tried on a real table" not in m.body, m.id
        assert ("on one real table so far" in m.body
                or "only one real table" in m.body), m.id
    assert "has not been tried on a table yet" not in " ".join(i1io_layout_help().split())
    assert "patch by patch is not yet tried to the end" in M.M_DUAL_BEFORE_START_TABLE.body
    assert "only patches of 8 mm, on one table" in M._I1IO_SHORT_PATCH
    con = M.M_I1IO_DRIVE_CONSENT.body
    assert "Not tried on a real table yet: the dual scan patch by patch to the end, sheets cut " \
        "into pieces, and what happens at the end of the arm's range of movement." in con
    # still true
    assert "not been tried on a real table yet" in M.M_I1IO_DRIVE_DUAL_SPOT.body
    assert "simulated table only" in M._I1IO_PIECES_INFO
    assert "have not been tried on a table yet" in M._I1IO_THIN_SPACER
