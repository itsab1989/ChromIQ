"""Create Chart tab auto-tags a well-mixed fixed-order chart as randomised.

The TI2 layout editor already upgrades CHART_ID → RANDOM_START on save when the
layout passes the randomisation gate. This pins the matching behaviour on the
main Create Chart tab's generate path (_maybe_autotag_randomised), so a
pre-shuffled "Preserve Patch Order" (-r) chart isn't left fixed-order and can be
measured bidirectionally — the situation that produced the pharmacist's
mistagged charts.
"""
import tempfile
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return s


@pytest.fixture()
def tab(qapp, settings):
    return TabChart(ArgyllRunner(settings), FileManager(settings), settings)


_HEAD = ('CTI2\n\nKEYWORD "SAMPLE_LOC"\n{kw} "426"\nNUMBER_OF_FIELDS 5\n'
         'BEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\n'
         'END_DATA_FORMAT\n')


def _label(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _make_ti2(vals, steps, kw):
    rows, sid = [], 0
    for k in range(0, len(vals), steps):
        letter = _label(k // steps)
        for j, (r, g, b) in enumerate(vals[k:k + steps], 1):
            sid += 1
            rows.append(f'{sid} "{letter}{j}" {r} {g} {b}')
    text = (_HEAD.format(kw=kw) + f"NUMBER_OF_SETS {sid}\nBEGIN_DATA\n"
            + "\n".join(rows) + "\nEND_DATA\n")
    p = Path(tempfile.mkstemp(suffix=".ti2")[1])
    p.write_text(text, encoding="utf-8")
    return p


def _tag(p: Path) -> str:
    t = p.read_text(encoding="utf-8")
    return "RANDOM_START" if "RANDOM_START" in t else (
        "CHART_ID" if "CHART_ID" in t else "?")


@pytest.fixture()
def shuffled():
    rng = np.random.default_rng(0)
    return [tuple(rng.uniform(0, 100, 3)) for _ in range(200)]


@pytest.fixture()
def ramp():
    return [(100 * i / 199,) * 3 for i in range(200)]


def test_wellmixed_chart_id_is_upgraded(tab, shuffled):
    p = _make_ti2(shuffled, 20, "CHART_ID")
    tab._maybe_autotag_randomised(p)
    assert _tag(p) == "RANDOM_START"


def test_structured_chart_id_is_left_fixed(tab, ramp):
    p = _make_ti2(ramp, 20, "CHART_ID")
    tab._maybe_autotag_randomised(p)
    assert _tag(p) == "CHART_ID"


def test_already_randomised_is_untouched(tab, shuffled):
    p = _make_ti2(shuffled, 20, "RANDOM_START")
    before = p.read_text(encoding="utf-8")
    tab._maybe_autotag_randomised(p)
    assert p.read_text(encoding="utf-8") == before          # byte-for-byte no-op


def test_missing_file_is_noop(tab):
    tab._maybe_autotag_randomised(Path("/tmp/chromiq_no_such_file.ti2"))  # no raise
