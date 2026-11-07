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

#: A CGATS value: a quoted string (which may hold spaces, as a
#: SAMPLE_NAME "Patch 1" does) or a run of non-space characters.
_TOKEN = re.compile(r'"[^"]*"|\S+')


class UnreadablePatchLine(ValueError):
    """A data line whose values do not match the file's format, so nobody
    can tell which of them are colour values (4.3.26, review r1 L6). Its
    text is the {reason} of the "Couldn't read that patch set" window."""

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


def _code_part(line: str) -> str:
    """*line* without a ``#`` comment, outside quoted values. ArgyllCMS's
    CGATS reader skips a comment line inside the data and a comment after
    the values (review r2, measured: printtarg exits 0 on both)."""
    out, quoted = [], False
    for ch in line:
        if ch == '"':
            quoted = not quoted
        elif ch == "#" and not quoted:
            break
        out.append(ch)
    return "".join(out)


def _tokens(line: str) -> "list[tuple[int, int, str]]":
    return [(m.start(), m.end(), m.group())
            for m in _TOKEN.finditer(_code_part(line))]


def clamp_text(text: str) -> "tuple[str, list[Change]]":
    """*text* (a CGATS .ti1 / .ti2) with every device value of its PATCH
    table held inside 0..100, and the list of what changed.

    Only the changed numbers are rewritten, each keeping the number of
    decimals it had ("-23.1373" becomes "0.0000", "104" becomes "100"); every
    other byte stays as it was, so a file with nothing to change comes back
    identical.

    WHICH TABLE (review r2): the patch table only, the first table of the
    file or any table with a SAMPLE_ID. A .ti2 from printtarg or printcal
    may carry a calibration-curve table (CMYK_I, CMYK_C ...) in which values
    above 100 are legitimate, and a .ti1 carries density tables after its
    patches; neither is touched.

    WHAT A LINE IS (review r2): ArgyllCMS reads the data as a stream of
    values and skips comments, so a comment line, a comment after the
    values, and one patch's values split over two lines are all valid. A
    comment is ignored; when a line's count of values differs from the
    format, the block is read as one stream grouped by the field count, and
    refused (:class:`UnreadablePatchLine`) only when the total is not a
    whole number of patches. Such a block, when something in it is clamped,
    is written back one patch per line."""
    color_rep = ""
    fields: "list[str]" = []
    in_format = in_data = False
    out_lines: "list[str]" = []
    block: "list[str]" = []
    block_start = 0
    changes: "list[Change]" = []
    prefix = ""
    table = -1
    lines = text.splitlines(keepends=True)
    for number, line in enumerate(lines, start=1):
        s = line.strip()
        if in_data:
            if s == "END_DATA":
                in_data = False
                out_lines += _clamp_block(block, fields, prefix, changes,
                                          block_start)
                block = []
                out_lines.append(line)
            else:
                block.append(line)
            continue
        if s.startswith("COLOR_REP"):
            color_rep = s[len("COLOR_REP"):].strip()
        if s == "BEGIN_DATA_FORMAT":
            in_format, fields = True, []
            table += 1
        elif s == "END_DATA_FORMAT":
            in_format = False
            patch_table = table == 0 or "SAMPLE_ID" in fields
            prefix = _device_prefix(color_rep, fields) if patch_table else ""
        elif in_format:
            fields += _code_part(s).split()
        elif s == "BEGIN_DATA":
            in_data, block, block_start = True, [], number + 1
        out_lines.append(line)
    if in_data:                          # no END_DATA: left as it was
        out_lines += block
    return "".join(out_lines), changes


def _clamp_block(block: "list[str]", fields: "list[str]", prefix: str,
                 changes: "list[Change]", first: int) -> "list[str]":
    """The data lines of one table, clamped (see :func:`clamp_text`)."""
    if not prefix or not fields:
        return block
    n = len(fields)
    counts = [len(_tokens(l)) for l in block]
    if all(c in (0, n) for c in counts):
        return [_clamp_line(l, fields, prefix, changes) if c else l
                for l, c in zip(block, counts)]
    # THE STREAM FORM: one patch over several lines, or several on one.
    stream = [t for l in block for _a, _b, t in _tokens(l)]
    if len(stream) % n:
        from core.i18n import tr
        bad = next(i for i, c in enumerate(counts) if c not in (0, n))
        raise UnreadablePatchLine(tr(
            "line {line} of the patch set does not have as many values as "
            "its format names (the line has {got}, the format names {want}), "
            "so ChromIQ cannot tell which of them are the colour values"
        ).format(line=first + bad, got=counts[bad], want=n))
    found: "list[Change]" = []
    ending = next((l[len(l.rstrip("\r\n")):] for l in block
                   if l.endswith(("\n", "\r"))), "\n")
    rows = []
    for i in range(0, len(stream), n):
        row = " ".join(stream[i:i + n]) + ending
        rows.append(_clamp_line(row, fields, prefix, found))
    if not found:
        return block
    changes += found
    return rows


def _clamp_line(line: str, fields: "list[str]", prefix: str,
                changes: "list[Change]") -> str:
    spans = _tokens(line)
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
        # NOT A NUMBER IS NOT 100 (review r1 L6): "nan" compares false with
        # everything and came out as 100. A value that is not a finite number
        # is left exactly as it is, for the patch set's own checks (and
        # ArgyllCMS) to refuse; "inf" is no colour either.
        if v != v or v in (float("inf"), float("-inf")):
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
    changing it. A file that cannot be opened has nothing to say; a data
    line that does not match its format raises :class:`UnreadablePatchLine`."""
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
