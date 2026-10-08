"""The chart preview shows the sheet as it will print (#182, beta 12).

Knut, 6045500910 answer 4: *"preview should always look as paper would look
printed, assuming normal printing path, as Sebastian said."* Basti,
6045468325: *"as soon as those settings are locked in for a verification run
I think showing the softproofed version makes sense. Maybe the tiff preview
could show a little indicator that gives this information without being a
distraction."*

A chart page TIFF holds the numbers sent to the printer. Painted as screen
RGB they are not what the paper shows (FINDINGS J of the beta-12 diagnosis:
L* 4.8 brighter on average on Basti's run2 chart). This module decides, for
one page, what the normal printing path does to it, and renders that:

* **a profiling chart** prints raw. With the run's profile built, the page is
  shown through that profile; before it, as device values, and the indicator
  says so;
* **a verification chart printed raw** (a FROM PROFILE GAMUT chart is always
  raw, §3.1a; a regular chart when Raw is chosen) is shown through the run's
  profile;
* **a verification chart printed through the profile** is converted exactly
  as the print converts it (the recorded source profile and intent, the
  cctiff arguments of :func:`workflow.verification_print.
  convert_pages_through_profile`) and the result shown through the profile.

Which way a verification chart prints: its print record once it has been
printed (and the record is newer than the page), else the Colour row's choice
(the Print Chart tab passes its live radios; the other tabs read the target's
stored choice, or the same history-aware default the Print tab starts from).

The screen end is relative colorimetric to Argyll's ``sRGB.icm``, as the
CMYK preview's "True colours" render already is: the paper is shown as the
screen's white, the colours as they sit relative to it. With **Simulate paper
white** (beta 14, Basti 2026-10-08, Photoshop's "Simulate Paper Color") the
run's profile is read absolute colorimetric instead, so the paper keeps the
tone the profile's media white point gives it and every colour sits on it as
on the sheet; only that last step, print to screen, changes (a verification
chart printed through the profile is converted for the print exactly as
before). See :attr:`PreviewPlan.paper_white` and :func:`paper_colour`.

Nothing here changes what is printed. Process model: ``subprocess.run`` with
an injectable runner and a ``timeout=``. Since build C of beta 12 (Basti,
2026-10-08) nothing is cached on disk: cctiff is asked only about the colours
a chain has not met yet, its answers are kept in memory, and a page is mapped
through them with numpy (:func:`softproof_page`).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

from core.logger import get_logger

log = get_logger(__name__)

#: What the preview shows.
KIND_RAW = "raw"            # the page's values, through the run's profile
KIND_THROUGH = "through"    # converted as the print converts it, then shown
KIND_DEVICE = "device"      # the page's values as screen colours (no profile)

#: Why a page is shown as device values.
WHY_NO_PROFILE = "no_profile"
WHY_CALIBRATED = "calibrated"      # the page holds calibrated pixels (-K)
WHY_FAILED = "failed"              # ArgyllCMS could not convert it

_TIMEOUT_S = 120

#: Per chain (see :func:`chain_key`), the colours cctiff has been asked
#: about and its answers, in memory only; the two most recent chains are kept.
_tables: "OrderedDict[tuple, _ColourTable]" = OrderedDict()
_MAX_TABLES = 2
_UNKNOWN = np.uint32(0xFFFFFFFF)
#: Chains cctiff refused.
_failed: "set[tuple]" = set()
#: The preview soft-proofs the page on screen itself and the chart's other
#: pages in a background thread (Basti, 2026-10-08: switching the view must be
#: a swap). `_lock` guards the globals above; `_fill_lock` lets one thread at
#: a time ask cctiff for new colours, so no colour is asked for twice.
_lock = threading.RLock()
_fill_lock = threading.Lock()


@dataclass(frozen=True)
class PreviewPlan:
    """How one chart page is to be shown."""
    kind: str
    profile: "Path | None" = None
    intent: str = ""                 # the print's own intent (through)
    source_profile: str = ""         # the print's source profile (through)
    printed: bool = False            # decided by a print record
    why: str = ""                    # for KIND_DEVICE
    #: Simulate paper white (beta 14): the profile is read absolute
    #: colorimetric on the way to the screen, so the paper shows its own tone.
    #: Never set by :func:`plan_for_page` (it decides how the page PRINTS);
    #: the preview sets it from the user's choice with ``dataclasses.replace``.
    paper_white: bool = False


@dataclass(frozen=True)
class _Chart:
    run_dir: Path
    ti2: Path
    verification: bool
    record_from: "Path | None"       # a .ti3 path whose print record applies


def _page_stem(tiff: Path) -> str:
    """The chart stem of a page TIFF (``<stem>.tif`` or ``<stem>_01.tif``)."""
    stem = tiff.stem
    base = stem.rstrip("0123456789")
    if base != stem and base.endswith(("_", "-")):
        return base[:-1]
    return stem


def chart_of_page(tiff: "str | Path") -> "_Chart | None":
    """Which run's chart *tiff* is a page of, or None (a calibration chart,
    a chart opened from elsewhere, a page in a temporary folder)."""
    from core.file_manager import VERIFICATIONS_DIRNAME
    RUNS_DIRNAME = "runs"            # Project.runs_root
    tiff = Path(tiff)
    d = tiff.parent
    stem = (tiff.stem if (d / f"{tiff.stem}.ti2").is_file()
            else _page_stem(tiff))
    try:
        if d.name == VERIFICATIONS_DIRNAME and d.parent.parent.name == RUNS_DIRNAME:
            ti2 = d / f"{stem}.ti2"
            return _Chart(d.parent, ti2, True, d / f"{stem}.ti3")
        # a dated verification's own snapshot: verifications/<date>/chart/
        if (d.name == "chart" and d.parent.parent.name == VERIFICATIONS_DIRNAME
                and d.parents[2].parent.name == RUNS_DIRNAME):
            ti2 = d / f"{stem}.ti2"
            return _Chart(d.parents[2], ti2, True, d.parent / f"{stem}.ti3")
        if d.parent.name == RUNS_DIRNAME:
            return _Chart(d, d / f"{stem}.ti2", False, None)
    except IndexError:
        return None
    return None


def _record_is_for_this_page(rec: dict, tiff: Path) -> bool:
    """A print record describes this page only if the page existed when it
    was printed: a chart generated again since is a new chart."""
    try:
        printed = datetime.fromisoformat(str(rec.get("printed_at") or ""))
        made = datetime.fromtimestamp(tiff.stat().st_mtime)
    except (OSError, ValueError, TypeError):
        return False
    return printed >= made.replace(microsecond=0)


def _stored_colour(run_dir: Path) -> "tuple[str, str]":
    """The verification target's stored Colour and intent, or ``("", "")``."""
    meta = run_dir / "verifications" / "meta.json"
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
        ps = data.get("print_settings") or {}
        return str(ps.get("colour") or ""), str(ps.get("intent") or "")
    except (OSError, ValueError, AttributeError):
        return "", ""


def plan_for_page(tiff: "str | Path", *, selected_colour: "str | None" = None,
                  selected_intent: "str | None" = None,
                  bin_dir: "str | Path | None" = None) -> "PreviewPlan | None":
    """How *tiff* is shown, or None when it is not a run's chart page.

    *selected_colour* / *selected_intent*: the Print Chart tab's live Colour
    row, which is what the next print will do; it outranks the print record
    there. Never raises."""
    try:
        return _plan(Path(tiff), selected_colour, selected_intent, bin_dir)
    except Exception:      # noqa: BLE001 — a preview is never worth a crash
        log.debug("print preview plan failed for %s", tiff, exc_info=True)
        return None


def _plan(tiff, selected_colour, selected_intent, bin_dir):
    from core.file_manager import Run
    from workflow import printer_calibration as pc
    from workflow import verification_print as vp
    chart = chart_of_page(tiff)
    if chart is None:
        return None
    run = Run.for_dir(chart.run_dir)
    profile = Path(run.built_profile_icc())
    if not profile.is_file():
        return PreviewPlan(KIND_DEVICE, why=WHY_NO_PROFILE)
    mode = pc.calibration_mode_of(chart.ti2) if chart.ti2.is_file() else pc.MODE_OFF
    if mode in (pc.MODE_APPLY, pc.MODE_OLD_ENGINE_APPLY, pc.MODE_UNKNOWN):
        # The page's pixels carry the printer calibration (printtarg -K):
        # the profile describes the values BEFORE it, so it cannot be applied
        # to these pixels honestly.
        return PreviewPlan(KIND_DEVICE, profile=profile, why=WHY_CALIBRATED)
    if not chart.verification:
        return PreviewPlan(KIND_RAW, profile=profile)

    # A FROM PROFILE GAMUT chart is already in the printer's values and is
    # always printed raw (§3.1a).
    if vp.chart_conversion_state(chart.ti2) != vp.STATE_REGULAR:
        rec = vp.read_print_record(chart.record_from) if chart.record_from else None
        printed = bool(isinstance(rec, dict)
                       and vp.record_answers_how_printed(rec)
                       and _record_is_for_this_page(rec, tiff))
        return PreviewPlan(KIND_RAW, profile=profile, printed=printed)

    colour, intent, source, printed = "", "", "", False
    if selected_colour in (vp.COLOUR_RAW, vp.COLOUR_THROUGH):
        colour, intent = selected_colour, selected_intent or ""
    else:
        rec = vp.read_print_record(chart.record_from) if chart.record_from else None
        if (isinstance(rec, dict) and str(rec.get("printed_at") or "").strip()
                and rec.get("colour") in (vp.COLOUR_RAW, vp.COLOUR_THROUGH)
                and _record_is_for_this_page(rec, tiff)):
            colour, intent = rec["colour"], str(rec.get("intent") or "")
            source = str(rec.get("source_profile") or "")
            printed = True
        else:
            colour, intent = _stored_colour(chart.run_dir)
            if colour not in (vp.COLOUR_RAW, vp.COLOUR_THROUGH):
                colour = vp.default_colour_for_run(run)
    if colour == vp.COLOUR_RAW:
        return PreviewPlan(KIND_RAW, profile=profile, printed=printed)
    if bin_dir is not None:
        source = vp.recorded_source_profile(source, bin_dir)
    return PreviewPlan(KIND_THROUGH, profile=profile,
                       intent=intent or vp.DEFAULT_INTENT,
                       source_profile=source, printed=printed)


def _srgb(bin_dir: Path) -> "Path | None":
    ref = Path(bin_dir).parent / "ref" / "sRGB.icm"
    if ref.is_file():
        return ref
    try:
        from workflow.verification_print import source_profile_path
        p = source_profile_path(bin_dir)
        return Path(p) if p and Path(p).is_file() else None
    except Exception:      # noqa: BLE001
        return None


def _stat_key(path: "Path | str") -> tuple:
    p = Path(path)
    st = p.stat()
    return (str(p), st.st_mtime_ns, st.st_size)


def chain_key(plan: PreviewPlan, bin_dir: "str | Path") -> "tuple | None":
    """What a page's soft-proof depends on besides the page itself: the
    profile (path, modification time, size), the route, the intent, the
    source profile and the ArgyllCMS folder, and whether the paper white is
    simulated (its own colour table: the same page colour shows differently).
    None when the profile is gone."""
    if plan.kind not in (KIND_RAW, KIND_THROUGH) or plan.profile is None:
        return None
    try:
        key = (_stat_key(plan.profile), plan.kind, plan.intent,
               plan.source_profile, str(bin_dir))
    except OSError:
        return None
    return key + ("paper-white",) if plan.paper_white else key


#: The colour table's block size, as a shift: colours are grouped in runs of
#: 64 neighbours (0xRRGGBB >> 6), and only the groups a chart touches get room.
_BLOCK_SHIFT = 6
_BLOCK_MASK = np.uint32((1 << _BLOCK_SHIFT) - 1)


class _ColourTable:
    """Every 8-bit RGB colour this chain has been asked about, and what
    ArgyllCMS's cctiff made of it, packed 0xRRGGBB; :data:`_UNKNOWN` where
    nothing has been asked yet.

    Sparse (review C of beta 12): a flat 2^24 table is 64 MB per chain for
    the ~20,000 colours a 4000-patch chart holds. Here a 1 MB index of the
    2^18 blocks of 64 colours points into a store that holds only the blocks
    a chart touches: 5.6 MB for that chart, measured, and never more than the
    flat table. Block 0 of the store is all :data:`_UNKNOWN`, so a colour in
    a block nobody asked about reads as unknown without a branch. Reads and
    writes take the table's lock: the preview and its background prefetch
    share one table."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index = np.zeros(1 << (24 - _BLOCK_SHIFT), dtype=np.uint32)
        self._store = np.full(1 << _BLOCK_SHIFT, _UNKNOWN, dtype=np.uint32)
        self._used = 1                     # blocks in use, block 0 included

    def nbytes(self) -> int:
        return int(self._index.nbytes + self._store.nbytes)

    def lookup(self, packed: np.ndarray) -> np.ndarray:
        with self._lock:
            return self._store[self._index[packed >> _BLOCK_SHIFT]
                               | (packed & _BLOCK_MASK)]

    def insert(self, colours: np.ndarray, values: np.ndarray) -> None:
        with self._lock:
            blocks = np.unique(colours >> _BLOCK_SHIFT)
            new = blocks[self._index[blocks] == 0]
            if new.size:
                need = (self._used + new.size) << _BLOCK_SHIFT
                if need > self._store.size:
                    grown = np.full(max(need, 2 * self._store.size), _UNKNOWN,
                                    dtype=np.uint32)
                    grown[:self._store.size] = self._store
                    self._store = grown
                self._index[new] = (np.arange(self._used, self._used + new.size,
                                              dtype=np.uint32) << _BLOCK_SHIFT)
                self._used += int(new.size)
            self._store[self._index[colours >> _BLOCK_SHIFT]
                        | (colours & _BLOCK_MASK)] = values


def _table_for(key: tuple) -> _ColourTable:
    with _lock:
        t = _tables.get(key)
        if t is None:
            t = _ColourTable()
            _tables[key] = t
            # the same chain with an older profile file is never asked again
            for old in [k for k in _tables if k != key and k[0][0] == key[0][0]
                        and k[1:] == key[1:]]:
                del _tables[old]
            while len(_tables) > _MAX_TABLES:
                _tables.popitem(last=False)
        else:
            _tables.move_to_end(key)
        return t


def _page_pixels(tiff: Path, frame: int) -> "np.ndarray | None":
    """The page's frame as an (h, w, 3) uint8 array, or None when it is not
    an 8-bit RGB page (those are not soft-proofed here)."""
    from PIL import Image
    with Image.open(tiff) as im:
        try:
            im.seek(frame)
        except EOFError:
            pass
        if im.mode not in ("RGB", "RGBA"):
            return None
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def _pack(a: np.ndarray) -> np.ndarray:
    return ((a[..., 0].astype(np.uint32) << 16)
            | (a[..., 1].astype(np.uint32) << 8) | a[..., 2].astype(np.uint32))


def _unpack(p: np.ndarray) -> np.ndarray:
    out = np.empty(p.shape + (3,), dtype=np.uint8)
    out[..., 0] = (p >> 16) & 0xFF
    out[..., 1] = (p >> 8) & 0xFF
    out[..., 2] = p & 0xFF
    return out


#: The temporary folder of one cctiff call is named after the process that
#: made it, so a ChromIQ that was killed in the middle of a call (Force Quit,
#: a crash) leaves a folder the next one can recognise as an orphan and
#: remove (review C of beta 12: nothing of the preview may stay on disk).
_TMP_PREFIX = "chromiq-print-preview-"
_swept = False


def _tmp_prefix() -> str:
    import os
    return f"{_TMP_PREFIX}{os.getpid()}-"


def _pid_alive(pid: int) -> bool:
    import os
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # type: ignore[attr-defined]
        if not h:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))  # type: ignore[attr-defined]
        ctypes.windll.kernel32.CloseHandle(h)  # type: ignore[attr-defined]
        return code.value == 259           # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True                        # someone else's: alive
    return True


def _sweep_orphans(root: "Path | None" = None) -> None:
    """Once per process: remove the preview's temporary folders left by a
    ChromIQ that no longer runs. Only folders with this exact name pattern,
    only in the temporary folder, only when their process is gone."""
    global _swept
    if _swept and root is None:
        return
    _swept = True
    import shutil
    base = Path(root or tempfile.gettempdir())
    try:
        found = list(base.glob(_TMP_PREFIX + "*"))
    except OSError:
        return
    for d in found:
        rest = d.name[len(_TMP_PREFIX):]
        pid = rest.split("-", 1)[0]
        if not d.is_dir() or d.is_symlink() or not pid.isdigit() \
                or _pid_alive(int(pid)):
            continue
        shutil.rmtree(d, ignore_errors=True)


def _cctiff_colours(colours: np.ndarray, plan: PreviewPlan, bin_dir: Path,
                    runner) -> "np.ndarray | None":
    """Send *colours* (packed 0xRRGGBB) through the same cctiff chain the page
    itself used to go through, as a small image of just those colours, and
    return what came out, in the same order. cctiff transforms each pixel on
    its own, so a colour comes out of this exactly as it comes out of the
    whole page. The two small files live in a temporary folder for the
    duration of the call and are gone when it returns."""
    from PIL import Image
    from core.proc_text import run_text
    from core.resource_path import argyll_binary
    from workflow.cctiff_apply import convert_args
    from workflow.verification_print import intent_letter
    exe = bin_dir / argyll_binary("cctiff")
    srgb = _srgb(bin_dir)
    if not exe.exists() or srgb is None:
        return None
    if plan.kind == KIND_THROUGH and (
            not plan.source_profile or not Path(plan.source_profile).is_file()):
        return None
    n = int(colours.size)
    w = min(n, 1024)
    h = -(-n // w)
    flat = np.empty(w * h, dtype=np.uint32)
    flat[:n] = colours
    flat[n:] = colours[-1]
    _sweep_orphans()
    with tempfile.TemporaryDirectory(prefix=_tmp_prefix()) as tmp:
        src = Path(tmp) / "colours.tif"
        out = Path(tmp) / "shown.tif"
        Image.fromarray(_unpack(flat.reshape(h, w)), "RGB").save(src)
        steps: "list[list[str]]" = []
        if plan.kind == KIND_THROUGH:
            sent = Path(tmp) / "sent.tif"
            # exactly the print's own conversion (same arguments, same depth)
            steps.append([str(exe), *convert_args(
                Path(plan.source_profile), plan.profile, src, sent,
                verbose=False, intent=intent_letter(plan.intent))])
            src = sent
        # print to screen: the profile relative colorimetric (the paper is
        # the screen's white), or absolute when the paper white is simulated
        # (the paper keeps its own tone, D50 adapted to the screen's white,
        # as Photoshop's Simulate Paper Color shows it)
        steps.append([str(exe), "-f", "T",
                      "-i", "a" if plan.paper_white else "r", str(plan.profile),
                      "-i", "r", str(srgb), str(src), str(out)])
        for cmd in steps:
            try:
                r = run_text(cmd, runner=runner, capture_output=True,
                             timeout=_TIMEOUT_S)
            except (OSError, subprocess.TimeoutExpired) as exc:
                log.warning("print preview: cctiff did not finish: %s", exc)
                return None
            if r.returncode != 0:
                log.info("print preview unavailable (cctiff %s): %s",
                         r.returncode,
                         ((r.stderr or "") + (r.stdout or "")).strip()[-200:])
                return None
        if not out.is_file():
            return None
        with Image.open(out) as im:
            if im.mode != "RGB" or im.size != (w, h):
                log.info("print preview: cctiff answered %s %s", im.mode, im.size)
                return None
            got = np.asarray(im, dtype=np.uint8)
    return _pack(got).reshape(-1)[:n]


def softproof_page(tiff: "str | Path", plan: PreviewPlan, bin_dir: "str | Path",
                   *, frame: int = 0,
                   runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                   fill_only: bool = False) -> "np.ndarray | None":
    """The page as it will print, for the screen: an (h, w, 3) uint8 RGB
    array at the page's own resolution, or None when it cannot be made (the
    caller then shows the device values and says so). Never raises.

    **Nothing is written to disk that outlives the call** (Basti,
    2026-10-08). A chart page holds a few thousand distinct colours, so only
    the colours this chain has not met yet go through cctiff, as a small
    image of those colours; what came out is kept in memory in a colour table
    per chain, and the page is mapped through it with numpy. The pixels are
    the ones cctiff makes of the whole page (`tests/test_beta12_c_preview_
    switch.py` compares them with a full-page cctiff run). A chain cctiff
    refused is remembered, so a broken chain is not retried on every repaint.
    """
    tiff, bin_dir = Path(tiff), Path(bin_dir)
    key = chain_key(plan, bin_dir)
    if key is None:
        return None
    with _lock:
        if key in _failed:
            return None
    try:
        page = _page_pixels(tiff, frame)
    except Exception:      # noqa: BLE001 — an unreadable page shows as it is
        log.debug("print preview: could not read %s", tiff, exc_info=True)
        return None
    if page is None:
        return None
    packed = _pack(page)
    out = _through_table(packed, key, plan, bin_dir, runner, tiff.name)
    if out is None or fill_only:
        return None
    return _unpack(out)


def _through_table(packed: np.ndarray, key: tuple, plan: PreviewPlan,
                   bin_dir: Path, runner, name: str) -> "np.ndarray | None":
    """*packed* mapped through the chain's colour table, asking cctiff first
    about any colour the table does not hold yet; None when cctiff refuses."""
    table = _table_for(key)
    out = table.lookup(packed)
    unknown = out == _UNKNOWN
    if not unknown.any():
        return out
    with _fill_lock:
        # another thread may have asked about these colours meanwhile
        out = table.lookup(packed)
        unknown = out == _UNKNOWN
        if not unknown.any():
            return out
        seen = np.zeros(1 << 24, dtype=bool)       # 16 MB, for this call only
        seen[packed[unknown]] = True
        missing = np.flatnonzero(seen).astype(np.uint32)
        del seen
        try:
            got = _cctiff_colours(missing, plan, bin_dir, runner)
        except Exception:      # noqa: BLE001 — a preview is never worth a crash
            log.debug("print preview: cctiff chain failed", exc_info=True)
            got = None
        if got is None:
            with _lock:
                _failed.add(key)
            return None
        table.insert(missing, got)
        log.info("print preview: %d new colours of %s through %s (%s)",
                 missing.size, name, plan.profile.name, plan.kind)
    # every colour of the page is in the table now, and entries never change
    return table.lookup(packed)


def prefetch_page(tiff: "str | Path", plan: PreviewPlan,
                  bin_dir: "str | Path") -> None:
    """Fill the chain's colour table with *tiff*'s colours, so showing the
    page later asks cctiff nothing; makes no picture (the background
    prefetch of the chart preview). Never raises."""
    softproof_page(tiff, plan, bin_dir, fill_only=True)


#: The paper's own colour on screen per profile (see :func:`paper_colour`),
#: a few bytes each, in memory only.
_paper: "OrderedDict[tuple, tuple[int, int, int] | None]" = OrderedDict()
_MAX_PAPER = 8


def paper_colour(plan: PreviewPlan, bin_dir: "str | Path", *,
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                 ) -> "tuple[int, int, int] | None":
    """The blank paper's colour on screen with the paper white simulated: the
    printer's device white (nothing printed) through *plan*'s profile,
    absolute colorimetric. It colours the frame the preview draws round a
    page. Always the PRINTER's white, also for a chart printed through the
    profile, whose own white margin is converted for the print first: the
    paper beyond the page is never printed on. None when ArgyllCMS cannot say.
    Never raises."""
    if plan.profile is None or plan.kind not in (KIND_RAW, KIND_THROUGH):
        return None
    paper = PreviewPlan(KIND_RAW, profile=plan.profile, paper_white=True)
    key = chain_key(paper, bin_dir)
    if key is None:
        return None
    with _lock:
        if key in _paper:
            _paper.move_to_end(key)
            return _paper[key]
        if key in _failed:
            return None
    try:
        got = _cctiff_colours(np.array([0xFFFFFF], dtype=np.uint32), paper,
                              Path(bin_dir), runner)
    except Exception:      # noqa: BLE001 — a preview is never worth a crash
        log.debug("print preview: paper colour failed", exc_info=True)
        got = None
    rgb = (tuple(int(v) for v in _unpack(got[:1])[0]) if got is not None
           else None)
    with _lock:
        _paper[key] = rgb
        while len(_paper) > _MAX_PAPER:
            _paper.popitem(last=False)
    return rgb


def clear_cache() -> None:
    """Forget every colour table and every refused chain (tests)."""
    with _lock:
        _tables.clear()
        _failed.clear()
        _paper.clear()
