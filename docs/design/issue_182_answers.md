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

Last updated 2026-09-12 (sections 2e to 2h; 2f rewritten after Knut withdrew the answer it was built on, 2h added from his edit of the same post).

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

> **2026-09-23: the permission question is answered in writing, the rule
> stands until the owner says go.** DIN's legal department: *"wenn Sie
> definitiv nur Werte aus der Norm verwenden – keine Bilder, keine Seiten,
> keine Texte, dann fällt das nicht unter Vervielfältigung."* The owner agreed
> it covers ISO 12647-7 and ISO 12647-8. Everything is prepared so that
> filling `data/compliance_sets/iso12647.json` is the only step left
> (`measurement_report_limits.md` §23, B8-851), and that step waits on his
> explicit go-ahead. Values only, even then: no wording, table, figure or page
> of either standard.

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

> **CLOSED (A15 of 5802027116; Knut, 2026-09-24, [5817809396](https://github.com/itsab1989/ChromIQ/issues/182#issuecomment-5817809396): "the recommended is
> accepted").** The four chart layout questions of 2026-09-10 and 2026-09-11
> that this section still carried as open are closed, settled by his later
> rulings (5649810914) and the beta 9 to beta 18 text placement rounds: the
> page note against the clip border text (§2, 2026-09-10, and §2c); "Clip"
> also moving the right edge (§2c-i); the top strip labels holding their
> distance from the edge (§2b, §2m-1); the 7 pt floor for strip letters and
> row numbers (§2d, §2e). Closing them records no new behaviour: the sections
> below keep their own status.

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

### 2c-i. ~~OPEN, and Knut's or Basti's call~~ CLOSED 2026-09-24 (Knut, 5817809396, A15): "Clip" moves the RIGHT edge too

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

## 2b. ~~Open, and needing Knut's ruling~~ SETTLED 2026-09-13: the top labels do the OPPOSITE

> **ANSWERED. See §2m-1.** Knut ruled on 2026-09-13, in comment 5649810914,
> that the strip labels hold their distance from the page edge and overlap the
> patch area where the top margin cannot hold them. The clamp described below
> is gone. This section is kept as the record of the question and of what the
> code did before, because the reversal is only readable next to it.

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

> **~~STILL OPEN AFTER THE 2026-09-10 RULING, and deliberately so.~~** Section
> 2c settles that text is never DROPPED and that all four sides WARN the same
> way, and both halves are now built for all four. It did not settle this, and
> his wording suggested he believed the strip labels already overlap the patch
> area (*"if the text is overlapping with the patch area due to the margins"*)
> when in fact they slid toward the page edge instead. Changing the clamp would
> move ink on every area-first chart, including every shipped preset, so it was
> left exactly as it was and asked again.
>
> **He answered on 2026-09-13 and his belief was his intention.** The clamp is
> removed, the ink did move on every area-first chart, and §2m-1 carries the
> measurement, the second fault it exposed (the patches were painting the
> letters out) and the price it leaves on the sheet.

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

### ~~🔴 ONE PART IS NOT BUILT~~ ASKED, ANSWERED, AND THE ANSWER WITHDRAWN

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

That answer was built the same evening, and **he withdrew it the next morning**
(#182, 2026-09-12), having read the commit note that said it reversed his own
rule:

> *"I was confused about the question, when you already know the text-edge
> distance is a limit on every side. The text on each of the 4 sides shall NOT
> cross the text-edge distance limit on every side. If the patch area with its
> margins are pushing against these limits, the text shall overlap in the other
> direction, inward and over the edges of the patch area instead. When this
> happens the warning texts shall appear, informing the user, as described and
> defined earlier."*

**So rule 1 of section 2c was never wrong and is not amended.** The question
asked him about a DIRECTION and he read it as being about whether to warn at
all. What was really open was where the text goes when it cannot fit, and the
answer is: inward, over the patch area. Section 2f records what is built; the
outward push existed for one evening and one commit (`0ca96864`) and is gone.

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

## 2f. ⏳ Awaiting confirmation — text that will not fit goes INWARD, over the patches

**Confirmed by:** *nobody yet.*

**This section replaces one that said the opposite, and the rule never changed;
the answer to a badly-worded question did.** Section 2d asked Knut whether the
clip-border text should be allowed to print closer to the paper edge than "Text
distance from edge" asks. On 2026-09-11T21:23:10Z he said yes, that was built,
and on 2026-09-12 he read the commit note and withdrew it:

> *"I was confused about the question, when you already know the text-edge
> distance is a limit on every side. The text on each of the 4 sides shall NOT
> cross the text-edge distance limit on every side. If the patch area with its
> margins are pushing against these limits, the text shall overlap in the other
> direction, inward and over the edges of the patch area instead. When this
> happens the warning texts shall appear, informing the user, as described and
> defined earlier."*

So **rule 1 of section 2c stands exactly as approved**, on all four sides, and
what this section records is the DIRECTION of the overflow, which is the thing
that was genuinely open.

### The rule as built

1. **The page-edge distance is never spent on text by a CALLER.**
   `workflow/text_edge_fit.py::clip_content_inset_mm` takes the band and the
   distance and nothing else, so nothing outside it can trade it away.

   > **AND IT IS NOT ABSOLUTE, WHICH THIS RULE SAID IT WAS.** The four-side
   > audit of 2026-09-12 measured the outermost clip ink at Clip 4.0 mm: a
   > 40 mm band prints it 5.33 mm from the paper edge, 26 mm at 5.08, **16 mm
   > at 3.81 and 12 mm at 2.79**. From about a 20 mm band down the ink is
   > closer to the edge than the box asks, because the function itself caps
   > the reserve at a fifth of the band (`CLIP_INSET_MAX_FRAC`) so a narrow
   > band is not eaten whole. Every band width Knut tests with, 8 to 16 mm, is
   > inside that range. Reproduced here on his own run 2.
   >
   > **Whether the CAP should stay is Knut's to rule and has been asked**: a
   > narrow band that keeps the full distance has almost nothing left for its
   > own text and would overhang inward a great deal further. **The MESSAGE was
   > not his to rule**, and it said the distance "is a limit and is never
   > crossed". It now names the reserve actually kept and where it came from:
   > *"the 12.0 mm band leaves 9.6 mm once 2.4 mm is kept clear at the paper
   > edge. That is “Clip” under “Text distance from edge (mm)”, or a fifth of
   > the band where that is less."*
2. **Text that will not fit inside it grows INWARD**, past the band and over
   the patch area, by exactly the shortfall:
   `text_edge_fit.clip_text_overhang_mm`, applied by
   `layout_engine/geometry.py::clip_area_mm`, which extends the content
   rectangle at its patch-side end only. The rectangle's page-edge end cannot
   move.
3. **The overflow is ACROSS the band only.** The top and bottom of the sheet
   are a different edge with a different complaint and are untouched.
4. **The block is anchored at the page-edge end whichever way the content
   reads.** See the finding below: "Flip 180°" used to move the anchor as well
   as the glyphs, so on a flipped band the text grew toward the paper edge.
5. **Nothing is cut any more.** See the second finding.
6. **The ink is composited, not pasted.** See the third finding, which is the
   one that would have done real damage.
7. **It is warned about, in red, in the "Measured from Preview" message field**,
   and the warning says whether the text actually reaches the patches.

### Three faults found while building it, all of them silent

**The clip text was CUT, with nothing said anywhere.** `raster._vtext` draws
into a canvas the width of the band's content rectangle and stacks the lines
from one end at their natural spacing, so a block taller than that rectangle had
its last lines fall outside the canvas and vanish. Measured on Knut's run 1 with
a 12 mm band: four lines need 11.9 mm, the rectangle gave them 9.6, and the
fourth line was printed nowhere, with nothing in the log and nothing on screen.
Growing the rectangle inward is also what fixes that.

**"Flip 180°" decided which end the text overflowed from.** `_vtext` stacks from
canvas zero and the caller turns the finished strip over, so the turn moved the
anchor with the glyphs. Of the four combinations of side and flip, **two grew
the block toward the paper edge**, and one of those two is Knut's own run 1 (a
right-hand band with "Flip 180" on). The flip now turns the content over without
choosing which end overflows (`render_clip_strip(anchor_far=...)`).

*What that costs, measured:* on a band where "auto" fills the width, nothing
moves at all. Driven on screen against his run 1 at its own 24 mm band, the ink
occupies columns 12 to 156 of the 157-pixel rectangle both before and after.
The change is visible only where there is slack, which means a band with a
**typed** clip-text size, and there the block moves to the other end of the
band. That is the behaviour his ruling asks for and it is a real change on those
charts.

**And pasting the overflow would have ERASED the patches, not printed on them.**
`render_clip_strip` returns an image with an OPAQUE WHITE background, and
`render_page` pasted it whole. Extending that rectangle over the patch area
without changing anything else would have wiped every patch under the band to
paper white, and a patch that reads as paper is built into the profile as paper.
The overhang is composited through an ink mask now, so only the glyphs land on
the patches and the colour shows through everywhere else.

### What the overlap costs a reading, measured and calculated

Driven on screen by `scripts/drive_182_sheet_text_fit.py` (step F4) against his
own run 1, with the clip content blanked as the control so every changed pixel
is the band's own ink, and the patch rectangles taken from
`geometry.patch_rects_px` rather than from ink detection:

| band | right margin | lines | patches inked | worst patch |
|---|---|---|---|---|
| 16 mm | 16 mm | 4 | 0 | fits, nothing warned |
| 12 mm | 32 mm | 4 | **0** | overflows the band onto clear paper |
| 12 mm | 12 mm | 4 | **17 of 374** | **2.4 %** covered |
| 10 mm | 10 mm | 8 | 6 of 374 | **22.0 %** covered |

The middle row is why the warning does not simply assert that patches are inked:
the text grows inward from the band's inner edge into whatever paper is there,
and the patch area begins at the clip-side margin. With a 12 mm band and a 32 mm
margin there are 17.7 mm of clear paper in between and not one patch is touched.

**What ink on a patch does to the reading taken from it.** A
spectrophotometer integrates over its aperture, so a patch of which a fraction
*f* is covered reads as the area mix of patch and ink. Taking black ink at 0 %
of paper luminance (the upper bound) and at 4 % (realistic for inkjet black on
photo paper), and ignoring optical dot gain, which makes the real error larger:

| coverage | paper white | mid grey | near black |
|---|---|---|---|
| 2.4 % (his 12 mm band) | ΔL\* 0.9 | ΔL\* 0.5 | ΔL\* 0.3 |
| 22 % (the worst the boxes allow) | **ΔL\* 8.9** | ΔL\* 5.4 | ΔL\* 2.5 |

ΔL\* is a lower bound on ΔE: the ink also pulls a\* and b\* toward neutral.

**And ChromIQ cannot tell.** `chartread` records what the instrument read;
`colprof` builds from that; nothing marks a contaminated patch, in the `.ti3` or
anywhere else. So a user who leaves the text over the patch area is choosing to
put ink on patches that will be measured and built into a profile, and the
warning says so in those words: *"those patches are measured with the ink on
them, so what the instrument reads there is the patch and the text together."*

Whether that is acceptable at 2.4 % and unacceptable at 22 % is a judgement for
Knut or Sebastian, not for us. **The question, in what a user sees:** when the
clip-border text is too wide for its band and prints over the edge of the patch
area, should ChromIQ let the chart be built at all, or should it refuse until
the band is wide enough? Today it builds it and says what is happening.

### A second audit finding: three content modes were told they overflow

The panel counted the clip text's lines for the **image** and **branding**
content modes as well as plain text, while `raster.render_page` produces an
overhang only for `"text"`: the other two scale to whatever band they are
given, so they have no floor to overflow from. Measured at a 12 mm band with
four lines: the text really does reach 13.46 mm, past the band, and branding
reaches 11.18 mm and never leaves it, and the panel told both of them that
2.3 mm was printed past the band. The predicate now asks the same question the
renderer asks. (Found by the four-side audit, 2026-09-12.)

### The levers the warning names

* **"Clip border width"**, set to the width that actually works. NOT the band
  plus the shortfall, which is the answer that looks obvious: the page-edge
  reserve is capped at a fifth of the band, so widening the band widens the
  reserve and gives part of it back. Measured on four lines at the floor with
  "Clip" at 4 mm, an 11.9 mm band overhangs by 2.3 and a 14.2 mm band is still
  0.4 mm short; 14.8 mm is the first that works
  (`text_edge_fit.clip_band_needed_mm`).
* **Size under "Clip-border content"**.
* **"Clip" under "Text distance from edge (mm)"**, offered ONLY when lowering it
  can finish the job. It buys back at most the whole reserve, so on a band
  narrower than the text needs it moves the overlap without removing it.
* **the clip-side MARGIN is not a lever.**
  `instruments.geom_from_build_kwargs` raises that margin to the band
  (`mr = max(mr, clip_w)`); the band's width never depends on it. It does
  decide whether the overflow reaches the patches, which the warning reports,
  but it cannot stop the overflow.

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

---

## 2h. ⏳ Awaiting confirmation — on the LEFT the text meets the ROW LABELS first

**Confirmed by:** *nobody yet.*

Knut added this to the post of 2026-09-12 after it was first answered, so §2f
was built without it:

> *"If clip-border text starts overlapping with the row labels (if enabled),
> the warning shall occur too, because the row labels are left of the patch
> area edges and any clip-border text that does not have space enough to fit
> between the clip text-edge distance setting and the patch area left edge or
> the row labels to its left, will overflow and overlap towards the row label
> or the left edge of the patch area (left margin). This situation must be
> caught."*

> *"When this is done correctly, I hope the behaviour and handling of text on
> all 4 sides is the ruled by same type of rules."*

### What is to the left, and in what order

Measured on his own run 2 through the real window
(`scripts/drive_182_sheet_text_fit.py`, step F5), a 12 mm left band with the
row indicators on:

| | mm from the page edge | what sets it, and what moves it |
|---|---|---|
| the clip content starts | 2.40 | `min(Clip, a fifth of the band)`. A LIMIT: nothing crosses it |
| the band's inner edge | 12.00 | "Clip border width" |
| the clip text reaches | 14.25 | the reserve plus what the lines take at their floor |
| the row labels' floor | 12.00 | `max(Clip, the band, the instrument's furniture)` |
| the label band's left edge | 13.00 | `floor + 1`, the RESERVATION |
| **the leftmost label INK** | **17.22** | the band's right edge less the widest number actually drawn |
| the label band ends | 22.43 | `floor + rlwi` |
| the patch area starts | 22.43 | the left margin, RAISED to hold the labels |

So it is a three-way squeeze and the labels come first: the patch area is
beyond them, and it is the left margin, which
`raster.apply_row_label_geometry` raises to `floor + band + 1` whatever the
user typed.

**WHICH CONTROL MOVES WHICH BOUNDARY**, measured over the whole range of each:

| control | the clip text's reach | the label ink |
|---|---|---|
| "Clip border width" | shortens the overflow | moves it one for one |
| Size under "Clip-border content" | shortens it | no effect |
| "Clip", below the band's width | shortens it | no effect |
| "Clip", above the band's width | no effect | moves it one for one |
| **left margin**, 12 to 45 mm | no effect | **no effect**: it is spent between the labels and the patches |
| **row-indicator Size**, 4 to 28 pt | no effect | moves it, **the wrong way**: 4 pt puts the ink at 13.86 mm and 28 pt at 18.94, so a SMALLER label sits CLOSER to the band |

**The last row is why the warning does not offer a smaller row-indicator
size.** It reads like a way to make room and it is the opposite; a user
following it would make the collision worse. A bigger one does clear the
labels, but it buys that with left margin to fix a problem in the clip text,
so the message offers "Clip" instead, which does the same thing directly.

### The rule as built

1. **The clip band's text is measured against whichever comes first**, the row
   labels or the patch area, both taken from the geometry that draws them
   (`geometry.row_label_area_mm`, `geom.margin_l`), never from arithmetic
   repeated in the panel.
2. **Both are reported when a deep overflow crosses both**, because they are
   different kinds of damage.
3. **Only a LEFT-hand band can reach the labels.** They are down the left; a
   right-hand band's text never mentions them.
4. **The remedies named are the ones that move ink**: the band's width, the
   Size under "Clip-border content", and "Clip" — lowered when that can remove
   the overflow outright, or RAISED above the band's width when the collision
   is with the labels, which moves them out of the way without moving the text.

### What it costs, and it is a different cost

Measured on the sheets the app wrote, the control being the same chart with
the clip text blanked:

| overlap | patches inked | label ink erased | the clip text fills, of the white inside a label's own box |
|---|---|---|---|
| 1.25 mm (12 mm band, 4 lines) | none | 0.00 % | **4.1 %** |
| 9.91 mm (16 mm band, 8 lines) | 2.96 mm of the patch area | 0.02 % | **21.7 %** |

**Nothing is erased**, which is the compositing §2f added doing its job: the row
labels are drawn onto the page BEFORE the clip strip is pasted, so an unmasked
paste would have rubbed them out.

**And the harm is legibility, not measurement.** A patch with ink on it is
still measured and returns a wrong number that reaches the profile; a row label
with ink on it is read by a person who then cannot find their row. At the
shallow overlap the numbers are still clear. At the deep one a fifth of the
space between the strokes carries another text. The warning says which kind it
is, in those terms, rather than reusing the patch wording.

**The question, in what a user sees:** when the clip-border text runs over the
row numbers, is a warning enough, or would you rather ChromIQ refused to build
until the band is wide enough? It builds it today and says what is happening.

### A fault found on the way: the panel warned about a band that is not drawn

`instruments` stores `lbord = clip_border_width - border`, and
`geometry.clip_area_mm` returns None when `lbord <= 0`, so **no clip content is
drawn at all** when the clip-border width does not exceed the patch border.
Measured on Knut's run 2, whose border is 10 mm, with the width set to 10: an
empty band on the sheet and a red warning saying its eight lines were printed
15.7 mm over the patches. The chart-note block already asked `lbord > 0` for
exactly this reason; the clip-content block did not, and now does.

**Flagged rather than changed:** whether a clip-border width equal to the patch
border SHOULD draw nothing is a separate question, and it is not ours. Today
the band collapses silently, and the only thing corrected here is the panel
claiming otherwise.

### One more thing the sheet shows, and it is not this round's to fix

On that same chart the row labels' floor comes out at 4.0 mm while the clip
band runs to 10 mm, because `apply_row_label_geometry` reads `lbord` and
`has_clip_border` rather than the typed width, and both say "no border" when
`lbord` is 0. So the labels are placed INSIDE a band that is not drawn.
`docs/design/row_label_geometry.md` §R2 already records the general case
("Nothing moves the patches or the clip-border content out of the labels'
way"), and this is that case reached by a different route. Nothing about it is
changed here.

---

## 2i. ⏳ Awaiting confirmation — the ChromIQ-CR30-hex-demo pack, now built

**Confirmed by:** *nobody yet.*

Knut answered the outstanding half of his own batch on 2026-09-11T22:04:19Z:

> *"Your question: 'Would you like the demo packs rebuilt so they look like a
> real scan and go all the way through, or should one of them keep tripping the
> end-of-scale warning deliberately, so you can see it happen?' My answer: Make
> both examples as part of the ChromIQ-CR30-hex-demo pack."*

What the ruling asks for, in the same terms:

1. a scan that looks like a real one and carries all the way through the
   alignment, the read and the report;
2. a second one, alongside it and inside the same pack, that keeps tripping the
   end-of-scale warning on purpose, so the warning can be seen happening.

`scripts/make_scan_align_demos*.py` builds the auto-align CHALLENGE set, which
is a different artefact: every case there exists to expose a shortcoming and
none of them is meant to go all the way through.

### CORRECTION, 2026-09-12 evening: this section described the pack as new, and it was not

**A pack of that name had already shipped, on v4.3.0-beta.3.** This section was
written after searching the repository, where no such generator existed, and
the releases were not searched. The conclusion drawn from that, that the pack
was being built for the first time, was wrong, and everything downstream of it
was written on a false premise.

What the beta.3 pack held, fetched from the release and read:

    chart/testHex.ti1 / .ti2 / .channels.json    648 patches, CR30 honeycomb,
                                                 A4, TWO pages
    chart/testHex.ti3                            a measurement, beside the chart
    chart/testHex_01.tif / _02.tif               both pages
    measurements/testHex.ti3                     the same measurement
    measurements/read2-noisy.ti3                 and with instrument noise
    measurements/read3-noisier.ti3               and with more, for averaging
    scan/testHex_01-simulated-scan.tif           one scan per page
    scan/testHex_02-simulated-scan.tif
    README.txt

So the build recorded below was not an addition. It was a **replacement that
lost four `.ti3` files, the second page of the chart, and the averaging demo**,
and it was reported as such the same day:

> *"the latest version of ChromIQ-CR30-hex-demo did not have all files as
> before. It is missing ti3 measurements, so I cannot use it to test the
> creation of CHT files, or use them in the scanner function. Add the files
> that previously was included, with real measurements etc."*

Both losses are structural rather than cosmetic. **Create scanner or camera
target** takes a chart's `.ti3` and nothing else will do
(`ui/dialogs/scanin_target_dialog.py`), so with none in the pack that window
cannot be driven at all and no `.cht` can be created from it. And a one-page
chart writes a single `.cht`, where two pages write one per page against a
single `.cie`, which is the branch worth testing.

**The lesson, which is the reason this correction is kept rather than the
section simply rewritten: a search of the repository is not a search of what
has shipped.** A generator that is not in the tree does not mean a pack that
has never existed, and a demo pack is a released artefact before it is a
script.

### Built, 2026-09-12, by `scripts/make_cr30_hex_demo.py`

The first build of the day, described below, was the regression. What the
generator builds now is the beta.3 pack rebuilt plus the two brightness states
the ruling asked for, so nothing from either pack is dropped:

    chart/testHex.ti1 / .ti2 / .channels.json    648 patches, flat-top CR30
                                                 honeycomb, A4, two pages
                                                 (396 and 252)
    chart/testHex_01.tif / _02.tif               both pages
    chart/testHex.ti3                            the clean measurement, filed
                                                 beside the chart, which is
                                                 where the scanner tools look
    measurements/read1-clean.ti3                 the same measurement
    measurements/read2-noisy.ti3                 the sheet read again with more
    measurements/read3-noisier.ti3               scanner speckle, for averaging
    scan/testHex_01-scan.tif / _02-scan.tif      the sheet, brightness OFF
    scan/testHex_01-scan-out-of-scale.tif        page 1 with it ON

The measurements are the part that changed in kind. The beta.3 files came from
`fakeread`, which restates the chart's own aim values through a reference
profile, so nothing that happens to a sheet or a scan can appear in them. Every
`.ti3` here is read off an actual image by an actual `scanin -c`, page 1 and
then page 2 accumulated onto it with `-ca`, so the turn, the optics, the
speckle and the sampling square averaging over a hexagon are all in the
numbers. The sheet is still a simulation and the pack's README says so.

`scanin -c` does not write `SAMPLE_LOC`, and the scanner-target window refuses
a measurement without it by name. The generator restores that column from the
chart's own `.ti2`, which is a fact about the chart rather than about the
measurement, and proves the join landed: every row's device values must still
equal the `.ti2`'s for the same `SAMPLE_ID`.

The chart itself is a real `targen` design laid out by ChromIQ's own engine.
The two page-1 scans are renderings of ONE simulated printed sheet, identical
in geometry, patch values, rotation, softening and speckle; the only difference
is that the second has had the sheet's own white lifted to 255, which is what a
scanner's automatic brightness does, taking every patch printed at the top of a
channel over the rail with it.

The generator refuses to write a pack whose three reads are not really a ladder
of noise. Measured against an independent rendering of the same sheet at the
same speckle: 0.0388, 0.1344, 0.2629. The obvious yardstick, a speckle-free
rendering, does NOT work and the first build proved it: a read at speckle 1.6
sits 0.240 from one and a read at 8.0 sits 0.282, so five times the speckle
moved the number by a sixth, because almost all of it is a fixed difference
between a rendering that was speckled and one that was not.

It also refuses a pack whose own `.ti3` will not drive the two windows. Both
are walked at build time, on the files about to be shipped: **Create scanner or
camera target** must write one `.cht` per page and a `.cie` covering all 648
patches, and the scanner path must then read every patch of both pages back
through them.

The generator measures its own two claims with the app's own code, from the
real `.ti3` a real `scanin` writes through the real per-page `.cht` the scanner
window prepares, and **refuses to write the pack** if they do not hold. At the
window's own 49 % sample area for this honeycomb:

| scan | patches on a rail | `scanner_max_clipped` |
|---|---|---|
| in range | **0.0 %** | 15 % |
| out of scale | **37.9 %** | 15 % |

Driven on screen, 2026-09-12 evening, on the rebuilt pack copied into an empty
folder with nothing else on disk. The login session's screen was LOCKED all
evening, so `scripts/onscreen_capture.py` refused a photograph rather than
saving wallpaper; the windows were opened by the real window server all the
same (platform plugin `cocoa`, no `QT_QPA_PLATFORM` override) and what is
recorded is the text they showed.

**Create scanner or camera target**, 640x630 on screen: the run button starts
disabled, picking `chart/testHex.ti3` turns the note to "Ready, recognition
files will be written as testHex.cht / .cie" and enables it, and pressing it
logs

    [OK] Wrote .../chart/testHex_01.cht
    [OK] Wrote .../chart/testHex_02.cht
    [OK] Wrote .../chart/testHex.cie
    Recognition files for 648 patches on 2 pages saved next to your chart.

**Build profile with scanner or camera**, 1240x928 on screen, offering all
three scenarios. Reading the pack's own scans back through the files the first
window had just written: page 1 gives 396 patches, page 2 gives 252, both at
`scanin` exit 0, at the window's own 49 % sample area for this honeycomb.

### The finding the pack turned up, which is NOT fixed here

**On the "Profile my printer from this scan" path, the end-of-scale check does
not look at the scan.** That path runs `scanin -c`, whose `.ti3` carries the
CHART's printer device values in `RGB_*` and the measurement in `XYZ_*`, and
`scan_read_check.inspect_read` counts a patch as clipped from `RGB_*`. So the
figure is a property of the chart's patch list and does not move with the scan
at all.

Measured on this pack, same chart, same corners, same window, one checkbox
apart:

| | Check alignment, box unticked | Check alignment, box ticked |
|---|---|---|
| in-range scan | no warning | ⚠ "Part of this scan has no colour left in it", 23 % |
| out-of-scale scan | ⚠ same warning, 38 % | ⚠ same warning, 23 % |

The two figures on the ticked path are identical because 23.3 % of the
648-patch chart's patches ask for 0 % or 100 % of a channel. `M_SCAN_DARK` is computed from the
same field and is equally blind there; `M_SCAN_FIT_UNSUPPORTED` reads `XYZ_*`
and is unaffected.

This also explains a report from the field on 2026-09-11, that 25 % of a page
full of patches "read at a rail" and that every one of them was a patch the
chart itself asks for at 0 % or 100 % of a channel. That was written down as an
observation about the scan. It is an observation about the check.

**Not fixed, deliberately.** The honest repair is a choice between spending a
second full `scanin` per page to read the scan properly on that path and simply
withholding the two scale findings there, which would drop a real guard for
genuinely blown-out scans. That is a change to shipped behaviour with a
trade-off in it, and it is not this pack's call to make. The pack is the
reproduction: two files that differ only in their scale, on which that path
reports the same number twice.

The pack's README says all of this in the reader's terms, and says it from the
numbers the build measured rather than from typed ones, so it corrects itself
if the app changes.

---

## 2j. Reported, not built — three findings of the fifth adversarial round

**Confirmed by:** *nobody yet.* Recorded so they are not re-found.

### The guide said the read-only ISO columns hold published values. They hold none.

Fixed the same hour and recorded here because of HOW it happened. The morning's
correction separated the two Custom columns, which do not hold a standard's
numbers, from the two read-only ones, and then said the read-only ones do. They
do not: `data/compliance_sets/iso12647.json` ships empty by design, pending the
licensing answer, so in every build ChromIQ distributes those two columns carry
**30 rows and not one number**. The fix for one half of a false sentence wrote
the identical falsehood onto the other half.

The guide now says what is true in both states: that is where those values go,
ChromIQ ships none of them, and the column cannot be chosen unless a licence
holder supplies them.

### The in-memory refresh is now NARROWER than the write beside it, on one field

`measurement_report_dialog._recalculate_run` stamps `report_type` onto a report
that has none while rewriting it on disk, and the in-memory refresh calls only
`stamp_verdict`. Driven: both dates' files read `t2_full_colour_check` while the
window's own records still read `None`. **No user-visible consequence was
found**, because `_report_type_now` asks the run and `generated_report_types`
re-reads disk. It is the same shape as the fault round four fixed, mirrored, and
the honest fix touches §10's open ruling about untyped reports, so nothing is
changed.

### A guard that is built and called by nobody

`core/measurement_target.verification_blocked_reason` returns `BLOCK_NEW_RUN`,
`BLOCK_NO_PROFILE` and `BLOCK_NO_CHART`. Every use of the function and of all
three constants outside its own module is a TEST. The Measure tab wrote its own
guard instead, which covers two of the three and not the new-run case, and the
Print tab asks nothing. So the state §3.1 of
`verification_printing_and_target.md` names in terms, *"'New run' selected: no
run, no profile, nothing to print"*, is enforced nowhere.

**It was not reachable through the window.** Switching the Profile-run box to
"New run" clears the Print tab: its pages go from two to none, the loaded chart
to none, and the colour route back to raw, because `_resolve_target_chart`
refuses to load a chart for a run that does not exist. The two tabs DO resolve
different runs from that selection, the Print tab taking the manifest's current
run and the Measure tab taking the run the loaded chart lives in, but with no
chart loaded the group is hidden and the answer is correct anyway. Recorded as a
latent hole with a dead guard beside it, not as a live fault.

---

## 2k. The same false sentence, in four places, corrected three times

**Confirmed by:** *nobody yet.* Written down because the PATTERN is the lesson,
not any one of the sentences.

A sentence about what a column named after a standard contains was wrong, was
corrected, and the correction was wrong in a new direction. Twice. The sixth
adversarial round then found two more copies of the original that neither
correction had reached.

| where | what it said | why it was false |
|---|---|---|
| the report's guide, v1 | "The columns named after a standard hold that standard's published tolerance values" | false of the two Custom columns: they start from ChromIQ's own numbers |
| the report's guide, v2 | "A read-only column named after a standard holds that standard's published tolerance values" | false of the read-only ones as ChromIQ ships: the data file is empty by design, 30 rows and 0 numbers |
| the report's guide, v3 | "those columns are empty, and cannot be chosen unless you hold the standard and supply its figures yourself" | false in the one state v2 was rewritten to cover. With figures supplied the columns carried 7 and 5 numbers and both appeared in the pulldown, while this paragraph, which is the same bytes in every state, still called them empty. And a run BOUND to an ISO set carries that choice to a machine holding no figures, where the set stays selectable |
| the Custom columns' blurb | "The starting numbers are ChromIQ's own, not ISO 12647-7:2016's" and "The two editable columns start from the same numbers" | true only while the file is empty. `factory_limits` takes ChromIQ's placeholders **only where the file supplied no number**, so with figures supplied custom-7 starts from the 12647-7 block and custom-8 from the 12647-8 block |
| `M_THRESHOLDS_NOT_CERTIFICATION` | the v1 sentence, verbatim | never touched by either correction, and `_notes_text` prints it two lines below its own correct sentence, so one panel said both things at once |
| the Report limits window's note | "the two Custom sets that start from them are empty" | true until 2026-09-12, when the Custom sets took a value on every measurable row. Its guard is "neither ISO set is selectable", so it was shown ONLY in the state where it had become false |

**The rule this produces, and it is general.** A sentence about what ChromIQ
holds must be true in the state ChromIQ ships AND in the state a licence holder
creates, because none of these strings is state-aware and none of them is going
to become so. Every one of them is now phrased as a condition rather than as a
state. `tests/test_a_custom_column_is_not_a_standards_column.py` drives both
states: it supplies figures through `CHROMIQ_COMPLIANCE_ISO_FILE` and requires
the Custom column to start from them, so the clause that says so cannot rot.

**And the second rule, which is the one that cost three attempts.** When a
sentence is found false, grep for its words before rewriting it. Two of the six
rows above are copies nobody looked for.

---

## 2m. ⏳ Awaiting confirmation — 2026-09-13: the three layout rulings, and the clamp is gone

**Confirmed by:** *nobody yet.*

Three answers arrived on 2026-09-13 and they settle §2b, which had been open
since 2026-09-10 and asked twice. They are quoted here from the comments
themselves, not from a summary, because Knut edits his posts and two of these
three are edits.

### 2m-1. The strip labels: the distance from the page edge is a LIMIT on this edge too

> **Comment 5649810914.** *"Regarding your question: "Which of the two do you
> want on a sheet where the top margin is too small?" Answer: I want the
> function that I specified, where the strip labels do not cross the "Text
> distance from edge" value (or the defined "Distance from page edge" +
> "Marker length" + 1.0mm, whichever is largest (if helper markers are
> enabled)), and then the text overlaps on top of the patch area top edge
> (according to top margin). This principle, which I specified to be the same
> for all sides (in their own direction overlapping towards the patch area edge
> for each side)"*

So all four sides now keep one law: the reserve is held, the patch area is
allowed to meet the text, and the collision is warned about rather than
designed away. The top was the last side that did the opposite.

**What was removed.** `workflow/layout_engine/geometry.py::placement` computed
`_leader_top = max(0.0, min(_ideal_top, g.margin_t - _lab_h))`. The `min` is
gone; the reserve is what is used.

**What it costs, measured on the SHIPPED CR30 A4 default and put in front of
him before he ruled.** Read back off the app's own `*.strips.json` sidecar, A4,
300 dpi, 345 patches: the label band's bottom moves from **83 px to 130 px**
while the first patch box starts at **91 px**, so every strip letter is printed
over the first row of hexagons. `tests/test_the_honeycomb_can_be_turned.py::
test_the_shipped_default_now_prints_the_letters_on_the_hexagons` pins that, and
the test that used to pin the opposite has been rewritten rather than deleted,
so the reversal is on the record.

**A second fault the ruling exposed, and it had to be fixed for the ruling to
mean anything.** The strip's own patches are painted AFTER its label, so the
moment the band was allowed to cross the margin the patches ERASED it: measured
on the same sheet, 39 px of every letter, a little under half of it, painted
out, and on a dark patch the letter would be gone altogether. That is the
silent drop his 2026-09-10 ruling forbids by name. `raster.render_pages` now
draws the letters and their underline onto a white overlay and composites the
INK alone at the end of the page, exactly as the clip strip and
`tiff_metadata`'s right-edge note already do, and appends their display-list
rows at the same point so the vector PDF paints them in the same order.
Measured after: the shortest letter is 55 px on the tight sheet and 55 px on a
roomy one, so nothing is lost.

**The one place the clamp deliberately stays**, and it is not the letters:
`geometry._top_reserve_for_a_turned_hex` moves the PATCH AREA down so a turned
honeycomb's raised strips do not climb into the label band on a sheet that has
the room. Carrying the unclamped reserve into it would push the patch block
down by the very amount his ruling says should show as an overlap, costing the
sheet patches at a margin the user set. Its comment says so.

### 2m-2. The clip band is vertically centred, and each end reads its own box

> **Comment 5649955254.** *"the clip band should be vertically centred between
> the T and B. So with T at 12 and B at 4 and A4 page hight, the band is
> centred between (0+T) and (297 - B) , which means between 12mm an 293mm.
> This is if helper markers are off. If helper makers are ON (with top/bottom
> ON), and if either helper markers are further in on the page than T or B,
> then "Distance from page edge" + "Marker length" + 1.0mm will be used for the
> text distance from edge parameter that is smaller."*
>
> *"The same vertical centring should be done for the right clip-border text
> (and the chart note and the third type of text too "Stamp settings used on
> the chart")"*

His four rows reduce to one rule per edge, `max(that edge's box, the markers'
reach)`, which is `text_edge_fit.edge_reserve_mm` and is what the other three
elements on those edges already use. `text_edge_fit.side_text_band_mm` is the
table; `geometry.clip_area_mm` uses it.

**This CORRECTS his earlier rule, and the correction is his own.** The rule it
replaces was *"page height minus T and minus B, OR page height minus (distance
x2 + length x2 + 2.0mm), whichever is smallest"*, applied as a SYMMETRIC inset.
That is right whenever T and B fall on the same side of the reserve and wrong
in the two mixed rows he has now written out. On his own example (A4, T = 12,
B = 4, markers at 4.0 + 2.0) the old rule gave a 281.0 mm band starting 8.0 mm
down; his rows ask for a 278.0 mm band starting 12.0 mm down. The height moved
by three millimetres and the anchor by four, and the anchor is the half a
reader could see: the band was centred on the middle of the sheet whatever T
and B said.

**The chart note and the settings stamp already comply**, and this was checked
rather than assumed. `tiff_metadata._stamp_one` places its strip at
`y0 = _pad_t` with `strip_h = H - _pad_t - _pad_b`, both supplied by
`chart_creator` from `text_edge_fit.edge_reserve_mm` for the top and bottom
edges, and `_render_rotated_line` centres the line along that strip. Those are
Knut's two bounds and his centring, built on 2026-09-12 for a different report
of his. Nothing was changed for them.

### 2m-3. The bottom line is horizontally centred, and the clip border is one of its bounds

> **Comment 5651269930, which is an EDIT of 5649955254 and supersedes its
> looser wording.** *"So the bottom text ("Stamp layout summary on the sheet")
> is horizontally centred between following (example uses A4 paper size,
> Portrait): Helper markers are off and Clip-border off: (0+Clip) and (210 -
> Clip); Helper markers are off and Clip-border ON (side=left) (also applies
> for Helper markers are on when Clip is larger than helper marker): (0+Clip-
> border width) and (210 - Clip); … Helper markers are on for sides and
> Clip-border ON (side=right): Clip is smaller than helper marker:
> (0+("Distance from page edge" + "Marker length" + 1.0mm)) and (210 -
> Clip-border width)"*

and his reason, from the post the edit replaced:

> *"the text added for the bottom line must be centred according to page width
> (or the side reserve width), so that text can equally expand to both sides if
> the text string length is increased."*

Six rows, two rules, and they are written once in
`text_edge_fit.bottom_text_bounds_mm`:

* the side with no clip border keeps `max(Clip, the markers' reach)`, which is
  his "whichever is larger" proviso in every row;
* the side with the clip border keeps the border's own width, because the band
  and the line share that strip of paper: since 2m-2 the band runs from the "T"
  bound to the "B" bound, so it reaches down across the bottom line's own row.

`raster.render_pages` centres EACH LINE on the midpoint of those two bounds
(the custom text and the settings stamp are different lengths, so centring the
pair as a block would leave the shorter one off centre), and the same figure is
what the "auto" size shrinks against and what the panel's width warning
reports.

### The one clause that is genuinely ambiguous, resolved conservatively and reported

Every row of his bottom-line table has the clip border WIDER than the reserve,
so the two readings agree. A border NARROWER than the reserve is a case he does
not cover, and taking his words literally there would let the line into a
reserve that is a limit on all four sides everywhere else. The bound is
therefore `max(border width, reserve)` on the border's side, which is exactly
his table wherever his table speaks. **If he means the border width to win even
when it is smaller than the reserve, this is the one line to change**
(`text_edge_fit.bottom_text_bounds_mm`).

### The messages that changed

The two "the strip letters are printed closer to the paper edge than you asked"
and "they do not fit above the patches" notices described the clamp and are
gone. In their place are two that describe the overlap and name whichever
reserve is actually binding, so the box the message offers is the box that
moves the ink. The panel now measures the DRAWN ink
(`Geom.label_ink_bottom_mm`, the renderer's own figure) rather than the
reserved band, which is 7.0 mm against 4.826 mm on a stock i1Pro A4 chart: at a
9 mm top margin the ink ends 8.83 mm down and clears the patches, and warning
there would have been the same cry-wolf message in a third costume.

**A wiring fault found while building it.** The panel handed
`strip_label_overlap` the already-maxed reserve where the function wants the
raw "T", because it computes the reserve itself in order to say WHICH of the
two won. That made `from_markers` compare `7.0 > 7.0`, so a sheet held by the
markers was blamed on "T" and the remedy offered would have moved no ink. The
function that came before it took the reserve, so the call site was right for
the old callee and wrong for the new one.


## 2n. ⏳ Awaiting confirmation — 2026-09-13: the six straight-strip presets ship, and the test that held them was wrong

**Knut's ruling, on beta 7:** *"all 6 profiles give no warnings at all. The A4
chart presets look good and work exactly as desinged. No overlap warnings...
show top=12.3mm and bottom = 6.9mm in Measured from Preview. All ok. Ship the
presets."*

They are shipped: six rows, three on A4 (450 / 900 / 1350 patches) and three on
US Letter (396 / 792 / 1188), all on one 18-column grid, registered as the
`straight=True` cut of the CR30 family. `KNUT_PRESETS` 143 to 149, built-in keys
154 to 160.

### The half-millimetre that held them for a day was never on the sheet

The three A4 charts were reported at Top 10.499 / Bottom 5.112 against the
11.0 / 6.0 their own recipe declares, so they appeared to accuse themselves and
were commented straight back out. Knut, on the same six as user presets, read
12.3 and 6.9 with no warning. Both numbers were produced honestly; only one came
from the app.

`test_no_builtin_preset_breaks_its_own_declared_margins` re-implemented
`margin_inspector.measure_from_engine` in a local helper, and the copy had
drifted. The shipped function asks `recipe_is_flat_top` which way the hexagons
point; the copy always took the vertical apex. A turned honeycomb's apexes point
sideways, so the copy moved 1.82 mm off the top and bottom and left 1.59 mm on
the left and right that the ink does not have. Fed the engine's own geometry the
shipped function answers **12.319 and 6.932**, which is Knut's reading to the
tenth, on all three. The helper now CALLS it.

Driven on screen, all six built-ins, real window: A4 T=12.319 B=6.932, Letter
T=15.748 B=10.287, no violations, no text notices, no overlap notices, "Margins:
OK" in green. Photographs in `~/Desktop/ChromIQ-proof-2026-09-13-straight`.

### And a real fault of the same shape, found by measuring them

"Patch width (in strip reading direction)" came off the slot rect's `w`. On an
upright honeycomb that IS the patch, because the flats are its left and right
sides and the column pitch is the same number. On a turned one the three come
apart:

    column pitch       w          9.398 mm    <- what the panel showed
    across the flats   h         10.922 mm    <- the patch
    across the points  w * 4/3   12.531 mm

The panel understated a 10.9 mm patch by 14 per cent on charts whose own names
say 11 mm, on the one readout that says whether a CR30's round head fits inside
a patch. Measured against the INK rather than the arithmetic, by rendering the
A4 450p chart at 600 dpi and flood-filling four separate hexagons out of the
page: every one is **12.573 mm across the points and 10.880 to 10.922 across the
flats**, against a slot width of 9.398. The number the panel used to print is
not a dimension of the patch at all. The report now carries the across-flats measure in both orientations:
it is the inscribed circle, the only span worth a single number, and nothing
upright moves. The "Chart layout information" panel beside the preview had it
right all along and separately, listing "Patch size (mm) 12.53x10.92" beside
"Column pitch (mm) 9.4".

**Naming.** His files spell it "Streight". The presets say "Straight", following
the app's own control ("Straight strips (turn the honeycomb 30 degrees)"). One
word to put back if he wants his spelling.

**One thing left open for Knut, and it is the label rather than the number.**
The row is called "Patch width (in strip reading direction)". Strips run down
the page, so read literally that is the patch's VERTICAL extent, and the row has
always carried a horizontal one on an upright chart. The number is now the
across-flats measure in both orientations, which is the inscribed circle and the
only span of a hexagon worth a single figure, but the label still says something
slightly different from what it shows. The "Chart layout information" panel
beside the preview avoids the question by printing both, "Patch size (mm)
12.53x10.92". Two ways out, and it is his call: rename the row, or print both
dimensions there too. Nothing was changed on the strength of a guess.

## 2o. ⏳ Awaiting confirmation — 2026-09-13: which PDF the strip-label rule was missing from

**Knut asked:** *"Which PDF export is this? from the Measurement Report? or any
other export? If the Measurement Report, I say we keep as is. Reports are
properly reviewed at later time and things may change."*

**It is not the report. It is the chart.** Create Chart's "Also export a PDF"
writes a vector sheet beside the TIFF from one display list, so the two are the
same chart in two forms, and the PDF is the file that goes to a RIP. His
keep-as-is therefore does not apply, and it was fixed.

A `vrect` display-list row is half-open, like a Python slice, and the PDF writer
takes `x1 - x0` by `y1 - y0` as the size. The helper markers emit half-open
rows. The three strip-label underlines wrote Pillow's inclusive box straight in.
Two emitters, two conventions, one consumer that cannot be right for both, so
every rule came out one pixel short in both dimensions.

Measured on a real export at 200 dpi with the rule at 0.10 mm: **1** zero-height
rectangle in `black` mode, **5** in `segments`, **18** in `cycle`. The rule is in
the TIFF and absent from the PDF. At 0.50 mm nothing vanished and every rule was
a quarter thin instead, 1.08 pt against the TIFF's 1.44. After the fix: no dead
rectangles in any mode, and 0.36 pt / 1.44 pt, exactly 1 px and 4 px at that
resolution.

## 2p. ⏳ Awaiting confirmation — 2026-09-13: the clip-text warning fires on the COLLISION, and §2f rule 7 is amended

**Knut, on beta 7,** testing the built-in ColorMunki A3-900p-2pages-Portrait at
a 24 mm right margin with the clip band narrowed from 24 mm to 18:

> *"the chart does not change at all and the clip-border text still fits
> perfectly (it did not move on page or overlap with anything). However, there
> is a red warning text. ... When there is space for the text due to the right
> margin being bigger than the clip-border width, should not the test pass
> without errors? Thus, if either right margin or clip-border width is higher
> than the needed height, it is ok."*

**He is right, and it is his own draft he is correcting.** §2f rule 7 said the
warning fires on the band overflow and reports separately whether the text
reaches the patches. That section is `⏳ Awaiting confirmation` and
`Confirmed by: nobody yet.`, so the ruling stands over it. **Rule 7 is amended:
the warning fires when, and only when, the text reaches something** — the row
indicator labels on a left-hand band, the patch area on either side. Leaving the
band onto clear paper is not a fault and is no longer reported.

### Measured before the change, on his own preset

One project name, one seed, clip 24.0 against clip 18.0, page 1 of 2:

| | value |
|---|---|
| pixels changed, of 7,735,073 | **3,364 (0.043 %)** |
| where they are, from the right page edge | 6.99 to 21.72 mm, which is the clip band's own text and nothing else |
| innermost clip ink to the first patch | **2.03 mm of clear paper, at BOTH settings** |

No patch, no margin, no label and no marker moved. The one pixel of difference
inside the text is the content rectangle being 17.000 mm wide instead of 16.944.

### And it does not silence the guard

Five combinations, each built and each photographed, before and after:

| band / right margin / clip size | before | after | what the sheet shows |
|---|---|---|---|
| 24 / 24 / 10 pt | silent | silent | ink ends 21.7, patches at 23.7 |
| **18 / 24 / 10 pt (his case)** | **warns** | **silent** | identical ink, patches at 23.7 |
| 12 / 12 / 10 pt | warns | **warns** | three lines printed across patches |
| 12 / 32 / 10 pt | **warns** | **silent** | 9.4 mm of clear paper beyond the text |
| 24 / 24 / 14 pt | warns | **warns** | ink runs unbroken into the patch block |

The proposed rule agrees with the ink in all five. A full 24 mm band with a
14 pt clip text still warns, because the text is too big for the paper it has.

### Two consequences for the wording

*"It reaches clear paper, so it lands on nothing"* is now unreachable and is
gone: a message that says nothing was hit is a message that should not have been
printed.

**On a right-hand band the margin is now a third lever**, which is Knut's own
sentence, so the message offers it: *"Raising “Right” under “Margins (mm)” past
{want} mm also clears it: the text still leaves the band, but the patches move
out of its way."* Down the LEFT it is not offered, and must not be: there the
left margin is raised for the row labels, so moving it moves them too and the
text meets them just the same (§2h rule 1 is untouched).

### One stale sentence found while reading §2f

§2f rule 1 and §2g still describe the page-edge reserve as capped at a fifth of
the band. That cap was removed from `clip_content_inset_mm` on 2026-09-12 on
Knut's own report, and the measurements above are consistent with no cap
("Clip" 4.0 with side markers gives a 7.0 mm reserve exactly). Those two
paragraphs are stale on that point.

## 2q. Reported and NOT built — 2026-09-13: the gap between the chart note and the clip text (K5)

**Knut:** *"When chart notes are printed on right side and/or 'Stamp settings
down the right edge' is ON, and the clip-border is on with defined custom text,
the gap between the chart notes text line and the beginning of the clip-border
text is a little too narrow, and not exactly the normal distance two text lines
would have for the set font size. It needs maybe a 1 pt gap more, or maybe 1mm."*

**He is right, it is measured, and it is NOT in this build.** The whole of it is
recorded here because the measuring is done and only the building is left.

### The leading is computed correctly and then discarded

`chart_creator.py` hands `_stamp_one` a `gap_mm` of `CLIP_LINE_SPACING x
pt_to_mm(max(clip floor, note floor))`, which is 4.236 mm at a 10 pt clip text.
Measured on the sheets the app wrote, in mm from the right page edge:

| clip size / note Size | leading passed in | note ink | white gap to the clip ink |
|---|---|---|---|
| 10 pt / auto | 4.236 | 24.003 to 26.289 | 2.286 |
| 14 pt / auto | 5.928 | 30.734 to 33.020 | 3.048 |
| 7 pt / auto | 2.964 | 18.796 to 21.082 | 1.778 |
| 10 pt / typed 12 pt | 5.076 | 24.130 to 28.067 | 2.413 |

In every case the note's ink starts within 0.06 mm of the clip content's reach:
the leading is not applied at all. What is missing is exactly
`(leading - the note's own ink thickness) / 2`, because the ink is butted
against the reach instead of centred in a line's slot: 0.95, 1.84, 0.32 and
0.57 mm predicted against 0.92, 1.80, 0.40 and 0.38 measured.

**So it is not "add 1 mm" and not "add 1 pt": it is "give the note the block's
next line slot".** Knut's "maybe 1 pt more, or maybe 1 mm" is the 0.92 mm this
comes to at his own 10 pt clip text.

### Underneath it, a second fault with the same cause

`_detect_writable_band` looks for the patch block by column ink density over the
whole page width, and a clip-border line passes the 0.30 threshold: on this
sheet the rightmost column at or over 0.30 is 7.62 mm from the paper edge,
inside the clip text, and the band's rule line runs at 0.86. So the search
window shrank to the 7.6 mm sliver outboard of the clip text, `strip_w` went
negative, and the re-placement branch put the note flush against the reach at
the 7 pt legibility floor with the gap never used. Two more consequences,
measured: **the note is printed at 7 pt on every one of these charts even where
there is room** (its ink 2.29 mm thick where 3.43 was free), and the log says
*"Right-edge stamp overlaps the patch block"* on sheets where it does not.

### Why it is not in this build

The three parts have to land together. Fixing the detector alone was tried and
measured here: the note is then sized correctly (3.429 mm of ink instead of
2.286, which is 10 pt instead of 7) and the white gap becomes **0.254 mm**,
worse than the 2.286 mm it replaced, because the intended packing path is wrong
too. `x0 = _right_limit - _gap_px - strip_w` measures the gap to the strip's
page-edge edge while `_render_rotated_line(anchor_px=...)` draws the ink at the
strip's patch side, so the realised white gap is `gap + (strip_w - anchor - ink)`
and can never be one leading.

Shipping half of it would make the gap he reported narrower, so the change is
held whole. The three parts, with the analyst's line numbers:

1. `tiff_metadata._detect_writable_band`, the `patch_cols` scan: look for the
   patch block inside `keep_out_px` only, on both sides.
2. `tiff_metadata._stamp_one`, the placement and the `_overlaps` re-placement:
   put the note in the slot `[_right_limit - _gap_px, _right_limit]`, centred in
   it, so a note on "auto" is sized to the leading and matches the clip text
   instead of shrinking to the floor.
3. `ui/tabs/tab_chart.py`'s `_note_keep_out`, which is
   `clip_text_reach_mm(...)` and would have to become `reach + gap`, or the red
   overlap warning goes quiet exactly when the note starts landing on patches.

**No specification covers this.** The rule exists only as Knut's sentence quoted
inside `_stamp_one` and `chart_creator`; nothing in `docs/design/` carries it,
so building it contradicts nothing and it should be written into §2 once the
placement is confirmed.

### And a third fault found in the same place, also not built

On a chart with the note, the stamp and a right-hand clip band, the note is
printed **on top of** the clip band's text. Measured, from the right page edge:
clip-border text ink 7.33 to 22.57 mm (about 43 pt of line), chart-note ink 6.98
to 9.52, **overlap 2.19 mm**. The cause is one function:
`text_edge_fit.clip_text_reach_mm` computes the keep-out from
`text_floor_pt(size_pt)`, which on "auto" is 7 pt and gives a reach of 6.96 mm,
while `raster._vtext` on "auto" GROWS the font to fill the band and drew that
line at about 43 pt reaching 22.57 mm. The keep-out under-predicts by 15.6 mm.
Getting it right means asking the renderer what size it actually chose, which is
a structural change to `render_clip_strip`, and it decides where printed ink
lands, so it is a round of its own.

## 2r. ⏳ Awaiting confirmation — 2026-09-13: "nobody recorded the printing" was read the other way, and CH-17 is his to confirm

**Knut**, loading `ChromIQ-Report-Limit-Demos`, project
`Report-Limits-Border-Conditions`:

> *"Why 'A sheet nobody recorded the printing of, so the grey rows keep their
> numbers and are shown for information'? Is that relevant? A measurement
> performed on a verification chart was obviously printed. This is a demo, so
> this might be wrong information. The Gray test thresholds exist, so they
> should not be INFO if the test can be performed."*

Two separate things, and only the first is ours.

### The sentence, which was ambiguous and is fixed

What is missing on that run is the RECORD OF HOW the sheet was printed, the
paper, ink and driver settings, not the fact of its printing. **The app's own
reason line has always said so**: *"how this sheet was printed is not recorded,
so this value is shown for information only"*. The DEMO PACK's run title did
not, and that is what he read. It now says *"A sheet whose printing condition
nobody wrote down"*, and the run's description spells out that it was printed
and measured like all the others.

### The rule, which is his

CH-17 makes the two grey-balance rows INFO when no printing condition is
recorded AND the reference is the chart's own design. The reasoning behind it:
graded in absolute Lab against a design aim, the PAPER'S OWN TINT lands in the
grey row, so a perfectly good print on a warm paper fails a row about the
printer. With a printing condition recorded there is a reference that already
carries the paper, and the row means what it says.

He is asking for the opposite: *"The Gray test thresholds exist, so they should
not be INFO if the test can be performed."* That is a real choice with a real
cost either way, and CH-17 lives in `measurement_report_limits.md`, which is a
DRAFT with every section awaiting confirmation, so it is his call and it has
been put to him. **Nothing about the rule was changed.**

## 2s. Knut's ruling of 2026-09-13, 16:38: the grey rows ARE graded, and a numbered note carries the caveat

He was asked, in §2r, which he would rather have on a sheet with no printing
condition recorded: the grey numbers with no verdict, as CH-17 has it, or a
verdict that includes the paper's own tint. His answer:

> *"the grey metric tests is not about the printer, it is about verifying that
> the profile created for a specific paper or process condition measures within
> set acceptable thresholds. The verdicts should be given, but a note can be
> given in a numbered list of notes, where a verdict is commented, for example
> regarding the tint of a paper and profile combination."*

**So CH-17 is overruled, and the shape of the replacement is his too.** The rows
are graded like every other row. Where the grading carries a caveat, the caveat
goes into a NUMBERED LIST OF NOTES beside the report, keyed to the verdict it
comments on, rather than being expressed by withholding the verdict.

That second half is a report feature that does not exist yet: there is no
numbered note list, and no mechanism for a row's verdict to carry a note
reference. It is a bigger change than deleting the CH-17 branch, and deleting
that branch WITHOUT the notes would leave a grey verdict on a warm paper with
nothing to explain it, which is the state he is trying to avoid.

**BUILT, 2026-09-13, both halves together.** The note list had to come first,
and it did: `measurement_report_limits.md` gains §12 (CH-30 to CH-33) and CH-17
is marked withdrawn in the same change.

* `row_values` no longer ungrades anything. The grey rows are judged like every
  other row and carry a note code instead.
* A **note** and a **reason** are now different fields with different meanings:
  a reason explains why a row has no verdict, a note comments a verdict that was
  given. Merging them is what produced the state Knut objected to.
* `numbered_notes` numbers them once for the whole document, in row order, one
  number per distinct note however many rows carry it. The verdict cell and the
  list ask the same function, so they cannot disagree about which note is
  note 1.
* A note dies with its verdict. The Printing record withholds every verdict, so
  it prints no notes.

Driven on screen on the border-conditions demo project, all three report types:
the run with a printing record reads COND and PASS with no note, the run without
one reads **PASS¹ PASS¹** with note 1 naming both rows, and the Printing record
reads INFO with no note and no heading. A report SAVED under CH-17 keeps its
INFO, which is the rule that a run keeps its verdicts working as written.

The pack's own description of that run said the grey rows "keep their numbers
and are shown for information", which the ruling made false; it now says they
are judged with a numbered note against them.

## 2t. ⏳ Awaiting confirmation — 2026-09-13: the note marker is `1)`, and one question back about the profiling sheet

Knut, 2026-09-13, 17:20:

> The notes should also be numbered in the report, and the verdict line in a
> table which applies to a note should snow a number as a reference to the note
> that applies to it, f.ex. a note as a raised number, ex. "1)" "2)" or "a)"
> "b)"

Built. The first pass printed a bare superscript digit beside the verdict and a
bold `1.` at the head of the list item, which is two notations for one
cross-reference and neither of them the one he named.
`measurement_report.note_label` is now the single formatter and both renderers
ask it, so the marker and the list cannot come apart. Photographed on screen:
the two grey rows read **PASS** with a raised **1)**, and the list under the
table opens **1)** with the same number.

> A test that asked `note_label` the same question the renderer does PASSED
> under a mutation that put the notation back to a bare digit: both moved
> together. The notation is a literal in the test now. That is the third time
> this project has caught a check re-deriving the value it is checking.

### The question back, which is his to answer

The rest of his comment is about a column where every row reads INFO:

> Why are most of them INFO, when the thresholds are set and can be tested.
> Verdict should be given when report is calculated.
> Make sure all verdicts exist in the demo package, and only those tests that
> genuinly cannot be tested should state this in their notes.

The missing verdicts in the package are B8-111 and are fixed. The INFO rows are
a different thing, and they are **his own ruling**, recorded in §4 of
`measurement_report_limits.md` as his 12b of 2026-09-09:

> since the measurements are not a verification run and will most often not
> fall within set accuracy threshold values. In this case the report output
> must explain this.

The sheet in his screenshot is the run's own **profiling** chart, printed raw
by definition, and the document does carry the explanation his condition asks
for, immediately under the table:

> This sheet is not graded, so its numbers are shown for information only. It
> was measured to build a profile rather than to check one, and a profiling
> measurement is expected to fall outside the accuracy limits. That is normal
> here, and it is not a fault.

Read in the rendered document, not in the source. What he pasted was a
fragment that stops before it.

So the question is whether 12b still stands now that he has seen it in
practice. His new sentence, *"only those tests that genuinely cannot be tested
should state this in their notes"*, would grade the profiling sheet too: the
numbers are all there, and what is withheld is a judgement about whether they
mean anything, not a measurement nobody could make. That is exactly the
argument he used this morning to overturn CH-17 for the grey rows, and the
remedy he chose there was a verdict plus a numbered note.

**Nothing has been changed either way.** Overturning 12b is his call and not
ours, and the same is true of the second, quieter consequence: a profiling
sheet's ΔE against the chart's design is the printer's own error before any
profile exists, so on any ordinary limit set it would read FAIL on nearly every
row, on nearly every printer, by design. A column of red that is expected to be
red teaches a reader to ignore red.

### ANSWERED: 12b stands. Confirmed by Knut, 2026-09-13

> Anser to "So: does 12b still stand now you have seen it in practice? ": For
> now, leave it as is.

Nineteen minutes after the question. So the profiling sheet keeps its INFO rows
and the sentence under the table that explains them, and §4 of
`measurement_report_limits.md` now carries that confirmation inline against the
rule itself. No code changed: the answer was to leave it, and it was already
left.

"For now" is doing work in that sentence and is recorded as written. If he
comes back to it, the remedy is the one he chose for the grey rows on the same
day: a verdict plus a numbered note saying what the number is measuring.

## 2u. Knut's ruling of 2026-09-14: the bottom lines get an ALIGNMENT, and it supersedes 2m-3

He asked twice in one morning, and the second post replaces the first. It is
recorded that way here so the sequence cannot be misread later: the first ask
was for left-alignment alone, the second for a control offering all three.

> **First.** *"for the sake of beauty, I find it better that the two bottom
> text type (in Sheet text frame) should be left-aligned against the patch area
> left margin, instead of centred against available horizontal space. This
> means a long text only gets warning when hitting towards the right side
> limits. This is ok. Leave limit detection as is for the left side, as
> alignment of text may change again later."*

> **Then.** *"However, in some cases the centre adjustment is best, depending
> on the setup. I thus suggest a new input box to be added below the Size input
> box in the Sheet text frame. The "Alignment" input box should be placed
> aligned with the other selection and input boxes in that frame, so it looks
> nice and orderly. The Alignment input bod shall have three options in its
> pulldown list: 1. Left margin (default): this is the new option mentioned
> above, where any of the two bottom text types are left adjusted against the
> left margin. 2. Centre of available space: This is the alignment type already
> in the design on beta 13. 3. Centre between left and right margin: This type
> is new, where the centre alignment is set between the patch area left margin
> and right margin. This is a slightly different centring of the text, which is
> useful in some cases. Leave side-limit detection as it is designed. Depending
> on the set alignment of text, a long text may trigger a warning on either
> sides, or only one side. The new alignment parameter must be added in the
> list of parameters so that it is saved/remembered or loaded in all cases for
> a profile run or run type, when changing profile run or run type, or when
> loading a preset, generating chart and all the other events that will load,
> save or generate … like all other parameters. Please make this change. Test
> it thoroughly, that all alignment options result in the correct behaviour on
> screen, tested on presets for each instrument type."*

**§2m-3 IS NOT WITHDRAWN, IT IS NOW ONE OF THREE.** Its two bounds are exactly
what they were, and his option 2 is its placement, kept and named. That is why
`text_edge_fit.bottom_text_bounds_mm` has no alignment argument at all: the
side limits cannot be moved by a choice about placement, which is the cleanest
way to keep *"Leave side-limit detection as it is designed"* true.

### The three placements, written once

`text_edge_fit.bottom_text_start_mm` is all three, and the renderer and the
panel both go through it and through `bottom_text_room_mm`:

| option | the key stored | where a line of width *w* starts |
|---|---|---|
| Left margin | `left_margin` | `bottom_text_anchor_mm`, which is the left margin held at or right of the left bound |
| Centre of available space | `available` | the midpoint of the two bounds, less *w*/2 |
| Centre between left and right margin | `between_margins` | `bottom_text_centre_mm`, the midpoint of the patch area, less *w*/2 |

and in every one of them the start is clamped to the LEFT BOUND, so a line
wider than its room is anchored there rather than spilling half its overflow
into the clip band. That is what the centred renderer already did with an
over-long line, kept.

### The room follows the placement, and that is his own sentence

*"Depending on the set alignment of text, a long text may trigger a warning on
either sides, or only one side."* The room is "the widest line that still fits
between the two bounds", so it depends on where the line starts:

* `left_margin`: `right bound - anchor`;
* `available`: `right bound - left bound`, which is his earlier 202 mm example
  on A4 unchanged;
* `between_margins`: twice the distance from the patch-area midpoint to the
  NEARER bound, because a centred line grows at both ends.

On A4 with a 12 mm left margin and a 30 mm right one those are 194, 202 and
184 mm, against bounds of (4.0, 206.0) in all three cases.

**ONE CONSEQUENCE HE DID NOT SPELL OUT, AND IT IS REPORTED RATHER THAN
ASSUMED.** Before this, the width check measured `right bound - left bound`
whatever the margins were. Left-aligned, that would let a typed size run off
the right of the paper with nothing said whenever the left margin is wider than
the left bound: on A4 with 12 mm margins, an 8 mm blind gap. A silent overflow
is the fault he reported against beta 8 in the first place, so the room is
measured from where the line starts. His 202 mm example is untouched where it
lives, on the bounds.

### A chart made before the option existed

`LayoutRecipe.from_dict` gives it `left_margin`, his default, so an old preset
or a stored chart changes alignment when it is loaded. That is what "(default)"
means and it is deliberate; the note is in the code so a later reader does not
undo it.

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Built and driven on screen against one engine
preset from each of the six instrument groups, all three options on each, with
the ink measured off the app's own TIFFs
(`scripts/drive_182_bottom_text_alignment.py`). His *"Test it thoroughly … on
presets for each instrument type"* is that run; whether the result is what he
wants to see is his to say.

## 2v. Knut's ruling of 2026-09-14: the report waits for "Generate report"

> *"This change give the user more feeling of control and understanding of when
> something should change, or when a change will result in a changed report,
> and will see that it does change or not when clicking "Generate report". It
> will also give a user a chance to undo a changed field, if not wanting to
> regenerate the report. Make the change."*

answering his beta 12 observation, *"The generate report button seems not to do
much, as the report auto-generates whenever report type or judged against is
changed."*

Five settings now move the control and leave the document standing, with a red
line under the buttons: **Report type**, **Judged against**, **Show all
measurement runs**, **Show detailed data for each run**, and **the measurements
ticked in the list**. Pressing the button builds the document with them and
clears the line.

**WHAT DOES NOT WAIT, AND WHY THE LINE IS DRAWN THERE.** Opening a
measurement, adding or removing one, and the limits window writing a number all
still repaint at once. Those change what there IS to report on; the five change
how the same measurements are PRESENTED. A document quietly showing a
measurement the list beside it no longer contains would be a worse lie than the
one this defers.

**AND THE BANNER IS A COMPARISON, NOT A FLAG**, which is his second sentence
doing the work. A boolean set on every change cannot see an undo, so putting a
control back would leave a red line over a document that already matches it.
`_doc_settings()` snapshots the five, `_render` records what the document was
built from, and the banner is the two being different.

**WHAT A SETTING DOES ON DISK IT STILL DOES AT ONCE.** Choosing a limit set
still binds the run and still asks its recalculate question; choosing a type
still stores it on the run. Deferring those would turn a deliberate act into a
pending one, which is not what he asked for.

### Confirmed behaviour: the PDF is what is on screen, and the door stays open

**Confirmed by:** Knut, 2026-09-18.

Round 21 measured that **Save report as PDF** walked straight past the
deferral: with the pulldown on `Colour summary (one page)`, the red line up and
the document on screen still reading *Full colour check* over several pages,
the export wrote a one-page `Colour summary` document nobody had seen, and left
the window unchanged with the line still up. The rule did not say what the
export should do, so it was reported rather than fixed. He answered:

> *"After a setting is changed, giving the user a red text notification that he
> should press Generate Report to apply the changes, then the 'Print Report as
> PDF' button should be disabled until the Generate Report button has been
> pressed. After Generate Report button has been pressed the report output is
> updated, and then the 'Print Report as PDF' can be pressed, which then
> creates the document as the report is written. So, as long as the settings
> for a loaded report is untouched the PDF can be generated and printed."*

He first ruled that the button should be greyed until Generate was pressed,
and that was built. Later the same day he changed it:

> *"I realise that it is better that clicking the button always generates a pdf
> from the currently loaded report text. If some settings are changed, those
> are not applied before clicking Generate Report, and making the PDF should be
> possible still, because the user can also revert any changed settings. Thus
> the disabling of the Print Report As PDF button is not needed, unless no
> report is loaded in the window at all."*

**So the button follows the sources, as it always did, and the fault is fixed
at the other end**: `_export_pdf` builds from the settings the document on
screen was built with (`_doc_built_with`) rather than from whatever the
controls hold now. That answers the original complaint better than greying the
button did, because a reader can still hand somebody the document in front of
them while they think about a setting they have moved.

The five settings are restored for the length of the build with every signal
blocked, so nothing repaints and nothing is written; see
`_as_the_document_was_built`.

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Driven on the real window over fourteen steps
with the document fingerprinted at each, so "nothing changed" is measured
rather than assumed (`scripts/drive_182_generate_waits.py`).

## 2w. Knut, 2026-09-14: a help icon per metric, and the five rows that have no detection

> *"In report limits window (Edit limits button) the first column is a name for
> each metric. Right aligned to the end of each metric name, add an info help
> icon, where each help icon describes the metric for that line and details the
> conditions used to detect if a chart contains the patches needed to assess
> and judge this metric. If any metric is missing a detection method for
> checking if a chart used for verification contains needed patches, then this
> detection method must be determined and specified."*

Built. Thirty icons, one per row, lined up at the right edge of the name
column, each holding two paragraphs: what the metric measures, and how ChromIQ
decides whether your chart can be judged on it. The text lives on the ROW, in
`compliance_sets.ROWS`, so a row cannot be added without it (`__post_init__`
refuses), and `tests/test_every_metric_says_how_it_is_detected.py` reads the
numbers in the sentences back out of `measurement_report`'s own constants, so a
changed threshold cannot leave the window promising the old one.

### Which rows can be judged at all, measured

Eleven of the thirty carry a verdict. Fourteen are `unmeasurable` and always
were: they need a gloss meter, a xenon rig, nine readings at set positions, or
a workflow ChromIQ does not have, and their icons say exactly that. The
remaining **five have no detection method**, which is what his last sentence is
about.

### The three reference rows are dead on every ChromIQ chart, and the icon says so

**MEASURED: `needs_reference_file` in 80 of 80 saved reports in the demo
package**, for *Paper white, difference from the reference paper*, *Solid
colours, largest difference* and *Cyan, magenta and yellow solids, largest hue
difference*. Those three need a colorimetric reference sidecar, which only the
profile-gamut chart module writes. They are also the three rows both Custom
columns put a number on. So the rows a user is most likely to type a limit into
are the rows an ordinary chart can never answer, and the icon now says which
kind of chart supplies them.

### Rows 8, 9, 10: the control strip

The population is the standard's own control strip, a named strip with a
published patch list that ChromIQ does not hold and cannot invent. But the
detection does not need the list, only a declaration. **Approved by Knut,
2026-09-18, and built (B8-397):**

> A chart carries a control strip when a sidecar `<chart stem>.control-strip.json`
> sits beside it holding `{"name": "<the strip's own name>", "sample_ids":
> ["A1", "A2", ...]}`, or when the `.ti1` / `.ti2` carries a CGATS keyword
> `CONTROL_STRIP_IDS` naming the same ids.
>
> The row is computable when the sidecar exists, when **k**, the count of those
> ids present in the measured `.ti3`, is **at least 8** (below eight an average
> over the strip says nothing), and when a reference exists for them. The 95th
> percentile row needs **k >= 20**, because its nearest rank `ceil(0.95 k)`
> equals `k` for every k below 20 and it would simply repeat the largest.
>
> Two reason codes, because they send a reader to different places:
> `no_control_strip` and `control_strip_too_small`.

Nothing in that reads a standard. It answers *"does this chart have a strip and
is it big enough"*, which is the question he asked the detection to answer.

### Rows 18 and 19: a specification change, not a fault

*Outer-gamut patches* and *Surface-gamut patches* are missing the DEFINITION of
their population, not the detection. ChromIQ could define its own and compute
them honestly today:

> **Surface-gamut patches**: every patch whose device values touch the surface
> of the device cube, `min(v, 100 - v) <= 2.0` for at least one of R, G, B.
> Computable with at least 10 such patches carrying a reference.
>
> **Outer-gamut patches**: the top quartile by chroma, `C*ab = hypot(a*, b*)`,
> requiring at least 20 patches so the average is not one or two readings.

**But those rows sit under the heading "Selected patches of the standard's
chart", and giving them ChromIQ's own definition while leaving that heading is
exactly the "attributing coverage to a standard" mistake `compliance_sets.py`
already records being made twice.** If Knut wants them computable, the group
heading and the row names change with them.

He does, and he changed the heading in the same breath (2026-09-18): *"I have
already proposed to change the heading from 'Selected patches of the standard's
chart' to 'Selected patches of the chart'."* `GROUP_LABELS["selected"]` reads
that now, and the row NAMES are unchanged, which he did not ask for and which
name no standard.

### Confirmed behaviour

**Confirmed by:** Knut, 2026-09-18, on #182: *"Implement the proposals. I have
already proposed to change the heading from 'Selected patches of the standard's
chart' to 'Selected patches of the chart'. The help text can explain, as for
all the other metrics, what the detection method is and how it is used, and if
there are any requirements to the charts etc. (similar structure as the other
metrics help file)."*

All three are built (B8-397). The icons were built and driven on screen for the
2026-09-14 round (`scripts/drive_182_metric_help_icons.py`, thirty icons, three
of the info dialogs photographed); the detection itself is driven by
`scripts/drive_182_the_five_rows.py`, which photographs the changed heading,
the five rows carrying a limit in the two Custom columns, all five new help
texts, and the two new reasons as sentences in the Measurement Report.

**What is built, exactly as the proposals read, with four things they left
open and the code had to settle:**

1. **k counts the ids that are in the measurement AND carry a reference
   value.** The proposal states those two conditions separately; counting them
   as one number is never more lenient, and it is the population the statistics
   are actually taken over. A strip that is all present and has no reference at
   all reads `no_reference` rather than "too small", because those send a reader
   to different places.
2. **The outer-gamut quarter is ranked by the REFERENCE's chroma, not the
   measured one**, so the population is a property of the chart and the same
   chart picks the same patches however well it printed.
3. **The cube corners are in both gamut populations.** They are surface patches
   by construction and the most saturated patches on any chart, and the
   proposal excludes nothing. The ΔE00 statistics elsewhere exclude them for a
   different reason (they are unreachable by design on a from-profile-gamut
   chart) and that exclusion is not carried over.
4. **"At least 20 patches" is the size of the QUARTER**, which is what its own
   reason clause says ("so the average is not one or two readings"). A chart
   therefore needs roughly 80 patches carrying reference values before the
   outer-gamut row can be judged. Measured: the demo pack's 210-patch
   verification charts give a quarter of 53 and are judged; a 76-patch chart
   gives 19 and is not.

### And one fault found while mapping the table

The *Worst 5 % of patches* row could be withheld with a sentence that
contradicted itself: **measured on a 20-patch chart, *"the chart has 20
patches; at least 20 are needed"***. The verdict is passed on the within-gamut
subset, which was 18, and `{n}` was filled from the sheet's own count. The
sentence now names the population that was actually counted.

## 2x. Knut's ruling of 2026-09-15: every margin warning is MEASURED, and it is recomputed on Generate Chart

His test of v4.3.0-beta.17 (#182, comment 5679470670), with his chart, his log
and his rendered sheet attached:

> *"The height measurement of the bottom text (either custom text and "Stamp
> layout summary..." or only one of them), must be calculated if it fits inside
> the space between bottom margin of parch area and the B (or the helper marker
> parameters, whichever are biggest, as ruled before).*
>
> *When any chart layout parameter changes, a red text says to click Generate
> Chart to update the preview. This is the correct behaviour, so the margin
> warnings need only be updated upon the chart being updated with Generate
> Chart, and the also the calculations should use the Measured from Preview
> numbers in the calculations if text fit. This simplifies very much the
> calculation and it does not need to calculate across many page sizes or other
> searches, and does not need to do this every time a setting is changed.*
>
> *It is also a special case for hexagonal patches, or when "Use ChromIQ layout
> engine..." OFF, that set margins does not always match closely the Measured
> from Preview margins. That is why, even though margins input boxes are used
> to change the margins space, the margins used in the assessment of space for
> text, and if the text overlaps the patch area edges, must be calculated
> correctly and used in the assessment. Measured from Preview margin values are
> reliably calculated for all instrument types, all patch types and for all dpi
> and page sizes) and thus most reliable to use in the calculations of space in
> margins, and if text falls on the patch area edges or not (on all sides).
> However, they are only usable after the Measured from Preview margin values
> have been completed (after a Generate Chart has been performed). Test all
> margin text parameter combinations for all 4 sides again, using this
> principle. Make sure all the rules defined are adhered to."*

### Why he is right, in one line of arithmetic, on his own chart

CR30, A4, area-first, **hexagonal** patches, layout engine on, bottom margin
13.0 mm, "B" 10.0 mm, ruler helper markers top and bottom at 4.0 + 2.0, Size
auto, a ten-placeholder custom line with "Stamp layout summary along the
bottom" on, so two lines, at 200 dpi.

| where the patch area's bottom edge is | mm | what the panel then said |
|---|---|---|
| `predicted_patch_bottom_mm` (retired) | **18.60** | nothing: 8.60 mm of room for 8.38 mm of text |
| `margin_inspector.measure_from_engine` | **15.822** | 5.82 mm of room for 8.38 mm, **2.56 mm short** |

15.822 is the 15.8 he read off the frame. **A flat-top honeycomb's last row
hangs below the grid box `geometry.compute` returns**, so a prediction built out
of `compute` and `placement` cannot see it. Measured off his own TIFF at 200
dpi: the bottom helper markers run 4.06 to 6.22 mm, and from 10.16 mm (the "B"
anchor) upward the ink is unbroken, so there is no clear paper anywhere between
the text and the patches.

### The rule as built

1. **All four patch-area checks read "Measured from Preview".** The bottom
   sheet text against `report.bottom_mm`, the strip letters against
   `report.top_mm`, the chart notes and the settings stamp against
   `report.right_mm`, and the clip border's band and its text against
   `report.right_mm` or `report.left_mm` on whichever edge it sits. Nothing on
   this panel predicts a patch edge any more. That also closes B8-137, the open
   item saying the other three edges measured the margin and not the patches.
2. **With no chart generated, they say nothing.** His sentence *"they are only
   usable after ... a Generate Chart has been performed"* is taken literally: a
   prediction is not offered in their place, because the prediction is what was
   wrong.
3. **They are recomputed on Generate Chart and on nothing else.** The refresh
   B8-176 put on every layout keystroke hours earlier is removed again. The red
   *"What is on screen is not in this run's chart yet. Press “Generate Chart” to
   apply it."* line is what tells the reader the boxes are ahead of the frame,
   and he names that behaviour as already correct.
4. **Nothing is searched for.** `margin_rise_that_clears_mm`,
   `predicted_patch_bottom_mm`, `_larger_paper_note`, `_bottom_clears_with`,
   `lowering_b_clears` and `markers_off_clears` are deleted. Every one answered
   *"how much more margin clears it"*, which this rule cannot ask: the answer is
   a measurement of a sheet that has not been drawn.

### What the messages say now

Four bottom wordings become two, one line and two lines. Each names what is
short, names the controls that move it, and ends by asking for a Generate
Chart:

> ⚠ The two lines of sheet text along the bottom run into the patches. They are
> printed 10.0 mm up from the paper edge and need 8.4 mm of room, and the patch
> area in "Measured from Preview" comes down to 15.8 mm, leaving 5.8 mm, so they
> are 2.6 mm short. Raise "Bottom" under "Margins (mm)", set a smaller Size
> under "Sheet text", or switch one of the two lines off, then press Generate
> Chart to measure it again.

No rise is named and nothing is claimed about paper: both were answers to the
question rule 4 retires, and both had already been measured false once. The
"B" sentence survives, because it is arithmetic on two numbers the panel holds
rather than a search: with the markers holding the text above "B", winding "B"
down moves no ink, and that is worth saying whether or not another control
finishes the job.

### Driven on screen, all four sides, on his own recipe

Read out of the `channels.json` he attached and pushed into the panel through
`_set_engine_recipe`, which is the door a preset, a loaded chart and the
restored session all use. Every number below is off the app's own frame.

| state | measured L / R / T / B | what the frame said |
|---|---|---|
| his recipe as attached | 11.1 / 26.0 / 14.4 / **15.8** | the bottom warning above, 2.6 mm short |
| the bottom box moved 13 → 20, **no Generate** | 11.1 / 26.0 / 14.4 / 15.8 | **word for word the same**, and the red "press Generate Chart" line appears |
| then Generate, at 20 mm | 11.1 / 26.0 / 16.3 / **24.8** | ⚠ Margins: OK |
| top margin 5.0, "T" 2.0 | 11.1 / 26.0 / **11.9** / 18.2 | bottom, 0.1 mm short |
| right margin 4.0 | 11.2 / **23.0** / 11.9 / 13.5 | the settings stamp over the patches, and the bottom, 4.8 mm short |
| a 12 mm clip band on the left, four lines | **18.7** / 26.1 / 15.1 / 16.7 | the clip text past its band and over the row labels, and the bottom, 1.7 mm short |

### ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* The rule is Knut's and is quoted above; the
wordings and the table are ours, driven on screen and photographed
(`~/Desktop/ChromIQ-beta18-proof/knut-bottom-text/`), and nobody has yet said
that what the app now does is what it should do.

### And the engine-off half is reported, not built

With "Use the ChromIQ layout engine instead of printtarg" OFF, the layout
panel's Sheet text box, its Size, the "B" box, the clip-border controls and the
ruler-marker boxes are all **hidden**: printtarg lays the sheet out and none of
that furniture exists. `_engine_text_notes` returns before it does anything
there, so none of the four checks runs.

**One thing on an engine-off sheet is still text, and it is not covered.**
`ChartCreator._stamp_tiff_metadata` is called on the printtarg path as well as
the engine path, so "Run 1 Chart Notes" and "Stamp settings down the right
edge" really are printed down the right edge of an engine-off chart. Measured
on screen, CR30 / A4 / 300 dpi, a typed note with the stamp on: the patch
area's measured right edge is **17.53 mm** and the nearest black ink to the
right paper edge is at **10.41 mm**, so on that sheet there are 7.1 mm of clear
paper and nothing is wrong. The check simply does not exist there.

Extending it is a change to a surface his ruling does not name, so it is
reported rather than made. What would be needed is the right-edge overlap
asked without the engine gate, using the same measured `report.right_mm`.

## 2y. Knut's ruling of 2026-09-26: no i1iSis entry in the layout engine, and nothing hidden (B8-1283)

### Confirmed behaviour

**Confirmed by:** Knut, 2026-09-26, on #182 (comment 5845519118), for exactly
what he said. The question put to him: *"With the ChromIQ layout engine on,
the i1iSis cannot be chosen in Manual: the layout panel has no i1iSis entry
and shows the i1Pro. Choosing any paper there quietly switches the instrument
to the i1Pro, and that is what Save as Defaults then stores. Should choosing
the i1iSis hide the layout panel and use printtarg's own fields, as it does
with the engine off? Or should the engine get an i1iSis entry?"* His answer:

> *"No i1iSis entry. Do not hide. That setting is only used if a user measures
> a chart outside ChromIQ (in i1Profiler) and then imports the results back
> into ChromIQ for creating the report."*

So the app stays as it is: the layout panel has no i1iSis entry, and with the
engine on the panel is not hidden for the i1iSis. Nothing was changed for it
(B8-1283); `tests/test_b8_1283_no_i1isis_entry_and_nothing_hidden.py` pins
both halves.

The i1iSis help (printtarg's Measurement Instrument, `data/parameters.yaml`)
does not say what the setting is for in his words. Wording proposed to him,
not shipped, in `~/Desktop/ChromIQ-beta44-proof/k50-create-chart/NOTES.txt`.
