"""#130 + #131 (Knut, 2026-07-28), testing beta.77. Four faults.

1. **The Delete button's ⓘ kept one tab's colour.** *"The info icon for the
   Delete button does not change color according to tab selected, like the
   other info icons."*
2. **A window's button was clipped again.** *"The button Delete Run 4
   Permanently has its text cut on both sides. Again, all windows created must
   follow the universal rules created to prevent this happening."*
3. **The selection did not move after a delete.** *"After deletion of run 4, the
   Profile run selection did not jump to last run in the list (which now was
   run 5)."*
4. **A window came up over a half-painted tab.** *"the whole main window behind
   the popup warning window is half drawn… the right preview panel is not at
   all drawn."*

(3) is the interesting one: the manifest was right all along — `current_run`
was already the last run — but the BAR reads its selection from the target,
which still named the run that had just been deleted.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtGui import QFont, QFontMetrics          # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMessageBox,  # noqa: E402
                             QPushButton)

import core.i18n as I                                # noqa: E402
import core.run_delete as rd                         # noqa: E402
from ui.widgets import (ButtonFontFilter,            # noqa: E402
                        fit_message_box_buttons)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


# ---- 1. every ⓘ in the bar follows the tab ------------------------------
def test_the_delete_info_icon_follows_the_tab_colour():
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar.set_accent)
    assert "self._delete_tip" in src, "the Delete ⓘ keeps the last tab's colour"


def test_every_tooltip_button_in_the_bar_is_tinted():
    """A guard against the next one being forgotten: every ⓘ the bar creates
    must appear in set_accent."""
    from ui.measurement_target_bar import MeasurementTargetBar
    built = inspect.getsource(MeasurementTargetBar.__init__)
    tinted = inspect.getsource(MeasurementTargetBar.set_accent)
    names = {ln.split("=")[0].strip()
             for ln in built.splitlines()
             if "= TooltipButton(" in ln and ln.strip().startswith("self.")}
    missing = [n for n in names if n not in tinted]
    assert not missing, f"these ⓘ are never tinted: {missing}"


# ---- 2. the universal button rule, applied to these windows -------------
def _painted_width(btn) -> int:
    text = btn.text().replace("&&", "\x00").replace("&", "").replace("\x00", "&")
    if btn.font().capitalization() == QFont.Capitalization.AllUppercase:
        text = text.upper()
    return QFontMetrics(btn.font()).horizontalAdvance(text)


def test_fitting_a_message_box_widens_every_button(qapp):
    """Fitting a freshly built box — **without** swapping the font first, which
    is the state the real code is in when it calls this. The helper has to
    apply the final font itself and then measure; measuring first computes a
    width for the narrow font and the wide one is painted into it."""
    box = QMessageBox()
    box.addButton("Delete run 4 permanently", QMessageBox.ButtonRole.DestructiveRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

    fit_message_box_buttons(box)

    for b in box.buttons():
        assert b.font().capitalization() == QFont.Capitalization.AllUppercase, \
            "the final font was not applied before measuring"
        assert b.minimumSizeHint().width() >= _painted_width(b), b.text()


def test_measuring_before_the_font_swap_is_not_enough(qapp):
    """The failure mode itself, so the ordering cannot quietly regress: the
    plain width helper, used on an unswapped button, leaves it too narrow for
    what will actually be painted."""
    from ui.widgets import fit_button_width
    btn = QPushButton("Delete run 4 permanently")
    fit_button_width(btn)                       # measured in the narrow font
    narrow = btn.minimumSizeHint().width()

    ButtonFontFilter.fit(btn)                   # what the app then does
    assert _painted_width(btn) > narrow - 36, (
        "if this ever fails the fonts have converged and "
        "fit_message_box_buttons could be simplified")


def test_it_survives_a_box_that_cannot_be_measured(qapp):
    """Sizing must never raise — a window has to open even if the fit fails."""
    class _Broken:
        def buttons(self):
            raise RuntimeError("no")

    fit_message_box_buttons(_Broken())       # must not raise


@pytest.mark.parametrize("where,method", [
    ("measurement_target_bar", "_on_delete_clicked"),
    ("tab_measure", "_confirm_replacing_measurement"),
    ("tab_chart", "_confirm_displacing_results"),
])
def test_every_new_window_applies_the_universal_rule(where, method):
    """His standing rule: "all windows created must follow the universal rules
    created to prevent this happening"."""
    if where == "measurement_target_bar":
        from ui.measurement_target_bar import MeasurementTargetBar as C
    elif where == "tab_measure":
        from ui.tabs.tab_measure import TabMeasure as C
    else:
        from ui.tabs.tab_chart import TabChart as C
    src = inspect.getsource(getattr(C, method))
    assert "fit_message_box_buttons(box)" in src, \
        f"{where}.{method} builds a window without fitting its buttons"


def test_the_fit_happens_before_the_window_is_shown():
    from ui.measurement_target_bar import MeasurementTargetBar
    lines = [l.strip() for l in
             inspect.getsource(MeasurementTargetBar._on_delete_clicked).splitlines()]
    fit = next(i for i, l in enumerate(lines) if "fit_message_box_buttons" in l)
    show = next(i for i, l in enumerate(lines) if l == "box.exec()")
    assert fit < show


@pytest.mark.parametrize("lang", ["en"] + sorted(
    p.stem for p in (__import__("pathlib").Path(__file__).resolve().parents[1]
                     / "data" / "i18n").glob("*.json") if "." not in p.stem))
def test_the_delete_labels_fit_in_every_language(qapp, lang):
    """The label that clipped was a *composed* one — "Delete run {n}
    permanently" — so it is measured per language with a real number in it."""
    I.set_language(lang)
    try:
        plan = rd.DeletePlan(kind=rd.KIND_RUN, run_id="run4", project_name="P",
                             lands_on="run5")
        labels = [rd.confirm_label(plan), I.tr("Cancel"),
                  I.tr("Empty run {n}").format(n="1"),
                  I.tr("Delete the whole project")]
        for label in labels:
            btn = QPushButton(label)
            ButtonFontFilter.fit(btn)
            assert btn.minimumSizeHint().width() >= _painted_width(btn), \
                f"{lang}: {label!r}"
    finally:
        I.set_language("en")


# ---- 3. the selection moves to the last run -----------------------------
def test_the_bar_moves_its_selection_after_a_delete():
    """The manifest was already right; the BAR reads the target, which still
    named the deleted run."""
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._on_delete_clicked)
    assert "landed = rd.delete_run(" in src
    assert "self._ctl.set_profile_run(landed)" in src


def test_it_clears_the_verification_choice_too():
    """The dates belonged to the run that is gone."""
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._on_delete_clicked)
    assert 'self._ctl.set_verification_id("")' in src


def test_delete_run_still_reports_where_it_landed(tmp_path):
    """The value the bar now uses — checked against the folders on disk."""
    import json

    from core.file_manager import Project, RunMeta
    root = tmp_path / "P"
    root.mkdir(parents=True)
    (root / "runs").mkdir()
    (root / Project.MANIFEST).write_text(json.dumps({
        "schema_version": 3, "created_at": "", "target_name": "P",
        "current_run": "run1", "runs": ["run1"]}), encoding="utf-8")
    proj = Project.load(root)
    for _ in range(4):
        proj.new_run()
    for r in proj.all_runs():
        r.ensure_dir()
        if not r.meta_path.exists():
            r.save_meta(RunMeta.fresh(r.id))

    class _T:
        profile_run, run_type, verification_id = "run4", "profiling", ""
        def is_verification(self): return False

    landed = rd.delete_run(proj, rd.plan_for(proj, _T()))
    assert landed == "run4", "5 runs minus one leaves run1…run4"
    assert sorted(d.name for d in proj.runs_root.iterdir() if d.is_dir()) == \
        ["run1", "run2", "run3", "run4"]


# ---- 4. no window over a half-painted tab -------------------------------
def test_the_offer_is_never_opened_inside_show_event():
    """A modal opened from showEvent blocks before the tab has painted, so it
    comes up over a half-drawn window."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.showEvent)
    assert "QTimer.singleShot(0, self._offer_existing_overlay_now)" in src
    assert "_maybe_offer_existing_overlay()" not in src, \
        "the window is still being opened straight out of showEvent"


def test_the_visible_path_is_deferred_as_well():
    """Changing the Profile run while the tab is already on screen opens the
    same window out of the same kind of handler."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure.set_ti1_path)
    assert "QTimer.singleShot(0, self._offer_existing_overlay_now)" in src


def test_the_deferred_offer_checks_the_tab_is_still_showing():
    """By the time it runs, the user may have moved on."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._offer_existing_overlay_now)
    assert "self.isVisible()" in src
    assert "except Exception" in src
