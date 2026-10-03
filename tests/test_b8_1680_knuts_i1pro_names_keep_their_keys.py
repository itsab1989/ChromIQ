"""B8-1680: Knut's new i1Pro and i1Pro 3 Plus names keep the presets' keys.

Knut, #182 5872273862 (2026-09-28): 56 of the i1Pro and i1Pro 3 Plus built-ins
get a new name, the old one plus the patch set's own name ("-Uniform 6x6x6",
"-9x9x9-Skintones-Plus"). *"They are to replace all those that have the same
beginning of the name ... The new and updated presets shall have the same tick
ON as before, in the "Settings for built-in presets" window."*

What was renamed is the NAME. The slug, and so the key a person's settings
store (their ticks in that window, the dropdown's data), stays what it was,
the same rule the CR30 w16 to w17 rename followed (ddc36b7c). So a setting
written by beta 49 under the old key still reaches the preset, now under its
new name, and the shipped ticks are exactly the ones beta 49 shipped.

Measured when the batch came in: all 56 exports' .ti1 files are byte-for-byte
the shipped chart.ti1, and their colour-set recipes equal the shipped
recipe.json after the importer's normalise_recipe. Nothing but the names moved,
which is why no asset and no B8-1590 geometry snapshot changes with this.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication                        # noqa: E402

import core.curated_presets as cp                               # noqa: E402
from core.argyll_runner import ArgyllRunner                     # noqa: E402
from core.file_manager import FileManager                       # noqa: E402
from core.settings import AppSettings                           # noqa: E402
from ui.tabs.tab_chart import (                                 # noqa: E402
    BUILTIN_PRESET_KEYS, KNUT_FLS_SUFFIX, KNUT_PRESETS, KNUT_PRESETS_BY_KEY,
    TabChart,
)

ROOT = Path(__file__).resolve().parent.parent

#: (slug, beta 49 name, Knut's new name, shipped ticked). The tick column is
#: what beta 49's data/preset_defaults.json said, key by key.
RENAMED = [
    ('i1_w8_a3_1144p_1page_landscape_w9_0mm',
     'A3-1144p-1page-Landscape-w9.0mm',
     'A3-1144p-1page-Landscape-w9.0mm-Uniform 9x9x9', False),
    ('i1_w75_a3_1404p_1page_landscape_w7_5mm',
     'A3-1404p-1page-Landscape-w7.5mm',
     'A3-1404p-1page-Landscape-w7.5mm-9x9x9-Skintones-Edge Emphasis', True),
    ('i1_w8_a3_2288p_2pages_landscape_w9_0mm',
     'A3-2288p-2pages-Landscape-w9.0mm',
     'A3-2288p-2pages-Landscape-w9.0mm-Uniform 12x12x12-Edge Emphasis', False),
    ('i1_w75_a3_2808p_2pages_landscape_w7_5mm',
     'A3-2808p-2pages-Landscape-w7.5mm',
     'A3-2808p-2pages-Landscape-w7.5mm-Uniform 13x13x13-Edge Emphasis', True),
    ('i1_w8_a3_3432p_3pages_landscape_w9_0mm',
     'A3-3432p-3pages-Landscape-w9.0mm',
     'A3-3432p-3pages-Landscape-w9.0mm-14x14x14-Skintones-Corner Emphasis-Plus', False),
    ('i1_w75_a3_4212p_3pages_landscape_w7_5mm',
     'A3-4212p-3pages-Landscape-w7.5mm',
     'A3-4212p-3pages-Landscape-w7.5mm-15x15x15-Skintones-Edge Emphasis-Plus', False),
    ('i1_w8_a4_1144p_2pages_portrait_w8_0mm',
     'A4-1144p-2pages-Portrait-w8.0mm',
     'A4-1144p-2pages-Portrait-w8.0mm-Uniform 9x9x9', True),
    ('fls_i1pro_a4_1200p_3pages_portrait',
     'A4-1200p-3pages-Portrait-w8.5mm',
     'A4-1200p-3pages-Portrait-w8.5mm-Uniform 9x9x9-Edge Emphasis', False),
    ('i1_w75_a4_1296p_2pages_portrait_w7_5mm',
     'A4-1296p-2pages-Portrait-w7.5mm',
     'A4-1296p-2pages-Portrait-w7.5mm-Uniform 9x9x9-Edge Emphasis', True),
    ('i1_w8_a4_1716p_3pages_portrait_w8_0mm',
     'A4-1716p-3pages-Portrait-w8.0mm',
     'A4-1716p-3pages-Portrait-w8.0mm-Uniform 10x10x10-Skintones-Edge Emphasis', True),
    ('i1_w75_a4_1944p_3pages_portrait_w7_5mm',
     'A4-1944p-3pages-Portrait-w7.5mm',
     'A4-1944p-3pages-Portrait-w7.5mm-Uniform 11x11x11-Edge Emphasis', True),
    ('i1_w8_a4_2288p_4pages_portrait_w8_0mm',
     'A4-2288p-4pages-Portrait-w8.0mm',
     'A4-2288p-4pages-Portrait-w8.0mm-Uniform 12x12x12-Edge Emphasis', False),
    ('i1_w75_a4_2592p_4pages_portrait_w7_5mm',
     'A4-2592p-4pages-Portrait-w7.5mm',
     'A4-2592p-4pages-Portrait-w7.5mm-12x12x12-Skintones-Edge Emphasis-Plus', False),
    ('i1_w8_a4_2860p_5pages_portrait_w8_0mm',
     'A4-2860p-5pages-Portrait-w8.0mm',
     'A4-2860p-5pages-Portrait-w8.0mm-Uniform 13x13x13-Edge Emphasis', False),
    ('i1_w8_a4_312p_1page_portrait_w8_0mm',
     'A4-312p-1page-Portrait-w8.0mm',
     'A4-312p-1page-Portrait-w8.0mm-Uniform 6x6x6', False),
    ('i1_w75_a4_3240p_5pages_portrait_w7_5mm',
     'A4-3240p-5pages-Portrait-w7.5mm',
     'A4-3240p-5pages-Portrait-w7.5mm-13x13x13-Skintones-Edge Emphasis-Plus', False),
    ('i1_w75_a4_324p_1page_portrait_w7_5mm',
     'A4-324p-1page-Portrait-w7.5mm',
     # renamed again in 4.3.3-beta.1 (#182 5943544919); the key still holds
     'A4-324p-1page-Portrait-w7.5mm-Uniform 6x6x6-Half Page', False),
    ('i1_w8_a4_3432p_6pages_portrait_w8_0mm',
     'A4-3432p-6pages-Portrait-w8.0mm',
     'A4-3432p-6pages-Portrait-w8.0mm-14x14x14-Skintones-Corner Emphasis-Plus', False),
    ('i1_w75_a4_3888p_6pages_portrait_w7_5mm',
     'A4-3888p-6pages-Portrait-w7.5mm',
     'A4-3888p-6pages-Portrait-w7.5mm-14x14x14-Skintones-Edge Emphasis-Plus', False),
    ('fls_i1pro_a4_484p_1page_portrait',
     'A4-484p-1page-Portrait-w7.5mm',
     'A4-484p-1page-Portrait-w7.5mm-Uniform 7x7x7', False),
    ('i1_w8_a4_572p_1page_portrait_w8_0mm',
     'A4-572p-1page-Portrait-w8.0mm',
     'A4-572p-1page-Portrait-w8.0mm-Uniform 7x7x7-Edge Emphasis', True),
    ('i1_w75_a4_648p_1page_portrait_w7_5mm',
     'A4-648p-1page-Portrait-w7.5mm',
     'A4-648p-1page-Portrait-w7.5mm-Uniform 6x6x6-Edge Emphasis', True),
    ('i1_w8_letter_1144p_2pages_portrait_w8_0mm',
     'Letter-1144p-2pages-Portrait-w8.0mm',
     'Letter-1144p-2pages-Portrait-w8.0mm-Uniform 9x9x9', True),
    ('i1_w75_letter_1296p_2pages_portrait_w7_5mm',
     'Letter-1296p-2pages-Portrait-w7.5mm',
     'Letter-1296p-2pages-Portrait-w7.5mm-Uniform 9x9x9-Edge Emphasis', True),
    ('i1_w8_letter_1716p_3pages_portrait_w8_0mm',
     'Letter-1716p-3pages-Portrait-w8.0mm',
     'Letter-1716p-3pages-Portrait-w8.0mm-Uniform 10x10x10-Skintones-Edge Emphasis', True),
    ('i1_w75_letter_1944p_3pages_portrait_w7_5mm',
     'Letter-1944p-3pages-Portrait-w7.5mm',
     'Letter-1944p-3pages-Portrait-w7.5mm-Uniform 11x11x11-Edge Emphasis', True),
    ('i1_w8_letter_2288p_4pages_portrait_w8_0mm',
     'Letter-2288p-4pages-Portrait-w8.0mm',
     'Letter-2288p-4pages-Portrait-w8.0mm-Uniform 12x12x12-Edge Emphasis', False),
    ('i1_w75_letter_2592p_4pages_portrait_w7_5mm',
     'Letter-2592p-4pages-Portrait-w7.5mm',
     'Letter-2592p-4pages-Portrait-w7.5mm-12x12x12-Skintones-Edge Emphasis-Plus', False),
    ('i1_w8_letter_2860p_5pages_portrait_w8_0mm',
     'Letter-2860p-5pages-Portrait-w8.0mm',
     'Letter-2860p-5pages-Portrait-w8.0mm-Uniform 13x13x13-Edge Emphasis', False),
    ('i1_w8_letter_312p_1page_portrait_w8_0mm',
     'Letter-312p-1page-Portrait-w8.0mm',
     'Letter-312p-1page-Portrait-w8.0mm-Uniform 6x6x6', False),
    ('i1_w75_letter_3240p_5pages_portrait_w7_5mm',
     'Letter-3240p-5pages-Portrait-w7.5mm',
     'Letter-3240p-5pages-Portrait-w7.5mm-13x13x13-Skintones-Edge Emphasis-Plus', False),
    ('i1_w75_letter_324p_1page_portrait_w7_5mm',
     'Letter-324p-1page-Portrait-w7.5mm',
     'Letter-324p-1page-Portrait-w7.5mm-Uniform 6x6x6', False),
    ('i1_w8_letter_3432p_6pages_portrait_w8_0mm',
     'Letter-3432p-6pages-Portrait-w8.0mm',
     'Letter-3432p-6pages-Portrait-w8.0mm-14x14x14-Skintones-Corner Emphasis-Plus', False),
    ('i1_w75_letter_3888p_6pages_portrait_w7_5mm',
     'Letter-3888p-6pages-Portrait-w7.5mm',
     'Letter-3888p-6pages-Portrait-w7.5mm-14x14x14-Skintones-Edge Emphasis-Plus', False),
    ('i1_w8_letter_572p_1page_portrait_w8_0mm',
     'Letter-572p-1page-Portrait-w8.0mm',
     'Letter-572p-1page-Portrait-w8.0mm-Uniform 7x7x7-Edge Emphasis', True),
    ('i1_w75_letter_648p_1page_portrait_w7_5mm',
     'Letter-648p-1page-Portrait-w7.5mm',
     'Letter-648p-1page-Portrait-w7.5mm-Uniform 6x6x6-Edge Emphasis', True),
    ('p3_a3_1008p_3pages_portrait_w16_0mm',
     'A3-1008p-3pages-Portrait-w16.0mm',
     'A3-1008p-3pages-Portrait-w16.0mm-8x8x8-Skintones-Plus', False),
    ('p3_a3_1344p_4pages_portrait_w16_0mm',
     'A3-1344p-4pages-Portrait-w16.0mm',
     'A3-1344p-4pages-Portrait-w16.0mm-9x9x9-Corner Emphasis-Plus', True),
    ('p3_a3_1680p_5pages_portrait_w16_0mm',
     'A3-1680p-5pages-Portrait-w16.0mm',
     'A3-1680p-5pages-Portrait-w16.0mm-10x10x10-Skintones-Edge Emphasis-Plus', False),
    ('p3_a3_2016p_6pages_portrait_w16_0mm',
     'A3-2016p-6pages-Portrait-w16.0mm',
     'A3-2016p-6pages-Portrait-w16.0mm-11x11x11-Corner Emphasis-Plus', True),
    ('p3_a3_336p_1page_portrait_w16_0mm',
     'A3-336p-1page-Portrait-w16.0mm',
     'A3-336p-1page-Portrait-w16.0mm-Uniform 5x5x5-Skintones-Edge Emphasis', False),
    ('p3_a3_672p_2pages_portrait_w16_0mm',
     'A3-672p-2pages-Portrait-w16.0mm',
     'A3-672p-2pages-Portrait-w16.0mm-6x6x6-Skintones-Plus', True),
    ('p3_a4_1232p_8pages_portrait_w16_0mm',
     'A4-1232p-8pages-Portrait-w16.0mm',
     'A4-1232p-8pages-Portrait-w16.0mm-9x9x9-Skintones-Plus', True),
    ('p3_a4_1540p_10pages_portrait_w16_0mm',
     'A4-1540p-10pages-Portrait-w16.0mm',
     'A4-1540p-10pages-Portrait-w16.0mm-Uniform 10x10x10-Skintones', False),
    ('p3_a4_2002p_13pages_portrait_w16_0mm',
     'A4-2002p-13pages-Portrait-w16.0mm',
     'A4-2002p-13pages-Portrait-w16.0mm-Uniform 11x11x11-Skintones-Edge Emphasis', True),
    ('p3_a4_308p_2pages_portrait_w16_0mm',
     'A4-308p-2pages-Portrait-w16.0mm',
     'A4-308p-2pages-Portrait-w16.0mm-Uniform 5x5x5', True),
    ('p3_a4_462p_3pages_portrait_w16_0mm',
     'A4-462p-3pages-Portrait-w16.0mm',
     'A4-462p-3pages-Portrait-w16.0mm-Uniform 6x6x6-Skintones-Edge Emphasis', False),
    ('p3_a4_616p_4pages_portrait_w16_0mm',
     'A4-616p-4pages-Portrait-w16.0mm',
     'A4-616p-4pages-Portrait-w16.0mm-6x6x6-Plus', True),
    ('p3_a4_924p_6pages_portrait_w16_0mm',
     'A4-924p-6pages-Portrait-w16.0mm',
     'A4-924p-6pages-Portrait-w16.0mm-Uniform 8x8x8-Edge Emphasis', False),
    ('p3_letter_1144p_8pages_portrait_w16_0mm',
     'Letter-1144p-8pages-Portrait-w16.0mm',
     'Letter-1144p-8pages-Portrait-w16.0mm-9x9x9-Skintones-Plus', True),
    ('p3_letter_1430p_10pages_portrait_w16_0mm',
     'Letter-1430p-10pages-Portrait-w16.0mm',
     'Letter-1430p-10pages-Portrait-w16.0mm-Uniform 10x10x10', False),
    ('p3_letter_2002p_14pages_portrait_w16_0mm',
     'Letter-2002p-14pages-Portrait-w16.0mm',
     'Letter-2002p-14pages-Portrait-w16.0mm-Uniform 11x11x11-Skintones-Edge Emphasis', True),
    ('p3_letter_286p_2pages_portrait_w16_0mm',
     'Letter-286p-2pages-Portrait-w16.0mm',
     'Letter-286p-2pages-Portrait-w16.0mm-Uniform 5x5x5-Edge Emphasis', True),
    ('p3_letter_429p_3pages_portrait_w16_0mm',
     'Letter-429p-3pages-Portrait-w16.0mm',
     'Letter-429p-3pages-Portrait-w16.0mm-Uniform 6x6x6-Skintones-Edge Emphasis', False),
    ('p3_letter_572p_4pages_portrait_w16_0mm',
     'Letter-572p-4pages-Portrait-w16.0mm',
     'Letter-572p-4pages-Portrait-w16.0mm-Uniform 6x6x6-Skintones', True),
    ('p3_letter_858p_6pages_portrait_w16_0mm',
     'Letter-858p-6pages-Portrait-w16.0mm',
     'Letter-858p-6pages-Portrait-w16.0mm-Uniform 8x8x8-Skintones-Edge Emphasis', False),
]


def _key(slug: str) -> str:
    return f"__chromiq_knut_{slug}__"


def _bare(name: str) -> str:
    return name[: -len(KNUT_FLS_SUFFIX)] if name.endswith(KNUT_FLS_SUFFIX) else name


def test_the_batch_is_the_fifty_six_knut_sent():
    assert len(RENAMED) == 56
    assert len({s for s, *_ in RENAMED}) == 56
    assert sum(1 for *_, ticked in RENAMED if ticked) == 25


@pytest.mark.parametrize("slug,old,new,_ticked", RENAMED, ids=[r[0] for r in RENAMED])
def test_the_old_key_reaches_the_renamed_preset(slug, old, new, _ticked):
    key = _key(slug)
    assert key in BUILTIN_PRESET_KEYS
    p = KNUT_PRESETS_BY_KEY[key]
    assert p.slug == slug
    assert _bare(p.name) == new
    assert new.startswith(old + "-"), "the new name keeps the old beginning"
    assert KNUT_FLS_SUFFIX in p.marked_name, "the row keeps its Full layout setup label"
    assert "built-in" in p.combo_label


def test_no_preset_still_carries_an_old_name():
    """Replaced, not added: no built-in is left under a beta 49 name."""
    olds = {old for _s, old, _n, _t in RENAMED}
    assert not olds & {_bare(p.name) for p in KNUT_PRESETS}


def test_the_shipped_ticks_are_the_ones_beta_49_shipped():
    shown = json.loads((ROOT / "data" / "preset_defaults.json")
                       .read_text(encoding="utf-8"))["shown"]
    for slug, _old, new, ticked in RENAMED:
        key = _key(slug)
        assert (key in shown) is ticked, slug
        assert cp.is_shown_by_default(key) is ticked, slug
        if ticked:
            assert f" · {new} ·" in shown[key], "the reader's name follows"


@pytest.fixture()
def settings(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set(cp.PAPER_FILTER_KEY, False)
    return s


def test_a_tick_stored_under_the_old_key_still_holds(settings):
    """A beta 49 user unticked one shipped-ON preset and ticked one shipped-OFF
    one. Their answer is stored under the keys, so it reaches the renamed rows."""
    on = next(s for s, _o, _n, t in RENAMED if t)
    off = next(s for s, _o, _n, t in RENAMED if not t)
    settings.set(cp.SETTING_KEY, json.dumps({_key(on): False, _key(off): True}))
    shown = cp.shown_keys(settings, BUILTIN_PRESET_KEYS)
    assert _key(on) not in shown
    assert _key(off) in shown


def test_the_dropdown_lists_the_old_key_under_the_new_name(settings):
    QApplication.instance() or QApplication([])
    tab = TabChart(ArgyllRunner(settings), FileManager(settings), settings)
    try:
        combo = tab._preset_combo
        for slug, _old, new, _t in RENAMED:
            idx = combo.findData(_key(slug))
            assert idx >= 0, slug
            assert new in combo.itemText(idx), (slug, combo.itemText(idx))
    finally:
        tab.hide()
        tab.deleteLater()
        QApplication.instance().processEvents()
