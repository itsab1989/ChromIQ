# Changelog

## v4.1.3-beta.15

Knut's review of beta.13, in full. Every one of the faults he reported turned
out to be larger than it looked from the outside.

### Added

- **Three new help cards**, one for each of the tools that had none: “Design a
  custom patch set for a chart”, “Spot-read the colour of a surface”, and
  “Show or compare a chart's patch set in 3D”. Each explains what every button
  in the window does, and the patch-set card answers the question Knut asked
  directly — “New patch set” replaces what is in the window, “Add” extends it.

- **Keyboard shortcuts now appear in tooltips.** Hovering a button that has a
  shortcut shows it in brackets after the name — “Open Project (⌘O)”. The five
  main buttons, one per tab, had no tooltip at all before; they now carry both
  a name and their ⌘↵ shortcut.

- **Nineteen new i1Pro charts** with 7.5 mm patches, in A4, US Letter and A3,
  from 162 to 4212 patches. Two older A4-924p charts were withdrawn.

### Fixed

- **Help cards printed blank pages.** A table row that would not fit was moved
  two pages on instead of one, leaving a whole sheet carrying nothing but the
  repeated table header. Eight such sheets across the eighteen cards. “Overview
  of Main Actions” goes from 5 sheets to 3, and the folder guide from 12 to 9.

- **The patch size shown for a chart was wrong by a fifth.** All nine of the
  “by Pharmacist” charts reported patches 20 % larger than they are — 8.99 mm
  where the true size is 7.48 — because ChromIQ read the wrong figure for the
  chart's resolution and fell back to assuming 300 dpi. The two panels beside
  the preview now agree with each other and with the printed sheet.

- **The margin guide lines sat in the wrong place on later pages.** On any
  chart with roughly more than twenty-one strips a page, the top margin was
  measured to the strip labels instead of the first row of patches — 8 mm where
  38 is right. It also raised a false warning that the top margin was below the
  instrument's minimum, and overstated the strip length by 24 mm.

- **Settings in Preferences ▸ Chart Layout vanished when you switched
  instrument.** Changing the instrument reset the density box to its first
  entry, so ChromIQ looked for settings that had never been saved under that
  combination and showed its own defaults instead. Nothing was ever lost from
  disk — cancelling and reopening brought it all back — but there was no way to
  tell that from the screen. The tab now says which you are looking at, and
  explains that it opens on the combination your current chart uses.

- **Choosing a preset with no project name created one you did not ask for.**
  It made up a folder named after the date and built the whole chart into it,
  with no message at all. ChromIQ now asks for a name. Two further routes that
  could invent a project have been closed as well — including one where merely
  asking “is anything at risk here?” created the folder.

- **File dialogs opened in your home folder.** Eight of the nine started there
  rather than in your ChromIQ folder, including “Open Chart File (.ti2)”.

- **Help text sent you to a button that had moved** — and, worse, to a button
  that still exists in that spot and does something else. Preferences was
  described as being at the top left when it is at the top right.

- **Three tooltips told Mac users to press “Ctrl”.** The chart editor's Undo and
  Redo said Ctrl+Z while the Help card, two clicks away, said ⌘Z for the same
  key. Fifteen more hard-typed shortcuts were sitting in the translations, each
  wrong in its own language's spelling.

- **Importing a set of charts could quietly change every chart in a family.**
  The check that is meant to catch a chart that does not belong compared each
  batch against its own first file, so a difference shared by the whole batch
  passed unnoticed. It now compares against the family ChromIQ ships, and
  refuses rather than folding the difference in.

- **Importing chart-layout settings could overwrite the ones you had.** The
  import accepted any JSON file and replaced real settings with defaults.

- **The Start Measurement button lost its keyboard hint.** It was the only one
  of the five main buttons that did not show its shortcut.

### Behind the scenes

- The test suite could write into your real ChromIQ preferences folder. Only
  one test reached that far and it happened to guard against it, but nothing
  enforced it; the suite now redirects the preset store to a scratch folder the
  way it already does for the demo projects.

## v4.1.3-beta.14

### Added

- **A "Close Project" button.** Third along the top left, beside "Open Chart
  File". It puts ChromIQ back to the way it looks on a fresh install, with no
  project open. Nothing is deleted and nothing on disk changes — every run,
  chart, measurement and profile stays exactly where it is, and "Open Project"
  brings it all back. Only what you have typed and not yet used is let go: the
  name in "Printer profile project name" and the run description beside it. A
  confirmation window explains all of that before anything happens, and the
  button is greyed with a reason when there is no project to close.

- **A greyed tab now tells you why.** During a measurement or a profile build
  the other tabs are locked; hovering one used to say nothing at all, which
  read as a fault rather than a lock. Each greyed tab now explains what is
  running and when it will come back — and its own explanation is put back
  afterwards, so a verification run's "not for a verification" note survives a
  measurement.

- **A keyboard shortcut for the top-left buttons.** ⌘O / Ctrl+O opens a
  project, ⇧⌘O / Ctrl+Shift+O opens a chart file. Both obey the same locks as
  the buttons themselves.

### Fixed

- **ChromIQ could create a project you never asked for — a third way.** Simply
  opening a loose chart file with nothing loaded was enough: the question "is
  this chart inside my project?" created one to compare against, leaving a
  folder named after the date beside your real work. The app then thought it
  was working in that phantom, and the next chart you built went into it.

- **Closing the Soft-proof window could stop ChromIQ noticing that anything
  had finished.** Opening Soft-proofing and closing it again quietly detached
  the part of ChromIQ that listens for a tool completing. The next measurement
  would read the whole chart and then appear to hang for ever: the tabs and the
  buttons along the top stayed greyed, because nothing was left to hear that it
  had ended. Only quitting and reopening cleared it.

- **Soft-proofing removed the picture you were looking at.** Changing the ΔE
  threshold, the rendering intent or the highlight colour started a new proof
  and deleted the previous one's files immediately — so the preview went blank
  and "Save proof" quietly did nothing while still looking available. The old
  files are now kept until the new proof is ready.

- **A patch set you loaded was not the one ChromIQ built.** After loading an
  i1Profiler patch set or a .ti1 and pressing "Generate Chart", ChromIQ could
  quietly build a completely different chart from a fresh patch calculation —
  measured, two patches in and 525 out, with no message beyond a line in the
  log. It happened for two separate reasons: in Guided mode the loaded set was
  ignored outright, and in Manual mode the act of binding the set to a run
  reset the patch-recipe settings, which ChromIQ then read as you having asked
  for a different chart. Unlocking "Edit patch recipe (override preset)" and
  changing a setting still gives you a fresh chart, as it always did.

- **Loading a second patch set discarded the first.** After loading a patch set
  and then loading another — or having a second load fail — the first one was
  deleted from disk while ChromIQ still believed it was in use. Pressing
  "Generate Chart" then silently built a completely different chart from a
  fresh patch calculation, with only a line in the log to say so.

- **A wrong ArgyllCMS path could lock you out of the app.** If a tool could not
  start at all — a mistyped path in Preferences, a moved installation — nothing
  ever reported that it had failed. The window stayed greyed as though the
  build were still going, including Preferences itself, which is the one place
  the path could have been corrected. The only way out was to quit and restart.
  ChromIQ now says which program it could not start and points at the setting
  that fixes it.

- **The "Close Project" button stayed greyed after generating a chart or
  opening a project.** It was watching the wrong thing.

- **Building a chart left the rest of the window live.** You could switch to a
  different project, open another chart, or open the Tools menu while targen
  and printtarg were still writing into the current run. A measurement and a
  profile build had always locked those buttons; a chart build now does too.

- **Print Chart's settings were lost when you closed the project.** A change to
  Rendering intent made on the Print Chart tab was not written down if you
  closed the project from that tab — the same change made on any other tab was
  kept.

- **A measurement and a profile build running together unlocked the tabs too
  early.** Whichever finished first re-enabled everything, leaving the window
  open for editing while the other was still running.

- **ChromIQ left large temporary files behind.** Soft-proofing wrote a fresh
  set of full-size TIFFs for every proof — around 60 MB — and never removed the
  previous ones, so nudging the ΔE threshold a few times could leave hundreds
  of megabytes on disk until the next reboot. The patch-set editor's "Apply"
  left a complete chart behind every time it ran. Six more places did the same
  on a smaller scale. All are now cleaned up.

- **The patch-set editor described what it does incorrectly.** Its "Overwrite"
  window said the page layout was carried across and locked. Neither was true:
  only the patch set moves, the layout comes from the Create Chart tab, and the
  page-layout panel stays editable. It also said measurements were "kept" when
  they are moved into the run's "old" folder. The window now says what actually
  happens.

- **A project deleted outside ChromIQ came back.** If "restore last session"
  was on and you had removed the folder in Finder, ChromIQ still believed the
  project was open and would recreate it.

- **A new project no longer starts with a name you did not choose.** The
  "Printer profile project name" box was pre-filled with "ChromIQ Test Chart",
  so a brand-new install showed a location line pointing into a project that
  did not exist. The box now starts empty, and pressing "Generate Chart"
  without a name asks for one instead of inventing "Printer_Paper_Type_Instr"
  plus the date.

- **Japanese and Chinese folder guides read correctly.** Lines no longer begin
  with a comma, a full stop or a dash left stranded at the margin.

## v4.1.3-beta.13

### Fixed

- **Closing a window could crash ChromIQ.** Three buttons and labels were put
  back by a timer that outlived them — the scanner window's "Saved ✓" flash for
  1.4 seconds, the Measure tab's status message for **8**. Close the window
  inside that time and the timer reached for something that no longer existed.

- **Two paths created a project you never asked for.** Opening the Tools menu
  with nothing loaded was enough to make ChromIQ name a project, and the next
  thing you did created the folder. Worse, the patch-set editor's "Save & apply"
  wrote its chart into that invented folder — leaving a folder with no project
  in it that ChromIQ could never find again — and then made a second, real
  project beside it. Applying a chart with no project open now says so and
  changes nothing.

- **The Build Profile tab stayed clickable during a measurement.** It was
  disabled when the measurement started and re-enabled three lines later by
  another part of the same code, so you could walk into a build mid-read.

## v4.1.3-beta.12

### Fixed

- **A table row no longer leaves its bottom edge on the next page.** Knut
  reported "an empty line below the header row, before next row with content
  starts" on the "Overview of Main Actions" and "Where are my files?" cards.
  The rule that keeps a row off a page break was ending the page *inside* the
  row above it — so every cell's text landed on the right page while the row's
  own padding and closing border were painted overleaf, under the repeated
  header. A straddling row is now moved whole.

  **This costs paper**, and the two cards with very tall rows pay for it:
  "Overview of Main Actions" goes from 3 pages to 5 on A4 and 3 to 4 on Letter,
  "Where are my files?" from 9 to 12 and 10 to 12. A row that will not fit is
  moved down whole, which leaves the foot of the sheet before it blank. Every
  other card is unchanged.

## v4.1.3-beta.11

### New

- **Twelve more i1Pro charts.** Knut's 8 mm line-up is complete: the same eight
  patch counts on **US Letter** as on A4 (156 up to 3,432), an **A4-3432p** to
  finish the A4 run, and three on **A3 landscape** (1,144 / 2,288 / 3,432) laid
  out on a 44-column grid. Nineteen charts in all, grouped by paper in the
  preset list and climbing by patch count inside each group — you pick the
  sheet in your printer first.

  The Letter charts keep their own right and bottom margins (9 mm and 15 mm
  against A4's 6 and 19). That is deliberate: Letter is 18 mm shorter than A4,
  so it does not need A4's deeper bottom margin to keep a strip inside the
  i1Pro ruler's 240 mm travel.

## v4.1.3-beta.10

### Fixed

- **The 8 mm i1Pro charts printed without their ruler marks.** Knut, on the
  A4-2288p chart: *"the markers should be active so this is a bug. It was not
  intended."* All nineteen of his exports ask for marks on and five to a patch;
  the family's shared recipe said off and three, and because every chart in the
  family is built from that shared recipe, **all seven of them** lost the marks
  whatever their own export said.

- **The A4-2288p chart's stored setup rebuilt a different chart.** Its recipe
  described a nine-step colour cube where the chart was built with eleven, so
  "Load setup from preset" offered a design that regenerated other colours from
  the second row on. Knut re-exported it; the chart and its setup now match, and
  all 80 bundled charts regenerate their patch sets colour-for-colour.

## v4.1.3-beta.9

### Fixed

- **The folder guide's vertical lines now reach the folders they point at.**
  A folder whose explanation ran to more than one line had a gap between its
  own connector and its first child's, so the diagram read as dashed — below
  `run1/` and `verifications/` especially (Knut). Every continuation line now
  carries the level the row opens, and the top-level folder gets its own
  vertical for the first time. On screen, on paper, and in
  "Where are my files.txt".

- **The CMYK+N card's steps are a real numbered list.** They were literal
  characters — `1)` with no indent and sub-points at the same margin as the
  text around them. They now read `1.` `2.` `3.` with the text indented under
  the number and item 5's three sub-points as a proper bulleted list, on screen
  and in print alike, matching every other card (Knut). Still one printed page.

- **Opening the Tools menu with no project open could invent a project.**
  Asking where the working folder is was enough to make ChromIQ name one and
  keep the name, so the next action created a folder nobody asked for. It now
  asks whether a project is open, which creates nothing.

### Known

- The first-run sentence on the Profile-run bar is clipped at some window
  widths — three of its four lines at 1200 px, and at 900–1000 px its second
  line is drawn over the icons beside it. It has always been too tall for the
  space; it only became visible when the text stopped being invisible in
  beta.8.

## v4.1.3-beta.8

beta.7 fixed the loud half of a fault and made the quiet half worse. Both are
closed here.

### Fixed

- **Settings could follow you from one run to another.** ChromIQ marks the
  chart rows as "belonging to the build" while a chart is being made, so the
  run change the build itself causes cannot reset them. That mark was only ever
  taken down when a build FINISHED — so a Generate that was refused, that
  failed to estimate its patch count, or that you cancelled left it up, and the
  next run or calibration you clicked never received its own settings. On
  screen: a run with a 17 mm margin, a refused Generate, one click to
  Calibration, and the calibration showed 17 mm.

  beta.7 widened this without meaning to: before it, a stale mark suppressed
  only part of the panel; after it, all of it.

- **The "by Pharmacist" charts still rebuilt themselves as a different chart.**
  beta.7 said this was fixed and it was not — that family never claimed its
  rows at all. Pressing Generate once, changing nothing, turned TC3.00's 300
  bundled patches into 504, with no error to show for it.

- **Choosing "Default" left the previous preset's design on the run.** One
  click was enough to reproduce *"a previously created patch set setting is
  there instead"*: "Default" builds a fresh chart through targen and has no
  design of its own, but it said "leave the record alone" rather than "this
  chart has no design".

- **The first-run guidance was invisible** — black text on the black masthead
  (1.11:1 for the two labels, 1.55:1 for the sentence, where readable text
  wants 4.5:1). Both style hooks existed and nothing used them.

## v4.1.3-beta.7

### Fixed

- **The first "Generate Chart" after loading a built-in preset failed, or built
  the wrong chart.** On a fresh project, loading a preset and pressing Generate
  reported *"Nothing for targen to generate"* over an empty preview — with
  "Edit patch recipe (override preset)" untouched, and targen never involved in
  the preset at all (Knut).

  Loading a preset builds its own patch set and then moves the Profile-run bar
  onto the new run. On a fresh project that is a change of run, so the rule that
  opens an unvisited target on its defaults fired and reset the chart rows —
  and the factory default for "Total Patch Count" is zero. The preset's own
  binding no longer matched, so Generate abandoned the preset's patch set and
  fell through to targen. Rows that belong to the build on screen are now left
  alone; a genuine switch to another target still opens on its defaults.

  **On the "by Pharmacist" presets it was worse and silent**: automatic patch
  count is on there, so no error appeared and a different chart was built —
  TC3.00's 300 patches came out as 504, with no warning.

  This shipped in **4.1.2** and is not a beta regression; every 4.1.3 beta has
  it too.

## v4.1.3-beta.6

Knut's wording batch for the help cards, and the guard that should have been
there when the print sizes were fixed.

### Changed

- **Every help card names the thing it is telling you to click.** "the bar" is
  now "the Profile-run bar" — the name its own table gives it — in all nine
  places that said otherwise, and "card" is "help card" throughout, so a printed
  page still says what it belongs to when it is read away from the app (Knut).

- **Getting started ▸ "1. Create Chart"** now also points at the ready-made
  charts behind the "Built-in presets" button and at Tools ▸ Charts & patch sets
  ▸ "Edit / create chart patch set" for designing the colours yourself.

- **Getting started ▸ "3. Measure"** explains the overlay: "Each patch shows:"
  and its three choices, "Show only measured patches", and the progress bar
  above the preview.

- **"Open a project" is now the first entry** under "More than one way to do
  most things", and it names the file to look for — "project.json", inside the
  profile's own folder — or the folder itself.

All twelve translations updated with it, using each language's own names for
the controls it quotes.

### Fixed

- **Nothing was stopping the printed help cards going back to point sizes.** The
  comment in the print style sheet claimed a test guarded it; there was none,
  and the rule next door matches only margins. A font size in `pt` is resolved
  against the screen's DPI, which is what made the cards print a quarter smaller
  on macOS than anywhere else (fixed in beta.4). Reverting every size to `pt` was
  proven to slip through unnoticed; it now fails.

### Known

- The help-card body text is **14 px**, which measures as Times New Roman 11–12
  (x-height 1.914 mm against TNR 11's 1.774 mm). The Measurement Report's body
  is 12 px, below TNR 10 — that is the document that is genuinely small.

## v4.1.3-beta.5

### Fixed

- **A chart could carry a record of a design that never built it.** Knut spotted
  it from the outside — he took a 1,144-patch preset as a basis, built a
  different chart over it, and the stored setup data went on describing the old
  one; charts made from that chart inherited the same wrong record. He was
  right, and it reaches further than the exports he sent: these records live in
  your own saved Create Chart presets, so an affected entry offers the wrong
  design as the starting point for the next one in "Load setup from preset".

  Saving a chart's layout has always been allowed to leave its creation recipe
  alone, which is correct for a layout-only save. A REBUILD from a different
  patch set was doing the same thing, so nothing ever cleared the old design.
  There is now a third state — *this chart was not built from a stored design* —
  and loading a patch set uses it, so the previously selected preset's design
  is no longer stamped onto a chart it does not describe.

  Existing records are not rewritten: a chart already carrying the wrong design
  keeps it until it is rebuilt.

## v4.1.3-beta.4

Knut's help-card batch. Chasing a heading that printed on its own turned up the
reason: the rules that lay out a printed card were measuring a document they had
already destroyed, and pages of it were never reaching the paper.

### Fixed

- **Printed help cards were losing whole pages of text — silently, and on
  paper.** A `QTextDocument` lays itself out lazily, and changing a block in one
  that is only half laid out does not make the geometry stale, it DESTROYS it:
  every element below the change collapses to nothing. Each of the four
  pagination rules measures the document and then edits it, so each could trip
  it. The dictionary card printed **29 of its 79 entries**; the other 50 existed,
  paginated, and were simply not on any sheet. The card looked finished — it
  ended with a heading and a page number.

  This has been shipping. On US Letter the glossary has been losing its last
  entries since the rules were introduced; 4.1.3-beta.3 widened it to A4. Every
  rule now takes its layout from one place that finishes the layout first, and
  every card on A4, Letter and A5 has been read back out of the PDF word by
  word: nothing is missing.

- **Help cards printed a quarter smaller on macOS than anywhere else.** Font
  sizes were in `pt`, and Qt resolves those against the primary screen's logical
  DPI — 72 on macOS, 96 elsewhere. So 10.5 pt body text was 11 px on a Mac and
  14 px on Windows, Linux and in every test we ran, while the folder guide's
  directory tree kept its absolute 12 px and towered over the text around it
  (Knut, A2). Every size is now in `px`, so the printed page is the same
  everywhere and what the tests measure is what comes out.

- **A card title no longer wraps.** "Calibrate my printer (and how that differs
  from a profile)" ran to two lines. The `h1 { font-size: 19pt }` meant to
  control it was dead — Qt fixes an `<h1>`'s size from its own default and
  ignores the style sheet, inline styles, and every unit (measured). Titles are
  a styled paragraph now, and the longest one fits with room to spare (A3).

- **A section heading could print alone at the foot of a page**, its text
  overleaf — Knut's "Instrument" in the dictionary card (A5). The rule that
  exists to prevent this judged which page a block was on by the top of its box,
  and a block can start in the last pixels of a page while its first line falls
  on the next. It judges the line now. A second fault in the same rule abandoned
  every later heading in a card once it met one it could not move.

- **A blank line at the END of clip-border text now prints.** Leading and
  interior blank lines came back in beta.3; the last one was still swallowed,
  because `splitlines()` treats a final newline as a terminator rather than a
  separator (Knut). Putting a space on the line worked, but an invisible space is
  no answer — any editor that trims trailing whitespace throws it away.

### Known

- On US Letter, three cards still end with a page holding only the closing line.
  Their content is 2–4 % taller than a Letter page; no typographic rule fixes
  that, only shorter cards.
- A table row that meets a page break still stretches to the page bottom instead
  of ending under its last line (Knut, A1). Qt grows the last row on a page, and
  the honest fix is to split the table at each break — its own piece of work.

## v4.1.3-beta.3

The preview window beta.2 put in front of the print dialog is gone — and taking
it out uncovered the fault it had been showing all along.

### Fixed

- **Help cards printed at a third of their size on macOS.** ChromIQ asked the
  printer to work in the 96-dpi units the cards are written in. A PDF writer
  agrees to that; a printer does not — macOS snaps the request to a resolution
  the queue actually has (96 became 300 on both printers here) while still
  reporting its pixels at that resolution. Dividing those by 96 read a 180 mm
  page as 562 mm, so every card was laid out for a sheet three times too wide
  and then squeezed onto the real one: microscopic text crammed into the top
  third, and 3 times too much of it on each page. Every card, both common paper
  sizes. It reached only the printer — "Save as PDF…" came out the right size
  throughout, which is why nothing looked wrong until a preview drew the
  printer's page on screen. Cards now print at the printer's own resolution,
  and all 18 cards on A4, Letter, A5, A6, Legal, landscape and wide margins
  come out page-for-page identical to the PDF.

  Linux was not affected — its print engine takes the resolution it is given.
  Windows should not be either, for the same reason, but that has not been run.

  The saved PDFs shift very slightly with this: the printable width used to be
  rounded down to a whole device pixel and is now not, so the text column is
  0.35 mm wider. Page counts are unchanged on every card.

- **A help card could run to half again as many pages on US Letter.** Keeping
  table rows off page breaks put the break directly after a repeating header
  row, and Qt then had to reprint that header on the new page: one such break
  cost three pages. The folder guide finished at 14 pages on Letter where the
  same card on A4 took 9. It now moves the whole table down instead: 11 pages,
  with no row cut in half on any card at either size. A4 is unchanged at 9.

  Five other cards lost pages too, one of them eight. Letter still has one
  near-empty page in the folder guide, where a heading sits alone above its
  table — beta.2 had four.

- **Printing no longer changes the print job's settings.** Painting a card left
  the printer at 300 dpi even if the user had chosen 600.

### Changed

- **Print… opens your system's print window again, with no preview window in
  front of it.** ChromIQ cannot put a preview inside that window: on macOS the
  pane Apple draws there belongs to a kind of print job Qt does not use, the
  Windows print dialog has no preview at all, and Qt hides the one in its own
  Linux dialog. To see the pages before they are printed, use "Save as PDF…"
  beside the button.

## v4.1.3-beta.2

Knut's second batch, and it turned out to be one fault wearing several hats: the
printed Help cards were never being paginated, so almost everything he reported
about them had the same cause. Plus his seven new i1Pro charts, two withdrawals,
and the full translation pass.

### Fixed

- **Printed Help cards were laid out for a page ChromIQ never asked for.** The
  document was handed a text width instead of a PAGE, which sends Qt down a
  different path: it re-lays the card at the PRINTER's resolution and adds a
  2 cm margin of its own. Three of the reports follow from that single line.
  Every card printed into a 140 mm column on a 180 mm page. The folder guide's
  section headings and its whole directory tree came out as an unreadable
  smudge, because the cards are written in pixels and a pixel meant something
  different on a 720 dpi printer than on a 96 dpi screen — which is also why the
  same bug looked different to different testers. And the workflow diagram was
  clipped at the right edge and printed again on the next page.

- **Bullets and numbered lists printed as one continuous block.** Two causes,
  both now fixed. Qt's rich-text engine accepts a margin in pixels and silently
  ignores one in points, so a stylesheet written in points has no spacing at
  all — no blank line above a heading, no gap between list items, no indent
  under a dictionary term. And a card whose body is plain text (the CMYK+N one)
  was being pasted into HTML, where newlines simply vanish.

- **The steps named the wrong tab.** "Print an existing test chart" told you to
  go to Measure. The table of tab names was numbered from zero with four
  entries; the steps are numbered from one across five.

- **"Save as PDF" offered "Untitled.pdf".** ChromIQ now asks for the file name
  itself, with the card's own title filled in.

- **The Help window dropped behind the main window** after the print or save
  panel closed, so you had to reopen Help to get back to the card.

- **The ruler-marker warning was drawn on top of the strip labels and the
  dashes.** It now sits below the sheet, outside the page, centred — in a band
  reserved before the page is scaled, because the frame around a sheet that
  carries its own white margin can be zero pixels wide. Its wording is Knut's.

- **Keyboard shortcuts were spelled in macOS symbols everywhere.** ⌘1 is Ctrl+1
  on Windows and Linux, and the card now says whichever is true where you are
  reading it.

- **Blank lines in the clip-border text were dropped** at the first and last
  line. They are writing space, and they are all kept now, for every content
  option that takes text.

- **"Export template" wrote only the strip's measurements**, never the content
  you could see in the preview. It now exports what the preview shows for any
  content option; with the band switched off it still writes the blank,
  exact-size design canvas that button was made for.

### New

- **Every printed page carries the ChromIQ wordmark and the five-segment
  spectrum bar**, the card's name from page two on, and a page number centred on
  the page rather than tucked into the corner.

- **The printing rules Knut asked for**: a blank line above every heading, no
  heading stranded at the foot of a page away from its text, no table row cut in
  half by a page break, and a table that spans pages repeating its header row at
  the top of each one. They live in a module the Measurement Report shares, so
  it can adopt them next; today the report uses only the whole-table rule it
  already had.

- **Print… now shows a preview** before the system print dialog, which on macOS
  shows none of its own. *(Withdrawn in beta.3 — see above.)*

- **Seven new i1Pro charts** on A4 with 8 mm patches — 156, 312, 572, 1,144,
  1,716, 2,288 and 2,860 patches, one 22 × 26 grid, 572 to a sheet. Knut's own
  i1Pro charts are now listed in ascending order within their block, like the
  ColorMunki and i1Pro 3 Plus ones.

- **"Imported image" can carry text too.** Only the Notes box fills itself in,
  so only the Notes box switches the Text field off.

- **The strings this work added are translated in all twelve languages** — 40
  of them, with no English placeholders among them. (The catalogues as a whole
  are not finished: each language still carries roughly 25 long strings from
  earlier work that read as English. Those are on the list for GA.)

### Changed

- **Two built-in charts were withdrawn** at Knut's request: the i1Pro
  A4-495p-1page-Landscape, and the i1Pro A4 "TC9.24 by Pharmacist" that had been
  parked since its bundled page disagreed with its own reference. Nothing on
  disk points at a built-in preset, so **a project built from either one still
  opens, still reloads and still restores its used chart** — only the dropdown
  rows are gone. The ColorMunki A3 TC9.24 is a different chart and stays.

- **The clip band's fit and move fields now apply to the ChromIQ branding as
  well as to an imported image**, and they are the same stored fields — so a
  preset that carried an image placement applies that placement to branding too.

- The clip area reported in Preferences follows the paper of the recipe loaded
  there instead of always reporting A4.

- **Blank lines you typed into the clip-border text are now printed as you typed
  them.** A saved preset or recipe whose text begins or ends with blank lines
  will print a taller band than it did in beta.1. No bundled chart is affected —
  every built-in's clip text is four lines with no blanks.
- **"Imported image" now honours the clip Font and Size** as well as the Text.
- **The chart preview shrinks a little** while the marker controls differ from
  the sheet on screen, to make room for the caption underneath it.
- **No built-in preset is parked any more.** The greying mechanism stays; it
  simply has nothing in it.
- **Print… opens a preview**, not the system print dialog, and saving a copy is
  now its own button beside it. *(The preview was withdrawn in beta.3; the
  separate button stayed.)*
- **The i1Pro preset list is in a different order**, so entries you knew by
  position have moved.

### Known

- The seven new i1Pro charts are laid out with a **6 mm right margin**, while
  ChromIQ's own i1Pro seed asks for 9 mm — their other three margins match it
  exactly. They ship exactly as Knut authored them, so the Measured-from-Preview
  panel will flag the right edge on all seven until it is decided which of the
  two numbers should move.

### Internal

- `paginate_tables` moved from the Measurement Report into a shared
  `ui/pdf_layout.py`; the report keeps its behaviour and its tests.
- One of the seven imported presets carried a colour-set sidecar claiming 1,200
  patches beside a 2,288-patch chart — "Load setup from preset" would have
  offered to regenerate it 1,088 patches short. The importer now re-points the
  patch count as well as the instrument and paper, and a test pins it.
- `docs/dev_builtin_presets.md` gained the missing procedure for removing a
  built-in for good, and lost a false claim that Guided mode depends on one
  particular preset plus two citations of test files that do not exist.

## v4.1.3-beta.1

Knut's 2026-08-23 batch. The ruler helper markers turn out to have been right on
paper all along — it was the preview that was lying — and the clip-border panel
was dead on a ColorMunki. Help cards can now be printed.

### Fixed

- **The preview was counting two combs of ruler dashes at once.** Knut reported
  that "Markers per patch" drew five dashes when set to 4 and seven when set to
  6, unevenly spaced. The printed sheet was never wrong: the geometry draws
  exactly the number asked for, every gap identical, with the outer dashes
  centred on the spacers — the design he specified. What was wrong is what the
  screen showed. A sheet keeps the dashes it was *generated* with, and the live
  overlay drew the *current* spin-box value over the top, so the preview showed
  the union of the two combs: 3 printed + 4 proposed = 5 dashes per patch,
  unevenly spaced; 3 + 6 = 7. Every number he counted falls out of that. The
  overlay now says so — while the controls differ from the sheet in front of
  you, the dashes are drawn in the accent colour under the caption "Markers not
  on this sheet yet — press Generate Chart", and go back to plain black once the
  two agree. Dash positions are rounded rather than truncated, so the overlay
  lands on the printed ink instead of half a pixel below it, and the white halo
  narrows and then gives way when dashes are close instead of flooding the gaps
  between them.

- **The clip-border Preview and "Clip area" work on a ColorMunki.** They were
  dead for every content mode on a ColorMunki or SpectroScan preset — an empty
  box and a long dash — while the band was printed onto the sheet all the same.
  The panel built its geometry for an i1 or i1Pro 3+ and answered "no band" for
  anything else; it now asks the same question the renderer asks. A second cause
  went with it, and that one was never instrument-specific: the preview worked
  the band width out from the page margins rather than from the recipe, so wide
  margins erased the clip area on an i1 too. "Export template (PNG + PDF)" was
  behind the same guard and did nothing on those instruments.

- **A disabled text box now looks disabled.** The clip-border Text field is
  switched off in Notes-box mode — the notes design fills itself in — but it was
  pixel for pixel identical to a live one, so it read as editable and its
  contents looked ignored. Both themes were missing a rule for text boxes; the
  field's label greys with it now. The same box in ChromIQ-branding mode is
  live, and now visibly so.

- **"Also export a PDF" was exporting charts without their helper markers.** The
  TIFF had them, the PDF silently did not, and both come out of the same tick of
  Generate Chart.

### New

- **"Show markers for: Top/bottom · Sides".** Two tick boxes in Ruler helper
  markers, so the set you do not need is simply not printed — Knut: *"especially
  as the strip markers are the most useful for measuring."* The set you keep
  reaches into the corners as well: the corner trim only ever existed to stop
  the two sets colliding, and with one of them off there is nothing to collide
  with. Carried in the recipe, so it saves and loads with a preset, and if you
  leave both unticked the panel says plainly that nothing will be printed.

- **Help cards can be printed.** A Print… button on any open Help card opens
  your normal print dialog, which is also where "Save as PDF" lives — handy for
  the keyboard shortcuts, or a workflow to follow at the printer. Every card
  kind prints, the glossary and the step lists included, and the Getting-Started
  card keeps its workflow diagram.

- **ChromIQ branding can be placed.** *"For Imported image option, then there
  are fields to position the image. Why are those options not available for
  ChromIQ branding?"* — they are now, and they are the same fields. "Content
  fit" and "Content move" scale the wordmark and move it across and along the
  band, and your own lines under the wordmark move with it. Rotation stays an
  image-only transform, because the branding always reads up the strip and
  "Flip 180°" is how that is turned round.

### Changed

- **Every tick box in "Measured from Preview" has its own ⓘ.** There was one
  icon against the first of three, carrying a single explanation of the panel
  and of all three boxes at once. Each box now answers for itself, and the
  overview of the numbers sits on the numbers.

- **Worth knowing if you have your own presets.** The clip band's fit and move
  fields now apply to the ChromIQ branding as well as to an imported image, and
  they are the same stored fields — so a preset that carried an image placement
  will apply that placement to branding too. The "Clip area" figure for an i1 or
  i1Pro 3+ can also read slightly differently from before, because it is now
  worked out the way the renderer works it out; a clip template exported earlier
  was sized to the old number and is worth exporting again.

### Internal

- The printed Getting-Started card was clipping its workflow diagram at the page
  edge and repeating it on the next page, because the picture was placed at a
  fixed size instead of the page's. The size now comes from the printer the user
  chose, so it is whole on A4, Letter, Legal, A5, A6 and landscape alike — the
  first version of this fix worked on A4 only and left A5 exactly as it was.
- Scaling the clip branding to an extreme value crashed the panel outright
  (Pillow refuses a glyph that large). It is capped now, and a branding that
  cannot be drawn leaves the band blank instead of taking the window with it —
  which needed a second fix, because the handler that promises that called a
  logger the module did not have and raised `NameError` instead. The same
  missing logger sat behind the helper-marker handler, unnoticed since 4.0.0.
- The marker overlay rebuilds its geometry with the chart's own patch count, so
  a matching overlay really does mean "these are the dashes on the sheet".
  Without it an area-first chart could be described by a comb nothing like the
  printed one.
- The two "Show markers for" boxes are stacked rather than side by side: on one
  line they made the Ruler-helper-markers group the widest thing in Expert
  Options and drove the whole column into horizontal scrolling.
- A help card that cannot be printed now says so instead of doing nothing. (A
  cancelled print dialog still says nothing, which is the point of cancelling.)
- The clip area shown in Preferences follows the paper of the recipe loaded
  there, instead of always reporting A4.
- The preset round-trip test was comparing several fields against their own
  defaults, so a dropped one would have passed unnoticed. It now sets every
  field, and a new test keeps it that way.

## v4.1.2

A polish release. ChromIQ starts in about half the time, tabs switch the instant
you click them, and a long list of small frictions in Create Chart, Measure and
the in-gamut module are gone. Nothing about how charts are made, printed,
measured or profiled has changed.

### Changed

- **The app opens in about half the time.** Roughly 5.7 seconds to a usable
  window before, about 3.0 now. Four separate things were costing that: the
  splash screen spent a full second inside the toolkit waiting for something
  that never happened, four separate filters each had to look at every event the
  app produced, the tabs were styled twice because the window was built assuming
  dark mode before the real theme was known, and the tab strip was restyled two
  or three times over with identical values.

- **Switching tabs is no longer sluggish.** Clicking a tab took about a quarter
  of a second before the tab appeared; it is now under a hundredth. The thin
  line under the tab bar was drawn in the current tab's colour, so every switch
  re-drew every control in all five tabs — around 26,000 of them.

- **Patch sample area is limited to what your patches can actually give.** On a
  chart with six-sided patches the area ChromIQ reads runs out of room sooner
  than it does inside a square one, and the neighbouring patch is flush against
  it — so a reading area a little too large picks up the colour next door on
  every patch at once. ChromIQ now works the limit out from the shape of your
  own patches instead of leaving you to guess. Square patches are unaffected.

- **Guided mode says what it keeps fixed**, and no longer applies settings you
  cannot see. Options Guided does not offer can no longer be stored by "Save as
  Defaults", and "Patch-by-patch mode" is now available there.

- **The ruler helper markers moved into Create Chart**, next to the chart they
  belong to, with a "markers per patch" control.

### Fixed

- **Create Chart no longer loses what you built with.** Pressing Generate could
  put the tab back into Manual with a different instrument, paper size and
  layout — whatever that run had stored from an earlier session — moments after
  your chart appeared. What the chart was built with now stays on screen.

- **Reading a chart with a scanner no longer gives up on six-sided patches.**
  When you place the four corners yourself, ChromIQ no longer asks the scanning
  step to work the perspective out as well; it never used that answer, and on a
  honeycomb it collapsed and took the whole scan with it. Nearly one scan in
  four failed or hung; now none do, and every colour comes back identical.

- **The in-gamut chart no longer offers colours your profile cannot print**, and
  a profile that can print nothing no longer gets the largest chart. It also
  starts from the chart you set up in Manual, and opening a run is quicker.

- **Your Measure settings stop changing when you switch runs**, and settings
  saved before this release still work.

- **Guided says which measurement options belong to Manual.** "Don't save
  spectral data" is one of them: Guided never applied it, but it looked as
  though it might. Guided still saves spectral data — it now says so instead of
  leaving you to wonder.

- **The chart preview no longer draws a white border twice.** Charts from the
  layout engine carry their own paper margin and the preview was adding another,
  so the sheet looked as if it had a wider white edge than it has.

- **Dialogs opened from a tab no longer borrow that tab's colour.** The
  measurement report showed a pink trend line opened from one tab and a green one
  from another, and in light mode those dialogs were missing the frame they have
  everywhere else.

- **The log text no longer stays bold after switching to dark mode.**

- **"Show overlay from existing measurement" explains itself** when there is no
  measurement to show.

- **The clip border prints its ChromIQ logo and your own lines together**, and
  its preview shows the size it will actually print.

- **On a machine without ArgyllCMS, the "not found" message is reachable and
  correct.** It could open behind the start-up picture with no way to reach it,
  and it gave every user macOS instructions regardless of their system.

### Notes

- Two switches are available if the new start-up behaviour ever misbehaves:
  **Classic splash screen** in Preferences → Beta, and the environment variable
  `CHROMIQ_SEPARATE_FILTERS=1`.
- Hexagonal charts in the scanner and camera tools remain opt-in under
  Preferences → Beta. A sample pack is attached to the beta releases for anyone
  who wants to try them.

## v4.1.1

### New

- **A set of 24 built-in charts for the i1Pro 3 Plus**, made and measured on
  paper by soul-traveller — the same treatment his ColorMunki charts had, for
  the other instrument. There is a size for every job: 84 patches on one sheet
  up to 2,016 across six A3 sheets, on A4, US Letter and A3.

  Pick one under **Create Chart → Manual → Presets**, or from the magenta list
  button next to the GUIDED / MANUAL switch, where they have their own
  **i1Pro 3 Plus** section. They are kept apart from the i1Pro charts on
  purpose: these layouts are cut for the 3 Plus.

  Every chart leaves a 40 mm run-in at the top so the instrument clears the
  first patch, 20 mm of white paper at the bottom to finish a strip on, and a
  28 mm band down the left for the instrument to run up before it reaches the
  first patch — the chart's details are printed in that band for you. Patches
  are 16 mm wide, except the two 84-patch quick charts, which use 25 mm.

  The colours are fixed, but the layout is not: change the paper, the margins or
  anything else and press **Generate Chart** to re-flow the same patches.

### Changed

- **The preset lists now name each instrument group the way the Instrument field
  does.** The headings in the **Presets** dropdown and in the ★ overlay used
  short names — "ColorMunki", "i1Pro" — which hid who the charts are for: the
  i1Pro charts suit an i1Pro 2 and an i1Pro 3 as well. The headings now read
  **ColorMunki / i1Studio / ColorChecker Studio**, **i1Pro / i1Pro 2 / i1Pro 3**
  and **i1Pro 3 Plus**, exactly as the Instrument box lists them, and the
  dropdown shows a proper heading above each group instead of only a dividing
  line. Chart and folder names are unchanged.

### Internal

- The importer that stages Knut's exported charts is now family-driven
  (`scripts/import_knut_presets.py <family> <folder>`), so a future line-up is a
  table entry rather than a second script. It still rejects any export that
  differs from its family's shared recipe outside the fields one chart may own,
  and re-points the colour-set recipe at the chart it actually built — which all
  24 of these needed.

## v4.1.0

Everything reported against 4.0.0 and 4.0.1 by soul-traveller is fixed — verified
by him on real hardware — and two features he asked for are in. The ColorMunki
also gains a complete set of ready-made charts, which he made and measured on
paper himself.

### New

- **A new set of 45 built-in ColorMunki charts**, made and measured on paper by
  soul-traveller. They replace the older ColorMunki charts of his, and are built
  for reading with a ruler: the margins keep the knobs under the instrument off
  the edge of the page, leave white paper to finish a strip on, and keep both the
  first and the last strip reachable. The helper markers are switched on, and at
  the ~10 mm patch width most of them use, the ruler goes four markers below the
  strip you are reading.

  Pick one under **Create Chart → Manual → Presets**, or from the magenta list
  button next to the GUIDED / MANUAL switch. There
  is a size for every job — 84 to 2,280 patches on A4, US Letter, A3 and A3+, in
  portrait and landscape. Most sizes come as a **Fast** and a **Slow Reading
  Speed** pair: same patches, but the fast one puts shorter strips on more sheets,
  because the ColorMunki reads a short strip more quickly. Three **Hand Held**
  charts use big 26 mm patches for reading without a ruler at all. Each chart
  prints the reason for every margin down its side, so the sheet explains itself.

  The colours are fixed, but the layout is not: change the paper, the margins or
  anything else and press **Generate Chart** to re-flow the same patches.

- **Ruler helper markers on the printed chart.** Short dashes along all four
  edges of the sheet, so you can lay a ruler against the paper and line your
  instrument up with the patches. One dash sits exactly at the centre of each
  patch and the next midway to its neighbour, evenly spaced all the way along —
  and they follow your patch spacers automatically, however you set them. Switch
  them on under the preview with **"Show helper markers"**, choose how far in
  from the edge they sit and how long they are, then press **Generate Chart**.
  The corners stay clear, and charts with six-sided patches grey the option out
  and say why.

- **A measurement progress bar in the preview header.** While you measure, the
  header fills in your accent colour and shows how far through the chart you
  are, so you can see progress without counting strips. Turn it off in
  **Preferences → Measurement** if you prefer the plain header.

- **Preferences → Sounds: "Wake the audio device before playing a sound".** Off
  by default. Turn it on if the first sound after a silence is too quiet or
  seems to start halfway through.

### Fixed

- **Measurement sounds work again.** An attempt to make the first sound louder
  could stop every sound instead — during a measurement, on the instrument
  button, and on the Play buttons in Preferences. ChromIQ no longer touches the
  audio device before playing, and the behaviour that caused it is now the
  optional setting above.

- **ArgyllCMS's own beeps play again**, alongside ChromIQ's sounds rather than
  instead of them. They are separate cues: the reader's beep tells you the
  instrument is ready for you to start, which none of ChromIQ's sounds covers.

- **Your Measure settings are saved when you press Start Measurement.** Anything
  you changed just before measuring — "Skip initial calibration", patch-by-patch,
  the tolerance, resume — was not being stored, so it reverted afterwards. Every
  control on that panel is now kept with its own run.

- **"Refine / resume existing measurement" no longer breaks a measurement when
  there is nothing to resume.** Ticking it on a run whose measurement is missing,
  empty or damaged made the measurement fail before the first patch. The tick is
  now honoured only when there really is a measurement behind it.

- **A chart with no measurement no longer claims its measurement belongs to a
  different chart**, and says plainly that it has not been measured yet.

- **"All strips read" waits until every patch really is read**, instead of
  appearing on a chart that is 97% measured, and the log says how many patches
  are still missing.

- **"n" during patch-by-patch reading moves to the next unread patch** instead of
  stopping on the one you are already on.

- **The ColorMunki's patch limit and the reading-speed guidance** now match what
  the instrument and the paper actually allow.

- **Loading a .ti1 in the patch editor** no longer adds more patches than the
  file contains.

- **A fixed seed reproduces the same chart** when a target is duplicated.

- **"Show helper markers" now follows the chart you load.** Opening a preset or a
  saved chart that uses the markers built them onto the sheet correctly, but left
  the tick box under the preview showing off. The tick box and the two distances
  now match whatever chart is loaded — and the two distance boxes are the same
  slim size as the margin boxes in Create Chart.

- **The live preview no longer replaces a chart you have just built.** With
  "Update the preview automatically" on, choosing a preset could show the right
  chart and then, a second later, replace it with one laid out the old way — the
  same patches, but narrower. A chart's own settings were not being filed against
  its run when it was built, so the run's previous settings loaded back over the
  screen and the preview redrew the sheet from those. Building a chart now saves
  its settings with its run straight away, and the preview follows the chart in
  front of you.

## v4.0.1

Fixes around the very first chart of a new project — found by Knut and
Sebastian testing side by side on one afternoon, all sharing a single root:
what you type before the first Generate had nowhere to live yet — together
with a group of measuring aids that were describing the chart slightly
inaccurately.

### Fixed

- **"Close to the limit" is only said when a strip really is close.** While you
  measure, the message under the chart preview tells you how your reading speed
  is doing. It was calling a strip "close to the limit" when it was as much as
  35% clear of it — so a ColorMunki strip read at 521 ms per patch was warned
  about even though the limit is 400 ms. How close is close enough to mention
  is now yours to choose, in **Preferences ▸ Measurement ▸ Close to the
  limit**, and it starts at 10%. At that setting the 521 ms strip in the report
  is simply called a good reading speed, which is what it was. Set it to 0% if
  you would rather only ever be told when a strip is genuinely too fast
  (reported by soul-traveller).

- **The reading-speed message now tells you the whole-strip time as well.**
  Milliseconds per patch is a hard thing to picture while you are holding an
  instrument. The message now also gives the figure you can actually feel — the
  seconds a whole strip should take — so instead of just "400 ms or more per
  patch" you get "400 ms or more per patch — 6.0 sec. or more per strip". If
  the window is narrow the message wraps onto another line and the area grows
  to fit it, rather than cutting the end off (reported by soul-traveller).

- **The ColorMunki gets more room at the top of the page.** The top margin
  ChromIQ warns below is now 33 mm for every paper size, instead of 30 mm. The
  reason is mechanical rather than optical: the two knobs on the underside of a
  ColorMunki catch on the edge of the sheet as you start a strip, so the
  instrument needs a little more paper in front of the first patch than the
  light path alone would suggest. If you had already set a margin of your own
  for a page size, your value is kept exactly as it is (reported by
  soul-traveller).

- **Loading a patch set tells you how many patches arrived.** The **Edit /
  Create Chart Patch Set** window now says, for example, "Loaded MyChart.ti1 —
  2002 patches", so you can check the number against the file you chose
  (reported by soul-traveller).

- **A chart keeps the patch set it was built from.** If you built a chart from
  a patch set of your own — one you made with the patch generators, edited in
  the Patch Set editor, or loaded from a file — and later pressed **Generate
  Chart** again, ChromIQ could quietly build a completely different chart with
  a fresh set of patches. It happened once the project had been closed and
  opened again, which is easy to do without thinking about it: the link between
  the chart and your patch set was only remembered while the app stayed open.
  This mattered most when the chart had already been printed, because the
  sheets on your desk then no longer matched the chart ChromIQ would measure
  them against, and nothing on screen said so. A run now keeps its own patch
  set, so generating again lays out the very same patches. Changing something
  that defines the patch set itself — the patch count, the grey steps, the
  white or black patches — still gives you a fresh chart, because that is what
  asking for different patches means. You can also see that your patches are
  protected: the **"Edit patch recipe (override preset)"** box is shown with
  the patch settings greyed out behind it, and you tick that box on the
  occasions when you do want a brand-new set of patches (reported by
  soul-traveller).

- **Loading a patch set no longer adds patches that are not there.** In **Edit /
  Create Chart Patch Set**, choosing **Load Patch Set…** and picking a `.ti1`
  file added more patches than the file contains — 2019 instead of 2002 for a
  typical chart. A `.ti1` file holds three tables, and only the first one is
  the patches to print; the two after it hold reference values that ArgyllCMS
  needs, such as the corners of the colour cube. Those were being read in as
  though they were patches. Only the patch table is loaded now (reported by
  soul-traveller).

- **The colour list handed to a print shop is no longer empty.** Every chart
  writes a `-colours.txt` file into its run's `exports` folder — a plain list
  of the chart's colours you can pass to a print shop or another program. That
  file was being written completely empty, for every chart, because of the same
  misreading of the three tables described above. It now contains the full list
  of colours again. Any file you exported before this will still be empty, so
  generate the chart again if you need one of them.

- **The measurement sounds are heard again.** Many of the short sounds went
  missing entirely — the tick for each patch, the thump for a patch that is
  off-colour, and ding, click, chime, buzz, bump and ding-hi — and longer ones
  could lose their opening, which is what stopped the bell sounding like a
  bell. The sound files were never at fault. On a Mac the sound hardware is
  allowed to go to sleep when nothing has been played for a while, and whatever
  wakes it up loses its own beginning while the hardware starts. A short sound
  can be over before the hardware is properly awake, so it is never heard at
  all. ChromIQ now wakes the sound hardware quietly in advance — when a
  measurement starts, and when you press **Play** in **Preferences ▸ Sounds** —
  so the sound you actually want to hear arrives into hardware that is already
  running. During a measurement the cues follow each other closely enough to
  keep it awake by themselves (reported by soul-traveller).

- **The instrument's own "ready" beep is back.** When you press the button on
  your instrument to start reading, it plays a short beep to tell you it is
  ready for you to move. That beep comes from ArgyllCMS rather than from
  ChromIQ's own sounds, which is why it does not appear in the list on
  **Preferences ▸ Sounds** — and it had gone quiet on macOS. It sounds again
  (reported by soul-traveller).

- **Three sounds start out better chosen.** A patch that reads off-colour now
  starts as **bump**, a finished measurement as **chime-long**, and a finished
  profile as **applause**. If you had already chosen your own sound for any of
  these, your choice is kept exactly as it is (chosen by soul-traveller).

- **The pointer ruler measures the chart you are looking at.** With "Show
  measurement coordinates on pointer" ticked, the readout used the Resolution
  setting rather than the resolution the chart on screen was actually made at.
  On a 200 dpi chart every reading came out at two thirds of the truth — an A4
  sheet's far corner read 140.0 × 198.3 mm instead of 210 × 297, and the ruler
  disagreed with the margins listed right below it. Both now read the page's
  own resolution, so they always agree, on any paper size and either
  orientation (reported by Knut).

- **The expected-vs-measured overlay sits exactly on its patches.** During a
  measurement the coloured split could leave a thin rim of the real patch
  showing along an edge. Four separate causes, all fixed: the patch boxes were
  rounded in a way that shifted them up and to the left; on a hexagonal
  SpectroScan chart the honeycomb offset was missing entirely; on a Retina
  screen an edge could land half a pixel off; and the strips were not always
  kept inside the page. The corrected patch rounding also makes the patch
  boxes in a scanner or camera target exact for rectangular charts. Scanner
  and camera work stays unavailable for hexagonal SpectroScan charts, as it
  always has been — a CHT recognition file cannot describe a hexagon, so
  those charts are measured with the SpectroScan itself.

- **The overlay legend keeps clear of the chart.** It could overlap the last
  row of patches, the edge spacer or the scan arrow, depending on the layout.
  On a ColorMunki chart with staggered strips it sat across the last patches
  of the lower strips: every second strip is offset down the page, and its
  recorded position did not include that offset. The strip highlight and the
  click-to-jump target on the Measure tab were off by the same amount on those
  charts, and are now exact.

- **"No spacers" now means bare paper.** Choosing no spacer still drew black
  bars between the patches and the strips; the gaps are left blank, as asked
  for.

- **Your run description survives the first Generate.** Typing a description
  for a brand-new project and pressing Generate Chart cleared the field and
  lost the text; it is now written into the freshly created run, exactly as
  it already was when adding a run to an existing project.

- **The project name is one value in Guided and Manual.** A name typed in
  Guided now appears in Manual immediately (and the other way round) — before,
  the two fields only agreed once a project existed, so a fresh start showed
  the name in one mode only.

- **The first chart of a new project keeps your settings.** After the first
  Generate, the screen could snap back to factory defaults — the instrument
  jumped from ColorMunki to i1Pro by itself, and a re-layout could redraw the
  chart with the wrong instrument's geometry, leaving the page half filled.
  A new project's first run is now born with the exact settings its chart was
  built from.

- **Save as Defaults no longer stores the project name.** Every other row on
  the tab is a preference; the name identifies a project — saving it seeded
  every future fresh start with an old project's name, one Generate away from
  building into it. The saved name from older versions is cleared too.

- **The app no longer crashes when an instrument keeps dropping off the USB
  bus.** Closing Read Single Patches now lets go of the measuring engine
  properly. Before, a session that ended by itself could report back a moment
  later, into a window that had already closed, and the app died outright
  (reported by Knut with a ColorMunki on a 2019 MacBook).

- **"No instrument found" now names the likeliest cause and offers the fix.**
  On some computers, older Macs in particular, the "Faster instrument
  connection" shortcut is what stops an instrument being seen at all. Both the
  measurement window and Read Single Patches now explain this and carry a
  **Turn off faster connection** button, so you do not have to go hunting
  through Preferences in the middle of a measurement; the text also says where
  the option lives (Preferences ▸ Measurement) for switching it back on. The
  option's own help text says when turning it off is the right move.

## v4.0.0

> **This entry covers everything that changed since v3.14.7, the last stable release** — 224 betas' worth of work, grouped so you can find what affects you instead of reading a diary. The individual beta histories remain in the repository.

**If you only read one paragraph:** ChromIQ 4.0 looks after your work — every
run keeps its own chart, measurement and settings, nothing you made is ever
deleted, and checking how good a finished profile really is has become a
guided, honest, repeatable workflow. Your existing projects are picked up
exactly as they are: ChromIQ migrates them in place the first time it opens
them, keeps every old file, and there is nothing you need to do first.

Two headlines in more detail. **ChromIQ now keeps track of your work for
you**: a profile run
holds its own chart, its own measurement, its own settings and its own
description; nothing you made is ever deleted, only archived; and every window
that could cost you something says exactly what it is about to do. And
**checking a finished profile is now a first-class workflow**: three clearly
explained ways to verify, honest statistics for each of them, and a
measurement report that keeps the whole dated history of a profile's health.

*(New words along the way — "gamut", "drift check", "judged as measured" —
each have a plain-language Dictionary entry: open the Welcome window's
"Dictionary and terminology" card. The card "Check a finished profile
(verification run)" walks the whole workflow step by step.)*

### New

**🎯 Verification, from start to finish:**

- **Three ways to check a profile, clearly told apart.** A chart built from
  the profile's own gamut (the everyday accuracy check), a chart printed
  through the profile (the strict whole-path check), and a sheet printed from
  your own application with the profile applied (the everyday-chain check).
  The Dictionary entry *"Which verification should I use? (the three ways)"*
  compares them, and the report records which way every sheet was made so
  they are never mixed silently.

- **A verification chart built from your profile's own gamut.** The **FROM
  PROFILE GAMUT** module on Create Chart asks the profile which colours it
  can actually print — from a fixed, published reference set — and builds the
  chart out of exactly those, so no patch is wasted on a colour that was
  never possible on this paper. White, black and evenly spaced grey steps
  take about one patch in eight — enough of a grey wedge to catch a
  drifting printer, without swallowing a small chart. Repeated checks of
  one profile always get the same colours, so this month's figures compare
  patch by patch with last month's. The chart already carries the profile, the Print Chart tab selects
  Raw for it by itself, and for a verification run with a built profile this
  module is the one Create Chart opens on.

- **A verification chart can be printed THROUGH its profile.** The Print
  Chart tab's **Colour** row chooses "Through the profile" (ChromIQ converts
  every patch itself — the printer's own colour management stays off, so
  nothing is ever converted twice) or "Raw — no profile". The choice, the
  profile file and the rendering intent are written into a print record
  beside the chart, and the report states them for every sheet.

- **Sheets ChromIQ did not print are asked about, once.** Measuring or
  importing a verification sheet that has no print record raises *"How was
  this sheet printed?"* — Raw / With colour management / Not sure (always
  safe, stores nothing). The answer is kept with that one measurement.

- **Import a measurement made in another program.** With **Run type** set to
  **Verification**, the Measure tab shows an **IMPORT** module (it exists
  only for verification runs): it files an i1Profiler (or any .ti3)
  measurement as a dated verification — converted, checked patch-for-patch
  against this run's chart, and stored exactly where a native measurement
  would go. Your original file is never touched.

- **The report judges every sheet by the fair yardstick.** A print that
  mapped white to the paper — through the profile with relative intent, or
  another application's colour management — is judged **relative to its own
  paper white**; everything else is judged **as measured — no white
  adjustment** (a way of comparing, not a rendering intent). The report says
  which was used, per sheet, and physical readings like paper white and
  deepest black always stay as measured.

- **Colour accuracy is split into within / beyond the profile's gamut.**
  Some design colours are simply not printable on a given paper; their
  distance describes the gamut, not a mistake of the profile. The report
  shows both groups — side-by-side columns in the detail chapters, row
  blocks in the Overview so dated columns stay comparable — and Pass/Fail
  judges the within-gamut figures. Every patch stays counted and visible.

- **Raw sheets get a drift figure instead of an unfair verdict.** A sheet
  printed raw is not expected to match the design, so it is never graded
  Pass/Fail against the profile thresholds. Instead the report compares it
  with your **previous raw check of the same chart** — print against print,
  patch by patch. The first raw check becomes the baseline; checks made with
  different charts are refused rather than mispaired.

- 📈 **The Measurement Report grew into the profile's health record.** It
  gathers every dated check of a run automatically, trends colour accuracy,
  paper white, darkest black and the cube corners over time, lets you
  untick individual runs, warns about mixed instruments and mixed printing
  methods, carries adjustable Pass thresholds, and remembers every option
  you set. **Save report as PDF** produces a print-sharp document (vector
  text, ~300 dpi charts) whose proposed folder always matches what the
  report covers — one dated check, one run's checks, or the whole profile.

**🧰 And the rest:**

- 🧭 **The run bar — one place that says what you are working on.** Above the
  tabs, on every tab: **Profile run**, **Run type** (Profiling,
  Verification — and Calibration, once its options are enabled in
  Preferences) and — for verifications — which dated check,
  each with its own ⓘ explanation. Beside them sit the run actions:
  duplicate a run, restore the chart a measurement was made with, and
  delete — with a window first that says exactly what would happen. The
  whole app follows the bar: Create Chart, Print, Measure and Build Profile
  always show the run it points at, and when no project is loaded the bar
  says so instead of guessing.

- 📦 **Ready-made Red River Paper charts.** Four built-in starting points in
  Create Chart carry Red River's own 2052-patch Standard Patch Set v25 —
  byte-identical to their published file — laid out and verified for i1Pro
  (A4 and Letter, with the clip-border record) and ColorMunki. The patch
  set is fixed so results stay comparable; every layout control (paper,
  margins, branding) stays yours to change.

- **Every setting belongs to the run you set it on.** Create Chart, Measure
  and Build Profile each remember their own settings per run — and per run
  type, verification included; switching run, opening a project or changing
  run type loads them, leaving a tab saves them — without a dialog. This
  holds before any chart exists, and a generated chart's own file records
  the complete recipe that made it, so returning to a run always shows the
  options its sheet was really built with. A brand-new run starts from the
  values of the run you were on — by design, so "make another run like this
  one, with one change" needs no preset.

- **Runs have descriptions.** "Matte paper, second attempt" appears in the
  run bar, the measurement report and on the printed chart
  (`{rundescription}`); verifications and the calibration have one too. The
  profile description writes itself from project, run and date — editable,
  or off. And the installed copy of a profile can be **named after its
  description** (a checkbox on Build Profile), so the profile picker in your
  editor reads like your own words.

- **Calibration is a run type.** Once **"Enable calibration options"** is
  ticked in Preferences, **Calibration** appears in the Run type list —
  choose it and the whole app follows: chart, measurement, `.cal` file and
  its description live in the project's `cal/` folder, shared by every run,
  and each profile run records which calibration it was built with — one
  run can keep an older calibration with "Include" while another applies
  the new one.

- 🔔 **Sounds during measurement** — a strip accepted, a patch misread, a
  session finished — so you can keep your eyes on the chart. **Preferences →
  Sounds** — pick a sound per event, or point ChromIQ at your own sounds.

- **A gentle warning when you swipe a strip too fast.** Every instrument
  takes a fixed number of readings per second, so a strip has a minimum
  time it needs — swipe faster and patches get too few readings, even when
  ArgyllCMS still accepts the strip. ChromIQ knows the pace for your
  instrument, shows a live verdict while you measure, and mentions it when
  a strip was read quicker than the minimum, so you can re-read it before
  it costs you accuracy — the strip reading times under the chart preview
  mark such a strip with an **✕**. Tune or switch it off under
  **Preferences → Measurement** ("Warn me when I read a strip too fast").

- 📖 **The "Getting started" help card was rebuilt**: a clickable chapter
  index, chapters that walk from first start to a finished profile, its own
  chapter on checking a finished profile (the three ways, and which to
  pick), and a plain-language overview of where your files are stored — in
  all twelve languages.

- 🌍 **Twelve languages, complete** — German, Spanish, French, Italian, Dutch,
  Portuguese, Swedish, Norwegian, Polish, Russian, Japanese and Chinese —
  every button, message, tooltip and help text.

- **Demo projects for learning and testing**, attached to this release as
  downloads:
  [ChromIQ-demo-projects.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/ChromIQ-demo-projects.zip)
  demonstrates the file-handling rules step by step (including projects in
  the old 3.13 layout, to watch the migration happen),
  [Demo-Report-Matrix.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/Demo-Report-Matrix.zip)
  holds thirteen documented Measurement Report cases with one ready-made
  PDF per case, and
  [ChromIQ-Switching-Demo.zip](https://github.com/itsab1989/ChromIQ/releases/download/v4.0.0/ChromIQ-Switching-Demo.zip)
  demonstrates the per-run settings rules with documented test cases.

- **Preferences → "Hide the log panel on every tab"**, for when the chart
  preview deserves the room. The full log is still written to disk.

### Changed

- **The ChromIQ layout engine is the default for new charts** — in Manual
  mode too, where printtarg stays one untick away (Guided has used the
  engine all along). A saved echo of the old off-default is migrated once;
  a choice you make yourself is never touched, and charts that exist keep
  the layout recipe recorded in their own file.

- **The chart-reading engine has left the Beta tab.** It and its
  companion options (patch flagging, calibration retries, faster
  connection, the misalignment warning) now live at the top of
  Preferences ▸ Measurement, and the engine no longer carries a beta
  label — only the profile engine is still experimental.

- **The measurement report explains its own limits.** *How to read this
  report* now says what the one ΔE figure bundles — the profile's
  conversion of each colour, the printer's behaviour on the day, the
  instrument's own small uncertainty — and points to Check & Refine ▸
  **Analyse Profile Quality** as the check that looks at the profile
  alone. It also says plainly what the figures are for: comparing a
  profile with itself over time, not ranking papers or printers against
  each other. The coverage line in Create Chart and the report's
  within-gamut note now carry percentages besides the counts.

- **Preferences links the ChromIQ website.** The "Created by" line above
  the buttons carries a **Website** link in the app's accent colour — one
  click to the showcase page.

- **The measurement report breathes, and its PDF prints the same
  everywhere.** A small gap under every section headline, after the intro
  lines, and between the four trend charts; each section starts on its own
  PDF page, and a table always keeps its headline beside it. Headline sizes
  are pinned, so a saved report renders identically wherever it is made.
  The report window opens a little wider, and the console warning about a
  missing "Sans-serif" font is gone.

- **The measurement model is consistent everywhere.** Replacing a chart,
  rebuilding one, measuring over an existing measurement, deleting a run —
  each has one window, one wording and one outcome, whichever tab you reach
  it from. The rules live in `docs/design/` and the app is tested against
  them.

- **Nothing is deleted, only archived.** Replaced measurements, regenerated
  charts, redone calibrations and replaced verification charts all move to a
  dated `old/` folder — and the windows say so before you commit.

- **Every measurement keeps a copy of the chart it was measured with**, saved
  the moment measuring starts — profile runs, dated verifications and the
  calibration alike — and **Restore Used Chart** puts it back. A dated
  verification is always judged against the chart *it* was measured with,
  even if the shared chart was replaced later.

- **File dialogs are ChromIQ's own everywhere** — with the sidebar shortcuts
  to your working folder — instead of the bare system dialogs.

- 🗂️ **Existing projects are migrated in place.** A project from 3.13 or an
  earlier 3.14 is reorganised into the new folder shape the first time it is
  opened — every old file kept, the plain-language folder guide ("Where are
  my files?" in the Welcome window) always current.

- **The interface holds still.** Buttons sit in the same place on every tab,
  the log panel ends on the same line shown or hidden — and can be dragged
  as large as the window allows — the run bar no longer shifts during
  start-up, and windows placed off-screen by the system are nudged back so
  their bottom row of buttons is always reachable.

- **The icons were drawn for the job.** Load Project and Load chart have
  their own recognisable icons, the Duplicate and Calibration actions got
  purpose-made marks, and the run bar's action marks were aligned optically
  — reviewed on screen, in light and dark mode, before being adopted.

- **The windows that ask what to do with a chart read like every other
  window** — explanation in plain text, buttons in a row, Cancel set apart,
  long project names shortened in the middle with the full name given in the
  text.

- **ChromIQ starts a little quicker** — the printer list is fetched when you
  first open Print Chart rather than while the window is being built.

### Fixed

Two hundred and twenty-four betas fixed far more than fits a list — the
per-beta histories in the repository carry the complete record. What users
met most sat in measuring and in chart handling, so those come first:

**While measuring:**

- **Pressing Esc during a measurement no longer throws your readings away.**
- **Patches no longer come back as "inconsistent" for no visible reason** —
  the tolerance sent to the instrument was stricter than the manufacturer's
  own default.
- **Several measurement windows never appeared at all** when the ChromIQ
  reading engine was in use — the abort confirmation, failure windows, and
  two that opened in silence. All reachable now, verified against a real
  instrument, and the sound tables for every window are written down as
  specification.
- **A resume no longer archives the measurement it resumes from**, a
  finished re-measurement of a whole chart announces its completion, and a
  good measurement is no longer called foreign while guided refinement
  loses its ticks.
- **The "this chart already has a measurement" window opens showing what
  the panel actually says** — its old answers could quietly switch an armed
  refinement off and turn the next read into a replacement.
- **"No instrument found" fired once per app run** instead of every
  attempt, and the abort window wording was reworked.
- **Text typed for a "New run" is kept**, and lands on the run you make.
- **The strip reading times sit exactly under their strips** — they used to
  drift right of their strips as the preview re-fitted; they are placed
  live at every paint now, and on a small window they split into two
  staggered rows so every time stays readable.

**Charts and previews:**

- **"This chart was made for a different instrument" could name the wrong
  instrument** — it compared your connected device against a setting rather
  than against the chart itself.
- **Restoring a calibration chart put back a completely different chart**,
  and a calibration restore redrew the selected run's chart.
- **The chart patch-set editor and the 3D patch view opened the run's
  chart, not the chart you had selected.**
- **The windows that ask what to do with a loaded chart were rebuilt** —
  explanation in plain text, buttons on one row, Cancel set apart, long
  project names shortened without clipping ("JSE AS BASE FOR A NEW
  PROFILE" is gone: windows widen to fit their buttons, everywhere).
- **The auto-update preview judged the wrong chart** after switching
  modules, and a switched-off option now looks switched off in both
  themes.
- **printtarg margins were applied in the wrong order** (top/right/bottom/
  left confusion) — charts now sit where the instrument minimums say.

**Reports, projects and the app around them:**

- **Checking for updates works again for stable versions.** The check used
  to fail with "No release tag found" whenever the newest releases were all
  betas; it now asks for the latest finished release directly.
- **The measurement report's PDF paginates cleanly** — headings stay with
  their tables, the trend legend never overlaps the graph, and charts print
  sharp instead of pixelated. The proposed save folder follows the
  four-location design again. The report window itself keeps its run list
  to five lines, its charts readable and its buttons on screen at every
  window size.
- **A damaged `meta.json` no longer stops a run remembering anything**, and
  runs write their metadata atomically.
- **Help texts tell the truth.** The verification help card described a
  colour-management print path the app deliberately prevents; the gamut
  check was described as a drift check; "as measured (absolute)" read like
  a rendering intent. All corrected — and every such correction is now
  guarded by a test.

### Internal

- The test suite no longer writes to your own ChromIQ preferences.
- `docs/design/` holds the agreed, binding specifications: the measurement
  model, the message catalogue, per-target settings, the measurement windows
  and their sounds, calibration as a run type, and verification printing;
  the suite fails when code and specification disagree.
- Two purpose-built demo generators (`scripts/make_demo_projects.py`,
  `scripts/make_report_demo.py`) build test projects entirely from the real
  Argyll pipeline, and on-screen drivers verify the app against them —
  54 automated expectations for the Measurement Report alone.
