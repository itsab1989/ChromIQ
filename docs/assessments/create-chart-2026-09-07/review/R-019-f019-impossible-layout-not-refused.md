# R-019 F-019 an impossible layout is not refused before Generate
Verdict: CONFIRMED, one fact added
Grade: OBSERVED (R04, R05: i1, custom 20 x 20, patch-first 60 mm: estimate dashes, Generate enabled, targen ran (443 patches), "[ERROR] ChromIQ layout engine: paper too short: a single pass of patches does not fit (8.0 mm available)", no dialog, preview NO PREVIEW, both frames at their placeholders).
Added: the app log carries "[WARNING] workflow.chart_creator: engine patch estimate failed: paper too short ..." BEFORE targen is launched (the Auto-count estimate already fails). The refusal point Agent 1 proposes therefore already exists in the code path; it is only not acted on.
Severity: medium (agree). See R-025 for what the failure does to exports/.
