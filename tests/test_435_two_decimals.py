"""Two decimals for every threshold of Preferences ▸ Measurement (#182, Knut
6102031563, answer 2, reversing 4.3.4's one decimal).

    "the one decimal rounding for comparison with the threshold should be
    changed to rounding to two decimals and the value should then show 2
    decimals ... for the neighbour check or the patch error check text in the
    hover-text card. So that will result in a 5.01 value is triggered on a
    5.00 threshold. The threshold values in preferences -> measurement should
    show two decimals too, but increasing or decreasing the number should use
    0.50 steps for every click. A User may manually choose a more detailed
    limit, like 4.35 (if desired). Make sure all texts and the test functions
    use two decimals and that number values checked against the thresholds
    are rounded to two decimals."

Proved here: the shared helper at two decimals; the table's boxes (two
decimals, 0.50 a click, 4.35 typed and kept); stored values kept exactly; the
help; and, over many values, that what a card prints is what was compared,
for the patch error limit and for the neighbour limit.
"""
from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QSettings  # noqa: E402

from workflow import misread_settings as MS  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))


def test_five_point_zero_one_is_above_five():
    assert MS.above(5.01, 5.0) and not MS.above(5.0, 5.0)
    assert MS.above(5.006, 5.00) and not MS.above(5.004, 5.00)
    assert MS.above(4.36, 4.35) and not MS.above(4.35, 4.35)
    assert MS.shown(5) == "5.00" and MS.shown(4.349) == "4.35"


# ---- Preferences ▸ Measurement ----------------------------------------------

def _dialog(tmp_path, values=None):
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    for k, v in (values or {}).items():
        s.set(k, v)
    return s, SettingsDialog(s, None)


def _spins(dlg):
    return (list(dlg._patch_limit_spins.values())
            + list(dlg._neighbour_limit_spins.values())
            + list(dlg._neighbour_radius_spins.values())
            + [dlg._same_reading_spin])


def test_every_threshold_shows_two_decimals_and_steps_by_half(qapp, tmp_path):
    _s, dlg = _dialog(tmp_path)
    spins = _spins(dlg)
    assert len(spins) == 13
    for sp in spins:
        assert sp.decimals() == 2, sp.objectName()
        assert sp.singleStep() == 0.5, sp.objectName()
        import re
        # the system's decimal mark, a point or a comma
        assert re.fullmatch(r"\d+[.,]\d\d", sp.text().split(" ")[0]), \
            sp.text()
    sp = dlg._patch_limit_spins[MS.VERIFICATION]
    sp.setValue(5.0)
    sp.stepUp()
    assert sp.value() == 5.5
    sp.stepDown()
    sp.stepDown()
    assert sp.value() == 4.5


def test_a_typed_value_with_two_decimals_is_kept(qapp, tmp_path):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    s, dlg = _dialog(tmp_path)
    sp = dlg._neighbour_limit_spins[MS.VERIFICATION]
    sp.lineEdit().selectAll()
    QTest.keyClicks(sp.lineEdit(), "4.35")
    QTest.keyClick(sp.lineEdit(), Qt.Key.Key_Return)
    sp.interpretText()
    assert sp.value() == 4.35
    dlg._save_misread_table(s)
    assert MS.neighbour_limit(s, MS.VERIFICATION) == 4.35


#: Values stored by 4.3.4 (one decimal) and one a user typed with two.
STORED = {
    MS.PATCH_ERROR_LIMIT_KEYS[MS.ESTIMATED]: 95.0,
    MS.PATCH_ERROR_LIMIT_KEYS[MS.ACCURATE]: 20.0,
    MS.PATCH_ERROR_LIMIT_KEYS[MS.VERIFICATION]: 5.0,
    MS.PATCH_ERROR_LIMIT_KEYS[MS.CALIBRATION]: 37.5,
    MS.NEIGHBOUR_LIMIT_KEYS[MS.ESTIMATED]: 10.0,
    MS.NEIGHBOUR_LIMIT_KEYS[MS.ACCURATE]: 7.3,
    MS.NEIGHBOUR_LIMIT_KEYS[MS.VERIFICATION]: 4.35,
    MS.NEIGHBOUR_RADIUS_KEYS[MS.ESTIMATED]: 15.0,
    MS.SAME_READING_KEY: 2.5,
}


def test_stored_values_are_kept_exactly(qapp, tmp_path):
    """No migration is needed and none rounds: every value stored before
    (one decimal) and one typed with two come back, and are saved again,
    exactly as they were."""
    s, dlg = _dialog(tmp_path, STORED)
    dlg._save_misread_table(s)
    for k, v in STORED.items():
        assert float(s.get(k)) == v, k


def test_the_help_explains_two_decimals_not_one(qapp, tmp_path):
    from ui.dialogs import settings_dialog as sd
    assert not hasattr(sd, "ONE_DECIMAL_HELP")
    text = sd.TWO_DECIMALS_HELP
    assert text.startswith("TWO DECIMALS\n")
    assert "5.00" in text and "5.01" in text and "0.50" in text
    assert "4.35" in text and "one decimal" not in text.lower()
    import inspect
    src = inspect.getsource(sd.SettingsDialog)
    assert src.count("tr(TWO_DECIMALS_HELP)") == 4


# ---- the cards: what is printed is what was compared, over many values ------

from test_neighbour_check_in_the_measure_tab import (  # noqa: E402
    _card, _flags, _info, _strip, _tab, _text)


def _random_values(seed, n):
    rng = random.Random(seed)
    vals = [round(rng.uniform(3.0, 7.0), rng.choice((2, 3, 4)))
            for _ in range(n)]
    vals += [5.0, 5.004, 5.005, 5.0050001, 5.006, 5.01, 4.99, 4.995, 4.35,
             4.354, 4.355, 4.36]
    return vals


@pytest.mark.parametrize("limit", [5.0, 4.35, 5.5])
def test_the_limit_card_and_the_outline_always_agree(qapp, tmp_path, limit):
    """Hundreds of ΔE*ab values around the limit: a patch is outlined red
    exactly when the ΔE its card prints is above the limit its card prints,
    and both print two decimals."""
    vals = _random_values(int(limit * 100), 300)
    per_tab = 6 * 12           # the harness's six strips of twelve
    for t0 in range(0, len(vals), per_tab):
        tab = _tab(tmp_path / f"t{t0}", settings={
            "patch_read_warn_de_estimated": limit,
            "patch_strip_test_estimated": False,
            "patch_neighbour_check": False})
        batch = vals[t0:t0 + per_tab]
        for i in range(0, len(batch), 12):
            chunk = batch[i:i + 12]
            letter = "ABCDEF"[i // 12]
            ev = _strip(letter)
            for p, de in zip(ev["patches"], chunk + [1.0] * (12 - len(chunk))):
                p["de"] = de
            tab._on_strip_measured(ev)
            for n, de in enumerate(chunk, start=1):
                loc = f"{letter}{n}"
                info = _info(tab, loc)
                red = bool(info["warn"])
                assert bool(_flags(tab)[loc]) is red
                assert red is (float(f"{de:.2f}") > float(f"{limit:.2f}")), \
                    (loc, de)
                if red:
                    text = " ".join(_text(_card(info)).split())
                    # 4.3.5 beta 3: M-PATCH-CARD-PLAIN's words, on a red
                    # card or a yellow one confirmed by similar patches
                    # ("Without that confirmation it would be red: ...")
                    for shown in (f"ΔE*ab {de:.2f} off its expected colour",
                                  f"patch error limit of ΔE*ab {limit:.2f} "
                                  f"for"):
                        assert shown in text, (de, shown)


def test_the_neighbour_card_and_the_outline_always_agree():
    """The neighbour limit, the same way: "ΔE x further" on the card, the
    limit beside it, and the outline, for hundreds of values."""
    from workflow.neighbour_check import NeighbourCheck
    rng = random.Random(6102031563)
    for limit in (3.0, 4.35, 10.0):
        for _ in range(250):
            own = round(limit + rng.uniform(-0.03, 0.03), rng.choice((3, 4)))
            nc = NeighbourCheck(limit=limit)
            nc.set_reading_lab("A1", (50, 0, 0), (50 - own, 0, 0), "A")
            for j, loc in enumerate(("B1", "C1", "D1"), start=1):
                nc.set_reading_lab(loc, (50, j, 0), (50, j, 0), loc[0])
            nc.evaluate()
            further = nc.comparison("A1")[1]
            printed = MS.shown(further)
            assert nc.is_suspect("A1") is (float(printed) > float(
                MS.shown(limit))), (limit, own, further)
