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
| **ISO** | REFUSED as asked, and redirected | Reproducing the content of a standard inside software needs explicit permission or a specific licence; a single-user licence is not enough; the route is the national member body. A letter is drafted, reviewed three times and **not yet sent**. |

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
