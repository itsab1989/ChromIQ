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
  saved as typed): A4 landscape one pass (36 x 28 of 6.5 mm), Letter
  landscape one pass (36 x 30), Barbieri standard area 225 x 180 mm (30 x 24
  of 7.5 mm), full reading area (36 x 30 of 6.5 mm), film frame 9.25 x 7.75 in
  (3 mm transmission, 2032 ppi, 34 x 28 of 6.5 mm) and 35 mm frame
  4096 x 2730 px at 2731 ppi (0.5 mm, 36 x 23 of 1 mm). Each gives exact
  numbers to both programs (spans in whole 0.1 mm, a Gateway target size in
  whole mm); a size a person makes that does not is said in the steps window.
* **Guided** offers A4 and Letter (landscape first) for the 3 mm and 6 mm
  openings, and only the two film frames for the 0.5 mm opening; Manual keeps
  every paper for every opening. The two film frames need the page-output Beta
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

## ⏳ Awaiting confirmation: the Spectro32 import (step 2, 2026-11-24)

**Confirmed by:** *nobody yet.*

*Written from Basti's brief of 2026-11-24 ("work on the import with what he
gave us"). What the app does, verified by tests on synthetic files of the
owner's 896-patch geometry and on screen without an instrument. No transmission
file from a real Spectro 100xy has been seen.*

* **Where:** the Measure tab's IMPORT module, for a profiling or a verification
  run whose chart is a Barbieri chart with its side file, while the Beta is on
  (`workflow/barbieri/spectro32_import.py`; the door is
  `TabMeasure._convert_barbieri_import`, the rule `measurement_import.assess`).
  START MEASUREMENT keeps showing the Spectro32 steps (ChromIQ cannot drive the
  100xy yet); their paragraph on bringing the measurement back now says how.
* **Files taken:** Spectro32's `_measurements.txt`, `_VAL.txt` or
  `_spectrum.txt` (tabs, CRLF, cp1252 or UTF-8, a decimal comma accepted), one
  per page; a chart of several pages needs every page's file at once, each
  matched to its page by its colours. The same run's `_VAL.txt`, `_XYZ.txt`
  and `_LAB.txt` beside it add Spectro32's colour setting and its own colours.
* **Pairing:** reading k is the k-th patch of the page's `reading_order` in the
  side file (rows from the top, each from the left). The side file must hold
  the `.ti2`'s SHA-256. The filed copy has the `.ti2`'s rows in its own order
  with their SAMPLE_ID, SAMPLE_LOC and device values, XYZ computed from the
  spectra by ArgyllCMS's method (D50, 1931 2 degree), and the 41 bands in
  percent, as chartread writes them; `CHROMIQ_PAIRED_BY_BARBIERI_ORDER`,
  `CHROMIQ_BARBIERI_MODE`, `CHROMIQ_BARBIERI_HEAD`, `CHROMIQ_MEASURED` (the
  file's date) and `TARGET_INSTRUMENT "Barbieri Spectro 100xy"`.
* **Refused, nothing written (M-IMPORT-BARBIERI-REFUSED):** not a Spectro32
  file; colours only; no readings; not 41 bands; a line of another length; a
  value that is not a finite number (a failed reading); reading numbers with a
  gap; spectra above 2 or below -0.05; a count other than the page's cells; the
  wrong number of files; a file that fits no page clearly or two files for one
  page; a side file missing or of another version of the chart; readings that
  fit no arrangement; a sheet mirrored, upside down or turned half round, or a
  head aimed one patch beside the aim patch (named in the reason).
* **The arrangement check:** the chart's expected colours (the `.ti2`'s XYZ)
  are fitted to the readings for the sheet as it should lie and for each wrong
  arrangement (median residual over the readings' spread; owner's real chart:
  0.15 right, 0.98 to 1.0 wrong). Where the fit cannot tell, the check patches
  decide, each predicted from the other patches (right 12 to 13 dE76, wrong 34
  to 48 on the tests' printer); where they cannot either, the person is asked
  (M-IMPORT-BARBIERI-CANNOT-CHECK, Cancel the default).
* **Spectro32's own colours:** compared with the spectra (owner's run: 0.014
  dE76 at most; limit 0.5). Another Spectro32 illuminant / observer that
  explains them is only noted; an unexplained difference is asked about
  (M-IMPORT-BARBIERI-COLOURS-DIFFER, Cancel the default).
* **Transmission:** filed exactly like reflection (ArgyllCMS's chartread writes
  no keyword for it); the "done" window and the log say to set Media Type
  (-Z t) to Transparent (and the polarity for a negative) in Build Profile.
* **Log:** every file with its SHA-256, kind, template line and setting; every
  page's grid, first and last patch, the fit numbers and what decided; the
  colour comparison; every refusal and answer.
* **Not in this step:** Gateway's CGATS files; several reads of one chart
  averaged on import; the Spectro32 template `.TXT` export; Build Profile
  setting Media Type by itself.

*Provenance: the reading of Spectro32's files follows `barbieri_to_ti3.py` 1.1
by LVTguru (archives Barbieri-to-TI3-1.1 and Barbieri-Chart-Tools-1.0, issue
215, offered under ChromIQ's GPL-3.0 licence); what was taken and what was not
is listed in the module's docstring.*
