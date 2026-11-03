"""Passive colour events, skewed paint, resume and the native-dialog printer."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json

import pytest
from PyQt6.QtCore import QPointF, QRect
from PyQt6.QtGui import QColor, QImage, QPainter, QPolygonF
from PyQt6.QtWidgets import QLabel

from tests.test_fd9_partial import setup, configure, capture
from tests.test_fd9_normal_measurement import tab, FD9Job
from tests.test_fd9_factory_workflow import native_settings
from tests.test_fd9_row_workflow import fixture_rows
from workflow.fd9.preview import build_scan_preview
from workflow.fd9.measurement import measure_chart, first_table, publish_measurement


def colours(s, path):
    from fd9_independent.instrument_model import InstrumentModel
    from fd9_independent.protocol import RawSpectrum

    root = Path(path)
    report = json.loads((root / "progress.json").read_text(encoding="utf-8"))
    model_path = root / "spectral-model"
    model = InstrumentModel(
        (model_path / "matrix.bin").read_bytes(),
        (model_path / "conditions.bin").read_bytes(),
        (model_path / "sensor-info.bin").read_bytes(),
        report["factory_sections_sha256"],
    )
    return [
        model.convert(
            RawSpectrum(tuple(r["header"]), tuple(tuple(b) for b in r["blocks"]))
        )
        for r in report["raw_samples"]
    ]


def acquisition(s, count=36):
    def run(source, layout, destination, host, **kwargs):
        root = fixture_rows(s, destination, kwargs["row_indices"], count, True)
        kwargs["on_scan"](root)
        for i, sample in enumerate(colours(s, root), 1):
            kwargs["on_readings"](i)
            if kwargs.get("on_sample"):
                kwargs["on_sample"](i, sample, root)
        return root

    return run


def test_worker_queues_selected_condition_colours_equal_to_export(tab, setup, qtbot):
    s = setup
    configure(tab, s)
    settings = replace(s.settings, condition="M2")
    events, threads = [], []
    from PyQt6.QtCore import QThread

    def work(*args, **kwargs):
        return measure_chart(*args, **kwargs, capture=acquisition(s))

    worker = FD9Job(s.chart, settings, s.tmp / "worker", action=work)
    worker.patch_ready.connect(
        lambda event: (events.append(event), threads.append(QThread.currentThread()))
    )
    with qtbot.waitSignal(worker.result, timeout=10000) as finished:
        worker.start()
    worker.wait(2000)
    assert len(events) == 36 and all(t is tab.thread() for t in threads)
    records = first_table(finished.args[0]["staged"])[2]
    for event, row in zip(events, records):
        assert event["condition"] == "M2" and event["session"] == str(
            worker.session.resolve()
        )
        patch = event["patches"][0]
        assert patch["loc"] == row["SAMPLE_LOC"]
        assert patch["xyz"] == pytest.approx(
            [float(row[k]) for k in ("XYZ_X", "XYZ_Y", "XYZ_Z")], abs=1e-8
        )


def test_live_colours_land_on_the_scan_and_reject_stale_events(tab, setup):
    s = setup
    configure(tab, s)
    root = capture(s, s.tmp / "scan", [0, 1, 2], 1)
    event = build_scan_preview(
        root, s.chart.with_suffix(".fd9.json"), s.settings.driver_source
    )
    tab._fd9_job = SimpleNamespace(session=root)
    tab._fd9_live = True
    tab._fd9_active_settings = s.settings
    tab._fd9_scan_ready(event)
    update = {
        "session": str(root.resolve()),
        "layout_sha256": event["layout_sha256"],
        "condition": "M1",
        "patches": [
            {"loc": "A1", "exyz": [30, 35, 40], "xyz": [20, 25, 30], "de": 1.0}
        ],
    }
    tab._fd9_patch_ready(update)
    items = tab._preview._patch_overlay[0]
    assert len(items) == 1 and items[0][0] == tab._patch_boxes[0]["A1"]
    assert items[0][2] != QColor("#56d6a5")
    update["patches"][0]["loc"] = "B1"
    for stale in [
        dict(update, session=str(s.tmp / "other")),
        dict(update, condition="M2"),
        dict(update, layout_sha256="bad"),
    ]:
        tab._fd9_patch_ready(stale)
        assert len(tab._preview._patch_overlay[0]) == 1
    tab._fd9_patch_ready(update)
    assert len(tab._preview._patch_overlay[0]) == 2
    tab._fd9_live = False


def test_skewed_scan_uses_normal_split_and_colour_modes_without_painting_gaps(tab):
    preview = tab._preview
    cell = [[10, 10], [80, 20], [75, 80], [15, 70]]
    box = QPolygonF([QPointF(x, y) for x, y in cell]).boundingRect().toAlignedRect()
    preview.set_scan_grid([[cell]], {0})
    preview.set_patch_overlay(
        0, [(box, QColor("red"), QColor("blue"), False)], replace_page=True
    )

    def paint(mode):
        preview.set_overlay_mode(mode)
        image = QImage(100, 100, QImage.Format.Format_RGB32)
        image.fill(QColor("gray"))
        painter = QPainter(image)
        preview._draw_scan_grid(painter, 1, 1, 0, 0)
        painter.end()
        return image

    both = paint("both")
    assert both.pixelColor(30, 30) == QColor("red")
    assert both.pixelColor(60, 60) == QColor("blue")
    assert both.pixelColor(12, 65) == QColor("gray")  # inside box, outside skewed cell
    assert paint("measured").pixelColor(30, 30) == QColor("blue")
    assert paint("expected").pixelColor(60, 60) == QColor("red")
    preview.set_show_only_measured(True)
    preview.clear_patch_overlay()
    assert paint("measured").pixelColor(30, 30) == QColor("white")


def test_saved_and_unsaved_resume_prefix_colours_are_restored_on_new_scan(tab, setup):
    from tests.test_fd9_row_workflow import action

    s = setup
    settings = native_settings(s)
    first = measure_chart(s.chart, settings, s.tmp / "first", capture=action(s, 12))
    configure(tab, s)
    root = capture(s, s.tmp / "rescan", [1, 2], 1)
    event = build_scan_preview(
        root, s.chart.with_suffix(".fd9.json"), s.settings.driver_source
    )
    tab._fd9_live = True
    tab._fd9_prior_count = 12
    tab._fd9_prior_measurement = Path(first["staged"])
    tab._fd9_show_scan(event, s.chart)
    assert len(tab._preview._patch_overlay[0]) == 12
    assert tab._preview._patch_info[0][0][1]["loc"] == "A1"
    publish_measurement(
        first["staged"], first["destination"], s.chart, allow_partial=True
    )
    tab._fd9_live = False
    tab._fd9_show_scan(event, s.chart)
    assert len(tab._preview._patch_overlay[0]) == 12
    tab._on_overlay_toggled(False)  # delayed legacy setting/prompt settlement
    assert len(tab._preview._patch_overlay[0]) == 12


def test_preview_callback_failure_never_changes_measurement(setup):
    s = setup
    messages = []

    def failed(_):
        raise ValueError("invented display error")

    result = measure_chart(
        s.chart,
        native_settings(s),
        s.tmp / "failure",
        capture=acquisition(s),
        on_patch=failed,
        progress=messages.append,
    )
    assert result["complete"] and result["patches"] == 36
    assert any("invented display error" in message for message in messages)


def test_native_dialog_never_warns_about_the_hidden_printer(qtbot):
    from ui.tabs.tab_print import TabPrint

    label = QLabel("Canon_IPF9400B stale warning")
    qtbot.addWidget(label)

    def wrong_queue():
        pytest.fail("The native-dialog printer cannot be read from the hidden combo")

    tab = SimpleNamespace(
        _edge_note_lbl=label,
        _settings={"use_native_print_dialog": True},
        _printer_combo=SimpleNamespace(currentData=wrong_queue),
    )
    TabPrint._update_edge_note(tab)
    assert not label.text() and label.isHidden()


def test_old_driver_checkbox_preference_cannot_disable_fd9(tab, setup):
    from workflow.measure_settings import apply, snapshot

    configure(tab, setup)
    assert "fd9_research" not in snapshot(tab)
    assert not hasattr(tab, "_fd9_research")
    assert "fd9_research" not in apply(
        tab, {"fd9_research": {"enabled": True, "value": False}}
    )
    assert tab._fd9_settings().allow_research is True
