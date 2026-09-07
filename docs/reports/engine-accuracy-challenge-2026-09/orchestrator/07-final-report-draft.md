# Maximum-accuracy engine challenge — final report (draft, numbers final; reviewer section pending)

## The three questions

**Q1 — do the accurate-mode options work as intended?** Most did; several
promises did not hold, and two colour-science faults were in BOTH engine modes:
paper white was never pinned (ink in every paper-white area under relative and
perceptual rendering) and L*=0 printed a blue-cast dark grey. In accurate mode the
"hue-preserving" clip printed the opposite hue for 5.7 % of out-of-gamut colours,
`-L` capped total ink instead of black, two observers offered in the tab crashed
the build, and the "smoothing chosen by cross-validation" line reported noise as a
decision. All of that is fixed and measured (table in
`docs/dev_profile_engine_accuracy_challenge.md`). What is NOT fixed, because the
referee said no: the smoothing selection itself — three alternatives each helped
one synthetic printer and cost another by 8–21 %.

**Q2 — more options for better profiles?** Built: a black ink limit (`-L` and
`BLACK_INK_LIMIT`), the CIE 2015 observers, opt-in duplicate-patch averaging
(off by default — it lost on the battery). Recorded as real practice but not
built: `.sp` custom illuminants, `-g` image gamuts and `-p` abstract profiles
for CMY+N, the `-s`/`-S` percentage forms, per-channel dot limits, light-ink
(CMYKcm) separation (A-20 — a real bug for light-ink printers, needs its own
design and a battery printer).

**Q3 — is the engine used by the scanner/camera tool?** It was not: the tool
always ran colprof, whatever Preferences said, and showed no trace. Now its
printer-profile build asks the same chooser the tab uses, keeps the nan/inf
sanitiser and the archive in front, the preview names the builder and mode, and
the engine prints colprof's "Profile check complete" line so the tool's
misalignment verdict still works. The engine-only rows are not offered there
(they live in the tab's Manual group); the tool's own closing line already sends
users to the tab for fine-tuning.

## Honest verdict on the mode (Agent A, unchanged by the fixes)
Tighter at the chart patches (0.05 vs colprof 0.34 ΔE00), a tie or a loss on
unseen patches, round-trip and neutral-ramp smoothness not better than Fast.
The mode now clips by hue better than colprof (0.000 vs 0.014 flips) and its
log tells the truth; it is not yet a proven accuracy gain at the print.

## Referee (synthetic battery, shipped → final, A2B median ΔE00)
S1 0.089→0.088 · S2 0.223→0.221 · S3 0.242→0.239 · S4 0.449→0.431 · S5
0.653→0.651 · S6 0.447→0.446. B2A: S5 1.874→1.337 (−29 %), S4 0.485→0.528
(+8.8 % — the one regression; not the white correction, the clip or the black
pin per bisect; the CV λ interacts with S4's noise). Gate: "DO NOT PROMOTE" on
that single metric — recorded, not hidden.

## Tests
Engine set: 211 passed (round 9). UI fixes: 6/6. i18n: 87/87 (17 keys × 12
languages, 5 stale removed). Everyday tier: see below. `--runslow`: pending.

## Not done / needs Basti
* A-20 light inks; B-19 second run from a measurement-only project; B-32 the
  engine log is English in every language; B-16 per-target store vs Save-as-
  Defaults after a restart; the ETA cannot see inside colprof.
* The branch carries the peer session's master merge base (rebased onto
  1b9cad54) — merge to master when the reviewer's findings are addressed and
  `--runslow` is green.
