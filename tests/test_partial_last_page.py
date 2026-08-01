"""#93 (Knut): the "last page not full" hint computation. The pure helper
returns the unused-slot count when a patch set leaves a notable gap on the last
page, else None — so it's testable without the modal."""
import pytest

pytest.importorskip("PyQt6")
import json
from pathlib import Path

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from core.argyll_runner import ArgyllRunner
from core.file_manager import FileManager
from core.settings import AppSettings
from ui.tabs.tab_chart import TabChart
from workflow.layout_engine.presets import LayoutRecipe


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def tab(qapp, tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    return TabChart(ArgyllRunner(s), FileManager(s), s)


def _engine_chart(dir_: Path, n_patches: int) -> Path:
    """A minimal engine chart: <stem>.ti2 (with NUMBER_OF_SETS) + channels.json
    carrying a ChromIQ recipe (i1 / A4, fixed 8x10 patches)."""
    dir_.mkdir(parents=True, exist_ok=True)
    ti2 = dir_ / "chart.ti2"
    ti2.write_text(f'NUMBER_OF_SETS {n_patches}\n')
    rec = LayoutRecipe(instrument="i1", paper="A4", layout_mode="patch_first",
                       patch_w_mm=8.0, patch_h_mm=10.0, clip_border=True)
    (dir_ / "chart.channels.json").write_text(json.dumps(
        {"layout": {"engine": "chromiq", "recipe": rec.to_dict()}}))
    return ti2


def test_no_warning_for_a_nearly_empty_page(tab, tmp_path):
    """This test used to assert the opposite, and the behaviour it pinned is
    the one Knut reported as wrong (#130, 2026-08-01): on a 12-patch chart the
    hint offered to help fill "about 670 more patches".

    5 patches on an i1/A4 layout that holds hundreds is not a page that
    "doesn't quite fill" — it is a page that is essentially empty, and the
    hint's advice (add or remove a few patches) cannot be acted on. The gap is
    only worth mentioning once the page is at least half full; see
    tests/test_knut_beta118_partial_page_hint.py for the full boundary set.
    """
    ti2 = _engine_chart(tmp_path / "few", 5)
    assert tab._partial_last_page_blank(ti2) is None


def test_no_warning_for_a_full_page(tab, tmp_path):
    # Fill exactly one page → no gap → None.
    from workflow.layout_engine import instruments, geometry, papers
    rec = LayoutRecipe(instrument="i1", paper="A4", layout_mode="patch_first",
                       patch_w_mm=8.0, patch_h_mm=10.0, clip_border=True)
    g = instruments.geom_from_build_kwargs(rec.build_kwargs())
    per = geometry.patches_per_sheet(g, *papers.dimensions_mm("A4"))
    ti2 = _engine_chart(tmp_path / "full", per)
    assert tab._partial_last_page_blank(ti2) is None


def test_none_for_printtarg_chart(tab, tmp_path):
    # No channels.json / not an engine chart → None (no hint).
    d = tmp_path / "pt"; d.mkdir()
    ti2 = d / "chart.ti2"; ti2.write_text("NUMBER_OF_SETS 100\n")
    assert tab._partial_last_page_blank(ti2) is None


def test_no_warning_in_guided_mode(tab, monkeypatch):
    """Guided has no patch-set editor and auto-fills the count, so the hint must
    not fire there (#93, Knut)."""
    tab._switch_mode("guided")
    called = []
    monkeypatch.setattr(tab, "_partial_last_page_blank",
                        lambda ti2: called.append(1) or 50)
    tab._maybe_warn_partial_last_page(Path("x.ti2"))
    assert not called           # gated out before computing → no modal


def test_no_warning_when_auto_patch_count(tab, monkeypatch):
    """Manual with Auto patch count on auto-fills the page, so a small gap is just
    rounding — no hint (#93)."""
    tab._switch_mode("manual")
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(True)
    called = []
    monkeypatch.setattr(tab, "_partial_last_page_blank",
                        lambda ti2: called.append(1) or 50)
    tab._maybe_warn_partial_last_page(Path("x.ti2"))
    assert not called


def test_no_warning_for_fixed_ti1_preset(tab, monkeypatch):
    """A bundled fixed-patch-set preset (TC9.18 / Knut / a vendor family like Red
    River) owns its patch count — the set is locked, so "add/remove a few patches"
    is the wrong advice and the hint must not fire."""
    tab._switch_mode("manual")
    if tab._manual_auto_patches_check is not None:
        tab._manual_auto_patches_check.setChecked(False)
    tab._knut_active = True          # a ti1 preset is active → set is locked
    called = []
    monkeypatch.setattr(tab, "_partial_last_page_blank",
                        lambda ti2: called.append(1) or 50)
    tab._maybe_warn_partial_last_page(Path("x.ti2"))
    assert not called
