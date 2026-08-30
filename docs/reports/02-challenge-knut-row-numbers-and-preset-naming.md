# Challenge of report 01 — row numbers + preset naming

STATUS: complete

Adversarial verification of docs/reports/01-knut-row-numbers-and-preset-naming.md.
Every claim re-checked against the code at master (2026-08-30). Sections appended as work proceeds.

## A. Claim-by-claim verification
### A1. Issue 1 claims — verified, refuted, and what was missed

**VERIFIED — rlwi hard-wiring.** Every `Geom(...)` in
`workflow/layout_engine/instruments.py` checked: `rlwi=0.0` for i1/p3 (:474),
CM extra-high (:520), CM normal/high (:538), DTP41 (:740), DTP51 (:756);
`rlwi=7.5` for SS (:558) and CR30 (:717). No other Geom construction exists in
the app (`scripts/drive_46_aiming_overlay_report.py:272` does a `replace(g,
rlwi=0.0)` but that is a driver script, not the app). Nothing mutates `rlwi`
after `_build_base`. The report's line numbers are all correct.

**WRONG — "Gated on two conditions".** It is gated on THREE. The row-number
block (`raster.py:1217`, indent 16) sits INSIDE `if draw_indicators:`
(`raster.py:1181`, indent 12). `draw_indicators` IS the recipe field
`show_strip_indicators` — the "Show strip indicators" checkbox
(`presets.py:354` maps it into build kwargs; `layout_options_panel.py:3442/3585`
binds the checkbox). **So a checkbox that controls the row numbers already
exists: unchecking "Show strip indicators" on a SpectroScan/CR30 chart removes
the row numbers too.** Report 01 says "no checkbox" — false as stated. There is
no INDEPENDENT checkbox, which is what Knut wants, but any design must decide
whether the new row toggle stays nested under strip indicators (today's
behaviour) or becomes independent (changes SS/CR30 output for
strip-indicators-off recipes).

**Corollary the report missed:** on SS/CR30 with "Show strip indicators"
unchecked, geometry still RESERVES the 7.5 mm band (`geometry.py:147` keys only
on `fill_beyond_ruler`, never on `draw_indicators`) but raster draws nothing in
it. 7.5 mm of paper is spent on an empty band today. Any recipe-driven design
should fix or at least document this.

**WRONG — "p == 0 (leftmost strip only)" / open question 5.** `p` is the strip
index WITHIN THE CURRENT PAGE (`for page in range(layout.pages): ... for p in
range(n_passes):`, raster.py:1151/1166). Row numbers are drawn on the leftmost
strip of EVERY page, and `label_patch(_j + 1)` restarts at 1 on every page
(`_j` indexes `col_slots`, the per-page, per-strip slot list, raster.py:1179).
Meanwhile strip labels use `global_strip + 1` (raster.py:1176) and continue
ACROSS pages. So the printed grid is: columns numbered globally, rows numbered
per page. Not a bug today, but a fact the design must preserve (or Knut will
report the "wrong" one).

**WRONG — "the Patch pattern does reach paper here".** It does not.
`raster.py:1047`: `label_patch = permutation.make_labeller(permutation.DEFAULT_PATCH_PATTERN)`
— the row numbers use the HARD-CODED default pattern. The user's configured
patch pattern is accepted by `chart.py:54/185` and reaches only the `.ti2`
writer (`chart.py:363`); raster does not even take a `patch_pattern` parameter
(`raster.py:977` takes only `strip_pattern`). Knut's impression ("the patch
pattern only affects the files") is CORRECT, on every instrument including
SS/CR30. The two coincide today only because the default pattern is decimal
(`make_labeller` returns `str(n)` for non-alpha patterns, permutation.py:47-49).
Pick an alphabetic patch pattern and the sheet says "1,2,3" while the `.ti2`
locs say "A,B,C" — a latent sheet-vs-file mismatch report 01 asserts cannot
exist.

**MISSED — a collision warning system already exists.** `ui/tabs/tab_chart.py:16397-16407`
already warns, in the layout inspector, when `geom.rlwi > 0` and the left
margin is under 0.5 mm ("numbers will not be printed") or under 2 mm ("patches
will cover part of each one") — thresholds measured on a real CR30 chart. It
keys on `geom.rlwi`, so a recipe-driven rlwi inherits it for free.
`workflow/layout_engine/preflight.py` (the green/red badge) has no rlwi check
and arguably needs none — the inspector warning is the established home.

**VERIFIED — geometry/citations.** `geometry.py:147,279` (`_rlwi = 0.0 if
g.fill_beyond_ruler else g.rlwi`), the area-first rationale block
(geometry.py:125-146), the paper-edge clamp + Basti's 2026-08-30 ruling
(raster.py:1229-1240), `instruments.py:96` and the :638-644 rationale — all
check out.

**Half-wrong — "JSON key `draw_indicators`".** The USER-PRESET store serialises
recipes via `LayoutRecipe.to_dict()` = `asdict(self)` (presets.py:184-185,
PresetStore at :488-511), so the preset JSON key is `show_strip_indicators`.
`draw_indicators` is the BUILD-KWARGS key (presets.py:354, inside
`build_kwargs()`), used in channels.json and as the raster parameter — and it
doubles as the from_dict discriminator: a dict containing `nolpcbord` or
`draw_indicators` is treated as build-kwargs, not a recipe (presets.py:192).
Two different serialisations; the report names only one and attributes it to
the wrong store.

### A2. Issue 2 claims — verified, refuted, and the answer the report missed

**VERIFIED.** `_ensure_profile_name` (:9265) seeds only when empty;
`_set_manual_name_plain` (:9254) sets `_name_typed_by_user = False`;
`_typed_project_peek` (:8690-) returns None for a seeded name; callers at
:10104/:10145 pass `p.default_target_name`; the :9229 "81-character" comment
exists. All correct.

**WRONG — "no name prompt on any preset path".** Two errors:

1. `_ask_for_a_project_name` (`tab_chart.py:12066`) is a live name prompt
   (InfoDialog "Your project needs a name first" + focus into the field,
   Basti's #164 Q15 ruling "A NAME IS REQUIRED — never invent one"). It fires
   from `_on_generate` (:12309) and from `_generate_from_ti1` (:11393) whenever
   the field is empty and no project is open. A USER preset with an attached
   .ti1, an applied editor chart, and plain Generate all DO ask today. The
   built-ins escape it precisely because `_ensure_profile_name` fills the field
   FIRST — the seed defeats the guard.
2. The report grepped only for `QInputDialog`. The historic prompt was a
   custom `QDialog` (`_prompt_target_name`), which is why the grep found
   nothing.

**MISSED — the question "was this deliberate?" has a documented answer: YES.**
- `f11e592b` ("3.7.37: prompt for a target name when selecting a built-in
  preset") ADDED a name-prompt dialog for exactly Knut's scenario.
- `8996a25b` ("#70: decouple printer-profile name from chart layout (Knut's
  model)", 2026-06-18) DELETED `_prompt_target_name` and both its call sites;
  its commit message says verbatim: "built-ins generate under the current
  profile name **without a name prompt**".
- The code states the empty-field consequence is known and deliberate:
  tab_chart.py:11380-1390 — "That is deliberate and written down twice (#70,
  Knut's model)... The consequence worth knowing is... tracked as an issue: a
  preset chosen on a freshly started app creates a project with no window at
  all."

So Knut is remembering a real former behaviour that #70 — filed as HIS OWN
model — removed. The answer to him is not "the tooltips lied all along"; it is
"3.7.37 asked; #70 removed the ask; the tooltips were written in between
(44284a3c, May 25) and were true when written, then went stale at 8996a25b
(June 18)". Report 01's tooltip finding is real but it is the SYMPTOM; the
removal commit is the cause, and whether #70 truly meant "never ask even when
the field is empty" (vs. only "never overwrite a typed name") is the one
question for Knut/Basti.

**MISSED — tests encode the current behaviour as intent.**
- `tests/test_knut_issues_45_59_60_62.py:273` `test_preset_seeds_name_only_when_field_empty`
  asserts the seeded fallback verbatim ("#70: ... a seeded preset supplies a
  sensible fallback so the folder isn't created nameless").
- `tests/test_project_name_collision.py:459` `test_a_name_the_app_filled_in_never_raises_the_window`
  monkeypatches `QMessageBox.exec` to FAIL if any window opens on a seeded
  name — its docstring records that the release gate once caught a preset
  opening a modal in a suite that types nothing. Any "ask on preset" design
  collides head-on with this test and with the modal-in-suite problem it
  guards.
- `tests/test_project_name_collision.py:767` asserts a seeded name must not
  move the live preview to another project.

**VERIFIED end-to-end — the seeded name really becomes the folder/ICC stem.**
`_generate_from_ti1` reads the manual field (:11411), calls
`self._file_mgr.set_target_name(name)` (:11445);
`FileManager.set_target_name` (core/file_manager.py:2193) sanitises and points
the project at `<ChromIQ>/<name>`; the chart files carry the sanitised name as
their stem (CLAUDE.md folder-layout section). Prebuilt route: same via :11193.
Nothing later re-derives the name. Confirmed.


## B. Attack on the proposed directions
### B1. Issue 1 — attacking "recipe field + checkbox, rlwi from the recipe"

**The only backward-compatible default is a TRI-STATE, and the report never
says so.** `LayoutRecipe.from_dict` (presets.py:188-195) filters to known
fields and lets the dataclass default fill anything missing — a missing key is
NOT distinguishable from a value equal to the default once loaded. A plain
bool cannot work, exactly as report 01's point 2 says, but the report stops at
naming the problem. The answer: `show_row_indicators: bool | None = None`,
None = "instrument default" (7.5 on SS/CR30, 0 elsewhere). JSON `null`
round-trips through `asdict`/`json`; old preset files simply lack the key and
load as None.

**Proof the 121 built-ins are safe under None:** all built-in `layout_recipe`
dicts are literal dicts in tab_chart.py (`_CM_BASE` :929, `_P3_BASE` :998,
`_I1_BASE` :1277, `_I1_75_BASE` :1371ff, `_KNUT_SCANNER_RECIPE` :310); none
contains the new key, so every one loads as None → instrument default →
byte-identical output. Under a default of False, the SIX scanner built-ins
(`layout_recipe=dict(_KNUT_SCANNER_RECIPE...)`, instrument "SS", 6 occurrences)
would silently LOSE their row numbers. Under True, every i1/p3/CM built-in
would gain a band. Tri-state or nothing.

**The report missed the nesting decision.** Because the row block sits inside
`if draw_indicators:` (A1), the design must choose: (a) new checkbox effective
only when strip indicators are on (preserves today's SS/CR30 semantics), or
(b) independent (a user can have row numbers without strip letters — but then
`show_row_indicators=None` + strip-indicators-off on SS must STILL draw
nothing, or existing recipes change). (a) is the safe default reading.

**The UI restore trap.** A checkbox cannot display None. `set_recipe`
(layout_options_panel.py:3442 pattern) must render None as the instrument's
effective state and must NOT write back an explicit True/False the user never
touched — otherwise merely opening and re-saving a preset bakes the tri-state
into a bool (the recipe-panel-drops-unknown-fields class of bug, already in
the project memory).

**Collisions on the i1Pro are real and worse than "unverified".** The i1
built-in family is `layout_mode: "area_first"` with `margin_left: 26.0`,
`clip_border: True`, `clip_content_mode: "notes"` (_I1_BASE :1277-1326). In
area-first the band is not reserved (`geometry.py:147`), so raster draws the
numbers into `[margin_l - 7.5, margin_l] = [18.5, 26] mm` — INSIDE the clip
zone, whose notes content spans `[text_edge_clip=4, 26] mm`
(`geometry.py:400-418`: `clip_w = lbord + border`). Row numbers would print
OVER the notes text, and physically that strip is what the jig clamps. In
patch-first the band IS reserved after `margin_l`, so no overlap — but the
existing inspector warning (tab_chart.py:16397) only fires below 2 mm of left
margin and would say nothing about the clip-notes overlap. A new warning is
needed for: rlwi enabled + area-first + clip border on the same side.

**Width/digits.** The row numbers use the strip-indicator font and size
(raster.py:1063, shared `font`); the band stays 7.5 mm regardless. A large
`indicator_size_mm` makes digits wider than the band and they extend left past
it (only the PAPER edge clamps, raster.py:1236) — into the margin, or on the
i1 into the clip/notes zone. Three-digit rows are unlikely (rows restart per
page; ~50-70 max at 4 mm patches) but two digits at a large font already
overflow. No check exists for font-width vs band-width; the design needs one
or a width field.

**CHT/TI2/scanin.** Neither writer reads `rlwi`; both take patch coordinates
from the same `placement` the raster uses (x0 includes `_rlwi`,
geometry.py:318), so the .cht and the printed sheet shift together — scanner
alignment is safe for charts built and read as a pair. The hazard is only a
DEFAULT that changes output between app versions, which the tri-state
eliminates.

**Cost visibility (report point 1) — confirmed** (`geometry.py:148`,
`area_fit.py:38`): in patch-first, enabling the band changes strips-per-page
and possibly page count. The live inspector/preview already re-computes, so
"visible to the user" mostly comes free; the Guided path (patch-first, fixed
recipes) should simply never get the checkbox.

### B2. Issue 2 — attacking "keep seeding, ask when never typed"

**Every path that reaches a build with an app-seeded name**
(`_ensure_profile_name` call sites):
1. :9951 TC9.18 built-in ("TC9.18 by Pharmacist") — auto-runs on select.
2. :10018 ColorMunki built-ins — auto-run on select.
3. :10104/:10145 the 121 Knut built-ins (both engine and printtarg families;
   Knut's "i1Pro-A4-162p-1page-Portrait-w7.5mm" is the :10104 engine branch) —
   auto-run on select via `_apply_knut_preset` → `_generate_from_ti1`.
4. :11085 prebuilt-files built-ins (TC9.24/TC3.00 by Pharmacist) — MERE
   SELECTION copies the bundle (`_create_prebuilt_target`).
5. :10635 loading a .ti2 for reference (seeds `ti2_path.stem`) — does NOT
   build; a later Generate builds under it.
6. :10882 editor-applied chart (seeds the editor chart's name, then
   `_generate_from_ti1` immediately).
Paths that already ASK when empty: plain Generate (:12309), user preset with
attached .ti1 (auto-run ▶ included) via :11393 — the refuse-and-focus dialog
`_ask_for_a_project_name` (#164 Q15). The asymmetry is: routes WITHOUT a
bundled default ask; routes WITH one seed silently.

**Mid-auto-run ask is correct, at the existing guard, not at selection.** All
five refusals in `_generate_from_ti1` sit ABOVE `target_started.emit()`
(docstring :11334-1341), and `_create_prebuilt_target`'s gate likewise; a
refusal there returns False and #175's undo puts the tab back. So the ask
slots into the two existing guards by changing their condition from
"field empty" to "field empty OR (not `_name_typed_by_user` and not
`_is_named`)" — pre-filling the prompt with the seeded default so one Enter
keeps today's outcome. Asking at SELECTION time instead would (a) fire before
the §4/§S4.7 gates and create double-window sequences, (b) break
`test_a_name_the_app_filled_in_never_raises_the_window`'s intent (a suite that
types nothing must not hit a modal), and (c) reintroduce exactly what
`8996a25b` removed.

**Double-ask risk: real but manageable.** `_on_generate` asks at :12309 and
then routes into `_generate_from_ti1` (:11393) — today both key on the same
"field empty" condition and the first return prevents the second. The new
condition must stay identical in both places or one click can ask twice.
`_create_prebuilt_target` is reached from TWO callers (:11090 selection,
:12207 Generate-with-prebuilt-active) — the same family of double-window bug
that :12211-2216 documents for §4 ("raised the identical §4 window twice...
shipped 4.1.3 does it too").

**Open-project case is already handled** — the guard's `_is_named` arm: an
open project legitimately reflects its name via `_update_name_fields` (:5871,
also `_name_typed_by_user = False` at :5890), so keying on the flag ALONE
would wrongly interrogate a user who just opened a project. The compound
condition above is mandatory.

**Tests that break if the ask lands:**
- `test_preset_seeds_name_only_when_field_empty`
  (tests/test_knut_issues_45_59_60_62.py:273) — still passes if seeding stays
  (it tests `_seed_knut_preset` only, no build), but its documented rationale
  ("so the folder isn't created nameless") becomes stale.
- `test_a_name_the_app_filled_in_never_raises_the_window`
  (tests/test_project_name_collision.py:459) — patches `QMessageBox.exec`;
  whether it fails depends on the dialog class used, but its INTENT must be
  renegotiated: it asserts no interruption for seeded names.
- Any driver that selects a built-in preset headless
  (scripts/drive_130_test_plan.py etc.) will now block on the prompt — the
  suite-wide modal hazard CLAUDE.md warns about ("a test opening a modal
  dialog .exec()"). The prompt must be injectable/suppressible for drivers.


## C. On-screen reproduction
Both issues reproduced in the REAL app (real MainWindow, real event loop, the
combo's real `activated` signal), v4.1.5-beta.4, 2026-08-30. Safety: plist and
preset folder backed up first and restored/verified after; projects redirected
to a scratch root via `custom_output_path`; preset store sandboxed via
`CHROMIQ_PRESETS_DIR`; ~/ChromIQ (incl. CR30-Test) never touched. Proof folder
with numbered screenshots + INDEX.md:
`~/Desktop/knut-row-numbers-and-preset-naming/`.

**Issue 2, reproduced end to end.** Empty name field, no project open →
selected "i1Pro · A4-162p-1page-Portrait-w7.5mm · Full layout setup" → NO
dialog of any kind (modal watchdog polled every 400 ms), field silently became
`i1Pro-A4-162p-1page-Portrait-w7.5mm` with `_name_typed_by_user=False`, the
build ran unattended and created
`<root>/i1Pro-A4-162p-1page-Portrait-w7.5mm/runs/run1/i1Pro-A4-162p-1page-Portrait-w7.5mm.tif`,
and the sheet itself carries "profile name: i1Pro-A4-162p-1page-Portrait-w7.5mm".
Same for the scanner preset (69-character seeded name became the folder).

**Issue 1, reproduced.** The scanner (SS-layout) chart prints row numbers
1..49 down the left; the i1Pro chart from the same session prints none — its
left 26 mm is the clip/notes band. The full layout panel, Basic AND Expert
expanded, contains exactly one indicator toggle ("Show strip indicators") and
no row control (screenshots 05/08).

**Probe honesty note.** The first driver run produced a phantom
`Printer_Paper_Type_Instr_<timestamp>` target — caused by the PROBE itself
calling the mutating `get_target_name()`, and by `setCurrentIndex` not firing
the `activated`-wired slot. Both were fixed (non-mutating `_target_name` read;
`activated.emit`) before any conclusion was drawn — the "a probe that searches
too wide finds its answer somewhere else" trap, caught in the act. It is also
live evidence of what the :12303 comment warns `get_target_name()` does.


## D. Verdicts
### D1. What report 01 got WRONG
1. "Gated on two conditions" — there are three: the row-number block is nested
   inside `if draw_indicators:` (raster.py:1181/1217). The "Show strip
   indicators" checkbox already turns row numbers off on SS/CR30. "There is
   no ... checkbox" is therefore false as stated; there is no INDEPENDENT one.
2. "`p == 0` (leftmost strip only)" left the per-page question open — `p` is
   per-page: numbers are drawn on EVERY page and RESTART at 1 each page, while
   strip letters number globally across pages (raster.py:1151-1179).
3. "the Patch pattern does reach paper here" — false. raster.py:1047 hard-codes
   `DEFAULT_PATCH_PATTERN`; the user's patch pattern reaches only the files
   (chart.py:363). Knut's impression was correct on every instrument.
4. "JSON key `draw_indicators`" — that is the build-kwargs key (presets.py:354);
   the user-preset store serialises `show_strip_indicators` via `asdict`
   (presets.py:184, :488-511).
5. "grep -rn QInputDialog finds no name prompt on any preset path" — wrong
   method, wrong conclusion. `_ask_for_a_project_name` (tab_chart.py:12066,
   an InfoDialog, not QInputDialog) fires today on empty-name user-preset/.ti1,
   editor-chart and plain-Generate paths (:11393, :12309); and the historic
   prompt was a custom QDialog (`_prompt_target_name`) invisible to that grep.
6. The report treats "was this deliberate?" as settled by two stale tooltips.
   The decisive evidence is in git: `f11e592b` ADDED a name prompt for built-in
   presets; `8996a25b` ("#70 ... Knut's model") REMOVED it, saying "built-ins
   generate under the current profile name without a name prompt"; and
   tab_chart.py:11380-1390 documents the empty-field consequence as deliberate
   AND as a known tracked issue. Answer to Knut: yes, deliberate — under his
   own #70 model; the tooltips (written between the two commits) went stale.

### D2. Edge cases / oversights report 01 MISSED
1. The strip-indicators nesting decision (independent vs. nested row toggle).
2. SS/CR30 with strip indicators off still RESERVE the 7.5 mm band and draw
   nothing in it (geometry keys on rlwi alone).
3. The rows-restart-per-page vs. strips-numbered-globally asymmetry.
4. The existing inspector warnings for the row band (tab_chart.py:16397-16407,
   thresholds measured on a real CR30 chart) — the natural home for any new
   collision warning; preflight.py is not it.
5. The i1 built-in family is area-first with `clip_content_mode: "notes"`:
   enabling rlwi there draws digits over the notes text inside the clip band
   ([18.5, 26] mm vs. notes content [4, 26] mm) — a concrete, provable
   collision, not an "unverified interaction".
6. Row digits use the strip-indicator font/size; a large `indicator_size_mm`
   overflows the fixed 7.5 mm band with no warning.
7. Six of the 121 built-ins are SS ("Scanner" family) — a plain `False`
   default would strip THEIR row numbers; only a tri-state None default keeps
   all 121 byte-identical (from_dict fills missing keys with the dataclass
   default, presets.py:194-195).
8. Tests already encode the current issue-2 behaviour as intent:
   `test_preset_seeds_name_only_when_field_empty`
   (test_knut_issues_45_59_60_62.py:273) and
   `test_a_name_the_app_filled_in_never_raises_the_window`
   (test_project_name_collision.py:459, "the release gate caught it:
   selecting a preset opened a modal in a suite that types nothing").
   Headless drivers (scripts/drive_*.py) selecting built-ins would block on
   any new modal.
9. `.cht`/scanin safety: the writers take coordinates from the same placement
   as the raster, so recipe-driven rlwi shifts sheet and .cht together —
   alignment is safe; only a changed DEFAULT is dangerous.
10. The `from_dict` build-kwargs discriminator (presets.py:192) keys on
    `draw_indicators` being present — any new kwargs naming must not confuse
    recipe-dicts with kwargs-dicts.

### D3. Recommended designs

**Issue 1.** Add `show_row_indicators: bool | None = None` to `LayoutRecipe`
(None = instrument default: on for SS/CR30, off elsewhere — the ONLY value
that leaves every saved preset, all 121 built-ins, and every migrated
channels.json byte-identical). Plumb through `build_kwargs`
("draw_row_indicators", tri-state) → `chart.build_chart` →
`replace(geom, rlwi=...)`: None → keep table value; False → 0.0; True →
7.5 mm (the SS value; a width field can come later if wanted). Keep the raster
nesting under `draw_indicators` (preserves today's SS semantics; whether an
independent row toggle is wanted is Knut's/Basti's call — see open questions).
UI: a "Show row numbers" checkbox next to "Show strip indicators", displayed
resolved (checked on SS/CR30, unchecked elsewhere) but written back only when
the user touches it. Extend the inspector warnings for: enabled + area-first +
clip band on the left (digits over the notes/clip zone), and digit-width >
band width at the chosen indicator size. Also EITHER route the row labeller
through the recipe's patch pattern (fixing the sheet-vs-file mismatch and
Knut's actual first question) or state explicitly that row numbers are always
decimal — today's hard-coded default decided neither.

**Issue 2.** Keep the seed (visible in the field, #70's model intact for the
typed-name case), but change the two existing build-time name guards
(`_generate_from_ti1`:11391, `_create_prebuilt_target`'s entry, plus
`_on_generate`:12308 for symmetry) from "field empty" to "field empty OR
(`not _name_typed_by_user and not _is_named(fm)`)" — and, instead of the
refuse-and-focus InfoDialog, show a small prompt PRE-FILLED with the seeded
default so one Enter reproduces today's outcome. The ask lands mid-auto-run
and that is correct: it sits above `target_started.emit()` where all five
documented refusals already live, Cancel changes nothing (#175), and asking at
selection time would reintroduce the modal-in-suite hazard and double-window
sequences with §4/§S4.7. Both guards must share the exact condition (the
:12211 double-§4 bug is the cautionary tale). Update the two stale tooltips
(:7322, :7452) IN THE SAME change, whatever is decided — they lie today.
Update/renegotiate the two tests in D2.8 deliberately, and give drivers a
suppression hook. Per CLAUDE.md this touches user-facing message text: any new
dialog wording goes through §M-PROPOSED first
(docs/design/unified_measurement_management.md; test_message_catalogue.py
enforces it). Design-spec exposure (checked line by line): no spec
mentions rlwi or row numbers; per_target_settings.md:73 rules only that the
project name is GLOBAL (names the project, not a run) and per_run_description.md
T6.1-T6.9 covers description recompute on name change — neither constrains
seeding vs. asking. BUT per_target_settings.md:1.2 makes "the ChromIQ engine
on/off, and its whole layout recipe" per-target: a new `show_row_indicators`
recipe field automatically falls under that binding spec and its on-screen
test plan (per_target_settings_test_plan.md — every parameter, both states),
an obligation report 01 never mentions.

### D4. Open questions — only the owner (and Knut) can answer
1. Did #70 mean "never ask at all", or only "never overwrite a typed name"?
   `8996a25b` implemented the former in Knut's name; Knut's new report says he
   expected an ask when the field is EMPTY. The code comment at :11386 already
   tracks this as an issue — is that tracker the same as Knut's report?
2. Issue 1: should the new row-number toggle be independent of "Show strip
   indicators", or nested under it (today's behaviour on SS/CR30)?
3. Should enabling row numbers on a strip instrument RESERVE the band
   (patch-first: costs patch area, moves patches; changes .cht for rebuilt
   charts) or draw into the margin as area-first does (free, but collides with
   the i1 clip/notes band)? Basti's 2026-08-30 clamp ruling covers area-first
   only.
4. Row numbers restart per page; strip letters do not. Keep, or number rows
   globally when the feature goes public on more instruments?
5. Should the printed row numbers follow the user's Patch pattern (fixing the
   sheet-vs-file mismatch) — and if so, is an alphabetic row label acceptable
   on the sheet?
6. Is a pre-filled name prompt on built-in preset selection acceptable UX for
   the auto-run flow, or should the seeded name stand and only a non-modal cue
   (e.g. the existing "project exists" label style) mark it as provisional?
7. The seeded 81-character names: even with an ask, the DEFAULT offered is the
   preset name — should the default be something shorter/user-oriented?

STATUS: complete

