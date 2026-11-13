# X-Rite i1iO scanning table: preparation step (Beta)

> **These specifications are binding.** They must be consulted before changing
> code in the area they cover, and a fault that contradicts one is reported and
> approved before it is implemented; the specification may be the part that
> needs to change.

## ⏳ Awaiting confirmation: what the preparation step does (2026-11-13)

**Confirmed by:** *nobody yet.*

*Written 2026-11-13 from Basti's request ("prepares the implementation ... so
maybe we can already create a chart for it? of course hidden behind the beta
option") and his decisions of the same day: the goal is fast automated
scanning of rows; only the i1iO 2 with an i1Pro 2; only commands whose meaning
is known; a consent window when the option is switched on. What the app does
now, verified by tests and on screen without a table.*

### The option

* Preferences > Beta, "X-Rite i1iO support (beta)", off by default, restart to
  apply (`workflow/i1io/support.py`, setting `i1io_support_beta`).
* Ticking it opens a consent window first (the profile engine's pattern: no
  icon, "Keep it off" is the default, "Turn on i1iO support" is marked as the
  risky choice). Cancel leaves it off. Unticking asks nothing; ticking again
  asks again.
* The ⓘ and the consent window say: what the table is; that **this version
  sends nothing at all to a table and only makes charts** (THE ONE SENTENCE TO
  CHANGE WHEN MEASURING ARRIVES, in both texts); that the commands were worked
  out from one owner's recordings, not from X-Rite's documentation; that only
  known commands will ever be sent; that nobody on the team owns a table; that
  X-Rite ended support (i1Profiler 3.8.7 removed the i1Pro 2 and the i1iO 2);
  that only the i1iO 2 with an i1Pro 2 is supported and other owners are
  welcome on GitHub; own risk.

### Off: ChromIQ is 4.3.32, with one deliberate exception

No i1iO in any list, no i1iO chart code loaded (only the switch module), no
chart read for it, no key written. A target made with the option on keeps its
stored i1iO values while it is opened with the option off (the shared carry
rules, `workflow/beta_chart_carry.py`); a saved Guided default naming the
i1iO, and its sheet, read as none. **The exception:** Start on an i1iO chart
shows M-I1IO-SUPPORT-OFF, where 4.3.32 would have shown the "names an
instrument ArgyllCMS cannot use" window, whose repair could not tell which
instrument to name.

### On: Create Chart

* Guided and Manual: "i1iO 2 + i1Pro 2" (code `IO2`) in the Instrument lists,
  the layout panel and Preferences > Chart Layout.
* Sheets: A4 landscape and Letter landscape (Guided picks Letter landscape
  for someone on a US sheet, A4 landscape otherwise). The engine refuses a
  portrait sheet or one larger than the reach.
* Laid out by the layout engine for scanning rows along the sheet's long side:
  patches 10 x 8 mm with a 1 mm white gap between neighbours along the row
  (none between rows), 15 mm of blank paper before the first and after the
  last patch of every row, three numbered aiming marks at the sheet corners
  (1 top left, 2 bottom left, 3 bottom right), column letters above the
  patches and row numbers beyond the left end of every run, the ChromIQ
  wordmark beside mark 1, "N/M" at the top centre on a multi-sheet chart, the
  chart name (and Manual's sheet text) at the bottom. **Nothing is printed on a
  scan line outside the patches**, and a label keeps 1 mm from the patches
  across the scan; a label that cannot be placed safely on a sheet is left
  off there, never its clearance. No arrow: the numbered marks define the
  orientation. Capacity per sheet: A4 483 (504 without row numbers), Letter
  462 (484). Every number, its source and its confidence are in
  `workflow/i1io/table_facts.py`.
* Manual: the patch size (8.9 to 20 mm along the row, 7 to 20 mm across it),
  the strip letters and row numbers on/off and their size, the sheet text,
  paper, pages, randomisation, calibration and output are live; every other
  layout control is greyed with the reason and shows the value that applies.
* Generate refuses, before anything is written, a layout where a patch, a run
  or a mark leaves the sheet or touches a mark.
* Files: `.ti2` `TARGET_INSTRUMENT "X-Rite i1iO"` (the family), declared
  keywords `CHROMIQ_I1IO_LAYOUT "1"` and `CHROMIQ_I1IO_TABLE "i1iO 2"`;
  `<stem>.i1io.json` with every mark, row, run, label and patch centre in mm.
  A later i1iO / i1iO 3 entry gets its own code and writes the same family
  name, so no file already written is renamed.
* The patch set editor lays an i1iO chart out again as one (switch on).

### On: Measure

Start on an i1iO chart shows M-I1IO-NOT-YET before anything is recovered,
armed or written: measuring with the table is being prepared, the layout may
still change, and the i1Profiler route that works today.

### Proposed for the measuring step (not built)

The `.ti3` names the head (its ArgyllCMS name, so FWA keeps working) and adds
a declared `MEASUREMENT_TABLE` keyword for the table. Note
`workflow/reference_convert.py` already maps "i1io" to the i1Pro family.
