"""#133 (found while rendering report screenshots, 2026-08-02): the Measurement
Report was unreadable on the dark theme.

The report body is one self-contained HTML document, because the same string is
shown in the window and saved to the PDF. It was written with a fixed
light-theme palette — ``color:#333`` on the outer div, ``#2a2a2a`` headings,
``#555`` sub-lines — and inline HTML colours beat the widget stylesheet that
tries to set light text. On the dark theme that put **#333333 text on the
#1f1f1f background: a contrast ratio of 1.29:1**, where readable body text
needs 4.5:1. The only legible parts were the ones that happened to sit on a
light panel or an alternate-row band.

Measured, not guessed: the dominant colours of a grab of the report body were
(31,31,31) background and (51,51,51) text.

These tests pin the three things that must hold:

1. the window follows the theme;
2. the PDF stays light whatever the theme is, because it is printed on white;
3. every colour the dark palette uses clears 4.5:1 against the surface it
   lands on — including the alternate-row band, which used to be a class
   attribute bound to the light colour once at import and could never follow.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import ui.dialogs.measurement_report_dialog as M    # noqa: E402
from ui.styles import BG_INPUT                      # noqa: E402


# ---- contrast ------------------------------------------------------------
def _luminance(hexc: str) -> float:
    hexc = hexc.lstrip("#")
    if len(hexc) == 3:
        hexc = "".join(c * 2 for c in hexc)
    ch = []
    for i in (0, 2, 4):
        v = int(hexc[i:i + 2], 16) / 255
        ch.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_the_bug_itself_would_be_caught():
    """The exact pair that shipped, so the number in the docstring is checked
    rather than asserted."""
    assert _contrast("#333333", "#1f1f1f") < 1.5


@pytest.mark.parametrize("key", ["text", "head", "dim", "faint",
                                 "pass", "fail", "error"])
def test_dark_text_colours_are_readable_on_the_window_background(key):
    assert _contrast(M._DARK_REPORT[key], BG_INPUT) >= 4.5, (
        f"{key}={M._DARK_REPORT[key]} on {BG_INPUT} is "
        f"{_contrast(M._DARK_REPORT[key], BG_INPUT):.2f}:1")


@pytest.mark.parametrize("key", ["text", "head", "dim", "faint",
                                 "pass", "fail", "error"])
def test_dark_text_colours_are_readable_on_the_alternate_row_band(key):
    """The band is the surface that used to invert the problem: fixing the text
    colour alone would have left light bands under light text."""
    zebra = M._DARK_REPORT["zebra"]
    assert _contrast(M._DARK_REPORT[key], zebra) >= 4.5, (
        f"{key}={M._DARK_REPORT[key]} on the band {zebra} is "
        f"{_contrast(M._DARK_REPORT[key], zebra):.2f}:1")


@pytest.mark.parametrize("key", ["text", "head", "dim", "faint",
                                 "pass", "fail", "error"])
def test_light_text_colours_stay_readable_on_paper(key):
    """The PDF is printed on white; the light palette must hold up there too."""
    assert _contrast(M._LIGHT_REPORT[key], "#ffffff") >= 4.5


def test_the_two_palettes_describe_the_same_things():
    """A key present in one and missing from the other is a crash waiting for
    whichever theme lacks it."""
    assert set(M._LIGHT_REPORT) == set(M._DARK_REPORT)


# ---- the palette actually reaches the HTML -------------------------------
def _dialog(qapp, mode, ti3):
    from core.settings import AppSettings
    s = AppSettings()
    s.set("appearance", mode)
    return M.MeasurementReportDialog(s, None, initial_ti3=ti3)


@pytest.fixture(scope="session")
def _report_project(tmp_path_factory):
    """Build the demo project ONCE for the whole session.

    It shells out to real ArgyllCMS and costs about 35 seconds. Function-scoped,
    the three tests below paid that three times over — the very waste that was
    taken out of test_legacy_migration.py earlier the same day, quietly put back
    in a new file. Session-scoped and copied per test instead.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from make_demo_projects import build_verify_history
    root = tmp_path_factory.mktemp("report-demo")
    build_verify_history(root)
    return root / "Demo-Verify-History"


@pytest.fixture
def report_ti3(_report_project, tmp_path):
    """This test's own copy of the demo project's newest verification.

    Copied rather than shared: these tests only read, but a shared tree that
    something later writes to would couple them invisibly.
    """
    import shutil
    dst = tmp_path / _report_project.name
    shutil.copytree(_report_project, dst)
    found = sorted(dst.rglob("*-verify.ti3"))
    assert found, "the demo project grew no verification measurements"
    return found[-1]


@pytest.mark.slow
def test_the_window_follows_the_theme(qapp, report_ti3):
    dark = _dialog(qapp, "dark", report_ti3)
    body = dark._report_body_html(dark._runs_for_report(), for_pdf=False)
    assert M._DARK_REPORT["text"] in body
    assert M._LIGHT_REPORT["text"] not in body


@pytest.mark.slow
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_pdf_is_light_whatever_the_window_is(qapp, report_ti3, mode):
    """It goes on white paper. A dark-themed PDF would be unreadable printed,
    and it is the same function that builds both."""
    dlg = _dialog(qapp, mode, report_ti3)
    pdf = dlg._report_body_html(dlg._runs_for_report(), for_pdf=True)
    assert M._LIGHT_REPORT["text"] in pdf
    assert M._DARK_REPORT["text"] not in pdf


@pytest.mark.slow
def test_the_alternate_row_band_follows_the_palette(qapp, report_ti3):
    """It was a class attribute, evaluated once at import against the light
    palette, so it could never change. Reading it off the instance is what
    makes it live."""
    dark = _dialog(qapp, "dark", report_ti3)
    dark._report_body_html(dark._runs_for_report(), for_pdf=False)
    assert dark._ZEBRA_BG == M._DARK_REPORT["zebra"]
