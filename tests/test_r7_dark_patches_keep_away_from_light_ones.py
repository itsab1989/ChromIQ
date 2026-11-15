"""R7 (4.3.39): on a chart in FIXED order the layout engine keeps very dark
patches away from very light ones along a strip.

jctay (forum 150236): strip 12 of his fixed-order chart, a grey ramp up to
94 % and then 7/7/8 % near-blacks, was refused 15 times of 15 with "Reading is
inconsistent": the near-black patch read straight after the almost white one
caught light from it. The engine now swaps the fewest patches needed
(`workflow/layout_engine/neighbour_order.py`), through its one slot list, so
the .ti2 and the pages agree. Proved here:

* the tester's strip is cleared, deterministically, the patch set unchanged;
* a chart without such neighbours, a randomised chart and the option off are
  written byte for byte as before; padding and calibration charts never move;
* the .ti2's locations and the drawn pages say the same thing;
* a recipe made from 4.3.39 on has it on, one saved before reads it off (and
  lays out as it did); the Create Chart option is greyed while "Randomise
  patch order" is on, and nothing else.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from workflow.layout_engine import neighbour_order as N

REPO = Path(__file__).resolve().parents[1]


def _grey(v):
    c = v / 100.0
    y = 100 * (c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (0.9505 * y, y, 1.089 * y)


def _testers_strip():
    return [_grey(v) for v in (50, 56, 62, 69, 75, 81, 87, 94)] + \
        [_grey(7), _grey(7), _grey(8), _grey(14)]


def _mid():
    return [_grey(v) for v in (30, 35, 40, 45, 50, 55, 60, 65, 70, 72, 74, 76)]


def test_the_thresholds_hold_the_testers_pair_with_a_margin():
    w = max(x[1] for x in _testers_strip())
    assert N.lightness(_grey(94), w) >= N.NEAR_WHITE_L + 15
    assert N.lightness(_grey(7), w) <= N.NEAR_BLACK_L - 10


def test_the_testers_strip_is_cleared_with_one_swap():
    xyz = _mid() + _testers_strip() + _mid()
    slots, moves = N.arrange(xyz, len(xyz), 12, len(xyz))
    assert N.remaining_pairs(xyz, None, len(xyz), 12) == 1
    assert N.remaining_pairs(xyz, slots, len(xyz), 12) == 0
    assert len(moves) == 1
    assert sorted(slots) == list(range(len(xyz)))          # a permutation
    assert sum(1 for i, s in enumerate(slots) if i != s) == 2
    # deterministic
    assert N.arrange(xyz, len(xyz), 12, len(xyz)) == (slots, moves)


def test_nothing_moves_without_such_neighbours():
    xyz = _mid() * 3
    assert N.arrange(xyz, len(xyz), 12, len(xyz)) == (None, [])


def test_padding_and_other_pages_are_never_used():
    # the near-black is the last real patch; the paper-white padding follows
    xyz = _mid()[:11] + [_grey(5)] + [_grey(100)] * 12
    slots, moves = N.arrange(xyz, len(xyz), 12, movable=12, per_page=12)
    # the only fix would move a padding patch or go to page 2: none is made
    assert slots is None and moves == []
    assert N.remaining_pairs(xyz, None, len(xyz), 12) == 0   # strips differ


def test_targens_whites_then_blacks_are_parted():
    xyz = [_grey(100)] * 4 + [_grey(0)] * 4 + _mid()[:4] + _mid() * 2
    slots, moves = N.arrange(xyz, len(xyz), 12, len(xyz))
    assert moves and N.remaining_pairs(xyz, slots, len(xyz), 12) == 0


# ---- through the layout engine -------------------------------------------------

def _ti1(path: Path, rgbs) -> Path:
    rows = []
    for i, (r, g, b) in enumerate(rgbs, 1):
        x, y, z = _grey((r + g + b) / 3)
        rows.append(f"{i} {r:.4f} {g:.4f} {b:.4f} {x:.5f} {y:.5f} {z:.5f}")
    path.write_text(
        "CTI1   \n\nDESCRIPTOR \"Argyll Calibration Target chart information 1\"\n"
        "ORIGINATOR \"ChromIQ test\"\nCOLOR_REP \"iRGB\"\n\nNUMBER_OF_FIELDS 7\n"
        "BEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z \n"
        "END_DATA_FORMAT\n\n" + f"NUMBER_OF_SETS {len(rgbs)}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="latin-1")
    return path


def _rgbs(with_pair: bool):
    ramp = [(v, v, v) for v in (30, 35, 40, 45, 50, 55, 60, 65, 70, 72, 74, 76)]
    if with_pair:
        ramp[6] = (95, 95, 95)
        ramp[7] = (6, 6, 6)
    return ramp * 4


def _build(tmp, name, rgbs, **kw):
    from workflow.layout_engine.chart import build_chart
    ti1 = _ti1(tmp / f"{name}.ti1", rgbs)
    return build_chart(ti1, tmp / name, instrument="i1", paper="A4",
                       seed=1, dpi=100, **kw)


def _digest(paths) -> str:
    h = hashlib.sha256()
    for p in paths:
        data = Path(p).read_bytes()
        if Path(p).suffix == ".ti2":
            data = b"\n".join(l for l in data.splitlines()
                              if not l.startswith(b"CREATED"))
        h.update(data)
    return h.hexdigest()


@pytest.mark.parametrize("pair,randomize", [(False, False), (True, True)])
def test_untouched_charts_are_byte_identical(tmp_path, pair, randomize):
    a = _build(tmp_path / "a", "c", _rgbs(pair), randomize=randomize) \
        if (tmp_path / "a").mkdir() is None else None
    b = _build(tmp_path / "b", "c", _rgbs(pair), randomize=randomize,
               avoid_dark_light_neighbours=True) \
        if (tmp_path / "b").mkdir() is None else None
    assert b.neighbour_moves == ()
    assert _digest([a.ti2_path, *a.tiff_paths]) == \
        _digest([b.ti2_path, *b.tiff_paths])


def _locs(ti2: Path) -> "dict[int, str]":
    out, on = {}, False
    for line in ti2.read_text(encoding="latin-1").splitlines():
        if line == "BEGIN_DATA":
            on = True
            continue
        if line == "END_DATA":
            break
        if on and line.strip():
            f = line.split()
            out[int(f[0])] = f[1].strip('"')
    return out


def test_a_chart_with_such_a_pair_is_rearranged_and_recorded(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    off = _build(tmp_path / "a", "c", _rgbs(True), randomize=False)
    on = _build(tmp_path / "b", "c", _rgbs(True), randomize=False,
                avoid_dark_light_neighbours=True, spacer_mode="none")
    off = _build(tmp_path / "a", "c2", _rgbs(True), randomize=False,
                 spacer_mode="none")
    assert on.neighbour_moves and on.neighbour_pairs_left == 0
    assert on.neighbour_patches_moved == 2 * len(on.neighbour_moves)
    a, b = _locs(off.ti2_path), _locs(on.ti2_path)
    assert set(a) == set(b) and sorted(a.values()) == sorted(b.values())
    moved = {i for i in a if a[i] != b[i]}
    assert 2 <= len(moved) <= 2 * len(on.neighbour_moves)
    assert off.tiff_paths and on.tiff_paths
    assert _digest(off.tiff_paths) != _digest(on.tiff_paths)


def test_calibration_and_tables_are_never_rearranged(tmp_path):
    (tmp_path / "a").mkdir()
    r = _build(tmp_path / "a", "c", _rgbs(True), randomize=False,
               avoid_dark_light_neighbours=True, ramps_per_strip=True)
    assert r.neighbour_moves == ()


# ---- the recipe and the panel ----------------------------------------------------

def test_it_is_off_by_default_everywhere_and_saved_when_on():
    from workflow.layout_engine.presets import LayoutRecipe, default_recipe
    assert LayoutRecipe().avoid_dark_light_neighbours is False
    assert default_recipe("i1", "A4").avoid_dark_light_neighbours is False
    for inst in ("i1", "p3", "CM"):
        assert "avoid_dark_light_neighbours" not in default_recipe(
            inst, "A4").build_kwargs()
    old = LayoutRecipe().to_dict()
    old.pop("avoid_dark_light_neighbours")
    assert LayoutRecipe.from_dict(old).avoid_dark_light_neighbours is False
    r = LayoutRecipe(randomize=False, avoid_dark_light_neighbours=True)
    assert r.build_kwargs()["avoid_dark_light_neighbours"] is True
    assert "avoid_dark_light_neighbours" not in LayoutRecipe(
        randomize=True).build_kwargs()
    assert LayoutRecipe.from_dict(r.to_dict()).avoid_dark_light_neighbours


def test_the_option_is_greyed_only_while_randomising(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel()
    assert p.avoid_dark_light_cb.isChecked() is False     # off by default
    p.randomize_cb.setChecked(True)
    assert not p.avoid_dark_light_cb.isEnabled()
    p.randomize_cb.setChecked(False)
    assert p.avoid_dark_light_cb.isEnabled()
    p.avoid_dark_light_cb.setChecked(True)
    assert p.get_recipe().avoid_dark_light_neighbours is True
    p.deleteLater()


def test_the_log_names_the_moves():
    from workflow.chart_creator import _neighbour_log_lines
    lines = _neighbour_log_lines([("1H", "2H")], 0, False, 2)
    assert len(lines) == 1 and "1H and 2H" in lines[0]
    assert "Patches moved: 2." in lines[0]
    # the truth about the exports: they list colours, not places
    assert "the chart file, not the patch set" in lines[0]
    assert "i1Profiler export all use them" not in lines[0]
    assert "Randomisation" in lines[0] and "—" not in lines[0]
    assert _neighbour_log_lines([("1H", "2H")], 0, True) == []
    assert len(_neighbour_log_lines([], 2, False)) == 1


def test_the_editor_reorders_nothing_behind_its_grid():
    src = (REPO / "ui/dialogs/ti2_relayout_dialog.py").read_text(encoding="utf-8")
    assert src.count("avoid_dark_light_neighbours = False") == 4
    i = src.index("self._engine_recipe.randomize = False")
    assert "self._engine_recipe.avoid_dark_light_neighbours = False" in \
        src[i:i + 300]


def test_the_option_is_greyed_where_it_has_no_meaning(qapp):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(with_selectors=True)
    p.randomize_cb.setChecked(False)
    assert p.instr is not None
    for i in range(p.instr.count()):
        p.instr.setCurrentIndex(i)
        want = p.instr.itemData(i) in ("i1", "p3", "CM")
        assert p.avoid_dark_light_cb.isEnabled() is want, p.instr.itemData(i)
    p.deleteLater()


# ---- review of 4.3.39: the search clears what one swap can clear -------------

W, K = _grey(100), _grey(0)


def _no_swap_clears(xyz, slots, steps, movable, per_page=0):
    """Truth of M-CHART-NEIGHBOURS-LEFT: for every pair left, no swap of
    either member with another movable patch on its page clears it while
    making fewer pairs around the two places."""
    n = len(xyz)
    at = list(range(n))
    if slots is not None:
        for p_, s_ in enumerate(slots):
            at[s_] = p_
    kinds = [N._kind(N.lightness(x, 100.0)) for x in xyz]

    def bad(e):
        return (0 <= e < n - 1 and e // steps == (e + 1) // steps
                and kinds[at[e]] * kinds[at[e + 1]] == -1)

    def local(ss):
        return sum(1 for e in {t + d for t in ss for d in (-1, 0)} if bad(e))
    for e in range(n - 1):
        if not bad(e):
            continue
        for src in (e, e + 1):
            if at[src] >= movable:
                continue
            for c in range(n):
                if c in (e, e + 1) or at[c] >= movable:
                    continue
                if per_page and c // per_page != src // per_page:
                    continue
                b = local((src, c))
                at[src], at[c] = at[c], at[src]
                ok = not bad(e) and local((src, c)) < b
                at[src], at[c] = at[c], at[src]
                if ok:
                    return False
    return True


def test_targens_white_then_black_start_is_cleared():
    """The reviewer's MAJOR: targen's 4 whites then 4 blacks at the start of
    the chart (A4 / A5) were never parted, on 13 charts of 13."""
    rest = [_grey(v) for v in (30, 40, 50, 60, 35, 45, 55, 65)] * 6
    xyz = [W] * 4 + [K] * 4 + rest
    slots, moves = N.arrange(xyz, len(xyz), 12, len(xyz))
    assert N.remaining_pairs(xyz, None, len(xyz), 12) == 1
    assert moves and N.remaining_pairs(xyz, slots, len(xyz), 12) == 0
    # inside the first strip, as the nearest place comes first
    assert all(m.slot_a // 12 == 0 and m.slot_b // 12 == 0 for m in moves)


def test_repeated_ramp_strips_are_cleared():
    """The reviewer's MAJOR: each strip two ramps light -> dark, so a dark
    end meets a light start inside the strip and both in-strip neighbours
    of the dark patch are dark too."""
    ramp = [_grey(v) for v in (100, 85, 70, 55, 40, 0)]
    xyz = (ramp + ramp) * 4
    assert N.remaining_pairs(xyz, None, len(xyz), 12) == 4
    slots, moves = N.arrange(xyz, len(xyz), 12, len(xyz))
    left = N.remaining_pairs(xyz, slots, len(xyz), 12)
    assert left == 0
    assert sorted(slots) == list(range(len(xyz)))


def test_lightness_is_judged_against_the_paper():
    shadows = [_grey(v) for v in (2, 5, 8, 12, 16, 20, 25, 30, 35, 40, 45, 50)]
    xyz = shadows * 3
    assert N.arrange(xyz, len(xyz), 12, len(xyz), white_y=100.0) == (None, [])
    # the old rule (lightest patch as white) would have called 50 % white
    assert N.lightness(_grey(50), max(x[1] for x in xyz)) >= N.NEAR_WHITE_L
    assert N.lightness(_grey(50), 100.0) < N.NEAR_WHITE_L


def test_white_point_comes_from_the_patch_set(tmp_path):
    p = tmp_path / "w.ti1"
    p.write_text('CTI1\nAPPROX_WHITE_POINT "95.1 88.0 108.8"\nBEGIN_DATA\n',
                 encoding="latin-1")
    assert N.white_y_of_ti1(p) == 88.0
    q = tmp_path / "x.ti1"
    q.write_text("CTI1\nBEGIN_DATA\n", encoding="latin-1")
    assert N.white_y_of_ti1(q) == 100.0


def test_a_left_pair_is_never_claimed_when_a_swap_exists():
    import random
    rnd = random.Random(7)
    pool = [W, K, _grey(50), _grey(30), _grey(70), _grey(95), _grey(5)]
    for trial in range(60):
        n = 48
        xyz = [rnd.choice(pool) for _ in range(n)]
        slots, _m = N.arrange(xyz, n, 12, n, per_page=24)
        if N.remaining_pairs(xyz, slots, n, 12):
            assert _no_swap_clears(xyz, slots, 12, n, per_page=24), trial


def test_a_drawn_spacer_separates_the_pair(tmp_path):
    (tmp_path / "s").mkdir()
    (tmp_path / "n").mkdir()
    sp = _build(tmp_path / "s", "c", _rgbs(True), randomize=False,
                avoid_dark_light_neighbours=True, spacer_mode="colored")
    no = _build(tmp_path / "n", "c", _rgbs(True), randomize=False,
                avoid_dark_light_neighbours=True, spacer_mode="none")
    assert sp.neighbour_moves == () and sp.neighbour_pairs_left == 0
    assert no.neighbour_moves


def test_targen_charts_lose_their_start_pair_and_log_no_false_left(tmp_path):
    """Real targen patch sets (whites then blacks first), laid out without
    spacers: the start pair is cleared and LEFT appears only when true."""
    import shutil
    import subprocess
    targen = shutil.which("targen") or "/Applications/Argyll/bin/targen"
    if not Path(targen).exists():
        pytest.skip("ArgyllCMS targen not available")
    from workflow.layout_engine.chart import build_chart
    for f in (100, 300):
        d = tmp_path / f"t{f}"
        d.mkdir()
        subprocess.run([targen, "-v0", "-d2", f"-f{f}", str(d / "t")],
                       check=True, capture_output=True, timeout=120)
        r = build_chart(d / "t.ti1", d / "c", instrument="i1", paper="A4",
                        seed=1, dpi=72, randomize=False, spacer_mode="none",
                        avoid_dark_light_neighbours=True)
        locs = _locs(r.ti2_path)
        assert r.neighbour_moves, f
        if r.neighbour_pairs_left:
            from workflow.layout_engine import ti1_reader
            t = ti1_reader.read_ti1(d / "t.ti1")
            xyz = [x for _d, x in t.patches] + [t.media_patch()[1]] * r.layout.padding
            assert _no_swap_clears(xyz, r.slots, r.layout.steps_in_pass,
                                   len(t.patches),
                                   r.layout.patches_per_page), f
