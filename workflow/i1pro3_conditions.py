"""THE SWITCH, AND THE FILES, FOR "X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from
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

#: 4.3.49 (Basti, 2026-11-19): the engine's capability word for a record that
#: outlives an end of the conditions (``chromiq_chartread.c`` cq_cond_keep).
KEPT_CAPABILITY = "conditions_kept"

#: ...and the name of a pair in which some read patches have the measurement's
#: own condition only (``<hash>-M1.partial.ti3``): it holds only the patches
#: that have all three, is never offered by Build Profile, and is taken up
#: again by Continue Measurement, which then reads the rest with all three.
PARTIAL_SUFFIX = ".partial.ti3"

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
    """The condition a measurement file holds: the one it records; when it
    records none, the one its pair of condition files leaves free (review
    F1, 2026-11-15); M0 when it records none and has no pair (a measurement
    made before, or with the Beta off: 4.3.40's reading). "" when it records
    none and its condition files do not show it either (one of the two, or
    all three): then nothing may be offered in its name."""
    from workflow.measurement_condition import read_condition
    rec = read_condition(ti3)
    if rec:
        cond = rec.upper()
        return cond if cond in CONDITIONS else "M0"
    return _condition_from_pair(ti3)


def _condition_from_pair(ti3: "str | Path") -> str:
    """For a main file that records no condition. Python records the main
    file's condition at the END of a session, while the engine writes the
    pair during it, so a session measured in M1 or M2 that ended abnormally
    (a crash, a kill) leaves an unrecorded main beside its two siblings. The
    engine writes exactly the two conditions the main is NOT in, named
    ``<hash>-Mx.ti3`` by the main's readings (:meth:`Run.condition_ti3`), so
    when exactly two of the three names exist for these readings the main is
    the third. No such file: M0, as always. One, or all three: ""."""
    try:
        have = [c for c in CONDITIONS
                if (p := sibling_path(ti3, c)) is not None and p.is_file()]
    except Exception:  # noqa: BLE001
        return "M0"
    if not have:
        return "M0"
    free = [c for c in CONDITIONS if c not in have]
    return free[0] if len(free) == 1 else ""


# ---------------------------------------------------------------------------
# The pairing hash (the same function as cq_cond_hash in the helper)
# ---------------------------------------------------------------------------

#: Byte patterns of the data block, kept as SOURCE (compiled where used, the
#: re module caches them): a module-level compiled bytes pattern would be
#: taken for a tool-output parser and searched with text by the suite's
#: census (tests/test_beta10_a_usb_error_flood_is_collapsed.py).
_BEGIN_SRC = rb"^[ \t]*BEGIN_DATA[ \t]*\r?$"
_END_SRC = rb"^[ \t]*END_DATA[ \t]*\r?$"


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
    b = re.search(_BEGIN_SRC, raw, re.MULTILINE)
    if b is None:
        return None
    start = raw.find(b"\n", b.end())
    if start < 0:
        return None
    e = re.compile(_END_SRC, re.MULTILINE).search(raw, start)
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


def partial_sibling_path(main_ti3: "str | Path", cond: str) -> "Path | None":
    """The PARTIAL *cond* file of the readings *main_ti3* holds now
    (``conditions/<hash>-<cond>.partial.ti3``), None without a data block."""
    full = sibling_path(main_ti3, cond)
    if full is None:
        return None
    return full.with_name(full.name[:-len(".ti3")] + PARTIAL_SUFFIX)


def _locs_of(path: "str | Path") -> "list[str]":
    """The SAMPLE_LOC of every row of the first table ([] when unreadable)."""
    try:
        text = Path(path).read_text(encoding="latin-1").replace("\r", "")
        fields = text.split("BEGIN_DATA_FORMAT", 1)[1].split(
            "END_DATA_FORMAT", 1)[0].split()
        data = text.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
        li = fields.index("SAMPLE_LOC")
    except (OSError, IndexError, ValueError):
        return []
    out = []
    for ln in data.splitlines():
        tok = ln.split()
        if len(tok) == len(fields):
            out.append(tok[li].strip('"'))
    return out


def m0_only_locs(main_ti3: "str | Path | None") -> "list[str]":
    """4.3.49: the read patches of *main_ti3* that have only the
    measurement's own condition while others have all three: those not in
    its partial pair (in step), in file order. [] when the complete pair is
    in step, or when there is no partial pair: then nothing is known to be
    missing, except for an i1Pro 2 dual scan, whose read patches are all
    "own condition only" without any pair (the engine takes them back so,
    ``cq_cond_keep_empty``)."""
    if not main_ti3:
        return []
    main = Path(main_ti3)
    try:
        if not main.is_file():
            return []
        own = file_condition(main)
        if not own:
            return []
        others = [c for c in CONDITIONS if c != own]
        if all(condition_file(main, c) is not None for c in others):
            return []
        locs = _locs_of(main)
        have: "set[str] | None" = None
        for c in others:
            sib = partial_sibling_path(main, c)
            if sib is None or not sibling_in_step(main, sib):
                have = None
                break
            got = set(_locs_of(sib))
            have = got if have is None else (have & got)
        if have is None:
            from workflow.dual_scan import storage as dual
            if dual.read_dual_record(main).dual and not averaged_read_count(
                    main):
                # 4.3.49 review SHOULD-1: an AVERAGE is never completed by
                # Continue (it would replace the averaged readings of every
                # strip it reads with one reading), so nothing is listed
                return locs
            return []
        return [loc for loc in locs if loc not in have]
    except Exception:  # noqa: BLE001 - unreadable: nothing promised
        return []


def no_pair_kept(main_ti3: "str | Path | None") -> bool:
    """4.3.49 review SHOULD-1: *main_ti3* is a dual measurement whose read
    patches are ALL M0 only because no pair at all belongs to its readings
    (lost to a save failure, ended in 4.3.48, or the readings were changed:
    imported, replaced, edited). Then "the other strips keep their M1 and M2"
    is not true; Continue Measurement still reads every strip again with
    both passes (the engine's ``cq_cond_keep_empty``)."""
    if not main_ti3 or not m0_only_locs(main_ti3):
        return False
    main = Path(main_ti3)
    own = file_condition(main)
    for c in CONDITIONS:
        if c == own:
            continue
        sib = partial_sibling_path(main, c)
        if sib is None or not sibling_in_step(main, sib):
            return True
    return False


def averaged_read_count(main_ti3: "str | Path | None") -> int:
    """How many reads *main_ti3* is the average of: the run's measurement
    while the run keeps two or more reads (``reads/readN.ti3``, the rule
    `average_missing_reason` uses); 0 for any other measurement."""
    if not main_ti3:
        return 0
    try:
        from core.file_manager import Run
        run = Run.for_dir(Path(main_ti3).parent)
        if Path(main_ti3) != run.measurement_ti3:
            return 0
        n = len(run.reads())
    except Exception:  # noqa: BLE001
        return 0
    return n if n >= 2 else 0


def strip_order(strips: "list[str]") -> "list[str]":
    """Strip labels in chart order without the chart (A..Z, then AA..):
    review N-8, Build Profile named "strips D, C" in file order."""
    return sorted(strips, key=lambda s: (len(s), s))


def strips_of(locs: "list[str]", strip_of=None) -> "list[str]":
    """The strips of *locs*, each once, in order. *strip_of* maps a
    location to its strip (the chart's own labels); default: the letters."""
    out: "list[str]" = []
    for loc in locs:
        s = strip_of(loc) if strip_of else "".join(
            ch for ch in str(loc) if ch.isalpha()).upper()
        if s and s not in out:
            out.append(s)
    return out


def strips_phrase(strips: "list[str]") -> str:
    """"strip C" / "strips C, D" for the sentences that name them (a real
    singular and plural, the house rule)."""
    from core.i18n import tr
    names = ", ".join(strips)
    if len(strips) == 1:
        return tr("strip {names}").format(names=names)
    return tr("strips {names}").format(names=names)


def rows_phrase(strips: "list[str]") -> str:
    """4.3.50: "row C" / "rows C, D" for the i1iO table's notes (the table reads the rows the
    chart prints its letters beside; a real singular and plural)."""
    from core.i18n import tr
    names = ", ".join(strips)
    if len(strips) == 1:
        return tr("row {names}").format(names=names)
    return tr("rows {names}").format(names=names)


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
    own = file_condition(main)
    if not own:
        return None        # its own condition is not known (review F1)
    if cond.upper() == own:
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
    if not own:
        # Review F1: the measurement records no condition and its condition
        # files do not show which one it is, so it is offered only as it is,
        # under no condition's name, and the others are not offered at all.
        why = tr(
            "This measurement does not record which condition it was "
            "measured in, and the files kept beside it do not show it "
            "either (this happens when a measurement ended unexpectedly). "
            "So ChromIQ does not offer other conditions for it: their "
            "readings could be mixed up with the measurement's own. Measure "
            "the chart again to have all three.")
        return [Choice("", main, main=True)] + [
            Choice(c, None, why) for c in CONDITIONS]
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
        out.append(Choice(cond, path, "" if path else (
            _unproven_file_reason(main, cond)
            or average_missing_reason(main, cond) or no_file_reason(main))))
    return out


def _unproven_file_reason(main: Path, cond: str) -> str:
    """Why a file under the pair's name is not used: it does not say that
    it holds these readings ("" when there is no such file)."""
    from core.i18n import tr
    sib = sibling_path(main, cond)
    if sib is None or not sib.is_file():
        return ""
    return tr(
        "There is a file for the {condition} readings of this measurement, "
        "but it does not say that it holds these readings, so ChromIQ does "
        "not use it.").format(condition=cond)


def no_file_reason(main: Path) -> str:
    """Why a measurement has no file for another condition."""
    from core.i18n import tr
    from core.measure_pace import model_key
    from workflow.measurement_condition import read_header_keyword
    from workflow.dual_scan import storage as dual
    from workflow.dual_scan.session import ended_before as _ended
    gaps = strip_order(strips_of(m0_only_locs(main)))
    if gaps:
        # 4.3.49 (Basti, 2026-11-19): the other conditions of the strips
        # already read are kept; these strips have the main condition only
        named = strips_phrase(gaps)
        if dual.read_dual_record(main).dual and no_pair_kept(main):
            # review SHOULD-1: no pair at all, so no other strip keeps any
            return tr(
                "This dual scan has M0 only: no M1 and M2 belong to its "
                "readings as they are now. They could not be kept during the "
                "measurement, or the readings were changed afterwards (for "
                "example imported or replaced). To add them, go to the "
                "Measure tab, tick “Refine / resume existing measurement "
                "(-r)” and press Continue Measurement, with the dual scan "
                "still switched on: ChromIQ takes you back to {strips} for a "
                "new reading with both passes. Until then this measurement "
                "can be built from M0 only.").format(strips=named)
        if dual.read_dual_record(main).dual:
            return tr(
                "M1 and M2 are not available yet, because they are missing "
                "from {strips}, read with M0 only. The other strips keep their "
                "M1 and M2. To complete the measurement, go to the Measure "
                "tab, tick “Refine / resume existing measurement (-r)” and "
                "press Continue Measurement, with the dual scan still switched "
                "on: ChromIQ takes you back to {strips} for a new reading with "
                "both passes. Until then this measurement can be built from M0 "
                "only.").format(strips=named)
        own = file_condition(main) or "M0"
        others = [c for c in CONDITIONS if c != own]
        return tr(
            "{first} and {second} are not available yet, because they are "
            "missing from {strips}, read with {own} only. The other strips "
            "keep their {first} and {second}. To complete the measurement, go "
            "to the Measure tab, tick “Refine / resume existing measurement "
            "(-r)” and press Continue Measurement: ChromIQ takes you back to "
            "{strips} for a new reading with all three conditions. Until then "
            "this measurement can be built from {own} only.").format(
                first=others[0], second=others[1], own=own, strips=named)
    if dual.read_dual_record(main).dual or _ended(main):
        # The i1Pro 2 dual scan (review of 2026-11-18): its M1 and M2 come
        # from a second pass per strip, and exist only once every strip has it.
        # Review of 2026-11-18, M-1: Continue Measurement reads only the
        # strips not read yet, and it cannot take M1 and M2 up again once
        # they ended (the engine's condition files no longer belong to the
        # readings), so it is promised only where it is true.
        if _ended(main):
            return tr(
                "This dual scan has no M1 and M2 that belong to its readings "
                "any more: they ended during the measurement, so its "
                "readings are M0 only. Continue Measurement cannot add M1 "
                "and M2 to it; for M1 and M2, measure the chart again as a "
                "new measurement.")
        n_reads = averaged_read_count(main)
        if n_reads:
            # review SHOULD-1: an average of reads that have no M1 and M2
            return tr(
                "This measurement is the average of {n} reads and has M0 "
                "only: M1 and M2 are averaged only when every read has them. "
                "Continue Measurement does not complete an average, because "
                "it would replace the averaged readings of every strip it "
                "reads with a single reading. For M1 and M2, measure the "
                "chart again with the dual scan switched on, each time you "
                "measure a read to average, so that every read has them."
                ).format(n=n_reads)
        rec = dual.pass_record_of(main)
        unread = ([s for (s, which) in rec.missing() if which == "lamp"]
                  if rec is not None else [])
        if unread:
            return tr(
                "M1 and M2 are not available yet: not every strip has been "
                "read. Continue Measurement, with the dual scan still "
                "switched on, reads the strips still missing ({strips}) with "
                "both passes; until then this measurement is M0."
                ).format(strips=", ".join(unread))
        due = dual.strips_without_second_pass(main)
        if due:
            # read strips whose second pass is missing while the files are
            # in step: not a state the engine leaves, so nothing is promised
            return tr(
                "M1 and M2 are not available yet: the second pass (UV light) "
                "of these strips is missing: {strips}. Until then this "
                "measurement is M0.").format(strips=", ".join(due))
        return tr(
            "There are no M1 and M2 readings for this dual scan as it is now. "
            "They exist only once every strip has its second pass (UV light), "
            "and only until the readings are changed in another way (for "
            "example averaged, imported or replaced).")
    inst = (read_header_keyword(main, "TARGET_INSTRUMENT") or "").strip()
    if inst and model_key(inst) == "i1pro2":
        # 4.3.54 (guide gaps of 2026-11-20, C4): "Only an X-Rite i1Pro 3 ..." read as
        # "the i1Pro 2 cannot", the opposite of its dual scan
        from workflow.dual_scan.session import switch_label, where_label
        return tr(
            "This measurement was read with one pass per strip, without the "
            "i1Pro 2 dual scan, so it has M0 only. For M1 and M2, switch on "
            "“{option}” in {where}, choose M1 or M2 in the Measure tab (or "
            "“{always}” beside the option), and measure the chart again as a new "
            "measurement: each strip is then read twice.").format(
                option=switch_label(), where=where_label(), always=tr("always"))
    if inst and model_key(inst) not in ("i1pro3", "i1pro3plus"):
        return tr(
            "Only an X-Rite i1Pro 3 gives all three conditions from one "
            "scan. This measurement was made with {instrument}."
            ).format(instrument=inst)
    return tr(
        "There are no readings in this condition for the measurement as it "
        "is now. They are kept only for a measurement made with the option "
        "“X-Rite i1Pro 3 and i1Pro 2: keep M0, M1 and M2 from every scan” "
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
    when the conditions agree, the profile records none, or the file belongs
    to no run. *at* is where the measurement was measured when *ti3* is an
    archived copy (`build_report`'s *at*).

    THE SWITCH IS NOT ASKED (review F2, 2026-11-15). A profile built from M1
    stays an M1 profile when the Beta is switched off afterwards, so its
    checks and verifications still follow the condition its build RECORDED
    (this only reads files that are already there). A profile that records
    no condition (built with the Beta off, or before it) gives None, which
    is 4.3.40's behaviour exactly. *settings* is kept for the callers."""
    del settings
    try:
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


# ---------------------------------------------------------------------------
# Averaging (Basti, 2026-11-15: "needed for completeness")
# ---------------------------------------------------------------------------

def _set_condition_of(path: Path, key: str) -> bool:
    """Put ``CHROMIQ_CONDITION_OF "<key>"`` into *path*'s header (replacing
    one that is there); the data is not touched."""
    import re as _re
    try:
        raw = path.read_bytes()
    except OSError:
        return False
    head, sep, rest = raw.partition(b"BEGIN_DATA_FORMAT")
    if not sep:
        return False
    kw = CONDITION_OF_KEYWORD.encode("ascii")
    line = kw + b' "' + key.encode("ascii") + b'"'
    m = _re.search(rb"^[ \t]*" + kw + rb"[ \t]+.*?$", head, _re.MULTILINE)
    if m:
        head = head[:m.start()] + line + head[m.end():]
    else:
        first, nl, after = head.partition(b"\n")
        head = (first + b"\n" + b'KEYWORD "' + kw + b'"\n' + line + b"\n"
                + after)
    try:
        path.write_bytes(head + sep + rest)
    except OSError:
        return False
    return True


def average_conditions(result: "str | Path", reads: "list[Path]",
                       method: str = "mean", *,
                       bin_dir: "str | Path | None" = None,
                       timeout: float = 120.0) -> "dict[str, str]":
    """After the reads were averaged into *result* (the run's measurement),
    average the SAME reads, in the same order and by the same method, in
    each of the two other conditions, and keep each average as the
    condition file of *result*'s readings, so Build Profile can offer it.

    A condition is averaged only when EVERY read has its file in step; when
    one does not, there is none for the average, and the reason is the one
    `no_file_reason` gives for it. Returns ``{condition: ""}`` for each one
    made and ``{condition: <the read that lacks it>}`` for each one not.
    Never raises; the measurement itself is never touched."""
    import shutil
    import subprocess
    import tempfile
    out: "dict[str, str]" = {}
    result = Path(result)
    key = data_block_hash(result)
    if key is None or len(reads) < 2:
        return out
    own = file_condition(result)
    from workflow.dual_scan.storage import average_guard
    mixed = average_guard(reads)
    if mixed:
        # i1Pro 2 dual scans made with different factors (or dual and single
        # reads together): their M1 / M2 must not be averaged into one file.
        # Reported as "average" (not averaged), the honest sentence the
        # caller has today; the UI step may name the factor.
        return {c: "average" for c in CONDITIONS if c != own}
    from core.file_manager import Run
    from workflow.ti3_merge import _resolve_average
    exe = _resolve_average(bin_dir)
    for cond in CONDITIONS:
        if cond == own:
            continue
        files = [condition_file(r, cond) for r in reads]
        missing = [Path(r).name for r, f in zip(reads, files) if f is None]
        if missing:
            out[cond] = missing[0]
            continue
        dst = Run.for_dir(result.parent).condition_ti3(cond, measurement=result)
        if dst is None:
            continue
        work = Path(tempfile.mkdtemp(prefix="chromiq-cond-average-"))
        try:
            tmp = work / "average.ti3"
            args = [exe, "-v"] + (["-e"] if method == "median" else [])
            args += [str(f) for f in files] + [tmp.name]
            proc = subprocess.run(args, cwd=str(work), capture_output=True,
                                  text=True, encoding="utf-8",
                                  errors="replace", timeout=timeout)
            if proc.returncode != 0 or not tmp.is_file():
                out[cond] = "average"
                continue
            if not _set_condition_of(tmp, key):
                out[cond] = "average"
                continue
            from workflow.measurement_condition import record_condition
            record_condition(tmp, cond)
            from workflow.ti3_provenance import stamp
            stamp(tmp)                      # A10 (4.3.50)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp), str(dst))
            out[cond] = ""
        except (OSError, subprocess.SubprocessError):
            out[cond] = "average"
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return out


def average_missing_reason(main: Path, cond: str) -> str:
    """Why an AVERAGED measurement has no *cond* readings: a read it was
    averaged from has none ("" when that is not the reason)."""
    from core.i18n import tr
    try:
        from core.file_manager import Run
        run = Run.for_dir(Path(main).parent)
        if Path(main) != run.measurement_ti3:
            return ""
        reads = run.reads()
    except Exception:  # noqa: BLE001
        return ""
    if len(reads) < 2:
        return ""
    lacking = [r.name for r in reads if condition_file(r, cond) is None]
    if not lacking or len(lacking) == len(reads):
        return ""
    return tr(
        "This measurement is the average of {n} reads, and {read} has no "
        "{condition} readings, so there are none for the average either. "
        "Only a condition every read has is averaged.").format(
            n=len(reads), read=lacking[0], condition=cond)


# ---------------------------------------------------------------------------
# Housekeeping: pairs that no measurement in the run names any more
# ---------------------------------------------------------------------------

_PAIR_NAME_RE = re.compile(r"^(\d+-[0-9a-f]{8})-M[012](?:\.partial)?\.ti3$")
#: The engine's temporary name for a condition file while it writes it
#: (``cq_cond_write``: ``<hash>-Mx.ti3.cqtmp``, renamed into place at once).
#: One is left only when the engine stopped in between (a crash).
_PAIR_TMP_RE = re.compile(r"^(\d+-[0-9a-f]{8})-M[012](?:\.partial)?\.ti3\.cqtmp$")


def prune_pairs(cond_dir: "str | Path", owner: "str | Path") -> "list[Path]":
    """Delete the condition files in *cond_dir* whose readings no measurement
    file anywhere under *owner* holds any more (its ``.ti3``, ``reads/``,
    ``old/``, a dated verification and its archives; *cond_dir* itself left
    out), and return them. Only files named as the engine names them
    (``<hash>-M0|M1|M2.ti3``) AND whose own header says ChromIQ wrote them so
    (:func:`_written_by_us`) are ever deleted; anything else is left alone,
    and so is anything changed in the last 10 minutes (a session that is
    still writing). 4.3.42: also the engine's temporary files of such a pair
    (``<hash>-Mx.ti3.cqtmp``) that a crash left behind in *cond_dir*: only
    that name, only in that folder, only when older than 10 minutes (a
    temporary file is never anyone's readings; the engine renames it into
    place right after writing it). Never raises."""
    import time
    cond_dir, owner = Path(cond_dir), Path(owner)
    gone: "list[Path]" = []
    try:
        if not cond_dir.is_dir():
            return gone
        now = time.time()
        for t in list(cond_dir.iterdir()):
            if not _PAIR_TMP_RE.match(t.name):
                continue
            try:
                if not t.is_file() or t.is_symlink() \
                        or now - t.stat().st_mtime < 600:
                    continue
                t.unlink()
                gone.append(t)
            except OSError:
                continue
        files = [p for p in cond_dir.iterdir()
                 if p.is_file() and _PAIR_NAME_RE.match(p.name)]
        if not files:
            return gone
        held: "set[str]" = set()
        for p in owner.rglob("*"):
            if not p.is_file() or ".ti3" not in p.name:
                continue
            try:
                p.relative_to(cond_dir)
                continue
            except ValueError:
                pass
            if p.parent.name == CONDITION_DIRNAME:
                continue           # another conditions/ folder's files
            key = data_block_hash(p)
            if key:
                held.add(key)
        for f in files:
            m = _PAIR_NAME_RE.match(f.name)
            if m is None or m.group(1) in held:
                continue
            if not _written_by_us(f, m.group(1)):
                continue        # the name alone proves nothing: left alone
            try:
                if now - f.stat().st_mtime < 600:
                    continue
                f.unlink()
                gone.append(f)
            except OSError:
                continue
    except Exception:  # noqa: BLE001 - housekeeping never stops anything
        return gone
    return gone


def _written_by_us(path: Path, key: str) -> bool:
    """True only when *path*'s own header says ChromIQ wrote it as the
    condition file its name gives: a ``CHROMIQ_CONDITION_OF`` of *key* (the
    hash in its name) and a ``MEASUREMENT_CONDITION`` equal to the name's
    ``Mx``, both of which the engine's writer (``cq_cond_write_one``) and
    :func:`average_conditions` put in, and no other tool does. A file named
    like one of ours that does not say so is never deleted."""
    from workflow.measurement_condition import read_header_keyword
    try:
        of = (read_header_keyword(path, CONDITION_OF_KEYWORD) or "").strip()
        cond = (read_header_keyword(path, "MEASUREMENT_CONDITION")
                or "").strip().upper()
    except Exception:  # noqa: BLE001
        return False
    return (of.lower() == key and bool(cond)
            and (path.name.endswith(f"-{cond}.ti3")
                 or path.name.endswith(f"-{cond}{PARTIAL_SUFFIX}")))


def prune_run(run) -> "list[Path]":
    """:func:`prune_pairs` for a run's ``conditions/`` (held by any
    measurement file in the run) and its ``verifications/conditions/`` (held
    by any under ``verifications/``)."""
    gone = prune_pairs(run.condition_dir, run.dir)
    gone += prune_pairs(run.verification_condition_dir, run.verifications_dir)
    # review F7: an EMPTY conditions/ folder (a session with another
    # instrument, or one that ended before its first reading) is taken away;
    # rmdir never removes a folder with anything in it
    for d in (run.condition_dir, run.verification_condition_dir):
        try:
            Path(d).rmdir()
        except OSError:
            pass
    return gone
