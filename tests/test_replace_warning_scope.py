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
    """Since beta.79 the window is not opened from inside showEvent — a modal
    blocks there before the tab has painted (Knut, #130 2026-07-28) — so it is
    handed to the event loop and made a moment later."""
    from ui.tabs.tab_measure import TabMeasure
    show = inspect.getsource(TabMeasure.showEvent)
    assert "self._pending_overlay_offer = False" in show
    assert "QTimer.singleShot(0, self._offer_existing_overlay_now)" in show
    assert "_maybe_offer_existing_overlay()" in inspect.getsource(
        TabMeasure._offer_existing_overlay_now)


def test_the_held_offer_is_made_only_once():
    """The flag is cleared as the tab is shown, so re-showing does not ask
    again even though the window itself opens a moment later."""
    from ui.tabs.tab_measure import TabMeasure
    lines = [l.strip() for l in inspect.getsource(TabMeasure.showEvent).splitlines()]
    cleared = next(i for i, l in enumerate(lines)
                   if "self._pending_overlay_offer = False" in l)
    scheduled = next(i for i, l in enumerate(lines) if "QTimer.singleShot" in l)
    assert cleared < scheduled


def test_showing_the_tab_never_breaks_on_a_failed_offer():
    from ui.tabs.tab_measure import TabMeasure
    assert "except Exception" in inspect.getsource(
        TabMeasure._offer_existing_overlay_now)


# --- 7. the overlay offer carries the same silence (Knut's scenario 4) ----
# *"scenario 4: keep it and Implement the same per-run 'don't ask again' I
# specified."*
def test_the_offer_window_can_be_silenced_per_run():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert "self._offer_silenced" in src
    assert "_replace_warning_scope()" in src, "it must use the SAME scope rule"


def test_the_offer_silence_is_consulted_before_the_window_is_built():
    from ui.tabs.tab_measure import TabMeasure
    lines = [l.strip() for l in
             inspect.getsource(TabMeasure._maybe_offer_existing_overlay).splitlines()]
    check = next(i for i, l in enumerate(lines) if "in self._offer_silenced" in l)
    build = next(i for i, l in enumerate(lines) if "QDialog(self)" in l)
    assert check < build


def test_the_two_windows_have_separate_silences():
    """Silencing the load-time offer must not silence the last guard before
    readings are overwritten, and the other way round."""
    from ui.tabs.tab_measure import TabMeasure
    init = inspect.getsource(TabMeasure.__init__)
    assert "self._offer_silenced: set = set()" in init
    assert "self._replace_warning_silenced: set = set()" in init

    offer = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    replace = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    assert "_replace_warning_silenced" not in offer
    assert "_offer_silenced" not in replace


def test_the_offer_silence_is_never_persisted():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    for bad in ('settings.set("offer_silenced', 'settings.set("_offer_silenced'):
        assert bad not in src


def test_cancelling_the_offer_never_silences_it():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    lines = [l.strip() for l in src.splitlines()]
    ret = next(i for i, l in enumerate(lines) if "DialogCode.Accepted" in l)
    add = next(i for i, l in enumerate(lines) if "self._offer_silenced.add" in l)
    assert ret < add, "the silence is recorded before the window was accepted"


def test_the_two_labels_name_which_window_they_silence(qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure

    class _T(_Tab):
        _offer_silence_label = TabMeasure._offer_silence_label

    t = _T(_Ctl(_project(tmp_path), _Target(profile_run="run1")))
    assert t._offer_silence_label() != t._replace_warning_silence_label(), \
        "two windows that can be silenced separately need distinguishable ticks"


# --- 8. every window explains what its buttons do ------------------------
# *"Make sure the actions/consequences of each window's buttons are explained
# for all windows."*
def test_the_replace_warning_explains_its_buttons():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._confirm_replacing_measurement)
    assert "What each button does" in src
    assert "Measure again — starts the measurement now" in src
    assert "Cancel — nothing is measured and nothing is written" in src


def test_the_offer_window_explains_its_buttons():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._maybe_offer_existing_overlay)
    assert "What each button does" in src
    assert "OK — applies the two choices" in src
    assert "Cancel — changes nothing at all" in src


# --- 9. the overlay box is ON when it first appears ----------------------
# His beta.76 report: he measured a run that had nothing, stopped after one
# strip, and the readings were on the preview while the checkbox — newly
# visible — was unticked.
def test_a_first_measurement_ticks_the_overlay_box():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._adopt_overlay_after_first_measurement)
    assert "_sync_overlay_checkboxes(True)" in src
    assert "_show_overlay_from_existing_ti3()" in src, \
        "the picture and the control must agree in substance, not just look"


def test_it_only_acts_on_the_transition():
    """A box the user deliberately unticked on a chart that already had a
    measurement must be left alone."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._adopt_overlay_after_first_measurement)
    assert "cb.isChecked()" in src and "not cb.isVisible()" in src


def test_both_completion_paths_reach_it():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_measure_done)
    assert src.count("_adopt_overlay_after_first_measurement()") >= 2, \
        "the interrupted path and the ordinary one both have to tick it"


def test_it_never_breaks_the_end_of_a_measurement():
    from ui.tabs.tab_measure import TabMeasure
    assert "except Exception" in inspect.getsource(
        TabMeasure._adopt_overlay_after_first_measurement)
