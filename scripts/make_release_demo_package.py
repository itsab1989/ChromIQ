#!/usr/bin/env python3
"""Build the ONE demo package attached to every ChromIQ release (#182 K29).

Knut, #182, 5795310999 (2026-09-23): *"Create a bigger demo project package
that attacks all thresholds, metrics, requirement, output behaviour and
messages and functionality, from more angles of attack, so that none of these
things are only tested against one way of thinking, but rather multiple ways.
Use these demo projects in tests, but also release for download at release of
app. Try to use available paper data as part of the simulation data to make it
more realistic."*

What it builds, into ``<parent>/ChromIQ-Demo-Projects_v<APP_VERSION>/``:

* every project of `make_report_limit_demos` (its ``PROJECTS``, the
  report-folder, calibration and rename seeds, the demo chart presets), which
  includes the K29 angle projects (Paper-Classes, Border-Values, Second-Route,
  Renamed);
* ``Report-Limits-Evenness`` (`make_evenness_demo`) and
  ``Report-Notes-Every-Reason`` (`make_notes_demo`), which until K29 were in
  no release asset at all;
* ONE ``README.txt``, and ``COVERAGE.md`` / ``coverage-matrix.json``: every
  rule of the spec index, every metric row, threshold, verdict word, N-A
  reason, report type, run type, report location, message and help-worthy
  behaviour, with the projects that exercise it, COMPUTED from the saved
  reports of the built package (never from the plan).

Run it::

    python scripts/make_release_demo_package.py [PARENT] [--zip]
    python scripts/make_release_demo_package.py --verify <folder or .zip>

``--zip`` writes ``ChromIQ-Demo-Projects_v<APP_VERSION>.zip`` beside the
folder. ``--verify`` checks a built package and changes nothing: every project
present, every design matched, every measurable row exercised from two angles
each way, every spec-index rule mapped, and no path of the build machine left
in any file.

The release step (not done by this script)::

    python scripts/make_release_demo_package.py dist --zip
    python scripts/make_release_demo_package.py --verify dist/ChromIQ-Demo-Projects_v<ver>.zip
    gh release upload v<ver> dist/ChromIQ-Demo-Projects_v<ver>.zip
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

SPEC = REPO / "docs" / "design" / "measurement_report_limits.md"

#: The neutral place every build path is rewritten to. A saved report records
#: the absolute folder of each measurement it covers, so a package built on a
#: developer's Desktop would carry that developer's home folder into a public
#: download. The app matches a report's measurements from the project down
#: (`measurement_report.project_relative`, `_named_coverage_key`), which is
#: exactly what a user who unzips the package anywhere relies on, so every
#: project in the package is a MOVED project for everyone, the builder too.
NEUTRAL_PREFIX = "/ChromIQ-demo-build"

#: Text files the rewrite and the leak check read. Page TIFFs, profiles and
#: PDFs are never scanned; nothing in them records a folder.
TEXT_SUFFIXES = {".json", ".txt", ".md", ".ini", ".ti1", ".ti2", ".ti3",
                 ".cht", ".cie", ".ps", ".eps", ".csv"}


def app_version() -> str:
    from core.version import APP_VERSION
    return APP_VERSION


def root_name(version: "str | None" = None) -> str:
    return f"ChromIQ-Demo-Projects_v{version or app_version()}"


def zip_name(version: "str | None" = None) -> str:
    return root_name(version) + ".zip"


def _gen():
    import make_report_limit_demos as g
    return g


# ---------------------------------------------------------------------------
# The spec index, and what demonstrates each ruling
# ---------------------------------------------------------------------------
def spec_index_rows(spec: Path = SPEC) -> "list[dict]":
    """Every row of the index table at the top of the design record, read from
    the document itself so a ruling added tomorrow is a row this package must
    answer for."""
    rows: "list[dict]" = []
    in_table = False
    for line in spec.read_text(encoding="utf-8").splitlines():
        if line.startswith("| section | subject"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                if rows:
                    break
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4 or set(cells[0]) <= {"-", " "}:
                continue
            rows.append({"section": cells[0], "subject": cells[1],
                         "ruling": cells[2], "status": cells[3]})
    return rows


def is_superseded(row: dict) -> bool:
    return row["status"].lower().startswith("superseded") or (
        "NOT confirmed; superseded" in row["status"])


#: (section, a phrase of the subject, [demonstrations]). A demonstration is
#: "<project>/<run>: what to do there". Hand-written, because which project
#: shows a ruling is a design decision; checked, because `rule_map` fails on
#: any live index row this list does not answer, and on any project named here
#: that the package does not contain.
RULE_DEMOS: "list[tuple[str, str, list[str]]]" = [
    ("§11", "This report covers n of the total", [
        "Report-Limits-Report-Folders/run1: the report of ALL dates covers 3 of 3",
        "Report-Limits-Threshold-Series/run1: tick 4 of the 11 dates and Generate",
    ]),
    ("§13.8", "Generate asks about a selected report even when nothing changed", [
        "Report-Limits-Report-Types/run1: select a saved report, change nothing, Generate (M-REPORT-UNCHANGED-UPDATE-OR-NEW)",
        "Report-Limits-Paper-Classes/run2: the same on a Colour summary",
    ]),
    ("§13.8", "An Update re-creates a report by today's rules", [
        "Report-Limits-Report-Folders/run2: the second date's report saved by an older ChromIQ, Update it",
        "Report-Notes-Every-Reason/run6: the two older report shapes, Update them",
    ]),
    ("§13.9", "A report that judges nothing keeps every ticked measurement", [
        "Report-Limits-Report-Types/run7: Grey and tone check on a chart with no grey ramp",
        "Report-Limits-Border-Conditions/run3: a raw sheet, no verdict given",
    ]),
    ("§13.9", "One report, one limit set, applied to every measurement it includes", [
        "Report-Limits-Report-Folders/run1+run2: the report across both runs",
        "Report-Limits-Renamed/run1 + Report-Limits-Paper-Classes/run1: the report across two projects",
        "Report-Limits-Every-Limit-Set/run1 + Report-Limits-Second-Route/run1: one set, two charts",
    ]),
    ("§13.10", "Report types by run type; the automatic report follows", [
        "every run's profiling sheet: a Printing record only",
        "Report-Limits-Report-Types/run1..run7: every verification type",
    ]),
    ("§13.10", "The report type can be chosen with two runs' measurements added", [
        "Report-Limits-Report-Folders/run1: add run2's measurements, change the type",
    ]),
    ("§13.10", "Counts and list hold only the types the run type allows", [
        "Report-Limits-Report-Types/run1: four types saved, the bar decides which are counted",
        "Report-Limits-Report-Folders/run1: three verification types and the profiling record",
    ]),
    ("§13.10", "The profile bar's Run type decides", [
        "Report-Limits-Report-Types/run1: switch the bar between Profiling and Verification",
        "Report-Limits-Report-Folders (Calibration options on): Run type Calibration",
    ]),
    ("§13.11", "Where a report lives, and which folders the list reads", [
        "Report-Limits-Report-Folders: every location (date, run, project, pack reports/, cal/reports)",
        "Report-Limits-Renamed: a report in the pack's reports/ under a former project name",
    ]),
    ("§13.11", "Update moves an older report into the new place", [
        "Report-Limits-Report-Folders/run1: the LEGACY report of two dates",
        "Report-Limits-Report-Folders/run1: the DELETED report, its records left in the dates",
    ]),
    ("§13.11", "\"Save report as PDF\" opens the report's own reports/ folder", [
        "Report-Limits-Report-Folders/run1: a one-date and an all-dates report",
        "Report-Limits-Paper-Classes/run1: a one-date report",
    ]),
    ("§13.11", "A new report's PDF name carries that report's own time", [
        "Report-Limits-Report-Folders/run1: the all-dates report of 2026-12-21 09:00",
        "Report-Limits-Border-Values/run1: any of the three dates",
    ]),
    ("§13.12", "\"Report shown\" grouped by run and by project", [
        "Report-Limits-Report-Folders + Report-Limits-Report-Folders-Second",
        "Report-Limits-Renamed + Report-Limits-Paper-Classes",
    ]),
    ("§14", "A ChromIQ set never carries a \"recommended\" note", [
        "Report-Limits-Set-Compare/run1..run3: the three ChromIQ sets on one measurement",
    ]),
    ("§14", "The ISO COND cap is retired", [
        "Report-Limits-Custom-Columns/run1+run2: the two Custom columns and their caveat",
        "Report-Limits-Paper-Classes/run4: Custom ISO 12647-7 on office paper",
    ]),
    ("§16", "Evenness: method, noise guard", [
        "Report-Limits-Evenness/run1: even, drift, blotch, noisy",
        "Report-Limits-Evenness/run8: the same four through relative colorimetric",
    ]),
    ("§16", "9 by 9 stays the minimum grid", [
        "Report-Limits-Evenness/run2: 7 strips on the page",
        "Report-Notes-Every-Reason/run1: a 3 by 5 page",
    ]),
    ("§16.5", "E1 a page under 9 by 9 is left out", [
        "Report-Limits-Evenness/run2", "Report-Notes-Every-Reason/run5",
    ]),
    ("§16.5", "E3 all three ChromIQ sets carry 1.5 / 1.0", [
        "Report-Limits-Evenness/run1: the drift crosses 1.5, the blotch crosses 1.0",
    ]),
    ("§16.5", "E4 the evenness rows do not take a preset's star", [
        "Create Chart presets (verification demos): the presets window",
    ]),
    ("§16.5", "E5 / E6 Custom columns 1.5 / 1.0", [
        "Report-Limits-Custom-Columns/run1+run2: the evenness rows' limits",
    ]),
    ("§16.5", "E7 1.0 on the from-the-mean row", [
        "Report-Limits-Evenness/run1: the blotch date",
    ]),
    ("§16.6", "E2 page coverage at 60 %", [
        "Report-Limits-Evenness/run4: 68 % covered, judged",
        "Report-Limits-Evenness/run6: 37 % covered, N-A",
    ]),
    ("§16.6", "E4 the i1Pro 3 Plus 11 by 14 presets", [
        "Report-Limits-Evenness/run5: two pages, judged",
        "Report-Limits-Evenness/run7: one page, too noisy",
    ]),
    ("§21.1", "E8 evenness always judged in absolute Lab", [
        "Report-Limits-Evenness/run8: printed relative colorimetric on a real paper",
    ]),
    ("§21.2", "B8-483 the grey ramp's required steps", [
        "every From Profile Gamut run: grey rows N-A grey_steps_bunched",
        "Report-Notes-Every-Reason/run2: ramps that stop short of white and of black",
    ]),
    ("§21.3", "R2 the pre-flight widened", [
        "Report-Limits-Evenness/run3: nothing measured yet, open the Measure tab as a verification",
    ]),
    ("§21.4", "A report deleted across projects goes to", [
        "the pack's reports/: delete a report across two projects",
        "Report-Limits-Renamed: delete its report across projects",
    ]),
    ("§22", "K28: the judged figures on the one-page summary", [
        "Report-Limits-Report-Types/run1: the one-page summary's judged figures",
        "Report-Limits-Strip-And-Gamut/run4: a split sheet, the within-gamut sentence",
        "Report-Limits-Threshold-Series/run1: a set with \"–\" rows, and the For information heading",
        "Report-Limits-Renamed: a report across projects, the several-projects Run description",
        "Report-Notes-Every-Reason: B8-845's texts",
    ]),
    ("§17", "Trend graphs for the judged metrics", [
        "Report-Limits-Threshold-Series/run1: eleven dates",
        "Report-Limits-Border-Values/run1..run4: three dates hugging the limit line",
    ]),
    ("§17.1", "Every graph explains its lines", [
        "Report-Limits-Threshold-Series/run1", "Report-Limits-Second-Route/run1",
    ]),
    ("§18.1", "Calibration rule: every type but the Printing record", [
        "Report-Limits-Report-Folders: cal/ and its reports",
    ]),
    ("§18.12", "Run type Calibration as built in beta 39", [
        "Report-Limits-Report-Folders, -Report-Folders-Second, -Report-Types: a measured cal/ each",
    ]),
    ("§18.2 to §18.11", "K26:", [
        "Report-Limits-Threshold-Series/run1: Judged against row, within-gamut graph",
        "Report-Limits-Report-Folders: Profiling names Run1, Run2",
        "Report-Limits-Paper-Classes: the demo white is a real paper white",
    ]),
    ("§19.1", "Report text is for a customer", [
        "any saved report, e.g. Report-Limits-Paper-Classes/run1",
    ]),
    ("§19.2", "An N-A note names what the measured chart lacks", [
        "Report-Notes-Every-Reason: every reason",
        "Report-Limits-Strip-And-Gamut/run4 and Report-Limits-Border-Conditions/run1",
    ]),
    ("§19.3", "The one-page summary gives its numbers with their unit", [
        "Report-Limits-Report-Types/run1", "Report-Limits-Paper-Classes/run2",
    ]),
    ("§19.4", "The paper white line prints L\\*, a\\* and b\\*", [
        "Report-Limits-Paper-Classes/run1..run6: five real paper classes",
    ]),
    ("§19.5", "The verification pre-flight", [
        "Report-Limits-Evenness/run3: before the first verification (shown)",
        "Report-Limits-Paper-Classes/run5: after one (not shown)",
    ]),
    ("§19.6", "\"Unlock this run's limits\" is dim", [
        "Report-Limits-Threshold-Series/run3 and Report-Limits-Paper-Classes/run5: one date, dim",
        "Report-Limits-Border-Values/run1: three dates, locked, live",
    ]),
    ("§19.7", "Before printing, say that a metric the chart cannot answer", [
        "Report-Limits-Strip-And-Gamut/run4: a chart with no surface patch",
        "Create Chart presets (verification demos): the presets window",
    ]),
    ("§19.8", "Sheets with different patch counts", [
        "Report-Notes-Every-Reason/run2: three charts of different sizes",
        "Report-Limits-Threshold-Series/run1 + run2: 210 and 156 patches in one report",
    ]),
    ("§19.9", "A report type says which metrics it judges", [
        "Report-Limits-Report-Types/run1..run7",
    ]),
    ("§19.10", "Restore Used Chart restores the chart's fields only", [
        "Report-Limits-Paper-Classes/run4: an i1Pro layout",
        "Report-Limits-Threshold-Series/run2: an A3 ColorMunki layout",
    ]),
    ("§19.11", "A per-target row a stored block lacks opens on its default", [
        "any run of the pack (the generator stores printtarg and targen rows only)",
    ]),
    ("§19.12", "Knut's eight i1Pro presets built in", [
        "Create Chart presets (verification demos)", "the whole package",
    ]),
    ("§19.13", "\"New report…\" on a bound run shows the run's own set", [
        "Report-Limits-Isolated-Rows/run1: an edited column",
        "Report-Limits-Set-Compare/run2: ChromIQ tight",
    ]),
    ("§20", "Rulings not built", [
        "listed in the spec, one gap at a time; the package demonstrates the built ones above",
    ]),
]


def rule_map(rows: "list[dict]", present: "set[str] | None" = None) -> "list[dict]":
    """Every index row with its demonstrations, and whether it is answered."""
    out = []
    for row in rows:
        demos: "list[str]" = []
        for sec, needle, ds in RULE_DEMOS:
            if row["section"] == sec and needle.lower().replace("\\", "") in \
                    row["subject"].lower().replace("\\", ""):
                demos = list(ds)
                break
        sup = is_superseded(row)
        missing_projects = []
        if present is not None:
            for d in demos:
                for name in re.findall(r"Report-(?:Limits|Notes)-[A-Za-z-]+", d):
                    name = name.rstrip("-")
                    if name not in present and name + "-Second" not in present:
                        missing_projects.append(name)
        out.append({**row, "superseded": sup, "demos": demos,
                    "answered": sup or bool(demos),
                    "missing_projects": sorted(set(missing_projects))})
    return out


# ---------------------------------------------------------------------------
# Messages and behaviours
# ---------------------------------------------------------------------------
#: §M messages of the report and verification feature, and how to raise each
#: with the package. Read against the catalogue: an id here that the app no
#: longer has fails `--verify`, and a report message the app gains that is not
#: here is listed as not demonstrated.
MESSAGE_DEMOS: "dict[str, list[str]]" = {
    "M-REPORT-CHART-MISMATCH": [
        "Report-Limits-Strip-And-Gamut/run4: its chart cannot supply the surface row the column numbers",
        "Report-Limits-Report-Types/run7: a Grey and tone check with no grey ramp",
    ],
    "M-REPORT-CHART-MISMATCH-LAYOUT": [
        "Report-Limits-Evenness/run2: the evenness rows on a 7-strip page",
    ],
    "M-REPORT-DELETE": [
        "Report-Limits-Report-Folders/run1: Delete Selected Report on the all-dates report",
        "the pack's reports/: Delete a report across two projects",
    ],
    "M-REPORT-ONE-PAGE-ONE-DATE": [
        "Report-Limits-Report-Types/run1: Colour summary with both dates ticked",
        "Report-Limits-Paper-Classes/run2: the same on baryta",
    ],
    "M-REPORT-PATCH-COUNTS-DIFFER": [
        "Report-Limits-Threshold-Series: add run2 (156) to run1 (210)",
        "Report-Notes-Every-Reason/run2: three chart sizes in one run",
    ],
    "M-REPORT-UNCHANGED-UPDATE-OR-NEW": [
        "Report-Limits-Report-Types/run1: select a saved report, Generate",
        "Report-Limits-Border-Values/run1: the same",
    ],
    "M-REPORT-UPDATE-OR-NEW": [
        "Report-Limits-Report-Types/run1: select a saved report, change the type, Generate",
        "Report-Limits-Report-Folders/run1: select the all-dates report, untick one date, Generate",
    ],
    "M-REPORT-NOT-SAVED": [
        "not reachable from data: needs a disk that refuses the write",
    ],
    "M-VERIFY-PREFLIGHT": [
        "Report-Limits-Evenness/run3: Measure tab, Run type Verification, before the first measurement",
    ],
    "M-VERIFY-UNCHECKED-METRICS": [
        "Report-Limits-Strip-And-Gamut/run4: the pre-flight's paragraph on a chart that cannot answer every metric",
    ],
    "M-VERIFY-NO-CONTROL-STRIP": [
        "not reachable from a built project: raised when Create Chart files a verification chart that cannot carry a strip (Report-Limits-Strip-And-Gamut/run4 is such a chart, already filed)",
    ],
    "M-LIMIT-RECOMMENDED": [
        "not reachable while the ISO columns read '?' (a standard's recommended row)",
    ],
    "M-VERIFY-NO-PROFILE": ["not a report message: a run without a profile (none in this package)"],
    "M-VERIFY-NO-CHART": ["not a report message: a run without a verification chart (none in this package)"],
    "M-VERIFY-SAVED": ["raised after a real measurement; needs an instrument"],
    "M-VERIFY-CREATE-NO-PROFILE": ["not a report message: Create Chart on a run with no profile"],
}

#: Behaviours worth a help page, and where to try each.
BEHAVIOUR_DEMOS: "dict[str, list[str]]" = {
    "Restore Used Chart": [
        "Report-Limits-Paper-Classes/run4 (i1Pro layout)",
        "Report-Limits-Threshold-Series/run2 (A3)",
    ],
    "Delete Selected Report": [
        "Report-Limits-Report-Folders/run1", "the pack's reports/ (across projects)",
    ],
    "Update or New": ["Report-Limits-Report-Types/run1", "Report-Limits-Report-Folders/run1"],
    "Unlock this run's limits": [
        "Report-Limits-Border-Values/run1 (locked, three dates)",
        "Report-Limits-Paper-Classes/run5 (one date, dim)",
    ],
    "The verification pre-flight": ["Report-Limits-Evenness/run3"],
    "Trend graphs": ["Report-Limits-Threshold-Series/run1", "Report-Limits-Border-Values/run1"],
    "Report shown grouping": ["Report-Limits-Report-Folders + -Second", "Report-Limits-Renamed + -Paper-Classes"],
    "Paper white line": ["Report-Limits-Paper-Classes/run1..run6"],
    "A renamed project finds its reports": ["Report-Limits-Renamed"],
    "A moved project finds its reports": ["the whole package: every saved report names a folder that is not where the user unzips it"],
    "Where are my files?": ["Report-Limits-Report-Folders"],
}


def message_rows() -> "list[dict]":
    from workflow.measurement_messages import CATALOGUE
    out = []
    for mid in sorted(set(MESSAGE_DEMOS) | {
            k for k in CATALOGUE
            if k.startswith(("M-REPORT-", "M-VERIFY-", "M-LIMIT-"))}):
        msg = CATALOGUE.get(mid)
        withdrawn = msg is None
        out.append({"id": mid,
                    "title": getattr(msg, "title", "") if msg else "",
                    "demos": MESSAGE_DEMOS.get(mid, []),
                    "in_catalogue": not withdrawn})
    return out


# ---------------------------------------------------------------------------
# The saved reports, read back
# ---------------------------------------------------------------------------
def _meta(run_dir: Path) -> dict:
    try:
        return json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def saved_reports(root: Path) -> "list[dict]":
    """One entry per saved report of one measurement, with its route.

    A document file (role "document") covers several measurements and holds
    no verdict of its own; a report moved to ``old/`` by Delete is not in the
    list. Verdict records of the same measurement are kept once per
    (measurement, set, type).
    """
    out: "list[dict]" = []
    seen: set = set()
    for p in sorted(root.rglob("report_*.json")):
        rel = p.relative_to(root)
        parts = rel.parts
        if "old" in parts or len(parts) < 3:
            continue
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(rep, dict) or not isinstance(rep.get("verdict"), dict):
            continue
        if (rep.get("document") or {}).get("role") == "document":
            continue
        project = parts[0]
        run = parts[2] if len(parts) > 2 and parts[1] == "runs" else parts[1]
        kind = ("calibration" if parts[1] == "cal" else
                "verification" if "verifications" in parts else "profiling")
        run_dir = root / project / "runs" / run
        meta = _meta(run_dir) if kind != "calibration" else {}
        comp = rep.get("compliance") or {}
        printing = rep.get("printing") or {}
        chart = (f"{rep.get('patches')} patches, "
                 f"{rep.get('instrument') or '?'}"
                 + (", colorimetric reference"
                    if rep.get("reference_source") == "colorimetric" else ""))
        how = (printing.get("colour") or "not recorded") + \
            f" ({rep.get('yardstick') or '?'})"
        date = parts[-3] if kind == "verification" else kind
        key = (project, run, date, comp.get("set_id"), rep.get("report_type"),
               rep.get("ti3"))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "path": str(rel), "project": project, "run": run, "kind": kind,
            "date": date,
            "set_id": comp.get("set_id") or "", "edited": bool(comp.get("edited")),
            "type": rep.get("report_type") or "",
            "chart": chart, "print": how,
            "paper": meta.get("paper") or "",
            "rows": {r.get("row_id"): r for r in rep["verdict"].get("rows") or []
                     if isinstance(r, dict)},
            "overall": (rep["verdict"].get("overall") or {}).get("word")
            if isinstance(rep["verdict"].get("overall"), dict)
            else rep["verdict"].get("overall"),
        })
    return out


def angle_of(r: dict) -> tuple:
    """What makes two cases different angles (DESIGN.md, review point 1): the
    chart, the limit set, the report type or how the sheet was printed. The
    paper alone does not: on a media-relative sheet it is divided out."""
    return (r["chart"], r["set_id"], r["type"], r["print"])


def where(r: dict) -> str:
    return f"{r['project']}/{r['run']}/{r['date']}"


# ---------------------------------------------------------------------------
# The matrix
# ---------------------------------------------------------------------------
def coverage_matrix(root: Path) -> dict:
    from workflow.compliance_sets import ROWS, SET_BY_ID
    from workflow import measurement_report as _mr
    g = _gen()
    reps = saved_reports(root)
    selectable = sorted(g._selectable())

    metric: "dict[str, dict]" = {}
    cells: "dict[tuple, dict]" = {}
    words: "dict[str, list]" = defaultdict(list)
    reasons: "dict[str, list]" = defaultdict(list)
    for r in reps:
        for rid, row in r["rows"].items():
            w = row.get("word")
            if w:
                words[w].append(where(r))
            if row.get("reason"):
                reasons[row["reason"]].append(where(r))
            m = metric.setdefault(rid, {"trip": defaultdict(list),
                                        "pass": defaultdict(list),
                                        "valued": 0, "na": defaultdict(int)})
            if row.get("value") is not None:
                m["valued"] += 1
            if w == "N-A" and row.get("reason"):
                m["na"][row["reason"]] += 1
            side = "trip" if w == "FAIL" else "pass" if w == "PASS" else None
            if side is None:
                continue
            m[side][angle_of(r)].append(where(r))
            c = cells.setdefault((rid, r["set_id"]),
                                 {"trip": defaultdict(list),
                                  "pass": defaultdict(list)})
            c[side][angle_of(r)].append(where(r))
        if r["overall"]:
            words[f"overall {r['overall']}"].append(where(r))

    metric_rows = []
    for row in ROWS:
        m = metric.get(row.id)
        trip = dict(m["trip"]) if m else {}
        pas = dict(m["pass"]) if m else {}
        measurable = bool(m and m["valued"])
        metric_rows.append({
            "id": row.id, "label": row.label, "status": row.status,
            "measurable": measurable,
            "trip_angles": len(trip), "pass_angles": len(pas),
            "trip_examples": [v[0] for v in list(trip.values())[:4]],
            "pass_examples": [v[0] for v in list(pas.values())[:4]],
            "trip_routes": [list(k) for k in trip][:6],
            "pass_routes": [list(k) for k in pas][:6],
            "na_reasons": dict(m["na"]) if m else {},
            "why_not": ("" if measurable else
                        g.UNCOVERABLE_ROW_STATUS.get(row.status, "")),
        })

    cell_rows = []
    for row in ROWS:
        for sid in selectable:
            c = cells.get((row.id, sid))
            if c is None:
                continue
            cell_rows.append({
                "row": row.id, "set": sid,
                "set_label": SET_BY_ID[sid].label if sid in SET_BY_ID else sid,
                "trip_angles": len(c["trip"]), "pass_angles": len(c["pass"]),
                "trip_examples": [v[0] for v in list(c["trip"].values())[:3]],
                "pass_examples": [v[0] for v in list(c["pass"].values())[:3]],
            })

    codes = sorted({getattr(_mr, n) for n in dir(_mr) if n.startswith("REASON_")})
    reason_rows = [{"code": c, "count": len(reasons.get(c, [])),
                    "examples": sorted(set(reasons.get(c, [])))[:3],
                    "why_not": "" if reasons.get(c) else
                    g.UNREACHABLE_BY_DATA.get(c, "")} for c in codes]

    type_rows = []
    by_type = defaultdict(list)
    for r in reps:
        by_type[(r["type"], r["kind"])].append(where(r))
    for tid, name, _b, built in _mr.REPORT_TYPE_MENU:
        kinds = {k: len(v) for (t, k), v in by_type.items() if t == tid}
        type_rows.append({"id": tid, "name": name, "built": built,
                          "by_run_type": kinds,
                          "examples": sorted({x for (t, _k), v in by_type.items()
                                              if t == tid for x in v})[:3]})

    run_types = defaultdict(list)
    for r in reps:
        run_types[r["kind"]].append(where(r))

    locations = report_locations(root)
    index = rule_map(spec_index_rows(), {p.name for p in root.iterdir()
                                         if p.is_dir()})
    paper_rows = paper_facts(reps)
    return {
        "package": root.name,
        "saved_reports": len(reps),
        "projects": sorted(p.name for p in root.iterdir()
                           if p.is_dir() and (p / "project.json").is_file()),
        "spec_index": index,
        "metrics": metric_rows,
        "cells": cell_rows,
        "words": {w: {"count": len(v), "examples": sorted(set(v))[:3]}
                  for w, v in sorted(words.items())},
        "reasons": reason_rows,
        "report_types": type_rows,
        "run_types": {k: {"count": len(v), "examples": sorted(set(v))[:3]}
                      for k, v in sorted(run_types.items())},
        "locations": locations,
        "messages": message_rows(),
        "behaviours": BEHAVIOUR_DEMOS,
        "papers": paper_rows,
    }


def report_locations(root: Path) -> "dict[str, list[str]]":
    """Every kind of place a report lives in the package (K23)."""
    kinds: "dict[str, list[str]]" = defaultdict(list)
    for p in sorted(root.rglob("report_*.json")):
        rel = p.relative_to(root)
        s = str(rel)
        parts = rel.parts
        if parts[0] == "reports":
            kinds["the pack's own reports/ (across projects)"].append(s)
        elif "old" in parts:
            kinds["old/ (moved there by Delete)"].append(s)
        elif len(parts) > 2 and parts[1] == "cal":
            kinds["cal/reports/ (a calibration)"].append(s)
        elif len(parts) > 1 and parts[1] == "reports":
            kinds["<project>/reports/ (across runs)"].append(s)
        elif "verifications" in parts and parts[-3] == "verifications":
            kinds["<run>/verifications/reports/ (several dates of one run)"].append(s)
        elif "verifications" in parts:
            kinds["<date>/reports/ (one measurement)"].append(s)
        else:
            kinds["<run>/reports/ (the profiling sheet)"].append(s)
    return {k: v[:3] + ([f"... {len(v) - 3} more"] if len(v) > 3 else [])
            for k, v in sorted(kinds.items())}


def paper_facts(reps: "list[dict]") -> "list[dict]":
    """Each paper class with its source, its CIE whiteness, and the paper
    white the reports of runs printed on it actually recorded."""
    g = _gen()
    out = []
    for pc in g.PAPER_CLASSES.values():
        name = f"{pc.name} (demo)"
        runs = sorted({f"{r['project']}/{r['run']}" for r in reps
                       if r["paper"] == name})
        out.append({"id": pc.id, "name": pc.name, "lab": list(pc.lab),
                    "oba": pc.oba, "cie_whiteness": round(pc.cie_whiteness, 1),
                    "fact": pc.fact, "source": pc.source, "runs": runs})
    return out


def matrix_faults(m: dict) -> "list[str]":
    """What makes a package not shippable, as sentences."""
    faults = []
    for row in m["spec_index"]:
        if not row["answered"]:
            faults.append(f"spec index {row['section']} '{row['subject']}' is "
                          f"not mapped to any demonstration")
        for name in row["missing_projects"]:
            faults.append(f"spec index {row['section']} names {name}, which "
                          f"the package does not contain")
    for row in m["metrics"]:
        if not row["measurable"]:
            continue
        if row["trip_angles"] < 2 or row["pass_angles"] < 2:
            faults.append(f"metric {row['id']}: {row['trip_angles']} trip and "
                          f"{row['pass_angles']} pass angles (2 and 2 needed)")
    for msg in m["messages"]:
        if not msg["in_catalogue"]:
            faults.append(f"message {msg['id']} is not in the catalogue any "
                          f"more; take it out of MESSAGE_DEMOS")
    for pc in m["papers"]:
        if not pc["runs"]:
            faults.append(f"paper class {pc['id']} is printed on by no run")
    return faults


def cell_shortfalls(m: dict) -> "list[str]":
    """Cells of (row, limit set) with fewer than two angles each way. Listed,
    not fatal: a cell is one limit set's number, and several sets share the
    same rule."""
    return [f"{c['row']} x {c['set']}: {c['trip_angles']} trip, "
            f"{c['pass_angles']} pass"
            for c in m["cells"]
            if c["trip_angles"] < 2 or c["pass_angles"] < 2]


# ---------------------------------------------------------------------------
# Writing it down
# ---------------------------------------------------------------------------
def coverage_md(m: dict) -> str:
    L: "list[str]" = []
    a = L.append
    a(f"# Coverage of {m['package']}")
    a("")
    a("Computed from the saved reports of the built package by "
      "`scripts/make_release_demo_package.py`, never from the plan. "
      f"{m['saved_reports']} saved reports of single measurements were read, "
      f"across {len(m['projects'])} projects.")
    a("")
    a("An ANGLE is a different chart, limit set, report type or way of "
      "printing. The paper class is shown, but on its own it is not a new "
      "angle, because a media-relative sheet divides the paper out.")
    a("")
    a("## 1. The design record's index of rulings")
    a("")
    a("| section | subject | status | demonstrated by |")
    a("|---|---|---|---|")
    for r in m["spec_index"]:
        demos = ("superseded, nothing to show" if r["superseded"] and not r["demos"]
                 else "<br>".join(r["demos"]) or "**NOT MAPPED**")
        a(f"| {r['section']} | {r['subject']} | {r['status']} | {demos} |")
    a("")
    a("## 2. Metric rows: trip and pass angles")
    a("")
    a("| row | trips (angles) | passes (angles) | a trip | a pass | N-A reasons seen |")
    a("|---|---|---|---|---|---|")
    for r in m["metrics"]:
        if not r["measurable"]:
            continue
        flag = "" if r["trip_angles"] >= 2 and r["pass_angles"] >= 2 else " **short**"
        na = ", ".join(f"{k} ({v})" for k, v in sorted(r["na_reasons"].items()))
        a(f"| {r['label']} (`{r['id']}`){flag} | {r['trip_angles']} | "
          f"{r['pass_angles']} | {'<br>'.join(r['trip_examples'][:2])} | "
          f"{'<br>'.join(r['pass_examples'][:2])} | {na} |")
    a("")
    a("Rows no ChromIQ data can put a number on, and why:")
    a("")
    for r in m["metrics"]:
        if not r["measurable"]:
            a(f"* {r['label']} (`{r['id']}`, {r['status']}): {r['why_not']}")
    a("")
    a("## 3. Thresholds: every row against every selectable limit set")
    a("")
    a("| row | limit set | trip angles | pass angles | a trip | a pass |")
    a("|---|---|---|---|---|---|")
    for c in m["cells"]:
        a(f"| `{c['row']}` | {c['set_label']} | {c['trip_angles']} | "
          f"{c['pass_angles']} | {'<br>'.join(c['trip_examples'][:1])} | "
          f"{'<br>'.join(c['pass_examples'][:1])} |")
    short = cell_shortfalls(m)
    a("")
    a(f"Cells with fewer than two angles each way: {len(short)}.")
    for s in short:
        a(f"* {s}")
    a("")
    a("## 4. Verdict words")
    a("")
    for w, v in m["words"].items():
        a(f"* **{w}**: {v['count']} (e.g. {', '.join(v['examples'])})")
    a("")
    a("## 5. N-A reasons")
    a("")
    for r in m["reasons"]:
        a(f"* `{r['code']}`: {r['count']}"
          + (f" (e.g. {', '.join(r['examples'])})" if r["examples"] else
             f": NOT SHOWN. {r['why_not']}"))
    a("")
    a("## 6. Report types, run types, report locations")
    a("")
    for t in m["report_types"]:
        a(f"* {t['name']} (`{t['id']}`, {'built' if t['built'] else 'not built'}): "
          + (", ".join(f"{k} {n}" for k, n in sorted(t["by_run_type"].items()))
             or "no saved report"))
    a("")
    for k, v in m["run_types"].items():
        a(f"* run type {k}: {v['count']} saved reports (e.g. {', '.join(v['examples'])})")
    a("")
    for k, v in m["locations"].items():
        a(f"* {k}: {'; '.join(v)}")
    a("")
    a("## 7. Messages (§M)")
    a("")
    for msg in m["messages"]:
        a(f"* **{msg['id']}** {msg['title']}: "
          + ("; ".join(msg["demos"]) or "NOT DEMONSTRATED"))
    a("")
    a("## 8. Behaviours worth a help page")
    a("")
    for k, v in m["behaviours"].items():
        a(f"* **{k}**: {'; '.join(v)}")
    a("")
    a("## 9. Paper classes")
    a("")
    for p in m["papers"]:
        a(f"* **{p['name']}**, L* {p['lab'][0]}, a* {p['lab'][1]}, "
          f"b* {p['lab'][2]}, CIE whiteness {p['cie_whiteness']} (D50), "
          f"brighteners: {p['oba']}. {p['fact']} Source: {p['source']}. "
          f"Printed on by: {', '.join(p['runs']) or 'nothing'}.")
    a("")
    return "\n".join(L) + "\n"


PROJECT_PURPOSE = {
    "Report-Limits-Threshold-Series": "a dated series: every judged row crosses on one date and recovers on the next",
    "Report-Limits-Isolated-Rows": "rows that cannot cross alone, isolated by a run's own edited column",
    "Report-Limits-Set-Compare": "one measurement judged by ChromIQ default, tight and Quick check",
    "Report-Limits-Report-Types": "one run per report type, and a run holding several",
    "Report-Limits-Report-Folders": "every place a report can live, legacy and deleted reports, a calibration",
    "Report-Limits-Report-Folders-Second": "a second project for reports across projects",
    "Report-Limits-Custom-Columns": "the two Custom ISO columns with numbers",
    "Report-Limits-Border-Conditions": "a sheet under 20 patches, a raw sheet, an unrecorded printing",
    "Report-Limits-Profile-Gamut": "a From Profile Gamut chart: paper white, solids, CMY hue",
    "Report-Limits-Strip-And-Gamut": "the control strip, the surface of the cube, the most saturated quarter",
    "Report-Limits-Every-Limit-Set": "every judgeable row against every selectable limit set, first route",
    "Report-Limits-Paper-Classes": "five real paper classes, each on its own route (K29)",
    "Report-Limits-Border-Values": "exactly on a limit, 0.001 over, 0.001 under, on four rows and sets (K29)",
    "Report-Limits-Second-Route": "every cell of the limit-set matrix again, on a different chart and paper (K29)",
    "Report-Limits-Renamed": "a project renamed after a report across projects was written (K29)",
    "Report-Limits-Evenness": "evenness across the sheet: judged, too small, too noisy, too little of the page",
    "Report-Notes-Every-Reason": "every reason a row can read N-A, and older report shapes",
}


def package_readme(m: dict, limit_readme: str, notes_lines: "list[str]",
                   faults: "list[str]") -> str:
    from make_evenness_demo import __doc__ as even_doc
    L: "list[str]" = []
    a = L.append
    ver = m["package"].split("_v", 1)[-1]
    title = f"ChromIQ demo projects, version {ver}"
    a(title)
    a("=" * len(title))
    a("")
    a("Projects to try every part of ChromIQ's Measurement Report without a")
    a("printer or an instrument: every limit, every metric, every verdict word,")
    a("every reason a row can read N-A, every report type and every place a")
    a("report lives, each from more than one side (#182, Knut 5795310999).")
    a("")
    a("HOW TO USE IT")
    a("")
    a("1. Unzip the archive anywhere.")
    a("2. Open ChromIQ Preferences, Paths, and set 'Default output folder'")
    a(f"   to the unzipped folder, {m['package']}.")
    a("   Every project below then appears in the project list.")
    a("3. Open a project, pick a run, and open the Measurement Report.")
    a("")
    a("Every measurement is SIMULATED: real ArgyllCMS charts and profiles, with")
    a("readings designed so each date crosses exactly the limits it says it")
    a("does. It is a picture of the report's behaviour, not a measurement of")
    a("any printer, and contains no licensed reference values (ISO, Fogra,")
    a("Idealliance) and nobody's private measurements.")
    a("")
    a("THE PROJECTS")
    a("")
    for p in m["projects"]:
        a(f"  {p}")
        a(f"      {PROJECT_PURPOSE.get(p, '')}")
    a("")
    a("THE PAPERS")
    a("")
    a("Five classes of real paper, each a round, typical paper white under D50.")
    a("The value is ours; the fact it rests on is published, and named:")
    a("")
    for p in m["papers"]:
        a(f"  {p['name']}")
        a(f"      L* {p['lab'][0]}  a* {p['lab'][1]}  b* {p['lab'][2]}   "
          f"CIE whiteness {p['cie_whiteness']}   brighteners: {p['oba']}")
        for line in _wrap(p["fact"], 68):
            a(f"      {line}")
        for line in _wrap("Source: " + p["source"], 68):
            a(f"      {line}")
        a(f"      Printed on by: {', '.join(p['runs']) or 'nothing'}")
        a("")
    a("A run's profile is built from a sheet printed on its paper, so the paper")
    a("white its profiling sheet and every sheet printed through the profile")
    a("record is that paper's (seen on screen: 96.0 on the glossy paper, 94.5")
    a("on the rag). Two kinds of sheet do NOT show the class, and say so: a")
    a("sheet judged in absolute Lab (its printing not recorded), and a From")
    a("Profile Gamut chart. On both, every patch, the paper included, is put at")
    a("its designed distance from the chart's own aim, because that distance IS")
    a("what the date is designed to show. Runs not named here print on the")
    a("pack's default matte paper, 95.5 / 0.2 / 1.4.")
    a("")
    a("COVERAGE")
    a("")
    measurable = [r for r in m["metrics"] if r["measurable"]]
    ok = [r for r in measurable if r["trip_angles"] >= 2 and r["pass_angles"] >= 2]
    live = [r for r in m["spec_index"] if not r["superseded"]]
    a(f"{len(ok)} of the {len(measurable)} metric rows ChromIQ can measure are")
    a("tripped from at least two angles and passed from at least two.")
    a(f"{sum(1 for r in live if r['demos'])} of the {len(live)} live rulings in the design")
    a("record's index name the projects that demonstrate them.")
    a("COVERAGE.md lists every rule, row, limit, word, reason, type, location")
    a("and message with the projects that exercise it.")
    if faults:
        a("")
        a("NOT YET COVERED:")
        for f in faults:
            a(f"  {f}")
    a("")
    a("")
    a("=" * 72)
    a("THE REPORT-LIMIT PROJECTS IN DETAIL")
    a("=" * 72)
    a("")
    L.append(limit_readme.rstrip())
    a("")
    a("")
    a("=" * 72)
    a("Report-Limits-Evenness")
    a("=" * 72)
    a("")
    doc = (even_doc or "").strip().split("\n    python", 1)[0]
    L.append(doc)
    a("")
    a("")
    a("=" * 72)
    a("Report-Notes-Every-Reason")
    a("=" * 72)
    a("")
    L.extend(notes_lines)
    a("")
    return "\n".join(L) + "\n"


def _wrap(text: str, width: int) -> "list[str]":
    import textwrap
    return textwrap.wrap(text, width) or [""]


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def _is_text(p: Path) -> bool:
    return p.suffix.lower() in TEXT_SUFFIXES


def neutralise_paths(root: Path) -> int:
    """Rewrite the build folder in every text file to `NEUTRAL_PREFIX`.

    Returns how many files changed. Every spelling of the folder is replaced
    (`/tmp` is `/private/tmp` on macOS, and a resolved path may differ from
    the one a generator was handed), longest first so no half-replacement is
    left behind."""
    spellings = {str(root), str(root.resolve())}
    for s in list(spellings):
        if s.startswith("/private/"):
            spellings.add(s[len("/private"):])
    target = f"{NEUTRAL_PREFIX}/{root.name}"
    order = sorted(spellings, key=len, reverse=True)
    changed = 0
    for p in root.rglob("*"):
        if not p.is_file() or not _is_text(p):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new = text
        for s in order:
            new = new.replace(s, target)
        if new != text:
            st = p.stat()
            p.write_text(new, encoding="utf-8")
            os.utime(p, (st.st_atime, st.st_mtime))
            changed += 1
    return changed


LEAK_RE = re.compile(r"(/Users/[^/\s\"']+|/private/(?:tmp|var)/|/home/[^/\s\"']+|"
                     r"[A-Z]:\\\\Users\\\\)")


def path_leaks(root: Path) -> "list[str]":
    """Any text file that still names a home folder or a temp folder."""
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or not _is_text(p):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        m = LEAK_RE.search(text)
        if m:
            out.append(f"{p.relative_to(root)}: {m.group(0)}")
    return out


# ---------------------------------------------------------------------------
# Build, zip, verify
# ---------------------------------------------------------------------------
def build(parent: Path) -> "tuple[Path, int, list[str]]":
    """Build the package into *parent*. Returns (folder, the limit
    generator's exit code, the matrix faults)."""
    import make_evenness_demo as even
    import make_notes_demo as notes
    g = _gen()
    parent = Path(parent).resolve()
    root = parent / root_name()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    # THE TWO SMALLER GENERATORS FIRST, so the limit generator's own coverage
    # (which reads every Report-Limits-* folder) sees the evenness rows judged.
    even.build(root)
    _nroot, notes_lines = notes.build(root)
    rc = g.main([str(root)])
    limit_readme = (root / "README.txt").read_text(encoding="utf-8")
    m = coverage_matrix(root)
    faults = matrix_faults(m)
    (root / "coverage-matrix.json").write_text(json.dumps(m, indent=2),
                                               encoding="utf-8")
    (root / "COVERAGE.md").write_text(coverage_md(m), encoding="utf-8")
    (root / "README.txt").write_text(
        package_readme(m, limit_readme, notes_lines, faults), encoding="utf-8")
    n = neutralise_paths(root)
    print(f"\npaths: {n} files rewritten to {NEUTRAL_PREFIX}/{root.name}")
    for f in faults:
        print(f"  MATRIX: {f}")
    short = cell_shortfalls(m)
    print(f"matrix: {len(m['metrics'])} rows, {len(m['cells'])} cells, "
          f"{len(short)} cells short of 2+2, {len(faults)} faults")
    return root, rc, faults


def make_zip(root: Path) -> Path:
    out = root.parent / (root.name + ".zip")
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.name == ".DS_Store" or p.is_dir():
                continue
            zf.write(p, str(Path(root.name) / p.relative_to(root)))
    return out


def verify(path: Path) -> "list[str]":
    """Why a built package (folder or zip) is not shippable. Empty = ship."""
    path = Path(path)
    tmp = None
    try:
        if path.suffix.lower() == ".zip":
            if not path.is_file():
                return [f"no such archive: {path}"]
            tmp = Path(tempfile.mkdtemp(prefix="chromiq-demo-verify-"))
            with zipfile.ZipFile(path) as zf:
                zf.extractall(tmp)
            tops = [p for p in tmp.iterdir() if p.is_dir()]
            if len(tops) != 1:
                return [f"the archive holds {len(tops)} top folders, not one"]
            root = tops[0]
        else:
            root = path
        if not root.is_dir():
            return [f"no such folder: {root}"]
        g = _gen()
        gaps = list(g.verify_pack(root))
        for name in ("Report-Limits-Evenness", "Report-Notes-Every-Reason"):
            if not (root / name / "project.json").is_file():
                gaps.append(f"project missing: {name}")
        for name in ("README.txt", "COVERAGE.md", "coverage-matrix.json",
                     "intended-vs-actual.json"):
            if not (root / name).is_file():
                gaps.append(f"file missing: {name}")
        if not re.fullmatch(r"ChromIQ-Demo-Projects_v.+", root.name):
            gaps.append(f"the package folder is called {root.name}")
        try:
            results = json.loads((root / "intended-vs-actual.json")
                                 .read_text(encoding="utf-8"))
            for r in results:
                if g._misses(r):
                    gaps.append(f"design missed: {r['project']}/{r['run']}/"
                                f"{r['date']}")
        except (OSError, ValueError):
            pass
        # THE MATRIX IS RECOMPUTED FROM THE FILES, not read from the json the
        # build wrote: a package edited after it was built must not verify on
        # the strength of its own old claim.
        gaps += matrix_faults(coverage_matrix(root))
        gaps += [f"path of the build machine left in {x}"
                 for x in path_leaks(root)]
        return gaps
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("parent", nargs="?", default=str(REPO / "dist"),
                    help="folder to build the package in (default: dist/)")
    ap.add_argument("--zip", action="store_true",
                    help=f"also write {zip_name()} beside the folder")
    ap.add_argument("--verify", default="",
                    help="check a built package (folder or .zip) and exit")
    args = ap.parse_args(argv)
    if args.verify:
        gaps = verify(Path(args.verify))
        for x in gaps:
            print(f"  {x}")
        print(f"{'NOT SHIPPABLE' if gaps else 'complete'}: {args.verify}")
        return 2 if gaps else 0
    root, rc, faults = build(Path(args.parent))
    if args.zip:
        z = make_zip(root)
        print(f"archive: {z}  ({z.stat().st_size / 1e6:.1f} MB)")
    print(f"written to {root}")
    return 1 if (rc or faults) else 0


if __name__ == "__main__":
    # A FILE GENERATOR, NOT A DRIVER: nothing here opens a window. The two
    # smaller generators import Qt-backed layout code, and without this they
    # would try to reach the window server for no reason.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.exit(main())
