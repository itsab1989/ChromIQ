"""Every font ChromIQ opens for Pillow is laid out with BASIC (beta 11, RB-6).

Pillow picks RAQM where FriBiDi is installed (Basti's Mac, via Homebrew) and
BASIC everywhere else, so the same preset laid out a fraction of a millimetre
differently on two machines. Basti, 2026-10-05: *"ok pin basic for beta 11"*.
`core.pil_font.load_font` is the one door; this file makes sure nothing in
product code walks round it.
"""
from __future__ import annotations

import ast
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parents[1]

#: Shipped Python. scripts/ are drivers and props (no shipped asset is drawn
#: with Pillow there); tests/ may ask Pillow anything.
PRODUCT = ["core", "ui", "workflow", "data", "main.py"]
THE_HELPER = ROOT / "core" / "pil_font.py"

#: Names that open a FreeType font with Pillow's machine-dependent default.
FORBIDDEN = {"truetype", "FreeTypeFont"}


def _product_files():
    for entry in PRODUCT:
        p = ROOT / entry
        yield from ([p] if p.is_file() else sorted(p.rglob("*.py")))


def _offences(path: Path, root: Path = ROOT) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
                "ImageFont"):
            for a in node.names:
                if a.name in FORBIDDEN or a.name == "*":
                    out.append(f"{path.relative_to(root)}:{node.lineno} "
                               f"imports {a.name} from PIL.ImageFont")
        if isinstance(node, ast.Call):
            f = node.func
            name = (f.attr if isinstance(f, ast.Attribute)
                    else f.id if isinstance(f, ast.Name) else None)
            if name in FORBIDDEN:
                out.append(f"{path.relative_to(root)}:{node.lineno} "
                           f"calls {name}(...)")
    return out


def test_product_code_opens_fonts_only_through_load_font():
    found = []
    for path in _product_files():
        if path.resolve() == THE_HELPER.resolve():
            continue
        found += _offences(path)
    assert not found, (
        "Open Pillow fonts with core.pil_font.load_font, which pins the "
        "BASIC layout; ImageFont.truetype on its own lays text out with RAQM "
        "wherever FriBiDi happens to be installed:\n  " + "\n  ".join(found))


def test_the_guard_sees_a_direct_call(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("from PIL import ImageFont\n"
                   "f = ImageFont.truetype('x.ttf', 12)\n"
                   "from PIL.ImageFont import FreeTypeFont\n", encoding="utf-8")
    assert len(_offences(bad, tmp_path)) == 2


def test_the_helper_pins_basic_even_where_raqm_is_the_default():
    from core.pil_font import load_font
    font = str(ROOT / "assets" / "fonts" / "Inter-VariableFont_opsz,wght.ttf")
    assert load_font(font, 12).layout_engine == ImageFont.Layout.BASIC
    # A variant keeps the engine of the font it copies.
    assert (load_font(font, 12).font_variant(size=20).layout_engine
            == ImageFont.Layout.BASIC)


def test_the_chart_fonts_are_basic():
    from workflow.layout_engine import raster
    from workflow import tiff_metadata
    for family in raster.FONTS:
        for bold, italic in ((False, False), (True, False), (False, True)):
            f = raster._font(24, family, bold=bold, italic=italic)
            assert getattr(f, "layout_engine",
                           ImageFont.Layout.BASIC) == ImageFont.Layout.BASIC, (
                family, bold, italic)
    f = tiff_metadata._pick_font(18)
    assert getattr(f, "layout_engine",
                   ImageFont.Layout.BASIC) == ImageFont.Layout.BASIC
