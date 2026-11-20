"""The owner's decision of 2026-11-18 (D-4b): "i guess the tables value because this is more
automated and matches closer". A table measurement uses the white tile values stored in the
table by default, as i1Profiler does; switched off in Preferences > Beta it uses the i1Pro 2's
own reference, as by hand; values that cannot be used are said plainly and the measurement goes
on with the instrument's own; the first page and the log name the reference; Beta off and the
hand path never touch any of it."""
from __future__ import annotations

import inspect
from pathlib import Path

from tests.i1io_table.test_window import open_window, settings  # noqa: F401
from tests.i1io_table.window_sim import WindowSim
from ui import i1io_table_window as W

ROOT = Path(__file__).resolve().parents[2]


def test_the_default_is_on_and_a_fresh_settings_file_gives_on(tmp_path):
    from core import settings as S
    assert S.DEFAULTS[W.STORED_WHITE_KEY] is True

    class Fresh:
        def get(self, key, default=None):
            return S.DEFAULTS.get(key, default)
    assert W.stored_tile_white(Fresh()) is True

    class Empty:
        def get(self, key, default=None):
            return default
    assert W.stored_tile_white(Empty()) is True


def _first_page_and_log(qtbot, monkeypatch, tmp_path, settings, sim=None):
    win, sim, run, p, saved, finished = open_window(qtbot, monkeypatch, tmp_path, settings,
                                                    asking=False, sim=sim)
    first = win._text.text() if p.page() == "prepare" else ""
    p.script["stored_white_refused"] = "Go on"
    pages = []
    for _ in range(60):
        page = p.page()
        pages.append(page)
        if page == "sheet_laid":
            break
        p.answer_page(page)
    log = run.i1io_table_log(win._stamp).read_text(encoding="utf-8")
    return first, pages, log, sim


def test_on_by_default_named_on_the_first_page_and_in_the_log(qtbot, monkeypatch, tmp_path,
                                                              settings):
    settings.set(W.STORED_WHITE_KEY, True)
    first, pages, log, sim = _first_page_and_log(qtbot, monkeypatch, tmp_path, settings)
    assert "White reference: the values the table keeps for its white tile" in first
    assert "stored_white_refused" not in pages
    assert "white reference: the table's stored white tile values" in log
    assert sim.jobs[0].white_scale is not None


def test_off_is_honoured(qtbot, monkeypatch, tmp_path, settings):
    settings.set(W.STORED_WHITE_KEY, False)
    try:
        first, pages, log, sim = _first_page_and_log(qtbot, monkeypatch, tmp_path, settings)
    finally:
        settings.set(W.STORED_WHITE_KEY, True)
    assert "White reference: the i1Pro 2's own" in first
    assert "white reference: the i1Pro 2's own" in log
    assert sim.jobs[0].white_scale is None and sim.jobs[0].tile_readings == []


def test_values_that_cannot_be_used_are_said_and_the_own_reference_is_used(qtbot, monkeypatch,
                                                                           tmp_path, settings):
    settings.set(W.STORED_WHITE_KEY, True)
    first, pages, log, sim = _first_page_and_log(qtbot, monkeypatch, tmp_path, settings,
                                                 sim=WindowSim(stored_tile=None))
    assert "stored_white_refused" in pages
    assert "white reference: the i1Pro 2's own" in log
    assert sim.jobs[0].white_scale is None


def test_the_hand_path_never_uses_the_stored_values():
    """Only the table's own code reads the option or scales by it."""
    hits = []
    for base in ("core", "ui", "workflow"):
        for p in (ROOT / base).rglob("*.py"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            if W.STORED_WHITE_KEY in text or "white_scale" in text:
                hits.append(p.relative_to(ROOT).as_posix())
    # core/beta_registry.py (4.3.50, A1): the app log's session header NAMES the option's
    # state; it reads it for the log only and scales nothing
    allowed = {"core/settings.py", "ui/i1io_table_window.py", "ui/dialogs/settings_dialog.py",
               "core/beta_registry.py"}
    assert {h for h in hits if not h.startswith("workflow/i1io/table/")} <= allowed, hits


def test_the_job_itself_stays_off_unless_told():
    from workflow.i1io.table import job as J
    sig = inspect.signature(J.TableJob.__init__)
    assert sig.parameters["stored_tile_white"].default is False
