# Unified Measurement Management — Design Specification

> **Revision 2026-08-09 (e) — two approved messages carry a revised print step.**
> **Awaiting review:** M-VERIFY-NO-PROFILE and M-VERIFY-NO-CHART (revised wording only), M-CM-NO-CCTIFF, M-CM-CONVERT-FAILED and M-CM-PROFCHECK-CONVERTED (new, feature A), M-VERIFY-CREATE-NO-PROFILE and M-GAMUT-NO-PROFILE (feature B — wording agreed verbatim with Sebastian on #133, 2026-08-02, listed for the formal record), M-IMPORT-MISMATCH and M-IMPORT-DATE-TAKEN (the Measure tab's IMPORT module; its import-done window was approved by Sebastian 2026-08-10), plus the revised M-CHART-VERIFY (W5, reworked after the 2026-08-10 hardware session) and M-HOW-PRINTED (pairing 3 — the measure-time question for sheets ChromIQ did not print), plus M-ALL-STRIPS-PATCHES-LEFT (new, 2026-08-14 — every strip read while patches inside them are not, #156; both are wording only, their bug fixes are already in the code and speak through the log until these are approved), plus M-NO-INSTRUMENT-FAST (new, 2026-08-13 — Knut's ColorMunki was invisible on older hardware until "Faster instrument connection" was switched off, so that variant of the no-instrument window names the shortcut and carries its switch), plus M-ENGINE-FELL-BACK (new, 2026-08-14 — asked for by Knut on #148: ChromIQ's own measuring engine could not use the instrument, so stock chartread took over, which also silences ChromIQ's measurement sounds without saying so) — all defined in the awaiting-review section below, plus M-PATCHSET-MISSING (new, 2026-08-25 — a loaded patch set that had gone from disk wrote one line to the log and built a different chart, in silence), plus M-PROJECT-EXISTS (new, 2026-08-27 — a typed project name that already names a project on disk adopted it in silence; Knut reported it and Basti ruled on when it may appear and what it may offer, but the WORDING is new and waits here), plus M-PROJECT-REPLACE-CONFIRM and M-PROJECT-REPLACE-FAILED (new, 2026-08-27 — the second look before §S4.7's "Replace it" clears a whole project, and the window for the case where its promise cannot be kept), plus M-CR30-STOCK-READER (new, 2026-08-28, #159 — a CR30 chart carries the honest name the device reports for itself, which stock ArgyllCMS chartread refuses outright, so the window names the Preferences control that fixes it) and M-CR30-READ-ENDED (new, 2026-08-28, #159 — the same refusal seen from the other end: an engine run that fails on a CR30 chart has no second reader to fall back to, so the two existing fallback messages, one of which promises that every measured strip will be kept, must not be shown) and M-CR30-CALIBRATE (new, 2026-08-28, #159 — Basti ruled that ChromIQ triggers the CR30's white calibration itself on both transports, which deliberately reverses a documented safety rule; the window's warning is about which face of the cap meets the aperture, not about magnets) and M-CR30-INSTRUMENT-GONE (new, 2026-08-28, #159 — the instrument unplugged mid-measurement and ChromIQ said nothing at all) and M-CR30-PATCH-GAVE-UP (new, 2026-08-28, #159 — one refused reading used to end a CR30 session for ever in silence; refusals are now re-armed and this is the window for when re-arming keeps failing) and M-CR30-HOW-TO-MEASURE (new, 2026-08-28, #159 — every other instrument reaches its "how to measure" window through `calibration_done`, which cannot fire when ChromIQ supplies the values itself, so a CR30 user was given a spot session with no on-screen instruction at all) — all defined in the awaiting-review section below.
> **Withdrawn, never approved:** the patch-set sibling of the message above was removed on 2026-08-26 without reaching the catalogue. Ticking “Edit patch recipe (override preset)” already opens a window saying the loaded patches will be replaced, and that box is shown for a patch set the user loaded themselves, not only for a built-in preset — so a second window at Generate time would have interrupted a decision the user had already made and acknowledged. Knut, 4.1.3-beta.17: *“there is already a message when clicking the ‘Edit patch recipe’ warning of consequences … that warning should be sufficient for a user.”* Checked against the existing text before removal.

> Both were approved by Knut on 2026-08-04, but one step in each instructed *"(with colour management on)"* — a setting ChromIQ deliberately locks **off** on every print path, so the approved text told the user to do something the app prevents (established in `verification_printing_and_target.md` §1, and A0.1 of its plan). With feature A the instruction has a real control to name — the Print Chart tab's **Colour** row — so that one step is revised and the revision waits in §M-PROPOSED. Every other message in §M remains approved as before: the last, **M-BUILD-ELSEWHERE**, was accepted on 2026-08-04 — *"Message M-BUILD-ELSEWHERE accepted"* — and M-CHART-CORRUPT, M-REPLACE-UNCOUNTABLE and M-PREVIEW-PAUSED the day before. A new message goes to §M-PROPOSED first, and `tests/test_message_catalogue.py` fails if one is added to the code without it.

> **Status:** specification, agreed on [issue #130](https://github.com/itsab1989/ChromIQ/issues/130).
> Written by the ChromIQ assistant, reviewed and directed by Knut (soul-traveller)
> and Sebastian, 2026-08-02/03.
>
> This is the first chapter of what is meant to become ChromIQ's design
> documentation. It covers **the life of a measurement** — how one ends, what is
> written, what is archived, and every warning shown along the way. Later
> chapters can cover the other areas of the app in the same shape: the tables
> here are the contract, and §T says how each row is proved.

> **These specifications are binding.** Knut, 2026-08-06: *"These must always be
> consulted on changing code so that behaviour defined is not violated. And if
> faults are found that do not match with the specification [it] must be
> reviewed and approved."* So: read the relevant document before changing code
> in the area it covers, and if you find behaviour that contradicts it, **report
> it and get the change approved** rather than quietly correcting one side to
> match the other.

## The companion specifications

This chapter covers the life of a measurement. Three further specifications
came out of the same issue and are part of the same contract; Knut asked
(2026-08-06) that each posted analysis and table set be written down as a
specification rather than left in the thread, *"strictly described from what has
been agreed, including fixes that has risen from tests and bugfixes."*

| Document | What it specifies | Thread post |
|---|---|---|
| [`per_run_description.md`](per_run_description.md) | the four description / notes fields: which file a keystroke reaches, what Restore Used Chart puts back, `-D`, and the run lifecycle. §9b and §9c record what the beta.148 and beta.150–157 rounds found | [5190506691](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5190506691) |
| [`measurement_exit_strategy.md`](measurement_exit_strategy.md) | every window that can end a measurement, for stock chartread and the ChromIQ engine, in strip and patch-by-patch mode: the key each button sends, what it does, and whether it follows §1/§1a's single exit | [5206885923](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5206885923) |
| [`per_target_settings.md`](per_target_settings.md) | which settings belong to a target rather than to the installation, and exactly when they are loaded and written | [5206901110](https://github.com/itsab1989/ChromIQ/issues/130#issuecomment-5206901110) |

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

**BUILT — beta.140/141.** Every window in this table offers Save · Discard · Keep
Measuring. Two things had to be settled while building it, and both are rules
now rather than accidents:

- **A window that is already open is never covered by another one.** Every
  during-a-read window signs into one register, so "is one already open?" is a
  question the app can answer — Knut: *"I can also click the instrument button
  more times, and this window comes on top of previous windows, all at the same
  time. This should not be allowed."* Same rule as the instrument-mismatch
  window in beta.136, now applied to all of them.
- **One failure is one window, however many times it is reported.** See §7c.

---

## 1b. The exact sequence each ending sends

Knut, beta.133: *"The save partial and quit and stop buttons worked before. Even
the q and d keys worked before. What is different now? … Update the … document
with the sequences to use to exit windows and measurement session."*

Here is every one, because they are not the same and the difference is not
visible on screen. **Two things decide the sequence: which engine is reading,
and whether a prompt is open.**

### Save Partial & Quit

| Engine | Mode | Where it starts | What ChromIQ sends | What ends it |
|---|---|---|---|---|
| ChromIQ | strip | any | `{"cmd":"quit"}` → the helper answers with the **event** `{"event":"strip_interrupted"}` (and prints the give-up prompt) → `{"cmd":"quit"}` | the helper writes the `.ti3` (`cq_write_ti3_atomic`) and exits |
| ChromIQ | patch | any | the same two commands; the printed line reads *"**Spot** read stopped at user request!"* | as above |
| stock | strip | a failure prompt | `r` → *"Ready to read strip pass X"* → `d` → *"Are you sure [y/n]"* → `y` | chartread writes the `.ti3` and exits |
| stock | patch | a failure prompt | `r` → *"Ready to read patch 'N' at 'LOC'"* → `d` → *"Done ? — At least one unread patch (…) Are you sure [y/n]"* → `y` | as above |
| stock | either | the menu | `d` → *"Are you sure [y/n]"* → `y` | as above |

**Why the first key differs.** A failure prompt reads **any key that is not Esc
or `q` as "retry"** (chartread.c:1652-1654), so a `d` sent there is swallowed
and the reader simply carries on. The retry key has to be spent first, and only
then does `d` reach the menu that raises the saving question.

**In engine mode the second command hangs off the EVENT, not the printed line.**
Prose never reaches the stock parser there — it goes straight to the log — so a
chain waiting for *"Strip read stopped at user request"* waits for ever. Knut,
beta.135, pressing Stop → "Save and stop": *"The session still did not exit."*
The test that covered it called the stock parser directly, which the app never
does in engine mode, so it proved the chain against a path that does not run.

### Skipping the unit that just failed

Two steps, always: the retry prompt has to be answered before anything can
move, because it reads any key but Esc/`q` as *retry*.

| Engine | Mode | What Skip sends | Where the move is flushed |
|---|---|---|---|
| ChromIQ | strip | `{"cmd":"ok"}` → then `f` | on the `strip_ready` event |
| ChromIQ | patch | `{"cmd":"retry"}` → then `f` | on the `spot_ready` event |
| stock | strip | `\r` → then `f` | on *"Ready to read strip pass X"* |
| stock | patch | `\r` → then `f` | on *"Ready to read patch 'N' at 'LOC'"* — **added in beta.137**; the flush hung off the strip line alone, so this was the one combination of the four where Skip acknowledged the prompt and then never moved (Knut, beta.136) |

### Moving about while reading

| Key | stock chartread | ChromIQ engine |
|---|---|---|
| `f` / `b` | one unit forward / back | `{"cmd":"forward"}` / `{"cmd":"back"}` |
| `F` / `B` | ten units (chartread.c:2319-2327) | the helper has no ten-step command, so **ten single steps** are sent |
| `n` | next unread | `{"cmd":"next_unread"}` |
| `g` | go to a patch | `{"cmd":"goto", …}` |
| ← / → | `b` / `f` — **not** the raw arrow sequence | `{"cmd":"back"}` / `{"cmd":"forward"}` |

An arrow key is three characters and the first one is Escape. chartread reads
**one character at a time**, and Escape there is *give up without saving*
(chartread.c:1611, :1654, :1857) — so sending `\x1b[D` for a Left arrow
abandoned the session, and on the engine it matched no command and did nothing.
Both arrows send the keys chartread prints in its own menu (beta.139).

*(The stray semicolon in chartread's own help line — `'B; to move back 10` — is
Argyll's, at chartread.c:2122.)*

### After the ending window, nothing else asks

"Save and stop" is an answer, not a question. Once it has been given, the
session ends and **no further window may open about the same ending** — the old
"Strip Read Interrupted" window appearing behind it was pre-model and is gone
(Knut, beta.137: *"I have already decided to save and stop, so this is what must
happen"*). The helper both prints and reports the give-up prompt; the printed
copy now only completes the chain, never raises a window.

### What the user's own keys do

| Key | ChromIQ engine | stock chartread |
|---|---|---|
| `d` at the menu | asks *"Are you sure"*, then writes | the same |
| `d` at a failure prompt | read as "retry" | read as "retry" |
| space, `r` at a failure or warning prompt | `{"cmd":"retry"}` | *any key that is not Return/Esc/`q`* means retry (chartread.c:1855) |
| `q` / Esc at a failure prompt | the helper **writes the `.ti3` first**, then gives up | **gives up without writing** — `chartread.c:1654` returns −1 and the readings die with the process |
| Stop | §2's window: *Save and stop* runs the sequence above; *Discard and stop* ends the session and keeps nothing | the same |

That last row is the whole reason ChromIQ never sends `q` on stock chartread,
and why the two engines cannot share one sequence.

### What changed, and when

- **beta.139** gave the retry key a command. Every failure and warning window
  spells chartread's *"any other key to retry"* as a **space**; stock chartread
  takes it, but the engine's key→command table had no entry for it, so Retry
  sent nothing and the helper sat at its prompt for ever — Knut, beta.138:
  *"The instrument now stopped responding (no button press reacting and no
  sound), so I cannot measure strips anymore."* It also gave the arrow keys the
  row above, and closed the last door on the duplicate ending window: the
  give-up prompt arrives both as an event and as a printed line, beta.138 
  silenced only the printed one, so whichever arrived **second** still opened a
  window. One per-session flag — *this ending has been answered* — is now set by
  whichever arrives first and checked by both.
- **beta.130** taught the stock path that a failed *strip* read leaves a retry
  prompt open. Before that, Save Partial sent `d` straight into that prompt,
  which ate it — Knut's beta.128 report.
- **beta.138** removed the second window after "Save and stop", let the
  wrong-dial warning be raised again in engine mode (its one-per-prompt flag was
  cleared only on chartread's printed menu line, which the engine never emits),
  and fixed the completion window for a chart with **one** patch left: whether
  the chart was already complete was read from the strip flags, and in
  patch-by-patch a strip whose last patch is unread still reports itself read.
- **beta.137** finished the same story in the two places it still ran out: the
  helper answers the first quit with an **event** in strip mode and with a
  **printed line** in patch-by-patch, and only the event was handled — so
  reading patch by patch, Save Partial & Quit sent one `quit`, which is Esc, and
  the session ended without writing. Both are handled now. It also stopped the
  wrong-dial window opening twice (chartread prints the fault and its reason on
  two lines, and both matched), and gave Skip its missing flush above.
- **beta.136** made the engine's own ending work at all: its give-up prompt
  arrives as an event, and nothing was listening for it, so the second `quit`
  was never sent. It also gave `F` / `B` a meaning in engine mode, and made the
  wrong-dial-position message raise a window in **both** engines and **both**
  modes — chartread prints it as *"Spot read failed due to the sensor being in
  the wrong position"* (chartread.c:1644) even in strip mode, with no
  parenthesised reason, so no other pattern saw it.
- **beta.134** does the same for **patch-by-patch**: its menu line is *"Ready to
  read patch 'N' at 'LOC'"*, which the chain did not recognise, so it walked
  back to the menu and then waited for a line that never came. And the ChromIQ
  engine's patch mode never matched *"Spot read stopped at user request"* at
  all, so its second `quit` was never sent — that one had never worked.

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

**Who answers a file with nothing readable in it — settled 2026-08-04.** Two rules met on the same file. Beta.110: a session that measured nothing archives what it left behind, *"right after measurement session was exited/stopped/completed"*. That had been extended to files merely **found when the Measure tab opens**, which archived them before Start Measurement could mention them — and §3a's two rows above say Start is exactly where they are answered.

Knut's ruling: **"leave as is, use §3a."** So the archive happens at the end of a session, never on tab-open, and a header-only or empty `.ti3` already on disk is met by **M-REPLACE-UNCOUNTABLE** when Start Measurement is pressed. That message is also why the older complaint does not return: it never claims a measurement exists — it says ChromIQ cannot tell how many readings the file contains.

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
| Chart + a `.ti3` that is **corrupt or empty**, no profile | Profiling | a window of its own, naming the file as corrupt or empty | **M-CHART-CORRUPT** ✅ (not M-CHART-PROFILING) |
| Chart + a `.ti3` that is **corrupt or empty**, **and a profile** | Profiling | as above, **plus** what it costs the profile | **M-CHART-CORRUPT** ✅ with its profile paragraph |
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
> • **Cancel** — stops here so you can look at the files first. The run is at {path}. This run's `chart/` folder holds the copy of the chart that was stored when it was last measured, and Restore Used Chart puts that copy back. There is exactly one; ChromIQ does not keep earlier versions of a chart.
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

### 7c. One failure, reported twice — the helper prints it AND sends it (beta.141)

Knut's beta.140 log has it exactly:

```
Patch read failed due unexpected error :'Wrong Sensor Position' (Sensor should be in surface position)
send_key '{"cmd": "ok"}'                                   <- Retry was pressed
{"event":"error","kind":"misread","detail":"Sensor should be in surface position"}
```

The helper **prints** the failure in the same prose stock chartread uses, and
then — once the window it raised has been answered — reports the same failure
again as a **JSON event**. Both parsers were reading independently, so each
raised a window: Instrument Error -> Retry -> Patch Read Failed -> Retry ->
Instrument Error, with no way out but Stop.

**The rule:** while a sensor-position window is open, an event describing that
same sensor position is the failure already on screen, not a new one, and is
dropped. Anything else — a different misread, or the dial being wrong *again*
after the reader has moved on — still opens its own window, because silencing
those was the opposite bug in beta.136. Both directions have tests
(`tests/test_knut_beta140_no_window_loop.py`).

This is the general shape of every engine-parity problem in §7: **the two
parsers see one event, and whichever notices first owns it.**

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

> **Amended 2026-08-08 (Sebastian).** The two bullets used to read *“Start a
> fresh measurement”* and *“Cancel and look at the files first”* — names the
> window has never had. Its buttons are **Measure anyway** and **Cancel**, which
> are Knut's own beta.132 ruling: *“Measurement has not yet started, so it is
> wrong name for the ‘MEASURE AGAIN’ button. Call button instead ‘MEASURE
> ANYWAY’.”* The buttons were right and the message was stale, so the message
> follows the buttons. Nothing else about the message changed. Found by the
> Japanese translator, who looked up every control name the text quotes.

### M-TI3-MISMATCH · the measurement and the chart disagree — §5

> **This run's measurement and its chart do not match**
>
> The measurement file holds **{c} readings**, and the chart ({stem}.ti2) describes **{a} patches**. {extra}
>
> ChromIQ cannot tell which of the two is the wrong one. A measurement can be cut short by an interrupted session, and a chart can be replaced or edited outside ChromIQ — both look the same from here.
>
> **What each button does:**
> • **Measure anyway** — starts a fresh measurement. The safe choice if this chart is the one you printed: the existing measurement is moved to `old/{date}/` and nothing is lost.
> • **Cancel** — stops here so you can look at the files first. The run is at {path}. This run's `chart/` folder holds the copy of the chart that was stored when it was last measured, and **Restore Used Chart** puts that copy back. There is exactly one; ChromIQ does not keep earlier versions of a chart.
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

### M-OVERLAY-NO-MEASUREMENT · the overlay is asked for on a chart that has never been measured — Measure tab

> **This chart has not been measured yet**
>
> There is no measurement file beside this chart, so there is nothing to draw on the patches.
>
> Read the chart with your instrument and the overlay will fill in as you go, showing what you measured against the colour each patch was meant to be.

*Approved by Knut, 2026-08-14: "Text approved. Make Sure to use the guideline
used for other messages, if relevant." Switching to a run that had never been
measured showed **M-TI3-MISMATCH**'s claim — that the measurement was made for a
different chart — about a file that does not exist (#155). Stopping that false
claim was the bug fix; this is the window that replaces it. It is a **window**
and not a log line, per his ruling in the same review: "all events shall have
windows, and not hidden in a log where user will not see it."*

### M-CHART-CORRUPT · the run's measurement file cannot be read — §4

*Approved by Knut, 2026-08-04. **It is the window**, not a paragraph inside another one — his ruling on beta.133: "M-CHART-CORRUPT (ONLY THIS MESSAGE …)". It replaces M-CHART-PROFILING whenever the run holds a `.ti3` that is corrupt or empty, because M-CHART-PROFILING's `{items}` list cannot describe a file whose readings will not count — "a measurement of 0 patches" would be false, and naming it in a list under a headline about matching files says less than the message below says on its own. M-CHART-NOPAGES and M-DUPLICATE-BLOCKED still append to it when they apply; they are about other things.*

> **The measurement file in this run cannot be read**
>
> It has no readable measurement data in it — no readings, or a structure ChromIQ cannot make sense of. That can happen when a session ended before the first patch was read, or when the file was changed outside ChromIQ.
>
> It is moved to the run's "old" folder rather than deleted. **Look at it there before you measure again** — ChromIQ cannot tell whether it holds anything you would want to keep, and only you can judge that.

*Appended to that when the run also holds a profile:*

> The profile in this run moves to the "old" folder with it. That profile was built from a measurement, and the measurement file that should describe it can no longer be read — so nothing on disk now connects the profile to the chart it came from. ChromIQ cannot tell whether the file was always like this or became so later, and it cannot repair it. Measuring the chart again is the way to get a run whose chart, measurement and profile describe each other once more.

*(The `{items}` entry that once went with it is gone: with the message standing on its own there is no list to fill.)*

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

### M-CHART-VERIFY — definition moved to §M-PROPOSED

*The wording was revised after the 2026-08-10 hardware session (Sebastian
saw the old text live and it earned a "needs rework": it ignored the
per-date chart snapshots and its Duplicate advice contradicted its own
"no measurement is touched"). The revision awaits review in the
awaiting-review section below; once approved it returns here. The archive
it promises is now real: ``verifications/old/<date>/``.*

### M-IMPORT-DONE · the import succeeded — Measure ▸ IMPORT

*Approved by Sebastian, 2026-08-10 — seen live in the hardware session
("import worked and the messages were good").*

> **The measurement was imported**
>
> It is filed as this run's verification from {when}, in its own dated folder:
> {folder}
>
> A copy of the chart it was measured against is stored with it, so the result stays interpretable even if the chart is replaced later.
>
> To see the colour-accuracy figures, open Tools ▸ "Measurement report" — the imported measurement is already in place there.

---

### M-VERIFY-SAVED · a verification measurement was saved — Measure

*Approved by Sebastian, 2026-08-10 (delegated: "if you think the text
... is correct, friendly, extensive and easy to understand then use
it"), after using it live in the hardware session.*

*Replaces the completion window's inline text. It promised "colour accuracy"
but only offered the measurement inspector — the accuracy analysis lives in
the measurement report, so the window now offers both doors and says what
each is for (Sebastian, 2026-08-10 hardware session). Buttons: Close · Open
in measurement inspector · Open measurement report (default).*

> **Verification Measurement Saved**
>
> Your verification measurement has been saved as {name}, in its own dated folder.
>
> This file checks a print against a profile — do not build a profile from it. Two ways to look at it:
>
> Measurement report — the colour-accuracy analysis: how close each printed colour landed to what the profile expected, the worst patches, your printer's reach at the cube corners, and — once you have several dated verifications — how the profile holds up over time.
>
> Measurement inspector — the physical portrait of this one print: paper white, contrast, grey cast, and how it behaves under different light.

### M-BUILD-ELSEWHERE · the measurement belongs to another run — §6

*Approved by Knut, 2026-08-04. Raised when Build Profile is pressed while the measurement loaded in the tab sits in a different run's folder from the one the bar shows — his Demo-08 step 10: "I created a profile for run 6 via standing in run 5."*

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

### M-NO-INSTRUMENT · the instrument is not there — §S2

*Knut's own words, written by him in his beta.150 report and used unedited, so
this one is approved by authorship. It replaces the original "No Instrument
Found" bullet list, and it replaces the ten-second window I had proposed as
**M-INSTRUMENT-SILENT** — which is withdrawn:* "I prefer your more detailed
message, but the original 'No Instrument Found' had a few bullets to add."

*Two things about it are his instruction rather than the text. It arrives **5
seconds** after the no-instrument condition is detected — the detection is
unchanged, only the moment it reaches the user, which used to be whenever
chartread happened to exit (about twenty seconds). And its **OK button ends the
session through the one ending every route shares**, so nothing read is lost
and nothing is discarded without being offered:* "All messages that can arrive
during measurement must exit in that safe manner, as a single exit strategy for
all cases."

> **No Instrument Found**
>
> ChromIQ has started the measurement and asked your instrument to wake up, and it has not replied for {n} seconds. A working instrument answers almost at once, so something is in the way.
>
> This is nearly always the connection rather than anything you did. Try these in order:
>
> •  Unplug the instrument's USB cable and plug it back in.
> •  Use a different USB port, and plug straight into the computer rather than through a hub.
> •  Close anything else that may be holding the instrument — another profiling program, or a virtual machine.
>
> Nothing has been lost. The measurement you already had is put back exactly as it was if this session ends without reading anything, and you can keep waiting instead if you would rather.

---

## M-PROPOSED. Messages awaiting review

*This section is where a new or revised message goes: add it to
`workflow/measurement_messages.py` with `approved=False`, write it here, and
list it on the issue. `tests/test_message_catalogue.py` holds the two in step —
it fails if a proposed message is missing from this section, and equally if an
approved one is left sitting in it.*

*The two below are **revisions**, not new messages. Both were approved by Knut
on 2026-08-04, but one step in each instructed "(with colour management on)" —
a setting ChromIQ deliberately locks off on every print path
(`postscript_generator.py`, `cups_printer.py`, `workflow/native_print_macos.py`;
established in `verification_printing_and_target.md` §1). Feature A gives the
instruction a real control to name: the Print Chart tab's **Colour** row. Only
that one step changed in each; every other sentence is the approved text.*

### M-VERIFY-NO-PROFILE · PROPOSED revision · a verification with no profile to check — §S1.2

*Revision of the message approved 2026-08-04: step 6 now names the Print Chart
tab's "Colour" row instead of instructing colour management on. Raised when Run
type = Verification and the selected run has no built profile; also what the
greyed Start button's tooltip says. The numbers below are escaped so both
halves of the list line up exactly as they do on screen — Knut, beta.132: "the
numbered list from 4 to 7 does not have the same indent as points 1 to 3".*

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
> &nbsp;&nbsp;6\. Print that chart from the Print Chart tab with "Colour" set to "Through the profile" — ChromIQ applies the profile for you and keeps the printer's own colour management off.
> &nbsp;&nbsp;7\. Measure it here with "Run type" = "Verification" — the result is kept in a dated folder under this run's "verifications" folder.

### M-VERIFY-NO-CHART · PROPOSED revision · a verification with no chart to measure — §S1.3

*Revision of the message approved 2026-08-04: step 2 now names the Print Chart
tab's "Colour" row instead of instructing colour management on. Since beta.128
Start Measurement needs a `.ti2`, so a run without its verification chart meets
this as the greyed button's tooltip; the window remains for the case where a
chart exists but the profile does not.*

> **No verification chart for this run yet**
>
> This run has a finished profile, but you haven't created its verification chart.
>
> &nbsp;&nbsp;1\. Go to the Create Chart tab and, with "Run type" = "Verification", create the verification chart (a smaller chart is fine).
> &nbsp;&nbsp;2\. Print it from the Print Chart tab with "Colour" set to "Through the profile" — ChromIQ applies the profile for you and keeps the printer's own colour management off.
> &nbsp;&nbsp;3\. Come back here with "Run type" = "Verification" and measure it — the result is stored in a dated folder under this run's "verifications" folder.

### M-CR30-STOCK-READER · PROPOSED · a CR30 chart while Preferences selects stock chartread — Measure

*New message (#159, 2026-08-28). A CR30 chart carries `TARGET_INSTRUMENT
"CR30"` — the honest name the device reports for itself, by ruling. Stock
ArgyllCMS `chartread` matches that keyword against its own instrument table and
refuses the chart before reading a patch, so a CR30 chart is readable only by
ChromIQ's own chartread fork. Raised BEFORE anything is armed, when the loaded
chart is a CR30 and Preferences → Measurement → "Chart-reading engine" is set
to ArgyllCMS chartread. The window offers to change that setting; declining
cancels the measurement rather than starting one that cannot succeed. This is
the guard that keeps `_blocked_by_unusable_target_instrument`'s claim true:
"CR30" is in `KNOWN_INSTRUMENTS`, so that window no longer fires for a CR30
chart — and this one asks the question that is still open.*

> **This chart can only be read by ChromIQ**
>
> This chart was made for the CR30, and ChromIQ reads that instrument itself. Standard ArgyllCMS chartread does not know the CR30 at all — it would refuse the chart before reading a single patch, whichever instrument you have connected.
>
> Right now, Preferences → Measurement has "Chart-reading engine" set to ArgyllCMS chartread. Switch it to ChromIQ's own reader and this chart measures normally. The setting applies to every chart, and every other chart reads the same either way.
>
> Nothing is wrong with the chart, and nothing you have already measured is affected.

### M-CR30-READ-ENDED · PROPOSED · an engine run failed on a CR30 chart, and there is no second reader — Measure

*New message (#159, 2026-08-28). The mirror of M-CR30-STOCK-READER, seen from
the other end of the run. When ChromIQ's own chart-reading engine fails,
`MeasureManager` restarts the measurement on stock ArgyllCMS chartread and says
so (M-ENGINE-FELL-BACK); when it fails partway through a chart it does the same
with `-r` and promises that "every strip you have already measured has been
saved and will be kept". **Neither promise can be kept for a CR30 chart** —
stock chartread matches `TARGET_INSTRUMENT "CR30"` against its own instrument
table, finds nothing, and errors with "Unrecognised chart target instrument"
before the first patch. So all three fallback sites are gated off for such a
chart and the run ends on the helper's own exit. This is what the user is told
instead: one honest ending rather than a rescue that fails a second time.
`{reason}` is the helper's own sentence, captured from its stderr prose — the
same failure used to render as "unknown error".*

> **The measurement stopped**
>
> Reading this chart has stopped before it finished.
>
> This chart was made for the CR30, and ChromIQ reads that instrument itself. There is no second reader to try: standard ArgyllCMS chartread does not know the CR30 and would refuse the chart before reading a single patch, so ChromIQ has not started it and has ended the measurement here rather than showing you a second failure.
>
> Nothing you have already measured is lost — every patch that was read is on disk, and you can carry on from it by ticking "Refine / resume existing measurement" before you press Start again.
>
> What went wrong: {reason}

### M-CR30-CALIBRATE · PROPOSED · calibrate the instrument before the measurement — Measure

*New message (#159, 2026-08-28). **Ruled by Basti**: the window offers a
Calibrate button and ChromIQ triggers the calibration itself rather than asking
for a button press — on **both** transports. EXP-MEAS-004 established the host
trigger over USB; EXP-BLE-012 established it over Bluetooth on 2026-08-28,
after he pushed back on a "no BLE host trigger is known" that turned out never
to have been tested (host trigger 3.9222 %R against his own button press
3.9416 %R on the same surface, 0.0347 %R apart).*

*This **deliberately reverses** the documented rule that a ChromIQ backend never
sends the trigger command. That rule existed because the host cannot see a
magnet and so cannot tell a measurement from a calibration; here the calibration
is the whole intention. His ruling, his instrument.*

*The warning is **not** about magnets. The magnet is what makes the command a
calibration at all — telling the user to keep magnets away would tell them to
remove the thing the operation requires. The hazard is **which face of the cap**
is at the aperture: calibrating against the cap's green side is what corrupted
the research unit (81.10 → 149.10 %R), and the error is one-sided and invisible
in every reading afterwards.*

*It must not claim success. When the magnet gate engages the device reports the
firmware's nominal tile constant whatever is under the aperture — white tile and
green face come back bit-identical, max absolute difference across all 31 bands
0.0 — so there is nothing to check, no number worth showing, and no tick or
green mark may appear. The window is shown on every Start unless the run's
`disable_initial_cal` is set, which is hard-coded False in Guided and is the
existing "Skip initial calibration" box in Manual, exactly as he ruled.*

*The calibration reading is **not** counted as a measurement, and that needs no
enforcing: the window runs before the helper is started, so no prompt is
outstanding and there is nowhere for a value to go.*

> **Calibrate your CR30 before measuring**
>
> Your instrument takes a white calibration before it measures a chart. It takes a couple of seconds and ChromIQ does it for you — there is no button to press on the instrument.
>
> Put the magnetic cap on the measuring end, with the WHITE TILE facing the opening. The cap is reversible and the other side is green, so it is worth a glance: white towards the instrument.
>
> Then press "Calibrate now".
>
> ChromIQ cannot check the result for you. The instrument reports the same value whatever is under the cap, so a calibration against the green side looks exactly like a good one and would quietly shift every reading that follows. Your eyes are the only check there is.
>
> If you would rather not calibrate now, press Cancel — nothing has been changed and any measurement this run already has is untouched.

### M-CR30-INSTRUMENT-GONE · PROPOSED · the instrument stopped answering mid-measurement — Measure

*New message (#159, 2026-08-28). Basti unplugged the CR30 mid-session and
**ChromIQ said nothing at all**, then froze for three minutes when he tried to
stop. The spot workflow spends nearly all its time with nothing arriving,
because it is waiting for a human to press a button — so "no frame yet" is the
normal state, and a bare catch-all treated a transport that had GONE as that
same normal state. The two are now told apart (`DeviceLost`), and this is what
the user is told about the second. It deliberately does **not** say "press the
button again": that is the advice for a refused reading and it is the wrong
advice for an instrument that is not there. The promise about nothing being
lost is real and checked — the helper writes the measurement file after every
single patch (`chromiq_chartread.c`, `cq_write_ti3_atomic` in the external-value
branch). `{loc}` is the patch being read; `{reason}` is the underlying failure.*

> **The instrument stopped answering**
>
> ChromIQ has lost contact with your CR30 while measuring patch {loc}.
>
> This is not something you did wrong, and nothing you have measured is lost — every patch you have already read is written to your measurement file as it is read, so all of it is safe on disk.
>
> The usual causes, in the order worth checking:
>
> •  The USB cable came out, or the instrument was switched off.
> •  Over Bluetooth, the instrument moved out of range or its battery ran down.
> •  Something else took the instrument — the phone app holds it exclusively while it is connected.
>
> Reconnect it, then start the measurement again with "Refine / resume existing measurement" ticked: ChromIQ will offer you only the patches that are still missing.
>
> What went wrong: {reason}

### M-CR30-PATCH-GAVE-UP · PROPOSED · one patch was refused again and again — Measure

*New message (#159, 2026-08-28). A reading can be refused for good reasons: the
magnetic cap left on, the instrument lifted too early, a reading identical to
the last one. Until now a single refusal **ended the session for ever, in
silence** — `_start_read` is reached only from a new `spot_ready`, which the
helper sends only when it receives a command, so a failure that re-armed nothing
left no reader running and no prompt ever coming again, while the screen still
said "press the button on the instrument again". The likeliest first-run mistake
there is — starting a chart with the cap still on, which is where the cap lives
when the instrument is idle — reached it every time. Refusals are now re-armed,
so pressing again genuinely works; this window is for when that has been tried
several times and is still failing, so the user is not left pressing a button
with nothing changing. `{loc}` is the patch; `{reason}` is what the instrument
reported.*

> **That patch could not be read**
>
> ChromIQ has tried several times to read patch {loc} and each attempt was refused, so it has stopped asking rather than leave you pressing the button with nothing changing on screen.
>
> Everything you have already measured is safe on disk.
>
> The two things that cause this, and both are quick to check:
>
> •  The magnetic cap is still on the instrument. That is where the cap lives when the CR30 is not in use, so it is an easy one to miss — and with a magnet at the opening the instrument does not measure at all. Take the cap right off and put it aside.
> •  The instrument was lifted before it had finished. Hold it flat on the patch until it has beeped.
>
> When you have checked those, end this session with "Save and stop" and start it again with "Refine / resume existing measurement" ticked — you will be offered only the patches that are still missing.
>
> What the instrument reported: {reason}

### M-CR30-HOW-TO-MEASURE · PROPOSED · the spot session's instructions, when ChromIQ supplies the values — Measure

*New message (#159, 2026-08-28). Every other instrument reaches its "how to
measure" window through `MeasureManager.calibration_done`, which
`tab_measure._on_calibration_done` answers — and that handler is the **only**
route to `ui.ti2_loader.patch_measurement_instructions_html`. When ChromIQ
supplies the readings itself the helper is run with `-x`, opens no instrument,
and `cq_handle_calibrate` sits inside `if (xtern == 0)`, so `calibration_done`
can never fire. A CR30 user therefore got a spot session with **no on-screen
instruction at all**. This window is shown once when such a measurement starts,
in place of that one. It carries the two things a CR30 user needs that no other
instrument's user does — take the magnetic cap OFF, and nothing on screen has
to be pressed — plus `{how}`, the instrument's own steps from
`patch_measurement_instructions_html`, which gained its `cr30` branch in the
same change (it previously fell through to the generic "as described in its
manual").*

> **Ready to measure, patch by patch**
>
> ChromIQ reads your CR30 itself, so the measurement is driven from here rather than by ArgyllCMS.
>
> {how}
>
> The patch to read is highlighted in the preview, and the highlight moves on by itself as each reading arrives. You can click any patch in the preview to jump to it, and ChromIQ keeps every reading as it is taken, so you can stop and continue later without losing anything.

### M-PATCHSET-MISSING · PROPOSED · the loaded patch set is no longer on disk — Create Chart

*New for 4.1.3-beta.16. Shown when "Generate Chart" is about to lay out a patch
set the user opened earlier and that file can no longer be found. Until now this
path wrote one line to the log and built a completely different chart. Modal,
one button; the build does not start. `{path}` is the file ChromIQ was looking
for.*

> **The patch set you loaded is no longer there**
>
> ChromIQ was going to lay out the patch set you opened earlier, but that file cannot be found any more — it may have been moved, renamed or deleted since you loaded it:
>
> {path}
>
> Nothing has been changed. The chart already in this run is untouched, and no new chart has been made.
>
> To carry on, choose one of these:
> • Open the patch set again with the patch-grid icon at the top right of this tab, and pick the file from wherever it is now.
> • Choose a ready-made patch set from the "Presets" list.
> • Or let ChromIQ work out a fresh set of colour patches for you: tick "Edit patch recipe (override preset)" and click "Generate Chart".

### M-PROJECT-EXISTS · PROPOSED · the typed project name is already a project — Create Chart

*New for 4.1.3. **Nothing in this model governed it.** §4 governs what a RUN
holds; nothing governed which PROJECT a typed name lands on. So typing the name
of a project you already have adopted that project in silence and built into its
current run — Knut, 2026-08-27: "there is no warning message that this project
already exists, with choice to overwrite or cancel, and message to change to a
different name … Nothing shall ever be lost and user shall always be notified if
there is a risk of overwriting a project."*

*Raised at build time — Generate Chart, a preset, a loaded patch set, an applied
editor chart, a from-profile-gamut build — when the name in "Printer profile
project name" resolves to a project that exists on disk, is not the project
already open, **and holds something**. An existing project that is empty raises
nothing: there is nothing to lose, and a window there would be a nag. In every
case, empty included, a line appears under the name box saying which project the
name now points at; that line is hidden whenever the name does not match one, so
its appearing is itself the signal (Basti's ruling, 2026-08-27).*

*It is **never** raised from the live auto-update preview, which may not open a
window (§4) and no longer adopts an uncommitted name at all.*

*This window ALSO carries §4's answer for the run it names, so one action still
opens one window — see §S4.6.*

*`{name}` is the sanitised project name (the folder that will really be used),
`{folder}` its path, `{runs}` how many runs it has, `{cal}` the one extra
sentence when the project has a calibration of its own, `{chosen}` the run the
picker is on, and `{holds}` what that run holds.*

> **There is already a project called “{name}”**
>
> ChromIQ found it here:
> {folder}
>
> That name is already taken, so building now would carry on inside that project rather than start a new one. A project keeps its work in runs, and each run holds one finished profile. This one has {runs}.{cal}
>
> You can choose below which run the new chart goes into. {chosen} holds:
>
> {holds}
>
> Nothing has been changed yet. Choose what you would like to do:
>
> •  Continue this project: the new chart is made in the run named in the box below. Anything that chart replaces is moved to that run’s “old” folder first, with today’s date on it, so you can always get it back. Choosing a new run adds a fresh, empty one and leaves everything already in the project exactly as it is.
>
> •  Replace it: everything the project holds now is moved into its own “old” folder, with today’s date, and a new, empty project of the same name is started. Nothing is deleted, and ChromIQ asks you to confirm before it does it.
>
> •  Use a different name: nothing is touched, and ChromIQ takes you back to the name box so you can type another one.
>
> •  Cancel: stops here and changes nothing.

Buttons: **Continue this project** · **Replace it** · **Use a different name** ·
**Cancel**. The default is **Cancel** — a Return keypress must never be an
overwrite.

The picker below the text is labelled **"Make the new chart in:"** and offers
**"A new run (nothing already there is touched)"** first — the default, because
it is the one answer that cannot cost anything — followed by every run the
project has, oldest first. `{chosen}` and `{holds}` follow the picker as it
moves. `{runs}` is *"one run"*, *"{n} runs"*, *"{n} runs, one of them with work
in it"* or *"{n} runs, {f} of them with work in them"*.

`{holds}` is a LIST, not a sentence — joining the parts with commas and a final
"and" would need the comma and the conjunction to be translatable too, and word
order differs enough across the thirteen languages that the result would be
wrong somewhere. It is built from these lines and from nothing else (house rule:
real singular and plural, never "(s)"):

> •  a chart
> •  a measurement
> •  a built profile
> •  one dated verification check          ← when there is exactly one
> •  {n} dated verification checks         ← when there is more than one

Only the lines that apply are shown. When none of them do:

> •  nothing yet: no chart, no measurement and no profile

That is the line the window shows by default, because the picker starts on
**a new run** — a run that does not exist yet holds nothing. It is also what a
project shows when every one of its runs is empty, and THAT case raises no
window at all: only the line under the name box.

`{cal}` is empty, or this one sentence — a calibration belongs to the PROJECT,
not to a run, so it is stated with the project rather than listed under
"A new run holds:", where it said something plainly untrue:

> It also has a calibration of its own, shared by every run.

### M-PROJECT-REPLACE-CONFIRM · PROPOSED · the second look before a project is cleared — Create Chart

*New for 4.1.3, with §S4.7. Basti, 2026-08-27: "Keep it but require a second
confirmation". "Replace it" is the only control in the app that clears a whole
project from the Create Chart tab, and three of the six data-loss faults found in
the first implementation were about it — so it is never one click away from a
window somebody opened by accident. Default button: **Go back**.*

> **Start “{name}” again from empty?**
>
> Everything this project holds is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays inside the project, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.
>
> After that, a new and completely empty project of the same name is started in the same place, and your new chart is made in its first run.
>
> If what you wanted was to ADD to this project rather than start it again, go back and choose “Continue this project” instead. That leaves everything where it is.

Buttons: **Replace it** · **Go back**, default **Go back**.

### M-PROJECT-REPLACE-FAILED · PROPOSED · the Replace could not be carried out — Create Chart

*New for 4.1.3, with §S4.7. "Replace it" promises that everything is moved into
the project's own "old" folder and that nothing is deleted. When the move cannot
be made — a read-only folder, a share that has gone away, a file another program
holds open — the promise is not kept, and this says so. The archive is
all-or-nothing: anything already moved is put back before this window appears,
and the build does not go ahead. `{folder}` is the project, `{reason}` the error
the operating system gave.*

> **The existing project could not be moved aside**
>
> ChromIQ was going to move everything in this project into its own “old” folder before starting a fresh one of the same name, and it could not:
>
> {folder}
>
> Nothing has been changed. Anything that had already been moved has been put back, and no new chart has been made.
>
> The reason given was:
> {reason}
>
> This usually means the folder is read-only, is on a disk or a share that is no longer available, or holds a file another program still has open. Close anything that might be using it and try again, or choose “Use a different name” and leave this project alone.

### M-CM-NO-CCTIFF · PROPOSED · the profile-applying tool is missing — feature A, §3.2 A10

*New with feature A (`verification_printing_and_target.md` §6 S9). Shown when
"Through the profile" is chosen but `cctiff` is not in the configured
ArgyllCMS folder. Nothing is printed.*

> **ChromIQ cannot find the tool that applies your profile**
>
> To print this chart through your profile, ChromIQ uses a program called cctiff, which comes with ArgyllCMS. It is not in the ArgyllCMS folder ChromIQ is set to use.
>
> You can still print this sheet raw — choose "Raw — no profile" above — but measuring it will tell you about your printer rather than about your profile.
>
> To fix it: open Preferences and check that the ArgyllCMS folder is the one you installed, then come back to this tab.

### M-CM-CONVERT-FAILED · PROPOSED · a page could not be converted — feature A, §3.2 A11/A12

*New with feature A (`verification_printing_and_target.md` §6 S10). Shown when
a page's conversion fails or times out; the whole job stops and nothing is
printed. `{reason}` carries cctiff's parsed error, so an unreadable or non-RGB
profile (A12) names itself.*

> **This sheet could not be prepared**
>
> ChromIQ was working out the ink amounts your profile predicts for page {n} of {total}, and that did not finish. Nothing has been printed and nothing has been changed.
>
> The most common reason is that the profile file is damaged or is not a printer profile. Rebuilding the profile on the Build Profile tab usually fixes it.
>
> Details: {reason}

### M-CM-PROFCHECK-CONVERTED · PROPOSED · Check & Refine on a print-time-converted sheet — feature A, §2b

*New with feature A (`verification_printing_and_target.md` §2b, test T13).
`profcheck` pushes the chart's device values through the profile, so those
values must be what was printed. A sheet converted at print time still has the
unconverted values in its chart file — the check would produce confident,
meaningless figures, and nothing downstream could tell. Shown before the check
runs; Cancel is the default button.*

> **This measurement came from a sheet printed through the profile**
>
> This check pushes the chart's own numbers through the profile and compares the answer with what you measured. That only means something when the chart's numbers are what was actually sent to the printer.
>
> This sheet was printed with "Colour" = "Through the profile", so ChromIQ converted the numbers before printing — the chart file still holds the unconverted ones. The check would run without complaint and produce confident figures, but they would not describe your profile or your printer.
>
> To judge this measurement, use the Measurement Report instead — it compares against the right reference. To use this check, print the verification chart raw and measure that sheet.
>
> **What each button does:**
> • **Run the check anyway** — runs the check on these files unchanged.
> • **Cancel** — changes nothing.

### M-VERIFY-CREATE-NO-PROFILE · PROPOSED · Create Chart, verification with no profile — #133 §10

*Feature B. The wording was agreed VERBATIM with Sebastian on #133
(2026-08-02), before this review queue existed; it is defined here so the
formal record is complete. Shown as the non-blocking info box at the foot of
Guided / Manual while Run type = Verification and the run has no built
profile — those modules stay fully usable.*

> **There's no finished profile in this run yet**
>
> You can go ahead and create the chart — the files will be ready and waiting for you. Printing and measuring it will have to wait for the profile, though: a verification chart is printed through your finished profile, and that's the whole point of it. Measuring one without a profile is turned off for the same reason.
>
> To get there: set Run type to Profiling, then create, print and measure the profiling chart as usual and build the profile on the Build Profile tab. Come back here afterwards and everything will be ready for you.

### M-GAMUT-NO-PROFILE · PROPOSED · the From-profile-gamut module with no profile — #133 §10

*Feature B, same provenance as the message above. Shown INSTEAD of the
module's options, with Generate disabled — the profile's gamut is this
module's input, so without one there is nothing to ask.*

> **This run needs a finished profile first**
>
> This way of making a chart asks your profile which colours it believes your printer can produce, and then tests exactly those. {run} doesn't have a profile yet, so there's nothing to ask.
>
> How to get one:
> &nbsp;&nbsp;1\. Set Run type to Profiling.
> &nbsp;&nbsp;2\. Create, print and measure the profiling chart as usual.
> &nbsp;&nbsp;3\. Build the profile on the Build Profile tab.
> &nbsp;&nbsp;4\. Come back here and set Run type to Verification again.
>
> GUIDED and MANUAL can still build you a chart in the meantime, so the files are ready. Printing and measuring any verification chart waits for the profile either way.

### M-IMPORT-MISMATCH · PROPOSED · an imported file fails validation — Measure ▸ IMPORT

*The IMPORT module (verification runs) files a measurement made in i1Profiler
through the same doors a native measurement uses — but only after checking,
patch by patch, that the file belongs to this run's verification chart.
`{reason}` names the failed check in plain words (patch counts, or the
patch-identity comparison).*

> **This file does not match the verification chart**
>
> Before filing anything, ChromIQ checks that the measurement really belongs to this run's verification chart — and this one does not:
>
> {reason}
>
> Nothing has been imported and nothing has been changed.
>
> The two usual causes: the file belongs to a different chart, or the patches came back in a different order than they were sent — that can happen when the shuffled i1Profiler export was used for measuring. Use the chart's normal export (the file without "shuffled" in its name), measure again, and import that.

### M-IMPORT-DATE-TAKEN · PROPOSED · importing over an existing dated result — Measure ▸ IMPORT

*The import never replaces an existing dated measurement; the way to a fresh
check is the same field a native measurement uses.*

> **This verification already holds a measurement**
>
> The verification from {when} already has its measurement, and importing over it would replace a result you may still need.
>
> Nothing has been imported and nothing has been changed.
>
> To file this measurement as a new check, set the "Verification" field in the bar above to "New verification" and press Import Measurement again — it gets its own dated folder, and the earlier result stays exactly as it is.

### M-CHART-VERIFY · PROPOSED · replacing the verification chart — §4 (W5), revised wording

*Revised after the 2026-08-10 hardware session; the previous approved text
claimed the displaced measurements would "no longer have the chart they
were made with" (untrue — every measured date snapshots its chart) and its
Duplicate advice contradicted its own "no measurement is touched". The
M-DUPLICATE-BLOCKED note was stripped of its four-file jargon at the same
time.*

> **The verification measurements already made in this run used the chart you are about to replace**
>
> The {v} dated verification measurement{s} in this run were made with this verification chart. Replacing it does not make them wrong — each date keeps its own stored copy of the chart it was measured with, so every result stays readable, and "Restore Used Chart" can bring a date's chart back on screen.
>
> One thing to keep in mind: a trend across the change compares two different charts, which is not the same measurement made twice.
>
> The chart itself moves to the "old" folder inside "verifications"; no measurement is touched and nothing is deleted. If you would rather keep measuring the current chart, duplicate the run first — it lives on in the copy.

### M-HOW-PRINTED · PROPOSED · asking how an unrecorded verification sheet was printed — Measure tab, at save time

*New with pairing 3 (the media-relative yardstick, agreed with Knut and
Sebastian 2026-08-10). Shown once, just before the saved/imported window,
only when a verification measurement is being filed and its sheet has no
print record — ChromIQ's own prints and answered sheets are never asked
again. Buttons: **Raw — no profile** · **With colour management** ·
**Not sure** (default). The answer is written into the dated folder's
print record with `recorded: "asked-at-measure"`; Not sure leaves the
sheet unrecorded, exactly as today.*

> **How was this sheet printed?**
>
> ChromIQ did not print this sheet itself, so it does not know whether a profile took part — and the measurement report needs to know, because the two kinds of sheet are judged differently.
>
> Raw — no profile: the chart's own numbers went straight to the printer, with every colour setting off. Measuring it checks the printer, not a profile.
>
> With colour management: the sheet was printed from another application (for example Photoshop) with this run's profile applied. Measuring it checks your whole everyday printing chain, and the report judges it relative to the sheet's own paper white — so the paper is not counted against the profile.
>
> Not sure is always safe: the report simply notes that the printing method is not recorded, and judges the colours as they are. Your answer is stored with this measurement only — it changes nothing else.

### M-ALL-STRIPS-PATCHES-LEFT · PROPOSED (revised 2026-08-14) · every strip read, but patches inside them are not — Measure tab

> **Some patches are still unread**
>
> Every strip has been read, but {n} patches still have no reading. Everything you have read so far is safe.
>
> This usually happens when some patches were read one at a time in **Patch-by-patch mode** and a few were stepped over.
>
> To finish them, start measuring again with **Patch-by-patch mode** ticked and **Refine / resume existing measurement** ticked. ChromIQ picks up where the readings stop, so you only measure the patches that are still missing rather than the whole chart again.
>
> • **Re-read Individual Strips** — stay in this session and read a strip again now. Use **f** and **b** to move between strips, **n** to jump to the next unread one, and **d** when you are done.
>
> • **Close** — finish here. ChromIQ asks whether to keep what you have measured so far, so nothing is decided behind your back.

*Revised after Knut's review of the first draft (2026-08-14), which he corrected
on three counts.*

**1. The cause was wrong.** The first draft said *"a slight wobble as the
instrument passes over them is enough"*. His answer: *"is not likely. if not
enough patches are registered it is caught. The likely reason is that a user has
used patch-by-patch mode to read some patches and missed some."* The message now
says that instead. Nothing here asserts a mechanism that has not been observed.

**2. The button was invented.** The first draft told the user to press
**"Stop & Save"**, which is not a button this app has. His answer: *"The button
'Stop & Save' is not the wording used for other windows … like the All Patches
Read (for patch-by-patch mode) and All Strips Read (for strip mode) [which] have
one button to Close, which calls the window where user decides to stop and save,
or stop and discard. This is the unified exit method defined in the design spec,
which you would have known."* He is right that it is defined, and right that I
should have read it: `measurement_exit_strategy.md` §"The single exit".

**3. Every button needs its own explanation** — *"the rules used in the design
specification is that all windows have an explanation for each button in a
window"* — so both now carry one.

**It must exist in all four cases.** Strip mode and patch-by-patch, on ChromIQ's
engine and on stock ArgyllCMS chartread, are four separate windows with different
exit keys behind the same buttons (`measurement_exit_strategy.md`, Tables 1 and
2). A window raised from one parser only reaches half the users, and the stock
half working is what has hidden that four times already. So this window is to be
raised from code both `_handle_line` and `_handle_engine_line` reach, and its
Close must delegate to `_confirm_end_of_session`, which already knows which mode
and which reader it is in rather than sending a key of its own.

**4. It is a STRIP-MODE window, so its button re-reads strips.** The first
revision offered "Re-read Patches", which he corrected: *"this message is for a
strip mode session (and this message only happens during strip mode), not a
patch-by-patch session. Here one would 'Re-read strips'."* The button now matches
the completion window it stands in for, and the guidance in the body still points
at patch-by-patch + resume, because that is how the missing patches get finished
in a later session — which he approved separately.

**Close — ruled 2026-08-14.** He answered **(A)**: *"Close should raise the 'Keep
what you have measured so far?' window. However, the description 'keeps the
measurement, goes nowhere' is still correct, because it is referring to the other
button that says to jump to build profile tab."* So the row in
`measurement_exit_strategy.md` is not stale — it was read against the wrong
button. Close raises the ending; the Go-to-tab button is the one that keeps the
measurement and moves on.

**Both readers, per his instruction:** *"If this check is possible to implement
for the stock argyllcms chartread engine also, then the button commands should be
made to use the correct command for the specific chartread engine, according to
the measurement exit strategy in the design specification. Use the All Strips
Read window for each engine as basis for the correct action to use to re-read or
to Close / exit."* So both buttons take their keys from the All Strips Read row
of Table 1 (engine) and Table 2 (stock) rather than sending anything of their
own.

### M-ENGINE-FELL-BACK · PROPOSED · ChromIQ's own measuring engine could not use the instrument — Measure tab

> **Measuring with ArgyllCMS instead**
>
> ChromIQ's own measuring engine could not use your instrument this time, so the measurement has been started again using ArgyllCMS's chartread. Carry on measuring exactly as you would normally — nothing you have already read is lost.
>
> One thing changes while this is running: **ChromIQ's measurement sounds are silent.** ArgyllCMS makes its own beeps as it reads, and playing ChromIQ's sounds on top would double every one of them. The beeps you hear are coming from ArgyllCMS.
>
> Reason: {reason}

*Why it is proposed rather than in use.* Knut asked for it directly (#148,
2026-08-14): *"there should be a defined and approved instrument error message in
the design specification for this error, is there not? I think there should be a
warning message so the user knows."* He is right that there is none — the
fallback is announced only in the measurement log
(`workflow/measure_manager.py`, `engine_fell_back_resumed`), which is easy to
miss mid-measurement.

*Why the second paragraph matters as much as the first.* The fallback silently
changes a second thing: `SoundManager.play` deliberately suppresses every
per-patch and per-strip sound while stock chartread is driving, because chartread
beeps for itself and cannot be silenced (Knut's own ruling, #131 2026-07-27). So
a user whose engine falls back loses ChromIQ's sounds for the rest of that
measurement, is told nothing about it, and has every reason to report it as the
sound feature being broken — which is one of the two things being untangled in
#148. The suppression itself is correct and stays; what is missing is saying so.

Until this is approved, the fallback continues to write its line into the
measurement log, and `core.sound` now logs each suppressed sound with the reason,
so a log can at least distinguish "deliberately quiet" from "audio broken".

### M-NO-INSTRUMENT-FAST · PROPOSED · the instrument is not there, and the connection shortcut is on — §S2

*The same moment as M-NO-INSTRUMENT, and the same text, plus one paragraph.
Knut, 2026-08-13: his ColorMunki was found on a 2023 MacBook Pro and not on a
2019 one — in strip mode, patch-by-patch and Read Single Patches alike — and
switching off "Faster instrument connection" was the whole fix:* "That did it…
Now it works. Maybe the No Instrument detected message could warn about this
setting?" … "warning about this setting not working on all computers,
especially some older hardware, might be good. And suggesting to also test
connecting without that setting."

*Two things about it are instruction rather than text. The window carries the
switch itself —* "Maybe the pop-up should have this option linked already so
the user does not have to go to preferences to find it" *(Sebastian; Knut:*
"Sounds ok"*) — as a **Turn off faster connection** button beside OK, which
sets the preference and leaves the session ending exactly as before. And the
paragraph names where the option lives for later (Sebastian: Preferences ▸
Measurement), so someone who wants the shortcut back can find it. Which of the
two messages is shown follows the preference: with the shortcut off, Knut's
original text is unchanged.*

> **No Instrument Found**
>
> ChromIQ has started the measurement and asked your instrument to wake up, and it has not replied for {n} seconds. A working instrument answers almost at once, so something is in the way.
>
> This is nearly always the connection rather than anything you did. Try these in order:
>
> •  Unplug the instrument's USB cable and plug it back in.
> •  Use a different USB port, and plug straight into the computer rather than through a hub.
> •  Close anything else that may be holding the instrument — another profiling program, or a virtual machine.
>
> One more thing is worth trying, and it is the likeliest cause on an older computer. ChromIQ is using a shortcut called “Faster instrument connection”: it skips the ports an instrument is never plugged into, so the calibration prompt appears sooner. On some computers that shortcut is what stops the instrument being found at all. The button below turns it off straight away — then start the measurement again, and your instrument will very likely be found. Nothing else about your measurements changes, and you can switch it back on whenever you like in Preferences ▸ Measurement, where it is called “Faster instrument connection”.
>
> Nothing has been lost. The measurement you already had is put back exactly as it was if this session ends without reading anything, and you can keep waiting instead if you would rather.

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
| §4, run holds a corrupt or empty `.ti3` | Profiling | **M-CHART-CORRUPT** ✅ — the window itself, replacing M-CHART-PROFILING |
| §S1.2, Verification with no built profile | Start Measurement | **M-VERIFY-NO-PROFILE** ✅ |
| §S1.3, Verification with a profile but no verification chart | the greyed Start button's tooltip | **M-VERIFY-NO-CHART** ✅ |
| §6, the measurement is not in the selected run | Build Profile | **M-BUILD-ELSEWHERE** ✅ |
| §4, chart with no `.channels.json` | — | **M-CHART-NOPAGES** appended |
| §4, run with a verification history | Profiling | **M-CHART-W4** |

✅ = approved by Knut, 2026-08-04. 🆕 = **PROPOSED**, awaiting review — see **§M-PROPOSED**.

**Singular and plural.** Every message that states a count carries two bodies, and the one that reads correctly is chosen — "one dated verification measurement" against "4 dated verification measurements". Knut, 2026-08-03: *"Yes, use house rule with real singular and plural. You do not need to ask about this."* The bracketed "(s)" appears nowhere, and a test fails on it.


## I. The IMPORT module — a measurement made in i1Profiler — Confirmed behaviour

**Confirmed by:** Sebastian, 2026-08-10 — hardware session: a real ColorMunki
measurement imported via the module ("done, import worked and the messages
were good"); filing, chart snapshot, marker keyword and untouched original
verified on disk. M-IMPORT-DONE approved the same day; M-IMPORT-MISMATCH and
M-IMPORT-DATE-TAKEN remain in §M-PROPOSED (their windows were verified in the
on-screen drive but not yet read by a human).

*Built 2026-08-09 (#133). A third mode on the Measure tab — GUIDED · MANUAL ·
IMPORT — shown only while the shared Run type is **Verification**. It files a
measurement made outside ChromIQ (typically i1Profiler with an i1iO table)
through the same doors a native verification read uses.*

The sequence, in the order the code performs it (`TabMeasure._on_import_measurement`):

| # | Step | On failure |
|---|---|---|
| I.1 | "New run" guard (same window as Start) | stop, nothing written |
| I.2 | Verification guard — **M-VERIFY-NO-PROFILE** / **M-VERIFY-NO-CHART** | stop, nothing written |
| I.3 | A chosen dated verification that already holds its measurement → **M-IMPORT-DATE-TAKEN** | stop, nothing written — an import never replaces a result |
| I.4 | Convert to `.ti3` into `runs/runN/cache/import/` (`.mxf`/`.cxf` read directly; `.txt` via txt2ti3; a `.ti3` passes through). The user's original is never touched. | one window with the converter's reason |
| I.5 | Validate: patch count against the run's verification chart, then the patch-identity comparison the report itself uses → **M-IMPORT-MISMATCH** | stop, nothing written |
| I.6 | The same dated-folder + chart-snapshot front door as a native read (`_snapshot_verification_chart`): creates the folder on "New verification", moves the bar to it, asks before replacing a differing stored chart | user cancel stops the import |
| I.7 | Copy to `verifications/<date>/<name>-verify.ti3`, stamp `CHROMIQ_VERIFICATION "true"` | log line, nothing half-written |
| I.8 | **M-IMPORT-DONE**, with a button straight into the measurement report | — |

Deliberate limits (v1): an import never replaces an existing dated result
(the road to a fresh check is the bar's "New verification", exactly as for a
native read); a partial measurement (fewer patches than the chart) is refused,
not filed; profiling and calibration runs cannot import at all — a profile is
built only from a measurement made here.

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
| S2.9 (beta.141) | the same failure arrives twice — once printed, once as an event (§7c) | 1 first arrival opens the window → 2 the second is recognised as the failure already reported and is **dropped**. A genuinely different failure still opens its own window |
| S2.10 (beta.141) | a second failure arrives while a window is open | 1 nothing stacks on top → 2 it waits, per S2.3. Enforced by the register, not by each window remembering to check |

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
| S4.7 · **PROPOSED** | the typed project name resolves to a **different** project that exists on disk **and holds something** — in ANY of its runs (not only the current one), or its shared calibration | 1 **M-PROJECT-EXISTS**, listing every run and defaulting its picker to **a new run** → 2 *Cancel / Use a different name stops* → 3 Replace it → **M-PROJECT-REPLACE-CONFIRM** → *Go back stops* → archive the whole project into its `old/` and start a fresh one · Continue this project → adopt it, point the Profile-run bar at the run the picker names → 4 generate. For **Profiling**, S4.1–S4.4 do not also fire: M-PROJECT-EXISTS carries §4's answer for the run it names. For **Verification** and **Calibration** they DO — see below. When the project is EMPTY in every run, no window at all: only the line under the name box. |

S4.3 and S4.4 are the only place two windows can follow one action, and they are strictly sequential: the second is built after the first returns, and only if the first was accepted.

**S4.7 replaces S4.1–S4.4, and only those.** It describes the run's *profiling*
artefacts — a chart, a measurement, a profile — which is what M-CHART-PROFILING
would have said, so for a Profiling build one action still opens one window. It
knows nothing about the verification charts under `verifications/` or about the
calibration in `cal/`, so for **Run type = Verification** it does NOT stand in
for S4.5, and for **Run type = Calibration** it does not stand in for the
calibration question: the specific one follows it. That is a second window for
one action, and it is recorded here rather than left to be discovered.

**⏳ Awaiting confirmation.** Whether two windows are right for those two run
types, or whether M-PROJECT-EXISTS should instead grow a verification and a
calibration variant, is a decision about the model.
**Confirmed by:** *nobody yet.*

**Why S4.1–S4.5 could not answer this on their own.** They are all evaluated against *the run*, and until 4.1.3 they were evaluated **before** the typed name was applied — so when a name adopted a different project, the question was answered about the run the app happened to be on, not the one about to be written. S4.7 resolves the name first and asks about the project the build will really touch.

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

