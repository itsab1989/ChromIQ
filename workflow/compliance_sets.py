"""Limit sets for the Measurement Report (#182): the table of tolerances, the
verdict words, and nothing else.

The Measurement Report used to judge five statistics with TWO numbers, the
"average" and the "maximum" threshold, both global settings. Knut's #182
rulings (2026-09-04 to 2026-09-07) replace that with **limit sets**: a column
of limits, one per *population × statistic* row, that a profile run is bound
to and that every dated verification of that run is judged with.

Everything the rest of the application needs to know about limit sets lives
here, once:

* the **rows** (:data:`ROWS`): what is measured, over which patches, in which
  unit, and whether ChromIQ can compute it today (``now`` / ``build`` /
  ``ref`` needs a reference file / ``unknown`` the clause is not held /
  ``unmeasurable`` ChromIQ cannot measure it at all);
* the **sets** (:data:`SETS`): ChromIQ default, ChromIQ tight, Quick check,
  the two ISO value sets (read-only) and the two Custom sets that start from
  their ISO parent;
* the **factory limits** of each set (:func:`factory_limits`), and the
  effective limits once the user's Preferences overrides are applied
  (:func:`effective_limits`);
* the **verdict words** PASS / FAIL / COND / INFO / N-A (Knut, K-f,
  2026-09-07) and the two decision rules that produce them
  (:func:`row_verdict`, :func:`set_summary`).

**The ISO tolerance numbers are not in this file, and not in the repository.**
They are read from ``data/compliance_sets/iso12647.json``, which ships EMPTY
until the licensing question (#182, Sebastian's S-2) is answered; a row an ISO
set is known to limit then reads ``?`` (the limit is in a clause ChromIQ does
not hold or may not show). The *structure* of a standard, which rows it
writes a limit over, is not licensed content and is stated below so the table
can draw ``?`` in the right cells and ``–`` (the set defines no limit) in the
others.

**A verdict never names a standard.** A column may be headed "ISO 12647-8:2021
values"; a verdict sentence says "this limit set's values" and never
"conforms" (D7, D24). ChromIQ does not certify anything.

No Qt in here: this module is imported by the report code, the Measure tab's
save path, the settings migration and the two windows, and is tested without
a QApplication.
"""
from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.i18n import tr
from core.resource_path import resource_path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# The five words
# ---------------------------------------------------------------------------
#: Knut, #182 K-f (2026-09-07): *"PASS / FAIL / CONDITIONAL / INFO / N-A, and
#: maybe using a shorter version of the word for CONDITIONAL"*. The stored
#: token is English and never translated; the DISPLAYED word goes through
#: :func:`word_label`. N-A keeps his hyphen (he wrote N-A, not N/A).
PASS = "PASS"
FAIL = "FAIL"
COND = "COND"
INFO = "INFO"
N_A = "N-A"
WORDS = (PASS, FAIL, COND, INFO, N_A)


def word_label(word: str) -> str:
    """The word as shown on screen (translatable; the token is not)."""
    return {PASS: tr("PASS"), FAIL: tr("FAIL"), COND: tr("COND"),
            INFO: tr("INFO"), N_A: tr("N-A")}.get(word, word)


# ---------------------------------------------------------------------------
# A limit: one cell of the table
# ---------------------------------------------------------------------------
#: ``value`` a required limit (a *shall*); ``should`` a recommendation the set
#: does not require (exceeding it is COND, never FAIL); ``none`` the set
#: defines no limit for this row (``–``); ``unknown`` the number is in a
#: clause ChromIQ does not hold or may not show (``?``); ``unmeasurable`` the
#: set defines a limit ChromIQ cannot measure at all (``✕``).
LIMIT_KINDS = ("value", "should", "none", "unknown", "unmeasurable")


@dataclass(frozen=True)
class Limit:
    kind: str
    number: "float | None" = None

    # -- constructors
    @classmethod
    def value(cls, x: float) -> "Limit":
        return cls("value", float(x))

    @classmethod
    def should(cls, x: float) -> "Limit":
        return cls("should", float(x))

    @classmethod
    def none(cls) -> "Limit":
        return cls("none")

    @classmethod
    def unknown(cls) -> "Limit":
        return cls("unknown")

    @classmethod
    def unmeasurable(cls) -> "Limit":
        return cls("unmeasurable")

    # -- properties
    @property
    def is_numeric(self) -> bool:
        """True for a limit a value can be compared against (shall or should)."""
        return self.kind in ("value", "should") and self.number is not None

    @property
    def is_should(self) -> bool:
        return self.kind == "should"

    # -- JSON: number | [number, "should"] | null | "?" | "x"
    def to_json(self) -> Any:
        if self.kind == "value":
            return self.number
        if self.kind == "should":
            return [self.number, "should"]
        if self.kind == "none":
            return None
        if self.kind == "unknown":
            return "?"
        return "x"

    @classmethod
    def from_json(cls, v: Any) -> "Limit":
        """Tolerant: anything unreadable becomes ``unknown`` (``?``), never a
        number nobody wrote and never an exception."""
        if v is None:
            return cls.none()
        if isinstance(v, bool):
            return cls.unknown()
        if isinstance(v, (int, float)):
            return cls.value(float(v)) if math.isfinite(float(v)) else cls.unknown()
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("?", "unknown"):
                return cls.unknown()
            if s in ("x", "✕", "unmeasurable"):
                return cls.unmeasurable()
            if s in ("", "-", "–", "none"):
                return cls.none()
            try:
                return cls.value(float(s.replace(",", ".")))
            except ValueError:
                return cls.unknown()
        if isinstance(v, (list, tuple)) and v:
            try:
                n = float(v[0])
            except (TypeError, ValueError):
                return cls.unknown()
            if not math.isfinite(n):
                return cls.unknown()
            return cls.should(n) if (len(v) > 1 and str(v[1]).lower() == "should") \
                else cls.value(n)
        return cls.unknown()


def format_number(x: float) -> str:
    """``2.0``, ``2.5``, ``0.75``: one decimal, two when the second is not
    zero. Decimal POINT, as every number ChromIQ writes elsewhere."""
    s = f"{x:.2f}"
    if s.endswith("0"):
        s = s[:-1]
    return s


def limit_text(limit: Limit) -> str:
    """The table cell: ``2.0``, ``(2.0)`` for a should-limit, ``–``, ``?``, ``✕``."""
    if limit.kind == "value":
        return format_number(limit.number)
    if limit.kind == "should":
        return f"({format_number(limit.number)})"
    if limit.kind == "none":
        return "–"
    if limit.kind == "unknown":
        return "?"
    return "✕"


# ---------------------------------------------------------------------------
# The rows: population × statistic
# ---------------------------------------------------------------------------
#: Row status. ``now``: computed today; ``build``: computed from this release;
#: ``ref``: computable only against a reference file for the printing
#: condition (N-A until one exists); ``unknown``: the population is in a
#: clause ChromIQ does not hold (``?`` for every set that limits it);
#: ``unmeasurable``: ChromIQ cannot evaluate it at all (``✕``; it stays in the
#: table so the user sees what a standard asks that ChromIQ does not do, Knut
#: K2 / D16, and it is a note in the report, never a verdict, D11).
ROW_STATUSES = ("now", "build", "ref", "unknown", "unmeasurable")

GROUP_LABELS: "dict[str, str]" = {
    "substrate":     "Paper",
    "solids":        "Solid colours",
    "control_strip": "Control strip (the standard's own patches)",
    "grey_ramp":     "Grey ramp of the measured chart",
    "all_patches":   "All patches of the measured chart",
    "selected":      "Selected patches of the standard's chart",
    "not_evaluated": "Not evaluated by ChromIQ",
}


@dataclass(frozen=True)
class Row:
    id: str
    group: str
    label: str            # English source; display through tr()
    unit: str             # "ΔE00" | "ΔCh" | "ΔH*ab" | "ΔL*" | ""
    status: str
    #: the key of the same statistic in ``report["de00"]`` (the five ChromIQ
    #: statistics keep their old keys so trends and old tests still read)
    metric_key: "str | None" = None
    #: why ChromIQ cannot measure it (``unmeasurable`` rows only); English
    note: str = ""

    def __post_init__(self) -> None:
        assert self.status in ROW_STATUSES, self.status
        assert self.group in GROUP_LABELS, self.group


ROWS: "tuple[Row, ...]" = (
    # -- Paper
    Row("substrate_de00_max", "substrate",
        "Paper white, difference from the reference paper", "ΔE00", "ref"),
    Row("substrate_overprinted_de00_max", "substrate",
        "Overprinted proofing paper against the production paper", "ΔE00",
        "unmeasurable",
        note="needs the production paper measured as well"),
    Row("substrate_gloss_class", "substrate", "Gloss class of the paper", "",
        "unmeasurable", note="needs a gloss meter or the paper maker's data sheet"),
    Row("substrate_fluorescence_class", "substrate",
        "Fluorescence class of the paper", "", "unmeasurable",
        note="needs a brightness reading with and without UV"),
    # -- Solid colours
    Row("solids_de00_max", "solids",
        "Solid colours, largest difference", "ΔE00", "ref"),
    Row("cmy_solids_dhab_max", "solids",
        "Cyan, magenta and yellow solids, largest hue difference", "ΔH*ab", "ref"),
    Row("spot_solids_de00_max", "solids",
        "Spot colours, largest difference", "ΔE00", "unmeasurable",
        note="ChromIQ has no spot-colour workflow"),
    # -- Control strip
    Row("control_strip_de00_avg", "control_strip",
        "Control-strip patches, average", "ΔE00", "unknown"),
    Row("control_strip_de00_max", "control_strip",
        "Control-strip patches, largest", "ΔE00", "unknown"),
    Row("control_strip_de00_p95", "control_strip",
        "Control-strip patches, 95th percentile", "ΔE00", "unknown"),
    # -- Grey ramp (K-h)
    Row("grey_balance_neutral_ramp_avg", "grey_ramp",
        "Grey balance of the grey ramp, average", "ΔCh", "build"),
    Row("grey_balance_neutral_ramp_max", "grey_ramp",
        "Grey balance of the grey ramp, largest", "ΔCh", "build"),
    # -- All patches (ChromIQ's five, shape A merge with the ISO all-patch rows)
    Row("all_de00_avg", "all_patches", "All patches, average", "ΔE00", "now",
        metric_key="avg_all"),
    Row("best95_de00_avg", "all_patches", "Best 95 % of patches, average", "ΔE00",
        "now", metric_key="avg_low95"),
    Row("worst5_de00_avg", "all_patches", "Worst 5 % of patches, average", "ΔE00",
        "now", metric_key="avg_high5"),
    Row("all_de00_max", "all_patches", "All patches, largest", "ΔE00", "now",
        metric_key="max_all"),
    Row("all_de00_p95", "all_patches", "All patches, 95th percentile", "ΔE00",
        "now", metric_key="max_low95"),
    # -- Selected patches of the standard's chart
    Row("outer_gamut_226_de00_avg", "selected",
        "Outer-gamut patches, average", "ΔE00", "unknown"),
    Row("surface_gamut_de00_avg", "selected",
        "Surface-gamut patches, average", "ΔE00", "unknown"),
    Row("ramps_30_70_dl_max", "selected",
        "Single-colour ramps 30 % to 70 %, largest lightness difference", "ΔL*",
        "build"),
    # -- Not evaluated by ChromIQ (✕ rows; notes in the report)
    Row("uniformity_sd", "not_evaluated",
        "Evenness across the sheet, nine locations (spread of L*, a*, b*)", "",
        "unmeasurable", note="needs nine readings at set positions on one sheet"),
    Row("uniformity_de00_max_from_mean", "not_evaluated",
        "Evenness across the sheet, largest difference from the mean", "ΔE00",
        "unmeasurable", note="needs nine readings at set positions on one sheet"),
    Row("macro_uniformity_score", "not_evaluated",
        "Macro-uniformity score", "", "unmeasurable",
        note="a scanned-image method; ChromIQ measures patches, not areas"),
    Row("repeatability_de00_max", "not_evaluated",
        "Repeatability from print to print and day to day", "ΔE00",
        "unmeasurable", note="a timed protocol, not a property of one sheet"),
    Row("permanence_de00_max", "not_evaluated",
        "Permanence in storage", "ΔE00", "unmeasurable",
        note="needs climate chambers"),
    Row("fading_24h_de00_max", "not_evaluated",
        "Fading in the dark, first 24 hours", "ΔE00", "unmeasurable",
        note="a timed physical test"),
    Row("light_fastness", "not_evaluated", "Light fastness", "", "unmeasurable",
        note="needs a xenon exposure rig"),
    Row("stabilization_minutes_max", "not_evaluated",
        "Print stabilisation and rub resistance", "", "unmeasurable",
        note="needs the rub apparatus of the standard"),
    Row("tone_value_limits", "not_evaluated", "Tone value reproduction limits", "",
        "unmeasurable", note="ChromIQ measures no tone value"),
    Row("measurement_condition", "not_evaluated",
        "Measurement condition (M0, M1, M2) stated and matched", "",
        "unmeasurable",
        note="ArgyllCMS records no measurement condition in the file"),
)

ROW_BY_ID: "dict[str, Row]" = {r.id: r for r in ROWS}
GROUP_ORDER: "tuple[str, ...]" = tuple(dict.fromkeys(r.group for r in ROWS))


def rows_in_group(group: str) -> "list[Row]":
    return [r for r in ROWS if r.group == group]


# ---------------------------------------------------------------------------
# The sets
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SetDef:
    id: str
    label: str            # English source; display through tr()
    kind: str             # "chromiq" | "iso" | "custom"
    editable: bool
    parent: "str | None" = None   # custom sets start from their parent's factory
    #: one sentence for the pulldown's tooltip (English source)
    blurb: str = ""


SETS: "tuple[SetDef, ...]" = (
    SetDef("chromiq_default", "ChromIQ default (recommended)", "chromiq", True,
           blurb="ChromIQ's own limits: 2.0 on the averages, 3.0 on the "
                 "maxima. The right choice for checking a profile you built."),
    SetDef("chromiq_tight", "ChromIQ tight", "chromiq", True,
           blurb="Half of ChromIQ default: for critical work where a small "
                 "colour difference matters."),
    SetDef("chromiq_quick", "Quick check", "chromiq", True,
           blurb="Twice ChromIQ default: a quick health check that only a "
                 "clearly drifted printer fails."),
    SetDef("iso_12647_7", "ISO 12647-7:2016 values", "iso", False,
           blurb="The published tolerance values of ISO 12647-7:2016 "
                 "(contract proofs), applied to the chart you printed. "
                 "Read-only."),
    SetDef("iso_12647_8", "ISO 12647-8:2021 values", "iso", False,
           blurb="The published tolerance values of ISO 12647-8:2021 "
                 "(validation prints), applied to the chart you printed. "
                 "Read-only."),
    SetDef("custom_iso_12647_7", "Custom ISO 12647-7", "custom", True,
           parent="iso_12647_7",
           blurb="Starts from the ISO 12647-7:2016 values; every limit is "
                 "yours to change."),
    SetDef("custom_iso_12647_8", "Custom ISO 12647-8", "custom", True,
           parent="iso_12647_8",
           blurb="Starts from the ISO 12647-8:2021 values; every limit is "
                 "yours to change."),
)
SET_BY_ID: "dict[str, SetDef]" = {s.id: s for s in SETS}


#: Names that mean "these numbers are somebody's published figures". Matched
#: against a set id and against the label a run stored, and only ever consulted
#: for a set this ChromIQ no longer defines.
_STANDARD_BODY_MARKERS: "tuple[str, ...]" = (
    "iso", "12647", "fogra", "gracol", "swop", "idealliance", "cgats",
)


def applies_a_standard(set_id: "str | None",
                       stored_label: "str | None" = "") -> bool:
    """Whether this set judges with a STANDARD's published figures.

    True for the two read-only ISO columns and ALSO for the Custom columns that
    start from them, and the second half is the point.

    An on-screen round drove the documented route on 2026-09-10: a tester who
    owns the standard puts one number into "Custom ISO 12647-7", the set becomes
    selectable, and the report printed a bold green **PASS** with the sentence
    "Every value this limit set requires was checked and is within its limit."
    No string claimed anything, so the sweep for claim words could not see it:
    the claim was made by JUXTAPOSITION, a column named after a standard beside
    a green PASS with no caveat.

    The cap on an ISO column is not about licensing and never was. It is that a
    standard's figures are written for that standard's own control strip on that
    standard's own chart, and ChromIQ measures the chart YOU printed. Typing the
    numbers in by hand does not change what they are being applied to, so a set
    derived from one carries exactly the same caveat.
    """
    s = SET_BY_ID.get(set_id or "")
    if s is not None:
        if s.kind == "iso":
            return True
        return bool(s.parent) and SET_BY_ID.get(s.parent or "", None) is not None \
            and SET_BY_ID[s.parent].kind == "iso"
    # AN ID WE NO LONGER KNOW IS THE OTHER WAY IN, AND IT WAS OPEN. A run keeps
    # the id and the label of the set it was bound to; when a later ChromIQ no
    # longer defines that id, `set_label` shows the stored label marked
    # "(historical)" and this function used to answer False, so the column read
    # "Custom ISO 12647-7 (historical)" beside a green PASS with no caveat. No
    # string claimed anything; the claim was the arrangement.
    #
    # Judged by NAME, on the id and on whatever label the run stored, because
    # that is all a forgotten set leaves behind. The list is the bodies whose
    # published figures ChromIQ can name at all, so it covers a set that has
    # not been written yet as well as the two that have.
    _hay = f"{set_id or ''} {stored_label or ''}".lower()
    return any(k in _hay for k in _STANDARD_BODY_MARKERS)
SET_IDS: "tuple[str, ...]" = tuple(s.id for s in SETS)
EDITABLE_SET_IDS: "tuple[str, ...]" = tuple(s.id for s in SETS if s.editable)
DEFAULT_SET_ID = "chromiq_default"


def is_known_set(set_id: str) -> bool:
    return set_id in SET_BY_ID


def set_label(set_id: str, stored_label: str = "") -> str:
    """The display label of a set, or the label a run stored when the id is
    no longer known (D23: shown as historical)."""
    s = SET_BY_ID.get(set_id)
    if s is not None:
        return tr(s.label)
    if stored_label:
        return tr("{label} (historical)").format(label=stored_label)
    return tr("{id} (historical)").format(id=set_id or "?")


# ---------------------------------------------------------------------------
# Factory limits
# ---------------------------------------------------------------------------
#: ChromIQ's own numbers. Knut, #182 K4 (2026-09-05) and Q1 (2026-09-06): the
#: default stays 2.0 / 2.0 / 2.0 / 3.0 / 3.0; tight and quick are half and
#: double, "modifiable in the future if needed". The grey-balance pair is a
#: SHOULD limit in every ChromIQ set until a healthy printer has been measured
#: (CH-9, recorded in docs/design/measurement_report_limits.md): exceeding
#: it reads COND, never FAIL.
_CHROMIQ_FACTORY: "dict[str, dict[str, Limit]]" = {
    "chromiq_default": {
        "all_de00_avg": Limit.value(2.0), "best95_de00_avg": Limit.value(2.0),
        "worst5_de00_avg": Limit.value(2.0), "all_de00_max": Limit.value(3.0),
        "all_de00_p95": Limit.value(3.0),
        "grey_balance_neutral_ramp_avg": Limit.should(1.5),
        "grey_balance_neutral_ramp_max": Limit.should(3.0),
    },
    "chromiq_tight": {
        "all_de00_avg": Limit.value(1.0), "best95_de00_avg": Limit.value(1.0),
        "worst5_de00_avg": Limit.value(1.0), "all_de00_max": Limit.value(1.5),
        "all_de00_p95": Limit.value(1.5),
        "grey_balance_neutral_ramp_avg": Limit.should(1.0),
        "grey_balance_neutral_ramp_max": Limit.should(2.0),
    },
    "chromiq_quick": {
        "all_de00_avg": Limit.value(4.0), "best95_de00_avg": Limit.value(4.0),
        "worst5_de00_avg": Limit.value(4.0), "all_de00_max": Limit.value(6.0),
        "all_de00_p95": Limit.value(6.0),
        "grey_balance_neutral_ramp_avg": Limit.should(3.0),
        "grey_balance_neutral_ramp_max": Limit.should(7.0),
    },
}

#: Which rows each ISO set writes a limit over. This is the STRUCTURE of the
#: standard (what it regulates), not its numbers; the numbers come from the
#: data file and read ``?`` while that file is empty. Sources: ISO 12647-7:2016
#: Table 2 and 4.3.2 to 4.3.7; ISO 12647-8:2021 Table 1 and 4.2.1 to 4.2.8
#: (the free previews).
_ISO_ROWS: "dict[str, tuple[str, ...]]" = {
    "iso_12647_7": (
        "substrate_de00_max", "substrate_overprinted_de00_max",
        "substrate_gloss_class", "substrate_fluorescence_class",
        "solids_de00_max", "cmy_solids_dhab_max", "spot_solids_de00_max",
        "control_strip_de00_avg", "control_strip_de00_max",
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
        "all_de00_avg", "all_de00_p95", "outer_gamut_226_de00_avg",
        "uniformity_sd", "uniformity_de00_max_from_mean",
        "repeatability_de00_max", "permanence_de00_max", "light_fastness",
        "stabilization_minutes_max", "tone_value_limits",
        "measurement_condition",
    ),
    "iso_12647_8": (
        "substrate_de00_max", "substrate_gloss_class",
        "substrate_fluorescence_class", "spot_solids_de00_max",
        "control_strip_de00_avg", "control_strip_de00_p95",
        "grey_balance_neutral_ramp_avg", "grey_balance_neutral_ramp_max",
        "all_de00_avg", "all_de00_p95", "surface_gamut_de00_avg",
        "ramps_30_70_dl_max",
        "uniformity_sd", "uniformity_de00_max_from_mean",
        "macro_uniformity_score", "repeatability_de00_max",
        "permanence_de00_max", "fading_24h_de00_max", "light_fastness",
        "stabilization_minutes_max", "tone_value_limits",
        "measurement_condition",
    ),
}

#: The data file. Ships empty (see the module docstring). The environment
#: variable exists so a licence holder can point ChromIQ at their own copy.
ISO_DATA_FILE = "data/compliance_sets/iso12647.json"
ISO_DATA_ENV = "CHROMIQ_COMPLIANCE_ISO_FILE"
_iso_cache: "dict[str, dict[str, Limit]] | None" = None


def _iso_data_path() -> Path:
    override = os.environ.get(ISO_DATA_ENV, "").strip()
    return Path(override) if override else resource_path(ISO_DATA_FILE)


def _load_iso_numbers() -> "dict[str, dict[str, Limit]]":
    """``{set_id: {row_id: Limit}}`` from the data file; unreadable → empty."""
    global _iso_cache
    if _iso_cache is not None:
        return _iso_cache
    out: "dict[str, dict[str, Limit]]" = {}
    path = _iso_data_path()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("compliance data file %s unreadable (%s); ISO cells read ?",
                    path, exc)
        doc = {}
    if isinstance(doc, dict):
        for set_id, cells in doc.items():
            if set_id.startswith("_") or not isinstance(cells, dict):
                continue
            out[set_id] = {rid: Limit.from_json(v) for rid, v in cells.items()
                           if rid in ROW_BY_ID}
    _iso_cache = out
    return out


def reset_iso_cache() -> None:
    """For tests that swap the data file."""
    global _iso_cache
    _iso_cache = None


def factory_limits(set_id: str) -> "dict[str, Limit]":
    """Every row's factory limit for *set_id* (a Custom set: its parent's).

    An ``unmeasurable`` row that a set limits reads ``✕`` whatever the set's
    number is: the cell says "the standard asks this, ChromIQ cannot measure
    it" (D16), and such a row never carries a verdict.
    """
    s = SET_BY_ID.get(set_id)
    if s is None:
        return {r.id: Limit.none() for r in ROWS}
    source = s.parent or s.id
    out: "dict[str, Limit]" = {}
    if source in _CHROMIQ_FACTORY:
        table = _CHROMIQ_FACTORY[source]
        for r in ROWS:
            out[r.id] = table.get(r.id, Limit.none())
    else:
        numbers = _load_iso_numbers().get(source, {})
        touched = set(_ISO_ROWS.get(source, ()))
        for r in ROWS:
            if r.id not in touched:
                out[r.id] = Limit.none()
            elif r.status == "unmeasurable":
                out[r.id] = Limit.unmeasurable()
            else:
                out[r.id] = numbers.get(r.id, Limit.unknown())
    return out


def effective_limits(set_id: str, overrides: "dict | None") -> "dict[str, Limit]":
    """Factory limits with the user's Preferences overrides applied.

    *overrides* is ``{set_id: {row_id: number | None}}`` (None = the user set
    "no limit"). Only editable sets take overrides; a number on a row whose
    factory limit is a *should* stays a should. Unknown row ids are ignored.
    """
    limits = factory_limits(set_id)
    s = SET_BY_ID.get(set_id)
    if s is None or not s.editable or not overrides:
        return limits
    mine = overrides.get(set_id) or {}
    if not isinstance(mine, dict):
        return limits
    for rid, v in mine.items():
        row = ROW_BY_ID.get(rid)
        if row is None or row.status in ("unmeasurable", "unknown"):
            continue
        if v is None:
            limits[rid] = Limit.none()
            continue
        try:
            n = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(n) or n <= 0.0:
            limits[rid] = Limit.none()          # the spin box's "–" (CH-21)
            continue
        limits[rid] = Limit.should(n) if limits[rid].is_should else Limit.value(n)
    return limits


def limit_bearing(limits: "dict[str, Limit]") -> "dict[str, Limit]":
    """The rows a report is actually judged on: numeric limits on rows ChromIQ
    can compute (``now`` / ``build`` / ``ref``)."""
    return {rid: lim for rid, lim in limits.items()
            if lim.is_numeric
            and ROW_BY_ID[rid].status in ("now", "build", "ref")}


def selectable_set_ids(overrides: "dict | None") -> "list[str]":
    """The sets the report window may offer: those with at least one
    limit-bearing row (CH-11: an empty column is never a choice)."""
    return [s.id for s in SETS if limit_bearing(effective_limits(s.id, overrides))]


def limits_to_json(limits: "dict[str, Limit]") -> "dict[str, Any]":
    return {rid: lim.to_json() for rid, lim in limits.items()}


def limits_from_json(doc: "dict | None") -> "dict[str, Limit]":
    """A run's or a report's stored copy back into limits. Unknown row ids are
    KEPT (a report from a newer ChromIQ must not lose them; CH-20)."""
    out: "dict[str, Limit]" = {}
    if isinstance(doc, dict):
        for rid, v in doc.items():
            out[str(rid)] = Limit.from_json(v)
    return out


def is_edited(values: "dict[str, Limit]", set_id: str,
              overrides: "dict | None") -> bool:
    """True when a run's stored copy differs from its set's effective values on
    any limit-bearing row (CH-15: derived, never trusted to a flag)."""
    if not is_known_set(set_id):
        return False
    ref = effective_limits(set_id, overrides)
    for rid in set(ref) | set(values):
        a, b = ref.get(rid, Limit.none()), values.get(rid, Limit.none())
        if a.is_numeric != b.is_numeric:
            return True
        if a.is_numeric and b.is_numeric and abs(a.number - b.number) > 1e-9:
            return True
    return False


# ---------------------------------------------------------------------------
# The two decision rules
# ---------------------------------------------------------------------------
def row_verdict(limit: Limit, value: "float | None", graded: bool) -> "str | None":
    """The word for one row of one column, or None when the cell is not a
    verdict at all (a ``?`` or ``✕`` limit, or a ``–`` limit with no value).

    CH-3, recorded in docs/design/measurement_report_limits.md (no "not
    recorded" case here: a
    report without a recorded verdict is graded live by its caller) and
    CH-20 (a ``–`` row with no value is blank, not INFO).
    """
    if limit.kind in ("unknown", "unmeasurable"):
        return None
    if limit.kind == "none":
        return INFO if value is not None else None
    if value is None:
        return N_A
    if not graded:
        return INFO
    if float(value) <= float(limit.number) + 1e-9:
        return PASS
    return COND if limit.is_should else FAIL


#: Appended to a SAVED verdict when the set it was judged against applies a
#: standard's published figures. The saved word itself is kept, because the
#: design record has Knut ruling that a run keeps its values and verdicts; what
#: may not stand is the word ALONE under a standard's name, because ChromIQ
#: promised a rights holder in writing that it never claims conformance. A
#: challenge round found a saved PASS printed green and unqualified under
#: "Custom ISO 12647-7", in the window and in the PDF.
STANDARD_CAVEAT = ("This limit set holds a standard's published values applied "
                   "to your chart. It is not a test against that standard.")


#: The column summary's sentences (English source; the extractor sweeps this
#: dict, review F6). Filled with {checked} {total} {failed} {cond} {not_computed}.
SUMMARY_REASONS: "dict[str, str]" = {
    "empty": "This limit set defines no limits.",
    # Knut, #182 12b (2026-09-09): showing INFO for a profiling run's report is
    # right, "since the measurements are not a verification run and will most
    # often not fall within set accuracy threshold values. In this case the
    # report output must explain this." The old sentence said the sheet was not
    # graded and stopped there, which explains nothing: a reader who sees big
    # numbers and no verdict is left to guess whether something is wrong.
    "not_graded": "This sheet is not graded, so its numbers are shown for "
                  "information only. It was measured to build a profile rather "
                  "than to check one, and a profiling measurement is expected "
                  "to fall outside the accuracy limits. That is normal here, "
                  "and it is not a fault.",
    # #182 D28, report type T4. The sentence above names a reason that is only
    # true of a PROFILING sheet, and T4 is a deliberate choice about a
    # verification measurement: telling such a reader the sheet "was measured
    # to build a profile" would be false. Same word, INFO, different reason.
    "record_type": "You chose the Printing record, which sets down what was "
                   "printed and measured and judges none of it. The numbers "
                   "are shown for information only. Choose Full colour check "
                   "to have the same measurement graded.",
    # FOUND BUILDING T3, AND REACHABLE TODAY. A column where NOTHING could be
    # checked, and where every row that is missing is a recommendation rather
    # than a requirement, fell through every clause to PASS — under a sentence
    # that says "Every value this limit set requires was checked", with nothing
    # checked at all. T3 shows two bracketed grey rows and nothing else, so it
    # meets that state on the first chart without an 8-step grey ramp, which is
    # most of them; but a 3-patch measurement reaches it in the full report too.
    "nothing_checked": "This chart supplied none of the values this limit set "
                       "puts a limit on, so there is nothing to judge. The "
                       "rows above say what is missing; add those patches to "
                       "the chart in Create Chart to have them checked.",
    "fail": "{failed} of {checked} values checked are over this limit set's limits.",
    "iso": "{checked} of {total} values checked, all within this limit set's "
           "values. This limit set holds a standard's published values applied "
           "to your chart; it is not a test against that standard, and the "
           "values not checked are listed below.",
    "cond_both": "{checked} of {total} values checked, none over a required "
                 "limit; {not_computed} not computed and {cond} over a "
                 "recommended value.",
    "cond_missing": "{checked} of {total} values checked, none over a required "
                    "limit; {not_computed} not computed on this chart.",
    "cond_recommended": "{checked} of {total} values checked, none over a "
                        "required limit; {cond} over a recommended value.",
    "pass": "Every value this limit set requires was checked and is within its limit.",
}


@dataclass(frozen=True)
class Summary:
    word: str
    checked: int          # limit-bearing rows that produced PASS/FAIL/COND
    total: int            # limit-bearing rows
    failed: int
    conditional: int
    not_computed: int     # limit-bearing rows that read N-A
    reason: str           # English source sentence; display through tr()


#: Every reason that means "INFO, because nothing here was judged". The
#: footnote under the results table is chosen by EXACT EQUALITY on the reason
#: string, and a second ungraded reason arriving silently dropped that footnote
#: once already, so the set is named here rather than spelled out at the two
#: places that ask.
def is_ungraded_reason(reason: str) -> bool:
    return reason in (SUMMARY_REASONS["not_graded"],
                      SUMMARY_REASONS["record_type"])


def set_summary(rows: "list[tuple[Limit, str | None]]", *, set_is_iso: bool,
                graded: bool, ungraded_reason: str = "") -> Summary:
    """The column's one word, with the numbers a reader needs beside it.

    *rows* is ``[(limit, word)]`` for every row of the column, words from
    :func:`row_verdict`. Rules (CS §3.3 as amended by CH-9, CH-21, CH-22):

    * no limit-bearing row → N-A ("this limit set defines no limits");
    * a sheet that is not graded (drift check, profiling measurement) → INFO;
    * any FAIL → FAIL;
    * an ISO column is COND at best: its values are applied to a chart that is
      not the standard's chart (footnote 1), so the set was never fully
      tested;
    * any COND, or an N-A on a REQUIRED row → COND (an N-A on a should-row
      does not demote the column);
    * else PASS.
    """
    bearing = [(lim, w) for lim, w in rows if lim.is_numeric]
    total = len(bearing)
    R = SUMMARY_REASONS
    if total == 0:
        return Summary(N_A, 0, 0, 0, 0, 0, R["empty"])
    failed = sum(1 for _l, w in bearing if w == FAIL)
    cond = sum(1 for _l, w in bearing if w == COND)
    not_computed = sum(1 for _l, w in bearing if w == N_A)
    checked = sum(1 for _l, w in bearing if w in (PASS, FAIL, COND))
    if not graded:
        return Summary(INFO, checked, total, failed, cond, not_computed,
                       ungraded_reason or R["not_graded"])
    if checked == 0:
        # A verdict is a statement about measured values. With none of them
        # measured there is no statement to make, and PASS would be a claim
        # about a chart nobody checked. N-A is what the five words already use
        # for "not computed", and the clause above it, "no limit-bearing row",
        # is the same idea one step earlier.
        return Summary(N_A, 0, total, 0, cond, not_computed, R["nothing_checked"])
    if failed:
        return Summary(FAIL, checked, total, failed, cond, not_computed, R["fail"])
    required_missing = sum(1 for lim, w in bearing
                           if w == N_A and not lim.is_should)
    if set_is_iso:
        return Summary(COND, checked, total, failed, cond, not_computed, R["iso"])
    if cond or required_missing:
        # no "0 over a recommended value" clauses (text review)
        key = ("cond_both" if (cond and not_computed)
               else "cond_missing" if not_computed else "cond_recommended")
        return Summary(COND, checked, total, failed, cond, not_computed, R[key])
    return Summary(PASS, checked, total, failed, cond, not_computed, R["pass"])


def summary_text(s: Summary) -> str:
    """The summary's sentence, translated and filled."""
    return tr(s.reason).format(checked=s.checked, total=s.total,
                               failed=s.failed, cond=s.conditional,
                               not_computed=s.not_computed)


# ---------------------------------------------------------------------------
# The two old settings keys → the five rows (the schema-23 migration reads this)
# ---------------------------------------------------------------------------
#: The old "average" threshold judged the three average rows, the old
#: "maximum" threshold the two maximum rows.
OLD_AVG_ROWS: "tuple[str, ...]" = ("all_de00_avg", "best95_de00_avg", "worst5_de00_avg")
OLD_MAX_ROWS: "tuple[str, ...]" = ("all_de00_max", "all_de00_p95")


def legacy_pair(limits: "dict[str, Limit]") -> "tuple[float, float]":
    """``(avg, max)`` for readers of the old ``pass_thresholds`` block: the
    all-patch average and the all-patch maximum, or the factory 2.0 / 3.0."""
    a = limits.get("all_de00_avg")
    m = limits.get("all_de00_max")
    return (float(a.number) if a is not None and a.is_numeric else 2.0,
            float(m.number) if m is not None and m.is_numeric else 3.0)
