"""Device values outside 0..100 in a patch set somebody else made (4.3.26).

A printer prints every colorant from 0 % to 100 %, and ChromIQ's own
generators never write anything else. A patch set made by another program
can: jctay (printerknowledge forum, 2026-11-07) loaded a .ti1 with a red of
-23.1373 and a value of 104. Nothing agreed on what that patch was:

* ArgyllCMS's printtarg wraps a value outside 0..100 round: -23.14 % was
  printed as 196 of 255, a light colour instead of none, and 104 % as 10;
* colprof, the .ti2 and every export took -23.14 as it was;
* the ChromIQ layout engine and the i1Profiler exports clamped it to 0.

So the RUN'S COPY of such a patch set is held inside 0..100 before anything
is laid out (``chart_creator.load_ti1_and_generate_preview``): the TIFF, the
.ti2, the exports, the readings, colprof and printtarg then all name the patch
that is really printed. The person's own file is never touched, and the
person is told which values were changed (M-CHART-DEVICE-VALUES-CLAMPED).

A file with every value in range comes back byte for byte as it went in.

For a run that already holds such a chart the comparisons that pair a
measurement with its chart compare against the clamped value too
(:func:`clip_0_100`; ``unified_measurement_management.md`` §I.16).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"\S+")
#: The real minus sign, so "−23.14" does not read as a dash in the warning.
MINUS = "−"


@dataclass(frozen=True)
class Change:
    """One device value that was outside 0..100 and what it became."""
    sample_id: str
    loc: str          # SAMPLE_LOC, or "" when the file has none (a .ti1)
    channel: str      # the field's letter: "R", "C", "O" ...
    space: str        # "RGB", "CMYK", "CMYKOGV" ...
    old_text: str     # the value exactly as the file wrote it
    old: float
    new: float


def _device_prefix(color_rep: str, fields: "list[str]") -> str:
    """The prefix of the device fields ("RGB", "CMYK", "CMYKOGV" ...).

    COLOR_REP is "iRGB" in a .ti1, "RGB_XYZ" in a .ti2 or .ti3; the device
    part is before the underscore, without Argyll's "i" (inverted) mark."""
    rep = color_rep.strip().strip('"').split("_")[0]
    if rep.startswith("i") and rep[1:].isupper():
        rep = rep[1:]
    if rep and any(f.startswith(rep + "_") for f in fields):
        return rep
    for guess in ("RGB", "CMYK"):
        if any(f.startswith(guess + "_") for f in fields):
            return guess
    return ""


def clamp_text(text: str) -> "tuple[str, list[Change]]":
    """*text* (a CGATS .ti1 / .ti2) with every device value held inside
    0..100, and the list of what changed.

    Only the changed numbers are rewritten, each keeping the number of
    decimals it had ("-23.1373" becomes "0.0000", "104" becomes "100"); every
    other byte stays as it was, so a file with nothing to change comes back
    identical."""
    color_rep = ""
    fields: "list[str]" = []
    in_format = in_data = False
    out_lines: "list[str]" = []
    changes: "list[Change]" = []
    prefix = ""
    for line in text.splitlines(keepends=True):
        s = line.strip()
        if not in_data and s.startswith("COLOR_REP"):
            color_rep = s[len("COLOR_REP"):].strip()
        if s == "BEGIN_DATA_FORMAT":
            in_format, fields = True, []
        elif s == "END_DATA_FORMAT":
            in_format = False
            prefix = _device_prefix(color_rep, fields)
        elif in_format:
            fields += s.split()
        elif s == "BEGIN_DATA":
            in_data = True
        elif s == "END_DATA":
            in_data = False
        elif in_data and prefix and s:
            line = _clamp_line(line, fields, prefix, changes)
        out_lines.append(line)
    return "".join(out_lines), changes


def _clamp_line(line: str, fields: "list[str]", prefix: str,
                changes: "list[Change]") -> str:
    spans = [(m.start(), m.end(), m.group()) for m in _TOKEN.finditer(line)]
    if len(spans) != len(fields):
        return line
    vals = dict(zip(fields, (t for _a, _b, t in spans)))
    sid = vals.get("SAMPLE_ID", "").strip('"')
    loc = vals.get("SAMPLE_LOC", "").strip('"')
    edits = []
    for (a, b, tok), name in zip(spans, fields):
        if not name.startswith(prefix + "_"):
            continue
        try:
            v = float(tok)
        except ValueError:
            continue
        if 0.0 <= v <= 100.0:
            continue
        new = 0.0 if v < 0.0 else 100.0
        decimals = len(tok.split(".", 1)[1]) if "." in tok else 0
        edits.append((a, b, f"{new:.{decimals}f}"))
        changes.append(Change(sid, loc, name[len(prefix) + 1:], prefix, tok,
                              v, new))
    for a, b, new_tok in reversed(edits):
        line = line[:a] + new_tok + line[b:]
    return line


def clamp_bytes(data: bytes) -> "tuple[bytes, list[Change]]":
    """:func:`clamp_text` for the bytes of a file; the bytes come back as
    they were when nothing changes (or the file is not text)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = data.decode("latin-1")
        except UnicodeDecodeError:          # pragma: no cover
            return data, []
        enc = "latin-1"
    else:
        enc = "utf-8"
    new, changes = clamp_text(text)
    if not changes:
        return data, []
    return new.encode(enc), changes


def changes_in(path: "str | Path") -> "list[Change]":
    """What :func:`clamp_bytes` would change in the file at *path*, without
    changing it. An unreadable file has nothing to say."""
    try:
        return clamp_bytes(Path(path).read_bytes())[1]
    except OSError:
        return []


def clip_0_100(arr):
    """A 0..100 device array held inside 0..100, for the comparisons that
    pair a measurement with its chart (§I.16)."""
    import numpy as np
    return np.clip(np.asarray(arr, dtype=float), 0.0, 100.0)


def _number(text: str) -> str:
    """The value as the file wrote it, with a real minus sign."""
    t = text.strip()
    return MINUS + t[1:] if t.startswith("-") else t


def _new_number(v: float) -> str:
    return "0" if v == 0.0 else "100"


def _words() -> "dict[str, dict[str, str]]":
    """The colorant each device field letter stands for, in the words the
    warning uses (literal ``tr()`` calls, so every language has them)."""
    from core.i18n import tr
    inks = {"C": tr("cyan"), "M": tr("magenta"), "Y": tr("yellow"),
            "K": tr("black"), "O": tr("orange"), "G": tr("green"),
            "V": tr("violet"), "R": tr("red"), "B": tr("blue")}
    return {"RGB": {"R": tr("red"), "G": tr("green"), "B": tr("blue")},
            "CMYK": inks}


def channel_word(change: Change) -> str:
    """"red", "cyan" ... translated; the bare letter for an ink not known."""
    words = _words()
    table = words.get(change.space) or (
        words["CMYK"] if change.space.startswith("CMYK") else {})
    return table.get(change.channel, change.channel)


def change_line(change: Change) -> str:
    """"Patch 13 (C1): red −23.1373 → 0", in the person's language."""
    from core.i18n import tr
    if change.loc:
        return tr("Patch {id} ({loc}): {colour} {old} → {new}").format(
            id=change.sample_id, loc=change.loc, colour=channel_word(change),
            old=_number(change.old_text), new=_new_number(change.new))
    return tr("Patch {id}: {colour} {old} → {new}").format(
        id=change.sample_id, colour=channel_word(change),
        old=_number(change.old_text), new=_new_number(change.new))


#: How many changed values the warning lists one by one; the rest are counted.
LISTED = 40


def change_list(changes: "list[Change]") -> str:
    from core.i18n import tr
    lines = [change_line(c) for c in changes[:LISTED]]
    rest = len(changes) - LISTED
    if rest == 1:
        lines.append(tr("and 1 more value"))
    elif rest > 1:
        lines.append(tr("and {n} more values").format(n=rest))
    return "\n".join(lines)


def warning(changes: "list[Change]", file_name: str) -> "tuple[str, str]":
    """(title, body) of M-CHART-DEVICE-VALUES-CLAMPED."""
    from workflow.measurement_messages import M_CHART_DEVICE_VALUES_CLAMPED
    return M_CHART_DEVICE_VALUES_CLAMPED.render(
        count=len(changes), file=file_name, changes=change_list(changes))


def log_line(changes: "list[Change]") -> str:
    """The Create Chart log's line for the run's copy."""
    from core.i18n import tr
    return tr("Values outside 0 to 100 were set to the nearest printable "
              "value in this run's copy of the patch set (your own file is "
              "unchanged): {changes}").format(
        changes="; ".join(change_line(c) for c in changes))
