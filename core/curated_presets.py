"""Which BUILT-IN presets the Create Chart lists show straight away.

Knut, #182 5818659478 (2026-09-24): *"Users have complained that the current
numbers of presets are too many and they want the amount reduced. This would
though limit an advanced user to have larger charts available."* So nothing is
removed. Every built-in stays in the "Select preset" pulldown and in the
Built-in presets list; the ones that are not ticked wait under a collapsible
arrow placed after the last ticked preset of their group.

Two sources decide what is ticked, and the second always wins:

1. **What ChromIQ ships**, :data:`DEFAULTS_FILE`. A data file, not code, so the
   list Knut's users send back can replace it without touching a line of the
   app. ``scripts/make_preset_defaults.py`` writes it, from the beta rule
   (:func:`beta_selection`) or from a filled-in table.
2. **What this person chose** in the window behind the gear button, stored in
   the setting :data:`SETTING_KEY` as ``{preset key: shown}``.

**ONLY THE PERSON'S OWN DIFFERENCES ARE STORED, NEVER A COPY OF THE
DEFAULTS.** That is what lets a later release change the shipped list without
overwriting anyone: a preset whose box differs from the shipped list keeps the
person's answer, and every other preset follows whatever the release ships.
:func:`store_choices` records a preset exactly while its box differs from the
shipped default, and forgets it the moment the box agrees again (challenge 3
of beta 42, B8-1033): ticking the boxes back to the shipped list by hand left
all 62 of them stored as the person's own answers, so a later release's list
would never have reached that person. A person who opens the window and
closes it without changing anything stores nothing at all.

The key of a preset is its identity (``docs/dev_builtin_presets.md``: *"the
key, not the label, is the identity"*), so renaming a preset keeps both its
shipped default and a person's choice. A stored key that no longer exists is
ignored and kept, harmlessly, in case the preset comes back.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Iterable

from core.logger import get_logger

log = get_logger(__name__)

#: The shipped defaults, relative to the app's resources.
DEFAULTS_FILE = "data/preset_defaults.json"

#: The setting that holds the person's own choices, as a JSON object
#: ``{preset key: bool}``. Empty (the default) means "the shipped list".
SETTING_KEY = "builtin_presets_shown"

#: userData of the arrow row in the "Select preset" pulldown. The group's
#: heading follows the colon. It is not a preset key and never becomes one:
#: :meth:`TabChart._on_preset_selected` refuses it before anything else.
MORE_ROW_PREFIX = "__chromiq_more_presets__:"


def is_more_row(data: Any) -> bool:
    """True for the arrow row's userData, and for nothing a preset carries."""
    return isinstance(data, str) and data.startswith(MORE_ROW_PREFIX)


#: userData of the paper-filter note at the bottom of "Select preset" (Knut,
#: #182 5834773589, B8-1171). Like the arrow row it is not a preset key and
#: never becomes one: :func:`is_not_a_preset` refuses it in the preset handler.
NOTE_ROW_DATA = "__chromiq_presets_note__"


def is_not_a_preset(data: Any) -> bool:
    """True for a row of "Select preset" that is not a preset but carries
    userData: an arrow row, or the paper-filter note."""
    return is_more_row(data) or data == NOTE_ROW_DATA


@lru_cache(maxsize=1)
def shipped_defaults() -> frozenset[str]:
    """The keys ChromIQ ships ticked, read once from :data:`DEFAULTS_FILE`.

    A missing or unreadable file answers "every preset shown" rather than
    "none shown", because an empty pulldown would look like a broken app while
    a long one is merely what every earlier beta did. The caller tells the two
    apart through :func:`defaults_available`.
    """
    from core.resource_path import resource_path
    try:
        doc = json.loads(resource_path(DEFAULTS_FILE).read_text(encoding="utf-8"))
        shown = doc.get("shown", {})
        return frozenset(str(k) for k in shown)
    except (OSError, ValueError, AttributeError, TypeError):
        log.warning("The shipped preset defaults could not be read; every "
                    "built-in preset is shown", exc_info=True)
        return frozenset()


def defaults_available() -> bool:
    return bool(shipped_defaults())


def parse_choices(raw: Any) -> dict[str, bool]:
    """Decode the stored choices; anything malformed is dropped, not raised."""
    if isinstance(raw, dict):
        doc = raw
    else:
        if not raw:
            return {}
        try:
            doc = json.loads(str(raw))
        except (ValueError, TypeError):
            log.warning("Corrupt %s setting, ignoring it", SETTING_KEY)
            return {}
    if not isinstance(doc, dict):
        return {}
    return {str(k): bool(v) for k, v in doc.items() if isinstance(v, bool)}


def user_choices(settings: Any) -> dict[str, bool]:
    try:
        return parse_choices(settings.get(SETTING_KEY, ""))
    except Exception:      # noqa: BLE001 — a settings fake without get()
        return {}


def is_shown_by_default(key: str) -> bool:
    defaults = shipped_defaults()
    return (key in defaults) if defaults else True


def shown_keys(settings: Any, all_keys: Iterable[str]) -> set[str]:
    """The built-ins shown directly: the shipped list, then the person's own
    answers on top."""
    choices = user_choices(settings)
    out = set()
    for key in all_keys:
        if choices.get(key, is_shown_by_default(key)):
            out.add(key)
    return out


def choices_to_store(ticked: Iterable[str], all_keys: Iterable[str],
                     existing: dict[str, bool]) -> dict[str, bool]:
    """What :func:`store_choices` writes, without writing it (the rule above)."""
    ticked = set(ticked)
    out = dict(existing)
    for key in all_keys:
        state = key in ticked
        if state != is_shown_by_default(key):
            out[key] = state
        else:
            # The same as the shipped list is no answer of the person's.
            out.pop(key, None)
    # A key this build does not know is left alone, harmlessly, in case the
    # preset comes back.
    return out


def store_choices(settings: Any, ticked: Iterable[str],
                  all_keys: Iterable[str]) -> bool:
    """Record the window's boxes as the person's choice. Returns whether
    anything was written: nothing is, when what is stored already says it."""
    existing = user_choices(settings)
    out = choices_to_store(ticked, all_keys, existing)
    if out == existing:
        return False
    if out:
        settings.set(SETTING_KEY, json.dumps(out, sort_keys=True))
        return True
    # Nothing of the person's is left: no answer stored at all, exactly as
    # before the window was first opened.
    unset = getattr(settings, "unset", None)
    if callable(unset):
        unset(SETTING_KEY)
    else:
        settings.set(SETTING_KEY, "")
    return True


def split_group(entries: list, shown: set[str]) -> tuple[list, list]:
    """``(ticked, the rest)`` of one group's ``(combo, overlay, key)`` rows, each
    in the group's own order. The arrow goes between the two."""
    top = [e for e in entries if e[2] in shown]
    rest = [e for e in entries if e[2] not in shown]
    return top, rest


# ---------------------------------------------------------------------------
# The beta rule
# ---------------------------------------------------------------------------

#: How many presets the beta rule ticks per instrument group and paper size.
BETA_PER_PAPER = 4
#: Page counts the beta rule may tick: one to four sheets.
BETA_PAGES = (1, 4)


def beta_selection(facts: list[dict]) -> list[str]:
    """Knut's rule for the beta, #182 5818659478: *"pre-select 4 presets for
    each type of paper size and instrument, so that the 4 selected are between
    1 and 4 pages with different patch sizes, but skipping the smallest and the
    largest presets."*

    ``facts`` holds one dict per built-in: ``key``, ``group``, ``paper``,
    ``patches``, ``pages`` and ``width`` (patch width in mm, 0 when the chart
    does not say). Returned in the order given.

    Per (group, paper):

    1. Sort by patch count (then pages, then width, then key, so it is stable).
    2. When the paper has MORE than four presets, drop the one with the fewest
       patches and the one with the most. "Smallest" and "largest" are read as
       patch count, which is what a chart's size is to the person reading it.
       A paper with four or fewer keeps them all: dropping two of three would
       leave a paper with nothing shown.
    3. Keep the ones of one to four sheets.
    4. Four or fewer left: all of them. More: cut the list, still sorted by
       patch count, into four consecutive bands of near-equal length and take
       one per band, so the four spread from small to large. Inside a band the
       pick is the preset whose patch WIDTH is not yet among the picks (so the
       widths differ wherever the paper offers more than one), then the one
       nearest the band's middle.
    """
    by_cell: dict[tuple[str, str], list[dict]] = {}
    for f in facts:
        by_cell.setdefault((f["group"], f["paper"]), []).append(f)
    chosen: set[str] = set()
    for cell in by_cell.values():
        rows = sorted(cell, key=lambda f: (f["patches"], f["pages"],
                                           f.get("width") or 0.0, f["key"]))
        if len(rows) > BETA_PER_PAPER:
            rows = rows[1:-1]
        lo, hi = BETA_PAGES
        rows = [f for f in rows if lo <= f["pages"] <= hi]
        if len(rows) <= BETA_PER_PAPER:
            chosen.update(f["key"] for f in rows)
            continue
        n = len(rows)
        widths: set[float] = set()
        for b in range(BETA_PER_PAPER):
            start = (b * n) // BETA_PER_PAPER
            end = ((b + 1) * n) // BETA_PER_PAPER
            band = rows[start:end]
            mid = (len(band) - 1) / 2.0
            best = min(range(len(band)), key=lambda i: (
                (band[i].get("width") or 0.0) in widths, abs(i - mid), i))
            pick = band[best]
            widths.add(pick.get("width") or 0.0)
            chosen.add(pick["key"])
    return [f["key"] for f in facts if f["key"] in chosen]


# ---------------------------------------------------------------------------
# The table: one CSV format for the script and for the window
# ---------------------------------------------------------------------------
#
# Knut, #182 5831246553: *"one "Export list" and one "Import list". The export
# button saves a csv file of the table with the current settings. The import
# button imports the same type of file back into the app and updates the
# checked settings."* The table is the one ``scripts/make_preset_defaults.py
# --table`` has written for his users since beta 42, so a file the window
# exports is a file ``--from-table`` reads, and a table his users filled in is
# a file the window imports. ONE format, written and read here, by both.

#: The columns, in order. Knut's three (name, the yes/no answer, comments)
#: with the group in front for the reader and the key behind, which is the
#: preset's identity and what a row is matched by.
TABLE_HEADER = ["Group", "Name of preset", "Include as default [yes/no]",
                "Comments", "Key"]
TABLE_NAME = TABLE_HEADER[1]
TABLE_ANSWER = TABLE_HEADER[2]
TABLE_COMMENTS = TABLE_HEADER[3]
TABLE_KEY = TABLE_HEADER[4]

#: Answers that tick, and answers that clear (any case). Anything else, an
#: empty cell included, is not an answer.
TABLE_YES = frozenset({"yes", "y", "x", "1", "ja", "true"})
TABLE_NO = frozenset({"no", "n", "nein", "nei", "0", "false"})

#: The name the window offers when it saves the table. English in every
#: language, on purpose: the file travels between people (Knut's users send
#: theirs back to him), and its name should say the same thing to all of them.
EXPORT_FILENAME = "ChromIQ built-in presets shown.csv"

#: How the table is written: UTF-8 with a byte-order mark, which is what makes
#: a spreadsheet read the "·" in the names as a "·". Every reader here accepts
#: the file with or without it.
TABLE_ENCODING = "utf-8-sig"


def write_table(fh, facts: list[dict], ticked: Iterable[str] | None = None,
                comments: dict[str, str] | None = None) -> None:
    """Write the table to the text stream ``fh`` (opened with ``newline=""``).

    ``facts`` as :func:`ui.tabs.tab_chart.builtin_preset_facts` gives them
    (``group``, ``name``, ``key``), one row each in that order. ``ticked``
    None leaves the answer column empty, for people to fill in; a set of keys
    writes "yes" or "no" on every row."""
    import csv
    ticked = None if ticked is None else set(ticked)
    comments = comments or {}
    w = csv.writer(fh)
    w.writerow(TABLE_HEADER)
    for f in facts:
        answer = "" if ticked is None else (
            "yes" if f["key"] in ticked else "no")
        w.writerow([f["group"], f["name"], answer,
                    comments.get(f["key"], ""), f["key"]])


class TableError(ValueError):
    """The file is not a preset table at all (no Key or no answer column),
    or it cannot be read as a table (:attr:`unreadable`)."""

    def __init__(self, message: str, *, unreadable: bool = False) -> None:
        super().__init__(message)
        #: True when the file could not be read as text in columns at all
        #: (B8-1162: a cell over the csv module's 128 KB limit, or a binary
        #: file), rather than read and found to lack the two columns.
        self.unreadable = unreadable


class TableReading:
    """What :func:`read_table` found. ``line`` is the file's own line number
    (the header is line 1)."""

    def __init__(self) -> None:
        #: ``{key: True/False}`` for every known key answered yes or no.
        self.answers: dict[str, bool] = {}
        #: ``{key: text}`` for every known key with a comment.
        self.comments: dict[str, str] = {}
        #: ``[(line, key, name)]``: keys this ChromIQ does not have.
        self.unknown: list[tuple[int, str, str]] = []
        #: ``[(line, key, name)]``: a known key whose answer is empty.
        self.blank: list[tuple[int, str, str]] = []
        #: ``[(line, key, name, answer)]``: an answer that is neither yes nor no.
        self.invalid: list[tuple[int, str, str, str]] = []
        #: ``[(line, name)]``: a row with no key, which cannot be matched.
        self.no_key: list[tuple[int, str]] = []
        #: ``[(lines, key, name, answer)]``: a known key answered yes or no
        #: on more than one line (B8-1163). The LAST line counts, and
        #: ``answer`` is the answer it gave; ``lines`` lists every one.
        self.duplicates: list[tuple[list[int], str, str, bool]] = []

    @property
    def skipped(self) -> int:
        return (len(self.unknown) + len(self.blank) + len(self.invalid)
                + len(self.no_key))


def _decode(raw: bytes) -> str:
    """UTF-8, with or without a byte-order mark; else the Windows code page a
    spreadsheet's plain "CSV" is saved in. The keys are ASCII, so every row
    is matched either way; only a name could come out differently."""
    for codec in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(codec)
        except UnicodeDecodeError:
            continue
    # cp1252 leaves five bytes undefined; Latin-1 defines all 256.
    return raw.decode("latin-1")


def read_table(raw: bytes | str, known: Iterable[str]) -> TableReading:
    """Read a table. ``known`` is every built-in key this ChromIQ has.

    A comma or a semicolon separates the columns: a spreadsheet set to a
    language that writes a decimal comma saves its "CSV" with semicolons.
    Columns are found by their header, so their order does not matter.
    Raises :class:`TableError` when the header has no Key or no answer
    column, since then no row in the file can be matched or read."""
    import csv
    import io
    text = _decode(raw) if isinstance(raw, bytes) else raw.lstrip("﻿")
    first = text.split("\n", 1)[0]
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    try:
        return _read_rows(reader, known)
    except csv.Error as exc:
        # B8-1162: a cell over the csv module's limit (128 KB), which is
        # what a binary file with no line break reads as. It escaped as an
        # uncaught `_csv.Error` and the window said nothing at all.
        raise TableError(f"not readable as a table: {exc}",
                         unreadable=True) from None


def _read_rows(reader, known: Iterable[str]) -> TableReading:
    try:
        header = [h.strip() for h in next(reader)]
    except StopIteration:
        raise TableError("empty file") from None
    if TABLE_KEY not in header or TABLE_ANSWER not in header:
        raise TableError("no Key or answer column")
    col = {h: i for i, h in enumerate(header)}
    known = set(known)
    out = TableReading()

    def cell(row: list[str], name: str) -> str:
        i = col.get(name)
        return row[i].strip() if i is not None and i < len(row) else ""

    answered_on: dict[str, list[int]] = {}
    names: dict[str, str] = {}
    for row in reader:
        line = reader.line_num
        if not any(c.strip() for c in row):
            continue
        key = cell(row, TABLE_KEY)
        name = cell(row, TABLE_NAME)
        if not key:
            out.no_key.append((line, name))
            continue
        if key not in known:
            out.unknown.append((line, key, name))
            continue
        comment = cell(row, TABLE_COMMENTS)
        if comment:
            out.comments[key] = comment
        answer = cell(row, TABLE_ANSWER)
        low = answer.lower()
        if low in TABLE_YES or low in TABLE_NO:
            out.answers[key] = low in TABLE_YES
            answered_on.setdefault(key, []).append(line)
            names[key] = name
        elif not answer:
            out.blank.append((line, key, name))
        else:
            out.invalid.append((line, key, name, answer))
    out.duplicates = [(lines, key, names.get(key, ""), out.answers[key])
                      for key, lines in answered_on.items() if len(lines) > 1]
    return out


# ---------------------------------------------------------------------------
# The paper filter (Knut, #182 5832303551, beta 43)
# ---------------------------------------------------------------------------
#
# *"Add a checkbox in the window named "Filter preset-dropdown list according
# to selected paper size". When OFF, all presets are listed [...] according to
# what is selected to be shown in the settings window. When ON, the dropdown
# lists for "Select preset" and the "built-in presets" button show only the
# presets related to the selection in "Paper" field in Create Chart (either
# "Paper size" in Guided or "Paper" in Manual mode) [...] The presets under
# headings Scanner are always shown. The Red River Paper presets area also
# filtered [...] If the Paper size setting is Custom [...] all the presets
# using the Custom Paper size setting will be shown."*
#
# SCANNER IS FILTERED TOO since Knut's ruling of 2026-09-25 (#182 5840692243,
# K48): *"I also think the Scanner presets now should obey the same filtering
# according to paper size."* The "always shown" above no longer holds.
#
# A preset's paper is the printtarg ``-p`` code it lays the chart out on,
# which every built-in carries and a person's own preset stores as
# ``printtarg_-p``. The pulldowns list each ORIENTATION as its own entry
# ("A3 Portrait" is ``A3``, "A3 Landscape" is ``420x297``), so orientation is
# part of the paper and the match is exact. Any code the paper list does not
# name (``100x150``, a person's ``210x280``) is what the Paper field shows as
# "Custom (enter dimensions)", and matches Custom whatever its dimensions.

#: The setting: True filters both lists by the paper selected in Create Chart.
PAPER_FILTER_KEY = "builtin_presets_paper_filter"

#: What :func:`paper_class` answers for every size the paper list does not
#: name: the Paper field's own "custom" entry.
CUSTOM_PAPER = "custom"


def paper_filter_on(settings: Any) -> bool:
    try:
        # ON unless the person stored OFF (Knut, #182 5833232475)
        v = settings.get(PAPER_FILTER_KEY, True)
    except Exception:      # noqa: BLE001 — a settings fake without get()
        return True
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


def paper_class(code: Any) -> str:
    """The Paper field entry a ``-p`` code is shown as: the code itself when
    the paper list names it, :data:`CUSTOM_PAPER` for any other size, and ""
    for no paper at all."""
    from data.patch_db import PAPER_LABELS
    code = str(code or "").strip()
    if not code:
        return ""
    return code if code in PAPER_LABELS else CUSTOM_PAPER


def paper_matches(preset_paper: Any, selected: str) -> bool:
    """True when a preset on ``preset_paper`` belongs in a list filtered to the
    Paper field entry ``selected`` (a :func:`paper_class`). A preset with no
    paper is always shown; so is every preset when nothing is selected."""
    mine = paper_class(preset_paper)
    if not mine or not selected:
        return True
    return mine == selected
