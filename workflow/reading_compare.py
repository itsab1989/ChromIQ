"""Two readings of one chart, compared patch by patch (4.3.32, jctay).

Tools ▸ Inspect a measurement ("Measurement info") can take a second reading
of the same chart beside the measurement it shows: another ``.ti3``, a CGATS
text file with XYZ or L*a*b* values, or an i1Profiler ``.mxf`` / ``.cxf``
(converted on the fly into a temporary folder by the import's own converter).
It reports where the two readings disagree, by ΔE₀₀, and nothing else: no
measurement is changed and nothing reaches a profile.

THE PAIRING IS CHECKED BEFORE ANY NUMBER IS SHOWN, by the rule Tools ▸ Verify
against reference uses since 4.3.30 (`colverify_runner.reference_mismatch`):
the same number of patches, every patch number present, and the device values
of every pair within ``PATCH_IDENTITY_TOL``. Two readings of one chart that
were saved on different grids or in different orders (a turned i1Profiler
measurement beside the imported one, say) carry the same patch numbers on
different patches; they are paired by their device values instead, but only
when every device value names exactly one patch in each file, so the pairing
is never a choice between equal candidates. Anything else is refused with
M-READINGS-NOT-SAME-CHART, never compared patch by wrong patch (measured
2026-11-11: the same readings with their patch numbers moved on by six gave
an average ΔE₀₀ of 18 instead of 0.2).
"""
from __future__ import annotations

import math
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from core.i18n import tr
from core.logger import get_logger

log = get_logger(__name__)

#: The tolerances offered for "above the tolerance", in ΔE₀₀. jctay's own
#: numbers (forum, 2026-11-10): about 1.0 for a chart scanned with an i1Pro,
#: 0.5 for a very consistent setup; 2.0 for a hand-held reading. The default
#: is the scanning one.
TOLERANCE_PRESETS = (0.5, 1.0, 2.0)
DEFAULT_TOLERANCE = 1.0
#: The custom tolerance's range and step in the window.
TOLERANCE_MIN, TOLERANCE_MAX, TOLERANCE_STEP = 0.1, 10.0, 0.1

#: How many of the worst patches the window lists (the saved text lists every
#: patch above the tolerance).
WORST_SHOWN = 10

#: A strip "disagrees as a whole" when at least this share of its patches is
#: above the tolerance, and it has at least this many patches. One misread
#: strip in a reading (a slip, the wrong strip read) shows up exactly so,
#: while instrument noise scatters over the whole chart.
WHOLE_STRIP_SHARE = 0.75
WHOLE_STRIP_MIN_PATCHES = 3


class ReadingsNotComparable(Exception):
    """The second reading cannot be compared with the measurement.

    *message* is M-READINGS-NOT-SAME-CHART or M-READINGS-UNUSABLE, *reason*
    its translated {reason}; :meth:`render` gives (title, body) for *file*."""

    def __init__(self, message, reason: str) -> None:
        super().__init__(reason)
        self.message = message
        self.reason = reason

    def render(self, file: str) -> "tuple[str, str]":
        return self.message.render(file=file, reason=self.reason)


@dataclass
class Reading:
    """One reading, as compared: its patches in file order."""
    path: Path
    ids: "list[str]"
    locs: "list[str]"
    device: np.ndarray            # (N, k) device values, or (0, k) when none
    lab: np.ndarray               # (N, 3) L*a*b* D50
    condition: str = ""           # the measurement condition, when known
    converted_from_cxf: bool = False
    #: paired through the turned i1Profiler order on import: its patch
    #: numbers are the chart's, not the ones i1Profiler's own files carry
    turned: bool = False
    instrument: str = ""          # the instrument, as the file names it
    measured_on: str = ""         # when it was read, as the file says


@dataclass
class PatchDiff:
    sid: str
    loc: str
    strip: "str | None"
    position: "int | None"        # 1-based place in its strip
    lab_a: tuple
    lab_b: tuple
    de: float


@dataclass
class StripSummary:
    label: str
    n: int
    mean: float
    worst: float
    above: int

    @property
    def whole_strip_off(self) -> bool:
        return (self.n >= WHOLE_STRIP_MIN_PATCHES
                and self.above >= WHOLE_STRIP_SHARE * self.n)


@dataclass
class Comparison:
    """The two readings, paired and compared. ΔE₀₀ throughout."""
    a: Reading
    b: Reading
    paired_by: str                # "id" | "device"
    device_checked: bool          # False when a file carries no device values
    #: patches left out because their device value repeats in the chart
    #: (pairing by device values only)
    left_out: int = 0
    patches: "list[PatchDiff]" = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.patches)

    def _des(self) -> np.ndarray:
        return np.array([p.de for p in self.patches], dtype=float)

    @property
    def mean(self) -> float:
        return float(self._des().mean())

    @property
    def median(self) -> float:
        return float(np.median(self._des()))

    @property
    def p95(self) -> float:
        return float(np.percentile(self._des(), 95))

    @property
    def worst(self) -> float:
        return float(self._des().max())

    def above(self, tol: float) -> "list[PatchDiff]":
        """Patches whose ΔE₀₀ is ABOVE *tol* (equal is within it), worst first."""
        return sorted((p for p in self.patches if p.de > tol + 1e-9),
                      key=lambda p: -p.de)

    def worst_patches(self, k: int = WORST_SHOWN) -> "list[PatchDiff]":
        return sorted(self.patches, key=lambda p: -p.de)[:k]

    def strips(self, tol: float) -> "list[StripSummary]":
        """Per printed strip, worst average first; empty when the locations
        name no strips."""
        groups: "dict[str, list[float]]" = {}
        order: "list[str]" = []
        for p in self.patches:
            if p.strip is None:
                continue
            if p.strip not in groups:
                groups[p.strip] = []
                order.append(p.strip)
            groups[p.strip].append(p.de)
        if len(groups) < 2:
            return []
        out = [StripSummary(s, len(d), float(np.mean(d)), float(max(d)),
                            sum(1 for x in d if x > tol + 1e-9))
               for s, d in ((s, groups[s]) for s in order)]
        return sorted(out, key=lambda s: -s.mean)


# ---------------------------------------------------------------------------
# Reading the second file
# ---------------------------------------------------------------------------

def _unusable(kind: str, error: str = "") -> ReadingsNotComparable:
    from workflow.measurement_messages import (M_READINGS_UNUSABLE,
                                               readings_unusable_reason)
    return ReadingsNotComparable(M_READINGS_UNUSABLE,
                                 readings_unusable_reason(kind, error))


def _lab_of(xyz: np.ndarray) -> np.ndarray:
    from workflow.strip_read_twice import xyz_to_lab
    return np.array([xyz_to_lab(tuple(v)) for v in xyz], dtype=float)


def reading_from_ti3(path: Path) -> Reading:
    """A measurement (.ti3) or CGATS text file with XYZ or L*a*b* values."""
    from workflow.ti3_analysis import Ti3ParseError, parse_ti3
    try:
        data = parse_ti3(Path(path))
    except (OSError, ValueError, IndexError) as exc:
        # ValueError / IndexError: a value that is not a number, a short
        # row. They used to escape and leave the window without an answer.
        raise _unusable("unreadable", str(exc)) from exc
    except Ti3ParseError as exc:
        text = str(exc)
        if "XYZ" in text or "Lab" in text:
            raise _unusable("no-colour") from exc
        raise _unusable("unreadable", text) from exc
    n = data.n_patches
    if n == 0:
        raise _unusable("no-colour")
    ids = [str(s).strip('"') for s in (data.sample_ids or [])] \
        or [str(i + 1) for i in range(n)]
    locs = [str(s).strip('"') for s in (data.sample_locs or [])] \
        or [""] * n
    kw = data.keywords
    return Reading(Path(path), ids, locs,
                   np.asarray(data.rgb, dtype=float).reshape(-1, 3)
                   if len(data.rgb) else np.empty((0, 3)),
                   _lab_of(np.asarray(data.xyz, dtype=float)),
                   condition=kw.get("MEASUREMENT_CONDITION", ""),
                   turned=_TURNED_KEYWORD in kw,
                   instrument=(kw.get("CHROMIQ_I1P_INSTRUMENT")
                               or kw.get("TARGET_INSTRUMENT") or ""),
                   measured_on=_date_of(kw.get("CHROMIQ_MEASURED")
                                        or kw.get("CREATED") or ""))


def display_date(text: str) -> str:
    """A date as a file writes it, shown the one way this window shows dates:
    ``2026-11-11 09:30`` when it has a time, ``2026-11-11`` when it has only
    a day, and as the file has it when it does not read as a date.

    Read by `core.cgats_date` (chartread's "Wed Nov 11 09:30:00 2026" in any
    shipped language, ISO dates, i1Profiler's "July 19, 2026"); the same
    year-month-day form as the app's other dates (verification dates,
    `measurement_target.pretty_verification_date`), which reads the same in
    every language (4.3.32 review: "Measured on" showed chartread's raw text
    beside readings shown as 2026-11-11)."""
    from core.cgats_date import parse_created_date, parse_created_datetime
    raw = str(text or "").strip().strip('"').strip()
    if not raw:
        return ""
    when = parse_created_datetime(raw)
    if when is not None:
        return when.strftime("%Y-%m-%d %H:%M")
    day = parse_created_date(raw)
    if day is not None:
        return day.strftime("%Y-%m-%d")
    return raw


def _date_of(text: str) -> str:
    """*text* as :func:`display_date` shows it."""
    return display_date(text)


def _argyll_bin() -> str:
    """The ArgyllCMS folder of the settings, as every import door uses it."""
    from core.platform_paths import default_argyll_bin_dir
    try:
        from core.settings import AppSettings
        return str(AppSettings().get("argyll_bin_path", "")
                   or default_argyll_bin_dir())
    except Exception:          # noqa: BLE001 — the default is still a folder
        return default_argyll_bin_dir()


def _reading_from_cgats_text(path: Path, argyll_bin: "str | None") -> Reading:
    """A CGATS text file that is not an ArgyllCMS measurement (an i1Profiler
    CGATS export, say), read EXACTLY as the import reads it
    (`reference_convert.convert_i1profiler_measurement`: txt2ti3, then the
    CIE scale repaired and XYZ added from a spectral-only export), in a
    temporary folder that is removed again. Read directly, i1Profiler's XYZ
    on the 0..1 scale came out a hundredfold dark (a real export against its
    own import: average ΔE00 45 instead of 0) and a spectral export was
    called a file without colours (4.3.32 review). Decimal commas are read
    by that converter too, from a temporary copy with points."""
    from workflow.reference_convert import (ReferenceConvertError,
                                            convert_i1profiler_measurement)
    from core.text_io import read_text
    try:
        read_text(path, lenient=True)     # unreadable: said in words here
    except OSError as exc:
        raise _unusable("unreadable", str(exc)) from exc
    with tempfile.TemporaryDirectory(prefix="chromiq-compare-") as tmp:
        try:
            # Decimal commas are read by the import's own converter
            # (`reference_convert.decimal_point_source`), one rule for both.
            out = convert_i1profiler_measurement(
                path, argyll_bin or _argyll_bin(), Path(tmp) / "out")
        except ReferenceConvertError as exc:
            raise _unusable("unreadable", str(exc)) from exc
        except OSError as exc:
            raise _unusable("unreadable", str(exc)) from exc
        r = reading_from_ti3(out)
    r.path = path
    return r


def _is_argyll_table(path: Path) -> bool:
    """An ArgyllCMS table announces itself on its first line (CTI3 …)."""
    from workflow.measurement_import import _cgats_table_kind
    return _cgats_table_kind(path).startswith("CTI")


#: `i1profiler_turned.TURNED_KEYWORD`, here to keep this module light.
_TURNED_KEYWORD = "CHROMIQ_PAIRED_BY_TURNED_ORDER"


def load_reading(path: Path, prefer_condition: str = "",
                 argyll_bin: "str | None" = None) -> Reading:
    """The reading in *path*. An i1Profiler ``.mxf``/``.cxf`` is converted in
    a temporary folder that is removed again; it takes *prefer_condition*
    (the first reading's condition) when the file holds it, else the
    condition the import window would offer first. A CGATS text file that
    is not an ArgyllCMS table is converted the way the import converts it
    (*argyll_bin*, default: the settings' ArgyllCMS folder)."""
    from workflow.reference_convert import is_cxf
    path = Path(path)
    if not path.is_file():
        raise _unusable("unreadable", tr("the file does not exist"))
    if not is_cxf(path):
        if _is_argyll_table(path):
            return reading_from_ti3(path)
        return _reading_from_cgats_text(path, argyll_bin)
    from workflow.reference_convert import (ReferenceConvertError,
                                            cxf_conditions,
                                            cxf_measurement_to_ti3)
    try:
        conds = cxf_conditions(path)
        cond = (prefer_condition if prefer_condition in conds.available
                else conds.preselect) or None
        with tempfile.TemporaryDirectory(prefix="chromiq-compare-") as tmp:
            out = cxf_measurement_to_ti3(path, Path(tmp) / "reading.ti3", cond)
            r = reading_from_ti3(out)
    except ReferenceConvertError as exc:
        raise _unusable("unreadable", str(exc)) from exc
    r.path = path
    r.converted_from_cxf = True
    r.condition = cond or r.condition
    return r


# ---------------------------------------------------------------------------
# Pairing: the same chart, or a refusal
# ---------------------------------------------------------------------------

def _mismatch(reason: str) -> ReadingsNotComparable:
    from workflow.measurement_messages import M_READINGS_NOT_SAME_CHART
    return ReadingsNotComparable(M_READINGS_NOT_SAME_CHART, reason)


def _fmt_device(v) -> str:
    return " ".join(f"{x:g}" for x in np.round(np.asarray(v, float), 2))


#: When pairing by device values, patches whose device value appears more
#: than once in the chart (a second white, a repeated black) cannot be told
#: apart, so they are left out of the comparison and said to be. More than
#: this share of the chart left out, and the files are not paired at all.
MAX_LEFT_OUT_SHARE = 0.10


def _pair_by_device(da: np.ndarray, db: np.ndarray, tol: float
                    ) -> "tuple[list[tuple[int, int]] | None, str, int]":
    """(pairs, "", left_out) by device values, or (None, why, 0).

    A patch is paired when its device value names exactly one patch in each
    file (every channel within *tol*). A value repeated in the chart is left
    out when both files hold it equally often (ChromIQ cannot tell those
    copies apart); *why* is ``"differ"`` when some value of one file is not
    in the other as often, ``"repeats"`` when more than
    :data:`MAX_LEFT_OUT_SHARE` of the chart would be left out."""
    n = len(da)
    pairs: "list[tuple[int, int]]" = []
    left_out = 0
    for i in range(n):
        in_b = np.flatnonzero(np.all(np.abs(db - da[i]) <= tol, axis=1))
        in_a = np.flatnonzero(np.all(np.abs(da - da[i]) <= tol, axis=1))
        if len(in_b) != len(in_a):
            return None, "differ", 0
        if len(in_b) == 1:
            pairs.append((i, int(in_b[0])))
        else:
            left_out += 1
    if len({ib for _ia, ib in pairs}) != len(pairs):
        return None, "differ", 0
    if left_out > MAX_LEFT_OUT_SHARE * n or not pairs:
        return None, "repeats", 0
    return pairs, "", left_out


def pair_readings(a: Reading, b: Reading
                  ) -> "tuple[list[tuple[int, int]], str, bool, int]":
    """(pairs, paired_by, device_checked, left_out), or raise
    ReadingsNotComparable.

    Checked in the order of `colverify_runner.reference_mismatch`: patch
    count, patch numbers, device values. Where the patch numbers or the
    device values of same-numbered patches do not fit, the two are paired by
    their device values instead when that is unambiguous."""
    from workflow.measurement_messages import (readings_count_reason,
                                               readings_device_reason,
                                               readings_ids_reason)
    from workflow.measurement_report import (PATCH_IDENTITY_TOL,
                                             paired_device_0_100)
    n_a, n_b = len(a.ids), len(b.ids)
    if n_a != n_b:
        raise _mismatch(readings_count_reason(n_a, n_b))
    have_dev = len(a.device) == n_a and len(b.device) == n_b and n_a > 0
    da = db = None
    if have_dev:
        da, db = paired_device_0_100(a.device, b.device)

    where = {sid: i for i, sid in enumerate(b.ids)}
    missing = [sid for sid in a.ids if sid not in where]
    if not missing and len(where) == n_b:
        pairs = [(ia, where[sid]) for ia, sid in enumerate(a.ids)]
        if not have_dev:
            if a.turned != b.turned:
                # Only the numbers could pair them, and they do not mean the
                # same patches (4.3.32 review).
                from workflow.measurement_messages import \
                    readings_turned_no_device_reason
                raise _mismatch(readings_turned_no_device_reason())
            return pairs, "id", False, 0
        diffs = np.array([np.abs(da[ia] - db[ib]).max() for ia, ib in pairs])
        bad = np.flatnonzero(diffs > PATCH_IDENTITY_TOL)
        if not len(bad):
            return pairs, "id", True, 0
        by_dev, why, left = _pair_by_device(da, db, PATCH_IDENTITY_TOL)
        if by_dev is not None:
            log.info("compare readings: patch numbers do not pair (%d of %d "
                     "device values differ); paired by device values",
                     len(bad), n_a)
            return by_dev, "device", True, left
        k = int(bad[0])
        ia, ib = pairs[k]
        raise _mismatch(readings_device_reason(
            int(len(bad)), n_a, a.ids[ia], _fmt_device(a.device[ia]),
            _fmt_device(b.device[ib]), why))
    if have_dev:
        by_dev, _why, left = _pair_by_device(da, db, PATCH_IDENTITY_TOL)
        if by_dev is not None:
            log.info("compare readings: %d patch numbers of the measurement "
                     "are not in the second reading; paired by device values",
                     len(missing))
            return by_dev, "device", True, left
    shown = missing[:5] + (["…"] if len(missing) > 5 else [])
    raise _mismatch(readings_ids_reason(shown or ["?"]))


# ---------------------------------------------------------------------------
# The comparison
# ---------------------------------------------------------------------------

def _strip_and_place(labels, loc: str) -> "tuple[str | None, int | None]":
    if labels is None or not loc:
        return None, None
    try:
        sp = labels.split(loc)
    except Exception:          # noqa: BLE001 — labels never block a report
        return None, None
    if sp is None:
        return None, None
    try:
        return labels.strip(sp[0]), sp[1] + 1
    except Exception:          # noqa: BLE001
        return None, None


def compare(a: Reading, b: Reading) -> Comparison:
    """Pair *a* and *b* (or raise ReadingsNotComparable) and compare them."""
    from workflow.ti3_analysis import ciede2000
    pairs, how, checked, left_out = pair_readings(a, b)
    labels = None
    try:
        from workflow.layout_engine.labels import labels_for_measurement
        labels = labels_for_measurement(a.path)
    except Exception:          # noqa: BLE001 — without labels, no strips
        labels = None
    out = Comparison(a, b, how, checked, left_out=left_out)
    for ia, ib in pairs:
        la, lb = tuple(float(x) for x in a.lab[ia]), tuple(
            float(x) for x in b.lab[ib])
        de = ciede2000(la, lb)
        if not math.isfinite(de):
            de = 0.0
        strip, place = _strip_and_place(labels, a.locs[ia])
        out.patches.append(PatchDiff(a.ids[ia], a.locs[ia], strip, place,
                                     la, lb, float(de)))
    log.info("compare readings: %s against %s, %d patches paired by %s; "
             "mean %.2f, median %.2f, 95th percentile %.2f, max %.2f",
             a.path.name, b.path.name, out.n, how, out.mean, out.median,
             out.p95, out.worst)
    return out


# ---------------------------------------------------------------------------
# Several readings (Basti, 2026-11-11: "several readings, not only two")
# ---------------------------------------------------------------------------
#
# WITH THREE OR MORE READINGS THERE IS SOMETHING TO JUDGE BY. Two readings
# show a difference and cannot say which of them is off. With more, each
# patch has a CENTRE that a single bad reading hardly moves, and every
# reading is measured against it.
#
# THE CENTRE IS THE PER-PATCH MEDIAN OF L*, a* AND b* SEPARATELY, not the
# mean: one reading that is 5 ΔE₀₀ off pulls a mean of four by a quarter of
# that, which makes the good readings look off too and the bad one look
# better than it is. The median of each coordinate stays with the majority.
# With THREE readings it is, per coordinate, the middle value: when two of
# them agree it lies at or between those two, so the third shows its whole
# difference and the two show at most their own small scatter. With an EVEN
# number it is the mean of the two middle values per coordinate, which still
# lies inside the majority when only one reading is off (with four: the
# middle two of the three that agree). Split evenly (two against two) it
# lies between the groups, every reading is about half the gap away, and no
# reading is named: that is the honest answer then. (A medoid, the reading
# nearest to all others, was the other candidate: it picks one reading as
# "right", which is exactly the claim this tool must not make.)
#
# THE SPREAD of a patch is the LARGEST ΔE₀₀ BETWEEN ANY TWO READINGS of it:
# with two readings it is their difference, the number the two-reading view
# shows, so both views speak of the same quantity. It grows a little with
# the number of readings (more readings, more chance of a wider pair); that
# is said where it is shown.
#
# A READING STANDS APART on a patch whose spread is above the tolerance when
# all the OTHER readings agree with each other within the tolerance and it
# is the only reading of which that is true. Otherwise "the readings
# disagree with each other". That is strong evidence, not proof: two
# readings that share an error (the same strip slipped twice) agree with
# each other and make the good one stand apart.

#: How many other readings can be compared with the measurement at once
#: (ten readings in all).
MAX_OTHER_READINGS = 9

# A reading "differs overall" when its MEDIAN distance from the centre is
# above the tolerance: more than half of its patches are off, which a
# misread strip or a few bad patches never cause, and another instrument,
# another measurement condition, another print or a drifting instrument do
# (`SeveralComparison.verdict`).


@dataclass
class ReadingStats:
    mean: float
    median: float
    p95: float
    worst: float


@dataclass
class Verdict:
    """What one reading looks like beside the others, at one tolerance.

    *kind*: ``"agrees"``, ``"patches"`` (*count* patches above the
    tolerance), ``"strip"`` (nearly the whole of *strips*, and *count* above
    in all) or ``"overall"``."""
    kind: str
    count: int = 0
    strips: "list[str]" = field(default_factory=list)


@dataclass
class StripRow:
    label: str
    n: int
    means: np.ndarray             # (R,) average distance from the centre
    above: np.ndarray             # (R,) patches above the tolerance

    def off(self, k: int) -> bool:
        """Nearly the whole strip of reading *k* is above the tolerance."""
        return (self.n >= WHOLE_STRIP_MIN_PATCHES
                and self.above[k] >= WHOLE_STRIP_SHARE * self.n)


def _norm_instrument(name: str) -> str:
    """An instrument name for comparing: "X-Rite i1 Pro 2" (chartread) and
    "i1Pro 2" (i1Profiler) are the same instrument."""
    t = re.sub(r"[^a-z0-9]", "", str(name).lower())
    for brand in ("xrite", "datacolor", "konicaminolta"):
        if t.startswith(brand):
            t = t[len(brand):]
    return t


@dataclass
class SeveralComparison:
    """The measurement and two or more other readings, paired and compared
    with each patch's centre. Readings are numbered from 0 here (0 is the
    measurement); the window numbers them from 1."""
    readings: "list[Reading]"
    paired_by: "list[str]"        # per OTHER reading: "id" | "device"
    device_checked: bool          # False when some pair was not checked
    left_out: int                 # measurement patches not in every reading
    sids: "list[str]"
    locs: "list[str]"
    strips_of: "list[str | None]"
    positions: "list[int | None]"
    lab: np.ndarray               # (R, N, 3)
    centre: np.ndarray            # (N, 3) per-patch median
    dev: np.ndarray               # (R, N) ΔE₀₀ to the centre
    pair: np.ndarray              # (R, R, N) ΔE₀₀ between two readings
    spread: np.ndarray            # (N,) largest pairwise ΔE₀₀

    @property
    def n(self) -> int:
        return int(self.dev.shape[1])

    @property
    def r(self) -> int:
        return int(self.dev.shape[0])

    def stats(self, k: int) -> ReadingStats:
        d = self.dev[k]
        return ReadingStats(float(d.mean()), float(np.median(d)),
                            float(np.percentile(d, 95)), float(d.max()))

    def above(self, k: int, tol: float) -> int:
        """Patches of reading *k* farther than *tol* from the centre."""
        return int(np.count_nonzero(self.dev[k] > tol + 1e-9))

    def repeatability(self) -> "tuple[float, float]":
        """(median, 95th percentile) of the per-patch spread."""
        return (float(np.median(self.spread)),
                float(np.percentile(self.spread, 95)))

    def spread_above(self, tol: float) -> np.ndarray:
        """Patch indexes whose spread is above *tol*, largest first."""
        idx = np.flatnonzero(self.spread > tol + 1e-9)
        return idx[np.argsort(-self.spread[idx], kind="stable")]

    def worst(self, k: int = WORST_SHOWN) -> np.ndarray:
        return np.argsort(-self.spread, kind="stable")[:k]

    def stands_apart(self, tol: float) -> np.ndarray:
        """(N,) the reading that stands apart on each patch, or -1.

        Only on patches whose spread is above *tol*: reading k stands apart
        when every pair of the OTHER readings is within *tol* and k is the
        only reading of which that holds."""
        r, n = self.r, self.n
        agree = np.zeros((r, n), dtype=bool)
        for k in range(r):
            keep = [i for i in range(r) if i != k]
            sub = self.pair[np.ix_(keep, keep)]
            agree[k] = sub.max(axis=(0, 1)) <= tol + 1e-9
        out = np.full(n, -1, dtype=int)
        one = (agree.sum(axis=0) == 1) & (self.spread > tol + 1e-9)
        out[one] = np.argmax(agree[:, one], axis=0)
        return out

    def strips(self, tol: float) -> "list[StripRow]":
        """Per printed strip (in chart order); empty when the locations name
        no strips."""
        groups: "dict[str, list[int]]" = {}
        for i, s in enumerate(self.strips_of):
            if s is not None:
                groups.setdefault(s, []).append(i)
        if len(groups) < 2:
            return []
        out = []
        for s, idx in groups.items():
            d = self.dev[:, idx]
            out.append(StripRow(s, len(idx), d.mean(axis=1),
                                np.count_nonzero(d > tol + 1e-9, axis=1)))
        return out

    def verdict(self, k: int, tol: float,
                strips: "list[StripRow] | None" = None) -> Verdict:
        count = self.above(k, tol)
        if count == 0:
            return Verdict("agrees")
        if float(np.median(self.dev[k])) > tol + 1e-9:
            return Verdict("overall", count)
        strips = self.strips(tol) if strips is None else strips
        off = [s.label for s in strips if s.off(k)]
        if off:
            return Verdict("strip", count, off)
        return Verdict("patches", count)

    def typical(self) -> np.ndarray:
        """(R, R) the TYPICAL difference between two readings: the median
        ΔE₀₀ between them over all compared patches."""
        return np.median(self.pair, axis=2)

    def groups(self, tol: float) -> "list[list[int]]":
        """The readings split into groups that agree, or [] when they do not
        split cleanly (4.3.32 review: two against two read as four readings
        that each "differ from the others overall").

        Two readings AGREE when their typical difference is within *tol*.
        The groups are the sets of readings joined by agreement, and they are
        named only when the split is CLEAN: inside every group each reading
        agrees with each other one (a chain where 1 agrees with 2 and 2 with
        3 but 1 not with 3 is no group), and at least two groups hold two
        readings or more. A single reading on its own is not a group: one
        reading apart from the rest is what "stands apart" already says.
        Returned in reading order, each group sorted; readings that agree
        with nobody come back as groups of one. Nothing here says which
        group is right."""
        close = self.typical() <= tol + 1e-9
        r = self.r
        seen: "set[int]" = set()
        comps: "list[list[int]]" = []
        for k in range(r):
            if k in seen:
                continue
            todo, comp = [k], []
            seen.add(k)
            while todo:
                i = todo.pop()
                comp.append(i)
                for j in range(r):
                    if j not in seen and close[i, j]:
                        seen.add(j)
                        todo.append(j)
            comps.append(sorted(comp))
        for comp in comps:
            if not all(close[i, j] for i in comp for j in comp):
                return []
        if sum(1 for comp in comps if len(comp) >= 2) < 2:
            return []
        return sorted(comps, key=lambda g: g[0])

    def mixed(self) -> "tuple[dict[str, list[int]], dict[str, list[int]]]":
        return mixed_ways(self.readings)


def mixed_ways(readings: "list[Reading]"
               ) -> "tuple[dict[str, list[int]], dict[str, list[int]]]":
    """({condition: reading indexes}, {instrument: reading indexes}), each
    only when the files name more than one. A reading whose file does not
    say is left out of both (many a .ti3 names no measurement condition)."""
    conds: "dict[str, list[int]]" = {}
    insts: "dict[str, list[int]]" = {}
    shown: "dict[str, str]" = {}
    for k, rd in enumerate(readings):
        if rd.condition:
            conds.setdefault(rd.condition.upper(), []).append(k)
        key = _norm_instrument(rd.instrument)
        if key:
            shown.setdefault(key, rd.instrument)
            insts.setdefault(key, []).append(k)
    return ((conds if len(conds) > 1 else {}),
            ({shown[key]: v for key, v in insts.items()}
             if len(insts) > 1 else {}))


def _same_reading_as(a: Reading, b: Reading, m: "dict[int, int]",
                     paired) -> "Reading | None":
    """The reading among *a* and those already *paired* that *b* repeats
    exactly (the same L*a*b* on every patch they share), or None."""
    ia = np.asarray(sorted(m), dtype=int)
    if not len(ia):
        return None
    lb = b.lab[np.asarray([m[i] for i in ia], dtype=int)]
    if np.array_equal(lb, a.lab[ia]):
        return a
    for c, mc, _h, _k in paired:
        both = [i for i in ia if i in mc]
        if len(both) != len(ia):
            continue
        lc = c.lab[np.asarray([mc[i] for i in ia], dtype=int)]
        if np.array_equal(lb, lc):
            return c
    return None


def compare_several(a: Reading, others: "list[Reading]"
                    ) -> "tuple[SeveralComparison | None, list[tuple[Reading, ReadingsNotComparable]]]":
    """Pair every reading of *others* with *a*, refuse the ones that are not
    the same chart (each on its own: a refused reading never stops the
    rest), and compare the rest with each patch's centre.

    Returns (comparison, refused). The comparison is None when fewer than
    two other readings pair: the two-reading view (`compare`) is the one
    for that."""
    from workflow.profile_engine.metrics import delta_e_2000
    paired: "list[tuple[Reading, dict[int, int], str, bool]]" = []
    refused: "list[tuple[Reading, ReadingsNotComparable]]" = []
    for b in others:
        try:
            pairs, how, checked, _left = pair_readings(a, b)
        except ReadingsNotComparable as exc:
            refused.append((b, exc))
            continue
        m = dict(pairs)
        twin = _same_reading_as(a, b, m, paired)
        if twin is not None:
            # 4.3.32 review: one reading counted twice outvotes the others
            # (the same file added twice, or the measurement itself again).
            from workflow.measurement_messages import (
                M_READINGS_UNUSABLE, readings_duplicate_reason)
            refused.append((b, ReadingsNotComparable(
                M_READINGS_UNUSABLE, readings_duplicate_reason(
                    twin.path.name))))
            continue
        paired.append((b, m, how, checked))
    if len(paired) < 2:
        return None, refused
    common = [i for i in range(len(a.ids))
              if all(i in m for _b, m, _h, _c in paired)]
    if not common:
        return None, refused
    labels = None
    try:
        from workflow.layout_engine.labels import labels_for_measurement
        labels = labels_for_measurement(a.path)
    except Exception:          # noqa: BLE001 — without labels, no strips
        labels = None
    idx = np.asarray(common, dtype=int)
    lab = np.stack([a.lab[idx]] + [
        b.lab[np.asarray([m[i] for i in common], dtype=int)]
        for b, m, _h, _c in paired])
    r, n = lab.shape[0], lab.shape[1]
    centre = np.median(lab, axis=0)
    dev = np.stack([delta_e_2000(lab[k], centre) for k in range(r)])
    pair = np.zeros((r, r, n))
    for i in range(r):
        for j in range(i + 1, r):
            pair[i, j] = pair[j, i] = delta_e_2000(lab[i], lab[j])
    dev = np.where(np.isfinite(dev), dev, 0.0)
    pair = np.where(np.isfinite(pair), pair, 0.0)
    spread = pair.max(axis=(0, 1))
    sp = [_strip_and_place(labels, a.locs[i]) for i in common]
    out = SeveralComparison(
        readings=[a] + [b for b, _m, _h, _c in paired],
        paired_by=[h for _b, _m, h, _c in paired],
        device_checked=all(c for _b, _m, _h, c in paired),
        left_out=len(a.ids) - len(common),
        sids=[a.ids[i] for i in common], locs=[a.locs[i] for i in common],
        strips_of=[s for s, _p in sp], positions=[p for _s, p in sp],
        lab=lab, centre=centre, dev=dev, pair=pair, spread=spread)
    med, p95 = out.repeatability()
    log.info("compare readings: %s against %d other readings, %d patches; "
             "spread median %.2f, 95th percentile %.2f; %d refused",
             a.path.name, r - 1, n, med, p95, len(refused))
    return out, refused
