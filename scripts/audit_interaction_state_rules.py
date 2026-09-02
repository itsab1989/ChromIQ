#!/usr/bin/env python3
"""Audit the colours in every INTERACTION-STATE stylesheet rule, from source.

    python scripts/audit_interaction_state_rules.py [ui ...]

WHY A SOURCE AUDIT AND NOT A CENSUS. `:hover` cannot be photographed in this
environment. `scripts/../hover_positive_control.py` proves it: a throwaway
button with `QPushButton:hover { background: #ff00ff }` stays grey under nine
techniques — a synthesised `QEnterEvent`, `WA_UnderMouse` (which
``underMouse()`` then reports as True), `QTest.mouseMove`, `QHoverEvent`, a
synchronous `repaint()`, and a real `QCursor.setPos` warp that provably lands
on the button, with and without the window activated. `:checked`, `:disabled`,
`:pressed` and `:focus` all paint in the same control, so the control is sound
and the gap is specific to hover.

A previous sweep reported "no hue on hover" from a technique in that failing
list. That is not a measurement, and a false zero is worse than a gap because
it closes the question. THIS is the instrument that can answer it: the rules are
in the source, so read the source.

WHAT IT REPORTS. Every `:hover` / `:pressed` / `:checked` / `:focus` /
`:selected` / `:disabled` rule in a Python stylesheet string, the colours it
sets, and whether those colours are hued. A hued value in a rule that the
Neutral appearance can reach is a hue nobody will see until they point at
something — which is exactly the class of miss this sweep exists to close.

The three appearance stylesheets (`ui/styles.py`, `ui/light_styles.py`,
`ui/neutral_styles.py`) are per-appearance by construction, so only
`neutral_styles.py` is read from that set; everything else in `ui/` is
appearance-agnostic unless it asks, and is read in full.
"""
from __future__ import annotations

import os
import re
import sys

#: The pseudo-states a person reaches by pointing, clicking, tabbing or
#: dragging — every one of them invisible to a census of a resting window.
STATES = ("hover", "pressed", "checked", "focus", "selected", "disabled",
          "on", "open", "active-hover")
_STATE_RE = re.compile(r":(" + "|".join(STATES) + r")\b")
_HEX_RE = re.compile(r"#([0-9a-fA-F]{6})\b")
_RGBA_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")

#: Only this one of the three appearance stylesheets applies to Neutral.
_APPEARANCE_SHEETS = ("ui/styles.py", "ui/light_styles.py")

#: A colour that arrives by NAME rather than as a literal — the thing a regex
#: over the line cannot see, and where most of these rules keep their hue.
_INTERP_RE = re.compile(r"\{[a-zA-Z_][\w.\[\]'\"()]*\}|%s|%\(")

#: The theme doors. A rule that interpolates a name is fine when one of these
#: stands between the name and the paint.
_DOORS = ("accent_for", "ink_for", "set_ink", "by_mode", "use_index_rule",
          "neutral_styles", "NM_", "APPEARANCE_NEUTRAL", "reapply_ink")


def chroma_hex(h: str) -> int:
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return max(r, g, b) - min(r, g, b)


def scan_file(path: str) -> list:
    """Every interaction-state rule in *path*, with the colours it sets."""
    out = []
    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            continue
        if not _STATE_RE.search(line):
            continue
        # A rule's declarations often run onto the following lines of a
        # concatenated string literal, so take a small window.
        window = "\n".join(lines[i - 1:i + 3])
        hues = []
        for m in _HEX_RE.finditer(window):
            c = chroma_hex(m.group(1))
            if c >= 8:
                hues.append(("#" + m.group(1), c))
        for m in _RGBA_RE.finditer(window):
            r, g, b = (int(m.group(k)) for k in (1, 2, 3))
            c = max(r, g, b) - min(r, g, b)
            if c >= 8:
                hues.append((f"rgb({r},{g},{b})", c))
        # THE BLIND SPOT OF A SOURCE AUDIT, CLOSED. Most of these rules do not
        # carry a literal at all: they interpolate a name — `{accent}`,
        # `%s` % _TAB_COLOR — and a regex over the line then sees no colour and
        # reports a clean bill on a rule that paints the Measure tab's green.
        # So an interpolated rule is recorded too, with whether a theme door
        # appears anywhere near it. "No literal and no door" is the finding,
        # not the absence of one.
        interpolated = bool(_INTERP_RE.search(window))
        # A door can be several lines above the rule — the value is usually
        # resolved once at the top of the method and interpolated below — so
        # follow the NAME rather than reading a fixed window: if the identifier
        # this rule interpolates is assigned from a door anywhere in the file,
        # the rule is covered.
        near = "\n".join(lines[max(0, i - 10):i + 4])
        door = sorted({d for d in _DOORS if d in near})
        if not door:
            for m in re.finditer(r"\{([a-zA-Z_]\w*)", window):
                name = m.group(1)
                assign = re.search(
                    rf"^\s*(self\.)?_?{re.escape(name)}\s*=.*$", text,
                    re.MULTILINE)
                if assign and any(d in assign.group(0) for d in _DOORS):
                    door.append(f"{name}<-{assign.group(0).strip()[:60]}")
        states = sorted({m.group(1) for m in _STATE_RE.finditer(line)})
        out.append(dict(file=path, line=i, states=states, hues=hues,
                        interpolated=interpolated, door=door,
                        text=line.strip()[:150]))
    return out


def main(roots) -> int:
    rows = []
    for root in roots:
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in ("__pycache__",)]
            for f in sorted(fn):
                if not f.endswith(".py"):
                    continue
                p = os.path.join(dp, f)
                if any(p.endswith(s) for s in _APPEARANCE_SHEETS):
                    continue          # Light/Dark only, by construction
                rows += scan_file(p)

    hued = [r for r in rows if r["hues"]]
    blind = [r for r in rows
             if not r["hues"] and r["interpolated"] and not r["door"]]
    print(f"interaction-state rules found: {len(rows)}")
    print(f"  ...setting a HUED literal:            {len(hued)}")
    print(f"  ...interpolating a name, NO door:     {len(blind)}\n")
    by_state: dict = {}
    for r in rows:
        for s in r["states"]:
            by_state.setdefault(s, [0, 0, 0])
            by_state[s][0] += 1
            if r["hues"]:
                by_state[s][1] += 1
            if r in blind:
                by_state[s][2] += 1
    for s, (n, h, b) in sorted(by_state.items()):
        print(f"  :{s:<13} {n:4d} rules, {h:3d} hued literal, "
              f"{b:3d} interpolated with no door")
    if hued:
        print("\nRULES THAT PAINT A HUED LITERAL IN AN INTERACTION STATE:")
        for r in sorted(hued, key=lambda r: (-max(c for _v, c in r["hues"]),
                                             r["file"])):
            vals = ", ".join(f"{v} (c={c})" for v, c in r["hues"][:4])
            print(f"  {r['file']}:{r['line']}  :{'/'.join(r['states'])}")
            print(f"      {vals}")
            print(f"      {r['text']}")
    if blind:
        print("\nRULES WHOSE COLOUR ARRIVES BY NAME, WITH NO THEME DOOR NEAR IT")
        print("(a regex cannot see what these paint — read each one):")
        for r in blind:
            print(f"  {r['file']}:{r['line']}  :{'/'.join(r['states'])}"
                  f"  {r['text']}")
    return 1 if (hued or blind) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["ui"]))
