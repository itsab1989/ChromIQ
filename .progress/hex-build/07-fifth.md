# Fifth adversarial review — #159 hexagon work

Reviewer: fifth round. Started 2026-09-09.
Target: commit `8c4c9b20` ("#159: the fourth review's five findings, including the sixth
self-validating test"), the fixes for the fourth round's H1-H5.
Bar: *would I sign this off to print on a paying customer's paper.*

Findings are numbered J1, J2, ... and appended as they are measured.
Everything below is written to disk as it happens; nothing is held in memory.

---

## J0 — setup and orientation (not a finding)

Tree state at start: `git status --porcelain` empty, HEAD =
`8c4c9b20b0617a78c290f714ca9d1b2e2315c97a`, branch `feature/nelson-photocard-presets`.
Verified with `git branch --show-current` and `git rev-parse HEAD`.

Read first: `06-fourth.md` (H1-H5), the full diff of `8c4c9b20`, the current
`workflow/layout_engine/geometry.py::patch_rects_px`, and the same function at
`964f0fd9` (the pre-lattice commit the H2 fix restores parity with).

Static observation, to be measured, not yet a finding: the H2 `else` branch is a
verbatim copy of the pre-lattice four lines (`_x0,_y0 = px(x_of(p)), px(y_of(j))
+ _stag; _x1 = px(x_of(p)+pwid); _y1 = px(y_of(j)+plen)+_stag`), so byte
identity for every non-hexagonal chart is *expected*. Measured below (J2).

## J1 — H2's fix VERIFIED, and far wider than the commit claimed. NOTHING FOUND

The commit says *"56 rectangular configurations are byte-identical to the
pre-lattice tree again"*. I did not take that number; I re-derived it.

Probe: `scratchpad/j2_rects.py`, run once against `/Users/Basti/develop/ChromIQ`
(HEAD `8c4c9b20`) and once against the existing worktree
`scratchpad/pre-lattice` (`964f0fd9`, the commit before the lattice). It calls
`geometry.patch_rects_px` directly — the function under review — and hashes
**all four fields** of every slot (`x,y,w,h`), not `y` alone (H3's blind spot).

Matrix: 8 instruments (i1, p3, CM, 41, 51, DTP20, SS, CR30) x spacers off/on x
ColorMunki row stagger off/on x `hflag` off/on x three chart sizes
(60 / 400 / 5000 patches, so **1 page and many pages**) x 13 papers (A4, A3,
Letter, all three landscape, Legal, Tabloid, 5x7, 4x6, 8x10, A5, 13x19) x 11
resolutions (72, 96, 150, 200, 240, 300, 360, 400, 600, 720, 1200).

```
configs 13728   slots 25,067,790   errors 0
differing configs: 1580   {SS: 786, CR30: 794}
classified by instruments.is_hexagonal(geom) — the branch condition itself:
  HEX configs total:      1716      differing & hex:   1580
  RECT configs total:    12012      differing & RECT:     0
```

**12,012 rectangular configurations and 0 disagreements, over 25 million slots.**
That includes the DTP41 Letter/Legal/Tabloid cases H2 named, multi-page charts
(5000 patches spills to 8+ pages), and the ColorMunki row stagger in both
states. The DTP41/Letter/300 dpi case H2 measured as 72 boxes wrong is now
hash-identical.

WHY IT MATTERS: this was H2's blocker and the commit's headline claim. It holds,
and it holds over 200x more ground than was claimed. Confidence: high.
Method note: the `else` branch is a verbatim copy of the pre-lattice four lines,
so identity is expected — the value of the measurement is that it proves no
*other* edit in the commit leaked into the rectangular path.

