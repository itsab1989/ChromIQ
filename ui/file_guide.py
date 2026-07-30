"""The "Where are my files?" folder guide (#125/#126, Knut).

One place that explains every file ChromIQ writes into a project folder: which
feature creates it, when, and what it's for. Shown as its own card in the
Welcome/Help window (rendered as a table — Knut); the same information (in
English) is also dropped into each project folder as ``Where are my files.txt``
(see ``core.file_manager``), rendered as an aligned plain-text table.

Each row's cells are individual ``tr()`` strings so they translate like every
other help text. ``{name}`` stands for the profile's name.
"""
from __future__ import annotations

import html

from core.i18n import tr


def file_guide_card_title() -> str:
    """Tile title in the Welcome/Help window's card grid."""
    return tr("Where are my files? (folder guide)")


def file_guide_card_subtitle() -> str:
    return tr("Every file a ChromIQ project folder can contain — what "
              "created it, when, and what it's for.")


def _intro() -> str:
    return tr(
        "Every ChromIQ project lives in its own folder (inside ~/ChromIQ, or "
        "your custom output folder from Settings), named after the profile. "
        "Everything you would print, install or keep sits right at the top of "
        "each run folder; the paperwork is grouped into a few folders whose "
        "names already tell you whether you care about them. Each build is a "
        "“run” (runs/run1, run2 …); a run's profiling work sits in the run "
        "folder, and any later checks of the finished profile — “verification” "
        "runs — accrue as dated folders inside verifications/, kept apart so the "
        "two never mix. Below: first the three files that matter, then what each "
        "folder means, then every file in detail. “{name}” stands for your "
        "profile's name.")


def _outro() -> str:
    return tr(
        "Safe to tidy: everything inside a cache folder is always safe to "
        "delete — ChromIQ can recreate all of it. The reports folders are "
        "safe to delete too, if you don't need the history of your quality "
        "checks. Your measurements ({name}.ti3, reads/, cal/{name}-cal.ti3) "
        "are real ink on real paper — keep those; any profile can be rebuilt "
        "from them later. The quickest big tidy-up is deleting whole runN "
        "folders you no longer need.")


#: The connector pieces the tree is drawn from. Box-drawing characters rather
#: than dotted ones: Knut asked for lines showing the hierarchy and suggested
#: dotted, but the dotted variants (┈ ┊) are missing from many monospace faces
#: and fall back to a box glyph of a different width, which is exactly what
#: would break the alignment he asked for. These four are in every monospace
#: font ChromIQ ships or can fall back to, and a test checks that.
_TREE_BRANCH = "├─ "     # an entry with more entries after it
_TREE_LAST = "└─ "       # the last entry at this level
_TREE_PASS = "│  "       # a level that continues past this row
_TREE_GAP = "   "        # a level that has already ended

#: The families the tree column asks for, most-wanted first. Every one of them
#: draws all four connector pieces at the same width; the UI font does not.
_MONO = "Menlo,Monaco,'Courier New',monospace"


def _structure():
    """The project folder as a hierarchy: ``(depth, name, explanation)`` rows.

    Knut, #130 2026-07-29: *"add before the first section 'Files Relating to
    Features', a new section 'Project File Structure'. In that section, create a
    full hierarchical overview of each folder and a brief explanation what is
    located in each folder. The hierarchy of folders shall be shown with lines
    pointing from higher level to next lower level folders… so that the hierarchy
    becomes clear. Make sure all lines and folders are aligned for the same level
    of the hierarchy."*

    Only the DEPTH is written here. Which rows are last at their level, and
    therefore where a line continues and where it stops, is worked out in
    :func:`tree_rows` — my first attempt carried those flags by hand and drew
    continuation lines under a branch that had already ended, which is exactly
    the misalignment he asked to avoid.

    The names are the real ones; ``test_file_guide_structure`` compares them
    against ``core.file_manager``'s folder constants so this diagram cannot
    drift from the folders ChromIQ actually creates.
    """
    return [
        (0, "{name}/", tr(
            "Your project folder, named after the profile. One per printer, "
            "paper and instrument combination you profile.")),
        (1, "project.json", tr(
            "ChromIQ's own note of which runs exist and which one you are "
            "working on. Small, and best left alone.")),
        (1, "Where are my files.txt", tr(
            "This guide, as a plain text file, refreshed whenever the layout "
            "changes. Yours to read, edit or delete.")),
        (1, "cal/", tr(
            "The optional printer-calibration target and the curves measured "
            "from it, shared by every run in this project.")),
        (2, "exports/", tr(
            "That calibration chart's hand-off files for other programs.")),
        (1, "exports/", tr(
            "Files made for other programs from the Tools menu, belonging to "
            "the whole project rather than to one run.")),
        (1, "reports/", tr(
            "Measurement reports that cover the whole profile rather than one "
            "run — see the Measurement Report row in the next section for which "
            "reports folder a report lands in.")),
        (1, "runs/", tr(
            "One folder per profile build. This is where nearly everything "
            "lives.")),
        (2, "run1/", tr(
            "The first build: its chart, its measurement, its profile. "
            "run2, run3 … follow the same shape, and the newest is the one "
            "ChromIQ is working on.")),
        (3, "chart/", tr(
            "The copy of the chart this run was measured with, kept the moment "
            "measuring starts. “Restore Used Chart” puts this back.")),
        (3, "reads/", tr(
            "Your individual readings, when you measure one chart several "
            "times to average them.")),
        (3, "reports/", tr(
            "What ChromIQ tells you about this build: quality checks, the "
            "re-measure list, and the dated measurement reports.")),
        (3, "exports/", tr(
            "This chart's files for other programs — the i1Profiler patch set "
            "and the plain colour list.")),
        (3, "cache/", tr(
            "Working files from the tools. Always safe to delete: ChromIQ can "
            "make all of it again.")),
        (3, "old/", tr(
            "Measurements a new chart displaced. Kept rather than deleted, so "
            "a re-generate can never cost you ink on paper.")),
        (4, "2026-07-15_103000/", tr(
            "One displacement, stamped with the moment it happened — so several "
            "re-generations never overwrite each other's history.")),
        (3, "verifications/", tr(
            "Checks of the FINISHED profile, over time. The shared "
            "verification chart lives here, and each check gets its own dated "
            "folder — which is what lets a report show how the profile holds "
            "up, or drifts, month after month.")),
        (4, "2026-07-15_1030/", tr(
            "One dated check: its measurement, and the folders below.")),
        (5, "chart/", tr(
            "A copy of the chart that check was measured with, so its numbers "
            "stay tied to the sheet they came from.")),
        (5, "reads/", tr(
            "That check's individual readings, when it was averaged.")),
        (5, "reports/", tr(
            "The measurement report for that check, so each date keeps its own "
            "verdict alongside its readings.")),
        (5, "cache/", tr(
            "Working files from that check. Safe to delete, like every other "
            "cache folder.")),
        (4, "exports/", tr(
            "The verification chart's hand-off files for other programs.")),
        (4, "reports/", tr(
            "Reports that cover SEVERAL of this run's checks at once — the trend "
            "across dates, rather than any single one of them.")),
        (4, "old/", tr(
            "Earlier verification charts, archived when the chart was "
            "replaced. Your dated results are never moved.")),
        (2, "run2/", tr(
            "The next build, with exactly the same shape inside.")),
    ]


def tree_rows():
    """``(drawn, name, explanation)`` for every row of :func:`_structure`, with
    the connector column already drawn.

    Standard tree drawing, and the part worth stating: a level contributes a
    continuing ``│`` to the rows below it only while that level still has
    entries to come. Once it has had its last child, it contributes a blank of
    the SAME width instead — which is what keeps every depth aligned under the
    one above rather than drifting.
    """
    rows = _structure()
    # Is row i the last entry at its own depth, within its parent?
    last = [True] * len(rows)
    for i, (depth, _n, _m) in enumerate(rows):
        for j in range(i + 1, len(rows)):
            d = rows[j][0]
            if d < depth:
                break
            if d == depth:
                last[i] = False
                break
    out = []
    for i, (depth, name, meaning) in enumerate(rows):
        pieces = []
        for level in range(1, depth):
            # Does the ancestor at this level still have entries after us?
            cont = False
            for j in range(i + 1, len(rows)):
                d = rows[j][0]
                if d < level:
                    break
                if d == level:
                    cont = True
                    break
            pieces.append(_TREE_PASS if cont else _TREE_GAP)
        if depth:
            pieces.append(_TREE_LAST if last[i] else _TREE_BRANCH)
        out.append(("".join(pieces), name, meaning))
    return out


def tree_text_column() -> int:
    """The column every explanation starts in — the widest drawn folder plus two
    spaces of air. Exposed so a test can check the alignment against the real
    number instead of pattern-matching runs of spaces, which is ambiguous: a
    continuing "│" is itself followed by two spaces."""
    return max(len(prefix + name) for prefix, name, _m in tree_rows()) + 2


def tree_lines(text_width: int = 62) -> list:
    """The diagram as finished text lines: connectors, folder, explanation.

    Why the explanation is wrapped HERE rather than left to the renderer: in a
    table each row is as tall as its own wrapped text, so the ``│`` glyphs of
    consecutive rows do not meet and the vertical lines come out dashed. Wrapping
    the text ourselves and carrying the row's own connectors onto each
    continuation line keeps every line the same height, so the verticals run
    unbroken from a folder down to its last child — which is what makes it read
    as a diagram (Knut, #130 2026-07-29).
    """
    import textwrap
    rows = tree_rows()
    width = tree_text_column()
    # A continuation line keeps the levels that are still open, and drops this
    # row's own branch mark — the text belongs to the row above it, not to a new
    # entry.
    out = []
    for prefix, name, meaning in rows:
        cont = prefix[:-len(_TREE_BRANCH)] if prefix else ""
        cont += _TREE_PASS if prefix.endswith(_TREE_BRANCH) else _TREE_GAP
        wrapped = textwrap.wrap(meaning, text_width) or [""]
        out.append((prefix + name).ljust(width) + wrapped[0])
        for extra in wrapped[1:]:
            out.append(cont.ljust(width) + extra)
    return out


def _folders():
    """The folder vocabulary: (folder, meaning) rows — the heart of the
    guide since #127. Six short explanations replace thirty file-by-file
    'safe to delete?' judgments."""
    return [
        ("runs/run1, run2 …", tr("One folder per profile build; the newest is current. Old runs are your history — delete a whole runN if not needed.")),
        ("runs/runN/reports/", tr("Things ChromIQ tells you about your PROFILING work: quality-check reports, the re-measure list, and the dated measurement reports for the profile build.")),
        ("runs/runN/verifications/", tr("Checks of a FINISHED profile over time. The shared verification chart lives here, and each check gets its own dated sub-folder (verifications/2026-07-15_1030/ …) holding its measurement, its report, and — in a chart/ folder — a copy of the chart that check was measured with, so the results always stay tied to the sheet they came from. Kept apart from your profiling measurement, so the two never mix — this is what lets the Measurement Report trend how a profile holds up, or drifts, month after month. Replacing the verification chart archives the old one to verifications/old/; your dated results stay where they are.")),
        ("runs/runN/exports/", tr("Files made for use in other programs — the i1Profiler patch set and the plain colour list.")),
        ("runs/runN/cache/", tr("Temporary working files from the tools. Always safe to delete — ChromIQ can recreate everything in here.")),
        ("runs/runN/reads/", tr("Your individual readings when you measure a chart more than once to average.")),
        ("cal/", tr("The optional printer-calibration target and its curves, shared by every run of this project.")),
        ("exports/", tr("Files made for other programs from the Tools menu (project-wide, not tied to one run).")),
    ]


def _features():
    """(feature, input files, output files) rows — Knut's "Files Relating to
    Features" table, so it's clear at a glance what each feature reads and
    writes. File names use “{name}” for the profile's name, like the rest of the
    guide."""
    return [
        (tr("Create Chart"),
         tr("Your settings (or a loaded patch set / preset)"),
         tr("{name}.ti1, {name}.ti2, {name}.channels.json, {name}.strips.json, "
            "{name}_01.tif …; optional {name}.pdf; the exports/ sidecars")),
        (tr("Print Chart"),
         tr("{name}_01.tif … (the chart pages)"),
         tr("{name}.ps (only on the PostScript print path)")),
        (tr("Measure (profiling)"),
         tr("{name}.ti2 (+ {name}.strips.json / .channels.json for the preview)"),
         tr("{name}.ti3; reads/readN.ti3 when averaging; "
            "reports/report_*.json when a measurement report is saved; plus "
            "chart/, a copy of the chart this run was measured with, saved the "
            "moment the measurement starts")),
        (tr("Measure (verification)"),
         tr("{name}-verify.ti2 (the shared verification chart, printed through "
            "the profile)"),
         tr("verifications/<date>/{name}-verify.ti3 and its "
            "verifications/<date>/reports/report_*.json — one dated check, kept "
            "as history and never built into a profile; plus "
            "verifications/<date>/chart/, a copy of the chart that check was "
            "measured with, saved the moment the measurement starts")),
        (tr("Build Profile"),
         tr("{name}.ti3"),
         tr("{name}.icc; merged.ti3 / merged.icc and calibrated.icc when "
            "refinement / calibration are used")),
        (tr("Check & Refine"),
         tr("{name}.ti3 and {name}.icc"),
         tr("reports/Quality_Check_N_{name}.txt, reports/Refine_Strips_{name}.txt")),
        (tr("Create scanner or camera target"),
         tr("A measurement of the chart ({name}.ti3 or a reference .cie/i1Profiler file)"),
         tr("{name}.cht (recognition template) + {name}.cie (reference values)")),
        (tr("Build profile with scanner or camera"),
         tr("Your scan/photo image(s) + the chart's {name}.cht and {name}.cie"),
         tr("The scanner/camera ICC profile; cache/ working copies + a -diag.tif")),
        (tr("Verify a profile (Tools)"),
         tr("{name}.icc and a verification {name}-verify.ti3 (the last step of a "
            "verification run: print through the profile → measure → report → "
            "this tool)"),
         tr("reports/Verify_Profile_N_{name}.txt; a 3D difference map (*.x3d.html)")),
        (tr("Verify against reference (Tools)"),
         tr("A profile / measurement and a reference"),
         tr("reports/Verify_Reference_N_{name}.txt")),
        (tr("i1Profiler export (Tools)"),
         tr("{name}.ti1 / {name}.ti2"),
         tr("exports/{name}-i1profiler.txt and .pxf")),
    ]


def _rows():
    """Groups of (file, folder, description, origin) rows, grouped by where
    they live (folder-first since #127). Lazily built so the tr() calls run
    after the language is set."""
    return [
        (tr("The three files that matter"), [
            ("{name}_01.tif, {name}_02.tif …", "runs/runN", tr("The printable chart pages. Print these."), tr("Create Chart")),
            ("{name}.ti3", "runs/runN", tr("Your measurements — the file the profile is built from. Keep it; any profile can be rebuilt later."), tr("Measure tab (on completion)")),
            ("{name}.icc", "runs/runN", tr("Your finished ICC profile — the file you install or share."), tr("Build Profile tab")),
        ]),
        (tr("The working files of a chart (run folder, top level)"), [
            ("{name}.ti1", "runs/runN", tr("The list of patch colours (the recipe, before it's laid out on paper)."), tr("Create Chart (targen / generators)")),
            ("{name}.ti2", "runs/runN", tr("The laid-out chart: which colour sits where. Measuring needs it."), tr("Create Chart")),
            ("{name}.channels.json", "runs/runN", tr("Records the ink channels and (for engine charts) the exact layout + recipe, so reopening restores everything."), tr("Create Chart")),
            ("{name}.strips.json", "runs/runN", tr("Exact per-strip and per-patch pixel positions, used by the Measure preview (arrow, click-to-jump, split patches)."), tr("Create Chart (engine)")),
            ("{name}.pdf", "runs/runN", tr("The chart as a vector PDF — only when “Also export PDF” is ticked."), tr("Create Chart")),
            ("{name}.ps", "runs/runN", tr("A PostScript copy for printing (bypasses colour management)."), tr("Print Chart")),
            ("{name}.cht / .cie", "runs/runN", tr("The recognition template + reference values for reading a scanned or photographed chart. They stay next to the chart so the scanner tool finds them."), tr("Create scanner/camera target")),
        ]),
        (tr("reports/ — things ChromIQ tells you"), [
            ("Quality_Check_1_{name}.txt", "runs/runN/reports", tr("A readable quality report — grade, explanation, worst strips, full output. Numbered so checks don't overwrite each other."), tr("Check & Refine")),
            ("Refine_Strips_{name}.txt", "runs/runN/reports", tr("The list of strips to re-measure after a check; the guided refinement reads it back."), tr("Check & Refine")),
            ("Verify_Profile_1_{name}.txt", "runs/runN/reports", tr("A readable report from “Verify a profile” — verdict, scores, full output. Numbered so repeated checks keep a history."), tr("Verify a profile (Tools)")),
            ("Verify_Reference_1_{name}.txt", "runs/runN/reports", tr("A readable report from “Verify against reference” — result summary and full output."), tr("Verify against reference (Tools)")),
            ("report_*.json", "runs/runN/reports", tr("Dated PROFILING measurement reports (accuracy & drift), saved automatically after each measurement (Preferences → Reports). The Measurement Report tool reads these back — it builds its figures from the run's .ti3, needs the chart's .ti2 beside it for the ΔE, and reads the instrument name from the .ti3 — and plots how the printer drifts over time. Verification checks keep their own report points under verifications/<date>/reports/, gathered separately."), tr("Measure tab")),
            # Knut asked where the four-way rule belongs, and suggested here
            # rather than in the hierarchy — *"maybe under the Measurement
            # Report function's files and folders?"* (#130, 2026-07-30). He is
            # right: the diagram should show the folders, and the rule for
            # choosing between them belongs with the tool that applies it.
            ("measurement_report_*.pdf", "reports/ — the one that matches the report's scope", tr("A printable PDF of a measurement report, written when you press “Save report as PDF”. It is filed with whatever the report actually covers, so a report always sits beside the measurements it describes: ONE PROFILING RUN goes in that run's reports folder (runs/runN/reports/). ONE DATED CHECK goes in that date's own folder (runs/runN/verifications/<date>/reports/). SEVERAL CHECKS OF ONE RUN — the trend across dates — go in runs/runN/verifications/reports/. SEVERAL RUNS, or the whole profile, go in the project's own reports folder next to runs/. A measurement you browsed to from outside a project gets a reports folder beside the file itself."), tr("Measurement Report tool")),
        ]),
        (tr("exports/ — files for other programs"), [
            ("{name}-colours.txt", "runs/runN/exports", tr("The chart's colours as a plain hex list (RGB charts). Can be pasted back into the New-chart dialog."), tr("Create Chart (best-effort)")),
            ("{name}-i1profiler.txt / .pxf", "runs/runN/exports", tr("The patch set in i1Profiler's formats, for measuring with an i1iSis in i1Profiler."), tr("Create Chart (best-effort)")),
        ]),
        (tr("cache/ — temporary tool files (always safe to delete)"), [
            ("*-patchbox.cht, *-sample.cht", "runs/runN/cache", tr("Prepared working copies of the recognition template the scanner tool reads instead of your original."), tr("Scanner/camera profiling")),
            ("*-diag.tif", "runs/runN/cache", tr("A diagnostic image showing where the tool found each patch — handy if recognition went wrong."), tr("Scanner/camera profiling")),
        ]),
        (tr("Measuring, refining and verification"), [
            ("reads/read1.ti3, read2.ti3 …", "runs/runN/reads", tr("Individual readings when you use “Read again & average”; averaged back into {name}.ti3 when you finish."), tr("Measure tab")),
            ("preconditioning.ti3 / .icc", "runs/runN", tr("Copies of a previous run's measurement + profile, used to aim the next chart better."), tr("Refine")),
            ("merged.ti3 / merged.icc", "runs/runN", tr("The build-time merge of your new measurement with the pre-conditioning one. The installed profile still gets the clean {name}.icc name."), tr("Build Profile (refinement)")),
            ("calibrated.icc", "runs/runN", tr("Your profile with calibration curves baked in (applycal), when the calibration workflow is on."), tr("Build Profile")),
            ("*.x3d.html + x3dom.css / x3dom.js", "runs/runN", tr("The 3D difference map from a profile verification, next to the measurement it belongs to (the three files reference each other)."), tr("Verify profile (Tools)")),
        ]),
        (tr("Verification runs — checking a finished profile over time"), [
            ("{name}-verify.ti1 / .ti2 / .cht …", "runs/runN/verifications", tr("The shared verification chart for this profile — usually smaller than the profiling chart (one page is plenty). You make it once on the Create Chart tab with Run type = Verification, and every future check reuses it, so results always compare like with like."), tr("Create Chart (Run type = Verification)")),
            ("{name}.ti1 / .ti2 / .channels.json …", "runs/runN/chart", tr("A copy of the chart this profile run was measured with, kept so the measurement always describes a chart you still have. ChromIQ saves it automatically the moment a measurement starts. If you later change or re-create the chart, the “Restore Used Chart” button beside the Profile run brings this one back — your measurement is never touched. Only the chart's own files are copied: never the measurement, the profile or ChromIQ's own book-keeping."), tr("Measure tab (Run type = Profiling)")),
            ("{name}-verify.ti1 / .ti2 / .channels.json …", "runs/runN/verifications/<date>/chart", tr("A copy of the verification chart this dated check was measured with, kept so the results always describe a chart you still have. ChromIQ saves it automatically the moment a verification measurement starts. If you later change the verification chart, the “Restore Used Chart” button beside the Verification date puts this one back — your measurements are never touched. Page images are rebuilt from these files, and are stored here as well when the chart carries no layout recipe to rebuild them from."), tr("Measure tab (Run type = Verification)")),
            ("{name}-verify.ti3", "runs/runN/verifications/<date>", tr("One dated verification measurement: the verification chart printed THROUGH the profile (colour management ON) and measured, to see how accurate the profile still is. Each check lands in its own date-stamped folder, so nothing is overwritten. Tagged internally so it never builds a profile and never mixes with your profiling measurement."), tr("Measure tab (Run type = Verification)")),
            ("report_*.json", "runs/runN/verifications/<date>/reports", tr("The accuracy report for that one dated check. The Measurement Report tool trends these verification checks over time — entirely separately from the profiling runs above — so you can watch a profile hold up, or drift, month after month."), tr("Measure tab (Run type = Verification)")),
        ]),
        (tr("Project-level files and folders"), [
            ("project.json", "(project root)", tr("ChromIQ's manifest: current run + run history. Please don't edit."), tr("Created on first use")),
            ("meta.json", "runs/runN", tr("Remembers the run's settings so reopening restores them."), tr("Each run")),
            ("cal/{name}-cal.*", "cal", tr("The calibration chart, its measurement (-cal.ti3) and curves (-cal.cal); the chart's own exports live in cal/exports."), tr("Calibration workflow")),
            ("exports/{name}-i1profiler.*", "exports", tr("i1Profiler exports made from the Tools menu."), tr("Tools menu")),
            ("Where are my files.txt", "(project root)", tr("This guide as a text file, updated when the folder layout changes. Edit or delete freely."), tr("Created on first use")),
            ("scanner-test-targets/", "(output folder)", tr("Next to your projects: every standard scanner target's layout file (.cht), yours to inspect or tweak — ChromIQ prefers the files here over its built-in copies, puts missing ones back, and never overwrites your edits. Demo scans land here too."), tr("Scanner/camera profiling")),
        ]),
    ]


def file_guide_html() -> str:
    """Rich-text (HTML) table for the Welcome/Help card (Knut)."""
    def esc(s: str) -> str:
        return html.escape(s)

    parts = [f"<p>{esc(_intro())}</p>"]
    # An empty line of air after every section headline (Basti). Qt's rich-text
    # engine collapses a <p> bottom margin against a following <table>, so the
    # blank line is an explicit small spacer paragraph instead.
    spacer = "<p style='font-size:5px; margin:0'>&nbsp;</p>"

    # Section 1 — "Project File Structure": the folder hierarchy as a diagram
    # (Knut, #130 2026-07-29). The connector column is monospace and
    # pre-formatted, which is what keeps every level aligned under the one
    # above; a proportional font would stagger them.
    parts.append(f"<p style='margin:16px 0 0; font-size:15px'><b>"
                 f"{esc(tr('Project File Structure'))}</b></p>")
    parts.append(spacer)
    _lead = tr("Every folder a project can contain, and what lives in it. "
               "“{name}” stands for your profile's name.")
    parts.append(f"<p style='margin:0 0 6px'>{esc(_lead)}</p>")
    parts.append(
        f"<pre style=\"font-family:{_MONO}; font-size:12px; margin:2px 0 0; "
        f"line-height:100%\">"
        + esc("\n".join(tree_lines()))
        + "</pre>")

    # Section 2 — "Files Relating to Features": what each feature reads/writes.
    parts.append(f"<p style='margin:20px 0 0; font-size:15px'><b>"
                 f"{esc(tr('Files Relating to Features'))}</b></p>")
    parts.append(spacer)
    parts.append("<table cellspacing='0' cellpadding='4' width='100%' "
                 "style='border-collapse:collapse'>")
    parts.append(
        "<tr style='color:#888'>"
        f"<th align='left'>{esc(tr('Feature'))}</th>"
        f"<th align='left'>{esc(tr('Input Files'))}</th>"
        f"<th align='left'>{esc(tr('Output Files'))}</th></tr>")
    for feat, ins, outs in _features():
        parts.append(
            "<tr>"
            f"<td valign='top'>{esc(feat)}</td>"
            f"<td valign='top'>{esc(ins)}</td>"
            f"<td valign='top'>{esc(outs)}</td></tr>")
    parts.append("</table>")

    # Section 2 — "All File Types and Their Use": the folder map + file detail.
    parts.append(f"<p style='margin:20px 0 0; font-size:15px'><b>"
                 f"{esc(tr('All File Types and Their Use'))}</b></p>")
    parts.append(spacer)
    parts.append(f"<p style='margin:14px 0 0'><b>{esc(tr('What the folders mean'))}</b></p>")
    parts.append(spacer)
    parts.append("<table cellspacing='0' cellpadding='4' width='100%' "
                 "style='border-collapse:collapse'>")
    parts.append(
        "<tr style='color:#888'>"
        f"<th align='left'>{esc(tr('Folder'))}</th>"
        f"<th align='left'>{esc(tr('What it is'))}</th></tr>")
    for folder, meaning in _folders():
        parts.append(
            "<tr>"
            f"<td valign='top'><code>{esc(folder)}</code></td>"
            f"<td valign='top'>{esc(meaning)}</td></tr>")
    parts.append("</table>")
    for title, rows in _rows():
        parts.append(f"<p style='margin:14px 0 0'><b>{esc(title)}</b></p>")
        parts.append(spacer)
        parts.append("<table cellspacing='0' cellpadding='4' width='100%' "
                     "style='border-collapse:collapse'>")
        parts.append(
            "<tr style='color:#888'>"
            f"<th align='left'>{esc(tr('File'))}</th>"
            f"<th align='left'>{esc(tr('Folder'))}</th>"
            f"<th align='left'>{esc(tr('What it is'))}</th>"
            f"<th align='left'>{esc(tr('Created by'))}</th></tr>")
        for f, folder, desc, origin in rows:
            parts.append(
                "<tr>"
                f"<td valign='top'><code>{esc(f)}</code></td>"
                f"<td valign='top'>{esc(folder)}</td>"
                f"<td valign='top'>{esc(desc)}</td>"
                f"<td valign='top'>{esc(origin)}</td></tr>")
        parts.append("</table>")
    parts.append(f"<p style='margin-top:14px'>{esc(_outro())}</p>")
    return "".join(parts)


def file_guide_body() -> str:
    """Plain-text version for the ``Where are my files.txt`` sidecar."""
    lines = [_intro(), ""]
    # The same hierarchy as the card, and here it is even simpler: a text file
    # is already monospace, so the tree needs no markup at all (#130, Knut).
    lines.append("=== " + tr("Project File Structure").upper() + " ===")
    lines.append("")
    # Exactly the same drawn lines as the card — one source, so the two can
    # never disagree about the folder layout.
    lines.extend(tree_lines())
    lines.append("")
    lines.append("=== " + tr("Files Relating to Features").upper() + " ===")
    lines.append("")
    for feat, ins, outs in _features():
        lines.append(f"  • {feat}")
        lines.append(f"      {tr('Input Files')}:  {ins}")
        lines.append(f"      {tr('Output Files')}: {outs}")
    lines.append("")
    lines.append("=== " + tr("All File Types and Their Use").upper() + " ===")
    lines.append("")
    lines.append(tr("What the folders mean").upper())
    lines.append("")
    for folder, meaning in _folders():
        lines.append(f"  • {folder}")
        lines.append(f"      {meaning}")
    lines.append("")
    for title, rows in _rows():
        lines.append(title.upper())
        lines.append("")
        for f, folder, desc, origin in rows:
            lines.append(f"  • {f}  [{folder}]")
            lines.append(f"      {desc}")
            lines.append(f"      Created by: {origin}")
        lines.append("")
    lines.append(_outro())
    return "\n".join(lines)
