"""4.3.32 review of feature B: every sentence a turned measurement's refusal
or filing window can show is translated, and the extractor sees them.

Found in review (2026-11-11): the eight "cannot tell" sentences live in a
dict (`_TURNED_GRID_COLOURS_UNSURE`), which `scripts/i18n_extract.py` did not
sweep, so they were never in any catalogue and the refusal showed them in
English in the middle of a translated paragraph, in all thirteen languages.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import measurement_messages as M                  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LANGS = sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json"))


def test_the_extractor_sees_every_cannot_tell_sentence():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import i18n_extract
    keys = i18n_extract.extract_keys()
    for text in M._TURNED_GRID_COLOURS_UNSURE.values():
        assert text in keys, text[:60]


@pytest.mark.parametrize("lang", LANGS)
def test_every_turned_grid_verdict_sentence_is_translated(lang):
    cat = json.loads((ROOT / "data" / "i18n" / f"{lang}.json").read_text(
        encoding="utf-8"))
    texts = [*M._TURNED_GRID_COLOURS_UNSURE.values(),
             M._TURNED_GRID_COLOURS_STRIP_WRONG,
             M._TURNED_GRID_COLOURS_DISAGREE,
             M._TURNED_GRID_COLOURS_OTHER_ARRANGEMENT,
             M._TURNED_GRID_COLOURS_UNSURE_TAIL, M._TURNED_GRID_WAY_BACK,
             M.M_IMPORT_TURNED_GRID_COLOURS.title,
             M.M_IMPORT_TURNED_GRID_COLOURS.body]
    missing = [t[:60] for t in texts if not cat.get(t)]
    assert not missing, missing
