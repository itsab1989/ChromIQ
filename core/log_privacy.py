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
* the account name (and the home folder's own name, when it differs), and the
  first and the last name from the account database, as a WHOLE WORD and in
  their possessive and joined forms ("Bastis AirPods", "Basti's iPhone",
  "/dev/cu.Bastis-AirPods", "basti_test"), case-insensitive, unicode-aware ->
  ``<user>`` (the possessive tail is kept: ``<user>s AirPods``). A word that
  merely contains it is left alone ("bastion" stays for the account "basti").
  A name that is also an ordinary word (``max``, ``test``, ``mark``: the list
  ``_COMMON``) is NOT replaced as a free word, only as a path component, with
  an apostrophe ("Max's"), and possessive or joined before a device word
  ("Maxs AirPods", "/dev/cu.max-iPhone"); so for such an account the name as a
  free word, and joined to anything but a device word ("max_project"), stays
  in the log. Names
  shorter than three letters are replaced only inside the home paths above,
  never as words, since a one- or two-letter word occurs everywhere;
* the full name from the account database, as a whole phrase -> ``<user>``;
* this computer's own name as a whole word (``Bastis-Mac-mini``,
  ``Bastis-Mac-mini.local``) -> ``<computer>``; a short name that is an ordinary
  word ("Mac", from "Mac.fritz.box") only in its full dotted form;
* instrument and table serial numbers in every shape ArgyllCMS and the helper
  print them (``Serial Number:     1234567``, ``Serial number = 1234567``,
  ``serial number '1234'``, ``Spectrometer serial number: 12``, JSON
  ``"serial": "..."``, a bare ``serial CM454M0223``, ``USB serial string:``,
  ``S/N 1234567``, CxF ``...SerialNumber>``, the calibration file names
  ``.i1p_<n>.cal``, ``.i1p3_<n>.cal``, ``.mk_<s>.cal``, the i1Pro 2 ``Chip ID``
  and Argyll's ``getchipid: returning ...``, the CR30's ``internal id`` and the
  id string it names itself by after ``unit`` / ``calls itself``), Bluetooth and
  network hardware addresses, and UUIDs -> ``<sn:xxxxxxxx>``, a short hash that is
  STABLE on one computer (two lines about the same device still match) and keyed
  with a random salt made once per install and kept in the settings (never in
  the log), so it cannot be turned back into the serial by trying every number;
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
  and cannot pass through a Python formatter while it is written; its stacks
  name source file paths (with the account name for a source run or an app in
  the home folder). It is passed through this filter at the NEXT start, before
  faulthandler opens it (``core.crash_log.clean_previous``), so a crash log
  sent before ChromIQ is started again is not cleaned.

OLDER LOGS (M3): ``chromiq.log`` is appended to and rotated. At the first start
of a build with this filter, the log and its rotated copies are passed through
it once (:func:`clean_old_logs`, atomic replace, the original kept on any
failure), and a line in the new log says so.

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

#: a value a word labels as a serial: two or more characters, at least one digit
_SERIAL_VALUE = r"(?P<val>(?=[A-Za-z0-9-]*\d)[A-Za-z0-9][A-Za-z0-9-]{1,})"
#: a value after a bare "serial" (no ":" or "number"): four or more, one digit,
#: so "serial port" and "serial 2" stay
_BARE_VALUE = r"(?P<val>(?=[A-Za-z0-9-]*\d)[A-Za-z0-9][A-Za-z0-9-]{3,})"
_SERIALS = [
    # "Serial Number:     1234567", "Serial number = 1234567", "serial number '1234'",
    # "Spectrometer serial number: 12", "serial no. 1234", "serial_no=...", "Serial#1234",
    # "USB serial string: ..."
    re.compile(r"(?P<pre>\bserial[ _-]?(?:no\b\.?|number|num\b|nr\b|string|str\b|#)"
               r"\s*[:=]?\s*['\"]?)" + _SERIAL_VALUE, re.IGNORECASE),
    # "serial: 1234", "serial=1234"  (a bare "serial port" has no ':' or '=', so stays)
    re.compile(r"(?P<pre>\bserial\s*[:=]\s*['\"]?)" + _SERIAL_VALUE, re.IGNORECASE),
    # a bare "serial CM454M0223" (the CR30's connect line said exactly that)
    re.compile(r"(?P<pre>(?<![\w<])serial\s+['\"]?)" + _BARE_VALUE, re.IGNORECASE),
    # JSON: "serial": "1234", "serial_no": 1234, "serial_number":"..."
    re.compile(r"(?P<pre>[\"']serial(?:[_ -]?(?:no|number|num))?[\"']\s*:\s*[\"']?)"
               + _SERIAL_VALUE, re.IGNORECASE),
    # CxF / XML / camelCase: <MeasurementDeviceSerialNumber>1234</...>, SerialNumber="1234"
    re.compile(r"(?P<pre>(?<=[a-z])Serial(?:Number|No|Num)?\s*(?:>|=\s*[\"']|:\s*[\"']?))"
               + _SERIAL_VALUE),
    # the calibration files ArgyllCMS keeps per instrument: .i1p_<n>.cal .i1p3_<n>.cal .mk_<s>.cal
    re.compile(r"(?P<pre>\.(?:i1p3?|mk|ex1|i1d3|cmk)_)(?P<val>[A-Za-z0-9-]+)(?=\.cal\b)",
               re.IGNORECASE),
    # i1Pro 2 "Chip ID:           a1-b2c3d4e5f6a7b8", Argyll's debug
    # "i1pro3_getchipid: returning 01-23456789ABCDEF"
    re.compile(r"(?P<pre>chip[ _-]?id\b\s*[:=]?\s*(?:returning\s+)?['\"]?)"
               r"(?P<val>[0-9A-Fa-f][0-9A-Fa-f-]{5,})", re.IGNORECASE),
    # the CR30's "internal id PT694D01E7" (a device identifier like the serial)
    re.compile(r"(?P<pre>\binternal[ _-]?id\s*[:=]?\s*['\"]?)" + _SERIAL_VALUE,
               re.IGNORECASE),
]
#: "S/N 1234567" (Argyll's white-reference prompt), "SN: 1234567": upper case
#: only, so the word "sn" in a sentence or a "<sn:...>" tag is never touched
_SN = re.compile(r"(?P<pre>(?<![\w/<])S/?N\b\.?\s*[:#=]?\s*['\"]?)" + _SERIAL_VALUE)
#: a CR30 names itself by its id string ("CM454M0223"): after "unit" or
#: "calls itself", a run of upper-case letters AND digits, 6 to 16 long
_UNIT_ID = re.compile(r"(?P<pre>\b(?:[Uu]nit|calls itself)\s+['\"]?)"
                      r"(?P<val>(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6,16})(?![A-Za-z0-9])")
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
        #: the HMAC key of the short hashes; made from the per-install salt at
        #: the first hash (S5, :func:`_install_salt`)
        self.key: "bytes | None" = None
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
        full = ""
        try:
            import pwd  # POSIX only
            full = (pwd.getpwuid(os.getuid()).pw_gecos or "").split(",")[0].strip()
        except Exception:      # noqa: BLE001
            pass
        if not full and os.name == "nt":
            full = _windows_display_name()
        given = set()
        if full and len(full) >= 3:
            phrases.add(full)
            given = set(_name_parts(full))
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
        self.names = sorted({n for n in names | given if n}, key=len, reverse=True)
        self.phrases = sorted(phrases - names - given, key=len, reverse=True)
        self.hosts = sorted(hosts, key=len, reverse=True)

    def _compile(self) -> None:
        def alt(items):
            return "|".join(re.escape(i) for i in items)
        flags = re.IGNORECASE if os.name == "nt" else 0
        # a home folder is replaced only at a path boundary ("/Users/basti2" is
        # somebody else's folder, not ours with a "2" after it)
        self.home_re = (re.compile(r"(?:" + alt(self.homes) + r")(?=$|[\\/\s'\":,;)\]}])", flags)
                        if self.homes else None)
        all_words = [n for n in self.names if len(n) >= 3]
        common = _common_words()
        # S4 (4.3.50): a name that is also an ordinary word ("max", "test",
        # "mark") is never replaced as a free word, only where it can only be
        # a name: as a path component, possessive with an apostrophe, and
        # possessive or joined in front of a device word ("Maxs AirPods",
        # "/dev/cu.max-iPhone")
        words = [n for n in all_words if n.lower() not in common]
        self.common_names = [n for n in all_words if n.lower() in common]
        self.common_re = None
        if self.common_names:
            c = alt(self.common_names)
            self.common_re = re.compile(
                r"(?<=[\\/])(?:" + c + r")(?=[\\/])"
                r"|(?<![^\W_])(?:" + c + r")(?P<apos>['\u2019]s)(?!\w)"
                r"|(?<![^\W_])(?:" + c + r")(?P<dev>s?[ _.-]+(?:" + _DEVICE_WORDS + r"))(?!\w)",
                re.IGNORECASE)
        # M2 (4.3.50): a name is a word on its own AND in its possessive and
        # joined forms: "Bastis AirPods", "Basti's iPhone", "Basti’s",
        # "/dev/cu.Bastis-AirPods", "basti_test". An underscore separates here
        # (it joins a device or queue name); a letter or digit does not, so
        # "bastion", "xbasti" and "/Users/basti2" stay. The tail is kept:
        # "<user>s AirPods".
        self.word_re = (re.compile(r"(?<![^\W_])(?:" + alt(words) + r")(?P<tail>['\u2019]s|s)?"
                                   r"(?![^\W_])", re.IGNORECASE)
                        if words else None)
        self.rare_lower = [n.lower() for n in words]
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
        if self.key is None:
            self.key = (_install_salt() + "\x00chromiq-log").encode("utf-8", "replace")
        digest = hmac.new(self.key, value.strip().lower().encode("utf-8", "replace"),
                          hashlib.sha256).hexdigest()[:8]
        return f"<{kind}:{digest}>"


def _name_parts(full: str) -> "list[str]":
    """M2 (4.3.50): the first and the last name of a full name, each as a word
    of three letters or more: macOS names a device "<First>s AirPods" /
    "<First>'s iPhone"."""
    out = []
    for part in re.split(r"[\s,]+", str(full or "")):
        part = part.strip(".-'")
        if len(part) >= 3 and part.replace("-", "").isalpha():
            out.append(part)
    return out


#: S4: words a device is named with after its owner's name (macOS, Windows,
#: Android, Bluetooth headsets): only before one of these is a name that is
#: also an ordinary word treated as a name without an apostrophe
_DEVICE_WORDS = (r"iPhone|iPad|iPod|iMac|Mac|MacBook|MacBook[ _-]?(?:Pro|Air)|Mac[ _-]?mini|"
                 r"Mac[ _-]?Studio|Mac[ _-]?Pro|AirPods|AirPods[ _-]?(?:Pro|Max)|"
                 r"Apple[ _-]?Watch|Watch|Galaxy|Pixel|Phone|Handy|Laptop|PC|Desktop|"
                 r"Notebook|Headphones|Kopfh\u00f6rer|Beats|Buds|Speaker|Lautsprecher|"
                 r"Surface|ThinkPad|Kindle|Tablet|TV|Magic[ _-]?(?:Mouse|Keyboard|Trackpad)")

#: S4: ordinary words an account may be named (the review saw max, mark, test,
#: user, admin, mac, print, office). A fixed list, not the app's own texts:
#: those name people too (credits, contributors), and a first name must stay a
#: name. Some entries are also first names (mark, will, frank): for such an
#: account the free word stays, which is the price of not mangling the log.
_COMMON = frozenset("""
max min mark test tester user users admin administrator mac print printer office guest
home root dev data demo info light white black grey gray color colour paper chart patch
strip read scan table sample profile target new old red green blue owner studio design
photo work main local system server default setup lab art will may rose page bill frank
grant joy hope sky ray dean sun star king pro mini air book ink media image images shop
master temp tmp public shared support service apple""".split())


def _common_words() -> "frozenset[str]":
    return _COMMON


_SALT_LOADING = threading.local()
_PROCESS_SALT: "str | None" = None


def _install_salt() -> str:
    """S5 (4.3.50): the salt of the short hashes, random and made once per
    install, kept in the settings (``log_privacy_salt``, never logged). The
    key used to be the home folder, the account name and the host name: all
    scrubbed from the log, but none secret from someone who knows the tester,
    and a 7-digit serial is ten million HMACs, seconds of work. A random salt
    keeps the code stable on one computer and unguessable elsewhere. When the
    settings cannot be reached a salt for this process is used (stable within
    the session). Never raises."""
    global _PROCESS_SALT
    if getattr(_SALT_LOADING, "on", False):      # a log line while loading it
        return _process_salt()
    _SALT_LOADING.on = True
    try:
        from core.settings import log_privacy_salt
        v = log_privacy_salt()
        if v:
            return v
    except Exception:      # noqa: BLE001
        pass
    finally:
        _SALT_LOADING.on = False
    return _process_salt()


def _process_salt() -> str:
    global _PROCESS_SALT
    if _PROCESS_SALT is None:
        import secrets
        _PROCESS_SALT = secrets.token_hex(16)
    return _PROCESS_SALT


def _windows_display_name() -> str:
    """The account's display name on Windows (GetUserNameExW, NameDisplay):
    a cheap call, no process. "" when unknown."""
    try:
        import ctypes
        size = ctypes.c_ulong(0)
        fn = ctypes.windll.secur32.GetUserNameExW   # type: ignore[attr-defined]
        fn(3, None, ctypes.byref(size))
        if not size.value:
            return ""
        buf = ctypes.create_unicode_buffer(size.value + 1)
        if fn(3, buf, ctypes.byref(size)):
            return buf.value.strip()
    except Exception:      # noqa: BLE001
        pass
    return ""


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
        if "phrases" in override:
            parts = [p for ph in ident.phrases for p in _name_parts(ph)]
            ident.names = list(ident.names) + [p for p in parts if p not in ident.names]
        if override:
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
            if any(u in low for u in ident.rare_lower) or (
                    ident.common_re is not None and ident.common_re.search(n)):
                ident.printers[n] = ident.tag("printer", n)
                changed = True
        if changed:
            ident._compile_printers()
    except Exception:      # noqa: BLE001
        pass


def device_tag(value) -> str:
    """A device identifier (serial, internal id, the id string a CR30 names
    itself by, a Bluetooth address) as the log shows it: ``<sn:xxxxxxxx>``, the
    same short hash the filter gives it, so a call site never has to format the
    raw value into a line. ``?`` for an empty value. Never raises."""
    try:
        v = str(value or "").strip()
        if not v:
            return "?"
        return _identity().tag("sn", v)
    except Exception:      # noqa: BLE001
        return "<sn>"


def scrub(text: str) -> str:
    """The line with everything private replaced (see the module text).

    Each rule runs only when a cheap substring test says it can match (most
    lines match none), so an ordinary line costs a few microseconds."""
    s = str(text)
    ident = _identity()
    low = s.lower()
    if ident.printer_re is not None and any(p in s for p in tuple(ident.printers)):
        s = ident.printer_re.sub(lambda m: dict(ident.printers).get(m.group(0), "<printer>"), s)
    if ident.home_re is not None and any(h.lower() in low for h in ident.homes):
        s = ident.home_re.sub("~", s)
        low = s.lower()

    def _other(m):
        name = m.group("name")
        if name.strip().lower() in _KEEP_HOME_NAMES:
            return m.group(0)
        return m.group("pre") + "<user>"
    if "users" in low or "/home/" in low:
        s = _OTHER_HOME.sub(_other, s)
    if ident.phrase_re is not None and any(p.lower() in low for p in ident.phrases):
        s = ident.phrase_re.sub("<user>", s)
    # the computer's name before the words: "Bastis-Mac-mini" is a computer
    if ident.host_re is not None and any(h.lower() in low for h in ident.hosts):
        s = ident.host_re.sub("<computer>", s)
        low = s.lower()
    if any(n in low for n in ident.lower_names):
        if ident.word_re is not None:
            s = ident.word_re.sub(lambda m: "<user>" + (m.group("tail") or ""), s)
        if ident.common_re is not None:
            s = ident.common_re.sub(
                lambda m: "<user>" + (m.group("apos") or m.group("dev") or ""), s)
    def _sn(m):
        return m.group("pre") + ident.tag("sn", m.group("val"))
    if "serial" in low or ".cal" in low or "chip" in low or "internal" in low:
        for rx in _SERIALS:
            s = rx.sub(_sn, s)
    if "SN" in s or "S/N" in s:
        s = _SN.sub(_sn, s)
    if "unit" in low or "itself" in low:
        s = _UNIT_ID.sub(_sn, s)
    if s.count(":") >= 5 or s.count("-") >= 4:
        s = _MAC.sub(lambda m: ident.tag("sn", m.group("val")), s)
        s = _UUID.sub(lambda m: ident.tag("sn", m.group("val")), s)
    if len(s) > 64:
        s = _LONG_HEX.sub(lambda m: ident.tag("hex", m.group(0))[:-1]
                          + f" {len(m.group(0))} digits>", s)
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


# --------------------------------------------------------------------------
# M3 (4.3.50): the log a tester sends after updating still held every older
# session unscrubbed (chromiq.log is appended to and rotated, five copies).
# At the first start of a build with the filter, each of those files passes
# through the same filter once. The crash log is cleaned at every start,
# before faulthandler opens it (its stacks name source paths).
# --------------------------------------------------------------------------

#: raised when what the filter removes changes enough that old logs should be
#: cleaned again (the marker file holds the version it was cleaned with)
CLEAN_VERSION = 1
CLEAN_MARKER = "chromiq-log-cleaned"


def clean_file(path) -> "tuple[int, str | None]":
    """Pass one log file through :func:`safe_scrub`, line by line, and replace
    it ATOMICALLY (a temporary file beside it, then ``os.replace``). Returns
    ``(lines changed, None)``, or ``(0, "<why>")`` when it could not be done:
    the original is then left exactly as it was. Bytes that are not UTF-8 are
    kept as they are. Never raises."""
    from pathlib import Path
    p = Path(path)
    tmp = p.with_name(p.name + ".cleaning")
    try:
        raw = p.read_bytes()
        text = raw.decode("utf-8", "surrogateescape")
        out, changed = [], 0
        for ln in text.splitlines(keepends=True):
            body = ln.rstrip("\r\n")
            end = ln[len(body):]
            new = safe_scrub(body) if body else body
            if new != body:
                changed += 1
            out.append(new + end)
        if not changed:
            return 0, None
        data = "".join(out).encode("utf-8", "surrogateescape")
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)
        return changed, None
    except Exception as exc:      # noqa: BLE001
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:      # noqa: BLE001
            pass
        return 0, f"{type(exc).__name__}: {exc}"


def clean_old_logs(directory, name: str = "chromiq.log") -> "dict | None":
    """Once per :data:`CLEAN_VERSION`: clean *name* and its rotated copies
    (``<name>.1`` ...) in *directory*. Returns ``None`` when it was already
    done (or there was nothing), else ``{"cleaned": [(file, lines)],
    "failed": [(file, why)]}``. The marker file is written only when every
    file was cleaned, so a failure is tried again at the next start.
    Never raises; call it BEFORE a handler opens the file."""
    try:
        from pathlib import Path
        d = Path(directory)
        marker = d / CLEAN_MARKER
        try:
            if marker.read_text(encoding="utf-8").strip() == str(CLEAN_VERSION):
                return None
        except OSError:
            pass
        files = [d / name] + sorted(d.glob(name + ".[0-9]*"),
                                    key=lambda q: q.name)
        files = [f for f in files if f.is_file() and f.suffix != ".cleaning"]
        res = {"cleaned": [], "failed": []}
        for f in files:
            n, why = clean_file(f)
            if why:
                res["failed"].append((f.name, why))
            else:
                res["cleaned"].append((f.name, n))
        if not res["failed"]:
            try:
                d.mkdir(parents=True, exist_ok=True)
                marker.write_text(f"{CLEAN_VERSION}\n", encoding="utf-8")
            except OSError as exc:
                res["failed"].append((CLEAN_MARKER, f"{type(exc).__name__}: {exc}"))
        return res if files else (res if res["failed"] else None)
    except Exception as exc:      # noqa: BLE001
        return {"cleaned": [], "failed": [("?", f"{type(exc).__name__}: {exc}")]}


def log_cleaning_result(res, logger=None) -> None:
    """The marker line in the new log: what was cleaned, what could not be.
    Never raises."""
    if not res:
        return
    try:
        lg = logger or logging.getLogger("chromiq.privacy")
        if res.get("cleaned"):
            lg.info("log privacy: the older sessions in this log were passed through the "
                    "privacy filter once (filter version %d): %s", CLEAN_VERSION,
                    ", ".join(f"{f} ({n} lines changed)" for f, n in res["cleaned"]))
        for f, why in res.get("failed") or ():
            lg.warning("log privacy: could not clean %s (%s); the original is kept "
                       "unchanged and will be tried again at the next start", f, why)
    except Exception:      # noqa: BLE001
        pass
