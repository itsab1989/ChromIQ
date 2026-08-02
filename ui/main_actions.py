"""The "Overview of Main Actions" card (#130, Knut 2026-07-28).

His instruction, after reviewing the survey posted on the issue:

    *"Call this table 'Overview of Main Actions' and create this as a separate
    help card next to the Getting Started Card. Make sure the card uses the
    table format, like html table, to get the nice look. Also, when there is
    only one action alternative, you do not need to show (a) in front."*

So: the same content as the survey, as a real table, sitting beside the tour —
and the ``(a)`` lettering appears only where there is genuinely more than one
way, which is what the letters are for.

The second table is the honest half: **what ChromIQ cannot do today**. Knut
asked for printing through a profile to be recorded there as a possible future
improvement rather than built, because ChromIQ does not control the printer
drivers and printing outside it is the natural thing.
"""
from __future__ import annotations

import html

from core.i18n import tr
from core.platform_paths import file_manager_name

#: (action, [route, …]) — one entry per thing a user sets out to do.
ACTION_ROWS: "list[tuple[str, list[str]]]" = [
    (tr("Start a new profile project"), [
        tr("Type a name in Create Chart and press “Generate Chart” — the first "
        "build creates the project folder."),
    ]),
    (tr("Open an existing project"), [
        # Moved out of Create Chart to the masthead (#130, 2026-08-01).
        tr("The project icon at the top left of the window, left of the chart "
        "icon — it brings back the project's runs, charts and measurements."),
        tr("Load a chart that lives inside a project folder — that adopts the "
        "project."),
        tr("Start ChromIQ, which reopens the last project you used."),
    ]),
    (tr("Create a chart"), [
        tr("Create Chart ▸ “Generate Chart”, in Guided or Manual."),
        tr("Choose a preset first, then generate."),
        tr("Tools ▸ “Edit / create chart patch set”, then apply it."),
    ]),
    (tr("Open an existing chart"), [
        # The two load buttons moved to the masthead (#130, 2026-08-01), so the
        # per-tab instructions here were wrong; Knut asked for every card to be
        # brought up to date.
        tr("The chart icon at the top left of the window — one button for the "
        "whole app, so Create Chart, Print Chart and Measure all show what you "
        "open."),
        tr("Create Chart ▸ “Load patch set” for an Argyll .ti1, or an i1Profiler "
        "set (.pxf or CGATS .txt)."),
        tr("Select a Profile run that already has one — the run "
        "currently chosen has no stored chart to restore."),
    ]),
    (tr("Put a chart into a particular run"), [
        tr("Set “Profile run” first, then generate."),
        tr("Load a chart file and answer the destination window: New run, "
        "Replace, or “Replace only the chart”."),
    ]),
    (tr("Duplicate a run, or a chart"), [
        # Knut, #130 2026-08-01: this row is where anyone looks for "duplicate",
        # and it talked only about charts while the Duplicate button was about
        # runs. The run answer goes first because it is the one people mean.
        tr("“Duplicate” on the run bar copies the whole run — chart, "
        "measurement and profile — into a new one, leaving this run untouched. "
        "That is the safe way to re-measure, to try a different profile from "
        "the same readings, or to change the chart your verification runs use."),
        tr("For the chart alone: load its .ti1 and build into a New run — same "
        "patches, fresh layout."),
        tr("“Restore Used Chart” puts a run's stored copy back over the live one."),
    ]),
    (tr("Copy a run"), [
        # The Duplicate button (#130, "course B") is the direct answer to this
        # question, so it goes first — the pre-conditioning route below seeds a
        # refinement, which is a different intention.
        tr("“Duplicate” on the run bar — makes a new run holding a copy of this "
        "run's chart, measurement and profile, leaving this one untouched. Use "
        "it before re-measuring, before building a different profile from the "
        "same readings, or to give verification runs a different chart."),
        tr("Create a New run, then “← Use as Pre-conditioning” on Build Profile "
        "or Check & Refine — that copies the run's profile and measurement in "
        "as seeds."),
    ]),
    (tr("Keep a measurement you already have"), [
        tr("“Duplicate” the run first, then measure in the copy — the original "
        "run keeps its measurement and the profile built from it."),
        tr("Tick “Refine / resume existing measurement (-r)” to add to the "
        "readings instead of replacing them."),
        tr("Re-creating a chart in a run that has been measured leaves the "
        "measurement describing a chart you no longer have, and any profile "
        "built from it no longer matches the verification runs checked against "
        "it. ChromIQ warns before that happens."),
    ]),
    (tr("Print a chart"), [
        tr("Print Chart ▸ “Print All Pages” or “Print Current Page”."),
        tr("Print the page TIFF files from any other program."),
    ]),
    (tr("Measure a chart"), [
        tr("Measure ▸ “Start Measurement”."),
        tr("Patch by patch, with that option ticked."),
        tr("Tools ▸ “Read single patches” for readings outside a chart."),
    ]),
    (tr("Add to an existing measurement"), [
        tr("Tick “Refine / resume existing measurement (-r)” before you start."),
        tr("“Re-read Individual Strips” for particular strips."),
        tr("“Continue Measurement” after stopping part-way."),
    ]),
    (tr("Bring in a measurement made elsewhere"), [
        tr("Tools ▸ “Convert i1Profiler → TI3”."),
        tr("Build Profile ▸ browse for a .ti3 file."),
        tr("Check & Refine ▸ “Load Measurement”."),
    ]),
    (tr("Build a profile"), [
        tr("Build Profile ▸ “Build Profile”."),
        tr("Tools ▸ “Build profile with scanner or camera”."),
    ]),
    (tr("Check a profile"), [
        tr("Check & Refine ▸ “Analyse Profile Quality”."),
        tr("A Verification run, with its measurement report."),
        tr("Tools ▸ “Verify a profile”, “Verify against reference” or “Inspect a "
        "profile”."),
    ]),
    (tr("Delete a run"), [
        tr("The Profile-run bar ▸ “Delete”, with Run type = Profiling."),
    ]),
    (tr("Delete a verification"), [
        tr("“Delete” with Run type = Verification — one date, or the whole "
        "verification folder."),
    ]),
    (tr("Delete a chart on its own"), [
        tr("Not directly. “Generate Chart” replaces it, and the run's measurement "
        "is moved to the “old” folder rather than lost."),
        tr("“Delete” removes the whole run."),
    ]),
    (tr("Delete a project"), [
        tr("“Delete” on the last remaining run offers “Delete the whole project”."),
    ]),
    (tr("Empty a run without deleting it"), [
        tr("Only through the last-run window's “Empty the run”."),
    ]),
    (tr("Rename"), [
        tr("The project can be renamed, and its files follow. A run or a "
        "verification date cannot — their number and their date are what "
        "identify them."),
    ]),
    (tr("Recover something"), [
        tr("The run's “old” folder holds whatever a Replace or a re-generation "
        "displaced. A Delete is permanent and cannot be undone."),
    ]),
    (tr("Find your files"), [
        tr("The “Location being edited” line under the Profile-run bar."),
        tr("The reveal-folder button."),
        tr("The log, which names every file written."),
        tr("The “Where are my files?” card in this window."),
    ]),
]

#: (what ChromIQ cannot do, what to do instead / why) — Knut asked for this to
#: be kept with the actions, and for printing through a profile to sit here as
#: a possible future improvement rather than a missing feature.
CANNOT_ROWS: "list[tuple[str, str]]" = [
    (tr("Duplicate a run complete with its chart, measurement and profile"),
     tr("Create a New run and seed it with “← Use as Pre-conditioning”, which "
     "copies the profile and measurement in as a starting point. A full copy "
     "is a possible future improvement.")),
    (tr("Rename a run, or a verification date"),
     tr("Run numbers and verification dates are what identify them, so they are "
     "not free text. Rename the project instead.")),
    (tr("Reorder runs"),
     tr("Run numbers follow their position, and are renumbered automatically when "
     "one is deleted.")),
    (tr("Move a run into another project"),
     tr("Move the folder yourself in {manager}.").format(
         manager=file_manager_name())),
    (tr("Delete only the chart and keep the run"),
     tr("Generating a new chart replaces it, and your measurement is moved to the "
     "run's “old” folder rather than lost.")),
    (tr("Undo a deletion"),
     tr("A Delete is permanent by design, and every Delete window says so before "
     "you confirm. What a Replace displaced is still in “old”.")),
    (tr("Print through a profile from inside ChromIQ"),
     tr("ChromIQ prints charts with colour management off, which is what "
     "profiling needs — and it does not drive your printer's own colour "
     "settings, so printing THROUGH a profile is done in the program you "
     "normally print from (or with Tools ▸ device-link). A possible future "
     "improvement.")),
    (tr("Compare two runs or two profiles side by side"),
     tr("Build a measurement report for each, or use Tools ▸ “Verify against "
     "reference”. A possible future improvement.")),
]


def main_actions_card_title() -> str:
    return tr("Overview of Main Actions")


def main_actions_card_subtitle() -> str:
    return tr("Every main action, and each of the different ways to reach it — "
              "plus what ChromIQ cannot do today.")


def _esc(text: str) -> str:
    return html.escape(tr(text), quote=False)


def main_actions_html() -> str:
    """Both tables as HTML. Routes are lettered only when there is more than
    one — a single route needs no “(a)” in front of it (Knut)."""
    out = ["<p>" + _esc(
        "Most things in ChromIQ can be reached more than one way. This is every "
        "main action with all of its routes, so you can use whichever one suits "
        "where you already are.") + "</p>",
        '<table border="1" cellspacing="0" cellpadding="6">',
        f"<tr><th>#</th><th>{_esc('Action')}</th>"
        f"<th>{_esc('How to do it')}</th></tr>"]
    for n, (action, routes) in enumerate(ACTION_ROWS, start=1):
        if len(routes) == 1:
            cell = _esc(routes[0])
        else:
            cell = "<br>".join(
                f"({chr(ord('a') + i)})&nbsp; {_esc(r)}"
                for i, r in enumerate(routes))
        out.append(f"<tr><td>{n}</td><td><b>{_esc(action)}</b></td>"
                   f"<td>{cell}</td></tr>")
    out.append("</table>")

    out.append("<p><b>" + _esc("What ChromIQ cannot do today") + "</b> — "
               + _esc("with the nearest thing it can, and where a future "
                      "improvement is possible.") + "</p>")
    out.append('<table border="1" cellspacing="0" cellpadding="6">')
    out.append(f"<tr><th>#</th><th>{_esc('Not possible today')}</th>"
               f"<th>{_esc('What to do instead')}</th></tr>")
    for n, (what, instead) in enumerate(CANNOT_ROWS, start=1):
        out.append(f"<tr><td>{n}</td><td><b>{_esc(what)}</b></td>"
                   f"<td>{_esc(instead)}</td></tr>")
    out.append("</table>")
    return "\n".join(out)
