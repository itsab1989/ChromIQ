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

The order is what makes the guess *safer*, not what makes it safe. A cp1252
file containing an umlaut (``0xfc`` followed by an ASCII letter) is invalid
UTF-8 and cannot be mistaken for it, which is why German — the language the
issue was filed in — is recovered correctly. **But the reverse is not
guaranteed, and this module used to claim it was.** 1,770 two-character cp1252
strings encode to bytes that are also valid UTF-8 meaning something else
(measured; ``tests/test_encoding_is_named.py``). The realistic one is
double-encoded text: a file that already says ``prÃ©fÃ©rence`` in cp1252 is the
exact bytes of ``préférence`` in UTF-8, so step 1 succeeds, the text silently
changes meaning, and **no fallback happens and nothing is logged at all**. That
case is not detectable from the bytes — both readings are legitimate text — so
it is not fixed here; it is written down so nobody reasons from the old claim.

Since cp1252 maps 251 of 256 byte values, the fallback also almost never raises
where the platform default used to succeed. That is convenient and it is also
the danger: it means the last resort cannot say no. So a file that is
positively **not** ChromIQ text at all is refused before the fallback is ever
reached, and refusing is the whole point of :func:`_not_text_at_all`.

Every fallback decode is reported. Every time, not once per file: a
measurement read on every chartread run warned once and then went quiet for the
rest of the session, which is the same silence the issue is about wearing a
different hat.

What this deliberately is **not**:

* ``errors="replace"`` on the first read. It never raises, and it never tells
  anyone: an umlaut becomes ``\\ufffd`` and the corruption ships. Silence is the
  failure mode the issue is about, so it cannot be the fix.
* A charset sniffer. ChromIQ's own files and Argyll's are ASCII-or-UTF-8 by
  construction, plus one known legacy case; statistical detection would add a
  new way to be wrong about the files we do understand. Reading a byte-order
  mark is not sniffing: a BOM is the file stating what it is, in the file.
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

#: Byte-order marks that say "this file is UTF-16 or UTF-32", i.e. two or four
#: bytes per character with NULs in between. ``FF FE 00 00`` is UTF-32LE and
#: starts with the UTF-16LE mark, so the pair is enough to recognise all four.
#: The UTF-8 BOM is deliberately absent: ``utf-8-sig`` eats that one, which is
#: the whole reason it is the first codec tried.
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


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


def _not_text_at_all(raw: bytes) -> "tuple[str, int, int] | None":
    """``(reason, start, end)`` when *raw* is positively not ChromIQ text.

    THE LAST RESORT CANNOT SAY NO, SO SOMEBODY HAS TO SAY IT FIRST. cp1252
    maps 251 of 256 byte values, so it decodes almost anything, and it decoded
    UTF-16 into visible nonsense without raising:
    ``FF FE 4D 00 FC 00`` came back as ``'ÿþM\x00ü\x00'``. Worse, UTF-16LE
    with ASCII content is *valid UTF-8* (NUL is a legal UTF-8 byte), so
    ``'CREATED "2026"'`` written by PowerShell decoded on the first try with
    no warning at all. Both were measured.

    Two signals, both certainties rather than statistics:

    * a UTF-16/UTF-32 byte-order mark. The file says what it is.
    * a NUL byte anywhere. ChromIQ writes CGATS, JSON and plain text; Argyll
      writes CGATS. None of them contains a NUL, so one means the bytes are
      not the text they are being read as, whether that is UTF-16 with no BOM
      or a binary file handed to the wrong reader.

    Windows PowerShell 5.1 is still the default shell there, and ``>`` and
    ``Out-File`` write UTF-16LE with a BOM; older Notepad's "Save as →
    Unicode" does the same. No ChromIQ or Argyll producer writes UTF-16, so
    the mechanism is proved and the trigger is plausible but unobserved.
    """
    for bom in _UTF16_BOMS:
        if raw.startswith(bom):
            return ("byte-order mark says UTF-16 or UTF-32, not UTF-8", 0,
                    len(bom))
    nul = raw.find(b"\x00")
    if nul >= 0:
        return ("NUL byte in a text file (UTF-16 with no byte-order mark, "
                "or not text at all)", nul, nul + 1)
    return None


def _decode_as_declared(raw: bytes) -> str:
    """*raw* read as whatever its byte-order mark says, for ``lenient=True``.

    A lenient caller must never raise, and returning the bytes mangled through
    ``utf-8``/``replace`` would hand it the nonsense this whole function exists
    to refuse. When the file declares itself, honour the declaration; the
    result is the text somebody actually wrote.
    """
    for bom, codec in ((b"\xff\xfe\x00\x00", "utf-32"),
                       (b"\x00\x00\xfe\xff", "utf-32"),
                       (b"\xff\xfe", "utf-16"),
                       (b"\xfe\xff", "utf-16")):
        if raw.startswith(bom):
            try:
                return raw.decode(codec)
            except (UnicodeDecodeError, LookupError):
                break
    # No mark, but UTF-16 with no mark still has a shape nothing else has:
    # ASCII text puts a NUL under every second byte, on one fixed parity for
    # the whole file. That is a structure, not a statistic, so it is checked
    # rather than guessed at, and only here — a strict read has already
    # refused the file, and this path may not raise.
    #
    # THE DENSITY AS WELL AS THE PARITY, and leaving the density out cost a
    # measurement. `all(i % 2 for i in nuls)` is satisfied by ONE stray NUL at
    # an odd offset — so a 344-byte ASCII `.ti3` with a single corrupt byte
    # (a crash mid-write, a flaky USB stick, a bad restore) was decoded as
    # UTF-16LE and came back as 83 characters of CJK. `mark_verification_ti3`
    # then wrote that back and unlinked the original: the person's measurement,
    # destroyed by one bad byte. Before this module existed the same file lost
    # exactly one character. A real UTF-16 file has a NUL under about half its
    # bytes; requiring a quarter admits even a file that is half CJK, and
    # rejects any plausible stray-NUL count outright.
    if len(raw) >= 4 and not len(raw) % 2:
        nuls = [i for i, b in enumerate(raw) if b == 0]
        if len(nuls) * 4 < len(raw):
            nuls = []                    # too sparse to be UTF-16 at all
        if nuls and all(i % 2 for i in nuls):
            try:
                return raw.decode("utf-16-le")
            except UnicodeDecodeError:
                pass
        elif nuls and not any(i % 2 for i in nuls):
            try:
                return raw.decode("utf-16-be")
            except UnicodeDecodeError:
                pass
    return raw.decode("utf-8", errors="replace")


def read_text(path: str | os.PathLike[str], *, lenient: bool = False) -> str:
    """Read a text file, naming the encoding rather than inheriting one.

    UTF-8 first; then this machine's own default if it is something else; then
    cp1252. Anything but the first is logged as the guess it is.

    A file that is positively not ChromIQ text is refused before any of that
    (see :func:`_not_text_at_all`), so the codec list cannot be used to launder
    UTF-16 into nonsense.

    With ``lenient=False`` (the default) a file that no codec decodes, and a
    file that is refused, raise :class:`UnicodeDecodeError` — one failure mode,
    the one a strict read always had, so every caller that already handles a
    bad file keeps handling it. With ``lenient=True`` nothing raises: a file
    that declares itself UTF-16 is decoded as UTF-16, anything else as UTF-8
    with replacement characters, for the call sites that passed
    ``errors="replace"`` or ``errors="ignore"`` before this change.
    """
    p = Path(path)
    raw = p.read_bytes()

    refused = _not_text_at_all(raw)
    if refused is not None:
        reason, start, end = refused
        if lenient:
            log.warning(
                "%s is not UTF-8: %s. Reading it as best as can be managed; "
                "the text may not be what whoever wrote it intended.",
                p, reason)
            return _universal_newlines(_decode_as_declared(raw))
        log.error("%s is not UTF-8: %s. ChromIQ writes UTF-8 and cannot read "
                  "this file. Save it as UTF-8 and try again.", p, reason)
        raise UnicodeDecodeError("utf-8", raw, start, end, reason)

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
            # EVERY TIME, not once per file. This used to dedup on
            # (path, codec) in a module-global set that was never cleared, so
            # a measurement read on every chartread run warned once and then
            # went quiet for the rest of the session, and the set grew for the
            # life of the process. Nothing can make the guess always right, so
            # what gets removed is the silence, not the ambiguity (Basti,
            # 2026-09-02).
            #
            # The text says what happened and what was assumed, and claims
            # nothing else. It used to say the file "was probably written by
            # an older ChromIQ on Windows", which it cannot know: a cp1252
            # file may equally have come off any Windows machine, any editor,
            # or a hand edit.
            log.warning(
                "%s is not valid UTF-8. It was read as %s instead, which is a "
                "guess: the file does not say what it is, so the text may not "
                "be what whoever wrote it intended. ChromIQ will write it as "
                "UTF-8 the next time it saves it.", p, enc)
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
