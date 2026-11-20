# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""Who wrote a measurement (4.3.50, A10).

A tester sent only the ``.ti3`` of a dual scan (19 Nov 2026), and nothing in it
said which ChromIQ or which chart-reading helper had made it: its ORIGINATOR is
ArgyllCMS's "Argyll chartread". Every ``.ti3`` ChromIQ writes or finalises now
carries two header keywords, written the way the other ``CHROMIQ_*`` keywords
are (``KEYWORD "X"`` then ``X "value"``, after the first line)::

    CHROMIQ_VERSION "4.3.50"
    CHROMIQ_HELPER_BUILD "chromiq-chartread_2026-11-19d_legacy-labels"

``CHROMIQ_VERSION`` is the ChromIQ that wrote or finalised the file LAST (a
resumed, merged or averaged file says the newest). ``CHROMIQ_HELPER_BUILD`` is
the helper's build up to its first ``+`` (the rest is its list of abilities),
``stock chartread`` for ArgyllCMS's own reader, and is kept as it is when a
Python step (a merge, an average) writes the file without reading anything.

Only the header of the FIRST table changes; every other byte (the readings, a
calibration table after them) stays as it was, and the readings' hash
(``workflow.i1pro3_conditions.data_block_hash``) with it. ArgyllCMS's CGATS reader
takes unknown keywords (colprof is run on a stamped file in
``tests/test_every_ti3_says_who_wrote_it.py``). Never raises.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

log = logging.getLogger(__name__)

VERSION_KEYWORD = "CHROMIQ_VERSION"
HELPER_KEYWORD = "CHROMIQ_HELPER_BUILD"
STOCK = "stock chartread"
_SAFE = re.compile(r"[^A-Za-z0-9 ._:+/()-]")


def short_build(build: "str | None") -> str:
    """The helper's build up to its first ``+``; "" when unknown."""
    b = str(build or "").strip()
    return _SAFE.sub("_", b.split("+", 1)[0])[:120]


def _set(head: bytes, nl: bytes, key: str, value: str) -> bytes:
    k = key.encode("ascii")
    v = value.encode("ascii", "replace")
    value_re = re.compile(rb"^([ \t]*" + k + rb"[ \t]+)[^\r\n]*", re.MULTILINE)
    m = value_re.search(head)
    if m:
        return head[:m.start()] + m.group(1) + b'"' + v + b'"' + head[m.end():]
    first, found, after = head.partition(b"\n")
    if not found:
        return head
    return (first + b"\n" + b'KEYWORD "' + k + b'"' + nl + k + b' "' + v + b'"' + nl
            + after)


def stamp(path, helper_build: "str | None" = None) -> bool:
    """Write who wrote *path* into its header (see the module text). True when
    the file changed."""
    try:
        from core.version import APP_VERSION
        p = Path(path)
        raw = p.read_bytes()
        head, sep, rest = raw.partition(b"BEGIN_DATA_FORMAT")
        if not sep or not head.lstrip().upper().startswith((b"CTI3", b"CTI2", b"CGATS")):
            return False
        nl = b"\r\n" if b"\r\n" in head[:4096] else b"\n"
        new = _set(head, nl, VERSION_KEYWORD, _SAFE.sub("_", str(APP_VERSION)))
        build = short_build(helper_build) if helper_build not in (None, STOCK) else (
            STOCK if helper_build == STOCK else "")
        if build:
            new = _set(new, nl, HELPER_KEYWORD, build)
        elif not re.search(rb"^[ \t]*" + HELPER_KEYWORD.encode() + rb"[ \t]", new,
                           re.MULTILINE):
            new = _set(new, nl, HELPER_KEYWORD, "-")
        if new == head:
            return False
        tmp = p.with_name(p.name + ".provenance-tmp")
        tmp.write_bytes(new + sep + rest)
        try:
            os.replace(tmp, p)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
        return True
    except Exception:      # noqa: BLE001 - who wrote it never costs a measurement
        log.debug("provenance not written into %s", path, exc_info=True)
        return False


def read(path) -> "tuple[str | None, str | None]":
    """(version, helper build) from *path*'s header, None where absent."""
    try:
        from workflow.measurement_condition import read_header_keyword
        return (read_header_keyword(path, VERSION_KEYWORD),
                read_header_keyword(path, HELPER_KEYWORD))
    except Exception:      # noqa: BLE001
        return None, None
