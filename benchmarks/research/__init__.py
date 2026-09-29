"""Research benchmark (Agent 6, 2026-09-29): dev-only, never shipped.

One command reproduces a full run::

    python -m benchmarks.research.run --out <dir>

See ``run.py`` for the options and the Desktop ``Benchmarks/README.md`` for
the method. Everything here judges profile BYTES through real CMMs (Argyll
xicclu and littleCMS), against ground truth computed at 1 nm independently
of the engine's own spectral code.
"""
