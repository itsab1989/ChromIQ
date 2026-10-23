"""Native macOS print path (PyObjC): the macOS print dialog, and a job in the
printer state a Photoshop print gets when "Photoshop manages colours".

Opens the standard macOS print panel via ``NSPrintPanel`` / ``NSPrintOperation``
and submits the profiling-target bitmap at its exact generated size (no
scaling).

What decides the printer state, measured on macOS 27.0.1 (report folder
``2026-10-08_print_fix``):

* Photoshop's own contribution to the job ticket is one key,
  ``AP_ColorMatchingMode`` = ``AP_ApplicationColorMatching``; everything else is
  written by the driver's dialog extension for the medium chosen.  ChromIQ sets
  that key (locked, before and after the dialog).  For printers whose dialog
  picks a paper profile (Canon IJ, Epson: ``ppd_color.PAPER_PROFILE_RULES``) it
  sets nothing else, so the ticket equals a Photoshop print's.  For any other
  printer it still locks the driver's own "no colour adjustment" option found in
  the PPD (e.g. HP), as before.
* macOS 27 spools an ``NSDeviceRGBColorSpace`` bitmap tagged as sRGB, and its
  rasteriser converts tagged colour to the job's output profile (the paper
  profile).  After the dialog ChromIQ reads that profile
  (``_destination_rgb_profile``) and re-tags the chart with exactly it, so the
  conversion is the identity and the chart's own numbers reach the driver.
* After submission the job is read back from CUPS (``workflow.print_ticket``),
  not from ChromIQ's own dictionary.  ``print_frames`` only records what it
  submitted (``last_submission``); the Print Chart tab reads the job back on a
  background thread (``read_back``), with a timeout, and learns the paper
  profile the dialog wrote (``workflow.printer_memory``).

``PMPrintSettingsSetValue`` is not wrapped by PyObjC, so it is called through
``ctypes`` against PrintCore; so are the ``PMSession*WithColorSyncProfiles``
read and the ColorSync profile accessors.

macOS only.  Imported lazily by ``ui/tabs/tab_print.py`` when
``sys.platform == "darwin"``.
"""
from __future__ import annotations

import ctypes
from pathlib import Path

from PIL import Image

from core.logger import get_logger
from workflow.ppd_color import (cmyk_raster_space, is_postscript_queue,
                                paper_profile_for, vendor_no_cm_settings)

log = get_logger(__name__)

_PT_PER_INCH = 72.0

# PrintCore ``PMPrintSettings`` key/values that put the job into
# application-managed colour.  These are vendor-neutral — they come from Apple's
# print framework, not the driver.  Only ``AP_ColorMatchingMode`` is set here:
# ColorByte Print-Tool's no-colour-management path sets *exactly* this one Apple
# key (to ``AP_ApplicationColorMatching``) and nothing else — notably it never
# names a source profile.  We previously also set
# ``APCustomColorMatchingProfile = "sRGB"``; that was removed because it
# *declares an sRGB source*, which invites the driver/ColorSync to transform
# sRGB→device (i.e. the very colour management we are trying to suppress) — the
# likely reason Canon drivers still profiled the chart.  Under
# ``AP_ApplicationColorMatching`` a custom source profile is meaningless anyway:
# the application is asserting the pixels are already device-ready.
#
# Beta 15: the session-level calls that used to follow (re-declaring the
# printer's default output intent as the application's, after ColorByte
# Print-Tool) are gone. Phase 1 (2026-10-08) measured that they change nothing on
# macOS 27, and Photoshop's own ticket carries only the key above. The key is set
# *locked* so it cannot be silently rewritten between dialog and submission.
# ``vendor_no_cm_settings`` still adds a driver's own "No Color Adjustment"
# option for printers OUTSIDE ``ppd_color.PAPER_PROFILE_RULES`` (e.g. HP); for
# Canon IJ and Epson the driver's dialog writes what a Photoshop print carries.
_LOCKED_COLOR_SETTINGS: dict[str, str] = {
    "AP_ColorMatchingMode": "AP_ApplicationColorMatching",
}


def is_available() -> bool:
    """True if the PyObjC AppKit bridge is importable on this machine."""
    try:
        import AppKit  # noqa: F401
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# PrintCore (ApplicationServices) glue — PMPrintSettingsSetValue isn't wrapped
# by PyObjC, so we call it directly via ctypes on the opaque PMPrintSettings
# pointer that -[NSPrintInfo PMPrintSettings] returns.
# --------------------------------------------------------------------------
_kCFStringEncodingUTF8 = 0x08000100

try:  # pragma: no cover - macOS only
    _libobjc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    _libobjc.sel_registerName.restype = ctypes.c_void_p
    _libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
    _libobjc.objc_msgSend.restype = ctypes.c_void_p
    _libobjc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    _cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    _cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    _cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
    _cf.CFRelease.restype = None
    _cf.CFRelease.argtypes = [ctypes.c_void_p]
    # Read-only dictionary access + a UTF-8 snapshot of a CFString, used purely
    # to log which device profile the print system hands us as the output
    # intent (mirrors Print-Tool's "OutputIntent = %@" NSLog diagnostics).
    _cf.CFDictionaryGetValue.restype = ctypes.c_void_p
    _cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    _cf.CFStringGetCString.restype = ctypes.c_bool
    _cf.CFStringGetCString.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32,
    ]

    _appsvc = ctypes.CDLL(
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
    )
    _appsvc.PMPrintSettingsSetValue.restype = ctypes.c_int32  # OSStatus
    _appsvc.PMPrintSettingsSetValue.argtypes = [
        ctypes.c_void_p,  # PMPrintSettings
        ctypes.c_void_p,  # CFStringRef key
        ctypes.c_void_p,  # CFTypeRef value
        ctypes.c_bool,    # Boolean locked
    ]
    # ColorSync lives inside the ApplicationServices umbrella; used to log the
    # human-readable name of whichever device profile we declare as the output
    # intent (diagnostics only).
    _appsvc.ColorSyncProfileCopyDescriptionString.restype = ctypes.c_void_p  # CFStringRef
    _appsvc.ColorSyncProfileCopyDescriptionString.argtypes = [ctypes.c_void_p]
    _PRINTCORE_OK = True
except Exception as _exc:  # pragma: no cover
    _PRINTCORE_OK = False
    log.warning("PrintCore ctypes setup failed; colour-matching lock disabled: %s", _exc)

# Session-level colour APIs (the PMSession*WithColorSyncProfiles family) are
# bound separately so that, if any is missing on this OS, the working
# PMPrintSettings lock above is *not* disabled with them.  Signatures were
# recovered from ColorByte Print-Tool 2.3.4's arm64 disassembly: every call in
# the family takes (PMPrintSession session, PMPrintSettings settings, payload),
# confirmed at its ``runPrintSettings:`` call site (x0=PMPrintSession from
# ``-[NSPrintInfo PMPrintSession]``, x1=PMPrintSettings).  These are the modern
# *WithColorSyncProfiles variants — distinct from the bare
# PMSessionSetApplicationOutputIntent / PMSessionCopyDefaultOutputIntent that
# SIGABRT on the NSPrintInfo-vended session — and Print-Tool calls them on
# exactly that session without crashing.
if _PRINTCORE_OK:
    try:  # pragma: no cover - macOS only
        _appsvc.PMSessionSetColorMatchingMode.restype = ctypes.c_int32  # OSStatus
        _appsvc.PMSessionSetColorMatchingMode.argtypes = [
            ctypes.c_void_p,  # PMPrintSession
            ctypes.c_void_p,  # PMPrintSettings
            ctypes.c_void_p,  # CFStringRef mode
        ]
        _appsvc.PMSessionCopyDefaultOutputIntentWithColorSyncProfiles.restype = ctypes.c_int32
        _appsvc.PMSessionCopyDefaultOutputIntentWithColorSyncProfiles.argtypes = [
            ctypes.c_void_p,                # PMPrintSession
            ctypes.c_void_p,                # PMPrintSettings
            ctypes.POINTER(ctypes.c_void_p),  # CFDictionaryRef* out
        ]
        _appsvc.PMSessionSetApplicationOutputIntentWithColorSyncProfiles.restype = ctypes.c_int32
        _appsvc.PMSessionSetApplicationOutputIntentWithColorSyncProfiles.argtypes = [
            ctypes.c_void_p,  # PMPrintSession
            ctypes.c_void_p,  # PMPrintSettings
            ctypes.c_void_p,  # CFDictionaryRef intents
        ]
        _appsvc.ColorSyncProfileCopyData.restype = ctypes.c_void_p
        _appsvc.ColorSyncProfileCopyData.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        _cf.CFDataGetLength.restype = ctypes.c_long
        _cf.CFDataGetLength.argtypes = [ctypes.c_void_p]
        _cf.CFDataGetBytePtr.restype = ctypes.c_void_p
        _cf.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
        _PM_SESSION_OK = True
    except Exception as _exc2:  # pragma: no cover
        _PM_SESSION_OK = False
        log.warning("PrintCore session colour APIs unavailable: %s", _exc2)
else:  # pragma: no cover
    _PM_SESSION_OK = False


# Custom paper with the driver's minimum margins (beta 16 package).  Bound on
# their own so a missing symbol leaves the colour lock above untouched.
class _PMRect(ctypes.Structure):
    """PrintCore ``PMRect`` / ``PMPaperMargins``: top, left, bottom, right."""
    _fields_ = [("top", ctypes.c_double), ("left", ctypes.c_double),
                ("bottom", ctypes.c_double), ("right", ctypes.c_double)]


if _PRINTCORE_OK:
    try:  # pragma: no cover - macOS only
        _appsvc.PMSessionGetCurrentPrinter.restype = ctypes.c_int32
        _appsvc.PMSessionGetCurrentPrinter.argtypes = [ctypes.c_void_p,
                                                       ctypes.POINTER(ctypes.c_void_p)]
        _appsvc.PMPaperCreateCustom.restype = ctypes.c_int32
        _appsvc.PMPaperCreateCustom.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_double,
            ctypes.c_double, ctypes.POINTER(_PMRect), ctypes.POINTER(ctypes.c_void_p)]
        _appsvc.PMCreatePageFormatWithPMPaper.restype = ctypes.c_int32
        _appsvc.PMCreatePageFormatWithPMPaper.argtypes = [ctypes.POINTER(ctypes.c_void_p),
                                                          ctypes.c_void_p]
        _appsvc.PMCopyPageFormat.restype = ctypes.c_int32
        _appsvc.PMCopyPageFormat.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        _appsvc.PMGetPageFormatPaper.restype = ctypes.c_int32
        _appsvc.PMGetPageFormatPaper.argtypes = [ctypes.c_void_p,
                                                 ctypes.POINTER(ctypes.c_void_p)]
        _appsvc.PMPaperGetMargins.restype = ctypes.c_int32
        _appsvc.PMPaperGetMargins.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMRect)]
        _appsvc.PMPaperGetWidth.restype = ctypes.c_int32
        _appsvc.PMPaperGetWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]
        _appsvc.PMPaperGetHeight.restype = ctypes.c_int32
        _appsvc.PMPaperGetHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]
        _appsvc.PMRelease.restype = ctypes.c_int32
        _appsvc.PMRelease.argtypes = [ctypes.c_void_p]
        # k81: ChromIQ's own PostScript, submitted with the dialog's ticket
        _appsvc.PMPrinterPrintWithFile.restype = ctypes.c_int32
        _appsvc.PMPrinterPrintWithFile.argtypes = [ctypes.c_void_p] * 5
        # 4.3.5 beta 2: the PostScript job's title in the print queue
        _appsvc.PMPrintSettingsSetJobName.restype = ctypes.c_int32
        _appsvc.PMPrintSettingsSetJobName.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        _PM_PAPER_OK = True
    except Exception as _exc3:  # pragma: no cover
        _PM_PAPER_OK = False
        log.warning("PrintCore paper APIs unavailable: %s", _exc3)
else:  # pragma: no cover
    _PM_PAPER_OK = False


def _cfstr(value: str) -> int:
    """Create a CFStringRef (returns its pointer as int).  Caller must CFRelease."""
    return _cf.CFStringCreateWithCString(None, value.encode("utf-8"), _kCFStringEncodingUTF8)


def _cfstr_to_py(cfstr_ptr: int) -> str | None:
    """Best-effort UTF-8 snapshot of a CFStringRef for logging; None on failure."""
    if not cfstr_ptr:
        return None
    buf = ctypes.create_string_buffer(512)
    if _cf.CFStringGetCString(
        ctypes.c_void_p(cfstr_ptr), buf, len(buf), _kCFStringEncodingUTF8
    ):
        return buf.value.decode("utf-8", "replace")
    return None


def _queue_name(display_name: str) -> str:
    """Map an ``NSPrinter`` display name (e.g. "EPSON ET-8550") to its CUPS
    queue name (e.g. "EPSON_ET_8550"), which is what the PPD file is keyed by.
    Falls back to *display_name* unchanged if the lookup fails."""
    try:
        import cups
        printers = cups.Connection().getPrinters()
        if display_name in printers:
            return display_name
        for queue, attrs in printers.items():
            if attrs.get("printer-info") == display_name:
                return queue
    except Exception:
        pass
    return display_name


def _locked_settings_for(print_info, after_dialog: bool = False) -> dict[str, str]:
    """The full set of (key, value) pairs to lock for *print_info* — the
    vendor-neutral base plus, if found, the selected printer's own no-colour
    options (all of them: HP colour lasers split the choice over per-object
    options like HPTextRGB / HPGraphicsRGB / HPPhotoRGB).

    *after_dialog*: for a Canon IJ / Epson queue, also the driver options the
    dialog's Color Matching sheet can set away from a Photoshop print's
    (``ppd_color.dialog_route_colour_locks``: Epson's EPIJ_OSColMat)."""
    settings = dict(_LOCKED_COLOR_SETTINGS)
    try:
        printer = print_info.printer()
        display = printer.name() if printer is not None else None
        if display:
            from workflow.print_manager import PrintModule
            ppd = PrintModule.find_ppd_path(_queue_name(display))
            if ppd and _is_reference_vendor(ppd):
                # Canon IJ / Epson (ppd_color.PAPER_PROFILE_RULES): the job
                # carries what a Photoshop print carries, the Apple key alone;
                # the driver's dialog writes the medium and its paper profile.
                if after_dialog:
                    # …except where the Color Matching sheet wrote another
                    # value than a Photoshop print carries: B5, 2026-10-10,
                    # "EPSON Color Matching" chosen there reached the job as
                    # EPIJ_OSColMat=1 and the status line still confirmed it.
                    # Set back to the Photoshop print's value after the
                    # dialog (before it, the sheet shows what the user had),
                    # and read back like every other locked key.
                    from core.text_io import read_text
                    from workflow.ppd_color import dialog_route_colour_locks
                    settings.update(dialog_route_colour_locks(
                        read_text(Path(ppd), lenient=True)))
                return settings
            if ppd:
                for key, val in vendor_no_cm_settings(ppd):
                    settings[key] = val
                    log.info("native print: driver no-colour option %s=%s", key, val)
    except Exception as exc:
        log.warning("native print: vendor PPD scan failed: %s", exc)
    return settings


def _is_reference_vendor(ppd_path: str) -> bool:
    """True for a PPD whose driver dialog picks a paper profile (Canon IJ, Epson)."""
    try:
        from core.text_io import read_text
        return paper_profile_for(read_text(Path(ppd_path), lenient=True)) is not None
    except Exception:  # noqa: BLE001
        return False


def _refuse_unless_rgb(tiff_path: Path, frame: int) -> None:
    """Raise :class:`ChartIsNotRGB`, naming the chart's inks, for any page that
    is not RGB in its file and in its ink list (``chart_inks.is_rgb_page``)."""
    from workflow import chart_inks
    try:
        if chart_inks.is_rgb_page(tiff_path, frame):
            return
        n, _phot = chart_inks.page_photometric(tiff_path, frame)
    except Exception:  # noqa: BLE001 - unreadable by tifffile: PIL decides below
        return
    codes = chart_inks.sidecar_ink_codes(tiff_path)
    if n == 1 and not codes:
        raise ChartIsNotRGB(chart_inks.ink_set_label(["k"]))
    plan = chart_inks.plan_for_file(tiff_path, frame, codes)
    raise ChartIsNotRGB(chart_inks.ink_set_label(
        plan.codes if plan is not None else codes, n))


class ChartIsNotRGB(RuntimeError):
    """The chart's own pixels are not RGB, and this route can only carry RGB.

    **THE SILENT CASE WAS EXACTLY FOUR INKS** (adversary round 26, R26-F8).
    `use_native_print_dialog` defaults to True on macOS, so this is the route a
    chart takes unless the user changes a setting, and it built every page
    through `Image.convert("RGB")` into an `NSDeviceRGBColorSpace` bitmap. On a
    real `targen -d4` chart, measured: CMYK ``75,0,128,255`` reached the driver
    as RGB ``0,0,0``, and ``255,255,0,136`` as ``0,0,119``. PIL's CMYK to RGB
    is a naive formula, not a conversion anybody asked for, and nothing said a
    word: the sheet then disagrees with the `.ti2`, and the `.ti3` measured
    from it is paired with values that were never printed.

    An RGB chart is unaffected (`convert` is a no-op). A six-ink chart already
    failed loudly, because PIL cannot open it at all. Four inks was the one
    case that went through quietly, which is why this refusal exists rather
    than a warning.

    Printing a CMYK chart correctly through the native dialog would mean an
    `NSDeviceCMYKColorSpace` rep and a way to prove on paper that macOS left it
    alone, and that cannot be proved without a printer and an instrument. Until
    it is, the standard route - PostScript hex values through ``lp -o raw``,
    which is what `PostScriptGenerator` exists for - is the one that carries
    the chart's own numbers.
    """


#: What the last ``_lock_no_color_management(after_dialog=True)`` found the
#: dialog had written for a key it then set back: {key: (dialog's, ChromIQ's)}.
last_reset_by_chromiq: dict[str, tuple[str, str]] = {}


def _lock_no_color_management(print_info, after_dialog: bool = False) -> dict[str, str]:
    """Set the application-colour-matching keys (locked) on *print_info*'s
    PrintCore ``PMPrintSettings`` and sync them back into the Cocoa layer.

    Also mirrors the keys into the Cocoa ``printSettings`` dict as a fallback.
    Best-effort: logs and continues if PrintCore is unavailable.  Returns the
    keys it set (what the read-back expects the job to carry).
    *after_dialog*: see ``_locked_settings_for``; a key the dialog had set
    to another value is logged and kept in ``last_reset_by_chromiq``.
    """
    import objc

    global last_reset_by_chromiq
    locked = _locked_settings_for(print_info, after_dialog=after_dialog)

    # Cocoa-dict fallback first (cheap, always works).
    cocoa = print_info.printSettings()
    if after_dialog:
        last_reset_by_chromiq = {}
        for key, value in locked.items():
            if key in _LOCKED_COLOR_SETTINGS:
                continue
            had = cocoa.get(key) if hasattr(cocoa, "get") else None
            if had is not None and str(had) != value:
                last_reset_by_chromiq[key] = (str(had), value)
                log.warning("native print: the dialog set %s=%s; set back to %s, "
                            "as a Photoshop print carries it", key, had, value)
    for key, value in locked.items():
        cocoa[key] = value

    if not _PRINTCORE_OK:
        return locked
    try:
        pm_ptr = _libobjc.objc_msgSend(
            ctypes.c_void_p(objc.pyobjc_id(print_info)),
            _libobjc.sel_registerName(b"PMPrintSettings"),
        )
        if not pm_ptr:
            log.warning("native print: PMPrintSettings() returned NULL")
            return locked
        for key, value in locked.items():
            k_ref = _cfstr(key)
            v_ref = _cfstr(value)
            try:
                status = _appsvc.PMPrintSettingsSetValue(
                    ctypes.c_void_p(pm_ptr),
                    ctypes.c_void_p(k_ref),
                    ctypes.c_void_p(v_ref),
                    True,  # locked
                )
                if status != 0:
                    log.warning("native print: PMPrintSettingsSetValue(%s) -> %d", key, status)
            finally:
                if k_ref:
                    _cf.CFRelease(ctypes.c_void_p(k_ref))
                if v_ref:
                    _cf.CFRelease(ctypes.c_void_p(v_ref))
        if hasattr(print_info, "updateFromPMPrintSettings"):
            print_info.updateFromPMPrintSettings()
    except Exception as exc:
        log.warning("native print: locking colour-matching failed: %s", exc)
    return locked


def _destination_rgb_profile(print_info) -> tuple[bytes | None, str | None]:
    """The RGB profile macOS will convert this job's tagged colour INTO.

    macOS 27 spools an ``NSDeviceRGBColorSpace`` bitmap tagged as sRGB, and its
    rasteriser then converts it to the output intent of the job: the paper
    profile the driver's dialog chose (phase 1, 2026-10-08: 62.5 % of a Canon
    test chart's pixels changed, blue 0,0,255 to 25,54,254; the Epson the same).
    ``PMSessionCopyDefaultOutputIntentWithColorSyncProfiles`` on the FINAL
    ticket names that profile; tagging the chart with exactly it makes the
    conversion the identity, which is what ColorSync Utility's "Print as color
    target" does.  Returns (ICC bytes, description) or (None, None).
    """
    if not (_PRINTCORE_OK and _PM_SESSION_OK):
        return None, None
    import objc

    intents = ctypes.c_void_p(0)
    try:
        pid = objc.pyobjc_id(print_info)
        session = _libobjc.objc_msgSend(
            ctypes.c_void_p(pid), _libobjc.sel_registerName(b"PMPrintSession"))
        settings = _libobjc.objc_msgSend(
            ctypes.c_void_p(pid), _libobjc.sel_registerName(b"PMPrintSettings"))
        if not session or not settings:
            log.warning("native print: PMPrintSession/Settings NULL, no output intent")
            return None, None
        status = _appsvc.PMSessionCopyDefaultOutputIntentWithColorSyncProfiles(
            ctypes.c_void_p(session), ctypes.c_void_p(settings), ctypes.byref(intents))
        if status != 0 or not intents.value:
            log.warning("native print: CopyDefaultOutputIntent -> %d, no profile", status)
            return None, None
        k_ref = _cfstr("PMSessionRGBOutputIntent")
        try:
            prof = _cf.CFDictionaryGetValue(intents, ctypes.c_void_p(k_ref))
        finally:
            _cf.CFRelease(ctypes.c_void_p(k_ref))
        if not prof:
            return None, None
        data = None
        d_ref = _appsvc.ColorSyncProfileCopyData(ctypes.c_void_p(prof), None)
        if d_ref:
            n = _cf.CFDataGetLength(ctypes.c_void_p(d_ref))
            ptr = _cf.CFDataGetBytePtr(ctypes.c_void_p(d_ref))
            data = ctypes.string_at(ptr, n)
            _cf.CFRelease(ctypes.c_void_p(d_ref))
        name = None
        desc_ref = _appsvc.ColorSyncProfileCopyDescriptionString(ctypes.c_void_p(prof))
        if desc_ref:
            name = _cfstr_to_py(desc_ref)
            _cf.CFRelease(ctypes.c_void_p(desc_ref))
        return data, name
    except Exception as exc:  # noqa: BLE001
        log.warning("native print: reading the output intent failed: %s", exc)
        return None, None
    finally:
        if intents.value:
            _cf.CFRelease(intents)


def _retag_reps(reps: list, icc: bytes) -> list | None:
    """*reps* re-tagged with the colour space of *icc*, pixels untouched
    (``bitmapImageRepByRetaggingWithColorSpace:`` changes the tag, not the
    samples); None when *icc* is not a usable RGB colour space."""
    import AppKit
    import Foundation
    cs = AppKit.NSColorSpace.alloc().initWithICCProfileData_(
        Foundation.NSData.dataWithBytes_length_(icc, len(icc)))
    if cs is None:
        return None
    out = []
    for r in reps:
        t = r.bitmapImageRepByRetaggingWithColorSpace_(cs)
        if t is None:
            return None
        out.append(t)
    return out


#: What the last ``print_frames`` submitted (a ``Submission``), or None when
#: nothing was submitted.  ``read_back`` turns it into a ``TicketReport``.
last_submission = None


class Submission:
    """One job handed to the spooler by ``print_frames``, enough to find and
    judge it in CUPS later (off the GUI thread)."""

    def __init__(self, printer_display: str | None, expected: dict,
                 started: float, tagged_icc: bytes, tagged_with: str | None,
                 output_intent: str | None = None) -> None:
        self.printer_display = printer_display
        self.queue: str | None = None
        self.ppd_text: str | None = None
        self.expected = dict(expected)
        self.started = started
        self.tagged_icc = tagged_icc
        self.tagged_with = tagged_with
        #: the name of the profile macOS converts this job's colour into
        #: (its output intent), or None when none could be read
        self.output_intent = output_intent
        #: driver options the dialog had set away from a Photoshop print's
        #: and ChromIQ set back: {key: (dialog's, ChromIQ's)} (B5)
        self.reset_by_chromiq: dict[str, tuple[str, str]] = {}
        #: k81: ChromIQ's own PostScript went to a PostScript printer, the
        #: chart as DeviceRGB (no tag, no output intent to match)
        self.device_rgb = False
        #: 4.3.5 beta 2: on a PostScript printer, the form the chart went in
        #: (``POSTSCRIPT_DEVICE_RGB`` / ``POSTSCRIPT_AS_MACOS``), else None
        self.postscript_form: "str | None" = None
        #: the CMYK family the job is rasterised in when the chart was left
        #: untagged for it (4.3.5, ``cmyk_raster_job``), else None
        self.cmyk_raster: str | None = None


#: PrintCore's colour space model of a job (``PMColorSpaceModel``): 3 is
#: kPMCMYKColorSpaceModel. macOS writes it into the print settings and the job
#: ticket from the queue's PPD; it is used only to VETO a CMYK verdict.
_PM_CMYK_COLOR_SPACE_MODEL = 3


def _pm_colour_space_model(settings: dict) -> "int | None":
    for k, v in settings.items():
        if "PMColorSpaceModel" in str(k):
            try:
                return int(str(v))
            except ValueError:
                return None
    return None


def cmyk_raster_job(ppd_text: "str | None", settings: dict,
                    queue: "str | None") -> "str | None":
    """The CMYK family a job with these options is rasterised in, or None.

    4.3.5 (Basti, 2026-10-10, option 3 of B5's analysis): on a queue whose
    driver takes CUPS raster in a CMYK-family colour space, macOS converts the
    chart from its own tag into CMYK and ignores an RGB profile assigned to
    the printer in ColorSync (review R3 and B5, measured on capture queues),
    so the re-tag would make the sheet depend on that profile. (A CMYK profile
    assigned there is used for the conversion, review R1; it was never a
    re-tag, which takes an RGB profile only.) Strict: the PPD
    must declare it for the job's own colour mode
    (``ppd_color.raster_colour``), and macOS's own colour space model of the
    job, when it states one, must be CMYK too."""
    settings = {str(k): v for k, v in (settings or {}).items()}
    cmyk = cmyk_raster_space(ppd_text, settings, queue)
    if cmyk is None:
        return None
    pm = _pm_colour_space_model(settings)
    if pm is not None and pm != _PM_CMYK_COLOR_SPACE_MODEL:
        log.info("native print: the PPD declares %s raster, macOS's colour space "
                 "model is %s: not treated as CMYK", cmyk, pm)
        return None
    return cmyk


def read_back(sub: "Submission"):
    """Find *sub*'s job in CUPS and read it back (blocking: run it through
    ``print_ticket.BackgroundReadBack``).  The chart's tag is compared with the
    job's paper profile by bytes."""
    from workflow.print_ticket import check_job, find_job
    if sub.printer_display:
        sub.queue = _queue_name(sub.printer_display)
        from workflow.print_manager import PrintModule
        ppd = PrintModule.find_ppd_path(sub.queue)
        if ppd:
            from core.text_io import read_text
            try:
                sub.ppd_text = read_text(Path(ppd), lenient=True)
            except OSError:
                sub.ppd_text = None
    job = find_job(sub.queue, sub.started) if sub.queue else None
    rep = check_job(sub.queue or "?", job, sub.expected, ppd_text=sub.ppd_text,
                    tagged_with=sub.tagged_with, tagged_icc=sub.tagged_icc)
    if sub.cmyk_raster and rep.read:
        # 4.3.5: the chart was left untagged because the options after the
        # dialog put the job into CMYK raster. Decided again from the colour
        # mode the job READ BACK carries: only if that is CMYK raster too is
        # the untagged chart expected; otherwise the window below says that
        # macOS may convert it, as before 4.3.5.
        rep.cmyk_raster = cmyk_raster_job(sub.ppd_text, rep.options, sub.queue)
        if rep.cmyk_raster is None:
            log.warning("native print: the job read back is not CMYK raster, "
                        "although its options after the dialog were (%s)",
                        sub.cmyk_raster)
    rep.device_rgb = bool(getattr(sub, "device_rgb", False))
    if (not rep.device_rgb and not sub.tagged_icc and rep.read
            and rep.tag_matches_job is None
            and not rep.cmyk_raster
            and (sub.output_intent
                 or (sub.ppd_text and "*cupsICCProfile" in sub.ppd_text))):
        # …AND ANY JOB WITH AN OUTPUT INTENT THE CHART DID NOT GET (B3,
        # 2026-10-10). A generic PostScript queue declares no profile in its
        # PPD, but a profile assigned to the printer in ColorSync Utility (as
        # on Knut's HP CLJ5550) is its output intent all the same. Measured on
        # a capture queue set up like his, with the re-tag withheld: macOS
        # changed the chart's numbers by 18.6 levels on average (max 107),
        # and the status line still said nothing but "application colour
        # matching".
        # Any printer whose PPD names profiles macOS can match to (HP DesignJet
        # and the like, not only Canon/Epson): the chart went untagged, so macOS
        # may convert it, and the status line must not say otherwise. A PPD
        # without profiles (no output intent at all) stays quiet: measured on
        # the sample HP DeskJet queue, its raster is byte-identical to beta 14's.
        rep.tag_matches_job = False
    rep.reset_by_chromiq = dict(sub.reset_by_chromiq)
    if (sub.tagged_icc and sub.tagged_with and rep.read and rep.paper_profile is None
            and is_postscript_queue(sub.ppd_text)):
        # M-PRINT-JOB-TAGGED-INTENT (approved by Basti, 2026-10-10), on
        # PostScript queues ONLY: there the chart's numbers were measured to
        # reach the printer unchanged with the job's profile attached (review
        # R3, 1,372,807 of 1,372,807 pixels). On a raster queue (the CUPS
        # sample HP DeskJet, CMYK) macOS converts from the chart's tag and
        # ignores the job's profile, so the sentence would be untrue there.
        rep.tagged_intent = sub.tagged_with
    return rep


# The print view is registered with the Objective-C runtime on first import;
# it must live at module scope so re-printing doesn't re-register the class.
try:  # pragma: no cover - macOS only
    import AppKit as _AppKit
    import Foundation as _Foundation
    import objc as _objc

    _PAGINATION_CLIP = getattr(
        _AppKit, "NSPrintingPaginationModeClip",
        getattr(_AppKit, "NSClipPagination", 1),
    )

    class _ChartPrintView(_AppKit.NSView):
        """Paints one ``NSBitmapImageRep`` per printed page at its native size."""

        def initWithReps_sizes_pageBox_(self, reps, sizes, page_box):  # noqa: N802
            self = _objc.super(_ChartPrintView, self).initWithFrame_(
                _Foundation.NSMakeRect(0.0, 0.0, page_box[0], page_box[1])
            )
            if self is None:
                return None
            self._reps = reps
            self._sizes = sizes
            #: off centre, in points, x right and y down, as
            #: workflow.overhang plans a chart a little larger than its paper
            self._shift = (0.0, 0.0)
            return self

        def knowsPageRange_(self, _range):  # noqa: N802
            return True, _Foundation.NSMakeRange(1, len(self._reps))

        def rectForPage_(self, _page):  # noqa: N802
            return self.bounds()

        def drawRect_(self, _dirty):  # noqa: N802
            op = _AppKit.NSPrintOperation.currentOperation()
            idx = (op.currentPage() - 1) if op is not None else 0
            if idx < 0 or idx >= len(self._reps):
                return
            rep = self._reps[idx]
            w_pt, h_pt = self._sizes[idx]
            b = self.bounds()
            x = (b.size.width - w_pt) / 2.0 + self._shift[0]
            y = (b.size.height - h_pt) / 2.0 - self._shift[1]    # y runs up
            rep.drawInRect_(_Foundation.NSMakeRect(x, y, w_pt, h_pt))

except Exception:  # pragma: no cover - non-macOS / no PyObjC
    _ChartPrintView = None  # type: ignore[assignment]


# 4.3.5 beta 2: the two forms a PostScript printer can get the chart in
# (defined in ``ppd_color``, which the Print Chart tab reads on every platform)
from workflow.ppd_color import (DEFAULT_POSTSCRIPT_FORM, POSTSCRIPT_AS_MACOS,  # noqa: E402
                                POSTSCRIPT_DEVICE_RGB, POSTSCRIPT_FORMS)


class ChartOverPaper(RuntimeError):
    """The chart is a little larger than the paper the dialog ended on, and
    what would not be on the paper is not empty margin (workflow.overhang,
    jctay 149803): printed at 100 % it would lose printed parts or the white
    the instrument needs. Nothing was sent. *plan* says why."""

    def __init__(self, plan, chart_pt, paper_pt):
        super().__init__(f"chart {chart_pt} over paper {paper_pt}: {plan.reason}")
        self.plan = plan
        self.chart_pt = chart_pt
        self.paper_pt = paper_pt


#: The plan of the last print that went out with a chart a little larger
#: than its paper (only empty margin off it), for the tab's log line and the
#: print record; None otherwise.
last_overhang = None


class PaperNotOnPrinter(RuntimeError):
    """The paper the dialog ended on is not one the PostScript printer's PPD
    lists, and the PPD takes no custom size that fits it (4.3.5 beta 2). Sent
    anyway, the job would say the PPD's default paper while ChromIQ's
    PostScript asks for this one. Nothing was sent."""

    def __init__(self, printer: "str | None", w_pt: float, h_pt: float):
        super().__init__(f"{w_pt:.0f} x {h_pt:.0f} pt is not a paper of {printer}")
        self.printer = printer
        self.w_pt = w_pt
        self.h_pt = h_pt

    @property
    def size_mm(self) -> str:
        """"297 × 420 mm" (rounded to whole millimetres)."""
        return (f"{round(self.w_pt * 25.4 / _PT_PER_INCH)} \u00d7 "
                f"{round(self.h_pt * 25.4 / _PT_PER_INCH)} mm")


def ppd_takes_paper(ppd_text: "str | None", w_pt: float, h_pt: float,
                    tol: float = 1.5) -> bool:
    """True when the PPD lists a paper of *w_pt* x *h_pt* (either way round),
    or takes a custom page size whose width and height ranges hold it; True
    as well when there is no PPD to ask (nothing can be told)."""
    if not ppd_text:
        return True
    import re
    # Its own reading of *PaperDimension, not ``_is_named_paper``'s: the
    # generic PostScript PPD writes "595 842 " with a space before the quote,
    # which that one (the Canon custom-paper rule's) does not match.
    for pw, ph in re.findall(r'^\*PaperDimension\s+[^:]+:\s*"\s*([\d.]+)\s+([\d.]+)\s*"',
                             ppd_text, re.M):
        pw, ph = float(pw), float(ph)
        if (abs(pw - w_pt) <= tol and abs(ph - h_pt) <= tol) or \
                (abs(pw - h_pt) <= tol and abs(ph - w_pt) <= tol):
            return True
    if not re.search(r"^\*CustomPageSize\s+True\s*:", ppd_text, re.M):
        return False
    rng = {}
    for name, lo, hi in re.findall(
            r"^\*ParamCustomPageSize\s+(Width|Height)\s*:\s*\d+\s+points\s+"
            r"([\d.]+)\s+([\d.]+)", ppd_text, re.M):
        rng[name] = (float(lo), float(hi))

    def fits(w, h):
        for name, v in (("Width", w), ("Height", h)):
            if name in rng and not (rng[name][0] - tol <= v <= rng[name][1] + tol):
                return False
        return True
    return fits(w_pt, h_pt) or fits(h_pt, w_pt)


def _printer_name(print_info) -> str:
    """The name of *print_info*'s printer as macOS shows it, else its queue."""
    try:
        return str(print_info.printer().name())
    except Exception:  # noqa: BLE001
        return _queue_of(print_info) or ""


def form_after_dialog(is_postscript: bool, postscript_form: "str | None",
                      ask=None, printer_name=lambda: "") -> "tuple[bool, str | None]":
    """(go on, form) once the macOS dialog closed with Print (Basti,
    2026-10-13, "decide AFTER the dialog"). Only a PostScript printer chosen
    in the dialog with no form for the run (*postscript_form* None) is asked,
    through *ask* (``ask(printer_name())`` returns the form, or None for
    Cancel: then (False, None) and nothing may be sent); without *ask* it gets
    the default. Any other printer, or a stored form, is never asked."""
    if not is_postscript or postscript_form is not None:
        return True, postscript_form
    if ask is None:
        return True, DEFAULT_POSTSCRIPT_FORM
    form = ask(printer_name())
    if form is None:
        return False, None
    return True, form


def print_frames(pages: list[tuple[Path, int]], printer: str | None = None,
                 postscript_form: "str | None" = DEFAULT_POSTSCRIPT_FORM,
                 refuse_unlisted_paper: bool = False,
                 ask_postscript_form=None) -> bool:
    """Show the native macOS print dialog for *pages* and submit them as one job.

    *pages* is a list of ``(tiff_path, frame_index)`` tuples — the same shape
    ``TiffPreview._pages`` uses.  Each entry becomes one printed page, drawn at
    the TIFF's native size (from its resolution tag) with no scaling and no
    colour management.  Raises on failure; the caller surfaces it to the user.
    Must be called on the main (GUI) thread.

    Returns **True when the job was handed to the spooler** and False when it
    was not — the dialog was cancelled, or there was nothing to print, or
    ``runOperation`` refused it. It used to return ``None`` on all four
    outcomes, so a caller could not tell a print from a cancel; the print
    record depends on that difference (R6 F5).  After a submission
    ``last_submission`` describes the job; it is read back from CUPS by the
    caller, off the GUI thread (``read_back``).

    *printer*: a CUPS queue to preselect in the dialog (the Print Chart tab
    passes the queue it was about to print to when it hands the job over to the
    dialog because it does not know that model's paper profiles).

    *postscript_form* (4.3.5 beta 2): how a PostScript printer chosen in the
    dialog gets the chart, ``POSTSCRIPT_DEVICE_RGB`` (ChromIQ's own PostScript,
    k81) or ``POSTSCRIPT_AS_MACOS`` (the print view, as 4.3.4). Any other
    printer ignores it. *refuse_unlisted_paper*: on the DeviceRGB form, raise
    :class:`PaperNotOnPrinter` instead of sending when the dialog's paper is
    not one the PPD takes (said by M-PRINT-PS-PAPER-NOT-LISTED); False sends
    the job as before and the log says so.

    *ask_postscript_form* (4.3.5 beta 2, Basti 2026-10-13, "decide AFTER the
    dialog"): with *postscript_form* None (the run has no choice yet), called
    as ``ask_postscript_form(printer_display_name)`` after the user closed the
    dialog with Print, only when the printer chosen IN the dialog is a
    PostScript queue, and before anything is sent. It returns the form, or
    None to cancel: then nothing is sent and False is returned. Without a
    callback a missing form is the default. Any other printer never asks.
    """
    if not pages:
        return False
    if _ChartPrintView is None:
        raise RuntimeError("PyObjC AppKit is not available on this system")

    import AppKit

    reps: list = []
    sizes_pt: list[tuple[float, float]] = []
    content_pt: list = []
    for tiff_path, frame in pages:
        # 4.3.5 B2: ASKED OF THE FILE AND ITS INK LIST, BEFORE PIL OPENS IT.
        # PIL cannot open a chart of five or more inks (the refusal below then
        # never came, only "Could not open the macOS print dialog"), and a CMY
        # chart the layout engine wrote before 4.3.5 is an RGB TIFF of inverted
        # ink values, which went through as RGB colours. An RGB chart passes
        # this test and goes on exactly as before.
        _refuse_unless_rgb(tiff_path, frame)
        with Image.open(tiff_path) as im:
            n_frames = getattr(im, "n_frames", 1)
            im.seek(min(frame, n_frames - 1))
            # ASKED BEFORE THE CONVERSION, NOT AFTER IT. See `ChartIsNotRGB`:
            # `convert("RGB")` is a no-op for an RGB chart and a colour
            # conversion for any other, and this route's whole promise is that
            # "pixel values reach the driver unchanged".
            if im.mode != "RGB":
                from workflow.chart_inks import ink_set_label
                raise ChartIsNotRGB(ink_set_label(
                    None, {"CMYK": 4, "L": 1}.get(im.mode, len(im.getbands()))))
            rgb = im.convert("RGB")
            w_px, h_px = rgb.size
            dpi = rgb.info.get("dpi") or (300.0, 300.0)
            dpi_x = float(dpi[0] or 300.0)
            dpi_y = float(dpi[1] or 300.0)
            raw = rgb.tobytes()

        rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
            None, w_px, h_px, 8, 3, False, False,
            AppKit.NSDeviceRGBColorSpace, w_px * 3, 24,
        )
        if rep is None:
            raise RuntimeError(f"could not allocate bitmap rep for {tiff_path.name}")
        dst = rep.bitmapData()
        if dst is None or len(dst) < len(raw):
            raise RuntimeError(f"bitmap buffer too small for {tiff_path.name}")
        dst[: len(raw)] = raw
        reps.append(rep)
        sizes_pt.append((w_px * _PT_PER_INCH / dpi_x, h_px * _PT_PER_INCH / dpi_y))
        try:
            content_pt.append(_solid_box_pt(rgb, dpi_x, dpi_y))
        except Exception:  # noqa: BLE001 - unknown content: never given margins
            content_pt.append((0.0, 0.0, sizes_pt[-1][0], sizes_pt[-1][1]))

    page_box = (max(s[0] for s in sizes_pt), max(s[1] for s in sizes_pt))
    view = _ChartPrintView.alloc().initWithReps_sizes_pageBox_(reps, sizes_pt, page_box)
    if view is None:
        raise RuntimeError("could not create print view")

    print_info = AppKit.NSPrintInfo.sharedPrintInfo().copy()
    print_info.setHorizontalPagination_(_PAGINATION_CLIP)
    print_info.setVerticalPagination_(_PAGINATION_CLIP)
    print_info.setHorizontallyCentered_(True)
    print_info.setVerticallyCentered_(True)
    print_info.setLeftMargin_(0.0)
    print_info.setRightMargin_(0.0)
    print_info.setTopMargin_(0.0)
    print_info.setBottomMargin_(0.0)
    print_info.setScalingFactor_(1.0)
    print_info.printSettings()["Duplex"] = "None"
    # Default paper size to the chart's own dimensions. The Sequoia/Tahoe print
    # panel hides the standalone paper-size control, so without this we'd
    # inherit whatever was last in sharedPrintInfo and silently clip charts
    # bigger than that.  The user can still override below via the page-setup
    # accessory or the driver's Printer Options pane.
    print_info.setPaperSize_(_Foundation.NSMakeSize(page_box[0], page_box[1]))

    # Ask for application colour matching *before* the dialog so its colour
    # panes open greyed out, then show the dialog (for paper / quality /
    # copies), then ask again afterwards in case a pane reset it.
    global last_submission
    last_submission = None
    if printer:
        _preselect_printer(print_info, printer)
    # beta 16 package: a page no paper of the printer matches gets the Canon
    # driver's minimum margins, before the dialog and again after it (the
    # printer may have been changed in it), so its alert never comes
    give_custom_paper_driver_margins(print_info, page_box, content_pt, sizes_pt)
    _lock_no_color_management(print_info)

    panel = AppKit.NSPrintPanel.printPanel()
    # Force the paper-size / orientation / scale controls to be available in
    # the panel even on the new macOS print dialog, which otherwise omits them.
    panel.setOptions_(
        panel.options()
        | getattr(AppKit, "NSPrintPanelShowsPaperSize", 0x4)
        | getattr(AppKit, "NSPrintPanelShowsOrientation", 0x8)
        | getattr(AppKit, "NSPrintPanelShowsScaling", 0x10)
        | getattr(AppKit, "NSPrintPanelShowsPageSetupAccessory", 0x100)
    )
    ok_response = getattr(AppKit, "NSModalResponseOK", getattr(AppKit, "NSOKButton", 1))
    if panel.runModalWithPrintInfo_(print_info) != ok_response:
        log.info("native print: dialog cancelled")
        return False

    if _same_page(print_info, page_box):
        give_custom_paper_driver_margins(print_info, page_box, content_pt, sizes_pt)
    # A CHART A LITTLE LARGER THAN THE PAPER CHOSEN IN THE DIALOG (jctay
    # 149803): at exactly 100 %, moved so only empty margin is off the paper,
    # with no question; refused when more would be lost (workflow.overhang).
    # Until 4.3.10 this route clipped any overhang, centred, without a word.
    global last_overhang
    last_overhang = None
    try:
        _ps = print_info.paperSize()
        _paper = (float(_ps.width), float(_ps.height))
    except Exception:  # noqa: BLE001 - nothing to compare
        _paper = None
    if _paper and _paper[0] > 0 and _paper[1] > 0:
        from workflow import overhang as _O
        _pp = _O.paper_like_chart(page_box, _paper)
        _tol = _O.NO_OVERHANG_MM / _O.MM_PER_PT
        if page_box[0] > _pp[0] + _tol or page_box[1] > _pp[1] + _tol:
            _plan = _O.plan_for_chart(pages, page_box, _paper)
            if _plan.safe:
                view._shift = _plan.shift_pt()
                last_overhang = _plan
                log.info("native print: the chart is larger than the paper; "
                         "at 100 %%, only empty margin off it (%s)",
                         _plan.describe())
            elif _plan.reason != "too_much":
                raise ChartOverPaper(_plan, page_box, _paper)
    locked = _lock_no_color_management(print_info, after_dialog=True)
    _ppd_after = _ppd_text_of(print_info)
    _is_ps = is_postscript_queue(_ppd_after)
    # 4.3.5 beta 2 (Basti, 2026-10-13): the printer is known only now, so a
    # run with no choice yet is asked here, never before the dialog
    _go, postscript_form = form_after_dialog(
        _is_ps, postscript_form, ask_postscript_form, lambda: _printer_name(print_info))
    if not _go:
        log.info("native print: PostScript form not chosen; nothing sent")
        return False
    if _is_ps and postscript_form == POSTSCRIPT_DEVICE_RGB:
        # k81 (Knut, #182 6102031563): ON A POSTSCRIPT PRINTER THE CHART GOES
        # AS THE PRINTER'S OWN RGB, as the direct route sends it. Drawn
        # through the print view, macOS spools a PDF and its PostScript filter
        # (cgpdftops) writes the chart as CIEBasedABC (a generic queue) or
        # CIEBasedDEF (a queue with a ColorSync profile, Knut's HP CLJ 5550),
        # which the printer converts with its own colour rendering: no
        # "no colour management" exists on that path, and none can be chosen
        # in the dialog. Measured on capture queues, 2026-10-11: an exact-size
        # PDF with DeviceRGB and an untagged bitmap both still arrive
        # CIEBased; ChromIQ's own PostScript submitted with the dialog's
        # ticket arrives DeviceRGB, all 1,372,807 chart pixels unchanged, with
        # every option of the dialog (paper, the HP colour locks) in the job.
        # 4.3.5 beta 2: only on the form chosen for the run (the Print Chart
        # tab's PostScript row); "as macOS sends it" goes on below, as 4.3.4.
        try:
            _size = print_info.paperSize()
            _w, _h = float(_size.width), float(_size.height)
        except Exception:  # noqa: BLE001 - nothing to check against
            _w = _h = 0.0
        if _w and _h and not ppd_takes_paper(_ppd_after, _w, _h):
            # 4.3.5 beta 2 (combined review, item c): measured, an A3 page on
            # the generic PostScript PPD (no A3, no custom size) went as a job
            # whose ticket says Letter while the PostScript asks for A3.
            try:
                _disp = str(print_info.printer().name())
            except Exception:  # noqa: BLE001
                _disp = _queue_of(print_info)
            if refuse_unlisted_paper:
                raise PaperNotOnPrinter(_disp, _w, _h)
            log.warning("native print: %.0f x %.0f pt is not a paper of %s; "
                        "sent anyway (not refused by the caller)",
                        _w, _h, _disp)
        return _print_device_rgb_postscript(print_info, pages, locked)
    # Tag the chart with the profile macOS will convert it into, so the
    # conversion is the identity and the chart's own numbers reach the driver.
    dest_icc, dest_name = _destination_rgb_profile(print_info)
    # The profile macOS converts this job INTO, kept even when the chart could
    # not be given it: then macOS converts the chart, and the read-back must
    # say so whatever the PPD declares (B3, 2026-10-10).
    output_intent = dest_name if dest_icc else None
    try:
        _settings_now = dict(print_info.printSettings())
    except Exception:  # noqa: BLE001
        _settings_now = {}
    _ppd_now = _ppd_text_of(print_info)
    cmyk = cmyk_raster_job(_ppd_now, _settings_now, _queue_of(print_info))
    if _is_ps:
        log.info("native print: PostScript printer, chart sent as macOS sends "
                 "it (the form chosen for this run)")
    if cmyk and dest_icc:
        # 4.3.5: a CMYK raster job. macOS converts the chart from its tag into
        # CMYK and ignores an RGB ColorSync profile of the queue, so the chart
        # keeps the tag every other print from an application gets (sRGB),
        # and the sheet no longer depends on which profile is assigned.
        log.info("native print: %s raster job, chart left untagged (output "
                 "profile %r not used)", cmyk, dest_name)
        dest_icc, dest_name = None, None
    elif dest_icc:
        tagged = _retag_reps(view._reps, dest_icc)
        if tagged is not None:
            view._reps = tagged
            log.info("native print: chart tagged with the job's output profile %r",
                     dest_name)
        else:
            log.warning("native print: output profile %r not usable as a colour space",
                        dest_name)
            dest_icc, dest_name = None, None
    elif not cmyk:
        log.warning("native print: no output profile could be read; macOS may "
                    "convert the chart's colours")

    import time as _time
    t_start = _time.time()
    op = AppKit.NSPrintOperation.printOperationWithView_printInfo_(view, print_info)
    op.setShowsPrintPanel_(False)
    op.setShowsProgressPanel_(True)
    ok = op.runOperation()
    try:
        pi_after = op.printInfo()
        log.debug("native print: resolved printSettings = %r", dict(pi_after.printSettings()))
    except Exception as exc:  # pragma: no cover - diagnostics only
        log.warning("native print: could not dump resolved settings: %s", exc)
        pi_after = print_info
    if not ok:
        log.warning("native print: job submission failed")
        return False
    try:
        printer_obj = pi_after.printer()
        display = str(printer_obj.name()) if printer_obj is not None else None
    except Exception:  # noqa: BLE001
        display = None
    last_submission = Submission(display, locked, t_start, dest_icc or b"",
                                 dest_name if dest_icc else None,
                                 output_intent=output_intent)
    last_submission.reset_by_chromiq = dict(last_reset_by_chromiq)
    last_submission.cmyk_raster = cmyk
    last_submission.postscript_form = POSTSCRIPT_AS_MACOS if _is_ps else None
    return True


def _postscript_for_pages(pages: list, page_pt: "tuple[float, float] | None") -> bytes:
    """ChromIQ's own PostScript for *pages* (``(tiff, frame)``): the direct
    route's document (``PostScriptGenerator``, DeviceRGB, ``cups-disable-cmm``),
    one page per chart page, each centred on *page_pt*. A single page is the
    direct route's document exactly."""
    import tempfile
    from workflow.postscript_generator import PostScriptGenerator
    gen = PostScriptGenerator()
    docs: "list[str]" = []
    with tempfile.TemporaryDirectory(prefix="chromiq-dialog-ps-") as tmp:
        for k, (tiff_path, frame) in enumerate(pages):
            src = Path(tiff_path)
            if frame:
                with Image.open(src) as im:
                    im.seek(frame)
                    dpi = im.info.get("dpi") or (300, 300)
                    src = Path(tmp) / f"page{k}.tif"
                    im.save(src, dpi=dpi)
            # placed as the dialog's check planned it (workflow.overhang)
            from workflow import overhang as _O
            _plan = last_overhang
            with _O.placed(_plan.shift_pt() if _plan is not None else None):
                docs.append(gen.generate(src, page_size_pt=page_pt))
    if len(docs) == 1:
        return docs[0].encode("ascii")
    head = ("%!PS-Adobe-3.0\n%%LanguageLevel: 3\n%cupsJobTicket: cups-disable-cmm\n"
            f"%%Pages: {len(docs)}\n%%EndComments\n")
    body = []
    for n, doc in enumerate(docs, 1):
        part = doc.split("%%EndComments\n", 1)[-1].replace("%%EOF\n", "")
        body.append(f"%%Page: {n} {n}\n{part}")
    return (head + "".join(body) + "%%EOF\n").encode("ascii")


def _print_device_rgb_postscript(print_info, pages: list, locked: dict) -> bool:
    """Submit ChromIQ's PostScript (:func:`_postscript_for_pages`) to the
    printer chosen in the dialog, with the dialog's print settings and page
    format (``PMPrinterPrintWithFile``), so the job carries every option the
    dialog set and the chart reaches the printer as DeviceRGB."""
    global last_submission
    import objc
    import tempfile
    import time as _time
    if not (_PRINTCORE_OK and _PM_PAPER_OK):
        raise RuntimeError("PrintCore is not available for the PostScript job")
    try:
        size = print_info.paperSize()
        page_pt = (float(size.width), float(size.height))
    except Exception:  # noqa: BLE001 - the chart's own size then
        page_pt = None
    data = _postscript_for_pages(pages, page_pt)
    pid = ctypes.c_void_p(objc.pyobjc_id(print_info))
    # 4.3.5 beta 2 (combined review, item d): PMPrinterPrintWithFile names no
    # job, so the print queue showed the job without a title or application.
    _name_the_job(print_info, job_title(pages), "ChromIQ")
    session = _libobjc.objc_msgSend(pid, _libobjc.sel_registerName(b"PMPrintSession"))
    settings = _libobjc.objc_msgSend(pid, _libobjc.sel_registerName(b"PMPrintSettings"))
    page_format = _libobjc.objc_msgSend(pid, _libobjc.sel_registerName(b"PMPageFormat"))
    printer = ctypes.c_void_p()
    if not session or _appsvc.PMSessionGetCurrentPrinter(
            ctypes.c_void_p(session), ctypes.byref(printer)) != 0 or not printer.value:
        log.warning("native print: no printer in the dialog's session")
        return False
    t_start = _time.time()
    mime = _cfstr("application/postscript")
    try:
        with tempfile.TemporaryDirectory(prefix="chromiq-dialog-ps-") as tmp:
            # named after the chart: the print queue shows the file's name
            path = Path(tmp) / (Path(job_title(pages)).stem + ".ps")
            path.write_bytes(data)
            import Foundation
            url = Foundation.NSURL.fileURLWithPath_(str(path))
            status = _appsvc.PMPrinterPrintWithFile(
                printer, ctypes.c_void_p(settings), ctypes.c_void_p(page_format),
                ctypes.c_void_p(mime), ctypes.c_void_p(objc.pyobjc_id(url)))
    finally:
        _cf.CFRelease(ctypes.c_void_p(mime))
    if status != 0:
        log.warning("native print: PMPrinterPrintWithFile -> %d", status)
        return False
    log.info("native print: PostScript printer, chart sent as DeviceRGB with the "
             "dialog's settings (%d page(s), %d bytes)", len(pages), len(data))
    try:
        display = str(print_info.printer().name())
    except Exception:  # noqa: BLE001
        display = None
    last_submission = Submission(display, locked, t_start, b"", None)
    last_submission.device_rgb = True
    last_submission.postscript_form = POSTSCRIPT_DEVICE_RGB
    last_submission.reset_by_chromiq = dict(last_reset_by_chromiq)
    return True


def job_title(pages: list) -> str:
    """The title a PostScript job gets in the print queue: the chart's file
    name, as the print view's job of the same chart would carry it."""
    try:
        return Path(pages[0][0]).name
    except Exception:  # noqa: BLE001
        return "ChromIQ chart"


#: the key macOS stores the printing application's name under
_APP_NAME_KEY = "com.apple.print.JobInfo.PMApplicationName"


def _name_the_job(print_info, title: str, application: str) -> None:
    """Give the job *title* and *application*, in the print settings it is
    submitted with (``PMPrintSettingsSetJobName``, and the application's name
    the way the print view sets it). Never raises: a job without a name still
    prints."""
    import objc
    try:
        pid = ctypes.c_void_p(objc.pyobjc_id(print_info))
        settings = _libobjc.objc_msgSend(pid, _libobjc.sel_registerName(b"PMPrintSettings"))
        if not settings:
            return
        t = _cfstr(title)
        try:
            _appsvc.PMPrintSettingsSetJobName(ctypes.c_void_p(settings), ctypes.c_void_p(t))
        finally:
            _cf.CFRelease(ctypes.c_void_p(t))
        k, v = _cfstr(_APP_NAME_KEY), _cfstr(application)
        try:
            _appsvc.PMPrintSettingsSetValue(ctypes.c_void_p(settings), ctypes.c_void_p(k),
                                            ctypes.c_void_p(v), False)
        finally:
            _cf.CFRelease(ctypes.c_void_p(k))
            _cf.CFRelease(ctypes.c_void_p(v))
    except Exception:  # noqa: BLE001
        log.debug("native print: could not name the job", exc_info=True)


# ---- custom paper margins (beta 16 package) -------------------------------------
#
# The dialog route sizes the page to the chart (``setPaperSize_``).  When the
# printer has a paper of that size, macOS picks it; when it has none (an
# imagePROGRAF PRO-2100/4100/2600 with a 5 x 7 in, 4 x 6 in, roll-width or
# custom chart) macOS makes a custom paper with NO margins, and the Canon driver
# then stops the job with its own alert, "The margin settings of the custom
# paper size are less than the supported minimum values" (vendor tests
# 2026-10-09).  Nobody can answer that alert from a program.  So such a page
# gets the driver's minimum margins, the PPD's ``*HWMargins``, and only when no
# chart content lies inside them: the chart is drawn centred at 1:1, so with
# margins the outer band of the page is not printed, which a chart's own white
# border easily covers (printtarg leaves several millimetres).


def _canon_min_margins(ppd_text: str) -> tuple[float, float, float, float] | None:
    """(left, bottom, right, top) in points: a Canon IJ PPD's ``*HWMargins``,
    the smallest margins its driver accepts on a custom paper; None for any
    other printer or a PPD without them."""
    import re
    if "*OpenUI *CNIJ" not in ppd_text:
        return None
    m = re.search(r"^\*HWMargins:\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
                  ppd_text, re.M)
    if not m:
        return None
    vals = tuple(float(x) for x in m.groups())
    return vals if any(v > 0 for v in vals) else None


def _is_named_paper(ppd_text: str, w_pt: float, h_pt: float, tol: float = 1.5) -> bool:
    """True when the PPD declares a paper of *w_pt* x *h_pt* (either way round),
    which macOS then picks for the page instead of making a custom one."""
    import re
    for a, b in re.findall(r'^\*PaperDimension\s+\S+?(?:/[^:]*)?:\s*"([\d.]+)\s+([\d.]+)"',
                           ppd_text, re.M):
        pw, ph = float(a), float(b)
        if (abs(pw - w_pt) <= tol and abs(ph - h_pt) <= tol) or \
                (abs(pw - h_pt) <= tol and abs(ph - w_pt) <= tol):
            return True
    return False


def content_inside_margins(content_pt: list[tuple[float, float, float, float]],
                           sizes_pt: list[tuple[float, float]],
                           page_box: tuple[float, float],
                           margins: tuple[float, float, float, float]) -> bool:
    """True when every page's content stays printable with *margins*
    (left, bottom, right, top).  Each page is drawn centred in *page_box*, and
    the view is centred in the printable area, so the band of the view that
    is not printed is (left + right) / 2 at each side and (bottom + top) / 2 at
    top and bottom.  *content_pt*: per page, the non-white box (x0, y0, x1, y1)
    in points from the page's top left, None for a blank page."""
    left, bottom, right, top = margins
    cut_x, cut_y = (left + right) / 2.0, (bottom + top) / 2.0
    bw, bh = page_box
    for box, (w, h) in zip(content_pt, sizes_pt):
        if box is None:
            continue
        ox, oy = (bw - w) / 2.0, (bh - h) / 2.0
        x0, y0, x1, y1 = box
        if ox + x0 < cut_x - 0.01 or ox + x1 > bw - cut_x + 0.01:
            return False
        if oy + y0 < cut_y - 0.01 or oy + y1 > bh - cut_y + 0.01:
            return False
    return True


def _content_box_pt(rgb, dpi_x: float, dpi_y: float):
    """The page's non-white box in points (x0, y0, x1, y1) from its top left,
    None when it is blank.  "White" is 250 or more in every channel."""
    import numpy as np
    a = np.asarray(rgb)
    ink = (a < 250).any(axis=2)
    rows, cols = np.flatnonzero(ink.any(axis=1)), np.flatnonzero(ink.any(axis=0))
    if rows.size == 0:
        return None
    k_x, k_y = _PT_PER_INCH / dpi_x, _PT_PER_INCH / dpi_y
    return (cols[0] * k_x, rows[0] * k_y, (cols[-1] + 1) * k_x, (rows[-1] + 1) * k_y)


def _solid_box_pt(rgb, dpi_x: float, dpi_y: float, min_mm: float = 1.0):
    """The box of the page's SOLID ink in points (x0, y0, x1, y1) from its
    top left, None when there is none: ink at least *min_mm* across both
    ways, which patches and scan markers are and text and hairlines are not
    (beta 16 review).  printtarg prints its info line rotated along the
    chart's side, and on a short page it runs from the top edge to the bottom
    edge: measured on a 4 x 6 in chart made with -M6, whose patches keep
    6 mm clear.  Judged by every ink pixel, such a chart could never be given
    the driver's minimum margins, so the Canon imagePROGRAF alert this was
    made to prevent came back for it, with no way past it.  The driver's
    3 mm band may now clip that line; it never clips a patch."""
    import numpy as np
    a = np.asarray(rgb)
    ink = (a < 250).any(axis=2)
    b = max(1, int(round(min(dpi_x, dpi_y) * 0.3 / 25.4)))      # ~0.3 mm cells
    h, w = ink.shape[0] // b, ink.shape[1] // b
    if h == 0 or w == 0:
        return _content_box_pt(rgb, dpi_x, dpi_y)
    cells = ink[: h * b, : w * b].reshape(h, b, w, b).all(axis=(1, 3))
    k = max(2, int(np.ceil(min_mm / (b * 25.4 / min(dpi_x, dpi_y)))))
    if h < k or w < k:
        return _content_box_pt(rgb, dpi_x, dpi_y)
    s = np.zeros((h + 1, w + 1), np.int32)
    s[1:, 1:] = cells.cumsum(0, dtype=np.int32).cumsum(1, dtype=np.int32)
    win = s[k:, k:] - s[:-k, k:] - s[k:, :-k] + s[:-k, :-k]
    solid = win == k * k
    rows, cols = np.flatnonzero(solid.any(axis=1)), np.flatnonzero(solid.any(axis=0))
    if rows.size == 0:
        return None
    # one cell of slack each side: a patch's edge cell may be part white
    x0, y0 = max(0, (cols[0] - 1) * b), max(0, (rows[0] - 1) * b)
    x1 = min(ink.shape[1], (cols[-1] + k + 1) * b)
    y1 = min(ink.shape[0], (rows[-1] + k + 1) * b)
    k_x, k_y = _PT_PER_INCH / dpi_x, _PT_PER_INCH / dpi_y
    return (x0 * k_x, y0 * k_y, x1 * k_x, y1 * k_y)


def dialog_printer() -> tuple[str | None, str | None]:
    """(CUPS queue, display name) of the printer the macOS print dialog opens
    on: ``print_frames`` shows it a copy of the shared print info."""
    import AppKit
    pr = AppKit.NSPrintInfo.sharedPrintInfo().printer()
    display = str(pr.name()) if pr is not None and pr.name() else None
    return (_queue_name(display) if display else None), display


def _queue_of(print_info) -> str | None:
    try:
        printer = print_info.printer()
        display = printer.name() if printer is not None else None
        return _queue_name(str(display)) if display else None
    except Exception:  # noqa: BLE001
        return None


def _ppd_text_of(print_info) -> str | None:
    try:
        printer = print_info.printer()
        display = printer.name() if printer is not None else None
        if not display:
            return None
        from workflow.print_manager import PrintModule
        ppd = PrintModule.find_ppd_path(_queue_name(str(display)))
        if not ppd:
            return None
        from core.text_io import read_text
        return read_text(Path(ppd), lenient=True)
    except Exception:  # noqa: BLE001
        return None


def paper_margins(print_info) -> tuple[float, float, float, float, float, float] | None:
    """(width, height, top, left, bottom, right) of *print_info*'s paper, in
    points, read back from PrintCore; None when it cannot be read."""
    import objc
    if not _PM_PAPER_OK:
        return None
    pf = _libobjc.objc_msgSend(ctypes.c_void_p(objc.pyobjc_id(print_info)),
                               _libobjc.sel_registerName(b"PMPageFormat"))
    if not pf:
        return None
    paper = ctypes.c_void_p()
    if _appsvc.PMGetPageFormatPaper(ctypes.c_void_p(pf), ctypes.byref(paper)) != 0 \
            or not paper.value:
        return None
    m, w, h = _PMRect(), ctypes.c_double(), ctypes.c_double()
    if _appsvc.PMPaperGetMargins(paper, ctypes.byref(m)) != 0:
        return None
    _appsvc.PMPaperGetWidth(paper, ctypes.byref(w))
    _appsvc.PMPaperGetHeight(paper, ctypes.byref(h))
    return (w.value, h.value, m.top, m.left, m.bottom, m.right)


def give_custom_paper_driver_margins(print_info, page_box: tuple[float, float],
                                     content_pt: list, sizes_pt: list) -> bool:
    """Make *print_info*'s paper a custom paper of *page_box* with the Canon
    driver's minimum margins, when its printer is a Canon IJ whose PPD has no
    paper of that size and no chart content lies inside those margins.
    Returns True when it did.  Never raises: at worst the page stays as it
    was."""
    import objc
    if not _PM_PAPER_OK:
        return False
    try:
        text = _ppd_text_of(print_info)
        if not text:
            return False
        margins = _canon_min_margins(text)
        if margins is None or _is_named_paper(text, *page_box):
            return False
        if not content_inside_margins(content_pt, sizes_pt, page_box, margins):
            log.warning("native print: chart content reaches into the driver's "
                        "minimum margins %s; the page keeps no margins", margins)
            return False
        have = paper_margins(print_info)
        if have is not None:
            w, h, top, left, bottom, right = have
            if abs(w - page_box[0]) < 0.5 and abs(h - page_box[1]) < 0.5 and all(
                    got >= want - 0.01 for got, want in
                    zip((left, bottom, right, top), margins)):
                return True         # already so
        pi_id = ctypes.c_void_p(objc.pyobjc_id(print_info))
        session = _libobjc.objc_msgSend(pi_id, _libobjc.sel_registerName(b"PMPrintSession"))
        page_format = _libobjc.objc_msgSend(pi_id, _libobjc.sel_registerName(b"PMPageFormat"))
        if not session or not page_format:
            return False
        printer = ctypes.c_void_p()
        if _appsvc.PMSessionGetCurrentPrinter(ctypes.c_void_p(session),
                                              ctypes.byref(printer)) != 0 or not printer.value:
            return False
        left, bottom, right, top = margins
        rect = _PMRect(top=top, left=left, bottom=bottom, right=right)
        w_pt, h_pt = page_box
        # the name the print dialog shows for this paper: a real "×"
        name = f"{w_pt * 25.4 / 72.0:.0f} × {h_pt * 25.4 / 72.0:.0f} mm"
        pid, pname = _cfstr(f"ChromIQ-chart-{w_pt:.2f}x{h_pt:.2f}"), _cfstr(name)
        paper, new_pf = ctypes.c_void_p(), ctypes.c_void_p()
        try:
            if _appsvc.PMPaperCreateCustom(printer, ctypes.c_void_p(pid), ctypes.c_void_p(pname),
                                           w_pt, h_pt, ctypes.byref(rect),
                                           ctypes.byref(paper)) != 0 or not paper.value:
                return False
            if _appsvc.PMCreatePageFormatWithPMPaper(ctypes.byref(new_pf), paper) != 0 \
                    or not new_pf.value:
                return False
            if _appsvc.PMCopyPageFormat(new_pf, ctypes.c_void_p(page_format)) != 0:
                return False
            print_info.updateFromPMPageFormat()
        finally:
            for ref in (pid, pname):
                if ref:
                    _cf.CFRelease(ctypes.c_void_p(ref))
            for obj in (new_pf, paper):
                if obj.value:
                    _appsvc.PMRelease(obj)
        log.info("native print: custom page %s given the driver's minimum margins %s "
                 "(left, bottom, right, top)", name, margins)
        return True
    except Exception as exc:  # noqa: BLE001 - the page then stays as it was
        log.warning("native print: could not give the custom page margins: %s", exc)
        return False


def _same_page(print_info, page_box: tuple[float, float]) -> bool:
    """True while *print_info*'s paper is still the chart's own page size (a
    paper the user picked in the dialog is left alone)."""
    try:
        size = print_info.paperSize()
        return abs(size.width - page_box[0]) < 0.5 and abs(size.height - page_box[1]) < 0.5
    except Exception:  # noqa: BLE001
        return False


def _preselect_printer(print_info, queue: str) -> None:
    """Select *queue* (a CUPS queue name) in *print_info* before the dialog."""
    try:
        import AppKit
        display = queue
        try:
            import cups
            display = cups.Connection().getPrinters().get(queue, {}).get(
                "printer-info") or queue
        except Exception:  # noqa: BLE001
            pass
        pr = AppKit.NSPrinter.printerWithName_(display)
        if pr is not None:
            print_info.setPrinter_(pr)
    except Exception as exc:  # noqa: BLE001
        log.warning("native print: could not preselect %s: %s", queue, exc)
