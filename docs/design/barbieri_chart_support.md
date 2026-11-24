# Barbieri Spectro 100xy: chart creation (Beta)

> **These specifications are binding.** They must be consulted before changing
> code in the area they cover, and a fault that contradicts one is reported and
> approved before it is implemented; the specification may be the part that
> needs to change.

## ⏳ Awaiting confirmation: what the Barbieri chart Beta does (2026-11-24)

**Confirmed by:** *nobody yet.*

*Written from Basti's brief and decisions of 2026-11-24 (step 1 of the
Barbieri integration: a chart Beta, its own instrument entry; the SpectroScan's
hidden top band stays; the 235 x 200 mm datasheet area is no block and no
warning, only a note with its source; ready-made sizes that suit the device;
no import, no template export and no device driving in this step). What the
app does, verified by tests and on screen without an instrument. Nobody on the
project owns a Spectro 100xy; no ChromIQ chart has been read by one.*

### The option

* Preferences > Beta, "Barbieri Spectro 100xy (beta)", off by default,
  restart to apply (`workflow/barbieri/support.py`, setting
  `barbieri_chart_beta`). Ticking it asks first (no icon, "Keep it off" the
  default); unticking asks nothing.
* Off, ChromIQ is what it was: no Barbieri entry in any list, no Barbieri
  module loaded beyond the switch, no chart read for it; Start on a Barbieri
  chart shows M-BARBIERI-SUPPORT-OFF (`tests/test_barbieri_off_changes_nothing.py`).

### The entry and its chart

* "Barbieri Spectro 100xy" (code `B100XY`) in Guided, Manual and the layout
  engine; `TARGET_INSTRUMENT "Barbieri Spectro 100xy"`, `.ti2` keywords
  `CHROMIQ_BARBIERI_LAYOUT` and `CHROMIQ_BARBIERI_HEAD`.
* **Measuring opening** (Guided and Manual): 3 mm reflection (Spectro32
  `MR`, 6.5 mm patches, the size an owner read 896 of in one run), 3 mm
  transmission (`MT`, 6.5 mm), 0.5 mm transmission (`M5`, 1 mm, untested),
  6 mm reflection of the second model (command unknown, 10 mm, untested).
  A patch smaller than the opening plus 0.25 mm each side is warned about,
  never refused.
* **Grid:** a plain rectangle per page, no run-up (the margins typed are where
  the patches begin), no spacers, gaps allowed, patch size first; patch size
  and gaps in 0.1 mm steps (other values rounded and said); at most 99
  patches across and down (Gateway's limit; extra width stays empty and is
  said); the last pass filled up with paper patches so every page is a full
  rectangle. New reflective charts: 15 mm left margin (the datasheets say 15
  or 35 mm; the help says so), 10 mm elsewhere, the right and bottom margins
  raised so the patch area stays inside 235 x 200 mm (a default only).
* **Reading order:** row by row from the top, each row from the left (A1, B1,
  ... last column, then row 2), never back and forth. Patch names are the
  engine's own: the column letter and the row number, so "AF1" is the top
  patch of column AF.
* **Marks**, in the margins only, on every page: thin corner marks whose arms
  continue the patch grid's outer edges (Gateway aims at three corners); the
  upper-right corner bold; two thin ticks continuing row 1 and the last
  column, crossing at the centre of the upper-right patch (where Spectro32 is
  aimed); a small solid square left of A1. They shrink with narrow margins
  (film frames); a margin too narrow leaves that side out and is said. An
  option, on by default.
* **Check patches** (an option, on by default; not on a calibration chart
  whose ramps each take a column): on every page the darkest patch of the page
  at A1, the most colourful at the upper-right patch, the lightest at the
  lower-left patch, and the two most different from those right of and below
  A1. Only positions move, within a page; the set and its count are unchanged.
  The side file lists each with its role, name, device values and expected
  CIELAB, for the import of a later step: a mirrored sheet swaps A1 with the
  upper-right patch, a sheet upside down puts another patch at A1, a vertical
  flip puts the lightest at A1, a shift by one puts B1's or A2's colour there.
* **Ready-made sizes** (Manual, built in, every value stays editable and is
  saved as typed): A4 landscape one pass (36 x 29 of 6.5 mm), Letter
  landscape one pass (36 x 30), Barbieri standard area 225 x 180 mm (30 x 24
  of 7.5 mm), full reading area (36 x 30 of 6.5 mm), film frame 9.25 x 7.75 in
  (3 mm transmission, 2032 ppi) and 35 mm frame 4096 x 2730 px at 2731 ppi
  (0.5 mm, 36 x 23 of 1 mm). The two film frames need the page-output Beta
  and are greyed with that reason without it.
* **Greyed in Manual, each with its reason:** spacers and edge spacers, the
  patch scale, the layout mode, offset strips and hexagons, the strip-limit
  switch, the ruler helper markers. Everything else stays open.

### Beside the chart, at Start and in the log

* Under "Chart layout information", for a Barbieri chart in the preview: the
  opening, per page Spectro32's line `R0,0,xspan,yspan,cols,rows` (spans from
  the first patch centre to the last, 0.1 mm), the aim patch and Gateway's
  numbers (patches across and down, target size count x pitch in whole mm),
  the patch area, the pitch, the pages and the reading time (1.9 s a patch).
* Start: M-BARBIERI-STEPS (§M-PROPOSED of `unified_measurement_management.md`).
* The app log: the options at Generate, and the chart, page and reading-time
  lines with the grid numbers.
* The side file `<stem>.barbieri.json`: every page's grid in mm, the numbers,
  the reading order, the check patches and the `.ti2`'s SHA-256.
