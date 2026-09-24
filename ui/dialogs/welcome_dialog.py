"""Welcome dialog — opens on first launch and via the masthead "?" button.

Two-page QStackedWidget:
  • Page 0 — six clickable WorkflowCard tiles arranged 3x2
  • Page 1 — numbered step instructions for the selected workflow

Theme-aware via set_appearance(mode); persists the "show on startup" choice
through AppSettings.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetrics, QFontMetricsF, QPainter, QPainterPath,
    QPaintEvent, QPen, QPolygonF,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.fade_scroll import FadeScrollArea
from ui.styles import SPEC_MAGENTA, TAB_COLORS
from ui.theme import APPEARANCE_NEUTRAL, accent_for
from core.i18n import tr
from core.platform_paths import file_manager_name
from ui.keyboard_help import keys_for
from core.logger import get_logger
from ui.warning_sign import warn

log = get_logger(__name__)

if TYPE_CHECKING:
    from core.settings import AppSettings


# ---------------------------------------------------------------------------
# Workflow content
# ---------------------------------------------------------------------------

# Each step is one of
#     (tab_index_1based, text)
#     (tab_index_1based, text, optional_bool)
#     (tab_index_1based, text, optional_bool, notes)
# tab_index drives the coloured badge. The displayed number inside the badge is
# the step count, not the tab number — the colour already tells you which tab.
# optional=True renders the badge outlined (rather than filled) and dims the
# text slightly, marking steps that improve quality but aren't required.
#
# `notes` IS THE SECOND REGISTER, AND IT IS WHY IT EXISTS.
#
# Knut, 2026-09-06: *"A user should be guided with simple steps, and given the
# more detailed explanations as notes for a deeper understanding, if the user
# decides to want that."*
#
# Until this existed a card had exactly ONE register — a numbered step — so
# every explanation had to be written as an instruction. That is how
# "printer_from_scan" came to carry a 200-word step that sets three controls
# and a 130-word step opening "Why it matters, in one sentence", both numbered,
# both compulsory reading, on a sheet the user may be holding at the printer.
#
# `notes` is a sequence of (heading, body) pairs. On screen each one is a
# CLOSED disclosure under its step: the heading is a small ▶ line the reader
# can open if they want the reasoning, and the card reads as a short list of
# actions until they do. On paper there is nothing to click, so every note
# prints, indented and in smaller grey type under its step.
#
# THE SPLIT IS THE POINT, not the widget. A step is an action the reader
# performs: "pick the second usage scenario". A note is why that action is
# right, what it sets, and what happens if it is skipped. If a sentence cannot
# be carried out, it is not a step.
WORKFLOWS: list[dict] = [
    {
        "key": "first_profile",
        "title": tr("Build my first ICC profile"),
        "subtitle": tr("The full walk-through from blank chart to finished profile."),
        "steps": [
            (1, tr("On the Create Chart tab, pick the instrument you will "
                "measure with (an i1Pro, say) and your paper size, set the "
                "number of pages, type a name for the chart, and click "
                "“Generate Chart”."),
             False,
             ((tr("How many pages to ask for"),
               tr("More pages means more patches, and more patches means a "
                  "more accurate profile. Two or three A4 pages is a sensible "
                  "start: with an i1Pro that is roughly 1000 to 1500 patches. "
                  "Raise it for critical work, drop it back while you are "
                  "still experimenting. The page count is the only size "
                  "control you need here; ChromIQ fills each page as densely "
                  "as your instrument allows.")),
              (tr("The name travels with every file"),
               tr("Whatever you type here becomes the stem of the chart, the "
                  "measurement and the finished profile, so it is the name "
                  "you will read in {manager} and in every colour-managed "
                  "program months from now. Printer, paper and date works "
                  "well: “EpsonP900_HahnemuhlePhotoRag_2026-05”. Avoid spaces "
                  "and punctuation. ChromIQ also writes a .ti2 beside the "
                  "chart TIFF, which records exactly where every patch sits "
                  "on the page.").format(manager=file_manager_name())),
              (tr("Two boxes worth filling in while you are here"),
               tr("Both are optional and both start empty. “Run 1 "
                  "Description” is your own note about what this attempt is, "
                  "such as “PhotoRag Baryta, gloss, large chart”. It follows "
                  "the run, so you can tell run 1 from run 2 later, and "
                  "ChromIQ offers it again at the end of the profile's "
                  "description in step 4. “Run 1 Chart Notes” is printed ON "
                  "the sheet, which is what lets you tell two printed charts "
                  "apart on the desk.")))),
            (2, tr("Move to the Print Chart tab, choose your printer and "
                "media, check that the driver's colour management is OFF, "
                "and click “Print”."),
             False,
             ((tr("Why colour management has to be off"),
               tr("The whole point of the chart is to find out what your "
                  "printer does with a known set of numbers. If the driver "
                  "re-maps those numbers on the way to the paper, you are "
                  "measuring the driver instead of the printer, and the "
                  "profile you build describes something that does not "
                  "exist. Nothing downstream can detect this, which is why it "
                  "is worth one look in the print dialog.")),
              (tr("Where that switch is on each system"),
               tr("On macOS ChromIQ turns it off for you; all you need do is "
                  "confirm that nothing in the print dialog has switched it "
                  "back on. On Windows and elsewhere you turn it off "
                  "yourself, in the driver's own dialog. The wording varies: "
                  "look for “No colour adjustment”, “Application manages "
                  "colours” or “ICM off”.")))),
            (3, tr("On the Measure tab, connect and switch on your "
                "spectrophotometer, lay the printed chart on a white "
                "surface, then click “Start Measurement” and follow the "
                "strip-by-strip prompts."),
             False,
             ((tr("Why the backing has to be white"),
               tr("Thin stock lets whatever is under it bleed through into "
                  "the reading. A plain sheet of paper underneath works "
                  "perfectly; a coloured desk mat or a dark table skews every "
                  "patch on the page, and the profile inherits the skew.")),
              (tr("Leave “Strip recognition” on Auto"),
               tr("With its “Auto” box ticked, ChromIQ picks the mode that "
                  "suits the instrument saved in your chart. Changing it by "
                  "hand is an expert setting: the wrong choice on a "
                  "fixed-order chart can latch onto the wrong strip and "
                  "quietly build a profile with colour casts. Nothing warns "
                  "you afterwards, because every patch was read "
                  "successfully; they were simply the wrong patches.")))),
            (4, tr("On the Build Profile tab the new .ti3 measurement is "
                "already loaded. Click “Build Profile”."),
             False,
             ((tr("The three metadata boxes, and whether to fill them in"),
               tr("Description, Manufacturer and Copyright are embedded in "
                  "the .icc header, so colour-management programs can name "
                  "the profile back to you later. They change nothing about "
                  "the colour. Leave them empty if you would rather, but a "
                  "Description is the difference between picking a profile "
                  "from a list of names and picking one from a list of "
                  "filenames.")),
              (tr("What the result popup offers"),
               tr("When the build finishes a popup appears with the next "
                  "moves: install the .icc into your system colour folder, "
                  "or jump to Check & Refine to measure how accurate it "
                  "actually is and start the guided refinement below. You can "
                  "dismiss the popup and reach either of them later.")))),
            (5, tr("Optional — On the Check & Refine tab click “{analyse}”. "
                "ChromIQ runs profcheck and flags any patches whose ΔE is "
                "above your refinement threshold (2.0 is a sensible starting "
                "point). If outliers are found, ChromIQ offers to send you "
                "back to the Measure tab to re-read only the affected strips.").format(analyse=tr('Analyse Profile Quality')),
                True),
            (3, tr("Optional — Re-measure the strips ChromIQ marks. The new "
                "readings are merged into the .ti3; patches that were already "
                "good are kept as they are."),
                True),
            (4, tr("Optional — Click “Build Profile” again. The refined .ti3 "
                "produces a more accurate profile."),
                True),
            (5, tr("Optional — Run “{analyse}” one more time to confirm the "
                "worst outliers are now below threshold. Repeat the refine "
                "loop as often as you like — each pass should reduce ΔE "
                "further.").format(analyse=tr('Analyse Profile Quality')),
                True),
        ],
    },
    {
        "key": "two_pass",
        "title": tr("Build a high-quality profile (2-pass)"),
        "subtitle": tr("A pre-conditioning pass produces a sharper second profile."),
        "steps": [
            (1, tr("On the Create Chart tab, start a fresh chart with a LOW "
                "page count. One A4 page is plenty. Name it with a “_pre” "
                "suffix so you can tell it apart later, then click “Generate "
                "Chart”."),
             False,
             ((tr("Why the first chart is deliberately small"),
               tr("The profile this pass produces is throwaway. Its only job "
                  "is to tell ChromIQ where your printer is most non-linear, "
                  "so that the second chart can place its patches where they "
                  "are actually worth measuring. Save your paper, your ink "
                  "and your reading time for that second pass, where they buy "
                  "you something.")),)),
            (2, tr("Print it from the Print Chart tab with the driver's "
                "colour management OFF, then measure it on the Measure tab "
                "exactly as you would any chart."),
             False,
             ((tr("The same two rules as any chart"),
               tr("Driver colour management OFF, because a driver that "
                  "re-maps the patches makes you measure the driver instead "
                  "of the printer. And the printed sheet on a white backing, "
                  "because thin stock lets a coloured desk bleed into every "
                  "reading. On macOS ChromIQ switches the colour management "
                  "off for you; elsewhere you do it in the driver's own "
                  "dialog.")),)),
            (4, tr("On the Build Profile tab click “Build Profile”, then in "
                "the result popup (or in Check & Refine) click “← Use as "
                "Pre-conditioning”. ChromIQ jumps back to the Create Chart "
                "tab with this .icc loaded as the pre-conditioning profile."),
             False,
             ((tr("Treat this profile as a map, not as a result"),
               tr("It is a rough description of your printer's colour space, "
                  "and it is good enough for exactly one purpose: telling "
                  "targen where the printer behaves awkwardly. Do not install "
                  "it. The profile you install is the one the second pass "
                  "produces.")),)),
            (1, tr("Raise the patch count for the second chart, then click "
                "“Generate Chart” again."),
             False,
             ((tr("Why more patches pay off this time and not last time"),
               tr("With a pre-conditioning profile loaded, targen no longer "
                  "spreads patches evenly through a colour space it knows "
                  "nothing about. It puts them where your printer's response "
                  "bends, which is where a profile built from too few "
                  "measurements goes wrong. Extra patches now buy accuracy; "
                  "extra patches in pass one would only have bought "
                  "time.")),)),
            (2, tr("Print the new chart from the Print Chart tab, colour "
                "management OFF, and measure it on the Measure tab.")),
            (4, tr("Click “Build Profile” one more time. This is the profile "
                "to install."),
             False,
             ((tr("What the second pass actually bought you"),
               tr("The same instrument and the same paper, but the "
                  "measurements now cover the parts of the colour space the "
                  "first profile was weakest in. The result is noticeably "
                  "more accurate than the first-pass profile, and it is the "
                  "one the result popup offers to install.")),)),
            (5, tr("Optional — On the Check & Refine tab click “{analyse}”. "
                "ChromIQ runs profcheck and flags any patches whose ΔE is "
                "above your refinement threshold. After a clean 2-pass build "
                "the result is often already good enough; the steps below "
                "are for squeezing out the last few outliers.").format(analyse=tr('Analyse Profile Quality')),
                True),
            (3, tr("Optional — Re-measure the strips ChromIQ marks. The new "
                "readings are merged into the .ti3; patches that were already "
                "good are kept as they are."),
                True),
            (4, tr("Optional — Click “Build Profile” again. The refined .ti3 "
                "produces a more accurate profile."),
                True),
            (5, tr("Optional — Run “{analyse}” one more time to confirm the "
                "worst outliers are now below threshold. Repeat the refine "
                "loop as often as you like — each pass should reduce ΔE "
                "further.").format(analyse=tr('Analyse Profile Quality')),
                True),
        ],
    },
    {
        "key": "improve_existing_profile",
        "title": tr("Improve an existing ICC profile"),
        "subtitle": tr("Seed ChromIQ with a current profile to build a sharper one."),
        "steps": [
            (1, tr("On the Create Chart tab, open the “Refinement "
                "(Optional)” section, tick “Refinement profile”, click "
                "“Select pre-conditioning profile” and pick the existing "
                ".icc for this printer and paper."),
             False,
             ((tr("What the seed profile changes"),
               tr("Without it, targen spreads patches evenly through a "
                  "colour space it knows nothing about. With it, ChromIQ "
                  "already knows where your printer's response bends and "
                  "puts the patches there. That is why this workflow gets a "
                  "better profile from the same amount of paper than "
                  "starting again from scratch would.")),)),
            (1, tr("Set the instrument and paper size as usual, RAISE the "
                "patch count, give the chart a name with a “_v2” suffix, and "
                "click “Generate Chart”."),
             False,
             ((tr("Why the count goes up here"),
               tr("The seed profile has told ChromIQ which regions are "
                  "tricky, so extra patches land in those regions rather "
                  "than being spread thin over colours your printer already "
                  "handles well. A name such as "
                  "“EpsonP900_HahnemuhlePhotoRag_v2_2026-05” keeps the new "
                  "profile visibly apart from the one it improves on, in "
                  "{manager} and in every program that lists profiles by "
                  "name.").format(manager=file_manager_name())),)),
            (2, tr("Print the chart from the Print Chart tab with the "
                "driver's colour management OFF, then measure it on the "
                "Measure tab as usual."),
             False,
             ((tr("The two rules that decide whether this is worth doing"),
               tr("Driver colour management OFF, or you measure the driver "
                  "instead of the printer and the refined profile is wrong "
                  "in a way nothing later can see. And the sheet on a white "
                  "backing, because thin stock lets a coloured surface bleed "
                  "into every reading.")),)),
            (4, tr("On the Build Profile tab the new .ti3 is already loaded. "
                "Click “Build Profile”, then install the new .icc from the "
                "result popup or check it first on the Check & Refine tab."),
             False,
             ((tr("Why the new profile beats the seed"),
               tr("It is built from measurements taken where the printer is "
                  "hardest to model, rather than from measurements spread "
                  "evenly over easy and hard colours alike. The optional "
                  "metadata boxes (Description, Manufacturer, Copyright) are "
                  "embedded in the .icc header so a colour-managed program "
                  "can name it back to you; they change nothing about the "
                  "colour.")),)),
            (5, tr("Optional — On the Check & Refine tab click “{analyse}”. "
                "ChromIQ runs profcheck and flags any patches whose ΔE is "
                "above your refinement threshold (2.0 is a sensible starting "
                "point). If outliers are found, ChromIQ offers to send you "
                "back to the Measure tab to re-read only the affected strips.").format(analyse=tr('Analyse Profile Quality')),
                True),
            (3, tr("Optional — Re-measure the strips ChromIQ marks. The new "
                "readings are merged into the .ti3; patches that were already "
                "good are kept as they are."),
                True),
            (4, tr("Optional — Click “Build Profile” again. The refined .ti3 "
                "produces a more accurate profile."),
                True),
            (5, tr("Optional — Run “{analyse}” one more time to confirm the "
                "worst outliers are now below threshold. Repeat the refine "
                "loop as often as you like — each pass should reduce ΔE "
                "further.").format(analyse=tr('Analyse Profile Quality')),
                True),
        ],
    },
    {
        "key": "print_chart",
        "title": tr("Print an existing test chart"),
        "subtitle": tr("You already have a chart on disk and just want to print it."),
        "steps": [
            (2, tr("Click “Open Chart File (.ti2)” at the top left of the "
                "window and pick the chart definition file. The chart appears "
                "on the Print Chart tab."),
             False,
             ((tr("You do not pick the TIFF pages yourself"),
               tr("The .ti2 records which patch sits where, and ChromIQ finds "
                  "the matching TIFF pages beside it automatically. If the "
                  "chart was made in ChromIQ, “Open Project” next to it opens "
                  "the whole project instead, and the chart comes with "
                  "it.")),)),
            (2, tr("Choose your printer, paper type and whatever quality "
                "settings the print dialog offers, and check that driver "
                "colour management is OFF."),
             False,
             ((tr("The same rule as a freshly made chart"),
               tr("A driver that re-maps colours makes the printed patches "
                  "disagree with their definition in the .ti2, and every "
                  "measurement taken from that sheet is then wrong by an "
                  "amount nothing downstream can see. On macOS ChromIQ "
                  "switches it off for you; elsewhere you do it in the "
                  "driver's own dialog.")),)),
            (2, tr("Click “Print”."),
             False,
             ((tr("How the sheet reaches the printer"),
               tr("The TIFF is sent as raw PostScript, so no driver filter "
                  "alters the patches on the way. That is the same path a "
                  "chart made in ChromIQ takes, which is what makes the two "
                  "sheets comparable.")),)),
            (3, tr("Once the print is dry, go to the Measure tab, connect "
                "your spectrophotometer, lay the chart on a white surface, "
                "click “Start Measurement” and follow the prompts."),
             False,
             ((tr("Leave “Strip recognition” on Auto"),
               tr("ChromIQ then picks the mode that suits the instrument "
                  "saved in your chart. If the chart is not randomised, "
                  "ChromIQ warns you before that choice can go wrong: on a "
                  "fixed-order chart the wrong mode can latch onto the wrong "
                  "strip and build a profile with colour casts, and every "
                  "patch will have been read successfully.")),)),
            (4, tr("On the Build Profile tab the new .ti3 is already loaded. "
                "Click “Build Profile”, then install the .icc from the "
                "result popup or check it first on the Check & Refine tab."),
             False,
             ((tr("The optional metadata boxes"),
               tr("Description, Manufacturer and Copyright are embedded in "
                  "the .icc header so colour-management programs can identify "
                  "the profile later. They change nothing about the colour, "
                  "and you can leave them empty.")),)),
            (5, tr("Optional — On the Check & Refine tab click “{analyse}”. "
                "ChromIQ runs profcheck and flags any patches whose ΔE is "
                "above your refinement threshold (2.0 is a sensible starting "
                "point). If outliers are found, ChromIQ offers to send you "
                "back to the Measure tab to re-read only the affected strips.").format(analyse=tr('Analyse Profile Quality')),
                True),
            (3, tr("Optional — Re-measure the strips ChromIQ marks. The new "
                "readings are merged into the .ti3; patches that were already "
                "good are kept as they are."),
                True),
            (4, tr("Optional — Click “Build Profile” again. The refined .ti3 "
                "produces a more accurate profile."),
                True),
            (5, tr("Optional — Run “{analyse}” one more time to confirm the "
                "worst outliers are now below threshold. Repeat the refine "
                "loop as often as you like — each pass should reduce ΔE "
                "further.").format(analyse=tr('Analyse Profile Quality')),
                True),
        ],
    },
    {
        "key": "measure_existing",
        "title": tr("Measure a chart I already printed"),
        "subtitle": tr("Jump straight to reading patches with your spectrophotometer."),
        "steps": [
            (3, tr("Click “Open Chart File (.ti2)” at the top left of the "
                "window and pick the .ti2 that matches your printed chart."),
             False,
             ((tr("Why it has to be the matching .ti2"),
               tr("The .ti2 holds the exact patch positions of the sheet in "
                  "front of you. A .ti2 from a different chart will line up "
                  "with nothing, and ChromIQ has no way of noticing. Once it "
                  "is open the chart appears on the Measure tab, and on "
                  "Create Chart and Print Chart as well.")),)),
            (3, tr("Connect and switch on the spectrophotometer, and wait for "
                "the green status pill in the toolbar."),
             False,
             ((tr("You do not have to choose the instrument"),
               tr("ChromIQ detects it by itself. The pill turning green is "
                  "the signal that the instrument has been found and is "
                  "ready; until then “Start Measurement” has nothing to talk "
                  "to.")),)),
            (3, tr("Leave the “Auto” box on the “Strip recognition” row "
                "ticked."),
             False,
             ((tr("What Auto decides, and what it costs to override it"),
               tr("ChromIQ chooses the mode that suits the instrument saved "
                  "in your chart, which is right for almost everybody. "
                  "Changing it by hand is an expert setting: the wrong choice "
                  "on a fixed-order chart can latch onto the wrong strip and "
                  "quietly build a profile with colour casts, so ChromIQ "
                  "warns you before it lets that happen.")),)),
            (3, tr("Click “Start Measurement” and follow the strip-by-strip "
                "prompts. The readings are saved as a .ti3 beside the chart."),
             False,
             ((tr("Where that leaves you"),
               tr("The .ti3 is the measurement, and it is what the Build "
                  "Profile tab turns into an .icc. It is written when the "
                  "reading ends cleanly, so let the run finish rather than "
                  "closing the window part-way through.")),)),
            (3, tr("Optional: tick “Play sounds during measurement” for "
                "audible feedback as you read."),
                True,
             ((tr("What each sound means, and where to change them"),
               tr("A tick as each patch is read, a bell when a strip is "
                  "done, a warning if a reading looks off, and a fanfare when "
                  "the whole chart is finished. It is a hands-free way to "
                  "follow progress without watching the screen. Choose the "
                  "sound for each event, or add your own, in Preferences → "
                  "Sounds.")),)),
            (4, tr("On the Build Profile tab the new .ti3 is already loaded. "
                "Click “Build Profile”, then install the .icc from the result "
                "popup or check it first on the Check & Refine tab."),
             False,
             ((tr("The optional metadata boxes"),
               tr("Description, Manufacturer and Copyright are embedded in "
                  "the .icc header so colour-management programs can identify "
                  "the profile later. They change nothing about the colour, "
                  "and you can leave them empty.")),)),
            (5, tr("Optional — On the Check & Refine tab click “{analyse}”. "
                "ChromIQ runs profcheck and flags any patches whose ΔE is "
                "above your refinement threshold (2.0 is a sensible starting "
                "point). If outliers are found, ChromIQ offers to send you "
                "back to the Measure tab to re-read only the affected strips.").format(analyse=tr('Analyse Profile Quality')),
                True),
            (3, tr("Optional — Re-measure the strips ChromIQ marks. The new "
                "readings are merged into the .ti3; patches that were already "
                "good are kept as they are."),
                True),
            (4, tr("Optional — Click “Build Profile” again. The refined .ti3 "
                "produces a more accurate profile."),
                True),
            (5, tr("Optional — Run “{analyse}” one more time to confirm the "
                "worst outliers are now below threshold. Repeat the refine "
                "loop as often as you like — each pass should reduce ΔE "
                "further.").format(analyse=tr('Analyse Profile Quality')),
                True),
        ],
    },
    {
        "key": "build_from_measurement",
        "title": tr("Build a profile from an existing measurement"),
        "subtitle": tr("You have a .ti3 file — turn it into an ICC profile."),
        "steps": [
            (4, tr("On the Build Profile tab, click the small chart icon in "
                "the top-right corner of the tab, whose tooltip reads “Load "
                "your measurement data”, and pick your .ti3."),
             False,
             ((tr("What comes along with it"),
               tr("The matching .ti1 or .ti2 is found and loaded "
                  "automatically, so you do not have to hunt for the chart "
                  "the measurement came from. Those files say which patch "
                  "was which, and colprof cannot build without them.")),)),
            (4, tr("Optional: fill in Description, Manufacturer and "
                "Copyright."),
                True,
             ((tr("What those three boxes are for"),
               tr("They are embedded in the .icc header, so colour-managed "
                  "programs can name the profile back to you later. They "
                  "change nothing about the colour, and an empty box costs "
                  "you nothing but a less recognisable entry in a long list "
                  "of profiles.")),)),
            (4, tr("Click “Build Profile”. The .icc lands next to the .ti3, "
                "in the same folder.")),
            (4, tr("Choose what to do from the result popup."),
             False,
             ((tr("The three things it offers"),
               tr("Install the profile into your system colour folder; jump "
                  "to Check & Refine to measure how accurate it actually is; "
                  "or feed it back as a pre-conditioning profile, which is "
                  "the 2-pass workflow on its own card. You can dismiss the "
                  "popup and reach any of the three later.")),)),
            (5, tr("Optional — On the Check & Refine tab click “{analyse}”. "
                "ChromIQ runs profcheck and flags any patches whose ΔE is "
                "above your refinement threshold (2.0 is a sensible starting "
                "point). If outliers are found, ChromIQ offers to send you "
                "back to the Measure tab to re-read only the affected strips.").format(analyse=tr('Analyse Profile Quality')),
                True),
            (3, tr("Optional — Re-measure the strips ChromIQ marks. The new "
                "readings are merged into the .ti3; patches that were already "
                "good are kept as they are."),
                True),
            (4, tr("Optional — Click “Build Profile” again. The refined .ti3 "
                "produces a more accurate profile."),
                True),
            (5, tr("Optional — Run “{analyse}” one more time to confirm the "
                "worst outliers are now below threshold. Repeat the refine "
                "loop as often as you like — each pass should reduce ΔE "
                "further.").format(analyse=tr('Analyse Profile Quality')),
                True),
        ],
    },
    {
        "key": "refine",
        "title": tr("Refine an existing profile"),
        "subtitle": tr("Re-measure only the strips where ΔE is worst."),
        "steps": [
            (5, tr("On the Check & Refine tab, click the folder button beside "
                "“.ti3 test data file:” and open the measurement of the "
                "profile you want to improve."),
             False,
             ((tr("The profile comes with the measurement"),
               tr("The matching .icc loads by itself, because the two share a "
                  "stem. That pairing is what makes the comparison "
                  "meaningful: profcheck asks what the profile PREDICTED for "
                  "each patch and what the instrument actually READ, and both "
                  "halves have to come from the same build.")),)),
            (5, tr("Click “{analyse}”.").format(analyse=tr('Analyse Profile Quality')),
             False,
             ((tr("What the threshold decides"),
               tr("ChromIQ runs profcheck and lists every patch whose ΔE is "
                  "above the refinement threshold in the panel. 2.0 is a "
                  "sensible starting point: below about 1 a difference is "
                  "invisible, and between 2 and 4 it is visible side by side. "
                  "Set it lower and you will be re-measuring patches that "
                  "were already good enough.")),)),
            (5, tr("Accept the offer to go back to the Measure tab when "
                "outliers are found."),
             False,
             ((tr("Why only some strips are re-read"),
               tr("ChromIQ marks just the strips carrying the outlying "
                  "patches, so you re-read a handful of rows rather than "
                  "reprinting and re-measuring the whole chart. On a large "
                  "chart that is the difference between a minute and an "
                  "afternoon.")),)),
            (3, tr("Re-measure the strips ChromIQ marks."),
             False,
             ((tr("Nothing good is thrown away"),
               tr("The new readings are merged into the existing .ti3, and "
                  "patches that were already within threshold are kept "
                  "exactly as they were. The file grows more accurate in "
                  "place rather than being replaced.")),)),
            (4, tr("Click “Build Profile” again, and repeat the cycle until "
                "the worst outliers are below threshold.")),
        ],
    },
    {
        "key": "calibrate_printer",
        "title": tr("Calibrate my printer (and how that differs from a profile)"),
        "subtitle": tr("Bring the printer itself to a known, repeatable state — "
            "an optional step BEFORE profiling, and not the same thing as a "
            "profile."),
        "steps": [
            (4, tr("Before anything else, decide whether you need a "
                "calibration at all. Most people do not."),
             False,
             ((tr("What a calibration is, and why it is not a profile"),
               tr("These two words get used as if they meant the same thing, "
                  "and they do not. A CALIBRATION changes the printer: it "
                  "measures how much ink each channel actually lays down and "
                  "works out a correction, so that from then on the printer "
                  "responds evenly, predictably, and the same way next month "
                  "as it does today. The result is a small file ending "
                  "“.cal”. A PROFILE changes nothing about the printer. It "
                  "describes what your printer does with your paper and your "
                  "inks, so that colour-managed software can convert your "
                  "images correctly. The result is a file ending “.icc”. If "
                  "it helps: calibrating is tuning the instrument, and the "
                  "profile is the music written for an instrument tuned that "
                  "way.")),
              (tr("Who this is for"),
               tr("Consumer and prosumer inkjet printers usually give better "
                  "results from a plain profiling run with no calibration "
                  "step at all. Reach for this when your printer's own "
                  "documentation asks for linearisation, when you are "
                  "following an ArgyllCMS guide that calls for it, or when "
                  "you want the printer to behave the same way over months "
                  "rather than days.")))),
            (4, tr("Switch the feature on: Preferences → “Enable calibration "
                "options”."),
             False,
             ((tr("What appears when you do"),
               tr("Until you switch it on, none of this is visible, which is "
                  "deliberate, because most people never need it. Switching "
                  "it on adds “Calibration” to the “Run type” list in the "
                  "Profile-run bar above the tabs, and adds two modules to "
                  "the Calibration & Profiling tab.")),)),
            (1, tr("In the Profile-run bar above the tabs, set “Run type” to "
                "“Calibration”."),
             False,
             ((tr("Why “Profile run” greys out"),
               tr("It changes to “Project calibration” and greys, and that is "
                  "expected rather than a fault. A calibration describes your "
                  "printer, your paper and your inks rather than one "
                  "particular profile, so a project keeps exactly one and "
                  "every profile run in it can use the same one.")),)),
            (1, tr("On the Create Chart tab, set “Single Channel Steps” (20 "
                "is a good starting point) and click “Generate Chart”."),
             False,
             ((tr("Why the automatic patch counts are greyed out"),
               tr("ChromIQ has already set the chart up as a plain ramp of "
                  "one ink channel at a time, which is what a calibration "
                  "needs. A calibration chart's size is decided by the number "
                  "of steps rather than by filling a number of pages, so the "
                  "page-filling controls switch off. More steps measure the "
                  "printer's response more finely and take longer to "
                  "read.")),)),
            (2, tr("Print it from the Print Chart tab with the driver's "
                "colour management OFF, exactly as you print any chart."),
             False,
             ((tr("The same reason as profiling"),
               tr("If the driver re-maps the colours, you are measuring the "
                  "driver instead of the printer, and a calibration built "
                  "from that corrects for something that is not your "
                  "printer.")),)),
            (3, tr("Measure it on the Measure tab, the same way you measure "
                "any chart. The readings are saved in the project's “cal” "
                "folder, beside the chart they came from."),
             False,
             # #182 beta 39 (B8-844, Knut 5794078008): a calibration has
             # reports of its own.
             ((tr("Its measurement reports"),
               tr("With “Save measurement report” ticked on the Measure tab, "
                  "a dated report of the calibration's measurement is written "
                  "into the project's “cal/reports” folder. With Run type "
                  "Calibration, Tools → “Measurement report (accuracy & "
                  "drift)” and the Measure tab's “Measurement report…” open "
                  "on that measurement. It can have every report type but "
                  "the Printing record, and you can add other projects' "
                  "calibrations to one report. The reports are named “Cal” "
                  "for one project's calibration, and “Multiple cals” or "
                  "“All cals” when calibrations of several projects are "
                  "in one.")),)),
            (4, tr("Go to the Calibration & Profiling tab and click “Create "
                "Calibration File”."),
             False,
             ((tr("What that produces, and who it belongs to"),
               tr("ChromIQ turns your readings into the “.cal” file. That "
                  "file is your calibration, and it is shared by every "
                  "profile run in this project. With Run type set to "
                  "Calibration the tab offers this one module and nothing "
                  "else, because nothing else applies yet.")),)),
            (1, tr("Put the calibration to work, in whichever of the two ways "
                "suits your equipment."),
             False,
             ((tr("If your printer or RIP can apply a calibration itself"),
               tr("Load the “.cal” file there and let it do the work. "
                  "ChromIQ then prints charts normally and the calibration is "
                  "already in effect by the time the ink reaches the "
                  "paper.")),
              (tr("If it cannot, ChromIQ can bake it into the chart"),
               tr("Switch “Run type” back to “Profiling” and, on the Create "
                  "Chart tab, you will find the calibration already filled "
                  "into two fields: “Apply Calibration File” and “Include "
                  "Calibration File”. Neither is switched on for you, because "
                  "which one you want depends on your setup. “Apply” reprints "
                  "every patch value through the calibration; “Include” only "
                  "records it in the chart file. They cannot both be used at "
                  "once.")))),
            (4, tr("Carry on and build your profile exactly as usual. The "
                "profile you get now describes a calibrated printer, which is "
                "the point of the whole exercise.")),
            (4, tr("From now on, keep the two in step. Build a fresh profile "
                "whenever you make a new calibration."),
             False,
             ((tr("Why an old profile stops being accurate"),
               tr("A profile describes the printer as it was when you "
                  "measured it. Make a NEW calibration and every profile you "
                  "built on the old one now describes a printer that no "
                  "longer behaves that way. Those profiles keep working; they "
                  "are simply no longer accurate.")),
              (tr("What ChromIQ keeps track of for you"),
               tr("Each run records which calibration it was built with. "
                  "Making a new calibration chart never deletes a calibration "
                  "you have measured: it moves into the project's “cal/old” "
                  "folder, in a folder named with the date, so you can always "
                  "go back to it. Runs made before ChromIQ started recording "
                  "this simply say it is unknown.")))),
        ],
    },
    {
        "key": "verify",
        "title": tr("Check a finished profile (verification run)"),
        "subtitle": tr("Measure a check chart and see, in real numbers, how "
            "accurate your finished profile is — and whether it stays that "
            "way over time."),
        "steps": [
            (1, tr("In the Profile-run bar at the top of the window, set "
                "“Profile run” to the run whose profile you want to check, "
                "then set “Run type” to “Verification”."),
             False,
             ((tr("A verification always checks a profile that already "
                  "exists"),
               tr("If the run has no profile yet, ChromIQ tells you to build "
                  "one first and switches the type back to Profiling. Build "
                  "it, then come back here. Everything below belongs to that "
                  "one run: its verification chart and its dated checks. The "
                  "report type and the limits a check is judged against "
                  "belong to each report you make of it.")),)),
            (1, tr("On the Create Chart tab, choose the chart this profile "
                "will be checked with, then click “Generate Chart”."),
             False,
             ((tr("“Which presets can be used for verification?” answers this "
                  "for you"),
               tr("That button appears under “Select preset:” in the Presets "
                  "frame, and only on a Verification run, because a profiling "
                  "chart is chosen on quite different grounds. It lists every "
                  "preset ChromIQ ships and every preset of your own against "
                  "the metrics a report of the type you pick, judged against "
                  "the limit set you pick, asks of a chart. The “Metrics "
                  "answered” column says how many of them each preset can "
                  "answer; click one to see exactly which, and which it "
                  "cannot and why. Double-click loads it straight into Create "
                  "Chart. Nothing is hidden and nothing is filtered out: the "
                  "window marks presets, it does not withhold them.")),
              (tr("What the ★ means, and why it does not move"),
               tr("A star marks a chart MADE for verification: one printed "
                  "page, 600 patches or fewer, and nothing withheld that a "
                  "different patch set would have supplied. Those are "
                  "properties of the chart itself, so the star does not "
                  "change when you change the two pulldowns at the top of the "
                  "window. Tick “Show only the presets made for verification” "
                  "to see just those.")),
              (tr("Three metrics only “FROM PROFILE GAMUT” can answer"),
               # K31 (Knut, #182 5801677743): the version 1 names, and the
               # grey rows' neutral aims on such a chart (option a).
               tr("“ΔE00, paper white against the reference paper”, "
                  "“Maximum ΔE00, solid colours” and “Maximum ΔH*ab, cyan, "
                  "magenta and yellow solids” all need aim colours that no "
                  "ordinary patch set carries. The “FROM PROFILE GAMUT” "
                  "module on this tab builds the chart out of colours your "
                  "profile promises it can print AND writes those aims beside "
                  "it, which is what fills those three rows. It is also the "
                  "most direct accuracy check there is. On such a chart the "
                  "two grey balance rows take the neutral aims as their grey "
                  "steps, because the profile prints a neutral grey with "
                  "slightly unequal red, green and blue.")),
              (tr("Where the chart lives, and what happens if you replace "
                  "it"),
               tr("It goes into the run's “verifications” folder and is "
                  "reused for every future check, so you compare like with "
                  "like over time. Replace it and the old chart is archived "
                  "there rather than deleted, and every check you already "
                  "measured keeps its own stored copy of the chart it was "
                  "measured with.")))),
            (2, tr("On the Print Chart tab, set the “Colour” row to “Through "
                "the profile”, and print."),
             False,
             ((tr("Why that choice is the whole meaning of the check"),
               tr("Every patch is converted by the profile you are checking, "
                  "so the sheet is the profile's own prediction made real. "
                  "Measuring it answers “how accurate is this profile?”. "
                  "Whichever setting you pick, ChromIQ does all the colour "
                  "work itself and keeps the printer's own colour management "
                  "off, exactly as for a profiling chart.")),
              (tr("When “Raw — no profile” is the right answer instead"),
               tr("It prints the chart untouched, which asks whether the "
                  "PRINTER has drifted rather than how good the profile is. "
                  "ChromIQ treats such a sheet as a drift check and shows its "
                  "numbers without grading them, because there is no profile "
                  "in the loop to be right or wrong. A chart from “FROM "
                  "PROFILE GAMUT” already has the profile applied, so ChromIQ "
                  "selects Raw for it by itself.")))),
            (3, tr("On the Measure tab, pick “New verification” in the "
                "Verification box, then measure the chart as normal."),
             False,
             ((tr("What a dated check is, and what it never touches"),
               tr("The result is saved in its own dated folder under the "
                  "run's “verifications” folder, so every check is kept as "
                  "history. It never overwrites your profiling measurement "
                  "and it never builds a profile. Pick an earlier date "
                  "instead of “New verification” to re-measure that one.")),
              (tr("Measured somewhere else? Import it"),
               tr("If the sheet was read elsewhere, for example on an i1iO "
                  "table, the IMPORT module on this tab files that "
                  "measurement in exactly the same way, so it joins the same "
                  "history.")))),
            (3, tr("Open Tools → “Measurement report (accuracy & drift)” and "
                "set “Report type:” and “Judged against:”, then click "
                "“Generate report”."),
             False,
             ((tr("What those two pulldowns decide"),
               tr("“Report type:” is which document you get: a one-page "
                  "Colour summary, a Full colour check or a Grey and tone "
                  "check. The Printing record, which sets down what was "
                  "printed and measured and grades none of it, is the report "
                  "of a profiling measurement and is not offered for a "
                  "verification. “Judged against:” is the LIMIT SET, one "
                  "column of numbers saying how far off each measurement may "
                  "be. ChromIQ ships three of its own, “ChromIQ default "
                  "(recommended)”, “ChromIQ tight” and “Quick check”, the "
                  "published values of ISO 12647-7 and ISO 12647-8 as two "
                  "read-only sets, and two Custom ISO sets you can edit. The "
                  "defaults for new reports are set in Preferences → "
                  "Reports.")),
              (tr("How to read the result words"),
               tr("Each row reads PASS when it is inside its limit and FAIL "
                  "when it is not, and N-A when your chart carries nothing "
                  "that could answer it. INFO means the number is shown for "
                  "information only and nothing was judged from it: on a "
                  "report type that judges nothing, on a raw drift check, "
                  "and on a row that needs something about the print that "
                  "was not recorded. A row the limit set puts no limit on "
                  "(“–”) is left out of the report altogether. “Overall” is the one word for a whole dated "
                  "check, and the only place COND appears. A profiling "
                  "measurement is never graded at all: it is expected to "
                  "fall outside accuracy limits, and saying so would be "
                  "noise rather than news.")),
              (tr("The limits belong to the report"),
               tr("Each report carries its own limit set and judges every "
                  "check ticked in it against the same numbers, so the dates "
                  "in one report always compare like with like. The report "
                  "ChromIQ writes after each check is that date's own report. "
                  "To see a series judged against another set, tick the dates "
                  "in the report window, choose the set and generate a report "
                  "of them: nothing already saved is changed, and a report "
                  "you update keeps its earlier version in an “old” folder "
                  "beside it. A new report starts on the set chosen in "
                  "Preferences → Reports, unless the run has a default of its "
                  "own, chosen in the report window's Edit limits….")))),
            (3, tr("Repeat a verification every few weeks or months, and read "
                "the trend."),
             False,
             ((tr("What the trend shows, and what it never mixes in"),
               tr("“Trend over time” plots colour accuracy, "
                  "paper white, darkest black and the cube corners across "
                  "every dated check of this run, or, in a report across "
                  "runs or projects, across every measurement ticked in it. "
                  "A verification report is titled and filed separately from "
                  "a profiling report, and it only ever trends verification "
                  "measurements, so a profile's checks are never mixed in "
                  "with the run that built it. You can set its title, and "
                  "those of the profiling and calibration reports, in "
                  "Preferences → Reports.")),
              (tr("Unsure which kind of check fits you?"),
               tr("The Dictionary entry “Which verification should I use? "
                  "(the three ways)” compares all three side by "
                  "side.")))),
        ],
    },
    {
        "key": "check_visualise",
        "title": tr("Visualise a profile's gamut"),
        "subtitle": tr("See in 3D what colours a printer can and can't reproduce."),
        "steps": [
            (5, tr("On the Check & Refine tab, load the .icc profile you want "
                "to inspect."),
             False,
             ((tr("A measurement is helpful but not needed"),
               tr("The gamut viewer works from the profile alone, because a "
                  "gamut is what the profile claims the device can reach. A "
                  "matching .ti3 lets the rest of the tab tell you how "
                  "accurate that claim is, which is a different "
                  "question.")),)),
            (5, tr("Open the Gamut Viewer pane, and rotate, zoom and pan the "
                "colour volume with the mouse."),
             False,
             ((tr("What you are looking at"),
               tr("ChromIQ runs iccgamut on the profile and renders the "
                  "printer's colour volume as a 3D mesh. Its shape is the "
                  "honest answer to “what can this paper and ink actually "
                  "do?”: a deep, even solid is a roomy gamut, and a flattened "
                  "or dented one shows where the printer runs out of "
                  "colour.")),)),
            (5, tr("Optional: overlay a reference gamut such as sRGB or "
                "AdobeRGB."),
                True,
             ((tr("What the overlay tells you"),
               tr("At a glance: which colours of the reference space your "
                  "printer can hit, and which it has to clip. That is the "
                  "practical version of “will this image print the way I see "
                  "it?”, and it is far easier to read here than in a table of "
                  "numbers.")),)),
            (5, tr("Poke around freely. This workflow is read-only and writes "
                "no files.")),
        ],
    },
    {
        "key": "scanner_profile",
        "title": tr("Profile my scanner or camera"),
        "subtitle": tr("Colour-profile a scanner or a camera, from a chart you "
                       "measured or a standard target you own."),
        # KNUT, 2026-09-06: *"A user should be guided with simple steps, and
        # given the more detailed explanations as notes for a deeper
        # understanding, if the user decides to want that."*
        #
        # Every step below is an action. Everything that explains, justifies or
        # measures is a note. The card used to carry both as numbered steps,
        # because until this release there was no second register: step 6 was a
        # 145-word instruction to set three controls by hand, which is what the
        # second usage scenario now does from one radio button.
        "steps": [
            (3, tr("Get a target whose true colours are known. Either print "
                "and measure a ChromIQ chart and keep its recognition files "
                "(tick “Also save scanner-profiling files for this chart” "
                "after measuring, or run Tools ▸ Create scanner or camera "
                "target on any measured chart), or use a standard target you "
                "own, such as an IT8 or an X-Rite ColorChecker, with the "
                "reference data file that came with it."),
             False,
             ((tr("Which target gives the better profile"),
               tr("A chart you printed yourself wins whenever you mainly scan "
                  "your own prints: profile from a sheet made on your printer, "
                  "on your paper, through your normal print workflow, and the "
                  "colours the profile is fitted to are the colours you "
                  "actually put on the glass. A bought target is the answer "
                  "when you have no printer to hand, when you scan other "
                  "people's prints and film, or when you are profiling a "
                  "camera. The ChromIQ route needs the chart's .cht and .cie "
                  "files, which is what the tick box above writes; without "
                  "them ChromIQ has no map of where the patches sit.")),)),
            (3, tr("Capture the target on the device you are profiling. Scan "
                "it, or photograph it for a camera, as a plain RGB TIFF with "
                "the device's own auto-correction and colour management turned "
                "OFF. Scan at 600 dpi or more; 1200 dpi is preferred."),
             False,
             ((tr("Why 300 dpi is too coarse"),
               tr("The profile is built by reading the middle of every patch "
                  "and averaging it. At 300 dpi a small patch is only a few "
                  "dozen pixels across once the edges are left out, so the "
                  "average carries the scanner's own noise into the profile. "
                  "More pixels per patch is simply a quieter measurement, and "
                  "it costs nothing but scan time.")),
              (tr("Photographing the target, for a camera profile"),
               tr("A camera profile is only valid for the light you shot "
                  "under, so light the target flatly and evenly, with no glare "
                  "or hot-spots, under the lighting you will actually use. "
                  "Shoot raw and convert with a neutral, linear setting: no "
                  "creative white balance, no tone curve, no contrast, no "
                  "sharpening. Export a plain TIFF. That is the camera version "
                  "of turning a scanner's correction off. Fill the frame "
                  "square-on so the target is flat and undistorted.")))),
            (3, tr("Open Tools ▸ Build profile with scanner or camera and "
                "answer the first question in the window, “Usage scenario: "
                "what is this profile for?”. For scans and photographs that "
                "should simply open looking right, pick “A profile for my "
                "scanner or camera, for everyday scanning”. ChromIQ fills in "
                "the profile type, the quality and the white point handling "
                "for you."),
             False,
             ((tr("What that scenario sets, and why it waits for your files"),
               tr("There is no one right answer for everyday scanning, because "
                  "the right profile type depends on how big your target is. "
                  "So ChromIQ waits until it knows the patch count and then "
                  "sets all three settings together: below about a hundred "
                  "patches “Shaper + matrix” at Medium with “Map chart white "
                  "to white”, and at a hundred or more the XYZ look-up table "
                  "at High with “Scale white to a perfect white surface "
                  "(-u -R)”. Both pairings were measured on real scans and "
                  "scored only on patches the fit never saw. Nothing is "
                  "locked: a scenario fills the settings in once, at the "
                  "moment you pick it, and every control stays yours to "
                  "change.")),
              (tr("It will not touch settings you saved yourself"),
               tr("If you have pressed “Save as Defaults” for this kind of "
                  "profile, ChromIQ shows what you saved and sets nothing, "
                  "because the profile you build next has to be the profile "
                  "you built last unless you say otherwise. A line under the "
                  "scenario list tells you when that is what is "
                  "happening.")))),
            (3, tr("Under “Create profile using:”, say where the target came "
                "from, pick the files, drag the four corners over the patch "
                "area until the green grid lines up with the real patches, and "
                "press “Build profile with scanner or camera”. ChromIQ runs "
                "scanin and colprof and writes the ICC profile next to your "
                "capture."),
             False,
             ((tr("Several pages, and several scans of each"),
               tr("A multi-page ChromIQ chart shows a Page selector: pick and "
                  "place each page's scan in turn, and all the pages go into "
                  "one profile. You can also add several scans of the same "
                  "page and have them averaged, which cancels out the random "
                  "noise every scanner adds. Each scan keeps its own corner "
                  "placement, so it does not matter if the sheet shifted a "
                  "little on the glass between scans. A bought target is "
                  "always a single sheet, even a two-area one like the Wolf "
                  "Faust IT8.")),)),
            (3, tr("Building this profile so the scanner can MEASURE with it, "
                "the way “Profile my printer with a flatbed scanner” needs? "
                "Then pick the second scenario instead, “A profile for my "
                "scanner, so it can stand in for a measuring instrument”, and "
                "save the result as a separate file with a name that says so."),
             True,
             ((tr("Why a measuring profile is a different profile"),
               tr("A profile for looking at pictures reports colour "
                  "relative to the white patch of the target you scanned. A "
                  "profile for measuring has to report the colour that is "
                  "really there. "
                  "The scenario sets Profile type “cLUT — XYZ table”, Quality "
                  "“High” and, under Advanced…, White Point Handling on "
                  "“Force Absolute Colorimetric (-ua)”, which is exactly the "
                  "flag ArgyllCMS asks for whenever an input profile is used "
                  "“as a substitute for a colorimeter”.")),
              (tr("Why it has to stay a separate file"),
               tr("Built this way the profile makes ordinary scans arrive "
                  "darker and keeps the slight tint of your target's paper: "
                  "right for measuring, wrong for photographs. And the swap "
                  "the other way is worse. A profile built for everyday "
                  "scanning quietly clips everything brighter than the "
                  "target's white board when you measure with it, and nothing "
                  "later recovers it. Two files, two names, no doubt about "
                  "which is which.")))),
        ],
    },
    {
        "key": "printer_from_scan",
        "title": tr("Profile my printer with a flatbed scanner"),
        "subtitle": tr("No spectrophotometer? A profiled scanner can measure "
                       "your chart and build the printer profile."),
        # THE ORDER IS THE POINT, and it is the window's own order too
        # (`scanin_dialog.py`: *"Scenario 2 builds the profile scenario 3
        # needs"*). Step 1 is the step people miss; its reasoning is in notes
        # so that the step itself is one sentence long and cannot be skimmed
        # past.
        "steps": [
            (3, tr("Profile your scanner first, and build that profile FOR "
                "MEASURING. Open Tools ▸ Build profile with scanner or camera "
                "and pick the second usage scenario at the top of the window, "
                "“A profile for my scanner, so it can stand in for a measuring "
                "instrument”. It sets the three settings this job needs. Then "
                "follow the “Profile my scanner or camera” card to build it."),
             False,
             ((tr("What the scenario sets, and what each part is worth"),
               tr("Profile type “cLUT — XYZ table”, which was about twice as "
                  "accurate as the default “Shaper + matrix” on a real IT8 "
                  "scan: 0.48 against 0.91 average ΔE00. Quality “High”, worth "
                  "about 30 % on its own, the biggest single gain there is. "
                  "And, under Advanced…, White Point Handling on “Force "
                  "Absolute Colorimetric (-ua)”, which tells the profile to "
                  "report the colour that is really there, measured against a "
                  "perfect white surface, instead of reporting it relative to "
                  "the white patch of the target you scanned. That is what a "
                  "measuring instrument has to do, and ArgyllCMS asks for the "
                  "same flag whenever an input profile is used “as a "
                  "substitute for a colorimeter”.")),
              (tr("Why the white point matters, in one sentence"),
               tr("Your target's white board is not as white as your paper. A "
                  "photographic IT8 measures about 84 % reflectance and most "
                  "inkjet and office paper is brighter, so a profile that "
                  "calls the target's white “white” has no room left to "
                  "describe your paper. With a “cLUT — Lab table” profile that "
                  "is fatal: your paper white and every light tint on the "
                  "sheet are measured as one and the same colour. With the "
                  "“cLUT — XYZ table” the scenario picks it is much milder, "
                  "because ChromIQ already reads your scan through the profile "
                  "absolutely. Set the flag anyway. It costs nothing, and it "
                  "makes the profile say what it is for.")))),
            (3, tr("Save that measuring profile as a separate file, with a "
                "name that says what it is for."),
             True,
             ((tr("Why it is not the profile for everyday scanning"),
               tr("Built this way it makes ordinary scans arrive darker and "
                  "keeps the slight tint of your target's paper, which is "
                  "right for measuring and wrong for photographs. It is not "
                  "the profile you want your scanning software to use day to "
                  "day, and overwriting your normal scanner profile with it "
                  "would break your scanning with no visible reason "
                  "why.")),)),
            (1, tr("On the Create Chart tab, create a chart for your printer "
                "and paper."),
             False,
             ((tr("Which chart to use"),
               tr("A ChromIQ layout-engine chart is ideal: its patch geometry "
                  "travels with the chart, so the reading grid knows exactly "
                  "where every patch sits and you have no .cht files to find. "
                  "A chart made elsewhere works too, as long as you have its "
                  ".ti2 and the .cht page files that came with it.")),)),
            (2, tr("Print the chart from the Print Chart tab as usual, with "
                "driver colour management OFF. You do NOT measure it: the "
                "scanner is going to do that.")),
            (3, tr("Scan every printed page on your profiled scanner as a "
                "plain RGB TIFF, with the scanner's auto-correction and colour "
                "management turned OFF, using the same settings you profiled "
                "it with. Scan at 600 dpi or more; 1200 dpi is preferred."),
             False,
             ((tr("The settings have to match the ones you profiled with"),
               tr("The profile describes your scanner at the settings it was "
                  "built under. Change the resolution, the bit depth or any "
                  "correction and it no longer fits, and the measurement it "
                  "produces is wrong in a way nothing downstream can "
                  "see.")),)),
            (3, tr("Open Tools ▸ Build profile with scanner or camera and pick "
                "the third usage scenario, “A profile for my printer, measured "
                "with this scanner”. Pick your measuring profile, the chart "
                "you printed (its .ti2) and each page's scan, drag the four "
                "corners so the grid lines up with the patches on every page, "
                "then press “Build printer profile”. ChromIQ reads the patches "
                "through the scanner profile and writes a printer ICC "
                "profile."),
             False,
             ((tr("What that scenario changes in the window"),
               tr("It ticks “Profile my printer from this scan” for you and "
                  "opens the rows that go with it: the scanner profile to "
                  "measure through, and, for a chart made outside ChromIQ, its "
                  ".cht page files. The chart row asks for the chart you "
                  "PRINTED rather than one you measured, and the build button "
                  "and the window's own title both change to “Build printer "
                  "profile”, so it is always visible which of the two things "
                  "you are about to make.")),
              (tr("Why a bought target cannot do this job"),
               tr("An IT8 or a ColorChecker was printed and measured by its "
                  "manufacturer, not by your printer, so there is no record of "
                  "the colour values that went in and nothing to compare a "
                  "scan against. A printer profile is built from exactly that "
                  "comparison, which is why this scenario needs a chart you "
                  "printed yourself, and its .ti2.")))),
            (3, tr("Save the diagnostic image and take any alignment warning "
                "seriously: a misplaced grid reads the wrong patches and ruins "
                "the profile."),
             True,
             ((tr("How good is a flatbed, honestly"),
               tr("A flatbed is a fine everyday instrument and it will get you "
                  "a genuinely useful printer profile with no spectrophotometer "
                  "at all. It is not a spectrophotometer, though, and it will "
                  "not match one. Judge the result on your own prints rather "
                  "than on a number.")),)),
        ],
    },
]


# ---------------------------------------------------------------------------
# Dictionary and terminology (Knut, #108) — every term, phrase and
# abbreviation the app (and printer/scanner profiling generally) throws at a
# newcomer, alphabetical, in plain language. Rendered by its own detail view
# (no numbered steps).
GLOSSARY: list[tuple[str, str]] = [
    (tr(".cht file"),
     tr("ArgyllCMS's recognition file: where every patch sits on a scanned target, so software can find them in the image.")),
    (tr(".cie file"),
     tr("The reference colours of a target — what each patch SHOULD measure — used together with a scan to build a scanner profile.")),
    (tr(".ti1 / .ti2 / .ti3 files"),
     tr("ArgyllCMS's chart pipeline: .ti1 = the designed patch set, .ti2 = the printed layout (which patch sits where), .ti3 = the measurements. colprof turns a .ti3 into a profile.")),
    (tr("Black point"),
     tr("The darkest colour a printer and paper can produce. Everything darker in an image gets squeezed up to this level.")),
    (tr("Calibration"),
     tr("Bringing a device to a fixed, repeatable state (e.g. printer ink limits or a monitor's brightness). Done BEFORE profiling — a profile describes a device, calibration sets it.")),
    (tr("Calibration run"),
     tr("The round trip that produces your printer's calibration file: make the calibration chart, print it, measure it, then create the .cal from those readings. It is not a profile run — nothing is built from it — but every profile run in the project can use its result. Choose it under “Run type” in the Profile-run bar above the tabs; a project keeps exactly one calibration, in its “cal” folder.")),
    (tr("Chart / test chart"),
     tr("A printed page of colour patches with known device values. Measuring what the printer actually made of them is the raw material of a profile. Also called a target.")),
    (tr("chartread"),
     tr("The ArgyllCMS command-line tool that reads a printed chart with a spectrophotometer. ChromIQ runs it on the Measure tab.")),
    (tr("CMYK"),
     tr("Cyan, magenta, yellow and black — printing inks. ChromIQ profiles RGB-driven printers, whose drivers convert to ink internally.")),
    (tr("Colorimeter"),
     tr("A measuring device with a few colour filters — fine for monitors, not suitable for printer profiling. Compare spectrophotometer.")),
    (tr("colprof"),
     tr("The ArgyllCMS tool that turns a measurement file (.ti3) into an ICC profile.")),
    (tr("D50"),
     tr("The standard 'daylight' illuminant of printing: warmish daylight at 5000 K. Profiles and measurements are referenced to it, and prints should be judged under it.")),
    (tr("Delta E (ΔE)"),
     tr("The distance between two colours as a single number. Below about 1 is invisible; 2–4 is visible side by side; above 6 is obvious. Used to judge profile quality.")),
    (tr("Device link"),
     tr("A special profile that converts directly from one device's colours to another's, in one step, without the usual detour through a neutral colour space.")),
    (tr("dpi / ppi"),
     tr("Dots (printer) or pixels (scanner/image) per inch. For scanning charts: 600 dpi is fine, 1200 dpi preferred; the reading software averages each patch anyway.")),
    (tr("Fiducial marks"),
     tr("Small crosses or corners printed outside a target's patch area. Scanning software uses them to locate the patch grid precisely.")),
    (tr("Gamma / TRC"),
     tr("The tone curve relating stored values to brightness. Profiles carry it per channel (the 'shaper' in shaper/matrix profiles).")),
    (tr("Gamut"),
     tr("All the colours a device can reproduce. A printer's gamut is much smaller than what a camera captures or a monitor shows — the profile manages the squeeze.")),
    (tr("Gamut volume"),
     tr("A single number for a gamut's size (in Lab space). Useful for comparing papers or printers; bigger is roomier, not automatically better.")),
    (tr("ICC profile"),
     tr("A standard file (.icc) describing how a device reproduces colour. Colour-managed programs use it to translate between device colours and real-world colours.")),
    (tr("Illuminant"),
     tr("The light a measurement or profile assumes. Printing uses D50; changing the light changes how prints look (see metamerism).")),
    (tr("Ink limit"),
     tr("The maximum ink a paper can take before problems (bleeding, pooling). RGB printer drivers handle this internally.")),
    (tr("Instrument"),
     tr("The measuring device — in ChromIQ usually a spectrophotometer (i1Pro, ColorMunki, SpectroScan) or, with the scanner workflow, a profiled flatbed scanner.")),
    (tr("Lab (CIELAB)"),
     tr("A device-independent colour space built around human vision: L* is lightness, a* red–green, b* yellow–blue. The neutral meeting ground profiles translate through.")),
    (tr("LUT profile"),
     tr("A profile built as a lookup table — flexible enough for a printer's irregular gamut. Compare matrix profile.")),
    (tr("Matrix profile"),
     tr("A compact profile type: one tone curve per channel plus a 3×3 matrix. Great for well-behaved devices (monitors, scanners); ChromIQ's recommended type for scanner profiles.")),
    (tr("Measurement modes (M0/M1/M2)"),
     tr("Standard instrument modes differing in UV content: M0 legacy, M1 includes UV (matches D50), M2 excludes UV ('UV-cut') — matters on OBA-rich papers.")),
    (tr("Metamerism"),
     tr("Two colours matching under one light but not under another. The reason prints are judged under standard light (D50).")),
    (tr("OBA (optical brighteners)"),
     tr("Additives that make paper look whiter under UV-containing light. They can shift measurements and make prints look different across lighting.")),
    (tr("Patch"),
     tr("One coloured rectangle on a test chart. More patches = more measured colours = a potentially more accurate profile.")),
    (tr("Perceptual (rendering intent)"),
     tr("Squeezes the whole image smoothly into the printer's gamut, keeping relationships between colours. Good default for photos.")),
    (tr("printtarg"),
     tr("The ArgyllCMS tool that lays out a patch set onto printable pages (ChromIQ's layout engine is an alternative to it).")),
    (tr("Profile (verb)"),
     tr("To measure how a device reproduces colour and store the result as an ICC profile.")),
    (tr("Quality (profile build)"),
     tr("colprof's -q setting: how finely the profile models the measurements. Higher = slower build, bigger file, usually only marginally better.")),
    (tr("Relative colorimetric (rendering intent)"),
     tr("Reproduces in-gamut colours exactly, clips out-of-gamut ones to the edge. Good for proofing; can flatten saturated areas.")),
    (tr("Rendering intent"),
     tr("The strategy for squeezing colours into a smaller gamut: perceptual, relative colorimetric, saturation, or absolute colorimetric.")),
    (tr("RGB"),
     tr("Red, green, blue — how images, monitors, scanners and (from the computer's side) most photo printers describe colour.")),
    (tr("Saturation (rendering intent)"),
     tr("Keeps colours as vivid as possible at the expense of accuracy — for graphs and signage, not photos.")),
    (tr("scanin"),
     tr("The ArgyllCMS tool that reads patch values out of a SCANNED image of a target, using a .cht file to find the patches.")),
    (tr("Scanner target (IT8 etc.)"),
     tr("An industrially-made chart with known reference values (e.g. Wolf Faust IT8, LaserSoft), used to profile a scanner or camera.")),
    (tr("Soft-proof"),
     tr("Simulating on screen how an image will look when printed through a given profile — including its gamut limits.")),
    (tr("Spacer"),
     tr("A separator strip between patch rows/columns on a chart, helping strip-reading instruments (and scan alignment) stay on track.")),
    (tr("Spectrophotometer"),
     tr("A measuring device that samples the whole visible spectrum of a patch — the standard instrument for printer profiling.")),
    (tr("Strip"),
     tr("A row of patches read in one sweep by instruments like the i1Pro.")),
    (tr("targen"),
     tr("The ArgyllCMS tool that designs a patch SET (which colours to print) before printtarg/the engine lays it out.")),
    (tr("White point"),
     tr("The colour of the paper itself — the lightest 'colour' a print can contain. Profiles measure and account for it.")),
]


# App-workflow terms (Knut: "patch set, chart layout, layout engine, etc. —
# it should make a bit longer list").
GLOSSARY += [
    (tr("Open a project"),
     tr("Load a printer profile project you made earlier, so every tab acts "
        "on it again. Press “Open Project” at the top left ({keys}) and "
        "choose the “project.json” file inside the profile's own folder under "
        "your ChromIQ folder — or just pick the folder itself. Opening a "
        "project changes nothing inside it; it only tells ChromIQ which one "
        "you are working on. The project you had open before is left exactly "
        "as it was.").format(keys=keys_for("open_project"))),
    (tr("Close a project"),
     tr("Put ChromIQ back to how it looks on a fresh install, with no project "
        "open. Press “Close Project” at the top left — the third button, "
        "beside “Open Chart File”. Nothing is deleted: every run, chart, "
        "measurement and profile stays where it is on disk, and “Open "
        "Project” brings it all back. Only what you have typed and not yet "
        "used is let go — the name in “Printer profile project name”, and the "
        "run description beside it — and the Create Chart settings return to "
        "your saved defaults. Useful when you have finished a job, when you "
        "are handing the computer to someone else, or before moving a project "
        "folder somewhere else on disk.")),
    (tr("Patch set"),
     tr("The list of colours a chart will contain — designed by targen or by "
        "the generators in the chart editor — before anything is laid out on "
        "paper. Stored as a .ti1 file.")),
    (tr("Chart layout"),
     tr("How a patch set is arranged on the page: patch size, margins, "
        "spacers, strips and page splits. The layout decides what the "
        "instrument (or scanner) can read reliably.")),
    (tr("Layout engine"),
     tr("ChromIQ's own chart-layout generator — an alternative to printtarg. "
        "It records exactly where every patch sits, so scans of its charts "
        "can be read with perfect knowledge of the geometry.")),
    (tr("Preset"),
     tr("A saved set of chart options you can reload with one click. ChromIQ "
        "ships built-in presets (marked ★) and stores the ones you save "
        "yourself; both appear in the Presets dropdown.")),
    (tr("Chart recipe"),
     tr("The saved design of a chart's colour set (which generators, how many "
        "patches, in what order) — carried with the chart so the same design "
        "can be reloaded, edited or reused later.")),
    (tr("Preconditioning profile"),
     tr("A quick first-pass profile used to seed a better second chart: "
        "patch colours are chosen where the printer actually needs them. See "
        "the two-pass workflow.")),
    (tr("Refinement (two-pass)"),
     tr("Building a profile in two rounds: a first chart maps the printer "
        "roughly, a second chart — placed using that knowledge — measures "
        "where it matters. The measurements are merged for the final "
        "profile.")),
    (tr("Averaging (measurements)"),
     tr("Reading the same printed chart more than once and averaging the "
        "measurements. Evens out instrument noise and print unevenness; "
        "ChromIQ offers it after the last strip is read.")),
    (tr("Randomised patch order"),
     tr("Scrambling the printed order of patches so neighbouring strips "
        "don't contain similar colours in sequence. Helps strip-reading "
        "instruments notice when a strip was read wrongly.")),
    (tr("Patch sample area"),
     tr("How much of each patch's centre gets read when profiling from a "
        "scan — shown as the green inner square. Reading only the middle "
        "avoids edges, bleed and slight grid misplacement.")),
    (tr("Reading grid (marquee)"),
     tr("The draggable four-corner frame you place over a scanned target so "
        "ChromIQ knows where every patch sits. The misalignment check warns "
        "when it seems off.")),
    (tr("Demo target"),
     tr("A rendered stand-in scan for a standard target, with exact known "
        "colours and realistic softness/noise. Lets you try the scanner "
        "workflow end-to-end without hardware.")),
    (tr("Driver colour management"),
     tr("The printer driver's own colour correction. It MUST be off when "
        "printing charts — if the driver remaps colours, the measurements "
        "describe the driver, not the printer.")),
    (tr("Bit depth (8/16-bit)"),
     tr("How many steps each colour channel has: 8-bit = 256, 16-bit = "
        "65536. Charts print fine as 8-bit; 16-bit matters for smooth "
        "gradients and some editing workflows.")),
    (tr("Verification (profile check)"),
     tr("Printing and measuring a small chart THROUGH the finished profile "
        "to see how close the result lands (in ΔE). The honest way to judge "
        "a profile — better than trusting the build report.")),
    (tr("From profile gamut (verification chart)"),
     tr("A way of making a verification chart where the colours are chosen "
        "by your profile instead of by a patch generator: ChromIQ asks the "
        "profile which of a fixed reference list of colours it can print, "
        "and tests exactly those. Measuring the sheet then shows how far "
        "each printed colour landed from what the profile promised. The "
        "chart already has the profile applied when it is made, so it is "
        "printed exactly as it is — the Print Chart tab selects “Raw” for "
        "it automatically.")),
    (tr("Reference colour set (verification)"),
     tr("The fixed, published list of colours ChromIQ draws from when "
        "building a chart from a profile's gamut. It is the same list for "
        "everyone, so two people checking the same printer get comparable "
        "figures — and smaller charts test the first colours of the same "
        "list, so a quick check stays comparable with a thorough one. The "
        "report always names the list's version.")),
    (tr("Coverage (gamut check)"),
     tr("How many colours of the reference set your profile can print at "
        "all — a measure of the gamut of your printer, ink and paper "
        "together. Shown before printing and recorded on the report. More "
        "coverage means a roomier gamut; accuracy is measured separately, "
        "over the colours that are in reach.")),
    (tr("Raw verification print (drift check)"),
     tr("Printing a verification chart WITHOUT the profile — the chart's own "
        "numbers go straight to the paper. Measuring it answers a different "
        "question: has the printer changed since last time? It cannot judge "
        "the profile, because no profile took part. The Print Chart tab's "
        "“Colour” row chooses between the two, and the report records which "
        "way each sheet was printed.")),
    (tr("Which verification should I use? (the three ways)"),
     tr("Three checks, three questions. (1) A chart from your profile's "
        "gamut, printed as it is — “does my printer deliver what this "
        "profile promised?” The most honest accuracy check, judged colour "
        "by colour with nothing forgiven; the best everyday choice. (2) A "
        "verification chart printed through the profile — “is the whole "
        "ChromIQ printing path still right?” Printed with absolute intent "
        "it is judged exactly as measured, the paper's own tone included — "
        "the strictest reading; with the everyday relative intent the "
        "report judges it against the sheet's own paper white instead, "
        "because that is the white the print was aimed at. "
        "(3) A sheet printed from your own application — Photoshop, a "
        "layout program — with the profile applied: “does my everyday "
        "printing chain work?” This one is judged relative to the sheet's "
        "own paper white, because such prints map white to the paper — so "
        "the paper is not counted against the profile. Any of the three, "
        "repeated the same way over time, shows drift; the report records "
        "which way each sheet was made so they are never mixed silently.")),
    (tr("Judged relative to paper white (media-relative)"),
     # K31 (Knut, #182 5801677743, section 3): evenness and its own line.
     tr("A way the measurement report scores a verification sheet: every "
        "measured colour is scaled so that this sheet's own paper white "
        "counts as pure white, and only then compared with the expected "
        "colours. The report does this by itself whenever the sheet was "
        "printed in a way that maps white to the paper (through the "
        "profile with relative intent, or in another application with "
        "colour management) and says so in the “How this verification was "
        "produced” section. The point: on such a print the paper's own "
        "tone was never supposed to be corrected, so counting it against "
        "the profile would blame it for something it was never asked to "
        "do. Physical readings like paper white and deepest black are "
        "always shown as measured, and so is evenness: it compares the nine "
        "areas of one sheet with each other, so it uses the readings as the "
        "instrument took them and moves every aim colour onto the paper "
        "instead. The report says so in a line of its own, “How evenness "
        "was judged”, whenever an evenness row is in it.")),
    (tr("Within / beyond the profile's gamut (report split)"),
     # K31 (Knut, #182 5801677743, sections 5 and 6).
     tr("Two groups the Measurement Report sorts a verification sheet's "
        "colours into, by asking the run's profile which of the chart's "
        "design colours it can actually print. “Within the profile's gamut” "
        "are the genuinely printable colours: their ΔE figures are the fair "
        "measure of accuracy, the Pass/Fail verdict judges them, and on such "
        "a report their names end in “within gamut”, for example “Average "
        "ΔE00, all patches within gamut”. “Beyond it” are colours brighter "
        "or more saturated than this printer and paper can physically "
        "produce; their larger ΔEs describe the limit of the gamut, not a "
        "mistake of the profile, and their stability from check to check is "
        "a useful drift signal. The Overview shows both groups and, under "
        "“Within and beyond the gamut together”, all the colours as one, for "
        "information only: neither of those ever has a limit. Every patch "
        "stays counted and visible. (A chart from the “From profile gamut” "
        "module is never split: every colour on it is printable by "
        "design.)")),
    (tr("Judged as measured (no white adjustment)"),
     tr("The other way the Measurement Report can score a verification "
        "sheet: every measured colour is compared exactly as the instrument "
        "read it — nothing is scaled, the paper's own tone counts too. The "
        "report uses it for sheets whose printing did not map white to the "
        "paper: raw drift sheets, and sheets printed through the profile "
        "with absolute colorimetric intent. One thing this is NOT: a "
        "rendering intent. Rendering intents (relative, absolute, "
        "perceptual) exist only when colours are converted for printing — a "
        "sheet printed raw has no intent at all. “Judged as measured” "
        "describes how the report compares afterwards, and it applies to "
        "any sheet, however it was printed. Its counterpart is “Judged "
        "relative to paper white”, explained in its own entry.")),
    (tr("Import a measurement (IMPORT module)"),
     tr("A third mode on the Measure tab, shown for verification runs: "
        "instead of measuring here, you hand ChromIQ a measurement made in "
        "another program — typically i1Profiler with an i1iO table. ChromIQ "
        "converts the file, checks patch for patch that it really belongs to "
        "this run's verification chart, and files a copy in its own dated "
        "verification folder — exactly where a measurement made here would "
        "go. Your original file stays untouched.")),
]


# Naming and folder terms (#130) — the words the load dialogs and the Create
# Chart tab use, so a newcomer can tell the project from the profile file.
GLOSSARY += [
    (tr("Printer profile project name"),
     tr("The name of a whole profiling job: the title you type in the Create "
        "Chart tab. It is the same as the project folder on disk and the base "
        "name of every file inside it (chart, measurements, the finished "
        "profile). Rename it and ChromIQ offers to rename the folder and files "
        "to match. Saved measurement reports that name the project follow the "
        "new name: its own, those in the reports folder beside it, and those "
        "of the projects beside it. Not to be confused with the printer "
        "profile itself.")),
    (tr("Printer profile (the file)"),
     tr("The finished .icc / .icm file a project produces — the thing you "
        "install and pick in a print dialog. A project makes exactly one; it "
        "takes the project's name so it's easy to recognise later.")),
    (tr("Profile run"),
     tr("One attempt at building (or checking) a profile inside a project. A "
        "project can hold several — run1, run2, … — so you can try again "
        "without losing earlier work. The Profile-run bar chooses which one "
        "you're working in.")),
    (tr("Run description"),
     tr("Your own words for what one particular run is: the paper, the finish, "
        "the chart size — whatever makes it different from the other runs in "
        "the project. It is optional and stays empty until you fill it in. You "
        "type it in the “Run N Description” box on the Create Chart tab, and it "
        "stays with that run, so bringing back an earlier chart with “Restore "
        "Used Chart” never changes it. ChromIQ also offers it at the end of the "
        "profile's own description in the tab where you build the profile — "
        "called “4. Build Profile”, or “4. Calibration & Profiling” when "
        "calibration options are switched on in Preferences — so the finished "
        ".icc carries it too. It is a label for you and changes no file "
        "name.")),
    (tr("Chart notes"),
     tr("A short note printed ON the chart itself, so you can tell one printed "
        "sheet from another after they have been lying on the desk for a week "
        "— the paper, the date, the printer settings, whatever you would want "
        "to read off the page. You type it in the “Run N Chart Notes” box on "
        "the Create Chart tab in Manual mode. It belongs to the chart rather "
        "than to the run: if you later use “Restore Used Chart” to bring back "
        "the chart a measurement was made with, its notes come back with it, "
        "because they are what is printed on that sheet.")),
    (tr("{rundescription} (chart text marker)"),
     tr("A marker you can put into a chart's sheet text or its clip border, "
        "which ChromIQ replaces with that run's description when the chart is "
        "made — or with the calibration's description on a calibration chart. "
        "Add it from the “Insert ▾” menu rather than typing it, so it is "
        "spelled the way ChromIQ expects. If the description is empty the "
        "marker simply prints nothing, so a saved layout is safe to reuse on a "
        "run you have not described.")),
    (tr("Spectral measurement"),
     tr("A reading that records how much light a patch reflects at each "
        "wavelength, rather than just three numbers for “how red, how green, "
        "how blue”. Most spectrophotometers — the i1Pro and ColorMunki "
        "families — measure spectrally; most colorimeters do not. Spectral "
        "data is what lets ChromIQ compensate for optical brighteners in the "
        "paper and re-calculate colours under a different light source, so "
        "when a measurement is not spectral those options stay switched "
        "off.")),
    (tr("Run type (Calibration / Profiling / Verification)"),
     tr("What you are working on right now, chosen in the Profile-run bar above the tabs. "
        "The list reads in the order of the work. Calibration prepares the "
        "printer itself, before any profile is built; there is one per "
        "project, and it needs no run. Profiling builds the profile — "
        "chart, measurement, .icc — and is what you want most of the time, "
        "which is why it is the one already selected. Verification checks "
        "a finished profile by measuring a chart printed through it; its "
        "results are kept in the run's “verifications” folder, dated, and "
        "never change the profile. Calibration appears only while calibration "
        "options are switched on in Preferences.")),
    (tr("old/ folder"),
     tr("Where ChromIQ moves files it would otherwise overwrite — every "
        "displaced chart, measurement or profile is kept in a dated “old” "
        "sub-folder instead of being deleted, so nothing is ever lost.")),
]


# The Measurement Report, the limits it judges against, and the standards and
# reference data behind them (#182, Knut 2026-09-20: *"The 'Dictionary and
# terminology' help card needs to be updated with all the new terms used in
# the measurement report, for the verification and standards, the FOGRA
# related tools (FOGRA, metrics, limits, reference files, etc.)."*).
#
# APPENDED, never inserted. `test_the_glossary_prints_its_terms` asserts on
# GLOSSARY[:8] in SOURCE order, and the card itself sorts alphabetically at
# render time, so a new term belongs at the end of the list and nowhere else.
GLOSSARY += [
    (tr("Measurement Report"),
     tr("The tool that turns a measurement into a document: what was "
        "measured, how far each figure is from what the chart asked for, "
        "whether that is inside the limits you chose, and how the printer has "
        "moved since the last check. Tools ▸ “Measurement report (accuracy & "
        "drift)”. It reads measurements you already have and writes a "
        "report_*.json beside them, plus a PDF when you ask for one; it never "
        "changes a measurement or a profile.")),
    (tr("Limit set"),
     tr("One column of the Report limits table: the numbers a report is "
        "judged against, one per row. ChromIQ ships three of its own, "
        "“ChromIQ default (recommended)”, “ChromIQ tight” (half the numbers) "
        "and “Quick check” (double them), plus two read-only columns named "
        "after ISO 12647-7 and 12647-8 that hold a standard's published values "
        "where ChromIQ ships them or a licence holder supplies them, and read "
        "“?” where neither is so, and two Custom columns you fill in yourself. "
        "Pick one "
        "in the report window's “Judged against:” pulldown.")),
    (tr("Row (in the limits table)"),
     tr("One line of a limit set, and it is always a population and a "
        "statistic together: WHICH patches, and WHICH number about them. "
        "“Average ΔE00, all patches” and “Maximum ΔE00, all patches” are two "
        "rows, not "
        "one, because a chart can pass on the average and fail on the worst "
        "patch. The rows are grouped by population: Paper, Solid colours, "
        "Control strip, the grey ramp, all patches, selected patches, and the "
        "ones ChromIQ does not evaluate.")),
    # COND IS NOT A ROW WORD ANY MORE, since Knut retired it as one on
    # 2026-09-21 (#182): `compliance_sets.row_verdict` returns PASS or FAIL
    # and never COND. The report window's own guide was rewritten that day
    # and these four help-card sentences were missed, so the Getting Started
    # card went on teaching the retired meaning as the only meaning, in
    # thirteen languages.
    (tr("PASS, FAIL, COND, INFO, N-A (the verdict words)"),
     tr("What a row of a report says about itself. PASS is inside its limit "
        "and FAIL is outside it. INFO means the number is shown for "
        "information only and nothing was judged from it: on a report type "
        "that judges nothing, such as the Printing record, on a profiling "
        "measurement or a raw drift check, which are never graded, and on a "
        "row that needs something about the print that was not recorded. A "
        "row the limit set puts no limit on (“–”) is left out of the report "
        "altogether. N-A means your chart "
        "carries nothing that could answer the row at all. A row the set "
        "cannot express gets no word. COND is not a row word: it belongs to "
        "the column's Overall, below. A report saved before ChromIQ 4.3.0 "
        "may still show COND on a row, where it meant a value over a limit "
        "the set only recommended; such a row reads FAIL today.")),
    # **AN N-A NEVER DEMOTES A COLUMN**, since Knut widened the rule on
    # 2026-09-21: *"a metric that is not applicable should not have verdict
    # conditional … When all other metrics PASS, that N-A is not applicable,
    # thus not relevant for the verdict, thus overall verdict becomes PASS."*
    # This entry went on teaching the arithmetic that ruling deleted, in
    # thirteen languages and translated into German, and the register that
    # pinned it recorded the clause as innocent. Measured over every
    # combination of up to three rows: COND arrived from an ISO-named set or
    # from a row a pre-4.3.0 report saved with the word, and from nothing else.
    # **AND THEN THE FIRST OF THE TWO WENT**, on Knut's ruling of 2026-09-22
    # retiring the ISO cap, so one cause is left and this entry named the
    # deleted one.
    (tr("Overall (verdict)"),
     tr("The one word for a whole dated check, worked out from its rows: any "
        "FAIL makes it FAIL; an ungraded sheet is INFO; a row your chart "
        "could not answer is not counted as a failure; otherwise PASS. A "
        "column judged against one of the ISO-named sets reads PASS or FAIL "
        "like any other, and carries a note saying that its values are a "
        "standard's applied to your chart rather than a test against that "
        "standard.")),
    (tr("Graded / not graded"),
     tr("Whether a sheet's numbers are compared with limits at all. A "
        "verification sheet printed through the profile is graded. A "
        "PROFILING measurement never is: it is expected to fall outside "
        "accuracy limits, because it is the raw material a profile is built "
        "FROM rather than a test of one. A raw drift check is not graded "
        "either, because no profile is in the loop to be right or wrong. An "
        "ungraded sheet shows every figure and reads INFO throughout.")),
    (tr("A report's limit set"),
     tr("Every report carries a copy of the limit set it was judged against, "
        "and judges every measurement it covers against that one set, "
        "whichever profile run or project the measurement comes from. "
        "Changing a set later never re-judges a report already saved; to "
        "judge measurements against another set, make a report of them or "
        "update one. A profile run holds no limits of its own, only, if you "
        "choose one in Edit limits…, the set its new reports start on.")),
    (tr("Required limit and recommendation (the brackets)"),
     tr("In the Report limits table a plain number is a limit the set "
        "REQUIRES; a number in brackets, such as (2.0), is one it only "
        "recommends. Missing either reads FAIL, and a row over a recommended "
        "limit carries a note saying the limit was a recommendation. Three "
        "other marks appear in the same column: “–” means the set puts no "
        "limit on that row, “?” means the set limits the row but no number "
        "has been supplied for it, and “✕” means ChromIQ cannot measure that "
        "row at all.")),
    (tr("Report type"),
     tr("Which document the report is. “Colour summary (one page)” is a "
        "single sheet about a single measurement. “Full colour check” is the "
        "complete one. “Grey and tone check” concentrates on neutrals and the "
        "tone ramps. “Printing record (not graded)” sets down what was "
        "printed and measured and judges none of it. Two further types named "
        "after ISO 12647-7 and 12647-8 are shown and greyed out: the "
        "standards' values ship with ChromIQ as two read-only limit sets, "
        "but those two documents are not built yet. Pointing at the greyed "
        "entry says why.")),
    (tr("Report scope (All dates, One date, Multiple dates)"),
     tr("A tag on a report's name saying how much it covers. A verification "
        "report reads One date, Multiple dates or All dates; a profiling "
        "report names its run (Run1, Run2 and so on), or reads Multiple runs "
        "or All runs; a calibration report reads Cal for one project's "
        "calibration, or Multiple cals or All cals when calibrations of "
        "several projects are in it. “All” means every measurement in the "
        "list was ticked. The tag follows what the report covers and nothing "
        "else: an update that covers the same measurements keeps it, and one "
        "that covers more or fewer changes it.")),
    (tr("ΔE00 (CIEDE2000)"),
     tr("The colour difference ChromIQ reports everywhere, and a newer "
        "formula than the plain ΔE in the older entry: it corrects for the "
        "fact that the eye is far fussier about some colours than others. "
        "Read it the same way, with about 1 invisible and 2 to 4 visible side "
        "by side.")),
    (tr("ΔCh (grey balance)"),
     tr("How far a grey has wandered off neutral, measured as the distance in "
        "a* and b* from a perfect grey and ignoring lightness altogether. It "
        "is the right number for a grey ramp, because a grey that is a little "
        "too dark is a tone problem while a grey that is a little too pink is "
        "a colour problem, and only the second one is what grey balance "
        "asks about.")),
    (tr("ΔH*ab (hue difference)"),
     tr("How far a colour's HUE has moved, with lightness and saturation "
        "taken out of it. Used on the cyan, magenta and yellow solids, "
        "because an ink that prints a little weak is a different fault from "
        "an ink that prints the wrong colour, and a hue shift is the one that "
        "shows in every image.")),
    (tr("ΔL* (lightness difference)"),
     # K31 rule A (Knut, #182 5801677743, section 4).
     tr("How much lighter or darker a patch came out than it should be, with "
        "colour taken out of it. Used on the single-colour ramps between "
        "30 % and 70 %, where the eye reads a lightness error as a tone "
        "curve going wrong. A ramp counts there when it has at least three "
        "steps in that band, spread roughly evenly rather than bunched at "
        "one end.")),
    (tr("95th percentile (a report row)"),
     tr("The figure that all but the highest 5 % of your patches come in "
        "under; the report names it “Maximum ΔE00, lowest 95 % (95th "
        "percentile)”. "
        "It is a fairer summary than the maximum difference, which one dusty "
        "patch can dominate, and a stricter one than the average, which hides "
        "a bad tail. ChromIQ takes it by nearest rank, so the number is "
        "always one of your real measurements rather than an "
        "interpolation.")),
    (tr("Grey ramp"),
     # K31 option (a) (Knut, #182 5801677743, section 7).
     # (the device tolerances and the tone row's needs: B8-910, beta 39.)
     tr("A run of patches whose red, green and blue values are equal, or "
        "within one unit of each other, stepping from white to black. ChromIQ "
        "needs at least eight of them, reaching both ends and roughly evenly "
        "spaced (each within 4 % of full scale of where an even spacing puts "
        "it), before it will judge grey balance on your chart; a chart "
        "without one gets N-A on those rows rather than a guess. On a chart "
        "built with “From profile gamut” the grey steps are the patches whose "
        "aim colour is neutral instead, because the profile prints a neutral "
        "grey with slightly unequal red, green and blue. The tone row needs "
        "less: a single-ink or grey ramp with at least three roughly evenly "
        "spaced steps between 30 % and 70 %.")),
    (tr("Control strip"),
     tr("In printing, the narrow band of standard patches along the edge of a "
        "sheet that a press operator measures. ChromIQ has no such band, so "
        "it looks for patches of its own chart that stand in for one: the "
        "paper, the eight ink extremes, tint ladders of each, and a few "
        "neutrals. When enough of them are present it writes a small "
        "“.control-strip.json” beside the verification chart naming which "
        "patches those are, and that is what lets a report fill the three "
        "control-strip rows instead of marking them N-A.")),
    (tr("Solid colours (solids)"),
     tr("The inks at full strength, with no tint and nothing mixed in. They "
        "are judged on their own row because they are the colours a printing "
        "standard describes most tightly, and because an error there affects "
        "everything printed with that ink.")),
    (tr("Cube corners (the eight ink extremes)"),
     tr("White, black, red, green, blue, cyan, magenta and yellow: the eight "
        "corners of the device's colour cube. They are the outer limits of "
        "what the printer can do, so the report trends them separately, and a "
        "corner that moves tells you something quite different from an "
        "average that moves.")),
    (tr("Outer-gamut and surface-gamut patches"),
     tr("Two populations the report judges apart from the rest. Surface-gamut "
        "patches sit on the outside of the device's colour cube, and "
        "outer-gamut patches are the most saturated quarter of the chart. "
        "Both are where a profile is worked hardest, so a chart that is "
        "excellent on average and poor here is telling you where it will let "
        "you down.")),
    (tr("Not evaluated by ChromIQ (the ✕ rows)"),
     tr("A group of rows at the foot of the limits table that a printing "
        "standard asks for and ChromIQ cannot measure: macro-uniformity, "
        "repeatability from day to day, light "
        "fastness, permanence in storage, rub resistance and the rest. They "
        "are listed rather than hidden, so you can see what a report does NOT "
        "cover as well as what it does.")),
    (tr("ISO 12647-7 and ISO 12647-8"),
     tr("Two parts of the printing standard: -7 covers a contract proof and "
        "-8 a validation print. ChromIQ names two limit-set columns after "
        "them. Each holds that standard's published values, as values only, "
        "where ChromIQ ships them or a licence holder supplies them; a column "
        "with neither reads “?” and judges nothing. ChromIQ can never say "
        "that a print conforms to a standard: "
        "it reports what it measured against the numbers in the column you "
        "chose, which "
        "is a different claim.")),
    (tr("Report limits (window)"),
     tr("The window that shows every limit set side by side, one column each, "
        "so you can compare them and edit your own. Reached from the "
        "Measurement Report through “Edit limits…”, and from Preferences → "
        "Reports. From the Measurement Report its first column, “This "
        "report”, holds the report's own limits, which a change there "
        "affects only; it is also where the default set for new reports is "
        "chosen, and, when every measurement of the report is of one profile "
        "run, the one that run's new reports start on.")),
    (tr("Reference values (window)"),
     tr("The one door to other people's numbers, reached from Report limits. "
        "It has two halves that must not be confused: the ISO half, where a "
        "licence holder puts in a file of limit values from their own copy, "
        "which take the place of any ChromIQ ships, "
        "and the FOGRA half, which shows which copy of each reference set is "
        "in force and lets you replace one with a newer file.")),
    (tr("Reference set (printing condition)"),
     tr("A table of the colours a named printing condition AIMS for, such as "
        "“Coated commercial print, current (FOGRA51)”. It is not a limit set, "
        "and the difference is worth holding on to: a reference says what a "
        "colour should BE, a limit set says how far off it may be. ChromIQ "
        "ships eleven of them and will prefer your own copy of any set over "
        "the one it shipped.")),
    (tr("Characterisation data"),
     tr("Fogra's own name for a reference set: the measured colours of a "
        "printing condition, published so that everybody aims at the same "
        "target. ChromIQ ships the Media Wedge subsets under Fogra's own "
        "published grant, records where each file came from and its checksum, "
        "and credits Fogra in the Licences page, which the grant "
        "requires.")),
    (tr("FOGRAxx (FOGRA39, FOGRA51, FOGRA61 …)"),
     tr("The identifier of one printing condition, named for the Fogra "
        "research institute that publishes the data. The number is the "
        "condition, not a version or a quality: FOGRA51 is today's coated "
        "commercial print and FOGRA39 is what it replaced. The designation "
        "may be used solely to identify the respective reference data. It is "
        "not a certification, approval or endorsement by Fogra.")),
    (tr("Aim values (colorimetric reference)"),
     tr("The colours a chart is SUPPOSED to be, which is what a measurement "
        "has to be compared against before it can mean anything. A chart "
        "built by “FROM PROFILE GAMUT” carries its own aims in a "
        "“-reference.ti3” file beside it; without such a file a report "
        "compares against the chart's own design colours instead, and three "
        "rows of the limits table cannot be filled at all.")),
    (tr("Which presets can be used for verification? (window)"),
     tr("A window on the Create Chart tab, shown on verification runs only, "
        "that lists every preset against the metrics a report of the type and "
        "limit set you choose asks of a chart, and says how many of them each "
        "preset can answer. A ★ marks a chart MADE for verification: one "
        "page, 600 patches or fewer, and nothing withheld that a different "
        "patch set would supply. It marks presets, it never withholds them, "
        "and a double-click loads one into Create Chart.")),
]

GLOSSARY_CARD: dict = {
    "key": "glossary",
    "title": tr("Dictionary and terminology"),
    "subtitle": tr("Every term used in ChromIQ and in printer/scanner "
                   "profiling, explained in plain language."),
    "steps": [],
    "kind": "glossary",
}
# Knut, #130 2026-08-01: *"in the Welcome to ChromIQ window, swap
# position/places of help card 'Dictionary and terminology' with
# 'Profiling a CMYK+N printer'."* The CMYK+N card is appended where the
# glossary used to sit; the glossary now follows it (see below). Only the
# order changes — neither card's content is touched.


# "Where are my files?" — the project-folder guide (#125, Knut). Its own card
# (Basti), rendered as one flowing text page (the body is a single translated
# catalog key shared with ui.file_guide).
from ui.file_guide import (file_guide_body, file_guide_card_subtitle,  # noqa: E402
                           file_guide_card_title)

# "Getting started" — the tour of the interface and the five steps (#130,
# Knut 2026-07-28). Inserted at the FRONT of the grid: it is the card a first
# run should meet before any of the specialised ones.
from ui.getting_started import (getting_started_card_subtitle,  # noqa: E402
                                getting_started_card_title)

GETTING_STARTED_CARD: dict = {
    "key": "getting_started",
    "title": getting_started_card_title(),
    "subtitle": getting_started_card_subtitle(),
    "steps": [],
    "kind": "getting_started",
}
WORKFLOWS.insert(0, GETTING_STARTED_CARD)

# "Overview of Main Actions" — every action and each route to it, as a table
# (#130, Knut 2026-07-28: "create this as a separate help card next to the
# Getting Started Card"). Second in the grid, so it sits beside the tour.
from ui.main_actions import (main_actions_card_subtitle,  # noqa: E402
                             main_actions_card_title)

MAIN_ACTIONS_CARD: dict = {
    "key": "main_actions",
    "title": main_actions_card_title(),
    "subtitle": main_actions_card_subtitle(),
    "steps": [],
    "kind": "main_actions",
}
WORKFLOWS.insert(1, MAIN_ACTIONS_CARD)


FILE_GUIDE_CARD: dict = {
    "key": "file_guide",
    "title": file_guide_card_title(),
    "subtitle": file_guide_card_subtitle(),
    "steps": [],
    "kind": "files",
}
# THIRD in the grid, beside "Overview of Main Actions" (Knut, #130 2026-07-29:
# *"Move the card to be places third in the list of cards, next to 'Overview of
# Main Actions'."*). Where your files are is a question a new user has on their
# first build, so it belongs with the two orientation cards rather than after
# the specialised workflows.
WORKFLOWS.insert(2, FILE_GUIDE_CARD)


# Profiling a printer with extra inks (CMYK+N / 6-ink, 7-ink …) — its own
# card, because the workflow has a few extra decisions a normal RGB inkjet
# doesn't (Knut). Rendered as one flowing text page.
def numbered_prose_html(body: str) -> "str | None":
    """Turn a plain-text "1) … 2) …" body into a real ``<ol>``, or return None.

    The CMYK+N help card is the only card written as one prose string rather
    than as `steps` tuples, so its list was literal characters: `1)` not `1.`,
    no indent, and its sub-points at the same margin as the text around them.
    Knut: *"These numbered lists shall look on the print and pdf like the other
    numbered items: 1. 2. 3. etc, with indentation in front, and text belonging
    to each numbered item also indented till after the dot of the number."*

    Converted HERE, at render time, rather than by re-cutting the card into
    `steps`: the string is one translated key, and all twelve catalogues keep
    the `1)`…`6)` markers and the `  • ` bullets byte-identically. Re-cutting
    would turn one key into eight and invalidate ~96 translation units;
    converting costs nothing.

    IT REFUSES RATHER THAN GUESSES. A translator is free to renumber, to use
    full-width digits, or to drop a marker, and a converter that half-recognised
    that would mangle the card. So the shape is accepted only when the markers
    are 1..N, consecutive, and start consecutive blocks; anything else returns
    None and the caller renders the prose exactly as it does today.
    """
    import html
    import re

    blocks = [b for b in (body or "").split("\n\n")]
    marked = [(i, b) for i, b in enumerate(blocks)
              if re.match(r"^\s*\d+\)\s", b)]
    if len(marked) < 2:
        return None
    nums = [int(re.match(r"^\s*(\d+)\)", b).group(1)) for _i, b in marked]
    if nums != list(range(1, len(nums) + 1)):
        return None                       # renumbered, or a marker is missing
    idx = [i for i, _b in marked]
    if idx != list(range(idx[0], idx[0] + len(idx))):
        return None                       # the items are not contiguous blocks

    def _esc(t: str) -> str:
        return html.escape(t).replace("\n", " ")

    out: list[str] = []
    for b in blocks[:idx[0]]:
        if b.strip():
            out.append(f"<p>{_esc(b.strip())}</p>")
    out.append('<ol class="tight">')
    for _i, b in marked:
        lines = b.strip().split("\n")
        head = re.sub(r"^\s*\d+\)\s*", "", lines[0])
        prose: list[str] = []
        bullets: list[str] = []
        after: list[str] = []
        for ln in lines[1:]:
            if ln.strip().startswith("•"):
                bullets.append(ln.strip().lstrip("•").strip())
            elif bullets:
                after.append(ln.strip())
            else:
                prose.append(ln.strip())
        item = f"<b>{_esc(head)}</b>"
        if prose:
            item += "<br>" + _esc(" ".join(prose))
        if bullets:
            item += "<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in bullets) + "</ul>"
        if after:
            # Inside the item, or it escapes the list's indent and sits back at
            # the left margin under the bullets.
            item += f"<p>{_esc(' '.join(after))}</p>"
        out.append(f"<li>{item}</li>")
    out.append("</ol>")
    for b in blocks[idx[-1] + 1:]:
        if b.strip():
            out.append(f"<p>{_esc(b.strip())}</p>")
    return "".join(out)


def _cmyk_n_body() -> str:
    return tr(
        "Most desktop inkjets are driven as RGB devices — you send red, green "
        "and blue, and the printer's own software decides how to mix its inks. "
        "Some printers, though, can be driven by their actual inks: CMYK "
        "(cyan, magenta, yellow, black) or CMYK plus extra inks such as "
        "orange, green, violet, light cyan or light magenta — written CMYK+N, "
        "where N is the number of extra inks (so a 7-ink printer is CMYK+3). "
        "Profiling one of these is very much like the normal five-step "
        "workflow, with a handful of extra choices. Here is the whole picture.\n"
        "\n"
        "1) Does your printer actually accept ink values?\n"
        "This is the big question. Many photo inkjets have six or more ink "
        "tanks but are still driven as RGB — the driver mixes the inks for "
        "you, and you cannot address them directly. You can only profile a "
        "printer as CMYK+N if there is a way to send it raw ink amounts "
        "(a RIP, a dedicated driver mode, or a device-link path) with the "
        "printer's own colour management switched OFF. If in doubt, profile it "
        "as a normal RGB printer — that is the right choice for most desktop "
        "machines.\n"
        "\n"
        "2) Create the chart (tab 1) — choose the ink set.\n"
        "In Create Chart, set the device to your ink layout (e.g. CMYK, "
        "CMYK+OGV, …) instead of RGB. ChromIQ then builds a chart whose "
        "patches are ink combinations, not screen colours. Extra inks mean "
        "many more patches are needed to map the larger colour space well, so "
        "these charts are bigger — often several pages. The preview shows the "
        "patches with approximate colours; the ink amounts in the file are "
        "exact.\n"
        "\n"
        "3) Print the chart (tab 2) — colour management OFF.\n"
        "This matters even more than for RGB: the printer must lay down "
        "exactly the ink amounts in the chart, with no driver colour "
        "correction in between. Use the print path that bypasses colour "
        "management (a RIP set to “no colour management”, or ChromIQ's raw "
        "print where supported). If the driver re-mixes the inks, the profile "
        "will be wrong.\n"
        "\n"
        "4) Measure (tab 3).\n"
        "Measuring is identical to RGB — sweep each strip with your "
        "instrument. Because the chart is larger, budget more time. Everything "
        "in the Measure tab (auto-save, re-measuring a strip, the split-patch "
        "preview) works the same.\n"
        "\n"
        "5) Build the profile (tab 4) — the extra-ink settings.\n"
        "Building a CMYK+N profile needs a couple of choices a normal RGB "
        "profile doesn't:\n"
        "  • Total ink limit — the most ink the paper can hold before it "
        "floods or dries badly, as a percentage. Too high and darks bleed; "
        "too low and you lose depth. Your paper/printer notes, or a quick "
        "ink-limit test, give a starting value.\n"
        "  • Black generation (GCR/UCR) — how much grey is built from black "
        "ink versus a C+M+Y mix. This affects neutrals, shadow detail and ink "
        "use.\n"
        "  • Extra-ink handling — how orange/green/violet etc. are used at the "
        "edges of the gamut.\n"
        "ChromIQ fills in sensible defaults; the tooltips on each field "
        "explain what to change and when. For six inks and beyond, ChromIQ "
        "uses its own profile engine (Argyll's own profiler stops at four "
        "inks), so make sure the profile engine is available.\n"
        "\n"
        "6) Check and refine (tab 5).\n"
        "Same as always: build a quick test, measure a few patches, and "
        "refine the worst strips. With more inks there is more to get right, "
        "so a refinement pass is especially worthwhile.\n"
        "\n"
        "In short: it's the same five steps, but you drive the printer by its "
        "inks, you keep colour management strictly off, your charts are "
        "bigger, and the profile build asks a few ink-specific questions. When "
        "unsure, a normal RGB profile is perfectly good for most printers.")


CMYK_N_CARD: dict = {
    "key": "cmyk_n",
    "title": tr("Profiling a CMYK+N printer (extra inks)"),
    "subtitle": tr("What's different when your printer is driven by its inks "
                   "(CMYK, or CMYK plus orange / green / violet …), start to "
                   "finish."),
    "steps": [],
    "kind": "richtext",
    "body": _cmyk_n_body(),
}
# CMYK+N and the Dictionary are appended AFTER the three tool cards below, so
# that the Dictionary and Keyboard-shortcuts cards stay side by side in the
# grid — Knut, 4.1.3-beta.15: *"Dictionary and terminology help card shall stay
# next to the keyboard shortcuts help card as before."* With 21 cards in three
# columns the last row is what decides it: appending the three new tool cards
# at the end pushed the Dictionary onto the row above and left Keyboard alone
# at the end of the next. Adding them here instead gives the three tool cards a
# clean row of their own and restores the beta.14 final row
# (CMYK+N | Dictionary | Keyboard shortcuts). #130's ruling that CMYK+N comes
# immediately before the Dictionary still holds.
#
# See the two appends further down — this is one ordering, written in two
# places, so keep them together in your head when adding a card.


# ---------------------------------------------------------------------------
# Tool cards (Knut, 4.1.3-beta.13): the three Tools-menu windows that had no
# card of their own. Same shape as the workflow cards above so they print and
# save to PDF identically.
# ---------------------------------------------------------------------------

PATCH_SET_EDITOR_CARD: dict = {
    "key": "patch_set_editor",
    "title": tr("Design a custom patch set for a chart"),
    "subtitle": tr("Using Tools ▸ “Edit / create chart patch set” — build a "
                   "colour set from scratch, or change the one a chart "
                   "already has."),
    "steps": [
        (1, tr("Open “Tools” at the top right and choose “Edit / create chart "
            "patch set”, under “Charts & patch sets”."),
         False,
         ((tr("What this window owns, and what it does not"),
           tr("A patch set is the LIST OF COLOURS a chart prints, and nothing "
              "else. Where those colours sit on the paper, the patch size, "
              "the margins, how many pages, is the Create Chart tab's job. "
              "That split is invisible until you apply your work, and then it "
              "decides what happens: see the last two steps.")),)),
        (2, tr("Look at what the window opened on."),
         False,
         ((tr("With a chart loaded"),
           tr("The window opens on ITS patch set and the title bar names it. "
              "Every colour is listed, and the grid beside the list shows "
              "them as swatches so you can see the shape of the set at a "
              "glance. When the chart carries its setup information, which "
              "ChromIQ charts do, the settings it was built with are shown "
              "alongside, so you can see what the set was designed for "
              "instead of guessing.")),
          (tr("With no chart loaded"),
           tr("The window opens empty and waits for you to build a set. Start "
              "at the next step.")))),
        (3, tr("Click “New patch set” to start a set from scratch, and pick "
            "how many of each kind of colour you want."),
         False,
         ((tr("What the generators offer, and what each is for"),
           tr("A regular grid through the whole colour space; extra patches "
              "on the gamut corners; detail just inside the most saturated "
              "colours; pure paper white and solid black; and near-neutral "
              "greys. You choose how many of each and ChromIQ shows the "
              "running total as you go. Note that this REPLACES whatever is "
              "in the window.")),)),
        (4, tr("Click “Add” to extend the set already in the window instead "
            "of replacing it."),
         False,
         ((tr("The two ways to add, and the whole difference"),
           tr("Type or pick a single colour, or bring in the colours from an "
              "existing file so you can fuse two sets together. Nothing "
              "already in the set is lost. So: “New patch set” to start "
              "again, “Add” to build on what you have. That is the whole "
              "difference between them.")),)),
        (5, tr("Edit individual colours directly in the list, or remove ones "
            "you do not want."),
         False,
         ((tr("How to see whether the set is any good"),
           tr("Tools ▸ “Show patch distribution (3D)” is the quickest way to "
              "see whether your set covers the colour space evenly or leaves "
              "a hole. A hole profiles that part of the colour space badly, "
              "and it is far easier to see as a gap in a cube than as an "
              "absence in a list of numbers.")),)),
        (6, tr("Press “Apply / Save…” and choose “Overwrite”, “Save As…” or "
            "“Cancel”."),
         False,
         ((tr("“Overwrite” sends the patch set to Create Chart"),
           tr("The PATCH SET goes to the Create Chart tab and is laid out "
              "there. The page layout comes from that tab, not from this "
              "window: your instrument, paper, margins and patch size are "
              "used exactly as they are set there, so the arrangement you see "
              "here is not carried across. The patch recipe is then locked so "
              "it cannot be rebuilt by accident, while the page layout stays "
              "editable.")),
          (tr("“Save As…” writes the complete chart, layout and all"),
           tr("The patch list, this layout and the printable pages, plus the "
              "i1Profiler files and a colour list, all into a folder you "
              "choose, without leaving the editor. This is the one that keeps "
              "the layout you see here. “Cancel” goes back to the editor and "
              "changes nothing.")))),
        (7, tr("Open or start a project before using “Overwrite”."),
         False,
         ((tr("What happens if you do not"),
           tr("“Overwrite” needs somewhere to put the chart. With no project "
              "open, ChromIQ says so and changes nothing. Start one on the "
              "Create Chart tab, or use “Save As…” instead and open the "
              "folder afterwards.")),)),
    ],
}

SPOT_READ_CARD: dict = {
    "key": "spot_read",
    "title": tr("Spot-read the colour of a surface"),
    "subtitle": tr("Using Tools ▸ “Read single patches” — measure one colour "
                   "at a time, with no chart involved."),
    "steps": [
        (1, tr("Open “Tools” at the top right and choose “Read single "
            "patches”, under “Measurements”."),
         False,
         ((tr("What this is for"),
           tr("Measuring ONE colour at a time: a paper you want the white "
              "point of, an ink patch, a wall, a light source. It is not part "
              "of profiling, and it writes nothing into your project unless "
              "you save it yourself.")),)),
        (2, tr("Pick what you are measuring in the mode box at the top, "
            "BEFORE you start the session."),
         False,
         ((tr("The three modes, and which one you want"),
           tr("“Reflective (material)” is anything lit by room light: paper, "
              "print, fabric, paint. This is the usual choice. “Emissive "
              "(display)” is something that makes its own light, such as a "
              "monitor. “Ambient (light)” is the light falling on a scene, "
              "measured with the instrument's diffuser in place. The mode has "
              "to be right before you start, because it decides how the "
              "instrument calibrates.")),)),
        (3, tr("Click “Start session” and calibrate the instrument when it "
            "asks."),
         False,
         ((tr("When you may skip the calibration, and when you may not"),
           tr("For most instruments calibrating means putting it on its "
              "white tile and following the prompt. If your instrument has "
              "just calibrated and you know it is still valid, “Skip "
              "initial calibration” saves the step. Leave it unticked when "
              "in doubt: an uncalibrated reading is confidently wrong "
              "rather than obviously wrong. The button becomes “Stop "
              "session” while a session is open.")),)),
        (4, tr("Place the instrument on the colour and click “Take reading”, "
            "or press the button on the instrument itself."),
         False,
         ((tr("Why the instrument's own button is often easier"),
           tr("It saves reaching for the mouse while the instrument is "
              "face-down on a sheet, which is exactly when a nudge spoils the "
              "reading. Each reading is added to the list with its Lab values "
              "and a swatch of the colour measured.")),)),
        (5, tr("To average several readings of the same colour, take a few, "
            "select them in the list, and click “Average selected”."),
         False,
         ((tr("When averaging is worth doing"),
           tr("On textured or uneven material, where one spot is not "
              "representative of the surface. The average is added as a new "
              "entry and the readings it came from stay in the list, so "
              "nothing is lost and you can see the spread you averaged "
              "over.")),)),
        (6, tr("Use “Save…” before “Close”, if the readings matter."),
         False,
         ((tr("What each button does to your readings"),
           tr("“Clear” empties the list and starts over. “Save…” writes the "
              "readings to a file you choose so you can keep or share them. "
              "“Close” ends the session and closes the window, and anything "
              "not saved is let go.")),)),
    ],
}

PATCH_CUBE_CARD: dict = {
    "key": "patch_cube",
    "title": tr("Show or compare a chart's patch set in 3D"),
    "subtitle": tr("Using Tools ▸ “Show patch distribution (3D)” — see how "
                   "your colours are spread, and where the gaps are."),
    "steps": [
        (1, tr("Open a project or a chart first, then open “Tools” at the top "
            "right and choose “Show patch distribution (3D)”, under “Charts & "
            "patch sets”."),
         False,
         ((tr("What the dots are, and what a gap means"),
           tr("Every patch in the chart is drawn as a dot, placed where its "
              "colour sits in the colour space and painted in that colour. A "
              "well-designed set fills the space evenly. A set with a hole in "
              "it will profile that part of the colour space badly, and the "
              "hole is far easier to see here than in a list of "
              "numbers.")),)),
        (2, tr("Drag to turn the cube, scroll to zoom, and drag with the "
            "right mouse button to slide the view sideways."),
         False,
         ((tr("If you lose your bearings"),
           tr("Double-click anywhere in the view to go back to the starting "
              "viewpoint.")),)),
        (3, tr("Optional: click “Compare with profile” beside the chart name "
            "to put a second cube next to the first."),
            True,
         ((tr("What the comparison answers"),
           tr("The second cube shows a built-in preset's patch set, grouped "
              "by the instrument it was designed for. This is the quickest "
              "way to answer “is my set as well spread as a known-good "
              "one?”, and the two cubes turn together, so you are always "
              "comparing the same viewpoint. Choose “None” to close the "
              "comparison and go back to one cube.")),)),
        (4, tr("Click “Close” when you are done. Nothing here changes your "
            "chart."),
         False,
         ((tr("Where to change the patch set instead"),
           tr("This window only looks. To CHANGE the patch set, use Tools ▸ "
              "“Edit / create chart patch set”, which has its own "
              "card.")),)),
    ],
}

WORKFLOWS.append(PATCH_SET_EDITOR_CARD)
WORKFLOWS.append(SPOT_READ_CARD)
WORKFLOWS.append(PATCH_CUBE_CARD)
# …and only now the two that must end up in the final row (see the note above).
WORKFLOWS.append(CMYK_N_CARD)
WORKFLOWS.append(GLOSSARY_CARD)


# Keyboard shortcuts — its own card (Knut/Sebastian keyboard-accessibility pass),
# an alphabetical HTML table sourced from ui.keyboard_help.
from ui.keyboard_help import (keyboard_card_subtitle,  # noqa: E402
                              keyboard_card_title)

KEYBOARD_CARD: dict = {
    "key": "keyboard_shortcuts",
    "title": keyboard_card_title(),
    "subtitle": keyboard_card_subtitle(),
    "steps": [],
    "kind": "shortcuts",
}
WORKFLOWS.append(KEYBOARD_CARD)


# ---------------------------------------------------------------------------
# Painted card icon — geometric placeholder per workflow
# ---------------------------------------------------------------------------

class WorkflowIcon(QWidget):
    """96x96 painted icon. Magenta accent + monochrome lines that flip with theme."""

    SIZE = 96

    def __init__(self, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._mode = "dark"
        self.setFixedSize(QSize(self.SIZE, self.SIZE))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self.update()

    def _fg(self) -> QColor:
        """The line art. In Neutral it steps back to TEXT_DIM so the one
        accented element — which stays at full ACTION — is the thing the eye
        lands on. That is the handoff's pictogram rule: the distinction was
        never really hue, it was solid against outline."""
        from ui import neutral_styles as _n
        from ui.theme import by_mode
        return QColor(by_mode("#22211f", "#e6e6e6", _n.NM_TEXT_DIM, self._mode))

    def _card_surface(self) -> QColor:
        """The ground this pictogram is drawn ON — the WorkflowCard's fill.

        Kept in step with :meth:`WorkflowCard._apply_style`, which is the only
        place that colour is set, and pinned there by
        ``tests/test_cmyk_n_pictogram.py`` so the two cannot drift apart in
        silence. Needed because the Neutral drawing knocks a gap out around its
        solid shape, and a gap has to be painted in the colour behind it.
        """
        from ui import neutral_styles as _n
        from ui.theme import by_mode
        return QColor(by_mode("#ffffff", "#1a1a1a", _n.NM_BG_SURFACE, self._mode))

    def _draw_cmyk_n_neutral(self, p: QPainter, fg: QColor, accent: QColor,
                             s: int, r: int, cx: int, cy: int,
                             stroke: float) -> None:
        """The CMYK+N mark with the hue taken out of it.

        **WHY THIS ONE NEEDED A REDRAW AND NOT A RECOLOUR.** Every other
        pictogram in this dialog is line art with ONE accented element, which
        is the handoff's rule and the reason it survives a colourless theme
        untouched. This one is five filled drops in five different colours, and
        the handoff is explicit about that case:

            "The rule only works when the solid shape is unique in the frame.
            If any pictogram currently has two or more accented elements,
            redraw it first."

        Four of the five carry meaning in their hue — they are the process
        inks, named by colour. Turning them grey would have made four
        indistinguishable discs, so they become **four open rings**: the ring
        keeps the drop's size, its position and its overlap with its
        neighbours, and it is those positions that say which ink is which to
        anyone who knows the motif. What is lost is the naming, which the
        card's own title (*"Profiling a CMYK+N printer (extra inks)"*) carries
        anyway.

        **THE FIFTH SHAPE IS NOT ON THE SAME ORBIT, AND THAT IS THE WHOLE
        POINT.** It means *the extra ink*, and in the approved sketch it sat
        where the coloured artwork puts it: dead centre, at ring size. Rendered
        at the size this is actually seen — 96 px, not enlarged — that covers
        the middle and reduces the four rings to corner arcs, so the mark reads
        as one dark blob and the solid reads as simply the darkest of five
        inks. Moving it out of the pile is what fixes that: the four rings stay
        whole and legible as four, and the fifth is visibly not one of them.
        It still overlaps the group, because an extra ink is added TO the set
        rather than kept beside it.

        The gap knocked out around it is what makes it read as laid ON the
        four rather than tangled in them; without it the solid merges with
        every ring stroke it crosses.
        """
        gx = cx - int(s * 0.0625)          # the four-ring group, nudged left
        ex = cx + int(s * 0.1875)          # the extra ink, out of the pile
        o = r // 2                         # the drops' own offset, unchanged
        solid_r = int(r * 0.79)            # smaller than a ring: not a peer
        gap = stroke * 1.2

        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(fg, stroke))
        for dx, dy in ((-o, -o), (o, -o), (-o, o), (o, o)):
            p.drawEllipse(QRectF(gx + dx - r, cy + dy - r, 2 * r, 2 * r))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._card_surface())
        p.drawEllipse(QRectF(ex - solid_r - gap, cy - solid_r - gap,
                             2 * (solid_r + gap), 2 * (solid_r + gap)))
        p.setBrush(accent)
        p.drawEllipse(QRectF(ex - solid_r, cy - solid_r,
                             2 * solid_r, 2 * solid_r))

    def paintEvent(self, _ev: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fg = self._fg()
        accent = QColor(accent_for(SPEC_MAGENTA, self._mode))
        stroke = 2.4

        s = self.SIZE
        if self._key == "first_profile":
            # 5 nodes connected in a row, last one filled magenta
            cy = s / 2
            n = 5
            pad = 12
            step = (s - 2 * pad) / (n - 1)
            p.setPen(QPen(fg, stroke))
            for i in range(n - 1):
                x0 = pad + i * step
                x1 = pad + (i + 1) * step
                p.drawLine(int(x0), int(cy), int(x1), int(cy))
            for i in range(n):
                cx = pad + i * step
                r = 7 if i == n - 1 else 5
                if i == n - 1:
                    p.setBrush(accent)
                    p.setPen(Qt.PenStyle.NoPen)
                else:
                    p.setBrush(QColor(0, 0, 0, 0))
                    p.setPen(QPen(fg, stroke))
                p.drawEllipse(int(cx - r), int(cy - r), 2 * r, 2 * r)

        elif self._key == "calibrate_printer":
            # A stepped ramp — which is literally what a calibration chart is:
            # one ink channel walked from light to dark. Bars rise left to
            # right, the last one filled, so it reads as "bring the printer to
            # a known response" rather than as another sheet-of-patches icon.
            margin = 14
            bars = 6
            gap = 4
            usable = s - 2 * margin
            bw = (usable - gap * (bars - 1)) / bars
            base = s - margin
            p.setPen(QPen(fg, stroke))
            for i in range(bars):
                # Lowest bar a stub, tallest nearly the full height.
                frac = (i + 1) / bars
                h = max(6.0, usable * frac)
                x = margin + i * (bw + gap)
                if i == bars - 1:
                    p.setBrush(accent)
                    p.setPen(Qt.PenStyle.NoPen)
                else:
                    p.setBrush(QColor(0, 0, 0, 0))
                    p.setPen(QPen(fg, stroke))
                p.drawRoundedRect(QRectF(x, base - h, bw, h), 2, 2)

        elif self._key == "print_chart":
            # Sheet (rectangle) with a 4x6 patch grid; one accent patch
            margin = 14
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawRoundedRect(margin, margin, s - 2 * margin, s - 2 * margin, 4, 4)
            cols, rows = 6, 4
            cell_w = (s - 2 * margin - 8) / cols
            cell_h = (s - 2 * margin - 8) / rows
            ox = margin + 4
            oy = margin + 4
            p.setPen(Qt.PenStyle.NoPen)
            accent_cell = (2, 1)
            for r in range(rows):
                for c in range(cols):
                    x = ox + c * cell_w
                    y = oy + r * cell_h
                    if (r, c) == accent_cell:
                        p.setBrush(accent)
                    else:
                        col = QColor(fg)
                        col.setAlpha(110)
                        p.setBrush(col)
                    p.drawRect(int(x + 1), int(y + 1), int(cell_w - 2), int(cell_h - 2))

        elif self._key == "measure_existing":
            # Spectro head (rounded rectangle with notch) above a strip of patches.
            # Sized to leave a generous gap to the card title below.
            head_w, head_h = 50, 24
            head_x = (s - head_w) / 2
            head_y = 19
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawRoundedRect(int(head_x), int(head_y), head_w, head_h, 7, 7)
            # Aperture
            p.setBrush(accent)
            p.setPen(Qt.PenStyle.NoPen)
            ap = 7
            p.drawEllipse(int(s / 2 - ap / 2), int(head_y + head_h - 4), ap, ap)
            # Patches strip — integer dimensions keep every cell and gap uniform.
            n = 6
            cell = 12          # 12 * 6 = 72
            strip_w = n * cell  # 72
            strip_h = 18
            strip_y = 53
            pad = (s - strip_w) // 2  # 12
            patch_w = cell - 2  # 10 — leaves a 2 px gap to the next patch
            for i in range(n):
                if i == 2:
                    p.setBrush(accent)
                else:
                    col = QColor(fg)
                    col.setAlpha(110)
                    p.setBrush(col)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRect(pad + i * cell + 1, strip_y, patch_w, strip_h)
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawRect(pad, strip_y, strip_w, strip_h)

        elif self._key == "build_from_measurement":
            # Document glyph (folded corner) → arrow → cube. Tightened so the
            # whole composition fits within the 96 canvas with a clear bottom
            # margin (previous version overflowed past the right edge).
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            # Document
            dx, dy, dw, dh = 10, 13, 28, 52
            p.drawLine(dx, dy, dx + dw - 9, dy)
            p.drawLine(dx + dw - 9, dy, dx + dw, dy + 9)
            p.drawLine(dx + dw, dy + 9, dx + dw, dy + dh)
            p.drawLine(dx + dw, dy + dh, dx, dy + dh)
            p.drawLine(dx, dy + dh, dx, dy)
            p.drawLine(dx + dw - 9, dy, dx + dw - 9, dy + 9)
            p.drawLine(dx + dw - 9, dy + 9, dx + dw, dy + 9)
            # Arrow
            ax0 = dx + dw + 4
            ax1 = ax0 + 12
            ay = dy + dh / 2
            p.setPen(QPen(accent, stroke))
            p.drawLine(int(ax0), int(ay), int(ax1), int(ay))
            p.drawLine(int(ax1), int(ay), int(ax1 - 4), int(ay - 4))
            p.drawLine(int(ax1), int(ay), int(ax1 - 4), int(ay + 4))
            # Cube
            p.setPen(QPen(fg, stroke))
            csz = 20
            cx0 = ax1 + 4
            cy0 = int(ay - csz / 2)
            iso = 6
            p.drawRect(cx0, cy0, csz, csz)
            p.drawLine(cx0 + iso, cy0 - iso, cx0 + csz + iso, cy0 - iso)
            p.drawLine(cx0 + csz, cy0, cx0 + csz + iso, cy0 - iso)
            p.drawLine(cx0 + csz + iso, cy0 - iso,
                       cx0 + csz + iso, cy0 + csz - iso)
            p.drawLine(cx0 + csz, cy0 + csz, cx0 + csz + iso, cy0 + csz - iso)

        elif self._key == "refine":
            # Magnifying glass — refinement = inspecting + re-measuring outliers.
            # (Previous circular-arrow attempt had arrowhead-angle issues — this
            # geometry is foolproof and matches the analyse-then-re-measure flow.)
            import math
            lens_r = 22
            cx = s / 2 - 8
            cy = s / 2 - 8
            p.setPen(QPen(fg, stroke + 0.4))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawEllipse(int(cx - lens_r), int(cy - lens_r), 2 * lens_r, 2 * lens_r)
            # Handle — 45° line off the lower-right of the lens
            ang = math.radians(-45)
            hx0 = cx + lens_r * math.cos(ang)
            hy0 = cy - lens_r * math.sin(ang)
            hx1 = hx0 + 18
            hy1 = hy0 + 18
            p.setPen(QPen(fg, stroke + 1.6, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(int(hx0), int(hy0), int(hx1), int(hy1))
            # Magenta accent dot inside the lens — the outlier being inspected
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent)
            p.drawEllipse(int(cx - 5), int(cy - 5), 10, 10)

        elif self._key == "verify":
            # A ring with a magenta check mark — confirming a finished profile
            # still measures accurate.
            ring_r = 24
            cx = s / 2
            cy = s / 2
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawEllipse(int(cx - ring_r), int(cy - ring_r), 2 * ring_r, 2 * ring_r)
            p.setPen(QPen(accent, stroke + 1.8, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPolyline(*[
                QPointF(x, y)
                for x, y in ((cx - 12, cy), (cx - 3, cy + 10), (cx + 14, cy - 11))
            ])

        elif self._key == "two_pass":
            # Two cubes side by side, second one filled magenta — first profile
            # becomes the pre-conditioning base for a higher-quality second one.
            csz = 24
            gap = 10
            x0 = (s - (2 * csz + gap + 10)) / 2
            y0 = (s - csz) / 2 + 3
            # Cube 1 — outline
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawRect(int(x0), int(y0), csz, csz)
            p.drawLine(int(x0 + 5), int(y0 - 5), int(x0 + csz + 5), int(y0 - 5))
            p.drawLine(int(x0 + csz), int(y0), int(x0 + csz + 5), int(y0 - 5))
            p.drawLine(int(x0 + csz + 5), int(y0 - 5),
                       int(x0 + csz + 5), int(y0 + csz - 5))
            p.drawLine(int(x0 + csz), int(y0 + csz),
                       int(x0 + csz + 5), int(y0 + csz - 5))
            # Arrow between
            ay = y0 + csz / 2
            ax0 = x0 + csz + 7
            ax1 = x0 + csz + gap + 6
            p.setPen(QPen(accent, stroke, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(int(ax0), int(ay), int(ax1), int(ay))
            p.drawLine(int(ax1), int(ay), int(ax1 - 4), int(ay - 4))
            p.drawLine(int(ax1), int(ay), int(ax1 - 4), int(ay + 4))
            # Cube 2 — filled magenta
            x1 = x0 + csz + gap + 6
            p.setPen(QPen(accent, stroke))
            p.setBrush(accent)
            p.drawRect(int(x1), int(y0), csz, csz)
            # Iso depth lines for cube 2 — slightly faded
            faded = QColor(accent)
            faded.setAlpha(170)
            p.setPen(QPen(faded, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawLine(int(x1 + 5), int(y0 - 5), int(x1 + csz + 5), int(y0 - 5))
            p.drawLine(int(x1 + csz), int(y0), int(x1 + csz + 5), int(y0 - 5))
            p.drawLine(int(x1 + csz + 5), int(y0 - 5),
                       int(x1 + csz + 5), int(y0 + csz - 5))
            p.drawLine(int(x1 + csz), int(y0 + csz),
                       int(x1 + csz + 5), int(y0 + csz - 5))

        elif self._key == "improve_existing_profile":
            # Existing profile (filled grey cube) → arrow → improved profile
            # (outlined cube with magenta "+"). Distinct from two_pass which
            # uses two cubes both being internally produced; here the first
            # cube is the *given* input, not built in-app.
            csz = 24
            gap = 10
            x0 = (s - (2 * csz + gap + 10)) / 2
            y0 = (s - csz) / 2 + 3
            # Cube 1 — filled in fg colour (the seed profile you bring in)
            seed = QColor(fg)
            seed.setAlpha(180)
            p.setPen(QPen(fg, stroke))
            p.setBrush(seed)
            p.drawRect(int(x0), int(y0), csz, csz)
            faded = QColor(fg)
            faded.setAlpha(160)
            p.setPen(QPen(faded, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawLine(int(x0 + 5), int(y0 - 5), int(x0 + csz + 5), int(y0 - 5))
            p.drawLine(int(x0 + csz), int(y0), int(x0 + csz + 5), int(y0 - 5))
            p.drawLine(int(x0 + csz + 5), int(y0 - 5),
                       int(x0 + csz + 5), int(y0 + csz - 5))
            p.drawLine(int(x0 + csz), int(y0 + csz),
                       int(x0 + csz + 5), int(y0 + csz - 5))
            # Arrow
            ay = y0 + csz / 2
            ax0 = x0 + csz + 7
            ax1 = x0 + csz + gap + 6
            p.setPen(QPen(accent, stroke, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(int(ax0), int(ay), int(ax1), int(ay))
            p.drawLine(int(ax1), int(ay), int(ax1 - 4), int(ay - 4))
            p.drawLine(int(ax1), int(ay), int(ax1 - 4), int(ay + 4))
            # Cube 2 — outlined in accent, with a magenta "+" inside
            x1 = x0 + csz + gap + 6
            p.setPen(QPen(accent, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawRect(int(x1), int(y0), csz, csz)
            p.drawLine(int(x1 + 5), int(y0 - 5), int(x1 + csz + 5), int(y0 - 5))
            p.drawLine(int(x1 + csz), int(y0), int(x1 + csz + 5), int(y0 - 5))
            p.drawLine(int(x1 + csz + 5), int(y0 - 5),
                       int(x1 + csz + 5), int(y0 + csz - 5))
            p.drawLine(int(x1 + csz), int(y0 + csz),
                       int(x1 + csz + 5), int(y0 + csz - 5))
            # "+" mark — improvement
            cx2 = x1 + csz / 2
            cy2 = y0 + csz / 2
            arm = 5
            p.setPen(QPen(accent, stroke + 0.4, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.drawLine(int(cx2 - arm), int(cy2), int(cx2 + arm), int(cy2))
            p.drawLine(int(cx2), int(cy2 - arm), int(cx2), int(cy2 + arm))

        elif self._key == "check_visualise":
            # Isometric wireframe cube
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            cx, cy = s / 2, s / 2
            r = 30
            import math
            verts = [
                (cx, cy - r),               # top
                (cx + r * math.cos(math.radians(30)), cy - r * math.sin(math.radians(30))),  # right-top
                (cx + r * math.cos(math.radians(30)), cy + r * math.sin(math.radians(30))),  # right-bot
                (cx, cy + r),               # bottom
                (cx - r * math.cos(math.radians(30)), cy + r * math.sin(math.radians(30))),  # left-bot
                (cx - r * math.cos(math.radians(30)), cy - r * math.sin(math.radians(30))),  # left-top
            ]
            # Outer hex outline
            for i in range(6):
                a = verts[i]
                b = verts[(i + 1) % 6]
                p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            # 3 inner spokes from centre to alternating verts
            for idx in (0, 2, 4):
                v = verts[idx]
                p.drawLine(int(cx), int(cy), int(v[0]), int(v[1]))
            # Accent vertex
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent)
            v = verts[1]
            p.drawEllipse(int(v[0] - 5), int(v[1] - 5), 10, 10)

        elif self._key in ("scanner_profile", "printer_from_scan"):
            # Flatbed scanner: bed rectangle, an accent scan bar, content lines.
            # printer_from_scan: the content is a patch grid instead of lines —
            # the scanner is reading a chart, not a photo.
            margin = 16
            top = margin + 6
            h = s - 2 * margin - 12
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawRoundedRect(margin, top, s - 2 * margin, h, 6, 6)
            inner = margin + 10
            # Accent scan bar (the moving light) near the top of the bed
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(inner, top + 12, s - 2 * inner, 6, 2, 2)
            if self._key == "printer_from_scan":
                # 4x2 patch grid under the Profile-run bar
                p.setPen(QPen(fg, 1.6))
                p.setBrush(QColor(0, 0, 0, 0))
                gw = (s - 2 * inner - 6) / 4
                for r_ in range(2):
                    for c_ in range(4):
                        p.drawRect(int(inner + c_ * (gw + 2)),
                                   int(top + 28 + r_ * 14), int(gw), 10)
            else:
                # Two content lines below it
                p.setPen(QPen(fg, stroke))
                for k in range(2):
                    y = top + 30 + k * 12
                    x1 = s - inner - (12 if k == 1 else 0)
                    p.drawLine(inner, y, x1, y)

        elif self._key == "glossary":
            # Dictionary: a big "Aa" with an accent underline.
            f = QFont()
            f.setPixelSize(int(s * 0.42))
            f.setBold(True)
            p.setFont(f)
            p.setPen(QPen(fg, stroke))
            p.drawText(0, 0, s, s - 14, Qt.AlignmentFlag.AlignCenter, "Aa")
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(int(s * 0.30), s - 22, int(s * 0.40), 5, 2, 2)

        elif self._key == "getting_started":
            # B — "Interface map" (Knut's choice, #130 2026-07-28): ChromIQ's
            # own layout — masthead, options panel, preview — because that is
            # what the card opens by explaining.
            m = 12
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawRoundedRect(m, m, s - 2 * m, s - 2 * m, 5, 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(m + 3, m + 3, s - 2 * m - 6, 13, 3, 3)
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawLine(m + 26, m + 20, m + 26, s - m - 3)
            for i in range(4):
                y = m + 28 + i * 9
                p.drawLine(m + 7, y, m + 20, y)

        elif self._key == "main_actions":
            # B — "Branching routes" (Knut's choice): one starting point and
            # several ways on, which is the card's actual subject.
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            sx, sy = 20, s / 2
            for y in (26, 48, 70):
                path = QPainterPath(QPointF(sx, sy))
                path.cubicTo(46, sy, 50, y, 72, y)
                p.drawPath(path)
                p.drawEllipse(QRectF(72 - 6, y - 6, 12, 12))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent)
            p.drawEllipse(QRectF(sx - 9, sy - 9, 18, 18))

        elif self._key == "file_guide":
            # Folder guide (#125): a folder — accent tab, outlined body, two
            # document lines inside.
            margin = 14
            tab_w = int((s - 2 * margin) * 0.42)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(accent)
            p.drawRoundedRect(margin, margin + 6, tab_w, 12, 3, 3)
            p.setPen(QPen(fg, stroke))
            p.setBrush(QColor(0, 0, 0, 0))
            p.drawRoundedRect(margin, margin + 14, s - 2 * margin,
                              s - 2 * margin - 20, 6, 6)
            inner = margin + 10
            for k in range(2):
                y = margin + 30 + k * 12
                x1 = s - inner - (14 if k == 1 else 0)
                p.drawLine(inner, y, x1, y)

        elif self._key == "cmyk_n":
            # Extra-ink profiling: overlapping ink drops (C, M, Y, K + one
            # accent) — the many-ink idea at a glance.
            r = int(s * 0.20)
            cx, cy = s // 2, s // 2
            if self._mode == APPEARANCE_NEUTRAL:
                self._draw_cmyk_n_neutral(p, fg, accent, s, r, cx, cy, stroke)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                drops = [
                    (QColor(0, 174, 239, 200), -r // 2, -r // 2),   # cyan
                    (QColor(236, 0, 140, 200), r // 2, -r // 2),    # magenta
                    (QColor(255, 222, 23, 200), -r // 2, r // 2),   # yellow
                    (QColor(35, 31, 32, 200), r // 2, r // 2),      # black
                    (accent, 0, 0),                                 # accent extra ink
                ]
                for col, dx, dy in drops:
                    p.setBrush(col)
                    p.drawEllipse(cx + dx - r, cy + dy - r, 2 * r, 2 * r)

        elif self._key == "keyboard_shortcuts":
            # A keyboard: outlined body with a grid of small keys and one accent
            # key (the ⌘ modifier), matching the "modifier-first" shortcut rule.
            # The key size is derived from the space INSIDE the frame so the grid
            # always fits with margin (never spilling over the bottom edge).
            bx, by, bw, bh = s * 0.12, s * 0.28, s * 0.76, s * 0.44
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(fg, stroke))
            p.drawRoundedRect(QRectF(bx, by, bw, bh), 6, 6)
            cols, rows = 5, 3
            inset, gap = s * 0.055, s * 0.028
            k = min((bw - 2 * inset - (cols - 1) * gap) / cols,
                    (bh - 2 * inset - (rows - 1) * gap) / rows)   # fits both axes
            grid_w = cols * k + (cols - 1) * gap
            grid_h = rows * k + (rows - 1) * gap
            ox = bx + (bw - grid_w) / 2                            # centre the grid
            oy = by + (bh - grid_h) / 2
            p.setPen(QPen(fg, 1.4))
            for row in range(rows):
                for col in range(cols):
                    kx, ky = ox + col * (k + gap), oy + row * (k + gap)
                    # Accent the bottom-left key (stands in for ⌘).
                    p.setBrush(accent if (row == rows - 1 and col == 0)
                               else Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(QRectF(kx, ky, k, k), 2, 2)

        elif self._key == "patch_set_editor":
            # A pencil over a row of patches — the only "authoring" icon in the
            # set, which is right: this is the one card about MAKING a patch
            # set rather than measuring or inspecting one. Chosen by Sebastian
            # from six mock-ups, 2026-08-25.
            p.setPen(QPen(fg, stroke)); p.setBrush(QColor(0, 0, 0, 0))
            for i in range(3):
                p.drawRoundedRect(QRectF(16 + i * 22, 60, 18, 18), 2, 2)
            p.setBrush(accent); p.setPen(QPen(accent, stroke))
            p.drawPolygon(QPolygonF([QPointF(38, 40), QPointF(74, 14),
                                     QPointF(82, 25), QPointF(46, 51)]))
            p.setBrush(QColor(0, 0, 0, 0)); p.setPen(QPen(fg, stroke))
            p.drawPolygon(QPolygonF([QPointF(38, 40), QPointF(46, 51),
                                     QPointF(30, 54)]))

        elif self._key == "spot_read":
            # A crosshair centred on ONE patch — the difference from
            # "measure_existing" (a strip) said in one shape. Chosen by
            # Sebastian from six mock-ups, 2026-08-25.
            p.setPen(QPen(fg, stroke)); p.setBrush(QColor(0, 0, 0, 0))
            p.drawRoundedRect(QRectF(20, 20, 56, 56), 3, 3)
            p.setPen(QPen(fg, 1.6))
            p.drawLine(48, 26, 48, 42); p.drawLine(48, 54, 48, 70)
            p.drawLine(26, 48, 42, 48); p.drawLine(54, 48, 70, 48)
            p.setBrush(accent); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(48, 48), 6, 6)

        elif self._key == "patch_cube":
            # A wireframe cube holding a CLOUD OF SEPARATE POINTS. It must not
            # be confusable with "check_visualise" (12), which draws a SOLID
            # hexagon: that card shows a gamut hull, this one shows individual
            # patches.
            #
            # PAINTED BACK TO FRONT, AND THAT ORDER IS THE POINT. Drawn with
            # all twelve edges at one weight this is a Necker cube — the eye
            # cannot fix which corner is nearest and the shape flips while you
            # look at it (Sebastian: *"the shape looks confusing"*). Two things
            # settle it, and both are depth cues:
            #   1. the three edges meeting at the BACK-BOTTOM-LEFT corner are
            #      hidden behind the solid, so they are faded to a third;
            #   2. the points sit INSIDE the box, so the near edges are drawn
            #      last, over them. Painting the cloud last instead makes a
            #      patch cover the front upright and read as stuck to the
            #      outside of the glass.
            # y0 = 20, not 30: the drawn shape runs from the top of the BACK
            # square to the bottom of the FRONT one, i.e. 56 px of the 96, so
            # centring it means (96-56)/2 = 20. At 30 it sat 10 px low and read
            # as sagging in the card (Sebastian, 2026-08-25). Horizontally it
            # already spans 20..76, centred.
            x0, y0, w0, dep = 20, 20, 40, 16
            f = [(x0, y0 + dep), (x0 + w0, y0 + dep),
                 (x0 + w0, y0 + dep + w0), (x0, y0 + dep + w0)]
            b = [(x0 + dep, y0), (x0 + dep + w0, y0),
                 (x0 + dep + w0, y0 + w0), (x0 + dep, y0 + w0)]
            visible = [(f[0], f[1]), (f[1], f[2]), (f[2], f[3]), (f[3], f[0]),
                       (b[0], b[1]), (b[1], b[2]),
                       (f[0], b[0]), (f[1], b[1]), (f[2], b[2])]
            hidden = [(b[3], b[0]), (b[3], b[2]), (b[3], f[3])]

            def _edges(pen, edges):
                p.setPen(pen); p.setBrush(QColor(0, 0, 0, 0))
                for (ea, eb) in edges:
                    p.drawLine(int(ea[0]), int(ea[1]), int(eb[0]), int(eb[1]))

            faded = QColor(fg); faded.setAlphaF(0.32)
            _edges(QPen(faded, 2.0), hidden)              # furthest away
            # The cloud is positioned RELATIVE to the box, not in absolute
            # canvas coordinates — moving the cube and leaving these behind
            # left the points sitting in its lower third.
            for dx, dy, cr in ((18, 28, 3.0), (34, 20, 3.2),
                               (24, 40, 2.8), (44, 34, 3.0)):
                p.setBrush(QColor(0, 0, 0, 0)); p.setPen(QPen(fg, 1.8))
                p.drawEllipse(QPointF(x0 + dx, y0 + dy), cr, cr)
            p.setBrush(accent); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x0 + 36, y0 + 32), 5.0, 5.0)   # in the volume
            _edges(QPen(fg, 2.3), visible)                # nearest the viewer

        p.end()


# ---------------------------------------------------------------------------
# Card widget (clickable)
# ---------------------------------------------------------------------------

class WorkflowCard(QFrame):
    """Clickable workflow tile — icon, title, one-line subtitle."""

    clicked = pyqtSignal(str)  # emits workflow key

    def __init__(self, workflow: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = workflow["key"]
        self._mode = "dark"
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Height is set uniformly for all cards by _build_menu_page via
        # required_height() — translated titles/subtitles wrap to more lines
        # than the English originals, so a hard-coded box would squeeze them
        # into the icon.
        self.setMinimumWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(8)

        icon_row = QHBoxLayout()
        icon_row.setContentsMargins(0, 0, 0, 0)
        self._icon = WorkflowIcon(self._key, self)
        icon_row.addWidget(self._icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(icon_row)

        self._title = QLabel(workflow["title"], self)
        self._title.setWordWrap(True)
        f = QFont()
        f.setPixelSize(14)
        f.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(f)
        self._title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._title)

        self._subtitle = QLabel(workflow["subtitle"], self)
        self._subtitle.setWordWrap(True)
        sf = QFont()
        sf.setPixelSize(11)
        self._subtitle.setFont(sf)
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._subtitle)
        layout.addStretch(1)

        self._apply_style()

    def required_height(self, text_width: int) -> int:
        """Height this card needs at `text_width` for its wrapped labels —
        margins + icon + spacings + title + subtitle (+ stretch floor)."""
        m = self.layout().contentsMargins()
        spacing = self.layout().spacing()

        # Font metrics, not heightForWidth(): the latter returns -1 until the
        # widget is polished, which silently collapses the computed height.
        def _wrapped_h(label: QLabel) -> int:
            fm = QFontMetrics(label.font())
            return fm.boundingRect(
                0, 0, text_width, 4000,
                Qt.TextFlag.TextWordWrap, label.text(),
            ).height()

        # minimumHeight, not height()/sizeHint(): before the first layout
        # pass height() is the default widget size, and a plain QWidget's
        # sizeHint() is invalid — setFixedSize() only pins min/max.
        icon_h = self._icon.minimumHeight()
        # +12: QLabel renders wrapped text slightly taller than raw
        # boundingRect metrics (leading / style margins).
        return (m.top() + icon_h + spacing + _wrapped_h(self._title)
                + spacing + _wrapped_h(self._subtitle) + m.bottom() + 12)

    def set_appearance(self, mode: str) -> None:
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        self._icon.set_appearance(self._mode)
        self._apply_style()

    def _apply_style(self) -> None:
        from ui import neutral_styles as _n
        from ui.theme import by_mode
        bg, border, text, sub = by_mode(
            ("#ffffff", "#d0ccc6", "#22211f", "#7a7570"),
            ("#1a1a1a", "#333333", "#e6e6e6", "#8a8a8a"),
            # A card is a raised SURFACE; its subtitle is tertiary ink at
            # 8.13:1, not a pale grey — nothing that works may be faint.
            (_n.NM_BG_SURFACE, _n.NM_BORDER, _n.NM_TEXT_MAIN, _n.NM_TEXT_FAINT),
            self._mode)
        # THE HOVER EDGE GOES THROUGH `accent_for` LIKE EVERY OTHER ACCENT.
        # It was raw SPEC_MAGENTA, so a card in Neutral grew a magenta outline
        # the moment the pointer touched it — the owner's report, 2026-09-02:
        # *"in neutral help cards still get a magenta outline when hovered"*.
        # The resting card is themed correctly a few lines up and the dialog's
        # own checkbox accents a few hundred lines down are routed properly
        # too, which is what makes this a missed site rather than a decision.
        # A hue in an INTERACTION STATE is painted at a different moment from
        # the resting widget, which is why every pixel census so far walked
        # straight past it.
        hover_border = (accent_for(SPEC_MAGENTA, self._mode)
                        if self._hover else border)
        self.setStyleSheet(
            f"""
            WorkflowCard {{
                background: {bg};
                border: 1.5px solid {hover_border};
                border-radius: 10px;
            }}
            WorkflowCard QLabel {{
                background: transparent;
                border: none;
            }}
            """
        )
        self._title.setStyleSheet(f"color: {text};")
        self._subtitle.setStyleSheet(f"color: {sub};")

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self._apply_style()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self._apply_style()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Tab number badge
# ---------------------------------------------------------------------------

class StepBadge(QLabel):
    """Step-number chip — the number is the step count; colour = tab.

    Optional steps render outlined (transparent fill + coloured ring) so they
    read as suggestions rather than required steps in the sequence.
    """

    def __init__(
        self,
        step_number: int,
        tab_index_1based: int,
        parent: QWidget | None = None,
        *,
        optional: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(str(step_number))
        color = TAB_COLORS[(tab_index_1based - 1) % len(TAB_COLORS)]
        f = QFont()
        f.setPixelSize(14)
        f.setWeight(QFont.Weight.Bold)
        self.setFont(f)
        if optional:
            # Outlined: ring in the tab colour, text in the tab colour,
            # transparent fill — visually quieter than a filled chip.
            self.setStyleSheet(
                f"background: transparent; color: {color}; "
                f"border-radius: 15px; border: 2px solid {color};"
            )
        else:
            self.setStyleSheet(
                f"background: {color}; color: #0a0a0a; "
                f"border-radius: 15px; border: none;"
            )


# ---------------------------------------------------------------------------
# A note under a step
# ---------------------------------------------------------------------------

class StepNote(QWidget):
    """The deeper explanation under a step, closed until it is asked for.

    Knut, 2026-09-06: *"A user should be guided with simple steps, and given
    the more detailed explanations as notes for a deeper understanding, if the
    user decides to want that."* Both halves matter. The step stays short, so
    the card can be followed; the reasoning is still on the card, one click
    away, so nothing had to be deleted to get there.

    It is a button, not a clickable label, so it is reachable by Tab and opens
    on Space or Return like every other control in the dialog.
    """

    #: Same triangles as `CollapsibleGroupBox`, for the same reason: the small
    #: ▸ / ▾ do not read as an open/close affordance (Knut).
    CLOSED = "▶  "
    OPEN = "▼  "

    def __init__(self, heading: str, body: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._heading = heading
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 0)
        v.setSpacing(2)

        self._btn = QPushButton(self.CLOSED + heading, self)
        self._btn.setCheckable(True)
        self._btn.setFlat(True)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setObjectName("welcome_note_head")
        hf = QFont()
        hf.setPixelSize(12)
        hf.setBold(True)
        self._btn.setFont(hf)
        # A BOUND METHOD. Never a lambda capturing `self` on a signal a child
        # of this widget emits — see CLAUDE.md, ui/fade_scroll.py.
        self._btn.toggled.connect(self._on_toggled)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self._btn)
        head.addStretch(1)
        v.addLayout(head)

        self._body = QLabel(body, self)
        self._body.setWordWrap(True)
        bf = QFont()
        bf.setPixelSize(12)
        self._body.setFont(bf)
        self._body.setObjectName("welcome_note_body")
        self._body.setContentsMargins(16, 0, 0, 0)
        self._body.setVisible(False)
        v.addWidget(self._body)

    # ------------------------------------------------------------------
    def _on_toggled(self, checked: bool) -> None:
        self._btn.setText((self.OPEN if checked else self.CLOSED)
                          + self._heading)
        self._body.setVisible(bool(checked))

    def is_open(self) -> bool:
        return self._btn.isChecked()

    def set_open(self, opened: bool) -> None:
        self._btn.setChecked(bool(opened))

    def heading(self) -> str:
        return self._heading

    def body_text(self) -> str:
        return self._body.text()


# ---------------------------------------------------------------------------
# Welcome dialog
# ---------------------------------------------------------------------------

class WelcomeDialog(QDialog):
    """Welcome menu + per-workflow instructions."""

    def __init__(
        self,
        settings: "AppSettings",
        parent: QWidget | None = None,
        initial_mode: str = "dark",
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        from ui.theme import accept_mode
        self._mode = accept_mode(initial_mode)
        self.setWindowTitle(tr("Welcome to ChromIQ"))
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setMinimumSize(870, 660)
        self._cards: list[WorkflowCard] = []
        self._current_card_key: str = ""      # which card the Print button prints
        self._build_ui()
        self.set_appearance(self._mode)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(16)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_menu_page())
        self._stack.addWidget(self._build_detail_page())
        self._stack.currentChanged.connect(self._on_page_changed)
        outer.addWidget(self._stack, stretch=1)

        # Work-in-progress disclaimer. Persistent across both pages; small,
        # italic, dimmed text — visible but not noisy.
        self._wip_note = QLabel(
            tr("These guides are still being polished — some details may not "
            "be fully accurate yet. When in doubt, trust what you see in "
            "the app over what you read here."),
            self,
        )
        self._wip_note.setObjectName("welcome_wip_note")
        self._wip_note.setWordWrap(True)
        self._wip_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wip_font = QFont()
        wip_font.setPixelSize(11)
        wip_font.setItalic(True)
        self._wip_note.setFont(wip_font)
        outer.addWidget(self._wip_note)

        # Footer — shared across both pages. Back button only shows on detail.
        # Three equal-width thirds so the support link sits on the DIALOG's
        # centre line, not merely midway through the leftover space (the
        # startup checkbox is wider than Close, which pushed a stretch-based
        # centring visibly off — Basti).
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        _left = QWidget(self)
        _left_l = QHBoxLayout(_left)
        _left_l.setContentsMargins(0, 0, 0, 0)
        self._show_cb = QCheckBox(tr("Show this on startup"), _left)
        self._show_cb.setChecked(bool(self._settings.get("show_welcome_dialog", True)))
        self._show_cb.toggled.connect(
            lambda v: self._settings.set("show_welcome_dialog", bool(v))
        )
        _left_l.addWidget(self._show_cb)
        _left_l.addStretch(1)
        # Quiet support link — the classic tucked-away spot: only people who
        # open the help find it, so it never feels pushy (Basti). Opens the
        # Ko-fi page in the browser.
        _mid = QWidget(self)
        _mid_l = QHBoxLayout(_mid)
        _mid_l.setContentsMargins(0, 0, 0, 0)
        self._support_btn = QPushButton(tr("♥ Support ChromIQ"), _mid)
        self._support_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._support_btn.setFlat(True)
        self._support_btn.setToolTip(tr(
            "ChromIQ is free and always will be. If it saves you time or "
            "ink, a coffee on Ko-fi is a kind way to say thanks — completely "
            "optional, and the app stays fully featured either way."))
        self._support_btn.clicked.connect(self._open_support_page)
        _mid_l.addStretch(1)
        _mid_l.addWidget(self._support_btn)
        _mid_l.addStretch(1)
        _right = QWidget(self)
        _right_l = QHBoxLayout(_right)
        _right_l.setContentsMargins(0, 0, 0, 0)
        _right_l.addStretch(1)
        # Print the card you are reading (#164, Knut: *"it would be possible to
        # print a currently viewed help card via normal print dialog (which also
        # would allow saving as pdf) … for example printing the keyboard
        # shortcuts."*). On the detail page only — there is nothing to print
        # while the menu of cards is showing.
        self._pdf_btn = QPushButton(tr("Save as PDF…"), _right)
        self._pdf_btn.setToolTip(tr(
            "Writes the help card you are reading to a PDF file you name — the "
            "help card's own title is filled in for you. Handy for keeping the "
            "keyboard shortcuts on a tablet, or mailing a workflow to someone."))
        self._pdf_btn.clicked.connect(self._save_current_card_pdf)
        self._pdf_btn.setVisible(False)
        _right_l.addWidget(self._pdf_btn)
        self._print_btn = QPushButton(tr("Print…"), _right)
        self._print_btn.setToolTip(tr(
            "Prints the help card you are reading — handy for the keyboard "
            "shortcuts, or a workflow to follow at the printer. Your usual "
            "print window opens, so you can choose the printer, the paper and "
            "how many copies. To see the pages first, or to keep them, use "
            "“Save as PDF…” beside this button."))
        self._print_btn.clicked.connect(self._print_current_card)
        self._print_btn.setVisible(False)
        _right_l.addWidget(self._print_btn)
        self._back_btn = QPushButton(tr("← Back"), _right)
        self._back_btn.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        self._back_btn.setVisible(False)
        _right_l.addWidget(self._back_btn)
        self._close_btn = QPushButton(tr("Close"), _right)
        self._close_btn.clicked.connect(self.accept)
        _right_l.addWidget(self._close_btn)
        self._footer_left = _left
        self._footer_mid = _mid
        self._footer_right = _right
        for _w in (_left, _mid, _right):
            footer.addWidget(_w, 1)      # equal thirds → true centre line
        outer.addLayout(footer)
        self._balance_footer()

    def _balance_footer(self) -> None:
        """Keep the centre line true WITHOUT starving the buttons.

        `addWidget(_w, 1)` three times hands each cell exactly a third of the
        footer, and a third is not enough for four buttons. A QHBoxLayout given
        less room than the sum of its items' minimums does not shrink them
        tidily, it lets them clip — so "Save as PDF…" painted as `ave as PDF.`
        **in English** at v4.3.0-beta.29, losing its first letter and its
        ellipsis, and Ukrainian lost characters off both ends of two buttons
        (measured 2026-09-21: `Зберегти як PDF…` 24 px short, `Роздрукувати…`
        8 px short). The equal thirds were about the Support link in the middle
        sitting on the window's true centre, and that survives here: both side
        cells are given the SAME minimum, so the middle stays centred, and the
        minimum is the wider side's real need rather than an arbitrary third.

        Called whenever the buttons change visibility, because what the right
        cell needs depends on how many of them are showing.

        **ALL THREE CELLS, NOT TWO.** The first cut of this gave the two side
        cells their room and said nothing about the middle, which simply moved
        the starvation one cell over: the Ko-fi link came out as `дтримка Chr`
        with both ends outside its frame, photographed within the hour. Three
        cells and a window minimum wide enough for all three is the whole fix;
        anything less just chooses which control gets cut.
        """
        try:
            side = max(self._footer_left.sizeHint().width(),
                       self._footer_right.sizeHint().width())
            mid = self._footer_mid.sizeHint().width()
            self._footer_left.setMinimumWidth(side)
            self._footer_right.setMinimumWidth(side)
            self._footer_mid.setMinimumWidth(mid)
            # …and the window has to be able to HOLD all three, or the layout is
            # back to choosing a victim. `setMinimumWidth` only ever raises the
            # floor here, so a card that already needs a wider window keeps it.
            want = 2 * side + mid + 48
            if self.minimumWidth() < want:
                self.setMinimumWidth(want)
        except Exception:      # noqa: BLE001 — sizing must never raise
            pass

    def _on_page_changed(self, index: int) -> None:
        self._back_btn.setVisible(index == 1)
        self._print_btn.setVisible(index == 1)
        self._pdf_btn.setVisible(index == 1)
        self._balance_footer()

    def _save_current_card_pdf(self) -> None:
        """Write the card on screen to a PDF the user names (#164)."""
        wf = next((w for w in WORKFLOWS if w["key"] == self._current_card_key),
                  None)
        if wf is None:
            return
        try:
            from ui.help_card_print import save_card_pdf
            path = save_card_pdf(
                wf, self, lang=str(self._settings.get("language", "en") or "en"))
        except Exception:      # noqa: BLE001 — a failed save never kills Help
            log.warning("could not save the help card as a PDF", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            self.raise_()
            warn(
                self, tr("Couldn't save this help card"),
                tr("Something went wrong while writing the PDF, so no file was "
                   "saved. You can still read the help card here on screen."))
            return
        # The save panel takes focus with it when it closes; come back to front.
        self.raise_()
        self.activateWindow()
        if path is not None:
            log.info("help card saved as %s", path)

    def _print_current_card(self) -> None:
        """Send the card on screen to the print dialog (#164).

        Every card kind is handled — see :mod:`ui.help_card_print`, which builds
        the printable HTML for the glossary rows, the step lists and the
        Getting-Started diagram as well as for the cards that are already HTML.
        """
        wf = next((w for w in WORKFLOWS if w["key"] == self._current_card_key),
                  None)
        if wf is None:
            return
        try:
            from ui.help_card_print import print_card
            print_card(wf, self,
                       lang=str(self._settings.get("language", "en") or "en"))
            # BRING THE HELP WINDOW BACK. Closing the print panel hands focus to
            # the main window, not to us, so the card the user was reading
            # disappears behind it and they have to reopen Help to get back to
            # it (#164, Knut). Both ways out of the panel — printed and
            # cancelled — leave it hidden, so this runs either way and the
            # return value is deliberately not read here.
            self.raise_()
            self.activateWindow()
        except Exception:      # noqa: BLE001 — a failed print never kills Help
            # …but it must not be SILENT either. Clicking Print… and getting
            # absolutely nothing back, not even a message, is the worst of the
            # three possible outcomes.
            log.warning("could not print the help card", exc_info=True)
            from PyQt6.QtWidgets import QMessageBox
            warn(
                self, tr("Couldn't print this help card"),
                tr("Something went wrong while preparing this help card for "
                   "printing, so nothing was sent to your printer.\n\n"
                   "You can still reach the same information here on screen. "
                   "If it keeps happening, the log (Help → Show log file) has "
                   "the details."))

    def _open_support_page(self) -> None:
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/itsab1989"))

    # ------------------------------------------------------------------
    def _build_menu_page(self) -> QWidget:
        page = QWidget(self)
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        # Heading
        heading = self._make_heading()
        v.addWidget(heading)

        self._subtitle = QLabel(tr("What would you like to do?"), page)
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        sf = QFont()
        sf.setPixelSize(15)
        self._subtitle.setFont(sf)
        v.addWidget(self._subtitle)

        # Card grid — 3 columns. Layout adapts to the workflow count:
        #   • 6 cards: 3+3
        #   • 7 cards: 3+3+1 (last centred)
        #   • 8 cards: 3+3+2 (last row at cols 0 and 2, col 1 empty for
        #     symmetry — mirrors the centred-bottom feel of the 7-card case)
        # Wrapped in a FadeScrollArea so the dialog can be shorter than the
        # full grid height; users scroll to reach lower workflows and the
        # edges fade to dialog bg instead of being cut by a hard line.
        grid_host = QWidget(page)
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 8, 12, 16)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        # 3-column grid. Full rows fill left-to-right; a partial final row is
        # centred (1 card → middle column; 2 cards → cols 0 and 2). Works for any
        # card count — a full last row (e.g. 9 cards) is just three clean rows.
        n_cards = len(WORKFLOWS)
        rem = n_cards % 3
        full_count = n_cards - rem
        last_row = full_count // 3
        for i, wf in enumerate(WORKFLOWS):
            card = WorkflowCard(wf, grid_host)
            card.clicked.connect(self._on_card_clicked)
            self._cards.append(card)
            if i < full_count:
                grid.addWidget(card, i // 3, i % 3)
            elif rem == 1:
                grid.addWidget(card, last_row, 1)
            else:  # rem == 2 → cols 0 and 2, leaving the middle empty
                grid.addWidget(card, last_row, 0 if i == full_count else 2)

        # Uniform tile height that fits the tallest translated card at the
        # narrowest card width the minimum dialog size allows (~205px of
        # label width at the 870px minimum dialog size, minus slack).
        text_w = 200
        tile_h = max(190, max(c.required_height(text_w) for c in self._cards))
        for c in self._cards:
            c.setFixedHeight(tile_h)

        self._menu_scroll = FadeScrollArea(page, surface="dialog")
        self._menu_scroll.setWidget(grid_host)
        self._menu_scroll.setWidgetResizable(True)
        self._menu_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._menu_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        v.addWidget(self._menu_scroll, stretch=1)
        return page

    # ------------------------------------------------------------------
    def _build_detail_page(self) -> QWidget:
        page = QWidget(self)
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(12)

        self._detail_title = QLabel("", page)
        tf = QFont()
        tf.setFamilies(["Instrument Serif", "Georgia", "Times New Roman", "serif"])
        tf.setPixelSize(32)
        tf.setWeight(QFont.Weight.Normal)
        self._detail_title.setFont(tf)
        self._detail_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        v.addWidget(self._detail_title)

        self._detail_subtitle = QLabel("", page)
        self._detail_subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._detail_subtitle.setWordWrap(True)
        ssf = QFont()
        ssf.setPixelSize(13)
        self._detail_subtitle.setFont(ssf)
        v.addWidget(self._detail_subtitle)

        # Steps in a scroll area
        self._steps_host = QWidget(page)
        self._steps_layout = QVBoxLayout(self._steps_host)
        self._steps_layout.setContentsMargins(20, 16, 20, 16)
        self._steps_layout.setSpacing(14)

        self._detail_scroll = FadeScrollArea(page, surface="dialog")
        self._detail_scroll.setWidget(self._steps_host)
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        v.addWidget(self._detail_scroll, stretch=1)

        return page

    # ------------------------------------------------------------------
    def _make_heading(self) -> QWidget:
        """Custom-painted 'Welcome to ChromIQ' wordmark with magenta IQ."""

        class _Heading(QWidget):
            def __init__(self, dialog: "WelcomeDialog") -> None:
                super().__init__(dialog)
                self._dialog = dialog
                self.setFixedHeight(72)

            def paintEvent(self, _ev):
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

                font_r = QFont()
                font_r.setFamilies(["Instrument Serif", "Georgia", "Times New Roman", "serif"])
                font_r.setPixelSize(44)
                font_r.setWeight(QFont.Weight.Normal)

                font_i = QFont()
                font_i.setFamilies(["Instrument Serif", "Georgia", "Times New Roman", "serif"])
                font_i.setPixelSize(44)
                font_i.setWeight(QFont.Weight.Bold)
                font_i.setItalic(True)

                fm_r = QFontMetricsF(font_r)
                fm_i = QFontMetricsF(font_i)
                # THREE RUNS, NOT TWO. The greeting and "Chrom" used to be
                # drawn as one string in one colour, so the sixth brand site
                # physically could not follow the masthead when "Chrom" was
                # given its own value: brightening it here would have greyed
                # the greeting with it. Only the greeting translates; "Chrom"
                # and "IQ" are the mark and never do.
                text_hi  = tr("Welcome to") + " "
                text_ch  = "Chrom"
                text_iq  = "IQ"
                whi  = fm_r.horizontalAdvance(text_hi)
                wch  = fm_r.horizontalAdvance(text_ch)
                wiq  = fm_i.horizontalAdvance(text_iq)
                total = whi + wch + wiq - 1
                x_start = (self.width() - total) / 2
                baseline = (self.height() + fm_r.ascent() - fm_r.descent()) / 2

                # THE WORDMARK. On screen the magenta goes: "Chrom" in
                # TEXT_FAINT and "IQ" in TEXT_MAIN, which the italic already
                # separates by more than the magenta was — measured at 2.55:1
                # on this frame. `ui/splash.py` made the same change; this is
                # the sixth brand site, and it is a SCREEN one, so the PDF
                # wordmark is untouched.
                from ui import neutral_styles as _n
                from ui.masthead_header import _NEUTRAL_WORDMARK
                from ui.theme import by_mode
                mode = self._dialog._mode
                # The greeting is dialog text and keeps the value it always
                # had, in all three appearances - this split moves no pixel of
                # Light or Dark.
                greeting = by_mode("#22211f", "#ffffff", _n.NM_TEXT_FAINT, mode)
                # "Chrom" is the mark, and in Neutral it reads from the
                # masthead's brand value so this site cannot drift from the
                # masthead and the splash again.
                chrom = by_mode("#22211f", "#ffffff", _NEUTRAL_WORDMARK, mode)
                p.setFont(font_r)
                p.setPen(QColor(greeting))
                p.drawText(int(x_start), int(baseline), text_hi)
                p.setPen(QColor(chrom))
                p.drawText(int(x_start + whi), int(baseline), text_ch)
                p.setFont(font_i)
                p.setPen(QColor(by_mode(SPEC_MAGENTA, SPEC_MAGENTA,
                                        _n.NM_TEXT_MAIN, mode)))
                p.drawText(int(x_start + whi + wch - 1), int(baseline), text_iq)
                p.end()

        self._heading = _Heading(self)
        return self._heading

    # ------------------------------------------------------------------
    def _on_card_clicked(self, key: str) -> None:
        wf = next((w for w in WORKFLOWS if w["key"] == key), None)
        if wf is None:
            return
        self._current_card_key = key
        self._detail_title.setText(wf["title"])
        self._detail_subtitle.setText(wf["subtitle"])
        # Clear previous step rows
        while self._steps_layout.count():
            item = self._steps_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                # Hide BEFORE deleteLater: a removed widget stays parented (and
                # painting, on top of the next card's rows) until the deferred
                # delete runs — which never happens outside a running event
                # loop, and even inside one may land after the next repaint.
                w.hide()
                w.deleteLater()
        if wf.get("kind") == "glossary":
            # Alphabetical term/definition rows — no step badges (Knut, #108).
            for term, definition in sorted(GLOSSARY,
                                           key=lambda e: e[0].lower()):
                self._steps_layout.addWidget(self._make_glossary_row(
                    term, definition))
        elif wf.get("kind") in ("files", "richtext", "shortcuts",
                                "getting_started", "main_actions"):
            # The folder guide (#125/#126) and the keyboard-shortcuts card render
            # as HTML tables (Knut); the CMYK+N card is a flowing text page.
            if wf.get("kind") == "files":
                from ui.file_guide import file_guide_html
                body = QLabel(file_guide_html(), self._steps_host)
                body.setTextFormat(Qt.TextFormat.RichText)
            elif wf.get("kind") == "getting_started":
                # One widget per chapter, so the index — one numbered LINK
                # per chapter (Knut, beta.4) — can scroll straight to the
                # chapter it names via ensureWidgetVisible.
                from ui.getting_started import getting_started_sections
                self._gs_chapter_widgets = {}
                bf0 = QFont()
                bf0.setPixelSize(13)
                for key, block in getting_started_sections():
                    lbl = QLabel(block, self._steps_host)
                    lbl.setTextFormat(Qt.TextFormat.RichText)
                    lbl.setFont(bf0)
                    lbl.setWordWrap(True)
                    lbl.setTextInteractionFlags(
                        Qt.TextInteractionFlag.TextSelectableByMouse
                        | Qt.TextInteractionFlag.LinksAccessibleByMouse)
                    lbl.setObjectName("welcome_step_body")
                    lbl.linkActivated.connect(self._on_gs_index_link)
                    if key is not None:
                        self._gs_chapter_widgets[key] = lbl
                    self._steps_layout.addWidget(lbl)
                    if key == "workflow":
                        img = self._gs_workflow_diagram_label()
                        if img is not None:
                            self._steps_layout.addWidget(img)
                self._steps_layout.addStretch(1)
                self._apply_detail_text_colors()
                self._stack.setCurrentIndex(1)
                return
            elif wf.get("kind") == "main_actions":
                from ui.main_actions import main_actions_html
                body = QLabel(main_actions_html(), self._steps_host)
                body.setTextFormat(Qt.TextFormat.RichText)
            elif wf.get("kind") == "shortcuts":
                from ui.keyboard_help import keyboard_shortcuts_html
                body = QLabel(keyboard_shortcuts_html(), self._steps_host)
                body.setTextFormat(Qt.TextFormat.RichText)
            else:
                # A prose card whose list can be made a real <ol> gets one on
                # screen too — the printed card and this one must not differ
                # (#164). `numbered_prose_html` returns None when the shape is
                # not there, and then this is the plain QLabel it always was.
                rich = numbered_prose_html(str(wf.get("body") or ""))
                if rich:
                    body = QLabel(rich, self._steps_host)
                    body.setTextFormat(Qt.TextFormat.RichText)
                else:
                    body = QLabel(wf["body"], self._steps_host)
            bf = QFont()
            bf.setPixelSize(13)
            body.setFont(bf)
            body.setWordWrap(True)
            body.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            body.setObjectName("welcome_step_body")
            self._steps_layout.addWidget(body)
        else:
            # Build new rows. Steps are (tab_idx, text) or
            # (tab_idx, text, optional).
            for i, step in enumerate(wf["steps"], start=1):
                tab_idx, text = step[0], step[1]
                optional = bool(step[2]) if len(step) > 2 else False
                notes = tuple(step[3]) if len(step) > 3 else ()
                row = self._make_step_row(i, tab_idx, text, optional=optional,
                                          notes=notes)
                self._steps_layout.addWidget(row)
        self._steps_layout.addStretch(1)
        self._apply_detail_text_colors()
        self._stack.setCurrentIndex(1)

    # ------------------------------------------------------------------
    def _gs_workflow_diagram_label(self) -> "QWidget | None":
        """Knut's example-workflow diagram (2026-08-12), painted straight
        from the bundled SVG at whatever width the card currently has —
        vector rendering, so it is crisp at every size and pixel ratio
        (a pre-rendered pixmap showed at double size on Retina, spilling
        into a horizontal scrollbar — Sebastian, live). Widening the
        window enlarges the diagram with it (Knut's fit-width wish). The
        labels in it are vector outlines, no font on the user's machine
        involved. It sits on its own white sheet because the diagram is
        designed for a light ground; in dark mode it reads as a figure,
        like a picture in a book. Returns None when the asset is missing
        — the text above it stands on its own."""
        from core.resource_path import resource_path
        try:
            from PyQt6.QtSvg import QSvgRenderer
        except ImportError:
            return None
        # One SVG per language (scripts/make_workflow_diagram.py generates
        # them from Knut's PDF); a language without its file falls back to
        # English rather than showing nothing.
        from pathlib import Path
        lang = str(self._settings.get("language", "en") or "en")
        path = resource_path(f"assets/help/workflow/{lang}.svg")
        if not Path(path).is_file():
            path = resource_path("assets/help/workflow/en.svg")
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return None
        from PyQt6.QtCore import QRectF, QSize
        from PyQt6.QtGui import QColor, QImage, QPainter
        from PyQt6.QtWidgets import QSizePolicy, QWidget
        from ui.theme import resolve_mode

        size = renderer.defaultSize()
        ratio = size.height() / max(1, size.width())
        settings = self._settings

        def _dark() -> bool:
            return resolve_mode(settings.get("appearance", "auto")) == "dark"

        class _Diagram(QWidget):
            def __init__(self, parent) -> None:
                super().__init__(parent)
                sp = QSizePolicy(QSizePolicy.Policy.Expanding,
                                 QSizePolicy.Policy.Fixed)
                sp.setHeightForWidth(True)
                self.setSizePolicy(sp)
                self.setMinimumWidth(320)
                self._cache_key: "tuple | None" = None
                self._cache_img: "QImage | None" = None

            def hasHeightForWidth(self) -> bool:      # noqa: N802
                return True

            def heightForWidth(self, w: int) -> int:  # noqa: N802
                return round(w * ratio)

            def sizeHint(self) -> QSize:              # noqa: N802
                return QSize(790, round(790 * ratio))

            def resizeEvent(self, event) -> None:     # noqa: N802
                # QVBoxLayout honours height-for-width unreliably; pinning
                # the height on every width change keeps the aspect exact
                # (idempotent, so no resize recursion).
                super().resizeEvent(event)
                h = self.heightForWidth(self.width())
                if self.height() != h:
                    self.setFixedHeight(h)

            def paintEvent(self, event) -> None:      # noqa: N802
                # Rendered into a device-pixel image and, in dark mode,
                # INVERTED: the diagram is pure greyscale, so inversion
                # turns it into the dark variant Sebastian asked for —
                # dark sheet, light lines and text — without maintaining
                # a second drawing. Cached per size/theme; the explicit
                # device-pixel image also sidesteps the pixmap
                # device-pixel-ratio loss that once showed the diagram at
                # double size on Retina.
                dpr = self.devicePixelRatioF() or 1.0
                key = (self.width(), self.height(), round(dpr * 100),
                       _dark())
                if key != self._cache_key:
                    img = QImage(max(1, int(self.width() * dpr)),
                                 max(1, int(self.height() * dpr)),
                                 QImage.Format.Format_ARGB32_Premultiplied)
                    img.fill(QColor("white"))
                    ip = QPainter(img)
                    renderer.render(
                        ip, QRectF(0, 0, img.width(), img.height()))
                    ip.end()
                    if key[3]:
                        img.invertPixels()
                        # Lift the shadows after inverting: the diagram's
                        # nesting shows as slightly different light greys,
                        # and plain inversion squeezes those into
                        # near-blacks that all look alike (Knut: "the
                        # group boxes became not so visible"). A gamma
                        # lift spreads them into clearly separate dark
                        # greys while pure black and the white lines and
                        # text stay exactly where they are.
                        import numpy as np
                        lut = (255.0 * (np.arange(256) / 255.0) ** 0.55
                               ).astype(np.uint8)
                        ptr = img.bits()
                        ptr.setsize(img.sizeInBytes())
                        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                            img.height(), img.bytesPerLine())
                        px = arr[:, :img.width() * 4].reshape(
                            img.height(), img.width(), 4)
                        px[..., 0:3] = lut[px[..., 0:3]]
                    self._cache_img, self._cache_key = img, key
                painter = QPainter(self)
                painter.drawImage(QRectF(self.rect()), self._cache_img)
                painter.end()

        return _Diagram(self._steps_host)

    def _on_gs_index_link(self, href: str) -> None:
        """A Getting-Started index line was clicked: scroll to its chapter.

        Knut, beta.4: each numbered index line "is a link to jump to the
        section in question further down in the window"."""
        if not href.startswith("gs:"):
            return
        target = getattr(self, "_gs_chapter_widgets", {}).get(href[3:])
        if target is None:
            return
        try:
            # Direct arithmetic, not ensureWidgetVisible: chapters taller
            # than the window made that land anywhere from mid-window to
            # past the headline (Sebastian, beta.5 check 6). The chapter's
            # HEADLINE sits a small margin under the top edge, for every
            # chapter the scroll range can reach.
            from PyQt6.QtCore import QPoint
            y = target.mapTo(self._steps_host, QPoint(0, 0)).y()
            sb = self._detail_scroll.verticalScrollBar()
            sb.setValue(max(0, min(y - 8, sb.maximum())))
        except Exception:      # noqa: BLE001 — a link must never break the card
            log.warning("Could not scroll to Getting Started chapter %s",
                        href, exc_info=True)

    def _make_glossary_row(self, term: str, definition: str) -> QWidget:
        """One dictionary entry: bold term, plain-language definition under it
        (Knut's "Dictionary and terminology" card, #108)."""
        row = QWidget(self._steps_host)
        v = QVBoxLayout(row)
        v.setContentsMargins(0, 0, 0, 10)
        v.setSpacing(2)
        t = QLabel(term, row)
        tf = QFont()
        tf.setPixelSize(13)
        tf.setBold(True)
        t.setFont(tf)
        t.setWordWrap(True)
        t.setObjectName("welcome_step_body")
        v.addWidget(t)
        d = QLabel(definition, row)
        df = QFont()
        df.setPixelSize(13)
        d.setFont(df)
        d.setWordWrap(True)
        d.setObjectName("welcome_step_body")
        v.addWidget(d)
        return row

    # ------------------------------------------------------------------
    def _make_step_row(
        self,
        number: int,
        tab_index: int,
        text: str,
        *,
        optional: bool = False,
        notes: "tuple | list" = (),
    ) -> QWidget:
        row = QWidget(self._steps_host)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(14)

        badge = StepBadge(number, tab_index, row, optional=optional)
        h.addWidget(badge, alignment=Qt.AlignmentFlag.AlignTop)

        # A COLUMN, NOT A LABEL — but only when there is a note to put under
        # it. A step with no notes builds exactly the widget it always did, so
        # every card that has none is untouched by this change.
        body = QLabel(text, row)
        body.setWordWrap(True)
        bf = QFont()
        bf.setPixelSize(13)
        if optional:
            bf.setItalic(True)
        body.setFont(bf)
        body.setObjectName("welcome_step_body")
        # Tag the label so theme re-tinting can dim optional steps.
        body.setProperty("welcome_optional", optional)
        if not notes:
            h.addWidget(body, stretch=1)
            return row

        col = QWidget(row)
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        body.setParent(col)
        v.addWidget(body)
        for heading, note_body in notes:
            v.addWidget(StepNote(heading, note_body, col))
        h.addWidget(col, stretch=1)
        return row

    # ------------------------------------------------------------------
    def set_appearance(self, mode: str) -> None:
        """Re-tint dialog chrome + propagate to children."""
        from ui.theme import accept_mode
        self._mode = accept_mode(mode)
        from ui import neutral_styles as _n
        from ui.theme import by_mode
        dialog_bg, sub_fg = by_mode(
            ("#eeece8", "#7a7570"),      # match LM_BG_WINDOW
            ("#181818", "#a8a4a0"),      # match BG_PANEL — dark grey, not black
            (_n.NM_BG_WINDOW, _n.NM_TEXT_FAINT),
            self._mode)
        # Dialog body. Override the global ACCENT (cyan/blue) for the checkbox
        # indicator so it picks up the spectrum-magenta accent of the welcome
        # dialog rather than the app-wide cyan/blue.
        self.setStyleSheet(
            f"""
            QDialog {{ background: {dialog_bg}; }}
            QDialog QLabel {{ background: transparent; }}
            QDialog QCheckBox::indicator:checked {{
                background: {accent_for(SPEC_MAGENTA, self._mode)};
                border-color: {accent_for(SPEC_MAGENTA, self._mode)};
            }}
            QDialog QCheckBox::indicator:hover {{
                border-color: {accent_for(SPEC_MAGENTA, self._mode)};
            }}
            """
        )
        if hasattr(self, "_support_btn"):
            # The heart is the one place a hue was doing decorative work; in a
            # colourless theme it is body ink, and the glyph still says "heart".
            _heart = by_mode("#c62b52", "#ff7aa2", _n.NM_TEXT_MAIN, self._mode)
            self._support_btn.setStyleSheet(
                "QPushButton {"
                f"  color: {_heart}; background: transparent; border: none;"
                "   padding: 2px 6px; font-size: 12px; }"
                "QPushButton:hover { text-decoration: underline; }")
        if hasattr(self, "_subtitle"):
            self._subtitle.setStyleSheet(f"color: {sub_fg};")
        if hasattr(self, "_detail_subtitle"):
            self._detail_subtitle.setStyleSheet(f"color: {sub_fg};")
        if hasattr(self, "_wip_note"):
            self._wip_note.setStyleSheet(f"color: {sub_fg};")
        for card in self._cards:
            card.set_appearance(self._mode)
        if hasattr(self, "_heading"):
            self._heading.update()
        if hasattr(self, "_menu_scroll"):
            self._menu_scroll.set_appearance(self._mode)
        if hasattr(self, "_detail_scroll"):
            self._detail_scroll.set_appearance(self._mode)
        self._apply_detail_text_colors()

    # ------------------------------------------------------------------
    def _apply_detail_text_colors(self) -> None:
        if not hasattr(self, "_steps_host"):
            return
        from ui import neutral_styles as _n
        from ui.theme import by_mode
        body_fg = by_mode("#22211f", "#e6e6e6", _n.NM_TEXT_MAIN, self._mode)
        optional_fg = by_mode("#7a7570", "#9a9a9a", _n.NM_TEXT_FAINT, self._mode)
        title_fg = body_fg
        for lbl in self._steps_host.findChildren(QLabel, "welcome_step_body"):
            fg = optional_fg if bool(lbl.property("welcome_optional")) else body_fg
            lbl.setStyleSheet(f"color: {fg};")
        # A NOTE IS SECONDARY TO ITS STEP, and it has to LOOK it — otherwise
        # the card gains a second thing competing for the reader's attention,
        # which is the opposite of what the notes are for. Same dimmed ink as
        # an optional step, in both themes and in Neutral.
        for lbl in self._steps_host.findChildren(QLabel, "welcome_note_body"):
            lbl.setStyleSheet(f"color: {optional_fg};")
        # AND IT IS TEXT, NOT A BUTTON, WHATEVER WIDGET IT IS BUILT FROM.
        #
        # The heading is a QPushButton so that Tab reaches it and Space opens
        # it. That also means the app-wide sheet's `QPushButton` rule reaches
        # it, and on screen that rule is **Menlo**: measured in the running app
        # (`QFontInfo(btn.font()).family()`), the step beside it resolved to
        # Inter and the note heading under it to Menlo, so a line of prose came
        # out in the same monospace as "Save as PDF" and "Close". The family is
        # taken from the step's own label rather than named here, so it follows
        # whatever the sheet gives body text.
        fam = ""
        bodies = self._steps_host.findChildren(QLabel, "welcome_step_body")
        if bodies:
            from PyQt6.QtGui import QFontInfo
            fam = QFontInfo(bodies[0].font()).family()
        for btn in self._steps_host.findChildren(QPushButton,
                                                 "welcome_note_head"):
            btn.setStyleSheet(
                f"QPushButton#welcome_note_head {{ color: {optional_fg}; "
                + (f'font-family: "{fam}"; ' if fam else "")
                + "background: transparent; border: none; text-align: left; "
                "padding: 0px; }")
        if hasattr(self, "_detail_title"):
            self._detail_title.setStyleSheet(f"color: {title_fg};")
