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

## The patch set editor's CMYK and multi-ink sets (#207)

**Ruling: Basti, 2026-10-21** (the approver while Knut is away), on issue
#207: *"option 2"*, port all of the research branch's work, the bug fixes and
the design changes alike. His condition: **the RGB part of the editor must not
change.** Saved charts never change; only a patch set generated from now on
follows the new rules.

> **⏳ Awaiting confirmation. Confirmed by:** *nobody yet.* How it was built,
> measured by the suite and on screen.

| | As built (New patch set, device CMYK or CMYK + extra inks) |
|---|---|
| Ensure unique colours | moves a patch only along the inks it already has, never switches one on or off, never over the ink limit; paper white and single-ink patches are never moved (R3) |
| Near-neutral greys with a preconditioning profile | inside the ink limit (R4) |
| Ink order | the generators get Argyll's order (CMYKOGV...), whatever order the inks were added in (R5) |
| Neutral grey ramp below a 300 % limit | spread from paper white to the darkest grey the limit allows, every step its own patch; unchanged at 300 % and more (R7) |
| New ticks, all OFF unless chosen | "more light steps" on Per-ink ramps (R6), "as grid" on Ink-pair overprints (R2), "3-4 inks per patch" on Fill remaining gaps (R1): mostly 3- and 4-ink patches, about 8 % with 5+ inks, some on the ink-limit face, complementary inks together half as often (by the preconditioning profile's measured hues, else by the ink letters) |
| "Multi-ink, professional layout" (★, Load setup from preset) | listed only while the device is CMYK or CMYK + extra inks; ticks the rows above; keeps inks, ink limit, fill size, instrument, paper and layout |
| RGB | unchanged: same patches for every generator switch, same window, same setup list |
| A chart made before | loads and lays out exactly as saved: the patches are in the chart file, nothing regenerates them |

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

## Two photo papers for 4 x 6 in printers (jctay 149803, 4.3.10)

#### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

Create Chart offers "10 × 15 cm (100 × 150 mm)" (code `10x15cm`) and
"Postcard (100 × 148 mm)" (code `postcard`, Canon SELPHY and similar) beside
"4×6\" (102 × 152 mm)", with a paragraph in the paper size's ⓘ. printtarg is
given the millimetres (`PAPER_PRINTTARG_ARG`: `-p100x150`, `-p100x148`), and a
generated name spells them `100x150mm` / `100x148mm`, as Knut's own 10 x 15 cm
presets do. The codes are new, so an existing "4x6" chart, a custom
"100x150" chart, a preset or a project loads and lays out exactly as saved.
Capacities per sheet are measured like every other entry
(`scripts/measure_photo_paper_capacity.py`, printtarg -t300 with each
table's own flags; each table's 4x6 value measured again first as a check of
the method, all equal). The i1Pro 3 Plus is not offered either (as for 4x6).

**The preset lists (4.3.11, Basti 2026-10-23).** With the paper filter on,
"10 × 15 cm (100 × 150 mm)" lists every preset whose paper is a custom
100 x 150 mm (Knut's built-in i1Pro cards among them), and "Postcard" every
custom 100 x 148 mm one, exact to half a millimetre in the orientation the
code spells (`core.curated_presets.paper_matches`). Those presets are still
Custom (`paper_class`), so they stay in the Custom list too, and they load
and lay out exactly as saved: only which list shows them changed. Every other
paper's list is unchanged. Driven on screen: in 4.3.10 the 10 × 15 cm list
held nothing but "none".

## Answered, and so not built

Whether importing a chart file should also offer "replace only the chart",
meaning take the patches from the file and lay the chart out at the settings on
screen, alongside the three choices it has now. Asked on the issue 2026-09-11
and answered the same day by Knut: **no**. So the chart-file import keeps its
three choices and never lays a chart out again, and "replace only the chart"
stays where it is, on the patch-set load.

## FD-9 (Beta): creating, loading and generating an FD-9 chart

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

*Written 2026-11-03 for PR #213 (the Konica Minolta FD-9, written and
contributed by lessbones). It replaces the contribution's five successive
proposal blocks, which contradicted each other (a 12 x 25 / 300-patch ceiling,
then none; square patches only, then rectangles). What the app does now,
verified by tests and on screen without an FD-9.*

* **Only with FD-9 support on** (Preferences > Beta, off by default, restart
  to apply). With it off "FD-9" is in no list (Guided's and Manual's
  Instrument, the layout panel, Preferences > Chart Layout), and a chart file
  that names the FD-9 loads as it did in 4.3.21 (its instrument is not
  recognised, so it is taken as an i1Pro chart, as any unknown name is).
* **Instrument "FD-9"** in Guided and in Manual. The chart is laid out by
  ChromIQ's own FD-9 layout (`workflow/fd9/chart.py`), never printtarg:
  one or more sheets, patches 6-30 mm wide and high, gaps of 0-5 mm (default 8 x 8 mm,
  1 mm), at least 15 mm free on each side, the middle of the first row 42 mm
  from the leading edge and at least 33 mm free at the trailing edge, four 3 mm
  marks around the patch area and an arrow showing which end goes in first.
  On a chart of several sheets every sheet also carries its page number,
  "N/M" (for example "2/3"), small, at the top left in the leading clear
  area, upright like the clip border text: it reads the right way up with
  the arrow pointing up, the way the person standing in front of the FD-9
  sees the sheet while feeding it (4.3.26, lessbones, who owns the unit;
  4.3.25 printed both turned 180 degrees, upside down for that person); a
  chart of one sheet
  has none, and there is no option for it. The page number is for the
  person feeding the sheets, not an automatic page-identity check (that is
  the sheet check after each sheet). The FD-9 clip border may be printed
  as well (below).
* **The FD-9 clip border** (4.3.25), on by default since 4.3.26
  (`workflow/fd9/furniture.py::FD9_CLIP_BORDER_DEFAULT`): lessbones measured
  real sheets with it and the page number, the labels read fine and the four
  marks were found every time. In Manual, a recipe in which a person
  switched it off keeps Off, also one stored with Save as Defaults (which
  stored the FD-9 recipe as an i1Pro one before 4.3.26); only a person's
  answer is stored, never what the panel merely showed. Guided has no
  clip-border setting for the FD-9 and always prints it, with the Notes box,
  as the default says (the owner, 4.3.26 review r1). It is
  a band at most 14 mm deep in the free space after the last row of patches
  (at least 10 mm from each side and 6 mm before the trailing edge), upright
  like the page number. The 33 mm at the trailing edge stay: the sheet is
  still in the FD-9's rollers while the last row is read (lessbones). It
  takes no room from the patches, and every page that carries it, or the
  page number, goes through the detector check before the chart is saved.
* **Sheets:** 137x300, A4, A4 landscape, Letter, Letter landscape, A3,
  329x483 and 330x660 in Guided. Manual uses the ordinary Custom paper entry
  for any 137-330 mm across the feed and 170-660 mm along it. Landscape A4 (297 x 210) and Letter (279.4 x
  215.9) are inside that envelope and are laid out by the same geometry
  (`tests/test_fd9_beta_option.py`).
* **Shared layout controls:** patch width and height, inter-patch gap along
  the feed, strip gap across it, paper and Pages use the existing controls.
  Rectangles and zero gaps are supported. There is no separate FD-9 size
  dialog or Guided Custom sheet button. Edit layout defaults opens the normal
  Chart Layout preferences and does not enable printtarg for the FD-9.
  Other unsupported controls stay greyed, with their state restored on leaving
  FD-9. Output, printer calibration, randomisation and Clip-border content
  (what the FD-9 clip border shows) remain available.
* **Multiple pages:** the existing Pages selector controls Guided capacity.
  A patch set exceeding one sheet is split into ordinary numbered TIFFs and
  one PDF/TI2, with unique sample IDs/locations across the chart. Only complete
  columns pad the last sheet. Schema-2 physical sidecars contain a grid per
  page; schema-1 printed charts remain unchanged and readable.
* **Files:** `<stem>.ti2` with the header every engine chart has
  (`DESCRIPTOR`, `CREATED`, `TARGET_INSTRUMENT "Konica Minolta FD-9"`,
  `APPROX_WHITE_POINT`), quoted `SAMPLE_LOC`, `<stem>.fd9.json` (the physical
  grid and marks the measurement uses) and the usual `.strips.json`.
  `.fd9.json` is a chart companion: it is copied, stashed, archived and
  imported with the chart. Padding cells are paper white with the engine's
  media white aim. With the clip border off nothing but marks, arrow,
  patches and the page number is on the sheet, so the run description is
  not printed. With it on, the band shows the content chosen under
  Clip-border content: the Notes box by default (patch count, FD-9, paper,
  date, page N/M, strips on the page, the profile name and lines to write
  on), or text, which may carry the run description through
  `{rundescription}`. The TIFF is not stamped.
* **Calibration charts** put one ink's ramp per column, paper white first.
* **The patch set editor** (Tools) opens an FD-9 chart like any other
  (4.3.25), and its edited patch set goes back to Create Chart, which lays
  it out with the FD-9's own builder (`tool_availability.md`).

## FD-9 (Beta): an FD-9 chart shown turned on screen

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.*

*Written 2026-11-04 from the owner's request (4.3.25): "a display-only
rotation of FD-9 charts, a sub-option under the FD-9 support, Off / 90 /
180 / 270". What the app does now, verified by tests
(`tests/test_fd9_4325_display_rotation.py`) and on screen with simulated
FD-9 data.*

* **Preferences > Beta, "Turn FD-9 charts on screen"**, indented under FD-9
  support: Off (default), 90°, 180°, 270°, clockwise. Greyed, keeping its
  value, while the FD-9 support box is unticked; with FD-9 support off for
  this run it has no effect at all. Applies when Preferences closes with OK,
  without a restart (`fd9_display_rotation`, `workflow/fd9/support.py`).
* **Where:** the chart preview of Create Chart and of the Measure tab (the
  FD-9's layout preview and its scan). Only pages that are an FD-9 chart's
  (beside a `.fd9.json` and a `.ti2` naming the FD-9), and the Measure tab's
  own FD-9 images, are turned; every other chart, and the Print tab, the
  soft-proof window and every other preview, are shown as before.
* **Display only:** the TIFF pages, PDF, `.ti2`, `.fd9.json`, the print and
  the measurement never change.
* **What follows the turn:** the page, its frame, the margin guide lines and
  the measured-margin lines, the live and saved colours, the row outlines of
  the scan, the hover outline and the patch under the pointer. **What does
  not:** every number about the chart describes the paper as printed
  ("Measured from Preview" Left/Right/Top/Bottom, the pointer's X and Y from
  the printed top-left corner, Chart layout information); and anything whose
  meaning is a direction on screen: the expected half of a split patch is
  the top-left triangle on screen at every angle, as the legend says, and
  the legend chip stays upright, placed under the lowest patch as shown.
* **90° and 270°** lay the sheet out sideways and fit it to the preview as
  a landscape page.

* **Why a person would turn it (4.3.26).** Since 4.3.26 everything written
  on an FD-9 sheet is printed upright, so Off already shows it readable, as
  the person in front of the FD-9 sees it. The option is kept for looking at
  a tall sheet sideways in a wide preview (90° and 270°); 180° now shows the
  text upside down. Its ⓘ no longer says that the sheet's text is printed
  turned round or that 180° makes it read the right way up.
