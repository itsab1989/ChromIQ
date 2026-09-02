"""Text file I/O with the encoding named — issue #178.

Python picks the encoding for :func:`open`, :meth:`Path.read_text` and
:meth:`Path.write_text` from the *platform*, not from the file. That is UTF-8
on macOS and Linux and **cp1252 on a German Windows**, so a project built on one
and opened on the other either comes back as ``MÃ¼ller-PrÃ¼fdruck`` or stops
with ``UnicodeDecodeError: 'utf-8' codec can't decode byte 0xfc``. Both were
measured on real files; see issue #178.

Every text read and write in ChromIQ therefore names its encoding, and the
non-obvious half of that — reading — goes through :func:`read_text` here.

The rule
--------

**Writing is always UTF-8, with no BOM.** Unconditionally, on every platform.
That is what the rest of the world and the rest of this codebase already expect,
it is what ArgyllCMS's byte-level CGATS parsers accept, and it is what Python
3.15 will make the default anyway.

**Reading tries UTF-8 first and only then falls back**, in this order:

1. ``utf-8-sig`` — UTF-8, and a leading BOM is consumed rather than delivered as
   a stray ``\\ufeff``. A Windows-written ``.txt`` re-saved by Notepad has one;
   an Argyll file does not. Decoding is otherwise identical to plain ``utf-8``,
   so there is no reason to prefer the strict spelling.
2. the *running machine's* own default, when it is neither UTF-8 nor already
   cp1252. This is what recovers a file that an older ChromIQ wrote **on this
   same machine** — on a Japanese Windows that is cp932, and no fixed fallback
   list would ever have guessed it.
3. ``cp1252`` — the Western-European Windows default, and the one the issue was
   filed against. This is a **guess**, and it says so: every fallback decode
   logs a warning naming the file and the codec.

The order is what makes the guess safe rather than reckless. It is not
symmetrical: text that is valid UTF-8 is *not* also plausibly cp1252, because
any non-ASCII UTF-8 sequence is a byte run cp1252 renders as visible mojibake —
whereas a cp1252 file containing an umlaut (``0xfc``) is *invalid* UTF-8 and
cannot be mistaken for it. So step 1 never mis-fires on a legacy file, and steps
2-3 are only ever reached for bytes that are definitely not UTF-8. Since
cp1252 maps 251 of 256 byte values, the fallback also almost never raises where
the platform default used to succeed.

What this deliberately is **not**:

* ``errors="replace"`` on the first read. It never raises, and it never tells
  anyone: an umlaut becomes ``\\ufffd`` and the corruption ships. Silence is the
  failure mode the issue is about, so it cannot be the fix.
* A charset sniffer. ChromIQ's own files and Argyll's are ASCII-or-UTF-8 by
  construction, plus one known legacy case; statistical detection would add a
  new way to be wrong about the files we do understand.
* A rewrite-on-read migration. Reading must not modify what it read — a
  measurement or a chart is evidence. Legacy files become UTF-8 the next time
  ChromIQ *writes* them, which is the point at which it owns the bytes.

``lenient=True`` adds a final ``utf-8``/``replace`` net so the call can never
raise. It exists for the call sites that already passed ``errors="replace"`` or
``errors="ignore"`` — they were tolerant before and stay exactly as tolerant,
except that they now try to be *correct* first.
"""
from __future__ import annotations

import locale
import os
from pathlib import Path

from core.logger import get_logger

log = get_logger(__name__)

#: What ChromIQ writes. Always, on every platform, and never with a BOM.
WRITE_ENCODING = "utf-8"

#: The codec ChromIQ reads with first. ``-sig`` only adds "eat a leading BOM".
READ_ENCODING = "utf-8-sig"

#: The legacy Western-European Windows default, tried last. Issue #178 was
#: filed against a German Windows 11, whose default this is.
LEGACY_ENCODING = "cp1252"

_UTF8_ALIASES = {"utf-8", "utf8", "utf_8", "utf-8-sig", "ascii", "us-ascii", "ansi_x3.4-1968"}

#: Files whose fallback has already been reported, so a caller in a loop does
#: not fill the log with the same line. Keyed by (path, codec).
_REPORTED: set[tuple[str, str]] = set()


def _native_encoding() -> str:
    """The encoding *this* machine would have used by default.

    ``locale.getencoding()`` and not ``locale.getpreferredencoding(False)``, for
    two reasons. It is the one CPython does not itself flag under
    ``PYTHONWARNDEFAULTENCODING`` — the detector this fix is measured with, so
    the helper must not be the last thing left in its output. And it is the more
    correct answer: under UTF-8 mode (``PYTHONUTF8=1``)
    ``getpreferredencoding`` reports ``utf-8``, while the legacy file we are
    trying to recover was written before that mode existed, in the machine's
    real locale encoding, which is what ``getencoding`` still reports.
    """
    try:
        getenc = getattr(locale, "getencoding", None)     # Python 3.11+
        raw = getenc() if getenc else locale.getpreferredencoding(False)
        return (raw or "").lower().replace("_", "-")
    except Exception:                                    # pragma: no cover - defensive
        return ""


def read_order() -> tuple[str, ...]:
    """The codecs :func:`read_text` will try, in order.

    Exposed so a test can prove the order rather than infer it, and so a
    simulated German Windows can be checked against the same list the app uses.
    """
    order = [READ_ENCODING]
    native = _native_encoding()
    if native and native not in _UTF8_ALIASES and native != LEGACY_ENCODING:
        order.append(native)
    order.append(LEGACY_ENCODING)
    return tuple(order)


def _universal_newlines(text: str) -> str:
    """What text mode would have done to the line endings.

    :meth:`Path.read_text` opens in text mode with ``newline=None``, which
    translates ``\\r\\n`` and a lone ``\\r`` to ``\\n``. This module decodes
    bytes instead — once, so a three-codec attempt is not three file reads — so
    it has to do that translation itself. Without it, every caller that splits
    on ``"\\n"`` would start seeing a trailing ``\\r`` on Windows-written files
    that it never saw before.
    """
    if "\r" not in text:
        return text
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path: str | os.PathLike[str], *, lenient: bool = False) -> str:
    """Read a text file, naming the encoding rather than inheriting one.

    UTF-8 first; then this machine's own default if it is something else; then
    cp1252. Anything but the first is logged as the guess it is.

    With ``lenient=False`` (the default) a file that no codec decodes raises
    :class:`UnicodeDecodeError`, exactly as a strict read always did. With
    ``lenient=True`` it is decoded as UTF-8 with replacement characters and
    never raises — for the call sites that passed ``errors="replace"`` or
    ``errors="ignore"`` before this change.
    """
    p = Path(path)
    raw = p.read_bytes()
    order = read_order()
    first_error: UnicodeDecodeError | None = None
    for i, enc in enumerate(order):
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError as exc:
            if first_error is None:
                first_error = exc
            continue
        if i:
            key = (str(p), enc)
            if key not in _REPORTED:
                _REPORTED.add(key)
                log.warning(
                    "%s is not UTF-8; read as %s instead. It was probably "
                    "written by an older ChromIQ on Windows. It will be "
                    "rewritten as UTF-8 the next time ChromIQ saves it.",
                    p, enc)
        return _universal_newlines(text)

    if lenient:
        log.warning("%s decodes as no known text encoding; reading it as UTF-8 "
                    "with replacement characters.", p)
        return _universal_newlines(raw.decode("utf-8", errors="replace"))
    assert first_error is not None
    raise first_error


def write_text(path: str | os.PathLike[str], text: str) -> int:
    """Write a text file as UTF-8, with no BOM. Always."""
    return Path(path).write_text(text, encoding=WRITE_ENCODING)
