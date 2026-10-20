"""ChromIQ's own print route on Windows (#205): a PostScript printer gets the
chart as ChromIQ's own PostScript, raw through the spooler.

The macOS direct route hands ``lp`` a PostScript file and CUPS puts the
options the Print Chart tab chose (paper size, media type, quality, tray) into
the job from the queue's PPD. On Windows nothing does that for a raw job: raw
data goes past the driver, and the settings in the driver's own dialog
(DEVMODE) never reach it. So this module does what CUPS' ``pstops`` does: it
puts each chosen option's PostScript code from the PPD into the document, in
the PPD's order, each in a ``stopped`` context so that an option the printer
does not understand cannot end the job. (The Microsoft PS Class Driver's PPD
code calls ``featurebegin``, a procedure that exists only in that driver's
own prolog: unprotected, it would be an ``undefined`` error.)

The chart's colours are what ``PostScriptGenerator`` writes on every
platform: DeviceRGB, DeviceCMYK or DeviceN with the chart's own values, page
size set by ``setpagedevice``, placed 1:1. Nothing on the way converts them:
measured 2026-10-20, the spooler delivered the document to the port byte for
byte, through a v3 driver (RAW) and the v4 Microsoft PS Class Driver
(XPS_PASS).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

from core.logger import get_logger
from core.text_io import read_text
from workflow import win_spooler
from workflow.cups_printer import PrintConfig
from workflow.postscript_generator import PostScriptGenerator

log = get_logger(__name__)

#: OrderDependency sections that belong in the document's setup, in order
_SETUP_SECTIONS = ("ExitServer", "Prolog", "DocumentSetup", "AnySetup", "PageSetup")

_OPENUI_RE = re.compile(
    r'^\*(?:JCL)?OpenUI\s+\*(\S+?)\s*(?:/([^:]*))?:\s*(PickOne|Boolean|PickMany)',
    re.M | re.I)
_ORDER_RE = re.compile(r'^\*(?:Non)?OrderDependency:\s*([\d.]+)\s+(\S+)\s+\*(\S+)', re.M)
_INCLUDE_RE = re.compile(r'^\*Include:\s*"([^"]+)"[ \t]*$', re.M)

#: PSCRIPT5's prolog defines ``featurebegin`` / ``featurecleanup``, which the
#: Xerox v4 PPDs and the Microsoft PS Class Driver's call in every choice
#: (``featurebegin{<< /MediaType (...) >> setpagedevice}featurecleanup``). A
#: raw job carries no such prolog, so without these the ``stopped`` around the
#: feature swallowed an ``undefined`` and the choice was never applied (#205
#: review, measured with Ghostscript). Defined only where the printer lacks them.
_FEATUREBEGIN_SHIM = ("/featurebegin where { pop } { userdict /featurebegin { } put "
                      "userdict /featurecleanup { exec } put } ifelse")


def read_ppd(path: "str | Path", _depth: int = 0) -> str:
    """A Windows driver's PPD with its ``*Include`` files in place (#205
    review): Microsoft's HP DesignJet T1300ps / Z3200ps data file is a stub
    whose Media Type and Paper Source live in ``*Include: "hpips3.PPD"``.
    CUPS resolves includes on macOS; a Windows PPD is read here. A relative
    name is looked up beside the including file; a missing one is left out."""
    p = Path(path)
    text = read_text(p, lenient=True)
    if _depth >= 8 or "*Include" not in text:
        return text

    def _inline(m: "re.Match[str]") -> str:
        name = m.group(1).strip()
        inc = Path(name) if Path(name).is_absolute() else p.parent / name
        if not inc.is_file():
            log.warning("PPD %s includes %s, which is not there; left out", p, name)
            return ""
        return read_ppd(inc, _depth + 1)

    return _INCLUDE_RE.sub(_inline, text)


def _decode(label: str) -> str:
    from workflow.page_geometry import ppd_text_label
    return ppd_text_label(label or "").strip()


def _spelled_out(keyword: str) -> str:
    """A PPD keyword as words, for an option with no translation string
    ("PageSize" -> "Page Size", "MediaType" -> "Media Type")."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", keyword)


def ppd_options(ppd_text: str) -> "dict[str, tuple[str, list[tuple[str, str]]]]":
    """``{option: (label, [(value, value_label), ...])}`` for every UI option
    of a PPD, with or without translation strings (a Windows PPD such as the
    Microsoft PS Class Driver's has none: ``*PageSize A4: "..."``). A value
    with no translation is labelled with its own name."""
    out: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    lines = ppd_text.splitlines()
    i = 0
    while i < len(lines):
        m = _OPENUI_RE.match(lines[i])
        if not m:
            i += 1
            continue
        key = m.group(1)
        label = _decode(m.group(2)) or _spelled_out(key)
        val_re = re.compile(rf'^\*{re.escape(key)}\s+([^\s/:]+)\s*(?:/([^:]*))?:')
        values: list[tuple[str, str]] = []
        j = i + 1
        while j < len(lines) and not re.match(r'^\*(?:JCL)?CloseUI', lines[j]):
            vm = val_re.match(lines[j])
            if vm and vm.group(1) not in {v for v, _ in values}:
                values.append((vm.group(1), _decode(vm.group(2)) or vm.group(1)))
            j += 1
        out[key] = (label, values)
        i = j + 1
    return out


def feature_code(ppd_text: str, option: str, value: str) -> "str | None":
    """The PostScript code of *option*'s choice *value* in the PPD, None when
    the PPD has no such choice. The quoted string may span lines (it ends at
    the next ``"``). A symbol value (``*InputSlot Upper: ^UpperTray``) is not
    resolved: such a choice has no code here and is left out of the job."""
    m = re.search(rf'^\*{re.escape(option)}\s+{re.escape(value)}\s*(?:/[^:]*)?:\s*"',
                  ppd_text, re.M)
    if not m:
        return None
    end = ppd_text.find('"', m.end())
    if end < 0:
        return None
    return ppd_text[m.end():end].strip()


def order_of(ppd_text: str, option: str) -> "tuple[float, str]":
    """(order, section) from the option's ``*OrderDependency``; an option the
    PPD gives none is placed last in AnySetup, as the PPD spec says."""
    for m in _ORDER_RE.finditer(ppd_text):
        if m.group(3) == option:
            try:
                return float(m.group(1)), m.group(2)
            except ValueError:
                break
    return 1e9, "AnySetup"


def _hex_decoded(raw: str) -> str:
    """A PPD QuotedValue with its hex substrings decoded (``<1B>`` is the
    escape that starts a PJL command, ``<0A>`` a line end). JCL strings are
    QuotedValues; PostScript code is an InvocationValue and is sent as
    written."""
    return re.sub(r"<([0-9A-Fa-f\s]+)>",
                  lambda h: bytes.fromhex(re.sub(r"\s", "", h.group(1))).decode("latin-1"),
                  raw)


def _jcl(ppd_text: str, keyword: str) -> str:
    m = re.search(rf'^\*{keyword}:\s*"', ppd_text, re.M)
    if not m:
        return ""
    end = ppd_text.find('"', m.end())
    if end < 0:
        return ""
    return _hex_decoded(ppd_text[m.end():end])


def with_features(ps_text: str, ppd_text: str, options: "dict[str, str]") -> str:
    """*ps_text* with the PPD code of every chosen option (value not "")
    inserted after its header, in OrderDependency order, each protected by
    ``stopped``. Options in the JCLSetup section go in a PJL header before
    the PostScript, when the PPD has ``*JCLBegin`` (CUPS does the same).
    Unknown options or choices are left out (logged)."""
    setup: list[tuple[float, str, str, str]] = []
    jcl: list[tuple[float, str]] = []
    for option, value in options.items():
        if not value or option.startswith("__"):
            continue
        code = feature_code(ppd_text, option, value)
        if code is None:
            log.info("PPD has no %s %s; not put into the job", option, value)
            continue
        order, section = order_of(ppd_text, option)
        if section == "JCLSetup":
            jcl.append((order, _hex_decoded(code)))
            continue
        if section not in _SETUP_SECTIONS:
            section = "AnySetup"
        setup.append((order, option, value, code))
    setup.sort(key=lambda t: t[0])
    jcl.sort(key=lambda t: t[0])

    block = ""
    if setup:
        parts = ["%%BeginSetup"]
        if any("featurebegin" in code for _o, _k, _v, code in setup):
            parts.append(_FEATUREBEGIN_SHIM)
        for _order, option, value, code in setup:
            parts.append(
                f"[{{\n%%BeginFeature: *{option} {value}\n{code}\n%%EndFeature\n"
                f"}} stopped cleartomark")
        parts.append("%%EndSetup")
        block = "\n".join(parts) + "\n"
    out = ps_text
    if block:
        marker = "%%EndComments\n"
        at = out.find(marker)
        if at < 0:
            out = block + out
        else:
            at += len(marker)
            out = out[:at] + block + out[at:]
    if jcl:
        begin, to_ps, end = (_jcl(ppd_text, "JCLBegin"),
                             _jcl(ppd_text, "JCLToPSInterpreter"),
                             _jcl(ppd_text, "JCLEnd"))
        if begin and to_ps:
            head = begin + "".join(c.replace("\r\n", "\n").rstrip("\n") + "\n"
                                   for _o, c in jcl) + to_ps
            out = head + out + (end or "")
        else:
            log.info("PPD has JCL options but no *JCLBegin; left out")
    return out


class WindowsRawPrinter:
    """The Windows counterpart of ``CupsRawPrinter`` for the Print Chart
    tab's own route: the same ``print_job_ps`` call, sent raw."""

    #: the spooler's job id of the last submission
    last_job_id: "int | None" = None
    #: no paper-profile job on Windows (the macOS Canon/Epson reference job)
    last_paper_profile = None
    last_expected: "dict[str, str]" = {}
    #: the spooler's reason when the last submission failed, for the window
    last_error: str = ""

    def print_job_ps(
        self,
        tiff_path: Path,
        config: PrintConfig,
        ink_channels: "list[str] | None" = None,
        on_finish: "Callable[[int], None] | None" = None,
        orientation: "int | None" = None,
        page_size_pt: "tuple[float, float] | None" = None,
        pdf_fallback: bool = False,
    ) -> None:
        """Send *tiff_path* as PostScript to the queue in *config*.

        *orientation* and *pdf_fallback* are ``CupsRawPrinter``'s and mean
        nothing here: the PostScript carries its own page, and a Windows queue
        that is not PostScript never gets this far (the tab hands an RGB chart
        to the Windows dialog and refuses any other). *on_finish* is called
        once, with 0 when the spooler took the job, else -1."""
        self.last_job_id = None
        self.last_error = ""
        self.last_error_is_chart = False
        self.last_chart_name = tiff_path.name
        self.last_expected = {}
        code = -1
        try:
            data = self.job_bytes(tiff_path, config, ink_channels, page_size_pt)
        except Exception as exc:  # noqa: BLE001 - ChromIQ's own failure, not Windows'
            # (review finding 6) the chart could not be read or turned into
            # PostScript: the tab says so, never "Windows did not accept"
            self.last_error, self.last_error_is_chart = str(exc), True
            log.error("Windows raw print: could not build the job for %s: %s",
                      tiff_path.name, exc)
            if on_finish:
                on_finish(code)
            return
        try:
            self.last_job_id = win_spooler.submit(
                config.printer_name, data, f"ChromIQ - {tiff_path.name}")
            code = 0
        except Exception as exc:  # noqa: BLE001 - the window says why
            self.last_error = getattr(exc, "windows_text", "") or str(exc)
            log.error("Windows raw print of %s to %s failed: %s",
                      tiff_path.name, config.printer_name, exc)
        if on_finish:
            on_finish(code)

    @staticmethod
    def job_bytes(tiff_path: Path, config: PrintConfig,
                  ink_channels: "list[str] | None" = None,
                  page_size_pt: "tuple[float, float] | None" = None) -> bytes:
        """The exact bytes the queue gets: ChromIQ's PostScript with the PPD
        code of the chosen options."""
        ps_text = PostScriptGenerator().generate(
            tiff_path, ink_channels=ink_channels, page_size_pt=page_size_pt)
        ppd = win_spooler.ppd_path(config.printer_name)
        if ppd:
            ps_text = with_features(ps_text, read_ppd(ppd),
                                    dict(config.options or {}))
        log.info("Windows raw print: %s to %s, options %s", tiff_path.name,
                 config.printer_name,
                 {k: v for k, v in (config.options or {}).items() if v})
        return ps_text.encode("latin-1", errors="replace")

    @staticmethod
    def is_printer_reachable(printer_name: str) -> bool:
        try:
            return not win_spooler.is_offline(printer_name)
        except Exception:  # noqa: BLE001 - never block a print on the check
            return True
