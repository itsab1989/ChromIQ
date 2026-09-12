"""Show the grep version of the always-built check could not see the fault.

Puts the old body back into `test_every_block_in_the_list_really_is_always_built`
and adds a CONDITIONAL block to `ALWAYS_BUILT_BLOCKS`; the old test passes.
Restores both files.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = "/Users/Basti/develop/ChromIQ/.venv/bin/python"
TEST = ("tests/test_a_row_that_was_never_computed_is_rebuilt.py"
        "::test_every_block_in_the_list_really_is_always_built")

OLD_BODY = '''    import inspect

    from ui.dialogs.measurement_report_dialog import ALWAYS_BUILT_BLOCKS
    from workflow import measurement_report as mr
    src = inspect.getsource(mr.build_report)
    for key in ALWAYS_BUILT_BLOCKS:
        assert f'report["{key}"]' in src, (
            f"{key!r} is in ALWAYS_BUILT_BLOCKS but build_report never "
            f"writes it, so every saved report would be stale for ever")
'''

TUPLE_OLD = ('ALWAYS_BUILT_BLOCKS: "tuple[str, ...]" = ("grey_balance", '
             '"ramps_30_70",\n'
             '                                          "summary_patches")')
TUPLE_NEW = ('ALWAYS_BUILT_BLOCKS: "tuple[str, ...]" = ("grey_balance", '
             '"ramps_30_70",\n'
             '                                          "summary_patches",\n'
             '                                          "gamut_split")')


def main() -> int:
    t = ROOT / "tests/test_a_row_that_was_never_computed_is_rebuilt.py"
    d = ROOT / "ui/dialogs/measurement_report_dialog.py"
    told, dold = t.read_text(encoding="utf-8"), d.read_text(encoding="utf-8")
    # swap the whole function body back to the grep form
    head = "def test_every_block_in_the_list_really_is_always_built(tmp_path):\n"
    i = told.index(head)
    j = told.index("\ndef test_a_current_report_is_left_alone", i)
    tnew = told[:i] + head + '    """the grep version"""\n' + OLD_BODY + told[j:]
    assert TUPLE_OLD in dold
    t.write_text(tnew, encoding="utf-8")
    d.write_text(dold.replace(TUPLE_OLD, TUPLE_NEW), encoding="utf-8")
    try:
        r = subprocess.run([PY, "-m", "pytest", TEST, "-q", "--no-header"],
                           cwd=ROOT, capture_output=True, text=True,
                           timeout=600,
                           env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
        print("GREP version + a conditional block in the list -> exit",
              r.returncode)
        print("   ", [ln for ln in r.stdout.splitlines() if ln.strip()][-2:])
        print("VERDICT:", "the grep version DID NOT see it" if r.returncode == 0
              else "the grep version caught it")
        return 0 if r.returncode == 0 else 1
    finally:
        t.write_text(told, encoding="utf-8")
        d.write_text(dold, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
