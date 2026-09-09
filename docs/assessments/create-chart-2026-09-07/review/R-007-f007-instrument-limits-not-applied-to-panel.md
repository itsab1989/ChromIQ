# R-007 F-007 an Instrument Limits change reaches the inspector but not the panel, the estimate or the build
Verdict: CONFIRMED
Area: layout engine / Preferences
Grade: OBSERVED
Attended: unattended (Preferences driven by a timer that asserted the title "ChromIQ Preferences" and pressed its OK)
Severity: high (agree)
Reproduced: R2-Guided, Manual, engine on, i1 A4 clip, instrument margins ticked (38/9/19/26, estimate 621 on that session's panel). Preferences > Instrument Limits > i1Pro / A4 Portrait, Top 38 -> 50, OK (settings read back T 50). Panel still 38/9/19/26, estimate still 621. Generate: built Top 38.9, verdict "Top margin 38.9 mm is below the 50 mm instrument minimum". Untick and re-tick "Use instrument margins": panel 50, estimate 598. Restore 38 in Preferences: panel stays 50 (one round behind, as Agent 1 said). Shots R02/10-f007-after-prefs-before-generate.png, 11-f007-built-after-T50.png, prefs-T50.png.
Code: ui/main_window.py:_open_settings refreshes `_apply_instrument_default_margin`, `_update_patch_count`, `_refresh_manual_command_preview`, `refresh_margin_inspector_settings`, `refresh_label_style_defaults`; nothing calls the layout panel's `_sync_instr_margins` (layout_options_panel.py:2914), whose only triggers are the checkbox toggle and instrument/paper changes.
Spec: per_target_settings.md §4c D-1: an instrument default may set a value the person has not chosen; with the box ticked the four margins are locked and are by definition not the person's, so refreshing them is inside the rule. §1.1: Preferences is the seed; the seed changed.
Solution check: Agent 1's A (re-run the sync after Preferences when the box is ticked) is the same code path the checkbox uses; watch `_saved_margins` (the user's own values remembered while the box is ticked must not be replaced by the table).
Tests: none pins the post-Preferences refresh; tests/test_layout_margin_thresholds.py covers the table maths only.
