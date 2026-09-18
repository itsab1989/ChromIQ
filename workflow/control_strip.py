"""The control strip ChromIQ declares for a verification chart (#182).

**THE DETECTION WAS BUILT FIRST AND NOTHING FED IT.** Knut approved the
declaration rule on 2026-09-18 (S2w of `docs/design/issue_182_answers.md`,
built as B8-397): a chart carries a control strip when a sidecar
``<chart stem>.control-strip.json`` sits beside it holding ``{"name": …,
"sample_ids": [...]}``, or when the ``.ti1``/``.ti2`` carries a CGATS
``CONTROL_STRIP_IDS`` keyword naming the same ids. Three rows of the limits
table then become computable at 8 declared ids present and referenced, and the
95th-percentile row at 20.

Nothing in ChromIQ wrote such a declaration, so on every chart on every disk
those three rows read *"this chart declares no control strip"*. Knut, beta 22:

> *"It is essential that the function that makes ChromIQ write a control-strip
> declaration for a chart is implemented, tested and working. … If that is a
> function that can always be created for a chart placed in the verifications/
> folder, and notify the user if a selected/loaded/created chart … does not
> fulfil the requirements to be able to create the control-strip
> declaration."*

This module is that function. It decides WHICH of a chart's patches make up
the strip, and it is the only place that decision is made.

THE RULE, AND WHY IT IS THIS ONE
--------------------------------
A control strip is the row of patches a press or proof is checked on: the
substrate, the solid inks, a tint ladder of each of them, and a neutral grey
ladder. Every published wedge ChromIQ's users will have met has that shape (the
Fogra Media Wedge and the IDEAlliance ISO 12647-7 control wedge are both
substrate + solids + tints + three-colour greys, at 72 and 84 patches), and it
is that shape rather than any of their patch lists, which ChromIQ does not hold
and may not invent.

So the strip is a **ladder of 29 aims in the printer's own device space**, and
a chart fills each rung with its own nearest patch:

* the **substrate**, device (100, 100, 100);
* the **seven other cube corners**: the composite black, the three ink solids
  cyan, magenta and yellow, and their three two-ink overprints red, green and
  blue. These are the same eight corners the report already reads
  (:data:`workflow.measurement_report.CUBE_CORNERS`);
* a **tint ladder of each of those six colours** at 25 %, 50 % and 75 % ink,
  eighteen rungs;
* a **neutral grey ladder** at the same three levels, three rungs, which is the
  three-colour grey-balance patch of a press wedge.

A rung is filled by the nearest patch whose device value is within
:data:`SLOT_TOL` of the aim, on every channel. That number is
``CORNER_PRESENT_TOL``, read from the report module rather than copied: ChromIQ
already has exactly one answer to *"is there a patch at this device aim"*, it
is the one the cube-corner rows are judged on, and a second number here would
be a second answer to the same question. Each patch fills at most one rung, and
the rungs are filled in ladder order, so the substrate and the solids are never
displaced by a tint.

WHAT IT SELECTS, MEASURED
-------------------------
On real charts built by ``targen -d2 -fN -e4 -B4 -G`` and laid out by
``printtarg`` (2026-09-19, the sizes ChromIQ's own presets produce):

=========  ======  ============  =====
patches    rungs   declaration   95th
=========  ======  ============  =====
13         4       no            no
17         7       no            no
21         11      yes           no
31         12      yes           no
51         17      yes           no
101        22      yes           yes
210        27      yes           yes
401        29      yes           yes
=========  ======  ============  =====

A reader accepts it because every rung is a patch a printer already looks at,
and because the strip is a property of the CHART: the same chart declares the
same patches every time, so two dated verifications of one chart are judged
over one population.

WHAT IT NEVER DOES
------------------
* It does not touch a chart that already declares a strip, by sidecar or by
  keyword. A declaration the user or another tool wrote outranks this one.
* It does not write beside a profiling chart. Knut scoped this to the
  verification chart, and a profiling sheet carries no verdict at all.
* It does not rewrite anything on a user's disk. The sidecar is written beside
  a chart ChromIQ has just created, in the same breath as the chart.

No Qt in here: the Create Chart tab and the chart importer both call
:func:`declare_for_chart`, and every rule below is testable without a
QApplication.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from core.logger import get_logger
from core.text_io import read_text
from workflow.measurement_report import (CONTROL_STRIP_MIN,
                                         CONTROL_STRIP_P95_MIN,
                                         CONTROL_STRIP_SIDECAR,
                                         CORNER_PRESENT_TOL,
                                         control_strip_declaration)

log = get_logger(__name__)

#: How near a patch has to be to a rung's aim, per channel, in device units.
#: The report's own "is there a patch at this device aim" number; see the
#: module docstring for why it is read and not chosen again.
SLOT_TOL = CORNER_PRESENT_TOL

#: The tint ladder, in per-cent ink. Device value = 100 - ink.
TINT_LEVELS: "tuple[int, ...]" = (75, 50, 25)

#: The name written into the sidecar. It says whose strip it is, because the
#: report shows it and a strip named after a standard would claim that
#: standard's list.
STRIP_NAME = "ChromIQ control strip"

#: **THE CONTROL THE WARNING POINTS AT, NAMED IN ONE PLACE.** Knut asked the
#: warning to *"refer to the button function in Create Chart mentioned above
#: for help in selecting a compatible chart"*. That is the button under the
#: Create Chart preset dropdown (`ui/tabs/tab_chart.py`, `_preset_verify_btn`),
#: which opens `ui/dialogs/preset_verification_dialog.py`. Built for the same
#: beta and by another hand, so M-VERIFY-NO-CONTROL-STRIP carries a
#: ``{button}`` placeholder rather than a literal and this is the one line that
#: has to change if the label does.
#:
#: It is deliberately NOT passed through ``tr()``: the button's own label is
#: translated where the button is built, a second ``tr()`` of the same words
#: here would be a second key, and the extractor cannot see ``tr(variable)``
#: at all.
ELIGIBILITY_CONTROL = "Which presets can be verified?"

#: Marks a sidecar as ChromIQ's own, so a later release can tell its own
#: declaration from one a user wrote by hand.
GENERATOR = "chromiq.control_strip"
FORMAT_VERSION = 1


@dataclass(frozen=True)
class Slot:
    """One rung of the ladder: what it is, and the device value it aims at."""
    key: str
    device: "tuple[float, float, float]"


def _ladder() -> "tuple[Slot, ...]":
    slots = [Slot("paper", (100.0, 100.0, 100.0)),
             Slot("solid_K", (0.0, 0.0, 0.0)),
             Slot("solid_C", (0.0, 100.0, 100.0)),
             Slot("solid_M", (100.0, 0.0, 100.0)),
             Slot("solid_Y", (100.0, 100.0, 0.0)),
             Slot("solid_R", (100.0, 0.0, 0.0)),
             Slot("solid_G", (0.0, 100.0, 0.0)),
             Slot("solid_B", (0.0, 0.0, 100.0))]
    # One ink at a tint, the other two channels clear of it: the single-ink
    # ladder a printer reads down the side of a wedge.
    for name, ch in (("C", 0), ("M", 1), ("Y", 2)):
        for ink in TINT_LEVELS:
            dev = [100.0, 100.0, 100.0]
            dev[ch] = 100.0 - ink
            slots.append(Slot(f"tint_{name}_{ink}", tuple(dev)))
    # The two-ink overprints at the same tints: red is magenta plus yellow, so
    # its tint holds the RED channel clear and the other two at the tint.
    for name, ch in (("R", 0), ("G", 1), ("B", 2)):
        for ink in TINT_LEVELS:
            dev = [100.0 - ink] * 3
            dev[ch] = 100.0
            slots.append(Slot(f"tint_{name}_{ink}", tuple(dev)))
    for ink in TINT_LEVELS:
        slots.append(Slot(f"grey_{ink}", (100.0 - ink,) * 3))
    return tuple(slots)


SLOTS: "tuple[Slot, ...]" = _ladder()
SLOT_BY_KEY: "dict[str, Slot]" = {s.key: s for s in SLOTS}


# ---------------------------------------------------------------------------
# Reading a chart's device values
# ---------------------------------------------------------------------------
def _sid_order(sid: str):
    try:
        return (0, int(sid), "")
    except (TypeError, ValueError):
        return (1, 0, str(sid))


def chart_device_values(path: "str | Path") -> "dict[str, tuple[float, float, float]]":
    """``{SAMPLE_ID: (R, G, B) on 0..100}`` from a ``.ti1`` / ``.ti2``, or ``{}``.

    Read straight out of the CGATS text and not through ``parse_ti3``, for the
    same reason :func:`workflow.measurement_report._cgats_keyword` is: a
    ``.ti1`` need not carry any colour column at all, and ``parse_ti3`` refuses
    a file with no measurement table. A chart's device values are what this
    module needs and they are always there.

    Only the FIRST data table is read. A ChromIQ ``.ti1`` carries three
    (the patch list, then the white and black reference tables), and the second
    and third repeat SAMPLE_IDs that mean something else entirely.

    The scale is normalised exactly as the report normalises it: a file whose
    largest value is past 101 is 0..255 code values.
    """
    p = Path(path)
    try:
        text = read_text(p, lenient=True)
    except OSError:
        return {}
    lines = text.splitlines()
    try:
        fmt = next(i for i, ln in enumerate(lines)
                   if ln.strip() == "BEGIN_DATA_FORMAT")
        fields = lines[fmt + 1].split()
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA")
        end = next(i for i, ln in enumerate(lines[start:], start)
                   if ln.strip() == "END_DATA")
    except (StopIteration, IndexError):
        return {}
    try:
        cols = [fields.index("SAMPLE_ID")] + [fields.index(f"RGB_{c}") for c in "RGB"]
    except ValueError:
        return {}
    out: "dict[str, tuple[float, float, float]]" = {}
    biggest = 0.0
    for ln in lines[start + 1:end]:
        parts = ln.split()
        if len(parts) <= max(cols):
            continue
        sid = parts[cols[0]].strip('"')
        try:
            dev = tuple(float(parts[i]) for i in cols[1:])
        except ValueError:
            continue
        if not all(math.isfinite(v) for v in dev):
            continue
        biggest = max(biggest, *dev)
        out.setdefault(sid, dev)          # a repeated id keeps its first row
    if biggest > 101.0:
        out = {sid: tuple(v * (100.0 / 255.0) for v in dev)
               for sid, dev in out.items()}
    return out


# ---------------------------------------------------------------------------
# Filling the ladder
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Fill:
    """One rung after the chart has been offered to it."""
    key: str
    sample_id: "str | None"
    distance: "float | None"      # device units, worst channel; None = nothing near


@dataclass(frozen=True)
class StripSelection:
    """What a chart's patches make of the ladder."""
    fills: "tuple[Fill, ...]"
    #: The chart had no readable device values at all.
    unreadable: bool = False

    @property
    def ids(self) -> "list[str]":
        return [f.sample_id for f in self.fills if f.sample_id is not None]

    @property
    def n(self) -> int:
        return len(self.ids)

    @property
    def missing(self) -> "list[str]":
        return [f.key for f in self.fills if f.sample_id is None]

    @property
    def can_declare(self) -> bool:
        """Enough rungs for the average and the largest (S2w: k >= 8)."""
        return self.n >= CONTROL_STRIP_MIN

    @property
    def p95_ready(self) -> bool:
        """Enough rungs for the 95th percentile as well (S2w: k >= 20)."""
        return self.n >= CONTROL_STRIP_P95_MIN


def select_strip(devices: "dict[str, tuple[float, float, float]]") -> StripSelection:
    """Offer every patch of a chart to the ladder, rung by rung.

    Ladder order, nearest patch, each patch used once. Ties are broken by
    SAMPLE_ID so the same chart always declares the same strip.
    """
    if not devices:
        return StripSelection(fills=tuple(Fill(s.key, None, None) for s in SLOTS),
                              unreadable=True)
    order = sorted(devices, key=_sid_order)
    used: "set[str]" = set()
    fills: "list[Fill]" = []
    for slot in SLOTS:
        best: "str | None" = None
        best_d: "float | None" = None
        for sid in order:
            if sid in used:
                continue
            d = max(abs(a - b) for a, b in zip(devices[sid], slot.device))
            if best_d is None or d < best_d:
                best, best_d = sid, d
        if best is not None and best_d is not None and best_d <= SLOT_TOL:
            used.add(best)
            fills.append(Fill(slot.key, best, round(float(best_d), 2)))
        else:
            fills.append(Fill(slot.key, None,
                              round(float(best_d), 2) if best_d is not None else None))
    return StripSelection(fills=tuple(fills))


def strip_for_chart(chart_path: "str | Path") -> StripSelection:
    """The ladder, filled from the chart file at *chart_path*."""
    return select_strip(chart_device_values(chart_path))


# ---------------------------------------------------------------------------
# Writing the declaration
# ---------------------------------------------------------------------------
def declaration_path(chart_path: "str | Path") -> Path:
    """``<chart stem>.control-strip.json`` beside *chart_path*.

    The suffix is the report's own constant, so the file this module writes and
    the file the report looks for cannot drift apart.
    """
    p = Path(chart_path)
    return p.parent / (p.stem + CONTROL_STRIP_SIDECAR)


def write_declaration(chart_path: "str | Path",
                      selection: StripSelection) -> Path:
    """Write the sidecar beside *chart_path* and return its path.

    ``name`` and ``sample_ids`` are what the report reads. The rest is for a
    human opening the file: which rung each patch filled, and how far off the
    aim it was.
    """
    out = declaration_path(chart_path)
    doc = {
        "name": STRIP_NAME,
        "sample_ids": selection.ids,
        "generator": GENERATOR,
        "format_version": FORMAT_VERSION,
        "tolerance": SLOT_TOL,
        "slots": [{"slot": f.key, "sample_id": f.sample_id,
                   "aim": list(SLOT_BY_KEY[f.key].device),
                   "distance": f.distance}
                  for f in selection.fills if f.sample_id is not None],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    log.info("control-strip declaration written: %s (%d of %d rungs)",
             out.name, selection.n, len(SLOTS))
    return out


#: Why :func:`declare_for_chart` did not write one. ``None`` means it did.
OUTCOME_WRITTEN = "written"
OUTCOME_TOO_FEW = "too_few_patches"
OUTCOME_UNREADABLE = "unreadable_chart"
OUTCOME_ALREADY = "already_declared"


@dataclass(frozen=True)
class DeclarationResult:
    outcome: str
    selection: StripSelection
    path: "Path | None" = None

    @property
    def written(self) -> bool:
        return self.outcome == OUTCOME_WRITTEN

    @property
    def needs_warning(self) -> bool:
        """Whether the user has to be told. A chart that already declares a
        strip, and a chart whose ladder filled, are both silent."""
        return self.outcome in (OUTCOME_TOO_FEW, OUTCOME_UNREADABLE)


def declare_for_chart(chart_path: "str | Path", *,
                      write: bool = True) -> DeclarationResult:
    """Declare a control strip for the chart at *chart_path*, if it can carry one.

    With ``write=False`` nothing is written or removed and the same answer comes
    back, so a caller that only has to decide whether to warn can ask without
    touching the disk a second time.

    Never raises: a chart that cannot be read, or cannot fill eight rungs, is
    left exactly as it is and the caller is told which. A chart that ALREADY
    declares a strip is left alone too, by sidecar or by CGATS keyword, because
    a declaration somebody else wrote is not ChromIQ's to replace.
    """
    chart = Path(chart_path)
    try:
        existing = control_strip_declaration(chart, chart)
    except Exception:                       # noqa: BLE001 - never break a build
        log.warning("control-strip: could not check %s for an existing "
                    "declaration", chart, exc_info=True)
        existing = None
    if existing is not None:
        # A declaration THIS module wrote beside THIS chart is not somebody
        # else's and is simply replaced; anything else is left alone.
        mine = declaration_path(chart)
        ours = (existing.get("source") == "sidecar"
                and existing.get("file") == mine.name
                and _is_ours(mine))
        if not ours:
            log.info("control-strip: %s already declares a strip (%s); "
                     "leaving it alone", chart.name, existing.get("source"))
            return DeclarationResult(OUTCOME_ALREADY,
                                     strip_for_chart(chart), None)
    selection = strip_for_chart(chart)
    if selection.unreadable:
        if write:
            _remove_ours(chart)
        return DeclarationResult(OUTCOME_UNREADABLE, selection, None)
    if not selection.can_declare:
        # A sidecar ChromIQ wrote for an EARLIER chart at this path would
        # otherwise outlive it and be read as this chart's declaration.
        if write:
            _remove_ours(chart)
        return DeclarationResult(OUTCOME_TOO_FEW, selection, None)
    if not write:
        return DeclarationResult(OUTCOME_WRITTEN, selection,
                                 declaration_path(chart))
    try:
        path = write_declaration(chart, selection)
    except OSError as exc:
        log.warning("control-strip: could not write the declaration beside "
                    "%s (%s)", chart.name, exc)
        return DeclarationResult(OUTCOME_UNREADABLE, selection, None)
    return DeclarationResult(OUTCOME_WRITTEN, selection, path)


def _is_ours(path: Path) -> bool:
    """Whether the sidecar at *path* is one this module wrote."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(doc, dict) and doc.get("generator") == GENERATOR


def _remove_ours(chart: Path) -> None:
    """Delete a declaration THIS module wrote beside *chart*, and nothing else.

    A regenerate replaces the chart at a path; the stale sidecar beside it
    describes patches the new chart may not have. One a user wrote by hand is
    never touched.
    """
    p = declaration_path(chart)
    if p.is_file() and _is_ours(p):
        try:
            p.unlink()
            log.info("control-strip: removed the stale declaration %s", p.name)
        except OSError as exc:
            log.warning("control-strip: could not remove %s (%s)", p.name, exc)
