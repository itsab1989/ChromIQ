"""What a tool wrote is decoded with the codec named here — issue #178.

`tests/test_encoding_is_named.py` covers files. This covers the other half:
the bytes ArgyllCMS, `lp` and `sysctl` write to a pipe.

Two shapes of the same defect were measured before this module existed:

  * `subprocess.run(..., text=True)` with no `encoding=` decodes with
    `locale.getpreferredencoding(False)`. Under `LANG=C PYTHONUTF8=0` that is
    US-ASCII and the first umlaut in a path is a `UnicodeDecodeError` — a hard
    stop in a build, on a platform (`ChromIQLinux.spec`) we ship.
  * `raw.decode("utf-8", errors="replace")`, hard-coded on the QProcess and PTY
    output in `core/argyll_runner.py` — the main Argyll channel. On a German
    Windows a path in a failure dialog reached the user as
    `M?ller-Pr?fdruck.ti3`, which is the symptom the issue is about.

Both now go through `core/proc_text.py`.
"""
from __future__ import annotations

import ast
import locale
import subprocess
import sys
from pathlib import Path

import pytest

from core import proc_text
from core.proc_text import decode_output, output_order, run_text

REPO = Path(__file__).resolve().parents[1]

NAME = "Müller-Prüfdruck"


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------

def test_the_order_is_the_same_one_files_use():
    """One rule, not two. A tool's output and a tool's input file carry the
    same names in the same bytes, so a second ladder would be one too many."""
    from core.text_io import read_order
    assert output_order() == read_order()
    assert output_order()[0] == "utf-8-sig"
    assert output_order()[-1] == "cp1252"


@pytest.mark.parametrize("native,expected", [
    ("utf-8", ("utf-8-sig", "cp1252")),          # macOS, Linux, a UTF-8 Windows
    ("cp1252", ("utf-8-sig", "cp1252")),         # a German/French/English Windows
    ("cp932", ("utf-8-sig", "cp932", "cp1252")),  # a Japanese one
])
def test_the_order_follows_the_machine_the_tool_ran_on(monkeypatch, native, expected):
    monkeypatch.setattr(locale, "getencoding", lambda: native, raising=False)
    assert output_order() == expected


def test_every_codec_in_the_ladder_agrees_on_ascii():
    """THE REASON ONE POLICY IS SAFE FOR PARSED OUTPUT AS WELL AS FOR THE LOG.

    Several callers turn this output into numbers — `xicclu`, `profcheck`,
    `gamut_map`, `ti2_relayout`. Guessing a codec for those would be reckless if
    the guess could change a value.

    It cannot. Every codec the ladder can reach is an ASCII superset, so all 128
    ASCII byte values decode to the same characters under every one of them.
    Argyll's numeric output is ASCII; non-ASCII bytes appear only where a name
    or a path is echoed. So the codec choice can change how a filename is
    rendered in a message and can never change a number, drop a field, or shift
    a column.

    If this test ever goes red, the replacement net in `decode_output` has
    stopped being safe for the parsing call sites and they need their own
    policy.
    """
    ascii_bytes = bytes(range(0x80))
    reachable = {"utf-8-sig", "utf-8", "cp1252", "cp1250", "cp932", "cp936",
                 "cp949", "cp950", "cp1251", "cp1253", "cp1254", "cp1255",
                 "cp1256", "cp1257", "cp1258", "cp874", "cp437", "cp850",
                 "latin-1", "ascii"}
    for enc in reachable:
        assert ascii_bytes.decode(enc) == ascii_bytes.decode("ascii"), enc


# ---------------------------------------------------------------------------
# decode_output
# ---------------------------------------------------------------------------

def test_utf8_output_comes_back_as_written():
    assert decode_output(NAME.encode("utf-8")) == NAME


def test_ansi_output_from_a_windows_tool_is_recovered(caplog):
    """What an MSVC console program echoes on a German Windows.

    `main()` receives argv already narrowed through the ANSI code page, and
    `printf` writes those same bytes to a redirected pipe. cp1252 bytes are
    invalid UTF-8, so the first rung cannot mis-fire on them.
    """
    raw = NAME.encode("cp1252")
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")                 # what a blanket encoding="utf-8" would do
    proc_text._REPORTED.clear()
    with caplog.at_level("WARNING"):
        assert decode_output(raw, what="chartread") == NAME
    assert any("not UTF-8" in r.getMessage() for r in caplog.records), \
        [r.getMessage() for r in caplog.records]


def test_a_fallback_is_reported_once_and_not_once_per_line(caplog):
    """The PTY reader decodes line by line. A warning per line would bury the
    log it is trying to make readable."""
    proc_text._REPORTED.clear()
    with caplog.at_level("WARNING"):
        for _ in range(50):
            decode_output(NAME.encode("cp1252"), what="chartread")
    assert len([r for r in caplog.records if "not UTF-8" in r.getMessage()]) == 1


def test_bytes_no_codec_accepts_are_replaced_and_said_so(caplog):
    """The last rung. A build log that loses one character beats a build that
    dies — and it is not silent."""
    proc_text._REPORTED.clear()
    with caplog.at_level("WARNING"):
        got = decode_output(b"ok \x9d\x81\x8f done", what="colprof")
    assert got.startswith("ok ") and got.endswith(" done")
    assert "�" in got
    assert any("no known text encoding" in r.getMessage() for r in caplog.records)


def test_replacement_never_touches_the_numbers():
    """The claim `test_every_codec_in_the_ladder_agrees_on_ascii` supports,
    driven on output shaped like xicclu's."""
    line = b"0.500000 0.250000 0.125000 [RGB] -> Lab 55.123456 1.20 -3.40\n"
    dirty = b"reading '/tmp/M\x9dller.icc'\n" + line
    got = decode_output(dirty, what="xicclu")
    assert got.endswith(line.decode("ascii"))
    assert [float(v) for v in got.splitlines()[-1].split("->")[1].split()[1:]] \
        == [55.123456, 1.20, -3.40]


def test_none_and_str_pass_through():
    """A caller that did not capture a stream sees what it saw before, and a
    test that injects a fake runner returning text keeps working."""
    assert decode_output(None) == ""
    assert decode_output("already text") == "already text"


def test_decode_output_never_raises():
    for raw in (b"", b"\xff\xfe\x00\x00", bytes(range(256)), b"\x9d" * 100):
        assert isinstance(decode_output(raw), str)


# ---------------------------------------------------------------------------
# run_text
# ---------------------------------------------------------------------------

_CHILD = (r"import sys;"
          r"sys.stdout.buffer.write('Müller-Prüfdruck\n'.encode('utf-8'));"
          r"sys.stderr.buffer.write(b'warn\n')")


def test_run_text_decodes_what_the_child_wrote():
    r = run_text([sys.executable, "-c", _CHILD], capture_output=True, timeout=30)
    assert r.stdout == NAME + "\n"
    assert r.stderr == "warn\n"
    assert r.returncode == 0


def test_run_text_survives_an_ascii_only_locale():
    """THE MEASURED CRASH.

    Under `LANG=C PYTHONUTF8=0`, `locale.getpreferredencoding(False)` is
    US-ASCII, and `subprocess.run(..., text=True)` raises on the first umlaut::

        subprocess text=True RAISED UnicodeDecodeError:
            'ascii' codec can't decode byte 0xc3 in position 1

    Re-run in a real child interpreter, because the locale cannot be changed
    inside a running one. The first half proves the crash is still there for
    `text=True` — without it this test could pass because the child's locale
    never changed.
    """
    import os
    env = dict(os.environ, LANG="C", LC_ALL="C", PYTHONUTF8="0",
               PYTHONCOERCECLOCALE="0", PYTHONPATH=str(REPO))
    env.pop("LC_CTYPE", None)
    probe = (
        "import locale, subprocess, sys\n"
        "print('pref', locale.getpreferredencoding(False))\n"
        f"child = {_CHILD!r}\n"
        "try:\n"
        "    subprocess.run([sys.executable, '-c', child], capture_output=True,"
        "                   text=True, timeout=30)\n"
        "    print('text=True', 'NO CRASH')\n"
        "except UnicodeDecodeError:\n"
        "    print('text=True', 'CRASH')\n"
        "from core.proc_text import run_text\n"
        "r = run_text([sys.executable, '-c', child], capture_output=True, timeout=30)\n"
        "print('run_text', ascii(r.stdout))\n"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                         encoding="utf-8", env=env, timeout=120)
    assert out.returncode == 0, out.stderr
    lines = dict(l.split(" ", 1) for l in out.stdout.splitlines() if " " in l)
    assert lines["pref"].lower() in ("us-ascii", "ascii", "ansi_x3.4-1968"), lines
    assert lines["text=True"] == "CRASH", (
        "the ASCII locale did not reach the child, so this test is proving "
        f"nothing: {out.stdout}")
    assert lines["run_text"] == r"'M\xfcller-Pr\xfcfdruck\n'", lines


def test_run_text_takes_an_injected_runner_and_a_str_input():
    """The call sites that let a test stand in for the tool — `xicclu_runner`,
    `reference_convert`, `verification_print`, `colorimetric_preview`."""
    seen = {}

    def fake(cmd, **kw):
        seen.update(kw)
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, NAME.encode("cp1252"), b"")

    r = run_text(["xicclu"], runner=fake, input="50 0 0\n",
                 capture_output=True, timeout=5)
    assert r.stdout == NAME                       # decoded through the ladder
    assert seen["input"] == b"50 0 0\n"           # str input encoded as UTF-8
    assert "text" not in seen and "encoding" not in seen


def test_run_text_drops_the_kwargs_it_is_replacing():
    """A caller that still passes `text=True` out of habit must not put the
    platform back in charge."""
    seen = {}

    def fake(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, b"x", b"")

    run_text(["t"], runner=fake, text=True, universal_newlines=True,
             encoding="cp1252", errors="ignore", capture_output=True)
    assert set(seen) == {"capture_output"}, seen


# ---------------------------------------------------------------------------
# The two classes are gone from the product tree
# ---------------------------------------------------------------------------

def _product_files() -> list[Path]:
    files: list[Path] = []
    for d in ("core", "ui", "workflow", "scripts"):
        files += sorted((REPO / d).rglob("*.py"))
    files.append(REPO / "main.py")
    return [f for f in files if f.is_file()]


def test_the_main_argyll_channel_no_longer_hard_codes_replace():
    """`core/argyll_runner.py` decoded eight buffers as `utf-8`/`replace`.

    That is every line the log, the failure dialogs and the stripe detector
    see — the QProcess pair the issue named and the six in the PTY reader,
    which is the interactive measurement channel where chartread echoes a
    path. All eight go through the ladder now.
    """
    src = (REPO / "core" / "argyll_runner.py").read_text(encoding="utf-8")
    assert 'errors="replace"' not in src
    assert src.count('decode_output(') == 8, src.count('decode_output(')


def test_no_product_call_site_decodes_with_a_hard_coded_replace():
    """A grep, deliberately: what is being banned is a spelling.

    The exceptions are byte-level formats with a codec fixed by their own
    specification — ICC text tags (`latin-1`, `utf-16-be`), TIFF ASCII fields,
    a USB descriptor — where the codec is not a guess about a platform.
    """
    allowed = {
        "core/icc_text.py", "workflow/icc_info.py", "workflow/tiff_metadata.py",
        "workflow/cr30/identity.py", "workflow/native_print_macos.py",
        "core/proc_text.py", "core/text_io.py",
        "ui/tabs/tab_chart.py",   # compares two .ti2 blobs ChromIQ itself wrote
    }
    offenders = []
    for f in _product_files():
        rel = f.relative_to(REPO).as_posix()
        if rel in allowed:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if ".decode(" in line and "errors=" in line:
                offenders.append(f"{rel}:{i}  {line.strip()[:70]}")
    assert offenders == [], "\n  ".join(offenders)


def test_the_module_is_importable_without_qt():
    """`core.proc_text` is imported by `core/`, `workflow/` and `scripts/`
    alike, so it must stay at the bottom of the dependency graph."""
    src = (REPO / "core" / "proc_text.py").read_text(encoding="utf-8")
    imports = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.ImportFrom):
            imports.add((n.module or "").split(".")[0])
        elif isinstance(n, ast.Import):
            imports.update(a.name.split(".")[0] for a in n.names)
    assert imports <= {"__future__", "subprocess", "typing", "core"}, imports
    assert "PyQt6" not in src
