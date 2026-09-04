"""The secondary notes in Expert Options must be READABLE — in all three
appearances, measured off the pixels they paint.

Basti, on screen, 4.1.5-beta.8: *"in create chart manual expert in sheet text
and [s]trip and row labels section under the neutral colorscheme some text is
not readable"*.

Four labels said ``color: palette(mid)``. TWO ARE LEFT, and they are the two
that were never explanation in the first place — both are values measured off
the chart on screen:

* ``text_preview`` — the "Preview:" line under **Sheet text**
* ``clip_dims_label`` — the clip-area readout next door

The other two went, and neither was deleted:

* ``_label_reach_note``, the paragraph naming each control's reach, was retired
  when the frame started saying the same thing by its SHAPE (B8-21 §4).
* ``_label_style_note``, the "saved with this chart" sentence, moved onto the
  ⓘ of every control in **Strip && row labels** on 2026-09-04 (Basti: *"the
  info text … directly inside the sections … i want that gone. You can fit it
  inside of a tooltip where it fits but not directly inside a section"*). It is
  still text a person has to be able to READ, so the check moved with it —
  ``test_a_note_moved_into_a_tooltip_is_still_readable`` in
  ``tests/test_the_notes_left_the_sections_for_the_tooltips.py`` measures it
  off the ⓘ dialog's own pixels in all three appearances, and the same file
  proves the sentence still reaches a reader at all.

``QPalette.Mid`` is what Fusion shades a FRAME with. Every appearance sets it a
hair from its own ground *deliberately*, which makes it the one role that
cannot carry a word. Measured on screen in the running app before the fix:
**1.25:1 in Light, 1.02:1 in Dark, 1.14:1 in Neutral** — invisible in all
three. Neutral is only where it was noticed; the reporter's own preference
file says ``appearance = neutral``.

WHY THIS FILE MEASURES INSTEAD OF ASSERTING A CONSTANT. A test that pins
``color == "#232323"`` passes happily the day the ground moves underneath it —
and this theme's ground HAS moved: ``NM_BG_PANEL`` and ``NM_BG_SURFACE`` were
collapsed onto ``NM_BG_WINDOW`` on 2026-09-02 and every ratio in
``ui/neutral_styles.py`` had to be recomputed. A ratio read off the painted
pixels survives that; a constant does not.

THE THRESHOLD IS 4.5:1 — WCAG 2.1 AA for normal text. These notes are 13 px
body text a person has to read to know where a setting lives, so
the large-text allowance (3:1) does not apply to them. It is a published
number rather than an opinion, and it is far enough above the 1.0-1.3:1 the
bug produced that no measurement noise can straddle it.

Nothing here calls ``qapp.setStyleSheet()`` — that re-polishes every widget the
suite has alive (CLAUDE.md: two 0.2 s tests became 29 s). The appearance is
painted onto the panel under test.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

#: WCAG 2.1 AA, normal text. See the module docstring.
MIN_RATIO = 4.5

#: A candidate ink must own this share of the label's NON-GROUND pixels before
#: it counts as a glyph core rather than an antialiasing blend.
#:
#: A share of the whole box does not work: ``clip_dims_label`` is one short
#: line in a 493 px-wide box, so its glyphs are under 1 % of it and a
#: box-relative floor rejected the real ink and reported 0.00:1 — a green-to-red
#: verdict produced by the measurement, not by the widget. Antialiasing lays a
#: ramp between ink and ground and the core is typically a quarter of the
#: glyph, so 6 % of the marked pixels is well inside every real stem and well
#: clear of the single-pixel tail.
INK_SHARE = 0.06

NOTES = ("text_preview", "clip_dims_label")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(rgb) -> float:
    r, g, b = (int(v) for v in rgb)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _ratio(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _ink_on_ground(host, widget):
    """``(ratio, ink, ground)`` read off what ``widget`` actually painted.

    Grabbed INSIDE ``host`` — the auto-filled panel — and cropped, never grabbed
    on its own. A transparent QLabel grabbed by itself paints Fusion's default
    ``#efefef`` instead of the appearance's ground, which silently turns the
    measurement into ink-against-a-ground-nobody-has: with that mistake in
    place, this file's own mutation run caught ``palette(mid)`` in Light and
    Neutral and MISSED it in Dark, because dark ink on a light default reads
    beautifully. Compositing inside the group box is the only way the ground is
    the one on screen.

    The ground is the colour the crop is mostly made of; the ink is the colour
    furthest from it in luminance that still owns :data:`INK_SHARE` of the
    marked pixels. Both come from the grab, so a rule that is present but does
    not reach the widget fails here exactly as it would on screen.
    """
    import numpy as np
    from PyQt6.QtCore import QPoint

    full = host.grab().toImage()
    # THE GRAB IS NOT IN LOGICAL PIXELS on a HiDPI screen — the suite runs
    # offscreen at 1.0, but a developer running this under cocoa gets 2.0 and
    # an unscaled rect would name the wrong quarter of the image.
    dpr = full.width() / max(1, host.width())
    top = widget.mapTo(host, QPoint(0, 0))
    img = full.copy(int(top.x() * dpr), int(top.y() * dpr),
                    max(1, int(widget.width() * dpr)),
                    max(1, int(widget.height() * dpr)))
    w, h = img.width(), img.height()
    assert w > 4 and h > 4, f"{widget.objectName() or widget} did not lay out"
    buf = img.constBits()
    buf.setsize(img.sizeInBytes())
    # QImage's 32-bit buffer is B,G,R,A in memory on a little-endian host, so
    # the last axis is REVERSED to get R,G,B. Luminance is 0.2126R + 0.7152G +
    # 0.0722B — it is not symmetric, and reading it channel-swapped quietly
    # moved every light-theme number here (#eeece8 read as #e8ecee, 13.60:1
    # where the running app measures 13.64:1).
    arr = np.frombuffer(buf, np.uint8).reshape(
        h, img.bytesPerLine() // 4, 4)[:, :w, 2::-1]
    flat = arr.reshape(-1, 3).astype(int)
    keys = flat[:, 0] * 65536 + flat[:, 1] * 256 + flat[:, 2]
    vals, counts = np.unique(keys, return_counts=True)
    ground_key = int(vals[counts.argmax()])
    ground = (ground_key >> 16, ground_key >> 8 & 0xFF, ground_key & 0xFF)
    marked = int(len(flat) - counts.max())
    floor = max(4, int(marked * INK_SHARE))
    best = (0.0, ground)
    for key, n in zip(vals.tolist(), counts.tolist()):
        if n < floor or key == ground_key:
            continue
        rgb = (key >> 16, key >> 8 & 0xFF, key & 0xFF)
        r = _ratio(rgb, ground)
        if r > best[0]:
            best = (r, rgb)
    return best[0], best[1], ground


def _panel_in(mode, qapp):
    """A real LayoutOptionsPanel wearing ``mode``, styled on ITSELF."""
    from PyQt6.QtWidgets import QWidget

    from ui import theme
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel

    sheet, make_palette = theme._APPEARANCE_STYLE[mode]
    panel = LayoutOptionsPanel(None, with_selectors=True)
    # The palette goes on every widget, not only the panel, so a disabled
    # control's Disabled/Text role is the theme's here too. Palettes are cheap;
    # an app-wide STYLESHEET is what CLAUDE.md forbids, and this is not that.
    #
    # WHAT IT STILL CANNOT DO, measured with the mutation below: Qt resolves
    # `palette(mid)` inside a stylesheet against the APPLICATION palette, not
    # the widget's, so a note put back on `palette(mid)` here paints Fusion's
    # default #b8b8b8 — which is 1.68:1 on the light ground and 1.53:1 on the
    # neutral one (caught), but perfectly legible on the dark one (missed).
    # The ratio check therefore cannot be the only guard, which is why
    # `test_a_note_never_asks_for_a_shading_role` exists and why the numbers in
    # the module docstring were taken from the RUNNING APP and not from here.
    pal = make_palette()
    panel.setPalette(pal)
    for child in panel.findChildren(QWidget):
        child.setPalette(pal)
    # THE GROUND HAS TO BE PAINTED BY SOMEBODY. Light and Neutral deliberately
    # carry no `QGroupBox { background }` QSS rule — the app fills a group box
    # from its palette instead, through `ui.widgets.GroupBoxSurfaceFilter`,
    # which `main.py` installs and the suite does not. Without a filler, a grab
    # in those two appearances comes back on Fusion's own #efefef, and dark ink
    # on a light default reads beautifully: measured here, that mistake caught
    # `palette(mid)` in Light and Neutral and MISSED it in Dark. One
    # auto-filled panel gives every transparent child the appearance's real
    # ground to composite onto, and Dark's group-box QSS still paints over it.
    panel.setAutoFillBackground(True)
    panel.setStyleSheet(sheet)
    # The appearance a component is HANDED, not one it measured for itself:
    # active_mode() reads the *application* palette, which this test must not
    # touch, so the mode is passed in explicitly the way apply_theme broadcasts
    # it. That also exercises the live-switch path, not just construction.
    panel.set_appearance(mode)
    panel._expert_frame.set_collapsed(False)
    # The clip-border group is hidden until the instrument reads in bands and
    # the border is on. A HIDDEN label grabs as a blank rectangle of Fusion's
    # own #efefef, which measures 0.00:1 and would fail this test for a reason
    # that has nothing to do with its ink — so put it on screen properly.
    panel.instr.setCurrentIndex(panel.instr.findData("i1"))
    idx = panel.clip_enable.findData("on")
    panel.clip_enable.setCurrentIndex(idx)
    panel._update_clip_visibility()
    panel.chart_text.setText("{project} - {date}")
    panel.clip_dims_label.setText("120.0 x 80.0 mm @ 600 dpi")
    panel.resize(620, 1600)
    panel.show()
    qapp.processEvents()
    return panel


@pytest.mark.parametrize("mode", ["light", "dark", "neutral"])
@pytest.mark.parametrize("note", NOTES)
def test_an_expert_note_reads_in_every_appearance(qapp, mode, note):
    panel = _panel_in(mode, qapp)
    try:
        lbl = getattr(panel, note)
        assert lbl.text().strip(), f"{note} painted nothing to measure"
        ratio, ink, ground = _ink_on_ground(panel, lbl)
        assert ratio >= MIN_RATIO, (
            f"{note} in {mode}: ink #{ink[0]:02x}{ink[1]:02x}{ink[2]:02x} on "
            f"ground #{ground[0]:02x}{ground[1]:02x}{ground[2]:02x} is "
            f"{ratio:.2f}:1 — under the {MIN_RATIO}:1 that 13 px body text "
            f"needs. The stylesheet asks for {lbl.styleSheet()!r}.")
    finally:
        panel.close()
        panel.deleteLater()
        qapp.processEvents()


@pytest.mark.parametrize("mode", ["light", "dark", "neutral"])
def test_a_note_never_asks_for_a_shading_role(qapp, mode):
    """The role, not only the result.

    A note could reach 4.5:1 by accident on one appearance's ground while still
    naming ``palette(mid)`` — the fault would then be one theme edit away from
    coming back, and the ratio test above would say nothing until it did.
    """
    panel = _panel_in(mode, qapp)
    try:
        for note in NOTES:
            qss = getattr(panel, note).styleSheet()
            assert "palette(mid)" not in qss, (
                f"{note} still asks for QPalette.Mid, the role Fusion shades a "
                f"FRAME with: {qss!r}")
    finally:
        panel.close()
        panel.deleteLater()
        qapp.processEvents()


def test_the_ink_is_named_per_appearance_and_not_folded(qapp):
    """A fourth appearance must not silently inherit Dark's note ink.

    ``theme.by_mode`` returns the Dark value for a mode it has never heard of
    (documented in ui/theme.py, measured in the beta-8 sweep), so what this can
    prove is the other half: that each of the three appearances the app SHIPS
    gets an ink of its own rather than one value folded across all of them.
    """
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel

    panel = LayoutOptionsPanel(None, with_selectors=True)
    try:
        inks = {m: panel._note_ink(m) for m in ("light", "dark", "neutral")}
        assert len(set(inks.values())) == 3, (
            f"two appearances share a note ink: {inks}")
        for mode, ink in inks.items():
            assert ink.startswith("#"), f"{mode} note ink is not a colour: {ink}"
    finally:
        panel.close()
        panel.deleteLater()
        qapp.processEvents()
