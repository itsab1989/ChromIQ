"""B8-1478 (Knut, #182 5856955264): the presets window said the i1Pro A4
484-patch "Full layout setup" preset holds 9 white and 8 black patches, while
its patch set holds 1 and 1 ("the correct is what the color patches show in the
ti1 file"). The counts are typed into ``KNUT_PRESETS`` by hand, so nothing tied
them to the file; the 1200-patch sibling said 9 and 8 over 2 and 2.

Every built-in preset that ships a patch set must declare exactly the patches,
the whites (R = G = B = 100) and the blacks (R = G = B = 0) that file holds."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.resource_path import resource_path
from ui.tabs.tab_chart import KNUT_PRESETS


def _counts(path: Path) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    body = text.split("\nBEGIN_DATA\n", 1)[1].split("\nEND_DATA", 1)[0]
    rows = [ln.split() for ln in body.splitlines() if ln.strip()]
    rgb = [[float(x) for x in r[1:4]] for r in rows]
    white = sum(all(abs(v - 100.0) < 1e-6 for v in c) for c in rgb)
    black = sum(all(abs(v) < 1e-6 for v in c) for c in rgb)
    return len(rows), white, black


_WITH_A_PATCH_SET = [p for p in KNUT_PRESETS if getattr(p, "ti1_asset", None)]


def test_there_are_presets_to_check():
    assert len(_WITH_A_PATCH_SET) > 100


@pytest.mark.parametrize("preset", _WITH_A_PATCH_SET, ids=lambda p: p.key)
def test_the_declared_counts_are_the_patch_sets_own(preset):
    patches, white, black = _counts(Path(resource_path(preset.ti1_asset)))
    assert (preset.patches, preset.white, preset.black) == (patches, white, black)
