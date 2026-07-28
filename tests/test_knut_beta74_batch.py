"""#131 (Knut, 2026-07-28), testing beta.74.

Three separate findings, and one of them turned out not to be a fault at all —
which is itself worth pinning down, because the *absence* of a bug is what his
three questions were really about.

1. **The windows-and-sounds ⓘ is on the wrong Settings tab.** *"Currently in
   preferences measurement tab, but should be moved to Sounds tab."*

2. **A measurement's painting outlives its chart.** He read one strip of a
   3-column chart, re-generated it with 4 columns, and the old strip stayed
   painted over the new layout — then followed him into every other profiling
   run he switched to.

3. **The vanishing checkboxes were correct, and unexplained.** Re-generating the
   chart archived the run's ``.ti3`` to ``old/``. With no measurement left in
   the run, "Refine / resume existing measurement" and "Show overlay from
   existing measurement" have nothing to act on, so they hide; the "this chart
   already has a measurement" window has nothing to announce, so it stays away.
   Every rule fired exactly as written — but nothing ever told him his
   measurement had been moved, so all he saw was controls disappearing.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication      # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- 1. the help icon sits with the sounds it explains --------------------
def test_the_windows_and_sounds_table_is_on_the_sounds_tab():
    from ui.dialogs.settings_dialog import SettingsDialog
    src = inspect.getsource(SettingsDialog._build_sounds_tab)
    assert "windows_and_sounds_html" in src
    assert "Which sound belongs to which window during a measurement:" in src


def test_it_is_no_longer_on_the_measurement_tab():
    from ui.dialogs.settings_dialog import SettingsDialog
    for name in dir(SettingsDialog):
        if not name.startswith("_build") or "sounds" in name:
            continue
        fn = getattr(SettingsDialog, name)
        if not callable(fn):
            continue
        try:
            src = inspect.getsource(fn)
        except (OSError, TypeError):
            continue
        assert "windows_and_sounds_html" not in src, (
            f"{name} still builds the windows-and-sounds row")


# ---- 2. a painting never outlives the chart it describes ------------------
def test_a_chart_change_discards_the_previous_painting():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._update_resume_availability)
    assert "_discard_stale_overlay()" in src
    # …before any of the branches, so the `no chart at all` path clears too.
    body = [l.strip() for l in src.splitlines()]
    discard_at = next(i for i, l in enumerate(body) if "_discard_stale_overlay" in l)
    branch_at = next(i for i, l in enumerate(body) if "self._ti1_path is None" in l)
    assert discard_at < branch_at


def test_it_clears_both_kinds_of_painting():
    """The static .ti3 overlay AND the live measured painting land on the same
    preview layer, which is why clearing that layer is the whole fix."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._discard_stale_overlay)
    assert "_clear_overlay()" in src


def test_it_never_wipes_a_measurement_in_progress():
    """The one time the painting is not stale: it is being drawn right now."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._discard_stale_overlay)
    assert "self._runner.is_running" in src
    lines = [l.strip() for l in src.splitlines()]
    guard = next(i for i, l in enumerate(lines) if "is_running" in l)
    clear = next(i for i, l in enumerate(lines) if "_clear_overlay()" in l)
    assert guard < clear, "the guard has to come first or it guards nothing"


class _Painted:
    """The three attributes the discard reads."""

    from ui.tabs.tab_measure import TabMeasure
    _discard_stale_overlay = TabMeasure._discard_stale_overlay
    _chart_identity = TabMeasure._chart_identity

    def __init__(self, path, running=False):
        class _R:
            is_running = running
        self._runner = _R()
        self._ti1_path = path
        self.cleared = 0

    def _clear_overlay(self):
        self.cleared += 1


def test_the_same_chart_keeps_its_painting(tmp_path):
    """The regression this guards: `_update_resume_availability` also runs when
    a measurement ENDS, and blanking the preview there would wipe the strips the
    user has just read — at the exact moment they want to look at them."""
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("x")
    p = _Painted(ti2)

    p._discard_stale_overlay()        # first sight of this chart
    p._discard_stale_overlay()        # end of a measurement on it
    p._discard_stale_overlay()
    assert p.cleared == 1, "the painting was cleared while the chart never changed"


def test_a_different_chart_drops_the_painting(tmp_path):
    a, b = tmp_path / "a.ti2", tmp_path / "b.ti2"
    a.write_text("x"); b.write_text("x")
    p = _Painted(a)
    p._discard_stale_overlay()
    before = p.cleared

    p._ti1_path = b
    p._discard_stale_overlay()
    assert p.cleared == before + 1


def test_re_generating_the_same_path_counts_as_a_different_chart(tmp_path):
    """Knut's actual case: the path never changed — the patches did. Identity
    therefore includes when the .ti2 was written, not just where it is."""
    import os
    ti2 = tmp_path / "chart.ti2"
    ti2.write_text("three columns")
    p = _Painted(ti2)
    p._discard_stale_overlay()
    before = p.cleared

    ti2.write_text("four columns")
    os.utime(ti2, (1, 1))             # a re-generation writes it afresh
    p._discard_stale_overlay()
    assert p.cleared == before + 1, "the old chart's strips would still be shown"


def test_a_measurement_in_progress_is_left_alone(tmp_path):
    a, b = tmp_path / "a.ti2", tmp_path / "b.ti2"
    a.write_text("x"); b.write_text("x")
    p = _Painted(a, running=True)
    p._discard_stale_overlay()
    p._ti1_path = b
    p._discard_stale_overlay()
    assert p.cleared == 0


def test_a_failure_to_clear_never_blocks_the_chart_change():
    from ui.tabs.tab_measure import TabMeasure
    assert "except Exception" in inspect.getsource(
        TabMeasure._discard_stale_overlay)


# ---- 3. displacing a measurement is announced before it happens -----------
class _Run:
    def __init__(self, tmp_path, ti3=False, icc=False):
        self.dir = tmp_path
        self.stem = "chart"
        if ti3:
            self.measurement_ti3.write_text("x")
        if icc:
            self.profile_icc.write_bytes(b"x")

    @property
    def measurement_ti3(self):  return self.dir / "chart.ti3"

    @property
    def profile_icc(self):      return self.dir / "chart.icc"

    @property
    def old_dir(self):          return self.dir / "old"


class _Tab(__import__("PyQt6.QtWidgets", fromlist=["QWidget"]).QWidget):
    """A real QWidget (the dialog needs a parent), with only the two
    attributes the guard actually reads."""

    from ui.tabs.tab_chart import TabChart
    _confirm_displacing_results = TabChart._confirm_displacing_results

    def __init__(self, run, verification=False):
        super().__init__()
        class _P:
            def current_run(_s): return run
        class _FM:
            def project(_s): return _P()
        self._file_mgr = _FM()
        self._verification = verification

    def _is_verification_target(self):
        return self._verification


def test_a_run_with_no_results_is_never_interrupted(qapp, tmp_path):
    """The ordinary case — still settling on chart options — must stay silent."""
    assert _Tab(_Run(tmp_path))._confirm_displacing_results() is True


def test_no_project_open_is_not_a_reason_to_ask(qapp):
    class _Tab2(_Tab):
        def __init__(self):
            class _FM:
                def project(_s): raise RuntimeError("no project")
            super().__init__(None)
            self._file_mgr = _FM()

        def _is_verification_target(self): return False

    assert _Tab2()._confirm_displacing_results() is True


def test_a_verification_build_is_not_a_reason_to_ask(qapp, tmp_path):
    """It snapshots and restores the run's profiling work, so nothing moves."""
    run = _Run(tmp_path, ti3=True, icc=True)
    assert _Tab(run, verification=True)._confirm_displacing_results() is True


@pytest.mark.parametrize("ti3,icc", [(True, False), (False, True), (True, True)])
def test_results_in_the_run_do_raise_the_question(qapp, tmp_path, ti3, icc):
    run = _Run(tmp_path, ti3=ti3, icc=icc)
    tab = _Tab(run)

    seen = {}

    import PyQt6.QtWidgets as QtW
    real = QtW.QMessageBox.exec

    def _fake(self):
        seen["text"] = self.text()
        seen["buttons"] = [b.text() for b in self.buttons()]
        # Answer "Cancel" — the build must not go ahead.
        self.setClickedButtonForTest = None
        return 0

    QtW.QMessageBox.exec = _fake
    try:
        tab._confirm_displacing_results()
    finally:
        QtW.QMessageBox.exec = real

    assert seen, "no window was raised"
    # It names where the files go, and promises nothing is deleted.
    assert "old" in seen["text"]
    assert "deleted" in seen["text"]
    # …and it offers the non-destructive way out.
    assert "New run" in seen["text"]


def test_the_wording_counts_one_result_and_two_differently(qapp, tmp_path):
    """Real singular and plural, never "(s)" — and never "1 item(s)"."""
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._confirm_displacing_results)
    assert "already has {item}" in src
    assert "already has {first} and {second}" in src
    assert "(s)" not in src


# ---- 4. Start Measurement warns before it replaces readings ---------------
# *"if I click on Start Measurement on a chart that has a measurement, there is
# supposed to be a warning, which not always comes."* It never came at Start:
# the only replacement warning lived in the chart-LOAD window, so a chart that
# was already open had nothing guarding it.
class _Box:
    def __init__(self, checked, visible=True, enabled=True):
        self._c, self._v, self._e = checked, visible, enabled

    def isChecked(self):  return self._c
    def isVisible(self):  return self._v
    def isEnabled(self):  return self._e


class _Measure(__import__("PyQt6.QtWidgets", fromlist=["QWidget"]).QWidget):
    from ui.tabs.tab_measure import TabMeasure
    _confirm_replacing_measurement = TabMeasure._confirm_replacing_measurement
    # Which measurement is at risk became its own lookup in beta.76, so a
    # verification's readings are found in their dated folder rather than
    # beside the shared chart. With no target controller it falls through to
    # the chart's own .ti3, which is what these profiling cases are about.
    _measurement_at_risk = TabMeasure._measurement_at_risk
    _replace_warning_scope = TabMeasure._replace_warning_scope

    def __init__(self, ti3, resume=False, refine=False):
        super().__init__()
        self._ti3 = ti3
        self._m_resume_cb = self._resume_cb = _Box(resume)
        self._m_refine_cb = self._refine_cb = _Box(refine)
        self._target_ctl = None          # → no scope, so no "don't ask" tick
        self._replace_warning_silenced = set()

    def _existing_ti3_for_chart(self):  return self._ti3
    def _current_mode(self):            return "manual"


def test_no_measurement_means_no_question(qapp):
    assert _Measure(None)._confirm_replacing_measurement() is True


@pytest.mark.parametrize("resume,refine", [(True, False), (False, True)])
def test_refining_or_resuming_is_not_replacing(qapp, tmp_path, resume, refine):
    """Both add to the readings instead of overwriting them, so neither is a
    reason to interrupt the user."""
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("x")
    m = _Measure(ti3, resume=resume, refine=refine)
    assert m._confirm_replacing_measurement() is True


def test_a_plain_re_read_does_raise_the_question(qapp, tmp_path):
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("x")

    seen = {}
    import PyQt6.QtWidgets as QtW
    real = QtW.QMessageBox.exec

    def _fake(self):
        seen["text"] = self.text()
        return 0

    QtW.QMessageBox.exec = _fake
    try:
        _Measure(ti3)._confirm_replacing_measurement()
    finally:
        QtW.QMessageBox.exec = real

    assert seen, "no warning was raised"
    assert str(ti3) in seen["text"], "it must name the file at risk"
    assert "Refine / resume" in seen["text"], "…and the way to keep the readings"


def test_it_is_asked_before_the_read_starts(qapp):
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    lines = [l.strip() for l in src.splitlines()]
    ask = next(i for i, l in enumerate(lines)
               if "_confirm_replacing_measurement()" in l)
    clear = next((i for i, l in enumerate(lines) if "self._log.clear()" in l),
                 len(lines))
    assert ask < clear, "asked after the session was already being set up"


def test_the_guard_runs_before_anything_is_built(qapp):
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_generate)
    lines = [l.strip() for l in src.splitlines()]
    guard = next(i for i, l in enumerate(lines)
                 if "_confirm_displacing_results()" in l)
    reset = next((i for i, l in enumerate(lines)
                  if "reset_ink_inspector" in l), len(lines))
    assert guard < reset, "asked too late — the previous chart is already gone"
