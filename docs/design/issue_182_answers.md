# Issue #182: the answers we have been given, and who gave them

**This file exists because the working notes for #182 are deliberately kept out
of the repository.** `.gitignore` excludes `.progress/issue-182/`, because those
notes quote tolerance VALUES out of paywalled standards and the permission
enquiry now with a standards body rests on those values not being in our public
repository. The ANSWERS below are ours to keep; the numbers are not, and none
appear here.

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
