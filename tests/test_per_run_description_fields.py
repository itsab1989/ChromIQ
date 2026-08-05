"""#130 — the two text fields, and the one file each keystroke reaches.

Test Plan Specification §1 and §2 (docs/design/per_run_description.md).

Knut's rule, which the whole design rests on: **the Profile run picks the
folder, the Run type picks the file, and exactly one file is written.** Two
writable copies of one text is how they come to disagree, which is what his §2
ruling exists to prevent.
"""
from __future__ import annotations

import pytest

from core.measurement_target import (RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING,
                                     RUN_TYPE_VERIFICATION)


@pytest.fixture
def tab(qapp, tmp_path):
    """A real Create Chart tab with a real project and two runs."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    class _Settings(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            if key == "calibration_mode":
                return True
            return super().get(key, default)

    st = _Settings()
    fm = FileManager(st)
    fm.set_target_name("Desc-Test")
    project = fm.project()
    project.new_run()                       # run2 as well as run1
    ctl = MeasurementTargetController(fm)
    # The bar normally does this from the preference; without it set_run_type
    # coerces Calibration straight back to Profiling, which is its job.
    ctl.set_calibration_allowed(True)
    widget = TabChart(ArgyllRunner(st), fm, st, None)
    widget.set_target_controller(ctl)
    return widget, ctl, project


# ---- T1.3 / T1.4: the labels say what is selected ------------------------
def test_the_labels_name_the_run_they_belong_to(tab):
    widget, ctl, project = tab
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    widget._refresh_target_text()
    assert widget._manual_run_desc_lbl.text() == "Run 1 Description:"
    assert widget._manual_chart_notes_lbl.text() == "Run 1 Chart Notes:"


def test_a_calibration_names_itself_on_both_rows(tab):
    """Knut, §3a: a calibration is not a run, so it carries no run number.

    His beta.144 report sharpened the second half of it — the bare "Chart
    Notes:" this once asserted did not say WHICH chart, and a calibration
    chart is one of three the field can be editing: *"When 'Run type' =
    'Calibration' I also said to Change 'Run N Chart Notes' to 'Calibration
    Chart Notes', which matches the 'Calibration Description' field."*
    """
    widget, ctl, project = tab
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    widget._refresh_target_text()
    assert widget._manual_run_desc_lbl.text() == "Calibration Description:"
    assert widget._manual_chart_notes_lbl.text() == "Calibration Chart Notes:"


# ---- T2: one file per keystroke -----------------------------------------
def _type(widget, description="", notes=""):
    widget._manual_run_desc_edit.setText(description)
    widget._manual_chart_notes_edit.setText(notes)
    widget._save_target_text()


def test_a_profiling_run_writes_only_its_own_meta(tab):
    widget, ctl, project = tab
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    widget._refresh_target_text()
    _type(widget, "PhotoRag Baryta, gloss", "printed 5 Aug")

    assert project.run("run1").load_meta().description == "PhotoRag Baryta, gloss"
    assert project.run("run1").load_meta().chart_notes == "printed 5 Aug"
    assert project.run("run2").load_meta().description == "", (
        "another run's file was written — the Profile run picks the folder"
    )
    assert not project.calibration.meta_path.exists(), (
        "cal/meta.json was written by a profiling run — the Run type picks "
        "the file, and exactly one file is written"
    )


def test_a_calibration_writes_only_its_own_meta(tab):
    widget, ctl, project = tab
    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    widget._refresh_target_text()
    _type(widget, "Canson Baryta, warm room", "cal sheet 5 Aug")

    assert project.calibration.load_meta().description == "Canson Baryta, warm room"
    assert project.run("run1").load_meta().description == "", (
        "a run's file was written by a calibration"
    )


def test_switching_runs_shows_each_run_its_own_text(tab):
    """T2.10 — the half of Knut's request that was a missing refresh."""
    widget, ctl, project = tab
    ctl.set_run_type(RUN_TYPE_PROFILING)

    ctl.set_profile_run("run1")
    widget._refresh_target_text()
    _type(widget, "the first one", "sheet A")

    ctl.set_profile_run("run2")
    widget._refresh_target_text()
    assert widget._manual_run_desc_edit.text() == "", (
        "run 2 is showing run 1's description"
    )
    _type(widget, "the second one", "sheet B")

    ctl.set_profile_run("run1")
    widget._refresh_target_text()
    assert widget._manual_run_desc_edit.text() == "the first one"
    assert widget._manual_chart_notes_edit.text() == "sheet A"


def test_switching_to_calibration_and_back_keeps_both_texts(tab):
    widget, ctl, project = tab
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)
    widget._refresh_target_text()
    _type(widget, "run one", "run one sheet")

    ctl.set_run_type(RUN_TYPE_CALIBRATION)
    widget._refresh_target_text()
    _type(widget, "the calibration", "cal sheet")

    ctl.set_run_type(RUN_TYPE_PROFILING)
    widget._refresh_target_text()
    assert widget._manual_run_desc_edit.text() == "run one"
    assert project.calibration.load_meta().description == "the calibration"


# ---- one value, two widgets ---------------------------------------------
def test_the_guided_and_manual_boxes_are_one_value(tab):
    """Guided and Manual have separate Output frames, so the one value has two
    widgets. A run has one description; two boxes showing different text for it
    would be two truths for one run."""
    widget, ctl, project = tab
    ctl.set_profile_run("run1")
    widget._refresh_target_text()

    widget._manual_run_desc_edit.setText("typed in manual")
    assert widget._guided_run_desc_edit.text() == "typed in manual"

    widget._guided_run_desc_edit.setText("typed in guided")
    assert widget._manual_run_desc_edit.text() == "typed in guided"


def test_filling_the_fields_from_disk_is_not_treated_as_typing(tab):
    """The write-back is driven by the fields' own signals, so loading without
    a guard would save run 1's text into run 2 on the way past."""
    widget, ctl, project = tab
    ctl.set_run_type(RUN_TYPE_PROFILING)
    ctl.set_profile_run("run1")
    widget._refresh_target_text()
    _type(widget, "run one only", "")

    ctl.set_profile_run("run2")
    widget._refresh_target_text()          # fills the boxes with run 2's (empty)
    assert project.run("run1").load_meta().description == "run one only", (
        "run 1's stored text changed while merely looking at run 2"
    )


# ---- T2.7: nowhere to write yet -----------------------------------------
def test_typing_before_the_run_exists_does_not_raise(tab):
    """A description typed for a run that does not exist yet is kept in the
    field and written when the run is created — nothing is lost, and nothing
    raises."""
    widget, ctl, project = tab
    ctl.set_profile_run("")                 # "New run"
    widget._refresh_target_text()
    _type(widget, "for a run that is not there yet", "")
    assert widget._manual_run_desc_edit.text() == "for a run that is not there yet"
