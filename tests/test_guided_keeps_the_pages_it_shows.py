"""Generate in Guided gives the pages "Number of pages" asks for, or asks
before it keeps the run's own patch set on other pages (the owner,
2026-11-15, M-GUIDED-SET-PAGES).

His sequence: an i1iSis chart, A4, 1 page; a patch set of 1008 made in the
patch set tool (one A4 page without the notes band) bound to the run; the
notes band switched on, so the page holds 896. Reopened and Generate in
Guided: 1008 patches on 2 pages, with "Number of pages: 1" on screen and no
word about it. The same happens with every instrument (the binding is #147,
shared), e.g. a ColorMunki set of 480 with 6 pages asked.

* the set takes other pages than asked: Generate asks; "Keep my patch set"
  (the default, and Escape) lays it out as before; "Make a new patch set"
  runs targen for the pages asked and drops the binding;
* the set takes exactly the pages asked: no question, laid out as before;
* Manual: no question, laid out as before.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import FileManager  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_chart import TabChart  # noqa: E402

FIXTURE = (Path(__file__).resolve().parent / "fixtures" / "charts"
           / "cm_a4_480p_2pages.ti1")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def isis_on():
    from workflow.isis import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _tab(tmp_path, instr, paper, pages, ti1):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    s.set("layout_info_show", True)
    tab = TabChart(ArgyllRunner(s), FileManager(s), s)
    tab._switch_mode("guided")
    tab._instr_combo.setCurrentIndex(tab._instr_combo.findData(instr))
    tab._paper_combo.setCurrentIndex(tab._paper_combo.findData(paper))
    tab._pages_spin.setValue(pages)
    tab._preset_ti1_path = ti1
    tab._preset_ti1_targen_sig = tab._targen_signature()
    tab._update_patch_count()
    return tab


def _answer(monkeypatch, which: "str | None"):
    """Answer M-GUIDED-SET-PAGES with the button whose text starts with
    *which* ("Make", "Keep"), or None to press Escape; return what was
    asked."""
    asked = []

    def fake_exec(box):
        asked.append(box.windowTitle())
        if which is None:
            box.escapeButton().click()
            return 0
        for b in box.buttons():
            if b.text().startswith(which):
                b.click()
                return 0
        raise AssertionError([b.text() for b in box.buttons()])

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return asked


def _isis_set(tmp_path, n=1008) -> Path:
    rows = "\n".join(f"{i + 1} {i % 100:.1f} {(i * 7) % 100:.1f} "
                     f"{(i * 13) % 100:.1f}" for i in range(n))
    p = tmp_path / "own.ti1"
    p.write_text(
        "CTI1\n\nDESCRIPTOR \"t\"\nORIGINATOR \"ChromIQ\"\n"
        "COLOR_REP \"RGB\"\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n{rows}\nEND_DATA\n",
        encoding="utf-8")
    return p


def test_his_sequence_is_asked_and_a_new_set_fills_one_page(
        qapp, tmp_path, monkeypatch, isis_on):
    tab = _tab(tmp_path, "XRISIS", "A4", 1, _isis_set(tmp_path))
    tab._isis_band_check.setChecked(True)
    tab._update_patch_count()
    assert tab._bound_set_pages == 2          # 1008 at 896 a page
    assert tab._guided_capacity == 896        # what a new set fills
    asked = _answer(monkeypatch, "Make")
    assert tab._guided_bound_set_pages_answer() == "new"
    assert len(asked) == 1


@pytest.mark.parametrize("which", ["Keep", None])
def test_keep_and_escape_keep_the_set(qapp, tmp_path, monkeypatch, which):
    ti1 = tmp_path / "mine.ti1"
    shutil.copy(FIXTURE, ti1)
    tab = _tab(tmp_path, "CM", "A4", 6, ti1)
    assert tab._bound_set_pages not in (None, 6)
    asked = _answer(monkeypatch, which)
    assert tab._guided_bound_set_pages_answer() == "keep"
    assert len(asked) == 1


def test_a_set_that_fits_the_pages_asks_nothing(qapp, tmp_path,
                                                monkeypatch):
    ti1 = tmp_path / "mine.ti1"
    shutil.copy(FIXTURE, ti1)
    tab = _tab(tmp_path, "CM", "A4", 6, ti1)
    tab._pages_spin.setValue(tab._bound_set_pages)
    tab._update_patch_count()
    asked = _answer(monkeypatch, "Make")
    assert tab._guided_bound_set_pages_answer() == "keep"
    assert asked == []


def test_manual_asks_nothing(qapp, tmp_path, monkeypatch):
    ti1 = tmp_path / "mine.ti1"
    shutil.copy(FIXTURE, ti1)
    tab = _tab(tmp_path, "CM", "A4", 6, ti1)
    tab._switch_mode("manual")
    asked = _answer(monkeypatch, "Make")
    assert tab._guided_bound_set_pages_answer() == "keep"
    assert asked == []


@pytest.mark.parametrize("which,laid_out", [("Keep", True), ("Make", False)])
def test_generate_follows_the_answer(qapp, tmp_path, monkeypatch, which,
                                     laid_out):
    """Through `_on_generate`: "Keep" lays the set out as before; "Make"
    drops the binding and goes on to targen (stopped here, before it runs)."""
    ti1 = tmp_path / "mine.ti1"
    shutil.copy(FIXTURE, ti1)
    tab = _tab(tmp_path, "CM", "A4", 6, ti1)
    tab._target_name_edit.setText("pages-test")
    _answer(monkeypatch, which)
    from_ti1, targen = [], []
    monkeypatch.setattr(tab, "_generate_from_ti1",
                        lambda p, ask=False: from_ti1.append(p))
    monkeypatch.setattr(tab._creator, "generate",
                        lambda *a, **k: targen.append(k))
    monkeypatch.setattr(tab, "_confirm_displacing_results", lambda *a: True,
                        raising=False)
    tab._on_generate()
    if laid_out:
        assert from_ti1 == [ti1] and not targen
        assert tab._preset_ti1_path == ti1
    else:
        assert not from_ti1
        assert tab._preset_ti1_path is None
