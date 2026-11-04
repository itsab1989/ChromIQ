"""4.3.24, review of #214 (Q4): a layout engine failure reaches a window.

`ChartCreator._run_engine` caught every exception, wrote it to the log and
ended with an empty preview: no window at all. Found on an FD-9 chart in
4.3.23 whose wider gap made a fixed patch count need a second sheet, but the
path is every engine chart's. Only a printer calibration for other inks had
its own words (`test_a_calibration_must_be_for_the_charts_inks.py`); every
other refusal now gets M-CHART-ENGINE-FAILED, with the engine's sentence as
the technical reason.
"""
from __future__ import annotations


def _creator(tmp_path):
    from workflow.chart_creator import ChartCreator
    from tests.test_chart_creator_engine import (_EngineRunner, _EngineSettings,
                                                 _MockFileManager)
    fm = _MockFileManager(tmp_path / "proj")
    return ChartCreator(_EngineRunner(), fm, _EngineSettings()), fm


def test_any_engine_refusal_becomes_a_window_text(tmp_path, monkeypatch):
    from workflow.chart_creator import ChartParams
    from workflow.layout_engine import chart as le_chart
    from workflow import measurement_messages as M
    creator, fm = _creator(tmp_path)
    work = fm.cwd_for_chart(cal_target=False)
    monkeypatch.setattr(creator, "_engine_kwargs",
                        lambda p: {"instrument": "i1", "paper": "A4"})

    def refuse(*_a, **_k):
        raise ValueError("FD-9 patch gap must be 0..5 mm")
    monkeypatch.setattr(le_chart, "build_chart", refuse)
    lines: list[str] = []
    creator._run_engine(ChartParams(instrument="i1", paper="A4"), work,
                        lines.append)
    failure = creator.primary_failure()
    assert failure is not None, "the refusal reached the log only"
    tool, key, text = failure
    assert (tool, key) == ("engine", "engine_failed")
    assert text == M.M_CHART_ENGINE_FAILED.render(
        reason="FD-9 patch gap must be 0..5 mm")[1]
    assert any("[ERROR] ChromIQ layout engine:" in ln for ln in lines)


def test_the_window_takes_the_catalogue_headline(qapp, qtbot, tmp_path,
                                                 monkeypatch):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs import tab_chart
    from workflow import measurement_messages as M
    settings = AppSettings()
    settings._qs = QSettings(str(tmp_path / "i.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(tmp_path / "projects"))
    tab = tab_chart.TabChart(ArgyllRunner(settings), FileManager(settings),
                             settings)
    qtbot.addWidget(tab)
    body = M.M_CHART_ENGINE_FAILED.render(reason="refused")[1]
    tab._creator._matched_errors = [("engine", "engine_failed", body)]
    shown = []

    class Window:
        def __init__(self, title, text, *a, **k):
            shown.append((title, text))

        def exec(self):
            return 0
    monkeypatch.setattr(tab_chart, "InfoDialog", Window)
    tab._on_generate_finished([])
    assert shown == [(M.M_CHART_ENGINE_FAILED.render(reason="")[0], body)]
