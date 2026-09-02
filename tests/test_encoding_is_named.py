"""Every text file ChromIQ reads or writes names its encoding. Issue #178.

Python takes the encoding for ``open``, ``Path.read_text`` and
``Path.write_text`` from the *platform*, not from the file. That is UTF-8 on
macOS and Linux and **cp1252 on the German Windows 11 the issue was filed
against**, so a project did not survive the trip between them:

    written on macOS : Müller-Prüfdruck, 90 g/m²
    read on Windows  : MÃ¼ller-PrÃ¼fdruck, 90 g/mÂ²
    Windows -> macOS : UnicodeDecodeError: 'utf-8' codec can't decode byte 0xfc

Both directions were measured on real files a real chart build wrote.

THE RULE, which `core/text_io.py` states in full:

  * **Writing is always UTF-8, no BOM.** Unconditionally.
  * **Reading tries UTF-8 first**, then this machine's own default if it is
    something else, then cp1252 — and says so in the log when it falls back.

The order is what makes the fallback *safer*, not safe. A cp1252 file
containing an umlaut is invalid UTF-8, so step 1 cannot mis-fire on THAT, which
is why German is recovered. The reverse is not guaranteed and this file used to
say it was: 1,770 two-character cp1252 strings are also valid UTF-8 meaning
something else, and for those nothing falls back and nothing is logged.
`test_a_cp1252_file_can_also_be_valid_utf8_and_nobody_can_tell` measures it.

And the last resort cannot say no. cp1252 maps 251 of 256 byte values, so it
decoded UTF-16 into visible nonsense without raising, and UTF-16LE with ASCII
content is valid UTF-8 outright. Section 7 pins the refusal that now comes
first.

What this file proves, in the order the issue asks for it:

  1. No call site in `core/`, `ui/`, `workflow/`, `scripts/` or `main.py`
     relies on the platform default — an AST sweep, with the sweep itself
     proved non-vacuous against planted violations.
  2. The read rule behaves as stated: UTF-8 first, cp1252 recovered, BOM eaten,
     line endings translated, strict by default, lenient where asked.
  3. **The cp1252 round trip the issue asks for by name.** The platform cannot
     be changed inside a test, but the *codec* can: `german_windows` makes
     Python's platform default cp1252 for the duration, which is precisely what
     the failing machine does. A real `Project` is then written and read back
     through it, with the issue's own name, description and notes.
  4. The lucky accident is pinned. `project.json`, `meta.json` and
     `<name>.channels.json` survive today only because `json.dumps` escapes
     `ü` to `\\u00fc` and nobody has passed `ensure_ascii=False`. That escaping
     is now load-bearing on purpose, and `test_the_json_manifests_stay_ascii`
     is what would notice if it stopped.
"""
from __future__ import annotations

import ast
import builtins
import io
import json
import locale
import sys
import unicodedata as ud
from pathlib import Path

import pytest

from core import text_io
from core.file_manager import Project
from core.text_io import LEGACY_ENCODING, WRITE_ENCODING, read_order, read_text, write_text

REPO = Path(__file__).resolve().parents[1]

#: The issue's own strings, typed by a German user.
NAME = "Müller-Prüfdruck"
DESC = "Größe: A4"
NOTES = "Müller-Prüfdruck, 90 g/m²"


# ---------------------------------------------------------------------------
# 1. No call site relies on the platform default
# ---------------------------------------------------------------------------

_TEXT_CALLS = {"open", "read_text", "write_text"}


def _unencoded_calls(src: str, label: str) -> list[str]:
    """Every text-IO call in ``src`` that names no encoding.

    Deliberately structural rather than a grep: a grep for ``read_text()``
    cannot tell ``Path(p).read_text()`` from ``core.text_io.read_text(p)``, and
    the fix turns the first into the second everywhere.
    """
    out: list[str] = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute):
            name = fn.attr
        elif isinstance(fn, ast.Name):
            name = fn.id
        else:
            continue
        if name not in _TEXT_CALLS:
            continue
        if any(k.arg == "encoding" for k in node.keywords):
            continue
        # `read_text(p)` / `write_text(p, s)` as a BARE NAME is the helper in
        # core.text_io, which names the encoding for us. Only the bound-method
        # forms (`Path(...).read_text()`) are the bug.
        if isinstance(fn, ast.Name) and name in ("read_text", "write_text"):
            continue
        if name == "open":
            # Binary modes have no encoding to name.
            mode = None
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for k in node.keywords:
                if k.arg == "mode" and isinstance(k.value, ast.Constant):
                    mode = k.value.value
            if isinstance(mode, str) and "b" in mode:
                continue
            # `Image.open`, `wave.open`, `webbrowser.open`, a transport's own
            # `.open()` — same spelling, nothing to do with text files.
            if isinstance(fn, ast.Attribute):
                recv = ast.get_source_segment(src, fn.value) or ""
                looks_like_a_path = recv.split(".")[-1] in ("Path", "p", "path")
                opens_a_named_file = bool(
                    node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str))
                if not (looks_like_a_path or opens_a_named_file):
                    continue
        out.append(f"{label}:{node.lineno}  {(ast.get_source_segment(src, node) or name)[:70]}")
    return out


def _product_files() -> list[Path]:
    files: list[Path] = []
    for d in ("core", "ui", "workflow", "scripts"):
        files += sorted((REPO / d).rglob("*.py"))
    files.append(REPO / "main.py")
    return [f for f in files if f.is_file()]


def test_no_product_call_site_relies_on_the_platform_default():
    """The sweep the issue's "97 product call sites" number came from.

    This is the guard that keeps the fix from rotting: a new
    ``Path(x).read_text()`` anywhere in the app fails here, on a macOS machine,
    long before it reaches the German Windows that would actually break.
    """
    offenders: list[str] = []
    for f in _product_files():
        rel = f.relative_to(REPO)
        if rel.as_posix() == "core/text_io.py":
            continue          # the one module allowed to talk about encodings
        offenders += _unencoded_calls(f.read_text(encoding="utf-8"), rel.as_posix())
    assert offenders == [], (
        f"{len(offenders)} text-IO call site(s) name no encoding:\n  "
        + "\n  ".join(offenders[:20]))


def test_the_sweep_would_notice_a_violation():
    """A green sweep only means something if the sweep can go red.

    Every form the codemod had to rewrite, planted deliberately. If this test
    ever passes with fewer than five findings the sweep above has stopped
    looking and its green is worthless.
    """
    planted = (
        "from pathlib import Path\n"
        "def f(p):\n"
        "    a = Path(p).read_text()\n"
        "    b = Path(p).read_text(errors='replace')\n"
        "    c = Path(p).open('r').read()\n"
        "    d = open(p).read()\n"
        "    Path(p).write_text(a)\n"
        "    with open(p, 'w') as fh: fh.write(a)\n"
        "    return a, b, c, d\n"
    )
    found = _unencoded_calls(planted, "planted")
    assert len(found) == 6, found

    # …and does NOT flag the things that are already right.
    clean = (
        "from pathlib import Path\n"
        "from core.text_io import read_text, write_text\n"
        "from PIL import Image\n"
        "def f(p, t):\n"
        "    a = read_text(p)\n"
        "    b = read_text(p, lenient=True)\n"
        "    write_text(p, a)\n"
        "    Path(p).write_text(a, encoding='utf-8')\n"
        "    Path(p).read_text(encoding='utf-8')\n"
        "    Path(p).read_bytes()\n"
        "    Path(p).write_bytes(b'x')\n"
        "    open(p, 'rb').read()\n"
        "    with open(p, 'w', encoding='utf-8') as fh: fh.write(a)\n"
        "    Image.open(p)\n"
        "    t.open()\n"
        "    return a, b\n"
    )
    assert _unencoded_calls(clean, "clean") == []


# ---------------------------------------------------------------------------
# 2. The read rule behaves as stated
# ---------------------------------------------------------------------------

def test_utf8_is_tried_first_and_cp1252_is_the_last_resort():
    order = read_order()
    assert order[0] == "utf-8-sig", order
    assert order[-1] == LEGACY_ENCODING, order
    assert WRITE_ENCODING == "utf-8"


@pytest.mark.parametrize("native,expected", [
    # macOS / Linux / a UTF-8 Windows: nothing to add, cp1252 is the fallback.
    ("utf-8", ("utf-8-sig", "cp1252")),
    ("UTF-8", ("utf-8-sig", "cp1252")),
    # A German/French/English Windows: its default IS the fallback already.
    ("cp1252", ("utf-8-sig", "cp1252")),
    # A Japanese Windows. No fixed list would have guessed cp932 — this is why
    # the machine's own default is consulted before the hard-coded fallback.
    ("cp932", ("utf-8-sig", "cp932", "cp1252")),
    # A Polish one.
    ("cp1250", ("utf-8-sig", "cp1250", "cp1252")),
])
def test_the_read_order_follows_the_machine_it_runs_on(monkeypatch, native, expected):
    monkeypatch.setattr(locale, "getencoding", lambda: native, raising=False)
    assert read_order() == expected


def test_a_utf8_file_reads_back_unchanged(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(NOTES.encode("utf-8"))
    assert read_text(p) == NOTES


def test_a_cp1252_file_from_an_older_windows_is_recovered(tmp_path, caplog):
    """The case a naive `encoding="utf-8"` sweep would have broken.

    Before this fix, this file read correctly on the Windows that wrote it and
    raised `UnicodeDecodeError` on macOS. Forcing UTF-8 everywhere would have
    made it raise on Windows too — trading a silent corruption for a hard
    failure on data already on disk. It is recovered instead, and the recovery
    is logged rather than silent.
    """
    p = tmp_path / "legacy.ti3"
    p.write_bytes(NOTES.encode("cp1252"))
    with pytest.raises(UnicodeDecodeError):
        p.read_text(encoding="utf-8")           # what a naive fix would do
    with caplog.at_level("WARNING"):
        assert read_text(p) == NOTES
    assert any("not valid UTF-8" in r.getMessage()
               for r in caplog.records), [r.getMessage() for r in caplog.records]
    # …AND AGAIN. There used to be a module-global `_REPORTED` set here, so the
    # second read of the same file said nothing (Basti, 2026-09-02: every
    # non-UTF-8 read gets reported, every time).
    caplog.clear()
    with caplog.at_level("WARNING"):
        assert read_text(p) == NOTES
    assert any("not valid UTF-8" in r.getMessage() for r in caplog.records)


def test_a_bom_is_eaten_not_delivered(tmp_path):
    """A `.txt` a Windows user opened in Notepad and saved comes back with one.

    Without `utf-8-sig` the BOM arrives as a leading `\\ufeff`, and a CGATS
    parser looking for `CTI3` on line 1 does not find it.
    """
    p = tmp_path / "notepad.txt"
    p.write_bytes(b"\xef\xbb\xbf" + NOTES.encode("utf-8"))
    got = read_text(p)
    assert got == NOTES
    assert not got.startswith("﻿")


def test_line_endings_are_translated_exactly_as_text_mode_would(tmp_path):
    """`read_text` decodes bytes, so it has to do this itself.

    Every caller that splits on `"\\n"` would otherwise start seeing a trailing
    `\\r` on Windows-written files that it never saw before.
    """
    p = tmp_path / "crlf.ti2"
    p.write_bytes(b"one\r\ntwo\rthree\nfour")
    assert read_text(p) == "one\ntwo\nthree\nfour"
    assert read_text(p) == p.read_text(encoding="utf-8")   # the same as text mode


def test_a_file_that_is_no_known_encoding_still_raises_by_default(tmp_path):
    """`errors="replace"` is not the fix — silence is the bug."""
    p = tmp_path / "junk.bin"
    p.write_bytes(b"\x9d\x81\x8f")             # the five bytes cp1252 refuses
    with pytest.raises(UnicodeDecodeError):
        read_text(p)


def test_lenient_keeps_the_tolerance_the_old_errors_argument_had(tmp_path):
    """Thirty-odd call sites passed `errors="replace"`/`"ignore"` before this.

    They were tolerant then and stay exactly as tolerant — but they now try to
    be *correct* first, which `errors="replace"` never did.
    """
    p = tmp_path / "junk.bin"
    p.write_bytes(b"\x9d\x81\x8f")
    assert read_text(p, lenient=True) == "���"
    # Lenient does not mean careless: a file that IS cp1252 is still recovered,
    # not replacement-charactered.
    p.write_bytes(NOTES.encode("cp1252"))
    assert read_text(p, lenient=True) == NOTES


def test_write_text_is_utf8_with_no_bom(tmp_path):
    """A BOM would break every ArgyllCMS parser that looks at byte 0."""
    p = tmp_path / "out.ti3"
    write_text(p, NOTES)
    raw = p.read_bytes()
    assert raw == NOTES.encode("utf-8")
    assert not raw.startswith(b"\xef\xbb\xbf")


def test_a_missing_file_still_raises_filenotfound(tmp_path):
    """`read_text` replaced `Path.read_text` at 77 sites, several of which catch
    `OSError` around it. It has to fail the same way."""
    with pytest.raises(FileNotFoundError):
        read_text(tmp_path / "nope.txt")


# ---------------------------------------------------------------------------
# 3. The cp1252 round trip — a simulated German Windows
# ---------------------------------------------------------------------------

@pytest.fixture
def german_windows(monkeypatch):
    """Make Python's platform default encoding cp1252, as on the failing box.

    The platform cannot be changed inside a test; the *codec* can, and the
    codec is the whole of the bug. `io.open` is what `Path.read_text`,
    `Path.write_text` and `Path.open` all funnel into, and `builtins.open` is
    what everything else uses — so patching both makes an unqualified text
    `open` behave here exactly as it does on a German Windows 11.

    Note `io.text_encoding(None)` returns the sentinel string ``"locale"``
    rather than ``None``, which is why both are treated as "no encoding named".
    A call that DOES name one is passed straight through, so this fixture
    changes the behaviour of the old code and not of the fixed code — which is
    what makes the round trip below a real test rather than a tautology.
    """
    real_open = io.open

    def fake_open(file, mode="r", buffering=-1, encoding=None, *args, **kw):
        if encoding in (None, "locale") and "b" not in mode:
            encoding = LEGACY_ENCODING
        return real_open(file, mode, buffering, encoding, *args, **kw)

    monkeypatch.setattr(io, "open", fake_open)
    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(locale, "getencoding", lambda: LEGACY_ENCODING, raising=False)
    return fake_open


def test_the_fixture_really_changes_the_platform_default(tmp_path, german_windows):
    """A mutation only counts if the mutation is proven to land.

    Without this, every "it survives cp1252" assertion below could be passing
    because the fixture does nothing at all.
    """
    p = tmp_path / "probe.txt"
    p.write_text(NOTES)                                  # no encoding named
    assert p.read_bytes() == NOTES.encode("cp1252"), p.read_bytes()
    assert p.read_bytes() != NOTES.encode("utf-8")
    # …and an explicit encoding still wins, so the fixture cannot mask the fix.
    p.write_text(NOTES, encoding="utf-8")
    assert p.read_bytes() == NOTES.encode("utf-8")


def test_a_whole_project_round_trips_through_a_german_windows_default(
        tmp_path, german_windows):
    """THE CHECK THE ISSUE ASKS FOR BY NAME.

    A real `Project` — manifest, run meta, the folder guide — written with the
    platform default set to cp1252, then read back. Nothing may be mangled and
    nothing may raise.

    This one would have passed before the fix as well, and that is the point of
    it: `core/file_manager.py` was already correct, so this pins the manifests
    against a future regression rather than proving today's change. The test
    that discriminates is
    `test_the_call_sites_the_fix_changed_survive_a_german_windows`.
    """
    root = tmp_path / NAME
    proj = Project.create(root, NAME)
    run = proj.new_run()
    meta = run.load_meta()
    meta.description = DESC
    meta.chart_notes = NOTES
    run.save_meta(meta)
    proj.save_manifest()
    proj.write_readme()

    # Everything ChromIQ wrote, read back through the same cp1252 default.
    reloaded = Project.load(root)
    assert reloaded.target_name == ud.normalize("NFC", NAME)
    back = reloaded.run(run.id).load_meta()
    assert back.description == DESC
    assert back.chart_notes == NOTES

    # And the folder guide — the file that failed to open at all, with
    # `UnicodeDecodeError: byte 0x9d`, because of a typographic quote in it.
    guide = read_text(proj.readme_path)
    assert guide.strip(), "the folder guide is empty"
    assert "”" in guide or "“" in guide or "→" in guide, \
        "this file no longer carries the character that used to break it"


def test_the_call_sites_the_fix_changed_survive_a_german_windows(tmp_path, german_windows):
    """The test above passes on the OLD code too, and that is worth saying.

    `core/file_manager.py` already named UTF-8 on every manifest read and write
    before this issue — it is the model the rest of the app was brought up to.
    So a project round trip alone proves the manifests, not the fix.

    These four are call sites the fix actually changed, driven with the file
    ChromIQ itself writes (UTF-8) while the platform default is cp1252 — which
    is the German Windows machine reading a Mac's project, and the direction
    that produced `MÃ¼ller-PrÃ¼fdruck` in the issue.
    """
    from core.strip_utils import parse_passes_per_page
    from ui.tiff_preview import _find_sidecar_channels
    from workflow.hex_support import chart_is_hexagonal
    from workflow.reference_convert import read_instrumentation, read_measurement_date

    # 1 + 2. An i1Profiler hand-off export, exactly as ChromIQ writes it.
    txt = tmp_path / f"{NAME}-i1profiler.txt"
    write_text(txt, f'CGATS.5\n\nORIGINATOR "ChromIQ"\nDESCRIPTOR "{NOTES}"\n'
                    f'CREATED "2026-09-02"\nINSTRUMENTATION "i1Pro 2 — Müller"\n')
    assert read_instrumentation(txt) == "i1Pro 2 — Müller"
    assert read_measurement_date(txt) == "2026-09-02"

    # 3. The chart sidecar, read by the preview and by the hex guard.
    tif = tmp_path / f"{NAME}_01.tif"
    sidecar = tmp_path / f"{NAME}.channels.json"
    write_text(sidecar, json.dumps({
        "ink_channels": ["R", "G", "B"],
        "chart_notes": NOTES,
        "layout": {"recipe": {"instrument": "SS", "hflag": True}},
    }))
    assert _find_sidecar_channels(tif) == ["R", "G", "B"]
    assert json.loads(read_text(sidecar))["chart_notes"] == NOTES

    # 4. A .ti2 whose header carries the project name — read by the strip
    #    helper, and the path the hex guard resolves its sidecar from.
    ti2 = tmp_path / f"{NAME}.ti2"
    write_text(ti2, f'CTI2\n\nDESCRIPTOR "{NOTES}"\nPASSES_IN_STRIPS2 "4"\n')
    assert parse_passes_per_page(ti2) == [4]
    assert chart_is_hexagonal(ti2) is True


def test_that_last_test_would_have_failed_before_the_fix(tmp_path, german_windows,
                                                         monkeypatch):
    """A mutation only counts if the mutation is proven to land.

    `workflow.reference_convert` is put back exactly as it was — the bound
    `Path.read_text(errors="replace")` it used to call — and the same UTF-8 file
    then comes back as the issue's mojibake. Without this, the assertion above
    could be passing because the fixture never reached that module.
    """
    import workflow.reference_convert as rc
    monkeypatch.setattr(rc, "read_text",
                        lambda p, **kw: Path(p).read_text(errors="replace"))
    txt = tmp_path / "old.txt"
    write_text(txt, 'INSTRUMENTATION "i1Pro 2 — Müller"\n')
    got = rc.read_instrumentation(txt)
    assert got != "i1Pro 2 — Müller", (
        "the pre-fix call was restored and the text came back INTACT — the "
        "german_windows fixture is not reaching this module, so the test above "
        "is guarding nothing")
    assert got == "i1Pro 2 â€” MÃ¼ller", got     # the issue's own symptom


def test_files_written_on_a_german_windows_are_read_back_on_a_mac(tmp_path):
    """The direction that used to fail outright rather than quietly.

    Write everything the cp1252 way — this is a byte-for-byte stand-in for what
    a 4.1.4 install on that machine left on disk — then read it here.
    """
    written = {}
    for name, body in (("chart_notes.txt", NOTES),
                       ("run_desc.txt", DESC),
                       ("i1profiler.txt", f'DESCRIPTOR "{NAME}"\nCREATED "x"\n')):
        p = tmp_path / name
        p.write_bytes(body.encode(LEGACY_ENCODING))
        written[p] = body
    for p, body in written.items():
        with pytest.raises(UnicodeDecodeError):
            p.read_text(encoding="utf-8")        # what 4.1.4 did here, and 3.15 will
        assert read_text(p) == body              # what ChromIQ does now


def test_what_a_german_windows_reads_out_of_what_a_mac_wrote(tmp_path):
    """The forward direction, at the byte level.

    Text ChromIQ writes is UTF-8. Decoded as cp1252 by a *pre-fix* ChromIQ it
    is the mojibake the issue quotes; decoded by `read_text` it is the text.
    """
    p = tmp_path / "exports.txt"
    write_text(p, f'DESCRIPTOR "{NAME}"')
    raw = p.read_bytes()
    assert raw.decode("cp1252") == 'DESCRIPTOR "MÃ¼ller-PrÃ¼fdruck"'   # the bug
    assert read_text(p) == f'DESCRIPTOR "{NAME}"'                      # the fix


# ---------------------------------------------------------------------------
# 4. The lucky accident, made deliberate
# ---------------------------------------------------------------------------

def test_the_json_manifests_stay_ascii(tmp_path):
    """`project.json` and `meta.json` are pure ASCII on disk, and must stay so.

    They survive a macOS→Windows trip today only because `json.dumps` defaults
    to `ensure_ascii=True` and escapes `ü` to `\\u00fc`, and ASCII decodes the
    same under every codec in the read order. That is worth keeping ON PURPOSE
    now that it is known — not because UTF-8 would be wrong (the writes name
    it), but because these two files are the ones an OLDER ChromIQ on Windows
    still has to be able to read, and an older ChromIQ reads them with the
    platform default.

    So the rule is: ChromIQ's own manifests stay 7-bit. A future
    `ensure_ascii=False` in `save_manifest` or `_atomic_json` would corrupt
    silently, on a machine none of us has, with nothing else to catch it.
    THIS TEST IS THAT SOMETHING ELSE.
    """
    root = tmp_path / NAME
    proj = Project.create(root, NAME)
    run = proj.new_run()
    meta = run.load_meta()
    meta.description = DESC
    meta.chart_notes = NOTES
    run.save_meta(meta)
    proj.save_manifest()

    for p in (proj.manifest_path, run.meta_path):
        raw = p.read_bytes()
        assert all(b < 0x80 for b in raw), (
            f"{p.name} is no longer pure ASCII — either json.dumps was given "
            f"ensure_ascii=False, or a non-JSON writer took over. Read this "
            f"test's docstring before changing it.")
        assert raw.decode("cp1252") == raw.decode("utf-8"), p.name

    # …and the escaping is lossless: the text comes back exactly as typed.
    assert json.loads(proj.manifest_path.read_text(encoding="utf-8"))["target_name"] \
        == ud.normalize("NFC", NAME)
    back = run.load_meta()
    assert (back.description, back.chart_notes) == (DESC, NOTES)


def test_the_ascii_pin_would_notice_ensure_ascii_false(tmp_path, monkeypatch):
    """Proof that the pin above is not vacuous.

    `json.dumps` is made to emit raw UTF-8 for the duration — the exact one-word
    change that would break the installed base — and the ASCII assertion must
    go red.
    """
    import core.file_manager as fm
    real_dumps = json.dumps
    monkeypatch.setattr(
        fm.json, "dumps",
        lambda obj, **kw: real_dumps(obj, **{**kw, "ensure_ascii": False}))

    root = tmp_path / NAME
    proj = Project.create(root, NAME)
    proj.save_manifest()
    raw = proj.manifest_path.read_bytes()
    assert not all(b < 0x80 for b in raw), (
        "the mutation did not land — `save_manifest` no longer goes through "
        "`json.dumps`, so `test_the_json_manifests_stay_ascii` is guarding "
        "nothing")
    assert raw.decode("cp1252") != raw.decode("utf-8"), \
        "…and this is what that costs: two machines reading two different names"


# ---------------------------------------------------------------------------
# 5. The shipped assets
# ---------------------------------------------------------------------------

def test_the_bundled_cht_and_ti1_assets_are_utf8_and_survive_a_rewrite():
    """ChromIQ's own bundled `.cht` files carry an em-dash in their header.

    `ui/dialogs/scanin_dialog.py` rewrites `.cht` files. On a German Windows the
    old code wrote that em-dash back as cp1252 and every later reader saw
    `â€"`; it is UTF-8 now. The round trip through the fixed reader and writer
    is byte-for-byte identical to the shipped file, which is the strongest form
    this can take: scanin cannot tell them apart because there is nothing to
    tell apart.
    """
    assets = sorted((REPO / "data" / "scanner_targets").glob("*.cht"))
    assert assets, "no bundled .cht files found"
    accented = [p for p in assets if any(b > 0x7F for b in p.read_bytes())]
    assert accented, "expected the bundled .cht headers to carry an em-dash"
    for p in accented:
        raw = p.read_bytes()
        raw.decode("utf-8")                        # they are UTF-8, not cp1252
        assert write_text.__module__ == "core.text_io"
        assert read_text(p).encode("utf-8") == raw, f"{p.name} does not round-trip"


# ---------------------------------------------------------------------------
# 6. The interpreter itself
# ---------------------------------------------------------------------------

def test_the_module_is_importable_without_qt():
    """`core.text_io` is imported by `core/`, `ui/` and `workflow/` alike, so it
    must stay at the bottom of the dependency graph — logger and stdlib only."""
    src = (REPO / "core" / "text_io.py").read_text(encoding="utf-8")
    imports = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ImportFrom):
            imports.add((n.module or "").split(".")[0])
        elif isinstance(n, ast.Import):
            imports.update(a.name.split(".")[0] for a in n.names)
    assert imports <= {"__future__", "locale", "os", "pathlib", "core"}, imports
    assert "PyQt6" not in src


# ---------------------------------------------------------------------------
# 7. A file that is not this kind of text at all
#
# cp1252 maps 251 of 256 byte values, so the last resort always "succeeded"
# and a UTF-16 file came back as visible nonsense with no exception:
#
#     utf16le_bom          -> 'ÿþM\x00ü\x00l\x00l\x00e\x00r…'   NO EXCEPTION
#     utf16be_bom          -> 'þÿ\x00M\x00ü\x00l\x00l\x00e…'    NO EXCEPTION
#     utf16le_nobom_ascii  -> 'C\x00R\x00E\x00A\x00T\x00E\x00D…'  NO EXCEPTION,
#                                                             AND NO WARNING
#
# The third is the worst: UTF-16LE with ASCII content is valid UTF-8 (NUL is a
# legal UTF-8 byte), so the FIRST attempt succeeded and nothing was logged at
# all, which is the silence this whole module exists to remove.
#
# Producer: Windows PowerShell 5.1, still the default shell there, writes
# UTF-16LE+BOM for `>` and `Out-File`; older Notepad's "Save as -> Unicode"
# does the same. No ChromIQ or Argyll producer writes UTF-16, so the mechanism
# is proved and the trigger is plausible but unobserved.
# ---------------------------------------------------------------------------

UTF16_CASES = {
    "utf16le_bom": NOTES.encode("utf-16"),                     # BOM + LE
    "utf16be_bom": b"\xfe\xff" + NOTES.encode("utf-16-be"),
    "utf16le_nobom_ascii": 'CREATED "2026-09-02"\n'.encode("utf-16-le"),
    "utf16le_bom_ascii_only": "BEGIN_DATA\n1 100.0\nEND_DATA\n".encode("utf-16"),
}


@pytest.mark.parametrize("case", sorted(UTF16_CASES))
def test_a_utf16_file_raises_instead_of_decoding_to_nonsense(tmp_path, case, caplog):
    """Every one of the four measured inputs. Loudly, not silently."""
    p = tmp_path / f"{case}.ti3"
    p.write_bytes(UTF16_CASES[case])
    with caplog.at_level("ERROR"):
        with pytest.raises(UnicodeDecodeError) as exc:
            read_text(p)
    # The reason says what was found, not what it guesses about who wrote it.
    assert ("UTF-16" in str(exc.value) or "NUL" in str(exc.value)), str(exc.value)
    assert any(str(p) in r.getMessage() for r in caplog.records), (
        "a refusal that is not logged is the silence again")


@pytest.mark.parametrize("case", sorted(UTF16_CASES))
def test_a_lenient_caller_gets_the_real_text_and_never_raises(tmp_path, case):
    """`lenient=True` exists so an optional sidecar cannot kill a build.

    It must not raise, and handing back the nonsense the refusal exists to
    prevent would be no better, so a file that declares itself (or is
    structurally unmistakable) is decoded as what it is.
    """
    p = tmp_path / f"{case}.ti3"
    p.write_bytes(UTF16_CASES[case])
    got = read_text(p, lenient=True)
    assert "\x00" not in got, repr(got[:60])
    if case == "utf16le_bom":
        assert got == NOTES
    if case == "utf16le_nobom_ascii":
        assert got.startswith('CREATED "2026-09-02"')


def test_the_refusal_is_a_unicodedecodeerror_so_existing_callers_still_catch_it(
        tmp_path):
    """One failure mode, the one a strict read always had.

    `read_text` already raised `UnicodeDecodeError` for a file no codec
    decodes, and callers catch that (or `ValueError`, or `Exception`). A new
    exception class would have walked past every one of those handlers.
    """
    p = tmp_path / "x.ti3"
    p.write_bytes(b"\xff\xfe" + "hello".encode("utf-16-le"))
    with pytest.raises(ValueError):          # UnicodeDecodeError is a ValueError
        read_text(p)
    try:
        read_text(p)
    except UnicodeDecodeError as exc:
        assert exc.encoding == "utf-8"
        assert exc.object == p.read_bytes()
        assert exc.reason


def test_a_nul_byte_is_refused_whatever_produced_it(tmp_path):
    """ChromIQ writes CGATS, JSON and plain text; Argyll writes CGATS. None of
    them contains a NUL, so one means these are not the bytes we think."""
    p = tmp_path / "truncated.ti3"
    p.write_bytes(b"CTI3\n\x00\x00\x00\x00")
    with pytest.raises(UnicodeDecodeError):
        read_text(p)


@pytest.mark.parametrize("payload", [
    NOTES.encode("utf-8"),                          # the normal case
    NOTES.encode(LEGACY_ENCODING),                  # the legacy case
    b"\xef\xbb\xbf" + NOTES.encode("utf-8"),        # Notepad's UTF-8 BOM
    b"BEGIN_DATA\r\n1 100.0\r\nEND_DATA\r\n",       # CRLF, plain ASCII
    b"",                                            # an empty file
])
def test_the_refusal_does_not_touch_a_file_that_was_always_fine(tmp_path, payload):
    """The overwhelming majority. A guard that fires on real data is a bug."""
    p = tmp_path / "fine.ti3"
    p.write_bytes(payload)
    read_text(p)                                    # strict: must not raise
    read_text(p, lenient=True)


def test_a_cp1252_file_can_also_be_valid_utf8_and_nobody_can_tell():
    """The claim this module used to make, measured and disproved.

    "Text that is valid UTF-8 is not also plausibly cp1252" was stated as the
    reason step 1 can never mis-fire. It can. This is not fixed here (both
    readings are legitimate text and the bytes do not say which) but the
    docstring no longer says otherwise, and the number is pinned so nobody
    re-derives it.
    """
    both = 0
    for a in range(256):
        for b in range(256):
            try:
                s = bytes([a, b]).decode(LEGACY_ENCODING)
            except UnicodeDecodeError:
                continue
            raw = s.encode(LEGACY_ENCODING)
            try:
                if raw.decode("utf-8") != s:
                    both += 1
            except UnicodeDecodeError:
                pass
    assert both == 1770, both
    # The realistic shape of it: text that was already mojibake once.
    doubled = "prÃ©fÃ©rence".encode(LEGACY_ENCODING)
    assert doubled.decode("utf-8") == "préférence"


def test_the_dedup_that_went_quiet_is_gone():
    """Basti, 2026-09-02: every non-UTF-8 read gets reported, every time.

    There was a module-global `_REPORTED` set, keyed by (path, codec) and
    never cleared, so a measurement file read on every chartread run warned
    once and then said nothing for the rest of the session, and the set grew
    for the life of the process.
    """
    assert not hasattr(text_io, "_REPORTED")
    src = (REPO / "core" / "text_io.py").read_text(encoding="utf-8")
    assert "_REPORTED" not in src


def test_the_fallback_warning_claims_only_what_it_knows(tmp_path, caplog):
    """It used to say the file "was probably written by an older ChromIQ on
    Windows". It cannot know that, and for a UTF-16 file it was simply untrue.
    """
    p = tmp_path / "legacy.ti3"
    p.write_bytes(NOTES.encode(LEGACY_ENCODING))
    with caplog.at_level("WARNING"):
        read_text(p)
    msg = " ".join(r.getMessage() for r in caplog.records)
    assert "older ChromIQ" not in msg
    assert LEGACY_ENCODING in msg and "guess" in msg
    assert "—" not in msg, "no em dashes in text a user may be shown"
