"""#130 (Knut, 2026-08-01, on his Demo-Full-RGB): "Restore Used Chart" was
enabled for ever on a run whose stored chart is identical to the live one.

    "Run 5 was made from run 1 using duplicate. That seems to work, but the
     'Restore Used Chart' button is always active … and files in chart/ folder
     seem identical as the chart files in run5/. The chart/ folder has tif files
     in this case. Why is still 'Restore Used Chart' button enabled?"

Because of those `.tif` files, and he pointed straight at them.

``files_to_copy()`` leaves the page images out when the chart carries a layout
recipe — they can be redrawn from it. ``snapshot_matches_live`` compared that
against **everything** in ``chart/``, so a snapshot that does contain images
(taken before that rule, or from a chart with no recipe — and copied forward by
Duplicate) always had extra files on the stored side. Two identical charts
therefore looked different, the button never greyed, and pressing it did
nothing visible: the exact fault greying was introduced to cure.

The chart is what defines it, not the pictures of it.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_slot import ChartSlot, PROFILING_CHART_SUFFIXES   # noqa: E402
from workflow.verify_chart_snapshot import (                          # noqa: E402
    slot_live_differs, snapshot_matches_live)

STEM = "Demo"


def _slot(tmp_path):
    live = tmp_path / "run5"
    snap = live / "chart"
    live.mkdir(parents=True, exist_ok=True)
    snap.mkdir(parents=True, exist_ok=True)
    return ChartSlot(live_dir=live, snapshot_dir=snap, stem=STEM,
                     suffixes=PROFILING_CHART_SUFFIXES)


def _write(slot, *, images_in_snapshot: bool, same: bool = True):
    """A chart WITH a layout recipe, in both places."""
    recipe = '{"layout": {"engine": "chromiq"}}'
    for d in (slot.live_dir, slot.snapshot_dir):
        (d / f"{STEM}.ti1").write_text("CTI1\ndata\n")
        (d / f"{STEM}.ti2").write_text("CTI2\ndata\n")
        (d / f"{STEM}.channels.json").write_text(recipe)
    # The live side always has its pages; the snapshot only sometimes.
    for i in (1, 2, 3):
        (slot.live_dir / f"{STEM}_{i:02d}.tif").write_bytes(b"II*\0page")
        if images_in_snapshot:
            (slot.snapshot_dir / f"{STEM}_{i:02d}.tif").write_bytes(b"II*\0page")
    if not same:
        (slot.snapshot_dir / f"{STEM}.ti2").write_text("CTI2\nDIFFERENT\n")


# ---- his case ------------------------------------------------------------
def test_a_snapshot_that_kept_its_page_images_can_still_match(tmp_path):
    """THE regression: identical charts, images on both sides, button greys."""
    slot = _slot(tmp_path)
    _write(slot, images_in_snapshot=True)
    assert snapshot_matches_live(slot) is True
    assert slot_live_differs(slot) is False


def test_a_snapshot_without_images_still_matches(tmp_path):
    """The ordinary case — a snapshot taken under the current rule."""
    slot = _slot(tmp_path)
    _write(slot, images_in_snapshot=False)
    assert snapshot_matches_live(slot) is True


# ---- and a real difference is still found --------------------------------
def test_a_real_difference_is_still_detected_with_images(tmp_path):
    """A fix that simply stopped noticing differences would pass the test
    above and quietly break the feature."""
    slot = _slot(tmp_path)
    _write(slot, images_in_snapshot=True, same=False)
    assert snapshot_matches_live(slot) is False
    assert slot_live_differs(slot) is True


def test_a_real_difference_is_still_detected_without_images(tmp_path):
    slot = _slot(tmp_path)
    _write(slot, images_in_snapshot=False, same=False)
    assert snapshot_matches_live(slot) is False


def test_a_missing_chart_file_is_a_difference(tmp_path):
    """Dropping a file from the stored side must not be excused as "extra
    images" — only images may be forgiven."""
    slot = _slot(tmp_path)
    _write(slot, images_in_snapshot=True)
    (slot.snapshot_dir / f"{STEM}.ti1").unlink()
    assert snapshot_matches_live(slot) is False


def test_extra_non_image_files_still_count(tmp_path):
    """The forgiveness is for page images specifically, not for anything the
    stored side happens to hold."""
    slot = _slot(tmp_path)
    _write(slot, images_in_snapshot=True)
    (slot.snapshot_dir / f"{STEM}.strips.json").write_text("{}")
    assert snapshot_matches_live(slot) is False


def test_a_chart_with_no_recipe_compares_its_images(tmp_path):
    """Without a recipe the images ARE part of the copy, so they must be
    compared on both sides — a changed page is a changed chart."""
    slot = _slot(tmp_path)
    for d in (slot.live_dir, slot.snapshot_dir):
        (d / f"{STEM}.ti1").write_text("CTI1\ndata\n")
        (d / f"{STEM}.ti2").write_text("CTI2\ndata\n")
    (slot.live_dir / f"{STEM}_01.tif").write_bytes(b"II*\0page")
    (slot.snapshot_dir / f"{STEM}_01.tif").write_bytes(b"II*\0OTHER")
    assert snapshot_matches_live(slot) is False
