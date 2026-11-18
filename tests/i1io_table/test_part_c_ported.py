"""Ported from the tester program chromiq-i1io-session 0.6.0: ``tests/test_i1io_part_c.py`` (branch
tester/i1io-session-0.6.0, 84d30fa1d), the tests that need only the modules that moved into
``workflow/i1io/table/`` and the simulators in ``tests/i1io_table/``. Test bodies are verbatim;
only this header and the imports are new (test_guarantees_in_the_app.py says what stayed).
No hardware: the simulated table and fake readers only.
"""
from __future__ import annotations

import ast  # noqa: F401
import hashlib  # noqa: F401
import inspect  # noqa: F401
import json  # noqa: F401
import math  # noqa: F401
import plistlib  # noqa: F401
import re  # noqa: F401
import signal  # noqa: F401
import subprocess  # noqa: F401
import sys  # noqa: F401
import zipfile  # noqa: F401
from pathlib import Path  # noqa: F401

import pytest  # noqa: F401

from tests.i1io_table import part_c_sim as csim  # noqa: F401
from tests.i1io_table import session_sim as sim_mod  # noqa: F401
from tests.i1io_table._moved import PKG, ROOT  # noqa: F401
from workflow.i1io.table import geometry as geo  # noqa: F401
from workflow.i1io.table import lines as cl  # noqa: F401
from workflow.i1io.table import reader as rd  # noqa: F401
from workflow.i1io.table import scan as sc  # noqa: F401
from workflow.i1io.table import session_table as tbl  # noqa: F401


A = geo.MEASURING_AREA


R = geo.AREA_RAW


def test_the_area_figures_are_pinned():
    assert (R.xmin, R.xmax, R.ymin, R.ymax) == (-1434, 1766, 473, 2773)
    assert (A.xmin, A.xmax, A.ymin, A.ymax) == (-1384, 1716, 523, 2723)
    assert R.xmax - R.xmin == 3200 and R.ymax - R.ymin == 2300      # 320 x 230 mm
    # every recorded chart move lies inside the target area
    assert A.contains(sc.RECORDED_ROW["start"]) and A.contains(sc.RECORDED_ROW["end"])
    for t in tbl.SPOT_TARGETS:
        assert A.contains(t)
    for t in RECORDED_TARGETS_ALL:
        assert A.contains(t), t


P0_FRONTMOST = ((-1413, 2773), (-1324, 2758), (-1434, 2755))     # R1 431.410, 279.888, 272.108


P0_RIGHTMOST = (-1434, 2755)                                     # R1 272.108


P0_FRONT_AFTER_MOTOR = (1169, 2560)                              # S2, after m2 to (1171, 2559)


P1_FRONTMOST = (1268, 3109)                                      # R1 412.443, mark 2


def test_the_front_edge_is_the_frontmost_sensor_reading_not_a_sight_reading():
    """Safety review of 7382e56f2, required change: both edges of the PROVEN zone rest on p0
    (sensor) readings; fix 2/3: the front zone beyond it is capped for targets at the frontmost
    recorded aim (no margin added), for swept rectangles at that plus the 5-unit arrival
    tolerance."""
    assert geo.FRONTMOST_Y_REACHED == max(p[1] for p in P0_FRONTMOST) == R.ymax
    assert geo.SMALLEST_X_REACHED == P0_RIGHTMOST[0] == R.xmin
    assert R.ymax < P1_FRONTMOST[1] - 300           # the sight reading is ~31 mm further front
    assert A.ymax == R.ymax - 50 and A.ymax < max(p[1] for p in P0_FRONTMOST)
    with pytest.raises(geo.AreaRefused, match="DZ"):
        geo.check_target((0, A.ymax + 1), "x")
    assert A.contains(P0_FRONT_AFTER_MOTOR)
    for dx, dy in geo.SIGHT_TO_SENSOR_SEEN:
        assert -323 <= dy <= -306 and -120 <= dx <= -83
    for name, pts in geo.RECORDED_ALIGNMENTS.items():
        if name in ("R1 716.8", "R2 144.5"):
            continue
        assert pts[1][1] > A.ymax and pts[2][1] > A.ymax, name
    # the cap: the frontmost recorded aim (p1, R1 412.443), nothing added (fix 3)
    assert geo.FRONTMOST_AIM_Y == P1_FRONTMOST[1] == max(
        p[1] for pts in geo.RECORDED_ALIGNMENTS.values() for p in pts)
    assert geo.FRONT_CAP_Y == 3109 == geo.CAP_AREA.ymax
    assert geo.ARRIVAL_SLACK == 5
    assert geo.FRONT_SWEEP_CAP_Y == 3114 == geo.CAP_RAW.ymax


CAP = geo.CAP_AREA


@pytest.mark.parametrize("x,y,ok", [(A.xmin, A.ymin, True), (A.xmax, A.ymax, True),
                                    (A.xmax, CAP.ymax, True),
                                    (A.xmin - 1, 2000, False), (A.xmax + 1, 2000, False),
                                    (0, A.ymin - 1, False), (0, CAP.ymax + 1, False),
                                    (0, 2000, True)])
def test_a_computed_line_is_built_and_passed_only_inside_the_cap(x, y, ok):
    """The builders and classify (stateless) never pass a line beyond the front zone's cap;
    what this sitting allows inside it is the gate's job (next tests)."""
    if ok:
        for line in (geo.m0_line(x, y), geo.m2_line(x, y, 54)):
            assert cl.classify(line)[1] is True
    else:
        with pytest.raises(geo.AreaRefused):
            geo.m0_line(x, y)
        with pytest.raises(geo.AreaRefused):
            geo.m2_line(x, y, 54)
        forged = geo._line("m0", x, y, 300)
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(forged)


@pytest.mark.parametrize("speed", [1, 39, 55, 100, 120, 139, 300, 1000])
def test_a_scan_move_at_an_unrecorded_speed_is_refused(speed):
    with pytest.raises(geo.AreaRefused):
        geo.m2_line(0, 2000, speed)
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(geo._line("m2", 0, 2000, speed))


@pytest.mark.parametrize("speed", [100, 150, 299, 301, 500])
def test_a_computed_move_at_an_unrecorded_speed_is_refused(speed):
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(geo._line("m0", 0, 2000, speed))


class _T:
    position_now = None


@pytest.mark.parametrize("start,ok", [((0, 2000), True), ((R.xmin, R.ymin), True),
                                      ((R.xmin - 1, 2000), False), ((0, R.ymax + 1), False),
                                      ((1102, 0), False), (None, False)])
def test_the_gate_checks_the_whole_swept_rectangle_from_a_fresh_reading(start, ok):
    t = _T()
    t.position_now = start
    gate = cl.make_gate(t)
    line = geo.m0_line(0, 2000)
    if ok:
        assert gate(line) == ("m0", True, "computed m0")
    else:
        with pytest.raises(tbl.ForbiddenLine):
            gate(line)


def test_the_gate_lets_nothing_else_through():
    allowed = {tbl.WIRE[k] for k in cl.PART_C_WIRE_KEYS} | set(cl.C_FIXED.values())
    for line in allowed:
        cl.classify(line)
    # part A's move to Y 250 is not part C's (outside the area); its move to (1102, 1000)
    # lies inside the area, so part C would pass it only as a computed move (fresh reading,
    # swept rectangle), never as a fixed line
    with pytest.raises(tbl.ForbiddenLine):
        cl.classify(tbl.WIRE["to_250"])
    assert cl.classify(tbl.WIRE["to_1000"])[2] == "computed m0"
    for bad in (b";i02e\r", b";u8000060000100d1x\r", b";d1016e34\r", b";m0\r",
                b";m00000000012c00\r", b";w8000000\r", b";m2000007d0003600\r"):
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(bad)


def test_every_fixed_part_c_line_is_byte_for_byte_its_recorded_form():
    assert {k: v.decode().rstrip("\r") for k, v in cl.C_FIXED.items()} == {
        "aim": ";p124", "scan_c4": ";c42e", "scan_d1": ";d1016d35", "scan_a3": ";a331",
        "scan_c3": ";c32f"}
    assert {csim.C_P1, csim.C_C4, csim.C_D1, csim.C_A3, csim.C_C3} == {
        v.decode().rstrip("\r") for v in cl.C_FIXED.values()}
    assert sc.recorded_row_plan().m0 == sc.RECORDED_ROW["m0_line"]
    assert sc.recorded_row_plan().m2 == sc.RECORDED_ROW["m2_line"]


def test_the_simulator_keeps_its_own_copy_of_the_area_and_speeds():
    assert csim.C_TARGET_BOX == (CAP.xmin, CAP.xmax, CAP.ymin, CAP.ymax)
    assert csim.C_SWEEP_BOX == (R.xmin, R.xmax, R.ymin, geo.CAP_RAW.ymax)
    assert csim.C_PROVEN_Y == (A.ymax, R.ymax) and csim.C_CREEP == geo.CREEP_STEP
    assert csim.C_SPEEDS_M2 == geo.RECORDED_M2_SPEEDS
    src = (PKG / "i1io_part_c_sim.py").read_text(encoding="utf-8")
    assert "i1io_geometry" not in src and "i1io_c_lines" not in src


def _aims_mm(pts):
    (p1, p2, p3) = pts
    l12 = ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5 / 10
    l23 = ((p2[0] - p3[0]) ** 2 + (p2[1] - p3[1]) ** 2) ** 0.5 / 10
    return ((0.0, 0.0), (0.0, l12), (l23, l12))


def test_the_recorded_alignments_pass_the_checks_and_reach_into_the_front_zone():
    """Fix 2: every non-degenerate recorded alignment is accepted (its marks lie inside the cap),
    and every one reaches into the front zone (its bottom marks lie in front of the proven
    part); the two degenerate ones are refused."""
    for name, pts in geo.RECORDED_ALIGNMENTS.items():
        aims = _aims_mm(pts)
        if name in ("R1 716.8", "R2 144.5"):
            with pytest.raises(geo.AlignmentRefused):
                geo.fit_alignment(aims, pts)
            continue
        al = geo.fit_alignment(aims, pts)
        assert abs(al.checks["rotation_deg"]) < 1.0
        assert max(p[1] for p in al.readings) > A.ymax
    # on the frontmost recorded mark: still inside; one unit more: refused (fix 3)
    pts = geo.RECORDED_ALIGNMENTS["R1 401.6"]
    geo.fit_alignment(_aims_mm(pts), pts)
    with pytest.raises(geo.AlignmentRefused, match="further to the front than any mark"):
        geo.fit_alignment(_aims_mm(pts), [(x, y + 1) for x, y in pts])


RECORDED_SPOT_TARGETS = {
    "S2 383.3": [(-1181, 1658), (-1094, 1659), (-1007, 1659), (-920, 1659), (-833, 1659),
                 (-745, 1659), (-658, 1660), (-571, 1660), (-484, 1660), (-396, 1660),
                 (-309, 1660), (-222, 1661), (-135, 1661), (-48, 1661), (39, 1661), (126, 1661),
                 (213, 1661), (300, 1662), (388, 1662), (475, 1662), (562, 1662), (649, 1662),
                 (736, 1663), (824, 1663), (911, 1663), (998, 1663), (1085, 1663), (1173, 1663)],
    "S2 684.0": [(-1182, 1657), (-1094, 1657), (-1007, 1657), (-919, 1657), (-832, 1658),
                 (-744, 1658), (-657, 1658), (-569, 1659), (-482, 1659), (-394, 1659),
                 (-307, 1659), (-219, 1660), (-132, 1660), (-44, 1660), (42, 1661), (130, 1661),
                 (217, 1661), (305, 1662), (392, 1662), (480, 1662), (567, 1662), (655, 1663),
                 (742, 1663), (830, 1663), (917, 1664), (1005, 1664), (1092, 1664), (1180, 1665)],
}


RECORDED_SCAN_TARGETS = {
    "S2 3.5": (18, [
        (-1196, 1645), (1175, 1735), (-1197, 1795), (1174, 1885), (-1198, 1945), (1174, 2035),
        (-1199, 2094), (1173, 2184), (-1200, 2244), (1172, 2334), (-1200, 2394), (1171, 2484),
        (-1201, 2543), (1175, 1661), (-1197, 1720), (1175, 1810), (-1198, 1870), (1174, 1960),
        (-1198, 2020), (1173, 2110), (-1199, 2169), (1172, 2259), (-1200, 2319), (1172, 2409),
        (-1201, 2469), (1171, 2559)
    ]),
    "S2 526.8": (18, [
        (-1191, 1653), (1180, 1748), (-1193, 1802), (1178, 1897), (-1194, 1951), (1177, 2045),
        (-1195, 2100), (1180, 1674), (-1192, 1728), (1179, 1822), (-1193, 1877), (1178, 1971),
        (-1195, 2025), (1176, 2120)
    ]),
    "S2 270.8": (18, [
        (-1095, 1636), (1192, 1658), (1188, 1658), (1103, 1657), (1019, 1656), (934, 1655),
        (850, 1654), (765, 1654), (681, 1653), (597, 1652), (512, 1651), (428, 1651), (343,
        1650), (259, 1649), (175, 1648), (90, 1647), (6, 1647), (-78, 1646), (-162, 1645),
        (-246, 1644), (-331, 1643), (-415, 1643), (-500, 1642), (-584, 1641), (-668, 1640),
        (-753, 1640), (-837, 1639), (-922, 1638), (-1006, 1637), (-1090, 1636)
    ]),
    "R1 401.6": (17, [
        (-1290, 1674), (1290, 1705), (1286, 1705), (1190, 1703), (1095, 1702), (1000, 1701),
        (904, 1700), (809, 1699), (714, 1698), (619, 1697), (523, 1696), (428, 1695), (333,
        1693), (238, 1692), (142, 1691), (47, 1690), (-47, 1689), (-142, 1688), (-238, 1687),
        (-333, 1686), (-428, 1685), (-523, 1683), (-619, 1682), (-714, 1681), (-809, 1680),
        (-904, 1679), (-1000, 1678), (-1095, 1677), (-1190, 1676), (-1285, 1675), (-1292, 1757),
        (1289, 1787), (1284, 1787), (1189, 1786), (1094, 1785), (999, 1784), (903, 1783), (808,
        1782), (713, 1780), (618, 1779), (522, 1778), (427, 1777), (332, 1776), (237, 1775),
        (141, 1774), (46, 1773), (-48, 1772), (-143, 1770), (-239, 1769), (-334, 1768), (-429,
        1767), (-524, 1766), (-620, 1765), (-715, 1764), (-810, 1763), (-906, 1762), (-1001,
        1760), (-1096, 1759), (-1191, 1758), (-1287, 1757)
    ]),
    "R2 427.5": (17, [
        (-1270, 1537), (1316, 1543), (1311, 1543), (1216, 1542), (1121, 1542), (1025, 1542),
        (930, 1542), (834, 1542), (739, 1541), (643, 1541), (548, 1541), (452, 1541), (357,
        1541), (262, 1540), (166, 1540), (71, 1540), (-24, 1540), (-119, 1540), (-215, 1540),
        (-310, 1539), (-406, 1539), (-501, 1539), (-596, 1539), (-692, 1539), (-787, 1538),
        (-883, 1538), (-978, 1538), (-1074, 1538), (-1169, 1538), (-1265, 1538), (-1270, 1620),
        (1316, 1625), (1311, 1625), (1216, 1624), (1121, 1624), (1025, 1624), (930, 1624), (834,
        1624), (739, 1624), (643, 1623), (548, 1623), (452, 1623), (357, 1623), (262, 1623),
        (166, 1622), (71, 1622), (-24, 1622), (-119, 1622), (-215, 1622), (-310, 1621), (-406,
        1621), (-501, 1621), (-596, 1621), (-692, 1621), (-787, 1621), (-883, 1620), (-978,
        1620), (-1074, 1620), (-1169, 1620), (-1265, 1620), (-1270, 1702), (1316, 1707), (1311,
        1707), (1216, 1707), (1120, 1706), (1025, 1706), (930, 1706), (834, 1706), (739, 1706),
        (643, 1705), (548, 1705), (452, 1705), (357, 1705), (261, 1705), (166, 1705), (71,
        1704), (-24, 1704), (-119, 1704), (-215, 1704), (-310, 1704), (-406, 1703), (-501,
        1703), (-597, 1703), (-692, 1703), (-787, 1703), (-883, 1702), (-978, 1702), (-1074,
        1702), (-1169, 1702), (-1265, 1702), (-1270, 1784), (1316, 1789), (1311, 1789), (1216,
        1789), (1120, 1788), (1025, 1788), (930, 1788), (834, 1788), (739, 1788), (643, 1788),
        (548, 1787), (452, 1787), (357, 1787), (261, 1787), (166, 1787), (71, 1786), (-24,
        1786), (-119, 1786), (-215, 1786), (-310, 1786), (-406, 1786), (-501, 1785), (-597,
        1785), (-692, 1785), (-787, 1785), (-883, 1785), (-978, 1784), (-1074, 1784), (-1169,
        1784), (-1265, 1784)
    ]),
}


RECORDED_TARGETS_ALL = [t for v in RECORDED_SPOT_TARGETS.values() for t in v] + \
    [t for _r, v in RECORDED_SCAN_TARGETS.values() for t in v]


def _model_grid(al, rows, cols=28):
    """Every patch centre (and the 0.5 mm run-in/run-out points i1Profiler's strips use) of a
    chart of *cols* columns and rows spaced 1/rows in v, through OUR Alignment.to_table."""
    (x0, y0), (_x1, y1), (x2, _y2) = al.aims_mm
    out = []
    for r in range(rows + 1):
        for u in [c / (cols - 1) for c in range(cols)] + [-0.002, 1.002]:
            out.append(al.to_table((x0 + u * (x2 - x0), y0 + r / rows * (y1 - y0))))
    return out


def test_aims_become_targets_exactly_as_i1profiler_moved_after_its_recorded_alignments():
    """The SIGHT-to-SENSOR question, checked against the recordings: OUR fit of each recorded
    alignment (its three p1 readings used as targets with no conversion) puts every patch of
    row 1 within 1 unit (0.1 mm, integer rounding) of where i1Profiler actually moved in that
    session (ALIGNMENT.md section 4: spot targets exactly the model), and every strip row start
    and end and every fallback spot patch within 1 unit too, once the model grid carries the
    strips' run-in points 0.5 mm beyond the end patches (ALIGNMENT.md allows 5 units there). Adding the recorded
    sight-to-opening offset to the aims would miss every one by about 31 mm."""
    worst_spot = 0
    for name, recorded in RECORDED_SPOT_TARGETS.items():
        pts = geo.RECORDED_ALIGNMENTS[name]
        al = geo.fit_model(_aims_mm(pts), pts)
        (x0, y0), _bl, (x2, _y2) = al.aims_mm
        ours = [al.to_table((x0 + (x2 - x0) * (27 - k) / 27, y0)) for k in range(28)]
        for o, r in zip(ours, recorded):
            worst_spot = max(worst_spot, abs(o[0] - r[0]), abs(o[1] - r[1]))
            assert abs(o[0] - r[0]) <= 1 and abs(o[1] - r[1]) <= 1, (name, o, r)
        # the alternative frame: aims taken as where the opening stood (p1 + offset)
        off = geo.SIGHT_TO_SENSOR_SEEN[5]
        shifted = [(x + off[0], y + off[1]) for x, y in pts]
        alt = geo.fit_model(_aims_mm(shifted), shifted)
        o = alt.to_table((x2, y0))
        assert abs(o[1] - recorded[0][1]) > 300, name
    assert worst_spot <= 1
    for name, (rows, recorded) in RECORDED_SCAN_TARGETS.items():
        pts = geo.RECORDED_ALIGNMENTS[name]
        al = geo.fit_model(_aims_mm(pts), pts)
        grid = _model_grid(al, rows)
        for r in recorded:
            d = min(max(abs(g[0] - r[0]), abs(g[1] - r[1])) for g in grid)
            assert d <= 1, (name, r, d)          # ALIGNMENT.md allows 5; measured 1


def test_the_instrument_check_wants_exactly_one_i1pro_and_nothing_else():
    from workflow.i1io.table.reader import instrument_check
    table, pro = (0x0971, 0x2004), (0x0971, 0x2000)
    assert instrument_check([table, pro, (0x05AC, 0x1234)]) is None
    assert "no i1Pro 2" in instrument_check([table])
    assert "2 separate i1Pro devices" in instrument_check([table, pro, pro])
    for other in ((0x0765, 0x5020), (0x085C, 0x0500), (0x0971, 0x2007)):
        assert "another measuring instrument" in instrument_check([table, pro, other])


def test_the_reader_s_problems_are_named(tmp_path, monkeypatch):
    from workflow.i1io.table import reader as rd
    monkeypatch.setattr(rd.sys, "platform", "darwin")
    assert "missing" in " ".join(rd.helper_problems(tmp_path / "nope"))
    f = tmp_path / "chromiq-chartread"
    f.write_bytes(b"")
    f.chmod(0o644)
    assert "chmod +x" in " ".join(rd.helper_problems(f))
    monkeypatch.setattr(rd.sys, "platform", "linux")
    assert "only on a Mac" in " ".join(rd.helper_problems(f))


def test_the_reader_is_never_asked_for_a_beta_flag_or_a_memory_write():
    src = (PKG / "i1io_reader.py").read_text(encoding="utf-8")
    for flag in ("--i1pro2-lights", "--ruler", "--condition-dir", "--lights-", "eeprom",
                 "write_eeprom"):
        assert f'"{flag}' not in src
    assert src.count("subprocess.Popen(") == 1


def test_the_real_reader_wrapper_logs_no_user_path(tmp_path):
    """A stand-in helper (a tiny Python script) that echoes a path: the log keeps names only."""
    from workflow.i1io.table import reader as rd
    helper = tmp_path / "fake-helper"
    helper.write_text("#!/usr/bin/env python3\nimport json, sys, os\n"
                      "print(json.dumps({'event': 'saved', 'path': os.path.expanduser('~/x.ti3')}))\n"
                      "sys.stdout.flush()\nsys.stdin.readline()\n", encoding="utf-8")
    helper.chmod(0o755)
    logged = []
    p = rd._Proc([str(helper), "--json", "--i1io-table-scan", str(tmp_path / "out")],
                 lambda k, t: logged.append(t), tmp_path)
    ev = p.wait(("saved",), 10)
    p.stop({"cmd": "quit"})
    assert ev and ev["event"] == "saved"
    text = "\n".join(logged)
    assert str(Path.home()) not in text and str(tmp_path) not in text, text


def test_m0_at_any_other_speed_is_refused_by_the_builder_and_the_gate():
    for v in (150, 299, 301, 600, 3000):
        with pytest.raises(geo.AreaRefused):
            geo.m0_line(0, 2000, v)
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(geo._line("m0", 0, 2000, v))


def test_the_plan_check_refuses_an_unrecorded_speed_and_a_way_from_outside():
    plan = sc.plan_row("x", (-1000, 2000), (1000, 2000), 54)
    sc.check_plan(plan, at=(0, 2000))
    with pytest.raises(sc.PlanRefused):
        sc.check_plan(plan, at=(-1500, 2000))           # the way from outside the area
    with pytest.raises(sc.PlanRefused):
        sc.check_plan(sc.plan_row("x", (-1000, 2000), (1000, 2000), 200))


def test_the_simulator_refuses_a_scan_move_without_a_ready_instrument_and_without_c3(tmp_path):
    sim = csim.CSimTable(part_c=True, pos=[0.0, 2000.0], jitter=False)
    sim.instrument = None
    with pytest.raises(sim_mod.SimViolation):
        sim.receive(geo.m2_line(1000, 2000, 54))
    assert sim.violations
    sim2 = csim.CSimTable(part_c=True, pos=[0.0, 2000.0], jitter=False)
    inst = csim.FakeScanReader(sim2, str(tmp_path), lambda k, t: None,
                               faults={"restored": True})
    inst.lights_off()
    sim2.clock += 2.0
    assert inst.arm(100)["ready"] is True
    sim2.receive(geo.m2_line(1000, 2000, 54))
    sim2.receive(cl.C_FIXED["scan_a3"])
    sim2.lamp(sim2.clock)                    # no c3 yet: the move must not start
    assert not sim2.m2_pending["lamp"] and not sim2.scan_moves


def test_the_fake_spot_reader_refuses_to_read_while_the_arm_moves(tmp_path):
    sim = csim.CSimTable(part_c=True, pos=[0.0, 2000.0], jitter=False)
    sim._busy_until = sim.clock + 5.0
    r = csim.FakeSpotReader(sim, str(tmp_path), "x", [("1", "A1")], lambda k, t: None, False)
    with pytest.raises(sim_mod.SimViolation):
        r.read("A1")
    assert sim.violations


def test_geometry_first_visit_matches_the_driven_boxes():
    assert not geo.first_visit((-1000, 1600), (1000, 2500))       # inside the chart box
    assert geo.first_visit((-1000, 1200), (1000, 1200))           # behind every recorded chart
    assert geo.first_visit((1500, 2000), (1600, 2000))            # the left 45 mm


def test_the_scan_path_sets_defer_stop_only_inside_its_try_after_busy():
    """Review (2)(b): a Ctrl-C between the two lines can no longer leave defer_stop set. Since
    the dual row (2026-11-18) the one path to the fire is one function every pass goes through
    (the single row, the dual row's lamp pass and its UV pass), and run_row reaches it only."""
    import inspect
    assert "return _one_path_to_the_fire(table, inst, plan, outdir, res)" in inspect.getsource(
        sc.run_row)
    assert "return _one_path_to_the_fire(table, inst, plan, outdir, res)" in inspect.getsource(
        sc._run_uv_pass)
    src = inspect.getsource(sc._one_path_to_the_fire)
    i_busy = src.index("table.busy += 1")
    i_try = src.index("try:", i_busy)
    i_defer = src.index("table.defer_stop = True")
    assert i_busy < i_try < i_defer
    assert src.count("table.defer_stop = True") == 1


def test_the_real_reader_reports_a_fire_it_could_not_send():
    from workflow.i1io.table import reader as rd

    class Dead:
        def poll(self):
            return 1

    class P:
        p = Dead()

        def send(self, obj):
            raise rd.ReaderFailed("gone")
    r = rd.ScanReader.__new__(rd.ScanReader)
    r.proc = P()
    r.log = lambda *a: None
    r.alive = lambda: True
    assert r.fire(10, 1, "x") is False
    r.alive = lambda: False
    assert r.fire(10, 1, "x") is False


def test_the_gate_lets_a_front_target_through_only_up_to_the_confirmed_y():
    t = _T()
    t.front_y = None
    t.creep = False
    gate = cl.make_gate(t)
    t.position_now = (0, 2700)
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, A.ymax + 1))                    # nothing confirmed yet
    t.creep = True
    t.position_now = (0, A.ymax)
    assert gate(geo.m0_line(0, A.ymax + 50))[2] == "computed m0"     # one creep step
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, A.ymax + 51))                   # beyond one step
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(51, A.ymax + 10))                  # more than 5 mm sideways
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m2_line(0, A.ymax + 10, 54))               # a strip never creeps
    t.creep = False
    t.front_y = 2900
    t.position_now = (0, 2000)
    assert gate(geo.m0_line(0, 2900))[2] == "computed m0"
    assert gate(geo.m2_line(0, 2900, 54))[2] == "scan move"
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, 2901))
    t.front_y = geo.FRONT_CAP_Y + 500                        # never beyond the cap
    t.creep = True
    t.position_now = (0, geo.FRONT_CAP_Y - 10)
    with pytest.raises(geo.AreaRefused):
        geo.m0_line(0, geo.FRONT_CAP_Y + 1)
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo._line("m0", 0, geo.FRONT_CAP_Y + 1, 300))
    assert gate(geo.m0_line(0, geo.FRONT_CAP_Y))[2] == "computed m0"


def test_the_front_limits_at_their_edges():
    """Planted-fault pass of fix 2: the cap inside areas(), the 5-unit sweep slack, one creep
    step beyond the confirmed Y and no more, from a reading inside the slack."""
    for fy in (geo.FRONT_CAP_Y, geo.FRONT_CAP_Y + 1, 5000, 1e9):
        t_, s_ = geo.areas(fy)
        assert t_.ymax == geo.FRONT_CAP_Y == 3109 and s_.ymax == geo.FRONT_SWEEP_CAP_Y == 3114
    with pytest.raises(geo.AreaRefused):
        geo.check_target((0, geo.FRONT_CAP_Y + 1), "x", front_y=5000)
    t_, s_ = geo.areas(2900)
    assert (t_.ymax, s_.ymax) == (2900, 2905)
    t = _T()
    t.front_y, t.creep = 2900, False
    gate = cl.make_gate(t)
    t.position_now = (0, 2905)
    assert gate(geo.m0_line(0, 2000))[2] == "computed m0"         # a reading within the slack
    t.position_now = (0, 2906)
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, 2000))                                 # one unit beyond it
    t.creep = True
    t.position_now = (0, 2905)
    assert gate(geo.m0_line(0, 2950))[2] == "computed m0"         # one step beyond 2900
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, 2951))                                 # 46 units, but beyond 2950


def test_a_target_on_the_cap_is_allowed_once_the_creep_confirmed_it():
    """Y 3109: refused while nothing (or less) is confirmed; the creep step that reaches it is
    allowed; once confirmed, an m0 and a scan move to it pass the gate."""
    assert geo.FRONT_CAP_Y == 3109
    with pytest.raises(geo.AreaRefused, match="DZ"):
        geo.check_target((0, 3109), "x")
    with pytest.raises(geo.AreaRefused, match="DZ"):
        geo.check_target((0, 3109), "x", front_y=3108)
    geo.check_target((0, 3109), "x", front_y=3109)
    t = _T()
    gate = cl.make_gate(t)
    t.front_y, t.creep, t.position_now = 3060, True, (0, 3060)
    assert gate(geo.m0_line(0, 3109))[2] == "computed m0"          # the creep's last step
    t.front_y, t.creep, t.position_now = 3109, False, (0, 2000)
    assert gate(geo.m0_line(0, 3109))[2] == "computed m0"
    assert gate(geo.m2_line(0, 3109, 54))[2] == "scan move"
    t.position_now = (0, 3114)                                     # read within the slack
    assert gate(geo.m0_line(0, 2000))[2] == "computed m0"
    t.position_now = (0, 3115)
    with pytest.raises(tbl.ForbiddenLine):
        gate(geo.m0_line(0, 2000))
    assert csim._inside(csim.C_TARGET_BOX, (0, 3109))
    assert csim._inside(csim.C_SWEEP_BOX, (0, 3114))
    assert not csim._inside(csim.C_SWEEP_BOX, (0, 3115))


@pytest.mark.parametrize("front_y", [None, 2723, 3060, 3109, 3110, 3159, 5000, float("inf"),
                                     float("nan"), 1e9])
@pytest.mark.parametrize("creep", [False, True])
def test_y_3110_is_refused_always(front_y, creep):
    """One unit beyond the cap: refused by both builders, by classify, by the gate with every
    confirmed Y and with the creep on or off, by check_target, and by the simulator's box."""
    for build in (lambda: geo.m0_line(0, 3110), lambda: geo.m2_line(0, 3110, 54)):
        with pytest.raises(geo.AreaRefused):
            build()
    raw_m0, raw_m2 = geo._line("m0", 0, 3110, 300), geo._line("m2", 0, 3110, 54)
    for raw in (raw_m0, raw_m2):
        with pytest.raises(tbl.ForbiddenLine):
            cl.classify(raw)
        with pytest.raises(tbl.ForbiddenLine):
            cl.wire_gate(raw)
    with pytest.raises(geo.AreaRefused):
        geo.check_target((0, 3110), "x", front_y=front_y)
    t = _T()
    t.front_y, t.creep, t.position_now = front_y, creep, (0, 3080)
    gate = cl.make_gate(t)
    for raw in (raw_m0, raw_m2):
        with pytest.raises(tbl.ForbiddenLine):
            gate(raw)
    assert geo.areas(front_y)[0].ymax <= 3109 and geo.areas(front_y)[1].ymax <= 3114
    assert not csim._inside(csim.C_TARGET_BOX, (0, 3110))


def test_the_gate_s_own_creep_limit_stops_at_the_cap_without_classify(monkeypatch):
    """Planted-fault pass of fix 3: the gate's creep limit is a second line behind classify's cap;
    with classify made permissive, the gate alone still refuses a creep step to Y 3110."""
    t = _T()
    t.front_y, t.creep, t.position_now = 3100, True, (0, 3100)
    monkeypatch.setattr(cl, "classify", lambda line: (line[1:3].decode(), True, "computed m0"))
    gate = cl.make_gate(t)
    assert gate(geo._line("m0", 0, 3109, 300))[2] == "computed m0"
    for y in (3110, 3114):
        with pytest.raises(tbl.ForbiddenLine):
            gate(geo._line("m0", 0, y, 300))

