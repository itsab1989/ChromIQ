"""#182: two flag limits chosen by the chart, and the yellow outline.

Sebastian, #182 5956560815, approved proposals A and B of 5956305908; Knut
refined A in 5956552085 (*"two values, one for each of the two cases ... each
default wired to the correct circumstance and chart when measuring"*) and B in
5956831467 (*"if those patches have larger error than those previously flagged
for the same color range ... automatically flag these patches with yellow"*).

The patches below are Knut's own: strips A, F and O of his beta-3 run1 (an i1Pro
2 reading of a 648-patch chart with ESTIMATED expected colours), exactly as the
.ti2 (expected) and the .ti3 (measured) hold them. At the new default 95 his
strip A flags A17 and A23, strip F flags F4, strip O flags O9.

Each part has a test that fails without it:

* A, the chart decides: `test_a_profile_made_chart_is_judged_by_the_accurate_limit`
* A, the migration: tests/test_settings_patch_warn_migration.py
* B, a re-read confirms: `test_reading_a_red_strip_again_turns_it_yellow`
* B2, learning: `test_two_close_confirmations_do_not_teach_knuts_blues`,
  and the colour ranges themselves: tests/test_k182_k10_colour_ranges.py
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PyQt6.QtCore import QRect  # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget  # noqa: E402

from workflow import patch_flags as pf  # noqa: E402
from workflow.icc_info import xyz_to_lab  # noqa: E402

#: (loc, expected XYZ from the .ti2, measured XYZ from the .ti3), Y = 100 scale.

@pytest.fixture(autouse=True)
def _reread_route_only(monkeypatch):
    """These tests are about the RE-READ confirmation on Knut's own strips.
    His blues are similar patches of different strips, which confirm each
    other since beta 9 (Knut 5979886227, tests/test_k22_peer_confirmation.py);
    here that route is switched off so each test still measures the re-read."""
    from workflow import patch_flags as _pf
    monkeypatch.setattr(_pf, "PEER_EXPECTED_DE", 0.0)

KNUT = [
    ("A1", (51.7861, 56.9365, 50.9639), (47.3953, 49.9001, 40.7323)),
    ("A2", (21.4997, 23.5995, 22.4715), (18.6359, 19.4010, 16.7082)),
    ("A3", (16.3303, 8.6543, 14.2005), (15.4516, 10.3054, 10.1505)),
    ("A4", (51.1523, 50.3190, 54.9129), (47.3157, 44.8657, 40.5975)),
    ("A5", (43.1028, 37.4070, 99.5563), (28.6426, 27.5437, 43.0117)),
    ("A6", (50.3283, 71.1645, 105.6913), (38.9977, 46.4552, 51.8892)),
    ("A7", (33.6425, 36.9781, 38.9525), (28.9347, 30.4777, 26.4743)),
    ("A8", (53.2024, 57.6063, 102.9228), (44.8559, 47.0573, 63.6293)),
    ("A9", (61.5973, 84.7504, 17.1587), (47.2406, 56.7841, 12.7254)),
    ("A10", (63.8455, 48.9181, 63.5787), (54.0572, 42.2351, 40.7204)),
    ("A11", (62.9612, 83.4576, 107.3983), (52.4595, 58.8073, 59.8980)),
    ("A12", (37.2873, 19.7323, 2.7895), (38.0881, 23.0364, 4.5205)),
    ("A13", (89.4211, 89.6533, 104.2145), (78.3457, 76.5090, 75.0666)),
    ("A14", (18.6599, 17.1123, 3.2656), (18.5675, 16.5451, 4.0222)),
    ("A15", (1.1685, 1.4359, 1.1617), (3.2000, 3.7023, 2.5872)),
    ("A16", (88.4690, 90.6198, 107.4363), (78.2244, 77.7284, 76.7336)),
    ("A17", (18.9593, 8.4265, 95.2349), (6.6063, 6.5640, 19.4108)),
    ("A18", (2.7174, 2.8590, 3.1134), (4.3338, 4.2423, 3.3471)),
    ("A19", (6.2454, 6.0456, 5.2552), (7.0080, 6.4574, 3.8892)),
    ("A20", (16.7713, 15.4812, 32.8859), (12.8416, 12.3608, 16.4531)),
    ("A21", (1.0665, 1.1013, 1.3536), (3.1737, 3.1822, 3.0157)),
    ("A22", (48.4946, 76.8176, 69.7729), (38.1942, 47.0986, 35.8272)),
    ("A23", (19.1748, 8.8575, 95.3068), (6.0850, 6.0143, 17.7297)),
    ("A24", (3.4840, 3.5497, 5.8112), (3.7346, 3.9189, 4.0115)),
    ("A25", (55.8488, 27.6757, 77.0948), (24.6368, 16.0864, 20.8939)),
    ("A26", (4.0839, 4.7628, 3.1995), (4.8468, 5.2032, 2.7064)),
    ("A27", (83.5500, 83.2174, 90.8239), (74.3793, 71.1579, 67.4434)),
    ("F1", (18.0509, 18.9910, 20.6812), (14.7162, 15.1921, 16.1796)),
    ("F2", (20.8203, 12.3255, 32.0634), (15.6335, 10.6633, 16.4730)),
    ("F3", (15.8416, 18.4027, 19.7453), (12.7417, 14.2963, 14.0190)),
    ("F4", (20.1716, 8.8446, 95.2518), (6.7478, 6.2691, 18.7849)),
    ("F5", (93.2185, 96.3370, 108.2895), (81.4764, 81.9629, 79.3119)),
    ("F6", (68.5011, 88.3778, 14.3943), (56.8386, 65.2110, 9.5631)),
    ("F7", (33.4444, 48.8273, 38.4436), (31.2453, 40.0796, 28.3155)),
    ("F8", (86.3706, 95.5256, 108.4938), (73.0524, 76.0889, 79.2340)),
    ("F9", (2.1724, 2.1984, 3.7149), (3.1765, 3.2729, 3.4734)),
    ("F10", (5.3976, 5.5323, 8.6596), (4.9487, 5.0431, 5.7957)),
    ("F11", (22.1702, 23.3248, 25.4007), (18.5189, 19.0110, 17.9061)),
    ("F12", (41.5485, 51.5984, 102.3774), (35.6851, 40.9659, 64.9576)),
    ("F13", (34.2792, 37.3636, 36.3957), (30.9766, 31.7212, 26.0866)),
    ("F14", (84.9437, 89.3674, 97.3210), (79.5477, 79.9792, 76.5562)),
    ("F15", (3.8298, 3.2845, 4.5170), (5.0944, 4.5116, 3.5867)),
    ("F16", (57.2721, 35.7712, 61.3875), (36.5193, 25.2556, 27.0575)),
    ("F17", (85.1858, 96.0543, 56.9560), (74.6622, 80.2143, 35.5495)),
    ("F18", (17.7960, 15.4205, 59.5401), (10.5636, 10.8317, 23.8985)),
    ("F19", (33.0987, 17.5730, 2.5935), (36.9539, 21.9147, 3.7930)),
    ("F20", (26.4944, 25.3008, 34.2921), (21.5140, 19.9990, 20.6564)),
    ("F21", (49.7834, 25.2495, 45.1552), (33.6885, 20.0437, 19.5850)),
    ("F22", (8.1944, 8.7266, 10.8263), (6.8098, 7.1636, 6.3296)),
    ("F23", (40.1777, 73.3347, 33.0310), (28.9062, 38.8149, 18.8742)),
    ("F24", (33.9886, 39.1711, 37.7898), (27.0764, 29.7715, 20.5861)),
    ("F25", (0.9505, 1.0000, 1.0890), (2.6814, 2.7400, 2.1353)),
    ("F26", (7.9944, 3.9737, 31.1273), (5.8962, 5.0342, 14.2882)),
    ("F27", (28.8268, 56.7526, 10.3811), (20.0799, 29.8971, 8.4538)),
    ("O1", (23.5239, 17.5555, 96.7565), (10.8197, 11.6154, 30.0619)),
    ("O2", (90.5176, 96.3473, 105.9924), (83.0091, 84.3897, 81.0409)),
    ("O3", (44.1519, 75.5510, 25.6465), (32.2939, 42.1745, 17.4215)),
    ("O4", (23.3448, 28.6281, 35.0771), (18.1475, 21.6814, 23.1862)),
    ("O5", (4.0656, 4.2774, 4.6581), (5.0300, 5.0200, 4.5510)),
    ("O6", (21.2377, 19.8934, 24.9316), (17.6831, 16.1948, 15.8071)),
    ("O7", (59.1237, 60.4129, 71.8625), (53.6703, 53.1866, 56.1350)),
    ("O8", (1.0414, 1.1376, 1.2558), (2.9809, 3.0499, 2.4946)),
    ("O9", (27.5588, 12.6528, 95.5975), (10.2207, 8.7976, 20.9069)),
    ("O10", (93.0845, 99.2138, 98.5496), (80.8945, 83.3842, 70.3732)),
    ("O11", (5.9790, 6.1791, 5.7683), (6.0648, 6.1805, 4.7834)),
    ("O12", (1.0906, 1.1165, 1.6400), (3.3161, 3.4241, 3.1118)),
    ("O13", (69.6544, 77.8000, 12.2918), (67.0836, 70.6881, 11.5681)),
    ("O14", (42.4336, 48.1714, 43.5786), (39.5506, 42.4959, 30.5852)),
    ("O15", (9.1258, 9.6695, 7.5189), (8.8693, 8.7213, 5.5374)),
    ("O16", (29.3713, 46.7276, 38.2530), (25.7112, 34.9590, 26.0575)),
    ("O17", (17.1653, 8.1126, 58.1627), (9.0612, 7.4527, 17.9777)),
    ("O18", (57.7704, 60.7789, 66.1882), (51.4837, 52.0650, 47.8927)),
    ("O19", (11.9916, 11.7930, 13.4566), (10.7991, 10.1340, 7.6557)),
    ("O20", (47.4704, 24.3243, 32.9748), (37.5131, 21.4658, 18.4523)),
    ("O21", (9.3802, 12.0542, 15.2230), (7.5022, 9.3900, 9.1705)),
    ("O22", (4.4968, 4.2937, 13.9825), (4.2368, 4.6665, 7.9564)),
    ("O23", (2.5877, 2.4499, 2.0470), (3.8956, 3.6441, 2.3782)),
    ("O24", (49.9794, 54.5862, 57.7883), (43.2321, 45.0872, 38.0453)),
    ("O25", (90.2958, 97.7828, 98.1189), (80.6199, 83.3718, 68.0397)),
    ("O26", (8.5281, 16.1551, 3.6149), (8.8891, 13.5228, 4.8924)),
    ("O27", (49.3584, 78.5094, 13.4984), (33.2255, 43.2880, 13.7522)),
]


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def _lab(xyz):
    return xyz_to_lab(tuple(v / 100.0 for v in xyz))


def _de(e, m):
    a, b = _lab(e), _lab(m)
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _strip(letter, *, swap=None):
    """The engine's strip_read event for one of Knut's strips, ΔE as the
    helper computes it (CIE76 on D50 L*a*b*). *swap* replaces one patch's
    measured colour, to make a misread."""
    out = []
    for loc, e, m in KNUT:
        if loc.rstrip("0123456789") != letter:
            continue
        if swap and loc in swap:
            m = swap[loc]
        out.append({"id": loc, "loc": loc, "exyz": list(e), "xyz": list(m),
                    "de": round(_de(e, m), 2)})
    return {"strip": letter, "patches": out}


class _Settings:
    def __init__(self, d=None):
        self._d = dict(d or {})

    def get(self, k, default=None):
        return self._d.get(k, default)

    def set(self, k, v):
        self._d[k] = v


def _chart(tmp_path, accurate: bool):
    ti2 = tmp_path / "chart.ti2"
    # Knut's .ti2 names D65 as its white, as printtarg does for an RGB chart;
    # the colour ranges are classified against it (#182 k10).
    ti2.write_text('CTI2\n\nORIGINATOR "ChromIQ layout engine"\n'
                   'APPROX_WHITE_POINT "95.050000 100.000000 108.900000"\n'
                   + ('ACCURATE_EXPECTED_VALUES "true"\n' if accurate else "")
                   + "NUMBER_OF_FIELDS 2\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC\n"
                   "END_DATA_FORMAT\nNUMBER_OF_SETS 0\nBEGIN_DATA\nEND_DATA\n",
                   encoding="utf-8")
    return ti2


def _tab(tmp_path, accurate=False, settings=None):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings(settings or {"chartread_engine": "chromiq"})
    tab = TabMeasure(ArgyllRunner(s), s)
    tab._ti1_path = _chart(tmp_path, accurate)
    # Knut's chart has strips A to X on one page; only A, F and O are fed.
    every = [chr(ord("A") + i) for i in range(24)]
    tab._page_stripe_rects = [[QRect(0, 20 * i, 600, 18) for i in range(24)]]
    tab._strips_per_page = [24]
    tab._engine_strips = [{"strip": c} for c in every]
    boxes = {}
    for i, c in enumerate(every):
        if c not in ("A", "F", "O"):
            continue
        for n in range(1, 28):
            boxes[f"{c}{n}"] = QRect(22 * (n - 1), 20 * i, 20, 18)
    tab._patch_boxes = [boxes]
    return tab


def _flags(tab):
    """loc → what the preview was told to draw."""
    boxes = tab._patch_boxes[0]
    by_box = {(b.x(), b.y()): loc for loc, b in boxes.items()}
    return {by_box[(it[0].x(), it[0].y())]: it[3]
            for it in tab._preview._patch_overlay.get(0, [])}


def _info(tab, loc):
    box = tab._patch_boxes[0][loc]
    for b, info in tab._preview._patch_info.get(0, []):
        if (b.x(), b.y()) == (box.x(), box.y()):
            return info
    raise AssertionError(loc)


def _card(qapp, info):
    from ui.tiff_preview import _PatchInfoTile
    host = QWidget()
    tile = _PatchInfoTile(host)
    tile.set_content(info, "both")
    return [text for _sw, text in tile._rows]


# ---- A: the chart decides which limit ---------------------------------------
def test_the_keyword_is_read_from_the_chart(tmp_path):
    assert pf.chart_has_accurate_expected_values(_chart(tmp_path, True))
    assert not pf.chart_has_accurate_expected_values(_chart(tmp_path, False))
    # The layout engine does not carry it into the .ti2: the .ti1 is asked.
    (tmp_path / "chart.ti1").write_text(
        'CTI1\n\nACCURATE_EXPECTED_VALUES "true"\nBEGIN_DATA\nEND_DATA\n',
        encoding="utf-8")
    assert pf.chart_has_accurate_expected_values(tmp_path / "chart.ti2")
    assert not pf.chart_has_accurate_expected_values(tmp_path / "missing.ti2")


def test_knuts_chart_at_the_new_default_flags_ten_not_seventy_two():
    """Not a chart file of his, but his numbers: the A, F, O strips here."""
    des = {loc: _de(e, m) for loc, e, m in KNUT}
    assert sorted(l for l, d in des.items() if d >= 95.0) == ["A17", "A23", "F4", "O9"]
    assert sum(d >= 50.0 for d in des.values()) > 4


def test_an_estimated_chart_is_judged_by_the_estimated_limit(tmp_path):
    tab = _tab(tmp_path, accurate=False)
    tab._on_strip_measured(_strip("A"))
    red = sorted(l for l, f in _flags(tab).items() if f is True)
    assert red == ["A17", "A23"]
    info = _info(tab, "A17")
    assert info["warn_de"] == 95.0 and info["accurate"] is False


def test_a_profile_made_chart_is_judged_by_the_accurate_limit(tmp_path):
    tab = _tab(tmp_path, accurate=True)
    tab._on_strip_measured(_strip("A"))
    info = _info(tab, "A17")
    assert info["warn_de"] == 20.0 and info["accurate"] is True
    red = [l for l, f in _flags(tab).items() if f]
    assert "A17" in red and len(red) > 2


def test_each_limit_is_the_users_own(tmp_path):
    tab = _tab(tmp_path, accurate=False, settings={
        "patch_read_warn_de_estimated": 105.5, "patch_read_warn_de_accurate": 12.0})
    tab._on_strip_measured(_strip("A"))
    assert _info(tab, "A17")["warn_de"] == 105.5
    assert [l for l, f in _flags(tab).items() if f] == []   # A17 is 105.3


def test_the_card_names_the_limit_it_used(qapp, tmp_path):
    tab = _tab(tmp_path, accurate=True)
    tab._on_strip_measured(_strip("A"))
    # beta 17: the patch error limit by its name, value and chart type (the
    # k56 card Knut approved in 6084176226)
    text = " ".join(_card(qapp, _info(tab, "A17")))
    assert "reached the patch error limit" in text
    assert "profiling charts made with a pre-conditioning profile" in text
    # Its own folder inside tmp_path, never tmp_path / "..": that is the
    # worker's shared basetemp, which later tests' files sit one level under.
    (tmp_path / "estimated").mkdir()
    tab2 = _tab(tmp_path / "estimated", accurate=False)
    tab2._on_strip_measured(_strip("A"))
    assert "profiling charts with estimated colours" in " ".join(
        _card(qapp, _info(tab2, "A17")))


def test_preferences_show_and_save_both_limits(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QDialog, QLabel
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    monkeypatch.setattr(QDialog, "accept", lambda self: None)
    s = AppSettings()
    s.set("patch_read_warn_de_estimated", 88.0)
    s.set("patch_read_warn_de_accurate", 22.0)
    d = SettingsDialog(s, None)
    try:
        assert d._patch_warn_est_spin.value() == 88.0
        assert d._patch_warn_acc_spin.value() == 22.0
        assert d._patch_warn_est_spin.maximum() >= 110.0   # Knut's largest is 107
        texts = {w.text() for w in d.findChildren(QLabel)}
        # beta 17: the table's column headings (Knut 6078174421)
        assert "Profiling charts with estimated colours" in texts
        assert "Profiling charts made with a pre-conditioning profile" in texts
        d._patch_warn_est_spin.setValue(101.0)
        d._patch_warn_acc_spin.setValue(27.0)
        d._save_and_close()
        assert float(s.get("patch_read_warn_de_estimated")) == 101.0
        assert float(s.get("patch_read_warn_de_accurate")) == 27.0
    finally:
        d.deleteLater()


# ---- B: a second reading confirms ------------------------------------------
def test_the_judge_confirms_only_a_live_second_reading_of_the_same_colour():
    j = pf.FlagJudge()
    e, m = (50.0, 60.0, -70.0), (40.0, 30.0, -40.0)
    assert j.judge("A1", e, m, 47.0, True).flag is pf.FLAG_RED
    # the file repainted: the same reading, not a second one
    assert j.judge("A1", e, m, 47.0, True, live=False).flag is pf.FLAG_RED
    v = j.judge("A1", e, (41.0, 31.0, -41.5), 46.0, True)
    assert v.flag == pf.FLAG_CONFIRMED and v.prev_de == 47.0
    # a third reading clearly different is not confirmed any more
    assert j.judge("A1", e, (60.0, 55.0, -20.0), 51.0, True).flag is pf.FLAG_RED
    # read clean, live, after a red reading: green, a corrected misread
    # (Knut, #182 5984277558); repainted clean it stays green
    v = j.judge("A1", e, e, 0.0, False)
    assert v.flag == pf.FLAG_CORRECTED and v.prev_de == 51.0
    assert j.judge("A1", e, e, 0.0, False, live=False).flag == pf.FLAG_CORRECTED
    # a patch never red, read clean: no outline at all
    assert j.judge("B1", e, e, 0.0, False).flag is pf.FLAG_NONE
    j.reset()
    assert j.confirmed == []


def test_reading_a_red_strip_again_turns_it_yellow(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A"))
    # Knut's re-read: the instrument gives the colour again, within noise.
    again = _strip("A")
    for p in again["patches"]:
        p["xyz"] = [v * 1.004 for v in p["xyz"]]
    tab._on_strip_measured(again)
    flags = _flags(tab)
    assert flags["A17"] == pf.FLAG_CONFIRMED and flags["A23"] == pf.FLAG_CONFIRMED
    info = _info(tab, "A17")
    assert info["flag"] == "confirmed"
    rows = _card(qapp, info)
    i = next(i for i, r in enumerate(rows) if r.startswith("─"))
    tail = rows[i + 1:]
    assert tail[0] == "Yellow outline: confirmed by a re-read"
    assert "paper cannot reach, not a misread." in tail
    assert "Red outline: a large difference" not in rows


def test_a_re_read_that_differs_stays_red(tmp_path):
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A"))
    a17_e = next(e for l, e, m in KNUT if l == "A17")
    # a different, still far-off colour: a misread the first or second time
    tab._on_strip_measured(_strip("A", swap={"A17": (a17_e[0] * 0.2, a17_e[1] * 0.9, a17_e[2] * 0.1)}))
    assert _flags(tab)["A17"] is True


def test_a_fresh_read_forgets_a_resumed_one_remembers(tmp_path):
    """#182 K4 (Sebastian 5959447807): the yellow memory belongs to the
    measurement. A completely new read replaces the readings it was confirmed
    against and forgets it; a read that resumes them takes it back from the
    file kept beside the .ti3 (tests/test_k182_k3_k4_overlay_and_memory.py
    covers the file itself)."""
    tab = _tab(tmp_path)
    tab._session_live = True
    tab._on_strip_measured(_strip("A"))
    tab._on_strip_measured(_strip("A"))
    assert _flags(tab)["A17"] == pf.FLAG_CONFIRMED
    # the session wrote its memory beside the measurement it is reading
    from workflow import confirmed_patches as cp
    ti3 = tab._ti1_path.with_suffix(".ti3")
    ti3.write_text("CTI3\n", encoding="utf-8")       # the final file
    tab._session_live = False
    tab._ti3_mtime_before = None
    tab._save_confirmed_memory(ti3)
    assert cp.confirmed_locations(ti3) >= {"A17", "A23"}
    tab._session_live = True
    tab._session_resumes = False
    tab._on_session_map([{"strip": c, "read": False} for c in "AFO"])
    assert tab._flag_judge().confirmed == []
    tab._session_resumes = True
    tab._on_session_map([{"strip": c, "read": False} for c in "AFO"])
    assert set(tab._flag_judge().confirmed) >= {"A17", "A23"}


@pytest.mark.parametrize("hex_mode", [False, True])
@pytest.mark.parametrize("flag,want", [(True, "red"), (pf.FLAG_CONFIRMED, "yellow"),
                                       (pf.FLAG_LEARNED, "yellow")])
def test_the_preview_draws_the_ring_in_its_colour(qapp, tmp_path, hex_mode,
                                                  flag, want):
    """Rendered, rectangular and hexagonal charts alike: a yellow patch has no
    red ring pixel and a red one no yellow pixel."""
    from PIL import Image
    from PyQt6.QtGui import QColor
    from ui.tiff_preview import TiffPreview
    tif = tmp_path / "flat.tif"
    Image.new("RGB", (500, 640), (128, 128, 128)).save(tif)
    p = TiffPreview()
    p.resize(520, 640)
    p.load_tiff([tif])
    p.set_hex_zigzag(hex_mode)
    p.set_patch_overlay(0, [(QRect(160, 160, 120, 120), QColor("#3050ff"),
                             QColor("#3050ff"), flag)], replace_page=True)
    p.show()
    qapp.processEvents()
    img = p.grab().toImage()
    p.close()
    red = yellow = 0
    for y in range(0, img.height(), 2):
        for x in range(0, img.width(), 2):
            c = img.pixelColor(x, y)
            if c.red() > 220 and c.green() < 90 and c.blue() < 90:
                red += 1
            elif c.red() > 220 and c.green() > 180 and c.blue() < 90:
                yellow += 1
    if want == "red":
        assert red > 50 and yellow == 0, (red, yellow)
    else:
        assert yellow > 50 and red == 0, (red, yellow)


def test_a_yellow_patch_does_not_sound_off(tmp_path):
    import core.sound as snd
    tab = _tab(tmp_path, settings={"sound_enabled": True})
    played = []
    tab._sound.play = played.append
    tab._sound._in_measurement = True
    ev = _strip("A")["patches"][16]
    assert ev["loc"] == "A17"
    for _ in range(2):
        tab._manager.patch_measured.emit(dict(ev))
    assert played == [snd.PATCH_OUT_OF_TOL, snd.PATCH_OK]


# ---- B2: learning, within a colour range (#182 k10) -------------------------
#: Three blues (D50 L*a*b*, hue about 288°) pairwise at least ΔE 7 apart: what a
#: colour range needs before it learns (Knut 5961180259 on 5961078418).
BLUES = [(30.0, 20.0, -60.0), (37.0, 20.0, -60.0), (44.0, 20.0, -60.0)]
#: How each falls short of its blue: less chroma, a little lighter (ΔE 32.4).
SHORT = (5.0, -20.0, 25.0)


def _confirm_blues(j, *, standout=None):
    for i, e in enumerate(BLUES, 1):
        m = tuple(a + b for a, b in zip(e, SHORT))
        for _ in range(2):
            j.judge(f"X{i}", e, m, 32.4, True, standout=standout)
    assert j.confirmed == ["X1", "X2", "X3"]
    assert j.range_status("blue")[0] == 3


def test_two_close_confirmations_count_as_two_knuts_blues(qapp, tmp_path):
    """Knut's own strips: A17 and A23 confirmed are two blues 3 ΔE apart. They
    count as two since beta 9 (no ΔE 6 spacing, Knut 5979886227), which is
    still short of three, so F4, a blue off the same way, stays red (peers are
    off in this file). Its card says how far the range has got."""
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A"))
    tab._on_strip_measured(_strip("A"))          # A17 and A23 confirmed
    tab._on_strip_measured(_strip("F"))
    assert _flags(tab)["F4"] is True
    info = _info(tab, "F4")
    assert info["colour_range"] == "blue" and info["range_k"] == 2
    rows = _card(qapp, info)
    assert "Colour range: blue" in rows
    assert "2 of 3 confirmations so far" in rows
    # O9 (hue 311°) is blue at the 315° edge (Knut 5963411325; it was purple
    # at 310°): the same range, still two confirmations of three.
    tab._on_strip_measured(_strip("O"))
    assert _flags(tab)["O9"] is True
    o9 = _info(tab, "O9")
    assert o9["colour_range"] == "blue" and o9["range_k"] == 2
    rows = _card(qapp, o9)
    assert "Colour range: blue" in rows
    assert "2 of 3 confirmations so far" in rows


def test_nothing_is_learned_before_a_confirmation(tmp_path):
    tab = _tab(tmp_path)
    tab._on_strip_measured(_strip("A"))
    tab._on_strip_measured(_strip("F"))
    assert _flags(tab)["F4"] is True


def test_a_misread_in_a_learned_colour_range_stays_red():
    """The conservative half (Basti's brief): in a blue range that HAS
    learned, a blue misread as a red is not the printer falling short of
    blue, though its expected colour is in the range and its ΔE is larger."""
    j = pf.FlagJudge()
    _confirm_blues(j)
    e = (33.0, 21.0, -61.0)
    assert j.judge("X4", e, (45.0, 60.0, 40.0), 112.0, True).flag is pf.FLAG_RED
    assert j.judge("X5", e, tuple(a + b for a, b in zip(e, SHORT)), 32.4,
                   True).flag == pf.FLAG_LEARNED


def test_a_patch_that_stands_out_far_more_than_the_reference_stays_red():
    j = pf.FlagJudge()
    _confirm_blues(j, standout=20.0)
    near_e = (32.0, 22.0, -62.0)
    shifted = tuple(a + b for a, b in zip(near_e, (6.0, -20.0, 25.0)))
    assert j.judge("X4", near_e, shifted, 33.0, True, standout=25.0).flag \
        == pf.FLAG_LEARNED
    assert j.judge("X5", near_e, shifted, 33.0, True, standout=45.0).flag \
        is pf.FLAG_RED
    # a learned patch is never itself a reference
    assert j.confirmed == ["X1", "X2", "X3"]


def test_patch_by_patch_the_direction_of_the_error_is_what_decides():
    """No strip, so no stand-out figure: a reading whose error points another
    way (here: much lighter and redder, where the confirmed ones fell short of
    the blue) stays red however large it is; one that falls short the same
    way, further, turns yellow."""
    j = pf.FlagJudge()
    _confirm_blues(j)
    near_e = (31.0, 21.0, -61.0)
    other_way = (60.0, 30.0, -20.0)              # shift (29, 9, 41)
    further = (37.0, -6.0, -30.0)                # shift (6, -27, 31)
    assert j.judge("X4", near_e, other_way, 51.0, True).flag is pf.FLAG_RED
    assert j.judge("X5", near_e, further, 41.5, True).flag == pf.FLAG_LEARNED
