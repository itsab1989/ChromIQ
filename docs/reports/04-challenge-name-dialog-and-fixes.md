# Challenge 2 — the name dialog, the B1–B6 fixes, and the i1Profiler round trip

STATUS: complete

Adversarial review of the uncommitted working tree on `master` (2026-08-30),
after report 03's six bugs were addressed and `ui/dialogs/name_prompt.py` was
built. Proof folder: `~/Desktop/knut-fixes-challenge-2/` (69 numbered
screenshots in `shots/`, backups in `backup/`).

## Method
- The **real** `MainWindow` in a **real** `QApplication`, on screen, driven
  through the real signals (`QComboBox.activated`, `QTest.keyClicks`,
  `_on_generate`, `_on_load_ti3`). No re-implementation of any code under test.
- A `QTimer` modal watchdog records every dialog that opens — class, title,
  buttons, every label, the line-edit contents — screenshots it, then acts.
  An unplanned modal is screenshotted and rejected, so a window that should not
  be there is a recorded *result*, never a silent pass.
- Data loss is measured by **SHA-1 fingerprints of every file in the project
  before and after**, not by folder listings. Folder listings hid the first
  overwrite; the fingerprints found it.
- Every claim about ink on paper is a **pixel count from a rendered TIFF**.
- Only the OS file chooser was stubbed (`open_file_dialog`), because a native
  `NSOpenPanel` cannot be driven. Everything downstream of it is the real code.
- Targeted `pytest` only. The gate was **not** re-run; no source file was
  edited at any point.

## Safety — NO DRIFT THIS TIME
Backed up before anything ran, checked after everything:

| | before | after |
|---|---|---|
| `~/Library/Preferences/com.chromiq.ChromIQ.plist` | `d45d76f1…` | **`d45d76f1…` — identical** |
| `~/Library/Preferences/ChromIQ/presets/` (18 files) | — | **byte-identical (`diff -rq` clean)** |
| `~/ChromIQ` top level (23 entries) | — | **identical** |
| `~/ChromIQ` to depth 3 (229 entries) | — | **identical** |

The redirect that leaked twice last session was strengthened with two things
the previous driver did not have: `core.i18n.QSettings` is redirected as well
as `core.settings.QSettings` (i18n reads `custom_output_path` from the real
plist directly, `core/i18n.py:64`), and a **tripwire on
`FileManager.root_dir`** that raises with a stack trace if it ever resolves to
`~/ChromIQ`. It never fired. `~/ChromIQ/CR30-Test` was never touched.

---

# 1. REGRESSIONS AND BUGS

## R1 — CRITICAL, NEW REGRESSION: a name typed in the new dialog is NEVER checked against existing projects, and silently overwrites one

**This is the exact fault the work set out to fix, rebuilt one layer down, and
it is worse than what it replaced because the name is now one a person chose.**

`_ask_for_a_project_name` (`ui/tabs/tab_chart.py:12131-12165`) does set
`_name_typed_by_user = True`, exactly as report 03's D2 required. The flag is
not the problem. **§S4.7 is asked before the dialog opens, on every route:**

| route | §S4.7 asked at | name asked at |
|---|---|---|
| prebuilt-file presets | `_apply_prebuilt_preset` — `tab_chart.py:11081` | `_create_prebuilt_target` — `tab_chart.py:11203` |
| Knut / TC9.18 / CM built-ins (.ti1) | `_generate_from_ti1` — `tab_chart.py:11403` | `_generate_from_ti1` — `tab_chart.py:11456` |
| Generate Chart | `_on_generate` — `tab_chart.py:12196` | `_on_generate` — `tab_chart.py:12384` |

Moving the guard above `_gate_route_and_replace` inside `_create_prebuilt_target`
did not help, because `_apply_prebuilt_preset` already asked the gate and passes
`gate_already_asked=True` (`tab_chart.py:11113`), which makes the inner call a
no-op. The comment at `tab_chart.py:12386-12388` states that "everything below —
the rename question and §S4.7 — must see the FINAL name"; §S4.7 is 188 lines
**above**, not below.

### Reproduction, driven, side by side, same name and same preset

`scripts/zz_p12_control.py`. Project `ZZ-ctl` exists and holds a chart.

**Control A — the name TYPED IN THE BOX** (`shots/CTL-typed-01.png`):
```
typed flag = True
MODAL: "There is already a project called “ZZ-ctl”"
       [Continue this project] [Replace it] [Use a different name] [Cancel]
Cancel -> files changed = []   files gone = []
```

**Control B — the SAME name, entered in the NEW DIALOG**
(`shots/CTL-dialog-01.png`):
```
MODAL: "Give this project a name"     <- and nothing else
files changed = ['runs/run1/ZZ-ctl.channels.json',
                 'runs/run1/ZZ-ctl.ti1', 'runs/run1/ZZ-ctl.ti2',
                 'runs/run1/exports/ZZ-ctl-colours.txt',
                 'runs/run1/exports/ZZ-ctl-i1profiler.pxf',
                 'runs/run1/exports/ZZ-ctl-i1profiler.txt',
                 'runs/run1/meta.json']
files gone    = ['runs/run1/ZZ-ctl.tif']
files new     = ['runs/run1/ZZ-ctl_01.tif']
```

Seven files of somebody's work replaced, the printed chart's `.ti2` — *the file
a printed sheet is read against* — among them, with **one** window on screen
and that window said nothing about an existing project.

Reproduced independently on the `.ti1` route (`scripts/zz_p4_collide.py`, C2:
the Knut i1Pro 648p built-in, same seven files, same silence) and on the
prebuilt route (C1).

**With a measurement and a profile already in the run** (`zz_p5`, case C4) the
`.ti3` and `.icc` are *archived* to `old/2026-08-30_233343/` rather than
deleted — so nothing is permanently destroyed — but **`MODALS SEEN: 1`**: no
§S4.7, and no §4 "this displaces results" window either. Knut, 2026-08-27:
*"Nothing shall ever be lost and user shall always be notified if there is a
risk of overwriting a project."* The second half of that sentence is broken.

**Why it is a REGRESSION and not the old behaviour.** At HEAD every built-in
seeded the field with the preset's own name and `_name_typed_by_user` stayed
False, so §S4.7 was silent *by design* on a name the app invented — and a name
the user typed in the box always reached the gate (Control A, unchanged). The
new dialog creates a third category the gate cannot see: a name a **person
chose** that the gate is never shown. Users reuse project names; preset default
names they do not.

## R2 — the new inspector warning fires on charts where the row numbers print perfectly

`ui/tabs/tab_chart.py:16500-16501` keys on
`geom.rlwi > 0 and geom.fill_beyond_ruler and geom.lbord > 0 and clip_side == "left"`.
`lbord` is derived from the clip **width** (`instruments.py:510`,
`_band = max(0.0, clip_band - border)`) and knows nothing about
`clip_content_mode`. But `raster.py:1334` pastes the clip strip **only** under
`if clip_content_mode != "off"` — with the content off nothing is pasted and the
digits survive.

Measured, real engine, i1Pro / A4 / area-first / clip border on the left, left
20 mm of page 1 at 300 dpi:

| clip content | rows off | rows on | warning fires? |
|---|---|---|---|
| `off` | **0 dark px** | **96 313 dark px, columns 153–235** | **YES — and it is false** |
| `notes` | 27 920 dark px (the notes) | 28 046 (+126, digits erased) | yes — correct |

So a user who turns the clip content off and ticks the box gets a full column of
row numbers on the sheet, and an inspector warning saying *"The row numbers will
not appear on this chart"* telling them to change the layout mode. Report 03's
B3 was "the warning says the opposite of what happens"; this is the same class
of fault, one condition over. `r.clip_content_mode` is in scope at that line
(`r` is bound at `tab_chart.py:16452`) — the check is simply not made.

## R3 — the row-number box is disabled but its value still reaches the engine

The Gap fix greys the checkbox when "Show strip indicators" is off. It does
**not** clear it, and `get_recipe` still reads it
(`ui/dialogs/layout_options_panel.py:3689-3690`), because
`_row_indicators_touched` stays True. Measured on the real panel
(`scripts/zz_p9_rows.py`, section F, `shots/F-strip-off.png`):

```
row box enabled = False   still checked = True
RECIPE: strip=False  row=True  rlwi=7.5
-> band reserved with nothing drawn in it: YES — 7.5 mm of dead paper
```

This is exactly the state attack F asked about, and exactly report 03's G1
outcome: 7.5 mm of the page is taken out of the patch area and nothing is
printed in it. The disable is cosmetic; it hides the control that is doing the
damage instead of stopping it. (Re-enabling works correctly, and a recipe
*loaded* with strip indicators off both disables and unticks the box, so only
the "tick it, then switch its parent off" order is affected — which is the
ordinary one, because the row box sits directly above the strip toggle's
dependants.)

## R4 — a name too long for the filesystem is accepted and leaves a half-built project

`ui/dialogs/name_prompt.py:57-77` has no length check. A 250-character name
passes `validate()` and is accepted (`scripts/zz_p13_longname.py`,
`shots/LONG-01b-typed.png`). The build then dies on the first sidecar:

```
[ERROR] Prebuilt copy failed: [Errno 63] File name too long:
  …/<250 chars>/runs/run1/<250 chars>.channels.json
MODAL 2: "Could not create target"   [Close]
```

and **leaves behind** `<250-char folder>/project.json`, `Where are my
files.txt`, `runs/run1/` and the copied `.ti1` and `.ti2` — a broken project the
user must delete by hand, with a 250-character name. #175 says a refused action
leaves nothing behind. macOS allows 255 bytes per component; the longest sidecar
suffix is `-i1profiler.pxf` (15 chars), so ~240 characters is the real ceiling —
measured directly: 240+15 = 255 bytes writes, 250+15 = 265 raises `OSError`.

## R5 — the destructive i1Profiler import path is not only reachable, it is the ONLY way forward

Report 03's D1 flagged that `ui/txt_loader.py` "Overwrite existing folder"
`rmtree`s while `ui/ti2_loader.py` "Replace existing" archives to `old/`. Driven
on screen (`scripts/zz_p6_i1p_roundtrip.py`, `shots/G-import-01b-typed.png`),
with the project `ZZ-challenge2-G1` **open in the app** and its own measurement
being brought back:

```
MODAL: "Choose a name for the profile"
typed: ZZ-challenge2-G1
ERRLABEL: "“ZZ-challenge2-G1” already exists.
           Click “Overwrite existing folder” to replace it."
button 'OK'                          enabled=True  visible=FALSE
button 'Overwrite existing folder'   enabled=True  visible=True
```

`_on_name_changed` (`ui/txt_loader.py:246-247`) **hides OK** on any collision.
There is no "add to that project", no "use a different name and keep both" — the
only enabled path forward under that name is a button that runs
`shutil.rmtree(dest)` (`ui/txt_loader.py:331`) on a whole ChromIQ project, after
one `QMessageBox` confirmation. So the natural action — "put my measurement into
the project it belongs to" — is answered by an offer to permanently delete that
project. The project rule is that user work is archived, never deleted;
`ui/ti2_loader.py:891-894` does exactly that for the same words. **Not a
regression** (both paths predate this work), but it is squarely in the blast
radius of G and it is destructive.

## R6 — the editor-hand-off route still names the project after the chart, with no ask

`ui/tabs/tab_chart.py:10973-10974`:
```python
name = (self._manual_target_name_edit.text().strip()
        if self._manual_target_name_edit is not None else "") or stem
```
`_import_applied_chart` gates §S4.7 at `:10969` and then falls back to the
chart's own **stem** with no name prompt of any kind. That is Knut's original
report — "the name was automatically defined … instead of asking user to define
a name" — still live on the Apply-from-the-layout-editor route. Static finding;
not driven (it needs a TI2-editor hand-off), so severity is stated as code, not
as a screenshot.

---

# 2. GAPS, OVERSIGHTS AND UI INCONSISTENCIES

**O1 — "only spaces" is a silent dead end.** `ask_for_project_name`'s
`_revalidate` (`name_prompt.py:139-142`) suppresses the message whenever
`not edit.text().strip()`, which is true for `"   "` as well as for `""`. Typing
three spaces therefore greys Continue, shows **no** error, and Return does
nothing at all. Driven: `return-spaces -> returned None, ok_enabled=False,
stayed_open=True, err=['']` (`shots/D-return-spaces.png`). The intent — don't
scold somebody who hasn't typed yet — is right; the condition should be
"the field has never been touched", not "the field trims to empty".

**O2 — an NFD name silently becomes a different folder.** macOS Finder and the
macOS clipboard hand out decomposed (NFD) text. Measured:

```
"Hahnemühle" typed  (NFC) -> folder  Hahnemühle
"Hahnemühle" pasted (NFD) -> folder  Hahnemu_hle
```

Same name on screen, two different folders on disk, no warning. Report 03's D8
item 9 predicted this and nothing normalises. Emoji go the same way:
`Canon 🎨 PRO-300` → `Canon-_-PRO-300`, accepted in silence.

**O3 — `_seed_preset_name`'s `target_name` argument is dead, and two comments
now describe a caller that does not exist.** `_on_preset_selected` sets
`name = None` unconditionally (`tab_chart.py:8137`) and is the only caller of
all four preset appliers (`:8228`, `:8230`, `:8232`, `:8234`). So the "A
*restored* name is still applied" half of `_seed_preset_name`'s docstring
(`:9276-9280`) can never run, and the edited comment at `:8701` — "a restored
run's name is seeded into it by `_seed_preset_name`" — is not true of any code
path. The behaviour is right; the documentation of it is fiction, and this file's
own history says stale comments here are how the last three faults started.

**O4 — the dialog's `body` parameter is never passed.** `name_prompt.py:78`
takes `body: str | None`; the only call site is
`tab_chart.py:12150 ask_for_project_name(self, prefill=current)`. Either the
per-route wording it was built for is missing, or the parameter should go.

**O5 — the "no room for the row numbers" warnings ignore the strip-indicator
switch.** `tab_chart.py:16481` and `:16486` fire on `geom.rlwi > 0` alone, while
the top-margin warning two lines above correctly tests
`r.show_strip_indicators`. On a SpectroScan with strip indicators off and a 0 mm
left margin the inspector says *"they will not be printed. Give the left margin
about 2 mm to get them back"* — 2 mm will not get them back, because
`raster.py:1217` draws them inside `if draw_indicators:`.

**O6 — `_create_prebuilt_target` reads one field and writes another.** The guard
tests `self._manual_target_name_edit` (`:11199-11201`) while
`_ask_for_a_project_name` writes into `_active_name_field()` (`:12147`,
`:12157`). They agree today only because `_activate_builtin_preset` switches to
Manual before the dispatch. Driven and confirmed benign (`zz_p11`, A-G2: both
fields end up correct), but it is one refactor away from `name` falling through
to `default_name` again — the branch this work just closed.

**O7 — the preset tooltips still state the ask unconditionally.**
`tab_chart.py:7322` "Picking it asks for a name, then copies the bundled patch
set" and `:7452` "Picking it asks for a name and builds the chart right away".
With a project open it correctly does **not** ask (proved: `zz_p6`, the second
build went into the open project without a window). Report 03's G5, unanswered.
Both are plain strings, not `tr()`.

**O8 — `_ensure_profile_name` is now unreachable from the preset routes.**
Worth a look before it rots: after this change its only remaining callers are
outside the built-in preset family.

## What I tried and could NOT break

- **E1–E5: the B1 fix is solid.** The real panel, every instrument, nothing
  touched: `i1/p3/CM → recipe None, rlwi 0.0`; `SS/CR30 → recipe None,
  rlwi 7.5`, each matching the shipped geometry exactly. Both directions
  (`SS→i1→CR30→CM→i1→SS→p3→SS`), zero mismatches. A **clicked** box sticks
  through every instrument change (True stays True, False stays False), and
  `set_recipe` round-trips `None/True/False` correctly on all five instruments
  **and shows the right box state for `None`** (ticked on SS/CR30, clear on
  i1/p3/CM). After an explicit `set_recipe`, the instrument sync correctly stays
  off; after a `None` recipe it correctly resumes. The instrument-switch trap is
  genuinely gone.
- **Cancel leaves nothing behind (#175).** Cancel on the name dialog:
  nothing on disk, name field still empty, `_name_typed_by_user` still False,
  `_pending_replace=None`, `_adopted_via_gate=False`,
  `_layout_owned_by_build=False`, and the dropdown back to `none`
  (`shots/A1-knut-i1-cancel-after.png`).
- **Continue really carries on and builds under that name**, on the .ti1 route
  and the prebuilt route, in Manual and in Guided: the project folder, the
  `.ti1/.ti2/.tif`, `channels.json` and both `exports/` sidecars all carry the
  typed stem.
- **Guided mode works.** Empty guided field + Generate Chart asks once and
  builds `ZZ-challenge2-GUIDED`; both name fields end up in step.
- **A busy runner is handled first.** With `_runner.is_running` True, picking a
  preset logs *"Built-in preset: a process is already running"*, opens **no**
  dialog and creates nothing — the `is_running` check sits above the ask.
- **Return accepts, Escape cancels, the window close button cancels.** All three
  measured on the real dialog.
- **Leading and trailing spaces are trimmed**; `///`, `...`, `-`, `a/b`, `:`,
  `\` are all refused with a readable reason; `2026` is correctly accepted.
- **248 targeted tests pass** (`test_project_name_is_never_invented`,
  `test_row_numbers_follow_the_instrument`, `test_layout_presets`,
  `test_knut_newbatch`, `test_project_name_collision`,
  `test_layout_options_panel`, `test_i18n`, `test_txt_loader`,
  `test_message_catalogue`). Report 03's B6 is fixed and `test_i18n` is green,
  so the twelve catalogues are complete.

---

# 3. WORDING

**W1 — R2's warning is wrong on the "clip content off" charts** (see R2). It
also asserts an absolute — "will not appear" — where the truthful version is
conditional. Suggested, subject to §M-PROPOSED:
> ⚠ The row numbers will not appear on this chart. "Prioritise chart area, then
> fit patches to it" gives their space to the patches, so they are drawn where
> the clip border's notes are printed, and the notes are printed over them.
> Switch to "Prioritise patch size, then fit to page" to get them back, put the
> clip border on the right, or set the clip border's content to "off".

and the condition must gain `and r.clip_content_mode != "off"`.

**W2 — the empty-box rule needs one more word.** O1: the dialog must
distinguish "you have not typed yet" from "what you typed is only spaces".

**W3 — the name dialog is otherwise good beginner English.** No "(s)", no
Markdown, no jargon; it names what the name is used for (folder, printed sheet,
ICC profile), gives a concrete example, and says the choice is reversible. The
tooltip is long but every paragraph earns its place. Count-bearing sentences
were checked: the tooltip says "two printed sheets", not "sheet(s)".

**W4 — "It costs 7.5 mm of paper down the left edge, so switching it on can
leave room for fewer or slightly smaller patches"** (the row-numbers tooltip)
is true in patch-first and understates area-first, where the 7.5 mm is spent and
— on a left-clip chart — nothing is printed. Report 03's W2, unchanged.

**W5 — the i1Profiler import wording is misleading about scope** (see §4):
"will be copied into your working folder as a new profile set" is accurate but
never says that the project you have open is not involved, and the collision
message offers only deletion.

---

# 4. THE ANSWER TO G, FOR SOMEBODY WHO DOES NOT READ CODE

**No. A measurement you make in i1Profiler does not come back into the project
you have open. It makes a brand-new project of its own, and the ICC profile is
built in there too. The project you were working in gets nothing.**

Driven end to end on screen (`scripts/zz_p7_g_full.py`, `zz_p8_g3.py`):

1. With **ZZ-challenge2-OPEN** open, ChromIQ made its chart and wrote the
   hand-off files for i1Profiler into
   `ZZ-challenge2-OPEN/runs/run1/exports/` — `…-i1profiler.txt` and
   `…-i1profiler.pxf`. That part is correct and easy to find.
2. A realistic i1Profiler measurement of that chart was brought back through
   **Build Profile → Load measurement data**, the real menu item.
3. ChromIQ asked *"Choose a name for the profile"* and said the file *"will be
   copied into your working folder as a new profile set"*. It **never mentioned
   the open project, never offered it, and never pre-filled its name.**
4. Answering "ZZ-challenge2-MEAS" created a whole new project:
   `ZZ-challenge2-MEAS/runs/run1/ZZ-challenge2-MEAS.ti3`.
5. Building the profile put the ICC there too:
   `ZZ-challenge2-MEAS/runs/run1/ZZ-challenge2-MEAS.icc`.
6. `ZZ-challenge2-OPEN` — the project whose chart was printed and measured —
   still has **no measurement and no profile**. Its run 1 holds only the chart.

**What the user sees.** Two things do warn them, and they are worth crediting:

- Pressing **Build Profile** raises *"This measurement is not in the run you
  have selected — the bar shows run1, but the measurement loaded here comes
  from: …/ZZ-challenge2-MEAS/runs/run1. A profile is always built beside the
  measurement it is built from, so pressing Build Profile now writes the profile
  into that folder — not into run1."* with **Build anyway** / **Cancel**
  (`shots/G2-build-01.png`).
- The **Profile Built** window shows the full path it saved to.

So the user is told *where the file went*. They are never offered *where it
should go*. The only way to end up with one project is to notice the warning,
cancel, and start over — and the one obvious thing to try, typing the open
project's own name at step 3, is answered with **"already exists — click
Overwrite existing folder to replace it"** and the OK button hidden (R5). The
natural recovery is a button that deletes the project.

**Two further facts:**

- **`.mxf` / `.cxf` behaves the same way.** `_import_i1profiler_cxf`
  (`ui/tabs/tab_profile.py:4251`) parses to a **temporary** folder and then
  calls `resolve_ti3`; a temp folder is outside the ChromIQ folder, so it takes
  the same "make a new project" branch. Confirmed by reading; the same
  `_project_root_for` decision applies.
- **A measurement that already sits inside *some* project uses THAT project,
  not the open one.** Driven: with `ZZ-challenge2-OPEN` open, a `.txt` dropped
  in `ZZ-challenge2-MEAS/runs/run1/` and loaded with "Continue" wrote
  `ZZ-challenge2-MEAS/runs/run1/ZZ-inside M0.ti3` — into the other project, and
  under a loose stem (`ZZ-inside M0.ti3`) so that run now holds two `.ti3` files
  with different names.

The mechanism, for the record: `ui/txt_loader.py:42-45` decides purely from the
file's own location (`_project_root_for(txt_path, working_dir)`); outside any
project it asks for a name and `_copy_txt` calls `Project.create(working_dir /
name)` (`:334`). Nothing anywhere in that file, or in `ui/ti2_loader.py`,
consults `FileManager`, the open target or the Profile-run bar. **The reporter's
code reading was correct.**

---

# 5. OPEN QUESTIONS FOR THE OWNER

1. **R1 is the tag-blocker.** Should §S4.7 be *moved* below the name ask on all
   three routes, or should `_ask_for_a_project_name` call the gate itself before
   returning True? The second is one place instead of three and cannot be
   forgotten by a fourth caller; the first keeps the gate where the comments
   already say it is. Either way `_apply_prebuilt_preset:11081`'s early gate
   must stop passing `gate_already_asked=True` when it ran on an empty name.
2. **R2** — should the warning simply gain `and r.clip_content_mode != "off"`,
   or should ticking the box be refused in that whole combination? (The owner's
   ruling was "warn, change no rendered output"; adding the condition honours it
   exactly.)
3. **R3** — with "Show strip indicators" off, should the recipe be *forced* to
   `show_row_indicators = False` (so the band is not reserved), or should the
   engine stop reserving `rlwi` when `draw_indicators` is off? The second fixes
   it for every chart including ones already saved; the first is local to the
   panel. Both change rendered output for a recipe in that state.
4. **G — the big one.** Should importing an i1Profiler measurement offer the
   **open project** as the destination (pre-filled, "add to
   ZZ-challenge2-OPEN / run 1"), and if so should it go into the current run or
   a new one? Today the workflow ChromIQ itself sets up — export, print, measure
   in i1Profiler, import — cannot be completed inside one project.
5. **R5** — should `txt_loader`'s "Overwrite existing folder" be replaced by
   `ti2_loader`'s archive-to-`old/` behaviour, so the two dialogs stop disagreeing
   about what the same word means? (Report 03's open question 7, still open.)
6. **R6** — should the editor hand-off ask for a name too, or is naming a chart
   after its stem right on that route?
7. **O2** — should the name be normalised to NFC before it becomes a folder?
   A user who pastes a paper name from Finder gets a different project from one
   who types it.
8. Should the name dialog cap the length (R4), and at what number — 200 is
   comfortably inside every sidecar suffix.

---

# 6. VERDICT

## NO — do not tag this as a beta.

**R1 alone is disqualifying.** The change makes it *easier* than before to
overwrite an existing project's chart without being asked, through the very
dialog that was added to make naming safer, and the fault is one the owner's
tester reported by name and the code comments claim to have fixed. Measured, on
screen, seven files replaced with one window shown; the identical name typed one
box over correctly raises the four-button §S4.7 window. It is a regression in an
already-working protection, which is the category this challenge was told to
weight most heavily.

**What would have to change for a yes:**

1. **R1 — required.** §S4.7 must be asked about the name the person typed, on
   all three routes. Prove it with a driven test that fingerprints the project
   files before and after and asserts the four-button window appeared, on both
   the prebuilt and the `.ti1` route — the existing unit tests all stub
   `_ask_for_a_project_name`, so none of them can see this.
2. **R3 — required.** A recipe must not be able to reach the engine with the
   band reserved and nothing drawn in it. Whichever way the owner rules in
   question 3, the current state (greyed box, live value) is the one outcome
   that is indefensible.
3. **R2 — required, and cheap.** One `and` on the condition. The owner ruled
   "warn, change no rendered output"; a warning that fires on charts that print
   correctly is not that ruling.
4. **R4 — should fix.** A length cap in `validate()`. Small, and it removes a
   path that leaves a broken project on disk.
5. **R6, R5, O1–O7 — can follow.** R5 and G (question 4) are pre-existing
   workflow faults, not regressions from this work; they deserve their own issue
   and their own verification pass, exactly as the owner ruled for B4.

Everything else in this batch is good work and holds up under attack: the B1
instrument-sync fix is correct in both directions and on all five instruments,
the tri-state round-trips everywhere it is stored, Cancel leaves nothing behind
on every route reached, the dialog's shape validation and its keyboard behaviour
are right, the wording is beginner-level and count-aware, all twelve catalogues
are complete, and 248 targeted tests are green.

STATUS: complete
