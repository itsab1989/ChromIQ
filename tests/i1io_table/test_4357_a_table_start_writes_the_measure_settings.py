"""4.3.57 (item 35): a TABLE START writes the Measure tab's settings, as a hand START does.

docs/design/per_target_settings.md §3, W8: "Start Measurement / Continue Measurement pressed"
writes the Measure tab's settings for the target. The hand path does it in ``_on_start``; the
table path (``_started_the_table_drive``) returned before that line, so a tick changed and then
used for a table START was never stored, and the next load put the old value back (found from
the table owner's dual scan tries, 22 Nov 2026). Code against spec; the spec is unchanged.
"""
from __future__ import annotations

from tests.i1io_table.test_window_in_the_measure_tab import (  # noqa: F401 - fixtures
    beta, start, tab, table_run)


def test_a_table_start_writes_the_settings_before_the_window_opens(tab, beta, tmp_path,
                                                                   monkeypatch):
    calls = []
    monkeypatch.setattr(tab, "save_target_settings",
                        lambda *a, **k: calls.append(getattr(tab, "_table_window", None)))
    run, _sheet = table_run(tmp_path)
    start(tab, run, monkeypatch)
    assert tab._table_window is not None            # the table answered this START
    assert calls == [None], "W8: written once, before the table window existed"


def test_a_table_start_cancelled_at_the_replace_question_writes_nothing(tab, beta, tmp_path,
                                                                        monkeypatch):
    calls = []
    monkeypatch.setattr(tab, "save_target_settings", lambda *a, **k: calls.append(1))
    monkeypatch.setattr(tab, "_confirm_replacing_measurement", lambda: False)
    run, _sheet = table_run(tmp_path)
    start(tab, run, monkeypatch)
    assert getattr(tab, "_table_window", None) is None
    assert calls == [], "as on the hand path, a START cancelled by a question writes nothing"


def test_the_written_settings_are_the_ones_the_table_start_ran_with(tab, beta, tmp_path,
                                                                    monkeypatch):
    """The real write, end to end: the Measure tab's snapshot at the table START lands in the
    target's store (the store a later load reads), with a tick changed just before it."""
    from types import SimpleNamespace
    from workflow.measure_settings import snapshot
    run, _sheet = table_run(tmp_path)
    meta = SimpleNamespace(measure_settings={})
    saved = []
    store = SimpleNamespace(dir=str(tmp_path), id="table-target",
                            load_meta=lambda: meta, save_meta=lambda m: saved.append(
                                dict(m.measure_settings)))
    monkeypatch.setattr("workflow.per_target_settings.store_for_target", lambda _ctl: store)
    import ui.i1io_table_window as W
    real_init = W.TableMeasureWindow.__init__
    at_window = []

    def init(self, *a, **k):
        at_window.append(snapshot(tab))         # what the START runs with
        real_init(self, *a, **k)
    monkeypatch.setattr(W.TableMeasureWindow, "__init__", init)
    flipped = not tab._m_nocal_cb.isChecked()
    real_set = tab.set_ti1_path

    def set_then_change(path):
        real_set(path)
        tab._m_nocal_cb.setChecked(flipped)     # the person's tick, right before START
    monkeypatch.setattr(tab, "set_ti1_path", set_then_change)
    start(tab, run, monkeypatch)
    assert tab._table_window is not None
    assert saved, "nothing reached the target's store"
    assert saved[-1]["disable_initial_cal"]["value"] is flipped
    assert saved[-1] == at_window[0]
