#!/usr/bin/env python3
"""Build a release note a user can actually scan, from CHANGELOG.md.

Knut, beta.139: *"the release note must give a great overview of all added
features, and the list of bugfixes must be shown in a comprehensive manner so
that users can recognise if a bug they have been annoyed by has been fixed."*

Two things follow from that, and both are the point of this script.

**A fix has to be findable by its symptom.** Somebody who lost a measurement
does not search for "the give-up prompt arrives as an event"; they search for
"Save and stop". So every fixed entry leads with what you would have noticed,
and explains the cause afterwards.

**One release, or a whole line of them.** ``--tag v3.14.8-beta.140`` renders one
version. ``--since v3.14.7`` folds every version after that tag into a single
note, merging their sections — which is what a 4.0.0 announcement needs after a
hundred-odd betas nobody wants listed one by one.

    python scripts/release_notes.py --tag v3.14.8-beta.140
    python scripts/release_notes.py --since v3.14.7 --title "ChromIQ 4.0.0"

Section headings in CHANGELOG.md are optional; an entry with no headings is
treated as one undifferentiated list and still renders, so nothing older breaks.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"

#: The sections a release note is built from, in the order a reader wants them:
#: what is new first (that is why they are upgrading), then what is fixed (that
#: is what they were waiting for), then the small print.
SECTIONS: "list[tuple[str, str, str]]" = [
    ("new", "New", "✨ What's new"),
    ("changed", "Changed", "🔁 Changed"),
    ("fixed", "Fixed", "🔧 Fixed"),
    # A release can be documentation only — the #130 specifications are worked
    # on in their own right. Without this the section is written, passes review
    # and then renders as nothing at all: the reader sees an empty release.
    ("docs", "Documentation", "📘 Documentation"),
    # Groundwork with nothing on screen yet still has to render, for the same
    # reason Documentation does: a release whose only section is unknown to
    # this table renders as an empty page.
    ("internal", "Internal", "🔧 Under the hood"),
    ("known", "Known issues", "⚠️ Known issues"),
]
SECTION_BY_KEY = {k: (md, pretty) for k, md, pretty in SECTIONS}


def _versions() -> "list[tuple[str, list[str]]]":
    """[(version-heading, body-lines)] in the order CHANGELOG.md lists them."""
    out: "list[tuple[str, list[str]]]" = []
    cur: "str | None" = None
    body: "list[str]" = []
    for line in CHANGELOG.read_text().splitlines():
        m = re.match(r"^## (\S+)\s*$", line)
        if m:
            if cur is not None:
                out.append((cur, body))
            cur, body = m.group(1), []
            continue
        if cur is not None:
            body.append(line)
    if cur is not None:
        out.append((cur, body))
    return out


def _normalise(tag: str) -> str:
    """CHANGELOG headings are written with or without the leading ``v``."""
    return tag[1:] if tag.startswith("v") else tag


def split_sections(body: "list[str]") -> "dict[str, list[str]]":
    """Split one version's body into the known sections.

    Anything before the first recognised heading — or a whole entry with no
    headings at all, which is every entry written before this script — lands in
    ``fixed``, because that is what those entries have always been.
    """
    known = {md.lower(): key for key, md, _ in SECTIONS}
    out: "dict[str, list[str]]" = {key: [] for key, _, _ in SECTIONS}
    cur = "fixed"
    for line in body:
        m = re.match(r"^###\s+(?:[^\w\s]*\s*)?(.+?)\s*$", line)
        if m:
            name = re.sub(r"^[^A-Za-z]+", "", m.group(1)).strip().lower()
            if name in known:
                cur = known[name]
                continue
        out[cur].append(line)
    return out


def _tidy(lines: "list[str]") -> "list[str]":
    """Drop leading/trailing blank lines, collapse runs of them."""
    out: "list[str]" = []
    for line in lines:
        if not line.strip():
            if out and out[-1].strip():
                out.append("")
            continue
        out.append(line.rstrip())
    while out and not out[-1].strip():
        out.pop()
    return out


def _count_entries(lines: "list[str]") -> int:
    return sum(1 for ln in lines if re.match(r"^\s*[-*]\s+", ln))


def build(tags: "list[str]", title: str) -> str:
    """Render one note from one or more CHANGELOG versions."""
    merged: "dict[str, list[str]]" = {key: [] for key, _, _ in SECTIONS}
    seen: "list[str]" = []
    by_version = {_normalise(v): b for v, b in _versions()}
    for tag in tags:
        body = by_version.get(_normalise(tag))
        if body is None:
            continue
        seen.append(tag)
        for key, lines in split_sections(body).items():
            merged[key].extend(lines)

    if not seen:
        raise SystemExit(
            f"No CHANGELOG.md entry for {', '.join(tags)} — nothing to render.")

    fixed_n = _count_entries(merged["fixed"])
    new_n = _count_entries(merged["new"]) + _count_entries(merged["changed"])
    docs_n = _count_entries(merged["docs"])
    internal_n = _count_entries(merged["internal"])

    parts = [f"## {title}", ""]
    # The overview: what this release is, in one honest sentence, before any
    # list. A reader deciding whether to update reads this and nothing else.
    bits = []
    if new_n:
        bits.append(f"**{new_n} new or changed "
                    f"{'thing' if new_n == 1 else 'things'}**")
    if fixed_n:
        bits.append(f"**{fixed_n} fixed "
                    f"{'problem' if fixed_n == 1 else 'problems'}**")
    # Counted too, so a documentation-only release still gets an opening
    # sentence instead of a blank line where the summary should be.
    if docs_n:
        bits.append(f"**{docs_n} documentation "
                    f"{'update' if docs_n == 1 else 'updates'}**")
    if internal_n:
        bits.append(f"**{internal_n} internal "
                    f"{'change' if internal_n == 1 else 'changes'}**")
    if len(seen) > 1:
        span = f"{seen[-1]} … {seen[0]}"
        parts.append(f"Everything from {span}, folded into one list — "
                     + " and ".join(bits) + ".")
    elif bits:
        parts.append(" and ".join(bits) + " in this release.")
    parts.append("")

    for key, _, pretty in SECTIONS:
        lines = _tidy(merged[key])
        if not lines:
            continue
        parts += [f"### {pretty}", ""] + lines + [""]

    if fixed_n:
        parts += [
            "*Every fixed entry above starts with what you would have noticed, "
            "so you can find the one that was bothering you without knowing "
            "what caused it.*", ""]
    return "\n".join(parts).rstrip() + "\n"


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--tag", help="render this one version")
    g.add_argument("--since", help="fold in every version newer than this tag")
    ap.add_argument("--title", help="heading for the note (default: the tag)")
    args = ap.parse_args(argv)

    versions = [v for v, _ in _versions()]
    if args.tag:
        tags = [args.tag]
        title = args.title or args.tag
    else:
        stop = _normalise(args.since)
        tags = []
        for v in versions:                     # newest first in the file
            if _normalise(v) == stop:
                break
            tags.append(v)
        title = args.title or f"Changes since {args.since}"

    sys.stdout.write(build(tags, title))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
