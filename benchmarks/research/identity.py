"""The Fast / Bit-exact identity reference, and the measured upstream column.

Decision D-02, answer 2 (Basti, 2026-10-03): the byte-identity reference for
Fast (``gammap_mode = "fast"``) and Bit-exact (``"argyll"``) is the research
branch's OWN Fast / Bit-exact, frozen at a commit, so the September round's
correctness fixes in both modes (paper white pinned, a neutral L*=0) stay.
Master's Fast / Bit-exact is NOT dropped: it is built as a separate,
non-gating column and its difference is measured, never hidden.

* :data:`IDENTITY_REF` is that frozen commit: the merge of origin/master
  fdcdd76f into research/profile-engine (2026-10-03), whose ``--runslow``
  gate is ``Validation/gate-02-merge-<sha>.txt``. Re-freezing it is a
  decision record of its own (D-02: each correctness fix in Fast / Bit-exact
  re-freezes the reference afterwards).
* :data:`UPSTREAM_REF` is the ref the measured upstream column is built from.

``python -m benchmarks.research.run --suite baseline`` uses both: the
identity check (exit 2 on any difference) against ``--identity-ref``
(default :data:`IDENTITY_REF`), and the upstream column against
``--upstream-ref`` (default :data:`UPSTREAM_REF`; empty to skip).
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

IDENTITY_REF = "8212236520f2f331d2b3461db83852fd85ce55a3"
UPSTREAM_REF = "origin/master"


def tag_table(path: Path | str) -> dict[str, bytes]:
    """Tag signature -> the tag's bytes, read from the ICC tag table."""
    data = Path(path).read_bytes()
    (count,) = struct.unpack(">I", data[128:132])
    tags = {}
    for i in range(count):
        sig, off, size = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        tags[sig.decode("latin-1")] = data[off:off + size]
    return tags


def differing_tags(a: Path | str, b: Path | str) -> dict:
    """Which tags differ between two profiles, and whether the header does
    (bytes 0-127 minus the profile ID, which is a hash of the rest)."""
    ta, tb = tag_table(a), tag_table(b)
    da, db = Path(a).read_bytes(), Path(b).read_bytes()
    hdr = lambda d: d[:84] + d[100:128]  # noqa: E731 - bytes 84-99 = profile ID
    return {"tags": sorted(k for k in set(ta) | set(tb) if ta.get(k) != tb.get(k)),
            "header_identical": hdr(da) == hdr(db),
            "identical": da == db}


def _lab_points(n: int, seed: int = 11) -> np.ndarray:
    from benchmarks.synthetic import halton
    h = halton(n, 3, seed)
    return np.column_stack([100.0 * h[:, 0], 160.0 * h[:, 1] - 80.0,
                            160.0 * h[:, 2] - 80.0])


def measure_difference(a: Path | str, b: Path | str, n_channels: int,
                       additive: bool, tac: float | None,
                       reader: str = "argyll", n: int = 5000) -> dict:
    """How far profile *b* is from profile *a*, read through one CMM.

    A2B: dE00 between the two tables at *n* TAC-respecting quasi-random
    device points. B2A: the largest per-channel device difference (0-1) at
    *n* quasi-random Lab points (L* 0-100, a*/b* -80..80, the same points
    for both), plus what each puts into paper white (Lab 100,0,0) and asks
    for black (Lab 0,0,0)."""
    from benchmarks.research import cmm, colour, metrics
    out = differing_tags(a, b)
    dev = metrics.eval_device(n_channels, additive, tac, n)
    de = colour.de2000(cmm.a2b(a, dev, reader), cmm.a2b(b, dev, reader))
    lab = _lab_points(n)
    dd = np.abs(cmm.b2a(a, lab, reader) - cmm.b2a(b, lab, reader)).max(axis=1)
    pick = lambda x: {"median": float(np.median(x)),  # noqa: E731
                      "p95": float(np.percentile(x, 95)), "max": float(x.max())}
    corners = np.array([[100.0, 0, 0], [0.0, 0, 0]])
    ca, cb = cmm.b2a(a, corners, reader), cmm.b2a(b, corners, reader)
    out.update({"reader": reader, "points": n,
                "a2b_de00": pick(de), "b2a_device_maxch": pick(dd),
                "white_a": ca[0].round(4).tolist(), "white_b": cb[0].round(4).tolist(),
                "black_a": ca[1].round(4).tolist(), "black_b": cb[1].round(4).tolist()})
    return out
