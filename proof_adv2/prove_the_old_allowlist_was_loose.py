"""Show that the SAME mutation walked past the allowlist as it was written.

Puts the old, seven-number allowlist back into the test, applies the mutation
that the tightened test now kills, and runs the file.  Restores both files.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = "/Users/Basti/develop/ChromIQ/.venv/bin/python"

NEW_LIST = '''    allowed = {round(float(lim.number), 6)
               for lim in cs._CHROMIQ_FACTORY["chromiq_default"].values()
               if lim.is_numeric}
    assert allowed, "ChromIQ default's own factory numbers could not be read"'''
OLD_LIST = '''    allowed = set()
    for table in cs._CHROMIQ_FACTORY.values():
        for lim in table.values():
            if lim.is_numeric:
                allowed.add(round(float(lim.number), 6))
    assert allowed, "ChromIQ's own factory numbers could not be read"'''

MUT_OLD = '"cmy_solids_dhab_max": Limit.value(2.0),         # ΔH*ab'
MUT_NEW = '"cmy_solids_dhab_max": Limit.value(4.0),         # ΔH*ab'


def main() -> int:
    t = ROOT / "tests/test_compliance_sets.py"
    c = ROOT / "workflow/compliance_sets.py"
    told, cold = t.read_text(encoding="utf-8"), c.read_text(encoding="utf-8")
    assert NEW_LIST in told and MUT_OLD in cold
    t.write_text(told.replace(NEW_LIST, OLD_LIST), encoding="utf-8")
    c.write_text(cold.replace(MUT_OLD, MUT_NEW), encoding="utf-8")
    try:
        r = subprocess.run(
            [PY, "-m", "pytest", "tests/test_compliance_sets.py", "-q",
             "--no-header"], cwd=ROOT, capture_output=True, text=True,
            timeout=600, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()][-2:]
        print("OLD allowlist + the 4.0 placeholder -> exit", r.returncode)
        print("   ", lines)
        print("VERDICT:", "the old test DID NOT see it" if r.returncode == 0
              else "the old test caught it")
        return 0 if r.returncode == 0 else 1
    finally:
        t.write_text(told, encoding="utf-8")
        c.write_text(cold, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
