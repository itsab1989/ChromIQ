"""numpy's OpenBLAS runs on ONE thread, so no fork can ever wait on it.

Knut, #182 6144104040 / 6144197668 / 6144276261 (4.3.5-beta.2, macOS 14.8.9,
Mac14,6): ChromIQ hung for good, force quit needed, after switching the run
type from profiling to verification or switching runs in verification. The
hang report: the window's thread was starting a subprocess, and inside
``fork()`` OpenBLAS's own fork handler (``blas_thread_shutdown_``) waited for
ever on one of its eleven pool threads, while a background Python thread
(the gamut reach beta 2 asks as soon as a verification run with a profile is
chosen) sat in a numpy matrix product. Any fork while another thread uses
OpenBLAS can do that; beta 2 only made it frequent, because it started that
work exactly when the window starts its xicclu preview processes. The engine
build's QThread and every other numpy worker were exposed before.

Reproduced with the numpy ChromIQ ships on macOS (2.4.4, macosx_11_0_arm64
wheel, scipy-openblas): a thread doing ``a @ b`` while the main thread runs
``/usr/bin/true`` in a loop hung 5 runs in 5, within seconds, with exactly
that stack. With ``OPENBLAS_NUM_THREADS=1`` there is no pool to shut down and
the same stress never hung.

The setting only counts before numpy loads OpenBLAS, so :func:`pin_blas_threads`
is the first thing ``main.py`` does, and the frozen apps also run it from a
PyInstaller runtime hook (``hooks/rth_blas_threads.py``), which runs before
``main.py``. Standard library only: it must be importable before anything.
"""
from __future__ import annotations

import os
import sys

#: The variables OpenBLAS reads for its thread count, all pinned to one.
#: ``OPENBLAS_NUM_THREADS`` is the one scipy-openblas reads first;
#: ``GOTO_NUM_THREADS`` is its older spelling. ``OMP_NUM_THREADS`` is left
#: alone: the wheels' OpenBLAS is built with pthreads, not OpenMP.
PINNED = {"OPENBLAS_NUM_THREADS": "1", "GOTO_NUM_THREADS": "1"}


def pin_blas_threads() -> bool:
    """Pin OpenBLAS to one thread. Overrides a value already in the
    environment, because any other value brings the hang back. Returns False
    when numpy is already imported, which means it came too late."""
    for name, value in PINNED.items():
        os.environ[name] = value
    return "numpy" not in sys.modules


def _loaded_openblas_paths() -> "list[str]":
    """Paths of the OpenBLAS libraries this process has loaded."""
    found: "list[str]" = []
    if sys.platform == "darwin":
        import ctypes
        libc = ctypes.CDLL(None)
        libc._dyld_image_count.restype = ctypes.c_uint32
        libc._dyld_get_image_name.restype = ctypes.c_char_p
        libc._dyld_get_image_name.argtypes = [ctypes.c_uint32]
        for i in range(libc._dyld_image_count()):
            name = libc._dyld_get_image_name(i)
            if name and b"openblas" in name.lower():
                found.append(name.decode())
    elif sys.platform.startswith("linux"):
        try:
            with open("/proc/self/maps", encoding="utf-8") as fh:
                for line in fh:
                    path = line.rstrip("\n").split(" ")[-1]
                    if "openblas" in path.lower() and path not in found:
                        found.append(path)
        except OSError:
            pass
    return found


def blas_thread_count() -> "int | None":
    """How many threads the loaded OpenBLAS uses, or None when no OpenBLAS
    is loaded (Apple's Accelerate) or it cannot be asked (Windows, which has
    no fork and so no hang). Call after ``import numpy``."""
    import ctypes
    for path in _loaded_openblas_paths():
        try:
            lib = ctypes.CDLL(path)
        except OSError:
            continue
        for sym in ("scipy_openblas_get_num_threads64_",
                    "scipy_openblas_get_num_threads",
                    "openblas_get_num_threads64_",
                    "openblas_get_num_threads"):
            fn = getattr(lib, sym, None)
            if fn is not None:
                fn.restype = ctypes.c_int
                return int(fn())
    return None
