"""Every third-party file ChromIQ ships must say on what terms it is here.

`assets/USWebCoatedSWOP.icc` shipped in every release from v2.3.0 to
4.1.5-beta. Its own ICC copyright tag read *"Copyright 2000 Adobe Systems,
Inc."*. It arrived in one line of an eight-file commit — *"assets: bundle
USWebCoatedSWOP.icc so ICC conversion works on all Macs"* — with no licence
file, no attribution, and nothing anywhere recording that anyone had asked
whether we were allowed to copy it. Adobe's end-user agreement for these
profiles says, in these words:

    No other distribution of the Software is allowed; including, without
    limitation, distribution of the Software when incorporated into or bundled
    with any application software.

Nobody noticed for four months, because nothing was watching. This file
watches. It is deliberately narrow — it does not try to police 277 generated
chart files — and instead guards the three shapes a third-party asset actually
takes here:

* a **colour profile**, which must carry an acceptable grant in its own ICC
  ``cprt`` tag and be named in ``THIRD-PARTY-NOTICES.md``;
* a **font**, whose licence must travel with it as OFL 1.1 requires;
* a **vendored library**, whose notice must be reproduced.

Plus the two ways a notices file rots: promising a licence file that is not
there, and naming an asset that is gone.
"""
import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NOTICES = ROOT / "THIRD-PARTY-NOTICES.md"

#: Grants we accept in an ICC ``cprt`` tag for a profile we REDISTRIBUTE.
#: Public-domain dedications only. A bare copyright line — which is all Adobe's
#: profile carried — is not a grant, and that is the whole point of this file.
_ACCEPTED_CPRT = (
    "released into the public domain",
    "public domain. no warranty",
)


def _icc_tag(path: Path, want: bytes) -> str:
    """The text payload of one ICC tag, or "" when the profile has no such tag."""
    d = path.read_bytes()
    if len(d) < 132 or d[36:40] != b"acsp":
        return ""
    count = struct.unpack(">I", d[128:132])[0]
    for i in range(count):
        sig, off, size = struct.unpack(">4sII", d[132 + i * 12:144 + i * 12])
        if sig == want:
            raw = d[off:off + size]
            # 'text' type: 4-byte sig, 4 reserved, then NUL-terminated ASCII.
            body = raw[8:] if raw[:4] in (b"text", b"desc") else raw
            if raw[:4] == b"desc":          # 'desc' has a 4-byte length first
                body = raw[12:]
            return body.split(b"\x00")[0].decode("latin1", "replace").strip()
    return ""


def _bundled_profiles() -> list[Path]:
    return sorted(p for p in (ROOT / "assets").rglob("*")
                  if p.suffix.lower() in (".icc", ".icm") and p.is_file())


def _fonts() -> list[Path]:
    return sorted((ROOT / "assets" / "fonts").glob("*.ttf"))


def _font_licence_note(path: Path) -> str:
    """Name-table entry 13 (licence description), or "" — enough to spot OFL."""
    d = path.read_bytes()
    num = struct.unpack(">H", d[4:6])[0]
    table = None
    for i in range(num):
        tag, _cs, off, ln = struct.unpack(">4sIII", d[12 + i * 16:28 + i * 16])
        if tag == b"name":
            table = (off, ln)
    if table is None:
        return ""
    off = table[0]
    _fmt, cnt, str_off = struct.unpack(">HHH", d[off:off + 6])
    for i in range(cnt):
        pid, _eid, _lid, nid, ln, o2 = struct.unpack(
            ">HHHHHH", d[off + 6 + i * 12:off + 18 + i * 12])
        if nid != 13:
            continue
        raw = d[off + str_off + o2:off + str_off + o2 + ln]
        try:
            return (raw.decode("utf-16-be") if pid == 3
                    else raw.decode("latin1"))
        except Exception:
            continue
    return ""


# ---------------------------------------------------------------------------
# The specific fault
# ---------------------------------------------------------------------------

def test_the_adobe_profile_is_gone_and_nothing_points_at_a_bundled_copy():
    """Adobe's profile may not come back, and no code may expect it to be here.

    The two halves matter separately: deleting the file while
    ``_get_cmyk_transform`` still asks for ``assets/USWebCoatedSWOP.icc`` would
    leave a silent downgrade to the naive conversion (16.9 ΔE76 mean) that no
    test would have caught.
    """
    stale = [p for p in (ROOT / "assets").rglob("USWebCoatedSWOP.icc")]
    assert not stale, (
        f"Adobe's profile is back at {stale}. Adobe's end-user agreement: "
        '"No other distribution of the Software is allowed; including, '
        'without limitation, distribution of the Software when incorporated '
        'into or bundled with any application software." See '
        "THIRD-PARTY-NOTICES.md.")

    src = (ROOT / "ui" / "tiff_preview.py").read_text(encoding="utf-8")
    bad = re.findall(r'resource_path\(\s*["\'][^"\']*USWebCoatedSWOP', src)
    assert not bad, (
        "ui/tiff_preview.py still resolves Adobe's profile as a BUNDLED "
        f"resource: {bad}. Reading a copy the user installed themselves is "
        "fine and stays; shipping one is not.")


def test_no_profile_we_ship_carries_a_bare_third_party_copyright():
    """A copyright line is not a licence — that is how this happened.

    Every ICC profile under ``assets/`` must carry a public-domain dedication
    in its own ``cprt`` tag, written by whoever owns it. Adobe's read
    "Copyright 2000 Adobe Systems, Inc." and nothing else.
    """
    bad = []
    for p in _bundled_profiles():
        cprt = _icc_tag(p, b"cprt")
        if not any(tok in cprt.lower() for tok in _ACCEPTED_CPRT):
            bad.append(f"{p.relative_to(ROOT)}: cprt = {cprt!r}")
    assert not bad, (
        "these bundled profiles carry no grant we can point at:\n  "
        + "\n  ".join(bad)
        + "\n\nA profile ChromIQ REDISTRIBUTES needs a dedication or an "
          "explicit grant, established from the copyright holder and recorded "
          "in THIRD-PARTY-NOTICES.md — not a bare copyright notice.")


def test_the_cmyk_preview_still_has_a_profile_to_use():
    """The swap must not have quietly dropped the preview to the naive path.

    Measured over a 6**4 CMYK grid, the naive subtractive fallback sits a mean
    16.9 ΔE76 (p95 47.0) from a profiled conversion and paints 100 % cyan as
    #00FFFF. Removing the profile without noticing would look like nothing.
    """
    from ui import tiff_preview
    from core.resource_path import resource_path

    profile = Path(resource_path(tiff_preview._BUNDLED_CMYK_PROFILE))
    assert profile.exists(), f"{tiff_preview._BUNDLED_CMYK_PROFILE} is missing"

    d = profile.read_bytes()
    assert d[16:20] == b"CMYK", (
        f"{profile.name} is not a CMYK profile (space {d[16:20]!r}) — the "
        "preview transform will fail to build and fall back to naive")

    from PIL import ImageCms
    src = ImageCms.getOpenProfile(str(profile))
    dst = ImageCms.createProfile("sRGB")
    t = ImageCms.buildTransformFromOpenProfiles(
        src, dst, "CMYK", "RGB", renderingIntent=ImageCms.Intent.PERCEPTUAL)
    assert t is not None

    from PIL import Image
    import numpy as np
    # 100 % cyan must NOT come out as the naive #00FFFF.
    cyan = Image.frombytes("CMYK", (1, 1), bytes([255, 0, 0, 0]))
    rgb = tuple(int(v) for v in
                np.asarray(ImageCms.applyTransform(cyan, t)).reshape(3))
    assert rgb != (0, 255, 255), (
        "100 % cyan rendered as #00FFFF — that is the naive fallback, not a "
        "profiled conversion")


# ---------------------------------------------------------------------------
# The general rule
# ---------------------------------------------------------------------------

def test_the_notices_file_exists_and_states_the_rule():
    assert NOTICES.is_file(), (
        "THIRD-PARTY-NOTICES.md is gone — it is the only place the repo says "
        "on what terms its bundled assets are here")
    text = NOTICES.read_text(encoding="utf-8")
    assert "must have its terms" in text, (
        "the notices file has lost the rule it exists to state")


def test_every_bundled_profile_and_font_is_named_in_the_notices():
    """A file that ships and is not listed is exactly the original fault."""
    text = NOTICES.read_text(encoding="utf-8")
    missing = [str(p.relative_to(ROOT)) for p in _bundled_profiles() + _fonts()
               if p.name not in text]
    assert not missing, (
        "these ship but THIRD-PARTY-NOTICES.md does not name them:\n  "
        + "\n  ".join(missing))


#: Words that mark a path the notices file mentions BECAUSE it is not there —
#: the removed Adobe profile, the plotly sidecar that never arrived. Prose has
#: to say so on the same line, so "gone" and "listed as present" stay distinct.
_ABSENT_MARKERS = ("removed", "not present", "never been present",
                   "is missing", "no longer")


def test_the_notices_file_names_nothing_that_has_been_deleted():
    """The other way a notices file rots: entries outliving their files.

    A path may be mentioned while absent — the removed Adobe profile is the
    reason this document exists — but the line has to SAY it is absent. That
    keeps "we ship this, here are its terms" and "we deliberately do not ship
    this" from reading the same.
    """
    claimed: dict[str, str] = {}
    for line in NOTICES.read_text(encoding="utf-8").splitlines():
        for m in re.findall(r"`((?:assets|data)/[^`]+?\.(?:icm|icc|ttf|js|md|txt|pdf))`",
                            line):
            claimed.setdefault(m, line)
    gone = sorted(
        path for path, line in claimed.items()
        if not (ROOT / path).exists()
        and not any(w in line.lower() for w in _ABSENT_MARKERS))
    assert not gone, (
        "THIRD-PARTY-NOTICES.md points at files that are not there:\n  "
        + "\n  ".join(gone)
        + "\n\nEither the file was deleted and its entry should go, or the "
          "line should say plainly that it is absent (one of "
          f"{list(_ABSENT_MARKERS)}).")


def test_every_licence_file_the_notices_promise_is_actually_present():
    """OFL 1.1 §2: the licence has to travel with the fonts. It did not."""
    required = [
        ROOT / "assets" / "fonts" / "OFL.txt",
        ROOT / "assets" / "sounds" / "CREDITS.md",
        ROOT / "assets" / "test_images" / "ATTRIBUTION.md",
        ROOT / "assets" / "test_images" / "PhotoDisc-Freeware-License.pdf",
        ROOT / "data" / "scanner_targets" / "LICENSE",
        ROOT / "native" / "argyll" / "LICENSE",
        ROOT / "LICENSE",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    assert not missing, (
        "THIRD-PARTY-NOTICES.md points at licence files that do not exist:\n  "
        + "\n  ".join(missing))


def test_the_ofl_fonts_ship_with_the_ofl():
    """Six OFL fonts shipped for months with no copy of the OFL anywhere.

    OFL 1.1 §2: *"The above copyright notice and this license notice shall be
    included in all copies of one or more of the Font Software typefaces."*
    The notice inside each font's name table names the licence; it is not the
    licence.
    """
    fonts = _fonts()
    assert fonts, "assets/fonts holds no .ttf — has the folder moved?"
    ofl_fonts = [p for p in fonts if "open font license" in
                 _font_licence_note(p).lower()]
    if not ofl_fonts:
        pytest.skip("no OFL fonts bundled")

    ofl = ROOT / "assets" / "fonts" / "OFL.txt"
    assert ofl.exists(), (
        f"{len(ofl_fonts)} OFL fonts ship with no assets/fonts/OFL.txt")
    text = ofl.read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1" in text, (
        "assets/fonts/OFL.txt does not contain the OFL 1.1 text")
    assert "PERMISSION & CONDITIONS" in text, (
        "assets/fonts/OFL.txt is truncated — the operative section is missing")
    # Every OFL font's own copyright holder must appear in the notice file,
    # which is what OFL §2 means by "the above copyright notice".
    for p in ofl_fonts:
        family = p.name.split("-")[0]
        token = {"InstrumentSerif": "Instrument Serif",
                 "JetBrainsMono": "JetBrains Mono"}.get(family, family)
        assert token in text, (
            f"{p.name}: OFL.txt carries no copyright line for {token}")


def test_the_vendored_javascript_carries_its_permission_notice():
    """MIT requires the permission notice to travel, and plotly's sidecar
    LICENSE.txt has never been in this repo."""
    js = ROOT / "assets" / "plotly-gl3d.min.js"
    if not js.exists():
        pytest.skip("plotly bundle not present")
    text = NOTICES.read_text(encoding="utf-8")
    assert "Permission is hereby granted, free of charge" in text, (
        "assets/plotly-gl3d.min.js is MIT; the permission notice MIT requires "
        "is not reproduced in THIRD-PARTY-NOTICES.md, and the sidecar "
        "plotly-gl3d.min.js.LICENSE.txt its own header points at is absent")
    assert "Plotly, Inc" in text, "the plotly copyright line is missing"
