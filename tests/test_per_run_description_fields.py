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


# ---- 2026-08-13: the two bugs Knut and Sebastian hit the same afternoon ---
def test_first_generate_of_a_new_project_keeps_the_typed_text(qapp, tmp_path):
    """Fresh start, no project: name the project, type a description, press
    Generate. The first build CREATES the project — and the text typed before
    that moment must land in run1's meta, not be wiped by the post-generate
    reload (Knut + Sebastian, both hit it on 2026-08-13). The "New run"
    flush of beta.147 covered a new run inside an existing project; this is
    the same rule for the project that does not exist yet."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    class _Settings(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            return super().get(key, default)

    st = _Settings()
    fm = FileManager(st)
    fm.set_target_name("Fresh-Project")     # named, but never created
    ctl = MeasurementTargetController(fm)
    widget = TabChart(ArgyllRunner(st), fm, st, None)
    widget.set_target_controller(ctl)

    _type(widget, "typed before the project existed", "and these notes too")
    assert widget._new_run_text is not None, "nowhere to write yet → held"
    assert not (tmp_path / "Fresh-Project" / "project.json").exists()

    # The moment _on_generate reaches for a build that is NOT into a loaded
    # project — the real handler calls exactly this, before the build runs.
    widget._seed_new_project_text(False)

    run1 = fm.project().current_run()
    meta = run1.load_meta()
    assert meta.description == "typed before the project existed"
    assert meta.chart_notes == "and these notes too"
    assert widget._new_run_text is None, "the text has a home now"
    # …and the reload that used to wipe the fields now finds the text.
    widget._refresh_target_text()
    assert widget._manual_run_desc_edit.text() == \
        "typed before the project existed"


def test_the_generate_path_actually_calls_the_seed(qapp):
    """The seed helper is only worth anything if _on_generate reaches it on
    the new-project branch — pin the wiring, not just the helper."""
    import inspect

    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_generate)
    assert "_seed_new_project_text" in src
    assert src.index("_builds_into_project") \
        < src.index("_seed_new_project_text"), \
        "the seed must run on the not-same-project branch"


def test_the_two_name_fields_are_one_value(tab):
    """Knut, 2026-08-13: "the main profile project name did not follow to the
    manual mode. There should be a direct link between the guided and manual
    for this field." Typed in either mode, the other shows it — before any
    project exists, which is the window where nothing else fills them."""
    widget, _ctl, _project = tab
    widget._target_name_edit.setText("Typed-In-Guided")
    assert widget._manual_target_name_edit.text() == "Typed-In-Guided"
    widget._manual_target_name_edit.setText("Renamed-In-Manual")
    assert widget._target_name_edit.text() == "Renamed-In-Manual"


def test_first_generate_of_a_new_project_seeds_its_settings(qapp, tmp_path):
    """The instrument flip Sebastian watched live (2026-08-13): run1 of a
    brand-new project was born with nothing stored, so §4's "nothing stored
    opens on its defaults" reset the screen — ColorMunki became i1Pro — the
    moment the post-generate load arrived. The seed writes the screen's
    settings into the fresh run before anything can read it back."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    class _Settings(AppSettings):
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            return super().get(key, default)

    st = _Settings()
    fm = FileManager(st)
    fm.set_target_name("Fresh-Settings")
    ctl = MeasurementTargetController(fm)
    widget = TabChart(ArgyllRunner(st), fm, st, None)
    widget.set_target_controller(ctl)
    combo = widget._instr_combo
    combo.setCurrentIndex(next(i for i in range(combo.count())
                               if combo.itemData(i) == "CM"))

    widget._seed_new_project_text(False)     # what _on_generate calls

    meta = fm.project().current_run().load_meta()
    stored = meta.create_chart_settings or {}
    assert stored, "run1 must be born with the screen's settings"
    import json
    assert '"CM"' in json.dumps(stored), \
        "the seeded settings must carry the instrument on screen"


def test_save_as_defaults_leaves_the_project_name_out(qapp, tmp_path):
    """Sebastian, 2026-08-13: Save as Defaults stored the current project
    name, so every future fresh start opened seeded with an old project's
    name — one Generate away from building into it. Every knob is a
    preference; the name is the project's identity, and the stored key is
    reset so older saves stop leaking too.

    It resets to EMPTY, not to the factory seed "ChromIQ Test Chart" that this
    test originally asserted (Basti, #164 Q15). The seed was itself the bug:
    it put "Location being edited: …/ChromIQ-Test-Chart/runs/run1/" on screen
    with no project open. The rule this test exists to defend — a project name
    is never persisted — is unchanged and now stricter."""
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    class _Settings(AppSettings):
        def __init__(self):
            super().__init__()
            self.written = {}
        def get(self, key, default=None):
            if key == "custom_output_path":
                return str(tmp_path)
            return self.written.get(key, super().get(key, default))
        def set(self, key, value):
            self.written[key] = value

    st = _Settings()
    fm = FileManager(st)
    fm.set_target_name("My-Precious-Project")
    ctl = MeasurementTargetController(fm)
    widget = TabChart(ArgyllRunner(st), fm, st, None)
    widget.set_target_controller(ctl)
    widget._target_name_edit.setText("My-Precious-Project")

    widget._on_save_defaults()

    assert not st.written.get("chart_target_name"), \
        "the name must be cleared, never saved"
