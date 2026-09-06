# Bundled scanner/camera target recognition files

These `.cht` files describe **where the patches sit** on standard scanner/camera
calibration targets (IT8, ColorChecker-style, etc.). ChromIQ uses them in
**Tools ▸ Build profile with scanner or camera** so it can lay its reading grid over
a scan or photo of a target you own. They contain **geometry only — no colours**;
the true patch colours come from the reference file that ships with your own
physical target (batch-specific, so it can't be bundled).

## The patch-area-corner convention

The real printed targets **have no fiducial marks** — just the patch grid, and
sometimes a single dot (rectarg *adds* fiducials when it renders a preview, which
is why some third-party `.cht` fiducials don't match the real sheet). So every
file here sets its **`F` line to the patch-area bounding box** (top-left,
top-right, bottom-right, bottom-left of the whole patch grid). You place ChromIQ's
reading grid on the **visible corners of the patch block** — no invisible
fiducials to hunt for — and it works the same at any scan resolution.

## Why these are bundled

ArgyllCMS ships `.cht` files for these targets in its `ref/` folder, but several
had fiducial coordinates that don't match the printed sheet, and a few
third-party "corrected" copies broke the box grid outright (box pitch too small,
so patches cluster or overlap). Each file here was **rebuilt to the patch-area-
corner convention above and validated end-to-end** through the real ArgyllCMS
`scanin -F`, at 100 / 200 / 300 / 600 dpi (worst per-patch registration error
0.0 — see `tests/test_scanner_multidpi.py`). ChromIQ prefers these over the
copies in Argyll's `ref/` when the names match.

Bundled:

- **HutchColor HCT** — `Hutchcolor.cht`
- **LaserSoft ISO 12641-2** — `ISO12641_2_1.cht`
- **LaserSoft DCPro** — `LaserSoftDCPro.cht`
- **QPcard 202** — `QPcard_202.cht`
- **SpyderChecker** — `SpyderChecker.cht`
- **SpyderChecker 24** — `SpyderChecker24.cht`
- **CMP Digital Target-4** — `CMP_Digital_Target-4.cht`
- **Wolf Faust IT8** — `it8Wolf.cht`

QPcard 202, SpyderChecker, SpyderChecker 24 and CMP Digital Target-4 had earlier
"corrected" copies that misregistered with `scanin` (box pitch not matching the
patch positions, an undersized fiducial, or an inconsistent `EXPECTED` list).
Rebuilding them onto the patch-area-corner convention — with the correct box
geometry — fixes all four.

`it8Wolf.cht` shipped here from the first commit of this folder but went
unlisted until 2026-09-06, which is how a licensing sweep came to describe the
folder as holding seven files when it holds eight.
`tests/test_the_scanner_targets_say_where_they_came_from.py` now fails if a
`.cht` in this folder is not named above.

## Provenance — measured, not assumed

**These are not original files. Every one of the eight carries ArgyllCMS's own
patch geometry**, and that was measured rather than inferred. It is written down
here so the next licensing sweep re-reads this section instead of re-deriving it.

**Method.** A `.cht` is structured text, and the two sides are not written in the
same shape: Argyll states a whole grid in one compact line
(`Y 01 29 A V 24.689655 24.545454 99.5 25.5 24.689655 24.545454`) where these
files state one line per patch. A text diff of those compares nothing, and a
"percent similar" number taken from one means nothing. So both sides were
**expanded to per-patch boxes first**, using a Python transcription of Argyll's
own reader — `scanin/scanrd.c`, `read_elist()` and `strinc()`, ArgyllCMS 3.5.0 —
and compared patch by patch, in the file's own units, against
`/Applications/Argyll/ref/`. The parse was checked before the comparison was
believed: expanded box count against declared `BOXES`, `XLIST`/`YLIST` row counts
against their declared N, `EXPECTED` count against its declared N, on both sides
of all eight pairs. Patch names were compared with zero-padding normalised
(`A01` and `A1` are the same patch).

**Result.** All eight have a same-named counterpart in Argyll's `ref/`.

| file | patches | patch size = Argyll's | `BOX_SHRINK` = Argyll's | geometry vs Argyll |
|---|---|---|---|---|
| `ISO12641_2_1.cht` | 864 | yes, 100 × 100 | yes, 12 | **864/864 patches at identical absolute coordinates, max \|Δ\| = 0** |
| `it8Wolf.cht` | 288 | yes, 25.625 wide; 25.625/51.25 tall | yes, 3.5 | **288/288 identical, max \|Δ\| = 0**, and the same asymmetric `F` line `1 1 616 1.5 615.5 358 1 358.5` |
| `Hutchcolor.cht` | 528 | yes, 24.6897 × 24.5455 | yes, 3 | **528/528 identical to 4 dp** (max \|Δ\| 0.00053 — this file rounds where Argyll accumulates), same origin 99.5, 25.5 |
| `CMP_Digital_Target-4.cht` | 570 | yes, 100 × 100 | yes, 12 | pure translation +50 / −50, residual 0 |
| `LaserSoftDCPro.cht` | 140 | yes, 12.675 × 12.75 | yes, 1.6 | uniform rescale ×0.835255 / ×0.836066, residual 0 |
| `QPcard_202.cht` | 35 | yes, 68 × 68 | yes, 4 | uniform rescale ×0.819277, residual 0 |
| `SpyderChecker24.cht` | 24 | yes, 88.5 × 88.5 | yes, 8 | uniform rescale ×0.867647, residual 0 |
| `SpyderChecker.cht` | 48 | yes, 42 × 42 | yes, 3 | positions genuinely re-laid out — x-pitches {42, 137} against Argyll's {49, 116} |

**What in that is evidence and what is not.** A shared patch count or box name is
not evidence of anything: every `.cht` for a given chart must agree about the
chart. Nor is the exact affine fit on the four uniform grids — any evenly spaced
n × m grid maps onto any other with zero residual, so *that number proves
nothing on its own* and is listed only for completeness. What does carry weight
is the arbitrary detail that survived the rescaling:

* **`BOX_SHRINK` is identical in 8 of 8** — 12, 3, 12, 1.6, 4, 3, 8, 3.5. It is a
  free tuning constant in the file's own units. Eight independent matches,
  including 1.6 and 3.5, is not coincidence.
* **The patch size is identical in 8 of 8**, including 24.6897 × 24.5455,
  12.675 × 12.75 and the two-valued 25.625 / 51.25. In four files the patch
  *positions* were rescaled while the *size* was left at Argyll's number — which
  is what editing a copy produces, and not what re-deriving a chart produces.
* **Three files match Argyll's absolute coordinates outright** (`ISO12641_2_1`,
  `it8Wolf`, `Hutchcolor`), with no transform at all, over 864, 288 and 528
  patches. `it8Wolf` also reproduces Argyll's asymmetric fiducial line digit for
  digit.

This agrees with the repository's own history: `1f9c534a` bundles "Knut Georg
Larsson's corrected versions (from the rectarg project) … plus ISO 12641-2
**unchanged**", and `caf6b103` regenerated all eight through
`workflow/scanner_labels.py`, itself "a port of rectarg's … label logic". The
work that went into these files is real — new fiducials, new labels, corrected
box geometry, and the `XLIST`/`YLIST` strength normalisation in `d3d1bd43` — but
it is work done **on** Argyll's geometry, not instead of it.

**Not established:** whether rectarg took the geometry from Argyll's `ref/` or
both took it from a common third source. It does not change the conclusion for
these files — what ships here matches Argyll's numbers — but the direction of
the borrowing upstream of rectarg has not been checked.

## Credit & licence

- Corrected `.cht` files: **Knut Georg Larsson** — rectarg
  (<https://github.com/soul-traveller/rectarg>).
- Derived from the recognition files distributed with **ArgyllCMS** by
  Graeme W. Gill (<https://www.argyllcms.com>).

These files are distributed under the **GNU Affero General Public License v3**
— see the `LICENSE` file in this folder, which is the same AGPLv3 text
ArgyllCMS ships as `ref/License.txt`.

**Why the AGPL and not the GPL.** The Provenance section above measured what
these files actually carry: ArgyllCMS's patch geometry, in all eight. Argyll's
`ref/ReadMe.txt` names all eight as covered by `ref/License.txt`, and that file
is the AGPLv3. A work derived from an AGPLv3 work cannot be redistributed under
the plain GPLv3 — that would drop the §13 network clause the AGPL exists for —
so the folder stated a licence it was not entitled to state. It said GPLv3 from
its first commit; that was corrected on 2026-09-06, on Basti's decision, once
the derivation was measured rather than assumed.

**This does not change ChromIQ's own licence.** ChromIQ remains **GPLv3** (see
the `LICENSE` at the top of the repository). These are data files, read at run
time and never linked into the program, and only this folder is AGPLv3. Nothing
about the application's behaviour changes either: no code reads this file, and
not one coordinate in any `.cht` was touched by the relicensing.
