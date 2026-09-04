"""COLOR_REP-agnostic ``.ti3`` reader for the profile engine (#122).

Unlike :mod:`workflow.ti3_analysis` (RGB-only, feeds the measurement
inspector), this reader accepts any device colour representation Argyll's
chartread can produce — ``iRGB``, ``CMYK``, ``CMYKOG``, light-ink reps like
``CMYKcm`` — and returns the device values as an (N, n) array plus the
measured XYZ.

Colour bases (the maths-A lesson, measured: the wrong basis costs ~7 ΔE
median):

* ``lab_absolute`` — Lab against D50 from the raw measured XYZ. This is what
  ``xicclu -ia`` speaks; use it for gamut work and cross-checks.
* ``lab_relative`` — media-relative Lab: measured XYZ Bradford-adapted from
  the *media white* to D50, so paper → exactly L*=100. This is what the
  profile's LUTs store (relative colorimetric); the ``wtpt`` tag plus the
  ``arts`` (Bradford) tag let CMMs reconstruct absolute colorimetry.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from workflow.profile_engine.icc_writer import BRADFORD
from core.text_io import read_text

D50_XYZ100 = np.array([96.42, 100.0, 82.49])

# Channel letters as they appear in COLOR_REP / field suffixes, multi-char
# tokens first (medium inks "2c…", light-light black "1k", light inks
# lowercase). Order = greedy tokeniser preference, not colorant order.
_LETTER_RE = re.compile(r"2c|2m|2y|2k|1k|[cmyk]|[A-Z]")


class Ti3Error(ValueError):
    """A .ti3 the profile engine cannot use (message is user-facing)."""


def split_rep_letters(device_rep: str) -> list[str]:
    """``"CMYKOG"`` → ``["C","M","Y","K","O","G"]``; handles ``cm``/``2c``/``1k``."""
    letters = _LETTER_RE.findall(device_rep)
    if "".join(letters) != device_rep:
        raise Ti3Error(f"Unrecognised colour representation {device_rep!r}.")
    return letters


@dataclass
class Ti3Measurement:
    path: Path
    color_rep: str                    # full token, e.g. "CMYK_XYZ"
    device_rep: str                   # device part, e.g. "CMYK" / "RGB"
    channel_letters: list[str]        # per-channel rep letters
    device: np.ndarray                # (N, n) fractions 0..1
    xyz: np.ndarray                   # (N, 3) absolute, Y=100 scale
    keywords: dict[str, str]
    text: str                         # full file text (embedded as 'targ')
    spectral: np.ndarray | None = None      # (N, bands) reflectance
    wavelengths: np.ndarray | None = None   # (bands,) nm
    sample_ids: list[str] | None = None     # SAMPLE_ID column, if present
    sample_locs: list[str] | None = None    # SAMPLE_LOC column (sheet cell)

    def patch_label(self, row: int) -> str:
        """How a person finds patch ``row`` (0-based) on the printed sheet:
        the SAMPLE_LOC cell first (that is what is printed next to the
        patch), the SAMPLE_ID in brackets, the data row as a last resort.
        A data-row number is meaningless on an imported or merged chart."""
        loc = self.sample_locs[row] if self.sample_locs else ""
        sid = self.sample_ids[row] if self.sample_ids else ""
        if loc and sid and loc != sid:
            return f"{loc} (ID {sid})"
        if loc or sid:
            return loc or sid
        return f"row {row + 1}"

    @property
    def n_channels(self) -> int:
        return self.device.shape[1]

    @property
    def is_additive(self) -> bool:
        """True when device 100% = white (RGB-like), False for ink counts."""
        return self.device_rep in ("RGB", "W")

    @property
    def ink_limit(self) -> float | None:
        """TOTAL_INK_LIMIT keyword in percent, if stamped."""
        v = self.keywords.get("TOTAL_INK_LIMIT")
        try:
            return float(v) if v is not None else None
        except ValueError:
            return None

    @property
    def black_ink_limit(self) -> float | None:
        """BLACK_INK_LIMIT keyword in percent, if stamped (targen -L; colprof
        reads it as the default black ink limit, colprof.c)."""
        v = self.keywords.get("BLACK_INK_LIMIT")
        try:
            return float(v) if v is not None else None
        except ValueError:
            return None

    # ------------------------------------------------------------------
    @cached_property
    def white_index(self) -> int:
        """Row index of the media-white patch (device white, brightest Y)."""
        target = 1.0 if self.is_additive else 0.0
        dist = np.abs(self.device - target).sum(1)
        near = np.flatnonzero(dist <= dist.min() + 1e-9)
        return int(near[np.argmax(self.xyz[near, 1])])

    @cached_property
    def media_white_xyz(self) -> np.ndarray:
        return self.xyz[self.white_index].copy()

    @cached_property
    def black_index(self) -> int:
        return int(np.argmin(self.xyz[:, 1]))

    # ------------------------------------------------------------------
    # Maximum-accuracy mode helpers (gammap_mode "accurate")
    # ------------------------------------------------------------------
    def average_endpoints(self) -> None:
        """Replace the single-patch white/black with duplicate averages.

        ``white_index`` picks the *brightest* of the duplicate device-white
        patches, which biases the media white high by ~σ·√(2·ln k) for k
        noisy repeats (max-selection bias); the black analogously low. The
        white is the Bradford adaptation basis for every patch, so the bias
        tilts the whole relative colorimetry. Averaging the duplicates is
        unbiased and reduces the noise by √k. Called by the builder in
        maximum-accuracy mode; a chart with a single white patch is
        unchanged.
        """
        target = 1.0 if self.is_additive else 0.0
        dist = np.abs(self.device - target).sum(1)
        near = np.flatnonzero(dist <= dist.min() + 1e-9)
        white = self.xyz[near].mean(0)
        bi = int(np.argmin(self.xyz[:, 1]))
        same = np.flatnonzero(
            np.abs(self.device - self.device[bi]).sum(1) <= 1e-9)
        black = self.xyz[same].mean(0)
        for attr in ("xyz_relative", "lab_relative",
                     "media_white_xyz", "black_xyz"):
            self.__dict__.pop(attr, None)
        self.__dict__["media_white_xyz"] = white
        self.__dict__["black_xyz"] = black

    @cached_property
    def black_xyz(self) -> np.ndarray:
        """XYZ of the darkest patch (the ``bkpt`` tag content)."""
        return self.xyz[self.black_index].copy()

    def collapse_duplicates(self) -> tuple[int, int]:
        """Average every group of exactly repeated device values into one
        row (XYZ and spectra; the first row's SAMPLE_ID/LOC is kept).

        Returns ``(groups, rows_removed)``. Fitting THROUGH k repeats is
        only equivalent to averaging them under equal weights, and it makes
        the robust loop read the between-read scatter of identical patches
        as misreads — measured on the noisy battery printer: 205 patches
        "flagged" with three stacked reads vs 62 pre-averaged, and the
        pre-averaged build won on every ground-truth metric (A-18)."""
        order = np.lexsort(self.device.T)
        groups: list[list[int]] = []
        cur = [int(order[0])]
        for prev, nxt in zip(order[:-1], order[1:]):
            if np.abs(self.device[nxt] - self.device[prev]).max() <= 1e-9:
                cur.append(int(nxt))
            else:
                groups.append(cur)
                cur = [int(nxt)]
        groups.append(cur)
        multi = [g for g in groups if len(g) > 1]
        if not multi:
            return 0, 0
        keep = sorted(min(g) for g in groups)
        xyz = self.xyz.copy()
        spec = None if self.spectral is None else self.spectral.copy()
        for g in multi:
            xyz[min(g)] = self.xyz[g].mean(0)
            if spec is not None:
                spec[min(g)] = self.spectral[g].mean(0)
        removed = len(self.device) - len(keep)
        self.device = self.device[keep]
        self.xyz = xyz[keep]
        if spec is not None:
            self.spectral = spec[keep]
        if self.sample_ids is not None:
            self.sample_ids = [self.sample_ids[i] for i in keep]
        if self.sample_locs is not None:
            self.sample_locs = [self.sample_locs[i] for i in keep]
        for attr in ("xyz_relative", "lab_relative", "lab_absolute",
                     "media_white_xyz", "white_index", "black_index",
                     "black_xyz"):
            self.__dict__.pop(attr, None)
        return len(multi), removed

    def extra_ink_hues(self) -> dict[str, float]:
        """Measured Lab hue angle per extra ink (channels beyond CMYK).

        The hue is read from the chart's own solid-ink patches (channel
        ≥ 85%, everything else ≤ 5%) instead of assumed constants — a
        printer whose orange leans red still gets its hue gate centred on
        the ink it actually has. Channels without a usable solid patch are
        absent from the result (callers fall back to the anchor table).
        """
        hues: dict[str, float] = {}
        if self.n_channels <= 4:
            return hues
        lab = self.lab_relative
        for ch in range(4, self.n_channels):
            others = np.delete(self.device, ch, axis=1)
            solid = (self.device[:, ch] >= 0.85) & (others.max(1) <= 0.05)
            if not solid.any():
                continue
            rows = lab[solid]
            chroma = np.hypot(rows[:, 1], rows[:, 2])
            good = chroma > 10.0
            if not good.any():
                continue
            a = float(rows[good, 1].mean())
            b = float(rows[good, 2].mean())
            hues[self.channel_letters[ch]] = float(
                np.degrees(np.arctan2(b, a)) % 360.0)
        return hues

    @cached_property
    def xyz_relative(self) -> np.ndarray:
        """Measured XYZ Bradford-adapted media-white → D50 (Y=100 scale)."""
        cone = BRADFORD @ (self.xyz.T / 100.0)
        cone_w = BRADFORD @ (self.media_white_xyz / 100.0)
        cone_d50 = BRADFORD @ (D50_XYZ100 / 100.0)
        adapted = np.linalg.inv(BRADFORD) @ (cone * (cone_d50 / cone_w)[:, None])
        return adapted.T * 100.0

    @cached_property
    def lab_relative(self) -> np.ndarray:
        return xyz_to_lab(self.xyz_relative)

    def relative_to_absolute_xyz(self, xyz_rel: np.ndarray) -> np.ndarray:
        """Undo :attr:`xyz_relative`'s adaptation: D50-relative XYZ (Y=100
        scale) → the measured, media-white basis. The exact inverse of the
        Bradford scaling the relative basis was built with."""
        xyz_rel = np.atleast_2d(np.asarray(xyz_rel, float))
        cone = BRADFORD @ (xyz_rel.T / 100.0)
        cone_w = BRADFORD @ (self.media_white_xyz / 100.0)
        cone_d50 = BRADFORD @ (D50_XYZ100 / 100.0)
        back = np.linalg.inv(BRADFORD) @ (cone * (cone_w / cone_d50)[:, None])
        return back.T * 100.0

    @cached_property
    def lab_absolute(self) -> np.ndarray:
        return xyz_to_lab(self.xyz)


def xyz_to_lab(xyz100: np.ndarray, white: np.ndarray = D50_XYZ100) -> np.ndarray:
    f = xyz100 / white[None, :]
    f = np.where(f > (6 / 29) ** 3, np.cbrt(f), f / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[:, 1] - 16,
                     500 * (f[:, 0] - f[:, 1]),
                     200 * (f[:, 1] - f[:, 2])], 1)


def lab_to_xyz(lab: np.ndarray, white: np.ndarray = D50_XYZ100) -> np.ndarray:
    fy = (lab[:, 0] + 16) / 116
    fx = fy + lab[:, 1] / 500
    fz = fy - lab[:, 2] / 200
    f = np.stack([fx, fy, fz], 1)
    v = np.where(f ** 3 > (6 / 29) ** 3, f ** 3, 3 * (6 / 29) ** 2 * (f - 4 / 29))
    return v * white[None, :]


_KW_RE = re.compile(r'^([A-Z0-9_]+)\s+"?([^"\n]*)"?\s*$')


def read_ti3(path: Path | str) -> Ti3Measurement:
    """Parse a ``.ti3`` into device n-D + XYZ arrays (Lab-only files accepted)."""
    p = Path(path)
    text = read_text(p, lenient=True)
    fm = re.search(r"BEGIN_DATA_FORMAT\s*\n(.*?)\nEND_DATA_FORMAT", text, re.S)
    dm = re.search(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", text, re.S)
    if not fm or not dm:
        raise Ti3Error(f"{p.name}: not a CGATS measurement file "
                       "(missing DATA_FORMAT / DATA block).")
    fields = fm.group(1).split()
    rows = [ln.split() for ln in dm.group(1).splitlines() if ln.strip()]
    if not rows:
        raise Ti3Error(f"{p.name}: the measurement table is empty.")

    keywords: dict[str, str] = {}
    for ln in text[:dm.start()].splitlines():
        m = _KW_RE.match(ln.strip())
        if m and m.group(2) != "":
            keywords.setdefault(m.group(1), m.group(2))

    color_rep = keywords.get("COLOR_REP", "")
    device_rep = color_rep.split("_")[0].lstrip("i")
    if not device_rep:
        raise Ti3Error(f"{p.name}: no COLOR_REP keyword — cannot identify "
                       "the device channels.")
    if device_rep in ("K", "W"):
        # Grayscale charts (targen -d0): COLOR_REP "K"/"W" with GRAY_* fields.
        prefix = "GRAY_"
        letters = [device_rep]
    else:
        prefix = device_rep + "_"
        letters = split_rep_letters(device_rep)
    dev_fields = [f for f in fields if f.startswith(prefix)]
    want = [prefix + letter for letter in letters]
    if dev_fields != want:
        # Order in the file is authoritative as long as the set matches.
        if sorted(dev_fields) != sorted(want):
            raise Ti3Error(
                f"{p.name}: device columns {dev_fields} don't match the "
                f"colour representation {device_rep!r}.")
        letters = [f[len(prefix):] for f in dev_fields]

    idx = {f: i for i, f in enumerate(fields)}
    ncol = len(fields)
    for r in rows:
        if len(r) < ncol:
            raise Ti3Error(f"{p.name}: malformed data row (expected {ncol} "
                           f"values, got {len(r)}).")

    def grab(names: list[str]) -> np.ndarray:
        cols = [idx[n] for n in names]
        return np.array([[float(r[i]) for i in cols] for r in rows], float)

    device = grab(dev_fields) / 100.0
    if all(c in idx for c in ("XYZ_X", "XYZ_Y", "XYZ_Z")):
        xyz = grab(["XYZ_X", "XYZ_Y", "XYZ_Z"])
    elif all(c in idx for c in ("LAB_L", "LAB_A", "LAB_B")):
        xyz = lab_to_xyz(grab(["LAB_L", "LAB_A", "LAB_B"]))
    else:
        raise Ti3Error(f"{p.name}: no XYZ or Lab columns in the measurement.")

    def column(name: str) -> list[str] | None:
        if name not in idx:
            return None
        return [r[idx[name]].strip('"') for r in rows]

    sample_ids, sample_locs = column("SAMPLE_ID"), column("SAMPLE_LOC")
    bad = ~(np.isfinite(device).all(1) & np.isfinite(xyz).all(1))
    if bad.any():
        probe = Ti3Measurement(path=p, color_rep=color_rep,
                               device_rep=device_rep, channel_letters=letters,
                               device=device, xyz=xyz, keywords=keywords,
                               text="", sample_ids=sample_ids,
                               sample_locs=sample_locs)
        rows_bad = np.flatnonzero(bad)
        names = ", ".join(probe.patch_label(int(i)) for i in rows_bad[:8])
        more = "" if len(rows_bad) <= 8 else f" (+{len(rows_bad) - 8} more)"
        raise Ti3Error(
            f"{p.name}: {len(rows_bad)} patch(es) have no usable reading "
            f"(nan/inf) — {names}{more}. Re-measure them, or remove those "
            f"rows, before building a profile.")

    spectral = wavelengths = None
    spec_cols = [i for i, f in enumerate(fields) if f.startswith("SPEC_")]
    if len(spec_cols) >= 3 and "SPECTRAL_BANDS" in keywords:
        try:
            bands = int(keywords["SPECTRAL_BANDS"])
            lo = float(keywords["SPECTRAL_START_NM"])
            hi = float(keywords["SPECTRAL_END_NM"])
        except (KeyError, ValueError):
            bands = -1
        if bands == len(spec_cols):
            spectral = np.array([[float(r[i]) for i in spec_cols]
                                 for r in rows], float)
            wavelengths = np.linspace(lo, hi, bands)

    return Ti3Measurement(path=p, color_rep=color_rep, device_rep=device_rep,
                          channel_letters=letters, device=device, xyz=xyz,
                          keywords=keywords, text=text,
                          spectral=spectral, wavelengths=wavelengths,
                          sample_ids=sample_ids, sample_locs=sample_locs)
