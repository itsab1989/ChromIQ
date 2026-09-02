"""Helpers for driving chromiq-chartread's replay mode in tests.

The replay script feeds the *real* chartread code path through a fake
instrument (see native/chartread_helper/chromiq_replay.c) — faults and
wrong swipes are injected live via the JSON command channel.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HELPER = REPO / "native" / "chartread_helper" / "build" / "chromiq-chartread"


def parse_ti2_rows(ti2_path: Path) -> tuple[int, dict[str, list[tuple[float, float, float]]]]:
    """Return (steps_per_pass, {pass_letter: [(X,Y,Z), …]}) from a .ti2.

    Uses SAMPLE_LOC ("A1"…) for row assignment and the expected XYZ fields.
    """
    text = ti2_path.read_text(encoding="latin-1")
    lines = text.splitlines()
    fields: list[str] = []
    in_fmt = in_data = False
    steps = 0
    rows: dict[str, list[tuple[int, tuple[float, float, float]]]] = {}
    for ln in lines:
        s = ln.strip()
        if s.startswith("STEPS_IN_PASS"):
            steps = int(s.split('"')[1])
        elif s == "BEGIN_DATA_FORMAT":
            in_fmt = True
        elif s == "END_DATA_FORMAT":
            in_fmt = False
        elif in_fmt:
            fields += s.split()
        elif s == "BEGIN_DATA":
            in_data = True
        elif s == "END_DATA":
            in_data = False
        elif in_data and s:
            vals = s.split()
            rec = dict(zip(fields, vals))
            loc = rec["SAMPLE_LOC"].strip('"')
            letter = "".join(c for c in loc if c.isalpha())
            num = int("".join(c for c in loc if c.isdigit()))
            xyz = (float(rec["XYZ_X"]), float(rec["XYZ_Y"]), float(rec["XYZ_Z"]))
            rows.setdefault(letter, []).append((num, xyz))
    out = {k: [xyz for _, xyz in sorted(v)] for k, v in rows.items()}
    return steps, out


def write_replay_script(ti2_path: Path, out_path: Path,
                        noise: float = 0.0) -> None:
    """Write a replay script whose readings equal the chart's expected
    values (optionally with a deterministic offset to mimic print drift)."""
    steps, rows = parse_ti2_rows(ti2_path)
    with out_path.open("w") as fp:
        fp.write(f"# replay for {ti2_path.name}\nPATCHES {steps}\n")
        for letter in sorted(rows):
            fp.write(f"STRIP {letter}\n")
            for x, y, z in rows[letter]:
                fp.write(f"{x + noise:.4f} {y + noise:.4f} {z + noise:.4f}\n")


#: Every session that has been started and not yet finished. A test that fails
#: or raises before calling ``finish()`` used to leave its helper running for
#: good — the process sits waiting on stdin, and nothing reaps it. Measured
#: 2026-08-05: 162 of them alive at once, which starved a gate worker into a
#: segmentation fault at 97%. ``tests/conftest.py`` empties this after every
#: test, so a leak is now impossible rather than merely unlikely.
_LIVE: "list[ReplaySession]" = []


def reap_live_sessions() -> int:
    """Kill any helper still running and return how many there were.

    AND CLOSE ITS PIPES, IN THE RIGHT ORDER. Killing the process alone leaves
    the pipes for the garbage collector, which raises BrokenPipeError while
    finalising a file object — pytest reports that as an ERROR on an otherwise
    passing test. Twelve of them appeared on a full parallel gate while every
    one of those files passed alone, which is exactly the noise that trains
    people to stop reading the gate.

    ORDER MATTERS, and `test_cr30_external_values.kill` had already worked it
    out for its own helper: kill, reap, JOIN the reader thread, and only then
    close. Closing while the reader is still inside its iterator turns the
    BrokenPipeError into a ValueError and pytest still reports an unraisable
    warning.
    """
    killed = 0
    for session in list(_LIVE):
        try:
            if session.proc.poll() is None:
                session.proc.kill()
                killed += 1
        except Exception:      # noqa: BLE001 — cleanup must not raise
            pass
        try:
            session.proc.wait(timeout=5)
        except Exception:      # noqa: BLE001 — teardown only
            pass
        reader = getattr(session, "_reader", None)
        if reader is not None and reader.is_alive():
            try:
                reader.join(timeout=5)
            except Exception:  # noqa: BLE001
                pass
        for pipe in (getattr(session.proc, "stdin", None),
                     getattr(session.proc, "stdout", None),
                     getattr(session.proc, "stderr", None)):
            try:
                if pipe is not None and not pipe.closed:
                    pipe.close()
            except (BrokenPipeError, OSError, ValueError):
                pass
        try:
            _LIVE.remove(session)
        except ValueError:
            pass
    return killed


class ReplaySession:
    """Drive chromiq-chartread --json --replay as a live subprocess.

    Usable as a context manager — ``with ReplaySession(...) as s:`` — which is
    the better habit, because it does not depend on the safety net above.
    """

    def __init__(self, chart_base: Path, replay: Path,
                 extra_args: list[str] | None = None) -> None:
        cmd = [str(HELPER), "--json", "--replay", str(replay)]
        cmd += extra_args or []
        cmd.append(str(chart_base))
        self.proc = subprocess.Popen(
            cmd, cwd=chart_base.parent,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1, encoding="utf-8")
        self.events: list[dict] = []
        self.raw_lines: list[str] = []
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        _LIVE.append(self)

    def __enter__(self) -> "ReplaySession":
        return self

    def __exit__(self, *_exc) -> None:
        self.finish()

    def _read(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            line = line.rstrip("\n")
            with self._lock:
                self.raw_lines.append(line)
                if line.startswith("{"):
                    try:
                        self.events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    def send(self, **cmd) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(cmd) + "\n")
        self.proc.stdin.flush()

    def wait_event(self, name: str, timeout: float = 10.0,
                   after: int = 0, **fields) -> dict:
        """Return the first `name` event with index >= after.

        ``fields`` narrows it: ``wait_event("strip_ready", strip="B")`` waits
        for the strip_ready that names B rather than for whichever arrives
        first. That matters after a ``goto`` — the helper can still be
        finishing with the strip it was on, so the next strip_ready is not
        necessarily the one the goto asked for, and a test that takes the first
        one passes or fails on timing. (Seen on a full-suite run, 2026-08-01:
        ``assert 'A' == 'B'`` in test_goto_jumps_and_allows_remeasure.)
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                for i, ev in enumerate(self.events):
                    if i < after or ev.get("event") != name:
                        continue
                    if all(ev.get(k) == v for k, v in fields.items()):
                        return ev
            time.sleep(0.02)
        with self._lock:
            tail = "\n".join(self.raw_lines[-15:])
        want = "".join(f" {k}={v!r}" for k, v in fields.items())
        raise TimeoutError(
            f"no '{name}'{want} event within {timeout}s; tail:\n{tail}")

    def event_index(self) -> int:
        with self._lock:
            return len(self.events)

    def finish(self, timeout: float = 10.0) -> int:
        try:
            return self.proc.wait(timeout=timeout)
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
            try:
                _LIVE.remove(self)
            except ValueError:
                pass
