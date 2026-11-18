"""THE i1Pro 2 DUAL SCAN IN THE MEASURE TAB (the UI step, 2026-11-18).

What the Measure tab asks before START, what it passes the engine, and the
sentences it shows for the engine's dual-scan events. Pure rules: no widget
here, so every decision is tested on its own (``tests/test_i1pro2_dual_scan_
ui.py``).

* **Where it is switched on**: Preferences > Beta, "X-Rite i1Pro 2: M1 and M2
  by a dual scan", which lives under "X-Rite i1Pro 3: keep M0, M1 and M2
  from every scan" and works only with it on: the dual scan ends in exactly
  that Beta's files (``storage``). Both off, or either: the app is unchanged.
* **The filter row chooses the MAIN condition** (the coordinator's decision of
  2026-11-18): with the dual scan on, the row's M0 / M1 / M2 is NOT sent as
  ArgyllCMS's ``-F`` (an i1Pro 2 refuses every ``-F``); it is recorded with
  ``--dual-chosen`` and Build Profile is pre-set to it once every strip has
  both passes. The main file stays physically M0. The polariser and the D65
  filter are refused before START (``M-DUAL-FILTER-NOT-DUAL``).
* **Only for an i1Pro 2**: an instrument this app run has already seen as
  another model (an i1Pro 3 keeps its own ``-F``) is measured as before. The
  very first measurement of a run cannot know the model before START; the
  switch says "i1Pro 2", so it is taken at its word, and an i1Pro 3 then
  measures M0 with M1 and M2 kept beside it by its own Beta.
* **Never mixed**: :func:`storage.start_guard` before START; a measurement
  started with another factor continues with its own
  (:func:`storage.continuation_choice`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from core.i18n import tr
from workflow.dual_scan import storage
from workflow.dual_scan.reasons import NOTES, REASONS
from workflow.dual_scan.scale import REFINED_SOURCE, ScaleChoice

#: AppSettings key of the Beta switch (core/settings.py)
SETTING = "i1pro2_dual_scan_beta"

#: the filter row's ``-F`` value -> the condition chosen with the dual scan
FILTER_CHOICE = {None: "M0", "": "M0", "n": "M0", "5": "M1", "u": "M2"}
#: the row's choices an i1Pro 2 has nothing for, even with the dual scan
NOT_DUAL_FILTERS = ("p", "6")

#: the reason ids the hand measurement can show (every one has its sentence
#: translated: ``scripts/i18n_extract.py`` reads this tuple). The refining
#: reasons are not here: refining the factor has no window yet.
SHOWN_REASONS = (
    "no_dual_calibration", "uv_tile_dark", "calibration_mismatch",
    "no_uv_tables", "bad_uv_tables",
    "uv_pass_missing", "uv_pass_count", "uv_pass_short", "uv_pass_too_fast",
    "uv_pass_too_long", "uv_pass_stalled", "uv_pass_wrong_strip",
    "uv_pass_no_uv_light", "uv_pass_misaligned", "lamp_pass_changed",
    "dual_needs_ruler", "uv_spot_failed", "no_ruler",
    "calibration_mode_changed", "bad_values", "bad_scale",
    "mixed_scan_kind", "mixed_factor", "dual_high_resolution",
)
SHOWN_NOTES = tuple(NOTES)


def switched_on(settings: Any) -> bool:
    """Preferences > Beta: the dual-scan switch AND the i1Pro 3 Beta it
    belongs to (the files are that Beta's)."""
    from workflow import i1pro3_conditions as conditions
    try:
        return bool(conditions.stored_value(settings)) and bool(
            settings.get(SETTING, False))
    except Exception:  # noqa: BLE001 - a broken store means "off"
        return False


def helper_can(caps: Iterable[str]) -> bool:
    """The engine knows the dual scan's files AND can drive the UV light."""
    caps = set(caps or ())
    return storage.CAPABILITY in caps and storage.DEVICE_CAPABILITY in caps


def other_instrument(reported_model: "str | None") -> bool:
    """This app run has seen the instrument, and it is not an i1Pro 2."""
    from core.measure_pace import model_key
    key = model_key(reported_model) if reported_model else None
    return key is not None and key != "i1pro2"


@dataclass(frozen=True)
class Plan:
    """What START does about the dual scan.

    *dual*: pass :meth:`args` (and drop ``-F``); *refusal*: a reason the
    measurement must not start (``"filter_not_dual"`` or a
    :data:`REASONS` id); *why_not*: for the app log only."""
    dual: bool
    chosen: str = "M0"
    refusal: str = ""
    choice: "ScaleChoice | None" = None
    white: str = "instrument"
    why_not: str = ""

    def args(self) -> "list[str]":
        if not self.dual or self.choice is None:
            return []
        return storage.helper_args(self.choice, self.white, self.chosen)


def plan_for(settings: Any, caps: Iterable[str], reported_model: "str | None",
             filter_code: "str | None", main_ti3=None,
             choice: "ScaleChoice | None" = None) -> Plan:
    """The dual scan's plan for one START (see the module docstring).
    *main_ti3*: the measurement this read continues (None: a new one);
    *choice*: the factor (default: the standard one)."""
    if not switched_on(settings):
        return Plan(False, why_not="off")
    if not helper_can(caps):
        return Plan(False, why_not="helper")
    if other_instrument(reported_model):
        return Plan(False, why_not="other_instrument")
    code = (str(filter_code).strip().lower() if filter_code is not None
            else None)
    if code in NOT_DUAL_FILTERS:
        return Plan(False, refusal="filter_not_dual")
    chosen = FILTER_CHOICE.get(code, "M0")
    choice = choice or ScaleChoice.standard()
    white = "instrument"
    guard = storage.start_guard(main_ti3, True, choice, white)
    if guard == "mixed_factor":
        cont = storage.continuation_choice(main_ti3)
        if cont is not None:
            choice, white = cont
            guard = storage.start_guard(main_ti3, True, choice, white)
    if guard:
        return Plan(False, refusal=guard)
    return Plan(True, chosen, choice=choice, white=white)


def single_scan_refusal(settings: Any, caps: Iterable[str],
                        reported_model: "str | None", main_ti3) -> str:
    """A single-scan START on a dual measurement: ``"mixed_scan_kind"``, else
    "". Asked only where the dual scan does not apply but the engine could
    have done it, so an app without the Beta is unchanged."""
    if not helper_can(caps):
        return ""
    return storage.start_guard(main_ti3, False) or ""


def without_filter(extra_args: str) -> str:
    """*extra_args* (chartread's extra arguments, one string) with ``-F``
    and its value taken out: the dual scan records the row's choice instead
    of sending it."""
    import shlex
    if not extra_args:
        return extra_args
    try:
        toks = shlex.split(extra_args)
    except ValueError:
        return extra_args
    out: "list[str]" = []
    skip = False
    for t in toks:
        if skip:
            skip = False
            continue
        if t == "-F":
            skip = True
            continue
        if t.startswith("-F") and len(t) > 2:
            continue
        out.append(t)
    return shlex.join(out)


# ---------------------------------------------------------------------------
# The engine's events, in words
# ---------------------------------------------------------------------------

def reason_id(why: str) -> str:
    """The :data:`REASONS` id behind an engine ``why`` ("dual_uv_tile_dark",
    "dual_dual_needs_ruler", "dual_high_resolution", "uv_pass_short"), or ""."""
    w = str(why or "").strip()
    for cand in (w, w[5:] if w.startswith("dual_") else ""):
        if cand and cand in REASONS:
            return cand
    if w == "mixed":
        return "mixed_scan_kind"
    return ""


def reason_sentence(why: str) -> str:
    """The sentence for an engine ``why``, translated; a reason without a
    sentence of its own gets a plain one."""
    rid = reason_id(why)
    if rid:
        return tr(REASONS[rid])
    return tr(
        "Something unexpected happened while ChromIQ worked out M1 and M2 "
        "(the engine's reason: {why}).").format(why=str(why or "?"))


def note_sentence(note: str) -> str:
    return tr(NOTES[note]) if note in NOTES else ""


def source_word(source: str) -> str:
    return tr("refined") if source == REFINED_SOURCE else tr("standard")


def is_dual_conditions_event(ev: dict) -> bool:
    return bool(ev.get("active")) and bool(ev.get("dual"))


def ends_dual(ev: dict) -> bool:
    """A conditions event that ends M1 / M2 of a dual session (``why``
    "dual_..." or "mixed"); the i1Pro 3 Beta's own reasons are not."""
    if ev.get("active"):
        return False
    why = str(ev.get("why") or "")
    return why.startswith("dual_") or why == "mixed"


def calibration_ok(ev: dict) -> bool:
    return bool(ev.get("ok"))


def switch_label() -> str:
    """The Preferences > Beta switch, as it is named everywhere."""
    return tr("X-Rite i1Pro 2: also M1 and M2, by a dual scan (beta, first "
              "try)")


def where_label() -> str:
    return tr("Preferences > Beta")
