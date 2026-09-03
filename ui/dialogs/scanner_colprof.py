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
    ("scale", tr("Manual white-point scale (-u)")),
]

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
    "• Manual white-point scale (-u) — you set the scale yourself in the box "
    "below.\n\n"
    "Leave it on the first option unless you have a specific white-point "
    "mismatch to fix. Only applies to a scanner/camera input profile.")
_TIP_WP_SCALE = (
    "The white-point scale factor used by “Manual white-point scale” above. "
    "1.00 makes no change.\n\n"
    "If the thing you're scanning or photographing is a little darker than the "
    "test chart's white, use a value slightly below 1.0 (try 0.90) so its white "
    "still comes out as white. If it's a little lighter and the highlights are "
    "blowing out, try a value slightly above 1.0 (try 1.10).\n\n"
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
            tr("Manual White-point Scale (-u)"),
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
        srow.addWidget(_green_tip("Manual White-point Scale (-u)", _TIP_WP_SCALE, grp))
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
