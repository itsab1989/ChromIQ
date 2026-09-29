"""B8-385 — "Show only measured patches" in the two modes that do not read
strips.

`ui/tabs/tab_measure.py::_update_engine_read_map` is the only thing that tells
the preview which strips have been read, and it was called from exactly two
places, both on the strip path (`_on_session_map` and `_on_strip_measured`).
Neither `_on_chart_measured` (the engine's XY and CHART modes, a whole sheet at
once) nor `_on_patch_measured` (spot mode, one patch at a time) reached it, so
in those two modes every strip stayed unread for the whole measurement and the
blank covered the sheet under everything they drew.

DRIVEN ON SCREEN FIRST, in a real window, before anything was changed
(`scripts/drive_b385_the_blank_sheet.py`,
`~/Desktop/ChromIQ-beta22-proof/b384-and-b385/`):

* chart mode, a 240-patch chart on three sheets: the read map was
  ``{0..6: False}`` at the start of the session and **still ``{0..6: False}``
  after the whole chart had been reported**;
* spot mode: the read map was ``{}`` for the whole session, and stayed ``{}``
  after 32 patches of strips A and B had been read one at a time.

**AND ONE CLAIM IN THE REGISTER WAS TOO STRONG**, which the photographs
corrected: in SPOT mode the sheet is not blank, because each patch's split is
drawn on top of the blank as it arrives. What is true in both modes is that no
strip is ever marked read, so every measured patch sits on blanked ground on
all four sides and the chart's own ink between the patches never comes back.
In CHART mode nothing at all appears until the read ends, because that is when
the one event arrives.

WHEN A STRIP COUNTS AS READ, and it is the same rule in both modes: when the
chart's geometry has a box for every one of its patches and each of those has
been reported. It is the same thing strip mode means by "read", it needs no
count from the engine, and it cannot flicker, because the set of reported
patches only grows while a chart is loaded.
"""
from __future__ import annotations

import os

import pytest
from PIL import Image
from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PAGE_W, PAGE_H = 620, 760
PATCH_W, PATCH_H = 60, 64
PITCH_X, PITCH_Y = 74, 78
COLS, ROWS = 4, 6
LEFT, TOP = 60, 120
#: the spacer band between two rows of a column, printed ink like any other
SPACER = 10

#: Column 0's spacers are navy and every other column's are black, so a pixel
#: that survives the blank says WHICH column it came from with no geometry to
#: get wrong. Nothing about the fix depends on the colours.
NAVY = (20, 20, 200)
BLACK = (0, 0, 0)
PATCH = (230, 60, 200)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _boxes(cols=COLS):
    """{loc: rect} for one page, "A1" downwards in column A, then "B1"…"""
    out = {}
    for c in range(cols):
        letter = chr(ord("A") + c)
        for r in range(ROWS):
            out[f"{letter}{r + 1}"] = QRect(LEFT + c * PITCH_X,
                                            TOP + r * PITCH_Y,
                                            PATCH_W, PATCH_H)
    return out


def _strip_rects(boxes):
    """One rect per column, as `engine_strip_rects_from_sidecar` builds them."""
    out = []
    for x in sorted({b.x() for b in boxes.values()}):
        cb = [b for b in boxes.values() if b.x() == x]
        out.append(QRect(x, min(b.y() for b in cb), PATCH_W,
                         max(b.y() + b.height() for b in cb)
                         - min(b.y() for b in cb)))
    return out


def _page(tmp_path, boxes, name="page.tif"):
    path = tmp_path / name
    if path.exists():
        return path
    im = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    px = im.load()
    for ci, x0 in enumerate(sorted({b.x() for b in boxes.values()})):
        cb = sorted((b for b in boxes.values() if b.x() == x0),
                    key=lambda b: b.y())
        colour = NAVY if ci == 0 else BLACK
        for k in range(len(cb) - 1):
            for y in range(cb[k].y() + cb[k].height(), cb[k + 1].y()):
                for x in range(x0, x0 + PATCH_W):
                    px[x, y] = colour
    for b in boxes.values():
        for y in range(b.y(), b.y() + b.height()):
            for x in range(b.x(), b.x() + b.width()):
                px[x, y] = PATCH
    im.save(path)
    return path


class _Settings:
    def __init__(self, extra=None):
        self._d = {"appearance": "dark", "chartread_engine": "chromiq"}
        self._d.update(extra or {})

    def get(self, key, default=None):
        return self._d.get(key, default)

    def set(self, key, value):
        self._d[key] = value


def _tab(qapp, tmp_path, monkeypatch, pages=1):
    """A real Measure tab with a real chart page under a real preview."""
    from core.argyll_runner import ArgyllRunner
    from ui.tabs.tab_measure import TabMeasure
    s = _Settings()
    tab = TabMeasure(ArgyllRunner(s), s)
    monkeypatch.setattr(tab, "_current_mode", lambda: "manual")
    boxes = _boxes()
    page = _page(tmp_path, boxes)
    tab._patch_boxes = [dict(boxes) for _ in range(pages)]
    if pages > 1:
        # the second sheet carries the NEXT strips, "E1"… onwards, at the same
        # places: a sheet's local strip indexes start again at 0, which is the
        # collision this fix had to avoid making visible.
        tab._patch_boxes[1] = {
            f"{chr(ord(loc[0]) + COLS)}{loc[1:]}": r
            for loc, r in boxes.items()}
    tab._page_stripe_rects = [_strip_rects(boxes) for _ in range(pages)]
    tab._strips_per_page = [COLS] * pages
    tab._preview.resize(700, 860)
    tab._preview.load_tiff([page] * pages)
    qapp.processEvents()
    tab._preview.set_page_patch_boxes({p: list(tab._patch_boxes[p].values())
                                       for p in range(pages)})
    tab._preview.set_stripe_rects(_strip_rects(boxes))
    return tab, boxes


def _patch(loc):
    return {"loc": loc, "xyz": [45, 45, 45], "exyz": [46, 45, 44], "de": 0.7}


def _strips(letters):
    return [{"strip": s, "sheet": 1, "read": False, "verifiable": True}
            for s in letters]


def _read_map(tab):
    return dict(tab._preview._stripe_read_map)


# ---------------------------------------------------------------------------
# the map itself
# ---------------------------------------------------------------------------
def test_a_whole_chart_read_marks_the_strips_it_covered(qapp, tmp_path,
                                                        monkeypatch):
    """XY / CHART mode: one event carries the sheet, and every strip of it is
    read when it lands.

    Driven through the manager's own signal, which is the seam the engine
    speaks through; everything from there on is the shipped path.

    MUTATION: drop the `_note_patches_read(placed)` call from
    `_on_chart_measured` and this goes red.
    """
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    tab._spot_session = False
    tab._manager.session_map.emit(_strips("ABCD"))
    qapp.processEvents()
    assert _read_map(tab) == {0: False, 1: False, 2: False, 3: False}, (
        "the fixture starts with something already read")

    tab._manager.chart_measured.emit({"patches": [_patch(l) for l in boxes]})
    qapp.processEvents()
    assert _read_map(tab) == {0: True, 1: True, 2: True, 3: True}


def test_a_strip_is_read_only_once_every_patch_of_it_is(qapp, tmp_path,
                                                        monkeypatch):
    """SPOT mode: patch by patch, and a strip earns the mark at its last patch.

    This is the "it must not flicker" half: a half-read strip is not read, so
    nothing turns on and off again as the reader moves down a column.

    MUTATION: count a strip as read as soon as ONE of its patches arrives
    (`have.get(s, 0) >= 1`) and this goes red on the half-read assertion.
    """
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    tab._spot_session = True
    tab._manager.session_map.emit(_strips("ABCD"))
    qapp.processEvents()
    mine = [f"A{r + 1}" for r in range(ROWS)]
    for loc in mine[:-1]:
        tab._manager.patch_measured.emit(_patch(loc))
    qapp.processEvents()
    assert _read_map(tab)[0] is False, (
        f"a strip with {len(mine) - 1} of its {len(mine)} patches read was "
        "called read")

    tab._manager.patch_measured.emit(_patch(mine[-1]))
    qapp.processEvents()
    assert _read_map(tab)[0] is True, "the last patch did not finish the strip"
    assert _read_map(tab)[1] is False, "an untouched strip was marked read"


def test_a_strip_that_has_been_read_stays_read(qapp, tmp_path, monkeypatch):
    """The set only grows, so the picture cannot go backwards.

    MUTATION: rebuild `_engine_patch_read` from the event instead of adding to
    it (`self._engine_patch_read = set(locs)`) and this goes red.
    """
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    tab._spot_session = True
    tab._manager.session_map.emit(_strips("ABCD"))
    qapp.processEvents()
    for r in range(ROWS):
        tab._manager.patch_measured.emit(_patch(f"A{r + 1}"))
    qapp.processEvents()
    assert _read_map(tab)[0] is True
    for r in range(ROWS):
        tab._manager.patch_measured.emit(_patch(f"B{r + 1}"))
    qapp.processEvents()
    assert _read_map(tab)[0] is True, "strip A un-read itself while B was read"
    assert _read_map(tab)[1] is True


def test_the_map_describes_the_page_on_screen(qapp, tmp_path, monkeypatch):
    """The map is keyed by the strip's LOCAL index on its sheet, so it means
    something different on every page.

    Every sheet's first strip is index 0. Reading sheet 1's first strip may not
    un-blank sheet 2's, and paging must re-point the map the way it re-points
    the strip rects.

    MUTATION: drop the `if pg != page: continue` filter from
    `_update_engine_read_map` and this goes red.
    """
    tab, boxes = _tab(qapp, tmp_path, monkeypatch, pages=2)
    tab._spot_session = True
    tab._manager.session_map.emit(_strips("ABCDEFGH"))
    qapp.processEvents()
    for r in range(ROWS):
        tab._manager.patch_measured.emit(_patch(f"A{r + 1}"))
    qapp.processEvents()
    assert _read_map(tab)[0] is True, "sheet 1's first strip is not read"

    tab._preview.show_page(1)
    tab._on_preview_page_changed(1)
    qapp.processEvents()
    assert _read_map(tab)[0] is False, (
        "reading the first strip of sheet 1 marked the first strip of sheet 2")


def test_a_changed_read_map_asks_for_a_repaint(qapp, tmp_path, monkeypatch):
    """`set_stripe_read_map` decides what the blank covers and scheduled no
    repaint, which every caller happened to hide: each one followed it with a
    `set_patch_overlay` that scheduled one of its own. Paging to another sheet
    is a caller that does not (B8-385).

    MUTATION: drop the `_schedule_refresh()` from `set_stripe_read_map` and
    this goes red.
    """
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    pv = tab._preview
    pv.set_stripe_read_map({0: False, 1: False})
    pv._refresh_timer.stop()
    pv.set_stripe_read_map({0: False, 1: False})
    assert not pv._refresh_timer.isActive(), (
        "the same map again asked for a repaint that changes nothing")
    pv.set_stripe_read_map({0: True, 1: False})
    assert pv._refresh_timer.isActive(), (
        "the map changed and the widget was never asked to repaint")


def test_the_strip_map_still_comes_from_the_engine_in_strip_mode(
        qapp, tmp_path, monkeypatch):
    """The path that always worked still works: what the session map says a
    strip is, it is, with no patch of it reported at all."""
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    tab._spot_session = False
    tab._manager.session_map.emit(
        [{"strip": "A", "sheet": 1, "read": True, "verifiable": True},
         {"strip": "B", "sheet": 1, "read": False, "verifiable": True}])
    qapp.processEvents()
    assert _read_map(tab)[0] is True and _read_map(tab)[1] is False


# ---------------------------------------------------------------------------
# the DEFAULT path: a chart that already has its measurement
# ---------------------------------------------------------------------------
def _cgats(path, boxes, *, measured: bool):
    """A real .ti2 (design, with SAMPLE_LOC) or .ti3 (measured) for *boxes*.

    Real files, parsed by the real reader: the thing under test is whether the
    tab learns what the measurement holds, and a fake reader handed the answer
    would prove only that the fake works.
    """
    locs = sorted(boxes)
    head = "CTI3" if measured else "CTI2"
    fields = ("SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"
              if measured else
              "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z")
    lines = [head, "", 'DESCRIPTOR "synthetic"',
             f"NUMBER_OF_FIELDS {len(fields.split())}", "BEGIN_DATA_FORMAT",
             fields, "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(locs)}",
             "BEGIN_DATA"]
    for i, loc in enumerate(locs, start=1):
        g = 20.0 + (i % 7) * 10.0
        xyz = (g * 0.9642, g, g * 0.8249)
        if measured:
            lines.append(f"{i} {g:.2f} {g:.2f} {g:.2f} "
                         f"{xyz[0]:.4f} {xyz[1]:.4f} {xyz[2]:.4f}")
        else:
            lines.append(f'{i} "{loc}" {g:.2f} {g:.2f} {g:.2f} '
                         f"{xyz[0]:.4f} {xyz[1]:.4f} {xyz[2]:.4f}")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_a_measurement_already_on_disk_is_read_with_no_session_at_all(
        qapp, tmp_path, monkeypatch):
    """**THE DEFAULT PATH, AND THE ONE A USER MEETS (round 23).**

    Open a project whose chart has been measured, tick "Show only measured
    patches", and the read map has never been filled by anything: there is no
    session. Round 23 photographed the result, a wholly blank sheet under a
    window reading *"Progress: 100.0 %"*.

    "Show overlay from existing measurement" ships OFF, so the split overlay
    cannot be the answer either: what the measurement holds has to be read for
    its patch LOCATIONS whether or not anything is drawn from it.

    Driven on screen before and after, on a 240-patch chart with its own .ti3
    (`scripts/drive_b385_the_default_path.py`): the read map was `{}` and the
    preview 45.9 % paper white; it is now `{0..6: True}` and 13.3 %.

    MUTATION: drop the `_note_measurement_on_disk()` call from
    `_apply_active_view_settings` and this goes red.
    """
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    ti2 = _cgats(tmp_path / "chart.ti2", boxes, measured=False)
    ti3 = _cgats(tmp_path / "chart.ti3", boxes, measured=True)
    tab._ti1_path = ti2
    monkeypatch.setattr(tab, "_existing_ti3_for_chart", lambda: ti3)
    tab._m_overlay_cb.setChecked(False)          # as the app ships
    tab._m_only_measured.setChecked(True)
    qapp.processEvents()

    assert _read_map(tab) == {0: True, 1: True, 2: True, 3: True}, (
        "a chart whose every patch has been measured is still blanked: "
        f"{_read_map(tab)}")
    assert not tab._preview._patch_overlay, (
        "the split overlay was drawn, and the tick box for it is off")


def test_a_half_measured_chart_on_disk_shows_only_what_it_holds(
        qapp, tmp_path, monkeypatch):
    """The same path, with a measurement that stops halfway: the strips it
    covers come back and the others stay blank."""
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    half = {k: v for k, v in boxes.items() if k[0] in "AB"}
    ti2 = _cgats(tmp_path / "chart.ti2", boxes, measured=False)
    ti3 = _cgats(tmp_path / "chart.ti3", half, measured=True)
    tab._ti1_path = ti2
    monkeypatch.setattr(tab, "_existing_ti3_for_chart", lambda: ti3)
    tab._m_only_measured.setChecked(True)
    qapp.processEvents()
    assert _read_map(tab) == {0: True, 1: True, 2: False, 3: False}


def test_loading_another_chart_forgets_the_first_ones_patches(
        qapp, tmp_path, monkeypatch):
    """The locations belong to the chart they were read from.

    MUTATION: drop the `self._engine_patch_read = set()` from
    `_setup_stripe_rects` and this goes red.
    """
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    tab._spot_session = True
    tab._manager.session_map.emit(_strips("ABCD"))
    for r in range(ROWS):
        tab._manager.patch_measured.emit(_patch(f"A{r + 1}"))
    qapp.processEvents()
    assert _read_map(tab)[0] is True
    tab._tiff_pages = []                 # a new chart, with no pages yet
    tab._setup_stripe_rects()
    assert not tab._engine_patch_read, (
        "the patches of the last chart are still counted against the next one")


# ---------------------------------------------------------------------------
# and what the user actually sees
# ---------------------------------------------------------------------------
def _ink(img, want):
    """How many device pixels of *img* carry the colour *want*, near enough."""
    n = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if (abs(c.red() - want[0]) < 40 and abs(c.green() - want[1]) < 40
                    and abs(c.blue() - want[2]) < 40):
                n += 1
    return n


def _picture(tab, qapp):
    tab._preview.show()
    qapp.processEvents()
    tab._preview._update_display()
    qapp.processEvents()
    pm = tab._preview._img_label.pixmap()
    return pm.toImage() if pm is not None else None


def test_the_blank_lifts_off_a_strip_the_reading_has_finished(qapp, tmp_path,
                                                              monkeypatch):
    """**THE THING A USER SEES**, and the reason the feature exists.

    "Show only measured patches" blanks every UNREAD strip to paper white. With
    the read map never updated, the whole sheet stayed blanked in both of these
    modes: the chart's own ink between the patches of a finished strip never
    came back, whatever had been read.

    Column A's spacers are printed navy and every other column's black, so the
    count below cannot be satisfied by ink from a neighbouring column.

    MUTATION: drop the `_note_patches_read([loc])` call from
    `_on_patch_measured` and this goes red: the navy count stays 0.
    """
    tab, boxes = _tab(qapp, tmp_path, monkeypatch)
    tab._spot_session = True
    tab._manager.session_map.emit(_strips("ABCD"))
    qapp.processEvents()
    tab._preview.set_show_only_measured(True)
    qapp.processEvents()
    blank = _picture(tab, qapp)
    assert blank is not None
    assert _ink(blank, NAVY) == 0, (
        "the fixture already shows column A's ink before anything was read")

    for r in range(ROWS):
        tab._manager.patch_measured.emit(_patch(f"A{r + 1}"))
    qapp.processEvents()
    after = _picture(tab, qapp)
    assert after is not None
    navy = _ink(after, NAVY)
    assert navy > 20, (
        "the strip whose every patch has been read is still blanked: its "
        f"printed spacers show {navy} device pixels")
    assert _ink(after, BLACK) < navy, (
        "an unread column's ink came back too, so the blank is not following "
        "the read map at all")
