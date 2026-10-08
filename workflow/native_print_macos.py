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
  not from ChromIQ's own dictionary, and ``last_report`` says what it carries.

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
from workflow.ppd_color import (paper_profile_for,
                                vendor_no_cm_settings)

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


def _locked_settings_for(print_info) -> dict[str, str]:
    """The full set of (key, value) pairs to lock for *print_info* — the
    vendor-neutral base plus, if found, the selected printer's own no-colour
    options (all of them: HP colour lasers split the choice over per-object
    options like HPTextRGB / HPGraphicsRGB / HPPhotoRGB)."""
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


def _ppd_text_for(print_info) -> tuple[str | None, str | None]:
    """(queue name, PPD text) of *print_info*'s printer, or (None, None)."""
    try:
        printer = print_info.printer()
        display = printer.name() if printer is not None else None
        if not display:
            return None, None
        queue = _queue_name(display)
        from workflow.print_manager import PrintModule
        ppd = PrintModule.find_ppd_path(queue)
        if not ppd:
            return queue, None
        from core.text_io import read_text
        return queue, read_text(Path(ppd), lenient=True)
    except Exception:  # noqa: BLE001
        return None, None


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


class ColorManagementMismatch(RuntimeError):
    """Raised when the job read back from CUPS does not carry the colour keys
    ChromIQ set, or the chart could not be tagged with the job's own paper
    profile.  The job has already been submitted by the time this is raised;
    ``last_report`` holds the details and the caller warns the user, no retry.
    """


def _lock_no_color_management(print_info) -> None:
    """Set the application-colour-matching keys (locked) on *print_info*'s
    PrintCore ``PMPrintSettings`` and sync them back into the Cocoa layer.

    Also mirrors the keys into the Cocoa ``printSettings`` dict as a fallback.
    Best-effort: logs and continues if PrintCore is unavailable.
    """
    import objc

    locked = _locked_settings_for(print_info)

    # Cocoa-dict fallback first (cheap, always works).
    cocoa = print_info.printSettings()
    for key, value in locked.items():
        cocoa[key] = value

    if not _PRINTCORE_OK:
        return
    try:
        pm_ptr = _libobjc.objc_msgSend(
            ctypes.c_void_p(objc.pyobjc_id(print_info)),
            _libobjc.sel_registerName(b"PMPrintSettings"),
        )
        if not pm_ptr:
            log.warning("native print: PMPrintSettings() returned NULL")
            return
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


def _icc_description(path: str) -> str | None:
    """The description of the ICC profile file at *path* (for the read-back)."""
    try:
        from PIL import ImageCms
        return ImageCms.getProfileDescription(ImageCms.getOpenProfile(path)).strip()
    except Exception:  # noqa: BLE001
        return None


#: The read-back of the last job ``print_frames`` submitted (a
#: ``print_ticket.TicketReport``), or None when nothing was submitted.
last_report = None


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
            x = (b.size.width - w_pt) / 2.0
            y = (b.size.height - h_pt) / 2.0
            rep.drawInRect_(_Foundation.NSMakeRect(x, y, w_pt, h_pt))

except Exception:  # pragma: no cover - non-macOS / no PyObjC
    _ChartPrintView = None  # type: ignore[assignment]


def print_frames(pages: list[tuple[Path, int]]) -> bool:
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
    record depends on that difference (R6 F5).  ``ColorManagementMismatch`` is
    raised only *after* a successful submission, so an exception of that one
    kind also means the job went.
    """
    if not pages:
        return False
    if _ChartPrintView is None:
        raise RuntimeError("PyObjC AppKit is not available on this system")

    import AppKit

    reps: list = []
    sizes_pt: list[tuple[float, float]] = []
    for tiff_path, frame in pages:
        with Image.open(tiff_path) as im:
            n_frames = getattr(im, "n_frames", 1)
            im.seek(min(frame, n_frames - 1))
            # ASKED BEFORE THE CONVERSION, NOT AFTER IT. See `ChartIsNotRGB`:
            # `convert("RGB")` is a no-op for an RGB chart and a colour
            # conversion for any other, and this route's whole promise is that
            # "pixel values reach the driver unchanged".
            if im.mode != "RGB":
                raise ChartIsNotRGB(im.mode)
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
    global last_report
    last_report = None
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

    _lock_no_color_management(print_info)
    # Tag the chart with the profile macOS will convert it into, so the
    # conversion is the identity and the chart's own numbers reach the driver.
    dest_icc, dest_name = _destination_rgb_profile(print_info)
    if dest_icc:
        tagged = _retag_reps(view._reps, dest_icc)
        if tagged is not None:
            view._reps = tagged
            log.info("native print: chart tagged with the job's output profile %r",
                     dest_name)
        else:
            log.warning("native print: output profile %r not usable as a colour space",
                        dest_name)
            dest_icc, dest_name = None, None
    else:
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
    # Read the job back from CUPS: what the printing system holds is what
    # prints, not the dictionary ChromIQ wrote (that check could not fail).
    from workflow.print_ticket import check_job, find_job
    queue, ppd_text = _ppd_text_for(pi_after)
    expected = _locked_settings_for(pi_after)
    job = find_job(queue, t_start) if queue else None
    last_report = check_job(queue or "?", job, expected, ppd_text=ppd_text,
                            tagged_with=dest_name if dest_icc else "",
                            tag_icc_desc_for=_icc_description)
    if (not dest_icc and last_report.read and last_report.tag_matches_job is None
            and ppd_text and "*cupsICCProfile" in ppd_text):
        # Any printer whose PPD names profiles macOS can match to (HP DesignJet
        # and the like, not only Canon/Epson): the chart went untagged, so macOS
        # may convert it, and the status line must not say otherwise. A PPD
        # without profiles (no output intent at all) stays quiet: measured on
        # the sample HP DeskJet queue, its raster is byte-identical to beta 14's.
        last_report.tag_matches_job = False
    if last_report.read and not last_report.ok:
        raise ColorManagementMismatch(last_report.summary())
    return True
