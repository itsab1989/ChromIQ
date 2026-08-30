# The dark-reference check — what a five-second hardware test found

2026-08-30, ~06:18. Basti ran the one branch no hardware had ever exercised:
black-calibrate with something deliberately in front of the opening.

## The result

```
calibrated against WHITE PAPER
CR30 dark reference read back at 0.00410 %R   (warn above 0.05)
→ reported as a healthy dark reference
```

**The check cannot see the mistake it appeared to guard against**, and the
reason is structural rather than a bug: a dark calibration DEFINES zero.
Whatever the instrument is looking at becomes the new zero, so reading that same
surface a moment later can only come back at ~0. It could only fire if something
moved in front of the aperture in the fraction of a second between the
calibration and the read-back — in practice, never.

What it does still prove is worth keeping: **the instrument answered, and
answered sanely.** Both texts now say that and no more. Basti's ruling, asked
and answered: keep the check, describe it accurately.

Under the project's own rule — no fake or circular checks — a check that cannot
see its own failure mode must not be described as one. It was described as *"the
one check it can honestly make"*.

## The bigger finding, which the test only exposed by accident

**Every calibration message was being erased.** `_on_start` cleared the
measurement log **fifty-one lines after** calling the calibration, in the same
method. So the read-back verdict, the note that a white calibration cannot be
verified at all, and the note naming which dark reference a skipped step left in
place were all written and then wiped milliseconds later.

**The check had been firing correctly for its entire life and nobody had ever
seen its answer.** That is how the overselling survived: there was no way to
notice it was wrong.

It surfaced only because Basti pasted the whole log and the answer was not in
it — *not even the "could not read back" variant*, which is what says **erased**
rather than **never ran**.

Fixed: the log is cleared before the calibration, and the reading also goes to
`chromiq.log`, so it survives in a support report instead of living only in a
panel the user can hide.

## And a ruling that generalises

> *"a failure message should be [a pop up] to warn the user and let him act
> accordingly because you can hide the log output as i do it and it is not that
> noticable there anyway"*

A dark reference that does not read as dark now opens a window that names the
number, says why it matters — every later reading is measured against it — and
offers **Take it again** rather than only describing the remedy. A healthy
reading still goes quietly to the log: only failures interrupt.

## Two faults found on the way, from one screenshot

* **bleak's own sentence was shown to the user.** *"Service Discovery has not
  been performed yet"* now reads *"the Bluetooth connection to the instrument
  was lost"*. Only library internals are translated — what the INSTRUMENT says
  is evidence and is kept verbatim.
* **ChromIQ invited him to measure over a dead link.** His CR30 powered itself
  off mid-session; the calibration failure window said "the measurement can go
  ahead", and a session started with patch A3 highlighted for an instrument that
  was not there. A refusal and a lost link now get opposite advice, and a lost
  link stops.

## Recorded, not implemented

A **real** check is possible: read the WHITE TILE after the black calibration,
where a dark reference taken against paper would show up. It costs the user
another step with the cap and it needs measuring before it is promised. In the
specification as a possibility, explicitly not a plan.

## Still true, and worth repeating

ChromIQ **cannot check a white calibration at all** — the instrument reports the
same value whatever is under the cap. That has always been said plainly and
still is.
