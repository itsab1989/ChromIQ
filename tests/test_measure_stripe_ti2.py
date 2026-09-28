"""Strip-rect setup resolves the sibling .ti2 when handed a .ti1.

The authoritative per-page strip count lives in ``PASSES_IN_STRIPS2``, which
printtarg writes only into the .ti2. Most load paths hand TabMeasure a .ti2, but
reopening a saved run passes ``run.chart_ti1`` (a real .ti1). Before the fix that
made ``parse_passes_per_page`` return [] and the code fell back to the fragile
label-counting detector, which miscounts charts whose rotated caption sits in the
page margin (e.g. the A3 ColorMunki TC9.24 chart: 47 strips counted as 48).

These tests pin the .ti2-resolution so the robust uniform detector runs in the
reopen path too, while leaving the .ti2-given and no-sibling cases unchanged.
"""
from __future__ import annotations

import os
import shutil
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.resource_path import resource_path  # noqa: E402
from core.settings import DEFAULTS  # noqa: E402
from ui.tabs.tab_measure import TabMeasure  # noqa: E402

# A bundled single-page chart (47 strips, 940 patches) whose descriptive caption
# is printed down the right margin — the exact shape that fools the label counter.
_ASSET_STEM = "tests/fixtures/charts/prebuilt/pharmacist/rgb/colormunki/a3/tc924/tc924"
_EXPECTED_STRIPS = 47


@pytest.fixture(scope="module", autouse=True)
def _qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class _StubSettings:
    def __init__(self, **overrides):
        self._d = dict(DEFAULTS)
        self._d.update(overrides)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


@pytest.fixture
def tab():
    settings = _StubSettings()
    return TabMeasure(ArgyllRunner(settings), settings)


def _stage_run(dst_dir, stem="Proj"):
    """Copy the bundled chart into a run-like folder under a project stem."""
    ti1 = dst_dir / f"{stem}.ti1"
    ti2 = dst_dir / f"{stem}.ti2"
    tif = dst_dir / f"{stem}_01.tif"
    shutil.copy(resource_path(f"{_ASSET_STEM}.ti1"), ti1)
    shutil.copy(resource_path(f"{_ASSET_STEM}.ti2"), ti2)
    shutil.copy(resource_path(f"{_ASSET_STEM}_01.tif"), tif)
    return ti1, ti2, tif


def test_reopen_with_ti1_uses_uniform_detector(tab, tmp_path):
    """Passing the .ti1 (reopen path) still finds the .ti2 strip count → 47 strips."""
    ti1, _ti2, tif = _stage_run(tmp_path)
    tab._ti1_path = ti1            # main_window passes run.chart_ti1 on reopen
    tab._tiff_pages = [tif]
    tab._setup_stripe_rects()
    assert tab._strips_per_page == [_EXPECTED_STRIPS]
    assert len(tab._page_stripe_rects) == 1
    assert len(tab._page_stripe_rects[0]) == _EXPECTED_STRIPS


def test_given_ti2_directly_still_works(tab, tmp_path):
    """The common path (a .ti2 is handed in) is unchanged."""
    _ti1, ti2, tif = _stage_run(tmp_path)
    tab._ti1_path = ti2
    tab._tiff_pages = [tif]
    tab._setup_stripe_rects()
    assert tab._strips_per_page == [_EXPECTED_STRIPS]
    assert len(tab._page_stripe_rects[0]) == _EXPECTED_STRIPS


def test_ti1_without_sibling_ti2_falls_back(tab, tmp_path):
    """No sibling .ti2 → label fallback (no uniform per-page counts), as before."""
    ti1, ti2, tif = _stage_run(tmp_path)
    ti2.unlink()                  # remove the .ti2 so no count is available
    tab._ti1_path = ti1
    tab._tiff_pages = [tif]
    tab._setup_stripe_rects()
    # Fallback detector runs (single page), so no authoritative per-page counts.
    assert tab._strips_per_page == []
