"""Send a TIFF print target to a CUPS printer via PostScript."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field as _field
from pathlib import Path
from typing import Callable

from core.logger import get_logger
from core.proc_text import decode_output
from workflow.postscript_generator import PdfGenerator, PostScriptGenerator
from workflow.ppd_color import (APPLICATION_COLOUR_MATCHING, PaperProfile,
                                paper_profile_for_queue,
                                vendor_no_cm_settings_for_queue)

log = get_logger(__name__)


def _tiff_page_pt(tiff_path: Path) -> "tuple[float, float] | None":
    """The chart page's size in points: the exact-size PDF's MediaBox when no
    paper size is chosen (PdfGenerator falls back to it)."""
    try:
        from workflow.page_geometry import read_tiff_dimensions_points
        return read_tiff_dimensions_points(tiff_path)
    except Exception:  # noqa: BLE001
        return None


def _name_the_default_page(opts: dict[str, str], printer_name: str,
                           page_size_pt: "tuple[float, float] | None",
                           ppd_path: "str | None" = None
                           ) -> "tuple[float, float] | None":
    """Name the driver's default paper on an exact-size PDF job that names none.

    Beta 16 final (measured on a PRO-300 capture queue): with the paper size
    at "Printer Default" the job carries no PageSize, and macOS matches the
    PDF's MediaBox (A4, no margins) to the driver's BORDERLESS twin of the
    default paper, "A4.FullBleed". The Canon driver then prints borderless
    and enlarges the page by its borderless extension: the chart came out at
    101.7 %, borderless. "Printer Default" means the driver's default paper,
    so that is named, and only when it is the chart's own size (within 2 pt
    either way round) and not itself a borderless variant; anything else is
    left to the Print Chart tab's size check, as before. A vendor size key
    (Epson's EPIJ_Size) is left alone: it brings its own PageSize.

    Returns the named paper's (w, h) in points as the PPD gives it (portrait
    for A4), so the PDF can be laid out on it; None when nothing was named."""
    if page_size_pt is None or opts.get("PageSize") or opts.get("EPIJ_Size"):
        return None
    try:
        import re
        from core.text_io import read_text
        from workflow.page_geometry import get_page_size_points
        from workflow.ppd_color import ppd_path_for_queue
        path = ppd_path or ppd_path_for_queue(printer_name)
        if not path:
            return None
        m = re.search(r"^\*DefaultPageSize:\s*(\S+)", read_text(Path(path), lenient=True),
                      re.M)
        if not m:
            return None
        name = m.group(1)
        if any(s in name.lower() for s in ("fullbleed", "borderless")):
            return None
        dims = get_page_size_points(path, name)
        if dims is None:
            return None
        w, h = page_size_pt
        if min(abs(dims[0] - w) + abs(dims[1] - h),
               abs(dims[0] - h) + abs(dims[1] - w)) > 2.0:
            return None
        opts["PageSize"] = name
        log.info("CUPS print: exact-size PDF on %s names the driver's default "
                 "paper PageSize=%s, so macOS cannot pick its borderless twin",
                 printer_name, name)
        return dims
    except Exception as exc:  # pragma: no cover - defensive, never stops a print
        log.warning("default paper lookup failed for %s: %s", printer_name, exc)
    return None

try:
    import cups as _cups_mod
    CUPS_AVAILABLE = True
except ImportError:
    _cups_mod = None  # type: ignore[assignment]
    CUPS_AVAILABLE = False
    if sys.platform != "win32":
        log.warning("pycups not available — CUPS printing disabled")

# Options injected into PS print jobs.
# Colour space is declared in the PS document itself; only neutral job-ticket
# options go here.  ColorSync=None is PS-specific — do NOT use for PDF.
# Apple's PrintCore colour-matching key, honoured by cgpdftoraster as a plain
# CUPS job option: it stops the OS applying the PPD's cupsICCProfile
# destination transform.  Canon/Epson PPDs pass untagged device colour
# through bit-exact even without it, but HP DesignJet PPDs (hundreds of
# cupsICCProfile entries) re-render every job — including untagged device
# colour — unless this key is present (2026-06 no-ink filter-chain test:
# Z2100 PPD altered (255,0,0)→(219,0,0) etc.; with this key, 0 altered
# colours; Canon PRO-300 / Epson ET-8550 stay bit-exact with it).  It is the
# same key the native-dialog path locks via PMPrintSettings.
_AP_NO_CM = {"AP_ColorMatchingMode": "AP_ApplicationColorMatching"}

# Duplex/sides are also baked into the PS via setpagedevice — these are the
# CUPS-level belt-and-suspenders for PPDs that ignore the PS directive or
# strip it during filtering.
_PS_JOB_OPTIONS: dict[str, str] = {
    "ColorSync": "None",   # belt-and-suspenders alongside %cupsJobTicket
    "Duplex":    "None",
    "sides":     "one-sided",
    **_AP_NO_CM,
}

# Options for the exact-size PDF fallback.  No ColorSync=None here (it is
# PS-specific, see above): the PDF embeds the chart as *untagged* device
# colour, which Apple's cgpdftoraster passes through bit-exact — verified
# against both Canon and Epson PPDs (which do declare cupsICCProfile
# destinations) by rasterising no-ink and diffing patch colours — plus
# _AP_NO_CM for PPDs where cupsICCProfile *is* applied regardless (HP
# DesignJet).  Geometry is likewise ours: the MediaBox matches PageSize and
# the image is placed 1:1, so nothing downstream rescales it (unlike raw-TIFF
# submission, where cgimagetopdf shrinks full-page charts to the imageable
# area and ignores ppi/scaling options).
_PDF_JOB_OPTIONS: dict[str, str] = {
    "Duplex": "None",
    "sides":  "one-sided",
    **_AP_NO_CM,
}

# TIFF fallback options per channel count.  These mirror the original
# _COLOR_MGMT_OFF dict but are now colour-space-aware.  They tell CUPS
# exactly how to format the raster data for the printer driver — bypassing
# ColorSync — without hardcoding DeviceRGB for every job.  _AP_NO_CM also
# fixes this path: the same Z2100 no-ink test through cgimagetopdf →
# cgpdftoraster went from 5 altered patch colours to 0 with the key set.
_TIFF_RASTER_OPTIONS: dict[int, dict[str, str]] = {
    1: {
        "ColorSync":        "None",
        "cupsColorSpace":   "0",          # CUPS Gray
        "cupsColorOrder":   "0",
        "ColorModel":       "Gray",
        "cupsCompression":  "None",
        "cupsBitsPerColor": "8",
        "Duplex":           "None",
        "sides":            "one-sided",
        **_AP_NO_CM,
    },
    3: {  # RGB — original _COLOR_MGMT_OFF, confirmed working for ET-8550
        "ColorSync":        "None",
        "cupsColorSpace":   "DeviceRGB",
        "cupsColorOrder":   "0",
        "ColorModel":       "RGB",
        "cupsCompression":  "None",
        "cupsBitsPerColor": "8",
        "Duplex":           "None",
        "sides":            "one-sided",
        **_AP_NO_CM,
    },
    4: {  # CMYK
        "ColorSync":        "None",
        "cupsColorSpace":   "6",          # CUPS CMYK
        "cupsColorOrder":   "0",
        "ColorModel":       "CMYK",
        "cupsCompression":  "None",
        "cupsBitsPerColor": "8",
        "Duplex":           "None",
        "sides":            "one-sided",
        **_AP_NO_CM,
    },
}

# ---------------------------------------------------------------------------
# Kept for reference only — superseded by print_job_ps().
# The TIFF path hardcodes DeviceRGB which breaks CMYK and N-channel targets.
# ---------------------------------------------------------------------------
_COLOR_MGMT_OFF: dict[str, str] = {
    "ColorSync":        "None",
    "cupsColorSpace":   "DeviceRGB",
    "cupsColorOrder":   "0",
    "ColorModel":       "RGB",
    "cupsCompression":  "None",
    "cupsBitsPerColor": "8",
    "Duplex":           "None",
}


# Options for a printer whose dialog picks a paper profile (Canon IJ, Epson:
# ``ppd_color.PAPER_PROFILE_RULES``).  The job carries what a Photoshop print with
# "Photoshop manages colours" carries and nothing more (Basti, 2026-10-08): the
# Apple application-colour-matching key, the medium's paper profile as the
# vendor's print dialog would set it, and one-sided printing.  None of
# ColorSync=None, the cups* raster hints or the vendor's "no colour correction"
# key: Photoshop sends none of them, and measured on the Canon PRO-300 they
# change nothing a printer sees (CNIJIntent2 is ignored in application mode, the
# printer stream is byte-identical) except where they hurt (no paper profile ->
# Canon's own colour processing on photo paper).
_REFERENCE_JOB_OPTIONS: dict[str, str] = {
    "Duplex": "None",
    "sides":  "one-sided",
    **APPLICATION_COLOUR_MATCHING,
}


def job_id_from_lp_output(text: str) -> int | None:
    """The job number in lp's answer, in any language ("request id is Q-12",
    "Anfrage-ID ist Q\u201312 (1 Datei(en))")."""
    import re
    m = re.search(r"[-\u2013\u2010](\d+)(?:\s|$)", text or "")
    return int(m.group(1)) if m else None


def write_tagged_tiff(src: Path, dst: Path, icc: bytes) -> None:
    """Copy *src* (first page) to *dst* with *icc* embedded, pixels and
    resolution untouched."""
    import tifffile
    with tifffile.TiffFile(str(src)) as tif:
        page = tif.pages[0]
        arr = page.asarray()
        res = page.tags.get("XResolution"), page.tags.get("YResolution")
        unit = page.tags.get("ResolutionUnit")
        resolution = None
        if res[0] is not None and res[1] is not None:
            xr, yr = res[0].value, res[1].value
            resolution = (xr[0] / xr[1], yr[0] / yr[1])
        unit_v = unit.value if unit is not None else 2
    tifffile.imwrite(str(dst), arr, photometric="rgb", iccprofile=icc,
                     resolution=resolution, resolutionunit=unit_v)


@dataclass
class PrintConfig:
    printer_name: str
    options: dict[str, str] = _field(default_factory=dict)


class CupsRawPrinter:
    """Submit a profiling target to a CUPS printer via PostScript."""

    #: the job number lp gave the last submission, for the read-back of its ticket
    last_job_id: int | None = None
    #: the paper profile the last job was sent with (reference route), or None
    last_paper_profile: PaperProfile | None = None
    #: the colour-relevant options the last job was sent with, for the read-back
    last_expected: dict[str, str] = {}

    def print_job_ps(
        self,
        tiff_path: Path,
        config: PrintConfig,
        ink_channels: list[str] | None = None,
        on_finish: Callable[[int], None] | None = None,
        orientation: int | None = None,
        page_size_pt: tuple[float, float] | None = None,
        pdf_fallback: bool = False,
    ) -> None:
        """Convert *tiff_path* to PostScript and send to the printer in *config*.

        ink_channels: ordered ink codes for the TIFF channels — required for
        correct DeviceN naming when the target has more than 4 colorants.
        orientation: CUPS orientation-requested (3=portrait, 4=landscape).
        Only used by the TIFF fallback below; the PS path bakes orientation
        into setpagedevice instead, since pstops double-rotates if it sees
        both a landscape PS and orientation-requested=4.
        page_size_pt: physical media size (w_pt, h_pt) — passed to the PS
        setpagedevice line so the PS doc and `lp -o PageSize=...` agree.
        pdf_fallback: when True, a CUPS PostScript rejection retries with an
        exact-size PDF (image placed 1:1 on a MediaBox matching PageSize)
        instead of the raw TIFF — avoiding the ~3% shrink Apple's
        cgimagetopdf applies to full-page charts.  The raw TIFF remains the
        last resort if the PDF submission itself fails.
        Falls back to TIFF automatically if CUPS rejects PostScript.

        A printer whose print dialog picks a paper profile (Canon IJ, Epson)
        gets the Photoshop-equivalent job instead (``_print_job_reference``):
        no PostScript, the chart tagged with that paper profile.
        """
        self.last_job_id = None
        self.last_paper_profile = None
        pp = self._reference_paper_profile(tiff_path, config)
        if pp is not None:
            self.last_paper_profile = pp
            self.last_expected = {**APPLICATION_COLOUR_MATCHING, **pp.keys()}
            self._print_job_reference(tiff_path, config, pp, on_finish, orientation,
                                      page_size_pt, pdf_fallback)
            return
        try:
            vendor = dict(vendor_no_cm_settings_for_queue(config.printer_name))
        except Exception:  # pragma: no cover - defensive
            vendor = {}
        self.last_expected = {**_AP_NO_CM, **vendor}
        try:
            ps_text = PostScriptGenerator().generate(
                tiff_path,
                ink_channels=ink_channels,
                page_size_pt=page_size_pt,
            )
        except Exception as exc:
            log.error("PS generation failed for %s: %s", tiff_path.name, exc)
            if on_finish:
                on_finish(-1)
            return

        fd, ps_str = tempfile.mkstemp(suffix=".ps")
        ps_path = Path(ps_str)
        code, stderr = -1, ""
        try:
            os.close(fd)
            ps_path.write_text(ps_text, encoding="ascii")
            cmd = self._build_lp_command_ps(ps_path, config, orientation)
            log.info("CUPS PS print: %s", " ".join(str(c) for c in cmd))
            code, stderr = self._run_lp_result(cmd)
        finally:
            ps_path.unlink(missing_ok=True)

        if code == 1 and "postscript" in stderr.lower():
            self._cancel_pending_jobs(config.printer_name)
            if pdf_fallback:
                log.warning("PostScript rejected by CUPS — retrying as exact-size PDF")
                self._print_job_pdf(
                    tiff_path, config, ink_channels, on_finish,
                    orientation, page_size_pt,
                )
            else:
                log.warning("PostScript rejected by CUPS — retrying as TIFF")
                self._print_job_tiff(tiff_path, config, on_finish, orientation)
            return

        if on_finish:
            on_finish(code)

    @staticmethod
    def _reference_paper_profile(tiff_path: Path, config: PrintConfig
                                 ) -> PaperProfile | None:
        """The paper profile the vendor's dialog would choose for this job, when
        the queue's PPD is one of ``PAPER_PROFILE_RULES``'s vendors and the chart
        is RGB with that profile readable; else None (the generic path).

        The value comes from the driver's own table, ChromIQ's built-in table or
        what the user's dialog prints taught it (``workflow.printer_memory``);
        ``pp.known`` is False when none of them knows the model, and the Print
        Chart tab asks the user before printing such a job
        (M-PRINT-PAPER-PROFILE-UNKNOWN).

        macOS only: the route answers macOS's rasteriser, which converts tagged
        colour into the job's paper profile. A Linux CUPS with a Canon or Epson
        PPD keeps the beta 14 job (review 2026-10-08)."""
        if sys.platform != "darwin":
            return None
        try:
            from workflow.printer_memory import PaperProfileMemory
            pp = paper_profile_for_queue(config.printer_name, config.options,
                                         learned=PaperProfileMemory())
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("paper-profile lookup failed for %s: %s", config.printer_name, exc)
            return None
        if pp is None:
            return None
        if not pp.icc_path or not Path(pp.icc_path).is_file():
            log.warning("CUPS print: %s names paper profile %s=%s but its file %s is "
                        "missing; generic path used", config.printer_name, pp.option,
                        pp.value, pp.icc_path)
            return None
        try:
            if CupsRawPrinter._tiff_n_channels(tiff_path) != 3:
                return None
        except Exception:
            return None
        return pp

    @staticmethod
    def reference_options(cfg: PrintConfig, pp: PaperProfile) -> dict[str, str]:
        """The job options of the Photoshop-equivalent route (see
        ``_REFERENCE_JOB_OPTIONS``): the tab's own choices, the reference keys and
        the medium's paper profile."""
        return {**cfg.options, **_REFERENCE_JOB_OPTIONS, **pp.keys()}

    def _print_job_reference(
        self,
        tiff_path: Path,
        config: PrintConfig,
        pp: PaperProfile,
        on_finish: Callable[[int], None] | None,
        orientation: int | None,
        page_size_pt: tuple[float, float] | None,
        pdf_fallback: bool,
    ) -> None:
        """Send the chart the way Photoshop sends an image it has colour-managed.

        The chart is tagged with the very profile the job selects
        (``pp.icc_path``).  macOS's rasteriser converts tagged colour to that
        destination, so the conversion is the identity and the chart's own
        numbers reach the driver; untagged, measured on the PRO-300, a job naming
        Matte Photo Paper changed 22 of 24 test patches by up to 116 levels.
        """
        icc = Path(pp.icc_path).read_bytes()
        opts = self.reference_options(config, pp)
        log.info("CUPS print: reference job, %s=%s (%s), chart tagged with %s",
                 pp.option, pp.value, pp.label, pp.icc_path)
        # Beta 16 review: an Epson job whose EPIJ_Size now carries its PageSize
        # (``PrintModule._page_size_for_vendor_size``) goes as the exact-size
        # PDF. macOS fits a TIFF into the PageSize's printable area: measured
        # on ET-8550, SC-P900, R3000 and XP-15000 capture queues, an A4 chart
        # on "A4" came out at 97 % (beta 15, without the PageSize: 100 %), and
        # no lp option (print-scaling, ppi, scaling, natural-scaling,
        # fit-to-page) changes that. The PDF places it 1:1.
        exact = pdf_fallback or (page_size_pt is not None
                                 and bool(opts.get("EPIJ_Size"))
                                 and bool(opts.get("PageSize")))
        suffix = ".pdf" if exact else ".tif"
        fd, tmp_str = tempfile.mkstemp(suffix=suffix)
        tmp = Path(tmp_str)
        code = -1
        try:
            os.close(fd)
            if exact:
                paper = page_size_pt or _name_the_default_page(
                    opts, config.printer_name, _tiff_page_pt(tiff_path))
                tmp.write_bytes(PdfGenerator().generate(
                    tiff_path, page_size_pt=paper, icc_profile=icc))
            else:
                write_tagged_tiff(tiff_path, tmp, icc)
                if orientation is not None:
                    opts["orientation-requested"] = str(orientation)
            cmd = ["lp", "-d", config.printer_name]
            for key, val in opts.items():
                if val:
                    cmd += ["-o", f"{key}={val}"]
            cmd.append(str(tmp))
            log.info("CUPS reference print: %s", " ".join(cmd))
            code, _ = self._run_lp_result(cmd)
        except Exception as exc:
            log.error("reference print failed for %s: %s", tiff_path.name, exc)
            code = -1
        finally:
            tmp.unlink(missing_ok=True)
        if on_finish:
            on_finish(code)

    def _print_job_pdf(
        self,
        tiff_path: Path,
        config: PrintConfig,
        ink_channels: list[str] | None = None,
        on_finish: Callable[[int], None] | None = None,
        orientation: int | None = None,
        page_size_pt: tuple[float, float] | None = None,
    ) -> None:
        """Submit the chart as a self-generated exact-size PDF.

        The PDF embeds the TIFF untagged in its device colour space, placed
        1:1 (centred) on a MediaBox matching *page_size_pt*, so neither the
        host rasteriser nor the driver has a scaling decision left to make —
        content reaching into the hardware margins is clipped, never scaled.
        Falls back to the raw-TIFF path if PDF generation or submission fails.
        """
        opts = dict(config.options)
        paper = page_size_pt or _name_the_default_page(
            opts, config.printer_name, _tiff_page_pt(tiff_path))
        config = PrintConfig(printer_name=config.printer_name, options=opts)
        try:
            pdf_bytes = PdfGenerator().generate(
                tiff_path,
                ink_channels=ink_channels,
                page_size_pt=paper,
            )
        except Exception as exc:
            log.error("PDF generation failed for %s — falling back to TIFF: %s",
                      tiff_path.name, exc)
            self._print_job_tiff(tiff_path, config, on_finish, orientation)
            return

        fd, pdf_str = tempfile.mkstemp(suffix=".pdf")
        pdf_path = Path(pdf_str)
        code = -1
        try:
            os.close(fd)
            pdf_path.write_bytes(pdf_bytes)
            cmd = self._build_lp_command_pdf(pdf_path, config)
            log.info("CUPS PDF print (exact-size fallback): %s",
                     " ".join(str(c) for c in cmd))
            code, _ = self._run_lp_result(cmd)
        finally:
            pdf_path.unlink(missing_ok=True)

        if code != 0:
            log.warning("PDF submission failed (code %d) — retrying as TIFF", code)
            self._cancel_pending_jobs(config.printer_name)
            self._print_job_tiff(tiff_path, config, on_finish, orientation)
            return

        if on_finish:
            on_finish(code)

    def _print_job_tiff(
        self,
        tiff_path: Path,
        config: PrintConfig,
        on_finish: Callable[[int], None] | None = None,
        orientation: int | None = None,
    ) -> None:
        """Submit the TIFF directly with colour-space-aware CUPS raster options.

        This mirrors the original _COLOR_MGMT_OFF approach but picks the correct
        cupsColorSpace / ColorModel for 1-, 3-, and 4-channel TIFFs so CUPS does
        not apply ColorSync or ICC transforms before handing off to the driver.
        N-channel (> 4) falls back to RGB options — those targets are typically
        only used on PostScript-capable RIPs that accept the PS path above.
        """
        n_ch = self._tiff_n_channels(tiff_path)
        cmd = self._build_lp_command_tiff(tiff_path, config, n_ch, orientation)
        log.info("CUPS TIFF print (fallback, %d-ch): %s", n_ch, " ".join(str(c) for c in cmd))
        self._run_lp(cmd, on_finish)

    # Superseded by print_job_ps() — kept temporarily for reference.
    def print_job(
        self,
        tiff_path: Path,
        config: PrintConfig,
        on_finish: Callable[[int], None] | None = None,
    ) -> None:
        """Send *tiff_path* to the printer named in *config* via lp."""
        cmd = self._build_lp_command(tiff_path, config)
        log.info("CUPS print: %s", " ".join(str(c) for c in cmd))
        self._run_lp(cmd, on_finish)

    def _run_lp_result(self, cmd: list[str]) -> tuple[int, str]:
        """Run lp, return (returncode, stderr_text)."""
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30, stdin=subprocess.DEVNULL)
            stderr = decode_output(result.stderr, what="lp")
            if result.returncode != 0:
                log.error("lp failed (code %d): %s", result.returncode, stderr)
            else:
                out = decode_output(result.stdout, what="lp").strip()
                log.info("lp submitted (stdout: %s)", out)
                self.last_job_id = job_id_from_lp_output(out)
            return result.returncode, stderr
        except subprocess.TimeoutExpired:
            log.error("lp timed out")
            return -1, ""
        except Exception as exc:
            log.error("lp exception: %s", exc)
            return -1, ""

    def _run_lp(
        self,
        cmd: list[str],
        on_finish: Callable[[int], None] | None,
    ) -> None:
        code, _ = self._run_lp_result(cmd)
        if on_finish:
            on_finish(code)

    @staticmethod
    def _cancel_pending_jobs(printer_name: str) -> None:
        if not CUPS_AVAILABLE:
            return
        try:
            conn = _cups_mod.Connection()
            jobs = conn.getJobs(which_jobs="not-completed", my_jobs=False)
            for job_id, attrs in jobs.items():
                if printer_name not in attrs.get("job-printer-uri", ""):
                    continue
                try:
                    conn.cancelJob(job_id)
                    log.info("Cancelled queued job %d for %s before TIFF retry", job_id, printer_name)
                except Exception:
                    pass
        except Exception as exc:
            log.warning("_cancel_pending_jobs error: %s", exc)

    @staticmethod
    def _apply_vendor_no_cm(opts: dict[str, str], printer_name: str) -> None:
        """Force the driver's own "no colour adjustment" options into *opts*.

        ``ColorSync=None`` only stops CUPS' *own* ColorSync transform; a driver
        whose colour engine lives below that (e.g. Canon, whose PPD exposes
        ``CNIJIntent2=1001`` / "No Color Correction") keeps re-profiling the
        chart unless its key is set explicitly.  Mirrors the backstop the native
        macOS print path applies.  All pairs are applied — HP colour lasers
        split the choice over per-object-type options (HPTextRGB /
        HPGraphicsRGB / HPPhotoRGB).  Best-effort: silently does nothing if the
        PPD isn't found or exposes no such option (e.g. Epson, already handled
        by the raster options above).
        """
        try:
            pairs = vendor_no_cm_settings_for_queue(printer_name)
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("vendor no-CM lookup failed for %s: %s", printer_name, exc)
            return
        for key, val in pairs:
            opts[key] = val
            log.info("CUPS print: driver no-colour option %s=%s", key, val)
        # Beta 16: an Epson without paper profiles (PictureMate) cannot switch
        # its colour processing off; its dialog sets Mode, quality and colour
        # mode for the medium, and the chart must print in that same state.
        if sys.platform == "darwin":
            try:
                from workflow.ppd_color import (dialog_keys_without_paper_profile,
                                                ppd_path_for_queue)
                from core.text_io import read_text
                ppd = ppd_path_for_queue(printer_name)
                keys = dialog_keys_without_paper_profile(
                    read_text(Path(ppd), lenient=True), opts) if ppd else {}
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("dialog keys for %s: %s", printer_name, exc)
                keys = {}
            for key, val in keys.items():
                opts[key] = val
                log.info("CUPS print: the print dialog's own %s=%s for this paper", key, val)

    @staticmethod
    def _build_lp_command_ps(
        ps_path: Path,
        cfg: PrintConfig,
        orientation: int | None = None,
    ) -> list[str]:
        # `orientation` is intentionally ignored on the PS path: the page
        # geometry is baked into setpagedevice PageSize by PostScriptGenerator.
        # Apple's pstops filter rotates a second time if it sees both a
        # landscape PS and orientation-requested=4 — clipping the chart or
        # silently dropping the job. The param stays in the signature for
        # symmetry with _build_lp_command_tiff, which still needs it.
        del orientation
        merged = {**cfg.options, **_PS_JOB_OPTIONS}
        CupsRawPrinter._apply_vendor_no_cm(merged, cfg.printer_name)
        cmd = ["lp", "-d", cfg.printer_name]
        for key, val in merged.items():
            if val:
                cmd += ["-o", f"{key}={val}"]
        cmd.append(str(ps_path))
        return cmd

    @staticmethod
    def _build_lp_command_pdf(pdf_path: Path, cfg: PrintConfig) -> list[str]:
        # No orientation-requested and no ColorSync=None: geometry is baked
        # into the PDF MediaBox (rotated to the chart's aspect, like the PS
        # setpagedevice), and the image is untagged device colour, which the
        # PDF rasteriser passes through bit-exact without any job option.
        merged = {**cfg.options, **_PDF_JOB_OPTIONS}
        CupsRawPrinter._apply_vendor_no_cm(merged, cfg.printer_name)
        cmd = ["lp", "-d", cfg.printer_name]
        for key, val in merged.items():
            if val:
                cmd += ["-o", f"{key}={val}"]
        cmd.append(str(pdf_path))
        return cmd

    @staticmethod
    def _tiff_n_channels(tiff_path: Path) -> int:
        import tifffile
        with tifffile.TiffFile(str(tiff_path)) as tif:
            shape = tif.pages[0].shape
        return shape[2] if len(shape) == 3 else 1

    @staticmethod
    def _build_lp_command_tiff(
        tiff_path: Path,
        cfg: PrintConfig,
        n_ch: int,
        orientation: int | None = None,
    ) -> list[str]:
        opts = _TIFF_RASTER_OPTIONS.get(n_ch, _TIFF_RASTER_OPTIONS[3])
        merged = {**cfg.options, **opts}
        if orientation is not None:
            merged["orientation-requested"] = str(orientation)
        CupsRawPrinter._apply_vendor_no_cm(merged, cfg.printer_name)
        cmd = ["lp", "-d", cfg.printer_name]
        for key, val in merged.items():
            if val:
                cmd += ["-o", f"{key}={val}"]
        cmd.append(str(tiff_path))
        return cmd

    @staticmethod
    def _build_lp_command(tiff_path: Path, cfg: PrintConfig) -> list[str]:
        merged = {**cfg.options, **_COLOR_MGMT_OFF}
        cmd = ["lp", "-d", cfg.printer_name]
        for key, val in merged.items():
            if val:
                cmd += ["-o", f"{key}={val}"]
        cmd.append(str(tiff_path))
        return cmd

    @staticmethod
    def is_printer_reachable(printer_name: str) -> bool:
        """Return True if the printer is idle or printing (state 3 or 4)."""
        if not CUPS_AVAILABLE:
            return True  # fail open on platforms without CUPS
        try:
            attrs = _cups_mod.Connection().getPrinters().get(printer_name, {})
            return attrs.get("printer-state", 5) in (3, 4)
        except Exception:
            return True  # fail open — let lp surface the real error
