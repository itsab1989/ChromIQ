#!/usr/bin/env python3
"""Write the built-in presets' metric certificates (#182, Knut 6045500910,
answer 5). RUN AT EVERY RELEASE, after the version bump:

    python scripts/make_preset_certificates.py          # writes the file
    python scripts/make_preset_certificates.py --check  # exit 1 if stale

For every built-in Create Chart preset it works out, from scratch, which of
the report's metrics the preset's chart can answer
(`workflow.preset_eligibility.chart_row_values`, laid out as the presets
window lays it out), and stores that answer keyed by the preset's hash and
this ChromIQ's version in ``data/preset_certificates.json``. The installed app
then reads the answer instead of laying the chart out again; a preset whose
hash or version does not match is worked out as before.

Built-in recipes depend on one setting ("i1Pro: ChromIQ clip style"), so both
of its values are certified. Settings are sandboxed: nothing here reads or
writes the user's preferences.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_SANDBOX = tempfile.TemporaryDirectory(prefix="chromiq-certificates-")
os.environ.setdefault("CHROMIQ_SETTINGS_FILE",
                      str(Path(_SANDBOX.name) / "settings.ini"))
os.environ.setdefault("CHROMIQ_PRESETS_DIR", str(Path(_SANDBOX.name) / "presets"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

OUT = ROOT / "data" / "preset_certificates.json"

#: The settings a built-in preset's recipe reads.
_VARIANTS = ({"i1pro_chromiq_clip_style": False},
             {"i1pro_chromiq_clip_style": True})


def build() -> dict:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from core.settings import AppSettings
    from ui.tabs.tab_chart import verification_preset_rows
    from workflow import preset_certificates as PC
    from workflow import preset_eligibility as PE
    PC.set_disabled(True)             # never certify from a certificate
    settings = AppSettings()
    certs: dict = {}
    t0 = time.monotonic()
    for variant in _VARIANTS:
        for k, v in variant.items():
            settings.set(k, v)
        PE.clear_cache()
        for row in verification_preset_rows(settings):
            if not row.builtin or row.chart is None:
                continue
            digest = PC.preset_hash(row.chart, row.recipe)
            if digest in certs:
                continue
            try:
                values = PE.chart_row_values(row.chart, row.recipe, lay_out=True)
            except Exception as exc:      # noqa: BLE001
                print(f"  {row.key}: cannot be checked ({exc})", file=sys.stderr)
                continue
            values = json.loads(json.dumps(values))
            answered = sorted(r for r, c in values.items()
                              if isinstance(c, dict) and c.get("value") is not None)
            certs[digest] = {"preset": row.key, "label": row.label,
                             "answered": len(answered), "values": values}
    print(f"{len(certs)} certificates in {time.monotonic() - t0:.1f} s")
    return {"code_version": PC.code_version(),
            "note": "Written by scripts/make_preset_certificates.py at release "
                    "time; see workflow/preset_certificates.py.",
            "certificates": dict(sorted(certs.items()))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when the shipped file is not what this "
                         "ChromIQ would write")
    args = ap.parse_args()
    data = build()
    if args.check:
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = {}
        same = (old.get("code_version") == data["code_version"]
                and old.get("certificates") == data["certificates"])
        print("certificates are current" if same else
              "certificates are STALE: run scripts/make_preset_certificates.py")
        return 0 if same else 1
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
