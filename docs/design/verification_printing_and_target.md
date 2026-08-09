# Verifying a profile: printing it properly, and testing it against its own gamut

> **These specifications are binding.** They must be consulted before changing
> code in the area they cover, and a fault that contradicts one is reported and
> approved before it is implemented — the specification may be the part that
> needs to change.

## ⏳ Awaiting confirmation — DRAFT

**Confirmed by:** *nobody yet.*

Nothing here is agreed. It is a plan to argue with, section by section. No code
has been written for either feature, and no row of any table below has been
implemented.

### Where this stands — 2026-08-09, after v3.14.8-beta.207

**Neither feature has advanced.** Phases A0–A3 and B are untouched, and none of
the decisions in §11 has been made. Everything below is still a draft.

Work *did* happen around this plan, and it is worth being clear that it is not
progress against A or B — it came out of questions asked while writing it:

| | |
|---|---|
| **Shipped** | **beta.206** the patch-identity check (reports, acts on nothing) · **beta.207** disabled radio buttons now look disabled |
| **Confirmed** | ✅ **One thing only**: the disabled-option styling (§3.1b), confirmed by Sebastian on 2026-08-08. Everything else in this file is unconfirmed |
| **Closed by evidence** | i1Profiler preserves patch order (a real 550-patch round trip) · `targen -t` is nested by construction (four size pairs, byte-compared) · the master-set size, from what the industry actually uses · the set recipe, which is a `targen` invocation rather than new code |
| **Corrected** | The set size twice — an invented 1 500, then 1 617 read from **CMYK** press references when ChromIQ is **RGB**. See §11 Q6 |
| **Still open** | All of §11. The load-bearing evidence gap in §12 is unchanged: **nothing about colour-managed printing has been tested on hardware** |
| **Owed when A lands** | The identity verdict prints as its own notice today; it belongs in the report's "how this was produced" block (§3.3, row A20), so the report gives one account of its conditions rather than two |
| **Corrected 2026-08-09** | **`profcheck` is not meaningless for a verification** — Argyll's docs allow *"other test samples from the same device"*, so the existing Check & Refine modules are appropriate, and **B may need no module there at all** (§2b) · **The rendering intent is two questions, not one** — feature A's is chosen on the Print tab, #133's in Create Chart, so they can hold different defaults (§11 Q4) |
| **New question** | §11 **Q5** — the Print Chart tab is **not** one of the storing tabs, so feature A's intent has nowhere to live per target. #133's does, automatically |

### Sections added after the plan was first written

Read these before building — each changes what gets built, and two of them
closed holes in the tables:

| § | What it settles |
|---|---|
| **2a** | The device type is **never chosen** — it is inherited from the run's profiling chart. Also: ChromIQ *can* build CMY+N profiles (the beta engine), and the real obstacle is that it has **three `.ti3` readers** and the narrowest one owns the report |
| **3.1a** | 🔴 A #133 chart is **already converted**, so the Print tab must force Raw and **disable** the other option. A hole in §3.1, which keyed only on run type |
| **3.1b** | The mirror case is **deliberately not symmetric** — raw on a regular chart is a legitimate drift check, not an error. Contains the one **confirmed** decision |

### The quickest way to start: a ready-made kick-off prompt

**`docs/design/START-verification-feature-A.txt`** is a prompt to paste into a
fresh session. It **pre-answers every question in §11** so the session never has
to stop and ask, states what "done" means as a checklist, and names what it must
*not* touch. Edit the DECISIONS block if any answer is wrong — that is what it is
there for.

A copy also sits on the Desktop as
`ChromIQ-START-verification-feature-A.txt`.

### If you would rather start by hand, do this first

1. Read **§0** (plain words) and **§11** (what is undecided).
2. Answer §11 **Q1** and **Q2** — build A? and A+B together? Nothing else is
   blocking, and the recommendation is *yes* and *A first*.
3. Start at **Phase A0** (§5). It is three small changes, none user-visible.
4. Re-run the two checkers before trusting any number in here:
   `scripts/check_issue_133_numbers.py` and
   `scripts/audit_tool_file_placement.py`.
5. **Do not freeze the master colour set.** Ship it marked provisional — see
   §0a's warning above; it is the only irreversible decision in either feature.

---

## 0. In plain words — read this part if you read nothing else

*This section is for someone who owns the app but does not want to become a
colour scientist to decide about it. No jargon; the technical sections start at
§1.*

### What problem are we solving?

You build a profile so your printer produces the colours you ask for. The
obvious follow-up question is **"did it work?"** — and ChromIQ cannot answer it
properly today.

It has a "verification run", but the sheet it prints is not connected to your
profile at all. It prints the chart's raw numbers, measures them, and compares
them against what those numbers would look like on a normal screen. That tells
you whether your *printer* has changed since last month. It cannot tell you
whether your *profile* is any good.

### The two features, and how they differ

**Feature A — print the verification chart through your profile.**
ChromIQ works out, for every patch, the exact ink amounts your profile says will
produce that colour, and prints those. The sheet is your profile's own promise,
made real. Measuring it tells you how close the promise came. **This makes the
verification you already have actually mean something.**

**Feature B — choose the test colours from your profile's own gamut (issue
#133).** Instead of reprinting the same colours as your profiling chart, pick
colours spread across everything your profile claims your printer can do, and
test exactly those. **This makes the check sharper**, and it is the one a
customer might pay for.

A is the foundation. B stands on it. B without A would be measuring against the
wrong reference.

### What will I see?

One new row on the **Print Chart** tab, which only appears when you have a
verification selected, with two choices — print through the profile, or print
raw — and a rendering intent. Everything else stays where it is. §8 has pictures
of every screen it touches.

### What does it cost, and what could go wrong?

**Feature A is small.** Everything it needs already exists in ChromIQ: the tool
that applies a profile to an image (`cctiff`) already ships as
*"Apply a device-link to an image"*, and the raw printing path does not change
at all. Seven small pieces, listed in §5.

**Feature B is larger** — a new panel in Create Chart, and a published list of
test colours that has to be designed, agreed and then never changed again. It
also still has open questions of its own that nobody has answered. It may need
*less* than first thought on the Check & Refine tab: the check that tab already
runs turns out to work for this too, so what is missing there may be wording
rather than a new panel.

**The honest risk in A**: turning it on changes what an existing verification
measures. A project with months of history would show a step change in its
trend, because the question being asked has changed. §10 says how to handle
that, and it is why §11 Q3 asks whether it should be off by default for
projects that already have history.

**The honest risk in B**: the published colour list is a promise. Once people
have reports based on it, it cannot be edited, only extended.

### What do I actually have to decide?

Five things, all in §11. Two of them matter most:

1. **Should A be built at all?** My recommendation is yes, and soon, because
   the verification feature currently in the app does not measure what its own
   messages say it measures.
2. **Should A and B be built together?** My recommendation is **no** — do A
   first. They share the *idea* but almost no code, and B is blocked on
   questions A is not.

If you want to stop after A, that is a complete, coherent product. B is an
addition, not a completion.

### What if I would rather not decide?

Then the default I would choose, and defend, is: **build A, ship it off by
default for existing projects and on for new ones, and leave B parked until
someone is actually paying for it.** That gets the app honest without spending
much, and keeps B's design questions open until there is a reason to answer
them.

---

## 0a. Picking this up in a later session — start here

*Written so this can be resumed cold, months later, by someone who has forgotten
all of it — including the assistant.*

### Nothing here needs a printer until the very last step

This is worth knowing before deciding when to start, because it is the opposite
of what one would assume for a printing feature:

| Step | Printer needed? |
|---|---|
| A0 — correct the §M text, generalise `convert_args`, lift the profile resolver | **no** |
| A1 — the conversion engine, `cctiff` through the profile | **no** — it converts files; a stub runner tests it |
| A2 — the Print-tab row, the record, the report block | **no** — the app runs and the option can be exercised offscreen or on screen |
| B — the master set, the gamut filter, the reference file | **no** — `targen` and `xicclu` are file tools |
| **Final proof** — does a printed sheet actually measure as predicted | **yes**, and only here |

So the whole build can be done and reviewed without hardware. What waits for a
printer is the one thing that would confirm the premise: **one chart printed
both ways, measured, and compared.**

**And that costs two sheets of plain paper — it does not need good stock or a
good profile.** Measured on the existing `printer-test` project (90 patches,
plain paper, a modest profile) by pushing its colours through its own profile
with `xicclu`:

| | mean ΔE00 | max |
|---|---|---|
| Raw print vs the intended colours | 14.15 | 30.87 |
| Through the profile vs the same | 10.89 | 28.88 |

**Separation 3.26 ΔE00 mean; 62 of 90 patches differ by >2 ΔE00, 22 by >5.** An
instrument repeats to ~0.1–0.3 ΔE00, so the signal is 10–30× the noise: if the
two sheets measure alike, the conversion did not happen.

Plain paper *helps* here — its small gamut gives the conversion more to do, so
the routes separate further. What it cannot show is whether the numbers are
*good* (through-the-profile still sits at 10.89 ΔE00 because so much clips), and
that is fine: this test proves the mechanism, not the profile.

Until it is run, §12's evidence rating stays where it is and the feature should
be described as untested end to end.

### The order that keeps it safe

1. **A0 → A1 → A2**, each ending somewhere shippable (§5).
2. **B's engine** — set generation, gamut filter, reference file — which is
   testable entirely offline.
3. **B's UI last**, and **all translations last of all**. The catalogue key is
   the exact English string, so every word changed during review discards that
   string in twelve languages. Wording first, translation once (§7).
4. **The master set ships marked provisional, not frozen** — see below.

### The one thing that must not be got wrong

§5.4 of #133 says a published set is never edited, only extended. That is a real
constraint, but it **only binds once somebody's reports cite it**. While no one
depends on it, the set can be re-cut freely.

> **So publish the first set as provisional and say so in the file header.**
> Freeze it — and give it a version number that means something — at the moment
> the first person outside this project relies on a report that names it.

Getting this wrong is the only decision in either feature that cannot be undone
later, and it costs nothing to defer.

### What is decided, and what is not

Everything in §11 is still open. Two recommendations have hardened since this
was written, both because evidence turned up rather than because the argument
improved — see §11 for the detail and the sources.

## 1. Status, and what is already settled

| Question | Answer | Where it was settled |
|---|---|---|
| What does "printed through the profile" mean? | ChromIQ applies the profile with Argyll's own CMM and sends the printer a finished sheet, which prints raw | Researched from ArgyllCMS's shipped documentation — [#130 comment 5227083342](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5227083342). ⏳ awaiting confirmation |
| Is the §M phrase *"with colour management on"* an approved design ruling? | **No.** It was written by the assistant on 2026-07-22 and rode along inside a message Knut approved for a different purpose | [#130 comment 5226966519](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5226966519) |
| Does ChromIQ colour-manage at print time? | **No, deliberately, on every path** — and the native macOS path verifies after submission that the driver did not override the lock | `postscript_generator.py:302`, `cups_printer.py:45/75/86/97/114`, `workflow/native_print_macos.py` |

### What ArgyllCMS's own documentation says, verbatim

The three quotations this whole plan rests on. Each can be checked in the file
named, which ships with Argyll at `/Applications/Argyll/doc/`.

> *"colverify provides a way of verifying how well a **color transformation**
> (such a proofing) performs."* — `colverify.html`

> *"For systems using two device profiles or **a device link to convert between
> the target space printing files and the proofing device space** … the **device
> link used to print proofer test charts** … Use the `target_proofer_fix1.icm`
> **to print out the test chart again**, and read it in"* — `refine.html`

> *"The **-U** flag suppresses the CUPS `%cupsJobTicket: cups-disable-cmm` …
> **By default this ensures that the resulting files doesn't have color
> management applied to it.** If you are creating a test chart that should be
> color managed (perhaps because you want to use it to **verify the overall
> operation of the printing system**), then you can use the -U flag"*
> — `printtarg.html`

**What they establish:** Argyll's own verification loop converts the chart file
through the profile and prints the converted file. Colour-managed printing is
documented as a *different* job — verifying the printing system, not the
profile.

**What they do not establish, stated plainly:** Argyll's worked examples are the
*proofing* case. There is no example headed "verify a printer profile". The
mechanism transfers directly, but that application is an inference, not a quote.
No ICC or ISO standards were consulted, and nothing has been tested on hardware.

---

## 2. The two features, bounded against each other

| | **A — colour-managed verification printing** | **B — profile-tailored target (#133)** |
|---|---|---|
| Question answered | Did the printer produce what the profile promised, for the colours in this chart? | …across the whole range the profile claims it can reach? |
| Where the profile is applied | at **print** time | at **chart-build** time |
| Argyll tool | `cctiff` | `xicclu` |
| Direction | sRGB → printer device | Lab → printer device |
| Colours come from | the existing chart | a published master set, filtered through the profile's gamut |
| Reference for ΔE | the chart's design values as sRGB → Lab | the stored colorimetric Lab targets |
| New UI | one row on Print Chart | a Create Chart module — **and possibly nothing in Check & Refine**: `profcheck` turns out to be a valid check for this chart, so what is missing there may be framing rather than a module (§2b) |
| Depends on | nothing new | A, for the print step |

**They share the idea and almost none of the code.** That is the central fact
for planning: building them together saves nothing.

---

## 2a. Device type — RGB, CMY, CMYK, CMY+N?

Asked 2026-08-08: should the verification let the user pick a device type, the
way `targen` and ChromIQ's own generator do?

**No — and that is the design working, not a limitation.**

#133's master set is a list of **Lab targets**, not device values. It is
device-independent by construction: the profile being verified performs
Lab → device, so the device space is **whatever that profile is**. A device-type
picker would let someone generate a CMYK verification set for an RGB profile,
which is a category error — you would be asking a profile to reproduce colours
expressed in a space it does not have.

So the answer to "which device type?" is always: **the one the profile under
test uses.** Nothing to choose, and nothing to get wrong.

### What actually bounds it, in two layers

**Layer 1 — what can be profiled at all.** From `targen.html`:

> *"targen is used to generate the device channel test point values for
> grayscale, RGB, CMY, CMYK or N-color output or display devices. **[ Note
> though that colprof will only create RGB, CMY or CMYK profiles. ]**"*

A verification verifies a profile, so it can only ever apply to **RGB, CMY or
CMYK**. N-channel targets can be generated but not turned into an ICC profile,
so there is nothing to verify.

### The rule that makes all of this simple

Sebastian, 2026-08-08: *"a verification chart should probably use the same
colorspace settings as the chart that was used for profiling."*

**Not "probably" — necessarily, and it settles the whole question.**

A verification verifies a profile. That profile was built from a profiling
chart, and it carries that chart's device space and ink set. A verification
chart in a different space could not be printed through the profile at all —
the profile has no table for it.

So the device space is **inherited, twice over**: the profiling chart fixes the
profile's space, and the profile fixes the verification chart's. There is no
point in the chain where a user should be asked, and a picker would only create
the opportunity to answer wrongly.

**🔴 Requirement: a verification chart takes its colour space and ink set from
the profiling chart of the run it belongs to — not from the Create Chart
controls, and not from the last chart the user happened to make.**

Everything needed to do that already exists:

| What is needed | Where it already is |
|---|---|
| The ink set of the chart a profile was built from | `<stem>.channels.json` → `"ink_channels"` (e.g. `["r","g","b"]`), written for every chart |
| The device type and the extra-ink cascade as settings | the per-target store — `targen -d` and the repeatable `targen -D` are `ParameterWidget` rows, and the registry is generated from `per_target_widgets()`, never a written list |
| Which run a verification belongs to | the Profile-run selection in the bar |

So this is a **read, not a new mechanism**: take the run's profiling chart's
`ink_channels`, apply them, and do not offer the choice. It also gives a free
consistency check — if a verification chart's `ink_channels` ever disagree with
its run's profiling chart, something is wrong and the app can say so before a
sheet is printed rather than after it is measured.

**This also disposes of the N-ink question below for the normal case.** If the
profile came from ChromIQ it is RGB, CMY or CMYK, because that is all `colprof`
builds — so an inherited space is always one the rest of the app can handle. The
N-ink discussion only ever concerned profiles brought in from elsewhere.

### Extra colorants — the part I first left out

ChromIQ does not only expose `targen -d`. It has a first-class **add/remove
extra ink** feature (#72): fifteen of them — Orange, Red, Green, Blue, Violet,
White, Light and Medium C/M/Y/K, and Light-light black — offered in the patch
set editor (`ti2_relayout_dialog._extra_ink_labels`), carried as the repeatable
`targen -D` cascade, and recorded per chart in `<stem>.channels.json`.

**So charts can have 5, 6, 7+ inks. Can those be verified?**

**Argyll cannot build a profile for them** — confirmed from `colprof.html`'s own
summary rather than inferred:

> *"Create an RGB, CMY or CMYK ICC profile from the .ti3 test chart patch
> values. **[ Note that currently, Monochrome and N-Color profiles are not
> supported. ]**"*

⚠️ **But ChromIQ is not limited to Argyll here, and I missed that.** Sebastian
pointed it out: the **ChromIQ profile engine (beta)** — Settings ▸ *"ChromIQ
profile engine (beta)"* — exists for precisely this. Its own module docstring
(`workflow/profile_engine/__init__.py`):

> *"An **optional alternative to Argyll's colprof, never the default**. colprof
> remains the engine for everything it covers; this package's unique value is
> **what colprof structurally cannot do: CMYK+N output profiles** (colprof
> handles Gray/RGB/CMY/CMYK only)."*

It accepts **1–15 device channels** (`builder.py:341`), rejecting only what
falls outside the ICC range — and grayscale, because shipping `colprof` rejects
that too.

**So N-ink profiles can come from ChromIQ itself**, and the N-ink verification
question is **live rather than hypothetical**. The chain does not stop; it
reaches the report and stops there.

**But ChromIQ already checks N-ink profiles that come from somewhere else.**
`workflow/profcheck_nchannel.py` reproduces `profcheck` for **any** channel
count in Python, driving `icclu -ff` (icclib handles 2–15 channels), because
Argyll's own `profcheck` refuses more than 4 inks. So a 6-ink profile from a RIP
or from i1Publish *is* checkable in Check & Refine today.

That means the boundary is **not** "RGB only" as a principle. It is:

| Profile | Where it comes from | Can #133 verify it? |
|---|---|---|
| RGB / CMY / CMYK | ChromIQ's own `colprof` | **yes** — the target case |
| N-ink (CMYK+OG, etc.) | **the ChromIQ profile engine (beta)**, or elsewhere — a RIP, i1Publish | **in principle yes**: the master set is Lab, and `xicclu` / `icclu` handle 2–15 channels. Blocked only by the report path below |
| Monochrome | nothing builds it | no |

### ⚠️ ChromIQ has two `.ti3` readers, with different limits

This is worth recording on its own, because it is the actual obstacle and it is
not where anyone would look for it:

**Three of them**, not two:

| Reader | Accepts | Used by |
|---|---|---|
| `ti3_analysis.parse_ti3` | **RGB only** — raises *"No device RGB columns — only RGB charts are supported"* (`:158`) | the measurement report, the cube corners, the patch-identity check |
| `profcheck_nchannel._read_ti3` (`:40`) | **any** channel count, device fields read generically as `<REP>_<letter>` | Check & Refine for >4 inks |
| `profile_engine.ti3_data.read_ti3` | **any** — `iRGB`, `CMYK`, `CMYKOG`, light-ink reps like `CMYKcm` | the ChromIQ profile engine |

The split is not accidental — `ti3_data`'s own docstring names it: *"Unlike
`workflow.ti3_analysis` (RGB-only, feeds the measurement inspector), this reader
accepts any device colour representation Argyll's chartread can produce."*

So the same application reads the same file format three ways, with different
limits, and **the narrowest one is the one the report depends on.** ChromIQ can
already build a 6-ink profile and check it in Check & Refine, but cannot produce
a measurement report for it. **That, rather than any colour
science, is what would have to be settled before a verification could cover more
than RGB.**

**Layer 2 — what ChromIQ's own measurement path accepts, which is narrower.**
`workflow/ti3_analysis.py:158` refuses anything else outright:

```
raise Ti3ParseError("No device RGB columns — only RGB charts are supported.")
```

`parse_ti3` is what the measurement report, the cube corners and the
patch-identity check all read through. **So today the whole verification and
reporting path is RGB-only by an explicit decision, not by accident.**

### ⚠️ A latent inconsistency this exposes, worth checking separately

Create Chart offers `targen -d` with **choices 0–15** — grey, RGB, CMY, CMYK and
the N-colour combinations (`data/parameters.yaml`, wired at
`ui/tabs/tab_chart.py:2736` as `_manual_devtype_pw`). It is not restricted to
RGB.

So a user can pick CMYK, generate a chart and print it — and the measurement
report cannot read the result. **That gap exists today, independently of either
feature here.** It belongs in the tool-availability work
(`tool_availability.md`), because it is exactly the shape that document is for:
an option offered in one place that the rest of the app cannot honour.

**Not investigated here:** whether `chartread` itself accepts a CMYK chart, i.e.
whether the wall is at measuring or only at reporting. Worth establishing before
anyone decides what to do about it.

### If CMYK verification were ever wanted

It is not a change to either feature — both are already device-agnostic. It is a
change to `parse_ti3` and everything shaped around RGB device values: the cube
corners (`CUBE_CORNERS` is eight *RGB* corners), the `device` reference
fallback, and the patch-identity check. That is a separate piece of work with
its own design, and nothing in this plan blocks it or presumes it.

## 2b. `profcheck` already answers half of this — which shrinks feature B

Established 2026-08-09, and it corrects a claim #133 §10 had carried since it
was written: that the existing Check & Refine modules were *"a self-consistency
check, meaningless for a verification measurement."*

**That is not what `profcheck` does.** From `profcheck.html`:

> *"profcheck provides a way of checking how well an ICC profile conforms to the
> test sample data that was used to create it **(or other test samples that are
> from the same device)**."*
>
> *"The **absolute forward table** in the profile is used to create PCS values
> from the sample points, and the profile's PCS value then compared to the PCS
> values of the measured sample points."*

Other samples from the same device is exactly what a verification measurement
is. So the existing modules **are** appropriate for a verification run.

### The two checks test different halves of one profile

| | Tests | Answers | Chart printed |
|---|---|---|---|
| **`profcheck`** — Check & Refine's Guided / Manual | the **forward (A2B)** table | *"does the profile describe what this printer does?"* | **raw** |
| **Feature B's module** | the **backward (B2A)** table | *"if I ask the profile for a colour, do I get it?"* | converted |

The second is the question that matters when someone prints a photograph, so B
still has a reason to exist. But it is a *second* check, not a replacement for a
meaningless one.

### The condition that decides when `profcheck` is valid

`profcheck` pushes the `.ti3`'s **device values** forward through the profile, so
those values must be what was actually sent to the printer. Verified against real
files: `chartread` copies the chart's device values into the `.ti3` verbatim and
only *adds* the measurements — **15 of 15 identical** when paired by
`SAMPLE_ID`.

| Chart | `profcheck` valid? | Why |
|---|---|---|
| Verification chart printed **raw** | ✅ | the `.ti3`'s device values are what was printed |
| **Feature A's** chart — converted at **print** time | ❌ | the `.ti2` still holds the *unconverted* values |
| **Feature B's** chart — converted at **build** time by `xicclu` | ✅ | the `.ti2` holds the final device values |

⚠️ **The middle row is a trap worth pinning with a test.** After feature A ships,
running Check & Refine on a converted print would produce confident, meaningless
numbers — the same failure shape as every other double-conversion hazard in this
plan.

### What this changes

**Feature B's Check & Refine module may be unnecessary.** That tab is already
file-driven — it runs on whatever `.ti3` and `.icc` are loaded
(`tab_check_refine.py:1676`, `:1695`), with intent defaulting to absolute,
matching `profcheck`. What is missing is not the check but the **framing**:
nothing tells the user which of the two questions they are asking, and nothing
points the modules at the verification's own measurement automatically.

That is wording and wiring rather than a new panel, and it is a much smaller
piece of work. **Open**, and it should be settled before B's UI is designed.

## 3. Condition → action tables, mapped to code

Knut's method, applied:

> *"the only way to get the implementation right is to force claude to build
> complete tables with all combinations of responses and input conditions for
> all features, and then also force mapping in the tables the code lines where
> input conditions are implemented and where all options of output events /
> actions are implemented in code. This forces implementation, so it is not
> skipped silently."*

So every row below names **where the condition is read** and **where the action
happens**. A cell reading `NEW → file::function` is work that does not exist
yet; it is the implementation checklist, and a row with no code reference is a
row that has been skipped.

### 3.1 Feature A — when is the option shown, and what does it do?

Input conditions: **Run type** (`measurement_target_bar.py:767`, read via
`target.is_verification()` / `is_calibration()`), **profile present**
(`Run.built_profile_icc().exists()`), **the user's choice**, **print mode**
(`use_native_print_dialog`, read at `tab_print.py:883`).

| # | Run type | Profile in run | Row shown? | Default | Action on Print | Condition read at | Action implemented at |
|---|---|---|---|---|---|---|---|
| A1 | Profiling | any | **no** | — | print raw, as today | `tab_print` NEW::`_update_colour_row_visible` | unchanged: `tab_print.py:890` `_print_pages` |
| A2 | Calibration | any | **no** | — | print raw, as today | same | unchanged |
| A3 | Verification | **yes** | **yes** | through the profile | convert, then print raw | same | NEW → `tab_print`::`_convert_pages_through_profile` |
| A4 | Verification | **no** | **yes**, "through" disabled | raw | print raw + notice S7 | `Run.built_profile_icc().exists()` | NEW → same, plus the notice |
| A5 | Verification, "raw" chosen | any | yes | — | print raw, record the choice | the radio | unchanged path; NEW record |
| A6 | Verification, no chart generated | n/a | row hidden with the tab's existing empty state | — | nothing to print | `tab_chart._resolve_target_chart()` (`tab_chart.py:10359`) | unchanged |

### 🔴 3.1a — a chart from #133's module has ALREADY been converted

Raised by Sebastian, 2026-08-08, and it is a hole in the table above: **§3.1
keys only on the run type and whether a profile exists, not on which module
built the chart.** So a chart made by #133's FROM PROFILE GAMUT module would
land on §3.1 row A3 and default to *"through this run's profile"* — converting a
second time.

That is precisely the double conversion §7.D warns about, and the worst kind:
the sheet prints, measures cleanly, and produces a confident report describing
nothing. Nothing downstream can detect it.

**The two verification charts want opposite settings on the same row:**

| Chart | Colours in the file | Correct setting | Why |
|---|---|---|---|
| Guided / Manual verification | source colours, read as sRGB | **through the profile** | the profile has not been applied yet |
| **#133 FROM PROFILE GAMUT** | **final device values** from `xicclu` at build time | **raw** | the profile was applied when the chart was made |

🔴 **Requirement: when the loaded chart carries stored colorimetric targets, the
"Colour" row is forced to Raw and "Through this run's profile" is disabled —
not merely deselected.**

**Disabled, not defaulted, and the distinction matters.** For this chart
"through the profile" is not a preference someone might reasonably hold — it is
an error with no legitimate use, whose damage is invisible afterwards. A default
can be changed by one stray click; a disabled control cannot. The app already
has this exact pattern and Knut chose it: Build Profile is **greyed with a
tooltip** during a verification run (beta.157, `main_window.py:934`) rather than
left enabled with a warning.

### What tells the app which kind of chart it is

**Nothing new needs recording.** §11 step 5 already has this module write the
reference `.ti3` of colorimetric targets beside the chart. **Its presence is the
marker** — a chart with stored colorimetric targets is, by definition, one whose
colours were already converted through the profile.

That is worth preferring over a flag in `meta.json` or `channels.json`
(`ink_channels`, `layout`, `chart_notes`, `stamp_commands` — no provenance field
today) for one reason: **the same file that tells the report to use the
`colorimetric` reference (row B4) tells the Print tab the sheet is already
converted.** One fact, one file, and the two cannot drift into disagreeing.

| # | Condition | Action | Where |
|---|---|---|---|
| A3a | Loaded chart **has** a colorimetric reference beside it | force Raw; disable "through the profile"; show the notice below | NEW → `tab_print`::`_update_colour_row_visible`, reading `Run`/`Verification` for the reference file |
| A3b | Loaded chart has **no** such reference | §3.1 applies unchanged | — |
| A3c | The reference file is missing but the chart claims to be one | **treat as A3a and say so** — refusing to convert is always the safe direction | NEW |

### The wording

Friendly, and explaining the outcome rather than the mechanism. Shown in place
of the choice, not behind an ⓘ, because it is a **state** and not an option:

> **This chart already has your profile applied, so it prints exactly as it is.**
>
> When you created it, ChromIQ asked your profile which ink amounts would
> produce each of the colours being tested, and stored the answer in the chart
> itself. The sheet is your profile's prediction already — there is nothing left
> to convert.
>
> That is why "Through this run's profile" is switched off here. Applying the
> profile a second time would print different colours from the ones being
> tested, your measurement would faithfully describe those different colours,
> and nothing afterwards could tell that it had happened.
>
> You do not need to change anything. Print as usual, and if you print from
> another application, simply make sure it does not convert the colours either.

**Test T11** (added to §9): a chart with a colorimetric reference disables the
option, and the disabled control cannot be re-enabled by switching run type
back and forth.

#### ✅ A disabled option must *look* disabled — CONFIRMED

**Confirmed by:** Sebastian, 2026-08-08 — *"what i saw last on github looked
right"*, *"it is ok as it is"*, after seeing the corrected render and the four
alternatives side by side.

This is the one part of this document that is settled. It was shipped in
v3.14.8-beta.207, checked on screen by a human, and the alternatives were
explicitly declined. The promotion rule from the top of this file has been
followed: verified, then shown, then confirmed by name and date.

The rest of the document remains a draft.

Reviewing the §3.1a mockup, Sebastian noticed the notice said the option was
unavailable while the option looked perfectly clickable. That was **not the
mockup**.

Measured on the dark theme, rendered pixels rather than read from the
stylesheet:

| Control | Enabled | Disabled |
|---|---|---|
| `QCheckBox` | `#e6e6e6` | `#6a6a6a` ✅ |
| `QRadioButton` | `#e6e6e6` | **`#e6e6e6`** ❌ — identical |

`ui/styles.py` carried `QCheckBox:disabled` and `QCheckBox::indicator:disabled`
but never the radio equivalents; only radios with `objectName="param_label"`
were covered, and the plan's rows use plain ones.

**This is a dependency of §3.1a, not a cosmetic aside.** That row requires an
option to be *disabled rather than merely deselected*, because choosing it would
convert a chart twice — an error nothing downstream can detect. A disabled
control that looks live cannot carry that design: the user would click it,
nothing would happen, and the only explanation would be a paragraph they had
already skipped.

**Fixed ahead of the feature** (it is a defect in its own right, and 26 plain
radios exist across seven files): `QRadioButton:disabled`,
`::indicator:disabled` and `::indicator:checked:disabled` now mirror the
checkbox rules. The last one is needed for the same reason it is on checkboxes —
the accent fill otherwise outranks Qt's disabled greying and a switched-off
option keeps a bright dot.

`tests/test_disabled_controls_look_disabled.py` **measures rendered pixels**
rather than reading the stylesheet, because the stylesheet said the right thing
about checkboxes for years while radios went uncovered and no test noticed.
Proved by removing the rules again: four tests fail.

**The general rule, worth applying beyond this feature:** when a design relies
on a control being visibly unavailable, that visibility is part of the design
and needs testing like any other behaviour. "Disabled" is a claim about what the
user can see, not only about what the widget will accept.

**Two things declined, recorded so they are not re-proposed as new ideas.**
Four treatments were rendered at 2× and compared (`cm_8_disabled_variants.png`):
`#6a6a6a` as shipped, `#505050` to match the app's disabled buttons, `#4a4a4a`,
and `#505050` with the reason written into the label. Sebastian chose to keep
what shipped. My own preference had been the last of those; it was not taken,
and that is the answer.

⚠️ **One inconsistency was found on the way and is left as it is:** disabled
*button* text is `#505050` while disabled tick boxes and radios are `#6a6a6a`.
The radios now match the tick boxes, which is self-consistent for controls of
that kind. Worth knowing before anyone "tidies" one of the two to match the
other — that would be a visual change across the whole app, not a fix.

**A process note that cost a round trip:** the corrected mockup looked unchanged
on GitHub because the embedded copy was cached from before the re-render. When a
mockup is corrected, link it by **commit SHA** (`/raw/<sha>/…`) rather than by
branch, or the reviewer is asked to judge the old picture.

### 🔴 3.1b — and the mirror case: should "raw" be greyed for a regular chart?

Asked immediately after §3.1a, and the honest answer is **no — the asymmetry is
real, not an oversight.** It is worth writing down precisely, because "be
consistent" is the obvious instinct and it would remove something useful here.

| Combination | What it is | Verdict |
|---|---|---|
| #133 chart + "through the profile" | the profile applied **twice** — different colours printed, measured faithfully, undetectable afterwards | **an error**, with no legitimate use → **disable** (§3.1a) |
| Regular chart + "raw" | the chart's own numbers printed untouched | **a different question**, and a useful one → **allow, and say what it measures** |

**Why "raw" is legitimate for a Guided or Manual verification chart.** Printed
raw and measured, the sheet answers *"is my printer still behaving the way it
did last month?"* — a genuine drift check, and one that needs no profile at all.
#133's own §3 table already names this as what a verification run does today:
*"Has anything drifted since last time, against the chart's own design
colours."* Every verification history in an existing project was made this way.

**So the two are not the same shape.** One combination cannot produce a
meaningful number at all; the other produces a perfectly good number to a
different question. Greying the second would take away the only check the app
has today, and would silently invalidate the histories people already have.

🔴 **Requirement: "raw" stays available for a regular verification chart, and
the panel says what it will measure.** The danger is not that someone picks it —
it is that they pick it *expecting an accuracy check* and get a drift check
without noticing. So the notice is about the **question being answered**, not
about a rule being broken:

> **Printing raw measures your printer, not your profile.**
>
> The sheet goes to the printer exactly as it is, with no profile involved. That
> is useful for one particular question: *"is my printer still behaving the way
> it did last time?"* Print the same chart the same way each month and compare
> the results, and you will see it drift before it becomes visible in your work.
>
> What it cannot tell you is how accurate your profile is, because no profile
> took part. For that, choose **Through this run's profile** above — then the
> sheet is your profile's own prediction, and measuring it shows how close the
> prediction came.
>
> Whichever you choose is written on the report, so you can always tell later
> which of the two questions a set of figures answered.

**The report must carry this too**, and it is not extra work: `reference_source`
(row A19/B4) and the printing route (A18) are already recorded. The report
should name the **question** in plain words — "how accurate is this profile?"
versus "has this printer changed?" — rather than leaving the reader to infer it
from two technical fields.

**Test T12** (§9): a regular verification chart offers both options with neither
disabled, and the notice changes with the selection.

### 3.2 Feature A — the conversion itself

| # | Condition | Action | Where |
|---|---|---|---|
| A7 | Conversion needed (A3) | `cctiff -p -f T -i <intent> <sRGB.icm> -i <intent> <run profile> page.tif out.tif` | `workflow/cctiff_apply.py` — `convert_args()` at `:47` **must be generalised**: it hardcodes `-i r` for both ends |
| A8 | Where the converted sheets go | `Verification.cache_dir` | `core/file_manager.py:1200`; documented as always safe to delete |
| A9 | Which source profile | Argyll `ref/sRGB.icm`, else the bundled copy | `tab_profile.py:3934` `_default_gamut_src` — **must be lifted** to a shared helper |
| A10 | `cctiff` missing from the Argyll folder | refuse, explain, offer raw | NEW → message **M-CM-NO-CCTIFF**, §M-PROPOSED |
| A11 | A page fails to convert | stop, name the page, print nothing | NEW → message **M-CM-CONVERT-FAILED**, §M-PROPOSED |
| A12 | The profile is unreadable / not RGB | refuse, explain | `cctiff_apply.py:63-78` already parses these errors |
| A13 | Converted sheet then printed | the existing raw path, unchanged | `tab_print.py:890` / `:1335`; locks at `cups_printer.py:45` and `native_print_macos.py` |
| A14 | Double conversion (driver also converts) | **must remain impossible** | already prevented; **a test must pin it** — see §9 T7 |

### 3.3 Feature A — what is recorded, so a number can be interpreted

| # | Fact | Stored | Shown | Where |
|---|---|---|---|---|
| A15 | Printed through the profile, or raw | `Verification` meta | report block | NEW → `CalibrationMeta`-style field; report at `measurement_report.py` |
| A16 | Rendering intent used | same | same | NEW |
| A17 | Which profile file, and its modification time | same | same | NEW — a profile rebuilt after printing invalidates the comparison |
| A18 | Route: printed by ChromIQ or elsewhere | same | same | NEW — this is #133 §8's second row, folded in here (§4) |
| A19 | The reference the ΔE was computed against | already `report["reference_source"]` | report block | `measurement_report.py:355-379`; today only `design` / `device` |
| A20 | Whether the readings belong to the chart at all | `report["patch_identity"]` | its own notice today — **should move into this block when A lands**, so the report gives one account of its conditions | **shipped** beta.206, `measurement_report.verify_patch_identity` |

### 3.4 Feature B — the reference source, which is where B meets A

| # | Chart kind | `reference_source` | Correct today? | Where |
|---|---|---|---|---|
| B1 | Profiling chart | `design` (sRGB reading of device values) | yes | `measurement_report.py:362` |
| B2 | Verification chart, printed **raw** (today) | `design` | **no** — compares ink numbers read as sRGB against a print nothing converted | `measurement_report.py:191` `_reference_labs` |
| B3 | Verification chart, printed **through the profile** (feature A) | `design` | **yes** — this is what makes A worth doing | unchanged code, newly correct |
| B4 | #133 gamut chart | **`colorimetric`** — a new value | n/a, does not exist | NEW → `measurement_report.py` |
| B5 | Imported measurement, no `.ti2` | `device` | yes | `measurement_report.py:370` |
| B6 | #133 chart, colorimetric reference missing | **must refuse**, not fall back | n/a | NEW — a silent fallback to `design` produces a plausible wrong number. **Follow the pattern beta.206 set**: state what could not be established rather than substituting something plausible |

**B3 is the single most important line in this document.** Feature A does not
just add an option; it makes the report's existing reference correct for the
first time.

---

## 4. The Print Chart tab, reconciled

#133 §8 proposed two rows on this tab (**Route**, and **Recorded on the
report**). Feature A proposes two more (**Colour**, **Rendering intent**). Four
rows from two documents would be incoherent, so they are reconciled here into
**one section with three rows**, and the fourth becomes a consequence rather
than a control.

| Row | Shown when | Choices | Applies to |
|---|---|---|---|
| **Colour** | Run type = Verification | through this run's profile · raw | verification only — a profiling chart is always raw, and offering the choice would invite the one mistake that ruins a profile |
| **Rendering intent** | Colour = through the profile | relative · absolute · perceptual · saturation | verification only |
| **Route** | always | print here · print in another application | every chart — a profiling chart printed through a foreign conversion is wrong in exactly the same undetectable way |
| ~~Recorded on the report~~ | — | — | **not a control.** ChromIQ knows both answers from the two rows above; it records them rather than asking a third time |

**Why "Route" survives and stays global**: ChromIQ can see whether it printed a
chart itself; it cannot see whether an application it never spoke to had colour
management switched on, and those two failures look identical on the report.

**How the two interact**, which is the question that needed thinking through:

| Colour | Route | What ChromIQ hands over | What the other application must do |
|---|---|---|---|
| through the profile | here | converted sheets, printed raw | — |
| through the profile | elsewhere | **converted** sheets in `cache/` | nothing but print them untouched — the colour work is already done |
| raw | here | the chart sheets, printed raw | — |
| raw | elsewhere | the chart sheets | print untouched |

**The reassuring outcome: the instruction to the outside world is the same in
every row — "do not convert these colours."** Feature A does not complicate the
external route; it removes the only reason someone would have wanted their
external application to colour-manage.

---

## 5. Implementation plan, ordered to be de-risked

Each step ends somewhere shippable. Nothing later is required for anything
earlier to be useful.

### Phase A0 — correct the record (no user-visible change)

| # | Work | Risk |
|---|---|---|
| A0.1 | Correct the §M text so it stops instructing something the app prevents. **Goes to §M-PROPOSED for approval; it is approved text and cannot be quietly rewritten** | none |
| A0.2 | Generalise `cctiff_apply.convert_args()` to take an intent | none — one parameter |
| A0.3 | Lift `_default_gamut_src` out of `tab_profile` into a shared helper; both callers use it | none, removes a duplication |

### Phase A1 — the conversion, with no UI at all

| # | Work | Risk | Mitigation |
|---|---|---|---|
| A1.1 | `convert_pages_through_profile(pages, profile, intent, out_dir)` in `workflow/` | low | pure function over paths; testable with a stub runner exactly as `xicclu_runner` is |
| A1.2 | Unit tests including A10–A12 failures | — | — |

**Shippable checkpoint:** nothing changes for users; the machinery is proven.

### Phase A2 — the UI and the record

| # | Work | Risk | Mitigation |
|---|---|---|---|
| A2.1 | The three-row section of §4, visibility per table 3.1 | low | the tab already switches on run type |
| A2.2 | Wire the conversion into the **one** place both print buttons funnel through (`_on_print_current` `:867` and `_on_print_all` `:879`) | **medium** — two entry points, and missing one means the option silently does nothing | insert below both, at `_print_pages`/`_print_native`; test T4 drives **both buttons** |
| A2.3 | Record A15–A18; show them in the report block | low | — |
| A2.4 | Help texts §6, and the two new §M messages | low | approval needed before they reach a tab |

**Shippable checkpoint:** feature A complete.

### Phase A3 — the honest migration

| # | Work | Risk | Mitigation |
|---|---|---|---|
| A3.1 | Decide and implement the default for projects that already have verification history (§11 Q3) | **highest risk in A**, and it is a *design* risk, not a coding one | a trend that silently changes meaning is worse than no trend; the report must mark the point where the method changed |

### Phase B — #133, only after A

Not planned in detail here, because **B's own open questions are unanswered**
(#133 §16: set size, whether colours are redrawn, the margin default, and nine
more). Planning it in detail now would be inventing those answers. What B
inherits from A: the vocabulary, the report block, the intent record, and the
`reference_source` enumeration extended with `colorimetric` (B4).

**One scoping note that is now known**, and it makes B smaller: B was assumed to
need a new Check & Refine module. §2b shows the existing `profcheck` modules are
a valid check for B's chart, so what is missing there may be framing rather than
a panel. Settle that before designing B's UI — it is the difference between a
new module and a paragraph.

---

## 6. Help texts — drafted, with stable IDs

IDs are used so translations attach to the **ID**, not to the English sentence.
That matters: the catalogue key is the exact English string
(`scripts/i18n_extract.py`), so a reworded sentence discards every translation
of it. With IDs, re-approval is a mapping exercise instead.

| ID | Where | Kind |
|---|---|---|
| S1 | Print tab, "Colour" row label | label |
| S2 | S1's two options | labels |
| S3 | Print tab, "Rendering intent" label | label |
| S4 | ⓘ behind S1 | long help |
| S5 | ⓘ behind S3 | long help |
| S6 | on-panel notice, profile present | state |
| S7 | on-panel notice, no profile | state |
| S8 | report block headings | labels |
| S9 | M-CM-NO-CCTIFF | §M message |
| S10 | M-CM-CONVERT-FAILED | §M message |
| S11 | Dictionary: rendering intent | glossary |
| S12 | Dictionary: verification | glossary |

The full English text of S4–S7 is what the mockups in §8 render, and is drawn
from `scripts/mockup_cm_verification_print.py` so the document and the picture
cannot drift. S9–S12 are drafted below.

**S9 — M-CM-NO-CCTIFF**

> **ChromIQ cannot find the tool that applies your profile**
>
> To print this chart through your profile, ChromIQ uses a program called
> `cctiff`, which comes with ArgyllCMS. It is not in the ArgyllCMS folder
> ChromIQ is set to use.
>
> You can still print this sheet raw — choose "Raw" above — but measuring it
> will tell you about your printer rather than about your profile.
>
> To fix it: open Preferences and check that the ArgyllCMS folder is the one
> you installed, then reopen this tab.

**S10 — M-CM-CONVERT-FAILED**

> **This sheet could not be prepared**
>
> ChromIQ was working out the ink amounts your profile predicts for page {n} of
> {total}, and that did not finish. Nothing has been printed and nothing has
> been changed.
>
> The most common reason is that the profile file is damaged or is not a
> printer profile. Rebuilding the profile on the Build Profile tab usually
> fixes it.
>
> Details: {reason}

**S11 — Dictionary: rendering intent**

> Your printer cannot make every colour that exists. The rendering intent is the
> rule for what happens to the colours it cannot reach — whether they are moved
> to the nearest colour it can print, and whether the shade of your paper counts
> as an error. For checking a profile, relative colorimetric is the usual
> choice.

**S12 — Dictionary: verification**

> A verification is a check on a profile you have already built. You print a
> chart through that profile, measure it, and see how close the colours came to
> what the profile promised. It answers "is my profile still good?" — unlike a
> profiling chart, which is what you print to *create* a profile in the first
> place.

---

## 7. Translations

**The recommendation is not to translate yet, and the reason is a lesson this
project already paid for.** The catalogue key is the exact English source string
(`scripts/i18n_extract.py`), so every word changed during review discards that
string's translation in all twelve languages. §6's English is a draft awaiting
approval; translating it now would mean translating it twice.

**What is prepared instead, so nothing is slow later:**

- Every string has a stable ID (§6), so translations can be produced against
  IDs and mapped when the English is signed off.
- Twelve languages are live and complete today — `data/i18n/*.json`: de, es,
  fr, it, ja, nl, no, pl, pt, ru, sv, zh_CN.
- The pipeline exists and is enforced: `scripts/i18n_extract.py --missing <lang>`
  lists what a language lacks, `--stats` reports coverage, and
  `tests/test_i18n.py` fails on missing keys, stale keys, placeholder mismatches
  and over-long short labels.
- `scripts/i18n_check_name_widths.py` guards the short labels (S1–S3, S8), which
  are the ones that can break a layout — German is typically the longest.

**So the sequence is: approve the English → run the extractor → translate → the
tests prove completeness.** Doing it in that order costs one pass instead of two.

---

## 8. Mockups

Drawn with the real ChromIQ widgets and the real stylesheet, so they show what
the app would render. Generator: `scripts/mockup_cm_verification_print.py` —
committed, so a wrong detail is a re-run rather than a redraw.

| Screen | File |
|---|---|
| Print Chart, the new section | `docs/mockups/cm130/cm_1_print.png` |
| The ⓘ window behind it (the real `_InfoDialog`) | `docs/mockups/cm130/cm_2_info.png` |
| The report block | `docs/mockups/cm130/cm_3_report.png` |
| The no-profile state | `docs/mockups/cm130/cm_4_no_profile.png` |
| **The reconciled section of §4** — Colour + Intent + Route together | `docs/mockups/cm130/cm_5_reconciled.png` |
| **§3.1a — a chart that already has the profile applied**, with the option disabled | `docs/mockups/cm130/cm_6_already.png` |
| **§3.1b — the mirror case**: a regular verification chart printed raw, with **nothing** disabled | `docs/mockups/cm130/cm_7_raw_chosen.png` |

The last one supersedes `acc133/acc_3_print.png`, which shows #133 §8's earlier
two-row proposal. That mockup stays where it is as the record of what was
proposed there; §4 and `cm_5_reconciled.png` are what would actually be built.

---

## 9. Tests

| # | Proves | Kind |
|---|---|---|
| T1 | The row appears for exactly the rows of table 3.1 and no others | unit, all three run types |
| T2 | Converted sheets land in `Verification.cache_dir`, never in the run root | unit |
| T3 | The `cctiff` arguments carry the chosen intent — not the hardcoded `-i r` | unit |
| T4 | **Both** print buttons convert — `_on_print_current` and `_on_print_all` | unit; the A2.2 risk |
| T5 | A missing `cctiff` shows S9 and prints nothing | unit |
| T6 | A failed page shows S10, prints nothing, changes nothing | unit |
| T7 | The colour-management locks are still asserted on both print paths | **regression**; pins A14 |
| T8 | The report block shows intent, route and reference; absent when not applicable | unit |
| T9 | An existing verification project opens unchanged (migration) | unit |
| T10 | On-screen: the real app, verification selected, both buttons, files checked on disk | driver script, per the project's practice |
| T11 | A chart with stored colorimetric targets **forces Raw and disables "through the profile"**, and cannot be re-enabled by toggling the run type | unit; pins §3.1a |
| T12 | A **regular** verification chart offers **both** options, neither disabled, and the notice follows the selection | unit; pins §3.1b — the asymmetry is deliberate |
| T13 | Check & Refine **refuses, or clearly warns**, when asked to `profcheck` a measurement whose chart was converted at **print** time | unit; pins the §2b trap — the `.ti2` holds unconverted values, so the numbers would be confident and meaningless |

---

## 10. Edge cases

- **A profile rebuilt after the sheet was printed** — the comparison is against
  a profile that no longer exists. A17 records the file and its modification
  time so the report can say so.
- **An existing project with verification history** — see A3.1 and Q3. The
  trend's meaning changes; the report must mark where.
- **A chart with no pages generated** — row hidden, handled by the tab's
  existing empty state.
- **Calibration selected** — never offered (A2). A calibration has no profile
  to print through.
- **"New run" selected** — no run, no profile, nothing to print.
- **Verification chart printed raw on purpose** — legitimate and kept (A5); it
  measures the printer, and the report says so.
- **16-bit sheets** — already the default (`tiff_16bit=True`), so the
  conversion does not visibly quantise.
- **Old projects** — nothing in the folder model changes; `cache/` is created
  on demand and is documented as safe to delete.

---

## 11. Open questions

1. **Build feature A?** Recommendation: yes. Today's verification does not
   measure what its own messages claim.
2. **Build A and B together?** Recommendation: **no** — A first. They share the
   idea and almost no code (§2), and B is blocked on its own unanswered
   questions.
3. **Default for projects that already have verification history?** Options:
   on everywhere (the trend changes meaning); off for existing projects, on for
   new ones (**recommended**); always ask once. This is the highest-risk
   decision in A, and it is a judgement about users, not code.
4. **Default rendering intent** — and it is **two questions, not one.**
   I had been treating it as a single decision, and describing my own answer as
   "weak" because it seemed to contradict the original #133 request. Sebastian
   pointed out that it need not: the two features choose their intent at
   **different moments, in different tabs**, so they can hold different defaults
   without disagreeing. He is right, and #133 §7.C already said so — *"one
   choice, made when the chart is generated"* — for its own feature.

   | | Chosen where | At what moment | Recommended default |
   |---|---|---|---|
   | **Feature A** (regular chart) | **Print Chart** tab | print time, when `cctiff` runs | **relative colorimetric** — the usual choice for judging a profile on its own paper |
   | **#133's module** | **Create Chart**, in *From profile gamut* | chart-build time, when `xicclu` runs, and written into the reference file | **absolute colorimetric** — matches the practice #133 sets out to replace, and keeps the figures comparable with it |

   This also matches what the mockups already show: `cm_6_already.png` has the
   Print tab's intent control **disabled** for a #133 chart, with the note *"the
   rendering intent was chosen when this chart was created, and is stored with
   it."* The design was already consistent; only this question was written up as
   though it were one decision.

   **What still needs answering** is therefore much smaller: confirm the two
   defaults above. Neither is a constraint — both intents are offered in full,
   and whichever is used is recorded on the report.

5. **Where would the Print tab's intent be *stored*?** Raised by Sebastian, and
   it has no answer today: **`tab_print` is not one of the storing tabs.** Only
   Create Chart, Measure and Build Profile implement
   `load_target_settings` / `save_target_settings`
   (`ui/tabs/tab_chart.py`, `tab_measure.py`, `tab_profile.py`) — the Print tab
   stores nothing per target.

   So Feature A's intent needs a decision the #133 one does not: make the Print
   tab a fourth storing tab, keep the setting app-wide, or record it only onto
   the verification it produced. **#133's intent needs none of this** — Create
   Chart's store is generated from `per_target_widgets()`, so a new row there is
   carried automatically.

   That is a point in favour of putting as much as possible in Create Chart, and
   worth weighing before Phase A2.

   **And it lowers the stakes of question 4 considerably.** Once a setting is
   stored per target, a default is only ever the *first* answer a target gets;
   the user's own choice is written to that target's `meta.json` and comes back
   next time. A default here is a starting point, not a policy.

6. **Does the Route row of §4 ship with A**, or stay with #133? Recommendation:
   with A, because §4 only becomes coherent once both exist.

---

7. **How big is the master set?** ⚠️ **I have now been wrong twice here, and
   the second time is instructive.**

   First I invented 1 500. Then I "corrected" it to **1 617** by counting the
   professional reference sets shipped with i1Profiler — but every one of those
   lives under `ColorSpaceCMYK/`. **1 617 is IT8.7/4, a CMYK printing-press
   number.** ChromIQ profiles **RGB** printers, so I took a figure from the
   wrong colour space, which is the same mistake as the §5.3 capacity table:
   a real number read against the wrong key.

   **What RGB practice actually looks like**, from `ColorSpaceRGB/` in the same
   installation and from ChromIQ's own bundled charts:

   | Set | Patches |
   |---|---|
   | i1Profiler `printer test` | 90 |
   | i1Profiler TC2.83 RGB | 294 |
   | i1Profiler default for **i1Pro** (handheld) | 800 |
   | i1Profiler TC9.18 RGB | 918 |
   | i1Profiler defaults for **i1iSis / i1iO** (automated) | 957 / 999 |
   | ChromIQ `redriver` standard patch set | 2 052 |
   | ChromIQ `knut` scanner A4 | 3 430 |
   | i1Profiler `RGB_default` measurements (iSis / iO / i1Pro) | **8 132** |
   | ChromIQ `knut` scanner A4, 3 pages | **10 290** |

   **So "more than 3 234 makes no sense" is false**, and provably so from files
   already on disk. What actually sets the sensible size is **how the chart is
   measured**, not any standard: i1Profiler's own defaults scale with the
   instrument — 90 for a quick single-patch check, 800 for a handheld i1Pro,
   ~1 000 for an automated table, 8 132 when reading is essentially free.

   **Revised recommendation:** generate the master set **large — 6 000 to
   8 000** — since nesting means the size costs nothing until someone prints it,
   and make the *offered* size follow the instrument the way i1Profiler does,
   using the per-instrument capacities `data/patch_db.py` already holds. The
   default should be a number of **sheets** the user will accept, not a number
   of patches picked from a standard.

   ⚠️ Note the big ChromIQ figures above are **scanner** charts, where a flatbed
   reads a whole sheet at once. They show the format is not the limit; they are
   not evidence that anyone wants to hand-measure 10 290 patches.

8. **The margin default** — "safely inside" or the full printable range?
   ⚠️ Also weak: no measurement stands behind it. Worth settling with one real
   print rather than an argument.

## 12. Rating

- **Correctness 8** — the mechanism is verified against Argyll's own
  documentation and against the modules cited, and the reuse is real. Not
  higher because the application to a printer profile is an inference from a
  proofing example (§1), and nothing has been tested on hardware.
- **Robustness 8** — the failure paths are enumerated with messages and tests,
  and the print path itself does not change. The residual risk is A3.1, which
  is a design decision rather than a defect.
- **Maintainability 9** — one new function, one row, two existing duplications
  removed. Feature B inherits rather than duplicates.
- **Efficiency 9** — one `cctiff` pass per page, only for verification runs.
- **Evidence quality 8** — the three load-bearing quotations are verbatim from
  the shipped documentation and named by file; every code reference in §3 was
  checked against the tree on 2026-08-08. One gap named here has since been
  closed by measurement rather than argument — i1Profiler does preserve patch
  order — but that was **not** the load-bearing one. Still not higher, and for
  the same two reasons: the proofing→printer inference is mine, no ICC or ISO
  source was consulted, and **nothing about colour-managed printing has been
  tested on hardware**. One real print done both ways would close it.
