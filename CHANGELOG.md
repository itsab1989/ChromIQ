# Changelog

## v4.2.0

**ChromIQ can now measure a chart with a CR30, the first instrument it drives
itself instead of handing to ArgyllCMS. The scanner and camera window asks what
the profile is for and sets itself up for that job. There is a third appearance,
Neutral, for anyone who would rather the app did not use colour to say things.
And a long list of faults that had been shipping for months is gone: a
measurement lost when you quit, an under-exposed scan that built a bad profile
and then rated it best of the run, a Windows driver installer that had never
installed a driver, and a "Save As" in the patch editor that handed back a
different chart.**

Eleven betas, folded into one list. Everything below is measured against 4.1.4.

### New

- **ChromIQ measures a chart with a CR30.** It is a low-cost spectrophotometer
  with no ArgyllCMS support of any kind, so finding it, identifying it,
  calibrating it and reading a patch are all ChromIQ's own work, over USB and
  over Bluetooth. It calibrates the instrument for you, showing both steps as a
  picture with the current one marked, and offers the dark reference as a tick
  box because a CR30 has no black tile. It also says plainly what it cannot do:
  a white calibration cannot be checked by software, because the instrument
  reports the same value whatever is under the cap. Read single patches works
  with a CR30 too. The instrument was reverse engineered on real hardware, and
  the protocol notes, the captures and the experiments that turned out wrong are
  public at https://github.com/itsab1989/chromiq-cr30-research. Used so far on
  macOS over USB and over Bluetooth and on Windows on ARM over USB, each with a
  real instrument and a real chart, and over Bluetooth on Windows 11, where a
  user reported connecting, calibrating and measuring without trouble. Linux
  should work and nobody has tried it.
- **A magnet at the measuring opening can no longer spoil a reading in
  silence.** A magnet makes a CR30 take a white calibration instead of a
  measurement and hand back its stored white-tile value, which looks like an
  ordinary patch colour, and a laptop lid, a fridge door or the instrument's own
  cap will do it straight through a sheet of paper. ChromIQ learns your own
  instrument's tile value (one press with the cap on over USB, two over
  Bluetooth), files it against that instrument so a second CR30 never inherits
  the first one's, then refuses such a reading, stops the measurement and offers
  to recalibrate on the spot. Everything measured before that moment is already
  saved. Over Bluetooth there is no equivalent signal, so use the cable if you
  have it.
- **Space, or Enter, takes the reading**, once your instrument's tile is
  learned. That is not only convenience: pressing the instrument's own button
  moves it by about ten times its own measurement noise, 0.5 %R against
  0.05 %R, both measured, so keeping it still is measurably more accurate.
- **See where the instrument will sit.** A CR30's 33 mm body hides the patch the
  moment you lower it, so the measurement preview now draws that body to scale,
  dashed, on the patch you are being asked for: line it up on screen, note which
  neighbours it covers, and put the instrument down so those same neighbours are
  evenly covered. A second, much smaller circle appears only when there is a
  problem, the 4 mm measuring opening, shown when the patch is too small for it.
  Both figures come from the manufacturer's own specification.
- **A Bluetooth report, for when the instrument will not connect.** Tools ▸
  Instruments. It separates the three cases (your computer's Bluetooth sees
  nothing, something is offering the service a CR30 uses, ChromIQ's own search
  accepts it) and writes a file you can send. It never asks the instrument to
  measure or to calibrate.

- **Twenty ready-made CR30 charts, from Knut.** Ten on A4 and ten on US Letter,
  from 77 patches on one sheet to 1,260 across three, eight of them hexagonal so
  that more round patches fit the page. They sit in their own CR30 group in the
  Presets dropdown and in the built-in presets bubble. Picking one builds the
  chart straight away: the colours are fixed, and every layout setting can still
  be changed.

- **Neutral, a third appearance.** A designed greyscale scheme rather than Light
  with the colour turned down: one accent value, five-cell rules where the tab
  hues used to be, and every icon redrawn to read without colour. Choose it in
  Preferences beside Light and Dark, which are unchanged, checked view by view.
- **The scanner and camera window asks what the profile is for.** Three choices:
  an everyday scanner or camera profile, a profile so the scanner can stand in
  for a measuring instrument, and a printer profile measured with that scanner.
  Picking one sets the profile type, the quality and the white point handling to
  suit it, so the three settings that decide whether the profile is any good are
  not something to remember. They also follow the size of your target: under 100
  patches ChromIQ starts from shaper plus matrix at Medium quality with "Map
  chart white to white", at 100 and above from the XYZ table at High with "Scale
  white to a perfect white surface". Nothing is locked, settings you saved
  yourself are never moved, and the window says which setting differs rather
  than changing it back.
- **Auto align, in the scanner and camera window.** Press it and ChromIQ tries
  to place the grid on the chart's patches for you, turning it the right way up
  if the scan was made sideways. It is an addition, not a replacement: nothing
  runs until you press it, one press puts your corners back exactly, and when it
  is not confident it says so and moves nothing rather than guessing. It works
  on all 25 bundled targets. On photographs it is much weaker, and dragging the
  corners roughly around the chart first is what makes it work on a cluttered
  desk.
- **The scanner and camera window is two panels.** The preview and its controls
  moved to the right, so the twelve wheel-turns of scrolling it used to take to
  reach the last control are now none, and it fits a 1280 screen in the twelve
  languages it was measured in. The preview takes the space the window gives it
  instead of staying pinned at its minimum, and the six buttons under it are
  grouped by what each one acts on.
- **Windows: one place to get an instrument driver.** For ArgyllCMS's supported
  devices and for the CR30's USB bridge. ChromIQ checks what is bound, offers
  the right package, asks for consent before anything elevated happens, says
  what it changes on your machine before you click, and says what it did
  afterwards.
- **"Show row numbers", on any chart.** ChromIQ has always printed a number
  beside each row on a SpectroScan chart, which together with the letters along
  the top lets you find one patch among several hundred the way you find a
  square on a map. There is now a checkbox for it in the layout panel, next to
  "Show strip indicators", for every instrument. Every chart you have already
  made looks exactly as it did: the setting starts out as "whatever this
  instrument normally does". Switching it on reserves 7.5 mm down the left edge,
  which the patch estimate and the built chart both take into account.
- **Check & Refine is a proper import door.** Browse for a measurement that is
  not in one of your projects and ChromIQ asks where it belongs, in the same
  window Build Profile uses; it used to make a project without asking. A third
  answer, "Just check it where it is", copies nothing, makes no project and
  writes the report next to the file, and the window says what that costs you.
- **A profile keeps its accented name.** A profile called Müller-Prüfdruck used
  to arrive as M?ller-Pr?fdruck in Windows' colour management, because the ICC
  field ArgyllCMS fills cannot hold an accent. ChromIQ writes the name into the
  field that can, and reads it back in its own Profile Info window.
- **The ColorMunki's dial is drawn.** Both calibration windows show the wheel
  turned to the mark that window is asking for, so the two cannot be confused.

- **The scanner and camera help is written as steps, with the reasoning kept
  aside.** Both printable cards are built around the three scenarios: the steps
  are what to click, and the longer explanations sit under them as notes you can
  open if you want them. On paper every note is printed, because a sheet has
  nothing to click.

### Changed

- **The scanner's Profile type control no longer says something nothing
  measured.** Four hundred profile builds on two targets, scored only on patches
  the fit never saw, settled where each type wins: shaper plus matrix below
  about a hundred patches, a lookup table above it. The help says so and points
  at where you can read your own patch count. The Lab table clips anything
  lighter than the chart's own white, so the XYZ one is marked as the
  recommended lookup table.
- **The white point options say which profile types they suit** rather than one
  of them being called the default, because that default costs real accuracy on
  the two matrix types. "Restrict white, black and primaries" now shows as
  ticked when your white point choice includes it; the flag was always being
  sent and the box did not say so. What is stored stays your own value.
- **Every warning, information and question sign in the app is ChromIQ's own.**
  The platform's signs were still showing in 70 places across 13 files. All
  three are drawn for Light, Dark and Neutral, and Neutral stays hueless.
- **Explanation has left the Create Chart sections for the ⓘ it belongs to.**
  Four blocks of standing text now ride on the information icon of the control
  they describe, with the first line also in the hover tooltip. 246 px of
  vertical space returned in English, 262 in German, and the panel did not get
  wider in any language.
- **Patch size and Patch scale have moved into Basic**, next to "Prioritise
  patch size", where the help has always said they were.
- **The chart legend fades out when you point at it**, so you can see the
  patches underneath. On a chart whose patches run to the paper's edge it has to
  rest on the last row, and it now simply gets out of the way.
- **An unmeasured calibration chart is treated as an experiment.** Replace one
  and it is not kept, the way a profile run's chart is not kept; a calibration
  that has been measured is always archived to the project's "cal/old" folder.
  The window says which of the two is about to happen. Before this it promised
  to keep a chart and then deleted five files.
- **The scanner window checks that what it read is the chart you meant.** It
  compares the reference against the chart, the read against the reference, and
  looks for clipping, before it builds anything.
- **A preset no longer names your project after itself.** Loading a built-in
  preset with the name box empty used to name the project after the preset, so a
  folder, the name printed on the chart and the finished ICC could all end up
  called something like "i1Pro-A4-162p-1page-Portrait-w7.5mm". ChromIQ asks you
  for a name, in a window that takes the answer and builds the chart.
- **The bundled CMYK profile is no longer Adobe's.** ChromIQ was redistributing
  `USWebCoatedSWOP.icc`, which Adobe's licence does not permit. It is replaced
  by ArgyllCMS's public-domain equivalent.
- **Your log reaches about three times further back.** A debug line recorded
  every help icon the app built, around three fifths of everything ChromIQ
  wrote, and pushed the entries that diagnose real faults out of the file.
- **Return no longer presses the button that discards a chart**, and the Tools
  menu is capped and scrolls instead of growing past the bottom of smaller
  screens.

- **The profile Algorithm list is two entries, and both of them work.** It had
  eight. Five of them could never build a printer profile: ArgyllCMS builds a
  printer profile as a lookup table or not at all, and colprof refuses a gamma,
  shaper or matrix model for one before it has read a single measurement. A
  sixth, "XYZ cLUT + matrix", built a file identical to plain "XYZ cLUT",
  because the matrix it promised is thrown away for a printer. What is left is
  "Lab cLUT" and "XYZ cLUT". The gamma, shaper and matrix models are not gone
  from ChromIQ: they suit a scanner or a camera, and the scanner and camera
  window still offers them there, where they work.
- **Three of those entries also named the wrong algorithm.** colprof's own
  names are `s = shaper+matrix`, `G = single gamma+matrix` and
  `S = single shaper+matrix`; ChromIQ called them "Single gamma + matrix",
  "Gamma + matrix (forced)" and "Single gamma + matrix (forced)". "Single" in
  ArgyllCMS means one tone curve shared by all three colour channels, not
  "forced", and the entry ChromIQ labelled as a gamma model was the shaper one,
  which ArgyllCMS calls the better of the two. The scanner window's names were
  right all along.
- **If a project of yours was saved with one of the entries that has gone, it
  still opens, and ChromIQ tells you what it did.** "XYZ cLUT + matrix" becomes
  "XYZ cLUT", and the profile that builds is unchanged, because for a printer
  the two were the same file. Anything else becomes "Lab cLUT", with a line
  saying the stored setting could not build a printer profile at all. Nothing
  is changed behind your back and nothing is thrown away.
- **The scanner and camera window no longer offers "Shaper + matrix" or
  "Matrix only" while "Profile my printer from this scan" is ticked.** That
  tick makes it a printer profile, so the same ArgyllCMS rule applies. With the
  tick off, all four types are there as before.
- **Quality is no longer greyed out for the shaper and matrix profile types.**
  It was greyed out and then sent to ArgyllCMS anyway, so it was doing
  something you were told it did not do and could not change. It does apply:
  for a lookup table it sets the table's resolution, and for the shaper and
  matrix types it sets how finely the tone curves are fitted. Measured, it
  changes the profile for every type.
- **The twelve translations were read end to end, and the English was corrected
  where they found it wanting.** Translating a string means reading it, which
  is a review nobody else performs, and it turned up things no test could see.
  The CR30 patch instruction said *"Take the magnetic cap off the measuring end
  first, with the cap on, the CR30 reads its own white tile"* — read past the
  second comma and "with the cap on" attaches to taking the cap off. Five more
  sentences ran two clauses together on a comma. A help card told you to tick
  "Also save scanner-profiling files" when the box says *for this chart* too,
  and another quoted "Sides" and "Top/bottom" for boxes that read *Sides
  (vertical)* and *Top/bottom (horizontal)*. One window was titled "Check the
  dark calibration" over a body about the dark reference, while the rest of the
  app calls that act a black calibration. The connection-lost line said
  `[WARN]` where the line under it says `[ERROR]`, and the app was evenly split
  between the two spellings. And "Unexpected Color
  Response" is now "Unexpected Colour Response", which is how the app spells
  colour everywhere else, including in the help card that quotes this window.
- **A help card no longer names a control in English in a window that renames
  it.** The folder guide tells you what printcal's "Re-calibrate" and "Verify"
  modes compare against, and ten of the twelve languages had left those two
  words in English, so a German reader was told to look for a control that
  reads *Nachkalibrieren* on screen. Four smaller cases went with it, and the
  log tag is now English in every language rather than translated in some
  strings and not others in the same log.

### Fixed

- **A measurement is no longer lost when you quit.** Closing ChromIQ during a
  measurement killed the reader, and the reader only writes its file on a clean
  exit, so the reading was gone with no warning. Quitting now asks, the way
  every other way out of a session already did.
- **"Save and stop" saves.** It was sending the reader a key it rejects, so the
  session never ended and nothing was written. "Keep measuring" now keeps
  measuring instead of stranding the session.
- **A single corrupt byte in a measurement no longer destroys it.** One zeroed
  byte in a `.ti3` made ChromIQ read the whole file as a different encoding and
  replace it with nonsense.
- **The optional calibration window no longer closes ChromIQ**, and its "Skip
  this step" button now does something. Both faults appear only with an
  instrument that offers optional calibration, such as a SwatchMate Cube, and
  both took the measurement in progress with them.
- **Importing a measurement can no longer end the app.** Four separate causes: a
  folder ChromIQ cannot write to, a disk that is full, a drive or share that has
  gone away, and a project whose own `project.json` has been damaged. Each now
  says what went wrong and leaves everything as it was.
- **A measurement can no longer be filed into the wrong project.** Picking a
  folder whose name contains something like a space (a Finder duplicate, an
  unzipped hand-off, a Dropbox conflicted copy) used to make an empty project of
  a slightly different name and then complain that it had no chart in it. A
  project behind a symlink, on an external drive or on a NAS could take the
  measurement into whatever project happened to be open instead.
- **A measurement refused as not belonging to the chart no longer leaves a run
  behind**, under a window saying nothing had been changed. The same check now
  covers the other road into a run: choosing an existing run that happens to
  hold no chart used to accept anything at all, in silence.
- **A print that never happened is no longer recorded as one.** A sleeping
  printer or a cancelled dialog left a record saying the sheet had been printed
  through the profile, which then silently changed the yardstick every dE in the
  report was measured against. That record also travels with the chart when a
  run is duplicated; it used to be dropped, so the guard that asks whether the
  sheet was converted when it was printed stopped firing on the copy.
- **A measurement report that could not be saved said nothing at all**, while a
  report that saved announced itself, so the failure looked exactly like
  success. It now says so, and says first that the measurement itself is safe.
- **Saved measurement reports were re-graded by whatever the thresholds say
  today.** A report is a record of a judgement made on a day; it now keeps the
  thresholds it was judged with and the verdict it was given.
- **A refine-strips list is no longer overwritten in place.** It was written
  under one fixed name, so re-checking a run destroyed the list from the check
  before it. They are numbered now, like the quality reports beside them, and a
  file written by an older version is left exactly where it is.
- **A new run opens on your defaults, not on the last run's settings.** The
  instrument, the paper, the layout mode, both indicator checkboxes, the stamp
  option, the Guided settings and the gamut options were all inherited from
  whichever run you had been looking at, and then stored on the new run as
  though you had chosen them.
- **An under-exposed scan built a profile with no warning, and the app rated it
  best of the run.** Measured at 21.7 dE out. The scan is now judged before it
  is trusted, and one too dark to profile from says so instead of producing a
  plausible, wrong profile.
- **A sheet photographed ten degrees off square was accepted as correctly
  placed.** Keystone is measured against a limit now rather than assumed away:
  328 correct placements separate cleanly from 106 wrong ones.
- **The alignment diagnostic drew no outline**, so a correct read looked
  misaligned; zooming it interpolated away the very edges being judged; and a
  refusal could not be diagnosed from the log. All three now say what happened.
- **A scan that is not the target you chose, an unreadable reference, and a
  scanin diagnostic image loaded as a scan** each said nothing, or blamed the
  wrong thing. Each now names what it found. The profile self-check also had no
  floor and no guard against a meaningless number.
- **The scanner white-point default clipped every original brighter than the
  chart's own board.** New scanner profiles start from a better default, and the
  help no longer says "1.00 makes no change", which is the opposite of what it
  does. Nothing in ChromIQ used to say that a scanner profile meant to stand in
  for a measuring instrument must be built for that purpose; it does now.
- **"Save As…" in the patch editor turned a chart ChromIQ had laid out into a
  different chart.** A change made in June switched the editor's ChromIQ layout
  engine off without anyone noticing, so the saved chart came back with extra
  fill patches, a different strip grid, and without the sidecar that records its
  layout, which the measuring path reads. Measured on a 525-patch i1Pro chart:
  525 patches became 528 and a 21 by 25 strip grid became 24 by 22. It now saves
  back identical, patch for patch and strip for strip. "Apply / Save ▸
  Overwrite" was never affected. If you kept a chart saved this way, save it
  again from the editor to get the layout back.
- **An i1Pro chart lost its automatic bidirectional reading whenever the project
  was reopened.** The instrument a chart names is written into the chart file by
  the layout stage, and after a reopen ChromIQ looked for it in the wrong file
  and found nothing, so the i1Pro family lost the setting that lets a strip be
  swiped either way, the preview's bidirectional arrow was wrong, and the pace
  row fell back to the i1Pro minimum sample count.
- **"Prioritise chart area" now honours your left margin.** The 7.5 mm band that
  carries the row numbers was reserved outside it in every mode, so a 1 mm
  margin put the first patch at 8.5 mm. It sits inside the margin now, in the
  one mode whose whole contract is that the patch area is exactly the margin
  box, and the panel warns when the margin is too tight for the numbers. The
  margin readout also says what it measures, "Left (to first patch)", and
  explains the two things that legitimately sit in that space.
- **A hexagonal patch was reported smaller than it prints.** The layout panel
  gave the row pitch as the patch height, so an 11.3 mm hexagon was listed as
  11.3 by 9.8 when it actually stands 13.1 mm from point to point. Hexagons
  interlock, so the pitch is real and useful, but it is not the patch: the panel
  now gives the patch size, and a separate "Row pitch (mm)" line for honeycombs.
  Nothing about the charts themselves changed, only what was reported.
- **On a hexagonal chart, two layout controls did nothing and did not say so.**
  With the strips pinned, neither "Patches per strip" nor "Minimum patch height
  (% of width)" could change the chart, because a honeycomb interlocks: its
  height follows from its width, and the strip count already decides the size.
  Both are locked where they cannot work, with the reason on the row's
  information button, and both stay live where they genuinely do something.
- **The seed box read 0 while the chart on screen had been built with something
  else.** With "randomise patch order" on and no fixed seed asked for, the
  engine drew its own seed and nothing carried it back to the box, and 0 is a
  valid seed rather than a placeholder, so the box was reporting a wrong answer
  as fact. The seed itself was never lost: it is written into the chart file,
  the chart's sidecar and the build log, and all three always agreed.
- **Row numbers fit the row they name.** On a tall chart the automatic size was
  taken from the patch width, so the numbers printed over each other into an
  unreadable ladder. They also stay inside the "Text distance to edge" limit
  instead of walking to the paper's edge on charts with more than ninety-nine
  rows.
- **A flagged patch keeps its whole red ring** on a hexagonal chart, where the
  neighbouring patch used to be painted over part of it; **loading a new chart
  no longer shows the previous chart's measurements**; and **the legend no
  longer lands at the top of the sheet**, over the column letters, on charts
  whose strip geometry is not recorded.
- **Windows: a project name that was accepted and then could not be written.**
  Names of about 111 to 120 characters passed the name box and then failed when
  ChromIQ wrote the chart, because Windows limits the whole path rather than
  each folder name. The limit is worked out from the longest file ChromIQ
  actually creates, and a project you already have opens whatever it is called.
  A name too long for the filesystem is now refused with an explanation instead
  of failing halfway and leaving a half-made project behind.
- **Two projects whose names differ only in capitals no longer overwrite each
  other's chart.** ChromIQ kept the name you typed while the folder kept its
  own, so one run could hold two charts, each invisible to the other.
- **A bracket in a project's folder name no longer hides its chart**, and an
  asterisk no longer lets one project claim another's files.
- **A project with an umlaut can be opened after a trip through a backup drive
  or a Windows machine.** Older Mac disks, and Windows, store accented names
  differently from a modern Mac, and ChromIQ used to find none of the project's
  files afterwards while telling you the chart was missing. On Windows it could
  be worse than invisible: a different chart was used in its place.
- **Everything ChromIQ writes now names its encoding**, so a file written on
  Windows and read on a Mac, or the reverse, arrives as what was written. This
  is GitHub issue #178.
- **On Windows, every measurement lost its own bookkeeping.** ChromIQ's
  measuring engine reports what it is doing as it goes, and a Windows chart path
  like `C:\Users\…` was written into that channel without escaping, so the
  message carrying the strip map and the patch count was thrown away silently,
  on every measurement. macOS and Linux were unaffected, because their paths
  have no backslashes.
- **Windows: the "Install USB Driver…" button had never installed a driver.**
  Not for any of the 28 supported instruments, not on any architecture, not
  once. It passed an option the tool it runs does not have, so that tool printed
  its usage text and exited cleanly, and ChromIQ read that as success and
  reported an installed driver every time, having installed nothing. It named no
  destination either, so anything it did extract went wherever the elevated
  process happened to start; and an instrument that still had a driver recorded
  against it from a different USB port made ChromIQ believe the device was ready
  and never offer to install anything at all. Found by testing that path against
  real hardware for the first time.
- **Windows: ArgyllCMS cannot use WinUSB, and ChromIQ told users to choose it in
  seven places.** An instrument bound to WinUSB is invisible to ArgyllCMS. The
  driver helper installs libusb-win32 now, and the Zadig instructions no longer
  point at the one driver that cannot work. If you followed the old advice, the
  helper puts it right: rebinding was tested on an X-Rite i1Studio, from
  `** No ports found **` back to a working instrument. ChromIQ also refuses
  outright to install WinUSB on a USB-serial instrument, whatever asks it to.
- **A project whose name ends in an underscore and digits silently lost its
  exports**, and **the ICC filename and the description embedded inside it
  disagreed** when no description was given.
- **A window can no longer open taller than your screen and take its buttons
  with it.** Long messages are widened rather than stretched, anything left over
  goes behind "Show Details", and no message window, tool window or patch editor
  can open past the edge of the usable screen. The patch editor opened 1280 by
  820 whatever screen it was on, which put Apply / Save… and Close under the
  bottom edge of a smaller laptop, and three controls in the scanner window
  opened past the bottom of the screen for the same underlying reason: a window
  was placed before it was sized, and nothing put it back.
- **The app no longer crashes when a tool window is opened** after a spot read
  ends badly, and a scroll bar that was crashing the app outright in some
  windows is fixed.
- **"Build anyway" was drawn as "uild anywa"** in three windows that built their
  own buttons and never called the helper that has fitted them since #130, and
  **four instruction labels were painted in the one colour that cannot carry a
  word**: 1.25:1 in Light and 1.02:1 in Dark, against the 4.5:1 that AA asks
  for. Now 13.6:1, 5.1:1 and 12.1:1.
- **Fourteen German sentences named buttons that do not exist**, including all
  three buttons of the window that decides whether your measurement is kept, and
  **four languages could not say where a measurement was running**: Italian,
  Portuguese, Polish and Russian glued a preposition to a translated label and
  produced ungrammatical text. Each language now supplies the whole sentence.
- **A chart whose paper size is larger than printtarg can lay out no longer
  answers with a wall of usage text.** The two custom paper boxes also offered
  sizes up to 9999 mm, and printtarg stops at 4000; both agree with the tool
  now, and the values ChromIQ sends are checked against what printtarg accepts
  before it is started at all. When a tool does refuse a chart, the patch editor
  says what happened in ChromIQ's own words and quotes the one line of the
  tool's answer that means something, instead of showing you the raw output.
- **Layout settings restored from a chart folder are range-checked**, not only
  checked for the right names, so a hand-edited or damaged `meta.json` cannot
  pass a value the tool refuses.

- **A profile build that ArgyllCMS refused for this reason produced no
  message.** It wrote no profile, opened no window and left one line in the
  log. It now says what happened and what to change. This is the same silence
  the beta 11 note described for a setting that never existed, and it was still
  there for five settings that do.
- **The "estimate" column described the chart you had before, not the one on
  screen.** Generating a chart, or picking a preset, left the estimate showing
  the previous chart's patch count and strip count, so loading two presets one
  after the other looked as though the two columns had swapped. Both columns now
  follow the chart in front of you. The charts themselves never changed.

### Documentation

- **`THIRD-PARTY-NOTICES.md` states the terms for everything ChromIQ ships**,
  measured per file rather than assumed. The bundled scanner targets are marked
  AGPLv3, matching ArgyllCMS, whose patch geometry they carry. No recognition
  file changed, and ChromIQ itself remains GPLv3.
- **`docs/cr30_platform_support.md` is the CR30 page**: what each platform
  needs, what has been tried on hardware and what has not. On Windows the
  instrument is reached through a serial driver, not WinUSB; macOS needs
  nothing; on Linux the driver is in the kernel and your user needs permission
  to open the serial port.

## v4.1.5-beta.11

**Opening Tools ▸ Edit / create chart patch set on a CR30 chart stopped the
window with fifty-one lines of ArgyllCMS usage text, in a box three hundred and
fifty pixels taller than the screen, with its only button off the bottom.** It
happened on every open, from either door, and there was nothing the user could
do inside that window to get past it.

Hunting that down turned up something quieter and worse: a line changed in June
had switched the patch editor's ChromIQ layout engine off without anyone
noticing, so "Save As" on a chart ChromIQ had laid out handed back a different
chart.

The rest of this release comes from a beta 10 review: the scanner and camera
window now asks what the profile is for and sets itself up for that job, and
three layout controls that quietly ignored what you typed on a hexagonal chart
now say so.

### New

- **The scanner and camera window asks what the profile is for.** Three
  choices: an everyday scanner or camera profile, a profile so the scanner can
  stand in for a measuring instrument, and a printer profile measured with that
  scanner. Picking one sets the profile type, the quality and the white point
  handling to suit it, so the settings that decide whether the profile is any
  good are not something to remember. Nothing is locked. Change a setting
  afterwards and the window says which one differs rather than changing it back.
- **Those three settings are also chosen from the size of your target.** Under
  100 patches ChromIQ starts from Shaper + matrix at Medium quality with "Map
  chart white to white"; at 100 and above from the XYZ table at High with "Scale
  white to a perfect white surface". Settings you have saved yourself are never
  moved, and the window tells you when it is leaving them alone.

### Changed

- **The white point options say which profile types they suit** rather than one
  being called the default, because the previous default costs real accuracy on
  the two matrix types.
- **"Restrict white, black and primaries" now shows as ticked** when the white
  point choice includes it. The flag was always being sent; the box did not say
  so. What is stored stays your own value.

### Fixed

- **The patch-set editor could not be opened on a CR30 chart.** ChromIQ asked
  printtarg to draw the preview, and printtarg has no code for the CR30, so it
  refused the chart and printed its whole usage text. ChromIQ lays CR30 charts
  out itself, and the editor now does the same instead of asking a tool that
  cannot. Charts ChromIQ laid out are drawn by ChromIQ everywhere, and the
  values that go to printtarg are checked against what printtarg actually
  accepts before it is started at all.
- **"Save As…" in the patch editor turned a ChromIQ-laid-out chart into a
  different chart.** The saved chart came back with extra fill patches, a
  different strip grid, and without the sidecar that records its layout, which
  the measuring path reads. Measured on a real 441-patch chart: it now saves
  back identical, patch for patch and strip for strip. "Apply / Save →
  Overwrite" was never affected. If you kept a chart saved this way, save it
  again from the editor to get the layout back.
- **A message window could open taller than your screen and take its buttons
  with it.** Long messages are now widened rather than stretched, anything left
  over goes behind "Show Details", and no message window can open past the edge
  of the usable screen. macOS could not rescue the old one: a window that tall
  does not fit anywhere.
- **The patch editor window itself opened 1280 by 820 whatever screen it was
  on.** On a smaller laptop that put Apply / Save… and Close under the bottom
  edge. It now opens no taller than the screen can hold.
- **When a tool refused a chart, the patch editor showed you the tool's raw
  output.** It was the only window in ChromIQ that did. It now says what
  happened in ChromIQ's own words, quotes the one line of the tool's answer that
  means something, and leaves the rest in the log.
- **"Matrix only (forced)" in the profile Algorithm list could never build a
  profile.** ArgyllCMS's colprof has no *forced* matrix setting: choosing it
  produced no profile, no message and one line in the log. The entry is gone.
  (Corrected after publication, because this note first said colprof "has no
  such setting" and that reads wider than it should. colprof does have a plain
  matrix-only algorithm and ChromIQ offered that one too; what never existed
  was the "(forced)" variant. And matrix only was not the only entry in that
  list that could not build a printer profile: see the next release.)
- **A chart whose paper size is larger than printtarg can lay out gave the same
  wall of text.** The two custom paper boxes also offered sizes up to 9999 mm,
  and printtarg stops at 4000. Both now agree with the tool.
- **The Create Chart command preview showed CR30 users a command that cannot be
  run.** ChromIQ never ran it; the line on screen simply described the wrong
  thing.
- **A hexagonal patch was reported smaller than it prints.** The layout panel
  gave the row pitch as the patch height, so an 11.3 mm hexagon was listed as
  11.3 x 9.8 when it actually stands 13.1 mm from point to point. Hexagons
  interlock, so the pitch is real and useful, but it is not the patch: the panel
  now gives the patch size, and a separate "Row pitch (mm)" line for honeycombs.
  Nothing about the charts themselves changed, only what was reported.
- **On a hexagonal chart, two layout controls did nothing and did not say so.**
  With the strips pinned, "Patches per strip" could not change the chart, and
  "Minimum patch height (% of width)" could not either: a honeycomb interlocks,
  so its height follows from its width, and the strip count already decides the
  size. Both are now locked where they cannot work, with the reason on the row's
  information button, and both stay live where they genuinely do something.
- **Three errors in the scanner window's printer-mode help.** A scanner profile
  used as a measuring instrument can be built from a chart you made in ChromIQ,
  not only from a bought target; choosing the XYZ table does not switch on Force
  Absolute Colorimetric; and the closing advice pointed at a control the
  paragraph above it recommends against.
- **A help note contradicted the help card it sits in front of**, telling users
  on the current default that their bright paper was being flattened and to lift
  a ceiling that already sits above anything physical.
- **Layout settings restored from a chart folder are now range-checked**, not
  only checked for the right names, so a hand-edited or damaged `meta.json`
  cannot pass a value the tool refuses.

## v4.1.5-beta.10

**ChromIQ's USB driver installer had never installed a driver. Not for any of
the 28 supported instruments, not on any architecture, not once, and beta 9
shipped it.**

It was found by testing the ArgyllCMS driver path against real hardware for the
first time. Three faults were stacked so that each one hid the next, and a
fourth appeared once they were gone. Beta 9's notes said the driver helper was
proven end to end on real hardware: that was true of the CR30's serial bridge,
and not of the USB half, which is what this release repairs.

This beta also carries the scanner-window and white-point work that landed after
beta 9 was tagged.

### Fixed

- **Windows: the USB driver installer never installed a driver.** Four faults,
  each hiding the next. A ghost registry entry, left by the same instrument on a
  different USB port, still had a driver recorded against it, so ChromIQ
  believed the instrument was ready and never offered to install anything. The
  installer passed `--driver WinUSB`, which is not a wdi-simple option, so
  wdi-simple printed its usage text and exited 0, and ChromIQ read that zero as
  success: it reported an installed driver every time, having installed nothing.
  No destination was given, so the driver was extracted to wherever the elevated
  process happened to start.
- **Windows: ArgyllCMS cannot use WinUSB, and ChromIQ told users to choose it in
  seven places.** An instrument bound to WinUSB is invisible to ArgyllCMS. The
  helper installs libusb-win32 now, and the Zadig instructions no longer point
  users at the one driver that cannot work. If you followed the old advice, the
  helper puts it right: rebinding was tested on an X-Rite i1Studio, from
  `** No ports found **` back to a working instrument.
- **Windows: an install that had not finished was reported as one that failed.**
  If ChromIQ stopped watching before Windows was done, it said the install had
  failed or been cancelled. Nothing had been cancelled and nothing undone, and
  the install was very likely still running. An instrument that was never tried
  is no longer reported as one that failed either.
- **Windows: a chart restored from a Mac was invisible, and a different one was
  used in its place.** macOS and Windows store accented and umlauted filenames
  differently, and NTFS keeps the two spellings apart where APFS folds them
  together.
- **Three controls in the scanner window opened past the bottom of the screen**
  on shorter displays.
- **The scanner white-point default clipped every original brighter than the
  chart's own board.** New scanner profiles start from a better default.
- **The white-point help said "1.00 makes no change".** It is the opposite.
- **Nothing in ChromIQ said that a scanner profile used as an instrument must be
  built for that purpose.** It does now.
- **The seed box read 0** while the chart on screen had been built with
  something else.
- **The consent button was English in eleven languages**, and German had been
  quietly leaking untranslated sentences.

### Changed

- **The driver install now says what it changes before you click.** Installing
  the driver also puts a certificate into two of Windows' trust stores, and it
  stays there after the driver is gone. A button opens the full notice. This
  cannot be avoided: the driver is built for your instrument at the moment it is
  installed, so it has to be signed then too, and ArgyllCMS's own installer does
  the same thing. The notice says what was measured and what was not, rather
  than implying more.
- **The bundled CMYK profile is no longer Adobe's.** ChromIQ was redistributing
  `USWebCoatedSWOP.icc`, which Adobe's licence does not permit us to
  redistribute. It is replaced by ArgyllCMS's public-domain equivalent, and
  `THIRD-PARTY-NOTICES.md` now states the terms for everything ChromIQ ships.
- **The bundled scanner targets are marked AGPLv3**, matching ArgyllCMS, whose
  patch geometry they carry. Measured per file rather than assumed. No
  recognition file changed, and ChromIQ itself remains GPLv3.

## v4.1.5-beta.9

**Windows can now get the driver its instrument needs without leaving ChromIQ,
a colorimeter stopped refusing the most saturated patches on glossy paper, and
a measurement report that failed to save no longer looks exactly like one that
worked.**

Twenty-eight changes, from three directions at once: a Windows machine that
built and hardware-tested the driver helper, a beta tester's review of beta 8,
and a bug reported on a public forum that turned out to be ours.

### New

- **Windows: one place to get an instrument driver.** For ArgyllCMS's supported
  devices and for the CR30's USB bridge. ChromIQ checks what is bound, offers
  the right package, asks for consent before anything elevated happens, and
  says what it did. Proven end to end on real hardware: from a driverless
  device to a working COM port, with the instrument identifying in 92 ms.

### Fixed

- **A CR30 refused the most saturated patches on glossy and satin paper, and
  blamed the instrument.** A guard rejected any reading with three consecutive
  bands at exactly zero, on the premise that "a real dark patch reads a few
  percent, never exactly 0.0". The instrument's firmware clamps, so real ink
  does read exactly 0.0 — and glossy paper crosses that floor where matte never
  does, which is exactly the pattern the reporter described. It refused a vivid
  mid-tone green, and it stopped the session for good: five retries, and
  resuming met the same wall, so the chart could never be finished. Reproduced
  on our own instrument afterwards — three of five ordinary chart patches
  contain exact zeros, and two more sat one band from refusal.
  **Reported by nertog, whose diagnosis was right.**
- **A measurement report that could not be saved said nothing at all**, while a
  report that saved announced itself — so the failure looked identical to
  success. It now says so, and says first that the measurement itself is safe.
- **Saved measurement reports were re-graded by whatever the thresholds say
  today.** A report is a record of a judgement made on a day; it now keeps the
  thresholds it was judged with and the verdict it was given.
- **The file dialog's back, forward and up arrows were invisible in Neutral** —
  measured at 1.03:1 against the toolbar behind them, now 14.69:1. Light and
  Dark improve as well.
- **A test worker died with no traceback and no log**, which made every gate on
  Windows unreadable. A test ended with a thread still running; Qt aborts the
  process for that, and on Windows the abort defeats the crash handler.
- **Fourteen German sentences named buttons that do not exist**, including all
  three buttons of the window that decides whether your measurement is kept.
- **Four languages could not say where a measurement was running.** Italian,
  Portuguese, Polish and Russian glued a preposition to a translated label and
  produced ungrammatical text. Each language now supplies the whole sentence.
- **The button that declines an elevated driver install said "OK".** It says
  "Not now".

### Changed

- **The six buttons under the scanner preview wrap to the width available**,
  three to a line where they fit, with Auto align beside Check alignment —
  the action and the check that judges it. Asked for by Knut.
- **The scanner's Profile type control no longer says something nothing
  measured.** Four hundred profile builds on two targets, scored only on
  patches the fit never saw, settled where each type wins: shaper+matrix below
  about a hundred patches, a lookup table above it. The help text says so, and
  points at where you can read your own patch count. The Lab table clips
  anything lighter than the chart's own white, so the XYZ one is marked as the
  recommended lookup table.

### For developers

- The register in `docs/beta8_open_items.md` now refuses duplicate item ids, a
  fix called FIXED that names a test which does not exist, and a deferred item
  with nobody's name against it.

## v4.1.5-beta.8

**Auto align worked on 8 of the 25 bundled scanner targets. It now works on all
25 — and the reason it failed was in files we ship, not in the recogniser.**

Knut reported that auto align did not work on his charts. Basti then found it
did not work on the test file ChromIQ ships with the app. Chasing that one
report opened the whole scanner path, and most of this release comes out of it:
an under-exposed scan that quietly built a bad profile and then rated it best,
a hand-held scan tilted ten degrees accepted as correctly placed, and a
diagnostic image that drew no outline, so a correct read looked wrong. Several
of these had been shipping for months.

### Fixed — the scanner path

- **Auto align could never work on a bought target.** Every bundled `.cht`
  carried an absolute edge length in a column that ArgyllCMS reads as *strength
  relative to the strongest feature*, where the strongest must be 1.0 — 385.125
  in one file, 3600.0 in another. `scanin` scored every candidate rotation as
  `nan` and refused the match before looking at the picture. Normalised in
  place; the geometry Knut supplied is untouched. **8 of 25 targets aligned
  before, 25 of 25 now.**
- **An under-exposed scan built a profile with no warning, and the app rated it
  best.** The scan is now judged before it is trusted, and a scan too dark to
  profile from says so instead of producing a plausible, wrong profile.
- **A ten-degree hand-held tilt was accepted as a correct placement.** Keystone
  is now measured against a limit rather than assumed away: 328 correct
  placements separate cleanly from 106 wrong ones.
- **Auto align found the right answer and threw it away.** An accepted result
  was extrapolated to the fiducials a second time, moving it back off the
  patches.
- **Auto align and "Fit to the patches" are one button.** Measured over 290
  cells: neither was a subset of the other — 139 cases only the search
  recovered, 30 only the reshaping did, and "Fit" applied a placement that was
  still wrong in 41 of the 118 cases it acted on. Auto align now searches,
  reshapes, and only then submits the result to both picture checks and the
  reference agreement. **68 % → 84 % of placements land on the patches, and
  nothing wrong is applied.**
- **The alignment diagnostic drew no outline**, so a correct read looked
  misaligned; zooming it interpolated away the very edges being judged; and a
  refusal could not be diagnosed from the log. All three now say what happened.
- **A scan that is not the target you chose, an unreadable reference, and a
  scanin diagnostic image loaded as a scan** each said nothing, or blamed the
  wrong thing. Each now names what it found.
- **The profile self-check had no floor and no NaN guard.**

### Fixed — elsewhere

- **A project whose name ends in an underscore and digits silently lost its
  exports.**
- **The ICC filename and the description embedded inside it disagreed** when no
  description was given.
- **"Build anyway" was drawn as "uild anywa"** — three windows built their own
  buttons and never called the helper that has fitted them since #130.
- **Four instruction labels were painted in the one colour that cannot carry a
  word**: 1.25:1 in Light, 1.02:1 in Dark, against the 4.5:1 that AA asks for.
  Now 13.6:1, 5.1:1 and 12.1:1.
- **A self-capturing lambda on the pop-out window's `finished` signal** — the
  same shape that crashed the app through the scroll-bar fade and is now
  guarded there. Replaced with a bound method.

### Changed

- **Every warning, information and question sign in the app is ChromIQ's own.**
  The platform's signs were still showing in 70 places across 13 files. All
  three signs are drawn for Light, Dark and Neutral, and Neutral stays hueless.
- **Explanation has left the Create Chart sections for the ⓘ it belongs to.**
  Four blocks of standing text that sat inside sections now ride on the
  information icon of the control they describe, with the first line also in the
  hover tooltip so an icon carrying something says so without being clicked.
  **246 px of vertical space returned in English, 262 in German**, and the panel
  did not get wider in any of the thirteen languages.
- **The six buttons under the scanner preview read in three rows instead of
  four**, grouped by what each one acts on. The preview itself now takes the
  space the window gives it — it was pinned to its 460 px minimum however large
  the window grew, handing the rest to an empty spacer.

### For developers

- **The 34-check scanner-window sweep lives in the repository**, runs as
  `./run-sweep.sh`, and drives the real window end to end rather than a harness.
- **`docs/beta8_open_items.md` is a register the test suite enforces.** A fix
  called FIXED must name a test that exists; a deferred item must name who
  decided it and why; and the release gate refuses to go green while anything
  marked as blocking release is still open.

## v4.1.5-beta.7

**A third appearance called Neutral, a project with an umlaut that survives the
trip to Windows, and a long night of adversarial testing that found faults
which had been shipping for months.**

Two full review rounds and more than twenty attacking passes went at this
build, each one going at the round before it. Several of the worst things below
were introduced during that work and caught within the hour; they are listed
anyway, because a fault you never saw is still a fault that existed.

### New

- **Neutral, a third appearance.** A designed greyscale scheme, not Light with
  the colour turned down: one accent value, five-cell rules where the tab hues
  used to be, and every icon redrawn to read without colour. Choose it in
  Preferences beside Light and Dark. Light and Dark are byte-identical to
  beta 6 - checked view by view, not window by window.
- **Read single patches works with a CR30**, over USB and over Bluetooth,
  through ChromIQ's own driver. ArgyllCMS has never supported that instrument
  and no fork of it was needed. Pick your instrument in the window, or leave it
  on Detect automatically. Your ColorMunki and every other ArgyllCMS instrument
  behave exactly as before.
- **The scanner and camera profiling window is two panels.** The preview and
  its controls moved to the right, so the twelve wheel-turns of scrolling it
  used to take to reach the last control are now none. It fits a 1280 screen in
  all twelve languages.
- **Auto align, in the scanner and camera window.** Press it and ChromIQ tries
  to place the grid on the chart's patches for you, turning it the right way up
  if the scan was made sideways. It is an addition, not a replacement: nothing
  runs until you press it, one press puts your corners back exactly, and when
  it is not confident it says so and moves nothing rather than guessing. On
  scans it placed the grid correctly in 21 of 29 deliberately awkward cases and
  refused the other 8 out loud. On photographs it is much weaker: it refused
  most of them, and dragging the corners roughly around the chart first is what
  makes it work on a cluttered desk.
- **A profile keeps its accented name.** A profile called Müller-Prüfdruck used
  to arrive as M?ller-Pr?fdruck in Windows' colour management, because the ICC
  field ArgyllCMS fills cannot hold an accent. ChromIQ now writes the name into
  the field that can, and ChromIQ's own Profile Info window reads it back.

### Changed

- **An unmeasured calibration chart is treated as an experiment.** Replace one
  and it is not kept, the way a profile run's chart is not kept. A calibration
  that *has* been measured is always archived to the project's "cal/old"
  folder, and the window now says which of the two is about to happen. Before
  this, the window promised to keep a chart and then deleted five files.
- **The scanner window checks that what it read is the chart you meant.** It
  compares the reference against the chart, the read against the reference, and
  looks for clipping, before it builds anything.
- **Return no longer presses the button that discards a chart.**

### Fixed

- **Windows: a project name that was accepted and then could not be written.**
  Names of about 111 to 120 characters passed the name box and then failed when
  ChromIQ wrote the chart, because Windows limits the whole path rather than
  each folder name. The limit is now worked out from the longest file ChromIQ
  actually creates, and a project you already have opens whatever it is called.
- **Windows: the scanner and camera window would not fit a 1080p laptop.** Its
  smallest height was taller than the screen leaves once the taskbar and title
  bar are taken off, in every language.
- **Two projects whose names differ only in capitals no longer overwrite each
  other's chart.** ChromIQ kept the name you typed while the folder kept its
  own, so one run could hold two charts, each invisible to the other.
- **A measurement is no longer lost when you quit.** Closing ChromIQ during a
  measurement killed the reader, and the reader only writes its file on a clean
  exit, so the reading was gone with no warning. Quitting now asks, the way
  every other way out of a session already did.
- **"Save and stop" saves.** It was sending the reader a key it rejects, so the
  session never ended and nothing was written. "Keep measuring" now keeps
  measuring instead of stranding the session.
- **A single corrupt byte in a measurement no longer destroys it.** One zeroed
  byte in a `.ti3` made ChromIQ read the whole file as a different encoding and
  replace it with nonsense.
- **A project with an umlaut can be opened after a trip through a backup
  drive.** Older Mac disks store accented names differently, and ChromIQ found
  none of the project's files afterwards while telling you the chart was
  missing.
- **A bracket in a project's folder name no longer hides its chart**, and an
  asterisk no longer lets one project claim another's files.
- **A print that never happened is no longer recorded as one.** A sleeping
  printer or a cancelled dialog left a record saying the sheet had been printed
  through the profile, which then silently changed the yardstick every dE in
  the report was measured against.
- **Importing a measurement into a new project asks for the name once.** It
  used to ask twice, throw the first answer away, and leave ChromIQ saying you
  had no project open.
- **The app no longer crashes when a tool window is opened** after a spot read
  ends badly. A scroll bar was also crashing the app outright in some windows.
- **Everything ChromIQ writes now names its encoding**, so a file written on
  Windows and read on a Mac, or the reverse, arrives as what was written.
  This is GitHub issue #178.

### Known issues

- **Auto align has not been tried on a real printed chart.** Every scan it was
  measured against was generated. It is also untested on hexagonal charts, and
  it refuses small targets such as the QPcard, where it cannot reach the
  confidence it requires before moving anything.
- **Windows has now been tried, once, and the test suite could not finish
  there.** The app itself started and worked, in German at 200 % scaling, as a
  source checkout and as a packaged build. The suite hit a crash while drawing
  a checkbox and the run then hung; the hang is fixed and the drawing was
  rewritten, but nobody has yet seen a completed Windows run. Linux is
  untried.
 The encoding
  work above is the fix for a Windows-only fault, and it was written and tested
  on a Mac. If you have a Windows machine, that is the single most useful thing
  you can test.
- **The scanner window's "Correct perspective" tick has no effect** on a normal
  read. Found while testing something else, left alone rather than changed
  under a release.
- Generating a new chart over a run that holds a chart and no measurement still
  replaces it without asking. Unchanged from beta 6, and deliberately deferred.
- In Neutral, a suspect patch is still marked in red. The colour is the
  information there, so it was left rather than flattened.
- Nine controls in the Check and Refine gamut panel cannot be reached at the
  smallest window size. Present in beta 6 as well.

## v4.1.5-beta.6

**Check & Refine now asks where a measurement should go instead of deciding for
you, and four ways to lose a measurement are gone.**

Three rounds of adversarial testing went at this build, each one attacking the
round before it. Most of what follows was found that way, and several of the
faults had shipped for months without anyone meeting them.

### New

- **Check & Refine is a proper import door.** Browse for a `.ti3` that is not
  in one of your projects and ChromIQ asks where it belongs, in the same window
  Build Profile uses, in Check & Refine's own colour. It used to create a
  project without asking.
- **"Just check it where it is."** A third answer, for a measurement you want
  to look at without filing anything: nothing is copied, no project is made,
  and the report is written next to the file itself. The window says plainly
  what that costs you: no run, and nothing to look it up in later.
- **The ColorMunki's dial is drawn.** Both calibration windows now show the
  wheel turned to the mark that window is asking for: the white bar at half
  past four on the gear when it wants calibrating, at six o'clock on the target
  mark when it wants measuring. Every other instrument's windows are unchanged.

### Fixed

- **Declining to teach a CR30 its tile no longer closes ChromIQ.** Pressing
  "Not now", which that window invites you to do, ended the app mid
  measurement and took the readings taken so far with it.
- **The optional calibration window no longer closes ChromIQ either**, and its
  "Skip this step" button now does something. Both faults only appear with an
  instrument that offers optional calibration.
- **Importing a measurement can no longer end the app.** Four separate causes:
  a folder ChromIQ cannot write to, a disk that is full, a drive or share that
  has gone away, and a project whose own `project.json` has been damaged. Each
  now says what went wrong and leaves everything as it was.
- **A measurement can no longer be filed into the wrong project.** Picking a
  folder whose name contains something like a space (a Finder duplicate, an
  unzipped hand-off, a Dropbox conflicted copy) used to make an empty project
  of a slightly different name and then complain that it had no chart in it. A
  project that lives behind a symlink, on an external drive or a NAS, could
  take the measurement into whatever project happened to be open instead.
- **"Nothing has been copied" is true again.** Checking a file where it lies
  used to be followed immediately by a window offering to copy it in, and one
  click made a whole project.
- **Cancel means nothing happens.** Answering Cancel to "Where should this
  measurement go?" used to be met by a second, unrelated question about copying
  chart files.
- **A new run opens on your defaults, not on the last run's settings.** The
  instrument, the paper, the layout mode, both indicator checkboxes, the stamp
  option, the Guided settings and the gamut options were all inherited from
  whichever run you had been looking at, and then stored on the new run as
  though you had chosen them.
- **Row numbers fit the row they name.** On a tall chart the automatic size was
  taken from the patch width, so the numbers printed over each other into an
  unreadable ladder; they are now capped at the height of a row. They also stay
  inside the "Text distance to edge" limit instead of walking to the paper's
  edge on charts with more than ninety-nine rows.
- **Guided's patch estimate matches the chart it builds.** It promised 368
  patches on a CR30 A4 sheet that holds 345.
- A refused import no longer leaves a run on disk, moves you to a different
  run, or leaves the target bar naming a run that does not exist.
- A new user with no projects yet can now reach "Just check it where it is".
  The window it lives on refused to appear when there was nothing to list.

## v4.1.5-beta.5

**Row numbers can now be printed on any chart, and a preset stops naming your
project after itself.**

Two reports from Knut.

### New

- **"Show row numbers".** ChromIQ has always printed a number beside each row
  of patches on a SpectroScan and a CR30 chart, which — together with the
  letters along the top — lets you find one patch among several hundred the way
  you find a square on a map: strip A, row 12. It was never offered anywhere
  else. There is now a checkbox for it in the layout panel, next to "Show strip
  indicators", for every instrument.
- Every chart you have already made looks exactly as it did. The setting starts
  out as "whatever this instrument normally does", so nothing changes until you
  tick or clear the box yourself. Your choice is then saved with your presets
  and with the chart.
- Switching it on reserves 7.5 mm down the left edge, so there may be room for
  slightly fewer or slightly smaller patches. The estimated patch count takes
  that into account, and so does the chart ChromIQ actually builds.
- Where the clip border would be printed over the numbers, the layout inspector
  says so and offers the two ways round it.

### Changed

- **A preset no longer names your project after itself.** Loading a built-in
  preset with the name box empty used to name the project after the preset, so
  a folder, the name printed on the chart and the finished ICC profile could
  all end up called something like "i1Pro-A4-162p-1page-Portrait-w7.5mm".
  ChromIQ now asks you for a name.
- **The window that asks now takes the answer.** It has a name box, a Continue
  button, and a ⓘ that explains what makes a good name and where that name will
  show up later. Type it and the chart you asked for is built — no going back to
  a field elsewhere and picking the preset a second time.

### Fixed

- Choosing a SpectroScan or a CR30 could silently switch off the row numbers
  those two instruments have always printed.
- A preset chosen while a project was already open could rename that project
  after the preset.
- The name is now settled before ChromIQ checks whether it already belongs to a
  project, so an existing project is never quietly replaced.
- A name too long for the filesystem is refused with an explanation, instead of
  failing halfway through and leaving a half-made project behind.
- The live chart preview no longer opens a window while you drag a slider.

### Known issues

- In "Prioritise chart area", the row numbers still cost 7.5 mm of paper that
  is then left empty at the right-hand edge. This affects SpectroScan and CR30
  charts as well, and predates this release; it is being tracked separately.

## v4.1.5-beta.4

**Finding out why Bluetooth will not connect — and a magnet guard that was
silently switched off for some people.**

### Fixed

- **A tile learned over the USB cable did not protect you over Bluetooth.**
  ChromIQ files your instrument's white-tile value under the instrument's own
  id, and it was reading a different id on each connection — so the magnet
  guard looked under a name with nothing stored against it and stayed off.
  Nothing was ever measured wrongly because of it, but the protection was
  absent on the one connection that has no other defence.
- **A failed Bluetooth connection left nothing in the log.** Success and
  failure looked identical afterwards, which made "did it even try?" an
  unanswerable question.
- **The help-icon debug line was filling your log.** It recorded every help
  icon the app built — around three fifths of everything ChromIQ wrote — and
  pushed the entries that diagnose real faults out of the file. Removing it
  roughly triples how far back your log reaches.

### Changed

- **The Measure tab now says how it connected**, over the cable or over
  Bluetooth, in the session log. ChromIQ chooses for you, and until now it
  never said which it chose.
- **The Bluetooth report says more.** It counts devices that advertise no
  services at all — which is allowed, and means ChromIQ may never have looked
  at your instrument — and it is honest that a serial number you type may not
  match what the instrument broadcasts, so a silent result does not rule your
  instrument out.
- **The Tools menu is capped and scrolls.** It had grown past the bottom of
  smaller screens, where the last tools could not be reached.

### Known issues

- Bluetooth has still only been used successfully on macOS. If it will not
  connect for you, Tools → Instruments → CR30 Bluetooth report is what to send.

## v4.1.5-beta.3

**Aiming help for the CR30, a legend that gets out of your way, and the layout
controls where the help says they are.**

### New

**See where the instrument will sit.** A CR30 is placed on each patch by hand,
and its 33 mm body hides the patch the moment you lower it — so you cannot look
at what you are aiming at while you aim. The preview now draws that body to
scale, dashed, on the patch you are being asked for: line it up on screen, note
which neighbours it covers, and put the instrument down so those same neighbours
are evenly covered. A second, much smaller circle appears only when there is a
problem — the 4 mm measuring opening, shown when the patch is too small for it,
in which case part of every reading is the neighbouring patch. Both figures come
from the manufacturer's own specification. The option is in the Measure tab's
live-preview section and appears for the CR30 only.

**A Bluetooth report, for when the instrument will not connect.** Tools →
Instruments. It looks at what your computer's Bluetooth can see, whether
anything is offering the service a CR30 uses, and whether ChromIQ's own search
accepts it — so the three cases can be told apart instead of guessed at. It
writes a file you can send. Nothing it does can disturb your instrument: it is
never asked to measure and never asked to calibrate.

### Changed

**The legend fades out when you point at it**, so you can see the patches
underneath. It sits in the bottom paper margin, but on a chart whose patches run
to the edge it has to rest on the last row — now it simply gets out of the way.

**Patch size and Patch scale have moved into Basic**, next to "Prioritise patch
size", where the help has always said they were. They were in Expert Options,
collapsed, while the other layout method showed its settings in plain sight.

### Fixed

- **"Prioritise chart area" now honours your left margin.** A 7.5 mm band for
  the row numbers was reserved OUTSIDE it, so a 1 mm margin put the first patch
  at 8.5 mm. The row numbers now sit inside the margin, and the panel warns when
  it is too tight for them.
- **The margin readout says what it measures** — "Left (to first patch)" — and
  explains the two things that legitimately sit in that space.
- **A flagged patch keeps its whole red ring.** On a hexagonal chart the
  neighbouring patch was painted over part of it.
- **Loading a new chart no longer shows the previous chart's measurements.**
- **The legend no longer lands at the top of the sheet**, over the column
  letters, on charts whose strip geometry is not recorded.

### Known issues

- Over Bluetooth the learning step asks for TWO presses with the cap on, not
  one, and does not yet say so while it waits.
- Bluetooth has still only been used successfully on macOS. If it will not
  connect for you, the new report under Tools → Instruments is what to send.

## v4.1.5-beta.2

**The magnet guard now works on your instrument, not only on the one it was
built from — and you can take a reading with the space bar.**

A magnet at the CR30's measuring opening stops it measuring: it takes a white
calibration instead and hands back its stored white-tile value. That value looks
like a perfectly ordinary patch colour, so the only defence is recognising it.
Until now ChromIQ recognised ONE instrument's value, hard-coded — and the only
other CR30 anyone has measured reads up to 4.69 %R away, ninety-four times the
tolerance. On anyone else's device the check matched nothing and its owner had
no protection at all.

### New

**ChromIQ learns your instrument's white-tile value.** One press with the cap
on over USB — two over Bluetooth, where the instrument does not report that the
opening was covered and ChromIQ instead requires two identical readings, which
real measurements never are. Offered once after calibrating. That press is harmless to your calibration:
measured across three experiments on real hardware, a capped press does not move
the white reference. The value is filed against your instrument, so a second
CR30 never inherits the first one's — over USB by its serial, over Bluetooth by
its address, which distinguishes two devices on macOS, Windows and Linux alike.

**Space, or Enter, takes the reading** without touching the instrument. That is
not only convenience: pressing the instrument's own button moves it, by about
ten times its own measurement noise — 0.5 %R against 0.05 %R, both measured.
Keeping it still is measurably more accurate. ChromIQ offers the key once it has
learned your instrument's tile and refuses it before then, because a reading
ChromIQ asks for cannot report the magnet gate, and the learned value is what
stands in for it.

**A CR30 chart no longer defaults to printing spacers.** A spacer exists so a
strip reader can find where one patch ends as it is swiped across the row. A
CR30 is lifted onto each patch by hand and never swipes, so a spacer is ink it
cannot use — and the width it costs is patches per sheet. Guided already knew
this; Manual and From Profile Gamut now do too. It is a default, not a rule:
turn them back on and you get them.

### Fixed

- **Bluetooth: the remembered address is identified before anything is written
  to it.** `ffe0` is the generic service every hobby gadget exposes, and the
  next frames sent to whatever answers there are calibration commands.
- **The magnet window no longer prints its own explanation back at you** in
  capitals, labelled as something the instrument said. It did not say it.
- **"With a magnet at the opening the instrument does not measure at all"** was
  the opposite of the danger. It answers — with a plausible number, which is
  the whole reason the guard exists.
- **A reading refused as a repeat** said "bit-identical" and "the low bits", and
  blamed the magnet in a window whose advice was to press the button again.
- **Seven places quoted the "Refine / resume existing measurement (-r)"
  checkbox without its flag** — and Polish quoted a label that did not exist on
  any control.

### Known issues

- Over Bluetooth the instrument reports no serial, so its address is used to
  tell two units apart. If your Bluetooth pairing is reset, ChromIQ offers the
  learning step again rather than trusting a stale value.
- Over Bluetooth the learning step asks for TWO presses with the cap on, not
  one, and it does not yet say so while it waits — if it seems to hang after
  the first press, press again. Over USB one press is enough.
- The keyboard trigger is refused until your instrument's tile is learned. This
  is deliberate — see above — but it means Space does nothing on a fresh
  install until you have been through the one-off step.

## v4.1.5-beta.1

**ChromIQ can now measure a chart with a CR30.** It is the first instrument
ChromIQ drives itself rather than handing to ArgyllCMS.

The CR30 is a low-cost spectrophotometer with no ArgyllCMS support of any kind,
so everything here — finding it, identifying it, calibrating it, reading a patch
— is new. It was reverse engineered on real hardware over several weeks; the
protocol notes, the captures, and the experiments that turned out **wrong**, are
public at https://github.com/itsab1989/chromiq-cr30-research.

**Where it has actually been used:** macOS over USB and over Bluetooth, and
Windows on ARM over USB, each with a real instrument and a real chart. Bluetooth
on Windows and everything on Linux should work and have not been tried on
hardware — please tell us if you get there first.

### Before you start — Windows needs a driver

The CR30 talks through a CH340-class USB-to-serial chip, and Windows needs WCH's
driver for it. macOS needs nothing at all. On Linux the driver is part of the
kernel, so there is nothing to install, but your user needs permission to open
the serial port (on most distributions, being in the `dialout` group).

1. Download **CH341SER** from **wch-ic.com**.
2. Run the installer, then unplug and replug the instrument.
3. On **Windows on ARM** you need version **4.0.2026.02 (11 February 2026) or
   newer** — the older packages do not include ARM64 and will install without
   doing anything.

If ChromIQ says no instrument was found while the CR30 is plugged in, this is
almost certainly why: look in Device Manager for a device with a warning
triangle. The cable and the instrument are fine. We would like ChromIQ to tell
those two apart itself, and it does not yet.

> ⚠ **Do not use Preferences ▸ “Install USB Driver…” for the CR30.** That button
> installs WinUSB, which is right for the colorimeters it lists and wrong here —
> it would replace the serial driver and the instrument would stop being found.
> It does not offer the CR30; please do not point it at one by hand.

The full page is `docs/cr30_platform_support.md`.

### How measuring with a CR30 works

- **ChromIQ calibrates it for you.** A window shows both calibration steps as a
  picture, with the current one marked, so the two cannot be confused. There is
  no button to press on the instrument.
- **The dark reference is offered as a tick-box** on that same window, taken
  against open air — your CR30 has no black tile. It is off unless you ask for
  it, so it never becomes a second window on every measurement. Afterwards
  ChromIQ reads once and tells you what came back — see below for exactly what
  that does and does not prove.
- **ChromIQ cannot check a white calibration at all**, and says so rather than
  implying otherwise. The instrument reports the same value whatever is under
  the cap, so a calibration against the cap's green face looks exactly like a
  good one. Your eyes are the only check there is.
- **Read a patch by pressing the button on the instrument.** ChromIQ highlights
  the patch it is waiting for, and never highlights one it is not listening to.
- **Bluetooth needs no driver on any platform.** A phone app that is merely
  *connected* takes the button press exclusively, so close it before measuring
  or your readings will never arrive.
- **A Bluetooth calibration takes about three seconds.** ChromIQ remembers the
  address it last reached your instrument at, so it does not search for a device
  it has already met. If that address stops working — a different computer, a
  second instrument, a reset Bluetooth stack — it searches again by itself.

### The safety part, which matters more than it sounds

**A magnet at the measuring opening does not measure — it recalibrates.** The
instrument takes a white calibration from whatever it is resting on and returns
a stored constant, and nothing in the reply says so. A laptop lid, a fridge
door, a magnetic desk mat or the instrument's own cap will do it, straight
through a sheet of paper.

ChromIQ detects this, **refuses the reading**, stops the measurement, and offers
to retake the white calibration on the spot. Everything measured before that
moment is safe and already saved. It cannot be prevented — the only signal
arrives inside the reading it has already spoiled — but it is never accepted in
silence.

Over USB this is caught on every unit. Over Bluetooth there is no equivalent
signal, so on a CR30 other than the one this was developed on the first such
reading may not be caught. Use USB if you have the cable.

### Fixed

These affected 4.1.4 and are not about the CR30.

- **On Windows, every measurement lost its own bookkeeping.** ChromIQ's
  measuring engine reports what it is doing as it goes, and a Windows chart path
  like `C:\Users\…` was written into that channel without escaping — so the
  message carrying the strip map and the patch count was thrown away silently,
  on every measurement. macOS and Linux were unaffected, because their paths
  have no backslashes.
- **The Zadig driver instructions now warn CR30 owners.** Those steps say to
  find your instrument and give it the WinUSB driver, which is right for every
  colorimeter ChromIQ lists and wrong for a CR30 — it is reached through a COM
  port, and WinUSB would remove it. ChromIQ also now refuses outright to install
  WinUSB on a USB-serial instrument, whatever asks it to.
- **The driver window counts properly**: “device(s)” and “colorimeter(s)” are
  gone.

### Found by testing it on the bench, not by reading the code

- **The check after a black calibration cannot tell you the reference was taken
  against the right thing**, and no longer implies it can. A dark calibration
  *defines* what zero means, so whatever the instrument was pointed at becomes
  the new zero and reads as nothing a moment later — calibrated deliberately
  against white paper on a real CR30, it read back 0.004 %. What it still gives
  you is the number itself, recorded where you and we can both see it. Getting
  that step right is your eyes, not ours, and both windows now say so.
- **Every calibration message used to be erased.** ChromIQ cleared the
  measurement log after the calibration had already written to it, so the
  read-back result, the note that a white calibration cannot be verified, and
  the note about skipping the dark step were all wiped a moment after they
  appeared. Nobody had ever read any of them. The reading now also goes to the
  log file, so it survives in a problem report.
- **A dark reference that does not look dark now stops and asks**, instead of
  mentioning it in a log panel you may have collapsed. It offers to take the
  calibration again on the spot.
- **When the instrument goes away mid-session, ChromIQ says so in plain
  words** — it used to pass on the Bluetooth library's own sentence, "Service
  Discovery has not been performed yet" — and it no longer tells you the
  measurement can go ahead over a connection that is gone.

### Known limits

- The measurement preview's legend can cover the last row of patches when the
  page margin is small.
- Help cards still print with US Letter measurements on Letter paper.
- On Windows, “no instrument found” is also what you see when the driver is
  missing. The two should be told apart and are not yet.

## v4.1.4

Every "Save as…" dialog in 4.1.3 was broken. One line was at fault, nothing had
ever tested it, and it took a bug report about a help card to find it. Looking
for its neighbours turned up more: typing `0.7` into a number field gave you
`7.0`, a chart build you interrupted destroyed the chart it was replacing, and
deleting a project could destroy half of it and then tell you nothing had
happened.

### Fixed

- **Every “Save as…” dialog works again.** The help card's PDF, the profile
  report, the measurement report, the spot readings, the clip template, the
  layout-preset export, the soft-proof image, the patch colours, the i1Profiler
  export — twelve in all. The shared save dialog overwrote its own *parent
  window* argument with a folder path, so it raised an error before it could
  open, for every caller that suggests a file name. Reported against Help ▸
  SAVE AS PDF…, where it showed as “Something went wrong while writing the PDF”.
- **Typing `0.7` no longer gives you `7.0`.** On any computer set to a language
  that writes decimals with a comma — German, French, Spanish, most of Europe —
  every number field rejected the `.` you typed, closed up the digits, and left
  a number ten times too big, in range, with nothing on screen disagreeing with
  it. All fourteen fields. The one that costs the most is the patch-consistency
  tolerance under Measure: ChromIQ really sent `chartread -T7.00` instead of
  `-T0.70`, which tells the instrument to accept a strip ten times further out
  of agreement than you asked for — a measurement that looks fine and is not.
  Both `.` and `,` are now read as the decimal point, whichever your computer
  uses.
- **A chart build you stop, or that fails, no longer destroys the chart it was
  replacing.** The old chart is set aside before the build starts and put back
  on any ending that does not produce a new one — including closing ChromIQ
  while it runs. This matters most in the window the app itself tells you to
  spend waiting: between printing a chart and measuring it. Losing the chart's
  `.ti2` there makes the sheets on your desk unreadable, and because the layout
  seed lives only in that file, building again from the same settings produces
  a different chart that no longer matches them.
- **There is a Stop button on Create Chart.** Until now the only way out of a
  build was to quit ChromIQ, which was exactly what destroyed the chart.
- **Cancelling a name prompt no longer closes ChromIQ.** Loading a patch set
  with no project open, or copying in a profile that lives outside your working
  folder, asks you to name the project — and pressing Cancel there shut the app
  down instead of simply stopping. It has done that in every version since
  4.0.0.
- **A help card PDF that cannot be written no longer reports success.** ChromIQ
  asked the PDF tool whether it had complained; the tool does not complain, it
  simply paints nothing. The file itself is checked now, and an empty one is
  removed rather than left behind under the name you chose.
- **Typing the project name is no longer sluggish.** One keystroke in the
  Create Chart name field recomputed the whole page layout — a column-fit search
  measuring all 26 capital letters, over 51,000 text measurements per key
  pressed, to answer a question whose answer never changes. Measured at 82 ms a
  keystroke; now about 4 ms. The same saving applies to every layout estimate
  and to building a chart.

### New

- **ChromIQ tells you when a project of that name already exists.** Type a name
  you have used before and a line appears under the box; build, and a window
  names the folder, lists what each of its runs holds, and lets you choose:
  carry on in a run you pick (a new one by default, which costs nothing),
  replace the project after a second confirmation, use a different name, or
  stop. Before this, ChromIQ opened that project in silence and built into it.
- **You choose which run to continue in**, in that same window, instead of the
  project's own last run being taken for you.
- **Backing out of a built-in preset now really changes nothing.** Pick one from
  the ★ list, read the window, press Cancel, and ChromIQ used to leave you in
  Manual with the preset's whole layout in the panel — and quietly kept four of
  its choices as your app-wide settings, including whether the ChromIQ layout
  engine is on and how the ruler marks are drawn. Everything goes back now: the
  mode, every setting on the page, the layout, the name field, any section you
  had opened, and the preset list itself, which returns to the preset you
  actually had and can be used to choose that one again. Triple Density in
  particular used to come back ticked but dead: the layout it hides was gone, so
  unticking it afterwards changed nothing.

### Fixed — your work is safer than it was

- **Deleting moves things to your Trash** — the Recycle Bin on Windows, the
  Wastebasket on Linux — so you can bring them back until you empty it. It used
  to remove files one by one and stop at the first it could not: one read-only
  sub-folder was enough to destroy ten files of twenty-nine, `project.json`
  among them, so ChromIQ could no longer open what was left — while the window
  said “Nothing was changed.” A move to the Trash cannot half-happen, and when
  there is nowhere to put the files nothing is touched at all.
- **The Delete window stops claiming nothing will be lost when something will.**
  Re-making a chart on a measured run archives the measurement and the profile
  into the run's “old” folder, on purpose, because they cannot be recreated.
  Delete only looked at the live files, so such a run reported itself as never
  measured — and the window said so while deleting two archived measurements, a
  profile and both averaging readings. It now counts what is in “old”, names the
  dates, and mentions the copy of the chart your measurement was taken with.

- **The individual readings of an averaged measurement are no longer deleted.**
  Re-generating a chart archived the measurement and the profile and then
  removed `reads/read1.ti3`, `read2.ti3`… — instrument readings taken by hand,
  which nothing can bring back. They are archived with everything else now.
- **Projects in a sub-folder of your ChromIQ folder are proper projects.**
  Renaming one used to fail and leave an empty project at the new name while
  abandoning the real one; the “this profile has already been built” guard could
  not see its profile; and “Delete the whole project” refused and said nothing.
- **Replacing a project is all or nothing.** It could fail half way and leave
  the folder neither the old project nor a new one, while reporting that nothing
  had changed. Everything is put back now, and a failure is a window rather than
  a line in the log.
- **A project folder with an unreadable or hand-edited `project.json` can no
  longer crash Generate Chart**, or steer ChromIQ outside the project folder.
- **The clip-template export lists your files again.** The dialog was handed a
  label where it expected a file filter, so it filtered on the words in it.
- **Your log is readable.** Nine minutes of use produced 2,315 lines, of which
  1,813 were the image library talking to itself and 101 were ChromIQ. The noisy
  libraries are quiet now, so a real fault is not pushed out of a rotated log by
  chatter — and ChromIQ says plainly whether it opened an existing project or
  created a new one.

### Also

- The website's Create Chart, Measure and scanner sections were rewritten, and
  two sections added: keeping a profile honest over months, and where your work
  lives.

## v4.1.3

ChromIQ now speaks thirteen languages properly, not just completely — every
catalogue was read end to end and the words on one screen were made to agree.
Thirty-eight new i1Pro charts, printable help cards, and a long list of things
that quietly did the wrong thing.

### New

- **Thirty-eight new i1Pro charts.** Nineteen with 7.5 mm patches in A4, US
  Letter and A3, and nineteen with 8 mm patches, from 156 up to 4,212 patches.
- **Help cards can be printed.** A Print… button on any open card, laid out for
  the paper rather than the screen, with the ChromIQ wordmark and the spectrum
  band on every page.
- **Three more help cards** — one each for the tools that had none: designing a
  patch set, reading single patches, and the patch cube.
- **A Close Project button**, third along the top left, beside Open Chart File.
- **Keyboard shortcuts appear in tooltips**, spelled the way your own keyboard
  spells them — ⌘1 on a Mac, Ctrl+1 everywhere else.

### Changed

- **All thirteen languages were swept for consistency, one at a time.** The same
  control was often named several different ways in one language — and the
  second name usually already meant something else. Italian used one word for
  both *chart* and *paper*, so the scanner help said "clean the glass and the
  paper" when it meant the chart. Polish used its word for *tab* to mean
  *chart*. Portuguese used one word for *gamut*, *gamma* and *range*. Russian,
  Norwegian and Chinese each carried five names for one thing. Around 2,900
  entries were corrected.
- **French now addresses you informally**, matching German, Dutch, Italian and
  Spanish — it had been split down the middle, saying "vous" in a help text and
  "tu" in the tooltip beside it. **Portuguese is consistently European
  Portuguese**, including the update notice everybody sees.
- **Preferences opens in about 0.7 seconds instead of 2.3.**
- **The Red River presets are Knut's own again**, and the i1Pro preset list is
  ordered by paper, then patch count, then page number.

### Fixed

- **A project name containing a dot split its files in half**, and the project
  could not be measured. 120 of the 130 built-in presets suggest such a name.
  Projects already broken this way are repaired when you open them, and nothing
  is deleted — the old files are kept.
- **Guided mode used ArgyllCMS printtarg instead of ChromIQ's own layout
  engine** whenever "Print info in left clip area" was ticked — a setting
  written only by the Manual tab, which Guided has no control for. So a box
  ticked in one tab changed what another tab produced, invisibly, while the
  screen still said "ChromIQ layout engine".
- **Your chart was re-drawn and overwritten when you had not asked for it.**
  With auto-update preview on, changing module, picking a different run, loading
  a preset, pressing Reset or opening a chart file each silently re-laid out the
  chart and rewrote it to disk.
- **The Create Chart ▸ Manual panel was cut off on the right in nine of the
  thirteen languages** — controls under the scrollbar, the ⓘ buttons sliced in
  half. Several controls had been sized against the English word they show, so
  German's "automatisch" arrived as "natisch".
- **The margin check no longer accuses a chart of breaking its own margins.** 45
  of the built-in charts are drawn at 200 dpi and land exactly on their declared
  margin, but were reported inside it because a chart's edges can only fall on
  whole pixels.
- **Duplicating a run dropped 17 of the 27 things it records**, including every
  Create Chart setting.
- **ChromIQ could create a project you never asked for** — three separate ways,
  including simply opening the Tools menu.
- **Closing a window could crash ChromIQ.**
- **A wrong ArgyllCMS path could lock you out of the app.**
- **Help text named buttons that do not exist** — twenty of them, including a
  tick box removed in 2025 and advice the app itself warns against. Corrected in
  English and in every language.
- **Printed help cards came out at a third of their size on macOS**, lost whole
  pages of text silently, and printed sheets with nothing on them.
- **ChromIQ left large temporary files behind** after soft-proofing.
- **Print Chart's settings were lost when you closed the project**, and settings
  could follow you from one run into another.

### Known issues

- A chart built in Guided and then continued in Manual is judged against layout
  defaults rather than your instrument's minimums, so it can show a green
  "Margins: OK" on a sheet the instrument cannot read. Judge margins from the
  Guided panel. See issue #171.

## v4.1.3-beta.21

Every language got read end to end, and the panel that had been quietly cut off
in nine of them now fits.

### Fixed

- **The Create Chart ▸ Manual panel was cut off on the right in nine of the
  thirteen languages.** Controls ran under the scrollbar, the ⓘ buttons down the
  right edge were sliced in half, and the panel could be swiped sideways. The
  worst was the row of preset buttons — in German, "Auf Vorgabe zurücksetzen /
  Vorgabe aktualisieren / Vorgaben bearbeiten" needed 60 px more than the panel
  has, Swedish 155 px more. Those buttons now wrap onto a second line instead of
  pushing everything sideways, so all three labels are readable in full.
  English is unchanged.
- **Several controls were sized against the English word they show.** The
  patch-size boxes reserved room for "auto" and cut German's "automatisch" to
  "natisch"; the "Stamp settings used on the chart" tick box lost its last
  letters behind its ⓘ; three tick boxes in the margin panel and a Portuguese
  label ("mático") were clipped the same way. Each now measures the word it
  actually shows.
- **The Measure tab scrolled sideways in Spanish, Portuguese and French** — a
  dropdown pinned to an English width.

### Changed

- **All thirteen languages were swept for consistency, one at a time.** The
  same control was often named several different ways in one language — and
  sometimes the second name already meant something else. Italian used one word
  for both *chart* and *paper*, so the scanner help said "clean the glass and
  the paper" when it meant the chart. Polish used its word for *tab* to mean
  *chart*, colliding with itself in a single sentence. Portuguese used one word
  for *gamut*, *gamma* and *range*. Russian, Norwegian and Chinese each had
  five names for one thing. Around 2,900 entries were corrected in total.
- **French now addresses you informally**, matching German, Dutch, Italian,
  Spanish and the others — it had been split down the middle, saying "vous" in
  a help text and "tu" in the tooltip beside it.
- **Portuguese is consistently European Portuguese**, including the update
  notice everybody sees.
- **Help text no longer names buttons that do not exist.** Twenty English
  strings pointed at controls that had been renamed or removed — one described
  a tick box deleted in 2025, and another gave advice the app itself warns
  against. All corrected, in every language.

## v4.1.3-beta.20

Changing tab, picking a run or loading a preset re-drew your chart and wrote it
to disk. And the help cards named eleven buttons that do not exist.

### Fixed

- **Your chart was re-drawn and overwritten when you had not asked for it.**
  With "Auto-update preview" on, generating a chart in Guided and then clicking
  MANUAL replaced the sheet you had just made — 450 ms after the click, with
  nothing touched. It happened again when you merely selected a different run in
  the run bar, when you loaded one of your own presets, when you pressed Manual's
  "Reset", and when you opened a chart file with Open Chart File (.ti2). Filling
  the layout boxes on your behalf looked exactly like you turning a knob, so the
  live preview believed the layout had changed. It now settles at the end of each
  of those operations; a change **you** make still refreshes the preview at once.
- **Eleven help-card steps named buttons that do not exist.** Six described a
  "Disable bidirectional reading" tickbox that was removed from ChromIQ in 2025 —
  the real control is the Measure tab's "Strip recognition" row with its "Auto"
  box. Seven said "Analyse" where the button reads "Analyse Profile Quality", two
  said "Load .ti3" where there is an icon and a folder button, and others named
  "Use as Pre-conditioning Profile", "Read again & average" and "Empty the run".
  All corrected in English and in all twelve languages.
- **A help card advised something the app itself warns against.** The new
  strip-recognition text told you to switch off "Auto" and force bidirectional
  reading if you scan in one continuous motion. On a fixed-order chart that can
  latch onto the wrong strip and quietly build a profile with colour casts —
  which is why ChromIQ shows a warning when you do it. The cards now say to leave
  "Auto" ticked and let ChromIQ choose.
- **A help card said "Auto" picks the strip-recognition mode from your chart
  and your instrument.** It reads the instrument alone — so on an i1Pro with a
  fixed-order chart it chooses bidirectional reading, which is the case ChromIQ
  separately warns you about. The card now says what Auto really does.
- **The margin warning named the wrong minimum in every language but English.**
  When a margin came out short, the panel had to say whether it missed your
  instrument's minimum or the one the chart itself was laid out to. It decided
  by inspecting a translated sentence, so outside English it always said
  "instrument" — quoting a figure no instrument setting carries.
- **"Check && Refine" appeared with two ampersands** in three help texts.
- **A US Letter help card printed a sheet with nothing on it** — the
  "Your first profile" card, after its text grew.

### Changed

- **The margin check no longer tightens itself on a coarse chart.** beta.19
  capped the allowance at one pixel of 200 dpi; that made correct charts accuse
  themselves. A factory preset changed only from 200 to 180 dpi reported "Top
  margin 33.9 mm is below the 34 mm minimum" against a layout that sits exactly
  on its box. A chart cannot be measured more finely than the pixels it is drawn
  on.
- **The "room left on the last page" hint no longer contradicts itself.** On a
  Guided chart it read "space for about 22 more patches on it (the page holds
  about 0 in total)". Both numbers came from re-deriving a page the recipe cannot
  describe, so the hint is now left out for those charts rather than guessed at.

### Under the hood

- One design specification, `per_target_settings.md` §7 B, prescribed a guard
  that cannot work — the handler it governs fills the panel twice and the second
  fill runs after the guard is down. Rewritten to describe the shape that holds,
  marked as awaiting confirmation.
- Three tests that could not fail were removed or repointed: a function nothing
  called, and the run-switch test the specification says nothing ships without,
  which had been passing against a stand-in class with no timer.

## v4.1.3-beta.19

Guided mode has been quietly using the wrong layout engine since June, and the
twelve translation catalogues are complete.

### Fixed

- **Guided mode used ArgyllCMS printtarg instead of ChromIQ's own layout
  engine** whenever "Print info in left clip area" was ticked. That setting is
  written only by the Create Chart ▸ Manual tab's "Save as defaults" button, and
  Guided has no control for it — so ticking a box in one tab permanently changed
  what another tab produced, invisibly. Meanwhile the Guided screen said
  "ChromIQ layout engine" and predicted the engine's patch count, so the number
  on screen could differ from the chart that was built. Present since
  2026-06-30, in the very change that was supposed to make Guided engine-only.
  **If you had that box ticked, your charts will now look different** — see
  below.
- **The chart preview told you to press a button that could not help.** A
  freshly made Guided chart showed red marker dashes captioned "Markers not on
  this sheet yet — press Generate Chart", but the marker settings live only in
  Manual, and Guided charts never carry markers — so pressing Generate Chart
  rebuilt the same sheet and the message came back. Guided now shows what the
  sheet actually carries, and never claims a change is pending.
- **The margin check no longer accuses a chart of breaking its own margins.**
  45 of the built-in charts are drawn at 200 dpi and land exactly on their
  declared margin, but were reported 0.05 mm inside it because a chart's edges
  can only fall on whole pixels. The check now allows one pixel — the smallest
  error a printer can actually make — instead of a fixed figure that happened to
  suit 300 dpi.
- **A built-in chart preset could build the wrong chart.** After choosing
  Presets ▸ Default, picking the same built-in preset again produced a chart
  with 6 strips instead of 7, no clip band, no ruler marks and none of the
  preset's margins.

### Changed

- **All twelve languages are complete** — every text ChromIQ shows is now
  translated in German, Dutch, Spanish, French, Italian, Portuguese, Swedish,
  Norwegian, Polish, Russian, Japanese and Simplified Chinese.

### If you had "Print info in left clip area" ticked

Your Guided charts were being laid out by printtarg and will now be laid out by
ChromIQ's engine. For i1Pro on A4, US Letter and Legal nothing changes — 484
patches, 22 strips, as before. A4R gains 16 patches, US Letter rotated gains 17,
and A3, 11x17 and A2 gain a whole extra strip. Every affected sheet looks
different. Nothing you have already measured is invalidated: a Guided chart
rebuilt from its own record always produced a different sheet anyway, because
printtarg charts record no layout recipe.

Gate: 7452 passed, 140 skipped, 2 xfailed.


## v4.1.3-beta.18

Fixes found by reviewing what beta.17 actually shipped, plus Knut's beta.17
notes. **Two of these were security or data faults in the repair added one
release earlier.**

### Fixed

- **The project repair could rename files outside the project.** The repair
  added in beta.17 executed its record of planned moves without checking that
  the paths stayed inside the project folder, so a project folder containing a
  crafted or merely corrupted `name-repair.json` — the kind of folder people zip
  and send each other — could rename files anywhere the recipient can write, the
  moment they opened it. The repair now refuses any entry that points outside
  the project, and says so in the log. Proven both ways: the shipped beta.17
  moves the file, this build does not, and a legitimate rename inside the
  project still runs.
- **The repair's undo record could be lost exactly when it was needed.** It was
  written by truncating the file first, so running out of disk part way through
  left an empty record *after* the renames had happened. It is now written to a
  temporary file and swapped in atomically — a move ChromIQ cannot record is a
  move it does not make.
- **One malformed entry no longer disables the repair for that project for
  ever.** A path containing a NUL byte raised an error the repair did not catch.
- **The Red River charts no longer show the “Full layout setup” label** (Knut,
  beta.17). The label means the patch-set editor has the chart's complete
  design; those six ship the page layout but not the colour-set design, so it
  overpromised. 115 of the 130 built-in charts carry it — the six Red River and
  the nine “by Pharmacist” charts do not.
- **The second patch-set warning is gone.** Ticking “Edit patch recipe (override
  preset)” already opens a window saying the loaded patches will be replaced,
  and that box is shown for a patch set you loaded yourself, not only for a
  built-in preset — so a second window at Generate time interrupted a decision
  you had already made (Knut).
- The landing page now says ChromIQ ships **130 ready-made chart presets**, and
  its embedded version metadata no longer claims 4.0.0.

### Also

- Three comments in the source described behaviour the code does not have,
  including one claiming the app tells you when it has repaired a project. It
  does not — for now that is a log line only, and the comment says so.
- An 842 KB stray backup file that a blanket `git add` had committed is removed,
  and that class of file is ignored from now on.

### Known, and deliberately not changed in this build

- A built-in ColorMunki preset warns that its own right margin is 0.055 mm below
  its declared minimum, and only when chosen through the ★ overlay. The printed
  chart is correct and the warning is accurate; the discrepancy is in the layout
  engine, not the check, so widening the check would hide it. Tracked as #167.

Gate: 7431 passed, 140 skipped, 2 xfailed.


## v4.1.3-beta.17

Knut's Red River presets, exactly as he sent them, and the repair for projects
whose files were split by the dotted-name bug.

### Fixed

- **The Red River presets are Knut's own again.** All six were replaced with the
  files he supplied, field for field: the markers-per-patch values he chose (5
  on the i1Pro charts, 7 on the ColorMunki A4 8-page, 3 on the rest), his
  ColorMunki margins, the clip band on the right with flip 180° for ColorMunki
  and on the left for i1Pro, and his 9-page ColorMunki charts in place of the
  10-page ones. The old six were removed entirely rather than edited.
  A test now reads his files from a fixture and checks every field, so a value
  cannot be changed by accident again — which is how the previous set drifted:
  a ruler-marks change wrote one markers-per-patch value across all six and
  overwrote the per-chart values he had measured.
- **“Full layout setup” is back on the preset list** — on every built-in except
  the nine “by Pharmacist” charts, which is the rule Knut asked for. It is added
  to the displayed row only, never to the preset's stored name: that name feeds
  both the suggested project-folder name and the key custom presets are matched
  against, so marking it there would have renamed 121 suggested folders and
  orphaned every custom preset already saved.

### Added

- **Projects broken by the dotted-name bug are repaired when you open them.**
  Charts built before beta.16 under a name containing a dot had their files
  written under two different names, which left the project unmeasurable.
  ChromIQ now puts those files back under one name on open, so sheets you have
  already printed stay readable and nothing has to be rebuilt or reprinted.
  It renames only files it can prove came from that bug — a truncated name, no
  file already holding the correct one, the run's own `.ti1` confirming the full
  name, and the strip file that only ChromIQ's own layout engine writes. Every
  rename is recorded in `name-repair.json` inside the project, so it can be read
  back or undone by hand, and the record is written before anything moves, so an
  interrupted repair finishes rather than restarting. Set
  `CHROMIQ_NAME_REPAIR=dry` to see what it would do without doing it, or `off`
  to switch it off entirely.
- **Preferences ▸ Chart Layout jumps to the density your layout is saved under**
  when you switch instrument, and says so underneath, instead of landing on the
  first density and showing factory defaults — which read as “my settings are
  gone” when they were one box away. The paper you are working on never moves.

Gate: 7426 passed.


## v4.1.3-beta.16

Knut's beta.15 review, plus four faults nobody reported — three of which were
losing or hiding data, and one of which has been shipping since 4.0.0.

### Fixed — data, and the ones that were never reported

- **A project name containing a dot split its files in half.** ChromIQ builds
  every file of a run from the project name, and in several places it worked
  that name out by asking Python to remove the extension — from something that
  has no extension. Python then reads “.0mm” in
  `…-Portrait-w10.0mm` as the extension and removes it, so the `.ti2`, the
  printable pages and the strip data were written under a shortened name while
  the `.ti1` kept the full one. **The project could not be measured**: chartread
  was handed a name whose `.ti2` did not exist. Duplicate Run was greyed out,
  and reopening the project showed no chart pages. **120 of ChromIQ's 130
  built-in charts suggest a name with a dot in it**, so this was the normal
  case, not an exotic one. Fixed in the chart builder, the scanner-target
  writer, the reference-file importer and the image writer — the last two of
  which also broke the scanner→profile flow outright, because ArgyllCMS's
  `scanin` builds those filenames by joining strings while ChromIQ predicted
  them by stripping extensions. There is now one rule, in `core/stem_paths.py`:
  artefact names are built by joining, never by guessing what part of a name is
  an extension.
- **Duplicating a run dropped 17 of the 27 things it records**, including all
  five settings groups and the patch-set editor's own state, which its own
  documentation says cannot be recovered from the chart file. A duplicate now
  carries everything that describes the files it copied. `per_target_settings.md`
  §6.3 had required this all along.
- **A duplicate lost the “this chart does not match this measurement” warning**
  while copying both the chart and the measurement — so it handed back a chart
  that did not describe the measurement beside it, silently.
- **The “Your duplicated run is ready” window had never once opened.** It raised
  on the way up because one placeholder in its text was never given a value.
  Present since 2026-08-01 and shipped in 4.0.0.
- After deleting a run, a duplicate's record of where it came from pointed at
  whichever run had since taken that number.

### Fixed — from Knut's beta.15 review

- **Keyboard shortcuts in tooltips now show the keys your own keyboard has.**
  ⌘ and ⇧ were written into the text on every platform; a Windows user was
  shown a key they do not have. All thirteen translations re-synced.
- **The Dictionary card sits beside the Keyboard shortcuts card again.** Adding
  three cards in beta.15 pushed it onto the row above.
- **The three cards that had no icon now have one.** They were not the wrong
  icons — nothing was drawn at all.
- **The help sentence on the profile-run bar is no longer cut in half** when it
  wraps to three lines, or laid over the buttons when it wraps below them. The
  cause was an ordering one: the bar's height was worked out before it was told
  how wide it would be, so it was always sized for the previous window width.
- **Choosing a built-in chart with no project open no longer creates a project
  you did not ask for.** The guard added in beta.15 was defeated one line
  earlier: choosing a preset fills the name box with the preset's own name, and
  the guard then read its own suggestion as the user's answer.
- **The i1Pro preset list is in order.** Its A4 block interleaved the 7.5 mm and
  8.0 mm charts; the Letter and A3 blocks already read paper → patch width →
  patch count, and A4 now matches them. No other family's order changed.

### Changed

- **Preferences opens in about 0.7 seconds instead of 2.3.** The cost was one
  preview being redrawn up to thirty times while a recipe loaded, and discarded
  twenty-nine times. It is shared with Create Chart → Manual and the layout
  editor, so every preset load anywhere in the app got the same time back.
- The clip-strip preview no longer keeps the height of whichever band you looked
  at last when it is empty.

### Note on the Red River charts

An earlier note in development claimed the ColorMunki charts printed a blank
stripe where the logo belongs, and that a flag had been changed to fix it. That
was wrong: the flag is not read for that instrument, the logo band was already
printing, and the change altered nothing. It was never released. Knut's updated
Red River presets have arrived and are not in this build — they are waiting on
two questions about his own files.


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
