# Unified Measurement Management — Design Specification

> **Revision 2026-08-04 (c) — what to review.**
> **Awaiting review:** M-BUILD-ELSEWHERE.
> M-VERIFY-NO-PROFILE and M-VERIFY-NO-CHART were **accepted** on 2026-08-04 and have joined §M; M-CHART-CORRUPT, M-REPLACE-UNCOUNTABLE and M-PREVIEW-PAUSED were accepted earlier the same day. The one new message guards a build whose measurement belongs to a different run — Knut, beta.132: *"I created a profile for run 6 via standing in run 5. A guard for this should be made."* ✅ marks a message Knut has approved; 🆕 marks one still in the queue. `tests/test_message_catalogue.py` checks this list against the `approved=` flags in the code.

> **Status:** specification, agreed on [issue #130](https://github.com/itsab1989/ChromIQ/issues/130).
> Written by the ChromIQ assistant, reviewed and directed by Knut (soul-traveller)
> and Sebastian, 2026-08-02/03.
>
> This is the first chapter of what is meant to become ChromIQ's design
> documentation. It covers **the life of a measurement** — how one ends, what is
> written, what is archived, and every warning shown along the way. Later
> chapters can cover the other areas of the app in the same shape: the tables
> here are the contract, and §T says how each row is proved.

## How to read this

- **§0–§3** are the model: what actually happens to a `.ti3`, and how ChromIQ
  can tell one state from another.
- **§4–§6** are the three places a matching set of files can be broken.
- **§7** maps every event ChromIQ detects to the exact line of ArgyllCMS or of
  ChromIQ's own reader that emits it.
- **§M** is the complete message catalogue: every window, with its ID and text.
- **§S** is the sequence: what happens in what order, one window at a time.
- **§T** is the test plan. Nothing here is implemented until its row is green.

**The rule the whole document serves:** a run holds one matching set — chart,
measurement, profile, and the verification measurements of that profile. Every
warning exists because some action would break that set, and every one of them
archives rather than deletes.

## 0. The one fact everything follows from

**ArgyllCMS `chartread` keeps its readings in memory and writes the `.ti3` only when it exits cleanly.** Kill it and the readings are gone — there is no partial file on disk to recover.

| | What is sent | What chartread does | `.ti3` |
|---|---|---|---|
| `d` then `y` | keystrokes | writes the file, exits 0 | **saved** |
| Stop (before beta.123) | SIGKILL | dies where it stands | **lost** |

Your own log carries both, minutes apart: every `d` ends `finished with code 0`, every Stop ends `finished with code -9`.

**The ChromIQ engine is different.** `chromiq_chartread.c` calls `cq_write_ti3_atomic()` *before* it gives up — a ChromIQ extension marked *"never lose readings"*. Stock chartread has no equivalent: `chartread.c:1654` treats `q` at a misread prompt as give-up and `return -1`, writing nothing.

---

## 1. Every way a measurement can end

| # | Route | Engine | Mode | What is sent today | Message today | `.ti3` today | Proposed |
|---|---|---|---|---|---|---|---|
| 1 | **Stop** | ChromIQ | strip | two `q` | "Keep what you have measured so far?" | saved | unchanged |
| 2 | **Stop** | ChromIQ | patch | two `q` | same | saved | unchanged |
| 3 | **Stop** | stock | strip | `d`→`y`, or `r`→`d`→`y` | same | saved | unchanged |
| 4 | **Stop** | stock | patch | **nothing — killed** | **none** | **LOST** | fixed in beta.123 (§6) |
| 5 | **Stop** | any | nothing read | kill | none | nothing to lose | say "nothing was measured, so nothing was saved" **on screen** |
| 6 | **`d`** | both | strip | `d` → chartread asks | "Patches Still Unread" | saved | replace with the one window (§2) |
| 7 | **`d`** | both | patch | as above | as above | saved | replace with the one window (§2) |
| 8 | **`Esc`/`q`** | both | strip | passthrough | none | **discarded silently** | the one window |
| 9 | **`Esc` `Esc`** | both | patch | passthrough | none | **discarded silently** | the one window |
| 10 | **any failure window offering a save** | both | any | see §1a | its own text | saved | all use the same wording |
| 11 | **any failure window offering only "Give Up"** | both | any | `Esc` | *"stop the measurement without saving"* | **discarded** | must offer to save — see §1a |
| 12 | **`Esc`** (single patch) | spotread | single | passthrough | inline | n/a — spotread appends per patch | §9 |
| 13 | Chart finished | any | any | — | "All patches read" | saved | unchanged |
| 14 | Instrument init fails | any | any | — | **none** — exits **0** | none | fixed in beta.123 (§6) |

### 1a. Every window that can end a measurement

You asked me to generalise rows 10 and 11 to all failure windows. Doing that turned up **five more doors that discard without offering to save** — the same fault as rows 8 and 9, wearing a button instead of a key:

| Window | Buttons today | Offers to save? |
|---|---|---|
| Patch Read Failed / Strip Read Failed | Retry · **Save Partial & Quit** | ✅ |
| Strip Read Interrupted | … · **Save Partial** | ✅ |
| Patches Still Unread | **Save Partial** · Keep Measuring | ✅ |
| Strip may be misaligned | Use Anyway · Re-measure · Retry · **Give Up** / **Stop** | ❌ |
| Wrong Strip Read | Use Anyway · Retry · **Give Up** | ❌ |
| Unexpected Colour Response | Use Anyway · Retry · Resume · **Give Up** | ❌ |
| Instrument Error | Retry · **Give Up** | ❌ |
| Confirm Abort | **Yes — Abort** · No — Keep Measuring | ❌ |

"Give Up" sends `Esc`, which for stock chartread means quit-without-saving. The windows say so honestly — but the user is being asked to choose between retrying and losing the session, when saving was available all along.

**Proposal: every one of these gets the same three choices as §2**, so "Give Up" stops meaning "throw away the last twenty minutes".

---

## 2. The proposed unified ending

**One window, one set of words, every route** — Stop, `d`, `Esc`/`q`, and every failure window in §1a:

> **Keep what you have measured so far?**
>
> You have read **{n} patches** in this session. They are not in your measurement file yet — ChromIQ can write them now, or end the session without them.
>
> **What each button does:**
> • **Save and stop** — writes what you have read so far to this run's measurement file and ends the session. You can carry on later with "Refine / resume existing measurement", reading only the strips or patches that are still missing.
> • **Discard and stop** — ends the session and keeps nothing from it. *(added only when a measurement was already there: "Your previous measurement of {n} patches is put back exactly as it was.")*
> • **Keep measuring** — closes this window and carries on where you were.

**On the first sentence.** You were right that the old wording fought itself — *"stopping now would throw them away"* immediately before a button that saves them reads as a threat, and an alarming one. It now states the position plainly and lets the buttons offer the way out.

**On the third sentence.** It assumed a previous measurement existed. It is now added only when one did, and says what will happen to it rather than merely that it is "untouched".

### 2a. Protecting the measurement that was already there

Your assumption is the right design, and it is only partly true today: ChromIQ archives a measurement to `old/` when *replacing* one, and archives an empty `.ti3` after a session — but a session that starts, reads nothing and dies has no guard of its own.

Proposed, and it makes §3 possible:

1. **At the start of every measurement**, if a `.ti3` exists, copy it to `old/<date_time>/` — `runs/runN/old/` for Profiling, `runs/runN/verifications/<date>/old/` for Verification — and record its reading count.
2. **At the end**, compare (§3).
3. **Put it back** when the session ended without saving, when the new file is empty, or when a resume ended with *fewer* readings than it started with.
4. **Never delete the archived copy.** It costs a few kB and it is the only insurance against a bad ending.

---

## 3. The `.ti3` reading-count check

**Where the counts come from.** A CGATS file states `NUMBER_OF_SETS` and then lists that many rows between `BEGIN_DATA` and `END_DATA`. `workflow/ti3_analysis.py` already parses this, so nothing new is needed:

| | Where | Meaning |
|---|---|---|
| **A** | `.ti2` `NUMBER_OF_SETS` | how many patches the chart HAS |
| **B** | `.ti3` `NUMBER_OF_SETS` | how many the file CLAIMS |
| **C** | rows between `BEGIN_DATA`/`END_DATA` | how many it actually HOLDS |
| **C₀** | C, measured **before** the session starts | the baseline |

**You are right, and my "not possible" was wrong.** With C₀ recorded at the start, `C − C₀` is exactly how many patches this session added — so the session's own result is measurable after all. I had only considered the file at the end.

### 3a. Every state a `.ti3` can be in

| State | B | C | Reading | Action | Message when Start Measurement is pressed |
|---|---|---|---|---|---|
| No `.ti3` at all | — | — | nothing measured yet | normal for a fresh run; C₀ = 0 | none |
| Header only, **no `BEGIN_DATA`/`END_DATA`** | any | — | **no measurements** — treat as empty | delete, restore the archived copy, say so | **M-REPLACE-UNCOUNTABLE** ✅ |
| Empty (`C = 0`), or `NUMBER_OF_SETS` absent or 0 | 0 | 0 | nothing was saved | delete, restore, say so | **M-REPLACE-UNCOUNTABLE** ✅ |
| `B ≠ C` | ✓ | ✓ | **corrupt or truncated** | never offer for resume; keep the file, restore the archived copy, explain | **M-TI3-MISMATCH** (with its `{extra}` sentence) |
| Partial (`0 < C < A`) | ✓ | ✓ | expected after a partial session | offer resume, name the count | **M-REPLACE-PARTIAL** |
| Complete (`C = A`) | ✓ | ✓ | fully measured | §6 warning before re-measuring | **M-REPLACE-COMPLETE** |
| `C > A` | ✓ | ✓ | **does not belong to this chart** | refuse, explain | **M-TI3-MISMATCH** |

✅ = approved by Knut, 2026-08-04 — full text in **§M**, with the rest of the approved catalogue. 🆕 = **PROPOSED**, awaiting review — full text in **§M-PROPOSED**. Every message not marked here was approved earlier.

**Why M-REPLACE-UNCOUNTABLE exists.** The first three rows all describe a file with nothing readable in it, and the model gave them no message of their own — so they fell through to M-REPLACE-PARTIAL, which states a fraction and produced **"0 of the chart's ? patches have been read"**. That reads as a fault in ChromIQ rather than a fact about the file, and it points at Refine / resume, which cannot work when there is nothing to resume from.

**Removed 2026-08-04: the "no `.ti2` beside it" row, and its message M-REPLACE-NO-CHART.** Knut asked whether that condition can arise at all: *"Can a chart read at all be initiated if a ti2 file does not exist? I thought it could not. Thus the Start Measurement button should not be available at all."*

He was right about what *should* happen, and — measured, not assumed — wrong about what *did*: **Start Measurement was offered without a `.ti2`.** The Measure tab can be loaded from the `.ti1` when a project is opened, and the button was enabled from that alone; chartread would then have failed with the chart file missing. That is a bug, not a case needing a message. Fixed in beta.128: Start is available only when the `.ti2` exists, and its tooltip says why when it is not. With the condition prevented, the message is gone from the model and from the code.

**C₀ and a corrupt file.** When the `.ti3` present *at the start of a measurement* is corrupt or empty, `C₀ = 0` — there is nothing in it to resume from and nothing to lose by measuring again, and it is treated exactly as "no measurement" for §3b's purposes. The file itself is still archived rather than deleted, because ChromIQ cannot judge whether it holds something the user would want.

### 3b. Judging the session by C₀ → C

| C₀ | C at end | Resume? | Verdict | What ChromIQ does |
|---|---|---|---|---|
| 0 | 0 | — | nothing read, nothing saved | delete the empty file; say so on screen |
| 0 | > 0 | no | normal first measurement | keep |
| > 0 | 0 | **yes** | **the resume destroyed the earlier work** | restore from `old/`, warn loudly |
| > 0 | < C₀ | **yes** | **readings went backwards** — cannot be right | restore from `old/`, warn loudly |
| > 0 | = C₀ | yes | resumed but read nothing new | keep; say nothing was added |
| > 0 | > C₀ | yes | normal resume | keep; say how many were added |
| > 0 | any | **no** | a fresh measurement replaced it | the replace warning already covers this; the archived copy stays |

The two "restore" rows are the case you described — *"if saved ti3 at stop was empty and the ti3 before start was 10 patches, and the session was a Refine/Resume, then we know something went wrong"*. Without C₀ this is undetectable.

**On reporting**: agreed — every one of these is told **on screen**, not only in the log. A log line is hidden information.

---

## 4. Chart integrity — when the chart changes under a measurement

You are right that this is the same problem from the other end: a `.ti3` describes *one* chart, and a profile describes *one* `.ti3`. Change the chart and the set stops belonging together.

**Triggers:** Generate Chart · loading a `.ti1` · applying a patch set from the editor · auto-update · any preset change that regenerates.

**Every one of them asks** (Knut, 2026-08-03, after beta.125 shipped with only two of them wired): *"the warning messages defined for section 4 … should then arrive for all these cases: Generate Chart, loading a .ti1, applying a patch set from the editor, any preset change that regenerates."*

**The auto-update preview is the one exception, and it is an exception about *how often*, not about *whether*.** A window on every turn of a layout knob would make the option unusable, so Knut set the rule:

> *"the popup window saying 'The live preview is not being re-drawn...' should come once only, then again the next time 'auto-update preview ...' is enabled. At the same time it can come in the log window until 'auto-update preview ...' is disabled."*

So the live preview **declines to re-draw** a run that holds work, writes the note to the log every time, and shows the window once per switch-on of the option. See **M-PREVIEW-PAUSED**.

| What the run holds | Run type | Warning | Message |
|---|---|---|---|
| Nothing | either | none — nothing to break | none |
| Chart only | either | none | none |
| Chart + partial `.ti3` | Profiling | "This run holds a partial measurement of {n} patches. A new chart cannot be measured with it — the patches would no longer match. The measurement is moved to `old/` and kept." | **M-CHART-PROFILING** |
| Chart + complete `.ti3` | Profiling | as above, plus: "…and you would have to measure the whole chart again." | **M-CHART-PROFILING** |
| Chart + `.ti3` + profile | Profiling | as above, plus: "The profile built from it is moved to `old/` too, because it describes a chart this run will no longer have." | **M-CHART-PROFILING** |
| **Chart + `.ti3` + profile, AND the run has verifications with readings** | **Profiling** | **W4 — the widest blast radius of the three; see below** | **M-CHART-W4** |
| Chart + `.ti3` (+ profile) | Verification | **W5** — the same shape as W4, one level down | **M-CHART-VERIFY** |
| Chart + a `.ti3` that is **corrupt or empty**, no profile | Profiling | the same warning, **plus** a paragraph naming the file as corrupt or empty | **M-CHART-PROFILING** + **M-CHART-CORRUPT** ✅, appended |
| Chart + a `.ti3` that is **corrupt or empty**, **and a profile** | Profiling | as above, **plus** what it costs the profile | **M-CHART-PROFILING** + **M-CHART-CORRUPT** ✅ with its profile paragraph |
| Any of the above, **and the trigger is the auto-update preview** | either | the preview declines to re-draw instead of asking | **M-PREVIEW-PAUSED** ✅ |
| Any of the above, **and the chart has no `.channels.json`** | either | the §4 message, **plus** a paragraph about the pages | **M-CHART-NOPAGES**, appended |
| Any of the above, **and the run cannot be duplicated** | either | the §4 message, **plus** a paragraph about Duplicate | **M-DUPLICATE-BLOCKED**, appended |

✅ = approved by Knut, 2026-08-04 — full text in **§M**, with the rest of the approved catalogue. 🆕 = **PROPOSED**, awaiting review — full text in **§M-PROPOSED**. Every message not marked here was approved earlier.

**What "`.ti3` exists" means in this table**, since Knut asked for it plainly: the rows above distinguish three things, and they are not the same.

| In the table | On disk | How ChromIQ decides |
|---|---|---|
| no `.ti3` | the file is not there | `Path.exists()` |
| a `.ti3` that is **corrupt or empty** | the file is there, but holds no readable readings — no `BEGIN_DATA`/`END_DATA`, no rows between them, or `NUMBER_OF_SETS` absent or 0 | §3a's *header only* and *empty* states |
| a `.ti3` with `{c}` readings | the file is there and `{c}` rows can be read | §3a's *partial*, *complete* and `B ≠ C` states |

**At this point no measurement is running**, so every count here is the state *before* anything is measured — `C₀` in §3b's terms.

**Messages combine.** A single window can be one base message with one or two paragraphs appended: M-CHART-PROFILING is the window, and M-CHART-NOPAGES and M-DUPLICATE-BLOCKED are paragraphs added to it when they apply. Nothing else in this specification stacks; these two do, because both describe the *same* replacement from a different angle.

**W4 — regenerating the profiling chart of a run that has a verification history**

> **This would undo the whole run, not just its chart**
>
> Replacing this run's chart breaks the chain three links deep:
>
> • the measurement of {n} patches no longer describes the chart in this run;
> • the profile built from that measurement no longer describes anything on disk;
> • and the {v} dated verification{s} under this run were printed **through** that profile, so they stop describing a profile that exists.
>
> Everything is kept in `old/` and nothing is deleted — but the run would no longer hold a set of files that belong together, and its verification history could not be continued.
>
> **Duplicate the run and change the chart in the copy** if you want a different chart while keeping this one's work and its history.

**W5 — replacing the verification chart**

> **The verification measurements already made in this run used the chart you are about to replace**
>
> The {v} dated verification measurement{s} in this run were all made with this verification chart. Replacing it does not make them wrong, and the report can still compare their figures — but those measurements would no longer have the chart they were made with, so nothing on disk would say what they were readings *of*.
>
> A trend across the change also compares two different charts, which is not the same measurement twice. See §6b for what that costs in practice.
>
> The chart is kept in `old/` and no measurement is touched. Duplicate the run instead if you want a different verification chart while keeping this run's verification measurements intact.

**Why W4 is worse than the row above it.** Without verifications, regenerating the chart costs a measurement and a profile — both rebuildable from a reprint. With verifications it also costs a **history**, and a history cannot be rebuilt at all: those sheets were printed on days that will not come back. That is why it gets its own row and its own message rather than another sentence on the end of the previous one.

The Verification row is the one worth arguing about: the damage is not to one file but to a **trend**, and a trend cannot be archived back into meaning. That is why "Duplicate the run" belongs in the message rather than in a footnote.

### 4a. What counts as "a chart" — one definition, taken from Restore Used Chart

You are right that this must not get a second opinion. The definition already exists in `workflow/chart_slot.py`, which is what Restore Used Chart compares and copies, and everything below uses it unchanged:

| Part | Rule | Where |
|---|---|---|
| Stem | the sanitised project name; `<stem>-verify` for a verification chart | `Run.stem` / `Run.verify_stem` |
| Profiling chart files | `.ti1` · `.ti2` · `.cht` · `.channels.json` · `.strips.json` | `PROFILING_CHART_SUFFIXES` |
| Page images | any `.tif` / `.tiff` | `_IMAGE_SUFFIXES` |
| Travels with the chart | `meta.json` | `CHART_SIDE_FILES` |
| Verification chart files | **every file** at the root of `verifications/` — folders are never included, so the dated runs, `old/` and `reports/` are safe | `suffixes=None` in `slot_for_verification` |
| Never part of a chart | dot-files (`.DS_Store`, `._name`) | `live_files()` |
| Can the pages be redrawn? | only if a `.channels.json` is present | `has_layout_recipe()` |

**The two chart kinds are deliberately not defined the same way**, and it is worth knowing why before reusing this: a profiling chart shares its folder with the measurement, the profile and the run's own files, so it must be identified by suffix. A verification chart has a folder to itself, so everything in it *is* the chart.

#### When a chart is valid for this feature

| # | On disk | Is there a chart? | Can pages be redrawn? | Effect on §4 |
|---|---|---|---|---|
| 1 | nothing | no | — | no warning — nothing to break |
| 2 | `.ti1` only | **no** | — | no warning; a patch list is not a chart |
| 3 | `.ti1` + `.ti2` | **yes**, incomplete | **no** | warn; say the pages cannot be redrawn |
| 4 | `.ti1` + `.ti2` + `.channels.json` | **yes** | **yes** | warn |
| 5 | `.ti1` + `.ti2` + `.tif` | **yes** | **no** | warn; the pages would be lost |
| 6 | `.ti1` + `.ti2` + `.channels.json` + `.tif` | **yes**, complete | **yes** | warn — the ordinary case |
| 7 | `.tif` only | **no** | — | no warning; images with no chart are not measurable |
| 8 | dot-files only | **no** | — | no warning |

Rows 3 and 5 are the ones worth naming in the message, because losing pages that cannot be redrawn is a different loss from losing pages that can.

**Same rule as Duplicate, deliberately.** Duplicate requires `.ti1` + `.ti2` + `.channels.json` + at least one `.tif` — row 6. This feature warns from row 3 upward, because the question is different: Duplicate asks *"can this be copied into a working run?"*, while §4 asks *"is there something here to lose?"*, and rows 3 and 5 answer yes to the second and no to the first.

## 5. Starting a measurement over an existing one

The mirror image, and it needs `C = A` from §3a:

| State of the `.ti3` | Resume ticked | Warning before starting |
|---|---|---|
| None | — | none |
| Partial (`C < A`) | yes | none — this is what resume is for |
| Partial (`C < A`) | no | "This run already holds {n} of {A} patches. Starting without “Refine / resume” replaces them. Tick it to keep them and read only what is missing." |
| Complete (`C = A`) | no | "This chart is **fully measured** — all {A} patches. Starting a new measurement replaces the finished measurement this run's profile was built from. The old one is kept in `old/`, but the profile will no longer match until you build it again." |
| Complete (`C = A`) | yes | "All {A} patches are already read. Resuming will only re-read the ones you scan again." |
| Corrupt (`B ≠ C`, or `C` ≠ the chart's `A`) | either | **W6 — see below** |

**W6 — the measurement and the chart disagree**

> **This run's measurement and its chart do not match**
>
> The measurement file holds {C} readings, and the chart ({stem}.ti2) describes {A} patches. {extra}
>
> ChromIQ cannot tell which of the two is the wrong one. A measurement can be truncated by an interrupted session, and a chart can be replaced or edited outside ChromIQ — both look exactly like this from here.
>
> **What you can do:**
> • **Start a fresh measurement** — the safe choice if this chart is the one you printed. The existing measurement is kept in `old/` and nothing is lost.
> • **Cancel and look at the files first** — the run is at {path}. This run's `chart/` folder holds the copy of the chart that was stored when it was last measured, and Restore Used Chart puts that copy back. There is exactly one; ChromIQ does not keep earlier versions of a chart.
>
> Resuming is not offered, because resuming into a mismatch would write readings against patch positions that may not be the ones on your paper.

where `{extra}` is the second-order detail when the file also disagrees with itself: *"The file's own header claims {B} readings, which does not match the {C} it contains — so this file may be damaged as well as mismatched."*

The wording is deliberately cautious throughout. ChromIQ can see that two numbers disagree; it cannot see **why**, and an interrupted session, a hand-edited file and a file dropped into the wrong folder all look identical from here. Saying "damaged" would be naming a cause the evidence does not support.

## 6. Rebuilding the profile when the run already has verifications

### 6a. What actually changes, and what does not

**Correcting what I wrote before.** I said a trend across a profile change "no longer means anything". That is wrong, and the report is better than that: its metrics were built to be compared across different charts and runs of the same printer. What a rebuild costs is narrower and more precise:

| | Effect of building a new profile under existing verifications |
|---|---|
| The **dated measurements** | untouched — still valid readings of what was on paper that day |
| Their **origin** | lost: each was printed *through* a profile that no longer exists, and nothing on disk records which |
| **Comparability of the numbers** | preserved in kind, but the reference has moved — later dates answer a different question from earlier ones |

The measurements do not become wrong. They become **undocumented**, which is the real damage: a year later nothing says which profile a given date was measured against.

### 6b. What comparing across charts actually costs, in statistics

Knut asked for this to be researched rather than asserted. Two of the report's metric families behave differently when the charts differ in size, and the difference matters:

**Averages are comparable; their precision is not equal.** The standard error of a mean is `SD / √n`, so a 400-patch chart's average ΔE carries **twice** the uncertainty of a 1 600-patch one. The average itself stays an unbiased estimate — it is not "wrong" — but a difference between two dates that is smaller than their combined standard error is not evidence of anything. A trend across charts of different sizes is readable; it is simply noisier on the smaller ones.

**The maximum is not comparable at all, and this one is a bias rather than noise.** The maximum of a sample can only rise as the sample grows: more patches mean more chances to draw from the tail. A 1 600-patch chart will report a higher maximum ΔE than a 400-patch chart *of the same printer, on the same day, with nothing wrong*. So `Maximum ΔE, all patches` must not be compared across charts of different sizes — and it is one of the five metrics carrying a Pass/Fail verdict.

**The percentile metrics sit in between.** `Worst 10%` and `lowest 95%` are order statistics over a fixed *fraction*, so they are far steadier than the raw maximum, but they still drift a little with n because the tail is sampled more finely.

**Which is exactly why a verification history is meant to use one chart** — and why the recommendation is to duplicate the profile run rather than re-base an existing one. Same chart, same size, same reference: the numbers then differ only because the printer did.

### 6c. The other verification tools, across differing charts

| Tool | Compares | Across differing charts |
|---|---|---|
| **Measurement Report** | measured vs the chart's design values, or vs stored reference | comparable, with the caveats above |
| **`profcheck`** (Check & Refine) | a profile against **the data it was built from** | not applicable — it never looks at a verification measurement |
| **Tools ▸ Verify against reference** (`colverify`) | two CIE datasets, patch by patch | **requires matching patch sets**: it pairs by `SAMPLE_ID`, or by `SAMPLE_LOC` with `-l`. Two different charts do not pair, so this tool cannot compare across a chart change at all |
| **Cube corners** (§9a) | nearest patch to eight ideal corners | comparable *only if both charts contain the corners* — which is why §9a makes them mandatory |

So one tool degrades gracefully, one is unaffected, and one stops working outright. That is worth knowing before someone changes a chart mid-history.

### 6d. The warning, and the checkbox

**The build signature idea is dropped.** Knut: *"The main intention is to make user aware, then the user is given authority to act responsibly on an informed basis."* Rebuilding with identical settings is neither dangerous nor the likely case — someone rebuilding has usually changed something, or is testing. Trying to detect "harmless" rebuilds bought precision nobody needed at the cost of machinery and a new file format.

So: **warn whenever a run holds a profile, a verification chart and at least one dated measurement.** Explain, recommend, allow. And add the same escape the "This chart already has a measurement" window has — *"Don't show this again for this run"*, per run and per session, so a testing session is not nagged and a fresh launch warns again.

**W1 — building a new profile under an existing verification history**

> **The verification measurements in this run were made against the profile you are about to replace**
>
> This run holds **{n} dated verification measurement{s}**, going back to {date}. Each was printed **through** the profile in this run and measured against it, so it records how that profile behaved on that day.
>
> Building a new profile here does not make those measurements wrong, and it deletes nothing — but they will no longer say which profile they belong to, and comparing them with verification measurements made afterwards means comparing against two different profiles.
>
> **What each button does:**
> • **Duplicate the run and build there** *(recommended)* — copies this run's chart, measurement and profile into a new run and builds there. This run keeps its profile and its verification measurements exactly as they are, and the copy starts fresh. This is the clean way to try a different profile from the same readings.
> • **Build here anyway** — replaces this run's profile. The current profile is moved to `old/`, and the {n} dated verification measurement{s} are moved to `verifications/old/{date}/` with it, because they describe the profile that is being replaced. Nothing is deleted.
> • **Cancel** — changes nothing.
>
> ☐ Don't show this again for this run

**Why the dated verifications move to `old/` too** — Knut's question, and the answer follows the folder model rather than being invented for this case: a run is meant to hold **one matching set**, chart → measurement → profile → the verifications of that profile. Leaving the old dates in place would break that rule and leave the report to explain a discontinuity for ever. Archiving them keeps the rule intact, keeps every file, and starts the new profile with a clean history — which is what "build here anyway" means.

That also retires the divider idea entirely: with the old dates archived there is no discontinuity left for the report to draw a line through.

### 6e. All the combinations

| # | Profile | Verify chart | Dated verifications | Warning |
|---|---|---|---|---|
| 1 | no | — | — | none — first build |
| 2 | yes | no | — | none — no history to document |
| 3 | yes | yes | 0 | none — a chart with no readings is just a chart |
| 4 | yes | yes | ≥ 1, "don't show again" set this session | none |
| 5 | yes | yes | 1 | **W1** (singular) |
| 6 | yes | yes | ≥ 2 | **W1** (plural) |
| 7 | target is a loaded file, not a run | — | — | none |

No row now depends on knowing whether the profile would differ, which is what the signature was for.

## 7. Every event detected during a read, and where it comes from

Line numbers are from **ArgyllCMS 3.5.0** source (`spectro/`) and from ChromIQ's own helper, found by searching each source for the string the detector keys on. "Detected by" is the pattern in `workflow/measure_manager.py`.

**Reading the "where it is printed" columns:** a dash means that program does not print it at all, which is a fact about the event rather than a gap.

| Event | Detected by | stock `chartread.c` | ChromIQ `chromiq_chartread.c` | `spotread.c` | Correct? |
|---|---|---|---|---|---|
| Strip read OK | `(?:strip\|patch)\s+read\s+ok` | 1909 | 2478 | — | ✅ fixed in beta.123 — it matched only "strip" before |
| Patch read OK | same pattern | 2422 | 3079 | — | ✅ |
| Strip read failed | `Strip read failed[^(]*\(([^)]+)\)` | 1652, 1671, 2222 | 2181, 2205, 2869 | — | ✅ three call sites, one wording |
| Wrong strip read | `Seem to have read strip pass (\w+) rather than (\w+)` | 1854 | 2412 | — | ✅ |
| Unexpected colour response | `unexpected response.*\(DeltaE\s*([\d.]+)\)` | 1887, 2445 | 2451, 3104 | — | ✅ both strip and patch paths |
| Strip read interrupted | `Strip read stopped at user request` | 1608 | 2127 | — | ✅ |
| Patches still unread | `Done\s*\?\s*-\s*At least one unread patch \(([^)]+)\)` | 1593, 2345 | 2108, 2998 | — | ✅ strip and patch paths |
| Ready to read strip | `Ready\s+to\s+read\s+strip` | 1539 | 2010 | — | ✅ |
| Ready to read patch | `Ready to read patch\s+'([^']+)'` | 2115, 2146 | 2753, 2784 | — | ✅ |
| All rows read | `ALL\s+ROWS\s+READ` | 1539 | 2010 | — | ✅ |
| Are you sure | `Are\s+you\s+sure\s+\[y/n\]` | 1593, 2295, 2345 | 2108, 2945, 2998 | — | ✅ |
| Sensor in wrong position | `sensor.*wrong\s+position\|sensor should be in surface` | 1644 | — | — | ✅ second alternative comes from the driver — `munki.c:490` |
| Comms establish failed | `Establishing communications with instrument failed with message\s+'([^']+)'` | 488 | 914 | — | ✅ |
| Instrument init failed | `Initialising instrument failed with message\s+'([^']+)'` | 498 | 924 | — | ✅ **exits 0** — see §7 |
| Instrument mode rejected | `Setting instrument mode failed with error\s*:?\s*'([^']+)'` | 975 | 1409 | 1603, 1618, 2040 | ✅ |
| Capability missing | `Need (reflection\|transmission\|emissive)\s.*?reading capability` | 536, 549, 559 | 970, 983, 993 | 1492 | ✅ |
| Correction file failed | `Setting Colorimeter Correction Matrix failed\|…` | 629 | 1063 | 1696 | ✅ |
| No instrument found | `no instrument detected\|no suitable instruments\|no instruments connected` | 476 | 901 | 1199 | ✅ |
| Chart / instrument mismatch | `Warning:\s*chart is for\s+(\S+),\s*using instrument\s+(\S+)` | 526 | 952 | — | ✅ |
| Generic instrument error | `Got\s+'([^']+)'\s*\(([^)]+)\)\s+error\.` | 391, 396, 1710 | 796, 808, 2251 | 391, 396 | ✅ |
| XY: place sheet | `Please place sheet\s+(\d+)\s+of\s+(\d+)\s+on table` | 1123 | 1576 | — | ✅ |
| XY: sheet read OK | `Sheet\s+(\d+)\s+of\s+(\d+)\s+read OK` | 1325 | 1782 | — | ✅ |

### 7a. Events that do NOT come from these three programs

Three of the windows are driven by strings printed elsewhere, and that is worth recording because it explains why they behave the same in every mode:

| Event | Printed by | Note |
|---|---|---|
| Calibration prompt | `spectro/instappsup.c:289` | shared application-support code — identical in chartread, spotread and the ChromIQ helper, which links the same library |
| Calibration complete | `spectro/instappsup.c:199` | as above |
| Device being used | `spectro/usbio_ox.c:380, 387` (macOS), `usbio_dk.c:544` (Windows) | the USB backend, **per platform**. Line 380 is `a1logd` — a *debug*-level message that may not reach the terminal at normal verbosity, so this one is the least reliable detector in the table |
| Strip may be misaligned | — | **not an Argyll string at all.** It is ChromIQ's own reading of a failed strip plus its reason. `"Bad strip"` exists in Argyll only for the DTP41/DTP20 (`dtp41.c:1026`, `dtp20.c:1251`) and never reaches a ColorMunki or i1 user |

### 7b. What this table changes

1. **`Device being used` is detected in both of its forms**, per Knut: either one raises the "Instrument Not Available" window. The error-level form (`usbio_ox.c:387`) reaches the terminal reliably; the debug-level one (`usbio_ox.c:380`) may not, so the pattern must match both rather than assuming which arrives, and the same window stays reachable from the generic error path as a third route.
2. **`Strip may be misaligned` is ChromIQ's own inference**, so it belongs in ChromIQ's documentation as an interpretation, not as an instrument message.
3. **Everything else is confirmed** against the exact line that emits it, in all three programs.

## M. The message catalogue

*Correcting myself: I referred to texts "marked (to define)", and no table carried such a marker. There was no such marking — the messages simply had not all been written. They are all written below, each with an ID, and every table in this document now names the ID it uses.*

Every window this specification can raise, in one place. **ID → where it is used → the text.**

**Bold in the quoted texts below is this document's typography, not the window's.** The windows show the headline in bold — it is the one line the user must read first — and everything under it at normal weight, because a screen of bold is a wall nobody reads. Emphasis inside a message is therefore carried by the words, and a test fails if a `**bold**` span ever reaches a message string, where it would show on screen as asterisks.

### M-END · ending a measurement — §1, §1a, §2

> **Keep what you have measured so far?**
>
> You have read **{n} patches** in this session. They are not in your measurement file yet — ChromIQ can write them now, or end the session without them.
>
> **What each button does:**
> • **Save and stop** — writes what you have read so far to this run's measurement file and ends the session. You can carry on later with "Refine / resume existing measurement", reading only the strips or patches that are still missing.
> • **Discard and stop** — ends the session and keeps nothing from it. *(when a measurement was already there: "Your previous measurement of {m} patches is put back exactly as it was.")*
> • **Keep measuring** — closes this window and carries on where you were.

### M-END-EMPTY · ending with nothing read — §1 row 5

> **Nothing was measured, so nothing was saved**
>
> This session ended before any patch was read. Your run is exactly as it was: {state}.
>
> *{state} is one of:* "the measurement it already held is untouched" · "it still has no measurement".

### M-TI3-EMPTY · the saved file holds no readings — §3a

> **The measurement file was empty, so it has been put aside**
>
> The file this session wrote contains no readings. It has been moved to `old/{date}/`, and {restored}.
>
> *{restored}:* "your previous measurement of {m} patches has been put back" · "this run has no measurement, as before".

### M-TI3-SHRANK · a resume ended with fewer readings — §3b

> **This session ended with fewer readings than it started with**
>
> The measurement held **{c0} patches** when this session began and **{c}** when it ended. A resume should only ever add readings, so something has gone wrong.
>
> Your earlier measurement has been put back from `old/{date}/`, and the file this session wrote is kept beside it so nothing is lost. Nothing needs doing right now — measure again when you are ready.

### M-TI3-MISMATCH · the measurement and the chart disagree — §5

> **This run's measurement and its chart do not match**
>
> The measurement file holds **{c} readings**, and the chart ({stem}.ti2) describes **{a} patches**. {extra}
>
> ChromIQ cannot tell which of the two is the wrong one. A measurement can be cut short by an interrupted session, and a chart can be replaced or edited outside ChromIQ — both look the same from here.
>
> **What each button does:**
> • **Start a fresh measurement** — the safe choice if this chart is the one you printed. The existing measurement is moved to `old/{date}/` and nothing is lost.
> • **Cancel and look at the files first** — the run is at {path}. This run's `chart/` folder holds the copy of the chart that was stored when it was last measured, and **Restore Used Chart** puts that copy back. There is exactly one; ChromIQ does not keep earlier versions of a chart.
>
> Resuming is not offered here, because resuming into a mismatch would write readings against patch positions that may not be the ones on your paper.
>
> *{extra}, only when the file also disagrees with itself:* "The file's own header claims {b} readings, which does not match the {c} it contains — so this file may be damaged as well as mismatched."

### M-REPLACE-PARTIAL · starting over a partial measurement — §5

> **This run already holds part of a measurement**
>
> {c} of the chart's {a} patches have been read. Starting now without **Refine / resume existing measurement** replaces them.
>
> Tick that option to keep what you have and read only the patches that are still missing. The existing measurement is moved to `old/{date}/` either way, so nothing is lost.

### M-REPLACE-COMPLETE · starting over a finished measurement — §5

> **This chart is fully measured**
>
> All **{a} patches** have been read, and this run's profile was built from that measurement.
>
> Starting a new measurement replaces it. The finished measurement is moved to `old/{date}/` and nothing is deleted — but the profile in this run will no longer match the measurement beside it until you build it again.
>
> *Refine / resume is left exactly as you set it before pressing Start; this window does not change your choice.*

### M-REPLACE-UNCOUNTABLE · a measurement file with nothing readable in it — §3a

*Approved by Knut, 2026-08-04 ("Accepted message"). Why it exists: with §5's partial message this case printed "**0 of the chart's ? patches have been read**", which reads as a fault in ChromIQ rather than a fact about the file. It must also not point at Refine / resume, because there is nothing in the file to resume from.*

> **This run already holds a measurement file**
>
> ChromIQ cannot tell how many readings it contains — the file is there, but it holds no readable measurement data. That usually means a session ended before the first patch was read, or the file was changed outside ChromIQ.
>
> Starting now writes a new measurement in its place. The file you have is moved to the run's "old" folder and nothing is deleted, so you can always look at it afterwards.
>
> Refine / resume is not offered for this file, because there is nothing in it to resume from.
>
> The measurement file is: {path}

### M-CHART-PROFILING · regenerating a chart with work under it — §4

> **This run already holds work made with the chart you are about to replace**
>
> Replacing the chart in this run means what is here no longer describes it:
> {items}
>
> Everything is moved to `old/{date}/` and nothing is deleted — but this run would no longer hold a matching set of files.
>
> **Duplicate the run and make the new chart in the copy** if you want a different chart while keeping this run's work.
>
> *{items} lists only what is actually present:*
> • "a measurement of {c} patches"
> • "the profile built from it"

### M-CHART-W4 · regenerating the chart of a run that has a verification history — §4 (W4)

*The text is §4's W4 block, unchanged; the ID was assigned when the catalogue was moved into `workflow/measurement_messages.py` so that every window could be checked against it.*

> **This would undo the whole run, not just its chart**
>
> Replacing this run's chart breaks the chain three links deep:
>
> • the measurement of {c} patches no longer describes the chart in this run;
> • the profile built from that measurement no longer describes anything on disk;
> • and the {v} dated verification runs under this run were printed through that profile, so they stop describing a profile that exists.
>
> Everything is kept in the run's `old/` folder and nothing is deleted — but the run would no longer hold a set of files that belong together, and its verification history could not be continued.
>
> Duplicate the run and change the chart in the copy if you want a different chart while keeping this one's work and its history.
>
> The `old/` folder is here: {folder}

### M-CHART-NOPAGES · the pages cannot be redrawn — §4a rows 3 and 5

> **This chart's printed pages cannot be recreated**
>
> This chart has no layout recipe (`.channels.json`), so ChromIQ cannot redraw its pages. {pages}
>
> If you have the printed sheets, keep them — they are the only copy. Everything is moved to `old/{date}/` rather than deleted.
>
> *{pages}:* "The {n} page images in this run are the only ones there will be." · "This run has no page images to lose."

### M-CHART-CORRUPT · the run's measurement file cannot be read — §4

*Approved by Knut, 2026-08-04 ("Message M-CHART-CORRUPT is accepted. move into model."). It is appended to M-CHART-PROFILING, in the same window, when the run holds a `.ti3` that is corrupt or empty — the `{items}` list cannot state a count for such a file, and "a measurement of 0 patches" would be false.*

> **The measurement file in this run cannot be read**
>
> It has no readable measurement data in it — no readings, or a structure ChromIQ cannot make sense of. That can happen when a session ended before the first patch was read, or when the file was changed outside ChromIQ.
>
> It is moved to the run's "old" folder rather than deleted. **Look at it there before you measure again** — ChromIQ cannot tell whether it holds anything you would want to keep, and only you can judge that.

*Appended to that when the run also holds a profile:*

> The profile in this run moves to the "old" folder with it. That profile was built from a measurement, and the measurement file that should describe it can no longer be read — so nothing on disk now connects the profile to the chart it came from. ChromIQ cannot tell whether the file was always like this or became so later, and it cannot repair it. Measuring the chart again is the way to get a run whose chart, measurement and profile describe each other once more.

*The `{items}` entry that goes with it:* "•  a measurement file that is corrupt or empty".

### M-PREVIEW-PAUSED · the auto-update preview declines to re-draw — §4

*Approved by Knut, 2026-08-04 ("Accepted message"). The auto-update preview re-lays out the chart in the run, so it is a §4 trigger — but a window on every turn of a layout knob would be unusable. Knut accepted the exception on 2026-08-03 and set the rule: "the popup window … should come once only, then again the next time 'auto-update preview …' is enabled. At the same time it can come in the log window until 'auto-update preview …' is disabled."*

> **The live preview is not being re-drawn**
>
> This run already holds work made with the chart the preview would replace, so the preview is left as it is rather than re-drawn over it.
>
> Press "Generate Chart" when you want the new layout. You will be told exactly what moves to the run's "old" folder first, and nothing is deleted.
>
> This window appears once each time you switch "Auto-update preview" on. While it stays on, the same note goes to the log instead, so your layout work is not interrupted.

### M-DUPLICATE-BLOCKED · Duplicate is recommended but unavailable — §4a, §6

*A paragraph appended to whichever message recommends Duplicate, when the run cannot be duplicated.*

> **Duplicate is not available for this run.** It needs all four of these: the patch list (.ti1), the laid-out chart (.ti2), the layout recipe (.channels.json) and at least one printed page (.tif). This run is missing {missing}.

### M-CHART-VERIFY · replacing the verification chart — §4 (W5)

> **The verification measurements already made in this run used the chart you are about to replace**
>
> The {v} dated verification measurement{s} in this run were all made with this verification chart. Replacing it does not make them wrong, and the report can still compare their figures — but those measurements would no longer have the chart they were made with, so nothing on disk would say what they were readings of.
>
> A trend across the change also compares two different charts, which is not the same measurement made twice.
>
> The chart is moved to `old/{date}/` and no measurement is touched. **Duplicate the run** instead if you want a different verification chart while keeping this run's verification measurements intact.

### M-VERIFY-NO-PROFILE · a verification with no profile to check — §S1.2

*Approved by Knut, 2026-08-04. Raised when Run type = Verification and the selected run has no built profile; also what the greyed Start button's tooltip says. The numbers below are escaped so both halves of the list line up exactly as they do on screen — Knut, beta.132: "the numbered list from 4 to 7 does not have the same indent as points 1 to 3".*

> **This run has no profile to verify yet**
>
> A verification checks a finished profile — but this profile run doesn't have a built profile yet.
>
> To build the profile first:
> &nbsp;&nbsp;1\. Set "Run type" to "Profiling".
> &nbsp;&nbsp;2\. Create, print and measure the profiling chart as normal — its measurement is stored in the run folder.
> &nbsp;&nbsp;3\. Build the profile on the Build Profile tab (this makes the profile's .icc / .icm file).
>
> Once the profile exists, you can verify it:
> &nbsp;&nbsp;4\. Set "Run type" back to "Verification".
> &nbsp;&nbsp;5\. Create a verification chart in the Create Chart tab.
> &nbsp;&nbsp;6\. Print that chart THROUGH the finished profile (with colour management on).
> &nbsp;&nbsp;7\. Measure it here with "Run type" = "Verification" — the result is kept in a dated folder under this run's "verifications" folder.

### M-VERIFY-NO-CHART · a verification with no chart to measure — §S1.3

*Approved by Knut, 2026-08-04. Since beta.128 Start Measurement needs a `.ti2`, so a run without its verification chart meets this as the greyed button's tooltip; the window remains for the case where a chart exists but the profile does not.*

> **No verification chart for this run yet**
>
> This run has a finished profile, but you haven't created its verification chart.
>
> &nbsp;&nbsp;1\. Go to the Create Chart tab and, with "Run type" = "Verification", create the verification chart (a smaller chart is fine).
> &nbsp;&nbsp;2\. Print it through this run's profile (with colour management on).
> &nbsp;&nbsp;3\. Come back here with "Run type" = "Verification" and measure it — the result is stored in a dated folder under this run's "verifications" folder.

### M-PROFILE-VERIFY · rebuilding under existing verification measurements — §6

> **The verification measurements in this run were made against the profile you are about to replace**
>
> This run holds **{n} dated verification measurement{s}**, going back to {date}. Each was printed **through** the profile in this run and measured against it, so each records how that profile behaved on that day.
>
> Building a new profile here does not make those measurements wrong, and it deletes nothing — but they will no longer say which profile they belong to, and comparing them with verification measurements made afterwards means comparing against two different profiles.
>
> **What each button does:**
> • **Duplicate the run and build there** *(recommended)* — copies this run's chart, measurement and profile into a new run and builds there. This run keeps its profile and its verification measurements exactly as they are, and the copy starts fresh. This is the clean way to try a different profile from the same readings.
> • **Build here anyway** — replaces this run's profile. The current profile is moved to `old/{date}/`, and the {n} dated verification measurement{s} are moved to `verifications/old/{date}/` with it, because they describe the profile being replaced. Nothing is deleted.
> • **Cancel** — changes nothing.
>
> ☐ Don't show this again for this run

---

## M-PROPOSED. Messages awaiting review

*Everything in this section is **PROPOSED**, not approved. Proposed messages are flagged in `workflow/measurement_messages.py` with `approved=False`, and `tests/test_message_catalogue.py` fails if that flag is dropped without the model being updated — or if this section still holds a message that has since been approved.*

*Approved and therefore **moved out of this section** into §M above: **M-REPLACE-UNCOUNTABLE**, **M-PREVIEW-PAUSED**, **M-CHART-CORRUPT**, **M-VERIFY-NO-PROFILE**, **M-VERIFY-NO-CHART** (all 2026-08-04).*

### M-BUILD-ELSEWHERE · PROPOSED · the measurement belongs to another run — §6

**When it arises:** Build Profile is pressed while the measurement loaded in the tab sits in a different run's folder from the one the bar shows.
**Why it is needed:** Knut, beta.132, Demo-08 step 10 — *"going to run 5, Build Profile tab. The measurement data field … has a file with path to run 6, not run 5. Pressing Build Profile starts building without any warning. The icc file was then placed in the run6 folder. What happened here? I created a profile for run 6 via standing in run 5."* A profile is written beside the measurement it is built from; nothing said so, and nothing checked.

> **This measurement is not in the run you have selected**
>
> The bar shows {run}, but the measurement loaded here comes from:
> {folder}
>
> A profile is always built beside the measurement it is built from, so pressing Build Profile now writes the profile into that folder — not into {run}. The run you have selected would be left exactly as it is.
>
> **What each button does:**
> • **Build anyway** — builds from this measurement and puts the profile beside it. Choose this when you meant to work on that run.
> • **Cancel** — changes nothing. To build into {run}, load that run's own measurement first: switching "Profile run" in the bar loads it for you when the run has one.

---

### M-x. Which table uses which message

| Table | Rows | Message |
|---|---|---|
| §1 Every way a measurement can end | 1–4, 6–12 | **M-END** |
| §1 | 5 | **M-END-EMPTY** |
| §3a Every state a `.ti3` can be in | empty, header-only | **M-TI3-EMPTY** |
| §3a | `B ≠ C`, `C > A` | **M-TI3-MISMATCH** |
| §3b Judging by C₀ → C | `C = 0` after resume, `C < C₀` | **M-TI3-SHRANK** |
| §4 Chart integrity | chart + `.ti3` (+ profile), Profiling | **M-CHART-PROFILING** |
| §4 | + verifications, Profiling | **M-CHART-PROFILING** then **M-PROFILE-VERIFY** wording folded in — see §8 sequence |
| §4 | Verification run | **M-CHART-VERIFY** |
| §4a validity | rows 3 and 5 | **M-CHART-NOPAGES**, in addition to the §4 message |
| §4a | rows 1, 2, 7, 8 | none |
| §5 Starting over | partial, no resume | **M-REPLACE-PARTIAL** |
| §5 | complete | **M-REPLACE-COMPLETE** |
| §5 | corrupt | **M-TI3-MISMATCH** |
| §6e Rebuilding | rows 5, 6 | **M-PROFILE-VERIFY** |
| §6e | rows 1–4, 7 | none |
| any recommending Duplicate while it is unavailable | — | **M-DUPLICATE-BLOCKED** appended |
| §3a header-only, empty | Start Measurement | **M-REPLACE-UNCOUNTABLE** ✅ |
| §4, trigger = auto-update preview | — | **M-PREVIEW-PAUSED** ✅ |
| §4, run holds a corrupt or empty `.ti3` | Profiling | **M-CHART-CORRUPT** ✅ appended |
| §S1.2, Verification with no built profile | Start Measurement | **M-VERIFY-NO-PROFILE** ✅ |
| §S1.3, Verification with a profile but no verification chart | the greyed Start button's tooltip | **M-VERIFY-NO-CHART** ✅ |
| §6, the measurement is not in the selected run | Build Profile | **M-BUILD-ELSEWHERE** 🆕 |
| §4, chart with no `.channels.json` | — | **M-CHART-NOPAGES** appended |
| §4, run with a verification history | Profiling | **M-CHART-W4** |

✅ = approved by Knut, 2026-08-04. 🆕 = **PROPOSED**, awaiting review — see **§M-PROPOSED**.

**Singular and plural.** Every message that states a count carries two bodies, and the one that reads correctly is chosen — "one dated verification measurement" against "4 dated verification measurements". Knut, 2026-08-03: *"Yes, use house rule with real singular and plural. You do not need to ask about this."* The bracketed "(s)" appears nowhere, and a test fails on it.


## S. Sequences — what happens, in what order, for every entry condition

**The rule this chapter exists to state: one window at a time.** Where a condition raises two, the second is not built until the first has returned. No window is ever opened from inside another's handler, and none is opened from a `showEvent` — a window raised while its parent is still being painted comes up behind it or over the wrong tab, which is how #134 and #130 both started.

Read each row top to bottom: that is the order the code must perform it in.

### S1 · Start Measurement

| # | Condition | Sequence |
|---|---|---|
| S1.1 | no chart loaded | 1 refuse, inline hint. No window. |
| S1.2 | Verification run type, run has no profile | 1 **M-VERIFY-NO-PROFILE** ✅ → 2 return. Nothing is written. Reachable when the run has a verification chart but no profile; otherwise met as the greyed Start button's tooltip. |
| S1.3 | Verification, profile exists, no verification chart | **M-VERIFY-NO-CHART** ✅, as the greyed Start button's tooltip — since beta.128 Start needs a `.ti2`, so this is met before a window can open. Knut, beta.128: *"Start Measurement button is not available, so test cannot be performed."* |
| S1.4 | no `.ti3` | 1 archive step (§2a) is a no-op → 2 record C₀ = 0 → 3 launch |
| S1.5 | `.ti3` partial, Resume ticked | 1 **archive `.ti3` → `old/{date}/`** → 2 record C₀ → 3 launch. No window. |
| S1.6 | `.ti3` partial, Resume **not** ticked | 1 **M-REPLACE-PARTIAL** → 2 *if cancelled, stop here* → 3 archive → 4 record C₀ → 5 launch |
| S1.7 | `.ti3` complete | 1 **M-REPLACE-COMPLETE** → 2 *if cancelled, stop* → 3 archive → 4 record C₀ → 5 launch. Resume is left exactly as the user set it. |
| S1.8 | `.ti3` corrupt (`B ≠ C`) or `C > A` | 1 **M-TI3-MISMATCH** → 2 *Cancel stops here* → 3 on "Start fresh": archive → 4 C₀ = 0 → 5 launch with Resume forced off |
| S1.9 | instrument cannot be opened | 1 launch → 2 detect init failure (§7) → 3 **Instrument Failed to Initialize** → 4 mark failed → 5 no `.ti3` written, archive untouched |

### S2 · During a measurement

| # | Condition | Sequence |
|---|---|---|
| S2.1 | patch/strip read OK | 1 record reading → 2 sound → 3 update preview. No window. |
| S2.2 | any failure window (§1a) | 1 **one** window → 2 its choice is sent to the reader → 3 nothing else opens until it returns |
| S2.3 | two failures in quick succession | 1 first window → 2 *closed* → 3 second window. Queued, never stacked. |
| S2.4 | user presses Stop, nothing read | 1 **M-END-EMPTY** → 2 end. No save prompt — there is nothing to save. |
| S2.5 | user presses Stop, readings exist | 1 **M-END** → 2 Save → graceful protocol per engine · Discard → abort · Keep → return, nothing changes |
| S2.6 | user presses `d` | identical to S2.5 — same window, same three buttons |
| S2.7 | user presses `Esc`/`q` | identical to S2.5 |
| S2.8 | bar / Tools / Preferences clicked | disabled for the duration; tooltip explains. No window. |

### S3 · After a measurement ends

Always in this order, whatever ended it:

| # | Step | Then |
|---|---|---|
| S3.1 | read the resulting `.ti3` → B, C | — |
| S3.2 | C = 0 or no `BEGIN_DATA` | **M-TI3-EMPTY** → move to `old/`, restore the archived copy |
| S3.3 | C₀ > 0 and C < C₀ after a resume | **M-TI3-SHRANK** → restore the archived copy, keep both |
| S3.4 | `B ≠ C` | keep the file, never offer resume, report it |
| S3.5 | otherwise | keep; log "{C − C₀} patches added, {C} in the file" **on screen** |
| S3.6 | verification run | tag `CHROMIQ_VERIFICATION`, file under the dated folder |
| S3.7 | report | offer / refresh the measurement report |

Only **one** of S3.2, S3.3, S3.4, S3.5 can apply, so at most one window follows a measurement.

### S4 · Generate Chart / load a `.ti1` / auto-update

| # | Condition | Sequence |
|---|---|---|
| S4.1 | run empty | 1 generate. No window. |
| S4.2 | chart only | 1 generate, replacing it. No window. |
| S4.3 | chart + `.ti3` (+ profile), Profiling | 1 **M-CHART-PROFILING** → 2 *Cancel stops* → 3 if the chart has no recipe: **M-CHART-NOPAGES** → 4 *Cancel stops* → 5 archive → 6 generate |
| S4.4 | as S4.3 **and** dated verifications exist | 1 **M-CHART-PROFILING**, its `{items}` naming the verification measurements too → 2 *Cancel stops* → 3 M-CHART-NOPAGES if applicable → 4 archive run work **and** `verifications/` → 5 generate |
| S4.5 | Verification run type | 1 **M-CHART-VERIFY** → 2 *Cancel stops* → 3 archive the verification chart → 4 generate |
| S4.6 | any of the above, Duplicate unavailable | the recommendation carries **M-DUPLICATE-BLOCKED** — one window still, not two |

S4.3 and S4.4 are the only place two windows can follow one action, and they are strictly sequential: the second is built after the first returns, and only if the first was accepted.

### S5 · Build Profile

| # | Condition | Sequence |
|---|---|---|
| S5.1 | target is a loaded file, not a run | 1 build. No window. |
| S5.2 | run has no profile, or no verification chart, or no dated measurements | 1 build. No window. |
| S5.3 | run has profile + verify chart + ≥ 1 dated measurement | 1 **M-PROFILE-VERIFY** → 2 Duplicate → duplicate, switch, build there · Build anyway → archive profile **and** `verifications/` → build · Cancel → nothing |
| S5.4 | as S5.3, "don't show again" set this session | 1 build. No window. |
| S5.5 | as S5.3, Duplicate unavailable | **M-DUPLICATE-BLOCKED** appended; the Duplicate button is not offered |


## T. Test plan

**Principle: every row of every table above is a test, and every button in every message is a test.** A specification that is not executable is a wish. The tables give the cases; this chapter says how each is proved.

### T1 · Unit — the decisions, with no UI

Pure functions, no Qt, milliseconds each.

| Group | Cases | Asserts |
|---|---|---|
| T1.1 `.ti3` state | every row of §3a: absent · header-only · `C=0` · `B≠C` · `0<C<A` · `C=A` · `C>A` | the classifier returns the right state for each |
| T1.2 session verdict | every row of §3b: the six C₀→C combinations × resume on/off | the right action: keep · restore · delete-and-restore |
| T1.3 chart validity | all eight rows of §4a | "is there a chart", "can pages be redrawn", "warn or not" |
| T1.4 which message | every row of §M-x | the case maps to the expected message ID |
| T1.5 counting | `.ti2` vs `.ti3` parsing: `NUMBER_OF_SETS` vs actual rows, missing `BEGIN_DATA`, trailing blank lines, CRLF | A, B, C read correctly from real files |
| T1.6 event detection | every row of §7, fed the **exact line from the Argyll source** | the right event fires, and *only* that one |
| T1.7 no false positives | near-miss lines: "Ready to read strip" must not match "strip read ok"; "Strip read failed" must not match either | nothing fires |

### T2 · Integration — the sequences

Driven through the real handlers with a stubbed reader, asserting the **order** of what happens.

| Group | Cases | Asserts |
|---|---|---|
| T2.1 start | every row of §S1 | the exact sequence, in order; nothing written when a guard stops it |
| T2.2 during | every row of §S2 | one window at a time; a second failure queues behind the first |
| T2.3 end | every row of §S3 | at most one window; the right file is on disk afterwards |
| T2.4 chart change | every row of §S4 | S4.3/S4.4 raise two windows **strictly sequentially**, second only if first accepted |
| T2.5 build | every row of §S5 | duplicate-and-build leaves the original untouched |
| T2.6 archive | every path that archives | the original is in `old/{date}/` and readable; **nothing is ever deleted** |
| T2.7 restore | S3.2 and S3.3 | the restored `.ti3` is byte-identical to the archived one |

### T3 · Windows — every message, every button

| Group | Cases | Asserts |
|---|---|---|
| T3.1 appearance | each message ID × each condition that raises it | it appears exactly when the tables say, and not otherwise |
| T3.2 text | each message | the placeholders are filled; no `{name}` reaches the screen; singular and plural both correct |
| T3.3 buttons | each button of each message | it performs the action the text promises — the text is the specification |
| T3.4 default button | each message | the **safe** choice is the default; nothing destructive is triggered by Return |
| T3.5 cancel | each message with a Cancel | disk is byte-identical before and after |
| T3.6 don't-show-again | M-PROFILE-VERIFY | suppressed for that run in that session; a new session shows it again |
| T3.7 never stacked | S2.3, S4.3, S4.4 | at no point are two of these windows open at once |

### T4 · Engine parity

| Group | Cases | Asserts |
|---|---|---|
| T4.1 both engines | every §S2 and §S3 row × {stock, ChromIQ} | the same windows, the same wording, the same `.ti3` outcome |
| T4.2 protocol | Save-and-stop on each engine | the right keys are sent — two `q` · `r`/`d`/`y` · `d`/`y` |
| T4.3 spotread | §9 | appends per patch; no ending window; the count is reported |
| T4.4 modes | strip · patch-by-patch · refine · single patch | each ending route behaves identically within a mode |

### T5 · What cannot be automated

Stated so it is not mistaken for coverage:

- **A real instrument.** Every test above uses recorded output. That the strings still match a live ColorMunki or i1 is checked by Knut's testing, which is why §7 cites the source lines — a wording change in a future Argyll shows up as a failing T1.6, not as a silent regression in the field.
- **Whether a warning reads well.** T3.2 proves the text is complete and correct; only a person can say whether it is understood.
- **Optical judgements** — the bar-icon alignment kind.

### T6 · Order of building

1. **T1** first: the decisions must be right before the sequences can be.
2. **T1.6** before any code changes to detection, using the exact source lines from §7 as fixtures.
3. **T2 and T3** alongside the implementation of each section, section by section.
4. **T4** last, once both engines follow the same path.

No section of this specification is implemented until its row in T1 and T3 is green.


## 8. Fixed in beta.123

| Your report | Cause | Fix |
|---|---|---|
| patch-by-patch Stop loses everything, no warning (row 4) | `_STRIP_OK_RE` matched only "Strip read OK"; stock prints "**Patch** read OK" in patch mode, so nothing was recorded as read and Stop went straight to the kill | the pattern matches both |
| "the instrument no longer responds" (row 14) | chartread exits **0** when it cannot open the device, so this read as success and the error window was never reached | init failure is a failure regardless of exit code; the window leads with "try again first", which your log shows working 16 s later |
| profile bar live mid-measurement | the bar consulted only its *tab* lock | bar, Duplicate, Tools, Preferences all lock; Help stays live |
| "Show the location being edited" OFF did nothing | closing Preferences refreshed a list of widgets the bar was not on | it is now |
| overlay / sounds / click-to-jump under stock chartread | keyed on "a `.ti3` exists" rather than the engine | hidden **and** switched off |
| messages naming Print and Measure for Open .ti2 | the button moved to the masthead | every message names the button and where it is |
| "Loaded chart…" after opening a file already in the project | no distinction between imported and opened-in-place | skipped when nothing was imported |
| Duplicate greyed with no reason | — | tooltip lists all four required files and names which are missing |
| log window too short | fixed 100 px | measured from the font: exactly 9 lines |

**Your two questions on this section, both checked in the code:**

- **"Is the '.ti3 exists' condition still there when the engine is ON?"** Yes — the rule is `show_overlay = has_ti3 and engine_selected`. The engine is a second condition, not a replacement.
- **"The strip label arrows must keep working for stock chartread."** They do, and they were never touched. The arrow follows `stripe_changed`, which stock emits from chartread's own "Ready to read strip pass B" line (`measure_manager.py:1009`) — a different path from the overlay, with no engine test anywhere in it.

## 9. Does any of this transfer to Read single patches (spotread)?

**Partly, and the difference is worth stating: `spotread` does not hold readings in memory.** ChromIQ appends each patch as it is read, so there is no cliff — pulling the plug loses at most the patch in progress. Rows 8/9 do not apply.

What *does* transfer:

| Idea | Transfers? | Why |
|---|---|---|
| One ending window | ➖ | nothing is at risk, so a confirmation would be noise |
| Say what happened, on screen | ✅ | "12 patches saved to …" — the same rule as §3 |
| Archive before starting (§2a) | ✅ | a spot session appends to an existing file, so the pre-session copy is exactly as valuable |
| C₀ → C (§3b) | ✅ | "12 patches added, 47 in the file now" is a true and useful sentence |
| Corrupt-file check (§3a) | ✅ | the file can be damaged by anything, not only by chartread |
| Complete-chart warning (§5) | ➖ | spot reading is not tied to a chart's patch count |

---

