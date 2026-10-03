"""A worker QThread gets a stack big enough for numpy's linear algebra.

Knut, #182 5956290893 (4.3.3-beta.3, macOS 14.8.5, Apple Silicon): Build
Profile with Engine v2 died with "Fatal Python error: Bus error" in
``numpy.linalg.solve``; the crash report shows ``KERN_PROTECTION_FAILURE`` on
the guard page of ``_EngineThread``'s stack, inside OpenBLAS's
``dgetrf_parallel``. A QThread on macOS gets a 512 KiB stack by default (a
Python ``threading.Thread`` gets 16 MiB), and OpenBLAS's parallel LU keeps
per-thread work tables on the caller's stack. Apple's Accelerate, which the
arm64 numpy used until 4.3.3-beta.1, did not, so the stack never ran out.

Measured with the numpy ChromIQ ships (2.4.4, macosx_11_0_arm64 wheel,
scipy-openblas 0.3.31): ``np.linalg.solve`` on a QThread with the default stack
dies at 128 x 128; with 32 MiB it solves 1024 x 1024. The Intel half has always
used OpenBLAS, so it was exposed before too.

32 MiB is address space, not memory: only the pages a thread touches are ever
backed. Every QThread the app starts goes through :func:`roomy`.
"""
from __future__ import annotations

#: Stack size for every worker QThread (bytes).
WORKER_STACK_BYTES = 32 * 1024 * 1024


def roomy(thread):
    """Give *thread* (a QThread, not yet started) :data:`WORKER_STACK_BYTES`
    of stack, and return it."""
    thread.setStackSize(WORKER_STACK_BYTES)
    return thread
