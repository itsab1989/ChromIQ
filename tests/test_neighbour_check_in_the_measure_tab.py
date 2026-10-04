"""The neighbour check in the Measure tab (#182 beta 11, Knut 5983470377
item 5, and the threshold box of 5983725218).

The rule itself is tests/test_neighbour_check.py. Here: the live preview
draws a suspect red even below the limit, with its own card; a re-read with
the same colour turns it yellow; a patch read before its comparisons is
judged again when they arrive; the buffer is the user's; and the check, and
the summary in the closing window, are absent on a verification, a
calibration chart and a chart made from a profile.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from workflow import measurement_messages as M  # noqa: E402
from workflow import patch_flags as pf  # noqa: E402

STRIPS = "ABCDEF"
PER = 12


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class _Settings:
    def __init__(self, d=None):
        self._d = {"chartread_engine": "chromiq", **dict(d or {})}

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


def _exp(letter, n):
    """A lattice of expected colours: each patch has patches of the next and
    previous strip within ΔE 15, so every patch has comparisons."""
    s = STRIPS.index(letter)
    return [18.0 + 2.0 * s, 20.0 + 1.5 * n, 22.0 + 1.0 * s]


def _meas(letter, n, factor=1.0):
    """Every patch read 10 % dark against its rough estimate, as a print is;
    *factor* darkens one reading further (a misread)."""
    return [v * 0.9 * factor for v in _exp(letter, n)]


def _de(e, m):
    from workflow.icc_info import xyz_to_lab
    a = xyz_to_lab(tuple(v / 100 for v in e))
    b = xyz_to_lab(tuple(v / 100 for v in m))
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _strip(letter, bad=None):
    """strip_read event; *bad* maps a loc to its darkening factor."""
    out = []
    for n in range(1, PER + 1):
        loc = f"{letter}{n}"
        e = _exp(letter, n)
        m = _meas(letter, n, (bad or {}).get(loc, 1.0))
        out.append({"id": loc, "loc": loc, "exyz": e, "xyz": m,
                    "de": round(_de(e, m), 2)})
    return {"strip": letter, "patches": out}


def _chart(folder, accurate=False):
    folder.mkdir(parents=True, exist_ok=True)
    ti2 = folder / "chart.ti2"
    ti2.write_text('CTI2\n\nORIGINATOR "ChromIQ layout engine"\n'
                   + ('ACCURATE_EXPECTED_VALUES "true"\n' if accurate else "")
                   + "NUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC\n"
                   "END_DATA_FORMAT\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n",
                   encoding="utf-8")
    return ti2


def _tab(folder, accurate=False, settings=None):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings(settings)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._ti1_path = _chart(folder, accurate)
    tab._page_stripe_rects = [[QRect(0, 20 * i, 600, 18)
                               for i in range(len(STRIPS))]]
    tab._strips_per_page = [len(STRIPS)]
    tab._engine_strips = [{"strip": c} for c in STRIPS]
    tab._patch_boxes = [{f"{c}{n}": QRect(22 * (n - 1), 20 * i, 20, 18)
                         for i, c in enumerate(STRIPS)
                         for n in range(1, PER + 1)}]
    return tab


def _flags(tab):
    by_box = {(b.x(), b.y()): loc for loc, b in tab._patch_boxes[0].items()}
    return {by_box[(it[0].x(), it[0].y())]: it[3]
            for it in tab._preview._patch_overlay.get(0, [])}


def _red(tab):
    return sorted(loc for loc, f in _flags(tab).items() if f is True)


def _info(tab, loc):
    box = tab._patch_boxes[0][loc]
    for b, info in tab._preview._patch_info.get(0, []):
        if (b.x(), b.y()) == (box.x(), box.y()):
            return info
    raise AssertionError(loc)


def _card(info):
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content(info, "both")
    return [text for _sw, text in tile._rows]


def _read_all(tab, bad=None):
    for c in STRIPS:
        tab._on_strip_measured(_strip(c, bad))


def test_the_misread_is_below_the_limit(qapp):
    """The point of the check: the limit 95 cannot see this misread."""
    e, m = _exp("D", 6), _meas("D", 6, 0.55)
    assert _de(e, m) < 95


def test_a_misread_below_the_limit_is_red_with_its_own_card(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == ["D6"]
    info = _info(tab, "D6")
    assert not info["warn"] and info["neighbour"]["n"] >= 3
    lines = _card(info)
    assert M._CARD_NB_RED in lines
    assert M._CARD_NB_5 in lines and M._CARD_RED_READ_AGAIN in lines
    assert any(l.startswith("they should read within ΔE ") for l in lines)
    assert any(l.startswith("but it reads ΔE ") for l in lines)
    assert not any("reached your limit" in l for l in lines)


def test_a_clean_chart_has_no_neighbour_outline(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab)
    assert _red(tab) == []
    assert tab._misread_summary().startswith(M._SUM_NB_NONE)


def test_the_same_reading_again_turns_it_yellow(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._on_strip_measured(_strip("D", {"D6": 0.55}))
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
    lines = _card(_info(tab, "D6"))
    assert "Yellow outline: confirmed by a re-read" in lines
    assert tab.neighbour_summary_facts()["kept"] == ["D6"]
    assert tab.neighbour_summary_facts()["red"] == []


def test_a_good_reading_again_clears_it(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._on_strip_measured(_strip("D"))
    assert _flags(tab)["D6"] is False
    assert _info(tab, "D6")["neighbour"] is None


def test_a_patch_read_first_is_judged_again_when_its_comparisons_arrive(
        qapp, tmp_path):
    """A6 is read before any other strip: no comparisons, not judged. Two
    strips later it has them, and the preview turns it red without A being
    read again."""
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A", {"A6": 0.55}))
    assert _red(tab) == []
    tab._on_strip_measured(_strip("B"))
    tab._on_strip_measured(_strip("C"))
    assert "A6" in _red(tab)
    assert _info(tab, "A6")["neighbour"]["n"] >= 3


def test_the_buffer_is_the_users(qapp, tmp_path):
    tab = _tab(tmp_path, settings={"patch_neighbour_buffer_de": 50.0})
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == []
    tab._settings.set("patch_neighbour_buffer_de", 10.0)
    tab._on_strip_measured(_strip("A"))      # the next batch takes the new value
    assert _red(tab) == ["D6"]


def test_painted_from_disk_it_is_the_same(qapp, tmp_path):
    tab = _tab(tmp_path)
    patches = [p for c in STRIPS for p in _strip(c, {"D6": 0.55})["patches"]]
    tab._on_chart_measured({"patches": patches}, live=False, strip_fence=True)
    assert _red(tab) == ["D6"]


@pytest.mark.parametrize("case", ["verification", "calibration", "accurate"])
def test_not_on_these_charts(qapp, tmp_path, monkeypatch, case):
    folder = tmp_path / ("cal" if case == "calibration" else "run1")
    tab = _tab(folder, accurate=(case == "accurate"))
    if case == "verification":
        monkeypatch.setattr(type(tab), "_is_verification_run", lambda self: True)
    _read_all(tab, {"D6": 0.55})
    assert _red(tab) == []
    assert tab.neighbour_summary_facts() is None
    if case == "verification":
        tab._read_twice_log = [("B", "A", "keep")]
        monkeypatch.setattr(type(tab), "_read_twice_was_active",
                            lambda self: True)
        assert tab._misread_summary() == ""


def test_the_summary_names_what_is_still_red(qapp, tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55, "B11": 0.5})
    text = tab._misread_summary()
    assert text.splitlines()[0] == M._SUM_NB_RED.format(n=2, locs="B11, D6")
    tab._on_strip_measured(_strip("B", {"B11": 0.5}))      # kept as real
    lines = tab._misread_summary().splitlines()
    assert lines[0] == M._SUM_NB_RED_ONE.format(locs="D6")
    assert lines[1] == M._SUM_NB_KEPT_ONE


def test_the_summary_says_what_the_strip_test_found(qapp, tmp_path,
                                                    monkeypatch):
    tab = _tab(tmp_path)
    _read_all(tab)
    monkeypatch.setattr(type(tab), "_read_twice_was_active", lambda self: True)
    tab._read_twice_log = []
    assert tab._misread_summary().splitlines()[-1] == M._SUM_TWICE_NONE
    tab._read_twice_log = [("C", "B", "reread"), ("E", "D", None)]
    assert tab._misread_summary().splitlines()[-1] == M._SUM_TWICE.format(
        n=2, list="C (like B, read again), E (like D, kept)")
    monkeypatch.setattr(type(tab), "_read_twice_was_active", lambda self: False)
    assert M._SUM_TWICE_NONE not in tab._misread_summary()


def test_the_completion_summary_puts_it_under_the_reading_times(qapp,
                                                                tmp_path):
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55})
    tab._measurement_summary = lambda: "Total measuring time: 00:01:00"
    text = tab._completion_summary().splitlines()
    assert text[0] == "Total measuring time: 00:01:00"
    assert text[1] == M._SUM_NB_RED_ONE.format(locs="D6")


def test_suspects_off_alike_in_other_strips_confirm_each_other(qapp,
                                                              tmp_path):
    """A suspect is a red patch like any other (10.9): two of them, of
    different strips, expected nearly the same colour and off in the same
    way, confirm each other as similar patches (Knut 5979886227)."""
    tab = _tab(tmp_path)
    _read_all(tab, {"D6": 0.55, "B3": 0.5})
    assert _flags(tab)["D6"] == pf.FLAG_CONFIRMED
    assert _flags(tab)["B3"] == pf.FLAG_CONFIRMED
    lines = _card(_info(tab, "D6"))
    assert M._CARD_PEER_1 in lines and M._CARD_NB_YELLOW in lines
    assert tab.neighbour_summary_facts()["red"] == []
