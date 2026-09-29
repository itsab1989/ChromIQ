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


def test_a_flat_colour_capture_is_refused_however_plausible_its_size():
    """An empty buffer of the right size is not a photograph.

    2026-09-13: `CGWindowListCreateImage` handed back a 960x717 image of pure
    black for a real, visible, correctly sized dialog. `capture_window` checked
    only that the picture was bigger than 200x200, so it returned OK, and the
    round that took it compared the black rectangle against a good capture, got
    "34.75 % of pixels differ", and filed the pair as proof that two scans
    behaved differently. The blank one showed nothing at all.

    The region route has guarded its own version of this since the wallpaper
    incident (it hides the window and refuses a picture that did not change).
    The window-id route skipped that check, reasonably, because a window id
    cannot return the desktop. Nothing was checking what it COULD return.
    """
    import tempfile
    from pathlib import Path

    from PyQt6.QtGui import QColor, QImage

    from scripts.onscreen_capture import _is_one_flat_colour

    with tempfile.TemporaryDirectory() as td:
        blank = Path(td) / "blank.png"
        im = QImage(960, 717, QImage.Format.Format_RGB32)
        im.fill(QColor(0, 0, 0))
        assert im.save(str(blank))
        assert _is_one_flat_colour(blank), "an all-black buffer must be refused"

        # ...and a picture with anything in it must not be.
        real = Path(td) / "real.png"
        im2 = QImage(960, 717, QImage.Format.Format_RGB32)
        im2.fill(QColor(230, 230, 230))
        for x in range(100, 200):
            for y in range(100, 140):
                im2.setPixelColor(x, y, QColor(20, 20, 20))
        assert im2.save(str(real))
        assert not _is_one_flat_colour(real), (
            "a picture with a dark band in it is not one flat colour")

        missing = Path(td) / "not-written.png"
        assert _is_one_flat_colour(missing), "a file that is not there is not proof"


def test_the_window_route_asks_whether_the_picture_has_anything_in_it():
    """The guard has to be CALLED, not merely mentioned.

    This test was written as a substring search first, and the mutation that
    deletes the call left it green: the comment above the call says "See
    `_is_one_flat_colour`", and a comment is text in the source too. It reads
    the syntax tree now, which is the same lesson the sibling guards in this
    file each had to learn.
    """
    import ast
    import inspect
    import textwrap

    from scripts import onscreen_capture

    src = textwrap.dedent(inspect.getsource(onscreen_capture.capture_window))
    tree = ast.parse(src)
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "_grab_window_id" in called, "the window-id route is gone"
    assert "_is_one_flat_colour" in called, (
        "the window-id route returns OK without asking whether the buffer has "
        "anything in it")


# ---------------------------------------------------------------------------
# Challenge round 31: the helper photographed the WRONG window of the right app
# ---------------------------------------------------------------------------
class _FakeWin:
    """Just enough of a QWidget for the CHOICE to be measured.

    The fault is a choice between two candidate windows, and a choice can be
    proved without a window server, a Space, or a Screen Recording grant. Every
    other guard in this file reads source; this one runs the function.
    """

    class _G:
        def __init__(self, x, y, w, h):
            self._v = (x, y, w, h)

        def x(self): return self._v[0]
        def y(self): return self._v[1]
        def width(self): return self._v[2]
        def height(self): return self._v[3]

    def __init__(self, x, y, w, h, title=""):
        self._g = self._G(x, y, w, h)
        self._t = title

    def frameGeometry(self): return self._g
    def windowTitle(self): return self._t


def _helper():
    """`scripts/` is not a package, so load the helper by path, the way the
    drivers reach it (`sys.path.insert(0, ROOT / "scripts")`)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("onscreen_capture_probe",
                                                  HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cg(x, y, w, h, name, number):
    return {"kCGWindowBounds": {"X": x, "Y": y, "Width": w, "Height": h},
            "kCGWindowName": name, "kCGWindowNumber": number}


def test_the_helper_photographs_the_window_it_was_given_not_the_biggest_one():
    """**A MODAL MESSAGE TAKES ITS PARENT'S TITLE, SO "biggest with this title"
    IS ALWAYS THE PARENT.**

    `ui.tooltip_button.InfoDialog` is constructed with its parent's title, so
    the box over the Reference values window is also called "Reference values".
    Both matched, `max(..., area)` preferred the larger one, and the capture
    came back as the window BEHIND the sentence it was filed as.

    Measured challenge round 31 against round 30's own pictures:
    `C-said-en-1.png`, `E-stop-said-en-1.png` and `G-zip-said-en-1.png` are all
    1640x1308 photographs of the greyed-out parent, and the message each is
    named for appears in none of them. Nothing was faked; the helper answered a
    different question, and it has answered it that way for every driver that
    has ever photographed a message box on this project.

    MUTATION, run: delete the `_by_geometry` call in `window_id_for` (or make
    `_by_geometry` return None) and this goes red on the id.
    """
    _by_geometry = _helper()._by_geometry

    parent = _cg(100, 100, 820, 654, "Reference values", 11)
    box = _cg(250, 300, 520, 240, "Reference values", 22)

    # the window the caller asked for is the small one on top
    assert _by_geometry(_FakeWin(250, 300, 520, 240), [parent, box]) is box
    # and asking for the parent still gets the parent
    assert _by_geometry(_FakeWin(100, 100, 820, 654), [parent, box]) is parent


def test_the_geometry_match_gives_up_rather_than_guessing():
    """It may only ANSWER when it is sure, because the caller's fallback (the
    biggest window this process owns) is right far more often than a wrong
    id is harmless: a wrong id photographs a real window, so nothing downstream
    can tell that the picture is of the wrong thing. A near miss inside the
    frame shadow is a match; anything else is None and the size rule decides.
    """
    _by_geometry = _helper()._by_geometry

    a = _cg(100, 100, 820, 654, "x", 11)
    # off by a shadow: still a match
    assert _by_geometry(_FakeWin(104, 102, 812, 650), [a]) is a
    # off by a window: not a match, and it says so rather than picking `a`
    assert _by_geometry(_FakeWin(600, 400, 300, 200), [a]) is None
    # nothing to choose from, and a window with no size yet
    assert _by_geometry(_FakeWin(100, 100, 820, 654), []) is None
    assert _by_geometry(_FakeWin(0, 0, 0, 0), [a]) is None
    # a candidate whose bounds the window server did not give us
    assert _by_geometry(_FakeWin(100, 100, 820, 654),
                        [{"kCGWindowNumber": 9}]) is None


def test_an_untitled_popup_the_server_has_not_placed_yet_is_not_the_main_window():
    """**K2's proof, 2026-09-22: a photograph of the MAIN WINDOW filed under
    the pre-flight's name.** macOS tells the window server no title for a
    `QMessageBox`, so nothing in the list carries its title, and just after
    `show()` its bounds did not yet match `frameGeometry` either. The old rule
    then fell back to the biggest window this process owns, which is the main
    window, on 3 of 4 captures in one run.

    With no title match only the geometry may answer; otherwise it is None and
    `window_id_for` asks again, then the caller's checked rectangle route
    decides. MUTATION, run: put back `max(named or cands, ...)` in
    `_pick_window` and the first assert goes red.
    """
    pick = _helper()._pick_window
    main = _cg(0, 89, 1500, 1028, "ChromIQ — Printer Profiling", 11)
    popup_not_yet_placed = _cg(0, 0, 500, 500, "", 22)
    box = _FakeWin(482, 120, 516, 902)
    assert pick(box, [main, popup_not_yet_placed], "Before you measure") is None
    # once the server has it where Qt says, the geometry answers
    placed = _cg(482, 120, 516, 902, "", 22)
    assert pick(box, [main, placed], "Before you measure") is placed
    # and a TITLED window still falls back to the size rule among its namesakes
    assert pick(_FakeWin(5, 5, 10, 10), [main], "ChromIQ — Printer Profiling") \
        is main


def test_window_id_for_asks_again_until_the_server_has_placed_the_popup(
        monkeypatch):
    """The retry in `window_id_for` is what B8-777 rests on: the window server
    places a just-shown popup late. Adversary round on 528b7cfc: `range(10)`
    cut to `range(1)`, or the break inverted, left every test green.

    A fake `Quartz` whose list shows the popup unplaced until the Nth ask: the
    id is found on exactly that ask, and a popup placed on the first ask is
    found on the first, so a found window does not wait. MUTATIONS:
    `range(1)` -> None in the first case; inverted break -> ten asks.
    """
    import os
    import sys
    import time
    import types
    mod = _helper()
    monkeypatch.setattr(time, "sleep", lambda s: None)
    box = _FakeWin(482, 120, 516, 902)
    main = _cg(0, 89, 1500, 1028, "ChromIQ — Printer Profiling", 11)
    unplaced = _cg(0, 0, 500, 500, "", 22)
    placed = _cg(482, 120, 516, 902, "", 22)
    calls = {"n": 0, "placed_on": 4}

    def listing(option, relative):
        calls["n"] += 1
        pop = placed if calls["n"] >= calls["placed_on"] else unplaced
        return [dict(w, kCGWindowOwnerPID=os.getpid()) for w in (main, pop)]

    monkeypatch.setitem(sys.modules, "Quartz", types.SimpleNamespace(
        CGWindowListCopyWindowInfo=listing, kCGWindowListOptionOnScreenOnly=1,
        kCGWindowListOptionAll=0, kCGWindowListExcludeDesktopElements=16,
        kCGNullWindowID=0))
    # one listing per attempt, because the on-screen list is never empty here
    assert mod.window_id_for(box) == 22
    assert calls["n"] == 4
    calls.update(n=0, placed_on=1)
    assert mod.window_id_for(box) == 22
    assert calls["n"] == 1
