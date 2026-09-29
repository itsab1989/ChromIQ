"""B8-860: a chart built from a .ti1 through printtarg must FINISH, and under
Run type = Verification it must not touch the run's profiling work.

Tester A, beta 39: fresh session, Run 1, Verification, Create Chart > FROM
PROFILE GAMUT, Generate. printtarg ran in 0.2 s and then nothing: Generate
greyed, Stop showing, no preview, for minutes. The run root now held the gamut
chart as the PROFILING chart and the run's profile and measurement were in
``old/``. A Manual Generate earlier in the session made the same build work.

The cause: since 93ba45ee every ending of a build goes through
``ChartCreator._finish``, which calls ``_pending_on_finish`` rather than the
callback handed in, and the printtarg branch of
``load_ti1_and_generate_preview`` never stored it. So the tab's finish handler
(which files a verification chart into ``verifications/`` and puts the
profiling chart back) never ran on a first build, and on a later one the
previous build's callback ran in its place.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import pytest
import tifffile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.argyll_runner import ArgyllRunner               # noqa: E402
from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import RUN_TYPE_VERIFICATION  # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from workflow import gamut_target as gt                   # noqa: E402
from workflow.chart_creator import ChartCreator, ChartParams  # noqa: E402


class _SyncRunner:
    """Stages what printtarg writes, then reports exit 0 at once."""

    is_running = False

    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, tool, args, cwd, on_line=None, on_finish=None):
        self.calls.append(tool)
        cwd = Path(cwd)
        stem = args[-1]
        if tool == "printtarg":
            (cwd / f"{stem}.ti2").write_text("NEW TI2", encoding="utf-8")
            tifffile.imwrite(str(cwd / f"{stem}_01.tif"),
                             np.full((40, 40, 3), 200, dtype=np.uint8),
                             resolution=(200, 200), resolutionunit="INCH")
        if on_finish:
            on_finish(0)

    def abort(self):
        pass


class _Settings:
    def get(self, key, default=None):
        return default


class _FM:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._project = None

    def project(self):
        if self._project is None:
            self._project = Project.create(self.root, self.root.name)
        return self._project

    def chart_stem(self, *, cal_target: bool) -> str:
        return self.project().current_run().stem


def _creator(tmp_path: Path) -> tuple[ChartCreator, Path]:
    fm = _FM(tmp_path / "P")
    creator = ChartCreator(_SyncRunner(), fm, _Settings())
    src = tmp_path / "in.ti1"
    src.write_text("FAKE TI1", encoding="utf-8")
    return creator, src


def _manual() -> ChartParams:
    # Manual with no engine setting stored: the printtarg branch.
    return ChartParams(target_name="P", device_type="2", is_manual=True)


def test_a_first_printtarg_build_from_a_ti1_reports_that_it_finished(tmp_path):
    """The first build of a session: nothing has set ``_pending_on_finish``
    before, and the callback handed in must still be called, exactly once,
    with the pages printtarg wrote.

    Mutation: delete ``self._pending_on_finish = on_finish`` from
    ``load_ti1_and_generate_preview`` and this fails with no call at all,
    which is the frozen tab tester A photographed."""
    creator, src = _creator(tmp_path)
    assert creator._pending_on_finish is None        # a fresh session
    got: list = []
    creator.load_ti1_and_generate_preview(
        src, _manual(), on_line=lambda _l: None, on_finish=got.append)
    assert creator._runner.calls == ["printtarg"]
    assert len(got) == 1, "the build finished and nobody was told"
    assert got[0] and all(Path(t).exists() for t in got[0])


def test_the_callbacks_are_this_builds_before_printtarg_starts(tmp_path):
    """Both callbacks are stored before the tool is launched, so nothing in
    between can still see the previous build's.

    Mutation: delete either assignment (``_pending_on_finish`` or
    ``_pending_on_line``) from the top of ``load_ti1_and_generate_preview``."""
    creator, src = _creator(tmp_path)
    seen = {}

    class _Holding(_SyncRunner):
        def run(self, tool, args, cwd, on_line=None, on_finish=None):
            seen["finish"] = creator._pending_on_finish
            seen["line"] = creator._pending_on_line

    creator._runner = _Holding()

    def fin(_t):
        pass

    def line(_l):
        pass

    creator.load_ti1_and_generate_preview(src, _manual(), on_line=line,
                                          on_finish=fin)
    assert seen["finish"] is fin
    assert seen["line"] is line


def test_a_previous_builds_callback_is_never_invoked(tmp_path):
    """A build earlier in the session left its own callbacks behind. The next
    printtarg build from a .ti1 must call ITS callback and never the old one.

    Mutation: delete ``self._pending_on_finish = on_finish`` from
    ``load_ti1_and_generate_preview``: the stale callback is the one called,
    which is how a Manual Generate first made tester A's FPG build 'work'."""
    creator, src = _creator(tmp_path)
    stale: list = []
    first: list = []
    creator.generate(_manual(), on_line=lambda _l: None,
                     on_finish=lambda t: first.append(t))
    assert first, "the priming build should have finished"
    creator._pending_on_finish = stale.append     # what a previous build left
    creator._pending_on_line = lambda _l: stale.append("line")
    fresh: list = []
    creator.load_ti1_and_generate_preview(
        src, _manual(), on_line=lambda _l: None, on_finish=fresh.append)
    assert len(fresh) == 1
    assert stale == [], "the previous build's callback was invoked"


def test_a_stop_left_over_from_the_last_build_does_not_cancel_this_one(tmp_path):
    """``_cancelling`` from a Stop pressed after a build had already ended must
    not turn the next build into a cancel (which would put the old chart back
    and report nothing built).

    Mutation: delete ``self._cancelling = False`` from the top of
    ``load_ti1_and_generate_preview``."""
    creator, src = _creator(tmp_path)
    creator.cancel()                        # idle: the flag is simply left set
    got: list = []
    creator.load_ti1_and_generate_preview(
        src, _manual(), on_line=lambda _l: None, on_finish=got.append)
    assert got and got[0], "a leftover Stop cancelled a build nobody stopped"


# ---------------------------------------------------------------------------
# The tab, end to end: FROM PROFILE GAMUT under Run type = Verification
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _profiled_project(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("use_chromiq_layout_engine", False)      # the printtarg branch
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    run = Project.create(tmp_path / "P", "P").current_run()
    run.ensure_dir()
    fm.set_target_name("P")
    # A finished profiling run: its chart, its measurement and its profile.
    run.chart_ti1.write_text("PROFILING TI1", encoding="utf-8")
    run.chart_ti2.write_text("PROFILING TI2", encoding="utf-8")
    tifffile.imwrite(str(run.dir / f"{run.stem}_01.tif"),
                     np.zeros((30, 30, 3), dtype=np.uint8),
                     resolution=(200, 200), resolutionunit="INCH")
    run.artefact(".ti3").write_text("PROFILING TI3", encoding="utf-8")
    run.profile_icc.write_bytes(b"PROFILING ICC")
    from ui.measurement_target_bar import MeasurementTargetController
    return s, fm, MeasurementTargetController(fm), run


def _fake_select(profile, count, margin, intent, **kw):
    sel = gt.GamutSelection(
        master_version="TEST-r0", master_total=10, in_gamut_total=4,
        requested=count, intent=intent, margin=margin)
    sel.targets = [(i, (50.0, 0.0, 0.0), (10.0 * i, 20.0, 30.0))
                   for i in range(4)]
    sel.corners = list(zip(gt.CORNER_DEVICES, gt.CORNER_DEVICES))
    return sel


def _profiling_hashes(run) -> dict:
    names = [run.chart_ti1, run.chart_ti2, run.dir / f"{run.stem}_01.tif",
             run.artefact(".ti3"), run.profile_icc]
    return {p.name: _sha(p) for p in names}


def test_fpg_under_verification_files_its_chart_and_leaves_the_run_alone(
        qapp, tmp_path, monkeypatch):
    """Tester A's steps, on the tab: a first build in the session, FROM
    PROFILE GAMUT, Run type = Verification. The new chart lands in
    ``verifications/``; the profiling chart, the profiling ``.ti3`` and the
    profile are byte-identical afterwards; nothing is put into the run's
    ``old/``; and Generate is usable again.

    Mutations: (1) delete ``self._pending_on_finish = on_finish`` from
    ``load_ti1_and_generate_preview`` and the verify chart never appears while
    the run root holds the gamut chart; (2) drop
    ``keep_results=self._is_verification_target()`` from
    ``_generate_from_ti1`` and the run gains an ``old/`` holding copies of the
    profile and the measurement it never lost."""
    s, fm, ctl, run = _profiled_project(tmp_path)
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("gamut")
    monkeypatch.setattr("workflow.gamut_target.select_gamut_targets",
                        _fake_select)
    tab._creator._runner = _SyncRunner()
    # The fake chart declares no control strip; its notice is not under test.
    monkeypatch.setattr(type(tab), "_warn_no_control_strip",
                        lambda self, *a, **k: None)
    assert tab._creator._pending_on_finish is None     # first build
    before = _profiling_hashes(run)

    tab._gamut_count_spin.setValue(100)
    tab._on_generate()

    assert tab._creator._runner.calls == ["printtarg"]
    assert run.verify_chart_ti2.exists(), "the chart was never filed"
    assert run.verify_chart_ti2.read_text(encoding="utf-8") == "NEW TI2"
    assert _profiling_hashes(run) == before, "the profiling run was changed"
    assert not (run.dir / "old").exists(), (
        "a verification chart put the run's profiling work into old/")
    assert tab._generate_btn.isEnabled(), "the tab never came back"


def test_a_manual_verification_generate_leaves_the_run_alone_too(
        qapp, tmp_path, monkeypatch):
    """The control case: the ordinary Generate (targen, then printtarg) under
    Run type = Verification, which FROM PROFILE GAMUT is now the same as. The
    chart is filed into ``verifications/`` and the profiling files are
    byte-identical, with no ``old/`` in the run.

    Mutation: drop ``keep_results=self._is_verification_target()`` from the
    ``self._creator.generate(...)`` call in ``_on_generate`` and the run gains
    an ``old/`` holding a copy of its profile and measurement on every build."""
    s, fm, ctl, run = _profiled_project(tmp_path)
    from ui.tabs.tab_chart import TabChart
    tab = TabChart(ArgyllRunner(s), fm, s, None)
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    tab._switch_mode("manual")

    class _WithTargen(_SyncRunner):
        def run(self, tool, args, cwd, on_line=None, on_finish=None):
            if tool == "targen":
                (Path(cwd) / f"{args[-1]}.ti1").write_text(
                    "NEW TI1", encoding="utf-8")
            super().run(tool, args, cwd, on_line, on_finish)

    tab._creator._runner = _WithTargen()
    monkeypatch.setattr(type(tab), "_warn_no_control_strip",
                        lambda self, *a, **k: None)
    before = _profiling_hashes(run)
    # Whatever preset the Manual panel opened on may carry a patch set of its
    # own; this case is the fresh targen chart, so none is attached.
    tab._preset_ti1_path = None

    tab._on_generate()

    assert tab._creator._runner.calls == ["targen", "printtarg"]
    assert run.verify_chart_ti2.read_text(encoding="utf-8") == "NEW TI2"
    assert _profiling_hashes(run) == before
    assert not (run.dir / "old").exists()
