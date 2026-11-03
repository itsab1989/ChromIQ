"""Scan projection, queued row updates and persisted/resumed preview ownership."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PyQt6.QtCore import QThread
from workflow.fd9.preview import build_scan_preview, saved_scan_preview
from workflow.fd9.measurement import measure_chart, publish_measurement, sha
from tests.test_fd9_partial import setup, capture, configure, action
from tests.test_fd9_normal_measurement import tab, FD9Job


def test_scan_is_flipped_once_and_grid_uses_skewed_measured_marks(setup):
    s = setup
    root = capture(s, s.tmp / "scan", [0, 1, 2], 1)
    from fd9_independent.geometry import grid_rows
    from workflow.fd9.independent import chart_grid

    path = root / "geometry.json"
    geometry = json.loads(path.read_text(encoding="utf-8"))
    geometry["marks"] = [[200, 100], [3400, 120], [210, 900], [3410, 920]]
    geometry["rows"] = grid_rows(geometry["marks"], **chart_grid(s.layout))
    path.write_text(json.dumps(geometry), encoding="utf-8")
    image = Image.open(root / "scan.pgm")
    image.putpixel((1000, 450), 177)
    image.save(root / "scan.pgm")
    digest = sha(root / "scan.pgm")
    event = build_scan_preview(
        root, s.chart.with_suffix(".fd9.json"), s.settings.driver_source
    )
    assert sha(root / "scan.pgm") == digest
    with Image.open(event["image"]) as view:
        assert view.getpixel((3637 - 1000, 450)) == 177
        assert view.size == (3638, 1000)
    for row, centres in zip(event["rows"], geometry["rows"]):
        for poly, (x, y) in zip(row, centres):
            assert sum(p[0] for p in poly) / 4 == pytest.approx(x - 1)
            assert sum(p[1] for p in poly) / 4 == pytest.approx(y)
            assert (
                poly[0][1] != poly[1][1]
            )  # preserve actual skew, not axis-aligned boxes


def test_live_progress_is_cumulative_on_resume_and_deduplicates_events(tab, setup):
    s = setup
    configure(tab, s)
    root = capture(s, s.tmp / "scan", [1, 2], 1)
    event = build_scan_preview(
        root, s.chart.with_suffix(".fd9.json"), s.settings.driver_source
    )
    tab._fd9_job = SimpleNamespace(session=root)
    tab._fd9_prior_count = 12
    tab._fd9_live = True
    tab._reset_progress(from_files=False)
    tab._progress_file_locs = set(tab._fd9_ordered_locations[:12])
    tab._progress_base = 12
    tab._fd9_scan_ready(event)
    assert tab._preview.measurement_progress() == pytest.approx(100 / 3)
    assert tab._preview._scan_grid[1] == {0}
    tab._fd9_count_changed(12)
    tab._fd9_count_changed(12)
    assert tab._preview.measurement_progress() == pytest.approx(200 / 3)
    assert tab._preview._scan_grid[1] == {0, 1}
    assert tab._preview._scan_grid[2] == 2
    tab._settings.set("measure_progress_bar", False)
    tab.refresh_progress_setting()
    assert tab._preview.measurement_progress() is None
    tab._fd9_count_changed(24)
    assert tab._preview._scan_grid[1] == {0, 1, 2}
    tab._settings.set("measure_progress_bar", True)
    tab.refresh_progress_setting()
    assert tab._preview.measurement_progress() == 100
    tab._fd9_live = False


def test_stale_session_scan_never_replaces_current_chart(tab, setup):
    s = setup
    configure(tab, s)
    root = capture(s, s.tmp / "scan", [0, 1, 2], 1)
    event = build_scan_preview(
        root, s.chart.with_suffix(".fd9.json"), s.settings.driver_source
    )
    tab._fd9_job = SimpleNamespace(session=s.tmp / "different-session")
    tab._fd9_scan_ready(event)
    assert tab._fd9_scan_preview is None
    assert tab._preview._scan_grid is None


def test_preview_reloads_with_canonical_partial_but_rejects_changed_measurement(
    tab, setup
):
    s = setup
    session = s.chart.parent / "fd9-sessions" / "partial"
    result = measure_chart(s.chart, s.settings, session, capture=action(s, 1))
    event = build_scan_preview(
        session, s.chart.with_suffix(".fd9.json"), s.settings.driver_source
    )
    target = publish_measurement(
        result["staged"], result["destination"], s.chart, allow_partial=True
    )
    assert saved_scan_preview(s.chart)["image"] == event["image"]
    configure(tab, s)
    tab._reset_progress()
    assert tab._fd9_scan_preview is not None and tab._preview._scan_grid[1] == {0}
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert saved_scan_preview(s.chart) is None
    tab._preview.clear()
    assert tab._preview._scan_grid is None


def test_scan_event_is_queued_from_worker_and_preview_failure_does_not_drop_readings(
    tab, setup, qtbot, monkeypatch
):
    s = setup
    configure(tab, s)
    events = []

    def acquisition(source, layout, destination, host, **kwargs):
        from tests.test_fd9_factory_workflow import fixture_native

        root = fixture_native(s, destination, [0, 1, 2], 36, complete=True)
        kwargs["on_scan"](root)
        kwargs["on_readings"](36)
        return root

    def work(*args, **kwargs):
        return measure_chart(*args, **kwargs, capture=acquisition)

    worker = FD9Job(s.chart, s.settings, s.tmp / "worker", action=work)

    def received(event):
        events.append((event, QThread.currentThread()))

    worker.scan_ready.connect(received)
    with qtbot.waitSignal(worker.result, timeout=10000):
        worker.start()
    worker.wait(2000)
    assert len(events) == 1 and events[0][1] is tab.thread()
    monkeypatch.setattr(
        "workflow.fd9.preview.build_scan_preview",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("display-only failure")),
    )
    result = measure_chart(
        s.chart,
        s.settings,
        s.tmp / "no-preview",
        capture=acquisition,
        progress=lambda _: None,
    )
    assert result["complete"] and result["patches"] == 36


def test_fresh_read_resets_old_progress_and_discard_restores_it(
    tab, setup, qtbot, monkeypatch
):
    import threading

    s = setup
    old = measure_chart(
        s.chart, s.settings, s.tmp / "old", capture=action(s, 3, complete=True)
    )
    target = publish_measurement(old["staged"], old["destination"], s.chart)
    configure(tab, s)
    tab._reset_progress()
    assert tab._preview.measurement_progress() == 100
    unblock = threading.Event()

    def acquisition(source, layout, destination, host, **kwargs):
        root = capture(s, destination, [0, 1, 2], 1)
        kwargs["on_scan"](root)
        kwargs["on_readings"](12)
        assert unblock.wait(10)
        from workflow.fd9.independent import CaptureFailed

        raise CaptureFailed(root, "Supervised test stop")

    def work(*args, **kwargs):
        return measure_chart(*args, **kwargs, capture=acquisition)

    monkeypatch.setattr(
        "ui.fd9_measurement.FD9Job",
        lambda chart, settings, session, parent: FD9Job(
            chart, settings, session, parent, action=work
        ),
    )
    monkeypatch.setattr(tab, "_confirm_end_of_session", lambda how: "discard")
    try:
        tab._on_start()
        qtbot.waitUntil(
            lambda: tab._fd9_readings == 12 and tab._fd9_scan_preview is not None,
            timeout=10000,
        )
        assert tab._preview.measurement_progress() == pytest.approx(100 / 3)
        assert tab._preview._scan_grid[1] == {0}
    finally:
        unblock.set()
    qtbot.waitUntil(lambda: not tab._fd9_live, timeout=10000)
    qtbot.waitUntil(lambda: not tab._fd9_job.isRunning())
    assert tab._preview.measurement_progress() == 100
    assert tab._preview._scan_grid[1] == {0, 1, 2}
    assert sha(target) == old["staged_sha256"]


@pytest.mark.parametrize(
    "rep,tokens", [("RGB", ("R", "G", "B")), ("W", ("W",)), ("K", ("K",))]
)
def test_generated_additive_and_gray_preview_matches_print_pixels(
    tab, tmp_path, rep, tokens
):
    from tests.test_fd9_chart_creation import ti1
    from workflow.fd9.chart import build_chart
    from workflow.fd9.measurement import checked_chart

    source, _ = ti1(tmp_path, rep, tokens, count=24)
    if rep in ("W", "K"):
        source.write_text(
            source.read_text(encoding="utf-8").replace(rep + "_" + rep, "GRAY_" + rep),
            encoding="utf-8",
        )
    result = build_chart(
        source, tmp_path / "generated", dpi=100, randomize=True, seed=42
    )
    tab.set_ti1_path(source)
    assert tab._fd9_load_preview(result.ti2_path)
    _, layout, _ = checked_chart(result.ti2_path)
    with Image.open(result.tiff_paths[0]) as printed, Image.open(
        tab._tiff_pages[0]
    ) as preview:
        for row in layout["rows"]:
            for p in row:
                x, y = p["centre_mm"]
                actual = preview.getpixel((round(x * 4), round(y * 4)))
                expected = printed.getpixel(
                    (round(x * 100 / 25.4), round(y * 100 / 25.4))
                )
                assert max(abs(a - b) for a, b in zip(actual, expected)) <= 1
