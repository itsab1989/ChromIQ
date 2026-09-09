# R-005 F-005 "Clip border: Off, more patches" gains nothing with instrument margins on
Verdict: CONFIRMED
Grade: OBSERVED. i1 A4, instrument margins on: 525 both ways, Left 26.0 both ways (R04). Own margins 10 mm: Off 667 vs On 609, so the label is true when the instrument margins are off.
Severity: medium (agree). It is a design question exactly as Agent 1 framed it (is the 26 mm i1 left minimum the jig or the clip band). Solution A (a different left minimum when the clip is off) changes shipped geometry and touches the settled i1Pro margin rulings; B/C are text.
Spec: docs/dev_margin_inspector.md says the 26 mm i1 left seed is the clip border ("the i1Pro A4 portrait preset's 8 mm left/right" is the cross-scan example); the seed table row for A4 portrait L 26 therefore encodes the band. Agrees with Agent 1's reading.
