# Template: the brief for an independent safety review

Give this to a reviewer who did not build the work (a person, or a separate agent session that
has not seen your reasoning). Give them the code and the builder's safety brief
(`docs/templates/safety_brief.md`), never your conclusions. The same structure served for
every review round of the i1iO 2 table drive; the questions in section 3 are the ones those
rounds converged on.

```markdown
# Safety review <N>: <instrument>, <round name>

## Your copy, and the rules
* Review exactly <commit> (diff <base>..<commit>). Make your own copy (`git worktree add` or
  `git archive`) in your own new folder; the builder's tree is read only for you.
* No hardware, no USB device, no instrument program, no print dialog, nothing posted anywhere.
* Every probe you write is a test file in YOUR copy, so it can be run again and, if it finds
  something, copied into the suite. Your temp files stay in your folder (TMPDIR, --basetemp).
* Never edit a file while a test tier runs in that copy. Read pytest's own exit code (redirect
  to a file, then `echo "exit=$?"`), never through a pipe.
* Measure, do not only read: a finding from reading is a lead until a probe or the app on
  screen confirms it. Say for every finding whether it was measured or read.

## Scope
In scope: physical harm to the device, the instrument or a sheet; any write to the memory or
configuration of either; the allow-list and caps; truthful texts (do they promise what the code
does?); privacy (serial numbers, names, paths in logs and files); "Beta off changes nothing".
Out of scope: wording style, layout taste, performance (note them, at most, as NOTE).
"A step may fail" is not a finding; "a step may hurt the device" is.

## Questions every review answers
1. Can anything move without a fresh hands-off confirmation, especially after a stop, a
   refusal, a failure, a problem report, an ending, or while the person's hands were at the
   device? (Walk the QUESTIONS table.)
2. Does anything new reach the wire: a line outside the allow-list, a speed or a place not
   recorded, a cap raised, a memory write?
3. Can a move that may still be waiting (on the i1iO: a scan move waiting for the lamp) be lost,
   so that "switch it off first" is not said, at a stop, a lost link, a problem report or a
   quit?
4. Is the hand path's behaviour kept: START guards, run types and where each is saved, the
   completion window, the lock (quit, close box, shortcuts, tab switch, Preferences)?
5. Beta off: nothing imported, nothing written, nothing shown?
6. Are the texts true against the code, in English and in the translations you can check?
7. Are the tests strong enough? Plant at least <N> faults in your copy and report each.
8. Do the proof pictures show what their index says, on THIS version?

## What to deliver
A file REVIEW<N>.md with, in this order:
* header: reviewer, commit, diff, mode (on screen / offscreen, and why);
* runs: what you ran, its result, its output file, pytest's own exit code;
* what holds (checked, not read);
* findings by severity: BLOCKER (must not ship), MUST FIX (before the release), SHOULD, NOTE.
  Each: where (file:line), what happens, the scenario at the device, the probe that shows it,
  a proposed fix;
* planted faults: a table of fault, the test that caught it, or SURVIVED;
* verdict, in one paragraph;
* "To delete later": every folder you made.
```
