"""Settings round-trip + violation logic for the margin inspector."""
from __future__ import annotations

import pytest

from core.settings import AppSettings, default_margin_thresholds, margin_combo_key
from workflow.margin_inspector import MarginReport, Violation, check_violations


def _report(L=20.0, R=20.0, T=20.0, B=20.0) -> MarginReport:
    return MarginReport(left_mm=L, right_mm=R, top_mm=T, bottom_mm=B,
                        strip_width_mm=11.0, page_w_mm=210.0, page_h_mm=297.0)


# --- combo key + seeds -----------------------------------------------------

def test_combo_key_format():
    assert margin_combo_key("i1Pro", "A4", "landscape") == "i1Pro|A4 Landscape"
    assert margin_combo_key("ColorMunki", "A3", "Portrait") == "ColorMunki|A3 Portrait"
    assert margin_combo_key("i1Pro", "A2", "") == "i1Pro|A2"


def test_seed_table_matches_knut_values():
    seeds = default_margin_thresholds()
    # i1Pro primary combos: 26 / 9 / 38 (L/R/T), confirmed (#82). The two
    # full-height-strip combos (A4 Portrait, A3 Landscape) carry a 19 mm bottom
    # so the seeded chart stays under the 240 mm strip-length limit (#130); the
    # other primary combos keep the 9 mm bottom.
    assert seeds["i1Pro|A4 Portrait"] == {"L": 26, "R": 9, "T": 38, "B": 19,
                                          "desc": "i1Pro ruler / jig"}
    assert seeds["i1Pro|A3 Landscape"] == {"L": 26, "R": 9, "T": 38, "B": 19,
                                           "desc": "i1Pro ruler / jig"}
    assert seeds["i1Pro|Letter Portrait"]["B"] == 9      # shorter sheet, stays 9
    assert seeds["i1Pro|A3 Landscape"]["T"] == 38
    # Other i1Pro paper/orientations: plain 9 mm all round.
    assert seeds["i1Pro|A3 Portrait"] == {"L": 9, "R": 9, "T": 9, "B": 9,
                                          "desc": "i1Pro ruler / jig"}
    # ColorMunki: 6 mm sides/bottom, 24 mm on Top.
    assert seeds["ColorMunki|A4 Portrait"]["L"] == 6
    assert seeds["ColorMunki|Tabloid Landscape"]["T"] == 24
    # A fresh call returns an independent copy (no shared mutation).
    seeds["i1Pro|A4 Portrait"]["L"] = 999
    assert default_margin_thresholds()["i1Pro|A4 Portrait"]["L"] == 26


# --- settings round-trip ---------------------------------------------------

def _isolated_settings(tmp_path) -> AppSettings:
    from PyQt6.QtCore import QSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def test_thresholds_round_trip(tmp_path):
    s = _isolated_settings(tmp_path)
    # Empty store → seed defaults.
    assert s.get_margin_thresholds()["i1Pro|A4 Portrait"]["L"] == 26
    table = {"i1Pro|A4 Portrait": {"L": 12.5, "R": 30, "T": 11, "B": 11,
                                   "desc": "my rig"}}
    s.set_margin_thresholds(table)
    got = s.get_margin_thresholds()
    assert got["i1Pro|A4 Portrait"]["R"] == 30
    assert got["i1Pro|A4 Portrait"]["desc"] == "my rig"


def test_corrupt_blob_falls_back_to_seeds(tmp_path):
    s = _isolated_settings(tmp_path)
    s.set("margin_thresholds", "{not json")
    assert s.get_margin_thresholds() == default_margin_thresholds()


# --- violation logic -------------------------------------------------------

def test_no_thresholds_no_violations():
    assert check_violations(_report(), None) == []
    assert check_violations(_report(), {}) == []


def test_below_threshold_flags_edge():
    v = check_violations(_report(L=8.0), {"L": 11, "R": 11, "T": 11, "B": 11})
    assert v == [Violation("Left", 8.0, 11.0)]


def test_equal_threshold_is_ok():
    assert check_violations(_report(L=11.0), {"L": 11}) == []


def test_value_that_displays_equal_is_ok():
    """#85: a margin that rounds to the threshold at 1 decimal (e.g. 5.997 →
    '6.0') must not be flagged below a 6 mm threshold."""
    assert check_violations(_report(L=5.997), {"L": 6}) == []
    assert check_violations(_report(L=6.04), {"L": 6}) == []
    # But a value that displays below it still warns.
    assert check_violations(_report(L=5.94), {"L": 6}) != []


def test_decimal_threshold_supported():
    assert check_violations(_report(L=6.0), {"L": 6.5}) != []
    assert check_violations(_report(L=6.5), {"L": 6.5}) == []


def test_multiple_edges_and_missing_keys():
    v = check_violations(_report(L=5.0, T=2.0),
                         {"L": 11, "T": 11})   # R/B unset → unchecked
    edges = {x.edge for x in v}
    assert edges == {"Left", "Top"}


def test_blank_string_threshold_ignored():
    assert check_violations(_report(L=1.0), {"L": "", "R": 11}) == []


# --- strip-length limit (#16) ----------------------------------------------
# (The Default Patch Sizes table was removed — Knut #93: the instrument's natural
# patch size is a sufficient auto target on its own, so no user-facing table.)

def test_strip_length_limit_round_trip(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import thresholds_for_combo
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    table = s.get_margin_thresholds()
    table[margin_combo_key("i1Pro", "A4", "Portrait")]["ruler"] = 200.0
    s.set_margin_thresholds(table)
    entry = thresholds_for_combo(s.get_margin_thresholds(), "i1", 210.0, 297.0)
    assert entry is not None and entry.get("ruler") == 200.0
