# F-009 "Use instrument margins" is ticked and locks the four margin boxes for SpectroScan, CR30 and custom papers, while the inspector says no instrument margins exist
Area: layout engine (margins group) / Preferences (Instrument Limits)
Grade: OBSERVED
Attended: unattended
Type: UX / inconsistency
Severity: low
Expected: The checkbox is offered only when a table exists for the instrument and paper (the panel hides it entirely when no lookup is wired), or the boxes stay editable and the label says a fallback is in use.
Actual: SpectroScan flat A4: "Use instrument margins" visible and ticked, all four boxes greyed (disabled) at 6.0 / 6.0 / 6.0 / 11.1; after Generate the inspector prints "No instrument margins set for this instrument and paper size." Same for CR30 (6/6/6/14.4) and for every custom paper of every instrument (6/6/6/6 or the clip fallback). The 11.1 / 14.4 left value is the row-indicator band fallback computed in `_sync_instr_margins`, not an instrument limit. The Instrument Limits tab offers i1Pro, i1Pro 3+ and ColorMunki tables only (SpectroScan and CR30 have `default_ruler_mm` 0 and no seed rows).
Why it matters: A ticked box that locks controls promises a table that does not exist; the user cannot edit the margins without first discovering that the box is the reason, and the inspector contradicts the box on the same screen.
Steps to reproduce (click by click): MANUAL, engine on, Instrument SpectroScan, A4. Look at the Margins group (boxes greyed, box ticked). Generate. Read the status line under the preview.
Evidence: Screenshots/A4-margins/u01-SS-margins-group.png, u02-SS-flat-A4-window.png, Test Runs/logs/d03b_thresholds_and_stripcap.log ("SS: use_instr visible=True checked=True margins={t:(6.0,False)...l:(11.1,False)}"), d02_matrix.json (all SS / CR30 / custom rows: status "No instrument margins set...").
Spec or source cited: ui/dialogs/layout_options_panel.py:_sync_instr_margins fallback branch; docs/dev_margin_inspector.md "A missing combo -> no check (inspector still shows the measured numbers)".
Possible solutions (no code): A. Untick and disable the box (with a tooltip "no instrument limits are defined for this instrument and paper") when the lookup returns nothing. B. Keep it ticked but leave the boxes editable and rename the state "Instrument defaults (none set)". C. Seed SpectroScan and CR30 rows in Instrument Limits so the box is true.
Regression risk if changed: Low for A/B; C touches the seed table and its migration history (schemas 7, 12, 19).
Needs owner decision: yes (which of A/B/C matches his intent for hand-placed and flatbed instruments).
