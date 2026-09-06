# Unified Measurement Management — Design Specification

> **Revision 2026-08-09 (e) — two approved messages carry a revised print step.**
> **Awaiting review:** M-VERIFY-NO-PROFILE and M-VERIFY-NO-CHART (revised wording only), M-CM-NO-CCTIFF, M-CM-CONVERT-FAILED and M-CM-PROFCHECK-CONVERTED (new, feature A), M-VERIFY-CREATE-NO-PROFILE and M-GAMUT-NO-PROFILE (feature B — wording agreed verbatim with Sebastian on #133, 2026-08-02, listed for the formal record), M-IMPORT-MISMATCH and M-IMPORT-DATE-TAKEN (the Measure tab's IMPORT module; its import-done window was approved by Sebastian 2026-08-10), plus the revised M-CHART-VERIFY (W5, reworked after the 2026-08-10 hardware session) and M-HOW-PRINTED (pairing 3 — the measure-time question for sheets ChromIQ did not print), plus M-ALL-STRIPS-PATCHES-LEFT (new, 2026-08-14 — every strip read while patches inside them are not, #156; both are wording only, their bug fixes are already in the code and speak through the log until these are approved), plus M-NO-INSTRUMENT-FAST (new, 2026-08-13 — Knut's ColorMunki was invisible on older hardware until "Faster instrument connection" was switched off, so that variant of the no-instrument window names the shortcut and carries its switch), plus M-ENGINE-FELL-BACK (new, 2026-08-14 — asked for by Knut on #148: ChromIQ's own measuring engine could not use the instrument, so stock chartread took over, which also silences ChromIQ's measurement sounds without saying so) — all defined in the awaiting-review section below, plus M-PATCHSET-MISSING (new, 2026-08-25 — a loaded patch set that had gone from disk wrote one line to the log and built a different chart, in silence), plus M-PROJECT-EXISTS (new, 2026-08-27 — a typed project name that already names a project on disk adopted it in silence; Knut reported it and Basti ruled on when it may appear and what it may offer, but the WORDING is new and waits here), plus M-PROJECT-REPLACE-CONFIRM and M-PROJECT-REPLACE-FAILED (new, 2026-08-27 — the second look before §S4.7's "Replace it" clears a whole project, and the window for the case where its promise cannot be kept), plus M-CR30-STOCK-READER (new, 2026-08-28, #159 — a CR30 chart carries the honest name the device reports for itself, which stock ArgyllCMS chartread refuses outright, so the window names the Preferences control that fixes it) and M-CR30-READ-ENDED (new, 2026-08-28, #159 — the same refusal seen from the other end: an engine run that fails on a CR30 chart has no second reader to fall back to, so the two existing fallback messages, one of which promises that every measured strip will be kept, must not be shown) and M-CR30-MAGNET (new, 2026-08-30, #159 — a magnet recalibrated the instrument mid-chart, which happened to Basti with a MacBook under his paper; the session now stops and offers to retake the white calibration instead of inviting another press) and M-CR30-CALIBRATE-BLACK (new, 2026-08-29, #159 — the dark reference, taken against open air with the instrument's own command, offered by an unticked per-use checkbox so it never becomes a second window on every Start) and M-CR30-CALIBRATE (new, 2026-08-28, #159 — Basti ruled that ChromIQ triggers the CR30's white calibration itself on both transports, which deliberately reverses a documented safety rule; the window's warning is about which face of the cap meets the aperture, not about magnets) and M-CR30-INSTRUMENT-GONE (new, 2026-08-28, #159 — the instrument unplugged mid-measurement and ChromIQ said nothing at all) and M-CR30-PATCH-GAVE-UP (new, 2026-08-28, #159 — one refused reading used to end a CR30 session for ever in silence; refusals are now re-armed and this is the window for when re-arming keeps failing) and M-CR30-HOW-TO-MEASURE (new, 2026-08-28, #159 — every other instrument reaches its "how to measure" window through `calibration_done`, which cannot fire when ChromIQ supplies the values itself, so a CR30 user was given a spot session with no on-screen instruction at all) and M-CR30-READ-FAILED (new, 2026-08-30, #159 — a refused reading was announced only in the log, where Basti did not see it; the behaviour was already right and only the place it was said was wrong, so this is a modeless window that closes itself when the reading arrives) and M-CR30-LEARN-TILE (new, 2026-08-30, #159 — the magnet guard recognised one unit's stored white-tile value because it was hard-coded from that unit; every other owner had no protection at all, so ChromIQ now learns it from a single capped press) and M-CR30-TRIGGER-NOT-ARMED (new, 2026-08-30, #159 — taking the reading from the keyboard is measurably steadier than pressing the instrument's button, but a reading ChromIQ asks for cannot report the magnet gate, so it is refused until that instrument's tile is known), plus M-IMPORT-REPLACE-CONFIRM, M-IMPORT-REPLACE-PROJECT-CONFIRM and M-IMPORT-REPLACED-KEPT (new, 2026-08-31 — importing a measurement or a chart under a name that is already a project asked the question in each loader's own words AND with its own consequence: one said “Overwrite existing folder” and destroyed the project outright, the other said “Replace” and archived it. Basti ruled that the consequence and the vocabulary are shared with §S4.7 while the window stays the loaders' own, because theirs carries a name box and a live “this name is taken” line that §S4.7's has no room for; the third message exists because nothing anywhere told the person where their replaced project had gone) and M-INSTRUMENT-BUSY (new, 2026-09-02, #159 — Tools ▸ Read single patches now reads a CR30 with ChromIQ's own driver, which is the first time two windows can reach for one instrument; every existing guard answers from process state and cannot see a reader that spawns no process, and the instrument hands its last reading to whoever asks, so the fault it prevents is a plausible wrong colour rather than an error), plus M-SPOT-CLEAR and M-SPOT-UNSAVED (new, 2026-09-03 — Tools ▸ Read single patches could throw a whole measuring session away in silence by two separate routes: Clear had no question and no undo, and Close, the red window button and Escape all discarded the readings without a word. Knut found the first of them by pressing the spacebar, which the Measure tab uses as the reading trigger), plus M-SCAN-REF-SHORT, M-SCAN-REF-DISAGREES, M-SCAN-CLIPPED and M-SCAN-PROFILE-ARCHIVED (new, 2026-09-03 — review 5 of Tools ▸ Build profile with scanner or camera found the app building a profile from data that is not the chart it thinks it is, with every indicator on screen green: a reference file holding a correct SUBSET of the target builds from a sixth of the sheet and scores BETTER on colprof's own self-check than the correct build, an upside-down scan passes every pre-build check, and a scan with two of every five patches clipped to white builds clean and silent. The mechanisms are in the code and can ship ahead of these words; the fourth message says where a rebuilt profile's predecessor went, now that it is archived instead of overwritten), plus M-SCAN-DARK, M-SCAN-FIT-UNSUPPORTED and M-SCAN-SELFCHECK-UNUSABLE (new, 2026-09-04 — beta 8 items B8-01 and B8-03, the two places where the same window tells the user a bad profile is a good one. Every guard in it is scale-invariant and an exposure slip is pure scale, so an under-exposed scan passes all of them in silence and builds a profile 21.7 ΔE out; and colprof's self-check is measured against the rows it was fitted to, so it is smallest exactly when there is least to fit — a one-colour reference scores a perfect 0.007 and a profile whose white point is nan is not checked at all, both ending "Install it as your scanner's input profile"), plus M-SCAN-LOADED and M-SCAN-DIAGNOSTIC (new, 2026-09-03, beta 8 items B8-16 and B8-15 — the same window said nothing at all when a scan was loaded, so a 24-patch photograph loaded under a 288-patch target left an empty log and a live Run button; and it accepted one of ArgyllCMS's own diagnostic images as a scan, which Knut did in his beta.7 log, and then reported a misplacement that was not real about a read that had been fine), plus M-SCAN-ALIGN-NO-BETTER (revised wording only, 2026-09-04, beta 8 item B8-42 — the headline is unchanged and approved; the body used to describe the recogniser alone, and the merged placement button reaches this ending only when the search AND the reshaping have both declined, so it now says both and names “Check alignment”, the one check in the window that can tell a grid one whole patch out from the right answer), plus M-SCAN-CONVERTED and M-SCAN-FIT-TOO-FAR (new, 2026-09-04, beta 8 — the photograph path, revised the same day for B8-42's merged placement button. The window offers “a scan or photo” and Argyll reads TIFF only, so a camera JPEG aligned perfectly on screen and then failed inside scanin; and a sheet that is bowed AND photographed at an angle is read wrongly at its own corners — measured over 48 bow × lens × tilt conditions, each distortion alone costs nothing and two together put 102 patches over 1 ΔE00, which is why the four corners can now be reshaped onto the patches under a bound of three quarters of a patch pitch. Four further messages written for that button on the same day are WITHDRAWN, never having been approved — they are named and accounted for in the awaiting-review section below, and they went with the button itself, which B8-42 merged into Auto align), plus M-SCAN-ALIGN-NOT-SEATED (revised wording, 2026-09-04, beta 8 items B8-02 and B8-42 — Auto align's seventh refusal, and the first one about geometry rather than colour. The quad it is able to return is always a rotated rectangle, so a sheet photographed off square gets a grid that is systematically wrong — and every check it had looks at the chart's COLOURS, which a shear does not disturb because the patches keep their brightness order while sliding onto their neighbours. Measured at 8 degrees of compound tilt: 20 of 23 targets accepted, ten of them more than half a patch out, while the window printed “agrees … to 0.98” beside its own sentence “anything below 0.80 is refused”. Its body is reworded for B8-42 because the placement it refuses may now have come from reshaping the user's own corners rather than from the recogniser, so “it found the chart, but …” would not always be true), plus M-SCAN-SHOT-EMPTY and M-SCAN-TARGET-CHANGED (new, 2026-09-04, beta 8 item B8-32 — two silences in the same window found by the regression sweep: an averaging slot left empty is dropped without a word, so the window shows “Scan 2 of 2” while the build reads one scan and averages nothing; and changing the Target type discards the loaded scan, its placement and every other shot on the page, into a log that is cleared in the same block), plus M-SCAN-WP-DEFAULT (new, 2026-09-05 — the white-point handling a scanner or camera profile is built with moved from “Map chart white to white” to “Scale white to a perfect white surface” (`colprof -u -R`), because the old default clipped every original brighter than the test chart's own white board — 84 % reflectance on the scan it was measured from — irreversibly onto white, at no gain in accuracy. Basti ruled that existing remembered settings adopt the new default rather than being pinned to the old one: “our user base is not very big at the moment so i want the better default”. The RULING is his; this message is the announcement that goes with it, and its wording is new and waits here) — all defined in the awaiting-review section below.
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
> • **Save and stop** — writes what you have read so far to this run's measurement file and ends the session. You can carry on later with "Refine / resume existing measurement (-r)", reading only the strips or patches that are still missing.
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
> • **Save and stop** — writes what you have read so far to this run's measurement file and ends the session. You can carry on later with "Refine / resume existing measurement (-r)", reading only the strips or patches that are still missing.
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
> {c} of the chart's {a} patches have been read. Starting now without **Refine / resume existing measurement (-r)** replaces them.
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

### M-CAL-REPLACE-CHART · replacing a calibration chart nobody measured — Create Chart, Run type = Calibration

**Approved by:** Basti, 2026-09-02, together with M-CAL-REPLACE-MEASURED and
M-CAL-ARCHIVED-HERE, as one approval.

**Why it was rewritten.** It used to say *"Nothing is deleted: the chart you
have now moves to the project's “cal/old” folder … and you can go back to it at
any time."* On 2026-09-02 Basti was given three options for what should happen
to a replaced calibration chart and chose **option 3** — *"Keep it only if it
was measured; experiments leave nothing"* — against a recommendation to keep the
last one. That made the old sentence false, so the behaviour and this text
landed together. Two strict `xfail`s held the branch shut in between, rather
than let the window promise something the code no longer did.

Shown when `cal/` holds a chart and `Calibration.exists()` is false — no `.ti3`
and no `.cal`. That is narrower than what the code keeps
(`Calibration.result_files()`, which also counts an `.icc` and a
`.ti3.engine-partial`), and the direction is deliberate: this window can say
"not kept" over a calibration that is in fact kept, and can never say "kept"
over one that is dropped.

> **Replace this project's calibration chart?**
>
> *(bold first line)* You already made a calibration chart for this project, but it has not been measured yet.
>
> Generating a new one replaces it, and the chart you have now is not kept. Nothing has been measured from it, so ChromIQ treats it as an attempt rather than as work to go back to. This is what a profile run does with a chart you have not measured.
>
> Once a calibration has been measured it is never replaced this way: the measurement, the calibration file made from it and the chart that produced them all move to the project's “cal/old” folder, and nothing is deleted.
>
> If you want to keep this chart, press Cancel and copy the “cal” folder somewhere else first.
>
> **Buttons:** *Replace the chart* · *Cancel*

### M-CAL-REPLACE-MEASURED · replacing a finished calibration — Create Chart, Run type = Calibration

**Approved by:** Basti, 2026-09-02. **The wording is unchanged** — it was
drafted at `docs/design/calibration_run_type_plan.md:240` and option 3 did not
touch the measured branch. What changed is where it lives: the window is
governed in one place now instead of half of it, so a future edit to one branch
cannot quietly leave the other saying something else.

Shown when `Calibration.exists()` — a `.ti3` or a `.cal` is there.

> **Replace this project's calibration?**
>
> *(bold first line)* This project already has a finished calibration, and generating a new chart starts that work again from the beginning.
>
> You would need to print the new chart and measure it before this project has a calibration once more.
>
> These move to the project's “cal/old” folder, in a folder named with today's date — nothing is deleted, and you can go back to them at any time:
>   •  the calibration chart
>   •  its measurement
>   •  the calibration file (.cal) made from it
> {runs_line}
>
> **Buttons:** *Replace the calibration* · *Cancel*

`{runs_line}` — real singular and plural, never "(s)"; omitted entirely when no
run recorded this calibration, because absent means unknown:

> • one run → "Run 3 was built using this calibration. It is not changed, and its profile keeps working, but it was made with the calibration you are about to replace."
> • more → "Runs 3, 5 and 6 were built using this calibration. They are not changed, and their profiles keep working, but they were made with the calibration you are about to replace."

### M-CAL-ARCHIVED-HERE · where a replaced calibration went — the Create Chart log

**Approved by:** Basti, 2026-09-02.

Not a window: two lines written into the log the build is already streaming
into, because that is where a person is looking when it happens.
`Calibration.reset()` returned the archive folder and every caller discarded it,
so M-CAL-REPLACE-MEASURED promised "a folder named with today's date" and the
app then named it nowhere — true and unfindable. Found by the adversarial round
of 2026-09-02.

Shown only when an archive was really made. An unmeasured chart is dropped, so
there is no folder to name and nothing is said.

> **The calibration that was here has moved to this folder, and nothing in it was deleted:**
>
> {folder}

### M-IMPORT-NOT-OPENED · the copy is filed and ChromIQ is not in the project — the import door

*Approved by Basti, 2026-09-02. New for 4.1.5, round 2 of the import-door review (2026-09-02, findings T1-A,
T1-B and T1-C). The new-project door has three ways to end with the measurement
copied to disk and the app still standing outside the project it was copied
into: no `project.json` above the copy, an open that was attempted and failed
(a truncated manifest, which `save_manifest` writes non-atomically, so it is an
ordinary accident), and no Create Chart tab to perform the open with. All three
ended in a `log.warning`, no window, and a bar that said "Load a profile
project" about a project ChromIQ had just made — the exact fault the door was
rewritten to remove. The person is told the one thing they cannot work out for
themselves: where the file is.*

> **The measurement is filed, but the project could not be opened**
>
> Nothing has been lost. Your own file is untouched where it is, and the copy ChromIQ made is here:
>
> {folder}
>
> ChromIQ could not open that project afterwards, so it is not the project you are working in, and the bar at the top still shows the one you were on.
>
> The reason: {reason}.
>
> That folder is an ordinary folder. Everything ChromIQ put in it, including the measurement you have just imported, is there and can be opened like any other folder on your computer. Once the reason above is dealt with, use “Open Project” at the top left of the window to go there.

`{reason}` is one of three, and each is written out here because the reviewer
sees the sentence, not the code:

* *there is no project.json in that folder or above it, so ChromIQ has nothing to open*
* *the project could not be read ({error})*
* *the Create Chart tab, which performs the Open Project step, is not open*

### M-IMPORT-FOLDER-EXISTS · the typed name is a folder and not a project — the import door

*Approved by Basti, 2026-09-02. New for 4.1.5, round 2 (finding T1-D). The window decided "already a project"
from the folder merely existing, so the one window the door still opens for a
plain folder arrived asserting, in red, that the folder is a project — about
the folder whose NOT being one is the only reason that window opens at all.
The consequence and the vocabulary follow M-IMPORT-REPLACE-CONFIRM, which Basti
ruled on for the project case on 2026-08-31; only the claim about what is there
differs, because what is there is different.*

> **There is already a folder called “{name}”**
>
> ChromIQ found it here:
>
> {folder}
>
> It is not a ChromIQ project: there is no project.json in it. Nothing has been changed yet.
>
> •  Type a different name, and ChromIQ starts a new project under that name instead. Nothing in the folder above is touched.
>
> •  Replace it: everything in that folder is moved into its own “old” folder, with today’s date on it, and a new and empty project of the same name is started in its place, with what you are importing in its first run. Nothing is deleted, and ChromIQ asks you to confirm before it does it.
>
> •  Cancel: stops here and changes nothing.

The form this takes on screen today is the live line under the name box, which
is a fragment of the message above and the twin of the sentence shown when the
name really is a project:

* *“{name}” is a folder you already have, and it is not a ChromIQ project. Choose a different name, or click “Replace it”.*

### M-IMPORT-REPLACE-FOLDER-CONFIRM · the second look before a plain folder is moved aside — the import door

*Approved by Basti, 2026-09-02. New for 4.1.5, round 2 (finding T1-D). The twin of M-IMPORT-REPLACE-CONFIRM
for a folder that is not a project: the same act, the same promise, and no
claim that what is being moved aside is a project.*

> **Move everything in “{name}” aside?**
>
> That folder is not a ChromIQ project, and everything in it is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays where the files were, so you can open it at any time and take anything back out of it.
>
> After that, a new and completely empty ChromIQ project of the same name is started in the same place, and {subject} you are importing is put into its first run.

### M-IMPORT-REPLACE-FOLDER-FAILED · that move could not be made — the import door

*Approved by Basti, 2026-09-02. New for 4.1.5, round 2 (finding T1-D). The twin of M-PROJECT-REPLACE-FAILED,
which said “The existing project could not be moved aside” about a plain
folder — driven against a read-only folder that held one text file.*

> **That folder could not be moved aside**
>
> ChromIQ was going to move everything in this folder into its own “old” folder before starting a project of the same name in its place, and it could not:
>
> {folder}
>
> Nothing has been changed. Anything that had already been moved has been put back, and nothing has been imported.
>
> The reason given was:
> {reason}
>
> This usually means the folder is read-only, is on a disk or a share that is no longer available, or holds a file another program still has open. Close anything that might be using it and try again, or type a different name and leave that folder alone.

### M-SCAN-ALIGN-AMBIGUOUS · Auto align cannot tell which way up the sheet is — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. Auto align hands the scan to
ArgyllCMS's own chart recogniser, scores the answer against this chart's
reference, and either places the grid on it or changes nothing. It refuses for
six distinct reasons, and the module names them the way a program wants them
named — `ambiguous-orientation`, `below-floor`, `not-recognised`,
`no-usable-candidate`, `no-chart-geometry`, `no-better`. Those names belong in
the log file and in the tests. The first implementation printed them in
brackets in the middle of the sentence the user reads, which is what these six
messages replace.*

*All six open with the same line, because after a refusal the first thing the
user needs to know is that they have lost nothing: the four corners they placed
by hand are exactly where they left them, and the button was safe to press.*

*This one: a rectangle of patches maps onto itself when it is turned, so more
than one orientation scores the same and picking one of them at random would
read every patch as another patch and build a confidently wrong profile.*

> **Auto align left your corners exactly where they are**
>
> This chart's patches look the same whichever way round it is turned, so ChromIQ cannot work out which way your scan was made. If you know it needs turning, use the “⟳ Rotate 90°” button below the preview. Otherwise drag the four corners onto the chart yourself, which always works.

### M-SCAN-ALIGN-NO-MATCH · what Auto align found does not agree with the reference — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. The recogniser found a chart and
the placement scored below the agreement floor of 0.80, which is the same
question M-SCAN-REF-DISAGREES asks of a finished read, asked before anything is
moved.*

*`{ref_row}` is the row on screen that holds this chart's known colours, and
there are three of them: “Target reference data” for a standard target, and the
chart picker for a ChromIQ chart — “Measured chart (.ti3)”, or “Chart you
printed (.ti2)” in printer mode. The window fills it in from the label it is
actually showing, so the message never names a row that is hidden.*

> **Auto align left your corners exactly where they are**
>
> It found the chart, but what your scan shows does not match the reference closely enough to rely on. That usually means the reference file belongs to a different target, or the scan is of a different chart. Check the file in the “{ref_row}” row above and try again.

### M-SCAN-ALIGN-NOT-FOUND · Auto align found nothing chart-like at all — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. The recogniser returned no
candidate placement of any kind. The advice is not a formality: when the user's
own quad covers less than 70 % of the image, Auto align re-runs the same
recogniser inside it, so drawing the corners roughly round the chart really is
what makes a cluttered photograph work.*

> **Auto align left your corners exactly where they are**
>
> ChromIQ could not find this chart anywhere in the picture. That usually happens when the picture shows a lot more than the chart, or when one edge of the chart is missing. Drag the four corners roughly around the chart and press Auto align again: it will then search only inside them.

### M-SCAN-ALIGN-NO-FIT · something was found, and this chart does not fit it — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. The distinction from the message
above is a real one and not a shade of the same thing: there, nothing
chart-shaped was found; here, candidates came back and every one of them was
rejected — the quad was not a plausible sheet, its values could not be
measured, or its outer edges are not this chart's edges. The usual cause is a
target chosen that is not the one on the glass.*

*`{chart_row}` is “Target type” for a standard target, and the chart picker for
a ChromIQ chart, filled in the same way as `{ref_row}` above.*

> **Auto align left your corners exactly where they are**
>
> ChromIQ found something chart-shaped in the picture, but no way of fitting this target's patches onto it. Check that the chart chosen in the “{chart_row}” row above is the one you actually scanned.

### M-SCAN-ALIGN-NO-GEOMETRY · the chart definition records no patch positions — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. Auto align works from the patch
boxes in the `.cht`; without them there is nothing to fit. Nothing else in the
window depends on it, and the message says so, because a user who has just been
told a feature cannot work needs to know how far the trouble reaches.*

> **Auto align left your corners exactly where they are**
>
> The chart definition for this target does not record where its patches sit, and that is what Auto align needs to work. Place the four corners yourself; everything else in this window works normally.

### M-SCAN-ALIGN-DONE · Auto align moved the corners — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5. `{rho}` is the agreement between
what the placed grid reads and this chart's reference, to two decimals, on the
same scale as M-SCAN-REF-DISAGREES. The number is given a scale in the sentence
rather than left bare, and the message points at the pre-build check rather than
inviting a build.*

> **Auto align put the grid on the patches**
>
> What the grid reads now agrees with this chart's own reference to {rho}, on a scale where 1.00 is a perfect match and anything below 0.80 is refused. Press “Check alignment” below to look at the read before you build anything. Nothing else has changed, and you can still drag any corner by hand.

### M-SCAN-ALIGN-NO-INPUT · Auto align pressed before there is anything to align — Tools ▸ Build profile with scanner or camera

*Approved by Basti, 2026-09-03. New for 4.1.5.*

> **Auto align has nothing to look at yet**
>
> Load a scan for this page and choose the chart it was made from, then press Auto align again.

### M-REPORT-NOT-SAVED · the dated report after a measurement could not be written — Measure

*New message (#182 spin-off, 2026-09-04). "Save measurement report" is on by
default, and after every measurement ChromIQ builds a dated accuracy report and
writes it into the run's `reports/` folder, so a printer's reports accrue and
can be trended. When that failed, `_maybe_save_measurement_report` sent the
exception to `log.warning` and appended NOTHING to the screen.*

*The silence was worse than an omission, because the SUCCESS is announced: a
good run prints "[Report] Measurement report saved: …" into the measurement log.
So a failure did not merely fail to inform — the window that had just written no
report was indistinguishable from the window that had, and the only evidence
lived in a log file the user never opens.*

*It is the log and the status line, not a window.* This is the shape
`_on_cr30_dropped_reading` already uses in the same tab, and the reason Basti
gave for wanting a pop-up on M-CR30-READ-FAILED — *"instead of ruining a whole
measurement session when this is unnoticed"* — does not reach here. There the
session stalls with the instrument waiting. Here the measurement is over and
safe: the `.ti3` is the record, the report is derived from it, and the
**Measurement report** button rebuilds it on demand. Nothing is interrupted,
nothing is lost, and there is nothing to do at that instant — so a modal after
every failed report would cost more than it says.

*The message carries NO placeholder and no exception text, and that is
deliberate.* Basti's standing rule for user-facing text is *"friendly,
extensive, easy to understand and correct"*, and an errno with a path in it
fails three of those four: it blames, it is not plain language, and — because
the same `except` catches a failure to BUILD the report and a failure to WRITE
it — a sentence built around it would state a cause nobody has established. So
the message says what happened, what it costs and what to do, names the usual
reasons as things to check rather than as a diagnosis, and points at the
technical line that follows it in the log. That line is
`[Report] Technical detail: <class>: <message>`, and it is not part of §M — it
is a log line, not an explanation.

*The first paragraph is the most valuable one in the message.* A user who reads
"the report failed" and concludes their measurement is gone has been badly
served by a technically accurate sentence, so the message opens by saying what
was NOT lost, before it says what was.

> **The measurement report could not be created**
>
> Your measurement is safe. It was read, checked and written to disk exactly as it always is, and nothing about it has changed. This is only the dated accuracy report ChromIQ normally saves beside it, and nothing in your chart, your measurement or your profile depends on that report.
>
> What did not happen: ChromIQ was not able to work out and save this measurement's report just now, so there is no new dated entry for it in the run's reports folder.
>
> You do not need to measure anything again. The report is worked out from the measurement file itself, so you can open it whenever you like with the Measurement report button, and save it from there.
>
> If you would like to look into it, the technical detail is on the line below this message and in ChromIQ's log file. The usual reasons are a run folder that has been moved, renamed or deleted since the measurement began, a disk with no room left on it, or a folder ChromIQ is not allowed to write into. If this keeps happening and you would rather not be asked about it, you can switch the automatic report off in Preferences, under Reports.

**Confirmed by:** Basti, 2026-09-04 — *"i approve it"*, on the wording as
written, after reading it in full.

## M-PROPOSED. Messages awaiting review

*This section is where a new or revised message goes: add it to
`workflow/measurement_messages.py` with `approved=False`, write it here, and
list it on the issue. `tests/test_message_catalogue.py` holds the two in step —
it fails if a proposed message is missing from this section, and equally if an
approved one is left sitting in it.*

### ⏳ Awaiting confirmation — the log rule no longer describes what CR30 does

**Confirmed by:** *nobody yet.* This is a discrepancy report and a proposed
amendment, not a change to the rule. Nothing here is in force.

§M says that a message whose wording is not yet approved says its piece **in the
log** until it is. For the CR30 messages that is no longer true of any of them:

| message | where its text appears | wording |
|---|---|---|
| M-CR30-CALIBRATE | window | `approved=False` |
| M-CR30-CALIBRATE-BLACK | window | `approved=False` |
| M-CR30-MAGNET | window | `approved=False` |
| M-CR30-INSTRUMENT-GONE | window | `approved=False` |
| M-CR30-READ-FAILED | window | `approved=False` |

Each window exists because **Basti asked for that window**, in his own words,
after meeting the fault himself — the magnet one after a MacBook recalibrated
his instrument mid-chart, the read-failure one after missing a grey line under
the buttons, the instrument-gone one on 2026-08-30: *"if this is an important
message this should be in a pop up windows with benefitial options for this
case"*.

So this is not four exceptions accumulating. It is the rule having stopped
describing practice, which is worse, because the next message will break it
without anyone noticing.

**Proposed amendment, for Basti or Knut to accept or reject:**

> Proposed wording may be shown in a window when the window itself has been
> asked for. The WORDING remains §M-PROPOSED and unapproved either way, and
> still needs review before it can move to §M.

The distinction that matters is preserved: a ruling that a *window* should exist
is not an approval of the *text* inside it. What the log rule was protecting —
that nobody's unreviewed prose quietly becomes the specification — is untouched,
because none of these five is marked approved.

**If this is rejected**, the honest alternative is to put all five back to
log-only, which reverses four decisions Basti made deliberately. Recording it
that way so the choice is visible rather than drifted into.

*Raised by the round-3 review, 2026-08-30.*


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
> Nothing you have already measured is lost — every patch that was read is on disk, and you can carry on from it by ticking "Refine / resume existing measurement (-r)" before you press Start again.
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

### M-CR30-READ-FAILED · PROPOSED · a reading did not arrive complete — Measure

*New message (#159, 2026-08-30). The behaviour already existed and was correct:
a reading that does not arrive complete is refused, the patch is armed again,
and the operator presses the instrument's button once more. What was wrong was
where ChromIQ said so. Basti, with a screenshot of it as a line of grey text
under the buttons:* **"a message like this would be better in a pop up so the
user is aware of it instead of ruining a whole measurement session when this is
unnoticed"**.

*He has the cost right. The failure itself is one button press. NOT NOTICING is
what ruins the session: the instrument sits waiting, the operator believes they
have already pressed it, and nothing moves — and there is no other cue, because
a refused reading makes no sound and leaves the preview unchanged.*

*The window is MODELESS, and that is not a detail. The remedy is to press the
button on the instrument, so a window that had to be dismissed first would stand
between the user and the only thing that puts it right — and a press made while
it was up would arrive behind a window still asking for it. It closes itself
when the chart moves on, which is the same event as the reading having arrived,
and the text promises exactly that so the user is not left wondering whether to
close it.*

*ONE WINDOW PER PATCH, not one per refusal. A flaky link can refuse the same
patch five times before the retry limit gives up (M-CR30-PATCH-GAVE-UP takes
over there). Five windows for one stuck patch is a worse interface than none.
The second and later refusals of the same patch keep the log line and the status
flash they always had.*

*{reason} is the instrument's own words and they are technical — "no usable
reply among the only candidate in 200 bytes" and the like. They stay: the
sentence above them says what to do without needing them, and the detail is what
makes a report worth reading when somebody sends one in. The same screenshot
also showed "1 candidate(s)", which is fixed at source — this project writes
singular and plural out.*

> **That reading did not come through**
>
> The reading for patch {loc} did not arrive complete, so ChromIQ has not used it — nothing wrong has gone into your measurement file.
>
> Press the button on the instrument again, with it resting on patch {loc}. This window will close by itself when the reading comes through.
>
> What the instrument reported: {reason}

### M-INSTRUMENT-BUSY · PROPOSED · two windows reaching for one instrument — Measure and Tools

*New message (#159, 2026-09-02). Tools ▸ "Read single patches" can now read a
CR30, and it reads it the way the Measure tab does: with ChromIQ's own driver,
in this process, over USB or Bluetooth. That is the first time two windows in
ChromIQ can reach for one instrument.*

*Nothing already in the app could see it happening.* `ArgyllRunner.is_running`
*is the question every guard asks, and it answers purely from PROCESS state. The
Measure tab's CR30 session is visible to those guards only by accident, because
`chromiq-chartread -xx` is a real process even though it opens no instrument. A
window driving the reader directly spawns nothing at all.*

*The failure this prevents is not an error. Over Bluetooth a CR30 accepts one
connection and stops advertising once it is taken; over USB two openers
interleave their bytes on the same port. And the instrument holds its last
reading indefinitely and hands it back to whoever asks, so what the second
window gets is a plausible colour belonging to somebody else's patch. That is
the same class of fault the whole CR30 bridge exists to prevent, and it is worse
here because neither window has any reason to doubt what it was given.*

*So the claim on the instrument is explicit and process-wide, taken by whichever
window opens the device. It is refused in BOTH directions and the message is the
same either way, with {where} naming the window that has it: "the Measure tab"
or "Tools ▸ Read single patches". Refusing costs nothing at the moment it
happens, because it is refused BEFORE anything is opened, measured or written.*

*Only ChromIQ's own reader takes the claim. Two ArgyllCMS sessions already
exclude each other through the process guard, and a ColorMunki chart read
alongside a CR30 spot read is two different instruments doing two different
jobs, which is allowed and should be.*

> **Your instrument is already in use**
>
> ChromIQ is measuring in {where}, and your instrument can only answer one window at a time.
>
> Finish or stop that measurement, then start this one again.
>
> Nothing has been changed and nothing has been measured.

### M-CR30-LEARN-TILE · PROPOSED · teaching one unit its own white-tile value — Measure

*New message (#159, 2026-08-30). The magnet guard works by recognising the
value the instrument returns when something magnetic is at the opening — it
stops measuring and hands back its stored white tile. That value was HARD-CODED
from one particular unit. The only other CR30 anyone has measured reads up to
4.69 %R lower, which is 94 times the tolerance, so on that instrument the guard
matched nothing and its owner had no protection at all: a gated reading looks
exactly like an ordinary patch colour and goes straight into the profile.*

*The value cannot be taken from the calibration itself. After a white
calibration the instrument's stored slot is ZERO-FILLED — the code already
measures this and passes `allow_dark=True` because of it — so learning there
would store a spectrum of zeros and arm a guard that matches nothing.*

*It has to come from a capped press, and that is safe to ask for. Measured
across EXP-TILE-002/003/004 on 2026-08-30: a capped press does not damage the
white reference. The paper readings afterwards moved -3.43 %R in one run and
+4.72 %R in the next, and a damaged reference is monotonic; repositioning alone
accounts for 2.36 %R with no cap involved at all. The window says so, because a
user who has read the calibration window's warnings has every reason to be
nervous about pressing the button with the cap on.*

*Offered once per session, only while the guard is unarmed for that instrument,
and always refusable. Skipping costs nothing that is not already lost today.*

*The press count is now asked of the OPEN TRANSPORT and shown as the
instruction, with a pictogram of the capped instrument carrying a downward
arrow and “1×” or “2×”. The window used to be titled "One press teaches…" and
buried the two-press Bluetooth rule four paragraphs down: Basti pressed once
over Bluetooth on 2026-08-30, confirmed, and the window sat there until he
force-quit the app; pressing twice worked immediately. Two is the default when
the transport cannot be read — being told twice and having it accept after one
costs nothing, while being told once when two are needed is a dead end.*

*A tile is learned PER TRANSPORT, and this is by design, not a defect. Over USB
the key is the unit's serial; over Bluetooth there is no serial, so the key is
the address the OS hands back. Basti's own store holds the same 31 values twice
— once under `PT694D01E7` and once under a `ble:` key — because he learned it
over each. The cost is one extra learning press per connection type; the
alternative, arming one unit's constant on an instrument that has not been
learned, is the exact fault this feature exists to remove.*

**Two bodies, chosen by the OPEN TRANSPORT** (`count_key="presses"`,
rendered `M_CR30_LEARN_TILE.render(presses=1|2)`). Each states its own
press count first and then explains it, and each names what the OTHER
transport needs. One shared body with a sentence injected into it left both
windows saying *"Why the difference"* about a difference neither of them
had mentioned, and the one-press window never said that Bluetooth needs two
(Basti, 2026-08-31). No em dashes, by the same ruling.

**Over USB (one press):**

> **Teach ChromIQ your instrument's white tile**
>
> This is a one-off, and it makes every measurement afterwards safer.
>
> If anything magnetic touches the measuring opening, such as a laptop lid under your paper, a magnetic desk mat, or the instrument's own cap, the CR30 stops measuring and hands back the value of its white tile instead. That value looks like a perfectly ordinary patch colour, so without knowing what it is, ChromIQ cannot tell it from a real reading.
>
> Every instrument's tile value is slightly different, so ChromIQ has to learn yours from your own device.
>
> LEAVE THE CAP ON, exactly as it is now, and press the button on the instrument ONCE. This window closes as soon as ChromIQ has the reading.
>
> One press is enough over USB, because the instrument itself tells ChromIQ that the opening was covered, so a single reading proves what it is looking at. Over Bluetooth the instrument does not say, and ChromIQ has to ask for two.
>
> The reading is not part of your measurement and nothing is written to your chart.
>
> This does not change your calibration. A press with the cap on reads the tile that is already the instrument's reference, so there is nothing for it to spoil.
>
> You can press “Not now” and carry on measuring as usual. Everything works exactly as before, and ChromIQ will offer this again next time.

**Over Bluetooth (two presses):**

> **Teach ChromIQ your instrument's white tile**
>
> This is a one-off, and it makes every measurement afterwards safer.
>
> If anything magnetic touches the measuring opening, such as a laptop lid under your paper, a magnetic desk mat, or the instrument's own cap, the CR30 stops measuring and hands back the value of its white tile instead. That value looks like a perfectly ordinary patch colour, so without knowing what it is, ChromIQ cannot tell it from a real reading.
>
> Every instrument's tile value is slightly different, so ChromIQ has to learn yours from your own device.
>
> LEAVE THE CAP ON, exactly as it is now, and press the button on the instrument TWICE. This window closes as soon as ChromIQ has both readings.
>
> Two presses are needed over Bluetooth, because the instrument does not tell ChromIQ that the opening was covered. ChromIQ accepts the value only when two readings come back identical, which real measurements never do. Over USB the instrument does say, and one press is enough there.
>
> The reading is not part of your measurement and nothing is written to your chart.
>
> This does not change your calibration. A press with the cap on reads the tile that is already the instrument's reference, so there is nothing for it to spoil.
>
> You can press “Not now” and carry on measuring as usual. Everything works exactly as before, and ChromIQ will offer this again next time.

### M-CR30-TRIGGER-NOT-ARMED · PROPOSED · the keyboard trigger, on an instrument that has not been learned — Measure

*New message (#159, 2026-08-30). Pressing the instrument's own button moves
it: measured at ~0.5 %R against its own repeat noise of 0.05 %R when nothing
touches it (EXP-TILE-003/004). Taking the reading from the keyboard removes that
error, which is worth roughly a factor of ten in steadiness — Basti asked for it
for exactly this reason: "this would help to keep the device more stable because
pressing its button introduces shake".*

*But a reading ChromIQ asks for cannot report the magnet gate. Byte 58 marks a
solicited reply and the flag at offset 24 is meaningful only in the unsolicited
header a button press produces, so `button_header_is_gated` correctly answers
"cannot tell". The learned tile signature is what replaces the flag — and it is
an exact replacement, because a gated host trigger returns the constant
bit-for-bit (EXP-MEAS-004, 2026-08-30: worst-band delta 0.0000 %R).*

*So the trigger is refused on an instrument whose tile is not yet known, rather
than offered in a state where a magnet would go unnoticed. The window explains
the one-off step that unlocks it and makes clear that nothing is broken
meanwhile.*

> **Measuring from the keyboard needs one quick setup step**
>
> ChromIQ can take each reading for you when you press the space bar, so the instrument never moves between patches — that makes readings about ten times steadier than pressing its own button.
>
> To do that safely, ChromIQ first needs to know what your instrument's white tile looks like, so it can tell a real patch from a covered opening. That takes one press: after calibrating, leave the cap on and press the instrument's button once when ChromIQ asks.
>
> Until then, keep using the button on the instrument — every reading still works exactly as before.

### M-CR30-MAGNET · PROPOSED · a magnet recalibrated the instrument mid-chart — Measure

*New message (#159, 2026-08-30), and it comes from a real incident rather than a
hazard analysis. Basti rested his chart on a MacBook while measuring, and the
laptop's magnets reached straight through the sheet. The instrument did what it
always does with a magnet at the aperture: it took a WHITE CALIBRATION from
whatever it was sitting on — in this case the patch he was trying to read.*

*ChromIQ's guard fired and refused the reading, which was right. Then it re-armed
the patch, told him to press the button again, and let the session carry on — so
every patch after that was measured against a reference that had just been
overwritten. He noticed only because the numbers looked wrong.*

*So the refused reading is the least of it, and this window says so. The session
STOPS. The window offers to retake the white calibration on the spot — with the
instrument's own command, which is a remedy the app can actually perform, unlike
the old advice to seat the cap and press the button, which mid-session simply
produces another gated reading and another refusal.*

*Nothing measured BEFORE the moment is affected, and the window says that too:
the refusal happens before any reading is accepted, so the suspect set is empty
and there is nothing to mark or discard. "Your calibration is wrong" without
that sentence invites someone to bin work that is perfectly sound.*

*⚠ Prevention is impossible, and the text does not pretend otherwise. The only
signal that a magnet is present arrives INSIDE the reading it has already
ruined, and a probe reading would itself be the calibration. Detection before
acceptance is the most that can be done — and it is enough, because it keeps the
suspect set empty.*

*⚠ Known limit: over Bluetooth on a unit other than this one, the first gated
press is not yet detectable — there is no gate flag on that transport and the
tile signature is one unit's constant. USB catches it on every unit.*

> **Your CR30 has just recalibrated itself**
>
> Something magnetic was against the measuring opening, and that changes what the instrument does: instead of measuring your patch, it takes a white calibration from whatever it is resting on.
>
> The usual culprit is not obvious. A laptop has magnets in its lid and body, and they reach straight through a sheet of paper; so do fridge doors, magnetic desk mats, tool trays and the instrument's own cap.
>
> EVERYTHING YOU MEASURED BEFORE THIS IS SAFE, and is already saved. ChromIQ refused this reading before using it, so nothing wrong has gone into your measurement file.
>
> But nothing more can be measured until the white calibration is taken again — until then every reading would be wrong by an amount nothing afterwards could detect.
>
> Move your chart onto something non-magnetic — a book, a pad of paper, a wooden desk — then press “Recalibrate now” and ChromIQ will take the white calibration for you and carry on from the patch you were on.
>
> What ChromIQ detected: {reason}

### M-CR30-CALIBRATE-BLACK · PROPOSED · the dark reference, taken against air — Measure

*⚠ REVISED 2026-09-07, wording only, and it is still PROPOSED — nothing here
has been approved. The act had two names. `black calibration` names it in seven
places and all twelve catalogues have committed to it (`svartkalibrering`,
`kalibracja czerni`, `калибровка по чёрному`, `黑校准`); `dark calibration`
named the same act in three, one of which was this body, one a window title
sitting directly over the sentence "That dark reference does not look dark."
`dark reference` is kept, because it names the RESULT the instrument now holds
and that distinction is worth having. So the body now says "A black calibration
DEFINES what zero means". Three em dashes went with it, under the em-dash rule:
the string was modified, so it stops matching the frozen baseline.*

*New message (#159, 2026-08-29). The second calibration step, offered by an
unticked checkbox in M-CR30-CALIBRATE — per use, deliberately not remembered, so
a second window only ever appears for the user who has just asked for it. That
is the honest answer to the owner's worry about two pop-ups on every Start.*

*The command is the instrument's own. Captured from the vendor's USB frames
(PRIORART-001) and from a Bluetooth trace of the vendor app on his unit
(EXP-BLE-016), and verified on that unit in EXP-022 after he lifted the standing
instruction never to send it: both calibrations were accepted and answered in
~250 ms, and a properly seated white calibration moved his paper reading from
83.95 to 88.37 %R — back into the band every other reading that evening sat in.
So the command really does set the reference, and setting it against the wrong
surface really does shift everything afterwards.*

*⚠ **There is no black tile.** This unit has none, and the vendor calibrates
black against open air with the port downward. The wording says "pointing at
nothing" and never "put something in front of it", and the picture shows no
black tile — because the nearest dark thing to hand is the cap's GREEN face, the
surface that silently corrupted this instrument's white reference during the
research. A drawing of a black tile would teach the one mistake this window
exists to prevent.*

*⚠ **No success is claimed, because none can be.** The reply's bytes fit a
result code and fit equally well the high byte of a device clock that was never
set — over Bluetooth the same field carried a real timestamp. What the dark
reference DOES have, and the white one does not, is an honest test: afterwards, a
reading of nothing should come back at nothing. ChromIQ asks, and reports what
it saw. The threshold is a starting point, not a measured limit, and the check
is one-sided — a reference set too high clamps to a healthy-looking zero.*

*The lamp-and-window clause is PRUDENCE, not measurement. It follows from the
arithmetic of a dark reference and from the vendor's own instruction; the one
experiment that tried to measure it was compromised and is filed as such.*

*Both calibration windows carry the same pair-of-steps picture with the current
step marked — the owner's own choice from eight variants. It is drawn at runtime
from the live palette, so one drawing is correct in light and dark by
construction: a black swatch on a dark window is invisible, and the dark step is
where being unmistakable matters most.*

> **Now the dark reference**
>
> This second step is the opposite of the first one, so it is worth a glance at the picture above.
>
> TAKE THE CAP OFF and put it aside. Hold the instrument with the opening pointing DOWNWARD into open space, about a metre above the floor, with nothing in front of it, and not aimed at a lamp or a window.
>
> There is nothing to place it on. Your CR30 has no black tile: it takes its dark reading from empty air, which is why the picture shows it pointing at nothing.
>
> Then press "Calibrate now". Afterwards ChromIQ reads once more and shows you the number that came back, so there is a record of it.
>
> ⚠ It cannot check that you pointed it at the right thing. A black calibration DEFINES what zero means, so whatever the instrument was looking at becomes the new zero and reads as nothing a moment later. Measured on a real unit: calibrated against white paper, it read back 0.004 %. Getting this step right is your eyes, not ours.
>
> If you would rather not, press "Skip this step". Your white calibration still stands and the measurement goes ahead with the dark reference the instrument already had.
>
> If you have changed your mind about measuring at all, press "Cancel the measurement". Nothing has been measured yet and nothing on disk changes, so the only thing you lose is the white calibration you have just taken, and you can take that again in a few seconds whenever you like.

*⚠ REVISED 2026-08-30, and this one is a retraction. The window claimed the
read-back was "the one check it can honestly make". **It is not a check of what
the user did.** Basti tested it on hardware — black-calibrated deliberately
against white paper — and the read-back came back at **0.004 %R**, comfortably
inside the 0.05 threshold, reported as a healthy dark reference.*

*The reason is structural, not a bug: a black calibration DEFINES zero. Whatever
the instrument is looking at becomes the new zero, so reading that same surface
a moment later can only return ~0. The check is circular for the one mistake it
appeared to guard — pointing it at the wrong thing — and could only fire if
something moved in front of the aperture in the fraction of a second between
the calibration and the read-back.*

*What it still gives is the NUMBER — recorded on screen and now in
`chromiq.log` too. Not "the instrument answered sanely": `allow_dark=True` is
what makes the read-back possible at all, and it necessarily disables the
zero-run guard, so a truncated zero-filled frame passes this exactly as a real
dark reading does. Claiming sanity would have been the same overselling one
sentence further down. The text now promises the number and nothing else.* Under the project's own
rule about colour science — no fake or circular checks — a check that cannot
see its own failure mode must not be described as one.*

*A real check is possible and is NOT implemented: read the WHITE TILE after the
black calibration, where a dark reference taken against paper would show up. It
costs the user another step with the cap, and it needs measuring before it is
promised. Recorded as a possible improvement, not a plan.*

*⚠ ALSO FOUND BY THAT TEST, AND WORSE: every calibration message was being
erased. `_on_start` cleared the measurement log fifty-one lines AFTER calling
the calibration, so the read-back verdict, the note that a white calibration
cannot be verified at all, and the skip note were all written and then wiped
milliseconds later. The check had been firing correctly for its whole life and
nobody had ever seen its answer — which is how the overselling survived this
long. The log is now cleared before the calibration, and the reading also goes
to `chromiq.log`.*

*⚠ REVISED 2026-08-30: a third button, because closing this window used to mean
"skip". Basti found it:* **"none of the calibration pop ups allow to cancel and
if i close them via the red traffic light button chromiq gives me the next
window anyway and allows me to go into the measurement"**.

*The window offered "Calibrate now" and "Skip this step", and the code asked
"is it not Calibrate now?" — which is also true of the red traffic light, the
Windows X and Esc, since `clickedButton()` is None for all three (measured).
So dismissing the window was read as a decision to skip the dark reference, and
the measurement went ahead.*

*Skipping a calibration step is a positive decision and keeps its own button.
Dismissing a window is a withdrawal and now cancels — which costs nothing at
all, because the calibration runs BEFORE the helper starts and there is no
session yet to lose. The same rule is applied at the white window, where it was
already correct, and at M-CR30-INSTRUMENT-GONE, where the safe option is the
opposite one (there, ending is the consequential act, so a dismissal carries
on).*

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
> Plug it back in or switch it on, then press "Carry on measuring" and ChromIQ will pick up from the patch you were on. If it is still not there, you will simply land back here.
>
> If you would rather stop, press "Stop the measurement". Everything you have read is saved either way, and you can come back to the rest later by starting the measurement again with "Refine / resume existing measurement (-r)" ticked — ChromIQ will then offer you only the patches that are still missing.
>
> What went wrong: {reason}

*⚠ REVISED 2026-08-30, twice over, and the second revision is a ruling.*

*The advice was WRONG for the code it belonged to. It offered restarting with
"Refine / resume" as the only way forward, while the handler had already been
changed to offer carrying on from the patch you were on — so the text sent the
user the long way round past a door the app was holding open. Carrying on is
now named first, because it is what the user wants and what the app does;
restarting is kept as the fallback for someone who would rather stop.*

*And it is shown in a WINDOW now, not only in the log. Basti ruled on that
directly:* **"i don't know what m-cr30-instrument-gone is for but if this is an
important message this should be in a pop up windows with benefitial options
for this case"**. *It had been log-only under §M's own rule — that unapproved
wording speaks through the log until it is approved — with the consequence that
the user got the shared ending window and no statement of why it had appeared.
An instrument that has vanished mid-chart is not something to discover by
scrolling.*

*The two buttons are the two real options and both are safe: "Carry on
measuring" re-arms the outstanding patch (nothing ends), "Stop the measurement"
goes through `_confirm_end_of_session` like every other ending
(`measurement_exit_strategy.md` §1). **Closing the window does not end the
session** — `clickedButton()` is None for the red traffic light, the Windows X
and Esc alike, and ending is the consequential act, so a dismissal takes the
option that changes nothing.*

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
> •  The magnetic cap is still on the instrument. That is where the cap lives when the CR30 is not in use, so it is an easy one to miss — and with a magnet at the opening the instrument stops measuring and hands back its own white-tile value instead, which ChromIQ refuses. Take the cap right off and put it aside.
> •  The instrument was lifted before it had finished. Hold it flat on the patch until it has beeped.
>
> When you have checked those, end this session with "Save and stop" and start it again with "Refine / resume existing measurement (-r)" ticked — you will be offered only the patches that are still missing.
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
>
> You can also press the SPACE BAR, or Enter, to take the reading from here without touching the instrument. That keeps it perfectly still, and a reading taken that way is steadier than one taken by pressing the instrument's own button — pressing it moves the instrument slightly, by about ten times its own measurement noise. ChromIQ offers this once it has learned what your instrument's white tile looks like, which it asks about after calibrating.

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

### M-IMPORT-REPLACE-CONFIRM · PROPOSED · the second look before an import clears a project — the loaders

*`M-PROJECT-REPLACE-CONFIRM` with one clause changed, because on this route
what lands in the new project is an imported file rather than a new chart.*

> **Start “{name}” again from empty?**
>
> Everything this project holds is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays inside the project, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.
>
> After that, a new and completely empty project of the same name is started in the same place, and {subject} you are importing is put into its first run.

Buttons: **Replace it** · **Go back**; default **Go back**.

### M-IMPORT-REPLACE-PROJECT-CONFIRM · PROPOSED · the second look before "Copy the whole project in" replaces — Print ▸ Load chart

*New for 4.1.5. This route archived a whole project on ONE CLICK with no
confirmation of any kind, while its own error line named a button ("Replace
it") that was not on the window ("Replace existing"). Its own wording, because
what arrives is a whole project with its own runs — not a single file landing
in run 1, which is what M-IMPORT-REPLACE-CONFIRM describes.*

> **Start “{name}” again from empty?**
>
> Everything the project here holds is about to be moved into its own “old” folder, with today’s date on it:
>
> {folder}
>
> Nothing is deleted. That “old” folder stays in place, so you can open it at any time and take anything back out of it: the charts, the measurements, the profiles, all of it.
>
> The project you are copying in then takes its place, with everything it brings of its own.

Buttons: **Replace it** · **Go back**; default **Go back**.

### M-IMPORT-REPLACED-KEPT · PROPOSED · where the replaced project went — the loaders

*New for 4.1.5. Nothing anywhere recorded it: no window, no log line, not even
a line in the tab's log. "Nothing is deleted" is only true if the person can
find it again.*

> **The earlier “{name}” has been kept**
>
> It has been moved into its own “old” folder:
>
> {folder}
>
> Nothing was deleted. You can open that folder at any time and take anything back out of it.

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
> To finish them, start measuring again with **Patch-by-patch mode** ticked and **Refine / resume existing measurement (-r)** ticked. ChromIQ picks up where the readings stop, so you only measure the patches that are still missing rather than the whole chart again.
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

### M-SPOT-CLEAR · PROPOSED · the second look before the spot list is emptied — Tools ▸ Read single patches

*New message (2026-09-03). Knut reported the spacebar as an annoyance:
"pressing spacebar there which is a trigger in measure tab closes the read
single patches window even in an active session." Driving the real window shows
it is worse than that. `setEnabled(false)` on the focused **Take reading**
button makes Qt walk the focus on to the next ENABLED button, and once there
are readings in the table that button is **Clear** — which had no question,
no undo, and left the window open, so nothing on screen said a whole session
had just been thrown away.*

*Two independent guards, because they cover different mistakes. This one stops
the click that was never meant. The Clear button then turns into "Undo clear"
until the next reading arrives, which covers the click that was meant and
regretted. Nothing the user made is destroyed without a way back.*

*Shown only when the list is not empty, and it states the count, so the person
can see whether it is the reading they just took or an afternoon of them.*

> **Clear every reading in this list?**
>
> This window holds {n} readings, and none of them are saved to a file yet.
>
> Clearing empties the list. Nothing is written to disk and nothing is asked of the instrument, so if you clear by mistake press “Undo clear” and every reading comes straight back. The next reading you take replaces what Undo would restore.
>
> To keep them, choose Cancel and use Save first.

*Singular, when the list holds one:*

> This window holds one reading, and it is not saved to a file yet.
>
> Clearing empties the list. Nothing is written to disk and nothing is asked of the instrument, so if you clear by mistake press “Undo clear” and the reading comes straight back. The next reading you take replaces what Undo would restore.
>
> To keep it, choose Cancel and use Save first.

*Buttons: **Clear** (destructive) and **Cancel** (default).*

### M-SPOT-UNSAVED · PROPOSED · closing a spot window that holds readings nobody saved — Tools ▸ Read single patches

*New message (2026-09-03), found while fixing the one above and independent of
it. The readings live in `self._readings` and nowhere else; the only thing that
writes them out is Save. `reject()`, `closeEvent()` and therefore **Escape**
all went straight to releasing the instrument and out, so Close, the red window
button and a stray Escape each discarded an entire measuring session without a
word.*

*Three ways out, and each says what it does, because the difference matters
here: the readings cannot be recovered afterwards by any route. Save is the
default, and if the file dialog is cancelled the window stays open rather than
closing on work it did not write.*

*Not shown when everything in the list has already been saved, so the ordinary
end of a session is still one click.*

> **These readings are not saved yet**
>
> This window holds {n} readings that are not written to any file. They live in this window only, so closing it lets them go.
>
> Save writes them as a CSV and an ArgyllCMS .ti3 beside the run you are working on, and then the window closes. Discard closes the window and loses the readings. Cancel leaves the window open exactly as it is, with every reading still in the list.

*Singular, when the list holds one:*

> This window holds one reading that is not written to any file. It lives in this window only, so closing it lets it go.
>
> Save writes it as a CSV and an ArgyllCMS .ti3 beside the run you are working on, and then the window closes. Discard closes the window and loses the reading. Cancel leaves the window open exactly as it is, with the reading still in the list.

*Buttons: **Save** (default), **Discard** (destructive) and **Cancel**.*

### M-SCAN-WP-DEFAULT · PROPOSED · the scanner white-point default moved, and existing settings moved with it — Tools ▸ Build profile with scanner or camera

*New for 4.1.5-beta.9, 2026-09-05. The white-point handling a scanner or camera profile is built with moved from "Map chart white to white" (no colprof flag) to "Scale white to a perfect white surface" (`colprof -u -R`). **Basti ruled the migration**: existing remembered settings adopt the new default rather than being pinned to the old one — "our user base is not very big at the moment so i want the better default". This message is the other half of that ruling. CLAUDE.md's principle 10 is "migrate schemas in place, ANNOUNCE it, keep the old files", and this is exactly that case: somebody who re-profiles a scanner they have profiled before gets a visibly different profile, and nothing else in the app would tell them why.*

*Shown once, in the window's LOG, the first time the window opens after the migration has actually changed something — never for a user who had no stored settings, and never twice. It is in the log rather than a window because §M's rule is that unapproved wording speaks through the log, and because nobody has asked for a window here; if Basti would rather it were a window, the mechanism is the same and only the presentation changes.*

*The measured case behind the change (re-measured independently 2026-09-05 on the 864-patch IT8 scan in `beta 9/knut-whitepoint/`, `colprof -ax -qh`): the old default put the chart's own white board at PCS white, and that board is 84.286 % reflectance, so four physically different whites — the board at 84 %, a brighter paper at 89 %, a very bright paper at 95 % and a perfect diffuse reflector at 100 % — all reached L\* 101.1 / 103.5 / 106.1 / 108.1 and every one of them landed on sRGB 255/255/255. Under `-u -R` the same four land at L\* 93.50 / 95.69 / 98.12 / 99.98 and none of them clips. Accuracy is unchanged: profcheck avg ΔE00 0.336709 against 0.336727. Neutrality is unchanged too — the board reads a\* −0.83 / b\* −0.50 against the old default's −0.89 / −0.53 — which is what separates this from `-ua`, whose board carries the chart's real cast at a\* +1.49.*

> **The white point setting for new scanner profiles has changed**
>
> ChromIQ used to build scanner and camera profiles so that the white patch of your test chart became pure white. It now scales white to a perfect white surface instead — the entry "Scale white to a perfect white surface (-u -R)" under Advanced… ▸ White Point ▸ White point handling. Your remembered settings for this window have been moved to it, which is why you are reading this.
>
> Why it moved. Under the old setting, anything you scanned that was lighter than your chart's own white board came out as flat white with no detail left in it, and no amount of editing afterwards could bring that detail back. A test chart's white board is not very white: on the scan this was measured from it is 84 % as bright as a perfect white surface, so that board, a brighter paper, a very bright paper and a perfect white surface all came out as exactly the same white. The new setting keeps them apart. It is just as accurate as the old one, and it keeps whites just as neutral.
>
> What this does not change. Every profile you have already built is a file on disk and is untouched. So is every measurement, every chart and every project. Nothing has been rebuilt, converted, moved or deleted, and no profile changes unless you build it again.
>
> What you will notice. A profile you build from now on makes scans open a little darker — a white board lands at about 93 out of 100 in lightness rather than at 100 — so a scan wants one levels or curves step to finish. Nothing has been lost by that: the highlight detail that used to be flattened is now there for you to work with.
>
> If you preferred the old behaviour, it has not gone anywhere. Open Advanced…, and under White Point set "White point handling" back to "Map chart white to white". That is exactly what ChromIQ did before. Press "Save as Defaults" and it will stay that way.

*No buttons: it is a log entry, not a window.*

### M-SCAN-REF-SHORT · PROPOSED · the reference file covers only part of the target — Tools ▸ Build profile with scanner or camera

*New for 4.1.4, review 5 (2026-09-03), finding D. **The most serious thing this
window does.** A reference file holding the first 48 rows of the target's own
correct 288-row reference — a truncated download, a partial export, a maker's
"short" file — builds a profile from a sixth of the sheet while every indicator
on screen is green: "✓ Ready — 288 patches, reference loaded", the alignment
tick at "worst 99.84 %, average 99.96 %", and colprof's own self-check at
0.185 / 0.076, which is **better** than the correct 288-patch build's
0.620 / 0.098 because forty-eight points fit a matrix beautifully. The `.ti3`
records `NUMBER_OF_SETS 48`: 240 patches were read off the scan and thrown away
in silence. The 288 on screen is the `.cht`'s count and nothing ever compared it
with the reference's own rows.*

*Shown the moment the reference is picked, in the status line under the
"Target reference data" row, where the user can still fix it by choosing another
file — and again as a line in the pre-build warning window, so it cannot be
scrolled past. `{covered}` is how many of the chart's patches the reference
names, `{total}` how many the chart has, `{missing}` the difference.*

*The opposite case says nothing: a reference with MORE rows than the chart has
patches builds a perfect profile, because the extra rows simply go unused
(measured: peak 0.62, average 0.098 from a 400-row reference for a 288-patch
target).*

> **This reference file covers only part of the target**
>
> The reference file you picked gives colours for {covered} of the {total} patches on this target. ChromIQ can only use the patches the reference names, so the other {missing} would be read from your scan and then thrown away, and the profile would describe your scanner from a fraction of the sheet.
>
> Nothing later would show it. A profile built from fewer patches passes its own quality check more easily, not less.
>
> In the “Target reference data” row, pick the full reference file that came with this target. That file lists every patch, so it has about as many rows as the target has patches.

*Singular, when exactly one patch is missing:*

> The reference file you picked gives colours for {covered} of the {total} patches on this target. ChromIQ can only use the patches the reference names, so the remaining one would be read from your scan and then thrown away.
>
> In the “Target reference data” row, pick the full reference file that came with this target. That file lists every patch, so it has about as many rows as the target has patches.

### M-SCAN-REF-DISAGREES · PROPOSED · what was read does not match the reference — Tools ▸ Build profile with scanner or camera

*New for 4.1.4, review 5, findings B2 and B4. ChromIQ already computes the one
number that names a wrong reference or an upside-down scan —
`scan_reference_correlation`, the rank agreement between how light each patch
read and how light the reference says it is — and used it only to decide whether
to run a further check. Measured: **+0.94 to +0.97 on every good read, and −0.60
to +0.14 on every broken one**. When it collapsed, the window quietly declined
to judge and then printed a green tick from the geometric ladder, which never
looks at the reference at all.*

*An upside-down scan is the ordinary flatbed mistake and the clearest case: the
patch block maps onto itself, so every geometric check passes, every patch reads
its opposite number's colour, and only colprof's fit noticed, at the very end.*

*Shown as a line in the pre-build warning window, which already offers Stop and
Build anyway. `{rho}` is the measured agreement, to two decimals.*

*The floor is **0.25**, not the 0.8 the existing `ref_usable` gate uses for a
different purpose. A strongly saturated target (LaserSoft) ranks at ρ≈0.5 even
on a perfect read, which is why that gate exists; this one must sit well below
it. Measured against 30 legitimate reads on two targets across an exposure and
cast sweep, the lowest was **+0.940**.*

> **What was read does not match this reference**
>
> ChromIQ compared how light each patch came out of your scan with how light the reference says that patch is. On a good scan the two run together closely. Here they hardly agree at all: {rho}, where a good read is above 0.9.
>
> That is what happens when the scan is upside down or a quarter turn out, or when the reference belongs to a different target from the one you scanned. A profile built from this read would be wrong, and nothing later would tell you.
>
> Check that the scan is the right way up, and that the file in the “Target reference data” row is the one that came with this target.

### M-SCAN-CLIPPED · PROPOSED · the scan has run out of scale — Tools ▸ Build profile with scanner or camera

*New for 4.1.4, review 5, finding B3. A scan with every value lifted 55 % built
a clean profile in silence: 39.2 % of its patches read at the top of the device
scale, rank agreement +0.943 (so the check above cannot see it), and colprof's
self-check passed without a word. Clipping is the one scan fault that cannot be
profiled around — the values are gone, not merely shifted, and the profile
treats "as bright as this scanner goes" as a measurement.*

*Shown as a line in the pre-build warning window. `{pct}` is the share of
patches at either end of the scale.*

*The floor is **15 %**, and it is deliberately late rather than eager. Measured
across an exposure ladder, `profcheck` against the read's own data goes 0.098 →
0.286 → 0.740 → 1.097 → 5.967 average ΔE as the clipped share goes 0 % → 6 % →
11 % → 16 % → 39 %, so the damage becomes real between 10 % and 16 %. Against
that, the highest reading from any legitimate scan measured — including an
extreme warm cast, a low-contrast scan, a second target, and exposures from
×0.12 to ×1.10 — was **9.7 %**. A floor of 15 % keeps a 1.55× margin over the
worst legitimate case and still catches the scan that is ruined.*

> **Part of this scan has no colour left in it**
>
> {pct} of the patches were read at the very end of the scan's brightness range, where there is nothing left to record. Their real colours are gone, not merely shifted, so ChromIQ cannot tell those patches apart and the profile would treat “as far as this scanner goes” as a measurement.
>
> Scan the target again with the automatic brightness and contrast turned off in your scanner software, so that no patch reaches either end of the scale.

### M-SCAN-PROFILE-ARCHIVED · PROPOSED · where the profile this build replaced went — the scanner window's log

*New for 4.1.4, review 5, finding B5. Building twice in the same folder wrote
over the first profile in place: no copy, no question, and not a word in the log
— and it may be one the user has already installed and been working against. The
measurement beside it went the same way. The app's habit everywhere else is to
archive (`runs/run1, run2, …`, `old/<timestamp>/`, "Deleting moves to the
Trash"), and this window was the exception.*

*The archiving itself needs no new wording and is fixed outright. Saying WHERE
does — and the adversarial round of 2026-09-02 established that moving something
and then naming the folder nowhere is a fault of its own, which is why
M-CAL-ARCHIVED-HERE exists. This follows its shape and its sentence deliberately,
with one word changed.*

*Not a window: two lines written into the log the build is already streaming
into. Shown only when an archive was really made — a first build in a clean
folder moves nothing and says nothing.*

> **The profile that was here has moved to this folder, and nothing in it was deleted:**
>
> {folder}

### M-SCAN-DARK · PROPOSED · the scan never reached the top of the scale — Tools ▸ Build profile with scanner or camera

*New for 4.1.5, beta 8, item B8-01. The opposite twin of M-SCAN-CLIPPED, and the
one nothing in the window could see. Every other guard here is
**scale-invariant** and an exposure slip is **pure scale**: darkening Knut's own
Wolf Faust sheet by 30 % leaves the reference coverage unchanged, the rank
agreement unchanged to three decimals (+0.9839 → +0.9838) and the clipped share
unmoved by a single patch. The build is silent from end to end, and the profile
it produces is **21.7 ΔE** out against a correctly exposed read of the same
sheet. At ×0.18 it is **177.9 ΔE** out, peak 335.7, and still silent.*

*colprof's own self-check cannot see it either, because it is computed against
the same dark data: across the whole ladder it moves only 1.93 → 2.59, against
limits of 30 and 12.*

*Shown as a line in the pre-build warning window, beside the clipping line it
mirrors. `{pct}` is where the chart's own white patches landed on the device
scale.*

*The measure is the median of the **largest device channel** over the patches
the reference calls near-white (Y within 5 % of the reference's own brightest).
A properly exposed scan puts the chart's brightest patch near the top of the
scale, because that is what setting the exposure means, and it is the one
statement about level that survives a change of scanner — every encoding curve
fixes white. Three cheaper measures were built and thrown away, each killed by a
legitimate scan beating an under-exposed one: the **mean** device level (a
transparency's tone scale 28.04 against ×0.70's 27.27), the **black patch above
zero** (matte paper 14.52 against ×0.70's 5.04 — upside down), and the white
patch's **luminance** rather than its max channel (a cool cast 66.28 against
×0.85's 66.88).*

*The floor is **60**, and it comes from 74 reads: Knut's ten real IT8 sheets on
two targets read **72.92 – 79.82**; this session's own re-reads of his two
full-resolution scans, 74.84 and 79.77; the app's own demo scan for all 25
bundled and ArgyllCMS targets, **80.96 – 94.34**; nine legitimate variations
built from his scans — a gamma-1.8 scanner, a gamma-2.6 scanner, matte paper, a
transparency tone scale anchored at the medium's Dmin, a warm cast, a cool cast,
a scanner running 12 % hot, 16-bit and JPEG q12 — **69.57 – 83.86**. Against
that, ×0.85 reads 67.84, ×0.70 reads 55.85 and 52.43 on the two targets, ×0.45
reads 35.87 and 33.71, ×0.18 reads 14.47. A floor of 60 is 9.6 points under the
worst legitimate case measured and 12.9 under the worst that came off real
hardware.*

*It says nothing at all when the reference names no near-white patch — a low-key
target has no exposure to judge against. Measured on a deliberately dark chart
(every reference value scaled to 0.28 and the scan darkened to match) the level
reads 44.1, which would be an accusation; the reference's own brightest patch
reads Y = 22.97, and the check declines instead.*

*And it deliberately lets a half-stop slip through. ×0.85 at 67.84 sits 1.7
points under the harshest legitimate case and cannot be separated from it. That
profile is 9.5 ΔE out, which is not free — but a window that fires on a
legitimate scan is worse, because the same user then clicks past the ×0.70 one.*

> **This scan came out darker than it should be**
>
> The white patches on this target came out at {pct} of your scanner’s brightness range. On a scan exposed for this target they sit just under the top of that range, and getting them there is what the brightness or exposure setting in your scanning software is for.

Nothing later in ChromIQ would tell you. A dark scan is not harder to describe than a bright one: it passes every other check in this window, and the quality number you are shown at the end of the build is worked out from this same dark reading, so it comes out looking just as good. What changes is the profile itself — it would describe your scanner in a state you are unlikely to set up again, so it would not match your everyday scans.

Scan the target again with the brightness or exposure turned back up in your scanner’s own software — not in ChromIQ, which never changes your scan — so that the white patches sit just below the top of the scale without touching it.

One exception: if you are scanning a transparency or a negative, a low reading here can be normal for that medium. Check the exposure before you go on, but you may find nothing is wrong.

### M-SCAN-FIT-UNSUPPORTED · PROPOSED · the reference gives too few colours to fit a profile to — Tools ▸ Build profile with scanner or camera

*New for 4.1.5, beta 8, item B8-03, the half that can be caught before the
build. colprof's self-check is measured against the very rows it was fitted to,
so it is **smallest exactly when there is least to fit**. A reference whose every
`SAMPLE_ID` reads `A1` leaves one row and scores `peak err = 0.007339, avg err =
0.007339` — a better mark than any correct build in this document — and the log
ends "Install it as your scanner's input profile". A reference whose every value
reads `0.00` leaves 288 rows of ONE colour, sends colprof's Powell fit to
`residual error = nan`, and lands a 26 KB profile whose white point is `nan nan
nan`, with the same closing line.*

*An error FLOOR cannot separate these, and the number that proves it is the
app's own: the bundled ColorChecker demo builds at `avg err = 0.059311` — a
legitimate, shipped case only eight times above the degenerate one, with a cLUT
build on real data at 0.462 in between. Counting the **distinct** colours can:
**1** for both degenerate references, against **21** for the smallest target
ChromIQ or ArgyllCMS ships (`MLG`), 24 for a ColorChecker, 288 for Wolf Faust
and 864 for the ISO 12641-2. The floor is **10** — under half the smallest
legitimate case and ten times the degenerate one.*

*Shown as a line in the pre-build warning window. It catches the all-zero
reference squarely, where the existing agreement check caught it only by a
whisker (ρ = 0.246 against a floor of 0.25), and it catches it **before** colprof
spends two minutes converging on nan. `{support}` is the number of distinct
colours.*

> **This reference file describes too few colours to build a profile from**
>
> The reference file names only {support} different colours for this target. A profile describes how your scanner answers to colour, and that cannot be worked out from so few.

ChromIQ can still build one, and it would pass its own quality check easily — when there is almost nothing to match against, almost any answer matches. The quality number you are shown at the end of the build would look better than a correct profile’s, and it would mean nothing at all.

In the “{ref_row}” row, choose the reference file that came with your target. It lists a different colour for every patch on the sheet.

*Singular, when the whole reference holds ONE colour — which is what both of
beta 8's degenerate references reduce to:*

> The reference file names the same colour for every patch it lists. A profile describes how your scanner answers to colour, and that cannot be worked out from a single one.

ChromIQ can still build one, and it would pass its own quality check perfectly — when there is nothing to match against, any answer matches. The quality number you are shown at the end of the build would look better than a correct profile’s, and it would mean nothing at all.

In the “{ref_row}” row, choose the reference file that came with your target. It lists a different colour for every patch on the sheet.

### M-SCAN-SELFCHECK-UNUSABLE · PROPOSED · colprof's own quality check produced no number — the scanner window's log

*New for 4.1.5, beta 8, item B8-03, the half that can only be caught after the
build. `_PROFCHECK_RE` matched only digits and dots, so colprof's `avg err = nan`
line did not match at all: `found` came back empty and the verdict returned on
its `if not found` line. **The one case where the check had the most to say was
the one case it could not read.** Even parsed, `0.0 <= 30.0` would have
short-circuited the `or`. The build then wrote "[OK] Scanner profile saved" and
"Install it as your scanner's input profile" over a profile whose white point is
`nan nan nan`.*

*Two lines in the log the build is already streaming into, in the same place as
the existing self-check warning, and it grades the Install button the same way —
"Install Profile Anyway", which is existing wording. `{raw}` is what colprof
actually printed, so the log names its own evidence.*

*No false-positive cost worth stating: a finite fit never reads `nan`.*

> **This profile could not be checked**
>
> After building a profile, ChromIQ asks how closely it matches the colours it was built from, and shows you the answer as a quality number. This time no number came back at all — the answer was “{raw}”, which is what happens when the measurements handed over had nothing in them to match against.

So the file on disk is a profile in name only, and nothing has confirmed that it describes your scanner. Treat it as unchecked: read the warnings above, put right what they name, and build again before you use it for anything.

### M-SCAN-LOADED · PROPOSED · what has just been loaded, and that nothing has been checked yet — the scanner window's log

*New for beta 8, item B8-16. Loading a scan under the wrong Target type produced
an **empty log**, a live Run button and a 288-cell mesh drawn confidently across
a 24-patch photograph. Pressing Run does fire two automatic guards before
colprof — the reference-agreement test at −0.22 and the placement check at
0.00 % — so this is **not** a silent wrong profile, and it must not be reported
as one. What it is: for as long as the user cares to look, the window is
authoritative about a placement that cannot be right, and it invites them
straight past it.*

*A load-time mismatch DETECTOR is not proposed, because at load time the app has
read nothing and cannot honestly know. What it can do is stop being silent: say
what was loaded, say what it is about to be read as, and say that nothing has
been checked yet. The check that can answer the question is named, because it is
the button beside it.*

*Not a window: two lines in the log the window already writes into, on every
successful load — the matching case as well as the mismatched one, because a
line that appears only when something is wrong teaches the user nothing about
what right looks like.*

> **Scan loaded**
>
> {file} — {w} × {h} pixels. It will be read as “{target}”, which has {n} patches.
> Nothing has been checked yet. Place the grid over the patch area, then press Check alignment — that reads the scan and says whether the grid is really on the patches.

### M-SCAN-ALIGN-NOT-SEATED · PROPOSED · Auto align found the chart and the grid does not sit on the patches — Tools ▸ Build profile with scanner or camera

*New for 4.1.5, beta 8, item B8-02. The seventh Auto align refusal, and the
first one about GEOMETRY rather than about colour. Every other check in
`workflow/scan_auto_align.py` scores the placement against the chart's known
colours, and the quad Auto align is able to return is always a rotated
rectangle — `corners_from_candidate` builds it from a rotation and two scales,
so its two edge vectors are orthogonal by construction. A sheet photographed
even slightly off square is a keystone, which a rectangle cannot be, so the grid
comes out systematically wrong: right in the middle of the sheet and worst at
one corner. **A rank correlation cannot see that**, because the patches keep
their brightness ORDER while they slide onto their neighbours.*

*Measured with a pinhole camera at three sheet-widths and a compound pitch+yaw
tilt — what a hand holding a phone actually does. At **8 degrees**, 20 of 23
bundled targets accepted the answer and **ten of them were more than half a
patch pitch out**, which is the point at which a sample box reads the
neighbouring patch; the window printed “agrees … to 0.98” beside its own
sentence “anything below 0.80 is refused”. Knut's LaserSoft target was 0.921
pitch out at 0.98; LaserSoftDCPro 0.426 out at **1.00**. Costed end to end on
Knut's real Wolf Faust scan at 10 degrees: 33 of 288 patches move by more than
3 ΔE00, six by more than 10, and the resulting scanner profile differs from the
correct one by a median **2.23 ΔE00** with 320 of 343 device grid points over
1 ΔE00, against a harness floor of 0.78.*

*The gate is `seating_drift`: for every patch box, the offset that would seat it
on flat colour, shrunk by how much moving it actually helped, averaged over a
4×4 grid of chart regions, in patch pitches. Noise cancels inside a region; a
keystone does not.*

*Measured over three populations: 600 camera views of 25 targets; 216 CROSSED
views carrying a paper bow, a lens distortion and a tilt at once; and the
38-case challenge set at its own ground truth plus Knut's two real scans and
nine legitimate degradations of his sheet. **328 correct placements read 0.0631
or less** — the single worst a 24-patch half Passport at 15 degrees, with Knut's
own scan plus heavy noise next at 0.0583 and his untouched scans at 0.0175 and
0.0139 — while **106 placements more than half a pitch out read 0.0989 or
more**. Every value from **0.065 to 0.095** gives the same two counts: **0 false
refusals in 328, and 106 of 106 wrong answers refused**. The limit is **0.075**,
1.19× above the worst correct placement and 1.32× below the worst wrong one.*

*The false-refusal cost is stated rather than implied: this refuses nothing that
Auto align places correctly today, and it refuses the barrel- and
pincushion-distorted photographs where **no** four corners can seat the patches
(Agent G's lens measurements: an ordinary phone lens already costs 6 patches
over 3 ΔE at the best possible quad, a pincushion 39). Those were being accepted
at rho 0.98 and are now refused, which is the right answer for them.*

*What it does NOT catch, said plainly: about half of the placements between a
quarter and half a patch pitch out — where the sample box overhangs its patch
border but does not reach the neighbouring patch. 126 of 252 of those are
refused. Nearly all the survivors are lens-distorted photographs at low tilt.*

*A refusal, not a warning, and this is the one place in the scanner window where
that is the right shape: the harm is a confidently wrong profile, the user loses
nothing (their own corners are untouched), and dragging four corners by hand
always works.*

> **Auto align left your corners exactly where they are**
>
> It found the chart, but the patches in the picture do not sit where that grid would put them: towards one edge of the sheet the grid would read part of the neighbouring patch, and a profile built from that is wrong without looking wrong.

This is what a photograph taken at a slight angle does — the sheet further from the camera comes out smaller, and no rectangle fits both ends of it. A flatbed scan does not have the problem at all.

Scan the sheet, or photograph it square-on with the camera above the middle of it — or drag the four corners onto the chart yourself, which always works and is what the grid is for.

### M-SCAN-DIAGNOSTIC · PROPOSED · a scanin diagnostic image offered as a scan — the scanner window's log

*New for beta 8, item B8-15. Knut did this in his own beta.7 session
(`chromiq.log`, 15:30): he picked `diagnosticReadLSTarget01.tif` — an output of
`scanin -dipn`, a picture OF a read — as the scan. The app took it without a
word, and the alignment check then reported a misplacement that was not real
("sample boxes sit on patch edges, worst 73.80 %") about a read that had been
fine. ChromIQ writes one of these into `cache/` beside every scan it reads, so
it is an easy file to pick again by mistake.*

*Recognised from the pixels, not from the file name: his was written by his own
`scanin` command and is called nothing ChromIQ would write. Measured at full
resolution over three diagnostics and twenty real scans and photographs
(`workflow/scan_diagnostic_image.py` carries the table): a diagnostic is 60–66 %
exactly neutral and 0.7–3.4 % Argyll's annotation colour, while no real scan in
the set had a single pixel of that colour. Both signatures must hold, because
the neutral fraction alone reached 45 % on a JPEG at quality 12.*

*A WARNING, not a refusal. The harm is a false verdict, not a bad profile, and a
detector measured on three files should not be able to lock a user out of their
own scan. Written into the log at load time, so the user meets it before the
false verdict rather than after it.*

> **This looks like a diagnostic image, not a scan**
>
> ChromIQ writes one of these after every read: your scan turned grey, with the colour painted back only where ArgyllCMS sampled it, and the patch names drawn on top. It is a picture of a read, not something that can be read again.
>
> The grid cannot line up on it, and the alignment check will report a misplacement that is not real. Load the original scan of your target instead — diagnostic images live in the “cache” folder beside it and are safe to delete.

### M-SCAN-CONVERTED · PROPOSED · a photograph converted so ArgyllCMS can read it — the scanner window's log

*New for beta 8, agent L. The window's own subtitle offers “a scan **or photo**
of the target”, and the file picker's “All files” entry lets a camera JPEG be
chosen. Qt decodes it happily into the preview, the marquee aligns on it, the
Run button goes live — and `scanin` then exits with* `Not a TIFF or MDI file,
bad magic number` *at the very end of the job, worded as an Argyll file error.
Measured here on a real camera JPEG.*

*ChromIQ now writes a TIFF copy and reads that. Said out loud rather than
silently, because a file the app has substituted for the one the user chose is
not the user's file any more, and the two questions they will have — “was
anything done to my colours?” and “was my original changed?” — are both answered
here. A file that is already a TIFF is not copied, not re-encoded and not
opened: that is the flatbed path and it stays exactly what it was.*

> **This photograph was converted for reading**
>
> ArgyllCMS reads TIFF images only, and {file} is not one. ChromIQ made a TIFF copy of it and will read that; your own file is not changed. The copy holds the same pixels — nothing has been sharpened, resized or colour-managed.

### WITHDRAWN on 2026-09-04, never approved — the separate “Fit to the patches” button's own four messages

*B8-42 merged “Auto align” and “Fit to the patches” into one button, on the
measurement that neither was useless and neither was a subset of the other: over
290 starting placements there are 139 cases only the search recovers and 30 only
the reshaping does, and one button that searches, then reshapes, then checks
lands 244 of the 290 on the patches where pressing both landed 226. With the
second button gone, four of the messages written for it describe states the user
can no longer reach, and every ending the merged button HAS is told in Auto
align's own approved words:*

* **M-SCAN-FIT-DONE** — “The grid was fitted to the patches”. There is one
  success now, M-SCAN-ALIGN-DONE, and it is approved. This one also quoted a
  number that was true only of the reshaping step: on screen, on Knut's own Wolf
  Faust scan, it said “moved your corners by up to 0.54 of a patch” while the
  grid was 1.54 patches out.
* **M-SCAN-FIT-NO-BETTER** — “The grid was left exactly where you put it”.
  The approved M-SCAN-ALIGN-NO-BETTER says the same thing, and now covers it.
* **M-SCAN-FIT-NOTHING** — the button pressed before there was anything to look
  at. The approved M-SCAN-ALIGN-NO-INPUT is that state.
* **M-SCAN-FIT-NOT-SEATED** — the reshaped answer failing the picture check.
  There is one picture check now, at the end, on whatever placement is about to
  be applied, and M-SCAN-ALIGN-NOT-SEATED is its refusal.

### M-SCAN-ALIGN-NO-BETTER · PROPOSED (revised wording) · nothing could be improved on the corners the user placed — Tools ▸ Build profile with scanner or camera

*The headline was approved by Basti on 2026-09-03 and is unchanged. The BODY is
rewritten for B8-42 and is back in the queue for that reason.*

*What changed under it: this used to be the recogniser's own ending, reached
when its answer did not beat the placement on screen by a margin. The merged
placement button reaches it only when BOTH halves of the operation have
declined — the search found nothing better, and the reshaping then found
nothing worth moving the corners for — so a body that describes only the search
would describe half of what happened.*

*The second half of the body is the part that matters, and it is new. This
ending is a statement about what was searched and is NOT a statement that the
placement is right: a grid exactly one patch out reads every patch as its
neighbour and is, to everything measured inside the sample boxes, identical to
the right answer. The wording therefore says what happened, refuses the claim it
cannot make, and names the one check in this window that can tell the two apart
— which the approved version did not do.*

> **Auto align left your corners exactly where they are**
>
> ChromIQ searched the picture for the chart, and then looked around the four corners you placed for a better place to put the grid. Neither found one worth moving them for — what you have is already the closest match it can see.
> That is not the same as saying the grid is on the right patches: a grid a whole patch out reads every patch as its neighbour and looks just as even. Press “Check alignment” below — that reads the scan and can tell the difference.

### M-SCAN-FIT-TOO-FAR · PROPOSED · nothing was found, and the corners cannot be improved from where they are — the scanner window's log

*Beta 8. Written for agent L's separate “Fit to the patches” button and REWRITTEN
for the merged one (B8-42): from beta 8 the scanner window has ONE placement
button, which searches the picture for the chart, reshapes what it finds — or,
when nothing is found, the four corners the user placed — onto the patches, and
checks the result before anything moves. This is the ending where the search had
no diagnosis of its own and the reshaping then found its best placement further
away than it is allowed to move. Measured over 290 starting placements, 2 end
here.*

*The refusal carries the safety rule, so it says what the rule is: past three
quarters of a patch pitch the “same patch, better centred” reading of the answer
stops being the only one, and the wrong reading looks exactly as convincing.
Measured: from a placement 0.35 of a patch out on a sheet bowed 5.5 % and tilted
15 degrees the reshaping wants 0.85 of a pitch, and is refused; the user moves
the corners closer and it lands.*

*The arithmetic in the first version was wrong twice over — it said “more than
half a patch” of a limit that is three quarters, and “half a patch further and
the grid would be reading the neighbouring patch” of a distance that is a
quarter. The headline is now the one every other refusal from this button
carries, because after a refusal the first thing the user needs to know is that
they have lost nothing.*

> **Auto align left your corners exactly where they are**
>
> ChromIQ looked around the four corners you placed for a better place to put the grid, and the best one it found is further than three quarters of a patch away from them. That is as far as it will move your corners by itself: one whole patch and the grid would be reading the neighbouring squares, which looks just as convincing and is completely wrong.
> Drag the four corners onto the chart’s patch area, as close to the real patches as you can get them, and press Auto align again.

### M-SCAN-SHOT-EMPTY · PROPOSED · an averaging slot left empty — the scanner window's log

*New for beta 8, item B8-32 (regression-sweep finding F-7). Press
**＋ Add another scan to average** and stop there. The shot bar reads
"Scan 1 / Scan 2", `_page_ready` asks only `any(s["path"] …)` so the Run button
stays live, and the build runs **one** `scanin`, no averaging step, and ends
`[OK] Scanner profile saved` exactly as if one scan had been asked for. Driven
end to end in the real window (sweep check J32): two slots, one file, one
scanin call, and nothing said on screen or in the log.*

*A sentence, not a refusal. What happens is a legitimate build from fewer scans
— not a wrong profile — and this window's rule for that case is already set
(B8-15: warn, never lock the user out of their own file). A Run button that
greys out with no reason attached would be a new silence rather than the end of
one.*

*One message, not a singular and a plural: every count in it is a bare number in
a clause that does not inflect around it.*

> **An empty scan slot was skipped**
>
> This page has {slots} scan slots, and a file has been picked for {filled} of them. An empty slot is not read and nothing is averaged with it, so this build uses only the scans that are there.
> If you meant to average repeated scans of this page, pick a file for each empty slot and build again. If a slot was added by mistake, “Remove this scan” takes it away.

### M-SCAN-TARGET-CHANGED · PROPOSED · the scan a target-type change throws away — the scanner window's log

*New for beta 8, item B8-32 (regression-sweep finding F-9). Load a scan, place
the grid, change **Target type**: the scan, its four corners and every other
shot on that page are dropped (`_set_std_targets` → `_reset_shots`), the preview
goes empty, and the log — cleared in the same block, which is B8-16's fix — said
nothing about any of it.*

*The discard is correct and is not being changed. A different target has a
different grid, so a placement made on the old one is meaningless on the new
one, and a demo scan belongs to the target that generated it. What was missing
was the sentence saying it happened, and where to start again.*

> **Target type changed — the loaded scan was cleared**
>
> A scan is read through the target’s own recognition file, and a different target has a different grid, so a placement made on the old one would not mean anything on this one. The scan that was loaded, its four corners and any further scans on this page have been dropped.
> Nothing on disk was touched. Pick the scan again — or press “Try with a demo scan” — for the target now selected.

### Frame titles awaiting a ruling — Create Chart ▸ Manual ▸ Expert (B8-21 §4)

**Confirmed by:** *nobody yet.* Proposed 2026-09-04 by AGENT-R. Not approved,
and Basti rules on it.

*Deliberately NOT given an `M-` identifier. §M is a catalogue of MESSAGES —
each one a window or a log line with a headline and a body, rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading in this document to exist there. A group-box title
is not a message and must not be given a fake one to satisfy a parser. It is
recorded here because it is new user-facing wording and this is where new
user-facing wording is proposed and ruled on.*

The frame **"Strip && row labels"** used to explain which of its controls
reaches which set of labels in a paragraph. Basti, 2026-09-03: *"keep the first
note, drop the second, and rule on sub-frames… the paragraph is the option I'd
argue against — it's correct, and correct is not the same as clear."* So the
frame is split in two along the line the ink drew, and the two titles ARE the
explanation:

| proposed title | what it holds | German |
|---|---|---|
| **Strip letters and row numbers** | Font, Size, Bold — measured at 11 086 to 126 162 pixels of row-label ink each, and Font and Size re-lay the page | Streifenbuchstaben und Zeilennummern |
| **Strip letters only** | Underline, line thickness, line distance, rotation, Label offset — 0 row-label pixels, every time | Nur Streifenbuchstaben |

*Written for somebody who has never met the words "indicator" or "band": they
name what the reader can see on the printed sheet — the letters across the top
and the numbers down the left — and the second says "only", which is the whole
point of the split. Italic is in neither title: it is greyed out because
neither bundled font has an italic face, and it drew nothing on either side.*

*The other eleven catalogues carry the English source until this is ruled on,
because translating a draft translates it twice. German is translated, as the
beta convention has it.*

### Button labels — Tools ▸ Build profile with scanner or camera (AGENT-S) — Confirmed behaviour

**Confirmed by:** Basti, 2026-09-04 — *"it is ok"*, put to him as the label
and its tooltip together and approved as proposed. Drafted the same day by
AGENT-S.

*The eleven non-German catalogues still carry the English source, and that is
now the BETA TRANSLATION CONVENTION doing it, not a pending ruling: translation
happens before a final, not during a beta, so that nothing is translated twice.
Do not "finish" them here — the language sweep before the final is where they
land.*

*Deliberately NOT given an `M-` identifier, for the reason the section above
gives: §M is a catalogue of MESSAGES, each one rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading here to exist there. A button label is not a
message and must not be given a fake identifier to satisfy a parser. It is
recorded here because it is new user-facing wording and this is where new
user-facing wording is proposed and ruled on.*

Basti, 2026-09-04, looking at the running window: *"could you task an agent to
rearrange the buttons under the preview in a way it makes sense and takes up
less space?"* The block was four rows for six buttons, and the last row held
one button because its label was a sentence.

| proposed label | replaces | German |
|---|---|---|
| **⤢ Pop out** | ⤢ Pop out for a bigger view | ⤢ Ablösen |

*Measured at these buttons' own metrics: the old label is the longest in the
window — 202 px in Italian, 191 in German, against 78 for this one — and it is
what forced a fourth row. What the four dropped words said is now said twice
over: by the new tooltip below, and by the hint line printed under the block,
which already ends "Rotate handles a sideways scan; Pop out gives a bigger
view".*

| proposed tooltip (the button has none today) |
|---|
| Open the preview in its own resizable window, much bigger, so the corners are easier to place. The placement, the zoom and the rotation all come back with it when you dock it again. |

*German: "Öffnet die Vorschau in einem eigenen, frei skalierbaren Fenster – viel
größer, damit sich die Ecken leichter setzen lassen. Platzierung, Zoom und
Drehung kommen beim Andocken unverändert zurück."*

*The other eleven catalogues carry the English source until this is ruled on,
because translating a draft translates it twice. German is translated, as the
beta convention has it. "⤢ Dock back", the label the button carries while the
preview is popped out, is unchanged.*

### Profile type help text, Tools ▸ Build profile with scanner or camera (AGENT-AD, AGENT-AF) — Confirmed behaviour

**Confirmed by:** Basti, 2026-09-04 — *"i approve it"*, given after he read the
text in full and asked whether it was "friendly, extensive, easy to understand".
Approved as written: the help itself, the "(recommended cLUT)" marker in scanner
mode, and the patch-count hint. Drafted 2026-09-04 by AGENT-AD, revised the same
day by AGENT-AF when Basti ruled that the measurement must be reflected in the
app rather than only in a reply to Knut. Knut asked for it: *"Maybe the help text for the profile type should give
recommendations for when to use the LUT types, such as when one has large
targets with many patches… or whatever…."*

#### ⏳ Awaiting confirmation — three paragraphs of the scanner-side ⓘ, 2026-09-06

**Confirmed by:** *nobody yet.*

Basti approved the words above on 2026-09-04. Three paragraphs of the
scanner-side text have changed since, and neither change has been put to him,
so they are flagged here rather than left inside a "Confirmed" heading as if
they had been:

1. **The Lab-table bullet was already out of date in this document before
   today**, and that is a pre-existing divergence, not something this change
   introduced. B8-75 moved the white-point default to "Scale white to a perfect
   white surface (-u -R)" on 2026-09-05, which moves a Lab cLUT's ceiling from
   about 94 % reflectance to about 114 %, and the bullet was rewritten in the
   code to say so. This document kept the older wording, which still ends
   *"set Advanced… ▸ White point handling to 'Auto-scale to avoid clipping
   (-u)', which lifts the ceiling"* — advice the new default has already taken.
   The paragraph above is now the code's, so the two agree again.
2. **"the default here" is gone from the Shaper + matrix bullet, and "on the
   default there" from the Lab one.** Knut asked in beta 10 for the profile
   type, the quality and the white point to be chosen from the patch count, and
   for the white-point dropdown to stop calling one entry the default (it is
   wrong for the two matrix types, which this window's own help says). With
   both built, "the default" names nothing on either control, so the two
   sentences that leaned on it had to say something else.
3. **The third paragraph now says the window acts on the patch count**, because
   it does. That is the change B8-19 considered and deliberately did not make;
   Knut asked for it and Basti authorised it, and the guard that keeps it safe
   is that it never touches a bucket whose settings somebody saved. B8-78 has
   the whole of it.

4. **The printer side lost two of its four profile types, and this
   document said they worked.** It read *"All four choices build a working
   profile"* for the printer mode and listed Shaper + matrix and Matrix only in
   the dropdown table, and ArgyllCMS makes that impossible: `colprof.c:1244`
   answers any non-cLUT algorithm for a `DEVICE_CLASS "OUTPUT"` measurement
   with *"Output profile can only be a cLUT algorithm"* and writes nothing.
   MEASURED on Knut's own `Knut-Scanner-printer.ti3`, the printer-mode
   measurement this very window produced: `-as` and `-am` exit 1 with no
   profile. So this is a fault in the DOCUMENT as much as in the code, and by
   CLAUDE.md's rule that is Knut's and Basti's call rather than ours: the
   wording below is what the app now shows, and it is flagged here for a ruling
   rather than presented as settled. B8-93 and B8-94 carry the whole
   measurement. The same note applies to the Quality paragraph on BOTH sides:
   it said `-q` "applies only to the two cLUT types and is greyed out for the
   other two", and ArgyllCMS's own `colprof.html` says the opposite ("For
   matrix profiles it sets the per channel curve detail level and fitting
   'effort'"), which is measured: `-q l/m/h/u` gives four different profiles
   for every algorithm tested. The greyed value was being sent regardless.
   B8-95.

The patch-count *hint* Basti approved is still there and still changes nothing.
It now fires only where ChromIQ may not choose for the user: a bucket with
saved settings, or one edited by hand this session.

**The wording below is what the app now shows.** It is written into
`ui/dialogs/scanner_colprof.py` (`ptype_help`, `ptype_advice`) and reproduced
here verbatim so a ruling can be made on the exact words. If a word changes
there it changes here in the same commit —
`tests/test_the_profile_type_says_which_clut.py` pins the claims and
`tests/test_i18n.py` pins the catalogues.

*Deliberately NOT given an `M-` identifier, for the reason the sections above
give: §M is a catalogue of MESSAGES rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading here to exist there. A tooltip is not a message and
must not be given a fake identifier to satisfy a parser.*

**Every recommendation is a measurement, not colour-management lore.** The
numbers come from cross-validated builds on two REAL scans — a Wolf Faust IT8
(288 patches) and a LaserSoft DCPro (864) — fitted on part of the patch set and
scored, in CIEDE2000, only on patches the fit never saw. The evidence is in
`beta 8/24-scanner-profile-default/`, the harness is `cv_profile_type.py`, and
the register entries are B8-19 and B8-56.

**It differs by MODE, because the advice does.** The same row builds a scanner /
camera INPUT profile and, with "Profile my printer from this scan" ticked, a
printer OUTPUT profile — and the window already marks a different "(default)"
for each. The XYZ recommendation is about capturing something lighter than the
chart's white; ArgyllCMS's `colprof.html` makes that claim of INPUT devices
specifically, AGENT-AD measured input profiles only, and nothing a printer
prints is lighter than the paper it prints on. So it is made on the scanner side
and NOT on the printer side. One text covering both would have to contradict one
of the two "(default)" markers.

#### 1 · The ⓘ beside "Profile type (-a):" — scanner or camera mode

> How the scanner or camera profile models colour.
>
> Profile type (-a) — the shape of the maths inside the profile, and how it describes what your device does with colour. All four choices build a working profile. What separates them is how many measured patches they need before they are any good, and how they behave on colours your target did not contain.
>
> That makes the size of your target the first thing to look at, and you do not have to count anything or set anything up. The patch count is printed beside each target's name in the list above, and again in the green “✓ … patches” line once a target or a chart is loaded; and the moment ChromIQ knows that number it sets this control, the Quality below it and Advanced… ▸ White point handling to suit it. Below about a hundred patches that is “Shaper + matrix” at Medium; at a hundred or more it is the XYZ look-up table at High. Change any of the three and ChromIQ leaves all three alone from then on.
>
> • Shaper + matrix, and what ChromIQ chooses for a target under about a hundred patches: a small, sturdy profile made of one gentle tone curve for each of red, green and blue plus a 3×3 matrix, which is a fixed recipe for mixing those three into a finished colour. It is a formula rather than a stored table, so it needs very little data to work well, and it carries on sensibly beyond the lightest and darkest patch your target contains. Take it for a ColorChecker (24 patches), a SpyderChecker (48) or a QPcard (49), and whenever a scan is noisy or you would rather not think about it. On real scanned targets it was the most accurate of the four at 24 and at 48 patches.
>
> • cLUT — XYZ table — “cLUT” means a look-up table. Instead of a formula, the profile stores your measurements and interpolates between them, so it can follow a device that does not behave like tidy maths. That freedom has to be paid for in patches: with too few of them there is nothing much to interpolate between, and the table will happily fit the noise in a scan rather than the colour. Take it when your target has roughly two hundred patches or more — a full IT8 has 288, a three-page ISO 12641-2 set has 864 — and the scan is clean and correctly exposed. At that size it measured about a third more accurate than Shaper + matrix on a real IT8 scan. “XYZ” is simply the internal form the table keeps colour in, and it is the one to use here — the next entry says why.
>
> • The Lab look-up table, the other of the two cLUT entries: the same kind of table, keeping colour in a different internal form. On the colours your target actually contains, the two tables measured close together, with neither of them consistently ahead of the other. The difference is at the top end: a Lab table has a hard ceiling and stops dead at it, flattening every tone above onto one value, where Shaper + matrix and the XYZ table both carry on. How high that ceiling sits is decided by Advanced… ▸ White point handling. On “Scale white to a perfect white surface” it sits at about 114 % reflectance, brighter than a perfect white surface, so nothing you can put on the glass will reach it. On “Map chart white to white” the ceiling drops to about 94 % reflectance, which ordinary bright paper does reach, and everything above it arrives flattened. (Both figures measured on a real IT8 scan, so your own will differ a little.) The XYZ table has no ceiling at all under any of those settings, which is why it is the safer of the two and why it costs nothing to take.
>
> • Matrix only — the 3×3 mix and nothing else, with no tone curves in front of it. It suits a device that is already perfectly linear, such as a camera shooting RAW. On an ordinary scanner it measured several times less accurate than any of the other three at every size tested, so it is not the one to reach for here.
>
> Right around a hundred patches the first three land within a whisker of one another and the choice barely matters; it is above and below that the difference shows. And whichever you pick, changing the paper or the target you scan moves the result a great deal further than the profile type does.
>
> ArgyllCMS has two more variants that this list leaves out, and it is worth knowing they exist. They fit one tone curve shared by all three colour channels instead of a separate curve for each. That is not an accuracy choice: their stated purpose is compatibility with applications that refuse a profile carrying a different curve per channel. If an application will not accept a profile this window built, that is the first thing to mention when you report it.
>
> Quality (-q): how much detail and fitting effort goes into the profile. For the two look-up-table types it sets the table's grid resolution; for the shaper and matrix types it sets how finely the tone curves are fitted. Higher is finer but slower, and needs better data to be worth it. It applies to every profile type. Medium is a good default, Low is a quick test, and High and Ultra are for large, clean charts.
>
> If you tick “Profile my printer from this scan”, this same control builds the printer profile instead — a different kind of device, with different advice. The type then defaults to “cLUT — Lab table”; open this ⓘ again with the box ticked and it will explain why. Either way you won't find a working space (like sRGB) or a rendering intent here; a rendering intent is something you choose when you print, not when you build a profile from measurements.
>
> None of the recommendations above is received wisdom. Profiles were built from part of two real scanned targets and then scored only on the patches the fit had never seen, which is the only way the numbers mean anything — a profile marked against its own measurements flatters a look-up table badly.

*German:*

> Wie das Scanner- oder Kameraprofil Farbe modelliert.
>
> Profiltyp (-a) – die Form der Mathematik im Inneren des Profils, also wie es beschreibt, was dein Gerät mit Farbe macht. Alle vier Möglichkeiten erzeugen ein funktionierendes Profil. Sie unterscheiden sich darin, wie viele gemessene Felder sie brauchen, bevor sie wirklich gut sind, und wie sie sich bei Farben verhalten, die dein Target gar nicht enthielt.
>
> Damit ist die Größe deines Targets das Erste, worauf du schauen solltest, und zählen oder einstellen musst du nichts: Die Feldanzahl steht in der Liste oben neben dem Namen jedes Targets und noch einmal in der grünen Bereitschaftszeile mit dem Häkchen, sobald ein Target oder eine Testkarte geladen ist. Und sobald ChromIQ diese Zahl kennt, setzt es dieses Bedienelement, die Qualität darunter und Erweitert… ▸ Weißpunkt-Behandlung passend dazu. Unter etwa hundert Feldern ist das „Shaper + Matrix“ mit Mittel, ab hundert die XYZ-Nachschlagetabelle mit Hoch. Änderst du eine der drei, lässt ChromIQ von da an alle drei in Ruhe.
>
> • Shaper + Matrix, und das, was ChromIQ für ein Target unter etwa hundert Feldern wählt: ein kleines, robustes Profil aus je einer sanften Tonwertkurve für Rot, Grün und Blau und einer 3×3-Matrix, also einem festen Rezept, das diese drei zu einer fertigen Farbe mischt. Es ist eine Formel und keine gespeicherte Tabelle, braucht deshalb sehr wenig Daten, um gut zu arbeiten, und verhält sich auch jenseits des hellsten und des dunkelsten Feldes deines Targets noch vernünftig. Nimm es für einen ColorChecker (24 Felder), einen SpyderChecker (48) oder eine QPcard (49) und immer dann, wenn ein Scan verrauscht ist oder du dir darüber lieber keine Gedanken machen möchtest. Bei echten gescannten Targets war es bei 24 und bei 48 Feldern das genaueste der vier.
>
> • cLUT — XYZ-Tabelle – „cLUT“ heißt Nachschlagetabelle. Statt einer Formel speichert das Profil deine Messwerte und interpoliert dazwischen, kann also einem Gerät folgen, das sich nicht wie saubere Mathematik verhält. Diese Freiheit muss in Feldern bezahlt werden: Sind es zu wenige, gibt es kaum etwas, wozwischen sich interpolieren ließe, und die Tabelle bildet bereitwillig das Rauschen im Scan ab statt der Farbe. Nimm sie, wenn dein Target ungefähr zweihundert Felder oder mehr hat – ein volles IT8 hat 288, ein dreiseitiges ISO-12641-2-Set 864 – und der Scan sauber und richtig belichtet ist. In dieser Größe war sie bei einem echten IT8-Scan rund ein Drittel genauer als Shaper + Matrix. „XYZ“ ist einfach die interne Form, in der die Tabelle Farbe hält, und sie ist hier die richtige – warum, sagt der nächste Punkt.
>
> • Die Lab-Nachschlagetabelle, der andere der beiden cLUT-Einträge: dieselbe Art Tabelle, die Farbe nur in einer anderen internen Form hält. Auf den Farben, die dein Target tatsächlich enthält, lagen die beiden Tabellen dicht beieinander, keine von beiden durchgehend vorn. Der Unterschied liegt am oberen Ende: Eine Lab-Tabelle hat eine harte Obergrenze und bleibt dort stehen; jeder Ton darüber wird auf einen einzigen Wert eingeebnet, während Shaper + Matrix und die XYZ-Tabelle beide weiterlaufen. Wie hoch diese Grenze liegt, entscheidet Erweitert… ▸ Weißpunkt-Behandlung. Mit „Weiß auf eine perfekt weiße Fläche skalieren“ liegt sie bei rund 114 % Reflexionsgrad, heller als eine perfekt weiße Fläche, nichts, was du auf das Glas legen kannst, erreicht sie also. Mit „Chart-Weiß auf Weiß abbilden“ fällt die Grenze auf etwa 94 % Reflexionsgrad, was gewöhnliches helles Papier durchaus erreicht, und alles darüber kommt eingeebnet an. (Beide Werte an einem echten IT8-Scan gemessen, deine eigenen werden also etwas abweichen.) Die XYZ-Tabelle hat unter keiner dieser Einstellungen eine Obergrenze, und deshalb ist sie die sicherere der beiden und deshalb kostet es nichts, sie zu nehmen.
>
> • Nur Matrix – die 3×3-Mischung und sonst nichts, ohne jede Tonwertkurve davor. Sie passt zu einem Gerät, das bereits perfekt linear ist, etwa einer Kamera im RAW-Modus. Bei einem gewöhnlichen Scanner war sie in jeder getesteten Größe um ein Vielfaches ungenauer als alle drei anderen und ist hier deshalb nicht die richtige Wahl.
>
> Genau um die hundert Felder herum liegen die ersten drei so dicht beieinander, dass die Wahl kaum eine Rolle spielt; erst darüber und darunter zeigt sich der Unterschied. Und was du auch nimmst: Ein anderes Papier oder ein anderes Target zu scannen verschiebt das Ergebnis weit stärker als der Profiltyp.
>
> ArgyllCMS hat zwei weitere Varianten, die diese Liste weglässt, und es lohnt sich zu wissen, dass es sie gibt. Sie legen eine einzige Tonwertkurve für alle drei Farbkanäle an statt einer eigenen Kurve je Kanal. Das ist keine Frage der Genauigkeit: Ihr erklärter Zweck ist die Kompatibilität mit Anwendungen, die ein Profil mit unterschiedlichen Kurven je Kanal ablehnen. Wenn eine Anwendung ein hier gebautes Profil nicht annimmt, erwähne das bitte als Erstes, wenn du es meldest.
>
> Qualität (-q): wie viel Detail und Anpassungsaufwand in das Profil geht. Bei den beiden Tabellentypen legt sie die Gitterauflösung der Tabelle fest, bei den Shaper- und Matrixtypen, wie fein die Tonwertkurven angepasst werden. Höher heißt feiner, aber langsamer, und lohnt sich nur mit besseren Daten. Sie gilt für jeden Profiltyp. Mittel ist ein guter Standard, Niedrig ein schneller Test, Hoch und Ultra sind für große, saubere Charts.
>
> Wenn du „Meinen Drucker aus diesem Scan profilieren“ ankreuzt, baut genau dieses Bedienelement stattdessen das Druckerprofil – ein anderes Gerät, eine andere Empfehlung. Der Typ ist dann auf „cLUT — Lab-Tabelle“ voreingestellt; öffne dieses ⓘ mit gesetztem Haken noch einmal, dann erklärt es dir warum. So oder so findest du hier keinen Arbeitsfarbraum (etwa sRGB) und kein Rendering-Intent; ein Rendering-Intent wählst du beim Drucken, nicht beim Erstellen eines Profils aus Messwerten.
>
> Nichts von alledem ist überliefertes Halbwissen. Die Profile wurden aus einem Teil zweier echter gescannter Targets gebaut und danach nur an den Feldern bewertet, die die Anpassung nie gesehen hatte – nur so bedeuten die Zahlen überhaupt etwas: Ein Profil, das an seinen eigenen Messwerten gemessen wird, schmeichelt einer Nachschlagetabelle erheblich.

#### 2 · The same ⓘ with "Profile my printer from this scan" ticked

> How the printer profile models colour.
>
> “Profile my printer from this scan” is ticked, so this window is building a PRINTER profile: your scanner is the measuring instrument, and the chart it reads is the one you printed. That changes what to choose here, so this is not the same advice you get for a scanner or camera profile.
>
> Profile type (-a): the shape of the maths inside the profile, and how it describes what your printer does with colour. There are two here, not the four you get with the tick off, and both build a working profile.
>
> • cLUT — Lab table — the default here, and what a printer profile should normally be. “cLUT” means a look-up table: instead of reducing your printer to a formula, the profile stores your measurements and interpolates between them. It also carries something the formula types cannot — the perceptual and saturation rendering intents, which are what decide how colours your printer cannot reach are eased inwards when you print a photograph. Everything under Advanced… ▸ Gamut Mapping describes those two intents, so it has nothing to act on unless the profile is a table. “Lab” is simply the internal form the table keeps colour in; it is ArgyllCMS's own default for this job, and it is what ChromIQ's Build Profile tab builds as well.
>
> • cLUT — XYZ table — the same kind of table, keeping colour in the other internal form. It is worth knowing why this window points at the XYZ table on the scanner side and not here. A Lab table cannot describe anything lighter than the white patch of the chart it was built from, and a scanner meets paper brighter than a scanning target's white board all the time. A printer never does — nothing it prints is lighter than the paper it prints on — so that reason does not apply here, and the Lab default stands.
>
> “Shaper + matrix” and “Matrix only”, which this list offers with the tick off, are not here. That is ArgyllCMS's rule and not a ChromIQ choice: colprof refuses to build a printer profile from a formula, and refuses it before it has read a single patch. The rule is not arbitrary either. By the way the ICC format works, a matrix-based profile cannot carry a perceptual or a saturation intent at all, so it would have nothing to fall back on when a colour is out of the printer's reach.
>
> Quality (-q): how much detail and fitting effort goes into the profile. For the two look-up-table types it sets the table's grid resolution; for the shaper and matrix types it sets how finely the tone curves are fitted. Higher is finer but slower, and needs better data to be worth it. It applies to every profile type. Medium is a good default, Low is a quick test, and High and Ultra are for large, clean charts.
>
> Untick “Profile my printer from this scan” and this control goes back to building a scanner or camera profile, where the default is “Shaper + matrix” and the advice is different — open this ⓘ again and it will tell you that story instead. Either way you won't find a working space (like sRGB) or a rendering intent in this row: the working space the gamut mapping uses is under Advanced… ▸ Gamut Mapping, and a rendering intent is something you choose when you print, not when you build a profile from measurements.

*German:*

> Wie das Druckerprofil Farbe modelliert.
>
> „Meinen Drucker aus diesem Scan profilieren“ ist angehakt, dieses Fenster baut also ein DRUCKERPROFIL: Dein Scanner ist das Messgerät, und die Testkarte, die er liest, ist die, die du gedruckt hast. Das ändert, was du hier wählen solltest – es ist deshalb nicht dieselbe Empfehlung wie für ein Scanner- oder Kameraprofil.
>
> Profiltyp (-a): die Form der Mathematik im Profil und damit, wie es beschreibt, was dein Drucker mit Farbe macht. Hier gibt es zwei davon, nicht die vier, die du ohne Haken bekommst, und beide bauen ein funktionierendes Profil.
>
> • cLUT — Lab-Tabelle – hier die Voreinstellung und normalerweise das, was ein Druckerprofil sein sollte. „cLUT“ heißt Nachschlagetabelle: Statt deinen Drucker auf eine Formel zu reduzieren, speichert das Profil deine Messwerte und interpoliert dazwischen. Es trägt außerdem etwas, das die Formel-Typen nicht können – die Rendering-Intents Perzeptiv und Sättigung, die darüber entscheiden, wie Farben, die dein Drucker nicht erreicht, beim Druck eines Fotos sanft nach innen geführt werden. Alles unter Erweitert… ▸ Gamut-Mapping beschreibt genau diese beiden Intents und hat deshalb nichts, worauf es wirken könnte, wenn das Profil keine Tabelle ist. „Lab“ ist einfach die interne Form, in der die Tabelle Farbe hält; es ist die eigene Voreinstellung von ArgyllCMS für diese Aufgabe und auch das, was der Reiter „Profil erstellen“ von ChromIQ baut.
>
> • cLUT — XYZ-Tabelle – dieselbe Art Tabelle, die Farbe nur in der anderen internen Form hält. Es lohnt sich zu wissen, warum dieses Fenster auf der Scanner-Seite zur XYZ-Tabelle rät und hier nicht. Eine Lab-Tabelle kann nichts beschreiben, was heller ist als das Weißfeld der Testkarte, aus der sie gebaut wurde, und ein Scanner bekommt ständig Papier zu sehen, das heller ist als das Weiß eines Scan-Targets. Ein Drucker nie – nichts, was er druckt, ist heller als das Papier, auf das er druckt –, deshalb greift dieser Grund hier nicht und die Lab-Voreinstellung bleibt richtig.
>
> „Shaper + Matrix“ und „Nur Matrix“, die diese Liste ohne Haken anbietet, gibt es hier nicht. Das ist die Regel von ArgyllCMS und keine Entscheidung von ChromIQ: colprof weigert sich, ein Druckerprofil aus einer Formel zu bauen, und weigert sich schon, bevor es ein einziges Feld gelesen hat. Willkürlich ist die Regel auch nicht. So wie das ICC-Format funktioniert, kann ein matrixbasiertes Profil überhaupt keinen perzeptiven und keinen Sättigungs-Rendering-Intent tragen, es hätte also nichts, worauf es zurückfallen könnte, wenn eine Farbe außerhalb der Reichweite des Druckers liegt.
>
> Qualität (-q): wie viel Detail und Anpassungsaufwand in das Profil geht. Bei den beiden Tabellentypen legt sie die Gitterauflösung der Tabelle fest, bei den Shaper- und Matrixtypen, wie fein die Tonwertkurven angepasst werden. Höher heißt feiner, aber langsamer, und lohnt sich nur mit besseren Daten. Sie gilt für jeden Profiltyp. Mittel ist ein guter Standard, Niedrig ein schneller Test, Hoch und Ultra sind für große, saubere Charts.
>
> Nimm den Haken bei „Meinen Drucker aus diesem Scan profilieren“ heraus, dann baut dieses Bedienelement wieder ein Scanner- oder Kameraprofil, wo die Voreinstellung „Shaper + Matrix“ heißt und die Empfehlung eine andere ist – öffne dieses ⓘ dann noch einmal, es erzählt dir stattdessen jene Geschichte. So oder so findest du in dieser Zeile keinen Arbeitsfarbraum (etwa sRGB) und kein Rendering-Intent: Der Arbeitsfarbraum, den das Gamut-Mapping benutzt, steht unter Erweitert… ▸ Gamut-Mapping, und ein Rendering-Intent wählst du beim Drucken, nicht beim Erstellen eines Profils aus Messwerten.

#### 3 · The dropdown's second marker

The factory default already carries "(default)", and that is unchanged. A
SECOND marker names which of the two cLUTs to take if you want one — **in
scanner / camera mode only** (`PTYPE_RECOMMENDED_CLUT = {False: "x", True:
None}`). The Lab option is NOT removed, NOT disabled and NOT relabelled: Knut
likes its results, it stays a legitimate choice, and picking it still emits
`-al` unchanged. The two markers can never land on the same item, and a
recommendation identical to that mode's default is refused by a test.

| mode | what the dropdown reads |
|---|---|
| scanner / camera | Shaper + matrix **(default)** · Matrix only · cLUT — XYZ table **(recommended cLUT)** · cLUT — Lab table |
| printer | cLUT — XYZ table · cLUT — Lab table **(default)** |

| proposed marker | German |
|---|---|
| **{option} (recommended cLUT)** | {option} (empfohlene cLUT) |

#### 4 · Three live notes, carried inside that same ⓘ

Not a new control, and nothing new on the face of the window:
`TooltipButton.set_live_note`, the mechanism Basti asked for on 2026-09-04
(*"a tooltip will be enough"*), which puts a note in FRONT of the standing help
and lifts only its first line into the hover tooltip. It changes no setting, and
it disappears on its own when it stops being true.

**An automatic switch was considered and REJECTED** (B8-19): the window learns
the patch count only after a chart or target is loaded, while the type is set
before it, so an automatic default would move the user's control under them —
and the crossover is shallow. A note is the proportionate form of the same
information.

> **⏳ Superseded, and awaiting confirmation, 2026-09-06.** *Knut asked for that
> automatic switch in beta 10 and Basti authorised it, so the paragraph above
> is no longer what the app does: the profile type, the quality and the white
> point ARE chosen from the patch count, by the rule in B8-78. The objection it
> records was answered rather than overruled. The window learning the count
> late is why the rule fires on `_refresh` and not at construction; the control
> being moved under the user is why it is refused for any bucket whose settings
> were saved or hand-edited (`_may_auto_setup`); and the crossover being
> shallow is why the note below still exists, for exactly the cases where
> ChromIQ may not choose. Read this paragraph as the reasoning that shaped the
> rule, not as the behaviour. **Confirmed by:** *nobody yet.*

Each one requires a KNOWN patch count, and none of them fires in printer mode,
where nothing was measured.

| when | note |
|---|---|
| Shaper + matrix chosen, and the target has 200 patches or more | (a) |
| either cLUT chosen, and the target has fewer than 100 patches | (b) |
| cLUT — Lab chosen, and (b) did not already fire | (c) |
| anywhere between, or the count not yet known, or printer mode | *nothing* |


**(a)** — shown here with a 288-patch target:

> A note on the profile type: your target has 288 patches, which is big enough for a look-up table to be worth it.
>
> Above about a hundred patches, a cLUT measured about a third more accurate than “Shaper + matrix” on real scanned targets, and “cLUT — XYZ table” is the one to take. “Shaper + matrix” is still a perfectly good, safe profile and it will not clip your highlights — this is a suggestion, not a warning, and nothing has been changed for you.

*German:*

> Ein Hinweis zum Profiltyp: Dein Target hat 288 Felder – groß genug, dass sich eine Nachschlagetabelle lohnt.
>
> Oberhalb von etwa hundert Feldern war eine cLUT bei echten gescannten Targets rund ein Drittel genauer als „Shaper + Matrix“, und die richtige davon ist „cLUT — XYZ-Tabelle“. „Shaper + Matrix“ bleibt trotzdem ein völlig brauchbares, sicheres Profil und beschneidet deine Lichter nicht – das hier ist ein Vorschlag, keine Warnung, und es wurde nichts für dich geändert.

**(b)** — shown here with a 48-patch target:

> A note on the profile type: your target has 48 patches, which is on the small side for a look-up table.
>
> Below about a hundred patches, “Shaper + matrix” measured more accurate than either cLUT on real scanned targets — a table needs plenty of well-spread patches before it has anything to interpolate between, and with fewer it starts fitting the noise in the scan. Your choice stands; this is only a suggestion, and nothing here has been changed for you.

*German:*

> Ein Hinweis zum Profiltyp: Dein Target hat 48 Felder, das ist für eine Nachschlagetabelle eher wenig.
>
> Unterhalb von etwa hundert Feldern war „Shaper + Matrix“ bei echten gescannten Targets genauer als beide cLUTs – eine Tabelle braucht reichlich gut verteilte Felder, bevor sie überhaupt etwas zum Interpolieren hat, und mit weniger bildet sie das Rauschen im Scan ab. Deine Wahl bleibt bestehen; das hier ist nur ein Vorschlag, und es wurde nichts für dich geändert.

**(c)** — shown here with a 288-patch target:

> A note on the profile type: “cLUT — Lab table” has a ceiling, and how high it sits depends on Advanced… ▸ White point handling.
>
> A Lab table cannot describe anything above that ceiling: every tone over it comes out at one lightness, with the differences flattened away. On “Scale white to a perfect white surface” the ceiling is at about 114 % reflectance, brighter than a perfect white surface, so nothing you can put on the glass reaches it and there is nothing to worry about. On “Map chart white to white” it drops to about 94 %, which ordinary bright photo paper does reach. “cLUT — XYZ table” has no ceiling under any of those settings and measured just as accurate on the colours your target does contain, so it is the safer of the two. Your choice stands either way, and nothing here has been changed for you.

*German:*

> Ein Hinweis zum Profiltyp: „cLUT — Lab-Tabelle“ hat eine Obergrenze, und wie hoch sie liegt, entscheidet Erweitert… ▸ Weißpunkt-Behandlung.
>
> Eine Lab-Tabelle kann nichts oberhalb dieser Grenze beschreiben: Jeder Ton darüber kommt mit einer einzigen Helligkeit heraus, die Unterschiede sind eingeebnet. Mit „Weiß auf eine perfekt weiße Fläche skalieren“ liegt die Grenze bei rund 114 % Reflexionsgrad, heller als eine perfekt weiße Fläche, nichts, was du auf das Glas legen kannst, erreicht sie also, und es gibt nichts zu befürchten. Mit „Chart-Weiß auf Weiß abbilden“ fällt sie auf etwa 94 %, was gewöhnliches helles Fotopapier durchaus erreicht. „cLUT — XYZ-Tabelle“ hat unter keiner dieser Einstellungen eine Obergrenze und war auf den Farben, die dein Target tatsächlich enthält, genauso genau, sie ist also die sicherere der beiden. Deine Wahl bleibt so oder so bestehen, und hier wurde nichts für dich geändert.

> **⏳ Awaiting confirmation, 2026-09-06 (CL-6).** *Note (c) above is not the
> wording Basti approved on 2026-09-04, and the wording he approved had stopped
> being true the day after: B8-75 moved the white-point default on 2026-09-05,
> and from then on this note told a user on the shipped default that their
> bright paper was being flattened and sent them to "Auto-scale to avoid
> clipping" to lift a ceiling that already sat at about 114 % reflectance,
> above anything that can physically be put on the glass. The same ⓘ gave two
> answers, 130 lines apart. It now names the ceiling and says what decides how
> high it is. **Confirmed by:** *nobody yet.*

*The other eleven catalogues carry the English source until this is ruled on,
because translating a draft translates it twice. German is translated, as the
beta convention has it. 22 keys arrive and 1 is retired — the retired one is the
sentence this item exists to remove, "XYZ and Lab are just how the table stores
colour inside; both are accurate, and Lab sometimes gives slightly smoother
neutrals", which nothing measured either way.*

*The dropdown's "(default)" markers are unchanged in BOTH modes: the
measurements support keeping **Shaper + matrix** as the scanner default (B8-19)
and say nothing against **cLUT — Lab** as the printer one, which is also
ArgyllCMS's own default and ChromIQ's own in tab 4
(`workflow/profile_builder.py`, `data/parameters.yaml`). If either default were
ever moved, the marker, the help and the recommendation would have to move in
the same commit or the window would contradict itself.*

### Button label — the driver consent window's decline button (AGENT-BD) — ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Proposed 2026-09-05 by AGENT-BD. Basti approved
the CHANGE — *"fix the ok button and the grammar, then land it"* — but not a
particular phrase, so the phrase is here for him to correct.

*Deliberately NOT given an `M-` identifier, for the reason the two sections above
give: §M is a catalogue of MESSAGES, each one rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading in this document to exist there. A button label is
not a message and must not be given a fake identifier to satisfy a parser. It is
recorded here because it is user-facing wording and this is where user-facing
wording is proposed and ruled on.*

`ui/dialogs/settings_dialog.py::_driver_notice` shows two kinds of window. With
no second button it is a NOTICE — it asks nothing, and **OK** is exactly the
right word for acknowledging one. With a second button it is an OFFER, and then
the plain button is the **DECLINE**: `ok.clicked.connect(dlg.reject)`,
deliberately, because `box.accepted` fires for OK too and that is how OK once
came to start an elevated driver install (`f7a565ad`).

The behaviour has been right since that commit and a mutation kills seven tests
if it is undone. **The WORD was still wrong.** On "Before ChromIQ starts" —
the one window in ChromIQ whose entire purpose is informed consent — the row
read `Herunterladen und installieren` and `OK`, and OK is the word most people
read as "yes". Somebody skimming clicks it meaning to agree and gets the
opposite of what they intended, which is the single mistake that window exists
to prevent.

| proposed label | replaces | German | where it appears |
|---|---|---|---|
| **Not now** | OK | Jetzt nicht | the dismissing button of any driver window that OFFERS something |

*It is not new vocabulary. `ui/cr30_calibration.py` already builds a button
labelled **Not now** for exactly this meaning — declining an offered action in a
window that can be opened again — so this reuses that key rather than adding a
thirteenth way to say no, and German is already translated. **Zero new
translation keys.***

*It is correct on all five offers this window makes — `Download and install`,
`Check and install`, `I already have the folder…`, `Choose a different folder…`
and `Try Zadig` — and nothing is lost by pressing it: every one of these windows
is reachable again from Preferences ▸ Instrument drivers…. A label naming the
action ("Don't install") would be correct on two of the five and wrong on three.*

*The alternative considered and not chosen was Qt's **Cancel** / `Abbrechen`,
which is equally unmistakable and also costs no new keys. It was rejected
because there is nothing in flight to cancel on three of the five windows — the
user is declining an offer, not aborting an operation — and because "Not now" is
already the house word for that.*

*Only the button's TEXT changes. It stays a `StandardButton.Ok`, so its role,
its place in the row and its identity to everything that looks it up are
unchanged, and it remains the dialog's default — the key most people press to
get rid of a window still declines. Measured in all thirteen languages, in the
dark appearance's wider button font, on a screen tall enough that the window is
not at its cap: the row fits, nothing is clipped, nothing runs past the edge
(`tests/test_usb_driver_dialog.py::test_the_consent_buttons_fit_the_row_in_every_language`).*

### The driver window's fifth ending — an install that has not finished (A9) — ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Proposed 2026-09-06 by A9. Nobody has ruled on
this wording; it is recorded here because it is user-facing wording on the
driver helper, and this is where user-facing wording on that window is proposed
and ruled on.

*Deliberately NOT given an `M-` identifier, for the reason the driver consent
button's section above gives: §M is a catalogue of MESSAGES rendered from
`workflow/measurement_messages.py`, and `tests/test_message_catalogue.py`
requires every `M-` heading in this document to exist there. The driver helper
is a Preferences window, not a measurement window, and must not be given a fake
identifier to satisfy a parser.*

**What was wrong.** `core/usb_driver_installer.py::install_winusb` waited 60 s
for the elevated installer, threw away what `WaitForSingleObject` returned, then
read `GetExitCodeProcess` — which answers `STILL_ACTIVE` (259) for a process
that has not finished. `259 != 0`, so the window said the install had **failed**
and offered **Try Zadig**. Measured on the bench 2026-09-06 against a real
driverless X-Rite i1Studio on an idle 2-core ARM64 VM, a *successful* install
took **48.6 s** (`00:41:24.501` → `00:42:13.129`) — 11.4 s inside that budget,
most of it Windows making a system restore point. On a machine that is actually
busy the window would have called a succeeding install a failure and sent the
user to replace a driver that was being installed as they read it.

**The window now has a fifth ending**, alongside *It worked* / *cannot tell you
whether that changed anything* / *did not take* / *failed or was cancelled*. It
is reached when ChromIQ stops WATCHING — because its five-minute budget ran out,
or because the user pressed the button that says so. It never says "failed", it
names no instrument, and it offers no Zadig button.

> **ChromIQ stopped waiting, and cannot tell you whether that worked.**
>
> The installer had not finished when ChromIQ stopped watching it. Nothing was
> cancelled and nothing was undone. Windows is very likely still installing the
> driver, and it may well finish on its own.
>
> Give it a moment, then open **Instrument drivers** in Preferences again and
> use **Check again**. That looks your instrument up afresh and says whether the
> driver is attached now.

*No instrument is named because there is nothing to point at:
`unbound_targets()` is deliberately not asked while an install is in flight — it
samples the same device stack wdi-simple is re-enumerating and can be wrong in
either direction. No Zadig button, because nudging somebody to replace a driver
while an elevated installer is still putting one in is the one action here that
could leave the machine worse than it started. Both onward controls are named
from the controls' own `tr()` keys via `_in_prose`, the same way the reboot
window and the "cannot tell" ending are, so they cannot drift from the buttons
in any of the twelve languages.*

**And the window that is on screen while it waits.** The install used to hold
the GUI thread: `Get-Process ChromIQ` reported `Responding = False` for ~50 s
with no spinner, no message and no cursor change, and the owner read it as a
hang (*"after confirming the uac nothing seems to happen"*, then *"it seems to
be hanging"*).

| what it says | when |
|---|---|
| **Installing the driver for {name}. Windows makes a restore point before it touches a driver, and that is most of the wait.** | from the first moment there is anything to wait for |
| button: **Stop waiting** | on that window |

*The window appears only once there is a wait — an install that ends at the
permission prompt takes 2-5 s and gets nothing flashed at it. It is
application-modal, which is what stops a second install, a closed Preferences
window or a quit while an elevated installer is running.*

*The button is **Stop waiting** and not Qt's **Cancel**. The section above
rejects `Cancel` on this window's other five offers because "there is nothing in
flight to cancel … the user is declining an offer, not aborting an operation".
Here something IS in flight — and it still cannot be cancelled: an elevated
driver install cannot be safely killed, and ChromIQ does not try. The button
stops ChromIQ watching, which is what it says, and the ending above says the
same thing again in a sentence. **Not now** was considered and is wrong for the
same reason: nothing is being offered.*

**And a sixth sentence, for an instrument ChromIQ never got to.** `Reinstall
Driver` runs over every detected instrument, one permission prompt each, and the
run stops after five of the endings — the user said No, Windows would not ask, or
an elevated installer may still be running and starting a second one while it
holds Windows' PnP install lock is a way to make a good install fail. Whatever
the instruments that WERE tried have earned, this is appended:

> ChromIQ stopped before it reached {names}. Nothing was tried there, and
> nothing was changed.

*It exists because the shipped code did the skipping SILENTLY and then blamed
the skipped instrument: `all(install_winusb(d) for d in targets)` is a
generator, so the first falsy answer ended the iteration, and the untried
instrument came back from `unbound_targets()` to be named in "the driver still
isn't bound to {names}" — a sentence about an install that never happened. It is
one sentence with no count and no pronoun, so it reads for one instrument and for
four without a singular/plural pair, the same way the "isn't bound to" sentence
beside it already does.*

*The permission prompt itself is still frozen time — `SEE_MASK_NOASYNC` makes
`ShellExecuteExW` block until the shell operation completes, so ChromIQ does not
pump events while Windows asks for consent. That is deliberate: consent must
stay a modal, deliberate act. It is a second or two, not fifty.*

### The measurement guard's "{where}" — a preposition glued to a translated noun (AGENT-BD) — ⏳ Awaiting confirmation

**Confirmed by:** *nobody yet.* Recorded 2026-09-05 by AGENT-BD. **No wording is
being proposed here** — every sentence below is the wording that already
shipped, re-cut so that each language can inflect it. It is recorded because
part of it is a §M concern and because the sibling defect named at the end is
one somebody has to rule on.

ChromIQ's driver helper refuses to open during a measurement and says why. That
paragraph used to be built by formatting `core.instrument_lease.where_label()`'s
noun phrase into `"…is being read right now, from {where}."` English survives
that, and German survives it only because both labels were hand-inflected into
the dative to fit. Rendered from the shipped catalogues, four languages did not:

| | what it produced | what the language needs |
|---|---|---|
| it | da la scheda Misura | **dalla** scheda Misura |
| pt | a partir de o separador Medir | a partir **do** separador Medir |
| pl | z karcie Pomiar | z **karty** Pomiar (genitive) |
| ru | из вкладке «Измерение» | из **вкладки** «Измерение» (genitive) |

*Nothing in the project could see it. `tests/test_i18n.py` sees a key that is
present, translated, and whose placeholder matches. `scripts/i18n_extract.py`
sees nothing at all — the broken sentences exist nowhere as literals, they are
assembled at run time, so no translator was ever shown one.*

*Hand-inflecting the label was the German fix (`8d5b8430`) and it cannot
generalise: two different sentences interpolate the same label with two
different prepositions, and a language with cases needs a different form of the
noun in each. So the WHOLE SENTENCE is the translatable unit now — one complete
sentence per holder, with nothing formatted into it — and each language writes
its own preposition, article and case. It is also its own paragraph rather than
glued to the next with a space, because ja and zh join sentences with 。and no
space: even joining two translated sentences is a decision the code must not
make on a translator's behalf.*

**The sibling, which is NOT fixed and needs a ruling.** `M-INSTRUMENT-BUSY`
("ChromIQ is measuring in {where}") is fed by the same `where_label()` and has
the identical fault — "in la scheda Misura", "in o separador Medir", "in karcie
Pomiar", "in вкладке «Измерение»" — and it is worse, because that sentence is
still the English source in eleven of the twelve catalogues. It is a §M message,
so its wording is not an implementer's to change; it is raised here and left
alone.

### M-x. Which table uses which message

**Calibration replacement** (`docs/design/calibration_run_type_plan.md` Table C,
and `docs/design/calibration_run_type.md` §4.4). Which of the two appears is
`Calibration.exists()`; what the code then does is `Calibration.result_files()`,
which is wider — see M-CAL-REPLACE-CHART.

| condition | message |
|---|---|
| `cal/` empty | none |
| `cal/` has a chart, nothing measured | **M-CAL-REPLACE-CHART** — and the chart is NOT kept |
| `cal/` has a `.ti3` and/or a `.cal` | **M-CAL-REPLACE-MEASURED** — everything moves to `cal/old/<date>/` |
| …and runs were built on that `.cal` | **M-CAL-REPLACE-MEASURED** + its `{runs_line}` |
| an archive was really made | **M-CAL-ARCHIVED-HERE**, in the log |

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

> **Two of those three limits are WITHDRAWN by §I.9 / §I.10 below.** They are
> left standing here because this section records what shipped; read them with
> the amendment.

### ⏳ Awaiting confirmation — §I.9 / §I.10, importing into a profiling run

**Confirmed by:** *nobody yet.*

**Amendment approved by:** Sebastian, 2026-08-31 — the RULE is his ruling; the
BEHAVIOUR is not built yet, which is why the line above still says nobody. It
is promoted only once he has seen it work.

Two findings drove it, both from shipped code rather than opinion:

* ChromIQ **already** builds a profile from a partial measurement made here,
  deliberately: `ui/tabs/tab_profile.py:4026` — *"A partial measurement is
  legitimate… this does not forbid it — it says how partial it is, and leaves
  the choice with the user."* Refusing the same data on import contradicts it.
* ChromIQ **already advertises** the banned capability. `ui/dialogs/tools_dialogs.py:1324`
  tells the user: *"Measured your chart in X-Rite's i1Profiler? This brings
  those readings back into ChromIQ so you can build a profile from them."*

**I.9 · A profiling run may be an import destination.** The IMPORT module is
offered while the shared Run type is **Profiling** as well as **Verification**.
Its sequence is §I.1–§I.8 unchanged, with three substitutions:

* **I.5** validates against the run's own chart, `Run.chart_ti2`, in place of
  the verification chart.
* **I.6** keeps its chart snapshot — for a profiling run that is the run's own
  chart, not the verification chart. Dropping it (an earlier draft of this
  clause did) would leave the filed measurement with no record of what it was a
  measurement OF.
* **I.7**: the measurement is copied to `Run.measurement_ti3` — the run's
  canonical stem, never the source file's name, because the report finds its
  chart by that stem (`measurement_report._find_reference_ti2`) and a
  measurement filed under any other name falls back to
  `reference_source: device` without saying so.
* **I.8** offers *Open measurement report* and *Build the profile*.

**Where the door is.** The module lives on the Measure tab for verifications.
For a profiling run the import is offered **in the Build Profile tab**, on the
control that already loads measurement data — that tab is disabled for
verification runs (`ui/main_window.py:1590`), so the tab a person is on already
says which act they are performing, and they are never sent to another tab to
perform it. Basti, 2026-08-31: *"clicking the button should allow me to do the
import there instead of skipping around"*.

**Choosing where it goes.** The load control asks: import into the open project,
or start a new one. With nothing open it offers to import into an existing
project, and performs ChromIQ's own Open Project act in place before carrying
straight on — one way to open a project, and no window that explains a fix and
then leaves the person to repeat what they just did.

**THE PATCH ORDER IS CHECKED, NEVER REPAIRED.** A measurement whose patches do
not line up with the chart is refused with an explanation. ChromIQ does **not**
re-pair it by matching device values, and this is deliberate (Basti,
2026-08-31, on measured evidence):

* `measurement_report.verify_patch_identity` cannot validate such a repair. It
  compares the chart's device values with the measurement's for each pairing —
  and a repair assigns the pairings by minimising exactly that difference, so
  it reports "verified" afterwards whether the repair was right or wrong.
  Measured: `mismatch, worst=100.0` before, `verified, worst=0.0001` after.
* A tolerant match — which a real implementation needs, because 23 of 240
  device values in ChromIQ's OWN demo chart differ from its measurement in the
  fourth decimal — can hand a reading to a patch **16.24 ΔE00 away** in design
  colour on real charts.
* The interchangeability rule ("patches asked to be the same colour may be
  swapped freely") holds for EXACT duplicates, measured on 22 of 24 real
  charts. It does not extend to tolerant neighbours.

A profiling run that **already holds a measurement** is not displaced. As for a
verification, the road to a second result is a new place to put it: ChromIQ
duplicates the run through `duplicate_run_plan` / `duplicate_run` and files the
import into the copy — **copying the CHART only**
(`groups=("chart",)`). Copying the whole run was driven on a real project and
made a run that contradicted itself: the copy carried the measurement, the
profile, `reads/`, `reports/` and a 153 KB export, every one of them orphaned
the moment the import overwrote the `.ti3` — while the confirmation window said
it was copying them for the person. Where `duplicate_source()` is `None` — the run has no
complete chart — the import is refused with the reason
`_duplicate_missing_phrase()` already writes.

**A calibration run still cannot import.** There is one `cal/` per project,
shared by every run, and `Calibration.reset()` has no `old/` archive
(`calibration_run_type.md` §3 D1), so an import there has no safe way to
displace what is present. This stays out until that defect is fixed — a
data-safety reason, not a preference.

**I.10 · A partial measurement is filed, not refused.** Withdrawn for both run
types. A measurement holding **fewer** readings than the chart has patches is
filed and the user is told **both counts** — M-IMPORT-PARTIAL-PROFILING or
M-IMPORT-PARTIAL-VERIFICATION. A measurement holding **more** readings than the
chart has patches is still refused (M-IMPORT-TOO-MANY): that is not a partial
measurement, it is a different chart.

**A file ChromIQ wrote must be a file ChromIQ will take back.** Its own real
verification read of 15 patches from a 105-patch chart could not be re-imported
by it.

**No threshold is set, and none may be added later without a measurement to
justify it.** Charts in use run from 64 to 2064 patches and quality falls off
with the absolute count, not the fraction, so any line drawn across it would be
arbitrary. ChromIQ states the counts and leaves the judgement with the person,
exactly as Build Profile already does.

**One measured caution for whoever implements this:** `colprof` builds silently
from as few as **4 patches** (exit 0, no warning), and its own self-check then
reports **0.016** — the best number in the table — for a profile **41.5 ΔE**
wrong against 924 real readings. The self-check is anti-correlated with quality
and must never be shown as reassurance. A missing **white** patch is a hard
failure (`rc=1`); a missing black one is not, so ChromIQ must not invent a
black-patch rule.

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

