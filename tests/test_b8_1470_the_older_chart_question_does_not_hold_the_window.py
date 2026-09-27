"""B8-1470 (beta 45 challenge 2, F1): B8-1460's older-chart question held
the window.

Reopening a beta 44 targen chart asked targen, with subprocess.run on the GUI
thread, whether the settings on screen make its patches: for Manual's
arguments AND Guided's even after Manual's said "makes", for every ordinary
beta 44 chart, and again in every session because the answer lived in memory
only. Measured on screen: frozen 0.4 s at 48 patches, 9.9 s at 2,000.

Now targen runs as a QProcess, stops at the first "makes", and the answer is
kept in the run's cache/ (never the chart's sidecar, which Restore Used Chart
compares by content). While it is out Generate and the live preview wait.
"""
import json
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QProcess, QSettings, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs import tab_chart as TC  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402

TARGEN = Path("/Applications/Argyll/bin/targen")
needs_targen = pytest.mark.skipif(not TARGEN.is_file(),
                                  reason="ArgyllCMS targen is not installed")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", False)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("argyll_bin_path", str(TARGEN.parent))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._manual_btn.setChecked(True)
    tab._switch_mode("manual")
    return tab


def _run_dir(tmp_path) -> Path:
    """A project's run folder, as the reopen finds a chart in."""
    proj = tmp_path / "Proj"
    run = proj / "runs" / "run1"
    run.mkdir(parents=True)
    (proj / "project.json").write_text("{}", encoding="utf-8")
    return run


def _targen(where: Path, stem, args):
    r = subprocess.run([str(TARGEN)] + list(args) + [stem], cwd=where,
                       capture_output=True, timeout=180,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr
    return where / f"{stem}.ti1"


def _own_chart(tab, where: Path, n=60):
    tab._manual_auto_patches_check.setChecked(True)
    p = tab._collect_params()
    p.patches = n
    tab._apply_auto_neutrals(p, use_estimate=True)
    return _targen(where, "own", TC._targen_args_for(p, n, "own")[:-1])


def _wait(tab, limit=60.0):
    t0 = time.monotonic()
    while tab._patch_set_question_pending() and time.monotonic() - t0 < limit:
        QApplication.processEvents()
        time.sleep(0.005)
    assert not tab._patch_set_question_pending(), "targen never answered"


def _show(tab, ti1):
    """What the reopen has done by the time it rebinds."""
    tab._current_ti1_path = ti1
    tab._preset_ti1_path = None


def _no_subprocess(monkeypatch):
    real = subprocess.run

    def refuse(cmd, *a, **k):
        if "targen" in str(cmd[0] if isinstance(cmd, (list, tuple)) else cmd):
            pytest.fail("targen was run on the GUI thread")
        return real(cmd, *a, **k)
    monkeypatch.setattr(subprocess, "run", refuse)


def _count_starts(monkeypatch):
    starts = []
    real = QProcess.start

    def start(self, prog, args=(), *a):
        starts.append((prog, list(args)))
        return real(self, prog, args, *a)
    monkeypatch.setattr(QProcess, "start", start)
    return starts


@needs_targen
def test_the_reopen_asks_without_holding_the_window(qapp, tmp_path,
                                                    monkeypatch):
    """The rebind returns at once with the question out; the event loop
    keeps running while targen works; the loaded set is bound when it
    answers."""
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    ti1 = _targen(_run_dir(tmp_path), "external", ["-d3", "-f200"])
    _no_subprocess(monkeypatch)
    _show(tab, ti1)
    tab._rebind_patch_set_from_run(ti1, given=None)
    assert tab._patch_set_question_pending()
    assert tab._preset_ti1_path is None          # not decided yet
    assert not tab._generate_btn.isEnabled()
    ticks = []

    def tick():
        ticks.append(1)
    t = QTimer()
    t.timeout.connect(tick)
    t.start(1)
    _wait(tab)
    t.stop()
    assert ticks, "the event loop did not run while targen was asked"
    assert tab._preset_ti1_path == ti1
    assert tab._generate_btn.isEnabled()
    tab.deleteLater()


@needs_targen
def test_it_stops_at_the_first_makes(qapp, tmp_path, monkeypatch):
    """Manual's arguments make ChromIQ's own chart, so Guided's are never
    asked: one targen, not two."""
    tab = _tab(tmp_path)
    ti1 = _own_chart(tab, _run_dir(tmp_path))
    starts = _count_starts(monkeypatch)
    _show(tab, ti1)
    tab._rebind_patch_set_from_run(ti1, given=None)
    _wait(tab)
    assert len(starts) == 1, starts
    assert tab._preset_ti1_path is None          # targen's own: unbound
    tab.deleteLater()


@needs_targen
def test_the_answer_is_kept_for_the_next_session(qapp, tmp_path,
                                                 monkeypatch):
    """Kept in the run's cache/, so a second tab (a new session) binds at
    once without running targen, and the chart's sidecar is untouched."""
    run = _run_dir(tmp_path)
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    ti1 = _targen(run, "external", ["-d3", "-f200"])
    sidecar = run / "external.channels.json"
    sidecar.write_text('{"create_chart_settings": {}}', encoding="utf-8")
    before = sidecar.read_bytes()
    _show(tab, ti1)
    tab._rebind_patch_set_from_run(ti1, given=None)
    _wait(tab)
    assert tab._preset_ti1_path == ti1
    kept = run / "cache" / TC._PATCH_SET_ORIGIN_FILE
    doc = json.loads(kept.read_text(encoding="utf-8"))
    assert doc and all(v is False for v in doc.values())
    assert sidecar.read_bytes() == before
    tab.deleteLater()

    fresh = _tab(tmp_path)
    fresh._manual_auto_patches_check.setChecked(True)
    starts = _count_starts(monkeypatch)
    _no_subprocess(monkeypatch)
    _show(fresh, ti1)
    fresh._rebind_patch_set_from_run(ti1, given=None)
    assert not fresh._patch_set_question_pending()
    assert starts == []
    assert fresh._preset_ti1_path == ti1
    fresh.deleteLater()


@needs_targen
def test_generate_and_the_live_preview_wait_for_the_answer(qapp, tmp_path,
                                                           monkeypatch):
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    ti1 = _targen(_run_dir(tmp_path), "external", ["-d3", "-f200"])
    _show(tab, ti1)
    tab._rebind_patch_set_from_run(ti1, given=None)
    assert tab._patch_set_question_pending()
    monkeypatch.setattr(tab, "_log_chart_build",
                        lambda *a: pytest.fail("a build started"))
    tab._on_generate()
    assert tab._generate_from_ti1(ti1, ask=False) is False
    tab._settings.set("auto_update_preview", True)
    # the preview's own wait, not only the greyed button it also reads
    # (`_chart_build_in_flight`): something else may enable Generate
    tab._generate_btn.setEnabled(True)
    monkeypatch.setattr(tab, "_layout_signature",
                        lambda: pytest.fail("the live preview went ahead"))
    tab._auto_regenerate_preview()
    monkeypatch.undo()
    _wait(tab)
    tab.deleteLater()


@needs_targen
def test_an_answer_for_a_chart_no_longer_shown_is_dropped(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._manual_auto_patches_check.setChecked(True)
    ti1 = _targen(_run_dir(tmp_path), "external", ["-d3", "-f200"])
    _show(tab, ti1)
    tab._rebind_patch_set_from_run(ti1, given=None)
    assert tab._patch_set_question_pending()
    tab._current_ti1_path = tmp_path / "another.ti1"
    _wait(tab)
    assert tab._preset_ti1_path is None
    tab.deleteLater()


def test_a_new_chart_cancels_the_question_still_out(qapp, tmp_path,
                                                    monkeypatch):
    """Showing another chart kills the old question and frees Generate."""
    tab = _tab(tmp_path)
    ti1 = tmp_path / "c.ti1"
    ti1.write_text(
        'CTI1\nORIGINATOR "Argyll targen"\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\nBEGIN_DATA\n"
        "1 1 2 3\nEND_DATA\n", encoding="utf-8")
    sleeper = tmp_path / "slow-targen"
    sleeper.write_text("#!/bin/sh\nsleep 30\n", encoding="utf-8")
    sleeper.chmod(0o755)
    monkeypatch.setattr(tab._runner, "resolve_tool", lambda _t: sleeper)
    _show(tab, ti1)
    tab._rebind_patch_set_from_run(ti1, given=None)
    assert tab._patch_set_question_pending()
    proc = tab._patch_set_q["proc"]
    other = tmp_path / "other.ti1"
    other.write_text('CTI1\nORIGINATOR "Somebody"\n', encoding="utf-8")
    _show(tab, other)
    tab._rebind_patch_set_from_run(other, given=None)
    assert not tab._patch_set_question_pending()
    assert proc.state() == QProcess.ProcessState.NotRunning
    assert tab._generate_btn.isEnabled()
    assert tab._preset_ti1_path == other         # not targen's: bound
    tab.deleteLater()


def test_could_not_say_is_not_kept(qapp, tmp_path, monkeypatch):
    run = _run_dir(tmp_path)
    tab = _tab(tmp_path)
    ti1 = run / "c.ti1"
    ti1.write_text(
        'CTI1\nORIGINATOR "Argyll targen"\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\nBEGIN_DATA\n"
        "1 1 2 3\nEND_DATA\n", encoding="utf-8")
    monkeypatch.setattr(tab._runner, "resolve_tool",
                        lambda _t: tmp_path / "no-such-targen")
    _show(tab, ti1)
    tab._rebind_patch_set_from_run(ti1, given=None)
    _wait(tab)
    assert tab._preset_ti1_path == ti1           # kept, and said so
    assert not (run / "cache" / TC._PATCH_SET_ORIGIN_FILE).exists()
    tab.deleteLater()


def test_the_answer_is_kept_only_beside_a_projects_chart(tmp_path):
    run = _run_dir(tmp_path)
    assert (TabChart._patch_set_origin_file(run / "x.ti1")
            == run / "cache" / TC._PATCH_SET_ORIGIN_FILE)
    loose = tmp_path / "loose"
    loose.mkdir()
    assert TabChart._patch_set_origin_file(loose / "x.ti1") is None


def test_a_redraw_of_an_unknown_older_chart_leaves_the_record_unsaid(
        tmp_path):
    """Restore Used Chart no longer runs targen; without a kept answer its
    new sidecar says nothing, so the reopen still asks."""
    from workflow.chart_creator import ChartCreator, ChartParams
    cc = ChartCreator.__new__(ChartCreator)
    p = ChartParams()
    p.patch_set_given = None
    cc._write_channel_sidecar(tmp_path, "c", p)
    doc = json.loads((tmp_path / "c.channels.json").read_text(encoding="utf-8"))
    assert "patch_set_given" not in doc


def test_the_reopen_never_calls_the_synchronous_question():
    """A guard on the shape: the reopen's older-record branch hands the
    question to `_ask_patch_set_origin` and returns."""
    import inspect
    src = inspect.getsource(TabChart._rebind_patch_set_from_run)
    assert "self._ask_patch_set_origin(ti1)" in src
    assert "_older_patch_set_verdict(" not in src
    assert "_targen_makes_this_patch_set(" not in src
