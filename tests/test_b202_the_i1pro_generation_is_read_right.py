"""#202 (Knut, 2026-10-01): an i1Pro 2 was timed against the first-generation
i1Pro limit, "at least 240 ms" per patch (24 readings at 100 Hz) where the
i1Pro 2 wants 120 ms (24 at 200 Hz).

ArgyllCMS 3.5.0 prints "X-Rite i1 Pro 2" (spectro/insttypes.c:240-246), with a
space before the digit; `model_key` looked for "i1 pro2". The i1Pro 3 and 3 Plus
fell through the same way. The 3 Plus is "X-Rite i1 Pro 3" plus " Plus" only in
the verbose header (spectro/i1pro3_imp.c:927), which the engine never read; and
re-reading the chart put its own "GretagMacbeth i1 Pro" back over what the
instrument had reported. These tests use only the strings Argyll really prints.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.measure_pace import model_key, refines  # noqa: E402

#: Every reflective strip/spot spectrometer name Argyll 3.5.0 can print for
#: the instruments ChromIQ measures with, and the row it must land on.
ARGYLL_NAMES = [
    ("GretagMacbeth i1 Pro", "i1pro"),
    ("X-Rite i1 Pro 2", "i1pro2"),
    ("X-Rite i1 Pro 3", "i1pro3"),
    ("X-Rite i1 Pro 3 Plus", "i1pro3plus"),       # the verbose header's form
    ("X-Rite ColorMunki", "colormunki"),
    ("GretagMacbeth SpectroScan", "spectroscan"),
    ("GretagMacbeth SpectroScanT", "spectroscan"),
]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("name,key", ARGYLL_NAMES)
def test_every_name_argyll_prints_lands_on_its_own_row(name, key):
    assert model_key(name) == key


@pytest.mark.parametrize("name,key", [
    ("Xrite i1 Pro 2", "i1pro2"),             # spelled without the hyphen
    ("x-rite I1 PRO 3 PLUS", "i1pro3plus"),   # any case
    ("i1 Pro3+", "i1pro3plus"),               # the short forms people write
    ("i1Pro2", "i1pro2"),
    ("X-Rite i1Studio", "colormunki"),
    ("ChnSpec CR30", "cr30"),
])
def test_other_spellings_still_resolve(name, key):
    assert model_key(name) == key


@pytest.mark.parametrize("name", ["", None, "Datacolor Spyder5",
                                  "X-Rite i1 DisplayPro"])
def test_what_is_not_a_strip_spectrometer_is_not_guessed(name):
    """`i1 DisplayPro` must not read as an i1Pro: "displaypro" has no "i1pro"."""
    assert model_key(name) is None


def test_a_later_report_never_loses_the_plus():
    assert refines("i1pro3plus", "i1pro3")
    assert refines("i1pro3", None)
    assert not refines("i1pro3", "i1pro3plus")
    assert refines("i1pro2", "i1pro")


# ---- the measure tab ------------------------------------------------------

def _chart(stem: Path, instrument: str) -> Path:
    """A .ti1 with its .ti2 beside it, TARGET_INSTRUMENT only in the .ti2."""
    stem.parent.mkdir(parents=True, exist_ok=True)
    ti1 = stem.with_suffix(".ti1")
    ti1.write_text(
        "CTI1\n\nDESCRIPTOR \"chart\"\nCOLOR_REP \"RGB\"\n\n"
        "NUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
        "END_DATA_FORMAT\n\nNUMBER_OF_SETS 1\nBEGIN_DATA\n1 100 100 100\n"
        "END_DATA\n", encoding="utf-8")
    stem.with_suffix(".ti2").write_text(
        "CTI2\n\nDESCRIPTOR \"chart\"\nCOLOR_REP \"RGB\"\n"
        f"TARGET_INSTRUMENT \"{instrument}\"\n\n"
        "NUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 A1 100 100 100\nEND_DATA\n",
        encoding="utf-8")
    return ti1


def _tab(tmp_path: Path, chart_instrument="GretagMacbeth i1 Pro"):
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_ti1_path(_chart(tmp_path / "chart" / "c", chart_instrument))
    return tab


def _min_ms(cfg) -> float:
    return 1000.0 * cfg.min_samples / cfg.sample_hz


def test_knuts_case_an_i1pro_chart_read_with_an_i1pro2(qapp, tmp_path):
    """His chart was laid out for an i1Pro; the device was an i1Pro 2. His
    Preferences (from his log): 24 readings per patch on both rows."""
    tab = _tab(tmp_path)
    tab._settings.set("pace_min_samples_i1pro", 24)
    tab._settings.set("pace_min_samples_i1pro2", 24)
    tab._on_instrument_detected("X-Rite i1 Pro 2")
    cfg = tab._pace_config()
    assert cfg.sample_hz == 200.0
    assert _min_ms(cfg) == pytest.approx(120.0)
    assert 163 > _min_ms(cfg), "his 163 ms per patch is a good speed"


def test_reading_the_chart_again_does_not_undo_the_report(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._on_instrument_detected("X-Rite i1 Pro 2")
    tab._refresh_bidir_autodetect()          # re-reads TARGET_INSTRUMENT
    assert tab._pace_config().sample_hz == 200.0


def test_with_no_report_the_chart_and_then_the_slowest_row_decide(qapp, tmp_path):
    tab = _tab(tmp_path)
    assert tab._pace_config().sample_hz == 100.0     # the chart says i1 Pro


def test_a_3_plus_stays_a_3_plus_and_warns_once(qapp, tmp_path, monkeypatch):
    """Engine mode reports the device twice: the verbose header (with Plus),
    then the JSON event (without). The second must neither downgrade the row
    nor raise the mismatch window again."""
    tab = _tab(tmp_path, "X-Rite i1 Pro 3 Plus")
    warned = []
    monkeypatch.setattr(tab, "_warn_if_instrument_does_not_match_chart",
                        lambda m: warned.append(m))
    tab._on_instrument_detected("X-Rite i1 Pro 3 Plus")
    tab._on_instrument_detected("X-Rite i1 Pro 3")
    assert model_key(tab._reported_instrument) == "i1pro3plus"
    assert tab._pace_config().min_samples == 66
    assert warned == ["X-Rite i1 Pro 3 Plus"]


def test_the_same_report_twice_warns_once(qapp, tmp_path, monkeypatch):
    tab = _tab(tmp_path)
    warned = []
    monkeypatch.setattr(tab, "_warn_if_instrument_does_not_match_chart",
                        lambda m: warned.append(m))
    tab._on_instrument_detected("X-Rite i1 Pro 2")
    tab._on_instrument_detected("X-Rite i1 Pro 2")
    assert warned == ["X-Rite i1 Pro 2"]


def test_a_new_session_forgets_the_last_device():
    """A different instrument may be plugged in for the next measurement."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure)
    reset = src.index("self._saw_instrument = False")
    assert "self._reported_instrument = None" in src[reset:reset + 200]


def test_the_engine_reads_argylls_verbose_header(qapp):
    """The helper prints "Instrument Type:" as prose; it is the only line
    that says Plus."""
    from core.argyll_runner import ArgyllRunner
    from core.settings import AppSettings
    from workflow.measure_manager import MeasureManager
    mgr = MeasureManager(ArgyllRunner(AppSettings()))
    got = []
    mgr.instrument_detected.connect(got.append)
    mgr._handle_engine_line("Instrument Type:   X-Rite i1 Pro 3 Plus", lambda _l: None)
    assert got == ["X-Rite i1 Pro 3 Plus"]
