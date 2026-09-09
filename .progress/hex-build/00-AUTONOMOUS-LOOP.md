# Standing orders while Basti is away (2026-09-09)

He asked: *"can you make it a loop so you launch those challenging agents
yourself until there are no more blockers? because i have to leave for a while
now"* — and earlier, *"when it finds no more blocker i want 4.2.1 stable and
4.3.0 beta 1 with the report work tagged"*.

So the release is AUTHORISED, conditional on a clean round. These are the rules
I am holding myself to. If context is compacted, re-read this file first.

## The loop

1. One reviewer at a time, never two (his budget rule).
2. When it reports: verify every finding MYSELF before acting on one. Reviewers
   have been wrong before — a withdrawn finding, a probe that measured its own
   harness, numbers that disagreed with mine and each other.
3. Fix what qualifies as a blocker (below). Mutation-prove every fix lands and
   every new test bites. Run the full `--runslow` gate. Commit.
4. Launch the next round against the new commit, naming the fixes as its
   primary targets, and telling it to hunt the next self-validating test.
5. Repeat.

## What I fix without asking

* anything that prints wrong on paper, or outside the user's margins;
* anything that corrupts or misreports a MEASUREMENT;
* anything that shows the user a number or a picture that disagrees with the
  sheet in their hand;
* any test proved not to catch the fault it exists for;
* anything in the changelog that is untrue.

## What I do NOT fix, and defer to a 4.2.2 list

* anything measured byte-identical at the branch point AND on master — that is
  shipped behaviour, not this branch's, and changing it under a release is how
  a stable tag becomes a surprise. Two are already on that list: the margin
  inspector over-reporting on i1/p3/CM, and reopening a project unticking Auto
  so a Generate lays out 16 patches where the project held 525.
* design questions that are Basti's call, not mine. Currently open: whether an
  edge band should contrast with the PAPER rather than the patch (a white band
  on white paper is invisible), and the "wiith" typo baked into all three page
  TIFFs of Nelson's 648-patch target, which only he can regenerate.

## When I stop

* A round returns no blocker -> run the release sequence below.
* OR two consecutive rounds return only deferred/non-blocking items -> stop and
  report, because that is the same signal.
* OR a round contradicts an earlier one on a fact -> stop and report rather
  than pick a side.

## The release sequence, agreed with him

He chose "everything in 4.2.1", and MERGE over rebase, because the report work
must stay discardable:

1. green `--runslow`; `APP_VERSION` already reads 4.2.1
2. merge this branch into master (fast-forward), tag `v4.2.1`, push
   — pushing a `v*` tag fires build-release / build-linux / build-windows /
     sync-readme-version, so the platform assets build themselves
3. merge master INTO `feature/182-compliance-sets` (no force-push, nothing
   rewritten, the ten #182 commits keep their identities)
4. bump `APP_VERSION` to `4.3.0-beta.1`, write its CHANGELOG section, gate
5. tag `v4.3.0-beta.1`, push

The report work never touches master, so "delete the report work and proceed
with only the other stuff" is simply: do not merge that branch. No surgery.

## What I will NOT do while he is away

* force-push anything;
* touch the real preferences store (every driver sandboxes
  `CHROMIQ_SETTINGS_FILE` and `custom_output_path`, verified after each run);
* post to GitHub beyond what he has already approved (#164 is closed; nothing
  else goes out without him);
* delete or rewrite a published tag.
