"""#202 round 2 (Knut, 5943245399): "Make sure that all instruments in the
'Instrument' selection, except SpectroScan and CR30, are associated with the
correct Per instrument minimum reading speed calculation in Preferences -->
Measurement. SpectroScan and CR30 do not perform strip readings, and the input
fields for SpectroScan and CR30 in Preferences --> Measurement should be
locked/disabled (field for 'Readings per second', 'Patches per strip' and
'Minimum readings per patch') with their current values."

The Instrument selection is `data.patch_db.INSTRUMENT_LABELS` (Create Chart's
Guided and Manual instrument lists, the presets, `parameters.yaml`'s
printtarg -i). One entry can stand for several devices ("i1Pro / i1Pro 2 /
i1Pro 3"), and the row a strip is judged by is chosen from the name the DEVICE
reports, so every device behind every entry is checked here, by the names
ArgyllCMS 3.5.0 really prints (spectro/insttypes.c, the verbose
"Instrument Type:" headers), against `core.measure_pace.model_key`.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                   # noqa: E402

from core.measure_pace import MODEL_DEFAULTS, model_key  # noqa: E402
from data.patch_db import EXTERNAL_INSTRUMENTS, INSTRUMENT_LABELS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INSTLIB = ROOT / "native" / "instlib"

#: Selection code -> every device behind it: (the name Argyll prints, where it
#: prints it, the Preferences row it must be timed by).
#:   "inst_name" = insttypes.c inst_name(), the engine's JSON "model" and the
#:                 stock "Instrument Type:" header of the i1Pro 1/2 (i1pro_imp.c:1426)
#:   "header"    = the verbose header only (i1pro3_imp.c:927, munki_imp.c:858)
DEVICES = {
    "i1": [("GretagMacbeth i1 Pro", "inst_name", "i1pro"),
           ("X-Rite i1 Pro 2", "inst_name", "i1pro2"),
           ("X-Rite i1 Pro 3", "inst_name", "i1pro3")],
    "p3": [("X-Rite i1 Pro 3 Plus", "header", "i1pro3plus")],
    # i1Studio and ColorChecker Studio are the ColorMunki's USB device, and
    # Argyll's munki driver reports every one of them as a ColorMunki.
    "CM": [("X-Rite ColorMunki", "inst_name", "colormunki"),
           ("ColorMunki", "header", "colormunki")],
}
#: Not timed, by Knut's ruling: no strips.
NO_STRIPS = {"SS": "spectroscan", "CR30": "cr30"}

CASES = [(code, name, where, key)
         for code, devs in DEVICES.items() for name, where, key in devs]


def test_every_entry_of_the_selection_is_accounted_for():
    """A new entry in the Instrument selection fails here until somebody
    decides which row times it."""
    assert set(INSTRUMENT_LABELS) == (set(DEVICES) | set(NO_STRIPS)
                                      | set(EXTERNAL_INSTRUMENTS))


@pytest.mark.parametrize("code,name,where,key", CASES)
def test_each_device_is_a_name_argyll_really_prints(code, name, where, key):
    if where == "inst_name":
        src = (INSTLIB / "insttypes.c").read_text(encoding="utf-8", errors="replace")
        assert f'return "{name}";' in src, name
    elif name.endswith(" Plus"):
        src = (INSTLIB / "i1pro3_imp.c").read_text(encoding="utf-8", errors="replace")
        assert '"Instrument Type:   %s%s\\n"' in src and '" Plus"' in src
        ins = (INSTLIB / "insttypes.c").read_text(encoding="utf-8", errors="replace")
        assert f'return "{name[:-len(" Plus")]}";' in ins
    else:
        src = (INSTLIB / "munki_imp.c").read_text(encoding="utf-8", errors="replace")
        assert f'"Instrument Type:   {name}\\n"' in src


@pytest.mark.parametrize("code,name,where,key", CASES)
def test_each_device_is_timed_by_its_own_row(code, name, where, key):
    assert model_key(name) == key, f"{INSTRUMENT_LABELS[code]}: {name}"
    assert key in MODEL_DEFAULTS
    hz, min_samples = MODEL_DEFAULTS[key]
    assert hz > 0 and min_samples, f"{key} must have a limit to judge by"


def test_the_engine_ships_the_names_it_reports():
    helper = ROOT / "native" / "chromiq-chartread"
    if not helper.is_file():
        pytest.skip("bundled helper not present")
    blob = helper.read_bytes()
    for _code, name, where, _key in CASES:
        if where == "inst_name":
            assert name.encode() in blob, name


@pytest.mark.parametrize("code,want", [("i1", "i1pro"), ("3p", "i1pro"),
                                       ("CM", "colormunki")])
def test_a_chart_alone_falls_back_to_its_familys_row(tmp_path, code, want):
    """Before the device reports, the chart's TARGET_INSTRUMENT decides, and
    printtarg records only the family: "GretagMacbeth i1 Pro" for every i1Pro
    chart, the 3 Plus included (printtarg.c: "3p" is instI1Pro with a layout
    modifier). The family's row is the slowest of its members, which is the
    safe side of Knut's rule."""
    targen = shutil.which("targen") or "/Applications/Argyll/bin/targen"
    printtarg = shutil.which("printtarg") or "/Applications/Argyll/bin/printtarg"
    if not (Path(targen).exists() and Path(printtarg).exists()):
        pytest.skip("Argyll targen/printtarg not available")
    base = tmp_path / "c"
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", "-f20", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    subprocess.run([printtarg, "-v0", f"-i{code}", "-pA4", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    from ui.ti2_loader import read_target_instrument
    assert model_key(read_target_instrument(base.with_suffix(".ti2"))) == want


# ---------------------------------------------------------------------------
# Preferences ▸ Measurement
# ---------------------------------------------------------------------------
@pytest.fixture
def dlg(qapp, tmp_path):
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    # Stored values that are NOT the defaults: the locked rows must show
    # these, not reset them.
    s.set("pace_sample_hz_spectroscan", 123.0)
    s.set("pace_estimate_patches_spectroscan", 7)
    s.set("pace_min_samples_spectroscan", 12)
    s.set("pace_estimate_patches_cr30", 3)
    s.set("pace_min_samples_cr30", 0)
    from ui.dialogs.settings_dialog import SettingsDialog
    d = SettingsDialog(s, None)
    d._settings = s
    yield d
    d.deleteLater()


@pytest.fixture
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _row_label(d, key):
    """The text of the first cell of the row holding *key*'s minimum box."""
    from PyQt6.QtWidgets import QGridLayout, QLabel
    box = d._pace_min[key]
    grid = box.parentWidget().findChildren(QGridLayout)
    for g in [box.parentWidget().layout(), *grid]:
        if not isinstance(g, QGridLayout):
            continue
        idx = g.indexOf(box)
        if idx < 0:
            continue
        row, _c, _rs, _cs = g.getItemPosition(idx)
        w = g.itemAtPosition(row, 0).widget()
        assert isinstance(w, QLabel)
        return w.text()
    raise AssertionError(f"no row for {key}")


@pytest.mark.parametrize("code", sorted(DEVICES))
def test_every_timed_row_is_editable_and_names_its_instruments(dlg, code):
    for _name, _where, key in DEVICES[code]:
        for boxes in (dlg._pace_hz, dlg._pace_patches, dlg._pace_min):
            assert boxes[key].isEnabled(), f"{key} must stay editable"
    if code == "CM":
        label = _row_label(dlg, "colormunki")
        for device in ("ColorMunki", "i1Studio", "ColorChecker Studio"):
            assert device in label, (device, label)


@pytest.mark.parametrize("key", ["spectroscan", "cr30"])
def test_the_rows_without_strips_are_locked_with_their_values(dlg, key):
    boxes = [dlg._pace_patches[key], dlg._pace_min[key]]
    if key == "spectroscan":
        boxes.append(dlg._pace_hz[key])
    for box in boxes:
        assert not box.isEnabled(), f"{key}: {box.toolTip()}"
        assert "no reading speed to set" in box.toolTip()
    if key == "spectroscan":
        assert dlg._pace_hz[key].value() == pytest.approx(123.0)
        assert dlg._pace_patches[key].value() == 7
        assert dlg._pace_min[key].value() == 12
    else:
        assert dlg._pace_patches[key].value() == 3
        assert dlg._pace_min[key].text() in ("Off", dlg._pace_min[key].specialValueText())


def test_the_cr30_rate_cell_is_greyed_with_the_rest(dlg):
    from PyQt6.QtWidgets import QGridLayout, QLabel
    box = dlg._pace_min["cr30"]
    g = box.parentWidget().layout()
    assert isinstance(g, QGridLayout)
    row, *_ = g.getItemPosition(g.indexOf(box))
    cell = g.itemAtPosition(row, 1).widget()
    assert isinstance(cell, QLabel) and not cell.isEnabled()


def test_saving_does_not_change_a_locked_row(dlg):
    s = dlg._settings
    dlg._save_and_close()
    assert float(s.get("pace_sample_hz_spectroscan")) == pytest.approx(123.0)
    assert int(s.get("pace_estimate_patches_spectroscan")) == 7
    assert int(s.get("pace_min_samples_spectroscan")) == 12
    assert int(s.get("pace_estimate_patches_cr30")) == 3


def test_the_help_says_the_clock_starts_at_the_beep(dlg):
    """Knut's Q3: "the help text should mention this, and also mention the
    lamp warmup time between button click and beep"."""
    from ui.dialogs.settings_dialog import pace_clock_note, pace_clock_section
    for text in (pace_clock_note(), pace_clock_section()):
        assert "beep" in text and "lamp" in text and "0.7" in text
        assert "—" not in text
    from PyQt6.QtWidgets import QLabel
    labels = [w.text() for w in dlg.findChildren(QLabel)]
    assert any(pace_clock_note() in t for t in labels), \
        "the note under the Measurement tab's introduction must say it"
    from ui.tooltip_button import TooltipButton
    from core.i18n import tr
    tips = [b for b in dlg.findChildren(TooltipButton)
            if b._title == tr("Warn Me When I Read a Strip Too Fast")]
    assert len(tips) == 1
    assert pace_clock_section().strip() in tips[0]._body, \
        "the pace ⓘ must say it too"


def test_saving_keeps_a_locked_value_its_box_cannot_show(qapp, tmp_path):
    """Review P_review2_beta1: a value an older build stored outside the box's
    range (or a stored 0 Hz) came back clamped / as the default after OK,
    because the locked boxes were written back. They are not written now."""
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("pace_sample_hz_spectroscan", 0.0)
    s.set("pace_estimate_patches_spectroscan", 999)
    s.set("pace_min_samples_spectroscan", 5)
    s.set("pace_estimate_patches_cr30", 999)
    d = SettingsDialog(s, None)
    d._settings = s
    try:
        d._save_and_close()
    finally:
        d.deleteLater()
    assert float(s.get("pace_sample_hz_spectroscan")) == 0.0
    assert int(s.get("pace_estimate_patches_spectroscan")) == 999
    assert int(s.get("pace_min_samples_spectroscan")) == 5
    assert int(s.get("pace_estimate_patches_cr30")) == 999
