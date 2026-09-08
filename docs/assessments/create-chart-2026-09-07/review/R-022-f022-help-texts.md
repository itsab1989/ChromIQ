# R-022 F-022 help texts that do not match Argyll or the engine
Verdict: CONFIRMED for the items I checked (1, 2, 5); items 3, 4, 6 not re-checked
- Item 1 (-P): data/parameters.yaml says "By default printtarg caps strip length so that every strip fits within the paper without overflow". printtarg.c: `if (nollimit == 0) mxrowl = (240.0 - lcar - tspa)` else MAXROWLEN; the doc: "disables any normal limiting of strip length that would normally be imposed due to guide or instrument limitations. There is still an upper limit of around 500 patches or 2 Meters". Agent 1 is right: the limit is the instrument's, not the paper's.
- Item 2 (-n): doc lines 530 to 533 carry the ">200" and "not randomized" caveats; the app text does not. Right.
- Item 5: the Guided boxes read "Suppress left clip border (-L)" and "Don't limit strip length (-P)" on screen (R08) while the fixed-settings line under them says "ChromIQ layout engine". Right.
Severity low (agree). Translations: 13 catalogues.
