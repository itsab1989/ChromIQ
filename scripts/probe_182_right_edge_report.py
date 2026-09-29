#!/usr/bin/env python3
"""Print the K1 / K5 measurement JSON in a readable shape (no app, no window)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path.home() / "Desktop" / "chromiq-182-right-edge"


def main() -> int:
    d = json.loads((OUT / "k1-k5.json").read_text(encoding="utf-8"))
    want = sys.argv[1] if len(sys.argv) > 1 else "both"
    for phase in ("k1", "k5"):
        if phase not in d or want not in (phase, "both"):
            continue
        print(f"\n########## {phase.upper()} ##########")
        for s in d[phase]["states"]:
            print("=" * 74)
            print(s["tag"], {k: v for k, v in s.items()
                             if k in ("clip_width_typed", "right_margin_typed",
                                      "clip_pt", "note_pt", "note")})
            for c in s.get("calls", []):
                print("  CALL", c["fn"], c.get("args"), c.get("kwargs"),
                      "->", c.get("result"))
            for c in s.get("stamp_calls", []):
                print("  STAMP", c.get("text"), c.get("args"), c.get("kwargs"))
            for w in s.get("overlap_warnings", []):
                print("  WARN >>", w)
            for p in s.get("ink", []):
                print(f"  page {Path(p['file']).name}  {p['w']}x{p['h']} "
                      f"@{p['dpi']} dpi")
                for g in p["right_groups"]:
                    print("    band mm from right edge "
                          f"{g['mm_from_right_outer']:7.3f} .. "
                          f"{g['mm_from_right_inner']:7.3f}   "
                          f"w={g['width_px']:4d}px ink={g['ink_px']:7d} "
                          f"rows={g['row_span_mm']}mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
