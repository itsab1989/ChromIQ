"""A PROJECT NAME IS A NAME, NOT A FILENAME.

ChromIQ uses the project name verbatim as the file *stem* of every artefact a
run owns — ``<name>.ti1``, ``<name>.ti2``, ``<name>.ti3``, ``<name>.icc``,
``<name>_01.tif`` — because the ArgyllCMS tools are stem-and-cwd coupled and
because the name is what gets printed on the sheet.

A project name may legitimately contain a dot. ChromIQ's own built-in presets
suggest names that do: ``ColorMunki-A4-204p-1page-Portrait-w10.0mm``,
``A4-1160p-2pages-TC9.18-extended-greys-by-Pharmacist``. ``pathlib`` has no way
to know those are names rather than filenames, so it reads the tail as a file
extension::

    Path("X-w10.0mm").suffix              == ".0mm"
    Path("X-w10.0mm").stem                == "X-w10"
    Path("X-w10.0mm").with_suffix(".ti2") == "X-w10.ti2"     # 4 characters gone

Every one of those is silent. The file is written, under a name nothing looks
for, and the failure surfaces much later as "the chart has no measurement" or
"there is no scanner target" — never as an error about a name.

So: **derive artefact paths by concatenation, never through with_suffix()**,
which is what ``core.file_manager.Run`` has always done
(``self.dir / f"{self.stem}.ti2"``). This module is that rule, in one place, for
the code that does not have a ``Run`` to hand.

There is deliberately **no** "strip whatever extension this looks like" helper.
That is the operation that cannot be done safely — it has to guess, and every
guess list is wrong for some legal project name. Where a caller genuinely has a
path with a known extension, :func:`without_ext` removes exactly that one.
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["artefact", "without_ext"]


def artefact(stem: "str | Path", ext: str) -> Path:
    """``<stem><ext>`` — the artefact belonging to *stem*, by concatenation.

    *ext* includes its leading dot and may be compound (``".strips.json"``).
    Never touches anything already in *stem*::

        artefact("runs/run1/X-w10.0mm", ".ti2")  ->  runs/run1/X-w10.0mm.ti2

    Use this everywhere ``<stem>.with_suffix(ext)`` would otherwise appear.
    """
    p = Path(stem)
    return p.parent / (p.name + ext)


def without_ext(path: "str | Path", ext: str) -> Path:
    """*path* with a **known** trailing *ext* removed — by string, not by guess.

    The inverse of :func:`artefact`, for the one safe case: the caller knows
    which extension is there. A path that does not end in *ext* is returned
    unchanged, so this can be used defensively::

        without_ext("X-w10.0mm.ti3", ".ti3")  ->  X-w10.0mm
        without_ext("X-w10.0mm",     ".ti3")  ->  X-w10.0mm     (not X-w10)

    Compare ``Path("X-w10.0mm").with_suffix("")``, which gives ``X-w10``.
    """
    p = Path(path)
    if ext and p.name.lower().endswith(ext.lower()):
        return p.parent / p.name[: -len(ext)]
    return p
