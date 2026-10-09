"""Parse a CUPS/PPD file for the driver's own "no colour management" option.

Pure text parsing — no PyObjC, PrintCore, or CUPS bindings — so it is safe to
import on any platform and from either print path (the native macOS dialog in
``native_print_macos`` and the ``lp`` path in ``cups_printer``).

The job: find the option/value a driver exposes to mean "do not colour-manage
this job" so ChromIQ can lock it and stop the driver re-profiling a profiling
target.  Examples: Epson ``EPIJ_CMat=3`` ("No Color Adjustment"), Canon
``CNIJIntent2=1001`` ("No Color Correction").
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass
import re
from core.text_io import read_text
from core.logger import get_logger

log = get_logger(__name__)

# A PPD UI option is specifically a "colour-management" option if its label
# looks like one (used to qualify a bare "Off"/"None" value):
_PPD_CM_OPT_RES = (
    re.compile(r"colou?r.*(match|manag)", re.I),
    re.compile(r"(match|manag).*colou?r", re.I),
    re.compile(r"colou?r\s*(setting|option|mode|correction|control|process|transform)", re.I),
    # HP colour lasers hang the rendering choice off "RGB Color" with values
    # sRGB / Vivid / Photo / Adobe RGB / None — "None" is the raw device mode.
    # Anchored so a bare "Color" or watermark "Text Color" never qualifies.
    re.compile(r"^rgb\s+colou?r$", re.I),
)
# Value labels that unambiguously mean "do not colour-manage":
_PPD_NO_CM_VALUE_RES = (
    re.compile(r"no\s+colou?r\s+adjustment", re.I),
    re.compile(r"application[\s-]*(managed|controlled)", re.I),
    re.compile(r"(managed|controlled)\s+by\s+application", re.I),
    re.compile(r"no\s+colou?r\s+(management|matching|correction)", re.I),
    re.compile(r"colou?r\s+(management|matching|correction)\s+off", re.I),
    re.compile(r"uncalibrated", re.I),
)
# Value labels that count only when the option is clearly a CM option:
_PPD_GENERIC_OFF_RES = (
    re.compile(r"^\s*off\s*$", re.I),
    re.compile(r"^\s*none\s*$", re.I),
    # HP DesignJets label the choice just "Application" (vs "Printer") on a
    # "Color Management" option — its PS invocation sets RGBColorManagement
    # to None, i.e. the driver hands colour over to the application.
    re.compile(r"^\s*application(\s+matching)?\s*$", re.I),
    # Samsung colour lasers offer Standard/Vivid/"Device" on "RGB Color" —
    # the Device invocation is `userdict /RGBColorMode (DEVICE) put`, i.e.
    # raw device RGB without rendering treatment.
    re.compile(r"^\s*device\s*$", re.I),
)

_PPD_OPENUI_RE = re.compile(r'^\*OpenUI\s+\*([A-Za-z0-9_]+)\s*/([^:]*):\s*PickOne', re.I)


def parse_ppd_options(text: str):
    """Yield ``(key, ui_label, [(value, value_label), ...])`` for each PPD
    ``*OpenUI ... PickOne`` block."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        m = _PPD_OPENUI_RE.match(lines[i])
        if not m:
            i += 1
            continue
        key, ui_label = m.group(1), m.group(2).strip()
        values: list[tuple[str, str]] = []
        j = i + 1
        val_re = re.compile(rf'^\*{re.escape(key)}\s+([^\s/]+)\s*/([^:]*):', )
        while j < len(lines) and not lines[j].startswith("*CloseUI"):
            vm = val_re.match(lines[j])
            if vm:
                values.append((vm.group(1), vm.group(2).strip()))
            j += 1
        yield key, ui_label, values
        i = j + 1  # advance past this block — without this the loop never ends


def vendor_no_cm_settings(ppd_path: str) -> list[tuple[str, str]]:
    """Scan a PPD for **every** "no colour adjustment" option/value it exposes.

    Returns ``[(option_key, value), ...]`` ordered best-match first (an explicit
    "No Color Adjustment"/"Application Managed" value ranks above a bare
    "Off"/"None" on a colour-management option), or ``[]`` if nothing matches.

    All pairs must be applied together: HP colour lasers split the rendering
    choice into *three* sibling options all labelled "RGB Color" (HPTextRGB /
    HPGraphicsRGB / HPPhotoRGB) — setting only one leaves the other object
    types colour-managed (2026-06 survey of the Apple vendor driver bundles).
    """
    try:
        text = read_text(pathlib.Path(ppd_path), lenient=True)
    except OSError:
        return []
    hits: list[tuple[int, int, str, str]] = []
    for order, (key, ui_label, values) in enumerate(parse_ppd_options(text)):
        best: tuple[int, str] | None = None  # best value for *this* option
        is_cm_opt = any(r.search(ui_label) for r in _PPD_CM_OPT_RES)
        for val, vlabel in values:
            prio: int | None = None
            if any(r.search(vlabel) for r in _PPD_NO_CM_VALUE_RES):
                # An explicit "no colour management" *value* (e.g. Canon's
                # "No Color Correction") is unambiguous on its own, so accept
                # it regardless of the option's own name.  Canon hangs this off
                # an option labelled "Rendering Intent" (CNIJIntent2=1001), not
                # one with "colour" in the name, so an option-label gate here
                # would silently miss it.
                prio = 0
            elif is_cm_opt and any(r.match(vlabel) for r in _PPD_GENERIC_OFF_RES):
                # A bare "Off"/"None" is only a no-CM signal when the option
                # itself clearly *is* a colour-management option, so we don't
                # mistake e.g. "Duplex: Off" for colour management.
                prio = 1
            if prio is not None and (best is None or prio < best[0]):
                best = (prio, val)
        if best is not None:
            hits.append((best[0], order, key, best[1]))
    hits.sort()
    return [(key, val) for _, _, key, val in hits]


def vendor_no_cm_setting(ppd_path: str) -> tuple[str, str] | None:
    """The single best no-CM option/value of *ppd_path* (see
    ``vendor_no_cm_settings``), or ``None`` if it exposes none."""
    pairs = vendor_no_cm_settings(ppd_path)
    return pairs[0] if pairs else None


def vendor_no_cm_settings_for_queue(queue_name: str) -> list[tuple[str, str]]:
    """Locate *queue_name*'s installed PPD and return its no-CM options.

    Mirrors ``PrintModule._find_ppd_path`` so the ``lp`` path can apply the same
    backstop the native dialog uses, without importing the macOS print module.
    """
    for base in ("/etc/cups/ppd", "/private/etc/cups/ppd"):
        p = pathlib.Path(f"{base}/{queue_name}.ppd")
        if p.exists():
            return vendor_no_cm_settings(str(p))
    return []



# ---------------------------------------------------------------------------
# The printer state a Photoshop print gets ("Photoshop manages colours")
# ---------------------------------------------------------------------------
#
# Basti, 2026-10-08: a profiling chart must print in EXACTLY the printer state his
# later image prints get, and those come from Photoshop with "Photoshop manages
# colours" -- application colour matching.  What decides that state was measured
# on macOS 27.0.1 with capture queues (report folders 2026-10-08_print_fix and
# 2026-10-08_vendor_tests):
#
# * Photoshop's own contribution to the job ticket is one key,
#   AP_ColorMatchingMode=AP_ApplicationColorMatching.  Everything else on the
#   ticket is written by the driver's print-dialog extension (PDE) for the medium
#   chosen in the dialog.
# * The Canon IJ PDE writes, besides the medium, the paper profile it belongs to
#   (CNIJProfileID); the Epson PDE writes EPIJProfileSpec.  macOS's rasteriser
#   picks the matching *cupsICCProfile through the PPD's *cupsICCQualifierN line,
#   and the Canon filter (Raster2CanonIJ2S) tells the printer
#   `printcolormode_intent=none` only when, in application mode, that id names a
#   paper profile; otherwise `pro` (Canon's own colour processing).
# * ``lp`` has no PDE, so it must send the paper-profile key itself.
#
# WHERE THE MEDIUM -> PAPER PROFILE TABLE COMES FROM (beta 15).  Until the vendor
# tests the medium was matched to a profile by comparing NAMES.  That fitted the
# PRO-300/310 and ET-8550/18100 only: the PRO-1000/1100/200S profiles carry
# "_500_"/"_510_"/"_S1MkII_", the PRO-100 uses codes (MP2, LU3), and the Epson
# P/R models name theirs "Epson SC-P900_700 ...", "SPR3000 ...".  Measured on the
# real dialogs the name rule was right 17 times in 69.  The drivers ship the very
# tables their dialogs read, so ChromIQ reads those, in this order:
#
# 1. the installed driver's own table (Canon: the model's media database,
#    ``<output_icc>`` per medium; Epson: PDEData.dat, ``*EPIJConditionValue
#    EPIJProfileSpec``);
# 2. the tables shipped with ChromIQ (``data/printer_paper_profiles.json``),
#    measured from the drivers and their dialogs for the models tested
#    (``scripts/printer_paper_tables.py`` writes them);
# 3. what the user's own prints through the macOS dialog taught it
#    (``workflow.printer_memory``);
# 4. otherwise the model is UNKNOWN: the paper profile is not guessed, and the
#    Print Chart tab says so before printing (M-PRINT-PAPER-PROFILE-UNKNOWN).


@dataclass(frozen=True)
class PaperProfileRule:
    """How one vendor's print dialog writes the paper profile for a medium."""

    vendor: str
    #: PPD option that names the medium the user chose
    media_option: str
    #: PPD option that selects the paper profile (the PPD's *cupsICCQualifierN)
    profile_option: str
    #: PPD option for the print quality (a learned entry is per quality)
    quality_option: str = ""
    #: PPD option for the paper source, which the dialog sets for the medium
    #: (beta 16: the Canon dialog moves Baryta and fine-art papers to Manual Feed)
    source_option: str = ""
    #: True when the vendor's filter switches its own colour processing off,
    #: in application colour matching, only for a job naming a paper profile
    #: other than the PPD's default (Canon: `none` vs `pro`)
    own_colour_off_needs_paper_profile: bool = False
    #: keys EVERY dialog of this vendor tested writes in application colour
    #: matching whatever the model and medium; the per-model keys (built-in
    #: table, learned, or the dialog type) are added to them
    dialog_keys: tuple[tuple[str, str], ...] = ()
    #: which installed table to read: "canon-db" or "epson-pde"
    driver_table: str = ""
    evidence: str = ""


PAPER_PROFILE_RULES: tuple[PaperProfileRule, ...] = (
    PaperProfileRule(
        vendor="Canon IJ",
        media_option="CNIJMediaType",
        profile_option="CNIJProfileID",
        quality_option="CNIJPrintQuality",
        source_option="CNIJMediaSupply",
        own_colour_off_needs_paper_profile=True,
        driver_table="canon-db",
        # The PDE also writes CNIJColorMatchingMode=1 and CNIJHalfToneRadio=0;
        # neither changes one byte of the printer stream (measured), so lp does
        # not send them.
        evidence=(
            "Canon PRO-300 driver 30.10.1, macOS 27.0.1, 2026-10-08: in application "
            "colour matching the PDE wrote the medium's CNIJProfileID; "
            "Raster2CanonIJ2S sends printcolormode_intent=none for application mode "
            "with a paper profile, pro otherwise, and ignores CNIJIntent2 there. "
            "Vendor tests 2026-10-08: the model's media database names the profile "
            "the dialog wrote on PRO-300/310/200S/1000/1100 (PRO-100: measured table)"),
    ),
    PaperProfileRule(
        vendor="Epson",
        media_option="EPIJ_Medi",
        profile_option="EPIJProfileSpec",
        quality_option="EPIJ_Qual",
        driver_table="epson-pde",
        dialog_keys=(("EPIJ_CMat", "3"), ("EPIJ_OSColMat", "2"), ("EPIJ_OSCMProf", "1"),
                     ("EPIJ_HdofClSp", "0")),
        evidence=(
            "Epson ET-8550 driver 13.45, macOS 27.0.1, 2026-10-08: in application "
            "colour matching the PDE wrote the medium's EPIJProfileSpec and "
            "EPIJ_CMat=3, EPIJ_OSColMat=2, EPIJ_OSCMProf=1, EPIJ_HdofClSp=0; vendor "
            "tests 2026-10-08: the same on ET-18100, SC-P900/P700/P5300/P800 and "
            "Stylus Photo R3000/R2000, EPIJ_Mode and EPIJ_CCor by dialog type"),
    ),
)

#: Epson dialog keys that depend on the dialog type (PDEData.dat ``*EPIJUIType``),
#: measured on the real dialogs (vendor tests 2026-10-08):
#: * "NewUI_J" (SC-P900/P700/P5300) leaves EPIJ_Mode at 0; every other type
#:   writes 3 (Custom);
#: * EPIJ_CCor stays at the PPD's default (4 on SC-P900/P700/P5300/P800 and
#:   R3000, 3 on R2000, 12 on ET-18100) except on the ET-8550, whose dialog
#:   writes 3 on photo media and keeps 12 on plain paper (its built-in table
#:   carries that per medium).
EPSON_MODE_BY_UI = {"NewUI_J": None}
EPSON_MODE_DEFAULT = "3"


@dataclass(frozen=True)
class PaperProfile:
    """The paper profile a vendor's dialog would select for one medium."""

    rule: PaperProfileRule
    media_value: str
    media_label: str
    option: str
    #: the profile option's value (None only when the PPD has no default either)
    value: str | None
    label: str
    icc_path: str | None
    is_default: bool
    #: where the value comes from: "job" (read back from a job), "driver" (the
    #: installed driver's table), "built-in" (shipped table), "learned" (the
    #: user's own dialog prints), or "unknown" (none of these: the PPD default,
    #: which the Print Chart tab must not use without telling the user)
    source: str = "unknown"
    #: the printer model, as the PPD's *ModelName names it
    model: str = ""
    #: the keys the vendor's dialog writes for this medium besides the profile,
    #: which the lp route sends itself (only values the PPD allows)
    dialog_keys: tuple[tuple[str, str], ...] = ()

    @property
    def known(self) -> bool:
        """True when the value is the dialog's own, not a fallback."""
        return self.source in ("job", "driver", "built-in", "learned")

    def keys(self) -> dict[str, str]:
        """Every key the lp route sends for this paper profile."""
        out = dict(self.dialog_keys)
        if self.value is not None:
            out[self.option] = self.value
        return out


def _ppd_default(text: str, key: str) -> str | None:
    m = re.search(rf"^\*Default{re.escape(key)}:\s*(\S+)", text, re.M)
    return m.group(1) if m else None


def _qualifier_index(text: str, option: str) -> int | None:
    m = re.search(rf"^\*cupsICCQualifier([23]):\s*{re.escape(option)}\s*$", text, re.M)
    return int(m.group(1)) if m else None


def _icc_profiles(text: str) -> list[tuple[list[str], str, str]]:
    """[(qualifiers, label, path)] from the PPD's *cupsICCProfile lines."""
    out = []
    for m in re.finditer(r'^\*cupsICCProfile\s+([^/\s]*)/([^:]*):\s*"([^"]+)"', text, re.M):
        out.append((m.group(1).split("."), m.group(2).strip(), m.group(3)))
    return out


def ppd_model(ppd_text: str) -> str:
    """The printer model as the PPD names it (``*ModelName``), or ""."""
    m = re.search(r'^\*ModelName:\s*"([^"]*)"', ppd_text, re.M)
    return m.group(1).strip() if m else ""


# ---- 1. the installed driver's own tables -----------------------------------------

#: Where macOS printer drivers live.  ``CHROMIQ_PRINTER_DRIVER_ROOT`` points the
#: readers at a copy (the tests' fixtures in tests/data/printer_drivers).
DRIVER_ROOT_ENV = "CHROMIQ_PRINTER_DRIVER_ROOT"
MAC_DRIVER_ROOT = "/Library/Printers"


def driver_root() -> pathlib.Path:
    import os
    return pathlib.Path(os.environ.get(DRIVER_ROOT_ENV, "").strip() or MAC_DRIVER_ROOT)


def _driver_path(path: str) -> pathlib.Path:
    """*path* (a /Library/Printers path a PPD names) under ``driver_root()``."""
    if path.startswith(MAC_DRIVER_ROOT + "/"):
        return driver_root() / path[len(MAC_DRIVER_ROOT) + 1:]
    return pathlib.Path(path)


def canon_media_database(ppd_text: str) -> pathlib.Path | None:
    """The Canon IJ model's media database folder, as its PPD names it
    (``*CNIJNameTblPath``), or the name the driver gives it."""
    m = re.search(r'^\*CNIJNameTblPath:\s*"([^"]+)"', ppd_text, re.M)
    if m:
        return _driver_path(m.group(1))
    mm = re.search(r'^\*ModelName:\s*"Canon (\S+) series"', ppd_text, re.M)
    if not mm:
        return None
    return (driver_root() / "Canon/BJPrinter/Resources/Database"
            / f"CIJ{mm.group(1).replace('-', '')}series.db" / "Contents" / "Resources")


@dataclass(frozen=True)
class CanonMedium:
    """What a Canon IJ model's media database says about one medium (beta 16).

    *icc*: the output ICC (the PPD's CNIJProfileID label) the dialog selects;
    *qualities*: the CNIJPrintQuality values the dialog offers for it, best
    first; *dialog_quality*: the one it picks when the user leaves the quality
    alone; *bins*: the paper sources (Canon input-bin ids) it allows, and
    *bin_default*: the one the dialog switches to when the current source is
    not allowed (empty for a database that does not say)."""

    icc: str
    qualities: tuple[str, ...]
    dialog_quality: str | None
    bins: tuple[str, ...] = ()
    bin_default: str = ""
    #: {CNIJPrintQuality: output ICC} where the database names one per quality
    #: (the binary tables do: PRO-100 Luster is LU1 at Fine, LU3 at Normal)
    icc_by_quality: tuple[tuple[str, str], ...] = ()
    #: {CNIJPrintQuality: the dialog's Resolution option, "600x600dpi"} (beta 16:
    #: the Canon dialog sets the PPD's Resolution for the paper and quality,
    #: PRO-10S 600 or 1200 dpi, imagePROGRAF 300 or 600 dpi)
    resolution_by_quality: tuple[tuple[str, str], ...] = ()

    def resolution_for(self, quality: str | None) -> str | None:
        return dict(self.resolution_by_quality).get(quality or self.dialog_quality or "")

    def icc_for(self, quality: str | None) -> str:
        """The output ICC the dialog selects at *quality* (its own quality
        when None or not offered)."""
        return dict(self.icc_by_quality).get(quality or "", self.icc)


def _q_from_type(t: str) -> str | None:
    """CNIJPrintQuality for a media database quality type: ``(N - 1) * 5``."""
    return str((int(t) - 1) * 5) if t.isdigit() and 1 <= int(t) <= 5 else None


def canon_media(ppd_text: str) -> dict[str, CanonMedium]:
    """{medium value: CanonMedium} from the Canon IJ model's media database:
    XML (``<uuid>.hmi`` per medium, drivers 30.x) or binary (``cnb_*.tbl``,
    the 16.9x drivers of the PRO-100, PRO-10S, iP8700 and iX6800).  {} when
    the driver has no readable database."""
    db = canon_media_database(ppd_text)
    if db is None or not db.is_dir():
        return {}
    xml = dict(_canon_media_hmi(ppd_text, db))
    if xml:
        return xml
    try:
        return _canon_media_tbl(ppd_text, db)
    except (OSError, ValueError, IndexError):  # a damaged table: nothing known
        return {}


def _canon_media_hmi(ppd_text: str, db: pathlib.Path):
    roll = bool(re.search(r"^\*OpenUI \*CNIJFitRollPaperWidth/", ppd_text, re.M))
    for mv, uuid in re.findall(
            r'^\*CNIJMediaTypeIVEC\s+(\S+):\s*"custom-media-type-canon-([0-9A-Fa-f-]+)"',
            ppd_text, re.M):
        try:
            x = read_text(db / f"{uuid}.hmi", lenient=True)
        except OSError:
            continue
        cm = re.search(r'<printcolormode type="color">(.*?)</printcolormode>', x, re.S)
        body = cm.group(1) if cm else x
        by_q = dict(re.findall(r'<printquality_rgb type="(\d+)"[^>]*>.*?<output_icc>'
                               r'<!\[CDATA\[([^\]]+)\]\]>', body, re.S))
        if not by_q:
            continue
        dq = re.search(r'<availableprintquality_rgb default="(\d+)">([^<]*)<', body)
        icc = (by_q.get(dq.group(1)) if dq else None) or next(iter(by_q.values()))
        # The dialog picks the quality marked "normal" (the Standard position of
        # its quality control) and, where a medium has none, the default.  The
        # imagePROGRAF dialog (a roll-paper model) picks the database's default
        # instead: beta 16, PRO-2100/2600/4100, 16 media measured.
        types = re.findall(r'<printquality_rgb type="(\d+)"\s+threeposition="(\w+)"', body)
        normal = None if roll else next((t for t, pos in types if pos == "normal"), None)
        pick = _q_from_type(normal or (dq.group(1) if dq else ""))
        allowed = [t.strip() for t in (dq.group(2) if dq else "").split(",") if t.strip()]
        if not allowed:
            allowed = [t for t, _pos in types]
        qualities = tuple(q for q in sorted({_q_from_type(t) for t in allowed} - {None},
                                            key=int))
        ib = re.search(r'<availableinputbinid default="([^"]*)">([^<]*)<', x)
        bins = tuple(b.strip() for b in (ib.group(2) if ib else "").split(",") if b.strip())
        by_cnij = tuple((q, v.strip()) for t, v in by_q.items()
                        if (q := _q_from_type(t)) is not None)
        res = tuple((q, f"{r}x{r}dpi") for t, r in re.findall(
            r'<printquality_rgb type="(\d+)"[^>]*>.*?<availableresolution default="(\d+)"',
            body, re.S) if (q := _q_from_type(t)) is not None)
        yield mv, CanonMedium(icc=icc.strip(), qualities=qualities, dialog_quality=pick,
                              bins=bins, bin_default=ib.group(1) if ib else "",
                              icc_by_quality=by_cnij, resolution_by_quality=res)


#: the binary table's quality byte for CNIJPrintQuality 0/5/10/15/20
_TBL_Q0 = 0x20


def _canon_media_tbl(ppd_text: str, db: pathlib.Path) -> dict[str, CanonMedium]:
    """The binary media database of the 16.9x drivers (``cnb_NNNN.tbl``).

    Decoded 2026-10-09 (report folder 2026-10-09_vendor_tests2): a directory of
    tables at 0x300 (``count``, then ``(length, id, offset)``).  Table 2002 lists
    every print mode the driver has, one 28-byte entry per mode, keyed by
    ``(quality byte, borderless 0/0x40, cartridge, medium)``; table 2004 holds
    the output profile of each mode that has one, 128-byte records with the same
    key followed by the profile name.  The quality byte is
    ``0x20 + CNIJPrintQuality``.  With the PPD's default cartridge and bordered
    printing this reproduces all 29 paper profiles and qualities the PRO-100's
    dialog wrote (vendor tests 2026-10-08); a medium the database has modes for
    but no profile record gets the PPD's default profile, as the dialog does.
    The dialog's quality is Normal (10) where the medium offers it, else the
    nearest one it offers."""
    import struct
    tbl = next(iter(sorted(db.glob("cnb_*.tbl"))), None)
    if tbl is None:
        return {}
    d = tbl.read_bytes()
    n = struct.unpack_from("<I", d, 0x300)[0]
    if not 0 < n < 64:
        raise ValueError("not a Canon media table")
    tables = {}
    for i in range(n):
        _ln, tid, off = struct.unpack_from("<III", d, 0x304 + 12 * i)
        tables[tid] = off
    if 2002 not in tables or 2004 not in tables:
        raise ValueError("Canon media table without print modes or profiles")
    cart = int(_ppd_default(ppd_text, "CNIJCartridge") or "0")

    modes: dict[int, set[str]] = {}
    o = tables[2002]
    size, _a, _b, _c, count = struct.unpack_from("<IIIII", d, o)
    # a 20-byte header, then *count* entries of one size (28 bytes on the
    # PRO-100, PRO-10S and iP8700, 20 on the iX6800), the key 4 bytes in
    stride = (size - 20) // count if count else 0
    for i in range(count):
        k = o + 24 + stride * i
        if stride < 12 or k + 8 > o + size or k + 8 > len(d):
            break
        qb, border, flag, mv, _z = struct.unpack_from("<BBHHH", d, k)
        if border == 0 and flag == cart and _TBL_Q0 <= qb <= _TBL_Q0 + 20 \
                and (qb - _TBL_Q0) % 5 == 0:
            modes.setdefault(mv, set()).add(str(qb - _TBL_Q0))

    icc: dict[tuple[int, str], str] = {}
    o = tables[2004]
    end = o + struct.unpack_from("<I", d, o)[0]
    for m in re.finditer(rb"Canon [^\0]{2,60}\0", d[o:end]):
        k = o + m.start() - 8
        qb, border, flag, mv, _z = struct.unpack_from("<BBHHH", d, k)
        if border == 0 and flag == cart and _TBL_Q0 <= qb <= _TBL_Q0 + 20:
            name = d[k + 8:k + 0x48].split(b"\0")[0].decode("latin-1").strip()
            icc.setdefault((mv, str(qb - _TBL_Q0)), name + ".icc")

    # table 2001: the print-mode commands of each mode, 136-byte entries; its
    # ESC ( d gives the resolution (50 of 50 PRO-10S/iP8700/iX6800 papers)
    resolution: dict[tuple[int, str], str] = {}
    if 2001 in tables:
        o = tables[2001]
        size, _a, _b, count = struct.unpack_from("<IIII", d, o)
        stride = round((size - 16) / count) if count else 0
        for i in range(count if stride >= 16 else 0):
            k = o + 20 + stride * i
            if k + stride > len(d):
                break
            qb, border, flag, mv, _z = struct.unpack_from("<BBHHH", d, k)
            m = re.search(rb"\x1b\(d\x04\x00(....)", d[k + 8:k + stride], re.S)
            if m and border == 0 and flag == cart and _TBL_Q0 <= qb <= _TBL_Q0 + 20:
                h, v = struct.unpack(">HH", m.group(1))
                resolution[(mv, str(qb - _TBL_Q0))] = f"{h}x{v}dpi"

    values = {key: dict(vals) for key, _l, vals in parse_ppd_options(ppd_text)}
    default_icc = values.get("CNIJProfileID", {}).get(
        _ppd_default(ppd_text, "CNIJProfileID") or "", "")
    out: dict[str, CanonMedium] = {}
    for mv in values.get("CNIJMediaType", {}):
        if not mv.isdigit() or int(mv) not in modes:
            continue
        qs = tuple(sorted(modes[int(mv)], key=int))
        pick = "10" if "10" in qs else min(qs, key=lambda q: (abs(int(q) - 10), int(q)))
        out[mv] = CanonMedium(icc=icc.get((int(mv), pick), default_icc), qualities=qs,
                              dialog_quality=pick,
                              icc_by_quality=tuple((q, icc.get((int(mv), q), default_icc))
                                                   for q in qs),
                              resolution_by_quality=tuple(
                                  (q, resolution[(int(mv), q)]) for q in qs
                                  if (int(mv), q) in resolution))
    return out


def canon_driver_table(ppd_text: str) -> dict[str, str]:
    """{medium value: output ICC file name} from the Canon IJ model's media
    database (``canon_media``).  That is the profile the dialog writes for the
    medium: vendor tests 2026-10-08 reproduced every id the
    PRO-300/310/200S/1000/1100 dialogs wrote (XML database), and beta 16 every
    one the PRO-100 dialog wrote (binary database).  The profile does not depend
    on the print quality on the XML models (0 of 174 media); on the binary ones
    it is the profile of the dialog's quality.  {} when the driver has no
    readable database."""
    return {mv: m.icc for mv, m in canon_media(ppd_text).items() if m.icc}


def canon_driver_qualities(ppd_text: str) -> dict[str, str]:
    """{medium value: CNIJPrintQuality} the Canon IJ dialog writes for the medium
    when the user leaves the quality alone, from the model's media database.

    Each medium's ``.hmi`` lists its print qualities (``<printquality_rgb
    type="N" threeposition="fine|normal|draft|none">``) and a default.  The
    dialog picks the quality marked "normal" (the Standard position of its
    quality control) and, where a medium has none, the database's default; it
    writes it as ``CNIJPrintQuality = (N - 1) * 5``, which the filter
    (Raster2CanonIJ2S) turns back into ``<ivec:printquality>N``.  Review 2,
    2026-10-08: this reproduced every quality the PRO-300/310/200S/1000/1100
    dialogs wrote, measured on the real dialogs for every medium
    (report folder 2026-10-08_beta15_print_review2, dialog_canon/).  The
    quality is part of the printer state a profile describes: on a PRO-1000
    the plain ``lp`` job printed Canvas and the fine-art papers at type 3, the
    dialog at type 4."""
    return {mv: m.dialog_quality for mv, m in canon_media(ppd_text).items()
            if m.dialog_quality is not None}


def canon_allowed_qualities(ppd_text: str) -> dict[str, tuple[str, ...]]:
    """{medium value: the CNIJPrintQuality values the Canon dialog offers for
    it, best first} (Basti, 2026-10-09: the Print Chart tab offers them, the
    highest included, as the dialog's Custom slider does)."""
    return {mv: m.qualities for mv, m in canon_media(ppd_text).items() if m.qualities}


#: Canon media-database input bins -> the PPD's CNIJMediaSupply value.  AUTO and
#: MANUAL03 measured on the PRO-300/310/200S/1000/1100 dialogs (102 media, review
#: 2 of beta 15); the others by the PPD's own label for the value (Disc tray,
#: Multi-purpose Tray, Roll Paper (Auto), Roll 1, Roll 2, Cut Sheet).
CANON_BIN_SUPPLY = {"AUTO": "7", "MANUAL03": "38", "DISCTRAY": "26",
                    "MULTITRAYFORDISC": "75", "ROLL_AUTO": "71", "ROLL_01": "72",
                    "ROLL_02": "73", "CUT_SHEET": "70"}


def canon_driver_source(ppd_text: str, media_value: str,
                        current: str | None = None) -> str | None:
    """The paper source (CNIJMediaSupply) the Canon dialog prints *media_value*
    from, starting from *current* (the source chosen, else the PPD's default).

    The dialog keeps the current source when the medium allows it and otherwise
    switches to the medium's default (``<availableinputbinid default=...>``):
    measured on 102 media of five models, Baryta, the fine-art papers and the
    heavyweight papers went to Manual Feed (38), the rest stayed at the top
    feed (7).  None when the database does not say."""
    m = canon_media(ppd_text).get(media_value)
    if m is None or not m.bins:
        return None
    by_bin = {b: CANON_BIN_SUPPLY.get(b) for b in m.bins}
    cur = current or _ppd_default(ppd_text, "CNIJMediaSupply") or ""
    if cur in by_bin.values():
        return cur
    return CANON_BIN_SUPPLY.get(m.bin_default) or next(
        (v for v in by_bin.values() if v), None)


def epson_pde_path(ppd_text: str) -> pathlib.Path | None:
    """The model's PDEData.dat (the first variant, see ``epson_pde_variants``)."""
    paths = epson_pde_variants(ppd_text)
    if paths:
        return paths[0][1]
    m = re.search(r'^\*EPIJMachineBundleName:\s*"([^"/]+)"', ppd_text, re.M)
    if not m:
        return None
    return (driver_root() / "EPSON/InkjetPrinter2/Machine" / m.group(1) / "Contents"
            / "Resources" / "PDEData.dat")


def epson_pde_variants(ppd_text: str) -> list[tuple[str, pathlib.Path]]:
    """[(variant, PDEData.dat)] of the Epson model.  Most models have one file
    in ``Resources``.  A few keep one per ink set instead, ``Resources/1/``
    and ``Resources/2/`` (beta 16): the Stylus Photo R2400/R2880/2200 (their
    Photo Black and Matte Black papers, each listed in its own folder; the
    2200 lists Archival Matte and Watercolor in both) and the SC-P7000/P9000
    (two ink-set editions with their own profile numbers, 2-27 and 102-127).
    The print dialog asks the printer which one it has; with no printer to
    ask (the capture queues) it used folder 1, measured."""
    m = re.search(r'^\*EPIJMachineBundleName:\s*"([^"/]+)"', ppd_text, re.M)
    if not m:
        return []
    res = driver_root() / "EPSON/InkjetPrinter2/Machine" / m.group(1) / "Contents" / "Resources"
    if (res / "PDEData.dat").is_file():
        return [("", res / "PDEData.dat")]
    try:
        subs = sorted((p.name, p / "PDEData.dat") for p in res.iterdir()
                      if p.name.isdigit() and (p / "PDEData.dat").is_file())
    except OSError:
        return []
    return sorted(subs, key=lambda x: int(x[0]))


def _epson_pde_text(path: pathlib.Path) -> str | None:
    try:
        return read_text(path, lenient=True)
    except OSError:
        return None


def epson_pde(ppd_text: str, variant: str | None = None) -> tuple[str | None, dict[str, list]]:
    """(dialog type, {key: rules}) from the Epson model's PDEData.dat, the
    file its print dialog reads (*variant*: which black-ink folder, the first
    one when None).  A rule is ``([(key, value), ...], result)``;
    the first rule whose conditions all hold gives the key's value, a rule
    without conditions is the fallback.  ``(None, {})`` when absent."""
    paths = dict(epson_pde_variants(ppd_text))
    path = paths.get(variant) if variant is not None else next(iter(paths.values()), None)
    if path is None:
        return None, {}
    text = _epson_pde_text(path)
    if text is None:
        return None, {}
    ui = re.search(r'^\*EPIJUIType:\s*"([^"]+)"', text, re.M)
    tables: dict[str, list] = {}
    for key, body in re.findall(r'^\*EPIJConditionValue\s+(\S+?)/:\s*"(.*?)"', text,
                                re.S | re.M):
        rules = []
        for line in body.splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            cond, _, result = line.rpartition("|")
            pairs = re.findall(r"\*(\S+)\s+(\S+)", cond)
            rules.append((pairs, result.strip()))
        tables[key] = rules
    return (ui.group(1) if ui else None), tables


def epson_condition_value(rules: list, settings: dict[str, str]) -> str | None:
    """The value the first matching rule of *rules* gives for *settings*."""
    for pairs, result in rules:
        if all(settings.get(k) == v for k, v in pairs):
            return result
    return None


def epson_driver_table(ppd_text: str) -> dict[str, str]:
    """{medium value: EPIJProfileSpec} from the Epson model's PDEData.dat, for
    a colour job with the PPD's defaults.  Vendor tests 2026-10-08: reproduces
    every value the ET-8550/18100, SC-P900/P700/P5300/P800 and R3000/R2000
    dialogs wrote (ET-8550 Letterhead and Photo Stickers: 1, measured)."""
    blocks = {key: values for key, _label, values in parse_ppd_options(ppd_text)}
    base = {k: _ppd_default(ppd_text, k) or "" for k in blocks}
    out = {}
    for mv, _label in blocks.get("EPIJ_Medi", []):
        variant = epson_variant_for(ppd_text, mv)
        _ui, tables = epson_pde(ppd_text, variant)
        rules = tables.get("EPIJProfileSpec")
        if not rules:
            continue
        v = epson_condition_value(rules, {**base, "EPIJ_Medi": mv})
        if v is not None:
            out[mv] = v
    return out


def epson_variant_for(ppd_text: str, media_value: str,
                      options: dict[str, str] | None = None) -> str | None:
    """Which PDEData variant (ink-set folder, ``epson_pde_variants``) gives
    the medium: one file, that one; several, the first whose EPIJProfileSpec
    table names the medium itself (R2400/R2880 list every medium in one of
    them only), else the first.  *options* is kept for callers."""
    variants = epson_pde_variants(ppd_text)
    if len(variants) <= 1:
        return variants[0][0] if variants else None
    names = [v for v, _p in variants]
    for v in names:
        _ui, tables = epson_pde(ppd_text, v)
        for pairs, _result in tables.get("EPIJProfileSpec", []):
            if ("EPIJ_Medi", media_value) in pairs:
                return v
    return names[0]


def epson_ui_type(ppd_text: str) -> str | None:
    return epson_pde(ppd_text)[0]


def epson_driver_quality(ppd_text: str, media_value: str,
                         settings: dict[str, str]) -> str | None:
    """The EPIJ_Qual the Epson dialog sets when the user picks *media_value*,
    from the model's PDEData.dat: ``*EPIJLinkValue: *EPIJ_Medi <medium>|
    <conditions>|*EPIJ_Qual <q> ...``, the first line whose conditions hold for
    *settings* (the job's EPIJ_Mode and EPIJ_Ink_).  Review 2, 2026-10-08:
    reproduces all 13 qualities the ET-8550, ET-18100, SC-P800, R3000 and
    R2000 dialogs wrote (vendor tests).  None when the file has no such line
    (the SC-P900/P700/P5300 dialogs choose quality another way, EPIJ_APri)."""
    variant = epson_variant_for(ppd_text, media_value, settings)
    path = dict(epson_pde_variants(ppd_text)).get(variant or "") if variant is not None \
        else epson_pde_path(ppd_text)
    if path is None:
        return None
    text = _epson_pde_text(path)
    if text is None:
        return None
    for mv, cond, result in re.findall(
            r'^\*EPIJLinkValue:\s*\*EPIJ_Medi\s+(\S+)\|([^|\n]*)\|([^\n]*)$', text, re.M):
        if mv != media_value:
            continue
        if not all(settings.get(k) == v for k, v in re.findall(r"\*(\S+)\s+(\S+)", cond)):
            continue
        q = re.search(r"\*EPIJ_Qual\s+(\S+)", result)
        if q:
            return q.group(1)
    return None


#: Epson dialog types that stay in Automatic mode (EPIJ_Mode 0) and choose the
#: quality through EPIJ_APri and EPIJAutoPreset: the SC-P900/P700/P5300 dialog
#: ("NewUI_J", vendor tests) and the legacy Stylus Photo 1390/1400 one (its
#: PDEData.dat names no type, "N/A"; beta 16, 7 media measured)
EPSON_AUTOMATIC_UIS = ("NewUI_J", "N<2F>A", "N/A")


def _epson_presets(text: str, name: str) -> dict[tuple[str, ...], dict[str, str]]:
    """``*EPIJPreset <name>,k1,k2,.../`` blocks: {(k1, k2, ...): {key: value}}."""
    out = {}
    for k, body in re.findall(r'^\*EPIJPreset ' + re.escape(name) + r',([^/]*)/[^:]*:\s*"(.*?)"',
                              text, re.M | re.S):
        toks = body.split()
        out[tuple(k.split(","))] = dict(zip(toks[::2], toks[1::2]))
    return out


def _epson_link(text: str, trigger: str, value: str, settings: dict[str, str],
                target: str) -> str | None:
    """The first ``*EPIJLinkValue: *<trigger> <value>|<conditions>|<results>``
    whose conditions hold for *settings* and that sets *target*."""
    for v, cond, res in re.findall(r'^\*EPIJLinkValue:\s*\*' + re.escape(trigger)
                                   + r'\s+(\S+)\|([^|\n]*)\|([^\n]*)$', text, re.M):
        if v != value:
            continue
        if not all(settings.get(k) == x for k, x in re.findall(r"\*(\S+)\s+(\S+)", cond)):
            continue
        r = dict(re.findall(r"\*(\S+)\s+(\S+)", res))
        if target in r:
            return r[target]
    return None


def epson_dialog_keys(ppd_text: str, media_value: str) -> dict[str, str]:
    """What the Epson print dialog writes for *media_value* in application
    colour matching, worked out from the model's PDEData.dat the way its
    dialog does (beta 16), besides the paper profile:

    * ``EPIJ_APri``: the automatic priority its medium link gives (Mode 0);
    * ``EPIJ_CCor``: ``EPIJColorControlPreset`` for (medium, colour, Mode 0,
      that priority), then ``EPIJAMMPreset`` for application matching;
    * ``EPIJ_MeInSeNm``/``EPIJ_MdGropID``: the black ink and media group of
      ``EPIJMediaGroupPreset`` (SC-P6000 to P9000: Matte Black for matte
      papers), and the paper configuration of ``EPIJPaperConfigPreset``
      (``EPIJ_Thck``, ``EPIJ_PGDt``, ``EPIJ_Suct``, ``EPIJ_RpTn``...): each of
      them changes the commands the printer gets (beta 16, measured through
      the full Epson filter chain);
    * ``EPIJ_Mode`` and ``EPIJ_Qual``: an automatic dialog
      (``EPSON_AUTOMATIC_UIS``) stays at Mode 0 and takes the quality from
      ``EPIJAutoPreset``; any other sets Mode 3 and the quality, high speed,
      finest detail and Super MicroWeave its medium link gives.

    Validated on every Epson dialog measurement of both vendor rounds (25
    models, 120 media, report folder 2026-10-09_vendor_tests2): all keys equal
    apart from four qualities where the probe opened the dialog with the
    medium already chosen, so its medium link never fired.  {} when the model's
    PDEData.dat cannot be read."""
    variant = epson_variant_for(ppd_text, media_value)
    path = dict(epson_pde_variants(ppd_text)).get(variant or "") if variant is not None else None
    text = _epson_pde_text(path) if path is not None else None
    if not text:
        return {}
    ui = re.search(r'^\*EPIJUIType:\s*"([^"]+)"', text, re.M)
    automatic = bool(ui) and ui.group(1) in EPSON_AUTOMATIC_UIS
    ink = "1"
    out: dict[str, str] = {}
    apri = _epson_link(text, "EPIJ_Medi", media_value,
                       {"EPIJ_Mode": "0", "EPIJ_Ink_": ink}, "EPIJ_APri") or "0"
    for key, d in _epson_presets(text, "EPIJColorControlPreset").items():
        if key[:4] == (media_value, ink, "0", apri) and "EPIJ_CCor" in d:
            out["EPIJ_CCor"] = d["EPIJ_CCor"]
            break
    auto_preset = _epson_presets(text, "EPIJAutoPreset").get((media_value, ink, "0", apri), {})
    if "EPIJ_CCor" not in out:
        # a dialog without colour-control presets (the PictureMates) keeps the
        # colour keys of its automatic preset for the medium: EPSON Vivid on
        # photo papers, CMat 0, the scene-correction keys
        for k in ("EPIJ_CCor", "EPIJ_CMat", "EPIJ_ATon", "EPIJ_AGai", "EPIJ_ACam",
                  "EPIJ_AFil", "EPIJ_DCCT"):
            if k in auto_preset:
                out[k] = auto_preset[k]
    amm = _epson_presets(text, "EPIJAMMPreset").get(("2",), {})
    if "EPIJ_CCor" in amm:
        out["EPIJ_CCor"] = amm["EPIJ_CCor"]
    # the media group and its black ink (SC-P6000 to P9000: Matte Black for
    # matte papers), and the paper configuration the large-format dialog sets
    # for the paper (thickness, platen gap, suction, roll tension, feed)
    group = _epson_presets(text, "EPIJMediaGroupPreset").get((media_value,), {})
    out.update({k: v for k, v in group.items() if k.startswith("EPIJ_")})
    for key, d in _epson_presets(text, "EPIJPaperConfigPreset").items():
        if key[0] == media_value:
            out.update({k: v for k, v in d.items() if k.startswith("EPIJ_")})
            break
    if automatic:
        out["EPIJ_Mode"], out["EPIJ_APri"] = "0", apri
        out.update({k: v for k, v in auto_preset.items()
                    if k in ("EPIJ_Qual", "EPIJ_Bi_D", "EPIJ_FDet", "EPIJ_FWea", "EPIJ_Weav")})
    else:
        out["EPIJ_Mode"] = "3"
        # the paper's own link in the Advanced mode: quality, high speed,
        # finest detail, Super MicroWeave
        for v, cond, res in re.findall(r'^\*EPIJLinkValue:\s*\*EPIJ_Medi\s+(\S+)\|([^|\n]*)\|'
                                       r'([^\n]*)$', text, re.M):
            if v != media_value:
                continue
            if not all({"EPIJ_Mode": "3", "EPIJ_Ink_": ink}.get(k) == x
                       for k, x in re.findall(r"\*(\S+)\s+(\S+)", cond)):
                continue
            r = dict(re.findall(r"\*(EPIJ_\w+)\s+([^*\s]+)", res))
            if "EPIJ_Qual" in r:
                out.update({k: r[k] for k in ("EPIJ_Qual", "EPIJ_Bi_D", "EPIJ_FDet",
                                              "EPIJ_FWea", "EPIJ_Weav") if k in r})
                break
    # The standard CUPS options the dialog sets from its condition tables:
    # MediaType, ColorModel and, above all, Resolution, the resolution the
    # chart is rasterised at for the filter (Premium Glossy: 720x720dpi where
    # the PPD's default is 360x360dpi).  Beta 15 sent none of them.
    _ui, tables = epson_pde(ppd_text, variant)
    settings = {k: v for k, v in ((k, _ppd_default(ppd_text, k)) for k, _l, _v in
                                  parse_ppd_options(ppd_text)) if v is not None}
    settings.update(out)
    settings.update({"EPIJ_Medi": media_value, "EPIJ_Ink_": ink})
    for key in ("MediaType", "ColorModel", "Resolution"):
        v = epson_condition_value(tables.get(key, []), settings)
        if v is not None:
            out[key] = v
    return out


def epson_allowed_qualities(ppd_text: str, media_value: str,
                            settings: dict[str, str] | None = None) -> tuple[str, ...]:
    """The EPIJ_Qual values the Epson dialog offers for *media_value* in colour,
    in the PPD's order, from the model's PDEData.dat (``*EPIJConditionValue
    Resolution``: one line per medium and quality the driver can print).
    Beta 16: reproduces all 13 media of the hand-made ET-8550 lists
    (``PrintModule._EPSON_QUALITY_RULES``, taken from its dialog in beta 13);
    () when the file says nothing for the medium."""
    variant = epson_variant_for(ppd_text, media_value, settings)
    _ui, tables = epson_pde(ppd_text, variant)
    found = set()
    for pairs, _result in tables.get("Resolution", []):
        d = dict(pairs)
        if d.get("EPIJ_Medi") == media_value and "EPIJ_Qual" in d \
                and d.get("EPIJ_Ink_", "1") == "1":
            found.add(d["EPIJ_Qual"])
    order = [v for k, _l, vals in parse_ppd_options(ppd_text) if k == "EPIJ_Qual"
             for v, _lab in vals]
    return tuple(v for v in order if v in found)


@dataclass(frozen=True)
class QualityChoices:
    """What the Print Chart tab offers in its quality row for one medium (beta 16).

    Basti, 2026-10-09: he prints his photos at the highest quality the Canon
    dialog allows for the paper (its Custom slider at the top); the direct route
    sent the dialog's standard quality and offered no choice.  *values* are the
    qualities the driver's dialog offers for the medium, in the PPD's order;
    *highest* the best of them; *standard* the one the dialog picks when left
    alone; *learned* the one the user's last print through the macOS dialog on
    this paper used (``workflow.printer_memory``)."""

    option: str
    values: tuple[str, ...]
    highest: str | None
    standard: str | None
    learned: str | None = None

    @property
    def preselect(self) -> str | None:
        if self.learned in self.values:
            return self.learned
        return self.standard if self.standard in self.values else None


def quality_choices(ppd_text: str, options: dict[str, str] | None = None,
                    learned=None) -> QualityChoices | None:
    """The quality row of the Print Chart tab for the medium in *options* (the
    PPD's default medium when none is chosen), or None when the driver's tables
    do not say which qualities the medium allows (any printer that is not a
    Canon IJ or Epson model with readable tables; the tab then keeps its
    generic quality row).  *learned*: a ``printer_memory.PaperProfileMemory``."""
    options = options or {}
    blocks = {key: values for key, _label, values in parse_ppd_options(ppd_text)}
    for rule in PAPER_PROFILE_RULES:
        if rule.media_option not in blocks or rule.quality_option not in blocks:
            continue
        mv = str(options.get(rule.media_option) or _ppd_default(ppd_text, rule.media_option)
                 or "")
        ppd_values = [v for v, _l in blocks[rule.quality_option]]
        try:
            if rule.driver_table == "canon-db":
                values = tuple(v for v in ppd_values
                               if v in canon_allowed_qualities(ppd_text).get(mv, ()))
                standard = canon_driver_qualities(ppd_text).get(mv)
                highest = min(values, key=int) if values else None
            else:
                settings = {k: str(options.get(k) or _ppd_default(ppd_text, k) or "")
                            for k in ("EPIJ_Mode", "EPIJ_Ink_")}
                settings["EPIJ_Mode"] = settings["EPIJ_Mode"] if settings["EPIJ_Mode"] \
                    not in ("", "0") else "3"
                values = epson_allowed_qualities(ppd_text, mv, settings)
                standard = epson_driver_quality(ppd_text, mv, settings)
                highest = values[-1] if values else None
        except Exception:  # noqa: BLE001 - a broken driver file must not stop printing
            return None
        if not values:
            return None
        hit = None
        model = ppd_model(ppd_text)
        if learned is not None and model:
            try:
                hit = learned.lookup(model, rule.media_option, mv)
            except Exception:  # noqa: BLE001
                hit = None
        lq = str((hit or {}).get("keys", {}).get(rule.quality_option) or "") or None
        return QualityChoices(option=rule.quality_option, values=values, highest=highest,
                              standard=standard if standard in values else None,
                              learned=lq if lq in values else None)
    return None


# ---- 2. the tables shipped with ChromIQ ---------------------------------------------

BUILT_IN_TABLES = "data/printer_paper_profiles.json"
_built_in_cache: dict | None = None


def built_in_tables() -> dict:
    """``{"models": {model: {...}}}`` from ``data/printer_paper_profiles.json``
    (see ``scripts/printer_paper_tables.py``); {} when it cannot be read."""
    global _built_in_cache
    if _built_in_cache is None:
        import json
        from core.resource_path import resource_path
        try:
            _built_in_cache = json.loads(
                resource_path(BUILT_IN_TABLES).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _built_in_cache = {}
    return _built_in_cache


def built_in_model(model: str) -> dict | None:
    return (built_in_tables().get("models") or {}).get(model)


# ---- 3. what the user's own dialog prints taught ChromIQ: workflow.printer_memory -----


def _allowed(ppd_text: str, blocks: dict, keys: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """*keys* without any option the PPD lacks or any value it does not offer
    (vendor tests: beta 15 sent EPIJ_CCor=3 where the SC-P900's PPD allows only
    4 and 6)."""
    out = []
    for k, v in keys.items():
        values = {val for val, _ in blocks.get(k, [])}
        if v in values:
            out.append((k, v))
    return tuple(out)


def _epson_type_keys(rule: PaperProfileRule, ppd_text: str) -> dict[str, str]:
    """The Epson dialog keys for a model ChromIQ has not measured, by its
    dialog type (``EPSON_MODE_BY_UI``)."""
    keys = dict(rule.dialog_keys)
    ui = epson_ui_type(ppd_text)
    mode = EPSON_MODE_BY_UI.get(ui, EPSON_MODE_DEFAULT) if ui else EPSON_MODE_DEFAULT
    if mode is not None:
        keys["EPIJ_Mode"] = mode
    # EPIJ_CCor is not sent: only the ET-8550 class changes it, and only per
    # medium; a model ChromIQ has not measured keeps the PPD's default.
    return keys


def paper_profile_for(ppd_text: str, options: dict[str, str] | None = None,
                      honour_profile_option: bool = False,
                      learned=None) -> PaperProfile | None:
    """The paper profile the vendor's print dialog puts on the ticket for the
    medium in *options* (or the PPD's default medium), or None when the PPD is
    not one of ``PAPER_PROFILE_RULES``'s vendors.  Pure text work apart from
    reading the installed driver's tables; any platform.

    *honour_profile_option*: when *options* already names a value of the
    profile option (a job read back from CUPS), that is the profile the job
    selects ("job").  The lp route computes it from the medium instead.

    *learned*: a ``printer_memory.PaperProfileMemory`` (or None); asked only
    for a model neither the driver's nor ChromIQ's tables know."""
    options = options or {}
    blocks = {key: values for key, _label, values in parse_ppd_options(ppd_text)}
    for rule in PAPER_PROFILE_RULES:
        if rule.media_option not in blocks or rule.profile_option not in blocks:
            continue
        q = _qualifier_index(ppd_text, rule.profile_option)
        if q is None:
            continue
        model = ppd_model(ppd_text)
        media_value = str(options.get(rule.media_option) or _ppd_default(
            ppd_text, rule.media_option) or "")
        media_label = dict(blocks[rule.media_option]).get(media_value, media_value)
        quality = str(options.get(rule.quality_option) or "") if rule.quality_option else ""
        values = dict(blocks[rule.profile_option])
        default = _ppd_default(ppd_text, rule.profile_option)
        chosen: str | None = None
        source = "unknown"
        keys: dict[str, str] = {}
        if honour_profile_option and options.get(rule.profile_option) is not None:
            carried = str(options[rule.profile_option])
            if carried in values:
                chosen, source = carried, "job"
        if chosen is None:
            chosen = _driver_value(rule, ppd_text, media_value, values, quality)
            if chosen is not None:
                source = "driver"
        built = built_in_model(model) if model else None
        if built is not None and built.get("vendor") == rule.vendor:
            entry = (built.get("media") or {}).get(media_value)
            if chosen is None and entry and entry.get("profile") in values:
                chosen, source = entry["profile"], "built-in"
            keys.update(rule.dialog_keys)
            keys.update(built.get("dialog_keys") or {})
            if entry:
                keys.update(entry.get("keys") or {})
        elif rule.vendor == "Epson":
            keys.update(_epson_type_keys(rule, ppd_text))
        else:
            keys.update(rule.dialog_keys)
        if rule.driver_table == "epson-pde":
            # beta 16: what the installed driver's dialog writes for the medium,
            # worked out from its PDEData.dat (``epson_dialog_keys``); it
            # agrees with every measurement and also covers unmeasured media
            try:
                emulated = epson_dialog_keys(ppd_text, media_value)
            except Exception:  # noqa: BLE001 - a broken driver file must not stop printing
                emulated = {}
            if emulated:
                keys.update(rule.dialog_keys)
                keys.update(emulated)
        if chosen is None and learned is not None and model:
            hit = learned.lookup(model, rule.media_option, media_value,
                                 rule.quality_option, quality)
            if hit and _learned_still_valid(hit, values, blocks, rule):
                chosen, source = str(hit["value"]), "learned"
                keys.update(hit.get("keys") or {})
        if chosen is None:
            chosen, source = default, "unknown"
        keys.pop(rule.profile_option, None)
        if rule.quality_option:
            if str(options.get(rule.quality_option) or ""):
                # the user chose the quality (the Print Chart tab offers it on
                # Epson): that is what goes, as in the dialog
                auto_q = keys.pop(rule.quality_option, None)
                if keys.get("EPIJ_Mode") == "0" and \
                        str(options[rule.quality_option]) != auto_q:
                    # an automatic Epson dialog prints a chosen quality only in
                    # its Advanced mode, as the user's photos then must too
                    keys["EPIJ_Mode"] = "3"
                    keys.pop("EPIJ_APri", None)
            elif rule.quality_option not in keys:
                # review 2: the quality the dialog picks for the medium when the
                # user leaves it alone (lp otherwise sent the PPD's default)
                q_val = _driver_quality(rule, ppd_text, media_value, keys, options)
                if q_val is not None:
                    keys[rule.quality_option] = q_val
        if rule.driver_table == "canon-db" and "Resolution" in blocks \
                and not str(options.get("Resolution") or ""):
            # beta 16: the Canon dialog also sets the PPD's Resolution for the
            # paper and quality, which the chart is rasterised at
            try:
                medium = canon_media(ppd_text).get(media_value)
                job_q = str(options.get(rule.quality_option) or keys.get(rule.quality_option)
                            or "")
                res = medium.resolution_for(job_q) if medium is not None else None
            except Exception:  # noqa: BLE001
                res = None
            if res is not None:
                keys["Resolution"] = res
        if rule.source_option and rule.source_option in blocks:
            if str(options.get(rule.source_option) or ""):
                # the user chose the paper source in the tab: that one goes
                keys.pop(rule.source_option, None)
            else:
                # beta 16: the source the dialog switches to for this medium
                # (Baryta, fine-art and heavyweight papers: Manual Feed)
                try:
                    src = canon_driver_source(ppd_text, media_value) \
                        if rule.driver_table == "canon-db" else None
                except Exception:  # noqa: BLE001
                    src = None
                if src is not None:
                    keys[rule.source_option] = src
                if keys.get(rule.source_option) == _ppd_default(ppd_text, rule.source_option):
                    keys.pop(rule.source_option)   # what lp gets anyway
        icc = None
        if chosen is not None:
            for quals, _label, path in _icc_profiles(ppd_text):
                if len(quals) >= q and quals[q - 1] == chosen:
                    icc = path
                    break
        return PaperProfile(rule=rule, media_value=media_value, media_label=media_label,
                            option=rule.profile_option, value=chosen,
                            label=values.get(chosen, chosen or ""), icc_path=icc,
                            is_default=(chosen == default), source=source, model=model,
                            dialog_keys=_allowed(ppd_text, blocks, keys))
    return None


def _driver_value(rule: PaperProfileRule, ppd_text: str, media_value: str,
                  values: dict[str, str], quality: str = "") -> str | None:
    """The profile value the installed driver's own table gives the medium (at
    *quality*, the quality the job prints at, where the table depends on it)."""
    try:
        if rule.driver_table == "canon-db":
            medium = canon_media(ppd_text).get(media_value)
            if medium is None or not medium.icc:
                return None
            icc = medium.icc_for(quality)
            by_label = {label: val for val, label in values.items()}
            return by_label.get(icc)
        if rule.driver_table == "epson-pde":
            v = epson_driver_table(ppd_text).get(media_value)
            return v if v in values else None
    except Exception:  # noqa: BLE001 - a broken driver file must not stop printing
        return None
    return None


def _learned_still_valid(hit: dict, values: dict[str, str], blocks: dict,
                         rule: PaperProfileRule) -> bool:
    """A learned entry is used only while the installed PPD still means the same
    by it (review 2: a driver update can renumber its paper profiles).  The
    value must still exist and still carry the label it had when it was learned;
    the medium too, when its label was kept."""
    value = str(hit.get("value"))
    if value not in values:
        return False
    label = hit.get("label")
    if label and values.get(value) != label:
        log.warning("printer memory: %s=%s is now %r in the driver, was %r when "
                    "learned; not used", rule.profile_option, value, values.get(value),
                    label)
        return False
    return True


def _driver_quality(rule: PaperProfileRule, ppd_text: str, media_value: str,
                    keys: dict[str, str], options: dict[str, str]) -> str | None:
    """The print quality the installed driver's dialog picks for the medium."""
    try:
        if rule.driver_table == "canon-db":
            return canon_driver_qualities(ppd_text).get(media_value)
        if rule.driver_table == "epson-pde":
            settings = {k: str(options.get(k) or keys.get(k) or _ppd_default(ppd_text, k)
                               or "") for k in ("EPIJ_Mode", "EPIJ_Ink_")}
            return epson_driver_quality(ppd_text, media_value, settings)
    except Exception:  # noqa: BLE001 - a broken driver file must not stop printing
        return None
    return None


def dialog_keys_without_paper_profile(ppd_text: str,
                                      options: dict[str, str] | None = None) -> dict[str, str]:
    """Beta 16: the keys an Epson print dialog writes for the medium on a model
    that has no paper profiles at all (the PictureMate PM-400/PM-520: no
    EPIJProfileSpec, no "no colour adjustment" value).  Its dialog, in
    application colour matching, sets Mode 3, the medium's quality and the
    driver's own colour mode (EPSON Vivid on photo papers); the direct route
    left the PPD's defaults (Mode 0, Automatic).  Keys the user chose in the
    tab stay theirs; only values the PPD offers.  {} for any other printer."""
    options = options or {}
    blocks = {key: values for key, _label, values in parse_ppd_options(ppd_text)}
    if "EPIJ_Medi" not in blocks or "EPIJProfileSpec" in blocks:
        return {}
    mv = str(options.get("EPIJ_Medi") or _ppd_default(ppd_text, "EPIJ_Medi") or "")
    try:
        keys = epson_dialog_keys(ppd_text, mv)
    except Exception:  # noqa: BLE001 - a broken driver file must not stop printing
        return {}
    keys = {k: v for k, v in keys.items() if not str(options.get(k) or "")}
    return dict(_allowed(ppd_text, blocks, keys))


def paper_profile_for_queue(queue_name: str, options: dict[str, str] | None = None,
                            learned=None) -> PaperProfile | None:
    path = ppd_path_for_queue(queue_name)
    if path is None:
        return None
    try:
        text = read_text(pathlib.Path(path), lenient=True)
    except OSError:
        return None
    return paper_profile_for(text, options, learned=learned)


def ppd_path_for_queue(queue_name: str) -> str | None:
    for base in ("/etc/cups/ppd", "/private/etc/cups/ppd"):
        p = pathlib.Path(f"{base}/{queue_name}.ppd")
        if p.exists():
            return str(p)
    return None


#: The one key Photoshop itself puts on a job when it manages colours.
APPLICATION_COLOUR_MATCHING = {"AP_ColorMatchingMode": "AP_ApplicationColorMatching"}
