# F-027 A patch set loaded with the header icon stays armed after another project is opened (override row and greyed engine toggle appear on the other project)
Area: header (Load patch set) / presets
Grade: PARTIAL (the locked look is OBSERVED on the other project's screen; that Generate would build from the foreign .ti1 there is INFERRED from `_pending_patch_set_total` and was not executed)
Attended: unattended
Type: bug / regression risk
Severity: medium
Expected: Loading a patch set arms it for the project it was loaded into (D08b: Demo-Full-RGB, "Build it as a new run instead" created run4 from it). Opening a different project clears that arming; the other project shows its own state.
Actual: D08b, 09:37 to 09:40. External patch set loaded into Demo-Full-RGB (run4 built from it, 308 patches). Then A5-Furniture was opened and built normally. Then A1-EngineVsPrinttarg run1 was opened: its Manual panel shows "Edit patch recipe (override preset)" unticked above a collapsed targen group and the engine toggle greyed, the presentation used while a fixed patch set is armed. `_preset_ti1_path` still pointed at Evidence/external_patchset.ti1 when B5 was recorded, and nothing in the later project opens reports clearing it. The info line on A1 read "targen -d2 -f400 ..." (its own settings) while the lock said otherwise.
Why it matters: If the arming persists, the next Generate on A1 would lay out the foreign 304-patch set instead of A1's own recipe, and the greyed toggle stops the user changing the engine choice for a reason that belongs to another project.
Steps to reproduce (click by click): Header icon "Load patch set", choose any .ti1, answer "Build it as a new run instead". Open another project (Open Project or session restore). Look at the Manual panel: override row and greyed engine toggle. (Generate was not pressed in this state; do that to complete the proof.)
Evidence: Screenshots/B9-window/w-1280x800-manual.png and w-1700x1050-manual.png (A1-EngineVsPrinttarg with the override row and greyed toggle), Test Runs/logs/d08b_results.json (b5-load-ti1 preset_ti1 path), d08b_rest.log sequence.
Spec or source cited: per_target_settings.md section 2, L2 (a project change replaces the target); tab_chart `_leave_prebuilt` / `_leave_applied` exist for presets but the armed `_preset_ti1_path` is cleared only on specific paths (13109, 11264, 8729).
Possible solutions (no code): clear the armed patch set (and the override rows) whenever the project or the target changes, unless the incoming target's own sidecar arms one.
Regression risk if changed: Low-medium (preset flows rely on the same flags).
Needs owner decision: no
