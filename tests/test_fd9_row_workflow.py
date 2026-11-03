"""Invented device model and row wire, with no captured numerical fixtures."""

import hashlib
import json
import struct
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_fd9_partial import setup, capture as raw_fixture
from tests.test_fd9_factory_workflow import native_settings
from workflow.fd9.independent import CaptureFailed
from workflow.fd9.measurement import (
    measure_chart,
    first_table,
    publish_measurement,
    resume_plan,
)
from workflow.fd9.factory_evidence import verified_factory_rows
from workflow.fd9.native_export import export_native


def fixture_rows(
    s,
    root,
    selected,
    count,
    complete=False,
    *,
    dropped_conversion=0,
    changed_model=False
):
    from fd9_independent.factory import (
        RECORD_SIZES,
        SensorFactoryRecord,
        FactoryCharacterization,
    )
    from fd9_independent.instrument_model import InstrumentModel, model_data_request
    from fd9_independent.protocol import RawSpectrum

    columns = len(s.layout["rows"][0])
    root = raw_fixture(
        s, root, selected, count // columns, complete=complete, tail=count % columns
    )
    records = [bytearray(length) for length in RECORD_SIZES.values()]
    for kinds in ((0,), (1, 2, 3, 4, 5, 6), (7,), (10,)):
        struct.pack_into(
            "<I",
            records[kinds[-1]],
            len(records[kinds[-1]]) - 4,
            (~sum(sum(records[k]) for k in kinds)) & 0xFFFFFFFF,
        )
    factory = FactoryCharacterization(
        tuple(SensorFactoryRecord(bytes(data), k) for k, data in enumerate(records))
    )
    matrix = struct.pack(">400f", *([0.002 if changed_model else 0.001] * 400))
    conditions = b"".join(
        struct.pack(">I97f", kind, *([1.0] * 97)) for kind in [0, 2, 160] + [23] * 24
    )
    info = struct.pack("<II", 0x216, 0) + bytes((1, 0, 0, 2)) + bytes(36)
    model = InstrumentModel(matrix, conditions, info, factory.verified_sections_sha256)
    model.save(root / "spectral-model")
    frame = lambda side, p: struct.pack("<BBH", side, 0, len(p)) + p
    sent = frame(0, struct.pack("<I", 0x216))
    received = frame(1, info)
    spans = [
        (0x0C02E520, (0x0C034C28).to_bytes(4, "big")),
        (0x0C04C378, (27).to_bytes(4, "big")),
        (0x0C02D4F8, matrix),
        (0x0C034C28, conditions[:8000]),
        (0x0C036B68, conditions[8000:]),
    ]
    for address, data in spans:
        sent += frame(0, model_data_request(address, len(data)))
        received += frame(
            1, struct.pack("<IIBBHI", 0x20E, 0, 0, 0, len(data), address) + data
        )
    for k, data in enumerate(records):
        sent += frame(0, struct.pack("<IBB", 0x206, 0, k))
        received += frame(1, struct.pack("<IIBBH", 0x206, 0, 0, k, 0) + data)
    # Keep the original single registration, then add pre-loading reads before
    # the raw fixture's one command per row. No cached getters or finite starts.
    old_sent = (root / "wire/sent.bin").read_bytes()
    (root / "wire/sent.bin").write_bytes(old_sent[:8] + sent + old_sent[8:])
    (root / "wire/received.bin").write_bytes(
        received + (root / "wire/received.bin").read_bytes()
    )
    manifest = json.loads((root / "wire/manifest.json").read_text(encoding="utf-8"))
    for side in ("sent", "received"):
        manifest[side + "_sha256"] = hashlib.sha256(
            (root / "wire" / (side + ".bin")).read_bytes()
        ).hexdigest()
    (root / "wire/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    report = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    samples = [
        model.convert(
            RawSpectrum(tuple(r["header"]), tuple(tuple(b) for b in r["blocks"]))
        ).to_dict()
        for r in report["raw_samples"]
    ]
    if dropped_conversion:
        samples = samples[:-dropped_conversion]
    report.update(
        calibrated_reflectance=True,
        conversion_source="instrument_model",
        factory_sections_sha256=model.factory_sections_sha256,
        model_sha256=model.model_sha256,
        native_samples=samples,
        completed_native_rows=len(samples) // columns,
    )
    (root / "progress.json").write_text(json.dumps(report), encoding="utf-8")
    return root


def action(s, count, complete=False, **fixture_options):
    def run(source, layout, dest, host, **kwargs):
        assert kwargs["native_factory"] is True
        assert kwargs.get("factory_row_sequencing", True) is True
        root = fixture_rows(
            s, dest, kwargs["row_indices"], count, complete, **fixture_options
        )
        kwargs["on_readings"](count)
        if not complete:
            raise CaptureFailed(root, "synthetic row stop")
        return root

    return run


def test_all_conditions_export_from_same_raw_rows_without_profiles(setup):
    s = setup
    result = measure_chart(
        s.chart, native_settings(s), s.tmp / "rows", capture=action(s, 36, True)
    )
    text, _, rows = first_table(result["staged"])
    assert len(rows) == 36 and result["complete"]
    assert result["conversion_source"] == "instrument_model" and result["model_sha256"]
    assert 'FD9_CONVERSION_SOURCE "INSTRUMENT_MODEL"' in text
    assert 'CALIBRATED_REFLECTANCE "YES"' in text and "FD9_PROFILE_SHA256" not in text
    for mode in ("M0", "M1", "M2"):
        out = s.tmp / (mode + ".ti3")
        export_native(
            s.settings.driver_source,
            result["session"],
            s.chart.with_suffix(".fd9.json"),
            out,
            mode,
        )
        assert len(first_table(out)[2]) == 36


def test_row_stop_resume_preserves_original_prefix_and_model_binding(setup):
    s = setup
    settings = native_settings(s)
    first = measure_chart(s.chart, settings, s.tmp / "first", capture=action(s, 17))
    assert first["patches"] == 12
    prefix = first_table(first["staged"])[2]
    publish_measurement(
        first["staged"], first["destination"], s.chart, allow_partial=True
    )
    resumed = replace(settings, resume=True)
    assert resume_plan(s.chart, resumed)[2] == [1, 2]

    def checked_capture(*args, **kwargs):
        assert kwargs["expected_model_sha256"] == first["model_sha256"]
        return action(s, 24, True)(*args, **kwargs)

    last = measure_chart(s.chart, resumed, s.tmp / "last", capture=checked_capture)
    assert last["complete"] and last["new_readings"] == 24
    assert first_table(last["staged"])[2][:12] == prefix
    with pytest.raises(ValueError, match="spectral model changed"):
        measure_chart(
            s.chart,
            resumed,
            s.tmp / "wrong-model",
            capture=action(s, 24, True, changed_model=True),
        )


def test_partial_conversion_only_recovers_fully_converted_rows(setup):
    s = setup
    first = measure_chart(
        s.chart,
        native_settings(s),
        s.tmp / "partial",
        capture=action(s, 24, dropped_conversion=1),
    )
    assert first["patches"] == 12


@pytest.mark.parametrize(
    "corruption",
    [
        "values",
        "row_count",
        "model_file",
        "model_digest",
        "write_flag",
        "version",
        "extra_exposure",
    ],
)
def test_rejects_changed_wire_model_or_results(setup, corruption):
    s = setup
    root = fixture_rows(s, s.tmp / corruption, [0, 1, 2], 36, True)
    report = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    if corruption == "values":
        report["native_samples"][0]["spectra"]["M1"]["values"][5] += 0.01
    elif corruption == "row_count":
        report["completed_native_rows"] = 2
    elif corruption == "model_digest":
        report["model_sha256"] = "0" * 64
    elif corruption == "model_file":
        (root / "spectral-model/matrix.bin").write_bytes(bytes(1600))
    else:
        wire = bytearray((root / "wire/sent.bin").read_bytes())
        if corruption == "write_flag":
            start = wire.index(struct.pack("<I", 0x20E))
            wire[start + 4] = 1
        elif corruption == "version":
            wire = bytearray((root / "wire/received.bin").read_bytes())
            wire[12] = 9
            (root / "wire/received.bin").write_bytes(wire)
        else:
            payload = struct.pack("<IBBHI", 0x203, 4, 0, 2, 0)
            wire.extend(struct.pack("<BBH", 0, 0, len(payload)) + payload)
        if corruption != "version":
            (root / "wire/sent.bin").write_bytes(wire)
        manifest = json.loads((root / "wire/manifest.json").read_text(encoding="utf-8"))
        for side in ("sent", "received"):
            manifest[side + "_sha256"] = hashlib.sha256(
                (root / "wire" / (side + ".bin")).read_bytes()
            ).hexdigest()
        (root / "wire/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "progress.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises((ValueError, RuntimeError)):
        verified_factory_rows(
            s.settings.driver_source, root, s.chart.with_suffix(".fd9.json")
        )


@pytest.mark.parametrize("columns,row_count", [(20, 23), (33, 65)])
def test_variable_grid_uses_one_row_command_and_exports_every_patch(
    setup, columns, row_count
):
    from workflow.fd9.measurement import prepare_chart

    s = setup
    s.layout["fiducials_mm"] = [
        [9.5, 32.5],
        [327.5, 32.5],
        [9.5, 650.5],
        [327.5, 650.5],
    ]
    s.layout["rows"] = [
        [
            {
                "id": r * columns + c + 1,
                "centre_mm": [19 + 9 * c, 42 + 9 * r],
                "device_values": [r, c, 0, 0],
            }
            for c in range(columns)
        ]
        for r in range(row_count)
    ]
    path = s.tmp / "variable.json"
    path.write_text(json.dumps(s.layout), encoding="utf-8")
    s.chart = prepare_chart(path, s.tmp / "variable")
    result = measure_chart(
        s.chart,
        native_settings(s),
        s.tmp / "large",
        capture=action(s, columns * row_count, True),
    )
    assert result["patches"] == columns * row_count and result["complete"]
    sent = (Path(result["session"]) / "wire/sent.bin").read_bytes()
    ids, offset = [], 0
    while offset < len(sent):
        size = struct.unpack_from("<H", sent, offset + 2)[0]
        ids.append(struct.unpack_from("<I", sent, offset + 4)[0])
        offset += size + 4
    assert ids.count(0x106) == row_count
    assert 0x203 not in ids and 0x205 not in ids


def test_gui_files_row_conversion_without_profile_access(setup, qtbot, monkeypatch):
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
        text, _, rows = first_table(saved.args[0])
        assert len(rows) == 36 and 'FD9_CONVERSION_SOURCE "INSTRUMENT_MODEL"' in text
        assert not tab._fd9_live and instrument_lease.holder() is None
    finally:
        instrument_lease.release(tab)
        tab.close()


@pytest.mark.parametrize("mismatch", [None, "model", "factory"])
def test_capture_defaults_to_rows_and_checks_model_before_loading(
    setup, monkeypatch, mismatch
):
    from types import SimpleNamespace
    import fd9_independent
    from fd9_independent.motion import Phase
    from workflow.fd9.independent import capture_layout

    s = setup
    template = raw_fixture(s, s.tmp / "template", [0, 1, 2], 0)
    scan = (template / "scan.pgm").read_bytes().split(b"\n255\n", 1)[1]
    events = []

    class Instrument:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def close(self):
            events.append("close")

        def save_transcript(self, path):
            pass

    class Acquisition:
        def __init__(self, *args, **kwargs):
            self.phase = Phase.NEW
            self.raw_samples, self.native_samples = [], []
            self.completed_native_rows = 0
            self.calibration = b""
            self.image = dict.fromkeys(range(1000))

        def prepare_model(self):
            events.append("model")
            return SimpleNamespace(
                save=lambda path: None,
                model_sha256="a" * 64,
                factory_sections_sha256="b" * 64,
            )

        def begin_loading(self):
            events.append("loading")

        def wait_ready(self, seconds):
            events.append("ready")

        def prescan(self):
            return scan

        def measure_rows(self, rows, on_point):
            events.append("rows")
            assert len(rows) == 3 and all(len(row) == 12 for row in rows)
            self.phase = Phase.DONE

    monkeypatch.setattr(fd9_independent, "Instrument", Instrument)
    monkeypatch.setattr(
        "fd9_independent.factory_motion.FactoryRowAcquisition", Acquisition
    )
    options = (
        {"expected_model_sha256": "c" * 64}
        if mismatch == "model"
        else {"expected_factory_sha256": "c" * 64} if mismatch == "factory" else {}
    )

    def run():
        return capture_layout(
            s.settings.driver_source,
            s.chart.with_suffix(".fd9.json"),
            s.tmp / "capture",
            "test-host",
            native_factory=True,
            allow_experimental=True,
            **options
        )

    if mismatch:
        with pytest.raises(CaptureFailed, match="differs"):
            run()
        assert events == ["model", "close"]
    else:
        run()
        assert events == ["model", "loading", "ready", "rows", "close"]
