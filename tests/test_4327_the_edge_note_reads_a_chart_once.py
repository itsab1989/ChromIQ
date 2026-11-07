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


# ---- a rewrite the file stamp cannot see (4.3.27 review) -------------------
# On a disk that keeps modification times to the second (HFS+, an external
# drive in FAT or exFAT) a chart rebuilt in place keeps its inode, its size
# and its modification time within one tick, so the stamp alone answered from
# the old page. Every writer of chart pages in ChromIQ forgets both memories.
def _engine_page(folder: Path, text_bottom_px: int) -> "list[Path]":
    from workflow.layout_engine import raster
    w, h = round(100 / PX), round(150 / PX)
    a = np.full((h, w, 3), 255, np.uint8)
    a[100:500, 60:340] = 80
    a[h - text_bottom_px - 6:h - text_bottom_px, 80:240] = 0
    return raster.save_tiffs([Image.fromarray(a)], folder / "c.tif",
                             dpi=DPI, compression="none")


def test_a_same_stamp_rewrite_through_chromiq_is_read_again(tmp_path):
    from workflow import overhang as O
    page = _engine_page(tmp_path, 4)[0]
    st = page.stat()
    first = PE.losses_for_chart([(page, 0)], EDGES, PAPER)
    assert first.text.get("bottom"), first
    O._ink_mm(page, 0)
    # the layout engine writes the page again, text well clear of the edge,
    # and the disk keeps the old modification time (one tick)
    _engine_page(tmp_path, 200)
    os.utime(page, ns=(st.st_atime_ns, st.st_mtime_ns))
    now = page.stat()
    assert (now.st_ino, now.st_size, now.st_mtime_ns) == (
        st.st_ino, st.st_size, st.st_mtime_ns), "not a same-stamp rewrite"
    again = PE.losses_for_chart([(page, 0)], EDGES, PAPER)
    assert not again.text.get("bottom"), (
        f"the old page's answer came back: {again.text}")
    assert again == _uncached([(page, 0)])


def test_a_printtarg_run_forgets_the_pages(tmp_path):
    """printtarg writes the pages itself, through `ArgyllRunner`: both
    memories are forgotten when it starts and when it ends."""
    import inspect
    from core import argyll_runner as AR
    from workflow import overhang as O
    pages = [(_page(tmp_path, n), 0) for n in (1, 2)]
    PE.losses_for_chart(pages, EDGES, PAPER)
    assert PE._loss_cache and O._ink_cache
    AR._forget_chart_pages_for("targen")          # writes no page
    assert PE._loss_cache and O._ink_cache
    AR._forget_chart_pages_for("/Applications/Argyll/bin/printtarg")
    assert not PE._loss_cache and not O._ink_cache
    assert "_forget_chart_pages_for(tool)" in inspect.getsource(
        AR.ArgyllRunner.run)
    assert "_forget_chart_pages_for(" in inspect.getsource(
        AR.ArgyllRunner._on_finished)


#: Places that write an image or start printtarg and never write a page of a
#: chart the edge note or the overhang plan reads, with why.
_NOT_CHART_PAGES = {
    "ui/dialogs/settings_dialog.py::SettingsDialog._save_and_close":
        "saves the settings",
    "ui/dialogs/softproof_dialog.py::SoftproofDialog._on_save_proof":
        "the soft proof the user exports",
    "ui/fd9_measurement.py::FD9MeasureMixin._fd9_load_preview":
        "the FD-9 scan preview picture",
    "ui/tabs/tab_print.py::TabPrint._send_page": "a temporary print copy",
    "ui/tabs/tab_print.py::TabPrint._print_native_qt": "a temporary print copy",
    "workflow/chart_creator.py::ChartCreator._capture_printtarg_cht":
        "printtarg in a temporary folder, for the .cht only",
    "workflow/chart_creator.py::ChartCreator._binary_search":
        "printtarg in a temporary folder, for a capacity probe",
    "workflow/chart_inks.py::split_page": "a temporary file for printing",
    "workflow/cups_printer.py::write_tagged_tiff": "a print copy",
    "workflow/cups_printer.py::CupsRawPrinter._print_job_tiff_converted":
        "a temporary print copy",
    "workflow/fd9/independent.py::capture_layout": "a spectral model",
    "workflow/fd9/preview.py::build_scan_preview": "a scan preview picture",
    "workflow/i18n_roundtrip.py::write_xlsx": "a spreadsheet",
    "workflow/layout_engine/raster.py::export_clip_template":
        "the clip-strip template the user exports",
    "workflow/native_print_macos.py::_postscript_for_pages":
        "a temporary print source",
    "workflow/photo_fit.py::as_tiff": "a scan converted for scanin",
    "workflow/preset_layout.py::_printtarg_binary":
        "names printtarg; its layouts run in a temporary folder",
    "workflow/print_preview.py::_cctiff_colours": "a temporary preview file",
    "workflow/scan_auto_align.py::auto_align": "a scan crop",
    "workflow/softproof_runner.py::prepare_input_tiff": "a soft-proof input",
    "workflow/softproof_runner.py::SoftproofRunner._after_preview_proof":
        "a soft-proof file",
    "workflow/softproof_runner.py::SoftproofRunner._compute":
        "soft-proof files",
    "workflow/standard_targets.py::make_test_scan": "a synthetic scan",
    "workflow/verify_expected.py::convert_like_the_print":
        "a temporary file for cctiff",
}


def _image_writers():
    """Every call that writes an image file (``imwrite``, ``.save(path)``)
    or names printtarg in ChromIQ's code, with whether the function it is in
    (or one around it) carries `@writes_chart_pages`."""
    import ast
    root = Path(__file__).resolve().parent.parent
    files = [*(root / "workflow").rglob("*.py"), *(root / "ui").rglob("*.py"),
             *(root / "core").rglob("*.py"), root / "main.py"]
    found = {}
    for f in sorted(files):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        rel = f.relative_to(root).as_posix()

        def walk(node, names, marked):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef)):
                    deco = any(getattr(d, "id", getattr(d, "attr", ""))
                               == "writes_chart_pages"
                               for d in getattr(child, "decorator_list", []))
                    walk(child, names + [child.name], marked or deco)
                    continue
                if isinstance(child, ast.Call):
                    fn = child.func
                    name = (fn.attr if isinstance(fn, ast.Attribute)
                            else getattr(fn, "id", ""))
                    hit = (name == "imwrite"
                           or (name == "save" and child.args)
                           or (name in ("argyll_tool_path", "argyll_binary")
                               and any(isinstance(a, ast.Constant)
                                       and a.value == "printtarg"
                                       for a in child.args)))
                    if hit:
                        key = f"{rel}::{'.'.join(names)}"
                        found[key] = found.get(key, True) and marked
                walk(child, names, marked)
        walk(tree, [], False)
    return found


def test_every_chart_page_writer_forgets_the_pages():
    found = _image_writers()
    assert len(found) > 20, found                  # the scan does find them
    unmarked = sorted(k for k, ok in found.items()
                      if not ok and k not in _NOT_CHART_PAGES)
    assert not unmarked, (
        "these write images or run printtarg and neither carry "
        "@writes_chart_pages nor are named in _NOT_CHART_PAGES: "
        f"{unmarked}")
    # the page writers themselves are marked
    for k in ("workflow/layout_engine/raster.py::save_tiffs",
              "workflow/layout_engine/raster.py::save_separated_tiffs",
              "workflow/tiff_metadata.py::_write_preserving",
              "workflow/ti2_relayout.py::regenerate",
              "workflow/ti2_relayout.py::recolor_spacers",
              "workflow/fd9/chart.py::_build_single_chart"):
        assert found.get(k) is True, (k, found.get(k))
    stale = sorted(k for k in _NOT_CHART_PAGES if k not in found)
    assert not stale, f"named in _NOT_CHART_PAGES but gone: {stale}"


def test_the_writers_that_copy_pages_forget_them_too():
    """Copies are not found by the scan above: these put chart pages in place
    by copying files, and carry the mark all the same."""
    from ui import ti2_loader
    from ui.tabs.tab_chart import TabChart
    from workflow import chart_import, verify_chart_snapshot
    from workflow.fd9 import chart as fd9_chart
    for fn in (TabChart._import_applied_chart, TabChart._create_prebuilt_target,
               ti2_loader._copy_files,
               chart_import._copy_chart_set, chart_import.copy_whole_project,
               chart_import.rebuild_missing_pages,
               verify_chart_snapshot.restore_slot,
               verify_chart_snapshot.restore_chart,
               verify_chart_snapshot._restore_turned_export,
               fd9_chart.build_chart):
        assert getattr(fn, "writes_chart_pages", False), fn.__qualname__
