"""#130 (Knut, 2026-07-30): "Unrecognised chart target instrument 'i1Pro'".

*"chartread: Error - Unrecognised chart target instrument 'i1Pro' … Normally, it
is allowed to measure anyway, but here I am cut off abruptly without any warning
or message, beside the log info that is a bit hidden."* — and *"If I try to
measure I always get this error."*

Two faults, and the first one is mine:

1. ``scripts/make_load_test_data.py`` — a fixture generator I gave him — wrote
   ``TARGET_INSTRUMENT "i1Pro"``. That is a ChromIQ-internal instrument key, not
   an ArgyllCMS name. chartread matches that keyword by exact string and refuses
   the whole run when it does not know the value, so every chart the script made
   was unmeasurable. His own files confirm it: four of them carry the bad name.
   The same lesson as the demo projects — test data must produce what the real
   pipeline produces, and the name now comes from ``KNOWN_INSTRUMENTS`` so the
   two cannot drift apart.

2. ChromIQ let the measurement start anyway and then ended the session with
   nothing on screen but a raw tool error in the log. A run that cannot possibly
   succeed must not begin, and the reason has to be said where the user is
   looking.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox     # noqa: E402

from core.settings import AppSettings                     # noqa: E402
from ui.ti2_loader import KNOWN_INSTRUMENTS               # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _ti2(path, instrument: str) -> None:
    path.write_text(
        "CTI2\n\n"
        'DESCRIPTOR "chart"\n'
        'COLOR_REP "RGB"\n'
        f'TARGET_INSTRUMENT "{instrument}"\n\n'
        "NUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        "NUMBER_OF_SETS 1\nBEGIN_DATA\n1 A1 100 100 100\nEND_DATA\n",
        encoding="utf-8")


def _tab(tmp_path):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return TabMeasure(ArgyllRunner(s), s), s


# ---- 1. the fixture generator ---------------------------------------------
def test_the_load_test_generator_writes_a_name_argyll_knows():
    src = (os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
           + "/scripts/make_load_test_data.py")
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    assert 'TARGET_INSTRUMENT "i1Pro"' not in text, \
        "the generator is writing a ChromIQ key as an ArgyllCMS name again"
    assert "KNOWN_INSTRUMENTS" in text, \
        "the name must come from the one list, not be spelled out again"


def test_the_generator_actually_produces_a_measurable_chart(tmp_path):
    """Not just the source — the file it writes."""
    import importlib.util
    import sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    spec = importlib.util.spec_from_file_location(
        "make_load_test_data", root + "/scripts/make_load_test_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    ti2 = tmp_path / "c.ti2"
    mod.write_ti2(ti2, [(100.0, 100.0, 100.0), (0.0, 0.0, 0.0)])
    from ui.ti2_loader import read_target_instrument
    assert read_target_instrument(ti2) in KNOWN_INSTRUMENTS

    ti3 = tmp_path / "c.ti3"
    mod.write_ti3(ti3, [(100.0, 100.0, 100.0)])
    assert read_target_instrument(ti3) in KNOWN_INSTRUMENTS


# ---- 2. the app refuses to start a run that cannot succeed ----------------
def test_a_good_chart_is_not_blocked(qapp, tmp_path):
    tab, _s = _tab(tmp_path)
    ti2 = tmp_path / "good.ti2"
    _ti2(ti2, next(n for n in KNOWN_INSTRUMENTS if "i1 Pro" in n))
    tab._ti1_path = ti2
    assert tab._blocked_by_unusable_target_instrument() is False


def test_a_chart_with_no_instrument_at_all_is_not_blocked(qapp, tmp_path):
    """Absent is fine — ArgyllCMS then uses its own default. Refusing here would
    block charts that have always worked."""
    tab, _s = _tab(tmp_path)
    ti2 = tmp_path / "bare.ti2"
    ti2.write_text("CTI2\n\nNUMBER_OF_SETS 1\n", encoding="utf-8")
    tab._ti1_path = ti2
    assert tab._blocked_by_unusable_target_instrument() is False


def test_an_unusable_name_stops_the_run_and_says_why(qapp, tmp_path, monkeypatch):
    tab, _s = _tab(tmp_path)
    ti2 = tmp_path / "bad.ti2"
    _ti2(ti2, "i1Pro")
    tab._ti1_path = ti2

    shown = {}

    def _exec(self):
        shown["text"] = self.text()
        for b in self.buttons():
            if "Cancel" in b.text():
                shown["btn"] = b
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: shown.get("btn"))

    assert tab._blocked_by_unusable_target_instrument() is True
    assert "i1Pro" in shown["text"], "the window must quote what it found"
    # Checked in the BODY, not the title: macOS message boxes have no title bar,
    # so Qt reports an empty windowTitle there and the user never sees it. Any
    # information that matters has to be in the text.
    assert "ArgyllCMS" in shown["text"]
    # …and the log says it too, because that is where he was looking.
    assert "i1Pro" in tab._log.toPlainText()


def test_choosing_to_correct_it_makes_the_chart_measurable(qapp, tmp_path,
                                                           monkeypatch):
    from ui.ti2_loader import read_target_instrument
    tab, _s = _tab(tmp_path)
    ti2 = tmp_path / "bad.ti2"
    _ti2(ti2, "i1Pro")
    ti2.with_suffix(".ti3").write_text(
        'CTI3\nTARGET_INSTRUMENT "i1Pro"\n', encoding="utf-8")
    tab._ti1_path = ti2

    picked = {}

    def _exec(self):
        for b in self.buttons():
            if "Correct" in b.text():
                picked["btn"] = b
        return 0

    monkeypatch.setattr(QMessageBox, "exec", _exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self: picked.get("btn"))

    assert tab._blocked_by_unusable_target_instrument() is False
    assert read_target_instrument(ti2) in KNOWN_INSTRUMENTS
    # the measurement beside it is corrected too, so the pair stays consistent
    assert read_target_instrument(ti2.with_suffix(".ti3")) in KNOWN_INSTRUMENTS


@pytest.mark.parametrize("found,expect", [
    ("i1Pro", "i1 Pro"), ("i1", "i1 Pro"), ("p3", "i1 Pro"),
    ("i1Pro3", "i1 Pro"), ("ColorMunki", "ColorMunki"),
    ("i1Studio", "ColorMunki"), ("SpectroScan", "SpectroScan"),
])
def test_each_family_maps_to_the_argyll_name(qapp, tmp_path, found, expect):
    from ui.ti2_loader import read_target_instrument
    tab, _s = _tab(tmp_path)
    ti2 = tmp_path / f"{found}.ti2"
    _ti2(ti2, found)
    assert tab._repair_target_instrument(ti2, found) is True
    assert expect in read_target_instrument(ti2)


def test_a_name_that_says_nothing_is_not_guessed_at(qapp, tmp_path, monkeypatch):
    """Guessing which device a chart was laid out for would be worse than saying
    we cannot tell — the strips would be the wrong size for the instrument."""
    from ui.ti2_loader import read_target_instrument
    tab, _s = _tab(tmp_path)
    ti2 = tmp_path / "odd.ti2"
    _ti2(ti2, "Some Other Spectro 9000")
    warned = {}
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a, **k: warned.setdefault("said", a[2]))

    assert tab._repair_target_instrument(ti2, "Some Other Spectro 9000") is False
    assert read_target_instrument(ti2) == "Some Other Spectro 9000", \
        "an unrecognisable name must be left exactly as it was"
    assert "cannot tell" in warned["said"] or "guessing" in warned["said"]


def test_the_check_runs_before_anything_is_armed():
    """A run that cannot succeed must not start — not arm the sounds, not clear
    the pace panel, not touch the measurement."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    guard = src.index("_blocked_by_unusable_target_instrument")
    for later in ("_sound.arm(", "_clear_pace_readout()"):
        assert guard < src.index(later), f"{later} runs before the check"


# ---- the Inspect Measurement browse dialog (Knut, 08:32:12Z) --------------
def test_inspect_measurement_starts_in_the_configured_chromiq_folder(tmp_path):
    """*"The Inspect Measurement tool: when opening the file dialog to browse for
    ti3 file it does not start in the default ChromIQ folder."*

    Both browse handlers hard-coded ~/ChromIQ and ignored Preferences → Paths.
    Every other place in the app already consults the setting first; these two
    were the only ones that did not.
    """
    from ui.dialogs.ti3_info_dialog import _chromiq_root
    custom = tmp_path / "MyColourWork"
    custom.mkdir()
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(custom))
    assert _chromiq_root(s) == custom


def test_it_falls_back_to_the_default_folder_then_to_home(tmp_path):
    import pathlib
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", "")
    root = _root = __import__("ui.dialogs.ti3_info_dialog",
                             fromlist=["_chromiq_root"])._chromiq_root(s)
    home_default = pathlib.Path.home() / "ChromIQ"
    assert root in (home_default, pathlib.Path.home())

    # A configured folder that has since been removed must not be offered.
    s.set("custom_output_path", str(tmp_path / "gone"))
    assert _root is not None
    assert __import__("ui.dialogs.ti3_info_dialog",
                      fromlist=["_chromiq_root"])._chromiq_root(s) == pathlib.Path.home()


def test_no_browse_handler_hard_codes_the_folder_any_more():
    """The bounded check that found this: every other site in the app already
    reads the setting first, so a hard-coded home path is the smell."""
    import pathlib
    src = pathlib.Path("ui/dialogs/ti3_info_dialog.py").read_text(encoding="utf-8")
    body = src[src.index("def _on_browse"):]
    assert 'Path.home() / "ChromIQ"' not in body, \
        "a browse handler is ignoring Preferences → Paths again"
