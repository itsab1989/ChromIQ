"""WHICH INSTRUMENT IS CONNECTED, BEFORE START, FOR THE i1Pro 2 DUAL SCAN.

The owner, 2026-11-18 (review S-1: the first measurement of an app run took
the switch "at its word", so an i1Pro 3 lost its -F and any other instrument
lost its M-FILTER-REFUSED window). Nothing is ever sent to an instrument to
find out. The order of knowing:

a. **the USB connection** (:func:`usb_family`): the operating system's own
   list, read by :func:`core.argyll_instruments.usb_devices` (ioreg / sysfs /
   the Windows device list; nothing is opened). ArgyllCMS 3.5.0's own table
   (``spectro/insttypes.c`` ``inst_usb_match``): 0765:6009 is an i1Pro 3 (an
   i1Pro 3 Plus has the same id; the driver tells them apart only after it
   opened the device, ``i1pro3_imp.c``), and 0971:2000 is "i1Pro or i1Pro 2",
   told apart by ArgyllCMS only by the number of USB pipes ("The i1pro2/rev E
   has 5 pipes"), which the system list read here does not give. So USB can
   say "an i1Pro 3", "another instrument", or "the i1Pro family", never
   "an i1Pro 2" on its own;
b. **the model the instrument reported** at the last measurement (the
   helper's ``instrument`` event and ArgyllCMS's "Instrument Type:" line),
   remembered in the settings across app runs, or the person's own answer;
c. **one question** (M-DUAL-MODEL-ASK) when neither tells, only with the dual
   scan on; the answer is remembered and shown, changed or forgotten in
   Preferences > Beta (:func:`describe`);
e. **the instrument's own report at the start always wins**: the Measure tab
   compares it with what START assumed (:func:`differs`) and starts again the
   right way before anything is read.

Only two answers matter to the dual scan: an i1Pro 2 (``"i1pro2"``) or not
(``"other"``: an i1Pro 3, the first i1Pro, any other instrument), which then
measures exactly as without the Beta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: the remembered answer: "i1pro2", "other" or "" (unknown)
SETTING = "dual_scan_instrument"
#: the instrument's own name when the answer came from its report, else ""
SETTING_NAME = "dual_scan_instrument_name"
#: "reported" (the instrument said so) or "chosen" (the person said so)
SETTING_SOURCE = "dual_scan_instrument_source"

I1PRO2, OTHER, ASK = "i1pro2", "other", "ask"
#: what the USB connection can say (:func:`usb_family`)
FAMILY_I1PRO, FAMILY_I1PRO3, FAMILY_OTHER = "i1pro_family", "i1pro3", "other"
#: ArgyllCMS 3.5.0 insttypes.c: the two ids that matter here
USB_I1PRO3 = (0x0765, 0x6009)
USB_I1PRO_FAMILY = (0x0971, 0x2000)


def usb_family(devices) -> "str | None":
    """What the USB list says about the ONE ArgyllCMS instrument attached:
    :data:`FAMILY_I1PRO3`, :data:`FAMILY_I1PRO` (an i1Pro or an i1Pro 2),
    :data:`FAMILY_OTHER`, or None (the list could not be read, nothing is
    attached, or several instruments are)."""
    if devices is None:
        return None
    from core.argyll_instruments import match
    found = {(d.vid, d.pid) for d in devices if match(d.vid, d.pid)}
    if len(found) != 1:
        return None
    ids = next(iter(found))
    if ids == USB_I1PRO3:
        return FAMILY_I1PRO3
    if ids == USB_I1PRO_FAMILY:
        return FAMILY_I1PRO
    return FAMILY_OTHER


def attached_family() -> "str | None":
    """:func:`usb_family` of what is attached now (a plain system read)."""
    from core import argyll_instruments
    try:
        return usb_family(argyll_instruments.usb_devices())
    except Exception:  # noqa: BLE001 - an unreadable list is "cannot tell"
        return None


def kind_of(reported_model: "str | None") -> str:
    """"i1pro2" for a reported i1Pro 2, "other" for any other report, ""."""
    if not reported_model:
        return ""
    from core.measure_pace import model_key
    return I1PRO2 if model_key(reported_model) == "i1pro2" else OTHER


@dataclass(frozen=True)
class Remembered:
    kind: str = ""          # "i1pro2", "other" or ""
    name: str = ""          # the instrument's own name, when it reported it
    source: str = ""        # "reported" or "chosen"


def remembered(settings: Any) -> Remembered:
    try:
        kind = str(settings.get(SETTING, "") or "")
        if kind not in (I1PRO2, OTHER):
            return Remembered()
        return Remembered(kind, str(settings.get(SETTING_NAME, "") or ""),
                          str(settings.get(SETTING_SOURCE, "") or ""))
    except Exception:  # noqa: BLE001 - a broken store means "unknown"
        return Remembered()


def remember_reported(settings: Any, reported_model: str) -> Remembered:
    """The instrument's own report (it always wins over a choice)."""
    kind = kind_of(reported_model)
    if not kind:
        return remembered(settings)
    settings.set(SETTING, kind)
    settings.set(SETTING_NAME, str(reported_model).strip())
    settings.set(SETTING_SOURCE, "reported")
    return Remembered(kind, str(reported_model).strip(), "reported")


def remember_choice(settings: Any, kind: str) -> None:
    """The person's answer to M-DUAL-MODEL-ASK or in Preferences."""
    if kind not in (I1PRO2, OTHER):
        raise ValueError(kind)
    settings.set(SETTING, kind)
    settings.set(SETTING_NAME, "")
    settings.set(SETTING_SOURCE, "chosen")


def forget(settings: Any) -> None:
    """Preferences' "Ask again": nothing remembered."""
    for k in (SETTING, SETTING_NAME, SETTING_SOURCE):
        settings.set(k, "")


@dataclass(frozen=True)
class Decision:
    """What START assumes: *kind* "i1pro2", "other" or "ask"; *source*
    "usb", "remembered" or ""; *family* what the USB list said."""
    kind: str
    source: str = ""
    family: "str | None" = None


def resolve(settings: Any, family: "str | None") -> Decision:
    """The order of knowing (module docstring), without the question."""
    if family in (FAMILY_I1PRO3, FAMILY_OTHER):
        return Decision(OTHER, "usb", family)
    rem = remembered(settings)
    if family == FAMILY_I1PRO:
        # USB says "an i1Pro or an i1Pro 2": a remembered answer that fits
        # that family stands; one about another family (an instrument
        # changed since) does not
        if rem.kind == I1PRO2:
            return Decision(I1PRO2, "remembered", family)
        if rem.kind == OTHER and (rem.source == "chosen" or (
                rem.name and _key(rem.name) == "i1pro")):
            return Decision(OTHER, "remembered", family)
        return Decision(ASK, "", family)
    if rem.kind:
        return Decision(rem.kind, "remembered", family)
    return Decision(ASK, "", family)


def _key(name: str) -> "str | None":
    from core.measure_pace import model_key
    return model_key(name)


def differs(assumed: str, reported_model: "str | None") -> bool:
    """The instrument's report contradicts what START assumed."""
    kind = kind_of(reported_model)
    return bool(kind) and assumed in (I1PRO2, OTHER) and kind != assumed


def describe(settings: Any) -> str:
    """One line for Preferences > Beta: what ChromIQ remembers."""
    from core.i18n import tr
    rem = remembered(settings)
    if rem.kind == I1PRO2 and rem.source == "reported":
        return tr("Remembered: an i1Pro 2 (the instrument reported itself as "
                  "“{name}” at the last measurement).").format(name=rem.name)
    if rem.kind == OTHER and rem.source == "reported":
        return tr("Remembered: not an i1Pro 2 (the instrument reported "
                  "itself as “{name}” at the last measurement).").format(
                      name=rem.name)
    if rem.kind == I1PRO2:
        return tr("Remembered: an i1Pro 2 (your answer).")
    if rem.kind == OTHER:
        return tr("Remembered: another instrument, not an i1Pro 2 (your "
                  "answer).")
    return tr("Nothing remembered: ChromIQ asks before the next measurement "
              "with the dual scan, unless the USB connection already tells.")
