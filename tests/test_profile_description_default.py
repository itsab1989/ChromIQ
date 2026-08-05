"""#130 §4 / §4a — the Profile Description default, and who owns the field.

Two things, and the first is a **pre-existing bug** this work had to fix before
it could build on the field at all:

* ``set_ti3_path`` overwrote BOTH description fields unconditionally, so a
  description the user had typed was lost the moment a measurement was loaded
  or handed over from Measure. The consequence analysis promised the opposite —
  *"the moment you type in it yourself, it is yours and is never rewritten"* —
  and cited a line that turned out to be printcal's field, not colprof's.
* The default itself becomes ``<project>-<run>-<calibration>``, with any empty
  part dropping out **along with its separator** (Knut, §4a).
"""
from __future__ import annotations

import pytest


@pytest.fixture
def tab(qapp, tmp_path):
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_profile import TabProfile

    class _Settings(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            if key == "calibration_mode":
                return True
            return super().get(key, default)

    st = _Settings()
    fm = FileManager(st)
    fm.set_target_name("Desc-Project")
    project = fm.project()
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    widget = TabProfile(ArgyllRunner(st), st, None)
    widget.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    return widget, ctl, project


def _run_description(project, text):
    run = project.run("run1")
    meta = run.load_meta()
    meta.description = text
    run.save_meta(meta)


def _cal_description(project, text):
    from core.file_manager import CalibrationMeta

    project.calibration.save_meta(CalibrationMeta(description=text))


# ---- §4a: what it is built from -----------------------------------------
def test_the_default_is_project_and_run_description(tab):
    widget, ctl, project = tab
    _run_description(project, "PhotoRag gloss")
    widget._apply_profile_description_default()
    assert widget._m_desc_edit.text() == "Desc-Project-PhotoRag gloss"


def test_an_empty_run_description_drops_out_with_its_separator(tab):
    """T6.14 — an unnamed part must not leave a trailing hyphen."""
    widget, ctl, project = tab
    _run_description(project, "")
    widget._apply_profile_description_default()
    assert widget._m_desc_edit.text() == "Desc-Project"
    assert not widget._m_desc_edit.text().endswith("-")


def test_a_calibration_that_is_not_used_is_not_named(tab):
    """T6.12 — a calibration that merely EXISTS did not go into this profile."""
    widget, ctl, project = tab
    _run_description(project, "gloss")
    _cal_description(project, "Canson Baryta")
    widget._apply_profile_description_default()
    assert "Canson Baryta" not in widget._m_desc_edit.text(), (
        "the profile is named after a calibration it was not built with"
    )


def test_a_calibration_that_was_used_is_named(tab):
    """T6.13 — recorded in the run's meta by #137 as calibration_used."""
    widget, ctl, project = tab
    _run_description(project, "gloss")
    _cal_description(project, "Canson Baryta")
    run = project.run("run1")
    meta = run.load_meta()
    meta.calibration_used = "Desc-Project-cal"
    run.save_meta(meta)
    widget._apply_profile_description_default()
    assert widget._m_desc_edit.text() == "Desc-Project-gloss-Canson Baryta"


# ---- §4: who owns the field ---------------------------------------------
def test_the_users_own_text_is_never_overwritten(tab):
    """T6.21 — the promise the consequence analysis made, now true."""
    widget, ctl, project = tab
    _run_description(project, "gloss")
    widget._apply_profile_description_default()
    widget._m_desc_edit.setText("My Own Name For This")
    widget._desc_edit.setText("My Own Name For This")

    _run_description(project, "matte")            # a trigger fires
    widget._apply_profile_description_default()
    assert widget._m_desc_edit.text() == "My Own Name For This"


def test_chromiqs_own_default_is_replaced(tab):
    """T6.20 — while it is still ours, it follows what it is made of."""
    widget, ctl, project = tab
    _run_description(project, "gloss")
    widget._apply_profile_description_default()
    assert widget._m_desc_edit.text() == "Desc-Project-gloss"

    _run_description(project, "matte")
    widget._apply_profile_description_default()
    assert widget._m_desc_edit.text() == "Desc-Project-matte"


def test_clearing_the_field_by_hand_gives_it_back(tab):
    """T6.22 — an empty field is ours again."""
    widget, ctl, project = tab
    _run_description(project, "gloss")
    widget._apply_profile_description_default()
    widget._m_desc_edit.setText("mine")
    widget._desc_edit.setText("")
    widget._m_desc_edit.setText("")
    widget._apply_profile_description_default()
    assert widget._m_desc_edit.text() == "Desc-Project-gloss"


def test_loading_a_measurement_no_longer_overwrites_your_text(tab, tmp_path):
    """The pre-existing bug: set_ti3_path replaced both fields unconditionally."""
    widget, ctl, project = tab
    widget._m_desc_edit.setText("My Own Name For This")
    widget._desc_edit.setText("My Own Name For This")

    ti3 = tmp_path / "some-measurement.ti3"
    ti3.write_text("CGATS.17\n")
    widget.set_ti3_path(ti3, propagate=False)

    assert widget._m_desc_edit.text() == "My Own Name For This", (
        "loading a measurement overwrote the description the user typed"
    )


def test_loading_a_measurement_still_names_an_untouched_field(tab, tmp_path):
    """…and the old behaviour survives where the field is still ours."""
    widget, ctl, project = tab
    ti3 = tmp_path / "some-measurement.ti3"
    ti3.write_text("CGATS.17\n")
    widget.set_ti3_path(ti3, propagate=False)
    assert widget._m_desc_edit.text() != ""
