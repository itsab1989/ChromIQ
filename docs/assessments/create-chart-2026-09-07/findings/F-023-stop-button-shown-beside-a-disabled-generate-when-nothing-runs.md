# F-023 In the From Profile Gamut module without a profile, a Stop button is shown beside the disabled Generate button while nothing is running
Area: gamut
Grade: OBSERVED
Attended: unattended
Type: UX
Severity: low
Expected: Stop appears only while a build runs (as in Guided and Manual, where it is hidden at rest).
Actual: Run type Verification, run without a profile (Demo-Full-RGB run3), FROM PROFILE GAMUT: the module shows its "This run needs a finished profile first" card, Generate Chart is greyed, and a live-looking STOP button stands next to it. Nothing is running. Seen twice (D00 at 07:46 and D08 at 09:29, stop_visible True).
Why it matters: A greyed Generate with a live Stop reads as "something is running and cannot be started", which is the opposite of the state.
Steps to reproduce (click by click): Open a project whose current run has no .icc. Run type: Verification. Click FROM PROFILE GAMUT. Look at the bottom-left buttons.
Evidence: Screenshots/00-launch/10-gamut-module.png, Screenshots/B3-gamut/g03-gamut-no-profile-run3.png, Test Runs/logs/d08_results.json (b3-no-profile: generate_enabled False, stop_visible True).
Spec or source cited: measurement_exit_strategy.md does not cover Create Chart's Stop; tab_chart._stop_btn visibility is toggled by the build state in Guided/Manual.
Possible solutions (no code): hide Stop whenever no build is running, in every module.
Regression risk if changed: none.
Needs owner decision: no
