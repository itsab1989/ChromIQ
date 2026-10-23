"""The Measure tab's scan arrow points at a real strip, on the page shown.

Basti's screenshot, 2026-10-23 13:06 (agent 25's replay dry run of a
printtarg-made, paper-white, two-page ColorMunki chart: A B | C D, the pause
between pages on): at the pause after strip B the green arrow stood on page 1
to the right of strip B, on printtarg's rotated caption, where a strip C would
be.

Two things were wrong, and each test here fails on the code before the fix:

* **the strips were found on the caption.** `_detect_uniform_stripe_rects`
  took the widest run of "inked" columns as the patch block. A chart of very
  light patches has no such column except the caption's, so both strips were
  laid side by side on the caption (x 338 and 346 of a 402 px page) and every
  arrow of that chart pointed at the caption, not only at the pause. The block
  must now lie under the strip labels, or is found from them;
* **the arrow stayed up in the pause.** The reader holds with no strip armed,
  so an arrow on the page under review says "read this next" about a strip
  that is not next. It is put away for the pause, stays away through Continue
  until the engine has armed the next strip (so it never flashes back on page
  1 on its way to page 2), and comes back on whatever strip the engine arms.
"""
from __future__ import annotations

import json
import os
import shutil
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                    # noqa: E402
from PyQt6.QtWidgets import QApplication              # noqa: E402

from core.argyll_runner import ArgyllRunner           # noqa: E402
from core.resource_path import resource_path          # noqa: E402
from core.settings import AppSettings                 # noqa: E402

_FIX = "tests/fixtures/charts/paper_white_cm_2pages/white"
#: printtarg -iCM -p80x250 -r -t150 of 48 paper-white patches: 402 px wide,
#: strips A and B at x 0-330, the caption from x ~335 to the right edge.
_CAPTION_X = 334

STRIPS = [{"strip": s, "sheet": 1 if s in "AB" else 2, "read": False,
           "verifiable": True} for s in "ABCD"]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _stage(dst):
    for suffix in (".ti1", ".ti2", "_01.tif", "_02.tif"):
        shutil.copy(resource_path(_FIX + suffix), dst / f"white{suffix}")
    return dst / "white.ti2"


@pytest.fixture
def tab(qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    t = TabMeasure(ArgyllRunner(s), s)
    ti2 = _stage(tmp_path)
    t._ti1_path = ti2
    t._try_load_tiffs(ti2)
    mgr = t._manager
    written = []
    monkeypatch.setattr(mgr._runner, "write_stdin",
                        lambda text: written.append(json.loads(text)))
    mgr._engine_active = True
    mgr._page_pause_on = True
    mgr._engine_holds = True
    mgr._spot_mode = False
    mgr._guided_state = "disabled"
    mgr._session_strips = [dict(x) for x in STRIPS]
    mgr._loc_strip = {f"{s}{i}": s for s in "ABCD" for i in (1, 2)}
    mgr._unread_locs = set(mgr._loc_strip)
    mgr._padding_locs = set()
    mgr._chart_was_complete = False
    mgr._is_resume = False
    mgr._read_something = True
    t._session_live = True
    t._written = written
    yield t
    t._session_live = False


def _feed(mgr, ev):
    mgr._handle_engine_line(json.dumps(ev), lambda _line: None)


def _settle(ms=60):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.005)


def _ready(tab, strip):
    _feed(tab._manager, {"event": "strip_ready", "strip": strip,
                         "read": False, "all_done": False})
    _settle()


def _read(tab, strip):
    tab._manager._unread_locs -= {f"{strip}1", f"{strip}2"}


def _hold(tab, strip):
    _feed(tab._manager, {"event": "held", "strip": strip, "button": True})
    _settle()


def _arrow(tab):
    """(page index, strip rect) the arrow is drawn on, or None."""
    p = tab._preview
    if not p.scan_arrows_shown():
        return None
    return p.current_page(), p._stripe_rects[p._active_stripe]


# ---------------------------------------------------------------------------
# the strips of a paper-white chart are where the strips are
# ---------------------------------------------------------------------------
def test_a_paper_white_chart_has_its_strips_under_their_labels(tmp_path):
    from ui.tabs.tab_measure import _detect_uniform_stripe_rects
    _stage(tmp_path)
    for page in ("white_01.tif", "white_02.tif"):
        rects = _detect_uniform_stripe_rects(tmp_path / page, 2)
        assert len(rects) == 2, page
        a, b = rects
        # side by side, each a strip wide, and all of it left of the caption
        assert a.x() < 10 and a.width() > 140, (page, a)
        assert abs(b.x() - (a.x() + a.width())) <= 2, (page, a, b)
        assert b.x() + b.width() <= _CAPTION_X, (page, b)


def test_the_arrow_for_strip_b_is_on_strip_b_not_the_caption(tab):
    _ready(tab, "A")
    page, r = _arrow(tab)
    assert page == 0 and r.x() < 10
    _ready(tab, "B")
    page, r = _arrow(tab)
    assert page == 0
    assert 150 < r.x() and r.x() + r.width() <= _CAPTION_X, r


# ---------------------------------------------------------------------------
# the pause: no arrow, then page 2 with the arrow on C
# ---------------------------------------------------------------------------
def test_the_pause_shows_page_1_without_an_arrow(tab):
    _ready(tab, "B")
    _read(tab, "A"), _read(tab, "B")
    _hold(tab, "B")
    assert tab._page_pause_active()
    assert tab._preview.current_page() == 0       # page 1 stays, to review it
    assert _arrow(tab) is None


def test_paging_by_hand_in_the_pause_shows_no_arrow_on_either_page(tab):
    _ready(tab, "B")
    _read(tab, "A"), _read(tab, "B")
    _hold(tab, "B")
    tab._preview.show_page(1)
    _settle()
    assert _arrow(tab) is None
    tab._preview.show_page(0)
    _settle()
    assert _arrow(tab) is None


def test_continue_keeps_the_arrow_away_until_c_is_armed_on_page_2(tab):
    _ready(tab, "B")
    _read(tab, "A"), _read(tab, "B")
    _hold(tab, "B")
    tab._page_pause_continue_btn.click()
    assert tab._written[-1] == {"cmd": "goto", "strip": "C"}
    # the engine has not answered yet: no arrow back on B in the meantime
    _settle()
    assert _arrow(tab) is None
    _ready(tab, "C")
    page, r = _arrow(tab)
    assert page == 1 and r.x() < 10               # page 2, strip C


def test_reread_from_the_pause_brings_the_arrow_back_on_that_strip(tab):
    _ready(tab, "B")
    _read(tab, "A"), _read(tab, "B")
    _hold(tab, "B")
    tab._page_pause_reread_btn.click()
    assert tab._written[-1] == {"cmd": "goto", "strip": "B"}
    _ready(tab, "B")
    page, r = _arrow(tab)
    assert page == 0 and 150 < r.x() < _CAPTION_X
    # read again: the pause and its arrowless page come back
    _hold(tab, "B")
    assert tab._page_pause_active() and _arrow(tab) is None


def test_the_end_of_the_session_gives_the_arrows_back(tab):
    _ready(tab, "B")
    _read(tab, "A"), _read(tab, "B")
    _hold(tab, "B")
    tab._end_page_pause()
    assert tab._preview._scan_arrows_held is False


# ---------------------------------------------------------------------------
# without the pause: the turn to page 2 is one step
# ---------------------------------------------------------------------------
def test_without_the_pause_c_is_armed_straight_onto_page_2(tab):
    tab._manager._page_pause_on = False
    _ready(tab, "B")
    seen = []
    p = tab._preview
    orig = p._schedule_refresh

    def spy():
        # what a paint at this moment would show
        seen.append((p.current_page(), p.active_stripe_on_screen(),
                     p.scan_arrows_shown()))
        orig()

    p._schedule_refresh = spy
    _read(tab, "A"), _read(tab, "B")
    _ready(tab, "C")
    p._schedule_refresh = orig
    page, r = _arrow(tab)
    assert page == 1 and r.x() < 10
    # never "page 1 with an arrow on a strip index that is C's on page 2"
    assert all(not (pg == 0 and shown and act == 0) for pg, act, shown in seen), seen


# ---------------------------------------------------------------------------
# the arrow hangs BELOW a lone strip's letter (Basti, 2026-10-23: "the arrow
# covered the strip indicator of the last strip, but only of the very last")
# ---------------------------------------------------------------------------
def _label_ink_bottom(tif):
    """The last row of the first run of dark rows from the top: the bottom
    of the strip letters."""
    from PIL import Image
    im = Image.open(tif).convert("L")
    w, h = im.size
    px = im.load()

    def dark(y):
        return any(px[x, y] < 80 for x in range(w))
    top = next(y for y in range(h) if dark(y))
    y = top
    while dark(y + 1):
        y += 1
    return y


@pytest.mark.parametrize("tif", [
    # printtarg -iCM -p80x250, 36 patches: A B | C, page 2 holds strip C alone
    "tests/fixtures/charts/cm_one_strip_last_page/onestrip_02.tif",
    # the layout engine's 4x6 ColorMunki chart, page 4 holds strip J alone
    # (read without its sidecar, which is how a chart without one is shown)
    "tests/fixtures/charts/cm_one_strip_last_page/engine_one_strip_04.tif",
])
def test_a_page_with_one_strip_hangs_the_arrow_below_its_letter(tif):
    from pathlib import Path
    from ui.tabs.tab_measure import _detect_uniform_stripe_rects
    path = Path(resource_path(tif))
    rects = _detect_uniform_stripe_rects(path, 1)
    assert len(rects) == 1
    # "base" mode: the arrow is drawn from the rect top downwards
    assert rects[0].y() > _label_ink_bottom(path), (rects[0], _label_ink_bottom(path))
