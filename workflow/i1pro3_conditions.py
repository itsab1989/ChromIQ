"""THE SWITCH, AND THE FILES, FOR "X-Rite i1Pro 3: keep M0, M1 and M2 from
every scan" (Preferences > Beta, 2026-11-15).

An i1Pro 3 reads every strip in ONE pass, alternating its lamp LEDs and its
ultraviolet LEDs, and ArgyllCMS's i1Pro 3 driver works out from that pass,
with the instrument's own factory data, the reading under all three ISO 13655
conditions: M0 (the lamp), M1 (D50 daylight with its UV) and M2 (UV cut).
Today the driver hands back the one the Measure tab's "Spectral filter type
(-F)" chose. With this Beta the chart-reading engine keeps the other two as
well, from the same pass, with nothing extra sent to the instrument
(``native/instlib/i1pro3_imp.c``, ``i1pro3_cq_cond_*``).

THE FILES. ``<stem>.ti3`` stays THE measurement, exactly as today, in the
condition -F chose. The other two are written by the engine in the same
autosave into the run's ``conditions/`` folder, NAMED BY a hash of the main
file's readings (:func:`data_block_hash`): ``conditions/<hash>-M1.ti3`` and
``-M2.ti3`` (:meth:`core.file_manager.Run.condition_ti3`). So whatever brings
the main file's readings back (a Discard, a read put back, a restore from
``old/``, a duplicated run) brings their pair back with them, and a main file
whose readings changed without the engine (averaged, imported, edited) has
none: it is never paired with readings that are not its own. Each file also
carries its ``MEASUREMENT_CONDITION`` and ``CHROMIQ_CONDITION_OF`` (the hash).

Read at every Start (Measure) and whenever Build Profile shows a run, like
the ruler check: no restart. Off: nothing in Measure, Build Profile or Check
& Refine asks for a condition file, and the helper is started with exactly
4.3.40's command line.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

#: The AppSettings key (``core.settings.DEFAULTS``: False).
SETTING = "i1pro3_conditions_beta"

#: The engine's capability word (``--caps``).
CAPABILITY = "i1pro3_conditions"

#: The three conditions the i1Pro 3 gives from one pass, in menu order.
CONDITIONS = ("M0", "M1", "M2")

#: The condition file's header keyword naming the main file's readings.
CONDITION_OF_KEYWORD = "CHROMIQ_CONDITION_OF"

#: The run's folder for them (``Run.condition_dir``).
CONDITION_DIRNAME = "conditions"

#: ``RunMeta.profile_settings`` key of Build Profile's "Build from" choice
#: ("" = as measured). Written only while the Beta is on.
BUILD_FROM_KEY = "build_from_condition"

#: ``RunMeta.profile_build`` keys recording what a profile was built from.
BUILT_FROM_KEY = "measurement_condition"
BUILT_FILE_KEY = "measurement_file"


def stored_value(settings: Any) -> bool:
    """Whether the Beta is on in Preferences (a broken store means off)."""
    try:
        return bool(settings.get(SETTING, False))
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# The main file's condition
# ---------------------------------------------------------------------------

def main_condition(filter_code: "str | None") -> "str | None":
    """The condition the MAIN file is measured in for the Measure tab's -F
    *filter_code* (None / "n" = M0, "5" = M1, "u" = M2), or None when the
    Beta does not apply (the polariser, D65)."""
    if not filter_code:
        return "M0"
    from workflow.measurement_condition import condition_for_filter
    cond = condition_for_filter(filter_code)
    return cond if cond in CONDITIONS else None


def file_condition(ti3: "str | Path") -> str:
    """The condition a measurement file records (M0 when it says none)."""
    from workflow.measurement_condition import read_condition
    cond = (read_condition(ti3) or "M0").upper()
    return cond if cond in CONDITIONS else "M0"


# ---------------------------------------------------------------------------
# The pairing hash (the same function as cq_cond_hash in the helper)
# ---------------------------------------------------------------------------

_BEGIN_RE = re.compile(rb"^[ \t]*BEGIN_DATA[ \t]*\r?$", re.MULTILINE)
_END_RE = re.compile(rb"^[ \t]*END_DATA[ \t]*\r?$", re.MULTILINE)


def data_block_hash(path: "str | Path") -> "str | None":
    """``<length>-<crc32>`` of the bytes between the FIRST ``BEGIN_DATA``
    line and the ``END_DATA`` line after it (the last row's line end
    included), every ``\\r`` left out, CRC-32 as zlib computes it; None when
    the file has no such block. A header edit (the condition keywords, a
    repaired instrument name) or another table after the first (a
    calibration) does not change it. Not a security check: it tells
    "these readings" from "other readings"."""
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    b = _BEGIN_RE.search(raw)
    if b is None:
        return None
    start = raw.find(b"\n", b.end())
    if start < 0:
        return None
    e = _END_RE.search(raw, start)
    if e is None:
        return None
    return block_hash(raw[start + 1:e.start()].replace(b"\r", b""))


def block_hash(data: bytes) -> str:
    import zlib
    return f"{len(data)}-{zlib.crc32(data) & 0xffffffff:08x}"


def sibling_path(main_ti3: "str | Path", cond: str) -> "Path | None":
    """The *cond* file of the readings *main_ti3* holds now, by the run's own
    path rule (:meth:`core.file_manager.Run.condition_ti3`); None when the
    file has no data block to name it by. A measurement kept in ``reads/``
    or ``old/`` finds its pair in the run's folder, a verification's in the
    run's ``verifications/conditions/`` (:meth:`Run.condition_dir_of`)."""
    from core.file_manager import Run
    return Run.for_dir(Path(main_ti3).parent).condition_ti3(
        cond, measurement=Path(main_ti3))


def sibling_in_step(main: "str | Path", sibling: "str | Path") -> bool:
    """True when *sibling* holds the readings *main* holds now: its name and
    its ``CHROMIQ_CONDITION_OF`` both carry the main file's hash."""
    from workflow.measurement_condition import read_header_keyword
    if not Path(sibling).is_file() or not Path(main).is_file():
        return False
    have = data_block_hash(main)
    want = read_header_keyword(sibling, CONDITION_OF_KEYWORD)
    return (have is not None and bool(want) and want.lower() == have
            and Path(sibling).name.startswith(have + "-"))


def condition_file(main_ti3: "str | Path | None", cond: "str | None"
                   ) -> "Path | None":
    """The file holding *main_ti3*'s readings under *cond*: the main file
    itself for its own condition, the condition file when it is in step,
    else None."""
    if not main_ti3 or not cond:
        return None
    main = Path(main_ti3)
    if not main.is_file():
        return None
    if cond.upper() == file_condition(main):
        return main
    sib = sibling_path(main, cond.upper())
    return sib if sib is not None and sibling_in_step(main, sib) else None


# ---------------------------------------------------------------------------
# What Build Profile may offer
# ---------------------------------------------------------------------------

class Choice:
    """One entry of the "Build from" list: *cond*, the file to build from
    (None = not usable here), and *reason* (why not, user-facing) or ""."""

    def __init__(self, cond: str, path: "Path | None", reason: str = "",
                 main: bool = False) -> None:
        self.cond, self.path, self.reason, self.main = cond, path, reason, main

    @property
    def usable(self) -> bool:
        return self.path is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging only
        return f"Choice({self.cond!r}, {self.path!r}, main={self.main})"


def choices_for(main_ti3: "str | Path | None", *,
                merging: bool = False) -> "list[Choice]":
    """The conditions *main_ti3* can be built from: the main file's own
    condition first (always usable), then the other two, each usable only
    when its condition file is in step and the build does not merge."""
    from core.i18n import tr
    if not main_ti3 or not Path(main_ti3).is_file():
        return []
    main = Path(main_ti3)
    own = file_condition(main)
    out = [Choice(own, main, main=True)]
    for cond in CONDITIONS:
        if cond == own:
            continue
        if merging:
            out.append(Choice(cond, None, tr(
                "This build merges the run's measurement with the earlier "
                "measurement it refines, which was kept in one condition "
                "only. So this profile can only be built from the condition "
                "chosen in the Measure tab.")))
            continue
        path = condition_file(main, cond)
        out.append(Choice(cond, path, "" if path else no_file_reason(main)))
    return out


def no_file_reason(main: Path) -> str:
    """Why a measurement has no file for another condition."""
    from core.i18n import tr
    from core.measure_pace import model_key
    from workflow.measurement_condition import read_header_keyword
    inst = (read_header_keyword(main, "TARGET_INSTRUMENT") or "").strip()
    if inst and model_key(inst) not in ("i1pro3", "i1pro3plus"):
        return tr(
            "Only an X-Rite i1Pro 3 gives all three conditions from one "
            "scan. This measurement was made with {instrument}."
            ).format(instrument=inst)
    return tr(
        "There are no readings in this condition for the measurement as it "
        "is now. They are kept only for a measurement made with the option "
        "“X-Rite i1Pro 3: keep M0, M1 and M2 from every scan” "
        "switched on, and only until its readings are changed in another "
        "way (for example averaged, imported or replaced).")


# ---------------------------------------------------------------------------
# Verifications (Basti, 2026-11-15): a verification is judged in the
# condition its run's profile was built from
# ---------------------------------------------------------------------------

def beta_on() -> bool:
    """The switch as Preferences holds it, for code that has no settings
    object of its own (the measurement report)."""
    try:
        from core.settings import AppSettings
        return stored_value(AppSettings())
    except Exception:  # noqa: BLE001
        return False


def profile_condition(run) -> str:
    """The condition *run*'s profile was built from, as its build record
    says ("" when it records none: built with the Beta off, or before)."""
    try:
        built = getattr(run.load_meta(), "profile_build", None) or {}
    except Exception:  # noqa: BLE001
        return ""
    cond = str(built.get(BUILT_FROM_KEY) or "").upper()
    return cond if cond in CONDITIONS else ""


class ProfileReadings:
    """How a measurement meets the condition its run's profile was built
    from: *condition* (the profile's), *own* (the measurement's), *path*
    (the file holding the readings in the profile's condition, None when
    there is none)."""

    def __init__(self, condition: str, own: str, path: "Path | None",
                 verification: bool = False) -> None:
        self.condition, self.own, self.path = condition, own, path
        self.verification = verification

    @property
    def other(self) -> bool:
        return self.condition != self.own

    def __repr__(self) -> str:  # pragma: no cover - debugging only
        return (f"ProfileReadings({self.condition!r}, own={self.own!r}, "
                f"path={self.path!r})")


def profile_readings(ti3: "str | Path", *, at: "str | Path | None" = None,
                     settings: Any = None) -> "ProfileReadings | None":
    """For a measurement of a run whose profile was built (with the Beta on)
    from ANOTHER condition than the measurement's own: that condition and
    the file holding these readings in it (None when there is none). None
    when the conditions agree, the profile records none, the file belongs to
    no run, or the Beta is off. *at* is where the measurement was measured
    when *ti3* is an archived copy (`build_report`'s *at*)."""
    try:
        on = stored_value(settings) if settings is not None else beta_on()
        if not on:
            return None
        from workflow.run_compliance import run_context_for
        ctx = run_context_for(at or ti3)
        if ctx is None:
            return None
        cond = profile_condition(ctx.run)
        own = file_condition(ti3)
        if not cond or cond == own:
            return None
        return ProfileReadings(cond, own, condition_file(ti3, cond),
                               verification=ctx.verification is not None)
    except Exception:  # noqa: BLE001 - a report is never stopped by this
        return None
