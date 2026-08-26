# Per-target settings — test plan

> **These specifications are binding.** Knut, 2026-08-06: *"These must always be
> consulted on changing code so that behaviour defined is not violated. And if
> faults are found that do not match with the specification [it] must be
> reviewed and approved."*

Issue #130. The plan for [`per_target_settings.md`](per_target_settings.md),
written **before** the implementation, in Knut's order: *"Answer those and I
will write the test plan and build it, in that order."*

**Status, 2026-08-07.** The feature is built for all four tabs in scope
(beta.171–174) and most of this plan is written. What is done, and what is not:

| Section | State |
|---|---|
| §2 parameter coverage (P1–P6) | done for Create Chart, whose list is generated. The other three tabs are covered by their own drift guards instead — see below |
| §3 three-way agreement (A1–A5) | A1/A2/A4/A5 done. **A3 — the log line naming the parameter and value — is not** |
| §4 load events + negatives (L, N1–N4) | done: `tests/test_per_target_settings_events.py`, parametrised across the three storing tabs |
| §5 nothing-stored (S1–S9, D1–D4) | done for the empty and deleted cases; **D2, a truncated `meta.json`, is not** |
| §6 write events (W1–W8) | done |
| §7 demo package (X1–X7) | done — the seven steps are in the package document, and Demo-09's three runs carry a different patch count each (210 / 420 / 630) so X1 and X2 have something to recognise |

**Where §2's generated-list guarantee could not hold.** Only Create Chart is
built from `ParameterWidget`, so only it can be enumerated that way. Measure and
Build Profile get the same protection by a different route: their settings are
checked against `MeasureParams` / the preset pair, so a field added there and
not mapped fails the suite. Different mechanism, same promise — nothing is
hand-maintained without something failing when it drifts.

---

## 0. What the plan has to satisfy

Knut's requirement, read back as R1–R6 in §8 of the specification:

| # | Requirement |
|---|---|
| R1 | **On-screen**, driving the real window. Every non-global parameter, every in-scope tab |
| R2 | The **on-screen value**, the **logged value** and the **JSON tag and value** must agree — three-way |
| R3 | Every parameter in **both** states: empty/disabled and filled/enabled |
| R4 | Checked **before and after** the write |
| R5 | Loading happens at **exactly** the events in §2 and no others |
| R6 | The demo package exercises **every input source and activation event** |

Two properties of the specification shape the whole plan:

- **§1 S1.1** — the parameter list is *generated*, so the tests are generated
  from the same list. A parameter added to `parameters.yaml` is tested
  automatically, or the run fails for not knowing what to do with it. A
  hand-written list would rot, and a rotted list is what let `### Documentation`
  and the stock-only windows through.
- **§2.0** — one target is live at a time. Every assertion names the target it
  expects the value in, and at least one asserts the value is **not** in any
  other.

---

## 1. Shape of the harness

One driver, `scripts/drive_per_target_settings.py`, in the shape of
`scripts/drive_demo_package.py` and `scripts/drive_130_test_plan.py`: it starts
the **real** application on screen with the real styling, and drives it as a
person would.

```
for tab in (Create Chart, Measure, Build Profile, Calibration & Profiling):
    for widget in registry(tab):            # generated — S1.1
        for state in (filled/enabled, empty/disabled):
            set it on screen
            record: on-screen value, the log line, the JSON before and after
            trigger each write event in turn
            assert the three agree, in the right file, for the right target
```

**Why on screen and not a fixture.** Every fault in this area so far came from
the sequence, not the function: a signal that fires during a fill, a handler
that runs after a refresh, a value read before the widget was polished. A
fixture calling `save()` proves the function; it does not prove the tab.

**Hard-stop the driver.** A GUI driver that hangs costs a gate run. Timed
subprocess, no modal `.exec()` left open, and a watchdog that kills and reports
rather than waits.

---

## 2. Parameter coverage (R1, R3)

| # | Test | Asserts |
|---|---|---|
| **P1** | every widget the registry yields is driven | the count driven equals the count in the registry — a parameter cannot be skipped silently |
| **P2** | a widget the harness has no strategy for | **fails**, naming it. Never skipped |
| **P3** | each parameter, **filled/enabled** | stored with its value, in the right tag |
| **P4** | each parameter, **empty/disabled** | stored as *absent* or as *empty*, whichever the design says — and it comes back in the same state |
| **P5** | `-D ""` versus no `-D` | the two are distinguishable in the JSON and survive a round trip. §8's named trap |
| **P6** | a global parameter (§1.1) is changed | **nothing** is written to any target |

---

## 3. The three-way agreement (R2, R4)

For every parameter, at every write event:

| # | Test | Asserts |
|---|---|---|
| **A1** | before the write | the JSON does **not** yet hold the new value |
| **A2** | after the write | JSON tag and value == on-screen value |
| **A3** | the log line | names the parameter and the **same** value |
| **A4** | reload the target | the widget comes back to what the JSON holds |
| **A5** | the value lands in **that target's** file | and in no other run, verification or calibration (§2.0) |

A2 alone would pass on a store that writes the default; A1 is what makes it a
real observation. A4 is what makes it a round trip rather than a write.

---

## 4. Load events — exactly these, and no others (R5)

One test per row of §2, each asserting the load happened **and** that the widget
now shows the target's own value:

| # | Event | Also asserts |
|---|---|---|
| L1 | a tab is activated | the tab that was *not* activated has not loaded |
| L2 | Open Project | every tab marked stale; the visible one loaded at once |
| L3 | Profile run changes | write-then-load order (§2.1) — see N1 below |
| L4 | Run type changes | Verification goes through this path, not one of its own |
| L5 | chart opened / Restore Used Chart | the chart's recorded settings, not the defaults |
| L6 | preset loaded | the preset's values; the preset is not a target |
| L7 | `.ti1` / `.ti2` loaded | whatever the file carries |
| L8 | app start | the restored project, then L2 |

**Negative tests — the "no others" half, which is the half that gets forgotten:**

| # | Test | Asserts |
|---|---|---|
| **N1** | change target while standing on a tab | the outgoing target is **written first**, then the incoming one loaded. Assert by leaving the tab afterwards and checking the old edits did **not** land on the new target — the §2.1 hazard, stated as a test |
| **N2** | typing in a field | writes nothing, at any point, until an event in §3 |
| **N3** | loading a target's settings | does **not** trigger an auto-update rebuild (§7 B). Assert that no rebuild is **started** — see the note below |
| **N4** | opening a tab twice with no edit between | the second load writes nothing |

**N3 is the one that would actually hurt** — a rebuild over a measured chart —
so it is asserted on every tab, not once.

> ⏳ **Awaiting confirmation** — two corrections to N3's wording, not to the rule.
>
> **Confirmed by:** *nobody yet.*
>
> **1. "Assert the chart file's mtime is unchanged" cannot fail.** Measured
> 2026-08-26: the rebuild runs `_generate_from_ti1` → `ArgyllRunner.run` →
> `QProcess.start`, which is asynchronous. Nothing on disk has moved when the
> call returns — the `.ti2` is written by printtarg, in another process, and
> printtarg takes 0.263 s on a 210-patch A4 chart. With the 450 ms debounce
> ahead of it, the earliest the mtime can move is about 0.75 s after the switch.
> A test that switches run and stats the file therefore reads an **unchanged
> mtime while the bug is happening**. (Filesystem granularity is not the
> obstacle: `/private/tmp`, `$TMPDIR` and `$HOME` all resolve to ~1.6 ms here.)
>
> N3 now asserts that no rebuild is **started**: no redraw is armed, the layout
> fingerprint is re-baselined, and forcing the fire-time path renders nothing.
> That is the same rule, observed earlier and without the race — and the third
> clause closes the hole a two-flag check leaves, where a future seeding path
> both arms the timer and moves the fingerprint.
> `tests/test_the_live_preview_only_follows_the_user.py::
> test_selecting_a_run_does_not_re_render_its_chart`.
>
> **2. "Asserted on every tab" needs a definition for the other three.** Only
> Create Chart has an auto-update rebuild — `auto_update_preview` appears in
> `ui/tabs/tab_chart.py` and nowhere else — so on Measure, Build Profile and
> Check & Refine the sentence as written has nothing to assert, and a test
> written to satisfy it literally would pass without measuring anything. That is
> the failure this very rule was written to prevent: N3 itself sat green on a
> stand-in class with no timer while the real path was broken.
>
> Either those tabs get their own named equivalent of "a rebuild" (re-running
> profcheck? re-loading a `.ti3`? something else?), or the plan says plainly
> that N3 is a Create Chart rule because only Create Chart can rebuild. **That
> is a decision about the specification, not something to infer from the code.**

---

## 5. What a target with nothing stored opens on (§4)

One test per row, S1–S9. Each sets an unusual value on a *different* target
first, so "opens on defaults" cannot pass by accident when the defaults happen
to match:

| # | Case | Opens on |
|---|---|---|
| S1–S3 | run / verification / calibration **with** settings | its own |
| S4–S5 | run Profiling / Verification, **nothing** stored | saved defaults, else factory |
| S6–S7 | New run, Profiling / Verification | saved defaults, else factory |
| S8 | Calibration, nothing stored | saved defaults, else factory |
| S9 | a run from before the feature | defaults, and it records its own on first use |

| # | Test | Asserts |
|---|---|---|
| **D1** | `meta.json` **deleted** | S4/S5/S8, not an error and not the previous target's values — Knut's *"some cases can occur if user deletes a file"* |
| **D2** | `meta.json` **truncated / invalid JSON** | same |
| **D3** | a stored key that no longer exists | ignored, the rest still load (§7 A) |
| **D4** | New run | **empty** description and chart notes — the T5.1 reversal |

---

## 6. Write events (§3)

| # | Event | Test |
|---|---|---|
| W1 | Generate Chart | the target's settings match the screen |
| W2–W4 | preset / `.ti1` / `.ti2` loaded | same |
| W5 | auto-update redraw | same |
| W6 | **leaving a tab** | same, for the tab being left |
| W6q | **app quit** | writes the visible tab, for the selected target, **silently** — Knut's Q2 — and nothing for the other tabs (§2.0) |
| W7 | **Build Profile** pressed | tab 4, both modules |
| W8 | **Start / Continue Measurement** | the Measure tab |

W6q is driven by closing the real window, not by calling the handler: the point
is that Qt raises no tab-change for it.

---

## 7. Demo package (R6)

The package gains a project whose runs carry **real** measurements and **real**
`chart/` snapshots, because the current one cannot exercise Restore Used Chart —
Knut, step 24: *"The demo test runs and verification runs do not have proper
data files … thus using the 'Restore Used Chart' button was not possible."*

Steps to add, each naming the tab and the exact control:

| # | Step |
|---|---|
| X1 | set a distinctive value on run 1, switch to run 2, switch back — run 1's value is there |
| X2 | …and run 2 never acquired it |
| X3 | **New run — run 1's values, not defaults.** Written before Knut's seeding ruling (§4a N-1…N-5), which reversed it: selecting New run now shows what is already on screen, and the user edits that into the run they are about to make. The old wording is left visible here because a test plan that quietly changes is worse than one that shows its history |
| X4 | Restore Used Chart on a run — chart **and** its settings come back |
| X5 | the same for a **verification** |
| X6 | the same for a **calibration** — the case that failed in beta.157 |
| X7 | quit with an edited tab, reopen — the value is there, and no dialog appeared on quit |

---

## 8. Order of work

1. The registry (S1.1) — everything else is generated from it.
2. P1/P2, so an untested parameter is impossible before any storing exists.
3. The store, then A1–A5 per tab, Create Chart first (it already has a store).
4. L1–L8 and N1–N4. **N1 and N3 before the other tabs get stores**, because
   they are the two that corrupt rather than merely fail.
5. S1–S9, D1–D4.
6. Measure, Build Profile, Calibration & Profiling.
7. The demo package (X1–X7) and a full on-screen pass.

**Nothing ships until N1, N3 and D1 are green** — those three are the ones that
lose a user's work rather than inconvenience them.
