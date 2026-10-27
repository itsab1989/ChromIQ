"""The turned i1Profiler export describes the chart that STAYS on disk (beta;
review 4.3.17 r1, S7).

Create Chart wrote it beside the other sidecars, before the auto-tag and before
the rebuild guard. Restore Used Chart redraws the pages under that guard, and
the guard then puts the run's own .ti2 back (always: even a faithful redraw
stamps a new CREATED line). So the order file named the SHA-256 of a .ti2 that
no longer existed, and the run's turned measurement could never be brought
back. Driven here through `TabChart._on_generate_finished`, the funnel every
build reaches.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import i1profiler_turned as T               # noqa: E402

from tests.test_i1profiler_turned_export import _chart    # noqa: E402


def _tab_on_a_run(tmp_path, *, on: bool):
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    out = tmp_path / "ChromIQ"
    out.mkdir()
    s.set("custom_output_path", str(out))
    s.set("i1profiler_turned_export", on)
    fm = FileManager(s)
    run = Project.create(out / "R", "R").current_run()
    run.ensure_dir()
    fm.set_target_name("R")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1")
    src = _chart(tmp_path / "src", "Src", 350)
    for f in src.parent.iterdir():
        if f.is_file():
            shutil.copy2(f, run.dir / ("R" + f.name[len("Src"):]))
    tif = run.dir / "R.tif"
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    return tab, run, tif


def _finish(tab, tif, monkeypatch):
    monkeypatch.setattr("ui.tabs.tab_chart.InfoDialog",
                        lambda *a, **kw: type("D", (), {"exec": lambda s: 0})())
    monkeypatch.setattr(type(tab), "_warn_no_control_strip",
                        lambda self, n: None)
    tab._on_generate_finished([tif])


@pytest.mark.parametrize("relaid", [False, True])
def test_after_restore_used_chart_the_order_names_the_chart_on_disk(
        qapp, tmp_path, monkeypatch, relaid):
    """*relaid*: the redraw changed the chart itself (the guard warns), or
    only its CREATED stamp (routine). Either way the .ti2 that stays is the
    held one, and the turned order must be the order OF that one."""
    from ui.tabs.tab_chart import _ChartRebuildGuard
    tab, run, tif = _tab_on_a_run(tmp_path, on=True)
    held = run.chart_ti2.read_bytes()
    tab._rebuild_guard = _ChartRebuildGuard(run.chart_ti2)
    # the redraw writes another .ti2
    text = held.decode("utf-8")
    import re
    redrawn = re.sub(r'^CREATED ".*"$', 'CREATED "Wed Oct 28 09:00:00 2026"',
                     text, count=1, flags=re.M)
    if relaid:
        redrawn = redrawn.replace('DESCRIPTOR "', 'DESCRIPTOR "redrawn ', 1)
    run.chart_ti2.write_text(redrawn, encoding="utf-8")
    assert run.chart_ti2.read_bytes() != held
    _finish(tab, tif, monkeypatch)
    assert run.chart_ti2.read_bytes() == held, "the guard did not put it back"
    order = T.turned_order_for(run.chart_ti2)
    assert order is not None, (
        "the turned order was written for the redrawn bytes the guard then "
        "replaced, so it names no chart on disk")
    assert order.path.parent == run.exports_dir


def test_a_plain_build_writes_it_too(qapp, tmp_path, monkeypatch):
    tab, run, tif = _tab_on_a_run(tmp_path, on=True)
    _finish(tab, tif, monkeypatch)
    assert T.turned_order_for(run.chart_ti2) is not None


def test_with_the_option_off_the_build_writes_none(qapp, tmp_path, monkeypatch):
    tab, run, tif = _tab_on_a_run(tmp_path, on=False)
    _finish(tab, tif, monkeypatch)
    assert not any("turned" in p.name for p in run.exports_dir.iterdir())


def test_it_is_written_after_the_guard_is_released():
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_generate_finished)
    at = src.index("self._write_turned_i1profiler_export(ti2, stem)")
    assert src.index("self._release_rebuild_guard()") < at
    assert src.index("self._maybe_autotag_randomised(ti2)") < at
    assert src.count("self._write_turned_i1profiler_export(") == 1
