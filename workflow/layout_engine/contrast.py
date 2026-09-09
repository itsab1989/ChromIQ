"""Inter-patch contrast: spacer colour choice + a readability guard.

A strip reader finds patch boundaries by the contrast between a patch and the
spacer beside it (printtarg runs a whole anneal for this).  ChromIQ owns the
order, so at minimum it picks each spacer's colour to maximise the *minimum*
contrast to its two neighbouring patches, and can flag passes whose neighbours
are too similar.
"""
from __future__ import annotations

from .colorants import luminance

# Below this min patch↔spacer luminance gap a boundary may be hard to detect.
LOW_CONTRAST_THRESHOLD = 32.0


def spacer_rgb(above: tuple[int, int, int] | None,
               below: tuple[int, int, int] | None) -> tuple[int, int, int]:
    """Black or white spacer maximising the minimum contrast to its neighbours."""
    neigh = [n for n in (above, below) if n is not None]
    if not neigh:
        return (0, 0, 0)
    lums = [luminance(n) for n in neigh]
    # contrast to black = lum; to white = 255 - lum. Maximise the worst case.
    worst_black = min(lums)
    worst_white = min(255.0 - l for l in lums)
    return (0, 0, 0) if worst_black >= worst_white else (255, 255, 255)


# Candidate spacer colours for "coloured" mode: black/white plus saturated
# primaries/secondaries — printtarg uses coloured spacers so the patch↔spacer
# density contrast is guaranteed even between two ~50%-density patches.
_COLOURED_PALETTE = [
    (0, 0, 0), (255, 255, 255),
    (255, 0, 0), (0, 255, 0), (0, 0, 255),
    (0, 255, 255), (255, 0, 255), (255, 255, 0),
]


def _rgb_dist(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def colored_spacer_rgb(above: tuple[int, int, int] | None,
                       below: tuple[int, int, int] | None,
                       palette: "list[tuple[int, int, int]] | None" = None
                       ) -> tuple[int, int, int]:
    """A coloured spacer maximising the minimum RGB distance to both neighbours.

    Picks from *palette* (default: black/white/primary/secondary) the colour
    whose *worst-case* distance to the two neighbouring patches is largest, so
    the boundary is always detectable (printtarg's coloured-spacer guarantee).
    Pass a custom *palette* to draw spacers from a user-chosen colour set.
    """
    pal = palette or _COLOURED_PALETTE
    neigh = [n for n in (above, below) if n is not None]
    if not neigh:
        return pal[0]
    best, best_score = pal[0], -1.0
    for cand in pal:
        score = min(_rgb_dist(cand, n) for n in neigh)
        if score > best_score:
            best, best_score = cand, score
    return best


def spacer_for_mode(mode: str, above, below,
                    palette: "list[tuple[int, int, int]] | None" = None
                    ) -> tuple[int, int, int]:
    """Spacer colour for *mode* ("colored" | "bw"); *palette* customises colored."""
    return colored_spacer_rgb(above, below, palette) if mode == "colored" \
        else spacer_rgb(above, below)


def ring_for_mode(mode: str, neighbours: "list[tuple[int, int, int]]",
                  palette: "list[tuple[int, int, int]] | None" = None
                  ) -> tuple[int, int, int]:
    """Spacer colour for a RING drawn around one hexagon (#159).

    A bar sits between exactly two patches, so `spacer_for_mode` asks for two
    colours and maximises the worst of the two. A ring sits between one patch
    and up to SIX, and the honest generalisation is the same rule over the whole
    set: pick the colour whose WORST-case contrast, against the patch itself and
    against every neighbour it touches, is largest.

    That is not an extension of the pair logic so much as the pair logic finally
    written down: both `spacer_rgb` and `colored_spacer_rgb` already reduce their
    two arguments to a list and score candidates by `min(...)` over it, so they
    generalise with no change of meaning. This function only removes the
    assumption that the list has two entries in it.
    """
    neigh = [n for n in neighbours if n is not None]
    if not neigh:
        return (0, 0, 0) if mode != "colored" else (palette or _COLOURED_PALETTE)[0]
    if mode == "colored":
        pal = palette or _COLOURED_PALETTE
        best, best_score = pal[0], -1.0
        for cand in pal:
            score = min(_rgb_dist(cand, n) for n in neigh)
            if score > best_score:
                best, best_score = cand, score
        return best
    lums = [luminance(n) for n in neigh]
    return (0, 0, 0) if min(lums) >= min(255.0 - l for l in lums) \
        else (255, 255, 255)


def min_boundary_contrast(patch_rgbs: list[tuple[int, int, int]]) -> float:
    """Worst patch↔spacer luminance gap across a pass (spacers chosen optimally)."""
    if len(patch_rgbs) < 2:
        return 255.0
    worst = 255.0
    for a, b in zip(patch_rgbs, patch_rgbs[1:]):
        sp = spacer_rgb(a, b)
        ls = luminance(sp)
        gap = min(abs(luminance(a) - ls), abs(luminance(b) - ls))
        worst = min(worst, gap)
    return worst


def low_contrast_passes(slot_rgbs: list[tuple[int, int, int]], steps_in_pass: int
                        ) -> list[int]:
    """Indices of passes whose worst boundary contrast is below the threshold."""
    flagged: list[int] = []
    n_passes = (len(slot_rgbs) + steps_in_pass - 1) // steps_in_pass
    for p in range(n_passes):
        col = slot_rgbs[p * steps_in_pass:(p + 1) * steps_in_pass]
        if min_boundary_contrast(col) < LOW_CONTRAST_THRESHOLD:
            flagged.append(p)
    return flagged
