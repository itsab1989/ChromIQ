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

**Windows: MEASURED, and it is UTF-8.** This paragraph used to argue the
opposite — that ArgyllCMS ships as MSVC console programs with no UTF-8
manifest, so ``main()`` receives argv already narrowed from the wide command
line through the ANSI code page and ``printf`` writes those same bytes back.
That reasoning is FALSIFIED. On **Windows 11 Home 26200.9168 (25H2), ARM64,
German UI**, with **ArgyllCMS 3.5.0, the official win64 build, under x64
emulation**, ``printtarg.exe`` was made to echo a path holding umlauts into an
error message and the raw bytes were captured without being decoded
(a Claude Code session on the owner's VM, 2026-09-03, reported in
``WINDOWS-VM-REPORT.md`` §2d)::

    argv: [...\\printtarg.exe, '-v', 'Müller-Prüfdruck-does-not-exist']
    stderr RAW BYTES: b"... 'M\\xc3\\xbcller-Pr\\xc3\\xbcfdruck-does-not-exist.ti1' ..."

``ü`` came back as ``0xC3 0xBC`` — UTF-8. The ANSI byte for ``ü`` on that
machine is ``0xFC``, and the machine really is an ANSI-cp1252 one::

    GetACP() = 1252      GetConsoleOutputCP() = 850
    locale.getpreferredencoding(False) = cp1252

**Nothing here changes, and the reason the order is still right is a different
one.** It is not "we do not know what Windows writes" any more; it is that
**one Argyll build is not every Argyll build**. That measurement covers 3.5.0
win64 under emulation, and the module is also handed ``lp`` (which does not
exist on Windows) and ``sysctl`` (nor does it) on the platforms where they do
— neither was, or can be, measured there. So the module still does not bet: it
tries the codecs in order, exactly as :func:`core.text_io.read_order` does for
files, and takes the first that decodes.

**UTF-8 first is now the measured-correct first rung rather than a hopeful
one**, and the ladder is what stopped the old reasoning from doing damage: had
this module hard-coded the ANSI code page on Windows — which is exactly what
the falsified paragraph argued for — every Argyll path with an umlaut would
today be ``MÃ¼ller-PrÃ¼fdruck`` on screen, silently, on the one platform issue
#178 was filed from. The order must not be inverted to "ANSI first on
Windows": that decodes valid UTF-8 into mojibake without ever raising, because
cp1252 maps 251 of 256 byte values and therefore cannot say no.

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
            # A DIAGNOSTIC, not UI text: this logger has a file handler and a
            # stream handler and no log-panel handler, so nothing here reaches
            # a window. It used to end "on Windows that is the tool's own ANSI
            # code page and is expected" — measured false for ArgyllCMS 3.5.0,
            # which writes UTF-8 there (see the module docstring). Reaching a
            # fallback rung is now a surprise on every platform, and the line
            # says so, because "expected" is what stops somebody looking.
            _report(enc, what,
                    "%s wrote output that is not UTF-8; read as %s instead. "
                    "That is a fallback and a guess: name the tool and the "
                    "platform before trusting any path in this output.")
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
