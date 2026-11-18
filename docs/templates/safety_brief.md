# Template: the builder's safety brief for one round

Written by the person (or agent) who BUILT the round, for the reviewer, before the review
starts. One per build round of a driven instrument. Keep it short and exact: the reviewer
measures against it, so every claim in it must be checkable.

```markdown
# Safety brief: <instrument>, <round name> (<date>)

Tree: <branch> at <commit>; diff to review: <base>..<commit>.
No hardware was used; everything ran on the simulated device and helper.
Planted faults of the builder: <file with the list> (<caught> of <planted> caught).

## What changed, in one paragraph
<What the round does, in plain words. Say what did NOT change: "nothing in the job, the
allow-list, the caps or the recorded lines changed (`git diff <base> -- <device package>` is
empty)", if that is true.>

## 1. Every allow-list, cap and constant change, with its evidence
| what | before | after | evidence (recording, file, measurement) | test that pins it |
|---|---|---|---|---|

If none: "Allow-list and caps: UNCHANGED", and how you checked that.

## 2. What can move differently now
Every way the device can now move that it could not before, or no longer moves. Each with the
condition, the confirmation that comes before it, and the test.

## 3. What reads or saves differently
Calibration, readings, where a measurement is saved, what is kept between sessions.

## 4. The conditions, and where each is enforced
| condition | code (file::function) | tests |
|---|---|---|

## 5. What a reviewer should attack
The places YOU are least sure of, as concrete attacks: "any path that calls X while Y", "a
language with long labels", "Stop pressed while a pop-up is open".

## 6. Not changed, and why
Code that was left alone on purpose (another contributor's code, the hand path), and texts
whose version number was kept.
```
