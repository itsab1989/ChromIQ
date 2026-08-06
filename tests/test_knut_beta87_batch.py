"""#130 (Knut, 2026-07-28/29), testing beta.86/87 with a real project.

Four findings, and one that turned out not to be a fault — which mattered most,
because he asked directly whether recent changes had broken his data:

    *"Also, run 3 now suddenly seems to have 44 pages. Has the changes lately
    created new problems? … Is the New run feature modifying other runs?"*

**No.** His own project answers it: run 3's chart really does hold 1950 patches,
and its geometry describes 44 pages, with 44 page files to match. run 1 has 90
patches over 2 pages and 2 files; run 2 has 484 patches on one page and one
file. Every run is self-consistent, and run 3's chart file predates all of the
recent work. What he saw was a genuinely large chart, not a damaged one.
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


# ---- "This run already has results" on a NEW run ------------------------
class _Target:
    def __init__(self, profile_run):
        self.profile_run = profile_run
        self.run_type = "profiling"

    def is_verification(self):
        return False


class _Ctl:
    def __init__(self, profile_run):
        self.target = _Target(profile_run)


class _Tab(__import__("PyQt6.QtWidgets", fromlist=["QWidget"]).QWidget):
    from ui.tabs.tab_chart import TabChart
    _confirm_displacing_results = TabChart._confirm_displacing_results
    # Since beta.133 the guard asks the run the BAR points at, through
    # core.measurement_target.resolve_run — so the stub project answers
    # has_run/run as well as current_run.
    _target_run = TabChart._target_run
    # §4 split the one message into two, sharing a window builder.
    _ask_chart_question = TabChart._ask_chart_question
    _profiling_chart_message = TabChart._profiling_chart_message
    _verify_chart_message = TabChart._verify_chart_message
    _duplicate_blocked_note = TabChart._duplicate_blocked_note
    _corrupt_measurement_note = TabChart._corrupt_measurement_note
    _pages_paragraph = TabChart._pages_paragraph

    def __init__(self, tmp_path, profile_run):
        super().__init__()
        class _Run:
            dir = tmp_path
            stem = "P"
            measurement_ti3 = tmp_path / "P.ti3"
            profile_icc = tmp_path / "P.icc"
            old_dir = tmp_path / "old"
        class _P:
            def current_run(_s): return _Run()
            def has_run(_s, rid): return bool(rid)
            def run(_s, rid): return _Run()
        class _FM:
            def project(_s): return _P()
        self._file_mgr = _FM()
        self._target_ctl = _Ctl(profile_run)

    def _is_verification_target(self):
        return False


def test_a_new_run_never_warns_about_another_run_s_results(qapp, tmp_path):
    """His report: the previously selected run had a measurement, and building
    a chart for a BRAND NEW run warned about it. The new run displaces
    nothing."""
    (tmp_path / "P.ti3").write_text("x")
    (tmp_path / "P.icc").write_bytes(b"x")

    tab = _Tab(tmp_path, profile_run="")        # "New run"

    seen = {}
    import PyQt6.QtWidgets as W
    real = W.QMessageBox.exec
    W.QMessageBox.exec = lambda self: seen.setdefault("shown", True) or 0
    try:
        assert tab._confirm_displacing_results() is True
    finally:
        W.QMessageBox.exec = real
    assert not seen, "it warned about a run that is not being built into"


def test_an_existing_run_with_results_still_warns(qapp, tmp_path):
    """The guard must not be lost — only narrowed."""
    (tmp_path / "P.ti3").write_text("x")
    tab = _Tab(tmp_path, profile_run="run2")

    seen = {}
    import PyQt6.QtWidgets as W
    real = W.QMessageBox.exec
    W.QMessageBox.exec = lambda self: seen.setdefault("shown", True) or 0
    try:
        tab._confirm_displacing_results()
    finally:
        W.QMessageBox.exec = real
    assert seen, "an existing run with results must still be protected"


def test_the_new_run_check_comes_before_the_run_is_read():
    """A "New run" displaces nothing, so it must return before any run is
    resolved — resolving one is also what could create it."""
    from ui.tabs.tab_chart import TabChart
    lines = [l.strip() for l in
             inspect.getsource(TabChart._confirm_displacing_results).splitlines()]
    guard = next(i for i, l in enumerate(lines) if "ctl.target.profile_run" in l)
    read = next(i for i, l in enumerate(lines) if "_target_run()" in l)
    assert guard < read


# ---- the completion window names the button it actually has -------------
def test_the_completion_window_names_the_real_button():
    """He renamed it to "Go to Build Profile Tab" and the first line still
    said "Click Build Profile".

    The name became a placeholder in beta.149, because tab 4 has two names —
    "Build Profile", and "Calibration & Profiling" while calibration options
    are on. The invariant is unchanged: the prose names the button that is
    there. Both now come from ``_profile_tab_name()``.
    """
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    assert "Click <b>Go to {tab} Tab</b>" in src
    assert "Click <b>Build Profile</b> to finalise" not in src, \
        "the old wording names a button that is not there"
    assert "Go to Build Profile Tab</b> to finalise" not in src, \
        "a hard-coded tab name is back; it is wrong half the time"


def test_both_completion_windows_were_corrected():
    """Strips and patch-by-patch each have their own window."""
    from ui.tabs.tab_measure import TabMeasure
    assert inspect.getsource(TabMeasure).count(
        "Click <b>Go to {tab} Tab</b>") == 2


def test_the_button_is_named_after_the_tab_that_exists(qapp, tmp_path):
    """Knut, beta.148: with calibration options on, tab 4 is called
    "4. Calibration & Profiling", so a button offering to go to "Build Profile"
    sends the user looking for a tab that is not there — and it must go back
    when the preference is switched off again."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure

    class _S(AppSettings):
        cal = False

        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            if key == "calibration_mode":
                return self.cal
            return super().get(key, default)

    st = _S()
    tab = TabMeasure(ArgyllRunner(st), st)
    assert tab._profile_tab_name() == "Build Profile"
    st.cal = True
    assert tab._profile_tab_name() == "Calibration & Profiling"
    st.cal = False
    assert tab._profile_tab_name() == "Build Profile"


# ---- the strip times belong to the chart that was measured --------------
def test_changing_chart_clears_the_strip_times():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._discard_stale_overlay)
    assert "_clear_pace_readout()" in src, (
        "the previous run's reading times stay on screen for a run that was "
        "never measured")


def test_it_still_only_acts_when_the_chart_really_changed():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._discard_stale_overlay)
    lines = [l.strip() for l in src.splitlines()]
    guard = next(i for i, l in enumerate(lines) if "_painted_chart" in l)
    clear = next(i for i, l in enumerate(lines) if "_clear_pace_readout()" in l)
    assert guard < clear


def test_a_measurement_in_progress_keeps_its_times():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._discard_stale_overlay)
    lines = [l.strip() for l in src.splitlines()]
    running = next(i for i, l in enumerate(lines) if "is_running" in l)
    clear = next(i for i, l in enumerate(lines) if "_clear_pace_readout()" in l)
    assert running < clear


# ---- the Delete button label, measured (his sixth clipping report) -------
# He tested beta.86; the per-window fit shipped in beta.87. Rather than point
# at a newer build again, this measures the exact label he named, in the font
# that paints it, through the code path the window uses — in every language.
def test_the_delete_run_button_label_fits_everywhere(qapp):
    import pathlib

    from PyQt6.QtGui import QFont, QFontMetrics
    from PyQt6.QtWidgets import QMessageBox

    import core.i18n as I
    import core.run_delete as rd
    from ui.widgets import ButtonFontFilter, fit_message_box_buttons

    def painted(btn) -> int:
        t = btn.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&")
        if btn.font().capitalization() == QFont.Capitalization.AllUppercase:
            t = t.upper()
        return QFontMetrics(btn.font()).horizontalAdvance(t)

    langs = ["en"] + sorted(
        p.stem for p in (pathlib.Path(__file__).resolve().parents[1]
                         / "data" / "i18n").glob("*.json") if "." not in p.stem)
    bad = []
    for lang in langs:
        I.set_language(lang)
        for n in ("1", "4", "10"):
            plan = rd.DeletePlan(kind=rd.KIND_RUN, run_id=f"run{n}",
                                 project_name="P", lands_on="run1")
            box = QMessageBox()
            box.addButton(rd.confirm_label(plan),
                          QMessageBox.ButtonRole.DestructiveRole)
            box.addButton(I.tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
            fit_message_box_buttons(box)
            ButtonFontFilter.fit_window(box)
            for btn in box.buttons():
                if btn.minimumSizeHint().width() < painted(btn):
                    bad.append((lang, btn.text()))
    I.set_language("en")
    assert not bad, bad


def test_every_delete_window_label_fits(qapp):
    """Not only the run one — the verification and last-run windows too."""
    from PyQt6.QtGui import QFont, QFontMetrics
    from PyQt6.QtWidgets import QPushButton

    import core.run_delete as rd
    from ui.widgets import ButtonFontFilter

    plans = [
        rd.DeletePlan(kind=rd.KIND_RUN, run_id="run10", project_name="P"),
        rd.DeletePlan(kind=rd.KIND_VERIFY_ALL, run_id="run1", project_name="P",
                      verification_ids=["a", "b", "c"]),
        rd.DeletePlan(kind=rd.KIND_VERIFY_ALL, run_id="run1", project_name="P"),
        rd.DeletePlan(kind=rd.KIND_VERIFY_ONE, run_id="run1", project_name="P",
                      verification_ids=["a"], verification_measured=True),
        rd.DeletePlan(kind=rd.KIND_VERIFY_ONE, run_id="run1", project_name="P",
                      verification_ids=["a"], verification_measured=False),
    ]
    for plan in plans:
        btn = QPushButton(rd.confirm_label(plan))
        ButtonFontFilter.fit(btn)
        t = btn.text()
        if btn.font().capitalization() == QFont.Capitalization.AllUppercase:
            t = t.upper()
        need = QFontMetrics(btn.font()).horizontalAdvance(t)
        assert btn.minimumSizeHint().width() >= need, btn.text()


# ---- the pages field follows the chart, not a saved default -------------
# "All three runs seem to show pages = 20, even though run 1 only has 2 pages.
# After changing parameters … this stuck 20 pages setting suddenly was gone."
# 20 was his saved default; the chart's own count was only applied inside the
# full-recipe branch and a default could land on top of it afterwards.
def test_the_page_count_is_taken_from_the_chart(qapp, tmp_path):
    import inspect

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._display_run_chart)
    assert "_show_loaded_page_count" in src
    lines = [l.strip() for l in src.splitlines()]
    restore = next(i for i, l in enumerate(lines)
                   if "_restore_chart_settings(" in l)
    show = next(i for i, l in enumerate(lines) if "_show_loaded_page_count" in l)
    assert restore < show, "a default applied later would win again"


class _PagesTab:
    from ui.tabs.tab_chart import TabChart
    _show_loaded_page_count = TabChart._show_loaded_page_count

    def __init__(self):
        class _Spin:
            def __init__(self): self.v = 20        # his saved default
            def setValue(self, n): self.v = int(n)
        self._manual_pages_spin = _Spin()
        self._pages_spin = _Spin()


def test_the_real_page_files_decide(qapp, tmp_path):
    tab = _PagesTab()
    tifs = []
    for n in (1, 2):
        t = tmp_path / f"P_{n:02d}.tif"
        t.write_bytes(b"x")
        tifs.append(t)

    tab._show_loaded_page_count(tifs, tmp_path / "P.ti2")

    assert tab._manual_pages_spin.v == 2, "the stale default survived"
    assert tab._pages_spin.v == 2


def test_the_geometry_decides_when_no_pages_are_rendered_yet(qapp, tmp_path):
    import json
    (tmp_path / "P.channels.json").write_text(json.dumps(
        {"layout": {"patches": [{"page": 0}, {"page": 1}, {"page": 2}]}}))
    tab = _PagesTab()

    tab._show_loaded_page_count([], tmp_path / "P.ti2")

    assert tab._manual_pages_spin.v == 3


def test_a_chart_that_says_nothing_leaves_the_field_alone(qapp, tmp_path):
    tab = _PagesTab()
    tab._show_loaded_page_count([], tmp_path / "P.ti2")
    assert tab._manual_pages_spin.v == 20, "it invented a page count"


def test_it_never_breaks_a_chart_load(qapp, tmp_path):
    import inspect

    from ui.tabs.tab_chart import TabChart
    assert "except Exception" in inspect.getsource(
        TabChart._show_loaded_page_count)
