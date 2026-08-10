"""Native macOS print path (PyObjC) — emulates Adobe Color Printer Utility's
colour-off behaviour on the spool side.

Opens the standard macOS print panel via ``NSPrintPanel`` / ``NSPrintOperation``
and submits the profiling-target bitmap as **device RGB with no embedded ICC
profile** at its exact generated size (no scaling).

To stop the printer driver from colour-managing the chart it sets
``AP_ColorMatchingMode`` = ``AP_ApplicationColorMatching`` on the job's
PrintCore ``PMPrintSettings`` with the *locked* flag, before and again after
the print dialog.  As a vendor-independent backstop it also scans the
selected printer's PPD for that driver's own "no colour adjustment" option
(e.g. Epson ``EPIJ_CMat=3``) and locks it directly.  ``PMPrintSettingsSetValue``
is not wrapped by PyObjC, so it is called through ``ctypes`` against
PrintCore.  No custom colour-matching callback is registered, so no
transform is applied: pixel values reach the driver unchanged.

In addition, ``_apply_session_no_color_management`` re-declares the printer's
own default output intent as the *application* output intent on the
``PMPrintSession`` and switches the session to application-managed colour, via
the ``PMSession*WithColorSyncProfiles`` SPI family.  This is the step ColorByte
Print-Tool performs (reverse-engineered from its binary) that the
``PMPrintSettings`` lock alone does not: it stops vendor colour engines that
ignore the Apple-level keys — notably newer Canon macOS drivers, which
otherwise colour-manage profiling charts even with ``ColorSync=None``.  Unlike
the *bare* ``PMSessionSetApplicationOutputIntent`` /
``PMSessionCopyDefaultOutputIntent`` (which SIGABRT on the ``NSPrintInfo``
session), the ``*WithColorSyncProfiles`` variants are callable on that session
— Print-Tool uses exactly this path under ``NSPrintOperation``.  See the
``project-native-print-acpu`` auto-memory entry.

This module logs the resolved ``printSettings`` / ``dictionary`` after every run
for diagnostics.

macOS only.  Imported lazily by ``ui/tabs/tab_print.py`` when
``sys.platform == "darwin"``.
"""
from __future__ import annotations

import ctypes
from pathlib import Path

from PIL import Image

from core.logger import get_logger
from workflow.ppd_color import vendor_no_cm_settings

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
# The real "no colour management" mechanism is the *session*-level declaration in
# ``_apply_session_no_color_management`` (application output intent +
# ``PMSessionSetColorMatchingMode``), which is also what greys out the print
# panel's Color Matching pane.  This settings key mirrors it into the Cocoa /
# PrintCore settings as a backstop, set *locked* so it can't be silently
# rewritten between dialog and submission.  ``vendor_no_cm_settings`` additionally
# scans the selected printer's PPD for that driver's own "No Color Adjustment"
# option (e.g. Canon ``CNIJIntent2=1001``) and locks it too, so it doesn't matter
# whether a given vendor's PDE honours the Apple-level key.
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


# The output-intent dictionary returned by PrintCore is keyed by colour model;
# we only generate RGB charts, but log all three if present so a future
# grey/CMYK path is easy to diagnose.
_OUTPUT_INTENT_KEYS = (
    "PMSessionRGBOutputIntent",
    "PMSessionGrayOutputIntent",
    "PMSessionCMYKOutputIntent",
)


def _log_output_intent_profiles(intents_dict_ptr: int, label: str) -> None:
    """Log the device-profile name(s) inside an output-intent CFDictionary.

    This is the visibility Print-Tool gets from its ``OutputIntent = %@`` NSLog:
    on the Canon path it tells us *which* profile the print system is treating
    the chart pixels as already being in.  For a true colour-managed-off pass
    this should name the printer's own device profile (so the transform is
    identity), not a working space like sRGB.  Diagnostics only; never raises.
    """
    if not intents_dict_ptr:
        return
    for key in _OUTPUT_INTENT_KEYS:
        k_ref = _cfstr(key)
        try:
            prof = _cf.CFDictionaryGetValue(
                ctypes.c_void_p(intents_dict_ptr), ctypes.c_void_p(k_ref)
            )
        finally:
            if k_ref:
                _cf.CFRelease(ctypes.c_void_p(k_ref))
        if not prof:
            continue
        desc_ref = 0
        try:
            desc_ref = _appsvc.ColorSyncProfileCopyDescriptionString(ctypes.c_void_p(prof))
            name = _cfstr_to_py(desc_ref) or "<unnamed profile>"
        except Exception:  # pragma: no cover - diagnostics only
            name = "<description unavailable>"
        finally:
            if desc_ref:
                _cf.CFRelease(ctypes.c_void_p(desc_ref))
        log.info("native print: [%s] %s -> %s", label, key, name)


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
            if ppd:
                for key, val in vendor_no_cm_settings(ppd):
                    settings[key] = val
                    log.info("native print: driver no-colour option %s=%s", key, val)
    except Exception as exc:
        log.warning("native print: vendor PPD scan failed: %s", exc)
    return settings


class ColorManagementMismatch(RuntimeError):
    """Raised when the post-submit verification doesn't match the values we
    locked into the print settings — i.e. some part of the OS or driver stack
    overrode our ``AP_ApplicationColorMatching`` request after the dialog
    closed.  The job has already been submitted by the time this is raised;
    the caller should warn the user but not retry.
    """


def _verify_color_management(print_info, stage: str) -> dict[str, tuple[str | None, str]]:
    """Read each expected colour-management key back from *print_info*'s Cocoa
    ``printSettings`` dict and compare against the value we locked.  Logs a
    single ✓ line on success or a warning line on mismatch.

    Returns a mapping of mismatches ``{key: (observed, expected)}``; empty if
    every key matched.  *stage* is a short label ("post-dialog", "post-submit")
    so we can tell at which point a mismatch crept in.
    """
    expected = _locked_settings_for(print_info)
    cocoa = print_info.printSettings()
    mismatches: dict[str, tuple[str | None, str]] = {}
    parts: list[str] = []
    for key, want in expected.items():
        try:
            raw = cocoa.objectForKey_(key)
        except Exception:
            raw = None
        got = None if raw is None else str(raw)
        if got == want:
            parts.append(f"{key}={got}")
        else:
            mismatches[key] = (got, want)
            parts.append(f"{key}={got!r}!=({want})")
    summary = ", ".join(parts) if parts else "no keys to verify"
    if mismatches:
        log.warning("native print: [%s] colour-management verification FAILED — %s",
                    stage, summary)
    else:
        log.info("native print: [%s] colour management verified OFF (%s)",
                 stage, summary)
    return mismatches


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


def _apply_session_no_color_management(print_info) -> None:
    """Re-declare the printer's *default* output intent as the *application's*
    output intent and switch the print session to application-managed colour.

    This is the step ColorByte Print-Tool performs that ChromIQ previously did
    not.  Setting only the ``PMPrintSettings`` ``AP_ColorMatchingMode`` key (see
    ``_lock_no_color_management``) is enough for some drivers (e.g. Epson, which
    also exposes ``EPIJ_CMat``), but newer Canon macOS drivers keep running
    their internal colour engine regardless — the symptom a user hit on a Canon
    Pro-1000 under Tahoe, where charts printed as if a profile had been applied.

    Copying the printer's default output intent (its own device-space profiles)
    and re-declaring it as the application output intent tells the print system
    the bitmap is *already* in the device's space, so neither ColorSync nor the
    vendor colour engine transforms it — the same thing Print-Tool does, and
    why its Color Matching pane shows greyed out.

    Best-effort: every failure is logged and swallowed so a print is never
    blocked.  Reverse-engineered from Print-Tool 2.3.4; see the binding comment
    near ``_PM_SESSION_OK`` for the recovered signatures.
    """
    if not (_PRINTCORE_OK and _PM_SESSION_OK):
        return
    import objc

    try:
        pid = objc.pyobjc_id(print_info)
        session = _libobjc.objc_msgSend(
            ctypes.c_void_p(pid), _libobjc.sel_registerName(b"PMPrintSession"),
        )
        settings = _libobjc.objc_msgSend(
            ctypes.c_void_p(pid), _libobjc.sel_registerName(b"PMPrintSettings"),
        )
        if not session or not settings:
            log.warning("native print: PMPrintSession/Settings NULL — session intent skipped")
            return

        # 1. Copy the printer's default output intent (its device profiles).
        intents = ctypes.c_void_p(0)
        status = _appsvc.PMSessionCopyDefaultOutputIntentWithColorSyncProfiles(
            ctypes.c_void_p(session), ctypes.c_void_p(settings), ctypes.byref(intents),
        )
        if status == 0 and intents:
            # Log which device profile the print system says is the printer's
            # default — on the Canon this is the single most useful signal for
            # whether colour-off is really happening (it must name the printer's
            # own space, not sRGB/working space).
            _log_output_intent_profiles(intents.value or 0, "default-intent")
            # 2. Re-declare it as the *application's* output intent → the print
            #    system treats the pixels as already device-targeted (no CM).
            st2 = _appsvc.PMSessionSetApplicationOutputIntentWithColorSyncProfiles(
                ctypes.c_void_p(session), ctypes.c_void_p(settings), intents,
            )
            if st2 != 0:
                log.warning("native print: SetApplicationOutputIntent -> %d", st2)
            else:
                log.info("native print: application output intent declared (device-space passthrough)")
            _cf.CFRelease(intents)
        elif status == 0:
            # Not a fault: this driver simply registers no default output
            # intent, so the device-space redeclare (the anti-vendor-CM step)
            # has nothing to work with. The ColorSync-off lock and the
            # application-managed-colour switch below still apply. Logged as
            # info — the WARNING wording alarmed a user mid-print session
            # (Sebastian, 2026-08-10).
            log.info(
                "native print: driver reports no default output intent — "
                "device-space redeclare skipped; colour-off lock and "
                "application-managed colour still apply")
        else:
            log.warning(
                "native print: CopyDefaultOutputIntent -> %d (intents=%s)",
                status, bool(intents),
            )

        # 3. Switch the session itself to application-managed colour.
        mode_ref = _cfstr("AP_ApplicationColorMatching")
        try:
            st3 = _appsvc.PMSessionSetColorMatchingMode(
                ctypes.c_void_p(session), ctypes.c_void_p(settings),
                ctypes.c_void_p(mode_ref),
            )
            if st3 != 0:
                log.warning("native print: SetColorMatchingMode -> %d", st3)
        finally:
            if mode_ref:
                _cf.CFRelease(ctypes.c_void_p(mode_ref))
    except Exception as exc:
        log.warning("native print: session output-intent setup failed: %s", exc)


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


def print_frames(pages: list[tuple[Path, int]]) -> None:
    """Show the native macOS print dialog for *pages* and submit them as one job.

    *pages* is a list of ``(tiff_path, frame_index)`` tuples — the same shape
    ``TiffPreview._pages`` uses.  Each entry becomes one printed page, drawn at
    the TIFF's native size (from its resolution tag) with no scaling and no
    colour management.  Raises on failure; the caller surfaces it to the user.
    Must be called on the main (GUI) thread.
    """
    if not pages:
        return
    if _ChartPrintView is None:
        raise RuntimeError("PyObjC AppKit is not available on this system")

    import AppKit

    reps: list = []
    sizes_pt: list[tuple[float, float]] = []
    for tiff_path, frame in pages:
        with Image.open(tiff_path) as im:
            n_frames = getattr(im, "n_frames", 1)
            im.seek(min(frame, n_frames - 1))
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

    # Lock "no colour management" *before* the dialog so its colour panes open
    # greyed out, then show the dialog (for paper / quality / copies), then lock
    # it again afterwards in case a pane reset it — the same dance ACPU does.
    _lock_no_color_management(print_info)
    _apply_session_no_color_management(print_info)

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
        return

    _lock_no_color_management(print_info)
    _apply_session_no_color_management(print_info)
    # Verify the lock survived the dialog before we hand the job to the spooler.
    _verify_color_management(print_info, "post-dialog")

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
        return
    # Verify what the submitted job actually carried.  If something overrode
    # the lock between our re-apply and submission, surface it to the user.
    mismatches = _verify_color_management(pi_after, "post-submit")
    if mismatches:
        details = ", ".join(
            f"{k}={got!r} (expected {want!r})" for k, (got, want) in mismatches.items()
        )
        raise ColorManagementMismatch(
            "the job was submitted but ChromIQ could not verify that colour "
            "management was disabled — " + details
        )
