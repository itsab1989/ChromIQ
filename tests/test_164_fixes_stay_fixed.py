"""The #164 fixes that had no test of their own.

A review of the batch mutated each fix in turn and found eight that nothing
guarded — including two that were themselves defects an earlier review had
found. A fix nobody can break twice is worth more than a fix nobody tested, so
each one below is written so that removing the fix fails it.

Ordered as the fixes were made.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from core.resource_path import resource_path  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


# --- the overlay must describe the sheet, not a chart of its own -------------

def test_the_overlay_matches_what_the_renderer_actually_drew(qapp, tmp_path):
    """The overlay rebuilds the chart's geometry from its recipe — and
    `build_kwargs()` does not carry `area_target_count`, which the renderer
    injects from the .ti1 it is building. Every default recipe is area-first and
    sizes its patches to FILL the page with exactly that many, so without the
    count the overlay described a different chart: 19 dashes at a 15.8 mm pitch
    against the sheet's 285 at 1.0 mm.

    Survivable while the overlay was only ever a guide. Not survivable now that
    a matching overlay positively claims to BE the ink on the sheet.

    Compared against what the RENDERER drew, captured as it drew it — not
    against a second guess at the geometry.
    """
    from PyQt6.QtCore import QSettings

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    from workflow.layout_engine import chart as le_chart, geometry, papers
    from workflow.layout_engine.presets import default_recipe

    drawn: list[tuple] = []
    real = geometry.helper_marker_lines_mm

    def spy(*a, **kw):
        out = real(*a, **kw)
        drawn.append(tuple(out))
        return out

    rec = default_recipe("CM", "A4", mode="freehand")
    rec.helper_markers = True
    rec.helper_marker_edge_mm = 2.0
    rec.helper_marker_len_mm = 4.0
    rec.helper_marker_per_patch = 3

    import workflow.layout_engine.raster as raster_mod
    raster_mod.geometry.helper_marker_lines_mm = spy
    try:
        res = le_chart.build_chart(
            "tests/fixtures/charts/cm_a4_480p_2pages.ti1", tmp_path / "c",
            **rec.build_kwargs())
    finally:
        raster_mod.geometry.helper_marker_lines_mm = real
    assert drawn, "the renderer drew no markers to compare against"
    printed = sorted(drawn[0])

    Path(res.ti2_path).with_suffix(".channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq", "recipe": rec.to_dict(),
                    "seed": res.seed}}), encoding="utf-8")

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("manual")
    tab._margin_tiffs = [Path(res.tiff_paths[0])]
    tab._margin_ti2 = Path(res.ti2_path)
    lp = tab._manual_layout_panel
    lp.helper_markers_cb.setChecked(True)
    lp.helper_marker_edge.setValue(2.0)
    lp.helper_marker_len.setValue(4.0)
    lp.helper_marker_per_patch.setValue(3)

    lines, pending = tab._helper_marker_lines_frac()
    w_mm, h_mm = papers.dimensions_mm("A4")
    overlay = sorted((x0 * w_mm, y0 * h_mm, x1 * w_mm, y1 * h_mm)
                     for x0, y0, x1, y1 in lines)

    assert len(overlay) == len(printed), (
        f"the overlay draws {len(overlay)} dashes where the sheet has "
        f"{len(printed)}")
    worst = max((max(abs(a - b) for a, b in zip(o, p))
                 for o, p in zip(overlay, printed)), default=0.0)
    assert worst < 0.001, f"the overlay is up to {worst:.3f} mm off the ink"
    assert pending is False, (
        "an overlay identical to the sheet still called itself a proposal")


# --- an empty proposal is still a proposal ----------------------------------

def _painted_pixels(prev, lines, pending):
    """Non-white pixels the overlay puts on a white canvas."""
    import numpy as np
    from PyQt6.QtGui import QImage, QPainter

    img = QImage(420, 300, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    prev.set_helper_markers(lines, pending=pending)
    p = QPainter(img)
    prev._draw_helper_markers(p, 0.0, 420.0, 300.0)
    p.end()
    buf = img.constBits()
    buf.setsize(img.sizeInBytes())
    arr = np.array(np.frombuffer(buf, np.uint8).reshape(
        300, img.bytesPerLine() // 4, 4)[:, :420, :3], dtype=int)
    return int((arr.min(axis=2) < 240).sum())


def test_no_dashes_at_all_is_the_loudest_proposal(qapp):
    """Untick both edges and the proposal IS "nothing" — the case the sheet's
    own printed dashes contradict most flatly, because they are still on screen.
    The flag was being gated on there being lines to draw, which threw it away
    exactly then."""
    from ui.tiff_preview import TiffPreview

    prev = TiffPreview()
    assert _painted_pixels(prev, [], pending=True) > 0, (
        "an empty proposal drew nothing — the user is not told the next chart "
        "will have no markers")
    assert _painted_pixels(prev, [], pending=False) == 0, (
        "something was drawn when there was nothing to say")


def test_the_repaint_reaches_the_caption_with_no_lines(qapp, tmp_path):
    """…and the PAINT PATH has to call the painter at all.

    The flag surviving is only half the fix: the repaint asked "are there lines
    to draw?" before drawing anything, so an empty proposal was still silent.
    Both halves have to be exercised, which means going through a real page in
    a real widget rather than calling the painter by hand.
    """
    import numpy as np
    from PIL import Image

    from ui.tiff_preview import TiffPreview

    page = tmp_path / "page.tif"
    Image.new("RGB", (600, 850), (255, 255, 255)).save(page, dpi=(150, 150))

    prev = TiffPreview()
    prev.resize(500, 700)
    prev.load_tiff([page])
    prev.show()
    qapp.processEvents()          # …or the widget has nothing painted to grab

    def accent_pixels() -> int:
        img = prev.grab().toImage()
        w, h = img.width(), img.height()
        buf = img.constBits()
        buf.setsize(img.sizeInBytes())
        a = np.array(np.frombuffer(buf, np.uint8).reshape(
            h, img.bytesPerLine() // 4, 4)[:, :w, :3], dtype=int)
        b, g, r = a[..., 0], a[..., 1], a[..., 2]
        return int((((r - g) > 60) & (r > 150) & (b > g)).sum())

    prev.set_helper_markers([], pending=False)
    qapp.processEvents()
    quiet = accent_pixels()
    prev.set_helper_markers([], pending=True)
    qapp.processEvents()
    loud = accent_pixels()
    assert loud > quiet + 50, (
        f"an empty proposal painted nothing on a real page ({quiet} → {loud} "
        f"accent pixels)")


def test_the_caption_says_which_kind_of_proposal_it_is(qapp):
    from ui.tiff_preview import TiffPreview

    prev = TiffPreview()
    prev.set_helper_markers([], pending=True)
    assert prev._helper_markers_pending is True
    prev.set_helper_markers([(0.1, 0.1, 0.2, 0.1)], pending=True)
    assert prev._helper_markers_pending is True


def test_the_caption_shortens_before_it_elides(qapp):
    """Three steps, and the middle one matters: at a width where the full
    sentence will not fit, the user should get a shorter SENTENCE, not the long
    one cut off at "…press Gene". Measuring ink cannot tell those apart, so the
    choice is made in a function of its own and checked here."""
    from PyQt6.QtGui import QFont, QFontMetricsF

    from ui.tiff_preview import TiffPreview

    prev = TiffPreview()
    prev.set_helper_markers([(0.1, 0.5, 0.2, 0.5)], pending=True)
    font = QFont()
    font.setBold(True)
    fm = QFontMetricsF(font)

    full = prev._pending_caption_text(fm, 4000.0)
    assert "Generate Chart" in full, "the roomy case lost the instruction"

    short = prev._pending_caption_text(
        fm, fm.horizontalAdvance(full) + 16 - 1)
    assert short != full, "no shorter form was used when the long one did not fit"
    assert "…" not in short and "..." not in short, (
        f"the long caption was elided instead of shortened: {short!r}")

    tiny = prev._pending_caption_text(fm, 60.0)
    # An elide is the last resort, and it must actually shorten. (Which of the
    # two sentences gets elided is not observable: the elide branch is only
    # reached when even the short one does not fit, and at that width both come
    # out as a couple of letters. So it is not asserted — a test line that
    # cannot fail is worse than no line.)
    assert len(tiny) < len(short), "nothing shorter was available for a tiny pane"


@pytest.mark.parametrize("width", [1200.0, 420.0, 260.0, 150.0, 90.0])
def test_the_caption_never_runs_off_the_pane(qapp, width):
    """*"t on this sheet yet — press Gene"* is worse than no caption at all."""
    import numpy as np
    from PyQt6.QtGui import QImage, QPainter

    from ui.tiff_preview import TiffPreview

    prev = TiffPreview()
    prev.set_helper_markers([(0.1, 0.5, 0.2, 0.5)], pending=True)
    img = QImage(int(width) + 40, 200, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    prev._draw_helper_markers(p, 0.0, width, 200.0)
    p.end()
    buf = img.constBits()
    buf.setsize(img.sizeInBytes())
    arr = np.array(np.frombuffer(buf, np.uint8).reshape(
        200, img.bytesPerLine() // 4, 4)[:, :int(width) + 40, :3], dtype=int)
    # The caption's white plate sits in the top-left; nothing it draws may reach
    # past the page width it was given.
    ink = np.where((arr.min(axis=2) < 240).any(axis=0))[0]
    assert len(ink) == 0 or ink.max() <= width, (
        f"the caption reached x={ink.max()} on a {width:.0f} px page")


# --- the branding ceiling ---------------------------------------------------

def _sweep(raster, band_px: int, dpi: int) -> None:
    for scale in (100.0, 400.0, 5000.0, 50000.0):
        raster.render_clip_strip(
            "branding", width_px=band_px, height_px=band_px * 3, dpi=dpi,
            text="Knut Larsson", image_scale=scale)


@pytest.mark.parametrize("band_px,dpi", [(260, 300), (1417, 600), (4535, 1200)])
def test_no_scale_can_blow_the_branding_up_until_it_throws(band_px, dpi):
    """The Scale box runs to 50 000 % — it was built for blowing a small logo up
    — and multiplying a solved font size by that asked Pillow for a 257-megapixel
    glyph. It refused, and the refusal came out of a Qt slot while the user was
    typing in a spin box."""
    from workflow.layout_engine import raster

    import warnings

    from PIL import Image

    # THE RESCUE MUST NOT BE NEEDED. The try/except added alongside the ceiling
    # catches the bomb and returns a blank band, so a test that only asks "did
    # it raise?" passes with the ceiling raised a hundredfold — it measures the
    # safety net, not the fix. Watch the rescue itself instead.
    rescued: list[str] = []
    real_warning = raster.log.warning
    raster.log.warning = lambda *a, **k: rescued.append(str(a[0] if a else ""))
    try:
        _sweep(raster, band_px, dpi)
    finally:
        raster.log.warning = real_warning
    assert not rescued, (
        f"the ceiling let it through and the rescue had to catch it: {rescued}")

    for scale in (100.0, 400.0, 5000.0, 50000.0):
        # WARNINGS AS ERRORS. Without this the try/except added alongside the
        # ceiling catches the bomb and the band comes back blank — so the test
        # passed with the ceiling raised a hundredfold, measuring the safety net
        # instead of the fix. Pillow warns long before it refuses; the ceiling's
        # job is that it never gets that far.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = raster.render_clip_strip(
                "branding", width_px=band_px, height_px=band_px * 3, dpi=dpi,
                text="Knut Larsson", image_scale=scale)
        assert img.size == (band_px, band_px * 3)


def test_the_ceiling_leaves_ordinary_scales_alone():
    """A cap that clamps a value somebody might actually use is a bug of its
    own, so the working range has to keep responding.

    Only up to the point where the block outgrows the band — past that the ink
    goes DOWN, because what leaves the band is cropped, exactly as an oversized
    imported image is. That is the design, not the ceiling.
    """
    import numpy as np

    from workflow.layout_engine import raster

    def ink(scale):
        img = raster.render_clip_strip(
            "branding", width_px=1417, height_px=4251, dpi=600,
            text="Knut Larsson", image_scale=scale)
        return int((np.asarray(img.convert("L")) < 200).sum())

    half, normal, double = ink(50.0), ink(100.0), ink(200.0)
    assert half < normal < double, (
        f"scaling stopped working in the normal range: {half} / {normal} / "
        f"{double}")
    assert ink(400.0) != normal, "400 % renders the same as 100 %"


def test_a_branding_that_cannot_be_drawn_leaves_the_band_blank(monkeypatch):
    """…rather than taking the window with it. The handler that promises this
    called a logger the module did not have, so it raised `NameError` on the one
    path that was already going wrong."""
    import numpy as np

    from workflow.layout_engine import raster

    def boom(*_a, **_kw):
        raise MemoryError("no room")

    monkeypatch.setattr(raster, "_vwordmark", boom)
    img = raster.render_clip_strip("branding", width_px=260, height_px=1200,
                                   dpi=300, text="Knut")
    arr = np.asarray(img.convert("L"))
    assert arr.min() > 250, "the band is not blank"


def test_the_module_has_the_logger_its_handlers_use():
    """Both rescue handlers in this module log. Neither could."""
    from workflow.layout_engine import raster

    assert getattr(raster, "log", None) is not None


# --- the panel says when the two tick boxes cancel each other out ------------

@pytest.mark.parametrize("markers,tb,sides,warn", [
    (True, True, True, False),
    (True, True, False, False),
    (True, False, True, False),
    (True, False, False, True),
    (False, False, False, False),
    (False, True, True, False),
])
def test_the_panel_warns_only_when_nothing_will_print(qapp, markers, tb, sides,
                                                      warn):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel

    p = LayoutOptionsPanel(with_selectors=True)
    p._expert_frame.set_collapsed(False)
    p.helper_markers_cb.setChecked(markers)
    p.helper_markers_top_bottom.setChecked(tb)
    p.helper_markers_sides.setChecked(sides)
    shown = p.helper_markers_edge_warning.isVisibleTo(p)
    assert shown is warn, (
        f"markers={markers} top/bottom={tb} sides={sides}: warning "
        f"{'shown' if shown else 'hidden'}, expected the opposite")


# --- the panel does not drive the column into horizontal scrolling -----------

def test_the_marker_group_is_not_the_widest_thing_in_expert_options(qapp):
    """Two tick boxes on one line made this group 547 px against 472 for the
    next widest, which pushes the whole right-hand column into horizontal
    scrolling and clips the second label. The panel has been here before: the
    marker tick box's own label was shortened for exactly this reason."""
    from PyQt6.QtWidgets import QGroupBox

    from ui.dialogs.layout_options_panel import LayoutOptionsPanel

    p = LayoutOptionsPanel(with_selectors=True)
    p._expert_frame.set_collapsed(False)
    p.resize(520, 2200)
    p.show()

    widths = {g.title(): g.sizeHint().width()
              for g in p.findChildren(QGroupBox) if g.title()}
    markers = widths.get("Ruler helper markers", 0)
    others = max(w for t, w in widths.items()
                 if t not in ("Ruler helper markers", "Expert Options"))
    assert markers <= others, (
        f"the ruler-marker group is {markers} px, wider than every other group "
        f"({others} px) — Expert Options will scroll sideways")


# --- Preferences measures the clip band on the right paper -------------------

def test_a_panel_without_a_paper_selector_follows_its_recipe(qapp):
    """It reported an A4 clip band to somebody working on A3."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from workflow.layout_engine.presets import default_recipe

    p = LayoutOptionsPanel()          # no selectors — the Preferences copy
    seen = {}
    for paper in ("A4", "A3"):
        r = default_recipe("i1", paper, mode="clip")
        r.clip_content_mode = "notes"
        p.set_recipe(r)
        p._refresh_clip_preview()
        seen[paper] = p.clip_dims_label.text()
    assert seen["A4"] != seen["A3"], (
        f"both papers reported the same clip band: {seen['A4']!r}")
    assert "289" in seen["A4"] and "412" in seen["A3"], seen
