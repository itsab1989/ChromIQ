"""Tests for the single-patch (spot) read tool.

Covers the spotread line parser, the argument builder, the Lab(D50)→sRGB swatch
helper, and the CSV/.ti3 writers. The dialog gets a light offscreen smoke test
(a simulated reading must add a table row with a swatch — no real instrument).

Fixture lines mirror ArgyllCMS 3.5.0 spotread.c / instappsup.c output.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from workflow.spot_read_io import (
    SpotReading,
    average_readings,
    lab_d50_to_srgb,
    write_csv,
    write_ti3,
)
from workflow.spot_read_manager import SpotReadManager, SpotReadParams


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _StubRunner:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.run_args: list | None = None

    def write_stdin(self, text: str) -> None:
        self.writes.append(text)

    def run(self, tool, args, cwd, **kw) -> None:
        self.run_args = [tool, args, cwd]

    def abort(self) -> None:
        pass

    @property
    def is_running(self) -> bool:
        return False


def _make_manager():
    runner = _StubRunner()
    mgr = SpotReadManager(runner)
    sigs: dict = {}

    def _collect(name: str):
        sigs.setdefault(name, [])
        return lambda *args: sigs[name].append(args)

    for name in (
        "reading_ready", "ready_to_read", "calibration_prompt", "misread",
        "sensor_wrong_position", "no_instrument", "device_busy",
        "instrument_disconnected", "coms_init_failed", "inst_init_failed",
    ):
        getattr(mgr, name).connect(_collect(name))
    return mgr, runner, sigs


def _feed(mgr, line: str) -> None:
    mgr._handle_line(line, lambda _l: None)


# --- argument building ------------------------------------------------------

def _args(**kw) -> list[str]:
    mgr, _r, _s = _make_manager()
    return mgr._build_args(SpotReadParams(**kw))


def test_reflective_has_no_mode_flag():
    a = _args(mode="reflective")
    assert "-e" not in a and "-a" not in a
    # By position originally; -v now precedes it (#130, 2026-07-31 — spotread
    # only names the connected instrument when asked to be verbose). What this
    # test is really about is that the port is passed and reflective adds no
    # mode flag, neither of which depends on where -c sits.
    assert a[a.index("-c") + 1] == "1"


def test_the_instrument_is_asked_for():
    """-v is what makes spotread print "Instrument Type: …", which is the only
    way ChromIQ can tell a ColorMunki from an i1Pro (Knut, #130)."""
    assert "-v" in _args()


def test_emissive_flag():
    assert "-e" in _args(mode="emissive")


def test_ambient_flag():
    assert "-a" in _args(mode="ambient")


def test_skip_initial_cal_and_highres():
    a = _args(disable_initial_cal=True, high_res=True)
    assert "-N" in a and "-H" in a


# --- line parsing -----------------------------------------------------------

def test_result_line_parses_xyz_and_lab():
    mgr, _r, sigs = _make_manager()
    _feed(mgr, " Result is XYZ: 12.345 45.678 7.890, D50 Lab: 73.21 -1.50 3.40")
    assert sigs["reading_ready"]
    xyz, lab = sigs["reading_ready"][0]
    assert xyz == pytest.approx((12.345, 45.678, 7.890))
    assert lab == pytest.approx((73.21, -1.50, 3.40))


def test_ready_prompt_detected():
    mgr, _r, sigs = _make_manager()
    _feed(mgr, "Hit ESC or Q to exit, any other key to take a reading: ")
    assert sigs["ready_to_read"]


def test_calibration_prompt_fires_on_continue_line():
    mgr, _r, sigs = _make_manager()
    _feed(mgr, "Place the instrument on its reflective white reference S/N 12345,")
    _feed(mgr, " and then hit any key to continue,")
    assert len(sigs["calibration_prompt"]) == 1


def test_calibration_prompt_fires_once_per_step():
    mgr, _r, sigs = _make_manager()
    _feed(mgr, "Set instrument sensor to calibration position,")
    _feed(mgr, " and then hit any key to continue,")
    _feed(mgr, " and then hit any key to continue,")  # repeated flush — no re-fire
    assert len(sigs["calibration_prompt"]) == 1
    # A later reading prompt re-arms it for the next calibration.
    _feed(mgr, "Hit ESC or Q to exit, any other key to take a reading: ")
    _feed(mgr, " and then hit any key to continue,")
    assert len(sigs["calibration_prompt"]) == 2


def test_misread_and_no_instrument():
    mgr, _r, sigs = _make_manager()
    _feed(mgr, "Spot read failed due to misread (Sample read failed)")
    _feed(mgr, "No instruments connected")
    assert sigs["misread"] and sigs["no_instrument"]


# --- Lab → sRGB -------------------------------------------------------------

def test_lab_white_is_near_white():
    r, g, b = lab_d50_to_srgb(100.0, 0.0, 0.0)
    assert r > 250 and g > 250 and b > 250


def test_lab_black_is_black():
    assert lab_d50_to_srgb(0.0, 0.0, 0.0) == (0, 0, 0)


def test_lab_mid_grey_is_balanced_grey():
    r, g, b = lab_d50_to_srgb(53.39, 0.0, 0.0)  # ~sRGB 0.5 grey
    assert 110 < r < 140 and abs(r - g) <= 3 and abs(g - b) <= 4


def test_lab_red_is_reddish():
    r, g, b = lab_d50_to_srgb(54.0, 80.0, 70.0)
    assert r > g and r > b


# --- file writers -----------------------------------------------------------

def _sample_readings() -> list[SpotReading]:
    return [
        SpotReading("White", (96.4, 100.0, 82.5), (100.0, 0.0, 0.0)),
        SpotReading("Grey",  (20.5, 21.6, 17.8),  (53.4, 0.1, -0.2)),
    ]


def test_write_csv_round_trips(tmp_path: Path):
    out = write_csv(tmp_path / "r.csv", _sample_readings())
    rows = out.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "name,L,a,b,X,Y,Z,sRGB_hex"
    assert rows[1].startswith("White,100.0000,0.0000,0.0000,")
    assert rows[1].endswith("#ffffff")
    assert len(rows) == 3


def test_average_readings_means_xyz_and_lab():
    r1 = SpotReading("A", xyz=(30.0, 32.0, 74.0), lab=(60.0, -8.0, -30.0))
    r2 = SpotReading("B", xyz=(32.0, 34.0, 76.0), lab=(62.0, -6.0, -28.0))
    avg = average_readings([r1, r2], "Average")
    assert avg.name == "Average"
    assert avg.xyz == pytest.approx((31.0, 33.0, 75.0))
    assert avg.lab == pytest.approx((61.0, -7.0, -29.0))
    # swatch hex is derived, so an averaged entry shows a colour like any reading
    assert avg.hex.startswith("#") and len(avg.hex) == 7


def test_average_readings_empty_raises():
    with pytest.raises(ValueError):
        average_readings([], "Average")


def test_write_ti3_is_valid_cgats(tmp_path: Path):
    out = write_ti3(tmp_path / "r.ti3", _sample_readings())
    text = out.read_text(encoding="utf-8")
    assert "CTI3" in text
    assert "XYZ_X" in text and "XYZ_Y" in text and "XYZ_Z" in text
    assert "BEGIN_DATA" in text and "END_DATA" in text


# --- dialog smoke -----------------------------------------------------------

def test_dialog_appends_row_on_reading():
    class _Settings:
        def get(self, *a):
            return "dark"

    from ui.dialogs.spot_read_dialog import SpotReadDialog
    dlg = SpotReadDialog(_StubRunner(), _Settings())
    dlg._on_reading((20.0, 21.0, 18.0), (53.0, 1.0, -2.0))
    assert dlg._table.rowCount() == 1
    assert dlg._table.item(0, 0).text() == "Patch 1"
    assert dlg._save_btn.isEnabled()
    dlg.deleteLater()
