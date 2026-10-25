"""The row labels' own rotation, "Row indicators only" -> Rotation (Basti,
2026-10-25). A recipe without the key prints exactly what it printed; a
turned label is measured, placed and checked by the layout engine, so the
band, the margin, the preview and the printed page agree.
`docs/design/row_label_geometry.md` §R10."""
from __future__ import annotations

import dataclasses
import os
import random
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402
from PIL import Image                                          # noqa: E402

from workflow.layout_engine import instruments                # noqa: E402
from workflow.layout_engine.chart import build_chart          # noqa: E402
from workflow.layout_engine.presets import (LayoutRecipe,     # noqa: E402
                                            default_recipe)

ANGLES = (0, 90, 180, 270)


def _ti1(path: Path, n: int = 48) -> Path:
    rnd = random.Random(n)
    rows = "\n".join(f"{i + 1} {rnd.uniform(0, 100):.4f} {rnd.uniform(0, 100):.4f}"
                     f" {rnd.uniform(0, 100):.4f} 50 50 50" for i in range(n))
    path.write_text(
        'CTI1\n\nDESCRIPTOR "Argyll Calibration Target chart information 1"\n'
        'ORIGINATOR "test"\nAPPROX_WHITE_POINT "95.05 100 108.9"\n'
        'COLOR_REP "iRGB"\n\nNUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n'
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}\nEND_DATA\n")
    return path


def _build(tmp: Path, r: LayoutRecipe, tag: str):
    d = tmp / tag
    d.mkdir()
    kw = r.build_kwargs()
    kw["seed"], kw["chart_date"] = 7, "2026-02-02"
    res = build_chart(_ti1(d / "c.ti1"), d / "c", **kw)
    return res, instruments.geom_from_build_kwargs(dict(kw)), d


# ---- the recipe ---------------------------------------------------------
def test_round_trip_and_nothing_written_at_zero():
    r = LayoutRecipe()
    assert r.row_indicator_rotation == 0
    assert "row_indicator_rotation" not in r.to_dict()
    assert "row_indicator_rotation" not in r.build_kwargs()
    for deg in (90, 180, 270):
        t = dataclasses.replace(r, row_indicator_rotation=deg)
        assert t.to_dict()["row_indicator_rotation"] == deg
        assert LayoutRecipe.from_dict(t.to_dict()).row_indicator_rotation == deg
        kw = t.build_kwargs()
        assert kw["row_indicator_rotation"] == deg
        assert LayoutRecipe.from_build_kwargs(kw).row_indicator_rotation == deg
    assert LayoutRecipe.from_dict({}).row_indicator_rotation == 0


def test_a_stray_value_draws_as_upright():
    kw = dict(default_recipe("CR30", "A4").build_kwargs(),
              row_indicator_rotation=45)
    assert instruments.geom_from_build_kwargs(kw).row_label_rotation == 0


@pytest.mark.parametrize("inst,paper", [("CR30", "A4"), ("SS", "A4"),
                                        ("CR30", "Letter"), ("SS", "A3")])
def test_without_the_key_the_geometry_is_todays(inst, paper):
    r = default_recipe(inst, paper)
    d = {k: v for k, v in r.to_dict().items() if k != "row_indicator_rotation"}
    a = instruments.geom_from_build_kwargs(LayoutRecipe.from_dict(d).build_kwargs())
    b = instruments.geom_from_build_kwargs(
        LayoutRecipe.from_dict(dict(d, row_indicator_rotation=0)).build_kwargs())
    assert a == b and a.row_label_rotation == 0


# ---- the geometry, every angle, several instruments and papers ----------
@pytest.mark.parametrize("inst,paper", [("CR30", "A4"), ("SS", "A4"),
                                        ("CR30", "Letter"), ("SS", "A3"),
                                        ("CM", "A4")])
def test_the_band_follows_the_rotation(inst, paper):
    base = dataclasses.replace(default_recipe(inst, paper),
                               show_row_indicators=True)
    g = {deg: instruments.geom_from_build_kwargs(dataclasses.replace(
        base, row_indicator_rotation=deg).build_kwargs()) for deg in ANGLES}
    assert g[0].rlwi > 0
    # upside down takes the same width as upright; on its side, the ink
    # across (the type's height) and not the label's length
    assert g[180].rlwi == pytest.approx(g[0].rlwi)
    assert g[90].rlwi == pytest.approx(g[270].rlwi, abs=0.05)
    assert g[90].rlwi < g[0].rlwi
    for deg in ANGLES:
        # the margin always holds the band; the floor does not move
        assert g[deg].margin_l >= g[deg].row_label_floor + g[deg].rlwi + 1.0 - 1e-6
        assert g[deg].row_label_floor == pytest.approx(g[0].row_label_floor)


@pytest.mark.parametrize("deg", ANGLES)
@pytest.mark.parametrize("inst,paper", [("CR30", "A4"), ("SS", "A4"),
                                        ("CM", "Letter")])
def test_the_printed_labels_stay_in_their_band_and_their_row(tmp_path, inst,
                                                            paper, deg):
    r = dataclasses.replace(default_recipe(inst, paper),
                            show_row_indicators=True, dpi=150,
                            row_indicator_rotation=deg)
    res, g, _d = _build(tmp_path, r, f"{inst}{deg}")
    im = Image.open(res.tiff_paths[0])
    mm = 25.4 / im.info["dpi"][0]
    ink = np.asarray(im.convert("L")) < 128
    x_floor = int(g.row_label_floor / mm) - 1
    from workflow import overhang
    x_patch = int(overhang.patch_box(res.tiff_paths[0], 0).left / mm)
    band = ink[:, x_floor:x_patch - int(0.6 / mm)]
    cols = np.where(band.any(axis=0))[0]
    assert cols.size, "no row label ink in the band"
    # never closer to the paper edge than the floor, never on the patches
    assert ink[:, :max(0, x_floor - 1)].sum() == 0 or g.lbord > 0
    left_of_patches = ink[:, x_patch - int(0.6 / mm):x_patch - 1]
    assert left_of_patches.sum() == 0, "label ink within 0.6 mm of the patches"


def test_a_wide_margin_moves_only_the_label_pixels_and_never_the_ti2(tmp_path):
    """With a left margin wide enough for every rotation, turning the labels
    changes nothing but the labels: the patches, their positions and the .ti2
    chartread reads are those of the upright chart."""
    base = dataclasses.replace(default_recipe("CR30", "A4"),
                               show_row_indicators=True, dpi=150,
                               margin_left=30.0, margins_explicit=True)
    out = {}
    for deg in ANGLES:
        res, g, d = _build(tmp_path, dataclasses.replace(
            base, row_indicator_rotation=deg), f"w{deg}")
        ti2 = "\n".join(l for l in (d / "c.ti2").read_text("latin-1").splitlines()
                        if not l.startswith("CREATED "))
        out[deg] = (np.asarray(Image.open(res.tiff_paths[0]).convert("L")),
                    ti2, g)
    a0, t0, g0 = out[0]
    x_patch = int(g0.margin_l / (25.4 / 150))
    for deg in (90, 180, 270):
        a, t, g = out[deg]
        assert t == t0, f"{deg}°: the .ti2 changed"
        assert g.margin_l == pytest.approx(g0.margin_l)
        diff = np.argwhere(a != a0)
        assert diff.size, f"{deg}°: nothing was turned"
        assert diff[:, 1].max() < x_patch, f"{deg}°: pixels changed past the margin"


def test_a_turned_auto_label_keeps_inside_its_row():
    from workflow.layout_engine import raster
    g = instruments.geom_from_build_kwargs(dataclasses.replace(
        default_recipe("SS", "A4"), show_row_indicators=True,
        row_indicator_rotation=90).build_kwargs())
    size = raster.effective_row_label_size_mm(g, 300, "JetBrains Mono", 0.0)
    px = max(6, round(size * 300 / 25.4))
    length = raster._widest_row_label_px(px, "JetBrains Mono", False, False,
                                         "", 0) * 25.4 / 300
    assert length <= (g.plen + g.pspa) * raster.ROW_LABEL_PITCH_FRAC + 0.1


def test_the_panel_and_the_preferences_carry_it():
    import inspect
    from core.settings import DEFAULTS, INDICATOR_STYLE_KEYS
    from ui.dialogs import layout_options_panel as P
    from ui.dialogs import settings_dialog as S
    assert DEFAULTS["row_indicator_rotation"] == 0
    assert INDICATOR_STYLE_KEYS["row_indicator_rotation"] == "row_indicator_rotation"
    assert "row_indicator_rotation" in P._LABEL_STYLE_FIELDS
    src = inspect.getsource(P.LayoutOptionsPanel)
    assert 'QGroupBox(tr("Row indicators only")' in src
    assert "r.row_indicator_rotation = int(" in src
    assert "—" not in P.ROW_ROTATION_HELP
    assert 's.set("row_indicator_rotation"' in inspect.getsource(S)
