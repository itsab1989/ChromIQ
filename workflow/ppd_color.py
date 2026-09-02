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
