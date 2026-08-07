#!/usr/bin/env python3
"""Audit every user-facing English string against ChromIQ's own writing rules.

Basti, 2026-08-07, before the pre-GA translation pass: *"would this be a good
opportunity to check whether all of the texts that are facing to the user are
friendly, extensive and easy to understand?"*

It is the right moment, and the right order. A string's **English source text is
its catalogue key**, so rewording one after it has been translated throws away
eleven translations of it. Auditing first means the translation pass only ever
sees text that is going to stay.

**This tool reports; it does not rewrite.** Message text is governed by §M of
`docs/design/unified_measurement_management.md` and the wording is Knut's to
approve — see the banner in that document. So the output of this script is a
list to post and get reviewed, never a patch to apply.

Every check below is a rule this project has already written down, not a matter
of taste. That matters: a tone audit that reports opinions produces an
unactionable list, and the reviewer has to re-litigate each one. Each finding
cites the rule it breaks.

    RULE                                     WHERE IT IS WRITTEN DOWN
    ----------------------------------------------------------------
    no "(s)" — real singular and plural      CLAUDE.md, i18n section
    no history ("used to", "no longer")      feedback_helptext_no_history
    no Markdown — Qt renders it literally    feedback_no_markdown_in_message_strings
    name the exact control, not "the box"    the tone contract
    no bare jargon without an explanation    the tone contract
    a tooltip explains outcome + prereq      the tone contract (too-short bodies)

Usage:
    python scripts/i18n_tone_audit.py              # summary + findings
    python scripts/i18n_tone_audit.py --csv out.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "data" / "i18n" / "de.json"      # keys == the English sources
PARAMS = ROOT / "data" / "parameters.yaml"


@dataclass
class Finding:
    rule: str
    severity: str          # "must" = a written rule is broken; "look" = needs a human
    text: str
    detail: str

    @property
    def short(self) -> str:
        t = self.text if len(self.text) <= 90 else self.text[:87] + "…"
        return t.replace("\n", "⏎")


# --------------------------------------------------------------------------
# The checks
# --------------------------------------------------------------------------

#: "(s)" and friends. The rule is explicit: count-bearing messages get real
#: singular and plural variants, because "1 patch(es)" is the kind of detail
#: that makes an app feel unfinished.
#:
#: The suffix must be **attached** to the noun — "patch(es)", "file(s)". With a
#: space in front it is something else entirely: "Enhanced Saturation / ICC (s)"
#: is ArgyllCMS's rendering-intent *flag letter*, and flagging it as a plural
#: dodge was this check's only hit on the whole 4,092-string corpus.
_PLURAL_DODGE = re.compile(r"\w\((s|es|ren)\)", re.I)

#: Text that tells the user what the app *used* to do. Help text describes what
#: is true now; a user reading "this used to be under Settings" has to work out
#: whether they are running the old version.
#:
#: **Tightened after the first run, which reported 57 and was mostly wrong.**
#: Two English constructions defeat the obvious pattern, and both are correct
#: writing that must NOT be flagged:
#:
#:   * *"a first-pass profile **used to** seed a better second chart"* — that is
#:     "utilised in order to", not the past habitual. Only "used to be" is
#:     unambiguous.
#:   * *"ChromIQ will **no longer** treat this chart as measured"* — that
#:     describes the consequence of the action the user is about to take, in the
#:     future tense. History would be "ChromIQ no longer supports…", about the
#:     app's own evolution.
#:
#: A tone audit whose list is mostly false costs the reviewer more than it
#: saves, so the checks stay narrow and certain rather than broad and noisy.
_HISTORY = re.compile(
    r"\b(used to be|formerly|in (an )?earlier versions?|in previous versions?|"
    # NOT "has been moved to": *"your previous measurement has been moved to
    # the run's old folder"* reports what just happened to the user's own file,
    # which is the archive-not-delete promise being kept. Flagging it was the
    # second false positive this check produced.
    r"before version|was renamed|"
    r"(ChromIQ|the app|we) (now )?no longer)\b", re.I)

#: "no longer" preceded by "will"/"would"/"can" is a consequence, not history.
_CONSEQUENCE = re.compile(r"\b(will|would|can|could|shall|may)\s+no longer\b", re.I)

#: Markdown in a string that Qt renders as plain text. QMessageBox shows the
#: asterisks. Backticks and underscores are the same trap.
_MARKDOWN = re.compile(r"\*\*[^*]+\*\*|(?<!\w)\*[A-Za-z][^*]{2,}\*(?!\w)|`[^`]+`")

#: "Tick the box", "click the button" — which box, which button? The rule is to
#: name the control exactly as it is labelled on screen.
_VAGUE_CONTROL = re.compile(
    r"\b(tick|check|untick|uncheck|click|press|select)\s+"
    r"(the\s+)?(box|checkbox|check box|button|option|field|dropdown|drop-down|menu)\b",
    re.I)

#: Terms a first-time user will not know. Each must be explained where it is
#: first used, or carry a Dictionary entry. Listed rather than inferred, because
#: a heuristic for "jargon" flags every technical word in a colour-management
#: app and is therefore useless.
_JARGON = [
    "chromatic adaptation", "tetrahedral", "OFPS", "perceptual intent",
    "device link", "black point compensation", "gamut clipping",
    "spectral", "tristimulus", "colorimetric", "dE94", "dE2000",
    "quantisation", "dithering", "linearisation",
]

#: Below this, a tooltip body is a label with a full stop, not an explanation of
#: the outcome and the prerequisite. Chosen from the distribution, not picked:
#: see the summary the script prints.
_TOOLTIP_MIN = 60


def _is_sentence(text: str) -> bool:
    """Prose, as opposed to a button label or a column heading."""
    return len(text) > 40 and (" " in text.strip())


def audit_catalogue(keys: "list[str]") -> "list[Finding]":
    out: list[Finding] = []
    for k in keys:
        if _PLURAL_DODGE.search(k):
            out.append(Finding(
                "plural-dodge", "must", k,
                "uses “(s)”. The rule is real singular and plural variants — "
                "“1 patch” / “2 patches” — chosen by the caller from the count."))
        if _HISTORY.search(k) and not _CONSEQUENCE.search(k):
            m = _HISTORY.search(k)
            out.append(Finding(
                "history-in-help", "must", k,
                f"says “{m.group(0)}”. Help text describes what is true now; a "
                "user cannot tell whether history applies to their version."))
        if _MARKDOWN.search(k):
            m = _MARKDOWN.search(k)
            out.append(Finding(
                "markdown-renders-literally", "must", k,
                f"contains “{m.group(0)}”. Qt message boxes are plain text, so "
                "the user sees the asterisks or backticks."))
        if _VAGUE_CONTROL.search(k):
            m = _VAGUE_CONTROL.search(k)
            out.append(Finding(
                "unnamed-control", "look", k,
                f"says “{m.group(0)}” without naming the control. The user has "
                "to guess which one, on a tab with many."))
        if _is_sentence(k):
            for term in _JARGON:
                if re.search(rf"\b{re.escape(term)}\b", k, re.I):
                    out.append(Finding(
                        "unexplained-jargon", "look", k,
                        f"uses “{term}” in prose. Beginners first: either "
                        "explain it in place or make sure it has a Dictionary "
                        "entry."))
                    break
    return out


def audit_parameters() -> "tuple[list[Finding], dict]":
    """parameters.yaml drives every tooltip in the UI, so it is audited directly."""
    try:
        import yaml
    except ImportError:
        print("PyYAML not available — skipping the parameter tooltips",
              file=sys.stderr)
        return [], {}
    data = yaml.safe_load(PARAMS.read_text())
    out: list[Finding] = []
    lengths: list[int] = []
    n = 0
    for tool, rows in (data.get("parameters") or {}).items():
        for row in rows or []:
            n += 1
            flag = row.get("flag", "?")
            title = (row.get("tooltip_title") or "").strip()
            body = (row.get("tooltip_body") or "").strip()
            if not body:
                out.append(Finding(
                    "tooltip-missing", "must", f"{tool} {flag} — {row.get('name','')}",
                    "has no tooltip_body at all, so the ⓘ explains nothing."))
                continue
            lengths.append(len(body))
            if len(body) < _TOOLTIP_MIN:
                out.append(Finding(
                    "tooltip-too-thin", "look",
                    f"{tool} {flag} — {row.get('name','')}: {body}",
                    f"the body is {len(body)} characters. That is a restated "
                    "label, not the outcome plus the prerequisite a beginner "
                    "needs."))
            if not title:
                out.append(Finding(
                    "tooltip-no-title", "look", f"{tool} {flag}",
                    "has a body but no tooltip_title."))
    stats = {"parameters": n, "bodies": len(lengths),
             "median_body": sorted(lengths)[len(lengths) // 2] if lengths else 0,
             "shortest": min(lengths) if lengths else 0}
    return out, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, help="write every finding to a CSV")
    ap.add_argument("--rule", help="show only this rule")
    args = ap.parse_args()

    cat = json.loads(CATALOGUE.read_text())
    keys = [k for k in cat if not k.startswith("@")]

    findings = audit_catalogue(keys)
    pf, stats = audit_parameters()
    findings += pf
    if args.rule:
        findings = [f for f in findings if f.rule == args.rule]

    print(f"Audited {len(keys)} catalogue strings and "
          f"{stats.get('parameters', 0)} parameter rows.")
    if stats:
        print(f"Tooltip bodies: {stats['bodies']}, median {stats['median_body']} "
              f"characters, shortest {stats['shortest']}.")
    print()

    by_rule: dict[str, list[Finding]] = {}
    for f in findings:
        by_rule.setdefault(f.rule, []).append(f)

    print(f"{'rule':30} {'severity':9} {'count':>6}")
    print("-" * 48)
    for rule, fs in sorted(by_rule.items(), key=lambda kv: -len(kv[1])):
        print(f"{rule:30} {fs[0].severity:9} {len(fs):6}")
    print(f"{'TOTAL':30} {'':9} {len(findings):6}")

    for rule, fs in sorted(by_rule.items(), key=lambda kv: -len(kv[1])):
        print(f"\n=== {rule} ({len(fs)}) — {fs[0].severity} ===")
        for f in fs[:40]:
            print(f"  • {f.short}")
            print(f"      {f.detail}")
        if len(fs) > 40:
            print(f"  … and {len(fs) - 40} more")

    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["rule", "severity", "text", "detail"])
            for f in findings:
                wr.writerow([f.rule, f.severity, f.text, f.detail])
        print(f"\nWrote {len(findings)} findings to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
