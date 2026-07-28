"""#131 (Knut, 2026-07-28): the "don't ask again" tick, and how narrow it is.

His ruling, which is the whole specification:

    *"Yes, make it remember a 'don't ask again' choice, which shall only be
    remembered for the CURRENTLY selected profile run (with run type=Profiling)
    or verification run (run type=verification and verification field set to a
    specific date, where that date_time folder has a measurement), and is reset
    when restarting the app. This way the warning disappears only while working
    on a specific run, and if later revisiting that run another day, the warning
    still comes."*

Three properties follow, and each is a test below:

1. it is scoped to **one** run — never global;
2. it lives **in memory only**, so closing the program forgets it;
3. it is only offered where there is something specific to scope it to —
   "New run" and "New verification" name nothing yet.

The fourth test family covers a gap his question exposed: a verification's
readings live in its **dated folder**, not beside the shared verification chart,
so the warning could never fire for a verification at all.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication              # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# --- doubles -------------------------------------------------------------
class _Verification:
    def __init__(self, root, run_id, vid):
        self.dir = root / "runs" / run_id / "verifications" / vid

    @property
    def measurement_ti3(self):
        return self.dir / "P-verify.ti3"


class _Run:
    def __init__(self, root, run_id):
        self._root, self.id = root, run_id

    def verification(self, vid):
        return _Verification(self._root, self.id, vid)


class _Project:
    def __init__(self, root, runs=("run1", "run2")):
        self.root = root
        self._runs = list(runs)

    def has_run(self, rid):
        return rid in self._runs

    def run(self, rid):
        return _Run(self.root, rid)


class _Target:
    def __init__(self, run_type="profiling", profile_run="run1",
                 verification_id=""):
        self.run_type = run_type
        self.profile_run = profile_run
        self.verification_id = verification_id

    def is_verification(self):
        return self.run_type == "verification"


class _Ctl:
    def __init__(self, project, target):
        self._p, self.target = project, target

    def project_or_none(self):
        return self._p


class _Tab:
    from ui.tabs.tab_measure import TabMeasure
    _replace_warning_scope = TabMeasure._replace_warning_scope
    _measurement_at_risk = TabMeasure._measurement_at_risk
    _replace_warning_silence_label = TabMeasure._replace_warning_silence_label

    def __init__(self, ctl, chart_ti3=None):
        self._target_ctl = ctl
        self._chart_ti3 = chart_ti3

    def _existing_ti3_for_chart(self):
        return self._chart_ti3


def _project(tmp_path):
    return _Project(tmp_path)


# --- 1. scoped to one run ------------------------------------------------
def test_a_profiling_run_is_scoped_by_project_and_run(qapp, tmp_path):
    tab = _Tab(_Ctl(_project(tmp_path), _Target(profile_run="run2")))
    assert tab._replace_warning_scope() == ("profiling", str(tmp_path), "run2")


def test_two_runs_never_silence_each_other(qapp, tmp_path):
    p = _project(tmp_path)
    a = _Tab(_Ctl(p, _Target(profile_run="run1")))._replace_warning_scope()
    b = _Tab(_Ctl(p, _Target(profile_run="run2")))._replace_warning_scope()
    assert a != b


def test_two_projects_with_the_same_run_name_never_silence_each_other(qapp, tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    a = _Tab(_Ctl(_Project(one), _Target(profile_run="run1")))._replace_warning_scope()
    b = _Tab(_Ctl(_Project(two), _Target(profile_run="run1")))._replace_warning_scope()
    assert a != b, "a run1 in one project would have silenced run1 in another"


# --- 2. nothing specific enough → not offered ----------------------------
def test_new_run_is_never_scoped(qapp, tmp_path):
    """"New run" names nothing on disk yet."""
    tab = _Tab(_Ctl(_project(tmp_path), _Target(profile_run="")))
    assert tab._replace_warning_scope() is None


def test_an_unknown_run_is_never_scoped(qapp, tmp_path):
    tab = _Tab(_Ctl(_project(tmp_path), _Target(profile_run="run9")))
    assert tab._replace_warning_scope() is None


def test_no_project_is_never_scoped(qapp):
    tab = _Tab(_Ctl(None, _Target()))
    assert tab._replace_warning_scope() is None


def test_new_verification_is_never_scoped(qapp, tmp_path):
    tab = _Tab(_Ctl(_project(tmp_path),
                    _Target("verification", "run1", verification_id="")))
    assert tab._replace_warning_scope() is None


def test_a_verification_date_without_a_measurement_is_never_scoped(qapp, tmp_path):
    """His condition, verbatim: "where that date_time folder has a
    measurement". An empty date has nothing that could be replaced."""
    tab = _Tab(_Ctl(_project(tmp_path),
                    _Target("verification", "run1", "2026-07-28_131500")))
    assert tab._replace_warning_scope() is None


def test_a_verification_date_with_a_measurement_is_scoped(qapp, tmp_path):
    vid = "2026-07-28_131500"
    vdir = tmp_path / "runs" / "run1" / "verifications" / vid
    vdir.mkdir(parents=True)
    (vdir / "P-verify.ti3").write_text("x")

    tab = _Tab(_Ctl(_project(tmp_path), _Target("verification", "run1", vid)))
    assert tab._replace_warning_scope() == (
        "verification", str(tmp_path), "run1", vid)


def test_two_dates_of_one_run_are_scoped_apart(qapp, tmp_path):
    scopes = []
    for vid in ("2026-07-28_131500", "2026-07-28_160244"):
        vdir = tmp_path / "runs" / "run1" / "verifications" / vid
        vdir.mkdir(parents=True)
        (vdir / "P-verify.ti3").write_text("x")
        scopes.append(_Tab(_Ctl(_project(tmp_path),
                                _Target("verification", "run1", vid)
                                ))._replace_warning_scope())
    assert scopes[0] != scopes[1] and all(s is not None for s in scopes)


# --- 3. in memory only ---------------------------------------------------
def test_the_silence_is_never_written_to_settings():
    """"…and is reset when restarting the app." A setting would survive the
    restart, so the store must not be one."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert "_replace_warning_silenced" in src
    for bad in ('self._settings.set("_replace_warning',
                'settings.set("replace_warning',
                'settings.set("measure_replace_warning'):
        assert bad not in src, f"the silence is being persisted: {bad}"


def test_it_starts_empty_on_every_construction():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.__init__)
    assert "self._replace_warning_silenced: set = set()" in src


# --- 4. the verification gap the question exposed ------------------------
def test_a_verification_looks_in_its_dated_folder(qapp, tmp_path):
    """The bug: a verification's readings are NOT beside the shared chart, so
    the chart-adjacent .ti3 is the wrong file to key on and the warning could
    never fire for a verification."""
    vid = "2026-07-28_131500"
    vdir = tmp_path / "runs" / "run1" / "verifications" / vid
    vdir.mkdir(parents=True)
    ti3 = vdir / "P-verify.ti3"
    ti3.write_text("x")

    tab = _Tab(_Ctl(_project(tmp_path), _Target("verification", "run1", vid)),
               chart_ti3=None)
    assert tab._measurement_at_risk() == ti3


def test_a_new_verification_puts_nothing_at_risk(qapp, tmp_path):
    tab = _Tab(_Ctl(_project(tmp_path), _Target("verification", "run1", "")),
               chart_ti3=tmp_path / "chart.ti3")
    assert tab._measurement_at_risk() is None


def test_profiling_still_uses_the_chart_s_own_measurement(qapp, tmp_path):
    ti3 = tmp_path / "chart.ti3"
    ti3.write_text("x")
    tab = _Tab(_Ctl(_project(tmp_path), _Target(profile_run="run1")),
               chart_ti3=ti3)
    assert tab._measurement_at_risk() == ti3


# --- 5. the window's own behaviour ---------------------------------------
def test_cancelling_never_silences_anything():
    """Ticking the box and then cancelling means "not this time", not
    "never warn me again"."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    assert "if agreed and ask is not None and ask.isChecked()" in src


def test_the_tick_is_not_offered_when_it_cannot_be_scoped():
    """Without a scope the tick could only mean "never ask again anywhere",
    which is exactly what his rule forbids."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    assert "if scope is not None:" in src
    assert "box.setCheckBox(ask)" in src


def test_the_silence_is_consulted_before_the_window_is_built():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    lines = [l.strip() for l in src.splitlines()]
    check = next(i for i, l in enumerate(lines)
                 if "in self._replace_warning_silenced" in l)
    build = next(i for i, l in enumerate(lines) if "QMessageBox(self)" in l)
    assert check < build


def test_the_label_names_what_it_applies_to(qapp, tmp_path):
    """A promise the user can read, rather than one they have to infer."""
    prof = _Tab(_Ctl(_project(tmp_path), _Target(profile_run="run1"))
                )._replace_warning_silence_label()
    ver = _Tab(_Ctl(_project(tmp_path), _Target("verification", "run1", "x"))
               )._replace_warning_silence_label()
    assert "profile run" in prof and "close ChromIQ" in prof
    assert "verification" in ver and "close ChromIQ" in ver


# --- 6. the offer is deferred, not discarded (Knut's scenarios 1 and 2) ---
# He asked whether loading a chart in Create Chart or Print Chart and THEN
# going to the Measure tab raises the "this chart already has a measurement"
# window. It did not: the offer was made while another tab was on screen,
# suppressed by the #134 rule, and never revisited.
def test_a_chart_loaded_from_another_tab_still_owes_the_offer():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.set_ti1_path)
    assert "self._pending_overlay_offer = True" in src
    assert "if self.isVisible():" in src, \
        "the #134 rule must still hold — never over Create Chart or Print Chart"


def test_showing_the_tab_makes_the_held_offer():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.showEvent)
    assert "_maybe_offer_existing_overlay()" in src
    assert "self._pending_overlay_offer = False" in src


def test_the_held_offer_is_made_only_once():
    """It is cleared BEFORE the window opens, so re-showing the tab does not
    ask again."""
    from ui.tabs.tab_measure import TabMeasure
    lines = [l.strip() for l in inspect.getsource(TabMeasure.showEvent).splitlines()]
    cleared = next(i for i, l in enumerate(lines)
                   if "self._pending_overlay_offer = False" in l)
    offered = next(i for i, l in enumerate(lines)
                   if "_maybe_offer_existing_overlay()" in l)
    assert cleared < offered


def test_showing_the_tab_never_breaks_on_a_failed_offer():
    from ui.tabs.tab_measure import TabMeasure
    assert "except Exception" in inspect.getsource(TabMeasure.showEvent)
