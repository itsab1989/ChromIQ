#!/usr/bin/env python3
"""Challenge round 3, second sweep: is there a spelling the guard STILL misses?

`probe_182_c3_capture_guard.py` attacked how the program NAME is held.  This
one attacks where the CALL sits: inside a lambda, a comprehension, a decorator,
a `try` body, an `except`, a `match` case, an async `with`, a nested function, a
method; and the shapes the argv itself can take: a tuple, `list(...)`, a dict
value, an f-string flag, `sudo` in front. It exists so "no others it did not
admit" is a measurement rather than a claim.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "tests" / "test_a_driver_photographs_the_window_not_the_screen.py"
spec = importlib.util.spec_from_file_location("capguard", GUARD)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
hit = mod._window_captures

MUST_CATCH = {
    "an f-string flag with the window id glued on":
        "import subprocess\nsubprocess.run(['screencapture', f'-l{wid}', out])\n",
    "an f-string program with no placeholder in it":
        "import subprocess\n"
        "subprocess.run([f'/usr/sbin/screencapture', '-R', r, out])\n",
    "inside a lambda assigned to a name":
        "import subprocess\n"
        "f = lambda: subprocess.run(['screencapture', '-R', r, out])\n",
    "inside a comprehension":
        "import subprocess\n"
        "[subprocess.run(['screencapture', '-R', r, out]) for r in rects]\n",
    "in a decorator argument":
        "@retry(cmd=['screencapture', '-R', r])\ndef shot():\n    pass\n",
    "a tuple argv rather than a list":
        "import subprocess\nsubprocess.run(('screencapture', '-R', r, out))\n",
    "list() wrapped round a tuple":
        "import subprocess\n"
        "subprocess.run(list(('screencapture', '-R', r, out)))\n",
    "the argv as a dict value":
        "CMDS = {'shot': ['screencapture', '-R', r, out]}\n",
    "inside a try body":
        "import subprocess\ntry:\n"
        "    subprocess.run(['screencapture', '-R', r, out])\n"
        "except OSError:\n    pass\n",
    "inside an except handler":
        "import subprocess\ntry:\n    pass\nexcept OSError:\n"
        "    subprocess.run(['screencapture', '-l', str(wid), out])\n",
    "inside a match case body":
        "match mode:\n    case 'w':\n"
        "        subprocess.run(['screencapture', '-R', r, out])\n",
    "inside an async with header":
        "async def go():\n"
        "    async with open_process(['screencapture', '-R', r]) as p:\n"
        "        pass\n",
    "inside a nested function":
        "def outer():\n    def inner():\n"
        "        subprocess.run(['screencapture', '-R', r, out])\n",
    "inside a method":
        "class S:\n    def go(self):\n"
        "        subprocess.run(['screencapture', '-l%d' % w, out])\n",
    "sudo in front of the program":
        "import subprocess\n"
        "subprocess.run(['sudo', 'screencapture', '-R', r, out])\n",
    "the program named only through an annotated assignment":
        "import subprocess\nPROG: str = 'screencapture'\n"
        "subprocess.run([PROG, '-R', r, out])\n",
}

MUST_ALLOW = {
    "the flag before the program, which makes the binary an ARGUMENT":
        "import subprocess\n"
        "subprocess.run(['ls', '-l', '/usr/sbin/screencapture'])\n",
    "an rsync of the folder the shots go in":
        "import subprocess\n"
        "subprocess.run(['rsync', '-R', str(src), str(dst)])\n",
    "a full-screen capture inside a comprehension":
        "import subprocess\n"
        "[subprocess.run(['screencapture', '-x', p]) for p in paths]\n",
    "prose in a decorator's own help text":
        "@click.option('--shot', help='never screencapture -R')\n"
        "def cmd():\n    pass\n",
    "a match case that only names the tool":
        "match tool:\n    case 'screencapture':\n"
        "        print('use -x for a whole screen')\n",
}


def main() -> int:
    bad = []
    print("### must be CAUGHT")
    for name, src in sorted(MUST_CATCH.items()):
        got = bool(hit(src))
        print(f"  {'ok  CAUGHT ' if got else '!!  MISSED '} {name}")
        if not got:
            bad.append(("missed", name))
    print("\n### must be ALLOWED")
    for name, src in sorted(MUST_ALLOW.items()):
        got = bool(hit(src))
        print(f"  {'!!  REFUSED' if got else 'ok  allowed'} {name}")
        if got:
            bad.append(("refused", name))
    print(f"\n{len(MUST_CATCH)} catch cases, {len(MUST_ALLOW)} allow cases, "
          f"{len(bad)} surprises: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
