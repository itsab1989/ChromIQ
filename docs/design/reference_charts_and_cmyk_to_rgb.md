# Charts that aim at a reference condition, and the CMYK to RGB question

**Status: CLOSED FOR THIS RELEASE (Knut, 2026-09-24, [5817809396](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817809396), A16 of
5802027116: "the recommended is accepted").** Nothing here is built and nothing
here is confirmed behaviour; it may be reopened after the release if charts
built towards a reference condition are wanted. ~~ANALYSIS, awaiting a
ruling.~~ Sections 1 to 6 answer the two questions asked on
2026-09-12 in issue #182. Sections 7 to 12 answer the two asked on 2026-09-13,
about an iterative RGB search and about where a profiling patch set comes from.
It records the measurements so nobody has to make them again.

Sections 1 to 6 were measured on 2026-09-12 from commit `73f9ab85`. Sections 7
to 12 were measured on 2026-09-13 from commit `e66dde29`. The raw output, the
scripts and the artefacts are in the proof folder for each date. No ISO
tolerance value and no reference data value appears in this file: only aggregate
results, and where a licence-clean stand-in was needed the aims came from
Argyll's public-domain `cmyk.icm` and are labelled as such.

Two profiles carry most of the numbers, both real measurements of the same Canon
Pro-300 on two papers: one on Canon Semi-Gloss read with an i1Pro, one on Epson
Premium Semi-Gloss read with an i1Studio. They are developer test data. They are
used to compare two real gamuts, not as a certified reference.

---

## 1. The first question: "Is this not true?"

No, and the part that is wrong is worth being exact about, because the part that
is right is the more important of the two and it survives.

### 1.1 A CMYK value is not a point in a cube. It is a point in a four-dimensional solid, and every colour in it is a whole line

A cube has three axes. CMYK has four numbers, and colour has three. That
difference is not a technicality; it is the entire subject of black generation,
and it is why every tool that goes from a colour to CMYK makes you choose a
policy before it will answer.

Measured, on Argyll's public-domain "Chemical proof" CMYK profile: 96 aim
colours were asked for twice, once with zero-black generation and once with
maximum-black generation.

| | result |
|---|---|
| the K value the two answers use differs by | mean 23.0 points, max 91.2 points |
| the total ink they lay down differs by | mean 25.0 points, max 166.6 points |
| the colour the two actually produce differs by | **0.00 dE00, on all 96** |

Two CMYK quadruples as different as it is possible to be, printing the same
colour exactly. That is the fourth dimension, and an RGB triple has nowhere to
put it. So there is no "the point in the CMYK cube" to check an RGB candidate
against: for every colour there is a continuous family of CMYK values, and they
are all equally correct.

The same thing shows up inside the reference file itself, which is a grid
carefully built to avoid duplicates. Of its 1,617 patches, **84 pairs of
different CMYK quadruples measure as the same colour** within 1.0 dE00 (37 pairs
within 0.5), and inside such a pair one channel can differ by 60 points.

### 1.2 The observation that started this is real, but it runs the other way

The formula never produced several RGB values for one CMYK. It cannot: it is a
function, one input, one output. What it does is the opposite, and that is the
damaging half.

Measured on the 1,617-patch grid with `R = 255(1-C)(1-K)`:

| | result |
|---|---|
| patches that end up with no RGB value of their own | **122 of 1,617 (7.5 %)** |
| collision groups | 82, the largest holding 39 patches |
| inside a group, how far apart the file's own **measured** colours are | mean 3.21, median 2.26, **max 22.38 dE00** |
| groups whose internal spread is more than 2.5 dE00 | 37 of 82 |

With the additive variant, `R = 255(1-(C+K))`, it is far worse: 464 patches
collapse (28.7 %), one group holds 106 patches, and the spread inside a group
reaches 45.48 dE00.

So there is nothing to discard. The formula does not hand you spare candidates
one of which is right. It hands you one answer for a set of patches that are
genuinely, measurably different colours, and the information needed to tell them
apart has already been destroyed. A filter cannot recover it and no refinement of
the formula can either, because the loss is in the arithmetic's shape, not in its
coefficients.

### 1.3 "Ink amounts" is not the same quantity on the two sides

C = 100 means a full layer of one particular cyan ink on one particular paper,
measured. R = 0 does not name an ink at all. It is a request to a driver that
chooses its own recipe, on its own inks, with its own black generation and its
own ink limit. There is no red ink in the machine. The two numbers are not the
same kind of thing, so there is no shared "ink-amount cube" for them to be
points in.

This is measurable, and it is the cleanest disproof of the idea, because it does
not even need CMYK. Take 1,617 aim colours and ask **two profiles of the same
printer, differing only in the paper**, what RGB produces each one:

| | result |
|---|---|
| aims where the two profiles want the same RGB | **0 of 1,617** |
| aims where they agree within one level of 255 on every channel | **0** |
| worst single channel difference | mean 37.6, median 36.2, **max 101.7 of 255** |
| distance between the two RGB answers | mean 46.5, 95th percentile 89.4 |
| colour cost of printing the other profile's RGB | mean 10.54, 95th percentile 22.23, max 34.54 dE00 |

Same printer. Same inks. Same aim colours. Different paper, and not one patch
agrees. The RGB that corresponds to a colour is a property of the machine and
the paper, not of the colour, and certainly not of a CMYK quadruple that
describes somebody else's press. A universal formula cannot be refined into
existence because there is no single answer for it to converge on.

### 1.4 And the figure from 5 September reproduces exactly

Measured again from scratch, through ChromIQ's own colour code, against the
1,617 measured Lab values:

| formula | avg | median | max | inside 2.5 dE00 |
|---|---:|---:|---:|---:|
| `R = 255(1-C)(1-K)` | **12.10** | 10.81 | 39.09 | **7 of 1,617** |
| `R = 255(1-(C+K))` | 13.87 | 13.01 | 39.09 | 6 of 1,617 |

The paper patch alone, with no ink and no printer involved, is **6.31 dE00** out.
Adding targen's 1 % flare, which is the most favourable reading available,
improves the first line only to 11.35. The number stands.

---

## 2. The second premise, which is correct and is the useful one

> *"the measured chart for a verification must have patches that have the same
> expected lab values as the reference files lab values, else the measurement
> will not be within the limits."*

**Yes. That is right**, and it is the right reason to be asking any of this. If a
report judges patch against patch, the patches have to aim at the same colours,
or the number it prints is the distance between two different intentions rather
than an error.

The conclusion does not need the device column, though, and that is the whole
resolution. What a chart needs is a Lab aim per patch (which is the reference's
own measured column, used exactly as it stands) and a device value that makes
**your** printer produce that Lab (which comes from your own profile). The
reference's CMYK column is never read. The step everyone has been trying to
build does not need to exist.

On the aside about the XYZ column: yes, a `.ti1` carries one, and on this route
it comes out right by construction, because the aim Lab is what the chart's
stored colorimetric reference records. There is no second conversion to get
wrong.

---

## 3. The choices, honestly costed

### Option A. Convert the reference's CMYK to RGB by formula

Measured error 12.10 dE00 average, 7 patches of 1,617 inside 2.5, the paper
6.31 out before printing. **Not viable at any tolerance anyone would set.**
Section 1 says why it cannot be repaired.

### Option B. Invert the user's own profile at every reference aim

Push each aim Lab backward through the profile under test to get RGB, print
that, measure it, compare against the aim. Measured, assuming the printer prints
exactly what its profile predicts:

| profile | avg | 95th | max |
|---|---:|---:|---:|
| Canon Semi-Gloss, all 1,617 aims, absolute | 0.40 | 1.66 | 4.59 |
| Epson Premium SG, all 1,617 aims, absolute | 1.04 | 4.37 | 8.08 |

That is a thirty-fold improvement on option A on the better profile. The error
left is almost all gamut clipping, which section 4 is about. The inversion
itself is not the limit: measured on colours certainly inside the gamut, the
round trip costs **0.35 dE00 mean** on the better profile and 0.73 on the weaker
one, and the profiles' own fit residuals are 0.235 and 0.363 average. So a
realistic floor for a printed in-gamut patch on the better machine is somewhere
under 1 dE00 before any print variation.

### Option C. Restrict the chart to the aims the printer can reach

Option B, minus the patches the printer physically cannot print:

| profile | kept | avg | 95th | max | dropped patches would have read |
|---|---:|---:|---:|---:|---|
| Canon Semi-Gloss, absolute | 94.1 % | **0.28** | 0.95 | **1.47** | avg 2.30, max 4.59 |
| Epson Premium SG, absolute | 83.7 % | **0.50** | 1.18 | **1.50** | avg 3.82, max 8.08 |

Every patch in the chart is then one the printer had a fair chance at, and the
worst patch in the report is under 1.5 dE00 rather than over 8. The patches that
left are not hidden: they are reported as unreachable, with how far out they are,
which is a real and interesting result about the printer.

**This is the recommendation.**

### Option D. Build the chart from the reference's own device values

Correct, exact, and unavailable: an RGB printer has no CMYK input. This becomes
live only if the CMYK report path (question S5) ships, and then it is the right
answer for CMYK devices and irrelevant for RGB ones.

### Option E. Do not match patches at all

Two things worth having that need no matching chart, and neither is a
verification:

* **Reachability.** Ask whether this printer on this paper can reach a named
  condition at all, before anybody prints anything. ChromIQ computes this today
  (`workflow/gamut_target.py::flags_in_gamut`), and it is arguably the single
  most useful thing a user could be told about a reference set.
* **A prediction.** Push the reference's aims through the profile and report the
  predicted error with no sheet printed. That measures the profile, not the
  print, and must be labelled as such.

---

## 4. The gamut, which decides whether any of this is sound

This is the part nobody has measured until now, and it changes the answer.

Coverage of the full 1,617-patch condition, through ChromIQ's own shipped
reachability test and its own thresholds:

| profile | absolute, safe | absolute, full | media-relative, safe | media-relative, full |
|---|---:|---:|---:|---:|
| Canon Semi-Gloss | 90.3 % | 97.2 % | 94.4 % | 99.2 % |
| Epson Premium SG | **70.6 %** | 85.3 % | 76.7 % | 90.1 % |

And of the eleven reference sets ChromIQ already ships, which are 72-patch media
wedges and therefore deliberately loaded with the hardest colours:

| | in gamut | clipping error avg | 95th | max |
|---|---:|---:|---:|---:|
| Canon Semi-Gloss | 679 of 792 (**85.7 %**) | 0.49 | 1.91 | 4.40 |
| Epson Premium SG | 565 of 792 (**71.3 %**) | 1.04 | 3.74 | 8.43 |

Per set it ranges from 100 % down to 55.6 %. So between roughly one patch in
seven and one patch in three simply cannot be printed, and a patch that cannot be
printed lands on the gamut surface and reads its distance from the aim: on the
weaker paper the unreachable patches average 3.82 dE00 and reach 8.43.

### And the substrate, which no chart design can touch

Every set's first row compares the reference's paper against the paper in the
printer. Measured, both printers against all eleven bundled sets:

* only **3 of 11** sets have a paper within 3.0 dE00 of either printer's paper;
* the closest is 1.39, the furthest **9.52**.

No patch set, no formula, no profile inversion and no rendering intent changes
that number. It is a property of two pieces of paper.

### What this means, plainly

A whole-set pass or fail against a published printing condition **cannot be
achieved on either of these printers, and probably not on any inkjet on a paper
that is not the condition's paper.** Not because the printer is bad, but because
it is a different process, different colorants and a different substrate. Any
design that promises a user a green verdict against a named condition is
promising something the physics will not deliver, and the user will conclude
their printer is broken.

What can be delivered, and is worth a great deal:

1. **coverage first**, stated before a chart is built: this printer can reach
   N of M colours of this condition;
2. **the reachable patches judged** against the aims, where the honest floor is
   about 0.3 to 0.5 dE00 average and 1.5 maximum, which is a real and useful
   accuracy statement;
3. **the unreachable patches reported separately** with their distance, never
   folded into an average;
4. **the substrate reported on its own**, as a property of the papers;
5. **the verdict word ChromIQ's own**, over ChromIQ's own limits, never carrying
   the standard's or the rights holder's name.

That is already the shape `workflow/reference_sets.py` argues for in its own
docstring, and its `can_fill` already enforces the cross-space half of it: driven
on screen today, it allows the substrate row on an RGB chart and refuses both
solids rows as cross-space.

---

## 5. What it would cost, and what already exists

Most of it is built. The gap is one wire and the report's presentation.

| piece | where it is | state |
|---|---|---|
| the aims of a named condition | `workflow/reference_sets.py::read_aims` | done, eleven sets bundled with their credits |
| whether a colour is reachable | `workflow/gamut_target.py::flags_in_gamut` | done, and used for the report's split statistics already |
| Lab to device, then device to Lab, at scale | `workflow/xicclu_runner.py` | done |
| pick reachable colours and build the chart | `workflow/gamut_target.py::select_gamut_targets`, `write_gamut_ti1` | done, and it already accepts a `master_path` |
| store the colorimetric reference beside the chart | `gamut_target.reference_rows`, `workflow/verification_print.py` | done |
| the report reading that reference as its yardstick | `workflow/measurement_report.py`, the `STATE_CONVERTED` path | done |
| **feeding a reference set in as the master list** | nothing | the wire |

The wire is small: `load_master_labs` reads XYZ out of a `.ti1`, so a reference
set (which carries Lab) needs a sibling entry point, and the neutral-budget and
nesting logic has to be skipped because a reference set has its own order and
none of targen's header keywords (it already degrades to a plain prefix when
those keywords are absent, so this part may be free). Call it a day.

The larger half is not code. It is the report saying the five things in section
4 in a way a user reads correctly, and the chooser telling them the coverage
figure before they print a sheet. That work overlaps the limits table already in
flight and should be designed with it rather than after it.

---

## 6. What is being asked for

1. Is the recommendation the right one: build the chart by inverting the user's
   own profile at the reference's own Lab aims, restricted to the patches the
   printer can reach?
2. Is the five-part reporting shape in section 4 acceptable, in particular that
   there is **no whole-set pass or fail** against a named condition, only a
   judged reachable subset, a separate unreachable list, a separate substrate
   line, and a coverage figure?
3. Should coverage be offered on its own, before any chart is built, as a plain
   answer to "can my printer do this condition at all"? It costs almost nothing
   and it may be the most useful single number here.

---

# Part two, 2026-09-13: the iterative search, and where a patch set comes from

Measured from commit `e66dde29`. The screen on the measuring machine was
**locked** for the whole session (`CGSSessionScreenIsLocked` was true), so
`scripts/onscreen_capture.py` correctly refused to photograph a window and no
screenshot exists for this part. The app's own shipped functions were driven
instead, with `CHROMIQ_SETTINGS_FILE` and `CHROMIQ_PRESETS_DIR` sandboxed;
`custom_output_path` was empty before and after, and nothing under the user's
working folder was written.

Two profiles carry the printer numbers, the same two as part one: one real
measurement of a Canon Pro-300 on Canon Semi-Gloss, one on Epson Premium
Semi-Gloss. Three more profiles were built for this part with `colprof -qh` from
three real printing conditions' own characterisation data, so that "a profile
built under that printing condition" could be tested rather than imagined. They
are called press A, press B and press C below. Their `.ti3` inputs were
intermediates and were deleted.

---

## 7. The first question: search RGB values until the expected Lab matches

> *"alter RGB values and calculate expected lab value ... Is this a doable
> method? ... The method is independent of a printer profile perhaps?"*

### 7.1 It is doable, and it works

It was implemented and run: a damped Gauss-Newton search over RGB, one residual
per patch in Lab, the whole 1,617-patch condition solved at once so that each
iteration is one batch evaluation rather than 1,617 separate ones. Started from
mid-grey, against the user's own profile, tolerance 0.1 dE00:

| | result |
|---|---:|
| patches brought inside 0.1 dE00 | **1,559 of 1,617 (96.4 %)** |
| residual to the aim, mean | **0.055 dE00** |
| residual on the patches the printer can reach | 0.0014 dE00 |
| cost | 40 iterations, 161 batch evaluations, 10.0 s |

So the answer to "is this doable" is yes, and it is accurate. The 58 patches it
cannot reach are outside the printer's gamut; no method reaches those.

### 7.2 But the whole method already ships inside ArgyllCMS

A search that repeatedly asks a profile "what would this RGB print as" and
steps towards the aim is a **numerical inverse of the profile's forward table**.
That is not a new idea and it does not need writing: `xicclu -fif` is exactly
it, and it is already installed. The comparison, same aims, same profile:

| method | mean | median | 95th | max | inside 0.1 | calls | seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| `xicclu -fb`, the baked B2A table | 0.345 | 0.204 | 1.152 | 4.163 | 293 | 2 | **0.07** |
| `xicclu -fif`, the numerical inverse | **0.059** | 0.000 | 0.000 | 4.082 | 1,560 | 2 | **0.17** |
| the search, cold start | **0.055** | 0.000 | 0.000 | 4.097 | 1,559 | 161 | 9.60 |
| the inversion, then the search | 0.054 | 0.000 | 0.000 | 4.082 | 1,559 | 163 | 9.68 |

On the 1,567 patches the printer can actually reach, `-fif` averages 0.0015
dE00 and the search 0.0014. They are the same answer. The search costs **56
times more wall time** to produce it.

On the weaker profile the picture is the same: `-fb` 0.883 mean, `-fif` 0.435,
the search 0.454.

**Pros of the search, honestly:** it is six times more accurate than the baked
backward table, it needs no B2A tag in the profile, the stopping rule is stated
in the unit anybody cares about (dE00, not device units), and it reports per
patch whether it got there. **Cons:** every one of those pros is also true of
`-fif`, which is two lines of code away and 56 times faster, and a hand-written
search adds a convergence failure mode that nobody has to own otherwise.

### 7.3 And this found a real fault in what ChromIQ does today

`workflow/gamut_target.py` calls `backward_device` with no ink limit, and
`workflow/xicclu_runner.py` only switches to `-fif` when an ink limit is given.
So every verification chart ChromIQ builds today takes the **baked table**, the
worst row of that comparison. Driven through the app's own
`reference_sets.read_aims` and its own eleven bundled sets, 792 patches, Canon
Semi-Gloss:

| | mean | max | inside 0.5 dE00 |
|---|---:|---:|---:|
| `-fb`, what ships today | 0.366 | 3.830 | 659 of 792 (83.2 %) |
| `-fif` | **0.052** | 3.405 | **770 of 792 (97.2 %)** |

A seven-fold improvement in the average, for one flag and a tenth of a second.
Checked that this is the numerical inverse and not the ink limit that reaches
it: a direct `xicclu -fif` with **no** `-l` flag at all reproduces 0.0589
exactly, as do non-binding limits of 300, 400 and 1000.

This is the one place where the question has already paid for itself. It is a
change to propose, not one to make unasked.

### 7.4 The clause that matters: is it independent of a printer profile?

**No. It cannot be, and this is the heart of it.**

Step 1 of the proposal says "calculate expected lab value". Something has to do
that calculating. An RGB triple is not a colour; it is an instruction to a
machine. To know what colour it will become, you need a description of the
machine and the paper, and a description of a machine and a paper measured into
a table **is** a profile, whatever it is called. The search does not remove the
profile. It only moves it from an explicit inversion into the inner loop, where
it is easier to forget it is there.

There is exactly one way to run the search without the user's profile, which is
to substitute a generic assumption. That was measured. The search was run to
convergence against sRGB, and then the two real printers were asked what those
RGB values actually print as:

| | mean | median | 95th | max |
|---|---:|---:|---:|---:|
| Canon Pro-300 on Canon Semi-Gloss | **7.99** | 6.99 | 19.25 | 33.27 |
| Canon Pro-300 on Epson Premium SG | 4.91 | 4.83 | 8.56 | 13.69 |

Of 1,617 patches, **164 land inside 2.5 dE00 and 48 inside 1.0**. The search
believed it had solved 1,422 of them to within 0.1. It had solved them against
a monitor space that is not in the room.

Two further facts settle it:

* **12.1 % of the condition (195 patches) is not inside sRGB at all**, so the
  search cannot even pretend there; it stops short by 4.69 dE00 on average and
  11.62 at worst.
* **The answer depends on which generic you pick.** The same search run against
  Adobe RGB instead of sRGB chooses different RGB values: on the 1,422 patches
  both solved, the two answers differ by 6.12 levels per channel on average and
  90.6 at worst, and printed on the real printer those two "correct" answers are
  **3.96 dE00 apart on average and 16.95 at worst**. A quantity that changes
  when you change an arbitrary assumption is not a property of the colour.

For scale: the direct CMYK formula measured 12.10 dE00 in part one. The generic
search is 7.99. It is better, and it is still four to eight times outside
anything a verification could use. The generic assumption is the entire error.

---

## 8. Could a generic patch set and chart preset be shipped?

This was the actual request behind question one, so it deserves a plain answer.

**A generic patch set that verifies against a reference condition cannot be
built, and no amount of work will produce one.** The reason is in part one,
section 1.3, and it was re-measured this round: the RGB that produces a given
colour is a property of the printer and the paper, not of the colour. Two
profiles of the *same printer* differing only in paper agreed on **0 of 1,617**
aims. A single shipped list of RGB values is therefore right for at most one
printer on one paper, and shipping it would tell every other user their printer
is broken.

**The nearest achievable thing, and it is worth having, is a generic chart
*preset* rather than a generic patch *set*.** Everything except the RGB numbers
can be fixed, shipped and identical for every user:

* which reference condition is being aimed at, and its Lab aims;
* the patch count, the page size, the instrument, the layout, the randomisation,
  the strip geometry, the file naming;
* the reachability test, its intent and its margin;
* the report's rows, its verdict words and its limits.

Only the device column is computed at generate time, from the user's own
profile, in the tenth of a second `-fif` costs. Two users of the same preset
then print physically different sheets that aim at exactly the same colours,
which is the thing that makes their reports comparable. That is a preset in
every sense a user cares about, and it is the honest version of what was asked
for.

The one genuinely generic artefact that can ship, and should, is the **coverage
figure**: this printer on this paper can reach N of M colours of this condition,
answerable before a sheet is printed. Measured through the app's own
`gamut_target.flags_in_gamut` on the eleven bundled sets, 792 patches:

| | safe margin | full margin |
|---|---:|---:|
| Canon Semi-Gloss, absolute | 85.7 % | 95.6 % |
| Canon Semi-Gloss, media-relative | 94.7 % | 98.2 % |
| Epson Premium SG, absolute | 71.3 % | 83.7 % |
| Epson Premium SG, media-relative | 80.2 % | 92.3 % |

The absolute rows reproduce part one's 679 of 792 and 565 of 792 exactly. Both
intents are correct and they answer different questions, so **whichever number
is shown to a user has to be labelled with its intent**; quoting one as though
it were the other is a nine-point error.

---

## 9. The second question, first half: must the profile match the printing condition?

> *"the profile used to invert lab values ... must have been built from
> measurements on paper and where the chart was printed for the same printing
> conditions. Else one can not invert the lab numbers and get the correct
> values."*

This is half right, and the half that is right matters. It is worth separating
the two halves precisely, because the conclusion drawn from it does not follow.

### 9.1 The half that is right: the device values really do differ

Condition A's own Lab aims were pushed backwards through three real profiles,
its own and two built from other printing conditions, and the resulting CMYK
compared against condition A's own device column:

| | mean | 95th | max |
|---|---:|---:|---:|
| through A's own profile | 12.21 | 42.37 | 85.28 points of 100 |
| through B's profile | 18.25 | 65.54 | 100.00 |
| through C's profile | 17.23 | 60.00 | 100.00 |

So yes: use a different condition's profile and you get very different numbers
out. That is real and it is measured.

### 9.2 The half that is wrong: those numbers are not incorrect

They are the correct answer to a different question, and the question they
answer is the useful one. Each set of device values was printed on the press
its own profile describes, which is the only press that can accept it:

| | mean | 95th | max |
|---|---:|---:|---:|
| A's aims via A's profile, printed on press A | **0.070** | 0.334 | 8.822 dE00 |
| A's aims via B's profile, printed on press B | 5.892 | 19.801 | 33.504 |
| A's aims via C's profile, printed on press C | 6.066 | 21.162 | 31.252 |

Press A reproduces its own condition's aims to 0.070 dE00. Presses B and C fall
short by about 6, and that shortfall is gamut, not arithmetic: those presses
physically cannot make some of condition A's colours. Nothing here is *wrong*.
Each inversion did its job on its own device.

The genuine mistake, the one the rule is worth stating to prevent, is different:
take the device values B's profile produced and send them to press A.

| | mean | 95th | max |
|---|---:|---:|---:|
| A's aims via B's profile, printed on **press A** | 8.714 | 22.643 | 46.706 dE00 |
| A's aims via C's profile, printed on **press A** | 8.320 | 22.222 | 33.892 |

### 9.3 So the rule is real, and it is about the printer, not the reference

Stated correctly: **the profile you invert must describe the device and paper
that will physically print the chart.** The reference's printing condition never
enters, because the reference is only supplying the Lab aims.

On the two real RGB printers, which is the case ChromIQ is actually in:

| | mean | 95th | max |
|---|---:|---:|---:|
| inverted through Canon SG, printed on Canon SG | **0.059** | 0.000 | 4.082 dE00 |
| inverted through Epson PSG, printed on Epson PSG | **0.435** | 4.209 | 8.976 |
| inverted through Epson PSG, printed on Canon SG | 10.643 | 22.467 | 34.945 |
| inverted through Canon SG, printed on Epson PSG | 11.062 | 25.849 | 36.057 |

The rule bites hard, and it bites on printer identity. Using the wrong printer's
profile costs about 11 dE00, which is as bad as the direct CMYK formula.

### 9.4 And one printer profile serves every reference condition

This is what disposes of the worry entirely. If the user's own profile had to
match the reference's condition, a user would need a different profile per
condition and would never have one. They do not:

| the user's profile | condition A aims | condition B aims | condition C aims |
|---|---:|---:|---:|
| Canon Semi-Gloss | 0.059 | **0.000** | 0.005 |
| Epson Premium SG | 0.435 | 0.037 | 0.044 |

One profile, three unrelated printing conditions, and the worst average is 0.435
dE00 with the rest at or near zero. Condition B, whose gamut is small enough to
sit entirely inside the Canon's, is reproduced at **0.000 mean over all 1,617
aims**. There is no per-condition profile to go and find, because the user's own
profile already answers for all of them.

---

## 10. The second question, second half: the common patch set

> *"all the FOGRA reference files with same patch count have the same CMYK
> numbers, but differs in the lab numbers ... we do not have the common patch
> set used in a profiling chart"*

### 10.1 The observation is correct, and it is stronger than stated

Checked across the 100 reference files present on the machine for this work:

| layout the files declare | patches | files | share one device column? |
|---|---:|---:|---|
| ECI2002 | 1,485 | 28 | **yes, all identical** |
| ISO 12642-2 | 1,617 | 22 | **yes**, 21 byte-identical, the 22nd the same 1,588 quadruples reordered |
| MediaWedge3 subset | 72 | 20 | **yes, all identical** |
| IT8.7/3 (ISO 12642:1996) | 928 | 26 | three variants, not one |
| TC9.18, RGB | 918 | 2 | **yes**, identical as a multiset |

On the 1,617-patch family the one apparent exception is not one: its device
column contains exactly the same 1,588 unique quadruples as the others, in a
different row order, with **0 quadruples in one and not the other**. So the
reading is right. One patch set, printed under many conditions, measured each
time.

It holds on the RGB side too, which nobody had checked: the **two RGB reference
conditions on this machine share one 918-patch RGB device set exactly**, 0
triples in one and not the other. That set is structurally a nine-level cube of
729 patches plus 182 more, including 11 extra steps on the neutral axis.

And the layouts nest cleanly:

| | unique device values | relationship |
|---|---:|---|
| IT8.7/3 | 836 | |
| ECI2002 | 1,457 | a strict superset of IT8.7/3 |
| ISO 12642-2 | 1,588 | a strict superset of ECI2002, adding 131 |

The 131 additions are not scattered: 130 of them sit on a single black plane,
and the level ladder the two layouts use is character for character the same.

### 10.2 But the conclusion drawn from it does not follow

The conclusion was that the common patch set is the missing piece. Two separate
measurements say otherwise.

**First, it is not missing.** ArgyllCMS already ships `ref/ECI2002R.ti2`, 1,485
rows, whose device column **is** the ECI2002 patch set exactly, and
`ref/ECI2002.ti2`, the same set at 8-bit quantisation with 54 padding whites.
Both are AGPL, both are on every machine that runs ChromIQ, and neither carries
the licensed measurement: their XYZ column matches the rights holder's measured
values in **0 of 1,485 and 0 of 1,539 rows**. It is a stand-in, exactly as it
should be. On the RGB side, the common 918-patch set is likewise recoverable,
being shared identically by two independent reference files.

**Second, and this is the part that settles it, having the patch set does not
give you a verification.** The proposed workflow was run end to end on the RGB
side, where the common set is genuinely in hand: print those 918 RGB values on
the user's printer, measure them, compare against the reference file's Lab.

| | mean | median | 95th | max | inside 2.5 |
|---|---:|---:|---:|---:|---:|
| Canon Pro-300 on Canon Semi-Gloss | **8.02** | 7.97 | 14.53 | 21.51 | 43 of 918 |
| Canon Pro-300 on Epson Premium SG | 11.92 | 10.36 | 25.52 | 35.11 | 14 of 918 |

Eight dE00, with the patch set, on the better printer. The same thing on the
CMYK side: send the shared 1,617-patch device set to three different printing
conditions and the colours that come out differ from each other by **6.12, 6.56
and 2.16 dE00 on average**, reaching 18.32.

That divergence is not a fault to be engineered away. It is the whole reason the
reference files differ from one another in the first place. A profiling chart's
job is to sample a device evenly; a verification chart's job is to aim at named
colours. The same list of device values cannot do both, because the second job
is defined in colour and the first is defined in ink.

For comparison, on the same aims and the same printers, the route that inverts
the user's own profile:

| | all 1,617 aims | on the reachable patches |
|---|---|---|
| Canon Semi-Gloss | 0.059 mean, 4.082 max | **0.001 mean, 0.434 max** (1,567 patches) |
| Epson Premium SG | 0.435 mean, 8.976 max | **0.003 mean, 0.493 max** (1,460 patches) |

Those reachable-subset figures supersede part one's 0.28 and 1.47, which were
measured through the baked backward table. With the numerical inverse the
floor is far lower than part one reported.

### 10.3 Does the rights holder supply a patch set that is not a reference file?

**No.** Checked by opening every file rather than by reasoning about it. Of the
103 files in the four published archives on this machine, 100 carry a data
table and **every one of the 100 is a reference file**: the device column always
arrives welded to a measured colour column. **Zero** are device values only. The
remaining three are a readme and two files whose data table uses a column layout
the parser did not read.

So the answer to the question as asked is no. But the thing wanted is available
anyway, from two other directions:

1. **The layouts are published standards, not the rights holder's property.**
   The files themselves name them: ISO 12642-2 for the 1,617-patch target
   (IT8.7/4), ISO 12642-1 for the 928 (IT8.7/3), ECI2002 for the 1,485, and the
   72-patch wedge which the rights holder's own readme states is a valid subset
   of ISO 12642-1, ISO 12647-2 and ISO 12642-3. A device-value definition
   carries no measurement and is separable from the licensed part by
   construction.
2. **One of them is already installed.** `ECI2002R.ti2` is the 1,485-patch
   profiling target, under a free licence, sitting in the Argyll folder ChromIQ
   already reads its `.cht` files from.

### 10.4 The best course of action, given all of that

Not to obtain the patch set, because obtaining it changes nothing measurable. If
one is wanted anyway, in descending order of cost:

1. **Nothing.** ChromIQ profiles RGB printers, and a CMYK patch set cannot be
   printed on one. This is the honest answer for the CMYK layouts.
2. For the RGB case, the **918-patch RGB set** is already usable and needs no
   grant, being shared identically by two independent published references. It
   is a fine profiling chart. It is not a verification chart, per the 8.02
   figure above.
3. If a CMYK verification path ever ships (question S5 in part one), the
   reference's **own** device column is the right chart and is already inside
   the file. No separate patch set is needed there either.

---

## 11. What changed in the recommendation

The recommendation from part one stands: build the chart by inverting the
user's own profile at the reference's own Lab aims, restricted to the patches
the printer can reach. This round strengthened it and corrected one figure.

* The inversion should use the **numerical inverse** (`-fif`), not the baked
  backward table. Measured over the app's own eleven bundled sets, that is
  0.366 to 0.052 dE00 average and 83.2 % to 97.2 % of patches inside 0.5 dE00.
  `workflow/xicclu_runner.py` can only reach `-fif` by being handed an ink
  limit, which is meaningless for an RGB profile, so it needs a way to ask for
  the numerical inverse directly. That is the whole change.
* Part one's floor of 0.28 mean and 1.47 max on the reachable patches was
  measured through the baked table. Through the numerical inverse it is
  **0.001 mean and 0.434 max**.
* Coverage figures must carry their intent. 85.7 % and 94.7 % are the same
  printer and the same sets under absolute and media-relative.

---

## 12. What is being asked for, this round

1. Is it agreed that the search is a numerical profile inversion under another
   name, and that the right move is to switch ChromIQ's verification inversion
   from the baked table to `-fif` rather than to write a search?
2. Is the "generic chart preset, per-printer device column" shape of section 8
   the right reading of what was wanted, given that a genuinely generic patch
   set costs 7.99 dE00 and a shipped RGB list agrees with 0 of 1,617 aims on a
   second paper?
3. Is a bare profiling patch set still wanted for its own sake, now that having
   one measures 8.02 dE00 as a verification, and given that the 1,485-patch
   version already ships free with ArgyllCMS?
