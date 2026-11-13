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
  icon, "Keep it off" is the default, "Turn it on" is marked as the risky
  choice). Cancel leaves it off. Unticking asks nothing; ticking again
  asks again.
* The ⓘ and the consent window say: what the table is; that **this version
  sends nothing at all to a table and only makes charts** (THE ONE SENTENCE TO
  CHANGE WHEN MEASURING ARRIVES, in both texts); that the commands were worked
  out from one owner's recordings, not from X-Rite's documentation; that only
  known commands will ever be sent; that nobody on the team owns a table; that
  X-Rite ended support (i1Profiler 3.8.7 removed the i1Pro 2 and the i1iO 2);
  that only the i1iO 2 with an i1Pro 2 is supported and other owners are
  welcome on GitHub; own risk. The confirm button reads "Turn it on", the
  cancel "Keep it off".

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
* An ordinary ChromIQ strip chart on a PORTRAIT A4 or Letter sheet (Guided
  picks Letter for someone on a US sheet, A4 otherwise), laid ACROSS the table
  a quarter turn clockwise (its top edge to the right), so its strips run
  along the arm (the table's scan moves change its X, along the 32 cm side:
  PROTOCOL 3.1, 4.4). Each strip is one line the arm scans in one move; strip
  letters, patch numbers ("C7" = the 7th patch of strip C), the spacers
  between the patches of a strip, the strip gap and the `.ti2`'s strip
  structure mean what they mean on every ChromIQ chart. The engine refuses a
  landscape sheet or one larger than the reach.
* Held as it lies on the table (landscape, cross 1 top left, 2 bottom left, 3
  bottom right), the sheet reads like text (the owner, 2026-11-13): strip A
  at the top, every strip's letter at its LEFT end, patch 1 at the left and
  the numbers 1, 2, 3 rising to the right along the top, every text upright.
  For this the patches of an i1iO strip run from the page's bottom up
  (`Geom.reverse_steps`, False for every other chart), the patch numbers are
  the engine's row labels beside strip A, and the strip letters are drawn by
  the i1iO at the strips' other end.
* Shown the way it is used: every preview (Create Chart, Print Chart,
  Measure, soft proof) turns an i1iO chart a quarter turn clockwise on screen
  through the preview's own view rotation, so overlays, the pointer readout,
  clicks and the strip highlight turn with it; the paper lists name the sheet
  "A4 (297 × 210 mm) Landscape" and "Letter (11 × 8.5") Landscape"; the Print
  tab says that the page prints upright and how to lay it on the table. The
  files, the PDF and printing stay portrait. Not turned yet: the patch set
  editor's page view and the measurement report's pictures.
* Defaults, chosen for ChromIQ's own reading with the table and to be
  confirmed by the first real scan: patches 10 mm along the strip x 8 mm
  across, Coloured contrast spacers of 1 mm between them (the layout
  ArgyllCMS gives every i1Pro strip, read by the same driver's patch finder),
  no gap between strips, 10 mm of blank paper before the first and after the
  last patch of every strip, the strip letters beyond every strip's left end and the
  patch numbers along the top (both upright on the table), the numbers 10 mm
  in from the paper edge so a printer's unprinted edge leaves them whole,
  three numbered aiming marks (on the table 1 top left, 2 bottom left, 3
  bottom right; each digit beside its cross along the strip direction, so
  the side bands are only the cross and its clearance and the marks cost one
  strip on A4 and none on Letter), the ChromIQ wordmark, the page "N/M", the chart name and
  Manual's sheet text as one group centred between crosses 2 and 3 along
  the table's bottom edge, each part's visual middle on the line through
  their centres (a long text is shortened before the logo shrinks); the
  wordmark set as on every other chart, one baseline for Chrom and IQ.
  **Nothing is printed on a scan line outside the patches** (no edge
  spacers, no labels in a run). No arrow, no helper markers, no clip border.
  Per sheet: A4 528 (572 without spacers), Letter 506 (552). Every number,
  its source and its confidence are in `workflow/i1io/table_facts.py`.
* Manual: margins (down to the safe minimum), patch size (8.9 to 20 mm along
  the strip, 7 to 20 mm across), spacers (Coloured, Black & white, None),
  Inter-patch gap (along a strip, at most 20 % of the patch length), Strip gap
  (between strips, 0 to 3 mm), strip letters and patch numbers on/off and size
  (at most 6 mm; a larger size moves the strips down, never into the letters),
  sheet text, paper, pages, randomisation, calibration and output are live;
  every other layout control is greyed with the reason and shows the value
  that applies.
* The ChromIQ logo never costs a patch: it is no layout input, it is drawn in
  the turned text line beside the strips, shrunk down to 2 mm before it is
  left off.
* Generate refuses, before anything is written, a layout where a patch, a run
  or a mark leaves the sheet or touches a mark.
* Files: `.ti2` `TARGET_INSTRUMENT "X-Rite i1iO"` (the family), declared
  keywords `CHROMIQ_I1IO_LAYOUT "1"` and `CHROMIQ_I1IO_TABLE "i1iO 2"`;
  `<stem>.i1io.json` with every mark, strip, run and patch centre in mm on
  the page, the turn, the spacers and gaps used. A later i1iO / i1iO 3 entry
  gets its own code and writes the same family name, so no file already
  written is renamed.
* The patch set editor lays an i1iO chart out again as one (switch on).
* The separate Beta "Also write an i1Profiler chart that matches the printed
  ChromIQ sheet" says, for an i1iO chart, that it cannot write a matching
  i1Profiler chart for the table yet and what has to be measured first.

### On: Verification and Calibration

*The owner, relayed 2026-11-13: "verification and calibration runs must work
like for other instruments."*

* Run type Verification and Calibration offer the i1iO and make their charts
  for it as for any instrument: the same options and flow, the files in
  `runs/runN/verifications/<stem>-verify.*` and `cal/<stem>-cal.*`, each with
  its `.i1io.json` and the `.ti2` keywords above, laid out with the i1iO's
  rules (a calibration's ink ramps each start their own strip, as on every
  calibration chart). FROM PROFILE GAMUT and printing through the profile
  work on it as on any chart; nothing there depends on the instrument.
* Which instrument a target with nothing stored opens on is
  `per_target_settings.md` §4 S5 / S8 (Knut's ruling): the saved defaults,
  else the factory i1Pro, for every instrument, so a fresh verification of
  an i1iO run opens on the i1Pro unless Save as Defaults holds the i1iO, as
  it does after a ColorMunki run. Once chosen, each target keeps the i1iO
  (§4 S1 to S3).
* A verification build puts the run's profiling chart back with its
  `.i1io.json` (it was archived without it before 2026-11-13).
* Start on a verification or calibration chart for the table shows
  M-I1IO-NOT-YET-BY-HAND: M-I1IO-NOT-YET's i1Profiler way ends in building a
  profile, which those charts are not for, so it names the table's own
  i1Pro 2, measured by hand, instead.
* The Measurement Report's evenness check applies to an i1iO chart
  unchanged: its nine areas are whole strips and rows by the chart's own
  labels, each one physical ninth of the portrait page (patch 1 at the
  bottom only mirrors which band is named first), and an area is named by
  the strips and rows printed on it (`tests/test_i1io_evenness.py`).

### On: Measure

Start on an i1iO chart shows M-I1IO-NOT-YET before anything is recovered,
armed or written: measuring with the table is being prepared, the layout may
still change, and the i1Profiler route that works today.

### Proposed for the measuring step (not built)

The `.ti3` names the head (its ArgyllCMS name, so FWA keeps working) and adds
a declared `MEASUREMENT_TABLE` keyword for the table. Note
`workflow/reference_convert.py` already maps "i1io" to the i1Pro family.
