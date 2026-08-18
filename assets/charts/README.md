# Bundled reference charts

These patch sets ship inside the app (everything under `assets/` is bundled by
`('assets','assets')` in `ChromIQ.spec`) and back the **built-in Create Chart
presets**. They are the *only* charts committed to the repo — every other
`.tif`/`.ti1`/`.ti2` is a workflow output and is gitignored. The `.gitignore`
re-includes these with `!assets/charts/**/*.tif{,f}`.

## Layout

Charts are filed by a fixed taxonomy, one folder level each:

```
assets/charts/<creator>/<colorspace>/<instrument>/<paper>/<target>/<files>
```

- **creator** — who made the patch set (e.g. `pharmacist`)
- **colorspace** — device colorspace of the patches (`rgb`, `cmyk`, …)
- **instrument** — measuring instrument the layout targets (`i1pro`, …)
- **paper** — page size the TIFFs are laid out for (`a4`, `letter`, …)
- **target** — the chart itself (`tc918`, `tc924`, …); files inside use this stem

The path carries the descriptive metadata, so file stems stay short (`tc924.ti1`,
not `tc924_a4.ti1`). Resolve a file at runtime with
`core.resource_path.resource_path("assets/charts/<creator>/<colorspace>/<instrument>/<paper>/<target>/<file>")`.

| Path | Preset (Create Chart → Manual) | Kind | Files |
|------|--------------------------------|------|-------|
| `pharmacist/rgb/i1pro/a4/tc924/` | ★ i1Pro TC9.24 (A4) by Pharmacist | prebuilt-files | `tc924.ti1` `tc924.ti2` `tc924_01.tif` `tc924_02.tif` |
| `pharmacist/rgb/i1pro/a4/abw1110/` | ★ i1Pro 1110 ABW-optimized (A4) by Pharmacist | prebuilt-files | `abw1110.ti1` `abw1110.ti2` `abw1110_01.tif` `abw1110_02.tif` |
| `pharmacist/rgb/i1pro/a4/tc918eg/` | ★ i1Pro TC9.18 extended greys 1160 (A4) by Pharmacist | prebuilt-files | `tc918eg.ti1` `tc918eg.ti2` `tc918eg_01.tif` `tc918eg_02.tif` |
| `pharmacist/rgb/i1pro/letter/tc918eg/` | ★ i1Pro TC9.18 extended greys 1160 (Letter) by Pharmacist | prebuilt-files | `tc918eg.ti1` `tc918eg.ti2` `tc918eg_01.tif` `tc918eg_02.tif` |
| `pharmacist/rgb/colormunki/a4/tc300/` | ★ ColorMunki TC3.00 (A4) by Pharmacist | prebuilt-files | `tc300.ti1` `tc300.ti2` `tc300_01.tif` |
| `pharmacist/rgb/colormunki/a4/abw702/` | ★ ColorMunki 702 ABW-optimized (A4) by Pharmacist | prebuilt-files | `abw702.ti1` `abw702.ti2` `abw702_01.tif` `abw702_02.tif` |
| `pharmacist/rgb/colormunki/a3/tc924/` | ★ ColorMunki TC9.24 (A3) by Pharmacist | prebuilt-files | `tc924.ti1` `tc924.ti2` `tc924_01.tif` |
| `pharmacist/rgb/colormunki/a3plus/tc918eg/` | ★ ColorMunki TC9.18 extended greys 1160 (A3+) by Pharmacist | prebuilt-files | `tc918eg.ti1` `tc918eg.ti2` `tc918eg_01.tif` |

Knut's charts don't ship rendered pages — the app builds them on selection — so
they are filed by **family** rather than by paper, one folder per chart holding
just the patch set and the design it came from:

| Path | Preset (Create Chart → Manual) | Kind | Files |
|------|--------------------------------|------|-------|
| `knut/rgb/colormunki/<slug>/` | ★ ColorMunki · the 45-chart ColorMunki line-up | ti1 → layout engine | `chart.ti1` `recipe.json` |
| `knut/rgb/fulllayout/fls_i1pro_*/` | ★ i1Pro · … · Full layout setup | ti1 → printtarg / engine | `chart.ti1` `recipe.json` |
| `knut/rgb/scanner/<paper>/` | ★ Scanner · flatbed printer-profiling charts | ti1 → layout engine | `chart.ti1` `recipe.json` |
| `redriver/rgb/standard_patch_set_v25/` | ★ Red River Paper · Standard Patch Set v25 | ti1 → layout engine | `chart.ti1` `recipe.json` `clip_logo.png` |

## How each kind is used

- **prebuilt-files** (`…/tc924/`) — a complete, pre-generated target (`.ti1` +
  `.ti2` + page TIFFs). Selecting the preset prompts for a name and **copies all
  the files verbatim** into a fresh `~/ChromIQ/<name>/` (renamed to the chosen
  target name); no targen and no printtarg are run. The `_NN.tif` pages are
  located by globbing `<stem>_*.tif` next to the `.ti1`.

- **ti1 → printtarg / layout engine** (`knut/…`, `redriver/…`) — only the patch
  set is bundled; the pages are laid out when the preset is picked, from a
  layout recipe held in `ui/tabs/tab_chart.py`. targen is greyed (the colours are
  fixed) but every layout control stays editable, so the same patches can be
  re-flowed onto different paper. The `recipe.json` beside each `chart.ti1` is
  the *colour-set* design, which "Load setup from preset" in the New-chart
  window starts from — not the page layout.

Either way the resulting `~/ChromIQ/<name>/` folder is self-contained: it holds
a `<name>.ti1` plus the generated/copied `<name>.ti2` and `<name>_NN.tif` pages.

## Adding another set

Drop the files in the matching `assets/charts/<creator>/<colorspace>/<instrument>/<paper>/<target>/`
leaf (create the levels that don't exist yet; keep the `<target>` stem on the
files) and wire the preset in `ui/tabs/tab_chart.py` — see
`docs/dev_builtin_presets.md` for the full recipe. Source charts in this batch
came from Pharmacist.

Another chart for one of Knut's shared-recipe families is a one-liner: drop his
exported `<name>.ti1` + `<name>.json` pair in a folder and run
`python scripts/import_knut_presets.py <family> <folder> --write`, naming the
family first — `cm` for the ColorMunki charts
(`knut/rgb/colormunki/`, 45 of them), `p3` for the i1Pro 3 Plus charts
(`knut/rgb/i1pro3/`, 24). It validates the export against that family's shared
recipe, stages the assets, and prints the registry row to paste.

An export that differs from the shared recipe outside the fields its family lets
a single chart own is **rejected**, not quietly folded in — paper, grid, left
margin and clip text for the ColorMunki family; paper and grid alone for the
i1Pro 3 Plus one, which shares its margins and shows the automatic notes box in
the clip border. A third family is a `FAMILIES` entry in that script.
