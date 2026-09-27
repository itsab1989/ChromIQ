"""B8-1571: the estimate's patch size is the one the chart will be drawn with.

Knut's 10 x 15 cm photo card, "i1Pro 100x150mm-150p-1page-Portrait-w7.5mm",
read "Patch size (mm) 7.49×7.37" on screen and "7.59×7.36" as the estimate,
with nothing marked. Both were true of different things. The estimate gave the
exact geometry. The on-screen column reads the first patch the engine
recorded, and `geometry.patch_rects_px` rounds each edge from its exact
position, so a 7.59 mm patch at 200 dpi is drawn 59 px wide in some columns and
60 in others; the first one is 59 (7.49 mm). That reading is deliberate and
pinned (`test_knut_preview_geometry`: it is what Knut measured with a ruler),
so the estimate now snaps the first slot of its own layout with the same
function at the chart's dpi, and after Generate the two columns say the same.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.resource_path import resource_path
from ui.tabs.tab_chart import KNUT_PRESETS, TabChart
from workflow.layout_engine import chart, instruments
from workflow.layout_engine.presets import LayoutRecipe

_PHOTO = [p for p in KNUT_PRESETS
          if getattr(p, "layout_recipe", None)
          and ("100x150mm" in p.name or "130x180mm" in p.name)]
# The first layout-engine preset of each other family (ColorMunki, CR30 and its
# honeycombs, i1Pro, i1Pro 3 Plus), so the rule is not photo-card only.
def _first_of_each_family():
    seen, out = set(), []
    for p in KNUT_PRESETS:
        if not getattr(p, "layout_recipe", None) or p in _PHOTO:
            continue
        fam = p.key.split("_")[4] if p.key.count("_") > 4 else ""
        hexa = bool(p.layout_recipe.get("hflag"))
        if fam in ("cm", "cr30", "i1", "p3") and (fam, hexa) not in seen:
            seen.add((fam, hexa))
            out.append(p)
    return out


_OTHERS = _first_of_each_family()


class _Panel:
    def __init__(self):
        self.estimate = None

    def set_estimate(self, **kw):
        self.estimate = kw

    def set_pitch_axis(self, *a, **k):
        pass

    def show_placeholder(self):
        pass

    def clear_estimate(self):
        self.estimate = None


class _Tab:
    def __init__(self):
        self._layout_info_panel = _Panel()


def _build(preset, tmp: Path):
    rec = LayoutRecipe.from_dict(dict(preset.layout_recipe))
    chart.build_chart(resource_path(preset.ti1_asset), tmp / "c",
                      **rec.build_kwargs())
    lay = json.loads((tmp / "c.strips.json").read_text(encoding="utf-8"))
    lay["recipe"] = rec.to_dict()
    (tmp / "c.channels.json").write_text(json.dumps({"layout": lay}),
                                         encoding="utf-8")
    return tmp / "c.ti2", rec


def _estimate(preset, rec, dpi):
    kw = rec.build_kwargs()
    kw["area_target_count"] = int(preset.patches)
    geom = instruments.geom_from_build_kwargs(kw)
    tab = _Tab()
    TabChart._predict_layout_info(tab, geom, rec.paper, 1,
                                  npat=int(preset.patches), dpi=dpi)
    est = tab._layout_info_panel.estimate
    return est["patch_w"], est["patch_h"], geom


def test_there_are_photo_cards():
    assert len(_PHOTO) >= 19


def test_the_reported_150p_card_agrees(tmp_path):
    p = next(p for p in _PHOTO if "100x150mm-150p-1page" in p.name)
    ti2, rec = _build(p, tmp_path)
    w, h, _pitch = TabChart._chart_patch_size_mm(ti2)
    ew, eh, geom = _estimate(p, rec, rec.dpi)
    assert round(geom.pwid, 2) == pytest.approx(7.59, abs=0.005)  # exact size
    assert round(w, 2) == pytest.approx(7.49, abs=0.005)          # first patch
    assert (ew, eh) == pytest.approx((w, h), abs=0.005)           # was 7.59


def test_without_a_dpi_the_estimate_is_the_exact_geometry(tmp_path):
    p = next(p for p in _PHOTO if "100x150mm-150p-1page" in p.name)
    rec = LayoutRecipe.from_dict(dict(p.layout_recipe))
    ew, _eh, geom = _estimate(p, rec, None)
    assert ew == pytest.approx(geom.pwid, abs=0.005)


@pytest.mark.parametrize("preset", _PHOTO + _OTHERS, ids=lambda p: p.key)
def test_on_screen_and_estimate_agree_after_generate(preset, tmp_path):
    ti2, rec = _build(preset, tmp_path)
    w, h, _pitch = TabChart._chart_patch_size_mm(ti2)
    ew, eh, _geom = _estimate(preset, rec, rec.dpi)
    assert (ew, eh) == pytest.approx((w, h), abs=0.005)


def test_the_manual_estimate_hands_over_the_charts_dpi():
    """The snapping only happens when a caller passes the dpi; Manual's
    estimate must, or the panel goes back to the exact size."""
    import inspect
    src = inspect.getsource(TabChart._refresh_layout_estimate)
    assert 'dpi=getattr(r, "dpi", None)' in src
