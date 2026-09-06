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

from PyQt6.QtCore import Qt
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

#: …and WHICH OF THE FOUR THE WINDOW MAY OFFER, keyed by printer-mode.
#:
#: This window builds two different device classes from one set of controls,
#: and only one of them can use a matrix profile. With "Profile my printer
#: from this scan" ticked the measurement is `DEVICE_CLASS "OUTPUT"`, and
#: `colprof.c:1244-1246` answers every algorithm but a cLUT with
#: "Output profile can only be a cLUT algorithm" and writes nothing. MEASURED
#: against the 3.5.0 binary on Knut's own printer-mode measurement from this
#: very window (`Knut-Scanner-printer.ti3`, OUTPUT, iRGB_XYZ, 315 sets):
#: `-as` and `-am` both exit 1 with no profile; `-ax` and `-al` build one.
#:
#: The combo used to hold all four in both modes and was populated once, so
#: "Matrix only" was selectable in printer mode, went into the printer
#: settings bucket, and "Save as Defaults" would have kept it there.
#:
#: The scanner/camera side keeps all four: for `DEVICE_CLASS "INPUT"` colprof
#: accepts every algorithm it has (MEASURED, all of `l L x X Y g G s S m`
#: build a profile), and the shaper and matrix types are the right answer for
#: a small target.
PTYPE_CHOICES_BY_MODE: "dict[bool, list[str]]" = {
    False: ["s", "m", "x", "l"],       # scanner / camera  (INPUT)
    True:  ["x", "l"],                 # printer           (OUTPUT)
}

QUALITY_CHOICES = [
    ("l", tr("Low")), ("m", tr("Medium")), ("h", tr("High")), ("u", tr("Ultra")),
]

#: The two profile types that ARE a stored table. Not "the ones -q applies to":
#: that was the claim this line used to make and it was wrong in both
#: directions. ArgyllCMS, `colprof.html` on `-q`: "For table based profiles
#: ('cLUT' profiles), it sets the main lookup table size … For matrix profiles
#: it sets the per channel curve detail level and fitting 'effort'." MEASURED
#: (controlled: one base filename, the ICC header creation time zeroed before
#: hashing) on an INPUT measurement, `-q l/m/h/u` against each algorithm:
#: `s`, `m`, `g`, `S` and `G` all produce four DIFFERENT profiles. The window
#: greyed Quality out for the matrix types and `make_profile_params` put the
#: greyed value on the command line anyway, so the control said it did not
#: apply, could not be changed, and was used regardless.
CLUT_ALGOS = ("x", "l")

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

#: The two profile types that are a FORMULA rather than a stored table. The
#: complement of `CLUT_ALGOS`, named because several rules below turn on "is
#: this a matrix profile?" and a second literal tuple would be a second answer.
MATRIX_ALGOS = ("s", "m")


def ptype_choices(printer: bool) -> "list[tuple[str, str]]":
    """The (letter, label) pairs the Profile type combo may show in *printer*
    mode or out of it. A subset of `PTYPE_CHOICES`, in the same order, so the
    entries a user knows never move about when the tick changes."""
    allowed = PTYPE_CHOICES_BY_MODE[bool(printer)]
    return [(d, lbl) for d, lbl in PTYPE_CHOICES if d in allowed]


def coerce_ptype(ptype: "str | None", printer: bool) -> "tuple[str, bool]":
    """A stored profile type, made legal for the mode it is loaded into.

    Returns ``(letter, changed)``. ``changed`` is True only when the stored
    letter is not one this mode may use, which is the caller's cue to say so
    in the log: the printer bucket could hold "s" or "m" from before this
    window filtered its list, and a build with either of those ends in a
    colprof error rather than a profile.
    """
    letter = (ptype or "").strip()
    allowed = PTYPE_CHOICES_BY_MODE[bool(printer)]
    if letter in allowed:
        return letter, False
    return PTYPE_DEFAULT[bool(printer)], bool(letter)


# ---------------------------------------------------------------------------
# ONE table decides what a scanner/camera profile is set up as (Knut, beta 10)
# ---------------------------------------------------------------------------
# Knut asked for three things, and all three set the same three controls: the
# usage scenario (B8-71), a profile type / quality / white-point choice made
# from the patch count, and a white-point recommendation that follows the
# profile type. Three mechanisms writing three controls is three mechanisms
# that can fight each other, so there is exactly ONE of them: this table, and
# the two functions under it. Everything else reads them.
#
# Knut's rule, beta 10, verbatim in substance: below a hundred patches
# "Shaper + Matrix" with quality Medium and "Map chart white to white"; at a
# hundred or above "cLUT — XYZ table" with quality High and "Scale white to a
# perfect white surface (-u -R)".
#
# It agrees with what was measured here, and the agreement is not luck: B8-19
# put the profile-type crossover at about a hundred fit patches
# (`PTYPE_SMALL_TARGET`), B8-69 measured Quality High as the biggest single
# lever a cLUT has (0.484 → 0.337 ΔE00), and B8-75 measured `-R` costing real
# accuracy on a matrix fit (7.877 → 9.028 ΔE00) while doing the anti-clipping
# job a cLUT wants.
SETUP_CROSSOVER = 100
SETUP_SMALL = {"ptype": "s", "quality": "m", "wp_mode": ""}
SETUP_LARGE = {"ptype": "x", "quality": "h", "wp_mode": "uR"}


def setup_for_patch_count(n_patches: "int | None") -> "dict[str, str] | None":
    """The three settings Knut's rule chooses for a target of *n_patches*, or
    None while the window does not know how big the target is.

    None is not "take the small one": a window that has not been given a chart
    yet knows nothing, and guessing would set settings from a number nobody
    supplied.
    """
    if not n_patches or n_patches < 2:
        return None
    return dict(SETUP_LARGE if n_patches >= SETUP_CROSSOVER else SETUP_SMALL)


# --- the usage scenario (B8-71) --------------------------------------------
# Three answers to one question, and this is the correction that makes the
# control work: they are NOT three parallel alternatives. Scenarios 2 and 3 are
# step one and step two of one job, so the second says "build this one once,
# the printer scenario below uses it" and the third says it needs the profile
# the one above builds. Flat, a user who wants a printer profile picks the
# third, has no measuring profile, and is stuck.
SCENARIO_EVERYDAY = "everyday"
SCENARIO_INSTRUMENT = "instrument"
SCENARIO_PRINTER = "printer"
SCENARIOS = (SCENARIO_EVERYDAY, SCENARIO_INSTRUMENT, SCENARIO_PRINTER)

#: What scenario 2 sets, and every one of the three is a measurement rather
#: than colour-management lore (B8-69, on two real scans, every figure scored
#: only on patches the fit never saw): `-ua` because a Lab cLUT on the old
#: default FLATTENS everything above the chart's own board (device 0.76 / 0.80
#: / 0.85 / 0.90 / 1.00 all read Y 0.833, one colour) and ArgyllCMS asks for
#: the flag by name whenever an input profile stands in for a colorimeter; the
#: XYZ table because it is twice as accurate as the everyday type (0.484
#: against 0.913) and never flattens; Quality High because it is the biggest
#: single lever of the three (0.484 → 0.337, about 30 %).
#:
#: "Restrict white, black and primaries" is deliberately NOT among them.
#: Measured beside `-ua` on a cLUT it is a complete no-op (the two profiles
#: transform identically), and on a cLUT it cannot restrict primaries at all
#: (`profin.c:1070` sets ICX_CLIP_WB only). Setting it would be cargo cult.
SETUP_INSTRUMENT = {"ptype": "x", "quality": "h", "wp_mode": "ua"}



def scenario_setup(scenario: str,
                   n_patches: "int | None") -> "dict[str, str] | None":
    """The settings a scenario pre-selects, or None when it sets none.

    * everyday — Knut's patch-count rule, so the two mechanisms are one thing
      and cannot disagree about the same three controls.
    * instrument — the three measured settings above, whatever the patch count.
      A profile that stands in for a colorimeter needs `-ua` at 24 patches
      exactly as much as at 864, and the cLUT/quality pair is what that job
      was measured on.
    * printer — nothing at all. The printer bucket already defaults to a Lab
      cLUT and white-point handling is stripped from an output build
      (`INPUT_ONLY_KEYS`), so there is no setting for it to pre-select. Its
      whole value is that it appears in the list, in the right order, after
      the scenario that builds the profile it needs.
    """
    if scenario == SCENARIO_EVERYDAY:
        return setup_for_patch_count(n_patches)
    if scenario == SCENARIO_INSTRUMENT:
        return dict(SETUP_INSTRUMENT)
    return None


def label_for(choices, data: str) -> str:
    """The plain, unmarked label of a choice, for quoting inside a sentence.

    The combos append "(recommended…)" markers to what the user sees, so a
    sentence built from the item text would read: Profile type is
    "Shaper + matrix (recommended for a target under 100 patches)".
    """
    for value, label in choices:
        if value == data:
            return label
    return data


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
#
# "uR" is `-u -R`, and it is the DEFAULT (Basti, 2026-09-05). It is one entry
# rather than the two controls it drives because it is one decision; the
# "Restrict white, black and primaries" switch in Expert Options stays where it
# was and stays unticked, so nothing about it changed except that this entry no
# longer needs it to be found.
#
# `-u 1 -R` is what was measured, and `-u 1` is byte-for-byte a bare `-u`:
# `colprof.c:494` sets `autowpsc = 1` before it reads the number and
# `xfit.c:2753` defaults the scale to 1.0. Re-measured 2026-09-05 on the same
# IT8 scan at `-ax -qh`: `-u 1 -R` and `-u -R` produce the same A2B0, B2A0,
# wtpt and bkpt — every colour tag identical, only `desc` differing because
# that is the file name. So the default carries no scale value at all.
WP_MODE_CHOICES = [
    ("uR", tr("Scale white to a perfect white surface (-u -R)")),
    ("", tr("Map chart white to white")),
    ("u", tr("Auto-scale to avoid clipping (-u)")),
    ("ua", tr("Force Absolute Colorimetric (-ua)")),
    ("uc", tr("Clip highlights above white (-uc)")),
    ("scale", tr("Manual white-point scale (-u scale)")),
]
#: The factory default, in ONE place. The combo marks whichever entry this
#: names "(default)" the same way the main window marks its own two, so the
#: label and the default cannot drift apart — the previous default said
#: "(default)" inside its own translated string, in thirteen catalogues.
#:
#: WHY IT MOVED, measured 2026-09-05 on the 864-patch IT8 scan behind
#: `beta 9/knut-whitepoint/REPORT.md`, at `-ax -qh`:
#:   * the old default puts the chart's own white board at PCS white, and that
#:     board is only 84.286 % reflectance. Every reflective original brighter
#:     than it lands above L* 100 — measured 101.12 (84.1 %), 103.47 (89.3 %),
#:     106.08 (95.2 %) and 108.06 (a perfect diffuser) — and all four arrive at
#:     sRGB 255/255/255. That is four different whites collapsed onto one, and
#:     it cannot be undone afterwards.
#:   * `-u -R` puts PCS white at a perfect diffuse reflector instead, so the
#:     same four land at L* 93.50 / 95.69 / 98.12 / 99.98 and none of them
#:     clips. Nothing physically possible ever does.
#:   * it costs no accuracy: profcheck -k -Ia gives avg ΔE00 0.336709 against
#:     the old default's 0.336727 (max 3.657 against 3.636).
#:   * and it stays neutral, which is what separates it from `-ua`. The board
#:     reads a* −0.83 / b* −0.50 under `-u -R` against the old default's
#:     −0.89 / −0.53 — the same chromaticity — where `-ua` reports the chart's
#:     real cast, a* +1.49 rising to +2.50 on a perfect diffuser. Right for an
#:     instrument, wrong for a picture, so `-ua` is not the default.
WP_MODE_DEFAULT = "uR"

#: WHICH ENTRY IS MARKED IN THE DROPDOWN, AND WHY IT IS NO LONGER "(default)".
#:
#: Knut, beta 10: *"the default white point option is wrong for the two matrix
#: profile types — our own help text says 'Scale white to a perfect white
#: surface (-u -R)' makes accuracy worse for them"*, and he offered two routes:
#: label the options "(recommended for cLUT profiles)" / "(recommended for
#: matrix profiles)" instead of calling one the default, or change the selected
#: option automatically when the profile type changes.
#:
#: THE LABEL ROUTE, and the reason is that the other one is a control that
#: silently undoes an edit. A user who has deliberately set "Force Absolute
#: Colorimetric (-ua)" for a measuring profile and then switches the type to
#: try something would have that choice thrown away by a rule following the
#: type — the exact failure `USAGE-SCENARIO-DESIGN.md` §3 rule 2 forbids and
#: the one B8-71 was deferred over. It would also have to fight the two other
#: things that set this control (the scenario and the patch-count rule) over
#: the same widget. A label changes no setting, so it cannot fight anything,
#: and it removes the false universal claim that was the actual complaint.
#:
#: The automatic side of what he asked for is not lost: `setup_for_patch_count`
#: sets all three together, from the patch count, in the one place where it is
#: safe to do so. These two markers are that same table, said out loud — they
#: are DERIVED from it, so a change to the rule moves the labels with it.
#: What the everyday scenario means before anything has been picked, so it has
#: no patch count to reason from.
#:
#: Found by driving the window, 2026-09-06. Choose the measuring scenario, then
#: choose everyday again with no chart loaded, and without this the settings
#: simply stayed on `-ua` and the XYZ table at High while the radio said
#: "everyday scanning". The window was showing one thing and the command line
#: doing another, which is the fault the divergence line exists to prevent and
#: which the divergence line cannot catch here, because with no patch count
#: there is no recipe to compare against.
#:
#: IT IS `SETUP_SMALL`, AND IT IS NOT THE WINDOW'S FACTORY PAIR (CL-2). The
#: first version of this named `PTYPE_DEFAULT[False]` with `WP_MODE_DEFAULT`,
#: which is what a fresh window shows — and that pair is a MATRIX profile type
#: beside the white point this very module labels "(best for cLUT profiles)".
#: It also gave the same scenario two answers at the same profile type: the
#: rule says shaper+matrix wants "Map chart white to white", and this said it
#: wants "Scale white to a perfect white surface". One scenario cannot mean two
#: things, so it means the rule's own small row.
#:
#: What it deliberately does NOT do is move `WP_MODE_DEFAULT`. A window nobody
#: has touched still opens exactly where B8-75 put it; that pairing is Basti's
#: ruling and a separate question from this one.
#:
#: It is ONLY for the explicit click. `setup_for_patch_count(None)` still
#: returns None, so the AUTOMATIC path never sets anything from a number
#: nobody supplied; and the click clears the bucket's "the user has touched
#: this" mark, so loading a chart afterwards refines all three properly.
SETUP_EVERYDAY_UNKNOWN = dict(SETUP_SMALL)

WP_MODE_RECOMMENDED = {
    SETUP_LARGE["wp_mode"]: "clut",
    SETUP_SMALL["wp_mode"]: "matrix",
}

#: What the default was before 2026-09-05. A stored configuration carrying this
#: value AND no schema stamp predates the change and is migrated to
#: `WP_MODE_DEFAULT`; see `migrate_stored_configs`.
WP_MODE_LEGACY_DEFAULT = ""

#: Stored-configuration schema for the scanner window's Advanced values. Bumped
#: when a stored configuration has to be REINTERPRETED rather than merely read
#: — which is exactly what a changed default means for a value that was written
#: because it was the default, not because it was chosen.
ADV_SCHEMA_KEY = "adv_schema"
ADV_SCHEMA_VERSION = 2


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
    # THE OLD WORDING SAID QUALITY APPLIED TO THE cLUT TYPES ONLY, and the row
    # greyed it out for the other two while sending it on the command line
    # regardless. ArgyllCMS, `colprof.html`: "For table based profiles … it
    # sets the main lookup table size … For matrix profiles it sets the per
    # channel curve detail level and fitting 'effort'." MEASURED: `-q l/m/h/u`
    # produces four different profiles for every algorithm tested.
    quality = tr(
        "Quality (-q): how much detail and fitting effort goes into the "
        "profile. For the two look-up-table types it sets the table's grid "
        "resolution; for the shaper and matrix types it sets how finely the "
        "tone curves are fitted. Higher is finer but slower, and needs better "
        "data to be worth it. It applies to every profile type. Medium is a "
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
            tr("Profile type (-a): the shape of the maths inside the "
               "profile, and how it describes what your printer does with "
               "colour. There are two here, not the four you get with the "
               "tick off, and both build a working profile."),
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
            tr("“Shaper + matrix” and “Matrix only”, which this list offers "
               "with the tick off, are not here. That is ArgyllCMS's rule and "
               "not a ChromIQ choice: colprof refuses to build a printer "
               "profile from a formula, and refuses it before it has read a "
               "single patch. The rule is not arbitrary either. By the way "
               "the ICC format works, a matrix-based profile cannot carry a "
               "perceptual or a saturation intent at all, so it would have "
               "nothing to fall back on when a colour is out of the "
               "printer's reach."),
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
        tr("That makes the size of your target the first thing to look at, "
           "and you do not have to count anything or set anything up. The "
           "patch count is printed beside each target's name in the list "
           "above, and again in the green “✓ … patches” line once a target or "
           "a chart is loaded; and the moment ChromIQ knows that number it "
           "sets this control, the Quality below it and Advanced… ▸ White "
           "point handling to suit it. Below about a hundred patches that is "
           "“Shaper + matrix” at Medium; at a hundred or more it is the XYZ "
           "look-up table at High. Change any of the three and ChromIQ leaves "
           "all three alone from then on."),
        tr("• Shaper + matrix, and what ChromIQ chooses for a target under "
           "about a hundred patches: a small, sturdy profile made of one "
           "gentle tone curve for each of red, green and blue plus a 3×3 "
           "matrix, which is a fixed recipe for mixing those three into a "
           "finished colour. It is a formula rather than a stored table, so "
           "it needs very little data to work well, and it carries on "
           "sensibly beyond the lightest and darkest patch your target "
           "contains. Take it for a ColorChecker (24 patches), a "
           "SpyderChecker (48) or a QPcard (49), and whenever a scan is noisy "
           "or you would rather not think about it. On real scanned targets "
           "it was the most accurate of the four at 24 and at 48 patches."),
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
        tr("• The Lab look-up table, the other of the two cLUT entries: the "
           "same kind of table, keeping colour in a different internal form. "
           "On the colours your target actually contains, the two tables "
           "measured close together, with neither of them consistently ahead "
           "of the other. The difference is at the top end: a Lab table has a "
           "hard ceiling and stops dead at it, flattening every tone above "
           "onto one value, where Shaper + matrix and the XYZ table both "
           "carry on. How high that ceiling sits is decided by Advanced… ▸ "
           "White point handling. On “Scale white to a perfect white "
           "surface” it sits at about 114 % reflectance, brighter than a "
           "perfect white surface, so nothing you can put on the glass will "
           "reach it. On “Map chart white to white” the ceiling drops to "
           "about 94 % reflectance, which ordinary bright paper does reach, "
           "and everything above it arrives flattened. (Both figures measured "
           "on a real IT8 scan, so your own will differ a little.) The XYZ "
           "table has no ceiling at all under any of those settings, which is "
           "why it is the safer of the two and why it costs nothing to "
           "take."),
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
        # WHY THE LIST IS FOUR. ArgyllCMS also has -aG and -aS, one tone curve
        # shared by all three channels instead of one curve each, and -ag,
        # gamma curves rather than shaper curves. All three are legal for a
        # scanner or camera (MEASURED: every letter builds a profile from an
        # INPUT .ti3). None is offered, and until now nothing said so. Argyll's
        # own documentation gives their purpose as compatibility, not quality:
        # "may be needed with certain applications that will not accept
        # different gamma curves for each channel", and shaper curves "are
        # superior to gamma curve profiles". So the list stays at four and the
        # window says why, rather than growing two entries nobody asked for.
        # The paragraph names TWO and not three on purpose: `-ag` costs a user
        # nothing, because `-as` is already on the list and is the better of
        # the pair by ArgyllCMS's own account. The shared-curve variants are
        # the only ones whose absence can leave somebody stuck.
        tr("ArgyllCMS has two more variants that this list leaves out, and it "
           "is worth knowing they exist. They fit one tone curve shared by all "
           "three colour channels instead of a separate curve for each. That "
           "is not an accuracy choice: their stated purpose is compatibility "
           "with applications that refuse a profile carrying a different curve "
           "per channel. If an application will not accept a profile this "
           "window built, that is the first thing to mention when you report "
           "it."),
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
            "A note on the profile type: “cLUT — Lab table” has a ceiling, and "
            "how high it sits depends on Advanced… ▸ White point "
            "handling.\n\n"
            "A Lab table cannot describe anything above that ceiling: every "
            "tone over it comes out at one lightness, with the differences "
            "flattened away. On “Scale white to a perfect white surface” the "
            "ceiling is at about 114 % reflectance, brighter than a perfect "
            "white surface, so nothing you can put on the glass reaches it and "
            "there is nothing to worry about. On “Map chart white to white” it "
            "drops to about 94 %, which ordinary bright photo paper does "
            "reach. “cLUT — XYZ table” has no ceiling under any of those "
            "settings and measured just as accurate on the colours your target "
            "does contain, so it is the safer of the two. Your choice stands "
            "either way, and nothing here has been changed for you.")
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
# Every claim below is a measurement from `beta 9/knut-whitepoint/REPORT.md` or
# `beta 9/printer-from-scan/measure/`, or a quotation from ArgyllCMS's own
# colprof.html. The text this replaced was accurate about `-u` and `-uc` and
# wrong about the manual scale; it also read as though the five options were
# five flavours of the same small adjustment, when two of them move every tone
# in the scan by about a stop.
_TIP_WP = (
    "Your scanner does not measure colour. It produces three numbers per pixel "
    "that depend on its lamp, its sensor and the software that saved the file: "
    "the same original scanned by different software gives different numbers. "
    "The profile is what turns those numbers into colour, and this setting "
    "chooses WHAT THE PROFILE CALLS WHITE.\n\n"
    "• Scale white to a perfect white surface (-u -R), recommended for the two "
    "look-up-table profile types. White is put where a perfect white surface "
    "would be, which is the brightest thing a reflective original can "
    "physically be, so nothing you ever put on the glass is brighter than the "
    "profile's white and nothing is clipped. Your chart's white board is "
    "dimmer than that, so it arrives at about L* 93 instead of 100 and a scan "
    "opens looking very slightly grey: one levels step, with every tone still "
    "there to work with. It costs no accuracy (measured on a real IT8 scan, it "
    "and the entry below both average 0.34 ΔE00) and it keeps whites as "
    "neutral as that entry does. On a matrix profile type it is the wrong "
    "choice, and that is why it is not marked recommended for those two: the "
    "“-R” half of it clamps the fit and costs real accuracy there, 7.9 against "
    "9.0 ΔE00 on the same scan.\n\n"
    "• Map chart white to white, recommended for the two matrix profile types. "
    "The white patch of your test chart becomes pure white, and every other "
    "colour is measured against it. A scan opens looking finished, with no "
    "levels step to make, which is why photo applications expect it. The cost "
    "is that anything lighter than your chart's white patch is clipped to "
    "white when the scan is converted into a working space such as sRGB, and "
    "that detail cannot be recovered afterwards. Measured on a real IT8 scan "
    "whose white board is 84 % reflectance: that board, a brighter paper at "
    "89 %, a very bright paper at 95 % and a perfect white surface all arrive "
    "at exactly the same 255/255/255. Take it when the originals you scan are "
    "on paper like your chart's, and you would rather not make that levels "
    "step.\n\n"
    "• Auto-scale to avoid clipping (-u): the profile is scaled so that the "
    "scanner's MAXIMUM value becomes white. Nothing can clip, but it goes far "
    "further than it needs to. That maximum is around 160 % reflectance, half "
    "as bright again as anything that can physically exist on paper, so every "
    "tone in the scan arrives much darker than with the first entry above, and "
    "you are expected to set the white yourself afterwards. Use it only if "
    "something later in your workflow does that.\n\n"
    "• Force Absolute Colorimetric (-ua): the profile reports colour as it "
    "actually is, measured against a perfect white surface, instead of "
    "relative to your chart's white. (“Absolute colorimetric” is the rendering "
    "intent that means exactly that: report what is there, adapt nothing.) "
    "Both intents then give the same answer, so no application can pick the "
    "wrong one. This is the setting for using the scanner as a measuring "
    "instrument, and it is what the usage scenario “A profile for my scanner, "
    "so it can stand in for a measuring instrument” chooses for you. Two "
    "costs: your scans arrive darker, because your chart's white patch is not "
    "a perfect white; and the profile no longer neutralises the colour of your "
    "chart's paper, so whites keep their real slight tint. Correct as a "
    "measurement, unfinished-looking as a picture.\n\n"
    "• Clip highlights above white (-uc): anything brighter than the chart's "
    "white is forced exactly onto white. It only affects look-up-table (cLUT) "
    "profile types, and it costs accuracy in the lightest colours.\n\n"
    "• Manual white-point scale (-u scale): this is “Auto-scale” above with "
    "your own number applied on top of it, not a scale on its own. A value of "
    "1.00 is therefore the same thing as “Auto-scale to avoid clipping”, not "
    "“no change”; see the box below.\n\n"
    "Which to choose. Once you have loaded a chart or a target, ChromIQ has "
    "already set this from the size of it, together with the profile type and "
    "the quality, so you can normally leave it alone. Change it if one of "
    "these fits you better. Scanning photographs on paper like your chart's, "
    "and you want the scan finished the moment it opens: “Map chart white to "
    "white”. Using the scanner to MEASURE rather than to photograph: “Force "
    "Absolute Colorimetric”.\n\n"
    "A note on “Restrict white, black and primaries”, the switch under Expert "
    "Options. It is the “-R” half of the first entry above, so while that "
    "entry is chosen the switch is shown ticked and locked, with a line beside "
    "it saying where the tick came from. Everywhere else it is yours to set, "
    "and what it does depends on the profile type: on a look-up-table profile "
    "it can only limit the white and black points, because a look-up table has "
    "no primaries to restrict; with “Map chart white to white” it usually does "
    "nothing at all; with “Force Absolute Colorimetric” it does nothing "
    "either, because that option has already put white where the clamp would "
    "(measured: the two profiles transform identically); and on the two matrix "
    "profile types it clamps the fit and costs accuracy.\n\n"
    "Worth more than any of this: the Quality setting. On a real IT8 scan, "
    "moving Quality from Medium to High cut the average error by about 30 %, "
    "more than every white-point option in this list put together.\n\n"
    "Only applies to a scanner/camera input profile.")
_TIP_WP_SCALE = (
    "The number that “Manual white-point scale” above uses, and it is applied "
    "ON TOP OF that option's automatic scaling rather than instead of it.\n\n"
    "So 1.00 does not mean “no change”. It means “the automatic scaling, "
    "unaltered”, which makes it identical to “Auto-scale to avoid clipping”: "
    "measured on a real IT8 scan, the two build the same profile. If what you "
    "want is to leave the white alone, that is the entry “Map chart white to "
    "white” in the list above, not a scale of 1.00.\n\n"
    "Numbers below 1.00 reduce the automatic scaling without undoing it. On "
    "that same scan, 0.90 still left the white point at about 1.46 instead of "
    "1.00, and every tone in the scan about 44 % darker than “Scale white to a "
    "perfect white surface”. Numbers above 1.00 scale further still.\n\n"
    "Reach for this only when you already know the factor you want. The one "
    "everyday thing it used to be needed for, a scale of 1.00 with “Restrict "
    "white, black and primaries” ticked alongside it to bring the white point "
    "back to a perfect white surface, is now the first entry in the list "
    "above, so you no longer have to build it out of two controls.\n\n"
    "This box only has an effect when the handling above is set to “Manual "
    "white-point scale”.")
# What it does depends on the PROFILE TYPE, and the old text said neither.
# `profin.c:794` (matrix path) sets ICX_CLIP_WB | ICX_CLIP_PRIMS; `profin.c:1070`
# (cLUT path) sets ICX_CLIP_WB only, and ICX_CLIP_PRIMS is consumed nowhere
# outside xicc/xmatrix.c — so on a cLUT the word "primaries" in the label is
# inert. Measured on a real IT8 scan: alone it is a complete no-op (identical
# tags), with "Force Absolute Colorimetric" it is a no-op too (identical
# transform), with "Manual white-point scale" it rescales the whole table, and
# on a matrix profile it costs accuracy — 7.877 to 9.028 dE00.
_TIP_R = (
    "Holds white to no brighter than full white and, on the two matrix profile "
    "types only, forces black and the pure primary colours to stay positive "
    "rather than negative. Some programs are unhappy with a profile whose "
    "white point is brighter than white or whose corners go negative, and this "
    "makes such a profile acceptable to them.\n\n"
    "What it actually does depends on the profile type, and it is worth "
    "knowing before you tick it:\n\n"
    "• On a look-up-table profile (either cLUT type) it can only clamp the "
    "white and black points. A look-up table has no primaries, so that half of "
    "the label does nothing here.\n"
    "• With White point handling on “Scale white to a perfect white surface”, "
    "this switch is ALREADY IN FORCE: that entry is this switch and “-u” "
    "together. So it is shown here ticked and locked, with a line beside it "
    "saying so, and choosing any other white point handling gives it back to "
    "you with whatever you had set.\n"
    "• On its own, with “Map chart white to white”, it usually changes nothing "
    "at all: measured on a real IT8 scan, the profile came out identical.\n"
    "• Together with “Manual white-point scale” it is not a tidy-up. It "
    "rescales the whole colour table, and it is what puts white at a perfect "
    "white surface.\n"
    "• With “Force Absolute Colorimetric” it does nothing, because that option "
    "has already put white where the clamp would put it.\n"
    "• On “Shaper + matrix” or “Matrix only” it clamps the fit and costs real "
    "accuracy. ArgyllCMS says so itself: “this will reduce the accuracy of the "
    "profile”.\n\n"
    "So you can leave it unchecked: the one setting that needs it already "
    "carries it. Tick it when a program refuses or misreads your profile, or "
    "when you are pairing it with “Manual white-point scale”.")


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
        # A bucket nobody has saved has no wp_mode at all, and an ABSENT key is
        # not the same thing as a stored "". `setdefault`, so a user who has
        # deliberately chosen "Map chart white to white" keeps it.
        v.setdefault("wp_mode", WP_MODE_DEFAULT)
    return v


def migrate_stored_configs(raw: Any) -> "tuple[dict, list[str]]":
    """Bring stored scanner-window configurations up to `ADV_SCHEMA_VERSION`.

    Returns ``(configs, migrated)`` — the configurations to use, and the names
    of the buckets whose white-point handling this call CHANGED. An empty list
    means nothing moved, and the caller has nothing to write and nothing to say.

    The one migration so far is the white-point default (Basti, 2026-09-05:
    *"our user base is not very big at the moment so i want the better
    default"*). A configuration written before this change stores
    ``wp_mode = ""`` — but "" was what the window WROTE for everybody, whether
    or not anybody chose it, so on its own it cannot be read as a decision.
    The schema stamp is what tells the two apart: a configuration with no stamp
    was written by a version in which "" was the default, so its "" is adopted
    into the new default; every configuration this version writes carries the
    stamp, so a "" chosen deliberately from here on is left exactly alone.

    Nothing else in the configuration is touched, and no profile, measurement
    or file on disk is read or written by this — it is one remembered dropdown
    position, and the option it used to name is still in the same dropdown.
    """
    out: dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    migrated: list[str] = []
    for ctx, cfg in list(out.items()):
        if not isinstance(cfg, dict):
            continue
        adv = cfg.get("adv")
        if not isinstance(adv, dict) or not adv:
            continue                       # never saved: it takes the default
        try:
            stamped = int(adv.get(ADV_SCHEMA_KEY, 1))
        except (TypeError, ValueError):
            stamped = 1
        if stamped >= ADV_SCHEMA_VERSION:
            continue
        adv = dict(adv)
        # `in`, not `.get(...) == ""` — a PRINTER bucket has no wp_mode at all
        # (`values()` writes it only in scanner mode, and `effective_adv_vals`
        # strips it), and giving one an input-profile setting would put a flag
        # colprof refuses on an output build into a config that never had it.
        if adv.get("wp_mode", object()) == WP_MODE_LEGACY_DEFAULT:
            adv["wp_mode"] = WP_MODE_DEFAULT
            migrated.append(ctx)
        adv[ADV_SCHEMA_KEY] = ADV_SCHEMA_VERSION
        out[ctx] = {**cfg, "adv": adv}
    return out, migrated


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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        v = QVBoxLayout(body)
        v.setSpacing(10)

        self._wp_mode = None                       # scanner-only; None in printer mode
        #: The user's own answer to "-R", kept apart from what the checkbox is
        #: currently SHOWING — see `_sync_r_lock`.
        self._r_user = False
        self._r_note = None
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
            # The markers are applied HERE, from `WP_MODE_RECOMMENDED`, not
            # written into an entry's own translated string. The window's other
            # two dropdowns are marked the same way and from the same constants
            # (`scanin_dialog._mark_default_combos`), so a change of advice is
            # one table and never thirteen catalogues out of step.
            #
            # TWO MARKERS, NOT "(default)" (Knut, beta 10). One of these two
            # options is better for a look-up-table profile and the other is
            # better for a matrix one — our own help says so, and it is
            # measured — so a single "(default)" told half the users of this
            # window something untrue about their own profile type.
            #
            # "best for", not Knut's own "recommended for", and the three
            # characters are MEASURED. This combo sits on its own line in a
            # FIXED-width pane, and `test_the_worst_languages_fit_a_1280_
            # screen` refuses to let opening the Advanced disclosure widen the
            # window. Against the app's own Fusion style: "(recommended for
            # cLUT profiles)" made the window 53 px wider the moment Advanced
            # was opened, "(recommended for cLUT)" 3 px wider, and this fits
            # with nothing to spare. A translation longer than this one will
            # be caught by the same test, which is where it belongs.
            kind = WP_MODE_RECOMMENDED.get(data)
            if kind == "clut":
                lbl = tr("{option} (best for cLUT profiles)").format(
                    option=lbl)
            elif kind == "matrix":
                lbl = tr("{option} (best for matrix profiles)").format(
                    option=lbl)
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

        # A BOUND METHOD, not a closure capturing `self`. CLAUDE.md's standing
        # rule for slots on a signal a widget's own child emits.
        self._wp_mode.currentIndexChanged.connect(self._on_wp_mode_changed)

        layout.addWidget(grp)

    def _on_wp_mode_changed(self, *_args) -> None:
        """The white-point choice moved: enable the manual scale box for the
        one entry that uses it, and show whether `-R` is in force."""
        if self._wp_mode is None:                  # printer mode has no such row
            return
        manual = self._wp_mode.currentData() == "scale"
        self._wp_scale_label.setEnabled(manual)
        self._wp_scale.setEnabled(manual)
        self._sync_r_lock()

    # ------------------------------------------------------------------
    # "Restrict white, black & primaries (-R)" — visible when it is in force
    # ------------------------------------------------------------------
    # Knut, beta 10: *"the -R checkbox is invisible. The default white-point
    # option is 'Scale white to a perfect white surface (-u -R)', which
    # includes -R, but the checkbox is not ticked."*
    #
    # He is right, and an unticked box beside a command line that reads
    # `-u -R` is simply false. So while that entry is chosen the box is shown
    # TICKED AND DISABLED, with the reason on screen beside it.
    #
    # Ticked, because it is on. Disabled, because it cannot be turned off from
    # here: the white-point entry puts `-R` on the command line whatever this
    # box says (`profile_builder.py:487` — `if p.clip_primaries or
    # p.wp_mode == "uR"`), so an editable control that cannot change the
    # outcome is worse than a locked one. The reason is a LABEL and not a
    # tooltip, because Qt sends no events to a disabled widget and a disabled
    # checkbox's tooltip therefore never appears.
    #
    # And the user's own answer is kept, untouched, in `_r_user`: `values()`
    # writes THAT, never the forced display state. Otherwise choosing the
    # default and pressing "Save as Defaults" would store `-R: true` for ever,
    # and a later switch to "Map chart white to white" would silently carry a
    # flag the user never asked for into a profile that had none. The command
    # line is byte-for-byte what it was before this change; that is what
    # `test_the_locked_tick_changes_no_command_line` proves.
    def _sync_r_lock(self) -> None:
        cb = self._flags.get("-R")
        if cb is None or self._wp_mode is None:
            return
        forced = self._wp_mode.currentData() == WP_MODE_DEFAULT
        cb.blockSignals(True)
        cb.setChecked(True if forced else self._r_user)
        cb.blockSignals(False)
        cb.setEnabled(not forced)
        if self._r_note is not None:
            self._r_note.setVisible(forced)

    def _r_choice(self) -> bool:
        """What the user has actually asked of `-R`, ignoring the lock."""
        cb = self._flags.get("-R")
        if cb is None:
            return False
        if not cb.isEnabled() and self._wp_mode is not None \
                and self._wp_mode.currentData() == WP_MODE_DEFAULT:
            return self._r_user
        return cb.isChecked()

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
        # WHERE THE TICK CAME FROM, said on screen (Knut, beta 10). A WRAPPING
        # label spanning the whole grid: this panel lives in the window's
        # fixed-width left pane, and a suffix on the checkbox itself would set
        # how wide that pane has to be in every one of thirteen languages.
        if not printer:
            self._r_note = QLabel(tr(
                "“Restrict white, black and primaries” is ticked and locked "
                "because White point handling above is set to “Scale white to "
                "a perfect white surface (-u -R)”, and the “-R” in that entry "
                "is this switch. Choose any other white point handling to get "
                "it back."), grp)
            self._r_note.setWordWrap(True)
            self._r_note.setEnabled(False)         # a note, not a control
            # …and it may not be what decides how wide this panel is. The
            # panel sits in the window's FIXED-width left pane, which grows
            # when Advanced opens and gives the width back when it closes, and
            # `test_the_worst_languages_fit_a_1280_screen` measures exactly
            # that: without the cap this note added 53 px to the open width in
            # English alone. Capped at the widest switch it already has to fit,
            # it wraps instead and costs nothing.
            cap = max(cb.sizeHint().width() for cb in self._flags.values())
            self._r_note.setMaximumWidth(cap)
            # …and its HEIGHT is settled here, once, from that same cap, rather
            # than latched on a resize. Measured on screen 2026-09-06: a
            # `_WrapHint`-style label that reclaims its height in `resizeEvent`
            # never gets one while it is hidden, so it kept the height its
            # text needs at the DEFAULT 100 px width — about 650 px — and the
            # note appeared floating in the middle of a tall empty box when it
            # was finally shown. The width here is fixed by the pane and by the
            # cap above, so one measurement is the whole answer, in any
            # language.
            g.addWidget(self._r_note, len(specs), 0, 1, 3,
                        Qt.AlignmentFlag.AlignTop)
            self._r_note.setFixedHeight(self._r_note.heightForWidth(cap))
            self._r_note.setVisible(False)
            self._flags["-R"].toggled.connect(self._on_r_toggled)
        layout.addWidget(grp)

    def _on_r_toggled(self, on: bool) -> None:
        """The user moved "-R" themselves: that is their answer from now on."""
        self._r_user = bool(on)

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
            # `WP_MODE_DEFAULT` as the fallback, not "": since 2026-09-05 "" is
            # a real entry a user can choose ("Map chart white to white"), so a
            # missing key and a stored "" mean different things and only the
            # missing one may be re-defaulted.
            k = self._wp_mode.findData(str(values.get("wp_mode", WP_MODE_DEFAULT)))
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
        # …and "-R" gets its lock applied AFTER the seed, so a stored value is
        # what comes back when the white-point option stops forcing it. The
        # seed above already ran `_on_r_toggled`, so `_r_user` is the stored
        # answer; set it again anyway, because a stored False after a stored
        # True emits nothing.
        self._r_user = bool(values.get("-R", False))
        self._on_wp_mode_changed()

    def set_wp_mode(self, data: str) -> bool:
        """Put the white-point handling on *data*. Returns whether it moved.

        The one supported way for the window above to change this control:
        the usage scenario and the patch-count rule both set it, and both go
        through here so the "-R" lock, the manual-scale box and the command
        preview all follow in one place.
        """
        if self._wp_mode is None:
            return False
        i = self._wp_mode.findData(data)
        if i < 0 or i == self._wp_mode.currentIndex():
            return False
        self._wp_mode.setCurrentIndex(i)
        return True

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
            k = self._wp_mode.findData(WP_MODE_DEFAULT)
            self._wp_mode.setCurrentIndex(k if k >= 0 else 0)
            self._wp_scale.setValue(1.0)
        for check, edit in self._meta.values():
            check.setChecked(False)
            edit.clear()
        for cb in self._flags.values():
            cb.setEnabled(True)        # so "-R" can be cleared before relocking
            cb.setChecked(False)
        self._r_user = False
        self._on_wp_mode_changed()

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
        # "-R" is the ONE flag whose widget can be showing something the user
        # did not choose (see `_sync_r_lock`), so it is written from their own
        # answer. Without this line, opening the window on the recommended
        # cLUT white point and pressing "Save as Defaults" would store
        # `-R: true` for ever, and a later switch to "Map chart white to
        # white" would quietly carry a clamp the user never asked for.
        if "-R" in out:
            out["-R"] = self._r_choice()
        # Anything this version writes is current by definition. Without the
        # stamp a deliberate "Map chart white to white" would be read as a
        # pre-2026-09-05 leftover on the next open and silently re-defaulted —
        # a migration that fired for ever instead of once.
        out[ADV_SCHEMA_KEY] = ADV_SCHEMA_VERSION
        return out
