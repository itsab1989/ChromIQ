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
  files, the PDF and printing stay portrait. The patch set editor's page
  view turns with the same rule (its clicks, marquee and highlight follow);
  the measurement report shows no picture of the chart, so it has nothing
  to turn.
* Defaults, chosen for ChromIQ's own reading with the table and to be
  confirmed by the first real scan: patches 10 mm along the strip x 8 mm
  across, Coloured contrast spacers of 1 mm between them (the layout
  ArgyllCMS gives every i1Pro strip, read by the same driver's patch finder),
  no gap between strips, 10 mm of blank paper before the first and after the
  last patch of every strip, the strip letters beyond every strip's left end and the
  patch numbers along the top (both upright on the table), the numbers 10 mm
  in from the paper edge so a printer's unprinted edge leaves them whole,
  three numbered aiming crosses, on by default and an option (see "Aiming
  crosses" below; the Instrument (i), the Beta's (i) and every greyed
  control's tooltip say so) (on the table 1 top left, 2 bottom left, 3
  bottom right; each digit beside its cross along the strip direction, so
  the side bands are only the cross and its clearance and the marks cost one
  strip on A4 and none on Letter), the ChromIQ wordmark, the page "N/M", the chart name and
  Manual's sheet text as one group centred between crosses 2 and 3 along
  the table's bottom edge, each part's visual middle on the line through
  their centres (a long text is shortened before the logo shrinks); the
  wordmark set as on every other chart, one baseline for Chrom and IQ.
  **Nothing is printed on a scan line outside the patches** (no edge
  spacers, no labels in a run). No arrow, no helper markers, and no clip
  border unless one is switched on (see "Clip border" below).
  Per sheet: A4 528 (572 without spacers), Letter 506 (552); without the aiming crosses more (see below). Every number,
  its source and its confidence are in `workflow/i1io/table_facts.py`.
* Manual: margins (down to the safe minimum), patch area alignment (any of
  the nine places; nobody's pick: centred with the crosses, at the patch
  numbers without them), patch size (8.9 to 20 mm along the strip, 7 to
  20 mm across), spacers (Coloured, Black & white, None), spacer size (1 mm
  up to a fifth of the patch length), own spacer colours, Inter-patch gap
  (along a strip, at most 20 % of the patch length), Strip gap (between
  strips, 0 to 3 mm), the aiming crosses, strip letters and patch numbers
  on/off and size (at most 6 mm; a larger size moves the strips down, never
  into the letters), their label patterns, face, underline and alignment,
  sheet text with its Insert menu, face and size, the clip border, paper,
  pages, randomisation, calibration and output are live (see "Label
  options" and "Clip border" below). Every other layout
  control was reviewed one by one (2026-11-13) and is greyed only for a
  concrete reason (ink where the aperture passes, leaving the area a printer
  prints or the table reaches, breaking the scan, or no meaning on a table);
  its tooltip gives that control's own reason first, and it shows the value
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

### On: Aiming crosses, an option (2026-11-13)

*The owner, relayed 2026-11-13: "in theory we could add an option to turn on
the crosses (or not in turn) and then make even more patches fit a single
sheet? the info should then mention what to aim at. it either knows from how
the chart was created what to tell or should mention both things"; "without
the crosses then the chromiq logo and probably sheet text would also go
away"; "guided mode gets the option as well".*

* "Aiming crosses", on by default, in Guided (on the instrument's own option
  line, where a SpectroScan or CR30 shows "Hexagon patches") and in Manual
  (in the slot of "Print helper markers", which an i1iO chart does not use;
  the group is titled "Aiming marks" while the i1iO is chosen). Its (i), the
  same in both, says what the crosses are for, that the table needs three
  points and not crosses, the patch count both ways on the current sheet,
  page 1's three aiming patches by name, what else changes on the sheet, and
  that the chart records the choice. Kept by the recipe, presets, Save as
  Defaults (`chart_i1io_crosses` for Guided), the run's Guided row and, with
  the Beta off, carried untouched.
* Off: a side needs only the printer's edge (5 mm) and, on the left, the
  patch numbers' band; the block starts at the numbers and what is left goes
  to the table's bottom edge. The page's three aiming points are the centres
  of its corner patches, as the sheet lies on the table: the first strip's
  patch 1 (top left), the last strip's patch 1 (bottom left) and the last
  strip's last patch (bottom right), named as printed (A1, W1, W24 on a
  full A4 page; the letters run on across pages). The engine's own page
  filling pads the last strip, so they always exist.
* The four corner slots of every page then hold clearly visible patches of
  the set: L* at most 60 and C* at least 25 or L* at most 45, never L* 85 or
  more, each the one that differs most from the paper and its neighbours.
  Only positions change (swaps); the set and its count do not, the order is
  reproducible from the seed, and the `.ti2`, the TIFF, the `.strips.json`,
  the side file and the `.cht` are written from one order. Every other
  instrument's order is untouched.
* Every page is aimed at on its own (each sheet is laid down by hand). A
  page of one strip, or one whose corner holds no visible patch, keeps its
  crosses, recorded for that page: nobody is told to aim at paper.
* The text line (name and page N/M, sheet text, logo) is printed only where
  it costs no patch and at least 10 mm from every paper edge (the patch
  numbers' own distance, past every unprinted edge ChromIQ knows: a Canon
  PRO-300 leaves 6.4 mm of a Letter sheet): beside the last strip (the
  table's bottom edge), else between the paper's edge and the patch numbers
  (the top edge, only when the numbers are off or a margin is wide). On a
  full A4 or Letter page neither is free that far in, so the line is left
  off there, and the help of "Aiming crosses" says so and asks for the name
  and page number to be written on each sheet by hand. Priority: the name with the page
  number, then the strip letters and patch numbers (their own places), the
  sheet text, the logo; each shrunk (text down to 1.5 mm capitals, logo to
  2 mm) before it is left off, a long sheet text shortened before the logo
  shrinks; centred between the two corner patches of that edge.
* Recorded: `.ti2` keywords `CHROMIQ_I1IO_AIM` ("crosses" or "corner
  patches"), `CHROMIQ_I1IO_AIM_DIGITS` ("yes" when the numbers 1, 2, 3 are
  printed beside crosses, "no" otherwise) and, without crosses, `CHROMIQ_I1IO_AIM_PATCHES` ("1: A1 W1 W24;
  2: crosses"), both declared; the side file's "aim", "labels_printed" and,
  per page, "aim", "digits_printed", "aim_patches" and "aim_points" (in mm on the page and on
  the table, in aiming order). A chart without the keyword is "unknown".
* What to aim at follows the record: the last paragraph of M-I1IO-NOT-YET and
  M-I1IO-NOT-YET-BY-HAND (M-I1IO-AIM-CROSSES, -CORNERS with the patch names
  per page, -CORNERS-UNLABELLED with position words only, -UNKNOWN with both
  ways), and the Print tab's note on how to lay the sheet down.

| Per sheet | A4, crosses | A4, none | Letter, crosses | Letter, none |
|---|---|---|---|---|
| default (10 x 8 mm, coloured spacers) | 528 | 552 | 506 | 528 |
| no spacers | 572 | 598 | 552 | 576 |
| maximum (no spacers, 7 mm across x 8.9 mm along) | 725 | 783 | 702 | 729 |

The "none" columns are Manual at its floor. Guided, which has no margin
boxes, keeps the right edge's room for the name and page line without the
crosses (review 5, item 4, awaiting confirmation; the owner: the name and
page number come first), so there the count is the same as with them.
A chart offset is fitted into the layout (review 5, item 2): the floor on the
side the patch block moves towards grows by the offset, so fewer patches fit
and the chart builds as estimated; only an offset that leaves no room for one
strip is refused.

### On: Clip border, an option off by default (2026-11-13)

*The owner, 2026-11-13: "the clip border should be possible to enable if a
user wants it as an option. just off by default".*

* The table holds the sheet, so the band holds no clip: it is the engine's
  notes band (Notes box, custom text, ChromIQ branding or an image, the
  "Clip-border content" group), as on a ColorMunki, SpectroScan or CR30
  chart. Manual: the "Clip border" Off/On selector those instruments have,
  shown for the i1iO, Off by default; the content controls live; "Side"
  greyed on Left with its reason. Guided: its own "Clip border" box on the
  i1iO's option line, unticked by default (setting `chart_i1io_clip_border`),
  the Notes box at 26 mm. Recipe field `i1io_clip_border` (written only when
  on), never `clip_content_mode`, whose default "notes" would have switched
  the band on for every recipe saved before.
* Always on the page's LEFT edge (the table's top edge): the other long edge
  holds crosses 2 and 3 and the name line. Width from the paper edge, at
  least 20 mm (default 26). Content from 10 mm in (the "Clip" distance the
  patch numbers keep) and 10 mm from the page's top; at the bottom it ends
  21 mm from the edge, 1 mm above cross 1's zone, with the crosses on or off
  (without them a short last page still keeps its crosses).
* Clear of every run, cross, strip letter and patch: `check_sheet` refuses a
  band touching a cross or a run, or content within 1 mm of a patch; the
  patch numbers follow the band (the engine's own row-label rule) and the
  left margin's minimum includes it. Without crosses the free "top edge"
  spot for the name line starts past the band.
* Capacity from the one geometry, shown live: A4 528 -> 480 with crosses,
  552 -> 504 without; Letter 506 -> 462 and 528 -> 484 (26 mm, defaults).
* Side file `"clip_border": {"side", "width_mm", "content", "area_mm"}`
  (written only when on); the `.ti2` gains nothing.

### On: Label options (2026-11-13)

*The owner, 2026-11-13: "cue up the label options for later" (queued after
4.3.33: label patterns, and the font / underline / alignment controls for
the sheet text and the labels).*

* With every option at its default the chart is 4.3.33's, file for file
  (the `.ti2`, the TIFF, the PDF, the `.strips.json` and the side file's
  geometry compared byte for byte on eleven charts).
* Strip and patch label patterns: the recipe's, as on every chart; the
  `.ti2`, the patch numbers, the strip letters, the side file, the aiming
  patch names and the Measure tab follow; an unreadable pair is refused.
* Label face, Bold, Italic: the strip letters (drawn by the i1iO) and the
  patch numbers (the engine's).
* The strip letters' band (bottom margin): 4 mm edge + the longest label the
  strip pattern can print in that face (never less than two letters of the
  engine's face, which is today's band) + 1 mm + the underline's gap and
  thickness. The longest label is the widest glyph of every position of the
  pattern, so the estimate and the build agree without a strip count.
* Underline: the engine's rule between the labels and the patches, here
  1 mm past every run-out (never on a run): Black across the block,
  Coloured (5 segments) across it, Coloured (per strip) per strip.
* Letter alignment, the engine's rule for a side-turned label: Left ends
  each letter at its strip (today's place), Centre centres it in the band,
  Right starts every letter 4 mm from the paper edge.
* Sheet text face, size, Italic: the sheet text part of the name line only;
  the page number, the chart name and the logo keep Inter Bold 3 mm
  capitals. Auto size = those capitals in the chosen face; a size the band
  cannot hold across is reduced to the largest that fits. Bold is the
  i1iO's own (on, as the whole line was in 4.3.33) unless unticked
  (`LayoutRecipe.i1io_text_bold`, written only when False).
* An i1iO recipe 4.3.33 saved loads with the values it carries (fields it
  lacks take their defaults) and is built like any other: what the panel
  shows is what prints (the owner, 2026-11-13: the Beta is hours old, so a
  4.3.33 i1iO chart may lay out differently when generated again). With
  the Beta off, `i1io_text_bold` and `i1io_clip_border` are carried
  untouched.
* Still greyed, each with its reason: the sheet text's alignment (the line
  sits in free paper, between crosses 2 and 3 or two corner patches, with no
  margin to align to), the label rotations, the strip-indicator gap, the
  label offsets and the text distances.

### On: Options open, defaults safe (2026-11-13, Job D)

**Confirmed by:** *nobody yet.* (The owner's rule, 2026-11-13: "our defaults
should be safe but advanced users should be able to tweak as much as
possible"; what follows is how it was built, awaiting confirmation.)

* Live on the i1iO as on every instrument, defaults unchanged (a chart with
  the defaults is byte-identical to 4.3.33's): Chart offset X / Y, Edge
  spacers (switched off when the i1iO is chosen), Max strip length / Don't
  cap, the ruler helper markers (their group is now "Aiming crosses and
  ruler helper markers"), text distance B (the strip letters' distance from
  the page's bottom edge, and always past the markers' ink + 1 mm), Clip
  (the patch numbers' own distance from the page's left edge, its own
  field `i1io_numbers_edge_mm`, default 10 mm), the strip-indicator gap
  (extra paper beyond the 1 mm clearance), the strip letters' label offsets,
  and the sheet text's Alignment (its own field `i1io_text_align`: "Left
  margin" starts the line at the left end of its paper, either centre
  option centres it, the default).
* Still greyed, each with its reason: patch and spacer scale, Mode, the
  area-first layout, the clip border's side, Offset every second strip,
  Use instrument margins, straight strips (hexagons), the layout summary
  stamp, text distance T (nothing is printed at the top) and the label
  rotations.
* Refused (nothing is built, the reason is shown): an aiming cross off the
  sheet, a patch off the sheet, a patch touching a cross, a patch in the
  clip border, the clip border touching a cross, the clip border's content
  over a patch. The first two name the chart offset among the fixes.
* Built and said in the log as `[WARNING] The i1iO table may not read this
  layout well: ...`: a strip's blank paper near the paper edge or touching a
  cross or the clip border, the clip border's content within 1 mm of a
  patch, edge spacers, ruler helper markers along the top and bottom.
* Every option is kept by Save as Defaults, the layout preset bar, a named
  preset and the target's own stored state (§4 of
  `per_target_settings.md`); `tests/test_i1io_every_option_persists.py`
  walks every recipe field. An i1iO recipe that carries "Use instrument
  margins" no longer locks the four margins at the table's minimum. The
  preset bar compares an i1iO layout on the fields its chart reads, so a
  fresh i1iO layout is not "modified".

### On: Review 3 corrections (2026-11-13)

**Confirmed by:** *nobody yet.*

* Choosing the i1iO from another instrument shows the i1iO's own values of
  the options opened above (what it had when last left in the session,
  else the safe factory values); leaving it gives the other instrument
  back what it had.
* "Clip" places the printed patch numbers (from 1 mm on the i1iO; unset is
  10 mm).
* "Label offset" X is held inside the side text distance of both paper
  edges, as on every chart; the panel's notice and the build use the same
  answer. Strip letters or their underline on a patch, on an aiming cross
  or partly past the paper's edge, and patch numbers on a cross or partly
  past it, are said in the log and under "Measured from Preview"
  (M-I1IO-FURNITURE-PARTS, proposed); wholly off the sheet is refused.
  So are letters or their underline on the blank paper of a strip's run
  (the table may take them for a patch) and patch numbers left off for
  want of room beside the strips (review 4).
* Opening another project's recipe keeps each instrument's own values: an
  i1Pro project's ruler helper markers do not become the i1iO's.
* A chart 4.3.33 made with the aiming crosses off reopens with its own
  smaller right margin.

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
Loading such a chart logs "Chart instrument: X-Rite i1iO." without the
strip-recognition detail other strip charts get, since no strip is read
(with the option off the line is 4.3.33's).

### Proposed for the measuring step (not built)

The `.ti3` names the head (its ArgyllCMS name, so FWA keeps working) and adds
a declared `MEASUREMENT_TABLE` keyword for the table. Note
`workflow/reference_convert.py` already maps "i1io" to the i1Pro family.
