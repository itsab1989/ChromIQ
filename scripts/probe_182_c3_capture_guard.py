#!/usr/bin/env python3
"""Challenge round 3: attack `_window_captures`, the capture guard.

Runs a matrix of spellings through the guard the test file itself uses, so the
probe measures the shipped function rather than a copy of it. Two questions:

* which real window captures does it still MISS, beyond the five it admits to
* which legitimate lines does it still REFUSE, beyond the one kept on purpose

It also re-verifies every admitted gap is really blind, and reports which files
the guard's scan actually reaches.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "tests" / "test_a_driver_photographs_the_window_not_the_screen.py"
spec = importlib.util.spec_from_file_location("capguard", GUARD)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
hit = mod._window_captures


# --- real window captures the guard should refuse -------------------------
CANDIDATE_CATCH = {
    "shutil.which finds the binary":
        "import shutil, subprocess\n"
        "prog = shutil.which('screencapture')\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "os.path.join builds the path":
        "import os, subprocess\n"
        "prog = os.path.join('/usr/sbin', 'screencapture')\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "Path() wraps the binary":
        "import subprocess\nfrom pathlib import Path\n"
        "prog = Path('/usr/sbin/screencapture')\n"
        "subprocess.run([str(prog), '-l', str(wid), out])\n",
    "a conditional picks the binary":
        "import subprocess\n"
        "prog = 'screencapture' if plain else '/usr/sbin/screencapture'\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "the program is a function default":
        "import subprocess\n"
        "def shot(rect, out, prog='screencapture'):\n"
        "    subprocess.run([prog, '-R', rect, out])\n",
    "the program is a keyword-only default":
        "import subprocess\n"
        "def shot(rect, out, *, prog='screencapture'):\n"
        "    subprocess.run([prog, '-l', str(wid), out])\n",
    "an alias of an alias":
        "import subprocess\n"
        "SCREENCAP = 'screencapture'\nPROG = SCREENCAP\n"
        "subprocess.run([PROG, '-R', rect, out])\n",
    "the program comes from a dict":
        "import subprocess\n"
        "TOOLS = {'shot': 'screencapture'}\n"
        "subprocess.run([TOOLS['shot'], '-R', rect, out])\n",
    "the program comes from a tuple unpack":
        "import subprocess\n"
        "prog, = ('screencapture',)\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "an augmented assignment builds the name":
        "import subprocess\n"
        "prog = 'screen'\nprog += 'capture'\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "the program is a class attribute":
        "import subprocess\n"
        "class Shot:\n    PROG = 'screencapture'\n"
        "subprocess.run([Shot.PROG, '-R', rect, out])\n",
    "the flag is a function default":
        "import subprocess\n"
        "def shot(rect, out, flag='-R'):\n"
        "    subprocess.run(['screencapture', flag, rect, out])\n",
    "the program returned by a helper, never a literal":
        "import subprocess\nprog = get_tool()\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "a walrus in the call":
        "import subprocess\n"
        "subprocess.run([(prog := 'screencapture'), '-R', rect, out])\n",
    "os.execvp":
        "import os\nos.execvp('screencapture', ['screencapture', '-R', rect, out])\n",
    "a locally aliased flag inside a with header":
        "import subprocess\n"
        "def go():\n    RECT = '-R'\n"
        "    with subprocess.Popen(['screencapture', RECT, rect]) as p:\n"
        "        p.wait()\n",
}

# --- legitimate lines the guard should allow ------------------------------
CANDIDATE_ALLOW = {
    "listing the binary with ls -l":
        "import subprocess\n"
        "subprocess.run(['ls', '-l', '/usr/sbin/screencapture'])\n",
    "copying a tree next to a full-screen shot":
        "import subprocess\n"
        "subprocess.run(['cp', '-R', str(src), str(dst)])\n"
        "subprocess.run(['screencapture', '-x', out])\n",
    "a table of commands, one of them a full screen":
        "CMDS = {\n"
        "    'shot': ['screencapture', '-x', 'out.png'],\n"
        "    'copy': ['cp', '-R', 'a', 'b'],\n"
        "}\n",
    "a for over two unrelated commands":
        "import subprocess\n"
        "for cmd in (['screencapture', '-x', out], ['ls', '-l', out]):\n"
        "    subprocess.run(cmd)\n",
    "chmod -R reaching the binary's folder":
        "import subprocess\n"
        "subprocess.run(['chmod', '-R', '755', '/usr/sbin/screencapture'])\n",
    "a docstring naming the binary path and a flag":
        '"""We never call /usr/sbin/screencapture with -R here."""\n',
    "an argparse -l whose default mentions the tool":
        "p.add_argument('-l', '--log', default='screencapture.log')\n",
    "a comment beside a cp -R":
        "import subprocess\n"
        "subprocess.run(['cp', '-R', a, b])  # then capture_window, not screencapture -R\n",
    "a full-screen capture chained with a recursive copy":
        "import subprocess\n"
        "subprocess.run(['screencapture', '-x', out], check=True) and \\\n"
        "    subprocess.run(['cp', '-R', out, dst])\n",
    "prose listing the two dead ends as a sentence":
        "print('neither screencapture -l nor screencapture -R works here')\n",
    "a match statement over tool names":
        "match tool:\n"
        "    case 'screencapture':\n"
        "        print('use -x for a whole screen')\n",
    "a settings dict with the tool and an rsync flag":
        "OPTS = {'tool': 'screencapture', 'rsync': '-R'}\n",
}


def report(title, cases, want_hit):
    print(f"\n### {title}")
    surprises = {}
    for name, src in sorted(cases.items()):
        got = bool(hit(src))
        ok = got == want_hit
        mark = "ok " if ok else "!! "
        print(f"  {mark}{'CAUGHT ' if got else 'MISSED '} {name}")
        if not ok:
            surprises[name] = src
    return surprises


def main() -> int:
    print("guard under test:", GUARD.relative_to(ROOT))

    print("\n### admitted gaps, re-verified blind")
    for name, src in sorted(mod._KNOWN_BLIND.items()):
        got = bool(hit(src))
        print(f"  {'!! NOW CAUGHT' if got else 'ok  still blind'}  {name}")

    print("\n### the guard's own must-catch / must-allow, re-run")
    bad = 0
    for name, src in sorted(mod._MUST_CATCH.items()):
        if not hit(src):
            print(f"  !! must-catch fails: {name}")
            bad += 1
    for name, src in sorted(mod._MUST_ALLOW.items()):
        if hit(src):
            print(f"  !! must-allow fails: {name}")
            bad += 1
    print(f"  {len(mod._MUST_CATCH)} must-catch, {len(mod._MUST_ALLOW)} "
          f"must-allow, {bad} disagreements")

    missed = report("real window captures: should be CAUGHT",
                    CANDIDATE_CATCH, True)
    refused = report("legitimate lines: should be ALLOWED",
                     CANDIDATE_ALLOW, False)

    print("\n### which files the guard actually scans")
    files = mod._driver_files()
    print(f"  {len(files)} files under scripts/")
    subdirs = sorted({p.parent.relative_to(mod.SCRIPTS).as_posix()
                      for p in files if p.parent != mod.SCRIPTS})
    print(f"  subdirectories reached: {subdirs}")
    print(f"  the one exempt file: {mod.HELPER.relative_to(ROOT)} "
          f"(by PATH; a same-named file in a subdirectory is still scanned)")

    out = {"missed_but_should_catch": sorted(missed),
           "refused_but_legitimate": sorted(refused)}
    print("\n" + json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
