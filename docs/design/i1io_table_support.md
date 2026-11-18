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
* The ⓘ and the consent window say: what the table is; **"With this beta,
  ChromIQ can also drive an i1iO 2 table with an i1Pro 2 when you press START
  MEASUREMENT: it asks you once before the first time, and explains what it
  does."** (since 4.3.45, the release that drives, as the step-4 proposal
  section 4 has it: this sentence replaced "this version sends nothing at all
  to a table and only makes charts" and "only known commands will ever be
  sent", in both texts; the ⓘ's Measure line now says that START MEASUREMENT
  drives the table and IMPORT still brings back an i1Profiler measurement);
  that the commands were worked out from one owner's recordings, not from
  X-Rite's documentation; that nobody on the team owns a table; that
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

### On: Any sheet inside the table's reach (review 5, item 7, 2026-11-13)

**Confirmed by:** *nobody yet.* (The owner asked: "does the i1iO allow for
smaller and custom paper sizes as well?")

* Offered in Guided and Manual: A4, Letter, 8x10", A5, 13 x 18 cm, 5x7",
  4x6", 10 x 15 cm and the postcard; Manual's "Custom..." takes any size.
  Every one is named as it lies on the table (landscape), and printed, like
  A4, on an upright (portrait) sheet.
* How a small sheet lies on the table: like A4, across the table, its long
  edge along the arm's travel, so the strips (which run down the portrait
  page) run along the arm; the corner the strips start from is the same, so
  the aiming crosses, the letters, the numbers and the name line keep their
  places relative to the sheet. The previews turn it as they turn A4.
* The limit is the arm's reach as X-Rite publishes it (`table_facts.
  REACH_MM`, 320 x 230 mm; a PUBLISHED figure, not yet confirmed on a
  table): a sheet that, laid across the table, lies outside it is refused,
  and so is a landscape code and a sheet too small for one strip, each with
  its reason (M-I1IO-SHEET-CHECK-PARTS). A sheet larger than A4 or Letter in
  one direction but inside the reach is built and said to be untested.
* Everything adapts to the sheet: the capacity, the letter and number
  bands, the crosses (on a small sheet they may take paper patches would
  have; they can be switched off), and the name line, which is dropped
  before a patch is lost, and said.
* A4 and Letter charts are byte-identical to before.

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
  i1Pro 2, measured by hand, instead. (Since round A of the table drive,
  2026-11-17, only for a chart START does not drive: a chart for an i1iO 2
  with an i1Pro 2 is driven by the table in every run type, see the section
  "START drives the table" below.)
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

### ⏳ Awaiting confirmation: START drives the table in the Measure tab (build step 9, 2026-11-17)

**Confirmed by:** *nobody yet.*

Built and proved on screen against the simulated table only (no real table yet). With "X-Rite
i1iO support" on, START MEASUREMENT on a profile run's chart made for an i1iO 2 with an i1Pro 2
(its side file says so) drives the table, in Manual and in Guided; calibration and verification
charts, i1iO 3 and bare "i1iO" charts keep their Start windows; IMPORT is unchanged.

Before anything is opened, these of the hand path's guards: a run that exists, the laid-out
chart, a measurement laid out for an earlier version of the chart (#211,
M-RESUME-LAYOUT-DIFFERS), the i1Pro 2 lights left on (Preferences > Beta, asked for the i1Pro 2
in the table's arm), and the replace question M-REPLACE-*. The hand path's other guards are
covered or have no meaning: a differing -F is the job's own refusal of -F; a differing -H, -l,
-L or -n is the job's field check (the session then measures the rest the way the earlier
readings were measured, keeping the resume, M-I1IO-DRIVE-OPTIONS-FIELDS); unreadable chart
locations do not matter (the job reads by the side file and files by name); an instrument in
use is the app's measurement lock and the job's own instrument check before the USB is opened.
Then the USB library's read-only check, the one-time explanation M-I1IO-DRIVE-CONSENT (kept
with its text version, setting `i1io_table_consent_given`), an interrupted earlier session
(complete or discard), and how the Measure tab's options apply.

The table's questions, its status, Report a problem, End measurement, "To stop the arm at
once, switch the table off at its power switch" and ONE Stop (red, at the bottom of the panel,
the same place on every page) stand in the Measure tab's measurement area, where the options
stand. While the panel is shown, the tab's own START / STOP / SAVE AS DEFAULTS row, "Play
sounds" and "Save measurement report" (its value set before START still applies) and Guided's
"Keep calm!" banner make room, and the log keeps three lines. An answer that only ends the step
on screen is "End this step", never a second Stop. Nothing is modal and nothing covers the
chart preview. The rest of the app is locked as during a hand measurement (the other tabs, the
masthead's buttons and the run bar); in addition, while the table works, Cmd-1 to Cmd-5 never
switch to a locked tab and Cmd-, never opens Preferences (a hand measurement still lets both
through: reported, not changed). Esc anywhere in the main window, except in a text field (the
note field, the log), where it is the field's own key, does what the panel's Close does: it withdraws an open question with its own answer that moves nothing and asks the
ending, or withdraws the ending. Quitting ChromIQ (Cmd-Q, the close box, a logout) during a
session asks the table's own ending in the panel (a step that runs stops at its next pause
first); "Keep measuring" keeps ChromIQ open, any other ending closes it once the job has let go
of the table. If ChromIQ ends without that (a crash, a forced quit, a power cut), a marker
written when the table was opened makes the next START ask "switched off and on" before
anything is sent (M-I1IO-DRIVE-MARKER-APP-ENDED).

The preview follows the job: the mark the arm should point at while aiming; the row being
read in a thick frame in the accent colour with a light fill, a read row only a green dot in the white space between its label and its first patch, a row that could not be read a small cross in the warning colour there (in
both modes); with "Patch-by-patch mode (-p)" also a ring, drawn twice as thick as the hand
path's, on the patch the arm goes to (announced after the stop check, when the arm really
moves). Every reading goes into the live overlay and the "Progress" figure. The panel's state
box counts the rows and readings as they are read and says what the table does now. The asking
mode (setting `i1io_table_ask_after_each_step`, on for the first measurement, offered off
after a clean one, never after a Stop, a failed or skipped row or a problem, and in
Preferences > Beta under the i1iO option) asks after every step that moved; the quiet mode asks
only the consent (once), the hands-off GO and the ending. Every text is in §M-PROPOSED
(M-I1IO-DRIVE-*). The endings are M-END's three, in the table's own words
(M-I1IO-DRIVE-END-CHOICES) with the table paragraph M-I1IO-DRIVE-END, and M-END-EMPTY's line
when nothing was read; the homing is offered after Save or Discard and asks its own GO. With
the replace agreed at START, the run's measurement is moved to old/ only when the table's Save
writes the new one; if that Save fails, it is put back when the session ends.

The rows the table reads: with Refine / resume and "Refinement strips file" ticked and the
quality check's list loaded, only the list's patches (or, for a list of strips only, every
patch of those strips); the Save replaces exactly their readings and every other reading stays
(M-I1IO-DRIVE-REFINE); a resume reads only the missing patches (M-I1IO-DRIVE-RESUME). For a
chart the table reads, the Measure options with no meaning are greyed with their reason (the
instrument port, strip recognition, the patch consistency tolerance, the spectral filter) and
not sent; patch by patch is ticked and locked; every other option reaches the job. The run
keeps a copy of the chart at START as on the hand path (runs/runN/chart/). A new chart for the
run moves the table's session folders of the old one to old/ (a folder whose "switch the table
off" marker is unanswered stays, marked discarded, so the question is still asked and its
readings are never completed into the new chart).

Fix round 10 stopped short of calibration and verification charts for the two reasons below.
Round A (2026-11-17) answers both; see the next section. Kept for the record:
* A verification is measured into its own dated folder (`verifications/<date>/`, created and
  given its chart snapshot at START) and finished by the verification chain (the dated
  measurement, its report against the profile's prediction, the dated folder's own replace
  rules, `verification_printing_and_target.md` and §6 of the unified model). The table job
  files only into `Run.measurement_ti3`, the profiling run's own measurement, and has no
  `Verification` twin of its session folders; a table verification would write into the wrong
  file.
* A calibration chart lives in the project's one `cal/` folder, and `Calibration.reset()`
  archives files only (`calibration_run_type.md`, amendment of 2026-09-23 and §4.4): table
  session folders under `cal/` would outlive a replaced calibration chart and could be offered
  for completion against the new one, and the job has no `Calibration` twin of the run's
  members.

### ⏳ Awaiting confirmation: every run type, and the answers to review 11 (round A, 2026-11-17)

**Confirmed by:** *nobody yet.*

Built and proved on screen against the simulated table only. The owner's ruling: "it just has
to save the measurement in the correct folder for every runtype with the correct name".

**Where a table measurement is saved, by run type.** START decides the place from the chart's
folder, as the hand path decides a calibration (`ui/i1io_table_window.py::table_place`), and
gives it to the job in place of the run. Every place has the same members
(`core/file_manager.py::I1ioTablePlace`): the chart, the file a reading of the chart is
written to, the `old/` folder and the table's session folders beside the chart.

| run type | chart | the job's Save writes | then | session folders |
|---|---|---|---|---|
| profile (and its refinement, resume) | `runs/runN/<stem>.ti2` | `runs/runN/<stem>.ti3` (`Run.measurement_ti3`) | as before: `measure_finished`, the usual completion window | `runs/runN/i1io-table/<stamp>/` |
| calibration | `cal/<project>-cal.ti2` | `cal/<project>-cal.ti3` (`Calibration.measurement_ti3`, the hand path's own name) | the hand path's calibration ending: the log names the "4. Calibration & Profiling" tab, `measure_finished`, then "Calibration Measurement Complete" with Create Calibration File / Close (no Re-read and no reader keys: the table has let go); never averaged | `cal/i1io-table/<stamp>/` |
| verification (one page and several) | `runs/runN/verifications/<stem>-verify.ti2` | `runs/runN/verifications/<stem>-verify.ti3`, beside the chart, where chartread writes a hand reading (`VerificationChart.measurement_ti3`) | once the table has let go, the hand path's `_finalize_verification`: renamed `-verify` and tagged, moved into the dated folder START made (`verifications/<date>/`, with its chart snapshot), an earlier measurement of that date kept in `<date>/old/`, the how-printed question, the automatic report, and the verification's own "saved" window; a partial one ticks Refine / resume and shows no window, as by hand. Never `measure_finished`, never Build Profile | `runs/runN/verifications/i1io-table/<stamp>/` |

* The hand path's guards of each run type run before the panel: for a verification
  `_verification_guard` (no verification of a run without a profile) and the dated folder's
  chart snapshot at START; a resumed verification is staged beside the chart first and the
  staged copy goes again when the session saved nothing (`_stage_verification_for_resume`,
  `_drop_unused_verification_stage`).
* A quit during a table verification files the readings the same way, without its windows
  (nothing may wait for an answer while ChromIQ closes).
* **A replaced chart takes its table sessions with it, in every run type**, so an interrupted
  session of an old chart can never be completed against a new one: a run's chart as before;
  `Calibration.reset()` moves `cal/i1io-table/<stamp>/` into the archive of a measured
  calibration (`cal/old/<date>/i1io-table/`), and for an unmeasured one into a dated
  `cal/old/<date>/i1io-table/` of its own; a replaced verification chart moves
  `verifications/i1io-table/<stamp>/` into `verifications/old/<date>/`. A folder whose "switch
  the table off" or "in use" marker is unanswered stays, marked discarded. **For the owner:**
  the calibration amendment of 2026-09-02 says an unmeasured calibration chart leaves no
  `cal/old/` folder. A table session's raw readings are kept all the same (set aside, never
  deleted), so a calibration chart that was never saved but was read by the table does leave
  `cal/old/<date>/i1io-table/`. The chart itself is dropped as ruled. Since review 12 (S-5,
  below) only a session that holds a reading is set aside.
* A START anywhere in the project asks about a marker left anywhere in it (each run, each
  run's verifications, `cal/`).

**After a refinement read by the table**, the usual "Re-measurement Complete" window, after the
table has let go, through the hand path's code: the opening line counts the patches read again,
M-REFINE-REBUILD, and the table's own next steps M-I1IO-DRIVE-REFINE-DONE-NEXT (proposed), with
Go to the tab and Close; "Continue Measuring Manually" is left out (no reader waits for keys).
A list of strips to refine that names no strip of the chart is refused at START with
M-I1IO-DRIVE-REFINE-NOT-ON-CHART (proposed) in the log; nothing is opened.

**Review 11's other answers:** a quit while a step runs (also while the USB is being opened)
never closes the panel under its worker: the step ends at its next pause and its result
decides; a quit while the arm is brought home after Save asks nothing more and closes once the
job has let go. No page shows a step's reason id: every id the job can return has a sentence,
and an unknown one gets "ChromIQ could not do this step. The diagnostics file of this
measurement has the details." The report after a row that could not be read says so. Stop,
Report a problem and the switch-off line appear when the USB is opened, not on the pages
before. At a row's end the ring goes, so the row's dot shows; the next patch is ringed when the
arm goes there. The legend chip of the preview never covers what an i1iO chart prints around
its patches (row letters, column numbers, marks, the wordmark and name line, the text column):
it takes a free band of the paper, smaller when it must, or is not drawn; every other chart's
chip is placed as before. App-level in-use markers are removed one month after they were
answered. The question's text gets the room the rest of the panel leaves, never less than three
lines and never under the answers; in a panel too low for six lines the true-state box moves
into the scrolling area under the text; the visible part of a long text ends on a whole line,
and the scroll bar says there is more. The words for a refusal never show a reason id. A chart made for the CR30 loaded after a table chart keeps the CR30's greyed options.


### ⏳ Awaiting confirmation: the instrument's button as "Aimed" (round B, 2026-11-17)

**Confirmed by:** *nobody yet.*

Built and proved against the simulated table and the helper's own replay instrument only. **Not
tried with a real i1Pro 2 in a real table**: whether the i1Pro 2's switch thread reports the press
there as it does by hand is only known after the first real session (its log then has a "button
press received" line for every mark answered that way). If no press ever arrives, nothing is
lost: the panel's Aimed always works.

* While the panel waits at an aiming question (the arm free, nothing moving), ONE press of the
  i1Pro 2's own button is the same answer as the panel's Aimed, for that mark only. The session
  log writes the answer's usual line followed by "(by the instrument's button)", plus a
  "button press received" line.
* A press never moves anything and never counts as the hands-off GO: after the third mark, the
  GO before the check move is asked in the panel as before (the hand is on the arm). The button
  is listened to only during the aims; a press at any other moment is ignored and logged.
* A press sooner than 0.4 s after the question appeared is not taken (it was meant for the
  question before). A press arriving after the panel's Aimed was used is ignored (each question
  has its own token, used once). Stop, Report a problem and End measurement cancel the wait.
* The helper's new mode `--i1io-press-wait` (build 2026-11-17b) opens the i1Pro 2 as every
  reading does, takes no reading, sets no mode, never opens the table, and only reports presses
  while the job has armed it. It is started only after the reader consent, after the same
  instrument check as every reader (exactly one i1Pro 2, nothing else), and it has let go of the
  i1Pro 2 before any reader opens it. With an older helper (no `+i1io-press-wait` in its build
  string) the button is not offered and nothing else changes. No setting.
* Text: M-I1IO-DRIVE-AIM-BUTTON (§M-PROPOSED), added under M-I1IO-DRIVE-AIM when the button is
  offered, and one status line under the question (ready / cannot be used this time).

### ⏳ Awaiting confirmation: reading rows as strips, a first try (round B, build step 10, 2026-11-17)

**Confirmed by:** *nobody yet.*

Built and proved against the simulated table and tester 0.6.0's simulated table-scan reader
only. **Not tried on a real table**: whether the table starts the scan move on ChromIQ's lamp
(D-1), the live timing of the trigger (D-2), the motion start the cut relies on (D-3), a lamp
pass longer than the recorded ones (D-7) and how strip values compare with spot values and
i1Profiler's (D-8) all wait for the volunteer's results.

* **The option.** The existing "Patch-by-patch mode (-p)" of Guided and Manual decides it for
  an i1iO table chart (STEP4_PROPOSAL section 2): ticked = patch by patch (the default: the box
  is ticked when a table chart is loaded, the person's own value for other charts is kept and
  comes back with them); not ticked = every row as a strip. The box is never greyed; a line
  under it and its tooltip (M-I1IO-DRIVE-STRIP-OPTION) say that strips are a first try, and the
  panel's first page says it again (M-I1IO-DRIVE-STRIP-FIRST-TRY). No new setting.
* **One strip row** is tester 0.6.0's E2 row, byte for byte on the wire (339 sittings compared):
  where the arm is, the first-visit rule for the way to the row start and the run, for a row in
  the front zone first a spot move to each of its two ends, the instrument's lights off, c4,
  the move to the row start at 300, d1, the arrival, the instrument armed (if it is not ready
  to fire at once, the scan move is NEVER sent), the scan move at a recorded speed, a3, c3, the
  lamp trigger on the one path with no stop point, the move's done answer, the arm at the row's
  end. The hands-off GO is asked as for every row.
* **The speed** is the slowest of 54, 61, 87, 88, 110, 118, 137, 138, 168 mm/s (all recorded;
  168 since i1Profiler's two rows on the volunteer's table, 17 Nov 2026) that
  keeps the row within 1,190 readings (the longest recorded pass, D-7) with at least five
  readings in every patch's clean middle. A row no recorded speed keeps inside, or whose run
  with its run-in and run-out leaves the measuring area, is read patch by patch by itself
  (M-I1IO-DRIVE-STRIP-TOO-LONG). So is a row of which only some patches are to be read (resume,
  refinement).
* **The patches** are found in the readings by position, with the tester's own rule (no
  refinement). Nothing is guessed: a row whose readings are missing, fewer than planned, whose
  patch windows hold fewer than five readings, are not on one colour (any band more than 10 %
  from the window's mean) or give values no print can have, is not kept at all, and the person
  chooses: read it again as a strip, read it patch by patch, skip it, or end the step
  (M-I1IO-DRIVE-ROW-FAILED-STRIP). Each of "again" and "patch by patch" asks the hands-off GO
  first and counts as a row read again (two per page at most). ArgyllCMS's own recogniser runs
  beside as a cross-check and is only recorded.
* **The values**: the instrument's own calibrated spectra (the helper's table-scan mode), the
  XYZ computed from them as ArgyllCMS's chartread does (D50, 2 degree observer); the row file
  has the fields a spot row's file has for the same options (-l, -L, -n honoured), so strip
  rows and rows read patch by patch mix in one measurement. -H has no meaning for strip rows
  (the session reads in standard resolution), -A (XRGA) is refused for strip rows.
* **The white**: in strip mode the calibration makes the strip white too, right after the spot
  white and on the same tile (tester C1). A strip session without it does not read a strip row.
* **A scan move that may still wait** (the lamp never came, the trigger could not be handed to
  the instrument, the instrument stopped at the fire): nothing more is sent in the session,
  the way back starts with switching the table off (M-I1IO-DRIVE-SWITCH-OFF), and the marker
  files ask again at the next START.
* **Stop** is honoured before the strip starts, or after the strip move has ended; it never
  cuts the one path to the lamp trigger.
* **App Nap**: on a Mac the job holds macOS's "latency critical" activity around every strip
  move, so a ChromIQ that is not in front is not slowed down while a row runs.
* **Unchanged**: the allow-list, every recorded line, the helper's own limit (2,000 readings),
  the session and step caps (they always counted a strip row as the tester's E2 row step plus
  its front-row ends, 19 lines and 4 movements).

### ⏳ Awaiting confirmation: review 12, where table readings are filed (2026-11-17)

**Confirmed by:** *nobody yet.*

Built and tested against the simulated table only; proved on screen with the simulated table.

* **A saved table verification is always filed.** Whatever closes the panel after a Save (Close
  on the last page, Esc, the panel's close, a quit), the readings are renamed `-verify` and
  moved into their dated folder by the hand path's `_finalize_verification`. Esc on the last page
  ends the panel as its Close does. A verification file left beside the chart and never filed
  (ChromIQ killed between the Save and the filing) is moved to `verifications/old/<date>/` at
  the next table START, exactly as the hand path's START does, so the next reading is never
  refused at Save.
* **A table session belongs to the chart it was read from, and a verification's to its date.**
  When a session starts, its folder records the checksum (sha256) of the chart's `.ti2` and,
  for a verification, the dated verification the target bar selects (`verification:<date>`, or
  `verification:new` for "New verification"). An interrupted session is offered for completion
  ("Complete it") only when both match: a chart replaced, made again, imported or restored by
  Restore Used Chart, or another date of the same chart, never gets those readings. Such a
  session is named on the panel with why (M-I1IO-DRIVE-EARLIER-ELSEWHERE, proposed), kept where
  it is, and never completed; the job refuses an adoption of it whatever asks. A session with
  no record (none exist outside the developers' machines: the table drive is unreleased) cannot
  be proved to be of this chart and is treated the same way.
* **A replaced verification chart takes its sessions with it also when its files were archived
  first** (the Replace of the chart import and of Create Chart): the sessions go into the same
  `verifications/old/<date>/` as the chart.
* **A resumed table verification keeps the date's earlier file in `verifications/<date>/old/`**
  (§2a), as the hand path does, not in the chart's `old/`.
* **S-5, for the owner (the coordinator's decision):** on a calibration reset only the table
  sessions that hold a reading are set aside into `cal/old/<date>/i1io-table/`. A session that
  read nothing stays where it is, marked discarded and never offered, so an unmeasured
  calibration chart whose table STARTs read nothing leaves no `cal/old/` folder, as the ruling
  of 2026-09-02 says.
* No page shows a reason id: every option reason of the table job has a sentence, and an
  unknown one reads "the table measurement cannot use it".
* The ending's question ("Keep what you have measured so far?") keeps its three answers in
  view at every size the main window allows; in the lowest panel its text scrolls above them.

### ⏳ Awaiting confirmation: what the real table showed on 17 Nov 2026, and what changed (owner-results round)

**Confirmed by:** *nobody yet.*

The volunteer (crismi2) ran ChromIQ's tester program 0.6.0 twice on his i1iO 2 with an i1Pro 2 on
a Mac and recorded i1Profiler three times (two rows read as strips, the same chart read patch by
patch, and a single scan with three alignments). Built and tested against the simulated table,
which now behaves as the real one did; the in-app drive itself has still not run on a real table.

* **Where the short move m1 ends.** m1 brings the measuring opening to X 2507, Y 1429 (read twice
  after m1 from the far side, 0.400 s; i1Profiler's own m1 from elsewhere takes the time of a
  plain move to that place: 1.759 s from (999, 1503), 2.751 s for 3,717 units). ChromIQ had
  expected (2832, 1371) or a "sight frame" box near (2716, 1057), so every START would have
  stopped at the alignment start. The check now accepts that one place within the usual 5 units
  and stops the session on any other. The areas taken from m1's target field are gone from where
  the motors are known to have driven the arm.
* **The geometry model.** p0 reads where the measuring opening is. p1, read at each aim while the
  sight's cross hairs sit on a mark, is the coordinate the opening must be sent to so that it sits
  on that mark: a target, with no offset to add. Patch targets are the affine map of the sheet's
  three marks onto the three p1 readings. i1Profiler's scans run straight along the line through
  the p1 points (starting and ending 0.4 mm beyond the end patches' centres), and its spot targets
  are that grid within 1 unit. While a mark is aimed, the opening itself stands about 31 mm behind
  the sight (p0 minus p1 after the third aim); no target is ever computed from that difference.
* **D-5 (the opening lands on the mark with p1 as target, no offset): settled for i1Profiler's own
  path**, scans and spot rows: the values computed from its raw readings at those places agree
  with its saved files to 0.087 dE00 on average (scan) and 0.068 (spot), with the table's stored
  tile values. **Not yet for a row driven by ChromIQ**, which has not run on a real table. So the
  check move to mark 3 and its question "Is the opening on mark 3?" stay as the live safeguard
  before anything is read; the text now says why it is asked.
* **D-4 (where to calibrate): answered.** A white made on the table's tile in the arm and one made
  on the instrument's own tile gave patch values 0.13 dE00 apart on average (at most 0.22), and
  i1Profiler calibrates on the table's tile. The table's tile is the default and is not asked any
  more; the own tile stays a choice in Preferences > Beta and from the first page. A calibration
  on the own tile that did not finish leaves the instrument out of the arm: the next calibration
  is made on the own tile again (never "in the arm" while the instrument is outside it).
* **D-4b (which white reference), an option until the owner decides, off by default:** "Use the
  table's stored white tile values (as i1Profiler does)". Off: the i1Pro 2's own white reference,
  as in a measurement by hand. On: after each calibration the table's tile is read once at rest,
  and the measurement's spectra are scaled per band by the value stored in the table (bytes 88-231
  of the memory block the app reads when it opens the table, 36 little-endian floats; no earlier
  byte is read, logged or stored) divided by that reading; XYZ and L*a*b* are computed again from
  the scaled spectrum, and the file declares `CHROMIQ_TABLE_WHITE`. Values that are not 36 finite
  numbers between 0.30 and 1.20, factors beyond 0.85-1.15, no tile reading or no spectral values
  (-n) are refused with M-I1IO-DRIVE-STORED-WHITE-REFUSED and the session measures as with the
  option off. Readings with and without it never go into one file. The session log names which
  white was used and the factors' range, never the values. Support from i1Profiler's own raw
  readings on the real table: scan 0.087 / spot 0.068 dE00 with the stored values against
  0.636 / 0.645 without (and 0.22 on a cross-paired comparison of the first analysis). Which is
  closer to the true colour is not known.
* **Recorded values added:** c4 may answer BC (B7..BC; BA, BB, B8 seen too); scan speed 168
  (i1Profiler's; used only where no slower recorded speed keeps a row within the readings rule,
  in practice never); 45 button presses in all, each answered by p1 2-5 ms later.
* **A position reading a hair outside the tolerance** after a move is read once more after 0.3 s
  before anything is doubted (i1Profiler's own arrivals: dx -2..+3, dy -5..+1 units); the
  tolerance itself (5 units) is unchanged, and a second reading outside still stops the session.
  The step caps allow that one extra reading per move.
* **Spot rows start at column 0 on every row** (the end of marks 1 and 2), as i1Profiler's spot
  rows do; only strip rows are serpentine. The time estimate per patch is 2.5 s (i1Profiler's
  dual reading took 2.0 s a patch; ChromIQ's single reading with its 1.0 s pace about 2.4 s).
* **The start-up of a just-switched-on table** is offered whenever the table says so, only after
  the person's own yes; it has run once on a real table (3.088 s, the arm travelled and came back).
* **Texts:** the consent (version 2), the start-up, the button, the reader consent on a Mac, the
  calibration place, the check at mark 3, the Beta's (i) and the release notes say what is now
  true.

### ⏳ Awaiting confirmation: the final fix round, review 13 (2026-11-18)

**Confirmed by:** *nobody yet.*

Built and tested against the simulated table; the in-app drive has still not run on a real
table.

* **The hands-off confirmation after every question (M-1).** After ANY question the person
  answers, the job's or the panel's own, the next motor move waits for the hands-off
  confirmation. Either the GO page ("The arm is about to move"), or the question's own answer is
  that confirmation, and then its page says "take your hands away from the table and the arm"
  and names the move that follows: "The page is laid, and my hands are away from the table"
  (the homing and the drive out to the aiming place; no GO is asked before the sheet is laid
  any more), "Make this move, my hands are away" (a first visit), "Start the table, my hands are
  away" (the start-up), "As described, my hands are away" (the report after a step; the page
  names the panel's next step) and "Yes, it is centred, my hands are away" (the mark-3 check;
  the rows follow). Every other answer (the reader consent inside a row, the calibration
  questions, the aims, Go on, Carry on, the problem page, ...) makes the next movement ask GO
  first. The table module refuses a movement line while a confirmation is owed (a guard: the
  session stops, nothing moves, nothing more is sent); the table tests fail if it ever fires.
  A Stop pressed on the mark-3 check or the next-page question takes effect once.
* **Where the white is made, and its level (S-1).** The white calibration is made only with the
  arm in the recorded resting box over the tile (Y up to 48 units, where every recorded
  calibration was made); from the wider rest guard (Y 49..80) the recorded homing at rest is
  sent first, after GO. After a white on the instrument's own tile, the table's tile is read once
  at rest with it: its Y must be 82..97 (the volunteer's table read Y 89.78 there; the values
  stored in the table give about 87.6), else the white is refused in plain words, nothing is
  read with it and the calibration can be made again. The same check is made on the tile
  reading of the stored-white option. After a white on the table's tile a reading at the same
  place cannot show a white made partly off the tile; there the resting box is the protection.
* **No reader while the button wait holds the i1Pro 2 (S-2):** a reader starts only after the
  wait has let go (at most 12 s); else the step is refused truthfully and nothing moves.
* **No text below the scroll edge while its answers are in view (S-3):** a question longer than
  the room above the answers scrolls with its answers after it; the failed strip's page names
  the hands-off rule first. The ending's answers stay pinned (nothing moves on them).
* **A held "-p" value never reaches another target (S-5):** a target's stored value loaded while
  a table or CR30 chart's value is held becomes what comes back with that target's own chart.
* **Windows: decided by what loads (S-6):** the bundled libusb-1.0 and, on Windows, libusb0.dll
  are loaded to decide; only a library that truly does not load gets a message (on an ARM64 PC
  the one that says the drive cannot run there yet).
* **Preferences and the completion window (S-8):** the calibration place has its (i); after a
  table measurement the completion window says "saved" once and Close only stays on the tab.
