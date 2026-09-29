# R-002 F-002 both frames keep describing the previous chart under NO PREVIEW
Verdict: CONFIRMED (New run instance)
Grade: OBSERVED
Severity: medium (agree)
Reproduced: Demo-Full-RGB, Profiling, Profile run "New run": preview empty, "Measured from Preview" still "Margins: OK" with run2's numbers, on screen 240 (run2's chart), estimate 1452 (the New-run seeded layout). Shot R03/08-new-run-frames.png. The frames are visible (margin_visible True, info_visible True).
Note: the estimate column in this state is not stale, it is the prediction for the seeded New run; only the "on screen" column and the verdict are stale. Agent 1's solution A (clear `_margin_tiffs` and show the placeholder when the preview is cleared) leaves the estimate column useful, B (hide both frames) would remove the only capacity feedback for a New run before its first build. Prefer A.
Spec: none.
