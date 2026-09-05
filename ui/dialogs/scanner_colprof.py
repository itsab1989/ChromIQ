"""Scanner / camera colprof settings for the profile-build dialog (#121, Knut).

The "Build profile with scanner or camera" window exposes the most-used colprof
options directly (profile type, quality, description) and the rest behind an
**Advanced…** button. The Advanced dialog mirrors the *layout, grouping and
labels of tab "4 Build profile" → Manual* — the same QGroupBox sections
("Measurement & Smoothing", "Gamut Mapping", "Profile Metadata", "Advanced"),
the same checkbox-gated controls, and the same ``(-flag)`` label convention —
so a user who knows one knows the other. All values are remembered between runs
(stored in QSettings, so *Restore factory defaults* in Preferences clears them),
and the window shows the exact colprof command the current settings produce.

This module holds the Advanced-dialog widgets, the mapping from UI values to
:class:`~workflow.profile_builder.ProfileParams`, and the persistence keys. The
main-window controls live in ``scanin_dialog.py`` next to the profile-type row.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                             QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QScrollArea, QVBoxLayout, QWidget)

from core.i18n import tr
from ui.styles import SPEC_GREEN
from ui.tooltip_button import TooltipButton
from ui.widgets import (NoScrollDoubleSpinBox, ValueWidthComboBox,
                        make_browse_button, open_file_dialog)

# QSettings prefix for the remembered scanner colprof configuration.
SETTINGS_PREFIX = "scanner_colprof"

# Main-window profile type = colprof's -a algorithm directly (data = the -a
# letter). The XYZ vs Lab distinction is how a cLUT stores colour internally, so
# it belongs to the profile type, not a separate "colour space" control — a
# scanner/camera *input* profile has no working-space or rendering-intent choice
# (those are output/printer-profile concepts). (Knut, #121)
PTYPE_CHOICES = [
    ("s", tr("Shaper + matrix")),
    ("m", tr("Matrix only")),
    ("x", tr("cLUT — XYZ table")),
    ("l", tr("cLUT — Lab table")),
]
# Which -a letter is the factory default per mode: a scanner/camera INPUT
# profile is best as shaper+matrix; a printer OUTPUT profile is best as a Lab
# cLUT (Basti/Knut, #121). The main window marks whichever applies "(default)".
PTYPE_DEFAULT = {False: "s", True: "l"}      # keyed by printer-mode
QUALITY_CHOICES = [
    ("l", tr("Low")), ("m", tr("Medium")), ("h", tr("High")), ("u", tr("Ultra")),
]
CLUT_ALGOS = ("x", "l")            # the -a letters for which -q quality applies

# Of the two cLUTs, the one ChromIQ recommends — keyed by printer-mode, exactly
# like PTYPE_DEFAULT above, because the recommendation is NOT the same on both
# sides of this window and a single answer would make it contradict itself.
#
# SCANNER / CAMERA (False) -> "x". Measured (B8-19, AGENT-AD, two real scans,
# every figure scored on patches the fit never saw): on the colours a target
# contains the two tables land close together with neither consistently ahead,
# but a Lab cLUT cannot encode anything above its chart's white — a neutral ramp
# through it reads L* 100.4 flat from device 82 upward, where the XYZ table and
# shaper+matrix both run on to L* ~119.5. An IT8's own white is only ~80 of 100
# on a real scan, so that ceiling sits inside the range a scanner uses daily.
# ArgyllCMS says the same in colprof.html, and says it of INPUT devices.
#
# PRINTER (True) -> None, deliberately. The clipping argument is about capturing
# something lighter than the chart's white, and nothing a printer prints is
# lighter than the paper it prints on; Argyll's own default for an output
# profile is -al ("the most robust and accurate results", and the only kind that
# carries the perceptual and saturation intents), which is what PTYPE_DEFAULT
# already selects and what the "(default)" marker already says. Nothing was
# measured about printer profiles here, so nothing is claimed about them.
PTYPE_RECOMMENDED_CLUT: dict[bool, "str | None"] = {False: "x", True: None}

#: Where the live profile-type note switches sides. Both are round numbers just
#: outside the measured crossover (~100 fit patches), so a note only ever fires
#: where the measurement is unambiguous and never in the shallow middle.
PTYPE_BIG_TARGET = 200        # at 192 fit patches: cLUT-XYZ 0.69 vs shaper 1.07
PTYPE_SMALL_TARGET = 100      # at 48: shaper 1.25 vs 1.68 / 1.68 for the cLUTs


# Gamut-source mode (colprof -s / -S). Same three choices, wording and order as
# tab 4's Manual module so the two windows read identically.
GAMUT_SOURCE_CHOICES = [
    ("", tr("None (colprof default)")),
    ("s", tr("Perceptual only (-s)")),
    ("S", tr("Perceptual + Saturation (-S)  ← recommended")),
]
# Rendering-intent overrides for -t / -T — identical list to tab 4's Manual
# module (labels shared, so translations are reused, not duplicated).
INTENT_CHOICES = [
    ("", tr("Default")),
    ("p", tr("Perceptual Preferred (p)")),
    ("pa", tr("Perceptual Appearance (pa)")),
    ("lp", tr("Luminance Preserving Perceptual (lp)")),
    ("r", tr("Relative Colorimetric / ICC (r)")),
    ("rl", tr("Lab White-point Matched (rl)")),
    ("ms", tr("Saturation (ms)")),
    ("s", tr("Enhanced Saturation / ICC (s)")),
    ("a", tr("Absolute Colorimetric (a)")),
    ("aw", tr("Absolute + white scaling (aw)")),
    ("aa", tr("Absolute Appearance (aa)")),
    ("al", tr("Lab Colorimetric (al)")),
]
B2A_CHOICES = [
    ("l", tr("Low")), ("m", tr("Medium")), ("h", tr("High")),
    ("u", tr("Ultra")), ("n", tr("None (skip B2A)")),
]
# White-point handling for a scanner/camera INPUT profile — the colprof -u family
# (#121, Knut). Data values map to ProfileParams.wp_mode.
WP_MODE_CHOICES = [
    ("", tr("Map chart white to white (default)")),
    ("u", tr("Auto-scale to avoid clipping (-u)")),
    ("ua", tr("Force Absolute Colorimetric (-ua)")),
    ("uc", tr("Clip highlights above white (-uc)")),
    ("scale", tr("Manual white-point scale (-u scale)")),
]


# ----------------------------------------------------------------------------
# The Profile type / Quality help, and the live note that goes in front of it
# ----------------------------------------------------------------------------
# B8-19. The shipped help said the two cLUTs were interchangeable and that Lab
# "sometimes gives slightly smoother neutrals" — a claim nothing measured, and
# the reason this text was rewritten. Everything asserted below is a held-out
# measurement from `beta 8/24-scanner-profile-default/` or a quotation from
# ArgyllCMS's own colprof.html; where the measurements say a difference is small
# the text says it is small, and where nothing was measured nothing is said.
#
# The help is MODE-AWARE because the advice is: a scanner/camera input profile
# and a printer output profile want different types, the window already marks
# different defaults for the two, and one text covering both would have to
# contradict one of those markers.

def ptype_help(printer: bool) -> "tuple[str, str]":
    """The ⓘ title and body for the Profile type / Quality row.

    *printer* is the state of "Profile my printer from this scan", i.e. the same
    key `PTYPE_DEFAULT` and `PTYPE_RECOMMENDED_CLUT` are keyed by, so the three
    can never drift apart.
    """
    title = tr("Profile type and quality")
    quality = tr(
        "Quality (-q) — the look-up table's grid resolution: higher is finer "
        "but slower, and needs better data to be worth it. It applies only to "
        "the two cLUT types and is greyed out for the other two. Medium is a "
        "good default, Low is a quick test, and High and Ultra are for large, "
        "clean charts.")
    if printer:
        return title, "\n\n".join((
            tr("How the printer profile models colour."),
            tr("“Profile my printer from this scan” is ticked, so this window "
               "is building a PRINTER profile: your scanner is the measuring "
               "instrument, and the chart it reads is the one you printed. "
               "That changes what to choose here, so this is not the same "
               "advice you get for a scanner or camera profile."),
            tr("Profile type (-a) — the shape of the maths inside the "
               "profile, and how it describes what your printer does with "
               "colour. All four choices build a working profile."),
            tr("• cLUT — Lab table — the default here, and what a printer "
               "profile should normally be. “cLUT” means a look-up table: "
               "instead of reducing your printer to a formula, the profile "
               "stores your measurements and interpolates between them. It "
               "also carries something the formula types cannot — the "
               "perceptual and saturation rendering intents, which are what "
               "decide how colours your printer cannot reach are eased inwards "
               "when you print a photograph. Everything under Advanced… ▸ "
               "Gamut Mapping describes those two intents, so it has nothing "
               "to act on unless the profile is a table. “Lab” is simply the "
               "internal form the table keeps colour in; it is ArgyllCMS's own "
               "default for this job, and it is what ChromIQ's Build Profile "
               "tab builds as well."),
            tr("• cLUT — XYZ table — the same kind of table, keeping colour in "
               "the other internal form. It is worth knowing why this window "
               "points at the XYZ table on the scanner side and not here. A "
               "Lab table cannot describe anything lighter than the white "
               "patch of the chart it was built from, and a scanner meets "
               "paper brighter than a scanning target's white board all the "
               "time. A printer never does — nothing it prints is lighter than "
               "the paper it prints on — so that reason does not apply here, "
               "and the Lab default stands."),
            tr("• Shaper + matrix, and Matrix only — a formula instead of a "
               "table: one gentle tone curve per colour channel plus a 3×3 "
               "matrix, which is a fixed recipe for mixing red, green and blue "
               "into a finished colour, or that mix on its own. They are small "
               "and undemanding, and they are offered here because this one "
               "control also serves the scanner side of the window. For a "
               "printer they have a real drawback: by the way the ICC format "
               "works, a matrix-based profile cannot carry a perceptual or a "
               "saturation intent at all, so it has nothing to fall back on "
               "when a colour is out of the printer's reach. Leave them be "
               "unless you know you want one."),
            quality,
            tr("Untick “Profile my printer from this scan” and this control "
               "goes back to building a scanner or camera profile, where the "
               "default is “Shaper + matrix” and the advice is different — "
               "open this ⓘ again and it will tell you that story instead. "
               "Either way you won't find a working space (like sRGB) or a "
               "rendering intent in this row: the working space the gamut "
               "mapping uses is under Advanced… ▸ Gamut Mapping, and a "
               "rendering intent is something you choose when you print, not "
               "when you build a profile from measurements."),
        ))
    return title, "\n\n".join((
        tr("How the scanner or camera profile models colour."),
        tr("Profile type (-a) — the shape of the maths inside the profile, and "
           "how it describes what your device does with colour. All four "
           "choices build a working profile. What separates them is how many "
           "measured patches they need before they are any good, and how they "
           "behave on colours your target did not contain."),
        tr("That makes the size of your target the first thing to look at, and "
           "you do not have to count anything: the patch count is printed "
           "beside each target's name in the list above, and again in the "
           "green “✓ … patches” line once a target or a chart is loaded."),
        tr("• Shaper + matrix — the default here, and a small, sturdy profile: "
           "one gentle tone curve for each of red, green and blue, plus a 3×3 "
           "matrix, which is a fixed recipe for mixing those three into a "
           "finished colour. It is a formula rather than a stored table, so it "
           "needs very little data to work well, and it carries on sensibly "
           "beyond the lightest and darkest patch your target contains. Take "
           "it for targets up to about a hundred patches — a ColorChecker (24 "
           "patches), a SpyderChecker (48), a QPcard (49) — and whenever a "
           "scan is noisy or you would rather not think about it. On real "
           "scanned targets it was the most accurate of the four at 24 and at "
           "48 patches."),
        tr("• cLUT — XYZ table — “cLUT” means a look-up table. Instead of a "
           "formula, the profile stores your measurements and interpolates "
           "between them, so it can follow a device that does not behave like "
           "tidy maths. That freedom has to be paid for in patches: with too "
           "few of them there is nothing much to interpolate between, and the "
           "table will happily fit the noise in a scan rather than the colour. "
           "Take it when your target has roughly two hundred patches or more — "
           "a full IT8 has 288, a three-page ISO 12641-2 set has 864 — and the "
           "scan is clean and correctly exposed. At that size it measured "
           "about a third more accurate than Shaper + matrix on a real IT8 "
           "scan. “XYZ” is simply the internal form the table keeps colour in, "
           "and it is the one to use here — the next entry says why."),
        tr("• cLUT — Lab table — the same kind of look-up table, keeping "
           "colour in a different internal form. On the colours your target "
           "actually contains, the two tables measured close together, with "
           "neither of them consistently ahead of the other. The difference is "
           "at the top end. A Lab table cannot describe anything lighter than "
           "your target's own white patch — and a target's white board is not "
           "very white: on a real IT8 scan it reached only about 80 out of the "
           "scanner's 100. So everything brighter than that, which includes "
           "most bright photo paper, arrives at exactly the lightness of the "
           "target's white patch, with the differences between those tones "
           "flattened away. Shaper + matrix and the XYZ table both keep going "
           "past it. That is the whole reason the XYZ table is the one to take "
           "if you want a table profile. If you would rather stay with Lab, "
           "set Advanced… ▸ White point handling to “Auto-scale to avoid "
           "clipping (-u)”, which lifts the ceiling."),
        tr("• Matrix only — the 3×3 mix and nothing else, with no tone curves "
           "in front of it. It suits a device that is already perfectly "
           "linear, such as a camera shooting RAW. On an ordinary scanner it "
           "measured several times less accurate than any of the other three "
           "at every size tested, so it is not the one to reach for here."),
        tr("Right around a hundred patches the first three land within a "
           "whisker of one another and the choice barely matters; it is above "
           "and below that the difference shows. And whichever you pick, "
           "changing the paper or the target you scan moves the result a great "
           "deal further than the profile type does."),
        quality,
        tr("If you tick “Profile my printer from this scan”, this same control "
           "builds the printer profile instead — a different kind of device, "
           "with different advice. The type then defaults to “cLUT — Lab "
           "table”; open this ⓘ again with the box ticked and it will explain "
           "why. Either way you won't find a working space (like sRGB) or a "
           "rendering intent here; a rendering intent is something you choose "
           "when you print, not when you build a profile from measurements."),
        tr("None of the recommendations above is received wisdom. Profiles "
           "were built from part of two real scanned targets and then scored "
           "only on the patches the fit had never seen, which is the only way "
           "the numbers mean anything — a profile marked against its own "
           "measurements flatters a look-up table badly."),
    ))


def ptype_advice(printer: bool, ptype: str, n_patches: "int | None") -> str:
    """A live note for the Profile type ⓘ, or ``""`` when there is nothing to say.

    It is a SUGGESTION and never an instruction: it changes no setting, it lives
    inside the ⓘ (only its first line reaches the hover tooltip), and it goes
    away by itself as soon as it stops being true.

    Three rules, and all three require a KNOWN patch count — the window learns
    that only once a target or chart is loaded, and a note about a size nobody
    has chosen yet would be noise. Nothing is said in printer mode: B8-19
    measured input profiles, and an unmeasured nudge is the fault this text was
    written to remove.
    """
    if printer or not n_patches or n_patches < 2:
        return ""
    if ptype in CLUT_ALGOS and n_patches < PTYPE_SMALL_TARGET:
        return tr(
            "A note on the profile type: your target has {n} patches, which is "
            "on the small side for a look-up table.\n\n"
            "Below about a hundred patches, “Shaper + matrix” measured more "
            "accurate than either cLUT on real scanned targets — a table needs "
            "plenty of well-spread patches before it has anything to "
            "interpolate between, and with fewer it starts fitting the noise "
            "in the scan. Your choice stands; this is only a suggestion, and "
            "nothing here has been changed for you."
        ).format(n=n_patches)
    if ptype == "l":
        return tr(
            "A note on the profile type: “cLUT — Lab table” cannot describe "
            "anything lighter than your target's own white patch.\n\n"
            "A scanning target's white board is not very white — on a real IT8 "
            "scan it reached only about 80 out of the scanner's 100 — so "
            "everything brighter, which includes most bright photo paper, "
            "comes out at exactly the lightness of that white patch with the "
            "differences between those tones flattened away. “cLUT — XYZ "
            "table” is the same kind of table without that ceiling, and it "
            "measured just as accurate on the colours your target does "
            "contain. If you would rather stay with Lab, Advanced… ▸ White "
            "point handling ▸ “Auto-scale to avoid clipping (-u)” lifts the "
            "ceiling. Your choice stands either way.")
    if ptype == "s" and n_patches >= PTYPE_BIG_TARGET:
        return tr(
            "A note on the profile type: your target has {n} patches, which is "
            "big enough for a look-up table to be worth it.\n\n"
            "Above about a hundred patches, a cLUT measured about a third more "
            "accurate than “Shaper + matrix” on real scanned targets, and "
            "“cLUT — XYZ table” is the one to take. “Shaper + matrix” is still "
            "a perfectly good, safe profile and it will not clip your "
            "highlights — this is a suggestion, not a warning, and nothing has "
            "been changed for you."
        ).format(n=n_patches)
    return ""

# Shared tooltip bodies — copied verbatim from tab 4's Manual module so the two
# windows explain each option in exactly the same words (and share translations).
_TIP_GAMUT = (
    "When printing, colours that fall outside your printer's range must "
    "be compressed to fit. This setting tells ChromIQ which colour "
    "space your images live in, so the compression is tuned to that "
    "space and looks natural in prints.\n\n"
    "None — colprof uses a large internal default. Works, but the "
    "perceptual intent is not optimised for any real working space.\n\n"
    "Perceptual only (-s) — applies the source gamut to the perceptual "
    "rendering intent only.\n\n"
    "Perceptual + Saturation (-S, recommended) — applies it to both "
    "intents. Use this unless you have a specific reason to treat them "
    "differently.\n\n"
    "Which source profile to point at:\n\n"
    "• ClayRGB1998.icm (the default) — this is Argyll's bit-for-bit "
    "AdobeRGB 1998 equivalent. The rename is a trademark workaround; "
    "Adobe doesn't license the \"AdobeRGB1998.icc\" name for "
    "redistribution, so Argyll ships the same profile under a different "
    "name. AdobeRGB is the right default for most photographic "
    "workflows — Lightroom, Photoshop, Capture One, and most pro RAW "
    "converters all default to AdobeRGB (or a wider space like "
    "ProPhoto). An AdobeRGB source profile also handles sRGB-tagged "
    "images correctly, since sRGB fits entirely inside AdobeRGB.\n\n"
    "• sRGB.icm — pick this if your source images are sRGB-tagged "
    "(web exports, smartphone JPEGs, most consumer images). It's a "
    "smaller working space, so the perceptual mapping is slightly "
    "tighter for sRGB sources than the AdobeRGB-sourced profile would "
    "be.\n\n"
    "• ProPhoto.icm or a wider space — only if you specifically edit "
    "in ProPhoto. The wider the source space, the more compression "
    "the perceptual intent has to do, which can desaturate colours "
    "that would have printed fine.\n\n"
    "Browse to the file in Argyll's ref folder, or use any standard "
    "RGB working-space ICC profile you have installed.")
_TIP_PERC_INTENT = (
    "The perceptual rendering intent is what most photo printing uses: colours "
    "your printer can't reproduce are gently eased inwards so the whole picture "
    "still looks natural, rather than a few colours being clipped harshly. This "
    "lets you swap in a different recipe for doing that easing.\n\n"
    "Leave it unchecked to use ChromIQ's built-in perceptual mapping — it's "
    "well-tuned for photographs and right for almost everyone. Tick it only if "
    "you want to experiment: the named recipes trade off how strongly colours "
    "are pulled in against how faithfully lightness and hue are kept, and the "
    "differences are usually subtle.")
_TIP_SAT_INTENT = (
    "The saturation rendering intent is meant for charts, business graphics and "
    "bold artwork, where vivid, punchy colour matters more than an exact match. "
    "This lets you choose a different recipe for it.\n\n"
    "Leave it unchecked unless you mainly print graphics and want to fine-tune "
    "how vivid colours are handled. For photographic and fine-art printing you "
    "can safely ignore this.")
_TIP_B2A = (
    "A profile holds tables that run in two directions. The “forward” tables "
    "(set by the main Quality) describe what colour each ink combination "
    "produces. The “back” tables — set here — do the reverse: they work out "
    "which ink numbers to send to get a colour you asked for, and are used "
    "whenever you print with the perceptual or saturation intent, or soft-proof "
    "on screen.\n\n"
    "Leave this unchecked to keep the back tables at the same quality as the "
    "main setting — normally what you want. Tick it and pick a lower quality to "
    "build faster and make a smaller profile if you mostly use colorimetric "
    "intents, or “None” to leave the back tables out of a measurement-only "
    "profile.")
_TIP_SMOOTH = (
    "Measuring the same patch twice never gives exactly the same reading — there "
    "is always a little noise. This tells ChromIQ how much to trust the overall "
    "trend versus each individual reading, smoothing the profile so a few noisy "
    "patches don't turn into bumps.\n\n"
    "The value is a percentage of ΔE (a standard measure of how different two "
    "colours look):\n"
    "• 0.5 % — clean, repeatable readings from a well-behaved instrument (the "
    "default).\n"
    "• 1–2 % — noisier measurements: textured or matte papers, or a camera "
    "shot.\n"
    "• 3–5 % — very noisy; smooths hard, which can blur genuine fine detail.\n\n"
    "Leave it at 0.5 % unless your measurements are visibly noisy.")
_TIP_DARK = (
    "Printers and papers are least predictable in their darkest tones, where a "
    "lot of ink piles up. This packs more of the profile's internal detail into "
    "the shadows so deep tones are described more accurately — at the cost of a "
    "little precision in the lighter tones.\n\n"
    "• 1.0 — spread evenly, no special emphasis (the default).\n"
    "• 1.5–2.0 — a good choice for glossy or baryta papers with deep, rich "
    "blacks.\n"
    "• up to 4.0 — strong shadow emphasis.\n\n"
    "This only affects look-up-table (cLUT) profile types. Leave it at 1.0 "
    "unless you see problems in the shadows.")
_TIP_MFR = (
    "Manufacturer name embedded in the ICC profile header — for example "
    "“Epson” or “Canon”. Optional metadata only: colour-managed apps may show "
    "it, but it doesn't change how the profile converts colour.")
_TIP_MODEL = (
    "Model name embedded in the ICC profile header — for example “SC-P900” or "
    "“PRO-300”. Optional metadata only; it doesn't change the colour conversion.")
_TIP_COPY = (
    "Copyright notice embedded in the ICC profile, e.g. “© 2026 Your Studio”. "
    "Metadata only — it doesn't affect the colour conversion.")
_TIP_NI = (
    "Before the main colour table, colprof normally fits a set of gentle "
    "per-channel curves that even out the device's tone response, so the table "
    "has a well-spread range of values to work with. They almost always improve "
    "accuracy.\n\n"
    "Leave this unchecked for normal profiling. Tick it only to force a plainer "
    "model — handy for troubleshooting, or for a device you already know behaves "
    "in a straight, linear way.")
_TIP_NO = (
    "After the main colour table, colprof normally fits a second set of "
    "per-channel curves that fine-tune the final values and keep the highlights "
    "and shadows smooth. They almost always improve the result.\n\n"
    "Leave this unchecked for normal profiling. Tick it only to force a plainer "
    "model when troubleshooting.")
_TIP_NP = (
    "The colour table is a grid of sample points. Normally colprof places those "
    "points cleverly, putting more of them where colours change quickly and "
    "accuracy matters most. This forces an evenly-spaced grid instead.\n\n"
    "This is an advanced troubleshooting option — leave it unchecked for normal "
    "profiling.")
_TIP_NC = (
    "By default colprof tucks a copy of the .ti3 measurements inside the "
    "finished ICC profile. Keeping them with the profile is handy if you ever "
    "want to rebuild or audit it later, and only makes the file a little "
    "larger.\n\n"
    "Tick this to leave the measurement data out and produce a smaller profile. "
    "Most people can leave it unchecked.")
_TIP_WP = (
    "A scanner or camera profile normally maps the white patch of your test "
    "chart to perfect white. That's usually what you want — but if you later "
    "scan or photograph something lighter than the chart's white (a brighter "
    "paper, or a slightly under-exposed chart), a look-up-table profile has to "
    "clip those brighter values. These options change how that white is "
    "handled.\n\n"
    "• Map chart white to white — the standard behaviour; leave it here for "
    "normal IT8 / ColorChecker profiling.\n"
    "• Auto-scale to avoid clipping (-u) — automatically scales the media white "
    "point so brighter-than-chart values aren't clipped, while still correcting "
    "the hue. Handy when the chart white doesn't match the media you'll "
    "actually use.\n"
    "• Force Absolute Colorimetric (-ua) — tags the profile with a fixed D50 "
    "white so it acts as an absolute colorimeter — useful when you're using the "
    "scanner as a simple measuring device. It keeps colours brighter than the "
    "chart white but doesn't hue-correct white.\n"
    "• Clip highlights above white (-uc) — forces anything brighter than the "
    "white point to land exactly on white. Only affects look-up-table (cLUT) "
    "profile types.\n"
    "• Manual white-point scale (-u scale) — this is “Auto-scale” above with "
    "your own number applied on top of it, not a scale on its own. A value of "
    "1.00 is therefore the same thing as “Auto-scale to avoid clipping”, not "
    "“no change”; see the box below.\n\n"
    "Leave it on the first option unless you have a specific white-point "
    "mismatch to fix. Only applies to a scanner/camera input profile.")
# THE SENTENCE THIS REPLACED WAS FALSE, AND IT COST A TESTER A PROFILE.
# It said "1.00 makes no change", and Knut reasonably built a profile on that.
# In ArgyllCMS `colprof.c:494` sets `autowpsc = 1` BEFORE it ever reads the
# number, and `xfit.c:2753` makes the default scale 1.0 anyway, so `-u 1` is
# byte-for-byte `-u`. Built both from his own scan to be sure: identical wtpt
# (1.591736 1.624054 1.343185). The worked example was inverted too — the text
# offered 0.90 as the way to keep a slightly darker white white, and 0.90
# measures a white point of Y 1.461655, a scan about 44 % darker.
_TIP_WP_SCALE = (
    "The number that “Manual white-point scale” above uses — and it is applied "
    "ON TOP OF that option's automatic scaling, not instead of it.\n\n"
    "So 1.00 does not mean “no change”. It means “the automatic scaling, "
    "unaltered”, which makes it identical to “Auto-scale to avoid clipping” "
    "— measured on a real IT8 scan, the two build the same profile. If what "
    "you want is to leave the white alone, that is the FIRST entry in the list "
    "above, “Map chart white to white”, not a scale of 1.00.\n\n"
    "Numbers below 1.00 reduce the automatic scaling without undoing it. On "
    "that same scan, 0.90 still left the white point at about 1.46 instead of "
    "1.00, and every tone in the scan about 44 % darker than the default. "
    "Numbers above 1.00 scale further still.\n\n"
    "Reach for this only when you already know the factor you want. Its one "
    "everyday use is with “Restrict white, black and primaries” ticked "
    "alongside it, which brings the white point back to a perfect white "
    "surface — nothing a reflective original can be is then clipped.\n\n"
    "This box only has an effect when the handling above is set to “Manual "
    "white-point scale”.")
_TIP_R = (
    "Keeps the profile physically sensible by holding white to no brighter than "
    "full white, and forcing black and the pure primary colours to stay "
    "positive (never negative). This can tidy up a profile built from noisy or "
    "slightly out-of-range measurements.\n\n"
    "Leave it unchecked for normal profiling; tick it only if a profile misbehaves "
    "near white, black or the pure primaries.")


# Keys of the values dict this module round-trips. Resolved colprof flags
# (-s/-S/-t/-T/-b/-A/-M/-C) are what make_profile_params reads; the *_on / *_val
# / gamut_* keys preserve the exact UI state so the dialog reopens unchanged.
MAIN_KEYS = ("ptype", "quality")

# The gamut source a printer profile starts from by default: Argyll's AdobeRGB
# 1998 equivalent, applied to BOTH intents (-S). AdobeRGB is the right default
# for most photographic workflows and also handles sRGB images correctly
# (Basti, #121). Preselected whenever the user hasn't touched the gamut choice.
DEFAULT_GAMUT_FILE = "ClayRGB1998.icm"
DEFAULT_GAMUT_MODE = "S"

# adv-value keys that only apply to a printer OUTPUT profile — stripped before a
# scanner/camera INPUT build so a leftover printer choice can't contaminate it.
OUTPUT_ONLY_KEYS = ("-s", "-S", "-t", "-T", "-b", "gamut_mode", "gamut_path",
                    "perc_on", "perc_val", "sat_on", "sat_val", "b2a_on", "b2a_q")
# …and the reverse: white-point handling only applies to a scanner INPUT profile.
INPUT_ONLY_KEYS = ("wp_mode", "wp_scale")


def default_gamut_path(ref_dir) -> str:
    """Absolute path to the bundled default gamut source (ClayRGB1998.icm) in
    Argyll's ref/ folder, or "" when it can't be found."""
    if ref_dir:
        p = Path(ref_dir) / DEFAULT_GAMUT_FILE
        if p.is_file():
            return str(p)
    return ""


def effective_adv_vals(adv_vals: dict[str, Any], printer: bool, ref_dir) -> dict[str, Any]:
    """The advanced values actually handed to colprof for the current mode.

    Printer mode preselects ClayRGB1998 as the gamut source when the user hasn't
    touched the choice (so the command preview and build show it without opening
    Advanced). Scanner mode strips every printer-output-only option so a leftover
    printer choice can't leak into an input profile (Basti, #121)."""
    v = dict(adv_vals)
    if printer:
        if "gamut_mode" not in v and not v.get("-s") and not v.get("-S"):
            clay = default_gamut_path(ref_dir)
            if clay:
                v["gamut_mode"] = DEFAULT_GAMUT_MODE
                v["gamut_path"] = clay
                v["-S"] = clay
        for k in INPUT_ONLY_KEYS:          # white-point handling is scanner-only
            v.pop(k, None)
    else:
        for k in OUTPUT_ONLY_KEYS:
            v.pop(k, None)
    return v


def make_profile_params(ti3, description: str, main_vals: dict[str, Any],
                        adv_vals: dict[str, Any]):
    """Build the :class:`ProfileParams` colprof runs from the UI's main +
    advanced values. Used both for the real build and the command preview, so
    the preview shown is exactly what runs."""
    from workflow.profile_builder import ProfileParams
    algo = main_vals.get("ptype", "s")          # ptype data IS the colprof -a letter
    try:
        smoothing = float(adv_vals.get("-r", 0.5))
    except (TypeError, ValueError):
        smoothing = 0.5
    try:
        dark_emphasis = float(adv_vals.get("-V", 1.0))
    except (TypeError, ValueError):
        dark_emphasis = 1.0
    try:
        _wp_scale = float(adv_vals.get("wp_scale", 1.0))
    except (TypeError, ValueError):
        _wp_scale = 1.0
    return ProfileParams(
        ti3_path=ti3, algorithm=algo, quality=main_vals.get("quality", "m"),
        description=description,
        model=str(adv_vals.get("-M", "") or "") or description,
        manufacturer=str(adv_vals.get("-A", "") or ""),
        copyright=str(adv_vals.get("-C", "") or ""),
        smoothing=smoothing,
        no_input_shaper=bool(adv_vals.get("-ni", False)),
        # Printer-output options (applied when they've been set). The gamut source
        # arrives already resolved to an .icc path under -s / -S from the dialog.
        b2a_quality=str(adv_vals.get("-b", "") or ""),
        gamut_src=str(adv_vals.get("-s", "") or ""),
        gamut_sat_src=str(adv_vals.get("-S", "") or ""),
        perc_intent=str(adv_vals.get("-t", "") or ""),
        sat_intent=str(adv_vals.get("-T", "") or ""),
        no_output_shaper=bool(adv_vals.get("-no", False)),
        no_grid_pos=bool(adv_vals.get("-np", False)),
        no_embedded_data=bool(adv_vals.get("-nc", False)),
        # Input-profile white-point handling (scanner path) + primary clamp.
        wp_mode=str(adv_vals.get("wp_mode", "") or ""),
        wp_scale=_wp_scale,
        clip_primaries=bool(adv_vals.get("-R", False)),
        dark_emphasis=dark_emphasis,
        verbose=True)


def _option_combo(parent: QWidget) -> ValueWidthComboBox:
    """An option combo for this panel: sized by the value it is SHOWING.

    Not by its longest entry, because this panel lives inside the scanner
    window's FIXED-width left pane and "Map chart white to perfect white" is
    410 px in Russian — one entry nobody has chosen would otherwise set how far
    the pane has to grow the moment Advanced is opened.

    And not by a character count either. That was tried here (eighteen
    characters, `AdjustToMinimumContentsLengthWithIcon`) and it cut the value
    the user was looking at in eleven of the thirteen catalogues — in Russian
    and Italian the combo's own DEFAULT, chopped mid-word with no ellipsis, so
    the window was wrong the moment it opened. Eighteen characters is a guess
    made in English about a string that is a third longer in Russian; the width
    of the actual string is not a guess.

    :class:`ValueWidthComboBox` therefore reserves what the value on screen
    needs, holds that minimum at the value the combo opened with so a later
    choice can never widen the window, and elides anything longer with an
    ellipsis and the full text in its tooltip. The drop-down always lists every
    entry in full.
    """
    return ValueWidthComboBox(parent)


def _option_rows(g: QVBoxLayout, leader: QWidget, combo: ValueWidthComboBox,
                 tip: QWidget) -> None:
    """Lay an option out as TWO lines: its name and ⓘ, then the control.

    All five of these rows are a name that is a phrase and a value that is a
    phrase — "Saturation Intent Override (-T):" against "Luminance Preserving
    Perceptual (lp)". Side by side inside the scanner window's fixed left pane
    they cannot both be read: the name takes its width first, and whatever is
    left is what the value gets, which in Polish is 253 px for a value needing
    378. The panel is ~600 px wide, so the control on its own line has room for
    the longest entry of any catalogue with a hundred pixels to spare.

    It costs a line of height per option and nothing at all in width — the row
    is now as wide as its widest HALF instead of the sum of both, so the panel
    (and with it the window's floor) gets narrower, not wider. The gamut-source
    path field directly below already sits on its own line this way, which is
    where the shape comes from.
    """
    head = QHBoxLayout()
    head.addWidget(leader, stretch=1)
    head.addWidget(tip)
    g.addLayout(head)
    g.addLayout(_indented(combo, leader.parentWidget()))


def _indented(w: QWidget, parent: QWidget | None) -> QHBoxLayout:
    """*w* on its own line, under the name it belongs to."""
    row = QHBoxLayout()
    sp = QLabel("", parent)
    sp.setObjectName("form_label_spacer")
    row.addWidget(sp)
    row.addWidget(w, stretch=1)
    return row


def _green_tip(title: str, body: str, parent: QWidget, min_width: int = 460) -> TooltipButton:
    """A ⓘ button in the scanner window's green accent (Parameter/TooltipButton
    default to the app's magenta accent)."""
    return TooltipButton(tr(title), tr(body), parent, min_width=min_width,
                         color=SPEC_GREEN)


def _i18n_tooltip_anchors():
    """Never called — it exists so the i18n extractor sees each tooltip-body
    constant as a ``tr(NAME)`` key. ``_green_tip`` applies ``tr()`` to a
    *parameter*, which the literal-only extractor can't follow, so the bodies
    that don't happen to also appear verbatim in another module would otherwise
    slip past CI untranslated. Keep this in sync with the constants above."""
    return (tr(_TIP_GAMUT), tr(_TIP_PERC_INTENT), tr(_TIP_SAT_INTENT),
            tr(_TIP_B2A), tr(_TIP_SMOOTH), tr(_TIP_DARK), tr(_TIP_MFR),
            tr(_TIP_MODEL), tr(_TIP_COPY), tr(_TIP_NI), tr(_TIP_NO),
            tr(_TIP_NP), tr(_TIP_NC), tr(_TIP_WP), tr(_TIP_WP_SCALE), tr(_TIP_R),
            # tip TITLES unique to this module (not shared with tab 4's literals):
            tr("White Point Handling (-u / -ua / -uc)"),
            tr("Manual White-point Scale (-u scale)"),
            tr("Restrict White, Black & Primaries (-R)"))


class ScannerAdvancedDialog(QDialog):
    """Modal Advanced-settings editor. Mirrors tab 4 → Manual: grouped
    QGroupBox sections with checkbox-gated controls and identical labels. The
    set is MODE-AWARE — a scanner/camera *input* profile and a printer *output*
    profile expose different applicable options (Knut, #121)."""

    def __init__(self, values: dict[str, Any], parent: QWidget | None = None,
                 printer: bool = False, ref_dir=None) -> None:
        super().__init__(parent)
        self._printer = printer
        self._ref_dir = ref_dir
        self.setWindowTitle(tr("Advanced printer-profile settings") if printer
                            else tr("Advanced profile settings"))
        self.setMinimumWidth(640)
        outer = QVBoxLayout(self)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        from PyQt6.QtCore import Qt
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        v = QVBoxLayout(body)
        v.setSpacing(10)

        self._wp_mode = None                       # scanner-only; None in printer mode
        self._build_measurement_group(v, printer)
        if printer:
            self._build_gamut_group(v)
        else:
            self._build_whitepoint_group(v)        # input-profile white-point handling
        self._build_metadata_group(v, printer)
        self._build_advanced_group(v, printer)
        v.addStretch(1)

        self._seed(values)

        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        bb = QDialogButtonBox(self)
        self._restore_btn = bb.addButton(tr("Restore defaults"),
                                         QDialogButtonBox.ButtonRole.ResetRole)
        bb.addButton(QDialogButtonBox.StandardButton.Ok)
        bb.addButton(QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self._restore_btn.clicked.connect(self.restore_defaults)
        outer.addWidget(bb)

    # ------------------------------------------------------------------ groups
    def _build_measurement_group(self, layout: QVBoxLayout, printer: bool) -> None:
        grp = QGroupBox(tr("Measurement && Smoothing"), self)
        g = QVBoxLayout(grp)
        g.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Smoothing / Noise (-r):"), grp))
        self._smooth = NoScrollDoubleSpinBox(grp)
        self._smooth.setRange(0.0, 5.0)
        self._smooth.setSingleStep(0.1)
        self._smooth.setDecimals(2)
        self._smooth.setValue(0.5)
        row.addWidget(self._smooth)
        row.addStretch()
        row.addWidget(_green_tip("Measurement Noise (-r)", _TIP_SMOOTH, grp))
        g.addLayout(row)

        # Dark-region emphasis applies to any cLUT profile (scanner or printer);
        # it's inert for shaper/matrix but harmless, so it's offered in both modes.
        drow = QHBoxLayout()
        drow.addWidget(QLabel(tr("Dark Region Emphasis (-V):"), grp))
        self._dark = NoScrollDoubleSpinBox(grp)
        self._dark.setRange(1.0, 4.0)
        self._dark.setSingleStep(0.1)
        self._dark.setDecimals(1)
        self._dark.setValue(1.0)
        drow.addWidget(self._dark)
        drow.addStretch()
        drow.addWidget(_green_tip("Dark Region Grid Emphasis (-V)", _TIP_DARK, grp))
        g.addLayout(drow)

        # B2A table quality is a printer/output concern (the PCS→device tables the
        # perceptual & saturation intents use), so only the printer path shows it.
        self._b2a_check = self._b2a_combo = None
        if printer:
            self._b2a_check = QCheckBox(tr("B2A Table Quality (-b):"), grp)
            self._b2a_combo = _option_combo(grp)
            for data, lbl in B2A_CHOICES:
                self._b2a_combo.addItem(lbl, data)
            self._b2a_combo.setCurrentIndex(1)          # Medium
            self._b2a_combo.setEnabled(False)
            self._b2a_check.toggled.connect(self._b2a_combo.setEnabled)
            _option_rows(g, self._b2a_check, self._b2a_combo,
                         _green_tip("B2A Table Quality (-b)", _TIP_B2A, grp, 480))

        layout.addWidget(grp)

    def _build_whitepoint_group(self, layout: QVBoxLayout) -> None:
        grp = QGroupBox(tr("White Point"), self)
        g = QVBoxLayout(grp)
        g.setSpacing(8)

        self._wp_mode = _option_combo(grp)
        for data, lbl in WP_MODE_CHOICES:
            self._wp_mode.addItem(lbl, data)
        _option_rows(g, QLabel(tr("White point handling:"), grp), self._wp_mode,
                     _green_tip("White Point Handling (-u / -ua / -uc)",
                                _TIP_WP, grp, 560))

        srow = QHBoxLayout()
        self._wp_scale_label = QLabel(tr("Manual scale:"), grp)
        srow.addWidget(self._wp_scale_label)
        self._wp_scale = NoScrollDoubleSpinBox(grp)
        self._wp_scale.setRange(0.10, 2.00)
        self._wp_scale.setSingleStep(0.05)
        self._wp_scale.setDecimals(2)
        self._wp_scale.setValue(1.00)
        srow.addWidget(self._wp_scale)
        srow.addStretch()
        srow.addWidget(_green_tip("Manual White-point Scale (-u scale)", _TIP_WP_SCALE, grp))
        g.addLayout(srow)

        def _on_wp() -> None:
            manual = self._wp_mode.currentData() == "scale"
            self._wp_scale_label.setEnabled(manual)
            self._wp_scale.setEnabled(manual)
        self._wp_mode.currentIndexChanged.connect(_on_wp)
        _on_wp()

        layout.addWidget(grp)

    def _build_gamut_group(self, layout: QVBoxLayout) -> None:
        grp = QGroupBox(tr("Gamut Mapping"), self)
        g = QVBoxLayout(grp)
        g.setSpacing(8)

        self._gam_mode = _option_combo(grp)
        for data, lbl in GAMUT_SOURCE_CHOICES:
            self._gam_mode.addItem(lbl, data)
        _option_rows(g, QLabel(tr("Gamut Source:"), grp), self._gam_mode,
                     _green_tip("Gamut Source (-s / -S)", _TIP_GAMUT, grp, 560))

        self._gam_path = QLineEdit(grp)
        self._gam_path.setPlaceholderText(
            tr("Path to source RGB profile (e.g. ClayRGB1998.icm or sRGB.icm from Argyll/ref/)"))
        self._gam_browse = make_browse_button(
            grp, tr("Select gamut source profile"), icon="folder_measure")
        self._gam_browse.clicked.connect(self._browse_gamut)
        path_row = _indented(self._gam_path, grp)
        path_row.addWidget(self._gam_browse)
        g.addLayout(path_row)

        def _on_mode() -> None:
            active = bool(self._gam_mode.currentData())
            self._gam_path.setEnabled(active)
            self._gam_browse.setEnabled(active)
        self._gam_mode.currentIndexChanged.connect(_on_mode)
        _on_mode()

        self._perc_check, self._perc_combo = self._intent_row(
            g, grp, tr("Perceptual Intent Override (-t):"),
            "Perceptual Rendering Intent Override (-t)", _TIP_PERC_INTENT)
        self._sat_check, self._sat_combo = self._intent_row(
            g, grp, tr("Saturation Intent Override (-T):"),
            "Saturation Rendering Intent Override (-T)", _TIP_SAT_INTENT)

        layout.addWidget(grp)

    def _intent_row(self, g: QVBoxLayout, grp: QWidget, label: str,
                    tip_title: str, tip_body: str):
        check = QCheckBox(label, grp)
        combo = _option_combo(grp)
        for val, lbl in INTENT_CHOICES:
            combo.addItem(lbl, val)
        combo.setEnabled(False)
        check.toggled.connect(combo.setEnabled)
        _option_rows(g, check, combo, _green_tip(tip_title, tip_body, grp, 500))
        return check, combo

    def _build_metadata_group(self, layout: QVBoxLayout, printer: bool) -> None:
        grp = QGroupBox(tr("Profile Metadata"), self)
        g = QVBoxLayout(grp)
        g.setSpacing(8)

        specs = [
            ("mfr", "A", tr("Manufacturer"), "e.g. Epson", _TIP_MFR),
            ("model", "M", tr("Model"), "e.g. SC-P900", _TIP_MODEL),
            ("copy", "C", tr("Copyright"), "e.g. © 2026 …", _TIP_COPY),
        ]

        self._meta: dict[str, tuple[QCheckBox, QLineEdit]] = {}
        for key, flag, label_text, placeholder, tip in specs:
            row = QHBoxLayout()
            check = QCheckBox(
                tr("{label_text} (-{flag}):").format(label_text=label_text, flag=flag), grp)
            edit = QLineEdit(grp)
            edit.setPlaceholderText(placeholder)
            edit.setEnabled(False)
            check.toggled.connect(edit.setEnabled)
            row.addWidget(check)
            row.addWidget(edit, stretch=1)
            row.addWidget(_green_tip(
                tr("{label_text} (-{flag})").format(label_text=label_text, flag=flag), tip, grp))
            g.addLayout(row)
            self._meta[flag] = (check, edit)

        layout.addWidget(grp)

    def _build_advanced_group(self, layout: QVBoxLayout, printer: bool) -> None:
        # "Expert Options", not "Advanced", and the owner named the reason on
        # 2026-09-03: this box sits INSIDE the window's own "Advanced..."
        # section, so both read "Advanced" and neither tells you which is
        # which. The two hold different KINDS of thing rather than different
        # depths - the outer one has the ordinary profile settings (type,
        # quality, description) while this one has raw ArgyllCMS switches
        # (-ni, -no, -np, -nc, -R and the gamut source).
        #
        # The app already draws exactly that distinction with exactly these
        # words: `tab_chart.py` calls its block of `expert_only` parameters
        # "Expert Options", and the device-link tool does the same. So this is
        # the convention everywhere else, not a coinage - and the key already
        # exists in all twelve catalogues, so no language ships English.
        grp = QGroupBox(tr("Expert Options"), self)
        g = QGridLayout(grp)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(6)
        # The curve / embedding diagnostics apply to both input and output
        # profiles (a scanner profile has input AND output shaper curves too), so
        # both modes show the full set — matching tab 4's Manual module.
        self._flags: dict[str, QCheckBox] = {}
        specs = [
            ("-ni", tr("No input shaper curves (-ni)"), "No Input Shaper Curves (-ni)", _TIP_NI),
            ("-no", tr("No output shaper curves (-no)"), "No Output Shaper Curves (-no)", _TIP_NO),
            ("-np", tr("No input grid position curves (-np)"), "No Grid Position Curves (-np)", _TIP_NP),
            ("-nc", tr("Don't embed measurement data (-nc)"), "Don't Embed .ti3 Data (-nc)", _TIP_NC),
            ("-R", tr("Restrict white, black && primaries (-R)"),
             "Restrict White, Black & Primaries (-R)", _TIP_R),
        ]
        # ONE COLUMN, not two across. Side by side this is the widest row in
        # the whole panel in all twelve languages — 689 px in Russian, 688 in
        # Italian, 673 in Polish, against 321 for the widest measurement row —
        # and this panel sits inside the fixed-width left pane, so that row and
        # nothing else set what the pane had to grow to when Advanced was
        # opened. Stacked it is the width of one switch: 360 px at its worst.
        # Five related switches as a list also read better than a 2 + 2 + 1
        # block whose second column starts at a different place on every row.
        for i, (flag, label, tip_title, tip_body) in enumerate(specs):
            cb = QCheckBox(label, grp)
            g.addWidget(cb, i, 0)
            g.addWidget(_green_tip(tip_title, tip_body, grp), i, 1)
            self._flags[flag] = cb
        g.setColumnStretch(2, 1)
        layout.addWidget(grp)

    # -------------------------------------------------------------- behaviour
    def _browse_gamut(self) -> None:
        # Open in — and pin a left-column shortcut to — Argyll's ref/ folder, where
        # the bundled RGB working-space profiles (ClayRGB1998.icm, sRGB.icm, …)
        # live, so the file the user most likely wants is one click away (Knut).
        start = str(self._ref_dir) if self._ref_dir else ""
        f = open_file_dialog(self, tr("Select gamut source profile"),
                             tr("ICC/ICM profiles (*.icc *.icm)"),
                             start_dir=start, extra_path=start)
        if f:
            self._gam_path.setText(f)

    def _seed(self, values: dict[str, Any]) -> None:
        """Load *values* into the widgets, preferring explicit UI-state keys and
        falling back to the resolved colprof flags (legacy configs)."""
        def _num(key, default):
            try:
                return float(values.get(key, default))
            except (TypeError, ValueError):
                return default
        self._smooth.setValue(_num("-r", 0.5))
        self._dark.setValue(_num("-V", 1.0))

        if self._printer:
            mode = values.get("gamut_mode")
            path = str(values.get("gamut_path", "") or "")
            if mode is None:                       # untouched → derive / preselect
                if values.get("-S"):
                    mode, path = "S", str(values["-S"])
                elif values.get("-s"):
                    mode, path = "s", str(values["-s"])
                else:                              # fresh: preselect ClayRGB1998
                    clay = default_gamut_path(self._ref_dir)
                    mode, path = (DEFAULT_GAMUT_MODE, clay) if clay else ("", "")
            i = self._gam_mode.findData(mode)
            self._gam_mode.setCurrentIndex(i if i >= 0 else 0)
            self._gam_path.setText(path)
            self._seed_intent(self._perc_check, self._perc_combo,
                              values, "perc", "-t")
            self._seed_intent(self._sat_check, self._sat_combo,
                              values, "sat", "-T")
            if self._b2a_check is not None:
                if "b2a_on" in values or "b2a_q" in values:
                    j = self._b2a_combo.findData(str(values.get("b2a_q", "m") or "m"))
                    self._b2a_combo.setCurrentIndex(j if j >= 0 else 1)
                    self._b2a_check.setChecked(bool(values.get("b2a_on", False)))
                elif values.get("-b"):             # legacy resolved flag
                    j = self._b2a_combo.findData(str(values["-b"]))
                    self._b2a_combo.setCurrentIndex(j if j >= 0 else 1)
                    self._b2a_check.setChecked(True)

        if self._wp_mode is not None:              # scanner: white-point handling
            k = self._wp_mode.findData(str(values.get("wp_mode", "") or ""))
            self._wp_mode.setCurrentIndex(k if k >= 0 else 0)
            self._wp_scale.setValue(_num("wp_scale", 1.0))

        for flag, (check, edit) in self._meta.items():
            on_key = {"A": "mfr_on", "M": "model_on", "C": "copy_on"}[flag]
            val_key = {"A": "mfr_val", "M": "model_val", "C": "copy_val"}[flag]
            if on_key in values or val_key in values:
                edit.setText(str(values.get(val_key, "") or ""))
                check.setChecked(bool(values.get(on_key, False)))
            elif values.get("-" + flag):           # legacy resolved flag
                edit.setText(str(values["-" + flag]))
                check.setChecked(True)

        for flag, cb in self._flags.items():
            cb.setChecked(bool(values.get(flag, False)))

    def _seed_intent(self, check, combo, values, prefix, flag) -> None:
        on_key, val_key = prefix + "_on", prefix + "_val"
        if on_key in values or val_key in values:
            i = combo.findData(str(values.get(val_key, "") or ""))
            combo.setCurrentIndex(i if i >= 0 else 0)
            check.setChecked(bool(values.get(on_key, False)))
        elif values.get(flag):                     # legacy resolved flag
            i = combo.findData(str(values[flag]))
            combo.setCurrentIndex(i if i >= 0 else 0)
            check.setChecked(True)

    def restore_defaults(self) -> None:
        """Put every control back to its built-in default."""
        self._smooth.setValue(0.5)
        self._dark.setValue(1.0)
        if self._printer:
            clay = default_gamut_path(self._ref_dir)   # default = ClayRGB1998, not None
            i = self._gam_mode.findData(DEFAULT_GAMUT_MODE if clay else "")
            self._gam_mode.setCurrentIndex(i if i >= 0 else 0)
            self._gam_path.setText(clay)
            for check, combo in ((self._perc_check, self._perc_combo),
                                 (self._sat_check, self._sat_combo)):
                check.setChecked(False)
                combo.setCurrentIndex(0)
            if self._b2a_check is not None:
                self._b2a_check.setChecked(False)
                self._b2a_combo.setCurrentIndex(1)      # Medium
        if self._wp_mode is not None:
            self._wp_mode.setCurrentIndex(0)            # Map chart white to white
            self._wp_scale.setValue(1.0)
        for check, edit in self._meta.values():
            check.setChecked(False)
            edit.clear()
        for cb in self._flags.values():
            cb.setChecked(False)

    def values(self) -> dict[str, Any]:
        """UI state + resolved colprof flags. State keys let the dialog reopen
        exactly as left; resolved keys are what make_profile_params reads."""
        out: dict[str, Any] = {"-r": self._smooth.value(), "-V": self._dark.value()}

        if self._printer:
            mode = self._gam_mode.currentData() or ""
            path = self._gam_path.text().strip()
            out["gamut_mode"] = mode
            out["gamut_path"] = path
            out["-s"] = path if mode == "s" else ""
            out["-S"] = path if mode == "S" else ""
            for check, combo, prefix, flag in (
                    (self._perc_check, self._perc_combo, "perc", "-t"),
                    (self._sat_check, self._sat_combo, "sat", "-T")):
                on = check.isChecked()
                val = combo.currentData() or ""
                out[prefix + "_on"] = on
                out[prefix + "_val"] = val
                out[flag] = val if on else ""
            if self._b2a_check is not None:
                on = self._b2a_check.isChecked()
                q = self._b2a_combo.currentData() or "m"
                out["b2a_on"] = on
                out["b2a_q"] = q
                out["-b"] = q if on else ""

        if self._wp_mode is not None:              # scanner: white-point handling
            out["wp_mode"] = self._wp_mode.currentData() or ""
            out["wp_scale"] = self._wp_scale.value()

        for flag, (check, edit) in self._meta.items():
            on = check.isChecked()
            val = edit.text().strip()
            key = {"A": "mfr", "M": "model", "C": "copy"}[flag]
            out[key + "_on"] = on
            out[key + "_val"] = val
            out["-" + flag] = val if on else ""

        for flag, cb in self._flags.items():
            out[flag] = cb.isChecked()
        return out
