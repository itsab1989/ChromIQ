"""Regression tests for the #124 bug-report batch.

Covers: extra-ink swatch/preview colours (reports 4/5), the COLOR_REP →
ink-code parser behind them, the strip fill-up notes (report 6), the
white/black count sequence users found confusing (report 3, by design),
and the per-set ⓘ grid placement fixed alongside.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from workflow.layout_engine.colorants import (rep_ink_codes, to_display_rgb)

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication  # noqa: E402

import ui.dialogs.ti2_relayout_dialog as M  # noqa: E402
from ui.dialogs.ti2_relayout_dialog import _NewChartDialog  # noqa: E402
from ui.tooltip_button import TooltipButton  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self):
        self.d = {}

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v

    def save(self):
        pass


# ---------------------------------------------------------------------------
# Reports 4/5: extra-ink patches rendered pure white
# ---------------------------------------------------------------------------

def test_rep_ink_codes_parses_argyll_inkmask_notation():
    assert rep_ink_codes("CMYKOG") == ["c", "m", "y", "k", "o", "g"]
    assert rep_ink_codes("CMYKRB") == ["c", "m", "y", "k", "r", "b"]
    assert rep_ink_codes("CMYKcm") == ["c", "m", "y", "k", "lc", "lm"]
    assert rep_ink_codes("CMYK2c2m1k") == \
        ["c", "m", "y", "k", "mc", "mm", "llk"]
    assert rep_ink_codes("iRGB") == ["r", "g", "b"]
    assert rep_ink_codes("CMYX") is None          # unknown token
    assert rep_ink_codes("CMYK2") is None         # dangling digit


def test_extra_ink_solo_patches_are_not_white():
    # The user's exact case: a per-ink ramp of an extra ink has C=M=Y=K=0,
    # and rendered pure white before the fix.
    for i, name in ((4, "orange"), (5, "green")):
        dev = [0.0] * 6
        dev[i] = 100.0
        rgb = to_display_rgb(tuple(dev), "CMYKOG")
        assert rgb != (255, 255, 255), f"solid {name} renders as paper white"
        assert max(rgb) - min(rgb) > 30, f"solid {name} renders as grey"
    # And the specific hues are sane: orange is red-heavy, green green-heavy.
    o = to_display_rgb((0, 0, 0, 0, 100, 0), "CMYKOG")
    g = to_display_rgb((0, 0, 0, 0, 0, 100), "CMYKOG")
    assert o[0] > o[1] > o[2]
    assert g[1] > g[0] and g[1] > g[2]


def test_extra_ink_ramp_darkens_monotonically():
    # A 32-step orange ramp must produce 32 visually distinct swatches
    # (report 4 showed 32 identical white ones).
    from workflow.layout_engine.colorants import luminance
    lums = [luminance(to_display_rgb((0, 0, 0, 0, v, 0), "CMYKOG"))
            for v in [100.0 * i / 31 for i in range(32)]]
    assert all(a > b for a, b in zip(lums, lums[1:])), \
        "orange ramp luminance is not strictly decreasing"


def test_overprint_pairs_of_extra_inks_are_coloured():
    # Report 5: pair/triple overprints of extra inks showed white too.
    pair = to_display_rgb((0, 0, 0, 0, 50, 50), "CMYKOG")
    trio = to_display_rgb((0, 0, 0, 0, 40, 40, 40), "CMYKOGV")
    assert pair != (255, 255, 255) and max(pair) - min(pair) > 20
    assert trio != (255, 255, 255)


def test_light_ink_reps_render():
    lc = to_display_rgb((0, 0, 0, 0, 100, 0), "CMYKcm")
    assert lc[2] > lc[0]                          # light cyan: blue > red
    assert lc != (255, 255, 255)


def test_plain_cmyk_display_unchanged():
    # The 4-channel formula must stay bit-identical (existing charts,
    # pinned raster behaviour), and zero extras must equal the plain base.
    cases = [(0, 0, 0, 0), (10, 20, 30, 5), (100, 0, 0, 0), (0, 0, 0, 100),
             (50, 50, 50, 50)]
    for c, m, y, k in cases:
        base = (max(0, min(255, round(255 * (1 - c / 100) * (1 - k / 100)))),
                max(0, min(255, round(255 * (1 - m / 100) * (1 - k / 100)))),
                max(0, min(255, round(255 * (1 - y / 100) * (1 - k / 100)))))
        assert to_display_rgb((c, m, y, k), "CMYK") == base
        assert to_display_rgb((c, m, y, k, 0.0, 0.0), "CMYKOG") == base


def test_unparseable_rep_keeps_base_colour():
    # A rep the tokenizer can't read falls back to the CMYK base, never crashes.
    assert to_display_rgb((0, 0, 0, 0, 100), "CMYKX") == (255, 255, 255)


# ---------------------------------------------------------------------------
# Report 6: designed 896 → printed 910 (strip fill-up)
# ---------------------------------------------------------------------------

def test_padding_note_wording(qapp):
    assert M._padding_note(0) == ""
    one = M._padding_note(1)
    many = M._padding_note(14)
    assert "1 paper-white patch " in one
    assert "14 paper-white patches " in many
    assert "strip" in one and "strip" in many


def test_number_of_sets_reader(tmp_path):
    from ui.tabs.tab_chart import _number_of_sets
    p = tmp_path / "x.ti2"
    p.write_text("CTI2\n\nDESCRIPTOR \"x\"\nNUMBER_OF_SETS 910\nBEGIN_DATA\n", encoding="utf-8")
    assert _number_of_sets(p) == 910
    assert _number_of_sets(tmp_path / "missing.ti2") is None


# ---------------------------------------------------------------------------
# Report 3 (by design): white/black "each" counts toward a total
# ---------------------------------------------------------------------------

def test_white_black_count_sequence_with_cube(qapp, tmp_path):
    # The user's sequence: with the 3D cube ticked (it contributes one white
    # + one black), each: 1/2/3/4 adds 0/2/4/6 patches — the chart ends up
    # holding exactly N of each.
    dlg = _NewChartDialog(tmp_path, _FakeSettings())
    dlg._mode_generate.setChecked(True)   # enables the generator panel
    for name in dlg._GEN_CHECKS:
        getattr(dlg, f"_gen_{name}").setChecked(False)
    dlg._gen_unique.setChecked(True)
    dlg._gen_cube.setChecked(True)
    dlg._gen_whiteblack.setChecked(True)
    seen = []
    for n in (1, 2, 3, 4):
        dlg._gen_whiteblack_n.setValue(n)
        dlg._update_gen_counts()
        import re
        seen.append(int(re.search(r"(\d+)",
                                  dlg._gen_whiteblack_count.text()).group(1)))
    assert seen == [0, 2, 4, 6]
    # Without any contributing set, each: N adds the full 2N.
    dlg._gen_cube.setChecked(False)
    dlg._gen_whiteblack_n.setValue(3)
    dlg._update_gen_counts()
    import re
    assert int(re.search(r"(\d+)",
                         dlg._gen_whiteblack_count.text()).group(1)) == 6
    # The tooltip explains the arithmetic with a concrete example.
    assert "'each: 3' adds 4" in dlg._gen_whiteblack.toolTip()


# ---------------------------------------------------------------------------
# ⓘ placement: every per-set info icon sits in its own grid row (the H&S ⓘ
# had landed on the Near-neutral row after a grid renumbering)
# ---------------------------------------------------------------------------

def test_gen_row_info_icons_occupy_unique_cells(qapp, tmp_path):
    dlg = _NewChartDialog(tmp_path, _FakeSettings())
    grid = dlg._gen_panel.layout()
    cells = []
    for i in range(grid.count()):
        w = grid.itemAt(i).widget()
        if isinstance(w, TooltipButton):
            row, col, _rs, _cs = grid.getItemPosition(i)
            if col == 8:                      # the per-set ⓘ column
                cells.append((row, col))
    assert len(cells) == len(set(cells)), \
        f"overlapping per-set info icons: {sorted(cells)}"
    # Every multi-ink row (0..4) and every RGB set row (5..20) carries one.
    rows = {r for r, _ in cells}
    for row in range(0, 21):
        assert row in rows, f"generator row {row} has no ⓘ icon"
