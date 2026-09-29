# F-022 Help texts that do not match the Argyll documentation or the engine they now describe
Area: help
Grade: OBSERVED (texts read from the running panel's data and data/parameters.yaml) + doc comparison against /Applications/Argyll/doc/printtarg.html, targen.html and printtarg.c
Attended: n/a
Type: UX (help accuracy)
Severity: low
Expected: An info text that explains an Argyll flag says what Argyll says; a text shown in a mode that never runs printtarg does not talk about printtarg.
Actual (each item verified against the source named):
1. printtarg -P "Don't Limit Strip Length": app text says "By default printtarg caps strip length so that every strip fits within the paper without overflow. Enabling this flag removes that limit". Argyll: "-P Don't limit strip length"; printtarg.c `nollimit` releases the INSTRUMENT'S strip-length limit (the ruler/jig length, 240 mm for the i1Pro in the engine). The paper always bounds a strip; the flag is about the instrument. The app's own ruler note ("Strip length 400 mm exceeds the 240 mm instrument ruler") says the right thing, the help says the wrong one.
2. printtarg -n "No Spacers": Argyll warns that omitting spacers "won't work successfully when a large number of test points is being used (>200), or when the patches are not randomized in location". The app text says only "Disable spacers only if your measurement workflow explicitly does not rely on them (e.g. some flatbed scanner setups)". The concrete Argyll limits are missing.
3. printtarg -L "Suppress Left Clip Border": app text "reclaiming ~15 mm of page width". The clip band is 26 mm (measured Left 26.0 on every i1 chart with the border; printtarg.c lbord); what is reclaimed is 26 minus the margin (16 mm at -m10, 20 mm at -m6). "~15 mm" is a rough number for one margin value.
4. targen -f Auto box tooltip (Manual): "...the Pages spinbox in the printtarg section" and "double-density, left-border, patch scale, margin". With the engine on, the Pages box lives in the ChromIQ layout panel and none of those printtarg terms apply; the text predates the engine.
5. Guided check boxes are labelled "Suppress left clip border (-L)" and "Don't limit strip length (-P)" although Guided always builds with the engine and never passes those flags (the engine has no -L or -P). The labels teach printtarg names for engine settings.
6. Instrument Limits intro: "the maximum strip length. The Create Chart preview warns when a chart goes outside these": true only while "Use instrument margins" is on (F-010) and never for area-first's own cap (F-008).
Items that checked out: -h ("hexagon for SS, double density for CM"), -a, -m/-M, -r, -b, -A, targen -e/-B/-g/-G, the CR30 shape help (345 vs 405 measured on A4 matches the text), the row-indicator widening note, and the ruler note wording.
Why it matters: The owner asked for beginner-tone help that is right; two of these (1 and 2) teach a wrong model of what the strip limit and spacers do.
Steps to reproduce: hover the info buttons named above, or read data/parameters.yaml entries for -P, -n, -L and the -f Auto tooltip in ui/tabs/tab_chart.py:4628.
Evidence: Reports/checkpoint-07 and this file; data/parameters.yaml lines for printtarg -P/-n/-L; /Applications/Argyll/doc/printtarg.html lines 311, 738; printtarg.c:2968 "-P Don't limit strip length".
Spec or source cited: CLAUDE.md i18n rules (help text describes current behaviour, no history); the Argyll docs as the trusted source per the brief.
Possible solutions (no code): rewrite the five texts; for the Guided boxes use engine wording ("Clip border" / "Cap strips at the ruler length") without flag names.
Regression risk if changed: none beyond translations (13 catalogues carry these strings).
Needs owner decision: no
