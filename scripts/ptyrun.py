#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run a console program in a pseudo-terminal, answer its questions in turn, keep a transcript.

For testing a console tester program (docs/adding_an_instrument.md, section 12b, step 3) the
way a volunteer uses it: the program sees a real terminal of a given size, and every answer is
typed only after the question it belongs to has appeared. No window, no focus, no keyboard is
taken. macOS and Linux (it needs the `pty` module).

    from ptyrun import run
    text, code, unanswered = run(["python3", "my_tester.py", "--simulate"],
                                 [("Type yes to run it", "yes\\n"), ("Did it do", "^C")],
                                 cols=80, timeout=300, transcript="session.txt")

answers: (text, reply) pairs, each used once, in order: a reply is sent when its text has
appeared in the output after the previous answer. "^C" sends Ctrl-C. Returns the whole output,
the exit code ("TIMEOUT" when it had to be stopped) and the questions never seen.

    python scripts/ptyrun.py --demo     # a tiny program that asks two questions, answered
"""
from __future__ import annotations

import os
import select
import signal
import struct
import sys
import time


def run(cmd, answers=(), cols=120, rows=40, timeout=300, cwd=None, env=None, transcript=None):
    import fcntl
    import pty
    import termios
    pid, fd = pty.fork()
    if pid == 0:
        # a harness started in the background has SIGINT ignored, and the child would inherit
        # that: Ctrl-C cases would then hang
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        if cwd:
            os.chdir(cwd)
        os.execvpe(cmd[0], cmd, env or os.environ)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    out, mark, todo = b"", 0, list(answers)
    end = time.time() + timeout
    code = None
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.3)
        if r:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                chunk = b""
            if not chunk:
                break
            out += chunk
        text = out.decode("utf-8", "replace")
        if todo and todo[0][0] in text[mark:]:
            want, reply = todo.pop(0)
            mark = text.index(want, mark) + len(want)
            time.sleep(0.4)                      # a person reads the question first
            os.write(fd, b"\x03" if reply == "^C" else reply.encode())
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            code = os.waitstatus_to_exitcode(status)
            while True:                          # drain what is left
                r, _, _ = select.select([fd], [], [], 0.3)
                if not r:
                    break
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk
            break
    else:
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)
        code = "TIMEOUT"
    if code is None:                             # the output ended first: wait for the exit
        for _ in range(100):
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                code = os.waitstatus_to_exitcode(status)
                break
            time.sleep(0.1)
    os.close(fd)
    text = out.decode("utf-8", "replace").replace("\r\n", "\n")
    if transcript:
        with open(transcript, "w", encoding="utf-8") as fh:
            fh.write(text)
    return text, code, [a for a, _ in todo]


DEMO = ("a = input('Type yes to run it: ')\n"
        "print('you typed', a)\n"
        "b = input('Did it do what was described? ')\n"
        "print('answer:', b)\n")


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="run a tiny two-question program")
    a = ap.parse_args(argv)
    if not a.demo:
        ap.print_help()
        return 0
    text, code, left = run([sys.executable, "-c", DEMO],
                           [("Type yes to run it", "yes\n"),
                            ("Did it do what was described?", "as described\n")], timeout=60)
    print(text)
    print(f"exit code {code}; questions never seen: {left or 'none'}")
    return 0 if code == 0 and not left else 1


if __name__ == "__main__":
    sys.exit(main())
