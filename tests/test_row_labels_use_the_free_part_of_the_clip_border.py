"""Row labels may sit in the free part of the clip border: 1 mm clear of what
the border prints, never closer to the edge than "Clip" (Basti, 2026-10-25,
on Knut's forum post 149832; `docs/design/row_label_geometry.md` §R1.3 as
amended). Proved on Knut's own preset values, on the rendered page."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402
from PIL import Image                                          # noqa: E402

from workflow.layout_engine import instruments, raster         # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe        # noqa: E402

REPO = Path(__file__).resolve().parents[1]

#: Knut's "i1Pro-100x150mm-600p-5pages-Portrait-TEST" (forum 149832), the
#: values that decide this: an 11 mm clip border with two lines of branding,
#: row labels at 6 pt, Clip 2 mm, left margin 11 mm.
KNUT = dict(instrument="i1", paper="100x150", dpi=200, border=10.0,
            clip_border=True, clip_border_width_mm=11.0, clip_side="left",
            clip_content_mode="branding",
            clip_text="{project} - {rundescription} - {paper}\n"
                      "{instrument} - {patchcount} - {page} - {date} - {seed}",
            clip_text_font="JetBrains Mono", clip_text_size_mm=2.12,
            margin_left=11.0, margin_top=17.0, margin_right=5.0,
            margin_bottom=13.0, layout_mode="area_first", area_method="by_grid",
            area_cols=10, area_rows=12, show_row_indicators=True,
            indicator_size_mm=2.12, text_edge_clip_mm=2.0,
            use_instrument_margins=False, margins_explicit=True, pscale=0.95,
            sscale=0.6, helper_markers=True, helper_marker_edge_mm=2.0,
            helper_marker_len_mm=2.0, helper_markers_sides=False)


def _geom(**kw):
    r = LayoutRecipe.from_dict(dict(KNUT, **kw))
    return instruments.geom_from_build_kwargs(
        dict(r.build_kwargs(), area_target_count=600)), r


def test_the_labels_start_where_the_branding_ends_not_past_the_border():
    g, r = _geom()
    reach = raster.clip_content_reach_mm(g, dict(r.build_kwargs()))
    assert reach is not None and 5.0 < reach < 10.0
    assert g.row_label_floor == pytest.approx(reach, abs=0.01)
    assert g.row_label_floor < 11.0 - 1.0, "the labels still clear the border"
    # the margin he asked for is raised far less than the 15.5 mm before
    assert g.margin_l < 13.5


def test_never_closer_to_the_edge_than_clip():
    g, _r = _geom(text_edge_clip_mm=9.5)
    assert g.row_label_floor >= 9.5 - 1e-6


def test_an_empty_clip_border_leaves_the_labels_at_clip():
    g, _r = _geom(clip_content_mode="off")
    assert g.row_label_floor == pytest.approx(2.0, abs=0.01)


def test_unknown_content_still_clears_the_whole_border(monkeypatch):
    monkeypatch.setattr(raster, "clip_content_reach_mm", lambda *a, **k: None)
    g, _r = _geom()
    assert g.row_label_floor == pytest.approx(11.0, abs=0.01)


def _render(tmp_path, **kw):
    from workflow.layout_engine.chart import build_chart
    r = LayoutRecipe.from_dict(dict(KNUT, **kw))
    src = Path(__file__).parent / "data" / "knut_149832_test.ti1"
    ti1 = tmp_path / "c.ti1"
    shutil.copy(src, ti1)
    kwargs = dict(r.build_kwargs(), seed=1919062204, chart_date="2026-10-24")
    res = build_chart(ti1, tmp_path / "c", **kwargs)
    return np.asarray(Image.open(res.tiff_paths[0]).convert("L"))


def test_on_the_page_the_label_ink_is_at_least_1_mm_clear_of_the_branding(
        tmp_path):
    a = _render(tmp_path)
    mm = 25.4 / 200
    cols = np.nonzero((a[:, : int(20 / mm)] < 200).any(axis=0))[0]
    runs, start, prev = [], cols[0], cols[0]
    for c in cols[1:]:
        if c != prev + 1:
            runs.append((start, prev))
            start = c
        prev = c
    runs.append((start, prev))
    # the first run is the branding, the next one the row labels
    text_end = runs[0][1] * mm
    label_start = runs[1][0] * mm
    assert label_start - text_end >= 1.0 - mm, (text_end, label_start)
    assert label_start < 11.0, "the labels did not move into the free part"


def test_the_strip_letters_use_the_free_part_too():
    """Basti, 2026-10-25: the same rule for the strip letters. On Knut's
    preset X = -4.0 mm was held at -3.7 mm by the whole 11 mm border."""
    r = LayoutRecipe.from_dict(dict(KNUT, strip_label_offset_x_mm=-4.0))
    kw = dict(r.build_kwargs(), area_target_count=600)
    g = instruments.geom_from_build_kwargs(kw)
    shift = raster.strip_label_x_shift(g, kw)
    assert shift is not None and not shift.held, shift
    assert shift.used_mm == pytest.approx(-4.0, abs=0.1)


def test_unknown_content_holds_the_letters_off_the_whole_border():
    import dataclasses
    r = LayoutRecipe.from_dict(dict(KNUT, strip_label_offset_x_mm=-8.0))
    kw = dict(r.build_kwargs(), area_target_count=600)
    g = instruments.geom_from_build_kwargs(kw)
    free = raster.strip_label_x_shift(g, kw)
    whole = raster.strip_label_x_shift(
        dataclasses.replace(g, clip_content_reach_mm=-1.0), kw)
    assert free.left_mm > whole.left_mm
