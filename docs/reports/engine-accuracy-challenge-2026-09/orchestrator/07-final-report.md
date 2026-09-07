# Maximum-accuracy engine challenge — final report (2026-09-05)

Branch `feature/engine-accuracy-challenge` (rebased onto master 1b9cad54),
commits 25120feb … 5cc35aa9. Proof folder: this directory. Developer page in
the repo: `docs/dev_profile_engine_accuracy_challenge.md`.

## Team
Critic (plan attack, 21 new suspects, 2 refuted premises) → Agent A (colour
science, 21 findings, every number with its command) + Agent B (33 findings on
the real app on screen, 22 pictures) in parallel → orchestrator fixes →
Reviewer (18 attack items, 4 tests proven unable to fail, 6 real bugs inside
the fixes) → second fix round.

## Answers

**Q1 — do the accurate-mode options work as intended?** Two colour-science
faults were in BOTH engine modes and are the headline: paper white was never
pinned (ink in every paper-white area under relative and perceptual
rendering) and L*=0 printed a blue-cast grey. In accurate mode the
"hue-preserving" clip printed the OPPOSITE hue for 5.7 % of out-of-gamut
colours, `-L` capped total ink instead of black, two observers offered by
the tab crashed the build, `-s` and `-nP -nS` were mistranslated, the gamut
tag flagged printable colours, nan rows crashed with a numpy error, a
stuck-instrument chart built "successfully", and the log reported noise as
decisions. All fixed and measured; the cross-validated smoothing SELECTION is
deliberately unchanged because three alternatives each helped one synthetic
printer and cost another by 8–21 % (the referee rules).

**Q2 — more options?** Built: black ink limit (`-L`/`BLACK_INK_LIMIT`), CIE
2015 observers, opt-in duplicate averaging (off by default — lost on the
battery). Recorded, not built: `.sp` illuminants, `-g`/`-p` for CMY+N,
`-s`/`-S` percentage forms, per-channel dot limits, light-ink (CMYKcm)
separation (A-20: a real bug for light-ink printers, needs its own design).

**Q3 — the scanner/camera tool?** It ignored Preferences and always ran
colprof. Its printer-profile build now uses the same chooser as the tab
(sanitiser and archive kept in front), the preview names builder and mode,
the engine emits colprof's fit-check line (peak over the fitted patches) so
the tool's misalignment verdict works, and the quit guard sees that builder.

## Verdict on the mode (Agent A, unchanged by the fixes)
Tighter at the chart patches than colprof, a tie or a loss on unseen patches,
round-trip and neutral smoothness not better than Fast. It now clips by hue
better than colprof and its log is honest; it is not yet a proven accuracy
gain at the print. Every measurement on Basti's drive was treated as
developer test data; the synthetic battery and colprof parity were the
referees.

## Referee — synthetic battery, shipped → final (A2B median ΔE00)
S1 0.089→0.088 · S2 0.223→0.221 · S3 0.242→0.239 · S4 0.449→0.431 ·
S5 0.653→0.651 · S6 0.447→0.446. B2A: S5 1.874→1.337 (−29 %); S4
0.485→0.528 (+8.8 %, the one regression — not the white correction, the clip,
the black pin or the L-axis by bisect; interacts with the CV λ on the noisy
printer). Gate verdict "DO NOT PROMOTE" on that one metric — recorded, not
hidden. Real chart (924 p, treated as smoke only): A2B(white) 100.000, B2A
(L*=100) 0.99999 (colprof 0.99996), hue flips 0.000 (colprof 0.014).

## Tests
Engine set 161+ passed (round 11 after the reviewer fixes), UI 7/7, i18n
87/87 (19 keys × 12 languages, 5 stale removed), everyday tier 10527 passed
(one encoding guard fixed). `--runslow`: see the appended line.

## Left open, needs Basti
A-20 light inks · B-19 second run from a measurement-only project · B-32 the
engine log is English in every language · B-16 per-target store vs Save-as-
Defaults after a restart · R2 littleCMS reads the engine's white one 8-bit
step darker than colprof's (xicclu identical) · the remaining-time estimate
cannot see inside colprof (it now counts down or says "taking longer").
Merge to master when you are satisfied; the peer session's master work is
already the branch's base.
--runslow gate (HEAD 04e722d6): 10674 passed, 143 skipped, 3 xfailed in 323.46s (0:05:23)

## Independent challenger (reports/challenger/), 2026-09-05 — verdicts on the claims
C1 beta OFF unchanged: colprof args byte-identical on master and branch; six
behaviour changes for a beta-off user, all UI-side: archive-before-every-
rebuild (which also moves `calibrated.icc` into `old/` — applycal must be
re-run after a rebuild), the `-k` rows now reset on a run switch (a fix that
changes colprof's args for CMYK users who had the leak), preconditioning
text, scanner preview, quit guard, hidden heading. Colour results: identical.
C2 battery: confirmed (S4 B2A +8.4 % at 20k; the last three changes moved
nothing else). C3 white/black exact through xicclu in all 8 builds × 3 intents;
littleCMS at 8 bits shows 1–2/255 at white — colprof's own profiles show the
same there. NEW: Maximum accuracy's CMYK black is 1.5 L* LIGHTER than Fast's
(14.9 vs 13.4 on the TAC) — contrary to the Preferences text "shadows keep
their depth"; open. C4 no hue flip (max 7.6°; a printer with a hue gap: 20°,
no family crossing, but chroma collapses). C5 the countdown was monotone and
useless (drained during colprof) — fixed after the challenge: colprof's time
is taken out of the budget, the end says "almost done". C6 scanner tool
confirmed. C7 on synthetics Maximum accuracy beats Fast on every median cell
and beats colprof on S1/S3/S4, but LOSES to colprof on S2's A2B (0.220 vs
0.136, p95 2.9×) — the matte/dot-gain printer wants more smoothing than the
CV picks. Not uniformly the best engine yet.

## Three next steps toward "best in every area" (not started)
1. A smoothing criterion that sees the print (B2A round trip + neutral
   smoothness), judged on the battery — the S2 loss and the S4 B2A regression
   are both λ-choice symptoms.
2. The CMYK black depth in accurate mode (Euclidean TAC projection vs
   proportional scaling) — 1.5 L* to recover.
3. Light inks (A-20) — a CMYKcm battery printer first.
--runslow gate (HEAD ec1bf103): 10674 passed, 143 skipped, 3 xfailed in 314.76s (0:05:14)
