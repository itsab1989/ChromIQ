# Charts that aim at a reference condition, and the CMYK to RGB question

**Status: ANALYSIS, awaiting a ruling. Nothing here is built and nothing here is
confirmed behaviour.** It answers the two questions asked on 2026-09-12 in
issue #182, and it records the measurements so nobody has to make them again.

Everything below was measured on 2026-09-12 from commit `73f9ab85`. The raw
output, the scripts and the on-screen artefacts are in the proof folder for that
date. No ISO tolerance value and no reference data value appears in this file:
only aggregate results, and where a licence-clean stand-in was needed the aims
came from Argyll's public-domain `cmyk.icm` and are labelled as such.

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
