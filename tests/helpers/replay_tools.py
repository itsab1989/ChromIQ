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


class ReplaySession:
    """Drive chromiq-chartread --json --replay as a live subprocess."""

    def __init__(self, chart_base: Path, replay: Path,
                 extra_args: list[str] | None = None) -> None:
        cmd = [str(HELPER), "--json", "--replay", str(replay)]
        cmd += extra_args or []
        cmd.append(str(chart_base))
        self.proc = subprocess.Popen(
            cmd, cwd=chart_base.parent,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.events: list[dict] = []
        self.raw_lines: list[str] = []
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

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
