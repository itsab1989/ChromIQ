"""4.3.27 (Basti's report on 4.3.26): with "auto update preview" on, a layout
change froze the window for about 3 s on an 8-page chart, and every page turn
for 1.3 s.

Measured on screen (2026-11-07, `drive_layout_speed.py`): after a build the
edge note (M-EDGE-NOT-PRINTED, `printer_edges.losses_for_chart`) was worked
out twice, once by Create Chart and once by the hidden Print Chart tab, and
each pass decoded every 300 dpi page three times over (`overhang._ink_mm`
for the page's ink, its helper markers and its patch box). Create Chart then
worked the whole chart out again on every page turn, although the answer is
the whole chart's and does not depend on the page on screen.

Now a page is decoded once while its readers ask for it in turn, and the
chart's answer is kept, keyed by every file it is read from (the page, its
.channels.json, .ti2 and .fd9.json), the printer's edges, the paper, the
shift and the FD-9 setting. No real printer is asked: the driver query is
replaced by a fake one.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np                                             # noqa: E402
import pytest                                                  # noqa: E402
from PIL import Image                                          # noqa: E402

from workflow import printer_edges as PE                      # noqa: E402

DPI = 100
PX = 25.4 / DPI
EDGES = PE.Edges(3.0, 3.0, 3.0, 3.0, "ppd")
PAPER = (100.0, 150.0)


def _count_decodes(monkeypatch) -> "dict[tuple[str, int], int]":
    """Count how often `workflow.overhang` opens a page to read its ink,
    by page, whichever function of it does the decoding."""
    import PIL.Image as _I
    real = _I.open
    seen: dict = {}

    def counting_open(fp, *a, **k):
        f = sys._getframe(1)
        if (f.f_globals.get("__name__") == "workflow.overhang"
                and "ink" in f.f_code.co_name):
            frame = int(f.f_locals.get("frame", 0) or 0)
            key = (str(fp), frame)
            seen[key] = seen.get(key, 0) + 1
        return real(fp, *a, **k)
    monkeypatch.setattr(_I, "open", counting_open)
    return seen


def _page(folder: Path, n: int = 1, *, text_bottom: float = 1.0) -> Path:
    """A 100 x 150 mm page *n* of chart "c": ruler dashes along the top and
    bottom 2 mm in, a line of 'text' *text_bottom* mm above the bottom
    edge, a patch block in the middle."""
    w, h = round(100 / PX), round(150 / PX)
    a = np.full((h, w, 3), 255, np.uint8)
    for x_mm in range(10, 95, 4):
        x = round(x_mm / PX)
        a[round(2 / PX):round(4 / PX), x:x + 1] = 0
        a[h - round(4 / PX):h - round(2 / PX), x:x + 1] = 0
    a[h - round((text_bottom + 1.5) / PX):h - round(text_bottom / PX),
      round(20 / PX):round(60 / PX)] = 0
    a[round(20 / PX):round(130 / PX), round(15 / PX):round(90 / PX)] = 80
    p = folder / f"c_{n:02d}.tif"
    Image.fromarray(a).save(p, dpi=(DPI, DPI))
    side = folder / "c.channels.json"
    if not side.exists():
        side.write_text(json.dumps({"layout": {"recipe": {
            "helper_markers": True, "helper_marker_edge_mm": 2.0,
            "helper_marker_len_mm": 2.0, "helper_markers_top_bottom": True,
            "helper_markers_sides": False}}}), encoding="utf-8")
    return p


def _uncached(pages, edges=EDGES, paper=PAPER, shift=(0.0, 0.0)):
    from workflow import overhang as O
    PE.clear_loss_cache()
    O.clear_ink_cache()
    return PE.losses_for_chart(pages, edges, paper, shift)


def test_the_same_question_twice_decodes_nothing_the_second_time(
        tmp_path, monkeypatch):
    pages = [(_page(tmp_path, n), 0) for n in (1, 2, 3)]
    seen = _count_decodes(monkeypatch)
    first = PE.losses_for_chart(pages, EDGES, PAPER)
    # one decode per page, although four readers ask for each
    assert seen == {(str(p), 0): 1 for p, _f in pages}, seen
    seen.clear()
    again = PE.losses_for_chart(pages, EDGES, PAPER)
    assert seen == {}, f"the second, identical question decoded {seen}"
    assert again == first
    assert first.markers and first.text.get("bottom"), first


def test_a_page_written_again_is_read_again(tmp_path, monkeypatch):
    pages = [(_page(tmp_path, n), 0) for n in (1, 2, 3)]
    before = PE.losses_for_chart(pages, EDGES, PAPER)
    assert before.text.get("bottom"), before
    seen = _count_decodes(monkeypatch)
    # page 2 rewritten with its text well clear of the edge: same size on
    # disk is likely, so only the stamp tells the two apart
    _page(tmp_path, 2, text_bottom=20.0)
    st = pages[1][0].stat()
    os.utime(pages[1][0], ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    after = PE.losses_for_chart(pages, EDGES, PAPER)
    assert (str(pages[1][0]), 0) in seen, "a rewritten page was not read again"
    assert after == _uncached(pages)
    # all three pages rewritten: the bottom text no longer reaches the edge
    for n in (1, 3):
        _page(tmp_path, n, text_bottom=20.0)
        p = tmp_path / f"c_{n:02d}.tif"
        st = p.stat()
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    clear = PE.losses_for_chart(pages, EDGES, PAPER)
    assert not clear.text.get("bottom"), clear
    assert clear == _uncached(pages)


def test_other_edges_paper_shift_or_sidecar_are_a_new_question(
        tmp_path, monkeypatch):
    pages = [(_page(tmp_path, n), 0) for n in (1, 2, 3)]
    base = PE.losses_for_chart(pages, EDGES, PAPER)
    seen = _count_decodes(monkeypatch)

    wider = PE.Edges(5.0, 5.0, 5.0, 5.0, "ppd")
    got = PE.losses_for_chart(pages, wider, PAPER)
    assert seen, "other edges were answered from memory"
    assert got == _uncached(pages, edges=wider)

    seen.clear()
    got = PE.losses_for_chart(pages, EDGES, (100.0, 148.0))
    assert seen, "another paper was answered from memory"
    assert got == _uncached(pages, paper=(100.0, 148.0))

    seen.clear()
    got = PE.losses_for_chart(pages, EDGES, PAPER, (0.0, 1.5))
    assert seen, "another shift was answered from memory"
    assert got == _uncached(pages, shift=(0.0, 1.5))

    # the helper markers switched off in the sidecar: no marker is lost now
    seen.clear()
    side = tmp_path / "c.channels.json"
    side.write_text(json.dumps({"layout": {"recipe": {
        "helper_markers": False}}}), encoding="utf-8")
    st = side.stat()
    os.utime(side, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    got = PE.losses_for_chart(pages, EDGES, PAPER)
    assert not got.markers, got
    assert base.markers
    assert got == _uncached(pages)


def test_the_fd9_setting_is_part_of_the_question(tmp_path, monkeypatch):
    from workflow.fd9 import support
    pages = [(_page(tmp_path, n), 0) for n in (1, 2)]
    monkeypatch.setattr(support, "_latched", False)
    PE.losses_for_chart(pages, EDGES, PAPER)
    calls = []
    real = PE._fd9_page
    monkeypatch.setattr(PE, "_fd9_page",
                        lambda t: (calls.append(t), real(t))[1])
    support.set_enabled_for_this_process(True)
    PE.losses_for_chart(pages, EDGES, PAPER)
    assert calls, "FD-9 switched on and the answer came from memory"


def test_a_returned_loss_cannot_change_the_next_answer(tmp_path):
    pages = [(_page(tmp_path, n), 0) for n in (1, 2)]
    first = PE.losses_for_chart(pages, EDGES, PAPER)
    want = _uncached(pages)
    first.markers["top"] = 99
    first.text.clear()
    first.caption.append("left")
    second = PE.losses_for_chart(pages, EDGES, PAPER)
    assert second == want
    second.needed_mm["left"] = 42.0
    second.patches.append("right")
    assert PE.losses_for_chart(pages, EDGES, PAPER) == want


def test_the_kept_ink_is_read_only_and_one_page(tmp_path):
    from workflow import overhang as O
    a, b = _page(tmp_path, 1), _page(tmp_path, 2)
    ink, _mm = O._ink_mm(a, 0)
    with pytest.raises(ValueError):
        ink[0, 0] = True
    assert O._ink_mm(a, 0)[0] is ink           # the same page: kept
    O._ink_mm(b, 0)
    assert len(O._ink_cache) == 1               # never more than one page


# ---- on a real printtarg chart ---------------------------------------------
def _printtarg():
    from core.resource_path import argyll_binary
    from tests.argyll_env import argyll_tool
    return shutil.which(argyll_binary("printtarg")) or argyll_tool("printtarg")


_PT = _printtarg()
requires_argyll = pytest.mark.skipif(_PT is None,
                                     reason="printtarg not installed")


def _three_page_chart(tmp_path: Path) -> "list[Path]":
    cm = (Path(__file__).resolve().parent
          / "fixtures" / "charts" / "cm_a4_480p_2pages.ti1")
    shutil.copy(cm, tmp_path / "chart.ti1")
    subprocess.run([_PT, "-iCM", "-pA4", "-t100", "-h", "-M6", "chart"],
                   cwd=tmp_path, check=True, timeout=120,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    tiffs = sorted(tmp_path.glob("chart_*.tif"))
    assert len(tiffs) >= 3, tiffs
    return tiffs


@requires_argyll
def test_the_kept_answer_is_the_worked_out_one_on_a_real_chart(tmp_path):
    tiffs = _three_page_chart(tmp_path)
    pages = [(t, 0) for t in tiffs]
    # wide enough that the caption, the text and the patches all reach in
    for e in (PE.Edges(7.0, 8.0, 7.0, 8.0, "ppd"),
              PE.Edges(9.0, 12.0, 9.0, 12.0, "ppd")):
        want = _uncached(pages, edges=e, paper=(210.0, 297.0))
        assert want.any(), want
        assert PE.losses_for_chart(pages, e, (210.0, 297.0)) == want
        assert PE.losses_for_chart(pages, e, (210.0, 297.0)) == want


# ---- the two tabs ----------------------------------------------------------
@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _fake_printer(monkeypatch):
    """A queue named Capture_Edge whose driver reports 7 mm all round on A4
    (the chart's patches start 6 mm in): nothing is asked of a real
    printer."""
    asked = []

    def query(printer, chart_mm):
        asked.append(printer)
        return PE.Edges(7.0, 7.0, 7.0, 7.0, "ppd"), (210.0, 297.0)
    monkeypatch.setattr(PE, "_query_driver", query)
    return asked


def _chart_tab(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("last_printer", "Capture_Edge")
    s.set("use_native_print_dialog", False)
    s.set("use_chromiq_layout_engine", True)
    s.set("margin_inspector_show", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    # Create Chart words the note in Manual, with the layout panel on
    # (`_engine_text_notes`), as in Basti's report.
    tab._switch_mode("manual")
    tab._manual_engine_check.setChecked(True)
    return tab, s


@requires_argyll
def test_create_chart_and_print_chart_read_each_page_once(
        qapp, tmp_path, monkeypatch):
    from ui.tabs.tab_print import TabPrint
    tiffs = _three_page_chart(tmp_path)
    asked = _fake_printer(monkeypatch)
    tab, s = _chart_tab(tmp_path)
    tp = TabPrint(s)
    tp._printer_combo.blockSignals(True)
    tp._printer_combo.clear()
    tp._printer_combo.addItem("Capture_Edge", "Capture_Edge")
    tp._printer_combo.setCurrentIndex(0)
    tp._printer_combo.blockSignals(False)
    seen = _count_decodes(monkeypatch)
    calls = []
    real = PE.losses_for_chart
    monkeypatch.setattr(PE, "losses_for_chart", lambda *a, **k: (
        calls.append(1), real(*a, **k))[1])

    tab._preview.load_tiff(tiffs)
    tab._set_margin_chart(tiffs, tmp_path / "chart.ti2")   # Create Chart
    tp.load_tiffs(tiffs)                                   # Print Chart
    assert asked and len(calls) >= 2, (asked, calls)       # both tabs asked
    assert tp._edge_note_lbl.text(), "the Print Chart tab shows no note"
    decoded = {k: v for k, v in seen.items()
               if Path(k[0]) in set(tiffs)}
    assert decoded == {(str(t), 0): 1 for t in tiffs}, decoded


@requires_argyll
def test_paging_does_not_work_the_chart_out_again(qapp, tmp_path, monkeypatch):
    """#83 still holds: the frame measures the page on screen. What is not
    done again is the whole-chart edge note."""
    import workflow.margin_inspector as mi
    tiffs = _three_page_chart(tmp_path)
    _fake_printer(monkeypatch)
    per_page = []
    real_losses = PE.losses
    monkeypatch.setattr(PE, "losses", lambda path, frame, *a, **k: (
        per_page.append(Path(path)), real_losses(path, frame, *a, **k))[1])
    measured: list[Path] = []
    real_mm = mi.measure_margins
    monkeypatch.setattr(mi, "measure_margins", lambda tif, **kw: (
        measured.append(Path(tif)), real_mm(tif, **kw))[1])

    tab, _s = _chart_tab(tmp_path)
    tab._preview.load_tiff(tiffs)
    tab._set_margin_chart(tiffs, tmp_path / "chart.ti2")
    assert sorted(per_page) == sorted(tiffs), per_page
    note = tab._printer_edge_notice()
    assert note, "no edge note to keep"
    for i in (1, 2, 1, 0, 2):
        tab._preview.show_page(i)
        assert measured[-1] == tiffs[i], "the frame left the page on screen"
    assert tab._printer_edge_notice() == note
    assert sorted(per_page) == sorted(tiffs), (
        f"paging worked the chart out again: {len(per_page)} page passes "
        f"for {len(tiffs)} pages")
