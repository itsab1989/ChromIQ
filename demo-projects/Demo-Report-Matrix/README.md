# Demo-Report-Matrix — the Measurement Report test package

Built by `scripts/make_report_demo.py` (every file made by real ArgyllCMS:
targen → printtarg → fakeread → colprof; the gamut chart via xicclu).
Argyll's sRGB.icm plays the printer; the run's own profile was built from a
real fakeread measurement of a real 210-patch chart.

`scripts/drive_report_demo_onscreen.py` opens the real Measurement Report on
every case, checks the expectations below, and exports one PDF per case into
`pdfs/` beside this file.

## run1 — twelve dated verification cases

| Case | Date | What it is | The report must show |
|---|---|---|---|
| V1 | 2026-05-01 | raw sheet, little noise | "printed raw — no profile"; judged as measured — no white adjustment; split blocks present (run profile referees); Result column says "drift", detail says this check **becomes the baseline** |
| V2 | 2026-06-01 | raw sheet, more noise | same as V1, worse figures → visible drift V1→V2 in the trend; detail shows **"Drift since the previous raw check"** with avg/max ΔE00 vs V1 — no Pass/Fail |
| V3 | 2026-06-15 | through profile, relative intent | "through this run's profile · relative colorimetric"; judged relative to paper white (media-relative); split present |
| V4 | 2026-07-01 | through profile, absolute intent | as-measured (absolute) yardstick, split present |
| V5 | 2026-07-10 | another app with colour management | "printed in another app with colour management"; "(your answer when the sheet was measured)"; media-relative |
| V6 | 2026-07-20 | no print record | "printing method not recorded"; judged as measured |
| V7 | 2026-08-01 | gamut chart #1 | reference = the profile's own colorimetric targets; NO split (all colours printable by design); corners excluded from stats; produced-block says it measured **the profile's accuracy against its own promise** (never "drift check"); run row says "gamut check — profile applied at build" |
| V8 | 2026-08-08 | gamut chart #2, noisier | same, worse figures → drift V7→V8 |
| V9 | 2026-08-09 | gamut chart, reference REMOVED | "No colour-accuracy figures, on purpose." — refusal, never a guessed number |
| V10 | 2026-08-10 09:00 | imported from another program | CHROMIQ keywords present; treated as external-CM (answered at measure) |
| V11 | 2026-08-10 10:00 | measured with an i1Pro3 | red "mixed instruments" warning names this date |
| V12 | 2026-08-10 11:00 | profile rebuilt after printing | "the profile has been rebuilt since this sheet was printed" warning; V10–V12 share one day, so their table columns and trend labels carry the **time** |

## run2 — one case

| Case | Date | What it is | The report must show |
|---|---|---|---|
| R2 | 2026-08-10 12:00 | verification, run has NO profile | report renders fully; no split blocks (no referee profile) — degraded, not broken |

## Options to exercise by hand (the driver does all of them too)

* **Show all measurement runs** on/off — trend + side-by-side vs one run.
* **Show detailed data for each run** on/off — detail chapters appear/disappear;
  Report Results wording follows.
* **Un-tick single runs** in the list — Report Scope says "hidden by you",
  the PDF's proposed folder follows the selection (four-tier design).
* **Pass thresholds** — Result flips; with the split, Pass/Fail judges the
  within-gamut figures.
* **Save report as PDF** — proposed folder: one date → that date's
  `reports/`; several dates of run1 → `verifications/reports/`; both runs →
  the project's `reports/`.

All options are remembered between openings.
