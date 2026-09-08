# R-105 NEW (the cause of F-003) Generate from "New run" adopts the seed block, not the screen, and reloads it over the user's edits
Area: run bar / per-target settings
Grade: OBSERVED (stack trace in R01)
Severity: high (it is F-003's cause and it covers every per-target row, not only printtarg's)
Actual: see R-003. `_align_current_run_to_target` -> `_adopt_new_run_settings` writes cache/new_run.json (captured when "New run" was selected) into the new run's meta.json, then `set_profile_run` triggers the visible-tab reload twice, which puts those pre-edit values back on screen; W1 then stores them.
Spec: per_target_settings.md §4a (Knut): the block "can be modified by user to what is desired for the new run. Then when Generate Chart is pressed, all these settings are copied into the new runs parameter slot". The code copies the unmodified block. §0 "exactly one writer" and §2.1 are broken during the click. This is a code/spec disagreement: report and approve before changing (CLAUDE.md rule 2), but the spec text already says which side is right.
Regression net: scripts/drive_new_run_seeding.py (11 checks), scripts/drive_per_target_settings.py (74 checks), tests/test_per_target_settings*.py, tests/test_a_preset_is_not_a_target_with_nothing_stored.py (P-1/P-2 must still hold).
