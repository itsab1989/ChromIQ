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

Last updated 2026-09-10.

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
clear, which is the fault Knut reported. Under the ruling they cannot print at
all. The drop now writes a log line naming both numbers and both settings, which
is a change from silence but is still not on screen: see section 5.

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

**A note with no room left is still dropped without a word ON SCREEN.**
Since 2026-09-10 it is no longer dropped in silence in the LOG: the stamper
names the paper it has, the reserve it must keep and the two settings that would
give it room. Nothing says so in the app. Knut's ruling that "Text distance from
edge" is a limit takes the count of configurations that print a note from 22 of
22 to 18 of 22 (see section 2), so the sentence matters more than it did, and it
is still a §M catalogue job. The paragraph below is the original finding and
stands.

**A note that will not fit a narrow clip band is dropped without a word.**
With the clip border on the right and a band of 10 or 14 mm, three of ten
content modes leave no run of blank paper wide enough to write in, so no note is
printed and nothing on screen or in the log says so. The three are a notes form
at 10 mm, a notes form at 14 mm, and three lines of custom text at 10 mm.

Measured against the pre-work control, all three printed nothing at 4.2.0 as
well, so this is not a regression and not a blocker for 4.2.2. The other seven
print, and across the twenty ordinary clip settings nineteen print in the same
columns 4.2.0 chose, with none of the user's own lines under the note and none
destroyed.

What is missing is the sentence, not the placement. A user who asks for a note
and gets a blank margin has no way to learn that the band they chose is too
narrow. That text is a §M catalogue job and goes to §M-PROPOSED first, so it is
not written into a tab under a release.
