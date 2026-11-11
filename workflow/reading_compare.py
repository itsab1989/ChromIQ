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
    return Reading(Path(path), ids, locs,
                   np.asarray(data.rgb, dtype=float).reshape(-1, 3)
                   if len(data.rgb) else np.empty((0, 3)),
                   _lab_of(np.asarray(data.xyz, dtype=float)),
                   condition=data.keywords.get("MEASUREMENT_CONDITION", ""))


#: One number written with a decimal comma (i1Profiler on a decimal-comma
#: system writes its CGATS text so): digits, one comma, digits.
_COMMA_NUMBER = re.compile(r"^[+-]?\d+,\d+(?:[eE][+-]?\d+)?$")
_POINT_NUMBER = re.compile(r"^[+-]?\d*\.\d+(?:[eE][+-]?\d+)?$")


def _decimal_points(text: str) -> "str | None":
    """*text* with the decimal commas of its data table made points, or None
    when it has none. Only when the table is consistent: some value is
    written with a comma and none with a point (a comma inside a quoted name
    is left alone, as is any token that is not one plain number)."""
    lines = text.splitlines()
    try:
        d0 = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA")
        d1 = next(i for i in range(d0, len(lines))
                  if lines[i].strip() == "END_DATA")
    except StopIteration:
        return None
    toks = [t for ln in lines[d0 + 1:d1] for t in ln.split()]
    if not any(_COMMA_NUMBER.match(t) for t in toks) \
            or any(_POINT_NUMBER.match(t) for t in toks):
        return None
    out = lines[:d0 + 1]
    for ln in lines[d0 + 1:d1]:
        out.append("\t".join(t.replace(",", ".") if _COMMA_NUMBER.match(t)
                             else t for t in ln.split()))
    return "\n".join(out + lines[d1:]) + "\n"


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
    called a file without colours (4.3.32 review). Decimal commas are made
    points first, in the temporary copy only."""
    from workflow.reference_convert import (ReferenceConvertError,
                                            convert_i1profiler_measurement)
    from core.text_io import read_text
    try:
        text = read_text(path, lenient=True)
    except OSError as exc:
        raise _unusable("unreadable", str(exc)) from exc
    with tempfile.TemporaryDirectory(prefix="chromiq-compare-") as tmp:
        src = path
        fixed = _decimal_points(text)
        if fixed is not None:
            src = Path(tmp) / "src" / path.name
            src.parent.mkdir()
            src.write_text(fixed, encoding="utf-8")
            log.info("compare readings: %s writes decimal commas; read as "
                     "decimal points", path.name)
        try:
            out = convert_i1profiler_measurement(
                src, argyll_bin or _argyll_bin(), Path(tmp) / "out")
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
