"""What an FD-9 sheet carries besides its patches, marks and arrow (4.3.25).

* THE PAGE LABEL (F5): a small line at the top left, where it has always
  been (the owner's final ruling, 2026-11-04), naming the project, the run
  and the page ("FD9-test · run 2 · page 1 of 3"). Turned 180 degrees like
  the clip border, so it reads the same way as the clip border text: upside
  down on screen with the arrow pointing up. Printed on every sheet of a
  chart with several sheets, with the clip border on or off; there is no
  option for it.
* THE FD-9 CLIP BORDER (F12): a smaller version of ChromIQ's clip border in
  the trailing band, in the content the person chooses (the Notes box by
  default: wordmark, colour bar, patch count, instrument, paper, date, the
  lines to write on, page N/M), turned the same way. It is OFF by default (`FD9_CLIP_BORDER_DEFAULT`): the owner's
  rule is that it may only be on by default once lessbones has confirmed on
  real sheets that it does not disturb the measurement.

Both are drawn as a one-bit mask in the chart's black ink, exactly like the
marks, and every page that carries them goes through the detector check
(`workflow.fd9.sheet_check`) before anything is written.

Placement, measured on synthetic scans (report of 2026-11-04): the band
starts 2 mm below the later of the bottom marks and the last patch row,
keeps at least 10 mm from each side and is at most 14 mm tall, ending at
least 6 mm before the trailing edge.
"""
from __future__ import annotations

#: THE ONE DEFAULT for the FD-9 clip border. Off until lessbones confirms on
#: real sheets (several papers, every page) that it does not disturb the
#: measurement; then this goes to True, and nothing else changes.
FD9_CLIP_BORDER_DEFAULT = False

#: The label's text height, where its box starts (from the left and the
#: leading edge, as in 4.3.24) and how far short of the arrow it must end, in
#: mm.
LABEL_HEIGHT_MM = 2.4
LABEL_LEFT_MM = 8.0
LABEL_TOP_MM = 10.0
LABEL_ARROW_CLEAR_MM = 10.0
#: The clip band: tallest it may be, how far from each side, from the marks
#: and patches before it, and from the trailing edge.
CLIP_MAX_HEIGHT_MM = 14.0
CLIP_SIDE_MM = 10.0
CLIP_GAP_MM = 2.0
CLIP_EDGE_MM = 6.0
CLIP_MIN_HEIGHT_MM = 6.0


def page_label_text(project: str, run: str, page: int, pages: int) -> str:
    """"project · run N · page N of M", leaving out what is not known. The
    sheet's own text is English, like every ChromIQ chart's record strip."""
    parts = []
    if str(project or "").strip():
        parts.append(str(project).strip())
    run = str(run or "").strip()
    if run:
        parts.append(run if not run.isdigit() else f"run {run}")
    if pages > 1:
        parts.append(f"page {page} of {pages}")
    return " · ".join(parts)


def _font(size_px: int):
    from PIL import ImageFont
    return ImageFont.load_default(size=max(6, int(size_px)))


def _fit(text: str, font, width_px: int) -> str:
    """*text*, shortened with an ellipsis at the front part (the project
    name) until it fits *width_px*; the page part is what must survive."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("1", (4, 4)))
    if d.textlength(text, font=font) <= width_px:
        return text
    head, sep, tail = text.partition(" · ")
    if not sep:
        while text and d.textlength(text + "…", font=font) > width_px:
            text = text[:-1]
        return text + "…"
    while head and d.textlength(head + "…" + sep + tail, font=font) > width_px:
        head = head[:-1]
    out = (head + "…" + sep + tail) if head else tail
    if d.textlength(out, font=font) > width_px:
        return _fit(tail, font, width_px) if tail != text else out
    return out


def label_mask(size, dpi, text):
    """A one-bit image of the sheet size with *text* at the top left, turned
    180 degrees, or None for no text. Never wider than the room before the
    arrow; a long project name is shortened, the page is kept."""
    from PIL import Image, ImageDraw
    if not text:
        return None
    mm = dpi / 25.4
    width, _height = size
    font = _font(round(LABEL_HEIGHT_MM * mm))
    room = int(width / 2 - (LABEL_LEFT_MM + LABEL_ARROW_CLEAR_MM) * mm)
    text = _fit(text, font, room)
    probe = ImageDraw.Draw(Image.new("1", (4, 4)))
    x0, y0, x1, y1 = probe.textbbox((0, 0), text, font=font)
    tile = Image.new("1", (x1 - x0 + 2, y1 - y0 + 2), 0)
    ImageDraw.Draw(tile).text((1 - x0, 1 - y0), text, font=font, fill=1)
    tile = tile.rotate(180)
    out = Image.new("1", size, 0)
    out.paste(tile, (round(LABEL_LEFT_MM * mm), round(LABEL_TOP_MM * mm)))
    return out


def clip_band_mm(page_doc, paper_mm):
    """(x0, y0, x1, y1) of the clip band in mm, or None when the sheet has
    no room for one."""
    width, height = paper_mm
    marks = page_doc["fiducials_mm"]
    rows = page_doc["rows"]
    patch_h = page_doc["patch_mm"][1]
    last_bottom = rows[-1][0]["centre_mm"][1] + patch_h / 2
    mark_bottom = max(y for _x, y in marks) + 1.5
    top = max(last_bottom, mark_bottom) + CLIP_GAP_MM
    bottom = min(top + CLIP_MAX_HEIGHT_MM, height - CLIP_EDGE_MM)
    if bottom - top < CLIP_MIN_HEIGHT_MM:
        return None
    return (CLIP_SIDE_MM, top, width - CLIP_SIDE_MM, bottom)


def clip_artwork(band_mm, dpi, *, mode="notes", ctx=None, text="",
                 font_family="Inter", text_size_mm=0.0, image_path="",
                 image_rotation=0, image_scale=100.0, image_offset_x_mm=0.0,
                 image_offset_y_mm=0.0):
    """The FD-9 clip border as an RGB image the size of *band_mm*, and where
    it goes ((x, y) in px). The artwork is ChromIQ's own clip border
    (`raster.render_clip_strip`) in the content the person chose, the Notes
    box by default (the owner's ruling, 2026-11-04: the same default as the
    i1Pro's), turned 180 degrees: the engine draws a clip border as a tall
    strip reading up it (90 degrees), and another 90 lays it across the
    trailing band, upside down with the arrow up, the right way up for the
    person holding the trailing end."""
    from workflow.layout_engine.raster import render_clip_strip
    mm = dpi / 25.4
    x0, y0, x1, y1 = (round(v * mm) for v in band_mm)
    w, h = x1 - x0, y1 - y0
    strip = render_clip_strip(
        mode or "notes", width_px=h, height_px=w, dpi=dpi, text=text or "",
        font_family=font_family or "Inter", image_path=image_path or "",
        ctx=ctx, image_rotation=int(image_rotation or 0),
        image_scale=float(image_scale or 100.0),
        image_offset_x_mm=float(image_offset_x_mm or 0.0),
        image_offset_y_mm=float(image_offset_y_mm or 0.0),
        text_size_mm=float(text_size_mm or 0.0))
    art = strip.convert("RGB").rotate(90, expand=True)
    if art.size != (w, h):
        art = art.resize((w, h))
    return art, (x0, y0)


#: A pixel at least this close to white in every channel is paper.
PAPER_LEVEL = 250


def artwork_ink(art):
    """A one-bit mask of the artwork's non-paper pixels."""
    import numpy as np
    from PIL import Image
    a = np.asarray(art.convert("RGB"))
    return Image.fromarray((a.min(axis=2) < PAPER_LEVEL).astype(np.uint8) * 255
                           ).convert("1")


def artwork_runs(art, xy, colours=12):
    """The artwork as horizontal runs of one colour each, for the vector
    PDF, which draws rectangles: [((x0, y, x1, y + 1), (r, g, b)), ...] in
    page pixels. The colours are reduced to *colours* first, so a line of
    anti-aliased text is a few runs and not one per shade."""
    import numpy as np
    pal = art.convert("RGB").quantize(colors=colours, dither=0)
    idx = np.asarray(pal)
    palette = pal.getpalette()[:3 * colours]
    ink = np.asarray(artwork_ink(art), dtype=bool)
    out = []
    ox, oy = xy
    for y in np.nonzero(ink.any(axis=1))[0]:
        row, keep = idx[y], ink[y]
        x = 0
        n = len(row)
        while x < n:
            if not keep[x]:
                x += 1
                continue
            c = row[x]
            x0 = x
            while x < n and keep[x] and row[x] == c:
                x += 1
            rgb = tuple(palette[3 * int(c):3 * int(c) + 3])
            out.append(((ox + x0, oy + int(y), ox + x, oy + int(y) + 1), rgb))
    return out


def runs_of(mask):
    """The one-bit *mask* as horizontal runs (x0, y, x1, y + 1), for the
    vector PDF, which draws rectangles."""
    import numpy as np
    arr = np.asarray(mask, dtype=bool)
    runs = []
    ys = np.nonzero(arr.any(axis=1))[0]
    for y in ys:
        row = arr[y].astype(np.int8)
        edges = np.diff(np.concatenate(([0], row, [0])))
        starts = np.nonzero(edges == 1)[0]
        ends = np.nonzero(edges == -1)[0]
        runs.extend((int(a), int(y), int(b), int(y) + 1)
                    for a, b in zip(starts, ends))
    return runs
