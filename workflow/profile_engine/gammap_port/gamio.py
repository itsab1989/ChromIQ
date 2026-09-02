"""Argyll ``.gam`` gamut file reader (CGATS GAMUT format).

Provides the port with byte-identical inputs to Argyll's own tools: the
vertex list plus the header's white/black points and the six cusps exactly
as ``gamut->getcusps``/``getwb`` return them — removing every cloud-derived
approximation from the comparison chain.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from core.text_io import read_text


@dataclass
class GamFile:
    vertices: np.ndarray            # (N, 3) Lab
    triangles: np.ndarray | None    # (M, 3) vertex indexes (may be None)
    white: np.ndarray
    black: np.ndarray
    cs_white: np.ndarray            # colorspace white/black (header CSPACE_*)
    cs_black: np.ndarray
    cusps: np.ndarray               # (6, 3) R Y G C B M


def read_gam(path: Path | str) -> GamFile:
    text = read_text(Path(path), lenient=True)

    def vec(key: str) -> np.ndarray:
        m = re.search(rf'^{key}\s+"([^"]+)"', text, re.M)
        return np.array([float(v) for v in m.group(1).split()])

    white = vec("GAMUT_WHITE")
    black = vec("GAMUT_BLACK")
    cs_white = vec("CSPACE_WHITE")
    cs_black = vec("CSPACE_BLACK")
    cusps = np.stack([vec(f"CUSP_{n}") for n in
                      ("RED", "YELLOW", "GREEN", "CYAN", "BLUE", "MAGENTA")])

    blocks = re.findall(r"BEGIN_DATA\s*\n(.*?)\nEND_DATA", text, re.S)
    rows0 = [ln.split() for ln in blocks[0].splitlines() if ln.strip()]
    vertices = np.array([[float(r[1]), float(r[2]), float(r[3])]
                         for r in rows0])
    triangles = None
    if len(blocks) > 1:
        rows1 = [ln.split() for ln in blocks[1].splitlines() if ln.strip()]
        if rows1 and len(rows1[0]) >= 3:
            triangles = np.array([[int(r[0]), int(r[1]), int(r[2])]
                                  for r in rows1])
    return GamFile(vertices=vertices, triangles=triangles, white=white,
                   black=black, cs_white=cs_white, cs_black=cs_black,
                   cusps=cusps)
