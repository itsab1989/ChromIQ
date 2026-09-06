# Every metric, one by one — what the standard asks, what ChromIQ has, what is missing
Round 4, issue #182. Answers Knut's instruction of 2026-09-05:
*"For every metric you say ChromIQ cannot comply with or calculate or measure today, please list
all of them one by one and explain why."*

**Sources.** `[P7]` ISO 12647-7:2016 free official preview (complete to 4.3.7);
`[P8]` ISO 12647-8:2021 free official preview (complete to 4.2.8);
`[TR15]` CGATS/Idealliance TR 015-2022 (complete);
`[G7M]` Idealliance G7 Master Pass/Fail Requirements v35, 2019;
`[CODE]` the ChromIQ checkout, read-only, cited `module:line`.
Anything not readable in a primary source is written **NOT ESTABLISHED** and names the document
that would settle it.

**The blocker vocabulary used in the last column.** Every "cannot" is one of exactly six things,
and they are not the same kind of problem:

| code | what is missing | can it be removed? |
|---|---|---|
| **W** | nothing but work — the arithmetic is defined and the inputs exist | yes, it is a build |
| **P** | *patches*: the chart does not contain the patch population the limit is written over | yes — by the patch-set criteria in `PATCH-SET-CRITERIA.md` |
| **R** | *reference*: an aim value per patch, which means the user's characterization file, which means the CMYK reader (S5/A3) | yes, once A1+A3 are settled |
| **L** | *licence*: the number, or the list of patches, is in a clause nobody here holds | only by buying the standard |
| **I** | *instrument or apparatus*: needs hardware ChromIQ's spectrophotometer path does not have | not by software |
| **D** | *declaration*: it is not a measurement at all — it is a property of the paper that somebody states | yes, cheaply — it is two dropdowns |

---

## Part A — the five ChromIQ computes today

`ACCURACY_METRICS`, `workflow/measurement_report.py:60-66`; `_stats`, `:374-404`;
`accuracy_verdict`, `:891-911`.

| # | metric — population × statistic | today | blocker |
|---|---|---|---|
| A1 | Average ΔE00 — all measured patches | computed, threshold `report_pass_threshold_avg` = 2,0 (`core/settings.py:229`) | — |
| A2 | Average ΔE00 — best 95 % | computed, same threshold | — |
| A3 | Average ΔE00 — worst 5 % | computed, same threshold | — |
| A4 | Maximum ΔE00 — all measured patches | computed, threshold `report_pass_threshold_max` = 3,0 (`:230`) | — |
| A5 | Maximum ΔE00 — best 95 % | computed, same threshold | — |

**The live defect in this block.** `avg_high5 ≥ avg_all ≥ avg_low95` and `max_all ≥ max_low95`
hold by construction (`_stats`, `low = a[:k]`, `high = a[k:]`). Three rows share one threshold and
two share the other, so a run passes exactly when A3 clears the average limit and A4 clears the
maximum. A1, A2 and A5 cannot fail alone. Knut's K3 ruling — five metrics, five numbers — repairs
it.

---

## Part B — computable, and only work stands in the way (blocker W and/or P)

These need no licence, no new hardware and no reference file. Each needs the right patches on the
sheet, which is what the criteria document is for.

| # | metric | what the standard asks | what ChromIQ has | what is missing | blocker |
|---|---|---|---|---|---|
| B1 | **Substrate (paper white) ΔE00** | ≤ 3,0 against the printing condition's substrate `[P7] 4.3.2 b) · [P8] 4.2.1 b)` | the paper-white patch is already found and reported (`report["paper_white"]`, `measurement_report.py`), and the `W` cube corner is already located with a presence test (`CUBE_CORNERS`, `CORNER_PRESENT_TOL = 12.0`, `:50-81`) | an **aim** for it. Against the reference condition that is **R**; against the user's own declared paper it is **W** | W + R |
| B2 | **Process-colour solids ΔE00** | ≤ 3,0 `[P7] 4.3.3` | the six chromatic cube corners and the composite black are already located and each already carries a ΔE00 when a reference exists (`report["corners"][…]["de"]`) | the same aim, and a rule that judges *these* patches separately instead of folding them into the whole-chart average — note they are currently **excluded** from the ΔE00 statistics on purpose (`:629-640`, "§9a rule 2") | W + R |
| B3 | **CMY solids — CIELAB metric hue difference ΔH\*ab ≤ 2,5** | `[P7] 4.3.3`, verbatim: *"The CIELAB metric hue difference for CMY shall not exceed 2,5"* | nothing. ChromIQ computes CIEDE2000's ΔH′ in three places; that is a **different quantity** | ~15 lines of arithmetic (ΔH\*ab = √(ΔE\*ab² − ΔL\*² − ΔC\*ab²)), and the aim | W + R |
| B4 | **Near-neutral scale — average ΔCh** | ≤ 2,0 `[P7] Table 2 r2` · ≤ 2,5 `[P8] Table 1 r3` | ΔCh — the a\*b\*-plane distance, `[P7] 3.2` — is **already computed**, as `PatchDelta.dab` (`workflow/colverify_runner.py:246-251`). It lives in the Verify tool, not in the report | move it into the report; identify the neutral scale on the sheet (**P**); an aim | W + P + R |
| B5 | **Near-neutral scale — maximum ΔCh** | ≤ 3,5 `[P7]` · ≤ 4,0 `[P8]` | same | same | W + P + R |
| B6 | **Single-colour ramps 30 %–70 % — absolute ΔL\* ≤ 2** (a *should*) | `[P8] 4.2.7` — Knut's K8 ruling puts it in the list | nothing | identify the ramps (**P** — and see the generator gap, below); an aim (**R**) | W + P + R |
| B7 | **Grey balance of the neutral ramp, substrate-relative** — *not in either ISO table; this is the G7 idea, and it is the one metric in this whole list that needs **no reference file at all*** | `[TR15] §5.3`: *"The color aim … is defined as a function of substrate CIELAB a\* and b\* values, reduced in proportion to the relative darkness of the scale."* | nothing — but every input is already in an ordinary ChromIQ measurement | the aim is computed from the sheet's own paper patch. **Measured, this round:** it runs on 40 of the measurements on this machine; see `measure_grey_balance_rgb.py` | W + P |

**The two ΔCh rows do not have the same population in the two standards, and this matters for the
patch-set criteria.** `[P7] Table 2` states it inline and the sentence is inside the free preview:
*"A CMY overprint scale roughly replicating the neutral scale for an average printing condition
comprising a minimum of five patches spaced approximately uniform intervals across the tone scale"*.
So for -7 the population is known, and it is a low floor: five patches, roughly evenly spaced.
`[P8] Table 1` writes the same two limits over *"Patches described in 5.2"* instead, and 5.2 is past
the end of that preview. So B4 and B5 are **W + P + R** for -7 and **W + P + R + L** for -8, and
criteria C6, C6+ and C7 are our own numbers, not the standard's.

**And B6's population is delegated, not free.** `[P8] 4.2.7` verbatim: *"The single-colour CMYK
patches (ramps), between 30 % and 70 %, described in ISO 12642-2 should be measured."* So the exact
tone values are pinned in a standard we do not hold, which puts B6 in the same family as the
clause-5.2 rows. Criterion C8's count-and-spread rule is a pragmatic substitute, and the report has
to say so.

---

## Part C — blocked on the reference, and therefore on CMYK (blocker R)

Computable arithmetic; nothing to compare against until a user supplies the printing condition's
characterization data, which is CMYK in every case, which is the reader that refuses it:
`workflow/ti3_analysis.py:159` — `raise Ti3ParseError("No device RGB columns — only RGB charts are
supported.")`. Tested last round: Knut's FOGRA51 file is refused.

| # | metric | limit | clause | note |
|---|---|---|---|---|
| C1 | All patches of the ISO 12642-2 target — **average** ΔE00 | 2,5 | `[P7] Table 2 r3 · [P8] Table 1 r5` | coincides with A1 **only when the printed chart *is* the reference target** |
| C2 | All patches of the ISO 12642-2 target — **95th percentile** ΔE00 | 5,0 | `[P7] Table 2 r3 · [P8] Table 1 r5` | see K9 on which 95th percentile |

---

## Part D — blocked on a licence (blocker L)

Nothing may be invented here, and nothing has been.

| # | metric | limit | clause | exactly what is unreadable |
|---|---|---|---|---|
| D1 | Control-strip patches — **average** ΔE00 | 2,5 | `[P7] Table 2 r1 · [P8] Table 1 r2` | **the population.** `[P7] 4.3.3` requires *"the digital control strip specified in 5.2"*; clause 5.2 is past the end of both free previews. **Which patches these are is NOT ESTABLISHED.** Five tolerance rows are written over it |
| D2 | Control-strip patches — **maximum** ΔE00 | 5,0 | `[P7] Table 2 r1` | same |
| D3 | Control-strip patches — **95th percentile** ΔE00 | 5,0 | `[P8] Table 1 r2` | same |
| D4 | Outer-gamut patches — average ΔE00 | 2,5 (226 patches) / 3,0 | `[P7] 4.3.4 · [P8] Table 1 r4, Annex C` | the **patch lists** are in Annexes that are in neither preview |
| D5 | Tone value reproduction limits | 2 %–98 % | `[P8] 4.2.6`; `[P7] 4.3.9` beyond the preview | ChromIQ measures no tone value at all — and for `[P7]` the limit itself is unread |
| D6 | Image register / resolving power | Knut's guide says ≤ 0,05 mm | `[P7] 4.3.11` | beyond the preview; **the number is NOT ESTABLISHED** |
| D7 | Margin / status information present | — | `[P7] 4.3.12` | beyond the preview; not a colour test |
| D8 | Ink-set gloss | "similar" | `[P8] 4.2.5`; `[P7] 4.3.8` beyond the preview | and gloss is **I**, below |

---

## Part E — not a measurement at all: a declaration (blocker D) — *and round 3's table was too pessimistic about these*

Round 2 already ruled fluorescence class a **declared** field; round 3's summary table then filed both it and gloss class under "ChromIQ cannot measure it". On re-reading the clauses they are not measurements
that ChromIQ is missing; they are **properties of the paper that somebody states**, and holding two
statements and comparing them is a small piece of work.

| # | requirement | what the clause says | why it is a declaration | what ChromIQ would need |
|---|---|---|---|---|
| E1 | **Substrate gloss class** must not cross between matte / semi-matte / gloss | `[P7] 4.3.2 a)` (shall) · `[P8] 4.2.1 a)` (should) | it is a category, from the paper maker's data sheet or a gloss meter | a three-way choice on the run, and the same for the production paper. **W + D** |
| E2 | **Substrate fluorescence class** — faint / low / moderate / high | `[P7] 4.3.2 c)` + Table 1 · `[P8] 4.2.1 c)`, both referring to ISO 15397:2014 5.12 | the measurement is **D65 brightness with UV in and UV out, per ISO 2470-2** — a paper-brightness test. No spectrophotometer ChromIQ drives can perform it. But it is **already declared in the reference file's own header** | a five-way choice for the user's paper; the other side is read from the dataset. **W + D** |

**A NOT-ESTABLISHED item that this round moved, though not all the way, from material already in
this thread.** `[P7]`'s NOTE calls the fluorescence figure *"the ratio UV/UV ex"*, while its Table 1
gives ranges 0–25, which cannot be a ratio. Knut's own attachment pushes hard the other way: every
Fogra file that states a class writes it as a **difference**. `FOGRA51.txt` and `FOGRA57.txt`:
*"fluorescence moderate (8-14 DeltaB according to ISO 15397)"*; `FOGRA52.txt`: *"fluorescence high
(> 14 DeltaB …)"*. Fogra's *moderate* band is Table 1's exactly; its *high* is open-ended where ISO
closes it at 25, and `FOGRA60.txt` uses *"fluorescence No"*, a category Table 1 does not name. So a
practitioner records it as **ΔB, a brightness difference in points**, and that is the best reading
available. **ISO 15397:2014 clause 5.12 is what would settle it and is still unread**, so the `?`
cell in the round-3 table becomes *"ΔB, on Fogra's usage"*, not *"ΔB, established"*.

---

## Part F — needs apparatus ChromIQ will never drive (blocker I)

| # | requirement | limit | clause | the apparatus |
|---|---|---|---|---|
| F1 | Within-sheet uniformity — SD of L\*, a\*, b\* at nine locations | < 0,5 each `[P7]` · ≤ 1,5 each `[P8]` | `[P7] 4.3.3 · [P8] 4.2.2.1 a)` | **none — see the correction below.** The instrument is the one already in the user's hand |
| F2 | Within-sheet uniformity — max ΔE00 from the nine-point mean | 2,0 · 2 | `[P7] 4.3.3 · [P8] 4.2.2.1 b)` | same |
| F3 | Macro-Uniformity-Score (ISO/TS 18621-21) | ≥ 50, should ≥ 60 | `[P8] 4.2.2.1` | a **scanning** spectrophotometer measuring areas, not patches. Genuinely out of reach, and the method is a separate paid standard |
| F4 | Repeatability, day to day / three prints | 2,0 · solids 2,0, mid-tones 2,5 | `[P7] 4.3.6 · [P8] 4.2.3 + Table 2` | no apparatus — a **protocol** (1 h, 1 day, recalibration control). ChromIQ's report trend is adjacent and is not this test. **W**, not I |
| F5 | Fading in the dark, first 24 h | 1,5 | `[P8] 4.2.4.2` | a timed physical test, measured M1 on white backing |
| F6 | Permanence across storage regimes | 2,5 (should 2,0; matte 4,0) · 4,5 | `[P7] 4.3.5 · [P8] 4.2.4.2` | climate chambers |
| F7 | Light fastness, filtered xenon, blue-wool 3 | rating 3 · ΔE00 < 4,5 | `[P7] 4.3.5 d) · [P8] 4.2.4.2` | a xenon exposure rig |
| F8 | Print stabilization / rub resistance | ≤ 30 min | `[P7] 4.3.7 + Annex B · [P8] 4.2.4.1` | the rub apparatus of `[P7]` Annex B |
| F9 | Vignette reproduction, no visible steps | shall | `[P8] 4.2.8` | a human eye under ISO 3664 P1 |
| F10 | Overprinted proofing substrate vs the production substrate | max ΔE00 3,0 | `[P7]` p11 | the *production* paper, in hand, measured |

### The correction on F1 / F2 — round 1 called this out of reach, round 2 corrected it, round 3's table put it back

He asked, 2026-09-04: *"what is the criteria for this, is that 9 measurement on one patch, or is
that a measurement of 9 patches distributed over the complete page?"*

It is the second, and the clause says so word for word. `[P8] 4.2.2.1`, verbatim:

> *"The variability of the coloration across the validation print format shall be verified by
> printing each of the three test forms described in 5.4. Each test form shall be measured at nine
> locations on each sheet as follows. Divide the printed area into thirds both horizontally and
> vertically and measure at the centre of each area."*

So: three full-format single-tint sheets, nine spot reads each, in a 3 × 3 grid at the centres of
the ninths. Every one of those steps is inside what ChromIQ already does — it lays out sheets, it
has a spot-read window, and the arithmetic is a standard deviation. **F1 and F2 are W, not I.**

**What still is not established:** clause 5.4 says *which three tints*, and 5.4 is past the end of
the preview. So the method is now known and the test forms are not. Same answer as D1: buy the
standard, or leave the row honest.

---

## Part G — no workflow of any kind exists (blocker W, large)

| # | requirement | clause | what it would take |
|---|---|---|---|
| G1 | Spot-colour solids and tints — max ΔE00 2,5 / 3,5 | `[P7] Table 2 r4 + 4.3.4 · [P8] Table 1 r6` | a spot-colour workflow and a CxF/X-4 path. Nothing in ChromIQ has either |
| G2 | Data delivered as PDF/X with the printing condition in `OutputIntents` and the profile in `DestOutputProfile` | `[P8] 4.1` | ChromIQ prints TIFF and PostScript |
| G3 | The measurement condition is M1 where the clause mandates one | `[P7] 4.3.5 · [P8] 4.2.4.2`; the general clauses `[P7] 5.4`, `[P8] 5.5` are past the preview | ChromIQ can **request** a filter, but Argyll writes `INSTRUMENT_FILTER` only for POLARIZED / D65 / UVCUT — **M0 and M1 leave identical evidence in the file: none.** So ChromIQ cannot *prove* what was used. It can *record what was asked for*, which is worth having and is honest. **W**, with a permanent asterisk |

---

## Part H — the two chart requirements that no numbers can satisfy

Not metrics. They are why a **verdict** may not carry either standard's name while the chart is
ChromIQ's.

* `[P7] 4.3.3`, verbatim: *"the digital control strip specified in 5.2 **and** an ISO 12642-2
  compliant chart shall be used."*
* `[P8] 4.2.2.2` says the same in its own words.

No ChromIQ chart is a 5.2 control strip and none is an ISO 12642-2 (IT8.7/4, 1 617-patch, CMYK)
chart. Permitted: *"judged against the tolerance values of ISO 12647-8:2021, Table 1"*, with the
unevaluated criteria listed. Forbidden: *"ISO 12647-8 PASS"*.

---

## Summary — how many of each

| blocker | metrics | is it permanent? |
|---|---:|---|
| computed today | 5 | — |
| **W** work only, or W + P | 7 (B1–B7, F1, F2, F4, E1, E2 in part) | **no** |
| **R** waits on the reference + the CMYK reader | 2 outright, and it gates most of B | no — S5/A3 |
| **L** waits on a purchased standard | 8 | no — it is money |
| **I** needs apparatus | 6 (F3, F5–F9) + F10 | **yes, for practical purposes** |
| **G** no workflow at all | 3 | no, but large |

**Nothing in the ISO tables is permanently impossible for reasons of colour science.** Six rows
need physical apparatus a colour-management application has no business owning. Everything else is
work, money or a chart with the right patches on it.
