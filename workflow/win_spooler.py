"""The Windows print spooler, reached directly (#205).

ChromIQ's own print route on Windows sends a PostScript printer the chart as
ChromIQ's own PostScript, past the printer driver, the way ``lp -o raw`` does
on macOS: ``OpenPrinter`` / ``StartDocPrinter`` / ``WritePrinter``. This module
is that and nothing else, in ctypes (no pywin32), and imports on every
platform; every function that needs the spooler raises ``SpoolerError`` off
Windows.

Measured on Windows 11 25H2 ARM64, 2026-10-20 (#205):

* **A v3 driver passes RAW data to the port byte for byte** (Epson ET-8550
  driver on a file port: the file equals the PostScript sent).
* **A v4 driver does not.** With the RAW datatype the v4 Microsoft PS Class
  Driver ends the job in the print processor (event 372, 0x80004005) and the
  port receives 0 bytes, on a file port and on a TCP/IP port alike. Microsoft
  documents it (KB 2779300): a v4 driver is XPS-based, and raw data for it
  must be submitted as **XPS_PASS**, chosen by ``PRINTER_DRIVER_XPS`` in
  ``DRIVER_INFO_8.dwPrinterDriverAttributes``. With XPS_PASS the same
  PostScript reached a 9100 capture port byte for byte.
* **A PostScript driver is one whose data file is a PPD**: the v3 PostScript
  drivers (``PSCRIPT5.DLL`` with the vendor's PPD) and the v4 Microsoft PS
  Class Driver (``MSxpsPS.ppd``) alike. The Epson inkjet driver's data file is
  a ``.VIF`` and Microsoft Print to PDF's an ``.xml``; GDI's GETTECHNOLOGY
  escape cannot tell (every v4 queue answers the XPS schema URL, and the Epson
  inkjet answers "ESC/Page").
"""
from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: DRIVER_INFO_8.dwPrinterDriverAttributes: the driver is XPS-based (every v4
#: driver), so raw data goes as XPS_PASS
PRINTER_DRIVER_XPS = 0x00000002
#: PRINTER_INFO_2.Attributes: "Use Printer Offline" is ticked
PRINTER_ATTRIBUTE_WORK_OFFLINE = 0x00000400

#: JOB_INFO_1.Status bits that mean the job will not print without help (the
#: same idea as CUPS' held / stopped / aborted, ``PrintModule.get_stuck_jobs``)
JOB_STATUS_PAUSED = 0x00000001
JOB_STATUS_ERROR = 0x00000002
JOB_STATUS_OFFLINE = 0x00000020
JOB_STATUS_PAPEROUT = 0x00000040
JOB_STATUS_BLOCKED_DEVQ = 0x00000200
JOB_STATUS_USER_INTERVENTION = 0x00000400
JOB_STATUS_DELETING = 0x00000004
JOB_STATUS_PRINTED = 0x00000080
JOB_STATUS_DELETED = 0x00000100
JOB_STATUS_COMPLETE = 0x00001000
STUCK_JOB_STATUS = (JOB_STATUS_PAUSED | JOB_STATUS_ERROR | JOB_STATUS_OFFLINE
                    | JOB_STATUS_PAPEROUT | JOB_STATUS_BLOCKED_DEVQ
                    | JOB_STATUS_USER_INTERVENTION)

_JOB_CONTROL_DELETE = 5
_PRINTER_ENUM_LOCAL = 0x00000002
_PRINTER_ENUM_CONNECTIONS = 0x00000004

DATATYPE_RAW = "RAW"
DATATYPE_XPS_PASS = "XPS_PASS"


class SpoolerError(OSError):
    """The spooler refused, or this is not Windows."""


@dataclass(frozen=True)
class DriverFacts:
    """What the spooler says about a queue's driver."""
    name: str
    version: int                 #: 3 or 4 (cVersion)
    driver_path: str
    data_file: str
    attributes: int              #: dwPrinterDriverAttributes
    manufacturer: str = ""

    @property
    def is_xps(self) -> bool:
        return bool(self.attributes & PRINTER_DRIVER_XPS)

    @property
    def ppd(self) -> "str | None":
        """The driver's PPD when its data file is one, else None."""
        if self.data_file and self.data_file.lower().endswith(".ppd"):
            return self.data_file
        return None

    @property
    def is_postscript(self) -> bool:
        return self.ppd is not None or \
            os.path.basename(self.driver_path or "").upper() == "PSCRIPT5.DLL"

    @property
    def datatype(self) -> str:
        """The datatype raw PostScript must be submitted as."""
        return DATATYPE_XPS_PASS if self.is_xps else DATATYPE_RAW


@dataclass(frozen=True)
class JobFacts:
    job_id: int
    document: str
    datatype: str
    status: int
    status_text: str
    pages: int


def available() -> bool:
    return sys.platform == "win32"


# --------------------------------------------------------------------------
# ctypes plumbing (built on first use, only on Windows)
# --------------------------------------------------------------------------

_API = None


def _api():
    global _API
    if _API is not None:
        return _API
    if not available():
        raise SpoolerError("the Windows print spooler exists only on Windows")
    from ctypes import wintypes as W

    class DRIVER_INFO_8(ctypes.Structure):
        _fields_ = [("cVersion", W.DWORD), ("pName", W.LPWSTR),
                    ("pEnvironment", W.LPWSTR), ("pDriverPath", W.LPWSTR),
                    ("pDataFile", W.LPWSTR), ("pConfigFile", W.LPWSTR),
                    ("pHelpFile", W.LPWSTR), ("pDependentFiles", ctypes.c_void_p),
                    ("pMonitorName", W.LPWSTR), ("pDefaultDataType", W.LPWSTR),
                    ("pszzPreviousNames", ctypes.c_void_p),
                    ("ftDriverDate", W.FILETIME),
                    ("dwlDriverVersion", ctypes.c_ulonglong),
                    ("pszMfgName", W.LPWSTR), ("pszOEMUrl", W.LPWSTR),
                    ("pszHardwareID", W.LPWSTR), ("pszProvider", W.LPWSTR),
                    ("pszPrintProcessor", W.LPWSTR), ("pszVendorSetup", W.LPWSTR),
                    ("pszzColorProfiles", ctypes.c_void_p),
                    ("pszInfPath", W.LPWSTR),
                    ("dwPrinterDriverAttributes", W.DWORD),
                    ("pszzCoreDriverDependencies", ctypes.c_void_p),
                    ("ftMinInboxDriverVerDate", W.FILETIME),
                    ("dwlMinInboxDriverVerVersion", ctypes.c_ulonglong)]

    class PRINTER_INFO_4(ctypes.Structure):
        _fields_ = [("pPrinterName", W.LPWSTR), ("pServerName", W.LPWSTR),
                    ("Attributes", W.DWORD)]

    class PRINTER_INFO_2(ctypes.Structure):
        _fields_ = [("pServerName", W.LPWSTR), ("pPrinterName", W.LPWSTR),
                    ("pShareName", W.LPWSTR), ("pPortName", W.LPWSTR),
                    ("pDriverName", W.LPWSTR), ("pComment", W.LPWSTR),
                    ("pLocation", W.LPWSTR), ("pDevMode", ctypes.c_void_p),
                    ("pSepFile", W.LPWSTR), ("pPrintProcessor", W.LPWSTR),
                    ("pDatatype", W.LPWSTR), ("pParameters", W.LPWSTR),
                    ("pSecurityDescriptor", ctypes.c_void_p),
                    ("Attributes", W.DWORD), ("Priority", W.DWORD),
                    ("DefaultPriority", W.DWORD), ("StartTime", W.DWORD),
                    ("UntilTime", W.DWORD), ("Status", W.DWORD),
                    ("cJobs", W.DWORD), ("AveragePPM", W.DWORD)]

    class JOB_INFO_1(ctypes.Structure):
        _fields_ = [("JobId", W.DWORD), ("pPrinterName", W.LPWSTR),
                    ("pMachineName", W.LPWSTR), ("pUserName", W.LPWSTR),
                    ("pDocument", W.LPWSTR), ("pDatatype", W.LPWSTR),
                    ("pStatus", W.LPWSTR), ("Status", W.DWORD),
                    ("Priority", W.DWORD), ("Position", W.DWORD),
                    ("TotalPages", W.DWORD), ("PagesPrinted", W.DWORD),
                    ("Submitted", W.WORD * 8)]

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", W.LPWSTR), ("pOutputFile", W.LPWSTR),
                    ("pDatatype", W.LPWSTR)]

    ws = ctypes.WinDLL("winspool.drv", use_last_error=True)
    H, P, DW, B = W.HANDLE, ctypes.c_void_p, W.DWORD, W.BOOL
    LPDW = ctypes.POINTER(W.DWORD)
    ws.OpenPrinterW.argtypes = (W.LPCWSTR, ctypes.POINTER(H), P)
    ws.OpenPrinterW.restype = B
    ws.ClosePrinter.argtypes = (H,)
    ws.ClosePrinter.restype = B
    ws.GetPrinterDriverW.argtypes = (H, W.LPWSTR, DW, P, DW, LPDW)
    ws.GetPrinterDriverW.restype = B
    ws.GetPrinterW.argtypes = (H, DW, P, DW, LPDW)
    ws.GetPrinterW.restype = B
    ws.EnumPrintersW.argtypes = (DW, W.LPWSTR, DW, P, DW, LPDW, LPDW)
    ws.EnumPrintersW.restype = B
    ws.EnumJobsW.argtypes = (H, DW, DW, DW, P, DW, LPDW, LPDW)
    ws.EnumJobsW.restype = B
    ws.GetJobW.argtypes = (H, DW, DW, P, DW, LPDW)
    ws.GetJobW.restype = B
    ws.SetJobW.argtypes = (H, DW, DW, P, DW)
    ws.SetJobW.restype = B
    ws.StartDocPrinterW.argtypes = (H, DW, ctypes.POINTER(DOC_INFO_1))
    ws.StartDocPrinterW.restype = DW
    ws.StartPagePrinter.argtypes = (H,)
    ws.StartPagePrinter.restype = B
    ws.EndPagePrinter.argtypes = (H,)
    ws.EndPagePrinter.restype = B
    ws.EndDocPrinter.argtypes = (H,)
    ws.EndDocPrinter.restype = B
    ws.AbortPrinter.argtypes = (H,)
    ws.AbortPrinter.restype = B
    ws.WritePrinter.argtypes = (H, P, DW, LPDW)
    ws.WritePrinter.restype = B
    ws.GetDefaultPrinterW.argtypes = (W.LPWSTR, LPDW)
    ws.GetDefaultPrinterW.restype = B

    class _Api:
        pass

    api = _Api()
    api.ws, api.W = ws, W
    api.DRIVER_INFO_8, api.PRINTER_INFO_4 = DRIVER_INFO_8, PRINTER_INFO_4
    api.PRINTER_INFO_2, api.JOB_INFO_1, api.DOC_INFO_1 = \
        PRINTER_INFO_2, JOB_INFO_1, DOC_INFO_1
    _API = api
    return api


def _error(what: str) -> SpoolerError:
    code = ctypes.get_last_error()
    text = (ctypes.FormatError(code).strip() if hasattr(ctypes, "FormatError")
            else str(code))
    err = SpoolerError(code, f"{what}: {text}")
    #: Windows' own sentence alone, for the window (#205 review: str() of the
    #: error reads "[Errno 1801] OpenPrinter('...'): ..."); the log keeps all
    err.windows_text = text
    return err


class _Printer:
    """An open printer handle, closed on exit."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.handle = None

    def __enter__(self):
        api = _api()
        h = api.W.HANDLE()
        if not api.ws.OpenPrinterW(self.name, ctypes.byref(h), None):
            raise _error(f"OpenPrinter({self.name!r})")
        self.handle = h
        return h

    def __exit__(self, *exc) -> None:
        if self.handle:
            _api().ws.ClosePrinter(self.handle)
            self.handle = None


def _two_call(fn, *args):
    """Call a size-then-fill spooler function; the filled buffer, or None
    when there is nothing to return."""
    api = _api()
    need = api.W.DWORD()
    fn(*args, None, 0, ctypes.byref(need))
    if need.value == 0:
        return None
    buf = ctypes.create_string_buffer(need.value)
    if not fn(*args, buf, need, ctypes.byref(need)):
        raise _error(fn.__name__)
    return buf


# --------------------------------------------------------------------------
# printers and their drivers
# --------------------------------------------------------------------------

def list_printers() -> list[str]:
    """Every queue this user can print to: local ones and connections."""
    api = _api()
    need, count = api.W.DWORD(), api.W.DWORD()
    flags = _PRINTER_ENUM_LOCAL | _PRINTER_ENUM_CONNECTIONS
    api.ws.EnumPrintersW(flags, None, 4, None, 0, ctypes.byref(need), ctypes.byref(count))
    if need.value == 0:
        return []
    buf = ctypes.create_string_buffer(need.value)
    if not api.ws.EnumPrintersW(flags, None, 4, buf, need, ctypes.byref(need),
                                ctypes.byref(count)):
        raise _error("EnumPrinters")
    arr = ctypes.cast(buf, ctypes.POINTER(api.PRINTER_INFO_4))
    return [arr[i].pPrinterName for i in range(count.value) if arr[i].pPrinterName]


def default_printer() -> str:
    api = _api()
    need = api.W.DWORD(0)
    api.ws.GetDefaultPrinterW(None, ctypes.byref(need))
    if need.value == 0:
        return ""
    buf = ctypes.create_unicode_buffer(need.value)
    if not api.ws.GetDefaultPrinterW(buf, ctypes.byref(need)):
        return ""
    return buf.value


def driver_facts(printer: str) -> DriverFacts:
    api = _api()
    with _Printer(printer) as h:
        buf = _two_call(api.ws.GetPrinterDriverW, h, None, 8)
    if buf is None:
        raise SpoolerError(f"no driver information for {printer!r}")
    d = api.DRIVER_INFO_8.from_buffer(buf)
    return DriverFacts(name=d.pName or "", version=int(d.cVersion),
                       driver_path=d.pDriverPath or "", data_file=d.pDataFile or "",
                       attributes=int(d.dwPrinterDriverAttributes),
                       manufacturer=d.pszMfgName or "")


def ppd_path(printer: str) -> "str | None":
    """The PPD of *printer*'s driver when it is a PostScript driver whose PPD
    is readable, else None (never raises)."""
    if not available() or not printer:
        return None
    try:
        ppd = driver_facts(printer).ppd
    except OSError as exc:
        log.debug("no driver facts for %s: %s", printer, exc)
        return None
    return ppd if ppd and Path(ppd).is_file() else None


def is_postscript(printer: str) -> bool:
    """True when *printer*'s driver is a PostScript driver (never raises)."""
    if not available() or not printer:
        return False
    try:
        return driver_facts(printer).is_postscript
    except OSError:
        return False


def is_offline(printer: str) -> bool:
    """True when the queue is set to "Use Printer Offline", or is gone.

    Only what the user (or Windows) set on the queue: the status a network
    printer reports is often stale (asleep reads as offline), and the direct
    route on macOS refuses only a queue CUPS has stopped."""
    api = _api()
    try:
        with _Printer(printer) as h:
            buf = _two_call(api.ws.GetPrinterW, h, 2)
    except OSError:
        return True
    if buf is None:
        return True
    info = api.PRINTER_INFO_2.from_buffer(buf)
    return bool(info.Attributes & PRINTER_ATTRIBUTE_WORK_OFFLINE)


# --------------------------------------------------------------------------
# jobs
# --------------------------------------------------------------------------

def submit(printer: str, data: bytes, document: str,
           datatype: "str | None" = None) -> int:
    """Send *data* to *printer* past its driver; the spooler's job id.

    *datatype* defaults to the one the driver needs (``DriverFacts.datatype``).
    A job the spooler took and then could not finish is aborted, so nothing
    half-written is left in the queue."""
    api = _api()
    if datatype is None:
        datatype = driver_facts(printer).datatype
    with _Printer(printer) as h:
        doc = api.DOC_INFO_1(document, None, datatype)
        job = api.ws.StartDocPrinterW(h, 1, ctypes.byref(doc))
        if not job:
            raise _error(f"StartDocPrinter({printer!r}, {datatype})")
        try:
            if not api.ws.StartPagePrinter(h):
                raise _error("StartPagePrinter")
            written = api.W.DWORD(0)
            buf = ctypes.create_string_buffer(data, len(data))
            if not api.ws.WritePrinter(h, buf, len(data), ctypes.byref(written)):
                raise _error("WritePrinter")
            if written.value != len(data):
                raise SpoolerError(f"WritePrinter wrote {written.value} of {len(data)} bytes")
            if not api.ws.EndPagePrinter(h):
                raise _error("EndPagePrinter")
        except OSError:
            api.ws.AbortPrinter(h)
            raise
        if not api.ws.EndDocPrinter(h):
            raise _error("EndDocPrinter")
    log.info("spooler: job %d on %s, %d bytes as %s", job, printer, len(data), datatype)
    return int(job)


def _job_facts(api, j) -> JobFacts:
    return JobFacts(job_id=int(j.JobId), document=j.pDocument or "",
                    datatype=j.pDatatype or "", status=int(j.Status),
                    status_text=j.pStatus or "", pages=int(j.TotalPages))


def jobs(printer: str) -> list[JobFacts]:
    """The jobs in *printer*'s queue now."""
    api = _api()
    with _Printer(printer) as h:
        need, count = api.W.DWORD(), api.W.DWORD()
        api.ws.EnumJobsW(h, 0, 999, 1, None, 0, ctypes.byref(need), ctypes.byref(count))
        if need.value == 0:
            return []
        buf = ctypes.create_string_buffer(need.value)
        if not api.ws.EnumJobsW(h, 0, 999, 1, buf, need, ctypes.byref(need),
                                ctypes.byref(count)):
            raise _error("EnumJobs")
        arr = ctypes.cast(buf, ctypes.POINTER(api.JOB_INFO_1))
        return [_job_facts(api, arr[i]) for i in range(count.value)]


def job(printer: str, job_id: int) -> "JobFacts | None":
    """One job, or None once it has left the queue (printed, or deleted)."""
    api = _api()
    with _Printer(printer) as h:
        need = api.W.DWORD()
        api.ws.GetJobW(h, job_id, 1, None, 0, ctypes.byref(need))
        if need.value == 0:
            return None
        buf = ctypes.create_string_buffer(need.value)
        if not api.ws.GetJobW(h, job_id, 1, buf, need, ctypes.byref(need)):
            return None
        return _job_facts(api, api.JOB_INFO_1.from_buffer(buf))


def stuck_jobs(printer: str) -> list[int]:
    """The ids of *printer*'s jobs that will not print without help."""
    return [j.job_id for j in jobs(printer)
            if j.status & STUCK_JOB_STATUS
            and not j.status & (JOB_STATUS_DELETING | JOB_STATUS_DELETED)]


def cancel_jobs(printer: str) -> int:
    """Delete every job in *printer*'s queue; how many were deleted."""
    api = _api()
    count = 0
    ids = [j.job_id for j in jobs(printer)]
    with _Printer(printer) as h:
        for jid in ids:
            if api.ws.SetJobW(h, jid, 0, None, _JOB_CONTROL_DELETE):
                count += 1
            else:
                log.warning("spooler: could not delete job %d on %s (%d)",
                            jid, printer, ctypes.get_last_error())
    return count
