# Issue #182: the answers we have been given, and who gave them

**This file exists because the working notes for #182 are deliberately kept out
of the repository.** `.gitignore` excludes `.progress/issue-182/`, because those
notes quote tolerance VALUES out of paywalled standards and the permission
enquiry now with a standards body rests on those values not being in our public
repository. The ANSWERS below are ours to keep; the numbers are not, and none
appear here.

> **AND THAT PREMISE WAS FALSE WHEN IT WAS WRITTEN. 2026-09-10.** Gitignoring
> the working notes protected nothing, because the numbers had already been
> published by another route: the branch `issue-182-mockups`, in this PUBLIC
> repository, carried twelve pictures and one document that reproduced the
> tolerance tables of both standards, one of them quoting a sentence of the
> standard verbatim, and every one of those pictures was embedded inline in the
> public issue. From round 3 onwards each picture masked the numbers and said so
> on its own face. Nobody went back for rounds 1 and 2.
>
> The branch has been rebuilt with no history, keeping only the material that is
> ours or is masked; the twelve pictures and the document now return 404, and
> the pictures that were safe still load in the issue. The complete original is
> preserved off the internet as a verified git bundle in the research folder, so
> nothing is lost.
>
> **What is NOT finished:** the superseded commit is still reachable on GitHub by
> its hash, because a force-push does not delete anything, and a public
> repository's activity log names the hash. Only GitHub Support can purge it,
> and only the account owner can ask. That request is on Basti's decision sheet.
>
> **What was NOT affected:** master. The material never touched it, on any
> commit, and the shipping branch carries standard NAMES and clause citations
> only, with no value anywhere.
>
> The lesson is the one this project keeps relearning: a rule enforced in one
> place is not enforced. A `.gitignore` covers a path, not a repository, and
> nobody had asked what else was public.

Nothing in this file is implemented yet unless it says so. It is a record, so
that a month from now nobody has to reconstruct what was decided from a chat
thread.

Last updated 2026-09-11 (sections 2e, 2f and 2g).

---

## 1. Permissions: four granted, one outstanding

| Rights holder | Answer | The wording that binds us |
|---|---|---|
| **Fogra** (Dr.-Ing. Andreas Kraushaar, Prepress) | GRANTED | Free use and unchanged redistribution, including inside commercial and non-commercial software, **provided Fogra is clearly named as the source**. The FOGRAxx name may be used to say which reference set was compared against, and that is **not a certification, approval or endorsement**. |
| **CGATS** (Adam Dewitz, Association for PRINT Technologies) | GRANTED | *"You are free to use the CGATS data sets in your software as you have defined below. These files have been made generally available to the industry."* No condition stated. The same reply is the originator confirmation the ICC asked for. |
| **ICC** (Phil Green, cc technical secretary and secretary) | ACCEPTED | Registry data *"is OK to re-distribute, with the usual proviso that if altered it shouldn't be represented as the same data."* Closed by Adam Dewitz answering for CGATS on the same thread. |
| **Idealliance / PRINTING United Alliance** (Jordan Gorski, VP Global Standards and Certifications, 2026-09-09) | GRANTED | The "may not be sold" clause means only that the profiles may not be sold as a product in their own right. They may be included in and distributed with software under any licence, including where a recipient charges for the copy, provided the profile is unaltered. Running a device value through a profile to obtain an aim colour is USE, not alteration. X-Rite's approval is not needed. Naming a profile to say what was compared against is agreed, and he asks for the line **"GRACoL is a registered trademark of PRINTING United Alliance."** |
| **ISO** | REFUSED as asked, and redirected | Reproducing the content of a standard inside software needs explicit permission or a specific licence; a single-user licence is not enough; the route is the national member body. A letter was drafted, reviewed three times and **has been sent** (Basti, 2026-09-10). No answer yet. |

### The standing rule, and it is the owner's

**No value from ISO 12647-7 or ISO 12647-8 goes into the code, the repository,
a release or a posted picture until permission is in writing.** Basti,
2026-09-10: *"don't implement the iso stuff until we got permission. i don't
want to get in trouble."* Knut has asked for the thresholds to be included so a
beta can be tested; that request is NOT authority to include them.

The honest way to give a tester real verdicts meanwhile: `compliance_sets.py`
reads its data file from a path the environment variable
`CHROMIQ_COMPLIANCE_ISO_FILE` can override, so a tester who owns the standard
points ChromIQ at their own copy. ChromIQ distributes nothing.

### What each grant obliges the app to do, and none of it is built yet

* Fogra: named as the source wherever its data is used, and nothing implying
  endorsement.
* Idealliance: the trademark line above, the profile shipped unaltered, and the
  promise that ChromIQ never prints that a print "conforms to", "is certified
  to" or "qualifies as" anything. **That promise is now made to a third party**,
  so the rule that the word appears only in denials has to hold permanently.
* ICC: altered data must never be presented as the original. This collides with
  any proposal to nudge values or convert them between colour spaces and keep
  the original name.
* `data/compliance_sets/` has no README or LICENSE where every other bundled
  third-party folder has one.

---

## 2. Knut's rulings

### 2026-09-07 (K-a to K-j)

| Ref | Ruling |
|---|---|
| K-a | Use shape A. |
| K-b | All columns ON by default. The setting is remembered **per profile run**, because another run in the same project may want to compare different columns. |
| K-c | No grid needed. |
| K-e | The Measurement Report belongs to the verification run. Copy the user's reference file into the run's verification folder. |
| K-f | The verdict words are **PASS / FAIL / CONDITIONAL / INFO / N-A**, with a shorter form wanted for CONDITIONAL because the tables get wide. Every outcome must be covered and every word defined in the report's own text. **"Conforms" must never be printed**, because ChromIQ does not certify compliance. |
| K-h | Asked back to us: does any standard define a grey-balance metric? If none does, derive a reasonable one. *(Answered by research: two ISO tables define the metric and its limits. The numbers are not recorded here; see the rule above.)* |
| K-i | Cube corners exist whether the chart is RGB or CMYK. They express the colour of each extreme and are a clear indicator when one ink changes. |
| K-j | Already confirmed; he should not have to confirm it twice. |
| — | *"I will be less available for helping out on this, so Sebastian will have to answer more questions."* |

### 2026-09-09

* **K-d, expanded into a brief.** A table comparing every report type side by
  side: what each contains, section by section, with a short summary of each,
  drawn from a study of the standards named and of industry practice, plus how
  often each should be run. Each type needs a definition of what it is for and
  when, a dropdown name a user understands without help, and help text that
  spells it out. The names should signal which types belong to a formal
  workflow against a standard.
* **The simplest type, specified outright:** one page, a title, a section on how
  to read the numbers, no graphs, sixteen in-gamut example colours plus the cube
  corners and greys each with its accuracy number, then average, maximum and
  95th percentile across all measurements with pass or fail against the
  threshold for each. The report being small does not mean the chart must be: a
  48 or 84 patch verification chart is fine.
* **12b answered.** Showing INFO on a measurement report for a profile run is
  fine, because a profile run is not a verification run and often will not sit
  inside the accuracy thresholds. **The report must say so in its own text.**
* **Report type names (issue question 19).** *"I would say we should use the
  names supplied for testing. This may be changed later. Standards number is
  fine as part of the name."*
* **Two ISO-based types must be able to PASS.** *"It is also not acceptable that
  Validation print check (ISO 12647-8) and Contract proof check (ISO 12647-7)
  cannot give PASS."* This is blocked on the permission above, not on us.

### 2026-09-10 (the chart note and the page edges)

* **"Text distance from edge" governs every side, and it is a LIMIT.**
  *"Right says 5.8 mm but text goes to the edge almost. … Like the left and top
  labels, I think the text needs to stay within the default 'Text distance from
  edge' settings in preferences chart layout. For all sides, for Guided mode.
  Not a hardwired margin."* And, on what happens when the room runs out:
  *"the labels respect the 'Text distance from edge' settings, even if the
  margins defined make the patch area overlap with the text. Then the user needs
  to adjust the margins."*
* **The note sits beside the patch block, not out at the paper edge.**
  *"should the text move closer to the patch area edge but still leave 2 pixels
  space/gap, so that it is not going towards the edge?"*

Both are implemented for the right-margin chart note in
`workflow/tiff_metadata.py::_stamp_one`, which was the only side of the four
that did not read the setting at all. Measured on Knut's own 130x180 mm card
with the box on 4.0 mm: the note ended **1.78 mm** from the paper edge and left
**2.67 mm** of empty paper on the patch side; it now ends **4.06 mm** from the
edge and starts **1.27 mm** from the patch block.

**What the ruling costs, counted rather than assumed.** Twenty-two
configurations were built twice, once through each version of the stamper, and
the note measured against an unstamped control of the same sheet. **All 22
printed a note before; 18 do after.** The four that stop are the ones where the
paper left between the patch block and the reserve is under 0.93 mm, which is
narrower than a line at the 9 px legibility floor:

| configuration | right margin | Clip | note to the paper edge, before |
|---|---|---|---|
| A4 i1, clip band on the RIGHT | 6.0 mm | 4.0 mm | 0.76 mm |
| A4 i1, right margin 3 mm | 3.0 mm | 4.0 mm | 0.76 mm |
| A4 i1, Clip = 8 mm | 6.0 mm | 8.0 mm | 2.12 mm |
| 130x180 with the i1Pro | 6.0 mm | 4.0 mm | 1.14 mm |

Each of those four was printing INSIDE the distance the user asked to keep
clear, which is the fault Knut reported.

> **SUPERSEDED THE SAME EVENING. The four do print, over the patches.** See
> section 2c: dropping them is the one outcome the ruling forbids. The table
> above is kept because 4.2.3 shipped that way and the next release note has to
> say what changed.

---

## 2c. 2026-09-10, later: text on any of the four sides is NEVER dropped

This corrects what shipped in 4.2.3 that afternoon, and it makes 4.2.3's
behaviour wrong rather than incomplete. His words:

> *"The release note for 4.2.3 says 'Where the margin is too narrow to keep that
> distance, the note is left off.' This is not the feature we have designed […]
> For the right margin, the text must still be visible, even if the patch area
> overlaps on the right Run Chart Notes text. Else the user will not notice that
> it is silently dropped, like you now do. The user must be given the chance to
> see that something is wrong, and then adjust the margins to place the patch
> area further in on the paper, so that the chart notes can be visible.*
>
> *For the Strip labels, we previously designed a warning message that should
> come (in the message field in Measured from Preview frame) if the text is
> overlapping with the patch area due to the margins. This should also be
> implemented for text defined for the right margin, when Run Chart Notes are
> defined or "Stamp settings used on the chart" is selected, or when Clip border
> content is defined (for either left or right side) and also for the bottom
> margin, when sheet text (custom text field) is defined. They should all behave
> the same way."*

### The rule

1. **"Text distance from edge" sets the distance from the paper edge on all four
   sides**, whatever text is defined for that side. For the strip labels it may
   additionally be moved by "Label offset" under "Strip letters only".
2. **The margins decide where the patch area lands.** That holds for the ChromIQ
   layout engine and for "Prioritise chart area". For printtarg layout, or
   "Prioritise patch size", the patch area may instead be moved as a block,
   because there the margins are measured after the patches are generated rather
   than being the starting position.
3. **If the patch area overlaps the text on any side, that is ALLOWED.** The
   text is still drawn and still shown on screen.
4. **And it is warned about, in red, in the message field of the "Measured from
   Preview" frame**, so the user can correct the margins or the text distance
   and make it line up.

### Where it is built

| side | text | who draws it | who warns |
|---|---|---|---|
| top | strip letters | `layout_engine/raster.py` (band placed by `geometry.placement`) | `tab_chart.py::_engine_text_notes` |
| right | run chart notes, stamped settings | `tiff_metadata.py::_stamp_one` | the same |
| bottom | sheet text (custom field), settings stamp | `layout_engine/raster.py` | the same |
| left / right | clip border content | `layout_engine/geometry.py::clip_area_mm` | the same |

The four predicates are one law in `workflow/text_edge_fit.py`, and
`tiff_metadata.py` takes its legibility floor from that module rather than
keeping a copy, because the panel PREDICTS what the stamper will do and the
prediction is only true while both read the same number.

### Three things measured while building it, which are not in his words

* **The clip border's content cannot overlap the patch area today.**
  `layout_engine/instruments.py` raises the clip-side margin to the band's width
  (`ml = max(ml, lbord + border)`), so the band ends exactly where the first
  patch column begins. The check the ruling asks for is implemented and asked on
  every chart; it correctly stays silent. It is kept because the day that raise
  changes is the day the user needs to be told.
* **The chart note is judged on the MEASURED right margin, not the typed one.**
  "Right" says where the patch area is allowed to start; the note has to fit
  between the paper edge and where the block actually ends. Measured on a
  120-patch A4 i1 chart with the right margin typed at 3 mm: 151.1 mm of white
  paper on the right. Judging by the typed figure would have warned there.
* **One collision the ruling does not settle: the note against the user's own
  clip content.** With a clip border on the right, the note and the band both
  want the sliver at the paper's edge. The ruling sanctions the note against the
  PATCH AREA and says nothing about the note against text the user wrote, so the
  band keeps the edge and the note moves inward over the patches, where the
  ruling does allow it, and the panel says so. **Flagged for Knut**: if he would
  rather the note printed on the band, that is a one-line change.

### 2c-i. OPEN, and Knut's or Basti's call: "Clip" moves the RIGHT edge too

Found in Knut's own log of 2026-09-10 (16:07:19, four lines, one per page of his
100x150 chart on 4.2.3) and reported here rather than fixed, because the answer
is a design choice with no obvious winner.

**The facts, measured.**

* The right-edge chart note reads `text_edge_clip_mm`
  (`workflow/chart_creator.py:1735`) on every chart, whichever side the clip
  border is on. His preset has `clip_side: left`.
* The three spin boxes in that row are labelled **T**, **B** and **Clip**
  (`ui/dialogs/layout_options_panel.py:1982`). **There is no box for the right
  edge.** It borrows the clip band's distance.
* So the advice printed in 4.2.3's log, and in the new on-screen warning, tells
  the user to change "Clip" to move text on the opposite side of the paper.
* **It works, which is the trap.** He lowered Clip from 4.0 to 2.0, the note
  appeared, and he sent the corrected preset. The control is real and the advice
  is effective; only the NAME is wrong.
* The tooltip on that row said "Clip = the clip-border / notes band and the row
  indicator labels down the left" and did not mention the note at all, so the
  help was untrue as well as the label being unclear. **That half is fixed**:
  the tooltip now names all three things the box governs and says outright that
  there is no separate box for the right edge.

**Nothing about which VALUE that edge reads has changed**, then or now, so
Knut's 2.0 still does exactly what it did. Under this ruling it is no longer the
difference between a note and no note; it is the difference between a note
printed clear of the patches and a note printed over them with a red warning. It
is still the right setting for that card and he should keep it.

**The three ways out, and what each costs.**

| | what it does | cost |
|---|---|---|
| **A. Give the right edge its own box** ("R"), defaulting to whatever `text_edge_clip_mm` holds | says what it means, and lets the two side margins differ | a new recipe field, a migration, and every preset gains a value; existing charts unchanged if the default is carried |
| **B. Rename the box** to something that covers all three uses ("Sides") and reword the tooltip | no migration, no new state, the meaning stops being wrong | the two side margins can still never differ, and "Clip" is a name users and presets know |
| **C. Leave both, correct only the help** | free | the label still names one of the box's three jobs |

**Recommendation: A, with the default carried from `text_edge_clip_mm`**, so no
existing chart or preset moves and nobody has to re-derive a value. B is the
cheap answer and is defensible. C is what is built today, and it is the least
that had to happen; it is not the answer.

---

## 2b. Open, and needing Knut's ruling: the top labels do the OPPOSITE

**He cited the top strip labels as the behaviour to copy, and they do not behave
that way.** The specification and the code agree with each other and both
disagree with his description, so this is reported rather than changed.

* **Top (strip labels).** `workflow/layout_engine/geometry.py:399` computes
  `_ideal_top = g.text_edge_top_mm + g.strip_indicator_gap` and then
  `_leader_top = max(0.0, min(_ideal_top, g.margin_t - _lab_h))`. The comment
  above it states the rule outright: when the top margin is too small the label
  *"slides UP toward the page edge (encroaching the 4 mm text-edge if it must)
  instead of overlapping the patch block"*. The distance is an **ideal**, given
  up to protect the patch area, and `ui/tabs/tab_chart.py:18527` fires
  *"Top margin is too small for the strip labels, they overflow toward the page
  edge."* The comment attributes the design to Knut himself (#93).
* **Left (row labels).** The opposite, and it is what he described:
  `docs/design/row_label_geometry.md` R1.3, *"The labels can never be closer to
  the edge than the floor; the margin is raised instead."*
* **Bottom (sheet text).** The distance is reserved outright,
  `workflow/layout_engine/raster.py:365` and `:1727`.

So of the four sides, two hold the distance as a limit (left, bottom), one gives
it up to save the patch area (top), and the fourth, the chart note on the right,
did not read it at all until now and has been built to the LEFT edge's rule.
`row_label_geometry.md` §R2 claims the left rule is *"the mirror image of what
`geometry.py` already does for the strip labels"*, and on this point it is not:
the left buys its guarantee by raising the margin and the top has no equivalent.

**The question for Knut, and it is his to answer, not ours:** should the top
strip labels change to hold the distance and let a collision with the patch area
show, as he has just described? That is a change to shipped behaviour he is
recorded as having asked for, on a chart that prints correctly today, so it is
not being made on our own judgement.

> **STILL OPEN AFTER THE 2026-09-10 RULING, and deliberately so.** Section 2c
> settles that text is never DROPPED and that all four sides WARN the same way,
> and both halves are now built for all four. It does not settle this, and his
> wording suggests he believes the strip labels already overlap the patch area
> (*"if the text is overlapping with the patch area due to the margins"*) when
> in fact they slide toward the page edge instead. Changing the clamp at
> `geometry.py:400` would move ink on every area-first chart, including every
> shipped preset, so it is left exactly as it is and asked again.

---

---

## 3. Basti's rulings

* Everything not related to the report ships as a stable release; the report
  work rides on top of it as a beta. Merge, never rebase, so the report work
  stays discardable.
* 2026-09-10: the CR30 honeycomb is turned in **Guided** as well, so every user
  gets straight strips without knowing the option exists. No new control in
  Guided: ticking "Hexagon patches" is the only action.
* 2026-09-10: the CR30 gets a **5 mm** margin in Guided, where the other
  instruments share 6 mm. *"in guided the user can't influence the margin but i
  think it is ok if you set it to 5 for this."*
* The ISO rule in §1.

---

## 3b. Basti's answers to the decision sheet, 2026-09-10

He answered all eight on the sheet he was given. Recorded verbatim in substance,
because several of them close questions that were open for days.

| # | Question | His answer |
|---|---|---|
| Money | Buy ISO 12647-7 and -8 now? | **Agreed** with the recommendation: not now. A purchase is a reading licence and does not move the permission. |
| 1 | Ask GitHub Support to purge the superseded commit? | **No.** *"the risk seems low and you seemingly need to actively look for it."* |
| 2 | The ISO limits in the issue's opening post, which Knut wrote | **Leave them.** *"he posted this on my repo so it is his fault not mine."* |
| 3 | Send the letter to the national standards body? | **ALREADY SENT.** *"i already sent the message you drafted."* |
| 4 | May ChromIQ name a standard and cite a clause? | **Yes.** Names and clause citations stay; only the VALUES stay out. |
| 5 | Ship four report types now or wait for six? | **Four now**, and tell Knut why the other two are absent. |
| 6 | Tell Knut the two ISO types can never read PASS? | **Yes, we tell him**, on the issue, in his terms. |
| 7 | Buy ISO/TS 15311-1, and ask APTech about CGATS TR 016? | **Ask rather than buy**, and he wants the follow-up letters drafted, built on the conversations already had, and challenged before he sends them. |
| 8 | Clean 266 em dashes in twelve translated catalogues now? | **Later**, with the next full release, where translations are reviewed anyway. |

**The one that changes a standing fact: the ISO request is no longer unsent.**
Section 1 said a letter was "drafted, reviewed three times and not yet sent". It
has been sent. Nothing else about the ISO rule changes: no value goes into the
code, the repository or a release until an answer arrives in writing.

**And two obligations follow from answers 6 and 7.** Knut is owed an explanation,
on the issue, of why the two ISO report types cannot read PASS even after a
licence, because that is physics rather than paperwork. And the follow-up
letters have to be written against the actual correspondence and challenged
before they go anywhere.

---

## 4. What is NOT built

None of the report work described above is implemented beyond what shipped in
4.3.0 beta 1. The six report types, their names and help text, the one-page
summary, the grey-balance numbers and the short verdict word all exist as design
only. The open questions and their recommendations are on the issue, in the
comment of 2026-09-09, with an index saying which ones only the owner can answer.

---

## 5. Open, and deliberately not fixed for 4.2.2

**A run's FIRST visit still files the tab's settings into it.** Selecting a run
that has never stored anything writes about forty rows of the tab's current
state into its `meta.json`, before that run's own chart has been shown, so the
panel and the run's record can disagree. Measured on six visits of six.

It is a RECORD fault, not a printing one. No sheet changes, the preference the
app actually builds from is never wrong, and nothing a user typed is lost: a
reviewer measured that an edit survives leaving by another run, by a tab change,
by the main button and by quitting.

The mechanism, measured rather than assumed: `controller.changed` carries two
slots. The main window's loader runs first and re-points the tab's store at the
INCOMING run; the tab's own handler then writes what it believes is the outgoing
one. They are sequential, not nested, so a re-entrancy flag cannot see it, and
the tab is pointed at the current target the moment the controller is handed to
it, so the first selection finds itself "leaving" a run it has never displayed.

Two attempts to fix it inside that handler each broke the project's own
acceptance driver, once by losing an edit when there is no main window and once
by writing the wrong instrument. It is therefore left alone under a release
rather than rushed. The fix belongs where the two slots are ordered, not inside
the handler: either the loader must not re-point the store before the writer has
run, or the tab must record which targets it has actually SHOWN and file only
those. §4 S9 is the rule to hold it against, since being pointed at a target is
not using it.

~~**A note with no room left is still dropped without a word ON SCREEN.**~~
**CLOSED 2026-09-10 by the ruling in section 2c.** The note is no longer dropped
at all: it is printed over the patches, and the collision is named in red in the
message field of the "Measured from Preview" frame. The count of configurations
that print a note goes back to 22 of 22, and past it, because a sheet with no
white right margin whatever is now stamped too.

**A note that will not fit a narrow clip band is dropped without a word.**
With the clip border on the right and a band of 10 or 14 mm, three of ten
content modes leave no run of blank paper wide enough to write in, so no note is
printed and nothing on screen or in the log says so. The three are a notes form
at 10 mm, a notes form at 14 mm, and three lines of custom text at 10 mm.

> **PART of this is closed by section 2c.** The RIGHT-margin note in those three
> configurations now prints over the patches with a warning. What is not closed
> is the clip band's own CONTENT being too cramped to render: that is the notes
> form running out of band, not the note running out of margin, and it is a
> different fault in `layout_engine/raster.py::_render_notes_strip`.

Measured against the pre-work control, all three printed nothing at 4.2.0 as
well, so this is not a regression and not a blocker for 4.2.2. The other seven
print, and across the twenty ordinary clip settings nineteen print in the same
columns 4.2.0 chose, with none of the user's own lines under the note and none
destroyed.

What is missing is the sentence, not the placement. A user who asks for a note
and gets a blank margin has no way to learn that the band they chose is too
narrow. That text is a §M catalogue job and goes to §M-PROPOSED first, so it is
not written into a tab under a release.

---

## 2d. ⏳ Awaiting confirmation — 2026-09-11: shrinking text has a FLOOR

**Confirmed by:** *nobody yet.*

Knut, testing 4.2.5 on his own CR30 hex chart (`testHex`, from the two test
projects he attached):

> *"if the Chart Notes are specified, or "Stamp settings used on the chart"
> checkbox is ON, and the right margin is 6mm, and the "Text distance from edge"
> Clip-setting is 4mm, then the text is reduced to a mini-sized font almost not
> readable, instead of warning of the text not having room to fit, like it was
> done for the strip labels. The shrinking of the text should have a lower limit
> so the shrinking stops and the warning comes instead. I suggest a font size
> limit of 8pt (if the Sheet text frame size parameter is set to auto). If the
> Sheet text frame size parameter is set to a value, no shrinking should happen
> and the warning instead shown […] The Sheet text frame Font and Size should be
> used for the Run Chart Notes text and the "Stamp settings used on the chart"
> checkbox, so that the text is controllable."*

and, for the clip border's own content:

> *"there should be a font size minimum limit before the clip-border text stops
> shrinking (suggest 8pt here too, when the size setting is auto under
> Clip-border content frame) […] Manually setting size below 8pt should be
> working fine also. It makes sense that only the Auto size setting allows
> automatic shrinking of the text. This should apply to Sheet Text frame also."*

### The rule as built

1. ~~**8 pt is the floor for AUTOMATIC shrinking**~~ **SEVEN, from
   2026-09-11T21:23:10Z. See section 2e.** The floor is one constant on both
   the chart note / stamped settings down the right edge and the clip border's
   own text: `workflow/text_edge_fit.py::AUTO_SHRINK_FLOOR_PT`, read by the
   renderer, the stamper and the panel so no two of them can disagree.
2. **Only "auto" shrinks.** A size typed into the Sheet text frame's Size, or
   into the Clip-border content frame's Size, is the size that is printed, and
   nothing steps it down. A size below 8 pt is honoured.
3. **The Sheet text frame's Font and Size govern the right-edge text**: the run's
   Chart Notes and "Stamp settings used on the chart". The help for all four
   controls says so.
4. **When the text no longer fits at its floor or its typed size it is still
   printed** (rule 3 of section 2c is untouched) and the "Measured from Preview"
   message field says so in red, naming how much more right margin is needed at
   that size.

### What the floor replaced, measured

Both floors were floors on the RASTER rather than on paper. The note's was
**9 pixels**, which is 3.24 pt at 200 dpi and 1.08 pt at 600; the clip text's was
**8 pixels**, 2.88 pt and 0.96 pt. Driven on screen through the real window
against Knut's own `testHex` at his own numbers (right margin 6.0 mm, Clip
4.0 mm, notes plus stamp on), by `scripts/drive_182_text_shrink_floor.py`:

| | before | after |
|---|---|---|
| the note's ink across the sheet | 2.29 mm (**6.5 pt**) | 2.79 mm (**7.9 pt**, the floor) |
| typing 12 pt into the Sheet text Size | **no effect at all**, 2.29 mm | 4.19 mm (**11.9 pt**) |
| the red warning under the preview | **nothing** | named, with the millimetres |

### Two corrections to messages that were WRONG, not merely unclear

* **"Neither the right margin nor “Clip” can free room here" is false**, and Knut
  demonstrated it: *"The Right margin is here overruled by the Clip-border width.
  […] If clip-border width is kept at 24mm and right margin is increased to be
  bigger than this, then that should free more room in the right margin area,
  which it does."* The message now says which side of the band the margin is on
  and names the millimetre figure that crosses it. The *"or leave it and read
  them over the patches"* clause is gone with it: at 6.5 pt there was nothing to
  read.
* **A chart with NO clip border was told it had one.** `_clip_zone` is
  `lbord + border`, and a CM/A4 recipe with the clip border off still reports
  `lbord 0.0, border 6.0`, so a no-border chart with a tight right margin read
  *"they share that edge with the clip border … the border takes the outer
  6.0 mm"* and was advised to move a band that does not exist. The predicate now
  asks `lbord > 0`.

### ~~🔴 ONE PART IS NOT BUILT~~ ANSWERED 2026-09-11, AND THE SPECIFICATION IS WHAT CHANGED

Knut also asked, for the clip-border text at its floor, that it be

> *"pushed towards the right until it passes the Text distance from edge Clip
> setting, which then should give a warning message in red text again."*

That was held back because **rule 1 of section 2c says the opposite**, and it is
his own ruling: *"the text needs to stay within the default 'Text distance from
edge' settings […] For all sides"*. The question was put to him as *"should the
text be allowed to print closer to the paper edge than 'Text distance from edge'
asks, or should it stay inside that distance and simply be warned about?"* and
he answered it (#182, 2026-09-11T21:23:10Z):

> *"Yes, allow to print closer to the paper edge than "Text distance from edge"
> asks, but warn about it, just as previously defined, so that user knows to
> change margin, clip-border width or the "Text distance from edge"
> Clip-parameter, to fit text correctly against limits without getting a
> warning."*

**So rule 1 of section 2c is amended for the clip band's own text, by the person
whose rule it is.** The distance remains a limit everywhere else: the strip
letters, the bottom sheet text and the right-edge chart note are untouched, and
only the band that carries the user's own lines may spend its page-edge reserve
on them. What is built is in section 2f.

---

## 2e. ⏳ Awaiting confirmation — 2026-09-11, later: the floor is SEVEN point

**Confirmed by:** *nobody yet.*

Knut, #182, 2026-09-11T21:23:10Z, after running the 8 pt floor of section 2d
against the two-run `test` project he attached to that comment:

> *"Run 2 has a right side Chart Text, set in Sheet Text frame as size 7. (The
> auto setting shrunk the text to size 8, but that cause the long text to
> overflow the height of the page, so I changed to size 7). This showed me that
> the threshold of 8pt font size as the limit for when shrinking stops, when
> size is set to Auto, is too high. Please set the stop-shrinking threshold to
> 7, applicable for all the places font size is set and has Auto as a choice.
> The shrinking limit should be informed about in help text for the places where
> font size is set, like the clip-border content frame and the Sheet text
> frame."*

### The rule as built

1. **7 pt is the floor for AUTOMATIC shrinking.** One constant,
   `workflow/text_edge_fit.py::AUTO_SHRINK_FLOOR_PT`, read by the note stamper,
   the clip-text renderer and the panel that warns.
2. **Only "auto" shrinks**, unchanged from section 2d: a typed size is printed
   as typed, below 7 pt included.
3. **Each Size box that offers "auto" says what its limit is**, in its own ⓘ.

### What his sentence cost, measured on his own sheet

Driven through the real window against his `test` project by
`scripts/drive_182_sheet_text_fit.py`, and again straight through the fitter:
his run 2 note is **141 characters** on a 130 x 180 mm card at 200 dpi with
"Text distance from edge" → Clip at 4.0 mm.

| floor | characters printed | what is lost |
|---|---|---|
| 8 pt | **129 and an ellipsis** | `nagement: OFF`, the end of *"color management: OFF"* |
| **7 pt** | **141, the whole sentence** | nothing |

### The THIRD place a size box offers "auto", and it is NOT changed

His words are *"all the places font size is set and has Auto as a choice"*.
There are three such boxes, not two:

| box | what "auto" does | its floor before | now |
|---|---|---|---|
| **Sheet text** → Size (`chart_text_size_mm`), which also governs the right-edge chart note | shrinks the line to fit its margin | 8 pt | **7 pt** |
| **Clip-border content** → Size (`clip_text_size_mm`) | shrinks the lines to fit the band | 8 pt | **7 pt** |
| **Strip letters / row numbers** → Font Size (`indicator_size_mm`), and its Preferences twin | FITS the label to the strip width | 1.5 mm, about **4.25 pt** (`raster.INDICATOR_MIN_LEGIBLE_MM`) | **unchanged, and this is a question for him** |

**Why the third is left alone.** Raising that floor to 7 pt would make every
label 2.469 mm instead of 1.5 mm on the charts that reach it. Measured across
125 instrument/paper/grid combinations, **29 sit on that floor today**, and the
tightest of them have a row pitch of 2.73 to 3.48 mm, so a 2.469 mm row number
would be up to 90 % as tall as the row it names. That is the exact picture
Basti ruled against on 2026-09-01, and `raster.effective_row_label_size_mm`
carries his cap (85 % of the row pitch) because of it. **Two people's rulings
pull against each other here, so neither is applied on our own judgement.** The
help for that box now says what its limits are, which is the half of his
sentence that is not in dispute.

**The question for Knut, in what a user sees:** on a chart whose patches are
very small, the strip letters and row numbers today shrink down to about 4 pt so
they still fit between the patches. Should they instead stop at 7 pt like the
other text, even though a row number would then be nearly as tall as the row it
labels and the numbers would start to crowd each other?

### And the floor's other half, which was silent

A floor that stops the type getting smaller is only honest while the text it
leaves still fits the sheet. It did not: at 8 pt the fitter cut the tail off
Knut's note, marked it with an ellipsis, and said so in the log at INFO and
nowhere on screen. That is what he read as *"overflow the height of the page"*.
The "Measured from Preview" message field now says it, in red, with the number
of characters lost (`tiff_metadata.note_characters_lost`, which asks the fitter
itself rather than repeating its rule).

---

## 2f. ⏳ Awaiting confirmation — the clip band may cross its page-edge distance

**Confirmed by:** *nobody yet.*

This is what section 2d's open question became once Knut answered it. His words
are quoted there.

### The rule as built

1. **The clip band's TEXT may be printed closer to the paper edge than "Text
   distance from edge" → Clip asks**, and only that text: the strip letters, the
   bottom sheet text and the right-edge chart note keep the distance as a limit.
2. **It takes only what it needs.** A band that holds its lines inside the
   reserve keeps every millimetre of it; a band that does not gives up exactly
   the shortfall and no more, and never more than the whole reserve, so the
   content can reach the paper edge but never leave the paper.
   `workflow/text_edge_fit.py::clip_content_inset_mm`, read by
   `layout_engine/geometry.py::clip_area_mm`, by the renderer through it, and by
   the panel's live clip preview, so what is on screen is what is on the sheet.
3. **The push is ACROSS the band only.** The top and bottom of the sheet are a
   different edge with a different complaint and are untouched.
4. **It is warned about, in red, in the "Measured from Preview" message field**,
   naming how far past the distance the text went, where it now starts, and what
   to change.
5. **When even the whole band is too narrow**, the older "does not fit its band"
   warning is what is shown instead: the worse fact, not both.

### The levers the warning names, and the one it does not

He asked for three: *"change margin, clip-border width or the 'Text distance
from edge' Clip-parameter"*. Two of them move this text and one does not, so
the message names the two that work plus the Size box:

* **"Clip border width"**, which decides the band, so it decides everything here.
* **"Clip" under "Text distance from edge (mm)"**: lowering it to where the
  text already is removes the warning without moving a pixel, which is what he
  asked for, *"to fit text correctly against limits without getting a warning"*.
* **Size under "Clip-border content"**: a smaller typed size fits.
* **the clip-side MARGIN is not a lever for this text.**
  `instruments.geom_from_build_kwargs` RAISES that margin to the band
  (`mr = max(mr, clip_w)`); the band's width never depends on it, so typing a
  larger margin frees nothing here. Naming it would repeat the fault section 2c
  records being caught out by once already, where a message offered a lever
  that moved no ink.

**The question for Knut, in what a user sees:** when the clip border's text is
printed closer to the paper edge than you asked, is making the margin on that
side wider something you would expect to help? It does not today: the margin
follows the clip-border width rather than deciding it, so only the width, the
"Clip" distance and the text size change anything.

---

## 2g. ⏳ Awaiting confirmation — the warning counted the same reserve twice

**Confirmed by:** *nobody yet.*

Knut, #182, 2026-09-11T21:23:10Z, with two sheets from his own project:

> *"When the right margin is set to 32.5mm and clip-border width is 24mm, the
> text to the right of the patch area looks like this, without giving any margin
> warning text […] When changing the right margin to 32mm (keeping other
> settings as is), the margin warning came […] Both images show very good white
> empty space to the left and right of the chart notes text "test text". This
> means that the measurements and the warning text is wrong with its text. The
> warning says "... need 3.8mm at 10pt and have 3.6mm..." The test-32.5.tif
> image shows 39 pixels from the patch area right edge to the top of the "t" […]
> and 59px to the bottom […] this gives […] 4.95mm […] and […] 7.49mm […] And
> the warning says it only needs 3.8mm, and still gives a warning...."*

### Two numbers, two different questions

| | the question it answers | his sheet at 32.0 mm |
|---|---|---|
| the code's *"have 3.6 mm"* | how much paper is between the patch area and a reserve made of the clip band **with another "Text distance from edge" strip stacked on top of it** | 32.0 − 4.0 − 24.0 − 0.34 = **3.66 mm** |
| his ruler | how much paper is between the patch area's right edge and the **nearest ink on the other side** | 32.0 − 24.0 − 0.34 = **7.66 mm** |

**His is the question the warning asks, and the code's second strip is not on
the sheet:** the 4 mm "Clip" asks for lies INSIDE the band's own 24 mm.
`tiff_metadata._stamp_one` has always computed the note's outer limit as
`W - max(_pad, clip_band)`, a MAX, and the panel added the two instead.

### Measured on the sheet the app itself writes

Driven through the real window from his run 1 recipe, A4 at 200 dpi, Chart Notes
"test text" at a typed 10 pt:

| right margin | the note's ink, from the paper edge | from the patch edge | warning, before | warning, after |
|---|---|---|---|---|
| 32.5 mm | 25.15 to 27.56 mm | 4.94 to 7.35 mm | none | none |
| 32.0 mm | 25.15 to 27.56 mm | 4.44 to 6.85 mm | *"need 3.8 mm at 10 pt and have 3.6 mm"* | **none** |

His own measurement of the same sheet was 4.95 mm and 7.49 mm, so the two rulers
agree to a tenth of a millimetre. The note lands in the identical place at both
margins, which is why one of them warning and the other not was the tell.

### One sentence in the same message was false as well

With a clip border on that edge the message said the notes *"are printed
{Clip} mm in from the paper edge"*, which was 4.0 mm while the band holds them
at 24.0. It now says they start where the band ends. The same message offered
*"lower 'Clip'"* as one of three remedies, and while the band is the larger of
the two reserves that moves no ink; it is gone, and the two levers that do work
remain.
