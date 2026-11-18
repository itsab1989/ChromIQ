"""MUST-B1 of the table safety review (2026-11-19): what ChromIQ says about the EFI ES-2000.

ArgyllCMS (doc/instruments.html, "OEM models") ties the missing UV light, ruler and wavelength
calibration to ONE part number, EO2-XR-UF, and names ES-2000s as OEM units that "appear from
time to time" with it. A tester's ES-2000 (issue 216, firmware 634) reported itself as an
i1Pro 2 and gave a clean ruler stream on 80 of 80 swipes. So no text may say that the ES-2000
has no UV light or ruler, and the model question must not send ES-2000 owners to "Another
instrument": an OEM i1Pro 2 usually works like an i1Pro 2, and ChromIQ notices a unit without
the UV light by itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from workflow import measurement_messages as M
from workflow.dual_scan import reasons as R

ROOT = Path(__file__).resolve().parents[1]

#: the 4.3.45 / first-beta wordings that were wrong
WRONG = (
    re.compile(r"neither has the OEM i1Pro 2", re.I),
    re.compile(r"ES-2000[^.\n]{0,60}(has|have) no UV", re.I),
    re.compile(r"no UV light[^.\n]{0,80}ES-2000", re.I),
    re.compile(r"ES-2000[^.\n]{0,60}(no|without the) (position )?ruler", re.I),
)


def _english_texts() -> "list[str]":
    de = json.loads((ROOT / "data/i18n/de.json").read_text(encoding="utf-8"))
    return [k for k in de if "ES-2000" in k]


def test_no_text_says_the_es2000_has_no_uv_light_or_ruler():
    texts = _english_texts() + [M.M_DUAL_MODEL_ASK.body] + list(R.REASONS.values())
    bad = [(p.pattern, t[:120]) for t in texts for p in WRONG if p.search(t)]
    assert bad == []


def test_the_model_question_sends_es2000_owners_to_i1pro2_not_to_another_instrument():
    body = M.M_DUAL_MODEL_ASK.body
    bullets = [b for b in body.split("\n\n") if "ES-2000" in b]
    assert len(bullets) == 1
    b = bullets[0]
    assert "“Another instrument”" not in b
    assert "choose “i1Pro 2”" in b
    assert "EO2-XR-UF" in b                         # the part number ArgyllCMS names
    assert "notices it by itself" in b              # nothing for the owner to find out


def test_the_reason_and_the_preferences_say_what_is_known():
    r = R.REASONS["not_available"]
    assert "EO2-XR-UF" in r and "usually has it" in r
    src = (ROOT / "ui/dialogs/settings_dialog.py").read_text(encoding="utf-8")
    assert "some OEM versions, for example the EFI ES-2000" not in src
    assert "EO2-XR-UF" in src


def test_every_language_carries_the_new_wording():
    for p in sorted((ROOT / "data/i18n").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        v = d.get(M.M_DUAL_MODEL_ASK.body)
        assert v and "EO2-XR-UF" in v and "ES-2000" in v, p.name
        assert v.count("\n\n") == M.M_DUAL_MODEL_ASK.body.count("\n\n"), p.name
