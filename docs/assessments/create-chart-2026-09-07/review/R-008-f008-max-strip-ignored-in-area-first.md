# R-008 F-008 Max strip length and Don't cap are ignored in area-first
Verdict: CONFIRMED
Grade: OBSERVED (R04: A3 area-first cap 200 -> 43 per strip estimate and build; patch-first -> 18). The Max strip spin has no tooltip of its own (empty), as Agent 1 said.
Severity: medium (agree). Owner question stands (does area-first honour a typed cap). Solution B (grey the controls in area-first with a reason) is the lowest-risk one; A changes geometry for stored recipes with a non-zero cap.
