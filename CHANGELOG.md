# Changelog

## v3.14.8-beta.52

- **"Restore Used Chart" now gives back the same chart, down to the patch
  order.** The stored copy holds no page images because the chart's own recipe
  can redraw them — but the shuffle seed the chart was really built with was not
  being read back, so redrawing dealt the patches out differently. The number
  the build actually drew is now what the rebuild uses, and there are tests that
  hold it to that.

- **Restoring a profiling run's chart redraws its pages again.** Only
  verification charts were rebuilt after a restore; a profiling run got its
  files back but the Create Chart preview stayed empty, so the obvious next move
  was to press Create Chart — which built a different chart over the restored
  one. Both run types now redraw straight after the restore.

- **A restore never moves your measurement aside.** The restored chart is
  exactly the chart that measurement was taken with, so redrawing its pages
  leaves the measurement, the profile and the individual reads where they are.

- **Creating a new chart in a run that already holds results says so.** Moving
  the old measurement and profile into the run's "old" folder is deliberate — a
  new chart no longer matches them, and nothing is ever deleted — but it used to
  happen without a word. The log now explains it as it happens.

- **The sentence next to the Profile-run boxes wraps instead of running over the
  version number.** It sits on its own line under the row now, so it stays
  readable at every window width.

## v3.14.8-beta.51

- **The margin warning now says which minimum it means** — "below the 28 mm
  minimum set for this chart" when you laid the chart out yourself, or "below
  the 38 mm instrument minimum" when the instrument's guideline applies. Both
  are measured against the printed margins exactly as before; only now it is
  clear which figure you are being held to.

- **The window that appears when a run already has a stored chart is rewritten.**
  The buttons are now "Replace stored chart" and "Keep stored chart" — the old
  names were long enough to be cut short and read as nonsense — and the text
  spells out what each choice does before you pick one.

- **"Restore Used Chart" explains both run types.** Its ⓘ described only
  verification runs; it now covers profiling first, then verification, and what
  is true of both. Its icon also follows the tab you are on instead of keeping
  the Measure tab's colour everywhere.

## v3.14.8-beta.50

- **Margins are still checked when you switch "Use instrument margins" off —
  against your own.** Beta 49 dropped those warnings altogether, which went too
  far: switching the guideline off declines the *instrument's* minimums, not
  the check itself. A chart laid out with your own margins is now measured
  against exactly those, so a printed margin that came out under what you asked
  for is still reported. With the guideline on, the per-instrument minimums
  from Preferences apply as before.

## v3.14.8-beta.49

- **"Save as Defaults" now keeps "Show overlay from existing measurement".**
  Switching it on and saving your defaults had no effect: the switch was not
  among the settings that button records, and it was also forced off every time
  the Measure tab was built — so even a saved value could not have brought it
  back. Both are fixed, in guided and manual mode alike. If you never asked for
  it, it still starts off.

## v3.14.8-beta.48

- **A chart built with "Use instrument margins" switched off is no longer
  judged against those minimums.** If you set your own margins with that switch
  off, the panel still warned that they were below the instrument's — a
  guideline you had deliberately declined. The measured numbers are still
  shown; only the warnings are gone, and only for charts that recorded the
  choice. Charts built with the switch on, and printtarg charts, are unchanged.

## v3.14.8-beta.47

- **A failed strip now opens one window, not two — which is why "Save Partial &
  Quit" appeared to do nothing.** The reading engine reports a failure as an
  event *and* prints ArgyllCMS's own message, and both were being treated as
  separate failures. The second window carried its own default answer, which
  quietly replaced the one you had just given: choose "Save Partial & Quit" and
  the measurement retried the strip instead and carried on. The printed line is
  now ignored while the engine is running, since the event says the same thing.
  With the separate ArgyllCMS chartread the printed line is still the source, as
  before.

## v3.14.8-beta.46

- **The reading-times area is now a frame of its own**, with a faint border, so
  it is clearly separate from the page controls just above it rather than
  appearing to contain them.

- **Its caption is on two lines** — "Strip reading times:" above "(15 patches)"
  — so it cannot run into the first strip's time on charts whose strips begin
  close to the page edge.

- **The frame insists on the height it needs**, so the large warning line
  underneath the times can no longer be squeezed away by the layout.

## v3.14.8-beta.45

- **A strip now makes one sound, not two.** A strip that was accepted but read
  too quickly sounded its "strip read OK" cue and the slow-down cue together.
  The cue is chosen once, where the verdict is known: slow-down when the strip
  was hurried, the ordinary strip cue otherwise. Switching the pace hint off
  still leaves you the strip cue.

- **The margin check judges your chart against the right instrument.** With the
  layout engine on, the panel was reading the instrument from the printtarg
  control — which is not even shown then — and falling back to the i1Pro. A
  ColorMunki chart was therefore measured against the i1Pro's 38 mm top and
  19 mm bottom minimums. It now reads the instrument the chart itself records,
  so the minimums are the ones set for that instrument.

## v3.14.8-beta.44

- **"Restore Used Chart" is now actually on screen for a profiling run.** The
  button worked for profiling in beta 42, but its visibility still followed the
  Verification date box, so it only ever appeared when Run type was
  Verification. It now shows for both run types — the date box still belongs to
  Verification alone.

## v3.14.8-beta.43

- **No window's buttons make a sound any more.** Pressing a button in the
  reading-speed window played the strip cue afterwards, as though the button
  had caused it. The cue now sounds when the strip lands, before any window can
  open — the same correction already made for the failure window. Every event
  is announced once, when it happens.

- **Choosing "Re-read Strip" goes back to reading that strip**, instead of
  showing the "All Stripes Read" window. The completion window is now held back
  whether it arrives while the reading-speed window is open or just after it
  closes, and it appears again as soon as the re-read is finished.

- **The reading times are set at normal text size**, and the panel always keeps
  room for the verdict line, which could previously be squeezed out.

- **Both engine comparisons read properly.** They were laid out as columns,
  which cannot line up in the info window's proportional font — first-row items
  wrapped and the headings drifted away from their answers. They are now two
  plain lists: what only the ChromIQ engine gives you, and what is the same
  either way.

- **ColorMunki page margins** now default to 30 mm at the top and 10 mm at the
  bottom for every page size, with 6 mm sides. Existing installations are
  updated automatically, except where you had set your own value.

## v3.14.8-beta.42

- **"Restore Used Chart" now works for profiling runs too.** Every profile run
  keeps a copy of the chart it was measured with, in its own `chart/` folder,
  saved the moment a measurement starts — so a measurement never stops
  describing a chart you still have. The button beside the Profile run puts
  that copy back; your measurement is never touched.

  Only the chart's own files are copied — never the measurement, the profile or
  ChromIQ's own book-keeping. The copy is taken before the measurement exists,
  so those could only be leftovers from an earlier read.

- **Starting a measurement with a different chart asks first**, exactly as it
  does for a verification, and offers a third answer: **Measure without
  changing the stored chart**, for trying a changed chart out. When you choose
  it, ChromIQ remembers that the stored copy no longer describes the run's
  measurement, and says so on the button — so a later restore can never quietly
  put back a chart that does not match.

  If you are averaging several reads, the question also points out that
  replacing the chart now would mean averaging readings taken from two
  different sheets.

- The button explains itself in each state: a new run says to create its chart
  first, and a run measured before this feature existed simply says it has no
  stored chart yet.

## v3.14.8-beta.41

- **Renaming a profile can no longer strand one of its own files.** If a file
  you had put in the folder yourself already carried the name one of the
  renamed files needed, that file used to be skipped — and it then kept its old
  name for good, while the profile quietly used the other one instead. The file
  you added is now kept and moved aside, with
  "_conflicted_at_renaming_procedure" added to its name, so nothing is lost and
  the profile's own files all end up correctly named. Renaming twice never
  overwrites a file already moved aside, and the rename dialog explains the
  case.

## v3.14.8-beta.40

- **"Skip Stripe" no longer promises something it cannot do.** Skipping asks
  ArgyllCMS for the next unread stripe, and that search wraps around — so when
  the stripe that just failed is the only one still unread, it comes back to
  that same stripe and nothing is skipped. In that situation the button is now
  **"Finish Without This Strip"**: it saves the stripes you have read and ends
  the measurement, and loading the chart again lets you continue from there.
  The window explains why the choice has changed. With every other stripe it
  behaves exactly as before.

## v3.14.8-beta.39

- **Both engine switches now show you what you are choosing between.** The help
  beside the chart-reading engine lists, side by side, what it gives you and
  what the separate ArgyllCMS chartread does — including the two rows where the
  older path simply cannot follow, with the reason: ArgyllCMS tells ChromIQ's
  own code the exact moment the instrument fires, which is what makes timing a
  swipe possible, and the separate program beeps on its own with no way to turn
  that off. The layout-engine help gained the same kind of table against
  printtarg, and both say plainly that the resulting chart is read and profiled
  identically either way.

## v3.14.8-beta.38

- **"All Stripes Read" is now always the last window.** Any strip window — a
  failed strip as well as a strip read too quickly — is dealt with first, and
  the completion window follows only when nothing more will be read. Choosing
  to retry or skip a strip goes back to measuring, with no completion window.

- **The measurement finishes with a summary.** Every version of the completion
  window now reports the total measuring time as hours, minutes and seconds,
  the average, fastest and slowest strip reading times, and the ten strips with
  the worst — that is, the fastest — reading times. Strips that failed are left
  out of the figures, since a failed scan has no reliable time to average.

- **The reading times survive turning the page.** On a multi-page chart the
  times for each page reappear as you move between pages; they are kept for the
  whole measurement and cleared when the next one starts.

## v3.14.8-beta.37

- **The reading-speed window can be put away for the rest of a measurement.**
  It now carries a "Do not show this message for the rest of the measurement
  session" box. Tick it and the window stays out of your way while you finish
  the chart — but the slow-down sound still plays, and the reading times and
  verdict under the chart still update, so you keep the feedback without the
  interruption. It comes back for your next measurement, because a different
  chart may need a different pace and that is worth seeing once.

## v3.14.8-beta.36

- **The reading times now sit under the strips they belong to.** Each strip's
  scan time is drawn beneath its own strip, turned a quarter-turn clockwise and
  reading downwards, aligned with the strip above it — so a chart with
  thirty-five strips across a landscape page still shows a time for every one.
  The patch count is stated once, on the left ("Strip reading times, 15
  patches:"), instead of being repeated against every strip, and the verdict
  line is centred underneath in its own colour. A strip that failed is listed
  with its time as well, marked so it reads as a failure.

## v3.14.8-beta.35

- **ChromIQ's own sounds are the only ones you hear now.** ArgyllCMS beeps from
  inside its reading code, and those beeps ignored the "Play sounds during
  measurement" switch, were absent from the Preferences list, sounded over
  ChromIQ's cue when a strip failed, and added an unasked-for noise when you
  pressed a button in the failure window. They are silenced, so every sound you
  hear is one you chose.

- **The strip-failure sound plays when the window appears**, not after you have
  dealt with it. It used to be queued behind the window itself, which is why
  Argyll's beep was all you heard. Pressing a button in that window makes no
  further sound — the failure has already been announced.

- **One window at a time on the last strip.** When the final strip was read too
  quickly, the "Strip Read Quickly" window and the "All Stripes Read" window
  opened together, with both sounds on top of each other. The pace window now
  always comes first and alone; the completion window follows only if you chose
  to keep the reading. Choosing to re-read goes back to measuring, with no
  completion window at all.

- **"Go to Build Profile Tab" and "Close" are now in every completion window.**
  The rename shipped in an earlier beta reached only one of the three windows
  that offer this step; all three now match, and a test pins them together so a
  future rename cannot land in one place only.

## v3.14.8-beta.34

- **A strip that was accepted but read too quickly now asks what you want to
  do.** ArgyllCMS only refuses a strip once it is unusable; between "fine" and
  "refused" lies a band where your readings are accepted but thin, and nothing
  used to mention it. When a strip falls in that band you now get the same kind
  of window a failed strip gives you, saying how long the strip took, how many
  milliseconds that left for each patch, roughly how many readings each patch
  received against the number you asked for, and what a comfortable time for
  that strip would be.

  It also explains why it matters: the instrument averages the readings it takes
  while passing over a patch, so fewer readings mean a noisier measurement, and
  that noise is carried into the profile you build from it.

  Your choices are **Re-read Strip**, which takes you back to that strip so a
  slower swipe replaces the hurried one, or **Continue Anyway**, which keeps
  what was read. Every figure comes from Preferences → Measurement, whose
  defaults are set for good-quality readings — lower the minimum readings per
  patch there if you would rather trade quality for speed, and the warning
  follows your setting.

## v3.14.8-beta.33

- **The cue now matches the fault when a strip fails.** ArgyllCMS reports a
  failed strip with its own wording, and only some of those failures mean you
  swiped too quickly. Each message is now classified: a hurried scan gets the
  "Slow down" sound, while a swipe that wandered off the strip, started or
  ended in the wrong place, or met the wrong light level gets "Strip read
  failed". "Too many patches" is treated as a hesitant swipe rather than a fast
  one — telling you to slow down there would be precisely the wrong advice.

- **Every strip now shows its reading time, whether it succeeded or failed**,
  with an explanation underneath that says what to try next: a slower swipe for
  a hurried strip, one smooth even movement for a hesitant one, or a check on
  where the swipe started and ended when speed was not the problem.

- **The numbers in those messages come from your own settings.** Change the
  readings per second or the minimum readings per patch in Preferences →
  Measurement and the advice changes with them, on the very next strip — the
  targets quoted are never fixed text.

- **Closing the window during an update check can no longer throw.** If the
  check finished after the window had gone, reporting the result raised an
  error inside the background thread — and so did the attempt to report *that*.
  There is nobody left to tell at that point, so the result is now simply
  dropped.

- **Preferences → Sounds now says which reading mode each patch sound applies
  to.** The patch tick and the "looks off" sound only apply to patch-by-patch
  reading: when you swipe a whole strip, the instrument reports the strip in one
  go once the swipe has finished, so there are no separate patches to sound as
  you go.

## v3.14.8-beta.32

- **Reading pace is judged per strip only.** Timing single patches in
  patch-by-patch reading told you nothing useful — pace only means something
  while you swipe a whole strip — so that calculation is gone.

## v3.14.8-beta.31

- **A strip that fails is now told when it was read too fast.** Argyll rejects a
  hurried scan with "Not enough patches", which says nothing about speed — so
  the natural response is to try again at exactly the same pace and fail again.
  ChromIQ now times the failed scan against the number of patches a strip holds
  and, when speed was the likely cause, says so plainly and suggests reading
  that same strip again more slowly. When the pace was fine it stays quiet,
  because a misread has other causes too — a crooked swipe, or the wrong strip.

## v3.14.8-beta.30

- **Reading speed is now shown on screen, and works for strip reading at
  last.** The pace feedback was built on a per-patch event that only exists in
  patch-by-patch reading — a strip-scanning instrument hands the whole strip
  back when the swipe ends, so nothing was ever timed and nothing was ever
  shown. The engine now reports the moment the instrument fires, which is the
  true start of a swipe, and each strip is judged on the time that scan took
  and the number of patches in it — the same two numbers the thresholds were
  derived from.

  Under the chart preview you now see the strips read so far with the time each
  scan took, and one large verdict line: green when the pace is comfortable,
  amber when it only just made it, red when it was faster than the instrument
  can properly manage, always with the milliseconds per patch and what to aim
  for. It clears itself for a fresh read.

- **The measurement-finished sound plays when the measurement finishes**, before
  you are asked what to do next, instead of after you had chosen. It sounds once
  per read.

- **The pop-up after a measurement says what its buttons do.** "Build Profile"
  became "Go to Build Profile Tab", since that is all it did — the profile is
  still built by you, on that tab. There is also a Close button now, for
  keeping the measurement without going anywhere.

- **The chart's file tooltip stays out of the way of hovered patch values.**
  With "Show patch values on hover" switched on, the path tooltip no longer
  pops up over the value you are reading.

## v3.14.8-beta.29

- **Fixes the overlapping bar introduced in beta.26.** Switching Run type to
  Verification could leave the labels, boxes, buttons and information icons
  piled on top of one another until a few more changes happened to sort it out.
  The bar sits on a hand-placed rail, so nothing was re-laying it when its own
  content changed — it kept the width it had before the extra boxes appeared,
  and with boxes that now hold their width, the only place left for them to go
  was on top of each other. The masthead now notices the moment the bar's
  content changes, whatever caused it, so it is correct on the very first
  change and at startup.

- **The bar gives way gracefully on a narrow window.** If the rail cannot hold
  the row at its comfortable width, the widest box gives up width first, down
  to a point where it is still readable, instead of running under the version
  number. Widen the window and the full width comes straight back.

- The folder line beneath the bar is shortened in the middle when space is
  tight, rather than forcing the whole bar wider. The full path stays in its
  tooltip.

## v3.14.8-beta.28

- **Every instrument in Preferences → Measurement now explains its own two
  numbers.** Each row has an ⓘ that says why that instrument's readings per
  second and minimum readings per patch are what they are, and works the figure
  out in front of you from a real chart — how many patches fit on a strip, how
  long a strip takes to read at a sensible pace, and what that leaves for each
  patch. The ColorMunki explains why it genuinely needs slow reading, the
  i1Pro 3 why its extra speed is spent on quality instead, the i1Pro 3 Plus why
  it asks for the most readings per patch of any of them, and the SpectroScan
  why it has no threshold at all.

  The closing line of each explanation is worked out from the values ChromIQ
  actually ships, so an explanation can never quietly fall out of step with the
  setting it describes.

- The rows on that tab also keep their boxes to a sensible width, so the new
  ⓘ sits beside each row instead of being squeezed off the edge.

## v3.14.8-beta.27

- **No button anywhere can paint its label clipped any more.** Every button in
  ChromIQ is switched to the monospace label font as it appears, and that font
  is wider than the one the button measured itself with — so a long label could
  be cut off at both ends, as it was on the new verification chart warning.
  Button widths are now decided in one shared place, which measures the label
  in the font it will really be painted in, and every button in every window
  and pop-up goes through it. The two places that worked their width out for
  themselves now use it too, so this cannot come back one dialog at a time.

## v3.14.8-beta.26

- **The Profile-run bar keeps still.** It is now anchored just to the right of
  the "PRINTER PROFILING" tag instead of being centred, so it no longer slides
  sideways whenever its content changes — switching Run type simply adds the
  verification boxes on the right, and nothing already on screen moves.

- **Every box is wide enough to read, and stays that width.** The Verification
  box could come up too narrow to read its entry, the Run and Run-type boxes
  could show "Run 1 (overwr…", and the "Restore Used Chart" button could render
  with its label cut off at both ends — then quietly correct itself on a later
  visit. Each box is now measured against the widest entry it can ever show,
  using the width its own style really leaves for text, and re-measured when
  the theme or font changes. A verification date gaining a measurement, or
  moving between tabs, no longer changes any width.

- **Tooltips no longer appear clipped or half empty.** All tooltips share a
  single label, and a size worked out for a long tooltip stayed on it: the next
  tooltip was then shown in the wrong box — too small for a longer text, far
  too large for a shorter one — and hovering back and forth appeared to fix and
  re-break it at random. Each tooltip is now sized from scratch.

- **The selection is shown but locked on Build Profile and Check & Refine.**
  Both tabs work on the measurement file you load into them, not on this
  selection, so changing it there looked as though it did nothing. It stays
  visible so you can see where you are, and each box explains that it can be
  changed on the Create Chart, Print Chart and Measure tabs.

- **"Where are my files?" now lists the verification chart copy.** The Files
  Relating to Features table said a verification writes its measurement and its
  report; it now also names verifications/<date>/chart/, the copy of the chart
  that check was measured with.

## v3.14.8-beta.25

- **The verification chart warning now points at the Verification field
  instead of acting for you.** Starting a new dated verification run is what
  the "Verification" field is for, so ChromIQ no longer offers to move your
  measurement to a new date from inside the warning. When the loaded chart
  differs from the one a chosen date was measured with, the warning explains
  what would be replaced and suggests the way out: set "Verification" to
  "New verification" and start the measurement again. Your two answers are to
  replace the stored chart deliberately, or to cancel.

- **One runner for the whole issue-130 test plan.** `scripts/drive_130.py`
  drives the real application through all 23 rows — the nine load-model
  scenarios and the fourteen verification rows — and prints a single table.
  Each half can still be run on its own.

## v3.14.8-beta.24

- **The Profile-run bar keeps its boxes together on the left.** The boxes and
  their labels were being spread across the whole width, so a label could sit a
  long way from the box it belongs to. They now stay left-aligned and in
  sequence, and switching "Run type" to Verification simply adds its boxes on
  the right instead of pushing the others apart.

- **Starting a measurement can no longer replace a stored verification chart
  without asking.** Every verification date keeps its own copy of the chart it
  was measured with — the copy "Restore Used Chart" puts back. Measuring a
  different chart into that same date used to overwrite that copy silently,
  which left the earlier result describing a chart nobody still had.

  ChromIQ now compares the loaded chart against the stored one, using the same
  content check that "Restore Used Chart" uses, and asks first. You can measure
  into a new verification date, which keeps both the earlier check and today's
  reading; replace the stored chart deliberately; or cancel. Re-measuring the
  very same chart is never interrupted — the question appears only when the two
  charts really differ.

## v3.14.8-beta.23

- **The pace warning now knows exactly which instrument you are using.** Every
  instrument takes a fixed number of readings per second — a ColorMunki takes
  50, an i1Pro 2 takes 200, an i1Pro 3 takes 400 — so the same swipe gives one
  of them eight times more light than another. ChromIQ now asks the instrument
  what it is when the measurement starts and uses that model's own figures.
  This distinguishes the i1Pro generations from one another, which the chart
  alone cannot do, so measuring an older chart with a newer instrument is judged
  by the instrument you are actually holding.

  If the instrument cannot be identified, the slowest i1Pro rate is assumed —
  never a faster one, which would let a hurried swipe pass unnoticed.

- **New Preferences → Measurement tab.** One row per instrument, with its
  readings per second and the fewest readings you want each patch to get. The
  defaults suit each instrument out of the box; raise the minimum for more
  careful measurements, or set it to "Off" to silence the warning for that
  instrument. The SpectroScan is off by default: it is a motorised table that
  places the head on each patch, so there is no swipe that could be too quick.


## v3.14.8-beta.22

- **ChromIQ now tells you when you are swiping too fast — before the strip is
  rejected.** Reading a strip too quickly is the commonest reason a scan fails,
  and ArgyllCMS only says so *afterwards*, once the strip has to be read again.
  ChromIQ times each patch as it is read, and after a strip that was accepted
  but read close to the limit it says so in plain language, for example:
  *"That strip was read quickly: 29 ms per patch. Aim for at least 100 ms per
  patch — a slower, steadier swipe gives the instrument more light to work with,
  and is read more accurately."* A strip read at a comfortable pace says nothing
  at all.

  If you have set your instrument's sampling rate in Preferences, the hint also
  estimates how many light samples each patch received — the figure the
  instrument itself never reports. Without that rate ChromIQ speaks only in
  milliseconds rather than inventing a sample count.

  The hint can be switched off, and its threshold changed, in Preferences.


## v3.14.8-beta.21

- **Fixed a rare crash at the end of a profile build.** When the ChromIQ profile
  engine finished, ChromIQ let go of the background worker a moment too early —
  while it was still shutting down. Most of the time nothing came of it, but if
  the timing was unlucky the whole application could close without warning as
  the build completed. It now holds on until the worker has genuinely stopped.

- **Restoring a verification chart now redraws its printable pages for you.**
  The stored copy of a chart deliberately holds no page images — they are
  redrawn from the chart's own layout information, which keeps the stored copy
  small. That redraw now happens automatically as part of the restore, using the
  settings the chart was originally made with, so the sheet matches the one that
  was measured. You are only asked to do something in the one case where it is
  genuinely impossible: a chart made without any layout information *and*
  without stored page images.

- **A verification date that has no measurement now says so.** If a verification
  measurement is cancelled or fails, its dated folder is kept — it already holds
  a copy of the chart, which you may still want to restore — and the Verification
  dropdown labels it "— no measurement yet", so an empty date is never mistaken
  for a result.

- **The "Where are my files?" guide covers the stored charts.** It explains what
  `runs/runN/verifications/<date>/chart/` is, that ChromIQ saves it automatically
  when a verification measurement starts, and that "Restore Used Chart" puts it
  back without ever touching your measurements.


## v3.14.8-beta.20

- **Every verification now remembers the chart it measured.** When you start a
  verification measurement, ChromIQ keeps a copy of the verification chart it is
  about to measure inside that verification's own dated folder, at
  `runs/runN/verifications/<date>/chart/`. Nothing is moved and nothing is
  deleted — it is a copy, taken before the measurement writes anything.

  This matters because a run has one verification chart, shared by every
  verification you have ever measured against it. Change that chart and your
  older results quietly stop describing a chart you still have. Now each set of
  results keeps its own chart alongside it.

- **New button: "Restore Used Chart".** It sits next to the Verification date
  and puts back the chart that date was measured with — so old results make
  sense again, and you can reprint exactly the same sheet. It becomes available
  once you pick a verification date that has a stored chart, and tells you why
  when it cannot be used. Your measurements are never touched: only the chart
  files are replaced, and if the chart currently in place is a different one you
  are asked first.

  The restore is all-or-nothing. If anything goes wrong part way through, your
  existing chart is put back exactly as it was rather than left half-replaced.
  A chart restored into a project you have since renamed comes back under the
  project's current name.

- **Starting a verification measurement on "New verification" now creates that
  dated folder straight away** and moves the Verification dropdown to it, so you
  can see where the measurement is going from the moment it begins.

## v3.14.8-beta.19

- **The bar now tells you which folder you are working in.** Under the Profile
  run and Run type selectors there is a new line — *"Location being edited:"* —
  showing the exact folder your current selection reads from and writes to,
  written out from your ChromIQ folder down, for example
  `ChromIQ/My-Printer/runs/run1/` or, with Run type set to Verification,
  `ChromIQ/My-Printer/runs/run1/verifications/`. It follows both dropdowns as you
  change them, so you can always see where your files are going before you do
  anything. It appears as soon as you have typed a profile project name — you do
  not have to create the chart first — so you can check the destination before
  anything is written. A profile project kept in sub-folders shows its real
  place, and "New run" shows the folder that would be created.

- **The profile project name you typed is no longer overwritten.** Switching Run
  type or Profile run could replace whatever you had typed in "Printer profile
  project name" with an automatically generated name such as
  `Printer_Paper_Type_Instr_2026-07-25_23-26`. That happened because several
  parts of the app asked for "the current name" through a call that quietly
  invented one whenever none had been set, and then wrote the invented name into
  the field. Those places now simply leave the field alone until a profile
  project genuinely has a name, so what you type stays put.

- **Replacing a verification chart now keeps everything else.** Choosing to
  replace when Run type is Verification only ever touches the verification chart
  itself: it moves to `runs/runN/verifications/old/`, and your dated
  verification results stay exactly where they are. Previously the dated results
  were archived as well, and everything landed in the run's own `old/` folder
  one level too high. Nothing was lost either way — this puts things where you
  would look for them.

- **Replacing a profiling chart now archives the whole run.** When you replace a
  run's chart, its measurement, printer profile and every folder inside that run
  — reports, exports and verifications included — move together into
  `runs/runN/old/`. They describe the chart that was there before, so they travel
  with it rather than being left behind to look current. Nothing is deleted.

- **Building into a run you already have always asks first.** The New-vs-Replace
  question no longer waits until the run holds a measurement or a profile: any
  build into an existing run offers to replace it, build a new run instead, or
  start a new project. Only "New run" goes straight through.

- **Printing or measuring with "New run" selected now explains itself.** Both
  buttons used to fail obscurely, because "New run" names a run that does not
  exist yet and so has no chart. They now tell you to pick an existing run, and
  list every way to create a new one.

## v3.14.8-beta.18

- **The applause completion sound is now a real recording.** Synthesising a
  convincing crowd turned out to be the wrong tool for the job: the first
  version sounded like static, and a rebuilt one — denser, with room
  reverberation — sounded like fireworks. Measuring a real applause recording
  afterwards showed why. It has *more* silence between claps and sharper peaks
  than the "improved" synthesised version, so the problem was never how the
  claps were arranged; it was the sound of a single clap. Filtered noise is a
  hiss, while a hand clap is a burst of air from a cupped cavity. The applause
  is therefore a genuine recording, dedicated to the public domain under CC0 —
  no attribution required and no licensing strings attached. Its origin and the
  processing applied to it are recorded in `assets/sounds/CREDITS.md`, and it is
  the only sound in the pack that is not generated by ChromIQ's own script.

- **The chart layout's sheet text now says "Printer profile project name".**
  One stale use of the old wording survived in the list of placeholders you can
  put on a printed sheet. It is the same rename already applied everywhere else,
  so that one term means one thing throughout the app.

## v3.14.8-beta.17

- **Projects kept in a sub-folder of your ChromIQ folder now stay where they
  are.** This was one bug behind several confusing reports. Opening such a
  project worked, but the moment anything re-applied its name — the "Printer
  profile project name" field, a preset, or clicking Create Chart — ChromIQ
  quietly switched to `<ChromIQ folder>/<name>` and created an empty duplicate
  project there. Everything you did next (importing a chart, replacing a
  verification chart, adding a run) went into that invisible duplicate, so it
  looked as though nothing had happened at all: no folder created, the loaded
  `.ti2` "not put anywhere", the verification chart not replaced. A project now
  keeps its real location for as long as its name still refers to it; typing a
  genuinely different name still starts a new project directly in your ChromIQ
  folder, exactly as before.

- **Loading a patch set now follows the Profile-run bar.** "Load .ti1" →
  "Add to this project" built the chart into the project's most recent run
  instead of the run the bar showed, so the chart appeared in a run you hadn't
  selected.

- **Making a verification chart no longer costs you the run's profiling work.**
  A verification chart is laid out at the run root before it is filed under
  `verifications/`, and only the plain Create Chart path protected what was
  already there. Loading a preset or a patch set with Run type = Verification
  therefore wiped that run's profiling chart — it was simply gone when you
  switched Run type back to Profiling. All four ways of building a chart now
  protect it, and the run's measurement (`.ti3`) and printer profile
  (`.icc`/`.icm`) are protected too, so a finished profile no longer disappears
  into `old/` when you make a verification chart.

- **Building a patch set into a run that already holds work now asks first.**
  You get a clear choice — replace that run, build it as a new run instead, or
  start a new project — with each option naming exactly which folder the
  displaced files move to. Replacing archives the same things a chart import
  does (`runs/runN/old/`, never deleted). A run that is still empty stays a
  single click, as before.

- **Chart-import pop-ups now name the exact destination folder,** e.g.
  `runs/run1/old/` and `runs/run1/verifications/`, instead of just "the folder
  `old/`" — and the "Create a new run instead" option now says plainly that the
  new run is created inside the project you already have open.

- **The drumroll and applause completion sounds have been rebuilt.** Both were
  synthesised as flat noise, so they came out as static rather than a drum roll
  and clapping. The drumroll is now a real sequence of snare strokes that speeds
  up and swells into a final accented hit, and the applause is built from
  individual claps.

## v3.14.8-beta.16

- **Check & Refine gamut comparison now keeps your 3-D rotation when you switch
  views.** Rotating the shape and then switching between Profile A, Profile B and
  Combined snapped the view back to the start each time, because each view is a
  separate 3-D scene that gets reloaded. The rotation is now carried across the
  switch, so the shape stays exactly where you left it — making it much easier to
  compare two profiles from the same angle. (Completes the gamut-compare fixes
  started in beta.15.)

## v3.14.8-beta.15

- **The "chart already has a measurement" pop-up now appears only on the Measure
  tab.** It was popping up over Create Chart and Print Chart too — when you
  opened a project that had a measurement, or changed the Profile-run / Run-type
  bar — because the Measure tab listens for charts loaded elsewhere. It now only
  offers the overlay when the Measure tab is actually on screen. (The persistent
  "Show overlay from existing measurement" checkbox is unchanged.)
- **Check & Refine gamut comparison keeps your opacity and saturation when you
  switch views.** Switching to profile A or B and back to Combined re-loaded the
  3-D scene at its default transparency/saturation while the sliders still showed
  your values — so it looked wrong until you nudged a slider. The view now
  re-applies your current slider values immediately after the switch.
- Added a first batch of automated conformance checks for the unified
  file-handling model (internal; findings for review are tracked on the issue).

## v3.14.8-beta.14

- **See how a print turned out without measuring it again (#134).** When a chart
  already has a measurement, the Measure tab can now paint that measurement onto
  the patches in the preview — each patch split between the colour the chart
  *expected* and what your instrument actually *measured*, with the far-off ones
  outlined. Turn it on with the new "Show overlay from existing measurement" box,
  which appears whenever a measurement (`.ti3`) is found for the loaded chart.
- **Loading a chart that already has a measurement now offers both choices up
  front.** Instead of a plain yes/no, a friendly dialog lets you tick "Show it as
  an overlay" and/or "Refine / resume this measurement" — with a clear warning
  that starting a fresh measurement without resume will *replace* the existing
  one. Your last choice is remembered.
- **A mid-chart instrument hiccup no longer throws away the strips you already
  measured (#134).** If ChromIQ's own measuring engine fails partway through a
  chart, it now continues on ArgyllCMS's chartread *resuming from where you left
  off* — keeping every strip already read — instead of ending the run. The
  partial measurement is backed up first, so your readings are safe no matter
  what. (When nothing had been measured yet, it still restarts cleanly as before.)
- The scanner-profiling checkbox in the "All Stripes Read" dialog now shows the
  tab's own accent colour when ticked or hovered, instead of the system blue.
- All of the above is fully translated into every supported language.

## v3.14.8-beta.13

- **Loading a chart (`.ti2`) from a sub-folder project now opens it in place too.**
  In beta.12 the Create Chart "Load profile" button learned to recognise projects
  organised in sub-folders of your ChromIQ folder; the Print Chart / Measure
  "Load chart" buttons now do the same — a chart inside a nested project is
  recognised as one ChromIQ manages (Open / Continue) instead of being offered as
  an external whole-project copy.

## v3.14.8-beta.12

- **Presets now build into the run you selected.** With "Overwrite run N" chosen
  in the Profile-run bar, picking a built-in "by Pharmacist" preset (or a TC9.18
  / Spyderprint preset) built the chart into the project's *last* run and
  overwrote it, ignoring your selection. Both now honour the bar — the chart
  lands in the run it shows ("Overwrite run N", or a fresh run for "New run").
  Together with beta.10's archiving, a preset can no longer overwrite the wrong
  run or destroy its results.
- **Projects can live in sub-folders of your ChromIQ folder.** Opening a project
  nested several levels deep now recognises it as one ChromIQ manages and opens
  it in place — no more "copy it into your working folder" prompt for a project
  that's already inside the ChromIQ folder. (A project truly outside still offers
  the copy-in.) The nested location is remembered across restarts.
- **The Measure tab now warns before verifying a run with no profile.** The
  "build a profile first" / "make a verification chart first" guidance now keys
  off the Profile-run bar, so it fires reliably (it previously missed the case
  where the loaded chart was a verification chart).
- **The "no chart yet" guidance now appears in the Print and Measure tabs too**,
  not just Create Chart — so wherever you are, it tells you where to make the
  missing chart.
- The empty-preview guidance names the actual button, "Generate Chart".

## v3.14.8-beta.10

More fixes from Knut's #130 testing:

- **Regenerating a chart can no longer delete a run's measurement or profile.**
  Building a new chart into a run that already had a measurement (`.ti3`) and
  profile (`.icc`) used to delete them; now they're archived to the run's
  `old/<timestamp>/` folder first — finished results are never destroyed. (Only
  runs that actually have results archive; iterating on a not-yet-measured chart
  doesn't create `old/` folders.)
- **Clearer wording.** The vague "tick an unlock box in Create Chart" (and two
  related hints) now name the exact checkboxes: "Edit patch recipe (override
  preset)" and "Edit page layout (override preset)".
- **Name field updates when a project is copied in.** Copying a whole project in
  from a Print/Measure chart load now updates the "Printer profile project name"
  field, so the new project is visibly loaded in Create Chart.

## v3.14.8-beta.9

More fixes from Knut's #130 testing:

- **Switching Run type now updates the printtarg parameters too.** Previously the
  preview swapped between a run's profiling and verification charts but the
  printtarg settings frame kept showing the last preset's values. Each chart now
  remembers its own printtarg settings, so toggling Run type shows the settings
  that actually made the chart on screen. (Engine charts already did this via
  their layout recipe; this is the printtarg-chart counterpart.)
- **Loading a patch set into a new project now asks for the name.** Choosing
  "Start a new project" when you load a `.ti1` prompts for the project name
  (pre-filled from the file, editable) like creating any new profile project, and
  then loads it — the "Printer profile project name" field updates so you can see
  the new project is active.

## v3.14.8-beta.8

Fixes from Knut's beta-6/7 testing (#130):

- **A verification chart no longer eats the profiling chart.** Generating a
  verification chart into a run kept the profiling chart safe at the run root —
  the verification chart now lives only in `runs/runN/verifications/`, and the
  two coexist as intended.
- **The empty preview now guides you.** When you switch to a Profile-run /
  Run-type that has no chart yet, the preview explains what to do — for a
  verification, "keep Run type = Verification, set up the chart and click Create
  Chart, then print it through your profile and measure it"; for a profiling run,
  "set up the options and click Create Chart" (with a note if files were moved or
  deleted). It clears the moment a real chart appears.
- **Opening a project from outside your working folder no longer happens
  silently.** "Load profile" on an external project now offers to copy the whole
  project into your working folder, then opens the copy — matching the unified
  load strategy.
- **The Profile-run dropdown is wider** so "Run N (overwrite)" is fully readable.
- The Measure tab's "Play sounds during measurement" tooltip icon now sits at the
  right of the panel.

## v3.14.8-beta.7

Measurement sound feedback — Phase 1 of #131. ChromIQ can now play a short
sound as you measure, so you can follow a read hands-free without watching the
screen. (This beta also includes everything from beta.6, the #130 unified
file-handling model.)

- **A new “Play sounds during measurement” switch on the Measure tab.** With it
  on, ChromIQ plays a tick as each patch is read, a bell when a strip is
  finished, a distinct sound if a reading looks off, a warning on an instrument
  error, and a fanfare when the whole chart is done. Argyll's own “Slow Down!”
  after a too-fast swipe gets its own calm cue. A sound also plays when a
  profile finishes building.
- **A new Preferences → Sounds tab** to choose which sound plays for each event,
  in two groups (measurement actions and action completion), each with a “Play”
  button to hear it. Pick “Off (no sound)” for any you'd rather keep silent.
- **Bring your own sounds.** Every dropdown is built from the `.wav` files
  present in a sounds folder, so it grows if you add your own. Point Preferences
  → Paths at a folder with `measurement-events/`, `slow-down/` and
  `task-complete/` sub-folders. ChromIQ ships a small built-in set so it works
  out of the box.
- Works on the ready-to-use macOS, Windows and Linux bundles; if a machine has
  no working audio, sounds simply stay silent and never interrupt a measurement.

Also fixed (from driving the #130 test plan through the app):

- **Single-page verification charts now preview.** Generating a verification
  chart that fits on one page left its page image at the run root instead of
  moving it into `verifications/`, so switching Run type to Verification showed a
  blank preview (and Print/Measure got no chart). The single-page TIFF now moves
  with the rest of the chart.

Notes: the per-patch “reading looks off” sound uses the ChromIQ reading engine
(on by default). Live measurement-speed feedback is Phase 2. New strings ship as
English placeholders in the non-English catalogs for this beta; full translation
follows before the final release.

## v3.14.8-beta.6

This beta completes the unified file-handling model for the verification-runs
work (#130): opening any chart, patch set or profile now routes through one
clear, explaining pop-up and always follows the shared **Profile-run / Run type**
bar. Nothing is ever silently overwritten or deleted.

- **Loading a chart (`.ti2`) now always explains what will happen first.**
  Whether you pick a loose chart, a chart from inside the loaded project, one
  from another project, or a complete project folder, ChromIQ shows a pop-up
  headed by the current bar state ("Since **Profile run** = … and **Run type** =
  …, the following actions are available:") and lists each option with its exact
  consequences and file paths, plus Cancel. Profiling loads the full chart set
  into the run; Verification files a verification chart under the run's
  `verifications/` folder; and choosing **Overwrite → Replace** moves every
  displaced file — including the whole `verifications/` tree — into a dated
  `old/` folder rather than deleting it.
- **Loading a patch set (`.ti1`) is bar-aware too.** With a profile project open,
  ChromIQ asks whether to lay the patches into that project (Create Chart then
  follows the bar) or start a new project named after the file — instead of
  quietly renaming your project.
- **Opening an older profile is explained before it's updated.** Reopening a
  project made by an older ChromIQ shows a friendly, one-time note that the
  folder is being brought up to the current layout — safe, in place, nothing
  deleted.
- **"No verification chart yet" guidance.** Starting a verification on a run that
  has a finished profile but no verification chart now stops and walks you
  through creating one, distinct from the "build a profile first" message.
- **Reports are saved in the right place.** An exported report PDF now lands at
  the tightest folder that still contains everything it covers: a single
  profiling run's own `reports/`, a single verification's dated
  `verifications/<date>/reports/`, or the whole profile's `reports/` (next to
  `runs/`) for the all-runs trend view.
- **Clearer naming: "Printer profile project name".** The Create Chart name field
  is renamed to make plain that it names the whole project (the folder and every
  file's base name), distinct from the printer profile itself (the `.icc`/`.icm`
  file it produces). The Dictionary gains entries for the project name, the
  profile file, a profile run, run type and the `old/` folder.
- **The run/type bar is honest when no project is loaded.** With nothing open the
  Profile-run and Run-type controls are greyed out with a short hint, and light
  up the moment you create or open a project.
- **The Create Chart presets button is a list icon** (it previously read as a
  favourites star), and the guided help describes it accordingly.

## v3.14.8-beta.5

More fixes from Knut's testing of the verification-runs work (#130):

- **Create Chart builds into the run you selected.** The chart is now written to
  the folder the shared bar shows: **Overwrite run N** rebuilds that run;
  **New run** creates a fresh `runs/runN+1/` (and, with Run type = Verification,
  files the chart under that run's `verifications/`). The bar defaults to the
  loaded project's current run — on load, on session restore, and after each
  build — so a plain **Generate** overwrites the current run instead of piling
  up new ones.
- **Clearer "build a profile first" guidance.** Starting a verification on a run
  with no profile yet now shows a numbered, step-by-step message that uses the
  correct **Run type = Profiling / Verification** labels (instead of the old
  "Profile verification OFF" wording) and names the run folder, the profile
  file, and the dated `verifications/` folder.

## v3.14.8-beta.4

Two more fixes from Knut's testing of the verification-runs work (#130):

- **Loading a preset refreshes the preview right away.** The chart-layout panel
  applied a preset's settings silently, so the clip-border content and the
  strip/patch layout kept showing the previous recipe until you nudged a field
  by hand. It now does one consolidated refresh at the end of a preset/recipe
  load, so the preview matches what you loaded immediately.
- **Print and Measure always follow the selected Profile run + Run type.**
  Switching Run type now reliably swaps Create Chart to that target's own chart
  and pushes the matching chart to the Print and Measure tabs. If the selected
  target has no chart yet, the previous chart is cleared from all three tabs so
  the wrong chart can never be printed or measured.

## v3.14.8-beta.3

Fixes from Knut's beta-2 test of the verification-runs work (#130):

- **The "Where are my files?" guide now covers verification runs.** It explains
  the new `runs/runN/verifications/` area — the shared verification chart and
  the dated per-check sub-folders — splits the Measure step into profiling vs
  verification, and adds a dedicated "Verification runs" section, so the guide
  matches how files are actually laid out now.
- **The chart preview no longer sticks on a phantom extra page.** Regenerating a
  *smaller* verification chart (fewer pages) used to leave the previous chart's
  extra page behind, so the preview kept showing an out-of-date page count. The
  old verification-chart files are now cleared before the new ones are saved —
  your dated verification history is untouched.
- **Switching Run type swaps the chart in Create Chart.** Changing between
  Profiling and Verification (or picking a different Profile run) now loads that
  target's *own* chart — its settings and its preview — so your edits and the
  next Generate apply to the right chart instead of overwriting the other one.
- **i1Pro bottom margin corrected for the tall sheets.** For i1Pro on
  **A4 Portrait** and **A3 Landscape**, the default bottom margin is now 19 mm
  (was 9 mm), keeping the strip under the i1Pro 240 mm strip-length limit;
  Letter Portrait is unchanged. Existing settings are migrated automatically,
  and a bottom margin you set yourself is kept.

## v3.14.8-beta.2

- **Verification runs — check a finished profile, and keep a history (#130).**
  ChromIQ now cleanly separates *profiling* (building a profile) from
  *verification* (checking a finished one). A verification is a chart printed
  *through* the profile with colour management **on**, then measured to see how
  accurate the profile still is — and each check is filed in its own dated
  folder, so you build up a history and can watch a profile hold up, or drift,
  over time. A verification never overwrites your profiling measurement and
  never builds a profile.
- **A shared "Profile run / Run type" bar, in the masthead.** A compact bar now
  sits on the masthead, centred in line with the "Printer Profiling" wordmark
  and the version number. **Profile run** picks which build you're working on
  (or a new one); **Run type** switches between Profiling and Verification; a
  third box appears for verifications so you can start a fresh dated check or
  re-measure an earlier one. The choice stays in step across Create Chart, Print
  Chart and Measure, and its highlight follows the active tab's colour.
- **Profiling and verification reports never mix.** The Measurement Report
  trends verification measurements entirely separately from the profiling run
  that built the profile. Report titles and file names are now configurable in
  **Settings → Reports** (separate profiling / verification wording, with an
  optional profile name); the first-page title carries no date, the file name
  does.
- **"Build a profile first" guidance.** Choosing Verification on a run that has
  no profile yet gently guides you to build one first and switches the type back
  to Profiling — nothing is created until you actually measure.
- **A verification help card.** The "?" help gains a step-by-step
  *"Check a finished profile"* walk-through, in all twelve languages.
- **Show or hide the startup splash screen.** A new **Settings → General**
  option turns the startup splash on or off (on by default) — turn it off for a
  quieter launch. Translated into all twelve languages.

## v3.14.8-beta.1

- **Red River Paper vendor presets (built-in).** A new *Red River Paper* group
  in Create Chart → Manual → Presets ships six ready starting points built on
  one shared, locked verification patch set: **i1Pro** A4 / Letter (4 pages) and
  **ColorMunki** A4 / Letter in a compact 8-page cut and a ruler-size 10-page
  cut. Each lays out "chart-area-first" (so the page margins are respected) with
  the i1Pro strips kept under the 240 mm jig ruler, and carries a Red River /
  ChromIQ logo band in the clip border. The patch set is locked (targen is
  greyed) while the page layout stays fully editable.
- **Editing the patch recipe drops the vendor branding.** Ticking *"Edit patch
  recipe"* on a vendor preset reverts the clip band to ChromIQ's own notes
  record and removes the vendor name from the sheet-edge stamp — once the set can
  be changed it is no longer the vendor's certified set, so nothing on the chart
  still names them.
- **A startup splash screen.** The Chrom/IQ wordmark underlined by the
  full-width spectrum bar, in light or dark to match your theme, shown while the
  app starts.
- Fixed: the "last page not quite full" hint no longer appears for a
  fixed-patch-set preset (adding/removing patches doesn't apply to a locked
  set), and the clip-border-vs-margin warning outline no longer sits on a
  greyed-out (instrument-margin-locked) margin box where it looked like a stuck
  focus ring.

## v3.14.7

- **The chart-reading engine can now also drive XY tables and chart readers
  (opt-in).** Motorised XY tables (the GretagMacbeth SpectroScan) and autonomous
  chart readers (the X-Rite i1iSis and DTP70) previously always used Argyll's
  chartread. A new **Settings → Beta** option, *"Also drive XY tables and chart
  readers with the engine"*, lets the ChromIQ engine measure them too — filling
  in the expected-vs-measured preview as sheets are read and saving after every
  sheet. It is **off by default**: these instruments are rare and the new path
  has not yet been tested on real hardware, so unless you turn it on they keep
  measuring exactly as before. With the engine's own strip and patch modes, that
  makes the engine cover every interactive reading mode.

## v3.14.6

- **Patch-by-patch measuring now autosaves after every patch.** Previously a
  patch-by-patch session only wrote its measurement file at the very end, so an
  interrupted read (an unplugged instrument, a crash) lost everything you'd
  scanned. It now saves after each patch — exactly like strip reading does after
  each strip — so you can always resume from the last patch you measured.

## v3.14.5

- **Patch-by-patch measuring now has the full live preview.** When you measure
  a chart one patch at a time (Measure → Manual → “Patch-by-patch mode”) with
  the ChromIQ chart-reading engine, the preview now guides you exactly like
  strip reading does: the patch to measure next is **highlighted**, the view
  follows it across pages, and every patch you read fills in with the colour the
  chart **expected** versus the colour your instrument **measured** — hover a
  patch to see both as RGB and L\*a\*b\* plus the ΔE. You can also **click any
  patch in the preview to jump straight to it.** Previously patch-by-patch mode
  fell back to plain ArgyllCMS with only text prompts and no live guidance. The
  engine now drives both interactive reading modes — strips and single patches.
- **Fix — patch-by-patch no longer hangs on instruments that must calibrate
  first.** On a meter like the ColorMunki that asks to be calibrated at the
  start, patch-by-patch mode would freeze; the calibration request now appears
  as the normal ChromIQ dialog and measuring proceeds.

## v3.14.4

- **See the numbers behind any measured patch, right in the preview.** With the
  ChromIQ chart-reading engine, the Measure preview already splits each patch
  into the colour the chart expected and the colour your instrument read. A new
  **“Show patch values on hover”** option (Measure → Live preview) adds a small
  card that follows your mouse and shows, for the patch under it, both colours
  as RGB and as exact L\*a\*b\*, plus the ΔE between them — so you can check a
  suspicious patch without leaving the measuring screen. It follows the “Each
  patch shows” setting, saves as a default, and travels in a preset.
- **The chart’s file path no longer pops up over the chart while you measure.**
  The path/name tooltip used to appear on the chart image during a read, getting
  in the way of swiping and the new hover card; it is now held back until the
  measurement finishes (and still sits on the header text throughout).

## v3.14.3

- **The number of automatic calibration retries is now adjustable (mavtop).**
  ChromIQ retries a failed instrument calibration a few times before giving up,
  which rescues an ageing instrument whose lamp needs a couple of strikes to burn
  in. That count is now a setting (Settings → Beta → “Retry a failed calibration
  up to…”), so an old i1Pro that wants ten attempts can have them. Default is 3
  (four tries in total); set it to 0 to turn retries off. It only affects the
  ChromIQ chart-reading engine.

## v3.14.2

- **A failed calibration no longer leaves measuring stuck (mavtop).** When the
  ChromIQ engine reported a failed calibration it waited for an answer that
  ChromIQ never sent, so the run stopped dead — no error, no way forward, and
  the message explaining what happened never appeared because it is only shown
  once a run has finished. ChromIQ now always answers.
- **Calibration is retried automatically (mavtop).** An older bus-powered
  instrument can fail to calibrate simply because striking the lamp briefly
  draws more power than the USB port supplies, and then succeed moments later.
  Rather than stopping at the first failure, ChromIQ now tries up to four times,
  pausing a couple of seconds between attempts so the instrument can recover,
  and tells you in the log what it is doing. Only if all four attempts fail does
  it report the problem — and it can then still fall back to ArgyllCMS's own
  chartread. Leave the instrument where it is while it retries.

## v3.14.1

- **Measurement Report — the cube corners are the chart's real ideals again
  (Knut).** Expected values were being read out of the chart's `.ti2` in the
  wrong colour space: printtarg records an RGB chart's design colours under D65,
  but the report compared them in D50. Paper white came out as a bluish
  Lab 100/-2.3/-19.3 instead of a neutral 100/0/0, and every corner looked
  invented rather than the textbook ideal. The design reference is now adapted to
  D50 first, so the corners match the sRGB primaries exactly and every ΔE in the
  report is correct — this affected **all** reports built against a chart, not
  just imported ones.
- **Measurement Report — charts whose `.ti2` stores XYZ 0..1 are read correctly
  (Knut).** printtarg writes the design colours either 0..100 or normalised
  0..1, with nothing in the header to tell them apart. The normalised form was
  taken at face value, making every expected colour 100× too dark (a chart's
  white read as L\* 9) and its ΔE meaningless. The scale is now detected and
  normalised.
- **Measuring falls back to ArgyllCMS when ChromIQ's engine can't use your
  instrument (mavtop).** v3.14.0 turned the ChromIQ chart-reading engine on by
  default. If it could not drive a particular meter, measuring simply stopped
  there — even when ArgyllCMS's own chartread would have worked. ChromIQ now
  notices a failed start and quietly restarts the run on stock chartread, so you
  can carry on measuring. It only ever does this before the first reading is
  taken, never after a strip has been read, and never when you stopped the run
  yourself.
- **The calibration prompt now shows what your instrument actually asked for
  (mavtop).** The engine reports the exact calibration step, but ChromIQ threw
  that away and showed one generic message for every case. It now passes the
  instrument's own instruction through, and offers a "Skip this step" button
  when the instrument says the step is optional.
- **Fixed unreadable characters in the calibration prompt.** For calibration
  steps that carry no message of their own — an X-Rite ColorMunki asking for its
  calibration position, for instance — the measuring engine sent uninitialised
  data instead of an empty message, which would have appeared as random
  characters in the dialog.
- **Clip border — the text no longer runs into the patch area (Knut).** The
  stacked lines were justified across the full strip width, which pushed the last
  line's ink past the inner edge and over the patches. Lines now keep their
  natural spacing and start at the outer text-edge distance, so the block always
  stays inside the strip. Only the font size grows — until the longest line
  reaches the text-edge along the strip, or the stack reaches it across.
- **Clip border — deleting the blank lines between records now visibly tightens
  the text (Knut).** Because the lines were stretched to fill the strip whatever
  their number, removing the blank lines between them changed nothing on screen.
- **Clip border — "Example custom table" is now called "Custom text example"
  (Knut).**

## v3.14.0

The chart-reading engine, the Measurement Report and the i1Profiler import
features that have matured across the 3.13.12 beta series are now on by default
and part of the stable release. Highlights since v3.13.11:

- **New: chart-reading engine, on by default.** ChromIQ now reads strips itself,
  with a live split preview of the chart, per-strip autosave, click a patch to
  jump there and re-read, and clearer stripe detection. (The classic ArgyllCMS
  reader is still available in Settings.)
- **New: Measurement Report tool (Tools → Measurement report).** Measure a chart
  and get a clear Pass/Fail report of how accurately it reproduced — average,
  worst and spread of the colour difference (ΔE00), the worst patches, paper
  white & black and the cube corners. Add several measurements of the same
  printer and it plots the drift over time, so you can see when ageing inks or a
  wandering printer make it worth re-profiling. Save it as a PDF. A dated report
  can be written automatically after every measurement (Settings → Reports).
- **New: read i1Profiler measurements directly.** Everywhere ChromIQ asks for a
  measurement — Build Profile, the Measurement Report, Convert, the
  scanner-target import — you can now hand it i1Profiler's own files
  (.mxf / .txt / .cxf) and ChromIQ converts them for you, no export step needed.
  Handy if you measure with an i1iSis or i1iO.
- **New: keyboard shortcuts + a "Keyboard shortcuts" Help card.** App-wide
  shortcuts (all carrying ⌘ or an F-key so they never clash with the instrument
  during a measurement), ⌘1–5 to jump between tabs and then the arrow keys to
  move along the tab strip.
- **Chart layout & clip border.** The ChromIQ layout engine gained a reworked
  clip border — auto-filled record strip, a 180° flip so a right-side border
  reads the right way up, text that now reaches the edges on every side — plus
  instrument-margin handling and an editable example table.
- **Tidier working folders.** Each profile now keeps its reports, exports and
  tool intermediates in their own sub-folders; older projects are migrated
  automatically the first time you open them.
- **Snappier UI.** Faster tab switching (styling is remembered per theme) and a
  smoother first chart render with a custom font.
- **Fully translated into twelve languages** — German, Spanish, French, Italian,
  Japanese, Dutch, Norwegian, Polish, Portuguese, Russian, Swedish and Simplified
  Chinese — including every tooltip and the long in-app help texts.

The per-beta detail for everything above is retained below.

## v3.13.12-beta.35

- **Clip border — the text reaches the edges on the sides too (Knut).** Short
  clip records with one long line (e.g. the Example table's header) left the
  lines packed in the middle of the strip. The lines are now spread across the
  strip's width so they reach the "Text distance from edge" on the left/right as
  well, not just top and bottom.
- **Snappier tab switching.** Switching to a tab no longer re-computes its
  styling from scratch every time — it's remembered per theme — so the heavier
  tabs (Create Chart, Build Profile) come up faster. Theme changes still restyle
  everything.
- **Smoother first chart render with a custom font.** The list of installed fonts
  is now prepared quietly in the background just after launch, so the first chart
  that uses a system font doesn't pause to gather them.

## v3.13.12-beta.34

- **Keyboard — arrows move between tabs (Basti).** After ⌘1–5 (or Tab to the tab
  strip), the ← / → keys now switch tabs. The Keyboard-shortcuts card lists it.
- **Scanner-target import takes i1Profiler's .mxf/.cxf directly (Knut).** The
  measurement picker only offered .ti3/.txt even though ChromIQ already converts
  the others; it now lists .mxf / .txt / .cxf, with matching help text.
- **Measurement Report — the PDF saves in a sensible place (Knut).** An imported
  i1Profiler measurement is converted in a temporary folder, and the report used
  to try to save there. It now defaults to a "reports" folder next to the file
  you loaded (created if missing).
- **Measurement Report — tidier header with many measurements (Knut).** Loading a
  whole folder of measurements no longer prints a long list of names in the page
  header; past a handful it shows the run count and date range instead.

## v3.13.12-beta.33

- **Measurement Report — add many measurements at once (Knut).** The picker is
  multi-select now, and several loose measurements in the same folder each add as
  their own trend point (before, only one per folder was taken). Works for
  ChromIQ .ti3 and i1Profiler .mxf / .txt / .cxf, mixed.
- **Measurement Report — more accurate colour for imported measurements (Knut).**
  When there's no design file, the reference derived from the device values was
  compared under the wrong white point, inflating every imported measurement's
  ΔE by about 1.5. It's now adapted to the same white point as the measurement,
  so the figures are correct (a white patch reads neutral). Saved reports refresh
  automatically.
- **Clip border — the text fills the sides too (Knut).** Auto-sized clip text
  reached the top and bottom edges but stopped short on the left/right; it now
  grows to fill the strip's width up to the same "Text distance from edge", so
  short records use the whole strip.
- **Build Profile — the Load tooltip now names the i1Profiler formats** it
  accepts (.mxf / .txt / .cxf).

## v3.13.12-beta.32

- **Measurement Report now takes i1Profiler measurements directly (Knut).** The
  report's "Add measurement" was .ti3-only; it now accepts i1Profiler files —
  .mxf, .txt or .cxf — and converts them for you, no export step. Add several
  measurements from one i1Profiler folder to see a trend across them; the
  instrument and measurement date are read from each file.
- **Convert i1Profiler → TI3: the output name follows each file you pick
  (Knut).** Picking a second measurement used to leave the save name stuck on
  the first file's; it now updates to match the new file (while still keeping a
  name you typed yourself).

## v3.13.12-beta.31

- **Keyboard shortcuts (Knut/Sebastian).** ChromIQ now has app-wide shortcuts:
  ⌘1–⌘5 jump straight to a tab, ⌘, opens Preferences, ⌘T opens the Tools menu,
  F1 (or ⌘?) opens Help, and ⌘Return runs the current tab's main action
  (Generate / Print / Measure / Build / Check). Every shortcut uses ⌘ (or an
  F-key) on purpose, so none can clash with the keys that drive the instrument
  while you measure (Space reads a patch, ← / → move between strips, Enter
  confirms, Esc stops).
- **New "Keyboard shortcuts" Help card.** The Welcome / Help window now lists
  every shortcut, alphabetically, with a note that the keyboard drives the meter
  during a measurement.

## v3.13.12-beta.30

- **Clip border — the writing lines fill the whole strip now (Knut).** The clip
  text used to shrink and stop well short of the page's top and bottom edges. It
  now runs right down to the clip text-edge distance you set before it reduces
  the size, so a hand-fill record uses the full length of the strip.
- **Clip border — "Flip 180°" (Knut).** A new checkbox next to the clip Side.
  A clip on the Right side is printed upside-down by default so it reads the
  right way up from that side of the sheet; tick this to turn any clip the other
  way — e.g. so a right-side clip reads the same direction as the info line
  stamped along the bottom. Works on the left side too. Saves as a default and
  inside a preset.
- **Clip border — "Example custom table" tweaks (Knut).** The ready-made record
  now reads "ChromIQ Chart …" (not "ArgyllCMS …"), and the fill-in lines were
  re-tuned (Profile name is longer).

## v3.13.12-beta.29

- **Space bar no longer trips a button you didn't mean to press (Knut).** When a
  tab or dialog opened, whatever button happened to take the initial focus would
  fire on the space bar — saving defaults, opening a file picker, popping a
  tooltip. Icon and help buttons are no longer keyboard-focusable, and a single
  guard clears that stray focus on every dialog and tab. Input fields keep their
  focus, and Enter still triggers a dialog's default button.
- **Import i1Profiler's native measurements directly (.mxf), no export step
  (Basti).** i1Profiler saves measurements as .mxf (CxF3); ChromIQ now reads them
  straight into a .ti3 — everywhere you can load an i1Profiler measurement (the
  Convert i1Profiler → TI3 tool, Build Profile, and the scanner-target import).
  The .txt and .cxf paths still work too.
- **Convert i1Profiler → TI3 now carries the instrument and the measurement date
  across.** The real measuring instrument (e.g. “i1Pro 2”) and the date the chart
  was measured are read from the i1Profiler file and stamped into the .ti3, so the
  Measurement Report shows the right instrument and plots each run on the date it
  was actually measured (not the day you converted it). This also fixes two
  beta.27 cases where the instrument wasn't stamped and the date was lost.
- **Measurement Report — trend threshold labels.** When a Pass threshold lands on
  a y-axis number, the Avg / Max labels no longer overlap it — both move just above
  their line instead.
- **Create Chart — clip border.** Blank lines in the clip-border text are kept now,
  so you can leave writing space between hand-filled fields. And a clip border on
  the Right side is now exactly its set width (it used to come out wider than the
  Left side).

## v3.13.12-beta.28

- **Measurement Report — fixed: a project full of valid charts showed "no design
  reference" and an empty trend (Knut).** Reports saved by an older ChromIQ used
  an older metric format; the report window now rebuilds those from each run's own
  measurement, so the colour-accuracy figures and the drift trend appear as they
  should. The saved dates are kept, so the timeline is unchanged.
- **Report trend — threshold labels tidied.** The Avg / Max labels on the Pass-
  threshold guide lines now sit in the left margin, aligned with the y-axis
  numbers and centred on their dotted line, and still follow the line as you
  change the thresholds. The Pass-threshold help also notes the defaults come from
  Settings → Reports.
- **Report — clearer about the reference for imported measurements.** When a
  measurement has no design file (.ti2) beside it, the report derives the
  reference from the file's **device (design) values** — the fixed code values
  sent to the printer, identical for every run — so it stays just as static across
  runs as a .ti2 would. Wording corrected throughout to make that plain.
- **Create Chart — "Use instrument margins" now works in "Prioritise patch size"
  too (Knut).** Previously, with instrument margins on, that layout mode pushed
  the patch area too far down and pinned the strip labels at the instrument
  margin. The strip labels now sit at the page text-edge and the patch area starts
  at the margin — matching "Prioritise chart area". The instrument ruler cap still
  applies, so the strip stays scannable.
- **Create Chart — clip-border "Example custom table".** The clip-border Text box
  is now multi-line (with a scrollbar), and a new Content option loads a ready-made
  record — the same table the old "Print info in left clip area" printed (chart
  summary, print-driver reminder, and fill-in lines for date / printer / ink set /
  profile name / paper / driver) — into the editable box for you to adjust. The
  Insert menu gained a "New line" item.
- **Print Chart — icon order.** The header icons are now load test chart, load
  image, reveal folder.

## v3.13.12-beta.27

- **Imported i1Profiler measurements now work in the Measurement Report on their
  own (Knut).** Measure a chart in i1Profiler (for an i1iSis or i1iO that lays
  out its own chart), export it, convert it with Tools → “Convert i1Profiler →
  TI3”, and add the .ti3 to the report — you get the full colour-accuracy
  figures with no extra reference file. ChromIQ works out each patch's expected
  colour from the measured device values, the same reference a chart's own
  design file (.ti2) carries; if a matching .ti2 happens to sit beside the .ti3,
  that's used instead. This removes the old need for a hand-matched .ti2.
- **The instrument is carried across.** “Convert i1Profiler → TI3” now reads the
  instrument from the i1Profiler file and stamps it into the .ti3, so Report
  Scope shows the real instrument (e.g. “i1Pro 2”). Files that name none show
  “i1Profiler (unspecified)”.
- **Convert i1Profiler → TI3 keeps things together.** The tool now suggests the
  same folder as your i1Profiler file, so the converted .ti3 and its report can
  live alongside your i1Profiler data, separate from ChromIQ's profile folders.
- Device values on the 0–255 scale i1Profiler exports are handled correctly.

## v3.13.12-beta.26

- **The load and reveal-folder buttons moved to the header.** On the Measure and
  Build Profile tabs the “load chart / load measurement” and “reveal folder”
  icons now sit in the top-right of the header, at the tab title's height — the
  same place they already live on Print Chart. The Create Chart tab's four
  header icons moved there too, so all four step tabs match.
- **Fixed: “Print info in left clip area” fighting the layout engine (Knut).**
  Turning on the ChromIQ layout engine while that older printtarg-only option was
  still ticked could silently flip the panel back to the printtarg parameters,
  even though the engine switch still read ON. The engine has its own Clip-border
  content, so the “Print info in left clip area” row is now hidden while the
  engine is on (your choice comes back if you switch the engine off).

## v3.13.12-beta.25

- **Settings — new “Reports” tab.** The measurement-report options live here now:
  the “Save a measurement report after each measurement” switch (moved out of
  Beta), and a “Measurement Report Defaults” section where you set the default
  Pass thresholds (Average and Maximum ΔE) the report opens with.
- **Chart-load button — a clearer icon.** The Measure tab's “load chart file”
  button now uses the same patch-grid glyph as the Print tab's “load test
  chart”, drawn as a small document (a folded-corner page around the grid), in
  the tab's accent colour — green on Measure, amber on Print.
- **Saving a measurement report is on by default** (existing installs that were
  on the old default switch on; you can turn it off in Settings → Reports).

## v3.13.12-beta.24

- **Measurement Report — a big rework (Knut).** The window and the PDF now show
  the same report in one sequence:
  - **Report Scope** — the profiles and instruments included, the run count and
    date range, with red warnings if the runs mix instruments or a chart is
    missing cube corners (the report can't tell printers apart, so it's up to you
    to include runs from one printer — name your Printer Profile Names clearly).
  - **Report Results** — a Pass/Fail grid of each colour-accuracy metric against
    each run, green for pass, red for fail.
  - **Colour accuracy** — a revised metric set: average and maximum ΔE over all
    patches, over the best 95 %, and over the worst 5 %, each judged against a
    Pass threshold (Average default 2.0, Maximum default 3.0, both adjustable).
  - Trend charts now plot all five metrics; the side-by-side comparison keeps to
    six dated columns with zebra rows and a wide Metric column; optional detailed
    data per run, each run on its own page.
- **PDF identity.** The ChromIQ wordmark sits top-right of every page, with the
  five-part spectrum line under the title on page 1 and across the top of later
  pages, a per-page header naming the profiles and date range, and page numbers.
- **Import i1Profiler measurements.** Convert an i1Profiler measurement to a .ti3
  (Tools → “Convert i1Profiler → TI3”), keep the chart's .ti2 beside it, and this
  report reads it — handy for verification tracking.
- Worst-patches and cube-corner tables now share the same column order
  (Patch · Expected · Measured · ΔE).
- **Faster startup.** The app no longer re-polishes its whole widget tree a
  second time at launch when the theme hasn't changed — about two seconds off a
  cold start (measured 8.1 s → 6.0 s on Windows-arm64; every platform benefits).

## v3.13.12-beta.23

- **Measurement Report window restyled** to match the other Tools windows: a
  masthead (title + ⓘ) over the full-width spectrum stripe with the green accent
  and its gradient wash, the report view scrolls with the same fade-to-edge
  gradient the other tool panels use, and the checked checkbox, focus rings and
  ⓘ icons all take the green accent.

## v3.13.12-beta.22

- **Measurement report — a lot tidier and more useful.** The buttons no longer
  clip their text, and "Save report as PDF" keeps its label instead of turning
  into the saved filename. A new **Reveal folder** button opens the profile's
  folder so you can browse to your saved reports. When "Include all measurement
  runs" is on, the PDF is saved to a `reports` folder next to the profile's runs
  (a report for the whole printer), otherwise to the loaded run's own `reports`
  folder; it is named `measurement_report_…` and opens automatically after
  saving.
- **Report PDF — built for print.** The Paper-white and Darkest-black trend
  charts now scale to the data (rounded to 0.1) instead of starting at 0, so a
  small drift is actually visible, and all four charts fit on one page. Each
  major section starts on a fresh page, every page has a centred "Page X of Y"
  footer, a comparison table too wide for the page continues in stacked tables
  below, and the worst patches (now 16) are shown as two columns side by side to
  save space.
- **Patch-flagging limit default is now 50 ΔE** (was 20). With the smarter
  adaptive flagging, 20 still lit up legitimately-vivid patches on scanner/print
  work; 50 is the value that gives a clean, useful red outline. If you had raised
  the old default it moves to 50; a value you deliberately lowered is kept.
- **Hexagonal SpectroScan charts** — "Show only measured patches" no longer wipes
  the A–F column labels across the top.
- **ColorMunki offset charts (scanner/camera profiling)** — the alignment grid
  now includes the top-most and bottom-most spacer, so its total height matches
  the printed chart on a chart with every second column shifted.

## v3.13.12-beta.21

- **Measured-patch flagging is much smarter.** The live red outline compares a
  patch to the chart's sRGB design, and a printer doesn't reproduce sRGB — so
  vivid colours legitimately sit 30–40 ΔE away on a perfect print, which made a
  good chart light up in red almost everywhere. A patch is now flagged only when
  it is BOTH past the limit AND clearly stands out from the rest of its own strip
  — a real misread stands out; ordinary print-vs-sRGB difference does not. If you
  had raised the flagging limit in an earlier beta to escape the old false
  alarms, it is reset to the default — the higher value would now only hide real
  misreads (a value you lowered is kept).
- **Measurement report — compare across runs.** The PDF can now include every
  saved measurement of the printer (a checkbox) with a per-run data table and a
  side-by-side comparison of each metric; paper white and darkest black are now
  their own charts (they're too far apart to share an axis); and the report is
  ordered how-to-read → charts → detailed data. A new "Add another project's
  runs…" button folds a second profile folder's measurements into the trend and
  PDF, for the same printer kept in a different project.
- **Misalignment safety net (opt-in, off by default).** Turn it on in
  Settings → Beta and, after each strip, ChromIQ checks whether the reading
  would fit dramatically better shifted by a patch (the reader locking a row one
  patch off). If so it warns and offers to re-measure just that strip. It only
  ever warns and never triggers on a normal good read.
- **Hexagonal SpectroScan charts** — "Show only measured patches" no longer
  wipes the column labels.
- **ColorMunki offset charts** — the blank-cell grid now draws the left edge on
  the top and bottom patches of the shifted columns.

## v3.13.12-beta.20

- **Measurement report: the eight cube corners.** The report now keeps paper
  white, composite black and the six primary/secondary inks (red, green, blue,
  cyan, magenta, yellow) — each with its measured colour, expected colour and
  ΔE00 — so it tells you about the inks themselves, not only the instrument
  (Knut).
- **Grouped trend charts.** Unlike-scaled metrics no longer share one axis:
  the trend is now three tabbed charts — colour accuracy (ΔE00), paper
  white/black (L*), and the eight cube corners (ΔE00 per ink). The trend
  x-axis now dates every measurement, not just the first and last.
- **Save the report as a PDF.** A new button writes the whole report — every
  data table, all three trend charts, and a plain-language "how to read this
  report" guide — as a PDF into the reports folder.
- **Hexagonal SpectroScan charts in "Show only measured patches".** Unread
  patches now draw as their true hexagon and measured patches fill the hexagon
  (with the diagonal expected/measured split), both following the zigzag —
  they were being drawn as rectangles.
- **No more wiped caption on a partial last page.** The "Show only measured"
  blank-out no longer covers the right-margin caption on a ragged last page.
- **ColorMunki measuring pop-up** now says to press and hold the side button
  while sliding the whole device (Knut).
- Fixed expected-colour swatches rendering white in the report (a scaling bug
  in the reference-colour conversion).

## v3.13.12-beta.19

- **"Offset every second strip" is finally hidden everywhere it should be.** The
  previous fix only reached the Create Chart panel; in Preferences → Chart Layout
  the ColorMunki-only checkbox (and the clip-border On/Off selector) still showed
  for the i1Pro, i1Pro 3 Plus, SpectroScan and the old DTP readers. Both windows
  now hide it for every non-ColorMunki instrument.
- **Consistent instrument lists.** Preferences → Chart Layout no longer lists
  DTP41 / DTP51 — they aren't offered in Create Chart or Instrument Limits and
  aren't supported, so all three places now show the same four instruments.

## v3.13.12-beta.18

- **Instrument-specific measuring instructions everywhere.** The measurement
  pop-up now matches your instrument in all three cases — a normal measurement,
  the guided re-measurement, and a manual resume — not just the first. A
  ColorMunki / i1Studio is told to turn the dial to the measurement position; an
  i1Pro to take it off its base, hold the button and slide; other instruments
  keep the general wording.

## v3.13.12-beta.17

- **Instrument-specific measuring instructions.** The "calibrate the instrument"
  and "how to measure" pop-ups now match the instrument your chart was made for:
  a ColorMunki / i1Studio tells you to turn the dial to the calibration position
  (the small gear icon); an i1Pro tells you to use its base and white tile; the
  SpectroScan and any unknown instrument keep the general wording.
- **The strip highlight follows hexagonal patches.** On SpectroScan hexagonal
  charts the mint strip outline in the Measure preview now traces the column's
  actual hexagons and their zigzag — one clean frame for the whole column,
  instead of a straight box that reached into the next column. The swipe arrow is
  also hidden for the SpectroScan, which reads patch-by-patch and isn't swiped.
- **"Offset every second strip" is ColorMunki-only again.** In Preferences →
  Chart Layout it was wrongly showing for the SpectroScan, i1Pro, DTP41 and
  DTP51; it (and the ColorMunki/SpectroScan clip-border On/Off selector) is now
  hidden for those instruments from the moment the window opens.
- **Building your own chart from a ready-made preset works.** Loading a built-in
  preset such as "TC9.18 extended greys by Pharmacist" and then switching on
  "Use the ChromIQ layout engine" now reveals the engine's layout controls, so
  you can adapt the layout instead of being stuck with the old page setup.

## v3.13.12-beta.16

- **Save a shuffled copy of the patch set for i1Profiler.** When you hand a patch
  set to i1Profiler, it lays the chart out in the exact order the patches appear
  in the file. A chart straight out of ChromIQ keeps its colours in a tidy,
  systematic order, which can put very similar colours right next to each other
  on the printed strip — a little harder to read and slightly less ideal for the
  instrument. There's now an opt-in "Also save a shuffled copy for i1Profiler"
  checkbox: tick it and ChromIQ writes a second copy alongside the normal one,
  with the patches shuffled into a mixed-up order and "-shuffled" added to the
  file name. Handed to i1Profiler, that copy keeps the mixed order instead of
  lining the colours back up, so similar colours end up spread across the chart.
  Both copies are always written, so you can pick whichever you prefer. The
  checkbox appears in Tools ▸ Convert TI1 → i1Profiler and in the patch-set
  editor's Apply / Save window (Nelson / pharmacist).
- **Convert TI1 → i1Profiler polish.** The window now uses its magenta accent for
  ticked checkboxes and focused fields, its Browse buttons are compact folder
  icons (matching the Soft-proof window), and the workflow-file option gained a
  plain-language help icon explaining what a `.pwxf` is.

## v3.13.12-beta.15

- **Faster instrument connection.** On some computers there was a long pause —
  often around ten seconds — between pressing Start and the instrument asking to
  be calibrated. It happened because, before finding your USB instrument, the
  measuring engine spent a couple of seconds trying each of the computer's serial
  ports in case an old serial instrument was attached — and on macOS (and
  sometimes Linux) there's usually an invisible Bluetooth serial port that eats
  that time for nothing. ChromIQ now skips those known-empty ports, so the
  calibration prompt appears almost immediately (measured: ~11 s → under half a
  second). A real serial instrument on a USB-to-serial adapter is always kept,
  and nothing about your measurements changes. There's a new switch for it in
  Preferences → Beta ("Faster instrument connection", on by default).

## v3.13.12-beta.14

- **Re-measuring a strip refreshes its live preview instead of doubling it.** When
  you read a strip again (for example re-measuring a chart that was already
  finished), its expected-vs-measured split patches now update in place rather
  than stacking a second copy on top — so the preview always shows the latest
  reading, with no leftover warning outline.

## v3.13.12-beta.13

- **Regenerating a chart no longer leaves a stale PDF behind.** Creating a new
  chart under the same name now clears the old vector PDF (and the `.cie` and
  `.strips.json` sidecars) from the working folder, along with the other chart
  files it already cleaned up.

## v3.13.12-beta.12

Measure-tab chart-reading-engine polish (Knut/Basti).

- **The live-preview view controls have their own section now.** "Each patch
  shows" (expected / measured / split) and "Show only measured patches" sit in
  a **Live preview** group that is always visible in both the Guided and Manual
  modules, stays usable **while you measure** (they only change the preview,
  never your readings), and is saved as defaults and in presets. The two
  modules keep their own independent view settings.
- **The left panel scrolls while measuring again.** Starting a measurement
  locks the parameters (as before) but no longer freezes scrolling, so every
  option stays reachable.
- **Clearer wording.** The old "Show:" selector is now "Each patch shows:", with
  plain-language choices.
- **The strip-hover highlight is snappy and complete.** Hovering a strip to jump
  to it now follows the pointer without delay, and its mint frame includes the
  strip's edge spacers (detected from the chart's own geometry) so it matches
  the whole swiped strip.
- **Click a strip to jump to it in Guided mode too**, not just Manual.

## v3.13.12-beta.11

Two follow-up fixes.

- **The pointer ruler now follows your mouse.** "Show measurement coordinates
  on pointer" drew its cross-hair well off to the side of the pointer and
  lagged behind it. It now sits exactly under the pointer and tracks it
  instantly, with the millimetre / inch readout right beside it.
- **SpectroScan charts default to a proper grid.** The SpectroScan is a flatbed
  that reads a fixed grid, but the generic layout default could collapse its
  chart into a single column of thin full-width bands. It now defaults to the
  patch-size-first layout (and the By-columns/rows method), so you get a proper
  grid of hexagons or squares straight away. Choosing "Prioritise chart area"
  with an explicit column/row count still works exactly as before.

## v3.13.12-beta.10

Knut's full SpectroScan-hexagonal + follow-up wish list.

- **Hexagonal charts: margin guide lines now land exactly on the patches.**
  For a SpectroScan hexagonal chart the "Show margin guide lines" lines (and
  the measured margins) now sit on the true edges of the hexagons — the top
  and bottom on the pointed tips, the left and right on the flat sides —
  instead of a little inside them.
- **New: a ruler on your pointer.** The "Measured from Preview" panel has a
  third switch, **Show measurement coordinates on pointer**. With it on, a
  thin cross-hair follows your mouse over the chart and shows its exact
  position — measured from the top-left corner of the paper — in millimetres
  (one decimal) and inches (three decimals). The easy way to check a real
  distance on screen.
- **Hexagonal chart reading is aligned.** With the chart-reading engine on, the
  expected/measured split now sits precisely on each hexagon (it followed the
  hexagons' natural row-to-row zig-zag). Strip counting and labels for
  hexagonal charts were verified correct.
- **Hexagonal charts explain their limits fully.** The heads-up now lists every
  feature that can't use a hexagonal chart (create scanner/camera target, build
  a scanner/camera profile, and the alignment check).
- **Tidy up old projects as you open them.** A new preference (General →
  Behaviour → **Declutter files when loading from legacy folders**, on by
  default) sorts an old flat project's loose ChromIQ files into the tidy
  reports / exports / cache sub-folders the first time you load a file from it.
  Only files ChromIQ made are moved; your own files are never touched.
- **The folder guide is clearer.** "Where are my files?" now opens with a
  **Files Relating to Features** table (what each feature reads and writes),
  followed by the full **All File Types and Their Use** list.
- **See how a printer drifts over time.** The Measurement Report window now
  draws a trend chart of the average and worst colour difference across every
  saved report for a printer — a slow rise or a sudden jump stands out at a
  glance.

## v3.13.12-beta.9

More of Knut's chart-layout wish list.

- **Chart Layout margins update the moment you switch instruments.** Picking a
  different instrument now refreshes the per-side margin boxes right away, even
  for instruments (like the SpectroScan) that don't carry their own fixed
  margin minimums — the boxes fill from the chart's own layout instead of
  staying stale.
- **Read strips stay clean in "Show only measured patches".** With the switch
  on, strips you've already measured are shown plainly, with no leftover grid
  lines over them.
- **Hexagonal charts explain themselves.** A chart built with the SpectroScan's
  hexagonal patches can't be used by the scanner or camera tools — the
  recognition file they rely on can only describe rectangular patches. ChromIQ
  now tells you this clearly, right when it matters: a friendly heads-up if you
  switch the patch shape to hexagonal while making a chart, and a plain
  explanation (instead of a late failure) if you try to feed such a chart to
  **Create scanner/camera target** or **Build profile with scanner/camera** —
  along with how to make a chart that works.

## v3.13.12-beta.8

More of Knut's chart-reading-engine wish list (engine on).

- **See your reading progress at a glance.** A new **Show only measured
  patches** switch in the Measure tab blanks every patch you haven't read yet
  to an empty cell, so the coloured, measured area growing down the chart shows
  exactly how far you've got. It handles every layout, including ColorMunki
  "offset every second strip".
- **Set your own "misread" threshold.** Preferences → Beta now has a
  **patch-reading error limit** (in ΔE, default 20): a just-measured patch gets
  the red warning outline only when it comes out further than this from the
  colour the chart expected. Lower it to be warned about smaller differences,
  raise it to flag only the worst.
- The **Clip-border content** help now says these options are available only
  when the clip border is turned on.

## v3.13.12-beta.7

A small polish to the chart-reading engine's live preview (engine on).

- **The warning outline around an off patch is now unmissable.** When a patch
  reads far from what the chart expected, its live split-patch preview is
  outlined so you can spot it at a glance. That outline was a muted red drawn
  on the patch edge, which blended into red, magenta, pink or dark patches. It
  is now a bright red line over a white halo — the same high-contrast style the
  margin guides use — so it stands out on any patch colour, in light or dark
  mode, without covering the patch.
- **The outline now hugs every patch identically.** A rounding quirk left some
  outlines a pixel off-centre while others sat perfectly; they now all line up
  exactly with their patch.

## v3.13.12-beta.6

Every point from Knut's beta.5 test report, fixed in one go.

### Create Chart / Preferences — no more "greyed-out" boxes

- The **Clip border width** box and the **Left/Right margin** boxes no longer
  turn permanently grey after a value change or after toggling "Use
  instrument margins". The red conflict outline used to *replace* each box's
  field styling instead of merging with it, leaving enabled boxes looking
  disabled. Now the outline rides on top and clears back to the exact
  original look. The boxes were always editable — they just looked locked.
- In **Preferences → Chart Layout**, a stale red outline no longer survives
  on a margin box when the clip border is **Off** (the hidden clip-width
  value used to keep the conflict highlight alive there).

### Build profile with scanner or camera

- **Older working files get tidied too**: starting a run now moves the
  previous releases' scanner intermediates (`…-aligned.cht`,
  `…-aligned-patchbox….cht`, prepared `…-patchbox/-sample.cht` copies,
  `…-diag.tif`) from the chart's and the scans' folders into `cache/`, in
  all three modes. Measurement data (`…-printer.ti2/.ti3`, `…-scanner.ti3`,
  per-shot `…-pNsK-scanner.ti3`, `…-pN-avg.ti3`) is real data and stays put.
- **The page selector always follows the selected target** in "A standard
  target I own" mode. Switching from a multi-page ChromIQ chart to a
  single-page standard target could leave the chart's page dropdown behind
  (the "Profile my printer" un-tick re-picked the chart under the hood and
  restored its pages).
- **Your `scanner-test-targets` folder is back — and smarter.** ChromIQ now
  places every standard target's layout file (`.cht`) into
  `scanner-test-targets` in your output folder whenever the scanner window
  opens: missing files are restored, a file you edited is never overwritten,
  and an untouched copy is refreshed automatically when a ChromIQ update
  ships a corrected version. **Your copy is the one ChromIQ uses** — edit a
  `.cht` there (same file name) and the tool reads your version instead of
  its built-in copy. The target-type help explains this, and the folder
  carries its own "About this folder.txt".

### Verify tools now leave reports

- **"Verify a profile"** and **"Verify against reference"** save a readable,
  numbered report (`Verify_Profile_N_….txt` / `Verify_Reference_N_….txt`)
  into the `reports/` folder next to the measurement — verdict, inputs and
  the full tool output, keeping a history just like the quality check.

## v3.13.12-beta.5

A small fix on the Create Chart layout panel.

- **The inch value next to each page margin now always matches the millimetre
  value in the box.** When **Use instrument margins** filled the four margins
  from your instrument limits, the little inch readout beside each box kept
  showing its previous value (for example the Left margin jumped to 26 mm but
  the readout still said 0.236″ instead of 1.024″). It now updates in step,
  whether the option is on or off.

## v3.13.12-beta.4

Tidier project folders (#127). A run folder used to collect up to 30+ files
side by side; now everything you print, install or keep stays right at the
top, and the paperwork lives in three self-explaining folders. **Your
existing projects are tidied automatically the first time you open them** —
nothing is deleted or renamed, your own files are never touched, and your
measurements and profiles stay exactly where they were.

### Cleaner run folders

- New sub-folders in every run, with a fixed meaning:
  - **reports/** — things ChromIQ tells you: quality-check reports, the
    re-measure list, and the dated measurement reports (which already lived
    here).
  - **exports/** — files made for other programs: the i1Profiler patch set
    and the plain colour list. Same name and meaning as the project-level
    `exports/` folder (Knut's naming).
  - **cache/** — temporary working files from the tools (scanner recognition
    copies, diagnostic images). Always safe to delete; ChromIQ can recreate
    everything in it (Knut's idea).
- The calibration chart's hand-off files get the same treatment in
  `cal/exports/`.
- The chart pages, your measurement (`.ti3`) and your profile (`.icc`) stay
  at the top of the run folder, exactly where they were — the measuring and
  profile-building tools require it, and they're the files you actually want.

### Automatic tidy-up of existing projects

- Opening a project made by an older ChromIQ reorganises it in place: only
  files ChromIQ itself wrote are moved (by exact name pattern), nothing is
  overwritten, and an interrupted tidy-up simply finishes on the next open.
- A project last used by a **newer** ChromIQ opens with a friendly "please
  update" note instead of half-working.

### The folder guide learned the new layout

- The "Where are my files?" card (and the `Where are my files.txt` in every
  project) is rebuilt folder-first: the three files that matter on top, then
  what each folder means in one sentence, then every file in detail. The
  text file is refreshed automatically when a project is tidied.
- The guide now also covers the profile-verification files
  (`.x3d.html` + `x3dom.*`), which were missing before.

### Fixed

- Renaming a project now also renames a calibration chart's export files
  (`…-cal-colours.txt`, `…-cal-i1profiler.*`) — they silently kept the old
  name before.

## v3.13.12-beta.3

A small polish beta on top of beta.2 — the same opt-in chart-reading engine
(issue #126), plus interface tidying from Sebastian's and Knut's feedback.
With the engine off, nothing about your results changes.

### Clip border ↔ page margins

- When **Use instrument margins** is on (so the four page margins are locked
  to your instrument's limits), the **Left / Right margin box now lights up
  red** whenever the clip-border width and that side's margin disagree — on
  whichever side the clip border is set to. Before, the clip-border-width box
  itself was outlined, which read as if that field were at fault. The margin
  box is the one affected, so that's the one that's flagged now; hovering the
  clip-border-width field explains, in plain language, which value wins and
  why.

### Load buttons are now matching icons

The **Load** buttons on the Measure and Build Profile tabs are now small
icon-only glyphs in each tab's accent colour, matching the Create Chart and
Print tabs (their meaning is in the section heading and a friendly tooltip):

- **Measure → Load chart (.ti2):** a strip of patches with a scan arrow —
  "read this chart".
- **Build Profile → Load measurement data (.ti3 / .txt):** a patch grid with
  a checkmark — "a measured chart".
- **Create Chart → Load profile:** two stacked pages carrying a small patch
  grid — "reopen a project you started earlier".

On the Create Chart tab the **Reveal-folder button** now sits with the other
icon buttons at the top-right of the panel, instead of down by Generate.

## v3.13.12-beta.2

The second beta of the chart-reading engine (issue #126): the same opt-in
engine as beta.1, refined from Sebastian's and Knut's feedback, plus a
round of Chart Layout / Settings polish that applies whether or not the
engine is on. Still **not tested against real measuring hardware** — keep
first sessions supervised. With the engine off, nothing changes.

### Measure preview (engine on)

- **The hover outline now hugs only a strip's patches.** Moving the mouse
  over a strip highlights exactly its column of patches — no longer the
  letter label above them or the white paper beside them. It's taken from
  the chart's own geometry, so it's pixel-exact on every layout, including
  ColorMunki "offset every second strip" charts (where the outline reaches
  the odd strip's last patch, which hangs lower than its neighbours) and on
  every page of a multi-page chart.
- **The split-patch overlay lands exactly on each patch**, on the same hard
  cases — ColorMunki double-density stagger and multi-page charts.
- **Only the actual off-patch is outlined.** A patch that reads far from
  expected gets a red outline on that patch alone, instead of reddening the
  whole strip.
- **Show: expected / measured / both.** A compact selector switches the
  preview between the chart's expected colours, what the instrument
  measured, and the diagonal split of the two — instantly, at any time.
- **Clearer notes.** The autosave reminder now sits as a caption under the
  preview (matching the Create-Chart "colours are approximate" note), and
  the small expected/measured legend sits in the bottom paper margin, out of
  the way of patches, with wording that matches the current Show mode.
- **The "Go to strip" dropdown is gone** — clicking a strip in the preview
  is the only jump control, and guided refinement uses it under the hood.

### Measurement report (new, opt-in)

Turn on **Settings → Beta features → Save a measurement report** and each
finished measurement also writes a dated report: accuracy statistics
(mean / max / 95th-percentile ΔE, standard deviation), the worst patches,
and a comparison against earlier reports of the same chart so you can watch
your inks drift over time. View it from the **Measurement report** button in
the Measure tab's manual panel, or the Tools menu. Off by default; when off,
no reports are written.

### Chart Layout & Settings polish (always active)

- **Font sizes are now shown in points** everywhere they're set (strip
  labels, chart text, clip-border text), the familiar unit from any text
  editor, instead of millimetres.
- **Strip-label underlines** can be inserted as their own text runs, and the
  Chart Layout tab's help icons were refreshed — including a full
  explanation of the strip-indicator style group and of the patch-pattern
  syntax (the `@` token and zero-padding).
- **Instrument Limits** shows each instrument's real maximum strip length.
- **Reveal-folder buttons** on the Measure, Print and Build tabs share one
  icon-only style, tinted in each tab's accent colour, with a distinct
  open-tray glyph; the manual-panel preset dropdowns pick up the same accent.
- **A new "Where are my files?" folder guide** in the Welcome/Help window,
  laid out as a table, now also covers the scanner/camera files and notes
  which are safe to delete.
- **A CMYK+N help card** explains multi-ink charts.
- **ArgyllCMS auto-detect** follows per-binary symlinks to find the `ref/`
  folder, so Homebrew-style installs are recognised.
- The clip-border margin/width fields are no longer greyed out when
  instrument margins are in play.

### The chart-reading engine, unchanged from beta.1

- The **Chart reading** option under **Settings → Beta features** is now a
  simple on/off checkbox (it matches the profile-engine checkbox above it).
- Per-strip autosave, click-to-jump, live split-patch feedback and the
  fixed-order safety net all work as in beta.1. If the engine binary isn't
  present, or a mode it doesn't cover is used, ChromIQ falls back to stock
  chartread and says so. The `.ti3` format is identical either way.

## v3.13.12-beta.1

A beta introducing an optional **ChromIQ chart-reading engine** for the
Measure tab (issue #126), switched off by default. With the option off,
nothing changes — this release behaves exactly like v3.13.11.

**This engine has not yet been tested against real measuring hardware.**
It is offered for testing behind a clearly-labelled beta switch; keep your
first sessions supervised and verify results before relying on them.

### New (opt-in): a ChromIQ chart-reading engine

Enable it under **Settings → Beta features → Chart reading**. It is a fork
of ArgyllCMS's own `chartread`, built from the same source and driving your
instrument with Argyll's own unmodified drivers, so the measurements
themselves are identical. What it adds around them:

- **Per-strip autosave.** Your readings are written to disk after every
  accepted strip. If the instrument disconnects, the app closes or the
  power drops, you lose at most the one strip you were reading — never the
  whole session. Resuming picks up exactly where you stopped.
- **Click a strip in the preview to jump to it.** No more stepping strip by
  strip to re-measure one row; hover shows a hand cursor, and read strips
  are marked. A "Go to strip" dropdown is there too.
- **Live split-patch feedback.** After each strip the preview fills in what
  the instrument saw, split diagonally against what the chart expected — a
  smudged or shifted row is visible immediately (screen colours are
  approximate; the file's numbers are exact).
- **A safety net for fixed-order charts.** On charts whose patches aren't
  shuffled, the engine checks — wherever it is mathematically able — that
  the row you swiped is the row it expected, and warns you on the spot.
  Stock chartread trusts you silently there.

If the engine binary isn't present on a platform, or a mode it doesn't yet
cover is used (patch-by-patch, XY tables), ChromIQ falls back to stock
chartread automatically and says so in the log. The result `.ti3` file has
the identical format, and resuming works interchangeably between both.

## v3.13.11

A small but important fix for anyone whose instrument drops its USB
connection mid-measurement (reported on the forum with an i1Pro).

### Fixed: partial readings were lost when the instrument disconnected during "Save Partial & Quit"

chartread keeps everything you have scanned in memory and only writes the
`.ti3` file at the very end. When a strip read failed with a communication
error and you chose **Save Partial & Quit**, a follow-up USB error
(`ReadPipeAsync failed`) could make ChromIQ kill chartread before it had a
chance to write the file — every strip you had read in that session was
gone, and "Continue Measurement" had nothing to resume from.

ChromIQ no longer stops chartread while the save is still in progress. If
the connection hiccup was transient (a flaky hub or cable contact), the
save now goes through and you can resume later; if the instrument is truly
gone, chartread ends on its own and the failure is reported as before.

The "Strip Read Failed" dialog also explains this now: after a
communication error, **Save Partial & Quit** needs the instrument to answer
one more time — re-seat the USB cable before clicking it.

## v3.13.10

The second feedback round on the multi-ink tools (issue #125), plus a wish
list from the same tester: one crash fixed, two smaller bugs his logs
exposed, a rework of how the clip border and the page margins interact,
and a new folder guide. Nothing changes for charts you have already made.

### Fixed: "y1 must be greater than or equal to y0" when applying a patch set

On dense charts, at certain combinations of patch size, scale and
resolution, rounding a patch position to whole pixels could produce a
rectangle whose bottom edge landed one pixel above its top edge — and the
whole page build aborted with this error. It was rare and looked random;
retrying usually worked. The renderer now simply skips such zero-area
rectangles (they cover no pixels, so nothing is lost) — the same guard the
ink-separated TIFF output always had.

Two more bugs surfaced by the same report's log files:

- Charts whose ink set contains a **White ink** (or light yellow /
  light-and-medium ink families) crashed the i1Profiler export with
  `KeyError: 'W'`. All ink families are covered now.
- After applying a multi-ink chart from the patch-set editor, the preview
  showed a floating "Approximate colours" badge **on top of the Next
  button**. The applied chart's sidecar now carries its ink list, so the
  preview shows the proper per-ink inspector row instead — and if the
  badge ever floats again, it anchors to the top of the preview, away
  from the buttons.

### The clip border and the margins — untangled

Until now, raising "Clip border width" silently copied the value into the
Left margin box — confusing, and wrong when the clip sits on the right.
The two fields are now independent: on the clip's side of the page, the
**larger** of the two (margin or clip-border width) is what gets reserved,
and the field being overruled shows a **red outline** with a tooltip
explaining which value wins and why. Turn the clip border off and both
margins behave normally again. The help texts for Margins, Clip border
width and Side each explain the interplay. (The printed geometry is
unchanged — the layout engine always reserved the larger value
internally; only the confusing display is gone.)

### More from the wish list

- **Clip-border text size** — the Clip-border content frame's Font row
  gained a Size box (mm; "auto" fits the text to the strip as before).
  Handy when the automatic text is larger than you want on a narrow
  strip. Saved in presets and chart recipes. Sheet text already had the
  same control (under its Font row, inside Expert Options).
- **i1Pro margins for A4/Letter Landscape** — the Instrument Margins tab
  now ships jig margins for i1Pro and i1Pro 3+ on A4 and Letter in
  landscape too (the jig reads those sheets sideways just fine), same
  values as portrait. If you customised those combos yourself, your
  values are kept.
- **Strip / patch pattern help** — both fields' help now shows four valid
  example patterns each and explains, honestly, how a pattern is
  interpreted (letters when it contains "A-Z", plain numbers otherwise)
  and how the two combine into a location like A12.
- **"Where are my files?"** — the Welcome/Help window (the "?" button)
  has a new card: a folder guide listing every file a ChromIQ project can
  contain — which feature creates it, when, and what it's for — ending
  with what's safe to tidy up. The "Where are my files.txt" dropped into
  each project folder was updated to match.
- The chart-layout information panel now shows how many of a chart's
  patches are paper-white **strip fill-up** ("… of those, fill-up"), and
  the engine's build log spells the same thing out — so a chart growing
  from, say, 896 designed patches to 910 printed is explained where the
  numbers appear, not just in the release notes.

Everything is translated in all 13 languages, as usual.

## v3.13.9

A quick patch release for the first round of user feedback on the
multi-ink chart tools (issue #124) — one real display bug, one silent
behaviour made visible, and a long-overdue rewrite of the chart
generator's help. Nothing else changes.

### Fixed: extra-ink patches showed as white swatches

On a CMYK + extra inks chart, patches made only of an extra ink — an
orange ramp, a red/green pair overprint, an orange+green+violet triple —
appeared as pure white in the patch-set editor's swatch grid (and in the
chart preview). The preview colour was computed from the CMYK channels
alone, so a patch with no CMYK in it looked like bare paper.

Every extra ink now contributes its real colour to the preview, using the
same per-ink colour model the separated-TIFF view already used. A 32-step
orange ramp shows 32 distinct swatches from pale peach to full orange.
Plain CMYK and RGB charts render exactly as before, to the pixel.

### Explained: the patch count that grew on its own

Designing 896 patches and ending up with a 910-patch chart was correct —
measuring instruments read whole strips, so the layout tops up a partial
last strip with paper-white patches, exactly as Argyll's printtarg has
always done (they are printed and measured like any others; the profile
just gets a few extra readings of the paper). But it happened silently.

Now the Create Chart log spells it out after applying a chart ("896
designed + 14 paper-white fill-up patches completing the last strip =
910 total"), the editor's save summary carries the same note for engine
charts, and the help documents the behaviour.

### The "Generate colour sets" help, rewritten

The main help still said "these five sets" while the panel had grown to
sixteen, never mentioned the multi-ink sets at all, and left three
things unexplained that this release's bug report reasonably read as
bugs:

- why the RGB-cube sets are greyed out on multi-ink devices (they trace
  the RGB colour cube, which a multi-ink printer doesn't have — "Even
  coverage" is their replacement), and why the look-based sets unlock
  once a preconditioning profile is set;
- why the 3D preview disappears for a multi-ink chart until a
  preconditioning profile provides an honest colour model;
- why "Pure white & black · each: 1" can add 0 patches (whites and
  blacks the other ticked sets already contribute count toward your
  number, so the chart ends with exactly N of each, never doubles).

The help now describes every set in on-screen order — including
Gamut-corner emphasis, Sunrises, Flamingos, Colour extremes and Pure
white & black, which were missing entirely — plus a "Multi-ink devices"
section with the exact availability rules, the white/black arithmetic
with a worked example, and the strip fill-up behaviour. Fully translated
into all 13 languages, as usual.

One small visual fix rode along: the info icon of "Highlights & shadows"
sat on the wrong row (overlapping the Near-neutral greys icon) — every
set now has its own.

## v3.13.8

A stable release with two jobs: it ships this cycle's new work, and it
properly tells the story that the v3.13.7 stable notes compressed into two
bullets — several major features only ever appeared in beta notes that
stable-channel users never saw. Nothing that existed before v3.13.7
changes behaviour; every new capability is opt-in or only appears for the
devices it concerns.

### The ChromIQ profile engine — the proper introduction

ChromIQ now contains its own profile builder next to Argyll colprof. It is
**off by default**; turn it on under Settings → Beta ("ChromIQ profile
engine"). With it enabled, the Build Profile tab lets you build with
colprof (still the default and the reference) or with the engine — same
measurement files, same options, so you can build both and compare.

Why it exists: colprof cannot build profiles for printers with more than
four inks. The engine can — CMYK plus orange, green, violet, light inks —
which closes the whole multi-ink loop inside ChromIQ: design the chart,
print, measure, build, refine.

It comes in three flavours (Settings → Beta → Accuracy):
- **Fast** — ChromIQ's own implementation of colprof's method, validated
  against Argyll; quickest.
- **Bit-exact** — for standard printers the profile is built by real
  colprof (identical to Argyll); for multi-ink printers a bundled helper
  runs Argyll's genuine gamut-mapping code.
- **Maximum accuracy** — the most careful build: your repeated
  white/black patches are averaged instead of trusting one reading, the
  smoothing is chosen for your specific chart by cross-validation, a
  smudged patch is survived rather than baked in (and named, so you can
  remeasure it), deep shadows keep their resolution, and the total-ink
  limit is honoured in the least-damaging way. On our synthetic test
  bench it matched or beat colprof on colours it had never seen. Builds
  show live progress with an estimated remaining time.

Also part of this cycle and honoured by colprof and all engine modes
alike: **Black generation (-k / -K)** in Build Profile → Manual — control
how much black ink your profiles use for dark colours, every rule
explained in plain language.

### Multi-ink chart creation — also finally in a stable changelog

The New Patch Set and Add windows (Create Chart → patch-set tools) design
charts for ink devices, not just RGB:
- **Device choice**: Print RGB (the unchanged default), CMYK, or CMYK +
  extra inks as removable chips — with a first-class ink limit and an
  optional preconditioning profile, validated against the ink set.
- **Multi-ink colour sets**: even coverage (targen), per-ink ramps,
  ink-pair overprints, grey-balance rings, white/black ink anchors — and
  with a preconditioning profile, all the look-based sets (skin tones,
  oceans, foliage…) translate into real ink values, with an honest note
  for colours outside the printer's gamut.
- **New in this release**: *Ink-triple overprints* (the dark three-ink
  mixtures that pairs never reach) and a *Rich-black ramp* (dark greys
  from colour ink plus black — exactly the measurements black generation
  learns from). Plus a round of correctness fixes: the gap filler now
  always respects the ink limit (it could previously exceed it), ramps
  and anchors honour limits below 100%, the grey-balance rings are now
  genuinely re-centred on the printer's measured neutral when a
  preconditioning profile is set (the tooltip had promised it; now the
  code does it), the build order matches the panel order, targen's count
  reads "≈", and greyed-out rows grey their size controls too.
- Charts save as true separated TIFFs (each ink a named channel, opens
  correctly in Photoshop and RIPs) with an optional press-ready
  **vector-PDF** export.

### The chart preview (TIFF viewer) — the multi-ink upgrades

- **True-colour preview**: with a preconditioning profile the preview
  renders a multi-ink chart's actual colours through it, with a badge
  saying so; without one, the approximate composite is clearly labelled
  and blends extra inks physically (linear light, measured absorption).
- **Per-ink inspector**: an "Inks:" row for device-native charts — hide
  individual inks to see what the others lay down, and read exact ink
  values under the cursor.
- **Honest 3D views**: with a preconditioning profile, the patch-set 3D
  panels plot multi-ink patches where the profile predicts them in Lab.

### New engine options in this release

Four options in Build Profile → Manual → Color Science, visible only
while the engine's Maximum accuracy mode is active, each with an
extensive plain-language tooltip, each saved with defaults and presets:
- **Spectral physics model** — a physical model of ink-on-paper for
  multi-ink printers with spectral measurements. It must beat the
  standard model on your own chart before it is used, so it can only win
  or change nothing. On the test bench, multi-ink profiles came out
  20–36% closer to the true colours.
- **Measurement noise handling** — diagnoses how noisy your measurement
  really was (from the repeated patches) and only engages when the chart
  is measurably noisy; on a clean chart your profile is bit-for-bit
  unchanged. Prints a per-region confidence map either way.
- **ICC profile version** — v2 (classic, most compatible), v4 (modern,
  with a built-in integrity checksum), or Both (a "-v4.icc" twin next to
  the normal file).
- **Out-of-gamut rendering** — keep the Argyll-matched rendering
  (default) or try ChromIQ's new mathematically-exact mapping and judge
  the look on your own prints.

### How much to trust all this (assessment by Claude, ChromIQ's
### development assistant — not by the project owner)

None of the new colour machinery has been validated on real printing
hardware yet. What it HAS been validated against: a synthetic test bench
of six mathematically exact "printers" (where the true colour of every
patch is known), held-out benchmarks on real measurements, ~2 000
automated tests including bit-identity checks, and ArgyllCMS's own tools
(iccdump, icclu, ColorSync, littleCMS). My confidence, stated plainly:
**high** that nothing that worked before behaves differently — defaults
are untouched, colprof paths are untouched, and the opt-ins are built to
stand aside rather than degrade anything; **medium-high** that the
measured accuracy gains carry over to real prints — the test bench was
built to be realistic, but paper and ink get the final vote;
**deliberately unproven** for how the new out-of-gamut rendering LOOKS —
numbers cannot judge taste, which is why it is not the default. Print a
test image before trusting any newly built profile for real work — that
advice is not new, but it carries extra weight for these features.

### The technical version

- Engine (issue #123): candidate framework with a synthetic ground-truth
  battery, ICC-byte referee and pre-registered promotion gates
  (benchmarks/). Implemented and benchmarked: CAM16-UCS fitting, ADMM
  joint separation, heteroscedastic noise model (GLS with banded
  model-error floor, λ hill-climb, z-score outlier logic with a
  reject/report split), cellular-free YNSN spectral hybrid with
  Saunderson flare (deployed via held-out challenge + L² projection onto
  the CLUT lattice), bijective radial rendering intents in CAM16-UCS
  (closed-form inverse ⇒ exact -nI). Gates verdict: nothing promoted
  into the accurate-mode defaults; spectral physics and noise handling
  ship as safe-by-construction user options, CAM16-UCS fitting and
  joint separation remain dark (measurably not better under the ΔE2000
  referee), the bijective renderer ships as an explicit style choice.
  Full data in issue #123.
- ICC v4 output: v4.4 header, mluc metadata, MD5 profile ID per
  ICC.1 §7.2.18; LUTs remain lut16Type (legal in v4, legacy PCS
  encoding preserved — colour tables byte-identical to v2). Verified
  against ColorSync and littleCMS.
- Patch generators (N-channel): ink-limit enforcement in fill_gaps_nd
  (simplex projection of candidates and Lloyd samples), per-ink ramps
  and K anchor capped at min(100, limit); ink_triple_overprints
  (C(n,3) trios ≤ L/3 by construction); rich_black_ramp (neutral CMY ×
  K-substitution grid); profile-recentred grey-balance rings
  (device-space ring offsets preserved); nch build order = panel order.
- Maximum accuracy internals (shipped across the v3.13.7 rebuilds,
  documented here): endpoint averaging, cross-validated smoothing,
  Huber IRLS with remeasure report, boundary-aware inversion, Euclidean
  TAC projection, hue-preserving clip, measured extra-ink hues, shaped
  XYZ-PCS tables; black generation -k/-K as a faithful icxKcurveNF
  port; granular build progress, now with a smoothed remaining-time
  estimate; Windows/ARM vector-PDF FreeType bundling fix.
- Test suite is now two-tiered: `pytest` runs the everyday tier,
  `pytest --runslow` adds the heavy end-to-end build tests and is the
  release gate.

## v3.13.7

Stable.

- Refining a profile is smoother: the "Use as pre-conditioning profile"
  option now also carries the profile into the Manual module's targen
  settings, so switching Guided → Manual to refine no longer starts with a
  blank pre-conditioning field.
- All 13 interface languages are now fully translated.

Also included, off by default and clearly marked experimental: an optional
ChromIQ profile engine for multi-ink (6-ink and wider) printers that
ArgyllCMS colprof can't profile, with a bit-exact gamut-mapping option. It's
new and not yet tested on real multi-ink hardware — verify any profile with a
test print before relying on it.

## v3.13.7-beta.6

- **Bit-exact gamut mapping now works on Windows and Linux**, not only macOS —
  the bundled helper is built for every platform. On Windows arm64 it falls
  back to the fast mapper if the helper isn't present.
- **Translations completed**: all 13 interface languages are now fully
  translated; several were still partly English placeholders before.

## v3.13.7-beta.5

Adds a bit-exact gamut-mapping option to the profile engine and extends the
profile accuracy check to multi-ink profiles. Both are opt-in; the profile
engine is still off by default.

- **Bit-exact gamut mapping** (Settings → Beta → Gamut mapping). "Fast" uses
  ChromIQ's built-in mapper. "Bit-exact" uses ArgyllCMS's own gamut-mapping
  code instead: for RGB and CMYK printers the profile is built with colprof
  directly, so it matches Argyll; for 6-ink and larger printers — which
  colprof can't build — a bundled helper runs Argyll's gamut mapper on the
  profile the engine builds. It takes a little longer than Fast.
- **Accuracy check for multi-ink profiles**: Check & Refine now works on
  6-ink and larger profiles, which stock profcheck won't read. The
  illuminant, observer and paper-whitener (FWA) options are honoured,
  computed from the measurement's spectral data.
- **Settings**: the profile-engine toggle and the gamut-mapping option now
  live on a separate "Beta" tab.
- Fixes to the multi-ink build and the ≤4-ink destination-gamut step.

## v3.13.7-beta.4

Profile engine (#122): the engine now covers colprof's full option
surface, and its perceptual rendering is built by ChromIQ's own port of
Argyll's gamut-mapping algorithm. Still optional and off by default.

- **Perceptual rendering, natively**: the engine's perceptual table is
  computed by a line-by-line port of Argyll's gamut mapping (gammap /
  nearsmth, AGPL-3.0, Graeme W. Gill — see workflow/profile_engine/
  gammap_port/). It runs in the same CIECAM02 appearance space colprof
  uses and was validated against Argyll's own mapping code to well
  inside colprof's build-to-build variation. No background colprof run
  is needed for the perceptual table any more; the saturation table
  still uses the colprof-matched path while its port converges.
- **Full colprof option surface**: spectral -i/-o illuminant/observer,
  FWA compensation (-f), XYZ PCS (-a x), -r/-b/-ni/-np/-no/-nc/-nI/
  -nP/-nS/-Z/-A/-M/-u/-R, -t/-T intent presets, -c/-d viewing
  conditions, gamut source from any RGB/CMYK profile (including v4).
  Unknown extra flags still route the build to colprof, named in the
  log.
- **Pre-conditioning hand-off (#44)**: the "Use as pre-conditioning
  profile" button in the Build Profile and Check & Refine result
  dialogs now also pre-fills the Manual module's targen expert option
  (Pre-conditioning Profile, -c), so switching to Manual finds the
  profile already in place.

## v3.13.7-beta.3

The ChromIQ profile engine (#122) — a profile builder inside the app, next
to Argyll colprof. Optional and off by default; colprof remains the default
engine everywhere.

- **Settings → Behaviour → "ChromIQ profile engine (beta)"**: turning it on
  adds a small "Profile engine" choice to the Build Profile tab — Argyll
  colprof (default) or ChromIQ engine (beta). Build the same measurement
  with both and compare; measurement files are never touched.
- **Multi-ink profiles**: measurements from multi-ink charts (CMYK plus
  orange, green, violet…) — which colprof cannot process — build
  automatically with the ChromIQ engine. Together with the multi-ink charts
  from Create Chart, the whole loop now closes inside ChromIQ: print,
  measure, build, use as pre-conditioning profile.
- **Loss-free rule**: the engine only takes a build it fully covers.
  Options it doesn't do yet (spectral illuminants, FWA, custom smoothing,
  extra command-line flags…) keep the build on colprof, and the log names
  the reason. The standard gamut sources (ClayRGB / sRGB) are covered,
  with perceptual and saturation tables built from them (approximate —
  the colorimetric intents are the reference).
- **Accuracy** (measured on real printers): at the same quality level the
  engine's colour accuracy sits at colprof's level for RGB measurements;
  profiles pass ColorSync verification and open in all Argyll tools.
- Multi-ink profiles work in every downstream tool: previews, Lab 3D
  views, profile-guided patch sets and lookups fall back transparently
  where Argyll's own tools stop at 4 ink channels.

## v3.13.7-beta.2

The multi-ink preview round (#72 Tier D), plus fixes from live testing.

- **True-colour chart preview**: when a multi-ink chart's preconditioning
  profile is known, the preview renders the actual colours through it
  (cctiff), with a badge saying so; without one, the approximate composite
  is clearly labelled — and its extra-ink blending is now done in linear
  light with absorption from real ink measurements.
- **Per-ink inspector**: device-native charts get an "Inks:" row — hide any
  ink to see what the others lay down, and read the exact ink values under
  the cursor. Resets the moment a new chart is generated.
- **Lab-space 3D views**: with a preconditioning profile, the New-patch-set
  3D panel and the Tools "Show patch distribution (3D)" window plot multi-ink
  patches where the profile predicts them in Lab — the honest distribution
  picture (the RGB projection remains, clearly named, when no profile is set).
- Generator options for multi-ink devices are remembered between sessions;
  3D preview stays hidden when a remembered multi-ink setup reopens; compact
  profile-row buttons; ink-limit ⓘ aligned; the patch-set window stays on
  top after choosing a profile.

## v3.13.7-beta.1

The other half of multi-ink profiling (#72): CMYK / CMYK+N **patch sets** can
now be designed, generated and edited — not just rendered. German is fully
translated; the other languages follow before the final release.

- **New patch set → Device**: choose Print RGB (unchanged default), CMYK, or
  CMYK + extra inks (orange, green, violet, light inks… as removable chips),
  with a first-class **ink limit** and an optional **preconditioning profile**
  (validated inline against the chart's ink set).
- **Multi-ink colour sets**: Even coverage (targen), per-ink ramps, ink-pair
  overprints (always inside the ink limit), the near-neutral rings as a true
  grey-balance set, white/black ink anchors — and with a preconditioning
  profile, all the look-based sets (skin tones, blues, greens…) translate into
  ink values, with an honest note when colours sit outside the printer's gamut.
- **Editor**: multi-ink charts load, reorder, re-render and save through the
  ChromIQ engine (press-ready separated TIFF + i1Profiler files included);
  per-ink patch tooltips; RGB-only actions are cleanly gated.
- **Profile build**: colprof's ink limit (-l) is prefilled from the chart's
  own limit, carried through .ti1 → .ti2 → .ti3 automatically.
- Generator rows whose set is off (or not available for the current device)
  now show their count struck through, so the total is easier to follow.

## v3.13.6

Stable. Multi-ink profiling in the layout engine (device-native CMYK/N TIFFs +
a full-vector PDF export), and a thoroughly reworked scanner/camera profile
builder with detailed, per-context colprof settings (#72, #121). All 13
languages are fully translated.

### Highlights (see the beta notes below for detail)
- **Device-native CMYK / CMYK+N charts** and a **vector-PDF chart export** from
  the layout engine (#72).
- **"Build profile with scanner or camera"** — renamed, and rebuilt to mirror
  the Build-Profile tab's Manual module: grouped, labelled colprof controls with
  a live command preview, ClayRGB1998 preselected as the printer gamut source,
  input-profile white-point handling, and settings remembered separately for a
  printer profile vs a chart-scanner vs a standard-target profile (#121).
- Every ⓘ tooltip is beginner-first, and now translated into all 13 languages.

## v3.13.6-beta.4

A beta for review — finishes the tool rename (#121, Knut).

- **The new name "Build profile with scanner or camera" now appears in every
  help text** that mentions the tool — the welcome guide, the target-tool's
  saved-files message, the landing page and the bundled-target README. A few
  references had been split across lines and missed the first pass; their
  translations are restored, German included.

## v3.13.6-beta.3

A beta for review — Knut's second round of feedback on the profile builder (#121).

### Scanner / camera profile settings (#121)
- **Settings are now remembered separately for each kind of profile.** A printer
  profile, a scanner profile from a ChromIQ chart, and a scanner profile from a
  standard target each keep their own profile type, quality, description and
  Advanced choices. Switching "Profile my printer from this scan" on/off, or
  between "A chart I made in ChromIQ" and "A standard target I own", loads that
  context's own settings — and "Save as Defaults" saves just the active one.
- **The tool is renamed "Build profile with scanner or camera"** — the old name
  didn't convey that it can also build a *printer* profile (with the scanner as
  the measuring instrument). The window title still switches to "Build printer
  profile" when that mode is on.

## v3.13.6-beta.2

A beta for review — Knut's feedback on the scanner/camera profile builder (#121).

### Scanner / camera profile settings (#121)
- **The Advanced window now mirrors tab "4 Build profile" → Manual exactly** —
  the same grouped sections (Measurement & Smoothing, Gamut Mapping, Profile
  Metadata, Advanced), the same checkbox-gated controls, and the same
  (-flag) labels — so a user who knows one knows the other. The free-form
  "extra arguments" box is gone; every option is now a proper, labelled control.
- **The gamut source ("colour space") is a clear dropdown**, and **ClayRGB1998
  (Adobe RGB) is preselected** as the default source for a printer profile —
  the right choice for most photographic workflows.
- **All applicable options are offered for both paths.** The scanner path now
  also exposes the profile Model, dark-region emphasis, the full set of
  curve/embedding diagnostics, and colprof's input-profile **white-point
  handling** (auto-scale -u, absolute -ua, clip-highlights -uc, or a manual
  scale) plus the primary clamp (-R); the printer path adds the rendering-intent
  overrides and the B2A table quality. Printer-only and scanner-only options
  never leak into the other kind of profile.
- **The window title now follows the mode** — it reads "Build printer profile"
  when "Profile my printer from this scan" is ticked, and the default profile
  type switches to Lab cLUT (and is labelled "(default)").
- **Every dropdown marks its default** with "(default)" so the recommended
  choice is obvious at a glance.
- **A "Save as Defaults" button** (next to Advanced…) remembers the current
  settings for next time — settings are no longer written silently on every
  change.
- **The command preview updates live** with every selection, and the
  gamut-source file picker opens on — and pins a shortcut to — Argyll's ref/
  folder. All the ⓘ tooltips are beginner-first (friendly, plain-language,
  current behaviour only), and the folder/ⓘ icons use the window's green accent.

## v3.13.6-beta.1

A beta for review. Multi-ink profiling comes to the layout engine (device-native
CMYK/N TIFFs + a crisp vector-PDF export), and the scanner/camera profile builder
gains detailed colprof settings.

### Scanner / camera profile settings (#121)
- **The "Build scanner or camera profile" window now exposes the main colprof
  settings** — profile type (-a), colour space, and quality (-q) — next to each
  other, using the same method and (-flag) label style as tab "4 Build profile".
  The defaults reproduce the previous output (shaper + matrix, medium).
- **An "Advanced…" button** opens the less-common options (average deviation -r,
  no input curves -ni, manufacturer -A, copyright -C, and free-form extra
  arguments), each showing its default and remembering your last value.
- **The window shows the exact colprof command** your current settings will run,
  updating live as you change them.
- **"Profile name" is now "Profile description (-D)"** with scanner-appropriate
  naming examples.
- All settings are remembered between runs; **Restore factory defaults** in
  Preferences clears them back to the defaults.

### Improvements
- **The engine writes device-native CMYK and CMYK + extra-ink charts.** A
  multi-ink chart is now saved as a true separated TIFF — every patch carries
  its exact ink values (not an RGB picture of them), each ink is a named
  channel, and the file opens correctly in Photoshop and print RIPs. Coloured
  contrast spacers and the notes strip keep their colour in the ink channels,
  matching printtarg. RGB charts are unchanged.
- **New "Also export a PDF" option** (Create Chart → Manual → Expert →
  Output). Ticking it saves a press-ready PDF next to the usual TIFF. It's true
  vector — the patches are exact device colours, the labels stay crisp at any
  zoom, and it uses the same fonts as the chart — with all pages in one file.
  CMYK+N charts carry each ink as a named separation, so a RIP knows exactly
  which ink is which. File → Properties states the colour space (e.g. "CMYKOG
  (6-channel)"). The choice is saved in presets and restored when a chart is
  reloaded.

### Fixes
- The DeviceN preview tint (used when previewing or printing multi-ink charts)
  no longer renders every ink as magenta — each ink previews as its real
  colour. This only affected on-screen preview; the printed ink channels were
  always correct.
- Several downstream tools (the scanner-geometry capture, the TIFF ID stamps,
  the margin inspector) no longer warn on the new device-native charts.

### Under the hood
- The vector PDF is drawn from the same collected geometry as the TIFF, so the
  two cannot diverge; glyph outlines come from the chart's exact fonts via
  freetype. Fidelity is guarded by structural tests that check every patch's
  exact device value and position in the PDF.
- New translations for the PDF-export strings in all 13 languages.

## v3.13.5

Chart notes and the stamp choice now survive a reload — a chart put back on
screen shows everything it was made with. Thanks to mavtop for the report.

### Improvements
- **Chart notes and the "Stamp targen …" checkbox are restored when a chart
  is loaded.** Every newly generated chart — layout-engine and printtarg
  alike — records both values alongside its layout, and opening the project
  (or the `.ti2`) puts them back exactly as they were. Charts saved with an
  earlier ChromIQ don't carry this information, so loading them leaves the
  two fields untouched and behaves exactly as before.
- **Presets carry the notes and stamp choice too.** Saving a user preset
  (★) stores both values; loading it brings them back. Presets saved with
  an earlier ChromIQ keep their current behaviour.
- **The message after loading a chart now says precisely what was
  restored** — it no longer mentions chart notes when the loaded chart
  carries none.

### Under the hood
- Both values live in the chart's `channels.json` sidecar; the restore is
  gated on the keys being present, so nothing changes for existing files.
- The restored stamp value is applied after the layout-engine toggle, whose
  mode default would otherwise overwrite it — pinned by a regression test.
- 6 new tests; the 2 new log messages are translated in all 13 languages.

## v3.13.4

Knut's edge-detection redesign lands as stable: the misalignment check now
senses exactly where it reads — no more, no less — plus chart-settings
restore on reload, and a fully translated release in all 13 languages.

### Improvements
- **Patch-edge detection follows Knut's activation-box design, verified
  measurement by measurement over eleven beta rounds.** Every patch carries
  a 30×30 grid of sensing cells over an 85 % equal-margin box (the coverage
  chosen by comparing 85/90/92/95 % on real and synthetic scans — 85 is the
  only one that never false-flags an aligned target). Only the cells around
  the reading box are awake — the box plus one thin ring outside it,
  following the *Patch sample area* setting in and out — and the localised
  edge operator guarantees a cell fires only on an edge that genuinely
  overlaps it, so deactivated outer rings truly shield. On the reference
  scans, every correctly aligned target reads zero flagged patches at every
  sample area from 20–80 %, while a quarter-patch shift flags dozens to
  hundreds and a single pulled corner is caught reliably.
- **Reading boxes use equal margins on all four sides** at every *Patch
  sample area* setting, and the sampled area is exactly the chosen
  percentage — pinned by tests to the pixel.
- **Loading a chart restores its creation settings.** Opening a `.ti2` from
  Print or Measure now fills Create Chart with the chart's own patch size,
  spacers, margins, seed, notes and patch count (charts made with the
  ChromIQ layout engine carry a complete recipe; printtarg charts restore
  instrument, paper and count). Thanks to mavtop for the request.
- **File dialogs open with a readable sidebar** — the location shortcuts
  panel no longer starts squeezed to a sliver.
- **New defaults from the beta round's field testing** (one-time migration;
  values you chose yourself are never touched): placement-agreement floor
  0.85, edge warning at 2 patches, sensing-cell run of 8 (range now 2–20 —
  the value counts real cells of the 30×30 grid, exactly as set), edge
  strength 0.20.
- **All help texts for the misalignment checks rewritten** — plain-language
  outcome first, precise mechanics after, and strictly describing the
  behaviour as implemented.
- **Complete translations in all 13 languages** — every text added during
  the 3.13.4 cycle is translated in German, Spanish, French, Italian,
  Japanese, Dutch, Norwegian, Polish, Portuguese, Russian, Swedish and
  Simplified Chinese.
- ChromIQ is free and always will be — if it saves you time or ink, a
  coffee on [Ko-fi](https://ko-fi.com/itsab1989) is a kind way to say
  thanks.

### Thanks
Eleven beta rounds of exact, patient measurement by **Knut** shaped the
edge detector — the activation-box design, the 85 % sensing grid and the
literal cell counting are his. The chart-settings restore came from
**mavtop**'s report.

## v3.13.4-beta.11

Knut's beta-10 field test (#119): the edge check fired while a border was
still ~10 % of a patch away from the sample box — observably "as if the
outer sensing rings never disabled". His observation was correct; the cause
was in the detector, and it's fixed at the root.

### Fixed
- **The edge operator is now localised, so a disabled sensing ring truly
  shields the cells behind it.** The old detector took the raw |centred
  difference| of the image, which lights every pixel whose ±4 px window
  merely CROSSES a border — a halo around the true edge line. A border
  sitting past a deactivated outer ring could therefore still light the
  outermost awake cell, which is exactly the too-early triggering Knut
  measured (~10 % of a patch at a 40 % sample area). The operator now keeps
  only the crest of its response (non-maximum suppression along each axis),
  which sits on the border's own transition zone — a sensing cell fires
  only when the edge line genuinely overlaps that cell. Verified on his
  protocol: the trigger distances collapse from ~10–16 % of a patch to the
  activation box's own edge plus the scan's physical blur, and detection
  gets stronger, not weaker (real-scan quarter-shift and pulled-corner
  counts all rise). The aligned matrices improve too: the real LaserSoft is
  now silent through a 50 % sample area (beta.10: flagged from 30 %), the
  real Wolf Faust and all five demo renders stay at zero everywhere.
- **"…needing this many sensing cells in a row" now counts literal cells,
  exactly as set** (Knut's correction): 6 means a straight run of 6 cells
  of the 30×30 sensing grid, 8 means 8 — the beta.10 conversion to a
  20-cell reference scale is gone. The maximum of 20 means 20 of the 30
  cells along one side. The default stays 8. Help text rewritten to say
  precisely this (German included).

### Added
- The reply on #119 documents which sensing cells are awake at every
  Patch-sample-area setting — table plus rendered diagram
  (`docs/dev/119-activation-map.png`), directly from the shipped geometry.

## v3.13.4-beta.10

Knut's grid-coverage verification round (#119): the sensing grid moves to
85 % of each patch — measured, not assumed — and the help texts catch up
with the implemented model.

### Changed
- **The edge check's sensing grid now covers 85 % of each patch's width and
  height** (Knut's spec, confirmed by measurement — he asked for the 90/92/95
  comparison that beta.7 skipped). The grid box is built with the same
  equal-margin rule as the *Patch sample area* box, so the two always stay
  parallel and share their height-to-width relationship on every patch
  shape. The comparison over both real 600 dpi IT8 scans and all five demo
  renders shows why 85 is right: it is the only coverage at which every
  truly-aligned target stays at zero flagged patches at every sample area
  from 20–80 % (at 90 % even a pixel-perfect CMP Studio render flags 3,
  at 92 % the LaserSoft DC Pro demo flags 8, at 95 % the real Wolf Faust
  flags 4), while detection stays sharp — a quarter-patch shift still
  fires with 11–308 flagged boxes depending on the chart. On the real
  scans the change is a pure win: the Wolf Faust is now silent at every
  sample area, and the LaserSoft's truthful reporting of scanin's local
  placement error settles at 31 boxes instead of 55.
- **"…needing this many sensing cells in a row" now defaults to 8 and runs
  up to 20** (Knut's numbers: 6 never false-triggered in his testing, 8
  adds buffer; the raised ceiling leaves room on rough scans). The value
  still means "out of 20 cells across one reading box" and is converted to
  the same physical line length on the finer 30×30 grid automatically. A
  one-time settings migration moves everyone still on a stored default
  (3 or 6) to 8; a deliberately chosen value is never touched.

### Fixed
- The help texts for the two edge-detection settings and the *Patch sample
  area* control described the old 20×20 fixed-sensing model. They now
  explain the implemented design — the 30×30 sensing grid over the 85 %
  equal-margin box, the activation ring that follows the sample area in
  and out, the 20-cell reference scale of the row-length setting and where
  the new default 8 comes from (Knut's request, with the German
  translations updated to match).

## v3.13.4-beta.9

Knut's activation-box design lands in full (#119) — his correction to the
beta-7 reading was right, and the fixed cap is gone.

### Changed
- **Edge detection implements Knut's refined sensing model, uncapped.** The
  sensing grid is now 30×30 sub-cells over 95 % of each full patch, and only
  the cells the activation box touches (the real sample box plus half a
  sub-cell on every side) detect — so exactly one thin ring senses ahead of
  the sample area's rim, at every *Patch sample area* setting, and at the
  80 % maximum the grid's own outermost ring is the one awake. Knut's
  challenge to the beta-7 "blur wall" reading was correct: the numbers
  behind the old 52 %-per-side cap were the probe detecting REAL local
  placement error in the test fixture (verified on the scan pixels — the
  LaserSoft's bottom rows genuinely overlap their neighbours by 5–10 %
  under scanin's own solved placement), not an optical limit at those
  areas. The fixed cap is removed.
- **The sensing window yields only to the page's own measured blur.** The
  probe measures each scan's border transition width (10–90 %, sampled
  across ~150 patch borders) and stops the activation from growing only
  where its sensing edge would enter that zone — because there, everything
  reads "edge" even on a perfectly aligned grid (demonstrated on the
  pixel-perfect demo renders: 23–553 aligned patches flagged at 70–80 %
  without the hold; with it, ZERO on every demo target at every sample
  area from 20–80 %, while a quarter-patch shift still fires with dozens
  to hundreds of hits). Nothing is hard-coded: a sharp, coarse-pitch chart
  keeps rim-following almost to the maximum; a soft scan of a dense chart
  holds earlier, exactly where its own optics demand.
- The straight-run rule's cell count now scales with the grid (default 6 on
  the old 20-cell grid = 9 on the 30-cell grid), so the finer grid doesn't
  quietly lower the physical bar that keeps grain streaks out; and the
  grain floor comes from a fixed inner region instead of the active cells,
  so the threshold means the same thing at every sample-area setting (at
  small areas the active window covered only squeaky-clean patch centres
  and ordinary grain lit up as "edges").

### Verified (Knut's requests)
- The full aligned matrix (20–80 % sample areas) and the trigger-distance
  table were regenerated for both real scans and the demo targets — see
  issue #119. The sample-area arithmetic he spot-checked on the CMP-4 demo
  (230 px patch at 60 %) is pinned by a test at his exact numbers: the
  drawn box is 178.16 px per side = 59.99…% of the patch area; the extra
  ~2 px in a screenshot measurement is the 1.4 px outline, which is stroked
  centred on the mathematical boundary.

## v3.13.4-beta.8

Loading a chart now restores the settings it was made with (a
printerknowledge.com request), and the ChromIQ file dialogs got a usability
pass.

### New
- **Reloading a chart brings its creation settings back.** Whether you open
  a saved profile in Create Chart or load a `.ti2` from Print/Measure, the
  options now show the values the chart was actually made with instead of
  stale defaults: for charts made with the ChromIQ layout engine that is
  everything — patch size, spacers, margins, seed, notes, pages and the
  patch count (pinned to the chart's real total) — read from the chart's own
  `channels.json`; charts made with printtarg (or an older ChromIQ) restore
  instrument, paper and patch count, and a friendly note says which of the
  two happened. The reflected-chart dialog's promise that unlocking starts
  "from these settings" is now literally true.
- The **Chart-layout-information panel fills its "on screen" column** when a
  saved profile is opened in Create Chart (it stayed all dashes before), and
  the **"estimate" column recomputes from the restored settings** right
  away, so both columns and the option panels tell one story.

### Fixed
- **The ChromIQ file dialogs open with a readable sidebar.** The shortcuts
  column was so narrow the location names were cut off and every dialog
  needed a manual resize first; it now opens at a comfortable width (and
  stays user-resizable), and dialogs open at a sensible size.
- **Six dialogs that still used the operating system's file picker now use
  the ChromIQ one** (saving spot readings, saving an ICC in Build Profile,
  layout-preset export/import, clip-template export, and the layout editor's
  image loader — which gained the thumbnail preview), so the
  native-dialogs setting is respected everywhere and every picker carries
  the sidebar shortcuts.

## v3.13.4-beta.7

Knut's beta-6 round (#119): the stuck-at-100 % agreement bug, the CMP Studio
mid-grid drift, and his activation-box edge-detection design.

### Fixed
- **Placement agreement no longer sticks at 100.00 % (#119).** On realigned
  charts (LaserSoft, CMP Digital Target 4) the sample-area shrink/grow
  round-trip left each box with its own sub-unit rounding; the probe's pitch
  detector mistook that float scatter for a ~0.002-unit "pitch", the whole
  measuring ladder collapsed onto one spot, and every position read
  identically — 100.00 % everywhere, even a patch off. A gap now only counts
  as the pitch when it is at least a quarter of a box wide.
- **The interior of the grid no longer drifts off the image mid-chart
  (Knut's CMP Digital Target Studio find).** The old "integer edge" rebuild
  placed interior columns for the corner distance's exact pixel size — a
  hand-placed corner is a few pixels off, which shifted the remainder
  distribution and dragged middle columns up to ~15 % of a patch off the
  image (corners and edge columns looked fine). Every chart now uses its own
  float geometry in all three places — the drawn grid, the prepared `.cht`,
  and the demo scans, which are rendered on that same geometry — so they
  agree at any placement, and real scans (which were never integer-edged)
  gain accuracy too.

### Changed
- **Edge detection follows the sample area's rim (Knut's activation-box
  design, #119).** The sensing grid (20×20 sub-cells) always covers 95 % of
  each full patch; which cells actually detect is decided by the activation
  box — the real sample box plus half a sub-cell on every side — so a small
  sample area only wakes the middle of the grid and detection triggers when
  a border approaches what is actually being read, at every *Patch sample
  area* setting (previously the sensing size was pinned, so the trigger
  point was identical from 50–80 %). The activation reach is capped at the
  calibrated safe zone (52 % of the patch per side): beyond it, a contiguous
  chart's border blur reads "edge" on perfectly aligned grids — measured on
  the real LaserSoft: 13 falsely flagged patches at a 40 % sample area, 160+
  at 60 %, with the cap none — and the placement agreement, which always
  measures the full sample area, covers what lies beyond.

## v3.13.4-beta.6

Knut's beta-5 pixel-measurement round (#119): the selection grid was drawing
one size smaller than everything scanin read, and rectangular patches get his
equal-margin rule.

### Fixed
- **The selection grid drew a 50 % sample box while everything else used the
  chosen value (#119).** Knut measured it: grid 50.8 %, diagnostic image
  60 %. The sample-area spinbox's initial value was set before its change
  signal was connected, so the marquee silently kept its built-in 50 % —
  invisible while the default WAS 50, exposed the moment beta.5 moved the
  default to 60. The dialog now pushes the initial value explicitly, and a
  regression test holds the two together.

### Changed
- **Rectangular patches keep an equal border distance on all four sides
  (#119, Knut's rule).** The sample box is inset by the same margin on every
  edge — chosen per patch shape so the sampled area is exactly the set
  percentage. On square patches this is identical to before (nothing
  recalibrates); on a Wolf Faust's tall GS strip the read zone is now a
  little longer-and-thinner than the patch shape, in exchange for the
  uniform safety margin the edge detection relies on. Applied identically
  in the on-screen grid, the prepared `.cht` scanin reads, and the
  diagnostic image — for ChromIQ charts (with or without printer mode) and
  standard targets alike, verified by parametrised tests at 40–80 % for
  square and 1:2 patches.
- `BOX_SHRINK` question settled (Knut): scanin's `BOX_SHRINK` is exactly
  the equal-margin principle, but it is one global value for all boxes —
  it cannot give differently-sized patches their own percentage — and
  scanin does not require it. ChromIQ therefore standardises on writing the
  margins into the box definitions themselves with `BOX_SHRINK 0`, so the
  diagnostic image always shows exactly what was sampled.

## v3.13.4-beta.5

Knut's beta-4 follow-ups (#119): ChromIQ-chart alignment polish and the last
default he asked for.

### Changed
- **"Warn when this many patches sit on an edge" defaults to 2** (Knut's
  preference after testing; migrated automatically unless deliberately
  chosen). With the straight-run cell rule an aligned scan leaves at most one
  counted patch, so 2 warns at the earliest reliable moment. Help text
  updated.
- **The spacer strips on ChromIQ charts are now visible in the alignment
  view.** Engine charts print thin spacer strips above the first and below
  the last patch row, so the printed block is slightly taller than the patch
  grid the corners belong on — a dotted guide now marks where the printed
  block ends, derived from the chart's own patch data (any spacer size, or
  absent when a chart has none), and the on-screen help says the spacers stay
  outside the grid. Standard targets are unaffected.
- The reference-data picker's label now lists **.ti3** alongside
  .cie/.txt/.cxf — accepting a .ti3 was always intended (measure the target
  yourself with a spectrophotometer and you get the most accurate reference
  possible for your exact copy), but only the file dialog and the ⓘ help knew.

### Fixed
- **"100 % sample area" no longer silently reads ≈ 50 % on ChromIQ charts.**
  Every ChromIQ chart's `.cht` ships with a baked-in default read margin
  (`BOX_SHRINK`, ≈ the old 50 % sample area) for third-party use of the
  sidecar; the reading pipeline neutralised it at every sample area except
  exactly 100 %, where it survived. It is now pinned to 0 there too.
- **Stale prepared `.cht` files from earlier releases are swept** from a
  ChromIQ chart's folder before each read — their naming scheme changed
  between betas, so a months-old leftover (old sample area, even an old
  upside-down fiducial line) could sit beside the current files and mislead
  anyone inspecting the folder.

## v3.13.4-beta.4

Knut's beta-3 follow-ups (#119): new defaults from his measurements, an
aspect-locked sample area for non-square patches, and a real bug found behind
his "detection is late on the demo targets" observation.

### Changed
- **New defaults, from Knut's beta-3 measurements** (existing users are
  migrated automatically unless they chose their own values): sensing cells
  in a row **3 → 6** (a long narrow grey speck still lit a straight run of
  four cells; 5 was his first clean value, 6 adds buffer), placement-
  agreement floor **0.85 → 0.87**, and *Patch sample area* now defaults to
  **60 %**. Help texts updated.
- **The sample area keeps each patch's own shape (#119).** On non-square
  patches (a Wolf Faust's tall-narrow greyscale strip, IT8.7/2 charts) the
  region scanin reads is now shrunk per axis — always the patch's own
  height-to-width relationship — instead of by scanin's single `BOX_SHRINK`
  amount, which insets all four sides equally and distorted elongated
  patches. Generic for any target, derived from the `.cht` patch data; the
  on-screen grid already drew it correctly.

### Fixed
- **Edge detection was 12–15 % late on the bundled demo targets (#119).**
  Found via Knut's SpyderChecker report: the "reads clean a little to one
  side" rule demanded an almost noise-free reading, which a demo scan's
  1.5 % sensor noise (deliberately matching a real Epson) never delivers —
  so every box "on an edge" was silently discarded until deep crossings.
  "Clean" is now measured against the page's own noise baseline; detection
  on the demo targets fires the moment the border reaches the sensing box,
  and quiet real scans keep the strict rule.
- The edge check's sensing box scales with the *Patch sample area* up to
  50 % and is deliberately pinned there (`FLANK_SAMPLE_MAX`) — measured on
  Knut's real aligned LaserSoft, any larger sensing box reads the
  neighbouring borders' blur ("on an edge": 5 patches at 55 %, 56 at 70 %,
  208 at 80 % — on a perfectly placed grid). Contamination of a larger
  colour box is the placement agreement's job; it always measures the full
  sample area, and on the demo targets it now visibly collapses (worst
  25–60 %) when a large sample area really crosses borders.

## v3.13.4-beta.3

Knut's full #119 rework of the scanner alignment checks: honest per-patch
statistics, instant pulled-corner detection, and a grain-proof edge detector.
Everything below is calibrated and verified against his real 600 dpi
LaserSoft / Wolf Faust scans, using the exact grid placements from his log.

### Changed
- **Placement agreement is now truly per patch (#119).** Every patch is
  ranked on its own 24×5 % ladder: its best reading anywhere is that patch's
  100 %, each of the 8 directions contributes its worst reading, directions
  where the reading never worsens beyond the noise floor are ignored (the
  roof then comes from the directions that did find a worst case — it never
  collapses onto the floor), and the mildest direction-worst — lowered by a
  small buffer — is its 0 %. **"Worst" is the single worst patch, "average"
  is the arithmetic mean of all patches**, so worst ≤ average always holds —
  the impossible "worst 98 %, average 100.00 %" pairs are gone.
- **A single pulled corner is detected instantly.** Dragging one corner
  inwards by just 2 % collapses the worst-patch number to ≈ 5 % and names
  exactly the patches beside that corner (previously the grid had to cross
  35–60 % of the sample box before anything fired). A correctly placed grid
  reads ≈ 90 % or better at every sample area; ≈ 5 % of manual placement
  scatter passes untouched.
- **Edge detection is grain-proof (#119).** Each reading box now carries a
  20×20 sensing grid (18×18 inside the box + a one-cell ring just outside,
  half the old ring width — so it no longer warns a few percent early), and
  a border is only believed when the hot cells form a **straight
  interconnected run** roughly parallel to a box side — a border is a line;
  specks light compact clumps and grain scatters, and neither forms a
  straight row. Knut's false positives (Q16, B3, W18, K16, R36 — grain and
  specs) are all silenced while every genuine detection (pulled corner, 20 %
  shift) still fires.
- **New Scanner Limits setting: "…needing this many sensing cells in a row
  (2–9)"** (default 3) — how many interconnected sensing cells make an edge,
  with beginner-first help text. Separate groups are each checked, so a
  speck can't mask a real border elsewhere in the same box.
- The edge check's sensing box is pinned to the 50 % sample area it is
  calibrated at, whatever *Patch sample area* you pick (the colour
  measurement always uses your chosen area). A border that contaminates a
  larger colour box is caught by the per-patch placement agreement, which
  always measures the full sample area — so every sample area up to the
  80 % maximum behaves consistently, with no false edge warnings on a
  perfectly aligned zero-gap target.

### Verified (Knut's #119 test requests)
- The 0 % roof is encountered in each of the 8 directions at some patches on
  both real scans.
- Directions that find no worst case are ignored; the roof never falls to
  the floor (real-scan + deterministic synthetic tests).
- A perfectly placed grid with grain and specs stays silent at 70–80 %
  sample area on both real scans.

## v3.13.4-beta.2

Follow-up beta for Knut: the edge warning on a well-aligned scan is fixed.

### Fixed
- **The edge check no longer warns on a perfectly aligned scan at a large
  sample area (#119).** On a zero-gap target (LaserSoft / ISO 12641-2) every
  patch touches its neighbours, so once the *Patch sample area* was large the
  sample box — and its surrounding edge-sensing ring — grazed the always-present
  neighbour border and the check fired even though the grid was placed exactly
  right (Knut: a correct LaserSoft warned at 64 % sample area and above, where
  80 % worked before). The edge-sensing box is now capped at 60 % of the patch
  pitch, independently of the *colour* sample area you pick: your chosen area
  still drives the measurement, but the edge check never reaches far enough to
  mistake a neighbour for an intrusion. Real misplacement moves a border well
  within the pitch and is still caught (the pulled-corner detection is
  unchanged — it works at any sample area). You no longer need to cap the sample
  area at 60 % by hand.

## v3.13.4-beta.1

A beta for Knut: a new way to build scanner/camera targets from charts laid out
in i1Profiler (#120), two #119 fixes, and a patch-size fix for i1Profiler
workflow exports.

### New
- **Scanner/camera targets from an i1Profiler chart (#120).** "Create scanner or
  camera target" gained an *In i1Profiler* mode: pick the patch set you exported,
  the chart TIFF(s) i1Profiler saved, and your measurement, and ChromIQ reads the
  layout straight off the saved chart (it verifies every patch's colour and
  refuses rather than guess) and writes the same `.cht` + `.cie`. The measurement
  can be i1Profiler's own `.txt` export — ChromIQ converts it for you. This
  reverse-engineers i1Profiler's exact grid: it ignores per-patch position tags
  and always lays the chart out column-major, splitting multi-page charts into
  separate files with a balanced row split.

### Fixed
- **Placement agreement never reads "worst" above "average" again (#119).** The
  two numbers are now on one shared ladder, so the worst patch can never score
  better than the page average.
- **Multi-page target names show the whole-chart total (#119)**, e.g.
  "3 pages × 288 patches = 864 patches".
- **i1Profiler `.pwxf` export no longer collapses to 6 mm patches.** It was
  writing a slider percent of 0 (the device minimum); it now emits the real
  8 × 7 mm.

### Still being investigated (need input from Knut)
- **The edge warning still fires on a well-aligned LaserSoft/ISO 12641-2 scan,
  and the grid can sit a hair off the patches (#119).** ChromIQ's `.cht` for this
  target is a mathematically exact uniform grid, and the profile builds cleanly,
  so the residual is sub-pixel — but the edge detector over-fires on it. To fix
  this safely (without weakening the pulled-corner detection added this round),
  the exact reading grid you used is needed: your marquee corner positions,
  whether "Use fiducial marks" was on, and the reference `.cie` (R250715.cie).
  See the note on issue #119.

## v3.13.3

Knut's scanner-profiling round: the full 1/2/3-page scanner preset set, and a
misalignment check that finally catches a pulled grid corner.

### Improvements
- **Scanner presets: three page counts for each paper.** Both A4 and US-Letter
  now offer a 1-page, a 2-page and a 3-page scanner chart (3430 / 6860 / 10290
  patches on A4, 3250 / 6500 / 9750 on Letter).
- **The misalignment check reports two numbers**, e.g. *"placement agreement:
  worst 56.88 %, average 96.70 %"*. The worst-patch number still decides; the
  average tells you whether a few patches are off or the whole grid has slipped.
- **Patch-edge detection is now configurable.** Settings → Scanner Limits gained
  *"Warn when this many patches sit on an edge"* (Off, 1–9). The Scanner Limits
  tab is grouped so it's visible which limits belong to which check, and its
  help text now explains, in plain language, what each number actually measures.
- **The alignment ladder is finer**: 24 steps of 5 % of a patch, replacing 12
  steps of 10 %. (2 % steps were measured and rejected — on ChromIQ's 4 mm
  scanner charts they fall below one sampled pixel and just repeat positions.)

### Fixes
- **A grid with one corner pulled inwards is now detected.** It never was: the
  page-wide ladder barely moves when only one corner is off, and the edge
  detector needed **seven** patches on a border before it said anything, while a
  pulled corner puts only a handful there. The threshold is now 3 — the number
  Knut specified originally — and the edge limit moved from 0.30 to 0.20. Both
  values were re-derived from his real 600 dpi LaserSoft and Wolf Faust scans
  (`docs/dev_scanner_misalignment.md`, `scripts/scanner_edge_study.py`); an
  aligned grid leaves at most 2 edge-carrying patches, a pulled corner 4 or more.
- **Scanner charts had one near-neutral ring instead of two.** The two 1-page
  presets were built with `nearneutral_rings: 1`; all six now use 2, with the
  other colour sets rebalanced so the patch counts are unchanged.
- **The clean-nearby probe drifted with the ladder step.** It was pinned to
  ladder rung 2 rather than to a physical 20 % of the patch pitch, so any change
  to the step size would have silently moved it (to ±4 % at 2 % steps) and
  quietly disabled edge detection.
- **A `.ti3` converted from an i1Profiler measurement now fails with a useful
  message.** `txt2ti3` writes the exported SampleID into `SAMPLE_LOC`, so every
  chart patch read as unmeasured and the error looked like a corrupt
  measurement.
- **The new edge limit actually reaches existing installs.** Saving Settings
  writes every value, so anyone who had ever opened the Settings dialog had the
  old `0.30` stored and would have kept it forever — receiving none of the fix
  above. On first start, a stored value that merely echoes the old default is
  dropped once. A limit you deliberately chose yourself is left alone.

## v3.13.2

Scanner/camera profiling refinements from Knut, plus a chart-preset fix.

### Improvements
- **The ISO 12641-2 three-page target is now one selection.** In Build scanner
  or camera profile → "A standard target I own", the three ISO 12641-2 pages
  used to appear as three separate list entries even though they're a single
  multi-page target. They're now one entry that opens a three-page workflow —
  pick and place a scan for each page, exactly like a multi-page ChromIQ chart —
  with each page locked to its own recognition file. "Try with a demo scan"
  loads a practice scan for every page.
- **Target-type names show their patch count.** Each standard target in the list
  now says how many patches it has (and, for the multi-page set, the per-page
  count), so you can tell the sizes apart before picking one.

### Fixes
- **The i1Pro · A4 924-patch TC9.24 "by Pharmacist" chart is temporarily
  unavailable.** Its bundled page image disagrees with its own reference values
  (one patch is printed white where the reference says grey), which would spoil
  both a print and any scanner target derived from it, so it's greyed out in the
  Create Chart presets list for now. It returns once the chart is regenerated.
  Every other "by Pharmacist" chart — including the ColorMunki A3 TC9.24 — is
  unaffected.

## v3.13.1

Follow-up fixes and refinements to the 3.13.0 layout engine and scanner
profiling.

### Fixes
- **Strip-indicator style now takes effect.** The label font, size,
  bold/italic, rotation, offset and underline options in Settings → Chart
  Layout were being ignored on new charts. They now apply to every engine
  chart — Settings is the single source of truth (a saved preset or "Save as
  Defaults" no longer silently overrides them).
- **Scanner targets from more charts.** The ten "by Pharmacist" prebuilt
  charts and ColorMunki double-density charts couldn't be turned into scanner
  targets because they carried no patch geometry. ChromIQ now derives that
  geometry from the printed chart itself — colour-verified patch by patch
  against the reference — so those charts are scanner-ready. (One bundled
  i1Pro/A4 TC9.24 chart is left out: its packaged image disagrees with its own
  reference values and should be regenerated.)
- **Guided patch count matches the chart.** The Guided "calculated patches"
  figure and the Chart-layout-information estimate now agree with what the
  engine actually builds, for every instrument and option (i1Pro / i1Pro 3+ /
  ColorMunki hand-held/double/triple density / SpectroScan) — including when
  the Manual layout-engine toggle is off, where the count and estimate could
  previously be wrong or blank.

### Improvements
- **ColorMunki extra-high (triple) density honours the patch-size scale**, so
  it reproduces printtarg's triple-density layout exactly at any scale instead
  of a single fixed size.
- **Eleven of the "Full layout setup" presets now build with the ChromIQ
  layout engine** (verified to match printtarg exactly), so they carry native,
  scanner-ready geometry.

## v3.13.0

The biggest ChromIQ release so far — 143 betas, developed and tested
end-to-end with Knut Georg Larsson. Three headline features: ChromIQ's
own chart layout engine, scanner & camera profiling, and profiling a
printer with a flatbed scanner instead of a spectrophotometer.

### 🧩 The ChromIQ layout engine
- ChromIQ can now lay out charts itself — a built-in alternative to
  ArgyllCMS printtarg for i1Pro / i1Pro 3 / ColorMunki / SpectroScan
  (toggle in Create Chart → Manual; Guided uses it transparently).
- Your margins are the law: the patch area is exactly the margin box you
  set, with strip labels, sheet text and the clip band living inside it —
  charts pack denser than printtarg (e.g. i1/A4 462 vs 441 patches), and
  "Use instrument margins" fills and locks the jig minimums when you
  want them.
- Two layout philosophies: "Prioritise patch size" (set the size, fit as
  many as possible) or "Prioritise chart area" (pin strips/rows or a
  minimum patch size and the grid grows to fill the page exactly).
- Per-chart control of everything: patch size and scale, per-edge
  margins, coloured/B&W spacers, inter-patch and label gaps, strip-label
  font/size/rotation/underline, 8/16-bit, compression, resolution.
- Sheet text with live placeholders ({project}, {paper}, {page}…), and a
  redesigned clip-border band whose default is an auto-filled Notes box —
  chart facts printed, labelled lines to hand-write printer/ink/paper.
- Randomise with a stored seed (reproducible layouts), optional
  ArgyllCMS .cht emission, SpectroScan hexagons, ColorMunki brick offset
  and native extra-high density.
- Everything saves as defaults and in named presets, exactly like the
  printtarg options, and the chart editor is now a true patch-set
  editor: layout lives in Create Chart, patches (generate, load from
  .ti1/.ti2/.ti3/CGATS/hex lists, combine, recolour) live in the editor,
  and an edited set re-lays-out under your current chart settings.

### 🖨️ Scanner & camera profiling (no target chart needed)
- Build an ICC profile for a flatbed scanner — or a digital camera —
  from a chart you printed and measured (its .cht + .cie are written on
  request from every measurement), or from a standard target you own:
  Wolf Faust IT8, LaserSoft (Advanced and DCPro), X-Rite ColorCheckers,
  HutchColor HCT, QPcard, SpyderChecker, CMP and every other target
  ArgyllCMS knows. Reference files convert themselves (.cie/.txt/.ti3
  as-is, .cxf via cxf2ti3, raw/spectral .txt via txt2ti3 + spec2cie).
- ChromIQ bundles Knut Georg Larsson's corrected recognition files —
  several of Argyll's shipped .cht files had wrong geometry — and all
  bundled targets read back 100 % of their patches through scanin.
- A live reading grid with zoom/pan/rotate, mid-side handles, pop-out
  view, per-target position memory, fiducial-frame support and a "Patch
  sample area" control (read only the clean patch centres).
- Average several scans (mean / geometric / trimmed), choose the profile
  type (Matrix recommended, LUT medium/high), name the profile and
  install it with one click. Try everything first with a demo scan —
  a rendered stand-in with known colours, realistic softness and real
  scanner noise.

### 🖨️→📷 Profile your printer with a flatbed scanner
- No spectrophotometer? Print a chart (no measuring!), scan every page
  on your profiled scanner, and ChromIQ reads the patches through the
  scanner profile and builds the printer ICC — the whole loop without a
  spectro. Works with ChromIQ charts (engine or printtarg) and with
  charts made outside ChromIQ (hand it their printtarg .cht pages).

### 🛡️ Misalignment protection (Knut's design)
- The reading grid is guarded by layered, calibrated checks: a dense
  placement evaluator ranks your grid position against a 12-step ladder
  in 8 directions (best position = 100 %), and an edge detector senses
  patch borders with an 11×11 grid per sample box — full coverage plus
  an outer ring that fires while a box is still approaching a border,
  symmetric in every direction, with a connectivity rule so dust can
  never fake an edge and a clean-nearby rule so a target's own printed
  bars don't count.
- A "Check alignment" button dry-runs the page on screen; every build
  checks all pages and warns (Stop / Build anyway) with the worst
  patches named; a post-build self-check reads colprof's own fit error.
  All thresholds editable under Settings → Scanner Limits, each with a
  plain-language explanation and its default stated.

### 🔗 Device-link tools
- New Tools: "Create device-link profile" (collink with friendly
  presets, viewing conditions, image-optimised gamut mapping via
  tiffgamut in CIECAM02 space, 3DLUT export) and "Apply a device-link
  to an image" (cctiff → printer-ready TIFF, sidestepping driver colour
  management; source-space auto-fix with v4→v2 conversion).

### ✨ More
- New built-in Scanner presets by Knut (A4/Letter one-page 3430/3250 and
  two-page 6860/6500 patch flatbed charts) that carry their full
  New-chart design; built-in preset recipes seed the editor.
- Print Chart can print any TIFF through the colour-management-free
  pipeline; Tools menu grouped by task; Settings gains a Paths tab
  (every folder ChromIQ uses, editable profile-install folder) and
  Scanner Limits; busy indicators with step names on long runs.
- New Help cards: "Profile my scanner or camera", "Profile my printer
  with a flatbed scanner", and a "Dictionary and terminology" glossary —
  60 terms from ChromIQ and colour management in plain language.
- Scan-resolution guidance everywhere it matters: 600 dpi or more,
  1200 dpi preferred.
- The three ISO 12641-2 target entries are labelled as what they are:
  the three pages of the standard's 3-page target set.
- macOS builds declare their true minimum (macOS 13); older Macs can run
  from source with Qt 6.8 (recipe in the README).

### 🌍 Languages
- Everything above is fully translated in all 13 languages.

### 🙏 Thanks
- To **Knut Georg Larsson** for designing, testing and calibrating this
  release across 143 betas — the layout engine, the scanner workflows
  and the misalignment checks carry his fingerprints throughout — and to
  Nelson for the Windows scanner-profiling reports.

## v3.13.0-beta.143

### ✨ Improvements
- **New help card: "Dictionary and terminology"** (Knut's idea) — 45
  terms, phrases and abbreviations from ChromIQ and printer/scanner
  profiling generally (ΔE, gamut, rendering intents, the ArgyllCMS
  tools, the .ti1/.ti2/.ti3 pipeline, M0/M1/M2, OBA…), alphabetical, in
  plain beginner-first language, in its own card in the Help window —
  fully translated into all 13 languages.
- The scanner-profiling help now states the scan resolution to use:
  600 dpi or more, 1200 dpi preferred — 300 dpi is too coarse for clean
  patch reads (Knut). Added to both Help-window walkthroughs and the
  Build scanner or camera profile window's ⓘ.

## v3.13.0-beta.142

### 🐛 Fixes
- **Edge detection now fires from every direction** (Knut's beta.140
  test: only leftward drags triggered). The derivative was one-sided —
  it assigned each colour change to the right/bottom pixel of the pair,
  shifting the whole detected edge line by the stride, so boxes crossing
  an edge rightward/downward didn't contain their own border until much
  deeper. The gradient is now CENTRED, at two spans (4 px and 8 px) that
  cover real transition widths — ~3–4 px at 300 dpi, ~5–8 px at 600 dpi.
  Verified on his real scans: crossings now flag in all four directions.
- **Dust can no longer fake an edge** (his LaserSoft dust finding, and
  his suggested rule): a box's hot sub-cells must be CONNECTED — a border
  line runs through adjacent cells of the 9×9 grid, dust specks scatter
  and never link up. Page rule recalibrated (default limit 0.30, seven
  boxes) on his real scans: aligned grids stay quiet including the
  LaserSoft (whose own printed bars leave a few genuinely edge-carrying
  boxes), just-crossing grids show 20–160 flagged boxes.
- **"Checking the grid…" can no longer hang forever**: a run request
  that hit a still-busy ArgyllCMS runner was silently dropped, leaving
  the check waiting for a finish that never came. It now fails fast.
- Demo scans render with realistic edge softness (~3–4 px transitions,
  as Knut measured on real 300 dpi scans; they were 7–8 px).
- Printer-from-scan mode: the chart picker only accepts .ti2 (and only
  .ti3 with the option off); the scanner-profile and BYO-.cht pickers
  use ChromIQ's file dialog with sidebar shortcuts — and respect the
  native-dialogs setting (Basti).
- ArgyllCMS auto-detect resolves symlinks (Homebrew's /opt/homebrew/bin
  points into the Cellar) so the ref folder next to the real binaries is
  found (Knut).
- Scanner Limits: Restore Factory Defaults now resets these fields too;
  range labels are honest (0.5–0.99 / 0.02–0.5); every limit's tooltip
  states its default (Knut).
- The suggested chart name reads instrument, paper and orientation from
  the layout ENGINE panel when the engine is on — the printtarg widgets
  could hold stale values (Letter Landscape suggested "A4…Portrait";
  Knut).

### ✨ Improvements
- **Two new built-in Scanner presets by Knut**: A4-6860p-2pages and
  Letter-6500p-2pages — the same 4 mm flatbed layout with a denser patch
  set over two sheets.
- Colour extremes generator: "per end" maximum raised to 200, matching
  Pastels and Highlights & shadows (Knut).
- The edge-detector help text explains the updated mechanism (centred
  derivative, connected sub-cells, grain floor) in all 13 languages.

## v3.13.0-beta.141

### 🐛 Fixes
- **Engine charts keep their exact geometry in the scanner tool** (found
  in Basti's showcase session: profiling from a chart's own TIFF). The
  grid overlay and the .cht handed to scanin both re-placed "uniform"
  grids onto rectarg's integer pixel edges — correct for rectarg-rendered
  standard targets, but an engine chart distributes its fractional patch
  pitch in its own pattern, so the drawn cells (and scanin's sampling)
  drifted up to ~20 % of a patch off the printed columns mid-chart while
  the corners stayed pinned. Aligning the grid then looked impossible:
  the middle columns appeared shifted right no matter where the corners
  went, even though the measurements still passed (the sample-area
  margins absorbed the bias). Engine layouts are now used as the pixel
  truth they are — on screen and in the .cht — in both axes; standard
  targets keep the (correct) rectarg treatment.

## v3.13.0-beta.140

### 🐛 Fixes
- **Edge detection rebuilt on Knut's derivative design — and it now sees
  a 2 % overlap.** A patch border is a LINE of sudden colour change, so
  the detector now works on spatial derivatives: every sample box is
  split into a 9×9 grid (his suggestion), each sub-cell records its PEAK
  colour-change over a widened baseline (peaks, not means — an edge is
  never averaged away), the page's own grain sets the noise floor, a box
  is on an edge when ≥3 sub-cells stand above it (a border line always
  crosses several; dust lights one), four such boxes flag the page, and
  — the piece that makes real
  targets workable — the box must read CLEAN at some nearby grid
  position, which cancels colour bars and wedges inside the patch itself
  (the LaserSoft's structured areas) while still catching dragged corners
  and sides that a whole-grid comparison can never represent.
- Calibrated on his three real scans and ALL bundled demo targets:
  aligned grids show 0–2 flagged boxes everywhere; a grid crossing
  borders by just 2 % of a sample box shows 14–66 on the real scans.
  Side drags fire; corner drags fire wherever the corner's patches have
  contrast to detect (a dark/greyscale corner region has none — physics).
- The Scanner Limits help text now explains the whole mechanism (Knut).

## v3.13.0-beta.139

### 🐛 Fixes
- **Edge-flank detection now actually bites** (Knut's beta.138 test). The
  3×3 sub-cells were too coarse: a sample box 5–10 % past a patch edge
  filled only a sliver of a third-of-a-box cell, so the deviation diluted
  below any threshold — which is also why the Scanner Limits knob seemed
  dead. The detector now measures THIN EDGE STRIPS (1/9 of the box side,
  one per side, per Knut's granularity suggestion): the same crossing
  fills half the strip and the signal jumps. Verified symmetric in all
  four directions on the demo targets and his real scans (aligned grids:
  0–2 hits; crossings: 31–288 boxes), and the trigger is now three boxes
  instead of five, so corner-drag distortions (one grid corner pulled
  inward — invisible to the whole-grid ladder by construction) trigger
  via the affected corner's own patches.

## v3.13.0-beta.138

### ✨ Improvements
- **Edge-flank detection** (Knut's design): every sample box is split into
  a 3×3 grid and each border zone is compared with the box centre, in
  brightness and two opponent-colour planes. A box whose edge lies on a
  patch border picks up the neighbouring colour along that side — three
  or more such boxes flag the page IMMEDIATELY, overriding the
  placement-agreement floor, and the worst-placed patches are named.
  Each box is judged RELATIVE to its own best nearby position, so
  patches with inner structure (the LaserSoft barcode row, grey wedges)
  don't count. Threshold in Settings → Scanner Limits ("Flag sample
  boxes on patch edges above", default 0.16, five-box rule), calibrated
  on his three real materials (Wolf Faust, LaserSoft Advanced, the
  3-page ChromIQ chart with spacers): aligned grids show 0–2 hits,
  grids on borders dozens.
- The placement-agreement floor default is 0.85 (Knut). The check (both
  layers) runs identically in all three scanin modes — standard target,
  ChromIQ-chart scanner profile, and printer-from-scan — for the Check
  alignment button and for every page at build time.

### 🐛 Fixes
- Switching between standard target types no longer keeps the previous
  target's grid placement — the grid re-seeds for the new geometry, and a
  demo scan of the previous target is cleared with it (clearest when
  using "Try with a demo scan" across types; Knut).
- The page selector is reliably hidden in standard-target mode, and
  switching back to a multi-page ChromIQ chart restores its full page
  list (a 3-page chart came back showing only page 1).
- Demo scans now carry simulated scanner noise (1.5 % Gaussian, the
  level Knut's real Epson V700 scans measure) on top of the edge
  softness — so the demo behaves like a real scan under the same
  thresholds (Knut).

## v3.13.0-beta.137

### 🐛 Fixes
- **Placement check: corner-frame bug fixed** (Knut's beta.136 test). With
  "Use fiducial marks" ON, the grid corners live on the fiducial frame,
  but the dense evaluator mapped the patch area onto them — every sample
  box was displaced outward and the ladder went blunt (agreement stuck
  above 99 % on offsets the diagnostic image showed plainly). The
  evaluator now maps through the .cht's own F frame, exactly like
  scanin's -F.
- **The placement check now sees colour edges, not just brightness.** An
  IT8's vertical neighbours often differ only in chroma, so a
  luminance-only check was structurally blind to vertical offsets. The
  edge lens now samples two opponent-colour planes as well, and scanner
  mode takes the worst of both lenses — the response lens (blends against
  the reference) and the edge lens (sample boxes straddling patch
  borders), per Knut's worst-rules.
- **Knut's tightened normalisation**: each of the 8 ladder directions has
  its own worst value and the LEAST worst of them is the 0 % end — the
  scale no longer depends on which octant the grid sits in, and small
  offsets move the number immediately.
- **The Build button now runs the same placement check on every page**
  (Knut). The old rank-agreement check and its "Minimum scan↔chart
  agreement" setting are retired; the placement floor covers Check
  alignment and building alike, and flagged pages are listed in the
  pre-build warning with Build anyway / Stop.
- Positive verdict reworded per Knut ("keeps all sample boxes within
  their chart patches"), agreement shown with 2 decimals.

## v3.13.0-beta.136

### 🐛 Fixes
- **Check alignment now implements Knut's dense step-ladder design** — and
  it works on real scans. The scan is sampled densely once, and the grid
  position competes against every position of the ladder he specified:
  12 steps of 10 % of a patch in all 8 directions (his high-density
  measurement idea, with the scanin detour replaced by direct image
  sampling — same maths, milliseconds instead of minutes). His
  normalisation is used verbatim: best ladder position = 100 %, worst
  position in the grid's octant = 0 %, the grid's own position lands in
  between with 3-decimal precision, and the patches reading furthest from
  expectation are named in the warning.
- Verified on his real scanned Wolf Faust target through the real dialog:
  aligned 98.067 %, 10 % offset 93.399 %, 15 % offset 87.190 % (all pass),
  25 % offset 71.311 % and diagonal ¼-patch 71.064 % (flagged) — exactly
  his acceptance spec (detect ≥25 %, accept <15 %, at 50 % sample area).
  On his real 3-page engine chart (printer mode) the same spec holds via a
  reference-free uniformity objective (aim values scatter against real
  prints, so printer mode ranks positions by whether sample boxes sit on
  flat colour instead).
- New Scanner Limits setting "Check alignment: flag placements below
  (0–1)" (default 0.85 = 85 %, calibrated on those real scans).
- The alignment-check result window now zooms (scroll) and pans (drag),
  double-click fits — so misalignment can be studied patch by patch.

## v3.13.0-beta.135

### ✨ Improvements
- Check alignment probes in Knut's full 8-direction star — left, right,
  up, down and the four diagonals — so a grid offset in ANY direction has
  a probe looking toward it (a diagonal ⅓-patch offset on a soft scan now
  triggers the "nudge it" warning; verified end-to-end). When the first
  ±40 % ring shows scanin isn't self-registering, a finer ±20 % ring runs
  automatically — his step ladder condensed to two rungs so the check
  stays under a minute.

## v3.13.0-beta.134

### 🐛 Fixes
- **Check alignment now catches sub-patch offsets — and never praises a
  placement it hasn't verified** (Knut's beta.132 test). Two real defects
  behind his frozen "agreement 0.93": the demo targets' reference file
  used a pseudo-Y that capped even a PERFECT read at 0.93 (now true
  luminance — aligned demo reads score 1.00, so stringent floors like
  0.95 work); and scanin silently self-registers on crisp targets, so
  shifted corners up to half a patch produced literally identical (and
  genuinely correct) reads — which the old single-run check then praised
  while the user stared at their shifted frame.
- The check now runs Knut's step-probe idea: after the main read it
  re-reads at ±40 % of a patch in all four directions. Identical probe
  reads → "ScanIn locked onto the target's grid on its own" (the honest
  version of what happened). Differing reads → the positions compete,
  and if a neighbour explains the chart better you get "a nearby grid
  position matches the chart better — nudge it and check again" — this
  catches fractional offsets on real scans that whole-page agreement is
  structurally blind to on smooth-ramp targets.
- Single-page targets say "Target:" instead of "Page 1", and the
  "…on this page's scan" tail is gone from single-page messages (Knut).
- macOS release notes now state the correct minimum (13+, was 12+).

## v3.13.0-beta.133

### 🌍 Translations
- All twelve languages are fully translated again: the entire scanner-
  profiling round (misalignment checks, Check alignment, Scanner Limits
  and Paths settings tabs, the printer-from-scan help card, Print-tab
  image loading) plus older stragglers from the beta.111–120 window
  (BYO-.cht rows, profile naming/installing, busy-bar and page-picker
  strings) — roughly 110 strings × 12 languages. Also caught a few
  long-standing gaps (Bold/Italic in Norwegian, Swedish and Chinese, the
  clip "Side:" label in Norwegian). What remains identical to English is
  identical by design: colour-space names, CIE terms, format-only
  strings, and words the language genuinely shares.

## v3.13.0-beta.132

### ✨ Improvements
- Build scanner or camera profile: new **Check alignment** button next to
  Reset grid (Knut's pre-build check, #108). It reads ONLY the page on
  screen — nothing is built — and shows a window with the verdict of the
  misalignment checks plus the diagnostic image of what was read. The
  whole dry-run happens in a temporary folder that is deleted when the
  window closes, so nothing lands next to your scans; the "Save a
  diagnostic image" checkbox keeps working for real builds as before.
  Works in all three modes (scanner/camera, printer-from-scan, standard
  target).

## v3.13.0-beta.131

### 🐛 Fixes
- Standard targets (Wolf Faust, LaserSoft…) no longer false-flag the
  row/column misalignment check on perfectly aligned scans (Knut's
  beta.130 test). Structured targets group colour FAMILIES into lines,
  and a scanner's hue-dependent response displaces a whole family
  coherently — mimicking a shifted line. The check now confirms a
  candidate by where its reads LAND: a truly shifted line sits on a
  neighbouring line's expected values; a response-shifted family sits
  between lines and stays quiet. Validated on Knut's own IT8 reference:
  0 % false alarms (was 98 % with a hue-dependent response), 99–100 %
  detection of genuine line shifts on both chart types.

### ✨ Improvements
- Print Chart: a new image button beside the chart-grid button loads any
  TIFF — a chart made by another tool, a test image — and prints it
  through ChromIQ's colour-management-free pipeline (#117, Knut).
  Printing only, by design: measuring still needs the chart's .ti2, which
  carries the patch geometry an image alone cannot.

## v3.13.0-beta.130

### 🐛 Fixes
- **Printer-from-scan: the misalignment check no longer flags perfectly
  aligned real scans.** The old check compared what the scanner measured
  against the chart's ideal aim colours — but a real printer can't REACH
  those aims (gamut compression, paper white), so saturated patches sit
  ΔE 20–40 away even when everything is perfect: Knut's real aligned
  pages flagged 100 % while colprof's own fit was excellent (peak 2.9).
  Printer mode now uses the same rank-agreement check as scanner mode —
  the ORDER of patch values survives honest physics (verified on his
  real scans: aligned pages ≈ 0.95, scrambled reads ≈ 0) — one
  methodology across scanner, printer and standard modes, as requested.
  The two ΔE threshold rows leave Settings → Scanner Limits with it.
- macOS: the app bundle now declares its TRUE minimum system version,
  macOS 13 Ventura (set by the Qt 6.11 frameworks inside — their
  binaries refuse to load on older systems). On macOS 12 Monterey the
  app used to flash in the Dock and vanish without a word; it now gets
  Apple's clear "requires macOS 13" message instead (forum report).
  Older Macs can run ChromIQ from source with Qt 6.8 — verified working,
  recipe in the README.

## v3.13.0-beta.129

### ✨ Improvements
- Build scanner or camera profile: the chart field now shows the file the
  mode actually consumes — switching "Profile my printer from this scan"
  ON swaps a pre-filled measured .ti3 for the chart's .ti2 (and back when
  switching OFF), so the input no longer reads like the wrong file
  (Knut).

## v3.13.0-beta.128

### ✨ Improvements
- Local misalignment detection (Knut's row/column pattern idea, adapted):
  a page whose whole-page checks pass can still have ONE grid edge a cell
  off — the new layer ranks every patch's read value against the
  reference over the page and flags a whole row or column whose patches
  are collectively displaced, naming it in the warning ("the patches in
  row 1 read like their neighbours' colours…"). Validated on the 3-page
  test chart: zero false alarms across 300 noisy aligned runs, 100 %
  detection of the mid-handle squeeze that slipped past the page checks.
  Knut's literal per-row pattern matching couldn't survive randomised
  charts (7-patch rows lose their uniqueness: 98.5 % false-alarm rate) —
  the rank-displacement form keeps the idea and fixes the statistics.
  Runs in scanner AND printer mode; sub-⅔-patch blends remain the
  post-build self-check's job (their values are individually plausible).

## v3.13.0-beta.127

### ✨ Improvements
- Scanner Limits: two labels now read plainly on their own — "Minimum
  scan↔chart agreement (0–1)" and "Warn when the finished profile fits
  worse than (peak) / …and its average error is also above" (the ⓘ texts
  already explained them; the labels no longer need them to).

## v3.13.0-beta.126

### 🐛 Fixes
- Self-check no longer cries wolf on honest Matrix scanner profiles: a
  perfectly aligned build can legitimately show a peak fit error around
  30 while its average stays low (Knut's: 32.8 / 8.5) — the warning now
  requires the peak AND the average to exceed their limits (a misplaced
  grid lifts both; his misaligned runs averaged ~40). The average limit
  is the fifth editable threshold.
- Create Chart: the left pane has a minimum width, so a narrow window
  can no longer slide the divider over the input fields (Knut).
- The post-stop reveal button is now honestly named "Reveal folder" (it
  opens the folder, and appears even without a diagnostic image —
  pointing at the scans; Knut).

### ✨ Improvements
- Create Chart: new "Reveal folder" button between Generate Chart and
  Save as Defaults opens the generated chart's folder (Knut).
- Settings: the Scanner tab is now "Scanner Limits"; the Paths tab shows
  the installation as the app bundle (not its Contents/MacOS innards)
  and every reference row explains on hover what the location is for
  (Knut).
- Scanner tool help leads with the honest framing: a scanner or camera
  never replaces a spectrophotometer, but gives spectro-less users a
  real path to better prints (Knut).

## v3.13.0-beta.125

### 🐛 Fixes
- Create Chart → Manual: after picking a preset near the end of the long
  list (e.g. the Scanner group), reopening the Presets dropdown showed it
  stranded at the top of the window. macOS aligns the menu-style popup
  with the SELECTED item, and the popup's height cap shrank it in place
  without moving it back — it now always anchors at the combobox like a
  plain dropdown (Basti).

## v3.13.0-beta.124

### ✨ Improvements
- Settings → new "Paths" tab collects every folder ChromIQ reads or
  writes (Knut): the default output folder (moved here from General) and
  a new editable "Profile install folder" — where "Install profile"
  copies a finished .icc; blank keeps your system's colour-profile
  folder — plus read-only rows with Reveal buttons for the log file,
  presets, translation overrides, ArgyllCMS binaries and the
  installation folder.

## v3.13.0-beta.123

### 🐛 Fixes
- Scanner profiling: engine charts' recognition files are now written in
  ArgyllCMS's native image convention (origin top-left, y down). The old
  y-up files read correctly but forced a reflection into scanin's corner
  mapping, so the diagnostic image drew every label mirrored — Knut read
  mirrored "2" as "5" / "12" as "15" and reasonably concluded the patch
  order was scrambled. The diag now renders upright, sequential labels you
  can actually proof-read (#108). Note: reads scrambled by the beta.117–120
  bug also poisoned any scanner profile built then — rebuild your scanner
  profile before profiling a printer through it, or every page will flag
  as misaligned even when perfectly placed.
- "Reveal profile" never actually appeared after a build: a widget-name
  collision made the success handler show the "Try with a demo scan"
  button instead. Fixed — and after a build STOPPED by the alignment
  warning, the button now appears as "Reveal diagnostic image" so the
  evidence is one click away (or, without a diagnostic image, the log
  suggests enabling it).

### ✨ Improvements
- Misalignment detection, layered (Knut's systematic tests): grid shifts
  under ~15% of a patch still read pure patch colour (harmless); the
  per-page checks catch scrambles and shifts from about two-thirds of a
  patch; and a new post-build self-check verdict reads colprof's own fit
  error (peak err 60–91 in Knut's half-patch tests vs under 10 aligned)
  to catch the subtle blends in between and warn before you trust the
  profile.
- All four thresholds are editable in Settings → new "Scanner" tab, each
  with a plain-language explanation: per-patch ΔE limit, wrong-share per
  page, scan↔chart agreement floor (raised to 0.60, validated against
  real data: aligned ≈ 0.88, scrambled ≤ 0.33), and the self-check peak
  error limit.

## v3.13.0-beta.122

### ✨ Improvements
- Build Profile tab: the Gamut Source path field now starts exactly under
  its combobox (guided and manual), and the Advanced section's option pairs
  sit on one grid so "No output shaper curves (-no)" aligns with "Don't
  embed measurement data (-nc)" (Basti).
- Build scanner or camera profile: printer mode's "Scanner profile (.icc)"
  label and field lose their indent and sit flush with the rows below,
  the field stretching the full row width (Basti).

## v3.13.0-beta.121

### 🐛 Fixes
- **Scanner profiling: ChromIQ engine charts read every strip in reverse —
  even with a perfectly placed grid** (#108, found via Knut's deliberate
  misalignment test). The patch-area fiducial rewrite wrote its corners in a
  fixed order that is correct for standard targets but vertically mirrors
  engine charts, so H1 was read as H15, H2 as H14, … while every box still
  landed on a patch. Present since beta.117; scanner and printer-from-scan
  profiles built from ChromIQ charts in betas 117–120 should be rebuilt.
  Verified against Knut's real 3-page chart: 0/105 correctly-labelled
  patches before, 105/105 after — and a new label-aware end-to-end test
  reads a rendered engine chart back patch-by-patch **by name**, so a
  scramble like this can't pass silently again.
- The alignment check now stops the build instead of drowning in colprof's
  output: findings are collected per page (naming the page to fix) and a
  warning dialog offers Stop / Build anyway before the profile is built.
  Scanner mode gets its own detector at last (it had none — its reference
  values make a ΔE check blind): the scanned patches are rank-correlated
  against the reference lightness; a misplaced grid scores near 0 and
  flags the page.
- "Not every patch on this page could be read" no longer cries wolf on
  every page of a multi-page printer run — with accumulation, only the
  final page's report can mean real gaps.
- The built-in demo scans ("Test files…") are now rendered on exactly the
  grid edges the reader uses — mid-grid cells could previously sit up to a
  pixel off (Knut's Hutchcolor diagnostic).

### ✨ Improvements
- Build scanner or camera profile: the "Other… (choose a .cht file)" picker
  finally has its label ("Target layout file (.cht):" with ⓘ) and aligns
  flush with the other file rows; Patch sample area and Profile type sit
  next to their labels on one shared column with Profile name (Knut, Basti).
- Build Profile tab, guided and manual: all pulldowns, fields and file
  boxes start at one common column instead of hugging their own label
  (Knut).
- New help-window card "Profile my printer with a flatbed scanner" walks
  through the printer-from-scan workflow step by step (Knut).

## v3.13.0-beta.120

### 🐛 Fixes
- The scan-geometry mismatch message now names the verified cause and the
  remedy: charts packed to the last few percent of page capacity paginate
  differently in printtarg's scan mode (measured: ColorMunki double density
  diverges at patch scale 0.91–0.93, matches again at 0.90 and below; i1Pro
  and plain ColorMunki never diverge). Reduce the Patch Size Scale slightly
  and regenerate, and the chart carries scan geometry after all (Knut).

## v3.13.0-beta.119

### ✨ Improvements
- Scanner/camera profile tool: the target-source choice at the top is now
  labelled "Create profile using:" so the two options read as one decision
  (Knut).

## v3.13.0-beta.118

### 🐛 Fixes
- Scanner profiling: ColorMunki double-density charts stored a wrong
  scan-geometry capture — printtarg lays them out differently in scan mode
  (2 printed pages became 3 recognition pages), so the selection grid could
  never match the scan (#108). Bad captures are now discarded at creation,
  and already-stored mismatched geometry is rejected with the concrete
  reason instead of a grid that can't fit. A new test pins that every
  bundled standard target's selection grid equals its .cht boxes exactly.
- Renaming a project via the generate-time chooser left the Print tab
  holding the old file paths — printing then failed with "no such file"
  until the chart was regenerated. All tabs now pick up the renamed paths
  immediately.
- The scanner-target tool's "no patch positions" message now names the
  exact file it looks for (<chart>.channels.json next to the picked file).

## v3.13.0-beta.117

### 🐛 Fixes
- Printer profiling from a scanned chart with its own printtarg .cht files:
  the patch grid finally lands where you place it (#108). Two geometry bugs
  compounded — the corners were mapped to printtarg's fiducial frame (which
  sits ~7 mm outside the patch area) instead of the patch area the marquee is
  aligned on, and printtarg's wider first column was flattened onto equal
  cells both on screen and in the file scanin reads. Charts with non-uniform
  patch grids now keep their true geometry everywhere.

### ✨ New
- Misalignment safety net: after the scans are read for a printer profile,
  ChromIQ compares every patch against the chart's aim values and warns when
  more than 10% differ by ΔE over 15 — a misaligned grid or a scan that
  doesn't belong to the chart, caught before the profile is built (Knut).
- The scan view can zoom out to 90% of the fit, so the grid's corner handles
  stay reachable on borderless full-page scans.

## v3.13.0-beta.116

### ✨ Improvements
- The busy indicator now lives only in the scanner/camera profile tool and,
  like the Build Profile tab's bar, is always visible — "Ready" while idle,
  animated with the current step and elapsed seconds only while a run is
  under way.

## v3.13.0-beta.115

### ✨ Improvements
- Tools windows now show a live busy indicator while an external tool runs —
  the animated spectrum bar with a ticking elapsed-seconds readout and a busy
  mouse cursor. The scanner tool also names the current step ("Step 2 of 6 —
  Reading page 2 for the printer profile…") and fills the bar across the whole
  run, so long silent scanin/colprof stretches no longer look like a freeze.
- Printer-from-scan mode no longer offers "Add another scan to average":
  it reads exactly one scan per page, and extra scans were silently ignored.
  A run that still carries extras says so in the status log. (Real per-page
  averaging for printer profiles may come later as its own feature.)

## v3.13.0-beta.114

### 🐛 Fixes
- Scanner/camera profile tool: scans from real scanners (16-bit, high dpi)
  showed no preview — their decoded size exceeds Qt's image memory limit, so
  the marquee stayed empty and the grid couldn't be aligned, leading to
  misaligned partial reads (#108). Previews now load regardless of size and
  bit depth, and a scan that truly can't be decoded says so instead of
  leaving the view blank. scanin's "not all sample values have been filled"
  is surfaced as a clear per-page warning.
- Strip labels: the automatic label size no longer shrinks below 1.5 mm when a
  wide font meets a narrow-patch chart — labels could become so small they
  looked switched off. "Restore factory defaults" in Settings → Chart Layout
  now also resets the strip-label style (font, size, rotation, underline …),
  and the size box there finally has a label.
- The A4 Scanner built-in preset is named …-Landscape-… again (the beta.113
  note saying "Portrait" followed a misnamed file — both scanner charts are
  laid out on rotated, landscape sheets).

### ✨ Improvements
- Scanner/camera profile tool: the "Profile my printer from this scan" switch
  now sits at the top of the chart section (it changes the fields below it),
  and the Page selector sits directly above the scan it switches, with a
  "one scan per page — k of n picked" counter (#108).

## v3.13.0-beta.113

### ✨ New
- The two Scanner built-in presets now carry Knut's updated patch sets (#107) —
  same sizes (A4 3430 patches / US-Letter 3250 patches, 4 mm grid, one page)
  with redesigned content: a denser RGB cube, spirals, skin tones, the
  blues/greens/sunrises/flamingos colour families, a 64-step neutral ramp,
  near-neutrals, saturated edges, a hue–saturation ring, pastels and
  white/black anchor patches. Each preset also ships its complete New-chart
  design, so it appears under "Load setup from preset" in the New Patch Set
  window and seeds the editor when a chart made from it is reopened. The A4
  chart is now named …-Portrait-… to match Knut's updated original.

### 🐛 Fixes
- "Load setup from preset" listed the Scanner charts' designs under a wrong
  "ColorMunki" label — they now file under "Scanner".

## v3.13.0-beta.112

### ✨ New
- Printer profiling from a scan now works with charts made outside ChromIQ
  (#105). A new "Chart geometry (.cht)" row in the scanner tool's printer mode
  takes the per-page .cht files printtarg wrote for the chart — pick the .ti2,
  then the .cht page files, and the chart loads like any ChromIQ chart (grid
  overlay, page selector, scanner-as-instrument reading). The picked pages are
  verified against the chart's .ti2 patch by patch, so a wrong or missing page
  is caught before anything is read. For ChromIQ charts the row simply notes
  that the geometry comes with the chart.

## v3.13.0-beta.111

### 🐛 Fixes
- Create Chart / layout editor: charts built with the ChromIQ layout engine
  lost their New-patch-set creation recipe end-to-end (#100) — the editor's
  engine save wrote no meta.json, the Apply/Overwrite hand-off dropped the
  recipe, the preset save overwrote its instrument/paper/layout from the hidden
  printtarg widgets, and the "Fill remaining space: pages" unit was never
  saved. Presets made from engine charts now reload their full design into the
  New Patch Set window (auto-load and "Load setup from preset").
- Scanner/camera profile tool: picking a chart honoured a sibling .ti3 over the
  .ti2 you actually chose, and a rejected chart only updated a small note while
  the scan Browse button later showed a generic (and in printer mode wrong)
  hint (#101). The picked file now wins, rejections land in the status log with
  the concrete reason, the Browse hint matches the mode, and a chart whose
  .channels.json was renamed/copied is found via the folder's single sidecar.
- Scanner/camera profile tool: with several scans averaged, only the first got
  a diagnostic image (#102) — every scan now writes its own <scan>-diag.tif.

### ✨ New
- New "Scanner" group of built-in presets (Create Chart → Manual, dropdown and
  ★ overlay): Knut's two flatbed-scanner printer-profiling charts (A4 3430
  patches / US-Letter 3250 patches, 4 mm patch grid, 1 page). Print without
  colour management, scan on a flatbed, then profile the printer via Tools →
  "Build scanner or camera profile".
- Scanner/camera profile tool: optional "Profile name" field — name the
  finished .icc (file and embedded description) yourself, e.g.
  "Epson ET-8550 scanner", instead of inheriting the chart/target name — and an
  "Install profile" button that copies it into your user colour-profile folder
  (ColorSync on macOS).

## v3.13.0-beta.110

### 🐛 Fixes
- Light mode: radio buttons (e.g. the "chart I made / standard target" chooser
  in the scanner window) rendered a broken square when selected and vanished on
  hover. The light theme was missing its `QRadioButton::indicator` rule, so a
  dialog's neutral-accent override half-styled the control. Added the rule
  (mirrors the dark theme) — radios are now round and consistent in both themes.

## v3.13.0-beta.109

### 🌍 Translations complete again
- The new "use the operating system's file browser" setting (label + its long
  help) and the leftover density / "Punchy" options are now translated in all 12
  languages — the catalogs are complete (only genuine cognates remain identical
  to English).

## v3.13.0-beta.108

### 🖨️ Printer profiling works from a chart you only *printed* (Knut)
- The printer-profile mode no longer needs a measured `.ti3`. Tick "Profile my
  printer from this scan" and the chart picker accepts the chart you **printed**
  (its `.ti2`) — ChromIQ reads the device values + aim colours straight from it,
  so no spectrophotometer reading is required anywhere in the loop. Works for
  both engine and printtarg charts (both write a `.ti2`).
- The picker label + help switch to match the mode, scanner mode still requires a
  real measurement, and every new string is translated in all 12 languages.

## v3.13.0-beta.107

### 🖨️ Profile your printer with a scanner (Knut)
- The scanner/camera-profile window can now build a profile for your **printer**
  from a scan of a chart you printed — using a flat-bed scanner in place of a
  spectrophotometer. Tick "Profile my printer from this scan", point it at the
  scanner profile you built earlier, and ChromIQ runs `scanin -c` (converting the
  scan to real colour through that scanner profile) and colprof to produce the
  printer profile. No spectro required.
- Help lives behind the ⓘ icons (click to open), and every string is translated
  in all 12 languages.

## v3.13.0-beta.106

### 🌍 Translations
- The scanner/camera-profile strings — labels, notes and the extensive tooltips
  (sample area, fiducial marks, Reading options, demo scan) — are now translated
  in all 12 languages; the catalogs are complete again.

## v3.13.0-beta.105

### ✨ Scanner: complete "Reading options" help
- The **Reading options** help now covers all three checkboxes — it was missing a
  friendly explanation of **Use fiducial marks** (and wrongly said "two settings").

## v3.13.0-beta.104

### 🐛 Scanner: interior grid alignment on rounded targets (Hutchcolor)
- On targets with **gaps** in the grid (e.g. Hutchcolor), the reading grid's inner
  columns/rows could look off-centre on a rectarg image even when the corners lined
  up — because those images round patch sizes unevenly and the gapped grid was
  placed uniformly. The marquee **and** scanin now place every patch on rectarg's
  exact integer edges (the same calculation full grids already used), so the whole
  grid — corners *and* interior — lines up. Reads were already clean; this fixes
  how it looks and unifies the two calculations.

## v3.13.0-beta.103

### ✨ Scanner: fiducial option hidden for ChromIQ charts
- In **A chart I made in ChromIQ** mode the **Use fiducial marks** checkbox is now
  hidden (ChromIQ charts print no fiducial marks), and the same align-the-patches
  process is used as for standard targets.

## v3.13.0-beta.102

### ✨ Scanner: fiducial frame drawn on screen + one shared geometry
- Turning on **Use fiducial marks** now **draws the fiducial frame** (a dashed
  outline) around the patch grid, so you can see the registration band while your
  four corners stay on the easy-to-aim patch block. Both targets and the "Other"
  option go through **one shared geometry** now — the grid, the on-screen frame,
  and the reader's alignment all come from the same calculation.
- The fiducial-marks tooltip is rewritten in plain language.

## v3.13.0-beta.101

### 🐛 Fixed — "Use fiducial marks" now aligns correctly (all targets)
- With **Use fiducial marks ON**, the reading grid could come out the wrong size on
  targets whose fiducials sit a little outside the patches (LaserSoft Advanced,
  LaserSoft DCPro, CMP) — because it asked you to place the corners on marks the
  scan doesn't clearly show. Now you **always line up the four corners on the patch
  block** (the reliable, always-visible reference), and ChromIQ **derives** the
  reference for the reader from that one alignment — the patch area when off, the
  target's fiducial frame when on. **Both settings now place the grid identically**,
  so on is as reliable as off. Verified on every bundled target.

## v3.13.0-beta.100

### 🐛 Fixed — scanner/camera targets now register correctly (incl. CMP)
- The bundled scanner-target recognition files (`.cht`) have been **regenerated to
  match rectarg exactly** — correct patch positions, the **real fiducial marks**,
  and patch names built with rectarg's own label logic (alpha-first, `2A1`/`GS`/
  Excel-alpha, padding-tolerant). Previously the **CMP Digital Target-4** failed in
  scanin entirely, and other targets could misregister because ChromIQ's grid
  disagreed with the printed sheet. **All 8 targets now read back 100 % of their
  patches through scanin**, so a scanner/camera profile builds from any of them.
- "Use fiducial marks" now maps correctly: **on** uses the target's real fiducial
  marks; **off** frames by the patch block — so the reading grid lines up whether
  or not you use the marks.

## v3.13.0-beta.99

### 🐛 Fixed — scanner build no longer cries failure on a good profile
- colprof can **exit non-zero *after* it has written a valid profile** (seen on
  Windows, right after "Profile done"), and on Windows it may write **`.icm`**
  rather than `.icc`. Either could make ChromIQ report **"Building the profile
  failed"** and hide the result — even though a perfectly good scanner profile was
  sitting next to the scan (Nelson: avg err 3.77 ΔE, proper white point). The build
  now **trusts the profile on disk over the exit code**, resolving it with the same
  robust `.icc`/`.icm` lookup the printer builder uses, so a successful build always
  reports success, prints the path, and shows the **Reveal profile** button.

## v3.13.0-beta.98

### ✨ Added — "Reveal profile" button
- After a scanner/camera profile builds, a **"Reveal profile"** button appears in
  the dialog and opens the folder containing the new `.icc` — so it's easy to find
  and install (ChromIQ doesn't auto-install scanner profiles; they're saved next to
  the scan). Hidden until a profile has been built.

## v3.13.0-beta.97

### 🔧 Changed — scanner profile build now runs colprof verbosely
- The scanner/camera profile build now passes **`colprof -v`**, so its progress and
  any error are shown in the log. Without it, colprof is **silent on success**,
  which made a failure indistinguishable from "no output" (Nelson). Now a build
  either prints **"Profile done"** or the exact reason it stopped.

## v3.13.0-beta.96

### 🐛 Fixed — the real colprof error is no longer hidden
- When building a scanner/camera profile fails, ChromIQ now prints **colprof's
  actual last output** instead of the unhelpful *"failed — see messages above"*
  (there was often nothing above it). So if a build fails, you can see exactly what
  colprof objected to. Pairs with beta.95's fix that drops unreadable-value patches
  rather than zero-filling them — together, a scanner profile that used to fail
  silently now either builds or tells you precisely why.

## v3.13.0-beta.95

### 🐛 Fixed — cleaner .ti3 recovery from unreadable patches
- The scanner-`.ti3` sanitiser (beta.93) is now smarter about *how* it recovers a
  degenerate patch. A patch whose actual **colour value** (device `RGB` / reference
  `XYZ`) couldn't be read is now **dropped** from the read (and `NUMBER_OF_SETS`
  updated) instead of zero-filled — so it can't become a false "reads as black"
  point that would distort the profile. A bad **noise figure** (`STDEV`) *alone* is
  still just set to 0 (no effect on the measured colour). Verified end-to-end:
  `colprof` rejects the raw nan file but builds a valid profile from the sanitised
  one.

## v3.13.0-beta.94

### 🔧 Changed — scan arrow on engine charts without strip labels
- On a ChromIQ-engine chart that has **no strip labels**, the measure-tab scan
  arrow now floats with its **tip just above the patch area**, instead of hanging
  from a label band that isn't there. Charts **with** strip labels (and printtarg
  charts) keep the arrow hanging directly under the labels, printtarg-style. The
  engine sidecar now records the rendered label-band bottom so the anchor is exact.

## v3.13.0-beta.93

### 🐛 Fixed — scanner-profile build crash (Nelson, Windows)
- **A patch that didn't read cleanly no longer aborts the whole profile.** When
  scanin can't read a patch (e.g. a box that caught too few pixels) it writes
  nan/inf for that patch's numbers — on Windows as `1.#IND` / `-1.#INF` — and
  colprof's strict CGATS parser then rejected the **entire** `.ti3`
  (*"Field 'STDEV_B' … is 'non-quoted char string'"*). ChromIQ now sanitises
  scanin's `.ti3` (those values become 0) before colprof, so the profile builds,
  with a note to re-check the grid covers every patch if the result looks off.

## v3.13.0-beta.92

### ✨ Changed — "Use fiducial marks" now visibly adds the band (Knut)
- Ticking **"Use fiducial marks"** now **grows the selection quad outward to the
  registration marks** — adding the fiducial band around the patch grid — and
  un-ticking shrinks it back, keeping the patches on the same spot. Before, it only
  changed the internal framing, which was invisible for most targets (only Wolf
  Faust's large frame difference showed). Now every target with fiducials visibly
  reframes when you toggle the box. The corner-move uses the quad homography, so it
  works on a skewed placement too.

## v3.13.0-beta.91

### ✨ Added — "Use fiducial marks" now works (Knut)
- The **"Use fiducial marks in the .cht"** checkbox is now functional for the
  bundled targets. Each bundled `.cht` carries a fiducial-mark frame — computed
  from the target's **rectarg** geometry (patch-area corners expanded by
  `pre − pre_f` top-left and `post` bottom-right, per Knut's spec) — stored as a
  `# CHROMIQ_FIDUCIALS` marker. With it **on**, the reading grid frames to the
  registration marks, so you place the four corners on the **fiducials** instead of
  the patch-area corners — for both the on-screen grid **and** the scanin read
  (scanin's `-F` is handed the fiducial frame). **Off** (default) uses the patch
  area, unchanged. The checkbox now enables for every bundled target that defines
  fiducials distinct from its patch block.

## v3.13.0-beta.90

### 🐛 Fixed — scanner-target geometry (Knut)
- **SpyderChecker, QPcard 202 and SpyderChecker 24 now align — grid *and* scanin
  diagnostic.** Their bundled `.cht` came from Argyll's `ref/`, which *spaces* the
  patches (pitch = `xi`); but rectarg and the real targets place them **contiguous
  (pitch = `tile`)**. Decoding the format with Knut: the last number pair on a
  patch-area line is the post-fiducial offset, **not** the patch pitch. Regenerated
  those three files at the correct contiguous pitch, with the `F` line set to the
  patch-area bounding box so scanin's `-F` maps the exact frame the marquee places
  its corners on (so the read no longer drifts from the on-screen grid). The other
  five targets were already correct.

### 🔧 Removed
- **"Match rectarg preview (patches touching)" checkbox.** It only existed to work
  around the wrong geometry above; now that the geometry is right by default, it's
  gone. The reading options are just Correct perspective, Save diagnostic image,
  and Use fiducial marks.

## v3.13.0-beta.89

### 🔧 Changed
- **Reading-options checkboxes now line up.** The four checkboxes (Correct
  perspective, Save diagnostic image, Match rectarg preview, Use fiducial marks)
  share one grid, so their two columns align (Knut).
- **Honest "Match rectarg preview" help.** Reworded to say plainly what it does and
  that which spacing is right for a real physical scan of the few affected targets
  (SpyderChecker, QPcard 202, SpyderChecker 24) is still being confirmed — pending
  a real-target scan.

## v3.13.0-beta.88

### 🔧 Changed
- **Friendlier, fuller reading-options help.** Rewrote the tooltips for the reading
  options — Correct perspective, Save a diagnostic image, "Match rectarg preview",
  and "Use fiducial marks" — in plain, beginner-facing language that says what each
  does, when to use it, and what to expect, leaving no open questions. Also fixed
  the patch-sample-area tip to say 50% (the current default).
- **Pop-out "Done" button is now green** (the scanner/measure accent) instead of the
  global blue — the pop-out is its own window and didn't inherit the dialog accent.

## v3.13.0-beta.87

### ✅ Tests / demo scan (Knut)
- **Demo-scan colours now span dark→light in a scrambled order** (`demo_patch_color`:
  golden-ratio hue + bit-reversed lightness). Neighbouring patches differ a lot
  (min RGB distance 114 of ~441), so if the reading grid slipped onto a neighbour
  cell the colour it picked up would be very different — turning the demo into a
  real **misalignment detector** instead of one a smooth gradient could hide.
- **The scanin self-check now covers every supported target.** `make_test_scan`
  generates a known-colour scan + matching reference from each bundled target's own
  geometry, and the test reads them all back through the real `scanin` (asserting
  <3/100 error) — no need to ship large rendered images; the geometry is the truth.

## v3.13.0-beta.86

### 🔧 Changed
- **"Test files…" → "Try with a demo scan", and it now auto-loads.** The button was
  confusing — it opened a Finder window on a synthetic rainbow image that looked
  like an unknown "target". It now **loads** the generated demo scan + its matching
  reference straight into the dialog and says clearly, in the log, that this is a
  practice image drawn from the recognition file (each patch a flat colour), **not**
  a real target — and that a real profile needs your own scan + the reference that
  came with your physical target. (The bundled `.cht` files live in
  `data/scanner_targets/`; a target's `.cie` reference is vendor-specific and isn't
  bundled.)

### ✅ Tests
- The demo generator (`make_test_scan`) is now exercised end-to-end: its known
  colours are read back through the real `scanin` for a contiguous IT8 and two
  gapped targets (Knut's suggestion — the demo doubles as a scanin self-check).

## v3.13.0-beta.85

### 🐛 Fixed
- **"Test files…" crashed instead of running.** The handler wrote to the log with
  ``.append()``, but that log is a ``QPlainTextEdit`` (no such method) — so it threw
  every click. Now uses ``appendPlainText`` (and fixed one other stray call on the
  same widget). Guarded with a regression test.

## v3.13.0-beta.84

### ✨ Scanner reading grid — part 2 (Knut)
- **Remembers your placement.** When you build a profile, the grid position is
  stored per target (as fractions of the image), and restored the next time you
  scan that target — at any resolution. "Reset grid" returns to the computed default.
- **"Use fiducial marks in the .cht as reference"** — frame the grid by the .cht's
  registration marks (place the corners on the fiducials) when the target defines
  them. It flashes and stays off for targets without separate fiducials.
- **"Match rectarg preview (patches touching)"** — for *gapped* targets
  (SpyderChecker, QPcard, CMP …), whose real spacing leaves gaps ChromIQ honours
  by default. Turn it on to line the grid **and** the scanin read up with a gapless
  rectarg-rendered test image (patches re-placed at pitch = tile, exactly as
  rectarg draws them). Off by default — the default stays correct for real scans.
- **Self-contained result folder** — the reference .cie is copied next to the scan
  and outputs on build, so everything for a profile sits together.

## v3.13.0-beta.83

### ✨ Scanner reading grid — placement controls (Knut)
- **Mid-side handles.** Each edge now has a centre handle — drag it to move that
  whole side parallel, instead of nudging two corners to keep an edge straight.
- **Middle-mouse always pans.** Press the middle button and drag to pan the image
  from anywhere, even while zoomed in over the grid (no need to zoom out first).
- **"Reset grid" button.** Re-centres the reading grid at the size computed from
  the target — recovers a placement that drifted off-screen (e.g. after loading an
  image at a different resolution).
- **Pop-out returns zoomed-out.** Docking the bigger-view window back now resets the
  main view to fully zoomed-out and centred.

## v3.13.0-beta.82

### 🐛 Fixed
- **"Test files…" now responds instantly.** It rendered the test scan pixel-by-
  pixel in Python (freezing the UI for many seconds on a big target); it now uses
  `ImageDraw` and is effectively instant.

### 🔧 Changed
- **Default patch sample area is now 50%** (was 60%). 60% of the *area* is ~77% of
  the *side*, which looked too close to the patch edges; 50% pulls the read zone in.

## v3.13.0-beta.81

### 🌍 Translated
- Translated beta.80's new strings into all 12 languages (test-files control and
  message, the move/zoom help line, Scan N).

## v3.13.0-beta.80

### 🐛 Fixed
- **The reading grid now matches rectarg's reconstruction exactly.** For a regular
  target grid (ISO 12641, DCPro, …) the overlay replicates rectarg's integer-pixel
  column/row edges (each cell `floor(total/n)` px, the remainder into the first
  cells) at the placed quad's pixel size — eliminating the accumulating
  misalignment against a rectarg-rendered image. Multi-area targets (an IT8's GS
  strip) fall back to per-box.
- **The starting quad matches the target's aspect ratio** instead of a blind 8%
  inset, so it's already the right shape to nudge onto the patches.

### ✨ Added / Changed
- **Move / pan / zoom the grid view.** Drag *inside* the grid to move the whole
  selection; drag the *background* to pan; scroll or ⌘/Ctrl + scroll to zoom, plus
  ⌘/Ctrl +/− and ⌘/Ctrl + 0 (or double-click) to reset — with a help line spelling
  it out.
- **Two IT8 targets** in the dropdown: **ISO 12641‑1 — Wolf Faust** and
  **ISO 12641‑2 — LaserSoft Advanced**, both bundled with corrected geometry.
- **"Test files…" button** (standard-target mode): writes a known-good test scan +
  reference for the chosen target and reveals them, so you can try the grid with
  no hardware and find where the bundled recognition file lives.

### 🌍 Translated
- New UI strings staged as English placeholders (full pass to follow).

## v3.13.0-beta.79

### 🐛 Fixed
- **The scanner/camera reading grid now spans the whole patch block.** It is
  normalised into the **total patch-area bounding box** — the union of every
  patch box across all areas — so it always covers the complete target,
  including multiple sub-areas like an IT8's greyscale (GS) strip, and no longer
  depends on where the fiducial marks sit. This matches how rectarg derives a
  target's extent from its patch-area lines (the `.cht` `D` line is "overall
  chart dimensions, not used"). You place the four corners on that same patch
  block.

## v3.13.0-beta.78

### 🌍 Translated
- Translated this beta cycle's new UI strings into all 12 languages — the patch
  sample-area control and its help, the marquee zoom / pan / rotate / pop-out
  controls, the "choose your target first" guidance, and the grouped Tools-menu
  headers.

## v3.13.0-beta.77

### ✨ Changed
- **Setup guidance now lives on the field it's about.** The scan/photo field's ⓘ
  in Build scanner or camera profile now includes the full scanner **and** camera
  setup help inline — how to turn the device's colour management off, scanning
  resolution tips, and camera lighting/exposure — instead of pointing you up to
  the main ⓘ. (Knut: put the relevant help on the relevant control.)

## v3.13.0-beta.76

### ✨ Changed
- **The Tools menu is grouped by task** — Measurements, Charts & patch sets,
  Scanner & camera, i1Profiler interchange, Profiles, Language — with section
  headers, instead of one long flat list. Easier to scan for the tool you want.

### 🌍 Translated
- Group headers staged as English placeholders (full translation pass at GA).

## v3.13.0-beta.75

### ✨ Added
- **Much easier grid placement** in Build scanner or camera profile. The marquee
  view is bigger, and you can now **zoom** (Ctrl/Cmd + scroll) and **pan** (drag),
  **Rotate 90°** a sideways scan, **Reset view**, and **Pop out** the grid into a
  large separate window (with its own Rotate / Reset controls and a Done button —
  you still build the profile back in the main window). Plain scroll keeps
  scrolling the dialog.
- **Corner handles now sit *outside* the patch area**, each joined to its true
  corner by a 45° dotted line, so the grab circle never hides the corner patch
  you're aiming at.

### 🌍 Translated
- New UI strings staged as English placeholders (full translation pass at GA).

## v3.13.0-beta.74

### ✨ Added
- **Patch sample area control** (Build scanner or camera profile). A spinbox
  under the grid sets how much of each patch scanin reads — shown live as a
  filled green inner square inside every patch cell. It samples the centre and
  ignores the edges (ink bleed, borders, slight misalignment); 60% by default.

### 🐛 Fixed
- **The scan "Browse…" button no longer looks dead.** If the chosen `.ti3` isn't
  a ChromIQ layout-engine chart (e.g. an old file from a plain scanin run, with
  no `.channels.json`), clicking Browse now explains what to pick — or to switch
  to "A standard target I own" — in the status box, instead of doing nothing.

### 🌍 Translated
- New UI strings staged as English placeholders (full translation pass at GA).

## v3.13.0-beta.73

### ✨ Changed
- **Scanner/camera targets now key off the patch-area corners, not fiducial
  marks.** The real printed targets have no fiducial marks — just the patch grid —
  so every bundled recognition file now sets its reference (`F` line) to the
  patch-area bounding box. You place the reading grid on the **visible corners of
  the patch block**, and it registers the same at any scan resolution.
- **Four more targets, corrected and shipped.** QPcard 202, SpyderChecker,
  SpyderChecker 24 and CMP Digital Target-4 — previously dropped because their
  supplied files misregistered (box pitch too small, undersized fiducial, or a bad
  `EXPECTED` list) — are rebuilt onto the patch-area-corner convention with correct
  box geometry. The bundle is now seven targets (HutchColor, LaserSoft ISO
  12641-2, LaserSoft DCPro, QPcard 202, SpyderChecker, SpyderChecker 24, CMP
  Digital Target-4).

### 🧪 Internal
- New test drives the real `scanin -F` over every bundled target at 100 / 200 /
  300 dpi using the patch-area corners, and checks each patch reads back from the
  right place (`tests/test_scanner_multidpi.py`).

## v3.13.0-beta.72

### 🐛 Fixed
- **Scanner targets built from a ChromIQ chart are now readable by scanin.** The
  `.cht` writer counted the fiducial (`F`) line in its `BOXES` total, but
  ArgyllCMS `scanin` does not count it — so every engine-chart scanner target was
  one box over and `scanin` aborted with "More BOXes than declared". Found by a
  new hardware-free test that generates targets and reads them back; fixed the
  count (matching Argyll's own `.cht`).
- **Dropped four broken bundled targets.** beta.71 bundled `.cht` files whose
  corrected copies (QPcard 202, SpyderChecker, SpyderChecker 24, CMP Digital
  Target-4) turned out to misregister with `scanin` (tiny box pitch / undersized
  fiducial / inconsistent EXPECTED list). ChromIQ now bundles only the three that
  validate end-to-end (HutchColor, LaserSoft ISO 12641-2, LaserSoft DCPro) and
  falls back to Argyll's own — correct — `ref/` copies for the rest.

### 🧪 Internal
- New guarded end-to-end tests: self-made targets across many layouts, and each
  target rendered from its own geometry, driven through the real `scanin -F` and
  checked patch-by-patch. These validate registration with no hardware and caught
  the `BOXES` bug above.

## v3.13.0-beta.71

### ✨ Added
- **Corrected standard-target recognition files, bundled.** ChromIQ now ships a
  set of scanner/camera target `.cht` files with **fixed fiducial coordinates**
  (HutchColor HCT, LaserSoft DCPro, QPcard 202, SpyderChecker, SpyderChecker 24,
  CMP Digital Target-4). Several of the copies ArgyllCMS ships had wrong fiducial
  positions that broke registration on those targets; the bundled files —
  Knut Georg Larsson's corrected versions from the **rectarg** project — fix it.
  The "standard target" list in Build scanner or camera profile now prefers these
  over the copies in Argyll's `ref/`. Geometry only (no colours); your target's
  own reference file still supplies the true patch colours. Bundled under GPLv3
  with credit — see `data/scanner_targets/README.md`.

## v3.13.0-beta.70

### ✨ Added
- **Standard-target reference files convert themselves.** When you load a bought
  target's reference data in Build scanner or camera profile, ChromIQ now takes
  whatever format it came in and prepares it for you — no command line:
  - Ready-to-use **.cie / .txt / .ti3** (Wolf Faust, HutchColor, LaserSoft
    DCPro…) are used as-is.
  - An **X-Rite .cxf** (LaserSoft ISO 12641-2 targets) is converted with Argyll's
    `cxf2ti3`.
  - A **raw or spectral .txt** (CMP Digital Target measurements) is converted with
    `txt2ti3` + `spec2cie`.
  The converted copy goes to a temporary folder, so your download is untouched.

### 🧪 Internal
- **Hardware-free end-to-end test of the scanner/camera pipeline.** A new guarded
  test drives the real `scanin -F` → `colprof` chain against standard target
  reference images (using ChromIQ's own `.cht` parser to place the marquee
  corners) and asserts a healthy profile ΔE across the Wolf Faust, HutchColor and
  LaserSoft (ISO 12641-2 + DCPro) targets — validating registration with no
  printer or scanner.

### 🌍 Translated
- The new reference-format strings translated across the twelve languages.

## v3.13.0-beta.69

### 🐛 Fixed
- **Consistent camera wording in two more spots.** The Profile Quality
  Assessment tip now adds a note that, for a **camera**, accuracy depends on the
  light you shoot under rather than a reprint (pointing to "Profiling a camera").
  And the status line logged after saving a chart's scanner files now names the
  right tool — **Build scanner or camera profile** — and mentions photographing
  the chart, not just scanning it.

### 🌍 Translated
- The two updated strings translated across the twelve languages.

## v3.13.0-beta.68

### ✨ Changed
- **Scanner profiling now covers cameras too.** ArgyllCMS reads camera and
  scanner targets the same way, so the same tools profile a digital camera from
  a photo of a target:
  - **"Build scanner profile" is now "Build scanner or camera profile"** and
    **"Create scanner target" is now "Create scanner or camera target"**, in the
    Tools menu, the Welcome guide and the window titles.
  - Wording is device-neutral throughout ("scan or photo of the target"), with a
    new **"Profiling a camera"** help section covering the capture that matters
    (even light, shoot raw/flat, fill the frame, keep Matrix for small targets).
  - The **"Also save scanner-profiling files"** option (All Stripes Read /
    Profile Quality Assessment) now explains the files it saves work for
    profiling a **camera** as well — photograph the printed chart instead of
    scanning it.
  - The help's "which chart" guidance gains a **"Does this apply to a camera?"**
    note: same core idea, but a camera profile is tied to the **light** you
    shoot under (a printed chart suits flat repro work; a ready-made ColorChecker
    is easier for general photography).

### 🌍 Translated
- All the new and reworded scanner/camera strings translated across the twelve
  languages.

## v3.13.0-beta.67

### ✨ Added
- **Profile your scanner from a standard target you own.** Build scanner profile
  now has a second mode: choose a bought reflective target (Wolf Faust and other
  IT8 charts, LaserSoft, the X-Rite ColorCheckers, and every other target
  ArgyllCMS ships), point ChromIQ at the reference data file that came with it
  (.cie / .txt), scan it, and build — no ChromIQ chart, printing or measuring
  needed. ChromIQ reads the target's layout straight from its Argyll `.cht`.
- **Average several scans for a cleaner profile.** Scan the same sheet a few
  times and ChromIQ averages the reads to cancel out scanner noise. Add scans
  with "Add another scan to average" — each keeps its own corner placement —
  and pick how they combine: **Mean**, **Geometric mean** (robust to an odd
  scan) or **Trimmed mean**. Multi-page charts average within each page, then
  build one profile from all pages.
- **Choose the scanner profile type** — **Matrix** (recommended), **LUT medium**
  or **LUT high** — instead of a fixed setting.
- **A live grid for every target.** The alignment grid is now rebuilt from the
  chart's `.cht` (verified against all of Argyll's standard targets, including
  two-area targets like the Wolf Faust IT8), so it lines up on standard targets
  and older printtarg charts too.
- **More scanner help.** Scan-setup guidance (flat, colour-managed-off capture)
  and a "Getting the best result" walkthrough covering averaging, multi-page
  charts and standard targets.

### ✨ Changed
- **The Build scanner profile window scrolls** with a soft edge fade so it fits
  smaller screens — Build and Close stay pinned in view.

### 🐛 Fixed
- **Patch-set editor accent.** The "Show patch number" and "Show gap between
  patches" checkboxes now use the editor's magenta accent instead of the
  app-wide cyan, in both light and dark mode.

### 🌍 Translated
- All new scanner-profiling strings translated across the twelve languages.

## v3.13.0-beta.66

### ✨ Changed
- **"Blank canvas" removed from the New patch set window.** The patch-set
  editor itself is the blank canvas — start with any source and add, remove
  or recolour patches there. Saved setups and presets that carried the old
  mode simply keep the current selection.

### 🐛 Fixed
- **Unchecked radio buttons are visible in dark mode again.** In the patch-set
  editor and its New patch set / Add patches windows the unselected ring used
  a palette colour that disappeared on the dark background; it now uses the
  same explicit border colours as the checkboxes in both light and dark mode.

## v3.13.0-beta.65

### ✨ Added
- **Show/hide the "Chart layout information" panel.** Settings now has a toggle
  for the Create Chart layout-info panel, alongside the existing "Measured from
  Preview" toggle — so you can hide either preview panel under the chart. Takes
  effect immediately.

## v3.13.0-beta.64

### ✨ Added
- **Scanner profiling: guidance on which chart to use.** The scanner-tool help
  (Create scanner target / Build scanner profile) and a note in the **Profile
  Quality Assessment** window now weigh up the two options: reuse the chart you
  already measured (free, correct, ideal for general use) vs. print a fresh
  chart through your normal colour-managed workflow and measure it (most
  accurate when you mainly scan your own colour-managed prints). The reference
  colours always come from your measurement, so either is correct — the choice
  is about how well the target matches what you'll scan.
- **New "Profile my scanner" card** in the Welcome / help window, walking through
  measure → keep scanner files → scan → build.

### 🐛 Fixed
- **Clearer scanin failures.** ChromIQ now recognises Argyll's reference-file
  errors (a damaged or hand-edited `.cht`/`.cie`, a mismatched pair, or an
  out-of-memory on a huge scan) and shows a plain-language message —
  *"recreate the scanner files"* — instead of a raw error dump.

### 🌍 Translated
- The new scanner-help, Welcome card, and assessment-note strings, in all 12
  languages.

## v3.13.0-beta.63

### ✨ Added
- **Save scanner-profiling files from the Check & Refine step too** — the
  **Profile Quality Assessment** dialog now offers the same **"Also save
  scanner-profiling files for this chart"** checkbox as the measurement dialog
  (shown only for charts ChromIQ has the geometry for). Tick it and whichever
  button you press — **Confirm**, **Install Profile**, **Use as
  Pre-conditioning**, or **Guide Me Through Refinement** — writes the chart's
  `.cht` + `.cie` from the measurement you just assessed. The dialog's former
  **Close** button is now labelled **Confirm**.

### 🐛 Fixed
- Two buttons were dropping their **"&"** — **"Average all reads & build"** and
  **"Clear & Print"** rendered as *"Average all reads build"* / *"Clear Print"*
  because Qt treated the ampersand as a keyboard-shortcut marker. They now read
  correctly.
- Dark mode: removed a stray dark box behind the scanner-profiling checkbox
  label so the card's tint shows through cleanly.

### 🌍 Translated
- Full 12-language translations of the scanner-profiling strings (#97, #98).
- Wrapped the layout-editor masthead tooltip for translation and split the
  page-count messages into proper singular/plural forms.

## v3.13.0-beta.62

### ✨ Added
- **Scanner profiling** — build an ICC profile for your **scanner** from a
  printed ChromIQ chart, no dedicated target chart needed (#97, #98):
  - After measuring, tick **"Also save scanner-profiling files for this chart"**
    in the "All Stripes Read" dialog (or use **Tools ▸ Create scanner target**)
    to write the chart's `.cht` + `.cie` — where each patch sits plus the real
    colours the spectrophotometer measured. They rebuild automatically from
    every finalised measurement, so they never go stale.
  - **Tools ▸ Build scanner profile (from a scan)** — pick the measured chart
    and a flatbed scan of the printed chart, drag four corners over the patch
    area until the live green grid lines up, and ChromIQ runs `scanin` + `colprof`
    to write a scanner profile next to the scan. Multi-page charts: one scan and
    placement per page, combined into one profile. The help explains how to use
    the resulting profile. Scanner outputs are named `-scanner` so they can never
    overwrite the printer profile.
  - Works for both layout-engine charts **and** printtarg / preset charts: at
    creation ChromIQ captures printtarg's exact `.cht` geometry (a fast,
    seed-independent re-run) after verifying it against the chart's own `.ti2`,
    so it's correct or simply absent — never wrong (#8). Charts made in older
    versions show an honest "recreate the chart to enable scanner files" note.

### 🔧 Changed
- Charts no longer write a `.cht` at creation time: a recognition template is
  only meaningful paired with a *measured* `.cie` (the aim `.cie` was dropped in
  beta.59), so both are now produced together from the measurement.

## v3.13.0-beta.60

### 🐛 Fixed
- Patch-set generator, "Fill remaining gaps": removed the leftover radio button
  in front of "patches" (the pages option is gone), moved "patches" to the right
  of the spinbox, matched the spinbox width to the other rows, and it's now
  greyed out when "Fill remaining gaps" is unticked (light and dark).

## v3.13.0-beta.59

### 🔧 Changed
- Dropped the `.cie` sidecar added in beta.57: its values were the chart's *aim*
  colours (sRGB-reconstructed), not measurements, so it didn't carry meaningful
  data for a `.cie` (which is a measured reference). Charts still get the colour
  list, the i1Profiler pair and the `.cht` recognition template.

## v3.13.0-beta.58

### 🐛 Fixed
- Renaming a project now also renames its chart hand-off sidecars — the colour
  list (`-colours.txt`), the `.cie` reference and the `.cht` template — so a
  renamed project stays self-consistent (the i1Profiler pair already followed).

## v3.13.0-beta.57

### 🐛 Fixed
- The patch-set editor's **Apply / Save** again writes the hand-off files for
  **engine** charts (it had only been doing so for printtarg charts): the colour
  list (`-colours.txt`), the i1Profiler pair (`-i1profiler.txt` / `.pxf`) and now
  a `.cie` reference.

### ➕ Added
- Every chart made from the **Create Chart** tab now always leaves those
  hand-off files in the run folder — not just for the i1iSis flow — so a
  generated chart is self-contained for profiling elsewhere.
- Charts now also get a **`.cht`** recognition template and a **`.cie`**
  reference (aim XYZ, read from the `.ti2` so it lines up with the `.cht`),
  enabling a `scanin` flatbed read. The engine now emits the `.cht` by default;
  printtarg already did. (The `.cie` values are the chart's aim colours, not
  measurements; colour list and `.cie` are RGB-chart only.)

### ➕ Added
- **New Tool: "Apply a device-link to an image".** Pushes your images through a
  device-link with `cctiff` and saves a **printer-ready TIFF** next to each
  (`<name>-printready.tif`) — already in the printer's own colours, no profile
  attached. Print it **raw** (the way charts are printed, driver colour
  management off) or load it in a RIP. This sidesteps the driver double-managing
  the link's output (the cause of "orange" prints on some Canon drivers), and it
  never touches the print pipeline so it works cross-platform.
  - **Source-space auto-fix:** the "Create device-link" tool now drops a small
    `.source.icc` sidecar next to each link, so the Apply tool knows the space
    the link expects. When an image is in a *different* space it is converted
    into the link's source first (v4 embedded profiles transcoded to v2) — so
    results are correct even if the image wasn't already in the link's source
    space. Third-party links without a sidecar fall back to a clear warning.
  - Multi-image, image preview, amber (print-family) accent, ⓘ per option.

### 🔧 Changed
- Built device-links now record their source colour space (a `.source.icc`
  sidecar) and are remembered as the "last link" for one-click auto-fill.
- All new strings translated into the 12 UI languages.

## v3.13.0-beta.55

### 🌍 Translated
- The layout-engine UI — the Create Chart layout panel, the Chart Layout and
  Instrument Limits settings tabs, the patch-set editor and the chart-layout
  information panel, plus all their tooltips — is now **fully translated in all 12
  languages** (German, Dutch, Spanish, French, Italian, Japanese, Norwegian,
  Polish, Portuguese, Russian, Swedish, Simplified Chinese). Each language uses
  ChromIQ's established terminology so the wording stays consistent across the app.

## v3.13.0-beta.54

### 🔧 Changed
- **Device-link Rendering-style help** now notes that perceptual (and its
  variants) can nudge very saturated colours — magenta especially — a few
  degrees to keep gradations smooth, and points hue-critical work to *Accurate
  colours*. (From backtomarfa's #99 measurements: the hue shift is Argyll's
  perceptual gamut mapping, not a ChromIQ defect, and is fully intent-selectable.)
- **Built profiles are now self-identifying:** colprof is always given a
  manufacturer (`ChromIQ`) and model (the profile description), so the device-ID
  tags are populated. A device-link built from a ChromIQ profile then carries a
  proper profile-sequence (`pseq`) instead of a blank/placeholder entry.

## v3.13.0-beta.53

### 🐛 Fixed
- **TIFF preview (Create Chart / Print / Measure):** the ‹ Prev / Next › page
  buttons appeared active on a freshly-opened tab before any file was loaded —
  the preview didn't apply its empty-state nav update until the first load or
  clear. They now hide/disable immediately, matching the loaded behaviour.

## v3.13.0-beta.52

### ➕ Added
- Device-link **Image-gamut detail** gains a **Custom…** option that reveals a
  raw 0–100 spinner for tiffgamut's `-f` filter, alongside the named presets.

### 🔧 Changed
- Device-link **Add images… / Remove** buttons are now compact and no longer
  crowd the control below them.
- New strings translated into the 12 UI languages.

## v3.13.0-beta.51

### ➕ Added
- **Device-link Tool — image-optimised gamut mapping (from backtomarfa's testing, #99):**
  - **Optimise for specific images** now takes a *set* of images (add/remove
    list) and builds one shared source gamut — map a whole exhibition series
    identically, not just a single picture.
  - New **Image-gamut detail** control (tiffgamut `-f` popularity filter) to
    trade off holding the main colours' saturation vs. preserving every
    gradation.
  - The image gamut is now built in **CIECAM02 appearance space** (`-pj`) with
    the link's own viewing conditions, so it actually lines up with the
    perceptual gamut mapping — the reason a source-image gamut can now bite.
  - **Rendering style** gains collink's finer gamut-mapping intents, including
    **Luminance-preserving perceptual**, which often suits matte fine-art paper.

### 🔧 Changed
- Device-link help text now explains the Photoshop step in full: turn on
  **Advanced** in *Convert to Profile* (device-links only appear there), pick it
  under *Device Link*, and print with the printer's colour management off.
- The loaded-images list is taller and shows just the file name (full path on hover).
- All new device-link strings translated into the 12 UI languages.

## v3.13.0-beta.50

### 🔧 Changed
- **ColorMunki Density** is now **hidden** (not greyed out) in "Prioritise chart
  area" mode, where the columns/rows define the grid — matching how the
  Calculation-method rows are hidden in "Prioritise patch size" (Knut).
- **"Offset every second strip"** moved from *Patches & spacers* into the
  **Layout** section, next to the other ColorMunki layout choices (Knut).
- Corrected the Density tooltip: "Hand-held" still reads whole strips — just a
  few large, widely-spaced patches — rather than "one patch at a time".

## v3.13.0-beta.49

### 🐛 Fixed
- **Settings → Chart Layout:** the "Show strip indicators" checkbox was drawn on
  top of the "Basic" section header (overlapping text) because it wasn't placed in
  the layout when the panel has no built-in selectors. It now sits correctly as a
  row in the Layout group, matching the Create Chart panel.

## v3.13.0-beta.48

### 🔧 Changed
- **Device-link Tool polish:**
  - Browse buttons now use the cyan folder icon (matching the rest of the app)
    instead of a "Browse…" text button.
  - Profile pickers add the OS ICC/ICM profile folders to the file-dialog
    sidebar shortcuts; the image picker shows a thumbnail preview pane.
  - **Viewing conditions** are now two separate dropdowns — *Screen* (monitor in
    a typical / bright / darkened room) and *Print* (normal indoor light / D50
    viewing booth / CIE 116-1995 / partial mid-tone adaptation) — each with a
    plain-language explanation, replacing the three combined presets.
  - The **Create device-link** button now shows an inactive state (muted fill
    with a cyan accent border) until the required fields are filled.

### 🐛 Fixed
- File-dialog ICC profile sidebar shortcuts are now correct cross-platform:
  honour `%SystemRoot%` on Windows (not a hardcoded `C:`) and include the modern
  `~/.local/share/icc` per-user directory on Linux.

## v3.13.0-beta.47

### ➕ Added
- **New Tool: "Create device-link profile"** (Tools menu). Builds an ICC
  device-link from a source profile (sRGB, AdobeRGB, ProPhoto…) and your printer
  profile, baking the gamut mapping in up front — apply it later in Photoshop's
  *Convert to Profile* or a RIP for repeatable colour across a print series.
  Wraps ArgyllCMS `collink`.
  - Friendly presets for rendering style, viewing conditions and quality, with
    an info (ⓘ) explanation on every option.
  - **Expert section** (collapsible): optimise the mapping for one specific
    image (via `tiffgamut`), abstract "tweak" profile, bake-in calibration,
    3DLUT export (.cube / eeColor / MadVR), inverse-table gamut mode, and forced
    white point.
  - **ICC v4 sources are converted to v2 automatically** (Argyll only reads v2)
    for standard matrix RGB profiles; the converted copy is a temp file removed
    after the link is built. Non-convertible v4 profiles get a clear message.

## v3.13.0-beta.46

### 🐛 Fixed
- **Layout-engine ↔ printtarg setting transfer** now carries the full set of
  shared options across the "Use the ChromIQ layout engine" toggle, in both
  directions: instrument, paper, pages, resolution, patch scale, clip border,
  density, spacers (none / B&W / coloured), bit depth, TIFF compression,
  randomise on/off and the fixed seed — not just instrument/paper/margin/scale.
- **Margins survive a toggle round-trip.** printtarg has a single margin while
  the engine has four; the four are now only collapsed onto printtarg's `-m`
  when they're all equal (lossless). When they differ, printtarg's margin is left
  untouched and the distinct engine values are restored on the way back — so you
  no longer lose, say, a 24 mm top / 9 mm sides setup by clicking the toggle.
  (If you deliberately change printtarg's margin while it's shown, that single
  value still applies to all four on return.)

## v3.13.0-beta.45

### 🐛 Fixed
- Area-first **"By columns / rows"**: a pinned *patches-per-strip* (rows) value
  on a float boundary rendered one row short, leaving a row-tall gap at the bottom
  (Knut: 16 cols × 15 rows drew only 14). The row-count fill now nudges off the
  float boundary so the chart always renders exactly the pinned number of rows;
  the same guard is applied to the auto/derived row paths.

## v3.13.0-beta.44

### 🐛 Fixed
- Area-first **"minimum patch height %" is now a true minimum**: the patch height
  is never below `patch width × (% / 100)`. When filling the box would make the
  patches shorter than that floor, they are stretched taller (fewer rows) and the
  count overflows to more pages if needed — it never comes out under the set
  height %. (Knut: 7.0 mm width + 130 % was producing 7.96 × 8.97 mm, an 8.97 mm
  height below the 10.35 mm floor; it now fills on one page at the correct shape.)
- Near-capacity counts that grew by columns alone could leave a wide right-edge
  gap; the fill now spans both axes for every below-capacity count.

## v3.13.0-beta.43

### 🐛 Fixed
- Area-first now reliably **fills the patch area for any patch set below one
  page's capacity** (including counts right at the capacity boundary that used to
  leave a gap), and a set larger than one page **overflows to more pages at the
  minimum size — never shrinks below the minimum**.

## v3.13.0-beta.42

### 🐛 Fixed
- Area-first fill refinement: a normal full chart now keeps the patch aspect you
  set (e.g. 100% height stays roughly square); the grow-to-fill only steps in
  when a fixed patch set would otherwise leave a gap.

## v3.13.0-beta.41

### 🐛 Fixed
- **Area-first now always fills the patch area for the chart's patch count.** The
  "minimum patch width" was being used like an exact size when the count was fixed
  (a loaded patch set / live re-layout), leaving a big gap on the right/bottom.
  Now the patches are sized so the whole margin box is filled — they grow above
  the minimum as needed (e.g. 7.5 mm minimum with 576 patches → ~8.7 mm), and the
  height follows the resulting width via the height-%. The minimum is a floor, not
  a fixed value.

## v3.13.0-beta.40

### 🐛 Fixed
- Patch-set editor: the **gap-size spinboxes showed no value** (the box was too
  narrow for the digits after the arrows). Widened so the value is visible.

## v3.13.0-beta.39

### 🐛 Fixed
- **Area-first "Minimum patch width = auto" now fills the chart area** like a
  typed minimum (the label says *minimum*): it takes the instrument's natural
  width as the floor and grows the patches to fill the usable width; the height
  follows via the height-% and fills too — both dimensions fill the margin box.
- **Built-in presets** (TC9.18, "by Pharmacist", Full-layout-setup) now load with
  the printtarg engine, so the layout shows the preset's real instrument / paper /
  orientation instead of the engine's defaults. Switch to the ChromIQ engine
  afterwards to convert the settings.

### 🔧 Changed
- Collapsible section headers have **bigger ▶/▼ arrows and bold titles** so they
  clearly read as open/close controls.
- Inch readouts are now **3 decimals**, and added to the gap / clip-border-width
  fields that were missing them.
- **"Use instrument margins" defaults on** (a new chart respects the jig margins).
- In Manual, the four targen **Auto** options default on.
- Patch-set editor: **total patch count shown under the grid**; the gap-size row
  is compact so it no longer overflows.

## v3.13.0-beta.38

### 🔧 Changed
- **Clip-border content now uses the full height of the page** (only a small
  printer-safe inset off the top/bottom edges), instead of being boxed in by the
  patch margins — so the notes box / logo can use the whole strip.
- **"Edit patch recipe" moved above the targen frame** so it stays visible when
  that frame is collapsed; ticking it expands the frame.
- New **"Auto-update preview when a layout setting changes"** option in Manual
  (remembered between sessions, with an info pop-up and ⓘ tooltip). Once you've
  generated a chart, changing a layout setting re-renders the preview by itself —
  it re-lays-out the existing patches (fast, no new colours) and hides the
  "room left on the last page" reminder while on. Guided ignores it.
- In Manual, the four targen **Auto** options (patch count, white, black, grey
  steps) now default **on**.

## v3.13.0-beta.37

### 🔧 Changed
- In the clip-border content section, the **image controls (path, rotate, scale,
  move) are hidden unless the content type is "Imported image"** — less clutter
  for the text / notes / branding modes.

## v3.13.0-beta.36

### 🐛 Fixed
- Turning the i1 / i1Pro 3+ clip border **on** now defaults its content to the
  notes box instead of "none" (so the record strip appears), matching the
  ColorMunki/SpectroScan behaviour. A chart that deliberately keeps the clip
  border on with no content is left as-is.

## v3.13.0-beta.35

### 🔧 Changed
- **Guided mode always uses the ChromIQ engine** now (it reproduces printtarg's
  Guided geometry exactly); the "Use the ChromIQ layout engine" toggle governs
  the Manual tab only.
- **Switching that Manual toggle converts your settings** between the printtarg
  controls and the engine layout panel (instrument, paper, margins, patch scale,
  clip border, density, strip-length limit), so the layout you set up isn't lost
  when you flip it.
- **Tab switching is tidier:** a plain Guided↔Manual switch carries only the
  instrument and paper; the rest of the settings transfer when you actually
  generate the chart (no more half-settings jumping between tabs).
- ColorMunki double-density now staggers in Guided, matching printtarg's rig.

## v3.13.0-beta.34

### 🐛 Fixed
- **Guided→Manual now reproduces the engine chart exactly.** With the ChromIQ
  engine on, opening Manual after generating in Guided carried only the
  instrument/paper, so Manual re-added a clip border you'd suppressed and the
  patches sat closer to the strip labels. The full engine recipe Guided used
  (clip-border suppression, margins, patch scale, density, edge spacers) now
  carries into the Manual layout panel.

### 🔧 Changed
- Create Chart layout reorganised into collapsible **Basic** (Layout, Page
  geometry, Randomisation) and **Expert Options** sections; the targen / printtarg
  / ChromIQ-layout frames are collapsible (targen starts collapsed). Collapsed
  frames drop their border so only the title line shows. The "Use the ChromIQ
  layout engine" toggle moved above the printtarg section.

## v3.13.0-beta.33

### 🔧 Changed
- **Collapsible sections in Create Chart.** Click a frame's title (▾/▸) to fold
  it away. In the ChromIQ layout panel, Layout and Page geometry start open and
  the rest (Patches & spacers, Randomisation, Output, Sheet text, Clip-border
  content, Printer calibration) start collapsed. The targen / printtarg Expert
  frames start collapsed, and the targen Basic frame folds away while the recipe
  is locked ("Edit patch recipe" off).

## v3.13.0-beta.32

### 🐛 Fixed
- **Generating in Manual after Guided now uses the right settings.** With the
  ChromIQ engine on, a Manual chart is built from the engine layout panel; the
  Guided→Manual carry-over updated the printtarg fields but left the panel on its
  old instrument/paper, so the generated chart was wrong. The instrument, paper
  and pages now follow into the panel too.

## v3.13.0-beta.31

### 🐛 Fixed
- **#18 — edge spacers no longer appear to overflow the margins.** The bracket
  (edge) spacers print one gap-thickness above the first patch and below the
  last, but the measured margins / guide lines were measured to the patches
  only, so the spacers sat outside the purple guide lines (worse with a larger
  inter-patch gap). The measured margins now include the edge-spacer overhang,
  so the guides match what prints.
- **Duplicate engine toggle removed** — "Use the ChromIQ layout engine" was
  showing twice in Create Chart → Manual (above both the targen and printtarg
  sections). Now shown once.

### 🔧 Changed
- **Strip-indicator styling moved to Settings → Chart Layout** (font, size,
  bold/italic, rotation, alignment, label offset, underline) as the default for
  new charts; Create Chart keeps just a "Show strip indicators" checkbox in the
  Layout frame, above Clip border. Saved presets still carry and restore their
  own styling.
- **Guided ↔ Manual now stay in sync.** Changing a shared setting (instrument,
  paper, pages, double/triple density, left border, strip limit, pre-conditioning)
  in one tab carries it to the other when you switch — without overwriting a
  setting the other tab can't represent.
- **Default Patch Sizes table removed** — the area-first "auto" column/row count
  aims for the instrument's natural patch size, explained in the columns/rows
  help. (Simpler; no separate table to keep.)
- Create Chart layout panel: **Page geometry now sits directly under Layout**.
- Editor: the **gap-size spinboxes** are wider so "30 px" and the arrows fit.

## v3.13.0-beta.30

### 🐛 Fixed
- **Multi-page engine charts report the right strip count per page** — the
  on-screen "strips / patches this page" now matches the preview and the estimate,
  and chartread segments the pages correctly (PASSES_IN_STRIPS2 was a single
  wrong number).

### 🔧 Changed
- **Patch-set editor swatch grid:** when "Show gap between patches" is on you can
  set the **Horizontal and Vertical gap** independently (1–30 px); selected
  patches get a pink border so the selection is visible even with numbers and gaps
  off; horizontal and vertical gaps are equal by default.
- **Create Chart layout panel reorg:** the Layout frame sits above Page geometry;
  "Max strip length", "Chart offset" and "Don't cap strip length" are hidden in
  "Prioritise chart area" (they don't apply there); Mode (ColorMunki Density /
  i1 clip / SpectroScan shape) and the Clip-border toggle moved into the Layout
  frame for better grouping.
- Tooltip/help clarifications: ColorMunki Density notes it's greyed in area-first;
  the Default Patch Sizes help describes the natural-size basis (and no longer
  implies a hard "stretch cap"); the generator's per-set ⓘ icons align.

## v3.13.0-beta.29

### 🔧 Changed
- **Applying an edited patch set now keeps your Create Chart layout.** The editor
  hands back only the patch set; Create Chart re-lays it out with the
  instrument / paper / margins / patch size set there (the patch set is fixed,
  the layout stays fully editable). This also fixes the case where an applied set
  wasn't randomised — "Randomise patch order" now takes effect.

### 🐛 Fixed / wording
- Patch-set editor help + the Apply/Save dialog now say "patch set" (not "chart
  layout"); the Inter-patch gap and Strip-indicator gap tooltips describe what
  they actually do; the Default Patch Sizes help explains the natural-size basis
  with example sizes.

## v3.13.0-beta.28

### 🐛 Fixed
- **The “last page not full” hint no longer pops up in Guided mode** (or in Manual
  with Auto patch count), where the count is filled to the page automatically and
  there's no patch-set to edit. It now appears only in Manual with a fixed patch
  count, and its wording is friendlier — it explains you can add a few patches or
  remove a few, and that the page layout stays as you set it.

## v3.13.0-beta.27

### 🐛 Fixed
- **Engine chart generation crashed in beta.26** (`build_chart() got an
  unexpected keyword argument 'area_default_w'`). The Default-Patch-Sizes value
  threaded into the build is now accepted by the engine. Regression test added.

## v3.13.0-beta.26

### ➕ Added
- **Settings → Default Patch Sizes** — an editable table of the patch
  width/height the area-first “auto” column/row count aims for, per instrument,
  paper and orientation (with a help ⓘ), so auto patches come out a sensible,
  readable size for the instrument.
- **Strip-length limit** in Settings → **Instrument Limits** — a configurable
  per-combo maximum strip length; the Create Chart preview warns when a strip is
  longer (0 = use the instrument's built-in ruler).
- A **“last page not full” hint** after generating: when the patch set leaves a
  notably under-filled last page (or a near-empty extra page), a message offers an
  **“Edit patch set…”** button that opens the patch-set editor — it never auto-
  fills or trims for you.

### 🔧 Changed
- The **“Instrument Margins”** settings tab is renamed **“Instrument Limits”** (it
  now holds both the margin minimums and the strip-length limit).

## v3.13.0-beta.25

### 🔧 Changed
- **The New Patch Set window is now generator-only.** The whole layout ("Chart")
  frame — instrument, paper, clip border, density — and the printtarg “Layout
  options” are gone; layout is set in the Create Chart tab. The window builds the
  patch set only (seed from targen, blank, paste/load, Generate colour sets), and
  the “fill to pages” option is replaced by “fill to N patches”.

## v3.13.0-beta.24

The chart editor is now fully a **patch-set editor** (Knut's review).

### 🔧 Changed
- **All layout editing removed from the editor.** The printtarg/engine layout
  panels are gone — layout is done in Create Chart, and a chart keeps the layout
  it was opened with. The dead controls went too: Update preview, Shuffle (the
  Create Chart Manual tab handles randomisation), “Highlight selected in preview”,
  and the Patches/Spacers mode radios.
- **Consistent “patch set” wording.** Masthead “Chart Patch Set · Editor”, Load /
  New **patch set** buttons and dialog, and rewritten help.
- **Editor layout tidied.** The swatch-size slider, the Show-patch-number /
  Show-gap toggles and the ⓘ moved to the top of the right column (ⓘ in the
  corner); the action buttons now line up with the bottom of the swatch grid;
  Apply / Save + Close share the column width; and the right column sits the same
  small distance from the window edge as the swatch on the left.

## v3.13.0-beta.23

Big engine + editor rework from Knut's feedback.

### 🐛 Fixed
- **Area-first now fills the whole patch area.** “Prioritise chart area” sizes the
  patches to fill the margin box instead of leaving a large empty band at the
  bottom; the minimum patch width / height-% are true minimums that grow to fill.
  By-columns/rows with a dimension on “auto” fills at a sensible patch size too.
- **Strip labels never sit behind the patches.** When the top margin is too small
  the labels slide toward the page edge (and a warning shows) instead of being
  covered by the first patch row.
- **Correct preview measurements.** The “Measured from Preview” numbers (margins,
  patch width, strip length) now come from the engine’s exact geometry, fixing the
  wrong patch width and the corruption when a strip gap was added.

### 🔧 Changed
- **“Margins are the law” is tied to area-first**, not “Use instrument margins”.
  The margin box is always authoritative; going below an instrument minimum is
  allowed and only flagged as a warning (no silent clamping).
- **The layout-engine on/off switch moved to the Create Chart tab**, above the
  layout panel; the old printtarg i1Pro options moved to the Chart Layout settings
  tab (greyed when the engine is on). Paper & Pages now sit under Instrument.
- **Loading a Manual preset selects the engine it was made with** (printtarg
  presets load with the printtarg engine).
- **The chart editor is now a patch-set editor.** The middle layout preview and
  all layout controls are gone — layout is done in Create Chart — so the swatch
  grid fills the window, with Show-patch-number / Show-gap toggles and a smaller
  minimum swatch size. Renamed throughout to “patch set”.

### ➕ Added
- **“Patches (this page)”** readout, and a warning when a strip is longer than the
  instrument’s ruler.

## v3.13.0-beta.22

### 🐛 Fixed
- **Layout engine and ChromIQ-style clip border no longer conflict.** With both
  enabled the engine silently fell back to the old printtarg path (so the Manual
  tab never showed the layout panel and the engine looked dead — mostly on
  Windows). The two settings are now mutually exclusive: turning the engine on
  disables and remembers the clip border, turning it off restores it, and an
  existing both-on configuration self-heals the next time Settings is opened.

## v3.13.0-beta.21

### 🔧 Changed
- **ColorMunki “Extra-high density” is now a native ColorMunki layout** — no more
  borrowing the i1Pro geometry. The engine makes the small, dense ColorMunki
  patches directly, so the chart is a real ColorMunki target end to end. Its
  patch size is fixed (a defined maximum-density mode), so Manual and Guided fill
  to the **same** patch count.
- **Manual Extra-high defaults now match Guided exactly** (5 mm margins, clip
  border off, centred patch block) — including the strip-label-to-patch spacing.
- **ColorMunki never caps the strip length** (it has no i1-style ruler), so
  Manual no longer drops patches versus Guided.
- **Clip border / notes band**: clip-border content (i1Pro / i1Pro 3 / ColorMunki
  / SpectroScan) and the per-instrument clip toggles now behave consistently — the
  clip-border content defaults to the notes box, and the ColorMunki/SpectroScan
  notes band defaults **off**.

### 🐛 Fixed
- Turning the clip border **off** now restores the page margin instead of leaving
  it stuck at the clip-border width (it no longer looks permanently reserved, and
  ColorMunki/SpectroScan no longer showed a double border).
- The Chart-Layout paper selector no longer defaults to **A2** — it falls back to
  **A4** when the previous paper isn’t available, so the page size stops “jumping
  back to A2”.

## v3.13.0-beta.20

### 🔧 Changed
- **ColorMunki “Extra-high density” now uses the proven i1Pro strip layout.**
  This is the mode that replaces the old triple-density trick. The engine builds
  the dense strip layout (clip border suppressed, strip-length cap lifted) and
  tags the chart as a ColorMunki directly — no more generating an i1Pro chart
  and rewriting the measurement file afterwards. The clip-border / strip-cap
  toggles and your patch scale / margin still apply. Density stays inert in
  area-first mode (the area fields define that grid).

## v3.13.0-beta.19

### 🔧 Changed
- **Guided mode no longer clamps to the margin thresholds.** For some
  instrument/paper combos (notably i1Pro · A4 portrait) the jig thresholds
  dominated the layout, so **Suppress left clip border** and **Don't limit strip
  length** changed the chart but not the patch count. Guided now behaves like
  before the threshold feature — those toggles affect the count again, and the
  layout matches printtarg's default reserves. The custom Margin-Thresholds
  safety still applies in Manual mode with **Use instrument margins** on.

## v3.13.0-beta.18

### 🔧 Changed
- **"Margins are the law" is now opt-in.** Knut's exact-margin behaviour (patch
  area = the margin box, no hidden instrument leader/trailer, strip labels at the
  page edge) applies only when **Use instrument margins** is on. With it off the
  engine uses the original printtarg-style layout, so the default matches
  printtarg again.
- **Use instrument margins**: the ⓘ aligns with the other tooltips, and
  unticking it **restores the margins you had** before ticking.
- Below the preview, a warning now appears if a margin is too small for its
  strip-label / sheet-text band (law mode).

### ✨ New
- **Clip-border image: rotate / scale / move.** The imported clip image can be
  rotated, scaled (1–50000 % of the fit-to-band size) and moved (X/Y in mm), with
  a live preview that stays smooth on big images (full resolution is used at
  generation).
- The **Browse** buttons (printer calibration and clip image) now use ChromIQ's
  own file dialog — sidebar shortcuts, and an image thumbnail preview.
- The **clip "ChromIQ branding"** extra text uses your chosen font.

### 🔧 Fixed
- **ColorMunki Density** is disabled in area-first layouts (the area fields define
  the grid there).

## v3.13.0-beta.17

More of Knut's decisions implemented.

### 🔧 Changed
- **The page margins are now the law.** The patch area is exactly the margin box
  you set — the engine no longer adds a hidden instrument leader/trailer or a
  label/text reserve on top, so charts pack more patches than before (and more
  than ArgyllCMS printtarg would). If a margin is too small for your jig, the
  instrument-margin warning still flags it. Strip labels, sheet text and the
  clip notes live **inside** the margins.
- **Strip labels sit at the page edge** (4 mm by default), not floating above
  the patches.

### ✨ New
- **"Text distance from edge"** is now three independent values — **Top** (strip
  labels), **Bottom** (sheet text) and **Clip** (notes band) — each 4 mm by
  default, in the Sheet text section.
- The **ChromIQ branding** clip content's extra text uses your chosen font.
- **ColorMunki Density** is disabled in area-first layouts (the area fields define
  the grid there).

## v3.13.0-beta.16

### 🔧 Fixed
- **Patch size in the Chart-layout panel** now shows 2 decimals, and the
  estimate-vs-on-screen highlight no longer flags a sub-pixel (≤0.15 mm)
  difference between the exact target size and the pixel-snapped rendered size —
  so a derived size like 7.34 mm reads honestly instead of looking like a 7.3 vs
  7.4 mismatch.

## v3.13.0-beta.15

### 🔧 Fixed
- **Chart-layout “estimate” now tracks the patch size again.** With *Auto patch
  count* on, changing the minimum patch width (or other sizing) updates the
  estimated total/rows/columns/pages instead of sticking on the last generated
  chart’s count. (The generated chart was already correct.)

## v3.13.0-beta.14

Big batch of layout-engine fixes from Knut's beta-13 testing.

### 🔧 Changed / fixed
- **Loading a preset then enabling the engine now carries Instrument and Paper
  across** to the ChromIQ layout panel, so the margins, the “Use instrument
  margins” lookup and Preferences all use the combo you actually selected.
- **Your margin boxes are authoritative again** — the engine no longer silently
  raises them to the instrument minimums on every generate. The minimums apply
  only when “Use instrument margins” is ticked.
- **The clip border now sits *inside* the page margin** instead of being added on
  top: turning it on copies the clip width into the margin box (editable), and
  the patches start at that margin.
- **Area-first “by columns/rows” fills the page** — with rows on auto the patches
  grow down so the last row reaches the bottom margin.
- The **layout-info “estimate”** column now lays out the on-screen chart’s real
  patch count under your current settings (correct pages/total).
- **“Text distance from edge”** is now an adjustable setting (Sheet text).
- The engine’s **instrument names match the printtarg list** (i1Pro / i1Pro 2 /
  i1Pro 3, ColorMunki / i1Studio / ColorChecker Studio, …).

### ✨ New
- **SpectroScan** now renders real interlocking **hexagons** (and the left column
  isn’t clipped), and labels the grid 2-D: **column letters + row numbers**.
- **ColorMunki “offset every second strip”** — printtarg’s measuring-rig brick
  layout, as its own option (independent of density).
- **ColorMunki / SpectroScan clip-border On/Off** selector, matching the i1Pro.
- The editor’s **“Pages”** spin fills the new page from the patch generator, now
  with the same guaranteed minimum patch spacing as the generator.
- The engine can emit an ArgyllCMS **`.cht`** recognition file (opt-in).

### ⚠️ Known / pending
- A few vertical-margin details (patch-area top exactly at the margin, strip
  labels 4 mm above the patches) depend on a pending decision about overriding
  the instrument’s physical run-off; unchanged for now.
- ColorMunki extra-high (triple) density still under-counts with the engine.

## v3.13.0-beta.13

Final round of layout-engine refinements from testing.

### ✨ New
- **“Use instrument margins” checkbox.** Tick it and the four page margins fill
  from your instrument’s margin thresholds and lock — so the patch area always
  clears the jig — and re-fill when you change instrument or paper.

### 🔧 Changed
- **New charts align the patch block to the top-left by default** (was
  centre-left). Existing presets and saved defaults keep their own setting.
- **Sheet text now sits 4 mm from the paper edge** (was 1.5 mm), so it can’t be
  clipped by the printer’s unprintable border.

## v3.13.0-beta.12

More layout-engine refinements from testing.

### ✨ New
- **Area-first “minimum patch size” mode.** Set the smallest patch your
  instrument can read, leave Strips/Rows on “auto”, and ChromIQ fits the most
  patches at that size and grows them to fill the area — the densest readable
  chart with no counting (a Patch shape ratio controls how they grow). Pin
  columns/rows instead when you want exact control.
- Area-first now shows **only the fields that choice needs** (the patch size /
  scale and patch-area-alignment rows are hidden when not used); margins and
  clip-border width stay, since they define the area.

### 🔧 Changed
- **Clip-border content (Notes box) is now the same size in Guided and Manual.**
  It uses the full clip strip from a small fixed inset, so a larger page margin
  no longer shrinks the notes text.
- **Guided mode** now fills a kept i1Pro/i1Pro 3+ clip border with the Notes box
  and brackets each strip with edge spacers (i1Pro / i1Pro 3+ / ColorMunki).

### ⚠️ Known issue
- **ColorMunki “extra-high (triple) density” with the new layout engine is
  wrong** — it currently produces *fewer* patches than double density. Use
  double density (or printtarg) for ColorMunki extra-high charts until this is
  fixed.

## v3.13.0-beta.11

Follow-up tweaks to the layout engine from testing.

### ✨ New
- **Chart layout information now shows patch size** (width × height), and the
  panel has separate **on screen** / **estimate** columns with steady, aligned
  widths so the numbers no longer shuffle as values change.

### 🔧 Changed
- **“Prioritise chart area” is now the default layout mode.** With columns/rows
  left on “auto” it fills the page just like before, so default charts are
  unchanged — but the area fields are right there when you want to pin a grid.
- The Chart layout estimate now refreshes immediately when you switch between
  Guided and Manual.

## v3.13.0-beta.10

A big round of layout-engine improvements from Knut's testing feedback.

### ✨ New
- **Two ways to lay out a chart.** A new **Create layout** choice in the engine's
  Layout section: **Prioritise patch size** (the old behaviour — you set the
  patch size and it fits as many as it can) or **Prioritise chart area** — you
  say how many strips (columns) and/or patches per strip (rows) you want and
  ChromIQ sizes the patches so the grid fills the usable area, so the patches
  reach the margins evenly. Only the fields each choice needs are shown.
- **Patch area alignment.** Place the whole patch block where you want it within
  the page — top-left, centre, bottom-right, and the rest.
- **Redesigned clip-border “Notes box”, now the default.** The left strip now
  prints a tidy record: chart facts filled in automatically (patches,
  instrument, paper, page, profile name, date) plus labelled lines to hand-write
  the printer, ink set, paper and media settings. It scales with the clip width
  and gives more writing room on larger sheets.
- **Chart layout information panel** next to “Measured from Preview”: total
  patches, patches per strip, strips and pages — with separate **on screen** and
  **estimate** columns, so after loading a chart and changing a setting you can
  see both what's printed and what re-generating would produce (changed values
  turn amber). The estimate shows even before you create the chart.

### 🔧 Changed
- **The layout engine now honours your margin thresholds.** If a chart would land
  inside the minimum margin you set (Preferences → Margin Thresholds), the engine
  widens that margin automatically — so i1Pro charts meet the run-up the ruler
  needs out of the box.
- The **Chart Layout** preferences tab now opens on the instrument/paper you're
  working with in Create Chart (so a saved preset is visible, not seemingly lost).

### 🐛 Fixed
- Removed a 1-pixel paper gap that could appear between a patch and its spacer.
- The Create Chart info box now reflects the engine's real settings (clip border,
  custom patch size, per-edge margins, paper orientation).

**Note for testers:** if you saved engine **defaults** before this build, your
saved clip-content and alignment values stay as they were until you re-save —
new charts pick up the new defaults (e.g. the Notes box).

## v3.13.0-beta.9

Fixes two layout-engine issues found in testing.

### 🐛 Fixed
- **Create Chart → Manual info box now shows the engine's real settings.** When
  the layout engine is on, the summary read from the old printtarg controls
  instead of the engine, so it could show the clip border as "off" when it was
  on, `patch ×0.95` even with a custom patch width/height set, and a single
  `margin 10 mm` when the four edges differed. It now reads straight from the
  active layout, shows per-edge margins and the custom patch size, and prints
  the paper **with its orientation** (e.g. `A4 landscape`) — in both the engine
  line and the "Layout preset:" line.
- **Removed a 1-pixel paper gap between a patch and its spacer.** At certain
  patch scales (e.g. ×0.95 at 300 dpi) a thin white line could appear between a
  patch and the colour spacer below it on every other row. Rows are now tiled
  seamlessly.

## v3.13.0-beta.8

Simplifies colour loading based on testing: reflective scan-target (CIE) files
and the experimental "stretch to fill the cube" option are removed.

### 🔧 Changed
- **Loading colours now accepts device-RGB files only** — Argyll `.ti1` / `.ti2`
  / `.ti3` / CGATS and plain hex/RGB lists, in New chart, Add and the editor's
  Load chart. **CIE reference files (XYZ/LAB) are no longer read**: a reflective
  scan target's colours can't be turned into a full-range chart layout in a
  meaningful way, so the **"Stretch colours to fill the RGB cube" option is
  gone** too. A CIE file now shows a clear "not supported" message.
  - **Want colours that span the whole RGB cube?** Use **Generate colour sets →
    3D cube / Saturated edges** — those place patches at the cube's faces and
    corners by construction, which is exactly what stretching a scan target
    could never do.
- **Removed the editor's "Append from file…" button** — it duplicated **Add →
  Load colours from a file**. ("Load Chart" is unchanged.)

## v3.13.0-beta.7

Layout-engine flexibility & fixes from testing — more paper sizes, friendlier
on-sheet text, tidier strip labels, and two persistence/preview bug fixes.

### ✨ New / changed
- **Portrait A2 / A3 / A3+** are now offered by the layout engine on the strip
  readers (i1 / i1Pro3+) — the engine packs them itself, so it isn't bound by
  printtarg's landscape-only capacity preference.
- **The page-label column is gone and its ~5 mm reclaimed for patches** (i1/A4
  now fits 462 vs printtarg's 441). The page number lives in the on-sheet text
  instead, via a new **`{page}`** placeholder ("page 1/3").
- **On-sheet placeholders now read in plain language:** `{instrument}` → "i1Pro3+",
  `{paper}` → "A4 landscape", `{patchcount}` → "576 patches", `{seed}` → "seed
  1234", `{dpi}` → "300 dpi", `{project}` → the printer-profile name. The Insert
  menu, tooltip and live preview all match.
- **Strip labels now sit flush under the top margin** (the band is still sized to
  the real label — font, size, rotation, multi-letter). New **Label offset** lets
  you nudge them; new **Strip gap** widens the space between strips.

### 🐛 Fixed
- **"Save as Defaults" now keeps every ChromIQ-engine option** (paper, margins,
  indicators, strip gap, label offset, …). They were being reset on restart.
- **Adding patches to an empty chart in the editor now shows a preview** built
  from the current engine settings (the right pane stayed blank before).

### 📝 Notes
- Non-German engine strings remain English placeholders pending translation
  before 3.13.0 final.

## v3.13.0-beta.6

Refines the "stretch to fill the cube" option from Knut's testing — it now lives
only where it belongs (New chart / Add), and the 3D cube shows it immediately.

### ✨ Changed
- **The "Stretch colours to fill the RGB cube" option is now only in the New
  chart and Add windows**, as a non-destructive checkbox — turn it on/off and
  the 3D cube updates live; nothing is committed until you press Create / Add.
  The button that was in the Edit Chart window has been **removed**.
- **Edit Chart → Load chart no longer opens CIE reference files.** Load those in
  New chart or Add, where the fill-the-cube toggle lives. Device-RGB charts
  (`.ti1` / `.ti2` / `.ti3` / CGATS) still load in the editor as before.
- **The live 3D cube now opens automatically when you load colours from a
  file**, so the distribution — and the effect of the stretch toggle — is
  visible right away instead of hidden behind the (collapsed) preview.

### 📝 Notes
- This follows from studying Argyll's `scanin`: a `.cie` reference holds only
  colorimetry (XYZ/LAB) — the device RGB in scanner profiling comes from the
  *scanned image*, never computed from CIE. Faithful loading shows a reflective
  target's real (gamut-limited) shape; the stretch is a deliberate layout-reuse
  transform. See the discussion in #96.
- Open follow-ups before 3.13.0 final are unchanged: translations of the new
  strings, real-hardware print+measure verification, multi-strip instruments,
  and the planned scanner-target workflow (#95 / #97 / #98).
- Thanks again to **Knut Georg Larsson**.

## v3.13.0-beta.5

Refines how reference-colour files load (from Knut's testing), with a new
fill-the-cube option for reusing them as chart layouts.

### ✨ New / changed
- **Loaded reference colours are now faithful by default.** CIE files describe
  real reflective targets, so their colours are reconstructed colorimetrically
  (matching Argyll rectarg's "display" intent exactly) — the 3D cube shows the
  target's real, gamut-limited shape and the white sits at its true value. (This
  replaces beta-4's media-relative stretch, which forced the white to screen
  white.)
- **"Stretch colours to fill the RGB cube"** — an optional, non-colorimetric
  per-channel stretch for when you want to *reuse* a reference chart's colours as
  a fresh full-range layout:
  - in the **Edit / create chart layout** editor, a button next to Darken /
    Lighten (undoable, so you can compare faithful vs stretched in the 3D
    distribution),
  - and as a checkbox in the **New chart "Load from file…"** and **Add "Load
    colours from a file"** windows, which live-updates the 3D cube.
  Each has a tooltip noting it changes the colours (no longer colour-accurate).

### 📝 Notes
- Open follow-ups before 3.13.0 final are unchanged: translations of the new
  strings, real-hardware print+measure verification, multi-strip instruments,
  and the planned scanner-target workflow (#95 / #97 / #98).
- Thanks to **Knut Georg Larsson** for the detailed testing and the sample files.

## v3.13.0-beta.4

Fixes and polish for the colour-file loading added in beta-3, from Knut's
testing with real scanner-target files.

### 🐛 Fixed
- **Loaded reference colours are no longer dim / squeezed.** CIE files describe
  reflective targets whose media white sits well below a perfect white (e.g.
  Hutchcolor ≈ 77%), so rendering them *absolutely* made everything look dark
  and the 3D cube collapse toward a gamut shape. Loading is now **media-relative**
  by default — the target's white maps to display white, so the colours fill the
  cube and read naturally.
- **The live 3D cube now reflects pasted / loaded / single colours**, not only
  the generated sets. (Seed-from-targen is still previewed only after generating.)
- **"Blank canvas" clears the preview** (and *Update preview* now works on an
  empty chart) instead of leaving the previous chart's image behind.
- **The New chart / Add window no longer slips behind the editor** after the
  file dialog closes.
- **Colours loaded into the Add window are de-duplicated** (near-identical ones
  spaced apart) so they don't run together and hurt readability.

### ✨ New / changed
- **Custom spacer colours** gained **white and black** swatches (5 accents → 7),
  giving the engine a strong high-contrast separator against very light or very
  dark patches.
- The spacer-colour pickers now use ChromIQ's own colour dialog (hex + RGB/HSV),
  matching the rest of the app, instead of the OS colour panel.
- Dark-mode standard tabs (Settings) now match the roomier light-mode tabs.

### 📝 Notes
- Open follow-ups before 3.13.0 final are unchanged from beta-3: translations of
  the new strings, real-hardware print+measure verification, multi-strip
  instruments, and the planned scanner-target workflow (#95 / #97 / #98).
- Thanks again to **Knut Georg Larsson** for the detailed testing and sample
  files.

## v3.13.0-beta.3

A small follow-up beta: **load existing colour sets from files** (the first step
toward the scanner-target workflow Knut proposed), plus polish and a correctness
guarantee for the layout engine.

### ✨ New
- **Load colours from a file** — CIE reference files (`.cie` / `.txt` carrying
  XYZ and/or LAB, e.g. SpyderChecker, QPcard, Wolf Faust IT8, Hutchcolor,
  LaserSoft) as well as Argyll `.ti1` / `.ti2` / `.ti3` / `.cgats` and plain
  hex/RGB lists. CIE files (no device values) are reconstructed to approximate
  device sRGB so they can be laid out and analysed in the 3D cube. Available in:
  - the **Edit / create chart layout** editor's **Load chart** button,
  - the **New chart** window's "Load from file…",
  - the **Add** window (new "Load colours from a file" option — previously you
    had to create a whole new chart to add colours from a file).

### 🎨 Polish
- Dark-mode standard tabs (the Settings dialog) now match the roomier light-mode
  tabs, so the two themes are consistent.

### 🔒 Reliability
- Added an end-to-end test that a generated chart's **saved TIFF carries the
  exact device colour the `.ti2` records at every patch location** — i.e. what
  gets printed is what `chartread` expects (verified across a randomised chart).
- CI: the x86_64 DMG step now retries `hdiutil convert` (it flaked on beta-2).

### 📝 Notes / still to do before 3.13.0 final
- The engine is **beta** and **off by default**.
- **Translations:** the new Chart-Layout / engine / file-loading strings are
  English placeholders in the non-German catalogs — to be translated before final.
- **Hardware verification:** print + measure on real i1Pro / i1Pro 3 /
  ColorMunki / SpectroScan hardware — the gate to GA.
- **CIE colour reconstruction is approximate** (D50→D65→sRGB, gamut-clamped) —
  fine for layout/analysis, not a colour-managed proof; D65-referenced files
  (e.g. SpyderChecker) shift slightly.
- **Multi-strip instruments (DTP41/51):** denser multi-strip layout not done yet.
- **Scanner workflow (planned, #97 / #98):** generate `.cht` + `.cie` from a
  `.ti3`, then drive ArgyllCMS `scanin` + `colprof` for a full scanner→printer
  roundtrip. `.ti1/.ti2/.ti3/.cie` loading (this release, #96) is the first step.
- Deferred: DeviceN/Separation PDF output for wide-gamut / CMYK+N.

Thanks again to **Knut Georg Larsson** for the detailed feature designs (#96–#98)
and the example target files.

## v3.13.0-beta.2

The second **ChromIQ layout engine** beta. It delivers the big beta-1 "coming
next" item — full layout-engine support in the **Edit / create chart layout**
editor — plus much smarter capacity handling and a round of polish. Still
**opt-in** (Settings → Chart Layout) and off by default.

### ✨ New
- **Engine in the chart editor.** Opening an engine chart shows every setting it
  was made with, updates the preview live as you edit, and carries your changes
  back to Create Chart. The **New chart** and **Add** windows respect the engine
  too: the printtarg knobs are replaced by the engine's, with a Chart section for
  the layout choices that change capacity (clip border on/off, *Don't cap strip
  length*, ColorMunki density) and a live **"≈ N fit one page"** hint.
- **Select patches in the preview.** Click or drag a marquee over the preview to
  select patches (Shift to add, Alt to remove) — the same as printtarg charts.
- **Multi-page navigation** (Page ◀ ▶) for engine charts in the editor preview.
- **Seeded Shuffle.** Editor charts start un-randomised; **Shuffle** reuses the
  same patches and randomises with a fresh, recorded seed.
- **Rotated-label alignment.** For 90° / 270° strip indicators, choose Left /
  Centered / Right; *Left* (default) keeps the first letter on a fixed line so a
  two-letter label grows away from the patches instead of creeping toward them.
- **Optional edge spacers** — bracket each strip with a leading + trailing
  spacer like printtarg (off by default).

### 🎯 Smarter packing (capacity now matches what's drawn)
- The patches-per-page count now accounts for **everything that uses space**:
  clip-border width, the strip-indicator gap, the real strip-label band
  (indicator size / font / rotation), the underline, the bottom sheet text and
  the command stamp. Charts no longer silently overflow, and the count is right.
- **Reclaim space you're not using:** turning strip labels off, or choosing a
  small indicator font, frees that space for more patches. With edge spacers
  **off** (the default), the engine also reclaims the strip-end gaps printtarg
  leaves — packing **denser than printtarg**, most at larger spacer widths.
- The editor preview of a loaded chart now matches the printed chart exactly
  (it was showing a second, different randomisation).

### 🎨 Polish
- Scroll **fade gradients** now actually render on the editor's controls panel
  and the New chart / Add / Settings windows; the Settings tabs share one warm
  background (the General / Margin tabs were stark white in light mode).
- The checked Patches/Spacers selector is round again (was a magenta square).
- The Settings window opens taller; the branding "IQ" uses the real Instrument
  Serif italic; assorted editor layout/scroll fixes.

### 📝 Notes / still to do before 3.13.0 final
- The engine is **beta** and **off by default** — printtarg remains the default
  and fallback.
- **Translations:** the new Chart-Layout / engine strings are English
  placeholders in the non-German catalogs — they'll be translated before final.
- **Hardware verification:** print + measure on real i1Pro / i1Pro 3 /
  ColorMunki / SpectroScan hardware is still pending and is the gate to GA.
- **Multi-strip instruments (DTP41/51):** denser multi-strip layout isn't
  implemented yet.
- A future idea (deferred): emit charts as DeviceN/Separation PDF for
  wide-gamut / CMYK+N profiling.

## v3.13.0-beta.1

The first beta of the **ChromIQ layout engine** — an optional, built-in
replacement for ArgyllCMS printtarg that lays out your charts itself. It's
**off by default** (Settings → Chart Layout); printing and measuring existing
charts are unaffected, so it's safe to try and switch back at any time.

### ✨ New
- **ChromIQ layout engine (opt-in).** When enabled, ChromIQ builds the chart
  TIFF and `.ti2` itself for the i1Pro / i1Pro 3 / ColorMunki / SpectroScan,
  packing patches efficiently and putting useful content where printtarg leaves
  blank space. Full per-instrument × paper × mode defaults live in
  Settings → Chart Layout, and every option is mirrored in the Create Chart
  Manual module.
- **Per-chart layout control.** Patch size & scale, spacer colour/width/scale,
  inter-patch and strip-indicator gaps, independent page margins, resolution,
  max strip length, chart offset, strip/patch label patterns, 8/16-bit and
  compression — each with a friendly tooltip.
- **Strip indicators.** Choose the label font (bundled + every system font),
  size (auto-fit), bold/italic; an optional rule under the labels (one
  continuous 5-segment ChromIQ-accent bar, a per-strip accent cycle, or black)
  with adjustable thickness and distance.
- **Randomisation.** Randomise patch order (default), enter or generate a fixed
  seed for a reproducible layout, or turn randomisation off.
- **Sheet text.** Print custom text in the bottom margin with
  `{project}/{date}/{paper}/{instrument}/{patchcount}/{pages}/{seed}/{dpi}`
  placeholders (an "Insert ▾" menu and a live preview), plus an optional
  one-line layout-summary stamp.
- **Clip-border content editor (i1/p3).** Fill the reserved left clip strip with
  custom text, the ChromIQ branding wordmark, a hand-writing notes box, or an
  imported logo — with an adjustable clip width, a live rotated preview, and an
  "Export template (PNG + PDF)" at the exact clip size to design a graphic
  elsewhere.
- **Reproducible & self-documenting.** The randomisation seed is stored with the
  chart; the command stamp records `targen` + the engine (not a misleading
  printtarg line).
- **Saveable like printtarg.** Every engine option saves as a default and inside
  the Create Chart named presets, with the same workflow as the printtarg
  options.

### ⏭️ Coming next
- **Layout-engine support in the Edit / create chart layout editor:** opening an
  engine chart will show all its settings, update the preview live as you edit,
  and carry your changes back to Create Chart. Tracked in #93.

### 📝 Notes
- The engine is **beta** and **off by default** — printtarg remains the default
  and the fallback.
- Non-German UI translations for the new Chart-Layout strings are pending and
  will land before a final release.

## v3.12.1

### 🔧 Changed
- **A chart's layout is now kept consistent across its two records.** A chart
  carries its printtarg layout both as the Create Chart manual settings (Set A)
  and inside its creation recipe (Set B, used to reload the New chart / Add
  windows). These could drift — e.g. a triple-density preset whose recipe said
  one scale while its printtarg block said another. Now, whenever a chart is
  generated or saved as a preset, Set B's layout block (scale, margin, spacers,
  `-L`/`-P`, double/triple density, DPI, bit depth) is re-synced from the layout
  the chart was actually built with, so the two can't disagree. The generators,
  colour-set settings, source mode and patch count stay frozen as "what was used
  at creation". (#92)

## v3.12.1-beta.1

### 🔧 Changed
- **A chart's layout is now kept consistent across its two records.** A chart
  carries its printtarg layout both as the Create Chart manual settings (Set A)
  and inside its creation recipe (Set B, used to reload the New chart / Add
  windows). These could drift — e.g. a triple-density preset whose recipe said
  one scale while its printtarg block said another. Now, whenever a chart is
  generated or saved as a preset, Set B's layout block (scale, margin, spacers,
  `-L`/`-P`, double/triple density, DPI, bit depth) is re-synced from the layout
  the chart was actually built with, so the two can't disagree. The generators,
  colour-set settings, source mode and patch count stay frozen as "what was used
  at creation". (#92)

## v3.12.0

The **margin inspector** release: ChromIQ now measures every chart you generate
and warns you before you print one your measuring rig can't read.

### ✨ New
- **Margin inspector — "Measured from Preview" panel.** Under the Create Chart
  preview, a new panel reports the chart's *realised* page margins (Left / Right
  / Top / Bottom), the **patch width** across a strip, and the **strip length**,
  in millimetres and inches with a **min** column showing each edge's threshold
  beside the measured value. printtarg only gives you one overall margin, yet the
  real margins shift with patch scale, spacers, paper and orientation — so the
  only reliable way to know them is to measure the rendered page, which is what
  this does. It measures the page you're looking at and updates as you page
  through a multi-page chart, and gives a green **"Margins: OK"** or a clear
  warning naming the offending edge and threshold.
- **Editable margin thresholds per instrument & paper** (Preferences → Margin
  Thresholds). Set the minimum each edge needs for your ruler / jig, per
  instrument and paper size, with a description field for which rig a row is for.
  Default seeds ship for the **i1Pro**, **i1Pro 3+** and **ColorMunki** (editable
  starting points, not gospel), and a **"Restore default thresholds"** button
  pulls in updated built-in defaults without overwriting values you've saved.
- **Margin guide lines on the preview.** Two independent toggles: dotted lines at
  each *threshold* position (red on a violated edge) and long dotted lines at each
  *measured* margin (where the patches meet the paper), plus a drawn **page-edge
  marker** so the thin white frame can't be mistaken for margin. The guides track
  the page on screen and the thresholds you edit.
- **Guided settings carry over to Manual mode.** Switching from Guided to Manual
  after a build seeds the Manual panel with the same recipe — instrument, paper,
  pages, patch count (Auto), patch scale, margin, density, strip-limit, border and
  profile name — so you can fine-tune the exact settings that produced the chart.
  (#79)

### 🔧 Changed
- **Reworked the built-in "Full layout setup" presets** for both i1Pro and
  ColorMunki so they meet each instrument's jig margins and strip-length limits,
  with the patch width shown in every name. Retired the "A4-960p Landscape"
  preset and removed the older "TC9.18+Spyderprint Grays" built-ins; the Full
  layout setup family and the "by Pharmacist" targets remain. (#88, #89)

### 🐛 Fixed
- **Margin measurement and guide placement are now accurate on every chart and
  page**, including ColorMunki double-density (`-h`) zig-zag layouts where the
  outermost strip row is half-populated and the rotated strip-label column sits
  past a strip of bare paper — both used to throw the top/bottom and right
  margins off and drift the guides between pages. (#83, #91)
- **No false warning when a margin equals its threshold** (6.0 mm vs a 6 mm
  minimum); threshold fields accept one decimal place. (#85)
- **Strip length and patch width are correct on landscape charts** — printtarg
  always lays strips vertically, so strip length is page height − top − bottom and
  patch width is measured across the strips regardless of orientation. (#87)
- **No bogus "paper mismatch" warning** when printing a correctly-sized full-page
  chart (the check compared against the printable area, not the sheet). (#84)
- In the editor's **Add…** window, **"Ensure unique colours"** now keeps generated
  patches clear of the chart's existing patches too, not just of each other. (#89)

Thanks to **Knut** for the detailed design and relentless testing across the beta
series, and to the **Pharmacist** for the report that started it.

## v3.11.25

### ✨ New
- **A way out when a refinement chart takes too long.** With certain
  pre-conditioning profiles, Argyll's default patch-arrangement method can slow
  down dramatically on larger (multi-page) charts — the app looked frozen while
  it was actually still working. ChromIQ now watches for this and, if a chart
  build runs unusually long, offers a clear choice: keep waiting, **rebuild the
  same chart with a faster patch layout** (same profile and patch count — for a
  refinement chart the quality is effectively identical, and it finishes almost
  instantly), or cancel. You're asked again on every slow build. Big thanks to
  @Hackensacker for the detailed report and test files that made this possible.
- **Live chart-building progress.** Patch placement now shows a running
  percentage in the log, so it's obvious the build is working and not stuck.

## v3.11.24

### ✨ New
- **Updated "Full layout setup" built-in charts from Knut** (i1Pro + ColorMunki,
  A4 / A3 / A3+, 480 – 2016 patches, incl. *Nature Focus* and *General Plus
  Skintones* variants). Each one bundles its **complete** Create-Chart setup —
  the colour-set recipe *and* the page layout — so you can pick one as a basis,
  open it in New Chart, tweak it and build your own. This family replaces the
  earlier "Wide-gamut" presets (the old name didn't describe what they're for).

### 🐛 Fixed
- **Save-Preset name suggestion no longer shows a stale patch count.** After
  loading a built-in preset and then applying a chart from the layout editor,
  the suggested name kept the built-in's patch count (e.g. `1168p`) instead of
  the chart you actually applied (`1575p`). Thanks to the Pharmacist for the
  report.
- **The layout editor's saved recipe now matches the chart you built.** Editing
  the printtarg panel (patch scale, margin, …) after New Chart left the stored
  recipe on the old values, so reusing the preset as a basis regenerated the
  wrong layout (e.g. a patch scale you'd dialled back to fit the page).
- **Built-in presets that use a standard paper size now show it by name.**
  Several presets whose size is exactly A3, A2 or Tabloid (11×17) showed
  "Custom" with raw millimetres instead of the named paper size.

## v3.11.23

### ♻️ Changed
- **Neutral grey ramp is back to a maximum of 64 steps** (reverting the 256 cap
  from the previous release).

## v3.11.22

### 🐛 Fixed
- **Built-in presets now carry their settings into the New Chart window, with
  thanks to the Pharmacist.** Loading a built-in preset that ships a design
  (colour sets, instrument, paper, layout) now seeds New Chart from it — just
  like a locally-saved preset — instead of falling back to your last-used
  settings. The "Load setup from preset" list is now registry-driven, so any
  preset that carries settings shows up, not only the wide-gamut family.
- **Presets load the right settings.** A preset that was saved before a
  generator existed no longer comes up with it wrongly enabled (e.g. Flamingos);
  a set the preset didn't include now loads off. And a Saturated-edges setting
  saved under the old meaning is migrated so its "between" field reads 1 rather
  than an old number that over-generated patches. Existing presets are fixed on
  load — no need to re-create them.
- **Gamut-corner emphasis hugs the corner.** With "edge" at 1 the single patch
  now lands closest to the gamut corner (the tip-adjacent gap) instead of
  further out, and extra patches cluster toward the corner.

### ✨ New
- **Neutral grey ramp now goes up to 256 steps** (a full 8-bit ramp), up from
  64. Near-neutral greys keeps its 64 cap.

## v3.11.21

### ✨ New
- **Neutral greys split into two clean generators, with thanks to the
  Pharmacist.** The old combined "Near-neutral greys" is now two independent
  sets in Generate colour sets: **Neutral grey ramp** (the pure black-to-white
  greys, no tints) and **Near-neutral greys** (only the gentle off-neutral hue
  rings). You can now choose how many pure neutrals to lay down separately from
  the near-neutral tints — more flexible and clearer. The defaults reproduce the
  old set exactly, existing charts and presets migrate automatically, and the
  more fiddly "More greys in between" option is retired in favour of this.

### ♻️ Changed
- **"Colour extremes" now sits just above "Highlights & shadows"** in the
  colour-set list — the chromatic-corner counterpart to the tonal-end set,
  grouped together.

## v3.11.20

### ✨ New
- **More greys in between, with thanks to the Pharmacist.** A new colour set in
  Generate colour sets, sitting right under **Near-neutral greys**: it drops
  extra grey steps **between** that set's steps, to make the all-important
  neutral ramp denser where it shows most. **Between** sets how many greys go in
  each gap (1 = the midpoints, 2 = two evenly spaced, …); leave **rings** at 0,
  the usual choice, for a plain, denser black-and-white ramp, or raise it to
  circle each with the same gentle tints as the set above. It rides on
  Near-neutral greys — it follows that set's step count and is only available
  while it is on — and, like every set, it saves and restores with the chart and
  is fully translated.

## v3.11.19

### ✨ New
- **Two new built-in charts, with thanks to the Pharmacist.** The Create Chart
  presets (both the ★ overlay and the Manual dropdown) gain a high-density
  1944-patch i1Pro target — *"extended target by Pharmacist"* — in A4 and
  US-Letter page sizes.

### 🐛 Fixed
- **Well-shuffled charts are now measured in both directions automatically.**
  When a chart is laid out in fixed order (the "Preserve Patch Order" option, or
  a layout designed in the TI2 editor) but its colours are in fact well mixed,
  ChromIQ now tags it as randomised on generation — so chartread can read its
  strips in either direction, exactly as it already does for charts saved from
  the layout editor. Structured charts (deliberate ramps, calibration targets)
  are left untouched.

## v3.11.18

### 🐛 Fixed
- **"Patches that clash" dialog: tidier button row.** The five choices are now
  centred under the explanation with a clear gap above them, and the long
  "Add new ones and fill the gaps" button no longer overlaps its neighbour.

## v3.11.17

### ✨ New
- **Adding patches that clash: clearer choices, and a new "fill the gaps" option.**
  When some of the colours you're adding land on (or right next to) ones already
  in the chart, the dialog now **spells out the count impact of each choice** —
  how many it adds, how many it drops — so you can see the total won't be what
  was first shown. It also has a new button, **"Add new ones and fill the gaps"**
  (between "Add only the new ones" and "Add anyway"): it drops the clashing
  patches and refills their slots with fresh, non-overlapping colours, so you
  still add the full count you asked for with nothing printed almost twice.

### 🐛 Fixed
- The overlap dialog's buttons no longer clip or overlap — they're sized for the
  app's monospace button font so every label fits.

### 💄 Improved
- **Corner spirals renamed "Colour extremes" and limited to the colour corners.**
  It now spirals into the six saturated colour corners (red, green, blue, cyan,
  magenta, yellow) only — white and black are left to Highlights & shadows, which
  already covers them, so the two no longer overlap.
- **Old charts and presets load the new corner sets off.** A recipe, preset or
  saved layout written before these generators existed now loads them switched
  off (rather than leaving whatever was last ticked), and the New-chart / Add
  total counts both new sets correctly.

## v3.11.15

### ✨ New
- **Two corner sets, split for clarity.** The corner work is now two generators:
  - **Gamut-corner emphasis** adds extra patches **on the gamut edge lines** right
    next to each corner tip (the TC9.18/TC9.24 trick), slotted into the gaps so
    they never land on the patches the 3D cube or Saturated edges already place
    there. One control: **edge** (how many per edge near each corner).
  - **Corner spirals** adds detail **just inside** each corner in a Highlights-&-
    shadows-style spiral cone (H&S generalised from white/black to all eight
    corners). Controls: **per end** + **reach**.
  - The exact corner tips have a single source — 3D cube → Saturated edges →
    Gamut-corner emphasis → Corner spirals — so a tip is never missing and never
    duplicated, whichever sets are on.

## v3.11.14

### 🐛 Fixed
- **Saturated edges now keeps the corners when used without the 3D cube.** The
  v3.11.9 rework filled the edges *between* the cube's steps, which dropped the
  corner tips when the cube wasn't also on. Edges now restores the eight corner
  tips whenever the cube isn't there to supply them.

### 💄 Improved
- **Gamut-corner emphasis reworked into corner spirals.** The set now works like
  **Highlights & shadows**, but spiralling in from each of the eight corners
  instead of from white and black, so the densest patches sit right at the
  saturated tips. Its controls are now **per end** (patches per corner) and
  **depth** (how far in they reach), matching Highlights & shadows. It also
  supplies the exact corner tips itself when neither the 3D cube nor Saturated
  edges is on, so a tip is never missing — and never duplicated.

## v3.11.13

### ✨ New
- **New "Gamut-corner emphasis" colour set.** In the chart layout editor's
  **Generate colour sets** mode, a new set (third in the list, next to the 3D cube
  and Saturated edges) drops extra patches just inside the eight extreme corners
  of the printer's colour range — the deepest, most saturated colours, which are
  the hardest to reproduce and where profiles carry the most error. It's a quick
  way to tighten the profile right where it strays most. **Per corner** sets how
  many patches at each corner; **spread** how far in they reach. Off by default;
  its settings save and restore with every preset and chart like the other sets.

## v3.11.12

### 🐛 Fixed
- **Built-in wide-gamut chart presets rebuild to their intended size again.** The
  generator rework in v3.11.9–v3.11.10 (the new "between" saturated-edges control
  and the Flamingos set) changed how the eleven bundled wide-gamut presets read,
  so they were building ~1.5–1.9× too many patches and no longer fitting their
  named page layouts. Each preset's recipe is updated to the new edges control and
  pins Flamingos off, so all eleven once more build to exactly the patch count in
  their name (e.g. "480p" → 480 patches). Thanks, Knut, for catching this.

## v3.11.11

### 💄 Improved
- **Adding patches now warns when colours would *crowd* your chart, not just when
  they're exact duplicates.** When you Add generated patches and some land right
  next to colours already in the chart (close enough to measure almost the same),
  you now get the same "make them unique / add only the new ones / add anyway"
  choice you previously only got for exact repeats. **Make them unique** keeps the
  full count and gently spaces each crowded patch a small gap clear of the
  existing ones; **Add only the new ones** drops the ones that would crowd. The
  wording was refreshed to match. (Builds on the v3.11.10 minimum-distance work —
  thanks again, Knut.)

### 🌍 Translations
- Updated the reworded dialog across all twelve languages.

## v3.11.10

More **Generate colour sets** polish from Knut's testing (thank you, Knut!).

### 💄 Improved
- **Clearer, standardised colour-set names.** The four hue-band sets now share one
  evocative style: **Oceans (blues)**, **Foliage (greens)**, **Sunrises (warm)**
  and **Flamingos (pinks)**.
- **Saturated edges moved directly under the 3D cube**, since the two work as a
  pair (the edges/faces fill is keyed to the cube's grid).
- **Saturated edges – faces: even fill, no more cross gap.** The faces option used
  to drop patches only *inside* each cube square, leaving empty cross-shaped
  channels along the grid lines between them. It now fills the whole face as one
  even lattice (the lines between the cube dots included), so cube + edges + faces
  read as a single uniform grid at any density.
- **"Ensure unique colours" now keeps a real minimum distance.** Previously it only
  guaranteed patches landed on separate cells, which could still leave two patches
  almost touching. It now genuinely spaces every patch at least a small distance
  from the ones already placed, working through the sets top-to-bottom (each set
  spaced against the ones above it), so generated patches no longer crowd the 3D
  cube's dots or each other.

### 🌍 Translations
- Updated the renamed sets and affected help across all twelve languages.

## v3.11.9

Improvements to the chart layout editor's **Generate colour sets** mode, all
from Knut's testing (thank you, Knut!).

### ✨ New
- **Flamingos (pinks) colour set.** A new hue-band generator covering the pinks,
  magentas and indigos between where *Blues / turquoise* ends and *Sunrises*
  begins — the big gap that was left in the middle of colour space when the other
  bands were all on. Works just like the other bands (per layer × layers), and is
  on by default. Great for flowers, fabrics, sunsets and skin.

### 💄 Improved
- **Saturated edges now stay even at any density.** The control changed from a
  raw patch count to **between** — how many patches to drop *evenly between each
  pair of neighbouring 3D-cube dots* — along the 12 cube edges, with **faces**
  doing the same inside each square of the cube's faces. Because the spacing is
  tied to the cube, the boundary fill is evenly spaced at every setting, not just
  when it happened to match the cube (the lumpiness above one patch per gap is
  gone). 1 puts one patch midway between each cube dot.
- **The warm bands reach into the dark tones.** *Sunrises* (and the new
  *Flamingos*) now start near the dark corner like *Greens*, instead of at mid
  lightness — closing the bright opening that sat between the warm and cool sides
  around the black corner.
- **Ensure unique colours keeps a little more breathing room.** Combined sets now
  keep a small minimum distance between patches, so a generated patch that lands
  right next to a 3D-cube dot is nudged clear of it rather than printed almost on
  top of it.

### 🌍 Translations
- Updated the affected strings (new Flamingos set, edges controls, white/black
  note) in all twelve languages.

## v3.11.8

### 💄 Improved
- **Near-neutral greys generator: a true black-and-white wedge.** In the chart
  layout editor's **Generate colour sets** mode (behind *New chart…* and
  *Add…*), the **Near-neutral greys** set now lets you set **rings to 0** — a
  plain neutral grey ramp with no hue tints at all, exactly what you want for
  black-and-white work and linearization. The **rings** and **offset** controls
  swapped places (now *steps · rings · offset*), and **offset** greys out when
  rings is 0, since it has no effect there. The patch count stays correct (0
  rings = just the grey steps). Tooltips and the in-app help explain it.

### 🌍 Translations
- Updated the Near-neutral greys help and tooltip in all twelve languages.

## v3.11.7

### 🐛 Fixed
- **Inspect a measurement / Inspect a profile were unreadable in light mode** —
  the detail text used a near-white colour that vanished on the light
  background. Both tools now use the correct text colour for your theme.

### 🚀 New
- **Save a report.** Both inspector tools gained a **Save report…** button that
  writes everything shown to a plain-text file — handy for keeping a record or
  sharing it. It uses ChromIQ's own save dialog with shortcuts to the usual
  folders (Desktop, Documents…) plus the folder the inspected file lives in.

## v3.11.6

### 🚀 New
- **Measure a verification chart without risking your profile.** The Measure tab
  has a new **Profile verification** section (guided and manual): tick
  **"Verification measurement (colour-managed print)"** when you measure a chart
  you printed *through* a profile to check it. ChromIQ saves it as a separate
  `…-verify.ti3`, never offers to build a profile from it, and reminds you to
  open it in **Tools ▸ Inspect a measurement** — which now switches to Verify
  mode automatically for these files. The manual setting can be stored in a
  preset.

### 💄 Improved
- The verify-mode options in *Inspect a measurement* now have ⓘ info icons with
  full explanations, and the window is a little wider to fit them.

## v3.11.5

### 🚀 New
- **Inspect a measurement now verifies, not just inspects.** When you measure a
  chart you printed *through* a profile, switch the new **Verify** mode on (or
  just attach a profile/reference and it switches itself). The grey read-out
  becomes the colour cast left over **after** correction — measured relative to
  your paper white by default, so the paper's own tint isn't counted against the
  profile — and a new **Colour accuracy** section scores every patch as a colour
  difference (ΔE₀₀): the average, the worst patch, and a per-colour breakdown so
  you can see where the profile is weakest. Compare against the **profile**
  itself (a round-trip check) or a **reference** target. The original Inspect
  view is unchanged.

### 💄 Improved
- Long tooltips no longer jump to the edge of the screen — they now appear next
  to the mouse and wrap to a comfortable width.
- The "no file loaded yet" message is centred in the Inspect-a-profile and
  Inspect-a-measurement windows.

## v3.11.4

### 🐛 Fixed
- **Pure white & black patches are added again.** In the layout editor's *Add
  patches* window, the “Pure white & black” set with *each: 2* added nothing
  when the chart already held white and black — it now adds the requested
  anchors on top of the existing chart (they're deliberate repeats, e.g. for
  averaging paper-white reads), and the count/total reflect them (#76, thanks
  @soul-traveller).
- **No more duplicate label on the 3D cube.** When comparing two patch
  distributions, each cube already carries its own title, so the redundant
  “Current chart” label in the top bar is now hidden in compare mode and shown
  only for the single-cube view (#77, thanks @soul-traveller).

## v3.11.3

### 💄 Improved
- **Clearer wording: “chart” instead of “target.”** Following feedback from
  @soul-traveller, the printable patch sheet is now called a **chart**
  everywhere in the UI. The Print tab's load icon is **“Load test chart,”** the
  layout editor's load button is **“Load chart…,”** the step headers read
  **Generate / Print / Measure Chart**, and the calibration-chart controls and
  measure dialogs follow suit. (The word “target” is kept only where it means
  printcal's colorimetric aim values.) Updated across all twelve languages.

### 🐛 Fixed
- **Correct page count in generated names.** A fixed-layout preset that
  ArgyllCMS split across two sheets is no longer mis-named “1page” — the name now
  reflects the chart's real page count, even when the Pages control is locked
  (#73, thanks @soul-traveller).
- **Attach log files to bug reports.** The “Logs / error messages” field in the
  GitHub bug-report form now accepts drag-and-dropped files, so `chromiq.log` can
  go straight where it belongs (#74, thanks @soul-traveller).

## v3.11.2

### 🚀 New
- **See the contrast between paper white and max black.** *Tools ▸ Inspect a
  profile* now shows the paper white and the deepest black a profile can reach,
  plus the contrast expressed three ways — contrast **ratio**, **dynamic range**
  (optical density) and the **ΔL\*** lightness spread. It also now reports the
  profile's real paper white, where before this row showed the fixed D50
  reference rather than the paper itself.
- **New tool: Inspect a measurement (.ti3).** Open the raw per-patch readings
  behind a profile to see what your printer and paper actually did — the *true*
  measured contrast, how neutral your greys really are (the colour cast the
  profile then corrects), how far the gamut reaches, whether the read looks
  clean or a strip was misread, and, from the spectral data, how the paper
  behaves under other lighting (D50, D65, tungsten, fluorescent). Every value
  has a plain-language explanation on hover.

### 💄 Improved
- A handful of #70 review follow-ups (thanks **Knut (@soul-traveller)**): the
  reuse-a-name dialog is now worded around your **printer profile** instead of a
  "target"; folder/load icons render consistently across windows; long tooltips
  and help text wrap instead of being clipped; the 3D patch-distribution window
  has a clearer title; and a chart's remembered **recipe** (New-chart vs Add) is
  stored and restored correctly.

## v3.11.1

### 🐛 Fixed
- **Save preset suggests the chart-layout name, not the profile name.** The
  Save Preset window now pre-fills the descriptive **chart-layout** name
  (instrument-paper-patches-pages-orientation) — a preset names a layout, so the
  printer-profile name from the Output frame no longer leaks in. Its info text
  now suggests a *layout*-distinguishing detail (a variant, build or date)
  instead of a paper type. (#70, thanks **Knut (@soul-traveller)**)

## v3.11.0

### ✨ Changed
- **The Create Chart name is now a plain "Printer profile name".** It names this
  whole job — the working folder, every file generated along the way and the
  description embedded in the ICC itself — so what you see later in, for example,
  macOS ColorSync Utility matches the folder and files exactly. The descriptive
  prefix that used to lead this field has moved to where it belongs: **Save
  preset** and the layout editor's **Save As…** (chart-layout names). Choosing a
  preset, loading a chart or applying one from the editor **no longer overwrites
  a name you've typed**. (#70, thanks **Knut (@soul-traveller)**)
- **Rename a profile just by editing the name.** Change the name and ChromIQ
  offers to rename the folder and files to match, the moment you leave the field
  — no need to regenerate. Once a profile has been **built**, the name is fixed
  (it's baked into the ICC), so ChromIQ tells you to copy it to a new name and
  build a fresh profile there instead. (#70)
- **Layout editor: "Apply / Save…".** The old "Save & apply" / "Save As" pair is
  now one button that opens a small window: **Overwrite** the chart currently
  loaded in Create Chart with this layout (your profile name and measurements are
  kept), **Save As** to export the full chart to a folder you pick, or **Cancel**
  back to the editor. (#70, thanks **Knut (@soul-traveller)**)

### 🚀 New
- **Reopen a profile to continue another day.** A magenta folder button beside
  the built-in-presets star opens an existing project (its `project.json`) and
  loads its chart, measurements and any profile exactly where you left them.
  Saving stays automatic. (#70, thanks **Knut (@soul-traveller)**)

### 💄 Improved
- **Charts built from a preset / loaded patch set** now stamp `Chart layout
  <name> |` on the printable TIFF in place of the (never-run) `targen` line,
  keeping the `printtarg` command — so the sheet self-documents how it was made.
- The Create Chart and Check & refine step tooltips were reworded for the new
  flow and are now fully translated into all supported languages.

## v3.10.28

### 🐛 Fixed
- **"Add a descriptive prefix" off-state corrected.** Turning the option off now
  shows the generated descriptive name as a **plain, fully editable** field (no
  dash) that you can keep, edit, or replace — instead of clearing it. With the
  option on, the descriptive part stays greyed and locked with a trailing `-`
  and you type your text after it. (#68, thanks **Knut (@soul-traveller)**)

## v3.10.27

### 💄 Improved
- **Name fields now show a clearly locked descriptive prefix.** With "Add a
  descriptive prefix" on, the generated part is shown greyed and locked with its
  `-` always visible (cursor lands right after it, ready to type); turning the
  option off clears the generated part and leaves the field free for your own
  name. Applies consistently to Create Chart's **Save preset** and the layout
  editor's **Save as…** and **Save & apply** dialogs. (#68, thanks
  **Knut (@soul-traveller)**)
- **Special characters in paper names are made filesystem-safe in names.** A
  paper like A3+ now reads **A3Plus** and inch sizes read **8x10in / 5x7in** in
  generated names (the `+` and `"` are kept only in the selection lists, never in
  folder/file names). (#68, thanks **Knut (@soul-traveller)**)

### 🐛 Fixed
- Forward-Delete from inside a locked name prefix no longer nibbles the first
  editable character.

## v3.10.26

### 🐛 Fixed
- **Layout editor Save dialogs no longer double the suggested name.** A
  regression in v3.10.25: the editor's **Save as…** / **Save & apply** name
  fields pre-filled the descriptive name twice (e.g.
  `ColorMunki-A3+-…-ColorMunki-A3_-…`) because the suggested prefix and the
  filesystem-sanitised stored name differed by one character (`A3+` vs `A3_`).
  They now seed the clean suggested name. (#68, thanks **Knut (@soul-traveller)**)

## v3.10.25

### 🐛 Fixed
- **Edit Chart Layout: a triple-density chart's settings are now read back
  correctly.** Opening a TD preset chart (e.g. patch scale 1.04 / margin 6) in
  the layout editor showed the i1Pro-emulation defaults (1.30 / 5) instead of the
  chart's own values, and Save & apply then propagated those wrong values back to
  Create Chart. Loading a chart no longer clobbers its scale/margin. (#68, thanks
  **Knut (@soul-traveller)**)
- **Generated names no longer end with a stray dash.** When you leave the
  editable part blank, the field now shows just the descriptive part (e.g.
  `i1Pro-A4-484p-1page-Portrait`) with no trailing `-`; the separator appears the
  moment you type. (#68)
- **Suggested names use the paper's name, not its millimetres.** A named size
  like A3+ now reads `…-A3+-…` in the editor's suggested name instead of
  `…-483x329-…` (only a truly custom size shows W×H). (#68)
- **Hardened chart generation from a patch set** so a re-layout can't wipe its
  own input and silently produce no pages (a cause of "Chart generation
  failed"); the input is now preserved across the rebuild. (#68)

### 💄 Improved
- **Consistent naming controls across the Save dialogs.** The "Add a descriptive
  prefix" option now also appears in the layout editor's **Save as…** and
  **Save & apply** dialogs, with a suggested name pre-filled (Save as… replaces
  the old "Suggest name" button with the same locked-prefix field and gained a
  location picker). Turning the option off now keeps the full name as editable
  text instead of blanking the field. (#68, thanks **Knut (@soul-traveller)**)

## v3.10.24

### 🐛 Fixed
- **Info popup no longer sends its window behind the main window.** Closing the
  ⓘ details popup from a dialog that is itself a child of another window (e.g.
  the layout editor's "3D distribution…" cube, or the New Chart window) used to
  drop that window behind the main window on macOS. It now stays in front. (#66,
  thanks **Knut (@soul-traveller)**)

### 💄 Improved
- **Add-patches window now has an ⓘ with the colour-set help.** The layout
  editor's "Add…" window gained the same info icon the New Chart window has,
  explaining each generator set (3D cube, skin tones, blues, greens, greys,
  saturated edges, highlights/shadows, pastels, from image, fill). (#66, thanks
  **Knut (@soul-traveller)**)

## v3.10.23

### 🐛 Fixed
- **Create Chart name generator no longer doubles preset names.** Applying a
  preset whose name was already descriptive (e.g.
  `ColorMunki-A3-1196p-2pages-w11.5mm-Portrait`) used to re-append the generated
  details, producing `…-Portrait-…-Portrait`. A loaded preset / applied /
  reflected chart now keeps its own name verbatim — the generator only fills in
  a fresh chart's name. (#68, thanks **Knut (@soul-traveller)**)

### 💄 Improved
- **Generated chart names now sort cleanly.** The "Add a descriptive prefix"
  option (was "suffix") now puts the chart's details — instrument, paper, patch
  count, pages, orientation — at the *start* of the name as a locked prefix,
  with your own text after it (e.g. `i1Pro-A4-484p-1page-Portrait-Baryta`). That
  keeps similar charts grouped together in the folder list. Clicking the field
  drops the cursor right after the prefix, ready to type. (#68, thanks
  **Knut (@soul-traveller)**)
- **Built-in preset names follow one standard.** All bundled presets now use
  `<instrument>-<paper>-<patches>p-<pages>pages-<orientation>-<extras>`; the patch
  width (`-wXmm`) and colour-set name (e.g. `TC9.18+Spyderprint Grays`) moved to
  the tail so the sortable part leads. (#68)

### 🧰 Internal
- Fixed an intermittent test-suite hang (a soft-proof dialog left a proof timer
  armed past the test, which later popped a blocking dialog) and hardened
  `scripts/run_tests.sh` with run serialisation and a watchdog timeout.

## v3.10.22

### 💄 Improved
- **Create Chart (manual): tidier Output layout.** The Target-name and
  Chart-notes fields and the option checkboxes below them now line up with the
  same left edge as guided mode (the label column was a touch too wide before),
  and the labels are no longer clipped.

## v3.10.21

### 💄 Improved
- **Layout editor 3D view: patch numbers on hover.** In the chart-layout
  editor's "3D distribution…" popup, hovering a patch now shows
  `patch #: N · RGB r g b`, so you can find that point in the swatch and layout
  preview. (Only there — the other 3D views keep the plain label.) (#67, thanks
  **Knut (@soul-traveller)**)

## v3.10.20

### 💄 Improved
- **3D RGB cube: clearer controls.** The patch-distribution and Compare cubes
  now show a help line (drag to rotate, scroll to zoom, right/middle-drag to
  pan) and support the **keyboard**: arrow keys rotate, **Shift+arrows** pan,
  **+ / −** zoom. Full details — including the compare-cube camera sync — are in
  the window's ⓘ. (#66, thanks **Knut (@soul-traveller)**)

## v3.10.19

### ✨ Added
- **Self-naming charts: "Add a descriptive suffix".** A new option (on by
  default) in Create Chart — guided *and* manual — and in the Save Preset
  dialog keeps a live tail on the name: instrument, paper, patch count, pages
  and orientation (e.g. `Baryta-i1Pro-A4-484p-1page-Portrait`). You type just
  the base; the suffix updates by itself as you change those settings and can't
  be edited directly. Turn it off to name the chart entirely yourself. Replaces
  the old "Suggest name" button.

## v3.10.18

### 💄 Improved
- **Long preset dropdowns now scroll.** The Create Chart → Manual presets list
  and the patch-distribution "Compare with profile" list are capped (20 and 15
  rows) with a scrollbar instead of an over-long popup, keeping their instrument
  separators.

## v3.10.17

Big thanks to **Knut (@soul-traveller)** for the ideas and testing behind most
of this release (#62, #64, #65, #66 and the soft-proof feedback).

### ✨ Added
- **Soft-proof is now hands-free and far more capable.** Pick an image and a
  printer profile and the preview appears and re-renders on its own as you
  change options — no button to press; options grey out until they're usable.
  The preview now **zooms and pans** (mouse-wheel zoom, drag to pan,
  double-click to fit), renders at **full resolution**, and you can **Save the
  proof** (PNG/TIFF/JPEG) for sharing. (#65)
- **Soft-proof "Other ICC profile…".** Choose your own working-space profile for
  the source; and the bundled sRGB/Adobe RGB/P3/ProPhoto profiles now resolve
  even when ArgyllCMS's own `ref` folder isn't found (e.g. Homebrew installs).
  (Knut)
- **3D RGB cube: middle-button drag pans** the view, in every window that shows
  the cube. (#64)
- **Patch distribution (3D): compare two charts side by side.** A "Compare with
  profile" dropdown opens a second cube of any preset's patches next to the
  current one, with the two cameras locked **continuously in sync** — rotate,
  zoom or pan one and the other follows. In both the Tools viewer and the chart
  editor's 3D popup. (#66)

### 💄 Improved
- **Soft-proof Gamut-fit view** gains separate **opacity / saturation /
  wireframe** controls for the image and printer gamuts (a wireframe gamut stays
  visible through the other), and friendlier in-app help.
- **File dialogs** show OS-correct Desktop / Pictures / Downloads / Documents
  shortcuts; Save-proof defaults to your Pictures folder.
- **Built-in presets feed the patch count** into Suggest-name, like custom
  presets do. (#62)

## v3.10.16

### 🐛 Fixed
- **The "preset already exists" prompt works again.** Saving a preset with a
  name that already exists now reliably asks to overwrite — it had been crashing
  silently behind the scenes (an unimported dialog), so no warning appeared and
  a duplicate could be created. (#59, thanks **Knut (@soul-traveller)** for the
  log that pinpointed it)
- **"Suggest name" is more complete.** The Create Chart Suggest-name button now
  includes the patch count (the predicted count in guided mode, the loaded
  preset's count in manual mode) and the page orientation, e.g.
  `ColorMunki-A3-1575p-3pages-Landscape`. (#62)

## v3.10.15

### ✨ Added
- **Soft-proof: simulate paper white.** A new option (under Intent) renders the
  preview — and the margin around it — with the paper's actual white from the
  printer profile (often a cream tint) instead of bright display white, for a
  more realistic proof. The out-of-gamut figure is unaffected.
- **Soft-proof: a built-in test target.** "Use built-in test target" loads a
  bundled Adobe RGB photographic colour target (the PhotoDisc/PDI freeware
  target), so you can try the tool without finding an image.
- **Soft-proof: image previews in the file picker**, and the picker opens wider.

### 🐛 Fixed
- **Saving a preset keeps your name exactly.** Dots, hyphens, underscores and
  spaces stay distinct and usable in names; the layout editor's Save & apply no
  longer turns a dot into an underscore, so a name like `Epson-A3-w11.5mm` stays
  consistent everywhere (and re-saving it correctly prompts to overwrite). (#59,
  thanks **Knut (@soul-traveller)**)
- A greyed-out checkbox's tick now greys with its label (e.g. "Highlight
  out-of-gamut" while the soft-proof is off).

## v3.10.14

### 🐛 Fixed
- **Saving a preset over an existing one always prompts now.** Names that
  differ only by punctuation — e.g. a dot vs the underscore the name cleaning
  produces (`w11.5mm` vs `w11_5mm`) — are now treated as the same preset, so you
  get the overwrite prompt instead of a near-identical duplicate. (#59, thanks
  **Knut (@soul-traveller)**)

## v3.10.13

More from **Knut (@soul-traveller)**'s testing. 🙏

### ✨ Added
- **13 ready-made example charts built in.** Knut's exported Create-Chart charts
  (i1Pro and ColorMunki, A4/A3/A3+, various patch counts, page counts and
  orientations — several triple-density) now ship as built-in presets in the
  Create Chart dropdown, and the ones with a colour-set design also appear in the
  New-chart "Load setup from preset" list. They replace the earlier four
  Wide-gamut presets. (#63)
- **"Suggest name" everywhere it's useful.** The button is now on the guided
  Create Chart Target-name field (with the predicted patch count) and the Save
  Preset dialog, in addition to manual mode and the layout editor. (#62)
- **Soft-proof remembers your last image** — it pre-fills it and opens the file
  picker in its folder.

### 🐛 Changed
- **Add window shows the resulting chart size too.** Beneath the additions
  total, the Add dialog now shows "Chart after adding" (existing patches + the
  generated additions). (#60)

## v3.10.12

More fixes from **Knut (@soul-traveller)**'s testing. 🙏

### 🐛 Fixed
- **Add window: the total counts the right thing.** It now shows how many
  patches the selected colour sets would add (the ticked sets plus Pure white &
  black and Fill remaining gaps) and shows it even when "Generate colour sets"
  is off — matching the per-set counts beside each option. (#60)
- **Saving a preset with an existing name always asks to overwrite.** A name
  pasted with an invisible character (e.g. a zero-width space) could slip past
  the check and create a duplicate; names are now normalised before comparing,
  so look-alike names match. (#59)

### ✨ Added
- **"Suggest name" in Create Chart.** The Target name field now has a
  Suggest-name button (instrument · paper · pages), like the one in the layout
  editor's Save & apply. (#62)

## v3.10.11

Two new Tools, plus more fixes from **Knut (@soul-traveller)**'s testing. 🙏

### ✨ Added
- **New tool — Inspect a profile.** Opens any ICC profile and shows what's
  inside it in plain language: version, kind of device, colour space, white
  point, who made it, and (for v2 profiles) its gamut volume. It also explains
  the **ICC v4** limitation clearly — ArgyllCMS only reads v2 profiles, so a v4
  profile (common from i1Profiler) can't be shown in the 3D gamut viewer or the
  soft-proof tool, even though it still works in other colour-managed apps.
- **New tool — Soft-proof / check an image.** Loads an image and a printer
  profile and shows how it will print: an approximate on-screen soft-proof with
  the colours your printer can't reproduce highlighted, a headline **% out of
  gamut**, and a 3D "Gamut fit" view that overlays the image's colours on the
  printer's gamut. Your monitor profile is detected automatically for a truer
  proof, and you can pick the image's colour space (sRGB, Adobe RGB, Display P3,
  ProPhoto, or its embedded profile).

### 🐛 Fixed
- **Add window: the total patch count is correct again.** It now reflects the
  chart's final size — your existing patches plus the generated additions
  (including Pure white & black and Fill remaining gaps) — matching the 3D
  cube exactly, instead of reading 0 or leaving sets out. (#60)
- **Triple-density layouts transfer faithfully from the editor.** A chart laid
  out in the layout editor at a custom margin / patch size now keeps those
  values in the Create Chart tab instead of being reset to the triple-density
  defaults. (#45)
- **Save & apply suggests a useful name.** It pre-fills the target name when one
  was carried into the editor, or — for a chart built fresh there — a name
  describing the instrument, paper, patches, pages and orientation (e.g.
  `i1Pro-A4-480p-2pages-Landscape`), with a **Suggest name** button. (#62)

## v3.10.10

### ✨ Added
- **Read single patches: average selected readings.** A new **Average selected**
  button (in the bottom row, between Take reading and Clear) lets you pick two or
  more readings already in the list and combine them into a new entry — handy for
  averaging repeat measurements of the same colour. The new entry is named
  "Average" (you can rename it) and shows its own L*a*b*/XYZ values and colour
  swatch, just like a measured reading, so it can be saved with the rest.

## v3.10.9

More polish from **Knut (@soul-traveller)**'s testing. 🙏

### 🔧 Changed
- **Read single patches: one tidy button row.** Start session, Take reading and
  Clear now sit together on the left of the bottom button row (with Save and
  Close on the right), instead of a separate row above the table. The results
  table also gives the Name column more room, keeps the L*a*b*/XYZ value columns
  compact, and shows a slightly larger, taller colour swatch.

### 🐛 Fixed
- **Tool windows no longer overlap their own controls when made shorter.** When
  you dragged the Average measurements, Merge measurements, the TI1 ↔ i1Profiler
  converters, or the Verify windows to a smaller height, buttons could slide over
  the fields above them and options squished together. Those windows now stop
  shrinking at the point where everything still fits.

## v3.10.8

### 🔧 Changed
- **A subtle accent wash behind the headers.** The tab-style headers in the Tools
  windows, the "update available" popup and the layout-editor windows now carry
  the same gentle accent-colour gradient behind their headline that the
  main-window tabs have — washing softly behind the title text while buttons and
  controls sit cleanly on top.

## v3.10.7

More fixes and polish from **Knut (@soul-traveller)**'s testing. 🙏

### ✨ Added
- **The Wide-gamut presets now appear in "Load setup from preset"** (New chart
  window, marked with ★) — so you can load one of those designs and tweak it,
  not just build it as-is. If you've saved a custom preset with the same name,
  an identical one is hidden and a different one is kept alongside. (#55, #58)
- **The "Report a Bug" form now also fills in your hardware and ArgyllCMS
  version** automatically, and the Severity question moved up the form so it's
  harder to miss. (#56)

### 🐛 Fixed
- **Margin shows as set after Save & apply.** A chart applied from the layout
  editor left the Create Chart margin row unticked at the default 6 mm, reading
  as "no margin set"; it now shows enabled. (#61)

## v3.10.6

### 🐛 Fixed
- **Add-patches total now matches the 3D preview.** When you opened the editor's
  **Add** window for a chart loaded from a preset, the running patch total could
  read a few patches lower than the 3D cube showed (it was an estimate that
  couldn't see the existing chart's white/black structure). The total is now
  taken straight from the patches actually generated, so it always agrees with
  the preview. (#60) — thanks **Knut (@soul-traveller)**.

## v3.10.5

Bug fixes for the new presets and preset handling, all reported by **Knut
(@soul-traveller)**. 🙏

### 🐛 Fixed
- **Custom paper size no longer collapses the dropdown.** Loading a preset with
  a custom W×H paper (e.g. the Wide-gamut ColorMunki charts) squished the Create
  Chart paper-size dropdown to a thin line and made the panel scroll sideways on
  macOS. The dropdown now keeps its full height and the row stays within the
  panel. (#57)
- **Wide-gamut presets keep their own patch set when regenerated.** Generating
  one again — for example after ticking *Preserve patch order* — loaded the
  shared TC9.18 1168-patch set instead of the preset's own, producing a different
  chart. It now reuses the correct patch set, and the info text and tooltip show
  the preset's real patch count. The command preview is also selectable now. (#58)
- **Saving a preset over an existing name asks first.** Instead of silently
  overwriting (or, on macOS, duplicating) a preset, ChromIQ now confirms the
  overwrite or lets you cancel and pick a different name. (#59)

## v3.10.4

Reuse a chart's design, and file issues with less typing — from **Knut
(@soul-traveller)**'s suggestions. 🙏

### ✨ Added
- **Reuse a chart's recipe.** The New chart / Add window settings that produced a
  chart — colour sets, instrument, paper and layout — are now saved with the
  chart and reloaded into those windows when you reopen it, so you can tweak or
  recreate a design instead of rebuilding it by hand. Charts without a saved
  recipe still fall back to your last-used values, and Reset still restores the
  app defaults.
- **"Load setup from preset" in the New chart window.** A dropdown that loads a
  whole saved setup from a preset in one go. Presets you save now carry their
  setup; the dropdown lists the ones that have it and otherwise stays at *None*
  (with a tooltip explaining what it does).
- **Pre-filled issue forms.** **"Report a Bug…"** and a new **"Request a
  Feature…"** button in Preferences open GitHub's forms with your ChromIQ
  version, platform and OS version already filled in — fewer fields to type.

## v3.10.3

Chart-design polish, new presets, and a friendlier update notice — most of it
driven by **Knut (@soul-traveller)**'s testing and ideas. 🙏

### ✨ Added
- **Four "Wide-gamut" built-in presets** (Knut's multi-colour-set charts, each
  with its own patch set): i1Pro A4-924p, and ColorMunki A3 1196p / 1575p / 2016p.
- **Startup "update available" popup.** When a newer release exists, ChromIQ now
  shows a tidy popup (tab-style header + spectrum stripe) that links to the
  download page, replacing the old status-bar line. It never installs anything
  on its own. A new **Settings → "Check for updates on startup"** toggle (and the
  popup's "Don't remind me of new available versions" box) turn it off and on.
- **Tab-style headers across the Tools windows** — uppercase eyebrow + serif
  title over the five-colour spectrum stripe, with a per-tool accent colour.

### 🔧 Changed
- **Saturated edges auto-follows the 3D cube** (cube per-axis − 1, to fill the
  cube's frame gaps once) until you set it yourself; your choice is remembered.
- **Near-neutral greys default to 16 / 4 / 1.**
- The **Add patches** window opens tall enough to show its whole left column, and
  both chart-design windows now grow **symmetrically** when you unfold the 3D
  preview (instead of only to the right).

### 🐛 Fixed
- **Applied editor charts now randomise correctly.** Unchecking "Preserve patch
  order" after Save & apply re-runs printtarg (randomised) instead of being seen
  as "no change" and copying the fixed-order chart — so randomisation no longer
  depends on toggling an unrelated option.
- The editor's **instrument / paper readout updates live** when you change them.
- The editor's **New chart / Load .ti2 buttons no longer clip** their text.

## v3.10.2

A fix for an app freeze when using the 3D-cube preview in the chart-design
windows (seen on Windows).

### 🐛 Fixed
- **The New chart / Add patches windows no longer freeze the app when the
  3D-cube preview is used.** The cube's browser view was built while the window
  was already open as a modal dialog, which on Windows wedged the modal grab and
  locked up every other window — whether the preview opened unfolded or you
  unfolded it afterwards. The view is now always built while the window is still
  non-modal, so the modal grab is never created mid-build. This is the robust
  path on every platform, not a Windows-only workaround.

## v3.10.1

A Windows-focused follow-up to v3.10.0, plus a refinement to the Saturated-edges
colour set. Once again driven by **Knut (@soul-traveller)**, whose Windows
testing and design notes turned up every item below. 🙏

### 🔧 Changed
- **"Saturated edges" now fills the gaps left by other sets.** On its own the
  set was already evenly placed, but combined with sets that also sit on the
  gamut boundary — the 3D cube above all — it re-sampled the very same edge and
  face points instead of filling between them. It now reads the patches already
  placed and lays its samples at the midpoints of the boundary gaps (largest-gap
  splits along each edge, a blue-noise-then-centroidal fill on each face), so it
  complements the cube rather than doubling up on it. Used on its own the output
  is byte-for-byte the original even spacing; the patch count is unchanged.

### 🐛 Fixed
- **The New chart / Add patches windows no longer freeze the first time you open
  the 3D preview on Windows.** Opening the very first preview spun Chromium up
  from scratch in the middle of the window's modal transition, which reordered
  and "reloaded" the editor and left the whole app unresponsive. ChromIQ now
  warms the preview engine up once at startup — off to the side, out of any
  dialog — so opening a preview is quick and side-effect-free every time.
- **The layout editor's preview no longer jumps around on Windows after each
  update.** When a preview finished rendering, the status line below the patch
  grid briefly forced its column wider — squeezing the preview — then snapped
  back a few seconds later when the message cleared. The status line is now
  free of the layout, so the preview and patch-grid columns hold their width.

## v3.10.0

**The chart layout editor takes centre stage.** Over the last dozen releases the
editor and its colour-set generators have grown from a simple `.ti2` viewer into
a full chart-design studio — this release rounds that work off with three new
generator improvements and gathers the whole feature into one place. Huge thanks
to **Knut (@soul-traveller)**, whose relentless testing and design ideas drove
almost all of it — including everything new below (issue #53). 🙏

### ✨ Added
- **New "Sunrises (warm)" colour set.** A warm-side companion to the Blues and
  Greens sets: golden yellows, oranges, reds and pinks — the sunrise side of the
  gamut nothing else concentrated on, for skies, flowers and warm highlights. It
  has the same **per layer × layers** controls as its cool siblings, joins the
  *Ensure unique colours* de-duplication, and counts toward the *Fill remaining
  gaps* top-up. On by default alongside Blues and Greens.

### 🔧 Changed
- **"Fill remaining gaps" now fills evenly, at the gap midpoints.** Instead of
  scattering the top-up patches at random, the fill now seeds the sparsest
  regions and then relaxes every added patch onto the centroid of its
  neighbourhood (a few Lloyd passes) — so they settle at the midpoints of the
  empty space and come out balanced rather than clumped. The "fill to N" target,
  the existing-chart top-up and the white/black accounting are all unchanged.
- **Skin-tone ranges stay true skin tones.** Adding more than one range used to
  fan parallel lines that drifted out of the skin region toward yellow-green and
  olive. The generator now works in CIELAB and keeps every range inside the real
  skin locus — grounded in the **Pantone SkinTone Guide** (its colours split into
  red/yellow undertones at the 60° hue angle) and the Fitzpatrick/ITA literature.
  Extra ranges now vary the **undertone** (rosier ↔ more golden) within that
  wedge, while lightness sweeps along each phototype's natural pathway with
  chroma easing off at the pale and deep extremes. Up to five ranges per type now
  give genuine skin-tone variety instead of wandering off into greens.

### 📋 The chart layout editor — what it can do

A spec sheet for the feature this release celebrates:

- **Open & create** — load any ArgyllCMS `.ti2`, or build a brand-new chart from
  scratch, then re-layout it for any instrument and paper size.
- **Direct patch editing** — add, delete, recolour and reorder patches on a live
  swatch grid, with a two-way link to the chart preview (select on either side).
- **Combinable colour-set generators** — eleven sets you can mix freely: an even
  **3D RGB cube**, **Fitzpatrick skin tones**, **Blues / turquoise**, **Greens
  (foliage)**, **Sunrises (warm)**, **near-neutral greys** (with hue rings),
  **saturated edges** (gamut wireframe + faces), **highlights & shadows**,
  **pastels**, **colours pulled from one of your own images**, and **pure white
  & black** anchors — each with its own size controls and a live patch count.
- **Even, unique coverage** — *Ensure unique colours* nudges any repeats apart,
  and **Fill remaining gaps** tops the whole chart up to a target count, placed
  evenly in the empty space.
- **Live 3D preview** — a foldable RGB-cube view shows exactly what your ticked
  sets would produce as you tune them, drawing the existing chart underneath when
  you're adding to one, so you can see gamut coverage and clumping at a glance.
- **Full undo / redo** — Ctrl+Z / Ctrl+Shift+Z through your last 20 edits, in
  memory only, cleared when you close the editor.
- **Settings that stick** — every generator choice is remembered between sessions
  and restored by *Reset to defaults*.

### 🌍 Translations
- The new "Sunrises (warm)" set is translated into all twelve languages.

## v3.9.31

A fix for a nasty freeze when opening the New chart / Add patches windows from
the layout editor, plus some visual polish to those windows.

### 🐛 Fixed
- **Opening *New chart* or *Add patches* from the layout editor no longer makes
  the editor flicker (close + reopen) and could freeze the whole app.** The
  embedded 3D-cube preview built its web view up front — even while folded away —
  and on macOS that reordered the windows mid-dialog and left the app with a
  stuck modal grab, so the main window stopped responding. The cube's web view is
  now created only when you actually unfold the preview, so opening these windows
  with the cube hidden (the default) is clean and instant.

### 🔧 Changed
- **Tab-style headings in the chart-design windows.** The layout editor, *New
  chart* and *Add patches* windows now carry the same eyebrow + serif-title
  heading as the main-window tabs, set off by a full-width spectrum bar.
- **Layout-editor tidy-ups.** The *New chart* / *Load .ti2* buttons swapped
  places, and the status line now sits under the patch grid and fades itself
  away a few seconds after each message instead of spanning the whole window.

## v3.9.30

Undo and redo come to the chart layout editor — experiment freely, nothing is a
one-way door anymore.

### ✨ Added
- **Undo / redo in the chart layout editor.** New **↶ Undo** and **Redo ↷**
  buttons (centred above the editor, with the usual **Ctrl+Z** / **Ctrl+Shift+Z**
  shortcuts) step back and forth through your last 20 edits. Everything is
  covered: deleted patches come back, added ones go away again, and recolours,
  reorders, spacer painting and layout-knob tweaks all reverse cleanly. The
  history lives only in memory and is cleared the moment you close the editor —
  it never touches your drive — and it starts fresh whenever you load or create a
  different chart.
- **A spectrum separator in the layout editor.** A thin full-width band of the
  ChromIQ tab colours now sits under the Load / New / Undo / Redo row, matching
  the main-window masthead, to set the controls apart from the editing area.

### 🔧 Changed
- **Downloads are now version-stamped.** Release files now carry the version in
  their name (e.g. `ChromIQ-macOS-universal_v3.9.30.dmg`), so saved downloads no
  longer collide as "…(1).dmg" and each file says which build it is. The install
  guides in the README and manual reflect the new names.

## v3.9.29

A new way to *see* the colour sets you're building before you commit to them.

### ✨ Added
- **Live 3D RGB-cube preview in the chart generators.** The New chart and
  *Add patches* dialogs now have a foldable 3D cube panel that shows exactly
  what your ticked colour sets ("Generate colour sets") would produce, redrawing
  live as you change the steps, layers and other settings. In the *Add* dialog it
  also draws the chart's existing patches (dimmed) underneath the ones you're
  about to add, so you can see at a glance how your additions fill the gaps.
  Click **"Show 3D preview ▸"** to reveal it — it stays folded away by default
  and remembers your choice — then rotate, zoom and pan the cube to judge gamut
  coverage and patch clumping. It's the same cube as the editor's
  *3D distribution…* view, now wired straight into the generator.

## v3.9.28

A small follow-up to v3.9.27's *Fill remaining gaps* fix.

### 🐛 Fixed
- **"Fill remaining gaps" now counts the pure white & black anchors toward its
  target.** "Pure white & black" was being added *after* the fill, so it stacked
  on top of an already-full chart and you ended up with more patches than the
  "fill to N" target. Generation now runs sets → white/black → fill, and the live
  count matches, so "fill to N" lands on exactly N patches. (White and black are
  still kept even if they duplicate another patch, and the fill still avoids
  placing patches on top of them.)

## v3.9.27

A fix-up release on the back of **Knut (@soul-traveller)**'s and **Pharmacist**'s
testing of the previous build — thank you both! 🙏

### 🐛 Fixed
- **Editor *Fill remaining gaps* now tops up the chart instead of overfilling
  (issue #51).** In the editor's *Add…* dialog, "Fill remaining gaps: N" now
  brings the *whole* chart up to N — the patches already present count toward the
  target and the fill works around them — rather than appending N more. Building
  a brand-new chart is unchanged.
- **Long names no longer clip the rename chooser's buttons (issue #52).** The
  target-rename dialog's option buttons embed the (variable-length) target name,
  so long names — or longer translations — could clip the text at both ends. Each
  button now reserves at least its text width plus padding and the dialog grows
  to fit, in every language.
- **Dutch labels that overflowed their row are shortened.** Pharmacist spotted
  *Kleurmiddel toevoegen/verwijderen* being cut off in the Create Chart manual
  options — it's a fixed-width control. It's now *Kleurmiddel wijzigen* (matching
  the German *Farbmittel ändern*), and the patch-consistency setting is now the
  shorter *Consistentietolerantie*. Also fixed a stray *Meetmeetveld* typo left
  by the v3.9.26 terminology sweep.
- **"Pure white & black" settings now persist and reset.** Filling a gap from
  v3.9.25: the generator's checkbox and amount are wired into the save/restore
  and factory-reset paths, so they're remembered between sessions and cleared by
  *Reset to defaults*.

## v3.9.26

A Dutch-language polish pass, with big thanks to **Pharmacist** for the careful
review. 🙏

### 🌍 Translations
- **Dutch terminology made consistent.** Pharmacist noticed the Dutch UI used
  several different words for the same thing — a *patch* was variously a `vak`,
  `meetvak` or `vlak`, and *spacers* showed up as both `tussenvak` and
  `scheidingsvak`. Every other language had already settled on one term each, so
  Dutch was the odd one out. It now uses a single word throughout, in labels
  *and* in the tooltip text behind them:
  - **patch → `meetveld`** (a "measurement field"). Chosen over `meetpunt`
    because you scale a field's *size* — a dimensionless "point" reads oddly
    there — and it lines up with how German (`Messfeld`), Norwegian and Swedish
    already name it.
  - **spacer → `scheidingslijn`** (a "separator line"), matching the Spanish,
    Portuguese and Polish translations.
  - **shuffle / randomise → `randomiseren`**. The old `husselen` is an archaic
    word for shuffling *physical* objects like playing cards, not abstract
    colour patches — so it's gone, along with the now-redundant
    "gehusselde (gerandomiseerde)" explanations.
- **More natural phrasing.** A few clunky hyphenated labels were rewritten the
  way Dutch actually reads (*Neutrale-as-nadruk* → *Nadruk neutrale as*,
  *Schaduwgebied-nadruk* → *Nadruk schaduwgebied*), and the cryptic
  *Kleurmiddel +/−* is now spelled out as *Kleurmiddel toevoegen/verwijderen*.
- **Meanings left intact on purpose.** Where a "nicer-sounding" word would have
  quietly changed the meaning, we kept the accurate one: *Apparaattype* stays
  **device type** (not colour space), *Doelnaam* stays **target name** (not
  profile name), and *Neutrale-as-stappen* stays **steps**.

### 🐛 Fixed
- **German: the reorder hint now matches its buttons.** In the chart-layout
  editor the tip text mentioned *Erstes / Letztes* while the actual buttons
  read *Anfang / Ende*. The hint now says *Anfang … Ende* to match — and to stay
  consistent with the existing *Am Anfang / Am Ende* wording elsewhere.

## v3.9.25

More from **Knut (@soul-traveller)**'s testing on #37 — thank you! 🙏

### ✨ New
- **"Pure white & black" colour set.** A new generator option that adds pure
  paper white and the deepest printable black — the two anchor points a good
  profile needs. A spin sets how many of *each* to include, and they're kept
  verbatim even with *Ensure unique colours* on (handy for averaging repeated
  readings of paper white). It's also aware of the rest of the chart: whatever
  the 3D cube, near-neutral greys or saturated edges already contribute counts
  toward your number, so asking for three of each when one is already there adds
  just two more.
- **A heads-up when added colours already exist.** When you use the editor's
  *Add… → Generate colour sets* and some of the generated colours are already in
  the loaded chart, ChromIQ now explains it in plain language and lets you *Make
  them unique* (nudge the repeats to free cells, keeping the full count), *Add
  only the new ones* (drop the repeats), *Add anyway*, or *Cancel* — so the same
  patch isn't silently printed twice.

### 🐛 Fixed
- **"Highlights & shadows" interlocks more precisely with *Near-neutral greys*
  (issue #37).** Following more of Knut's on-device testing, a highlight/shadow
  cone now yields its centre only where a grey step actually sits (within a
  couple of code values) rather than along its whole length. The gaps between
  grey steps keep filling in to the neutral axis, so few grey steps leave the
  cones almost whole while many tight steps carve out more — matching the grey
  ramp you actually chose.

## v3.9.24

Another round driven by **Knut (@soul-traveller)**'s testing — thank you! 🙏

### 💡 Improved
- **The layout editor preview is much faster (issue #44).** It used to render
  the chart twice (once for a hidden helper image) at full print resolution and
  re-scan every page after each change, which made generating and page-flipping
  sluggish. The on-screen preview now renders at a low resolution (the chart you
  *save* still uses your full DPI), skips the helper render unless you're
  actually editing spacers, and analyses only the page you're looking at. On a
  400-patch A4 chart the render step dropped from ~0.55 s to ~0.08 s (~7×), and
  page navigation is snappy.
- **Save Preset suggests the right name (issue #50, follow-up).** The suggested
  preset name now comes from the target name in the output frame rather than a
  preset that merely happened to still be selected, so it matches the chart you
  actually built.
- **Platform-correct key hints (issue #45, follow-up).** The spacer/patch
  selection hints in the editor now show **Ctrl / Alt** on Windows and Linux
  (and ⌘ / ⌥ on macOS) instead of always showing the Mac symbols.

### 🐛 Fixed
- **"Highlights & shadows" now fills the corners and the neutral tones (issue
  #37).** Following Knut's on-device testing, the highlight/shadow cones are
  filled rather than hollow shells, run all the way into the paper-white and
  pure-black corners, and — with *Near-neutral greys* off — cover the
  near-neutral light/dark tones that were previously missed. With greys on, the
  overlapping core is dropped and those patches are re-spent in the chromatic
  rim, so none are wasted. The two ends stay mirror-symmetric.
- **Highlight outline aligned on double-density charts (issue #48).** With the
  ColorMunki *double density* zig-zag layout (every other strip shifted half a
  patch), the "Highlight selected in preview" outlines were off by half a patch
  on the shifted strips. Each strip's patch positions are now detected
  individually, so the outlines line up. (This also restored the highlight and
  click-to-select-a-patch features, which had briefly stopped drawing after the
  preview-speed change above.)
- **Close dialog no longer asks twice (issue #49, follow-up).** Discarding
  unsaved changes from the editor's Close button prompted a second time; it now
  asks exactly once, and the dialog's buttons no longer clip their labels.

## v3.9.23

A small follow-up release, again shaped by **Knut (@soul-traveller)**'s testing
and analysis — thank you! 🙏

### 💡 Improved
- **Open the layout editor on the chart you're working on (issue #45).** Opening
  *Edit / create chart layout* now pre-loads the Create Chart tab's current
  chart — patches *and* every printtarg setting (instrument, paper, scales,
  margin, spacers, density, DPI, bit depth, strip options) — so it's ready to
  edit straight away. It loads a copy, so your working folder is untouched
  unless you Save & apply; **New chart** / **Load .ti2** still let you start
  from something else. (The natural counterpart to v3.9.22's Save & apply, so
  charts now travel both ways.)
- **Clearer spacer-editing wording in the layout editor (issue #47).** The
  Spacers-mode text now says *where* to act — click a spacer **on the page
  preview in the centre** (drag a box for several; ⌘/Shift to add, ⌥/Alt to
  remove) — and the palette is relabelled to explain it's the candidate colours
  printtarg auto-assigns per gap, as distinct from the per-spacer paint
  override. No behaviour change, just copy.

### 🐛 Fixed
- **"Highlights & shadows" ends are now symmetric (issue #37).** The shadow end
  of the *Highlights & shadows* colour set is now the exact mirror of the
  highlight end, so the two come out congruent instead of lopsided (the old
  asymmetry was an HSV-lightness artefact, not real gamut geometry). The set
  also interlocks with **Near-neutral greys**: with greys on it sits just
  outside their rings so no colour is printed twice, and with greys off it
  reaches in to cover the near-neutral light/dark tones itself. Applies in both
  the New-chart window and the new Add-patches popup.

## v3.9.22

More layout-editor polish and workflow fixes, again driven by careful testing
and suggestions from **Knut (@soul-traveller)** — thank you! 🙏

### ✨ New
- **Generate colour sets straight into the editor (issue #46).** The *Edit /
  create chart layout* tool's **Add…** button now opens a dialog where you can
  add a single chosen colour *or* generate one or more colour sets — 3D RGB
  cube, skin tones, blues, greens, near-neutral greys, saturated edges,
  highlights & shadows, pastels, from an image, and fill-the-gaps — and drop
  them at the start or end of the chart. The same generators the New-chart
  window offers, now available on a chart you're already editing (and they work
  even when no chart is open yet — a fresh one is created for you).
- **Close button in the layout editor (issue #49).** There's now an explicit
  **Close** button alongside Save As / Save & apply. If you have unsaved edits,
  Close (and the window's X) ask you to confirm first; saving clears that, so
  closing right after a save just closes.
- **i1Pro 3 Plus is its own instrument (issue #41).** In the layout editor the
  instrument list now offers *i1Pro 3 Plus* separately from the i1Pro family,
  so its larger-aperture strip layout is generated correctly.

### 💡 Improved
- **Save & apply now carries every layout setting (issue #43).** Handing a chart
  from the layout editor to the Create Chart tab used to transfer only the
  instrument and paper; the patch scale, margin, spacers, double/triple
  density, DPI, bit depth and strip options came along too now — so the manual
  panel reflects exactly what you laid out, even while it's locked. The sync is
  fully two-way.
- **The New-chart window remembers everything (issue #42).** Instrument, paper,
  the seed count and all the layout options are now kept between charts (not
  just the colour-set choices), and **Restore defaults** resets the whole
  window. The redundant *Name* field was removed — the name is chosen later at
  Save & apply.
- **Save Preset is friendlier (issue #50).** Saving a new preset pre-fills the
  name with your current target name (with a clear *Preset name:* label and a
  hint to change it), and defaults the *Generate immediately* and *Build from
  the loaded patch set* options on.
- The layout editor's **"Load from file…"** button is now compact, matching the
  *Load image…* button.

### 🐛 Fixed
- The i1Pro 3 Plus strip-only options (`-L` / `-P`) are now offered for it in
  the layout editor (previously gated to the plain i1Pro only).

## v3.9.21

A round of fixes and quality-of-life improvements for the chart workflow, most
of them sparked by detailed bug reports and suggestions from **Knut
(@soul-traveller)** — thank you! 🙏

### ✨ New
- **"Save & apply" in the layout editor.** The *Edit / create chart layout* tool
  now has a one-click **Save & apply** button that saves the chart you've
  designed *and* sets it up as a ready-to-use profiling project: it copies the
  files into a new working folder under a name you choose and opens it in the
  Create Chart tab, ready to print and measure. A friendly dialog walks you
  through exactly what will happen, and if the name you pick already exists
  you're asked whether to add it as a new run, replace the current chart, or
  cancel — so earlier measurements are never overwritten by accident.
- **A loaded chart now shows up everywhere.** Open a `.ti2` in the Print or
  Measure tab and the Create Chart tab mirrors it too, so every tab agrees on
  what you're working with. It's shown read-only — the patch recipe and layout
  are locked, with unlock boxes if you want to build your own from it — and a
  one-time note reminds you that any chart you'd built before is still safe in
  its own folder. Nothing is copied or overwritten.
- **A hint under the swatch grid** in the layout editor now spells out that you
  can drag swatches to reorder them, and Shift- or ⌘/Ctrl-click to move several
  at once.

### 🐛 Fixed
- **"Highlights & shadows" depth now affects the white side too (issue #37).**
  Turning up the *depth* control visibly filled in the dark (shadow) end of the
  cube but seemed to do nothing on the bright (highlight) end. It was actually
  moving both — but the highlights slid toward grey instead of fanning out into
  pale colour, so the change was invisible. They now spread into pale tints as
  you increase depth, mirroring the shadow side.
- **Loading a patch set no longer errors on "Generate Chart" (issue #40).**
  After loading a `.ti1` or i1Profiler patch set, the patch-generation panel
  stayed active and the loaded file was forgotten, so clicking Generate Chart
  failed with *"Nothing for targen to generate"* (and changing the patch count
  quietly overwrote your file). Loading a patch set now locks the recipe and
  lays it out as-is, exactly like a bundled preset — with an unlock box if you
  *do* want a fresh set.
- **Charts now carry the correct colour-space tag (issue #40).** Charts made by
  the layout editor or imported from i1Profiler were tagged as *video* RGB
  rather than *printer* RGB. It didn't affect the printed chart or the finished
  profile, but it could make a refinement *merge* of such a chart with a
  normally-built one fail. They now use the exact tag ArgyllCMS itself writes.

### 🔧 Changed
- The layout editor's **Save As** now also writes the patch colour list (what
  the old *Export* button produced), so the new **Save & apply** button could
  take its place — one button now saves everything.
- Small visual polish in the layout / new-chart dialogs: the lead action button
  and combo-box highlights use the app's magenta accent, and the
  Instrument / Paper row is tidier (including when *Custom* paper size is
  selected).

## v3.9.20

A big expansion of the New-chart **Generate colour sets** panel: five new
optional colour-set generators plus extra controls on the existing sets, all
off by default so existing charts are unchanged.

### ✨ New
- **Five new colour-set generators** in the New-chart dialog (each optional,
  off by default):
  - **Saturated edges** — samples the 12 RGB-cube gamut-boundary edges, with a
    new **per-face** control to also sample the 6 cube faces (the full gamut
    surface).
  - **Highlights & shadows** — pale tints near white and deep tones near black
    across the hue wheel, with a **depth** control for how far in from
    white/black the bands reach.
  - **Pastels** — low-chroma midtones across all hues, with **per-layer ×
    layers** chroma shells, from barely-tinted near-greys out to fuller pastels.
  - **From image** — load a photo and let k-means (in Lab) pick its most
    representative colours.
  - **Fill remaining gaps** — blue-noise top-up to a target patch total,
    computed against everything else you've selected.
- **Restore defaults** button resets the colour-set options to factory defaults
  without touching your source mode, name, instrument or paper.
- The New-chart dialog now **remembers your last-used settings** — source mode
  and every colour-set value — between sessions.
- **Per-set ⓘ info icons** open each set's explanation in its own window; the
  "Load image…" button is now compact to match the spinboxes; the dialog
  scrolls so it fits small screens.
- Friendly tooltips for every set, translated across all 12 languages.

### 🐛 Fixed
- The **Highlights & shadows** checkbox now shows its literal "&" (Qt was
  swallowing it as a keyboard mnemonic).

## v3.9.19

### 🐛 Fixed
- **Crash on quit after using the 3D views — fixed for good (issue #38).** The
  previous fix tore each 3D view (RGB cube, gamut viewer, drift map) down the
  moment its window closed, which helped but didn't fully cure it: a couple of
  testers still hit the same crash on quit after using the patch generator and
  the 3D cube. The real cause is deeper than any single view — once a 3D view
  has been shown, some of the browser engine's shared machinery stays alive for
  the rest of the session, and the crash happened while Python was shutting that
  down at the very end. ChromIQ now does all of its real cleanup (saving your
  settings and window position, finishing any running tool) *before* exiting and
  then hands straight back to the operating system, skipping the fragile final
  shutdown step entirely. Quitting after using the 3D cube, gamut viewer or
  drift map is now clean every time. A new automated test keeps it that way.

## v3.9.18

### ✨ New
- **Near-neutral greys can now use multiple rings.** The greys set gains a
  *rings* control (1–3). Each grey step is still circled by gentle off-neutral
  tints, but now you can add wider, denser rings around it — ring 1 is 6 tints,
  ring 2 adds 12, ring 3 adds 18 — for fuller coverage of the near-neutral
  region, the part that matters most for clean, cast-free greys. Purely opt-in:
  the default (1 ring) is byte-for-byte the previous behaviour, so nobody who
  leaves it alone is affected. The rings are spaced at multiples of the existing
  *offset* and interleaved so they fill the disk instead of forming spokes.

## v3.9.17

### ✨ New
- **Export & Save As now also write i1Profiler files.** The layout editor's
  *Export colours…* button has a new *"i1Profiler (.txt + .pxf)"* format, and
  *Save As* drops an `<name>-i1profiler.txt` + `.pxf` pair into the chart folder
  alongside the .ti1/.ti2/TIFFs — so a chart you design here can go straight to
  i1Profiler.
- **More layers for Blues / turquoise and Greens.** The per-set *layers* control
  now goes up to 10 (was 5), for denser coverage of those wide-gamut corners.

### 🔧 Changed
- **"Generate colour sets" starts from a fuller default.** All five sets are
  ticked out of the box with a balanced 1152-patch starting point (cube 8³, skin
  8×3, blues 64×3, greens 64×3, near-neutral greys 16), so a useful chart is one
  click away.

### 🐛 Fixed
- **Save no longer aborts with a false "requested patch … missing from
  regenerated chart" warning.** Charts built from the colour-set generators use
  arbitrary device values that can sit exactly on an 8-bit boundary, where the
  save-time integrity check's rounding disagreed with printtarg's by a single
  code. The check now tolerates that one-code shift (it is below the device's
  own 8-bit resolution) while still catching a genuinely dropped patch.

## v3.9.16

### 🐛 Fixed
- **Crash on quit after using the 3D views** (issue #38). Opening the 3D RGB
  cube (Tools ▸ patch distribution, or the Edit-chart layout editor), the gamut
  viewer or the measurement drift map and then quitting could end the app with
  a hard crash ("ChromIQ quit unexpectedly") on macOS. The embedded web views
  were not being fully torn down, so they were still half-alive when the app
  shut down and the cleanup tripped over them. They are now disposed of
  immediately and cleanly when their window closes, so quitting is reliable.

## v3.9.15

### ✨ New
- **Generate colour sets — round two** (Tools ▸ Edit / create chart layout ▸
  New chart ▸ Patches). Building on the five generators from v3.9.13, the
  three palettes that benefit most are now richer, and combined sets stay clean:
  - **Skin tones (Fitzpatrick)** reach further — from porcelain-pale highlights
    down to very deep, faintly cool shadows — and a new **Ranges** control
    (1–5, default 3) adds parallel ramps offset in hue, so each skin type is
    covered by a small spread of tones instead of a single line. Total is now
    6 × ranges × per-type.
  - **Blues / turquoise** now dips into the **greenish turquoise** corner and
    gains a **Layers** control (1–5, default 3): each layer is a non-parallel,
    gently angled sheet, so the turquoise wedge is filled in depth rather than as
    one flat blanket. Count is **per-layer × layers**.
  - **Greens (foliage)** gains the same **Layers** control (1–5, default 2).
  - **Ensure unique colours** (on by default) — when sets share a colour (a 3D
    cube and a grey ramp both include black and white, say), duplicates are
    nudged apart by a tiny amount so no patch is printed and measured twice. The
    patch total is unchanged.
  - The New-chart window is a little wider and reserves room for the live
    counts, so the layout no longer jumps as the numbers grow.

  _Thanks to Knut (soul-traveller) for the detailed follow-up in #37._

## v3.9.14

### ✨ New
- **Translate / edit language** (Tools menu) — contribute or tweak a translation
  without editing any code. Export every phrase in ChromIQ to a **CSV or Excel
  (XLSX)** spreadsheet, translate the right-hand column in Excel, LibreOffice or
  Google Sheets, then import the file back. Covers both the interface text and
  the parameter tooltips. Imports are checked first (it tells you how many
  phrases were translated and flags any broken `{…}` placeholders or incomplete
  option lists) and saved to your personal ChromIQ folder, so your edits survive
  app updates and take effect after a restart. You can also start a brand-new
  language, and a **Send to developer** button opens a pre-filled GitHub issue so
  finished translations can be shared back. _Thanks to Knut (soul-traveller) for
  suggesting this in #39._

### 🐛 Fixed
- Windows: the XLSX export in the new translation tool no longer crashes in the
  packaged build (the `openpyxl` dependency is now bundled), and the test suite
  runs cleanly on Windows.

## v3.9.13

### ✨ New
- **Generate colour sets** (Tools ▸ Edit / create chart layout ▸ New chart ▸
  Patches) — a new way to fill a fresh chart with purpose-built colour spreads
  instead of, or alongside, a targen seed. Tick any combination of five
  generators and they're laid down in sequence, with a live patch count shown
  for each set and a running total:
  - **3D RGB cube** — an even N×N×N grid across the whole RGB range (you choose
    the number of steps per axis).
  - **Skin tones (Fitzpatrick)** — a light-to-dark ramp through each of the six
    Fitzpatrick skin phototypes.
  - **Blues / turquoise** — denser sampling of the turquoise-to-blue band that
    wide-gamut spaces (AdobeRGB and friends) stretch furthest.
  - **Greens (foliage)** — forest, jungle and foliage greens for nature images.
  - **Near-neutral greys** — a neutral grey ramp plus, at each step, six small
    hue tints around the neutral axis.

  Available in all thirteen languages. Resolves #37.

### 🐛 Fixed
- **Measuring-instrument dropdown in the New-chart dialog showed only one
  entry** — the device list (Tools ▸ Edit / create chart layout ▸ New chart)
  now opens at full, comfortable height instead of clipping to a row and a half.
- **Untranslated text in the chart-layout editor** — the New-chart info (ⓘ)
  panel and the patch-reorder buttons (First / Up / Last / Down) now appear in
  your language in all thirteen languages, and the info panel explains the new
  colour-set generators in full.
- **Ticked colour-set option stayed highlighted while inactive** — a checked
  generator now greys out properly until "Generate colour sets" is selected.

## v3.9.12

### ✨ New
- **Read single patches** (Tools ▸ Read single patches) — measure individual
  colours off any material with your instrument: printed sheets, fabric, paint
  chips, even a display. Each reading shows its L\*a\*b\* value and an approximate
  on-screen colour swatch; save the whole set as a CSV (for a spreadsheet) and an
  Argyll `.ti3` (for other tools). Reflective, emissive (display) and ambient
  measurement modes are supported, with the same plain-language calibration
  guidance as the Measure tab. Available in all thirteen languages. Resolves #36.

### 🐛 Fixed
- **Create Chart tab rendered blank on first show** — the tab now draws
  correctly the first time you open it. Fixes #35.
- **Crash on quit after opening the 3D patch cube** — closing the app after
  viewing the 3D patch distribution no longer triggers a "quit unexpectedly"
  crash. Fixes #38.

## v3.9.11

### ✨ New
- **Russian (Русский)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  other languages. ChromIQ now ships in thirteen languages: English,
  German, Dutch, Norwegian, Swedish, Italian, Spanish, French, Polish,
  Portuguese, Japanese, Simplified Chinese and Russian.

## v3.9.10

### ✨ New
- **Simplified Chinese (简体中文)** — complete translation (1,203 strings
  + all parameter tooltips), in the same extensive, friendly style as the
  other languages. ChromIQ now ships in twelve languages: English, German,
  Dutch, Norwegian, Swedish, Italian, Spanish, French, Polish, Portuguese,
  Japanese and Simplified Chinese.

## v3.9.9

### ✨ New
- **Japanese (日本語)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  other languages. ChromIQ now ships in eleven languages: English,
  German, Dutch, Norwegian, Swedish, Italian, Spanish, French, Polish,
  Portuguese and Japanese.

## v3.9.8

### ✨ New
- **Portuguese (Português)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  other languages. ChromIQ now ships in ten languages: English, German,
  Dutch, Norwegian, Swedish, Italian, Spanish, French, Polish and
  Portuguese.

## v3.9.7

### ✨ New
- **Polish (Polski)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  other languages.

## v3.9.6

### 🐞 Fixed
- **Translated UI no longer clips or overflows.** The two-line print
  buttons (Print Current Page / Print All Pages / Clear Print Queue /
  Save as Defaults), the Create Chart and Measure option panes, and
  several long option labels were clipped or forced a horizontal
  scrollbar in the translated languages. All eight languages audited
  and fixed; the Target name / Chart notes label column now sizes
  itself to the translated text instead of clipping it.
- The onscreen i18n audit now also checks multi-line buttons and
  horizontal overflow of scroll panes (`scripts/i18n_onscreen_audit.py`).

## v3.9.5

### ✨ New
- **French (Français)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  other languages.

## v3.9.4

### ✨ New
- **Spanish (Español)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  other languages.

## v3.9.3

### ✨ New
- **Italian (Italiano)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  other languages.
- **Norwegian dialog buttons now translated.** Qt ships no Norwegian
  translation of its stock dialog buttons (OK/Cancel/Close/Yes/No…), so
  they stayed English. ChromIQ now answers those lookups from its own
  fallback catalog whenever Qt's translation is missing.

## v3.9.2

### ✨ New
- **Swedish (Svenska)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  other languages.

### 🐞 Fixes
- Windows: the frozen build now bundles the language catalogs (the
  Language dropdown previously only offered English), and three
  macOS-only print checkboxes no longer float garbled over the
  Settings dialog.

## v3.9.1

### ✨ New
- **Norwegian (Norsk)** — complete translation (1,203 strings + all
  parameter tooltips), in the same extensive, friendly style as the
  English and German texts.

Note: Qt's stock dialog buttons (OK/Cancel/…) remain English under
Norwegian — PyQt6 ships no Norwegian qtbase translation. All ChromIQ
text is fully translated.

## v3.9.0

ChromIQ now speaks your language. This release introduces a UI language
setting with complete German and Dutch translations.

### ✨ New
- **Language setting** (Settings → Appearance & Language). Every menu,
  button, dialog, tooltip, guide and help text is translatable; the change
  applies on the next start so nothing jumps around mid-session. Output from
  the ArgyllCMS tools in the log stays English — it comes from the tools
  themselves.
- **German (Deutsch)** — complete translation (1,203 strings + all
  parameter tooltips), written in the same extensive, friendly style as the
  English texts.
- **Dutch (Nederlands)** — complete translation, same coverage.
- Qt's standard dialog buttons (OK/Cancel/…) follow the chosen language.

### 🐞 Fixes
- Tool dialogs' main action buttons (Convert/Average/Merge/Verify) and the
  3D patch-cube statistics line are now translated.
- German: sentence-initial "Du" after the warning glyph in the print-tab
  info boxes.

### 🧰 Internals
- Per-language CI guards: catalog completeness, stale keys, placeholder
  integrity, button-length budgets and parameter-name width checks run for
  every shipped language automatically.
- `scripts/i18n_agent/new_language.py` generates a complete, self-validating
  translation brief for adding further languages.

## v3.8.19
A small reliability release that hardens the engine running the ArgyllCMS
tools behind every chart, measurement and profile build.

### 🐞 Fixes
- **Logs can no longer lose their final lines.** When a tool printed a large
  burst of output right before finishing — for example chartread's
  end-of-measurement summary — ChromIQ could stop listening before it had
  read everything, leaving the log cut off mid-summary. ChromIQ now reads
  everything the tool said before declaring the run finished.
- **Closed a rare timing window between two runs.** In the few milliseconds
  after a tool finished, starting the next operation could let leftover
  bookkeeping from the previous run interfere with the new one (its output
  silently dropped, or it reported the previous run's result). Each run is
  now tagged so leftovers from an earlier run are recognised and ignored.
- **A wrong Argyll folder is no longer hidden.** If the Argyll folder set in
  Settings doesn't actually contain a tool, ChromIQ quietly looked for it
  elsewhere on the system — and could end up running a different Argyll
  version without any indication. It still falls back, but now writes a
  clear warning to the log so a misconfigured path is visible.

### 📝 Notes
- Internal clean-up in the same engine: when a run finishes, only that run's
  own log listener is detached instead of every listener — groundwork that
  prevents a whole class of "output stopped appearing" bugs in future
  features.

## v3.8.18
A colour-fidelity release for many more printers: ChromIQ now knows how to
switch off the driver's own colour management on HP, Brother, Ricoh, Lexmark,
Samsung and Xerox printers too — and it blocks a hidden macOS colour
conversion that could silently re-render charts on some printers.

### ✨ Features
- **Driver colour management now disabled on many more brands.** When ChromIQ
  prints a chart it locks the printer driver's own "no colour adjustment"
  setting so the driver can't re-profile the chart. Until now that lookup
  reliably recognised Canon and Epson wording. After surveying nearly 3,000
  official driver files from nine manufacturers, ChromIQ now also recognises
  the equivalents used by **HP** (including DesignJet large-format and colour
  LaserJets), **Brother**, **Ricoh**, **Lexmark**, **Samsung** and **Xerox**.
  Where a driver splits the choice into several settings (some HP and Xerox
  models manage text, graphics and photos separately), ChromIQ now sets all
  of them — setting just one would leave the rest colour-managed.
- **Hidden macOS colour conversion blocked.** Some printer drivers (notably
  HP DesignJet) ship with built-in colour profiles that macOS applies to
  every print job — even when the chart carries no colour profile at all,
  and even with every visible colour option switched off. ChromIQ now sends
  Apple's own "application manages colour" instruction with every print job,
  which is the one switch that actually stops that conversion. Verified by
  rasterising charts through Apple's real print pipeline: previously-shifted
  patch colours come out bit-exact with the fix, and Canon/Epson output is
  unchanged (it was already bit-exact).

### 📝 Notes
- Old Canon models (PIXMA PRO-1/PRO-10/PRO-100, older PIXMA and G series)
  genuinely have no "no colour correction" setting in their macOS drivers —
  ChromIQ re-checked the newest 2025 driver builds. On those printers the
  driver always applies its own rendering; everything that can be locked is
  locked, but for fully colour-managed-free charts a newer model is required.
- Every modern Epson photo printer (SureColor P700/P900, P5300, P7300/P9300,
  P7500/P9500, P8500D and the XP photo line) was verified to use the same
  "No Color Adjustment" setting ChromIQ has always applied for Epson.

## v3.8.17
A print-accuracy release: a new opt-in fallback keeps charts at exactly 100%
size on macOS printers that don't speak PostScript, and ChromIQ now warns
before a borderless print silently scales the chart.

### ✨ Features
- **Exact-size PDF fallback (macOS, opt-in).** ChromIQ always sends a chart as
  PostScript first. Most home and photo printers don't understand PostScript,
  so macOS rejects it and ChromIQ resends the chart as a plain TIFF — and at
  that point macOS takes over the placement and quietly **shrinks a full-page
  chart by about 3%** to fit inside the printer's margins, ignoring every
  scaling option. The new Preferences option *Exact-size PDF fallback (ChromIQ
  printing)* resends the chart as a PDF built by ChromIQ instead, with the
  chart placed at exactly 100% scale — anything that would fall into the
  unprintable margin is simply cut off (charts keep white margins there), the
  same way Apple's ColorSync Utility prints. Colour is untouched either way:
  the PDF carries the chart untagged in the printer's own colour space, so no
  colour conversion can occur on the way to the driver — verified against both
  Canon and Epson drivers. The option only applies to ChromIQ's own printing
  pipeline, so it greys out while *Use default macOS printer dialog* is
  enabled. It ships **off by default** for this release; flip it on in
  Preferences to get exact-size prints.
- **Borderless now warns before scaling your chart.** Borderless printing
  enlarges the page a few percent so ink reaches past the paper edges — the
  driver does this and it cannot be turned off. That shifts every patch of a
  profiling chart. Printing with a borderless paper size, toggle, or page
  setup now shows a clear warning first (with Cancel as the safe default),
  and the print-settings summary explains the real consequence too.

## v3.8.16
A small feature release: see how a chart's patches are spread through colour
space, straight from the toolbar.

![ChromIQ — 3D patch distribution cube for the loaded chart](docs/v3.8.16-patch-cube.png)

### ✨ Features
- **Show patch distribution (3D), now a tool of its own.** The rotatable 3D RGB
  cube that the chart-layout editor offers is now also available directly from
  the **Tools** menu in the header. Pick *Show patch distribution (3D)* and it
  plots the patches of the chart currently loaded in the main window — every
  patch shown at its own (R, G, B) position and painted in its own colour, with
  a coverage read-out (patch count, gamut fill, and patch spacing) along the
  bottom. It's a quick way to eyeball how well a target samples the colour space
  before you print and measure it.

## v3.8.15
A bug-fix release that restores a missing recovery dialog during chart
measurement.

### 🐞 Fixes
- **Measurement now shows a recovery dialog when the instrument loses
  communication mid-strip.** Previously, when `chartread` failed a strip read
  because of a communication problem (rather than an ordinary misread), the app
  stayed silent and the measurement appeared to hang at a hidden retry prompt.
  ChromIQ now surfaces the same clear **Strip Read Failed** dialog it already
  shows for misreads — with **Retry**, **Skip Stripe** and **Save Partial &
  Quit** options — plus tailored advice to check the instrument's cable and
  connection.

## v3.8.14
A reliability-and-polish release: better crash diagnostics — prompted by a bug
report from **Knut** — plus a small visual fix to the preset setting locks
introduced in v3.8.13.

### 🛡️ Crash diagnostics
- **ChromIQ now records crashes to its own log folder.** If the app ever quits
  unexpectedly, it writes the technical details to `chromiq-crash.log` (right
  next to the normal log file), so problems that macOS doesn't always keep a
  crash report for can still be diagnosed and fixed. This came out of a rare
  close-time crash reported by **Knut**.

### 💅 Polish
- **Locked preset panels now grey out completely.** When a preset locks the
  *printtarg* options, the 8-/16-bit choice, the *Pages* field and the *Triple
  density* label grey out along with the rest of the panel — so it's
  consistently clear at a glance which settings the preset is in charge of.

## v3.8.13
A new ready-to-use **ColorMunki TC9.18 (A3+)** preset from **Pharmacist**, and —
suggested by **Knut** — the ability to safely tweak a preset's settings without
losing track of what it does.

### ✨ New built-in preset
- **TC9.18 extended greys, A3+ (ColorMunki).** A complete, ready-made 1160-patch
  target for the ColorMunki on A3+ paper, courtesy of **Pharmacist**. Pick it in
  *Create Chart → Manual → Presets* (or the ★ built-in presets menu) and print —
  no setup required.

### ✨ Edit a preset without surprises (thanks, Knut!)
- **Presets now lock the settings they own.** When you pick a preset that comes
  with a fixed set of colour patches, the *targen* options are greyed out (they no
  longer apply); ready-made charts grey out both *targen* and *printtarg*. This
  makes it obvious at a glance which settings the preset is in charge of.
- **Override checkboxes to unlock them.** A friendly checkbox above each locked
  panel lets you take control when you want to. Unlocking the **page layout**
  re-arranges the *same* patches differently (e.g. a different paper size or
  margin) — perfectly safe. Unlocking the **patch recipe** lets you build a
  different set of colours, which no longer matches the preset.
- **Clear warnings.** Each checkbox has a plain-language tooltip, and unlocking
  one pops up a short explanation — so it's always clear when a change will keep
  the preset's exact patches and when it will create a new, different chart.

## v3.8.12
Seventeen ready-to-use **TC9.18 charts for the Datacolor SpyderPrint**, courtesy
of **Knut**, plus a small accuracy fix to the patch-count estimates for the
i1Pro on the smallest photo papers.

### ✨ New built-in presets
- **TC9.18 + SpyderPrint.** Seventeen new presets in the *Create Chart →
  Manual → Presets* dropdown, each laying out the standard TC9.18 target for the
  Datacolor SpyderPrint on a common paper size — pick one and print, no layout
  tweaking required. They're grouped and sorted by paper size for quick scanning.

### 🐛 Fixes
- **More accurate patch counts on 4×6″ and 5×7″ paper (i1Pro).** The patch-
  capacity database now carries measured values for these papers at the 10 mm
  margin (and the denser −a 0.95 patch size), with and without the strip-length
  limit. Previously they fell back to a live estimate; the Create Chart tab now
  reports the exact per-sheet maximum straight away.

## v3.8.11
Bigger changes to the **Edit / create chart layout** tool: combine patch sets
from other files, see your patches as a rotatable 3D RGB cube, and shuffle the
order in one click. Thanks to **Knut** for suggesting these.

### ✨ New in the chart layout editor
- **Combine sets — *Append from file…***. Load another patch set (`.ti2`,
  `.ti1`, `.ti3`, CGATS `.txt`, or i1Profiler `.pxf` / `.pwxf`) and drop its
  colours onto the **start** or the **end** of the chart you're editing — an
  easy way to merge two targets into one. RGB patch sets only.
- **See the spread — *3D distribution…***. View the whole patch set as a
  rotatable, zoomable 3D RGB cube, each dot painted in its own colour inside a
  reference cube with the neutral (black→white) axis drawn through it. Makes
  gamut coverage and patch-density clumps obvious at a glance, with a quick
  count / gamut-fill / spacing read-out along the bottom.
- **Shuffle.** A one-click randomiser sitting next to *Update preview* mixes the
  patch order (losslessly — same patches, new order), handy for breaking up a
  structured set so each strip reads distinctly.

### ✨ Polish
- The editor's header now keeps the **patch count up to date** as you add,
  remove, or append patches.
- Friendlier, correctly-sized wording on the *Append from file…* placement
  prompt.

## v3.8.10
A new ColorMunki chart from Pharmacist, plus two measurement fixes — including
one that kept the strip highlighter aligned after reopening a project.

### 🎯 New built-in chart by Pharmacist
- **ColorMunki TC9.24 on A3.** A ready-made 940-patch TC9.24 target laid out for
  the ColorMunki on A3 joins the Create Chart presets — pick it from the Manual
  **presets** dropdown or the ⭐ built-in charts overlay and it copies straight
  into your project, no chart-generation step to run.

### 🐛 Fixes
- **The strip highlighter no longer drifts after you reopen a project.** When a
  saved project was reopened, the measure preview could fall back to a weaker
  strip-finder and misalign the highlighted strip (worst on charts whose
  description is printed down the page margin). It now always uses the chart's
  own layout data, so the highlight lands on the right strip every time.
- **Removed a harmless console warning** that appeared when the
  "Calibration complete" dialog opened.

### ✨ Polish
- **Consistent preset order.** The built-in charts now appear in the same order
  (ColorMunki, then i1Pro) in both the presets dropdown and the ⭐ overlay.

### 🙏 Thanks
- **Pharmacist** for the new A3 ColorMunki TC9.24 chart.

## v3.8.9
Two more built-in charts from Pharmacist, and a clearer message when a strip is
read out of order.

### 🎯 New built-in charts by Pharmacist
- **TC9.18 extended greys (1160 patches) — now in A4 and US Letter.** Two
  ready-made i1Pro targets join the Create Chart presets. Pick one from the
  Manual **presets** dropdown or the ⭐ built-in charts overlay and it copies
  straight into your project — no chart-generation step to run. The page size is
  now shown in **every** Pharmacist preset's name (e.g. "TC9.24 (A4)"), so the
  A4 and Letter charts are easy to tell apart at a glance.

### 🐛 Fixes
- **Clearer "use it anyway" warning when a strip is read out of order.** The
  measure-tab dialog now correctly says the reading is filed under the strip
  ChromIQ *expected*, and no longer suggests an option that could quietly write a
  reading onto the wrong strip's patches.

### 🙏 Thanks
- **Pharmacist** for the two new TC9.18 extended-greys charts.

## v3.8.8
The macOS system print dialog is the default again — and it now reliably turns
colour management off for every driver, including Canon.

### 🐛 Fixes
- **macOS print dialog no longer colour-manages the chart.** ChromIQ now
  replicates the technique dedicated tools like Print-Tool use: it declares the
  chart as already being in the printer's own colour space (so no colour
  transform is applied) and switches the driver to "no colour correction".
  Canon printers — which used to colour-correct the chart regardless — now print
  the patches in their raw colours, exactly as profiling needs.

### Changed
- **macOS uses the system print dialog by default again.** You can still pick
  paper feed, media type, and quality there, while ChromIQ handles colour-off
  for you — the dialog's "Color Matching" pane is greyed out, as expected. The
  built-in lp printing path remains available in Settings.
- The print screen's guidance was rewritten to match: it no longer asks you to
  disable colour management by hand. It does add one rule — **never click
  Cancel/Abort in the print dialog's panes; always close them with OK** (Cancel
  reverts the colour-off setting, OK keeps it).

## v3.8.7
Reliable colour-management-off for Canon (and other) printers, by making
ChromIQ's own printing the default again on macOS.

### 🐛 Fixes
- **Canon charts no longer print colour-managed.** When it prints the chart,
  ChromIQ now sends the driver's own "No Color Correction" option (and the
  matching option for other brands) straight to the printer, so the patches come
  out in the printer's raw colours — exactly what profiling needs.
- **macOS uses ChromIQ's built-in printing again by default.** It turns colour
  management off for you with no extra steps. Testing showed that some drivers —
  Canon in particular — ignore the macOS print dialog's colour-off request and
  colour-correct the chart anyway, so the built-in path is the dependable one.

### Changed
- The macOS system print dialog is still available as an option in Settings, but
  it now clearly explains that **you must switch the driver's colour management
  off yourself** in that dialog, with step-by-step notes for each brand. If in
  doubt, leave the option off and use ChromIQ's built-in printing.

## v3.8.6
A printing fix for the macOS print dialog: some printer drivers were quietly
colour-correcting the test chart even with colour management turned off.

### 🐛 Fixes
- **Stopped some printer drivers from colour-managing the test chart** when you
  print through the macOS print dialog. On recent macOS, certain drivers (Canon
  in particular) kept applying their own colour engine, so the chart printed as
  if a profile had already been baked in — which makes it useless for building
  an accurate profile. ChromIQ now tells the print system the chart is already
  in the printer's own colour space, so the driver leaves the patches exactly as
  sent.
- **The print dialog's "Color Matching" pane now locks and greys out** along
  with the driver's other colour controls, so there's no stray setting left to
  switch on by mistake. After every print ChromIQ still reads the job back to
  confirm colour management really stayed off.

## v3.8.5
A quicker way to reach the ready-made charts, plus a few small refinements.

### ⭐ One-click access to the built-in charts
- Create Chart now has a **star button** right next to the Guided / Manual
  switch. Click it for a tidy little menu of the built-in, ready-to-print
  charts, **grouped by the instrument** they're made for (i1Pro or ColorMunki).
  Pick one, give it a name, and the finished chart drops straight in — there's
  nothing to set up and nothing to get wrong.
- It's the fastest way to a known-good target, and ideal when you just want a
  reliable chart without thinking about the details. The very same presets also
  still live at the bottom of Manual mode's **Presets** dropdown, so nothing has
  moved — this is simply a shortcut to them.

### ✨ Polish
- The Create Chart help (ⓘ) now walks you through all three ways to make a
  chart — built-in presets, Guided, and Manual — so it's clearer which to reach
  for.
- The "no preset selected" entry in the manual-mode **Presets** dropdowns now
  reads **"none"** instead of "Default", which better reflects what it does.
- Fixed a small visual glitch where a row in the pop-up menus (the new presets
  menu and the header Tools menu) could stay highlighted while the cursor was
  just outside the menu to the left or right.

### 🙏 Thanks
- To **Knut** for suggesting the quick-access button for the built-in charts.

## v3.8.4
A small cosmetic refresh to the bundled charts from Pharmacist.

### 🎨 Chart appearance
- The four built-in **Pharmacist** charts have had a light visual tidy-up
  around the page margins and title band, so the printed sheets look a touch
  cleaner. The colour patches themselves are **completely untouched** — every
  patch value is byte-for-byte identical to the previous release, so your
  measurement and profiling results are exactly the same.
- With thanks, as always, to **Pharmacist** for designing these targets for
  the community. 🙏

## v3.8.3
A refreshed set of ready-to-print charts from Pharmacist, plus a small
polish to the Measure tab.

### 🎯 New built-in charts by Pharmacist
- The **Create Chart → Presets** dropdown ships a brand-new, curated line-up
  of four ready-made targets, all kindly built and tuned by **Pharmacist**:
  - **i1Pro TC9.24** — a high-quality 924-patch target for the i1 Pro family.
  - **i1Pro 1110 ABW-optimized** — an 1110-patch target tuned for advanced
    black-and-white / neutral work on the i1 Pro.
  - **ColorMunki TC3.00** — a compact 300-patch target for the ColorMunki /
    i1Studio.
  - **ColorMunki 702 ABW-optimized** — a 702-patch ABW-tuned target for the
    ColorMunki / i1Studio.
- Each is a **complete, pre-made chart**: picking one simply asks for a name
  and drops the finished files into your working folder — no chart generation
  step to wait on. The previous built-in presets have been retired in favour
  of this set.
- **Heartfelt thanks to Pharmacist** for designing, measuring and validating
  these targets for the community. 🙏

### 🔎 Measure tab
- The scan arrow that points at the strip you're about to read now sits at a
  consistent height across every chart. On a few targets a long caption
  printed down the page margin used to nudge the arrow lower than on the
  others; it now lines up the same way everywhere.

## v3.8.2
A small, focused addition for anyone who likes to keep their measurement
files tidy.

### 🔬 Leaner measurement files
- The Measure tab's **Manual** mode gains a new option,
  **"Don't save spectral data (-n)"**. Switch it on and the chart reader
  stores only the colour values (XYZ, or L\*a\*b\*) in the `.ti3` file and
  leaves out the per-wavelength spectrum — roughly three dozen extra numbers
  per patch. The file becomes much shorter and far easier to review by eye.
- Your profile is unaffected: building the ICC only needs the colour values,
  which are always kept, so a profile made with this option on is identical
  to one made with it off. Leave it off (the default) if you rely on the
  spectrum later — for optical-brightener (FWA) compensation when building
  the profile, or to re-derive values under a different illuminant. A
  detailed ⓘ explainer next to the option spells out the trade-offs.

## v3.8.1
A focused fix for the chart-layout editor's patch highlighter, plus a
quality-of-life touch when reopening charts.

### 🎯 Chart editor highlighting
- Selecting patches now highlights them **exactly on the patch** in the
  preview. The highlight fills the swatch instead of leaving a rim of the
  patch's own colour, and it no longer floats up into the white margin above
  the chart. This holds even when the first patch is white and on charts
  where the preview render and its internal analysis twin don't line up.

### 💾 Reopening charts
- Charts now remember the printtarg layout settings they were made with
  (patch/spacer scale, margins, density, bit depth, …) in the project's
  `meta.json`, so reopening one in the editor restores the panel exactly as
  you left it. Older projects keep working unchanged.

## v3.8.0
**ChromIQ is out of beta.** This is the first stable release of the 3.8 line,
and it's a big one. Since 3.7 it has grown a whole toolbox of stand-alone
utilities, an interactive chart editor, two optional ways to squeeze more
accuracy out of your profiles, and a tidier, more predictable way of storing
your work on disk — plus a long list of smaller fixes and polish.

If you followed the betas you've met most of this already; here is the complete
picture in one place, grouped by what you actually do with it. Everything new is
either on by sensible defaults or clearly opt-in, so upgrading shouldn't change
your day-to-day workflow unless you want it to.

### 🧰 A new Tools menu
A toolbox button now sits in the header next to Preferences. It opens a small
menu of stand-alone utilities you can use any time — no project setup required.
Each one has a plain-language explainer (ⓘ), its own file pickers, and a
destination + name for what it produces.

- **Average measurements** — combine repeated reads of the same chart into one
  averaged `.ti3` to cancel out instrument noise (mean, or median with 3+ reads).
- **Merge measurements** — join the patches of several `.ti3` files into one
  bigger set, giving the profiler more data to work with.
- **Verify against reference** — check how closely a print matches a set of
  expected colour values (ΔE per patch and overall) *without* building a profile.
  It now **explains** its numbers (whether a high score is really a paper/black-
  point limit or a true colour shift), can **leave out colours your paper can't
  physically print**, and can draw an interactive **3D difference map** of where
  each colour landed versus where it should have.
- **Verify a profile (independent check)** — the honest test: grade a finished
  profile against a freshly measured chart it was *not* built from, in plain
  language. (A profile always looks good against its own training patches.)
- **Convert TI1 → i1Profiler** — export an Argyll chart as i1Profiler patch sets
  (`.txt` / `.pxf`) so an i1iSis or other i1Profiler-driven instrument can
  measure it. It can now also write a ready-to-open i1Profiler **workflow file
  (`.pwxf`)** with the instrument, paper and layout already configured, across
  all twelve i1Profiler device types, with an optional patch-size override.
- **Convert i1Profiler → TI3** — bring an i1Profiler measurement export back into
  ChromIQ to build a profile from it.
- **Convert i1Profiler → TI1** — the reverse of the export, reading i1Profiler
  charts (including `.pwxf` workflows) back into an Argyll `.ti1`.

### ✏️ Interactive chart-layout editor
**Tools → "Edit / create chart layout"** opens a full editor where you can load
any RGB chart (or build one from scratch), drag patches into a new order,
recolour individual patches and spacers, paste in your own colour list, choose
custom paper sizes, and export the colour list as a text file. It always
regenerates the chart through Argyll's printtarg, so the data file and the
printed image can never drift out of sync. Well-mixed charts are **tagged as
randomised automatically on save** so they can be measured in either direction;
structured layouts are left alone unless you deliberately override.

### 🔁 Two optional ways to push accuracy further (both off by default)
- **ChromIQ-style refinement (two-pass profiling).** Build a first profile, then
  create a second chart that points at it as a "pre-conditioning" profile;
  ChromIQ keeps the first run's measurements and combines both sets at build
  time for a more accurate result. Your original measurement file is never
  altered — the combined data goes into separate `merged` files.
- **Measure-and-average.** Read the same printed chart several times and average
  the measurements (including full spectral data) to reduce instrument noise.
  The choice is offered right in the "All stripes read" window. With it off,
  measuring behaves exactly as in 3.7.
- _Thanks to **Alan Goldhammer** for suggesting averaging and the approach behind
  it._

### 🎯 Create Chart
- **Ready-made targets** — built-in i1Pro **TC9.24** (A4 + US Letter) and a
  refreshed **TC9.18** preset that drop in a complete chart with no targen /
  printtarg step. _(See the note on presets below.)_
- **Attach your own patch set to a saved preset** so selecting it later rebuilds
  that exact chart, and the `.ti1` travels with the preset when you share it.
- **Load i1Profiler files** (`.pxf` / `.cgats` / `.txt`) directly as a patch set.
- **More expert targen options in Manual mode** — total ink limit, OFPS
  adaptation, cube interior/surface steps, BCC steps and a patch-distribution
  selector, each behind its own opt-in so the default command line is unchanged.
  These now save correctly in presets and "Default" fully resets every field.
- **Rename-on-generate** — generating under a new name offers to rename the
  existing project properly (files and manifest, not just the folder), keep both,
  or replace.

### 📏 Measuring
- **Strip recognition is now a single dropdown** (Argyll default / bidirectional
  disabled / bidirectional forced) in both Guided and Manual modes, with **Auto**
  picking the right setting from your instrument (i1 Pro reads either direction,
  ColorMunki one direction).
- **Randomisation-aware bidirectional reading** — forcing bidirectional on a
  fixed-order chart now warns you first, because that combination can misread
  strips and bake a colour cast into the profile.
- **The bidirectional preview arrow is now honest** — the second arrow appears
  only when the read truly is bidirectional, so fixed-order charts show a single
  arrow.

### 🗂️ Reorganised project folders
Every project now uses a clear **per-run folder layout** under
`~/ChromIQ/<project>/`, with a `Where are my files.txt` map at its root, shared
`cal/` and `exports/` folders, and one folder per profile build under `runs/`.
Chart files now carry your **project's name** (so the printed sheet, the saved
files, and the installed `.icc` are all self-identifying), and a whole class of
"which measurement went where" bugs is now impossible by construction.

> **Upgrading from a 3.8 beta?** Projects created by beta.10 or earlier used the
> old flat layout and won't be picked up automatically. They're not lost — just
> open one of their files (Load .ti2 / .ti3) and ChromIQ rebuilds the project in
> the new layout, bringing every related file along. New charts use the new
> layout automatically.

### 🖨️ Printing (macOS)
- The **macOS print dialog is now the default on macOS** (you can still switch
  back to ChromIQ's built-in colour-managed pipeline in Preferences). When it's
  selected, the "Confirm print settings before printing" option greys out, since
  the system dialog is itself the confirmation step.

### 💅 Polish & fixes
- **Spin boxes** look right everywhere now — the up/down buttons tile cleanly
  with a single divider and the focus ring stays a clean rounded rectangle, in
  both light and dark mode.
- **Disabled options actually look disabled** — ticked checkboxes grey out with
  their group instead of keeping a bright fill.
- **Friendlier dark/light surfaces** in the tool dialogs (status and paste boxes,
  file lists, combo bodies) so input areas no longer read as a near-black void.
- **Plain-language ⓘ help popups** across the chart editor and every Tools dialog.
- **Cancelling Preferences is instant**, and a startup font warning is gone.
- **Windows fixes** — a project-create crash, a second-chart-read hang, and the
  Tools popup's stray border/shadow are all resolved.

### 📋 A note on built-in presets
The ready-made chart presets (the i1Pro **TC9.24** targets, and friends) are
getting one more **accuracy review** before they're switched on by default, so
they're temporarily held back in this release. They'll be enabled in a follow-up
update soon — everything else above is ready to use today.

### 🙏 Thanks
To **Alan Goldhammer**, **Pharmacist**, and everyone who tested the 3.8 betas and
sent feedback — this release is shaped by it.

## v3.8.0-beta.31
**Verify is far more useful, plus a second, more honest way to check a profile.**
The "Verify against reference" tool used to hand back a bare ΔE number that
could look alarmingly high for reasons that aren't your profile's fault (for
example checking glossy-targeted values against a matte print). It now explains
its results, can leave out colours your paper physically can't reproduce, and
can draw the differences in 3D. There's also a brand-new tool for checking a
finished profile against a fresh chart it has never seen.

### Added
- **New tool: "Verify a profile (independent check)."** Runs Argyll's profcheck
  on a profile plus a freshly measured chart it was *not* built from, then grades
  the result in plain language. Checking a profile against its own training
  patches almost always looks good — testing it on a different chart is the
  honest measure of accuracy. (Tools menu.)
- **3D difference map in "Verify against reference."** Tick *Create a 3D
  difference map* and, when the check finishes, an interactive 3D view opens
  drawing a line from each target colour to where your print actually landed —
  green dots are the reference, red dots your measurement. Drag to rotate, scroll
  to zoom. It reuses the gamut viewer's renderer and follows the light/dark
  theme.

### Changed
- **"Verify against reference" now explains its numbers.** Instead of just an
  average and peak ΔE, it tells you whether the difference is mostly *lightness*
  (a black-point / paper limit — expected when a reference made for one paper is
  checked on another) or a real *colour* shift, and reports the best-90% figure
  and a plain-language grade.
- **Skip colours your paper can't print.** Optionally point the verify tool at
  your profile (.icc): reference colours outside that paper's gamut — most often
  the deepest shadows — are left out of the score (it tells you how many), so
  unreachable colours stop dominating the result.
- **Consistent control highlights.** Checkboxes, focused text fields and combo
  boxes in the tool dialogs now use the same neutral highlight colour as the
  Settings window, in both light and dark mode.

### Fixed
- **Dark mode:** the status-message box and paste boxes in the tool dialogs now
  use the same background as the text-entry fields, instead of a darker shade
  that read as a near-black void.
- The Tools menu pop-up is a little wider so longer entries are no longer
  clipped.

## v3.8.0-beta.30
**The Measure tab's bidirectional strip indicator now matches what actually
happens during the read.** The preview shows a second (bottom) arrow on the
active strip to signal that it can be scanned in either direction — but on a
fixed-order chart left at Argyll's default setting, the chart is in fact read in
one direction only, so the second arrow was misleading.

### Fixed
- **Bidirectional preview arrow follows the effective read direction.** The
  double arrow now appears only when the read is truly bidirectional: always
  when "Bidirectional forced" is set, never when it is disabled, and — at the
  Argyll-default setting — only on a randomised chart (where chartread reads
  both directions). Fixed-order charts at the default setting now correctly
  show a single arrow.

## v3.8.0-beta.29
**Readability fix for the Average / Merge tool dialogs in dark mode.** The file
list in both dialogs used a near-black background that made it hard to tell the
list area apart from the surrounding window.

### Fixed
- The measurement-file lists in **Average measurements** and **Merge
  measurements** now use the same background as the text-entry fields, so the
  list reads as an editable area instead of a dark void. Selected rows are
  highlighted in the accent colour. (Dark mode only.)

## v3.8.0-beta.28
**Randomised tagging in the chart editor is now automatic.** A well-mixed chart
is tagged as randomised for you on save (so it can be measured bidirectionally),
and the manual checkbox is demoted to a "force" override that only matters for
structured layouts the safety check considers risky.

### Changed
- **Chart layout editor — auto-tag on save.** When you save, ChromIQ analyses
  the layout: a well-mixed chart is tagged as randomised automatically with no
  prompt; a structured one is left untagged unless you override it.
- The old "Tag as randomised" checkbox is renamed **"Force 'randomised' tag"**
  and is **enabled only while the current layout is judged unsafe** (greyed out
  otherwise, since safe charts are tagged anyway). Its state refreshes live with
  each preview.
- Forcing the tag on an unsafe layout now shows an extensive, plain-language
  risk warning with a **"Don't show this again"** option.
- The safety check looks at each strip individually — a single direction-
  ambiguous strip or a single near-identical strip pair flags the whole chart,
  rather than being averaged away.

### Notes
- The check is conservative (uncertain → treated as unsafe); you can always
  Force the tag from the warning. Small charts with short strips have less
  margin and may be flagged more readily.

## v3.8.0-beta.27
**Randomisation-aware bidirectional measuring, and plain-language help across
the tools.** The chart layout editor can now mark a chart as randomised so it
can be measured bidirectionally — but only when its patch order is actually
well mixed, checked automatically. The Measure tab warns if you force
bidirectional reading on a fixed-order chart, and every editor/tool screen
gained friendly ⓘ help popups.

### Added
- **Chart layout editor — "Tag as randomised for measurement"** (on by
  default). When you save, ChromIQ can mark the chart's `.ti2` as randomised so
  chartread will auto-recognise strips and read them in either direction. The
  patches on paper don't move — only a label inside the file changes. Because
  this is only safe when the patch order is well mixed, the editor analyses the
  saved layout first: a well-mixed chart is tagged silently, while a structured
  one (a smooth ramp or a regular RGB grid, especially on big charts) raises a
  warning so you can leave it untagged or tag it anyway.
- **Measure tab — fixed-order + forced-bidirectional warning.** Starting a
  measurement with strip recognition forced to bidirectional (`-b`) on a
  non-randomised chart now shows an explanatory warning (with "Don't show this
  again"), since that combination can make chartread misread strips and build a
  colour-cast profile.
- **ⓘ help popups on the tools.** The chart layout editor (overview, patch
  grid, new-chart, and the tag option) and all six Tools dialogs (Average,
  Merge, TI1 → i1Profiler, i1Profiler → TI3, i1Profiler → TI1, Verify) gained
  friendly, plain-language help popups — magenta in the editor, and the
  light/dark indicator accent in the Tools dialogs.

### Changed
- **Measure tab — ColorMunki now uses Argyll's default** under Auto, instead of
  forcing `-B`. ArgyllCMS's default already reads the ColorMunki correctly, so
  Auto no longer disables bidirectional for it; the i1 Pro family still
  auto-forces `-b`. The "Default" item in the Strip recognition menu is renamed
  **Argyll default**, and the guided menu is shown full-size (non-compact).
- Reworked the Strip recognition tooltip so "Argyll default" is described
  accurately (it depends only on whether the chart is randomised) and is clearly
  distinguished from ChromIQ's "Auto".

### Notes
- The randomisation safety check biases conservative: an uncertain chart is
  reported as structured, and you can always tag it anyway from the warning.

## v3.8.0-beta.26
**Strip recognition is now a single dropdown in the Measure tab.** The pair of
bidirectional checkboxes added in beta.25 (`-B` / `-b`) is replaced by one
**Strip recognition** menu — *Default*, *Bidirectional disabled* (`-B`), or
*Bidirectional forced* (`-b`) — in both Guided and Manual modes, with the
**Auto** toggle beside it as before. A single menu makes the choice clearer and
removes the "two checkboxes that can't both be on" awkwardness.

### Changed
- Measure tab (Guided + Manual): the **Disable** / **Force** bidirectional
  checkboxes are now one **Strip recognition** dropdown. While **Auto** is on
  the menu is locked but still shows the option Auto picked from the chart's
  instrument (i1 Pro → forced, ColorMunki → disabled, others → default); turn
  Auto off to choose by hand.
- Rewrote the strip-recognition and Auto tooltips to be longer and plainer,
  explaining what strip direction means and when to pick each option, in
  wider dialogs sized to fit the text.

### Notes
- Saved defaults and presets from beta.25 (and the older single-`-B` scheme)
  migrate automatically to the new dropdown value — no reconfiguration needed.

## v3.8.0-beta.25
**Force bidirectional strip reading (`-b`) in the Measure tab.** chartread can
now be told to accept a strip scanned in either direction even on fixed-order
charts. Previously chartread only auto-detected strip direction on *randomised*
charts; on a fixed-order layout (e.g. printtarg `-r`) it read one direction
only and rejected strips scanned backwards. The new option is the counterpart
to "Disable bidirectional" (`-B`), and the two are mutually exclusive.

### Added
- Measure tab — both **Guided** and **Manual** modes: a **Force bidirectional
  strip recognition (`-b`)** checkbox, saveable as a preset and as your
  default.
- The existing **Auto** toggle now drives both `-B` and `-b` from the chart's
  instrument: the i1 Pro family (reads either direction) force-enables `-b`,
  the ColorMunki (one direction only) uses `-B`, and SpectroScan / unknown
  instruments use neither. While Auto is on, both boxes are locked and show
  the chosen setting. The instrument log line now states the direction, e.g.
  "reading both directions (forced, `-b`)".

### Notes
- `-b` and `-B` are mutually exclusive. Turning **Auto** off lets you set
  either by hand, and ticking one clears the other.

## v3.8.0-beta.24
**New Tools utility: "Verify against reference".** Check how closely a printed
chart matches a set of expected colour values — per-patch and average ΔE —
*without* building a profile. Print your evaluation target through a candidate
profile, measure it, and compare the measurement against the values it should
have hit (e.g. a profile-evaluation target someone shared with you). Under the
hood this runs ArgyllCMS's `colverify`.

### Added
- Tools → **Verify against reference**. Paste (or load) the expected values —
  CIE L\*a\*b\* or XYZ, one patch per line in chart order — pick your measured
  `.ti3`, and optionally the chart's `.ti1`/`.ti2` so the patch count is
  cross-checked. ChromIQ builds a reference file whose patch IDs line up with
  your measurement and reports average / peak ΔE plus a per-patch list.
- ΔE formula selectable (CIEDE2000, CIE94, CIE76) and an option to list the
  worst patches first.

### Notes
- Patches are matched by `SAMPLE_ID`, so the measured chart and the expected
  values must describe the same patch set in the same order. The optional
  chart cross-check catches the most common mismatch (wrong patch count).

## v3.8.0-beta.23
**New i1Profiler workflow (.pwxf) export, plus .pwxf import.** "Convert TI1 →
i1Profiler" (Tools) can now also write an i1Profiler *workflow* file alongside
the .pxf/.txt patch set — open it in i1Profiler and the instrument, paper and
patch layout are already set up, so you don't have to configure them by hand.
It covers all twelve i1Profiler device entries, with an optional per-device
patch-size override. "Convert i1Profiler → TI1" now reads .pwxf files too, so
workflows round-trip both ways. The format was reverse-engineered from real
i1Profiler exports (see `docs/dev_pxwf_format.md`).

### Added
- Tools → Convert TI1 → i1Profiler: optional **"Also write an i1Profiler
  workflow file (.pwxf)"** (RGB targets only). Pick the instrument — i1Pro 2/3,
  i1Pro 3 PLUS / PLUS M3, i1iO 2/3, i1iO 3 PLUS / PLUS M3, i1iSis /2/XL/2 XL —
  scan mode and paper; i1Profiler opens the file with all of it preconfigured.
- Optional **"Set patch size"** with per-device limits (e.g. i1Pro 6–25 ×
  6–12 mm, the PLUS/M3 devices 16–40 mm), encoded the way i1Profiler stores
  the size so the requested patch dimensions are honoured. Left unticked,
  i1Profiler chooses its own sensible size (the default).
- Tools → Convert i1Profiler → TI1 now also accepts **.pwxf** workflow files
  (reading the patch list out of them), in addition to .pxf / .cgats / .txt.

### Notes
- i1Profiler owns the chart's column/row layout and the i1iSis lead-in
  ("header length") — it recomputes them on load — so ChromIQ supplies the
  patch set plus device/paper/size and lets i1Profiler lay the chart out.

## v3.8.0-beta.22
**TI2 editor: magenta selection/overlay polish and a fix for the drag-reorder
preview that wasn't refreshing.** Drag-reordering patches on the left now
correctly triggers the debounced auto-preview, the yellow selection wash on
the TIFF preview (spacer + patch overlays, marquee rubber-band) is now a
softer magenta in the accent family, and the left-column selection fill is a
toned-down translucent magenta so the swatches stay easy to read.

### Fixed
- TI2 editor: dragging patches in the grid now updates the preview. The
  reorder handler was wired only to `rowsMoved`, which Qt only emits when
  the model implements `moveRows()`; QListWidget's default InternalMove path
  uses remove + insert, so the auto-preview never queued. The handler is
  now also connected to `rowsRemoved`, which fires on both paths. Removing
  patches via the Remove button benefits from the same auto-refresh.

### Changed
- TI2 editor: TIFF preview overlay (spacer outline, patch highlight, marquee
  rubber-band) repainted in `SPEC_MAGENTA` instead of yellow, matching the
  rest of the editor's magenta accent.
- TI2 editor: left-column patch selection fill is now a translucent magenta
  (~43% alpha) instead of the system palette highlight — sits in the
  wine-magenta family of the info boxes without overpowering the swatches.
- TI2 editor: the per-spacer paint hint label now reads "Selected = magenta
  outline" (was "yellow outline").

## v3.8.0-beta.21
**Chart-layout editor polish + consistent non-native file pickers across
all Tools-menu utilities.** The TI2 editor's right panel breathes a bit
wider, gains custom paper sizes, exports its colour list as a paste-able
text file, and saves through a single dialog instead of a two-step
folder-then-name flow. The five Tools-menu dialogs now use ChromIQ's own
file pickers (with sidebar shortcuts + extension filtering) instead of
the OS-native ones.

### Added
- **Custom paper sizes in the chart-layout editor.** Both the New chart
  dialog and the right-panel `printtarg` section gain a "Custom" entry;
  selecting it reveals W / H (mm) spinboxes and emits printtarg's
  `WWWxHHH` form. Loaded charts whose paper code is `WWWxHHH` fall back
  to "Custom" + seed the W / H spinboxes from `paper_mm`. Matches the
  Create Chart tab's custom-paper UX.
- **Export colours… button** next to Save As in the chart-layout editor.
  Saves the current patch program as a text file (hex `#rrggbb` or
  decimal `R G B`, one per line, in chart order). The file round-trips
  through the New chart dialog's "Paste colour values" mode, so a chart's
  colours can be exported, edited, and rebuilt as a fresh chart.
- **`save_file_dialog` + `open_files_dialog` helpers** in `ui/widgets.py`
  to round out the file-dialog API. Both apply `DontUseNativeDialog`
  and pick up the same sidebar shortcuts / extension-filter behaviour
  as the existing `open_file_dialog` / `open_dir_dialog`.

### Changed
- **Spacer-mode picker is now a mutex-checkbox group** (Coloured / B&W /
  None) in both the New chart dialog and the right-panel `printtarg`
  section. Selecting one clears the others; selecting none falls through
  to printtarg's coloured default. "None" disables the Spacer scale
  (`-A`) field since there are no spacers to scale.
- **Save As uses a single save dialog** in the chart-layout editor (the
  typed filename becomes both the chart folder name and the basename
  of the files written inside). The old folder-pick → name-prompt
  two-step is gone.
- **Tools-menu file dialogs are now non-native.** `Average measurements`,
  `Merge measurements`, `TI1 → i1Profiler`, `i1Profiler → TI3` and
  `i1Profiler → TI1` (and the shared destination-row browse button) now
  go through `open_file_dialog` / `open_files_dialog` / `open_dir_dialog`,
  matching the rest of the app's pickers — same sidebar, same
  extension-filter behaviour, same look in light and dark mode.
- **Wider editor window + right panel** so the paper combo's full label
  ("A4 (210 × 297 mm) Portrait") and per-locale spinbox values no longer
  clip on first open. Default size is now 1280×820 (was 1180×760), right
  panel 360 px (was 320 px).
- **Magenta accent throughout the chart-layout editor** — checked
  checkboxes / radios, focused inputs, and the swatch-size slider all
  use the magenta accent, scoped to the dialog so the app-wide cyan
  accent stays untouched. The slider also picks up the Gamut viewer's
  slim-groove recipe (theme-aware groove colour).

## v3.8.0-beta.20
**Full printtarg-option parity in the chart-layout editor's right panel.**
Instrument + paper are now editable on an already-loaded chart, with the
same instrument-conditional show/hide rules and mutual-exclusion logic
as the New chart dialog.

### Added
- **Instrument + Paper combos in the right-panel `printtarg` section.**
  Switching instrument updates `spec.instrument_flag`, flips the visibility
  of the i1-only / ColorMunki-only options, and re-renders. Switching
  paper updates `spec.paper_flag` + `paper_mm` and re-renders. The editor
  now reaches full option parity with the New chart dialog.

### Fixed
- **Instrument-conditional checkboxes (-L / -P / double / triple density)
  now show the correct subset.** They previously all rendered visible at
  dialog startup because the conditional refresh only ran on chart load;
  the initial pass now happens at construction, and the combo handler
  flips visibility even before a chart is loaded.

## v3.8.0-beta.19
**Polish pass over the chart-layout editor (Tools → Edit / create chart
layout).** Every TI2 the editor produces now correctly preserves and
restores its source palette, the patch grid mirrors the printed chart's
spatial order, and the preview's selection overlays land on the right
pixels on charts of any size (verified at 100 / 500 / 1 000 / 3 000
patches across multi-page renders).

### Added
- **Highlight selected patches in the preview.** New checkbox in the
  Patches section: when on, selecting patches on the left highlights them
  on the rendered chart, and clicking / marquee-dragging on the chart
  selects them in the swatch grid. Bidirectional and works at any zoom.
- **Standard selection semantics** in both Patches and Spacers modes:
  plain click / marquee *replaces* the selection (clicking an empty area
  clears it); Shift adds; Alt subtracts — matching the Finder convention
  the rest of the app uses.
- **Dedicated `printtarg` section in the right panel.** Every printtarg
  option exposed in the New chart dialog (spacer mode, patch / spacer
  scale, margin, DPI, bit depth, `-L`, `-P`, double / triple density) is
  now live-editable on an already-loaded chart, behind the same
  instrument-conditional visibility rules.
- **Triple-density preset for ColorMunki + rig.** Mutually exclusive with
  double-density. Renders the chart with the i1Pro strip layout (printtarg
  `-ii1` at `-a 1.3 / -m 5 / -P / -L`) then rewrites `TARGET_INSTRUMENT`
  in the produced `.ti2` back to ColorMunki so chartread still drives the
  meter you actually own — same recipe Create Chart uses.
- **Margin / DPI / Bit-depth knobs** on the New chart dialog so the editor
  reaches printtarg parity with the Create Chart tab.
- **Scrollable controls panel** with a soft top / bottom fade so the
  printtarg + Patches + Spacers + What-a-mess block never falls off the
  bottom on smaller window heights.
- **White-bordered preview** matching the main app's TiffPreview look —
  the chart sits inside a 15 px white margin painted directly onto the
  canvas, so it reads as paper-on-table instead of TIFF-on-dialog.

### Changed
- **Loaded charts now open in the *visual* order they were printed in,**
  not in the `.ti2`'s internal `SAMPLE_ID` order. Charts generated with
  randomisation finally show the grid the same way as the preview.
- **Spacer palette persists across load.** The editor reads
  `DENSITY_EXTREME_VALUES` from the chart's sibling `.ti1` (if present)
  and seeds the palette buttons from it, so reloading a chart you saved
  with a custom palette renders the way you left it — no more snapping
  back to printtarg's W/CMY/K defaults.
- **Patch-highlight geometry rewritten** to combine the `.ti2`'s
  authoritative strip / step counts with the chart's patch-block bbox.
  Verified at 100 % hit-rate on 100 / 200 / 500 / 1 000 / 2 000 / 3 000
  patch charts across multi-page renders (was ~22 – 45 % on the previous
  uniform-divide approach).
- **Drag drop indicator** now snaps to the gap midpoint between two
  patches instead of flickering between "after A" and "before B" — same
  reorder result, calmer visual.
- **Compact spinboxes + comboboxes** throughout the editor — every input
  is now a `NoScroll*` widget tagged `compact_input`, picking up the
  shorter / smaller-arrow rules the app stylesheets already define.
  Fixes the off-white background in light mode and the oversized native
  arrows on macOS.

### Fixed
- **Preview no longer zooms itself out of existence.** A QSS border on
  the preview `QLabel` was inflating its `sizeHint`, kicking off a
  resize → rescale → `setPixmap` → resize loop that grew the image every
  refresh. Border moved off the label and onto a properly-framed
  canvas.

## v3.8.0-beta.18
**New Tools utility: an interactive chart-layout editor.** Open it from
Tools → "Edit / create chart layout" to load any RGB `.ti2` (or start one
from scratch), drag-arrange the patches, recolour individual patches and
spacers, and save a fresh, valid `.ti2` + page TIFF(s).

### Added
- **Tools → "Edit / create chart layout".** A standalone editor that
  regenerates the chart through printtarg every time, so the `.ti2` and the
  printed TIFF stay coupled by construction — no chance of measurement data
  going out of sync with what's on paper.
- **Two source modes for new charts.** *Blank canvas* lets you build a
  target by hand with the colour picker; *Seed from targen* fills the grid
  with an OFPS-optimised patch set you can then re-arrange and recolour.
- **Paste hex / RGB colour values** to populate a new chart from anything
  you have in a text file — `#RRGGBB`, `RRGGBB`, decimal triples on `0..1`,
  `0..100`, `0..255` or `0..65535` are all auto-detected.
- **Full printtarg layout options on the new-chart dialog** — instrument,
  paper (the same 15-entry list the Create Chart tab uses, with all
  orientations), spacer mode (coloured / B&W / none), patch scale (`-a`),
  spacer scale (`-A`), suppress left clip border (`-L`), don't limit strip
  length (`-P`), double density / hex patches (`-h`), and the basename
  printtarg stamps along the right margin.
- **Patch grid with drag-reorder + multi-select.** Drag-and-drop, plus a
  swatch-size slider, Add / Remove buttons, explicit *First / Up / Down /
  Last* buttons, and `Alt + arrow` / `F` / `L` keyboard shortcuts.
- **Per-patch colour editing.** Set a single patch, set a multi-selection
  at once, or apply a `Darken 10 %` / `Lighten 10 %` transform across the
  selection. Re-rendered through printtarg, so the `.ti2` device values and
  the TIFF pixels are still in lock-step.
- **Native spacer palette editor.** Edit any of the six middle entries of
  the spacer palette (the one printtarg picks contrast spacers from); the
  defaults at index 0/7 stay white/black because printtarg also uses them
  as the media / mark references.
- **Per-spacer paint with marquee.** Click coloured spacer bands in the
  preview to select them — selected ones get a translucent yellow fill +
  outline — drag a marquee for many at once, hold `Alt` to subtract from
  the selection, then pick a colour and paint just those spacers. Paint is
  applied per page on multi-page charts.
- **Auto-updating preview.** The initial preview renders automatically
  when you load or create a chart; subsequent edits trigger a debounced
  re-render so you can keep tweaking without clicking "Update preview"
  each time.
- **Multi-page preview navigation** with the strip count read from the
  regenerated `.ti2`'s `PASSES_IN_STRIPS2`, so the layout editor handles
  charts that span more than one printed page.
- **"What a mess!" flourish** on the right panel, matching the Print
  Chart tab's "Feed the beast" block (Georgia headline with the magenta
  accent, Menlo subtext, 5-colour bar).

### Notes for adventurous editors
- Re-colouring a patch changes its device value and therefore what your
  profile characterises — it stays a *valid* chart by construction, but
  the profile reflects whatever you've designed. Keeping a good gamut
  spread is on you.
- printtarg quantises device values to the output bit depth (8-bit by
  default), so a hand-entered `75.0` will round-trip to `74.9` in the
  saved `.ti2`. The integrity check compares on the 8-bit grid, so this
  is treated as a no-op rather than a data loss.

## v3.8.0-beta.17
**Create Chart Manual mode: the new expert targen options now save, and
"Default" fully resets.**

### Fixed
- **Manual-mode expert targen options can now be saved as defaults and in
  presets.** The new rows (Total Ink Limit `-l`, OFPS Adaptation `-A`, Cube
  Interior/Surface Steps `-m`/`-M`, BCC Steps `-b`, and the Patch
  Distribution selector) keep their enable-checkbox separate from their value,
  so Save-as-Defaults and presets recorded the value but never whether the
  flag was armed — on reload the value returned but the flag was dropped. The
  checkbox state is now persisted and restored alongside the value.
- **Selecting "Default" in the Manual presets dropdown now resets every
  parameter.** Rows that weren't part of your saved defaults — e.g. options
  added in a later version, or a value you changed but never saved — were
  left untouched instead of reverting. They now return to their factory
  default. (This also repairs single-letter flags like `-f`/`-g`, which the
  "Default" entry was reading from the wrong settings key and so never
  restored.)
**More targen control in Manual mode, healthier i1Profiler round-trips,
and a UI polish on the Tools button.**

### Added
- **Manual mode exposes the targen flags it was missing**: `-l` Total Ink
  Limit, `-A` OFPS Adaptation, `-m` Cube Interior Steps, `-M` Cube Surface
  Steps, `-b` Body-Centered Cubic Steps, and a Patch Distribution selector
  that picks one of `-t / -r / -R / -q / -Q / -i / -I` (or default OFPS).
  Each new control is gated behind its own expert enable-checkbox, so the
  default command line is unchanged unless you opt in.
- **Create Chart → Load patch set** (formerly "Load existing .ti1…") now
  also accepts i1Profiler files (`.pxf`, `.cgats`, `.txt`). RGB patch sets
  are converted to a tempfile `.ti1` on the fly; CMYK and parse errors
  surface as a clear info dialog.

### Fixed
- **i1Profiler → TI1 now matches targen's flare model**, applying a 1%
  flare toward the white point during sRGB → XYZ so a reconstructed target's
  strip-layout decisions in printtarg behave like a natively-generated one.
  Scale detection also handles 0..1 floats and 16-bit ranges in addition to
  0..100 and 8-bit.
- **TC9.18 / TC2.83 and other i1Profiler-converted charts now render their
  row letters and chart identification.** printtarg silently drops every
  chart label when the density-extremes table is written black-first;
  write_ti1 now emits it white-first, matching targen's iteration order.
- **Exported i1Profiler `.pxf` files are now write-protected.** Without
  `WriteProtected="True"`, i1Profiler exposes a patch-count slider and
  shuffle checkbox on our charts, and one stray click would silently
  desync the ChromIQ `.ti2`/`.ti3` round-trip. Matches the X-Rite-shipped
  reference charts.
- **Tools button no longer stays highlighted after the popup is dismissed.**
  Because `Qt.Popup` grabs the mouse the moment the button is pressed, the
  button never received the `Leave` event that would normally clear its
  hover background; the highlight lingered until the cursor next entered
  and left the button. The popup now sends a synthetic Leave to its anchor
  when it hides, so the button returns to its resting state immediately in
  both light and dark mode.

## v3.8.0-beta.15
**Workflow polish and a measurement-accuracy fix.** Rolls up the per-run
averaging fix, a new Tools converter, and a smoother Create Chart rename flow,
plus small UI tidy-ups in Check & Refine.

### Added
- **Tools → "Convert i1Profiler → TI1".** The reverse of the existing
  TI1 → i1Profiler export: reads an i1Profiler chart back into an ArgyllCMS
  `.ti1` so it can be fed to printtarg. RGB only.
- **Create Chart now offers to rename the target** when you generate under a
  new name. A chooser lets you rename the existing project (stems + manifest
  are fixed up properly, not just the folder), keep both, or replace it.

### Changed
- **Check & Refine result dialog button order.** When a refinement is
  suggested the actions now read left-to-right as *Guide Me Through
  Refinement → Use as Pre-conditioning → Install*, with Close pinned to the
  far right.
- **TC9.24 presets are temporarily disabled** in the Create Chart presets
  dropdown.

### Fixed
- **Averaging under the per-run folder layout** now reads each measurement
  relative to the output working directory, so repeated reads are addressed
  and averaged correctly.
- **Eliminated the `Populating font family aliases` startup/rename warning.**
  Several stylesheets requested the generic `monospace` family with no real
  family first, forcing Qt to build alias tables (~80 ms). They now lead with
  `Menlo`, so the family resolves immediately.

## v3.8.0-beta.14
**Windows polish on top of beta.13.** Carries the beta.13 fix for the
Windows project-create crash and tidies up the Tools popup on Windows.

### Fixed
- **Tools popup no longer shows a border on its bottom and right edges on
  Windows.** The frameless popup was also getting the operating system's own
  popup drop-shadow on top of the soft shadow ChromIQ already paints; on
  Windows that OS shadow rendered as a hard edge. It's now suppressed.

## v3.8.0-beta.13
**Fixes a Windows-only crash that made beta.11 unusable.** Creating or
importing a project on Windows failed silently part-way through: you'd see a
"files are being transferred to a new folder" message that never completed, a
blank `Where are my files.txt`, and a stuck Measure tab. This beta fixes that
and rolls up the beta.11 working-folder redesign and the beta.12 Tools menu, so
it's the first build where the new layout actually works on Windows.

### Fixed
- **Project create/import no longer crashes on Windows.** `Where are my
  files.txt` contains arrow characters (`←`) that Windows' default text
  encoding (cp1252) can't represent. Writing it raised `UnicodeEncodeError`
  *after* the empty file had been created but *before* the chart files were
  copied into the new folder — hence the blank README, the unfinished
  transfer, and the wedged tab. All project files are now read and written as
  UTF-8 explicitly, so the behaviour matches macOS.
- **Blank READMEs self-heal on next load.** A `Where are my files.txt` left
  empty by the crash above is rewritten with real content the next time its
  project is opened, so upgrading from beta.11 repairs the file automatically.
  A README you've edited yourself is still never touched.

### Note for anyone who hit this on beta.11
A project that failed to import on beta.11 has an empty `runs/run1/` — the
chart files never made it across. Re-import the chart (Load .ti2 / .ti3) and
choose to overwrite when prompted; the stale folder is replaced cleanly.

## v3.8.0-beta.12
**New Tools menu.** A toolbox button in the header — next to Preferences —
opens a popup listing four stand-alone measurement utilities. Each opens its
own dialog with a plain-language explanation of what it does, file pickers for
the input(s), and a destination + name for the output. These conversions were
already part of the normal workflow; the Tools menu exposes them for ad-hoc use
without having to set up a project. File pickers start in your working folder
and remember the last folder you used per tool.

### Features
- **Tools popup in the masthead.** A speech-bubble menu, themed for light and
  dark mode, listing the four utilities.
- **Average measurements.** Combine repeated reads of the same chart into one
  averaged `.ti3` to reduce instrument noise. Choose mean, or — with three or
  more reads — median.
- **Merge measurements.** Concatenate the patches of a primary `.ti3` with any
  number of additional `.ti3` files into a single measurement, giving the
  profiler more data points to fit.
- **Convert TI1 → i1Profiler.** Export an Argyll `.ti1` chart as i1Profiler
  patch sets (`.txt` and `.pxf`) so an i1iSis (or other i1Profiler-driven
  scanner) can measure it.
- **Convert i1Profiler → TI3.** Convert an i1Profiler measurement `.txt`
  export into an Argyll `.ti3` (via `txt2ti3`) for building a profile in
  ChromIQ.

## v3.8.0-beta.11
**Working-folder layout redesign.** Every project now uses a per-run folder
structure. The old prefix/suffix conventions (`pre_`, `cal_`, `_readN`,
`_average`, `_merged`) are gone — file role lives in the filename within a
folder, and folder names disambiguate context.

**Breaking change for projects created with earlier betas.** Old flat-layout
projects (`~/ChromIQ/<name>/<name>.ti2`, etc.) are no longer picked up on
launch or session restore. They aren't lost — see the migration steps at the
bottom of this entry.

### New layout
```
<project>/
  project.json                  # manifest (current run, run list)
  Where are my files.txt        # plain-language map of the folder
  cal/                          # calibration (optional, shared by all runs)
  exports/                      # external-tool exports
  runs/run1/, run2/, …          # one folder per profile build
    <project>.ti1 / .ti2 / .cht / .ps / .channels.json
    <project>_NN.tif            # page bitmaps
    <project>.ti3               # measurement (chartread output)
    <project>.icc               # profile (colprof output)
    reads/readN.ti3             # only when averaging is used
    preconditioning.ti3 / .icc  # only when seeded from a parent run
    merged.ti3 / merged.icc     # only when ChromIQ-style refinement ran
    calibrated.icc              # only when applycal ran
    meta.json
```

### Changed
- **Chart files take the sanitised project name as their stem.** printtarg
  stamps the project name on the printed sheet (was the generic basename
  before), the installed ICC is named after the project (was a generic
  filename that collided across projects in the system ColorSync folder),
  and the ICC's internal description carries the project name too.
- **Calibration chart files use `<project>-cal`** so a printed calibration
  sheet is distinguishable from the profiling chart in a stack on the desk.
- **i1Profiler exports** land in `exports/<project>-i1profiler.{txt,pxf}`
  (was a generic name).
- **Folder names get sanitised on import** (spaces → hyphens) — matching
  what Generate Chart has always done.
- **Each project gets a `Where are my files.txt`** at its root with a
  plain-language map of the folder ("your ICC is here, your printable
  chart is here…").

### Fixed
- **The "averaged reads double-counted into a refinement merge" bug is
  impossible by construction now.** Run 1's `reads/` cannot be seen by
  run 2's averaging code — they live in different folders. The previous
  patch (suffix-stripping + orphan rename) is no longer needed and has
  been removed.

### Migrating projects from earlier betas
1. **To migrate a project**, open one of its files via the **Load .ti2**
   button (Print or Measure tab), the **Load .ti3 or .txt** button (Build
   Profile tab), or **Browse for .ti3** (Check & Refine). ChromIQ rebuilds
   the project in the new layout, carrying every sibling chart file along
   (.ti1, .ti2, page TIFFs, .ti3, .icc). The new folder name is the
   sanitised version of the name you give it.
2. **To start fresh**, just create a new chart — it lands in the new
   layout automatically.
3. Old folders aren't deleted by the migration; they sit untouched in
   `~/ChromIQ/` until you remove them.

Architecture rationale and the full file-by-file mapping are in
`docs/dev_folder_layout.md`.

### What to test
- **Generate a new chart, print, measure, build profile.** Confirm the
  folder under `~/ChromIQ/<name>/` has the structure above, the printed
  sheet shows `<name>` (not `chart`), and the built `<name>.icc` shows
  `<name>` as its description in Photoshop / ColorSync Utility.
- **Calibration target → profiling chart → applycal.** Confirm `cal/` is
  populated, the printed cal sheet shows `<name>-cal`, and the calibrated
  profile lands in the run as `calibrated.icc`.
- **Averaging.** Read a chart, click **Measure again to average**, take a
  second read, **Average all reads & build**. Confirm `runs/run1/reads/`
  contains `read1.ti3` + `read2.ti3` and `<name>.ti3` is the averaged
  result.
- **Use as pre-conditioning profile** on a built profile → generate the
  refined chart → measure → build. Confirm a `runs/run2/` appears with
  `preconditioning.ti3`/`.icc` (copies of run1) and the refined profile
  builds (when ChromIQ-style refinement is on, you also see `merged.ti3`/
  `.icc`).
- **Open an old beta.10 flat-layout project's .ti2 or .ti3** via Load.
  Confirm a fresh new-layout project appears under the name you give it,
  with all sibling files inside `runs/run1/`.
- **i1Profiler workflow** (only relevant for i1iSis users): generate a
  chart with i1iSis selected → confirm `exports/<name>-i1profiler.pxf` is
  written → measure in i1Profiler → load the measurement `.txt` back.
- **Windows** specifically: the import flows, file dialogs, and
  i1Profiler export all use `pathlib.Path`, but this is the first beta
  with the new layout — please flag any path-related oddities.

## v3.8.0-beta.10
Fixes a Windows-only crash that hung the app when starting a second chart
read in the same session — most visibly via the new "Measure again to
average" button. Also tidies the button order in the "All Stripes Read"
window.

### Fixed
- **Second chart read no longer hangs the app on Windows.** With averaging
  enabled, finishing a chart and then clicking **Measure again to average**
  crashed silently with `OSError: [WinError 6] The handle is invalid` and
  left the Measure tab frozen — the spectrometer never re-prompted for
  calibration. Root cause was in the Windows keystroke-injection path used
  by chartread: after each `AttachConsole` + `FreeConsole` pair (used to
  forward keypresses into chartread's hidden console) the parent process
  was left with stale standard handles, and the next `subprocess.run` call
  (the `taskkill chartread.exe` guard at the start of every measurement)
  failed before chartread could even start. The standard handles are now
  reset to NULL after every detach, matching the state a `--windowed`
  PyInstaller app starts with. As a defensive measure, every
  `subprocess.run` call across the app now passes `stdin=subprocess.DEVNULL`
  so the same class of bug cannot resurface in chart creation, profile
  building, Argyll binary probing, average merging, or CUPS printing on
  macOS.

### Changed
- **"All Stripes Read" window — Build Profile is now on the right.** With
  averaging disabled, the window used to show **Build Profile →** on the
  left and **Re-read Stripes** on the right (the default order for
  `QDialogButtonBox` on Windows). The two buttons now swap places so the
  primary action sits on the right, matching the layout of the averaging-on
  variant. The calibration and guided-refinement variants of the same
  window pick up the new order too.

### What to test
- Windows, averaging on: finish a full chart read, then click **Measure
  again to average** in the "All Stripes Read" window. Confirm the
  spectrometer is re-prompted for calibration and the second read starts
  normally instead of hanging. Repeat for a third read to exercise the
  average + build path.
- Any platform, averaging off: finish a full chart read. Confirm **Re-read
  Stripes** is on the left and **Build Profile →** on the right.

## v3.8.0-beta.9
Small visual fix to the "All Stripes Read" averaging window.

### Fixed
- **Combo body matches the other input fields in light mode.** The Mean / Median
  selector that appears in the "All Stripes Read" window once you have re-read
  the chart for averaging was rendering with the surrounding cream surface
  colour instead of the usual white input background. It now matches every
  other dropdown / spin box in light mode. (The dark theme already looked
  correct, but the fix applies there too for consistency.)

### What to test
- With averaging on and light mode, get to the second-or-later read so the
  "Average all reads & build" dialog appears with the **Combine method** combo
  — confirm the combo body is white.

## v3.8.0-beta.8
Eighth beta of the 3.8.0 line. Streamlines the **"Read again & average"** flow so
the averaging choice is visible the moment a chart finishes — no second pop-up.

### Changed
- **Averaging is now offered directly in the "All Stripes Read" window.** When
  measurement averaging is enabled, finishing a chart used to show that window
  first and then a *second* "Measurement Complete" pop-up — so in Guided mode the
  averaging option was hidden until you clicked through, and the only "read again"
  on the first window (**Re-read Stripes**) re-scans individual strips into the
  same file rather than averaging. The averaging choice now lives in the "All
  Stripes Read" window itself:
  - first read → **Re-read Stripes** / **Measure again to average** / **Build Profile →**
  - after a re-read → **Use last read only** / **Measure again to average** /
    **Average all reads & build →** (with a mean/median selector)
- **Button order fixed.** The primary action ("Build Profile →" / "Average all
  reads & build →") now sits on the right, matching the rest of the app.
- **No surprise pause.** A note explains that **Measure again to average** sets
  the instrument up again and may ask you to recalibrate, so the brief wait
  before the next read is expected.

With averaging switched off, nothing changes.

### What to test
- With averaging **on**, read a chart in **Guided** mode: confirm the "All Stripes
  Read" window now shows the three buttons above (primary on the right) and that
  **no** second pop-up appears after you choose.
- Click **Measure again to average**, confirm the re-init note matches what you
  see, then average two reads and build — the profile should build from
  `…_average.ti3`.
- Try **Re-read Stripes** and **Use last read only** to confirm they still behave
  as before.
- Repeat a normal read in **Manual** mode, and confirm a plain read with averaging
  **off** still goes straight to Build Profile unchanged.

## v3.8.0-beta.7
Seventh beta of the 3.8.0 line. Two small interface fixes, also shipped in the
3.7.42 stable release.

### Fixed
- **Closing Preferences with Cancel is now instant.** Cancelling the Preferences
  window no longer pauses while it needlessly re-applied the whole app theme; the
  previewed theme is now only restored when you actually changed the Theme
  dropdown, so Cancel closes as quickly as OK.
- **Disabled options now look disabled.** A ticked checkbox kept its bright fill
  when its group was switched off (for example the targen / printtarg options
  greyed out by a prebuilt-chart preset). Ticked checkboxes and radio buttons now
  grey out together with the rest of their group, in both light and dark themes.

### What to test
- **Cancel speed.** Open Preferences and click Cancel without touching the Theme
  dropdown — the window should close immediately. Then change the Theme, click
  Cancel, and confirm the previous theme is restored correctly.
- **Greyed checkboxes.** Pick a prebuilt-chart preset in Create Chart so the
  targen / printtarg panels grey out, and confirm any ticked checkboxes there go
  grey instead of staying coloured.

## v3.8.0-beta.6
Sixth beta of the 3.8.0 line. The **"Read again & average"** measurement step
added in beta.5 is now an opt-in setting (off by default), plus the latest
interface polish.

### Changed
- **Measurement averaging is now opt-in.** The repeated-read / averaging flow
  introduced in beta.5 is controlled by a new **"Enable measurement averaging"**
  switch in Preferences → Behaviour, **off by default**. With it off, a finished
  read goes straight to Build Profile exactly as in 3.7.x — no extra dialog and
  no extra files. Turn it on to get the *Measure again* / *Average* options. The
  switch carries a full plain-language tooltip.
- **Preferences → Behaviour is easier to read.** The behaviour options are now
  laid out in two columns, and every option carries a full ⓘ tooltip.
- **Create Chart no longer scrolls sideways.** A long generated-command preview
  is kept inside the panel instead of forcing a horizontal scrollbar.

### What to test
- **Default off.** With the new setting off, finishing a chart read should behave
  exactly as before — straight to Build Profile, no completion dialog, no
  `_read*` / `_average` files created.
- **Toggle on.** Enable "Enable measurement averaging" in Preferences, then finish
  a read: the completion dialog offering *Measure again* / *Average* should appear,
  and the averaging flow from beta.5 should work end to end.
- **The tooltip.** The ⓘ beside the new switch should open a readable explanation
  that fits fully in its window.

## v3.8.0-beta.5
Fifth beta of the 3.8.0 line. Adds an optional **"Read again & average"** step to
the Measure tab: read the same printed chart more than once and average the
measurements together to reduce instrument noise.

### Added
- **Read the same chart several times and average the results.** When a
  measurement finishes, ChromIQ now asks whether you'd like to measure the chart
  again. Each repeat is kept alongside the previous reads, and once you have two
  or more you can combine them into a single averaged measurement — or just keep
  the most recent read — before building your profile. Averaging is handled by
  ArgyllCMS's own `average` tool: it averages the measured colour values,
  including the full spectral data, while leaving the chart's RGB patches
  untouched. A **Mean / Median** choice is offered once you have three or more
  reads (with two reads they're identical).

### Thanks
- **Alan Goldhammer** for suggesting measurement averaging and pointing to the
  approach behind it.

### What to test
- **The completion dialog appears.** Finish a normal chart read — after the usual
  "All stripes read" prompt, a new **Measurement Complete** dialog should offer
  *Continue to Build Profile* and *Measure again to average*.
- **Measure again.** Choosing it should re-read the same chart from the start (a
  fresh full read, not a resume) and keep the previous read.
- **Two or more reads.** After a second read the dialog should offer *Average all
  reads & build*, *Use last read only*, and *Measure again*, plus the Mean/Median
  selector.
- **Average & build.** Averaging should produce one measurement file and take you
  to Build Profile with it loaded; the chart's patch file is still linked, so
  "print again" / refinement keep working.
- **Three or more reads** and the **Median** option, if you want to exercise the
  outlier-rejection path.

## v3.8.0-beta.4
Fourth beta of the optional **ChromIQ-style refinement process** (still off by
default). The refinement merge is now done by ArgyllCMS itself, and this beta
folds in the same Create Chart additions and Check & Refine improvement shipping
in stable 3.7.40.

### Added
- **Two built-in "i1Pro TC9.24 by Pharmacist" targets — one for A4, one for US
  Letter.** Pick one from Create Chart → Manual → Presets, give it a name, and
  ChromIQ copies a complete, ready-made chart (patch set, layout and page TIFFs)
  into a new folder under that name. There's no targen or printtarg step — the
  files are used exactly as supplied — so the targen and printtarg options are
  greyed out while one of these presets is selected.
- **Save a preset together with its patch set.** The Save Preset dialog can now
  attach the patch set (`.ti1`) currently loaded. Selecting that preset later
  builds the chart straight from that patch set — skipping targen, just laying it
  out with printtarg — and the `.ti1` is stored inside the preset folder, so it
  travels with a shared preset.

### Changed
- **The refinement merge now uses ArgyllCMS's own `average -m`.** The optional
  pre-conditioning merge hands off to ArgyllCMS instead of ChromIQ's hand-rolled
  CGATS surgery, so the merged measurements match what Argyll's own tools produce.
- **The preset list is grouped by instrument.** Built-in presets are now sorted by
  instrument and separated with divider lines — one between your own saved presets
  and the built-ins, and one between each instrument group — so the list is easier
  to scan.
- **Check & Refine lists the worst individual patches.** Alongside the worst
  strips, the report now also calls out the single worst-performing patches, so
  it's easier to see whether a problem is a whole strip or just a few patches.

### Thanks
- **Alan Goldhammer** and **Pharmacist** for the TC9.24 targets and their testing
  and feedback.

## v3.8.0-beta.3
Third beta of the optional **ChromIQ-style refinement process** (the feature
itself is unchanged from beta.2 and still off by default). This beta folds in the
same chart-reading and measurement-abort fixes shipping in stable 3.7.39, plus
the refreshed built-in TC9.18 preset.

### Fixed
- **The strip highlighter now follows multi-page charts correctly.** On a chart
  that spans more than one page, the green "read this strip" marker could get
  stuck on the last strip of page 1 when it should have moved to the first strip
  of page 2. ChromIQ now reads the exact strips-per-page from the chart's own
  data (the `.ti2` file) instead of guessing from the image — printtarg prints a
  rotated title down the right margin that the old guess mistook for an extra
  strip — so the marker lands on the right strip and the right page every time.
- **Closing the "Calibration Required" dialog now stops the measurement.**
  Pressing the window's close button (or Esc) while that dialog is open now sends
  the abort key to the instrument and ends the run, instead of starting
  calibration anyway.
- **No more false "Measurement complete" after an aborted calibration.** If you
  cancel at the calibration step (Esc/Q, or by closing the dialog), the log no
  longer claims success and shows a "Saved:" path for a file that was never
  written — it now says the measurement was stopped and no `.ti3` was created.

### Changed
- **The built-in TC9.18 preset was rebuilt as "i1Pro TC9.18 by Pharmacist".** It
  now uses a plain 918-patch TC9.18 set with a simpler i1Pro recipe
  (`printtarg -ii1 -pA4 -t300 -L -m12 -M12 -b`). Leaving the preset now correctly
  restores your per-instrument default patch scale and margin.

### About ChromIQ-style refinement (unchanged)
See **v3.8.0-beta.2** below for the full description and testing notes. With the
setting off (the default), ChromIQ behaves exactly as it did in 3.7.x.

## v3.8.0-beta.2
Second beta of the optional **ChromIQ-style refinement process**. Same headline
feature as beta.1 — reuse the measurements from an earlier profile to build a more
accurate one — now with a fix so calculating the patch count for an unusual chart
layout no longer freezes the window. Still off by default; with the setting off,
ChromIQ behaves exactly as it did in 3.7.x.

### What ChromIQ-style refinement does
It builds a profile in two passes for higher accuracy:
1. Print and measure a first chart and build a profile from it — this becomes your
   *pre-conditioning* profile.
2. In Create Chart, create a second chart and point it at that profile. ChromIQ
   keeps the first run's measurements alongside the new chart.
3. After you measure the second chart, the Measure tab offers *"Also use measurement
   data from the pre-conditioning profile"*. Accept it and the final profile is built
   from both measurement sets combined.

Your freshly measured file is never changed — the combined data goes into separate
`*_merged.ti3` / `*_merged.icc` files. Turn the feature on in Settings (off by
default).

### Fixed
- **Patch-count calculation no longer freezes the window.** In Create Chart →
  Manual with *Auto* patch count, a layout that isn't in the built-in capacity
  database makes ChromIQ run targen/printtarg several times to find the exact fit.
  This used to lock the UI (spinning beach ball on macOS) until it finished. The
  log now updates step by step ("Step 3/8 — probing 412 patches…") so you can see
  it working.

### What to test
- **The refinement round-trip.** With the setting on, build a first profile, create
  a second chart using it as the pre-conditioning profile, measure, and confirm the
  Measure tab offers the merge and produces a `*_merged.icc`. Check the merged
  profile is at least as good as the single-pass one.
- **Toggle off = unchanged.** With the setting off, confirm the workflow behaves
  exactly as in 3.7.x — no merge prompt, no `pre_*` files left behind.
- **Custom-layout patch count.** In Manual mode with Auto patch count on, choose a
  patch scale or margin that isn't a standard value and click Generate — the window
  should stay responsive and show the search progress live.

## v3.8.0-beta.1
Beta: optional "ChromIQ-style refinement process" — reuse the measurements from
an earlier profile to build a more accurate one. Off by default; enable it in
Settings. When off, ChromIQ behaves exactly as before.

### Added
- **ChromIQ-style refinement (Settings toggle, off by default).** When enabled,
  the measurement data from a pre-conditioning profile you select in Create Chart
  is preserved (as a `pre_*.json` beside the chart) and can be merged into your
  new measurements at profile-build time, so colprof builds from a larger,
  combined set of patches. A new Measure-tab option, *"Also use measurement data
  from the pre-conditioning profile"*, appears only when such data is present.
- **`workflow/ti3_merge.py`** — combines the two measurement sets into a separate
  `<name>_merged.ti3` (your freshly measured file is never altered), renumbering
  patches and refusing to merge data measured in a different colour space/format.
  The profile is written as `<name>_merged.icc` so it's clear it used the extra
  data.

### Notes
- Guided Check & Refine still analyses only the strips you physically printed, so
  it never asks you to re-measure a patch that came from the earlier run.

## v3.7.42
Two small interface fixes.

### Fixed
- **Closing Preferences with Cancel is now instant.** Cancelling the Preferences
  window no longer pauses while it needlessly re-applied the whole app theme; the
  previewed theme is now only restored when you actually changed the Theme
  dropdown, so Cancel closes as quickly as OK.
- **Disabled options now look disabled.** A ticked checkbox kept its bright fill
  when its group was switched off (for example the targen / printtarg options
  greyed out by a prebuilt-chart preset). Ticked checkboxes and radio buttons now
  grey out together with the rest of their group, in both light and dark themes.

## v3.7.41
Small interface polish for the Preferences and Create Chart screens.

### Changed
- **Preferences → Behaviour is easier to read.** The behaviour options are now
  laid out in two columns, and every option carries a full ⓘ tooltip explaining
  exactly what it does.
- **Create Chart no longer scrolls sideways.** A long generated-command preview
  is kept inside the panel instead of forcing a horizontal scrollbar across the
  whole layout.

## v3.7.40
Ready-made i1Pro TC9.24 targets you can drop in without building a chart, the
option to bundle your own patch set with a saved preset, and a tidier preset list
grouped by instrument.

### Added
- **Two built-in "i1Pro TC9.24 by Pharmacist" targets — one for A4, one for US
  Letter.** Pick one from Create Chart → Manual → Presets, give it a name, and
  ChromIQ copies a complete, ready-made chart (patch set, layout and page TIFFs)
  into a new folder under that name. There's no targen or printtarg step — the
  files are used exactly as supplied — so the targen and printtarg options are
  greyed out while one of these presets is selected.
- **Save a preset together with its patch set.** The Save Preset dialog can now
  attach the patch set (`.ti1`) currently loaded. Selecting that preset later
  builds the chart straight from that patch set — skipping targen, just laying it
  out with printtarg — and the `.ti1` is stored inside the preset folder, so it
  travels with a shared preset.

### Changed
- **The preset list is grouped by instrument.** Built-in presets are now sorted by
  instrument and separated with divider lines — one between your own saved presets
  and the built-ins, and one between each instrument group — so the list is easier
  to scan.
- **Check & Refine lists the worst individual patches.** Alongside the worst
  strips, the report now also calls out the single worst-performing patches, so
  it's easier to see whether a problem is a whole strip or just a few patches.

### Thanks
- **Alan Goldhammer** and **Pharmacist** for the TC9.24 targets and their testing
  and feedback.

## v3.7.39
Fixes for multi-page chart reading and measurement aborts, a patch-count search
that no longer freezes the window, and a refreshed built-in TC9.18 preset.

### Fixed
- **The strip highlighter now follows multi-page charts correctly.** On a chart
  that spans more than one page, the green "read this strip" marker could get
  stuck on the last strip of page 1 when it should have moved to the first strip
  of page 2. ChromIQ now reads the exact strips-per-page from the chart's own
  data (the `.ti2` file) instead of guessing from the image — printtarg prints a
  rotated title down the right margin that the old guess mistook for an extra
  strip — so the marker lands on the right strip and the right page every time.
- **Closing the "Calibration Required" dialog now stops the measurement.**
  Pressing the window's close button (or Esc) while that dialog is open now sends
  the abort key to the instrument and ends the run, instead of starting
  calibration anyway.
- **No more false "Measurement complete" after an aborted calibration.** If you
  cancel at the calibration step (Esc/Q, or by closing the dialog), the log no
  longer claims success and shows a "Saved:" path for a file that was never
  written — it now says the measurement was stopped and no `.ti3` was created.
- **Patch-count search no longer freezes the window.** In Create Chart → Manual
  with Auto patch count, a layout that isn't in the built-in capacity database
  makes ChromIQ probe targen/printtarg several times to find the exact fit. The
  window used to lock up (macOS beach ball) until it finished; the log now
  updates step by step ("Step 3/8 — probing 412 patches…") while it works.

### Changed
- **The built-in TC9.18 preset was rebuilt as "i1Pro TC9.18 by Pharmacist".** It
  now uses a plain 918-patch TC9.18 set with a simpler i1Pro recipe
  (`printtarg -ii1 -pA4 -t300 -L -m12 -M12 -b`). Leaving the preset now correctly
  restores your per-instrument default patch scale and margin.

## v3.7.38
Your own Create Chart presets can now generate as soon as you pick them.

### Added
- **"Generate immediately when selected" option for your own presets.** The Save
  Preset dialog now has a checkbox to make a preset start its chart the moment you
  pick it from the list (after asking for a target name, just like the built-in
  presets). Such presets are marked with a ▶ in the dropdown. The setting is saved
  inside the preset file, so it's respected even when you share the preset with
  someone else. Picking the preset and cancelling the name prompt simply loads its
  values without generating, so the preset stays available to edit or delete.

### Changed
- **The Save Preset dialog was rebuilt** with a roomier layout and clearer text to
  make space for the new option.

## v3.7.37
Built-in presets now ask you to name the target before they generate.

### Changed
- **Selecting a built-in preset now prompts for a target name first.** Instead of
  generating straight into a folder named after the preset (e.g. `ColorMunki-648`),
  ChromIQ asks you to name the target — with guidance on picking a name that stays
  meaningful later (printer + paper + date/quality, e.g.
  `EpsonP900-CansonPlatine-2026-05`). It then creates the chart and fills that name
  into the Output → Target name field so you can regenerate. Cancelling the prompt
  returns to the previously selected preset and changes nothing.

## v3.7.36
Two more ready-made ColorMunki targets in Create Chart, a clearer preset list,
and a layout fix for the preset row.

### Added
- **Two built-in "ColorMunki by Pharmacist" presets (Create Chart → Manual →
  Presets).** A 324-patch *standard quality* and a 648-patch *high quality*
  ColorMunki target. Both select the ColorMunki with Triple density on, so the
  chart is laid out with the denser i1Pro geometry and the measurement file is
  set back to the ColorMunki automatically (e.g. `targen -d2 -f648 -e4 -B4 -G
  -g64`, A4 landscape, 16-bit TIFF). Like the other built-ins they can't be
  deleted, and selecting one **creates the chart right away** — every setting
  stays editable for a regenerate afterwards.

### Changed
- **The TC9.18 built-in preset now names its instrument:** "i1Pro TC9.18 +
  Extended grays by Pharmacist" (was "TC9.18 by Pharmacist").
- **Built-in presets are now listed below your own saved presets** in the preset
  dropdown, instead of above them.
- **Selecting any built-in preset now generates its chart immediately,** without
  a separate click on Generate (the ColorMunki presets now match TC9.18).

### Fixed
- **Long built-in preset names no longer stretch the preset row.** The preset
  dropdown now keeps a fixed width and shortens an over-long name with an
  ellipsis (the full name still shows when the list is open), so the +, − and
  folder buttons next to it are no longer squashed together.

## v3.7.35
Adds a ready-made grayscale test chart to the Create Chart tab.

### Added
- **"TC9.18 by Pharmacist" built-in preset (Create Chart → Manual → Presets).**
  A fixed, ready-to-use TC9.18 grey patch set. Selecting it loads the bundled
  chart and creates the target right away with a proven printtarg layout
  (`-ii1 -pA4 -L -a0.95 -m10 -M10 -r -P -c -A0.90`). It's pinned to the top of
  the preset list, marked as built-in, and can't be deleted. Everything stays
  editable afterwards: clicking Generate again re-lays-out the very same chart,
  while changing a patch-count (targen) setting builds a fresh one instead.
  Switching back to Default or another preset cleanly restores all layout
  options.

## v3.7.34
Small UI polish across three tabs: friendlier Profile Metadata tooltips, tidier
command previews when filenames get long, and a Windows-only tweak to the
Settings dialog.

### Improved
- **Friendlier Profile Metadata tooltips on the Build Profile tab.** The
  Manufacturer, Model and Copyright info boxes (in both the guided and manual
  modules) have been rewritten in plain, beginner-friendly language — each now
  explains what the field is for, reassures that it's optional and has no effect
  on colour, and gives a concrete example. The info dialogs also open with a
  proper title (e.g. *Manufacturer (-A)*) and are sized a little wider so the
  longer text has room to breathe.
- **Tidier command previews in Create Chart.** The `targen`/`printtarg` command
  boxes (both modules) now shorten long names — the target name and the
  pre-conditioning profile filename — with a middle ellipsis capped at 23
  characters, keeping both the start and the tail (extension/date) visible so a
  single long name can no longer stretch the box. Only the preview text is
  affected; the real filename used at Generate is unchanged.

### Fixed
- **"Confirm print settings before sending to printer" is now hidden on
  Windows.** The CUPS preflight summary is a macOS/Linux concept, so the Settings
  option no longer appears on Windows, where printing uses a different path.

## v3.7.33
Adds an import path for i1Profiler measurement data to the Build Profile tab.
The Load button now also accepts the `.txt` measurement files i1Profiler exports,
converts them to an Argyll `.ti3` with `txt2ti3`, and loads the result into the
normal profile-building flow — so charts read on an i1iSis (or any other
i1Profiler-driven instrument) can be profiled in ChromIQ.

### Features
- **Build Profile loads i1Profiler measurement `.txt` files.** The load button on
  the Build Profile tab now accepts both `.ti3` and i1Profiler `.txt` measurement
  exports. Picking a `.txt` runs Argyll's `txt2ti3` to produce a `.ti3`, which is
  then loaded exactly like a measured `.ti3` — instrument and spectral-data
  detection, option gating and build all behave as before.
- **Imported measurements are filed into a named profile folder.** As with
  loading a chart, a `.txt` from outside your working folder prompts for a profile
  name and is copied, renamed, into its own `<working>/<name>/` subfolder before
  conversion. A `.txt` already inside the working folder offers *Continue*
  (convert in place) or *Use as base for a new profile* (copy to a fresh folder),
  reusing the existing chart-loading dialogs.
- **Plain-language error when a `.txt` can't be read.** If `txt2ti3` can't make
  measurement data from the file — for example a patch/reference list rather than
  actual readings, or one missing the colour measurements — ChromIQ shows a clear
  dialog explaining what to export from i1Profiler, with the underlying `txt2ti3`
  error included as technical detail.

## v3.7.32
Fixes the Create Chart manual module's Neutral Axis Steps (`-n`) option, which
the UI accepted but never passed to targen or showed in the bottom-of-tab
command preview.

### Fixes
- **Neutral Axis Steps (`-n`) is honoured in manual mode.** The manual panel
  collected the expert targen extras `-D`/`-c`/`-C`/`-N`/`-V` but omitted `-n`,
  so any value set for Neutral Axis Steps was silently dropped from both the
  generated `targen` command and the live command preview. `-n` now flows
  through to both, and is emitted ahead of `-c` for readability (targen parses
  options order-independently, so the chart is unchanged).
- **Neutral Axis Steps is gated on a pre-conditioning profile.** targen's `-n`
  samples the neutral axis of the profile supplied via `-c`, so the field now
  stays greyed out (and unchecked) until a pre-conditioning profile is set —
  preventing a no-op configuration.

## v3.7.31
Extends the i1iSis hand-off (added in v3.7.28) beyond RGB. ChromIQ now writes
the i1Profiler patch set in the colour space of the target you generated — RGB,
CMYK, or extended-gamut CMYK+N (for example CMYK + Orange + Green + Violet) —
so the hand-off works for CMYK and multi-ink printers, not just RGB. Also folds
in a Create Chart command-preview fix.

### Features
- **i1Profiler export is colour-space aware (RGB / CMYK / CMYK+N).** When i1iSis
  is the selected instrument, ChromIQ reads the device channels straight from the
  generated target and writes the matching i1Profiler structure: RGB patches
  scaled to 0–255, CMYK and extended-gamut CMYK+N patches on the 0–100 ink scale.
  The CMYK and CMYK+N files carry the colour-space tag, ink limit and per-ink
  definitions, matching the patch sets i1Profiler ships, so its CMYK and
  extended-gamut loaders read them. Extended gamut is written as a CxF3 `.pxf`
  only — i1Profiler has no CGATS `.txt` for it. RGB output is byte-for-byte
  unchanged from v3.7.28.
- **The hand-off instructions adapt to the colour space.** The pop-up now names
  the colour space, lists the right file(s), and — because i1Profiler does not
  read the colour space from the patch set itself — reminds you to set the
  printer colour space (and define the extra inks, for CMYK+N) *before* loading,
  and to leave i1Profiler's Smart patch generator alone afterwards so it doesn't
  replace the loaded patches.

### Fixes
- **Create Chart command preview shows the staged pre-conditioning filename.**
  The guided info label unconditionally prepended `pre_`, so picking an
  already-archived `pre_*.icm` rendered as `-c pre_pre_…`; the manual preview
  emitted the picked absolute path, burying the rest of the arguments. Both sites
  now mirror what targen actually receives.

## v3.7.30
The back, forward and "go to parent folder" arrows in ChromIQ's file
open/save dialogs were almost invisible in Light mode — they now use a
dark, high-contrast arrow.

### Fixes
- **File-dialog navigation arrows are legible in Light mode.** The back,
  forward and parent-folder arrows in ChromIQ's file dialogs were recoloured
  to a single light grey that suited Dark mode's dark toolbar but washed out
  against Light mode's pale toolbar. They now switch to a near-black arrow
  (#1C1B18) in Light mode, while Dark mode is unchanged.

## v3.7.29
Fixes a Build Profile failure where a profile that was actually created was
reported as "Profile file was not created", and stops a long file path from
squeezing the Load button on the Measure tab.

### Fixes
- **Build Profile no longer fails when the target name contains a file
  extension.** If a chart/target name ended in an extension (for example a
  pasted ".icm" profile name), it was reused verbatim as the working-folder
  name and the stem of every generated file — producing "<name>.icm.ti3".
  colprof then wrote "<name>.icm.icc" (it appends, never replaces, the
  extension), while ChromIQ looked for "<name>.icc" and reported a phantom
  "Profile file was not created" even though the profile had built fine.
  ChromIQ now (a) strips known work-file extensions
  (.icc/.icm/.mpp/.ti1/.ti2/.ti3/.tif/.cal) from the target name — showing a
  hint in the Create Chart name field when it does — so new sessions can't be
  contaminated, and (b) recognises colprof's actual appended output (both .icc
  and .icm), so existing measurements with a stray extension build correctly
  too. Verified against ArgyllCMS 3.5.0 on Windows, where colprof writes .icm.
- **Long file paths no longer squeeze the "Load" button on the Measure tab.**
  The selected .ti2 path is now middle-elided with "(...)" — keeping the start
  of the path and the filename both visible — instead of word-wrapping onto
  several lines and crushing the button. The full path is shown on hover.

## v3.7.28
First step of i1iSis support. ChromIQ cannot drive the i1iSis directly —
that scanner only works through X-Rite's i1Profiler — so this release adds
a hand-off: select i1iSis in Manual mode and ChromIQ writes the patch list
in the two file formats i1Profiler reads, alongside the regular chart. The
user prints, scans and builds the profile in i1Profiler. Future releases
will close the loop further; for now this removes the i1iSis as a hard
blocker for ChromIQ users.

### Features
- **New "i1iSis (via i1Profiler)" instrument option in Manual mode.**
  Picking this runs targen as usual to build the patch list, then writes
  a CGATS `.txt` and a CxF3 `.pxf` next to the chart — both formats
  i1Profiler accepts as a custom patch set. The printtarg layout
  preview still renders, with a banner clarifying that it's a preview
  only; i1Profiler lays out the actual chart from the patch list when
  you load the `.pxf`. A popup at the end of generation walks through
  the next steps in i1Profiler (Advanced User Mode → Printer →
  Profiling → Patch Set window → Load). ChromIQ's Print, Measure and
  Profile tabs are not used for this instrument — the rest of the
  workflow happens entirely in i1Profiler.
- **Sensible printtarg defaults pre-applied when i1iSis is selected.**
  Paper jumps to A3+ Portrait, *No Spacers* and *Don't Limit Strip
  Length* tick on automatically, since the printtarg run is purely for
  the preview and i1Profiler re-lays-out the actual chart anyway. All
  four are still editable if you want a different preview shape;
  switching back to another instrument resets them to printtarg's
  normal defaults.
- **i1iSis is intentionally absent from Guided mode.** Guided's job is
  to optimise the chart layout for the instrument, but for i1iSis the
  layout is recomputed by i1Profiler — so there is nothing to optimise
  there. The Manual-mode flow is the supported path.
- **Defensive hand-off if printtarg fails.** The `.txt` / `.pxf` export
  fires off the targen output (the patch list), not the printtarg
  TIFF. If printtarg crashes for an unrelated reason the user still
  gets a working patch-set file pair, with the popup noting that the
  preview was unavailable but the i1Profiler workflow is unaffected.

## v3.7.27
Fixes three Create Chart bugs that silently mis-handed parameters to printtarg:
Triple density now respects manual overrides of the strip-limit, margin and
patch-size flags; the spacer-only scale and other layout-affecting extras now
participate in the Auto patch-count estimate; and float spinboxes no longer
leak floating-point noise into the generated command.

### Fixes
- **Triple density now respects your manual overrides of `-P`, `-m` and `-a`.**
  In Manual mode, ticking *Triple density* still seeds the i1Pro-emulation
  preset into the *Don't limit strip length*, *Margin* and *Patch size scale*
  widgets — but if you then edited any of those, the build code silently
  threw the edits away and handed `-a 1.30 -m 5 -P` to printtarg regardless.
  Your edits now flow through unchanged. The patch-count lookup is aware of
  the override and falls back to a live binary search when the values no
  longer match the preset the dedicated triple-density patch table was
  measured at. The `-i i1` instrument swap and the `-L` clip-border
  suppression remain forced — they're load-bearing for the .ti2 rewrite that
  makes the ColorMunki read an i1Pro-shaped chart.
- **Spacer-only scale (`-A`) and *No spacers* (`-n`) now actually change the
  Auto patch count.** The Manual-mode *Auto* patch-count estimate took a
  fast lookup path through the per-sheet patch database, which only covers
  the headline layout knobs (`-a`, `-m`, `-L`, `-P`, `-h`). Anything else
  that affects how much fits per page — most visibly the spacer-only scale
  flag and the *No spacers* toggle — was silently ignored, so changing
  spacer width or removing spacers entirely produced the same patch count
  as the default. ChromIQ now detects layout-affecting extras and routes
  the estimate through the live binary search so the override actually
  participates. Layout-neutral extras like `-Q`, `-R`, `-K`, `-I` still
  take the fast path.
- **Float spinboxes no longer leak `1.2000000000000002`-style noise into
  the printtarg command.** Stepping a `-A` (or `-a`, `-r`, `-V`, `-T`, `-N`)
  spinbox accumulates binary floating-point rounding error in the
  underlying value — `setDecimals(2)` hides it in the widget display, but
  the live command preview and the actual printtarg call would show the
  noisy raw value. ChromIQ now formats float widget values with their
  declared decimals when building the command line.

## v3.7.26
Makes the Windows USB driver installer trustworthy — it verifies the driver
actually bound and falls back to Zadig when the automatic install silently
fails — and shows the ChromIQ icon in the Windows taskbar.

### Fixes
- **The automatic driver install no longer reports false success.** `wdi-simple`,
  the silent WinUSB installer, can exit with "success" without actually binding
  the driver to the instrument — for example when a stale device instance left
  over from a previous USB port misdirects it. ChromIQ now re-checks the device
  after installing and, if the driver didn't bind, says so plainly and offers the
  **Zadig** fallback (pick the instrument, choose WinUSB / libusb-win32, then
  *Replace Driver*) instead of claiming the install worked. Zadig's forced,
  interactive driver replacement reliably handles the cases the silent installer
  can't.
- **The Windows taskbar now shows the ChromIQ icon.** ChromIQ didn't set a
  Windows AppUserModelID, so the taskbar button inherited the host process's
  icon — the Python interpreter when run from source, or the PyInstaller
  bootloader when frozen — and the app's own icon never appeared. ChromIQ now
  sets an explicit AppUserModelID at startup, so the taskbar uses the app's
  window icon.

## v3.7.25
Hotfix for the Windows USB-driver dialog: the install button did nothing when
clicked.

### Fixes
- **The driver dialog's primary button now works.** Clicking *Install Driver* /
  *Open Zadig* / *Reinstall Driver* did nothing — the dialog's button box never
  connected its `accepted` signal, so the AcceptRole button left the dialog open
  and never ran the action. It's now wired to the dialog's accept handler, so the
  install / Zadig / reinstall step runs as intended. (The bug was latent since the
  USB driver installer was introduced; it only became visible once a connected
  instrument actually needed the driver, e.g. a freshly attached i1Studio.)

## v3.7.24
Fixes Windows colorimeter detection and the USB-driver dialog, and clears up a
cosmetic page count when loading an existing target. The instrument list the
driver installer recognises now matches ArgyllCMS 3.5.0 exactly. Addresses
feedback from the ChromIQ thread (post #148275).

### Changes
- **The i1 Pro family is now detected by the USB driver installer.** The i1 Pro
  and i1 Pro 2 (GretagMacbeth `0971:2000`) and the i1 Pro 3 / i1 Pro 3+ (X-Rite
  `0765:6009`) were missing from ChromIQ's device list, so they weren't
  recognised and couldn't be offered the WinUSB driver. They are now included —
  one entry covers each pair, exactly as Argyll's own driver does.
- **The recognised-instrument list now mirrors ArgyllCMS 3.5.0.** The whole
  VID/PID table was rebuilt from the active entries in Argyll's own
  `usb/ArgyllCMS.inf`. This adds the ColorMunki Photo/Design, ColorMunki Smile,
  Eye-One Monitor / Eye-One Display 1 & 2, HueyL, DTP20 / DTP92Q, Spyder 1 and
  Spyder 2024, the HCFR colorimeters, ColorHug / ColorHug 2 and the Image
  Engineering EX1 — and corrects several wrong entries (the device previously
  labelled "Spyder 1" was actually an HCFR colorimeter, and the SpyderX2 product
  ID was wrong). HID-only colorimeters that must keep their HID driver are
  deliberately excluded so ChromIQ never offers to replace a driver they need.
- **The Zadig fallback now opens its download page when not bundled.** If the
  bundled Zadig tool isn't present, ChromIQ opens the Zadig download page in your
  browser and tells you, instead of failing silently.

### Fixes
- **The USB driver dialog no longer promises an action it can't perform.** When
  a connected colorimeter already had its driver installed, the dialog still
  showed driver-install instructions but offered only *Close* / *Refresh* — with
  no install button. It now always shows a working button whenever a device is
  connected (labelled *Reinstall Driver* when the driver is already present), and
  only shows install instructions when there's a matching button.
- **Loading an existing target no longer shows a phantom second page.** A
  one-page chart loaded back in (e.g. to reprint or re-measure) showed "Page 1 /
  2" with both pages identical. On Windows `pathlib`'s glob is case-insensitive,
  so the chart's single `.tif` was matched twice — once by the `*.tif` pattern
  and again by `*.TIF` — and counted as two pages. The file list is now
  de-duplicated, so a single-sheet chart shows one page. This mirrors the fix
  already applied to the chart-*generation* path; the load path shared the same
  root cause.

The SpectroScan is a serial (RS-232) instrument rather than USB, so it isn't
part of the USB driver installer and needs no device entry.

## v3.7.23
Corrects the Calibration & Profiling tab's help text so it describes the real
order of operations, and makes every ⓘ info dialog size itself to its content
so longer help text can no longer be cut off.

### Changes
- **Longer help text never gets clipped.** The shared info dialog behind every
  ⓘ button now grows to show its full content instead of being silently capped
  to two-thirds of the screen, and falls back to scrolling only when the text
  would exceed the display — so even long, multi-step explanations are fully
  readable on any screen size.

### Fixes
- **Calibration & Profiling help now lists the steps in the correct order.**
  The tab's tooltip previously implied the *Apply Calibration* button (Argyll's
  `applycal`) was used before printing the profiling chart. In fact `applycal`
  folds the calibration into the *finished* ICC profile as the last step, while
  the calibration is put to use back on the Create Chart tab (printtarg `-I` /
  `-K`). The help text now walks through the true sequence: create the
  calibration file → use it for a new target or load it into the printer →
  print → measure → build the profile → apply the calibration to the profile if
  needed, with a warning against double-applying it.

## v3.7.22
Adds measurement-instrument detection to the Build Profile and Check & Refine
tabs and tidies how the detected instrument is shown across the app. ChromIQ
reads the instrument a chart or measurement was made with from the
`TARGET_INSTRUMENT` field ArgyllCMS records in `.ti2` / `.ti3` files and
surfaces it — together with whether the `.ti3` carries spectral data — in each
tab's output. This is the groundwork for automatically disabling options an
instrument can't support.

### Changes
- **Instrument detection in Build Profile and Check & Refine.** When a `.ti3`
  is loaded its instrument, and whether it contains spectral data, is detected
  and shown in the output field — for both the measurement `.ti3` and, in Build
  Profile, the calibration `cal_*.ti3`. Lays the groundwork for greying out and
  stripping options the detected instrument can't use.
- **Friendly instrument names in all output fields.** Argyll's family tags are
  expanded to the models users recognise: "X-Rite ColorMunki" becomes
  "ColorMunki / i1Studio / CCStudio" and "GretagMacbeth i1 Pro" becomes
  "i1Pro / i1Pro2 / i1Pro3(+)".
- **SpectroScan reading note removed.** The SpectroScan is an XY table that
  reads patches individually, so its Create Chart message no longer mentions a
  bidirectional "reading direction".

### Fixes
- **Create Chart instrument notice no longer stacks up.** Generating several
  targets in one session now keeps only the most recent "Chart instrument: …"
  line in the output field instead of accumulating one per target.

## v3.7.21
Expands ChromIQ's coverage of chartread's interactive prompts so that more
mid-measurement situations surface a clear dialog with buttons that send the
right keystroke, rather than only being visible in the raw log. Audited
against the Argyll 3.5.0 chartread.c source.

### Changes
- **New mid-measurement recovery dialogs.** *Strip Read Interrupted* (after
  an accidental instrument-switch trigger), *Patches Still Unread* (when the
  user presses `d` early), and a generic *Instrument Error* retry dialog for
  transient errors raised by Argyll's `ierror()` helper. Buttons emulate the
  exact keys chartread's own prompt accepts.
- **Friendlier terminal dialogs for chartread startup failures.** Comms /
  init failures, reflection-incapable instruments, CCMX/CCSS load failures,
  and rejected mode changes now show a titled dialog with Argyll's reported
  reason, instead of falling through to the generic "measurement failed"
  path.
- **Status-bar messages for informational chartread output.** Chart-vs-instrument
  mismatch warning, "high-resolution ignored", "UV ignored", "no spectral
  mode", and "scan tolerance ignored" now flash a short non-blocking status
  message. (Battery level is written to the log but not flashed, to avoid
  noise on every instrument start-up.)
- **Defensive dialogs for spot / XY-table modes.** If chartread is invoked
  in a non-strip mode through extra-args, the user now sees friendly dialogs
  for sheet placement, spot-mode readiness, and abort confirmation, rather
  than a stuck UI.
- **Regression coverage for the "ALL ROWS READ" detection.** Tests pin the
  current behaviour against Argyll 3.5.0's inline-suffix form on the "Ready
  to read strip pass …" line, in both normal and resume modes.
- **Friendly failure dialogs for colprof, printcal and applycal.** When one
  of these batch tools fails, ChromIQ now identifies the underlying reason
  (illuminant mismatch, unreadable .ti3, no white patch, calibration /
  profile colour-space mismatch, etc.) and shows a dialog explaining what
  to do, instead of just "see output above". Audited against Argyll 3.5.0
  colprof.c / printcal.c / applycal.c. The existing FWA-instrument dialog
  for colprof is preserved as a bespoke case.
- **More colprof warnings surfaced in the Build Profile result dialog.**
  Intent-override hints, FWA-ignored-in-emissive-mode, and ink-limit-over-chart
  warnings now show up alongside the existing out-of-gamut / failure
  warnings, so users don't need to hunt for them in the raw log.
- **Friendly failure dialogs for the chart pipeline (targen + printtarg).**
  Common errors — preconditioning ICC profile mismatch, MPP profile
  mismatch, paper too small for the TID strip / patch row / row width,
  unsupported instrument, wrong device colour encoding — now show a titled
  dialog explaining what to change in the Chart tab.
- **Friendly failure dialog for profcheck.** Wrong illuminant for the
  reference type, unreadable / empty .ti3, unhandled colour representation,
  and missing-field errors now produce a "Profile Quality Check Failed"
  dialog instead of just a log line.
- **Friendlier iccgamut and viewgam error messages.** The Gamut Analysis
  dialog now includes the structured reason (VRML write failure, ICC read
  error, etc.) instead of a scraped "Error: …" line. viewgam's most common
  failure — incompatible gamut colour spaces — is now explained in plain
  language.

### Fixes
- **Info dialogs no longer clip long wrapped text.** The shared info/error
  dialog under-counted the height of word-wrapped paragraphs, so longer
  messages could be cut off at the top and bottom. It now measures each
  wrapping label at its real width and grows to fit. Affects every
  info/error dialog in the app.

## v3.7.20
Expands the Settings-dialog credits to acknowledge two more people who
helped shape ChromIQ, and slightly strengthens the existing acknowledgement
of Knut Georg Larsson to better reflect his role as the original inspiration
for the app.

### Changes
- **Settings credits expanded.** The build/library credit line now reads
  *"Built on ArgyllCMS by Graeme Gill · Made possible by Knut Georg Larsson
  · Testing & feedback: Nelson (Pharmacist), Alan Goldhammer"* — "With
  thanks to…" is reworded to "Made possible by…" to better reflect Knut's
  role as the original inspiration for the app, and the two testers are
  appended on the same line (separated by the same `·` used elsewhere) to
  keep the dialog footer compact.

## v3.7.19
Fixes a Guided-mode regression where the white / black patch base (-e / -B)
quietly shrank toward 2 across "Save as defaults" cycles, leaving even the
reference 560-patch chart on i1 Pro + A4 landscape generating `-e2 -B2`
instead of the documented `-e4 -B4` at the anchor.

### Fixes
- **Guided mode no longer collapses -e / -B toward 2 over time.** "Save as
  defaults" used to round-trip the **auto-computed** white / black patch
  counts back into the *base* setting that Guided then reread on the next
  computation. If you saved while a low-capacity config was selected
  (i1 Pro 3+ on small paper, ColorMunki, a single-page strip-reader chart),
  the base shrank to 2 and stayed there for every subsequent chart on every
  instrument — even the reference i1 Pro + A4 landscape + 1 page case that
  is supposed to land on `-g32 -e4 -B4`. The base is now fixed at the
  documented value of 4 in Guided mode and no longer round-trips through
  Save as defaults; affected installs self-heal on next launch (the stale
  settings keys are no longer read). Manual mode was never affected — its
  -e / -B widgets use a separate storage path and already fell back to 4
  whenever the Auto checkbox was on.
A2 Landscape (594 × 420 mm) joins the paper-size list — a much better fit
for strip readers than the existing A2 portrait. The i1 Pro 3+ also goes
back to printtarg's native 6 mm margin default, and the Measure tab's
bidirectional row gets a small tooltip tidy-up.

### Features
- **A2 Landscape (594 × 420 mm) paper size.** A new entry in the Paper
  size combo. Strip readers pack far more strips on a 594-wide sheet
  than on a 420-wide one — A2 landscape on i1 Pro lifts the base capacity
  from 1050 to 1512 patches (+44%), and on i1 Pro 3+ from 225 to 324
  (+44%). Per-instrument visibility in Guided mode: **i1 Pro / i1 Pro 3+**
  show landscape and hide A2 portrait (mirrors the existing A3 / A3+
  portrait-hidden behaviour for strip readers); **ColorMunki** shows both
  orientations; **SpectroScan** keeps portrait only (its bed can't reach
  the far edge of a 594 mm-wide sheet). Manual mode shows it for every
  instrument. The patch-capacity database has measured values for the new
  paper across every instrument + option combination already covered
  (margin 6/10, scale 1.0/0.95, `-L` / no-`-L`, `-P`, ColorMunki double
  density + triple density, SpectroScan hex), produced by a new
  `scripts/measure_a2_landscape_capacity.py` companion script.
- **i1 Pro 3+ default page margin is now 6 mm.** The original i1 Pro keeps
  10 mm to avoid its strip optics drifting onto the paper edge near
  the last patch ("not enough patches read"), but the i1 Pro 3+ doesn't
  need that headroom and goes back to printtarg's native 6 mm default in
  both Guided and Manual modes. Side benefit: slightly higher patch counts
  at the same paper size (A4 base 108 vs 99, A2 landscape 324 vs 315).

### Fixes
- **Measure tab: separate tooltip icons for *Disable bidirectional strip
  recognition (-B)* and *Auto*.** Each option now has its own ⓘ icon with
  option-specific text (one explains the `-B` checkbox itself, the other
  explains what Auto does), and the row spreads the two option-and-icon
  groups across the column width — the `-B` group on the left, Auto on
  the right. Applies to both Guided and Manual modes.

## v3.7.17
You can now tune how many neutral patches (grey ramp + white/black) ChromIQ
adds relative to chart size, from a single setting.

### Features
- **Grey ramp reference setting.** A new field under
  *Settings → Neutral Patches* sets the patch count at which a chart gets
  the standard 32 grey / 4 white / 4 black. Lower it for denser neutrals on
  every chart (better grey balance and shadow detail, fewer colour patches);
  raise it for sparser neutrals. Applies to both Guided mode and Manual mode
  (Manual when the Auto −g / −e / −B checkboxes are on), and updates the
  live patch preview as soon as you change it. Default 560 — unchanged
  behaviour out of the box. Small charts always keep the minimum neutral set
  (grey ≥ 8, white/black ≥ 2, and in Guided mode neutrals never exceed half
  the total patches), so a tiny target is never swamped by greys.

### Fixes
- **Guided mode: wider gap** between the *Suppress left clip border (-L)*
  and *Don't limit strip length (-P)* checkbox labels and their tooltip
  icons, so each icon reads as belonging to its option.

## v3.7.16
The patch-capacity database now knows about *Don't limit strip length*
(`-P`) for the i1 Pro family, so the calculated patch count reflects the
larger number of patches that fit when the strip-length cap is removed.
A new guided-mode checkbox exposes the same control.

### Features
- **`-P` (Don't limit strip length) factored into the patch-count
  database.** Previously the *Calculated Patches* number was always
  computed at the `-P`-off layout, regardless of whether the chart you
  were about to generate would actually have the cap removed. The
  database now contains measured per-sheet values for every
  i1 Pro / i1 Pro 3 / i1 Pro 3 Plus combination across `-m6 / -m10`
  and `-a 1.0 / -a 0.95`, with and without `-L` — and `-P` flips
  through to the new tables transparently. Big papers (A2, A3+,
  Tabloid, A3 landscape, Legal) gain up to ~2.5× more patches per
  sheet; A4 and smaller see modest gains where the strip-length cap
  barely bit.
- **Guided-mode *Don't limit strip length* checkbox.** A new option
  sits next to *Suppress left clip border* in Guided mode, visible
  only when an i1 Pro family instrument is selected. Toggling it
  immediately re-computes the patch count and shows `-P` in the
  command preview. Saveable as a default. Hidden on ColorMunki and
  SpectroScan (their layouts ignore `-P`) and on triple-density mode
  (which forces `-P` internally).

### Fixes
- **TIFF command stamp truncates long names.** When the stamped
  command line includes a long target name or a long `-c` / `-K`
  pre-conditioning/calibration filename, it no longer overruns the
  right margin — the displayed stamp shortens those tokens to their
  basename and caps the length. The actual command passed to ArgyllCMS
  is unchanged; only the printed stamp is shortened.
- **Bidirectional *Auto* checkbox layout.** In the Measure tab the
  *Auto* toggle now sits a short gap to the right of the
  *Disable bidirectional strip recognition (-B)* checkbox, with the
  tooltip pinned to the row's right edge (both Guided and Manual).

## v3.7.15
Two quality-of-life fixes: the Measure tab now auto-sets bidirectional
strip reading from the instrument baked into the loaded chart, and the
Settings window's tooltip icons and popup text are now legible and
theme-correct in both light and dark mode.

### Features
- **Auto bidirectional reading from the loaded chart.** Next to the
  *Disable bidirectional strip recognition (-B)* checkbox in both Guided
  and Manual modes there is now an **Auto** toggle (on by default).
  When on, ChromIQ reads the chart's `TARGET_INSTRUMENT` from the .ti2
  and decides for you: the i1 Pro family (incl. i1 Pro 3 / 3+) reads in
  both directions, the ColorMunki / i1Studio reads in one direction
  only. While Auto is on the -B checkbox is locked and shows the chosen
  setting. Turn Auto off to control it yourself — the value and the
  Auto state are saved with defaults and presets, so any preset or
  default you set wins.

### Fixes
- **Settings tooltip ⓘ icons are legible in light mode.** They were
  hard-coded to near-white (`#f4f4f4`), which all but disappeared on
  the light dialog background. The icons now use the Settings window's
  neutral indicator colour — the same colour as a checked checkbox in
  that dialog (`#1c1b18` in light, `#d0d0d0` in dark).
- **Tooltip popup text uses the standard themed colour.** The ⓘ popup
  was re-resolving the appearance setting to pick its text colour, but
  the Settings appearance combo applies the theme live and only
  persists on Save — so previewing Dark could paint dark text on a dark
  background. The popup now reads the live applied palette's text
  colour, identical to every other dialog.
- **Settings checkboxes and tooltip icons recolour live** when
  switching the appearance combo, instead of waiting for the dialog to
  be closed and reopened.

## v3.7.14
Guided mode now characterises the neutral axis more accurately when you
refine an existing profile. A big thanks again to **@pharmacist on the
printerknowledge forum** for the steady stream of sharp suggestions.

### Changes
- **Refinement passes sample the profile's neutral axis (`-n`), not
  device grey (`-g`).** When the **Refinement profile** option is active
  in Guided mode (and a profile is selected), the neutral ramp is now
  emitted as targen `-n<steps>` instead of `-g<steps>`, using the exact
  same step count ChromIQ already calculates. `-g` places naïve
  device-space greys (R=G=B); `-n` places patches along the
  *perceptually-true* neutral axis defined by the pre-conditioning
  profile (`-c`), so the second pass densely characterises the corrected
  neutral — exactly where refinement matters most. White (`-e`) and
  black (`-B`) anchors are unchanged, and Manual mode is untouched.

## v3.7.13
Manual mode now has the same smart neutral-axis defaults that Guided
mode uses — opt-in per row. Each of White patches, Black patches and
Grey axis steps gets an **Auto** checkbox: tick it and ChromIQ sizes
that value from the chart's total patch count, so it scales as you
change paper, pages or instrument. Untick to type your own number any
time.

### Features
- **Auto White / Black / Grey in Manual mode.** New Auto checkboxes
  next to `-e`, `-B` and `-g`, mirroring the existing Auto patch-count
  option. When on, the value is computed from the chart's total patch
  count (whether you set it by hand or it's auto-estimated):
  a ~560-patch chart gets `-g32 -e4 -B4`; each doubling of the total
  doubles the grey steps (cap 128, floor 8) and grows the white/black
  anchors by 50 % (cap 8, floor 2). The values update live in the
  command preview and re-resolve against the real patch count at
  Generate. State is saved with defaults and presets.
- **Extensive plain-language tooltips** for White / Black / Grey
  patches explaining what each does and exactly how the Auto option
  picks its number, with wider info windows so the text fits.

### Changes
- **Unified neutral anchor at 560 patches across both modes.** Guided
  mode now shares Manual's anchor and the same compounding curve for
  white/black. Practical effect on Guided: i1Pro + A4 portrait reads
  `-g30` (the new anchor is A4 *landscape* = 560 → `-g32`), and A3
  landscape lands on a clean `-g64` (exactly 2× A4 landscape).
- **Auto checkboxes grey only the input, not the row name.** Ticking
  any Auto box (including the existing patch-count one) now keeps the
  parameter label readable and greys out just its spinbox.

## v3.7.12
Follow-up to v3.7.11's capacity-aware neutrals. Two real-world gaps in
the formula are now closed: bigger paper sizes increase the grey ramp
and white/black anchors as you'd expect, and ColorMunki's rig
(double / triple density) feeds into the same calculation so a rig user
gets the bigger budget reflected in the chart. Same feature request
chain from **@pharmacist on the printerknowledge forum**.

### Fixes
- **Paper area now scales the neutrals.** Before, switching from A4 to
  A3 landscape on i1Pro left `-g32 -e4 -B4` unchanged — the pages-only
  formula ignored that A3 landscape carries roughly 2× the patches.
  The new "effective sheets" math compares the chart's nominal patch
  budget against the anchor (i1Pro + A4, margin 10, patch scale 0.95,
  clip border suppressed = 528 patches). i1Pro + A3 landscape now lands
  on `-g68 -e6 -B6`; A2 the same. ColorMunki + A2 climbs from `-g8` to
  `-g30 -e4 -B4`. Multi-page combinations stack the same way.
- **Non-suppressed clip border respected.** When you leave the clip
  border visible on i1Pro / i1Pro 3 Plus charts, fewer patches fit per
  sheet, and the neutrals now drop proportionally. i1Pro + A4 with the
  clip strip visible lands on `-g29` instead of `-g32`. Layout-only
  knobs (margin, patch scale) still don't move neutrals — the anchor is
  fixed.
- **ColorMunki double / triple density honoured.** Engaging the
  measuring rig multiplies the per-sheet capacity (CM + A4 goes 90 →
  210 → 324 patches across single / double / triple). The grey ramp and
  anchors now follow: CM + A4 with the rig produces `-g13 -e3 -B3` in
  double density and `-g20 -e3 -B3` in triple, instead of staying at
  the single-density `-g8 -e2 -B2`.

## v3.7.11
Smarter neutral-axis defaults in Create Chart's Guided mode, plus a
small label tweak in the ColorMunki density row. The grey-ramp (`-g`)
and white/black anchor (`-e`/`-B`) counts now scale to the actual
patch budget of the selected instrument + paper combo. Based on a
suggestion from **@pharmacist on the printerknowledge forum**.

### Features
- **Capacity-aware grey / white / black in Guided mode.** The grey-axis
  step count is sized from the chart's patch budget, anchored on the
  suggester's reference of i1Pro + A4 ≈ 441 patches → `-g32`. For
  i1Pro, ColorMunki and i1Pro 3 Plus the result is also capped at the
  literal per-page table (`32 / 64 / 96 / 128` for 1–4 pages, hard max
  128), so layout knobs like margin, patch scale and the `-L` flag
  can't push grey above spec. SpectroScan skips that per-page cap and
  only obeys the absolute 128 ceiling, since one SpectroScan sheet
  genuinely represents several i1Pro page-equivalents of colour
  sampling. `-e` / `-B` follow the same page-based ladder
  (`4 / 6 / 8 / 8` with the +50 % per-page step) but drop the starting
  base from 4 to 3 on low-capacity combos (`per_sheet < 200` — i.e.
  ColorMunki single density, i1Pro 3 Plus on A4, i1Pro on 4×6, etc.)
  so the anchors don't crowd out the random colour patches on tight
  charts. A final proportional-scale guardrail kicks in only for
  degenerate combos (e.g. ColorMunki on 4×6, 18 patches per sheet) and
  pulls all three values down together. Manual mode is untouched —
  power users still pick their own values there.
- **"For rig:" prefix on the Double / Triple density row.** When
  ColorMunki is the selected instrument both density options require
  the optional measuring rig accessory; the new label makes that
  explicit and aligns the first checkbox with the left edge of the
  Instrument combobox above it. Hidden for SpectroScan (where the
  same checkbox toggles hexagon patches, unrelated to the rig).

## v3.7.10
Patch follow-up to v3.7.9: Triple density's pre-TD widget values
(margin, patch scale, suppress-LB, don't-limit-strip-length) survive
"Save defaults" and preset saves, so switching instruments later
actually restores them. Plus a round of polish on disabled-state
indicators in Create Chart so greying actually matches what's
clickable.

### Fixes
- **Triple density defaults / preset round-trip.** Previously, clicking
  "Save defaults" or "Save preset" while Triple density was active
  persisted the i1Pro-emulation overrides (`-a 1.3 / -m 5 / -P on / -L
  on`) as the saved widget values, clobbering the user's pre-TD
  preferences. On the next launch the stash captured those override
  values as if they were the "natural" state, so when the user later
  switched away from ColorMunki the auto-untoggle's restore was a
  visible no-op — values appeared to "stick". Save paths now persist
  the stashed pre-TD values for those four flags when TD is on (both
  Manual `_on_save_defaults` / `_on_preset_save` and the guided `-L`
  default).
- **Heal existing corrupted defaults on load.** If saved widget values
  match the TD-override fingerprint (`a≈1.3`, `m=5`, `P=on`, `L=on`)
  and the saved TD flag is on, the restore path substitutes Argyll
  defaults (`1.0 / 6 / off / on`) before the toggle handler captures
  the stash, so anyone who saved defaults under v3.7.9 with TD on gets
  back into working shape on the first launch of v3.7.10 without
  having to manually reset.
- **Tooltip ⓘ icons grey out with their option.** In the guided
  Create Chart Double-/Triple-density row, ticking one option
  greyed the *checkbox* of the other but left its tooltip ⓘ
  fully active — visually inconsistent with the rest of the row.
  `TooltipButton` had a `changeEvent` override that silently
  re-enabled itself the moment anything tried to disable it,
  which cancelled direct `setEnabled(False)` calls. The override
  now tracks whether the disable was explicit (preserved) versus
  an incidental parent-cascade (still re-enabled as a safety net),
  and the guided / manual toggle handlers explicitly disable the
  paired ⓘ button on the inactive option.
- **Manual Double-density now greys out Triple-density too.** The
  mutex was wired one direction only (toggling Triple disabled the
  Double `ParameterWidget` and its tooltip via parent cascade).
  Ticking Double now also disables the whole Triple-density row
  — label, checkbox and ⓘ tooltip — and unticks Triple if it was
  active, so values previously stashed by the TD handler get
  properly restored.
- **Spacer options are fully mutually exclusive in Manual mode.**
  Force B&W Spacers (`-b`) and Force Colored Spacers (`-c`) now
  grey each other out when one is checked, so only one can be
  active at a time. When No Spacers (`-n`) is enabled, all three
  spacer-related options — `-b`, `-c` and Spacer-Only Scale
  (`-A`) — are unchecked and greyed out, since none of them have
  any effect without spacers. Previously `-c` was unwired and
  stayed clickable in all states.

## v3.7.9
ColorMunki + rig users get a new **Triple density** option in Create Chart
that generates the chart with the i1Pro strip layout (`-ii1 -a1.3 -m5 -M5
-P`) then rewrites the produced `.ti2` so chartread still talks to the
ColorMunki — roughly **3×** the patch count of a plain ColorMunki chart at
the same paper size, with no extra hardware beyond the existing measuring
rig. Available in both Guided and Manual modules, mutually exclusive with
Double density.

### Features
- **Triple density (ColorMunki + rig).** A new checkbox appears next to
  Double density when ColorMunki is selected as the instrument in either
  module. With it on, ChromIQ runs printtarg with `-ii1` (i1Pro strip
  geometry) plus the tuned scale / margin / strip-limit overrides
  (`-a 1.3 -m 5 -M 5 -P`) needed for the ColorMunki to read the denser
  layout, then patches the produced `.ti2` so its `TARGET_INSTRUMENT`
  line names the ColorMunki — chartread therefore selects the right
  driver and the user sees their actual hardware in the dropdown.
  Mutually exclusive with Double density: ticking one auto-unticks and
  greys out the other. The suppress-left-clip-border control is hidden
  while Triple density is active (it forces `-L` internally) and the
  prior value is restored on untoggle. Saveable as a default in both
  modules and as part of a Manual preset.
- **Empirical patch-capacity table for Triple density.** New
  `_PER_SHEET_CAPACITY_TRIPLE` / `_TRIPLE_NO_LB` tables in
  `data/patch_db.py`, populated for all 14 supported paper sizes via the
  new `scripts/measure_triple_density_capacity.py` helper. The guided
  patch-count display, hidden-defaults info box and live Manual-mode
  command preview all react to the toggle and show the correct count
  and printtarg invocation.

### Fixes / details
- Disabled `QCheckBox` controls now actually look disabled — both the
  indicator and the label dim under the dark and light themes. Prior to
  this only `QCheckBox#param_label` (the manual-mode ParameterWidget
  labels) had a `:disabled` rule, so plain QCheckBoxes (e.g. guided-mode
  Double / Triple density) stayed visually enabled even when their
  exclusion partner was ticked.
- `data/parameters.yaml` and the manual-mode UI now label the `-h`
  printtarg flag simply "Double density" instead of "Double density
  (for measuring rig)" — the parenthetical didn't fit in the column and
  is already covered in detail by the tooltip.

## v3.7.8
Manual-mode presets now live on disk as plain `.json` files in a per-tab
folder you can browse, copy and share with a normal file manager, and the
printtarg spacer options in Create Chart's Manual module stop fighting
each other when "No spacers" is enabled.

### Features
- **Manual presets stored as `.json` files on disk.** Every saved preset
  in Create Chart, Measure, Build Profile and Check & Refine is now an
  individual `.json` file under
  `~/Library/Preferences/ChromIQ/presets/<Tab>/` on macOS,
  `%APPDATA%\ChromIQ\presets\<Tab>\` on Windows or
  `$XDG_CONFIG_HOME/ChromIQ/presets/<Tab>/` on Linux — one file per
  preset, one subfolder per tab. The preset row in each tab gets a new
  folder-icon button that opens that subfolder in Finder / Explorer. To
  share a preset, copy the `.json` and send it to a colleague; to
  install a shared preset, drop the file into the matching folder on the
  target machine and ChromIQ picks it up on next launch. First launch of
  v3.7.8 silently migrates any presets that were previously kept inside
  the QSettings plist into the new folder, so nothing is lost; the
  legacy key is left in place as a safety net. Malformed files are
  skipped at load time instead of crashing the tab.
- **Mutually-exclusive printtarg spacer options** in the Create Chart
  Manual module. Enabling "No spacers" (`-n`) now automatically greys
  out and excludes "Force B&W spacers" (`-b`) and "Spacer-only scale"
  (`-A`) — both of those only affect spacers, so under `-n` they were
  silent no-ops that still appeared in the printtarg command if
  previously set. The dependent rows become interactive again when
  `-n` is turned off (unchecked, matching the existing `-K` / `-I`
  calibration mutex). Tooltips on all three options now reference the
  relationship.

### Fixes / details
- The "Manual Presets" tooltip dialog in all four tabs documents the
  new folder button, file locations and sharing flow, and was widened
  so the longer body fits without awkward re-wrapping.

## v3.7.7
Polish pass on the v3.7.6 i1Pro clip-border work: the per-chart
"suppress left clip border" toggle is honored again under ChromIQ-style
(was previously hidden and force-on), the right-margin command / notes
stamp now hugs the patch block on sparse charts instead of floating in
empty space, and A3+ portrait is removed from the i1Pro guided paper
list since its landscape twin holds substantially more patches.

_Follow-up to v3.7.6, in response to user feedback from @pharmacist on
the [printerknowledge](https://www.printerknowledge.com) forum._

### Features
- **Suppress-left-clip toggle respected under ChromIQ-style.** With the
  "ChromIQ-style clipping border" preference enabled, the per-chart
  "Suppress left clip border (-L)" control stays visible and functional
  in both Guided and Manual. Unchecked → the branded clip strip applies
  as before (forces `-L` internally, shifts the patches, routes commands
  and notes into a clip-border column). Checked → the border is fully
  suppressed: `-L` passes through, no patch shift, no branded stamp, and
  the targen / printtarg commands and chart notes print on the right
  margin as usual. The toggle now acts as a clean opt-out per chart
  instead of an all-or-nothing preference.

### Fixes / details
- **Right-margin stamp anchored to the patch side.** The targen /
  printtarg command line and chart notes were previously centered inside
  the widest white run right of the patches. On charts whose patch
  block doesn't fill the page (e.g. a small custom target), that run is
  a huge empty area, so centering stranded the text mid-void. The stamp
  now left-anchors to the patch-side edge of the band with a small gap,
  clamped so it can't run past the page edge — it sits snug against
  Argyll's vertical ID column regardless of how much blank space
  follows. Full-page charts are essentially unchanged.
- **A3+ portrait removed from the i1Pro guided paper list.** The
  i1Pro strip reader gets substantially more patches per sheet on the
  landscape variant (483 × 329) than the portrait one (329 × 483) at
  the same physical paper size. A3+ portrait was already excluded for
  i1Pro 3 Plus; do the same for i1Pro, and fall back to the landscape
  variant on instrument switch so the user doesn't drop back to A4
  unintentionally. Manual mode is unchanged.

## v3.7.6
Turns the otherwise-blank i1Pro left clip strip into useful, ChromIQ-branded
chart documentation: a chart summary, a fill-in-the-blank archival form, the
exact targen / printtarg commands, and a spectrum accent — all rotated into
the margin without touching a single patch. An opt-in "ChromIQ-style clipping
border" goes further and manufactures that strip even on charts printed at
full -L width, shifting the patches to make room while guaranteeing none are
clipped.

_Feature requested by @pharmacist on the [printerknowledge](https://www.printerknowledge.com) forum._

### Features
- **Left clip-area info stamp.** When the left clip border is *not* suppressed
  on an i1Pro / i1Pro 2 / i1Pro 3 / i1Pro 3 Plus chart (paper A4 / Letter or
  larger), ChromIQ can fill the reserved clip strip with rotated text columns:
  a one-line chart summary (patch count + paper) and print-driver reminder
  (borderless · 100% size · color management off), plus a fill-in-the-blank
  form line for archival notes — date, printer, ink set, profile name, paper
  type, driver/resolution — with the underscore writing space auto-sized to
  the paper. A thin ChromIQ spectrum bar frames the strip. The patch pixels and
  Argyll's own annotations are never modified. Auto-applies in Guided mode;
  Manual mode adds a "Print info in left clip area" checkbox. Saveable as a
  default (both modes) and inside Manual presets. The row hides automatically
  when the conditions aren't met (wrong instrument, clip border suppressed,
  paper too small).
- **ChromIQ-style clipping border** (Preferences → i1Pro Chart Defaults).
  Replaces printtarg's plain white i1Pro clip strip with the branded version
  above, even when packing patches at full width. It forces `-L` so printtarg
  uses the whole page, then shifts the patch block right inside the TIFF to
  open a fresh strip on the left — capped so the rightmost patch always stays
  on the page (the strip auto-shrinks rather than ever clipping a patch), with
  a 3 mm safety margin. The targen / printtarg commands and chart notes
  (available again in this mode) move into a dedicated clip-border column
  instead of the right margin, and Argyll's vertical right-edge ID text is
  dropped. Patch-count estimates and the grey-ramp sizing use the `-L`-enabled
  capacity to match what actually prints. Takes effect only for i1Pro-family
  instruments on A4 / Letter or larger; otherwise the chart is generated
  normally.

### Fixes / details
- The Create-Chart command preview (both Guided and Manual) now reflects the
  forced `-L` when ChromIQ-style clipping border is enabled, so the previewed
  `printtarg` line matches the command that runs.
- The Measure-tab strip-detection highlighter was verified to work unchanged on
  ChromIQ-style charts — strips track the shifted patch positions and the
  branded clip text does not interfere with column-label detection.

## v3.7.5
Adds a configurable i1Pro chart-layout default to Preferences, rewrites the
tooltips for the most-asked-about Create-Chart options, makes the bottom
command preview track the live target-name field, and extends the patch-
capacity database to cover `-a 0.95` so non-default patch scales now hit
the fast lookup table instead of triggering a live binary search.

### Features
- **i1Pro Chart Defaults setting.** Preferences gains a new combobox under
  the "i1Pro Chart Defaults" group with three presets — `−m 10  −a 0.95`
  (recommended, denser packing), `−m 10  −a 1.0`, and `−m 6  −a 1.0`
  (legacy). The new app default is `−m 10  −a 0.95`: the wider margin
  keeps the strip optics off the bare paper edge that otherwise causes
  "not enough patches read" errors on some printers, and the 5% patch
  shrink fits roughly 9% more patches per sheet. The setting applies
  only when the active instrument is `i1Pro / i1Pro 2 / i1Pro 3` —
  i1Pro 3 Plus, ColorMunki and SpectroScan are unaffected and keep
  their own defaults. Applies to both Guided and Manual mode; changes
  take effect immediately after closing the dialog. A custom margin or
  patch scale you typed in Manual mode is preserved across instrument
  switches — only recognised preset values are overwritten.
- **Patch-capacity database now covers `-a 0.95`.** All 168 new entries
  were measured directly against `printtarg` via two binary-search
  scripts (`scripts/measure_scale095_capacity.py` for i1Pro / i1Pro 3
  Plus across margins 6 mm and 10 mm, `scripts/measure_scale095_cm_capacity.py`
  for ColorMunki with both `-h` states). Selecting `-a 0.95` in Manual
  mode now hits the fast lookup instantly instead of running a live
  binary search every time you tweak the page count.
- **Auto patch-count uses the active patch scale.** Guided mode's
  recommended-patch label and the auto-patch flow in both modes now
  feed `patch_scale` into the capacity lookup, so the recommendation
  matches the actual chart that will be generated.

### Tooltip rewrites
- **Measurement Instrument tooltip** — short bullet for each of the four
  instruments (i1Pro family, i1Pro 3 Plus, ColorMunki / i1Studio /
  ColorChecker Studio, SpectroScan) describing how it reads charts and
  why picking the wrong one fails (e.g. "patches not found" errors).
- **Paper Size tooltip** — explains the portrait-versus-landscape trade-
  off for strip readers, notes which papers are hidden per instrument
  (A3 Portrait for i1Pro, 5×7" / 4×6" for i1Pro 3 Plus) and why, and
  reminds the user that paper-size changes refresh the recommended
  patch and page counts automatically.
- **Number of Pages tooltip** — rough guide for picking a page count
  (1 = quick check, 2–3 = everyday photo printing, 4+ = pro / fine-art)
  with the ink / paper / time trade-off spelled out instead of leaving
  the user to guess. The Manual-mode Auto-page tooltip also explains
  why the Pages spinbox greys out when the Auto checkbox is off.
- **Double Density / Hexagon tooltip** — clearly separates the two
  meanings of the `-h` flag: ColorMunki requires the physical measuring
  rig accessory (called out in caps so the prerequisite is impossible
  to miss); SpectroScan needs no extra hardware and just switches to
  hexagonal patches for ~14% denser packing.
- **Tooltip dialogs are now sized for the new content.** All four
  affected tooltips request `min_width=600` so the longer bodies don't
  get squeezed. `parameters.yaml` learnt an optional `tooltip_min_width:`
  key so the Manual-mode `ParameterWidget` can request the same width
  declaratively, and the dynamic CM ↔ SS relabel path now propagates
  the width too.

### Fixes
- **Patch scale resets to 1.0 when leaving i1Pro in Manual mode.**
  Previously, switching from i1Pro to ColorMunki / SpectroScan / i1Pro 3
  Plus would leave the `-a` widget at whatever the i1pro preset had
  set it to (often 0.95), even though `-a` has no documented use case
  for those instruments. The instrument switch now resets `-a` to 1.0
  alongside `-m`. Custom scales the user typed in (e.g. `0.85`) are
  still preserved — only recognised preset values are overwritten.
- **Bottom command preview shows the actual target name.** The info
  box under each Create-Chart mode used to render `… chart` regardless
  of what was typed into the "Target name" field above. Both previews
  now read the field live as the user types, fall back to `chart` only
  when the field is empty, and prefix `cal_` when the Calibration
  Target checkbox is active so the displayed command mirrors exactly
  what runs at Generate-click. Also fixes an existing minor bug where
  the Guided preview's `targen` line was missing the target-name
  positional argument entirely.
- **Long target names in the preview are truncated with an ellipsis.**
  Names over 32 characters with no whitespace would otherwise force
  the QLabel wider than its container, pushing the whole bottom info
  section out of alignment. The displayed name is now clipped to the
  first 31 characters + `…` once it exceeds the threshold. The full
  name is still used on disk and in the actual `targen` / `printtarg`
  invocations — the truncation is purely cosmetic.

## v3.7.4
Follow-up to v3.7.3 that fixes how the welcome dialog interacts with
the main window's saved size / state on startup, plus a small visual
fix to one of the workflow-card icons.

### Fixes
- **Welcome dialog is now non-modal.** The startup popup used to be
  shown via `dlg.exec()`, which blocks the Qt event loop. On macOS that
  block preempts the OS-level fullscreen / maximize animation triggered
  by `showFullScreen()` / `showMaximized()` during launch, leaving the
  main window at its plain geometry. The dialog now opens via `show()`
  with a stored reference (cleared on close) so it never blocks the
  event loop. A repeat click on the masthead "?" raises the existing
  dialog instead of opening a second one.
- **Explicit state re-apply is now deferred.** `showFullScreen()` /
  `showMaximized()` on launch are scheduled via
  `QTimer.singleShot(0, ...)` rather than called inline immediately
  after `win.show()`. On macOS a same-tick state change request can be
  dropped because the OS hasn't yet processed the show; a 0-timer
  guarantees we run on the next event-loop iteration.
- **Welcome-dialog startup delay reduced to 100 ms.** With the modal
  preemption gone, the 250 ms safety margin from v3.7.3 is no longer
  needed; the dialog just waits for the main window's initial paint.
- **"Measure a chart I already printed" card icon has even spacing.**
  The patches in the strip below the spectrophotometer head were
  drawn with floating-point cell widths that rounded inconsistently,
  producing a visibly wider gap between two of them. The strip is now
  laid out on an integer grid so every patch and gap is identical.

### Welcome-dialog content pass
- **Build my first ICC profile** — step 1 now mentions choosing the
  number of pages alongside instrument, paper and chart name, and
  recommends two or three A4 pages (around 1000–1500 patches with an
  i1Pro) as a sensible starting point — more pages = more patches =
  more accuracy.
- **Build a high-quality profile (2-pass)** — step 1 now explains
  that one page is plenty for the pre-conditioning pass, since that
  profile is throwaway and its only job is to map where the printer
  is most non-linear. Save the paper and ink for the second pass.
- **OS-specific colour-management note** in every print step (first
  profile, 2-pass first and second passes, improve existing). On macOS
  ChromIQ disables driver colour management automatically and the user
  just needs to verify nothing in the dialog re-enabled it; on Windows
  and other systems they still have to switch it off themselves.
- **Build a high-quality profile (2-pass)** — step 3 (measure) now
  contains the full bidirectional-reading and white-surface guidance
  instead of pointing back at workflow 1. Old steps 4 and 5 (build
  first .icc + click "Use as Pre-conditioning Profile") are merged
  into one Build-Profile step. The old combined "Print and measure
  the new chart" step is split into separate print + measure steps,
  each with the full guidance.
- **Improve an existing ICC profile** — steps 2 (print) and 3 (measure)
  receive the same full-text treatment as the other workflows; no more
  "see note in workflow 1" cross-references.
- **Build Profile step no longer mentions algorithm / quality.** Those
  pickers are not visible in guided mode (the default), so beginners
  couldn't act on the advice. Every workflow's Build Profile step now
  suggests filling in the optional metadata fields (Description,
  Manufacturer, Copyright) instead — these *are* visible in guided
  mode and get embedded in the .icc header so colour-management apps
  can identify the profile later.

## v3.7.3
**New help window for first-time users.** ChromIQ now opens a welcome /
help dialog on launch that shows eight clickable workflow cards —
"Build my first ICC profile", "Build a high-quality profile (2-pass)",
"Improve an existing ICC profile", "Print an existing test chart",
"Measure a chart I already printed", "Build a profile from an existing
measurement", "Refine an existing profile" and "Visualise a profile's
gamut". Each card opens a numbered step-by-step walkthrough that names
the exact buttons and settings to use on each tab, tinted by the
spectrum stripe so the badge colour tells you which tab you're on.
Optional steps (the guided refinement loop that follows every build)
render with an outlined badge and dimmed italic body. Re-openable any
time from the magenta "?" button in the masthead, next to the
preferences gear. A "Show this on startup" checkbox in the footer
opts out for return users.

The dialog shipped quietly in v3.7.2 marked as work-in-progress; this
release activates it by default and finishes the content pass.

### Features
- **Help window enabled by default.** First-launch onboarding is now
  active out of the box. Existing v3.7.2 users who toggled the
  "Show this on startup" checkbox keep their preference.
- **New workflow card: "Improve an existing ICC profile".** Walks a user
  who already has a working profile for their printer + paper through
  loading it as a pre-conditioning seed on the Create Chart tab and
  building a noticeably more accurate second profile. Painted icon: a
  filled seed cube → magenta arrow → outlined cube with a magenta "+"
  accent, distinct from the two-cube `two_pass` icon. Grid now lays out
  as 3+3+2, with the bottom row anchored to columns 0 and 2 for
  symmetry with the previous 3+3+1 layout.

### Tweaks
- **Full walkthroughs on every workflow card.** The "Print an existing
  test chart", "Measure a chart I already printed" and the two
  build-from-profile cards used to stop at their named step. They now
  carry the user through the remaining tabs explicitly — Measure → Build
  Profile → optional guided refinement — so a beginner never lands at a
  dead end and has to guess which workflow card to open next.
- **Optional refinement steps visually distinct.** Steps marked as
  optional (the Analyse → re-measure → rebuild → re-analyse loop that
  follows every "Build Profile" workflow) now render with an outlined
  step badge and italic, dimmed body text, separating them from the
  required steps in the same sequence.
- **Chart-naming guidance in step 1.** The two full-build cards now
  suggest a chart-naming convention (`Printer_Paper_Date`, no spaces or
  special characters) since that name carries through to every
  downstream file (.ti2, .ti3, .icc).
- **i1Pro sweep direction clarified.** The bidirectional-reading note
  used to say "down-and-up motion"; corrected to "left-and-right" to
  match how chart strips are actually scanned.
- **Chart backing surface clarified.** Switched from "flat dark surface"
  to "white surface (a plain sheet of paper underneath works)" — a
  coloured or dark backing can bleed through thin stock and skew the
  reading.
- **Build Profile result popup wording fixed.** Steps that described the
  install / jump-to-Check-&-Refine popup were tagged as Tab 5 (Check &
  Refine) even though the popup is shown from the Build Profile tab.
  Folded those steps into the Build Profile step so the badge colour
  matches the tab the popup actually appears on.
- **`two_pass` renamed in the title.** "Build a high-quality profile
  (two-pass)" → "Build a high-quality profile (2-pass)", matching how
  the workflow is referred to elsewhere.
- **Card-icon nudges.** The "Build a profile from an existing
  measurement" icon shifted 5 px up; the "Measure a chart I already
  printed" icon shifted 5 px down — both for a calmer visual fit
  against the card title below.
- **No more `targen` jargon in beginner copy.** The `two_pass` card no
  longer mentions targen's `-c` flag; rephrased to "loaded as the
  pre-conditioning profile" to match the rest of the dialog's
  ChromIQ-doing-things voice.

### Fixes
- **Window maximize / fullscreen state preserved across launches.** The
  welcome dialog opening on startup used to interrupt the main window's
  show transition on macOS, dropping the maximize / fullscreen state and
  leaving the window at its plain saved geometry. Two coordinated fixes:
  `closeEvent` now captures `saveGeometry()` (and an explicit
  `window_maximized` / `window_fullscreen` flag) before `self.hide()`,
  so the snapshot reflects the actual window state; and the welcome
  dialog's startup timer is now 250 ms instead of 0 ms, giving the
  show animation time to complete before the modal blocks the event
  loop. After `show()` the main window also re-applies the explicit
  maximize / fullscreen flag as a belt-and-braces guard.

## v3.7.2
Visual polish across both themes. Window and dialog chrome no longer
reads as pure black in dark mode, and every scrollable panel now
fades softly into its surrounding background at the top and bottom
edges instead of being clipped by a hard line.

### Tweaks
- **Dark-mode chrome moved off pure black.** `QMainWindow`, `QDialog`,
  `QTabWidget` and `QTabBar` now use the panel grey (`#181818`)
  instead of near-black (`#101010`) for their outer surfaces. The
  masthead surround, dialog bodies and the strip behind the tab bar
  no longer ring the content in hard black. Light mode is unchanged.
- **Soft fade at scroll edges.** Every scrollable panel — the four
  parameter panes, the gamut volume controls, and any future modal
  scrolls — now gets a vertical gradient at top and bottom that fades
  scrolled content into the surrounding background colour. The fades
  only appear when content actually overflows and hide at the
  top/bottom extremes so they never sit as decoration on a short
  list. Theme-aware: dark mode fades to `#181818`, light mode to the
  warm `#eeece8`. Implemented as a single `FadeScrollArea` widget
  (`ui/fade_scroll.py`) that picks up its colour from the existing
  `apply_theme()` broadcast.

## v3.7.1
Spinbox button polish — both themes. The up/down buttons on non-compact
spinboxes used to leave a noticeable gap between them at the actual
rendered widget height, and the up-button looked ~2 px shorter than the
down-button because Qt's QSS sub-control rendering rounded the heights
in a way that made the down-button overpaint the up-button's lower
edge. Buttons are now flush, equally tall, and a few pixels wider for
a friendlier click target. Compact spinboxes are unchanged.

### Fixes
- **No more gap between up/down buttons (non-compact spinboxes).**
  The buttons were sized for the 28 px minimum spinbox height, but
  inside form rows the spinbox actually renders at ~38 px, leaving a
  visible empty band between the two buttons. Heights have been
  retuned and `subcontrol-origin` switched from `padding` to `border`
  in dark mode (light mode already used `border`) so each button spans
  exactly half of the rendered widget height.
- **Up and down buttons are now the same visible size.** Qt's stylesheet
  engine was adding 1 px to each button's height, causing a 2 px overlap
  in the middle that the down-button painted over. Heights are now
  tuned so the rendered halves meet exactly with no overlap.

### Tweaks
- **Wider spin buttons.** Up/down buttons grew from 18 px to 22 px wide
  and the spinbox text padding from 20 px to 24 px so the value still
  has room.
- **Light-mode arrow micro-nudge.** Up arrow shifted 1 px up, down
  arrow 1 px down, so each icon sits closer to its respective outer
  edge. Dark mode arrows stay centered. Compact spinbox arrows are
  explicitly reset to centered so the offset is non-compact only.
- **Instrument-port spinbox in Manual measure module widened.** The
  fixed-width compact spinbox on the Measure tab's Manual module was
  clipping its value at the new wider button size. Bumped from 55 px
  to 61 px so the digit, frame, and buttons all fit without
  overlapping.

## v3.7.0
SpectroScan capacity overhaul. The patch-count database underreported
SS+A2 by 13% (4000 → 4592) and had small off-by-N drift on the no-LB
side for several papers; both tables have been re-measured against
Argyll 3.5.0. Hexagon patches (-h) are now a first-class option for
the SpectroScan in both Guided and Pro mode, with capacities measured
across all 14 paper sizes (typically +14% more patches per sheet). The
chart UI has been tidied so each instrument only exposes the printtarg
flags that actually affect its layout, and a state-leak bug that
silently injected -h into SS charts after the user had previously
enabled Double Density on ColorMunki is fixed.

### Features
- **Hexagon patches (-h) exposed for SpectroScan.** A new checkbox
  appears in both Guided ("Hexagon patches (packs ~15% more per
  sheet)") and Pro mode ("Hexagon patches"), with a tooltip that
  reflects the SS-specific semantics (hexagonal layout vs. ColorMunki's
  double-density rig). Patch-count display and Auto-estimation in
  Pro mode both honour the new option; e.g. SS+A4 jumps from 1014 to
  1170 patches per sheet when hex is enabled.
- **SpectroScan hex capacity database.** 14 paper sizes × hex on/off,
  measured by `scripts/measure_ss_hex_capacity.py` (binary-searches
  `targen -d2 -f<n>` + `printtarg -iSS -h ... -t300 -m6 -M6 [-L]` for
  the largest count that still fits exactly one page). Values land in
  both `_PER_SHEET_CAPACITY` and `_PER_SHEET_CAPACITY_NO_LB` because
  SS is a flatbed and ignores `-L`.

### Fixes
- **`-h` no longer leaks into SpectroScan charts.** Previously, if you
  enabled Double Density while on ColorMunki and then switched to
  SpectroScan, the checkbox was hidden but its checked state persisted
  and silently added `-h` to the printtarg command. On SS that
  invokes hexagonal layout (23×45 patches on A4 instead of 26×39),
  visually identifiable by columns running only A–W on a 1014-patch
  chart with three columns of empty space. The visibility logic for
  both Guided (`_update_dd_visibility`) and Pro (`_update_manual_lb_visibility`)
  now force-unchecks `-h` whenever the row is hidden, so the state
  can't survive an instrument switch. The arg builders in
  `workflow/chart_creator.py:_build_printtarg_args` and
  `ui/tabs/tab_chart.py` defensively filter `-h` to instruments where
  it's meaningful (CM, SS) and `-L` to strip instruments (i1, p3) so
  even a stale param dict can't reintroduce a no-op flag into the
  command stamped in TIFF metadata.
- **SpectroScan + A2 patch count was 13% under reality.** The
  `_PER_SHEET_CAPACITY` row read 4000 patches/sheet, but printtarg
  actually packs an 82×56 grid = 4592 on A2 with the default margin.
  Re-measured against Argyll 3.5.0 by `scripts/measure_ss_capacity.py`
  and corrected. Smaller no-LB drift on A3/Legal/A4/A4R/Letter/LetterR
  (each off by 1–4) was also corrected; all SS rows now agree between
  the with-L and no-LB tables because SS is `-L`-independent (flatbed
  reads individual patches, not strips).
- **Suppress-left-clip-border (`-L`) hidden for SpectroScan and
  ColorMunki.** It already had no effect on either instrument's
  layout but the checkbox was visible for SS, which was confusing.
  Now only strip instruments (i1, p3) expose the option in both
  Guided and Pro mode.
- **Dynamic relabelling for the `-h` row.** ParameterWidget gained
  `set_display_text(label, tooltip_title, tooltip_body)` so the same
  underlying widget can advertise *"Double density (for measuring
  rig)"* on ColorMunki and *"Hexagon patches"* on SpectroScan,
  matching what the flag actually does for each instrument. Tooltip
  title and body update in lockstep with the label.

## v3.6.7
Light-mode polish across the parameter panels and the Check/Refine
gamut viewer. Every combobox and spinbox body now renders white in
light mode (matching the QLineEdit path fields next to them) and
`BG_INPUT` in dark mode (matching dark-mode QLineEdits), instead of
inheriting the warm-cream surface of the GroupBox they sit inside.
The gamut viewer no longer shows the thin dark line at the top and
left edges in light mode.

### Fixes
- **Light-mode combobox & spinbox bodies are now white when enabled.**
  Two root causes had to be addressed together. (1) The QSS rule
  `QGroupBox { background: LM_BG_SURFACE }` in `ui/light_styles.py`
  was being propagated by Qt's QStyleSheetStyle into descendants'
  `palette.Base`, so every QComboBox / QSpinBox / QDoubleSpinBox body
  inherited the cream section colour — proven via a diagnostic that
  showed `widget.palette().base() = #f7f4ef` on enabled inputs
  despite the input QSS rule setting `background: #ffffff`. The QSS
  rule has been removed; the cream surface is now repainted by a
  new `GroupBoxSurfaceFilter` in `ui/widgets.py` that runs on every
  QGroupBox Polish event and calls `setAutoFillBackground(True)` +
  `palette.Window = LM_BG_SURFACE`. That mechanism does not
  contaminate descendants' Base role, so input widgets inherit the
  app palette's white Base again. `MainWindow.apply_theme` calls
  `reapply_groupbox_surface()` on every theme switch so light↔dark
  toggles update correctly. (2) Even after the contamination was
  fixed, the bodies rendered the warm-grey LM_BG_WIDGET because
  Fusion's `PE_PanelButtonCommand` paints a gradient using
  palette.Light/Mid/Button. Diagnostics on `drawPrimitive`,
  `drawComplexControl`, and `drawControl` overrides in the
  `WinButtonLayoutStyle` QProxyStyle confirmed Qt's QSS engine
  handles QComboBox / QSpinBox painting entirely internally for
  compound widgets and never delegates to the base style — and
  per-widget `setPalette()` calls were being silently reset by the
  QSS engine on the next polish cycle. The fix that did stick is a
  per-widget stylesheet attached in each NoScroll wrapper's
  `__init__`:
  `QComboBox:enabled, QSpinBox:enabled, QDoubleSpinBox:enabled
  { background-color: <palette.base> }`. Per-widget stylesheets
  bypass the QStyleSheetStyle quirk that affects app-wide rules.
  `reapply_input_stylesheet()` rewrites the rule with the current
  theme's `palette.base()` on every `apply_theme()` call, so dark
  mode picks up `#1f1f1f` and light picks up `#ffffff` without
  flicker. The `:enabled` selector scoping leaves the disabled-state
  appearance unchanged.
- **Dark line on the top and left of the gamut viewer in light mode.**
  Two contributing causes addressed. (1) X3DOM applies a default
  2 px dark border to the `<x3d>` element; the wrapper bumps the
  height to `100vh`, so the right and bottom edges were clipped by
  `overflow: hidden` but the top and left remained visible. The
  injected `<style>` in `workflow/gamut_viewer.py:_patch_html()` now
  zeroes border, outline, margin, and padding on `<x3d>` and its
  inner canvas so the X3DOM-supplied border no longer paints at all.
  (2) The wrapper widget in `ui/gamut_panel.py:_make_viewer_widget()`
  used `setContentsMargins(0, 1, 1, 1)` with `border-left: none`, so
  the QWebEngineView sat flush against the container's left edge
  with no frame-bg buffer to hide Chromium surface-edge artefacts.
  The contentsMargins are now symmetric `(1, 1, 1, 1)`; `border-left:
  none` is preserved so the "open on the left" design intent toward
  the splitter handle stays the same.

## v3.6.6
Dialog button-layout polish across the Check/Refine and Build Profile
tabs. Every result dialog now uses the same arrangement: action buttons
clustered on the left with an 8 px gap between them, and the
dismissal button (**Close** or **Done**) pinned to the right edge of
the window — instead of the previous "everything spread evenly" or
"everything grouped right" layouts that made the dismiss button land
in a different place each time the dialog opened. Also fixes one
button arrow that pointed the wrong way and wires the macOS bundle's
version into the OS-level *About ChromIQ* menu item.

### Fixes
- **Profile Quality Assessment dialog button layout.** The button row
  in `ui/tabs/tab_check_refine.py` previously used `addStretch()`
  between every button, so the Close button drifted to a new
  horizontal position every time the dialog opened with a different
  combination of action buttons (Install Profile, Use as
  Pre-conditioning, Guide Me Through Refinement). The layout now adds
  the action buttons first with an 8 px gap, a single stretch, then
  the Close button — yielding a consistent "actions left, Close right"
  arrangement that also right-aligns Close when it is the only button
  shown. Styling via `tint_dialog_primary()` is unchanged, so primary
  accent buttons continue to render correctly in both themes.
- **Build Profile result dialogs pin Done to the right edge.** The
  three result dialogs in `ui/tabs/tab_profile.py` (Apply Calibration
  result, Calibration File Created, Profile Built) all used
  `QDialogButtonBox` with ActionRole + AcceptRole buttons, which on
  macOS groups every button together on the right side of the row.
  Each now uses the same manual `QHBoxLayout` pattern as the
  Check/Refine fix: action buttons (Install, Pre-conditioning, Check
  Profile Quality, Apply Calibration, Go to Create Chart) clustered
  left with an 8 px gap, a single stretch, then Done on the right.
  `done_btn.setDefault(True)` preserves the Enter-key activation that
  `QDialogButtonBox` provided automatically; QDialog's built-in
  Escape-to-reject handling continues to work unchanged. Each
  dialog's `setMinimumWidth()` was bumped (520→580, 560→600,
  640→740 / 700→880) so the new stretch space has room without
  squeezing buttons.
- **Calibration File Created button arrow flipped.** The
  *Go to Create Chart →* button in `_show_printcal_result_dialog()`
  is now labelled **← Go to Create Chart** — the Create Chart tab
  sits to the *left* of Build Profile in the main tab strip, so the
  arrow on the left of the label pointing left matches the existing
  navigation convention used by `← Use as Pre-conditioning` and the
  forward-pointing `Check Profile Quality →` / `Apply Calibration →`.
- **macOS *About ChromIQ* menu now shows the version.** `main.py`
  set `QApplication.setApplicationName()` and
  `setApplicationDisplayName()` but never called
  `setApplicationVersion()` — so macOS's auto-generated *About
  ChromIQ* menu item, which reads
  `QCoreApplication.applicationVersion()`, displayed an empty version
  field. `APP_VERSION` is now imported from `core/version.py` and
  passed to `setApplicationVersion()`. The bundle's Info.plist already
  carried the version (`CFBundleShortVersionString` /
  `CFBundleVersion`, both set from `APP_VERSION` by `ChromIQ.spec`),
  so Finder *Get Info* and the masthead always showed it — this fixes
  the one place that didn't.

## v3.6.5
Polish patch with three visual fixes and one default flip. The
gamut viewer now reliably picks up ChromIQ's tinted accent colours
on every profile and the combined view's illumination is back to
normal, the main tab bar's active-tab colour no longer bleeds into
the next tab (and now reads symmetrically in both themes), the
Settings dialog's Restore Factory Defaults button is readable in
Light mode, and Manual measurement defaults the bidirectional-strip
checkbox off so the instrument can read strips in either direction
without configuration.

### Fixes
- **Gamut viewer colours now reliably tinted on every individual
  profile.** The JS-side ChromIQ accent remap in
  `workflow/gamut_viewer.py:_THEMED_JS` ran at `DOMContentLoaded`,
  but X3DOM had already parsed and cached the GPU buffers via a
  body-script-triggered init by then — so individual profile views
  often showed iccgamut's default colours, while the combined view
  accidentally worked thanks to a second mutation pass from
  `_COMPARE_CONTROLS_JS` at +150 ms. The remap now runs in Python
  via `_apply_chromiq_colors()` against the raw X3D markup before
  X3DOM ever sees the file; the JS only handles the `<Background>`
  node (which has to stay runtime-driven because it reads the CSS
  body background to follow live Light/Dark switches). Mirrored in
  `workflow/viewgam_runner.py` for the combined view. A new
  `_L_CAP = 0.92` clamp keeps the gamut's white tip visibly tinted
  with the accent hue instead of blowing out to pure white.
- **Combined-profile gamut view is no longer doubly-lit.** When
  iccgamut's compare scene was merged into the primary scene as an
  overlay group in `workflow/viewgam_runner.py`, its scene-level
  `DirectionalLight` nodes carried over too — six on top of
  primary's six, roughly doubling illumination on every shape in
  the combined view and making both profiles look much brighter
  than they do alone. New `_strip_scene_level_dupes()` removes
  `Background`, `NavigationInfo`, `Viewpoint`, `Environment`, and
  all three `Light` subtypes from the compare scene before
  merging, so only the gamut geometry carries over.
- **Main tab bar's active-tab colour no longer bleeds into the
  next tab.** `SpectrumTabBar.paintEvent` in
  `ui/spectrum_tab_bar.py` painted every per-tab fill (active body,
  body tint, top accent strip, inactive hint, disabled overlay)
  using `tabRect(i).width()`, which — with `setExpanding(True)`
  plus a custom `tabSizeHint` of `total // n` — produces tabRects
  whose right edge lands on the next tab's first pixel. Each fill
  now reserves 1 px on the right of every tab except the last
  (`paint_w = rect.width() - right_inset`), so the accent strip
  and active body stop cleanly before the separator instead of
  crossing it.
- **Active-tab overlay 1 px shift, per theme.** Building on the
  bleed fix above, the active colour overlay had a residual 1 px
  asymmetry: in Light mode the right edge read as overshooting the
  white body by 1 px; in Dark mode the left edge read as falling
  1 px short of the visible active region. Both observations
  describe the same physical pixel arrangement but contrast
  against opposite-colour reserved columns in each theme. The
  active overlay (body + tint + top accent strip + underline glow)
  now applies a mode-specific 1 px shift: Light mode shrinks the
  right edge by 1; Dark mode (non-first tab) extends the left edge
  by 1 into the previous tab's reserved column. First tab in Dark
  mode is left flush — there's no previous tab to extend into.
- **Restore Factory Defaults button is readable in Light mode.**
  The button in `ui/dialogs/settings_dialog.py` had a hard-coded
  inline `setStyleSheet` of `#f4f4f4` background / `#121212` text
  — i.e. near-white on the near-white settings dialog. Removed
  the inline rule, added `setObjectName("reset_defaults")`, and
  moved the styling into the theme stylesheets. Light mode now
  uses inverted colours (dark `#121212` background, bright
  `#f4f4f4` text) so the button stands out against the warm
  dialog surround; Dark mode keeps the prior light-on-dark
  appearance unchanged. Same dialog: the appearance combo is now
  a `NoScrollComboBox` so accidental scroll-wheel events don't
  change the theme.

### Behavior changes
- **Manual measurement defaults bidirectional-strip recognition
  to enabled.** Under Measure → Manual → Measurement Options,
  "Disable bidirectional strip recognition (-B)" used to ship
  checked by default — meaning chartread always expected strips
  scanned in one direction. It now ships unchecked, so the
  instrument can auto-detect scan direction without
  configuration. Affects the initial UI default
  (`ui/tabs/tab_measure.py:881`), the preset-restore fallback,
  the settings-restore fallbacks, and the
  `MeasureParams.disable_bidir` dataclass default in
  `workflow/measure_manager.py`. The hardcoded tooltip is
  rewritten to match: enable only if chartread repeatedly flags
  the wrong scan direction. The corresponding YAML entry in
  `data/parameters.yaml:-B` and its tooltip were also updated to
  match. Guided-mode bidirectional default is unchanged.

## v3.6.4
Light-mode polish patch covering the gamut viewer and a few widgets
whose colours had drifted from the masthead wordmark. No
workflow-affecting behaviour changes.

### Fixes
- **Gamut viewer 3D scene background now matches the panel frame in
  both modes.** `iccgamut -w` and `viewgam` emit X3DOM HTML with no
  `<Background>` node, so X3DOM fell back to its default near-black
  sky. The HTML body CSS was already theme-aware (`#efebe6` Light /
  `#111111` Dark, patched by `workflow/gamut_viewer.py:_patch_html`),
  but the X3D canvas (which fills the entire viewer at `height:
  100vh`) drew over it with the X3DOM clear colour — so in Light mode
  the gamut panel was dominated by a black canvas that clashed with
  the surrounding warm-beige frame. The injected `_THEMED_JS` now
  reads `getComputedStyle(document.body).backgroundColor` and ensures
  a `<Background>` element exists inside `<scene>` with both
  `skyColor` and `groundColor` set to that value — sky + ground both
  matter because X3D backgrounds are two hemispheres and setting only
  `skyColor` leaves the ground at default pure black, producing a
  half-black horizon split. Mirrored into `workflow/viewgam_runner.py`
  for the combined-profile view. Theme switches re-apply via the
  existing `_apply_mode_styles()` reload path in `ui/gamut_panel.py`
  without re-running iccgamut/viewgam.
- **Opacity / saturation slider grooves now use the wordmark colour
  in Light mode.** Both sliders in the gamut viewer's compare-mode
  controls (`ui/gamut_panel.py`) had the unfilled track hardcoded to
  `#333333` — a cool mid-grey that read as out of place against the
  warm Light-mode palette. The track is now generated by a new
  `_slider_stylesheet()` helper that returns `#1c1b18` in Light mode
  (the masthead "Chrom" wordmark) and keeps `#333333` in Dark mode
  (a white groove against the dark surround would clash). Re-applied
  from `_apply_mode_styles()` so theme switches update the groove
  live without restarting the panel.
- **Settings dialog checkboxes and path-field focus borders no
  longer inherit the global ACCENT cyan.** The previous dark-mode
  block at `ui/dialogs/settings_dialog.py:317–325` cleared the local
  override (`setStyleSheet("")`) expecting the global APP_STYLESHEET
  to take over, but that stylesheet sets `QCheckBox::indicator:
  checked` and `QLineEdit:focus` to `ACCENT = SPEC_CYAN = #37bcd6`
  — which happens to equal the Build Profile tab's accent stop and
  read as if a per-tab tint were leaking into the dialog. The dialog
  now always applies an explicit indicator colour: `#1c1b18` (Light,
  the masthead wordmark) and `#d0d0d0` (Dark, the same neutral grey
  as the Restore Factory Defaults button border). The dialog never
  picks up an accent regardless of which tab is active or how
  `resolve_mode()` resolves on a given open. Light-mode behaviour was
  briefly off by a hex (`#22211F` instead of `#1c1b18`) — both modes
  now anchor to the actual wordmark values.
- **Create Chart "Calculated Patches" big number now anchors to the
  wordmark colour, not the per-tab accent.** The per-tab QSS
  injector in `ui/main_window.py` was setting
  `QLabel#patch_count { color: {color}; }` in Dark mode, where
  `color` is the active tab's spectrum stop — so on Create Chart the
  56 px Georgia patch count rendered as magenta `#ff4573`, not the
  white the spec calls for. Light mode used `#22211f`, also adjacent
  to but not the same as the wordmark. Both modes now set
  `patch_count_color` to the wordmark hex for their palette
  (`#1c1b18` Light / `#ffffff` Dark), so the big number reads as a
  text anchor under the chart parameters instead of as a tab tint.

## v3.6.3
Polish patch covering three small but visible items: Light-mode log
text is now readable across all four tabs, the Measure tab's
existing-`.ti3` checkbox is honest about supporting both refine and
resume, and the macOS app bundle's Info.plist no longer reports the
wrong version in Finder Get Info / About. No workflow-affecting
behaviour changes.

### Fixes
- **Light-mode log text now hue-preserved but darkened per tab.**
  New `_darken_for_light_log()` helper in `ui/main_window.py`
  converts the tab's accent hex into HSL, drops lightness to ~55 %
  of the original (floor 0.22), tames fully-saturated inputs from
  S=1.0 down to 0.70 so violet doesn't crush into deep indigo, and
  applies a small saturation floor (0.75) for medium-sat hues with
  an extra bump (0.92) in the cyan/blue band (0.48 ≤ H ≤ 0.60) so
  the Build Profile tab's teal stays vivid. Resulting per-tab log
  colours: Create Chart `#8c6318` (amber), Measure `#149061`
  (green), Build Profile `#05778e` (teal), Check & Refine
  `#421fb3` (violet). All four land comfortably above the 4.5:1
  WCAG contrast threshold against the log background while staying
  recognisably the same hue family as the tab accent. The QSS
  injector already re-runs on every Light ↔ Dark switch
  (`apply_theme()` calls it directly), so the colour swaps live
  without an app restart. Dark mode is unchanged.
- **Measure tab — "Refine / resume existing measurement (-r)".**
  The chartread `-r` flag covers both re-measuring problem strips
  and continuing an interrupted measurement, but the checkbox label
  in both the Guided and Manual modules only advertised "Refine".
  The post-interruption log message at
  `ui/tabs/tab_measure.py:2475` already pointed users at this same
  checkbox to resume, so the label was actively misleading. Renamed
  the checkbox and its TooltipButton title in both modules, reworded
  the tooltip body's opening line from "Resumes from the existing
  .ti3 file…" to the neutral "Reuses the existing .ti3 file…" so
  it doesn't bias toward one of the two cases, and updated the log
  message string to quote the new label. Body text already mentioned
  both use cases ("re-measure problem strips" and "continue a
  measurement that was interrupted") and stays otherwise unchanged.
- **macOS bundle Info.plist now reports the real version.**
  `ChromIQ.spec` had `CFBundleShortVersionString` and
  `CFBundleVersion` hardcoded to `'3.5.0'`, so every release since
  3.5.0 shipped a bundle that displayed the wrong version in Finder
  Get Info, the macOS "About" sheet, and any system-level version
  query (Spotlight, mdls, etc.) — even though the in-app masthead,
  Settings dialog and log header all read `APP_VERSION` correctly
  via `core/version.py`. The spec now `exec()`s `core/version.py`
  at build time and feeds `APP_VERSION` into both plist keys, so the
  bundle version follows `APP_VERSION` automatically on every
  future release with no second place to remember to bump.

## v3.6.2
Quality-focused patch for the Build Profile tab. Adds the two CIECAM02
viewing-condition flags that `colprof` needs to build correct
perceptual / saturation gamut-mapping tables when a Gamut Source is
supplied, replaces a cluster of three checkboxes in the Manual
gamut-mapping section with one combobox + standalone checkbox, and
flips the default Gamut Source to ClayRGB1998 (Argyll's bit-for-bit
AdobeRGB 1998 equivalent) so fresh installs match the source profile
serious print workflows actually use. Tooltips across the section are
rewritten as plain-English paragraphs and given enough horizontal
room to read.

### New
- **CIECAM02 source / destination viewing conditions (`-c` / `-d`)
  in Manual mode.** Two new combo rows in the Manual panel's Color
  Science group, directly under FWA, exposing the full list of
  colprof viewing-condition presets — `pp` (practical office print),
  `pc` (critical print booth), `mt` (monitor in typical work
  environment), `md`/`mb`, `jm`/`jd` (projector), `pcd`, `ob`, `cx`,
  plus the two `pe` variants. Empty default keeps current behaviour;
  set them to e.g. `mt` (source) + `pp` (destination) and the
  emitted command picks up `-cmt -dpp`, matching the reference
  invocation pros use. This is the bit that materially affects
  profile quality when a Gamut Source profile is supplied via
  `-s`/`-S` — without `-c`/`-d`, colprof falls back to generic
  viewing-condition defaults that don't match any real
  screen-to-print workflow, and the perceptual / saturation tables
  end up wrong. New `src_viewing_cond` / `dst_viewing_cond` fields
  on `ProfileParams` flow through `_build_args` via the same
  `f"-c{val}"` / `f"-d{val}"` no-space append pattern used by
  `-a` / `-q` / `-V`. Wired through all five Manual save/restore
  sites (collect, preset save, preset restore, save-defaults, both
  default-restore paths) so the choice round-trips through named
  Manual presets and the Save-as-Defaults flow. Guided panel
  untouched.
- **Colorimetric-gamut combobox replaces the `-nP` / `-nS`
  checkboxes in Manual mode.** The two side-by-side checkboxes
  (`-nP` "Use colorimetric gamut — perceptual" and `-nS` "Use
  colorimetric gamut — saturation") collapse into one combobox
  with four entries: *Gamut mapping for both* (default), *-nP
  only*, *-nS only*, *-nP -nS* (both intents colorimetric). Every
  combination the old checkboxes could express remains reachable
  — verified end-to-end against the emitted command line. `-nI`
  (Inverse gamut mapping) is conceptually orthogonal (it controls
  B2A inversion, not which gamut shapes an intent) and stays as
  its own checkbox on a second row. Two tiny helpers,
  `_m_colorimetric_combo_values` and `_m_set_colorimetric_combo`,
  translate between the combo's `(bool, bool)` userData and the
  two existing `ProfileParams.no_perc_gamut` / `.no_sat_gamut`
  booleans, so `_build_args` is unchanged and **existing Manual
  presets and saved defaults round-trip into the new combo
  without a migration step** (the on-disk preset JSON and
  `manual2_colprof_no_perc_gamut` / `_no_sat_gamut` /
  `_inv_gamut` settings keys keep their existing names and
  shapes).

### Changed
- **ClayRGB1998 is now the default Gamut Source.** Fresh installs
  now point the Gamut Source path at `ref/ClayRGB1998.icm` (Argyll
  ships this as its bit-for-bit AdobeRGB 1998 equivalent —
  identical R/G/B primaries, gamma 2.2, D65 white point; renamed
  because Adobe won't license the "AdobeRGB1998.icc" name for
  redistribution). Previously the default was `ref/sRGB.icm`. The
  switch matches how serious print workflows actually drive
  colprof: AdobeRGB is the working space photo apps default to,
  and an AdobeRGB-sourced profile renders sRGB images correctly
  too (sRGB fits entirely inside AdobeRGB), while the reverse —
  AdobeRGB images through an sRGB-sourced profile — clips wide
  hues. `_default_gamut_src()` now tries
  `ref/ClayRGB1998.icm → ref/sRGB.icm → assets/profiles/ClayRGB1998.icm →
  assets/profiles/sRGB.icm`, so installs with an older Argyll
  layout still get a sensible default. **Existing users with a
  saved Gamut Source path are untouched** — the new default only
  fires when the user has never saved a value.
- **Bundled `assets/profiles/ClayRGB1998.icm`** alongside the
  existing bundled `sRGB.icm`, on the same Argyll-AGPL
  redistribution basis. `ChromIQ.spec` already bundles the whole
  `assets/` directory, so the new file is packed into frozen
  builds without any spec change.
- **Gamut-mapping tooltips rewritten and widened.** All five
  tooltips touched in this area (`-c`, `-d`, the new colorimetric
  combo, `-nI`, and the Gamut Source `-s`/`-S` description) are
  rewritten as plain-English paragraphs separated by `\n\n` —
  Qt word-wraps each paragraph automatically, so the previous
  hand-wrapped-every-70-chars style was actively fighting the
  auto-wrap when the dialog widened. `min_width` is bumped to
  540–580 px on the long bodies (the `_InfoDialog` cap is
  `max(min_width + 160, 720)`, so passing the larger min gives a
  comfortable ~720 px wrap width). Each new body explains what
  the flag does, when it matters, and which preset to pick for
  the common photographic workflow.

### Fixes
- **"Browse to AdobeRGB.icm in the Argyll ref folder" hint no
  longer points at a non-existent file.** Four places (Manual +
  Guided Gamut Source tooltips, both path-edit placeholders) used
  to advise the user to browse to `AdobeRGB.icm`, which Argyll
  doesn't ship — Adobe doesn't license the name for
  redistribution, so the file is called `ClayRGB1998.icm`
  instead. Updated all four to name the file that actually
  exists, with a one-paragraph note in each tooltip explaining
  why ClayRGB1998 = AdobeRGB so users aren't thrown by the
  unfamiliar name.

## v3.6.1
Follow-up release after v3.6.0 — fixes a visible strip-highlighter
drift during chartread on charts with letters that have thin
crossbars (notably "H") and on multi-character labels (AW, AX, … on
later pages), adds the missing targen `-n` (Neutral Axis Steps) flag
in Manual mode, and finishes the light-mode polish that v3.6.0 left
incomplete around the gamut viewer, parameter dialogs, and disabled
input states.

### New
- **targen `-n` (Neutral Axis Steps) in Manual mode.** New expert
  parameter under Create Chart → Manual → targen, immediately after
  Pre-conditioning Profile (`-c`) since the two work together. Adds
  extra wedge patches along the perceptually-true neutral axis of
  your printer + paper as defined by the pre-conditioning profile,
  rather than the device-space grey ramp that `-g` walks. Useful
  for refinement passes once you already have a first-pass ICC
  profile loaded under `-c`. Tooltip body spells out the
  distinction between `-n` (profile-derived steps), `-g` (device
  RGB ramp), and `-N` (neutral-axis emphasis dial) with worked
  examples. Auto-wires through Save-as-Defaults, the Default
  preset, and named preset save/restore via the existing YAML-driven
  `_manual_widgets` pipeline — no extra plumbing.
- **Live command preview in Manual mode.** A footer info box at the
  bottom of the Manual scroll area now mirrors the guided info box,
  showing the exact `targen` and `printtarg` commands the workflow
  will run, built from the current ParameterWidget state via the
  same `_build_targen_args` / `_build_printtarg_args` logic.
  Updates live on any parameter change (instrument, paper,
  double-density, `-L`, patch scale, margin, 16-bit toggle, pages
  spin, auto-patches toggle). Importantly the preview reflects the
  auto-bumped i1Pro margin (`-m10 -M10`) even though the margin
  widget is expert-only — by mirroring the actual collector instead
  of `ParameterWidget.build_args()` it shows what runs, not just
  what's user-enabled.

### Fixes
- **Strip highlighter no longer drifts after letter "H" or with
  two-character labels.** The TIFF strip-detection algorithm in
  `_detect_stripe_rects` previously split labels with thin
  horizontal crossbars (the letter "H" is the canonical case) into
  two clusters because the column-dark merge gap
  (`max(3, aw // 200)`, ≈4 px at the 1000-px analysis width) was
  tighter than the gap between the two vertical strokes of "H" at
  that scale. From "H" onwards every subsequent strip was off by
  one — reading "J" highlighted "I". The merge gap is now
  `max(8, aw // 100)` (≈10 px at aw=1000), comfortably above
  intra-letter gaps (~5 px) and well below inter-letter gaps
  (~22 px). On top of that, the detector now runs a **median-pitch
  + endpoint regularisation** pass: it computes the median
  centre-to-centre gap, trims leading/trailing clusters whose
  neighbour gap is < 60 % of the median (likely spurious edge
  marks), and resamples a uniform grid between the remaining
  endpoints with `round((right − left) / pitch) + 1` strips.
  Validated end-to-end on three-page A4 charts where page 3 uses
  two-character labels (AW AX AY … BT) — all three pages now
  detect 24 strips with column centres aligned to within 1–2 px.
  Hard-clamped to ±25 % of the raw cluster count as a sanity bound.
- **Settings dialog focus + checkbox colours follow the active
  theme.** The dialog previously hardcoded a near-white focus
  border and indicator fill that read fine in dark mode but
  appeared as low-contrast pale-on-pale in light mode. Now resolves
  the active appearance via `ui.theme.resolve_mode` and either
  applies an ink-coloured (`#22211F`) light variant or drops the
  local override so the global stylesheet cascades through in dark
  mode.
- **Tooltip dialog text colours follow the active theme.** The
  `TooltipButton → _InfoDialog` heading + body were hardcoded to
  white / light-grey and disappeared on the light-mode info-dialog
  background. Now `#22211F` in light mode, original palette in
  dark.
- **Gamut viewer page + frame backgrounds follow the active theme.**
  The WebEngine page background, the surrounding
  `QWidget#gamutViewerFrame`, and the "no data" fallback label all
  baked `#111111` directly. They now read the panel's mode
  (`_current_bg()`) and switch to `#efebe6` in light mode with a
  matching `#d0ccc6` border. The viewer also re-patches the
  background of already-rendered HTML files on theme switch via a
  new `repatch_background()` helper in `workflow/gamut_viewer.py` —
  flipping themes mid-session refreshes the X3DOM canvas without
  re-running `iccgamut`. The `bg` colour is plumbed through
  `GamutViewer.run()` and `ViewgamRunner.run()` so freshly-rendered
  HTML is patched with the right colour from the start.

### Improvements
- **Disabled inputs are visibly greyed in light mode.** Added
  `:disabled` QSS for `QLineEdit`, `QSpinBox`, `QDoubleSpinBox`,
  `QComboBox` (text + chrome dim to `LM_TEXT_FAINT` /
  `LM_BG_SURFACE`), and for `QLabel#param_label` /
  `QCheckBox#param_label` (`#6a6a6a` in dark, `LM_TEXT_FAINT` in
  light), so the off state is obvious in both themes.
  `ParameterWidget` was refactored to route enable/disable through
  a single `set_control_enabled(enabled)` helper that toggles the
  control, the browse button, **and** the row label together —
  without this the label's `:disabled` selector never matched
  because labels weren't being disabled.
- **Log widget uses a bolder mono font in light mode.** Switched to
  `JetBrains Mono` → `Menlo` → `SF Mono` → `Courier New` with
  weight 800 in light mode. Because Qt's QSS `font-weight` doesn't
  always reach a `QPlainTextEdit`'s underlying document on Windows,
  the weight is also pushed via `QFont` directly in `_apply_theme`
  on every theme switch — both the widget font and the
  `QTextDocument` default font are bumped, so the heavier weight
  survives the per-tab QSS re-injection that runs right after.

### Internal
- **`debug_highlighter` setting (default off).** New diagnostic
  flag in `core/settings.py` that, when true, makes
  `_on_stripe_changed` log one line per strip update to both the
  in-app log widget and `chromiq.log` (id, letter, global_idx,
  strips_per_page, page, local_idx). Used to confirm the
  strip-drift diagnosis above; left in place for future detection
  debugging. Page index is rendered 1-based in the log message for
  readability while the internal `page` variable stays 0-based.

## v3.6.0
First minor-version bump in the 3.x line: ChromIQ now ships a full
**Light Mode**, selectable as Light, Dark, or System (Auto) from a new
Appearance picker in Preferences. Auto follows the macOS Appearance
setting and re-skins live when the user flips it. Beyond the new
theme, the guided Measure panel ships with a slightly safer
patch-tolerance default and a long-standing Qt startup warning about
missing font families is gone.

![ChromIQ in Light Mode — Create Chart tab](docs/v3.6.0-light-mode.png)

### New
- **Appearance: Light / Dark / System (Auto).** A new `ui/theme.py`
  central applier wraps every theme switch: it selects the palette
  (`make_dark_palette` / `make_light_palette`) and stylesheet
  (`APP_STYLESHEET` / `LIGHT_STYLESHEET`) for the requested mode,
  broadcasts a `set_appearance(mode)` call to every descendant widget
  that opts in, retints the macOS title bar via NSAppearance
  (`Aqua` for light, `DarkAqua` for dark), and re-runs the per-tab
  QSS injector so its hardcoded primary-button and mode-button
  colours track the new theme. The setting persists under
  `appearance` in `core/settings.py` (defaults to `auto`). Auto
  resolves to light/dark via `QStyleHints.colorScheme()` and listens
  for `colorSchemeChanged` in `main.py`, so flipping macOS System
  Settings → Appearance re-skins ChromIQ without restart.
- **Preferences → Appearance picker.** A new `QGroupBox("Appearance")`
  in `ui/dialogs/settings_dialog.py` exposes a single combobox with
  three items — System (Auto) / Light / Dark. Changes preview live;
  OK persists, Cancel reverts to whatever was saved when the dialog
  opened.
- **Full v2 light visuals.** Beyond palette + QSS, the light variant
  re-tints surfaces that paint outside the global stylesheet: the
  `MastheadHeader` swaps to a warm-white header with dark wordmark,
  the `SpectrumTabBar` paints active tabs `#ffffff` / `#22211f` and
  inactive `#e5e2dd` / `#989490`, the `TiffPreview` and `GamutPanel`
  use a `#efebe6` viewer fill (with the WebEngine page background
  matched so the X3DOM canvas doesn't flash dark on first paint),
  the terminal `QPlainTextEdit#log` uses a pale-green
  `#f4f8f5 / #2a6e2a` palette, and `assets/folder/folder_light.svg`
  drives a `#22211f`-tinted folder icon in the Preferences dialog
  (recoloured at load time from the same PNG mask used by the dark
  variant so the line work matches exactly).

### Improvements
- **Patch consistency tolerance default → 0.7.** The guided Measure
  panel now ships with `-T 0.7` instead of `0.5`. The previous
  default was tuned for lab-grade conditions on an i1 Pro 2/3; in
  the field on consumer inkjet + cheaper colorimeters it produced
  too many "inconsistent patch" interruptions. 0.7 still catches
  real ink/printer faults while leaving more headroom for paper
  texture and slight scanning-speed variation. Updated in three
  places — `core/settings.py`, the guided panel's hardcoded init in
  `ui/tabs/tab_measure.py`, and the tooltip body / `parameters.yaml`
  documentation that referenced the old number.

### Other
- **No more `qt.qpa.fonts: Populating font family aliases …` at
  startup.** The QSS font-family chains in `ui/styles.py` and
  `ui/light_styles.py`, plus the `QFont.setFamilies(...)` calls in
  `ui/spectrum_tab_bar.py`, used to list `system-ui`,
  `-apple-system`, `Segoe UI`, `Helvetica Neue`, and the generic
  `sans-serif`. Qt's parser treats every entry as a literal family
  name (no CSS-generic resolution) and pays a ~73 ms alias lookup
  for each one it can't find on the current platform, then prints a
  warning. Trimmed down to just `"Inter"`, which is bundled and
  registered via `QFontDatabase.addApplicationFont(...)` in
  `main.py`, so Qt finds it on the first try, falls back to its
  own default sans-serif if the application font ever fails to
  load, and no longer warns or stalls on startup.

## v3.5.13
Small visual addition to the Measure preview. The green
downward-pointing triangle that marks the active strip at the top of
the chart now gets an upward-pointing twin at the chart's bottom edge
whenever bidirectional strip recognition is enabled — so the user
sees an arrow at each end of the strip's column, reflecting that
chartread will accept the scan from either direction. With the option
checked (bidirectional disabled, the current default) nothing
changes.

### Improvements
- **Bidirectional indicator on the chart preview.** When
  "Disable bidirectional strip recognition (-B)" is **unchecked** in
  either the Guided or Manual Measure panel, `TiffPreview` now draws
  a second `#56d6a5` triangle of the same width and height as the
  existing top arrow, anchored 5 px above the chart image's bottom
  edge with the apex pointing up. The bottom arrow's horizontal
  column tracks the active strip exactly like the top arrow does, so
  the two stay visually paired as chartread advances. When the
  checkbox is **checked** (the default — bidirectional disabled)
  rendering is identical to v3.5.12, just the single top arrow.
  Driven by a new `set_bidirectional(enabled: bool)` setter on
  `TiffPreview`; `_on_start` in `ui/tabs/tab_measure.py` pushes
  `not params.disable_bidir` into the preview just after
  `_collect_params()`, and `_on_measure_done` clears the flag
  alongside the existing `highlight_stripe(-1)` reset so a stale
  bidir state never carries into the next run. Pinning the bottom
  arrow's Y to the chart's bottom edge (instead of mirroring the
  strip's own bottom) keeps it out of the patch grid on multi-strip
  layouts where strip rects sit flush against each other.

## v3.5.12
Three small UX papercuts across the Check/Refine, Measure, and Create
Chart tabs. The result dialog after a profile analysis was clumping its
buttons against the left edge, the green stripe-arrow overlay on the
Measure preview stayed on screen after chartread had already exited
(advertising state that was no longer live), and the file picker for
pre-conditioning profiles dropped the user in `~` with no shortcut to
the OS's ColorSync / Color folder where ICC profiles actually live.

### Fixes
- **Profile Quality Assessment dialog: buttons left-aligned.** The
  popup raised by `_show_result_dialog` in
  `ui/tabs/tab_check_refine.py` was packing Close / Install / Use as
  Pre-conditioning (and optionally Guide Me Through Refinement) into a
  bare `QDialogButtonBox` added straight to the dialog's vertical
  layout. Qt's default packing left-aligned the row, so on the
  Excellent grade where only three buttons render, the right two-thirds
  of the dialog sat empty. The buttons are now individual
  `QPushButton`s laid out in a `QHBoxLayout` with stretches between
  every entry, so they distribute evenly across the dialog width
  regardless of how many actions are visible for the current grade.
- **Measure preview: green stripe-arrow stuck after chartread exited.**
  `_on_stripe_changed` in `ui/tabs/tab_measure.py` calls
  `TiffPreview.highlight_stripe(...)` on every `stripe_changed`
  signal to point at the strip chartread is currently waiting for,
  but `_on_measure_done` never cleared it. The arrow stayed pinned to
  the last-read strip even after the measurement finished, was
  stopped, or errored out — visually claiming the run was still
  active. `_on_measure_done` now resets the highlighter with
  `highlight_stripe(-1)` at the top of the handler so the overlay
  goes away in all three exit paths (clean finish, user-stop,
  instrument error).

### Improvements
- **Pre-conditioning profile picker: ICC/ICM folder shortcuts in the
  sidebar.** Both the Guided wizard's pre-conditioning step
  (`_on_guided_precond_browse` in `ui/tabs/tab_chart.py`) and the
  Manual panel's `-c` Pre-conditioning Profile row (driven by
  `ParameterWidget._browse` reading the new `icc_sidebar: true` flag
  in `data/parameters.yaml`) now seed the file dialog's sidebar with
  the OS-appropriate ICC profile directories — `/Library/ColorSync/Profiles`,
  `/System/Library/ColorSync/Profiles`, and `~/Library/ColorSync/Profiles`
  on macOS; `C:\Windows\System32\spool\drivers\color` and
  `%LOCALAPPDATA%\Microsoft\Windows\Color` on Windows; `/usr/share/color/icc`,
  `/usr/local/share/color/icc`, and `~/.color/icc` on Linux.
  Non-existent paths are silently dropped by the existing
  `_sidebar_urls` filter, so platform-mismatched entries don't show
  up. A new `icc_profile_paths()` helper in `ui/widgets.py` keeps the
  list in one place. Scope is deliberately narrow — only the
  pre-conditioning entry opts in via the YAML flag; the other
  ICC-filtered parameters on the Build Profile tab (colprof's `-s` /
  `-S` gamut-mapping sources) are unchanged.

## v3.5.11
Point release for issue #18 follow-up from soul-traveller: on the HP
Color LaserJet 5550 Bonjour driver, the Print Chart tab still forced
the user to pick a paper tray to reach Page Size and Media Type even
though Paper Source already showed "(not set)" as its default. The
v3.5.6 fix only covered the case where the user *changed* a combo to
"(not set)" — it didn't unlock anything on first build, because the
combo was already at index 0 and `currentIndexChanged` never fired.
This release enables every option combo from the start, renames the
neutral label so its meaning is obvious, and reworks the downstream
re-filter so changing an upstream combo refreshes every combo below
it (not just the immediate next one).

### Fixes
- **HP Bonjour: Page Size / Media Type stayed locked at default (#18).**
  `_rebuild_option_rows` in `ui/tabs/tab_print.py` used to enable only
  the first combo and rely on `currentIndexChanged` to unlock the rest
  sequentially. That signal never fires for the initial selection, so
  drivers whose Paper Source has no "Auto" entry left the user staring
  at two greyed-out controls. All combos now start enabled; the cascade
  still resets and re-filters downstream selections when an upstream
  combo changes interactively.
- **Downstream combos re-filtered too late.** `_on_option_changed` only
  repopulated `combo_index + 1`, leaving combo `+2` with whatever value
  list it had on initial build. With all combos live from the start
  that became visible — a user who flipped Paper Source could see
  stale Media Type entries until they touched Paper Size. Split out a
  `_repopulate_next` helper and walked the cascade forward across every
  remaining combo so the value lists stay in sync with preceding
  selections.

### Other
- **"(not set)" → "Printer Default" on Print Chart option combos.**
  Per soul-traveller's suggestion on #18: the literal label read as
  "this is broken / nothing chosen", but the actual semantic is "let
  the driver decide" — which is also exactly what macOS's own print
  dialog calls "Auto Select" for `InputSlot`. Same behaviour, clearer
  word. Also dissolves the parallel "Auto Select is missing from
  ChromIQ's Paper Source combo" complaint — `InputSlot` "Auto Select"
  isn't a PPD-declared value, it's the macOS dialog's name for passing
  no `InputSlot` at all, which is what selecting Printer Default now
  does.

## v3.5.10
Follow-up on issue #23, raised by Knut on the printerknowledge forum and
in GitHub. When a strip kept failing on his ColorMunki, the misread
dialog's "Give Up" button quit the entire run and discarded everything
— not what the label promised, and not what chartread actually offers
at that prompt. This release replaces that single button with three
honest options (Retry / Skip Stripe / Save Partial & Quit), wires up
real auto-resume after a partial save (the checkbox auto-arms and the
Start button relabels itself to "Continue Measurement"), and corrects
a misleading line on the calibration-resume dialog that claimed a
per-strip marker chartread never actually prints.

### Improvements
- **Misread dialog: Retry / Skip Stripe / Save Partial & Quit (#23).**
  The old two-button "Retry / Give Up" dialog
  (`_on_strip_error` in `ui/tabs/tab_measure.py`) misnamed Esc-quit
  as "Give Up" and gave no way to skip a single bad stripe. The new
  layout exposes three actions that match chartread's actual control
  surface, all driven through `workflow/measure_manager.py`:
  - **Skip Stripe** chains any-key (→ strip menu) + `n` (next unread)
    via the existing `send_post_retry_key()` helper. Lets you bail on
    a problem stripe and finish the rest.
  - **Save Partial & Quit** chains any-key + `d` (done) + auto-`y`
    against chartread's `"At least one unread patch, Are you sure
    [y/n]"` prompt via a new `send_save_partial_and_quit()` helper
    and a tiny `_save_partial_state` state machine driven by
    `_ARE_YOU_SURE_RE`. This is the only sequence that makes
    chartread write the `.ti3` with patches still unread — Esc at
    the misread prompt discards everything, so the destructive path
    is no longer offered in this dialog (the Stop button at the top
    of the tab is still there as the escape hatch).
- **Auto-resume after an interrupted measurement.** When a run ends
  with a fresh `.ti3` on disk but chartread never emitted
  `"ALL ROWS READ"` (Save Partial & Quit, or `d`+`y` typed manually),
  `_on_measure_done` now re-runs `_update_resume_availability()` to
  surface the "Refine existing measurement (-r)" checkbox, auto-ticks
  it for the active mode, and a new `_refresh_start_button_label()`
  flips the Start button text to **"Continue Measurement"**. One
  click resumes chartread with `-r` against the just-saved partial
  file — no need to reload the `.ti2` or hunt for the option.
  Wired to `toggled` on both `_resume_cb` and `_m_resume_cb` so the
  label tracks manual ticks too.

### Fixes
- **Calibration-resume dialog claimed a non-existent strip marker.**
  The "Calibration Complete — Manual Re-measurement" body in
  `_on_calibration_done` told users that already-measured strips were
  marked with `(!! ALL ROWS READ !!)`, but that line only appears when
  *every* strip has been read, not as a per-strip tag. Rewritten to
  describe what the user actually does (re-scan to overwrite, scan
  unread strips to fill them in) rather than asserting anything about
  chartread's output formatting.

### Other
- GitHub Discussions enabled on the repo (#21) — the
  "Question / discussion" link on the New Issue page now resolves
  to the Discussions tab instead of returning a 404.

## v3.5.9
Forum-feedback release driven by printerknowledge.com post #148124. The
headline is the i1Pro family's intermittent "not enough patches read"
error during chartread: the default 6 mm page margin left so little room
past the last patch that the strip-reader optics drifted onto the bare
paper edge and ended the strip early. This release auto-bumps the
margin to 10 mm for i1Pro / i1Pro 2 / i1Pro 3 / i1Pro 3 Plus, recomputes
the per-sheet patch capacity tables for the new margin (measured against
real printtarg output, not estimated), folds the same fix into the
guided workflow silently, and rolls in three adjacent forum complaints
about preview duplication, Perceptual+Saturation profile builds, and
chart traceability.

### Fixes
- **i1Pro "not enough patches read" — margin auto-set to 10 mm.** The
  per-instrument default margin map (`data/patch_db.py`) now reports
  10 mm for `i1` and `p3` and the original 6 mm for `CM` / `SS`.
  Guided mode applies it transparently (info label shows `-m10 -M10`
  for i1Pro / A3+ runs); Manual mode pre-selects it in the `-m` widget
  the moment the user picks an i1Pro instrument, but never overwrites
  a non-default value the user typed by hand (so a deliberate 12 mm
  survives flipping instruments back and forth). The patch-per-sheet
  database gained `_PER_SHEET_CAPACITY_M10` and
  `_PER_SHEET_CAPACITY_M10_NO_LB` with 56 measured values covering
  every paper size that still fits patches at 10 mm; `query_patches`
  takes an explicit `margin_mm` kwarg so live patch-count displays and
  chart generation share the same numbers. Tiny papers (127×178,
  4×6) drop out of the i1/p3 tables at -m10 because the strip simply
  doesn't fit — those combos fall through to the binary-search
  fallback in `workflow/chart_creator.py`.
- **Single-page chart showed "Page 1/2" in the preview** — the
  forum-reported "two pages, next button still active" symptom on a
  single-file chart. Root cause: `pathlib.Path.glob` is
  case-insensitive on Windows, so `glob("*.tif")` and `glob("*.TIF")`
  both matched the same file and the preview received each path twice.
  `_printtarg_done` now wraps the glob results in a set comprehension
  before sorting (`tests/test_chart_creator.py::test_printtarg_done_dedupes_case_insensitive_glob`
  guards the regression).
- **Perceptual + Saturation profile build no longer crashes colprof
  with a missing source profile.** `_default_gamut_src` now prefers
  Argyll's `ref/sRGB.icm` and falls back to a newly-bundled
  `assets/profiles/sRGB.icm` so fresh installs without Argyll's ref
  folder still get a valid default. A pre-flight `_validate_gamut_source`
  in `_on_build` aborts with a clear dialog ("Gamut source profile not
  found at <path>. Browse to a valid .icm/.icc or switch to None.")
  whenever the field is empty or the path no longer exists, instead of
  letting colprof exit non-zero mid-build.
- **`targen failed with code 1` in Manual mode** when the user clicked
  Generate with `-f0` and no `-g` / `-s` patches either. Targen exits
  with "Must have some single or multi dimensional RGB or CMY steps".
  A pre-flight check in `_on_generate` now catches this and writes a
  clear message into the log ("Set a non-zero Total Patch Count, enable
  the Auto checkbox, or set Grey/Single steps") without spawning the
  subprocess.
- **Manual chart parameter settings corrupted by Windows registry
  case-insensitivity.** `manual_targen_-g` (Grey Axis Steps, int) and
  `manual_targen_-G` (Good Mode, bool) collided in HKCU; `-G='true'`
  overwrote `-g`'s int slot and triggered `set_value(-g, 'true')`
  warnings on every restore. Single-letter alpha flag keys now get a
  `_u` / `_l` case suffix in storage (`manual_targen_-g_l`,
  `manual_targen_-G_u`), one-time migration silently discards
  type-incompatible legacy values and deletes the bare-flag key. The
  same trap existed latently for every other case-twin flag (`-d/-D`,
  `-c/-C`, `-b/-B`, `-s/-S`, ...) and is now closed off.

### Improvements
- **Chart TIFFs are self-documenting via right-edge metadata stamp.**
  Forum feature request: after printtarg writes its own vertical ID
  line on the long edge (`ArgyllCMS — Chart "name" (Random Start NNN)
  <date>`), ChromIQ now stamps a parallel rotated line containing the
  exact `targen` and `printtarg` commands used to produce the chart
  plus the ChromIQ version, in the widest white run of the right
  margin. Pixel-level guarantees: every column to the left of the
  detected writable band is byte-identical pre/post; bit depth (uint8
  /uint16), photometric, compression, ICC profile, ImageDescription,
  Orientation, XPosition/YPosition, ResolutionUnit (cm stays cm), and
  effective DPI are all preserved exactly. Strip layout
  (StripOffsets/StripByteCounts/RowsPerStrip) is the only unavoidable
  re-encoding artefact; the image renders identically. Implementation
  in `workflow/tiff_metadata.py`, tested under both 8-bit and 16-bit
  in `tests/test_tiff_metadata.py`.
- **Manual chart tab gained a "Chart notes" field and a "Stamp commands"
  toggle.** Notes (e.g. *Canon Pro-1000 / Hahnemühle Photo Rag 308*)
  ride along on the same right-edge stamp when filled. The checkbox
  defaults to on and persists across sessions; turn it off to keep the
  stamp clean (notes-only, or empty entirely). The notes field
  intentionally does not persist between sessions — notes are
  per-chart context, not a default.
- **Bundled `assets/profiles/sRGB.icm`** (Argyll's AGPL-redistributable
  source profile, 3 kB) so a fresh ChromIQ install gives a working
  Perceptual+Saturation default without needing the user to point at
  Argyll's ref folder first.
- **Guided info label now shows the effective margin flag** —
  `printtarg -ii1 -pA4 -t300 -L -m10 -M10 chart` — so users can see at
  a glance which margin is being applied and why the patch count
  differs from a fresh ColorMunki run on the same paper.
- **New `scripts/measure_margin10_capacity.py`** automates the
  binary-search measurement of per-sheet patch capacity at any margin
  for any instrument × paper × `-L` combination. Used to populate the
  margin-10 tables in this release; ready to reuse if a future tester
  reports the same scanning-jig issue at a different margin.

## v3.5.8
Log readability pass driven by tester feedback against v3.5.7. The
on-disk log file (`~/Library/Logs/ChromIQ/chromiq.log` on macOS,
`%LOCALAPPDATA%\ChromIQ\Logs\chromiq.log` on Windows) accumulates
output from every session back-to-back, and with no visual cue for
session boundaries or in-app navigation it had become hard to tell
which lines belonged to which run, or which tab was active when an
error happened. This release adds two scannable markers and bumps
the rotation cap so a typical day of use stays in one file.

### Improvements
- **Session banner on every startup.** `configure_logging` now
  writes a three-line `===` banner to `chromiq.log` before any
  log handlers are attached, stamped with the local time, app
  version, platform, and Python version. The banner is appended
  directly to the file (not routed through the logging
  framework) so it lands above the first log line of the new
  session and visually separates it from the tail of the
  previous one. Failures to write the banner are swallowed so a
  read-only log dir can never block app startup.
- **Tab-change marker in the log.** `MainWindow._on_tab_changed`
  now logs `---- Tab → <name> ----` at INFO on every switch,
  including the initial tab restored from settings at startup.
  The `----` prefix scans visually when scrolling a long log,
  so it's quick to find the section of output that belongs to a
  given step in the workflow.
- **Rotation cap raised from 2 MB × 4 to 5 MB × 5.** The
  `RotatingFileHandler` previously kept ~8 MB of history; a
  long session with verbose `chartread`/`colprof` output could
  rotate the earliest part of the day out before the user
  noticed a problem. The new ~25 MB ceiling keeps a typical
  day in a single file while still bounding disk use.

## v3.5.7
Windows reliability work driven by tester reports against v3.5.6. The
headline is a defensive rewrite of the chartread keystroke path on
Windows (#20): a missing ctypes `restype` truncated `CreateFileW`'s
HANDLE on 64-bit Windows, so calibration prompts and `<esc>` could
silently fail. The new bindings, INFO-level send-key logging, and a
12-second no-response watchdog mean the next time chartread stops
responding the log file actually shows what happened and the user
sees a recoverable warning instead of a frozen dialog. A second
Windows fix forces the native OS print dialog regardless of stored
setting, so a stale `use_native_print_dialog=False` carried over
from an older install can't strand a Windows user on the CUPS/
PostScript bypass UI (the Settings checkbox is hidden on Windows
because the bypass UI has no working path there).

### Fixes
- **Chartread keystrokes silently dropped on Windows (#20).** The
  Windows interactive path attaches to chartread's hidden console
  and injects keystrokes via `WriteConsoleInputW`. The supporting
  `CreateFileW(\\.\CONIN$)` call had no `restype` declared, so
  ctypes treated its pointer-sized HANDLE return as a 32-bit signed
  int and truncated the high bits on 64-bit Windows — the
  subsequent invalid-handle check then misfired and the
  `WriteConsoleInputW` call could write into the wrong handle or
  return silently. All Win32 bindings (`AttachConsole`,
  `FreeConsole`, `CreateFileW`, `WriteConsoleInputW`,
  `CloseHandle`, `GetLastError`) now have explicit `argtypes` and
  `restype`, and the invalid-handle sentinel is derived from
  `c_void_p(-1).value` so it survives the pointer width.
  `_win_inject_key` returns a bool that propagates out via a new
  `ArgyllRunner.keypress_failed` signal.
- **Native print dialog forced on Windows.** A stale
  `use_native_print_dialog=False` carried over from older installs
  stranded Windows users on the CUPS/PostScript bypass UI, which
  has no working path on Windows. The Settings checkbox is hidden
  there (gated on `native_print_supported()`, macOS-only), so
  users had no way to flip it back. `AppSettings.get` now
  overrides the value at read time so Windows always reports True
  regardless of what QSettings has stored.

### Improvements
- **Diagnostics for chartread interactive sessions.** Every
  keystroke sent to chartread is now logged at INFO with the human
  label (`ESC`/`CR`/`SPACE`/`LEFT`/`RIGHT`/letter), the chartread
  PID, and the outcome (`OK`/`FAIL`), so the local app log
  (`%LOCALAPPDATA%\ChromIQ\Logs\` on Windows,
  `~/Library/Application Support/ChromIQ/Logs/` on macOS) contains
  an audit trail of what the user pressed and whether it reached
  the instrument. Previously this was at DEBUG and absent from the
  user-facing log file, which is why the v3.5.6 hang report in
  #20 could not be diagnosed from the user's logs.
- **No-response watchdog on the Measure tab.** When a dialog
  sends a keystroke to chartread (calibration, retry, give-up,
  "press d to finish"…) and no output comes back within 12
  seconds, the tab now prints a `[WARN]` line and flashes the
  status bar telling the user the key may not have reached the
  instrument and suggesting they retry or click Stop. Doesn't
  auto-abort — the Stop button stays in their hands — but the
  app no longer pretends to be working when it isn't. Injection
  failures returned by the new Win32 path also surface
  immediately via the same `[WARN]` channel.

## v3.5.6
Tab 2 (Print Chart) fixes from tester reports against v3.5.5. The
headline is the macOS "ChromIQ quit unexpectedly" crash at app shutdown
after switching printers (#19): the root cause was orphaned option-row
widgets accumulating across printer changes and surviving into
`QApplication` teardown with live signal connections, where SIP could
then follow a half-freed wrapper. Along the way, two visible Tab 2
quirks from the same tester (#18) — a stray unlabeled combo box drifting
above the option list, and being forced to pick a paper tray on the HP
Bonjour driver even when wanting the printer default — are gone too.

### Fixes
- **macOS quit-unexpectedly after printer change on Tab 2 (#19).**
  `_rebuild_option_rows` builds each option row as a nested
  `QHBoxLayout` whose `QLabel` and `QComboBox` are parented to the
  `TabPrint` widget, not the layout. The old cleanup loop only deleted
  top-level widgets in the options layout, so the inner widgets were
  detached from the layout but kept alive as orphan children of
  `TabPrint` — one extra set on every printer switch, each still
  holding a `currentIndexChanged` lambda connection. At quit, Qt's
  parent-child teardown plus the live connections gave SIP a window to
  follow a dangling wrapper and `EXC_BAD_ACCESS`. Two-part fix: the
  rebuild cleanup now recursively deletes nested layouts and
  disconnects each combo's signal before `deleteLater`, and a new
  `TabPrint.shutdown()` runs from `MainWindow.closeEvent` to reparent
  and drain the option widgets via the same `processEvents` pump
  already used for the `QtWebEngine` shutdown race. Models on
  `ui/gamut_panel.py::shutdown_webengine`.
- **Stray unlabeled combo box above the option list (#18).** Same
  orphaned-widget bug above, surfaced visually: leftover combos from
  prior printer selections stayed as children of `TabPrint`, drifting
  into view as a small label-less "A3" pulldown over the Printer row.
  The recursive layout cleanup removes them at the moment of rebuild
  instead of letting them accumulate.
- **HP Bonjour driver no longer forces a tray selection (#18).** When
  the user picked `(not set)` on the Paper Source combo — the only way
  to defer to the printer default on drivers that ship no "Auto"
  option — the sequential-enable logic in `_on_option_changed` kept
  Paper Size disabled, so the user was stuck. `(not set)` now unlocks
  the next combo with its full value list (nothing to filter against
  when there's no preceding choice), matching the behaviour the user
  would expect from leaving an option at its default.

## v3.5.5
UX polish driven by tester feedback on the measure tab and the chart-
import flow. The headline is a much tighter default patch-consistency
check (so a clogged nozzle or low ink shows up at measurement time
instead of poisoning the resulting profile) plus the ability to
overwrite an existing profile folder when importing an external
chart. Smaller touch-ups to the import-dialog button bar, the settings
dialog button spacing, and the preview-header tooltip styling round
out the release.

### Features
- **Overwrite existing folder when importing a chart.** When the
  profile name typed into the "Copy Chart Files" dialog collides with
  an existing folder under the working directory, the OK button is
  swapped for an "Overwrite existing folder" action. Clicking it pops
  a confirmation listing the full path that will be deleted before
  the import proceeds; the previous behaviour silently rejected the
  name with no way forward. Works for charts loaded from outside the
  working folder (via Tab 2 → Load existing chart and via the Measure
  tab's loader) as well as the "Use as base for a new profile" branch
  when the chart already sits inside the working folder. Self-
  collision (overwriting the source chart's own folder) is guarded
  with an inline error, so `shutil.rmtree` can never delete the file
  the user is currently importing.

### Improvements
- **Patch consistency tolerance default lowered from 1.0 → 0.5.** The
  chartread `-T` flag is a multiplier on the built-in patch-read-
  consistency threshold, not an absolute delta-E. A tighter setting
  catches real problems early — clogged inkjet nozzles, low ink,
  dirty drum rollers, drifting laser toner — at chart-read time
  instead of letting them poison the profile silently. Argyll's stock
  1.0 is too forgiving on healthy hardware; experienced users on
  printerknowledge.com run 0.4 with i1 Pro 2 / 3. 0.5 leaves a little
  headroom over the community benchmark while still flagging
  pathological reads. The tooltip is rewritten in plain language to
  explain what `-T` actually multiplies, when to lower it (good
  printer, strict QA), and when to raise it to 0.8–1.5 (textured,
  matte, or fine-art papers where the surface itself contributes
  variance).
- **Manual measure: patch consistency tolerance is now on by
  default.** The guided panel already pre-activates `-T`; the manual
  panel did not, so users had to remember to tick the checkbox every
  session. Added `manual2_chartread_tolerance_enabled: True` to the
  DEFAULTS dict so the manual panel matches the guided one out of the
  box. Any value the user has explicitly saved with "Save as
  defaults" still wins on subsequent launches — this is just about
  the first-run state.
- **Import dialog button bar redesigned.** Replaced the
  `QDialogButtonBox` (which on macOS hugs the right edge) with a
  custom layout: primary action (OK or Overwrite, depending on
  collision state) on the left, Cancel pushed to the right by a
  stretch. OK and Overwrite share the same slot — only one is visible
  at any time — so the collision case reads as a clean two-button
  layout rather than a three-button squeeze. Dialog widened from
  500 px to 580 px so the longer Overwrite label has room. Enter
  still confirms OK when it's visible; when only Overwrite is
  visible, Enter is intentionally a no-op so the destructive action
  needs an explicit click.
- **Settings dialog button spacing.** Restore Factory Defaults,
  Report a Bug, and Check for Updates on the left now share the same
  gap as OK ↔ Cancel on the right, by querying
  `bb.layout().spacing()` and applying it as the bottom-row spacing.
  Replaces the previous mix of hard-coded 8 px gaps and the style-
  driven 6 px QDialogButtonBox gap so the bar reads as one visually
  unified row.

### Fixes
- **Guided panel was stuck at the old 0.7 tolerance.** A post-
  construction `opt.widget.setValue(0.7)` in `_make_guided_panel`
  (left over from the v3.1.2 default) was overriding the new 0.5
  spinbox constructor default. Fixed in place. Also updated
  `measure_tolerance_value` in `core/settings.py` DEFAULTS to 0.5 so
  `_restore_defaults()` doesn't reseed the spinbox with the stale
  value at startup. Users who previously clicked "Save as defaults"
  with 0.7 will keep that saved value (intentional — respects user
  choice); restoring factory defaults or saving 0.5 explicitly
  refreshes it.
- **Preview header tooltips rendered with a transparent background
  on macOS.** When a `QLabel` carries `background: transparent` in
  its own QSS, the global `QToolTip` rule fails to reach that
  label's tooltip popup — the popup falls back to the macOS native
  rendering and inherits the transparency. The image-body tooltip
  also lost its left border because `_img_label`'s
  `border-left: none` was bleeding into the tooltip. Added a global
  `QToolTip { background: #262626; color: #e6e6e6;
  border: 1px solid #404040; padding: 4px; }` rule to
  `APP_STYLESHEET`, plus a per-widget `QToolTip` block on each
  preview label, with the existing label declarations scoped inside
  `QLabel { … }` so they no longer leak. All three preview tooltips
  (caption, filename, image body) now render dark with a clean four-
  sided border.

## v3.5.4
Follow-up to v3.5.2 for issue #15: after the 16-bit colorimage fix, the
HP Color LaserJet 5550 (firmware ~2005) kept pulling each profiling
sheet back through its duplexer, and "Print All Pages" paired two
charts onto opposite sides of the same sheet — producing one corrupted
half-print. The printer was honouring its panel-side duplex default
instead of the CUPS `Duplex=None` option.

### Fixes
- **Duplex forced off at the PostScript layer.** Profiling charts are
  always single-sided, but `lp -o Duplex=None` is just a CUPS-level
  hint and some older firmware ignores it in favour of the printer's
  panel/PPD default. The PS document now declares `/Duplex false
  /Tumble false` inside its `setpagedevice` block, which the printer's
  PostScript interpreter has to honour — same mechanism we already use
  for `/PageSize`. Devices without a duplex unit silently ignore the
  key per the PS spec, so the change is harmless for the rest of the
  supported printer set. Also added `sides=one-sided` to the lp
  options as belt-and-suspenders for PPDs that filter `setpagedevice`
  keys but accept the IPP keyword. Regression-tested by pinning the
  emitted block in `test_setpagedevice_disables_duplex`.

## v3.5.3
Quality-of-life release for the Manual chart workflow: pick a page count,
tick **Auto**, and let ChromIQ size the patch count to fill exactly that
many sheets. Also fixes a long-standing bug in the patch-fitting binary
search that made custom patch scales produce partially-filled pages.

### Features
- **Auto patch count in Manual mode.** New "Auto" checkbox next to the
  total patch count spinbox in the basic targen parameters, paired with a
  new "Pages" spinbox under printtarg → paper size. When Auto is on, the
  patch count is computed at Generate-target time from the current paper,
  instrument, double-density, left-border, patch scale, and margin so the
  chart fills the requested page count with no empty space. The patch-
  count spinbox displays "Auto" in place of a number while the option is
  active. The estimate is deferred to the Generate click rather than
  running live on every settings change — custom layouts shell out to
  `targen`/`printtarg` for a binary search, which would otherwise freeze
  the UI on each tweak; progress now scrolls into the log as the search
  runs. Auto state and the target Pages value persist across presets and
  app restarts.

### Fixes
- **`_binary_search` bounds account for `patch_scale`.** The per-sheet
  capacity search used the standard-density (`-a 1.0`) DB estimate to
  seed its `[0.5×, 2.5×]` window. At `patch_scale = 2.0` each patch
  occupies four times the cell area, so the true capacity is roughly a
  quarter of that estimate — the entire search window lived above the
  real value, every probe overflowed, and the loop fell back to its 50-
  patch sentinel. Result: choosing a custom patch scale (or running
  Guided mode for a non-default layout) produced too few patches and
  partially-filled pages. The search now centres on `est / patch_scale²`
  and logs a warning + returns the scaled estimate when no fit is found,
  so a future stuck-loop bug surfaces instead of hiding.
- **Disabled inputs now look disabled.** `QLineEdit`, `QSpinBox`,
  `QDoubleSpinBox`, and `QComboBox` controls inherited their normal
  `TEXT_MAIN` colour even when `setEnabled(False)` had been called,
  making greyed-out fields visually indistinguishable from active ones.
  Added a `:disabled` rule to the global stylesheet that mirrors the
  existing `QPushButton:disabled` palette (dim grey text on a darker
  body). Picked up automatically by every enable-toggling call site.

## v3.5.2
Follow-up bugfix release for issue #15: 16-bit profiling targets loaded
from external bundles now print on older PostScript hardware, and the
`Load .ti1` flow on the Generate Chart tab no longer drops the channel
sidecar.

### Fixes
- **16-bit TIFFs are downcast to 8-bit before `colorimage`.** `printtarg
  -T` (capital T) writes 16-bit charts — common in third-party target
  bundles like the Argyll_Printer_Profiler project. Older HP PostScript
  interpreters (CLJ 5550 firmware ~2005 and similar vintage) silently
  drop jobs whose inline image uses BitsPerComponent=16, even though
  the L3 spec supports it. The PostScript generator now right-shifts
  16-bit samples to their high byte before encoding, so every print
  job goes out as 8-bit `colorimage`. Lossless for profiling — patches
  are flat fills, the 16-bit precision was redundant, and `colprof`
  reads from the `.ti3` measurement file rather than the printed
  image. Verified end-to-end on a synthetic of the reporter's exact
  3307 × 2339 A3-landscape chart.
- **`Load .ti1` on Generate Chart now writes `<stem>.channels.json`.**
  The sidecar guard in `_printtarg_done` checks `self._pending_params`,
  which the normal `generate()` entry point sets but
  `load_ti1_and_generate_preview()` did not — so loading a chart from
  an existing `.ti1` produced a working set of TIFFs but no channel
  sidecar, leaving the preview unable to identify inks in a future
  session. Mirrors the `generate()` path now and is covered by
  `tests/test_chart_creator.py`.

## v3.5.1
Bugfix release addressing a silent print-job failure on memory-constrained
PostScript printers and a handful of preview-clarity rough edges reported
against v3.5.0.

### Fixes
- **Print Chart: PostScript output now uses `/FlateDecode` + ASCII85
  instead of raw ASCII-hex.** Profile charts compress extremely well
  (large uniform patches), so a representative 16-bit A3 chart at 200 dpi
  shrinks from ~90 MB to ~0.3 MB of PostScript — bit-exact identical
  pixel data feeding `colorimage`, just a tighter wire format. Fixes
  issue #15: HP Color LaserJet 5550 and similar PS-interpreter-
  constrained printers were silently dropping the oversized job ~20 s
  after accepting it. The emitted PostScript LanguageLevel bumps to 3
  (universal on every printer ChromIQ targets); the existing TIFF
  raster fallback in `CupsRawPrinter` still handles L2-only edge cases.
- **Build workflow: macOS arm64 + universal2 matrix legs no longer
  race-fail on release creation.** The loser of the `gh release create`
  race now detects the 422 "already exists" response, continues, and
  uploads its DMG to the release the winner created.

### Preview clarity
- **Loaded chart name shown above every TIFF preview.** Generate Chart,
  Print Chart, and Measure tabs now display the chart stem directly
  beneath the section caption ("CHART PREVIEW" / "PRINT PREVIEW"),
  so it's always obvious which target is loaded. Hover the caption,
  the filename, or the dark image area to see the working folder and
  every per-page TIFF file name; the cursor changes to a help-style
  pointer over the header text as a discoverability cue.
- **Gamut Volume panel shows the loaded ICC profiles.** Under the
  "GAMUT VOLUME" header in Check & Refine, profile A and (when set)
  profile B stems appear as `A: <stem>   B: <stem>`. Full paths on
  hover, same as the TIFF previews.
- **Header height collapses when no chart is loaded** so the section
  caption hugs the preview area like before — extra height only
  appears when there's actually a filename to display.

### Workflow
- **Measure → Print cross-tab sync.** Loading an existing `.ti2` in
  the Measure tab now also populates the Print tab, mirroring the
  existing Print → Measure direction. The auto-sync skips
  `resolve_ti2`'s "Continue / Use as base for a new profile" dialog
  because the chart has already been resolved on the originating tab.

## v3.5.0
First stable release of the 3.5.x line, rolling up the six 3.5.0 betas
into a single supported build for macOS, Windows, and Linux.

### Highlights since v3.2.8
- **Linux support.** Pre-built tarballs for `x86_64` and `aarch64`
  ship with every release alongside the existing macOS DMGs and Windows
  ZIPs. All platform-conditional paths (Argyll bin defaults, log
  directory, ICC profile install location, gamut viewer ICC dialog)
  now live in `core/platform_paths.py` with explicit Windows / macOS /
  Linux branches. Linux is labelled **beta** in the README — the
  full ArgyllCMS workflow runs, but real-hardware coverage is still
  thin; please report what works and what doesn't.
- **Guided pre-conditioning (second-pass) workflow.** The *Generate
  Chart* tab gains an optional **Refinement** section: tick the box,
  pick an existing `.icc` / `.icm` / `.mpp`, and `targen` runs with
  `-c` for a refinement pass. The *Build Profile* and *Check & Refine*
  result dialogs grow a **Use as Pre-conditioning** button that
  pre-fills the chart panel with the just-built profile, and the prior
  session's `.icc` / `.ti3` are auto-renamed `pre_*.icc` / `pre_*.ti3`
  so v1 isn't overwritten by v2.
- **Per-tab onboarding tooltips.** Every workflow tab now has a
  clickable ⓘ icon next to its big title that opens a beginner-friendly
  explanation of what the screen does, what needs to be ready, how to
  use it, and what comes next. The *Build Profile* tooltip swaps to
  describe the 3-stage `printcal → applycal → colprof` flow when
  calibration mode is enabled, and the *Print Chart* tooltip varies by
  OS and `use_native_print_dialog` (macOS bypass, macOS native dialog,
  Linux CUPS bypass, Windows QPrintDialog).
- **Updater understands SemVer pre-release tags.** Beta users see
  newer betas as upgrade candidates; stable users only see stable
  releases. The "Check for Updates" crash on pre-release builds
  (`int("0-beta")`) is gone.
- **Landscape charts print correctly on the CUPS PostScript path.**
  The generated PostScript now declares its own page geometry to match
  the TIFF aspect, so Apple's `pstops` no longer double-rotates the
  job — HP drivers stop clipping columns A–E or silently dropping
  jobs.

### Other improvements & fixes
- File logger + `sys.excepthook` installed at the top of `main.py`,
  before PyQt6 / numpy are imported, so early import-time failures
  end up in `chromiq.log` with a full traceback instead of vanishing.
- Linux bundle ships nine xcb / xkbcommon helper libs next to the
  binary, so the Qt xcb platform plugin resolves its deps from
  `$ORIGIN` and the tarball launches on minimal distros without
  requiring `libxcb-cursor0` to be installed system-wide.
- Cross-platform icon builder (`scripts/build_icons.py`): generates
  `app_icon.icns` and `app_icon.ico` from PNG using Pillow only, so
  the icon step in `HOW_TO_BUILD.txt` no longer needs macOS-only
  `sips` / `iconutil`.
- GitHub release notes are guaranteed to be non-empty — the workflows
  first try to extract the matching `## <tag>` section from this
  changelog, then fall back to commit subjects since the previous tag.
- Pre-release-style tags (`-alpha`, `-beta`, `-rc`, `-pre`) are
  automatically flagged as GitHub prereleases by the build workflows;
  final tags stay regular.
- Issue forms auto-apply `platform:` and `Severity:` labels via the
  new `auto-label-issues.yml` workflow.
- WebEngine teardown moved from `aboutToQuit` to `MainWindow.closeEvent`
  to dodge the SIP / Chromium shutdown race that caused
  `EXC_BAD_ACCESS` on quit when the gamut viewer had been opened.

### Updating from a 3.5.0 beta
If you're running any 3.5.0-beta.X build, **Check for Updates** will
recognise v3.5.0 as an upgrade and prompt you to install it (final
releases sort above any pre-release of the same base version per
SemVer 2.0.0 precedence rules).

For the full per-beta breakdown of what landed when, see the
`v3.5.0-beta.1` … `v3.5.0-beta.6` sections below.

## v3.5.0-beta.6
### Added
- **Guided pre-conditioning workflow in *Generate Chart*.** A new
  *Refinement (Optional)* section appears on the guided panel: tick
  the checkbox + pick an existing `.icc`, `.icm`, or `.mpp` profile
  and `targen` is invoked with `-c` for a second-pass profiling run.
  The always-on `-G` OFPS distribution plus targen's default `-A=1.0`
  already satisfy the man-page condition for `-c`, so no extra flag
  plumbing is required.
- **"Use as Pre-conditioning" button** on both the *Build Profile*
  and *Check & Refine* result dialogs. Pressing it switches back to
  *Generate Chart* and pre-fills the picker with the just-built
  profile. Both dialogs were widened to fit the new button row plus
  its explanation paragraph.
- File-picker filter on the pre-conditioning field now accepts `.mpp`
  in addition to `.icc` / `.icm`, per the targen man page.

### Changed
- When a refinement run starts in the same working folder, the prior
  session's `<basename>.icc` and `<basename>.ti3` are renamed in
  place to `pre_*.icc` / `pre_*.ti3` instead of being overwritten by
  the upcoming `chartread` / `colprof` runs. `_stage_precond_profile`
  already handles in-folder `pre_` files without re-copying. Only one
  generation of history is kept — diminishing returns past v2.

## v3.5.0-beta.5
### Added
- **Tab-headline tooltips on every workflow tab.** Each of the five tabs
  (Create Chart, Print Chart, Measure, Build Profile, Check & Refine)
  now has a clickable ⓘ icon next to its big title that opens a
  beginner-friendly explanation of what the screen does, what the user
  needs ready (devices connected, paper loaded, …), how to use it, and
  what comes next. The tab 4 tooltip swaps between the standard
  `colprof` and the 3-stage `printcal → applycal → colprof` flow when
  calibration mode is toggled in Settings. The tab 2 tooltip
  additionally varies by OS and by the `use_native_print_dialog`
  setting, so macOS bypass, macOS native dialog, Linux CUPS bypass, and
  Windows QPrintDialog each get their own instructions.

### Fixed
- **Crash on quit when the gamut viewer was active.** PyQt6 plus
  QtWebEngine raced during shutdown: SIP walked the Chromium subtree
  in `QApplication`'s destructor and dereferenced a dangling pointer,
  surfacing as `EXC_BAD_ACCESS` in
  `sip_api_visit_wrappers/dealloc_QApplication`. The WebEngine teardown
  now runs from `MainWindow.closeEvent` (while the event loop is still
  alive) instead of from `aboutToQuit` (which fires too late for posted
  events to drain), and the main window hides itself first so the user
  sees no visible delay.

## v3.5.0-beta.4
### Fixed
- **Check for Updates no longer crashes on pre-release builds** (#16). The
  built-in version parser did `int("0-beta")` on tags like
  `v3.5.0-beta.3` and surfaced as "Check failed: invalid literal for
  int() with base 10: '0-beta'". The parser now follows SemVer 2.0.0
  precedence rules (`3.5.0 > 3.5.0-rc.1 > 3.5.0-beta.3`), and the
  checker queries `/releases` rather than `/releases/latest` so users on
  a beta can be told about a newer beta. Users on a final release still
  only see final releases as upgrade candidates.
- **Landscape charts now print correctly on the CUPS PostScript path**
  (#14, #15). When the chart aspect contradicted the selected paper
  orientation, the generated PostScript declared a portrait page and
  drew the landscape image on top — Apple's `pstops` filter then
  double-rotated, which caused HP drivers to clip columns A–E (#14) or
  silently drop the job (#15). `PostScriptGenerator` now swaps
  `setpagedevice` to match the TIFF aspect, and the CUPS PS command no
  longer forwards `orientation-requested`, so the document fully
  describes its own geometry. The raw-TIFF fallback path still uses
  `orientation-requested` because raw TIFF has no inherent page
  geometry.

### CI
- **Issue forms now auto-apply `platform:` and `Severity:` labels.**
  GitHub issue forms don't turn dropdown selections into labels — only
  the template's static `labels:` array applies. A new
  `auto-label-issues.yml` workflow parses the bug- and feature-form
  bodies on open and adds the matching repo labels
  (`platform: macos|windows|linux|any`,
  `Severity: Critical|High|Medium|Low`). Includes a `workflow_dispatch`
  entry for retroactively labelling existing issues.

## v3.5.0-beta.3
### Fixed
- **Early startup failures are now captured in `chromiq.log`** (#13, rooted
  in #11). The rotating file handler and a `sys.excepthook` are installed
  at the very top of `main.py`, before `PyQt6`, `numpy`, and the UI
  modules are imported. If a frozen bundle ships with a broken dylib
  graph (as happened in v3.2.7 with `libscipy_openblas64_.dylib`), the
  import-time `ImportError` is now written to disk with a full traceback
  instead of vanishing silently. The startup banner also records python
  version, `sys.platform`, `sys.frozen`, and `sys.argv` for diagnostics.

### CI
- macOS, Windows, and Linux release workflows now always include a
  changelog in GitHub release notes. They first try to extract the
  matching `## <tag>` section from `CHANGELOG.md`; if absent (e.g. the
  maintainer forgot), they fall back to an auto-generated bulleted list
  of commit subjects since the previous tag, so releases can never ship
  with empty notes.

## v3.5.0-beta.2
### Fixed
- **Linux: Qt xcb platform plugin crash on launch** — the beta.1 tarball
  aborted on first run with
  `qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to
  load the Qt xcb platform plugin` on any distro that did not happen to
  have `libxcb-cursor0` installed system-wide. `ChromIQLinux.spec` now
  detects nine xcb/xkbcommon helper libs on the build host and bundles
  them into the tarball next to the binary, so the Qt xcb plugin resolves
  its dependencies from `$ORIGIN` and the bundle launches without any
  system packages required. Reported by the Debian beta tester.

### Docs
- `HOW_TO_BUILD.txt`: retitled to drop the `.app` suffix; macOS-only steps
  (4, 4b, 5, 6 — PyInstaller spec choice, `codesign --deep`, "open .app",
  zip a `.app`) are now explicitly labeled so Linux readers stop reading
  them as cross-platform. Added a Troubleshooting subsection with
  apt/dnf/pacman fallback commands for the xcb-cursor error.
- `README.md`: Linux section gains a one-line troubleshooting note with
  the same fallback install commands.

## v3.5.0-beta.1
### Added
- **Linux support (beta)**: ChromIQ now builds and runs on Debian/Ubuntu and
  other glibc Linux distributions. Pre-built tarballs are produced for both
  `x86_64` and `aarch64` and attached to each release
  (`ChromIQ-Linux-x86_64.tar.gz`, `ChromIQ-Linux-aarch64.tar.gz`). Extract and
  run `./ChromIQ/ChromIQ` — no install step required.
- **Cross-platform icon builder**: a new `scripts/build_icons.py` script
  generates both `assets/app_icon.icns` (macOS) and `assets/app_icon.ico`
  (Windows) from the source PNG using Pillow only — no more macOS-only
  `sips`/`iconutil` dependency, so the icon step in `HOW_TO_BUILD.txt` now
  works on every platform.

### Changed
- All platform-conditional paths and URLs (Argyll bin directory defaults &
  auto-detection candidates, log directory, ICC profile install location,
  gamut viewer ICC profile dialog, ArgyllCMS download page, native-print
  dialog visibility) now live in a single `core/platform_paths.py` module
  with explicit branches for Windows, macOS, and Linux. Previously every
  call site assumed "not Windows" meant macOS, which silently produced
  `~/Library/Logs`, `~/Library/ColorSync/Profiles`, `/Applications/Argyll/bin`
  etc. on Linux. macOS and Windows behavior is preserved exactly (regression
  test: `tests/test_platform_paths.py`).
- On Linux the log file lives at `~/.local/state/ChromIQ/logs/chromiq.log`
  (or `$XDG_STATE_HOME/ChromIQ/logs/`), the default Argyll path is `/usr/bin`
  (also probes `/usr/local/bin`, `/opt/argyll/bin`, `/opt/argyllcms/bin`,
  `~/.local/bin`), installed profiles go to `~/.local/share/color/icc/`
  (or `$XDG_DATA_HOME/color/icc/`), the gamut viewer file dialog lists the
  XDG + colord-managed profile directories (`~/.local/share/color/icc`,
  `~/.color/icc`, `/usr/share/color/icc`, `/usr/local/share/color/icc`,
  `/var/lib/colord/icc`), and the **Download latest ArgyllCMS…** button
  opens the Linux download page on argyllcms.com.
- Profile-install dialog button text reads **Install Profile** on Windows
  and Linux (previously hard-coded **Install on this Mac** on every
  non-Windows OS).

## v3.2.8
### Fixed
- **Intel-only DMG (`ChromIQ-macOS-x86_64.dmg`) failed to launch** with
  `[PYI-3463:ERROR] Could not load PyInstaller's embedded PKG archive from
  the executable`. The v3.2.7 derive-x86_64 step ran `lipo -thin x86_64`
  over every Mach-O in the universal bundle, including the PyInstaller
  bootloader at `Contents/MacOS/ChromIQ`. The bootloader has its onedir
  PKG archive appended *after* the Mach-O slices; `lipo` writes only the
  Mach-O bytes and silently discards the trailing archive, bricking the
  binary. The CI step now skips the bootloader (it stays universal2 — a
  ~1 MB cost; macOS Intel picks the x86_64 slice at exec time anyway).
- **Universal DMG (`ChromIQ-macOS-universal.dmg`) crashed on import numpy**
  with `Library not loaded: @rpath/libscipy_openblas64_.dylib`. numpy 2.4+
  vendors a SciPy-built OpenBLAS dylib that PyInstaller's bundled
  `hook-numpy.py` did not pick up on the universal2 build, leaving
  `Contents/Frameworks/libscipy_openblas64_.dylib` absent. The spec now
  collects numpy's dynamic libs explicitly (`collect_dynamic_libs('numpy')`),
  and a new CI step asserts the OpenBLAS dylib is in the bundle so a hook
  regression can never silently ship again.

## v3.2.7
### Fixed
- **Native macOS print dialog ignored chart paper size**: the new
  Sequoia/Tahoe print panel hides the standalone paper-size control, and
  ChromIQ's native print path never called `setPaperSize_`, so the job
  inherited whatever paper was last in `sharedPrintInfo` (typically
  Letter/A4). With clip pagination set on the print info, charts larger
  than that default were silently cropped at print time. The native
  print path now sets the paper size to the chart's own dimensions
  (computed from the TIFF's resolution tag) before opening the dialog,
  and explicitly enables `NSPrintPanelShowsPaperSize`,
  `NSPrintPanelShowsOrientation`, `NSPrintPanelShowsScaling` and
  `NSPrintPanelShowsPageSetupAccessory` on the panel so the user can
  still override paper / orientation / scale in the dialog or via the
  driver's Printer Options pane.

## v3.2.6
### Fixed
- **Universal DMG launches on Apple Silicon but crashed on Intel Macs** with
  `dlopen … QtGui.framework/Versions/A/QtGui … incompatible architecture`.
  The CI lipo step that fattens arch-specific wheels into universal2 only
  matched `*.so` and `*.dylib` files, so the Qt6 framework binaries (which
  live at `PyQt6/Qt6/lib/Qt*.framework/Versions/A/Qt*` with no extension)
  were silently left arm64-only. `PyQt6-Qt6` and `PyQt6-WebEngine-Qt6` were
  also missing from the merge list entirely. The lipo helper now walks the
  x86_64 wheel by relative path and merges every Mach-O it finds, and both
  Qt framework packages are included — restoring true universal2 builds.

## v3.2.5
### Added
- **Report a Bug button in Preferences**: the bottom row of the Preferences
  dialog now exposes a *Report a Bug…* button that opens the GitHub bug-report
  form (pre-filled with the right template) in the user's default browser.
  Sits next to *Restore Factory Defaults* and *Check for Updates* so all three
  "GitHub / external" actions cluster together on the left of the row, with
  Cancel / OK pinned to the right as before.

### Changed
- **Preferences dialog widened from 840 → 900 px** so the bottom-row buttons
  (Restore Factory Defaults, Report a Bug…, Check for Updates, Cancel, OK)
  all show their full labels without truncation.

### Project
- **Reporting issues & feedback section added to the README**, with deep-links
  that jump straight into the bug-report and feature-request forms (skipping
  the GitHub template chooser). The lone Windows-section feedback link now
  also points at the bug-report form rather than the issues list.
- **`.github/SUPPORT.md` added** so GitHub surfaces a *Help* entry in the
  new-issue chooser sidebar and on the repo's community profile, routing
  users to bugs / features / Discussions / the ArgyllCMS mailing list.

## v3.2.4
### Fixed
- **Stale files reappear after a restart**: with *Restore last session* enabled,
  clearing a `.ti3` / `.icc` / cal-`.ti3` mid-session previously didn't take
  effect on the next launch — the cleared paths still lived in settings and
  were resurrected. `clear_files()` in the Build Profile tab now also nulls
  `_cal_ti3_path` (which was being skipped) and the Measure and Build Profile
  tab clear methods eagerly write empty values to `session_ti1_path`,
  `session_ti3_path`, `session_icc_path`, and `session_cal_ti3_path` instead
  of relying on the quit-time save — so a crash before quit can no longer
  resurrect cleared files.

- **Working-folder name not sanitised against filesystem-illegal characters**:
  `FileManager.set_target_name` previously only replaced spaces with `-`. A
  printer name containing `/` (CUPS permits it) or a manually-typed chart name
  with `:` / `\` / control chars could create unintended subfolders or fail
  outright on Windows. Names are now run through a single `_sanitise` rule
  that keeps alnum / `_` / `-` / `.`, replaces everything else with `_`,
  strips leading and trailing dots (Windows forbids them), and falls back to
  `"session"` if the result is empty. Auto-generated session names are
  unchanged (they were already hyphenated).

- **Dead "high ΔE" warning in the Build Profile result dialog**:
  `ProfileBuilder.sanity_check` contained a regex `r"delta E .{0,10}> 5"`
  that looked for the literal substring `> 5` in colprof's log — which
  colprof never emits, so the warning was unreachable. Removed the dead
  tuple. Real ΔE evaluation already lives in Tab 5 (Check & Refine) via
  `profcheck`. The other two sanity checks (`out of gamut`,
  `Profile creation failed`) and the file-size checks are unchanged.

## v3.2.3
### Fixed
- **Gamut Analysis failed when comparison profile was loaded from
  `/System/Library/ColorSync/Profiles/`** (e.g. `sRGB Profile.icc`):
  ChromIQ copies the comparison ICC into a private temp directory before
  invoking `iccgamut`, and was using `shutil.copy2`, which copies file data
  *and* metadata. macOS system ColorSync profiles carry the SIP-protected
  BSD flag `SF_RESTRICTED` — the data copy succeeded but `copystat` failed
  with `[Errno 1] Operation not permitted` when re-applying the flag to the
  destination, surfacing as "Gamut Analysis Failed — Cannot copy ICC file".
  User-installed profiles under `~/Library/ColorSync/Profiles/` lacked the
  flag and were unaffected. ChromIQ now uses `shutil.copyfile`, which copies
  only the file bytes and skips metadata. Reported by @soul-traveller in #12.

### Changed
- Installation instructions now document the
  `xattr -dr com.apple.quarantine /Applications/ChromIQ.app` workaround for
  macOS Sonoma+ where Gatekeeper refuses to launch the ad-hoc-signed bundle.
  Bundled into the README and the auto-generated release notes for future
  builds.

### Project
- Added GitHub issue templates (`bug_report.yml`, `feature_request.yml`) and
  the supporting `platform:` / `Severity:` labels, so reports can be
  categorised consistently. Thanks to @soul-traveller for the suggestion.

## v3.2.2
### Fixed
- **Intermittent crash on app quit (`EXC_BAD_ACCESS` in `CrBrowserMain`)**:
  macOS occasionally reported "Python quit unexpectedly" after closing the
  app. The crash originated in `dealloc_QApplication` → `sip_api_visit_wrappers`
  — SIP was walking its wrapper graph during `QApplication` teardown and
  following a dangling pointer inside the `QWebEngineView` / Chromium subtree
  on the gamut viewer panel. The previous `aboutToQuit` handler loaded
  `about:blank` and slept 200 ms but never actually destroyed the view, so
  its Chromium child objects survived into `QApplication`'s destructor where
  the race fires. ChromIQ now also disconnects `loadFinished`, reparents the
  `QWebEnginePage` and the view to `None`, calls `deleteLater()` on both,
  and pumps the event loop so the deferred deletes run *before* the
  `QApplication` destructor.

## v3.2.1
### Fixed
- **Check/Refine — 3D gamut viewer flashed white on first open**: When the
  user opened the Check/Refine tab for the first time after launching the app,
  the embedded QWebEngineView briefly painted its default white surface before
  the dark `#111111` placeholder HTML rendered on top. The widget-level
  stylesheet only styled the QWidget chrome, not the Chromium-rendered page
  surface. `QWebEnginePage.setBackgroundColor` is now set to `#111111`
  immediately after constructing the view, so Chromium paints its very first
  compositor frame dark — no flash on first show.

## v3.2.0
### Added
- **macOS native print dialog — Adobe Color Printer Utility behaviour**: When "Use default
  macOS printer dialog" is enabled, ChromIQ now opens the real macOS print panel via PyObjC
  and sends the chart as untagged device RGB at its exact generated size. The print job is put
  into application-managed-colour mode (`AP_ColorMatchingMode` locked via PrintCore), and the
  selected driver's own "No Color Adjustment" / "Application Managed" option is auto-detected
  from its PPD and locked too — so the driver's colour controls appear greyed out and cannot be
  re-enabled, exactly like ACPU. No colour transform is applied; pixel values reach the printer
  unchanged.
- **Native macOS print — colour-management lock verification**: After every print, ChromIQ now
  reads the resolved colour-management keys back from the submitted job and confirms each one
  matches the values it locked (`AP_ColorMatchingMode = AP_ApplicationColorMatching`,
  `APCustomColorMatchingProfile = sRGB`, plus any vendor-PPD "no colour adjustment" key
  detected). On success, the result is recorded in `~/Library/Logs/ChromIQ/chromiq.log` as
  *"colour management verified OFF"*; on mismatch, a warning dialog tells the user the job was
  sent but the lock couldn't be verified, so they can check the swatch or switch print modes.
  The macOS print-mode warning text also explains that the system's "Color Matching" pane is
  cosmetic (macOS doesn't let third-party apps grey it out — Adobe Color Printer Utility has
  the same limitation), and that ChromIQ overrides it at the job level regardless of what the
  pane visibly shows.
- **Preflight confirmation dialog**: Before sending a job to CUPS, ChromIQ can show a summary of
  every option that will be sent (printer, paper size, media type, quality, tray, borderless,
  auto-detected orientation, forced-off duplex/colour management, and any detected mismatches).
  Toggleable in Settings → "Confirm print settings before sending to printer" (on by default).
- **Automatic page orientation**: ChromIQ now compares the chart's aspect ratio with the
  selected paper and requests portrait or landscape so the chart matches the media.
- **Page-size mismatch warning**: If the selected paper size doesn't match the size the chart
  was generated for, the preflight dialog flags it before you waste paper and ink.

### Changed
- **PostScript output**: The generated PostScript now uses the selected media's exact PageSize
  and centres the chart on it (instead of forcing the page to the TIFF's own dimensions), so the
  PS document and `lp -o PageSize=…` agree.
- **Print options order**: The "Borderless" option now appears directly after "Paper size" in
  the Print tab (was last), which reads more naturally.
- **Paper-mismatch check**: Now compares the chart against the printer's *printable area*
  (from the PPD's `*ImageableArea`) when available — instead of the full sheet — so the normal
  loss of the printer's hardware margins no longer trips the warning. Falls back to comparing
  against the full sheet with a wider tolerance when no printable-area data is available, and
  the warning is reworded to "possible paper mismatch".

### Fixed
- **Bogus "page-size mismatch" warning**: ArgyllCMS `printtarg` writes the chart TIFF's
  resolution in pixels-per-centimetre, which ChromIQ was reading as DPI directly — so an A4
  chart was reported as 533 × 754 mm and the preflight dialog showed a false mismatch warning
  (and the generated PostScript could be mis-sized). `_read_dpi` now honours the TIFF's
  ResolutionUnit tag.
- **Print tab — TIFF preview "shrunk" after chart generation**: When jumping straight from
  Create Chart to Print Chart, the preview sometimes rendered with a dark border around it
  (pixmap scaled too small). The preview's `showEvent` repainted synchronously, before Qt
  had activated the now-visible tab's layout, so the label still reported its hidden minimum
  size. Switching tabs and back happened to work because the second show landed after layout
  was already settled. The repaint is now deferred until layout activation completes, so the
  first show always uses the true label size.

## v3.1.4
### Fixed
- **Gamut viewer — empty profile error dialog**: When an ICC profile file is 0 bytes
  (e.g. from an interrupted colprof run), a clear popup now explains why the file is
  empty and how to rebuild it, instead of showing a cryptic "iccgamut exited with code 1"
  warning in the console.
- **Gamut viewer — iccgamut error dialog**: Any other iccgamut failure now shows a popup
  with the actual tool error message, common causes (corrupt or non-standard ICC file),
  and a pointer to the full log for further diagnosis.

## v3.1.3
### Added
- **Gamut viewer — 3D comparison overlay**: Profile A now keeps its natural per-vertex
  colours in combined view (instead of flat red). Profile B is rendered semi-transparent
  so both gamuts are visible simultaneously.
- **Gamut viewer — Opacity & Saturation sliders**: Live controls for Profile B's
  transparency and colour saturation in combined view. Values are saved as defaults.
- **Build Profile — FWA error dialog**: When colprof reports that the instrument does
  not support FWA compensation (ColorMunki, i1Studio, CC Studio), a clear popup
  explains why and what to do instead.
- **Build Profile — expanded tooltips**: All option tooltips across the manual, guided,
  printcal, and applycal modules now contain full explanations of what each option does
  and when to change it. Dialog widths increased where needed.

### Fixed
- **Gamut viewer — app close crash**: Closing the app while the 3D viewer was active
  caused a SIGBUS / bus error on macOS (Chromium GPU shared-memory race). Fixed by
  spinning a 200 ms nested event loop after navigating to about:blank on quit, giving
  the GPU subprocess time to release framebuffers cleanly.
- **Measure tab — instrument port spinbox**: Applied compact styling to match other
  inputs in the manual module.

## v3.1.2
### Fixed
- **Build Profile — Gamut Mapping path input**: The file-selection field in Build Profile → MANUAL → Gamut Mapping was collapsing to a ~2 px sliver. A new `compact_path` CSS rule (`min-height: 22px`) gives it a stable 22 px compact height matching the rest of the group.
- **Measure tab — Patch consistency tolerance spinbox**: Removed compact (22 px) styling from this control in the guided module; it now renders at standard input height.
- **Gamut viewer — Profiles section compact styling**: Profile and Compare path fields now use compact 22 px height; browse and clear buttons match. Vertical row spacing increased to 8 px and horizontal button spacing set to 4 px for a more consistent look.

## v3.1.1
### Added
- **Gamut viewer — app theme colours**: A new "Use app theme colours for 3D gamut viewer" toggle in Preferences → Behaviour (default: on) remaps the 3D model's vertex colours to ChromIQ's five spectrum accents (Magenta, Amber, Green, Cyan, Violet), preserving original lightness so the 3D shape reads clearly. The Lab axes (+a*, −a*, +b*, −b*) are mapped to the same palette; the grey L* axis and white/black-point spheres are left unchanged. Themed mode is pure client-side JavaScript — the original ArgyllCMS file is never modified.
- **Gamut viewer — improved tooltips**: All iccgamut option controls now have detailed ⓘ info dialogs with plain-English explanations and practical guidance. New tooltips added for the Show Axes, Mark Cusp Points, and Show Edge Plot checkboxes. Dialog widths enlarged for comfortable reading.

### Fixed
- **Windows ARM64 — 3D gamut viewer**: The embedded Chromium browser (QWebEngineView) now works on Qualcomm ARM64 hardware. The Chromium GPU blocklist prevented WebGL from initialising, showing a black screen or "Your browser does not support X3DOM" error. Applying `--ignore-gpu-blocklist --disable-gpu-compositing` at startup enables WebGL while routing all compositing through the software path, fixing the viewer on both ARM64 and x64 Windows.

## v3.1.0
### Added
- **Gamut Volume panel (Check & Refine tab)**: New right-side panel powered by ArgyllCMS `iccgamut` and `viewgam`. Displays the gamut volume of the active ICC profile as a number and as an interactive 3D mesh rendered in-app via QWebEngineView + X3DOM. Options: rendering intent, colour space (Lab / CIECAM02 Jab), surface resolution, mapping direction (forward / backward), axes, cusp markers, and edge plot.
- **Gamut comparison**: Load a second ICC/ICM profile to compare against the primary. ChromIQ computes both volumes, the delta %, the intersection volume, and bidirectional coverage percentages (A covered by B / B covered by A) using `viewgam`. A [PROFILE A] / [COMBINED] / [PROFILE B] toggle switches the 3D viewer between the three views.
- **Compare browse — smart starting location**: The comparison file dialog opens at ArgyllCMS's `ref/` folder (if installed) and shows sidebar shortcuts to the system ICC/ICM profile directories (`~/Library/ColorSync/Profiles`, `/Library/ColorSync/Profiles` on macOS; `System32\spool\drivers\color` on Windows).
- **Reset View button**: Resets the X3DOM camera to the default position via `x3d.runtime.resetView()`.

### Changed
- Default gamut surface resolution raised to **20** for noticeably smoother meshes out of the box.
- 3D viewer background colour now matches the TIFF preview dark-grey (`#111111`).

## v3.0.2
### Fixed
- **Load Chart dialog — button order on macOS**: Buttons now appear in the same left-to-right order as on Windows (Continue / Use as base for a new profile / Cancel) instead of being reordered by macOS HIG. Applies to all dialogs throughout the app.
- **Load Chart dialog — print-specific description text**: The "Continue" option no longer says "Continue printing…". Text is now neutral and accurate regardless of which tab triggered the dialog.
- **Load Chart dialog — Cancel now restores previous state**: Clicking Cancel fully undoes the load and restores whatever files were loaded before. Previously, files were partially loaded into several tabs before the dialog appeared, making Cancel ineffective.
- **"Use as base for a new profile" — copies all file types**: `.ti3` and `.icc`/`.icm` files are now copied to the new subfolder alongside `.ti2`, `.ti1`, and TIFF files. All tabs (Build Profile, Check & Refine, Measure, Print Chart) update to the new location after the copy.
- **"Use as base for a new profile" — file list in dialog**: The confirmation dialog now lists all file types that will be copied, including `.ti3` and `.icc`/`.icm` if present.
- **Load Chart dialog — text input focus**: The profile name field now reliably receives keyboard focus when the dialog opens, without requiring a click outside and back in to activate it.

## v3.0.1
### Fixed
- Mode buttons (GUIDED/MANUAL, calibration) now render at the correct font size on macOS; the Windows compatibility commit had introduced `setPixelSize(11)` + `font-size: 11px` CSS which made them noticeably smaller than action buttons

## v3.0.0
### Added
- **Windows support (x64 + ARM64)**: ChromIQ now ships a native Windows build alongside macOS. ArgyllCMS binary resolution appends `.exe` on Windows and auto-detects `Program Files\ArgyllCMS\bin` and `%LOCALAPPDATA%\ArgyllCMS\bin`. ICC profiles install to `%WINDIR%\System32\spool\drivers\color\`. Log files go to `%LOCALAPPDATA%\ChromIQ\Logs\`. Settings dialog shows Windows-specific download links and architecture guidance. CUPS is platform-guarded; the native Qt print dialog is the Windows print path. All platform-specific UI text adapts to the OS.
- **Windows — WinUSB driver installer**: New "Install USB Driver…" button in Settings → ArgyllCMS. ChromIQ detects connected colorimeters via the Windows registry and installs the WinUSB driver silently using `wdi-simple` (built from libwdi source in CI, elevated via UAC). If installation fails or is cancelled, a "Try Zadig" button opens the bundled Zadig GUI for guided installation. No test-signing mode, no command line, no restart required.
- **Build Profile — ICC media attributes and default intent**: Six new controls for `colprof -Z` flags in both Guided and Manual modes (and the calibration workflow's Build Profile module): Media Surface (Glossy / Matte), Color Type (Color / B&W), Media Type (Reflective / Transparent), Media Polarity (Positive / Negative), and Default Rendering Intent (Perceptual / Relative / Saturation / Absolute). All default to ArgyllCMS defaults so no `-Z` flag is emitted unless explicitly changed. Persisted via Save Defaults and user presets.

### Fixed
- **Windows — Calibration / all interactive prompts unresponsive**: Replaced pywinpty (unreliable in frozen PyInstaller apps) with a Windows-native approach: chartread starts with `CREATE_NEW_CONSOLE + SW_HIDE` so it gets a real but invisible console. Keystrokes are injected via `AttachConsole(pid)` + `WriteConsoleInputW`, writing directly into the same input buffer that `_getch()` reads — identical to a physical keypress. Works on both x64 and ARM64.
- **Windows — "Profile file was not created" false error**: `colprof` on Windows produces `.icm` files, not `.icc`. `expected_icc_path()` now probes for the actual file (`.icc` first, then `.icm`) so the post-build existence check no longer fails on Windows.
- **Windows — All UI text ~33 % larger than on macOS**: `1 pt = 1 px` at macOS's 72 DPI but `≈ 1.33 px` at Windows' 96 DPI. Every `font-size: Xpt` stylesheet string and every `setPointSize()` / `setPointSizeF()` call across the entire UI has been converted to `px` / `setPixelSize()`. Affected widgets: tab step labels, tab titles, guided-panel headlines, patch count, CHART/PRINT PREVIEW labels, spectrum progress bar, scan row badge, masthead wordmark, and tab bar labels.
- **Windows — Mode button text size and bold**: Mode buttons (GUIDED / MANUAL / calibration workflow buttons) now have an explicit `font-size: 11px` stylesheet rule, overriding the inherited 13 px from the global `QWidget` rule and matching the intended `setPixelSize(11)`. The active (checked) state also has `font-weight: 700` explicitly set, restoring bold which was inadvertently dropped in a beta patch.
- **Windows — Colorimeter detection**: `KNOWN_COLORIMETERS` dict keys are now consistently lowercase (fixing Datacolor Spyder and Colorvision devices); composite USB devices deduplicated by `(vid, pid)`; `libusb0` driver accepted alongside `winusb` so devices with the Argyll driver no longer appear as needing installation. Added X-Rite i1 Studio Argyll-driver entry (VID=0765 / PID=6008).
- **Windows — VM instrument conflict**: When a colorimeter is assigned to a Windows VM (Parallels, VMware, VirtualBox) and measurement is attempted on the macOS host, ChromIQ now shows a clear "Instrument Not Accessible" popup explaining the conflict and steps to resolve it.
- **Windows — Console flash**: `_test_argyll()` and the `taskkill` pre-measurement subprocess both pass `CREATE_NO_WINDOW`, eliminating brief console flashes on Windows.
- **Windows — Measure false success from stale .ti3**: `_on_measure_done()` compares the `.ti3` mtime to a snapshot taken at measurement start; a leftover file from a prior session no longer registers as a successful new measurement.
- **Windows — Device-not-found error undetected**: `_NO_INSTRUMENT_RE` now also matches `"No suitable instruments found"` and `"No instruments connected to use!"`, which are the strings Argyll prints on Windows when the USB driver is missing or the device is inaccessible.
- **Settings — macOS-only options hidden on Windows**: The "Use default macOS printer dialog" checkbox and tooltip are hidden when running on Windows.
- **Settings — Windows layout**: "Install USB Driver…" appears on the same row as Test Binaries, Auto-detect, and Download Latest Argyll, matching the macOS layout.
- **Create Chart — "Good Distribution" label**: Shortened from "(recommended)" to "(recomm.)" so the label fits within its column on Windows.

## v3.0.0-beta.10
### Added
- **Build Profile — colprof `-Z` media attributes and default intent**: Two new controls appear in the **Color Science** section of the guided Build Profile panel, and five controls appear in the manual mode panel. In both modes the same controls are also available in the Calibration tab's Build Profile module.
  - **Media Surface** (guided + manual): Glossy / Reflective (default) or Matte (`-Z m`). Embeds the surface type in the ICC profile header so colour management systems can automatically select the correct profile when both a matte and glossy profile are installed.
  - **Color Type** (guided + manual): Color media (default) or Black & White (`-Z b`). Marks the profile for monochrome inksets or pure-greyscale print modes.
  - **Media Type** (manual only): Reflective (default) or Transparent (`-Z t`). For transparency inksets and slide-film workflows.
  - **Media Polarity** (manual only): Positive (default) or Negative (`-Z n`). For photographic film negative workflows.
  - **Default Rendering Intent** (manual only): Not set / Perceptual / Relative Colorimetric / Saturation / Absolute Colorimetric (`-Z p/r/s/a`). Marks which rendering intent the ICC profile header advertises as its default, used by CMSes that respect this field.
  - All selections default to the ArgyllCMS defaults so no `-Z` flag is emitted unless the user explicitly changes a value.
  - Settings are persisted via "Save as defaults" (guided and manual) and user presets (manual).

## v3.0.0-beta.9
### Fixed
- **Windows — All UI text ~33% larger than on macOS**: Qt stylesheet `pt` units are DPI-dependent — 1 pt = 1 px at 72 DPI (macOS) but ≈ 1.33 px at 96 DPI (Windows). Every inline `font-size: Xpt` string and every `setPointSize()`/`setPointSizeF()` call across the entire UI has been converted to `px`/`setPixelSize()`. Affected widgets: tab step labels, tab titles, guided-panel headlines and flavour text (all tabs), patch count number, CHART/PRINT PREVIEW labels, spectrum progress bar, scan row badge, and the masthead wordmark.
- **Windows — Tab bar text too large**: `SpectrumTabBar` used `setPointSize(13)` for tab labels; converted to `setPixelSize(13)` for consistent size across platforms.
- **Settings — macOS "Use native printer dialog" checkbox misaligned when hidden on Windows**: The row containing this macOS-only option had extra margins that shifted surrounding controls when the checkbox was invisible. Fixed layout margins; dialog minimum width increased to 840 px on both platforms so button labels are never clipped.
- **Settings — "Install USB Driver…" button below other ArgyllCMS buttons on Windows**: The button now appears on the same row as Test Binaries, Auto-detect, and Download Latest Argyll, consistent with the macOS layout.
- **Measure — No explanation when measurement device is connected to a virtual machine**: When a colorimeter is assigned to a Windows VM (Parallels, VMware, VirtualBox, etc.) and measurement is started on the macOS host, ArgyllCMS prints `"Failed to get piif for USB device"` and exits immediately. ChromIQ now detects this string and shows a clear popup — "Instrument Not Accessible" — explaining the VM conflict and the steps to resolve it (disconnect device from VM, reconnect, retry).

## v3.0.0-beta.8
### Fixed
- **Windows ARM64 — Interactive prompts still unresponsive (beta.7 regression on ARM64)**: On ARM64 Windows, pywinpty's native DLL is x64-only and fails to load (`DLL load failed: module not found`), setting `_WINPTY_AVAILABLE = False`. The `_run_pty()` guard then bypassed `_run_winpty()` entirely and fell back to the old pipe path — defeating the beta.7 `CREATE_NEW_CONSOLE + WriteConsoleInputW` fix on the very platform it was needed most. Fixed by removing the `_WINPTY_AVAILABLE` conditional: `_run_winpty()` has no pywinpty dependency since beta.7 and is now called unconditionally on Windows. Confirmed on ARM64 VM: `_win_inject_key: ch='\r' ok=True written=2` → `Calibration complete`.
- **Windows — X-Rite i1 Studio (Argyll driver) not detected by USB driver dialog**: The i1 Studio registers as VID=0765 PID=6008 when using the Argyll `libusb0` driver, but the app only knew PID `d0c0` (native HID). Added `("0765", "6008"): "X-Rite i1 Studio (Argyll)"` to `KNOWN_COLORIMETERS`.
- **Windows — Devices with Argyll `libusb0` driver shown as needing installation**: `enumerate_connected()` checked only for `winusb` service, so devices with the Argyll `libusb0` driver appeared as uninstalled even though ArgyllCMS can use them. Extended the check to accept both `winusb` and `libusb0`.
### Removed
- `pywinpty` dependency removed from `requirements.txt` — unused since beta.7 and broken on ARM64 Windows.

## v3.0.0-beta.7
### Fixed
- **Windows — Calibration / all interactive prompts still unresponsive**: Pywinpty proved unreliable across four beta releases in a frozen PyInstaller app — WinPTY backend cannot locate `winpty-agent.exe` inside `_MEIPASS`, and ConPTY's `write()` never reliably reaches MSVCRT's `_getch()`. Replaced pywinpty entirely with the Windows-native approach: chartread now starts with `CREATE_NEW_CONSOLE + SW_HIDE` so it gets a real but invisible console (which `_getch()` opens via `\\.\CONIN$` directly). Keystrokes are injected via `AttachConsole(pid)` + `WriteConsoleInputW`, writing events directly into the same input buffer that `_getch()` reads from — identical to a physical keypress. Applies to calibration, strip selection, guided navigation, Esc-to-abort, and all other interactive chartread prompts.

## v3.0.0-beta.6
### Fixed
- **Windows — Calibration keypress (and all interactive prompts) still unresponsive**: Root cause identified: pywinpty's ConPTY backend emits a spurious `EOFError` on its output pipe whenever the child process blocks on `_getch()` waiting for input. The reader thread caught this as a true end-of-process, set `_winpty_proc = None`, and the subsequent `write_stdin("\r")` from the "Start Calibration" button silently fell through to no-op. Two fixes: (1) `_run_winpty()` now requests the **WinPTY backend** explicitly (`Backend.WinPTY`), which injects keystrokes via `WriteConsoleInput` and does not have the spurious-EOF problem; falls back to ConPTY if WinPTY is unavailable. (2) `_inner()` reader thread now checks `proc.isalive` before treating `EOFError` as terminal — if the process is still running it sleeps 50 ms and retries, preventing premature teardown. Both fixes apply equally to calibration, strip selection, guided navigation, and all other interactive chartread prompts.

## v3.0.0-beta.5
### Fixed
- **Windows — "No colorimeter detected" for Datacolor Spyder and Colorvision devices**: `KNOWN_COLORIMETERS` used mixed-case VID keys (`"085C"`, `"04DB"`) but the registry lookup normalises to lowercase, so `"085c" != "085C"` and all Datacolor Spyder and Colorvision Spyder 1 devices were silently skipped. All dict keys are now consistently lowercase. X-Rite devices (VID `0765`, all digits) were unaffected.
- **Windows — Composite USB devices listed multiple times**: Composite devices register a parent key plus one key per interface (`VID&PID&MI_00`, `VID&PID&MI_01`…). `enumerate_connected()` now deduplicates by `(vid, pid)` so each device appears once in the installer dialog.

## v3.0.0-beta.4
### Fixed
- **Windows — Calibration keypress still unresponsive (beta.3 regression)**: Two bugs prevented pywinpty from activating in the bundled app. (1) `ChromIQWin.spec` listed `'winpty'` only in `hiddenimports`, which omits the compiled `.pyd` extension's native binaries — PyInstaller now collects winpty via `collect_all('winpty')`. (2) `_winpty_reader` called `proc.read(4096, timeout=…)` but pywinpty ≥ 2.0 `read()` has no `timeout` parameter, raising `TypeError` on the first call and immediately killing the reader thread. The reader is rewritten with an inner thread + `queue.Queue` to replicate the 150 ms silence-window flush without using the unsupported parameter.

## v3.0.0-beta.3
### Fixed
- **Windows — Calibration prompt unresponsive**: chartread's interactive calibration keypress now works correctly on Windows. The previous subprocess-pipe approach couldn't deliver a real console to chartread's `_getch()` call; replaced with a pywinpty ConPTY pseudo-terminal so the device calibration sequence completes as expected.
- **Settings — Console flash when testing Argyll binaries**: The `_test_argyll()` check now passes `CREATE_NO_WINDOW` to the subprocess, eliminating the brief console window that flashed on Windows when opening the Preferences dialog.
- **Windows — In-app WinUSB driver installer**: New "Install USB Driver…" button in Settings → ArgyllCMS. ChromIQ detects connected colorimeters via the Windows registry, then installs the WinUSB driver silently using wdi-simple (built from libwdi source in CI, elevated via UAC). If automatic installation fails or is cancelled, a fallback "Try Zadig" button opens the bundled Zadig GUI for guided installation. No test-signing mode, no command line, no restart required.

## v3.0.0-beta.2
### Fixed
- **Settings — Hide macOS printer dialog option on Windows**: The "Use default macOS printer dialog" checkbox and its tooltip are now invisible when running on Windows, where the option has no effect.
- **Windows — Mode button text clipped when active**: Mode buttons (GUIDED / MANUAL / calibration buttons) were sized using Medium-weight font metrics but rendered bold when checked (via CSS `font-weight: 700`), causing text to overflow on Windows where font substitution metrics differ. Buttons now compute their size hint from the bold font, with CSS explicitly resetting to normal weight for the unchecked state.
- **Windows — Font rendering consistency**: `ButtonFontFilter` and the `SpectrumTabBar` now specify an explicit font-family fallback chain (`Menlo → Consolas → Courier New → monospace` for buttons; `Inter → Segoe UI → system-ui` for tab labels) so Windows substitution is deterministic rather than OS-default.
- **Measure — Console window flash on Windows**: The `taskkill` subprocess used to kill any pre-existing `chartread.exe` before measurement now passes `creationflags=CREATE_NO_WINDOW`, eliminating the brief console window that appeared on Windows when starting measurement.
- **Measure — False "Measurement complete" from stale .ti3**: `_on_measure_done()` now checks whether the `.ti3` file was created or modified *during the current run* (by comparing its mtime to a snapshot taken at measurement start). A leftover `.ti3` from a previous session no longer causes a failed measurement to be reported as successful.
- **Measure — Device-not-found error undetected on Windows**: `_NO_INSTRUMENT_RE` now also matches `"No suitable instruments found"` and `"No instruments connected to use!"`, which are the strings Argyll outputs on Windows when the USB driver is missing or the device is inaccessible.
- **Measure — "No Instrument Found" dialog text**: The dialog now says "Windows PC" instead of "Mac" on Windows, and adds a hint to install the Argyll WinUSB driver via the ArgyllInstallers tool or Zadig.

## v3.0.0-beta.1
### Added
- **Windows beta support**: Initial Windows compatibility layer. All macOS behaviour is completely unchanged — every adaptation is behind a `sys.platform` guard. Changes include:
  - ArgyllCMS binary resolution appends `.exe` on Windows; auto-detection scans `Program Files\ArgyllCMS\bin` and `%LOCALAPPDATA%\ArgyllCMS\bin`
  - Interactive ArgyllCMS tools (chartread) use subprocess pipes instead of a PTY on Windows, with the same 150 ms silence-window flush logic so prompts remain visible
  - CUPS subsystem (`cups` module, `lp`, `lpoptions`) is platform-guarded; on Windows the native Qt print dialog is the default and only print path
  - ICC profiles install to `%WINDIR%\System32\spool\drivers\color\` on Windows with a clear error if elevation is required
  - Log files written to `%LOCALAPPDATA%\ChromIQ\Logs\` on Windows
  - Settings dialog links to the Windows ArgyllCMS download page with Windows-specific architecture guidance
  - Print tab warning text adapts to the OS name
  - File dialog `/Applications` sidebar shortcut is macOS-only

## v2.11.0
### Added
- **Print Chart — Native macOS printer dialog**: New option in Preferences → Behaviour: "Use default macOS printer dialog". When enabled, the printer selection and CUPS print options are hidden; clicking Print Current Page or Print All Pages opens the standard macOS print sheet instead of ChromIQ's built-in PostScript / CUPS pipeline. The info box updates to remind the user to disable colour management manually in the driver panel, with per-brand instructions for Epson, Canon, HP, and other manufacturers. The same instructions appear in the Preferences tooltip. Defaults to off — existing behaviour is unchanged unless the option is explicitly enabled.

## v2.10.3
### Fixed
- **Print — Stuck PostScript job on TIFF fallback**: When a printer rejects PostScript and the app retries with a TIFF, the original PS job is now cancelled from the CUPS queue before the TIFF is submitted, preventing it from lingering as a stuck job.
- **Create Chart — Pre-conditioning profile staged to working folder**: The `-c` pre-conditioning ICC/ICM profile is now copied into the session working folder (`~/ChromIQ/<name>/`) with a `pre_` prefix at chart-generation time. The working-folder copy is what targen receives, keeping all session files together. The file is preserved across normal profiling runs but is deleted when generating a calibration target (full fresh-start wipe).

## v2.10.2
### Fixed
- **All tabs — Stale file state after new measurement cycle**: Loading a new `.ti2` file in Print Chart or Measure now clears any previously loaded `.ti3` in Build Profile and any loaded `.ti3`/`.icc` in Check & Refine. Creating a new chart already had this behaviour; Print Chart and Measure now match.
- **Build Profile — Profile description not updated on reload**: Loading a second `.ti3` file now always overwrites the profile description field in both Guided and Manual modules (previously only filled it when the field was empty).
- **Build Profile — Loaded `.ti3` clears Check & Refine**: Manually loading a `.ti3` in Build Profile now resets the Check & Refine tab, preventing stale results from a previous profile run being checked against a new measurement.
- **Measure — Completion clears Check & Refine**: When measurement finishes and the resulting `.ti3` is sent to Build Profile, any previously loaded files in Check & Refine are cleared.

## v2.10.1
### Changed
- **All tabs — Tooltip improvements**: Tooltip dialogs now auto-size correctly to fit their content. All Measure tab tooltips have been expanded with practical guidance on when and why to use each option. The Presets tooltip is consistent across all four tabs and uses a structured bullet layout.

## v2.10.0
### Added
- **Create Chart — Cascading colorant slots (-D)**: The "Add/Remove Colorant" expert option in Manual mode now supports up to 11 stacked `-D` modifications. Enabling one slot reveals the next; disabling a slot collapses all subsequent ones. Values and enabled states are saved and restored through presets and Save Defaults. Allows configuring extended-gamut printers (e.g. CMYK + Orange + Green + Light Cyan) without using the command line.

### Fixed
- **TIFF preview — High channel-count fallback**: The no-sidecar channel layout fallback table now covers 9, 10, and 11-channel TIFFs. Previously anything above 8 channels fell back to an all-black heuristic.
- **Create Chart — Working folder cleanup**: `.json` and `.cal` files are now included in both the calibration-target and normal-profiling cleanup passes. In normal mode `cal_*`-prefixed files are preserved; in calibration-target mode all matching files are wiped.

## v2.9.4
### Fixed
- **Create Chart — Calibration target cleanup**: Generating a calibration target now also removes stale `.channels.json` sidecar files from the working folder (previously only `ti1/ti2/tif/cht/ps` extensions were wiped, leaving the old JSON behind).

## v2.9.3
### Changed
- **Create Chart — Calibration target pre-fill**: Enabling "Create target for calibration" now immediately writes the calibration-appropriate parameter values (patches = 0, white/black patches = 0, single-channel steps = 20, good distribution off, randomisation off) directly into the visible parameter widgets, so the user can review and adjust them before clicking Generate. Unchecking the option restores the previous widget values.

## v2.9.2
### Changed
- **Create Chart — Compact parameter inputs**: Comboboxes, spinboxes, line-edit fields, and browse buttons in the targen and printtarg parameter sections (Basic and Expert Options) now use the same reduced height as the Measure tab's additional options, keeping the panel more compact.

## v2.9.1
### Fixed
- **Create Chart — Calibration file auto-fill**: Removed erroneous `set_user_enabled(False)` calls that were unchecking the `-K` and `-I` enable-checkboxes on every auto-fill. The path is now pre-filled into both fields without touching the checkbox state — the user chooses which option to enable.

## v2.9.0
### Added
- **Create Calibration File — Channel target overrides**: Per-channel initial target controls for C/M/Y/K and extended inkset channels (Ch4–Ch7). Each channel can override the maximum device %, development target %, white-point minimum ΔE, and 50 % tone target that `printcal` computes automatically. Extended channels are hidden behind a disclosure checkbox and persist across sessions.
- **Create Calibration File — Calibration Metadata**: New section for embedding a description, manufacturer, model, and copyright string in the `.cal` file header (flags `-D`, `-A`, `-M`, `-C`). Description is auto-suggested from the loaded `.ti3` filename.
- **Create Calibration File — Imitation target mode**: New "Imitation target" mode (`-I`) creates a null-calibration `.cal` from an existing `.ti3` — useful for deriving a calibration target when no previous `.cal` exists. Target override controls are shared with Initial calibration mode.
- **Create Calibration File — Dry run**: New "Dry run" checkbox (`-d`) simulates the full calibration calculation without writing any files, so settings can be verified before committing.
- **Create Calibration File — Scrollable UI**: The module now scrolls vertically, keeping the run button and log pinned outside the scroll area.
- **Create Calibration File — Progress bar**: Spectrum progress bar shown while `printcal` is running.
- **Create Calibration File — Result dialog**: After a successful run a rich dialog explains the `-K` / `-I` printtarg flags and offers a "Go to Create Chart →" button that navigates directly to the Create Chart tab with the `.cal` path already filled in.
- **Apply Calibration — Progress bar**: Spectrum progress bar shown while `applycal` is running.
- **Apply Calibration — Result dialog**: After a successful `apply` run a dialog offers "Install on this Mac" to immediately register the calibrated profile with macOS ColorSync.
- **Build Profile — Apply Calibration option**: When calibration mode is enabled, the "Profile Built" result dialog gains an "Apply Calibration →" button that navigates to the Apply Calibration module with the ICC path pre-filled.
- **Measure — Calibration-aware completion dialog**: When all stripes of a `cal_*` target are read (calibration mode enabled), the "All Stripes Read" dialog is replaced by a "Calibration Measurement Complete" variant whose primary button reads "Create Calibration File →" and explains the next step clearly.

### Changed
- **Create Calibration File — Mode tooltip**: Tooltip text updated to include flag names (`-i`, `-r`, `-e`, `-I`) and expanded description for all four modes.
- **Measure — Completion log message**: The "[OK] Measurement complete" log entry now references the correct next tab ("4. Calibration & Profiling" vs "4. Build Profile") depending on whether the measurement is a calibration or profiling run.
- **Create Chart — Calibration file auto-fill**: When a `.cal` file is found in the working folder, its path is pre-filled into both the `-K` and `-I` fields. Neither option is enabled automatically — the user selects which one applies to their workflow.

## v2.8.1
### Fixed
- **Create Chart — Manual module — Layout**: Left panel width reduced to 580 px to match the Print Chart tab. Parameter combo boxes no longer force horizontal scrolling when their option labels are long — the selected value still displays fully, but the minimum control width is decoupled from the longest item text.

## v2.8.0
### Changed
- **Main window — Responsive sizing**: The window now opens at a size that fits the available screen. On large displays (≥ 1440 × 1025) behaviour is unchanged. On smaller screens such as a 13″ MacBook (1280 × 800) the window scales down to fit. A minimum size of 900 × 650 is enforced so the UI remains usable. Geometry saved on a larger display is clamped to the current screen on the next launch.
- **Print Chart — Scrollable options panel**: The print-options group ("No configurable options detected" / printer driver options) and the verification warning are now inside a scroll area. When the window is small they scroll vertically instead of being squeezed together, while the printer selector remains pinned above the scroll area and the action buttons remain pinned below.
- **Print Chart — Button alignment**: The print-action buttons are now flush with the bottom of the panel, consistent with the action buttons in all other tabs.

## v2.7.0
### Added
- **Session Restore**: New "Restore last session on launch" toggle in Preferences → Behaviour (off by default). When enabled, ChromIQ reloads the previously active profiling project on startup: the .ti2 path in Measure, TIFFs in Print Chart and Measure, .ti3 and .icc paths in Build Profile, and both paths in Check & Refine. If any file is missing or was moved it is silently skipped — no errors.

### Changed
- **Print Chart — Printer tooltip and warning label**: Updated to accurately describe the PostScript-first pipeline with automatic TIFF fallback, replacing outdated text that referred only to direct TIFF/CUPS submission.

## v2.6.0
### Added
- **Optional Calibration Workflow**: A full printer calibration workflow (printcal → applycal) is now available behind a toggle in Preferences → Behaviour → "Enable calibration options". Off by default — most users profiling consumer inkjet printers do not need it.
  - When enabled: guided mode panels are hidden across all tabs; tab 4 is renamed "Calibration & Profiling" with matching header text; a three-module selector (Create Calibration File / Build Profile / Apply Calibration) appears.
  - **Create Chart — Calibration target**: A "Create target for calibration" checkbox prefixes all output files with `cal_`, applies calibration-specific parameter overrides (`-s 20`, `-r`, etc.), and performs a full folder clean. When a `cal_<name>.cal` file is found in the working folder, the `-I` and `-K` fields are pre-filled automatically.
  - **Measure — Smart routing**: Finished measurements whose filename starts with `cal_` are automatically routed to the Create Calibration File module instead of Build Profile.
  - **Create Calibration File (printcal)**: Runs Argyll's `printcal` to generate a `.cal` curve file from a calibration measurement. Options: mode (initial / recalibrate / verify), previous `.cal` for recalibration, smoothing, verbosity. On success, the `.cal` path is handed directly to the Apply Calibration module.
  - **Apply Calibration (applycal)**: Runs Argyll's `applycal` to bake, remove, or check calibration curves on an ICC profile. Auto-fills the `.cal` field from printcal output and the input ICC field from Build Profile output. Leaving the output field blank saves as `cal_<name>.icc`.
  - **Build Profile**: ICC path handed to Apply Calibration automatically on success.
  - All new options support Save as Defaults and restore correctly on relaunch.

## v2.5.0
### Added
- **Create Chart — Manual module — printtarg Expert Options**: Eleven new printtarg parameters now available in the Expert Options panel, all correctly wired through to the `printtarg` binary:
  - **N-Channel TIFF (-N)**: For printers with more than 4 ink channels, encodes extra channels using TIFF's alpha-channel slots so all ink values are preserved in a single file.
  - **Apply Calibration (-K)**: Loads a `.cal` file (from Argyll's `printcal`) and remaps all patch values through its curves before chart generation, then embeds the calibration in the `.ti2` output. For printers without native calibration capability.
  - **Include Calibration (-I)**: Embeds a `.cal` file as metadata in the `.ti2` output without modifying patch values. For printers or RIPs that apply calibration natively during printing. Mutually exclusive with -K — enabling one automatically unchecks the other.
  - **Disable TIFF Compression (-C)**: Outputs uncompressed TIFF files for RIPs or drivers that cannot handle LZW-compressed TIFFs.
  - **Dither 8-bit Output (-D)**: Uses error-diffusion dithering when down-sampling from internal 16-bit precision to 8-bit TIFF output.
  - **Suppress CUPS CMM Header (-U)**: Removes the `cups-disable-cmm` job ticket comment from PostScript and EPS output files.
  - **Randomisation Seed (-R)**: Sets the starting seed for patch randomisation, producing identical layouts across sessions for reproducibility.
  - **Quantize Bits (-Q)**: Rounds all patch colour values to a specified bit depth before chart generation.
  - **Spacer-Only Scale (-A)**: Scales spacer bars independently from patch dimensions (complements the existing Patch Size Scale `-a`).
  - **No Spacers (-n)**: Removes all spacer bars between patches and strips.
  - **Force Colored Spacers (-c)**: Forces spacer areas to render in colour rather than black/white.

## v2.4.1
### Fixed
- **TIFF Preview — Multi-channel files with more than 4 inks**: PIL silently drops extra channels when opening Separated TIFFs with 5 or more inks (e.g. CMYK + LC LM). The preview now routes these files directly to tifffile, preserving all ink channels.
- **TIFF Preview — 16-bit and high-bit-depth TIFFs via tifffile**: Non-uint8 pixel data was passed raw to PIL, corrupting colours. The loader now normalises all data to uint8 before converting to RGB.

## v2.4.0
### Changed
- **Print Chart — Printing pipeline**: Replaced the TIFF/CUPS-RGB path with a PostScript Level 2/3 pipeline. The PS document embeds device-dependent colour spaces (`/DeviceGray`, `/DeviceRGB`, `/DeviceCMYK`, `/DeviceN`) and the `%cupsJobTicket: cups-disable-cmm` header, so CUPS and macOS ColorSync apply zero colour transforms to the profiling target — the pixel values that leave the application are exactly the values the spectrophotometer measures.
### Added
- **Print Chart — CMYK and multi-channel target support**: Profiling targets with 4 channels (CMYK) and 5–17 channels (DeviceN, e.g. CMYK + LC LM or extended-gamut inks) are now printed correctly. Previously all targets were force-cast to DeviceRGB by CUPS, corrupting CMYK and multi-ink patch data.
- **Print Chart — 16-bit TIFF support**: 16-bit profiling targets generated with `printtarg -T300` are printed as PostScript Level 3 with 16-bit colour components, preserving full bit depth for printers and RIPs with a true 16-bit pipeline.
- **Print Chart — Automatic TIFF fallback for non-PostScript printers**: Driverless / AirPrint printers (e.g. Epson EcoTank series) reject PostScript at the CUPS level. The pipeline now detects this and automatically retries by submitting the original TIFF with colour-space-aware CUPS raster options (`cupsColorSpace`, `ColorModel`), bypassing ColorSync without requiring PostScript support on the printer.

## v2.3.3
### Fixed
- **Create Chart — Manual module — Total Patch Count (-f) with 0**: Setting `-f` to 0 now passes `-f 0` directly to targen, letting targen determine the patch count automatically. Previously, 0 triggered a page-capacity database lookup (the guided-mode behaviour), causing the page to fill completely regardless of other parameters such as Single Channel Steps.

## v2.3.2
### Fixed
- **TIFF Preview — LZW-compressed multi-channel TIFFs**: Bundled app threw `could not import name 'lzw_decode' from 'imagecodecs'` when opening LZW-compressed CMYK or multi-ink TIFFs. PyInstaller's static analysis missed imagecodecs' compiled codec extensions; the spec now uses `collect_all('imagecodecs')` to include every binary.

## v2.3.1
### Fixed
- **Create Chart — Manual module — Total Patch Count (-f)**: The spinbox minimum was hardcoded to 50, preventing values below 50 from being entered. The minimum is now 0, matching targen's actual accepted range. Setting 0 passes `-f 0` to targen, which lets targen determine the patch count automatically based on other parameters.

## v2.3.0
### Added
- **TIFF Preview — Multi-channel support**: The preview widget now loads and displays CMYK and multi-channel TIFFs (up to 8 inks: LC, LM, Orange, Green, Violet, etc.) generated by ArgyllCMS. Previously, CMYK files showed wrong colours and 6–8 channel files failed silently.
- **TIFF Preview — ICC colour accuracy**: CMYK channels are now converted to sRGB using the bundled US Web Coated SWOP v2 ICC profile, with system Adobe/ColorSync profiles as fallbacks. Colours now match Photoshop rather than the naive subtractive formula.
- **TIFF Preview — Ink channel sidecar**: After chart generation a `.channels.json` sidecar is written alongside the TIFFs so that re-loading the file in a later session automatically identifies the correct ink order (C, M, Y, K, LC, LM, …) without any user input.
- **Stripe detection — Multi-channel TIFFs**: The Measure tab's strip auto-detection now works on multi-channel Separated TIFFs.
### Fixed
- **TIFF Preview — Sizing on tab switch**: When a chart was generated while on the Create Chart tab, the Print and Measure tab previews rendered too small with dark borders until something else triggered a repaint. The preview now repaints immediately when the tab is made active.

## v2.2.3
### Fixed
- **Create Chart — Manual module — Expert targen options**: Pre-conditioning Profile (`-c`), Calibration Override (`-C`), Add/Remove Colorant (`-D`), Neutral Axis Emphasis (`-N`), and Dark Region Emphasis (`-V`) were rendered in the UI but silently ignored — none of their values were passed to `targen`. All five are now correctly collected and included in the command.
- **App crash on close (macOS "quit unexpectedly")**: Closing the app while a measurement was running, or shortly after one completed, could trigger a segfault because a background PTY reader thread was still emitting Qt signals into objects being torn down. `closeEvent` now shuts down all running processes, closes the PTY file descriptor, and joins the reader thread before handing control back to Qt.

## v2.2.2
### Fixed
- **Create Chart — Manual module — Expert Options**: Preserve Patch Order (`-r`), Force B&W Spacers (`-b`), and Don't Limit Strip Length (`-P`) checkboxes now correctly pass their flags to printtarg. Previously toggling them had no effect because `ParameterWidget.get_raw_value()` was missing the same guard that `get_value()` already had for expert boolean widgets.

## v2.2.1
### Improved
- **Create Chart → Generate Chart**: Clicking Generate Chart now resets the Build Profile and Check & Refine tabs — clears any loaded .ti3 file, profile description, manufacturer, model, and copyright fields, and disables the Build button — so stale data from a previous session is never accidentally carried forward.
- **Create Chart — Guided module — Paper Size**: A3+ Portrait (329 × 483 mm) is now hidden when i1Pro 3 Plus is selected as the instrument, since its patch capacity is too low for a usable profile at that size.

## v2.2.0
### Added
- **Create Chart — Paper Size: Custom**: Both the Manual and Guided modules now include a "Custom (enter dimensions)" option in the Paper Size dropdown. Selecting it reveals width and height fields (in mm) whose values are passed directly to printtarg as `-pWxH`.
- **Create Chart — Paper Size: A3+**: A3+ Portrait (329 × 483 mm) and A3+ Landscape (483 × 329 mm) are now available as named paper sizes in both the Manual and Guided modules.
- **Create Chart — Paper Size: Photo formats**: 8×10" (203 × 254 mm), 5×7" (127 × 178 mm), and 4×6" (102 × 152 mm) added to both modules. In Guided mode, 5×7" and 4×6" are hidden for i1Pro 3 Plus where patch counts are too low for a usable profile.
- **Create Chart — Don't Limit Strip Length (-P)**: New expert option in the printtarg Expert Options section. Removes printtarg's default strip-length cap, useful for narrow roll paper or minimising strip count.
### Improved
- **Create Chart — Paper Size dropdown**: Sizes are now ordered from largest to smallest (A2 → A3+ → A3 → Tabloid → Legal → A4 → Letter → photo formats) in both the Manual and Guided modules.
- **Patch database**: All new paper sizes measured empirically with Argyll 3.5.0 for every instrument (i1Pro, i1Pro 3 Plus, ColorMunki standard and double-density, SpectroScan) × border-suppress setting combination. No estimated values.

## v2.1.2
### Improved
- **Settings — Behaviour**: New "Restore last active tab on launch" option. When enabled (default), the app re-opens on whichever tab was active when it was closed. When disabled, it always starts on the first tab.
- **Settings — Checkbox style**: Checked checkboxes in the Settings dialog now use the same grey/white colour as the "Restore Factory Defaults" button instead of the global cyan accent.
- **Print Chart tab**: The info panel now includes a note that colour management is disabled automatically via CUPS options, ensuring the printer always receives unaltered RGB values.
### Fixed
- **Create Chart — Guided module**: Tooltip buttons for "Double density", "Number of pages", and "Suppress left clip border" were positioned next to their controls instead of right-aligned. All three now align with the rest of the panel.
- **Build Profile — Manual module**: Tooltip buttons for "Smoothing / Noise" and "Dark Region Emphasis" in the Measurement & Smoothing section were positioned next to their controls instead of right-aligned.
- **Measure tab — Guided module**: Patch consistency tolerance (-T) option is now visible and enabled by default (0.7), pre-checked on every launch.

## v2.1.1
### Improved
- **All tabs — Guided module**: Each guided panel now shows a small motivational statement directly above the action buttons — a headline in Georgia with an accent-coloured italic punctuation mark and a one-line subtext in Menlo. Measure: "Keep calm!" / "Scan each strip with a slow, steady motion." Check & Refine: "Are you nervous?" / "Your colors are in good hands." Build Profile: "Ready to build?" / "Awaiting your command." — switches to "Working hard…" / "Good things take time." while colprof runs. Print Chart: "Feed the beast!" / "Your printer is hungry." — permanently visible, with load and print buttons moved to the bottom of the panel for a cleaner layout.
### Fixed
- **App bundle codesigning**: Replaced `codesign --deep` with an explicit bottom-up signing pass (leaf `.so`/`.dylib` → `.framework` bundles → outer `.app`). The previous `--deep` flag was re-signing already-signed internals and corrupting the code directory on Apple Silicon, causing Gatekeeper to reject the ARM build.

## v2.1.0
### Added
- **Measure tab — Manual mode refinement**: "Refine existing measurement (-r)" and "Use refinement strips file" options are now available in Manual mode, mirroring the Guided module. The refine option and strip file picker appear automatically when a `.ti3` file is present, and the guided strip-by-strip navigation activates when a strips file is loaded.

### Improved
- **Measure tab — Guided module**: Measurement Instrument section, Skip Initial Calibration, Patch-by-Patch Mode, and Additional Options section are now hidden in Guided mode, keeping the panel focused on the essential workflow steps.
- **Build Profile tab — Guided module**: Algorithm, Quality, and B2A table rows are hidden in Guided mode (Profile Description remains visible). Measurement & Smoothing, Color Science, and Advanced sections are hidden entirely. In Gamut Mapping, only the Gamut Source file picker is shown; Perceptual/Saturation Intent Overrides and nP/nS/nI flags rows are hidden.
- **Check & Refine tab — Guided module**: Delta E Formula, Rendering Intent, Sort by ΔE, and Verbosity rows are hidden in Guided mode (only the re-measurement threshold remains visible). Advanced Options section is hidden entirely.
- **Measure tab layout**: Fixed excess gap between the first section and the module action buttons; corrected spacing between the action buttons and the log output to match the 8 px standard used across all other tabs.

## v2.0.9
### Improved
- **Create Chart — Calibration Override (-C)**: New expert option in the targen Expert Options section. Accepts a `.cal` file whose calibration curves are applied when estimating the ink limit for patch generation, overriding any `.cal` embedded in a previous .ti3. Type `none` to explicitly suppress .cal use.

## v2.0.8
### Improved
- **Create Chart — Device Type (-d)**: Expanded from 6 to 16 options (0–15) matching targen 3.5.0 exactly. Adds Print grey (0) and all multi-channel CMYK combinations (CMYK + Light CM/CMK, CMYK + extended gamut inks). Labels updated to match targen's own output.
- **Create Chart — Add/Remove Colorant (-D)**: New expert option that lets you add or remove a single ink colorant from the base Device Type combination. Supports all 20 colorants known to targen (Cyan, Magenta, Yellow, Black, Orange, Red, Green, Blue, Violet, White, and their light/medium variants).
- **Settings dialog**: Focus border on path input fields is now a neutral grey (#f4f4f4) instead of the global cyan accent colour.

## v2.0.7
### Improved
- **Measure tab — Calibration Complete dialog**: Restructured with a visual key-binding table (Menlo, accent colour) for the navigation keys, separate prose and footnote sections. OK button is now tinted in the tab's green accent colour.
- **Measure tab**: All other tabs are disabled and visually dimmed while a measurement is running, preventing accidental tab switches mid-scan.
- **Build Profile tab**: Progress bar is now always visible — dimmed and static when idle, animated during a build.
- **Build Profile tab**: All other tabs are disabled and visually dimmed while colprof is running.
- **Build Profile tab — Profile Built dialog**: "Install on this Mac" and "Check Profile Quality" buttons are now tinted in the tab's cyan accent colour.
- **Spinboxes**: The focus border now runs continuously around the entire widget — the up/down buttons no longer interrupt it.
### Fixed
- ARM and universal2 app bundles are now reliably ad-hoc signed: all `.so` and `.dylib` files inside the bundle are signed individually before the top-level bundle sign, preventing Gatekeeper rejections on Apple Silicon.

## v2.0.6
### Improved
- Tab workflow headers: step label increased to 12 pt and headline increased to 30 pt for better legibility.

## v2.0.5
### Improved
- All button labels across every tab, dialog, and the Settings window now use Menlo font in all-caps, applied globally via a Qt event filter — future buttons inherit the style automatically.
- Empty TIFF preview placeholder text uses the same Menlo all-caps treatment.
- Status bar messages (ArgyllCMS warnings, update notifications) moved from the main-window status bar into the bottom of the left control panel on tabs 1–3, so the splitter divider now reaches the full window height.
- TIFF preview navigation buttons (‹ Prev / Next ›) now have 12 px of symmetric padding on all four sides.
- Left control panels are now fixed-width and non-resizable: Create Chart locks at 700 px, Print Chart and Measure both lock at 580 px.

## v2.0.4
### Improved
- Accent-coloured gradient wash at the top of each tab's control panel fades with a quadratic ease-out curve for a smoother, more natural look.
- A 2 px vertical accent line in the active tab's colour now runs along the full left edge of the window, below the tab bar.
- Active tab button background tint reduced to 6 % opacity for a subtler highlight.
- **Create Chart — Calculated Patches** section redesigned: patch count displayed in large Georgia 56 pt with letter-spacing 85 %, subtitle and paper info in small Menlo caps, and a five-segment spectrum bar underneath.
- Preview panel labels (CHART PREVIEW, PRINT PREVIEW) now use Menlo 9 pt grey all-caps.
- Calculated Patches group-box internal padding adjusted so top and bottom spacing are visually balanced.

## v2.0.3
### Improved
- Each tab now shows a workflow header at the top of its controls panel: a small coloured accent stroke followed by a step indicator (Menlo, all-caps, grey) and a large headline (Georgia 24 pt, white) — matching the tab's accent colour.
- Minimum window size increased slightly (1440 × 1025 px).

## v2.0.2
### Fixed
- arm64 DMG is now properly ad-hoc signed — the app opens on macOS 13+ via right-click → Open without Gatekeeper blocking it.
- Build is now automated via GitHub Actions (arm64 + universal2 in a single workflow).

## v2.0.1
### Fixed
- Settings lockdown during Build Profile — all settings widgets are disabled while colprof runs, preventing accidental changes mid-build.
- Guided panel section margins are now uniform across all five sections in the Create Chart tab.

## v2.0.0
### Added
- Complete UI redesign with the Spectrum design language: custom gradient masthead, per-tab accent colors, animated segment progress bar, and a new font stack (Inter, Instrument Serif, JetBrains Mono).
- Settings button embedded in the header.
- Colored folder and refresh icons on all file dialog buttons (HiDPI-aware).
- Start Measurement button is disabled until a .ti2 file is loaded.
- Analyse button in Check & Refine is disabled until both required files are loaded.
- Dialog primary buttons are tinted to match the active tab's color scheme.
- New monogram app icon.

## v1.7.1
### Fixed
- **Measure tab layout** — the empty space now appears between the Target File section and the action buttons, keeping the buttons and log output together at the bottom of the panel.

## v1.7.0
### Added
- **Spectral filter type option in Measure tab** — a new `-F` option in Additional Options lets you override the filter/illuminant condition used by the instrument: None (M0), D50 (M1), D65, UV Cut (M2), or Polarizing (M3). Disabled by default; D50 (M1) is pre-selected for when you need it.
### Improved
- **Measure tab layout** — the "Measurement Instrument" and "Target File (.ti2)" sections no longer stretch to fill the left panel height. They now sit at their natural content size, with the log output anchored to the bottom of the panel.
- **Additional Options input sizing** — combo boxes and spin boxes in Additional Options are now the same compact height as plain checkbox rows, giving the section a uniform appearance.

## v1.6.1
### Improved
- **AirPrint driver warning in Print tab** — when no configurable options are
  detected for the selected printer, the Print tab now shows an informative
  message explaining that macOS often installs AirPrint or Driverless drivers
  automatically, how to identify them in System Settings → Printers & Scanners,
  and how to reinstall the printer with the manufacturer's native PPD driver.

## v1.6.0
### Added
- **Manual mode presets** — the Create Chart tab's Manual mode now has a Presets section between the Output and parameter groups. Use the + button to save the current parameter values under a custom name, select a preset from the list to restore it instantly, and use the − button to delete it. Presets survive a factory settings reset.

## v1.5.2
### Fixed
- **Print tab button labels no longer clipped** — buttons in the Print tab are now taller and their labels are split across two lines so text fits correctly at all window sizes.
- **Save as Defaults button alignment** — on the Chart, Measure, Profile, and Check & Refine tabs, the "Save as Defaults" button was rendering at a different height than its neighbours. It now matches the row height exactly.

## v1.5.1
### Fixed
- **Update checker SSL error** — the "Check for Updates" feature failed with a certificate verification error inside the app bundle. Fixed by bundling certifi's CA certificates with the app.

## v1.5.0
### Added
- **Install Profile button in quality check dialog** — after running a quality check the result popup now offers a button to install the profile directly. The button label reflects the quality grade: "Install Profile" (Excellent), "Install Profile As Is" (Good / Acceptable), or "Install Profile Anyway" (Needs Work).
- **Update checker** — a "Check for Updates" button in Settings checks the GitHub releases page and shows the result inline. The app also performs a silent background check 3 seconds after launch and shows a status bar notice when a newer version is available.
### Improved
- **Quality report file numbering** — report files now always start at `_1_` (e.g. `Quality_Check_1_<stem>.txt`) so multiple reports sort correctly in any file browser.
- **Gamut source file browser** — the Browse button for the gamut source profile in Build Profile now opens directly in ArgyllCMS's `ref/` folder where the standard reference ICC profiles live.
- **Margin parameter simplified** — the duplicate "TIFF File Margin" (`-M`) expert option is removed from Create Chart. The page margin and TIFF margin are always kept in sync; a single "Margin (mm)" control handles both.
- **Sort disabled in summary mode** — in Check & Refine, "Sort by ΔE" is automatically unchecked and greyed out when verbosity is set to "Summary only", since sorting has no effect without per-patch output.
- **Settings credits** — the Settings dialog now credits ArgyllCMS author Graeme Gill and Knut Georg Larsson.

## v1.4.0
### Added
- **Clear Print Queue button** — cancels all pending and stuck jobs for the selected printer directly from the Print tab, without needing to open a system tool.
- **Stuck-job pre-print check** — before sending a job, ChromIQ detects held, stopped, or aborted jobs in the CUPS queue and offers to clear them first ("Clear & Print / Print Anyway / Cancel").
- **Printer reachability check** — a clear error dialog is shown if the selected printer is offline before a job is submitted.
### Improved
- **Print option combos unlock sequentially** — each option only becomes active once the preceding one is set, and incompatible quality values are filtered automatically based on the selected media type (Epson EPIJ exact rules, PPD UIConstraints, or general keyword heuristics for other drivers).
- **Color management is now always disabled automatically** — no manual option selection required; the correct CUPS flags are injected into every print job.
- **Multi-page TIFF handling** — "Print Current Page" and "Print All Pages" now correctly extract and send individual frames from multi-page TIFF files.
- **Printer detection** now uses the pycups API directly instead of parsing `lpstat` output, giving more reliable results across locales.
- **Drying time guidance** updated to reflect professional recommendations (at least 1 h; 24 h for best accuracy).
- **New app icon.**

## v1.3.1
### Improved
- **Check & Refine start-over logic** now uses OR logic: starting over is recommended when more than 50% of individual patches exceed the ΔE threshold, *or* when more than 75% of strips are flagged. This prevents false "start over" recommendations on small charts where a few outlier patches flag most strips, while still correctly catching large charts where nearly every strip needs re-measuring.
- **Settings dialog** now shows author credit at the bottom.

## v1.3.0
### Added
- **Build progress feedback** — the Build Profile button now shows "Building Profile…" while colprof runs, and a thin progress bar appears below it so it is clear the app is working. A result dialog appears on completion offering to install the profile, go to Check & Refine, or dismiss.
### Improved
- **Gamut Mapping defaults** — the gamut source is now enabled by default (Perceptual + Saturation, sRGB from the ArgyllCMS ref folder). Previously both options were disabled, leaving colprof to use an internal default that is not optimised for any real working colour space. The two separate `-s`/`-S` checkboxes are replaced by a single selector, preventing conflicting settings.
- **Gamut Mapping tooltips** rewritten to explain practical outcomes ("colours outside your printer's range are compressed to fit…") rather than raw CLI flag descriptions.
- **Measure tab** — the tooltip for "Refine existing measurement" is now hidden when the option itself is hidden, reducing clutter when no `.ti3` file is present.
### Fixed
- The `-s` (perceptual-only gamut source) path and enabled state were not saved to settings; the option had no effect after restarting the app.

## v1.2.0
### Added
- **Smart ti2 loading** in Print and Measure tabs: when a `.ti2` file is loaded from outside the working folder, a copy dialog guides the user to name and import the chart files. When the file is already in the working folder, the user can choose to continue printing as-is or use it as the base for a new profile.
### Improved
- **Profile quality grading** now accounts for peak ΔE as well as average ΔE. A profile with an excellent average but high-error outlier patches is now graded accordingly, and the explanation tells the user which metric is limiting the grade.
- **Guided refinement** recommendation logic is now patch-based: the "start over" recommendation is only triggered when more than 50 % of individual patches exceed the threshold, not when 50 % of strips are flagged. This avoids false "start over" recommendations on small charts with a handful of outlier patches.
- Log file moved to `~/Library/Logs/ChromIQ/chromiq.log` (standard macOS location). The app no longer creates a `ChromIQ` folder in the user's home directory on launch.
### Fixed
- Per-patch profcheck results were sometimes lost due to a QProcess output-buffer race condition. The fix ensures all output is drained before the process finish callback runs.
- The profile quality assessment popup was not shown when `profcheck` exited with a non-zero code (its normal exit behaviour when errors are found).
- An unhandled exception in the quality report file-write no longer silently prevents the assessment dialog from appearing.

## v1.1.6
### Fixed
- A3 Portrait is now hidden in guided mode when i1Pro / i1Pro 2 / i1Pro 3 is selected, matching the existing behaviour for i1Pro 3 Plus. A3 Landscape is shown and selected automatically instead.

## v1.1.5
### Fixed
- i1Pro 3 Plus patch capacity was incorrectly assumed identical to the regular i1Pro. All paper sizes have now been measured with `-i3p` and the database updated (e.g. A4: 504 → 108, A3: 735 → 153). Charts for this instrument will now correctly fill the page.
- A3 Portrait is hidden in guided mode when i1Pro 3 Plus is selected — it yields only 153 patches vs 225 on A3 Landscape, so the landscape variant is offered and selected automatically.
### Improved
- Guided mode now adds grey-axis patches (`-g`) scaled to total patch count: `max(8, total // 30)`, capped at 64. Previously grey patches were always disabled.
- White and black patches (`-e`, `-B`) in guided mode now scale with page count: base + (pages − 1) × 2 per type.

## v1.1.3
### Fixed
- Tooltip (ⓘ) and settings (⚙) icons now render crisp on Retina / HiDPI displays instead of appearing blurry.

## v1.1.2
### Improved
- The universal DMG now runs **natively on both Apple Silicon and Intel Macs** (universal2 fat binary). Previously it was arm64 only and required Rosetta on Intel machines.

## v1.1.1
### Improved
- macOS title bar now matches the dark app theme.
- Check & Refine: re-measurement threshold is now user-editable.
- Check & Refine: the resume option is hidden when no matching `.ti3` file exists.
- Tooltip buttons remain clickable even when their parent panel is collapsed.
### Fixed
- Button heights and vertical alignment corrected throughout the UI.

## v1.1.0
### Added
- **Check & Refine tab** — run `profcheck` on a finished profile, see per-patch ΔE results, and selectively re-measure only the worst patches with guided strip-by-strip instructions.
### Improved
- File open dialogs now show only relevant file types and include sidebar shortcuts for quick navigation.

## v1.0.3
### Fixed
- Pink / magenta screen artifact on Apple Silicon during measurement (disabled native file dialogs).
- App now auto-detects ArgyllCMS on launch and shows a clear setup guide if it is not found.
- Wrong-strip dialog now appears when chartread detects a mismatch during measurement.
- Unexpected colour-response warning dialog added (high ΔE on a known patch).
- "No instrument detected" dialog shown at measurement start instead of silent failure.
### Added
- Resume measurement flag (`-r`) exposed in measurement options.

## v1.0.2
### Added
- Calibration prompt dialog when chartread asks to position the instrument.
- Navigation instructions popup shown after instrument calibration completes.
- Completion dialog when all stripes have been successfully measured.
- Retry dialog on strip read failure.
### Improved
- Measurement settings are disabled while chartread is running to prevent accidental changes.

## v1.0.1
### Added
- Initial public release as a distributable DMG.
- Resolved macOS App Translocation crash (app must be run from /Applications).
- PyQt6 compatibility fix for macOS 15 Sequoia.
