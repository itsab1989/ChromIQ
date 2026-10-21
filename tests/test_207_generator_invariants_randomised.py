"""#207 review (agent 12, 4.3.9): the multi-ink generator's three promises,
checked over many RANDOM settings rather than the handful the issue named.

1. "Ensure unique colours" never switches an ink on (nor off): every patch
   keeps exactly the inks it had.
2. No patch of any set, nor of the whole program, is over the ink limit.
3. The ink codes are in Argyll's canonical order whatever order the extra
   inks were added in, so an ink-specific set writes into its ink's column.

Seeded, so a failure names a reproducible case. targen is left out: its
patches are Argyll's, and it needs the binaries.
"""
from __future__ import annotations

import random

import pytest

from workflow import patch_generators_nd as NDG

EXTRA = ("o", "r", "g", "b", "v", "lc", "lm", "lk", "ly", "mk")
EPS = 1e-6


def _on(p):
    return frozenset(i for i, v in enumerate(p) if v > 0.0)


def _random_inks(rnd):
    extra = rnd.sample(EXTRA, rnd.randint(0, 4))
    return ["c", "m", "y", "k"] + extra


@pytest.mark.parametrize("seed", range(40))
def test_function_level_invariants(seed):
    rnd = random.Random(1000 + seed)
    inks = _random_inks(rnd)
    order = {c: i for i, c in enumerate(
        ("c", "m", "y", "k", "o", "r", "g", "b", "v", "w", "lc", "lm", "ly",
         "lk", "mc", "mm", "my", "mk", "llk"))}
    inks = sorted(inks, key=order.get)
    n = len(inks)
    limit = float(rnd.choice([80, 150, 180, 220, 260, 300, 320, 352, 400]))
    sets = {
        "ramps": NDG.per_ink_ramps(n, rnd.randint(2, 21), ink_limit=limit,
                                   spacing=rnd.choice(["linear", "light"])),
        "pairs": NDG.ink_pair_overprints(n, rnd.randint(1, 8), ink_limit=limit),
        "grids": NDG.ink_pair_grids(inks, rnd.randint(1, 5), ink_limit=limit),
        "triples": NDG.ink_triple_overprints(n, rnd.randint(1, 5),
                                             ink_limit=limit),
        "richblack": NDG.rich_black_ramp(rnd.randint(1, 8), rnd.randint(1, 4),
                                         n, 3, ink_limit=limit),
        "neutral": NDG.neutral_ramp_device(rnd.randint(2, 21), n,
                                           ink_limit=limit),
    }
    for name, s in sets.items():
        over = [p for p in s if sum(p) > limit + EPS]
        assert not over, f"{name} at {limit} %: {over[:3]}"
    for p in sets["grids"]:
        assert len(_on(p)) == 2, f"a grid patch lost an ink: {p}"
    program = [p for s in sets.values() for p in s]
    rnd.shuffle(program)
    md = rnd.choice([1.0, 2.0, 3.0, 5.0])
    nudged = NDG.enforce_min_distance_nd(program, md, ink_limit=limit)
    assert len(nudged) == len(program)
    for a, b in zip(program, nudged):
        assert _on(a) == _on(b), f"unique colours changed the inks: {a} -> {b}"
        assert sum(b) <= max(limit, sum(a)) + EPS
    deduped = NDG.deduplicate_nd(program, ink_limit=limit)
    for a, b in zip(program, deduped):
        assert _on(a) == _on(b), f"dedupe changed the inks: {a} -> {b}"
        assert sum(b) <= max(limit, sum(a)) + EPS
    total = len(program) + rnd.randint(1, 120)
    fill = NDG.separation_fill_nd(program, total, inks, ink_limit=limit)
    assert len(fill) == total - len(program)
    for p in fill:
        assert sum(p) <= limit + EPS, p
        assert all(0.0 <= v <= 100.0 + EPS for v in p)
        assert "w" not in [inks[i] for i in _on(p)]


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


@pytest.mark.parametrize("seed", range(12))
def test_the_window_keeps_its_promises(qapp, tmp_path, seed):
    from ui.dialogs.ti2_relayout_dialog import _NewChartDialog
    rnd = random.Random(seed)
    d = _NewChartDialog(tmp_path, _FakeSettings())
    try:
        d._device_type.setCurrentIndex(d._device_type.findData(
            rnd.choice(["cmyk", "cmykplus", "cmykplus"])))
        added = []
        if d._device_type.currentData() == "cmykplus":
            for code in rnd.sample(EXTRA, rnd.randint(1, 4)):
                ix = d._nch_add_ink.findData(code)
                if ix > 0:
                    d._on_add_ink(ix)
                    added.append(code)
        d._refresh_nch_state()
        codes = d._nch_ink_codes()
        order = [c for c in ("c", "m", "y", "k", "o", "r", "g", "b", "v",
                             "w", "lc", "lm", "ly", "lk", "mc", "mm", "my",
                             "mk", "llk") if c in codes]
        assert codes == order, f"inks added {added} gave {codes}"
        limit = rnd.choice([160, 200, 240, 280, 300, 320, 360])
        d._ink_limit.setValue(limit)
        d._mode_generate.setChecked(True)
        d._nch_targen.setChecked(False)
        for cb, spin, hi in ((d._nch_perink, d._nch_perink_n, 21),
                             (d._nch_pairs, d._nch_pairs_n, 6),
                             (d._nch_triples, d._nch_triples_n, 4),
                             (d._nch_richblack, d._nch_richblack_n, 6),
                             (d._gen_neutral, d._gen_neutral_n, 21)):
            cb.setChecked(rnd.random() < 0.7)
            spin.setValue(rnd.randint(max(spin.minimum(), 1),
                                      max(spin.minimum(), hi)))
        d._nch_perink_light.setChecked(rnd.random() < 0.5)
        d._nch_pairs_grid.setChecked(rnd.random() < 0.5)
        d._gen_nearneutral.setChecked(False)
        d._gen_whiteblack.setChecked(False)
        d._gen_fill.setChecked(False)
        d._gen_unique.setChecked(False)
        plain = list(d._build_generated_program_uncached())
        d._gen_unique.setChecked(True)
        unique = list(d._build_generated_program_uncached())
        assert len(plain) == len(unique)
        for a, b in zip(plain, unique):
            assert _on(a) == _on(b), (
                f"seed {seed}: unique colours switched an ink: {a} -> {b}")
        d._gen_whiteblack.setChecked(True)
        d._gen_fill.setChecked(True)
        d._gen_fill_sparse.setChecked(rnd.random() < 0.6)
        d._gen_fill_to.setValue(len(unique) + rnd.randint(20, 200))
        full = list(d._build_generated_program_uncached())
        over = [p for p in full if sum(p) > limit + EPS]
        assert not over, f"seed {seed}: {len(over)} over {limit} %: {over[:3]}"
    finally:
        d.deleteLater()
