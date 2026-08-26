# Margin inspector & thresholds

Measures the realised page margins of a generated chart preview and warns when
they fall below the minimum a measuring ruler / jig needs. Requested by Knut to
address profiles that read badly because the chart sat too close to a sheet edge
for the i1Pro jig.

## Why measure, not set

printtarg exposes **one uniform `-m`/`-M` margin** (`ma[0..3] = marg`), plus a
fixed **26 mm i1Pro left clip border** (suppressed by `-L`). The realised
per-side margins are therefore an *output* of the whole layout — patch scale
(`-a`), spacer size, `-m`/`-M`, `-L`, strip-length limit (`-P`), paper and
orientation all move them. So the inspector **measures the rendered page**; the
user can't dial a left/right margin directly.

`-M` (what ChromIQ ships) keeps the margin inside the TIFF, so the TIFF spans the
full sheet and margins read straight against the paper edge. Plain `-m` crops the
margin out; `measure_margins` adds the trimmed `(paper − tiff)/2` back when the
true paper size is supplied.

## The "patch area"

The edge measured to is **where bare paper meets the first patch or spacer** —
spacers (between/at strip ends) count as patch area; strip labels (A B C…), the
rotated right-margin title and page labels are text and are **excluded**.

`workflow/margin_inspector.py` reuses `ti2_relayout._patch_grid_bbox` for the
horizontal extent (it already drops the title) and derives the vertical extent
from a row-fill scan inside that x-band (the grid's own y-range is title-
contaminated — the editor only ever uses its x-range). No B&W twin is needed.

## Orientation (the subtle bit)

Margins are reported in **printtarg / TIFF orientation** (what the preview
shows). The jig is rotated 90°: a sheet placed landscape in the jig is laid out
portrait by printtarg. The scanner runs **along the strips**, so the white
run-up is needed on the scan-direction edges:

| printtarg orientation | scan-direction (run-up) edges | cross-scan edges |
|-----------------------|-------------------------------|------------------|
| Portrait              | Top, Bottom                   | Left, Right      |
| Landscape             | Left, Right                   | Top, Bottom      |

Seed thresholds put the run-up only on the scan-direction edges; cross-scan
sides stay unset (0 = unchecked) so a shipped chart's small cross-scan margin
(e.g. the i1Pro A4 portrait preset's 8 mm left/right) can't false-alarm.

## Data model

- `core/settings.py`: `margin_thresholds` is one JSON blob,
  `{"<instrument>|<paper> <Orientation>": {"L","R","T","B","desc"}}`.
  `default_margin_thresholds()` is the seed table; `margin_combo_key()` builds
  the key; `parse/serialize_margin_thresholds()` round-trip the blob.
- Thresholds are **minimums to meet-or-exceed**; no upper bound. A missing combo
  → no check (inspector still shows the measured numbers).
- Two behaviour flags: `margin_inspector_show` (frame visibility),
  `margin_violation_notify` (warning; greyed out while the frame is hidden),
  plus `margin_guides_show` (the preview guide-line toggle, stored from the
  in-tab checkbox).

## UI

- **Settings → Margin Thresholds tab** (`settings_dialog.py`): instrument +
  paper(+orientation) pulldowns select a combo; a Description field and an
  L/R/T/B mm table edit that combo. Edits commit to an in-memory table, saved as
  the blob on OK.
- **Create Chart** (`ui/margin_inspector_panel.py`): the "Measured from Preview"
  frame under the preview shows L/R/T/B + reading-direction patch size (mm &
  inch), a large green `Margins: OK` / red violation status, and the dotted
  guide-line checkbox. `tab_chart._update_margin_inspector` measures every page,
  derives the combo key and surfaces the worst (most-violated) page.
- **Preview guides** (`tiff_preview.set_margin_guides`): dotted lines at each
  threshold position — white-halo black dash normally, red on the violated edge.
  Drawn on the display only, never into the TIFF.

## Seeds

`scripts/derive_margin_seeds.py` renders the shipped ColorMunki presets and
measures them; the seed values are rounded just below the smallest known-good
margin so those (practically-tested) presets read OK out of the box. i1Pro
seeds use Knut's 11 mm scan run-up. These are *editable starting points*, not
physical minima — rulers vary.

## Known gap — a Guided chart continued in Manual is barely checked

**Status: known, deliberately not fixed (Basti, 2026-08-26) — issue #171.
Do not "fix" it without asking; it was decided, not overlooked.**

Build a chart in Guided, click MANUAL, press Generate. The sheet is unchanged —
the same measured margins to the tenth of a millimetre — but the verdict flips:

```
GUIDED  measured  L 26.0  R 10.2  T 27.2  B 10.2
        minimum   L 26.0  R  9.0  T 38.0  B  9.0
        status    RED   "Top margin 27.2 mm is below the 38 mm minimum"

MANUAL  measured  L 26.0  R 10.2  T 27.2  B 10.2     <- the same sheet
        minimum   L  6.0  R  6.0  T  6.0  B  6.0
        status    GREEN "Margins: OK"
```

Three things combine, and each is worth knowing on its own:

1. **The seeded "own margins" are dataclass defaults.** Guided writes no recipe,
   so `LayoutRecipe` fills margin_top/right/bottom/left with 6/6/6/6. That is
   neither the border the engine was handed (10 mm for the i1Pro, whose shipping
   preset is `m10_a0.95`) nor the margins the sheet ended up with. So the Manual
   check is not merely lenient — almost no real sheet can fail a 6 mm floor.
2. **A Manual Generate erases the provenance.** `margins_chosen_by_user` is
   written only in `ChartCreator._embed_layout_geometry`'s `params.layout_recipe
   is None` branch. A Manual build supplies a recipe, takes the other branch, and
   the run loses the stamp for good. Returning to Guided does not restore it;
   only re-generating in Guided does.
3. **Charts made before the stamp existed have none.** Counted on the author's
   machine, 2026-08-26: 65 chart sidecars under `~/ChromIQ`, 60 carrying an
   engine recipe, **0 stamped**. This is not a long tail — it is every chart
   already made.

**There is no second net.** The check lives only in the Create Chart inspector;
nothing re-checks at print or measure time. So a chart the instrument cannot
read can show a green "Margins: OK", be printed, and only fail at the jig.

**The option that would remove all three** (considered, not taken): show both
the chart's own minimum and the instrument's in the panel's `min` column and
colour against whichever is stricter, naming which one failed. It changes no
printed sheet, needs no provenance stamp — so it works on all 65 existing charts
— and it never hides a Manual user's deliberate choice to go below the guideline.
The two rejected alternatives both have real costs: tracking "has the user
touched a margin control" is a UI-state heuristic that dies when a fourth seeder
is added, and forcing `use_instrument_margins` on changes the geometry of charts
that get printed.
