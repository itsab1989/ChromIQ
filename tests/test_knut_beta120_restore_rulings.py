"""#130 (Knut, 2026-08-02): two rulings on Restore Used Chart.

Both came out of the table he asked for — every combination of layout recipe,
images in ``chart/`` and images in the run, built and measured rather than
reasoned about.

**1. Page images count whenever both sides have them.**

    "Yes, I prefer images are always counted when both sides have them — even
     with a recipe."

The comparison used to be built from ``files_to_copy()``, which answers a
different question (what to put IN the folder) and leaves images out when a
recipe can redraw them. So a page image that had changed under a
recipe-carrying chart was never noticed.

**2. A restore that would destroy unregenerable pages must ask first.**

The table turned up a case worse than a stuck button: no recipe, no images in
``chart/``, images in the run. Restore replaces the whole live chart with the
stored one, so those pages are removed — and with no recipe nothing can redraw
them. His ruling:

    "I prefer option '1. Warn and let it proceed', but that the warning allow
     user to make the informed choice (The warning window must ask the user to
     investigate the specific files in question to make an informed decision)"
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.chart_slot import ChartSlot, PROFILING_CHART_SUFFIXES   # noqa: E402
from workflow.verify_chart_snapshot import (                          # noqa: E402
    restore_would_lose_pages, snapshot_matches_live)

STEM = "Demo"
RECIPE = '{"layout": {"engine": "chromiq"}}'


def _slot(tmp_path, *, recipe, snap_img, live_img, img_bytes=b"page"):
    live = tmp_path / "run5"
    snap = live / "chart"
    live.mkdir(parents=True, exist_ok=True)
    snap.mkdir(parents=True, exist_ok=True)
    for d in (live, snap):
        (d / f"{STEM}.ti1").write_text("CTI1\n", encoding="utf-8")
        (d / f"{STEM}.ti2").write_text("CTI2\n", encoding="utf-8")
        if recipe:
            (d / f"{STEM}.channels.json").write_text(RECIPE, encoding="utf-8")
    if live_img:
        (live / f"{STEM}_01.tif").write_bytes(b"page")
    if snap_img:
        (snap / f"{STEM}_01.tif").write_bytes(img_bytes)
    return ChartSlot(live_dir=live, snapshot_dir=snap, stem=STEM,
                     suffixes=PROFILING_CHART_SUFFIXES)


# ---- ruling 1: images count when both sides have them --------------------
def test_a_changed_page_is_noticed_even_with_a_recipe(tmp_path):
    """THE ruling. Before this, a recipe meant the images were never compared."""
    slot = _slot(tmp_path, recipe=True, snap_img=True, live_img=True,
                 img_bytes=b"DIFFERENT")
    assert snapshot_matches_live(slot) is False


def test_identical_pages_with_a_recipe_still_grey_the_button(tmp_path):
    slot = _slot(tmp_path, recipe=True, snap_img=True, live_img=True)
    assert snapshot_matches_live(slot) is True


def test_a_changed_page_without_a_recipe_is_noticed_too(tmp_path):
    slot = _slot(tmp_path, recipe=False, snap_img=True, live_img=True,
                 img_bytes=b"DIFFERENT")
    assert snapshot_matches_live(slot) is False


@pytest.mark.parametrize("snap_img,live_img", [(True, False), (False, True)])
def test_images_on_one_side_only_are_not_a_difference(tmp_path, snap_img,
                                                      live_img):
    """A recipe-carrying chart's snapshot deliberately omits them, so their
    absence must not read as a changed chart."""
    slot = _slot(tmp_path, recipe=True, snap_img=snap_img, live_img=live_img)
    assert snapshot_matches_live(slot) is True


# ---- ruling 2: the pages that cannot come back ---------------------------
def test_the_at_risk_pages_are_found(tmp_path):
    slot = _slot(tmp_path, recipe=False, snap_img=False, live_img=True)
    at_risk = restore_would_lose_pages(slot)
    assert [p.name for p in at_risk] == [f"{STEM}_01.tif"]


def test_a_recipe_means_nothing_is_at_risk(tmp_path):
    """They can be redrawn, so removing them costs nothing."""
    slot = _slot(tmp_path, recipe=True, snap_img=False, live_img=True)
    assert restore_would_lose_pages(slot) == []


def test_a_snapshot_with_images_brings_its_own_back(tmp_path):
    slot = _slot(tmp_path, recipe=False, snap_img=True, live_img=True)
    assert restore_would_lose_pages(slot) == []


def test_no_pages_in_the_run_means_nothing_to_lose(tmp_path):
    slot = _slot(tmp_path, recipe=False, snap_img=False, live_img=False)
    assert restore_would_lose_pages(slot) == []


def test_no_snapshot_at_all_is_not_a_loss(tmp_path):
    live = tmp_path / "run5"
    live.mkdir()
    (live / f"{STEM}_01.tif").write_bytes(b"page")
    slot = ChartSlot(live_dir=live, snapshot_dir=live / "chart", stem=STEM,
                     suffixes=PROFILING_CHART_SUFFIXES)
    assert restore_would_lose_pages(slot) == []


# ---- the window says what he asked it to say -----------------------------
def test_the_warning_names_the_files_and_both_folders():
    """His words: the window "must ask the user to investigate the specific
    files in question to make an informed decision"."""
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._confirm_restore_losing_pages)
    assert "{names}" in src, "the files at risk must be listed by name"
    # Knut, beta.120 review: he asked for "so the following images would be
    # removed and can not be recreated", dropping the count — which also drops
    # the singular/plural pair, since the sentence no longer carries a number.
    # Checked against the extracted catalogue key rather than the source, since
    # the sentence is split across several source lines and a literal match
    # would break the next time the wrapping moves.
    import sys as _sys
    _sys.path.insert(0, ".")
    from scripts.i18n_extract import extract_keys
    joined = "\n".join(extract_keys())
    assert "the following images would be removed and can not be recreated" in joined
    assert "{count}" not in src
    assert "{run}" in src and "{stored}" in src, "both folders must be named"
    assert "look at both folders before you decide" in src


def test_the_two_buttons_say_what_they_do():
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._confirm_restore_losing_pages)
    assert "Restore chart files anyway" in src
    assert "Cancel and keep the current chart files" in src
    assert "What each button does" in src
    assert "setDefaultButton(keep)" in src, \
        "the safe choice is the one that keeps the pages"


def test_the_restore_asks_before_it_acts():
    from ui.measurement_target_bar import MeasurementTargetBar
    src = inspect.getsource(MeasurementTargetBar._on_restore_clicked)
    assert "_confirm_restore_losing_pages" in src
    assert (src.index("_confirm_restore_losing_pages")
            < src.index("restore_used_chart")), \
        "asking after restoring would be no use at all"


def test_the_warning_describes_the_slot_that_will_be_restored():
    """The warning and the restore must never mean different slots."""
    from ui.measurement_target_bar import MeasurementTargetController
    src = inspect.getsource(MeasurementTargetController.restore_slot_or_none)
    assert "is_verification" in src and "selected_run" in src
