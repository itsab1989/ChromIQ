"""Merge pre-conditioning measurement data into a freshly measured .ti3.

Part of the optional "ChromIQ-style refinement process" (gated by the
``chromiq_refinement`` setting). When the user opts in, the patches measured
for an earlier pre-conditioning profile — copied into the refined run as
``preconditioning.ti3`` by ``Project.new_run`` — are merged into the chart
just measured (``chart.ti3``). The combined file (``merged.ti3``) is handed to
colprof, which then builds the profile from more data points.

The concatenation itself is done by ArgyllCMS's own ``average -m`` tool, which
appends the patch rows of two field-compatible measurement files (taking all
header/keyword data from the first input). Before invoking it we verify the two
files share a COLOR_REP and DATA_FORMAT, so an incompatible pairing (e.g. a
different instrument, or spectral vs. tristimulus data) yields a clear message
instead of a terse tool error.

The merged file feeds colprof only; Check & Refine always works from the clean
fresh chart.ti3, so the merged file needs no ChromIQ-specific markup. Validated
against ArgyllCMS 3.5.0: ``average -m`` output is ingested in full by colprof
and read back by profcheck.
"""
from __future__ import annotations

import functools
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.logger import get_logger
from core.proc_text import run_text
from core.resource_path import argyll_binary, argyll_tool_path
from core.text_io import read_text

log = get_logger(__name__)


class Ti3MergeError(Exception):
    """Raised when two measurement files cannot be safely merged.

    Carries a human-readable ``message`` suitable for showing in a dialog.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Ti3MergeConditionUnrecorded(Ti3MergeError):
    """Raised instead of merging when one measurement records no condition
    and another records M1, M2 or M3, and the caller has not said the merge
    may go ahead (review round 2, S-A3): a caller that can ask the person
    asks first (:func:`condition_check`) and passes ``merge_unrecorded``;
    any other caller gets this, which is "Don't merge", with a log line as
    its ``message``."""


@dataclass
class _Parsed:
    color_rep: str
    data_format: list[str]
    n_sets: int
    #: MEASUREMENT_CONDITION ("M0", "M1", "M2"), or "" when the file names
    #: none (every chartread file).
    condition: str = ""


def _parse(path: Path) -> _Parsed:
    """Read just enough of a CGATS .ti3 to validate compatibility before merging."""
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError) as exc:
        # UnicodeDecodeError too: `read_text` refuses a UTF-16 file rather than
        # laundering it through cp1252 into nonsense, and a merge that reports
        # WHICH file it could not read is more use than a traceback.
        raise Ti3MergeError(f"Could not read '{path.name}': {exc}") from exc

    lines = text.splitlines()
    color_rep = ""
    condition = ""
    data_format: list[str] = []

    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("MEASUREMENT_CONDITION"):
            parts = s.split(None, 1)
            if len(parts) == 2:
                condition = parts[1].strip().strip('"').upper()
        elif s.startswith("COLOR_REP"):
            parts = s.split(None, 1)
            if len(parts) == 2:
                color_rep = parts[1].strip().strip('"')
        elif s == "BEGIN_DATA_FORMAT" and i + 1 < len(lines):
            data_format = lines[i + 1].split()

    def _find(token: str) -> int:
        for i, ln in enumerate(lines):
            if ln.strip() == token:
                return i
        return -1

    b, e = _find("BEGIN_DATA"), _find("END_DATA")
    if b == -1 or e == -1 or e <= b:
        raise Ti3MergeError(
            f"'{path.name}' is not a valid measurement file "
            "(missing BEGIN_DATA / END_DATA)."
        )
    if not color_rep or not data_format:
        raise Ti3MergeError(
            f"'{path.name}' is missing its COLOR_REP or DATA_FORMAT header."
        )

    n_sets = sum(1 for ln in lines[b + 1:e] if ln.strip())
    if n_sets == 0:
        raise Ti3MergeError(f"'{path.name}' contains no measurement data.")

    return _Parsed(color_rep, data_format, n_sets, condition)


def _resolve_average(bin_dir: Path | str | None) -> str:
    """Return the path to the ArgyllCMS ``average`` binary (falling back to PATH)."""
    name = argyll_binary("average")
    if bin_dir:
        candidate = argyll_tool_path(bin_dir, "average")
        if candidate.exists():
            return str(candidate)
    return name


#: Conditions whose readings are not M0's: measured with brighteners
#: glowing as daylight shows it (M1), not glowing (M2), or through a
#: polarising filter (M3).
_NOT_M0 = frozenset({"M1", "M2", "M3"})


def conditions_clash(a: str, b: str) -> bool:
    """Whether two measurements' ``MEASUREMENT_CONDITION`` values ("" for
    none) keep them from being merged or averaged: both RECORD a condition,
    and not the same one (review round 2, S-A3, Basti 2026-11-03). One that
    records none against M1, M2 or M3 is not a clash but a question
    (:func:`condition_unrecorded`); none with M0, or none with none, merges
    as before."""
    a = (a or "").strip().upper()
    b = (b or "").strip().upper()
    return bool(a and b and a != b)


def condition_unrecorded(a: str, b: str) -> bool:
    """Whether one of two measurements records no condition while the other
    records M1, M2 or M3: they are combined only when the person says so
    (M-MERGE-CONDITION-ASK, M-AVERAGE-CONDITION-ASK). A file that records
    none may have been measured under any condition (ChromIQ 4.3.22 and
    older recorded none, whatever -F was set to), so ChromIQ cannot tell."""
    a = (a or "").strip().upper()
    b = (b or "").strip().upper()
    return (not a) != (not b) and bool({a, b} & _NOT_M0)


@dataclass
class ConditionCheck:
    """What the recorded conditions of several measurements allow.

    *clash* is the first two files that record different conditions, as
    ``((path, condition), (path, condition))``, or None. When there is no
    clash, *recorded* is the one condition the files that record one share
    ("" when none records one), and *unrecorded* the files that record
    none; :attr:`asks` says whether the person must be asked first."""
    clash: "tuple[tuple[Path, str], tuple[Path, str]] | None"
    recorded: str
    unrecorded: "list[Path]"
    conditions: "list[tuple[Path, str]]"

    @property
    def asks(self) -> bool:
        return (self.clash is None and bool(self.unrecorded)
                and self.recorded in _NOT_M0)

    @property
    def common(self) -> str:
        """The condition every file records ("" when they do not all record
        the same one): what a combined file may say it was measured
        under."""
        if self.clash is None and not self.unrecorded:
            return self.recorded
        return ""

    def lines(self) -> "list[tuple[str, str]]":
        """``(file name, condition in words)`` for the question."""
        return [(Path(p).name, _condition_text(c)) for p, c in self.conditions]


def condition_check(paths) -> ConditionCheck:
    """:class:`ConditionCheck` for the measurements at *paths*, in order."""
    from workflow.measurement_condition import read_condition
    conds = [(Path(p), (read_condition(p) or "").upper()) for p in paths]
    return _check_of(conds)


def _check_of(conds: "list[tuple[Path, str]]") -> ConditionCheck:
    first: "tuple[Path, str] | None" = None
    clash = None
    unrecorded = []
    for p, c in conds:
        if not c:
            unrecorded.append(p)
            continue
        if first is None:
            first = (p, c)
        elif clash is None and c != first[1]:
            clash = (first, (p, c))
    return ConditionCheck(clash, first[1] if first else "", unrecorded,
                          list(conds))


def _condition_text(condition: str) -> str:
    from core.i18n import tr
    if not condition:
        return tr("not recorded")
    from workflow.measurement_condition import condition_name
    return condition_name(condition)


def _not_asked(check: ConditionCheck) -> str:
    from workflow.measurement_condition import condition_name
    from workflow.measurement_messages import condition_not_asked_line
    return condition_not_asked_line(Path(check.unrecorded[0]).name,
                                    condition_name(check.recorded))


def clash_text(check: ConditionCheck, *, averaging: bool = False) -> str:
    """M-MERGE-CONDITION-TOOLS (or M-AVERAGE-CONDITION) for a clash."""
    from workflow import measurement_messages as MM
    (p1, c1), (p2, c2) = check.clash
    fn = MM.average_condition_text if averaging else \
        MM.merge_condition_tools_text
    return fn(Path(p2).name, Path(p1).name, _condition_text(c1),
              _condition_text(c2))


def _mismatch(fresh: _Parsed, pre: _Parsed) -> "str | None":
    """Why the two measurements cannot be merged, or None when they can."""
    if fresh.color_rep != pre.color_rep:
        return (
            "The pre-conditioning measurements use a different colour "
            f"representation ({pre.color_rep}) than the chart just measured "
            f"({fresh.color_rep}). They were likely made with a different "
            "instrument or colour space and cannot be combined.\n\n"
            "The profile will be built from the new measurements only."
        )
    if conditions_clash(fresh.condition, pre.condition):
        # M-MERGE-CONDITION (§M-PROPOSED).
        from workflow.measurement_messages import merge_condition_text
        return merge_condition_text(_condition_text(pre.condition),
                                    _condition_text(fresh.condition))
    if fresh.data_format != pre.data_format:
        return (
            "The pre-conditioning measurements have a different data layout "
            "(e.g. spectral vs. non-spectral, or a different field set) than "
            "the chart just measured, so they cannot be combined.\n\n"
            "The profile will be built from the new measurements only."
        )
    return None


def merge_refusal(fresh_ti3: Path, pre_data: Path) -> "str | None":
    """The check :func:`merge_preconditioning` makes before it runs
    ``average``, without merging anything: why it would refuse, or None.

    The Build Profile command box asks it, so the box shows the ``average``
    merge only when the build will run it; when the build would fall back to
    the fresh measurement alone (a different COLOR_REP or DATA_FORMAT, or a
    file it cannot read), the box shows that instead (review round 1).
    Remembered per file state, as the box asks on every change."""
    try:
        f, p = Path(fresh_ti3).stat(), Path(pre_data).stat()
    except OSError as exc:
        return str(exc)
    return _merge_refusal_of(str(fresh_ti3), f.st_size, f.st_mtime_ns,
                             str(pre_data), p.st_size, p.st_mtime_ns)


@functools.lru_cache(maxsize=16)
def _merge_refusal_of(fresh: str, _fs: int, _fm: int,
                      pre: str, _ps: int, _pm: int) -> "str | None":
    try:
        return _mismatch(_parse(Path(fresh)), _parse(Path(pre)))
    except Ti3MergeError as exc:
        return exc.message


def merge_asks(fresh_ti3: Path, pre_data: Path) -> "ConditionCheck | None":
    """The conditions of the two measurements when the pre-conditioning
    merge must ask before it runs (one records none, the other M1, M2 or
    M3; M-MERGE-CONDITION-ASK), else None. Pre-conditioning first, as the
    question lists them."""
    check = condition_check([pre_data, fresh_ti3])
    return check if check.asks else None


def average_merge_args(fresh_ti3: Path, pre_data: Path,
                       out_ti3: Path) -> "list[str]":
    """The arguments ``average`` is given to merge the two measurements.

    One list for the merge below AND for the Build Profile tab's command box,
    so the command shown is the command run."""
    return ["-m", str(fresh_ti3), str(pre_data), str(out_ti3)]


def merge_preconditioning(
    fresh_ti3: Path,
    pre_data: Path,
    out_ti3: Path,
    bin_dir: Path | str | None = None,
    *,
    merge_unrecorded: bool = False,
) -> int:
    """Merge ``pre_data`` patches into ``fresh_ti3``; write the result to ``out_ti3``.

    When one of the two records no measurement condition and the other M1,
    M2 or M3, the merge is made only with ``merge_unrecorded`` (the person
    answered "Merge them" to M-MERGE-CONDITION-ASK); otherwise
    :class:`Ti3MergeConditionUnrecorded` is raised and nothing is merged.

    ``pre_data`` holds CGATS .ti3 content (typically the run's
    ``preconditioning.ti3``). The merge is performed by ``average -m`` (located
    under ``bin_dir`` if given, otherwise via PATH). Returns the total number of
    sets in the merged file.

    Raises ``Ti3MergeError`` when the two files use a different COLOR_REP or
    DATA_FORMAT — colprof needs a single, consistent column layout — or when the
    ``average`` tool fails.
    """
    from workflow.cal_repair import repair_all
    repair_all([fresh_ti3, pre_data])
    fresh = _parse(fresh_ti3)
    pre = _parse(pre_data)

    refusal = _mismatch(fresh, pre)
    if refusal is not None:
        raise Ti3MergeError(refusal)
    if condition_unrecorded(fresh.condition, pre.condition) \
            and not merge_unrecorded:
        # Nobody said yes: "Don't merge" (review round 2, S-A3).
        raise Ti3MergeConditionUnrecorded(_not_asked(_check_of(
            [(pre_data, pre.condition), (fresh_ti3, fresh.condition)])))

    average = _resolve_average(bin_dir)
    cmd = [average] + average_merge_args(fresh_ti3, pre_data, out_ti3)
    try:
        proc = run_text(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise Ti3MergeError(
            f"Could not run ArgyllCMS 'average' to merge the data: {exc}\n\n"
            "The profile will be built from the new measurements only."
        ) from exc

    if proc.returncode != 0 or not out_ti3.exists():
        detail = (proc.stderr or proc.stdout or "").strip()
        raise Ti3MergeError(
            "ArgyllCMS 'average' could not merge the measurement files"
            + (f":\n{detail}" if detail else ".")
            + "\n\nThe profile will be built from the new measurements only."
        )

    if merge_unrecorded:
        # "Merge them": the merged file records the KNOWN condition, in
        # either order of the two files (`average -m` copies the fresh
        # one's header, which may be the one that records none).
        _record_confirmed(out_ti3, _check_of(
            [(pre_data, pre.condition), (fresh_ti3, fresh.condition)]))

    total = fresh.n_sets + pre.n_sets
    log.info(
        "Merged measurements via 'average -m': %d fresh + %d pre-conditioning "
        "= %d sets -> %s",
        fresh.n_sets, pre.n_sets, total, out_ti3.name,
    )
    return total


def merge_measurements(
    inputs: list[Path],
    out_ti3: Path,
    bin_dir: Path | str | None = None,
    *,
    merge_unrecorded: bool = False,
) -> int:
    """Concatenate the patches of ``inputs`` into ``out_ti3`` via ``average -m``.

    Inputs that record two different measurement conditions are refused
    (M-MERGE-CONDITION-TOOLS). When some record none and the others M1, M2
    or M3, they are merged only with ``merge_unrecorded``; otherwise
    :class:`Ti3MergeConditionUnrecorded` is raised.

    Generalises :func:`merge_preconditioning` to any number of measurement
    files (two or more). The first input is the primary: ``average -m`` takes
    its header/keyword data and appends every other input's patch rows.

    Every input must share the primary's COLOR_REP and DATA_FORMAT — colprof
    needs one consistent column layout — otherwise a ``Ti3MergeError`` naming
    the offending file is raised. Returns the total number of sets written.
    """
    if len(inputs) < 2:
        raise Ti3MergeError("Merging needs at least two measurement files.")

    from workflow.cal_repair import repair_all
    repair_all(inputs)
    primary = _parse(inputs[0])
    parsed = [primary] + [_parse(p) for p in inputs[1:]]
    # EVERY PAIR, not only each file against the primary: two additional
    # files of M1 and M2 beside a primary that records none clash too.
    check = _check_of([(Path(p), x.condition)
                       for p, x in zip(inputs, parsed)])
    if check.clash is not None:
        # M-MERGE-CONDITION-TOOLS (§M-PROPOSED).
        raise Ti3MergeError(clash_text(check))
    total = primary.n_sets
    for extra_path, extra in zip(inputs[1:], parsed[1:]):
        if extra.color_rep != primary.color_rep:
            raise Ti3MergeError(
                f"'{extra_path.name}' uses a different colour representation "
                f"({extra.color_rep}) than the primary file "
                f"'{inputs[0].name}' ({primary.color_rep}). They were likely "
                "made with a different instrument or colour space and cannot "
                "be combined."
            )
        if extra.data_format != primary.data_format:
            raise Ti3MergeError(
                f"'{extra_path.name}' has a different data layout (e.g. spectral "
                "vs. non-spectral, or a different field set) than the primary "
                f"file '{inputs[0].name}', so they cannot be combined."
            )
        total += extra.n_sets
    if check.asks and not merge_unrecorded:
        raise Ti3MergeConditionUnrecorded(_not_asked(check))

    average = _resolve_average(bin_dir)
    cmd = [average, "-m", *(str(p) for p in inputs), str(out_ti3)]
    try:
        proc = run_text(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    except OSError as exc:
        raise Ti3MergeError(
            f"Could not run ArgyllCMS 'average' to merge the data: {exc}"
        ) from exc

    if proc.returncode != 0 or not out_ti3.exists():
        detail = (proc.stderr or proc.stdout or "").strip()
        raise Ti3MergeError(
            "ArgyllCMS 'average' could not merge the measurement files"
            + (f":\n{detail}" if detail else ".")
        )

    if merge_unrecorded:
        # "Merge them": the KNOWN condition, whichever file is the primary.
        _record_confirmed(out_ti3, check)

    log.info(
        "Merged %d measurement files via 'average -m' = %d sets -> %s",
        len(inputs), total, out_ti3.name,
    )
    return total


def _record_confirmed(out_ti3: Path, check: ConditionCheck) -> None:
    """After a merge the person confirmed ("Merge them"): *out_ti3* records
    the known condition (:func:`settle_combined_condition`)."""
    if check.asks:
        settle_combined_condition(out_ti3, check, confirmed=True)


def settle_combined_condition(result: Path, check: ConditionCheck, *,
                              confirmed: bool = False) -> None:
    """After ``average`` has combined measurements into *result*: the
    condition it says it was measured under.

    * every input records the same one: that one (review round 2, S-A2);
    * some record none and the others M1, M2 or M3, and the person answered
      "Merge them" / "Average them" (*confirmed*): the KNOWN one, the
      condition the recorded files name. The answer says they were all
      measured the same way, so the result is that condition's readings,
      and FWA stays refused for M1/M2 (Basti 2026-11-03). ``average`` copies
      the FIRST file's header, so without this the result named whatever
      the first file had, or nothing, and FWA could be allowed on M1/M2
      data;
    * otherwise (none beside M0, which nobody was asked about): nothing.

    Only the header is changed (:func:`record_condition`)."""
    from workflow.measurement_condition import (clear_condition,
                                                record_condition)
    try:
        if check.common:
            record_condition(result, check.common)
        elif confirmed and check.asks:
            if record_condition(result, check.recorded):
                log.info("combined %s records %s: confirmed as measured "
                         "the same way", Path(result).name, check.recorded)
        elif clear_condition(result):
            log.info("averaged %s records no measurement condition: not "
                     "every input recorded the same one", Path(result).name)
    except Exception:      # noqa: BLE001 — never fail an average over this
        log.debug("condition of %s not settled", result, exc_info=True)
