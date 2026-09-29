# R-107 NEW Guided "Refinement profile" ticked with no profile builds a plain chart silently
Area: guided
Grade: OBSERVED (R07): box ticked, path empty, Generate: targen without -c, no dialog, no log line; only the fixed-settings line says "Pick a profile to refine from (Browse... above)".
Severity: low
Why it matters: a first-time user who ticks the box and forgets the file gets an ordinary chart and no hint that the refinement did not happen. With a profile the row works: targen `-c <run>/preconditioning.icc -n28`, the profile copied into the current run.
Possible solutions (no code): grey Generate or ask when the box is ticked and the path is empty; or untick the box automatically and say so in the log.
