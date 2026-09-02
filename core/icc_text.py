"""ICC text encodings — keeping an accent in a profile's name.

A v2 profile's ``desc`` tag is ``textDescriptionType``, which carries the SAME
name three times: a 7-bit ASCII string, a UTF-16BE (Unicode) string with a
language code, and a Macintosh ScriptCode string.  Only the first is limited
to ASCII.

ArgyllCMS fills the ASCII field and leaves the Unicode field zero length
(``profile/profout.c`` sets only ``wo->desc``), and its ASCII converter
substitutes ``'?'`` for every non-ASCII character
(``icc/icc_util.c::icmUTF8toASCIIZSn``, ``replacement_char = '?'``).  So a
project called ``Müller-Prüfdruck`` reaches the file as the literal bytes
``M?ller-Pr?fdruck`` — measured, 2026-09-02, Argyll 3.5.0 — and every reader
on every platform shows exactly that, macOS included.  Windows is not
mangling the name; it is displaying the only string the file contains.

Two fixes, and they are complementary because different readers look at
different fields (both measured on this machine):

* **Fill the Unicode field.**  macOS ColorSync prefers it and shows
  ``Müller-Prüfdruck``.  littleCMS 2.18 (GIMP, Krita, darktable, Firefox …)
  ignores it entirely.
* **Transliterate the ASCII field** instead of letting it become ``?``.
  ``Mueller-Pruefdruck`` is what a German reader would write by hand, and it
  is what every ASCII-only reader then shows.

Neither can be worse than a ``?``, so ChromIQ does both.
"""
from __future__ import annotations

import hashlib
import struct
import unicodedata

# German (and Nordic/Turkish) letters whose accepted ASCII spelling is a
# digraph, not the bare base letter: "Müller" is spelled "Mueller", never
# "Muller".  Applied before the generic diacritic strip below.
_DIGRAPHS = {
    # German — the reported case, and the one where dropping the mark is
    # actually WRONG: "Müller" is spelled "Mueller", never "Muller".
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ẞ": "SS",
    # Latin letters with no canonical decomposition, so the generic
    # mark-stripping below cannot reach them and they would become "?".
    "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
    "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "Th", "ł": "l", "Ł": "L", "ı": "i", "İ": "I",
    "ŋ": "n", "Ŋ": "N", "ħ": "h", "Ħ": "H",
    # Punctuation and symbols a copyright line is actually made of. These
    # have no combining mark to strip, so without an entry here they become
    # "?" — and "? 2026 Mueller Druckerei" is the blemish this whole change
    # set out to remove, one line further down the profile.
    "©": "(c)", "®": "(r)", "™": "(tm)", "€": "EUR", "£": "GBP", "¥": "JPY",
    "«": '"', "»": '"', "“": '"', "”": '"', "„": '"',
    "‘": "'", "’": "'", "‚": "'",
    "–": "-", "—": "-", "‑": "-", "…": "...", "·": ".", "•": "*",
    "\u00a0": " ", "\u202f": " ", "\u2009": " ",   # the no-break spaces
    "°": "deg", "±": "+/-", "×": "x", "÷": "/", "µ": "u", "½": "1/2",
}


def ascii_fallback(text: str) -> str:
    """A 7-bit ASCII spelling of ``text`` — what an ASCII-only reader shows.

    ``"Müller-Prüfdruck"`` → ``"Mueller-Pruefdruck"``.  Letters with an
    accepted digraph spelling use it; everything else is decomposed and has
    its combining marks dropped (``é`` → ``e``, ``ñ`` → ``n``).  Anything with
    no ASCII form at all — CJK, Greek, emoji — still becomes ``'?'``, exactly
    as before, because there is nothing better to put there.

    Pure-ASCII input is returned unchanged, so a profile with a plain name is
    byte-for-byte what it always was.
    """
    if text.isascii():
        return text
    out: list[str] = []
    for ch in unicodedata.normalize("NFC", text):
        if ch.isascii():
            out.append(ch)
            continue
        if ch in _DIGRAPHS:
            out.append(_DIGRAPHS[ch])
            continue
        stripped = "".join(
            c for c in unicodedata.normalize("NFD", ch)
            if not unicodedata.combining(c)
        )
        out.append(stripped if stripped.isascii() and stripped else "?")
    return "".join(out)


def text_description(text: str, *, script_code: int = 0) -> bytes:
    """A complete ``textDescriptionType`` tag for ``text``.

    The ASCII field carries :func:`ascii_fallback`; the Unicode field carries
    ``text`` itself as UTF-16BE, NUL-terminated, with ``ucLangCode`` 0 and no
    byte-order mark (Argyll's reader flags a BOM as ``icmUTF_unn_bom``, and
    ColorSync reads it identically either way — measured).  The ScriptCode
    block is the spec's fixed 67 bytes of zeros, which is what Argyll writes.

    For pure-ASCII ``text`` the Unicode field is left zero length, so the
    bytes are identical to what Argyll and to what ChromIQ's engine have
    always produced.
    """
    a = ascii_fallback(text).encode("ascii", "replace") + b"\0"
    blob = b"desc" + b"\0" * 4 + struct.pack(">I", len(a)) + a
    if text.isascii():
        blob += struct.pack(">II", 0, 0)
    else:
        u = (text + "\0").encode("utf-16-be")
        # uc16count counts UTF-16 code units INCLUDING the NUL terminator —
        # icc.c: "UTF-16 character count inc. nul".
        blob += struct.pack(">II", 0, len(u) // 2) + u
    return blob + struct.pack(">HB", script_code, 0) + b"\0" * 67


def parse_text_description(blob: bytes) -> tuple[str, str]:
    """``(ascii_field, unicode_field)`` of a ``textDescriptionType`` tag."""
    if blob[:4] != b"desc":
        raise ValueError(f"not a textDescriptionType tag: {blob[:4]!r}")
    n = struct.unpack(">I", blob[8:12])[0]
    ascii_field = blob[12:12 + n].split(b"\0")[0].decode("latin-1")
    p = 12 + n
    _lang, count = struct.unpack(">II", blob[p:p + 8])
    uni = blob[p + 8:p + 8 + count * 2].decode("utf-16-be", "replace")
    return ascii_field, uni.split("\0")[0].lstrip("﻿")


# ---------------------------------------------------------------------------
# Repairing a profile Argyll already wrote
# ---------------------------------------------------------------------------

# The v2 header has no profile ID; v4 defines bytes 84..99 as an MD5 taken
# with the flags, rendering-intent and ID fields themselves zeroed.
_ID_ZEROED_RANGES = ((44, 48), (64, 68), (84, 100))


def _profile_id(data: bytes) -> bytes:
    b = bytearray(data)
    for lo, hi in _ID_ZEROED_RANGES:
        b[lo:hi] = b"\0" * (hi - lo)
    return hashlib.md5(bytes(b)).digest()


def repair_descriptions(data: bytes, names: dict[bytes, str]) -> bytes:
    """Give an Argyll-written profile its accents back.

    ``names`` maps a tag signature (``b"desc"``, ``b"dmdd"``, ``b"dmnd"``) to
    the string ChromIQ actually asked for.  For each one whose true string is
    non-ASCII, the tag is rewritten with a transliterated ASCII field and a
    real Unicode field.

    **A tag is only touched when the file proves it is the right one**: the
    ASCII currently stored must equal what Argyll's ``'?'`` substitution of
    the requested string would have produced.  Anything else — a different
    name, an already-repaired tag, a tag type that is not
    ``textDescriptionType`` — is left exactly as it is.

    The new tag data is appended at the end of the file and the tag table
    entry repointed, so **no other tag moves**: only that entry's offset and
    size, the header's size field, and (if it was ever non-zero) the profile
    ID change.  When nothing needs repairing the input bytes are returned
    unchanged — a plain-ASCII profile is byte-identical.
    """
    if len(data) < 132 or data[36:40] != b"acsp":
        return data
    wanted = {sig: s for sig, s in names.items() if s and not s.isascii()}
    if not wanted:
        return data

    count = struct.unpack(">I", data[128:132])[0]
    if 132 + 12 * count > len(data):
        return data

    out = bytearray(data)
    changed = False
    for i in range(count):
        sig, off, size = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        true_name = wanted.get(sig)
        if true_name is None or off + size > len(data):
            continue
        blob = data[off:off + size]
        if blob[:4] != b"desc":
            continue
        try:
            stored_ascii, stored_uni = parse_text_description(blob)
        except (ValueError, struct.error):
            continue
        # Argyll's own '?' substitution of the requested name. If the file
        # does not hold one of those spellings, this is not the tag we think
        # it is.
        #
        # BOTH NORMAL FORMS, BECAUSE macOS SENDS THE DECOMPOSED ONE.
        # `ArgyllRunner` runs colprof through `QProcess`, and QProcess
        # converts its arguments to NFD on macOS — measured: `/bin/echo`
        # handed the NFC "Müller-Prüfdruck" (16 chars) prints it back
        # decomposed (18), while `subprocess` prints it unchanged. colprof
        # therefore stores "Mu?ller-Pru?fdruck", one '?' per combining mark,
        # not the "M?ller-Pr?fdruck" a direct call produces. Comparing only
        # against the composed spelling meant this guard never matched on the
        # one platform the feature was written for, and the repair silently
        # did nothing on every real build — the profile kept the mangled name
        # and the Unicode field stayed empty.
        #
        # The guard is no less strict: the file must still hold exactly
        # Argyll's '?' spelling of the name we asked for. It may now hold it
        # in either normal form, which is the only thing that varies.
        _spellings = {
            n.encode("ascii", "replace").decode("ascii")
            for n in (true_name,
                      unicodedata.normalize("NFC", true_name),
                      unicodedata.normalize("NFD", true_name))
        }
        if stored_ascii not in _spellings:
            continue
        if stored_uni:
            continue                       # already carries a Unicode name
        new = text_description(true_name)
        while len(out) % 4:
            out += b"\0"
        new_off = len(out)
        out += new
        while len(out) % 4:
            out += b"\0"
        struct.pack_into(">II", out, 136 + 12 * i, new_off, len(new))
        changed = True

    if not changed:
        return data
    struct.pack_into(">I", out, 0, len(out))
    if data[84:100] != b"\0" * 16:
        out[84:100] = _profile_id(bytes(out))
    return bytes(out)
