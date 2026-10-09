"""Beta 16 final (Basti, 2026-10-09): ChromIQ's own printing (the lp route, used
only while "Use default macOS printer dialog" is off) sends the exact-size PDF
by default instead of a TIFF that macOS shrinks into the printable area.

Measured on capture queues: the TIFF came out at 98.5 % (PRO-300 A4, "Printer
Default"), 96.8 % (PRO-300 on "A4") and 95 % (PictureMate 4x6); the PDF at
100 %, colours pixel-identical.

* the default is ON, and the macOS print dialog stays the default ROUTE on
  macOS and Windows (Basti's clarification: the PDF option only matters on
  the lp route);
* schema 28 drops a stored OFF: the box defaulted to OFF since it existed and
  Preferences writes every key, so a stored False cannot be told from the
  echo of the old default; a stored True stays; it runs once;
* the Preferences help says the option only matters while the dialog is off,
  that ON is the default, and no longer promises "about 3%";
* an exact-size PDF on "Printer Default" names the driver's default paper, so
  macOS cannot match its MediaBox to the borderless twin (PRO-300: A4.FullBleed,
  printed borderless at 101.7 %).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402

from core.platform_paths import is_macos, is_windows  # noqa: E402
from core.settings import AppSettings, DEFAULTS, SETTINGS_SCHEMA  # noqa: E402

KEY = "pdf_print_fallback"


def _settings(tmp_path: Path, value=None, schema: int = 27, **extra) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s._qs.setValue("settings_schema", schema)
    if value is not None:
        s._qs.setValue(KEY, value)
    for k, v in extra.items():
        s._qs.setValue(k, v)
    return s


# ---- the defaults -----------------------------------------------------------

def test_the_exact_size_pdf_is_on_by_default():
    assert DEFAULTS[KEY] is True
    assert SETTINGS_SCHEMA >= 28


def test_the_macos_print_dialog_stays_the_default_route():
    """Basti, 2026-10-09: the PDF default must not move the default ROUTE."""
    assert DEFAULTS["use_native_print_dialog"] == (is_windows() or is_macos())


def test_nothing_stored_reads_on(tmp_path):
    s = _settings(tmp_path)
    s.migrate()
    assert s.get(KEY) is True


# ---- the migration (schema 28) ---------------------------------------------

@pytest.mark.parametrize("stored", [False, "false"])
def test_a_stored_off_is_the_old_default_and_moves_to_on(tmp_path, stored):
    s = _settings(tmp_path, stored)
    dropped = s.migrate()
    assert s.get(KEY) is True
    assert any(KEY in d for d in dropped)


@pytest.mark.parametrize("stored", [True, "true"])
def test_a_stored_on_stays(tmp_path, stored):
    s = _settings(tmp_path, stored)
    dropped = s.migrate()
    assert s.get(KEY) is True
    assert not any(KEY in d for d in dropped)


def test_it_runs_once_so_a_later_off_is_respected(tmp_path):
    s = _settings(tmp_path, False, schema=28)
    s.migrate()
    assert s.get(KEY) is False


@pytest.mark.parametrize("route", [True, False, "true", "false"])
def test_the_migration_never_touches_the_print_route(tmp_path, route):
    s = _settings(tmp_path, False, use_native_print_dialog=route)
    s.migrate()
    assert s._qs.value("use_native_print_dialog") == route


# ---- the Preferences help ---------------------------------------------------

def _tooltip_source() -> str:
    src = (Path(__file__).resolve().parent.parent / "ui" / "dialogs"
           / "settings_dialog.py").read_text(encoding="utf-8")
    start = src.index('tr("Exact-size PDF fallback"),')
    return src[start:src.index("self._confirm_print_check", start)]


def test_the_help_says_where_the_option_matters_and_what_the_default_is():
    text = _tooltip_source()
    assert 'Applies only when \\"Use default macOS printer dialog\\" is off' in text
    assert "never uses" in text
    assert "ON (the default)" in text
    assert "about 3%" not in text
    assert "1.5% to 8.5%" in text


# ---- the borderless twin ---------------------------------------------------

_PPD = """*PPD-Adobe: "4.3"
*DefaultPageSize: A4
*PageSize A4/A4: ""
*PageSize A4.FullBleed/A4 borderless: ""
*PageSize Letter/US Letter: ""
*PaperDimension A4/A4: "595.28 841.89"
*PaperDimension A4.FullBleed/A4 borderless: "595.28 841.89"
*PaperDimension Letter/US Letter: "612.00 792.00"
"""


@pytest.fixture()
def ppd(tmp_path):
    p = tmp_path / "q.ppd"
    p.write_text(_PPD, encoding="latin-1")
    return str(p)


def test_printer_default_names_the_default_paper_not_its_borderless_twin(ppd):
    from workflow.cups_printer import _name_the_default_page
    opts: dict[str, str] = {}
    _name_the_default_page(opts, "q", (595.2, 841.9), ppd_path=ppd)
    assert opts == {"PageSize": "A4"}
    landscape: dict[str, str] = {}
    _name_the_default_page(landscape, "q", (841.9, 595.2), ppd_path=ppd)
    assert landscape == {"PageSize": "A4"}


@pytest.mark.parametrize("opts, size", [
    ({"PageSize": "Letter"}, (595.2, 841.9)),   # a chosen paper is kept
    ({"EPIJ_Size": "74"}, (595.2, 841.9)),      # an Epson size brings its own
    ({}, (612.0, 792.0)),                       # not the chart's size: left alone
    ({}, None),
])
def test_a_chosen_or_different_paper_is_left_alone(ppd, opts, size):
    from workflow.cups_printer import _name_the_default_page
    before = dict(opts)
    _name_the_default_page(opts, "q", size, ppd_path=ppd)
    assert opts == before


def test_a_borderless_default_is_never_named(tmp_path):
    from workflow.cups_printer import _name_the_default_page
    p = tmp_path / "b.ppd"
    p.write_text(_PPD.replace("*DefaultPageSize: A4", "*DefaultPageSize: A4.FullBleed"),
                 encoding="latin-1")
    opts: dict[str, str] = {}
    _name_the_default_page(opts, "q", (595.2, 841.9), ppd_path=str(p))
    assert opts == {}


def _tiff(path, w, h, dpi=72):
    import numpy as np
    from PIL import Image
    Image.fromarray(np.full((h, w, 3), 128, np.uint8), "RGB").save(path, dpi=(dpi, dpi))
    return path


def test_the_generic_pdf_job_names_it_and_lays_the_pdf_on_it(monkeypatch, ppd, tmp_path):
    import workflow.cups_printer as cp
    monkeypatch.setattr("workflow.ppd_color.ppd_path_for_queue", lambda q: ppd)
    seen = {}

    def fake_lp(self, cmd):
        seen["cmd"] = list(cmd)
        seen["pdf"] = Path(cmd[-1]).read_bytes()
        return 0, ""
    monkeypatch.setattr(cp.CupsRawPrinter, "_run_lp_result", fake_lp)
    chart = _tiff(tmp_path / "land.tif", 842, 595)          # landscape A4 at 72 dpi
    cp.CupsRawPrinter()._print_job_pdf(chart, cp.PrintConfig("q", {}), None, None,
                                        None, None)
    assert "PageSize=A4" in seen["cmd"]
    import re
    m = re.search(rb"/MediaBox \[0 0 (\S+) (\S+)\]", seen["pdf"])
    assert float(m.group(1)) < float(m.group(2)), "the PDF page must be the portrait paper"


# ---- a landscape chart is turned onto the paper ---------------------------

def test_a_landscape_chart_is_turned_onto_portrait_paper(tmp_path):
    """Measured on four capture queues: macOS's PDF rasteriser does not turn a
    landscape PDF page onto portrait paper, it cuts it off."""
    import re
    from workflow.postscript_generator import PdfGenerator
    pdf = PdfGenerator().generate(_tiff(tmp_path / "l.tif", 842, 595),
                                  page_size_pt=(595.28, 841.89))
    m = re.search(rb"/MediaBox \[0 0 (\S+) (\S+)\]", pdf)
    assert (float(m.group(1)), float(m.group(2))) == (595.28, 841.89)
    cm = re.search(rb"q\n(\S+) (\S+) (\S+) (\S+) (\S+) (\S+) cm\n/Im Do", pdf)
    a, b, c, d, e, f = (float(x) for x in cm.groups())
    assert a == 0 and d == 0 and b > 0 and c < 0, "image turned 90 degrees"
    # the turned image (595 wide, 842 tall on the page) covers the page 1:1
    assert abs(b - 842) < 0.5 and abs(-c - 595) < 0.5
    assert abs((e + c) - 0.14) < 0.5 and abs(f) < 0.5


# ---- the bump to 28 moves nothing else ------------------------------------

def test_a_schema_27_users_own_choices_survive_the_bump(tmp_path):
    """migrate() runs on every schema bump. Each step runs only when coming
    from below its own schema: measured before this, the bump to 28 reset a
    schema-27 user's Restore last tab, ArgyllCMS reading, report saving off,
    printtarg layout and a chosen limit of 30."""
    s = _settings(tmp_path, False, restore_last_tab="true", chartread_engine="argyll",
                  save_measurement_report="false", use_chromiq_layout_engine="false",
                  patch_read_warn_de_accurate=30.0, patch_neighbour_buffer_de=15.0)
    dropped = s.migrate()
    assert [d for d in dropped if KEY not in d] == []
    assert s.get("restore_last_tab") is True
    assert s.get("chartread_engine") == "argyll"
    assert s.get("save_measurement_report") is False
    assert s.get("use_chromiq_layout_engine") is False
    assert float(s.get("patch_read_warn_de_accurate")) == 30.0
    assert s._qs.value("patch_neighbour_buffer_de_accurate") is None


def test_an_old_install_still_gets_every_step(tmp_path):
    s = _settings(tmp_path, False, schema=9, restore_last_tab="true",
                  chartread_engine="argyll", save_measurement_report="false")
    s.migrate()
    assert s.get("restore_last_tab") is False
    assert s.get("chartread_engine") == "chromiq"
    assert s.get("save_measurement_report") is True
    assert s.get(KEY) is True
