# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 the ChromIQ authors. Part of ChromIQ (https://github.com/itsab1989/ChromIQ).
"""The privacy filter of the app log (4.3.50, A0).

The app log is the ONE file a tester is asked to send (the project owner, 19 Nov
2026). Before this, the account name reached it by three routes at least (the
settings file's path, ``sys.argv``, every ``Run:`` command line with full paths),
and only the i1iO table scrubbed its own separate log. This module scrubs EVERY
line at the handler, whoever wrote it, through :class:`ScrubbingFormatter`.

WHAT IS REPLACED
* this account's home folder (any spelling: ``/Users/x``, ``C:\\Users\\x``,
  ``C:/Users/x``, ``/home/x``, the resolved form) -> ``~``;
* other accounts' home folders -> ``/Users/<user>``, ``/home/<user>``,
  ``C:\\Users\\<user>`` (``Shared``, ``Public``, ``Default`` and ``All Users``
  stay: they name no person);
* the account name (and the home folder's own name, when it differs) as a WHOLE
  WORD, case-insensitive, unicode-aware -> ``<user>``. A word that merely
  contains it is left alone ("bastion" stays for the account "basti"). Names
  shorter than three letters are replaced only inside the home paths above,
  never as words, since a one- or two-letter word occurs everywhere;
* the full name from the account database, as a whole phrase -> ``<user>``;
* this computer's own name as a whole word (``Bastis-Mac-mini``,
  ``Bastis-Mac-mini.local``) -> ``<computer>``; a short name that is an ordinary
  word ("Mac", from "Mac.fritz.box") only in its full dotted form;
* instrument and table serial numbers in every shape ArgyllCMS and the helper
  print them (``Serial Number:     1234567``, ``Serial number = 1234567``,
  ``serial number '1234'``, ``Spectrometer serial number: 12``, JSON
  ``"serial": "..."``, the calibration file names ``.i1p_<n>.cal``,
  ``.i1p3_<n>.cal``, ``.mk_<s>.cal``, the i1Pro 2 ``Chip ID``), Bluetooth and
  network hardware addresses, and UUIDs -> ``<sn:xxxxxxxx>``, a short hash that is
  STABLE on one computer (two lines about the same device still match) and keyed
  with values that never reach the log, so it cannot be turned back into the
  serial by trying every number;
* a run of more than 64 hex digits (the shape of a table's memory answer; a
  SHA-256 is 64 and stays) -> ``<hex:xxxxxxxx n digits>``;
* a printer queue name that CONTAINS the account name (``Bastis_Epson``) ->
  ``<printer:xxxxxxxx>``. Queue names are learned when ChromIQ lists the printers
  (:func:`note_printer_names`); every other queue name stays, because printing
  cannot be diagnosed without it.

WHAT IS NOT REPLACED, AND WHY
* project and target names, run folders, file names under the ChromIQ folder:
  we need them to read a report; a project name the user chose is the user's to
  share (where it contains the account name as a whole word, that word still
  becomes ``<user>``);
* printer queue names without the account name (needed for printing faults);
* instrument models and firmware versions (they name a product, not a person);
* other short numbers (patch counts, dE values, ids of strips) — a number is only
  treated as a serial where a word says it is one.
* the crash log (``chromiq-crash.log``) is written by faulthandler at the C level
  and cannot pass through a Python formatter; it holds stack traces with source
  file paths of the app bundle, not the user's files.

It NEVER raises and NEVER drops a line: on any internal failure the line is still
written, with the home folder replaced the cheap way and ``[scrub failed]`` in
front, so a fault here shows itself without taking a message with it.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import threading

_LOCK = threading.Lock()

_KEEP_HOME_NAMES = {"shared", "public", "default", "all users", "default user", "<user>"}

#: one home-folder component: may hold spaces on macOS and Windows, but then a
#: separator must follow, so "C:\\Users\\ann was" does not swallow "was"
_COMPONENT = (r"(?:[^\\/\s:*?\"<>|]+(?: [^\\/\s:*?\"<>|]+){1,2}(?=[\\/])"
              r"|[^\\/\s:*?\"<>|,;()\[\]{}']+)")
_OTHER_HOME = re.compile(
    r"(?P<pre>(?<![\w.])(?:/Users/|/home/|/private/var/home/|[A-Za-z]:[\\/]+Users[\\/]+|"
    r"[\\/]{2}[^\\/\s]+[\\/]+Users[\\/]+))(?P<name>" + _COMPONENT + ")",
    re.IGNORECASE)

_SERIAL_VALUE = r"(?P<val>(?=[A-Za-z0-9-]*\d)[A-Za-z0-9][A-Za-z0-9-]{2,})"
_SERIALS = [
    # "Serial Number:     1234567", "Serial number = 1234567", "serial number '1234'",
    # "Spectrometer serial number: 12", "serial no. 1234", "serial_no=...", "Serial#1234"
    re.compile(r"(?P<pre>\bserial[ _-]?(?:no\b\.?|number|num\b|nr\b|#)\s*[:=]?\s*['\"]?)"
               + _SERIAL_VALUE, re.IGNORECASE),
    # "serial: 1234", "serial=1234"  (a bare "serial port" has no ':' or '=', so stays)
    re.compile(r"(?P<pre>\bserial\s*[:=]\s*['\"]?)" + _SERIAL_VALUE, re.IGNORECASE),
    # JSON: "serial": "1234", "serial_no": 1234, "serial_number":"..."
    re.compile(r"(?P<pre>[\"']serial(?:[_ -]?(?:no|number|num))?[\"']\s*:\s*[\"']?)"
               + _SERIAL_VALUE, re.IGNORECASE),
    # the calibration files ArgyllCMS keeps per instrument: .i1p_<n>.cal .i1p3_<n>.cal .mk_<s>.cal
    re.compile(r"(?P<pre>\.(?:i1p3?|mk|ex1|i1d3|cmk)_)(?P<val>[A-Za-z0-9-]+)(?=\.cal\b)",
               re.IGNORECASE),
    # i1Pro 2 "Chip ID:           a1-b2c3d4e5f6a7b8"
    re.compile(r"(?P<pre>\bchip[ _-]?id\s*[:=]?\s*)(?P<val>[0-9A-Fa-f][0-9A-Fa-f-]{5,})",
               re.IGNORECASE),
]
_MAC = re.compile(r"(?<![0-9A-Fa-f:-])(?P<val>(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})(?![0-9A-Fa-f:-])")
_UUID = re.compile(r"(?<![0-9A-Fa-f-])(?P<val>[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
                   r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})(?![0-9A-Fa-f-])")
_LONG_HEX = re.compile(r"[0-9A-Fa-f]{65,}")


class _Identity:
    """Who this account is, found once (cheap calls only: no subprocess, no network)."""

    def __init__(self) -> None:
        self.homes: "list[str]" = []
        self.names: "list[str]" = []
        self.phrases: "list[str]" = []
        self.hosts: "list[str]" = []
        self.key = b"chromiq"
        self.printers: "dict[str, str]" = {}
        self._find()
        self._compile()

    def _find(self) -> None:
        homes, names, phrases, hosts = set(), set(), set(), set()
        try:
            h = os.path.expanduser("~")
            if h and h not in ("~", "/", "\\"):
                homes.add(h)
                try:
                    homes.add(os.path.realpath(h))
                except Exception:      # noqa: BLE001
                    pass
                base = os.path.basename(h.rstrip("\\/"))
                if base:
                    names.add(base)
        except Exception:      # noqa: BLE001
            pass
        for env in ("USERPROFILE", "HOME"):
            v = os.environ.get(env, "")
            if v and v not in ("/", "\\"):
                homes.add(v)
        for env in ("USER", "USERNAME", "LOGNAME"):
            v = os.environ.get(env, "")
            if v:
                names.add(v)
        try:
            import getpass
            v = getpass.getuser()
            if v:
                names.add(v)
        except Exception:      # noqa: BLE001
            pass
        try:
            import pwd  # POSIX only
            gecos = (pwd.getpwuid(os.getuid()).pw_gecos or "").split(",")[0].strip()
            if gecos and len(gecos) >= 3:
                phrases.add(gecos)
        except Exception:      # noqa: BLE001
            pass
        try:
            import socket
            host = socket.gethostname() or ""
            if host and host.lower() not in ("localhost", "localhost.localdomain"):
                hosts.add(host)
                short = host.split(".")[0]
                # a short name like "Mac" or "office" is an ordinary word:
                # replaced only in its full dotted form, unless it looks like
                # a name of its own ("Bastis-Mac-mini", "pc42", "anna-pc")
                if short != host and len(short) >= 6 and (
                        "-" in short or any(c.isdigit() for c in short)
                        or any(n.lower() in short.lower() for n in names if len(n) >= 3)):
                    hosts.add(short)
        except Exception:      # noqa: BLE001
            pass
        # Windows spellings of each home: both slash forms
        for h in list(homes):
            if "\\" in h:
                homes.add(h.replace("\\", "/"))
        self.homes = sorted({h.rstrip("\\/") for h in homes if len(h.rstrip("\\/")) > 1},
                            key=len, reverse=True)
        self.names = sorted({n for n in names if n}, key=len, reverse=True)
        self.phrases = sorted(phrases - names, key=len, reverse=True)
        self.hosts = sorted(hosts, key=len, reverse=True)
        self.key = ("\x00".join(self.homes + self.names + self.hosts)
                    + "\x00chromiq-log").encode("utf-8", "replace")

    def _compile(self) -> None:
        def alt(items):
            return "|".join(re.escape(i) for i in items)
        flags = re.IGNORECASE if os.name == "nt" else 0
        # a home folder is replaced only at a path boundary ("/Users/basti2" is
        # somebody else's folder, not ours with a "2" after it)
        self.home_re = (re.compile(r"(?:" + alt(self.homes) + r")(?=$|[\\/\s'\":,;)\]}])", flags)
                        if self.homes else None)
        words = [n for n in self.names if len(n) >= 3]
        self.word_re = (re.compile(r"(?<!\w)(?:" + alt(words) + r")(?!\w)", re.IGNORECASE)
                        if words else None)
        self.phrase_re = (re.compile(r"(?<!\w)(?:" + alt(self.phrases) + r")(?!\w)", re.IGNORECASE)
                          if self.phrases else None)
        self.host_re = (re.compile(r"(?<![\w.-])(?:" + alt(self.hosts) + r")(?:\.local)?(?![\w-])",
                                   re.IGNORECASE) if self.hosts else None)
        self.lower_names = [n.lower() for n in self.names if len(n) >= 3]
        self._compile_printers()

    def _compile_printers(self) -> None:
        bad = sorted(self.printers, key=len, reverse=True)
        self.printer_re = (re.compile("|".join(re.escape(p) for p in bad)) if bad else None)

    def tag(self, kind: str, value: str) -> str:
        digest = hmac.new(self.key, value.strip().lower().encode("utf-8", "replace"),
                          hashlib.sha256).hexdigest()[:8]
        return f"<{kind}:{digest}>"


_ID: "_Identity | None" = None


def _identity() -> _Identity:
    global _ID
    if _ID is None:
        with _LOCK:
            if _ID is None:
                _ID = _Identity()
    return _ID


def reset_for_tests(**override) -> _Identity:
    """Rebuild the identity, optionally with fixed values (tests only):
    ``homes``, ``names``, ``phrases``, ``hosts``, ``printers``."""
    global _ID
    with _LOCK:
        ident = _Identity()
        for k, v in override.items():
            if k == "printers":
                continue
            setattr(ident, k, list(v))
        if override:
            ident.key = ("\x00".join(ident.homes + ident.names + ident.hosts)
                         + "\x00chromiq-log").encode("utf-8", "replace")
            ident.homes = sorted({h.rstrip("\\/") for h in ident.homes}, key=len, reverse=True)
            ident.names = sorted(set(ident.names), key=len, reverse=True)
            ident._compile()
        _ID = ident
    if "printers" in override:
        note_printer_names(override["printers"])
    return ident


def note_printer_names(names) -> None:
    """Tell the filter the queue names ChromIQ found. Only a queue whose name
    contains the account name (case-insensitive, also inside a word) is ever
    replaced. Never raises."""
    try:
        ident = _identity()
        changed = False
        for name in names or ():
            n = str(name or "")
            if not n or n in ident.printers:
                continue
            low = n.lower()
            if any(u in low for u in ident.lower_names):
                ident.printers[n] = ident.tag("printer", n)
                changed = True
        if changed:
            ident._compile_printers()
    except Exception:      # noqa: BLE001
        pass


def scrub(text: str) -> str:
    """The line with everything private replaced (see the module text)."""
    s = str(text)
    ident = _identity()
    if ident.printer_re is not None:
        s = ident.printer_re.sub(lambda m: ident.printers.get(m.group(0), "<printer>"), s)
    if ident.home_re is not None:
        s = ident.home_re.sub("~", s)

    def _other(m):
        name = m.group("name")
        if name.strip().lower() in _KEEP_HOME_NAMES:
            return m.group(0)
        return m.group("pre") + "<user>"
    s = _OTHER_HOME.sub(_other, s)
    if ident.phrase_re is not None:
        s = ident.phrase_re.sub("<user>", s)
    if ident.word_re is not None:
        s = ident.word_re.sub("<user>", s)
    if ident.host_re is not None:
        s = ident.host_re.sub("<computer>", s)
    for rx in _SERIALS:
        s = rx.sub(lambda m: m.group("pre") + ident.tag("sn", m.group("val")), s)
    s = _MAC.sub(lambda m: ident.tag("sn", m.group("val")), s)
    s = _UUID.sub(lambda m: ident.tag("sn", m.group("val")), s)
    s = _LONG_HEX.sub(lambda m: ident.tag("hex", m.group(0))[:-1] + f" {len(m.group(0))} digits>", s)
    return s


def safe_scrub(text) -> str:
    """:func:`scrub` that never raises: on a fault the line is kept, the home
    folder replaced the cheap way, and ``[scrub failed]`` put in front."""
    try:
        return scrub(text)
    except Exception:      # noqa: BLE001
        try:
            s = str(text)
            home = os.path.expanduser("~")
            if home and home not in ("~", "/"):
                s = s.replace(home, "~")
            return "[scrub failed] " + s
        except Exception:      # noqa: BLE001
            return "[scrub failed] <line could not be shown>"


class ScrubbingFormatter(logging.Formatter):
    """A Formatter whose whole output (message, arguments, traceback) passes
    :func:`safe_scrub`. A Formatter rather than a Filter, so the record other
    handlers (pytest's caplog) see is not changed under them."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            line = super().format(record)
        except Exception:      # noqa: BLE001  # a bad %-format must not lose the line
            try:
                line = f"{record.levelname} {record.name}: {record.msg!r} {record.args!r}"
            except Exception:      # noqa: BLE001
                line = "<a log line that could not be formatted>"
        return safe_scrub(line)
