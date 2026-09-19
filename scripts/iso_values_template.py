#!/usr/bin/env python3
"""Write a file a licence holder can fill in with ISO 12647 tolerance values.

Knut asked for the standards' limits listed in a table, in the order the Report
limits window draws its metrics. The values cannot come from ChromIQ: they are
the content of a paid standard, this repository published those tables once by
accident already, and DIN answered in writing on 2026-09-18 that putting them
into software is licensed at 50 % of the standard's purchase price.

Everything except the numbers can be given, and that is most of what the
question was after: which rows each standard writes a limit over, in the
window's own order, ready to fill in from a copy the reader owns.

    python scripts/iso_values_template.py [-o iso12647.json] [--set iso_12647_7]

Then fill in the nulls and point ChromIQ at the file:

    export CHROMIQ_COMPLIANCE_ISO_FILE=/path/to/your/iso12647.json

The numbers stay on the machine of somebody licensed to have them, which is the
only place they can be. ChromIQ's own repository stays empty of them.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workflow.compliance_sets import iso_values_template  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default="",
                    help="write here instead of standard output")
    ap.add_argument("--set", dest="set_id", default="",
                    choices=["", "iso_12647_7", "iso_12647_8"],
                    help="only one of the two sets")
    args = ap.parse_args(argv)
    text = iso_values_template(args.set_id or None)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"written to {args.out}")
        print("Fill in the nulls from your own copy of the standard, then:")
        print(f"  export CHROMIQ_COMPLIANCE_ISO_FILE={Path(args.out).resolve()}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
