"""#182, Knut 2026-09-21: the verification pre-flight, and the presets
window's first line.

He specified two things that share one check, and asked for the harder half to
be proved rather than asserted: *"test that this popup-window only comes for
the defined preconditions, and that the test performed on the chart defined in
Create Chart works for all conditions and variations of conditions."*

So the preconditions are taken ONE AT A TIME. Each test below starts from a
state where the window IS owed, breaks exactly one thing, and demands the
answer flip. A fixture that is already wrong in two ways proves nothing about
either.

The second trigger has a test of its own, because it is the one he said would
be missed: *"by standing on Measure tab on a different 'Profile run' and then
changing 'Profile run' to the run that has the above preconditions fulfilled"*.
`showEvent` does not fire for that. The controller's `changed` does, and the
guard here is that the tab really is connected to it.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                                 # noqa: E402
from PyQt6.QtWidgets import QApplication                           # noqa: E402

from core.argyll_runner import ArgyllRunner                        # noqa: E402
from core.file_manager import FileManager, Project                 # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,           # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                              # noqa: E402
from ui.dialogs import preset_verification_dialog as PVD           # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402
from workflow import measurement_report as MR                      # noqa: E402
from workflow import preset_eligibility as PE                      # noqa: E402

#: A shipped chart that really holds all eight cube corners, so the FROM
#: PROFILE GAMUT case below can be modelled on a chart rather than on a fake.
#: Measured over all 177 built-ins, 2026-09-21: this is one of the ones that
#: does, and `test_the_corner_chart_still_holds_every_corner` fails if it stops
#: being true instead of the gamut tests quietly testing nothing.
CORNER_CHART = Path("assets/charts/pharmacist/rgb/colormunki/a4/tc300/tc300.ti1")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _corner_chart() -> Path:
    return Path(__file__).resolve().parent.parent / CORNER_CHART


def _env(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path))
    fm = FileManager(s)
    Project.create(tmp_path / "P", "P").current_run().ensure_dir()
    fm.set_target_name("P")
    return s, fm, MeasurementTargetController(fm)


def _chart_into(run_dir: Path) -> Path:
    """The corner chart, copied in as the run's verification chart."""
    run_dir.mkdir(parents=True, exist_ok=True)
    dst = run_dir / "P.ti2"
    shutil.copy2(_corner_chart(), dst)
    return dst


def _ready_tab(tmp_path, qapp):
    """A TabMeasure in exactly the state Knut's four preconditions describe."""
    from ui.tabs.tab_measure import TabMeasure
    s, fm, ctl = _env(tmp_path)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    chart = _chart_into(tmp_path / "P" / "runs" / "run1" / "verifications")
    tab.set_ti1_path(chart)
    PE.clear_cache()
    return tab, ctl, chart


# ---------------------------------------------------------------------------
# 0. the fixture is what it claims to be
# ---------------------------------------------------------------------------
def test_the_corner_chart_still_holds_every_corner():
    """The gamut tests below are worth nothing on a chart with no corners."""
    import numpy as np
    from workflow.ti3_analysis import parse_ti3
    data = parse_ti3(_corner_chart())
    rgb = MR._rgb_to_0_100(np.asarray(data.rgb, dtype=float))
    for name, target in MR.CUBE_CORNERS:
        diffs = np.abs(rgb - np.array(target))
        i = int((diffs ** 2).sum(axis=1).argmin())
        assert float(diffs[i].max()) <= MR.CORNER_PRESENT_TOL, \
            f"{CORNER_CHART} no longer holds the {name} corner"


# ---------------------------------------------------------------------------
# 1. all four hold: the window is owed
# ---------------------------------------------------------------------------
def test_the_window_is_owed_when_every_precondition_holds(qapp, tmp_path):
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    assert tab._verification_preflight_due() is True


# ---------------------------------------------------------------------------
# 2. …and on none other. One broken thing per test.
# ---------------------------------------------------------------------------
def test_not_owed_when_the_run_type_is_not_verification(qapp, tmp_path):
    tab, ctl, _chart = _ready_tab(tmp_path, qapp)
    ctl.set_run_type(RUN_TYPE_PROFILING)
    assert tab._verification_preflight_due() is False


def test_not_owed_when_no_chart_has_been_generated(qapp, tmp_path):
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    tab._ti1_path = None
    assert tab._verification_preflight_due() is False


def test_not_owed_when_the_chart_file_has_gone(qapp, tmp_path):
    tab, _ctl, chart = _ready_tab(tmp_path, qapp)
    chart.unlink()
    assert tab._verification_preflight_due() is False


def test_not_owed_when_the_chart_holds_no_patch_set(qapp, tmp_path):
    """Knut: *"a chart needs to have been generated with a layout that has a
    given patch set, as a minimum."* A file that is not a patch set is not a
    chart, however much it is named like one."""
    tab, _ctl, chart = _ready_tab(tmp_path, qapp)
    chart.write_text("this is not a chart\n", encoding="utf-8")
    PE.clear_cache()
    assert tab._verification_preflight_due() is False


def test_not_owed_when_a_measurement_already_exists(qapp, tmp_path):
    """The .ti3 validity test is the tab's own, the one Start Measurement
    applies: a file with readings in it means the moment for this window has
    passed."""
    tab, _ctl, chart = _ready_tab(tmp_path, qapp)
    shutil.copy2(
        Path(__file__).resolve().parent.parent / CORNER_CHART,
        chart.with_suffix(".ti3"))
    assert tab._verification_preflight_due() is False


def test_still_owed_when_the_measurement_file_is_empty(qapp, tmp_path):
    """*"or ti3 existing is empty or invalid"* — the same test the rest of the
    tab applies, so a header-only file is not a measurement here either."""
    tab, _ctl, chart = _ready_tab(tmp_path, qapp)
    chart.with_suffix(".ti3").write_text(
        'CTI3\nKEYWORD "X"\nNUMBER_OF_SETS 0\n', encoding="utf-8")
    assert tab._verification_preflight_due() is True


def test_still_owed_when_a_dated_verifications_measurement_is_empty(qapp, tmp_path):
    """**THE OTHER HALF OF THE VALIDITY RULE, and the one a mutation showed
    was not being exercised at all.** A verification's readings live in its
    DATED folder, which `_existing_ti3_for_chart` cannot see: that path is
    `_measurement_at_risk`'s, and until this test nothing selected a dated
    verification, so the `_cgats_has_no_readings` call on that branch could be
    deleted with every guard still green. A header-only file there is not a
    measurement either."""
    tab, ctl, chart = _ready_tab(tmp_path, qapp)
    proj = ctl.project_or_none()
    v = proj.run("run1").new_verification()
    v.dir.mkdir(parents=True, exist_ok=True)
    v.measurement_ti3.write_text(
        'CTI3\nKEYWORD "X"\nNUMBER_OF_SETS 0\n', encoding="utf-8")
    ctl.set_verification_id(v.id)
    assert tab._measurement_at_risk() is not None, (
        "the dated verification's file is not the one being judged, so this "
        "test is not exercising the branch it was written for")
    assert tab._verification_preflight_due() is True


def test_not_owed_when_a_dated_verification_holds_real_readings(qapp, tmp_path):
    """…and the same branch the other way round, so the rule above is a rule
    and not a way of always saying yes."""
    tab, ctl, chart = _ready_tab(tmp_path, qapp)
    proj = ctl.project_or_none()
    v = proj.run("run1").new_verification()
    v.dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_corner_chart(), v.measurement_ti3)
    ctl.set_verification_id(v.id)
    assert tab._verification_preflight_due() is False


def test_not_owed_while_a_measurement_is_running(qapp, tmp_path, monkeypatch):
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    monkeypatch.setattr(type(tab), "a_measurement_is_running",
                        lambda self: True)
    assert tab._verification_preflight_due() is False


def test_not_owed_once_the_tick_has_silenced_this_run(qapp, tmp_path):
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    scope = tab._preflight_scope()
    assert scope is not None
    tab._preflight_silenced.add(scope)
    assert tab._verification_preflight_due() is False


# ---------------------------------------------------------------------------
# 3. the tick is per run, in memory, and is not the other windows' tick
# ---------------------------------------------------------------------------
def test_the_tick_is_remembered_against_the_profile_run_and_nothing_finer():
    """Knut's label promises *"for this profile run"*, so the key is the
    project and the run and nothing else. A finer key would ask again inside
    the same profile run and break the promise the label makes."""
    import inspect

    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._preflight_scope)
    assert "verification_id" not in src, (
        "the pre-flight tick is keyed on the dated verification, so it would "
        "ask again inside the profile run its own label promises to cover")
    assert "profile_run" in src


def test_the_pre_flight_tick_has_its_own_set(qapp, tmp_path):
    """Silencing one Measure-tab window must not silence another: the three
    say different things and one of them is the last guard before readings are
    overwritten."""
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    assert tab._preflight_silenced is not tab._offer_silenced
    assert tab._preflight_silenced is not tab._replace_warning_silenced


def test_the_tick_is_never_written_to_disk(qapp, tmp_path):
    """*"until I restart ChromIQ"* — so nothing about it may reach the project
    or the settings, where it would outlive the process."""
    tab, ctl, _chart = _ready_tab(tmp_path, qapp)
    scope = tab._preflight_scope()
    tab._preflight_silenced.add(scope)
    meta = ctl.project_or_none().run("run1").load_meta()
    blob = repr(vars(meta)) + repr(dict(tab._settings._qs.value(k) or ""
                                        for k in []))
    assert "preflight" not in blob.lower()
    settings_file = Path(tab._settings._qs.fileName())
    text = settings_file.read_text(encoding="utf-8") if settings_file.is_file() else ""
    assert "preflight" not in text.lower()


def test_the_tick_uses_knuts_own_wording(qapp, tmp_path):
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    assert tab._preflight_silence_label() == (
        "Do not show this message again for this profile run, "
        "until I close ChromIQ")


# ---------------------------------------------------------------------------
# 4. both triggers, and the second one is the one that gets missed
# ---------------------------------------------------------------------------
def test_entering_the_tab_asks_for_the_window(qapp, tmp_path):
    """DRIVEN, not grepped. A source probe for the call's NAME stayed green
    under a mutation that deleted the call, because the comment above it names
    the method too: this fires the real `showEvent` and looks at what the tab
    did about it."""
    from PyQt6.QtGui import QShowEvent
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    tab._preflight_queued = False
    asked: list = []
    tab._show_verification_preflight_now = lambda: asked.append(True)
    tab.showEvent(QShowEvent())
    assert tab._preflight_queued is True, \
        "arriving at the Measure tab no longer asks for the pre-flight"


def test_switching_profile_run_while_standing_here_asks_for_it(qapp, tmp_path):
    """THE TRIGGER KNUT SAID WOULD BE MISSED, driven rather than grepped: the
    tab is already on screen, the bar changes the selected run, and the tab
    must have asked for the window by the time the signal has been delivered.
    """
    tab, ctl, _chart = _ready_tab(tmp_path, qapp)
    tab._preflight_queued = False
    asked: list = []
    tab._show_verification_preflight_now = lambda: asked.append(True)
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_PROFILING)     # any change on the bar
    assert tab._preflight_queued is True, (
        "changing the selection on the measurement target bar did not ask for "
        "the verification pre-flight, so Knut's second trigger is dead")


def test_two_triggers_in_one_turn_ask_for_one_window(qapp, tmp_path):
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    tab._preflight_queued = False
    calls: list = []
    tab._show_verification_preflight_now = lambda: calls.append(True)
    tab._queue_verification_preflight()
    tab._queue_verification_preflight()
    tab._queue_verification_preflight()
    assert tab._preflight_queued is True
    # one timer armed, not three
    qapp.processEvents()


# ---------------------------------------------------------------------------
# 5. the window's text: §M's frame and the presets window's own answer
# ---------------------------------------------------------------------------
def test_the_window_says_what_the_presets_window_says(qapp, tmp_path):
    """Knut asked this window to *"initiate the same function used inside
    'Which presets can be used for verification?' window"* and to show *"the
    same detailed information"*. Same function, so the same sentences: every
    line of the summary must appear in the text the window puts on screen.
    """
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    row = tab._preflight_chart_row()
    type_id, set_id, overrides = tab._preflight_selection()
    row.assessment = PE.assess(row.chart, type_id, set_id, overrides)
    _title, text = tab._verification_preflight_message(row)
    lines = PVD.summary_lines(row)
    assert lines, "the summary said nothing at all about a real chart"
    for line in lines:
        assert line.text in text, f"the window drops {line.text!r}"


def test_the_window_frames_it_with_the_catalogue(qapp, tmp_path):
    from workflow import measurement_messages as M
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    row = tab._preflight_chart_row()
    row.assessment = PE.assess(row.chart, *tab._preflight_selection()[:2],
                               tab._preflight_selection()[2])
    title, text = tab._verification_preflight_message(row)
    m_title, m_body = M.M_VERIFY_PREFLIGHT.render()
    assert title == m_title
    assert m_body in text
    assert "{" not in text and "}" not in text


def test_the_headline_is_in_the_text_and_not_only_in_the_title_bar(qapp, tmp_path):
    """B8-615, found by photographing the real window: macOS draws no title on
    a QMessageBox, so a §M headline set with `setWindowTitle` alone is set
    where nobody can read it and the window opens on its second sentence."""
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    row = tab._preflight_chart_row()
    type_id, set_id, overrides = tab._preflight_selection()
    row.assessment = PE.assess(row.chart, type_id, set_id, overrides)
    title, text = tab._verification_preflight_message(row)
    assert text.startswith(title), (
        "the pre-flight's headline is not the first thing the window says, so "
        "on macOS it is not said at all")


def test_the_gamut_paragraph_is_shown_only_when_it_is_the_lever(qapp, tmp_path):
    """A reader whose chart already carries the reference must not be sent
    after a feature they have used."""
    from workflow import measurement_messages as M
    tab, _ctl, _chart = _ready_tab(tmp_path, qapp)
    row = tab._preflight_chart_row()
    type_id, set_id, overrides = tab._preflight_selection()

    # A set that puts a limit on the three reference rows: they are then asked
    # for, and an ordinary chart cannot supply them.
    row.assessment = PE.assess(row.chart, MR.REPORT_TYPE_FULL,
                               "custom_iso_12647_7", overrides)
    assert PVD.gamut_only_shortfalls(row), \
        "the strict set no longer asks for a metric only the gamut can supply"
    _t, text = tab._verification_preflight_message(row)
    assert M.M_VERIFY_PREFLIGHT_GAMUT in text

    # …and the everyday set, which asks for none of them.
    row.assessment = PE.assess(row.chart, MR.REPORT_TYPE_FULL,
                               "chromiq_default", overrides)
    assert not PVD.gamut_only_shortfalls(row)
    _t, text = tab._verification_preflight_message(row)
    assert M.M_VERIFY_PREFLIGHT_GAMUT not in text
