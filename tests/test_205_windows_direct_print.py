"""#205 (4.3.8): ChromIQ's own print route on Windows, and the Windows dialog
route printing at 100 %.

Basti, 2026-10-10: Windows gets the macOS switch ("Use default Windows printer
dialog", the dialog staying the default). With it off, a PostScript printer
gets ChromIQ's own PostScript raw through the spooler (``win_spooler``,
``win_raw_printer``); a printer whose driver is not PostScript gets an RGB
chart through the Windows dialog and refuses any other.

Measured on Windows 11 25H2 ARM64 before any of this was written (report
folder ``~/Desktop/ChromIQ-work/2026-10-20_205_windows_direct_print``):

* RAW through a v3 driver, and XPS_PASS through the v4 Microsoft PS Class
  Driver, reach the port byte for byte (five charts: RGB, CMY, CMYK, two
  six-ink sets); RAW through the v4 driver delivers 0 bytes (event 372).
* 4.3.8-beta.1's dialog route scaled every chart to the printable area: an A4
  chart on A4 at 93.2 %, an A5-size chart ENLARGED to 135.7 %, an A3 chart on
  A4 at 64.8 %; and it converted a CMYK chart to RGB without a word.

These tests hold what the measurements found; they run on every platform
(the spooler itself is faked except in the one ``real_spooler`` test).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                       # noqa: E402

from core import settings as settings_mod                # noqa: E402
from core.settings import AppSettings, DEFAULTS, SETTINGS_SCHEMA  # noqa: E402
from workflow import win_raw_printer as wrp              # noqa: E402
from workflow import win_spooler                          # noqa: E402
from workflow.cups_printer import PrintConfig            # noqa: E402
from ui.tabs.tab_print import TabPrint as _TabPrint      # noqa: E402
from tests.test_platform_paths import fresh_module       # noqa: E402,F401 - a fixture

#: the real dialog route, taken before conftest's autouse
#: ``_no_native_print_dialog`` replaces it on the class for every test
_REAL_PRINT_NATIVE_QT = _TabPrint._print_native_qt

# the Microsoft PS Class Driver's PPD, as Windows 11 ships it (abridged): no
# translation strings at all, and code that calls the driver's own prolog
MS_PS_CLASS_PPD = """*PPD-Adobe: "4.3"
*ModelName:             "Microsoft PS Class Driver"
*LanguageLevel: "3"
*OpenUI *Resolution/Resolution: PickOne
*OrderDependency: 10 PageSetup *Resolution
*DefaultResolution: 600dpi
*Resolution 300dpi:   "<< /HWResolution [300 300] >> setpagedevice"
*Resolution 600dpi:   "<< /HWResolution [600 600] >> setpagedevice"
*CloseUI: *Resolution
*OpenUI *PageSize: PickOne
*OrderDependency: 40 PageSetup *PageSize
*DefaultPageSize: Letter
*PageSize Letter:                                "featurebegin{<< /PageSize [612 792] >> setpagedevice}featurecleanup"
*PageSize A4:                                    "featurebegin{<< /PageSize [595 842] >> setpagedevice}featurecleanup"
*CloseUI: *PageSize
*ImageableArea Letter:                           "36 36 576 756"
*ImageableArea A4:                               "36 36 559 806"
*PaperDimension Letter:                          "612 792"
*PaperDimension A4:                              "595 842"
*OpenUI *MediaType: PickOne
*DefaultMediaType: Plain
*MediaType Plain: ""
*CloseUI: *MediaType
"""

# a vendor-style PPD: translations, a multi-line choice, and a JCL option
VENDOR_PPD = """*PPD-Adobe: "4.3"
*JCLBegin: "<1B>%-12345X@PJL JOB<0A>"
*JCLToPSInterpreter: "@PJL ENTER LANGUAGE = POSTSCRIPT <0A>"
*JCLEnd: "<1B>%-12345X@PJL EOJ <0A><1B>%-12345X"
*JCLOpenUI *JCLPrintQuality/Print Quality: PickOne
*OrderDependency: 20 JCLSetup *JCLPrintQuality
*DefaultJCLPrintQuality: Normal
*JCLPrintQuality Normal/Normal: "@PJL SET PRINTQUALITY=NORMAL<0A>"
*JCLPrintQuality Best/Best: "@PJL SET PRINTQUALITY=BEST<0A>"
*JCLCloseUI: *JCLPrintQuality
*OpenUI *MediaType/Paper Type: PickOne
*OrderDependency: 50 AnySetup *MediaType
*DefaultMediaType: Plain
*MediaType Plain/Plain Paper: "<</MediaType (Plain)>> setpagedevice"
*MediaType Glossy/Glossy Photo: "
<</MediaType (Glossy)>> setpagedevice
"
*End
*CloseUI: *MediaType
*OpenUI *InputSlot/Paper Source: PickOne
*OrderDependency: 30 AnySetup *InputSlot
*InputSlot Tray1/Tray 1: "<</ManualFeed false /MediaPosition 1>> setpagedevice"
*InputSlot Manual/Manual Feed: "<</ManualFeed true>> setpagedevice"
*CloseUI: *InputSlot
"""

PS = "%!PS-Adobe-3.0\n%%LanguageLevel: 3\n%%EndComments\n\nBODY\nshowpage\n%%EOF\n"


# ---- 1. the PPD as the Windows route reads it --------------------------------

def test_a_ppd_without_translation_strings_still_has_its_options():
    """The parsers the macOS route uses need ``*Key value/label:``; a Windows
    PPD has none, and the tab would have shown no paper size at all."""
    opts = wrp.ppd_options(MS_PS_CLASS_PPD)
    assert opts["PageSize"] == ("Page Size", [("Letter", "Letter"), ("A4", "A4")])
    assert opts["Resolution"][1] == [("300dpi", "300dpi"), ("600dpi", "600dpi")]
    assert opts["MediaType"] == ("Media Type", [("Plain", "Plain")])


def test_translations_and_jcl_options_are_read():
    opts = wrp.ppd_options(VENDOR_PPD)
    assert opts["MediaType"] == ("Paper Type", [("Plain", "Plain Paper"),
                                                ("Glossy", "Glossy Photo")])
    assert opts["JCLPrintQuality"][0] == "Print Quality"
    assert opts["InputSlot"][1][1] == ("Manual", "Manual Feed")


def test_the_feature_code_is_the_ppds_own_and_may_span_lines():
    assert wrp.feature_code(MS_PS_CLASS_PPD, "PageSize", "A4") == \
        "featurebegin{<< /PageSize [595 842] >> setpagedevice}featurecleanup"
    assert wrp.feature_code(VENDOR_PPD, "MediaType", "Glossy") == \
        "<</MediaType (Glossy)>> setpagedevice"
    assert wrp.feature_code(VENDOR_PPD, "MediaType", "Matte") is None


def test_chosen_options_go_into_the_job_in_ppd_order_each_one_protected():
    """What CUPS' pstops does for lp, and nothing on Windows does for a raw
    job: without it the media type and tray the tab shows never reach the
    printer. Each feature in ``stopped``, so the Microsoft PPD's
    ``featurebegin`` (defined only in that driver's own prolog) cannot end the
    job with ``undefined``."""
    out = wrp.with_features(PS, VENDOR_PPD, {"MediaType": "Glossy",
                                            "InputSlot": "Manual",
                                            "PageSize": ""})
    head, _, rest = out.partition("%%EndComments\n")
    assert head.startswith("%!PS-Adobe-3.0")
    setup = rest[:rest.index("BODY")]
    assert setup.index("*InputSlot Manual") < setup.index("*MediaType Glossy")  # 30 before 50
    assert setup.count("} stopped cleartomark") == 2
    assert "*PageSize" not in setup            # "Printer Default": nothing
    assert out.endswith(PS[PS.index("BODY"):])


def test_a_jcl_option_goes_into_a_pjl_header_before_the_postscript():
    out = wrp.with_features(PS, VENDOR_PPD, {"JCLPrintQuality": "Best"})
    assert out.startswith("\x1b%-12345X@PJL JOB\n@PJL SET PRINTQUALITY=BEST\n"
                          "@PJL ENTER LANGUAGE = POSTSCRIPT \n%!PS-Adobe-3.0")
    assert out.endswith("%%EOF\n\x1b%-12345X@PJL EOJ \n\x1b%-12345X")


def test_no_chosen_option_leaves_the_postscript_byte_for_byte():
    assert wrp.with_features(PS, VENDOR_PPD, {}) == PS
    assert wrp.with_features(PS, VENDOR_PPD, {"MediaType": "Unknown"}) == PS


# ---- 2. the driver decides PostScript and the datatype ------------------------

def _facts(path, data, attrs, version=3):
    return win_spooler.DriverFacts("d", version, path, data, attrs)


def test_a_postscript_driver_is_one_whose_data_file_is_a_ppd():
    v4_ps = _facts(r"C:\x\mxdwdrv.dll", r"C:\x\MSxpsPS.ppd", 11, 4)
    v3_ps = _facts(r"C:\x\PSCRIPT5.DLL", r"C:\x\HPCLJ.PPD", 0)
    epson = _facts(r"C:\x\E_YMAIYCE.DLL", r"C:\x\E_YVIFYCE.VIF", 1)
    pdf = _facts(r"C:\x\mxdwdrv.dll", r"C:\x\MPDW-PDC.xml", 163, 4)
    assert v4_ps.is_postscript and v3_ps.is_postscript
    assert not epson.is_postscript and not pdf.is_postscript


def test_a_v4_driver_takes_xps_pass_and_a_v3_driver_raw():
    """KB 2779300, and measured: RAW through the v4 PS Class Driver reached
    the port as 0 bytes, XPS_PASS byte for byte."""
    assert _facts("a", "b.ppd", 11, 4).datatype == "XPS_PASS"
    assert _facts("a", "b.ppd", 0, 3).datatype == "RAW"


@pytest.mark.skipif(sys.platform == "win32", reason="the off-Windows answer")
def test_the_spooler_module_imports_and_refuses_off_windows():
    assert not win_spooler.available()
    assert win_spooler.ppd_path("x") is None
    assert win_spooler.is_postscript("x") is False
    with pytest.raises(win_spooler.SpoolerError):
        win_spooler.list_printers()


def test_no_test_reaches_the_real_spooler():
    """The suite's own guard (conftest ``_no_real_spooler_jobs``): on the
    development VM the default printer is a real Epson."""
    from tests.conftest import SpoolerReachedFromATest
    with pytest.raises(SpoolerReachedFromATest):
        win_spooler.submit("EPSON ET-8550 Series", b"%!PS", "x")
    with pytest.raises(SpoolerReachedFromATest):
        win_spooler.cancel_jobs("EPSON ET-8550 Series")


# ---- 3. the raw job ----------------------------------------------------------

def _rgb_tiff(path: Path, w=60, h=90, dpi=300, value=(10, 200, 30)) -> Path:
    import tifffile
    arr = np.zeros((h, w, 3), np.uint8)
    arr[:] = value
    tifffile.imwrite(str(path), arr, photometric="rgb", resolution=(dpi, dpi),
                     resolutionunit=2)
    return path


def _cmyk_tiff(path: Path, w=60, h=90, dpi=300) -> Path:
    import tifffile
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0] = 200
    tifffile.imwrite(str(path), arr, photometric="separated",
                     resolution=(dpi, dpi), resolutionunit=2)
    return path


def test_the_job_is_chromiqs_postscript_with_the_chosen_features(tmp_path, monkeypatch):
    ppd = tmp_path / "MSxpsPS.ppd"
    ppd.write_text(MS_PS_CLASS_PPD, encoding="latin-1")
    monkeypatch.setattr(win_spooler, "ppd_path", lambda q: str(ppd))
    tiff = _rgb_tiff(tmp_path / "c.tif")
    data = wrp.WindowsRawPrinter.job_bytes(
        tiff, PrintConfig("Q", {"PageSize": "A4"}), page_size_pt=(595.0, 842.0))
    text = data.decode("latin-1")
    assert text.startswith("%!PS-Adobe-3.0")
    assert "%%BeginFeature: *PageSize A4\nfeaturebegin{" in text
    assert "/DeviceRGB setcolorspace" in text
    # ChromIQ's own setpagedevice comes after the PPD's, so the page is ours
    assert text.index("%%EndSetup") < text.index("<< /PageSize [595.00 842.00]")


def test_print_job_ps_reports_the_spoolers_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(win_spooler, "ppd_path", lambda q: None)
    sent = []
    monkeypatch.setattr(win_spooler, "submit",
                        lambda q, data, doc, datatype=None: sent.append((q, doc)) or 42)
    tiff = _rgb_tiff(tmp_path / "c.tif")
    codes = []
    pr = wrp.WindowsRawPrinter()
    pr.print_job_ps(tiff, PrintConfig("Q"), on_finish=codes.append)
    assert codes == [0] and pr.last_job_id == 42 and sent == [("Q", "ChromIQ - c.tif")]

    def _refuse(*a, **k):
        raise win_spooler.SpoolerError(5, "OpenPrinter('Q'): Access is denied.")
    monkeypatch.setattr(win_spooler, "submit", _refuse)
    pr.print_job_ps(tiff, PrintConfig("Q"), on_finish=codes.append)
    assert codes == [0, -1] and pr.last_job_id is None
    assert "Access is denied" in pr.last_error


# ---- 4. the switch -------------------------------------------------------------

def _settings(tmp_path, monkeypatch, *, windows: bool, **stored) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    for k, v in stored.items():
        s._qs.setValue(k, v)
    monkeypatch.setattr(settings_mod, "is_windows", lambda: windows)
    return s


def test_windows_honours_the_stored_route(tmp_path, monkeypatch):
    """Until 4.3.8 ``get`` answered True on Windows whatever was stored."""
    s = _settings(tmp_path, monkeypatch, windows=True)
    s.set("use_native_print_dialog", False)
    assert s.get("use_native_print_dialog") is False
    s.set("use_native_print_dialog", True)
    assert s.get("use_native_print_dialog") is True


def test_the_dialog_stays_the_default_on_windows_and_macos():
    """Basti, 2026-10-20: "like macos the os default path should be default"."""
    import importlib
    from core import platform_paths
    assert DEFAULTS["use_native_print_dialog"] == (
        platform_paths.is_windows() or platform_paths.is_macos())
    src = Path(settings_mod.__file__).read_text(encoding="utf-8")
    assert '"use_native_print_dialog":   is_windows() or is_macos(),' in src
    importlib.reload  # (the default is evaluated at import, per platform)


@pytest.mark.parametrize("stored", [False, "false"])
def test_an_off_stored_while_it_was_forced_is_dropped_on_windows(tmp_path, monkeypatch, stored):
    s = _settings(tmp_path, monkeypatch, windows=True, use_native_print_dialog=stored,
                  settings_schema=30)
    dropped = s.migrate()
    assert s._qs.value("use_native_print_dialog") is None
    assert any("use_native_print_dialog" in d for d in dropped)
    assert s.get("use_native_print_dialog") == DEFAULTS["use_native_print_dialog"]
    # removed directly: not counted as a switch of the setting
    assert int(s.get("print_dialog_setting_changes", 0) or 0) == 0


def test_an_on_is_kept_and_a_later_off_is_the_users(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch, windows=True, use_native_print_dialog=True,
                  settings_schema=30)
    s.migrate()
    assert s._qs.value("use_native_print_dialog") in (True, "true")
    s = _settings(tmp_path / "b", monkeypatch, windows=True,
                  use_native_print_dialog=False, settings_schema=SETTINGS_SCHEMA)
    s.migrate()
    assert s.get("use_native_print_dialog") is False


def test_macos_keeps_a_stored_off(tmp_path, monkeypatch):
    s = _settings(tmp_path, monkeypatch, windows=False, use_native_print_dialog=False,
                  settings_schema=30)
    s.migrate()
    assert s._qs.value("use_native_print_dialog") in (False, "false")


def test_the_switch_exists_on_macos_and_windows_only(fresh_module):
    assert fresh_module("darwin").print_route_switch_supported() is True
    assert fresh_module("win32").print_route_switch_supported() is True
    assert fresh_module("linux").print_route_switch_supported() is False
    # the macOS NSPrintPanel affordance is unchanged
    assert fresh_module("win32").native_print_supported() is False


class _FakeSettings:
    def __init__(self, **overrides):
        self._store = {**DEFAULTS, **overrides}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


def test_preferences_on_windows_offer_the_switch_and_the_confirmation(qapp, monkeypatch):
    from ui.dialogs import settings_dialog as sd
    monkeypatch.setattr(sd, "is_windows", lambda: True)
    monkeypatch.setattr(sd, "is_macos", lambda: False)
    monkeypatch.setattr(sd, "print_route_switch_supported", lambda: True)
    s = _FakeSettings(use_native_print_dialog=True)
    dlg = sd.SettingsDialog(s, None)
    try:
        assert dlg._native_print_check.text() == "Use default Windows printer dialog"
        assert dlg._native_print_check.parent() is not dlg      # placed in the grid
        assert dlg._confirm_print_check.parent() is not dlg
        assert dlg._native_print_check.isChecked()
        assert not dlg._confirm_print_check.isEnabled()        # the dialog confirms
        dlg._native_print_check.setChecked(False)
        assert dlg._confirm_print_check.isEnabled()
        dlg._save_and_close()
        assert s.get("use_native_print_dialog") is False
    finally:
        dlg.deleteLater()


# ---- 5. the Print Chart tab ----------------------------------------------------

def _tab(tmp_path, monkeypatch, pages):
    from ui.tabs import tab_print as tp
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    s.set("use_native_print_dialog", False)
    s.set("confirm_before_printing", False)
    tab = tp.TabPrint(s)
    tab._printer_combo.clear()
    tab._printer_combo.addItem("Office Inkjet", "Office Inkjet")
    tab._printer_combo.setCurrentIndex(0)
    tab._printer.is_printer_reachable = lambda name: True
    tab._module.get_stuck_jobs = lambda name: []
    tab._preview._pages = list(pages)
    tab._preview._current = 0
    monkeypatch.setattr(tp, "is_windows", lambda: True)
    events = []
    monkeypatch.setattr(tab, "_print_native",
                        lambda pages, printer=None: events.append(("dialog", printer)))
    monkeypatch.setattr(tab, "_show_print_refusal",
                        lambda title, body: events.append(("refused", title, body)))
    tab._printer.print_job_ps = lambda *a, **k: events.append(("raw",))
    return tab, events


def test_an_rgb_chart_for_a_printer_that_is_not_postscript_takes_the_dialog(
        qapp, tmp_path, monkeypatch):
    tiff = _rgb_tiff(tmp_path / "rgb.tif")
    tab, events = _tab(tmp_path, monkeypatch, [(tiff, 0)])
    tab._windows_queue_takes_postscript = lambda p: False
    tab._on_print_current()
    assert events == [("dialog", "Office Inkjet")]


def test_a_cmyk_chart_for_a_printer_that_is_not_postscript_is_refused(
        qapp, tmp_path, monkeypatch):
    from workflow import measurement_messages as MM
    tiff = _cmyk_tiff(tmp_path / "cmyk.tif")
    tab, events = _tab(tmp_path, monkeypatch, [(tiff, 0)])
    tab._windows_queue_takes_postscript = lambda p: False
    committed = []
    monkeypatch.setattr(tab, "_commit_print_record", committed.append)
    tab._on_print_current()
    assert [e[0] for e in events] == ["refused"]
    title, body = MM.M_PRINT_WIN_INKS_NOT_POSTSCRIPT.render(
        printer="Office Inkjet", inks="CMYK, 4 inks")
    assert events[0][1:] == (title, body)
    assert committed == [False]


def test_a_postscript_printer_gets_the_raw_job(qapp, tmp_path, monkeypatch):
    tiff = _cmyk_tiff(tmp_path / "cmyk.tif")
    tab, events = _tab(tmp_path, monkeypatch, [(tiff, 0)])
    tab._windows_queue_takes_postscript = lambda p: True
    tab._ink_conversion = lambda *a, **k: None
    tab._on_print_current()
    assert events == [("raw",)]


def test_the_tab_prints_through_the_spooler_on_windows(qapp, tmp_path):
    from ui.tabs import tab_print as tp
    src = Path(tp.__file__).read_text(encoding="utf-8")
    assert "WindowsRawPrinter() if is_windows() else CupsRawPrinter()" in src


def test_a_spooler_refusal_names_windows_not_cups(qapp, tmp_path, monkeypatch):
    from workflow import measurement_messages as MM
    tab, events = _tab(tmp_path, monkeypatch, [])
    tab._printer.last_error = "Der Drucker ist angehalten."
    tab._on_print_done(-1)
    title, body = MM.M_PRINT_WIN_SPOOLER_FAILED.render(
        printer="Office Inkjet", reason="Der Drucker ist angehalten.")
    assert events == [("refused", title, body)]
    assert "CUPS" not in body and "lp" not in body.split()


# ---- 6. the Windows dialog route at 100 % ----------------------------------------

class _Rect:
    def __init__(self, w, h):
        self._w, self._h = w, h

    def width(self):
        return self._w

    def height(self):
        return self._h


class _Layout:
    def __init__(self, pr):
        self.pr = pr

    def _dims(self):
        w, h = self.pr.paper_pt
        return (h, w) if self.pr.landscape else (w, h)

    def fullRectPoints(self):
        return _Rect(*self._dims())

    def fullRectPixels(self, res):
        w, h = self._dims()
        return _Rect(int(round(w / 72 * res)), int(round(h / 72 * res)))


class _FakePrinter:
    """The QPrinter the dialog route builds, as the dialog leaves it."""
    paper_pt = (595.0, 842.0)           # what the user picks in the dialog
    instances: list = []

    class PrinterMode:
        HighResolution = 1

    def __init__(self, *_a):
        self.name, self.full_page, self.landscape = "", False, False
        self.pages = 1
        _FakePrinter.instances.append(self)

    def setPrinterName(self, n):
        self.name = n

    def printerName(self):
        return self.name

    def setFullPage(self, v):
        self.full_page = v

    def setPageOrientation(self, o):
        from PyQt6.QtGui import QPageLayout
        self.landscape = o == QPageLayout.Orientation.Landscape

    def pageLayout(self):
        return _Layout(self)

    def resolution(self):
        return 600

    def newPage(self):
        self.pages += 1


class _FakePainter:
    draws: list = []

    class RenderHint:
        SmoothPixmapTransform = 1

    def __init__(self, printer):
        self.printer, self.t, self.rot = printer, (0.0, 0.0), 0

    def isActive(self):
        return True

    def save(self):
        pass

    def restore(self):
        self.t, self.rot = (0.0, 0.0), 0

    def setRenderHint(self, *a):
        pass

    def translate(self, x, y):
        self.t = (self.t[0] + x, self.t[1] + y)

    def rotate(self, a):
        self.rot += a

    def drawImage(self, rect, img):
        _FakePainter.draws.append((self.t, self.rot, rect.x(), rect.y(),
                                   rect.width(), rect.height(), img.width()))

    def end(self):
        pass


class _FakeDialog:
    accept = True

    def __init__(self, printer, parent=None):
        self.printer = printer

    def exec(self):
        from PyQt6.QtWidgets import QDialog
        return (QDialog.DialogCode.Accepted if _FakeDialog.accept
                else QDialog.DialogCode.Rejected)


@pytest.fixture()
def dialog_route(qapp, tmp_path, monkeypatch):
    import PyQt6.QtGui as QtGui
    import PyQt6.QtPrintSupport as QtPS
    from ui.tabs import tab_print as tp
    _FakePrinter.instances.clear()
    _FakePrinter.paper_pt = (595.0, 842.0)
    _FakePainter.draws.clear()
    _FakeDialog.accept = True
    monkeypatch.setattr(QtPS, "QPrinter", _FakePrinter)
    monkeypatch.setattr(QtPS, "QPrintDialog", _FakeDialog)
    monkeypatch.setattr(QtGui, "QPainter", _FakePainter)
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "d.ini"), QSettings.Format.IniFormat)
    tab = tp.TabPrint(s)
    events = []
    monkeypatch.setattr(tab, "_commit_print_record", lambda ok: events.append(("record", ok)))
    monkeypatch.setattr(tab, "_show_print_refusal",
                        lambda title, body: events.append(("refused", title)))
    # the conftest stub stands in for this method; the real one is under test
    monkeypatch.setattr(tab, "_print_native_qt", _REAL_PRINT_NATIVE_QT.__get__(tab))
    return tab, events


def test_an_a4_chart_prints_at_100_percent_centred(dialog_route, tmp_path):
    tab, events = dialog_route
    tiff = _rgb_tiff(tmp_path / "a4.tif", w=2339, h=3366)        # 198 x 285 mm at 300 dpi
    tab._print_native_qt([(tiff, 0)], printer="Office Inkjet")
    pr = _FakePrinter.instances[0]
    assert pr.full_page and pr.name == "Office Inkjet" and not pr.landscape
    (t, rot, x, y, w, h, _iw), = _FakePainter.draws
    assert rot == 0 and t == (0.0, 0.0)
    assert w == pytest.approx(2339 / 300 * 600) and h == pytest.approx(3366 / 300 * 600)
    page_w, page_h = round(595 / 72 * 600), round(842 / 72 * 600)
    assert x == pytest.approx((page_w - w) / 2) and y == pytest.approx((page_h - h) / 2)
    assert events == [("record", True)]


def test_a_small_chart_is_not_enlarged(dialog_route, tmp_path):
    tab, events = dialog_route
    tiff = _rgb_tiff(tmp_path / "a5.tif", w=1606, h=2339)        # 136 x 198 mm
    tab._print_native_qt([(tiff, 0)])
    (_t, _r, _x, _y, w, h, _iw), = _FakePainter.draws
    assert (w, h) == (pytest.approx(1606 * 2), pytest.approx(2339 * 2))


def test_a_landscape_chart_opens_the_dialog_in_landscape(dialog_route, tmp_path):
    tab, events = dialog_route
    tiff = _rgb_tiff(tmp_path / "l.tif", w=3366, h=2339)
    tab._print_native_qt([(tiff, 0)])
    assert _FakePrinter.instances[0].landscape
    (_t, rot, _x, _y, w, h, _iw), = _FakePainter.draws
    assert rot == 0 and w == pytest.approx(3366 * 2)


def test_a_chart_that_fits_only_turned_is_turned(dialog_route, tmp_path):
    """The user chose portrait in the dialog for a landscape chart."""
    tab, events = dialog_route
    tiff = _rgb_tiff(tmp_path / "l.tif", w=3366, h=2339)

    class _Portrait(_FakePrinter):
        def setPageOrientation(self, o):
            self.landscape = False
    import PyQt6.QtPrintSupport as QtPS
    QtPS.QPrinter = _Portrait
    tab._print_native_qt([(tiff, 0)])
    (t, rot, x, y, w, h, _iw), = _FakePainter.draws
    assert rot == 90
    page_w, page_h = round(595 / 72 * 600), round(842 / 72 * 600)
    # the image's 285 mm run down the page, its 198 mm across, centred
    assert t[0] == pytest.approx((page_w - h) / 2 + h)
    assert t[1] == pytest.approx((page_h - w) / 2)


def test_a_chart_larger_than_the_paper_is_refused_not_shrunk(dialog_route, tmp_path):
    from workflow import measurement_messages as MM
    tab, events = dialog_route
    tiff = _rgb_tiff(tmp_path / "a3.tif", w=3366, h=4819)        # 285 x 408 mm
    tab._print_native_qt([(tiff, 0)])
    assert _FakePainter.draws == []
    assert events == [("refused", MM.M_PRINT_WIN_DIALOG_TOO_BIG.title), ("record", False)]


def test_a_cmyk_chart_is_refused_before_the_dialog(dialog_route, tmp_path):
    from workflow import measurement_messages as MM
    tab, events = dialog_route
    tiff = _cmyk_tiff(tmp_path / "cmyk.tif")
    tab._print_native_qt([(tiff, 0)])
    assert _FakePrinter.instances == []                # no dialog was built
    assert events == [("refused", MM.M_PRINT_WIN_DIALOG_NOT_RGB.title), ("record", False)]


def test_a_cancelled_dialog_prints_nothing(dialog_route, tmp_path):
    tab, events = dialog_route
    _FakeDialog.accept = False
    tab._print_native_qt([(_rgb_tiff(tmp_path / "c.tif"), 0)])
    assert _FakePainter.draws == [] and events == [("record", False)]


def test_the_dialog_route_never_scales_into_the_viewport_again():
    from ui.tabs import tab_print as tp
    import inspect
    src = inspect.getsource(tp.TabPrint._print_native_qt)
    assert "KeepAspectRatio" not in src and "setViewport" not in src


# ---- 7. the real spooler, on a test queue only -------------------------------

@pytest.mark.real_spooler
@pytest.mark.skipif(sys.platform != "win32", reason="Windows spooler")
def test_a_raw_job_reaches_a_file_port_byte_for_byte(tmp_path):
    """Runs only where a ChromIQ-Test queue with a v3 driver on a file port
    exists (the development VM's bench); skipped elsewhere."""
    import time
    queue = "ChromIQ-Test Epson File"
    try:
        printers = win_spooler.list_printers()
    except OSError:
        pytest.skip("no spooler")
    if queue not in printers:
        pytest.skip(f"no {queue!r} queue on this machine")
    import ctypes
    port = None
    try:
        import subprocess
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              f"(Get-Printer '{queue}').PortName"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout.strip()
        port = Path(out) if out else None
    except Exception:  # noqa: BLE001
        port = None
    if port is None or not port.parent.is_dir():
        pytest.skip("the test queue has no file port")
    data = b"%!PS-Adobe-3.0\n%% ChromIQ test " + str(time.time()).encode() + b"\nshowpage\n"
    # Windows set to manage the default printer makes the queue printed to
    # last the default: hand the user's default back afterwards
    default = win_spooler.default_printer()
    try:
        win_spooler.submit(queue, data, "ChromIQ test")
        for _ in range(60):
            time.sleep(0.5)
            if port.exists() and port.read_bytes() == data:
                break
    finally:
        if default:
            time.sleep(1.0)
            ctypes.WinDLL("winspool.drv").SetDefaultPrinterW(default)
    assert port.read_bytes() == data
    assert win_spooler.default_printer() == default


# ---- 8. a DeviceN chart's inks each reach their own colorant ------------------
# Found by rendering the Windows route's port files with Ghostscript (#205,
# 2026-10-20), and true of the macOS direct route alike: `colorimage` ignores
# the current colour space, so ChromIQ's DeviceN chart was drawn as CMYK (a
# CMY + Orange chart's orange on the BLACK plane) and a 5 to 7 ink chart ended
# in /rangecheck. Report folder 01_spooler_round_trip/devicen_proof_*.json.

def _ink_tiff(path: Path, codes, value=200) -> Path:
    import json
    import tifffile
    n = len(codes)
    arr = np.zeros((8, 8 * n, n), np.uint8)
    for i in range(n):
        arr[:, i * 8:(i + 1) * 8, i] = value
    kw = dict(photometric="separated", resolution=(300, 300), resolutionunit=2)
    if n > 4:
        kw["extrasamples"] = ("unspecified",) * (n - 4)
    tifffile.imwrite(str(path), arr, **kw)
    path.with_suffix(".channels.json").write_text(
        json.dumps({"ink_channels": list(codes)}), encoding="utf-8")
    return path


@pytest.mark.parametrize("codes", [["c", "m", "y", "o"], ["c", "m", "y", "k", "lc", "lm"]])
def test_a_devicen_chart_is_drawn_in_its_own_colour_space(tmp_path, codes):
    import base64
    import re
    import zlib
    from workflow.postscript_generator import PostScriptGenerator
    tif = _ink_tiff(tmp_path / "inks.tif", codes)
    ps = PostScriptGenerator().generate(tif, ink_channels=codes)
    assert "[/DeviceN [" in ps
    assert "colorimage" not in ps
    assert f"/Decode [{' '.join(['0 1'] * len(codes))}]" in ps
    start = ps.index(">> image\n") + len(">> image\n")
    data = zlib.decompress(base64.a85decode(re.sub(r"\s", "", ps[start:ps.index("~>", start)])))
    import tifffile
    assert data == tifffile.imread(str(tif)).tobytes()


def test_rgb_and_cmyk_charts_keep_colorimage(tmp_path):
    import tifffile
    from workflow.postscript_generator import PostScriptGenerator
    rgb = _rgb_tiff(tmp_path / "rgb.tif")
    cmyk = tmp_path / "cmyk.tif"
    tifffile.imwrite(str(cmyk), np.zeros((8, 8, 4), np.uint8), photometric="separated",
                     resolution=(300, 300), resolutionunit=2)
    for tif, n in ((rgb, 3), (cmyk, 4)):
        ps = PostScriptGenerator().generate(tif)
        assert f"false {n}\ncolorimage\n" in ps and ">> image" not in ps


def _ghostscript() -> "str | None":
    import shutil
    return shutil.which("gswin64c") or shutil.which("gs")


@pytest.mark.skipif(_ghostscript() is None, reason="needs Ghostscript")
def test_ghostscript_puts_every_ink_on_its_own_plane(tmp_path):
    import subprocess
    import tifffile
    from workflow.postscript_generator import PostScriptGenerator
    codes = ["c", "m", "y", "o"]
    tif = _ink_tiff(tmp_path / "cmyo.tif", codes)
    psf = tmp_path / "cmyo.ps"
    psf.write_text(PostScriptGenerator().generate(tif, ink_channels=codes), encoding="ascii")
    subprocess.run([_ghostscript(), "-q", "-dSAFER", "-dBATCH", "-dNOPAUSE",
                    "-sDEVICE=tiffsep", "-r300", f"-sOutputFile={tmp_path / 'p.tif'}",
                    str(psf)], check=True, timeout=120)
    orange = 255 - tifffile.imread(str(tmp_path / "p(Orange).tif")).astype(int)
    black = 255 - tifffile.imread(str(tmp_path / "p(Black).tif")).astype(int)
    assert orange[4, 3 * 8 + 4] == 200 and black.max() == 0


# ---- 9. Windows 11's own print dialog keeps its own printer ---------------------
# Measured (report folder 03, probe_preselect_*.json): with a parent window the
# dialog Windows 11 shows opens on the printer last used from the app, whatever
# Qt preselects. On ChromIQ's own route that is the printer handed over.

class _ElsewhereDialog(_FakeDialog):
    def exec(self):
        self.printer.setPrinterName("Office Laser")     # the dialog's own choice
        return super().exec()


@pytest.mark.parametrize("answer", [True, False])
def test_another_printer_from_the_dialog_is_asked_about(dialog_route, tmp_path, monkeypatch, answer):
    import PyQt6.QtPrintSupport as QtPS
    tab, events = dialog_route
    monkeypatch.setattr(QtPS, "QPrintDialog", _ElsewhereDialog)
    asked = []
    monkeypatch.setattr(tab, "_confirm_other_printer",
                        lambda wanted, chosen: asked.append((wanted, chosen)) or answer)
    tab._print_native_qt([(_rgb_tiff(tmp_path / "c.tif"), 0)], printer="Office Inkjet")
    assert asked == [("Office Inkjet", "Office Laser")]
    assert bool(_FakePainter.draws) is answer
    assert events[-1] == ("record", answer)


def test_the_plain_dialog_route_never_asks(dialog_route, tmp_path, monkeypatch):
    """No printer handed over (the default route): whatever the dialog chose."""
    import PyQt6.QtPrintSupport as QtPS
    tab, events = dialog_route
    monkeypatch.setattr(QtPS, "QPrintDialog", _ElsewhereDialog)
    monkeypatch.setattr(tab, "_confirm_other_printer",
                        lambda *a: pytest.fail("asked on the dialog route"))
    tab._print_native_qt([(_rgb_tiff(tmp_path / "c.tif"), 0)])
    assert _FakePainter.draws and events == [("record", True)]


# ---- 10. a printer's old option rows are gone at once -----------------------------
def test_removed_option_rows_are_hidden_at_once(qapp, tmp_path):
    """Seen on screen (#205): the rows of the printer before stayed drawn over
    the new printer's box while a window opened right after the change was
    up, because a deferred delete waits for that window's exec() to end."""
    from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
    from ui.tabs.tab_print import TabPrint
    host = QWidget()
    outer = QVBoxLayout(host)
    row = QHBoxLayout()
    lbl = QLabel("Media Type:", host)
    row.addWidget(lbl)
    outer.addLayout(row)
    box = QLabel("box", host)
    outer.addWidget(box)
    host.show()
    qapp.processEvents()
    assert lbl.isVisible()
    TabPrint._clear_layout(outer)
    assert lbl.isHidden() and box.isHidden()      # before any event is processed
    host.close()
