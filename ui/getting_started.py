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
         tr("ChromIQ's name in the middle. On the LEFT two buttons that act on "
            "the whole app: “Open a project” and “Open a chart file (.ti2)” — "
            "open a chart there and Create Chart, Print Chart and Measure all "
            "show it. On the RIGHT “Tools”, “Settings” and “?”, which opens "
            "this window. The two on the left are unavailable while a "
            "measurement is running.")),
        (tr("Profile-run bar"), tr("in the middle of the masthead"),
         tr("The most important control in ChromIQ: it decides what every tab "
            "acts on. “Profile run”, “Run type”, “Verification”, an ⓘ, and the "
            "“Restore Used Chart”, “Duplicate” and “Delete” buttons.")),
        (tr("Location being edited"), tr("just under the bar"),
         tr("The exact folder the next action will write to. When you are not "
            "sure where something will land, read this line.")),
        (tr("The five tabs"), tr("under the masthead"),
         tr("1. Create Chart · 2. Print Chart · 3. Measure · 4. Build Profile · "
            "5. Check & Refine — numbered in the order you use them. (Tab 4 "
            "is called “Calibration & Profiling” when “Enable calibration "
            "options” is on in Preferences.)")),
        (tr("Options panel"), tr("the left of every tab"),
         tr("The settings for that step, arranged in modules you switch with "
            "the buttons at the top of the tab: GUIDED asks fewer questions, "
            "MANUAL shows every setting. On a verification run, Create Chart "
            "adds FROM PROFILE GAMUT — a check chart built from colours your "
            "finished profile promises it can print — and opens on it.")),
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
         tr("“Open Chart File (.ti2)” at the top left of the window — it opens "
            "the chart for the whole app, so Create Chart, Print Chart and "
            "Measure all show it. Or Create Chart ▸ “Load patch set” for an "
            "Argyll .ti1 or an i1Profiler set. Choosing a Profile run that "
            "already has a chart opens that one.")),
        (tr("Open a project"),
         tr("“Open Project” at the top left of the window. Or open a chart "
            "that lives inside a project folder, which adopts that project. "
            "Or start ChromIQ, which reopens the last project you used, "
            "provided “Restore last session on launch” is enabled in "
            "Preferences ▸ General.")),
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
        (tr("“Duplicate” is the safe way to carry on"),
         tr("When you want to measure a chart again, build a different profile "
            "from readings you already have, or give your verification runs a "
            "different chart, duplicate the run first. It makes a new run "
            "holding a copy of the chart, the measurement and the profile, and "
            "leaves the run you started from exactly as it is — so you can try "
            "something without putting the work behind it at risk.\n\n"
            "It needs a complete chart to copy: the patch list (.ti1), the "
            "laid-out chart (.ti2), the layout recipe (.channels.json) and at "
            "least one printed page (.tif). If the button is greyed, hover it "
            "— the tooltip names which of the four this run is missing.")),
        (tr("Why re-creating a chart mid-run is worth avoiding"),
         tr("A run is meant to hold one chart, the measurement of that chart, "
            "and the profile built from it. Re-create the chart after "
            "measuring and those three stop describing each other: the "
            "measurement refers to a sheet you no longer have, and any "
            "verification run checked against the old profile is no longer "
            "comparing like with like. Duplicate the run instead, and change "
            "the chart in the copy.")),
    ]


def _verifying() -> "list[tuple[str, str]]":
    """The 4.0 headline, as a short chapter of its own (Knut, 2026-08-11:
    the guide must cover starting a project, making a profile AND verifying
    it). The full walkthrough lives in its own card; this is the overview."""
    return [
        (tr("Why check at all"),
         tr("A profile describes how your printer behaved on the day you "
            "measured. Ink ages, paper batches differ, printheads drift — a "
            "check tells you whether the profile still holds, with numbers "
            "instead of a feeling.")),
        (tr("The short version"),
         tr("A verification always checks a finished profile — you need the "
            "one you built in step 4 first. "
            "Set “Run type” in the bar to “Verification”. Create Chart opens "
            "on the “From profile gamut” module — generate that chart, print "
            "it from the Print Chart tab (ChromIQ chooses the right way by "
            "itself), let it dry, and measure it on the Measure tab. The "
            "result is filed by date, and the Measurement Report shows how "
            "close every colour landed — and, as checks accumulate, how the "
            "profile holds up over time.")),
        (tr("Where to read more"),
         tr("The card “Check a finished profile (verification run)” in this "
            "window walks it step by step; the Dictionary entry “Which "
            "verification should I use? (the three ways)” compares the three "
            "kinds of check and when each one is the right tool.")),
    ]


def _files_overview() -> str:
    """Three sentences, not the folder tree — the tree has its own card."""
    return tr(
        "Everything lives under one folder per project (named after your "
        "project), with one folder per run inside it — each run holding its "
        "own chart, measurement, profile and reports, and dated verification "
        "checks in their own folders. Whatever you replace moves into a "
        "dated “old” folder rather than being deleted. The “Location being "
        "edited” line under the bar always shows the exact folder the next "
        "action writes to — and the card “Where are my files?” in this "
        "window walks the whole folder tree in plain language.")


def _outro() -> str:
    return tr(
        "Almost every setting has an ⓘ beside it that explains that setting in "
        "full, with the consequences of getting it wrong. If something looks "
        "wrong, the log at the bottom left is the first place to look — it "
        "names every file ChromIQ writes.")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _chapters() -> "list[tuple[str, str]]":
    """(key, translated title) for every chapter, in reading order — the one
    list the index, the links and the section renderer all share, so a chapter
    added later appears in the index automatically."""
    return [
        ("areas",   tr("Finding your way around")),
        ("steps",   tr("Your first profile, start to finish")),
        ("verify",  tr("Checking the profile you built (verification)")),
        ("files",   tr("Where your files live")),
        ("alts",    tr("More than one way to do most things")),
        ("keeping", tr("Trying again, and what is kept")),
    ]


def getting_started_sections() -> "list[tuple[str | None, str]]":
    """The card as (chapter_key, html) blocks.

    The Welcome window renders each block as its own widget, so the index —
    one numbered line per chapter, each a link (Knut, beta.4: *"each line is
    a link to jump to the section in question further down"*) — can scroll
    straight to the chapter it names. Keys are ``gs:<chapter>``; the intro
    and outro carry no key.
    """
    def esc(s: str) -> str:
        return html.escape(s, quote=False)

    sections: "list[tuple[str | None, str]]" = []

    index_lines = "".join(
        f"<a href=\"gs:{key}\">{i}. {esc(title)}</a><br>"
        for i, (key, title) in enumerate(_chapters(), start=1))
    sections.append((None, "\n".join([
        f"<p>{esc(tr('ChromIQ turns a printed sheet of colour patches into '
                     'an ICC profile for your printer. The whole job is '
                     'five steps, the tabs are numbered in that order — '
                     'and once a profile is built, ChromIQ can check how '
                     'good it really is, and keep checking over time.'))}</p>",
        f"<p><b>{esc(tr('What is in this guide'))}</b></p>"
        f"<p>{index_lines}</p>",
        "<p>" + esc(tr('Every topic here has a deeper card in this window — '
                       'this guide names the right one as it goes — and every '
                       'term of art has a plain-language entry under '
                       '“Dictionary and terminology”.')) + "</p>"])))

    titles = dict(_chapters())

    areas = [f"<h3>{esc(titles['areas'])}</h3>"
             # exactly ONE empty line before the table — a plain <br> here
             # stacked with the heading's own margin into two or three
             # (Sebastian, beta.5 check 6 follow-up)
             "<p style='font-size:6px; margin:0'>&nbsp;</p>",
             "<table cellpadding='4' cellspacing='0'>",
             "<tr><th align='left'>%s</th><th align='left'>%s</th>"
             "<th align='left'>%s</th></tr>" % (
                 esc(tr("Area")), esc(tr("Where")),
                 esc(tr("What it is for")))]
    for area, where, what in _areas():
        areas.append(f"<tr><td><b>{esc(area)}</b></td><td>{esc(where)}</td>"
                     f"<td>{esc(what)}</td></tr>")
    areas.append("</table>")
    sections.append(("areas", "\n".join(areas)))

    def _rows_section(key: str, rows) -> "tuple[str, str]":
        out = [f"<h3>{esc(titles[key])}</h3>"]
        for title, body in rows:
            out.append(f"<p><b>{esc(title)}</b><br>{esc(body)}</p>")
        return key, "\n".join(out)

    sections.append(_rows_section("steps", _steps()))
    sections.append(_rows_section("verify", _verifying()))
    sections.append(("files", f"<h3>{esc(titles['files'])}</h3>"
                              f"<p>{esc(_files_overview())}</p>"))
    sections.append(_rows_section("alts", _alternatives()))
    sections.append(_rows_section("keeping", _keeping()))
    sections.append((None, f"<p>{esc(_outro())}</p>"))
    return sections


def getting_started_html() -> str:
    """The card body as one HTML string (anywhere that shows it whole)."""
    return "\n".join(html_block for _key, html_block
                     in getting_started_sections())


def getting_started_body() -> str:
    """Plain-text form, for anywhere that cannot show rich text."""
    lines = [tr("ChromIQ turns a printed sheet of colour patches into an ICC "
                "profile for your printer. The whole job is five steps, the "
                "tabs are numbered in that order — and once a profile is "
                "built, ChromIQ can check how good it really is, and keep "
                "checking over time."), ""]
    lines.append(tr("Finding your way around"))
    for area, where, what in _areas():
        lines.append(f"  {area} ({where}) — {what}")
    lines.append("")
    for heading, rows in ((tr("Your first profile, start to finish"), _steps()),
                          (tr("Checking the profile you built (verification)"),
                           _verifying()),
                          (tr("More than one way to do most things"),
                           _alternatives()),
                          (tr("Trying again, and what is kept"), _keeping())):
        lines.append(heading)
        for title, body in rows:
            lines.append(f"  {title} — {body}")
        lines.append("")
    lines.append(tr("Where your files live"))
    lines.append(f"  {_files_overview()}")
    lines.append("")
    lines.append(_outro())
    return "\n".join(lines)
