"""Re-derive every checkable claim in issue #133 from the code.

Why this exists: the #133 re-analysis (2026-08-08) scored its own evidence
quality 6 and said the document's numbers should be "re-derived, not re-read,
at implementation time". Sebastian asked for that to be done now. Re-reading is
what produced the fault it found — a whole capacity table quoted from the wrong
`patch_db` keys — so the fix has to be a script, not another careful read.

Three kinds of claim are checked:

1. **Citations.** Every ``file:line`` in the document, each with the text that
   must be at that line. A bare line number cannot be verified, so the
   expectation is part of the table: if the line moves, this fails and names
   what it was looking for.
2. **Numbers.** The capacity table, the sheet counts, the worked example, the
   cube-corner constants and the default margins — all recomputed from
   ``data/patch_db.py`` and the layout engine.
3. **Quotations.** Where the document quotes shipped text (the §M messages, the
   Build Profile tooltip, the PDF tooltip) the quote is compared against the
   real string, because a hand-copied duplicate is how those drift.

    python scripts/check_issue_133_numbers.py            # checks the local tree
    python scripts/check_issue_133_numbers.py --body f   # also checks a body dump

Exit code 0 when everything holds, 1 otherwise.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OK, BAD = [], []


def ok(what: str, detail: str = "") -> None:
    OK.append(what)
    print(f"  OK   {what}" + (f"  → {detail}" if detail else ""))


def bad(what: str, detail: str) -> None:
    BAD.append(what)
    print(f"  FAIL {what}\n         {detail}")


# --------------------------------------------------------------- 1. citations
#: ``(path, line, must_contain)`` — the anchor that makes the line number
#: meaningful. Keep this in step with the document.
CITATIONS: list[tuple[str, int, str]] = [
    ("workflow/xicclu_runner.py", 176, "def forward_lab"),
    ("workflow/xicclu_runner.py", 191, "def backward_device"),
    ("workflow/xicclu_runner.py", 239, "def to_device_via_profile"),
    ("workflow/colverify_runner.py", 162, "def write_reference_ti3"),
    ("workflow/colverify_runner.py", 81, "patches in gamut"),
    ("workflow/colverify_runner.py", 310, '"-L"'),
    ("workflow/colverify_runner.py", 356, "in_gamut = int"),
    ("workflow/chart_exports.py", 42, "def write_colours_txt"),
    ("workflow/chart_exports.py", 64, "def write_sidecars"),
    ("workflow/i1profiler_export.py", 251, "def write_txt"),
    ("workflow/i1profiler_export.py", 370, "DeviceColorValues"),
    ("workflow/i1profiler_export.py", 406, "def write_pxf"),
    ("workflow/i1profiler_export.py", 766, "def write_pwxf"),
    ("workflow/reference_convert.py", 255, "def cxf_measurement_to_ti3"),
    ("workflow/postscript_generator.py", 302, "cups-disable-cmm"),
    ("workflow/cups_printer.py", 45, "ColorSync"),
    ("workflow/cups_printer.py", 75, "ColorSync"),
    ("workflow/cups_printer.py", 86, "ColorSync"),
    ("workflow/cups_printer.py", 97, "ColorSync"),
    ("workflow/cups_printer.py", 114, "ColorSync"),
    ("workflow/measurement_report.py", 9, "design colours"),
    ("workflow/measurement_report.py", 49, "CORNER_PRESENT_TOL"),
    ("workflow/measurement_report.py", 71, "CUBE_CORNERS"),
    ("workflow/measurement_report.py", 191, "def _reference_labs"),
    ("workflow/measurement_report.py", 442, "is_verification"),
    ("workflow/measurement_report.py", 513, "CORNER_PRESENT_TOL"),
    ("workflow/ti3_analysis.py", 55, "VERIFICATION_KEYWORD"),
    ("workflow/measurement_messages.py", 228, "M_CHART_W4"),
    ("workflow/measurement_messages.py", 260, "M_CHART_VERIFY"),
    ("workflow/measurement_messages.py", 368, "M_VERIFY_NO_PROFILE"),
    ("workflow/measurement_messages.py", 388, "M_VERIFY_NO_CHART"),
    ("core/file_manager.py", 88, "VERIFICATIONS_DIRNAME"),
    ("core/file_manager.py", 900, "verifications_dir"),
    ("core/file_manager.py", 1269, "Where are my files"),
    ("core/file_manager.py", 1475, "Where are my files"),
    ("workflow/standard_targets.py", 178, "_USER_TARGETS_README"),
    ("ui/styles.py", 334, "QLabel#info"),
    ("ui/main_window.py", 934, "_apply_profile_tab_gate"),
    ("ui/main_window.py", 961, "_profile_building"),
    ("ui/measurement_target_bar.py", 767, "RUN_TYPE_VERIFICATION"),
    ("ui/tabs/tab_measure.py", 1263, "_verification_guard"),
    ("ui/tabs/tab_measure.py", 5006, "_verification_guard"),
    ("ui/tabs/tab_measure.py", 5081, "_verification_guard"),
    ("ui/tabs/tab_chart.py", 7998, "_engine_capacity"),
    ("ui/tabs/tab_chart.py", 8006, "patches_per_sheet"),
    ("ui/tabs/tab_chart.py", 8083, "_update_patch_count"),
    ("ui/tabs/tab_chart.py", 10178, "_is_verification_target"),
    ("ui/tabs/tab_chart.py", 10929, "write_sidecars"),
    ("ui/tabs/tab_profile.py", 3990, "Load measurement"),
    ("ui/tabs/tab_print.py", 132, "go out of"),
    ("ui/dialogs/layout_options_panel.py", 1044, "Also export a PDF"),
    ("docs/design/unified_measurement_management.md", 827, "colour management on"),
    ("docs/design/unified_measurement_management.md", 839, "colour management on"),
]


def check_citations() -> None:
    print("\n--- 1. citations: is the cited line still the cited thing? ---")
    for rel, lineno, needle in CITATIONS:
        p = ROOT / rel
        if not p.is_file():
            bad(f"{rel}:{lineno}", "the file does not exist")
            continue
        lines = p.read_text(errors="replace").splitlines()
        if lineno > len(lines):
            bad(f"{rel}:{lineno}", f"file has only {len(lines)} lines")
            continue
        if needle in lines[lineno - 1]:
            ok(f"{rel}:{lineno}", needle)
        else:
            hits = [i + 1 for i, l in enumerate(lines) if needle in l]
            bad(f"{rel}:{lineno}",
                f"expected {needle!r}; line reads {lines[lineno - 1].strip()[:70]!r}. "
                f"{needle!r} is now at {hits[:4] or 'nowhere'}")


# ----------------------------------------------------------------- 2. numbers
#: The §5.3 table, as the document prints it: per-sheet, then sheets for
#: 1 500 and 3 000 patches.
CAPACITY_CLAIMS = {
    ("i1", "A4"): (483, 4, 7),
    ("i1", "A3"): (714, 3, 5),
    ("p3", "A4"): (108, 14, 28),
    ("p3", "A3"): (153, 10, 20),
    ("CM", "A4"): (90, 17, 34),
    ("CM", "A3"): (240, 7, 13),
}
ENGINE_CLAIMS = {("i1", "A4"): 441, ("i1", "A3"): 672,
                 ("p3", "A4"): 99, ("CM", "A4"): 105}
MARGIN_CLAIMS = {"i1": 10, "p3": 6, "CM": 6}
#: The provenance of the four figures the document says were wrong.
WRONG_NUMBER_PROVENANCE = {682: ("i1", False, "11x17"), 1485: "594x420"}
ABSENT_NUMBERS = (165, 63)


def check_numbers() -> None:
    from data.patch_db import INSTRUMENT_DEFAULT_MARGIN, query_patches

    print("\n--- 2a. per-instrument default margins ---")
    for instr, want in MARGIN_CLAIMS.items():
        got = INSTRUMENT_DEFAULT_MARGIN.get(instr, 6)
        if got == want:
            ok(f"{instr} default margin", f"{got} mm")
        else:
            bad(f"{instr} default margin",
                f"the document claims {want} mm, the code says {got} mm")

    print("\n--- 2b. §5.3 capacity table (printtarg database) ---")
    for (instr, paper), (per, s1500, s3000) in CAPACITY_CLAIMS.items():
        m = INSTRUMENT_DEFAULT_MARGIN.get(instr, 6)
        got = query_patches(instr, paper, False, True, m, 1.0, False, False)
        if got != per:
            bad(f"{instr}/{paper} per sheet",
                f"document says {per}, query_patches says {got}")
            continue
        g1, g3 = math.ceil(1500 / got), math.ceil(3000 / got)
        if (g1, g3) != (s1500, s3000):
            bad(f"{instr}/{paper} sheet counts",
                f"document says {s1500}/{s3000}, derived {g1}/{g3}")
        else:
            ok(f"{instr}/{paper}", f"{got} per sheet → {g1} / {g3} sheets")

    print("\n--- 2c. §5.3 engine capacities ---")
    try:
        from workflow.layout_engine import geometry, instruments, papers
    except Exception as exc:  # noqa: BLE001
        bad("layout engine import", f"{exc} (is numpy installed in this venv?)")
        return
    for (instr, paper), want in ENGINE_CLAIMS.items():
        m = float(INSTRUMENT_DEFAULT_MARGIN.get(instr, 6))
        kw: dict = dict(instrument=instr, paper=paper, spacer_on=True,
                        pscale=1.0, margins=(m,) * 4, border=m, nolimit=False)
        if instr in ("i1", "p3", "CM"):
            kw["edge_spacers"] = True
        if instr in ("i1", "p3"):
            kw["nolpcbord"] = False
        if instr == "CM":
            kw["density"] = 1
        geom = instruments.geom_from_build_kwargs(kw, thresholds=None)
        got = int(geometry.patches_per_sheet(geom, *papers.dimensions_mm(paper)))
        if got == want:
            ok(f"engine {instr}/{paper}", str(got))
        else:
            bad(f"engine {instr}/{paper}", f"document says {want}, engine says {got}")

    print("\n--- 2d. where the four WRONG figures really came from ---")
    src = (ROOT / "data" / "patch_db.py").read_text()
    for num, key in WRONG_NUMBER_PROVENANCE.items():
        if isinstance(key, tuple):
            pat = (rf'\(\s*"{key[0]}"\s*,\s*{key[1]}\s*,\s*"{key[2]}"\)\s*:\s*{num}\b')
        else:
            pat = rf'"{key}"\s*:\s*{num}\b'
        if re.search(pat, src):
            ok(f"{num} belongs to {key}", "as the document says")
        else:
            bad(f"{num} belongs to {key}",
                "the document's provenance claim no longer matches patch_db")
    for num in ABSENT_NUMBERS:
        hits = re.findall(rf':\s*{num}\b', src)
        if hits:
            bad(f"{num} absent from patch_db",
                f"the document says it appears nowhere, but it is a value {len(hits)}×")
        else:
            ok(f"{num} absent from patch_db", "as the document says")

    print("\n--- 2e. the §10 worked example and the cube corners ---")
    from workflow.measurement_report import CORNER_PRESENT_TOL, CUBE_CORNERS
    n_corners = len(CUBE_CORNERS)
    if n_corners == 8:
        ok("CUBE_CORNERS holds 8 corners")
    else:
        bad("CUBE_CORNERS holds 8 corners", f"it holds {n_corners}")
    if float(CORNER_PRESENT_TOL) == 12.0:
        ok("CORNER_PRESENT_TOL is 12 device units")
    else:
        bad("CORNER_PRESENT_TOL is 12 device units", f"it is {CORNER_PRESENT_TOL}")

    per = query_patches("i1", "A4", False, True,
                        INSTRUMENT_DEFAULT_MARGIN.get("i1", 6), 1.0, False, False)
    patches = 1042 + n_corners
    sheets = math.ceil(patches / per)
    if (patches, sheets) == (1050, 3):
        ok("worked example", f"1042 + {n_corners} = {patches} → {sheets} sheets")
    else:
        bad("worked example",
            f"document says 1 050 patches → 3 sheets; derived {patches} → {sheets}")


# -------------------------------------------------------------- 3. quotations
def check_quotations(body: "str | None") -> None:
    print("\n--- 3. quotations of shipped text ---")
    from workflow import measurement_messages as M

    for name, msg, must in (
        ("M-VERIFY-NO-PROFILE step 6", M.M_VERIFY_NO_PROFILE,
         "Print that chart THROUGH the finished profile (with colour management on)"),
        ("M-VERIFY-NO-CHART step 2", M.M_VERIFY_NO_CHART,
         "Print it through this run's profile (with colour management on)"),
        ("M-CHART-VERIFY names Duplicate", M.M_CHART_VERIFY,
         "Duplicate the run instead"),
    ):
        _, text = msg.render(**{k: 2 for k in ("v", "c")}) \
            if getattr(msg, "count_key", None) else msg.render()
        (ok if must in text else bad)(
            name, must if must in text else
            f"the shipped message no longer contains {must!r}")

    tip = (ROOT / "ui" / "dialogs" / "layout_options_panel.py").read_text()
    for frag in ("Same as source (no colour management)",
                 "a pure red patch of 255,0,0 came back as "):
        if frag in tip:
            ok(f"PDF tooltip still says {frag[:38]!r}…")
        else:
            bad("PDF tooltip", f"no longer contains {frag!r}")

    lock = (ROOT / "ui" / "main_window.py").read_text()
    if "Not for a verification run." in lock:
        ok("Build Profile lock tooltip is still the quoted one")
    else:
        bad("Build Profile lock tooltip", "the quoted headline is gone")

    if body is None:
        return
    print("\n--- 3b. the body dump agrees with the derived numbers ---")
    for instr_label, paper, per in (("i1Pro", "A4", 483), ("i1Pro", "A3", 714),
                                    ("i1Pro3+", "A4", 108), ("ColorMunki", "A4", 90)):
        row = re.search(rf"^\|\s*{re.escape(instr_label)}\s*\|\s*{paper}\s*\|"
                        rf"[^|]*\|\s*(\d+)\s*\|", body, re.M)
        if row is None:
            bad(f"body row {instr_label}/{paper}", "no such row in the body")
        elif int(row.group(1)) != per:
            bad(f"body row {instr_label}/{paper}",
                f"body prints {row.group(1)}, derived {per}")
        else:
            ok(f"body row {instr_label}/{paper}", row.group(1))
    # A plain for/else would report OK even after a failure, because there is no
    # break to suppress it — the kind of quietly-wrong check this script exists
    # to stop shipping.
    #
    # SCOPED TO THE CAPACITY TABLE, because these are ordinary numbers.
    # Checking the whole body flagged "| 1 485 |" the moment the document
    # gained a table of FOGRA patch counts — 1 485 is a real figure there, and
    # a checker that cannot tell one 1 485 from another is a checker that
    # trains you to ignore it.
    i = body.find("### 5.3")
    j = body.find("### 5.4", i + 1) if i >= 0 else -1
    section = body[i:j] if i >= 0 and j > i else ""
    stale = [g for g in ("| 682 |", "| 1 485 |", "| 165 |", "| 63 |")
             if g in section]
    if stale:
        bad("the wrong figures are out of the table",
            f"still present as table cells: {stale}")
    else:
        ok("no wrong capacity figure is still a table cell")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", type=Path, default=None,
                    help="a dump of the issue body to cross-check")
    args = ap.parse_args()
    body = args.body.read_text() if args.body and args.body.is_file() else None

    check_citations()
    check_numbers()
    check_quotations(body)

    print(f"\n{len(OK)} OK, {len(BAD)} FAIL")
    for b in BAD:
        print(f"  FAIL {b}")
    return 1 if BAD else 0


if __name__ == "__main__":
    raise SystemExit(main())
