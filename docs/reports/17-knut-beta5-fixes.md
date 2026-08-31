# Report 17 — Knut's beta-5 batch: what was fixed, what waits on a ruling

**STATUS: fixed and gated** (K12, K3/K4-corruption, K5, K8, F1, F2, F5, plus
the four vacuous tests). Report 16 is the challenge this acts on.

---

## Fixed, each proven by a mutation that was shown to land

| # | What was wrong | Fix | Proof |
|---|---|---|---|
| **K12** | The window said *one press*, needed *two* over Bluetooth, and **closed before it started listening** — so presses made while reading it went nowhere | It listens while open, counts readings as they land, names the count the OPEN TRANSPORT needs, and closes itself. No confirm button left to answer falsely | `test_cr30_the_learning_window_listens_while_it_is_open.py` (6) |
| **K12a** | `open_transport` stole `@property` from `guard_is_armed` → truthy for every unit: the window could never appear, and the host trigger was allowed on an unlearned instrument | Both decorators restored | 454 existing CR30 tests passed WITH the bug; the new file fails 4 ways |
| **K12b** | "Not now" then a press → signal to a deleted label → PyQt6 abort | `sip.isdeleted` guard + disconnect on close | the real signal fired on the real worker after the real close |
| **K12c** | The window opened shorter than its own text, cut off mid-sentence | sized from `heightForWidth` after layout; scrolls only if the screen is genuinely too short; the live line pinned outside the scroll area | screenshots, three states |
| **K3/K4** | Visiting a run **destroyed** the setting stored on it: the chart sidecar re-imposed its recipe and the next write filed it into the target's store | The store keeps the target's own value unless the row has BOTH reported a change and moved | driver: `printtarg-i` stays `CR30`; disable the shield and it reverts to `CM` |
| **F1** | `ui:stamp` — a §1.2 **confirmed** per-target setting — was reset on every target change | The engine's one-time stamp default moved from `_refresh_manual_command_preview` (which fires from anything touching the panel) to the actual toggle | acceptance driver 83/83 with `ui:stamp` judged |
| **K5** | "Offset every second strip" and its tooltip drawn ON TOP of the Clip-border pair (cell 6,1 and 6,2) | moved a row; the test asserts the PROPERTY — no cell may hold two widgets — from the live layout | `test_the_layout_panel_has_no_two_widgets_in_one_cell.py` |
| **K8** | The printed row band ignored the chart's patch pattern: a chart set to `A-Z;1-999` printed rows `1, 2, 3` while its own `.ti2` called them `A, B, C` | the labeller takes the chart's pattern; the sidecar now records `patch_pattern` too (F4) | pages rendered and compared; default output unchanged |
| **F2** | Area-first stopped **7.45 mm short** of the right margin with row indicators on — the third site of the row-label subtraction, the only one without the `fill_beyond_ruler` guard | one guard, matching `geometry.py:147` and `:279` | all three sites asserted equal |
| **F5** | A failed tile learn wrote nothing at all | one note per ending, and a failure says how many readings it took and why they were not enough | — |

### The acceptance driver was green because it looked away

`scripts/drive_per_target_settings.py` excluded `printtarg-i` and
`ui:engine_recipe` — **the exact two values reported** — from every verdict,
including the on-disk one. The §10 sidecar ruling is about what is SHOWN;
nothing in it says the chart's values may be filed into the target's store. The
exclusion now applies to the on-screen verdict only, and the store is checked
for everything. `ui:stamp` was removed from that list altogether: it looked like
another sidecar-owned key, but §1.2 names it outright, and excluding it would
have hidden a confirmed-section violation behind an unsettled question.

**83 checks, 0 failed** — and this time the two reported values are among them.

### The four vacuous tests

Each now asserts a result, and each was proven to catch the mutation the old
one missed:

| Test | Was | Now |
|---|---|---|
| run picker | grepped for `"currentIndexChanged"` | drives the picker and asserts **which run the file lands in** |
| button order | captured the `order=` argument | reads the laid-out row; plus a scrambled order no role layout produces |
| no re-pairing | grepped four library names | asserts the **verdict** on a shuffled measurement (a hand-written nearest-neighbour repair now fails it) |
| shared helper | the word in a docstring passed | both loaders' real function is driven with the helper answering the opposite |

---

## Waiting on a ruling — nothing was changed

1. **§10 / K3+K4, the display half.** Should selecting a different profile run
   let the chart's sidecar overwrite the settings stored for that run? The
   corruption is fixed either way; what the screen shows is Knut's call.
2. **K1** — choosing the CR30 silently rewrites the layout mode and the
   spacers. Reproduced, deliberate, ungoverned.
3. **K6** — "Show row indicators" greyed while strip indicators are off. The
   greying is correct as the raster stands; whether the raster should change is
   a design question.
4. **K7** — label text size is global, and Preferences overrides the preset in
   both directions. Deliberate (#93), ungoverned.
5. **K9 / K10 / F3** — the row-label band's geometry. Knut's clause list is a
   specification and the code breaks four of five clauses; area-first draws the
   labels inside the clip band. **This must be written down before it is
   built** — it is one design, not three bugs.
6. **F7** — one instrument, two transports, two learns. Documented as
   deliberate for now; the three options are in report 16.

---

## Not safe to tag a beta yet

Report 16's verdict stands on everything above the line: the fixes are in and
gated, but items 1–5 are design decisions and K9/K10 in particular govern what
a chart looks like on paper.
