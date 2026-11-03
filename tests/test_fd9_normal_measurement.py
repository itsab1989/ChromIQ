"""Native FD9 chart association, filing, worker cancellation and tab routing."""

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
import json, shutil
from pathlib import Path
from unittest.mock import patch
import pytest
from PyQt6.QtCore import QSettings
from core.argyll_runner import ArgyllRunner
from core.settings import AppSettings
from core import instrument_lease
from workflow.fd9.measurement import (
    prepare_chart,
    checked_chart,
    first_table,
    stamp_locations,
    publish_measurement,
    measure_chart,
    FD9Settings,
)
from ui.fd9_measurement import FD9Job

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def chart(tmp_path):
    layout = {
        "color_rep": "CMYK",
        "channel_tokens": ["C", "M", "Y", "K"],
        "fiducials_mm": [[9.5, 32.5], [127.5, 32.5], [9.5, 267.5], [127.5, 267.5]],
        "rows": [
            [
                {
                    "id": r * 12 + c + 1,
                    "centre_mm": [19 + 9 * c, 42 + 9 * r],
                    "device_values": [r * 20, c * 5, 0, 0],
                }
                for c in range(12)
            ]
            for r in range(3)
        ],
    }
    p = tmp_path / "layout.json"
    p.write_text(json.dumps(layout), encoding="utf-8")
    return prepare_chart(p, tmp_path / "chart")


def test_chart_ids_locations_and_renamed_sidecar_travel(chart, tmp_path):
    _, layout, locations = checked_chart(chart)
    assert locations[13] == "A2"
    from workflow.chart_import import _copy_chart_set

    dest = tmp_path / "imported"
    dest.mkdir()
    _copy_chart_set(
        chart, chart.with_suffix(".ti1"), [], dest, "renamed", include_measurement=False
    )
    assert checked_chart(dest / "renamed.ti2")[1] == layout


def test_chart_mismatch_is_rejected_before_device_access(chart):
    p = chart.with_suffix(".fd9.json")
    j = json.loads(p.read_text(encoding="utf-8"))
    j["rows"][1][1]["device_values"][0] += 1
    p.write_text(json.dumps(j), encoding="utf-8")
    with pytest.raises(ValueError, match="ink values"):
        checked_chart(chart)


def test_atomic_filing_archives_old_and_refuses_incomplete(chart, tmp_path):
    text, fields, rows = first_table(chart)
    locations = {int(r["SAMPLE_ID"]): r["SAMPLE_LOC"] for r in rows}
    # Start with actual non-placeholder XYZ, not design estimates.
    text = text.replace("CTI2", "CTI3", 1).replace(" 0 0 0\n", " 10 20 30\n")
    plain = tmp_path / "plain.ti3"
    plain.write_text(text, encoding="utf-8")
    from workflow.measurement_state import classify, Ti3State

    assert classify(plain, chart).state == Ti3State.COMPLETE
    target = chart.with_suffix(".ti3")
    target.write_bytes(b"previous measurement")
    publish_measurement(plain, target, chart)
    assert target.read_bytes() == plain.read_bytes()
    assert [p.read_bytes() for p in (chart.parent / "old").rglob("*.ti3")] == [
        b"previous measurement"
    ]
    bad = tmp_path / "bad.ti3"
    bad.write_text("CTI3\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n", encoding="utf-8")
    with pytest.raises(ValueError):
        publish_measurement(bad, target, chart)
    assert target.read_bytes() == plain.read_bytes()


def test_worker_reports_cancellation_without_result(qtbot, tmp_path):
    def stopped(*args, **kwargs):
        assert kwargs["cancelled"]()
        raise RuntimeError("stopped")

    worker = FD9Job(tmp_path, None, tmp_path, action=stopped)
    worker.request_stop()
    with qtbot.waitSignal(worker.failed, timeout=2000) as sig:
        worker.start()
    worker.wait(2000)
    assert sig.args == ["stopped", True]


@pytest.fixture
def tab(qapp, tmp_path):
    from ui.tabs.tab_measure import TabMeasure

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "app.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("fd9_host", "test-host")
    t = TabMeasure(ArgyllRunner(s), s)
    yield t
    instrument_lease.release(t)
    t.close()
    t.deleteLater()


def test_normal_start_routes_fd9_and_does_not_start_argyll(tab, chart):
    tab.set_ti1_path(chart.with_suffix(".ti1"))
    assert not tab._fd9_panel.isHidden()
    with (
        patch.object(tab, "_start_fd9_measurement") as fd9,
        patch.object(tab._manager, "start") as argyll,
    ):
        tab._on_start()
        fd9.assert_called_once()
        argyll.assert_not_called()
    tab.set_ti1_path(chart.parent / "other.ti1")
    assert tab._fd9_panel.isHidden()


def test_stop_and_quit_wait_for_fd9_worker(tab):
    class Job:
        stopped = False

        def request_stop(self):
            self.stopped = True

    job = Job()
    tab._fd9_job = job
    tab._fd9_live = True
    assert tab.a_measurement_is_running()
    tab._on_stop()
    assert job.stopped
    assert tab.confirm_quit_during_measurement() is False
    tab._fd9_live = False


def test_fd9_condition_round_trips_and_driver_is_automatic(tab, chart):
    from workflow.measure_settings import snapshot, apply

    # Stored for an FD-9 chart only (review M1): load one first.
    tab.set_ti1_path(chart.with_suffix(".ti1"))
    tab._fd9_condition.setCurrentText("M2")
    saved = snapshot(tab)
    tab._restore_defaults()
    assert (
        tab._fd9_condition.currentText() == "M1" and tab._fd9_settings().allow_research
    )
    apply(tab, saved)
    assert tab._fd9_condition.currentText() == "M2" and tab._fd9_settings().allow_research
    assert not hasattr(tab, "_fd9_research")


def test_fd9_keep_awake_release_is_balanced_on_failure(tab):
    with patch("ui.fd9_measurement.keep_awake.release") as release:
        tab._fd9_awake = True
        tab._fd9_failed("test failure", False)
        tab._fd9_restore_controls()
        release.assert_called_once()


@pytest.mark.parametrize("condition", ["M0", "M1", "M2"])
def test_native_worker_files_synthetic_complete_chart_without_private_assets(
    tab, chart, tmp_path, qtbot, monkeypatch, condition
):
    """Portable GUI-to-project coverage; synthetic XYZ, no instrument or SDK."""
    tab.set_ti1_path(chart.with_suffix(".ti1"))
    tab._fd9_condition.setCurrentText(condition)
    monkeypatch.setattr(FD9Settings, "validate", lambda self: None)
    from workflow.fd9.measurement import sha

    def action(chart, settings, session, **kwargs):
        session.mkdir(parents=True)
        assert settings.condition == condition
        text = (
            chart.read_text(encoding="utf-8")
            .replace("CTI2", 'CTI3\nMEASUREMENT_CONDITION "' + condition + '"', 1)
            .replace(" 0 0 0\n", " 10 20 30\n")
        )
        staged = session / "measurement.ti3"
        staged.write_text(text, encoding="utf-8")
        return {
            "staged": str(staged),
            "destination": str(chart.with_suffix(".ti3")),
            "chart": str(chart),
            "chart_sha256": sha(chart),
            "profile_sha256": None,
            "conversion_source": "instrument_firmware",
        }

    monkeypatch.setattr(
        "ui.fd9_measurement.FD9Job",
        lambda chart, settings, session, parent: FD9Job(
            chart, settings, session, parent, action=action
        ),
    )
    monkeypatch.setattr(
        tab._manager,
        "start",
        lambda *a, **k: pytest.fail("Native FD9 must bypass chartread"),
    )
    with qtbot.waitSignal(tab.measure_finished, timeout=5000) as saved:
        tab._on_start()
    qtbot.waitUntil(lambda: not tab._fd9_job.isRunning(), timeout=2000)
    assert saved.args[0] == chart.with_suffix(".ti3")
    assert len(first_table(saved.args[0])[2]) == 36
    assert (
        not tab._fd9_live and not tab._fd9_awake and instrument_lease.holder() is None
    )


def test_legacy_profile_api_retains_its_condition_guard(tab, tmp_path, monkeypatch):
    from types import SimpleNamespace

    assert [
        tab._fd9_condition.itemText(i) for i in range(tab._fd9_condition.count())
    ] == ["M0", "M1", "M2"]
    assert tab._fd9_condition.currentText() == "M1"
    settings = FD9Settings(
        None,
        tmp_path / "profile",
        tmp_path / "ill",
        tmp_path / "obs",
        "test-host",
        "M0",
        True,
    )
    fake = SimpleNamespace(
        ConversionProfile=SimpleNamespace(
            load=lambda path: SimpleNamespace(
                conditions={"M1": 1, "M2": 2}, host="test-host"
            )
        )
    )
    monkeypatch.setattr("workflow.fd9.measurement.driver", lambda source: fake)
    with pytest.raises(ValueError, match="not calibrated"):
        settings.validate()


def test_native_keep_measuring_does_not_cancel_or_send_argyll_keys(tab):
    from types import SimpleNamespace

    job = SimpleNamespace(
        new_readings=12, request_stop=lambda: pytest.fail("Keep must not cancel")
    )
    tab._fd9_job = job
    tab._fd9_live = True
    with patch.object(tab, "_confirm_end_of_session", return_value=None) as ending:
        tab._on_stop()
        ending.assert_called_once_with(tab.END_STOP)
    assert tab._fd9_live and tab._fd9_choice is None
    tab._fd9_live = False


def test_native_ending_counts_do_not_come_from_the_argyll_manager(tab, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    seen = []

    def choose_save(box):
        seen.append(box.text())
        for button in box.buttons():
            if "Save and stop" in button.text():
                button.click()
                break
        return 0

    tab._fd9_live = True
    tab._fd9_readings = 24
    monkeypatch.setattr(QMessageBox, "exec", choose_save)
    assert tab._confirm_end_of_session(tab.END_STOP) == "save"
    assert "24" in seen[0]
    tab._fd9_live = False


def test_native_discard_keeps_previous_file_and_closes_pending_state(
    tab, chart, tmp_path
):
    target = chart.with_suffix(".ti3")
    target.write_text("prior canonical", encoding="utf-8")
    tab.set_ti1_path(chart.with_suffix(".ti1"))
    tab._fd9_pending = {"staged": str(tmp_path / "unfiled.ti3"), "patches": 12}
    tab._fd9_readings = 12
    with patch.object(tab, "_confirm_end_of_session", return_value="discard"):
        assert tab.confirm_quit_during_measurement()
    assert (
        tab._fd9_pending is None
        and target.read_text(encoding="utf-8") == "prior canonical"
    )


def test_finish_while_stop_question_is_open_honours_discard(tab, chart, tmp_path):
    from types import SimpleNamespace
    import threading

    target = chart.with_suffix(".ti3")
    target.write_text("old", encoding="utf-8")
    tab.set_ti1_path(chart.with_suffix(".ti1"))
    event = threading.Event()
    tab._fd9_live = True
    tab._fd9_job = SimpleNamespace(
        new_readings=12, stop_event=event, request_stop=event.set
    )

    def answer(how):
        tab._fd9_result({"patches": 36, "staged": "not filed"})
        return "discard"

    with patch.object(tab, "_confirm_end_of_session", side_effect=answer):
        tab._on_stop()
    assert target.read_text(encoding="utf-8") == "old"
    assert not tab._fd9_live and tab._fd9_deferred is None


def test_quit_during_cooperative_stop_does_not_offer_keep_again(tab):
    import threading
    from types import SimpleNamespace

    event = threading.Event()
    event.set()
    tab._fd9_live = True
    tab._fd9_choice = "save"
    tab._fd9_job = SimpleNamespace(stop_event=event)
    with patch.object(
        tab,
        "_confirm_end_of_session",
        side_effect=AssertionError("Stop already in progress"),
    ):
        assert not tab.confirm_quit_during_measurement()
    tab._fd9_live = False


def test_quit_waits_for_qthread_after_its_result_has_been_filed(tab, monkeypatch):
    from types import SimpleNamespace

    job = SimpleNamespace(isRunning=lambda: True)
    tab._fd9_job = job
    tab._fd9_live = False
    tab._fd9_pending = None

    def unexpected_question(how):
        raise AssertionError("No readings remain to ask about")

    monkeypatch.setattr(tab, "_confirm_end_of_session", unexpected_question)
    assert tab.a_measurement_is_running()
    assert not tab.confirm_quit_during_measurement()
    job.isRunning = lambda: False
    assert not tab.a_measurement_is_running()
    assert tab.confirm_quit_during_measurement()
