"""Tab 2: Print Chart."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from core.logger import get_logger
from core.platform_paths import file_manager_name
from core.platform_paths import is_linux, is_macos, is_windows
from ui.dialogs.preflight_dialog import PreflightDialog
from ui.fade_scroll import FadeScrollArea
from ui.tab_header import TabHeader
from ui.tiff_preview import TiffPreview, _find_sidecar_channels
from ui.tooltip_button import TooltipButton
from ui.widgets import NoScrollComboBox, PatchGridButton, rewrap_button_label, info_box_qss, load_refresh_icon, message_box, open_file_dialog, set_accent_html, spectrum_cell
from workflow.cups_printer import CupsRawPrinter
from workflow.page_geometry import (
    ORIENTATION_LANDSCAPE,
    check_size_mismatch,
    compute_orientation,
    read_tiff_dimensions_points,
)
from workflow.print_manager import PrintModule
from workflow.win_raw_printer import WindowsRawPrinter

# CUPS option names that represent a paper-size selection — used to find which
# combo value to look up in the PPD when computing orientation / mismatch.
_PAGE_SIZE_KEYS = {"EPIJ_Size", "media", "PageSize"}
#: How close (sum of both sides, in points) a paper must be to the chart for
#: the paper size preselection to call it the chart's own size (~3.5 mm)
_PRESELECT_CLOSE_PT = 10.0
#: How much smaller than the chart a preselected paper may be: rounding of
#: the page image's pixels only (a 100 dpi 4 x 6 in chart is 1.4 pt wider
#: than its sheet), never a cut-off chart (re-review of 4.3.8).
_PRESELECT_ROUNDING_PT = 3.0
# Option names whose "on" value means borderless is enabled (native vendor
# toggles + the synthetic key surfaced by PrintModule for drivers that
# encode borderless in PageSize variants or EPIJ_PSrc).
_BORDERLESS_KEYS = {
    "EPIJ_Brlss", "CNBorderless", "BorderlessPrint", "Borderless",
    "__BORDERLESS__",
}


def _borderless_selected(selected_opts: dict[str, str]) -> bool:
    """True when the current option selection requests a borderless print.

    Covers all three ways drivers encode it: a dedicated on/off toggle
    (incl. ChromIQ's synthetic one), Epson's EPIJ_PSrc=3 page-setup value,
    and borderless PageSize variants picked directly (e.g. "A4.FullBleed").
    """
    from workflow.print_manager import (
        _BORDERLESS_SIZE_SUFFIXES,
        _EPSON_PSRC_BORDERLESS,
    )
    if any(
        selected_opts.get(k, "").lower() in ("true", "on", "yes", "1")
        for k in _BORDERLESS_KEYS
    ):
        return True
    if selected_opts.get("EPIJ_PSrc", "") == _EPSON_PSRC_BORDERLESS:
        return True
    return any(
        selected_opts.get(k, "").endswith(_BORDERLESS_SIZE_SUFFIXES)
        for k in _PAGE_SIZE_KEYS
    )

if TYPE_CHECKING:
    from core.settings import AppSettings

log = get_logger(__name__)
from ui.styles import SPEC_AMBER, TAB_COLORS
from core.i18n import count_phrase, tr
from core.platform_paths import default_output_root
from ui.warning_sign import inform, set_question_icon, set_warning_icon, warn

#: beta 16: the quality options whose rows follow the driver's own tables
#: (``ppd_color.quality_choices``) and carry M-PRINT-QUALITY
_PAPER_QUALITY_OPTS = ("CNIJPrintQuality", "EPIJ_Qual")


def _with_plain_paper(body: str) -> str:
    """A macOS Print Chart help, with the plain-paper paragraph after the
    paragraph that explains the paper types (beta 17). In both macOS helps
    that is the second paragraph (the paper profile and the media type), so
    it goes third; a shorter help gets it at the end."""
    paras = body.split("\n\n")
    extra = tr(_TT_PLAIN_PAPER)
    at = 2 if len(paras) > 2 else len(paras)
    return "\n\n".join(paras[:at] + [extra] + paras[at:])


def _queue_cmyk_raster(queue: str) -> "str | None":
    """The CMYK family *queue* rasterises a job in at its default colour mode
    (``ppd_color.cmyk_raster_space``), else None."""
    from workflow.ppd_color import cmyk_raster_space
    ppd = PrintModule.find_ppd_path(queue)
    if not ppd:
        return None
    from core.text_io import read_text
    try:
        text = read_text(Path(ppd), lenient=True)
    except OSError:
        return None
    return cmyk_raster_space(text, {}, queue)


def _ink_conversion_message(conv):
    """The §M message for an ``_ink_conversion`` result (4.3.5 B2)."""
    from workflow import measurement_messages as MM
    return (MM.M_PRINT_INKS_CONVERTED if conv[0] == "converted"
            else MM.M_PRINT_INKS_APPROXIMATE)


def _printer_display_name(queue: str) -> str:
    """The queue's name as macOS shows it (its printer-info), else the queue."""
    try:
        import cups
        return cups.Connection().getPrinters().get(queue, {}).get("printer-info") or queue
    except Exception:  # noqa: BLE001
        return queue


def _html_escape(text: str) -> str:
    import html
    return html.escape(text, quote=False)


_TT_TITLE_PRINT = "Step 2 — Print the chart"

_TT_BODY_PRINT_MACOS_BYPASS = (
    "This step sends the chart from step 1 straight to your printer's queue. "
    "On a Canon or Epson, ChromIQ sends it the way Photoshop sends an image "
    "when Photoshop manages colours: the medium's paper profile is attached, "
    "so macOS leaves the chart's numbers unchanged. Other printers get the "
    "chart with colour management switched off.\n\n"
    "ChromIQ knows which paper profile goes with which paper type for the "
    "Canon and Epson models whose drivers it can read, and for the models it "
    "has measured. For any other model it learns this one paper type at a "
    "time, from a print through the macOS print dialog. Until then it tells "
    "you before printing and offers the dialog. On plain paper, cards and "
    "printable discs a Canon keeps its own colour processing switched on, as "
    "it does for prints from Photoshop.\n\n"
    "**Before you print:**\n"
    "• Load the exact paper you chose in step 1. Different paper = "
    "different profile.\n"
    "• Make sure the printer is on, has ink, and is selected below.\n"
    "• Use the same ink, paper, and print settings every time you "
    "re-profile this printer: the profile only matches that recipe.\n\n"
    "**How to use this screen:**\n"
    "• Pick the printer, paper size and media type. If a quality setting "
    "is shown, choose the one you will use for real prints. On a Canon or "
    "Epson the quality row lists the qualities the driver allows for this "
    "paper; ChromIQ preselects the one you last used in the print dialog for "
    "it, otherwise the driver's standard.\n"
    "• Click \"Print All Pages\" (or \"Print Current Page\" for just the page on screen). No print dialog will appear: the chart goes "
    "straight to the queue.\n\n"
    "**After printing:** let the print dry fully (at least 1 hour, 24 h for "
    "best accuracy with pigment inks) before measuring. Wet ink reads "
    "wrong.\n\n"
    "If you'd rather use the macOS print dialog (e.g. to pick a specific "
    "paper feed), enable \"Use default macOS printer dialog\" in Preferences. "
    "The dialog works with any printer."
)

#: Beta 17 (Basti, 2026-10-09, approving the help drafted in
#: ~/Desktop/ChromIQ-work/2026-10-09_plain_paper_apps/REPORT.md): measured on
#: a Canon PRO-300, every macOS app puts plain paper into the same printer
#: state, Canon's own colour processing on, and so does ChromIQ. Added after
#: the paragraph that explains the paper types, on both macOS routes.
_TT_PLAIN_PAPER = (
    "On plain paper the Canon driver always uses its own colour processing, "
    "whatever program prints. ChromIQ prints the chart the same way. The "
    "profile therefore fits prints from Photoshop (\"Photoshop manages "
    "colours\"), Preview and other programs where you choose this profile in "
    "the colour settings, as long as you pick Plain Paper and the same print "
    "quality there.")

_TT_BODY_PRINT_MACOS_NATIVE = (
    "This step opens macOS's standard print dialog so you can pick paper "
    "feed, media type, quality, and copies yourself.\n\n"
    "ChromIQ asks for application colour matching, as Photoshop does. After "
    "you close the dialog it attaches the paper profile of the medium you "
    "chose to the chart, so macOS does not change its colours. Pick the right "
    "media type: the paper profile follows it. Afterwards the Print Chart tab "
    "says what the printing system holds for the job.\n\n"
    "This works with any printer: where the driver has paper profiles, its "
    "own dialog chooses one. ChromIQ also remembers that choice, so a Canon "
    "or Epson model it did not know can then print straight to the queue on "
    "that paper type as well.\n\n"
    "**Before you print:**\n"
    "• Load the exact paper you chose in step 1.\n"
    "• Make sure the printer is on, has ink, and is selected.\n\n"
    "**How to use this screen:**\n"
    "• Click \"Print All Pages\" (or \"Print Current Page\" for just the page on screen). The macOS print dialog appears.\n"
    "• Pick the right paper / media type and print quality.\n"
    "• You don't need to change any colour setting.\n\n"
    "Prefer ChromIQ to print straight to the queue with no dialog? Untick "
    "\"Use default macOS printer dialog\" in Preferences to use the lp path "
    "instead.\n\n"
    "Let the print dry fully (1 h minimum, 24 h for pigment inks) before "
    "measuring."
)

_TT_BODY_PRINT_LINUX = (
    "This step sends the TIFF from step 1 straight to your printer via "
    "CUPS, with all colour management turned off. ChromIQ converts the "
    "chart to PostScript and sends it through the \"lp\" command in raw "
    "mode, so the printer's own driver corrections don't touch the "
    "patches. That's deliberate: to profile a printer we need to see how "
    "it behaves on its own, before any correction.\n\n"
    "**Before you print:**\n"
    "• Load the exact paper you chose in step 1. Different paper = "
    "different profile.\n"
    "• Make sure the printer is on, has ink, and shows up in CUPS "
    "(the system print queue). If you don't see it below, check "
    "System Settings → Printers, or visit http://localhost:631.\n"
    "• Use the same ink, paper, and print settings every time you re-profile this printer: the profile only matches that recipe.\n\n**How to use this screen:**\n• Pick the printer and paper size. Quality should usually be the "
    "highest setting you'll print at in real use.\n"
    "• Click \"Print All Pages\" (or \"Print Current Page\" for just the page on screen). No print dialog will appear: the chart goes straight to the CUPS queue.\n\n"
    "**After printing:** let the print dry fully (at least 1 hour, 24 h for "
    "best accuracy with pigment inks) before measuring. Wet ink reads "
    "wrong.\n\n"
    "**Note:** on Linux there is no native dialog option: ChromIQ always "
    "prints via the CUPS bypass path, which is the right choice for "
    "profiling anyway."
)

_TT_BODY_PRINT_WINDOWS = (
    "This step opens Windows' standard print dialog so you can pick the "
    "printer and its options. IMPORTANT: ChromIQ cannot disable the "
    "printer driver's colour management for you on Windows. You must turn it off yourself before printing, or the printer will apply "
    "its own corrections and the chart will be unusable for profiling.\n\n"
    "**Before you print:**\n"
    "• Load the exact paper you chose in step 1.\n"
    "• Make sure the printer is on, has ink, and is selected.\n\n"
    "**How to use this screen:**\n"
    "• Click \"Print All Pages\" (or \"Print Current Page\" for just the page on screen) to open the dialog.\n"
    "• In the dialog, open the printer's Properties / Preferences and "
    "find its colour-management section. Set it to OFF / \"No Color "
    "Adjustment\" / \"Application Managed Colors\":\n"
    "    – Epson:  \"Epson Color Controls\" → Off (No Color Adjustment)\n"
    "    – Canon:  \"Color Options\" → Manual → None\n"
    "    – HP:     \"Color Options\" → Application Managed Colors\n"
    "    – Others: look for \"No Color Management\", \"Off\", or "
    "\"Application Controlled\"\n"
    "• Pick the right paper / media type and print quality. Confirm "
    "colour management is OFF before clicking Print.\n\n"
    "**After printing:** let the print dry fully (1 h minimum, 24 h for "
    "pigment inks) before measuring."
)


#: #205 (4.3.8): what the Windows dialog route does since 4.3.8, after the
#: help above (kept as it was approved and translated).
_TT_PRINT_WINDOWS_DIALOG_EXTRA = (
    "**Size:** ChromIQ prints the chart at exactly 100% size, centred on "
    "the paper, so that every patch is where your measuring instrument "
    "expects it. Choose a paper size in the dialog that the chart fits on. "
    "If the chart is larger than the paper, ChromIQ tells you instead of "
    "shrinking it.\n\n**CMYK and multi-ink charts** cannot go through the "
    "Windows print dialog, because Windows passes only RGB colours to the "
    "printer driver. ChromIQ tells you if you try.\n\n**Prefer to print "
    "without a dialog?** Untick \"Use default Windows printer dialog\" in "
    "Preferences. ChromIQ then sends the chart directly to a PostScript "
    "printer, bypassing the printer driver, so no colour setting can get "
    "in the way."
)

#: #205 (4.3.8): the help of ChromIQ's own route on Windows.
_TT_BODY_PRINT_WINDOWS_DIRECT = (
    "This step prints the chart from step 1 directly, without a print "
    "dialog.\n\n**How the chart reaches the printer:**\n• A PostScript "
    "printer receives the chart straight from ChromIQ. (PostScript is a "
    "printer language that many office, large-format and professional "
    "photo printers understand.) The printer driver is bypassed, so "
    "nothing on the way can adjust the colours: the printer gets the "
    "chart's own RGB, CMYK or ink values, at exactly 100% size. CMYK and "
    "multi-ink charts work too.\n• Most home and photo inkjet printers do "
    "not understand PostScript. For these, ChromIQ opens the Windows print "
    "dialog for an RGB chart. There, open the printer's Properties window "
    "and switch its colour adjustment off. A CMYK or multi-ink chart "
    "cannot reach such a printer unchanged, so ChromIQ tells you and does "
    "not print it.\n\n**Before you print:**\n• Load the exact paper you chose "
    "in step 1. Different paper = different profile.\n• Make sure the "
    "printer is on, has ink, and is selected below.\n• Use the same ink, "
    "paper and print settings every time you re-profile this printer: the "
    "profile only matches that recipe.\n\n**How to use this screen:**\n• Pick "
    "the printer and the paper size, and the media type and quality if the "
    "printer offers them. ChromIQ puts these settings into the print job "
    "itself. Settings you made earlier in the printer's own Properties "
    "window in Windows are not used for this print.\n• Click \"Print All Pages\" (or \"Print Current Page\" for just the page on screen). No "
    "print dialog appears: the chart goes straight to the "
    "printer.\n\n**After printing:** let the print dry fully (at least 1 "
    "hour, 24 h for best accuracy with pigment inks) before measuring. Wet "
    "ink reads wrong.\n\nIf you'd rather use the Windows print dialog for "
    "every printer, tick \"Use default Windows printer dialog\" in "
    "Preferences."
)

#: #205 (4.3.8): the tab's notice on the Windows dialog route gains this
#: paragraph after its approved text.
_WIN_DIALOG_NOTICE_EXTRA = (
    "ChromIQ prints the chart at exactly 100% size, centred on the paper, "
    "so choose a paper size in the dialog that the chart fits on. CMYK and "
    "multi-ink charts cannot go through this dialog: ChromIQ tells you if "
    "you try.\n\nWould you rather print without a dialog? Untick \"Use "
    "default Windows printer dialog\" in Preferences. A PostScript printer "
    "then receives the chart directly from ChromIQ, bypassing the printer "
    "driver, so no colour setting can get in the way."
)

#: #205 (4.3.8): the tab's notice on ChromIQ's own Windows route.
_WIN_DIRECT_NOTICE = (
    "⚠  Check that all print settings above match the paper you are "
    "printing on.\n\nWrong media type or quality settings put down the wrong "
    "amount of ink, and the colours you measure will be wrong. Allow "
    "pigment inks to dry fully before measuring (at least 1 h; 24 h for "
    "best accuracy).\n\nChromIQ prints this chart itself, without a print "
    "dialog. A PostScript printer receives the chart directly, bypassing "
    "the printer driver, so nothing can change the colours on the way: it "
    "gets the chart's own colour values at exactly 100% size. The settings "
    "above are part of the print job. Settings made in the printer's own "
    "Properties window in Windows are not used.\n\nA printer that does not "
    "understand PostScript (most home and photo inkjets) gets an RGB chart "
    "through the Windows print dialog, where you switch its colour "
    "adjustment off yourself. ChromIQ does not print a CMYK or multi-ink "
    "chart on such a printer, because its colours would be changed."
)

#: #205 (4.3.8): the options box for a printer whose driver is not PostScript
#: on ChromIQ's own Windows route, in place of the macOS AirPrint box.
_WIN_NOT_POSTSCRIPT_TITLE = "This printer does not understand PostScript"
_WIN_NOT_POSTSCRIPT_BODY = (
    "<b>{printer}</b> uses a printer driver that cannot receive "
    "PostScript, so ChromIQ cannot send the chart to it "
    "directly.<br><br><b>What happens when you click Print:</b><br>• An "
    "<b>RGB chart</b> opens in the Windows print dialog. Check that this "
    "printer is the one chosen at the top of the dialog: Windows 11 opens "
    "it on your default printer, and ChromIQ asks before printing on "
    "another one. Choose the paper and quality there. Then open the "
    "printer's Properties window and switch its colour adjustment "
    "off:<br>&nbsp;&nbsp;– Epson: \"Epson Color Controls\" → Off (No Color "
    "Adjustment)<br>&nbsp;&nbsp;– Canon: \"Color Options\" → Manual → "
    "None<br>&nbsp;&nbsp;– HP: \"Color Options\" → Application Managed "
    "Colors<br>&nbsp;&nbsp;– Others: look for \"No Color Management\", \"Off\" "
    "or \"Application Controlled\"<br>• A <b>CMYK or multi-ink chart</b> "
    "cannot reach this printer without its driver changing the colours, so "
    "ChromIQ does not print it.<br><br>This is normal for most home and "
    "photo inkjet printers. A printer with a PostScript driver, or a RIP "
    "(printing software that controls the printer itself), receives the "
    "chart directly with every colour value unchanged."
)
_WIN_PS_NO_OPTIONS = (
    "This PostScript printer's driver offers no settings to choose here. ChromIQ asks "
    "the printer for a page the size of the chart, so load paper the chart fits on."
)

# ---------------------------------------------------------------------------
# Feature A (#130) — the §6 help and state texts of
# docs/design/verification_printing_and_target.md. The mockup generator
# (scripts/mockup_cm_verification_print.py) renders THESE constants, so the
# document's pictures and the app cannot drift apart.
# ---------------------------------------------------------------------------

_CM_COLOUR_HELP_TITLE = "Printing this chart through your profile"
_CM_COLOUR_HELP_BODY = (
    "This decides how the colours on this sheet are worked out before it is "
    "printed — and it is the setting that makes a verification mean "
    "something.\n\n"
    "**What a verification is for.** When you built your profile, you taught "
    "ChromIQ how your printer and this paper behave together. A verification "
    "asks the follow-up question: does the printer still do what the profile "
    "says it does? Ink settles, paper batches differ, printheads age — so it "
    "is worth checking, and worth checking the same way every time.\n\n"
    "**Through the profile (recommended).** ChromIQ looks up, for every "
    "single patch on the sheet, the exact amount of each ink your profile "
    "predicts will produce that colour. Those amounts are what gets printed. "
    "So the sheet coming out of your printer is your profile's own prediction, "
    "made real — and when you measure it, the difference between what was "
    "promised and what landed on the paper is exactly the number you are "
    "looking for. Pick this one unless you have a particular reason not to.\n\n"
    "**Raw — no profile.** The chart's own numbers go to the printer "
    "untouched, with no profile involved anywhere. This is the right way to "
    "print a chart you are going to build a profile from, because it shows "
    "the printer's raw behaviour. It is the wrong way to check a profile, "
    "because no profile took part — the measurement would describe your "
    "printer, not the profile you wanted to test.\n\n"
    "You do not have to change anything in the print dialog. Whichever you "
    "choose, ChromIQ does all of the colour work itself and hands the printer "
    "a finished sheet, with the printer's own colour adjustment switched off. "
    "That is deliberate: if the printer driver also tried to adjust the "
    "colours, they would be converted twice, the sheet would be wrong, and "
    "nothing afterwards could tell that it had happened.\n\n"
    "Your choice is written onto the report next to the results, because two "
    "sheets printed different ways cannot be compared with each other — and "
    "six months from now, nobody remembers which way a sheet was printed.\n\n"
    "There is also a third way that does not use this tab at all: print the "
    "chart from your own application — Photoshop, for example — with this "
    "run's profile applied there. That checks your everyday printing chain "
    "end to end. When you measure such a sheet, ChromIQ asks how it was "
    "printed and then judges it relative to the sheet's own paper white, "
    "because prints made that way map white to the paper.\n\n"
    "**Default:** through the profile."
)

_CM_INTENT_HELP_TITLE = "Which rendering intent to print with"
_CM_INTENT_HELP_BODY = (
    "Your printer cannot make every colour that exists — no printer can. "
    "Rendering intent is the rule for what happens to the colours it cannot "
    "reach.\n\n"
    "**Relative colorimetric (recommended).** Every colour your printer can "
    "actually make is reproduced exactly, and the few it cannot reach are "
    "moved to the closest colour it can manage. Paper white is treated as "
    "white. This is the usual choice for checking a profile, because it asks "
    "“did you hit the colours you could hit?” without punishing the "
    "printer for the ones nobody could print.\n\n"
    "**Absolute colorimetric.** The same, except that the paper’s own shade "
    "counts too. If your paper is slightly warm or slightly blue, that shows "
    "up as an error on every patch, so the numbers come out higher. Choose "
    "this when you have to match figures somebody else produced this way, or "
    "when the exact paper white matters to you.\n\n"
    "Perceptual and Saturation are meant for photographs and graphics rather "
    "than for measurement. They deliberately shift colours to look pleasing, "
    "which is the opposite of what a measurement wants, so they are here for "
    "completeness rather than for everyday use.\n\n"
    "Whichever you pick is written on the report, because a colour difference "
    "means nothing unless you know how it was produced.\n\n"
    "**Default:** relative colorimetric."
)

_CM_ROUTE_HELP_TITLE = "Printing this chart somewhere other than ChromIQ"
_CM_ROUTE_HELP_BODY = (
    "Pick this when you would rather drive the printer from an application "
    "you trust. ChromIQ then shows you where the sheets are and exactly what "
    "that application must be set to, and prints nothing itself.\n\n"
    "There is one rule, and everything depends on it: nothing between here "
    "and the paper may change the colours. The sheets ChromIQ hands over are "
    "already finished — if another application converts them again, it prints "
    "different colours, your measurement describes those different colours, "
    "and nothing afterwards can tell that it happened.\n\n"
    "**So in the other application:** no output profile, no “let the printer "
    "manage colours”, no proofing or simulation, no scaling or fitting "
    "to page, and no auto-tone or vivid mode.\n\n"
    "Your answer is written on the report, so a surprising result has "
    "somewhere obvious to start.\n\n"
    "**Default:** print here."
)

#: S6 — the on-panel notice while "Through the profile" is selected.
_CM_NOTICE_THROUGH = (
    "ChromIQ will work out the ink amounts your profile predicts for every "
    "patch and print exactly those, so the sheet is your profile’s own "
    "prediction made real. The printer’s own colour adjustment stays "
    "switched off, so nothing between here and the paper changes the "
    "colours.<br><br>"
    "You do not need to change any colour setting in the print dialog. The "
    "finished sheets are kept in the <b>cache</b> folder beside the chart, "
    "which is always safe to delete."
)

#: S6 without its second sentence (combined review of 4.3.5, item b): where
#: the colours ARE converted on the way, on a printer whose driver takes CMYK
#: raster (macOS, or the CUPS filters on the direct route, turn the chart into
#: CMYK) and on a PostScript printer that gets the chart as macOS sends it
#: (its own colour rendering converts it), "The printer’s own colour adjustment
#: stays switched off, so nothing between here and the paper changes the
#: colours." is untrue and is left out.
_CM_NOTICE_THROUGH_CONVERTED_ON_THE_WAY = (
    "ChromIQ will work out the ink amounts your profile predicts for every "
    "patch and print exactly those, so the sheet is your profile’s own "
    "prediction made real.<br><br>"
    "You do not need to change any colour setting in the print dialog. The "
    "finished sheets are kept in the <b>cache</b> folder beside the chart, "
    "which is always safe to delete."
)

#: S7 — the on-panel notice when the run has no built profile (§3.1 A4).
_CM_NOTICE_NO_PROFILE = (
    "<b>There is no finished profile in this run yet</b>, so there is "
    "nothing for ChromIQ to print through. You can still print this sheet "
    "raw and measure it — but the result would describe your printer, not a "
    "profile, so it cannot tell you how accurate a profile is.<br><br>"
    "To get there: set <b>Run type</b> to <b>Profiling</b>, then create, "
    "print and measure the profiling chart as usual, and build the profile "
    "on the <b>Build Profile</b> tab. Come back here afterwards and this "
    "option will be waiting for you."
)

#: S7b — A4 when the PROJECT has a profile, just not in the run the bar points
#: at. The message above sends the user off to build a profile; if they already
#: built one in another run, that is an instruction to redo finished work. A
#: user reported exactly this: run 1 held the profile, the bar was on run 2, and
#: the option stayed greyed while the app said there was nothing to print
#: through. Singular and plural are separate strings, never "run(s)".
_CM_NOTICE_PROFILE_IN_ONE_OTHER_RUN = (
    "<b>The run chosen under “Profile run” has no finished profile</b>, so "
    "there is nothing for ChromIQ to print through while the bar points at "
    "it. {run} of this project has one.<br><br>"
    "Set <b>Profile run</b> at the top of the window to {run} and this option "
    "comes back. A verification is kept inside the run whose profile it "
    "judges, so the sheet has to be printed through that run's profile.<br><br>"
    "You can still print this sheet raw and measure it, but the result would "
    "describe your printer rather than a profile."
)

#: S7c — the same, with more than one other run holding a profile.
_CM_NOTICE_PROFILE_IN_OTHER_RUNS = (
    "<b>The run chosen under “Profile run” has no finished profile</b>, so "
    "there is nothing for ChromIQ to print through while the bar points at "
    "it. These runs of this project have one: {runs}.<br><br>"
    "Set <b>Profile run</b> at the top of the window to the run whose profile "
    "you are verifying and this option comes back. A verification is kept "
    "inside the run whose profile it judges, so the sheet has to be printed "
    "through that run's profile.<br><br>"
    "You can still print this sheet raw and measure it, but the result would "
    "describe your printer rather than a profile."
)

#: §3.1a — the notice for a chart that was converted when it was made.
_CM_NOTICE_ALREADY_CONVERTED = (
    "<b>This chart already has your profile applied, so it prints exactly "
    "as it is.</b><br><br>"
    "When you created it, ChromIQ asked your profile which ink amounts would "
    "produce each of the colours being tested, and stored the answer in the "
    "chart itself. The sheet is your profile’s prediction already — "
    "there is nothing left to convert.<br><br>"
    "That is why “Through the profile” is switched off "
    "here. Applying the profile a second time would print different colours "
    "from the ones being tested, your measurement would faithfully describe "
    "those different colours, and nothing afterwards could tell that it had "
    "happened.<br><br>"
    "You do not need to change anything. Print as usual — and if you print "
    "from another application, simply make sure it does not convert the "
    "colours either."
)

#: A3c — the chart claims stored colorimetric targets but the file is gone.
_CM_NOTICE_REFERENCE_MISSING = (
    "<b>This chart's records say its colours were already converted, but the "
    "stored reference file beside it is missing.</b> ChromIQ plays it safe "
    "and prints the chart exactly as it is — converting it again could not "
    "be undone and could not be detected afterwards. The measurement report "
    "may not be able to use the stored targets until the reference file is "
    "back."
)

#: §3.1b — raw chosen on a regular chart: a different question, not an error.
_CM_NOTICE_RAW_CHOSEN = (
    "<b>Printing raw measures your printer, not your profile.</b><br><br>"
    "The sheet goes to the printer exactly as it is, with no profile "
    "involved. That is useful for one particular question: <i>is my printer "
    "still behaving the way it did last time?</i> Print the same chart the "
    "same way each month and compare the results, and you will see it change "
    "before it becomes visible in your work.<br><br>"
    "What it cannot tell you is how accurate your profile is, because no "
    "profile took part. For that, choose <b>Through the profile</b> above: "
    "then the sheet is your profile’s own prediction, and measuring it "
    "shows how close the prediction came.<br><br>"
    "Whichever you choose is written on the report, so you can always tell "
    "later which of the two questions a set of figures answered."
)


#: The left pane every tab is locked to. `left.setFixedWidth(580)`, here and
#: on Create Chart, Measure and Check & Refine.
PANE_W = 580


def buttons_fit_one_row(hints: "list[int]", spacing: int,
                        pane: int = PANE_W) -> bool:
    """Whether these buttons can sit side by side in the locked pane.

    A FUNCTION, SO THAT THE RULE CAN BE TESTED WITHOUT A SCREEN. The row this
    decides was sized for English metrics and cut all four Ukrainian labels at
    both ends (Sebastian, 2026-09-21); the guard written for it could only be
    proved on a host with the real fonts, because under the offscreen plugin
    the same four buttons genuinely do fit. Feeding the rule its widths is the
    half that can be proved anywhere.

    `hints` are the buttons' own `sizeHint().width()` values: what each needs
    to paint its label with its frame. The margins allowance is the pane's own
    left and right padding.
    """
    return sum(hints) + max(len(hints) - 1, 0) * spacing + 24 <= pane


class _LpReadBack:
    """The read-back of a job ``lp`` created (runs on a background thread)."""

    def __init__(self, printer: str, job_id, expected: dict) -> None:
        self.printer, self.job_id, self.expected = printer, job_id, expected

    def __call__(self):
        from workflow.ppd_color import ppd_path_for_queue
        from workflow.print_ticket import check_job
        ppd_text = None
        ppd = ppd_path_for_queue(self.printer)
        if ppd:
            from core.text_io import read_text
            ppd_text = read_text(Path(ppd), lenient=True)
        return check_job(self.printer, self.job_id, self.expected, ppd_text=ppd_text)


class _DialogReadBack:
    """The read-back of a job the macOS print dialog submitted (background
    thread), which also teaches ChromIQ the paper profile the dialog wrote
    (``workflow.printer_memory``)."""

    def __init__(self, submission) -> None:
        self.submission = submission

    def __call__(self):
        from workflow import native_print_macos as npm
        from workflow.printer_memory import learn_from_report
        rep = npm.read_back(self.submission)
        try:
            learn_from_report(rep)
        except Exception as exc:  # noqa: BLE001 - learning never stops a print
            log.warning("printer memory: could not learn from job %s: %s",
                        rep.job_id, exc)
        return rep



def _reset_vendors(rep) -> set:
    """The vendors (``ppd_color.dialog_route_lock_vendor``) of the driver
    options the macOS dialog route set back for *rep*'s job."""
    from workflow.ppd_color import dialog_route_lock_vendor
    reset = getattr(rep, "reset_by_chromiq", None) or {}
    return {dialog_route_lock_vendor(k) for k in reset} - {None}



def ps_texts(*, proposed: bool = False):
    """``(question, choices, help or None)`` for a PostScript printer on the
    macOS dialog route: the explained wording (Knut, #182 6143186611:
    M-PRINT-PS-ASK-EXPLAINED, M-PRINT-PS-FORM-CHOICE-EXPLAINED and the help
    M-PRINT-PS-FORM-HELP-PROJECT-EXPLAINED, all approved by Knut on
    2026-10-13, #182 6152691121). *proposed* is kept for review drivers; the
    set is the same either way (§M: a proposed text is shown, Knut
    2026-10-14)."""
    from workflow import measurement_messages as MM
    return (MM.M_PRINT_PS_ASK_EXPLAINED, MM.M_PRINT_PS_FORM_CHOICE_EXPLAINED,
            MM.M_PRINT_PS_FORM_HELP_PROJECT_EXPLAINED)

class TabPrint(QWidget):

    ti2_loaded         = pyqtSignal(Path)  # emitted when the user loads a .ti2 file
    ti2_replaced       = pyqtSignal()      # emitted when a different .ti2 file is loaded by the user
    ti2_load_cancelled = pyqtSignal()      # emitted when the cross-tab dialog is cancelled
    chart_relocated    = pyqtSignal(Path)  # emitted when files were copied to a new folder
    chart_load_requested = pyqtSignal(Path, list)  # user loaded a .ti2 here → reflect it in Create Chart
    """Step 2: print the test chart via CUPS."""

    def __init__(
        self,
        settings: "AppSettings",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._module   = PrintModule()
        # #205: ChromIQ's own route on Windows sends a PostScript printer the
        # chart raw through the spooler, with the same call as CUPS' lp
        self._printer  = WindowsRawPrinter() if is_windows() else CupsRawPrinter()
        self._tiff_pages: list[Path] = []
        self._current_ti2: Path | None = None
        self._target_ctl = None          # shared Profile-run / Run-type controller (#130)
        # (ti2, kwargs) for a print record that is written only if a page is
        # actually submitted — see `_apply_verification_colour` (R6 F5).
        self._pending_print_record: "tuple[Path, dict] | None" = None
        # Sequential-enabling state — populated in _rebuild_option_rows
        self._ordered_opts: list[tuple[str, list[str], QComboBox]] = []
        self._raw_value_pairs: dict[str, list[tuple[str, str]]] = {}
        #: beta 16: the note under a Canon/Epson quality row (M-PRINT-QUALITY)
        self._quality_note: QLabel | None = None
        self._quality_choices = None
        self._restoring: bool = False
        self._mode: str = "dark"
        # ---- the printer and its options, per target (Knut, 2026-10-20) ----
        #: The printer the selected target stored (``print_settings["printer"]``
        #: of its meta.json), or None when it has none: then the saved
        #: defaults apply (per_target_settings.md §5a).
        self._target_printer: "str | None" = None
        #: The selected target's stored options, per queue
        #: (``print_settings["printer_options"]``); a queue missing here opens
        #: on its saved defaults (``print_opts_<queue>``).
        self._target_printer_opts: "dict[str, dict[str, str]]" = {}
        #: The store (its folder) whose settings are on screen. A write goes to
        #: that store only: values loaded for run 1 are never filed onto run 2.
        self._print_loaded_for: "str | None" = None
        #: True once the USER changed the printer or an option row since the
        #: last load. Only then are they written: a target that is merely
        #: looked at keeps nothing stored (§4 S4/S9), whatever the app itself
        #: preselects for the chart (review of fix/4.3.8, D1), and a stored
        #: printer that is no longer installed is kept (PS-8, D4).
        self._printer_dirty: bool = False
        #: True when the target on screen was seeded from the run it was made
        #: from (§4a, PS-6): then the seed is written like a choice.
        self._printer_seeded: bool = False
        #: Where a run made in this session came from, as the bar saw it
        #: (review D2/D3): {(project folder, run id): source}, a source being
        #: ("run", id) / ("verification", id) or None (the calibration, N-6).
        self._print_born_from: dict = {}
        #: The target and the run ids at the bar's last change, and the target
        #: "New run" was chosen from.
        self._print_prev: "tuple | None" = None
        self._print_new_run_source = None

        self._build_ui()

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Restyle the AirPrint info box when the theme changes."""
        from ui.theme import accept_mode
        new_mode = accept_mode(mode)
        if new_mode == self._mode:
            return
        self._mode = new_mode
        # If the AirPrint box is currently shown, restyle it in place.
        box = self.findChild(QFrame, "airprintInfoBox")
        if box is not None:
            self._apply_airprint_box_styles(box)
        # …and the printer-edge note, which takes its colours from the mode
        if getattr(self, "_edge_note_lbl", None) is not None \
                and self._edge_note_lbl.isVisible():
            self._update_edge_note()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ---- Left controls ----
        left = QWidget(self)
        self._left_panel = left
        left.setFixedWidth(580)
        left.setStyleSheet("QPushButton { min-height: 44px; }")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(16, 12, 16, 12)
        ll.setSpacing(10)

        _initial_tt_title, _initial_tt_body = self._compute_print_tooltip()
        # Amber grid button at the far right of the title row — loads an existing
        # target's .ti2 so it can be reprinted. Mirrors the Create Chart tab's
        # folder/grid/star trio, in this tab's amber accent (#70, Knut). Replaces
        # the old bottom-row "Load existing target" button.
        # MOVED TO THE MASTHEAD (#130, spec agreed 2026-07-31). These acted on
        # the whole app rather than on one tab, and Load .ti2 existed twice —
        # once here and once on the other tab. Both now live top-left in the
        # masthead; see MastheadHeader.load_project_clicked / load_ti2_clicked.
        # "Load image" (#117, Knut): print ANY TIFF through ChromIQ's raw,
        # colour-management-free pipeline — charts made by other tools, test
        # images. Print-only: measuring still needs the chart's .ti2.
        from ui.widgets import ImageFileButton
        self._load_image_btn = ImageFileButton(SPEC_AMBER, left)
        self._load_image_btn.setToolTip(
            tr("Load image (TIFF).\n"
               "Open any TIFF, for example a chart made by another tool, "
               "and print it exactly like a chart: without colour "
               "management.\n"
               "Printing only: to MEASURE a chart afterwards, open its .ti2 "
               "with “Open Chart File (.ti2)” at the top left of the "
               "window instead, so ChromIQ knows its patches."))
        self._load_image_btn.clicked.connect(self._on_load_image)
        _trailing = QWidget(left)
        _tl = QHBoxLayout(_trailing)
        _tl.setContentsMargins(0, 0, 0, 0)
        _tl.setSpacing(6)
        # Order: load image, then reveal folder. "Load test chart" used to lead
        # this row; it moved to the masthead (#130) so one button serves the
        # whole app instead of one per tab.
        _tl.addWidget(self._load_image_btn)
        from ui.widgets import RevealFolderButton
        self._reveal_btn = RevealFolderButton(SPEC_AMBER, _trailing)
        self._reveal_btn.setToolTip(tr(
            "Open this chart's folder in {manager} — where "
            "the printable pages live. Handy if you'd rather print the pages "
            "from another application.").format(manager=file_manager_name()))
        self._reveal_btn.clicked.connect(self._reveal_folder)
        _tl.addWidget(self._reveal_btn)
        self._header = TabHeader(
            tr("STEP 02 · PRINT CHART"), tr("Print test chart"), "#ffb42d", left,
            tooltip_title=_initial_tt_title,
            tooltip_body=_initial_tt_body,
            trailing_widget=_trailing,
        )
        ll.addWidget(self._header)

        # Printer selection (pinned above scroll area)
        self._printer_grp = QGroupBox(tr("Printer"), left)
        printer_grp = self._printer_grp
        pg = QVBoxLayout(printer_grp)

        pr_row = QHBoxLayout()
        pr_row.addWidget(QLabel(tr("Printer:"), left))
        self._printer_combo = NoScrollComboBox(left)
        pr_row.addWidget(self._printer_combo, stretch=1)

        refresh_btn = QPushButton(left)
        refresh_btn.setIcon(load_refresh_icon("refresh_print"))
        refresh_btn.setFixedSize(34, 34)
        refresh_btn.setStyleSheet("QPushButton { padding: 0; min-height: 0; }")
        refresh_btn.setToolTip(tr("Refresh printer list"))
        refresh_btn.clicked.connect(self._refresh_printers)
        pr_row.addWidget(refresh_btn)

        if is_macos():
            # Beta 15 (approved by Sebastian, 2026-10-08): the colour sentences
            # were untrue for a Canon or Epson on macOS.
            _printer_tip = tr(
                "Select the printer to send the chart to. Only printers installed "
                "in the system CUPS print queue are listed.\n\n"
                "A Canon or Epson gets the chart as a TIFF (or exact-size PDF) with "
                "the medium's paper profile attached, as a Photoshop print. Other "
                "printers get PostScript first, then the TIFF (or exact-size PDF), "
                "with colour management switched off.\n\n"
                "ChromIQ knows the paper profiles of the Canon and Epson models "
                "whose drivers it can read or which it has measured, and learns any "
                "other model one paper type at a time, from a print through the "
                "macOS print dialog.")
        else:
            _printer_tip = tr(
                "Select the printer to send the chart to.  Only printers installed in\n"
                "the system CUPS print queue are listed.\n\n"
                "ChromIQ converts the chart to PostScript and sends it via lp —\n"
                "bypassing ColorSync entirely.  If CUPS rejects PostScript (e.g.\n"
                "AirPrint or Driverless drivers), it automatically retries by sending\n"
                "the TIFF directly with colour-space-aware raster options.\n"
                "Colour management is always disabled automatically.")
        pr_row.addWidget(TooltipButton(tr("Printer Selection"), _printer_tip, left))
        pg.addLayout(pr_row)
        ll.addWidget(printer_grp)

        # Scrollable content area (options + warning)
        scroll = FadeScrollArea(left)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        scl = QVBoxLayout(scroll_content)
        scl.setContentsMargins(0, 0, 0, 0)
        scl.setSpacing(10)

        # "How this chart is printed" — feature A (#130): the reconciled
        # three-row section of verification_printing_and_target.md §4. Colour
        # and Rendering intent appear only for a verification; Route is shown
        # for every chart. Stays visible in native-dialog mode too — the
        # conversion happens before either print path. INSIDE the scroll area
        # (Basti, 2026-08-09): pinned above it, this section squeezed Print
        # Options down to a sliver — when space runs out, the info boxes and
        # every option scroll together instead of one section alone.
        self._build_cm_section(scroll_content, scl)

        # Print options — dynamically built from CUPS lpoptions output
        self._opts_grp = QGroupBox(tr("Print Options"), scroll_content)
        self._opts_layout = QVBoxLayout(self._opts_grp)
        self._option_combos: dict[str, QComboBox] = {}
        self._opts_layout.addWidget(
            QLabel(tr("Select a printer to see its options."), scroll_content)
        )
        scl.addWidget(self._opts_grp)

        self._printer_combo.currentIndexChanged.connect(self._on_printer_picked)

        # Warning label — inside the scroll area too (same request): it is an
        # info box, and it is tall.
        self._warn_lbl = QLabel("", scroll_content)
        self._warn_lbl.setObjectName("warning")
        self._warn_lbl.setWordWrap(True)
        scl.addWidget(self._warn_lbl)

        # M-PRINT-VERIFY-ROUTE (approved by Basti, 2026-10-10): what a
        # verification print needs, under the notice above, on macOS, for a
        # verification run with a chart loaded (``_update_verify_route_note``).
        self._verify_route_lbl = QLabel("", scroll_content)
        self._verify_route_lbl.setObjectName("warning")
        self._verify_route_lbl.setWordWrap(True)
        self._verify_route_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._verify_route_lbl.setVisible(False)
        scl.addWidget(self._verify_route_lbl)

        scl.addStretch()
        scroll.setWidget(scroll_content)
        ll.addWidget(scroll, stretch=1)

        # Spacer below warn label; shown only in native mode to vertically centre the label
        self._native_warn_spacer = QWidget(left)
        self._native_warn_spacer.setVisible(False)
        ll.addWidget(self._native_warn_spacer, stretch=1)

        # Feed the beast block
        beast_box = QGroupBox(left)
        # Only override layout (no title → zero top-margin + tight padding);
        # let border + radius come from the global QGroupBox theme.
        beast_box.setStyleSheet(
            "QGroupBox { margin-top: 0px; padding: 14px 8px 12px 8px; }"
        )
        beast_layout = QVBoxLayout(beast_box)
        beast_layout.setContentsMargins(0, 0, 0, 0)
        beast_layout.setSpacing(4)
        beast_headline = QLabel(beast_box)
        # The mark the headline ends in is an inline colour, which beats the
        # stylesheet -- so it kept its hue in a theme that has none. Resolved
        # through the appearance, and re-resolved on a live switch.
        set_accent_html(
            beast_headline,
            tr("Feed the beast<span style=\"color: {SPEC_AMBER}; font-style: italic;\">!</span>"),
            SPEC_AMBER=SPEC_AMBER)
        beast_headline.setTextFormat(Qt.TextFormat.RichText)
        beast_headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        beast_headline.setStyleSheet(
            "background: transparent;"
            " font-family: Georgia; font-size: 28px;"
        )
        beast_layout.addWidget(beast_headline)
        beast_subtext = QLabel(tr("Your printer is hungry."), beast_box)
        beast_subtext.setAlignment(Qt.AlignmentFlag.AlignCenter)
        beast_subtext.setStyleSheet(
            "color: #808080; background: transparent;"
            " font-family: Menlo; font-size: 9px; font-weight: 300;"
        )
        beast_layout.addWidget(beast_subtext)
        beast_bar = QHBoxLayout()
        beast_bar.setContentsMargins(0, 6, 0, 0)
        beast_bar.setSpacing(0)
        beast_bar.addStretch()
        # Decoration, not a readout: the same five cells on every tab. One
        # ACTION value under Neutral, and the hue kept on each cell so a live
        # appearance switch repaints it -- see ui.widgets.spectrum_cell.
        for _color in TAB_COLORS:
            beast_bar.addWidget(spectrum_cell(beast_box, _color))
        beast_bar.addStretch()
        beast_layout.addLayout(beast_bar)
        ll.addWidget(beast_box)

        # Print buttons
        btn_row = QHBoxLayout()
        self._print_page_btn = QPushButton(tr("Print\nCurrent Page"), left)
        self._print_page_btn.setObjectName("primary")
        self._print_page_btn.clicked.connect(self._on_print_current)

        self._print_all_btn = QPushButton(tr("Print All\nPages"), left)
        self._print_all_btn.clicked.connect(self._on_print_all)

        self._save_defaults_btn = QPushButton(tr("Save as\nDefaults"), left)
        self._save_defaults_btn.clicked.connect(self._on_save_defaults)

        self._clear_queue_btn = QPushButton(tr("Clear\nPrint Queue"), left)
        self._clear_queue_btn.setToolTip(
            tr("Cancel all pending and stuck jobs for the selected printer.")
        )
        self._clear_queue_btn.clicked.connect(self._on_clear_queue)

        # ONE ROW, ALWAYS, AND THE TEXT MADE TO FIT INSIDE IT.
        #
        # Sebastian photographed this row in Ukrainian on 2026-09-21 and all
        # four buttons were cut at BOTH ends -- `Роздрукувати / оточна сторінк`,
        # `оздрукувати вс / сторінки`, `ясно / Черга друк`, `Зберегти як /
        # а замовчування`. Losing the first character as well as the last is
        # the tell that the label is wider than the control and centred, not
        # that it is running off to the right.
        #
        # Measured in a real window, this pane being locked to 580 px: in
        # ENGLISH each button's width is exactly its own `minimumSizeHint`, so
        # the row fits with nothing at all to spare, and in Ukrainian the four
        # wanted 154 + 153 + 117 + 158 = 582 px before a pixel of spacing.
        #
        # The first fix let the ROW wrap onto two lines and he rejected it in
        # the same breath: *"buttons on the bottom are now in two rows, but
        # should be one like everywhere else"*. So the row stays one row and
        # the LABELS re-flow inside their own buttons, which is what English
        # already does ("Print / Current Page"). `rewrap_button_label` only
        # moves the line break; no word is shortened, split or dropped, and the
        # unbroken label goes on as the tooltip.
        _btns = (self._print_page_btn, self._print_all_btn,
                 self._clear_queue_btn, self._save_defaults_btn)
        # What one button may take: the pane, less its margins and the gaps
        # between four buttons, split four ways, less the frame each one draws
        # around its text. The chrome figure is measured from the button
        # itself rather than assumed.
        from PyQt6.QtGui import QFontMetrics
        _gaps = 3 * max(btn_row.spacing(), 0) + 24
        _chrome = max(
            (b.minimumSizeHint().width()
             - max(QFontMetrics(b.font()).horizontalAdvance(line)
                   for line in (b.text() or " ").split("\n"))
             for b in _btns), default=40)
        # …AND ONLY WHEN THE ROW ACTUALLY NEEDS IT. A per-button quarter share
        # is stricter than the row is: it took "Друк поточної / сторінки",
        # which fits perfectly well, onto three lines. So the labels are left
        # exactly as the translator broke them whenever the four fit as they
        # are, and re-flowed only when they do not.
        if not buttons_fit_one_row([b.sizeHint().width() for b in _btns],
                                   max(btn_row.spacing(), 0)):
            _room = max((PANE_W - _gaps) // len(_btns) - _chrome, 40)
            for _b in _btns:
                rewrap_button_label(_b, _room)

        btn_row.addWidget(self._print_page_btn)
        btn_row.addWidget(self._print_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._clear_queue_btn)
        btn_row.addWidget(self._save_defaults_btn)
        ll.addLayout(btn_row)

        # Status — hidden when empty so it doesn't add gap below buttons
        self._status_lbl = QLabel("", left)
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setVisible(False)
        ll.addWidget(self._status_lbl)

        # THE EDGE THIS PRINTER DOES NOT PRINT (Basti, 2026-10-25, jctay's
        # forum post 149836): a gentle note, never a block
        # (`_update_edge_note`, `workflow.printer_edges`).
        self._edge_note_lbl = QLabel("", left)
        self._edge_note_lbl.setWordWrap(True)
        self._edge_note_lbl.setObjectName("warn")
        self._edge_note_lbl.setVisible(False)
        ll.addWidget(self._edge_note_lbl)

        # Status bar (replaces main-window status bar)
        self._status_bar_lbl = QLabel("", left)
        self._status_bar_lbl.setWordWrap(True)
        self._status_bar_lbl.setVisible(False)
        ll.addWidget(self._status_bar_lbl)

        splitter.addWidget(left)

        # ---- Right preview ----
        right = QWidget(self)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 12)
        rl.setSpacing(0)
        self._preview = TiffPreview(right)
        # beta 12: a run's chart page is shown as it will print
        self._preview.set_print_preview(True)
        # the indicator's icon carries this tab's own accent (Basti)
        from ui.styles import SPEC_AMBER as _chip_accent
        self._preview.set_chip_accent(_chip_accent)
        self._preview.set_caption(tr("PRINT PREVIEW"))
        rl.addWidget(self._preview, stretch=1)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # Initial state
        self._set_print_buttons_enabled(False)
        # ASKING CUPS IS DEFERRED TO THE FIRST TIME THIS TAB IS SHOWN.
        #
        # `_refresh_printers` shells out twice — `detect_printers`, then
        # `_on_printer_changed` → `query_options` — and both were run while the
        # main window was still being built, for a tab most sessions never
        # open. Measured 2026-08-07: 73 ms of the startup, spent waiting on an
        # external process.
        #
        # Nothing outside this tab reads the printer list (the only consumers
        # are `_on_printer_changed` and the print call itself), and the user
        # cannot press a button on a tab they have not looked at — so there is
        # no window in which the list can be needed but empty.
        self._printers_loaded = False
        self._restore_defaults()
        self.apply_native_dialog_mode()

    def showEvent(self, event) -> None:         # noqa: N802 — Qt's name
        """Load the printer list the first time the tab is actually looked at,
        and re-read the Colour row on every entry — its forced/free state
        depends on files on disk (the chart's colorimetric-reference marker,
        the run's profile) which can change while this tab is hidden."""
        super().showEvent(event)
        if not getattr(self, "_printers_loaded", False):
            self._printers_loaded = True
            try:
                self._refresh_printers()
            except Exception:      # noqa: BLE001 — never block showing the tab
                log.warning("Could not load the printer list", exc_info=True)
        try:
            self._update_colour_row_visible()
        except Exception:      # noqa: BLE001 — never break tab switching
            log.warning("colour row refresh on show failed", exc_info=True)
        try:
            self._update_cmyk_route_note()
        except Exception:      # noqa: BLE001 — never break tab switching
            log.warning("CMYK route note refresh on show failed", exc_info=True)

    def reload_printers(self) -> None:
        """Ask CUPS again — for callers that need the list refreshed on demand."""
        self._printers_loaded = True
        self._refresh_printers()

    # ------------------------------------------------------------------

    def load_tiffs(self, paths: list[Path]) -> None:
        """Called by main window after chart generation."""
        self._tiff_pages = paths
        if paths:
            self._preview.set_notice(None)     # a real chart — drop guidance
        self._preview.load_tiff(paths)
        self._set_print_buttons_enabled(bool(paths))
        self._update_colour_row_visible()
        self._preselect_paper_for_chart()
        self._update_edge_note()

    def has_pages(self) -> bool:
        """Whether this tab currently holds printable page images.

        Asked by the masthead's Load .ti2 button, which took over from the two
        per-tab buttons: Print is the tab that notices a .ti2 arriving without
        its pages, and that message had to survive the move (#130).
        """
        return bool(self._tiff_pages)

    def set_chart_notice(self, text: "str | None") -> None:
        """Show guidance in the preview when there's no chart to print for the
        selected Profile-run / Run-type (#130, Knut)."""
        self._preview.set_notice(text)

    def set_target_controller(self, controller) -> None:
        """Receive the shared Profile-run / Run-type controller (#130) so loading
        a chart here honours the bar exactly like the Measure tab."""
        self._target_ctl = controller
        if controller is not None:
            # A run-type or run change moves the Colour/Intent rows in or out
            # (§3.1 table) — recompute rather than wait for the next tab visit.
            controller.changed.connect(self._update_colour_row_visible)
            # Where a new run comes from is a fact of the bar, not of this
            # tab's screen (review D2/D3): noted at every change, read when
            # the new run is first loaded here.
            controller.changed.connect(self._note_target_change)
            self._note_target_change()

    # ------------------------------------------------------------------
    # Feature A (#130) — printing a verification chart through its profile.
    # Specification: docs/design/verification_printing_and_target.md §3–§5.
    # ------------------------------------------------------------------

    def _build_cm_section(self, left: QWidget, ll: QVBoxLayout) -> None:
        """The three-row §4 section: Colour · Rendering intent · Route, plus
        the state notice below them. Built hidden; `_update_colour_row_visible`
        decides what shows for the selected target."""
        from ui.tooltip_button import TooltipButton

        self._cm_grp = QGroupBox(tr("How this chart is printed"), left)
        gl = QVBoxLayout(self._cm_grp)
        gl.setSpacing(8)

        def row(label: str, control: QWidget, tip_title: str,
                tip_body: str) -> QWidget:
            # A one-row form that puts the control UNDER its label when the
            # two do not fit side by side (4.3.5, review R5 k74): in Russian
            # the intent list ("Относительный колориметрический
            # (рекомендуется)") and the Colour radios of a chart that is
            # already converted made this box 582 points wide in a 534-point
            # pane at 1280 wide, and its right edge was cut off. Where they
            # fit, the row is laid out exactly as before.
            r = QWidget(self._cm_grp)
            form = QFormLayout(r)
            form.setContentsMargins(0, 0, 0, 0)
            form.setHorizontalSpacing(10)
            form.setVerticalSpacing(4)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
            form.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft
                                   | Qt.AlignmentFlag.AlignVCenter)
            form.setFormAlignment(Qt.AlignmentFlag.AlignLeft
                                  | Qt.AlignmentFlag.AlignTop)
            text = QLabel(label, r)
            text.setMinimumWidth(130)
            field = QWidget(r)
            fl = QHBoxLayout(field)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(10)
            fl.addWidget(control, 1)
            fl.addWidget(TooltipButton(tip_title, tip_body, field))
            form.addRow(text, field)
            return r

        # -- Colour: through the profile, or raw (verification only) --------
        # Side by side (Basti, 2026-08-09), with labels short enough that the
        # pair fits the 580 px panel in every language — the first version's
        # longer labels clipped mid-letter.
        choice = QWidget(self._cm_grp)
        cl = QHBoxLayout(choice)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(14)
        self._cm_through_rb = QRadioButton(tr("Through the profile"), choice)
        self._cm_raw_rb = QRadioButton(tr("Raw — no profile"), choice)
        self._cm_through_rb.setChecked(True)
        cl.addWidget(self._cm_through_rb)
        cl.addWidget(self._cm_raw_rb)
        cl.addStretch(1)
        self._cm_colour_row = row(tr("Colour"), choice,
                                  tr(_CM_COLOUR_HELP_TITLE),
                                  tr(_CM_COLOUR_HELP_BODY))
        gl.addWidget(self._cm_colour_row)

        # -- Rendering intent (verification only, and only when converting) -
        self._cm_intent_combo = NoScrollComboBox(self._cm_grp)
        self._cm_intent_combo.setMinimumHeight(30)
        for label, name in (
                (tr("Relative colorimetric (recommended)"), "relative"),
                (tr("Absolute colorimetric"), "absolute"),
                (tr("Perceptual"), "perceptual"),
                (tr("Saturation"), "saturation")):
            self._cm_intent_combo.addItem(label, name)
        self._cm_intent_row = row(tr("Rendering intent"),
                                  self._cm_intent_combo,
                                  tr(_CM_INTENT_HELP_TITLE),
                                  tr(_CM_INTENT_HELP_BODY))
        gl.addWidget(self._cm_intent_row)

        # -- Route: printed here, or handed to another application ----------
        route = QWidget(self._cm_grp)
        rl = QHBoxLayout(route)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)
        self._cm_route_here_rb = QRadioButton(tr("Print here"), route)
        self._cm_route_ext_rb = QRadioButton(
            tr("In another application"), route)
        self._cm_route_here_rb.setChecked(True)
        rl.addWidget(self._cm_route_here_rb)
        rl.addWidget(self._cm_route_ext_rb)
        rl.addStretch(1)
        self._cm_route_row = row(tr("Route"), route,
                                 tr(_CM_ROUTE_HELP_TITLE),
                                 tr(_CM_ROUTE_HELP_BODY))
        gl.addWidget(self._cm_route_row)

        # -- PostScript printer: its own RGB, or as macOS sends it ----------
        # 4.3.5 beta 2 (Basti, 2026-10-12): on the macOS dialog route a
        # PostScript printer gets the chart as its own RGB (k81, as Photoshop
        # sends a photo with "Photoshop Manages Colors") or as macOS sends it
        # (CIEBased, as Preview and 4.3.4). Kept per RUN, so the profiling
        # chart and its verification charts go the same way. Its words are
        # M-PRINT-PS-FORM-CHOICE / -HELP; the stored choice and its default
        # work regardless (``_ps_form``).
        from workflow import measurement_messages as _MM
        _ps_choice_msg, _ps_help_explained = ps_texts()[1:]
        _ps_label, _ps_lines = _ps_choice_msg.render()
        _ps_lines = _ps_lines.split("\n")
        ps_choice = QWidget(self._cm_grp)
        # ONE ABOVE THE OTHER (combined review of beta 2): side by side the
        # two approved choices made the box 547 px wide in English and up to
        # 677 in Russian, in a 534 px pane, so its right edge was cut off.
        pl = QVBoxLayout(ps_choice)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(4)
        self._ps_device_rb = QRadioButton(_ps_lines[0], ps_choice)
        self._ps_macos_rb = QRadioButton(_ps_lines[1], ps_choice)
        self._ps_device_rb.setChecked(True)
        pl.addWidget(self._ps_device_rb)
        pl.addWidget(self._ps_macos_rb)
        # 4.3.5 beta 2 (Basti, 2026-10-13): the row is shown only once the
        # run has a choice (asked after the dialog), and then says when it
        # applies: M-PRINT-PS-FORM-APPLIES
        ps_box = QWidget(self._cm_grp)
        pv = QVBoxLayout(ps_box)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(2)
        pv.addWidget(ps_choice)
        # the project-rule wording (M-PRINT-PS-FORM-APPLIES-PROJECT, final
        # review of beta 2)
        _applies = _MM.M_PRINT_PS_FORM_APPLIES_PROJECT
        self._ps_applies_lbl = QLabel(_applies.render()[1], ps_box)
        self._ps_applies_lbl.setWordWrap(True)
        pv.addWidget(self._ps_applies_lbl)
        ps_choice = ps_box
        # the help: the project rule and the explained choices
        # (M-PRINT-PS-FORM-HELP-PROJECT-EXPLAINED, Knut 2026-10-13) through
        # ps_texts
        _ps_help = _ps_help_explained
        self._ps_form_row = row(_ps_label, ps_choice, *_ps_help.render())
        self._ps_form_row.setVisible(False)
        gl.addWidget(self._ps_form_row)

        ll.addWidget(self._cm_grp)

        # -- the state notice (S6 / S7 / §3.1a / §3.1b) ---------------------
        # Below the group rather than inside it (as the mockups show): a
        # word-wrapped label nested in the group box clipped its own last
        # lines in the scroll area, while a sibling of the group renders in
        # full — the same placement the tab's other warning box uses.
        self._cm_notice = QLabel("", left)
        self._cm_notice.setObjectName("warning")
        self._cm_notice.setWordWrap(True)
        self._cm_notice.setTextFormat(Qt.TextFormat.RichText)
        ll.addWidget(self._cm_notice)
        self._cm_grp.setVisible(False)
        self._updating_cm = False
        #: The user's own Colour choice for the selected target — kept apart
        #: from the radios because a forced state (§3.1a, A4) must not
        #: overwrite what the user chose when the force lifts.
        self._cm_user_colour: "str | None" = None
        self._print_written: dict = {}       # per-store snapshot (§3a Q-4)

        self._cm_through_rb.toggled.connect(self._on_cm_selection_changed)
        self._cm_raw_rb.toggled.connect(self._on_cm_selection_changed)
        self._updating_ps_form = False
        self._ps_device_rb.toggled.connect(self._on_ps_form_changed)
        # beta-12 review: the preview converts through the profile in the
        # chosen intent, so a new intent must reach it too (the radios above
        # already do, through `_update_colour_row_visible`)
        self._cm_intent_combo.currentIndexChanged.connect(
            self._on_cm_intent_changed)

    def _on_cm_intent_changed(self, *_a) -> None:
        """Show the sheet in the Rendering intent just chosen (beta 12,
        Knut 6045500910 Q4): the preview converts exactly as the print will."""
        if getattr(self, "_updating_cm", False):
            return
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None or not ctl.target.is_verification() \
                or not self._tiff_pages:
            return
        self._preview.set_print_preview(
            True, colour=self._cm_selected_colour(),
            intent=self._cm_selected_intent())

    def _on_cm_selection_changed(self, *_a) -> None:
        """Follow a user click on the Colour radios: remember the choice and
        refresh the notice + intent row (§3.1b — the notice names the question
        the selected way of printing will answer)."""
        if getattr(self, "_updating_cm", False):
            return
        from workflow import verification_print as vp
        if self._cm_through_rb.isEnabled():
            self._cm_user_colour = (vp.COLOUR_THROUGH
                                    if self._cm_through_rb.isChecked()
                                    else vp.COLOUR_RAW)
        self._update_colour_row_visible()

    def _cm_run(self):
        """The Run the bar points at, or None (no project / no controller)."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return None
        try:
            project = ctl.project_or_none()
            if project is None:
                return None
            from core.measurement_target import resolve_run
            return resolve_run(project, ctl.target)
        except Exception:      # noqa: BLE001 — a question must never raise
            return None

    # ---- the PostScript printer's form (4.3.5 beta 2) ---------------------
    #: THE CHOICE BELONGS TO THE PROJECT (Basti, 2026-10-13): the calibration
    #: is the first step and the profiling runs follow it, so the first print
    #: to a PostScript printer through the macOS dialog asks, whichever chart
    #: it is, and the answer is kept in ``project.json``
    #: (``Project.print_setting("postscript")``). The calibration prints with
    #: it; every run inherits it; a run may have its own (the row on this tab,
    #: ``print_settings["postscript"]`` of its ``meta.json``), and a run
    #: refined from another (RunMeta.parent_run) keeps its parent's.
    def _ps_form_run(self):
        """The Run whose own PostScript form applies: the run the bar points
        at, for its profiling chart AND its verification charts (they must go
        the same way); None for a calibration, a new run, or no project."""
        ctl = getattr(self, "_target_ctl", None)
        try:
            if ctl is None or ctl.target.is_calibration() or ctl.target.is_new_run():
                return None
        except Exception:  # noqa: BLE001
            return None
        return self._cm_run()

    def _ps_project(self):
        """The open project, whose choice every target inherits; None when
        there is none (or it cannot be told)."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return None
        try:
            return ctl.project_or_none()
        except Exception:  # noqa: BLE001 - a question must never raise
            return None

    def _ps_form(self) -> str:
        """The form a PostScript printer gets the chart in on the macOS dialog
        route (``_ps_form_stored``), else the default, its own RGB."""
        from workflow import ppd_color as forms
        return self._ps_form_stored() or forms.DEFAULT_POSTSCRIPT_FORM

    def _dialog_setting_changes(self) -> int:
        """How many times "Use default macOS printer dialog" was switched
        (``core.settings`` "print_dialog_setting_changes")."""
        try:
            return int(self._settings.get("print_dialog_setting_changes", 0) or 0)
        except Exception:  # noqa: BLE001 - a count must never raise
            return 0

    def _ps_project_form(self) -> "str | None":
        """The project's choice, or None when there is none or it was made
        before "Use default macOS printer dialog" was last switched: then the
        project asks again at the next print to a PostScript printer through
        the dialog (Knut, #182, 2026-10-13). A run's own choice (the row) is
        kept.

        ONLY THE DIALOG ROUTE ASKS AGAIN (combined review of beta 4). With
        the setting switched OFF the choice still answers: the direct route
        never asks the PostScript question, and its own question before
        printing a "let the printer adjust" project as unchanged colours
        (M-PRINT-DIRECT-LIKE-PREVIEW, P14) reads this choice. Discarding it
        there turned that question off for exactly the user it was made for,
        whose project chose on the dialog route and who then switched to
        ChromIQ's own route."""
        from workflow import ppd_color as forms
        project = self._ps_project()
        try:
            got = project.print_setting("postscript") if project is not None else None
            dialog_route = bool(self._settings.get("use_native_print_dialog", False))
            if got is not None and dialog_route:
                asked_at = int(project.print_setting("postscript_dialog_changes") or 0)
                if asked_at != self._dialog_setting_changes():
                    return None
        except Exception:  # noqa: BLE001 - a default must never raise
            got = None
        return got if got in forms.POSTSCRIPT_FORMS else None

    def _ps_run_own_form(self, run, depth: int = 0) -> "str | None":
        """*run*'s own choice, else (a run refined from another) its parent's
        own, up the chain; None when no run of the chain has one."""
        from workflow import ppd_color as forms
        try:
            meta = run.load_meta()
            got = (getattr(meta, "print_settings", None) or {}).get("postscript")
            if got in forms.POSTSCRIPT_FORMS:
                return got
            # Combined review of 4.3.5 beta 2: a run refined from another
            # ("Use as Pre-conditioning", RunMeta.parent_run) prints the way
            # its parent did until it is given its own choice, so a second
            # pass does not silently fall back to the default.
            parent = getattr(meta, "parent_run", None)
            project = getattr(run, "_project", None)
            if parent and project is not None and depth < 32:
                return self._ps_run_own_form(project.run(parent), depth + 1)
        except Exception:  # noqa: BLE001 - a default must never raise
            return None
        return None

    def _ps_form_stored(self) -> "str | None":
        """The form chosen for the selected target: the run's own (or its
        parent's), else the project's; None when nothing was chosen yet.

        A VERIFICATION chart (4.3.8, Knut's run 6): after the run's own choice
        on the row, the form its profiling chart was recorded printed in
        (``_profiling_chart_form``) comes before the parent's and the
        project's. That is a fact about this run's sheet, not a preference:
        on a PostScript printer the two forms print measurably different
        colours, so the verification chart must go the same way."""
        run = self._ps_form_run()
        if run is not None:
            if self._target_is_verification():
                explicit = self._ps_run_explicit_form(run)
                if explicit is not None:
                    return explicit
                recorded = self._profiling_chart_form(run)
                if recorded:
                    return recorded
            own = self._ps_run_own_form(run)
            if own is not None:
                return own
        return self._ps_project_form()

    def _target_is_verification(self) -> bool:
        ctl = getattr(self, "_target_ctl", None)
        try:
            return bool(ctl is not None and ctl.target.is_verification())
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _ps_run_explicit_form(run) -> "str | None":
        """*run*'s own choice from the row (its ``meta.json``), not inherited."""
        from workflow import ppd_color as forms
        try:
            got = (getattr(run.load_meta(), "print_settings", None) or {}).get("postscript")
        except Exception:  # noqa: BLE001
            return None
        return got if got in forms.POSTSCRIPT_FORMS else None

    @staticmethod
    def _profiling_chart_record(run) -> "dict | None":
        """The print record of *run*'s profiling chart, or None."""
        from workflow import verification_print as vp
        try:
            rec_path = vp.print_record_path(Path(run.chart_ti2))
            if not rec_path.is_file():
                return None
            import json as _json
            data = _json.loads(rec_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a record never stops a print
            return None
        return data if isinstance(data, dict) else None

    def _profiling_chart_form(self, run) -> str:
        """The PostScript form *run*'s profiling chart was printed in, as its
        print record says (4.3.8 and later), else ""."""
        from workflow import verification_print as vp
        return vp.recorded_postscript_form(self._profiling_chart_record(run))

    def _is_postscript_queue(self, printer: str) -> bool:
        """True when *printer*'s PPD makes it a PostScript queue."""
        from workflow import ppd_color as forms
        try:
            ppd = forms.ppd_path_for_queue(printer) if printer else None
            if not ppd:
                return False
            from core.text_io import read_text
            return forms.is_postscript_queue(read_text(Path(ppd), lenient=True))
        except Exception:  # noqa: BLE001 - a question must never stop a print
            return False

    def _note_print_path(self, path: str, printer: str, postscript: str = "") -> None:
        """Add which way the sheet goes to the held print record (4.3.8)."""
        pending = getattr(self, "_pending_print_record", None)
        if pending is None:
            return
        _ti2, kwargs = pending
        kwargs["path"] = path
        kwargs["printer"] = printer or ""
        kwargs["postscript"] = postscript or ""

    def _ps_form_can_be_asked(self) -> bool:
        """Whether a target with no choice is asked after the dialog (Basti,
        2026-10-13): a project to keep the answer. Otherwise the default form
        is used, as before."""
        return self._ps_project() is not None

    def _ps_form_for_dialog(self) -> "str | None":
        """What ``print_frames`` gets as *postscript_form*: the stored choice;
        None (ask after the dialog) when there is none and it can be asked;
        else the default."""
        from workflow import ppd_color as forms
        try:
            once = getattr(self, "_ps_form_this_print", None)
        except RuntimeError:   # a wrapper whose QWidget was never built (tests)
            once = None
        if once:
            return once        # M-PRINT-VERIFY-PS-EARLIER-ASK's "Use the print dialog"
        stored = self._ps_form_stored()
        if stored is not None:
            return stored
        return None if self._ps_form_can_be_asked() else forms.DEFAULT_POSTSCRIPT_FORM

    def _ask_ps_form(self, printer: str, *, proposed: bool = False
                     ) -> "str | None":
        """M-PRINT-PS-ASK, after the macOS dialog closed with Print on a
        PostScript printer and before anything is sent: which way to print.
        The answer is stored for the run; Cancel returns None (nothing is
        printed).

        Its explained wording (M-PRINT-PS-ASK-EXPLAINED and
        M-PRINT-PS-FORM-CHOICE-EXPLAINED, Knut #182 6143186611, approved
        2026-10-13); *proposed* is kept for review drivers."""
        from workflow import measurement_messages as MM
        from workflow import ppd_color as forms
        ask_msg, choice_msg, _help = ps_texts(proposed=proposed)
        explained = ask_msg is MM.M_PRINT_PS_ASK_EXPLAINED
        title, body = ask_msg.render(printer=printer or "")
        label, lines = choice_msg.render()
        lines = lines.split("\n")
        if explained:
            # each button IS its choice, in words that say what happens to
            # the colours; no "Print like" in front
            label = ""
        box = QMessageBox(self)
        set_question_icon(box)    # ChromIQ's sign, not the platform's
        box.setWindowTitle(title)
        box.setText(title)
        box.setInformativeText(body)
        def _btn_text(choice):
            return choice if explained else tr("{label} {choice}").format(
                label=label, choice=choice)
        device_btn = box.addButton(_btn_text(lines[0]),
                                   QMessageBox.ButtonRole.AcceptRole)
        macos_btn = box.addButton(_btn_text(lines[1]),
                                  QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(device_btn)
        box.setEscapeButton(cancel_btn)
        # the long labels must not be clipped (Knut, #130 2026-07-28), and
        # the box must stay on screen: the pattern of the tab's other windows
        from ui.widgets import (fit_message_box_buttons,
                                keep_message_box_inside_the_work_area)
        keep_message_box_inside_the_work_area(box)
        # side by side the two choices do not fit the widest box Qt allows
        # in most languages (final review of beta 2): one above the other
        fit_message_box_buttons(box, stack_when_too_wide=True)
        box.exec()
        clicked = box.clickedButton()
        if clicked is device_btn:
            form = forms.POSTSCRIPT_DEVICE_RGB
        elif clicked is macos_btn:
            form = forms.POSTSCRIPT_AS_MACOS
        else:
            log.info("PostScript form not chosen: nothing printed")
            return None
        # the PROJECT's choice (Basti, 2026-10-13): the calibration and every
        # run that has none of its own print this way from now on
        self._store_ps_project_form(form)
        self._update_ps_form_row()
        self._update_colour_row_visible()
        return form

    def _tell_cmyk_raster_once(self, printer: str) -> None:
        """After a job went through the macOS dialog to a printer whose
        driver takes CMYK raster: the approved M-PRINT-CMYK-RASTER-ROUTE,
        once per run (``print_settings["cmyk_hint_shown"]``; once per printer
        and session where there is no run to keep it). Basti, 2026-10-13:
        the tab cannot know the printer before the dialog, so it is said
        after it."""
        from workflow import measurement_messages as MM
        run = self._ps_form_run()
        meta = None
        if run is not None:
            try:
                meta = run.load_meta()
                if (getattr(meta, "print_settings", None) or {}).get("cmyk_hint_shown"):
                    return
            except Exception:  # noqa: BLE001
                meta = None
        else:
            told = self.__dict__.setdefault("_cmyk_told_printers", set())
            if printer in told:
                return
            told.add(printer)
        inform(self, *MM.M_PRINT_CMYK_RASTER_ROUTE.render(printer=printer or ""))
        if meta is not None:
            try:
                stored = dict(getattr(meta, "print_settings", None) or {})
                stored["cmyk_hint_shown"] = True
                meta.print_settings = stored
                run.save_meta(meta)
            except Exception:  # noqa: BLE001 - never lose the print over a note
                log.warning("Could not note the CMYK hint", exc_info=True)

    def _store_ps_project_form(self, form: str) -> bool:
        """Keep *form* as the project's choice (``project.json``); False when
        there is no project or it could not be written."""
        project = self._ps_project()
        if project is None:
            return False
        try:
            if not Path(getattr(project, "root", "") or "").is_dir():
                return False           # never resurrect a deleted project
            # the setting's switch count it was asked at, so a later switch
            # asks again (Knut, #182, 2026-10-13)
            counted = project.set_print_setting(
                "postscript_dialog_changes", self._dialog_setting_changes())
            changed = project.set_print_setting("postscript", form) or counted
            if changed:
                log.info("PostScript form for the project: %s", form)
            return changed
        except Exception:  # noqa: BLE001 - never lose the print over a write
            log.warning("Could not store the project's PostScript form", exc_info=True)
            return False

    def _store_ps_form(self, form: str) -> bool:
        """The row's choice: the run's own, in its ``meta.json`` (it then no
        longer follows the project). False when there is no run to keep it
        (calibration, new run) or it could not be written."""
        run = self._ps_form_run()
        if run is None:
            return False
        try:
            if not Path(getattr(run, "dir", "")).is_dir():
                return False           # never resurrect a deleted run
            meta = run.load_meta()
            stored = dict(getattr(meta, "print_settings", None) or {})
            if stored.get("postscript") == form:
                return False
            stored["postscript"] = form
            meta.print_settings = stored
            run.save_meta(meta)
            log.info("PostScript form for %s: %s", getattr(run, "id", run), form)
            return True
        except Exception:  # noqa: BLE001 - never lose the tab over a write
            log.warning("Could not store the PostScript form", exc_info=True)
            return False

    def _on_ps_form_changed(self, *_a) -> None:
        if getattr(self, "_updating_ps_form", False):
            return
        from workflow import ppd_color as forms
        self._store_ps_form(forms.POSTSCRIPT_DEVICE_RGB if self._ps_device_rb.isChecked()
                            else forms.POSTSCRIPT_AS_MACOS)
        self._update_cmyk_route_note()
        self._update_colour_row_visible()

    def _update_ps_form_row(self) -> None:
        """Show the PostScript row where it applies: macOS, the dialog route
        on, a chart loaded, a run whose choice is known (its own, its
        parent's or the project's, asked after the dialog, Basti 2026-10-13:
        the printer the dialog opens on is never consulted), and its words
        approved. Changing it gives the run its own choice. Not on the
        calibration, which follows the project's choice (Basti, 2026-10-13),
        nor on a new run. The radios always follow the stored choice."""
        row = getattr(self, "_ps_form_row", None)
        if row is None:
            return
        from workflow import ppd_color as forms
        self._updating_ps_form = True
        try:
            (self._ps_device_rb if self._ps_form() == forms.POSTSCRIPT_DEVICE_RGB
             else self._ps_macos_rb).setChecked(True)
        finally:
            self._updating_ps_form = False
        show = (is_macos()
                and bool(self._settings.get("use_native_print_dialog", False))
                and bool(getattr(self, "_tiff_pages", None))
                and self._ps_form_run() is not None
                and self._ps_form_stored() is not None)
        row.setVisible(bool(show))

    def _colours_converted_on_the_way(self) -> bool:
        """Whether the Through notice may NOT promise that nothing between
        ChromIQ and the paper changes the colours (combined review of 4.3.5,
        item b): on the direct route, a queue whose driver takes CMYK raster;
        on the macOS dialog route always, because the printer is chosen only
        in the dialog and a CMYK raster driver or a PostScript printer sent
        the chart as macOS sends it converts the colours (Basti, 2026-10-13:
        nothing is decided from the printer the dialog opens on)."""
        try:
            if bool(self._settings.get("use_native_print_dialog", False)) and is_macos():
                return True
            if bool(self._settings.get("use_native_print_dialog", False)) and is_windows():
                # as before #205: the Windows dialog route had no printer list,
                # and the printer is chosen only in the dialog
                return False
            queue = self._printer_combo.currentData() or ""
            return bool(queue) and _queue_cmyk_raster(queue) is not None
        except Exception:  # noqa: BLE001 - a notice must never break the tab
            return False

    def _update_colour_row_visible(self) -> None:
        """§3.1 + §3.1a + §3.1b: which rows show, what is forced, and what the
        notice says — recomputed from the target, the run's profile and the
        loaded chart every time any of them changes."""
        from workflow import verification_print as vp
        ctl = getattr(self, "_target_ctl", None)
        has_pages = bool(self._tiff_pages)
        is_verif = ctl is not None and ctl.target.is_verification()
        self._update_verify_route_note()
        self._update_ps_form_row()
        # A6: with no chart the tab shows its existing empty state — no rows.
        self._cm_grp.setVisible(has_pages)
        self._cm_colour_row.setVisible(is_verif)
        self._cm_intent_row.setVisible(is_verif)
        # The notice is a sibling of the group (not a child), so it needs the
        # no-pages condition itself.
        self._cm_notice.setVisible(has_pages and is_verif)
        if not (has_pages and is_verif):
            # beta 12: no Colour row, so the preview follows the chart's own
            # printing path (a profiling chart prints raw)
            self._preview.set_print_preview(True)
            return

        state = vp.chart_conversion_state(self._current_ti2)
        run = self._cm_run()
        profile_exists = (run is not None
                          and run.built_profile_icc().exists())
        self._updating_cm = True
        try:
            if state != vp.STATE_REGULAR:
                # §3.1a — the chart was converted when it was made: force Raw,
                # DISABLE the other option (an error with no legitimate use).
                self._cm_raw_rb.setText(tr("Raw — already converted"))
                self._cm_raw_rb.setChecked(True)
                self._cm_through_rb.setEnabled(False)
                self._cm_intent_combo.setEnabled(False)
                notice = tr(_CM_NOTICE_ALREADY_CONVERTED)
                if state == vp.STATE_CONVERTED_REF_MISSING:
                    # A3c — say what could not be established, and stay safe.
                    notice = tr(_CM_NOTICE_REFERENCE_MISSING) + "<br><br>" + notice
                self._cm_notice.setText(notice)
            elif not profile_exists:
                # A4 — nothing to print through; raw stays available.
                self._cm_raw_rb.setText(tr("Raw — no profile"))
                self._cm_raw_rb.setChecked(True)
                self._cm_through_rb.setEnabled(False)
                self._cm_intent_combo.setEnabled(False)
                self._cm_notice.setText(self._no_profile_notice(run))
            else:
                # A3 / A5 — both options live; the user's choice rules.
                self._cm_raw_rb.setText(tr("Raw — no profile"))
                self._cm_through_rb.setEnabled(True)
                self._cm_raw_rb.setEnabled(True)
                wanted = self._cm_user_colour
                if wanted is None:
                    wanted = vp.default_colour_for_run(run)
                (self._cm_through_rb if wanted == vp.COLOUR_THROUGH
                 else self._cm_raw_rb).setChecked(True)
                through = self._cm_through_rb.isChecked()
                self._cm_intent_combo.setEnabled(through)
                if through and self._colours_converted_on_the_way():
                    self._cm_notice.setText(tr(_CM_NOTICE_THROUGH_CONVERTED_ON_THE_WAY))
                else:
                    self._cm_notice.setText(
                        tr(_CM_NOTICE_THROUGH) if through
                        else tr(_CM_NOTICE_RAW_CHOSEN))
        finally:
            self._updating_cm = False
        # beta 12 (Knut 6045500910 Q4, Basti 6045468325): the preview shows
        # the sheet the way the Colour row will print it
        self._preview.set_print_preview(
            True, colour=self._cm_selected_colour(),
            intent=self._cm_selected_intent())
        # k81: the dialog-route paragraph follows the Colour now chosen
        self._update_verify_route_note()

    def _profiles_in_other_runs(self, run) -> list[str]:
        """Ids of the project's OTHER runs that hold a built profile.

        Answers the question the A4 notice needs and no other: not "does this
        project have a profile" and not "does this run have one", but "is the
        thing the user is being told to build already sitting one click away".
        The selected run is excluded by id, because it is the run that has just
        been found to have none and naming it back to the user would be absurd.

        A question must never raise. With no controller, no project, or a
        manifest that cannot be read, the answer is "none known", which falls
        back to the notice ChromIQ has always shown.
        """
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None:
            return []
        try:
            project = ctl.project_or_none()
            if project is None:
                return []
            here = getattr(run, "id", None)
            return [other.id for other in project.all_runs()
                    if other.id != here and other.built_profile_icc().exists()]
        except Exception:      # noqa: BLE001 — a question must never raise
            return []

    def _no_profile_notice(self, run) -> str:
        """A4's notice, which depends on whether the profile exists elsewhere."""
        from ui.measurement_target_bar import MeasurementTargetBar
        others = self._profiles_in_other_runs(run)
        if not others:
            return tr(_CM_NOTICE_NO_PROFILE)
        # One formatter for the run name, borrowed from the bar the user is
        # being sent to, so the message cannot name a run differently from the
        # dropdown it is pointing at.
        pretty = [MeasurementTargetBar._pretty_run(rid) for rid in others]
        if len(pretty) == 1:
            return tr(_CM_NOTICE_PROFILE_IN_ONE_OTHER_RUN).format(run=pretty[0])
        return tr(_CM_NOTICE_PROFILE_IN_OTHER_RUNS).format(
            runs=", ".join(pretty))

    def _cm_selected_colour(self) -> str:
        """The colour route a print started now would actually take.

        Computed from the target and the widget STATE, never from
        ``isVisible()`` — a widget that has not been shown on screen yet
        answers ``isVisible() == False`` even when its row applies, which
        would silently downgrade "through" to raw."""
        from workflow import verification_print as vp
        ctl = getattr(self, "_target_ctl", None)
        if (ctl is None or not ctl.target.is_verification()
                or not self._tiff_pages):
            return vp.COLOUR_RAW
        if self._cm_through_rb.isChecked() and self._cm_through_rb.isEnabled():
            return vp.COLOUR_THROUGH
        return vp.COLOUR_RAW

    def _cm_selected_intent(self) -> str:
        return self._cm_intent_combo.currentData() or "relative"

    def _cm_selected_route(self) -> str:
        from workflow import verification_print as vp
        if self._tiff_pages and self._cm_route_ext_rb.isChecked():
            return vp.ROUTE_EXTERNAL
        return vp.ROUTE_CHROMIQ

    def _apply_verification_colour(self, pages):
        """The one funnel below both print buttons (§5 A2.2).

        Converts the pages through the run's profile when the Colour row says
        so, records how the sheet is produced (A15–A18), and handles the
        external route. Returns the pages the print path should send, or None
        when nothing is to be printed here — a failed conversion prints
        nothing (§3.2 A11), and the external route hands the files over
        instead of printing.
        """
        from workflow import verification_print as vp
        colour = self._cm_selected_colour()
        route = self._cm_selected_route()
        converted_dir = None
        chart_dir = (Path(self._current_ti2).parent
                     if self._current_ti2 is not None
                     else Path(pages[0][0]).parent)
        out_dir = chart_dir / "cache"

        # B7 (#182 5959070209): the printer calibration. A profile built from
        # a chart printed with -K describes the printer BEHIND the
        # calibration, so a sheet printed through it must be calibrated too;
        # a verification chart built with -K cannot go through the profile at
        # all. Verification targets only: nothing else shows the Colour row.
        cal_plan = None
        ctl = getattr(self, "_target_ctl", None)
        if ctl is not None and ctl.target.is_verification():
            cal_plan = vp.plan_calibration(
                self._cm_run(),
                Path(self._current_ti2) if self._current_ti2 is not None
                else None,
                colour, out_dir)
            if cal_plan.log:
                log.info("%s", cal_plan.log)
            if cal_plan.refuse:
                self._show_k_chart_refusal()
                self._set_status("")
                return None
            if cal_plan.warn_raw and not self._confirm_raw_uncalibrated():
                return None

        if colour == vp.COLOUR_THROUGH:
            run = self._cm_run()
            profile = run.built_profile_icc() if run is not None else None
            bin_dir = self._settings.get("argyll_bin_path",
                                         "/Applications/Argyll/bin")
            unique = list(dict.fromkeys(p for p, _f in pages))
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                def _progress(n: int, total: int) -> None:
                    self._set_status(tr(
                        "Working out the ink amounts your profile predicts — "
                        "page {n} of {total}…").format(n=n, total=total))
                    QApplication.processEvents()

                mapping = vp.convert_pages_through_profile(
                    unique, profile if profile is not None else Path(""),
                    self._cm_selected_intent(), out_dir,
                    bin_dir=bin_dir, on_page=_progress,
                    calibration=(cal_plan.cal if cal_plan is not None
                                 else None))
            except vp.VerificationPrintError as err:
                self._set_status("")
                self._show_cm_error(err)
                return None
            finally:
                QApplication.restoreOverrideCursor()
            pages = [(mapping.get(p, p), f) for p, f in pages]
            converted_dir = out_dir
            if cal_plan is not None and cal_plan.cal is not None:
                self._set_status(tr(
                    "The sheets have been prepared through this run's profile "
                    "and the printer calibration its chart was printed with."))
            else:
                self._set_status(tr(
                    "The sheets have been prepared through this run's profile."))

        # A RECORD OF A PRINT IS WRITTEN WHEN THERE HAS BEEN ONE (R6 F5).
        #
        # This wrote `<stem>.print.json` here, above BOTH print paths and above
        # every one of their guards — no printer, printer offline, stuck jobs,
        # the borderless warning, the preflight, a TIFF that will not open, a
        # queue that rejects the job. Driven: with the printer asleep ChromIQ
        # correctly said so, sent zero pages, and left behind
        # `{"printed_at": …, "colour": "raw", "route": "chromiq"}`. Same on
        # Cancel at the preflight. That file then told the Measure tab that
        # ChromIQ had printed the sheet, so the "How was this sheet printed?"
        # question was never asked about a sheet ChromIQ had NOT printed, and
        # the report asserted `colour: raw` about a sheet that went through the
        # profile — with pairing 3's media-relative yardstick left off.
        #
        # So the two routes are timed by what each of them actually does:
        #
        #   route = external — the hand-off IS the act. By this line the pages
        #     are converted and the folder is about to open; nothing further
        #     can refuse. Written here, unchanged.
        #   route = chromiq  — the act is a print, and ChromIQ has not made one
        #     yet. The record is held and committed by whichever print path
        #     runs, once a page has been accepted by the printing system.
        #
        # "Accepted" is the strongest fact available: paper coming out of a
        # printer is not observable from here, and the record's question is
        # "did ChromIQ put this sheet through the profile", not "did it reach
        # the paper". A job the queue took carries the converted pages and the
        # answer is yes; a job that was never submitted, or that CUPS refused,
        # is not a print and leaves no record.
        self._pending_print_record = None
        if self._current_ti2 is not None:
            run = self._cm_run()
            pending = dict(
                colour=colour,
                intent=self._cm_selected_intent(),
                profile=(run.built_profile_icc() if run is not None else None),
                route=route,
                source_profile=(vp.source_profile_path(
                    self._settings.get("argyll_bin_path",
                                       "/Applications/Argyll/bin"))
                    if colour == vp.COLOUR_THROUGH else ""),
                calibration=(cal_plan.record if cal_plan is not None
                             else None))
            if route == vp.ROUTE_EXTERNAL:
                vp.write_print_record(Path(self._current_ti2), **pending)
            else:
                self._pending_print_record = (Path(self._current_ti2), pending)

        if route == vp.ROUTE_EXTERNAL:
            folder = converted_dir if converted_dir is not None else (
                Path(self._current_ti2).parent if self._current_ti2 is not None
                else Path(pages[0][0]).parent)
            from core.preset_store import reveal_in_file_manager
            reveal_in_file_manager(folder)
            if converted_dir is not None:
                self._set_status(tr(
                    "The finished sheets are in the folder that just opened — "
                    "the colour work is already done. In your application: "
                    "print them with no colour conversion of any kind, and at "
                    "100% size."))
            else:
                self._set_status(tr(
                    "The chart pages are in the folder that just opened. In "
                    "your application: print them with no colour conversion "
                    "of any kind, and at 100% size."))
            return None
        return pages

    def _show_k_chart_refusal(self) -> None:
        """B7: a verification chart built with -K cannot go through the
        profile (M-CM-K-CHART-THROUGH). Nothing is printed."""
        from workflow import measurement_messages as M
        title, body = M.M_CM_K_CHART_THROUGH.render()
        dlg = QMessageBox(self)
        dlg.setIcon(QMessageBox.Icon.Critical)
        dlg.setWindowTitle(title)
        dlg.setText(title)
        dlg.setInformativeText(body)
        dlg.addButton(QMessageBox.StandardButton.Ok)
        dlg.exec()

    def _confirm_raw_uncalibrated(self) -> bool:
        """B7: the raw route on a run whose profiling chart was printed with
        the printer calibration applied (-K), for a verification chart that
        was not. Returns True to print anyway. Cancel is the default."""
        from workflow import measurement_messages as M
        title, body = M.M_CM_RAW_UNCALIBRATED.render()
        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        set_warning_icon(dlg)
        # House pattern: the headline as the bold text, the body under it
        # (a macOS message box shows no window title).
        dlg.setText(title)
        dlg.setInformativeText(body)
        anyway_btn = dlg.addButton(tr("Print Raw Anyway"),
                                   QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(cancel_btn)
        dlg.exec()
        if dlg.clickedButton() is anyway_btn:
            log.warning("raw verification print of a -K run confirmed by user")
            return True
        return False

    def _show_cm_error(self, err) -> None:
        """Render the §M message a failed conversion names (S9 / S10)."""
        from workflow import measurement_messages as M
        if err.message_id == "M-CM-NO-CCTIFF":
            title, body = M.M_CM_NO_CCTIFF.render()
        else:
            title, body = M.M_CM_CONVERT_FAILED.render(
                n=err.page or 1, total=err.total or 1,
                reason=err.reason or err.message_id)
        message_box(QMessageBox.Icon.Critical, self, title, body)

    # ---- per-target settings (#130 feature A, §11 Q5) --------------------
    def save_target_settings(self, store=None, key=None) -> bool:
        """Record the Colour / Rendering intent / Route choices, and the
        printer with every option row (Knut, 2026-10-20), against the
        selected target — the same duck-typed contract Create Chart, Measure
        and Build Profile follow, called by MainWindow on the L1/W6 events.

        Only into the store whose settings are on screen: values loaded for
        one target are never filed onto another (§2.0), which a write from a
        hidden tab after a run change would otherwise do."""
        if getattr(self, "_updating_cm", False) \
                or getattr(self, "_loading_print_settings", False):
            return False
        if store is None:
            from workflow.per_target_settings import store_for_target
            store = store_for_target(getattr(self, "_target_ctl", None))
        if store is None:
            return False
        try:
            if not Path(getattr(store, "dir", "")).is_dir():
                return False           # never resurrect a deleted project
        except (TypeError, ValueError):
            return False
        try:
            from workflow import verification_print as vp
            fingerprint = str(getattr(store, "dir", store))
            loaded_for = self._print_loaded_for
            if loaded_for is not None and loaded_for != fingerprint:
                log.debug("print settings not written: the screen shows %s, "
                          "not %s", loaded_for, fingerprint)
                return False
            wanted = {
                "colour": self._cm_user_colour or "",
                "intent": self._cm_selected_intent(),
                "route": (vp.ROUTE_EXTERNAL
                          if self._cm_route_ext_rb.isChecked()
                          else vp.ROUTE_CHROMIQ),
            }
            printer, opts = self._printer_snapshot()
            if loaded_for == fingerprint and printer:
                wanted["printer"] = printer
                wanted["printer_options"] = opts
            if self._print_written.get(fingerprint) == wanted:
                return False
            meta = store.load_meta()
            if not hasattr(meta, "print_settings"):
                return False
            stored = dict(getattr(meta, "print_settings") or {})
            merged = dict(stored)
            # A forced state (§3.1a / A4) leaves the user's stored Colour
            # alone: only a choice the user could actually make is recorded.
            if wanted["colour"]:
                merged["colour"] = wanted["colour"]
            merged["intent"] = wanted["intent"]
            merged["route"] = wanted["route"]
            # The printer and its options: only when the user changed them
            # since the load, or they were seeded from the run this one was
            # made from (§4a). A target that was merely looked at keeps what
            # it had: nothing (§4 S4/S9), or a printer no longer installed
            # (PS-8).
            if "printer" in wanted and (self._printer_dirty or self._printer_seeded):
                merged["printer"] = printer
                per_queue = dict(stored.get("printer_options") or {}) \
                    if isinstance(stored.get("printer_options"), dict) else {}
                per_queue[printer] = dict(opts)
                merged["printer_options"] = per_queue
            if merged == stored:
                self._print_written[fingerprint] = wanted
                return False
            meta.print_settings = merged
            store.save_meta(meta)
            self._print_written[fingerprint] = wanted
            if "printer" in merged:
                self._target_printer = merged["printer"]
                self._target_printer_opts = dict(merged.get("printer_options") or {})
            log.debug("print settings written for %s", getattr(store, "id", store))
            return True
        except Exception:      # noqa: BLE001 — never lose the tab over a write
            log.warning("Could not save the target's Print settings",
                        exc_info=True)
            return False

    def load_target_settings(self) -> bool:
        """Put the selected target's Print choices on screen (§2 L1), falling
        back to the defaults — and to the Q3 history-aware Colour default —
        when the target has nothing stored (§4 S4/S5)."""
        from workflow.per_target_settings import store_for_target
        from workflow import verification_print as vp
        # WHERE A NEW RUN CAME FROM IS NOTED BEFORE IT IS LOADED (re-review
        # N1). MainWindow's visible-tab load is connected to the bar's
        # `changed` before this tab's own `_note_target_change`, so with the
        # Print tab on screen a new run opened on the saved defaults and took
        # its source's printer only at the next visit. Noting is idempotent:
        # the later call from the signal finds nothing new.
        self._note_target_change()
        store = store_for_target(getattr(self, "_target_ctl", None))
        stored: dict = {}
        if store is not None:
            try:
                stored = dict(getattr(store.load_meta(), "print_settings",
                                      None) or {})
            except Exception:      # noqa: BLE001
                log.warning("Could not read the target's Print settings",
                            exc_info=True)
                stored = {}
        # the printer and its options (Knut, 2026-10-20): the target's own,
        # a verification's run's, a new run's seed, else the saved defaults
        if store is not None:
            printer, per_queue, seeded = self._printer_settings_to_load(store, stored)
            self._target_printer = printer
            self._target_printer_opts = per_queue
            self._printer_seeded = seeded
            self._print_loaded_for = str(getattr(store, "dir", store))
            self._printer_dirty = False
        self._loading_print_settings = True
        self._updating_cm = True
        try:
            if store is not None:
                self._apply_target_printer()
            colour = stored.get("colour") or ""
            self._cm_user_colour = colour if colour in (
                vp.COLOUR_THROUGH, vp.COLOUR_RAW) else None
            idx = self._cm_intent_combo.findData(
                stored.get("intent") or vp.DEFAULT_INTENT)
            self._cm_intent_combo.setCurrentIndex(idx if idx >= 0 else 0)
            (self._cm_route_ext_rb
             if stored.get("route") == vp.ROUTE_EXTERNAL
             else self._cm_route_here_rb).setChecked(True)
        finally:
            self._updating_cm = False
            self._loading_print_settings = False
        self._update_colour_row_visible()
        return bool(stored)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refresh_printers(self) -> None:
        # A refresh keeps the printer on screen; the first listing opens on
        # the selected target's own printer, else the saved default.
        first = self._printer_combo.count() == 0
        shown = "" if first else (self._printer_combo.currentData() or "")
        self._printer_combo.blockSignals(True)
        self._printer_combo.clear()
        printers = self._module.detect_printers()
        for p in printers:
            self._printer_combo.addItem(p, p)
        if not printers:
            self._printer_combo.addItem(tr("No printers found"), "")
        self._printer_combo.blockSignals(False)

        last = shown or self._wanted_printer()
        if last:
            idx = self._printer_combo.findData(last)
            if idx >= 0:
                # not the user's pick: the combo's signal stays blocked, or
                # the first look at a run would store the saved default
                self._printer_combo.blockSignals(True)
                self._printer_combo.setCurrentIndex(idx)
                self._printer_combo.blockSignals(False)
        self._on_printer_changed()

    # ---- the printer and its options, per target (Knut, 2026-10-20) -------
    #: Knut, 2026-10-20: "All the print settings should be 100% individual
    #: per run and should never change on a run based on settings made on a
    #: different run, while moving back and forth between runs."  Until 4.3.7
    #: the printer and every option row lived only on screen (and in Save as
    #: Defaults), so the run you came from was what the next run showed and
    #: printed with. Now they are the target's, in ``print_settings`` of its
    #: meta.json beside the Colour / intent / route choices
    #: (per_target_settings.md §5a).

    def _wanted_printer(self) -> str:
        """The printer the selected target opens on: its own, else the
        saved default (Save as Defaults, ``last_printer``)."""
        return self._target_printer or str(self._settings.get("last_printer", "") or "")

    def _saved_options_for(self, printer: str) -> "dict[str, str]":
        """The option values *printer* opens on for the selected target: the
        target's own for that queue, else the saved defaults."""
        own = self._target_printer_opts.get(printer)
        if isinstance(own, dict):
            return {str(k): str(v) for k, v in own.items()}
        saved: dict[str, str] = {}
        raw_saved = self._settings.get(f"print_opts_{printer}", "")
        if raw_saved:
            for pair in str(raw_saved).split("|"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    saved[k] = v
        return saved

    def _printer_snapshot(self) -> "tuple[str, dict[str, str]]":
        """The printer on screen and every option row's value ("" is
        "Printer Default")."""
        printer = self._printer_combo.currentData() or ""
        return printer, {k: (c.currentData() or "")
                         for k, c in self._option_combos.items()}

    def _apply_target_printer(self) -> None:
        """Put the selected target's printer and options on screen. Before
        the printer list was first read (the tab not yet shown) it is left to
        `_refresh_printers`, which asks `_wanted_printer` too."""
        if not getattr(self, "_printers_loaded", False) \
                or self._printer_combo.count() == 0:
            return
        want = self._wanted_printer()
        cb = self._printer_combo
        idx = cb.findData(want) if want else -1
        if idx < 0 and self._target_printer:
            # PS-8: a printer no longer installed opens on the saved default
            # (review D4); the run's stored printer stays until the user
            # changes something
            idx = cb.findData(str(self._settings.get("last_printer", "") or ""))
            log.info("Print: the target's printer %s is not listed; opened on "
                     "%s", self._target_printer,
                     cb.itemData(max(idx, 0)) or "none")
        if idx < 0:
            idx = 0
        cb.blockSignals(True)
        try:
            cb.setCurrentIndex(idx)
        finally:
            cb.blockSignals(False)
        self._on_printer_changed()

    def _printer_settings_to_load(self, store, stored: dict):
        """(printer, options per queue, seeded) for *store*: its own; else,
        for a verification, its run's (the sheet must print as the run's
        did); else, for a run made from the run on screen since the last
        load, the screen (§4a); else (None, {}, False): the saved defaults."""
        own = stored.get("printer")
        if isinstance(own, str) and own:
            opts = stored.get("printer_options")
            return own, (dict(opts) if isinstance(opts, dict) else {}), False
        if self._target_is_verification():
            run = self._cm_run()
            try:
                ps = dict(getattr(run.load_meta(), "print_settings", None) or {}) \
                    if run is not None else {}
            except Exception:  # noqa: BLE001 - a default must never raise
                ps = {}
            if isinstance(ps.get("printer"), str) and ps.get("printer"):
                opts = ps.get("printer_options")
                return ps["printer"], (dict(opts) if isinstance(opts, dict) else {}), False
            return None, {}, False
        from core.file_manager import Calibration
        if isinstance(store, Calibration):
            return None, {}, False
        # §4a / PS-6: a run made in this session starts on the printer
        # settings of the run it was made from, as the bar saw it (review
        # D2/D3), never on whatever this tab showed last; a calibration never
        # seeds (N-6); a duplicate carries exactly what its source had.
        try:
            meta = store.load_meta()
            project = self._target_ctl.project_or_none()
            key = (str(project.root), getattr(store, "id", None))
        except Exception:  # noqa: BLE001
            return None, {}, False
        if getattr(meta, "duplicated_from", None):
            return None, {}, False
        if key not in self._print_born_from:
            return None, {}, False
        source = self._print_born_from.pop(key)
        parent = getattr(meta, "parent_run", None)
        if parent:
            source = ("run", parent)        # refined: from its parent run
        got = self._printer_settings_of_source(project, source)
        if got is None:
            return None, {}, False
        printer, opts = got
        log.info("Print: %s is new; it starts on the printer settings of %s "
                 "(%s)", key[1], source, printer)
        return printer, opts, True

    @staticmethod
    def _printer_settings_of_source(project, source):
        """(printer, options per queue) stored by *source*, or None. A
        verification with none of its own gives its run's."""
        if not source:
            return None
        kind, run_id = source
        try:
            if not run_id or not project.has_run(run_id):
                return None
            run = project.run(run_id)
            from core.file_manager import Run as _Run
            stores = [run]
            if kind == "verification":
                stores.insert(0, _Run.for_dir(run.verifications_dir))
            for st in stores:
                if not Path(getattr(st, "dir", "")).is_dir():
                    continue
                ps = dict(getattr(st.load_meta(), "print_settings", None) or {})
                printer = ps.get("printer")
                if isinstance(printer, str) and printer:
                    opts = ps.get("printer_options")
                    return printer, (dict(opts) if isinstance(opts, dict) else {})
        except Exception:  # noqa: BLE001 - a seed is never worth a crash
            log.warning("Could not read the printer settings of %s", source,
                        exc_info=True)
        return None

    def _note_target_change(self) -> None:
        """Remember, at every change of the bar, the target that was left and
        the runs that existed while it was selected, so a run that appears
        later knows which run it was made from (§4a)."""
        ctl = getattr(self, "_target_ctl", None)
        try:
            project = ctl.project_or_none() if ctl is not None else None
            if project is None:
                self._print_prev = None
                return
            root = str(project.root)
            target = ctl.target
            ids = frozenset(r.id for r in project.all_runs())
        except Exception:  # noqa: BLE001
            self._print_prev = None
            return
        prev = self._print_prev
        if prev is not None and prev[0] == root:
            _root, p_type, p_run, p_ids = prev
            if p_type == "calibration":
                source = None                          # N-6
            elif not p_run:
                source = self._print_new_run_source    # chosen from New run
            else:
                source = (p_type, p_run)
            if target.is_new_run() and p_run:
                self._print_new_run_source = source
            elif target.is_calibration():
                pass
            elif target.profile_run and target.profile_run not in p_ids:
                self._print_born_from[(root, target.profile_run)] = source
        elif prev is None or prev[0] != root:
            self._print_new_run_source = None
        run_type = "calibration" if target.is_calibration() else (
            "verification" if target.is_verification() else "run")
        self._print_prev = (root, run_type, target.profile_run, ids)

    def _on_printer_picked(self) -> None:
        """The user chose a printer (the combo's own signal; every programmatic
        change blocks it)."""
        self._printer_dirty = True
        self._on_printer_changed()

    def _update_edge_note(self) -> None:
        """Say which ruler helper markers or text of the chart fall into the
        edge the chosen printer does not print (M-EDGE-NOT-PRINTED), placed
        as the print will place it; hidden when nothing does."""
        lbl = getattr(self, "_edge_note_lbl", None)
        if lbl is None:
            return
        note = None
        try:
            pages = list(getattr(self._preview, "_pages", None) or [])
            printer = self._printer_combo.currentData() or ""
            if pages and printer:
                from workflow import measurement_messages as MM
                from workflow import overhang as O
                from workflow import printer_edges as PE
                chart_pt = read_tiff_dimensions_points(pages[0][0])
                chart_mm = (chart_pt[0] * PE.MM_PER_PT,
                            chart_pt[1] * PE.MM_PER_PT)
                edges, paper = PE.edges_for(printer, chart_mm, self._settings)
                if edges.any():
                    shift = (0.0, 0.0)
                    paper_pt = (paper[0] / PE.MM_PER_PT, paper[1] / PE.MM_PER_PT)
                    plan = self._overhang_plan(pages, paper_pt)
                    if plan is not None and plan.safe:
                        shift = plan.shift_mm
                    loss = PE.losses_for_chart(pages, edges, paper, shift)
                    note = MM.edge_note(printer, edges, loss)
                    if note:
                        log.info("Print: %s: unprinted edge %s (%s); %s",
                                 printer, edges.as_dict(), edges.source, loss)
        except Exception:      # noqa: BLE001 - a note, never a blocker
            log.debug("edge note not worked out", exc_info=True)
            note = None
        if note:
            # A WARNING, AND IT LOOKS LIKE ONE (review of 4.3.14): the label
            # was named "warn", which no style sheet styles, so it read as
            # plain text under the buttons beside the tab's amber notices.
            try:
                from ui.widgets import banner_qss
                if getattr(self, "_mode", "dark") == "light":
                    from ui.light_styles import LM_WARN_BG, LM_WARN_TEXT
                    lbl.setStyleSheet(banner_qss(LM_WARN_TEXT, LM_WARN_BG,
                                                 kind="warn"))
                else:
                    lbl.setStyleSheet(banner_qss("#fdd835", "#2a2000",
                                                 kind="warn"))
            except Exception:      # noqa: BLE001 - a look, never a blocker
                log.debug("edge note not styled", exc_info=True)
        lbl.setText(note or "")
        lbl.setVisible(bool(note))

    def _on_printer_changed(self) -> None:
        printer = self._printer_combo.currentData() or ""
        self._rebuild_option_rows(printer)
        self._update_edge_note()
        # …AND CREATE CHART'S, which follows this printer (Basti,
        # 2026-10-25): its "Measured from Preview" notes are worked out again
        # now, not at its next refresh.
        try:
            tc = getattr(self.window(), "_tab_chart", None)
            if tc is not None and getattr(tc, "_margin_tiffs", None):
                tc._update_margin_inspector()
        except Exception:      # noqa: BLE001 - a note, never a blocker
            log.debug("Create Chart edge note not refreshed", exc_info=True)
        # combined review of 4.3.5, item b: the Through notice depends on
        # whether this printer's driver converts the chart into CMYK
        if getattr(self, "_cm_notice", None) is not None and getattr(self, "_tiff_pages", None):
            self._update_colour_row_visible()

    @classmethod
    def _clear_layout(cls, layout) -> None:
        """Recursively delete every widget and sub-layout inside *layout*.

        Rows in the Print Options group are nested QHBoxLayouts whose inner
        QLabel/QComboBox are parented to the tab widget, not the layout — so
        deleting only the top-level layout items leaks them across rebuilds.
        Signals are disconnected before deleteLater so a queued slot can't
        fire into a wrapper that's about to disappear.
        """
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w is not None:
                if isinstance(w, QComboBox):
                    try:
                        w.currentIndexChanged.disconnect()
                    except (TypeError, RuntimeError):
                        pass
                # HIDDEN NOW, deleted later (#205, seen on screen): a deferred
                # delete posted before a window's exec() runs only after that
                # window closes, so the previous printer's rows stayed drawn
                # over the new printer's box while the confirmation window was
                # open
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                cls._clear_layout(sub)
                sub.deleteLater()

    def _apply_airprint_box_styles(self, box: "QFrame") -> None:
        """Paint the 'No configurable options detected' info box.

        Dark mode keeps the original dark-olive / amber treatment; light mode
        reuses the same chrome as QLabel#warning so the box and the
        'Verify that all print settings…' warning above match.

        NOTHING HAD EVER DRAWN THIS BOX IN NEUTRAL. It needs two conditions at
        once: ChromIQ's own ``lp`` pipeline (Preferences turns the OS print
        dialog off) AND a printer whose driver exposes no options at all. The
        fold above had room for two answers, so the third appearance took the
        dark branch and painted a dark-olive slab with amber text across the
        middle of the Print tab - 523,776 hued pixels in a theme that is meant
        to have none. It is a warning, so ``kind="warn"`` keeps it one: in
        Neutral the amber goes and the 2 px underline says it instead.
        """
        if self._mode == "light":
            from ui.light_styles import LM_WARN_BG, LM_WARN_TEXT
            # Border + title pick up the Print Chart tab's spectrum colour so
            # the box matches the rest of the tab's accents (amber).
            bg          = LM_WARN_BG
            border      = SPEC_AMBER
            body_color  = LM_WARN_TEXT
            title_color = SPEC_AMBER
        else:
            bg, border    = "#2a2000", "#f9a825"
            body_color    = "#e0d5b0"
            title_color   = "#fdd835"
        box.setStyleSheet(info_box_qss(
            "airprint", bg=bg, border=border, title=title_color,
            body=body_color, mode=self._mode, kind="warn"))

    def _rebuild_option_rows(self, printer: str) -> None:
        self._clear_layout(self._opts_layout)
        self._option_combos.clear()
        self._ordered_opts.clear()
        self._raw_value_pairs.clear()
        self._quality_note = None
        self._quality_choices = None

        if not printer:
            self._opts_layout.addWidget(QLabel(tr("Select a printer to see its options."), self))
            return

        opts = self._module.query_options(printer)
        if not opts and is_windows():
            self._add_windows_no_options_box(printer)
            return
        if not opts:
            box = QFrame(self)
            box.setFrameShape(QFrame.Shape.NoFrame)
            box.setObjectName("airprintInfoBox")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(10, 8, 10, 8)
            box_layout.setSpacing(6)

            title = QLabel(tr("No configurable options detected"), box)
            title.setObjectName("airprintInfoTitle")
            box_layout.addWidget(title)

            body = QLabel(
                tr("macOS often installs an <b>AirPrint</b> or <b>Driverless</b> driver "
                "automatically when you add a printer. These work fine for everyday "
                "printing, but don't expose the detailed settings needed for ICC profiling."
                "<br><br>"
                "<b>How to check:</b><br>"
                "Open <i>System Settings → Printers &amp; Scanners</i>, select your "
                "printer, and look at the <i>Kind</i> field. If it says "
                "\"AirPrint\" or \"Driverless\", that's the cause."
                "<br><br>"
                "<b>How to fix:</b><br>"
                "1. Click the <b>−</b> button to remove the printer.<br>"
                "2. Download the native driver from your printer manufacturer's website.<br>"
                "3. Re-add the printer — macOS should now use the native PPD driver "
                "with all options available."),
                box,
            )
            body.setWordWrap(True)
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setObjectName("airprintInfoBody")
            box_layout.addWidget(body)

            self._apply_airprint_box_styles(box)
            self._opts_layout.addWidget(box)
            return

        # the selected target's own values for this printer, else the saved
        # defaults (Knut, 2026-10-20: every print setting is the run's own)
        saved_printer_opts = self._saved_options_for(printer)

        for i, (opt_name, (label, value_pairs)) in enumerate(opts.items()):
            self._raw_value_pairs[opt_name] = value_pairs
            row = QHBoxLayout()
            lbl = QLabel(tr("{label}:").format(label=label), self)
            lbl.setMinimumWidth(160)
            row.addWidget(lbl)
            combo = NoScrollComboBox(self)
            combo.setMaxVisibleItems(12)
            combo.addItem(tr("Printer Default"), "")
            for display, raw_val in value_pairs:
                combo.addItem(display, raw_val)
            # All combos start enabled — "Printer Default" on a leading combo means
            # "let the driver decide", so downstream combos must be reachable without
            # forcing the user to pick a tray/size they don't care about.
            combo.setEnabled(True)
            row.addWidget(combo, stretch=1)
            self._opts_layout.addLayout(row)
            self._option_combos[opt_name] = combo
            self._ordered_opts.append((opt_name, [rv for _, rv in value_pairs], combo))
            combo.currentIndexChanged.connect(
                lambda _, idx=i: self._on_option_changed(idx)
            )
            if opt_name in _PAPER_QUALITY_OPTS:
                # beta 16 (M-PRINT-QUALITY): photos must print at this quality
                note = QLabel(self)
                note.setObjectName("printQualityNote")
                note.setWordWrap(True)
                note.setTextFormat(Qt.TextFormat.RichText)
                note.setVisible(False)
                self._opts_layout.addWidget(note)
                self._quality_note = note

        # Restore saved values in insertion order so each restore re-filters the
        # next combo's value list before that combo is itself restored.
        self._restoring = True
        for opt_name, _, combo in self._ordered_opts:
            saved_val = saved_printer_opts.get(opt_name, "")
            if saved_val:
                found = combo.findData(saved_val)
                if found >= 0:
                    combo.setCurrentIndex(found)
        self._restoring = False
        self._refresh_quality_row(keep_current=True)
        self._preselect_paper_for_chart()

    def _add_windows_no_options_box(self, printer: str) -> None:
        """#205: a Windows printer with nothing to choose on ChromIQ's own
        route: a PostScript driver whose PPD offers no choice (a line), or a
        driver that is not PostScript (the box: what Print will do)."""
        from workflow import win_spooler
        if win_spooler.is_postscript(printer):
            lbl = QLabel(tr(_WIN_PS_NO_OPTIONS), self)
            lbl.setWordWrap(True)
            self._opts_layout.addWidget(lbl)
            return
        box = QFrame(self)
        box.setFrameShape(QFrame.Shape.NoFrame)
        box.setObjectName("airprintInfoBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(10, 8, 10, 8)
        box_layout.setSpacing(6)
        title = QLabel(tr(_WIN_NOT_POSTSCRIPT_TITLE), box)
        title.setObjectName("airprintInfoTitle")
        box_layout.addWidget(title)
        body = QLabel(tr(_WIN_NOT_POSTSCRIPT_BODY).format(
            printer=_html_escape(printer)), box)
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setObjectName("airprintInfoBody")
        box_layout.addWidget(body)
        self._apply_airprint_box_styles(box)
        self._opts_layout.addWidget(box)

    def _preselect_paper_for_chart(self) -> None:
        """Beta 16 package (Basti, 2026-10-09): a paper size row left at
        "Printer Default" whose paper does not match the chart is set to the
        driver's paper size that does (PictureMate PM-400/PM-520: the PPD's
        default is 9 x 13 cm, so every chart of another size was taken for
        one larger than the paper).  Several that match: the closest.  None
        that matches: the row stays at the driver's default, and the
        confirmation window still names the mismatch.  A size the user chose
        is never touched."""
        size_key = next((k for k in self._option_combos if k in _PAGE_SIZE_KEYS), None)
        tiffs = getattr(self, "_tiff_pages", None) or []
        if size_key is None or not tiffs:
            return
        combo = self._option_combos[size_key]
        if combo.currentData():
            return
        printer = self._printer_combo.currentData() or ""
        try:
            first = tiffs[0][0] if isinstance(tiffs[0], tuple) else tiffs[0]
            tw, th = read_tiff_dimensions_points(Path(first))
        except Exception:  # noqa: BLE001 - only a preselection
            return

        def _mismatch(raw: str, shown: str):
            dims = self._module.get_page_size_points(printer, raw, shown)
            if not dims:
                return None, None
            area = self._module.get_imageable_area_points(printer, raw, shown)
            return check_size_mismatch(tw, th, dims[0], dims[1], imageable_pt=area), dims

        d_raw, d_shown = self._ppd_default_page(printer)
        if not d_raw:
            return
        def _fit(d):
            return min(abs(d[0] - tw) + abs(d[1] - th), abs(d[0] - th) + abs(d[1] - tw))

        # NEVER A PAPER SMALLER THAN THE CHART (re-review of 4.3.8). The
        # nearest sheet within the mismatch check's 8 % used to win, so a
        # chart image smaller than its sheet (made without printtarg -M,
        # e.g. 561 x 808 pt for A4) got a smaller paper (7.75 x 10.75 in,
        # 558 x 774 pt, on an HP 5550) and the direct route, which never
        # scales, cut 12 mm off it. A paper qualifies only if the chart fits
        # on it in either orientation (within rounding); ChromIQ's own -M
        # charts are the size of their sheet and get it as before.
        def _holds(d):
            t = _PRESELECT_ROUNDING_PT
            return ((d[0] >= tw - t and d[1] >= th - t)
                    or (d[0] >= th - t and d[1] >= tw - t))

        miss, dims = _mismatch(d_raw, d_shown)
        if dims is None:
            return
        # Beta 16 review: the mismatch check forgives up to 8 %, so an A4
        # chart "matches" the R3000's default US Letter (279 mm for 297) and
        # was printed shrunk to 95 % onto it. A default paper that matches
        # only within that tolerance gives way to a paper of the chart's own
        # size; one within a few points of the chart stays.
        default_fit = _fit(dims) if (miss is None and _holds(dims)) else None
        if default_fit is not None and default_fit <= _PRESELECT_CLOSE_PT:
            return          # the driver's default paper is the chart's
        best = None
        for i in range(combo.count()):
            raw = combo.itemData(i) or ""
            if not raw:
                continue
            miss, dims = _mismatch(raw, combo.itemText(i))
            if dims is None or miss is not None or not _holds(dims):
                continue
            fit = _fit(dims)
            if best is None or fit < best[0]:
                best = (fit, i)
        if best is None or (default_fit is not None
                            and best[0] > default_fit - _PRESELECT_CLOSE_PT):
            return
        # keep the rows after it as they are: the size change re-fills them
        # (each back at "Printer Default"), so their choices are put back
        # where the new size still offers them (beta 16 review: a saved
        # media type was dropped by the preselection)
        kept = {k: c.currentData() or "" for k, c in self._option_combos.items()
                if c is not combo}
        self._restoring = True
        try:
            combo.setCurrentIndex(best[1])
            for k, val in kept.items():
                c = self._option_combos[k]
                if val and (c.currentData() or "") != val:
                    j = c.findData(val)
                    if j >= 0:
                        c.setCurrentIndex(j)
        finally:
            self._restoring = False
        # Beta 16 review: the size change re-filled the rows after it (as
        # "Printer Default") while restoring, which skips the quality row's
        # own refresh; measured on screen, the ET-8550 quality row then lost
        # its "Normal (standard)" preselection and the PictureMate kept a
        # quality note for a row at "Printer Default".
        self._refresh_quality_row(keep_current=True)
        log.info("Print: paper size %s=%s preselected for the chart (the "
                 "driver's default %s does not match it)", size_key,
                 combo.currentData(), d_raw)

    def _on_option_changed(self, combo_index: int) -> None:
        if not self._ordered_opts:
            return
        if not self._restoring:
            # a row the user changed (the app's own restores and the paper
            # preselection run under `_restoring`)
            self._printer_dirty = True

        # When the user changes a combo interactively, reset all later combos
        # so stale selections don't leak through into newly-invalid contexts.
        if not self._restoring:
            for j in range(combo_index + 1, len(self._ordered_opts)):
                _, _, c = self._ordered_opts[j]
                c.blockSignals(True)
                c.setCurrentIndex(0)
                c.blockSignals(False)

        # Re-filter every downstream combo so its value list matches the
        # current preceding selections — not just combo_index + 1.
        for j in range(combo_index, len(self._ordered_opts) - 1):
            self._repopulate_next(j)

        # Beta 16: the quality row follows the paper (the qualities the
        # driver's dialog allows for it, preselected as the dialog would).
        if not self._restoring:
            names = [name for name, _v, _c in self._ordered_opts]
            q_index = next((k for k, n in enumerate(names) if n in _PAPER_QUALITY_OPTS), None)
            if q_index is not None and combo_index == q_index:
                self._update_quality_note()
            elif q_index is not None:
                self._refresh_quality_row(keep_current=combo_index > q_index)

    def _refresh_quality_row(self, keep_current: bool) -> None:
        """Beta 16 (Basti, 2026-10-09): a Canon IJ or Epson quality row offers
        the qualities the driver's own dialog allows for the chosen paper,
        the highest included, and preselects the one the user's last print
        through the macOS dialog used on that paper (``printer_memory``),
        else the dialog's standard.  *keep_current*: a quality the row
        already shows stays when the paper allows it (a saved choice, or the
        user's own).  Any other printer keeps the generic row."""
        key = next((k for k in self._option_combos if k in _PAPER_QUALITY_OPTS), None)
        if key is None:
            return
        combo = self._option_combos[key]
        printer = self._printer_combo.currentData() or ""
        qc = None
        try:
            from workflow.ppd_color import ppd_path_for_queue, quality_choices
            from workflow.printer_memory import PaperProfileMemory
            ppd = ppd_path_for_queue(printer)
            if ppd:
                from core.text_io import read_text
                opts = {k: (c.currentData() or "") for k, c in self._option_combos.items()}
                qc = quality_choices(read_text(Path(ppd), lenient=True), opts,
                                     learned=PaperProfileMemory())
        except Exception as exc:  # noqa: BLE001 - the generic row still works
            log.warning("quality row: could not read the driver's qualities: %s", exc)
            qc = None
        self._quality_choices = qc if qc is not None and qc.option == key else None
        qc = self._quality_choices
        if qc is None:
            self._update_quality_note()
            return
        from workflow import measurement_messages as MM
        labels = {raw: shown for shown, raw in self._raw_value_pairs.get(key, [])}
        current = combo.currentData() or ""
        combo.blockSignals(True)
        combo.clear()
        if qc.preselect is None:
            # the dialog's own choice is not known here (an Epson SC-P900
            # chooses its quality another way): "Printer Default" stays
            combo.addItem(tr("Printer Default"), "")
        for v in qc.values:
            name = labels.get(v, v)
            if v == qc.highest:
                name = tr(MM._PRINT_QUALITY_HIGHEST).format(quality=name)
            elif v == qc.standard:
                name = tr(MM._PRINT_QUALITY_STANDARD).format(quality=name)
            combo.addItem(name, v)
        want = current if (keep_current and current in qc.values) else qc.preselect
        idx = combo.findData(want if want is not None else "")
        combo.setCurrentIndex(max(idx, 0))
        combo.blockSignals(False)
        self._update_quality_note()

    def _update_quality_note(self) -> None:
        """M-PRINT-QUALITY under the quality row, for a Canon or Epson whose
        qualities the driver lists, while a quality is chosen in it; hidden
        otherwise."""
        note = self._quality_note
        if note is None:
            return
        qc = self._quality_choices
        if qc is None:
            note.setVisible(False)
            return
        from workflow import measurement_messages as MM
        key = next((k for k in self._option_combos if k in _PAPER_QUALITY_OPTS), "")
        current = self._option_combos[key].currentData() if key else None
        if not current:
            # Beta 16 review: at "Printer Default" there is no quality for
            # "this quality" to name (PictureMate, SC-P900: the dialog's own
            # choice is not known, so nothing is preselected)
            note.setVisible(False)
            return
        head = tr(MM.M_PRINT_QUALITY.title)
        text = f"<b>{_html_escape(head)}</b><br>{_html_escape(tr(MM._PRINT_QUALITY_WHY))}"
        if qc.learned is not None and current == qc.learned:
            text += "<br>" + _html_escape(tr(MM._PRINT_QUALITY_LEARNED))
        note.setText(text)
        note.setVisible(True)

    def _repopulate_next(self, combo_index: int) -> None:
        """Repopulate the combo at *combo_index + 1* based on selections 0..combo_index."""
        _, _, changed_combo = self._ordered_opts[combo_index]
        has_val = bool(changed_combo.currentData())
        next_opt, next_all_vals, next_combo = self._ordered_opts[combo_index + 1]
        next_all_pairs = self._raw_value_pairs.get(next_opt, [])

        if has_val:
            preceding = {
                self._ordered_opts[k][0]: self._ordered_opts[k][2].currentData() or ""
                for k in range(combo_index + 1)
            }
            preceding_labels = {
                self._ordered_opts[k][0]: self._ordered_opts[k][2].currentText() or ""
                for k in range(combo_index + 1)
            }
            valid_vals = set(self._module.get_valid_option_values(
                self._printer_combo.currentData() or "",
                preceding, preceding_labels, next_opt, next_all_vals, next_all_pairs,
            ))
        else:
            # 'Printer Default' = let the driver decide. Nothing to filter
            # against, so the next combo shows every value it offers —
            # otherwise drivers like HP Bonjour (no Auto in Paper Source)
            # would force the user to pick a tray to reach Paper Size.
            valid_vals = set(next_all_vals)

        next_combo.blockSignals(True)
        next_combo.clear()
        next_combo.addItem(tr("Printer Default"), "")
        for display, raw_val in next_all_pairs:
            if raw_val in valid_vals:
                next_combo.addItem(display, raw_val)
        next_combo.blockSignals(False)

    def set_ti2_path(self, path: Path) -> None:
        """Programmatically load a .ti2 file (cross-tab auto-population).

        THE CONTROLLER GOES IN, exactly as this tab's own Browse passes it.
        `resolve_ti2` routes on that argument: with a controller it takes the
        #130 model (A1a/A2a/A2b/A1b), without one it falls through to the
        pre-#130 "Load Test Session" window. This omission meant EVERY
        cross-tab propagation of a chart took the legacy road whatever the bar
        said — and the legacy road offers to "copy the files to a new subfolder
        so you can build a separate ICC profile" about a project ChromIQ has
        just filed a measurement into (R6 F2, driven `d03_who_clears_check.py`).
        """
        from ui.ti2_loader import resolve_ti2
        if not path.exists():
            return
        result = resolve_ti2(self, path, self._settings,
                             getattr(self, "_target_ctl", None))
        if result is None:
            self.ti2_load_cancelled.emit()
            return
        ti2_path, tiffs = result
        self._current_ti2 = ti2_path
        self.ti2_loaded.emit(ti2_path)
        if ti2_path != path:
            self.chart_relocated.emit(ti2_path)
        if tiffs:
            self.load_tiffs(tiffs)

    def note_generated_chart(self, ti2_path: "Path | None") -> None:
        """A chart was just generated (or cleared) in Create Chart — track its
        .ti2 and re-read the Colour row from it.

        Without this the row judged the PREVIOUS chart: generation handed this
        tab only the page images, so a chart from the FROM PROFILE GAMUT
        module — already converted, §3.1a says force Raw — still offered
        "Through the profile", and even defaulted to it (Basti, 2026-08-10).
        Deliberately emits nothing: the generation flow already tells the
        other tabs itself.
        """
        self._current_ti2 = Path(ti2_path) if ti2_path else None
        self._update_colour_row_visible()

    def apply_loaded_ti2(self, ti2_path: Path) -> None:
        """Cross-tab sync entry — path is already resolved and on disk.

        Skips resolve_ti2() so the user is not re-prompted with the
        "Continue / Use as base for a new profile" dialog when another
        tab has already loaded this chart into the working folder.
        Deliberately does not emit ti2_loaded — that would echo back
        through the cross-tab graph and re-trigger the sender.
        """
        from ui.ti2_loader import _related_files
        if not ti2_path.exists() or ti2_path == self._current_ti2:
            return
        _, tiffs = _related_files(ti2_path)
        self._current_ti2 = ti2_path
        if tiffs:
            self.load_tiffs(tiffs)

    def _reveal_folder(self) -> None:
        """Open the current chart's folder in the file manager (Knut — same
        button as the other tabs, for consistency)."""
        from core.preset_store import reveal_in_file_manager
        ti2 = getattr(self, "_current_ti2", None)
        if ti2 is not None:
            target = Path(ti2).parent
        else:
            custom = str(self._settings.get("custom_output_path", "")).strip()
            target = Path(custom).expanduser() if custom else default_output_root()
        reveal_in_file_manager(target)

    def _on_load_ti2(self) -> None:
        from ui.ti2_loader import resolve_ti2
        path = open_file_dialog(
            self, tr("Select .ti2 file to load its chart"), tr("ArgyllCMS target files (*.ti2)"),
            extra_path=self._settings.get("custom_output_path", ""),
            declutter_settings=self._settings,
        )
        if not path:
            return
        result = resolve_ti2(self, Path(path), self._settings,
                             getattr(self, "_target_ctl", None))
        if result is None:
            return
        ti2_path, tiffs = result
        if ti2_path != self._current_ti2:
            self._current_ti2 = ti2_path
            self.ti2_replaced.emit()
        self.ti2_loaded.emit(ti2_path)
        # Mirror this explicit load into the Create Chart tab (reflect-only).
        self.chart_load_requested.emit(ti2_path, list(tiffs or []))
        if tiffs:
            self.load_tiffs(tiffs)
        else:
            self._set_status(tr("No TIFF files found matching the selected .ti2 file."))

    def _on_load_image(self) -> None:
        """#117 (Knut): print any TIFF raw. Deliberately print-only — the
        measuring workflow needs the chart's own .ti2 (the masthead's "Open
        Chart File (.ti2)", #130 — this tab's grid button is long gone), and a
        bare image can't provide patch geometry."""
        from ui.widgets import open_files_dialog
        paths = open_files_dialog(
            self, tr("Select the TIFF images to print"),
            tr("TIFF images (*.tif *.tiff)"),
            extra_path=self._settings.get("custom_output_path", ""),
            preview=True,
            declutter_settings=self._settings,
        )
        if not paths:
            return
        # A foreign image invalidates the loaded chart context downstream
        # (Profile / Check tabs) — same as loading a different chart.
        if self._current_ti2 is not None:
            self._current_ti2 = None
            self.ti2_replaced.emit()
        self.load_tiffs([Path(p) for p in paths])
        self._set_status(tr(
            "Image loaded for printing (no colour management). To measure a "
            "chart afterwards, open its .ti2 with “Open Chart File "
            "(.ti2)” at the top left of the window: an image alone "
            "carries no patch geometry."))

    def _blocked_by_new_run(self) -> bool:
        """True — and the explaining pop-up has been shown — when the bar's
        **Profile run** is "New run" (#130, Knut). A run has to exist before its
        chart can be printed."""
        ctl = getattr(self, "_target_ctl", None)
        if ctl is None or ctl.target.profile_run:
            return False
        from PyQt6.QtWidgets import QMessageBox
        from core.measurement_target import new_run_guard_message
        inform(self, tr("Choose a profile run to print"),
                                new_run_guard_message("print"))
        return True

    def _on_print_current(self) -> None:
        if not self._preview._pages:
            return
        if self._blocked_by_new_run():
            return
        pages = [self._preview._pages[self._preview._current]]
        # Feature A: the verification conversion + route handling sit below
        # BOTH print buttons, before the two print paths split (§5 A2.2).
        pages = self._apply_verification_colour(pages)
        if pages is None:
            return
        if self._settings.get("use_native_print_dialog", False):
            self._print_native(pages)
            return
        self._print_pages(pages)

    def _on_print_all(self) -> None:
        if not self._preview._pages:
            return
        if self._blocked_by_new_run():
            return
        pages = self._apply_verification_colour(list(self._preview._pages))
        if pages is None:
            return
        if self._settings.get("use_native_print_dialog", False):
            self._print_native(pages)
            return
        self._print_pages(pages)

    def _print_pages(self, pages: list[tuple[Path, int]]) -> None:
        """Run pre-send checks + preflight once, then submit each page."""
        printer = self._printer_combo.currentData() or ""
        if not printer:
            warn(self, tr("No Printer"), tr("Please select a printer before printing."))
            return

        if not self._printer.is_printer_reachable(printer):
            message_box(
                QMessageBox.Icon.Critical, self, tr("Printer Offline"),
                tr("The printer \"{printer}\" appears to be offline or unreachable.\n"
                   "Please check that it is powered on and connected."
                   ).format(printer=printer),
            )
            return

        if not self._handle_stuck_jobs(printer):
            return

        if is_windows() and not self._windows_queue_takes_postscript(printer):
            # #205: the driver takes RGB only; an RGB chart goes through the
            # Windows dialog (on this printer), any other is refused
            self._print_windows_not_postscript(pages, printer)
            return

        selected_opts = {k: (c.currentData() or "") for k, c in self._option_combos.items()}
        first_tiff, _ = pages[0]
        orientation, page_size_pt, mismatch = self._compute_geometry(
            printer, selected_opts, first_tiff
        )

        # Independent of the preflight setting: borderless physically cannot
        # print at 100% (the driver enlarges the page a few percent so ink
        # reaches past the paper edges — Epson PPDs bake a 1.03–1.07
        # cupsBorderlessScalingFactor into their borderless sizes, Canon
        # scales via its extension setting). A scaled chart shifts every
        # patch, so always warn before wasting paper and ink.
        if _borderless_selected(selected_opts) and not self._confirm_borderless():
            return

        # Beta 15: a Canon or Epson model whose paper profiles ChromIQ does not
        # know (not in the driver's tables, not built in, not learned) is not
        # printed with a guessed profile without asking.
        unknown = self._unknown_paper_profile(printer, selected_opts, first_tiff)
        if unknown is not None:
            choice = self._ask_unknown_paper_profile(printer, unknown)
            if choice == "dialog":
                self._print_native(pages, printer=printer)
                return
            if choice != "anyway":
                return

        # 4.3.5 beta 2 (Basti, 2026-10-13): a run that prints "like Preview"
        # gets a different form on a PostScript printer than this route can
        # send; asked on every such print once M-PRINT-DIRECT-LIKE-PREVIEW is
        # approved.
        like_preview = self._ask_direct_like_preview(printer)
        if like_preview == "dialog":
            self._print_native(pages, printer=printer)
            return
        if like_preview not in ("anyway", None):
            return
        # 4.3.8 (Knut's run 6): a verification chart whose profiling chart may
        # have gone through 4.3.4's dialog, where the printer converted it.
        # Basti, 2026-10-20: the window offers that way too.
        if like_preview is None:
            old_way = self._ask_verify_after_an_old_dialog_profile(printer)
            if old_way == "dialog":
                from workflow import ppd_color as _f
                self._ps_form_this_print = _f.POSTSCRIPT_AS_MACOS
                try:
                    self._print_native(pages, printer=printer)
                finally:
                    self._ps_form_this_print = None
                return
            if old_way not in ("anyway", None):
                return

        # 4.3.5 B2: a chart that is not RGB on a queue that converts its inks
        # (RGB raster) or may print them as a mix (DeviceN). None, and no
        # question, for every RGB chart.
        self._pending_ink_conversion = self._ink_conversion(
            printer, selected_opts, first_tiff, pages[0][1])
        if (self._pending_ink_conversion is not None
                and not self._ask_ink_conversion(printer, self._pending_ink_conversion)):
            return

        # Beta-16 review: a chart LARGER than the paper is shrunk by the
        # printing system to fit (measured: an A4 chart on a PictureMate's
        # 9 x 13 cm paper and on a DNP's 6 x 8 in), which moves every patch
        # out from under the instrument.  The confirmation window, which says
        # so, then shows even when it was switched off.
        too_big = bool(mismatch) and self._chart_larger_than_page(
            first_tiff, getattr(self, "_checked_page_pt", None) or page_size_pt)
        # A CHART A LITTLE LARGER THAN ITS PAPER (jctay 149803, Basti
        # 2026-10-23): printed at exactly 100 %, with no question, when only
        # empty margin is outside the paper (workflow.overhang), moved so the
        # cut falls in that margin; never shrunk. When more would be lost the
        # confirmation window says so, whether or not it was switched off.
        self._print_shift_pt = None
        ps_page_pt = page_size_pt
        paper_pt = getattr(self, "_checked_page_pt", None) or page_size_pt
        over = self._overhang_plan(pages, paper_pt)
        if over is not None and over.safe:
            too_big = False
            mismatch = None
            self._print_shift_pt = over.shift_pt()
            # "Printer Default": the page is the default paper, so nothing
            # downstream fits a page of the chart's own size to it
            ps_page_pt = page_size_pt or paper_pt
            self._note_overhang(over)
        elif over is not None and over.reason != "too_much":
            too_big = True
            mismatch = self._overhang_text(
                over, first_tiff, paper_pt, anyway=True)[1]
        if self._settings.get("confirm_before_printing", True) or too_big:
            if not self._show_preflight(
                printer, selected_opts, orientation, page_size_pt,
                mismatch, len(pages), first_tiff=first_tiff,
            ):
                return
        elif mismatch:
            log.warning("Preflight disabled; printing despite mismatch: %s", mismatch)

        from workflow import ppd_color as _forms
        from workflow import verification_print as _vp
        self._note_print_path(
            _vp.PATH_DIRECT, printer,
            _forms.POSTSCRIPT_DEVICE_RGB if self._is_postscript_queue(printer) else "")
        submitted = False
        from workflow import overhang as _overhang
        with _overhang.placed(self._print_shift_pt):
            for path, frame in pages:
                if self._send_page(path, frame, orientation, ps_page_pt):
                    submitted = True
        self._print_shift_pt = None
        self._commit_print_record(submitted)

    # ---- a chart a little larger than its paper (workflow.overhang) -------
    def _overhang_plan(self, pages, paper_pt):
        """The plan for a chart larger than *paper_pt*; None when it fits as
        it is, or when the sizes cannot be compared."""
        if not pages or not paper_pt:
            return None
        from workflow import overhang as O
        try:
            chart_pt = read_tiff_dimensions_points(pages[0][0])
        except Exception:  # noqa: BLE001 - nothing to compare
            return None
        pw, ph = O.paper_like_chart(chart_pt, paper_pt)
        tol = O.NO_OVERHANG_MM / O.MM_PER_PT
        if chart_pt[0] <= pw + tol and chart_pt[1] <= ph + tol:
            return None
        plan = O.plan_for_chart(pages, chart_pt, paper_pt)
        log.info("Print: the chart (%.1f x %.1f mm) is larger than the paper "
                 "(%.1f x %.1f mm): %s%s", chart_pt[0] * O.MM_PER_PT,
                 chart_pt[1] * O.MM_PER_PT, pw * O.MM_PER_PT, ph * O.MM_PER_PT,
                 "safe at 100 %, " if plan.safe else f"not safe ({plan.reason})",
                 plan.describe() if plan.safe else "")
        return plan

    @staticmethod
    def _overhang_text(plan, first_tiff, paper_pt, *, anyway: bool):
        """M-PRINT-CHART-CUT for *plan* (title, body)."""
        from workflow import measurement_messages as MM
        from workflow import overhang as O

        def mm(w, h):
            return f"{w * O.MM_PER_PT:.0f} × {h * O.MM_PER_PT:.0f} mm"
        try:
            cw, ch = read_tiff_dimensions_points(first_tiff)
        except Exception:  # noqa: BLE001
            cw = ch = 0.0
        pw, ph = O.paper_like_chart((cw, ch), paper_pt)
        why = {"content": MM._CUT_WHY_CONTENT, "lead": MM._CUT_WHY_LEAD}.get(
            plan.reason, MM._CUT_WHY_UNKNOWN)
        return MM.M_PRINT_CHART_CUT.render(
            chart=mm(cw, ch), paper=mm(pw, ph), why=tr(why),
            outcome=tr(MM._CUT_OUTCOME_ANYWAY if anyway
                       else MM._CUT_OUTCOME_NOTHING))

    def _note_overhang(self, plan) -> None:
        """The quiet line, and the print record's note, for a chart printed at
        100 % with only empty margin outside the paper."""
        from workflow import measurement_messages as MM
        c = plan.cut_mm
        caption = bool(getattr(plan, "caption_cut", lambda: False)())
        marks = dict(getattr(plan, "markers_cut", None) or {})
        sides = {"left": f"{c.get('left', 0):.1f}",
                 "right": f"{c.get('right', 0):.1f}",
                 "top": f"{c.get('top', 0):.1f}",
                 "bottom": f"{c.get('bottom', 0):.1f}"}
        if marks:
            words = {"top": MM._MARKS_TOP, "bottom": MM._MARKS_BOTTOM,
                     "left": MM._MARKS_LEFT, "right": MM._MARKS_RIGHT}
            listed = ", ".join(
                tr(words[k]).format(n=marks[k])
                for k in ("top", "bottom", "left", "right") if marks.get(k))
            line = tr(MM._OVER_PAPER_LOG_MARKERS).format(marks=listed, **sides)
        else:
            line = tr(MM._OVER_PAPER_LOG_CAPTION if caption
                      else MM._OVER_PAPER_LOG).format(**sides)
        log.info("Print: %s", line)
        try:
            self._set_status(line)
        except Exception:  # noqa: BLE001 - a status line is never worth a crash
            pass
        pending = getattr(self, "_pending_print_record", None)
        if pending is not None:
            pending[1]["outside_paper_mm"] = {k: round(float(v), 1)
                                              for k, v in c.items()}
            if marks:
                # which marks were cut, edge by edge (Basti, 2026-10-23)
                pending[1]["ruler_marks_outside_paper"] = marks
            if caption:
                pending[1]["caption_outside_paper_mm"] = {
                    k: round(float(v), 1)
                    for k, v in plan.caption_cut_mm.items()}

    @staticmethod
    def _windows_queue_takes_postscript(printer: str) -> bool:
        from workflow import win_spooler
        return win_spooler.is_postscript(printer)

    @staticmethod
    def _non_rgb_inks(pages: list[tuple[Path, int]]) -> "str | None":
        """The inks of the first page that is not RGB (``chart_inks
        .ink_set_label``), None when every page is RGB or grey. A page that
        cannot be read counts as RGB here: the print path says why it cannot
        print it, as before."""
        from workflow import chart_inks
        for tiff, frame in pages:
            try:
                codes = (_find_sidecar_channels(tiff)
                         or chart_inks.sidecar_ink_codes(tiff))
                if chart_inks.is_rgb_page(tiff, frame, codes):
                    continue
                n, phot = chart_inks.page_photometric(tiff, frame)
                if n < 3:
                    continue           # grey: GDI carries it as it is
                plan = chart_inks.plan_for(n, phot, codes)
                inks = list(plan.codes) if plan is not None else codes
                return chart_inks.ink_set_label(inks, n)
            except Exception:  # noqa: BLE001
                log.debug("ink check of %s failed", tiff, exc_info=True)
        return None

    def _show_print_refusal(self, title: str, body: str) -> None:
        """A §M refusal: its headline IN the box, the body under it."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        set_warning_icon(box)
        box.setText(title)
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _confirm_other_printer(self, wanted: str, chosen: str) -> bool:
        """M-PRINT-WIN-DIALOG-OTHER-PRINTER: the Windows print dialog came back
        with another printer than the one handed to it. True prints on
        *chosen*; Cancel (the default) prints nothing."""
        from workflow import measurement_messages as MM
        title, body = MM.M_PRINT_WIN_DIALOG_OTHER_PRINTER.render(
            wanted=wanted, chosen=chosen)
        box = QMessageBox(self)
        box.setWindowTitle(title)
        set_warning_icon(box)
        box.setText(title)
        box.setInformativeText(body)
        # '&' would be a mnemonic on a button (review finding 7)
        go = box.addButton(tr(MM._PRINT_OTHER_PRINTER_BTN).format(
                               printer=chosen.replace("&", "&&")),
                           QMessageBox.ButtonRole.AcceptRole)
        cancel = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() is go:
            log.warning("Print: printed on %s, which the Windows print dialog chose, "
                        "instead of %s", chosen, wanted)
            return True
        log.info("Print: cancelled; the Windows print dialog chose %s, not %s",
                 chosen, wanted)
        return False

    def _print_windows_not_postscript(self, pages: list[tuple[Path, int]],
                                      printer: str) -> None:
        """#205: ChromIQ's own route, a Windows printer whose driver is not
        PostScript. Its driver takes RGB only (GDI), so an RGB chart is handed
        to the Windows print dialog opened on this printer, and a CMYK or
        multi-ink chart is refused (M-PRINT-WIN-INKS-NOT-POSTSCRIPT): through
        the driver every patch would be converted."""
        inks = self._non_rgb_inks(pages)
        if inks is None:
            log.info("Print: %s is not a PostScript printer; the RGB chart goes "
                     "through the Windows print dialog", printer)
            self._print_native(pages, printer=printer)
            return
        from workflow import measurement_messages as MM
        log.warning("Print: refused a %s chart on %s, which is not a PostScript "
                    "printer (M-PRINT-WIN-INKS-NOT-POSTSCRIPT)", inks, printer)
        self._show_print_refusal(*MM.M_PRINT_WIN_INKS_NOT_POSTSCRIPT.render(
            printer=printer, inks=inks))
        self._commit_print_record(False)

    def _commit_print_record(self, submitted: bool) -> None:
        """Write the held print record, or drop it (R6 F5).

        Called by both print paths and by nothing else, so a route that ends in
        a refusal, a cancelled window or a rejected job leaves no record at
        all — and the next sheet is asked about rather than assumed.
        """
        pending, self._pending_print_record = self._pending_print_record, None
        if pending is None or not submitted:
            if pending is not None:
                log.info("nothing was submitted; no print record written")
            return
        ti2, kwargs = pending
        from workflow import verification_print as vp
        vp.write_print_record(ti2, **kwargs)

    def _confirm_borderless(self) -> bool:
        """Warn that borderless scales the chart. Returns False to cancel."""
        dlg = QMessageBox(self)
        dlg.setWindowTitle(tr("Borderless Will Scale the Chart"))
        set_warning_icon(dlg)
        dlg.setText(
            tr("Borderless printing enlarges the page by a few percent so the "
            "ink reaches past the paper edges. The printer driver does this "
            "and it cannot be turned off — it is what borderless means.\n\n"
            "A profiling chart must print at exactly 100%: enlarging it "
            "shifts every patch, so the measurement reads the wrong "
            "positions.\n\n"
            "Switch borderless off and print with borders instead — the "
            "chart's white margins are made for that.")
        )
        anyway_btn = dlg.addButton(
            tr("Print Borderless Anyway"), QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(cancel_btn)
        dlg.exec()
        if dlg.clickedButton() is anyway_btn:
            log.warning("Borderless print confirmed by user despite scaling warning")
            return True
        return False

    def _handle_stuck_jobs(self, printer: str) -> bool:
        """Prompt to clear stuck jobs. Returns False if user cancels."""
        stuck = self._module.get_stuck_jobs(printer)
        if not stuck:
            return True
        n = len(stuck)
        dlg = QMessageBox(self)
        dlg.setWindowTitle(tr("Stuck Print Jobs Detected"))
        set_warning_icon(dlg)
        if n == 1:
            head = tr("There is 1 stuck print job in the queue for \"{printer}\"."
                      ).format(printer=printer)
        else:
            head = tr("There are {n} stuck print jobs in the queue for \"{printer}\"."
                      ).format(n=n, printer=printer)
        dlg.setText(
            head + "\n\n"
            + tr("Stuck jobs can block new print jobs from being processed.\n"
                 "Clear them before printing?")
        )
        clear_btn  = dlg.addButton(tr("Clear && Print"),  QMessageBox.ButtonRole.AcceptRole)
        # K44 (beta 43, 2026-09-25): a destructive action is never drawn
        # filled.
        from ui.default_button import mark_destructive
        mark_destructive(clear_btn)
        anyway_btn = dlg.addButton(tr("Print Anyway"),
                                   QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        # Knut, #182 5835722977 (beta 43): "I think Cancel as the default is
        # the safest." Return presses Cancel; the destructive action stays
        # plain (B8-1156) and is reached by a click.
        dlg.setDefaultButton(cancel_btn)
        dlg.exec()
        clicked = dlg.clickedButton()
        # Only an answer that says "print" prints. A box closed without one
        # (reject() from code, the window torn down) is a Cancel, never a
        # print (review P_review2_beta1 W-1).
        if clicked not in (clear_btn, anyway_btn):
            return False
        if clicked is clear_btn:
            cleared = self._module.cancel_all_jobs(printer)
            log.info("Cleared %d stuck job(s) before printing", cleared)
        return True

    def _compute_geometry(
        self,
        printer: str,
        selected_opts: dict[str, str],
        tiff_path: Path,
    ) -> tuple[int | None, tuple[float, float] | None, str | None]:
        """Return (orientation, page_size_pt, mismatch_msg) for the given selection.

        Any/all may be None if PageSize is unset or the PPD doesn't declare
        physical dimensions (typical for AirPrint/Driverless queues).
        """
        self._checked_page_pt = None
        size_key = next(
            (k for k in _PAGE_SIZE_KEYS if selected_opts.get(k)),
            None,
        )
        size_display = ""
        if size_key is None:
            # Beta-16 review: with the paper size left at "Printer Default"
            # (or not offered in the tab, as on the PictureMate) the job
            # prints on the PPD's default paper, so that is what the chart is
            # compared with.  Before, nothing was compared and an A4 chart
            # went onto 9 x 13 cm paper shrunk, without a word.
            size_raw, size_display = self._ppd_default_page(printer)
            if not size_raw:
                return None, None, None
        else:
            size_raw = selected_opts[size_key]
        # Some vendor drivers (e.g. Epson EPIJ_Size) use opaque integer codes
        # for raw values but key *PaperDimension by display label. Pass both.
        combo = self._option_combos.get(size_key) if size_key else None
        if combo is not None:
            size_display = combo.currentText()
        page_dims = self._module.get_page_size_points(printer, size_raw, size_display)
        if not page_dims:
            return None, None, None
        imageable = self._module.get_imageable_area_points(printer, size_raw, size_display)
        try:
            tiff_w_pt, tiff_h_pt = read_tiff_dimensions_points(tiff_path)
        except Exception as exc:
            log.warning("Could not read TIFF dimensions for %s: %s", tiff_path.name, exc)
            return None, page_dims, None
        page_w_pt, page_h_pt = page_dims
        orientation = compute_orientation(tiff_w_pt, tiff_h_pt, page_w_pt, page_h_pt)
        mismatch = check_size_mismatch(
            tiff_w_pt, tiff_h_pt, page_w_pt, page_h_pt, imageable_pt=imageable,
        )
        self._checked_page_pt = page_dims
        if size_key is None:
            # only the check: the job itself stays exactly as before (no
            # PageSize, no orientation, the PostScript page the chart's own)
            return None, None, mismatch
        return orientation, page_dims, mismatch

    def _ppd_default_page(self, printer: str) -> tuple[str, str]:
        """(value, label) of the PPD's default paper size, ("", "") when the
        queue has no PPD or no default."""
        try:
            from core.text_io import read_text
            from workflow.ppd_color import _ppd_default, parse_ppd_options
            ppd = self._module._find_ppd_path(printer)
            if not ppd:
                return "", ""
            text = read_text(Path(ppd), lenient=True)
            blocks = {k: dict(v) for k, _l, v in parse_ppd_options(text)}
            for key in ("PageSize", "EPIJ_Size", "media"):
                val = _ppd_default(text, key)
                if val:
                    return val, blocks.get(key, {}).get(val, "")
        except Exception as exc:  # noqa: BLE001 - only a check, never a reason not to print
            log.warning("default paper size of %s not read: %s", printer, exc)
        return "", ""

    @staticmethod
    def _chart_larger_than_page(tiff: Path | None,
                                page_size_pt: tuple[float, float] | None) -> bool:
        """True when the chart does not fit the paper in either orientation
        (2 % slack), so the printing system would shrink it."""
        if tiff is None or not page_size_pt:
            return False
        try:
            w, h = read_tiff_dimensions_points(tiff)
        except Exception:  # noqa: BLE001
            return False
        pw, ph = page_size_pt
        fits = (w <= pw * 1.02 and h <= ph * 1.02) or (h <= pw * 1.02 and w <= ph * 1.02)
        return not fits

    def _show_preflight(
        self,
        printer: str,
        selected_opts: dict[str, str],
        orientation: int | None,
        page_size_pt: tuple[float, float] | None,
        mismatch: str | None,
        page_count: int,
        first_tiff: Path | None = None,
    ) -> bool:
        """Show the preflight dialog. Returns True if user accepts."""
        # Beta 15: every row name and fixed value goes through tr(); until now
        # only the colour rows did, so a German window was half English.
        rows: list[tuple[str, str]] = [(tr("Printer"), printer)]
        size_mm = None
        if page_size_pt is not None:
            w_mm = page_size_pt[0] * 25.4 / 72.0
            h_mm = page_size_pt[1] * 25.4 / 72.0
            size_mm = f"{w_mm:.0f} × {h_mm:.0f} mm"
        # Per-option rows, using the human-readable category label and the
        # selected combo's display text (not the raw CUPS value).
        size_row = None
        for opt_name, combo in self._option_combos.items():
            raw = combo.currentData() or ""
            if not raw:
                continue
            # Get the category label from the layout row's QLabel.
            label = self._option_label_for(opt_name)
            if size_row is None and opt_name in _PAGE_SIZE_KEYS:
                # BY NAME, AS THE PAGE SIZE ITSELF IS FOUND (R3): the
                # millimetres are those of this option's paper, and a label
                # with "paper size" in it can belong to another option (Xerox:
                # "Booklet Paper Size"; generic PPDs: PageRegion, "Media Size")
                size_row = len(rows)
            rows.append((label, combo.currentText()))
        if orientation is not None:
            rows.append((
                tr("Orientation"),
                tr("Landscape (auto)") if orientation == ORIENTATION_LANDSCAPE
                else tr("Portrait (auto)"),
            ))
        if size_mm is not None and size_row is not None:
            # ONE ROW FOR THE PAPER (B3, Knut's screenshot of 2026-10-10): the
            # driver's "Media Size: A4" and ChromIQ's own "Media size: 210 ×
            # 297 mm" stood two rows apart under nearly the same name. The
            # millimetres now follow the paper's name in its own row.
            name, value = rows[size_row]
            rows[size_row] = (name, f"{value} ({size_mm})")
        elif size_mm is not None:
            rows.append((tr("Media size"), size_mm))
        rows.append((tr("Duplex"), tr("Off (forced)")))
        rows.extend(self._colour_rows(printer, selected_opts, first_tiff))

        warnings: list[str] = []
        if mismatch:
            warnings.append(mismatch)
        if _borderless_selected(selected_opts):
            warnings.append(tr(
                "Borderless is enabled: the driver enlarges the page a few "
                "percent to reach past the paper edges, so the chart will NOT "
                "print at 100% and patches shift. Print with borders instead."
            ))

        dlg = PreflightDialog(rows, warnings, page_count, self)
        accepted = dlg.exec() == QDialog.DialogCode.Accepted
        if accepted and dlg.dont_ask_again():
            self._settings.set("confirm_before_printing", False)
        return accepted

    def _colour_rows(self, printer: str, selected_opts: dict[str, str],
                     first_tiff: Path | None) -> list[tuple[str, str]]:
        """The confirmation window's colour rows (M-PRINT-COLOUR-CONFIRM): what
        the job will carry.  A printer whose dialog picks a paper profile gets
        the Photoshop-equivalent job; any other keeps the beta 14 row."""
        from workflow import measurement_messages as MM
        from workflow.cups_printer import CupsRawPrinter, PrintConfig
        pp = None
        if isinstance(getattr(self, "_printer", None), WindowsRawPrinter):
            # #205: raw PostScript, no paper-profile job on Windows
            return [(tr(MM._PRINT_ROW_COLOUR), tr("Off (forced)"))]
        if first_tiff is not None:
            pp = CupsRawPrinter._reference_paper_profile(
                first_tiff, PrintConfig(printer_name=printer, options=selected_opts))
        if pp is None:
            return [(tr(MM._PRINT_ROW_COLOUR), tr("Off (forced)"))]
        rows = [(tr(MM._PRINT_ROW_COLOUR), tr(MM._PRINT_ROW_COLOUR_BY_CHROMIQ)),
                (tr(MM._PRINT_ROW_PAPER_PROFILE), pp.label)]
        if pp.rule.own_colour_off_needs_paper_profile and pp.known:
            # Review 2: not for a model ChromIQ does not know ("Print Anyway"
            # after M-PRINT-PAPER-PROFILE-UNKNOWN). The "on" value says "as for
            # prints from Photoshop", which nobody knows for that paper there.
            rows.append((tr(MM._PRINT_ROW_PRINTER_COLOUR),
                         tr(MM._PRINT_ROW_PRINTER_COLOUR_ON if pp.is_default
                            else MM._PRINT_ROW_PRINTER_COLOUR_OFF)))
        return rows

    def _unknown_paper_profile(self, printer: str, selected_opts: dict[str, str],
                               first_tiff: Path | None):
        """The paper profile of this job when ChromIQ does not know it (a Canon
        or Epson model in no table and not learned), else None.  macOS only:
        elsewhere the direct route keeps the beta 14 job."""
        if first_tiff is None or not is_macos():
            return None
        from workflow.cups_printer import CupsRawPrinter, PrintConfig
        try:
            pp = CupsRawPrinter._reference_paper_profile(
                first_tiff, PrintConfig(printer_name=printer, options=selected_opts))
        except Exception as exc:  # noqa: BLE001
            log.warning("paper-profile lookup failed: %s", exc)
            return None
        if pp is None or pp.known:
            return None
        log.warning("Print: %s (%s), medium %s=%s: paper profile unknown (not in the "
                    "driver's tables, not built in, not learned); asking the user",
                    printer, pp.model, pp.rule.media_option, pp.media_value)
        return pp

    def _direct_print_needs_like_preview_question(self, printer: str) -> bool:
        """True when a print by the direct route goes to a PostScript queue
        while the target's choice (the run's own, its parent's or the
        project's) is "Preview and most other apps": the direct route can
        only send the chart as the printer's own RGB."""
        from workflow import ppd_color as forms
        if not is_macos():
            # its choices are those of the macOS dialog (#205: not Windows)
            return False
        if self._ps_form_stored() != forms.POSTSCRIPT_AS_MACOS:
            return False
        return self._is_postscript_queue(printer)

    def _verify_after_an_old_dialog_profile(self, printer: str) -> bool:
        """True when a VERIFICATION chart is about to go by the direct route
        to a PostScript printer while its run's profiling chart was printed by
        ChromIQ 4.3.4 or earlier without saying which way
        (``profiling_chart_may_be_from_the_old_dialog``: its record, or with
        no record the profile's date). Through 4.3.4's dialog macOS
        marked the chart as sRGB, or with the queue's ColorSync profile, and
        the printer converted it; the direct route sends the printer's own
        RGB, so the sheet will not match the profile (Knut's run 6, printed
        2026-10-14: mean dE00 8.7 against its profile, 2.0 against a profile
        made by the direct route on the same printer)."""
        if not is_macos() or not self._target_is_verification():
            return False
        run = self._cm_run()
        if run is None:
            return False
        from workflow import verification_print as vp
        rec = self._profiling_chart_record(run)
        try:
            profile = run.built_profile_icc()
        except Exception:  # noqa: BLE001
            profile = None
        if not vp.profiling_chart_may_be_from_the_old_dialog(rec, profile):
            return False
        return self._is_postscript_queue(printer)

    def _ask_verify_after_an_old_dialog_profile(self, printer: str) -> "str | None":
        """M-PRINT-VERIFY-PS-EARLIER-ASK (proposed; Basti's decision of
        2026-10-20) as a window before a direct-route print (4.3.8, P18):
        None when it does not apply (the print goes on), else "dialog" (send
        it through the macOS print dialog, letting the printer adjust the
        colours, as the old profiling chart may have gone), "anyway", or ""
        (Cancel, the default: nothing sent). The tab's note keeps the approved
        M-PRINT-VERIFY-PS-EARLIER."""
        if not self._verify_after_an_old_dialog_profile(printer):
            return None
        from workflow import measurement_messages as MM
        title, body = MM.M_PRINT_VERIFY_PS_EARLIER_ASK.render()
        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        set_warning_icon(dlg)
        dlg.setText(title)
        dlg.setInformativeText(body)
        dialog_btn = dlg.addButton(tr(MM._PRINT_LIKE_PREVIEW_BTN_DIALOG),
                                   QMessageBox.ButtonRole.AcceptRole)
        anyway_btn = dlg.addButton(tr(MM._PRINT_LIKE_PREVIEW_BTN_ANYWAY),
                                   QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(cancel_btn)
        dlg.setEscapeButton(cancel_btn)
        from ui.widgets import (fit_message_box_buttons,
                                keep_message_box_inside_the_work_area)
        keep_message_box_inside_the_work_area(dlg)
        fit_message_box_buttons(dlg)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked is dialog_btn:
            log.info("Print: a verification chart handed to the macOS print dialog, "
                     "letting the printer adjust the colours (M-PRINT-VERIFY-PS-EARLIER-ASK)")
            return "dialog"
        if clicked is anyway_btn:
            log.warning("Print: a verification chart sent by the direct route to %s "
                        "although its profiling chart may have gone through the "
                        "4.3.4 dialog", printer)
            return "anyway"
        log.info("Print: cancelled at M-PRINT-VERIFY-PS-EARLIER-ASK; nothing sent")
        return ""

    def _ask_direct_like_preview(self, printer: str) -> "str | None":
        """M-PRINT-DIRECT-LIKE-PREVIEW (approved by Basti, 2026-10-13). None when it does not
        apply (the print goes as before); else "dialog", "anyway" or ""
        (Cancel)."""
        from workflow import measurement_messages as MM
        msg = MM.M_PRINT_DIRECT_LIKE_PREVIEW
        if not self._direct_print_needs_like_preview_question(printer):
            return None
        title, body = msg.render()
        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        set_warning_icon(dlg)
        dlg.setText(title)
        dlg.setInformativeText(body)
        dialog_btn = dlg.addButton(tr(MM._PRINT_LIKE_PREVIEW_BTN_DIALOG),
                                   QMessageBox.ButtonRole.AcceptRole)
        anyway_btn = dlg.addButton(tr(MM._PRINT_LIKE_PREVIEW_BTN_ANYWAY),
                                   QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(dialog_btn)
        dlg.setEscapeButton(cancel_btn)
        from ui.widgets import (fit_message_box_buttons,
                                keep_message_box_inside_the_work_area)
        keep_message_box_inside_the_work_area(dlg)
        fit_message_box_buttons(dlg)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked is dialog_btn:
            return "dialog"
        if clicked is anyway_btn:
            log.warning("Print: a 'like Preview' run printed by the direct route to %s", printer)
            return "anyway"
        return ""

    def _ask_unknown_paper_profile(self, printer: str, pp) -> str:
        """M-PRINT-PAPER-PROFILE-UNKNOWN.  Returns "dialog", "anyway" or ""."""
        from workflow import measurement_messages as MM
        title, body = MM.M_PRINT_PAPER_PROFILE_UNKNOWN.render(
            printer=printer, medium=pp.media_label, profile=pp.label)
        dlg = QMessageBox(self)
        # THE TITLE IN THE WINDOW, NOT ONLY ON ITS FRAME (beta-15 sweep): macOS
        # draws no title on a message box, so a title set only with
        # setWindowTitle is never seen. Like the other §M windows, the title
        # is the box's bold first line and the body its informative text.
        dlg.setWindowTitle(title)
        set_warning_icon(dlg)
        dlg.setText(title)
        dlg.setInformativeText(body)
        dialog_btn = dlg.addButton(tr(MM._PRINT_UNKNOWN_BTN_DIALOG),
                                   QMessageBox.ButtonRole.AcceptRole)
        anyway_btn = dlg.addButton(tr(MM._PRINT_UNKNOWN_BTN_ANYWAY),
                                   QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(dialog_btn)
        dlg.setEscapeButton(cancel_btn)
        from ui.widgets import (fit_message_box_buttons,
                                keep_message_box_inside_the_work_area)
        keep_message_box_inside_the_work_area(dlg)
        fit_message_box_buttons(dlg)
        dlg.exec()
        clicked = dlg.clickedButton()
        if clicked is dialog_btn:
            return "dialog"
        if clicked is anyway_btn:
            log.warning("Print: user printed %s with the driver's standard profile %s",
                        printer, pp.label)
            return "anyway"
        return ""

    # -- the read-back, off the GUI thread ------------------------------------------
    def _start_read_back(self, work, ink_conversion=None, *,
                         printer_adjusts_by_choice: bool = False) -> None:
        """Run *work* (a blocking read-back returning a TicketReport) on a
        background thread and report it when it is done, or say it could not be
        read after ``print_ticket.READ_BACK_TIMEOUT_S`` (review 2026-10-08: it
        ran on the GUI thread, with no timeout of its own)."""
        from workflow.print_ticket import BackgroundReadBack, READ_BACK_TIMEOUT_S
        if not hasattr(self, "_read_backs"):
            self._read_backs = []
            self._read_back_timer = QTimer(self)
            self._read_back_timer.setInterval(100)
            self._read_back_timer.timeout.connect(self._poll_read_backs)
        rb = BackgroundReadBack(work, READ_BACK_TIMEOUT_S)
        # 4.3.5 B2: what ``_ink_conversion`` found for the chart of this job
        # (None for every RGB chart, so their status lines are unchanged).
        rb.ink_conversion = ink_conversion
        rb.printer_adjusts_by_choice = printer_adjusts_by_choice
        self._read_backs.append(rb)
        if not self._read_back_timer.isActive():
            self._read_back_timer.start()

    def _poll_read_backs(self) -> None:
        from workflow import measurement_messages as MM
        # Review 2: a report can open a modal window, whose event loop keeps
        # this timer firing. Without the guard every other finished read-back
        # opened its window on top of the first, so several prints stacked up
        # several windows at once. Now they come one after another.
        if getattr(self, "_reporting_read_back", False):
            return
        self._reporting_read_back = True
        try:
            for rb in list(self._read_backs):
                state = rb.poll()
                if state == "pending":
                    continue
                self._read_backs.remove(rb)
                if state == "timeout" or rb.report is None:
                    log.warning("print ticket: no read-back (%s)",
                                "timed out" if state == "timeout" else rb.error)
                    self._set_status(tr(MM._PRINT_JOB_UNREAD))
                    continue
                conv = getattr(rb, "ink_conversion", None)
                chosen = bool(getattr(rb, "printer_adjusts_by_choice", False))
                if conv is None and not chosen:
                    self._report_job_ticket(rb.report)
                elif not chosen:
                    self._report_job_ticket(rb.report, conv)
                else:
                    self._report_job_ticket(rb.report, conv,
                                            printer_adjusts_by_choice=True)
        finally:
            self._reporting_read_back = False
        if not self._read_backs:
            self._read_back_timer.stop()

    def _report_job_ticket(self, rep, ink_conversion=None, *,
                           printer_adjusts_by_choice: bool = False) -> None:
        """Say what the job read back from the printing system carries
        (M-PRINT-JOB-CONFIRMED), or show M-PRINT-JOB-NOT-AS-SENT /
        M-PRINT-JOB-UNTAGGED."""
        from workflow import measurement_messages as MM
        if rep is None:
            return
        if ink_conversion is not None and rep.read and rep.ok:
            # 4.3.5 B2: the job carries what ChromIQ sent, but the chart's
            # colours are converted on the way, so "The printing system
            # confirms ..." would read as if they were not.
            msg = _ink_conversion_message(ink_conversion)
            self._set_status(tr(msg.title))
            return
        if not rep.read:
            self._set_status(tr(MM._PRINT_JOB_UNREAD))
            return
        if not rep.ok and not rep.mismatches and printer_adjusts_by_choice:
            # R3-1 (Basti, 2026-10-20): the user chose, in the P18 window, to
            # let the printer adjust the colours; that the chart went
            # untagged is what was asked for, so no warning, the plain line
            log.info("print ticket: job %s untagged, as chosen (Use the print "
                     "dialog in M-PRINT-VERIFY-PS-EARLIER-ASK)", rep.job_id)
            self._set_status(tr(MM._PRINT_JOB_SENT_PLAIN).format(job=rep.job_id))
            return
        if not rep.ok and not rep.mismatches:
            # the only problem: the chart could not be given the job's profile
            title, body = MM.M_PRINT_JOB_UNTAGGED.render()
            self._set_status(title)
            warn(self, title, body)
            return
        if not rep.ok:
            self._show_job_not_as_sent(rep)
            return
        pp = rep.paper_profile
        if pp is not None and pp.option in rep.carried:
            text = tr(MM._PRINT_JOB_SENT_PROFILE).format(job=rep.job_id, profile=pp.label)
        else:
            text = tr(MM._PRINT_JOB_SENT_PLAIN).format(job=rep.job_id)
        if rep.tag_matches_job:
            text += " " + tr(MM._PRINT_JOB_SENT_TAGGED)
        elif getattr(rep, "tagged_intent", None) and (pp is None or pp.option not in rep.carried):
            # M-PRINT-JOB-TAGGED-INTENT (approved by Basti, 2026-10-10): after
            # line 2, on a PostScript queue only (``native_print_macos.read_back``
            # sets it there and nowhere else).
            text += " " + MM.M_PRINT_JOB_TAGGED_INTENT.render(
                profile=rep.tagged_intent)[1]
        if getattr(rep, "device_rgb", False):
            # k81: ChromIQ's own PostScript, the chart as DeviceRGB
            # (M-PRINT-JOB-DEVICE-RGB, approved by Basti 2026-10-11)
            text += " " + MM.M_PRINT_JOB_DEVICE_RGB.render()[1]
        if _reset_vendors(rep) == {"Epson"}:
            # M-PRINT-JOB-EPSON-MATCHING-RESET (approved by Basti, 2026-10-10):
            # the Color Matching sheet had chosen the Epson's own matching and
            # ChromIQ set it back after the dialog; the job read back carries
            # the value ChromIQ set (``rep.ok``), so say what happened.
            text += " " + MM.M_PRINT_JOB_EPSON_MATCHING_RESET.render()[1]
        self._set_status(text)

    def _show_job_not_as_sent(self, rep) -> None:
        """M-PRINT-JOB-NOT-AS-SENT, with one line per key that differs."""
        from workflow import measurement_messages as MM
        from workflow.ppd_color import dialog_route_lock_vendor
        if (rep.mismatches and rep.tag_matches_job is not False
                and all(dialog_route_lock_vendor(k) == "Epson" for k in rep.mismatches)):
            # M-PRINT-JOB-EPSON-MATCHING (approved by Basti, 2026-10-10): the
            # only difference is the Epson colour matching the Color Matching
            # sheet chose, which ChromIQ set back and the job still carries.
            title, body = MM.M_PRINT_JOB_EPSON_MATCHING.render()
            self._set_status(title)
            warn(self, title, body)
            return
        lines = [tr(MM._PRINT_JOB_DIFFERS_LINE).format(
                     key=k, got=got if got is not None else "\u2013", want=want)
                 for k, (got, want) in sorted(rep.mismatches.items())]
        if rep.tag_matches_job is False:
            lines.append(tr(MM._PRINT_JOB_UNTAGGED_LINE))
        title, body = MM.M_PRINT_JOB_NOT_AS_SENT.render(details="\n".join(lines))
        self._set_status(title)
        warn(self, title, body)

    def _option_label_for(self, opt_name: str) -> str:
        """Return the human-readable category label currently shown next to
        the combo for *opt_name* (e.g. 'Paper Size', 'Media Type')."""
        for i in range(self._opts_layout.count()):
            item = self._opts_layout.itemAt(i)
            layout = item.layout() if item else None
            if layout is None:
                continue
            # First widget in the row is the QLabel, second is the QComboBox.
            lbl_item = layout.itemAt(0)
            combo_item = layout.itemAt(1)
            if not lbl_item or not combo_item:
                continue
            if combo_item.widget() is self._option_combos.get(opt_name):
                lbl = lbl_item.widget()
                if isinstance(lbl, QLabel):
                    return lbl.text().rstrip(":")
        return opt_name

    def _send_page(
        self,
        tiff_path: Path,
        frame: int = 0,
        orientation: int | None = None,
        page_size_pt: tuple[float, float] | None = None,
    ) -> bool:
        """Submit one page. Returns True when the printing system ACCEPTED it.

        The return value is what decides whether a print record is written
        (R6 F5), so it says only what it can prove: the job was handed to CUPS
        and CUPS took it. Whether ink reached paper is not knowable from here,
        and is not what the record claims.
        """
        printer = self._printer_combo.currentData() or ""
        if not printer:
            warn(self, tr("No Printer"), tr("Please select a printer before printing."))
            return False

        # Extract the target frame to a temporary single-page TIFF when needed.
        tmp_path: Path | None = None
        # 4.3.5 B2: a chart that is not RGB is read and split with tifffile,
        # which keeps every channel and the separated photometric; PIL cannot
        # open a 5-7 ink chart at all. An RGB chart goes on exactly as before.
        ink_plan, rgb_page = None, True
        try:
            from workflow.chart_inks import is_rgb_page, plan_for_file
            _codes = _find_sidecar_channels(tiff_path)
            rgb_page = is_rgb_page(tiff_path, frame, _codes)
            if not rgb_page:
                ink_plan = plan_for_file(tiff_path, frame, _codes)
        except Exception:  # noqa: BLE001 - unreadable here: the old path says why
            ink_plan, rgb_page = None, True
        if not rgb_page:
            try:
                from workflow.chart_inks import split_page
                tmp_path = split_page(tiff_path, frame)
                print_path = tmp_path or tiff_path
            except Exception as exc:
                message_box(
                    QMessageBox.Icon.Critical, self, tr("TIFF Error"),
                    tr("Cannot read TIFF file:\n{name}\n\n{exc}").format(name=tiff_path.name, exc=exc),
                )
                return False
        else:
            try:
                img = Image.open(tiff_path)
                n_frames = getattr(img, "n_frames", 1)
                if n_frames > 1 or frame > 0:
                    img.seek(min(frame, n_frames - 1))
                    fd, tmp_str = tempfile.mkstemp(suffix=".tif")
                    os.close(fd)
                    tmp_path = Path(tmp_str)
                    img.save(tmp_path, format="TIFF")
                    print_path = tmp_path
                else:
                    print_path = tiff_path
            except Exception as exc:
                message_box(
                    QMessageBox.Icon.Critical, self, tr("TIFF Error"),
                    tr("Cannot read TIFF file:\n{name}\n\n{exc}").format(name=tiff_path.name, exc=exc),
                )
                return False

        selected_opts = {k: (c.currentData() or "") for k, c in self._option_combos.items()}
        config = self._module.build_config(printer=printer, options=selected_opts)
        self._set_status(tr("Sending {name} (page {page}) to {printer}…").format(
            name=tiff_path.name, page=frame + 1, printer=printer))

        # `print_job_ps` reports the exit code through `on_finish`, and calls it
        # before returning on every one of its paths (PS, the PDF retry, the
        # TIFF retry, and a failure to generate PostScript at all). Recorded in
        # a cell rather than returned, so a path that ever became asynchronous
        # would leave this False — which asks the person how the sheet was
        # printed instead of assuming, the safe way round.
        accepted = [False]

        def _cleanup_and_finish(code: int) -> None:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
            accepted[0] = (code == 0)
            self._on_print_done(code)

        ink_channels = _find_sidecar_channels(tiff_path)
        if ink_channels is None and not rgb_page:
            from workflow.chart_inks import sidecar_ink_codes
            ink_channels = sidecar_ink_codes(tiff_path)
        self._printer.last_job_id = None
        # the chart's own name for a failure window: the file printed may be
        # a temporary single page (regression review of #205)
        self._page_name_for_messages = tiff_path.name
        self._printer.print_job_ps(
            print_path, config,
            ink_channels=ink_channels,
            on_finish=_cleanup_and_finish,
            orientation=orientation,
            page_size_pt=page_size_pt,
            pdf_fallback=is_macos() and bool(
                self._settings.get("pdf_print_fallback", True)
            ),
        )
        if accepted[0] and is_macos():
            # macOS only: Linux keeps beta 14's status line (review 2026-10-08).
            self._read_back_lp_job(printer)
        return accepted[0]

    def _read_back_lp_job(self, printer: str) -> None:
        """Read the job lp just created back from CUPS, on a background thread,
        and report it."""
        self._start_read_back(_LpReadBack(
            printer, getattr(self._printer, "last_job_id", None),
            dict(getattr(self._printer, "last_expected", {}) or {})),
            ink_conversion=getattr(self, "_pending_ink_conversion", None))

    def _ink_conversion(self, printer: str, options: dict,
                        tiff_path: Path, frame: int = 0):
        """4.3.5 B2: ``(route, inks, extra)`` when the chart is NOT RGB and this
        queue changes its inks (``ppd_color.ink_route``: "converted" or
        "approximate"), else None. Always None for an RGB or grey chart."""
        try:
            from workflow import chart_inks
            from workflow.ppd_color import ink_route
            codes = _find_sidecar_channels(tiff_path) or chart_inks.sidecar_ink_codes(tiff_path)
            if chart_inks.is_rgb_page(tiff_path, frame, codes):
                return None
            n, phot = chart_inks.page_photometric(tiff_path, frame)
            if n < 3:
                return None
            plan = chart_inks.plan_for(n, phot, codes)
            space = plan.space if plan is not None else (
                "DeviceCMYK" if n == 4 else "DeviceN")
            ppd = PrintModule.find_ppd_path(printer)
            if not ppd:
                return None
            from core.text_io import read_text
            route = ink_route(read_text(Path(ppd), lenient=True), space,
                              options, printer)
            if route is None:
                return None
            ink_codes = list(plan.codes) if plan is not None else codes
            return (route, chart_inks.ink_set_label(ink_codes, n),
                    chart_inks.extra_ink_label(ink_codes))
        except Exception:  # noqa: BLE001 - nothing certain to say
            log.debug("ink conversion check failed", exc_info=True)
            return None

    def _ask_ink_conversion(self, printer: str, conv) -> bool:
        """M-PRINT-INKS-CONVERTED / -APPROXIMATE before sending: False to
        cancel."""
        route, inks, extra = conv
        msg = _ink_conversion_message(conv)
        log.warning("Print: %s chart (%s) on %s: asked", route, inks, printer)
        title, body = msg.render(printer=_printer_display_name(printer),
                                 inks=inks, extra=extra)
        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        set_warning_icon(dlg)
        dlg.setText(body)
        anyway_btn = dlg.addButton(tr("Print Anyway"),
                                   QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = dlg.addButton(QMessageBox.StandardButton.Cancel)
        dlg.setDefaultButton(cancel_btn)
        dlg.exec()
        return dlg.clickedButton() is anyway_btn

    def _on_print_done(self, code: int) -> None:
        if code == 0:
            self._set_status(tr("Print job submitted successfully."))
        elif is_windows() and getattr(self._printer, "last_error_is_chart", False):
            # the chart could not be read or turned into PostScript: ChromIQ's
            # own failure, said as everywhere else (review finding 6)
            self._set_status(tr("TIFF Error"))
            message_box(
                QMessageBox.Icon.Critical, self, tr("TIFF Error"),
                tr("Cannot read TIFF file:\n{name}\n\n{exc}").format(
                    name=getattr(self, "_page_name_for_messages", "")
                    or getattr(self._printer, "last_chart_name", ""),
                    exc=getattr(self._printer, "last_error", "")))
        elif is_windows():
            # #205: the spooler's own reason; there is no CUPS, nor lp
            from workflow import measurement_messages as MM
            title, body = MM.M_PRINT_WIN_SPOOLER_FAILED.render(
                printer=self._printer_combo.currentData() or "",
                reason=getattr(self._printer, "last_error", "") or "?")
            self._set_status(title)
            self._show_print_refusal(title, body)
        else:
            self._set_status(tr("Print failed (lp exit code {code}).").format(code=code))
            message_box(
                QMessageBox.Icon.Critical, self, tr("Print Error"),
                tr("CUPS rejected the print job (exit code {code}).\n"
                   "Check that the printer is online and the selected options are "
                   "valid.").format(code=code),
            )

    def _on_clear_queue(self) -> None:
        printer = self._printer_combo.currentData() or ""
        if not printer:
            warn(self, tr("No Printer"), tr("Select a printer first."))
            return
        count = self._module.cancel_all_jobs(printer)
        if count:
            # beta 16: translated, with a real singular and plural
            self._set_status(count_phrase(
                count, tr("Cleared 1 job from the queue."),
                tr("Cleared {n} jobs from the queue.")))
        else:
            self._set_status(tr("No jobs in the queue to clear."))

    def _set_status(self, text: str) -> None:
        self._status_lbl.setText(text)
        self._status_lbl.setVisible(bool(text))

    def _set_print_buttons_enabled(self, enabled: bool) -> None:
        self._print_page_btn.setEnabled(enabled)
        self._print_all_btn.setEnabled(enabled)

    def _on_save_defaults(self) -> None:
        s = self._settings
        printer = self._printer_combo.currentData() or ""
        s.set("last_printer", printer)
        if printer and self._option_combos:
            pairs = "|".join(
                f"{k}={combo.currentData() or ''}"
                for k, combo in self._option_combos.items()
            )
            s.set(f"print_opts_{printer}", pairs)
        self._set_status(tr("Print settings saved as defaults."))

    def _restore_defaults(self) -> None:
        pass

    def shutdown(self) -> None:
        """Tear down option widgets and signals before QApplication destructs.

        Mirrors the QtWebEngine shutdown pattern in
        ui/gamut_panel.py::shutdown_webengine: disconnect signals, reparent
        children to None, deleteLater, then pump the event loop so the
        deferred deletes actually run while the main loop is still alive.
        Without this, SIP can follow a half-freed wrapper for one of the
        option combos during QApplication dealloc and EXC_BAD_ACCESS the
        process (issue #19 — macOS "ChromIQ quit unexpectedly").
        """
        try:
            self._printer_combo.currentIndexChanged.disconnect()
        except (TypeError, RuntimeError):
            pass

        for combo in list(self._option_combos.values()):
            try:
                combo.currentIndexChanged.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                combo.setParent(None)
                combo.deleteLater()
            except RuntimeError:
                pass

        # Clear the options group's layout so any sibling labels / placeholder
        # widgets get the same reparent + deleteLater treatment as the combos.
        self._clear_layout(self._opts_layout)

        self._option_combos.clear()
        self._ordered_opts.clear()
        self._raw_value_pairs.clear()

        app = QApplication.instance()
        if app is not None:
            for _ in range(3):
                app.processEvents()

    # ------------------------------------------------------------------
    # Native macOS print dialog
    # ------------------------------------------------------------------

    def apply_native_dialog_mode(self) -> None:
        self._set_native_mode(bool(self._settings.get("use_native_print_dialog", False)))
        header = getattr(self, "_header", None)
        if header is not None:
            header.set_tooltip(*self._compute_print_tooltip())

    def _compute_print_tooltip(self) -> tuple[str, str]:
        if is_windows():
            if bool(self._settings.get("use_native_print_dialog", True)):
                return tr(_TT_TITLE_PRINT), (tr(_TT_BODY_PRINT_WINDOWS) + "\n\n"
                                             + tr(_TT_PRINT_WINDOWS_DIALOG_EXTRA))
            return tr(_TT_TITLE_PRINT), tr(_TT_BODY_PRINT_WINDOWS_DIRECT)
        if is_linux():
            return tr(_TT_TITLE_PRINT), tr(_TT_BODY_PRINT_LINUX)
        if is_macos():
            if bool(self._settings.get("use_native_print_dialog", False)):
                return tr(_TT_TITLE_PRINT), _with_plain_paper(
                    tr(_TT_BODY_PRINT_MACOS_NATIVE))
            return tr(_TT_TITLE_PRINT), _with_plain_paper(
                tr(_TT_BODY_PRINT_MACOS_BYPASS))
        return tr(_TT_TITLE_PRINT), _with_plain_paper(
            tr(_TT_BODY_PRINT_MACOS_BYPASS))

    def _update_verify_route_note(self, native: "bool | None" = None) -> None:
        """M-PRINT-VERIFY-ROUTE (approved by Basti, 2026-10-10): shown on
        macOS for a verification run with a chart loaded, on BOTH routes.
        Since 4.3.5 (k81) its first paragraph only, followed by
        M-PRINT-VERIFY-DIALOG-AS-IS / -THROUGH (dialog route, *native*, else
        the setting; approved by Basti 2026-10-11; not on a printer that takes
        CMYK raster) and M-PRINT-VERIFY-PS-EARLIER once it is approved."""
        lbl = getattr(self, "_verify_route_lbl", None)
        if lbl is None:
            return
        ctl = getattr(self, "_target_ctl", None)
        show = (is_macos() and bool(getattr(self, "_tiff_pages", None))
                and ctl is not None and ctl.target.is_verification())
        if not show:
            lbl.setVisible(False)
            return
        from workflow import measurement_messages as MM
        if native is None:
            native = bool(self._settings.get("use_native_print_dialog", False))
        title, body = MM.M_PRINT_VERIFY_ROUTE.render()
        # k81 (4.3.5): since the dialog route sends a PostScript printer
        # ChromIQ's own PostScript (DeviceRGB), the approved paragraphs 2 and 3
        # are untrue there. Paragraph 1 is shown, and their replacements once
        # approved: the dialog's colour settings for a sheet printed as it is
        # or through the run's profile (Knut 6102031563), and what changed
        # for a PostScript printer.
        paras = body.split("\n\n")[:1]
        # Combined review of 4.3.5: M-PRINT-VERIFY-DIALOG-AS-IS / -THROUGH
        # are untrue where the printer takes CMYK raster (macOS converts the
        # chart into CMYK itself) and on a PostScript printer sent the chart
        # as macOS sends it. Basti, 2026-10-13 ("go with 2"): the printer is
        # chosen only IN the dialog, so the tab cannot tell before it, and
        # they are no longer shown; after the dialog a CMYK raster printer
        # gets M-PRINT-CMYK-RASTER-ROUTE once per run (``_tell_cmyk_raster_once``)
        # and a PostScript printer is asked (``_ask_ps_form``).
        # M-PRINT-VERIFY-PS-EARLIER ("both routes now send the chart as the
        # printer's own RGB") is shown only while that is this run's form for
        # certain: stored, or the default with nobody to be asked.
        from workflow import ppd_color as _forms
        own_rgb = (self._ps_form_for_dialog() == _forms.POSTSCRIPT_DEVICE_RGB
                   if native else self._ps_form() == _forms.POSTSCRIPT_DEVICE_RGB)
        if own_rgb:
            paras.append(MM.M_PRINT_VERIFY_PS_EARLIER.render()[1])
        lbl.setText(f"<b>{_html_escape(title)}</b><br><br>"
                    + "<br><br>".join(_html_escape(p) for p in paras))
        lbl.setVisible(True)

    def _update_cmyk_route_note(self, native: "bool | None" = None) -> None:
        """Put the macOS dialog route's notice on the tab
        (``_macos_dialog_notice``). Called on every entry to the tab."""
        if native is None:
            native = bool(self._settings.get("use_native_print_dialog", False))
        if native and is_macos():
            self._warn_lbl.setText(self._macos_dialog_notice())

    def _macos_dialog_notice(self) -> str:
        """The notice of the macOS print dialog route, the same for every
        printer.

        Basti, 2026-10-13 ("go with 2"): the printer is chosen only IN the
        dialog, so the notice may not depend on the printer the dialog opens
        on. The approved sentences promising that ChromIQ attaches the paper
        profile so macOS does not change the colours, and "This works with any
        printer…", are untrue on a printer whose driver takes CMYK raster and
        on a PostScript printer (combined review of 4.3.5), so the notice is
        the approved one without them, as a CMYK raster printer got it since
        B2. What depends on the printer is said after the dialog: a PostScript
        printer is asked how to print (``_ask_ps_form``), a CMYK raster
        printer gets M-PRINT-CMYK-RASTER-ROUTE once per run
        (``_tell_cmyk_raster_once``), and every job's read-back status line
        says what the printing system holds for it."""
        full = tr("⚠  You are printing via the macOS printer dialog. Verify that the "
                  "paper, media type, and quality you pick match the media you are "
                  "printing on: wrong settings cause incorrect ink laydown and invalid "
                  "colour measurements.\n\n"
                  "ChromIQ asks for application colour matching, as Photoshop does. "
                  "After you close the dialog it attaches the paper profile of the "
                  "medium you chose to the chart, so macOS does not change its "
                  "colours. Pick the right media type: the paper profile follows it. "
                  "Afterwards the Print Chart tab says what the printing system holds "
                  "for the job.\n\n"
                  "This works with any printer: where the driver has paper "
                  "profiles, its own dialog chooses one. You don't need to change "
                  "any colour setting.\n\n"
                  "Prefer no dialog at all? Untick \"Use default macOS printer dialog\" "
                  "in Preferences to send the chart straight to the queue via lp.\n\n"
                  "Allow pigment inks to dry fully before measuring "
                  "(at least 1 h; 24 h for best accuracy).")
        paras = full.split("\n\n")
        if len(paras) != 5:
            return full
        kept = tr("ChromIQ asks for application colour matching, as Photoshop does. "
                  "Afterwards the Print Chart tab says what the printing system holds "
                  "for the job.")
        # Why the dialog shows a colour profile it will not let you switch
        # off (Knut, #182 6144104040, M-PRINT-DIALOG-COLOUR-MATCHING):
        # measured, the dialog's Colour Matching choice does not change the
        # job (report folder 2026-10-13_b3_knut/item3).
        from workflow import measurement_messages as _MM
        cm = _MM.M_PRINT_DIALOG_COLOUR_MATCHING
        kept = kept + "\n\n" + cm.render()[1]
        return "\n\n".join([paras[0], kept, paras[3], paras[4]])

    def _show_paper_not_listed(self, title: str, body: str) -> None:
        """M-PRINT-PS-PAPER-NOT-LISTED, its headline IN the box (combined
        review of beta 2: shown with ``QMessageBox.warning`` the approved
        headline went only to the window frame, which macOS does not draw, so
        the user saw the body alone). The pattern of the other §M windows of
        this tab (``_ask_unknown_paper_profile``)."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        set_warning_icon(box)
        box.setText(title)
        box.setInformativeText(body)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _set_native_mode(self, enabled: bool) -> None:
        import sys as _sys
        self._update_verify_route_note(native=enabled)
        self._update_ps_form_row()
        self._printer_grp.setVisible(not enabled)
        self._opts_grp.setVisible(not enabled)
        # The spacer used to centre the warning label between the scroll area
        # and the buttons. With the warning inside the scroll area (Basti,
        # 2026-08-09) the spacer only fought the scroll for height — half the
        # panel went to pure emptiness while the warning was pushed out of
        # the viewport, invisible behind macOS's overlay scrollbar.
        self._native_warn_spacer.setVisible(False)
        if enabled:
            if _sys.platform == "win32":
                self._warn_lbl.setText(
                    tr("⚠  You are printing via the Windows printer dialog. You must disable "
                    "colour management in your printer driver before printing — otherwise "
                    "the printer applies its own corrections and the chart will be unusable "
                    "for accurate ICC profiling.\n\n"
                    "How to disable colour management: after clicking Print, open the "
                    "printer's Properties / Preferences and look for a colour-management "
                    "section:\n"
                    "  • Epson:  \"Epson Color Controls\" → Off (No Color Adjustment)\n"
                    "  • Canon:  \"Color Options\" → Manual → None\n"
                    "  • HP:     \"Color Options\" → Application Managed Colors\n"
                    "  • Others: look for \"No Color Management\", \"Off\", or "
                    "\"Application Controlled\"\n\n"
                    "Allow pigment inks to dry fully before measuring "
                    "(at least 1 h; 24 h for best accuracy).")
                    + "\n\n" + tr(_WIN_DIALOG_NOTICE_EXTRA)
                )
            else:
                self._warn_lbl.setText(self._macos_dialog_notice())
        elif is_windows():
            self._warn_lbl.setText(tr(_WIN_DIRECT_NOTICE))
        else:
            if is_macos() and bool(self._settings.get("pdf_print_fallback", True)):
                fallback_sentence = tr(
                    "If CUPS rejects PostScript (most non-PostScript printers), it "
                    "automatically retries with an exact-size PDF that keeps the chart "
                    "at 100% scale (edges beyond the printable area are clipped, "
                    "never shrunk)."
                )
            else:
                fallback_sentence = tr(
                    "If CUPS rejects PostScript (e.g. AirPrint or Driverless drivers), "
                    "it automatically retries by sending the TIFF directly with "
                    "colour-space-aware raster options."
                )
            # The sibling branch above has gone through tr() since it was
            # written; this one never did, because the trailing
            # `+ fallback_sentence` makes the whole argument an expression and
            # `i18n_extract.unwrapped_literals` only ever looked at a bare
            # literal. Measured 2026-09-16: these were the only three sentences
            # in the app hidden that way. The concatenation is now a
            # placeholder, so the sentence a translator sees is the whole one.
            if is_macos():
                # Beta 15 (approved by Sebastian, 2026-10-08).
                self._warn_lbl.setText(tr(
                    "⚠  Verify that all print settings above match the media you are "
                    "printing on.\n\n"
                    "Wrong media type or quality settings will cause incorrect ink laydown "
                    "and invalid colour measurements. Allow pigment inks to dry fully "
                    "before measuring (at least 1 h; 24 h for best accuracy).\n\n"
                    "On a Canon or Epson the chart goes as Photoshop sends an image it has "
                    "colour-managed, with the paper profile attached so macOS leaves it "
                    "unchanged; other printers get it with colour management switched "
                    "off. {fallback}"
                ).format(fallback=fallback_sentence))
                return
            self._warn_lbl.setText(tr(
                "⚠  Verify that all print settings above match the media you are printing on.\n\n"
                "Wrong media type or quality settings will cause incorrect ink laydown and "
                "invalid colour measurements. Allow pigment inks to dry fully before measuring "
                "(at least 1 h; 24 h for best accuracy).\n\n"
                "Colour management is disabled automatically. ChromIQ converts the chart to "
                "PostScript and sends it via lp, bypassing ColorSync entirely. {fallback}"
            ).format(fallback=fallback_sentence))

    def _print_native(self, pages: list[tuple[Path, int]],
                      printer: str | None = None) -> None:
        """Print through the OS print dialog.  *printer*: a queue to preselect
        (the direct route hands a job over when it does not know the model's
        paper profiles)."""
        import sys as _sys
        if _sys.platform == "darwin":
            submitted = False
            cmyk_printer = None
            try:
                from workflow.native_print_macos import (ChartIsNotRGB,
                                                          ChartOverPaper,
                                                          PaperNotOnPrinter,
                                                          print_frames)
                from workflow import measurement_messages as _MM
                try:
                    # 4.3.5 beta 2: a PostScript printer gets the chart in the
                    # form chosen for the run; a run with none yet is asked
                    # AFTER the dialog, once the printer is known (Basti,
                    # 2026-10-13); a paper its PPD does not list is refused
                    # (M-PRINT-PS-PAPER-NOT-LISTED)
                    submitted = bool(print_frames(
                        pages, printer=printer,
                        postscript_form=self._ps_form_for_dialog(),
                        refuse_unlisted_paper=True,
                        ask_postscript_form=(self._ask_ps_form
                                             if self._ps_form_can_be_asked() else None)))
                    if submitted:
                        from workflow import native_print_macos as _npm
                        from workflow import verification_print as _vp
                        if _npm.last_overhang is not None:
                            self._note_overhang(_npm.last_overhang)
                        sub = _npm.last_submission
                        # P16: the record names the QUEUE; the dialog knows
                        # only the name macOS shows (review of fix/4.3.8, D5)
                        _shown = getattr(sub, "printer_display", None) if sub is not None else None
                        self._note_print_path(
                            _vp.PATH_DIALOG,
                            (getattr(sub, "queue", None)
                             or (_npm._queue_name(_shown) if _shown else None)
                             or printer or "") if sub is not None else (printer or ""),
                            (getattr(sub, "postscript_form", None) or "") if sub is not None else "")
                        if sub is not None:
                            # R3-1 (Basti, 2026-10-20): after the P18 window's
                            # "Use the print dialog" the user chose to let the
                            # printer adjust the colours, so M-PRINT-JOB-UNTAGGED
                            # is not shown for this print
                            if getattr(self, "_ps_form_this_print", None):
                                self._start_read_back(_DialogReadBack(sub),
                                                      printer_adjusts_by_choice=True)
                            else:
                                self._start_read_back(_DialogReadBack(sub))
                            if sub.cmyk_raster:
                                cmyk_printer = sub.printer_display or ""
                except ChartOverPaper as exc:
                    log.error("Native macOS print refused: %s", exc)
                    self._show_print_refusal(*self._overhang_text(
                        exc.plan, pages[0][0], exc.paper_pt, anyway=False))
                except PaperNotOnPrinter as exc:
                    log.error("Native macOS print refused: %s", exc)
                    self._show_paper_not_listed(*_MM.M_PRINT_PS_PAPER_NOT_LISTED.render(
                        size=exc.size_mm, printer=exc.printer or ""))
                except ChartIsNotRGB as exc:
                    # R26-F8: this route can only carry RGB, and it used to
                    # convert anything else on the way in without saying so.
                    # Nothing was sent, so the print record must not say one
                    # was.
                    log.error("Native macOS print refused a %s chart", exc)
                    message_box(
                        QMessageBox.Icon.Critical, self, tr("This chart cannot go through the macOS print dialog"),
                        tr("This chart's pixels are {mode}, and the macOS print "
                           "dialog can only carry RGB. Sending it this way would "
                           "change every patch's value on the way to the printer, "
                           "so the printed sheet would no longer match the chart "
                           "file and the measurement taken from it would describe "
                           "colours that were never printed.\n\n"
                           "Turn off \u201cUse default macOS printer dialog\u201d in "
                           "Preferences and print again. The standard route sends "
                           "the chart to the printer through lp, with its own "
                           "numbers unchanged.").format(
                               mode=str(exc)),
                    )
            except Exception as exc:
                log.error("Native macOS print failed: %s", exc)
                message_box(
                    QMessageBox.Icon.Critical, self, tr("Print Failed"),
                    tr("Could not open the macOS print dialog:\n{exc}").format(exc=exc),
                )
            self._commit_print_record(submitted)
            if cmyk_printer is not None:
                self._tell_cmyk_raster_once(cmyk_printer)
            return
        self._print_native_qt(pages, printer=printer)

    @staticmethod
    def _log_printer_margins(qprinter, pw_pt: float, ph_pt: float) -> None:
        """Write the printer's OWN unprintable margins for the paper chosen in
        the dialog into the log, beside the paper size.

        jctay, forum 149836 (Canon SELPHY CP1500, Windows): the ruler helper
        markers were in the TIFF and missing on the print, and the text at the
        bottom was cut, while the log said only "100.2 x 147.8 mm paper" and
        "only empty margin is outside it". The chart is placed on the whole
        sheet (`setFullPage`), so whatever the driver cannot print near the
        edges is clipped without a word, and nothing on record said how much
        that was. Only a log line: nothing about the print changes."""
        try:
            from PyQt6.QtGui import QPageLayout
            lay = qprinter.pageLayout()
            m = lay.minimumMargins()
            per = {QPageLayout.Unit.Millimeter: 1.0,
                   QPageLayout.Unit.Point: 25.4 / 72.0,
                   QPageLayout.Unit.Inch: 25.4,
                   QPageLayout.Unit.Pica: 25.4 / 6.0,
                   QPageLayout.Unit.Didot: 0.376,
                   QPageLayout.Unit.Cicero: 4.512}.get(lay.units(), 25.4 / 72.0)
            log.info("Native print: %s, paper %.1f x %.1f mm; the printer "
                     "cannot print within L %.1f / T %.1f / R %.1f / B %.1f mm "
                     "of the paper's edges (driver's minimum margins); the "
                     "chart is placed on the whole sheet",
                     qprinter.printerName() or "?",
                     pw_pt * 25.4 / 72.0, ph_pt * 25.4 / 72.0,
                     m.left() * per, m.top() * per, m.right() * per,
                     m.bottom() * per)
        except Exception:      # noqa: BLE001 - a log line, never a blocker
            log.debug("could not read the printer's margins", exc_info=True)

    def _print_native_qt(self, pages: list[tuple[Path, int]],
                         printer: "str | None" = None) -> None:
        """The Windows print dialog route (Qt's QPrintDialog, GDI).

        Since 4.3.8 (#205) the chart is placed on the paper at EXACTLY 100 %,
        centred, turned a quarter when only that fits, as ChromIQ's
        PostScript places it. Until then it was scaled to fill the printable
        area (``KeepAspectRatio`` into the painter's viewport): an A4 chart on
        A4 came out at the printable area's size, and a small chart was
        enlarged to the page, so no patch was where the instrument expected
        it. A chart larger than the paper chosen in the dialog is not shrunk:
        nothing is printed (M-PRINT-WIN-DIALOG-TOO-BIG). And a chart that is
        not RGB is refused before the dialog (M-PRINT-WIN-DIALOG-NOT-RGB):
        GDI carries RGB only, and it used to be converted without a word.
        *printer*: the queue the dialog opens on (ChromIQ's own route hands
        over an RGB chart for a printer that is not PostScript)."""
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QImage, QPageLayout, QPainter
        from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
        from PyQt6.QtWidgets import QDialog
        from workflow import measurement_messages as MM

        inks = self._non_rgb_inks(pages)
        if inks is not None:
            log.error("Windows print dialog refused a %s chart "
                      "(M-PRINT-WIN-DIALOG-NOT-RGB)", inks)
            self._show_print_refusal(*MM.M_PRINT_WIN_DIALOG_NOT_RGB.render(inks=inks))
            self._commit_print_record(False)
            return

        sizes: list[tuple[float, float]] = []
        for tiff_path, _frame in pages:
            try:
                sizes.append(read_tiff_dimensions_points(tiff_path))
            except Exception as exc:  # noqa: BLE001 - said below, per page
                log.warning("Native print: no size for %s: %s", tiff_path.name, exc)
                sizes.append((0.0, 0.0))

        qprinter = QPrinter(QPrinter.PrinterMode.HighResolution)
        if printer:
            qprinter.setPrinterName(printer)
        # the chart's own size on the paper: no margins, the paper's corner
        # is the painter's origin
        qprinter.setFullPage(True)
        if sizes and sizes[0][0] > sizes[0][1]:
            qprinter.setPageOrientation(QPageLayout.Orientation.Landscape)
        dialog = QPrintDialog(qprinter, self)
        # Windows' print dialog raises and handles COM exceptions of its own,
        # which faulthandler writes into chromiq-crash.log as "Windows fatal
        # exception" (core/crash_log.py). Paused for this one call only.
        from core.crash_log import quiet_for_native_dialog
        with quiet_for_native_dialog():
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if not accepted:
            # Cancelled at the OS dialog: nothing was printed, so no record.
            self._commit_print_record(False)
            return

        # #205: Windows 11's own print dialog (the one Windows shows for a
        # dialog with a parent window since 24H2) opens on the WINDOWS DEFAULT
        # printer and ignores the one ChromIQ preselects (measured: report
        # folder 03, probe_preselect_*.json; the classic dialog honours it).
        # With "Let Windows manage my default printer" on, the default is the
        # printer used last, from any app. When ChromIQ's own route handed THIS printer over and the dialog
        # came back with another one, nothing is printed without asking.
        chosen = qprinter.printerName()
        if printer and chosen and chosen != printer \
                and not self._confirm_other_printer(printer, chosen):
            self._commit_print_record(False)
            return

        paper = qprinter.pageLayout().fullRectPoints()
        pw, ph = float(paper.width()), float(paper.height())
        self._log_printer_margins(qprinter, pw, ph)
        # A CHART A LITTLE LARGER THAN THE PAPER (jctay 149803: 102 x 152 mm
        # on the 100 x 148 mm a 4 x 6 in printer takes): printed at exactly
        # 100 %, no question, when only empty margin is off the paper
        # (workflow.overhang), moved so that margin takes the cut. When more
        # would be lost, nothing is printed (M-PRINT-CHART-CUT). Much larger
        # than the paper keeps M-PRINT-WIN-DIALOG-TOO-BIG.
        over = self._overhang_plan(pages, (pw, ph))
        shift_pt = (0.0, 0.0)
        if over is not None and over.safe:
            shift_pt = over.shift_pt()
            self._note_overhang(over)
        elif over is not None and over.reason != "too_much":
            log.error("Windows print dialog: %s would be cut on %.0f x %.0f pt "
                      "paper (%s); nothing printed", pages[0][0].name, pw, ph,
                      over.reason)
            self._show_print_refusal(*self._overhang_text(
                over, pages[0][0], (pw, ph), anyway=False))
            self._commit_print_record(False)
            return
        turns: list[bool] = []
        for (w, h), (tiff_path, _frame) in zip(sizes, pages):
            fits = w <= pw * 1.02 and h <= ph * 1.02
            fits_turned = h <= pw * 1.02 and w <= ph * 1.02
            if over is not None and over.safe:
                # placed as planned: the paper lies the chart's way round
                fits = (w > h) == (pw > ph) or abs(pw - ph) < 0.5
                fits_turned = not fits
            if w and h and not fits and not fits_turned:
                def _mm(a: float, b: float) -> str:
                    return f"{a * 25.4 / 72:.0f} × {b * 25.4 / 72:.0f} mm"
                log.error("Windows print dialog: %s is %.0f x %.0f pt, larger than "
                          "the paper %.0f x %.0f pt; nothing printed",
                          tiff_path.name, w, h, pw, ph)
                self._show_print_refusal(*MM.M_PRINT_WIN_DIALOG_TOO_BIG.render(
                    chart=_mm(w, h), paper=_mm(pw, ph)))
                self._commit_print_record(False)
                return
            turns.append(bool(w and h and not fits))

        painter = QPainter(qprinter)
        if not painter.isActive():
            log.error("Windows print dialog: the printer did not start the job")
            self._commit_print_record(False)
            return
        res = float(qprinter.resolution())
        page_px = qprinter.pageLayout().fullRectPixels(int(res))
        drawn = 0
        for i, ((tiff_path, frame), (w, h), turn) in enumerate(zip(pages, sizes, turns)):
            if i > 0:
                qprinter.newPage()
            try:
                img = Image.open(tiff_path)
                n_frames = getattr(img, "n_frames", 1)
                img.seek(min(frame, n_frames - 1))
                display_img = img.convert("RGB")
                import io as _io
                buf = _io.BytesIO()
                display_img.save(buf, format="PNG")
                buf.seek(0)
                qimg = QImage()
                qimg.loadFromData(buf.read())
                if qimg.isNull():
                    log.warning("Native print: QImage is null for %s frame %d", tiff_path.name, frame)
                    continue
                if not (w and h):
                    log.warning("Native print: %s has no size; not printed", tiff_path.name)
                    continue
                cw, ch = w / 72.0 * res, h / 72.0 * res      # device pixels
                dw, dh = (ch, cw) if turn else (cw, ch)       # as it lies on the paper
                x0 = (page_px.width() - dw) / 2.0
                y0 = (page_px.height() - dh) / 2.0
                # off centre only as the plan says, in the chart's own
                # orientation; turned a quarter clockwise, its right runs
                # down the page and its "down" to the left
                sx, sy = shift_pt[0] / 72.0 * res, shift_pt[1] / 72.0 * res
                if turn:
                    x0 -= sy
                    y0 += sx
                else:
                    x0 += sx
                    y0 += sy
                painter.save()
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
                if turn:
                    painter.translate(x0 + dw, y0)
                    painter.rotate(90)
                    painter.drawImage(QRectF(0.0, 0.0, cw, ch), qimg)
                else:
                    painter.drawImage(QRectF(x0, y0, cw, ch), qimg)
                painter.restore()
                log.info("Native print: %s frame %d at 100%% (%.1f x %.1f mm)%s on "
                         "%.1f x %.1f mm paper", tiff_path.name, frame,
                         w * 25.4 / 72, h * 25.4 / 72, ", turned" if turn else "",
                         pw * 25.4 / 72, ph * 25.4 / 72)
                drawn += 1
            except Exception as exc:
                log.warning("Native print: cannot render %s frame %d: %s", tiff_path.name, frame, exc)
        painter.end()
        # A record only if a page really went onto the QPrinter: every page
        # failing to render leaves an empty job and nothing to describe.
        self._commit_print_record(drawn > 0)
