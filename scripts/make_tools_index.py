#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Write the generated part of docs/dev_tools_index.md: every script in scripts/, by topic.

The hand-written top of docs/dev_tools_index.md explains the reusable TOOLS by purpose. Below
it, between two marker lines, this script lists EVERY file in scripts/ (Python, shell and
PowerShell): its path, whether it is a reusable TOOL or a one-off EXAMPLE of a past check, the
first line of its docstring (or of its header comment), and what it needs, read from its
source (a display, a settings sandbox, ArgyllCMS, paths of the maintainer's machine).

    python scripts/make_tools_index.py            # rewrite the generated part
    python scripts/make_tools_index.py --check    # exit 1 when the file is out of date

`tests/test_tools_index_is_current.py` runs --check, so a script added without running this
fails the suite, and the index cannot rot. It writes only docs/dev_tools_index.md.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
INDEX = ROOT / "docs" / "dev_tools_index.md"
BEGIN = "<!-- BEGIN GENERATED: python scripts/make_tools_index.py -->"
END = "<!-- END GENERATED -->"

#: The reusable tools (documented in the hand-written part); everything else is an EXAMPLE.
TOOLS = {
    "scripts/userdrive.py", "scripts/onscreen_capture.py", "scripts/onscreen_capture_win.py",
    "scripts/capture_screens.py", "scripts/instrument_parity.py",
    "scripts/instrument_parity_drive.py", "scripts/compare_with_release.py",
    "scripts/i1io_cut_check.py",
    "scripts/gate_tier.py", "scripts/session_cleanup.py", "scripts/disk_report.py",
    "scripts/em_dash_check.py", "scripts/make_demo_projects.py", "scripts/i18n_extract.py",
    "scripts/i18n_sync.py", "scripts/i18n_check_name_widths.py", "scripts/i18n_onscreen_audit.py",
    "scripts/i18n_agent/new_language.py", "scripts/audit_tool_file_placement.py",
    "scripts/audit_default_buttons.py", "scripts/audit_interaction_state_rules.py",
    "scripts/sweep_every_tab_for_clipping.py", "scripts/recording_timeline.py",
    "scripts/recording_vs_allowlist.py", "scripts/recordings/synthetic.py",
    "scripts/planted_faults.py", "scripts/driven_instrument_proof_driver.py",
    "scripts/make_tools_index.py", "scripts/run_tests.sh", "scripts/release_notes.py",
    "scripts/vendor_instlib.py", "scripts/decode_i1profiler_probe.py",
    "scripts/check_bundle_load_paths.py", "scripts/ptyrun.py", "scripts/run_release_gates.sh",
    "scripts/check_bundle_min_macos.py", "scripts/make_release_demo_package.py",
}

#: (topic, regular expression on the file's path); the first that matches wins.
TOPICS = (
    ("Driven instruments and recordings", r"recording|driven_instrument|planted|i1profiler_probe|"
                                          r"i1io|isis|fd9|tablescan|table_"),
    ("Release, gates and packaging", r"gate|release|bundle|homebrew|vendor|build_icons|"
                                     r"run_tests|tools_index|windows|win_"),
    ("Disk hygiene", r"disk|cleanup|session_clean"),
    ("Languages and texts", r"i18n|em_dash|german|translat|_de_|_de\.|lang|txt_round|tone|"
                            r"wording|words|text"),
    ("Calibration", r"calib|printcal|applycal|_cal_|cal\.py"),
    ("Reports and verification", r"report|limit|verif|evenness|metric|trend|quality"),
    ("Presets and recipes", r"preset|recipe|defaults"),
    ("Measurement", r"measure|strip|read|ti3|refine|averag|misread|chartread|scan|ruler"),
    ("Instruments", r"instrument|i1p|i1pro|cr30|spectro|lights|button|usb|ch34x|munki|"
                    r"colorchecker|parity"),
    ("Printing", r"print|pdf|ppd|paper|lp_|cups"),
    ("Charts and layout", r"chart|layout|margin|patch|page|target|cube|hex|grid|label|"
                          r"spacer|targen|ti1|ti2|demo|sample"),
    ("Profiles and colour", r"profile|engine|gamut|icc|colprof|cie|neutral|colour|color"),
    ("Driving and photographing the app", r"capture|onscreen|userdrive|shot|drive|proof|"
                                          r"mockup|render|screen"),
)
OTHER = "Other one-off checks"

#: a home folder written into a script (built in two parts, so this file does not match itself)
_HOME = re.compile("/" + "Users" + r"/[^/\s]+/|/home/[^/\s]+/")


#: People named in docstrings are named by their role in this public listing.
_PEOPLE = ((r"\bKnut's\b", "a maintainer's"), (r"\bKnut\b", "a maintainer"),
           (r"\bBasti's\b", "the owner's"), (r"\b(Basti|Sebastian)\b", "the owner"),
           (r"\bNelson Lau's\b", "a contributor's"))


def _first_paragraph(text: str) -> str:
    para = []
    for line in text.strip().splitlines():
        if not line.strip():
            if para:
                break
            continue
        para.append(line.strip())
    return " ".join(para)


def describe(path: Path) -> str:
    """The first paragraph of the module docstring, or of the header comment."""
    src = path.read_text(encoding="utf-8", errors="replace")
    text = ""
    if path.suffix == ".py":
        try:
            text = ast.get_docstring(ast.parse(src)) or ""
        except SyntaxError:
            text = ""
    if not text:
        comments = []
        for line in src.splitlines()[:40]:
            s = line.strip()
            if s.startswith("#!") or s.startswith("# SPDX") or s.startswith("# Copyright"):
                continue
            if s.startswith("#"):
                comments.append(s.lstrip("#").strip())
            elif s.startswith("<#"):
                continue
            elif comments or (s and not s.startswith(("import", "from", "set ", "param"))):
                break
        text = "\n".join(comments) if comments else ""
    one = _first_paragraph(text) or "(no description in the file)"
    one = one.replace(" — ", ": ").replace("—", ", ").replace("|", "/")
    one = _HOME.sub("~/", one)
    for name, role in _PEOPLE:
        one = re.sub(name, role, one)
    one = re.sub(r"\*\*|`", "", one)
    if len(one) > 220:
        one = one[:217].rsplit(" ", 1)[0] + " ..."
    return one


def needs(path: Path) -> str:
    """What the script may need, read from its source (a heuristic: check before you run it)."""
    if path.resolve() == Path(__file__).resolve():
        return "-"
    src = path.read_text(encoding="utf-8", errors="replace")
    out = []
    if re.search(r"^\s*(from|import)\s+[\w.]*(userdrive|onscreen_capture|capture_screens)", src,
                 re.M) or "screencapture" in src:
        out.append("display")
    if re.search(r"CHROMIQ_SETTINGS_FILE|userdrive|_sandbox", src):
        out.append("settings sandbox")
    if re.search(r"\b(targen|printtarg|colprof|chartread|scanin|printcal|applycal)\b", src):
        out.append("ArgyllCMS")
    if _HOME.search(src):
        out.append("maintainer's paths: adapt first")
    return ", ".join(out) or "-"


def topic(rel: str) -> str:
    name = rel.lower()
    for title, rx in TOPICS:
        if re.search(rx, name):
            return title
    return OTHER


def files() -> "list[Path]":
    out = []
    for p in sorted(SCRIPTS.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        if p.suffix in (".py", ".sh", ".ps1"):
            out.append(p)
    return out


def generated() -> str:
    groups: "dict[str, list[str]]" = {}
    for p in files():
        rel = p.relative_to(ROOT).as_posix()
        kind = "TOOL" if rel in TOOLS else "example"
        row = f"| `{rel}` | {kind} | {describe(p)} | {needs(p)} |"
        groups.setdefault(topic(rel), []).append(row)
    order = [t for t, _ in TOPICS] + [OTHER]
    parts = [BEGIN, "",
             f"Every file in `scripts/` ({sum(len(v) for v in groups.values())} in all), by "
             "topic. TOOL: reusable, kept working. example: a one-off check kept as a worked "
             "pattern; it may need adapting, and one marked \"maintainer's paths\" will not run "
             "unchanged on another machine. \"needs\" is read from the source by a heuristic. "
             "Read a script before you run it, and set CHROMIQ_SETTINGS_FILE first "
             "(scripts/README.md).", ""]
    for title in order:
        rows = groups.get(title)
        if not rows:
            continue
        parts += [f"### {title} ({len(rows)})", "", "| file | kind | what it does | needs |",
                  "|---|---|---|---|", *rows, ""]
    parts.append(END)
    return "\n".join(parts) + "\n"


def render(current: str) -> str:
    if BEGIN in current and END in current:
        head = current[:current.index(BEGIN)]
        tail = current[current.index(END) + len(END):].lstrip("\n")
        return head + generated() + (("\n" + tail) if tail else "")
    return current.rstrip("\n") + "\n\n" + generated()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="change nothing; exit 1 when docs/dev_tools_index.md is out of date")
    a = ap.parse_args(argv)
    current = INDEX.read_text(encoding="utf-8") if INDEX.is_file() else "# Developer tools\n"
    new = render(current)
    if a.check:
        if new != current:
            print("docs/dev_tools_index.md is out of date: run python scripts/make_tools_index.py")
            return 1
        print("docs/dev_tools_index.md is current")
        return 0
    if new != current:
        INDEX.write_text(new, encoding="utf-8")
        print(f"written: {INDEX.relative_to(ROOT)}")
    else:
        print("already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
