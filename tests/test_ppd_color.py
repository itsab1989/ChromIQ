"""Tests for the vendor "no colour management" PPD backstop in
``workflow.ppd_color`` (shared by the native macOS dialog and the ``lp`` path).

Pure PPD parsing — no PyObjC / PrintCore / CUPS — so they run on any platform.
"""
import textwrap

from workflow.ppd_color import (
    vendor_no_cm_setting as _vendor_no_cm_setting,
    vendor_no_cm_settings as _vendor_no_cm_settings,
)


def _write_ppd(tmp_path, body: str):
    p = tmp_path / "printer.ppd"
    p.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return str(p)


# Trimmed from the real installed Canon PRO-300 driver PPD (CNIJ587.ppd).  The
# only "no colour management" lever Canon exposes is value 1001 ("No Color
# Correction") on an option whose *name* is "Rendering Intent" — it has no
# "colour" in the option label, which is exactly what used to make the backstop
# miss it.
CANON_PRO300_PPD = """
    *OpenUI *CNIJMediaType/Media Type: PickOne
    *DefaultCNIJMediaType: 50
    *CNIJMediaType 50/Photo Paper Pro Platinum: ""
    *CloseUI: *CNIJMediaType
    *OpenUI *CNIJIntent2/Rendering Intent: PickOne
    *DefaultCNIJIntent2: 5
    *CNIJIntent2 5/Perceptual (Photo): ""
    *CNIJIntent2 1001/No Color Correction: ""
    *CloseUI: *CNIJIntent2
    *OpenUI *CNIJColorPatternCheckBox/View Color Pattern: PickOne
    *DefaultCNIJColorPatternCheckBox: 0
    *CNIJColorPatternCheckBox 0/OFF: ""
    *CNIJColorPatternCheckBox 1/ON: ""
    *CloseUI: *CNIJColorPatternCheckBox
"""


def test_canon_no_color_correction_on_rendering_intent(tmp_path):
    """Canon hangs its no-CM toggle off "Rendering Intent" → "No Color
    Correction"; the value alone must qualify it even though the option name
    has no "colour" in it."""
    ppd = _write_ppd(tmp_path, CANON_PRO300_PPD)
    assert _vendor_no_cm_setting(ppd) == ("CNIJIntent2", "1001")


def test_epson_cmat_still_detected(tmp_path):
    """Regression guard: the Epson path that already worked must keep working —
    "No Color Adjustment" on an "EPSON Color Controls" option."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *EPIJ_CMat/EPSON Color Controls: PickOne
        *DefaultEPIJ_CMat: 1
        *EPIJ_CMat 1/Color Controls: ""
        *EPIJ_CMat 3/No Color Adjustment: ""
        *CloseUI: *EPIJ_CMat
    """)
    assert _vendor_no_cm_setting(ppd) == ("EPIJ_CMat", "3")


def test_explicit_no_cm_value_preferred_over_generic_off(tmp_path):
    """A prio-0 explicit "no colour management" value beats a prio-1 bare
    "Off" on a colour-management option."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *ColorMatching/Color Matching: PickOne
        *DefaultColorMatching: Auto
        *ColorMatching Auto/Automatic: ""
        *ColorMatching Off/Off: ""
        *CloseUI: *ColorMatching
        *OpenUI *Intent/Rendering Intent: PickOne
        *DefaultIntent: Photo
        *Intent Photo/Perceptual: ""
        *Intent Raw/No Color Management: ""
        *CloseUI: *Intent
    """)
    assert _vendor_no_cm_setting(ppd) == ("Intent", "Raw")


def test_bare_off_on_non_cm_option_ignored(tmp_path):
    """A bare "Off" only counts on a clearly colour-management option — a
    "Duplex: Off" (or here a non-CM toggle) must not be mistaken for one."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *Duplex/Two-Sided: PickOne
        *DefaultDuplex: None
        *Duplex None/Off: ""
        *Duplex DuplexNoTumble/Long-Edge: ""
        *CloseUI: *Duplex
    """)
    assert _vendor_no_cm_setting(ppd) is None


# Trimmed from Apple's vendor driver bundles (2026-06 survey of 2 032 PPDs
# pulled from HewlettPackard/Brother/Canon/EPSON PrinterDrivers.dmg via
# pkgutil --expand-full — see scripts/survey_ppd_no_cm.py).


def test_hp_designjet_application_matching(tmp_path):
    """HP DesignJets (Z2100/Z3100/T-series) label the no-CM choice just
    "Application" (vs "Printer") on a "Color Management" option; its PS
    invocation sets RGBColorManagement to None.  From HP Designjet Z3100ps."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *HPColorMatchingMode/Color Management: PickOne
        *DefaultHPColorMatchingMode: ApplicationMatching
        *HPColorMatchingMode Vendor/Printer: ""
        *HPColorMatchingMode ApplicationMatching/Application: "/RGBColorManagement where {pop /None RGBColorManagement} if"
        *CloseUI: *HPColorMatchingMode
        *OpenUI *HPColorOptions/Mode: PickOne
        *DefaultHPColorOptions: colorsmart
        *HPColorOptions colorsmart/Color: ""
        *HPColorOptions grayscale/Grayscale: ""
        *CloseUI: *HPColorOptions
    """)
    assert _vendor_no_cm_setting(ppd) == ("HPColorMatchingMode", "ApplicationMatching")


def test_hp_deskjet_application_managed_colors(tmp_path):
    """Mobile/Deskjet HP inkjets spell it out: "Application Managed Colors"
    on the HPColorMode option.  From HP Deskjet 460."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *HPColorMode/Color: PickOne
        *DefaultHPColorMode: colorsmart
        *HPColorMode colorsmart/ColorSmart/sRGB: ""
        *HPColorMode application-managed/Application Managed Colors: ""
        *HPColorMode grayscale/Grayscale: ""
        *CloseUI: *HPColorMode
    """)
    assert _vendor_no_cm_setting(ppd) == ("HPColorMode", "application-managed")


def test_hp_laser_rgb_color_none(tmp_path):
    """HP colour lasers hang the rendering choice off "RGB Color"
    (sRGB/Vivid/Photo/Adobe RGB/None) — "None" is the raw device mode.  The
    watermark "Color" option next to it must not be mistaken for it.  From
    HP LaserJet CP 1025."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *HPwmTextColor/Color: PickOne
        *DefaultHPwmTextColor: Black
        *HPwmTextColor Black/Gray: ""
        *HPwmTextColor Red/Red: ""
        *CloseUI: *HPwmTextColor
        *OpenUI *RgbColor/RGB Color: PickOne
        *DefaultRgbColor: Default_(sRGB)
        *RgbColor Default_(sRGB)/Default (sRGB): ""
        *RgbColor Vivid/Vivid: ""
        *RgbColor Photo/Photo: ""
        *RgbColor Photo(Adobe_RGB_1998)/Photo (Adobe RGB 1998): ""
        *RgbColor None/None: ""
        *CloseUI: *RgbColor
    """)
    assert _vendor_no_cm_setting(ppd) == ("RgbColor", "None")


def test_hp_laser_per_object_rgb_options_all_returned(tmp_path):
    """HP PS colour lasers split the rendering choice into *three* sibling
    "RGB Color" options (text/graphics/photo) — all of them must be returned,
    or the unset object types stay colour-managed.  From HP Color LaserJet
    3000."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *HPTextRGB/RGB Color: PickOne
        *DefaultHPTextRGB: Default_sRGB
        *HPTextRGB Default_sRGB/Default (sRGB): ""
        *HPTextRGB None/None: ""
        *CloseUI: *HPTextRGB
        *OpenUI *HPGraphicsRGB/RGB Color: PickOne
        *DefaultHPGraphicsRGB: Default_sRGB
        *HPGraphicsRGB Default_sRGB/Default (sRGB): ""
        *HPGraphicsRGB None/None: ""
        *CloseUI: *HPGraphicsRGB
        *OpenUI *HPPhotoRGB/RGB Color: PickOne
        *DefaultHPPhotoRGB: Default_sRGB
        *HPPhotoRGB Default_sRGB/Default (sRGB): ""
        *HPPhotoRGB None/None: ""
        *CloseUI: *HPPhotoRGB
    """)
    assert _vendor_no_cm_settings(ppd) == [
        ("HPTextRGB", "None"),
        ("HPGraphicsRGB", "None"),
        ("HPPhotoRGB", "None"),
    ]


def test_samsung_rgb_color_device(tmp_path):
    """Samsung colour lasers: "RGB Color" Standard/Vivid/Device — "Device"
    invokes `userdict /RGBColorMode (DEVICE) put`, the raw device-RGB mode.
    From Samsung CLP-350."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *SECRGBColor/RGB Color: PickOne
        *DefaultSECRGBColor: Standard
        *SECRGBColor Standard/Standard: ""
        *SECRGBColor Vivid/Vivid: ""
        *SECRGBColor Device/Device: ""
        *CloseUI: *SECRGBColor
    """)
    assert _vendor_no_cm_setting(ppd) == ("SECRGBColor", "Device")


def test_lexmark_color_correction_off_on_mediacolor_key(tmp_path):
    """Lexmark reuses the key name "MediaColor" for an option *labelled*
    "Color Correction" whose Off value emits /ColorCorrection /Off — the label
    qualifies it, the key name doesn't matter.  Conversely Xerox's MediaColor
    really is "Paper Color" and must stay undetected.  From Lexmark C2100 /
    Xerox D110."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *MediaColor/Color Correction: PickOne
        *DefaultMediaColor: PrinterS
        *MediaColor PrinterS/Use Printer Setting: ""
        *MediaColor FalseM/Off: ""
        *MediaColor Auto/Auto: ""
        *CloseUI: *MediaColor
    """)
    assert _vendor_no_cm_setting(ppd) == ("MediaColor", "FalseM")
    paper = _write_ppd(tmp_path, """
        *OpenUI *MediaColor/Paper Color: PickOne
        *DefaultMediaColor: Unspecified
        *MediaColor Unspecified/Printer Default: ""
        *MediaColor White/White: ""
        *MediaColor Blue/Blue: ""
        *CloseUI: *MediaColor
    """)
    assert _vendor_no_cm_setting(paper) is None


def test_brother_inkjet_color_mode_none(tmp_path):
    """Brother inkjets: "Color Mode" with Natural/Vivid/None — "None" is the
    no-CM value.  From Brother MFC-J200."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *BRColorMatching/Color Mode: PickOne
        *DefaultBRColorMatching: Vivid
        *BRColorMatching Natural/Natural: ""
        *BRColorMatching Vivid/Vivid: ""
        *BRColorMatching None/None: ""
        *CloseUI: *BRColorMatching
    """)
    assert _vendor_no_cm_setting(ppd) == ("BRColorMatching", "None")


def test_brother_laser_color_transformation_off(tmp_path):
    """Old Brother colour lasers: "Color Transformation" On/Off — "Off" is the
    no-CM value.  From Brother HL-4000CN."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *BRColorAjst/Color Transformation: PickOne
        *DefaultBRColorAjst: CAON
        *BRColorAjst CAON/On: ""
        *BRColorAjst CAOFF/Off: ""
        *CloseUI: *BRColorAjst
    """)
    assert _vendor_no_cm_setting(ppd) == ("BRColorAjst", "CAOFF")


def test_no_colour_option_returns_none(tmp_path):
    """A PPD with nothing colour-related yields no backstop setting."""
    ppd = _write_ppd(tmp_path, """
        *OpenUI *PageSize/Page Size: PickOne
        *DefaultPageSize: A4
        *PageSize A4/A4: ""
        *CloseUI: *PageSize
    """)
    assert _vendor_no_cm_setting(ppd) is None
