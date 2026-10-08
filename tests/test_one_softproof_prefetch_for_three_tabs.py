"""Beta 12 (found in review C): each tab started its own background
soft-proof prefetch of the same chart.

Create Chart, Print Chart and Measure each hold a TiffPreview of the same
pages, and each one's `_prefetch_softproofs` started a thread decoding every
page and looking every colour up, though cctiff was asked only once. Now one
run per chart + profile chain + print colour/intent serves all three; what is
filled (and therefore the pixels and the toggle) is unchanged.
"""
from __future__ import annotations

import os
import threading
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui import tiff_preview as T  # noqa: E402
from workflow import print_preview as PP  # noqa: E402


@pytest.fixture
def worker(monkeypatch):
    """A prefetch worker that records each start and runs until released or
    stopped, so 'running' is a state the test controls."""
    starts = []
    release = threading.Event()

    def fake(pages, colour, intent, bin_dir, stop, **_kw):
        starts.append((tuple(pages), colour, intent, stop))
        while not (release.is_set() or stop.is_set()):
            release.wait(0.01)

    monkeypatch.setattr(T, "_prefetch_worker", fake)
    monkeypatch.setattr(T, "_PREFETCH", T._SharedPrefetch())
    yield SimpleNamespace(starts=starts, release=release)
    release.set()


@pytest.fixture
def chart(tmp_path):
    pages = []
    for i in (1, 2, 3):
        p = tmp_path / f"chart_0{i}.tif"
        p.write_bytes(b"page %d" % i)
        pages.append(p)
    prof = tmp_path / "chart.icc"
    prof.write_bytes(b"icc")
    plan = PP.PreviewPlan(kind=PP.KIND_RAW, profile=prof)
    return pages, plan, tmp_path / "bin"


def _preview(pages, selected=("raw", "")):
    """A stand-in carrying only what `_prefetch_softproofs` reads."""
    return SimpleNamespace(_pages=[(p, 0) for p in pages],
                           _print_selected=selected, _prefetch_sig=None)


def _ask(preview, plan, bin_dir):
    T.TiffPreview._prefetch_softproofs(preview, plan, bin_dir)


def _wait_done(run_count, worker):
    import time
    end = time.time() + 10
    while time.time() < end:
        if all(not r["thread"].is_alive()
               for r in T._PREFETCH._runs.values() if r["thread"]):
            return
        time.sleep(0.01)


def test_three_tabs_on_one_chart_start_one_prefetch(worker, chart):
    pages, plan, b = chart
    tabs = [_preview(pages) for _ in range(3)]
    for t in tabs:
        _ask(t, plan, b)
    assert len(worker.starts) == 1
    run = next(iter(T._PREFETCH._runs.values()))
    assert run["owners"] == {id(t) for t in tabs}


def test_one_tab_moving_on_does_not_stop_the_others(worker, chart, tmp_path):
    pages, plan, b = chart
    tabs = [_preview(pages) for _ in range(3)]
    for t in tabs:
        _ask(t, plan, b)
    stop = worker.starts[0][3]
    other = tmp_path / "other_01.tif"
    other.write_bytes(b"x")
    other2 = tmp_path / "other_02.tif"
    other2.write_bytes(b"y")
    tabs[0]._pages = [(other, 0), (other2, 0)]
    _ask(tabs[0], plan, b)
    assert len(worker.starts) == 2               # its own new chart
    assert not stop.is_set()                     # the shared run goes on
    for t in tabs[1:]:
        t._pages = [(other, 0), (other2, 0)]
        _ask(t, plan, b)
    assert stop.is_set()                         # nobody wants it any more
    assert len(worker.starts) == 2               # and they joined tab 0's


def test_a_different_profile_or_intent_is_its_own_run(worker, chart, tmp_path):
    pages, plan, b = chart
    _ask(_preview(pages, ("raw", "")), plan, b)
    _ask(_preview(pages, ("through", "p")), plan, b)
    prof2 = tmp_path / "other.icc"
    prof2.write_bytes(b"icc2")
    _ask(_preview(pages), PP.PreviewPlan(kind=PP.KIND_RAW, profile=prof2), b)
    assert len(worker.starts) == 3


def test_a_rebuilt_page_is_prefetched_again(worker, chart):
    pages, plan, b = chart
    a, c = _preview(pages), _preview(pages)
    _ask(a, plan, b)
    worker.release.set()
    _wait_done(1, worker)
    pages[1].write_bytes(b"a rebuilt page, longer than before")
    _ask(c, plan, b)
    assert len(worker.starts) == 2


def test_a_finished_run_is_reused_while_its_colours_are_held(worker, chart,
                                                             monkeypatch):
    pages, plan, b = chart
    _ask(_preview(pages), plan, b)
    worker.release.set()
    _wait_done(1, worker)
    chain = PP.chain_key(plan, b)
    monkeypatch.setitem(PP._tables, chain, object())
    _ask(_preview(pages), plan, b)
    assert len(worker.starts) == 1               # the table is still there
    del PP._tables[chain]
    _ask(_preview(pages), plan, b)
    assert len(worker.starts) == 2               # evicted: fill it again


def test_a_rerun_belongs_to_every_tab_that_still_wants_the_chart(worker,
                                                                  chart,
                                                                  tmp_path):
    """Review D: a finished run whose colours were let go is run again by the
    next tab to ask. The two tabs that joined the first run do not ask again,
    so if the rerun belonged to the asker alone, that tab moving on stopped a
    prefetch the other two still wanted."""
    pages, plan, b = chart
    a, c = _preview(pages), _preview(pages)
    _ask(a, plan, b)
    _ask(c, plan, b)
    worker.release.set()
    _wait_done(1, worker)
    worker.release.clear()
    d = _preview(pages)
    _ask(d, plan, b)                             # no table held: run again
    assert len(worker.starts) == 2
    rerun_stop = worker.starts[1][3]
    other = tmp_path / "elsewhere_01.tif"
    other.write_bytes(b"x")
    other2 = tmp_path / "elsewhere_02.tif"
    other2.write_bytes(b"y")
    d._pages = [(other, 0), (other2, 0)]
    _ask(d, plan, b)
    assert not rerun_stop.is_set(), "tabs a and c still want this chart"
    worker.release.set()


def test_the_real_worker_still_fills_the_shared_table(tmp_path, monkeypatch):
    """End to end with the real worker and a stand-in cctiff: three tabs, one
    cctiff call, and the table answers the page afterwards without another."""
    from PIL import Image
    import subprocess
    from core.resource_path import argyll_binary
    monkeypatch.setattr(T, "_PREFETCH", T._SharedPrefetch())
    b = tmp_path / "argyll" / "bin"
    b.mkdir(parents=True)
    (b / argyll_binary("cctiff")).write_text("", encoding="utf-8")
    (tmp_path / "argyll" / "ref").mkdir()
    (tmp_path / "argyll" / "ref" / "sRGB.icm").write_bytes(b"icc")
    prof = tmp_path / "chart.icc"
    prof.write_bytes(b"icc")
    pages = []
    for i, col in enumerate(((255, 0, 0), (0, 255, 0))):
        p = tmp_path / f"c_0{i + 1}.tif"
        Image.new("RGB", (8, 8), col).save(p)
        pages.append(p)
    plan = PP.PreviewPlan(kind=PP.KIND_RAW, profile=prof)
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        with Image.open(cmd[-2]) as im:
            im.convert("RGB").save(cmd[-1])
        return subprocess.CompletedProcess(cmd, 0, "", "")

    real = PP._cctiff_colours
    monkeypatch.setattr(PP, "_cctiff_colours",
                        lambda c, pl, bd, _r: real(c, pl, bd, runner))
    monkeypatch.setattr(PP, "plan_for_page", lambda *a, **k: plan)
    PP.clear_cache()
    try:
        tabs = [_preview(pages) for _ in range(3)]
        for t in tabs:
            _ask(t, plan, b)
        runs = list(T._PREFETCH._runs.values())
        assert len(runs) == 1
        runs[0]["thread"].join(timeout=60)
        assert runs[0]["done"]
        n = len(calls)
        assert n >= 1
        for p in pages:
            assert PP.softproof_page(p, plan, b, runner=runner) is not None
        assert len(calls) == n                   # all colours were filled
    finally:
        PP.clear_cache()
