# Brief — Agent B: user-journey breaker (the screen)

You are the project's most demanding tester: a fine-art printmaker who has
just switched on "ChromIQ profile engine (beta)" and chosen "Maximum
accuracy", and a Qt engineer who knows how UIs lie. Your job: drive the REAL
app on screen like that person and break every user journey that involves the
engine's Maximum accuracy mode — Build Profile (Guided and Manual), the
engine-only rows, Preferences, presets, per-target switching, rebuilds,
quitting mid-build, and the "Build profile with scanner or camera" tool.
Repo `/Users/Basti/develop/ChromIQ`, branch `feature/engine-accuracy-challenge`,
venv `.venv` (`.venv/bin/python`). Read `CLAUDE.md` first — especially
"Driving the app on screen — sandbox the settings FIRST".

Read before anything else (in full):
* `~/Desktop/ChromIQ-engine-challenge/reports/orchestrator/01-plan-v1.md`
* `~/Desktop/ChromIQ-engine-challenge/reports/critic/01-critique.md` (§2
  verdicts, §3 N-items, §4 split — your items are the ones the critic says
  MUST be on screen; §6 damage rules).
* `scripts/engine_challenge/harness.py` (docstring + code) and
  `scripts/engine_challenge/smoke_harness.py`; the smoke log
  `~/Desktop/ChromIQ-engine-challenge/builds/smoke-harness-run3.log`.

## Permission and safety (verbatim rules)
You MAY and SHOULD launch the real app (a real `MainWindow` through the
harness, or `python main.py`), click real controls, use a VISIBLE window (not
`QT_QPA_PLATFORM=offscreen`), save screenshots and LOOK at them (Read the PNG).
If a step is blocked, report exactly what blocked it — never conclude
"on-screen is blocked".

Hard preconditions for EVERY launch: `CHROMIQ_SETTINGS_FILE` and
`CHROMIQ_PRESETS_DIR` set to YOUR sandbox (the harness does this), and
`custom_output_path` pointing at your sandbox. Never open anything under
`~/ChromIQ`; copies of the real charts are in
`~/Desktop/ChromIQ-engine-challenge/charts/` (critic M10: the 18p and 315p
files are junk measurements — use them only as "what does the app say about
a bad measurement"; 924p and 1168p are real ColorMunki spectral charts).
After your last run: `defaults read com.chromiq.ChromIQ custom_output_path`
must still be the owner's value or unset — record the output.

Do NOT edit files under `workflow/`, `ui/`, `core/`, `tests/`, `benchmarks/`
— the tree is frozen while you and Agent A measure it. You OWN
`scripts/engine_challenge/harness.py` and may fix/extend it (Agent A does not
touch it); record every change in your report. Your drivers go to
`scripts/engine_challenge/drive_B_*.py` (they will be committed as proof) and
scratch to `~/Desktop/ChromIQ-engine-challenge/work-B/`.

A modal that stops a driver is a FINDING, not an obstacle: the harness's
watchdog answers modals and RECORDS each answer in `modals_answered` — print
that list in every driver's summary. A step answered by the watchdog is
"assisted", not "passed". No `pytest --runslow`; single test files are fine.

**Staged report**: append to
`~/Desktop/ChromIQ-engine-challenge/reports/agent-B/01-findings.md` after
every completed journey — heading, what you did click by click, what you
expected, what you saw (screenshot path, and what is IN the picture), grade
**BUG / GAP / INCONSISTENCY / IMPROVEMENT / OK**, and whether it was measured
ON SCREEN or offscreen. Number findings `B-01…`. A killed agent loses at most
one journey.

## Journeys (in this order)

**B1. The switch-on journey, through the real Preferences window.** Open
Preferences → Beta with the mouse/keyboard path a user takes, tick "ChromIQ
profile engine (beta)", read the consent dialog (screenshot it, check its
text is complete and the buttons are readable), pick "Maximum accuracy" in
the Accuracy dropdown (screenshot the dropdown open — `widget.grab()` cannot
see a popup; use the harness's `screen=True` screencapture), close with
Save/OK. Then go to Build Profile → Manual: are the four engine rows visible
NOW, without re-visiting the tab (critic: `_refresh_engine_rows` runs on
showEvent — the test `test_settings_close_refreshes_engine_rows` claims a
refresh on Settings close; prove it on screen). Read every tooltip of the four
rows and the Accuracy tooltip; compare each claim with what Agent A's numbers
and the critic's M-items say (the tooltip says fast "finishes in a few
seconds" and accurate "several minutes longer"; measured: fast 101 s,
accurate 53 s on the 924p chart — S04). Report every wrong sentence.

**B2. Guided + accurate (A-Q1, S21).** Load the 924p chart in Guided, Build
Profile. Screenshot the tab during the build (busy headline, progress-bar
label — does it say which mode?), the log at the end, and the "profile
built" state. Does anything on the Guided screen tell the user the engine's
accurate mode built it, with the four engine options at their defaults?
Then Manual with identical settings: are the two profiles byte-identical apart
from the timestamp (they should be; if not, which tag differs)?

**B3. The four engine-only rows, one at a time, on screen (S17 UI side).**
For each row: change it, build, read the log for the promised line (spectral
physics on an RGB chart must SAY it did nothing — does it?; noise handling
must say which way it went; bijective must not also print "matched to
ArgyllCMS" — critic N11; ICC version 4 → a v4 file; Both → the `-v4.icc` twin
appears). Then: Save as defaults, restart the app (new harness boot on the
same sandbox), do the rows come back? Save a preset with the rows set, load
the preset — do they come back? (S16/critic addendum: expected to be per-preset
but NOT per-target.)

**B4. Per-target switching (S16).** Project with run1 and run2 (make a
second run in the app: New run), set the four rows on run1, switch to run2,
back to run1: expected per CLAUDE.md per-target rules; measured?

**B5. Rebuild over an existing profile (S13, S14; critic N12).** Build once
(Both v2+v4), build again: is the old `.icc` archived to `old/<timestamp>/`
and is the `-v4.icc` twin archived too, or overwritten in place? Open the File
guide (the "Where are my files" view) — does it list the twin? Does Install
offer the twin? Delete the run — is the twin deleted, left behind, or
archived? Then the failure case: make the build fail after archiving (e.g.
observer 2015_2 — critic N03 — or an unknown extra flag on a multi-ink
chart, N10): what is left in the run folder, and what does the failure dialog
say (screenshot; is the whole message "-g"?).

**B6. Quit and close mid-build (S15, critic N16, N20).** Start an accurate
build with `-S ClayRGB1998.icm` on the 924p chart; while the log shows
"Saturation table: matching colprof's rendering", close the window / quit
via the menu. Observe: does the app quit, hang, or crash; `pgrep colprof`
afterwards; a half-written `.icc`; leftover `oracle.ti3` temp dirs. Also:
while a build runs, try every control that should be locked (other tabs,
Open Project, Tools, the Build button) and screenshot the locked state.

**B7. The scanner/camera tool (A-Q3).** Tools → "Build profile with scanner
or camera", printer mode ("Profile my printer from this scan"). Use the
project from `~/ChromIQ/Knut-Scanner` — COPY the whole project into your
sandbox first (it has the scans, .channels.json and .ti2 needed). With the
engine + Maximum accuracy on: what does the command preview say (`colprof …`),
which builder runs, what does the log say, are any engine rows offered? Record
the exact inconsistency a user sees between the two windows. Then the same
measurement (`Knut-Scanner-printer.ti3`) loaded in Build Profile → Manual →
accurate: build; compare the two profiles' A2B1 on 20 device values via
`xicclu`. This is the evidence for the routing decision.

**B8. Bad inputs as the user sees them (critic N13, N17).** Load the 18p
stuck-instrument chart and the 315p junk scanner chart in Build Profile
(accurate): is a profile written without a word? What does the fit line say?
Then a `.ti3` with a NaN row: the error text on screen (critic M7 predicts
"cannot convert float NaN to integer").

**B9. Wording and i18n on screen (S20, S24).** Every line the engine writes
to the Build Profile log during an accurate build with all four rows on:
list them, mark which are untranslated f-strings (switch the UI language to
German in your sandbox and rebuild — which lines stay English?), and which
sentences a beginner cannot act on ("rows 757, 811" — S07: can you find
patch 757 on the printed sheet from that line? The sheet knows F20).

**B10. Timing as felt (S04).** With the log's timestamps: fast, bit-exact,
accurate on the 924p at q=m and q=h, each in a fresh app launch; the
progress percentage and ETA lines — do they ever go backwards, does "almost
done" sit for long, is the bar honest?

## Deliverable
`reports/agent-B/01-findings.md` (staged) + `reports/agent-B/02-summary.md`:
table of B-NN findings with grade, screenshot, repro driver name; and the list
of every modal the watchdog answered. Screenshots you cite must be copied to
`~/Desktop/ChromIQ-engine-challenge/screenshots/B-NN-*.png`. Return a ≤ 50-
line summary to the orchestrator. Time budget about 3 hours; the 924p accurate
build is ~1 min, fast ~2 min — plan builds accordingly and reuse sandboxes.
