# Third adversarial review — hexagon / honeycomb work, gate before 4.2.1 stable

Reviewer: third round. Branch `feature/nelson-photocard-presets`.
Started 2026-09-09. Bar: "would I sign this off to print on a paying customer's paper".

Prior rounds: 01-challenge, 02-regression, 03-pentest (3 shipped defects),
04-final (F1..F21, 4 blockers). Commits under review that NOBODY has reviewed:
`65939d80` (four blockers + fourth self-validating test) and `e0079b2d` (changelog).

Findings are numbered G1, G2, ... and appended AS THEY ARE MEASURED.

---

## Log

- [start] Report file created. Beginning with the two unreviewed commits.

---

## G1 — the margin inspector's ring allowance is `ring/2`, but a honeycomb's ink reaches further than that at the APEX. It still over-reports clearance, in the UNSAFE direction, on every ringed chart with edge spacers on.

**What I did.** Built real CR30 A4 honeycombs at 600 dpi through
`workflow.layout_engine.chart.build_chart` from a `LayoutRecipe`, with the page
furniture off (`nolpcbord=True`, no strip/row indicators, no chart text) so the
only ink on the sheet is the patch field. Measured the TRUE ink bounding box
from the rendered TIFF (`any(pixel < 250)`) and compared it against
`margin_inspector.measure_from_engine()` on a `channels.json` carrying that same
recipe. Probe: `<scratchpad>/g/g1b.py`, harness `<scratchpad>/g/probe.py`.

**Numbers** (positive delta = the tool claims MORE clearance than the ink leaves):

| orientation | ring mm | edge spacers | left | right | top | bottom |
|---|---|---|---|---|---|---|
| pointy-top | 1.3 | on | +0.000 | +0.027 | **+0.127** | **+0.159** |
| pointy-top | 4.0 | on | +0.000 | +0.027 | **+0.296** | **+0.328** |
| flat-top   | 1.3 | on | **+0.190** | **+0.217** | +0.000 | +0.032 |
| flat-top   | 4.0 | on | **+0.572** | **+0.598** | +0.085 | +0.116 |

**Why.** `margin_inspector.py:280-287` expands the patch bbox by
`round(hex_ring_mm/2 * dpi/25.4)` px on all four sides. That is exactly right on
the two sides where the hexagon's extreme is a FLAT edge (delta 0.000 / +0.027
above, i.e. one device pixel). It is wrong on the two sides where the extreme is
an APEX. `raster.py:1562` grows the outer band with
`hexagon.inset(_pts, -ring_px/2)`, and offsetting two edges outward by `d` moves
the vertex where they meet outward by `d / sin(interior_angle/2)`, which for a
120-degree hexagon apex is `1.1547 d`, not `d`. So the apex reaches
`0.577 * ring` past the hexagon while the tool allows `0.500 * ring`.

The error lands on whichever pair of sides carries the apexes, and that pair
FLIPS with the new orientation option: top/bottom on a pointy-top sheet,
left/right on a flat-top one. The measured left/right error on a flat-top sheet
(+0.19 / +0.22 at the default ring) is larger than the pointy-top top/bottom
error because the CR30 slot is not exactly a regular hexagon.

**Why it matters.** This is the same fault, same direction, same tool as F10,
which the previous round graded a blocker at 0.879 mm. It is smaller: 0.13 to
0.22 mm at the shipped 1.3 mm default, rising to 0.60 mm at the 4.16 mm the new
`build()` clamp allows. It exceeds the inspector's own tolerance floor
(`max(tol, 25.4/dpi)` = 0.085 mm at 300 dpi), so it is inside the range the tool
claims to resolve, on the one tool whose whole job is saying whether the ink
clears the paper edge. F10 fixed the missing allowance and left the wrong
allowance behind.

**Fix (one line).** Scale the allowance by the apex factor on the apex axis:
`ring/2 / sin(half interior angle)` on the axis carrying the apexes (top/bottom
when pointy-top, left/right when flat-top), `ring/2` on the other. Or, exactly
and without trigonometry, take the extremes of
`hexagon.inset(hexagon.vertices(...), -ring_px/2)` — the same call the renderer
makes.

**Confidence: HIGH.** Measured on rendered ink, eight configurations, the error
is zero on the flat-side pairs and non-zero only on the apex pairs, which is the
signature of the mechanism named.

## G1b — with edge spacers OFF the allowance is skipped entirely, and that is correct but leaves the report `ring/2` conservative. NOT a defect.

Same probe, `edge_spacers=False`: the tool under-reports clearance by 0.60 to
2.52 mm (ring/2), because the patch itself is inset by ring/2 and no outward
band is painted. It is in the SAFE direction and it does not hide an overflow;
the number it reports is the hexagon's own extent, which is what the layout
engine actually realised its margins to, so it cannot produce a false alarm
against the chart's own margin either. Recorded so the next reviewer does not
re-derive it. Nothing to fix.

---

## G2 — "Edge spacers" is INERT on i1 / i1Pro3 / ColorMunki, and because of that the margin inspector over-reports top and bottom clearance by 1.0 mm (i1, CM) and 1.99 mm (i1Pro3) on the DEFAULT chart. Bigger than the F10 blocker, on the mainstream rectangular path.

**NOT introduced by the hexagon work** — `presets.build_kwargs` has forced the
flag since `3cbb0a9b` (#93). Reported because the bar here is the printed sheet
and this is the same tool, the same direction, and a larger number than the
defect the previous round held the release for.

**The mechanism.** `workflow/layout_engine/presets.py:404`:

```python
"edge_spacers": (self.edge_spacers
                 or self.instrument in ("i1", "p3", "CM")),
```

The BUILD resolves the flag. Every consumer reads it RAW:

* `workflow/margin_inspector.py:257` — `if rec.get("edge_spacers"):` guards the
  whole pspa/ring allowance block.
* `ui/tabs/tab_measure.py:514` — `if not recipe.get("edge_spacers"): return 0`,
  the strip-hover frame height.

`LayoutRecipe.edge_spacers` defaults to **False**, `presets.default_recipe("i1")`
does not change it, and `layout_options_panel` shows the box unticked
(`:4539`) and stores what the box says (`:4719`). So the out-of-the-box Manual
i1 chart carries `edge_spacers: False` in its `channels.json` and prints WITH
edge spacers.

**Measured** — same harness as G1, real rendered ink vs `measure_from_engine`,
A4 at 600 dpi, page furniture off (`<scratchpad>/g/g2.py`):

| instrument | recipe flag | resolved | pspa | top delta | bottom delta |
|---|---|---|---|---|---|
| i1  | False | True | 1.0 | **+1.016** | **+1.005** |
| i1  | True  | True | 1.0 | +0.000 | -0.011 |
| p3  | False | True | 2.0 | **+1.990** | **+1.979** |
| p3  | True  | True | 2.0 | +0.000 | -0.011 |
| CM  | False | True | 1.0 | **+1.016** | **+1.005** |
| CM  | True  | True | 1.0 | +0.000 | -0.011 |
| SS  | False | False| 0.0 | +0.000 | -0.011 |

Positive = the tool claims more clearance than the ink leaves. The same chart
reported correctly with the box ticked and wrongly with it unticked, while the
two sheets are pixel-identical.

**And the checkbox is a lie either way.** i1 `edge_spacers=False` and
`edge_spacers=True` produce the same ink extremes (6.011 / 5.969 / 6.011 above),
so ticking or unticking "Edge spacers (bracket each strip)" changes nothing on
an i1, i1Pro3 or ColorMunki sheet. Its tooltip says *"It's optional"*. It is not
shown greyed or hidden for those instruments (only four references to
`edge_spacers_cb` exist in `layout_options_panel.py`, none of them
`setVisible`/`setEnabled`).

**Fix.** One resolver, the way `recipe_is_flat_top` was added for the flat-top
flag in this very feature: give `LayoutRecipe` an
`edge_spacers_resolved()` (or a `hex_support.edge_spacers_of(recipe)`) and make
the two raw readers call it. The new whole-tree grep test written for
`hex_flat_top` (G5 below) is exactly the shape of guard this needs.

**Confidence: HIGH** for the numbers (rendered ink, seven configurations).
**Confidence: HIGH** that it is pre-existing and not a regression of this branch
(the forcing predates it; confirmed against `e1aeaf2f` in G8).

---

## G3 — EVERY patch count in the new changelog section is wrong. Two of the three "before" numbers are old SPACER capacities, the third number appears nowhere, and one "after" number belongs to a different paper.

`CHANGELOG.md`, v4.2.1, "Straight strips: the CR30 honeycomb can be turned 30
degrees" claims:

> on A4 portrait 368 becomes 360, on A4 landscape 368 becomes 378, on Letter
> 352 becomes 361.

**What I did.** Computed one-page capacity through
`geometry.compute(geom_from_build_kwargs(default_recipe("CR30", paper)
.build_kwargs()), w, h, 5000)` — i.e. the app's own shipped CR30 recipe — at
HEAD and at the branch point `e1aeaf2f` (in a `git worktree`), with
`CHROMIQ_SETTINGS_FILE` sandboxed so no Preferences leak in. Probes
`<scratchpad>/g/g3base.py`, `g3e.py`, `g3g.py`, `g3h.py`.

**What the turn actually costs, at HEAD:**

| paper | pointy-top | flat-top | changelog says |
|---|---|---|---|
| A4 portrait  | **405** | **391** | 368 -> 360 |
| A4 landscape | **396** | **416** | 368 -> 378 |
| Letter       | **375** | **378** | 352 -> 361 |

Not one of the six numbers is right. The DIRECTIONS are right (portrait loses,
landscape gains, Letter gains), which is presumably why nobody noticed.

**Where the wrong numbers came from.** Same recipe, same sandbox, at the branch
point `e1aeaf2f` with spacers switched ON (the old bar-in-the-pitch):

| paper | base, spacers off | base, spacers ON | HEAD, spacers ON |
|---|---|---|---|
| A4 portrait  | 405 | **360** | 405 |
| A4 landscape | 396 | **352** | 396 |
| Letter       | 375 | 330 | 375 |

`360` is the OLD A4-portrait capacity with the spacer bar. `352` is the OLD
A4-landscape one. `378` is HEAD's **Letter** flat-top count, printed against A4
landscape. `368` and `361` do not occur anywhere in this sweep. The three pairs
are numbers from a different comparison, shuffled between papers, and presented
as the cost of the rotation.

**I looked for a configuration that would make them right and there is none.**
`368` never appears as an A4-portrait pointy-top count on the CR30 default
recipe over a full four-way margin sweep of
{4,6,8,10,12,13,14,15,17,20,26,34} mm on all four edges (20,736 layouts,
`g3h.py`): **zero** hits. The same sweep for the claimed pair (368 -> 360):
**zero** hits (`g3g.py`).

**The 9-strips-of-26 claim is also a number from one harness, stated as a fact.**
The changelog says *"a sheet that held 9 strips of 26 with them off still holds
9 strips of 26 with them on, where it used to drop to 23"*. On the shipped
CR30 default recipe, a 210-patch A4 honeycomb is **8 strips of 27** with spacers
off and **8 of 27** with them on at HEAD; at the branch point it was 8 of 27 off
and **9 of 24** on. The 9x26 / 10x23 figures come from the earlier reports' own
`build_chart` harness (300 dpi, different furniture), not from the app.

**What IS true and is the claim worth making:** at the branch point, switching
spacers on cost patches (A4 capacity 405 -> 360, 45 patches, steps 27 -> 24); at
HEAD it costs none (405 -> 405, steps 27 -> 27). And the turn really does keep
the patch the same size: pointy `pwid 12.000 x plen 10.392`, flat-top `pwid
10.392 x plen 12.000` — the same hexagon on its side, so "nothing is stretched
and each patch holds the same ink" is correct.

**Why it matters.** The changelog tells a CR30 owner what to expect on the sheet
they are about to print, and it tells them six numbers, none of which their
machine will show. The instruction for this round was explicit that a changelog
that lies is a defect; this one does, on the one paragraph that was added
*because* the previous round graded the omission a blocker.

**Fix.** Either quote the measured pairs above with the configuration they were
measured on ("on the CR30's own default layout"), or drop the numbers and keep
the sentence that already carries the useful instruction — *"Watch the count
beside the preview."*

**Confidence: HIGH.** Reproduced at both revisions from the app's own default
recipe, and the wrong numbers are individually traceable to the comparison they
were taken from.

---

## G4 — **THE FIFTH SELF-VALIDATING TEST, AND THE F11 FIX DOES ALMOST NOTHING.** `hex_max_sample_fraction` is given the slot in PIXELS and the ring in MILLIMETRES. At 300 dpi the ring correction is 12x too small: the dialog offers 63 % where the ink supports 49 %.

**This is the one the brief said to assume exists.** It is a blocker.

**The mechanism.** `ui/dialogs/scanin_dialog.py:4340-4352`:

```python
ws = sorted(float(p["w"]) for p in patches if float(p.get("w", 0)) > 0)
hs = sorted(float(p["h"]) for p in patches if float(p.get("h", 0)) > 0)
frac = hex_max_sample_fraction(ws[len(ws) // 2], hs[len(hs) // 2],
                               flat_top=flat_top, ring_mm=ring_mm)
```

`patches` are the engine's recorded rects from `channels.json`, produced by
`geometry.patch_rects_px` — **pixels** (`margin_inspector` multiplies the same
`r["w"]` by `px2mm` to get millimetres). `ring_mm` comes from
`hex_support.ring_mm_of`, which reads `geom.hex_ring_mm` — **millimetres**.

Inside the function (`workflow/scanin_runner.py:180-184`):

```python
short = min(w, h)                 # 162 px
k = (short - ring_mm) / short     # (162 - 1.3) / 162 = 0.992
```

1.3 mm at 300 dpi is 15.35 px. The code subtracts 1.3 px. The un-ringed formula
is a pure ratio and therefore scale-free, which is why passing pixels was
harmless before this parameter existed; adding an ABSOLUTE length broke it
silently.

**Proof it is a unit bug, not a modelling one: the cap depends on the chart's
DPI.** Same physical CR30 A4 honeycomb, same 1.3 mm ring, built at three
resolutions (`<scratchpad>/g/g5.py`):

| dpi | slot px | cap AS SHIPPED | cap if the slot is passed in mm |
|---|---|---|---|
| 200 | 125 x 108 | 62 % | 52 % |
| 300 | 187 x 162 | 63 % | 52 % |
| 600 | 374 x 324 | 63 % | 52 % |

A fraction of the patch cannot depend on how finely the patch was rastered.

**What it costs on paper.** On the real CR30 honeycomb geometry
(`instruments.build("CR30", hflag=True, spacer_on=True)`, slot 12.000 x 10.392
mm), integrating the sample box against the true readable hexagon
`hexagon.inset(vertices, ring/2)` on a 2000 x 2000 grid
(`<scratchpad>/g/g5b.py`, `g5c.py`):

| ring | cap AS SHIPPED | correct cap | spacer inside the read box at the shipped cap | at the 60 % DEFAULT |
|---|---|---|---|---|
| 1.30 mm (the default) | 63 % | **49 %** | 2.01 % | **1.19 %** |
| 2.50 mm | 62 % | **37 %** | 8.66 % | **6.66 %** |
| 4.00 mm | 61 % | **24 %** | 29.08 % | **28.13 %** |

The commit message for `65939d80` states the fault it was fixing as *"offering
64 % where the ink inside a 1.3 mm ring supports 49 %, so every read averaged
spacer colour into the measurement"* and *"averaged 2.3 % of spacer colour"*.
Measured after the fix: 63 %, and 2.01 %. **The fix delivered 0.3 of the 2.3
percentage points it was written to remove**, and the number it was aiming at
(49 %) is exactly what the corrected units give.

And the Sample area spin box **defaults to 60 %** (`scanin_dialog.py:2407`),
which is above the true 49 % cap, so a user who never touches the control still
averages 1.19 % spacer into every patch of a scanner-read honeycomb — and
6.7 % / 28 % at the larger rings the new `build()` clamp permits.

**Why the suite did not catch it — the fifth self-validating test.**
`tests/test_the_honeycomb_spacer_is_a_ring.py:735-761`,
`test_the_sample_cap_shrinks_with_the_ring`:

```python
g = I.build("CR30", hflag=True)
base = cap(g.pwid, g.plen)
got  = cap(g.pwid, g.plen, ring_mm=ring)
...
assert got < base - 0.05
```

`g.pwid` and `g.plen` are **millimetres**. The test feeds the function the one
unit the shipped caller never passes it, so it measures a code path the app does
not execute, and its assertion (`got < base - 0.05`) is comfortably met in mm
while the app moves 0.64 -> 0.63. Same failure shape as F15: the test
re-implements the caller's contract instead of asking the caller.

**Fix.** Convert in the caller, where the dpi is known:

```python
dpi = float(self._layout.get("dpi") or 300) or 300.0
ring_px = ring_mm * dpi / 25.4
```

and pass `ring_px` (rename the parameter `ring` — it is in the caller's units,
whatever those are, which is the honest contract for a scale-free function). The
test must then build a chart, read its recorded rects, and assert the cap the
DIALOG computes, not the one the formula computes.

**Confidence: HIGH.** Three independent confirmations: the dpi dependence, the
exact recovery of the commit's own stated target number (49 %) when the units
are corrected, and the direct area integration of spacer inside the read box.

---

## G-gate — the release gate is GREEN. Nothing found.

```
QT_QPA_PLATFORM=offscreen pytest --runslow -n auto
========== 12583 passed, 167 skipped, 8 xfailed in 210.10s (0:03:30) ===========
EXIT=0
```

No `[gwN] node down`, no `Fatal Python error`, no `Timeout (0:0X:XX)!` thread
dump anywhere in the log. Exit 0 with no worker-down banner, which after the
2026-09-02 `pytest_testnodedown` work means a genuinely clean session. Same
count the `65939d80` commit message claims (12583).

**The gate being green is not evidence against G1-G4** — every one of them is a
defect the suite has no test for, and G4 has a test that passes *because* it
does not ask the shipped caller.

---

## G5 — **REGRESSION: a honeycomb with "Edge spacers" on now prints OUTSIDE the margin the user set** — 0.53 mm at the shipped 1.3 mm default, 2.30 mm at the new clamp's maximum. Clean at the branch point. The F3 test misses it because it only tests edge spacers OFF.

**What I did.** Exactly the case
`tests/test_the_honeycomb_spacer_is_a_ring.py::test_a_huge_spacer_still_prints_
inside_the_margins` builds — CR30 A4 honeycomb, 120 patches, 300 dpi,
`margins=(20,20,20,20)`, spacers coloured — and then crossed it with the ONE
option that test leaves at its default: `edge_spacers`. Worst of the four ink
margins measured off the rendered TIFF. Probe `<scratchpad>/g/g6.py`.

| spacer asked | edge spacers | orientation | worst ink margin | verdict |
|---|---|---|---|---|
| 1.3 mm | off | pointy | 20.659 | OK |
| 4.0 / 40 / 300 mm | off | pointy | 22.0-22.2 | OK (the F3 clamp works) |
| 1.3 mm | off | flat-top | 20.828 | OK |
| **1.3 mm** | **on** | pointy | **19.473** | **0.53 mm inside a 20 mm margin** |
| **4.0 mm** | **on** | pointy | **18.119** | **1.88 mm inside** |
| **40 / 300 mm** | **on** | pointy | **17.949** | **2.05 mm inside** |
| **1.3 mm** | **on** | flat-top | **19.304** | **0.70 mm inside** |
| **4.0 mm** | **on** | flat-top | **17.780** | **2.22 mm inside** |
| **40 / 300 mm** | **on** | flat-top | **17.695** | **2.30 mm inside** |

**It is a regression, not a pre-existing wart.** Same probe at the branch point
`e1aeaf2f` in a `git worktree` (`<scratchpad>/g/g6c.py`): worst margin
**20.066 mm in all four cases**, edge spacers on or off, 1.3 mm or 4.0 mm. The
old spacer was a bar inside the pitch, so an edge spacer went into space the
layout had already reserved.

**And it is honeycomb-only.** Rectangular control (`<scratchpad>/g/g6b.py`),
CR30 / i1 / SS, spacers 1.3 / 4.0 / 40 mm, edge spacers on and off, same 20 mm
margins: **18 of 18 OK**, never below 19.98 mm. So no rectangular chart is
touched.

**Mechanism.** `raster.py:1562` draws an edge patch's outward band with
`hexagon.inset(_pts, -_ring_px / 2.0)` — the GROW path, which is deliberately
NOT clamped (only `d > 0` is). That is correct as geometry: growing a convex
polygon can never invert it. But the ring came out of the PATCH, and
`geometry.compute` reserves nothing for it, so the outermost band is ink the
layout never budgeted. It reaches `ring/2 / sin(60 deg) = 0.577 * ring` past the
top and bottom apexes and `ring/2` past the flat sides — which is exactly the
same 0.577 vs 0.500 discrepancy G1 measures in the margin inspector, seen from
the other end.

**The 0.53 mm at the default does not come only from the ring.** 0.577 x 1.3 =
0.75 mm, and the observed loss is 0.53 mm, because the patch block does not sit
hard against its margin. At the 4.16 mm clamp the loss (1.88 mm) is close to
0.577 x 4.16 = 2.40 mm less the same slack. Either way, the sheet the user gets
does not honour the margin they typed.

**Why the suite is green.** `test_a_huge_spacer_still_prints_inside_the_margins`
calls `build_chart(...)` without `edge_spacers`, whose default is `False`. Its
three cases (1.3 / 40 / 300 mm) are all in the "off" rows above, all OK. The
option that breaks the assertion is one keyword away and is not crossed.

**Why it matters.** The CR30's margins are the jig's clearance — Knut's own
preset text says *"Top margin: 34 mm to avoid knobs underneath to get caught in
page edge"* and *"Left margin: 14 mm so 'glide-rails' do not fall outside of
page"*. Ink placed 0.5-2.3 mm outside the margin the user set is ink the
instrument may not be able to reach, on the one instrument this whole feature is
for.

**Fix.** Reserve the outward band. Either add `ring/2 / sin(apex half-angle)` to
the effective margins in `geometry.compute` when the chart is hexagonal AND
`edge_spacers` is on (the honest fix, costs a fraction of a patch row), or draw
the outer band INWARD like every other side and drop the "double on the outside"
ruling — which is Basti's call, not ours.

**Confidence: HIGH.** Rendered ink, 16 configurations, a clean rectangular
control and a clean branch-point control.

---

## G6 — PROCESS: another agent edited `hexagon.py` and `raster.py` IN THIS CHECKOUT while this review was running. Two uncommitted, unreviewed source changes are in the tree right now.

Discovered at the point G5 was written. `git status` mid-review:

```
 M workflow/layout_engine/hexagon.py
 M workflow/layout_engine/raster.py
```

The change adds an `apex_of` parameter to `hexagon.vertices` and threads
`_apex_ph = px(place.plen)` through `raster._hexagon_points`, so the pointy-top
apex overhang is taken from the SLOT length rather than from the rounded drawn
height `yB - y0`. It changes the ink on every pointy-top honeycomb sheet.

**Consequences for this report.** Every rendered measurement in G1, G2, G3, G5
was taken BEFORE these edits landed and describes `65939d80` + `e0079b2d` as
committed. G7/G8 exercise `hexagon.inset` and `vertices(apex_of=None)`, whose
behaviour the edit does not change. The `--runslow` run (12583 passed) was
against the tree as it stood then. I re-ran G5's measurement against the dirty
tree afterwards (below) and it is unchanged.

**Consequences for the release.** These two files are MODIFIED AND UNCOMMITTED.
Whatever is tagged must not be tagged from this working tree without deciding
what to do with them, and they have had no review of any kind — they arrived
after the round that was supposed to be the last. Nothing in this report
endorses them. `memory: feedback_agents_on_a_branch_share_your_tree` and
`feedback_never_judge_a_tree_from_a_truncated_status` both name this exact
hazard.

---

## G7 — the F3 clamp HOLDS, but the property it claims is not the property that saves it. Latent, not reachable. Report as a note.

**What I did.** Attacked `hexagon.inset` directly (`<scratchpad>/g/g7.py`,
`g8.py`, `g8b.py`): hexagons at aspect ratios 0.01 to 100, `d` at exactly the
inradius, 1.5x, 10x and 1000x it, negative `d` down to -1e6, NaN and +/-inf,
plus non-convex, collinear, zero-length-edge, clockwise and 2-point polygons.
Self-intersection tested by segment-pair crossing; area by the shoelace formula.

**Nothing reachable. All four questions from the brief answer clean:**

* **A polygon never inverts and never grows.** Every `d` above the clamp gives
  the same tiny convex remnant (e.g. a 12 x 10.392 slot: 124.70 mm2 -> 0.0499
  mm2 for d = 9, 60 and 6000). The 678 mm2 / 71,831 mm2 blow-ups F3 measured are
  gone.
* **Zero-length edge** returns the input unchanged (the `if L == 0` early
  return). **Collinear vertices** are handled (parallel-line guard). **Two
  points** returns them.
* **The GROW path (`d < 0`) is deliberately unclamped and that is correct**:
  growing a convex polygon can never make it self-intersect, confirmed down to
  d = -1e6 (area 1.2e2 -> 3.5e12, still convex). Its danger is not geometric, it
  is that the layout does not reserve the space — which is G5.

**The one thing that is not true is the comment.** `inset` says it "never
crosses its own inradius", and clamps to `0.98 * min(distance from the CENTROID
to each edge line)`. That is not the inradius of a non-regular hexagon, and
insetting a stretched hexagon by exactly that amount **does** self-intersect:

| slot | 0.98 x min centroid distance | self-intersects? |
|---|---|---|
| 24.00 x 12.00 | 7.438 | **yes** |
| 100.00 x 1.00 | 0.653 | **yes** |
| 12.00 x 10.392 (the real CR30) | 5.880 | no |

What actually keeps the app safe is the SECOND clamp, in `build()`: the ring is
capped at `0.8 * min(pwid, plen) / 2`, and the inset applied is `ring/2`, i.e.
`0.2 * min(pwid, plen)`. Swept over 8,000 aspect ratios from 0.1 to 400
(`g8b.py`), the smallest ratio between the self-intersection threshold and that
cap is **1.67x**. So there is a real margin, but it comes from the outer clamp,
not from the "floor under it" the inner comment describes. If anyone ever raises
the `build()` cap, or calls `inset` from a new site without it, the floor will
not hold. A correct floor is the largest inscribed circle, or simply a smaller
constant.

**NaN and infinity pass straight through** (`d > 0` is False for NaN, so the
clamp is skipped and every vertex comes back NaN; `+inf` returns finite
garbage). Not reachable from the UI — the Spacer size spin box cannot produce
either — but `json.loads` does accept a bare `NaN` literal, so a hand-edited
`channels.json` could. Latent only.
