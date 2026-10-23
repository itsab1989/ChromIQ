"""Two named photo papers for 4 x 6 in printers that really print 10 x 15 cm
(100 x 150 mm) or postcard size (100 x 148 mm): jctay, forum 149803, and
Basti 2026-10-23 ("i get jctay's complaint if it is true that we only offer
this slightly too big measurements for 4x6 paper size").

Before, the only small photo paper in the list was "4x6" (101.6 x 152.4 mm),
so a chart for a printer whose card is 100 x 148 mm came out larger than the
card. The new papers lay the chart out for the card itself.

What must NOT change: the existing "4x6" paper, and a custom "100x150" size,
keep their codes, labels, capacities and printtarg arguments, so every chart,
preset and project made before loads and lays out exactly as saved.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import data.patch_db as DB

NEW = ("10x15cm", "postcard")
TABLES = [n for n in dir(DB) if n.startswith("_PER_SHEET_CAPACITY")
          and isinstance(getattr(DB, n), dict)]


def test_the_two_papers_are_offered_with_their_sizes():
    from workflow.layout_engine.papers import dimensions_mm
    for code in NEW:
        assert code in DB.PAPER_SIZES
        assert code in DB.PAPER_LABELS
    assert dimensions_mm("10x15cm") == (100.0, 150.0)
    assert dimensions_mm("postcard") == (100.0, 148.0)
    assert "100 × 150 mm" in DB.PAPER_LABELS["10x15cm"]
    assert "100 × 148 mm" in DB.PAPER_LABELS["postcard"]


def test_printtarg_gets_the_millimetres_not_the_code():
    assert DB.PAPER_PRINTTARG_ARG["10x15cm"] == "100x150"
    assert DB.PAPER_PRINTTARG_ARG["postcard"] == "100x148"
    # every call site maps through the table, none passes p.paper raw
    root = Path(__file__).resolve().parent.parent
    for rel in ("workflow/chart_creator.py", "ui/tabs/tab_chart.py"):
        src = (root / rel).read_text(encoding="utf-8")
        assert "PAPER_PRINTTARG_ARG.get(p.paper, p.paper)" in src, rel


def test_existing_4x6_and_custom_100x150_are_unchanged():
    assert DB.PAPER_LABELS["4x6"] == "4×6\" (102 × 152 mm)"
    assert DB.PAPER_PRINTTARG_ARG.get("4x6", "4x6") == "4x6"
    # a custom size is not a named paper and is passed to printtarg as typed
    assert "100x150" not in DB.PAPER_PRINTTARG_ARG
    assert "100x148" not in DB.PAPER_PRINTTARG_ARG
    # the stored 4x6 capacities, as they were before the new papers
    assert DB.query_patches("i1", "4x6") == 100
    assert DB.query_patches("p3", "4x6") == 20
    assert DB.query_patches("CM", "4x6") == 18
    assert DB.query_patches("CM", "4x6", double_density=True) == 30
    assert DB.query_patches("SS", "4x6") == 209
    assert DB.query_patches("i1", "4x6", suppress_lb=False) == 80


def test_every_table_that_knows_4x6_knows_the_new_papers():
    """Measured with printtarg -t300 per table's own flags
    (scripts/measure_photo_paper_capacity.py, which re-measures each table's
    4x6 value first as a check of the method)."""
    for name in TABLES:
        table = getattr(DB, name)
        if "TRIPLE" in name:
            if "4x6" in table:
                for code in NEW:
                    assert table.get(code, 0) > 0, (name, code)
            continue
        for key in [k for k in table if k[2] == "4x6"]:
            for code in NEW:
                assert table.get((key[0], key[1], code), 0) > 0, (name, key, code)


def test_a_postcard_never_holds_more_than_the_10x15_card():
    for name in TABLES:
        table = getattr(DB, name)
        for key, v in table.items():
            paper = key if isinstance(key, str) else key[2]
            if paper != "postcard":
                continue
            other = ("10x15cm" if isinstance(key, str)
                     else (key[0], key[1], "10x15cm"))
            assert v <= table[other], (name, key)


def test_a_generated_name_spells_the_millimetres():
    assert DB.paper_name_token("10x15cm") == "100x150mm"
    assert DB.paper_name_token("postcard") == "100x148mm"
    assert DB.paper_name_token("4x6") == "4x6in"


def test_the_dropdown_row_is_translated():
    from core import i18n
    try:
        i18n.set_language("de")
        assert DB.paper_display_label("postcard").startswith("Postkarte")
        assert DB.paper_display_label("10x15cm").endswith("Hochformat")
    finally:
        i18n.set_language("en")
    assert DB.paper_display_label("10x15cm") == "10 × 15 cm (100 × 150 mm) Portrait"


_ARGYLL = Path(os.environ.get("ARGYLL_BIN", "/Applications/Argyll/bin"))


@pytest.mark.skipif(not (_ARGYLL / "printtarg").exists(), reason="no ArgyllCMS")
@pytest.mark.parametrize("code,mm", [("10x15cm", (100, 150)), ("postcard", (100, 148))])
def test_printtarg_lays_the_stored_capacity_on_one_card(tmp_path, code, mm):
    n = DB.query_patches("i1", code)
    subprocess.run([str(_ARGYLL / "targen"), "-d2", f"-f{n}", "c"], cwd=tmp_path,
                   check=True, capture_output=True, timeout=120)
    subprocess.run([str(_ARGYLL / "printtarg"), "-ii1", f"-p{DB.PAPER_PRINTTARG_ARG[code]}",
                    "-t100", "-L", "c"], cwd=tmp_path, check=True,
                   capture_output=True, timeout=120)
    tifs = sorted(tmp_path.glob("c*.tif"))
    assert len(tifs) == 1, [t.name for t in tifs]
    from PIL import Image
    with Image.open(tifs[0]) as im:
        w, h = im.size
    # printtarg's TIFF is the page less its default 6 mm margin on each side
    assert abs(w / 100 * 25.4 + 12 - mm[0]) < 1.0, w
    assert abs(h / 100 * 25.4 + 12 - mm[1]) < 1.0, h
