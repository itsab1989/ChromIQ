# Drafted tooltips

## Create Chart ▸ FROM PROFILE GAMUT (magenta ⓘ)

### Building a chart from this profile's gamut

This module builds a verification chart out of colours chosen by the profile you have already made, instead of colours chosen by a patch generator.

Why that is worth doing: an ordinary verification chart reprints the very same colours your profiling chart used, so it answers "has anything drifted since I made this profile?" — a genuinely useful question, but not the same as "how accurate is it?". This module answers the second one. It asks the profile which colours it claims it can print, prints exactly those, measures them, and shows you how far the print landed from what the profile promised.

What stays the same: everything below the reference colours. The sheet is laid out by printtarg or by the ChromIQ layout engine exactly as in the Manual module, with every option either of them gives you. This module replaces only the part that chooses the colours.

You need a run that already has a finished profile, and the run type set to Verification. Nothing here can overwrite your profiling chart or your profile.

Default: not selected — Guided and Manual are unchanged.

### How many colours to test

Sets how many reference colours ChromIQ asks the profile to reproduce.

The colours come from a fixed master list — the ChromIQ Verification Set — and are always taken in the same order. That matters more than it sounds: a check of 400 colours is a proper sample of a check of 1 500, so a small check today and a large one next year still describe the same thing, and their numbers can sit in the same trend.

Choosing a number is a trade between confidence and paper. More colours cover the gamut more finely and make the averages steadier; fewer colours cost fewer sheets and much less measuring time. The time cost depends heavily on your instrument — a strip-reading spectrophotometer eats hundreds of patches in minutes, while a single-patch device does not.

Not every colour will be printable. ChromIQ tells you how many of them this profile can actually reach, and how many sheets that comes to, before you print anything.

Default: 1 500 colours.

### How close to the gamut edge to go

Decides whether the test colours may sit right at the limit of what your printer and paper can do, or should keep a little distance from it.

Stay safely inside the printable range — colours are pulled slightly away from the very edge of the gamut. Near that edge even an excellent profile struggles: the ink is at its limit, small changes in the paper or the light make large changes in the measurement, and two prints of the same sheet can disagree with each other. Keeping clear of it gives you numbers that describe the profile rather than the physics, and that repeat when you check again next month.

Use the full printable range — colours go right up to the edge. This shows you the profile's true worst case, including the deep saturated corners where most of the error lives. Expect higher numbers, and expect them to wobble more between prints. Useful when you specifically want to know how the extremes behave.

Whichever you pick is recorded on the report, because comparing a "safely inside" check against a "full range" one would be comparing two different questions.

Default: stay safely inside the printable range.

### Which white the comparison is measured from

Paper is never perfectly white, and this setting decides whether that counts as an error.

The paper's own white (media-relative) — ChromIQ treats your paper's white as white, and measures every colour relative to it. A warm paper is simply the canvas, not a fault. Use this when you want to judge how well the profile does its job on this paper, without the paper's own tint dominating the numbers.

A fixed absolute white (absolute colorimetric) — colours are compared against a fixed laboratory white, so the paper's tint is included in every error. Numbers come out higher, sometimes much higher on a warm or optically brightened paper. Use this when you must match an external absolute reference, or when someone else's figures were produced this way.

Neither is more correct; they answer different questions. Both are always available, and the report always says which one produced its numbers, so nobody has to guess later.

Default: the paper's own white (media-relative).

## Print Chart ▸ how this chart is printed (amber ⓘ)

### Printing this chart somewhere other than ChromIQ

Says how this chart reaches the paper, so the report can record it and so ChromIQ can tell you what the other application has to do.

Print it here — ChromIQ sends the sheet straight to the printer with colour management switched off, which is what a chart needs. This is the reliable route and it stays the default.

I will print it in another application — pick this when you would rather drive the printer from an application you trust. ChromIQ then shows you where the sheet files are and exactly what that application must be set to. It does not try to print anything.

There is one rule, and everything depends on it: **nothing between here and the paper may convert the colours.** A chart is not a photograph. The numbers in the file are already the exact ink amounts to lay down — for a verification chart they are what your profile said would produce the colours being tested. If another application converts them through a profile on the way out, it prints different colours, the measurement describes those different colours, and nothing anywhere can detect that it happened. The report simply reads as though the profile were poor.

So in the other application: no output profile, no "let the printer manage colours", no proofing or simulation, no scaling or fitting to page, and no driver enhancement, auto-tone or vivid mode. The sheet must go out at its own size, unaltered.

This applies just as much to a profiling chart as to a verification chart. A profiling chart printed through a colour conversion produces a profile that is wrong in a way nothing later will reveal.

Default: print it here.

### Why ChromIQ asks instead of working it out

ChromIQ can see whether it printed a chart itself. What it cannot see is whether an application it never spoke to had colour management switched on.

That matters because the two failures look identical on the report. A chart printed through an unwanted colour conversion and a genuinely inaccurate profile both produce large errors in the same places, and no measurement can tell them apart afterwards.

So the report states which route was used, in your words rather than a guess. A run that says "printed outside ChromIQ" carries a short reminder of the settings that route depends on, and a surprising result has somewhere obvious to start. A run that says "printed by ChromIQ" needs no such caveat.

Nothing is blocked either way, and you can change the answer later if you printed it differently than you planned.

Default: filled in for you as "printed by ChromIQ" once ChromIQ has printed the chart.

## Check & Refine ▸ ACCURACY (violet ⓘ)

### Which measurement is being analysed

Picks the measurement the accuracy figures are calculated from.

This verification's measurement — the reading you made on the Measure tab for the date shown. This is the normal choice, and it is already selected for you when the run has one.

Import a measurement made in i1Profiler — for when you laid out and printed the chart in i1Profiler instead of here. Every chart ChromIQ builds already writes an i1Profiler patch set beside it, in the run's exports folder, so that route needs no preparation on your part; this is simply where the finished measurement comes back in. ChromIQ accepts i1Profiler's own .mxf as well as its exported text measurements, and pairs the patches up by their identifiers, so the order they were measured in does not matter.

Whichever you use, the result is filed under this verification date like any other, so both routes end up in the same history.

Default: this verification's measurement.

### What the measurement is compared against

A verification always compares your print against something. This chooses against what.

The reference colours stored with this chart — the colorimetric targets the profile promised when the chart was generated, saved beside it so the same comparison can be repeated years later. This measures accuracy: how close the print is to what the profile said it would be.

The chart's own design colours — the RGB values that were sent to the printer. This measures drift: whether today's print differs from an earlier one. It is available for every verification chart, including charts made before this module existed.

Both readings are worth having, and they can disagree in a way that is informative: a printer that has not drifted at all can still be inaccurate, if the profile was never quite right to begin with.

The option is only offered when the chart has reference colours stored with it. When it has not, the drift comparison is used and the report says so.

Default: the reference colours stored with this chart, when they exist.

### How colour differences are counted

Chooses the formula that turns "these two colours are not the same" into a number — the ΔE (delta E) value you see everywhere in the report.

CIEDE2000 — the modern formula, and the one to use unless you have a reason not to. It is built to follow what the eye actually notices, and it is fairer than the older formulas in the places printing is hardest: deep saturated colours, and near-neutral greys.

CIE94 — an earlier refinement, still met in older documentation.

CIE76 — the original 1976 formula. Simple, but it exaggerates errors in saturated colours and understates them in greys, so a CIE76 number is not comparable with a CIEDE2000 one.

As a rough guide with CIEDE2000: under 1.0 is a difference most people cannot see side by side, under 2.0 is good printing, and above 3.0 is visible when you compare the two directly.

Only pick one of the older formulas if you are comparing against figures that were produced with it. The report always states which formula it used.

Default: CIEDE2000.

### Which colours are called out individually

Sets the error above which a colour is listed by name in the report's worst-patches section, instead of only counting towards the averages.

This changes the report, nothing else. It does not affect the averages, the histogram, or the trend against earlier verifications — those always use every colour that was measured. It only decides how long the "here are the ones that missed" list is.

A lower value (1.0) gives you a long list and is useful when you are hunting for a pattern — a whole region of the gamut behaving badly usually shows up as a cluster. A higher value (3.0) keeps the list to the colours anyone would see were wrong.

Default: ΔE 2.0.
