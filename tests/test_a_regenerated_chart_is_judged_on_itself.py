"""A chart built on top of another must not be judged on the one it replaced.

**THE CACHE KEY WAS THE FILE NAMES.** `TabChart._worst_page_key` returned
*(the page TIFF paths, the .ti2 path)*, and a rebuild into the same run writes
`<name>_01.tif … _NN.tif` again, so the key never moved,
`_ensure_worst_page_cache` returned early, and every text notice on every chart
after the first was judged on the per-page margins of the chart it replaced.
It cleared only when the page COUNT changed or the run / target changed the
paths. **The function's own docstring claimed the opposite**: *"A new chart is a
new key, so the pages of the previous one can never judge this one's text."*

Two testers found it independently on beta 18, from opposite directions, and
the photographs are in `~/Desktop/ChromIQ-beta18-proof/`:

* `knut-sweep-preview-truth/R12-B-right-40mm.png`: a two-page chart built with
  Right = 6 mm, then Right = 40 and Generate pressed. The frame reads
  **40.2 mm**, the engine 40.159 and the app's own raster 40.13, and the red
  paragraph beside it still says *"the right margin leaves 1.7 mm … Raising
  “Right” … by about 2.8 mm"*. The reader did exactly what the message asked
  and got the identical message back.
* `knut-sweep-clipborder/`, group `P`: a three-page chart, the clip band moved
  from left to right and the right margin from 10 to 35 mm. The frame read
  **34.994**, the judgement used **10.017**, and raising the margin to 51 mm did
  not change one digit.

The key is now size plus `st_mtime_ns` per file. **Not mtime alone**:
`shutil.copy2` preserves it, and this project lost a day to exactly that shape
the week before.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from ui.tabs.tab_chart import TabChart                          # noqa: E402


class _Tab:
    """Just enough of the tab for the key: the two attributes it reads."""

    def __init__(self, tiffs, ti2):
        self._margin_tiffs = list(tiffs)
        self._margin_ti2 = ti2


def _chart(tmp_path: Path, body: bytes, pages: int = 2):
    tiffs = []
    for i in range(1, pages + 1):
        t = tmp_path / f"chart_{i:02d}.tif"
        t.write_bytes(body + bytes([i]))
        tiffs.append(t)
    ti2 = tmp_path / "chart.ti2"
    ti2.write_bytes(b"NUMBER_OF_SETS 4\n")
    (tmp_path / "chart.channels.json").write_text('{"layout": {}}',
                                                  encoding="utf-8")
    return _Tab(tiffs, ti2)


def test_the_key_moves_when_the_same_filenames_are_rewritten(tmp_path):
    """The exact route both testers took: Generate again into the same run.

    MUTATION: return `(tuple(str(t) for t in tiffs), str(ti2))` from
    `_worst_page_key` and this goes red.
    """
    tab = _chart(tmp_path, b"first chart" * 40)
    before = TabChart._worst_page_key(tab)
    time.sleep(0.01)
    for t in tab._margin_tiffs:
        t.write_bytes(b"second chart, a different sheet entirely" * 40)
    after = TabChart._worst_page_key(tab)
    assert before != after, (
        "a rebuild into the same run left the cache key unchanged, so the "
        "previous chart's per-page margins judge this one's text")


def test_the_key_moves_even_when_the_mtime_is_preserved(tmp_path):
    """`shutil.copy2` keeps the timestamp, so the timestamp cannot be the key.

    This project was bitten by exactly that the week before beta 19, on a
    different cache, which is why the size is in the key beside the stamp.

    MUTATION: drop `st_size` from `_file_stamp` and this goes red.
    """
    src = tmp_path / "src"
    src.mkdir()
    a = src / "a.tif"
    a.write_bytes(b"a" * 5000)
    tab = _chart(tmp_path, b"x" * 100, pages=1)
    before = TabChart._worst_page_key(tab)
    shutil.copy2(a, tab._margin_tiffs[0])          # same mtime, other bytes
    after = TabChart._worst_page_key(tab)
    assert before != after, (
        "copy2 preserved the mtime and the key did not move, which is the "
        "trap this key was rebuilt to avoid")


def test_the_sidecar_is_in_the_key_too(tmp_path):
    """An engine chart is measured from its `channels.json`, so a rewrite of
    that alone must invalidate the measurement.

    MUTATION: take the sidecar back out of `_worst_page_key` and this goes red.
    """
    tab = _chart(tmp_path, b"geometry" * 40)
    before = TabChart._worst_page_key(tab)
    (tmp_path / "chart.channels.json").write_text(
        '{"layout": {"dpi": 300, "patches": []}}', encoding="utf-8")
    assert TabChart._worst_page_key(tab) != before, (
        "the recorded geometry changed and the cached per-page measurement "
        "was kept")


def test_a_chart_that_did_not_change_keeps_its_measurement(tmp_path):
    """The other half: the cache must still BE a cache.

    Measuring every page of a chart is what a page turn would otherwise pay
    for, and it is why this key exists at all.
    """
    tab = _chart(tmp_path, b"unchanged" * 40)
    assert TabChart._worst_page_key(tab) == TabChart._worst_page_key(tab)


def test_the_docstring_describes_what_the_function_does(tmp_path):
    """The claim that was false is not allowed back.

    `_worst_page_key`'s docstring used to say *"A new chart is a new key, so
    the pages of the previous one can never judge this one's text"* while the
    key was the file NAMES, which a rebuild does not change. Three faults this
    week had that same shape, a guard asserting what it does not do, so the
    sentence is pinned to the mechanism that makes it true.
    """
    import inspect
    src = inspect.getsource(TabChart._worst_page_key)
    assert "st_mtime_ns" in src or "_file_stamp" in src, (
        "the key no longer carries each file's content stamp")
    assert "CONTENT" in src.upper(), (
        "the docstring no longer says the key is of the content")
