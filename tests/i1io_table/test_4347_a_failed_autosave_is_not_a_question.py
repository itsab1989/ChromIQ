"""4.3.47 (release review NOTE of 4.3.46): only the helper's QUESTIONS count as questions.

When a row ends, ``SpotReader.finish`` asks ``_prompt()`` where the helper is: at a prompt of
its own it is ended with Esc (its own way out), at its patch menu it is sent "done", which makes
it save its .ti3 one last time. ``_prompt()`` took EVERY ``{"event":"error"}`` for a prompt,
also the one the helper sends when the save after a reading could not replace the .ti3
("autosave_rename": Windows, a virus scanner holding the file) and then carries on at its menu
without waiting for anything. A row that ended right after such an event (``read()`` returns as
soon as an error arrives, before the next "spot_ready") was ended with Esc, and the helper's
final save was skipped.

Now only the error kinds after which the helper's C sources wait for a key count: "misread",
"coms", "cal_failed" (and "read_error", not reached in spot mode). Nothing sent to the table
changes: this is the reader of the i1Pro 2 only.
"""
from __future__ import annotations

import queue
import re
import sys
import time
from pathlib import Path

import pytest

from workflow.i1io.table import reader as rd

ROOT = Path(__file__).resolve().parents[2]
HELPER_SRC = ROOT / "native" / "chartread_helper"


class _Proc:
    """Stands in for ``reader._Proc``: *history* is what the helper has said so far, *after*
    what it says to the next commands; records what is sent."""

    history: "list[dict]" = []
    after: "list[dict]" = []

    def __init__(self, argv, log, cwd):
        self.events = list(self.history)
        self.sent: "list[dict]" = []
        self.q: "queue.Queue[dict]" = queue.Queue()
        for ev in self.after:
            self.q.put(ev)
        self._alive = True

    def send(self, obj):
        self.sent.append(obj)

    def wait(self, names, timeout):
        try:
            ev = self.q.get_nowait()
        except queue.Empty:
            return None
        self.events.append(ev)
        if ev.get("event") == "done":
            self._alive = False
        return ev

    def alive(self):
        return self._alive

    def stop(self, quit_cmd):
        self._alive = False


def _reader(tmp_path, monkeypatch, last_error, after):
    history = [{"event": "spot_ready", "loc": "A2"},
               {"event": "patch_read", "loc": "A2", "xyz": [1, 2, 3]}]
    if last_error is not None:
        history.append({"event": "error", "kind": last_error, "detail": ""})
    proc = type("P", (_Proc,), {"history": history, "after": after})
    monkeypatch.setattr(rd, "_Proc", proc)
    return rd.SpotReader(Path("chromiq-chartread"), tmp_path, "row",
                         [("1", "A1"), ("2", "A2")], lambda *a: None, False)


def test_a_failed_autosave_is_not_a_question(tmp_path, monkeypatch):
    r = _reader(tmp_path, monkeypatch, "autosave_rename", [])
    assert r._prompt() is None


def test_a_row_ending_after_a_failed_autosave_still_saves(tmp_path, monkeypatch):
    r = _reader(tmp_path, monkeypatch, "autosave_rename",
                [{"event": "saved", "path": "row.ti3"}, {"event": "done"}])
    r.finish(timeout=1)
    assert r.proc.sent[0] == {"cmd": "done"}, r.proc.sent


@pytest.mark.parametrize("kind", ["misread", "coms", "cal_failed", "read_error"])
def test_the_helpers_questions_still_end_it_with_esc(tmp_path, monkeypatch, kind):
    r = _reader(tmp_path, monkeypatch, kind, [{"event": "done"}])
    assert r._prompt() is not None and r._prompt()["kind"] == kind
    r.finish(timeout=1)
    assert r.proc.sent[0] == {"cmd": "quit"}, r.proc.sent
    assert {"cmd": "done"} not in r.proc.sent


def test_a_goto_it_could_not_follow_is_still_no_question(tmp_path, monkeypatch):
    r = _reader(tmp_path, monkeypatch, "patch_not_found", [])
    assert r._prompt() is None


# ---- the list is the C sources' --------------------------------------------------------------

def _c_sources() -> str:
    return "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(HELPER_SRC.glob("*.c")))


def _emitted_kinds(src: str) -> "set[str]":
    kinds = set(re.findall(r'cq_emit_error\("([a-z_]+)"', src))
    kinds |= set(re.findall(r'\\"kind\\":\\"([a-z_]+)\\"', src))
    return kinds


def test_every_kind_counted_as_a_question_is_followed_by_a_wait_for_a_key():
    src = _c_sources()
    lines = src.splitlines()
    for kind in rd.KEY_PROMPT_ERROR_KINDS:
        at = [i for i, ln in enumerate(lines)
              if f'cq_emit_error("{kind}"' in ln or f'\\"kind\\":\\"{kind}\\"' in ln]
        assert at, f"{kind} is not emitted by the helper"
        for i in at:
            # the emission itself, or the function it is in (cq_emit_coms_error), is followed
            # by the key wait within a few lines of the place it is called from
            near = "\n".join(lines[i:i + 12])
            if "cq_prompt_char()" in near or "cq_wait_char()" in near:
                continue
            fn = re.search(r"static void (cq_emit_\w+)\(", "\n".join(lines[max(0, i - 12):i]))
            assert fn, f"{kind} at line {i + 1}: no key wait follows"
            calls = [j for j, ln in enumerate(lines) if f"{fn.group(1)}(it, rv)" in ln]
            assert calls, kind
            for j in calls:
                after = "\n".join(lines[j:j + 4])
                assert "cq_prompt_char()" in after or "cq_wait_char()" in after, \
                    f"{kind} at line {j + 1}: no key wait follows"


def test_the_failed_autosave_is_followed_by_no_wait():
    src = _c_sources()
    i = src.index('\\"kind\\":\\"autosave_rename\\"')
    tail = src[i:i + 400]
    assert "return;" in tail and "cq_wait_char" not in tail and "cq_prompt_char" not in tail
    assert "autosave_rename" in _emitted_kinds(src)


# ---- the app's SpotReader on the REAL committed helper (its replay instrument) --------------

def _helper():
    sys.path.insert(0, str(ROOT / "tests" / "helpers"))
    from replay_tools import HELPER  # noqa: E402
    if not HELPER.exists():
        pytest.skip("chromiq-chartread not built")
    return HELPER


def test_the_real_helper_saves_the_last_reading_after_a_failed_autosave(tmp_path,
                                                                        monkeypatch):
    """The last patch's autosave fails (a folder stands where the .ti3 goes, as a held file
    does on Windows); the folder is gone again when the row ends; the row's .ti3 must then hold
    the last reading, written by the helper's final save."""
    helper = _helper()
    monkeypatch.setenv("CHROMIQ_REPLAY_INSTRUMENT", "i1pro2")
    monkeypatch.setenv("CHROMIQ_ENGINE_MUTE", "1")
    monkeypatch.delenv("CHROMIQ_REPLAY_NEEDCAL", raising=False)
    replay = tmp_path / "replay.txt"
    replay.write_text("PATCHES 2\nSTRIP A\n" + "50 50 50\n" * 2, encoding="utf-8")
    rdir = tmp_path / "reader"
    r = rd.SpotReader(helper, rdir, "row", [("1", "A1"), ("2", "A2")], lambda *a: None,
                      False, extra_args=("--replay", str(replay), "-S"))
    try:
        r.open(lambda ev: True, timeout=20)
        r.read("A1", timeout=10)
        end = time.monotonic() + 5
        while not (rdir / "row.ti3").is_file() and time.monotonic() < end:
            time.sleep(0.02)
        (rdir / "row.ti3").rename(rdir / "row-after-A1.ti3")
        (rdir / "row.ti3").mkdir()
        r.read("A2", timeout=10)
        end = time.monotonic() + 5
        while (not any(e.get("kind") == "autosave_rename" for e in r.proc.events)
               and time.monotonic() < end):
            time.sleep(0.02)
        (rdir / "row.ti3").rmdir()
        # the moment of the fault: the failed autosave is the newest thing the helper said
        r.proc.events[:] = [e for e in r.proc.events
                            if not (e.get("event") == "spot_ready" and e.get("all_done"))]
        ti3 = r.finish(timeout=10)
    finally:
        r.close()
    assert not r.proc.alive()
    assert ti3 is not None and ti3.is_file()
    assert '"A2"' in ti3.read_text(encoding="utf-8")
