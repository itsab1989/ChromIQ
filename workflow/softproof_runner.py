"""Soft-proof an image against a printer profile, and flag out-of-gamut colour.

Two ``cctiff`` passes (run async via :class:`~core.argyll_runner.ArgyllRunner`,
which is single-process, so they're chained) plus a NumPy compare:

  * **ref Lab**   — ``cctiff source.icm img`` → the image's own colorimetry.
  * **proof Lab** — ``cctiff source.icm printer.icm printer.icm img`` → the
    colour the printer would actually reproduce. Sandwiching the printer
    profile (PCS→device→PCS) simulates the print: relative-colorimetric
    intent *clips* out-of-gamut colours onto the gamut boundary, which is
    exactly what we detect.

Per pixel, ``ΔE(ref, proof)`` is ~0 where the colour is in gamut and large
where it was clipped. Pixels above a small threshold are out of gamut → we
build a highlight overlay and an out-of-gamut percentage. The soft-proof
preview itself is the proof Lab rendered to sRGB (an honest *approximate*
on-screen proof — see the dialog caption).

Everything ArgyllCMS touches must be **ICC v2** (the caller guards on
:func:`workflow.icc_info.is_v4`). cctiff is launched via QProcess, so it never
blocks the UI; large images are downsampled by the caller to bound runtime.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import numpy as np
from PIL import Image
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.i18n import tr
from core.logger import get_logger

if TYPE_CHECKING:
    from core.argyll_runner import ArgyllRunner

log = get_logger(__name__)


# --- Lab(D50) -> sRGB, vectorised (mirrors workflow.spot_read_io scalars) ---
_D50 = np.array([0.96422, 1.0, 0.82521], dtype=np.float64)
_BRADFORD_D50_TO_D65 = np.array([
    ( 0.9555766, -0.0230393,  0.0631636),
    (-0.0282895,  1.0099416,  0.0210077),
    ( 0.0122982, -0.0204830,  1.3299098),
])
_XYZ_TO_RGB = np.array([
    ( 3.2404542, -1.5371385, -0.4985314),
    (-0.9692660,  1.8760108,  0.0415560),
    ( 0.0556434, -0.2040259,  1.0572252),
])


def lab_d50_to_srgb_array(lab: np.ndarray) -> np.ndarray:
    """(...,3) D50 L*a*b* -> (...,3) uint8 sRGB, clamped to gamut."""
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t):
        t3 = t ** 3
        return np.where(t3 > 0.008856, t3, (t - 16.0 / 116.0) / 7.787)

    xyz = np.stack([finv(fx), finv(fy), finv(fz)], axis=-1) * _D50
    xyz65 = xyz @ _BRADFORD_D50_TO_D65.T
    rgb_lin = xyz65 @ _XYZ_TO_RGB.T
    rgb_lin = np.clip(rgb_lin, 0.0, 1.0)
    srgb = np.where(rgb_lin <= 0.0031308,
                    12.92 * rgb_lin,
                    1.055 * np.power(rgb_lin, 1.0 / 2.4) - 0.055)
    return np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _decode_lab_tiff(path: Path) -> np.ndarray:
    """Read an 8-bit CIELab TIFF (cctiff output) into float L*a*b*."""
    arr = np.asarray(Image.open(path)).astype(np.float32)
    if arr.ndim == 2:
        arr = np.dstack([arr, np.zeros_like(arr), np.zeros_like(arr)])
    # 8-bit TIFF CIELab (cctiff "CIELab" photometric): L* is unsigned
    # 0..255 → 0..100; a*/b* are *signed* two's-complement int8 stored in a
    # uint8 byte (so byte 1 ≈ 0, byte 255 = −1), NOT an offset-128 value.
    # Decoding them as byte−128 is what gave the proof its blue cast.
    L = arr[..., 0] * 100.0 / 255.0
    a = np.where(arr[..., 1] < 128, arr[..., 1], arr[..., 1] - 256.0)
    b = np.where(arr[..., 2] < 128, arr[..., 2], arr[..., 2] - 256.0)
    return np.dstack([L, a, b])


# --- Source-space + image preparation ---------------------------------------

def argyll_ref_dir(settings) -> Path | None:
    """The Argyll ``ref`` directory for the configured ``bin`` dir.

    A Homebrew install points ``bin`` at ``/opt/homebrew/bin`` — a symlink
    farm with no ``ref`` beside it, while the real ``ref`` lives next to the
    actual binaries in the Cellar. :func:`core.argyll_detect.resolve_ref_dir`
    follows the per-binary symlinks to find it (Knut). Note ``.resolve()`` on
    the ``bin`` *directory* itself does NOT help — only the binaries inside
    are symlinks.
    """
    from core.argyll_detect import resolve_ref_dir
    bin_path = settings.get("argyll_bin_path", "/Applications/Argyll/bin")
    if not bin_path:
        return None
    return resolve_ref_dir(bin_path)


def _bundled_profiles_dir() -> Path | None:
    """ChromIQ's own copy of the standard working-space profiles, used when
    Argyll's ``ref`` folder can't be found (e.g. Homebrew installs)."""
    from core.resource_path import resource_path
    d = resource_path("assets/profiles")
    return d if d.exists() else None


def find_colorspace_profile(name: str, settings) -> Path | None:
    """Locate a named working-space profile (e.g. ``sRGB.icm``): prefer Argyll's
    ``ref`` directory, then fall back to ChromIQ's bundled copy."""
    for d in (argyll_ref_dir(settings), _bundled_profiles_dir()):
        if d is not None and (d / name).exists():
            return d / name
    return None


def resolve_source_profile(
    image_path: Path, source_choice: str, settings, work_dir: Path,
    custom_path: Path | None = None,
) -> tuple[Path | None, str]:
    """Return ``(profile_path, note)`` for the image's source colour space.

    ``source_choice`` is "embedded", "srgb", "adobergb", "p3", "prophoto" or
    "custom". For "embedded" we pull the image's embedded ICC; if it's absent or
    ICC v4 (Argyll can't read v4) we fall back to sRGB and say so in ``note``.
    For "custom" we use ``custom_path`` (the profile the user browsed to).
    Named profiles are found in Argyll's ``ref`` folder or, failing that, in
    ChromIQ's bundled copy — so this works even when Argyll's ``ref`` is missing.
    """
    named = {
        "srgb":     ("sRGB.icm",        tr("source assumed sRGB")),
        "adobergb": ("ClayRGB1998.icm", tr("source assumed Adobe RGB (1998)")),
        "p3":       ("DisplayP3.icm",   tr("source assumed Display P3")),
        "prophoto": ("ProPhoto.icm",    tr("source assumed ProPhoto RGB")),
    }
    srgb = find_colorspace_profile("sRGB.icm", settings)

    if source_choice == "custom" and custom_path is not None:
        from workflow.icc_info import is_v4
        if not custom_path.exists():
            return srgb, tr("the colour-space profile you chose is missing — assumed sRGB")
        if is_v4(custom_path):
            return srgb, tr("the colour-space profile you chose is ICC v4 (unreadable) — assumed sRGB")
        return custom_path, tr("using the colour-space profile you chose")

    if source_choice == "embedded":
        try:
            profile_bytes = Image.open(image_path).info.get("icc_profile")
        except OSError:
            profile_bytes = None
        if profile_bytes:
            emb = work_dir / "embedded_source.icc"
            emb.write_bytes(profile_bytes)
            from workflow.icc_info import is_v4
            if is_v4(emb):
                return srgb, tr("the image's embedded profile is ICC v4 (unreadable) — assumed sRGB")
            return emb, tr("using the image's embedded profile")
        return srgb, tr("no embedded profile — assumed sRGB")

    name, note = named.get(source_choice, named["srgb"])
    prof = find_colorspace_profile(name, settings)
    if prof is None:
        return srgb, named["srgb"][1]   # fall back to sRGB if the profile is absent
    return prof, note


def prepare_input_tiff(image_path: Path, work_dir: Path, max_dim: int = 1600) -> Path:
    """Normalise any image to an RGB TIFF (cctiff input), downsampled so the
    longest side is at most ``max_dim`` to bound cctiff/tiffgamut runtime."""
    img = Image.open(image_path)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    out = work_dir / "input.tif"
    img.save(out, compression="tiff_lzw")
    return out


# --- Result + runner ---------------------------------------------------------

@dataclass
class SoftproofResult:
    proof_path: str          # soft-proof preview (sRGB, no highlight)
    highlight_path: str      # same + out-of-gamut pixels marked
    original_path: str       # the loaded image (for the soft-proof on/off toggle)
    oog_percent: float       # % of pixels out of gamut
    source_note: str         # how the source space was determined
    paper_white_rgb: tuple[int, int, int] | None = None  # simulated paper white (margin tint)


_HIGHLIGHTS = {
    "gray":    (128, 128, 128),
    "magenta": (255, 0, 255),
    "cyan":    (0, 255, 255),
}


@dataclass
class SoftproofParams:
    image_path: Path
    printer_profile: Path
    source_choice: str = "srgb"     # embedded | srgb | adobergb | p3 | prophoto | custom
    custom_source: Path | None = None    # the ICC the user browsed to (source_choice="custom")
    intent: str = "r"               # cctiff -i (r=relative recommended for OOG)
    threshold: float = 2.0          # ΔE above which a pixel is "out of gamut"
    highlight: str = "gray"
    display_profile: Path | None = None  # monitor profile for a truer on-screen proof
    paper_white: bool = False       # simulate the paper's white (absolute colorimetric)


class SoftproofRunner(QObject):
    """Two chained cctiff passes + NumPy ΔE → soft-proof preview + OOG mask."""

    finished = pyqtSignal(object)   # SoftproofResult
    error    = pyqtSignal(str)

    def __init__(self, runner: "ArgyllRunner", settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runner = runner
        self._settings = settings

    def _drop_retired_work(self) -> None:
        """Delete the folder the previous proof used, if any."""
        import shutil

        retired = getattr(self, "_retired_work", None) or []
        if not isinstance(retired, list):
            retired = [retired]
        for folder in retired:
            shutil.rmtree(folder, ignore_errors=True)
        self._retired_work = []

    def cleanup(self) -> None:
        """Remove this runner's working folder, if it still has one.

        Called before each new run and from the dialog's teardown, so the last
        proof's files go when the dialog closes rather than at reboot.
        """
        import shutil

        self._drop_retired_work()          # a proof that never completed
        work = getattr(self, "_work", None)
        if work is None:
            return
        shutil.rmtree(work, ignore_errors=True)
        self._work = None

    def run(self, params: SoftproofParams) -> None:
        if self._runner.is_running:
            self.error.emit(tr("Another process is already running."))
            return
        self._params = params
        # DROP THE PREVIOUS PROOF'S WORK DIR BEFORE MAKING A NEW ONE.
        # This reassigned `self._work` on every run and orphaned the old folder
        # with nothing holding or deleting it — and a proof re-runs on a 350 ms
        # debounce from the intent combo, the ΔE spinbox, the highlight combo,
        # the paper-white box and both file pickers. Measured: ~56-70 MB per
        # proof of a 6 MP image (proof_preview 16.4 MB, proof_oog_lab 14.2 MB,
        # proof_highlight 13.2 MB, ref_lab 11.9 MB), two proofs left 143 MB.
        # Nothing reclaims it: main.py exits via os._exit(), so not even
        # TemporaryDirectory finalizers run. Safe here because `_run_softproof`
        # has already cleared the dialog's `_result` and `_combined_html`.
        # RETIRE the previous proof's folder, do not delete it yet. Deleting it
        # here pulled the TIFFs out from under the dialog: `_run_softproof`
        # clears `_combined_html` and the two .gam paths but NOT `self._result`,
        # so the preview kept showing `proof_preview.tif` after it had been
        # removed ("Cannot open TIFF"), and Save proof stayed enabled while
        # `_on_save_proof` silently returned on a missing file. The old folder
        # now goes only once the replacement has actually landed.
        # A LIST. Seven `error.emit(...); return` paths lie between here and
        # the success at the bottom, and a single slot meant a FAILED proof
        # between two good ones overwrote its predecessor's path — orphaning
        # ~56-70 MB for ever, since nothing sweeps $TMPDIR and main.py exits
        # via os._exit(). Dropping them up front instead would be wrong: after
        # a failure the dialog's `_result` still points into the retired
        # folder, so the preview and Save proof would follow a deleted file.
        retired = getattr(self, "_retired_work", None)
        if not isinstance(retired, list):
            retired = self._retired_work = []
        previous = getattr(self, "_work", None)
        if previous is not None:
            retired.append(previous)
        self._work = Path(tempfile.mkdtemp(prefix="chromiq_softproof_"))

        try:
            # Render the proof at (effectively) full resolution so it stays
            # sharp when zoomed in, matching the original. Only truly huge files
            # are capped, to bound cctiff/NumPy time + memory.
            self._input_tif = prepare_input_tiff(params.image_path, self._work, max_dim=6000)
        except (OSError, ValueError) as exc:
            self.error.emit(tr("Could not read the image: {exc}").format(exc=exc))
            return

        self._source_profile, self._source_note = resolve_source_profile(
            params.image_path, params.source_choice, self._settings, self._work,
            params.custom_source)
        if self._source_profile is None or not self._source_profile.exists():
            self.error.emit(tr(
                "Could not find a source colour-space profile (sRGB/Adobe RGB). "
                "Check that the ArgyllCMS 'ref' folder is present next to its 'bin'."))
            return

        # Pass 1: reference Lab (image's own colorimetry), relative colorimetric.
        self._ref_tif = self._work / "ref_lab.tif"
        self._run_cctiff(
            [str(self._source_profile), str(self._input_tif), str(self._ref_tif)],
            self._on_ref_done, intent="r")

    # ------------------------------------------------------------------
    def _run_cctiff(self, tail_args: list[str], done: Callable[[int], None],
                    intent: str) -> None:
        # -i before each profile in the chain (tail_args =
        # [prof, (prof, prof,) input, output]).
        rebuilt: list[str] = []
        for a in tail_args:
            if a.endswith(".icm") or a.endswith(".icc"):
                rebuilt += ["-i", intent, a]
            else:
                rebuilt.append(a)
        log.info("cctiff: %s", " ".join(rebuilt))
        self._runner.run("cctiff", rebuilt, self._work, on_line=lambda _l: None,
                         on_finish=done)

    def _on_ref_done(self, code: int) -> None:
        if code != 0 or not self._ref_tif.exists():
            self.error.emit(tr("cctiff failed while reading the image (code {c}).").format(c=code))
            return
        # Pass 2 (deferred so QProcess is fully torn down): the out-of-gamut
        # proof — ALWAYS relative colorimetric, so the % out of gamut measures
        # gamut clipping regardless of the preview intent / paper-white choice.
        QTimer.singleShot(0, self._run_oog_proof)

    def _run_oog_proof(self) -> None:
        self._proof_oog_tif = self._work / "proof_oog_lab.tif"
        p = str(self._params.printer_profile)
        self._run_cctiff(
            [str(self._source_profile), p, p, str(self._input_tif), str(self._proof_oog_tif)],
            self._on_oog_done, intent="r")

    def _on_oog_done(self, code: int) -> None:
        if code != 0 or not self._proof_oog_tif.exists():
            self.error.emit(tr("cctiff failed while simulating the print (code {c}). "
                               "Is the printer profile ICC v2?").format(c=code))
            return
        # The preview proof: absolute colorimetric when simulating paper white
        # (shows the media's actual off-white), else the chosen intent. Reuse the
        # relative OOG proof when they coincide (no second cctiff pass).
        self._preview_intent = "a" if self._params.paper_white else (self._params.intent or "r")
        if self._preview_intent == "r":
            self._proof_preview_tif = self._proof_oog_tif
            QTimer.singleShot(0, self._after_preview_proof)
        else:
            self._proof_preview_tif = self._work / "proof_preview_lab.tif"
            p = str(self._params.printer_profile)
            QTimer.singleShot(0, lambda: self._run_cctiff(
                [str(self._source_profile), p, p, str(self._input_tif),
                 str(self._proof_preview_tif)],
                self._on_preview_proof_done, intent=self._preview_intent))

    def _on_preview_proof_done(self, code: int) -> None:
        if code != 0 or not self._proof_preview_tif.exists():
            self.error.emit(tr("cctiff failed while simulating the print (code {c}). "
                               "Is the printer profile ICC v2?").format(c=code))
            return
        self._after_preview_proof()

    def _after_preview_proof(self) -> None:
        # When simulating paper white, derive the paper's white colour (the
        # printer's media white, absolute) so the preview margin can be tinted
        # with it — render a pure-white source patch through the proof chain.
        if self._params.paper_white:
            self._white_in = self._work / "white_in.tif"
            Image.new("RGB", (16, 16), (255, 255, 255)).save(self._white_in)
            self._white_proof = self._work / "white_proof_lab.tif"
            p = str(self._params.printer_profile)
            QTimer.singleShot(0, lambda: self._run_cctiff(
                [str(self._source_profile), p, p, str(self._white_in),
                 str(self._white_proof)], self._on_white_done, intent="a"))
        else:
            self._paper_white_rgb = None
            self._render_or_finish()

    def _on_white_done(self, code: int) -> None:
        self._paper_white_rgb = None
        if code == 0 and self._white_proof.exists():
            try:
                lab = _decode_lab_tiff(self._white_proof).reshape(-1, 3).mean(0)
                rgb = lab_d50_to_srgb_array(lab.reshape(1, 1, 3))[0, 0]
                self._paper_white_rgb = tuple(int(v) for v in rgb)
            except (OSError, ValueError):
                pass
        self._render_or_finish()

    def _render_or_finish(self) -> None:
        # Optional truer on-screen proof: render the PREVIEW proof Lab through
        # the monitor profile (Lab → display RGB) instead of the approximate sRGB.
        disp = self._params.display_profile
        if disp is not None and disp.exists():
            from workflow.icc_info import is_v4
            if is_v4(disp):
                self._display_note = tr(" (monitor profile is ICC v4 — used approximate sRGB)")
                QTimer.singleShot(0, lambda: self._finish_compute(None))
            else:
                self._display_tif = self._work / "proof_display.tif"
                self._display_note = tr(" (rendered for your monitor profile)")
                QTimer.singleShot(0, lambda: self._run_cctiff(
                    [str(disp), str(self._proof_preview_tif), str(self._display_tif)],
                    self._on_display_done, intent="r"))
        else:
            self._display_note = ""
            self._finish_compute(None)

    def _on_display_done(self, code: int) -> None:
        rgb = self._display_tif if (code == 0 and self._display_tif.exists()) else None
        if rgb is None:
            self._display_note = ""  # fell back to approximate
        self._finish_compute(rgb)

    def _finish_compute(self, display_rgb: Path | None) -> None:
        try:
            result = self._compute(display_rgb)
        except (OSError, ValueError) as exc:
            self.error.emit(tr("Could not compute the soft-proof: {exc}").format(exc=exc))
            return
        # The new proof is complete and its files are on disk — only now is the
        # previous one safe to drop.
        self._drop_retired_work()
        self.finished.emit(result)

    # ------------------------------------------------------------------
    def _compute(self, display_rgb: Path | None = None) -> SoftproofResult:
        # Out of gamut from the relative-colorimetric proof vs the image's own Lab.
        ref = _decode_lab_tiff(self._ref_tif)
        oog_proof = _decode_lab_tiff(self._proof_oog_tif)
        h = min(ref.shape[0], oog_proof.shape[0])
        w = min(ref.shape[1], oog_proof.shape[1])
        de = np.sqrt(((ref[:h, :w] - oog_proof[:h, :w]) ** 2).sum(-1))
        mask = de > self._params.threshold
        oog_percent = 100.0 * float(mask.mean())

        # Soft-proof preview: rendered through the monitor profile if one was
        # given (truer proof), otherwise the preview proof Lab → sRGB (which is
        # absolute colorimetric — paper white — when that option is on).
        if display_rgb is not None:
            disp_img = Image.open(display_rgb)
            if disp_img.mode != "RGB":
                disp_img = disp_img.convert("RGB")
            srgb = np.asarray(disp_img)
        else:
            srgb = lab_d50_to_srgb_array(_decode_lab_tiff(self._proof_preview_tif))
        # The preview and the OOG mask can differ by a pixel after separate
        # cctiff passes — clip both to the common size before compositing.
        ph = min(srgb.shape[0], mask.shape[0])
        pw = min(srgb.shape[1], mask.shape[1])
        srgb = srgb[:ph, :pw]
        mask = mask[:ph, :pw]
        proof_path = self._work / "proof_preview.tif"
        Image.fromarray(srgb, "RGB").save(proof_path, compression="tiff_lzw")

        # Highlight overlay.
        marked = srgb.copy()
        marked[mask] = np.array(_HIGHLIGHTS.get(self._params.highlight, (128, 128, 128)),
                                dtype=np.uint8)
        hl_path = self._work / "proof_highlight.tif"
        Image.fromarray(marked, "RGB").save(hl_path, compression="tiff_lzw")

        log.info("softproof: OOG=%.1f%% (ΔE>%.1f), preview=%s",
                 oog_percent, self._params.threshold, proof_path)
        return SoftproofResult(
            proof_path=str(proof_path),
            highlight_path=str(hl_path),
            original_path=str(self._input_tif),
            oog_percent=oog_percent,
            source_note=self._source_note + getattr(self, "_display_note", ""),
            paper_white_rgb=getattr(self, "_paper_white_rgb", None),
        )
