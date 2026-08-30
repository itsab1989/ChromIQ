# Report 44 — Create layout's sizing controls: one strategy in Basic, the other in Expert

**Author:** Claude (reviewing agent), for beta 3. **COMPLETE — recommendation
at the end.**

The owner, on screen (2026-08-30): the help for `Create layout` says
"Prioritise patch size — you set the patch size (or scale)…", but with that
strategy selected no sizing control is visible anywhere; and switching to
"Prioritise chart area" makes THAT strategy's sizing inputs appear inside
Basic, directly under the combo. One help text, two strategies, asymmetric
placement. He asked whether he was doing something wrong. He was not.

Constraints honoured: no `--runslow`, no source edits, no CR30/serial access,
nothing written to `~/ChromIQ/CR30-Test`, plist untouched. Every fact below
was established by DRIVING the real `LayoutOptionsPanel` offscreen — a fresh
panel per instrument, the instrument chosen through the combo the way a user
chooses it, row visibility read from the live widgets. A full app launch was
not needed: every question here is widget parentage and visibility, which the
real panel answers headless, and the owner's own screenshots already show the
on-screen rendering matches.

---

## 1. The facts, from running it — PROVEN

**The section map** (comment at `layout_options_panel.py:511-515`, confirmed
by widget ancestry at runtime):

| Section (state at open) | Groups |
|---|---|
| **Basic** (expanded) | Layout, Page geometry, Randomisation |
| **Expert Options** (collapsed) | Patches & spacers, Output, Sheet text, Clip-border content, Printer calibration |

**Where each strategy's inputs live** (fresh panel per instrument, run
offscreen; "on screen" = actually visible with Expert collapsed, as the panel
opens):

| Row | Section | area-first | patch-first |
|---|---|---|---|
| Calculation method | BASIC (Layout) | on screen | hidden |
| Minimum patch width / height % | BASIC (Layout) | on screen (method = By patch width) | hidden |
| Strips (columns) / Patches per strip | BASIC (Layout) | on screen (method = By columns/rows) | hidden |
| **Patch size (mm)** | **EXPERT** (Patches & spacers) | hidden | row flag SHOWN, **not on screen** (Expert collapsed) |
| **Patch scale** | **EXPERT** (Patches & spacers) | hidden | row flag SHOWN, **not on screen** |
| Max strip length | BASIC (Page geometry) | hidden | on screen |
| Chart offset (mm) | BASIC (Page geometry) | hidden | on screen |
| Don't cap strip length | BASIC (Page geometry) | hidden | on screen |
| Patch-area alignment | BASIC | hidden | on screen |

So in patch-first, Basic shows the mode's SECONDARY tuning (strip cap, offset,
alignment) while its DEFINING inputs — the size and scale the help leads with
— sit inside a section that is collapsed by default and whose relevant rows
only reveal themselves after the user both expands Expert and knows to look
under "Patches & spacers". PROVEN by the runtime probe on all five
instruments (i1, p3, CM, SS, CR30); expanding Expert makes Patch size / Patch
scale appear, exactly as `_sync_layout_mode`'s row flags say.

**`_sync_layout_mode` (`:2530`) toggles visibility only and never re-parents.**
PROVEN: section membership was identical in both modes for every row on every
instrument. The docstring even calls the hiding "symmetric" — it is symmetric
about *visibility flags*, and placement makes the symmetry invisible: one
mode's rows surface in the open section, the other's in the collapsed one.

**The CR30 and SpectroScan land exactly in the affected mode.** PROVEN: a
genuine user switch to CR30 or SS forces `patch_first` (`_on_instr_changed`;
SS also forces By columns/rows), so the instrument this beta is about drops
the user into the one strategy whose sizing inputs are off screen. The
i1/p3/CM fresh default is `area_first`, where everything lines up — which is
why this went unnoticed until a CR30 user (the owner) picked patch-first
deliberately and read the help.

**A side-finding, separate from the placement question:** a freshly
constructed panel's `Patch scale` / `Spacer scale` spinboxes sit at **0.5**
(their range minimum; `scale()` never sets a value), while `default_recipe`
says 1.0 — so `get_recipe()` on an unseeded panel reports `pscale=0.5`.
PROVEN by running it. In the app every production path seeds the panel first
(`load_target_settings` calls `set_recipe` — the "×4" note at
tab_chart.py:13828 — and the one known unseeded read, preset-undo's snapshot,
already documents and handles it at :7741). INFERENCE that no production path
reads it unseeded today; it is a latent trap for any new host of this panel.
One-line hardening: initialise both scale spins to 1.0 at construction.

## 2. Is the split deliberate, and is it binding? — (b): a recorded ruling outside any spec

- `docs/design/` was searched: **no specification covers** the Basic/Expert
  split of the layout panel, the two layout strategies, or this panel at all.
  PROVEN (grep over every design doc).
- The split is attributed to Knut in code comments (`:511` "split into two
  collapsible sections (Knut)"; the strategy machinery is "#93 / Knut"
  throughout). That is a recorded ruling **outside** a spec — category (b).
- Per CLAUDE.md the binding artefacts are the design specifications; a code
  comment is not one. Knut has left the project; his specs stay binding, and
  the project's standing default for his non-spec design rulings is "change
  nothing without approval" — **which the owner can now give**. This is
  therefore the owner's decision, not a spec violation, and not something I
  or the coordinator may decide alone.
- Worth putting in front of him: the project already has an APPROVED precedent
  for promoting a control out of Expert when circumstances make it primary —
  `calibration_run_type.md` (":493 / :696 / :844) lifts `-N` out of Expert
  Options when the device type has more than four inks. Making a strategy's
  defining input visible while that strategy is selected is the same design
  move.

## 3. The help text against what the code does — two inaccuracies, named separately

**Fault A (the owner's): the patch-first bullet points at controls the user
cannot see.** "you set the patch size (or scale) and ChromIQ fits as many
patches as it can" — the controls exist, work, and are routed into collapsed
Expert. Nothing in the help or the panel says where they are.

**Fault B (the silent-default question): with Expert never opened, the user
sets nothing — the app chooses.** PROVEN: `patch_x`/`patch_y` default to
"auto" (0) and the recipe then carries `patch_w_mm=0` → `build_kwargs` turns
0 into `None` → `instruments.build` uses the instrument's own recommended
patch size, scaled by Patch scale. That default is sensible and the CR30's
10 mm ruled patch depends on exactly this mechanism — but the help's "you set
the patch size" is untrue for everyone who never opens Expert, and no visible
control or caption shows the size that was chosen for them (only the preview
shows the result). This is a milder fault than A — the app chooses well — but
the help claims user agency the default flow does not exhibit, and it is what
turned the owner's confusion into "am I doing something wrong?".

**Fault C (found while checking B): the area-first bullet describes only ONE
of its two calculation methods — and not the default one.** The bullet says
"you say how many strips (columns) and/or patches per strip (rows) you want"
— that is the `By columns/rows` method. The default method on a fresh panel
(and for i1/p3/CM) is `By patch width`, whose visible inputs are `Minimum
patch width (mm)` and `Minimum patch height (%)`. PROVEN by the probe: a user
reading the bullet and looking under the combo sees neither of the two
controls the bullet names. Same shape as fault A, milder consequence (the
right rows are at least on screen).

## 4. The same shape elsewhere — one true instance; not a pattern

A programmatic scan of every Basic-section tooltip against every
Expert-resident row label (run on the live panel) found seven tooltips
mentioning "patch size", of which SIX use it as a concept or as the mode's
name ("Only used in 'Prioritise patch size'…"). Exactly ONE — `Create
layout` — describes an *action on a control* whose widget is in Expert.
Reverse direction (Expert tooltips naming Basic controls like paper/margins/
dpi) is common and harmless: those reference context, not actions the reader
must perform. The Guided tab has no equivalent (it has no Basic/Expert split
of engine layout controls; its layout is fixed per instrument). PROVEN by the
scan; INFERENCE that I have not missed a phrasing the label-matching could
not catch. One instance plus the help-wording faults — a bug, not a pattern;
the recommendation below does not need pattern-scale caution.

## 5. The options, judged

**(1) Move `Patch size` + `Patch scale` into Basic's Layout group, visible
only in patch-first — mirroring what area-first already does.**
- For: it is exactly the symmetry the help describes and the owner expected;
  the beginner's mental model rules the UI, and the beginner here followed
  the help and could not find the control; patch-first's secondary controls
  (Max strip, Chart offset) already live in Basic, so today's placement is
  inconsistent even with itself; the CR30/SS forced-patch-first paths land
  every user of those instruments in the broken half.
- Against: it moves rows Knut placed (needs the owner's ruling, §2); Basic
  grows by two rows — but only in patch-first, where the area block is hidden,
  so the NET Basic height stays roughly constant per mode.
- Risk: none to presets or stored per-target recipes — recipes store values,
  `set_recipe`/`get_recipe` address widgets by attribute, and no test pins
  section placement (checked: `test_layout_options_panel.py` round-trips
  values only). The fix lands in all four hosts of the panel automatically
  (Manual, From Profile Gamut, Preferences → Chart Layout, TI2 re-layout
  dialog) because there is one class. i18n cost: zero for the move itself
  (labels keep their keys), small for the help rewording.

**(2) Leave the rows in Expert; reword the help to say where they live.**
- For: no ruling needed beyond wording; smallest change.
- Against: the asymmetry the owner explicitly flagged remains — one strategy
  configured in Basic, the other in a collapsed section two clicks away; the
  help becomes a set of directions to a filing cabinet. It answers his first
  message and ignores his second.

**(3) Read-only echo of the effective patch size in Basic + a link that
expands Expert.**
- For: shows the silently chosen size (fault B) without moving anything.
- Against: new machinery (a live-updating caption wired to the estimate), a
  control the user still cannot edit where they expect to, and the link is a
  worse version of option 1. Disproportionate.

**(4) (Added) Keep placement, but auto-expand Expert when patch-first is
chosen.** Rejected: expanding a whole section (spacers, gaps, swatches, sheet
text …) to surface two rows buries them differently, and surprises anyone who
collapsed Expert on purpose.

**(5) (Added, complementary — not an alternative) Fix the three help texts**
(fault A's bullet, fault B's "auto" sentence, fault C's method mismatch) so
each bullet names what is actually on screen in that mode. Needed under EVERY
option above.

## 6. RECOMMENDATION

**Option 1 + 5, pending the owner's ruling** (the split is Knut's recorded
non-spec ruling, so the owner decides; the `-N` precedent in
`calibration_run_type.md` shows the move is within the project's established
design language).

**The exact change I would make** (I have edited nothing):

1. In `LayoutOptionsPanel.__init__`, build a `self._patch_fields_w` container
   in the **Layout** group, added at the same grid position family as
   `_area_fields_w` (row 1), holding the existing `_patch_size_row` and
   `_patch_scale_row` widgets — MOVED there (created against the Layout grid
   instead of the Patches & spacers grid), never duplicated. `patch_x`,
   `patch_y`, `pscale` keep their attribute names, signals and tooltips, so
   `get_recipe`/`set_recipe`/presets/per-target settings are untouched.
2. In `_sync_layout_mode`, show `_patch_fields_w` when `not area` (replacing
   the two rows' entries in `_patch_first_rows`); everything else unchanged.
   "Patches & spacers" in Expert keeps the spacer rows, which are mode-
   independent.
3. Reword the `Create layout` tooltip: patch-first bullet — "you set the
   patch size or scale below (leave at 'auto' for the instrument's
   recommended size) and ChromIQ fits as many patches as it can"; area-first
   bullet — describe BOTH calculation methods in one breath ("you either set
   a minimum patch width, or say how many strips and patches per strip you
   want — see Calculation method — and ChromIQ sizes the patches so the grid
   fills the usable area").
4. Run `python scripts/i18n_extract.py --missing de` and translate the
   reworded strings (CLAUDE.md i18n rule); the moved rows need no new keys.
5. Cheap hardening while in the file (side-finding §1): initialise `pscale`
   and `sscale` spinboxes to 1.0 at construction so an unseeded panel can
   never report a half-scale recipe.

**Verification I would pair with it:** extend the §1 probe into a small test —
for each instrument × mode, every control the `Create layout` help names must
be on screen (not merely row-flagged) in the mode its bullet describes. That
test fails today for patch-first on every instrument and for fault C's
by-width default, and passes after the change; it also pins the symmetry so a
future re-shuffle cannot silently break one half again.

**Needs the owner's ruling before any of it is touched:**
- Moving the two rows out of the Expert section Knut defined (§2, category b).
- The reworded tooltip text (plain wording change; tooltips are not §M
  messages, so no catalogue procedure — but he owns wording).
- Nothing here needs Knut's original reasoning reconstructed beyond what the
  comments record: the split predates the two-strategy machinery's growth, and
  the area-first block was already placed in Basic later without the patch
  half following — the asymmetry looks accreted, not designed.

**PROVEN / INFERENCE ledger:** §1 all PROVEN (runtime probes, five
instruments, both modes, Expert expanded and collapsed); §2 spec absence
PROVEN, category call INFERENCE from the recorded comments; §3 faults A/B/C
PROVEN (probe + `build_kwargs`/`instruments.build` chain read); §4 scan
PROVEN, completeness INFERENCE; §5 preset/recipe safety PROVEN for tests
(none pin placement) and structurally for recipes, INFERENCE that no
out-of-tree consumer cares about widget parentage.
