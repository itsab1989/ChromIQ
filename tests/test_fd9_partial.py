"""Portable synthetic wire: partial-row recovery, provenance and resumed rows."""

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
import hashlib
import json
import shutil
import struct
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from workflow.fd9.independent import CaptureFailed, driver, export_saved, chart_grid
from workflow.fd9.measurement import (
    FD9Settings,
    prepare_chart,
    measure_chart,
    first_table,
    publish_measurement,
    resume_plan,
    sha,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def setup(tmp_path):
    source = Path(__file__).resolve().parents[1] / "vendor/fd9-independent"
    driver(source)
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
    chart = prepare_chart(p, tmp_path / "chart")
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "schema": 1,
                "calibrated": False,
                "host": "test-host",
                "calibration_sha256": hashlib.sha256(b"synthetic-cal").hexdigest(),
                "conditions": {
                    m: {
                        "high_source_weights": [0.2] * 22,
                        "reference_source": "invented test data",
                    }
                    for m in ("M1", "M2")
                },
            }
        ),
        encoding="utf-8",
    )
    ill = tmp_path / "ill.csv"
    ill.write_text("380,1\n730,1\n", encoding="utf-8")
    obs = tmp_path / "obs.csv"
    obs.write_text("380,.8,1,.7\n730,.8,1,.7\n", encoding="utf-8")
    settings = FD9Settings(source, profile, ill, obs, "test-host", "M1", True)
    return SimpleNamespace(chart=chart, settings=settings, layout=layout, tmp=tmp_path)


def capture(setup, output, selected, count, *, complete=False, tail=0, bad_ack=False):
    """Invented frames and square fiducials, not a captured device fixture."""
    from fd9_independent.geometry import find_marks, grid_rows
    from fd9_independent.motion import line_command
    from fd9_independent.protocol import RawSpectrum

    root = Path(output)
    (root / "wire").mkdir(parents=True)
    width, height = 3638, 1000
    pixels = bytearray(b"\xff" * (width * height))
    for x, y in ((200, 100), (3400, 100), (200, 900), (3400, 900)):
        for yy in range(y - 20, y + 20):
            pixels[yy * width + x - 20 : yy * width + x + 20] = b"\0" * 40
    grid = chart_grid(setup.layout)
    marks = find_marks(pixels, width, height)
    rows = grid_rows(marks, **grid)
    (root / "scan.pgm").write_bytes(f"P5\n{width} {height}\n255\n".encode() + pixels)
    (root / "geometry.json").write_text(
        json.dumps({"grid": grid, "marks": marks, "rows": rows}), encoding="utf-8"
    )
    (root / "chart-definition.json").write_text(
        json.dumps(setup.layout), encoding="utf-8"
    )
    frame = lambda side, p: struct.pack("<BBH", side, 0, len(p)) + p
    sent = frame(0, struct.pack("<I", 3))
    received = b""
    samples = []
    for i, index in enumerate(selected[: count + bool(tail)]):
        sent += frame(0, line_command(rows[index], i % 6 == 0, i < len(selected) - 1))
        received += frame(1, struct.pack("<II", 0x106, int(bad_ack)))
        n = len(setup.layout["rows"][0]) if i < count else tail
        for j in range(n):
            # Different rows yield different readings to catch incorrect merges.
            values = [0.2 + index * 0.01] * 38 + [0.6 + index * 0.01] * 38 + [1.0] * 76
            payload = struct.pack("<I4H152f", 0x305, 4, j + 1, 0, 0, *values)
            received += frame(1, payload)
            raw = RawSpectrum.decode(payload)
            samples.append(
                {"header": list(raw.header), "blocks": [list(b) for b in raw.blocks]}
            )
    if complete:
        sent += frame(0, struct.pack("<I", 0x100)) + frame(
            0, struct.pack("<II", 0x101, 1)
        )
    else:
        received += b"\x01\x00\x0c"  # stopped inside a trailing frame header
    for side, data in [("sent", sent), ("received", received)]:
        (root / "wire" / f"{side}.bin").write_bytes(data)
    (root / "wire/manifest.json").write_text(
        json.dumps(
            {
                "host": "test-host",
                "sent_sha256": hashlib.sha256(sent).hexdigest(),
                "received_sha256": hashlib.sha256(received).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    (root / "instrument-calibration.bin").write_bytes(b"synthetic-cal")
    (root / "progress.json").write_text(
        json.dumps(
            {
                "success": complete,
                "phase": "done" if complete else "failed",
                "calibrated_reflectance": False,
                "image_height": height,
                "measurement_row_indices": selected,
                "raw_samples": samples,
            }
        ),
        encoding="utf-8",
    )
    return root


def action(setup, count, *, complete=False, tail=0):
    def run(source, layout, dest, host, **kwargs):
        selected = kwargs["row_indices"]
        capture(setup, dest, selected, count, complete=complete, tail=tail)
        kwargs["on_readings"](count * len(setup.layout["rows"][0]))
        if not complete:
            raise CaptureFailed(dest, "synthetic disconnect")
        return dest

    return run


def test_partial_only_keeps_complete_verified_rows(setup):
    s = setup
    result = measure_chart(
        s.chart, s.settings, s.tmp / "first", capture=action(s, 1, tail=5)
    )
    assert (
        result["patches"] == 12
        and not result["complete"]
        and result["acquisition_error"]
    )
    assert not s.chart.with_suffix(".ti3").exists()
    assert [int(r["SAMPLE_ID"]) for r in first_table(result["staged"])[2]] == list(
        range(1, 13)
    )
    target = publish_measurement(
        result["staged"],
        result["destination"],
        s.chart,
        allow_partial=True,
        expected_base_sha256=None,
    )
    assert resume_plan(s.chart, replace(s.settings, resume=True))[2] == [1, 2]
    old_rows = first_table(target)[2]
    result2 = measure_chart(
        s.chart,
        replace(s.settings, resume=True),
        s.tmp / "second",
        capture=action(s, 2, complete=True),
    )
    merged = first_table(result2["staged"])[2]
    assert result2["complete"] and merged[:12] == old_rows and len(merged) == 36
    assert result2["new_readings"] == 24
    publish_measurement(
        result2["staged"], target, s.chart, expected_base_sha256=result2["base_sha256"]
    )
    assert (
        first_table(target)[2] == merged
        and len(list((target.parent / "old").rglob("*.ti3"))) == 1
    )


@pytest.mark.parametrize(
    "change",
    ["condition", "profile", "observer", "layout", "nan", "missing_row", "wrong_count"],
)
def test_resume_rejects_incompatible_or_damaged_base_before_capture(setup, change):
    s = setup
    result = measure_chart(s.chart, s.settings, s.tmp / "first", capture=action(s, 1))
    target = publish_measurement(
        result["staged"], result["destination"], s.chart, allow_partial=True
    )
    settings = replace(s.settings, resume=True)
    if change == "condition":
        settings = replace(settings, condition="M2")
    elif change == "profile":
        s.settings.profile.write_text(
            s.settings.profile.read_text(encoding="utf-8") + " ", encoding="utf-8"
        )
    elif change == "observer":
        s.settings.observer.write_text("380,.7,1,.7\n730,.7,1,.7\n", encoding="utf-8")
    elif change == "layout":
        s.chart.with_suffix(".fd9.json").write_text(
            s.chart.with_suffix(".fd9.json").read_text(encoding="utf-8") + " ",
            encoding="utf-8",
        )
    elif change == "nan":
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "1 A1 0.0000000000", "1 A1 nan", 1
            ),
            encoding="utf-8",
        )
    elif change == "missing_row":
        target.write_text(
            target.read_text(encoding="utf-8").replace("1 A1 ", "13 A1 ", 1),
            encoding="utf-8",
        )
    else:
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "NUMBER_OF_SETS 12", "NUMBER_OF_SETS 36"
            ),
            encoding="utf-8",
        )
    with patch(
        "workflow.fd9.measurement.capture_layout",
        side_effect=AssertionError("No device access"),
    ):
        with pytest.raises(ValueError):
            resume_plan(s.chart, settings)


def test_tampered_wire_and_unsuccessful_ack_cannot_be_saved(setup):
    s = setup
    root = capture(s, s.tmp / "evidence", [0, 1, 2], 1, bad_ack=True)
    from workflow.fd9.evidence import verified_rows

    with pytest.raises(ValueError, match="acknowledgement"):
        verified_rows(
            s.settings.driver_source,
            root,
            s.chart.with_suffix(".fd9.json"),
            allow_partial=True,
        )
    (root / "wire/received.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        verified_rows(
            s.settings.driver_source,
            root,
            s.chart.with_suffix(".fd9.json"),
            allow_partial=True,
        )


def test_concurrent_change_is_never_replaced(setup):
    s = setup
    result = measure_chart(s.chart, s.settings, s.tmp / "first", capture=action(s, 1))
    target = s.chart.with_suffix(".ti3")
    target.write_text("external change", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        publish_measurement(
            result["staged"],
            target,
            s.chart,
            allow_partial=True,
            expected_base_sha256=None,
        )
    assert target.read_text(encoding="utf-8") == "external change"


def test_repeated_partial_resume_uses_only_the_remaining_suffix(setup):
    s = setup
    first = measure_chart(s.chart, s.settings, s.tmp / "one", capture=action(s, 1))
    dest = publish_measurement(
        first["staged"], first["destination"], s.chart, allow_partial=True
    )
    second = measure_chart(
        s.chart,
        replace(s.settings, resume=True),
        s.tmp / "two",
        capture=action(s, 1, tail=3),
    )
    assert second["patches"] == 24 and not second["complete"]
    publish_measurement(
        second["staged"],
        dest,
        s.chart,
        allow_partial=True,
        expected_base_sha256=second["base_sha256"],
    )
    third = measure_chart(
        s.chart,
        replace(s.settings, resume=True),
        s.tmp / "three",
        capture=action(s, 1, complete=True),
    )
    assert third["patches"] == 36 and third["new_readings"] == 12
    assert [int(r["SAMPLE_ID"]) for r in first_table(third["staged"])[2]] == list(
        range(1, 37)
    )
    assert "one,two,three" in Path(third["staged"]).read_text(encoding="utf-8")


from tests.test_fd9_normal_measurement import (
    tab,
    FD9Job,
)  # shared fixture and original worker class


def configure(tab, s):
    # GUI coverage exercises the shipped factory path. Legacy profile export
    # remains covered independently by the backend tests above.
    s.settings = replace(
        s.settings,
        profile=None,
        illuminant=None,
        observer=None,
        conversion_source="instrument_firmware",
    )
    tab._settings.set("fd9_host", "test-host")
    tab.set_ti1_path(s.chart.with_suffix(".ti1"))


def install_worker(monkeypatch, s, count, complete=False):
    from tests.test_fd9_factory_workflow import action as factory_action

    def work(*args, **kwargs):
        columns = len(s.layout["rows"][0])
        return measure_chart(
            *args,
            **kwargs,
            capture=factory_action(
                s, count * columns + (0 if complete else 5), complete
            ),
        )

    monkeypatch.setattr(
        "ui.fd9_measurement.FD9Job",
        lambda chart, settings, session, parent: FD9Job(
            chart, settings, session, parent, action=work
        ),
    )


def test_native_save_partial_then_resume_files_every_patch(
    tab, setup, qtbot, monkeypatch
):
    s = setup
    configure(tab, s)
    install_worker(monkeypatch, s, 1)
    monkeypatch.setattr(tab, "_confirm_end_of_session", lambda how: "save")
    target = s.chart.with_suffix(".ti3")
    tab._on_start()
    qtbot.waitUntil(
        lambda: target.exists() and not tab._fd9_live and tab._fd9_pending is None,
        timeout=10000,
    )
    qtbot.waitUntil(lambda: not tab._fd9_job.isRunning())
    before = first_table(target)[2]
    assert len(before) == 12 and tab._fd9_resume.isChecked()
    assert tab._start_btn.text() == "Continue Measurement"
    install_worker(monkeypatch, s, 2, complete=True)
    with qtbot.waitSignal(tab.measure_finished, timeout=10000):
        tab._on_start()
    qtbot.waitUntil(lambda: not tab._fd9_job.isRunning())
    assert first_table(target)[2][:12] == before and len(first_table(target)[2]) == 36
    assert not tab._fd9_resume.isChecked() and not tab.a_measurement_is_running()
    assert len(list((target.parent / "old").rglob("*.ti3"))) == 1


def test_native_discard_partial_retains_old_complete_measurement(
    tab, setup, qtbot, monkeypatch
):
    s = setup
    old = measure_chart(
        s.chart, s.settings, s.tmp / "old", capture=action(s, 3, complete=True)
    )
    target = publish_measurement(old["staged"], old["destination"], s.chart)
    before = target.read_bytes()
    configure(tab, s)
    install_worker(monkeypatch, s, 1)
    seen = []

    def discard(how):
        seen.append(tab._fd9_readings)
        return "discard"

    monkeypatch.setattr(tab, "_confirm_end_of_session", discard)
    # §5 (review H4): replacing a complete measurement is asked first.
    asked = []
    monkeypatch.setattr(tab, "_confirm_replacing_measurement",
                        lambda: asked.append(True) or True)
    tab._on_start()
    assert asked == [True]
    qtbot.waitUntil(
        lambda: not tab._fd9_live and tab._fd9_pending is None, timeout=10000
    )
    qtbot.waitUntil(lambda: not tab._fd9_job.isRunning())
    assert seen == [12] and target.read_bytes() == before


def test_native_keep_after_connection_failure_preserves_pending_then_quit_saves(
    tab, setup, qtbot, monkeypatch
):
    s = setup
    configure(tab, s)
    install_worker(monkeypatch, s, 1)
    monkeypatch.setattr(tab, "_confirm_end_of_session", lambda how: None)
    tab._on_start()
    qtbot.waitUntil(
        lambda: tab._fd9_pending is not None and not tab._fd9_live, timeout=10000
    )
    qtbot.waitUntil(lambda: not tab._fd9_job.isRunning())
    assert tab.a_measurement_is_running() and not s.chart.with_suffix(".ti3").exists()
    monkeypatch.setattr(tab, "_confirm_end_of_session", lambda how: "save")
    assert tab.confirm_quit_during_measurement()
    assert len(first_table(s.chart.with_suffix(".ti3"))[2]) == 12


def test_external_write_during_atomic_commit_is_preserved(setup, monkeypatch):
    s = setup
    result = measure_chart(s.chart, s.settings, s.tmp / "first", capture=action(s, 1))
    target = s.chart.with_suffix(".ti3")
    target.write_text("old", encoding="utf-8")
    before = sha(target)
    import os

    real = os.fsync

    def external(fd):
        real(fd)
        target.write_text("new external write", encoding="utf-8")

    monkeypatch.setattr(os, "fsync", external)
    with pytest.raises(ValueError, match="before commit"):
        publish_measurement(
            result["staged"],
            target,
            s.chart,
            allow_partial=True,
            expected_base_sha256=before,
        )
    assert target.read_text(encoding="utf-8") == "new external write"


def test_negative_row_suffix_is_rejected_before_indexing_geometry(setup):
    from workflow.fd9.evidence import verified_rows

    s = setup
    output = capture(s, s.tmp / "bad-suffix", [0, 1, 2], 1)
    p = output / "progress.json"
    report = json.loads(p.read_text(encoding="utf-8"))
    report["measurement_row_indices"] = [-1, 0, 1, 2]
    p.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="remaining-row suffix"):
        verified_rows(
            s.settings.driver_source,
            output,
            s.chart.with_suffix(".fd9.json"),
            allow_partial=True,
        )
