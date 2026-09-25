"""Lay a preset out behind the scenes, so its evenness rows can be judged.

Knut, #182 5832026677 (2026-09-25), on "Which presets can be used for
verification?":

    *"the presets are mostly created with ChromIQ layout engine, not
    printtarg. Also, each preset has all layout information, so the "Which
    presets can be used for verification" must layout that preset behind the
    scenes, if needed, so that the window can judge it."*

The two evenness rows need the PAGE a chart is printed on: how many strips and
rows each page has, and how much of the paper the patches cover
(`measurement_report.chart_grid`, §16). A `.ti1` carries neither. A preset
carries everything that decides them, and there are exactly two ways ChromIQ
lays a sheet out, so there are exactly two ways to answer:

* **the layout engine** (a preset with a layout recipe, which is most of the
  built-ins and every user preset saved with the engine on): its own
  arithmetic predicts the page without writing a file
  (`preset_eligibility._predicted_grid`). That is fast and has been in the
  window since beta 37; this module only makes sure every engine preset
  reaches it with its recipe, the user's own presets included.
* **printtarg** (a preset saved with the engine off): printtarg IS the layout,
  so it is run, on a copy of the preset's patch set in a temporary folder,
  with the argument list a Generate click would build
  (`chart_creator.printtarg_layout_argv`), and the `.ti2` and page images it
  writes are read by the report's own `chart_grid`. Nothing about the page is
  predicted, and nothing is written anywhere but that temporary folder, which
  is gone when the layout has been read.

**NEVER IN THE WINDOW'S OWN THREAD.** Running printtarg takes a subprocess and
measuring its page images takes a fraction of a second more, per preset. A
window listing 185 presets may not wait for that, so a printtarg layout is
queued to ONE background thread and the evenness rows read "being laid out"
until it is done (`REASON_LAYING_OUT`). The thread touches no Qt object: the
window asks :func:`generation` on a timer and re-reads what changed.

**CACHED BY THE PRESET'S CONTENT, NOT ITS NAME.** The key is the patch set's
bytes (hashed), the printtarg argument list and the printtarg binary's own
size and time, so a preset re-saved with the same patches and settings is not
laid out twice, a changed one is laid out again, and an Argyll upgrade lays
everything out again. The cache lives for the session.

No Qt in here.
"""
from __future__ import annotations

import atexit
import hashlib
import logging
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

#: The recipe key that marks a PRINTTARG layout spec, as opposed to a layout
#: engine recipe. `preset_eligibility` passes a preset's layout through one
#: ``recipe`` argument either way, and this key is how the two are told apart.
PRINTTARG_ARGV = "printtarg_argv"
ARGYLL_BIN = "argyll_bin"

#: The evenness rows of a printtarg preset whose layout is still being worked
#: out in the background. Transient: the window shows "working" and re-reads
#: the row when the layout arrives.
REASON_LAYING_OUT = "evenness_laying_out"
#: printtarg could not be found where Preferences says ArgyllCMS is.
REASON_LAYOUT_NO_TOOL = "evenness_layout_no_tool"
#: printtarg ran and refused the preset (its settings, or its patch set), or
#: did not finish. The reason's detail carries printtarg's own sentence.
REASON_LAYOUT_REFUSED = "evenness_layout_refused"

#: How long one printtarg layout may take. Measured idle on this host: 0.05 to
#: 0.4 s for the one-page presets, about 1.5 s for a 14-page one. Budgeted for
#: a loaded machine, as CLAUDE.md asks of every subprocess timeout.
PRINTTARG_TIMEOUT_S = 120

_LOCK = threading.Lock()
#: key -> the grid `chart_grid` read off the laid-out chart, or a failure
#: ``{"reason": ..., "detail": ...}``.
_RESULTS: "dict[tuple, dict]" = {}
#: keys queued or being laid out right now
_PENDING: "set[tuple]" = set()
#: bumped every time a layout finishes, so a window can poll one integer
_GENERATION = 0
#: seconds each finished layout took, for the timing the brief asks for
_TIMINGS: "dict[tuple, float]" = {}
_QUEUE: "queue.Queue[tuple | None]" = queue.Queue()
_WORKER: "threading.Thread | None" = None
_STOP = threading.Event()


# ---------------------------------------------------------------------------
# What a preset's layout IS
# ---------------------------------------------------------------------------
def is_printtarg_spec(recipe: "dict | None") -> bool:
    """Whether *recipe* is a printtarg layout spec rather than an engine
    recipe."""
    return isinstance(recipe, dict) and PRINTTARG_ARGV in recipe


def printtarg_spec(argv: "list[str]", argyll_bin: "str | Path") -> dict:
    """The spec :func:`grid_for` lays a printtarg preset out from."""
    return {PRINTTARG_ARGV: [str(a) for a in argv],
            ARGYLL_BIN: str(argyll_bin)}


def params_for_user_preset(data: dict, settings_get) -> "object":
    """A :class:`~workflow.chart_creator.ChartParams` for a Create Chart
    preset saved with the layout engine OFF, read the way the tab reads it.

    Only the fields that decide the PAGE: the ten printtarg rows
    `TabChart._collect_manual` maps by name, the two expert rows that move the
    capacity (`chart_creator._extra_printtarg_affects_layout`: -A and -n), the
    16-bit choice, triple density, and the two clip settings that force -L.
    A row the preset does not carry takes the value a fresh Create Chart tab
    shows, which is `ChartParams`' own default (the same numbers as
    `data/parameters.yaml`).
    """
    from workflow.chart_creator import ChartParams

    def get(flag: str, default):
        v = data.get(f"printtarg_{flag}")
        return default if v is None else v

    p = ChartParams(is_manual=True)
    p.instrument = str(get("-i", p.instrument))
    p.paper = str(get("-p", p.paper))
    p.tiff_dpi = int(get("-t", p.tiff_dpi) or p.tiff_dpi)
    p.tiff_16bit = bool(data.get("tiff_16bit", p.tiff_16bit))
    p.double_density = bool(get("-h", p.double_density))
    p.disable_left_border = bool(get("-L", p.disable_left_border))
    p.patch_scale = float(get("-a", p.patch_scale) or p.patch_scale)
    p.margin_mm = int(get("-m", p.margin_mm))
    p.no_randomise = bool(get("-r", p.no_randomise))
    p.bw_spacers = bool(get("-b", p.bw_spacers))
    p.no_strip_limit = bool(get("-P", p.no_strip_limit))
    p.triple_density = (bool(data.get("triple_density", False))
                        and p.instrument == "CM")
    extra: "list[str]" = []
    if data.get("printtarg_-A_enabled") and data.get("printtarg_-A") is not None:
        try:
            scale = float(data["printtarg_-A"])
        except (TypeError, ValueError):
            scale = 1.0
        p.spacer_scale = scale
        extra += ["-A", f"{scale:g}"]
    if bool(data.get("printtarg_-n", False)):
        p.no_spacers = True
        extra.append("-n")
    if extra:
        import shlex
        p.extra_printtarg_args = shlex.join(extra)
    p.left_clip_info = bool(data.get("left_clip_info", False))
    p.chromiq_clip_style = bool(settings_get("i1pro_chromiq_clip_style", False))
    return p


def layout_for_user_preset(data: "dict | None", settings_get) -> "dict | None":
    """The ``recipe`` argument `preset_eligibility` should judge a user
    preset with: its engine recipe, or a printtarg spec, or None.

    * saved with the engine on: the recipe it stores (``layout_recipe``),
      which is what loading it switches the engine on for;
    * an instrument only the engine can lay out (the CR30): the engine
      recipe Generate would build from the same fields;
    * anything else: printtarg, which is what Generate runs for it.
    """
    if not isinstance(data, dict):
        return None
    lr = data.get("layout_recipe")
    if isinstance(lr, dict) and lr:
        return dict(lr)
    from workflow.chart_creator import (ENGINE_ONLY_INSTRUMENTS,
                                        engine_build_kwargs,
                                        printtarg_layout_argv)
    try:
        params = params_for_user_preset(data, settings_get)
        if params.instrument in ENGINE_ONLY_INSTRUMENTS:
            from workflow.layout_engine.presets import LayoutRecipe
            kw = engine_build_kwargs(params)
            r = LayoutRecipe.from_build_kwargs(kw)
            r.instrument, r.paper = params.instrument, params.paper
            return r.to_dict()
        argv = printtarg_layout_argv(params)
    except (TypeError, ValueError) as exc:
        log.info("preset layout settings cannot be read: %s", exc)
        return None
    from core.platform_paths import default_argyll_bin_dir
    return printtarg_spec(argv, settings_get("argyll_bin_path",
                                             default_argyll_bin_dir()))


# ---------------------------------------------------------------------------
# The cache and the background thread
# ---------------------------------------------------------------------------
def _printtarg_binary(spec: dict) -> Path:
    from core.resource_path import argyll_binary
    return Path(spec.get(ARGYLL_BIN) or "") / argyll_binary("printtarg")


def layout_key(chart: Path, spec: dict) -> tuple:
    """What a printtarg layout depends on: the patch set's bytes, the
    arguments, and the printtarg binary itself."""
    try:
        digest = hashlib.sha1(Path(chart).read_bytes()).hexdigest()
    except OSError:
        digest = ""
    exe = _printtarg_binary(spec)
    try:
        st = exe.stat()
        tool = (str(exe), st.st_mtime_ns, st.st_size)
    except OSError:
        tool = (str(exe), 0, 0)
    return (digest, tuple(spec.get(PRINTTARG_ARGV) or ()), tool)


def generation() -> int:
    """A number that changes every time a background layout finishes."""
    return _GENERATION


def pending() -> int:
    """How many layouts and assessments are queued or running.

    Also gives automatic collection back once the background thread has
    ended (B8-1191, :func:`release_gc_if_idle`), so a caller that only polls
    this, with no presets window and no timer, still gets it back."""
    release_gc_if_idle()
    with _LOCK:
        return len(_PENDING) + len(_REQUESTED)


def seconds_taken(chart: Path, spec: dict) -> "float | None":
    """How long the finished layout of this chart and spec took, or None."""
    with _LOCK:
        return _TIMINGS.get(layout_key(chart, spec))


def state(chart: Path, spec: dict) -> tuple:
    """``("done", key)`` once this layout is known, else ``("pending", key)``.
    Part of `preset_eligibility`'s cache key, so an answer given while the
    layout was being worked out is never served after it arrives."""
    key = layout_key(chart, spec)
    with _LOCK:
        return ("done" if key in _RESULTS else "pending", key)


def grid_for(chart: "str | Path", spec: dict, *, wait: bool = False) -> dict:
    """The page grid of *chart* laid out by printtarg under *spec*.

    Known already: returned. Otherwise, with *wait*, laid out here and now
    (scripts, tests, a background thread); without it, queued to the
    background thread and ``{"reason": REASON_LAYING_OUT}`` returned at once.
    Never raises.
    """
    global _GENERATION
    chart = Path(chart)
    key = layout_key(chart, spec)
    with _LOCK:
        hit = _RESULTS.get(key)
    if hit is not None:
        return hit
    if not wait:
        _schedule(key, chart, spec)
        return {"reason": REASON_LAYING_OUT}
    t0 = time.monotonic()
    res = lay_out_with_printtarg(chart, spec)
    with _LOCK:
        _RESULTS[key] = res
        _TIMINGS[key] = time.monotonic() - t0
        _PENDING.discard(key)
        _GENERATION += 1
    return res


def _schedule(key: tuple, chart: Path, spec: dict) -> None:
    with _LOCK:
        if key in _PENDING or key in _RESULTS:
            return
        _PENDING.add(key)
        # queued under the lock, so a thread deciding to retire (which it
        # does under the same lock, on an empty queue) cannot miss it
        _start_worker()
        _QUEUE.put(("layout", chart, dict(spec), None))
    _held_by_caller()


#: Every background thread started and not yet known to have ended
#: (B8-1191). Normally one; two only for the moment a retiring thread is
#: still unwinding while its successor has started.
_THREADS: "list[threading.Thread]" = []


#: Called on the main thread whenever work is handed over, so the GUI can
#: start the timer that collects while collection is held and gives it back
#: once the thread has ended (B8-1191). Set by the presets window's module;
#: this module stays free of Qt.
_HOLD_LISTENER = None


def set_hold_listener(callback) -> None:
    """Register what the main thread calls when it hands the background
    thread work (the presets window module's collector timer)."""
    global _HOLD_LISTENER
    _HOLD_LISTENER = callback


def _held_by_caller() -> None:
    cb = _HOLD_LISTENER
    if cb is None or threading.current_thread() is not threading.main_thread():
        return
    try:
        cb()
    except Exception as exc:      # noqa: BLE001 - never fatal to a request
        log.debug("the collector timer could not be started: %s", exc)


def _start_worker() -> None:
    """Called with `_LOCK` held, by whoever hands the thread work.

    Collection is switched off BEFORE the thread exists (B8-1191), so the
    thread never runs a line of Python with it on."""
    global _WORKER
    _hold_gc_locked()
    _THREADS[:] = [t for t in _THREADS if t.is_alive()]
    _RETIRING.intersection_update(_THREADS)
    if (_WORKER is None or not _WORKER.is_alive()
            or _WORKER in _RETIRING):
        _STOP.clear()
        _WORKER = threading.Thread(target=_work, name="chromiq-preset-layout",
                                   daemon=True)
        _THREADS.append(_WORKER)
        _WORKER.start()


#: Whole assessments queued to the same thread (see :func:`request`), by the
#: caller's own key, so one is never queued twice.
_REQUESTED: "set[tuple]" = set()


def request(key: tuple, work) -> None:
    """Run ``work()`` on the background thread, once per *key* until it has
    run. The presets window hands it the part of a preset's assessment its
    own thread may not wait for (`preset_eligibility.request_values`); what
    *work* computes lands in the caller's own cache, and :func:`generation`
    moves when it is done."""
    with _LOCK:
        if key in _REQUESTED:
            return
        _REQUESTED.add(key)
        _FINISHED.discard(key)
        _start_worker()
        _QUEUE.put(("call", None, None, (key, work)))
    _held_by_caller()


#: Keys of :func:`request` jobs that have run (B8-1161), so a window can ask
#: "has mine finished?" with a set lookup instead of re-reading every waiting
#: chart's files on each poll. Cleared for a key when it is requested again.
_FINISHED: "set[tuple]" = set()


def queued(key: tuple) -> bool:
    """Whether the :func:`request` job for *key* is waiting or running."""
    with _LOCK:
        return key in _REQUESTED


def finished(key: tuple) -> bool:
    """Whether the :func:`request` job for *key* has run since it was last
    requested."""
    with _LOCK:
        return key in _FINISHED


#: The interpreter's switch interval while this thread has work (B8-1161).
#: **THE WINDOW'S THREAD WAITS FOR THE GIL, AND 5 MS A TIME ADDS UP.**
#: Measured on screen with a 50 ms heartbeat: with this thread busy, the
#: window's own thread stalled up to 1.8 s reopening the presets window, all
#: of it in `stat`, `realpath` and Qt calling back into Python. Each of those
#: gives the GIL away, and CPython then lets this thread keep it for the
#: whole switch interval (5 ms by default) before handing it back. At 1 ms
#: the window gets it back five times sooner; the interval is put back when
#: the queue has been empty for half a second.
BUSY_SWITCH_INTERVAL_S = 0.001


# ---------------------------------------------------------------------------
# The garbage collector never runs on this thread (B8-1161, B8-1191)
# ---------------------------------------------------------------------------
#
# **A COLLECTION ON THIS THREAD CAN DESTROY A QT WIDGET OFF THE GUI THREAD.**
# Python collects on whichever thread allocates past the threshold, and this
# thread allocates a great deal (page images, numpy, the layout engine). A
# collection that finds a closed dialog in a reference cycle finalises it
# right here, while the GUI thread may be dispatching an event to it: the
# everyday tier lost a worker to exactly that (SIGSEGV in
# `QCoreApplicationPrivate::sendThroughObjectEventFilters` from a timer, with
# this thread in `PIL.Image.copy`). `core/sound.py` records the same crash
# class for an import.
#
# **AND "WHILE IT HAS WORK" WAS NOT ENOUGH (B8-1191).** B8-1161 switched
# collection off while this thread had a job and let the thread itself switch
# it back on after 5 s idle. That hand-back was the hole: while collection is
# off the GUI thread goes on allocating, so the count is far past the
# threshold, and the very next allocation after `gc.enable()` collects. The
# next allocation was THIS thread's own, in its idle loop, microseconds later.
# Measured: 5 of 5 runs of a script collected on this thread at that moment,
# and one everyday-tier run collected 2,024 objects here during a test that
# builds a Create Chart tab. The beta 43 gate then lost a worker to the same
# SIGSEGV with this thread idle in `queue.get`, which is where a hand-back
# leaves it.
#
# So the rule is now about the thread's WHOLE LIFE, not its jobs:
#
# * collection is switched off by whoever hands the thread work, before the
#   thread is started (`_start_worker`), so it never runs a line with it on;
# * the thread never switches it back on. It ENDS when it has been idle for
#   `_IDLE_EXIT_S`, and only a thread that is not this one gives collection
#   back, and only once no background thread is alive any more
#   (:func:`release_gc_if_idle`: the presets window's timer, every
#   :func:`pending` call, and the test suite between tests);
# * while it is off, the GUI thread collects the youngest generation itself
#   (:func:`collect_on_gui_thread`, on the presets window module's timer).

_GC_HELD = False
#: whether collection was on when the hold began, so a hold never switches
#: on a collector that somebody else had switched off
_GC_WAS_ENABLED = True
#: how long the thread waits for more work before it ends (B8-1191)
_IDLE_EXIT_S = 1.0
#: threads that have decided to end (under `_LOCK`) and are unwinding
_RETIRING: "set[threading.Thread]" = set()


def _hold_gc_locked() -> None:
    """Switch automatic collection off for as long as a background thread
    lives. Called with `_LOCK` held, never on the background thread."""
    global _GC_HELD, _GC_WAS_ENABLED
    import gc
    if not _GC_HELD:
        _GC_WAS_ENABLED = gc.isenabled()
        _GC_HELD = True
    gc.disable()


def _on_a_background_thread() -> bool:
    return threading.current_thread() in _THREADS


def release_gc_if_idle() -> bool:
    """Give automatic collection back if it is held and no background thread
    is alive any more. Never does anything on the background thread itself,
    whose own next allocation would otherwise be the one that collects.
    True when collection is not held (any more)."""
    global _GC_HELD
    import gc
    if not _GC_HELD:
        return True
    if _on_a_background_thread():
        return False
    with _LOCK:
        if not _GC_HELD:
            return True
        _THREADS[:] = [t for t in _THREADS if t.is_alive()]
        if _THREADS or not _QUEUE.empty():
            return False
        _RETIRING.clear()
        _GC_HELD = False
        if _GC_WAS_ENABLED:
            gc.enable()
        return True


def gc_held() -> bool:
    """Whether automatic collection is off because a background thread is
    alive."""
    return _GC_HELD


def collect_on_gui_thread() -> bool:
    """Call on the GUI thread, on a timer, while :func:`gc_held`: collects
    the youngest generation there, and gives automatic collection back once
    no background thread is alive. True when it has been given back (the
    timer may stop)."""
    import gc
    if release_gc_if_idle():
        return True
    gc.collect(0)
    return False


def _retire_if_idle(me: threading.Thread) -> bool:
    """On the background thread: end it if nothing is queued. Decided under
    `_LOCK`, which is also held while work is queued, so a job can never be
    left in the queue with no thread to run it."""
    global _WORKER
    with _LOCK:
        if not _QUEUE.empty():
            return False
        _RETIRING.add(me)
        if _WORKER is me:
            _WORKER = None
        return True


def _work() -> None:
    global _WORKER
    import gc
    import sys
    me = threading.current_thread()
    restore: "float | None" = None
    idle_since: "float | None" = None
    try:
        while not _STOP.is_set():
            try:
                job = _QUEUE.get(timeout=0.25)
            except queue.Empty:
                if restore is not None:
                    sys.setswitchinterval(restore)
                    restore = None
                now = time.monotonic()
                idle_since = idle_since or now
                if now - idle_since >= _IDLE_EXIT_S and _retire_if_idle(me):
                    return
                continue
            idle_since = None
            if job is None:
                return
            if _GC_HELD and gc.isenabled():
                # somebody switched it back on while this thread lives (an
                # import guard that restores what it found): off again
                gc.disable()
            if restore is None:
                restore = sys.getswitchinterval()
                sys.setswitchinterval(min(restore, BUSY_SWITCH_INTERVAL_S))
            _wait_while_held()
            _run_job(job)
            # the job's objects are released here, with collection still off
            job = None
    finally:
        if restore is not None:
            sys.setswitchinterval(restore)
        with _LOCK:
            _RETIRING.add(me)
            if _WORKER is me:
                _WORKER = None
        # collection is NOT given back here: see the note above


_HOLD_UNTIL = 0.0


def hold(seconds: float) -> None:
    """Start no new job for *seconds* (B8-1161).

    For the moment the presets window is being built and shown: that is work
    on the window's thread that calls into Python thousands of times, and
    every one of those calls waits for the GIL while this thread holds it.
    Measured on screen, a reopen took 0.3 to 0.8 s with this thread busy and
    0.18 s with it idle. A job already running finishes; the next one waits.
    """
    global _HOLD_UNTIL
    _HOLD_UNTIL = max(_HOLD_UNTIL, time.monotonic() + float(seconds))


def _wait_while_held() -> None:
    while not _STOP.is_set():
        left = _HOLD_UNTIL - time.monotonic()
        if left <= 0:
            return
        time.sleep(min(left, 0.05))


def _run_job(job: tuple) -> None:
    global _GENERATION
    kind, chart, spec, call = job
    if kind == "call":
        key, work = call
        try:
            work()
        except Exception as exc:      # noqa: BLE001 - one preset only
            log.info("checking a preset behind the scenes failed: %s", exc)
        with _LOCK:
            _REQUESTED.discard(key)
            _FINISHED.add(key)
            _GENERATION += 1
        return
    try:
        grid_for(chart, spec, wait=True)
    except Exception as exc:      # noqa: BLE001 - one preset is never fatal
        log.warning("laying %s out behind the scenes failed: %s", chart, exc)
        with _LOCK:
            _RESULTS[layout_key(chart, spec)] = {
                "reason": REASON_LAYOUT_REFUSED, "detail": str(exc)}
            _PENDING.discard(layout_key(chart, spec))
            _GENERATION += 1


def _stop_worker(timeout: float = 5.0) -> bool:
    """End the background thread and give collection back (B8-1191). A job
    that is running finishes and removes its folder, rather than leave a
    temporary folder behind; jobs still queued are dropped and may be asked
    for again. Never on the background thread. True when collection is back
    (or was never held)."""
    if _on_a_background_thread():
        return False
    _STOP.set()
    with _LOCK:
        threads = list(_THREADS)
    _QUEUE.put(None)            # wakes a thread waiting for work
    end = time.monotonic() + max(0.0, float(timeout))
    for t in threads:
        if t.is_alive():
            t.join(timeout=max(0.0, end - time.monotonic()))
    dropped = []
    while True:
        try:
            dropped.append(_QUEUE.get_nowait())
        except queue.Empty:
            break
    with _LOCK:
        for job in dropped:
            if not job:
                continue
            kind, chart, spec, call = job
            if kind == "call":
                _REQUESTED.discard(call[0])
            else:
                try:
                    _PENDING.discard(layout_key(chart, spec))
                except Exception:      # noqa: BLE001 - a key is a key
                    pass
    return release_gc_if_idle()


def settle(timeout: float = 30.0) -> bool:
    """Let the queued work finish, then end the background thread and give
    automatic collection back (B8-1191). For the test suite between tests,
    and for anything else that needs the process back in its ordinary state.
    True when all of that happened within *timeout*."""
    if _on_a_background_thread():
        return False
    end = time.monotonic() + max(0.0, float(timeout))
    while pending() and time.monotonic() < end:
        time.sleep(0.01)
    finished_in_time = not pending()
    return _stop_worker(max(0.5, end - time.monotonic())) and finished_in_time


atexit.register(_stop_worker)


def clear_cache() -> None:
    """Forget every layout (the tests)."""
    global _GENERATION
    with _LOCK:
        _RESULTS.clear()
        _TIMINGS.clear()
        _REQUESTED.clear()
        _FINISHED.clear()
        _GENERATION += 1


# ---------------------------------------------------------------------------
# Laying it out
# ---------------------------------------------------------------------------
def lay_out_with_printtarg(chart: Path, spec: dict) -> dict:
    """Run printtarg on a copy of *chart* in a temporary folder and read the
    page grid off what it wrote, with the report's own `chart_grid`.

    Returns that grid (``pages``, ``rows``, ``slot`` … and the page
    ``coverage``), with ``laid_out_by`` and ``pages_laid_out`` added, or
    ``{"reason": REASON_LAYOUT_NO_TOOL | REASON_LAYOUT_REFUSED, "detail":
    str}``. The folder is removed before this returns, whatever happened.

    **What this does NOT reproduce, on purpose:** ChromIQ's own
    post-processing of a printtarg page (the stamped notes, and on an i1Pro
    with the ChromIQ clip style the clip band painted in after the patches
    are moved right). None of it changes a page's strips or rows; the clip
    band moves the patch block sideways without changing its size, which is
    what the coverage is computed from.
    """
    from workflow import measurement_report as MR
    exe = _printtarg_binary(spec)
    if not exe.is_file():
        return {"reason": REASON_LAYOUT_NO_TOOL, "detail": str(exe.parent)}
    argv = [str(a) for a in spec.get(PRINTTARG_ARGV) or ()]
    with tempfile.TemporaryDirectory(prefix="chromiq-preset-layout-") as tmp:
        folder = Path(tmp)
        try:
            shutil.copyfile(chart, folder / "chart.ti1")
        except OSError as exc:
            return {"reason": REASON_LAYOUT_REFUSED, "detail": str(exc)}
        try:
            r = subprocess.run([str(exe), *argv, "chart"], cwd=str(folder),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", stdin=subprocess.DEVNULL,
                               timeout=PRINTTARG_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return {"reason": REASON_LAYOUT_REFUSED,
                    "detail": f"printtarg did not finish within "
                              f"{PRINTTARG_TIMEOUT_S} s"}
        except OSError as exc:
            return {"reason": REASON_LAYOUT_NO_TOOL, "detail": str(exc)}
        ti2 = folder / "chart.ti2"
        if r.returncode != 0 or not ti2.is_file():
            return {"reason": REASON_LAYOUT_REFUSED,
                    "detail": refusal_sentence((r.stdout or "") + "\n"
                                               + (r.stderr or ""))}
        grid = dict(MR.chart_grid(ti2))
        grid["laid_out_by"] = "printtarg"
        grid["pages_laid_out"] = len(list(folder.glob("chart*.tif")))
        return grid


def refusal_sentence(output: str) -> str:
    """printtarg's own one line out of its output (`chart_creator.
    printtarg_said`, the line a Generate click logs). Its words, quoted by the
    window as printtarg's: ChromIQ's longer explanation of a refusal is a
    Generate window's, with buttons to go with it, and too long for a line in
    a list."""
    from workflow.chart_creator import printtarg_said
    return printtarg_said(output) or "printtarg wrote no chart"
