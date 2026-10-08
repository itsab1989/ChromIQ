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


def canon_driver_table(ppd_text: str) -> dict[str, str]:
    """{medium value: output ICC file name} from the Canon IJ model's media
    database: ``<uuid>.hmi`` of each medium (``*CNIJMediaTypeIVEC`` gives the
    uuid), the ``<output_icc>`` of its colour mode.  That is the profile the
    dialog writes for the medium: vendor tests 2026-10-08 reproduced every id the
    PRO-300/310/200S/1000/1100 dialogs wrote.  The profile does not depend on the
    print quality on any of those models (0 of 174 media).  {} when the driver
    has no readable database (PRO-100: a binary table)."""
    db = canon_media_database(ppd_text)
    if db is None or not db.is_dir():
        return {}
    out: dict[str, str] = {}
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
        dq = re.search(r'<availableprintquality_rgb default="(\d+)"', body)
        icc = (by_q.get(dq.group(1)) if dq else None) or next(iter(by_q.values()))
        out[mv] = icc.strip()
    return out


def epson_pde_path(ppd_text: str) -> pathlib.Path | None:
    m = re.search(r'^\*EPIJMachineBundleName:\s*"([^"/]+)"', ppd_text, re.M)
    if not m:
        return None
    return (driver_root() / "EPSON/InkjetPrinter2/Machine" / m.group(1) / "Contents"
            / "Resources" / "PDEData.dat")


def epson_pde(ppd_text: str) -> tuple[str | None, dict[str, list]]:
    """(dialog type, {key: rules}) from the Epson model's PDEData.dat, the
    file its print dialog reads.  A rule is ``([(key, value), ...], result)``;
    the first rule whose conditions all hold gives the key's value, a rule
    without conditions is the fallback.  ``(None, {})`` when absent."""
    path = epson_pde_path(ppd_text)
    if path is None:
        return None, {}
    try:
        text = read_text(path, lenient=True)
    except OSError:
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
    _ui, tables = epson_pde(ppd_text)
    rules = tables.get("EPIJProfileSpec")
    if not rules:
        return {}
    blocks = {key: values for key, _label, values in parse_ppd_options(ppd_text)}
    base = {k: _ppd_default(ppd_text, k) or "" for k in blocks}
    out = {}
    for mv, _label in blocks.get("EPIJ_Medi", []):
        v = epson_condition_value(rules, {**base, "EPIJ_Medi": mv})
        if v is not None:
            out[mv] = v
    return out


def epson_ui_type(ppd_text: str) -> str | None:
    return epson_pde(ppd_text)[0]


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
            chosen = _driver_value(rule, ppd_text, media_value, values)
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
        if chosen is None and learned is not None and model:
            hit = learned.lookup(model, rule.media_option, media_value,
                                 rule.quality_option, quality)
            if hit and str(hit.get("value")) in values:
                chosen, source = str(hit["value"]), "learned"
                keys.update(hit.get("keys") or {})
        if chosen is None:
            chosen, source = default, "unknown"
        keys.pop(rule.profile_option, None)
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
                  values: dict[str, str]) -> str | None:
    """The profile value the installed driver's own table gives the medium."""
    try:
        if rule.driver_table == "canon-db":
            icc = canon_driver_table(ppd_text).get(media_value)
            if icc is None:
                return None
            by_label = {label: val for val, label in values.items()}
            return by_label.get(icc)
        if rule.driver_table == "epson-pde":
            v = epson_driver_table(ppd_text).get(media_value)
            return v if v in values else None
    except Exception:  # noqa: BLE001 - a broken driver file must not stop printing
        return None
    return None


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
