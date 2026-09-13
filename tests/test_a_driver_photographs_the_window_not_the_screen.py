"""A driver may not roll its own window capture, and may not give up on a lock.

Basti, 2026-09-13: *"so this will work in the future in other sessions
automatically as well?"*, after a round wrote "the screen is locked, so there
are no photographs" and stopped.

Fixing `scripts/onscreen_capture.py` makes it work for every driver that CALLS
it. It does nothing about the next driver, written from scratch, that shells
out to `screencapture` on its own and rediscovers the same two dead ends. This
file is the part that is actually automatic.

**The two dead ends, measured on macOS 15.6 with Screen Recording granted:**

* `screencapture -R <rect>` copies a RECTANGLE OF THE SCREEN. A window this
  process opened without stealing focus is not composited on the Space being
  captured, so the rectangle comes back as wallpaper. `win.raise_()` cannot fix
  it and neither can `NSRunningApplication.activateWithOptions_`, which returns
  True while `isActive` stays False.
* `screencapture -l <window id>` exits 1 with "could not create image from
  window". CLAUDE.md blamed that string on the missing permission grant; it
  survives the grant.

Only `CGWindowListCreateImage` works, and it lives in one place.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
HELPER = SCRIPTS / "onscreen_capture.py"

def _driver_files() -> list[Path]:
    # Excluded by PATH, not by basename: `scripts/anything/onscreen_capture.py`
    # is a different file and gets no exemption from the one shared helper.
    return [p for p in sorted(SCRIPTS.rglob("*.py"))
            if p != HELPER and "__pycache__" not in p.parts]


#: A string literal that IS the program, rather than prose mentioning it.
_PROGRAM = re.compile(r"^(?:.*/)?screencapture$")

#: A string literal that IS a window flag: `-R`, `-l`, or `-l` with the id
#: glued on (`-l42`, `-l%d`), which `screencapture` also accepts.
_WINDOW_FLAG = re.compile(r"^-(?:R|l)(?:\b|\d|$)")


def _window_captures(src: str) -> list[tuple[int, str]]:
    """Every STATEMENT that runs `screencapture` with `-l` or `-R`.

    **THIS GUARD HAS NOW BEEN WRONG THREE TIMES, IN BOTH DIRECTIONS, AND THE
    THIRD IS WHY IT NO LONGER READS SOURCE TEXT AT ALL.**

    * Version one read raw lines and failed on a DOCSTRING explaining the rule.
      Prose about `screencapture -R` is the fix written down, not the fault.
    * Version two skipped every line covered by a string literal and then let a
      real ``subprocess.run(['screencapture', '-R', ...])`` through, because a
      call like that IS string literals.
    * Version three asked the tree for CALLS and then grepped their source
      text, which brought both failures back at once. Measured 2026-09-13:

      - it MISSED the most ordinary way of writing the call, and three more::

            cmd = ['screencapture', '-R', rect, str(path)]   # one statement
            subprocess.run(cmd)                              # the next

        The call node's source is ``subprocess.run(cmd)``, which says nothing
        about screencapture. Putting the program in a constant
        (``SCREENCAP = 'screencapture'``) hid it the same way.
      - and it REFUSED five legitimate lines, every one of them a driver
        explaining the rule inside a call: a ``print``, a ``log.info``, an
        argparse ``help=``, a ``raise SystemExit``, and a comment sitting
        inside the parentheses of the `capture_window` call that replaced it.
        `ast.get_source_segment` hands back the comment along with the code.

    So this looks at STRING LITERALS in the tree, never at source text. A
    statement is an offence when it contains a literal that IS the program
    (``screencapture``, or a path ending in it) together with a literal that IS
    a window flag. Prose fails the first test: ``'screencapture -R returns the
    desktop'`` is one literal and it is not the program's name. A comment is
    not in the tree at all. A module-level ``NAME = 'screencapture'`` is
    followed, because hiding the program in a constant is not a defence, and so
    is ``FLAG = '-R'``: the same trick on the other half of the pair.

    **AND VERSION FOUR WAS BLIND TO A `with` AND AN `if`, WHICH IS WHERE
    ANYBODY PUTS A SUBPROCESS.** Measured 2026-09-13, second challenge round.
    It walked the tree for statements and then skipped every compound one
    outright, on the sound reasoning that a ``With`` node's source contains its
    whole body. But a compound statement's HEADER runs a command all by
    itself, and skipping the node threw the header away with the body::

        with subprocess.Popen(['screencapture', '-R', rect, out]) as p:  # missed
        if subprocess.run(['screencapture', '-R', rect, out]).returncode:  # missed
        for line in subprocess.check_output(['screencapture', '-l', wid]):  # missed
        while subprocess.call(['screencapture', '-l%d' % wid, out]):        # missed

    Five of the seven the round found were that one mistake; the sixth was the
    flag in a constant, and the seventh was ``'screencapture -R'.split()``,
    which is the "one literal, and only the words tell you" case below. So a
    compound statement is no longer skipped: it is examined WITHOUT its body
    (``body``/``orelse``/``finalbody``/``handlers``), which is exactly the part
    that runs where it is written. A ``Try`` was the one shape that already
    worked, because its call sits in the body as a statement of its own.

    **AND VERSION FIVE WAS WRONG IN BOTH DIRECTIONS AGAIN, WHICH IS WHY IT NOW
    LOOKS FOR AN ARGV AND NOT FOR TWO WORDS IN A STATEMENT.** Measured
    2026-09-13, third challenge round, by
    `scripts/probe_182_c3_capture_guard.py`.

    Version four said its only remaining misses were "the class it already
    names", one whole command in one string literal. That was not true. It
    followed a name bound by ``NAME = 'screencapture'`` and by nothing else, so
    every other ordinary way of holding the program lost it::

        prog = shutil.which('screencapture')            # missed
        prog = Path('/usr/sbin/screencapture')          # missed
        prog = os.path.join('/usr/sbin', 'screencapture')   # missed
        prog = 'screencapture' if plain else '/usr/sbin/screencapture'  # missed
        def shot(rect, out, prog='screencapture'): ...  # missed
        TOOLS = {'shot': 'screencapture'}               # missed
        class Shot: PROG = 'screencapture'              # missed
        PROG = SCREENCAP                                # missed (alias of alias)

    The literal is right there in every one of them, which is exactly what the
    guard says it follows. So a name is now an alias when ANY binding of it
    carries the marker ANYWHERE in the value: an assignment (including a tuple
    unpack and an attribute target), or a parameter default. It runs to a fixed
    point, so an alias of an alias resolves.

    And it refused six legitimate lines, not the one it admitted to, because it
    paired a program word with a flag word ANYWHERE IN THE SAME STATEMENT::

        subprocess.run(['ls', '-l', '/usr/sbin/screencapture'])     # refused
        subprocess.run(['chmod', '-R', '755', BIN_DIR])             # refused
        OPTS = {'tool': 'screencapture', 'rsync': '-R'}             # refused
        CMDS = {'shot': [...'-x'...], 'copy': ['cp', '-R', ...]}    # refused
        for cmd in (['screencapture', '-x', out], ['ls', '-l', o]): # refused
        run(['screencapture', '-x', o]) and run(['cp', '-R', o, d]) # refused

    Two words in one statement is not a command. An ARGV is: one SEQUENCE in
    which the program comes BEFORE a window flag. That is the shape of
    ``['screencapture', '-R', rect]`` and it is not the shape of ``['ls', '-l',
    '/usr/sbin/screencapture']``, where the binary is the ARGUMENT of another
    command and sits after the flag. Elements are judged without descending
    into a nested sequence, so a table or a loop over two unrelated commands is
    two argvs and never one. Lists joined with ``+`` are flattened, because
    ``['screencapture'] + ['-R', rect]`` is one command written in two pieces;
    a ``+`` of two strings is not, and is left alone.

    KNOWN GAPS, WRITTEN DOWN RATHER THAN IMPLIED, AND EVERY ONE OF THEM PINNED
    BY A TEST BELOW. A whole command assembled into ONE string literal and
    handed to ``os.system`` or to ``shell=True`` is not caught, whether it is
    an f-string or not, because the only thing that separates it from prose is
    what the words mean; ``'screencapture -R'.split()`` is the same literal
    wearing a method call. Neither is a flag built at runtime (``'-' + 'R'``),
    nor a program name built the same way (``'screen' + 'capture'``), nor a
    list grown across several statements with ``append``, nor a program that
    never appears as a literal at all (``prog = which_tool()``), which no rule
    over the syntax could see. Nor a program and its flags passed as separate
    POSITIONAL ARGUMENTS to a call rather than in a list (``os.execlp('screen
    capture', 'screencapture', '-R', rect)``), because that shape is also
    ``print('screencapture', '-R')``. All of them are things nobody writes by
    accident, which is what this guard is for; `scripts/onscreen_capture.py`
    and CLAUDE.md are what cover someone who is trying.

    AND ONE FALSE POSITIVE IS KEPT ON PURPOSE, because removing it would take
    the guard's whole point with it: ``banned = ['screencapture', '-R']``, a
    list of forbidden words, is the SAME ARGV as ``cmd = ['screencapture',
    '-R', rect]``, the case version three had to be rewritten to catch. Nothing
    but the meaning of the words separates them. A driver that needs to write
    one down should put it in prose, or in a comment, which this never reads.

    A plain full-screen ``screencapture -x out.png`` is untouched: photographing
    a whole screen is legitimate, and it is not what this guard is about.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    #: A literal sequence. An element that IS one is not part of the enclosing
    #: command, it is a command of its own, and is judged on its own turn.
    sequences = (ast.List, ast.Tuple, ast.Set, ast.Dict)

    prog_aliases: set[str] = set()
    flag_aliases: set[str] = set()

    def _marks(node, *, shallow: bool = False) -> tuple[bool, bool]:
        """``(carries the program, carries a window flag)`` for a subtree.

        With *shallow*, a nested sequence is not entered.
        """
        prog = flag = False
        stack = [node]
        while stack:
            n = stack.pop()
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                s = n.value.strip()
                prog = prog or bool(_PROGRAM.match(s))
                flag = flag or bool(_WINDOW_FLAG.match(s))
            elif isinstance(n, ast.Name):
                prog = prog or n.id in prog_aliases
                flag = flag or n.id in flag_aliases
            elif isinstance(n, ast.Attribute):
                # `Shot.PROG`, where the class body bound PROG.
                prog = prog or n.attr in prog_aliases
                flag = flag or n.attr in flag_aliases
            for child in ast.iter_child_nodes(n):
                if shallow and isinstance(child, sequences):
                    continue
                stack.append(child)
        return prog, flag

    # -- 1. which NAMES stand for the program, and which for a window flag ---
    bindings: list[tuple[set[str], ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            names = set()
            for t in targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        names.add(n.id)
                    elif isinstance(n, ast.Attribute):
                        names.add(n.attr)
            if node.value is not None and names:
                bindings.append((names, node.value))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.Lambda)):
            a = node.args
            positional = list(a.posonlyargs) + list(a.args)
            if a.defaults:
                for arg, default in zip(positional[-len(a.defaults):],
                                        a.defaults):
                    bindings.append(({arg.arg}, default))
            for arg, default in zip(a.kwonlyargs, a.kw_defaults):
                if default is not None:
                    bindings.append(({arg.arg}, default))

    # A binding can be written after the one it depends on, and an alias can
    # stand for another alias, so this settles rather than running once.
    for _ in range(len(bindings) + 1):
        before = (len(prog_aliases), len(flag_aliases))
        for names, value in bindings:
            prog, flag = _marks(value)
            if prog:
                prog_aliases |= names
            if flag:
                flag_aliases |= names
        if (len(prog_aliases), len(flag_aliases)) == before:
            break

    # -- 2. which SEQUENCES read as an argv ---------------------------------
    def _joined(node) -> bool:
        """A literal sequence, or literal sequences joined with ``+``."""
        if isinstance(node, (ast.List, ast.Tuple)):
            return True
        return (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add)
                and (_joined(node.left) or _joined(node.right)))

    def _elements(node):
        if isinstance(node, (ast.List, ast.Tuple)):
            yield from node.elts
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            yield from _elements(node.left)
            yield from _elements(node.right)
        else:
            yield node

    def _is_argv(node) -> bool:
        """The program, and then a window flag AFTER it, in one sequence."""
        if not _joined(node):
            return False
        seen_program = False
        for elt in _elements(node):
            if isinstance(elt, sequences):
                continue        # a command of its own, judged on its own turn
            prog, flag = _marks(elt, shallow=True)
            if flag and seen_program:
                return True
            seen_program = seen_program or prog
        return False

    #: The fields of a statement that hold OTHER statements. A compound
    #: statement is judged on everything except these, so its header is seen
    #: and its body is left to be judged as the statements it contains.
    body_fields = ("body", "orelse", "finalbody", "handlers")

    def _own(stmt):
        """Every node of *stmt* that runs where *stmt* is written."""
        for field, value in ast.iter_fields(stmt):
            if field in body_fields:
                continue
            for v in (value if isinstance(value, list) else [value]):
                if isinstance(v, ast.AST):
                    yield from ast.walk(v)

    out: list[tuple[int, str]] = []
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.stmt):
            continue
        if not any(_is_argv(n) for n in _own(stmt)):
            continue
        seg = ast.get_source_segment(src, stmt) or ""
        # A compound statement's segment carries its whole body, and the
        # offence is in the header, so only the header line is reported.
        # A simple statement is flattened whole, the way it always was.
        if any(getattr(stmt, f, None) for f in body_fields):
            seg = seg.split("\n")[0]
        out.append((stmt.lineno, " ".join(seg.split())[:120]))
    return out


def test_only_the_shared_helper_aims_screencapture_at_a_window():
    """`-l` and `-R` belong to `onscreen_capture.py` and nowhere else."""
    offenders = []
    for p in _driver_files():
        src = p.read_text(encoding="utf-8")
        for n, seg in _window_captures(src):
            offenders.append(f"{p.relative_to(ROOT)}:{n}: {seg}")
    assert not offenders, (
        "these aim `screencapture` at a window themselves. `-R` returns the "
        "desktop when the window is not composited on the captured Space, and "
        "`-l` does not work on macOS 15 at all. Call "
        "`scripts/onscreen_capture.py::capture_window`, which uses "
        "`CGWindowListCreateImage` and falls back to the rectangle with a "
        "hide/show proof:\n  " + "\n  ".join(offenders))


#: Real window captures. Every one of these must be refused. The first is the
#: shape the guard always caught; 2 to 5 are the ones it let straight through
#: until 2026-09-13, and 2 is the most ordinary way anybody would write it.
_MUST_CATCH = {
    "the literal list, inline in the call":
        "import subprocess\n"
        "subprocess.run(['screencapture', '-R', '1,1,9,9', 'x.png'])\n",
    "the list in a variable, run on the next line":
        "import subprocess\n"
        "cmd = ['screencapture', '-R', rect, str(path)]\n"
        "subprocess.run(cmd, check=True)\n",
    "the program name hidden in a module constant":
        "import subprocess\n"
        "SCREENCAP = 'screencapture'\n"
        "subprocess.run([SCREENCAP, '-R', rect, str(path)], check=True)\n",
    "the window id glued to the flag":
        "import subprocess\n"
        "subprocess.run(['screencapture', '-l%d' % wid, str(path)])\n",
    "an absolute path to the binary":
        "import subprocess\n"
        "subprocess.run(['/usr/sbin/screencapture', '-l', str(wid), 'x.png'])\n",
    # 6 to 10 are the second challenge round's, 2026-09-13. Five of them are
    # one mistake: a compound statement's HEADER was thrown away with its body.
    "a Popen in a `with` header":
        "import subprocess\n"
        "with subprocess.Popen(['screencapture', '-R', rect, 'x.png']) as p:\n"
        "    p.wait()\n",
    "a run inside an `if` test":
        "import subprocess\n"
        "if subprocess.run(['screencapture', '-R', rect, 'x.png']).returncode:\n"
        "    raise SystemExit(1)\n",
    "the output consumed by a `for` header":
        "import subprocess\n"
        "for line in subprocess.check_output(\n"
        "        ['screencapture', '-l', str(wid)]).splitlines():\n"
        "    print(line)\n",
    "retried in a `while` test":
        "import subprocess\n"
        "while subprocess.call(['screencapture', '-l%d' % wid, 'x.png']):\n"
        "    pass\n",
    "the FLAG hidden in a module constant":
        "import subprocess\n"
        "RECT = '-R'\n"
        "subprocess.run(['screencapture', RECT, rect, 'x.png'])\n",
    # 11 to 20 are the THIRD challenge round's, 2026-09-13. Every one of them
    # holds the program in a name, which is what version four said it follows
    # and did not: it followed `NAME = 'screencapture'` and nothing else.
    "the binary found with shutil.which":
        "import shutil, subprocess\n"
        "prog = shutil.which('screencapture')\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "the binary wrapped in a Path":
        "import subprocess\nfrom pathlib import Path\n"
        "prog = Path('/usr/sbin/screencapture')\n"
        "subprocess.run([str(prog), '-l', str(wid), out])\n",
    "the binary assembled with os.path.join":
        "import os, subprocess\n"
        "prog = os.path.join('/usr/sbin', 'screencapture')\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "a conditional picking between two spellings of the binary":
        "import subprocess\n"
        "prog = 'screencapture' if plain else '/usr/sbin/screencapture'\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "the program as a function default":
        "import subprocess\n"
        "def shot(rect, out, prog='screencapture'):\n"
        "    subprocess.run([prog, '-R', rect, out])\n",
    "the FLAG as a function default":
        "import subprocess\n"
        "def shot(rect, out, flag='-R'):\n"
        "    subprocess.run(['screencapture', flag, rect, out])\n",
    "an alias of an alias":
        "import subprocess\n"
        "SCREENCAP = 'screencapture'\nPROG = SCREENCAP\n"
        "subprocess.run([PROG, '-R', rect, out])\n",
    "the program looked up out of a dict":
        "import subprocess\n"
        "TOOLS = {'shot': 'screencapture'}\n"
        "subprocess.run([TOOLS['shot'], '-R', rect, out])\n",
    "the program as a class attribute":
        "import subprocess\n"
        "class Shot:\n    PROG = 'screencapture'\n"
        "subprocess.run([Shot.PROG, '-R', rect, out])\n",
    "one command written as two lists joined with +":
        "import subprocess\n"
        "subprocess.run(['screencapture'] + ['-R', rect, out])\n",
}

#: Real window captures this guard CANNOT see, named here so the gap is a
#: measured fact rather than a hope. Each is one string literal that only means
#: something because of the words inside it, which is the one thing an AST
#: cannot tell from prose. See `_window_captures`'s "KNOWN GAPS".
_KNOWN_BLIND = {
    "a whole command in one f-string, through os.system":
        "import os\nos.system(f'screencapture -R {rect} {path}')\n",
    "a whole command in one plain string, through shell=True":
        "import subprocess\n"
        "subprocess.run('screencapture -R 1,1,9,9 x.png', shell=True)\n",
    "one literal split into a list at runtime":
        "import subprocess\n"
        "subprocess.run('screencapture -R'.split() + [rect, 'x.png'])\n",
    "a flag built at runtime":
        "import subprocess\n"
        "subprocess.run(['screencapture', '-' + 'R', rect, 'x.png'])\n",
    "a list grown across several statements":
        "import subprocess\n"
        "cmd = ['screencapture']\ncmd += ['-R', rect]\nsubprocess.run(cmd)\n",
    # The third challenge round's two, 2026-09-13. Both are outside what a
    # rule over the syntax can reach at all, rather than merely unimplemented.
    "the program name built at runtime, like the flag above":
        "import subprocess\n"
        "prog = 'screen'\nprog += 'capture'\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "the program never written as a literal anywhere":
        "import subprocess\nprog = which_tool()\n"
        "subprocess.run([prog, '-R', rect, out])\n",
    "the program and its flags as separate positional arguments":
        "import os\n"
        "os.execlp('screencapture', 'screencapture', '-R', rect, out)\n",
}

#: Legitimate lines. Every one of these must be allowed. All five were REFUSED
#: by the version of this guard that grepped a call's source text, and all five
#: are things this repository writes constantly: a driver saying WHY it does
#: not roll its own capture.
_MUST_ALLOW = {
    "a module docstring explaining the rule":
        '"""A note about `screencapture -R` and why it is wrong."""\n',
    "a full-screen capture, which is legitimate":
        "import subprocess\nsubprocess.run(['screencapture', '-x', 'x.png'])\n",
    "the rule explained in a printed line":
        "print('screencapture -R returns the desktop; use capture_window')\n",
    "the rule explained in a log call":
        "log.info('not screencapture -R: that is a rectangle of the screen')\n",
    "a comment inside the call that replaced it":
        "capture_window(  # not screencapture -R, which hands back wallpaper\n"
        "    win, path)\n",
    "an argparse help string":
        "parser.add_argument('--shot', help='avoids screencapture -R entirely')\n",
    "a raise that names both dead ends":
        "raise SystemExit('screencapture -l and -R are both dead ends here')\n",
    # The second challenge round's additions: the shapes a compound header
    # could plausibly carry once headers stopped being skipped.
    "a `with` whose header only opens a file":
        "with open('shot.png', 'wb') as f:  # not screencapture -R\n"
        "    f.write(b'')\n",
    "an `if` that explains the rule in its message":
        "if bad:\n"
        "    raise SystemExit('screencapture -R returned the desktop')\n",
    "a `for` over prose about both flags":
        "for note in ('screencapture -R is a rectangle',\n"
        "             'screencapture -l does not work here'):\n"
        "    print(note)\n",
    "a full-screen capture inside a `with`":
        "import subprocess\n"
        "with open('log', 'w') as f:\n"
        "    subprocess.run(['screencapture', '-x', 'x.png'], stdout=f)\n",
    # The third challenge round's six, 2026-09-13. Every one was REFUSED by
    # version four, which paired a program word with a flag word anywhere in
    # one statement. In all six the binary is the ARGUMENT of another command,
    # or the two words are in different commands entirely.
    "listing the binary with `ls -l`":
        "import subprocess\n"
        "subprocess.run(['ls', '-l', '/usr/sbin/screencapture'])\n",
    "a recursive chmod that reaches the binary":
        "import subprocess\n"
        "subprocess.run(['chmod', '-R', '755', '/usr/sbin/screencapture'])\n",
    "a table of commands, one of them a full screen":
        "CMDS = {\n"
        "    'shot': ['screencapture', '-x', 'out.png'],\n"
        "    'copy': ['cp', '-R', 'a', 'b'],\n"
        "}\n",
    "a loop over two unrelated commands":
        "import subprocess\n"
        "for cmd in (['screencapture', '-x', out], ['ls', '-l', out]):\n"
        "    subprocess.run(cmd)\n",
    "a settings dict holding a tool name and an rsync flag":
        "OPTS = {'tool': 'screencapture', 'rsync': '-R'}\n",
    "a full-screen capture and a recursive copy in one statement":
        "import subprocess\n"
        "subprocess.run(['screencapture', '-x', out], check=True) and \\\n"
        "    subprocess.run(['cp', '-R', out, dst])\n",
}


@pytest.mark.parametrize("what", sorted(_MUST_CATCH))
def test_the_guard_above_can_actually_see_a_window_capture(what):
    """A guard that cannot fire is not a guard, and this one silently could
    not: see `_window_captures` for the three ways it failed."""
    assert _window_captures(_MUST_CATCH[what]), (
        f"a real window capture written as {what!r} is not detected:\n"
        + _MUST_CATCH[what])


@pytest.mark.parametrize("what", sorted(_MUST_ALLOW))
def test_the_guard_above_leaves_a_legitimate_line_alone(what):
    """The other half, and the one that turns a gate red on innocent code.

    Explaining the rule is not breaking it. A guard that refuses the sentence
    "do not use screencapture -R" makes the next driver's author delete the
    explanation rather than the fault.
    """
    hits = _window_captures(_MUST_ALLOW[what])
    assert not hits, (
        f"{what!r} is refused, and it is not a window capture: {hits}\n"
        + _MUST_ALLOW[what])


@pytest.mark.parametrize("what", sorted(_KNOWN_BLIND))
def test_the_gaps_this_guard_admits_to_are_the_ones_it_actually_has(what):
    """A gap that is written down but no longer real makes the note a lie, and
    a gap that is real but not written down is the next round's surprise.

    So the admitted blind spots are asserted to be blind. If one of these
    starts being caught, DELETE it from `_KNOWN_BLIND` and from the docstring's
    "KNOWN GAPS", and move it to `_MUST_CATCH`. This assertion failing is good
    news, not a regression.
    """
    assert not _window_captures(_KNOWN_BLIND[what]), (
        f"{what!r} is now caught, which the guard's docstring says it is not. "
        "Move it to `_MUST_CATCH` and delete it from the KNOWN GAPS note:\n"
        + _KNOWN_BLIND[what])


def test_the_false_positive_that_is_kept_on_purpose_is_still_the_only_one():
    """``banned = ['screencapture', '-R']`` is refused, and it must be.

    It is the same tree as ``cmd = ['screencapture', '-R', rect]``, which is
    the case version three of this guard had to be rewritten to catch, so no
    rule written over the syntax can allow one and refuse the other. Pinning it
    here stops the next reader "fixing" it and reopening the hole.
    """
    assert _window_captures("banned = ['screencapture', '-R']\n"), (
        "a list of the banned words is no longer refused. If that was done by "
        "letting a bare list assignment through, `cmd = ['screencapture', "
        "'-R', rect]` is through with it, and that is the whole fault this "
        "guard exists to catch")


def test_the_helper_tries_the_windows_own_buffer_before_the_screen():
    """The order is load-bearing: buffer first, rectangle only as a fallback."""
    src = HELPER.read_text(encoding="utf-8")
    assert "CGWindowListCreateImage" in src, (
        "the helper no longer photographs the window's own buffer, which is "
        "the only route that works when the window is not frontmost")
    body = src[src.index("def capture_window("):]
    buf = body.index("_grab_window_id")
    rect = body.index("_grab_region")
    assert buf < rect, (
        "`capture_window` reaches for the screen rectangle before the window's "
        "own buffer; on macOS 15 that returns wallpaper for any window the "
        "driver did not manage to bring to the front")


def test_a_lock_is_woken_before_it_is_reported():
    """*"my screen never needs a password to be unlocked"* (Basti, 2026-09-13).

    A lock with no password on it is cleared by asserting user activity, so
    reporting one as a blocker before trying is giving up early. That cost a
    whole morning's proof once.
    """
    src = HELPER.read_text(encoding="utf-8")
    assert "def wake_the_screen(" in src
    assert "caffeinate" in src, (
        "`wake_the_screen` no longer asserts user activity, so it cannot clear "
        "a passwordless lock")
    body = src[src.index("def capture_window("):]
    stop = body.index("session_is_locked()")
    woke = body.index("wake_the_screen()")
    ret = body.index("return False")
    assert stop < woke < ret, (
        "`capture_window` reports the lock before trying to wake it; the wake "
        "has to come first, and the refusal only after it fails")


@pytest.mark.parametrize("name", ["wake_the_screen", "window_id_for",
                                  "capture_window", "session_is_locked"])
def test_the_helper_still_offers_what_the_drivers_import(name):
    """Twenty-four drivers import from this module. Renaming is a breaking
    change to all of them at once, so the names are pinned."""
    tree = ast.parse(HELPER.read_text(encoding="utf-8"))
    got = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert name in got, f"{name} is gone from scripts/onscreen_capture.py"
