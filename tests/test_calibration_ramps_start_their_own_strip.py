"""Each ink's calibration ramp starts its own strip (#182, Knut 5965186237).

``targen -s N`` (the calibration knobs: -f0 -e0 -B0) writes one shared white
and then each channel's N-1 steps, channel after channel. Laid out in that
order the ramps ran across the strips: on Knut's 20-per-strip chart the last
patch of the magenta strip was the first yellow step, and the yellow strip
ended on two fill-up whites. Approved (Q3 "yes" to 5964724199): every ramp
starts a strip of its own with its own paper white, a ramp longer than a strip
carries on to the next one, the next ramp still starts a fresh strip, and the
rest of a ramp's last strip is paper white. printcal averages all whites.

Pinned here:

* the arrangement for RGB, CMYK and N-colour at every strip length, from the
  pure function down to the .ti2 the engine writes;
* nothing that is not targen's pure ramp set is ever rearranged (a profiling
  chart, a user's set, a calibration chart with -e/-B/-g under the override);
* the .ti1 rewrite keeps targen's extra tables and the header;
* the engine path and the printtarg path both arrange, and only for
  ``cal_target``;
* printcal makes the same .cal from the new layout as from the old one when
  the sheet carries as many whites, and the difference that remains when it
  carries more is the whites' weight alone (real Argyll, fakeread + printcal);
* the estimate counts what the build lays out;
* the calibration chart is never auto-tagged RANDOM_START (review 2026-10-03:
  the CMYK chart passed the randomisation gate) and is never bound as a given
  patch set.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.argyll_env import argyll_ref_dir, argyll_tool  # noqa: E402
from workflow.layout_engine import calibration_ramps as cr  # noqa: E402

_NAMES = {3: ["RGB_R", "RGB_G", "RGB_B"],
          4: ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"],
          6: ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K", "CMYK_O", "CMYK_G"]}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _targen_rows(channels: int, steps: int, additive: bool):
    """Device rows exactly as targen -s writes them: one white, then each
    channel's N-1 steps, channel after channel."""
    w = 100.0 if additive else 0.0
    rows = [tuple([w] * channels)]
    for ch in range(channels):
        for k in range(1, steps):
            v = 100.0 * k / (steps - 1)
            r = [w] * channels
            r[ch] = (100.0 - v) if additive else v
            rows.append(tuple(r))
    return rows


def _ti1_text(rows, additive: bool, extra_table: bool = True) -> str:
    n = len(rows[0])
    names = _NAMES[n] if n in _NAMES else [f"CMYK_{i}" for i in range(n)]
    rep = "iRGB" if additive else ("CMYK" if n == 4 else "CMYKOG")
    data = "\n".join(
        f"{i} " + " ".join(f"{v:.5f}" for v in r)
        + " " + " ".join(f"{(r[0] if additive else 100 - r[0]):.4f}" for _ in range(3)) + " "
        for i, r in enumerate(rows, 1))
    text = (
        'CTI1   \n\nDESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        f'ORIGINATOR "Argyll targen"\n'
        'APPROX_WHITE_POINT "95.106486 100.000000 108.844025"\n'
        f'COLOR_REP "{rep}"\n'
        f'SINGLE_DIM_STEPS "{(len(rows) - 1) // n + 1}"\n\n'
        f"NUMBER_OF_FIELDS {1 + n + 3}\nBEGIN_DATA_FORMAT\n"
        f"SAMPLE_ID {' '.join(names)} XYZ_X XYZ_Y XYZ_Z \nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n{data}\nEND_DATA\n")
    if extra_table:
        text += (
            'CTI1   \n\nDESCRIPTOR "Argyll Calibration Target chart information 1"\n'
            'ORIGINATOR "Argyll targen"\nDENSITY_EXTREME_VALUES "2"\n\n'
            f"NUMBER_OF_FIELDS {1 + n + 3}\nBEGIN_DATA_FORMAT\n"
            f"INDEX {' '.join(names)} XYZ_X XYZ_Y XYZ_Z \nEND_DATA_FORMAT\n\n"
            "NUMBER_OF_SETS 2\nBEGIN_DATA\n"
            f"0 {' '.join(['0.00000'] * n)} 1.0 1.0 1.0 \n"
            f"1 {' '.join(['100.0000'] * n)} 2.0 2.0 2.0 \nEND_DATA\n")
    return text


def _kind(row, additive: bool):
    """'W' for paper white, else the index of the one channel that is inked."""
    w = 100.0 if additive else 0.0
    d = [c for c, v in enumerate(row) if abs(v - w) > 1e-4]
    return "W" if not d else d[0]


def _check_arrangement(seq, channels: int, steps: int, sip: int):
    """*seq* is the sheet's patches in location order ('W' or a channel)."""
    starts = []
    for ch in range(channels):
        first = seq.index(ch)
        # its own white right before its first step, at a strip start
        assert seq[first - 1] == "W", f"channel {ch}: no white before its ramp"
        assert (first - 1) % sip == 0, (
            f"channel {ch}'s ramp starts mid-strip ({first - 1} % {sip})")
        last = len(seq) - 1 - seq[::-1].index(ch)
        assert last - first + 1 == steps - 1, f"channel {ch} is split"
        assert all(x == ch for x in seq[first:last + 1]), (
            f"something sits inside channel {ch}'s ramp")
        starts.append(first - 1)
    assert starts == sorted(starts)
    # everything that is not a step is paper white
    assert seq.count("W") == len(seq) - channels * (steps - 1)


# ---------------------------------------------------------------------------
# the arrangement itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("channels,additive", [(3, True), (4, False),
                                               (6, False)])
@pytest.mark.parametrize("steps", [5, 20, 27])
@pytest.mark.parametrize("sip", [1, 7, 14, 20, 21, 27, 60])
def test_every_ramp_starts_its_own_strip(channels, additive, steps, sip):
    rows = _targen_rows(channels, steps, additive)
    ramps = cr.find_ramps(rows)
    assert ramps is not None and ramps.is_targen_order
    assert len(ramps.ramps) == channels
    order = cr.arranged_order(ramps, sip)
    seq = [_kind(rows[i], additive) for i in order]
    # the layout pads the LAST strip with paper white, as it always has
    pad = (-len(seq)) % sip
    seq += ["W"] * pad
    _check_arrangement(seq, channels, steps, sip)
    assert len(order) == cr.arranged_count([steps - 1] * channels, sip)
    # every ramp but the last fills whole strips
    for k in range(channels - 1):
        assert seq.index(k + 1) - 1 == (k + 1) * (
            (steps + sip - 1) // sip) * sip


def test_knuts_case_costs_no_extra_patch():
    """20 steps, 20 per strip: three strips of 20, as before, and no fill-up
    splitting a ramp. Each strip is its white and its 19 steps."""
    rows = _targen_rows(3, 20, True)
    order = cr.arranged_order(cr.find_ramps(rows), 20)
    assert len(order) == 60
    seq = [_kind(rows[i], True) for i in order]
    assert seq == (["W"] + [0] * 19) + (["W"] + [1] * 19) + (["W"] + [2] * 19)
    rows = _targen_rows(3, 27, True)
    assert len(cr.arranged_order(cr.find_ramps(rows), 27)) == 81
    rows = _targen_rows(4, 20, False)
    assert len(cr.arranged_order(cr.find_ramps(rows), 20)) == 80


@pytest.mark.parametrize("bad", [
    "black", "grey", "two_inks", "comes_back", "first_not_white",
    "single_row", "half_white"])
def test_anything_but_a_pure_ramp_set_is_left_alone(bad):
    rows = _targen_rows(3, 6, True)
    if bad == "black":
        rows.append((0.0, 0.0, 0.0))
    elif bad == "grey":
        rows.append((50.0, 50.0, 50.0))
    elif bad == "two_inks":
        rows.insert(3, (50.0, 50.0, 100.0))
    elif bad == "comes_back":
        rows.append((10.0, 100.0, 100.0))
    elif bad == "first_not_white":
        rows = rows[1:] + rows[:1]
    elif bad == "single_row":
        rows = rows[:1]
    elif bad == "half_white":
        rows[0] = (50.0, 50.0, 50.0)
    assert cr.find_ramps(rows) is None


def test_extra_whites_are_a_ramp_set_but_never_rearranged():
    """targen with -e under the override writes more whites: still ramps (so
    the auto-tagger leaves it in order), but not targen's -s shape, so the
    layout keeps every row as it is rather than dropping a white."""
    rows = _targen_rows(3, 6, True)
    rows.insert(4, rows[0])
    ramps = cr.find_ramps(rows)
    assert ramps is not None and not ramps.is_targen_order
    assert cr.arranged_order(ramps, 6) is None


def test_a_profiling_chart_is_not_a_ramp_set():
    import random
    rng = random.Random(3)
    rows = [(100.0, 100.0, 100.0)] + [
        tuple(round(rng.uniform(0, 100), 4) for _ in range(3))
        for _ in range(200)]
    assert cr.find_ramps(rows) is None


def test_settle_finds_a_count_and_strip_length_that_agree():
    # strip length that shrinks as the count grows (area-first)
    def steps_for(n):
        return 20 if n <= 60 else 18

    def count_for(s):
        return cr.arranged_count([19, 19, 19], s)

    n, s = cr.settle(count_for, steps_for, 58)
    assert (n, s) == (60, 20)
    n, s = cr.settle(lambda s: cr.arranged_count([19] * 4, s), steps_for, 77)
    assert steps_for(n) == s        # a consistent pair


def test_settle_never_hands_back_a_pair_the_layout_disagrees_with():
    """Review of 7386afd8: area-first can make the strip length and the
    count chase each other for ever (count 74 wants strips of 10, strips of
    10 make a count that wants 9, and back). The last pair asked was used,
    the ramps were arranged for 9 and the sheet laid out on 10. A pair is
    only returned when the layout of that count really has that strip
    length, padding the LAST strip with paper white if that is what it
    takes; otherwise None, and targen's order is kept."""
    lens = [19, 19, 19]

    def flip(n):                 # no fixed point at all
        return 9 if n >= 70 else 10

    got = cr.settle(lambda s: cr.arranged_count(lens, s), flip, 58)
    assert got is None or flip(got[0]) == got[1]

    def wants_full_strips(n):    # agrees only once the last strip is full
        return 10 if n % 10 == 0 else 9

    got = cr.settle(lambda s: cr.arranged_count(lens, s), wants_full_strips,
                    58)
    assert got is not None and wants_full_strips(got[0]) == got[1]
    n, sip = got
    base = cr.arranged_count(lens, sip)
    assert base <= n < -(-base // sip) * sip + 1   # never past that strip
    rows = _targen_rows(3, 20, True)
    order = cr.arranged_order(cr.find_ramps(rows), sip, n)
    assert len(order) == n
    _check_arrangement([_kind(rows[i], True) for i in order], 3, 20, sip)


def _by_width_kwargs(instrument="i1", paper="A4", ratio=1.0) -> dict:
    """The Create Chart panel as it opens: area-first, by patch width, 100 %,
    minimum width auto."""
    from workflow.layout_engine.presets import LayoutRecipe
    kw = LayoutRecipe(instrument=instrument, paper=paper,
                      area_ratio=ratio).build_kwargs()
    kw.update(instrument=instrument, paper=paper, dpi=36, randomize=False)
    return kw


@pytest.mark.parametrize("channels,additive,steps,instrument,paper", [
    (3, True, 20, "i1", "A4"),       # the calibration default, as it opens
    (3, True, 21, "i1", "A4"),
    (3, True, 27, "i1", "A4"),
    (3, True, 20, "p3", "A4"),
    (3, True, 5, "i1", "Letter"),
    (4, False, 11, "i1", "A4"),
    (4, False, 27, "i1", "A4"),
    (4, False, 33, "i1", "A4"),
    (4, False, 27, "i1", "Letter"),
    (4, False, 11, "p3", "A4")])
def test_area_first_by_width_lays_each_ramp_on_its_own_strip(
        tmp_path, channels, additive, steps, instrument, paper):
    """Every one of these came out with the ramps arranged for one strip
    length and laid out on another (G started 8 patches down strip C on the
    default i1Pro A4 chart, driven on screen 2026-10-03), and the log said
    each ramp started its own strip. Now the ramps either really do start
    their strips, or, where no strip length agrees with the count it lays
    out, the chart is targen's own, exactly as before the change."""
    from workflow.layout_engine import chart
    ti1 = tmp_path / "Test-cal.ti1"
    ti1.write_text(_ti1_text(_targen_rows(channels, steps, additive),
                             additive), encoding="latin-1")
    before = ti1.read_bytes()
    res = chart.build_chart(ti1, tmp_path / "Test-cal", ramps_per_strip=True,
                            **_by_width_kwargs(instrument, paper))
    sip, seq, _text = _ti2_sequence(tmp_path / "Test-cal.ti2", additive)
    if res.ramp_whites_added:
        _check_arrangement(seq, channels, steps, sip)
    else:
        assert ti1.read_bytes() == before
        n = channels * (steps - 1) + 1
        assert seq[:n] == ["W"] + [ch for ch in range(channels)
                                   for _ in range(steps - 1)]
        assert set(seq[n:]) <= {"W"}


# ---------------------------------------------------------------------------
# the .ti1 rewrite
# ---------------------------------------------------------------------------

def test_the_ti1_rewrite_keeps_everything_but_the_order(tmp_path):
    rows = _targen_rows(3, 20, True)
    text = _ti1_text(rows, True)
    p = tmp_path / "Test-cal.ti1"
    p.write_text(text, encoding="latin-1")
    assert cr.arrange_ti1(p, 20) == 60
    new = p.read_text(encoding="latin-1")
    # header and the second table byte for byte
    head_old = text.split("NUMBER_OF_SETS", 1)[0]
    assert new.startswith(head_old)
    tail_old = text.split("END_DATA\n", 1)[1]
    assert new.split("END_DATA\n", 1)[1] == tail_old
    assert 'SINGLE_DIM_STEPS "20"' in new
    sets = re.findall(r"^NUMBER_OF_SETS\s+(\d+)", new, re.M)
    assert sets == ["60", "2"]
    from workflow.layout_engine import ti1_reader
    t = ti1_reader.read_ti1(p)
    assert len(t.patches) == 60
    body = new.split("BEGIN_DATA\n", 1)[1].split("END_DATA", 1)[0]
    ids = [int(ln.split()[0]) for ln in body.splitlines() if ln.strip()]
    assert ids == list(range(1, 61))
    seq = [_kind(d, True) for d, _xyz in t.patches]
    _check_arrangement(seq, 3, 20, 20)


def test_a_file_that_is_not_ramps_is_not_touched(tmp_path):
    rows = _targen_rows(3, 6, True) + [(0.0, 0.0, 0.0)]
    p = tmp_path / "x.ti1"
    p.write_text(_ti1_text(rows, True), encoding="latin-1")
    before = p.read_bytes()
    assert cr.arrange_ti1(p, 6) is None
    assert p.read_bytes() == before


# ---------------------------------------------------------------------------
# the engine
# ---------------------------------------------------------------------------

def _grid_kwargs(sip: int) -> dict:
    from workflow.layout_engine.presets import LayoutRecipe
    kw = LayoutRecipe(instrument="i1", paper="A4", randomize=False,
                      layout_mode="area_first", area_method="by_grid",
                      area_cols=15, area_rows=sip).build_kwargs()
    kw.update(dpi=36, randomize=False)
    return kw


def _ti2_sequence(ti2: Path, additive: bool):
    text = ti2.read_text(encoding="latin-1")
    sip = int(re.search(r'STEPS_IN_PASS\s+"?(\d+)', text).group(1))
    fmt = re.search(r"BEGIN_DATA_FORMAT\s*(.*?)END_DATA_FORMAT", text,
                    re.S).group(1).split()
    body = re.search(r"^BEGIN_DATA\s*$(.*?)^END_DATA", text,
                     re.S | re.M).group(1)
    dev = [i for i, f in enumerate(fmt) if f.startswith(("RGB_", "CMYK_"))]
    rows = [ln.split() for ln in body.splitlines() if ln.strip()]
    return sip, [_kind(tuple(float(r[i]) for i in dev), additive)
                 for r in rows], text


@pytest.mark.parametrize("channels,additive,steps,sip", [
    (3, True, 20, 20), (3, True, 27, 27), (3, True, 20, 14),
    (3, True, 20, 27), (4, False, 20, 20), (4, False, 20, 14),
    (4, False, 27, 27)])
def test_the_engine_lays_each_ramp_on_its_own_strip(tmp_path, channels,
                                                    additive, steps, sip):
    from workflow.layout_engine import chart
    ti1 = tmp_path / "Test-cal.ti1"
    ti1.write_text(_ti1_text(_targen_rows(channels, steps, additive),
                             additive), encoding="latin-1")
    res = chart.build_chart(ti1, tmp_path / "Test-cal", ramps_per_strip=True,
                            **_grid_kwargs(sip))
    got_sip, seq, text = _ti2_sequence(tmp_path / "Test-cal.ti2", additive)
    assert got_sip == sip
    assert "CHART_ID" in text and "RANDOM_START" not in text
    _check_arrangement(seq, channels, steps, sip)
    assert len(seq) % sip == 0
    assert res.ramp_whites_added == cr.arranged_count(
        [steps - 1] * channels, sip) - (channels * (steps - 1) + 1)
    if steps == sip:
        assert res.layout.padding == 0 and len(seq) == channels * steps


def test_without_the_flag_the_engine_keeps_targens_order(tmp_path):
    from workflow.layout_engine import chart
    ti1 = tmp_path / "Test-cal.ti1"
    ti1.write_text(_ti1_text(_targen_rows(3, 20, True), True),
                   encoding="latin-1")
    before = ti1.read_bytes()
    res = chart.build_chart(ti1, tmp_path / "Test-cal", **_grid_kwargs(20))
    assert ti1.read_bytes() == before
    assert res.ramp_whites_added == 0
    _sip, seq, _t = _ti2_sequence(tmp_path / "Test-cal.ti2", True)
    assert seq[39] == 2            # the first blue step ends strip B
    assert seq[-2:] == ["W", "W"]  # and the fill-up ends strip C


def test_a_profiling_ti1_is_never_rearranged_even_if_asked(tmp_path):
    import random
    from workflow.layout_engine import chart
    rng = random.Random(1)
    rows = [(100.0, 100.0, 100.0)] + [
        tuple(round(rng.uniform(0, 100), 3) for _ in range(3))
        for _ in range(57)]
    ti1 = tmp_path / "Prof.ti1"
    ti1.write_text(_ti1_text(rows, True), encoding="latin-1")
    before = ti1.read_bytes()
    res = chart.build_chart(ti1, tmp_path / "Prof", ramps_per_strip=True,
                            **_grid_kwargs(20))
    assert ti1.read_bytes() == before
    assert res.ramp_whites_added == 0
    assert res.layout.total_patches == 60


# ---------------------------------------------------------------------------
# ChartCreator: only a calibration build asks for it
# ---------------------------------------------------------------------------

class _FM:
    def __init__(self, root):
        self.root = root

    @staticmethod
    def chart_stem(cal_target=False):
        return "Test-cal" if cal_target else "Test"


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


@pytest.mark.parametrize("cal_target", [True, False])
def test_the_engine_build_asks_for_ramps_only_in_calibration(
        tmp_path, monkeypatch, cal_target):
    from workflow import chart_creator as cc
    from workflow.layout_engine import chart as le_chart
    seen = {}

    def _fake(ti1, out, **kw):
        seen.update(kw)
        raise RuntimeError("stop here")

    monkeypatch.setattr(le_chart, "build_chart", _fake)
    creator = cc.ChartCreator(object(), _FM(tmp_path), _Settings())
    creator._pending_on_finish = lambda tiffs: None
    lines = []
    creator._run_engine(cc.ChartParams(instrument="i1", paper="A4",
                                       cal_target=cal_target),
                        tmp_path, lines.append)
    assert seen["ramps_per_strip"] is cal_target


def test_the_log_line_names_the_added_whites():
    from workflow.chart_creator import _ramp_whites_log_line
    assert _ramp_whites_log_line(0) == ""
    one = _ramp_whites_log_line(1)
    assert "1 paper-white patch" in one and one.startswith(
        "[ChromIQ layout engine] ")
    assert "18 paper-white patches" in _ramp_whites_log_line(18, "[printtarg]")
    assert "—" not in one


# ---------------------------------------------------------------------------
# the printtarg path (engine off): asked for its strip length, then run again
# ---------------------------------------------------------------------------

_live = pytest.mark.skipif(
    not (argyll_tool("targen") and argyll_tool("printtarg")),
    reason="ArgyllCMS not installed")


def _argyll(tool, args, cwd):
    r = subprocess.run([argyll_tool(tool), *args], cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=180,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 0, f"{tool} {args} did not finish cleanly:\n" \
                              f"{r.stdout}\n{r.stderr}"


@_live
def test_argyll_reads_targens_own_file_after_the_rewrite(tmp_path):
    """The real thing: targen's .ti1, with its DENSITY_EXTREME_VALUES and
    DEVICE_COMBINATION_VALUES tables, rearranged and then read by printtarg."""
    _argyll("targen", ["-d2", "-f0", "-e0", "-B0", "-s20", "cal"], tmp_path)
    p = tmp_path / "cal.ti1"
    text = p.read_text(encoding="latin-1")
    assert cr.arrange_ti1(p, 20) == 60
    new = p.read_text(encoding="latin-1")
    assert new.split("END_DATA\n", 1)[1] == text.split("END_DATA\n", 1)[1]
    _argyll("printtarg", ["-ii1", "-pA4", "-r", "-T100", "cal"], tmp_path)
    m = re.search(r"^NUMBER_OF_SETS\s+(\d+)", (tmp_path / "cal.ti2").read_text(
        encoding="latin-1"), re.M)
    assert int(m.group(1)) >= 60   # its own fill-up on top of the 60


@_live
@pytest.mark.parametrize("d,channels,additive", [(2, 3, True), (4, 4, False)])
def test_printtarg_lays_each_ramp_on_its_own_strip(tmp_path, d, channels,
                                                   additive):
    from workflow.chart_creator import ChartCreator
    _argyll("targen", [f"-d{d}", "-f0", "-e0", "-B0", "-s20", "cal"], tmp_path)
    _argyll("printtarg", ["-ii1", "-pA4", "-r", "-T100", "cal"], tmp_path)
    added = ChartCreator._arrange_ramps_for_printtarg(tmp_path, "cal")
    assert added > 0
    _argyll("printtarg", ["-ii1", "-pA4", "-r", "-T100", "cal"], tmp_path)
    sip, seq, _t = _ti2_sequence(tmp_path / "cal.ti2", additive)
    _check_arrangement(seq, channels, 20, sip)
    # asked again, nothing more to do
    assert ChartCreator._arrange_ramps_for_printtarg(tmp_path, "cal") == 0


# ---------------------------------------------------------------------------
# printcal accepts it, and makes the same calibration
# ---------------------------------------------------------------------------

_pc_live = pytest.mark.skipif(
    not (argyll_tool("targen") and argyll_tool("fakeread")
         and argyll_tool("printcal") and argyll_ref_dir()
         and (argyll_ref_dir() / "sRGB.icm").is_file()
         and (argyll_ref_dir() / "cmyk.icm").is_file()),
    reason="ArgyllCMS (with its ref profiles) not installed")


def _measure(folder: Path, seq_rows, d: int, profile: Path):
    """What chartread hands printcal: one .ti3 row per patch on the SHEET,
    fill-up included, simulated with fakeread (which reads a .ti1)."""
    folder.mkdir()
    n = len(seq_rows[0])
    names = _NAMES[n]
    rows = "\n".join(f"{i} " + " ".join(f"{v:.5f}" for v in r)
                     for i, r in enumerate(seq_rows, 1))
    (folder / "meas.ti1").write_text(
        'CTI1\n\nDESCRIPTOR "t"\nORIGINATOR "Argyll targen"\n'
        f'COLOR_REP "{"iRGB" if d == 2 else "CMYK"}"\n\n'
        f"NUMBER_OF_FIELDS {1 + n}\nBEGIN_DATA_FORMAT\n"
        f"SAMPLE_ID {' '.join(names)}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(seq_rows)}\nBEGIN_DATA\n{rows}\nEND_DATA\n",
        encoding="latin-1")
    _argyll("fakeread", [str(profile), "meas"], folder)
    _argyll("printcal", ["-i", "meas"], folder)
    text = (folder / "meas.cal").read_text(encoding="latin-1")
    body = re.search(r"^BEGIN_DATA\s*$(.*?)^END_DATA", text,
                     re.S | re.M).group(1)
    return [[float(t) for t in ln.split()] for ln in body.splitlines()
            if ln.strip()]


def _sheet_rows(ti2: Path):
    text = ti2.read_text(encoding="latin-1")
    fmt = re.search(r"BEGIN_DATA_FORMAT\s*(.*?)END_DATA_FORMAT", text,
                    re.S).group(1).split()
    body = re.search(r"^BEGIN_DATA\s*$(.*?)^END_DATA", text,
                     re.S | re.M).group(1)
    dev = [i for i, f in enumerate(fmt) if f.startswith(("RGB_", "CMYK_"))]
    return [tuple(float(ln.split()[i]) for i in dev)
            for ln in body.splitlines() if ln.strip()]


@_pc_live
@pytest.mark.parametrize("d,steps,sip", [(2, 20, 20), (2, 27, 27),
                                         (2, 20, 14), (4, 20, 20),
                                         (4, 20, 14)])
def test_printcal_makes_the_same_calibration(tmp_path, d, steps, sip):
    from workflow.layout_engine import chart
    profile = argyll_ref_dir() / ("sRGB.icm" if d == 2 else "cmyk.icm")
    _argyll("targen", [f"-d{d}", "-f0", "-e0", "-B0", f"-s{steps}", "cal"],
            tmp_path)
    cals, sheets = {}, {}
    for tag, ramps in (("today", False), ("ramps", True)):
        sub = tmp_path / tag
        sub.mkdir()
        shutil.copy(tmp_path / "cal.ti1", sub / "cal.ti1")
        chart.build_chart(sub / "cal.ti1", sub / "cal", ramps_per_strip=ramps,
                          **_grid_kwargs(sip))
        sheets[tag] = _sheet_rows(sub / "cal.ti2")
        cals[tag] = _measure(sub / "m", sheets[tag], d, profile)
    a, b = cals["today"], cals["ramps"]
    assert len(a) == len(b) and len(a[0]) == len(b[0])
    diff = max(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra, rb))
    white = 100.0 if d == 2 else 0.0
    is_w = lambda r: all(abs(v - white) < 1e-4 for v in r)  # noqa: E731
    extra = (sum(map(is_w, sheets["ramps"]))
             - sum(map(is_w, sheets["today"])))
    if extra == 0:
        # the same patches in another order: the very same calibration
        assert diff == 0.0
    else:
        # more whites only re-weight the white point (printcal.c 1487)
        assert diff < 0.002, diff
        ctrl = _measure(tmp_path / "control",
                        sheets["today"] + [sheets["today"][0]] * extra,
                        d, profile)
        assert ctrl == b, "printcal is not order-blind after all"


# ---------------------------------------------------------------------------
# the Create Chart tab
# ---------------------------------------------------------------------------

def _stand_in(in_cal: bool, steps=20, e=0, B=0, g=0, f=0):
    from ui.tabs.tab_chart import TabChart
    p = SimpleNamespace(single_channel_steps=steps, white_patches=e,
                        black_patches=B, grey_steps=g, patches=f)
    s = SimpleNamespace(_calibration_selected=lambda: in_cal,
                        _collect_manual=lambda: p)
    return lambda n, kw: TabChart._calibration_ramp_total(s, n, kw)


@pytest.mark.parametrize("steps,sip,want", [(20, 20, 60), (27, 27, 81),
                                            (20, 14, 76)])
def test_the_estimate_counts_what_the_build_lays_out(steps, sip, want):
    """The count handed to the estimate is the .ti1's after the ramps are
    arranged; the layout then fills the last strip as it does for the build
    (20 steps on 14-patch strips: 76 here, 84 on the sheet)."""
    kw = _grid_kwargs(sip)
    count = _stand_in(True, steps=steps)
    assert count(3 * (steps - 1) + 1, kw) == want
    # CMYK: 4 ramps
    assert count(4 * (steps - 1) + 1, kw) == cr.arranged_count(
        [steps - 1] * 4, sip)


def test_the_estimate_is_unchanged_outside_a_pure_calibration():
    kw = _grid_kwargs(20)
    assert _stand_in(False)(58, kw) == 58
    assert _stand_in(True, e=4)(58, kw) == 58
    assert _stand_in(True, B=1)(58, kw) == 58
    assert _stand_in(True, g=5)(58, kw) == 58
    assert _stand_in(True, steps=0)(58, kw) == 58
    assert _stand_in(True)(57, kw) == 57     # not 1 + C*(N-1)


def test_one_white_patch_is_targens_own_white_and_counted(tmp_path):
    """targen -e 1 makes the very chart -e 0 does (one white, the ramps'
    own), so the build arranges it; the estimate has to count it too."""
    targen = argyll_tool("targen")
    if not targen:
        pytest.skip("ArgyllCMS not installed")
    for e in (0, 1):
        subprocess.run([targen, "-v0", "-d2", "-s20", "-f0", f"-e{e}",
                        "-B0", "-g0", str(tmp_path / f"e{e}")], check=True,
                       timeout=60, capture_output=True)
        assert cr.ramps_in_ti1(tmp_path / f"e{e}.ti1").is_targen_order
    kw = _grid_kwargs(20)
    assert _stand_in(True, e=1)(58, kw) == _stand_in(True, e=0)(58, kw) == 60


def _cmyk_ramp_chart(folder: Path, sip: int = 20):
    from workflow.layout_engine import chart
    ti1 = folder / "Test-cal.ti1"
    ti1.write_text(_ti1_text(_targen_rows(4, 20, False), False),
                   encoding="latin-1")
    chart.build_chart(ti1, folder / "Test-cal", ramps_per_strip=True,
                      **_grid_kwargs(sip))
    return folder / "Test-cal.ti2"


def test_the_cmyk_calibration_chart_passes_the_gate_it_must_not_meet(
        tmp_path):
    """Why the auto-tagger needed a rule of its own: four inks' ramps are
    easy to tell apart, so the randomisation gate calls the chart safe."""
    from workflow.ti2_relayout import analyze_randomisation
    assert analyze_randomisation(_cmyk_ramp_chart(tmp_path)).safe


@pytest.mark.parametrize("in_cal", [True, False])
def test_a_calibration_chart_is_never_tagged_random(tmp_path, in_cal):
    from ui.tabs.tab_chart import TabChart
    ti2 = _cmyk_ramp_chart(tmp_path)
    before = ti2.read_bytes()
    s = SimpleNamespace(_calibration_selected=lambda: in_cal)
    TabChart._maybe_autotag_randomised(s, ti2)
    assert ti2.read_bytes() == before
    assert "RANDOM_START" not in ti2.read_text(encoding="latin-1")


def test_a_well_mixed_profiling_chart_is_still_tagged(tmp_path):
    """The rule is narrow: a shuffled fixed-order profiling chart is still
    upgraded, as `test_chart_autotag_randomised` pins for the real tab."""
    import random
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine import chart
    rng = random.Random(0)
    rows = [(100.0, 100.0, 100.0)] + [
        tuple(round(rng.uniform(0, 100), 3) for _ in range(3))
        for _ in range(199)]
    ti1 = tmp_path / "P.ti1"
    ti1.write_text(_ti1_text(rows, True), encoding="latin-1")
    chart.build_chart(ti1, tmp_path / "P", **_grid_kwargs(20))
    s = SimpleNamespace(_calibration_selected=lambda: False)
    TabChart._maybe_autotag_randomised(s, tmp_path / "P.ti2")
    assert "RANDOM_START" in (tmp_path / "P.ti2").read_text(
        encoding="latin-1")


def test_the_arranged_calibration_chart_is_not_bound(qapp, tmp_path):
    """The rewritten .ti1 is no longer what targen wrote, so the B8-1460
    "does targen make these patches?" question would say no and bind it as a
    given set. It is never asked: the chart records patch_set_given false,
    and in Calibration nothing is bound at all."""
    from core.measurement_target import RUN_TYPE_CALIBRATION
    from tests._cal_target_fixture import (bound, make_window,
                                           override_row_shown,
                                           targen_panel_enabled)
    from workflow.chart_creator import ChartCreator, ChartParams
    w = make_window(qapp, tmp_path)
    try:
        tc = w._tab_chart
        proj = w._file_mgr.project()
        cal = proj.calibration
        d = cal.ensure_dir() if hasattr(cal, "ensure_dir") else cal.dir
        Path(d).mkdir(parents=True, exist_ok=True)
        ti1 = Path(d) / f"{cal.stem}.ti1"
        ti1.write_text(_ti1_text(_targen_rows(3, 20, True), True),
                       encoding="latin-1")
        assert cr.arrange_ti1(ti1, 20) == 60
        # the sidecar a calibration build writes
        creator = ChartCreator(object(), _FM(tmp_path), _Settings())
        creator._write_channel_sidecar(Path(d), cal.stem,
                                       ChartParams(cal_target=True),
                                       engine="chromiq")
        import json
        side = json.loads((Path(d) / f"{cal.stem}.channels.json").read_text(
            encoding="utf-8"))
        assert side["patch_set_given"] is False
        for run_type_cal in (False, True):
            if run_type_cal:
                w._target_ctl.set_run_type(RUN_TYPE_CALIBRATION)
                qapp.processEvents()
            asked = []
            tc._ask_patch_set_origin = lambda t: asked.append(t)
            tc._rebind_patch_set_from_run(ti1, given=False)
            qapp.processEvents()
            assert not asked, "the older-chart question was put"
            assert not bound(tc)
            if run_type_cal:
                assert not override_row_shown(tc)
                assert targen_panel_enabled(tc)
    finally:
        w.close()
