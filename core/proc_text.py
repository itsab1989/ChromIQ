"""Decoding what a command-line tool wrote — issue #178.

`core/text_io.py` covers files. This module covers the other half of the same
bug: the bytes ArgyllCMS, `lp` and `sysctl` write to a pipe, which ChromIQ
turned into text by letting the platform choose the codec.

Two spellings of that, both measured:

**`subprocess.run(..., text=True)` with no `encoding=`.** Python decodes with
`locale.getpreferredencoding(False)`. On this Mac that is UTF-8 and harmless.
Under a POSIX-default locale it is US-ASCII, and the first umlaut in a path is
a hard stop::

    $ LANG=C PYTHONUTF8=0 python probe_locale.py
    locale.getpreferredencoding() = US-ASCII
    subprocess text=True RAISED UnicodeDecodeError:
        'ascii' codec can't decode byte 0xc3 in position 1

`ChromIQLinux.spec` exists, so that is a build we ship. On a German Windows it
does not raise, it decodes cp1252 — right for Argyll, wrong for anything else,
and silent either way.

**`raw.decode("utf-8", errors="replace")`**, hard-coded, on the QProcess and
PTY output in `core/argyll_runner.py`. That is the main Argyll channel: every
line the log, the failure dialogs and the stripe detector see. On a German
Windows a path in an error message reached the user as ``M?ller-Pr?fdruck.ti3``
— the symptom issue #178 was filed about, produced by the code that reports it.

What encoding is actually right
-------------------------------

**macOS and Linux: UTF-8.** Python hands argv to the tool as UTF-8 bytes and
the tool echoes those bytes back. There is nothing to guess.

**Windows: the ANSI code page** — cp1252 on a German install. ArgyllCMS ships
as MSVC console programs with no UTF-8 manifest, so ``main()`` receives argv
already narrowed from the wide command line through the ANSI code page, and
``printf`` writes those same bytes to a redirected pipe. A blanket
``encoding="utf-8"`` would therefore have replaced a crash with a mangling on
the one platform the issue was filed from, which is the worse trade because it
is silent.

Neither of us has a Windows machine to check that reasoning on. So this module
does not bet on it: it tries the codecs in order, exactly as
:func:`core.text_io.read_order` does for files, and takes the first that
decodes. On macOS and Linux that is UTF-8 and nothing changes. On Windows a
UTF-8 echo decodes as UTF-8 and an ANSI echo decodes as ANSI, whichever the
tool turns out to write.

Why one policy is safe for parsed output as well as for the log
---------------------------------------------------------------

Several callers parse this output into numbers — `xicclu`, `profcheck`,
`gamut_map`, `ti2_relayout`. Guessing a codec for those would be reckless if
the guess could change a value. It cannot, and the reason is worth stating
because it is what makes a single policy defensible:

**Every codec in the ladder is an ASCII superset.** UTF-8, cp1252, cp932,
cp1250 and the rest all agree, byte for byte, on 0x00-0x7F.
:func:`test_every_codec_in_the_ladder_agrees_on_ascii` proves it over all 128
values for every codec ChromIQ can reach. Argyll's numeric output — patch
values, dE figures, the strip prompts — is ASCII. Non-ASCII bytes appear only
where a *name or a path* is echoed. So the codec choice can change how a
filename is rendered in a message; it can never change a number, drop a field,
or shift a column.

That is why :func:`run_text` may end in a replacement net rather than raising.
A build log that loses one character in a filename is far better than a build
that dies, and the guarantee above is what stops that argument from leaking
into the parsed output, where it would not hold.

Nothing here is ``errors="replace"`` on the first attempt. That is the design
`core/text_io.py` calls the bug, for the same reason: it never tries to be
correct and it never tells anyone. Replacement is the last rung of the ladder,
it is reached only for bytes no codec accepts, and it logs when it happens.
"""
from __future__ import annotations

import subprocess
from typing import Any, Callable, Sequence

from core.logger import get_logger
from core.text_io import read_order

log = get_logger(__name__)

#: What ChromIQ writes to a tool's stdin. Always UTF-8 — the same rule as
#: `core.text_io.WRITE_ENCODING`, and in practice always ASCII anyway, because
#: what ChromIQ pipes into a tool is device values.
INPUT_ENCODING = "utf-8"

#: Reported once per (codec, tool) so a per-line decoder in a loop does not
#: fill the log with the same sentence a thousand times.
_REPORTED: set[tuple[str, str]] = set()


def output_order() -> tuple[str, ...]:
    """The codecs :func:`decode_output` will try, in order.

    Deliberately :func:`core.text_io.read_order` and not a second list. A tool's
    output and a tool's input file carry the same names in the same bytes, so
    two rules would be one rule too many, and the file half of #178 is where
    that order was argued out.
    """
    return read_order()


def decode_output(raw: bytes | str | None, *, what: str = "a tool") -> str:
    """Turn what a tool wrote into text, naming the codec rather than inheriting one.

    ``None`` becomes ``""`` — a caller that did not capture that stream sees
    what it saw before. A ``str`` is passed straight through, so a test that
    injects a fake runner returning text keeps working.

    Never raises. The last rung is UTF-8 with replacement characters, and it
    logs when it is reached. See the module docstring for why that is safe here
    and is not safe for a file.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    order = output_order()
    for i, enc in enumerate(order):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if i:
            _report(enc, what,
                    "%s wrote output that is not UTF-8; read as %s instead. On "
                    "Windows that is the tool's own ANSI code page and is "
                    "expected; anywhere else it is a guess.")
        return text
    _report("replace", what,
            "%s wrote output that decodes as no known text encoding (%s); "
            "unreadable characters are shown as U+FFFD. Numbers are "
            "unaffected: every codec tried agrees on ASCII.")
    return raw.decode("utf-8", errors="replace")


def _report(enc: str, what: str, msg: str) -> None:
    key = (enc, what)
    if key in _REPORTED:
        return
    _REPORTED.add(key)
    log.warning(msg, what, enc)


def run_text(cmd: Sequence[Any], *,
             runner: Callable[..., subprocess.CompletedProcess] | None = None,
             input: str | bytes | None = None,
             **kw: Any) -> "subprocess.CompletedProcess[str]":
    """`subprocess.run` with the encoding named instead of inherited.

    A drop-in for ``subprocess.run(cmd, capture_output=True, text=True)``. The
    child is run in **binary** mode and its two streams are decoded here, by
    :func:`decode_output`, so the ladder applies — which ``text=True`` cannot
    do, because it takes a single codec name.

    ``runner`` is for the call sites that already accept an injected
    ``subprocess.run`` so a test can stand in for the tool; it defaults to the
    real one. ``text``, ``universal_newlines``, ``encoding`` and ``errors`` are
    dropped if passed, because this function is the thing that decides them.
    """
    runner = runner or subprocess.run
    for gone in ("text", "universal_newlines", "encoding", "errors"):
        kw.pop(gone, None)
    if isinstance(input, str):
        input = input.encode(INPUT_ENCODING)
    if input is not None:
        kw["input"] = input
    what = str(cmd[0]) if cmd else "a tool"
    r = runner(cmd, **kw)
    return subprocess.CompletedProcess(
        getattr(r, "args", cmd),
        r.returncode,
        decode_output(getattr(r, "stdout", None), what=what),
        decode_output(getattr(r, "stderr", None), what=what),
    )
