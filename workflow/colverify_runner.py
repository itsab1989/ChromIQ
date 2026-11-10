"""Build a reference .ti3 from expected CIE values and run Argyll ``colverify``.

Powers the Tools → "Verify against reference" utility. The user prints a chart
through a candidate profile, measures it (``chartread`` → measured ``.ti3``), and
wants to know how far each patch lands from a set of *expected* CIE values
supplied by someone else (e.g. a known-good profile-evaluation target). Argyll's
``colverify`` reports per-patch and summary ΔE between two CGATS files, matched
by ``SAMPLE_ID`` — no ``colprof`` step required.

The expected values rarely arrive as a ready ``.ti3``; they're a plain table of
Lab (or XYZ) triples in patch order. This module turns that table into a
``colverify``-ready reference ``.ti3`` whose SAMPLE_IDs line up with the measured
file:

  * SAMPLE_ID is written ``1..N`` in table order. ``chartread`` numbers patches
    ``1..N`` in the chart's patch order, so row *i* of the table == SAMPLE_ID *i*
    == the *i*-th patch measured. (Argyll's CGATS reader knows ``SAMPLE_ID`` is a
    string field and promotes the integer literals, satisfying ``colverify``'s
    string-type check — cgats.c ~L702.)
  * If the originating chart (``.ti1``/``.ti2``) is supplied, its device RGB is
    copied in (``COLOR_REP "RGB_LAB"``) and its patch count is cross-checked
    against the table — the robustness guarantee that the reference can't
    silently misalign with the chart it came from.

``colverify`` reads ``LAB_L``/``LAB_A``/``LAB_B`` directly (Argyll 3.5.0
colverify.c ~L559), so Lab tables need no conversion; XYZ tables are emitted as
``XYZ_X``/``XYZ_Y``/``XYZ_Z``. This module is Qt-free and unit-testable; the
dialog lives in ui/dialogs/tools_dialogs.py.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

from core.cgats_date import created_stamp
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.logger import get_logger

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)

# colverify.c ~L1442:  "  Total errors:     peak = %f, avg = %f"
# (an optional " (CIEDE2000)" / " (CIE94)" suffix sits before the colon).
_SUMMARY_RE = re.compile(
    r"Total errors[^:]*:\s*peak\s*=\s*([\d.]+),\s*avg\s*=\s*([\d.]+)",
    re.IGNORECASE,
)
# Per-patch line (verbose ≥ 2): "<id>[ <loc>]: l a b <=> l a b  de <value>"
# colverify prints the id immediately followed by a colon ("%s%s%s:"), so the
# id is everything up to the first colon.
# When either file carries SAMPLE_LOC the location follows the id after a
# space ("2 AF9: …", every chartread measurement used as the reference,
# 4.3.30); the id is still the first word.
_PATCH_RE = re.compile(r"^(\S+?)(?:\s+\S+?)?:.*?\bde\s+([\d.]+)\s*$")
# Full per-patch line, capturing both Lab triples (always Lab — colverify prints
# its internal v[] which is Lab regardless of the file's PCS). Lets us split each
# patch's error into lightness (ΔL*) vs colour (Δa*b*) without a second tool.
# colverify.c ~L1303:  printf("%s%s%s: %f %f %f <=> %f %f %f  de %f\n", …)
_PATCH_FULL_RE = re.compile(
    r"^(\S+?)(?:\s+\S+?)?:\s*"
    r"(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*<=>\s*"
    r"(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+de\s+([\d.]+)\s*$"
)
# "  Worst 10% errors (CIEDE2000): peak = …, avg = …"  (colverify.c ~L1443)
_WORST10_RE = re.compile(
    r"Worst\s*10%\s*errors[^:]*:\s*peak\s*=\s*([\d.]+),\s*avg\s*=\s*([\d.]+)",
    re.IGNORECASE,
)
# "  Best  90% errors (CIEDE2000): peak = …, avg = …"  (colverify.c ~L1444)
_BEST90_RE = re.compile(
    r"Best\s*90%\s*errors[^:]*:\s*peak\s*=\s*([\d.]+),\s*avg\s*=\s*([\d.]+)",
    re.IGNORECASE,
)
# "  avg err L* %f, a* %f, b* %f"  (colverify.c ~L1446) — mean signed component error.
_COMP_RE = re.compile(
    r"avg\s*err\s*L\*\s*(-?[\d.]+),\s*a\*\s*(-?[\d.]+),\s*b\*\s*(-?[\d.]+)",
    re.IGNORECASE,
)
# "No of test patches in gamut = 42/50"  (colverify.c ~L1027, only with -L + -v)
_GAMUT_RE = re.compile(r"patches in gamut\s*=\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)


def _fmt(v: float) -> str:
    return f"{v:.4f}"


# ---------------------------------------------------------------------------
# Reference table parsing
# ---------------------------------------------------------------------------

def parse_reference_values(text: str) -> list[tuple[float, float, float]]:
    """Parse a pasted/loaded table of CIE triples into ``(c0, c1, c2)`` rows.

    One patch per line, in patch order. Blank lines and ``#`` comments are
    ignored. Each data line must contain at least three numeric tokens; the
    **last three** numbers on the line are taken as the triple, so an optional
    leading index or sample name (e.g. ``GS01  50 0 0`` or ``1, 100, 0, 0``) is
    tolerated. Commas and tabs count as separators.

    Raises ``ValueError`` (naming the offending line) if a non-blank line has
    fewer than three numbers, or if no rows are found.
    """
    rows: list[tuple[float, float, float]] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        nums: list[float] = []
        for tok in line.replace(",", " ").replace("\t", " ").split():
            try:
                nums.append(float(tok))
            except ValueError:
                continue
        if len(nums) < 3:
            raise ValueError(
                f"Line {lineno} doesn't have three numbers: {line!r}"
            )
        rows.append((nums[-3], nums[-2], nums[-1]))
    if not rows:
        raise ValueError("No reference values found — the table is empty.")
    return rows


# ---------------------------------------------------------------------------
# A reference FILE (.ti3 or any CGATS table), 4.3.30
# ---------------------------------------------------------------------------
# Until 4.3.30 "Load from file…" put every file into the paste box, so a
# measurement chosen as the reference failed with "Line 1 doesn't have three
# numbers: 'CTI3'". colverify reads a CGATS file itself, Lab, XYZ or spectral
# (spectral-only included, measured 2026-11-11), and pairs it with the
# measurement by SAMPLE_ID; it refuses unequal patch counts and unknown IDs
# with an ArgyllCMS error, and it accepts the same IDs on a DIFFERENT chart
# without a word. So the file goes to colverify as it is, after the checks
# below, which say in plain words what does not fit.

_TOKEN_RE = re.compile(r'"[^"]*"|\S+')
_PCS_SETS = (("LAB_L", "LAB_A", "LAB_B"), ("XYZ_X", "XYZ_Y", "XYZ_Z"))


def looks_like_cgats(text: str) -> bool:
    """Whether *text* is a CGATS table (a ``.ti3``, ``.ti2``, ``.cgats`` …)
    rather than a plain list of number triples."""
    return bool(re.search(r"^\s*BEGIN_DATA_FORMAT\s*$", text, re.M))


@dataclass
class CgatsTable:
    """The FIRST table of a CGATS file, as written (values as strings)."""
    fields: list[str]
    rows: list[list[str]]

    def column(self, name: str) -> "list[str] | None":
        if name not in self.fields:
            return None
        i = self.fields.index(name)
        return [r[i].strip('"') for r in self.rows]


def parse_cgats_table(text: str) -> CgatsTable:
    """The first table of CGATS *text*. Raises ``ValueError`` when there is no
    ``BEGIN_DATA_FORMAT``…``BEGIN_DATA``…``END_DATA`` table with rows."""
    lines = text.splitlines()
    try:
        f0 = next(i for i, ln in enumerate(lines)
                  if ln.strip() == "BEGIN_DATA_FORMAT")
        f1 = next(i for i in range(f0 + 1, len(lines))
                  if lines[i].strip() == "END_DATA_FORMAT")
        d0 = next(i for i in range(f1 + 1, len(lines))
                  if lines[i].strip() == "BEGIN_DATA")
        d1 = next(i for i in range(d0 + 1, len(lines))
                  if lines[i].strip() == "END_DATA")
    except StopIteration as exc:
        raise ValueError("no data table") from exc
    fields = " ".join(lines[f0 + 1:f1]).split()
    rows = []
    for ln in lines[d0 + 1:d1]:
        toks = _TOKEN_RE.findall(ln)
        if len(toks) >= len(fields) and fields:
            rows.append(toks[:len(fields)])
    if not fields or not rows:
        raise ValueError("no data table")
    return CgatsTable(fields, rows)


def read_cgats_table(path: Path) -> CgatsTable:
    from core.text_io import read_text
    return parse_cgats_table(read_text(path, lenient=True))


class ReferenceFileError(ValueError):
    """A file that cannot serve as the reference; ``reason`` is the
    translated {reason} of M-VERIFY-REFERENCE-UNUSABLE."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class ReferenceFile:
    """A CGATS file chosen as the reference."""
    path: Path
    table: CgatsTable

    @property
    def n_patches(self) -> int:
        return len(self.table.rows)

    @property
    def by_id(self) -> bool:
        """True when colverify can pair it by its own SAMPLE_IDs; False for
        a table without them, which is paired in file order instead (as the
        pasted values are)."""
        return "SAMPLE_ID" in self.table.fields


def _has_colour(fields: "list[str]") -> bool:
    return (any(all(f in fields for f in s) for s in _PCS_SETS)
            or sum(1 for f in fields if f.startswith("SPEC_")) >= 3)


def load_reference_file(path: Path) -> ReferenceFile:
    """Read *path* as a reference table, or raise :class:`ReferenceFileError`
    with the reason it cannot be one."""
    from workflow.measurement_messages import reference_unusable_reason
    try:
        table = read_cgats_table(path)
    except OSError as exc:
        raise ReferenceFileError(
            reference_unusable_reason("unreadable", str(exc))) from exc
    except ValueError as exc:
        raise ReferenceFileError(reference_unusable_reason("no-table")) from exc
    if not _has_colour(table.fields):
        raise ReferenceFileError(reference_unusable_reason("no-colour"))
    return ReferenceFile(Path(path), table)


def _device_fields(fields: "list[str]") -> "list[str]":
    from workflow.ti3_analysis import device_columns
    return device_columns(fields)


def _fmt_device(values) -> str:
    return " ".join(f"{v:g}" for v in values)


def reference_mismatch(ref: ReferenceFile, measured: Path,
                       chart: "Path | None" = None) -> "str | None":
    """Why *ref* does not hold the chart *measured* was read from, as the
    translated {reason} of M-VERIFY-REFERENCE-MISMATCH, or None when it fits.

    Pairing is colverify's own: by ``SAMPLE_ID`` when the reference has
    them, otherwise row by row. Checked in this order: the chosen chart
    definition's patch count, the measurement's patch count, every measured
    patch number present in the reference, and the device values of each
    pair, which may differ by ``PATCH_IDENTITY_TOL`` (the rule the Measurement
    Report and the import use). A file whose patch numbers fit but which
    carries no device values cannot be checked further and is accepted."""
    import numpy as np

    from workflow.measurement_messages import (reference_chart_reason,
                                               reference_count_reason,
                                               reference_device_reason,
                                               reference_ids_reason)
    from workflow.measurement_report import (PATCH_IDENTITY_TOL,
                                             paired_device_0_100)
    n_ref = ref.n_patches
    if chart is not None:
        try:
            n_chart = chart_patch_count(chart)
        except OSError:
            n_chart = 0
        if n_chart and n_chart != n_ref:
            return reference_chart_reason(n_ref, n_chart)
    try:
        meas = read_cgats_table(measured)
    except (OSError, ValueError):
        return None   # colverify says what is wrong with the measurement
    if len(meas.rows) != n_ref:
        return reference_count_reason(n_ref, len(meas.rows))

    meas_ids = meas.column("SAMPLE_ID") or [str(i + 1) for i in range(n_ref)]
    if ref.by_id:
        ref_ids = ref.table.column("SAMPLE_ID") or []
        where = {sid: i for i, sid in enumerate(ref_ids)}
        missing = [sid for sid in meas_ids if sid not in where]
        if missing:
            shown = missing[:5] + (["…"] if len(missing) > 5 else [])
            return reference_ids_reason(shown)
        pairs = [(where[sid], mi) for mi, sid in enumerate(meas_ids)]
    else:
        pairs = [(i, i) for i in range(n_ref)]

    dev = [f for f in _device_fields(ref.table.fields)
           if f in _device_fields(meas.fields)]
    if not dev:
        return None
    try:
        want = np.array([[float(ref.table.rows[ri][ref.table.fields.index(f)])
                          for f in dev] for ri, _mi in pairs])
        got = np.array([[float(meas.rows[mi][meas.fields.index(f)])
                         for f in dev] for _ri, mi in pairs])
    except ValueError:
        return None
    w, g = paired_device_0_100(want, got)
    diffs = np.abs(w - g).max(axis=1)
    bad = np.flatnonzero(diffs > PATCH_IDENTITY_TOL)
    if not len(bad):
        return None
    k = int(bad[0])
    return reference_device_reason(
        int(len(bad)), len(pairs), meas_ids[pairs[k][1]],
        _fmt_device(want[k]), _fmt_device(got[k]))


def write_reference_with_ids(ref: ReferenceFile, measured: Path,
                             out_path: Path) -> Path:
    """A copy of a reference table WITHOUT patch numbers, given the
    measurement's own ``SAMPLE_ID`` row by row, so colverify pairs the two in
    file order (the order the pasted values are paired in). Every other
    column, spectral ones included, is copied as written."""
    from core.text_io import read_text
    meas = read_cgats_table(measured)
    ids = meas.column("SAMPLE_ID") or [str(i + 1) for i in range(len(meas.rows))]
    text = read_text(ref.path, lenient=True)
    lines = text.splitlines()
    f0 = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA_FORMAT")
    # The header as written, then the first table only (the one colverify
    # reads), with SAMPLE_ID in front.
    head = [ln for ln in lines[:f0] if not ln.strip().startswith("NUMBER_OF_FIELDS")]
    fields = ["SAMPLE_ID", *ref.table.fields]
    data = [" ".join([sid, *row]) for sid, row in zip(ids, ref.table.rows)]
    out = [*head, f"NUMBER_OF_FIELDS {len(fields)}", "BEGIN_DATA_FORMAT",
           " ".join(fields), "END_DATA_FORMAT", "",
           f"NUMBER_OF_SETS {len(data)}", "BEGIN_DATA", *data, "END_DATA", ""]
    out_path.write_text("\n".join(out), encoding="utf-8")
    return out_path


def vrml_output_path(measured_ti3: Path) -> Path:
    """Where ``colverify -w`` writes its 3D plot for a given measured file.

    colverify names the visualisation after the *measured* (second) file with its
    extension swapped for ``.x3d.html`` (colverify.c ~L446 strips the extension;
    new_vrml appends ``vrml_ext()``). It lands in the working directory alongside
    sibling ``x3dom.css`` / ``x3dom.js`` the HTML references relatively.
    """
    return measured_ti3.parent / f"{measured_ti3.stem}.x3d.html"


def chart_patch_count(path: Path) -> int:
    """Patch count of a chart's **first** CGATS table (``.ti1``/``.ti2``).

    A ``.ti1`` carries three tables (patch list, density extremes, device
    combinations); only the first is the patch list, so this counts rows in the
    first ``BEGIN_DATA``…``END_DATA`` block. Used purely to cross-check that a
    pasted reference table has the same number of patches as the chart it came
    from. Returns 0 if no data block is found.
    """
    n = 0
    in_data = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = raw.strip()
        if s == "BEGIN_DATA":
            in_data, n = True, 0
        elif s == "END_DATA":
            return n
        elif in_data and s:
            n += 1
    return n


# ---------------------------------------------------------------------------
# Reference .ti3 emitter
# ---------------------------------------------------------------------------

def write_reference_ti3(
    out_path: Path,
    rows: list[tuple[float, float, float]],
    *,
    space: str = "LAB",
    rgb: list[tuple[float, float, float]] | None = None,
) -> Path:
    """Emit a ``colverify``-ready reference ``.ti3`` from expected CIE values.

    ``rows`` are the expected triples in patch order; ``space`` is ``"LAB"`` or
    ``"XYZ"``. If ``rgb`` is given (device values on the 0..100 scale, same order
    and length as ``rows``), it is written alongside so the file is a normal
    device+PCS ``.ti3`` and ``colverify -d`` works. SAMPLE_ID is ``1..N``.
    """
    space = space.upper()
    if space not in ("LAB", "XYZ"):
        raise ValueError(f"space must be 'LAB' or 'XYZ', got {space!r}")
    if rgb is not None and len(rgb) != len(rows):
        raise ValueError(
            f"RGB count ({len(rgb)}) doesn't match value count ({len(rows)})."
        )

    pcs_fields = ("LAB_L", "LAB_A", "LAB_B") if space == "LAB" else ("XYZ_X", "XYZ_Y", "XYZ_Z")
    if rgb is not None:
        fields = ("SAMPLE_ID", "RGB_R", "RGB_G", "RGB_B", *pcs_fields)
        color_rep = "RGB_LAB" if space == "LAB" else "RGB_XYZ"
    else:
        fields = ("SAMPLE_ID", *pcs_fields)
        color_rep = space

    head = [
        "CTI3   ",
        "",
        'DESCRIPTOR "Argyll Calibration Target chart information 3"',
        'ORIGINATOR "ChromIQ"',
        f'CREATED "{created_stamp()}"',   # English, as ArgyllCMS writes it
        'DEVICE_CLASS "OUTPUT"',
        f'COLOR_REP "{color_rep}"',
        "",
        f"NUMBER_OF_FIELDS {len(fields)}",
        "BEGIN_DATA_FORMAT",
        " ".join(fields),
        "END_DATA_FORMAT",
        "",
        f"NUMBER_OF_SETS {len(rows)}",
        "BEGIN_DATA",
    ]
    data: list[str] = []
    for i, triple in enumerate(rows, start=1):
        cells = [str(i)]
        if rgb is not None:
            cells += [_fmt(c) for c in rgb[i - 1]]
        cells += [_fmt(c) for c in triple]
        data.append(" ".join(cells))

    out_path.write_text("\n".join([*head, *data, "END_DATA", ""]), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# colverify runner
# ---------------------------------------------------------------------------

@dataclass
class PatchDelta:
    """One patch's reference vs measured Lab, with the error split into
    lightness (ΔL*) and colour (Δa*b* magnitude).

    A patch dominated by ΔL* (deep shadow on a paper whose black point sits
    higher than the reference's) is a *reachability* limit, not a colour-accuracy
    fault — the distinction the summary banner leans on. ``de`` is colverify's
    own reported value (whatever formula was selected); ``dl``/``dab`` are derived
    here purely for that lightness-vs-colour breakdown.
    """
    sample_id: str
    target: tuple[float, float, float]    # reference L*a*b*
    measured: tuple[float, float, float]  # measured L*a*b*
    de: float

    @property
    def dl(self) -> float:
        """Signed lightness error (measured − reference)."""
        return self.measured[0] - self.target[0]

    @property
    def dab(self) -> float:
        """Magnitude of the a*/b* (colour) error."""
        da = self.measured[1] - self.target[1]
        db = self.measured[2] - self.target[2]
        return math.hypot(da, db)

    @property
    def lightness_dominated(self) -> bool:
        """True when the error is mostly lightness rather than colour."""
        return abs(self.dl) > self.dab


@dataclass
class ColverifyParams:
    ref_ti3: Path                 # target (reference) — built by write_reference_ti3
    measured_ti3: Path            # the user's chartread measurement
    de_formula: str = "-k"        # "" = CIE76, "-c" = CIE94, "-k" = CIEDE2000
    sort: bool = True             # -s : sort patches worst-first
    match_by_location: bool = False  # -l : pair by SAMPLE_LOC instead of SAMPLE_ID
    per_patch: bool = True        # -v 2 : print every patch's ΔE
    gamut_profile: Path | None = None  # -L : skip reference colours outside this profile's gamut
    vrml: bool = False            # -w : also emit a 3D PCS vector visualisation (.x3d.html)


@dataclass
class ColverifyResult:
    avg_de: float | None = None
    peak_de: float | None = None
    patch_errors: list[tuple[str, float]] = field(default_factory=list)
    raw_log: str = ""
    # Richer extras (present when colverify printed them):
    patches: list[PatchDelta] = field(default_factory=list)
    worst10_avg: float | None = None
    worst10_peak: float | None = None
    best90_avg: float | None = None
    best90_peak: float | None = None
    comp_l: float | None = None   # mean signed ΔL* across in-gamut patches
    comp_a: float | None = None
    comp_b: float | None = None
    in_gamut: int | None = None   # only set when a gamut profile (-L) was supplied
    total_patches: int | None = None


#: A per-patch line cut in two. ArgyllRunner emits whatever one pipe read
#: holds, so a line that straddles two reads arrives as two "lines" (on
#: purpose: Argyll's prompts end without a newline and must show at once),
#: and the cut falls anywhere. Measured on screen 2026-11-11 on 616-patch
#: runs: "389: " / "17.417000 0.873000 …  de 0.226562", and
#: "52 AP8: 37.492753 -3.723912 -33.537" / "450 <=> 37.713860 …"; the result
#: then said 615 patches.
def _rejoin_split_patch_lines(lines: "list[str]") -> "list[str]":
    """*lines* with each per-patch line that was cut in two put back
    together: two neighbours that are no patch line apart, and are one
    joined exactly as they arrived."""
    out: list[str] = []
    for ln in lines:
        if out:
            prev = out[-1]
            if (not _PATCH_FULL_RE.match(prev.strip())
                    and not _PATCH_FULL_RE.match(ln.strip())
                    and _PATCH_FULL_RE.match((prev + ln).strip())):
                out[-1] = prev + ln
                continue
        out.append(ln)
    return out


def _path_from(target: Path, cwd: Path) -> str:
    """*target* as a program running in *cwd* can open it: its bare name when
    it sits in *cwd*, otherwise its path relative to *cwd*, the way
    ``average_runner`` addresses its inputs.

    Relative rather than absolute, because ArgyllCMS opens files through the
    narrow (ANSI) API on Windows, where a folder name the code page cannot
    hold (a user name with letters outside it, above the temp folder) fails
    to open; a relative path leaves out the part both paths share. Taken
    between REAL paths, because the program climbs ``..`` from its real
    working folder (``/tmp`` is ``/private/tmp`` on macOS). Absolute when
    the two are on different Windows drives."""
    t = os.path.realpath(target)
    c = os.path.realpath(cwd)
    if os.path.dirname(t) == c:
        return os.path.basename(t)
    try:
        return os.path.relpath(t, c)
    except ValueError:
        return t


class ColverifyRunner:
    def __init__(self, runner: "ArgyllRunner") -> None:
        self._runner = runner
        self._last_log = ""

    def _build_args(self, p: ColverifyParams) -> list[str]:
        args: list[str] = []
        if p.per_patch:
            args += ["-v", "2"]
        if p.de_formula:
            args.append(p.de_formula)
        if p.match_by_location:
            args.append("-l")
        if p.sort:
            args.append("-s")
        if p.vrml:
            args.append("-w")
        if p.gamut_profile is not None:
            # colverify opens the profile directly, so an absolute path is fine
            # even though the measurement is named relative to cwd.
            args += ["-L", os.path.abspath(p.gamut_profile)]
        # colverify runs in the MEASUREMENT's folder (run(): -w writes
        # <measured stem>.x3d.html there, where vrml_output_path looks), so
        # the measurement goes by name, and the reference by its path FROM
        # that folder. Until 4.3.30 the reference went by name too, and since
        # c56c1061c (4.3.3 beta 3) the dialog writes it into its staging
        # folder: every check of pasted values without the 3D map ended in
        # colverify's "Unable to open file '<stem>-reference.ti3'".
        args += [_path_from(p.ref_ti3, p.measured_ti3.parent),
                 p.measured_ti3.name]
        return args

    def run(
        self,
        params: ColverifyParams,
        on_line: Callable[[str], None],
        on_finish: Callable[[int], None],
    ) -> None:
        from workflow.cal_repair import repair_all
        repair_all([params.ref_ti3, params.measured_ti3])
        args = self._build_args(params)
        cwd = params.measured_ti3.parent
        log.info("colverify: %s  [cwd=%s]", " ".join(args), cwd)
        self._last_log = ""

        def _accumulate(line: str) -> None:
            self._last_log += line + "\n"
            on_line(line)

        self._runner.run(
            "colverify", args, cwd, on_line=_accumulate, on_finish=on_finish,
        )

    @property
    def last_log(self) -> str:
        return self._last_log

    def parse_results(self, log_text: str = "") -> ColverifyResult:
        text = log_text or self._last_log
        result = ColverifyResult(raw_log=text)

        m = _SUMMARY_RE.search(text)
        if m:
            result.peak_de = float(m.group(1))
            result.avg_de = float(m.group(2))
        if (m := _WORST10_RE.search(text)) is not None:
            result.worst10_peak = float(m.group(1))
            result.worst10_avg = float(m.group(2))
        if (m := _BEST90_RE.search(text)) is not None:
            result.best90_peak = float(m.group(1))
            result.best90_avg = float(m.group(2))
        if (m := _COMP_RE.search(text)) is not None:
            result.comp_l = float(m.group(1))
            result.comp_a = float(m.group(2))
            result.comp_b = float(m.group(3))
        if (m := _GAMUT_RE.search(text)) is not None:
            result.in_gamut = int(m.group(1))
            result.total_patches = int(m.group(2))

        for line in _rejoin_split_patch_lines(text.splitlines()):
            stripped = line.strip()
            full = _PATCH_FULL_RE.match(stripped)
            if full:
                nums = [float(full.group(i)) for i in range(2, 9)]
                result.patches.append(
                    PatchDelta(
                        sample_id=full.group(1),
                        target=(nums[0], nums[1], nums[2]),
                        measured=(nums[3], nums[4], nums[5]),
                        de=nums[6],
                    )
                )
                result.patch_errors.append((full.group(1), nums[6]))
                continue
            # Fall back to the loose ΔE-only matcher so summary/other layouts
            # (and the existing self-compare test fixtures) still populate
            # patch_errors even if the full triple line doesn't parse.
            pm = _PATCH_RE.match(stripped)
            if pm:
                result.patch_errors.append((pm.group(1), float(pm.group(2))))
        return result


# ---------------------------------------------------------------------------
# Plain-language interpretation
# ---------------------------------------------------------------------------
# Average-ΔE bands, kept in step with profcheck's quality grading so the two
# verify paths speak the same language to the user.
_GRADE_LABELS = ("excellent", "good", "acceptable", "in need of work")
_AVG_THRESHOLDS = (1.0, 2.0, 4.0)
# Below this, a mean signed component error is just measurement noise, not a
# meaningful lightness/colour lean.
_COMP_NOISE = 0.5


def _grade(avg_de: float) -> str:
    t1, t2, t3 = _AVG_THRESHOLDS
    if avg_de < t1:
        return _GRADE_LABELS[0]
    if avg_de < t2:
        return _GRADE_LABELS[1]
    if avg_de < t3:
        return _GRADE_LABELS[2]
    return _GRADE_LABELS[3]


def interpret(result: ColverifyResult) -> str:
    """Turn a parsed colverify result into a friendly, beginner-readable summary.

    Leads with the outcome, explains a gamut-skip if one happened, and — the
    point of the whole exercise — says whether the remaining error is mostly
    *lightness* (a black-point / paper-reachability limit, often expected) or
    mostly *colour* (a real accuracy problem worth chasing).
    """
    if result.avg_de is None:
        return (
            "colverify didn't return a result. Check that your measured .ti3 has "
            "the same patches as the reference (they're matched by patch number)."
        )

    parts: list[str] = []

    peak = f"  ·  Peak ΔE {result.peak_de:.2f}" if result.peak_de is not None else ""
    n = len(result.patch_errors)
    parts.append(f"Average ΔE {result.avg_de:.2f}{peak}" + (f"  ({n} patches)" if n else ""))

    # Gamut skip — explain why some patches vanished, so the result isn't a mystery.
    if (
        result.in_gamut is not None
        and result.total_patches is not None
        and result.in_gamut < result.total_patches
    ):
        skipped = result.total_patches - result.in_gamut
        parts.append(
            f"{skipped} of {result.total_patches} reference colours fall outside "
            "what this paper/profile can physically reproduce, so they were left "
            "out — otherwise their large, unavoidable errors would dominate "
            f"everything. The numbers describe the {result.in_gamut} colours your "
            "paper can actually make."
        )

    # Lightness vs colour — the core insight.
    if result.comp_l is not None and result.comp_a is not None and result.comp_b is not None:
        colour_mag = math.hypot(result.comp_a, result.comp_b)
        if abs(result.comp_l) > _COMP_NOISE and abs(result.comp_l) > colour_mag:
            direction = "lighter" if result.comp_l > 0 else "darker"
            parts.append(
                "Most of the difference is in lightness, not colour: on average "
                f"the print came out {direction} than the reference (ΔL* "
                f"{result.comp_l:+.1f}) while the actual colour was much closer "
                f"(Δa*b* {colour_mag:.1f}). That's typical when the reference "
                "values were made for a different paper or finish — the hue and "
                "saturation match better than the ΔE alone suggests."
            )
        elif colour_mag > _COMP_NOISE and colour_mag > abs(result.comp_l):
            parts.append(
                f"The difference is mostly in colour (Δa*b* {colour_mag:.1f}) "
                f"rather than brightness (ΔL* {result.comp_l:+.1f}) — a genuine "
                "colour shift worth a closer look, not just a black-point limit."
            )

    if result.best90_avg is not None and n > 10:
        parts.append(
            f"Setting aside the worst 10% of patches, the rest match at average "
            f"ΔE {result.best90_avg:.2f}."
        )

    parts.append(f"Overall, this match is {_grade(result.avg_de)}.")
    return "\n\n".join(parts)
