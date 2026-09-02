"""Simulated reading of SpectroScan **hexagonal** patch charts (Knut).

Hexagonal charts can't be turned into a CHT (a .cht has no way to describe a
hexagon), so they are measured by the SpectroScan itself in XY mode — one pass
per column. Knut asked for a simulation of reading them, to shake out column
selection / navigation issues that only appear on the hex/XY path.

These tests build a real SpectroScan hexagonal chart with the ChromIQ layout
engine, then drive the REAL chromiq-chartread binary over it through the replay
instrument (only the USB edge is scripted) — exactly like test_chartread_engine
does for i1Pro strip charts, but over hexagonal SpectroScan chart *geometry*.

Scope note: the replay instrument presents as an i1Pro strip reader
(chromiq_replay.c), so this exercises column enumeration, column selection
(goto) and per-patch reading over a hex chart's layout — the parts Knut flagged
("selection of columns"). It does not fake the SpectroScan's XY-table hardware,
so the written .ti3 carries the replay instrument's own TARGET_INSTRUMENT, not
the SpectroScan. Faking instSpectroScan for a true XY-navigation simulation is a
further step.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from replay_tools import HELPER, ReplaySession, write_replay_script  # noqa: E402

ARGYLL = Path("/Applications/Argyll/bin")

pytestmark = pytest.mark.skipif(
    not HELPER.exists(), reason="chromiq-chartread helper not built")


def _make_hex_chart(tmp: Path, name: str = "hexchart") -> Path:
    """targen a small RGB patch set, then lay it out as a SpectroScan
    *hexagonal* chart with the engine. Returns the base path.

    SS + hexagons must use ``patch_first`` — ``area_first`` collapses the
    hexagons into full-width bands (the SS-hex ``area_first`` bug). Fixed order
    (``randomize=False``) keeps the replay script deterministic.
    """
    import shutil
    targen = shutil.which("targen") or str(ARGYLL / "targen")
    if not Path(targen).exists():
        pytest.skip("Argyll targen not available")
    tmp.mkdir(parents=True, exist_ok=True)
    base = tmp / name
    # -f90 lays out as two *uniform* 45-patch columns on A4; a ragged final
    # column (e.g. -f60 → 45+15) can't be replayed by the uniform-length replay
    # instrument, which would misread the short column (a harness limit, not an
    # engine bug — see chromiq_replay.c cq_read_strip).
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", "-f90", str(base)],
                   check=True, capture_output=True, cwd=tmp)
    from workflow.layout_engine.chart import build_chart
    build_chart(base.with_suffix(".ti1"), base, instrument="SS", paper="A4",
                hflag=True, layout_mode="patch_first", randomize=False)
    # The real app writes a channels.json recipe sidecar next to the chart;
    # hex_support.chart_is_hexagonal reads it. Write the minimal form so the
    # chart is positively identifiable as a SpectroScan hexagonal chart.
    import json
    base.with_suffix(".channels.json").write_text(
        json.dumps({"layout": {"recipe": {"instrument": "SS", "hflag": True}}}), encoding="utf-8")
    return base


@pytest.fixture()
def hex_chart(tmp_path: Path) -> tuple[Path, Path]:
    base = _make_hex_chart(tmp_path)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.2)
    return base, replay


def _read_all_and_finish(s: ReplaySession, n_cols: int) -> None:
    for _ in range(n_cols):
        idx = s.event_index()
        s.send(cmd="swipe")
        s.wait_event("strip_read", after=idx)
        s.wait_event("saved", after=idx)
    s.send(cmd="done")
    s.wait_event("done", timeout=6)


def test_hex_chart_is_actually_hexagonal(hex_chart):
    """Guard the fixture: the chart we built must really be a SS-hex chart
    (else the rest of the file would silently test a rectangular layout)."""
    base, _ = hex_chart
    from workflow.hex_support import chart_is_hexagonal
    assert chart_is_hexagonal(base.with_suffix(".ti2"))


def test_hex_full_xy_session_reads_every_column(hex_chart):
    base, replay = hex_chart
    s = ReplaySession(base, replay)
    ev = s.wait_event("session_start")
    cols = [x["strip"] for x in ev["strips"]]
    assert cols == sorted(cols) and len(cols) >= 2   # one pass per column
    assert ev["randomised"] is False
    s.wait_event("strip_ready")
    _read_all_and_finish(s, len(cols))
    assert s.finish() == 0
    ti3 = base.with_suffix(".ti3")
    assert ti3.exists()
    text = ti3.read_text(encoding="utf-8")
    assert text.startswith("CTI3")
    # Every hex patch across both columns is booked (2 × 45).
    assert "NUMBER_OF_SETS 90" in text
    assert text.count('"A') + text.count('"B') >= 90


def test_hex_column_read_carries_ordered_per_patch_de(hex_chart):
    base, replay = hex_chart
    s = ReplaySession(base, replay)
    s.wait_event("strip_ready")
    s.send(cmd="swipe")
    ev = s.wait_event("strip_read")
    patches = ev["patches"]
    assert len(patches) >= 40
    # Hex patches come back in column order (A1, A2, … — no stagger scramble).
    col = ev["strip"]
    nums = [int(p["loc"][len(col):]) for p in patches]
    assert nums == sorted(nums), "hex column patches must stay in slot order"
    for p in patches:
        assert set(p) >= {"id", "loc", "xyz", "exyz", "de"}
        assert p["de"] < 5.0                          # replay noise is tiny
    assert ev["verifiable"] is True


def test_hex_goto_selects_a_named_column(hex_chart):
    """Column selection on the hex/XY path: jumping to a column by name must
    land on it and let it be read (Knut's 'selection of columns')."""
    base, replay = hex_chart
    s = ReplaySession(base, replay)
    ev = s.wait_event("session_start")
    target = [x["strip"] for x in ev["strips"]][-1]   # last column
    s.wait_event("strip_ready")
    idx = s.event_index()
    s.send(cmd="goto", strip=target)
    ready = s.wait_event("strip_ready", after=idx)
    assert ready["strip"] == target
    s.send(cmd="swipe")
    assert s.wait_event("strip_read", after=idx)["strip"] == target
