"""4.3.5 beta 4: the release DMGs carry no signature of their own.

A forum user could not open the beta 3 universal DMG on an M4 Mac Studio:
macOS called the disk image itself untrusted and offered only "Move to
Trash". The workflow signed every DMG ad hoc; a quarantined disk image whose
signature Gatekeeper cannot accept is refused before it mounts, while an
unsigned one mounts and the app inside is judged on first launch. The app
keeps its ad-hoc signature. MUTATION: put back ``codesign --sign - <dmg>``
and this goes red.
"""
from __future__ import annotations

import re
from pathlib import Path

WF = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build-release.yml"


def _codesign_lines():
    return [ln.strip() for ln in WF.read_text("utf-8").splitlines()
            if re.search(r"\bcodesign\b[^\n]*--sign", ln) and not ln.strip().startswith("#")]


def test_no_dmg_is_signed():
    for ln in _codesign_lines():
        assert "dmg" not in ln.lower() and "matrix.artifact" not in ln, ln


def test_the_app_is_still_signed_ad_hoc():
    lines = _codesign_lines()
    assert any(ln.endswith("dist/ChromIQ.app") for ln in lines), lines
    assert any('"$THIN_APP"' in ln for ln in lines), lines


def test_the_workflow_refuses_a_signed_dmg():
    text = WF.read_text("utf-8")
    assert 'codesign -dv "${{ matrix.artifact }}"' in text
    assert 'codesign -dv "$X86_DMG"' in text
