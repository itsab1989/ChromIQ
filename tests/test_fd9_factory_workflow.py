"""Portable invented factory-native wire; no unit data or vendor code/fixtures."""

import hashlib
import json
import struct
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_fd9_partial import setup, capture as raw_fixture
from workflow.fd9.measurement import (
    measure_chart,
    first_table,
    resume_plan,
    publish_measurement,
)
from workflow.fd9.independent import CaptureFailed
from workflow.fd9.native_evidence import verified_native_rows
from workflow.fd9.native_export import native_colour, colour_data


def fixture_native(s, root, selected, n, complete=False):
    from fd9_independent.factory import (
        RECORD_SIZES,
        SensorFactoryRecord,
        FactoryCharacterization,
    )
    from fd9_independent.native import (
        NativeMeasurement,
        NativeSpectrum,
        NativeCondition,
    )
    from fd9_independent.sensor_data import CachedSensorData, cached_data_request
    from fd9_independent.motion import line_command
    from fd9_independent.native import finite_native_request, native_controls
    from fd9_independent.protocol import RawSpectrum

    # Reuse the synthetic square-mark image, not its legacy raw transcript.
    root = raw_fixture(s, root, selected, 0)
    rows = json.loads((root / "geometry.json").read_text(encoding="utf-8"))["rows"]
    frame = lambda side, p: struct.pack("<BBH", side, 0, len(p)) + p
    sent = frame(0, struct.pack("<I", 3))
    received = b""
    records = []
    for k, length in RECORD_SIZES.items():
        records.append(bytearray(length))
    for kinds in ((0,), (1, 2, 3, 4, 5, 6), (7,), (10,)):
        total = sum(sum(records[k]) for k in kinds)
        struct.pack_into(
            "<I", records[kinds[-1]], len(records[kinds[-1]]) - 4, (~total) & 0xFFFFFFFF
        )
    factory = FactoryCharacterization(
        tuple(SensorFactoryRecord(bytes(data), k) for k, data in enumerate(records))
    )
    for k, data in enumerate(records):
        sent += frame(0, struct.pack("<IBB", 0x206, 0, k))
        received += frame(1, struct.pack("<IIBBH", 0x206, 0, 0, k, 0) + data)
    raw, samples = [], []
    getters = (
        [(0, (0, 0, 0, 0))]
        + [(1, native_controls(m)) for m in ("M0", "M1", "M2")]
        + [(0, (0, 0, 0, 0)), (0, (1, 0, 0, 0))]
    )
    columns = len(s.layout["rows"][0])
    for i in range(n):
        r, c = divmod(i, columns)
        sent += frame(
            0, line_command([rows[selected[r]][c]], r % 6 == 0 and c == 0, False)
        )
        sent += frame(0, finite_native_request(2))
        received += frame(1, struct.pack("<II", 0x106, 0))
        payload = struct.pack("<I4H152f", 0x305, 4, 1, 0, 0, *([0.5] * 152))
        pose = RawSpectrum.decode(payload)
        raw.append(
            {"header": list(pose.header), "blocks": [list(b) for b in pose.blocks]}
        )
        received += frame(1, payload)
        received += frame(1, struct.pack("<9I", 0x300, 0, 0, 0, 0, 5, 1, 0, 0))
        received += frame(1, struct.pack("<IIBB", 0x203, 0, 0, 0))
        data = []
        for j, (selector, controls) in enumerate(getters):
            sent += frame(0, cached_data_request(selector, controls))
            vals = [0.5 + selected[r] * 0.01] * (152 if selector == 0 else 36)
            if selector:
                vals[0] += j * 0.01
            reply = struct.pack(
                "<II4BHHI", 0x205, 0, 0, 0, 0, 0, 2, 1, 0
            ) + struct.pack("<%df" % len(vals), *vals)
            received += frame(1, reply)
            data.append(CachedSensorData.from_reply(reply, selector, controls))
        m = NativeMeasurement(
            data[0],
            tuple(
                NativeSpectrum(NativeCondition(m), d.values, 2, 1, 0)
                for m, d in zip(("M0", "M1", "M2"), data[1:4])
            ),
            factory.verified_sections_sha256,
            "test-host",
            49152,
        )
        samples.append(m.to_dict())
    if complete:
        for command in (0x100, 0x101):
            sent += frame(0, struct.pack("<I", command))
            received += frame(1, struct.pack("<II", command, 0))
    for name, data in (("sent", sent), ("received", received)):
        (root / "wire" / (name + ".bin")).write_bytes(data)
    (root / "wire/manifest.json").write_text(
        json.dumps(
            {
                "host": "test-host",
                "port": 49152,
                "sent_sha256": hashlib.sha256(sent).hexdigest(),
                "received_sha256": hashlib.sha256(received).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    report = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    report.update(
        success=complete,
        phase="done" if complete else "failed",
        calibrated_reflectance=True,
        conversion_source="instrument_firmware",
        factory_sections_sha256=factory.verified_sections_sha256,
        native_samples=samples,
        raw_samples=raw,
        completed_native_rows=n // columns,
    )
    (root / "progress.json").write_text(json.dumps(report), encoding="utf-8")
    return root


def native_settings(s, **kwargs):
    return replace(
        s.settings,
        profile=None,
        illuminant=None,
        observer=None,
        conversion_source="instrument_firmware",
        **kwargs
    )


def action(s, count, complete=False):
    def run(source, layout, dest, host, **kwargs):
        assert kwargs["native_factory"] is True
        assert kwargs["expected_calibration_sha256"] is None
        root = fixture_native(s, dest, kwargs["row_indices"], count, complete)
        kwargs["on_readings"](count)
        if not complete:
            raise CaptureFailed(root, "synthetic stop")
        return root

    return run


def test_native_complete_without_external_files(setup):
    s = setup
    settings = native_settings(s, condition="M2")
    assert settings.validate() is None
    result = measure_chart(
        s.chart, settings, s.tmp / "native", capture=action(s, 36, True)
    )
    text, _, rows = first_table(result["staged"])
    assert len(rows) == 36
    assert 'CALIBRATED_REFLECTANCE "YES"' in text
    assert 'MEASUREMENT_CONDITION "M2"' in text
    assert "FD9_PROFILE_SHA256" not in text
    assert result["profile_sha256"] is None and not result["research_only"]
    assert not result["SDK_runtime_dependency"]
    assert len(result["factory_sections_sha256"]) == 64
    publish_measurement(result["staged"], result["destination"], s.chart)


def test_native_partial_resume_keeps_original_rows(setup):
    s = setup
    settings = native_settings(s)
    first = measure_chart(s.chart, settings, s.tmp / "first", capture=action(s, 17))
    assert first["patches"] == 12 and first["new_readings"] == 12
    old_rows = first_table(first["staged"])[2]
    publish_measurement(
        first["staged"], first["destination"], s.chart, allow_partial=True
    )
    resumed = replace(settings, resume=True)
    assert resume_plan(s.chart, resumed)[2] == [1, 2]
    last = measure_chart(s.chart, resumed, s.tmp / "last", capture=action(s, 24, True))
    assert last["complete"] and last["new_readings"] == 24
    assert first_table(last["staged"])[2][:12] == old_rows
    with pytest.raises(ValueError, match="same chart"):
        resume_plan(s.chart, replace(resumed, condition="M2"))


@pytest.mark.parametrize(
    "corrupt",
    [
        "spectrum",
        "source",
        "row_marker",
        "geometry",
        "hash",
        "selector",
        "advance",
        "factory",
    ],
)
def test_native_corruption_is_not_exported(setup, corrupt):
    s = setup
    root = fixture_native(s, s.tmp / "native", [0, 1, 2], 36, True)
    if corrupt in ("spectrum", "source", "row_marker"):
        path = root / "progress.json"
        j = json.loads(path.read_text(encoding="utf-8"))
        if corrupt == "spectrum":
            j["native_samples"][0]["spectra"]["M2"]["values"][0] += 0.01
        elif corrupt == "source":
            j["conversion_source"] = "local_profile"
        else:
            j["completed_native_rows"] -= 1
        path.write_text(json.dumps(j), encoding="utf-8")
    elif corrupt == "geometry":
        path = root / "geometry.json"
        j = json.loads(path.read_text(encoding="utf-8"))
        j["rows"][0][0][0] += 1
        path.write_text(json.dumps(j), encoding="utf-8")
    else:
        path = root / "wire/sent.bin"
        data = path.read_bytes()
        if corrupt == "selector":
            data = data.replace(
                struct.pack("<I5B", 0x205, 1, 0, 160, 0, 0),
                struct.pack("<I5B", 0x205, 1, 0, 14, 0, 0),
                1,
            )
        elif corrupt == "advance":
            data = data.replace(
                struct.pack("<I2B", 0x205, 0, 1), struct.pack("<I2B", 0x205, 0, 0), 1
            )
        elif corrupt == "factory":
            data = data.replace(
                struct.pack("<IBB", 0x206, 0, 0), struct.pack("<IBB", 0x206, 1, 0), 1
            )
        else:
            data += b"bad hash"
        path.write_bytes(data)
        if corrupt != "hash":
            manifest = root / "wire/manifest.json"
            j = json.loads(manifest.read_text(encoding="utf-8"))
            j["sent_sha256"] = hashlib.sha256(data).hexdigest()
            manifest.write_text(json.dumps(j), encoding="utf-8")
    with pytest.raises(ValueError):
        verified_native_rows(
            s.settings.driver_source, root, s.chart.with_suffix(".fd9.json")
        )


def test_native_reflectance_units_are_never_guessed():
    xyz, lab = native_colour([2.1] * 36)
    assert xyz[1] == pytest.approx(210)
    assert lab[0] > 100
    assert native_colour([1] * 36)[0][1] == pytest.approx(100)
    assert len(colour_data()[2]) == 64


def test_gui_only_offers_factory_settings(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from ui.fd9_measurement import FD9Setup, FD9MeasureMixin
    from types import SimpleNamespace

    store = QSettings(str(tmp_path / "fd9.ini"), QSettings.Format.IniFormat)
    store.setValue("host", "test-host")
    # Existing research paths must not influence the normal GUI anymore.
    store.setValue("profile", "missing.json")
    dialog = FD9Setup(store)
    assert set(dialog.inputs) == {"host"}
    owner = SimpleNamespace(
        _fd9_store=store,
        _fd9_condition=SimpleNamespace(currentText=lambda: "M1"),
    )
    settings = FD9MeasureMixin._fd9_settings(owner)
    assert settings.conversion_source == "instrument_firmware"
    assert (
        settings.profile is None
        and settings.illuminant is None
        and settings.observer is None
    )
    settings.validate()
    dialog.close()


def test_native_capture_checks_factory_before_insertion(setup, monkeypatch):
    from types import SimpleNamespace
    from workflow.fd9.independent import capture_layout
    import fd9_independent
    from fd9_independent.motion import Phase

    events = []

    class Instrument:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def close(self):
            events.append("close")

        def factory_characterization(self):
            events.append("factory")
            return SimpleNamespace(verified_sections_sha256="a" * 64)

        def save_transcript(self, *a):
            pass

    class Acquisition:
        def __init__(self, *a, **k):
            self.phase = Phase.NEW
            self.raw_samples = []
            self.native_samples = []
            self.completed_native_rows = 0
            self.calibration = b""

        def begin_loading(self):
            pytest.fail("Wrong factory must fail before loading")

    monkeypatch.setattr(fd9_independent, "Instrument", Instrument)
    monkeypatch.setattr("fd9_independent.native_motion.NativeAcquisition", Acquisition)
    with pytest.raises(CaptureFailed, match="factory characterization differs"):
        capture_layout(
            setup.settings.driver_source,
            setup.chart.with_suffix(".fd9.json"),
            setup.tmp / "mismatch",
            "test-host",
            allow_experimental=True,
            native_factory=True,
            factory_row_sequencing=False,
            expected_factory_sha256="b" * 64,
        )
    assert events == ["factory", "close"]


def test_native_resume_refuses_different_factory_even_with_valid_spectra(setup):
    s = setup
    settings = native_settings(s)
    first = measure_chart(s.chart, settings, s.tmp / "first", capture=action(s, 12))
    publish_measurement(
        first["staged"], first["destination"], s.chart, allow_partial=True
    )
    base = s.chart.with_suffix(".ti3")
    text = base.read_text(encoding="utf-8").replace(
        first["factory_sections_sha256"], "f" * 64
    )
    base.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="characterization changed"):
        measure_chart(
            s.chart,
            replace(settings, resume=True),
            s.tmp / "resumed",
            capture=action(s, 24, True),
        )
    assert base.read_text(encoding="utf-8") == text


def test_gui_factory_measurement_runs_real_export_and_filing(setup, qtbot, monkeypatch):
    from tests.test_fd9_partial import configure
    from ui.fd9_measurement import FD9Job
    from ui.tabs.tab_measure import TabMeasure
    from core.settings import AppSettings
    from core.argyll_runner import ArgyllRunner
    from core import instrument_lease
    from PyQt6.QtCore import QSettings

    s = setup
    app_settings = AppSettings()
    app_settings._qs = QSettings(str(s.tmp / "app.ini"), QSettings.Format.IniFormat)
    app_settings.set("custom_output_path", str(s.tmp / "out"))
    tab = TabMeasure(ArgyllRunner(app_settings), app_settings)
    qtbot.addWidget(tab)
    tab._fd9_store = QSettings(str(s.tmp / "gui.ini"), QSettings.Format.IniFormat)
    configure(tab, s)
    tab._fd9_condition.setCurrentText("M2")

    def work(*args, **kwargs):
        return measure_chart(*args, **kwargs, capture=action(s, 36, True))

    monkeypatch.setattr(
        "ui.fd9_measurement.FD9Job",
        lambda chart, settings, session, parent: FD9Job(
            chart, settings, session, parent, action=work
        ),
    )
    monkeypatch.setattr(
        tab._manager, "start", lambda *a, **k: pytest.fail("No external reader")
    )
    try:
        with qtbot.waitSignal(tab.measure_finished, timeout=10000) as saved:
            tab._on_start()
        qtbot.waitUntil(lambda: not tab._fd9_job.isRunning())
        assert saved.args[0] == s.chart.with_suffix(".ti3")
        text, _, rows = first_table(saved.args[0])
        assert len(rows) == 36 and 'MEASUREMENT_CONDITION "M2"' in text
        assert 'FD9_CONVERSION_SOURCE "INSTRUMENT_FIRMWARE"' in text
        assert not tab._fd9_live and instrument_lease.holder() is None
    finally:
        instrument_lease.release(tab)
        tab.close()
