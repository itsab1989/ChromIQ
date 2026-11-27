# X-Rite i1iSis family: chart creation (Beta)

> **These specifications are binding.** They must be consulted before changing
> code in the area they cover, and a fault that contradicts one is reported and
> approved before it is implemented; the specification may be the part that
> needs to change.

## ⏳ Awaiting confirmation: what the i1iSis chart Beta does (2026-11-14)

**Confirmed by:** *nobody yet.*

*Written from the owner's requests and rulings of 2026-11-14 (the Beta; the
old entry removed for everybody without migration; the header notes band in
the first version, off by default; every layout option open unless it has no
meaning or makes the chart unreadable) and the study
`ChromIQ-work/2026-11-14_isis_chart_study` (REQUIREMENTS v2, PROPOSAL v2, the
challenge and the response). What the app does, verified by tests and on
screen without an instrument. Nobody on the project owns an i1iSis; no
ChromIQ chart has been read by one.*

### The option

* Preferences > Beta, "X-Rite i1iSis charts (beta)", off by default, restart
  to apply (`workflow/isis/support.py`, setting `isis_charts_beta`).
* Ticking it opens a consent window first (no icon, "Keep it off" the
  default, "Turn it on" marked as the risky choice). Cancel leaves it off;
  unticking asks nothing; ticking again asks again.

### Off: ChromIQ is 4.3.37, with one deliberate exception

The printtarg instrument "i1iSis (via i1Profiler)" and its help bullet are
gone (the owner's ruling, see `issue_182_answers.md` §2y/§2z and the note
below §2z); a stored `isis` (Save as Defaults, a preset, a target's settings,
a 4.3.36 project) reads as no instrument (i1Pro, A4; the entry's own A3+, -n
and -P with it) with one log line, nothing written back until the person
saves (`data.patch_db.REMOVED_INSTRUMENT_CODES`,
`ui.tabs.tab_chart._saved_beta_instrument_is_off`). Start on an i1iSis chart
shows M-ISIS-SUPPORT-OFF. Nothing else of the i1iSis is offered, loaded or
read; a target made with the Beta on keeps its stored values untouched.

### On: Create Chart

* One entry, "i1iSis family" (code `XRISIS`), in Guided, Manual and the
  layout panel, with a model width: "i1iSis / i1iSis 2" (sheets up to 230 mm,
  right marker up to 218 mm from the paper's left edge) or "XL models" (330
  and 318 mm). Laid out by ChromIQ's layout engine only.
* Furniture as i1Profiler 3.8.8 draws it: the black bar 6 mm high, its top
  at header + 0.5 mm (header 32 to 80 mm, default 32), across every column of
  a full page; 6 mm clear under it (20 mm with the barcode); a 5 x 2.5 mm
  diamond at both ends of every row, 5 mm from the chart edge and 5 mm from
  the patches (4 and 3 with tight margins); patches side by side without
  gaps, 6 to 20 mm each way (default 6 x 6); trailer at least 25.5 mm; chart
  at least 171 mm long and at least 60 mm wide (white beyond the right
  markers when narrower); two feed arrows in the diamond columns; a dashed
  outline; the name and page line and the corner labels in the first 12 mm,
  the bottom corner labels in the last 3.5 mm.
* The name and page line ends in THE ChromIQ wordmark, drawn by the engine's
  own routine (`raster._draw_wordmark_h`, as the clip border's branding and
  the notes design draw it: Instrument Serif "Chrom", the magenta italic
  "IQ" after it on the same baseline), never the word typed as text. Its
  capital C stands as tall as the line's capitals, the text and the
  wordmark share one baseline, and its ink stays 0.75 mm under the outline
  and clear of the strip letters' zone and of the 20 mm before the bar (set
  smaller, down to half, when the band cannot hold it). On every page.
* *(2026-11-15, awaiting confirmation; the owner: "when the clipborder is
  turned on the information included in it don't need to double on the
  chart")* With the notes band on, the name line leaves out what the band on
  the same page prints legibly: the notes design's wordmark always, its
  profile name and "page x/y" when its text is set at 1.5 mm or more (the
  default 24 mm band sets 1.69 mm); the branding's wordmark when it fills the
  band; nothing for plain text or an image. With nothing left (no sheet text
  either) the line is not drawn; nothing else moves (`band_shows`).
* The name line never touches the top corner labels: measured with the
  real type (accents and other scripts included), 1.5 mm from each label.
  Too wide: the sheet text goes, the name is shortened with "…" in its
  middle (at least 8 characters; the files keep the full name), then the
  line is set smaller down to 1.8 mm; then, when the strip letters are not
  at the top, two lines (the wordmark between the corner labels, the name
  and page under them between the feed arrows); last the least needed part
  is left off and said (the M-ISIS-KEEP-OUT log line): the wordmark, then on a one-page
  chart the page, then the name. Never the page of a multi-page chart, never
  the corner labels. Strip letters and row numbers are measured in their
  own face and set smaller until neighbours cannot touch. *(4.3.40)* The
  row numbers end at least 0.5 mm (the
  outline's own line width) before the dashed outline's line
  (`ROW_NUMBER_GAP_MM`); set against the line itself they read as touching
  it.
* The grid is i1Profiler's rule (T = ceil(N / Cmax), P = ceil(T / Rmax),
  R = ceil(T / P), C = ceil(N / (R x P)); column-major; unused cells at the
  end white), reproducing all 38 layouts measured in i1Profiler.
* Placement: the chart's outline top-left inside the page margins (default
  5 mm), moved by Manual's patch area alignment and the chart offset.
* The cut rule: a sheet may be fed as printed when, from the paper edges, the
  paper is 60 to 230 (XL 330) mm wide and 170 to 660 mm long, the right
  marker within 218 / 318 mm, the bar's top within 80 mm of the leading edge
  and the left marker at least 3 mm in; otherwise the chart is still made and
  every instruction says to cut along the dashed outline. Refused
  (M-ISIS-SHEET-CHECK) only what cannot be read even when cut. More than 3000
  patches a page, or a chart over 660 mm, takes more pages instead.
* Options: every engine option that has a meaning on this chart works.
  Greyed, each with its own reason, are only the spacers and gaps, edge
  spacers and the strip-indicator gap (an i1iSis chart has no gaps), patch
  and spacer scale (no base size to scale), the mode row (one layout),
  offset strips and hexagons (the i1iSis reads a plain grid), "Don't cap
  strip length" (the page decides the rows), the side clip band and "Clip"
  (the band is the header or the trailer), the ruler helper markers (no
  ruler). Area-first, and the engine's own "Show strip indicators" and
  "Show row indicators" with their face, size, rotation, alignment,
  underline and offsets, draw the strip letters (top or trailer) and the
  row numbers, held inside their zone: clamped, or left off and said
  (M-ISIS-KEEP-OUT). Every option persists through Save as Defaults,
  presets, the target's settings and the chart's record.
* The notes band (off by default): in the header (the header grows by the
  band's height, up to 80 mm; the band ends 20 mm above the bar) or the
  trailer (from 22 mm after the last row), filled by the clip-border content
  and drawn for each page (its page number and the i1iSis's name, never the
  code). With the band off the run's chart notes and the settings line are
  printed in the trailer, one line each, shortened with "…" when too long.
* Papers in Guided: A4, Letter, A5, 5 x 7 in, 8 x 10 in; with XL also A3,
  11 x 17 in and A3+ (329 x 483). Manual: every engine paper and Custom.
* Every run type (profiling, verification, calibration) makes i1iSis charts
  in its usual folder.

### On: Files

`<stem>.isis.json` (every element in mm, the grid, the barcode text per page,
fed as printed or cut); in `exports/`, `<stem>-i1profiler-isis.txf` (device
"i1iSis" or "i1iSis XL", a custom page half a patch larger than the grid both
ways, the margins, patch size as slider percent, header percent, tight
margins, barcode, the patch list in placement order with ChromIQ's names) and
`<stem>-i1profiler-isis.order.json`; the `.pxf` beside every chart names the
device i1Profiler writes. RGB charts only for the `.txf` in this version.

### On: Measure and import

Start shows M-ISIS-NOT-YET before anything is armed: the i1Profiler steps, the
grid to check, the cut instruction, and for several pages that they are
measured in one go, in the order of their page numbers, and saved as one
measurement. Import Measurement pairs a measurement through the order file (by
position, checked by the device values).

*(2026-11-27, part 1 of the i1iSis pieces work, awaiting confirmation)* A
measurement of SEVERAL pages is brought back (until 4.3.67 it was refused,
"needs a later version"), paired by position as one page is: entry j is on
page j // (columns x rows). It is filed only when, randomised or not:

* every patch is in it once; a file that holds some pages whole names the
  missing ones (M-IMPORT-ISIS-PAGES-MISSING), part of a page is counted
  (M-IMPORT-ISIS-PARTIAL);
* i1Profiler's grid, when the file records it, is the test chart's columns
  and rows a page on its pages (M-IMPORT-ISIS-PAGES-GRID); "0 pages" says
  nothing about the pages;
* its places, when it records them, run page by page as ChromIQ's test chart
  writes them (the columns of each page from 0 or counted on). No i1iSis
  measurement of several pages is on record, so any other form (and a file
  that numbers its patches again on every page) is refused and the file asked
  for (M-IMPORT-ISIS-PAGES-FORM); places in another form are taken only when
  the colours clear every page by themselves;
* the colours: every page by the one-page judge, and the whole chart against
  every way the pages can go in wrongly (two swapped, one twice, another
  order). One that fits clearly better is refused and named
  (M-IMPORT-ISIS-PAGES-MIXED); a page that does not fit its own patches is
  refused (M-IMPORT-ISIS-COLOURS). Where the pages look alike the person is
  asked, Cancel the default (M-IMPORT-ISIS-PAGES-CANNOT-CHECK); a single page
  of a chart that is not randomised that cannot be checked asks
  M-IMPORT-ISIS-CANNOT-CHECK, as one page does; on a randomised chart such a
  page is filed as one page is.

Unproven: no i1iSis measurement of several pages is on record, so the form
i1Profiler writes is assumed only as far as its own saved test chart shows it
(columns and rows a page, the pages).

*(2026-11-25, item 63, awaiting confirmation)* Randomise does not decide
whether a measurement is checked. Pages, every patch once, i1Profiler's grid
and the colours are checked on a chart that is not randomised too; what its
colours cannot show (one colour, ramps, fewer than 20 patches) is asked before
anything is filed (M-IMPORT-ISIS-CANNOT-CHECK), never refused for it and never
filed in silence. Without the order file the order is worked out from the
chart and its side file; without both the measurement is refused
(M-IMPORT-ISIS-FILES). See §I.17 point 8 of the measurement specification.
**Not protected:** a single row or a single column slipped by one patch, and
half a sheet slipped by a column, can be filed, above all on a chart whose
colours are regular.

*(4.3.40)* ChromIQ never reads an i1iSis chart, so the Measure tab says
nothing about reading strips for it: its log names the chart's instrument
only ("Chart instrument: X-Rite i1iSis.", no strip-recognition clause) and
Guided's "Scan each strip with a slow, steady motion." under "Keep calm!" is
hidden. The i1iO table chart (also measured in i1Profiler) is treated the
same way; with each Beta off the tab reads as before.
