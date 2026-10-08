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
# on macOS 27.0.1 with capture queues (report folder 2026-10-08_print_fix):
#
# * Photoshop's own contribution to the job ticket is one key,
#   AP_ColorMatchingMode=AP_ApplicationColorMatching.  Everything else on the
#   ticket is written by the driver's print-dialog extension (PDE) for the medium
#   chosen in the dialog.
# * The Canon IJ PDE writes, besides the medium, the paper profile it belongs to
#   (CNIJProfileID).  macOS's rasteriser picks the matching *cupsICCProfile through
#   the PPD's *cupsICCQualifierN line, and the Canon filter (Raster2CanonIJ2S)
#   tells the printer `printcolormode_intent=none` only when, in application mode,
#   that id names a paper profile; otherwise `pro` (Canon's own colour processing).
#   CNIJIntent2 is ignored in application mode: the printer stream for
#   CNIJIntent2=5 and =1001 is byte-identical apart from the job UUID.
# * ``lp`` has no PDE, so without the paper-profile key a Canon photo-paper job ran
#   in `pro` although ChromIQ said "colour management off".
#
# The rule below is how a PDE maps a medium to its paper profile, expressed as
# data: a PPD declares the profile-selecting option in *cupsICCQualifierN, the
# option's values are labelled with the profile names, and the medium's label is
# the same name in words.  Recorded per vendor, with the evidence it rests on.


@dataclass(frozen=True)
class PaperProfileRule:
    """How one vendor's print dialog picks the paper profile for a medium."""

    vendor: str
    #: PPD option that names the medium the user chose
    media_option: str
    #: PPD option that selects the paper profile (the PPD's *cupsICCQualifierN)
    profile_option: str
    #: regexes removed from a profile value's label before comparing names
    profile_label_strip: tuple[str, ...]
    #: regexes removed from a medium's label before comparing names
    media_label_strip: tuple[str, ...] = ()
    #: normalised medium name -> normalised profile name, where the words differ
    aliases: tuple[tuple[str, str], ...] = ()
    #: True when the vendor's filter switches its own colour processing off,
    #: in application colour matching, only for a job naming a paper profile
    #: other than the PPD's default (Canon: `none` vs `pro`)
    own_colour_off_needs_paper_profile: bool = False
    #: keys the vendor's dialog writes in application colour matching whatever
    #: the medium, and which ``lp`` (no dialog) must therefore send itself so
    #: the job equals the reference.  Only keys whose PPD default differs.
    dialog_keys: tuple[tuple[str, str], ...] = ()
    #: per medium value, keys the dialog writes differently from ``dialog_keys``
    dialog_keys_by_media: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = ()
    evidence: str = ""

    def dialog_keys_for(self, media_value: str) -> dict[str, str]:
        keys = dict(self.dialog_keys)
        keys.update(dict(dict(self.dialog_keys_by_media).get(media_value, ())))
        return keys


PAPER_PROFILE_RULES: tuple[PaperProfileRule, ...] = (
    PaperProfileRule(
        vendor="Canon IJ",
        media_option="CNIJMediaType",
        profile_option="CNIJProfileID",
        profile_label_strip=(r"^CN_[^_]+_G\d+_", r"\.icc$", r"-P$"),
        own_colour_off_needs_paper_profile=True,
        # The PDE also writes CNIJColorMatchingMode=1 and CNIJHalfToneRadio=0;
        # neither changes one byte of the printer stream (measured), so lp does
        # not send them.
        evidence=(
            "Canon PRO-300 driver 30.10.1, macOS 27.0.1, 2026-10-08: in application "
            "colour matching the PDE wrote CNIJProfileID 1/3/4/6/10/11/17/1/1 for "
            "Plain Paper/Photo Paper Pro Platinum/Luster/Matte Photo Paper/Baryta/"
            "Premium Fine Art Smooth/Canvas/Hagaki/Card Stock; Raster2CanonIJ2S "
            "sends printcolormode_intent=none for application mode with ids 2-18, "
            "pro otherwise, and ignores CNIJIntent2 there"),
    ),
    PaperProfileRule(
        vendor="Epson",
        media_option="EPIJ_Medi",
        profile_option="EPIJProfileSpec",
        profile_label_strip=(r"^EPSON .*? Series ",),
        media_label_strip=(r"^Epson ",),
        # "Photo Paper Glossy" -> "Photo Glossy": the ET-8550 dialog wrote
        # EPIJProfileSpec=5 for EPIJ_Medi=145 (review 2026-10-08, N15_epson_m145);
        # without the alias lp sent 0 ("None") and the read-back cried wolf.
        aliases=(("plainpaper", "standard"), ("velvetfineartpaper", "velvetfineart"),
                 ("photopaperglossy", "photoglossy")),
        dialog_keys=(("EPIJ_Mode", "3"), ("EPIJ_CMat", "3"), ("EPIJ_CCor", "3"),
                     ("EPIJ_OSColMat", "2"), ("EPIJ_OSCMProf", "1"),
                     ("EPIJ_HdofClSp", "0")),
        # plain paper: the dialog leaves the colour-mode choice at the PPD's 12
        dialog_keys_by_media=(("0", (("EPIJ_CCor", "12"),)),),
        evidence=(
            "Epson ET-8550 driver 13.45, macOS 27.0.1, 2026-10-08: in application "
            "colour matching the PDE wrote EPIJProfileSpec 1/3/6/8/7/2 for Plain "
            "paper/Epson Premium Glossy/Epson Matte/Photo Quality Ink Jet/Velvet Fine "
            "Art Paper/Epson Ultra Glossy, and on every medium EPIJ_Mode=3 (Custom), "
            "EPIJ_CMat=3 (Off, No Color Adjustment), EPIJ_OSColMat=2, "
            "EPIJ_OSCMProf=1, EPIJ_HdofClSp=0, where the PPD defaults differ "
            "(EPIJ_CCor=3 on the photo media, 12 on plain paper); review 2026-10-08: "
            "EPIJProfileSpec 5/4 for Photo Paper Glossy/Epson Premium Semigloss"),
    ),
)


@dataclass(frozen=True)
class PaperProfile:
    """The paper profile a vendor's dialog would select for one medium."""

    rule: PaperProfileRule
    media_value: str
    media_label: str
    option: str
    value: str
    label: str
    icc_path: str | None
    is_default: bool


def _norm(text: str, strip: tuple[str, ...]) -> str:
    for rx in strip:
        text = re.sub(rx, "", text, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", text.lower())


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


def paper_profile_for(ppd_text: str, options: dict[str, str] | None = None,
                      honour_profile_option: bool = False) -> PaperProfile | None:
    """The paper profile the vendor's print dialog would put on the ticket for the
    medium in *options* (or the PPD's default medium), or None when the PPD is not
    one of ``PAPER_PROFILE_RULES``'s vendors.  Pure text work, any platform.

    *honour_profile_option*: when *options* already names a value of the
    profile option (a job read back from CUPS), that is the profile the job
    selects, whatever the medium's name maps to.  The read-back uses it; the
    lp route does not, it computes the value from the medium."""
    options = options or {}
    blocks = {key: (label, values) for key, label, values in parse_ppd_options(ppd_text)}
    for rule in PAPER_PROFILE_RULES:
        if rule.media_option not in blocks or rule.profile_option not in blocks:
            continue
        q = _qualifier_index(ppd_text, rule.profile_option)
        if q is None:
            continue
        media_value = options.get(rule.media_option) or _ppd_default(
            ppd_text, rule.media_option) or ""
        media_label = dict(blocks[rule.media_option][1]).get(media_value, media_value)
        want = _norm(media_label, rule.media_label_strip)
        want = dict(rule.aliases).get(want, want)
        default = _ppd_default(ppd_text, rule.profile_option)
        chosen = None
        if honour_profile_option and options.get(rule.profile_option):
            carried = str(options[rule.profile_option])
            values = dict(blocks[rule.profile_option][1])
            if carried in values:
                chosen = (carried, values[carried])
        for val, vlabel in (() if chosen else blocks[rule.profile_option][1]):
            if _norm(vlabel, rule.profile_label_strip) == want:
                chosen = (val, vlabel)
                break
        if chosen is None:
            values = dict(blocks[rule.profile_option][1])
            chosen = (default, values.get(default, default)) if default else None
        if chosen is None:
            return None
        icc = None
        for quals, _label, path in _icc_profiles(ppd_text):
            if len(quals) >= q and quals[q - 1] == chosen[0]:
                icc = path
                break
        return PaperProfile(rule=rule, media_value=media_value, media_label=media_label,
                            option=rule.profile_option, value=chosen[0],
                            label=chosen[1], icc_path=icc,
                            is_default=(chosen[0] == default))
    return None


def paper_profile_for_queue(queue_name: str, options: dict[str, str] | None = None
                            ) -> PaperProfile | None:
    path = ppd_path_for_queue(queue_name)
    if path is None:
        return None
    try:
        text = read_text(pathlib.Path(path), lenient=True)
    except OSError:
        return None
    return paper_profile_for(text, options)


def ppd_path_for_queue(queue_name: str) -> str | None:
    for base in ("/etc/cups/ppd", "/private/etc/cups/ppd"):
        p = pathlib.Path(f"{base}/{queue_name}.ppd")
        if p.exists():
            return str(p)
    return None


#: The one key Photoshop itself puts on a job when it manages colours.
APPLICATION_COLOUR_MATCHING = {"AP_ColorMatchingMode": "AP_ApplicationColorMatching"}
