STATUS: in-progress

# 06 — Hexagon generalisation critique (#159)

**Role:** CR30-HEX-CRITIC. Adversarial review of the *generalisation* of
hexagonal-patch support from a SpectroScan special case to a capability any
instrument's geometry can carry. Written against the live working tree of
`feature/cr30-instrument-159` while another agent implements. Every claim is
cited `file:line` and, where it is a behavioural claim, proved by running the
real engine. No production file or test was edited by this report.

**The design under attack:** do *not* widen `key == "SS"` to
`key in ("SS","CR30")`. Replace identity with capability — drive the gates off
`hxeh`/`hxew` (which a hexagonal `Geom` already sets non-zero), or add an
explicit boolean on `Geom` that whichever branch builds a hexagon sets.

Sections are appended as they are finished. Findings are ranked
BLOCKER / SERIOUS / MINOR and collected at the end.

