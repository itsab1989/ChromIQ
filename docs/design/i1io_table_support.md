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

* Guided only: "i1iO 2 + i1Pro 2" (code `IO2`). Manual, the layout panel,
  Preferences > Chart Layout and the presets do not offer it yet; Guided's
  settings are not carried into Manual for an i1iO chart (a log line says so),
  and Tools > Edit patch set refuses an i1iO chart with a window.
* Sheets: A4 landscape and Letter landscape. The engine refuses a portrait
  sheet or one larger than the reach.
* Laid out by the layout engine for scanning rows along the sheet's long side:
  patches 10 x 8 mm, no gaps or spacers, 15 mm of blank paper before the first
  and after the last patch of every row with a 2 mm black bar 5 mm from the
  patches, three numbered aiming marks at the sheet corners (1 top left, 2
  bottom left, 3 bottom right), an arrow at the top centre towards the arm's
  resting place, "N/M" beside it on a multi-sheet chart, the chart name at the
  bottom. No labels, clip border, helper markers or stamp. 546 patches per
  A4 sheet, 528 per Letter sheet. Every number, its source and its confidence
  are in `workflow/i1io/table_facts.py`.
* Generate refuses, before anything is written, a layout where a patch, a run
  or a mark leaves the sheet or touches a mark.
* Files: `.ti2` `TARGET_INSTRUMENT "X-Rite i1iO"` (the family), declared
  keywords `CHROMIQ_I1IO_LAYOUT "1"` and `CHROMIQ_I1IO_TABLE "i1iO 2"`;
  `<stem>.i1io.json` with every mark, row, run, bar and patch centre in mm.
  A later i1iO / i1iO 3 entry gets its own code and writes the same family
  name, so no file already written is renamed.

### On: Measure

Start on an i1iO chart shows M-I1IO-NOT-YET before anything is recovered,
armed or written: measuring with the table is being prepared, the layout may
still change, and the i1Profiler route that works today.

### Proposed for the measuring step (not built)

The `.ti3` names the head (its ArgyllCMS name, so FWA keeps working) and adds
a declared `MEASUREMENT_TABLE` keyword for the table. Note
`workflow/reference_convert.py` already maps "i1io" to the i1Pro family.
