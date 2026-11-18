# Template: the brief for an independent build review

For a review of a build round that is not mainly about physical safety (the panel, the
presentation, the run types, the texts). For a round that changes what the device may do, use
`docs/templates/safety_review_brief.md` instead or as well.

```markdown
# Review <N>: <what was built>

Review exactly <commit> (diff <base>..<commit>) in your own copy; read only in the builder's
tree; no hardware, no print dialog, no posting; temp files in your own folder.

## Look at it as a person would
* Run the app ON SCREEN on the simulated device (the proof driver:
  `scripts/driven_instrument_proof_driver.py`), the Beta on and off, in a narrow window
  (900 x 650) and in one other language.
* Open every picture of the builder's proof set and check it against its line in INDEX.md:
  nothing cut or overlapping, exactly one Stop, the current row or patch marked on the right
  patch, overlays centred, no default-looking button, the safety sentences visible, the version
  number of THIS build. Two identical pictures for two different states are a missing proof.

## Parity with the hand measurement (say for each: same, and reusing the hand path's code?)
- every run type (profile, refinement, calibration, verification) saved by its own rules;
- the START guards, in the same order;
- the completion window, auto-proceed, the log lines, a partial result and Continue;
- the lock (quit, close box, logout, shortcuts, tab switch, Preferences);
- Manual and Guided; greyed options each with a reason.

## Texts
New texts in §M-PROPOSED word for word as in the code; specification blocks under
"Awaiting confirmation" naming nobody; no em dash; singular and plural variants; do the texts
promise only what the code does?

## Deliver
REVIEW<N>.md: header, runs (with pytest's own exit codes), what holds, findings (BLOCKER /
MUST FIX / SHOULD / NOTE, each with where, what, the probe, a fix, measured or read), planted
faults, verdict, "To delete later".
```
