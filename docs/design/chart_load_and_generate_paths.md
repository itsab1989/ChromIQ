# Every path that loads a chart, and every path that builds one — Design Record (#182)

> **Status:** written 2026-09-11 in answer to Knut's question in issue #182:
> *"What are all the different paths that loads a chart (as it was built) and
> the paths that Generate a new chart from changes? List all the various paths,
> so it can be verified if each possible path correctly loads or generates …
> Make sure all places where a chart is loaded or generated is doing this
> correctly."*
>
> **⏳ Awaiting confirmation. Confirmed by:** *nobody yet.* Every row below was
> MEASURED by driving the real app in a real window and watching the run folder,
> so it records what the app does. Whether that is what it should do is Knut's
> or Sebastian's to say (CLAUDE.md, "only CONFIRMED behaviour may be written
> into a specification").

## How this was measured

Five drivers, thirteen windows on the real display, forty-five captures, each
one checked to hold a real ChromIQ window rather than the desktop behind it. The
run folder was listed before and after every action, so "loads" below means no
chart file changed and "builds" means one did. Two of the rows were also
verified independently from the source afterwards: that changing tabs makes no
chart call at all, and that importing a chart file runs no layout tool.

## Paths that SHOW a chart that was already built

| What the user does | What happens | Expected |
|---|---|---|
| Changes the profile run | Loads. A queued preview redraw is cancelled first, so a redraw in flight cannot land on the new run | yes |
| Changes the run type (Profiling, Verification, Calibration) | Loads. An empty target clears the preview and says why. The calibration and verification charts are both resolved from their own folders | yes |
| Changes tabs | No chart call at all | yes |
| Opens a project | Loads | yes |
| Restores a session, duplicates a run | Loads | yes |
| Opens a chart file that is already inside a project | Opens it in place, or offers to open the project it belongs to. The layout tool never runs | yes |
| Restore Used Chart, the files half | Puts the stored copy back, all together or none | yes |

Measured: seven run switches with the preview auto-update both off and on, five
run-type changes, ten tab changes. No chart file was written in any of them.

## Paths that BUILD a chart

| What the user does | What happens | Expected |
|---|---|---|
| Generate Chart | Builds, by one of seven routes | yes |
| A layout setting changes with auto-update on, run not yet measured | Re-lays out and rewrites that run's chart. Measured: 300 to 350 dpi turned a four-page chart into one page | yes |
| The same, run already measured | Declines, and says why | yes |
| Loads a patch set (.ti1), all five destinations | Builds. A full replace archives the old chart first | yes |
| Applies a patch set from the Editor | Builds | yes |
| A built-in preset | Two kinds: a layout preset lays its patch set out at the preset's settings; a preset that ships finished files copies them exactly as they are | yes |
| Restore Used Chart, the pages half | Redraws only when the stored copy carried no page images, and the chart itself is kept if the redraw would change it | yes |
| Imports a chart file (.ti2) | Copies. When no printable pages came with it, they are drawn from what the file itself records | see below |

## The chart file import (Knut, 2026-09-11)

He chose between two readings of his own *"loading a ti2 should generate"*:

> *"A agree with implementing your point 1: 'Rebuild only the missing pages,
> from the recipe the file itself carries. That fixes the unprintable run and
> changes nothing else. A chart you have already printed still reprints exactly
> as it was.'"*

So an import is not a re-layout. The pages are drawn from the chart file's own
patch order, instrument and paper; the imported file is never touched; a chart
that arrives with its pages is left alone. It says nothing to the user, which he
also ruled: *"it is the ti2 file that is imported, and any existing tif files
may not show according to the settings, margins and other features in the Create
Chart tab in ChromIQ (it may also come from a completely different external
source)."*

## Two ways of laying a chart out again, and they give different sheets

This is the one thing in this area a user can get wrong, and it is worth stating
plainly because both behaviours are correct for what they are for.

* **From the chart's own record.** Reproduces the sheet that was printed. This
  is what Restore Used Chart does, and what an import now does when pages are
  missing.
* **From the settings on screen.** Does not. This is what "Replace only the
  chart" does on a patch-set load when no settings file came with the file.

## Faults found, and what became of them

* **A chart in the project you have open could be announced as another
  project's**, with an offer to open the project already open. Two spellings of
  one folder were compared: one side resolved the path and the other did not, so
  the moment the ChromIQ folder was reached through a symlink they differed.
  Nothing was ever generated by mistake. Fixed.
* **A chart file imported on its own left a run that could not be printed.**
  Fixed per the ruling above.
* **A chart of a single page was invisible to the windows that show it.** One
  page is named without a page number and the loader looked only for numbered
  ones. Found by driving the import on screen after the fix above, and by
  nothing else. Fixed.
* **The project the import made was never opened.** Knut, 2026-09-11: he opened
  a chart file from outside the ChromIQ folder, typed `scan-test2` in the window
  that asks for a name, and came back to a Profile-run bar still locked on "New
  run", red text saying *"You already have a project with this name"*, and
  Generate Chart refusing with *"This chart is loaded from elsewhere"* until an
  unrelated "Edit patch recipe" tick was made. Three complaints, one omission:
  the project was created on disk and nothing opened it, so the name box (which
  ChromIQ itself had filled) matched a project that was not the open one, and
  Create Chart judged the chart to belong to somebody else. Every other route
  that ends in a project opens it and points the bar; the two that CREATE one
  did not. Reproduced on screen before and after. Fixed.
* **A file that is not a chart was copied into a new project as its chart.**
  The chooser hides everything but `.ti2` in its list, and its NAME BOX takes a
  typed, pasted or dragged name whatever it ends in. Measured: picking a page
  bitmap made a project whose `.ti2` begins `II`, which cannot be printed,
  measured or built from, and the app said the files had been copied. The
  import now reads the file first and refuses before anything is made. The
  refusal's wording is M-IMPORT-NOT-A-CHART and is in §M-PROPOSED, awaiting
  review.

## Not one path, though the source has two

The Print tab carries a complete second handler for opening a chart file that
nothing calls: the button moved to the masthead and the handler stayed. So "the
load .ti2 button may have several paths" is two in the source and one in the
app. It is recorded rather than removed, because a helper nobody calls may be a
dropped branch rather than dead code, and that is not a sweep's decision.

## Strip and patch patterns (forum report and Knut's ruling, 2026-10-03)

> **⏳ Awaiting confirmation. Confirmed by:** *nobody yet.* Measured in the real
> app and by the suite; the rule itself is Knut's (#182 5965589190, "use the
> rules defined for the strip and patch patterns defined by ArgyllCMS"), the
> rows below are how it was built and wait for his or Sebastian's word.

| Path | Labels | Pattern check |
|---|---|---|
| Generate Chart, a preset, a patch set (.ti1) loaded or applied from the Editor, the live preview | ArgyllCMS's, from the two patterns | Refused before anything is written when the readers could not read the chart back; the box is red, the reason is under the preview, Generate is unavailable, the live preview does not re-draw |
| Restore Used Chart, the pages half; the verification page rebuild | The labels the stored chart was printed with (ArgyllCMS's, or ChromIQ's old rule for a chart from before 4.3.3-beta.7, recognised from its own locations) | None: the chart is already on paper |
| A stored or preset pattern that cannot be used | Loads unchanged and shows red | Generate stays unavailable until it is changed |

## A built-in preset and the stamp (beta 12, #182)

> **⏳ Awaiting confirmation. Confirmed by:** *nobody yet.* The rule is Knut's
> statement that the presets are designed and saved without the stamp; how it
> is built waits for his or Sebastian's word.

* **Every built-in preset sets "Stamp settings down the right edge" OFF** when
  it is chosen, in Create Chart Manual and in From Profile Gamut. Until beta 11
  only 41 of 189 did (the Pharmacist charts, the photo cards, the i1 Maximised
  charts); the other 148, all 26 CR30 hexagon charts among them, left the box as
  it was, and on a new target that is ON (Basti's A3 Plus 616 verification,
  2026-10-07; the CR30 stamp over the patches).
* A user preset keeps the stamp it was saved with (`stamp_commands`).
* **Unchanged, and a question to Knut:** a new target still starts with the
  stamp ON (`chart_stamp_commands`, per_target_settings.md §1.2).

## Answered, and so not built

Whether importing a chart file should also offer "replace only the chart",
meaning take the patches from the file and lay the chart out at the settings on
screen, alongside the three choices it has now. Asked on the issue 2026-09-11
and answered the same day by Knut: **no**. So the chart-file import keeps its
three choices and never lays a chart out again, and "replace only the chart"
stays where it is, on the patch-set load.
