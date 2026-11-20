"""Review 2 of 4.3.52, S-1 to S-3: the texts.

S-1 (the owner, 2026-11-20: i1Profiler is never the main or only way out, the power switch
first): the done page after ChromIQ let go of the table with a held arm away from rest, and the
page of a table still in its aiming mode, give the power switch first and i1Profiler last.
S-2: the guided START homing page waits for the answer, so it does not say "now".
S-3: the CHANGELOG's v4.3.52 section states nothing untested as a fact; v4.3.51 is untouched.
"""
from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from core import i18n
from tests.i1io_table.test_window import settings  # noqa: F401 (the fixture)
from ui import i1io_table_window as W
from workflow import measurement_messages as M

ROOT = Path(__file__).resolve().parents[2]
LANGS = ["en"] + sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json"))


@pytest.mark.parametrize("msg", [M.M_I1IO_DRIVE_STILL_AIMING, M.M_I1IO_DRIVE_ARM_WAY_OUT_ENDED],
                         ids=lambda m: m.id)
def test_s1_the_power_switch_comes_before_i1profiler(msg):
    body = msg.body
    assert body.index("Switch the table off at its power switch") < body.index("i1Profiler")
    assert body.index("push the arm gently by hand") < body.index("i1Profiler")
    # i1Profiler is the LAST step
    last = body.split("\n\n")[1].split("\n")[-1] if msg is M.M_I1IO_DRIVE_STILL_AIMING \
        else body.split("\n")[-1]
    assert "i1Profiler 3.8.6 or older" in last


def test_s1_the_done_page_takes_the_way_from_the_catalogue():
    src = inspect.getsource(W.TableMeasureWindow._after_close)
    assert "M_I1IO_DRIVE_ARM_WAY_OUT_ENDED" in src
    assert "stayed extended over the table" not in inspect.getsource(W)


@pytest.mark.parametrize("code", LANGS)
def test_s1_s2_every_language_has_the_texts(code):
    i18n.set_language(code)
    try:
        for msg in (M.M_I1IO_DRIVE_STILL_AIMING, M.M_I1IO_DRIVE_ARM_WAY_OUT_ENDED,
                    M.M_I1IO_DRIVE_HOME_AT_START):
            title, body = msg.render(log="x")
            if code != "en":
                assert body != msg.body.replace("{log}", "x"), (code, msg.id)
            assert "—" not in body
        # the ended way states the limit itself (not flagged); the aiming page is flagged
        assert "3.8.7" in M.M_I1IO_DRIVE_ARM_WAY_OUT_ENDED.render()[1]
        assert not M.M_I1IO_DRIVE_ARM_WAY_OUT_ENDED.needs_old_i1profiler
        assert M.M_I1IO_DRIVE_STILL_AIMING.needs_old_i1profiler
        assert "3.8.7" not in M.M_I1IO_DRIVE_STILL_AIMING.render(log="x")[1]
    finally:
        i18n.set_language("en")


def test_s2_the_guided_start_homing_page_does_not_say_now():
    body = M.M_I1IO_DRIVE_HOME_AT_START.body
    assert "now" not in body.split("\n\n")[0]
    assert "ChromIQ can bring it there." in body


def _section(text: str, version: str) -> str:
    start = text.index(f"## v{version}\n")
    nxt = text.find("\n## v", start + 5)
    return text[start:nxt if nxt != -1 else len(text)]


def test_s3_the_changelog_states_nothing_untested_as_a_fact():
    sec = _section((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), "4.3.52")
    assert "works from wherever the arm is" not in sec
    assert "This has not been tried on a real table yet." in sec
    assert "when “Play sounds during measurement” is on" in sec
    assert "goes on" not in sec and "goes by itself" not in sec
    assert "—" not in sec


def test_s3_the_released_v4351_section_is_unchanged():
    try:
        old = subprocess.run(["git", "show", "v4.3.51:CHANGELOG.md"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    except Exception:      # noqa: BLE001 - no git here (a source package): nothing to compare
        pytest.skip("git is not available")
    if old.returncode != 0:
        pytest.skip("the tag v4.3.51 is not in this clone")
    now = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert _section(now, "4.3.51") == _section(old.stdout, "4.3.51")


@pytest.mark.parametrize("code", ["en", "de"])
def test_s1_the_done_page_after_the_back_strip_gives_the_power_switch_first(
        qtbot, monkeypatch, tmp_path, settings, code):  # noqa: F811
    """The reviewer's case on screen: the back-strip page (power switch first) and, after End
    measurement, the done page, which used to send the person to i1Profiler only."""
    from tests.i1io_table.test_4352_start_rule_by_state import _moves, _window
    i18n.set_language(code)
    try:
        win, sim, p = _window(qtbot, monkeypatch, tmp_path, settings, (1058.0, 317.0))
        p.drive_until(("refused", "stopped"))
        p.press("End measurement")
        assert p.drive_until(("done",)) == "done", win.pages_shown[-4:]
        text = win._text.text()
        way = M.M_I1IO_DRIVE_ARM_WAY_OUT_ENDED.render()[1]
        assert way in text
        # step 1 is the power switch (ARM-WAY-OUT's step 2, as translated), i1Profiler the last
        switch = M.M_I1IO_DRIVE_ARM_WAY_OUT.render()[1].split("\n")[2][3:]
        assert way.split("\n")[3] == "1. " + switch
        assert text.index(switch) < text.index("i1Profiler")
        assert text.count("3.8.7") == 1          # the limit once (the way states it itself)
        assert not _moves(sim.sim.received)
    finally:
        i18n.set_language("en")
