"""The "Getting Started" card (#130, Knut 2026-07-28).

His brief: *"make suggested text for a new 'Getting Started' help card, listing
all basic and normal actions, with alternative ways to achieve the goals. The
help card must start by identifying the main areas of the user interface, what
they are called and where they are and what they are used for."*

So the card is in that order: **where things are**, then **the five steps**,
then **the alternative routes** — because the survey behind it (posted on #130)
found that almost every action has two or three ways to reach it, and a new user
only ever finds one of them.

Each paragraph is its own ``tr()`` string, like :mod:`ui.file_guide`, so the
card translates a piece at a time rather than as one wall of text.
"""
from __future__ import annotations

import html

from core.i18n import tr


def getting_started_card_title() -> str:
    return tr("Getting started (a tour of ChromIQ)")


def getting_started_card_subtitle() -> str:
    return tr("Where everything is, the five steps from blank page to finished "
              "profile, and the different ways to reach the same result.")


# ---------------------------------------------------------------------------
# 1. The areas of the interface
# ---------------------------------------------------------------------------

def _areas() -> "list[tuple[str, str, str]]":
    """(area, where it is, what it is for)."""
    return [
        (tr("Masthead"), tr("across the top"),
         tr("ChromIQ's name on the left; on the right the three buttons "
            "“Tools”, “Settings” and “?” — which opens this window.")),
        (tr("Profile-run bar"), tr("in the middle of the masthead"),
         tr("The most important control in ChromIQ: it decides what every tab "
            "acts on. “Profile run”, “Run type”, “Verification”, an ⓘ, and the "
            "“Restore Used Chart” and “Delete” buttons.")),
        (tr("Location being edited"), tr("just under the bar"),
         tr("The exact folder the next action will write to. When you are not "
            "sure where something will land, read this line.")),
        (tr("The five tabs"), tr("under the masthead"),
         tr("1. Create Chart · 2. Print Chart · 3. Measure · 4. Build Profile · "
            "5. Check & Refine — numbered in the order you use them.")),
        (tr("Options panel"), tr("the left of every tab"),
         tr("The settings for that step. Each tab offers “Guided” and "
            "“Manual”: Guided asks fewer questions, Manual shows every "
            "setting.")),
        (tr("Preview"), tr("the right of every tab"),
         tr("The chart pages — and during a measurement, what you have read so "
            "far.")),
        (tr("Log"), tr("the bottom left of every tab"),
         tr("What ChromIQ and ArgyllCMS are doing, and the full path of every "
            "file written. The first place to look when something surprises "
            "you.")),
        (tr("Tools"), tr("the masthead, or Ctrl+T"),
         tr("Stand-alone tools in six groups — measurements, charts and patch "
            "sets, scanner and camera, i1Profiler interchange, profiles, and "
            "language.")),
    ]


# ---------------------------------------------------------------------------
# 2. The five steps
# ---------------------------------------------------------------------------

def _steps() -> "list[tuple[str, str]]":
    return [
        (tr("1. Create Chart"),
         tr("Make the sheet of colour patches you are going to print. Type a "
            "name for the profile project, choose your instrument and paper, "
            "and press “Generate Chart”. That first build also creates the "
            "project folder.")),
        (tr("2. Print Chart"),
         tr("Print every page. Colour management must be OFF — ChromIQ prints "
            "the patches exactly as they are, and any colour correction on the "
            "way to the printer would make the measurements describe the "
            "correction rather than your printer.")),
        (tr("3. Measure"),
         tr("Let the print dry, connect your instrument, and press “Start "
            "Measurement”. ChromIQ shows you which strip to read and marks "
            "each one off as it arrives.")),
        (tr("4. Build Profile"),
         tr("Turn the measurements into an ICC profile with “Build Profile”, "
            "then install it if you want to use it straight away.")),
        (tr("5. Check & Refine"),
         tr("See how accurate the profile is, and improve it by measuring more "
            "patches where it is weakest.")),
    ]


# ---------------------------------------------------------------------------
# 3. More than one way to do most things
# ---------------------------------------------------------------------------

def _alternatives() -> "list[tuple[str, str]]":
    return [
        (tr("Open an existing chart"),
         tr("Measure ▸ “Load .ti2 file”, or the same on Print Chart, or Create "
            "Chart ▸ “Load patch set” for an Argyll .ti1 or an i1Profiler set. "
            "Choosing a Profile run that already has a chart opens that one.")),
        (tr("Open a project"),
         tr("Create Chart ▸ “Open a printer profile project”, or load a chart "
            "that lives inside a project folder — which adopts that project — "
            "or simply start ChromIQ, which reopens the last one you used.")),
        (tr("Put a chart into a particular run"),
         tr("Set “Profile run” first, then generate. If you load a chart file "
            "instead, ChromIQ asks where it should go: a new run, replacing "
            "the run, or replacing only the chart and keeping your "
            "measurement.")),
        (tr("Add to a measurement instead of replacing it"),
         tr("Tick “Refine / resume existing measurement (-r)” before you "
            "start, use “Re-read Individual Strips” for particular strips, or "
            "press “Continue Measurement” if you stopped part-way.")),
        (tr("Bring in a measurement from another program"),
         tr("Tools ▸ “Convert i1Profiler → TI3”, or browse for a .ti3 file on "
            "Build Profile or Check & Refine.")),
        (tr("Check a profile"),
         tr("Check & Refine ▸ “Analyse Profile Quality”, a Verification run "
            "with its measurement report, or the independent checks under "
            "Tools ▸ Profiles.")),
        (tr("Read a few patches without a chart"),
         tr("Tools ▸ “Read single patches”.")),
        (tr("Find your files"),
         tr("The “Location being edited” line, the reveal-folder button, the "
            "log — which names every file written — or the “Where are my "
            "files?” card in this window.")),
    ]


# ---------------------------------------------------------------------------
# 4. Trying again, and what is kept
# ---------------------------------------------------------------------------

def _keeping() -> "list[tuple[str, str]]":
    return [
        (tr("Try again without losing what you have"),
         tr("Set “Profile run” to “New run” before you build a new chart. Your "
            "earlier run keeps its own chart, measurement and profile. To "
            "build on what you already have rather than start over, use "
            "“← Use as Pre-conditioning”.")),
        (tr("Replacing keeps a copy"),
         tr("Replacing a chart, or generating a new one over an old one, moves "
            "what it displaces into an “old” folder inside the run. Nothing is "
            "lost, and ChromIQ tells you before it happens.")),
        (tr("Deleting does not"),
         tr("“Delete” is permanent: nothing goes to the Trash and no copy is "
            "kept. Every Delete window says exactly what will go before you "
            "confirm, and Cancel is always the button that is ready to "
            "press.")),
        (tr("Your measurements are the irreplaceable part"),
         tr("A chart can be generated again in seconds; a measurement is real "
            "ink on real paper and cannot be. ChromIQ warns you before "
            "anything would overwrite one.")),
    ]


def _outro() -> str:
    return tr(
        "Almost every setting has an ⓘ beside it that explains that setting in "
        "full, with the consequences of getting it wrong. If something looks "
        "wrong, the log at the bottom left is the first place to look — it "
        "names every file ChromIQ writes.")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def getting_started_html() -> str:
    """The card body, as the Welcome/Help window renders it."""
    def esc(s: str) -> str:
        return html.escape(s, quote=False)

    out = [f"<p>{esc(tr('ChromIQ turns a printed sheet of colour patches into '
                         'an ICC profile for your printer. The whole job is '
                         'five steps, and the tabs are numbered in that '
                         'order.'))}</p>"]

    out.append(f"<h3>{esc(tr('Finding your way around'))}</h3>")
    out.append("<table cellpadding='4' cellspacing='0'>")
    out.append("<tr><th align='left'>%s</th><th align='left'>%s</th>"
               "<th align='left'>%s</th></tr>" % (
                   esc(tr("Area")), esc(tr("Where")), esc(tr("What it is for"))))
    for area, where, what in _areas():
        out.append(f"<tr><td><b>{esc(area)}</b></td><td>{esc(where)}</td>"
                   f"<td>{esc(what)}</td></tr>")
    out.append("</table>")

    out.append(f"<h3>{esc(tr('Your first profile, start to finish'))}</h3>")
    for title, body in _steps():
        out.append(f"<p><b>{esc(title)}</b><br>{esc(body)}</p>")

    out.append(f"<h3>{esc(tr('More than one way to do most things'))}</h3>")
    for title, body in _alternatives():
        out.append(f"<p><b>{esc(title)}</b><br>{esc(body)}</p>")

    out.append(f"<h3>{esc(tr('Trying again, and what is kept'))}</h3>")
    for title, body in _keeping():
        out.append(f"<p><b>{esc(title)}</b><br>{esc(body)}</p>")

    out.append(f"<p>{esc(_outro())}</p>")
    return "\n".join(out)


def getting_started_body() -> str:
    """Plain-text form, for anywhere that cannot show rich text."""
    lines = [tr("ChromIQ turns a printed sheet of colour patches into an ICC "
                "profile for your printer. The whole job is five steps, and "
                "the tabs are numbered in that order."), ""]
    lines.append(tr("Finding your way around"))
    for area, where, what in _areas():
        lines.append(f"  {area} ({where}) — {what}")
    lines.append("")
    for heading, rows in ((tr("Your first profile, start to finish"), _steps()),
                          (tr("More than one way to do most things"),
                           _alternatives()),
                          (tr("Trying again, and what is kept"), _keeping())):
        lines.append(heading)
        for title, body in rows:
            lines.append(f"  {title} — {body}")
        lines.append("")
    lines.append(_outro())
    return "\n".join(lines)
